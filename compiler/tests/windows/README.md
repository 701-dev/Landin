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
nothing but Python, this file's script and the bundle. An emitted bundle is
not an execution verdict.

A fixture's `status` is what a POSIX parent reads, the low byte of what
`main` returned; Windows keeps all 32 bits, so the lane compares the low
byte. A failed check ends a Windows program with the trap instruction and
no handler, whose exit code is `STATUS_ILLEGAL_INSTRUCTION`, 0xC000001D,
and the lane requires exactly that for a fixture marked `traps: yes`.
Before it runs anything the lane sets the error mode its programs inherit,
so Windows Error Reporting neither opens a dialog nor waits on a trap.

The selection refuses a fixture naming `windows-x86-64` that asks for what
the lane does not run yet: C peers, a C library (`link:`), library
directories, files, arguments' files or standard input. A Windows program
has no hosted provider yet, so a fixture importing `hosted/` or the POSIX
platform modules does not name the target.

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
`--runner`. A lane runs every build and every outcome before it reports,
then lists every failure, one line each, and exits 1; each transcript,
status file and `summary.json` is in the output directory.

On a Windows host with llvm-mingw or MSYS2's CLANG64 toolchain, `refine`
itself is not yet built for Windows, so emission stays on Linux.
