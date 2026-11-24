# Windows x86-64 execution

This directory's `check.py` emits with Linux `refine` and executes on
Windows. It selects every runtime fixture whose `targets:` names
`windows-x86-64`, compiles each at the four ordinary profiles, the two
specialization profiles where the fixture asks for them, and at the
baseline and `x86-64-v3` where its `levels:` names the higher level, and
holds each program's exit status, output and trap line to its fixture.

The gate splits the lane in two jobs. `windows-emit` runs on Ubuntu with the
checked release compiler and `--prepare-only`, linking with Clang 19, LLD
and Ubuntu's MinGW-w64 import libraries (`mingw-w64-x86-64-dev`) under the
name `x86_64-w64-mingw32-clang`, which is llvm-mingw's; `windows-runtime`
runs the bundle with `--prepared=DIR` on GitHub's `windows-2025` image, with
nothing but Python and the bundle, which carries this directory's script and
the three it imports at their own paths. That job checks nothing out: the
tree holds a fixture path with a double quote, which Git for Windows refuses
even outside a sparse checkout. An emitted bundle is not an execution
verdict.

A fixture's `status` is what a POSIX parent reads, the low byte of what
`main` returned; Windows keeps all 32 bits, so the lane compares the low
byte. A failed check ends a Windows program with the trap instruction and
no handler, whose exit code is `STATUS_ILLEGAL_INSTRUCTION`, 0xC000001D,
and the lane requires exactly that for a fixture marked `traps: yes`.
Before it runs anything the lane sets the error mode its programs inherit,
so Windows Error Reporting neither opens a dialog nor waits on a trap.

The selection refuses a fixture naming `windows-x86-64` that asks for what
the lane does not run yet: C peers, a C library (`link:`) or library
directories. The runtime job checks nothing out, so the bundle carries the
files a fixture names in `run_files` and `stdin` under `inputs/`, and a
program is given the copies. Each outcome runs in a working directory of
its own under the bundle's `work/`, holding copies of those files too,
since the profiles of one fixture run at once and a fixture may make files
where it runs (D2273).

The hosted providers are written over `platform/windows` on Windows
(D2270 to D2272), so a fixture over `hosted/` names the target unless it
needs POSIX itself: a fixture that imports `platform/posix`, starts
`/bin/sh`, opens `/dev/null` or holds an errno's POSIX number does not.
A Windows-only fixture, `runtime/windows-run-programs`, starts the command
processor in place of a shell.

## Running it locally

On Linux, `nix develop` gives the driver: its `x86_64-w64-mingw32-clang`
is the flake's Clang 19 for MinGW with LLD and nixpkgs' MinGW-w64 import
libraries. nixpkgs' Wine runs the programs:

```sh
nix develop
nix shell nixpkgs#wine64 -c python3 compiler/tests/windows/check.py \
    --refine="$PWD/compiler/ada/build/$LANDIN_BUILD_TAG/debug/bin/refine" \
    --runner=wine --output="$(mktemp -d)/windows"
```

The lane makes a Wine prefix of its own under the output directory and
turns off Wine's debugger there, which Wine would otherwise start for every
trap, and it leaves out the one line Wine writes when a trap ends a program,
which Windows does not. Wine is development feedback: the gate's Windows
runner is the verdict. `--case=NAME`, the fixture directory's bare name,
repeats and is visibly filtered; `--prepare-only` and `--prepared=DIR`
split the stages as the gate does, and on Windows the second needs no
`--runner`. A lane runs every build, and every outcome of the builds that
succeeded, before it reports, then lists every failed build and every
failed outcome, one line each, and exits 1; `--prepare-only` fails on a
failed build after writing the rest. Each transcript, status file and
`summary.json` is in the output directory.

On a Windows host with llvm-mingw or MSYS2's CLANG64 toolchain, `refine`
itself is not yet built for Windows, so emission stays on Linux.

## Microsoft's link

`--link=microsoft` runs the same corpus through Microsoft's toolchain, the
optional second one (D2327). refine cannot run where Microsoft's linker
does, so emission gives refine a recording driver named
`x86_64-pc-windows-msvc-clang`, the name that selects the policy; it keeps
each assembly and the link command refine chose, beside the executables'
places in the bundle. Execution runs each command with `--driver`, a
Clang, before it runs the program, and writes Clang's account of the link
to `LABEL.link.log`. In the gate `windows-emit` prepares this bundle too
and the `windows-microsoft` job runs it on `windows-2025` with the
runner's Clang and `--expect-linker=link.exe`, so a link that reached any
linker but Visual Studio's fails, and `summary.json` names the driver's
version and every linker that ran.

Locally, LLVM's `lld-link` stands in for `link.exe` and MinGW-w64's
import libraries for the Windows SDK's. `nix develop` puts `lld-link`
beside `clang-19`, which is the bare Clang when a command names its
target, as refine's does here; nixpkgs' `clang` is a wrapper for Linux
that adds options the MSVC target refuses. `lld-link` reads an import
library by the name Microsoft gives it, `NAME.lib`, from the directories
`LIB` names, so a directory of copies serves:

```sh
nix develop
lib="$(mktemp -d)"
for name in kernel32 bcrypt synchronization ws2_32 iphlpapi; do
    cp "$(x86_64-w64-mingw32-clang -print-file-name=lib$name.a)" "$lib/$name.lib"
done
nix shell nixpkgs#wine64 -c env LIB="$lib" python3 compiler/tests/windows/check.py \
    --refine="$PWD/compiler/ada/build/$LANDIN_BUILD_TAG/debug/bin/refine" \
    --link=microsoft --linker=lld --driver=clang-19 --runner=wine \
    --output="$(mktemp -d)/windows-microsoft"
```

The names are the `linker.library` lines of `platform/windows`. This
checks refine's link command, the assembly under Clang's MSVC target and
the programs, but not Microsoft's linker, which only the gate's Windows
runner has.
