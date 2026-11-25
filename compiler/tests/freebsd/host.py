#!/usr/bin/env python3
"""Build refine on FreeBSD and run its test program there.

check.py emits FreeBSD programs on Linux and runs them in a guest; this lane
makes FreeBSD the compiler's host.  It boots a fresh guest from the locked
release image (environments/freebsd/vm.py), unpacks the pinned GNAT and
GPRbuild that environments/freebsd/gnat.py built there from source, clones
the checkout's HEAD, builds refine and its test program with
scripts/build.sh, and runs scripts/test.sh with the arguments given after
`--`, as an unprivileged user, since the corpus has permission fixtures
root would pass wrongly.  On that host refine's own target is
freebsd-x86-64, so the test program's fixture execution compiles, links and
runs the hosted corpus with the refine it built.

    host.py --arch=amd64 --output=DIR [--mode=debug] [-- TEST ARGUMENTS]
    host.py --arch=amd64 --output=DIR --mode=release --package=DIR

--package builds the release archive, landin-VERSION-x86_64-freebsd.tar.gz,
and its debug archive with scripts/package.sh, smoke-tests the unpacked
archive in the guest and copies both out with their checksums.  The toolchain archive must already be in the cache; gnat.py builds
it, and --build-toolchain lets this lane do so first.
"""
import argparse
import contextlib
import os
import re
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'environments/freebsd'))
import gnat  # noqa: E402
import vm  # noqa: E402

USER = 'landin'
HOME = '/home/' + USER
CHECKOUT = HOME + '/Landin'
#  What the build and the test program need beyond the base system:
#  binutils' as assembles x86-64's GNU assembly (D475's -fno-integrated-as),
#  git gives the build its revision, bash runs the developer scripts.
PACKAGES = ('python3', 'git', 'bash', 'binutils')


def say(text):
    print('host: ' + text, file=sys.stderr, flush=True)


def as_user(command):
    return 'su -l ' + USER + ' -c ' + shlex.quote(command)


def streamed(guest, command, log, timeout):
    """Run a command in the guest, its output into LOG; its status."""
    with log.open('ab') as sink:
        sink.write(('$ ' + command + '\n').encode())
        sink.flush()
        result = subprocess.run([*guest.ssh, command], stdout=sink, stderr=subprocess.STDOUT,
                                timeout=timeout, check=False)
    return result.returncode


def provision(guest, archive, output):
    say('packages')
    guest.checked('service growfs onestart >/dev/null 2>&1 || true')
    guest.checked('env ASSUME_ALWAYS_YES=yes pkg bootstrap -f >/dev/null && pkg update -q'
                  ' && pkg install -qy ' + ' '.join(PACKAGES), timeout=1800)
    #  A login shell, for the user's own HOME, without its login messages.
    guest.checked(f'pw usershow {USER} >/dev/null 2>&1 || pw useradd {USER} -m -s /bin/sh;'
                  f' touch {HOME}/.hushlogin')
    say('toolchain ' + archive.name)
    gnat_home, gpr_home = gnat.install(guest, archive)
    (output / 'guest.txt').write_bytes(guest.checked(
        'freebsd-version -ku; uname -a; sysctl -n hw.ncpu hw.physmem; df -h /;'
        f' {gnat_home}/bin/gcc --version | sed -n 1p;'
        f' {gpr_home}/bin/gprbuild --version | sed -n 1p; as --version | sed -n 1p;'
        ' cc --version | sed -n 1p; python3 --version'))
    return gnat_home, gpr_home


def checkout(guest):
    """HEAD of this checkout, cloned in the guest from a bundle."""
    dirty = subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain',
                            '--untracked-files=no'], capture_output=True, text=True, check=True)
    if dirty.stdout.strip():
        say('the checkout has uncommitted changes; the guest builds HEAD without them')
    head = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True,
                          text=True, check=True).stdout.strip()
    bundle = subprocess.run(['git', '-C', str(ROOT), 'bundle', 'create', '-', 'HEAD'],
                            capture_output=True, check=True).stdout
    guest.checked('cat > /tmp/landin.bundle && chmod 644 /tmp/landin.bundle', input=bundle,
                  timeout=1800)
    guest.checked(as_user(f'rm -rf {CHECKOUT} && git clone -q /tmp/landin.bundle {CHECKOUT}'
                          f' && git -C {CHECKOUT} checkout -q --detach {head}'), timeout=1800)
    return head


def version():
    """The release the README names, as the release workflow reads it."""
    found = re.search(r'^\*\*Status: version ([0-9][0-9.]*)\.', (ROOT / 'README.md').read_text(),
                      re.M)
    vm.require(found, 'README.md names no version')
    return found.group(1)


def package(guest, options, environment, log):
    """The release archive and its debug information, made in the guest by
    scripts/package.sh as the release workflow makes the others, unpacked
    there and smoke-tested, and copied out with their checksums."""
    platform = ('x86_64' if options.arch == 'amd64' else 'aarch64') + '-freebsd'
    asset = f'landin-{version()}-{platform}.tar.gz'
    debug = f'landin-{version()}-{platform}-debug.tar.gz'
    binary = f'compiler/ada/build/freebsd-{options.arch}/release/bin/refine'
    say('package ' + asset)
    status = streamed(guest, as_user(
        f'rm -rf /tmp/landin-package && mkdir /tmp/landin-package && cd {CHECKOUT}'
        f' && {environment} ./scripts/package.sh --debug /tmp/landin-package/{debug}'
        f' {binary} /tmp/landin-package/{asset}'), log, 3600)
    vm.require(status == 0, 'packaging failed; see ' + str(log))
    #  The archive must run where no GNAT is: the toolchain is moved away
    #  while the unpacked refine names its host, compiles and runs a
    #  program, and says what it loads.
    guest.checked(f'mv {gnat.PREFIX} {gnat.PREFIX}.away')
    try:
        smoke = ' && '.join([
            'rm -rf /tmp/landin-unpacked && mkdir /tmp/landin-unpacked',
            f'tar -xzf /tmp/landin-package/{asset} -C /tmp/landin-unpacked',
            'ldd /tmp/landin-unpacked/bin/refine',
            '/tmp/landin-unpacked/bin/refine --version',
            f'cd {CHECKOUT}',
            'python3 compiler/tests/test_default_target.py'
            ' --refine /tmp/landin-unpacked/bin/refine',
            '{ /tmp/landin-unpacked/bin/refine run'
            ' compiler/tests/fixtures/runtime/add-exits-with-its-sum/main.ldn;'
            ' test $? = 42; }',
        ])
        status = streamed(guest, as_user(smoke), log, 1800)
    finally:
        guest.checked(f'mv {gnat.PREFIX}.away {gnat.PREFIX}')
    vm.require(status == 0, 'the packaged refine failed where no GNAT is; see ' + str(log))
    options.package.mkdir(parents=True, exist_ok=True)
    for name in (asset, debug):
        with (options.package / name).open('wb') as sink:
            subprocess.run([*guest.ssh, 'cat /tmp/landin-package/' + name],
                           stdout=sink, check=True, timeout=1800)
        digest = vm.sha(options.package / name)
        (options.package / (name + '.sha256')).write_text(f'{digest}  {name}\n')
    say('packaged ' + asset)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--arch', choices=('amd64', 'arm64'), default='amd64')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path,
                        default=Path(os.environ.get('LANDIN_FREEBSD_CACHE',
                                                    Path.home() / '.cache/landin/freebsd')))
    parser.add_argument('--mode', choices=('debug', 'release'), default='debug')
    parser.add_argument('--package', type=Path, help='make the release archive and copy it here')
    parser.add_argument('--build-toolchain', action='store_true',
                        help='build the toolchain archive first when the cache lacks it')
    parser.add_argument('--memory', type=int, default=8192, help='guest MiB (8192)')
    parser.add_argument('--cpus', type=int, default=os.cpu_count(), help='guest processors')
    parser.add_argument('--jobs', type=int, default=8,
                        help="LANDIN_TEST_JOBS, fixture execution's workers (8)")
    parser.add_argument('--runner-ssh', help='an existing guest: the SSH command that reaches'
                        ' it as root; it is provisioned again')
    parser.add_argument('tests', nargs='*', help="scripts/test.sh's arguments, after --")
    options = parser.parse_args()
    vm.require(options.package is None or options.mode == 'release',
               '--package makes the release archive, from --mode=release')
    options.output.mkdir(parents=True, exist_ok=True)
    archive = gnat.archive_path(options.arch, options.cache)
    if not archive.exists():
        vm.require(options.build_toolchain,
                   f'no toolchain archive {archive.name} in {options.cache}: build it with'
                   f' python3 environments/freebsd/gnat.py --arch={options.arch},'
                   ' or pass --build-toolchain')
        gnat.build(options.arch, options.cache, options.output / 'gnat',
                   memory=max(options.memory, 12288), cpus=options.cpus)
    log = options.output / 'host.log'
    started = time.monotonic()
    if options.runner_ssh:
        guests = contextlib.nullcontext(vm.Guest(ssh=options.runner_ssh))
    else:
        image, _ = vm.prepare(options.arch, options.cache)
        guests = vm.boot(options.arch, image, options.output, memory=options.memory,
                         cpus=options.cpus, disk='32G')
    with guests as guest:
        gnat_home, gpr_home = provision(guest, archive, options.output)
        say('checkout')
        head = checkout(guest)
        environment = (f'LANDIN_GNAT_HOME={gnat_home} LANDIN_GPRBUILD_HOME={gpr_home}'
                       f' LANDIN_BUILD_MODE={options.mode}')
        say(f'build {options.mode} of {head[:12]}')
        status = streamed(guest, as_user(f'cd {CHECKOUT} && {environment} ./scripts/build.sh'),
                          log, 3 * 3600)
        vm.require(status == 0, f'the {options.mode} build failed; see {log}')
        if options.package:
            package(guest, options, environment, log)
        else:
            arguments = ' '.join(shlex.quote(a) for a in options.tests)
            say('test program ' + (arguments or '(the complete local native suite)'))
            status = streamed(guest, as_user(
                f'cd {CHECKOUT} && {environment} LANDIN_TEST_JOBS={options.jobs}'
                f' LANDIN_TEST_TIMINGS=1 ./scripts/test.sh {arguments}'), log, 4 * 3600)
            vm.require(status == 0, 'the test program failed; see ' + str(log))
    say(f'passed in {time.monotonic() - started:.0f} s; log {log}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, subprocess.TimeoutExpired) as error:
        print('host: ' + str(error), file=sys.stderr)
        sys.exit(1)
