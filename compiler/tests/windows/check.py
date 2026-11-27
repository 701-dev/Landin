#!/usr/bin/env python3
"""Emit a Windows target's corpus on Linux, then execute it on Windows.

Two stages, which a local run joins and the gate splits between a Linux
job and a Windows job:

  --prepare-only   select the runtime fixtures whose `targets:` names
                   the --target, windows-x86-64 by default or windows-arm64,
                   compile each at every profile with Linux
                   `refine` and the llvm-mingw driver, and write the
                   executables and `prepared.json` into OUTPUT;
  --prepared=DIR   execute a prepared bundle and hold each outcome to its
                   fixture, with no compiler and no checkout: the
                   bundle carries this file and the scripts it imports
                   under `lane/`, as debug.py's does.

`--link=microsoft` selects Microsoft's link (D2327) in place of
llvm-mingw's: emission records the link command refine gives a driver
named for Clang's Microsoft target, `x86_64-pc-windows-msvc` or
`aarch64-pc-windows-msvc` (D2387), with the assembly, and execution runs
that command with `--driver`, a Clang that links with `link.exe` on
Windows, before it runs the program.

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
#  The lane's target, which --target sets: windows-x86-64 or windows-arm64.
TARGET = 'windows-x86-64'
#  Each target's llvm-mingw driver, and the level a fixture's `levels:`
#  names that the lane builds it at too, with the family's first.
DRIVERS = {'windows-x86-64': 'x86_64-w64-mingw32-clang',
           'windows-arm64': 'aarch64-w64-mingw32-clang'}
LEVELS = {'windows-x86-64': ('x86-64-v1', 'x86-64-v3'),
          'windows-arm64': ('armv8-a', 'armv8.1-a')}
PROFILES = [('none', 'off'), ('size', 'off'), ('size', 'auto'), ('speed', 'auto')]
SPECIALIZED = [('none', 'all'), ('speed', 'all')]
#  STATUS_ILLEGAL_INSTRUCTION: the exit code of a process ended by the
#  trap instruction a failed check executes, `ud2` or arm64's `brk #1`,
#  with no handler.
TRAP_STATUS = 0xC000001D
#  What the selection must not ask of the lane: a C peer is the ABI kind's
#  alone, and a C library is none Windows links.
UNSUPPORTED = ('c-shared', 'c-archives', 'library-directories', 'c-inputs', 'link')
#  The lane's kind, which --kind sets: the runtime corpus, or the ABI
#  fixtures, each linked with its independent C peer (D2473).
KIND = 'runtime'
#  D2473: the C peers the ABI kind must run: FreeBSD's required set
#  (compiler/tests/freebsd/check.py's ABI_REQUIRED), variadic floats past
#  the register slots, and on x86-64 the registers Win64 makes a callee
#  save, held across a callback C enters.
ABI_REQUIRED = {'r440-native-scalars', 'r440-native-aggregates', 'r440-native-callbacks',
                'r440-varargs-pointer-callback', 'r450-review-backend-c-entry',
                'windows-variadic-floats'}
ABI_REQUIRED_ON = {'windows-x86-64': {'windows-c-entry-saves'}, 'windows-arm64': set()}
#  What a C peer is compiled with, as every lane compiles one.
C_FLAGS = ('-std=c11', '-O2', '-Wall', '-Wextra', '-Werror')


#  The files a prepared bundle's execution runs, at their own paths under
#  OUTPUT/lane, so that a Windows host runs a bundle with no checkout.
LANE = ('compiler/tests/windows/check.py', 'scripts/lane_refine.py',
        'scripts/refine_revision.py', 'scripts/build_identity.py',
        'environments/pins.sh')


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
    for path in sorted((ROOT / 'compiler/tests/fixtures' / KIND).glob('*/fixture.meta')):
        meta = meta_module.read(path.parent)
        if meta.applies_to(TARGET):
            found.append((path.parent, meta))
    require(found, TARGET + ': empty fixture selection')
    for base, meta in found:
        asked = [key for key in UNSUPPORTED + (('c-sources',) if KIND == 'runtime' else ())
                 if meta.get(key)]
        require(not asked, '%s names %s, which the Windows lane does not run'
                % (base.name, ', '.join(asked)))
        require(KIND == 'runtime' or meta.c_sources,
                base.name + ': an ABI fixture lacks an independently compiled C peer')
    if KIND == 'abi' and not cases:
        missing = (ABI_REQUIRED | ABI_REQUIRED_ON[TARGET]) - {base.name for base, _ in found}
        require(not missing, TARGET + ': ABI coverage missing: ' + ', '.join(sorted(missing)))
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
        base_level, named = LEVELS[TARGET]
        if named in meta.levels_for(TARGET):
            levels += [base_level, named]
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
#  D2387: each target's recording driver, named for its Microsoft triple.
MICROSOFT_DRIVERS = {'windows-x86-64': 'x86_64-pc-windows-msvc-clang',
                     'windows-arm64': 'aarch64-pc-windows-msvc-clang'}


def recorder(output):
    """The recording driver under OUTPUT, whose file name selects
    Microsoft's link."""
    path = output / 'driver' / MICROSOFT_DRIVERS[TARGET]
    path.parent.mkdir(parents=True)
    path.write_text(RECORDER % sys.executable)
    path.chmod(0o755)
    return path


def windows_libraries():
    """The import libraries `platform/windows` names, each a
    `linker.library` line, which a C peer's link takes beside the C
    runtime's own."""
    import re
    names = set()
    for path in (ROOT / 'platform/windows').rglob('*.ldn'):
        names.update(re.findall(r'linker\.library\("([^"]+)"\)', path.read_text()))
    return sorted(names)


def build(args, bundle, item):
    base, meta, optimize, specialize, level = item
    label = '-'.join((base.name, optimize, specialize, level or 'default'))
    executable = bundle / (label + '.exe')
    peers = bool(meta.c_sources)
    #  D2473: a C peer's program is the C runtime's, so refine emits the
    #  assembly alone and the Windows job compiles the peer and links both
    #  with llvm-mingw's Clang there, which carries the C headers and
    #  runtime this host's MinGW driver lacks.
    output = bundle / (label + '.s') if peers else executable
    argv = [str(args.refine), 'compile', '--target=' + TARGET,
            '--optimize=' + optimize, '--specialize=' + specialize,
            *(['--level=' + level] if level else []),
            *([] if peers else ['--toolchain=' + args.toolchain]),
            *(['--linker=' + args.linker] if args.linker and not peers else []),
            *meta.source_arguments(base),
            '--emit=' + ('asm' if peers else 'exe'), '-o', str(output)]
    environment = dict(os.environ, LANDIN_DEFERRED_LINK=str(bundle / label))
    done = subprocess.run(argv, cwd=ROOT / 'compiler/ada', capture_output=True,
                          env=environment)
    (bundle / (label + '.build.log')).write_bytes(
        ' '.join(argv).encode() + b'\n' + done.stdout + done.stderr)
    require(done.returncode == 0, '%s: refine exited %d: %s' % (
        label, done.returncode, (done.stdout + done.stderr).decode(errors='replace')[:400]))
    #  The bundle carries the files a fixture is run with, beside its
    #  executables, at paths relative to the bundle, so that it runs where
    #  there is no checkout.
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
    deferred = args.link == 'microsoft' and not peers
    if deferred:
        link = json.loads((bundle / (label + '.link.json')).read_text())
        executable.unlink()
    peer = {}
    if peers:
        sources = []
        for one in meta.c_sources:
            copy = Path('inputs', base.name, one.strip())
            (bundle / copy).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(base / one.strip(), bundle / copy)
            sources.append(copy.as_posix())
        peer = {'peer': {'sources': sources, 'c_args': meta.c_args_for(TARGET),
                         'libraries': windows_libraries()},
                'assembly_sha256': sha(output)}
    return {'label': label, 'case': KIND + '/' + base.name,
            'optimize': optimize, 'specialize': specialize, 'level': level,
            **({'link': link, 'assembly_sha256': sha(bundle / (label + '.s'))}
               if deferred else peer if peers else {'executable_sha256': sha(executable)}),
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
    for file in LANE:
        (args.output / 'lane' / file).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / file, args.output / 'lane' / file)
    manifest = {'target': TARGET, 'kind': KIND, 'link': args.link,
                'scope': 'filtered' if args.case else
                         'shard %d of %d' % args.shard if args.shard else 'complete',
                'revision': os.environ.get('GITHUB_SHA'),
                'refine_sha256': sha(args.refine),
                'build_failures': failed,
                'results': [one for one in built if not isinstance(one, BaseException)]}
    (args.output / 'prepared.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def windows_error_mode():
    """Keep Windows Error Reporting away from a program a trap ends.

    The error mode, which every child inherits, keeps WER's dialog away
    but not WER itself: with several traps at once, most of them still
    start a WerFault that runs for seconds, enough to push an outcome
    past its limit on a host where WER is on (D2474; GitHub's images
    turn it off).  The lane's process therefore joins a job object that
    says JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION: a process of the
    job that an exception ends is ended with the exception's code as
    its status, as before, and WER is never asked.  Every child joins
    the job with its parent, and a job inside the runner's own is
    allowed.  WER's per-user `Disabled` value was measured too and keeps
    only some reports away."""
    if sys.platform != 'win32':
        return
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    #  SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX
    kernel32.SetErrorMode(0x8003)

    class Basic(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64),
                    ('PerJobUserTimeLimit', ctypes.c_int64),
                    ('LimitFlags', wintypes.DWORD),
                    ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t),
                    ('ActiveProcessLimit', wintypes.DWORD),
                    ('Affinity', ctypes.c_size_t),
                    ('PriorityClass', wintypes.DWORD),
                    ('SchedulingClass', wintypes.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', Basic),
                    ('IoInfo', ctypes.c_uint64 * 6),
                    ('ProcessMemoryLimit', ctypes.c_size_t),
                    ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t),
                    ('PeakJobMemoryUsed', ctypes.c_size_t)]

    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = kernel32.CreateJobObjectW(None, None)
    require(job, 'CreateJobObjectW failed: %d' % ctypes.get_last_error())
    limits = Extended()
    #  JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
    limits.BasicLimitInformation.LimitFlags = 0x400
    #  JobObjectExtendedLimitInformation
    require(kernel32.SetInformationJobObject(job, 9, ctypes.byref(limits),
                                             ctypes.sizeof(limits)),
            'SetInformationJobObject failed: %d' % ctypes.get_last_error())
    require(kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()),
            'AssignProcessToJobObject failed: %d' % ctypes.get_last_error())


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


#  D2969: the Microsoft tools the gate's link requires, by version, which
#  environments/pins.sh names and the lane selects among what the host
#  installs: an MSVC toolset, whose link.exe runs the link, and a Windows
#  SDK, whose import libraries it reads.  The machine is the SDK's and the
#  toolset's name for the target's architecture.
VSWHERE = os.path.join(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
                       'Microsoft Visual Studio', 'Installer', 'vswhere.exe')
SDK_ROOT = os.path.join(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
                        'Windows Kits', '10')
MACHINES = {'windows-x86-64': 'x64', 'windows-arm64': 'arm64'}
PIN_ADVICE = ('; the gate names its own as %s in environments/pins.sh, which'
              ' compiler/ada/TOOLCHAIN.md records: name one this host carries in both'
              ' (compiler/tests/windows/README.md, "Microsoft\'s link")')


def windows_path(path):
    """PATH as one spelling, for comparing what Clang printed with what
    the lane chose: backslashes, one each, and no case."""
    return path.replace('/', '\\').replace('\\\\', '\\').rstrip('\\').lower()


def visual_studio_installations():
    """Each Visual Studio installation vswhere names, as JSON objects."""
    require(os.path.isfile(VSWHERE),
            'no Visual Studio installer at %s, so no MSVC toolset to select' % VSWHERE)
    try:
        done = subprocess.run([VSWHERE, '-all', '-products', '*', '-format', 'json'],
                              capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Refused('vswhere did not list the Visual Studio installations: %s' % error)
    require(done.returncode == 0, 'vswhere exited %d' % done.returncode)
    return json.loads(done.stdout.decode(errors='replace') or '[]')


def microsoft_tools(toolset, sdk, installations, sdk_root=SDK_ROOT):
    """The MSVC toolset TOOLSET among INSTALLATIONS with a link.exe for the
    target, and the Windows SDK SDK under SDK_ROOT with the target's import
    libraries; refuse, naming what the host carries instead."""
    machine = MACHINES[TARGET]
    carried = {}
    for installation in installations:
        tools = os.path.join(installation['installationPath'], 'VC', 'Tools', 'MSVC')
        for name in sorted(os.listdir(tools)) if os.path.isdir(tools) else ():
            bin_dir = os.path.join(tools, name, 'bin')
            if any(os.path.isfile(os.path.join(bin_dir, host, machine, 'link.exe'))
                   for host in (sorted(os.listdir(bin_dir)) if os.path.isdir(bin_dir) else ())):
                carried.setdefault(name, (os.path.join(tools, name), installation))
    require(toolset in carried,
            'this host carries no MSVC toolset %s with a link.exe for %s; it carries %s'
            % (toolset, machine, ', '.join(sorted(carried)) or 'none')
            + PIN_ADVICE % 'LANDIN_MSVC_TOOLSET_VERSION')
    libraries = os.path.join(sdk_root, 'Lib')
    sdks = sorted(name for name in (os.listdir(libraries) if os.path.isdir(libraries) else ())
                  if os.path.isfile(os.path.join(libraries, name, 'um', machine,
                                                 'kernel32.lib')))
    require(sdk in sdks,
            'this host carries no Windows SDK %s with %s import libraries under %s; it'
            ' carries %s' % (sdk, machine, sdk_root, ', '.join(sdks) or 'none')
            + PIN_ADVICE % 'LANDIN_WINDOWS_SDK_VERSION')
    root, installation = carried[toolset]
    return {'toolset': toolset, 'root': root, 'windows_sdk': sdk, 'sdk_root': sdk_root,
            'machine': machine,
            'visual_studio': '%s %s' % (installation.get('displayName', 'Visual Studio'),
                                        installation.get('installationVersion', '?'))}


def tools_options(tools):
    """The Clang options that select TOOLS rather than leave the search to
    the driver, which a Clang built without Visual Studio's setup API, as
    llvm-mingw's is, cannot make."""
    return ['-Xmicrosoft-visualc-tools-root', tools['root'],
            '-Xmicrosoft-windows-sdk-root', tools['sdk_root'],
            '-Xmicrosoft-windows-sdk-version', tools['windows_sdk']]


def linker_version(linker):
    """The banner link.exe prints first, which names its own version."""
    try:
        done = subprocess.run([linker], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Refused('could not start the linker %s: %s' % (linker, error))
    return (done.stdout.decode(errors='replace').splitlines() or [''])[0].strip()


def linked(bundle, result, driver, expect_linker, tools=None):
    """Run the link command refine chose for Microsoft's link, with DRIVER,
    and say which linker it ran; with TOOLS, require that the link ran that
    toolset's linker over that SDK's import libraries; raise what is
    wrong."""
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
    #  Clang doubles each backslash of a quoted path.
    linker = ran[-1][1:].split('"', 1)[0].replace('\\\\', '\\')
    name = linker.replace('\\', '/').rsplit('/', 1)[-1].lower()
    require(not expect_linker or name == expect_linker.lower(),
            '%s: the link ran %s, not %s' % (label, linker, expect_linker))
    if tools:
        #  Clang ignores an SDK version it does not find and takes another.
        line = windows_path(ran[-1])
        require(windows_path(linker).startswith(windows_path(tools['root']) + '\\'),
                '%s: the link ran %s, not MSVC toolset %s\'s' % (label, linker, tools['toolset']))
        require(windows_path(os.path.join(tools['sdk_root'], 'Lib', tools['windows_sdk'], 'um',
                                          tools['machine'])) in line,
                '%s: the link did not read Windows SDK %s\'s import libraries: %s'
                % (label, tools['windows_sdk'], ran[-1][-600:]))
    result['linker'] = linker
    result['executable_sha256'] = sha(bundle / (label + '.exe'))


def peer_linked(bundle, result, cc):
    """Compile the C peers and link them with the emitted assembly, with
    CC, llvm-mingw's Clang for the target, and the C runtime it carries;
    raise what is wrong."""
    label = result['label']
    assembly = bundle / (label + '.s')
    require(sha(assembly) == result['assembly_sha256'], label + ': assembly checksum')
    peer = result['peer']
    compile_args = [a for a in peer['c_args'] if not a.startswith(('-Wl,', '-l'))]
    log = b''
    objects = []

    def step(argv, what):
        nonlocal log
        try:
            done = subprocess.run(argv, cwd=bundle, capture_output=True, timeout=300)
        except OSError as error:
            raise Refused('%s: could not start %s: %s' % (label, argv[0], error))
        except subprocess.TimeoutExpired:
            raise Refused('%s: %s did not finish within 300 seconds' % (label, what))
        log += ' '.join(argv).encode() + b'\n' + done.stdout + done.stderr
        (bundle / (label + '.link.log')).write_bytes(log)
        require(done.returncode == 0, '%s: %s exited %d: %s' % (
            label, what, done.returncode, (done.stdout + done.stderr).decode(errors='replace')[-600:]))
    for index, source in enumerate(peer['sources']):
        obj = bundle / ('%s-peer-%d.o' % (label, index))
        step([*cc, *C_FLAGS, *compile_args, '-c', str(bundle / source), '-o', str(obj)],
             'the C peer\'s compilation')
        objects.append(str(obj))
    #  The C runtime starts the program and calls the peer's `main`; the
    #  sections nothing retained reaches are dropped, as refine's own link
    #  drops them.
    step([*cc, str(assembly), *objects, *peer['c_args'], '-Wl,--gc-sections',
          *['-l' + name for name in peer['libraries']],
          '-o', str(bundle / (label + '.exe'))], 'the link')
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
    if 'peer' in result:
        #  A C peer writes through the C runtime's text-mode streams, which
        #  end a line with CR LF on Windows; a fixture's oracle is LF's.
        done.stdout = done.stdout.replace(b'\r\n', b'\n')
        done.stderr = (done.stderr or b'').replace(b'\r\n', b'\n')
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


def execute(bundle, manifest, runner, jobs, driver=(), expect_linker='', cc=(),
            tools=None):
    windows_error_mode()
    results = manifest['results']
    require(results or manifest.get('build_failures'), 'empty prepared fixture selection')

    def one(result):
        try:
            if 'link' in result:
                linked(bundle, result, driver, expect_linker, tools)
            if 'peer' in result:
                peer_linked(bundle, result, cc)
            outcome(bundle, result, runner)
            result['verdict'] = 'passed'
            return None
        except Refused as error:
            result['verdict'] = 'failed'
            result['failure'] = str(error)
            #  An image only the Windows job linked is kept apart, so that
            #  a failed outcome's can be read where it was not linked.
            image = bundle / (result['label'] + '.exe')
            if ('link' in result or 'peer' in result) and image.exists():
                kept = bundle.parent / 'failed'
                kept.mkdir(exist_ok=True)
                shutil.copyfile(image, kept / image.name)
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
    global TARGET, KIND
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sys.path.insert(0, str(ROOT / 'scripts'))
    import lane_refine  # the --refine every lane takes
    lane_refine.argument(parser, required=False, help='the Linux refine that emits')
    parser.add_argument('--output', type=Path, required=True,
                        help='a new directory for the bundle, transcripts and summary.json')
    parser.add_argument('--target', choices=sorted(DRIVERS), default=TARGET,
                        help='the Windows target the lane emits and runs')
    parser.add_argument('--kind', choices=('runtime', 'abi'), default=KIND,
                        help='the runtime corpus, or the ABI fixtures with their C peers')
    parser.add_argument('--cc', default='',
                        help="the ABI kind's C compiler at execution, llvm-mingw's"
                        " Clang for the target; the target's driver name by default")
    parser.add_argument('--toolchain',
                        help="the llvm-mingw driver refine links with; the target's by default")
    parser.add_argument('--link', choices=('mingw', 'microsoft'), default='mingw',
                        help="whose link refine chooses: llvm-mingw's, the default, or"
                        " Microsoft's (D2327), which execution runs with --driver")
    parser.add_argument('--linker', default='',
                        help="refine's --linker under Microsoft's link: lld for lld-link")
    parser.add_argument('--driver', default='clang',
                        help="the Clang that runs Microsoft's link at execution")
    parser.add_argument('--expect-linker', default='',
                        help="the linker Microsoft's link must run, such as link.exe")
    parser.add_argument('--msvc-toolset', default='',
                        help="the MSVC toolset Microsoft's link must run, such as 14.44.35207;"
                        " with --windows-sdk, selected among what Visual Studio installs")
    parser.add_argument('--windows-sdk', default='',
                        help="the Windows SDK whose import libraries Microsoft's link must"
                        " read, such as 10.0.26100.0")
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
    TARGET = args.target
    KIND = args.kind
    args.toolchain = args.toolchain or DRIVERS[TARGET]
    args.output = args.output.resolve()
    summary = {'target': TARGET, 'kind': KIND, 'status': 'failed'}
    try:
        require(not (args.prepare_only and args.prepared), 'prepare and execute are distinct stages')
        require(args.prepared or args.refine, 'emission needs --refine')
        require(not (args.shard and args.case), 'a shard is a share of the complete lane')
        require(KIND == 'runtime' or args.link == 'mingw',
                "the ABI kind links its C peers with llvm-mingw's C runtime alone")
        require(bool(args.msvc_toolset) == bool(args.windows_sdk),
                '--msvc-toolset and --windows-sdk select the Microsoft tools together')
        args.output.mkdir(parents=True, exist_ok=False)
        if args.prepared:
            prepared = args.prepared.resolve()
            manifest = json.loads((prepared / 'prepared.json').read_text())
            require(manifest['target'] == TARGET and manifest.get('kind', 'runtime') == KIND,
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
        driver, tools = args.driver.split(), None
        if manifest.get('link') == 'microsoft':
            summary['link'] = 'microsoft'
            summary['driver'] = driver_version(driver)
            if args.msvc_toolset:
                tools = microsoft_tools(args.msvc_toolset, args.windows_sdk,
                                        visual_studio_installations())
                summary['microsoft'] = {key: tools[key] for key in
                                        ('visual_studio', 'toolset', 'windows_sdk')}
                driver += tools_options(tools)
        try:
            execute(bundle, manifest, args.runner.split(), args.jobs,
                    driver, args.expect_linker,
                    (args.cc or DRIVERS[TARGET]).split(), tools)
        finally:
            if manifest.get('link') == 'microsoft':
                summary['linkers'] = sorted({one['linker'] for one in manifest['results']
                                             if 'linker' in one})
                if tools and summary['linkers']:
                    summary['microsoft']['linker'] = linker_version(summary['linkers'][0])
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
