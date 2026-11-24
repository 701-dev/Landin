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

`--link=microsoft` selects Microsoft's link (D2327) in place of
llvm-mingw's: emission records the link command refine gives a driver
named for Clang's `x86_64-pc-windows-msvc` target, with the assembly,
and execution runs that command with `--driver`, a Clang that links with
`link.exe` on Windows, before it runs the program.

Without either, the lane emits and then executes, natively on Windows or,
on Linux, through `--runner=wine`.  compiler/tests/windows/README.md says
what each verdict means.
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
#  peer is the ABI lane's, and a C library is none Windows links.
UNSUPPORTED = ('c-sources', 'c-shared', 'c-archives', 'library-directories',
               'c-inputs', 'link')


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


#  D2327: the driver refine is given under Microsoft's link, which links
#  nothing.  It keeps the assembly and the command beside the bundle's
#  executables, the operands spelled as placeholders, so the Windows job
#  can run the command refine chose with Clang and Microsoft's linker; the
#  empty file it leaves at the output is refine's to move into place.
RECORDER = r'''#!%s
import json, os, shutil, sys
prefix = os.environ['LANDIN_DEFERRED_LINK']
command, output = [], False
for argument in sys.argv[1:]:
    if output:
        open(argument, 'wb').close()
        command.append('{output}')
        output = False
    elif argument == '-o':
        command.append(argument)
        output = True
    elif argument.endswith('.s') and not argument.startswith('-'):
        shutil.copyfile(argument, prefix + '.s')
        command.append('{assembly}')
    elif not argument.startswith('-'):
        sys.exit('the deferred link cannot carry the operand ' + argument)
    else:
        command.append(argument)
with open(prefix + '.link.json', 'w') as file:
    json.dump(command, file)
'''
MICROSOFT_DRIVER = 'x86_64-pc-windows-msvc-clang'


def recorder(output):
    """The recording driver under OUTPUT, whose file name selects
    Microsoft's link."""
    path = output / 'driver' / MICROSOFT_DRIVER
    path.parent.mkdir(parents=True)
    path.write_text(RECORDER % sys.executable)
    path.chmod(0o755)
    return path


def build(args, bundle, item):
    base, meta, optimize, specialize, level = item
    label = '-'.join((base.name, optimize, specialize, level or 'default'))
    executable = bundle / (label + '.exe')
    argv = [str(args.refine), 'compile', '--target=' + TARGET,
            '--optimize=' + optimize, '--specialize=' + specialize,
            *(['--level=' + level] if level else []),
            '--toolchain=' + args.toolchain,
            *(['--linker=' + args.linker] if args.linker else []),
            *meta.source_arguments(base), '--emit=exe', '-o', str(executable)]
    environment = dict(os.environ, LANDIN_DEFERRED_LINK=str(bundle / label))
    done = subprocess.run(argv, cwd=ROOT / 'compiler/ada', capture_output=True,
                          env=environment)
    (bundle / (label + '.build.log')).write_bytes(
        ' '.join(argv).encode() + b'\n' + done.stdout + done.stderr)
    require(done.returncode == 0, '%s: refine exited %d: %s' % (
        label, done.returncode, (done.stdout + done.stderr).decode(errors='replace')[:400]))
    #  The runtime job checks nothing out, so the bundle carries the files
    #  a fixture is run with, beside its executables, at paths relative to
    #  the bundle.
    given = []
    for one in meta.run_files:
        copy = Path('inputs', base.name, one)
        (bundle / copy).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base / one, bundle / copy)
        given.append(copy.as_posix())
    standard_input = ''
    if meta.get('stdin'):
        copy = Path('inputs', base.name, meta['stdin'])
        (bundle / copy).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base / meta['stdin'], bundle / copy)
        standard_input = copy.as_posix()
    expected = meta.run_expected(base)
    if expected is None and 'stdout' in meta:
        expected = meta['stdout'].encode()
    if expected is not None:
        (bundle / (label + '.expected')).write_bytes(expected)
    deferred = args.link == 'microsoft'
    if deferred:
        link = json.loads((bundle / (label + '.link.json')).read_text())
        executable.unlink()
    return {'label': label, 'case': 'runtime/' + base.name,
            'optimize': optimize, 'specialize': specialize, 'level': level,
            **({'link': link, 'assembly_sha256': sha(bundle / (label + '.s'))}
               if deferred else {'executable_sha256': sha(executable)}),
            'run_args': meta.run_args, 'run_files': given,
            'stdin': standard_input,
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
    if args.link == 'microsoft':
        args.toolchain = str(recorder(args.output))

    def one(item):
        try:
            result = build(args, bundle, item)
        except Refused as error:
            return error
        print(TARGET + ': built ' + result['label'], flush=True)
        return result
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        built = list(pool.map(one, work))
    #  A build that failed is kept as a verdict beside the rest, so that
    #  one fixture that does not build hides no other's outcome.
    failed = [str(one).split('\n', 1)[0] for one in built if isinstance(one, BaseException)]
    manifest = {'target': TARGET, 'link': args.link,
                'scope': 'filtered' if args.case else
                         'shard %d of %d' % args.shard if args.shard else 'complete',
                'revision': os.environ.get('GITHUB_SHA'),
                'refine_sha256': sha(args.refine),
                'build_failures': failed,
                'results': [one for one in built if not isinstance(one, BaseException)]}
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
    #  Wine finishes making a new prefix after the command that made it
    #  returns; a program started meanwhile can wait past its limit.
    server = Path(shutil.which(runner[0]) or runner[0]).with_name('wineserver')
    if server.exists():
        subprocess.run([str(server), '-w'], capture_output=True, timeout=300)


def without_wine_report(text):
    """Output less the line Wine writes when a trap ends a program, which
    a Windows process does not."""
    return b''.join(line for line in text.splitlines(keepends=True)
                    if not line.startswith(b'wine: Unhandled '))


def linked(bundle, result, driver, expect_linker):
    """Run the link command refine chose for Microsoft's link, with DRIVER,
    and say which linker it ran; raise what is wrong."""
    label = result['label']
    assembly = bundle / (label + '.s')
    require(sha(assembly) == result['assembly_sha256'], label + ': assembly checksum')
    command = [str(assembly) if one == '{assembly}' else
               str(bundle / (label + '.exe')) if one == '{output}' else one
               for one in result['link']]
    #  `-v` makes Clang print each command it runs, the link's last.
    try:
        done = subprocess.run([*driver, '-v', *command], cwd=bundle, capture_output=True,
                              timeout=300)
    except OSError as error:
        raise Refused('%s: could not start the driver %s: %s' % (label, driver[0], error))
    except subprocess.TimeoutExpired:
        raise Refused(label + ': the link did not finish within 300 seconds')
    log = done.stdout + done.stderr
    (bundle / (label + '.link.log')).write_bytes(log)
    require(done.returncode == 0, '%s: the link exited %d: %s' % (
        label, done.returncode, log.decode(errors='replace')[-600:]))
    ran = [line.strip() for line in log.decode(errors='replace').splitlines()
           if line.startswith(' "')]
    require(ran, label + ': the driver named no command it ran')
    linker = ran[-1][1:].split('"', 1)[0]
    name = linker.replace('\\', '/').rsplit('/', 1)[-1].lower()
    require(not expect_linker or name == expect_linker.lower(),
            '%s: the link ran %s, not %s' % (label, linker, expect_linker))
    result['linker'] = linker
    result['executable_sha256'] = sha(bundle / (label + '.exe'))


def outcome(bundle, result, runner):
    """Run one executable and hold it to its fixture; raise what is wrong."""
    label = result['label']
    executable = bundle / (label + '.exe')
    require(sha(executable) == result['executable_sha256'], label + ': executable checksum')
    merged = result['stream'] == 'merged'
    try:
        given = (open(bundle / result['stdin'], 'rb') if result.get('stdin')
                 else subprocess.DEVNULL)
        #  Each outcome runs in a directory of its own, since the profiles
        #  of one fixture run at once and a fixture may make files where it
        #  runs.
        place = bundle / 'work' / label
        place.mkdir(parents=True, exist_ok=True)
        #  The directory holds the fixture's files too, so a program that
        #  lists where it runs finds something, as it does on Linux.
        for one in result.get('run_files', []):
            shutil.copyfile(bundle / one, place / Path(one).name)
        files = [str(bundle / one) for one in result.get('run_files', [])]
        try:
            done = subprocess.run([*runner, str(executable), *result['run_args'], *files],
                                  stdin=given, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT if merged else subprocess.PIPE,
                                  timeout=60, cwd=place)
        finally:
            if given is not subprocess.DEVNULL:
                given.close()
    except subprocess.TimeoutExpired:
        raise Refused(label + ': did not finish within 60 seconds')
    except OSError as error:
        #  Windows refusing the image, as it refuses one past 2 GiB.
        raise Refused('%s: the system did not start it: %s' % (label, error))
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


def execute(bundle, manifest, runner, jobs, driver=(), expect_linker=''):
    windows_error_mode()
    results = manifest['results']
    require(results or manifest.get('build_failures'), 'empty prepared fixture selection')

    def one(result):
        try:
            if 'link' in result:
                linked(bundle, result, driver, expect_linker)
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
    unbuilt = manifest.get('build_failures', [])
    require(not failures and not unbuilt, '%s%s' % (
        '%d builds failed:\n  %s\n' % (len(unbuilt), '\n  '.join(unbuilt)) if unbuilt else '',
        '%d of %d outcomes failed:\n  %s' % (len(failures), len(results),
                                              '\n  '.join(sorted(failures)))
        if failures else ''))


def driver_version(driver):
    """The first line the driver says of its version, which the summary
    keeps beside the linker each link ran."""
    try:
        done = subprocess.run([*driver, '--version'], capture_output=True, timeout=60)
    except OSError as error:
        raise Refused('could not start the driver %s: %s' % (driver[0], error))
    return (done.stdout.decode(errors='replace').splitlines() or [''])[0]


def shard(text):
    index, slash, count = text.partition('/')
    if not (slash and index.isdigit() and count.isdigit()
            and 1 <= int(index) <= int(count) <= 64):
        raise argparse.ArgumentTypeError('expected I/N with 1 <= I <= N <= 64')
    return int(index), int(count)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sys.path.insert(0, str(ROOT / 'scripts'))
    import lane_refine  # the --refine every lane takes
    lane_refine.argument(parser, required=False, help='the Linux refine that emits')
    parser.add_argument('--output', type=Path, required=True,
                        help='a new directory for the bundle, transcripts and summary.json')
    parser.add_argument('--toolchain', default='x86_64-w64-mingw32-clang',
                        help='the llvm-mingw driver refine links with')
    parser.add_argument('--link', choices=('mingw', 'microsoft'), default='mingw',
                        help="whose link refine chooses: llvm-mingw's, the default, or"
                        " Microsoft's (D2327), which execution runs with --driver")
    parser.add_argument('--linker', default='',
                        help="refine's --linker under Microsoft's link: lld for lld-link")
    parser.add_argument('--driver', default='clang',
                        help="the Clang that runs Microsoft's link at execution")
    parser.add_argument('--expect-linker', default='',
                        help="the linker Microsoft's link must run, such as link.exe")
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
                unbuilt = manifest['build_failures']
                require(not unbuilt, '%d builds failed:\n  %s' % (
                    len(unbuilt), '\n  '.join(unbuilt)))
                summary.update(status='emitted', scope=manifest['scope'],
                               results=manifest['results'])
                print('%s: %d %s outcomes emitted; execution pending'
                      % (TARGET, len(manifest['results']), manifest['scope']))
                return
        summary['scope'] = manifest['scope']
        summary['results'] = manifest['results']
        wine_prefix(args.runner.split(), args.output)
        if manifest.get('link') == 'microsoft':
            summary['link'] = 'microsoft'
            summary['driver'] = driver_version(args.driver.split())
        execute(bundle, manifest, args.runner.split(), args.jobs,
                args.driver.split(), args.expect_linker)
        if manifest.get('link') == 'microsoft':
            summary['linkers'] = sorted({one['linker'] for one in manifest['results']
                                         if 'linker' in one})
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
