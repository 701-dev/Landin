#!/usr/bin/env python3
"""The pinned GNAT and GPRbuild for FreeBSD, built from source in a guest.

GNAT-FSF-builds publishes no FreeBSD archive, so this builds GCC 16.1.0 with
Ada and GPRbuild 26.0.0 in a fresh guest booted from the locked release
image (vm.py), with gnat/build.sh, and keeps the result as one archive in
the cache, named by a digest of everything that went into it: the sources'
pins in environments/pins.sh, the ports' patches, the recipe and the
release image.  A later run with the same inputs takes the archive, so a
guest that builds refine unpacks it at PREFIX rather than building GCC.

    gnat.py --arch=amd64 --key      prints the inputs' digest
    gnat.py --arch=amd64 --path     the archive's path, building nothing
    gnat.py --arch=amd64            the archive's path, built if missing

The archive unpacks at PREFIX, /opt/landin, which the compiler's own
programs name to find their runtime.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import vm  # noqa: E402

PREFIX = '/opt/landin'
GCC_VERSION = '16.1.0'
GPR_VERSION = '26.0.0'
GNAT_HOME = f'{PREFIX}/gnat-{GCC_VERSION}'
GPRBUILD_HOME = f'{PREFIX}/gprbuild-{GPR_VERSION}'
RECIPE = HERE / 'gnat' / 'build.sh'
PATCHES = HERE / 'gnat' / 'patches'
#  GPRbuild's own fix for GNAT 16, from its commit after the 26.0.0 tag.
GPR_PATCH = HERE / 'gnat' / 'gprbuild-6421e350274b.patch'


def pins():
    values = dict(re.findall(r'^(LANDIN_\w+)=(\S+)$',
                             (ROOT / 'environments/pins.sh').read_text(), re.M))
    #  The pins name the versions the archive must hold.
    vm.require(values['LANDIN_GNAT_VERSION'].startswith(GCC_VERSION + '-')
               and values['LANDIN_GPRBUILD_VERSION'].startswith(GPR_VERSION + '-'),
               'environments/pins.sh pins another GNAT or GPRbuild than'
               ' environments/freebsd/gnat.py builds; change both together')
    return values


def sources(values):
    """(file name, URL, sha256) of every source the build takes."""
    adacore = 'https://github.com/AdaCore/{0}/archive/refs/tags/v' + GPR_VERSION + '.tar.gz'
    return [
        (f'gcc-{GCC_VERSION}.tar.xz',
         f'https://ftp.gnu.org/gnu/gcc/gcc-{GCC_VERSION}/gcc-{GCC_VERSION}.tar.xz',
         values['LANDIN_FREEBSD_GCC_SHA256']),
        (f'gprbuild-{GPR_VERSION}.tar.gz', adacore.format('gprbuild'),
         values['LANDIN_FREEBSD_GPRBUILD_SHA256']),
        (f'xmlada-{GPR_VERSION}.tar.gz', adacore.format('xmlada'),
         values['LANDIN_FREEBSD_XMLADA_SHA256']),
        (f'gprconfig_kb-{GPR_VERSION}.tar.gz', adacore.format('gprconfig_kb'),
         values['LANDIN_FREEBSD_GPRCONFIG_KB_SHA256']),
    ]


def key(arch):
    """The digest of everything the archive is built from."""
    values = pins()
    digest = hashlib.sha256()
    def part(name, data):
        digest.update(name.encode() + b'\0' + str(len(data)).encode() + b'\0' + data)
    part('arch', arch.encode())
    part('image', (vm.LOCK['release'] + ' ' + vm.LOCK[arch]['image']).encode())
    for name, _, sha in sources(values):
        part(name, sha.encode())
    part('ports', values['LANDIN_FREEBSD_PORTS_COMMIT'].encode())
    part('recipe', RECIPE.read_bytes())
    for patch in sorted(PATCHES.glob('patch-*')):
        part(patch.name, patch.read_bytes())
    part(GPR_PATCH.name, GPR_PATCH.read_bytes())
    return digest.hexdigest()[:16]


def archive_path(arch, cache):
    return cache / f'gnat-{GCC_VERSION}-gprbuild-{GPR_VERSION}-{arch}-{key(arch)}.tar.xz'


def build(arch, cache, output, *, memory, cpus):
    """Boot a fresh guest, build there, and keep the archive."""
    values = pins()
    image, _ = vm.prepare(arch, cache)
    fetched = cache / 'gnat-sources'
    fetched.mkdir(parents=True, exist_ok=True)
    for name, url, sha in sources(values):
        vm.download(url, fetched / name, sha)
    archive = archive_path(arch, cache)
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with vm.boot(arch, image, output, memory=memory, cpus=cpus, disk='48G') as guest:
        guest.checked('service growfs onestart >/dev/null 2>&1 || true; df -h /')
        guest.checked('rm -rf /var/tmp/landin-sources && mkdir -p /var/tmp/landin-sources/patches')
        for name, _, _ in sources(values):
            stream(guest, fetched / name, '/var/tmp/landin-sources/' + name)
        for patch in sorted(PATCHES.glob('patch-*')):
            guest.put(patch, '/var/tmp/landin-sources/patches/' + patch.name)
        guest.put(RECIPE, '/var/tmp/landin-sources/build.sh')
        guest.put(GPR_PATCH, '/var/tmp/landin-sources/' + GPR_PATCH.name)
        log = output / 'gnat-build.log'
        with log.open('wb') as sink:
            result = subprocess.run(
                [*guest.ssh, 'sh /var/tmp/landin-sources/build.sh /var/tmp/landin-sources '
                 + shlex.quote(PREFIX)], stdout=sink, stderr=subprocess.STDOUT,
                timeout=6 * 3600, check=False)
        vm.require(result.returncode == 0, 'the GNAT build failed in the guest; see ' + str(log))
        partial = archive.with_suffix('.part')
        with partial.open('wb') as sink:
            result = subprocess.run(
                [*guest.ssh, 'tar -cf - -C ' + shlex.quote(PREFIX) + ' . | xz -T0 -6'],
                stdout=sink, timeout=3600, check=False)
        vm.require(result.returncode == 0, 'could not take the built toolchain from the guest')
        partial.rename(archive)
    print(f'gnat: built {archive.name} in {time.monotonic() - started:.0f} s', file=sys.stderr)
    return archive


def stream(guest, source, destination):
    """Copy a file into the guest without holding it in memory."""
    with source.open('rb') as f:
        result = subprocess.run([*guest.ssh, 'cat > ' + shlex.quote(destination)],
                                stdin=f, capture_output=True, timeout=1800, check=False)
    vm.require(result.returncode == 0, 'could not copy %s into the guest: %s'
               % (source.name, result.stderr.decode(errors='replace')))


def install(guest, archive):
    """Unpack the archive at PREFIX in a guest; returns the two homes."""
    guest.checked('rm -rf ' + PREFIX + ' && mkdir -p ' + PREFIX)
    with archive.open('rb') as f:
        result = subprocess.run([*guest.ssh, 'xz -dc | tar -xf - -C ' + PREFIX],
                                stdin=f, capture_output=True, timeout=1800, check=False)
    vm.require(result.returncode == 0, 'could not unpack the toolchain in the guest: '
               + result.stderr.decode(errors='replace'))
    return GNAT_HOME, GPRBUILD_HOME


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--arch', choices=('amd64', 'arm64'), required=True)
    parser.add_argument('--cache', type=Path,
                        default=Path(os.environ.get('LANDIN_FREEBSD_CACHE',
                                                    Path.home() / '.cache/landin/freebsd')))
    parser.add_argument('--output', type=Path, help='where the build keeps its logs')
    parser.add_argument('--key', action='store_true', help="print the inputs' digest")
    parser.add_argument('--path', action='store_true',
                        help="print the archive's path in the cache, building nothing")
    parser.add_argument('--memory', type=int, default=12288, help='guest MiB (12288)')
    parser.add_argument('--cpus', type=int, default=os.cpu_count(), help='guest processors')
    options = parser.parse_args()
    if options.key:
        print(key(options.arch))
        return 0
    archive = archive_path(options.arch, options.cache)
    if options.path:
        print(archive)
        return 0
    if not archive.exists():
        with tempfile.TemporaryDirectory(prefix='landin-gnat-') as scratch:
            build(options.arch, options.cache, options.output or Path(scratch),
                  memory=options.memory, cpus=options.cpus)
    print(archive)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except ValueError as error:
        print('gnat: ' + str(error), file=sys.stderr)
        sys.exit(1)
