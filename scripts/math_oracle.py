#!/usr/bin/env python3
"""core/math against MPFR: the fixtures' tables, and the larger runs.

    python3 scripts/math_oracle.py fixtures [NAME...]
    python3 scripts/math_oracle.py measure FUNCTION WIDTH [--count N] [--seed N]
    python3 scripts/math_oracle.py exhaustive FUNCTION [--jobs N]

`fixtures` writes each `math-*` runtime fixture compiler/tests/math/
cases/*.json describes, or the ones named: a program whose tables hold
inputs and MPFR's correctly rounded results, and which checks that every
result core/math gives is within the table's bound of it, counted in
representable floats, on every target the fixture names.  It writes
compiler/tests/math/evaluate.ldn too, the program the other two run.

`measure` draws COUNT inputs (a million by default) from the function's
domains in its fixture's description, runs them through evaluate.ldn on
this host, and prints MPFR's verdict as one JSON object: the largest
error in units in the last place and an input that gives it.
`exhaustive` does the same for every one of the 2^32 inputs of a
one-argument f32 function, split among JOBS processes.

The oracle is compiler/tests/math/oracle.c, built here against the MPFR
and GMP of flake.lock's nixpkgs, which `nix build --inputs-from .`
fetches, or of the prefixes $LANDIN_MPFR and $LANDIN_GMP name.  The
programs are compiled with `--refine`, $LANDIN_REFINE, or the refine this
checkout built last.  compiler/tests/math/README.md says what the
evidence is.
"""

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import lane_refine  # noqa: E402

MATH = ROOT / 'compiler/tests/math'
CASES = MATH / 'cases'
EVALUATE = MATH / 'evaluate.ldn'
FIXTURES = ROOT / 'compiler/tests/fixtures/runtime'

#  Every target a runtime fixture runs on; the Cortex-M, RV32 and Xtensa
#  firmware lanes take theirs from compiler/tests/cortex-m/corpus.json.
TARGETS = ('linux-x86-64, linux-arm64, linux-rv64, darwin-arm64, '
           'freebsd-x86-64, freebsd-arm64, cortex-m0, windows-x86-64, '
           'windows-arm64')

#  The functions the oracle knows, with their arity.
ARITY = {
    'sqrt': 1, 'cbrt': 1, 'hypot': 2, 'fma': 3, 'floor': 1, 'ceil': 1,
    'trunc': 1, 'round': 1, 'round_even': 1, 'remainder': 2,
    'remainder_nearest': 2, 'exp': 1, 'exp2': 1, 'expm1': 1, 'log': 1,
    'log2': 1, 'log10': 1, 'log1p': 1, 'pow': 2, 'sin': 1, 'cos': 1,
    'tan': 1, 'asin': 1, 'acos': 1, 'atan': 1, 'atan2': 2, 'sinh': 1,
    'cosh': 1, 'tanh': 1, 'asinh': 1, 'acosh': 1, 'atanh': 1, 'erf': 1,
    'erfc': 1, 'gamma': 1, 'log_gamma': 1,
}

#  Each argument's name in the routine, for the generated calls.
PARAMETERS = {1: ('x',), 2: ('x', 'y'), 3: ('x', 'y', 'z')}


class Failure(Exception):
    """A refusal to report on one line."""


def nix_prefix(attribute):
    found = subprocess.run(
        ['nix', 'build', '--inputs-from', str(ROOT), 'nixpkgs#' + attribute,
         '--no-link', '--print-out-paths'],
        capture_output=True, text=True, check=False)
    if found.returncode != 0:
        raise Failure('nix build nixpkgs#%s failed; name the prefix with $LANDIN_MPFR'
                      ' and $LANDIN_GMP instead:\n%s' % (attribute, found.stderr))
    return Path(found.stdout.split()[-1])


def build_oracle():
    """The oracle, built once per source into the checkout's build tree."""
    source = MATH / 'oracle.c'
    tag = os.environ.get('LANDIN_BUILD_TAG', 'host')
    out = ROOT / 'compiler/ada/build' / tag / 'math'
    out.mkdir(parents=True, exist_ok=True)
    binary = out / 'oracle'
    if binary.exists() and binary.stat().st_mtime >= source.stat().st_mtime:
        return binary
    if os.environ.get('LANDIN_MPFR') and os.environ.get('LANDIN_GMP'):
        mpfr_include = mpfr_lib = Path(os.environ['LANDIN_MPFR'])
        gmp_include = gmp_lib = Path(os.environ['LANDIN_GMP'])
    else:
        mpfr_include, mpfr_lib = nix_prefix('mpfr.dev'), nix_prefix('mpfr.out')
        gmp_include, gmp_lib = nix_prefix('gmp.dev'), nix_prefix('gmp.out')
    compiler = shutil.which('cc') or shutil.which('clang')
    if compiler is None:
        raise Failure('no C compiler on PATH: run inside nix develop')
    command = [compiler, '-O2', '-o', str(binary), str(source),
               '-I%s/include' % mpfr_include, '-I%s/include' % gmp_include,
               '-L%s/lib' % mpfr_lib, '-L%s/lib' % gmp_lib,
               '-Wl,-rpath,%s/lib' % mpfr_lib, '-Wl,-rpath,%s/lib' % gmp_lib,
               '-lmpfr', '-lgmp', '-lm']
    built = subprocess.run(command, capture_output=True, text=True, check=False)
    if built.returncode != 0:
        raise Failure('building the oracle failed:\n' + built.stderr)
    return binary


def default_refine():
    """The refine this checkout built last."""
    found = sorted(ROOT.glob('compiler/ada/build/*/*/bin/refine'),
                   key=lambda path: path.stat().st_mtime)
    if not found:
        raise Failure('no refine: build one with ./scripts/dev-build.sh, or name'
                      ' one with --refine')
    return found[-1]


def descriptions():
    """Every fixture's description, by fixture name, in file order."""
    found = {}
    for path in sorted(CASES.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        for name, fixture in data['fixtures'].items():
            if name in found:
                raise Failure('%s describes %s a second time' % (path, name))
            fixture['source'] = path
            found[name] = fixture
    return found


def special_bits(text, width):
    """The bits of a special input, written as Python reads a float or
    a hexadecimal float, or `nan`; refused unless exact at WIDTH."""
    value = float.fromhex(text) if 'x' in text.lower() else float(text)
    if width == 64:
        return struct.unpack('<Q', struct.pack('<d', value))[0]
    bits = struct.unpack('<I', struct.pack('<f', value))[0]
    back = struct.unpack('<f', struct.pack('<I', bits))[0]
    if back != value and not (value != value):
        raise Failure('special %s is not exact in f32' % text)
    return bits


def table_cases(oracle, table, seed):
    """The oracle's lines for TABLE: lists of integers, the inputs and the
    correctly rounded result."""
    width = table['width']
    arity = ARITY[table['fn']]
    command = [str(oracle), 'cases', '--fn', table['fn'], '--width', str(width),
               '--seed', str(seed), '--random', str(table.get('random', 0)),
               '--hard', str(table.get('hard', 0)),
               '--pool', str(table.get('pool', 20000))]
    for argument, flag in ((0, '--domain'), (1, '--domain2'), (2, '--domain3')):
        for domain in domains_of(table, argument):
            command += [flag, domain]
    for special in table.get('specials', []):
        values = special if isinstance(special, list) else [special]
        if len(values) != arity:
            raise Failure('special %s of %s has not %d inputs' % (special, table['fn'], arity))
        command += ['--special', ','.join('%x' % special_bits(v, width) for v in values)]
    made = subprocess.run(command, capture_output=True, text=True, check=False)
    if made.returncode != 0:
        raise Failure('the oracle refused %s:\n%s' % (' '.join(command), made.stderr))
    return [[int(word, 16) for word in line.split()] for line in made.stdout.splitlines()]


def domains_of(table, argument):
    key = 'domains' if argument == 0 else 'domains%d' % (argument + 1)
    return table.get(key, [])


def landin_array(name, kind, words, width):
    """An array value NAME of WORDS in hexadecimal, wrapped at 72 columns."""
    digits = width // 4
    items = ['0x%0*x' % (digits, word) for word in words]
    lines, line = [], '    '
    for item in items:
        piece = item + ', '
        if len(line) + len(piece) > 76:
            lines.append(line.rstrip())
            line = '    '
        line += piece
    lines.append(line.rstrip().rstrip(','))
    return '%s: [%d]%s = [\n%s]\n' % (name, len(items), kind, '\n'.join(lines))


CHECKER = '''\
--  Reading and comparing bits, written here rather than taken from
--  core/math, so that the check does not lean on what it checks.
bits_64: (x: f64) -> (bits: u64) =
    view: ptr u64 = ptr(usize(addr x))
    bits = view.val
end bits_64

from_64: (bits: u64) -> (x: f64) =
    view: ptr f64 = ptr(usize(addr bits))
    x = view.val
end from_64

bits_32: (x: f32) -> (bits: u32) =
    view: ptr u32 = ptr(usize(addr x))
    bits = view.val
end bits_32

from_32: (bits: u32) -> (x: f32) =
    view: ptr f32 = ptr(usize(addr bits))
    x = view.val
end from_32

--  A float's place in the order of all floats: the next float up is one
--  more, and both zeros are one place.
place_64: (bits: u64) -> (key: u64) =
    key = if bits >> 63 == 1 then 0x8000000000000000 - (bits & 0x7fffffffffffffff)
          else 0x8000000000000000 + bits end if
end place_64

place_32: (bits: u32) -> (key: u32) =
    key = if bits >> 31 == 1 then 0x80000000 - (bits & 0x7fffffff)
          else 0x80000000 + bits end if
end place_32

--  Whether `got` is within `bound` floats of the correctly rounded
--  `want`: NaN only for NaN, an infinity only for itself, and a zero's
--  sign kept.
within_64: (got: f64, want: u64, bound: u64) -> (yes: bool) =
    expected := from_64(want)
    have := bits_64(got)
    if expected <> expected or got <> got then
        yes = expected <> expected and got <> got
    elsif want & 0x7fffffffffffffff == 0x7ff0000000000000
      or have & 0x7fffffffffffffff == 0x7ff0000000000000 then
        yes = have == want
    elsif (expected == 0.0 or got == 0.0) and have >> 63 <> want >> 63 then
        yes = false
    else
        a := place_64(have)
        b := place_64(want)
        yes = (if a > b then a - b else b - a end if) <= bound
    end if
end within_64

within_32: (got: f32, want: u32, bound: u32) -> (yes: bool) =
    expected := from_32(want)
    have := bits_32(got)
    if expected <> expected or got <> got then
        yes = expected <> expected and got <> got
    elsif want & 0x7fffffff == 0x7f800000 or have & 0x7fffffff == 0x7f800000 then
        yes = have == want
    elsif (expected == 0.0 or got == 0.0) and have >> 31 <> want >> 31 then
        yes = false
    else
        a := place_32(have)
        b := place_32(want)
        yes = (if a > b then a - b else b - a end if) <= bound
    end if
end within_32
'''


def runner(table, index):
    """The routine that runs table INDEX, counting the results past its
    bound."""
    fn, width = table['fn'], table['width']
    arity = ARITY[fn]
    stride = arity + 1
    name = 'cases_%d' % index
    kind = 'f%d' % width
    reads = '\n'.join('        %s := from_%d(%s[at + %d])' % (p, width, name, k)
                      for k, p in enumerate(PARAMETERS[arity]))
    call = 'math.%s(%s)' % (fn, ', '.join(PARAMETERS[arity]))
    return '''\
run_{index}: () -> (failures: u32) =
    --  {fn} at {kind}, within {bound} of the correctly rounded result
    failures = 0
    mut at: usize = 0
    while at < lenof {name} do
{reads}
        if not within_{width}({call}, {name}[at + {arity}], {bound}) then
            failures = failures + 1
        end if
        at = at + {stride}
    end while
end run_{index}
'''.format(index=index, fn=fn, kind=kind, bound=table['bound'], name=name,
           reads=reads, width=width, call=call, arity=arity, stride=stride)


def fixture_program(name, fixture, oracle):
    """The program of fixture NAME."""
    tables = fixture['tables']
    if len(tables) > 40:
        raise Failure('%s has more than 40 tables, which its status cannot name' % name)
    parts = ['''\
--  Generated by scripts/math_oracle.py from {source}: edit that and run
--  `python3 scripts/math_oracle.py fixtures {name}`, never this file.
--  Each table holds inputs and MPFR's correctly rounded result for them;
--  the program exits 42 when every result core/math gives is within the
--  table's bound of it, counted in floats, and otherwise with the number
--  of the first table that was not, from 1.
import core/math
'''.format(source=fixture['source'].relative_to(ROOT).as_posix(), name=name),
             CHECKER]
    for index, table in enumerate(tables, start=1):
        seed = table.get('seed', index)
        words = [word for case in table_cases(oracle, table, seed) for word in case]
        width = table['width']
        parts.append('--  %s at f%d: the specials, %d random inputs and the %d hardest'
                     ' to round of %d\n' % (table['fn'], width, table.get('random', 0),
                                            table.get('hard', 0), table.get('pool', 20000)))
        parts.append(landin_array('cases_%d' % index, 'u%d' % width, words, width))
        parts.append(runner(table, index))
    calls = '\n'.join('''\
    if run_{i}() <> 0 and code == 42 then
        code = {status}
    end if'''.format(i=i, status=i if i < 42 else i + 1)
                      for i in range(1, len(tables) + 1))
    parts.append('''\
public main: () -> (code: i32) =
    code = 42
{calls}
end main
'''.format(calls=calls))
    return '\n'.join(parts)


def write_fixture(name, fixture, oracle, refine):
    directory = FIXTURES / name
    directory.mkdir(parents=True, exist_ok=True)
    program = directory / 'main.ldn'
    program.write_text(fixture_program(name, fixture, oracle), encoding='utf-8')
    formatted = subprocess.run([str(refine), 'fmt', str(program)], capture_output=True,
                               text=True, check=False)
    if formatted.returncode != 0:
        raise Failure('refine fmt refused %s:\n%s' % (program, formatted.stderr))
    meta = directory / 'fixture.meta'
    meta.write_text('''\
class: runtime
profiles: standard
summary: {summary}
program: main.ldn
root: ../../../../..
status: 42
targets: {targets}
constructs: {constructs}
'''.format(summary=fixture['summary'], targets=fixture.get('targets', TARGETS),
           constructs=fixture.get('constructs', '0170, 0290')), encoding='utf-8')
    return directory


def evaluate_program():
    """compiler/tests/math/evaluate.ldn: every function, at either width,
    over inputs read from standard input or over a range of f32 bits."""
    def arm(fn, width):
        arity = ARITY[fn]
        kind = 'f%d' % width
        reads = ', '.join('from_%d(take_%d(record, %d))' % (width, width, k)
                          for k in range(arity))
        return '''\
    elsif same(name, "{fn}") then
        result = bits_{width}(math.{fn}({reads}))'''.format(fn=fn, width=width, reads=reads, kind=kind)
    arms = {}
    for width in (64, 32):
        body = '\n'.join(arm(fn, width) for fn in ARITY)
        arms[width] = body.replace('    elsif', '    if', 1)
    return '''\
--  Generated by scripts/math_oracle.py: run `python3 scripts/math_oracle.py
--  fixtures` to write it again.  The program `measure` and `exhaustive`
--  run: `evaluate FUNCTION WIDTH` reads records of the function's inputs,
--  little-endian at WIDTH bits, from standard input and writes each
--  record back with core/math's result after it;  `evaluate FUNCTION 32
--  FIRST COUNT` writes the records of COUNT f32 inputs, every bit pattern
--  from FIRST up, without reading any.
import core/io
import core/math
import core/text
import hosted/blocking

arity: (name: []u8) -> (count: usize) =
    count = 1
    if same(name, "hypot") or same(name, "remainder")
      or same(name, "remainder_nearest") or same(name, "pow")
      or same(name, "atan2") then
        count = 2
    elsif same(name, "fma") then
        count = 3
    end if
end arity

same: (left: []u8, right: []u8) -> (yes: bool) =
    yes = lenof left == lenof right
    if yes then
        for at in 0..<lenof left do
            if left[at] <> right[at] then
                yes = false
            end if
        end for
    end if
end same

bits_64: (x: f64) -> (bits: u64) =
    view: ptr u64 = ptr(usize(addr x))
    bits = view.val
end bits_64

from_64: (bits: u64) -> (x: f64) =
    view: ptr f64 = ptr(usize(addr bits))
    x = view.val
end from_64

bits_32: (x: f32) -> (bits: u64) =
    view: ptr u32 = ptr(usize(addr x))
    bits = u64(view.val)
end bits_32

from_32: (bits: u64) -> (x: f32) =
    narrow: u32 = u32(bits & 0xffffffff)
    view: ptr f32 = ptr(usize(addr narrow))
    x = view.val
end from_32

take_64: (record: []u8, index: usize) -> (bits: u64) =
    bits = 0
    for k in 0..<usize(8) do
        bits = bits | (u64(record[index * 8 + k]) << u64(8 * k))
    end for
end take_64

take_32: (record: []u8, index: usize) -> (bits: u64) =
    bits = 0
    for k in 0..<usize(4) do
        bits = bits | (u64(record[index * 4 + k]) << u64(8 * k))
    end for
end take_32

put: (into: []mut u8, at: usize, bits: u64, bytes: usize) -> none =
    for k in 0..<bytes do
        into[at + k] = u8((bits >> u64(8 * k)) & 0xff)
    end for
end put

result_64: (name: []u8, record: []u8) -> (result: u64) =
    result = 0
{arms64}
    end if
end result_64

result_32: (name: []u8, record: []u8) -> (result: u64) =
    result = 0
{arms32}
    end if
end result_32

argument_number: (host: blocking.host, index: usize) -> (value: u64) =
    value = 0
    given := io.argument(host, index) else begin return end
    value = text.parse_u64(text.os_string_bytes(given)) else 0
end argument_number

public main: () -> (code: i32) =
    host := blocking.new()
    code = 2
    given := io.argument(host, 0) else begin return end
    name := text.os_string_bytes(given)
    width := argument_number(host, 1)
    bytes: usize = if width == 64 then 8 else 4 end if
    inputs := arity(name)
    record_bytes := (inputs + 1) * bytes
    mut buffer: [32768]u8 = zeroed
    mut output: [65536]u8 = zeroed
    per_block := lenof output / record_bytes
    if io.arguments_length(host) == 4 then
        first := argument_number(host, 2)
        count := argument_number(host, 3)
        mut done: u64 = 0
        while done < count do
            mut filled: usize = 0
            while filled < per_block and done < count do
                at := filled * record_bytes
                put(output, at, first + done, 4)
                result := result_32(name, output[at..<at + record_bytes])
                put(output, at + 4, result, 4)
                filled = filled + 1
                done = done + 1
            end while
            io.write(host, io.out(host), output[0..<filled * record_bytes]) else begin return end
        end while
        code = 0
        return
    end if
    input_bytes := inputs * bytes
    mut held: usize = 0
    loop do
        got := io.read(host, io.input(host), buffer[held..<lenof buffer]) else begin return end
        held = held + got
        whole := held / input_bytes
        for r in 0..<whole do
            at := r * input_bytes
            to := r * record_bytes
            for k in 0..<input_bytes do
                output[to + k] = buffer[at + k]
            end for
            record := buffer[at..<at + input_bytes]
            result := if width == 64 then result_64(name, record)
                      else result_32(name, record) end if
            put(output, to + input_bytes, result, bytes)
        end for
        io.write(host, io.out(host), output[0..<whole * record_bytes]) else begin return end
        rest := held - whole * input_bytes
        for k in 0..<rest do
            buffer[k] = buffer[whole * input_bytes + k]
        end for
        held = rest
        break when got == 0
    end loop
    code = 0
end main
'''.format(arms64=arms[64], arms32=arms[32])


def compile_evaluate(refine, directory):
    binary = Path(directory) / 'evaluate'
    made = subprocess.run([str(refine), 'compile', '--optimize', 'speed', str(EVALUATE),
                           '-o', str(binary)], capture_output=True, text=True, check=False)
    if made.returncode != 0:
        raise Failure('refine refused evaluate.ldn:\n' + made.stderr)
    return binary


def table_for(fn, width):
    for fixture in descriptions().values():
        for table in fixture['tables']:
            if table['fn'] == fn and table['width'] == width:
                return table
    raise Failure('no fixture describes %s at f%d' % (fn, width))


def measure(args, oracle, refine):
    table = table_for(args.function, args.width)
    with tempfile.TemporaryDirectory() as scratch:
        evaluate = compile_evaluate(refine, scratch)
        command = [str(oracle), 'inputs', '--fn', args.function, '--width', str(args.width),
                   '--seed', str(args.seed), '--count', str(args.count)]
        for argument, flag in ((0, '--domain'), (1, '--domain2'), (2, '--domain3')):
            for domain in domains_of(table, argument):
                command += [flag, domain]
        inputs = subprocess.Popen(command, stdout=subprocess.PIPE)
        evaluated = subprocess.Popen([str(evaluate), args.function, str(args.width)],
                                     stdin=inputs.stdout, stdout=subprocess.PIPE)
        inputs.stdout.close()
        checked = subprocess.run([str(oracle), 'check', '--fn', args.function,
                                  '--width', str(args.width), '--bound', str(table['bound']),
                                  '--show', '5'],
                                 stdin=evaluated.stdout, capture_output=True, text=True,
                                 check=False)
        evaluated.stdout.close()
        if inputs.wait() != 0 or evaluated.wait() != 0:
            raise Failure('generating or evaluating the inputs failed')
        sys.stderr.write(checked.stderr)
        print(checked.stdout.strip())
        return 0 if checked.returncode == 0 else 1


def exhaustive_part(oracle, evaluate, function, bound, first, count):
    evaluated = subprocess.Popen([str(evaluate), function, '32', str(first), str(count)],
                                 stdout=subprocess.PIPE)
    checked = subprocess.run([str(oracle), 'check', '--fn', function, '--width', '32',
                              '--bound', str(bound), '--show', '3'],
                             stdin=evaluated.stdout, capture_output=True, text=True,
                             check=False)
    evaluated.stdout.close()
    if evaluated.wait() != 0:
        raise Failure('evaluate failed from %d' % first)
    return json.loads(checked.stdout), checked.stderr


def exhaustive(args, oracle, refine):
    if ARITY.get(args.function) != 1:
        raise Failure('%s is not a one-argument function' % args.function)
    table = table_for(args.function, 32)
    total = 1 << 32
    parts = args.jobs * 4
    size = total // parts
    with tempfile.TemporaryDirectory() as scratch:
        evaluate = compile_evaluate(refine, scratch)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(exhaustive_part, oracle, evaluate, args.function,
                                   table['bound'], k * size, size) for k in range(parts)]
            results = [future.result() for future in futures]
    summary = {'function': args.function, 'width': 32, 'records': 0,
               'not_correctly_rounded': 0, 'past_bound': 0, 'max_ulp': 0.0}
    for result, shown in results:
        sys.stderr.write(shown)
        for key in ('records', 'not_correctly_rounded', 'past_bound'):
            summary[key] += result[key]
        if result['max_ulp'] > summary['max_ulp']:
            summary['max_ulp'] = result['max_ulp']
            summary['at'] = result['at']
            summary['gives'] = result['gives']
    print(json.dumps(summary))
    return 0 if summary['past_bound'] == 0 and summary['records'] == total else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    lane_refine.argument(parser, required=False, environment=True)
    commands = parser.add_subparsers(dest='command', required=True)
    fixtures = commands.add_parser('fixtures', help='write the math-* fixtures')
    fixtures.add_argument('names', nargs='*')
    measured = commands.add_parser('measure', help='measure a random set')
    measured.add_argument('function')
    measured.add_argument('width', type=int, choices=(32, 64))
    measured.add_argument('--count', type=int, default=1000000)
    measured.add_argument('--seed', type=int, default=2551)
    every = commands.add_parser('exhaustive', help='measure every f32 input')
    every.add_argument('function')
    every.add_argument('--jobs', type=int, default=os.cpu_count())
    args = parser.parse_args()
    try:
        oracle = build_oracle()
        refine = args.refine or default_refine()
        if args.command == 'fixtures':
            known = descriptions()
            for name in args.names:
                if name not in known:
                    raise Failure('no description names %s' % name)
            for name in args.names or known:
                print(write_fixture(name, known[name], oracle, refine).relative_to(ROOT))
            EVALUATE.write_text(evaluate_program(), encoding='utf-8')
            subprocess.run([str(refine), 'fmt', str(EVALUATE)], check=True)
            return 0
        if args.command == 'measure':
            return measure(args, oracle, refine)
        return exhaustive(args, oracle, refine)
    except Failure as failure:
        print('math_oracle: %s' % failure, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
