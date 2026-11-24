#!/usr/bin/env python3
"""The Windows debugger sessions: LLDB over CodeView and a PDB, directly
and through `refine dap`.

The Windows debugger is LLDB as llvm-mingw ships it for Windows, LLVM's
own and free (D2292): `lldb.exe`, which reads a PDB with LLVM's own
reader, and `lldb-dap.exe`, the adapter `refine dap` relays.  Three
stages, which a local run joins and the gate splits between a Linux job,
a Windows job and WSL on that Windows runner:

  --prepare-only   on Linux, compile compiler/tests/freebsd/debug.ldn at
                   the four profiles and compiler/tests/dap/main.ldn
                   with --panic-map, each with --debug=full, and write
                   the images, their PDBs and prepared.json into OUTPUT;
  --prepared=DIR   on Windows, run LLDB's batch session over each
                   debug.ldn image and hold its transcript to
                   compiler/tests/debugging/lldb_batch.py's verdict;
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
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'compiler/tests/debugging'))
import lldb_batch  # noqa: E402

TARGET = 'windows-x86-64'
PROFILES = (('none', 'off'), ('size', 'off'), ('size', 'auto'),
            ('speed', 'auto'))
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
                'sessions': sessions, 'dap': dap,
                'dap_source': str(DAP_SOURCE)}
    (args.output / 'prepared.json').write_text(json.dumps(manifest, indent=2)
                                               + '\n')
    return manifest


def verify(bundle, built):
    require(sha(bundle / built['image']) == built['image_sha256'],
            built['image'] + ': image checksum')
    require(sha(bundle / built['pdb']) == built['pdb_sha256'],
            built['pdb'] + ': PDB checksum')


def direct(bundle, manifest, lldb, output):
    """LLDB's batch session over each debug.ldn image; the failures."""
    failures = []
    lines = {key: int(value) for key, value in manifest['lines'].items()}
    for built in manifest['sessions']:
        label = built['label']
        try:
            verify(bundle, built)
            try:
                done = subprocess.run(
                    [*lldb, '--batch', '-s', label + '.lldb', built['image']],
                    cwd=bundle, stdin=subprocess.DEVNULL,
                    capture_output=True, timeout=300)
            except subprocess.TimeoutExpired:
                raise Refused(label + ': LLDB did not finish within 300 seconds')
            text = (done.stdout + done.stderr).decode(errors='replace')
            (output / (label + '.transcript')).write_text(text)
            try:
                lldb_batch.check_source(text, lines, label)
            except lldb_batch.Mismatch as error:
                raise Refused(str(error))
            print('%s: LLDB session passed %s' % (TARGET, label), flush=True)
        except Refused as error:
            failures.append(str(error))
            print('%s: %s' % (TARGET, error), file=sys.stderr, flush=True)
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
    #  path; a Windows program started from WSL has taken more than a
    #  minute to answer its launch.
    os.environ['LLDBDAP_LOG'] = str(output / 'lldb-dap.log')
    os.environ['WSLENV'] = ':'.join(
        part for part in (os.environ.get('WSLENV'), 'LLDBDAP_LOG/p') if part)
    try:
        checks = session.run_session(
            lane_refine.command(refine, 'dap'), bundle / 'program.exe',
            source, output, TARGET + '-lldb', debugger_path=lldb_dap,
            limit=240)
    except AssertionError as error:
        raise Refused('the refine dap session: ' + str(error))
    print('%s: refine dap session passed, %d checks' % (TARGET, len(checks)),
          flush=True)


def main():
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
    parser.add_argument('--toolchain', default='x86_64-w64-mingw32-clang',
                        help='the llvm-mingw driver refine links with')
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
                      % (TARGET, len(manifest['sessions'])))
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
