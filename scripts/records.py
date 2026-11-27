#!/usr/bin/env python3
"""Checks too long for any gate, by record: whether each record still
covers the code it checked.

    python3 scripts/records.py check [RECORD...] [--refine PATH] [--fail-stale] [--github]
    python3 scripts/records.py stamp RECORD [--refine PATH] [--commit REV]
    python3 scripts/records.py digest PROGRAM --target T --symbol S [--refine PATH]

A check that takes hours, such as the run of every f32 input of
core/math against MPFR, runs on a host, never in a gate (D2874), and is
recorded in a JSON file under compiler/tests/records/: the commands, the
host, the date, the commit, the results, and for each routine it checked
the digest of that routine's emitted code on each target the record
claims.  compiler/tests/records/README.md describes the form.

`check` compiles each record's program for each target it names, with
the options it names, and says whether the record is fresh, every
routine's code what it was at the record's commit, or stale, naming the
routines and targets whose code changed since.  A stale record fails no
push: `check` exits 0 unless `--fail-stale` is given, which a release or
a phase-gate claim that cites a record runs.  An unreadable record, a
program refine refuses or a target it does not know exit 2.

`stamp` writes the digests of the current tree's code into a record,
for each routine and target it already names, and its commit, after its
check has been run again.  `digest` prints one routine's digest.

A routine's code is the assembly refine emits for the program, from the
section holding the routine's label through every section it reaches by
naming a label another section defines, in the order first reached, so
a change to code the routine does not reach leaves its digest alone.
Before hashing, the assembler's local names are renumbered in the order
they first appear, the numbers refine gives sections are dropped, and a
trap message's line and column are dropped, so that inserting a routine
before it, or a line above it in its file, changes nothing; the
instructions, the constants and what each trap reports remain.
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import lane_refine  # noqa: E402

RECORDS = ROOT / 'compiler/tests/records'
SCHEMA = 1
#  The fields every record holds; README.md says what each is.
REQUIRED = ('schema', 'title', 'check', 'commands', 'host', 'date', 'commit',
            'program', 'options', 'targets', 'routines')

LABEL = re.compile(r'^([A-Za-z_.$][\w.$]*):')
NAME = re.compile(r'[A-Za-z_.$][\w.$]*')
STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
#  refine numbers the sections of routines, traps, data and evidence in
#  the order it emits them; the number says nothing about the code.
SECTION_NUMBER = re.compile(r'\b(landin_(?:routine|trap|datum|evidence))_\d+\b')
#  A trap's message names its source position, `file.ldn:LINE:COLUMN:`,
#  and the instructions that report it pass its length within the next
#  few lines, which a position's digits change.
TRAP_POSITION = re.compile(r'(\.ldn):\d+:\d+:')
ASCIZ = re.compile(r'^\s*\.asciz\s+"((?:[^"\\]|\\.)*)"\s*$')
LENGTH_WINDOW = 3


class Failure(Exception):
    """A record or a program that cannot be checked at all."""


def chunks(text):
    """The assembly as its preamble and a list of sections, each a list of
    lines, in file order.  `.section` and `.text` start a section;
    `.pushsection` starts one that `.popsection` leaves, the lines after
    the pop going on with the section it interrupted."""
    preamble = []
    found = []
    current = None
    stack = []
    for line in text.splitlines():
        directive = line.strip().split(None, 1)[0] if line.strip() else ''
        if directive in ('.section', '.text', '.data', '.bss'):
            current = [line]
            found.append(current)
            stack = []
        elif directive == '.pushsection':
            stack.append(current)
            current = [line]
            found.append(current)
        elif directive == '.popsection':
            current = stack.pop() if stack else None
            if current is None:
                current = []
                found.append(current)
        elif current is None:
            preamble.append(line)
        else:
            current.append(line)
    return preamble, found


def names_in(line):
    """The names a line mentions outside its string literals."""
    return NAME.findall(STRING.sub('""', line))


class Assembly:
    """An assembly file parsed once: its preamble, its sections, the
    section defining each label, and each trap message's length by its
    label, for the closures of all the routines a record names."""

    def __init__(self, text):
        self.preamble, self.sections = chunks(text)
        self.defines = {}
        self.lengths = {}
        for index, section in enumerate(self.sections):
            labels = []
            length = None
            for line in section:
                match = LABEL.match(line)
                if match:
                    labels.append(match.group(1))
                    self.defines.setdefault(match.group(1), index)
                elif length is None:
                    message = ASCIZ.match(line)
                    if message and TRAP_POSITION.search(message.group(1)):
                        length = trap_length(message.group(1))
            if length is not None:
                for label in labels:
                    self.lengths[label] = length


def closure(text, symbol):
    """The canonical text of SYMBOL's code in the assembly TEXT, a string
    or an Assembly: the preamble, then each section reached from the one
    defining SYMBOL, in the order first reached, local names renumbered.
    Raises KeyError when no section defines SYMBOL."""
    parsed = text if isinstance(text, Assembly) else Assembly(text)
    preamble, sections, defines = parsed.preamble, parsed.sections, parsed.defines
    start = defines[symbol]
    order = [start]
    seen = {start}
    at = 0
    while at < len(order):
        for line in sections[order[at]]:
            for name in names_in(line):
                index = defines.get(name)
                if index is not None and index not in seen:
                    seen.add(index)
                    order.append(index)
        at += 1
    lengths = parsed.lengths
    local = {}

    def rename(match):
        name = match.group(0)
        if not name.startswith('.L'):
            return name
        if name not in local:
            local[name] = '.L%d' % len(local)
        return local[name]

    def canonical(line):
        line = TRAP_POSITION.sub(r'\1:', line.rstrip())
        line = SECTION_NUMBER.sub(r'\1', line)
        return outside_strings(line, lambda part: NAME.sub(rename, part))

    def section_text(lines):
        pending = []
        for line in lines:
            if not line.strip():
                continue
            #  The window ends at the next label, where other code starts.
            pending = [] if LABEL.match(line) else [
                (n, left - 1) for n, left in pending if left > 0]
            if not LABEL.match(line):
                pending += [(lengths[name], LENGTH_WINDOW) for name in names_in(line)
                            if name in lengths]
            line = canonical(line)
            for length, _ in pending:
                line = outside_strings(
                    line, lambda part, n=length: re.sub(
                        r'(?<![\w.])([#$]?)%d\b' % n, r'\1<length>', part))
            yield line

    out = list(section_text(preamble))
    for index in order:
        out.extend(section_text(sections[index]))
    return '\n'.join(out) + '\n', len(order)


def outside_strings(line, change):
    """LINE with CHANGE applied to each part outside its string literals."""
    pieces = []
    last = 0
    for literal in STRING.finditer(line):
        pieces.append(change(line[last:literal.start()]))
        pieces.append(literal.group(0))
        last = literal.end()
    pieces.append(change(line[last:]))
    return ''.join(pieces)


def trap_length(message):
    """The bytes of a trap message as an `.asciz` operand spells it."""
    return len(message.encode('utf-8').decode('unicode_escape').encode('latin-1'))


def digest(text, symbol):
    body, count = closure(text, symbol)
    return hashlib.sha256(body.encode('utf-8')).hexdigest(), count


def emit(refine, program, target, options, scratch, library=None):
    """The assembly refine emits for PROGRAM on TARGET."""
    out = Path(scratch) / ('%s.s' % target)
    made = subprocess.run([*lane_refine.compile_command(refine, library), *options,
                           '--target', target, '--emit', 'asm', str(program),
                           '-o', str(out)],
                          capture_output=True, text=True, check=False, timeout=600)
    if made.returncode != 0:
        raise Failure('refine refused %s for %s:\n%s'
                      % (program, target, made.stderr.strip()))
    return out.read_text(encoding='utf-8')


def load(path):
    try:
        record = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise Failure('%s: %s' % (path, error))
    problems = validate(record)
    if problems:
        raise Failure('%s: %s' % (path, '; '.join(problems)))
    return record


def validate(record):
    """What is wrong with a record's form, as a list of sentences."""
    if not isinstance(record, dict):
        return ['not a JSON object']
    problems = ['no %s' % key for key in REQUIRED if key not in record]
    if problems:
        return problems
    if record['schema'] != SCHEMA:
        problems.append('schema %r, not %d' % (record['schema'], SCHEMA))
    if not re.fullmatch(r'[0-9a-f]{40}', str(record['commit'])):
        problems.append('commit is not a full commit name')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(record['date'])):
        problems.append('date is not YYYY-MM-DD')
    if not (ROOT / record['program']).is_file():
        problems.append('no program %s' % record['program'])
    targets = record['targets']
    if not isinstance(targets, list) or not targets:
        problems.append('targets is not a list of targets')
        targets = []
    if not isinstance(record['commands'], list) or not record['commands']:
        problems.append('commands is not a list of commands')
    routines = record['routines']
    if not isinstance(routines, dict) or not routines:
        return problems + ['routines is not an object of routines']
    for symbol, entry in routines.items():
        digests = entry.get('digests') if isinstance(entry, dict) else None
        if not isinstance(digests, dict):
            problems.append('%s has no digests' % symbol)
            continue
        if sorted(digests) != sorted(targets):
            problems.append('%s has digests for %s, not the targets %s'
                            % (symbol, ', '.join(sorted(digests)), ', '.join(targets)))
        for target, value in digests.items():
            if not re.fullmatch(r'[0-9a-f]{64}', str(value)):
                problems.append('%s on %s: digest is not SHA-256' % (symbol, target))
    return problems


def measure(record, refine, library=None):
    """Each routine's digest on each target for the current tree, as
    {symbol: {target: digest or None}}, None where no section defines it."""
    found = {symbol: {} for symbol in record['routines']}
    with tempfile.TemporaryDirectory(prefix='records-') as scratch:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            texts = dict(zip(record['targets'], pool.map(
                lambda target: emit(refine, ROOT / record['program'], target,
                                    record['options'], scratch, library),
                record['targets'])))
    for target, text in texts.items():
        text = Assembly(text)
        for symbol in record['routines']:
            try:
                found[symbol][target] = digest(text, symbol)[0]
            except KeyError:
                found[symbol][target] = None
    return found


def judge(record, found):
    """The routines and targets whose code differs from the record's."""
    changed = []
    for symbol, entry in record['routines'].items():
        for target in record['targets']:
            now = found[symbol][target]
            if now != entry['digests'][target]:
                changed.append((symbol, target, now is None))
    return changed


def relative(path):
    path = Path(path).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def all_records():
    return sorted(RECORDS.glob('*.json'))


def command_check(args, refine):
    paths = args.records or all_records()
    stale = 0
    for path in paths:
        record = load(path)
        changed = judge(record, measure(record, refine, args.library))
        name = relative(path)
        count = len(record['routines'])
        since = '%s (%s)' % (record['commit'][:12], record['date'])
        if not changed:
            print('fresh  %s: %d routines on %s, unchanged since %s'
                  % (name, count, ', '.join(record['targets']), since))
            continue
        stale += 1
        print('stale  %s: %d of %d routines changed since %s:'
              % (name, len({symbol for symbol, _, _ in changed}), count, since))
        for symbol, target, gone in changed:
            print('         %s on %s%s' % (symbol, target, ', no longer emitted' if gone else ''))
        print('       run its commands again and `records.py stamp %s`, or withdraw'
              ' what cites it' % name)
        if args.github:
            routines = ', '.join(sorted({symbol for symbol, _, _ in changed}))
            print('::warning file=%s::%s is stale since %s: %s changed; a release or'
                  ' phase-gate claim citing it is refused until it is run again'
                  % (name, name, since, routines))
            summary = os.environ.get('GITHUB_STEP_SUMMARY')
            if summary:
                with open(summary, 'a', encoding='utf-8') as out:
                    out.write('- **stale** `%s` since %s: %s\n' % (name, since, routines))
    if not paths:
        print('no records under %s' % relative(RECORDS))
    return 1 if stale and args.fail_stale else 0


def command_stamp(args, refine):
    path = Path(args.record)
    record = load(path)
    found = measure(record, refine, args.library)
    missing = [(s, t) for s, by in found.items() for t, d in by.items() if d is None]
    if missing:
        raise Failure('no section defines %s' % ', '.join('%s on %s' % m for m in missing))
    for symbol, by in found.items():
        record['routines'][symbol]['digests'] = {t: by[t] for t in record['targets']}
    revision = subprocess.run(['git', 'rev-parse', args.commit], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    record['commit'] = revision
    path.write_text(json.dumps(record, indent=1) + '\n', encoding='utf-8')
    print('stamped %s at %s' % (relative(path), revision[:12]))
    return 0


def command_digest(args, refine):
    with tempfile.TemporaryDirectory(prefix='records-') as scratch:
        text = emit(refine, Path(args.program), args.target, args.option or [], scratch,
                    args.library)
    try:
        value, count = digest(text, args.symbol)
    except KeyError:
        raise Failure('no section of %s on %s defines %s'
                      % (args.program, args.target, args.symbol))
    print(json.dumps({'symbol': args.symbol, 'target': args.target, 'digest': value,
                      'sections': count}))
    return 0


def default_refine():
    found = sorted(ROOT.glob('compiler/ada/build/*/*/bin/refine'),
                   key=lambda path: path.stat().st_mtime)
    if not found:
        raise Failure('no refine: build one with ./scripts/dev-build.sh, or name one'
                      ' with --refine')
    return found[-1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    lane_refine.argument(parser, required=False, environment=True)
    lane_refine.library_argument(parser)
    commands = parser.add_subparsers(dest='command', required=True)
    checked = commands.add_parser('check', help='say whether each record is fresh')
    checked.add_argument('records', nargs='*', help='records to check; every one by default')
    checked.add_argument('--fail-stale', action='store_true',
                         help='exit 1 when a record is stale, as a release or a'
                              ' phase-gate claim citing it does')
    checked.add_argument('--github', action='store_true',
                         help='also write a warning annotation and a summary line for'
                              ' each stale record, as the gate does')
    stamped = commands.add_parser('stamp', help="write the current tree's digests into a record")
    stamped.add_argument('record')
    stamped.add_argument('--commit', default='HEAD',
                         help='the commit the record\'s run checked; HEAD by default')
    one = commands.add_parser('digest', help="print one routine's digest")
    one.add_argument('program')
    one.add_argument('--target', required=True)
    one.add_argument('--symbol', required=True)
    one.add_argument('--option', action='append',
                     help='a compile option, repeated for each word, such as'
                          ' --option=--optimize --option=speed')
    args = parser.parse_args(argv)
    try:
        refine = args.refine or default_refine()
        if args.command == 'check':
            return command_check(args, refine)
        if args.command == 'stamp':
            return command_stamp(args, refine)
        return command_digest(args, refine)
    except Failure as failure:
        print('records: %s' % failure, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
