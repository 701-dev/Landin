#!/usr/bin/env python3
"""Install the pinned embedded tools privately on Linux x86-64 (no sudo)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'scripts'))
import download  # noqa: E402
DEFAULT = Path.home() / "work/.cortex-m"
PINS = HERE.parent / "pins.sh"
#  The lock holds archives built by 701-dev/nix-packages: GCC, binutils and
#  newlib for the Cortex-M lanes (arm-eabi) and the RV32 lanes
#  (riscv64-elf), the emulators, and the GDB whose Python the sessions run.
#  Espressif's Xtensa compiler and its per-chip plugins are its release,
#  pinned in environments/pins.sh.
XTENSA = "xtensa-esp-elf"
#  Where the lock's archives are unpacked: the two bare-metal compilers,
#  QEMU for the Cortex-M machines, GDB, and Espressif's QEMU, one archive
#  serving the RV32 and the Xtensa lanes.
ARM = "gcc-arm-eabi"
RISCV = "gcc-riscv64-elf"
#  What the two compilers' --version names as their package.
BUILDER = "701-dev nix-packages"
QEMU_ARM = "qemu-arm"
GDB = "gdb"
ESPRESSIF = "qemu-espressif"
ESPRESSIF_XTENSA = "qemu-xtensa"


def pins():
    """environments/pins.sh's assignments, which this file never repeats."""
    return dict(re.findall(r"^(LANDIN_\w+)=(\S+)$", PINS.read_text(), re.M))


def locked(area):
    """The lock's archive unpacked into AREA: its URL, file and sha256."""
    for item in json.loads((HERE / 'tools.lock.json').read_text()):
        if area in areas(item):
            return item
    raise RuntimeError('environments/cortex-m/tools.lock.json has no archive for ' + area)


def gcc_version(area):
    """The GCC version the lock's compiler archive for AREA holds, from its
    file name, gcc-TARGET-VERSION-SYSTEM.tar.xz."""
    return locked(area)['file'][len(area) + 1:].split('-', 1)[0]


def xtensa_archive():
    """Espressif's compiler with its two chip-specific configuration plugins."""
    values = pins()
    version = values['LANDIN_XTENSA_ESP_ELF_VERSION']
    name = 'xtensa-esp-elf-%s-x86_64-linux-gnu.tar.xz' % version
    return {'url': '%s/%s/%s' % (values['LANDIN_XTENSA_ESP_ELF_RELEASES'],
                                values['LANDIN_XTENSA_ESP_ELF_RELEASE'], name),
            'file': name, 'version': version,
            'sha256': values['LANDIN_XTENSA_ESP_ELF_SHA256_X86_64_LINUX']}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


#  What an installation holds, each inventoried whole.
AREAS = (QEMU_ARM, GDB, ARM, RISCV, ESPRESSIF, XTENSA, ESPRESSIF_XTENSA)
REQUIRED_TOOLS = (
    'installation.json', ARM + '/bin/arm-eabi-gcc', RISCV + '/bin/riscv64-elf-gcc',
    QEMU_ARM + '/bin/qemu-system-arm', GDB + '/bin/gdb',
    ESPRESSIF + '/bin/qemu-system-riscv32',
    ESPRESSIF_XTENSA + '/bin/qemu-system-xtensa',
    XTENSA + '/bin/xtensa-esp-elf-gcc', XTENSA + '/bin/xtensa-esp-elf-as',
    *(XTENSA + '/bin/xtensa-%s-elf-%s' % (chip, tool)
      for chip in ('esp32', 'esp32s3') for tool in ('gcc', 'as')),
    *(XTENSA + '/lib/xtensa_%s.so' % chip for chip in ('esp32', 'esp32s3')),
)


def inventory(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob("*"))
            if p.is_file() and '__pycache__' not in p.parts}


def probe_inputs(root):
    """What a lane's verdict is about: every file under ROOT that a lane
    can read, which is all of them but the Markdown that describes them.
    A run records these before its lanes and refuses its own verdicts when
    one changed meanwhile; the guide beside the lanes is no input, so it
    may be edited while they run."""
    return {name: digest for name, digest in inventory(root).items()
            if not name.endswith('.md')}


#  The lock's archives need nothing of the host's: the two compilers, the
#  Espressif QEMU and GDB are static, and the Cortex-M QEMU carries its own
#  glibc and loader.  Espressif's Xtensa compiler is a glibc binary that
#  asks for glibc 2.17, so that is the host it needs, whichever
#  distribution supplies it.
GLIBC = (2, 17)


def supported_host(output=None):
    """Refuse a host the locked tools cannot run on, before anything builds.

    OUTPUT is the lane's --output, which must outlive the run.
    """
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("embedded probes require native Linux x86-64")
    library, version = platform.libc_ver()
    parts = version.split('.')[:2]
    if (library != 'glibc' or not all(part.isdigit() for part in parts)
            or tuple(map(int, parts)) < GLIBC):
        raise RuntimeError("embedded profile requires glibc %d.%d or later" % GLIBC)
    nixos_route(output)


LOADER = '/lib64/ld-linux-x86-64.so.2'
#  The flake's wrapper, which nix develop puts on PATH on Linux x86-64: it
#  runs a command in a bubblewrap namespace holding the store's glibc and
#  libstdc++ at their FHS paths, and sets LANDIN_FHS inside.
FHS = 'landin-fhs'


def nixos_route(output=None):
    """On NixOS, run this lane where the pinned cross compilers can start.

    NixOS's own loader path holds a stub that refuses a binary built for
    another distribution, so Espressif's Xtensa compiler, a release binary
    for glibc, starts only inside an FHS environment.  The flake's `landin-fhs` is one: when it is on PATH, as it
    is in `nix develop`, the lane runs itself again through it, with the
    same arguments, before it has done anything; without it the lane is
    refused naming that route.

    Inside landin-fhs /tmp is the host's.  Another FHS environment, such as
    steam-run's, gives /tmp a private namespace: a TMPDIR the outer shell
    set into it does not exist inside, so refine cannot make its files, and
    an --output under /tmp vanishes when the lane ends; those are refused.
    """
    lane = 'environments/cortex-m/' + os.path.basename(sys.argv[0] or 'run.py')
    route = (
        'nix develop -c python3 %s --tools DIR --refine REFINE --output NEW-DIRECTORY ...\n'
        'See environments/cortex-m/README.md#on-nixos.' % lane)
    stub = 'stub-ld' in os.path.realpath(LOADER) or (
        os.path.exists('/etc/NIXOS') and not os.path.exists(LOADER))
    if stub:
        if os.environ.get('LANDIN_FHS'):
            raise SystemExit(
                'cortex-m: inside %s, %s is still NixOS\'s stub loader, so the flake\'s'
                ' FHS environment did not provide the store\'s glibc there.' % (FHS, LOADER))
        wrapper = shutil.which(FHS)
        if wrapper is not None:
            sys.stdout.flush()
            sys.stderr.flush()
            os.execv(wrapper, [wrapper, sys.executable, *sys.orig_argv[1:]])
        raise SystemExit(
            'cortex-m: Espressif\'s pinned Xtensa compiler is a release binary for glibc, and this'
            ' NixOS host\'s %s is its stub loader, which refuses them.  Run the lane from `nix develop`,'
            ' whose %s runs it in an FHS environment of the store\'s glibc:\n  %s'
            % (LOADER, FHS, route))
    if os.environ.get('LANDIN_FHS'):
        return
    inside = not os.path.exists('/etc/NIXOS') and os.path.isdir('/run/current-system')
    if not inside:
        return
    temporary = os.environ.get('TMPDIR')
    if temporary and not os.path.isdir(temporary):
        raise SystemExit(
            'cortex-m: TMPDIR is %s, which does not exist inside this FHS environment:'
            ' it gives /tmp a private namespace, as steam-run\'s does.  Run the lane'
            ' from `nix develop` instead, whose %s keeps the host\'s /tmp:\n  %s'
            % (temporary, FHS, route))
    if output is not None and Path(os.path.abspath(output)).is_relative_to('/tmp'):
        raise SystemExit(
            'cortex-m: --output %s is under /tmp, which this FHS environment keeps private'
            ' and discards when the lane ends, as steam-run\'s does.  Run the lane from'
            ' `nix develop` instead, whose %s keeps the host\'s /tmp:\n  %s'
            % (output, FHS, route))


def installed_tools(path):
    """The resolved tool root, refused before any build if nothing is installed there.

    Every lane runs `gcc-arm-eabi/bin/arm-eabi-gcc` and friends under the
    root its --tools names, which defaults to DEFAULT; without this a host
    whose tools are elsewhere failed each profile with "No such file or
    directory" from a compile, naming neither where it looked nor how to
    look elsewhere.
    """
    root = Path(path).expanduser().resolve()
    missing = [relative for relative in REQUIRED_TOOLS
               if not (root / relative).is_file()]
    if missing:
        raise SystemExit(
            'cortex-m: the locked embedded tools are not installed at %s (no %s).\n'
            'Pass --tools DIRECTORY where `python3 environments/cortex-m/setup.py --tools DIRECTORY`'
            ' installed them, or install them there; the default is %s.'
            % (root, ', '.join(missing), DEFAULT))
    return root


def fetch(packages, item, sleep=time.sleep):
    """ITEM's archive downloaded into PACKAGES and verified before anything unpacks it."""
    dest = packages / item['file']

    def store(src):
        with dest.open('wb') as out:
            shutil.copyfileobj(src, out)
    url = item['url']
    try:
        #  urlopen is named here at each call, so a control can replace it.
        download.download(url, item['file'], store, sleep=sleep,
                          opener=lambda url, timeout: urllib.request.urlopen(url, timeout=timeout),
                          report=lambda line: print(line, file=sys.stderr, flush=True))
    except download.DownloadError as error:
        raise SystemExit('setup.py: %s' % error)
    #  Never asked again: the bytes arrived and are not the pinned ones.
    found = sha(dest)
    if found != item['sha256']:
        raise RuntimeError('archive hash mismatch: %s from %s has SHA-256 %s, not the pinned %s'
                           % (item['file'], url, found, item['sha256']))
    return dest


def unpack(archive, into, mode):
    """A release archive's one top directory unpacked as INTO itself."""
    into.mkdir()
    subprocess.run(['tar', mode, str(archive), '-C', str(into), '--strip-components=1'],
                   check=True, timeout=600)


#  The areas the lock's archives may be unpacked into.
LOCKED = (ARM, RISCV, QEMU_ARM, GDB, ESPRESSIF, ESPRESSIF_XTENSA)


def areas(item):
    """The areas an archive of the lock is unpacked into: `into` names one,
    or a list when one archive serves several, as nix-packages' Espressif
    QEMU, which holds both emulators, serves the RV32 and the Xtensa lanes."""
    into = item.get('into', [])
    return [into] if isinstance(into, str) else list(into)


def installer_tools():
    """Name missing unpackers before creating any installation directory."""
    missing = [name for name in ('tar', 'xz') if shutil.which(name) is None]
    if missing:
        raise RuntimeError(
            'setup.py needs %s on PATH to unpack the locked archives; install tar'
            ' and xz before retrying. On NixOS `nix develop` provides both; see'
            ' environments/cortex-m/README.md#on-nixos.' % ', '.join(missing))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools', type=Path, default=DEFAULT)
    args = parser.parse_args()
    supported_host(args.tools)
    installer_tools()
    root = args.tools.resolve()
    if root.exists():
        raise RuntimeError("installation already exists; choose a fresh --tools directory")
    root.mkdir(parents=True)
    packages = root / 'downloads'
    packages.mkdir()
    for item in json.loads((HERE / 'tools.lock.json').read_text()):
        dest = fetch(packages, item)
        if item['kind'] == 'tar.xz' and areas(item) and set(areas(item)) <= set(LOCKED):
            for area in areas(item):
                unpack(dest, root / area, '-xJf')
        else:
            raise RuntimeError('unknown archive kind: ' + item['kind'])
    unpack(fetch(packages, xtensa_archive()), root / XTENSA, '-xJf')
    record = {'lock_sha256': sha(HERE / 'tools.lock.json'),
              'xtensa': {key: xtensa_archive()[key] for key in ('version', 'sha256')},
              'files': {area: inventory(root / area) for area in AREAS}}
    (root / 'installation.json').write_text(json.dumps(record, sort_keys=True) + '\n')
    print('installed pinned embedded environment at', root)


if __name__ == '__main__':
    main()
