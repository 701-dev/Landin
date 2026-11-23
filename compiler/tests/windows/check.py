#!/usr/bin/env python3
"""Emit the Windows x86-64 corpus on Linux, then execute it on Windows.

Two stages, which a local run joins and the gate splits between a Linux
job and a Windows job:

  --prepare-only   select the runtime fixtures whose `targets:` names
                   windows-x86-64, compile each at every profile with Linux
                   `refine` and the llvm-mingw driver, and write the
                   executables and `prepared.json` into OUTPUT;
  --prepared=DIR   execute a prepared bundle and hold each outcome to its
                   fixture, with no compiler and no checkout beyond this
                   file and compiler/tests/fixture_meta.py.

Without either, the lane emits and then executes, natively on Windows or,
on Linux, through `--runner=wine`.  README.md beside this file says what
each verdict means.
"""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
TARGET = 'windows-x86-64'
PROFILES = [('none', 'off'), ('size', 'off'), ('size', 'auto'), ('speed', 'auto')]
SPECIALIZED = [('none', 'all'), ('speed', 'all')]
#  STATUS_ILLEGAL_INSTRUCTION: the exit code of a process ended by the
#  trap instruction a failed check executes, `ud2`, with no handler.
TRAP_STATUS = 0xC000001D
#  What the selection must not ask of the lane, each a later item's: a C
#  peer is the ABI lane's, a C library is none Windows links, and files
#  and standard input wait for Windows' Io providers.
UNSUPPORTED = ('c-sources', 'c-shared', 'c-archives', 'library-directories',
               'run_files', 'stdin', 'c-inputs', 'link')


class Refused(ValueError):
    """A verdict or a refusal, which says itself."""


def require(condition, message):
    if not condition:
        raise Refused(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture_meta():
    sys.path.insert(0, str(ROOT / 'compiler/tests'))
    import fixture_meta as module
    return module


def select(cases):
    meta_module = fixture_meta()
    found = []
    for path in sorted((ROOT / 'compiler/tests/fixtures/runtime').glob('*/fixture.meta')):
        meta = meta_module.read(path.parent)
        if meta.applies_to(TARGET):
            found.append((path.parent, meta))
    require(found, TARGET + ': empty fixture selection')
    for base, meta in found:
        asked = [key for key in UNSUPPORTED if meta.get(key)]
        require(not asked, '%s names %s, which the Windows lane does not run yet'
                % (base.name, ', '.join(asked)))
    if cases:
        known = {base.name for base, _ in found}
        unknown = sorted(set(cases) - known)
        require(not unknown, 'unknown exact case ' + ', '.join(unknown)
                + ': --case takes the bare directory name of a fixture whose'
                + ' targets name ' + TARGET)
        found = [(base, meta) for base, meta in found if base.name in cases]
    return found


def work_items(found, shard):
    if shard:
        index, count = shard
        found = found[index - 1::count]
        require(found, 'empty shard')
    work = []
    for base, meta in found:
        levels = [None]
        if 'x86-64-v3' in meta.levels_for(TARGET):
            levels += ['x86-64-v1', 'x86-64-v3']
        for level in levels:
            for optimize, specialize in PROFILES + (
                    SPECIALIZED if meta.get('profiles') == 'specialization' else []):
                work.append((base, meta, optimize, specialize, level))
    return work


def build(args, bundle, item):
    base, meta, optimize, specialize, level = item
    label = '-'.join((base.name, optimize, specialize, level or 'default'))
    executable = bundle / (label + '.exe')
    argv = [str(args.refine), 'compile', '--target=' + TARGET,
            '--optimize=' + optimize, '--specialize=' + specialize,
            *(['--level=' + level] if level else []),
            '--toolchain=' + args.toolchain,
            *meta.source_arguments(base), '--emit=exe', '-o', str(executable)]
    done = subprocess.run(argv, cwd=ROOT / 'compiler/ada', capture_output=True)
    (bundle / (label + '.build.log')).write_bytes(
        ' '.join(argv).encode() + b'\n' + done.stdout + done.stderr)
    require(done.returncode == 0, '%s: refine exited %d: %s' % (
        label, done.returncode, (done.stdout + done.stderr).decode(errors='replace')[:400]))
    expected = meta.run_expected(base)
    if expected is None and 'stdout' in meta:
        expected = meta['stdout'].encode()
    if expected is not None:
        (bundle / (label + '.expected')).write_bytes(expected)
    return {'label': label, 'case': 'runtime/' + base.name,
            'optimize': optimize, 'specialize': specialize, 'level': level,
            'executable_sha256': sha(executable),
            'run_args': meta.run_args,
            'status': meta.status_at(level), 'traps': meta.traps,
            'stream': meta.get('stream', 'merged'),
            'expected': expected is not None,
            'trap_report': meta.get('trap_report', '')}


def prepare(args):
    sys.path.insert(0, str(ROOT / 'scripts'))
    import build_lock
    build_lock.reading(args.refine)
    found = select(args.case)
    work = work_items(found, args.shard)
    bundle = args.output / 'bundle'
    bundle.mkdir(parents=True)

    def one(item):
        try:
            result = build(args, bundle, item)
        except Refused as error:
            return error
        print(TARGET + ': built ' + result['label'], flush=True)
        return result
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        built = list(pool.map(one, work))
    failed = [str(one).split('\n', 1)[0] for one in built if isinstance(one, BaseException)]
    require(not failed, '%d of %d builds failed:\n  %s' % (
        len(failed), len(built), '\n  '.join(failed)))
    manifest = {'target': TARGET,
                'scope': 'filtered' if args.case else
                         'shard %d of %d' % args.shard if args.shard else 'complete',
                'revision': os.environ.get('GITHUB_SHA'),
                'refine_sha256': sha(args.refine),
                'results': built}
    (args.output / 'prepared.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def windows_error_mode():
    """Keep Windows Error Reporting's dialog and its wait away from a
    program a trap ends: the mode is inherited by every child."""
    if sys.platform == 'win32':
        import ctypes
        #  SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX
        ctypes.windll.kernel32.SetErrorMode(0x8003)


def wine_prefix(runner, output):
    """A Wine runner's own prefix under OUTPUT, made once, whose
    unhandled-exception debugger is off: Wine would otherwise start it
    for every trap, slowly, and under load lose the exit status."""
    if not runner or not Path(runner[0]).name.startswith('wine'):
        return
    os.environ.setdefault('WINEDEBUG', '-all')
    os.environ['WINEPREFIX'] = str(output / 'wine')
    key = r'HKLM\Software\Microsoft\Windows NT\CurrentVersion\AeDebug'
    for name, value in (('Debugger', 'false'), ('Auto', '1')):
        done = subprocess.run([*runner, 'reg', 'add', key, '/v', name, '/d', value, '/f'],
                              capture_output=True)
        require(done.returncode == 0, 'could not configure the Wine prefix: '
                + (done.stdout + done.stderr).decode(errors='replace')[-400:])


def without_wine_report(text):
    """Output less the line Wine writes when a trap ends a program, which
    a Windows process does not."""
    return b''.join(line for line in text.splitlines(keepends=True)
                    if not line.startswith(b'wine: Unhandled '))


def outcome(bundle, result, runner):
    """Run one executable and hold it to its fixture; raise what is wrong."""
    label = result['label']
    executable = bundle / (label + '.exe')
    require(sha(executable) == result['executable_sha256'], label + ': executable checksum')
    merged = result['stream'] == 'merged'
    try:
        done = subprocess.run([*runner, str(executable), *result['run_args']],
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT if merged else subprocess.PIPE,
                              timeout=60, cwd=bundle)
    except subprocess.TimeoutExpired:
        raise Refused(label + ': did not finish within 60 seconds')
    (bundle / (label + '.stdout')).write_bytes(done.stdout)
    if not merged:
        (bundle / (label + '.stderr')).write_bytes(done.stderr)
    if runner:
        done.stdout = without_wine_report(done.stdout)
        done.stderr = without_wine_report(done.stderr or b'')
    status = done.returncode & 0xFFFFFFFF
    (bundle / (label + '.status')).write_text('%d\n' % status)
    #  Wine hands Linux the low byte of the Windows exit code.
    native = not runner
    if result['traps']:
        wanted = TRAP_STATUS if native else TRAP_STATUS & 0xFF
        require(status == wanted, '%s: status %#x, expected the trap\'s %#x'
                % (label, status, wanted))
    else:
        #  A fixture's status is the one a POSIX parent reads, the low byte
        #  of what main returned; Windows keeps all 32 bits.
        require(status & 0xFF == result['status'] and (native or status < 256),
                '%s: status %d, expected %d' % (label, status, result['status']))
    if result['expected']:
        expected = (bundle / (label + '.expected')).read_bytes()
        require(done.stdout == expected, '%s: output %r, expected %r'
                % (label, done.stdout[:400], expected[:400]))
    if result['trap_report']:
        written = done.stdout + (b'' if merged else done.stderr)
        require(result['trap_report'].encode() in written.split(b'\n'),
                '%s: trap report missing: %r' % (label, result['trap_report']))
    if not merged:
        require(not done.stderr, label + ': unexpected standard error output')


def execute(bundle, manifest, runner, jobs):
    windows_error_mode()
    results = manifest['results']
    require(results, 'empty prepared fixture selection')

    def one(result):
        try:
            outcome(bundle, result, runner)
            result['verdict'] = 'passed'
            return None
        except Refused as error:
            result['verdict'] = 'failed'
            result['failure'] = str(error)
            return str(error).split('\n', 1)[0]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        failures = [one for one in pool.map(one, results) if one]
    print('%s: %d of %d outcomes passed' % (TARGET, len(results) - len(failures), len(results)),
          flush=True)
    require(not failures, '%d of %d outcomes failed:\n  %s' % (
        len(failures), len(results), '\n  '.join(sorted(failures))))


def shard(text):
    index, slash, count = text.partition('/')
    if not (slash and index.isdigit() and count.isdigit()
            and 1 <= int(index) <= int(count) <= 64):
        raise argparse.ArgumentTypeError('expected I/N with 1 <= I <= N <= 64')
    return int(index), int(count)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--refine', type=Path, help='the Linux refine that emits')
    parser.add_argument('--output', type=Path, required=True,
                        help='a new directory for the bundle, transcripts and summary.json')
    parser.add_argument('--toolchain', default='x86_64-w64-mingw32-clang',
                        help='the llvm-mingw driver refine links with')
    parser.add_argument('--runner', default='',
                        help='a command each executable runs under, such as wine; none on Windows')
    parser.add_argument('--prepare-only', action='store_true',
                        help='emit the bundle and prepared.json; execute nothing')
    parser.add_argument('--prepared', type=Path,
                        help='execute the bundle a --prepare-only run wrote')
    parser.add_argument('--case', action='append',
                        help="a fixture's bare directory name; repeatable, visibly filtered")
    parser.add_argument('--shard', type=shard, metavar='I/N',
                        help='fixtures I, I+N, ... of the selection; all N together are the lane')
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 4)
    args = parser.parse_args()
    args.output = args.output.resolve()
    summary = {'target': TARGET, 'status': 'failed'}
    try:
        require(not (args.prepare_only and args.prepared), 'prepare and execute are distinct stages')
        require(args.prepared or args.refine, 'emission needs --refine')
        require(not (args.shard and args.case), 'a shard is a share of the complete lane')
        args.output.mkdir(parents=True, exist_ok=False)
        if args.prepared:
            prepared = args.prepared.resolve()
            manifest = json.loads((prepared / 'prepared.json').read_text())
            require(manifest['target'] == TARGET, 'prepared payload belongs to another lane')
            if os.environ.get('GITHUB_SHA'):
                require(manifest['revision'] == os.environ['GITHUB_SHA'],
                        'prepared payload belongs to another revision')
            bundle = args.output / 'bundle'
            shutil.copytree(prepared / 'bundle', bundle)
        else:
            args.refine = args.refine.resolve()
            require(sys.platform.startswith('linux'), 'emission runs on Linux')
            manifest = prepare(args)
            bundle = args.output / 'bundle'
            if args.prepare_only:
                summary.update(status='emitted', scope=manifest['scope'],
                               results=manifest['results'])
                print('%s: %d %s outcomes emitted; execution pending'
                      % (TARGET, len(manifest['results']), manifest['scope']))
                return
        summary['scope'] = manifest['scope']
        summary['results'] = manifest['results']
        wine_prefix(args.runner.split(), args.output)
        execute(bundle, manifest, args.runner.split(), args.jobs)
        summary['status'] = 'passed'
        print('%s: %d %s outcomes passed' % (TARGET, len(manifest['results']), manifest['scope']))
    except Refused as error:
        summary['failure'] = str(error)
        print('%s: %s' % (TARGET, error), file=sys.stderr)
        print('%s: failed; every transcript and status is in %s, the verdicts in %s'
              % (TARGET, args.output, args.output / 'summary.json'), file=sys.stderr)
        sys.exit(1)
    finally:
        if args.output.is_dir():
            (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
