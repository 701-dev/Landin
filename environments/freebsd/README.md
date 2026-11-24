# FreeBSD VMs

[`vm.py`](vm.py) verifies official release image and base-system archives
against [`lock.json`](lock.json), extracts a private cross sysroot and boots
an architecture-specific QEMU guest from a fresh overlay. It never modifies
the downloaded disk image. This is test provisioning, outside the
compiler's `Landin.Platform` host boundary.

The BASIC-CI image admits root over SSH with an empty password, so the
guest is admitted before any port reaches it. QEMU starts it with no
forwarded port, its serial console and monitor on sockets in a directory
only the caller can enter, outside the retained output. At the console's
root login the supervisor installs a key made for this boot as root's only
authorized key, turns the guest's password and empty-password logins off,
checks what `sshd -T` then says, and reads the host key the guest made at
its first boot. Only then does the monitor forward a loopback port, and the
client logs in with that key alone and holds the guest to that host key, so
another local user who takes the port or reaches it can neither enter the
guest nor answer for it. The VM is torn down and the key deleted on success
or failure; `console.log` keeps the console transcript, which holds only
public keys.

Each lane raises the guest's data-size ceiling to at least 4 GiB and lifts
the process's soft data limit. The unchanged displacement-limit fixture declares
a 2 GiB global array; FreeBSD arm64's default 1 GiB ceiling refuses that
executable before it reaches `main`. This reserves virtual address space,
not 4 GiB of guest RAM. A temporary ceiling change is restored after the lane.

The gate boots these fresh guests itself, one per lane on a GitHub-hosted
Linux x86-64 job: amd64 under KVM, arm64 under system emulation, since the
hosted arm64 images expose no KVM. The jobs cache the image and base
archives under the lock's digests, which `vm.py` verifies on every use;
the lanes of `compiler/tests/freebsd/check.py` compile no Landin in FreeBSD.

[`gnat.py`](gnat.py) builds the pinned GNAT and GPRbuild from source in
such a guest, with [`gnat/build.sh`](gnat/build.sh) and the patches beside
it, and keeps the result as one archive in the cache under a digest of
its inputs ([the toolchain's record](../../compiler/ada/TOOLCHAIN.md#freebsd-built-from-source)).
`compiler/tests/freebsd/host.py` unpacks it in another guest, builds
`refine` there and runs its test program
([refine on FreeBSD](../../compiler/tests/freebsd/README.md#refine-on-freebsd)).
`vm.boot` takes the guest's memory, processors and a larger disk for
those builds; the lanes keep 2 GiB and two processors.

`compiler/tests/freebsd/check.py --prepared --runner-ssh` still executes a
transferred payload in an existing guest, as the self-hosted controllers
did until 2026-10-16. Raw SSH uses the caller's identity and checked host
key. Guest sudo permits an isolated payload directory, exact source-path
alias, resource-limit setup and cleanup. A real directory at the source
alias is refused. The alias and payload are removed on success and failure.

See the [execution lanes](../../compiler/tests/freebsd/README.md) for commands,
feature confirmation, verdicts and retained evidence.
