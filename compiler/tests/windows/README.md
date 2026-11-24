# Windows execution

This directory's `check.py` emits with Linux `refine` and executes on
Windows. It selects every runtime fixture whose `targets:` names its
`--target`, `windows-x86-64` by default or `windows-arm64`, compiles each
at the four ordinary profiles, the two specialization profiles where the
fixture asks for them, and at the baseline and `x86-64-v3`, or `armv8-a`
and `armv8.1-a`, where its `levels:` names the higher level, and holds each
program's exit status, output and trap line to its fixture.

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

Windows arm64 has the same two jobs, `windows-arm64-emit` and
`windows-arm64-runtime`, the second on GitHub's `windows-11-arm` image.
Ubuntu packages no arm64 MinGW-w64, so the emission job takes the import
libraries from the `aarch64-w64-mingw32` directory of the pinned llvm-mingw
arm64 release, checked against its sha256 (D2348), and links with Clang 19
and LLD under the name `aarch64-w64-mingw32-clang`.

A fixture's `status` is what a POSIX parent reads, the low byte of what
`main` returned; Windows keeps all 32 bits, so the lane compares the low
byte. A failed check ends a Windows program with the trap instruction and
no handler, `ud2` on x86-64 and `brk #1` on arm64, whose exit code is
`STATUS_ILLEGAL_INSTRUCTION`, 0xC000001D,
and the lane requires exactly that for a fixture marked `traps: yes`.
Before it runs anything the lane sets the error mode its programs inherit,
so Windows Error Reporting neither opens a dialog nor waits on a trap.

The selection refuses a fixture naming the target that asks for what
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

On Linux, `nix develop` gives the drivers: its `x86_64-w64-mingw32-clang`
is the flake's Clang 19 for MinGW with LLD and nixpkgs' MinGW-w64 import
libraries, and its `aarch64-w64-mingw32-clang` the same Clang over the
pinned llvm-mingw release's arm64 import libraries. nixpkgs' Wine runs
x86-64 programs:

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

Nothing local runs an arm64 Windows program: Wine runs one only on an
arm64 host, which none of this project's Linux hosts is. `--target=
windows-arm64 --prepare-only` emits and links the whole corpus here, which
finds every refusal and link failure; the gate's arm64 runner is the only
execution verdict.

On a Windows host with llvm-mingw or MSYS2's CLANG64 toolchain, `refine`
itself is not yet built for Windows, so emission stays on Linux.

## Debugger sessions

`debug.py` runs the Windows debugger's sessions (D2292): LLDB as
llvm-mingw's release for Windows ships it, `lldb.exe` and `lldb-dap.exe`,
over the CodeView and PDB of `--debug=full` images. It compiles
`compiler/tests/freebsd/debug.ldn` at the four profiles and holds each
LLDB batch session to `compiler/tests/debugging/lldb_batch.py`'s verdict,
the one FreeBSD's and Linux's LLDB lanes hold: the source-line stop, the
frames, the locals and the caller's, the step out and the exit status. It
compiles `compiler/tests/dap/main.ldn`, the program every DAP lane debugs,
and runs `compiler/tests/dap/session.py`'s session through `refine dap`
relaying `lldb-dap.exe`, the program's own output among its checks.

The gate splits it as it splits the corpus: `windows-emit` adds
`--prepare-only` and keeps a second bundle, and `windows-debugger` runs it
on `windows-2025`, the LLDB sessions natively with `--prepared=DIR`, then
the `refine dap` session from WSL on the same runner with `--prepared=DIR
--dap`, since `refine` runs on Linux: WSL starts `lldb-dap.exe` as a
Windows program. The job fetches llvm-mingw's archive and checks it against
the sha256 `environments/pins.sh` names. The DAP program is compiled from
`/tmp/landin-windows-dap/main.ldn`, a path WSL recreates, because a
debugger finds a breakpoint's source by the path the program recorded.

`windows-arm64-emit` and `windows-arm64-debugger` do the same for
`--target=windows-arm64` on `windows-11-arm`, with llvm-mingw's arm64
release and the Linux arm64 release `refine` from `arm64-release-build`.
The runner enables WSL 1, which the setup action installs, but the
action's distribution is x86-64's, which WSL 1 on arm64 cannot run; the
job imports Ubuntu's arm64 base system from its pinned archive instead and
installs Python there (D2348).

Locally, Wine runs both, the Windows debugger debugging a Windows program
under Wine. `--lldb` and `--lldb-dap` take a command, so a wrapper that
runs the release's executables under Wine serves:

```sh
nix develop
dir=$(mktemp -d)
curl -fsSL -o "$dir/llvm-mingw.zip" \
  https://github.com/mstorsjo/llvm-mingw/releases/download/20261117/llvm-mingw-20261117-ucrt-x86_64.zip
sha256sum "$dir/llvm-mingw.zip"   # the sha256 environments/pins.sh names
unzip -q "$dir/llvm-mingw.zip" -d "$dir"
wine=$(nix build --no-link --print-out-paths nixpkgs#wine64)/bin/wine
for tool in lldb lldb-dap; do
  printf '#!/bin/sh\nexport WINEPREFIX=%s/wine WINEDEBUG=-all\nexec %s %s/llvm-mingw-20261117-ucrt-x86_64/bin/%s.exe "$@"\n' \
    "$dir" "$wine" "$dir" "$tool" > "$dir/$tool-wine"
  chmod +x "$dir/$tool-wine"
done
python3 compiler/tests/windows/debug.py \
    --refine="$PWD/compiler/ada/build/$LANDIN_BUILD_TAG/debug/bin/refine" \
    --lldb="$dir/lldb-wine" --lldb-dap="$dir/lldb-dap-wine" \
    --output="$dir/debugger"
```

LLDB's embedded Python writes a traceback at start under Wine, which is
harmless. Wine puts a recorded POSIX path on its `Z:` drive where Windows
puts it on the current one; `refine dap` reads either back (D2292). Wine is
development feedback: the gate's Windows runner is the verdict.
