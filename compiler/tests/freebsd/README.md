# FreeBSD hosted execution

This directory's `check.py` emits with Linux `refine`, Clang and a
checksum-locked FreeBSD sysroot, then executes in a FreeBSD VM. The gate reports runtime, native
LLDB and C ABI verdicts separately for amd64 and arm64, each job emitting
and executing its own lane; an emitted result is not an execution verdict.
The emulated arm64 runtime lane runs as two jobs, `--shard=1/2` and
`--shard=2/2`, which together are the lane: each takes alternate whole
fixtures of the selection, with all their levels and profiles, and the
first also checks the source verdicts. A shard cannot combine with `--case` or a
transferred payload. The sysroot and optional local VM base come from official 14.4 release files; hashes are in
[`environments/freebsd/lock.json`](../../../environments/freebsd/lock.json).

Each architecture's first runtime shard also compiles the production
publication, formatter and process C adapters with the guest's own `cc`
and runs their deterministic publication, cancellation, capture, private
directory and concurrent resource-registry controls.
The process controls include refusal before spawning under automatic child
reaping and preservation of the signal policy the OS actually installed.
`native-host-controls.log` retains the transcript. These check FreeBSD's
host system calls with the guest's C compiler; the compiler itself is built
and tested on FreeBSD by the host lane below.

The gate runs each lane in one GitHub-hosted Linux x86-64 job, which emits
and then boots a fresh VM from the locked 14.4 image, as a local run does: amd64
under KVM with host CPU passthrough, arm64 under QEMU's `max` CPU in system
emulation, because the hosted arm64 images expose no KVM.
A guest C probe confirms every additional selected
feature before any higher-level Landin program executes: CPUID plus XCR0
for x86-64-v3, and `elf_aux_info(AT_HWCAP)` for LSE, CRC32 and RDM. Lack of
support fails, with no skipped higher-level verdict. The emulated `max`
CPU's confirmed LSE supplies the capable arm64 execution lane.

Runtime and ABI selection reads fixture metadata and fails when empty.
Each program runs under `timeout 60` through `group_leader.c`, built
with the payload, which makes it the leader of a process group of its
own before it starts, as the test program and Darwin's parity runner
start every program; timeout(1) would otherwise lead the group, and
`runtime/posix-kill-group`, which signals its own group only when it
leads one, would stop with status 2.
The two I/O fixtures that use Linux `/sys` and `/dev/full` reuse the existing
portable C fault-endpoint adapter with ELF interposition names; ordinary paths
reach FreeBSD libc through its documented
[`RTLD_NEXT` search](https://man.freebsd.org/cgi/man.cgi?query=dlsym&sektion=3),
and source, errno, status and output oracles stay intact. Runtime
runs four ordinary profiles and two additional specialization profiles where
requested; it also checks applicable positive and negative source verdicts.
Fixtures naming the architecture's higher level run at default, explicit
baseline and higher level. The linked shift/atomic images must show BMI2 or
LSE only at the higher level, and the arm64 baseline must contain exclusive
loops. A separate assembler control refuses the higher instruction below its
level and accepts it at that level. Both architectures execute
`assembly-operands`; the compiler backend suite mutates an operand and requires
an IR register refusal under each FreeBSD description.

ABI peers are compiled separately as C objects, using FreeBSD headers, before
linkage with Landin assembly. Required sets cover scalar and floating values,
`layout(c)` records, imported and exported calls, callbacks and variadic bank
exhaustion. LLDB runs natively inside each VM at four profiles and checks source
stops, nested frames, callee and caller locals, step-out unwinding and final
status. The FreeBSD startup objects contribute debug ranges before Landin's
object, exercising section-relocated lexical ranges. At the same profiles it
runs the stack switch's session (D469), `runtime/stack-switch-frames`
stopped in a fibre and stepped through two switches: the guest's LLDB has no
Python, so its commands step a switch by the count of the switch routine's
instructions, which emission reads from the image with the LLVM object
tools, and `compiler/tests/debugging/switch_frames.py` holds the
transcript. Before the VM starts, emission also holds each switch image's
symbol table to naming the two routines' addresses by the routines alone
(D475): the lane's driver passes `-Wa,-L` to every compilation, the C peers
and the x86 GNU as included, which keeps the private `.L` labels, and every
link discards them again with `-Wl,--discard-locals`, as `refine`'s own
FreeBSD link does.

For a complete local lane, install Clang 19, LLD, LLVM object tools, GNU as,
and QEMU's x86-64 and arm64 system emulators with `qemu-img` and the arm64
UEFI firmware, then run (the arm64 guest's network device loads no option
ROM, since its firmware drives it, so Ubuntu's `ipxe-qemu`, which
`qemu-system-arm` only recommends, is not needed). The base system's
headers and libraries are unpacked by Python's own tar reader:

```sh
python3 compiler/tests/freebsd/check.py --arch=amd64 --kind=runtime \
    --refine=compiler/ada/build/linux-amd64/release/bin/refine \
    --output=/tmp/freebsd-runtime
```

On Linux x86-64, `nix develop` provides all of it, as the gate's jobs take
it: `clang-19`, `ld.lld-19`, `llvm-objdump-19`, `llvm-nm-19` and
`lldb-dap-19` from the flake's LLVM 19 under Ubuntu's names, GNU as, and
nix-packages' `qemu-system`, whose arm64 firmware the lane finds beside the
emulator. Its `clang-19` takes the bare compiler, with the wrapper's
resource directory, for a command that names a target or a sysroot, as
every FreeBSD compilation does, because nixpkgs' wrapper adds the host's
glibc to a FreeBSD build; a host program gets the wrapper, as
`bindings/test.py`'s `refine bindings` needs. amd64 needs read and write
access to `/dev/kvm`:

```sh
nix develop
python3 compiler/tests/freebsd/check.py --arch=arm64 --kind=runtime \
    --refine="$PWD/compiler/ada/build/$LANDIN_BUILD_TAG/debug/bin/refine" \
    --output="$(mktemp -d)/freebsd-arm64-runtime"
```

`LANDIN_FREEBSD_EFI` names another arm64 firmware file, when one is wanted.

The first run downloads and verifies the locked FreeBSD images and base
system into `~/.cache/landin/freebsd`. A lane runs every build and every
outcome before it reports: it prints how many passed, lists every failure
together, one line each, and exits 1 without a traceback; each failure's
whole message, and every transcript and status file, is in the output
directory and its `summary.json`.

The debugger lane's sessions are `compiler/tests/debugging/lldb_batch.py`'s,
and on a Linux host `nix develop` runs the same sessions against Linux images
with its LLDB, LLVM 19's as the guests' is (see
[the nix shell](../../../docs/environments.md#a-nix-shell-for-convenience)).
To ask which symbol LLDB gives an address in a FreeBSD image, emit the
payload with `--kind=debugger --prepare-only`, then in the shell

```sh
lldb --batch -o 'image lookup --address 0x401234' \
    /tmp/freebsd-debugger/bundle/switch-speed-auto
```

with the address a session's transcript printed; LLDB reads a FreeBSD ELF
image on Linux without running it.

Select `arm64`, `abi` or `debugger` for the other lanes. `--case=NAME` is exact
and visibly filtered; `NAME` is the fixture directory's bare name, such as
`network-connect-within`, without the class the other runners write before it. `--ssh-port=PORT` uses an existing development VM, logging in as root
at `127.0.0.1:PORT` with the caller's own SSH identity and known hosts;
`--prepare-only` emits and inspects a payload without executing it.
`--prepared=DIR --runner-ssh='ssh ... ci@freebsd-vm'` consumes it through the
supplied VM transport, verifies payload and executable hashes and the CI
revision, and uses guest sudo. Exact emission source paths resolve through a
temporary alias to the isolated payload. Guest identity, feature probes, source verdicts,
build/disassembly logs, debugger transcripts, output/status files and summary
hashes are retained by the gate for fourteen days. They are gate evidence,
not revision acceptance.

The [release image setup](https://github.com/freebsd/freebsd-src/blob/releng/14.4/release/tools/basic-ci.conf),
[auxiliary-vector API](https://man.freebsd.org/cgi/man.cgi?query=elf_aux_info&sektion=3)
and [arm64 capability definitions](https://github.com/freebsd/freebsd-src/blob/releng/14.4/sys/arm64/include/elf.h)
are FreeBSD's own contracts.

## refine on FreeBSD

[`host.py`](host.py) makes FreeBSD x86-64 the compiler's host. It boots a
fresh amd64 guest from the same locked image, unpacks the pinned GNAT and
GPRbuild that [`environments/freebsd/gnat.py`](../../../environments/freebsd/gnat.py)
built from source in such a guest ([the toolchain's record](../../ada/TOOLCHAIN.md#freebsd-built-from-source)),
clones the checkout's HEAD and, as an unprivileged user, builds `refine` and
its test program with `scripts/build.sh` and runs `scripts/test.sh` with the
arguments after `--`. There `refine`'s own target is `freebsd-x86-64`, so
fixture execution compiles, links with the base system's `cc` and runs the
hosted corpus with the `refine` the guest built, and the native adapter's
cases run on FreeBSD's system calls. The guest installs `python3`, `git`,
`bash` and `binutils`, whose `as` assembles x86-64's GNU assembly.

```sh
python3 environments/freebsd/gnat.py --arch=amd64      # once: about ten minutes on 16 processors
python3 compiler/tests/freebsd/host.py --arch=amd64 --output="$(mktemp -d)" -- --shard=1/2
python3 compiler/tests/freebsd/host.py --arch=amd64 --output="$(mktemp -d)" \
    --mode=release --package=DIR
```

The second builds the release compiler, makes
`landin-VERSION-x86_64-freebsd.tar.gz` and its debug archive with
`scripts/package.sh`, runs the unpacked `refine` in the guest with the GNAT
moved away, and copies both out with their checksums; the release workflow
publishes that archive. The test program's native FreeBSD lane differs from
Linux's in three places: it links with `cc` when the target's cross driver
is not installed, as `refine` does; it confirms `x86-64-v3` with
[`processor.c`](processor.c), since FreeBSD has no `/proc/cpuinfo`; and the
two fixtures that name Linux's fault endpoints run with
[`io_endpoints.c`](io_endpoints.c) preloaded. `host.py` clones HEAD, so
commit first; `--runner-ssh` takes an existing guest instead of booting one.
The gate runs the test program as two shards and the release leg, each in
its own guest (`freebsd-host-1`, `freebsd-host-2`, `freebsd-host-release`),
after `freebsd-toolchain` restores or builds the toolchain archive;
`freebsd-toolchain-main` does the same on every push to main, whose cache
every branch reads.

On FreeBSD arm64 the same lane runs with `--arch=arm64` in a guest under
KVM on an arm64 host, where `refine`'s own target is `freebsd-arm64` and
the base system's Clang assembles as well as links. GitHub's arm64 runners
have no KVM, and building GCC under emulation outlasts a job, so this is a
named run rather than a gate job. Both scripts take that guest with
`--runner-ssh`, the SSH command that reaches it as root; the toolchain
archive's digest is the same either way:

```sh
python3 environments/freebsd/gnat.py --arch=arm64 --runner-ssh="$GUEST"   # once: about ten minutes on 20 processors in 8 GiB
python3 compiler/tests/freebsd/host.py --arch=arm64 --runner-ssh="$GUEST" --output="$(mktemp -d)"
python3 compiler/tests/freebsd/host.py --arch=arm64 --runner-ssh="$GUEST" --output="$(mktemp -d)" \
    --mode=release --package=DIR
```

The guest is booted fresh from the locked image first, and each run
provisions it again. The last makes `landin-VERSION-aarch64-freebsd.tar.gz`,
which no release publishes yet.
