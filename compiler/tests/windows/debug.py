#!/usr/bin/env python3
"""The Windows debugger sessions: LLDB over CodeView and a PDB, directly
and through `refine dap`.

The Windows debugger is LLDB as llvm-mingw ships it for Windows, LLVM's
own and free (D2292): `lldb.exe`, which reads a PDB with LLVM's own
reader, and `lldb-dap.exe`, the adapter `refine dap` relays.  Three
stages, which a local run joins and the gate splits between a Linux job,
a Windows job and WSL on that Windows runner:

  --prepare-only   on Linux, compile compiler/tests/freebsd/debug.ldn and
                   the stack switch's workload (D469) at the four
                   profiles, compiler/tests/debugging/registers.ldn at
                   speed and compiler/tests/dap/main.ldn with
                   --panic-map, each with --debug=full, and write the
                   images, their PDBs and prepared.json into OUTPUT;
  --prepared=DIR   on Windows, run LLDB's batch sessions over each
                   debug.ldn image, each switch image and the copy image
                   and hold their transcripts to
                   compiler/tests/debugging/lldb_batch.py's verdicts, the
                   second switch_frames.py's and the third this file's;
  --dap            with --prepared, on Linux or in WSL, run
                   compiler/tests/dap/session.py's scripted session
                   through `refine dap` (--refine) over the Windows
                   adapter (--lldb-dap) and the DAP program.

Without --prepare-only or --prepared the lane emits and then runs both
sessions on Linux through Wine: --lldb and --lldb-dap then name a command
that runs llvm-mingw's Windows executables under Wine.  Wine is
development feedback; the gate's Windows runner is the verdict.
compiler/tests/windows/README.md says how to run it.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'compiler/tests/debugging'))
import lldb_batch  # noqa: E402
import switch_frames  # noqa: E402

#  The lane's target, which --target sets: windows-x86-64 or windows-arm64,
#  each with its llvm-mingw driver.
TARGET = 'windows-x86-64'
DRIVERS = {'windows-x86-64': 'x86_64-w64-mingw32-clang',
           'windows-arm64': 'aarch64-w64-mingw32-clang'}
PROFILES = (('none', 'off'), ('size', 'off'), ('size', 'auto'),
            ('speed', 'auto'))
#  D339 copies `inline_leaf` into `inline_outer` at speed.  The copy
#  session stops inside the copy, where LLDB must show `inline_leaf`'s frame
#  with its own parameter and local above `inline_outer`'s, which shows its
#  own: the inline site CodeView describes the copy by.
COPY_SOURCE = ROOT / 'compiler/tests/debugging/registers.ldn'
COPY_NEEDLE = 'total = doubled + 1'
COPY_FRAMES = ('inline_leaf', 'inline_outer', 'main')
COPY_VALUES = (('base', 2), ('doubled', 4))
COPY_CALLER_VALUES = (('first', 2),)
COPY_STATUS = 42
#  Where the DAP program is compiled from: a path a WSL distribution
#  recreates, since the debugger matches a breakpoint's source against the
#  path the program recorded.
DAP_SOURCE = Path('/tmp/landin-windows-dap/main.ldn')
#  The files the Windows and WSL stages run from, at their own paths: the
#  Windows runner checks nothing out (compiler/tests/windows/README.md
#  says why).
LANE = ('compiler/tests/windows/debug.py',
        'compiler/tests/debugging/lldb_batch.py',
        'compiler/tests/debugging/switch_frames.py',
        'compiler/tests/debugging/workload-frames.json',
        'compiler/tests/freebsd/debug.ldn',
        'compiler/tests/dap/session.py',
        'compiler/tests/dap/main.ldn',
        'scripts/lane_refine.py', 'scripts/refine_revision.py',
        'scripts/build_identity.py', 'scripts/build_lock.py',
        'environments/pins.sh')


class Refused(ValueError):
    """A verdict or a refusal, which says itself."""


def require(condition, message):
    if not condition:
        raise Refused(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compile_one(args, source, image, *flags):
    argv = [str(args.refine), 'compile', '--target=' + TARGET,
            '--toolchain=' + args.toolchain, '--debug=full', *flags,
            str(source), '-o', str(image)]
    done = subprocess.run(argv, capture_output=True)
    image.with_suffix('.build.log').write_bytes(
        ' '.join(argv).encode() + b'\n' + done.stdout + done.stderr)
    require(done.returncode == 0, '%s: refine exited %d: %s' % (
        image.name, done.returncode,
        (done.stdout + done.stderr).decode(errors='replace')[:600]))
    pdb = image.with_suffix('.pdb')
    require(pdb.is_file(), image.name + ': no PDB beside the image')
    return {'image': image.name, 'image_sha256': sha(image),
            'pdb': pdb.name, 'pdb_sha256': sha(pdb)}


def prepare(args):
    sys.path.insert(0, str(ROOT / 'scripts'))
    import build_lock
    build_lock.reading(args.refine)
    bundle = args.output / 'bundle'
    bundle.mkdir(parents=True)
    lines = lldb_batch.source_lines()
    sessions = []
    for optimize, specialize in PROFILES:
        label = 'debug-%s-%s' % (optimize, specialize)
        built = compile_one(args, lldb_batch.SOURCE, bundle / (label + '.exe'),
                            '--optimize=' + optimize,
                            '--specialize=' + specialize)
        (bundle / (label + '.lldb')).write_text(
            '\n'.join(lldb_batch.source_commands(lines)) + '\n')
        sessions.append(dict(built, label=label))
        print(TARGET + ': built ' + label, flush=True)
    #  The stack switch's session (D469).  LLDB steps a switch by a count,
    #  as FreeBSD's does, the instructions of the straight-line switch
    #  routine, counted in the assembly the image was linked from, which
    #  --debug=full keeps beside it: the image's symbols are in its PDB.
    switches = []
    for optimize, specialize in PROFILES:
        label = 'switch-%s-%s' % (optimize, specialize)
        image = bundle / (label + '.exe')
        built = compile_one(args, switch_frames.FIXTURE, image,
                            '--optimize=' + optimize,
                            '--specialize=' + specialize,
                            '--root=' + str(ROOT))
        assembly = image.with_name(image.name + '.s')
        require(assembly.is_file(), label + ': no assembly beside the image')
        count = switch_frames.assembly_instruction_count(assembly.read_text())
        (bundle / (label + '.lldb')).write_text(
            '\n'.join(lldb_batch.switch_commands(count, pdb=True))
            + '\n')
        switches.append(dict(built, label=label, switch_instructions=count))
        print(TARGET + ': built ' + label, flush=True)
    copies = []
    label = 'copy-speed-auto'
    built = compile_one(args, COPY_SOURCE, bundle / (label + '.exe'),
                        '--optimize=speed', '--specialize=auto')
    (bundle / (label + '.lldb')).write_text(
        '\n'.join(copy_commands(copy_line())) + '\n')
    copies.append(dict(built, label=label))
    print(TARGET + ': built ' + label, flush=True)
    DAP_SOURCE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'compiler/tests/dap/main.ldn', DAP_SOURCE)
    dap = compile_one(args, DAP_SOURCE, bundle / 'program.exe',
                      '--panic-map')
    require((bundle / 'program.exe.sources.json').is_file(),
            'program.exe: no source table beside it')
    print(TARGET + ': built the DAP program', flush=True)
    for file in LANE:
        (args.output / 'lane' / file).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / file, args.output / 'lane' / file)
    manifest = {'target': TARGET, 'revision': os.environ.get('GITHUB_SHA'),
                'refine_sha256': sha(args.refine), 'lines': lines,
                'sessions': sessions, 'switches': switches,
                'copies': copies, 'copy_line': copy_line(), 'dap': dap,
                'dap_source': str(DAP_SOURCE)}
    (args.output / 'prepared.json').write_text(json.dumps(manifest, indent=2)
                                               + '\n')
    return manifest


def copy_line():
    """The line of COPY_NEEDLE in COPY_SOURCE."""
    return next(i for i, line in
                enumerate(COPY_SOURCE.read_text().splitlines(), 1)
                if COPY_NEEDLE in line)


def copy_commands(line):
    """The copy session: a stop inside the copy, its frame and values,
    its caller's frame and values, the frame below, and the exit.

    The verdict reads each frame where `frame select` shows it: under
    Wine llvm-mingw's LLDB now and then printed no frame below an inlined
    one in `thread backtrace`, over Clang's PDB as well as this one, while
    each frame below was there to select; the backtrace stays in the
    transcript."""
    return ['settings set target.disable-aslr false',
            'breakpoint set --file %s --line %d' % (COPY_SOURCE.name, line),
            'run', 'frame info',
            'frame variable ' + ' '.join(name for name, _ in COPY_VALUES),
            'thread backtrace', 'frame select 1',
            'frame variable '
            + ' '.join(name for name, _ in COPY_CALLER_VALUES),
            'frame select 2', 'breakpoint delete --force', 'continue']


def check_copy(text, line, label):
    """Hold a copy session's transcript to its stop, frames and values."""
    def section(command):
        return text.split('(lldb) ' + command, 1)[-1].split('(lldb) ', 1)[0]
    require(re.search(re.escape(COPY_SOURCE.name) + ':' + str(line)
                      + r'[:\s]', section('frame info')),
            label + ': no stop at the line inside the copy')
    for frame, name in enumerate(COPY_FRAMES):
        shown = section('frame info' if frame == 0
                        else 'frame select %d' % frame)
        require(re.search(r'frame #%d:.*`%s\b' % (frame, name), shown),
                label + ': frame #%d is not %s' % (frame, name))
    shown = section('frame variable '
                    + ' '.join(name for name, _ in COPY_VALUES))
    for name, value in COPY_VALUES:
        require(re.search(r'\b%s = %d\b' % (name, value), shown),
                label + ': the copy\'s %s is not %d' % (name, value))
    shown = section('frame variable '
                    + ' '.join(name for name, _ in COPY_CALLER_VALUES))
    for name, value in COPY_CALLER_VALUES:
        require(re.search(r'\b%s = %d\b' % (name, value), shown),
                label + ': the caller\'s %s is not %d' % (name, value))
    require(re.search(r'exited with status = %d\b' % COPY_STATUS, text),
            label + ': the program did not exit %d' % COPY_STATUS)


def verify(bundle, built):
    require(sha(bundle / built['image']) == built['image_sha256'],
            built['image'] + ': image checksum')
    require(sha(bundle / built['pdb']) == built['pdb_sha256'],
            built['pdb'] + ': PDB checksum')


def direct(bundle, manifest, lldb, output):
    """LLDB's batch sessions over each debug.ldn image, each switch
    image and the copy image; the failures."""
    failures = []
    lines = {key: int(value) for key, value in manifest['lines'].items()}
    summary = {}
    for built in (manifest['sessions'] + manifest['switches']
                  + manifest['copies']):
        label = built['label']
        try:
            verify(bundle, built)
            try:
                done = subprocess.run(
                    [*lldb, '--batch', '-s', label + '.lldb', built['image']],
                    cwd=bundle, stdin=subprocess.DEVNULL,
                    capture_output=True, timeout=300)
            except subprocess.TimeoutExpired as late:
                #  What it printed before then, which says where it stopped.
                (output / (label + '.transcript')).write_bytes(
                    (late.stdout or b'') + (late.stderr or b''))
                raise Refused(label + ': LLDB did not finish within 300'
                              ' seconds')
            text = (done.stdout + done.stderr).decode(errors='replace')
            (output / (label + '.transcript')).write_text(text)
            try:
                if 'switch_instructions' in built:
                    summary[label] = lldb_batch.check_switch(
                        text, label, TARGET)
                elif built in manifest['copies']:
                    check_copy(text, manifest['copy_line'], label)
                else:
                    lldb_batch.check_source(text, lines, label)
            except lldb_batch.Mismatch as error:
                raise Refused(str(error))
            print('%s: LLDB session passed %s' % (TARGET, label), flush=True)
        except Refused as error:
            failures.append(str(error))
            print('%s: %s' % (TARGET, error), file=sys.stderr, flush=True)
    (output / 'switch-frames.json').write_text(json.dumps(summary, indent=2)
                                               + '\n')
    return failures


def through_dap(bundle, manifest, refine, lldb_dap, output):
    """session.py's scripted session through `refine dap`."""
    sys.path.insert(0, str(ROOT / 'compiler/tests/dap'))
    import session
    verify(bundle, manifest['dap'])
    source = Path(manifest['dap_source'])
    if not source.is_file() or source.read_bytes() != (
            ROOT / 'compiler/tests/dap/main.ldn').read_bytes():
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'compiler/tests/dap/main.ldn', source)
    sys.path.insert(0, str(ROOT / 'scripts'))
    import lane_refine
    #  lldb-dap's own log, which WSL hands the Windows program as a Windows
    #  path, kept with the transcripts.
    os.environ['LLDBDAP_LOG'] = str(output / 'lldb-dap.log')
    os.environ['WSLENV'] = ':'.join(
        part for part in (os.environ.get('WSLENV'), 'LLDBDAP_LOG/p') if part)
    try:
        checks = session.run_session(
            lane_refine.command(refine, 'dap'), bundle / 'program.exe',
            source, output, TARGET + '-lldb', debugger_path=lldb_dap)
    except AssertionError as error:
        raise Refused('the refine dap session: ' + str(error))
    print('%s: refine dap session passed, %d checks' % (TARGET, len(checks)),
          flush=True)


def main():
    global TARGET
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sys.path.insert(0, str(ROOT / 'scripts'))
    import lane_refine  # the --refine every lane takes
    lane_refine.argument(parser, required=False,
                         help='the Linux refine that emits, or whose refine'
                         ' dap --dap drives')
    parser.add_argument('--output', type=Path, required=True,
                        help='a new directory for the bundle, transcripts'
                        ' and summary.json')
    parser.add_argument('--target', choices=sorted(DRIVERS), default=TARGET,
                        help='the Windows target the sessions debug')
    parser.add_argument('--toolchain',
                        help="the llvm-mingw driver refine links with; the"
                        " target's by default")
    parser.add_argument('--lldb', default='lldb.exe',
                        help="the command that runs llvm-mingw's lldb.exe")
    parser.add_argument('--lldb-dap',
                        help="the command that runs llvm-mingw's lldb-dap.exe,"
                        ' which refine dap starts; under WSL its Linux path')
    parser.add_argument('--prepare-only', action='store_true',
                        help='emit the bundle and prepared.json; run nothing')
    parser.add_argument('--prepared', type=Path,
                        help='run the sessions over the bundle a'
                        ' --prepare-only run wrote')
    parser.add_argument('--dap', action='store_true',
                        help='with --prepared, the refine dap session alone')
    args = parser.parse_args()
    TARGET = args.target
    args.toolchain = args.toolchain or DRIVERS[TARGET]
    args.output = args.output.resolve()
    summary = {'target': TARGET, 'status': 'failed'}
    try:
        require(not (args.prepare_only and args.prepared),
                'prepare and run are distinct stages')
        require(not args.dap or args.prepared, '--dap runs a prepared bundle')
        require(args.prepared or args.refine, 'emission needs --refine')
        require(not args.dap or (args.refine and args.lldb_dap),
                '--dap needs --refine and --lldb-dap')
        args.output.mkdir(parents=True, exist_ok=False)
        if args.prepared:
            prepared = args.prepared.resolve()
            manifest = json.loads((prepared / 'prepared.json').read_text())
            require(manifest['target'] == TARGET,
                    'prepared payload belongs to another lane')
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
                summary['status'] = 'emitted'
                print('%s: %d LLDB sessions and the refine dap session'
                      ' emitted; running them is pending'
                      % (TARGET, len(manifest['sessions'])
                         + len(manifest['switches'])
                         + len(manifest['copies'])))
                return
        failures = []
        if not args.dap:
            #  A Windows path's backslashes are no shell's escapes.
            lldb = ([args.lldb] if Path(args.lldb).is_file()
                    else shlex.split(args.lldb))
            failures += direct(bundle, manifest, lldb, args.output)
        if args.dap or not args.prepared:
            require(args.lldb_dap, 'the refine dap session needs --lldb-dap')
            try:
                through_dap(bundle, manifest, args.refine, args.lldb_dap,
                            args.output)
            except Refused as error:
                failures.append(str(error))
                print('%s: %s' % (TARGET, error), file=sys.stderr, flush=True)
        require(not failures, '%d sessions failed:\n  %s' % (
            len(failures), '\n  '.join(failures)))
        summary['status'] = 'passed'
        print('%s: every debugger session passed' % TARGET)
    except Refused as error:
        summary['failure'] = str(error)
        print('%s: %s' % (TARGET, error), file=sys.stderr)
        print('%s: failed; every transcript is in %s, the verdict in %s'
              % (TARGET, args.output, args.output / 'summary.json'),
              file=sys.stderr)
        sys.exit(1)
    finally:
        if args.output.is_dir():
            (args.output / 'summary.json').write_text(
                json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
