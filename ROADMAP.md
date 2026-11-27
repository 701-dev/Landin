# Landin roadmap

## Authority and scope

`spec.md` decides the language and `tour.md` explains it. This file is the
sole authority for open work: its phases, lanes, dependencies and gates. A
work item cannot overrule the specification. A semantic change updates
`tour.md` or `spec.md`, the fixtures that pin it and this file together.

The first roadmap, R0 to R7, built the bootstrap compiler to a
feature-complete pre-v1 slice, last at commit `335b0814`. The second, R8 to
R16, took it to an editor, more hosted targets, the microcontrollers people
buy, a library split along the capability line, concurrency and the start
of measured optimization; its text is in the history, last at commit
`d27308107`. Its R16 continues here. Its R15,
Windows, was never started; its three items are retired and its content is
rewritten as R21 for today's library, second Io and threads.

This roadmap makes the language smaller and the tools around it ordinary:
the project's own process first, then `refine` split into commands, a
breaking simplification of the language, a review of the standard library,
Windows, the library a newcomer expects to find, and the install routes
that make a release quick to reach. Optimization runs beside all of it.

Outside it, and staying outside: a build tool and package manager, the
Companion tool and ecosystem family's; self-hosting and separate
compilation, Scale and self-hosting's; a browser or WebAssembly target;
dates and times in the library; and every release or version decision, each
of which needs an explicit decision of its own. Landin does not assume
SemVer.

The stated 32 TB hosted endpoint remains an unverified goal; what it
measures and what would prove it are still open, and nothing here claims it.

Work item, register and question identities are cited in this file, in the
register and question files, in the inputs under `roadmap/inputs/`, and
nowhere else, save the status pointer
`README.md` and `handoff.md` carry. `check.py` refuses such a citation
anywhere else. `docs/capabilities.md` is the capability inventory and
`README.md` summarises it; `Done:` paragraphs record evidence, not a second
summary.

## Mechanics

**Identities.** Phases run from R15, where the second roadmap's numbering
left off, in identity order without a gap, and each ends in one gate. A
phase retired before it started, as R15 was, keeps only its heading,
marked `(retired)`, and a paragraph saying why: no item and no gate.
Items are `R19.10`, `R19.20` and so on, spaced in tens; work found between
two items takes a unit identity, the earlier item's number plus one, so 21
after 20. Identities are never reused or renumbered, the earlier
roadmaps' included. Every item has
one status line, one dependency line and its exit evidence:

```text
Status: planned
Depends on: R17.10

```

A status is `planned`, `active`, `blocked` or `complete`; `blocked` carries
one `Blocked because:` line, which no other status keeps. Any item whose
dependencies are complete may be `active`, several at once, and a complete
item's dependencies are complete. There are no dates, estimates or
versions here.

**Lanes.** Work runs in the lanes the execution order declares. The serial
lane is one item at a time. Its item is the first in execution order that
is `active`, or `planned` with its dependencies complete, a blocked item
passed over, and `README.md` and `handoff.md` name it and no other: as
current work while it is active, as the next item while it is planned. An
item of a serial phase whose dependencies are complete may start beside
it, as R17.50, which depends on nothing, ran beside R17.10 to R17.30; it
is `active` while it runs, and the pointers keep naming the serial lane's
item. The site's front page shows that item first and every other active
item beside it. The continuous lane holds R16's and R22's continuous
items. Each of the two phases has a basis in the serial lane, R16.10 and
R22.80; its continuous items take the next ten after the last basis item
and count up by one, R16.20 onward and R22.90 onward. Each depends only on
its phase's basis, may run beside anything, and is never the next item;
any number of them may be active. A phase that declares a
breaking window (R19, then R20) keeps its serial items on one integration
branch and promotes them once, at its gate; a continuous item lands on
main meanwhile and the branch takes it. The phase declares it in one line
of its opening paragraphs, `Window: r20-integration`, naming the branch;
`scripts/item.py` starts the phase's items from it and lands them on it in
place of main, after their push gate and without boards, which the
window's one promotion dispatches on the integrated tree.

```text
Execution order: R17, R16.10, R18, R19, R20, R21, R22.10, R22.11, R22.13, R22.20, R22.21, R22.22, R22.23, R22.24, R22.26, R22.27, R22.28, R22.29, R22.30, R22.31, R22.32, R22.33, R22.34, R22.35, R22.36, R22.37, R22.38, R22.40, R22.50, R22.60, R22.61, R22.62, R22.63, R22.12, R22.14, R22.15, R22.16, R22.17, R22.18, R22.19, R22.70, R22.71, R22.72, R22.73, R22.74, R22.75, R22.76, R22.80, R23
Continuous: R16.20 onward, R22.90 onward
```

**Gates.** A phase's gate cannot be claimed until all its items have their
exit evidence, its continuous items apart. R16's gate is different: once
its basis is complete it is a standing invariant every later push must
keep, not a milestone; R22's is claimed with its serial items and then
holds the library's baselines in the same way. An item is
complete when its exit evidence exists: the complete gate passed on the
completing commit and, for a claim about a host the gate does not run, a
named run recorded in the item. It then gets a short `Done:` paragraph; the
reasoning goes in the commits and in `spec.md`'s register of decisions.

**Authority.** An item's agent may push its candidate, promote it to main
once its gate has passed, and remove its worktrees and branches, without
asking again. The session that runs the roadmap, or a train's integrator,
may also promote other items' gated candidates inside a train: merged into
the promotion token's holder, they land as one tree on its own gate and
boards (`docs/process.md`, "A train"). An item opts out with one line,
`Promotion: maintainer`, which returns that step to the maintainer and
keeps it off every train; `check.py` refuses any other spelling. Releases
and versions are never covered.

**The register.** A row is only for what outlives the item that met it
and waits for a trigger. A finding the item fixes is named in its commit
message and its `Done:` paragraph, not filed. Each row is one file,
`roadmap/register/`, its identity the file name: a front matter
block of `key: value` lines, then a body of a few lines at most saying
what stands and what would complete it. The keys are `kind` (`limit`,
`watch`, `defect`, `proposal` or `usability`), `family`, `status` (`open`,
or `scheduled` with the items that take it on), `opened` (a date),
`activation`, and `effort` and `impact`, each `S`, `M` or `L`. `check.py`
validates them. `roadmap/register.md` is generated from the files and is
never edited.

A row moved from the second roadmap keeps its identity, SR-n, R551-n or
another. A new row takes the next SR number from the allocation script
R17.10 provides; two branches that take the same number collide as an
add/add conflict on the file, which is the detection, and the integrator
renumbers the later one. The script is `scripts/register_next.py`;
`--file` writes the row with its keys to fill in. A retired or completed
row has no file: it is deleted in the commit that says why, and the
history keeps it; `register_next.py --delete` removes the file, puts the
row's citations here in code spans and regenerates the page. There is no
departures list, and the second roadmap's
retired rows were not migrated.

A moved row's `opened` is the date it first appeared, which the migration
script takes from the history.

An item's agent may delete a row its change fixed, or one that duplicates
another, naming the evidence in the commit. Retiring a row as not worth
doing, and anything a row asks the maintainer to choose, is a question and
waits for the maintainer. An item that meets a row without triggering its
activation leaves the row as it is: its activation names what triggers
it, not the items that did not.

The register holds at most 60 open rows; a scheduled row does not count,
and a row may be scheduled only on an item whose text names it. A row that has stood through ten
completed items without being scheduled is reviewed at the next item's
close: scheduled, retired, or kept with one sentence saying why, a body
line beginning `Kept:`, which restarts its count. At the cap,
an item cannot close until it has brought the count under it.

For a moved row the ten completed items count from the exchange, since the
sweep before it has just reviewed every live row; for a new row, from its
filing. Only an item completed after the filing or the `Kept:` line on
its own line of history, or after the merge that joined the two, counts,
so a window's branch taking main, or main taking the window, ages no row
by the merge alone; a `Kept:` line written in resolving a merge restarts
the count as one in an ordinary commit does.

**Questions.** A decision only the maintainer can take is a question, one
file under `roadmap/questions/`, Q-1 onward, never a register row and never
a question asked only in a report or a chat. The file begins with the
question as its heading, `# Q-7 — ...?`, and the line `Asked by R17.50 on
2026-11-17.`, or for work that is no item what the work is, `Asked by the
register sweep of 2026-11-21 on 2026-11-21.`, then what the maintainer
needs to decide it, and four
paragraphs each opening with its label in bold: `Options:`, a list
numbered from 1 with at least two; `Recommendation:`; `Default until
answered:`, which says what the default is in words and not by its option
number alone; and `What waits on the answer:`, the work it holds up or
`nothing`. The asker carries on with the default and with everything the
answer cannot change. A question closes with one paragraph,
`**Answer (YYYY-MM-DD, the maintainer):**`, and, where the answer is a
rule, a decision in `spec.md`; a decision reopened is a new question.
`check.py` refuses a file without these parts, a question cited that has
no file, and a question's identity outside the roadmap's files, and the
generated `roadmap/register.md` lists the open ones with their defaults
and what waits, the table a report to the maintainer quotes. A decision an
item's text gives to its own run, as R18.10 answers the command
inventory's questions, becomes questions when that item starts.

The gate is a safety net rather than a verdict: green says a tree passed
there, and no item claims more.

## R15 — Windows (retired)

Never started. Its three items are retired unused; their content is R21's,
and nothing cites them. This phase has no gate; it is the one
phase the gate rule exempts.

## R16 — Optimization

Measured first, and then only where the measurement says. R16.10 is the
basis and runs in the serial lane right after R17; R16.20 onward are
continuous.

### R16.10 — Measure generated code

Status: complete
Depends on: R17

Record the size and time of the same workloads for every supported target,
each CPU feature level `Landin.Targets.Levels` gives it (`refine targets`
lists them), and all nine combinations of `--optimize=none|size|speed` and
`--specialize=off|auto|all`, and hold every later change to them in the gate.
The level list is read from the compiler, never written out here.

The first deliverable is the measurement contract, reviewed before any
baseline is recorded:

- **Workloads.** A hosted set, the five ports of `docs/benchmarks.md` and a
  fibre and a thread program, which pay the prologue's stack check; and a
  firmware set that fits the 32 KiB reference, with prototype 5's
  counterpart on the firmware profile it fits. Each keeps the oracle its
  fixture already has, and a target runs the set its kind allows.
- **Size** is the exact bytes of each section of the linked image, read from
  the image: the build report gives a firmware image's totals, and its
  routine counters count emission sites, not bytes. Emission is deterministic, so size has no tolerance: growth
  fails unless the commit declares the new baseline.
- **Time** depends on where the code runs. On a native runner it is the
  median wall time over several fresh copies of each executable, since
  placement alone was found moving it by up to 50%. On the rig's boards
  it is the core's cycle counter over a RAM run where it has one (DWT CYCCNT on
  the M7 and M33, `mcycle` or the vendor's counter on RISC-V, CCOUNT on
  Xtensa), and a SysTick or timer count where it does not, as on the
  RP2040's M0+; the runner table names each board's.
  Under emulation alone (RV64, FreeBSD arm64 and the QEMU firmware lanes) it
  is a deterministic instruction count, or the target records size alone;
  an emulator's wall time does not measure the code. Each class's tolerance
  comes from a noise study recorded on its runner before the gate enforces
  it.
- **Runners.** A table names the runner and the class of every
  target/level pair. A level no runner executes, `x86-64-v4` if the hosted
  runners lack AVX-512, is a `limit` row with its activation, never a
  skipped measurement or a lower level in its place.
- **Baselines** are committed data keyed by target, level, firmware profile
  where there is one, optimization profile, workload and runner class, with the runner's CPU model and image. A candidate is
  compared with its base commit's baselines, never its own; a commit that
  changes one names each key it changes, and a changed runner class
  re-baselines rather than fails.
- **Cost.** Configurations whose emitted bytes are identical are measured
  once and cite the identity. Size runs on every push; time runs on the
  schedule and on dispatch: the schedule and a `scope=boards` dispatch run
  the boards, documents and scripts but no software lanes today, and this
  item adds the timing jobs to them. A pilot over the whole matrix records its minutes, its
  jobs against the account's concurrent-job limits and its noise before the
  thresholds are enforced.

The build report (D791) and `scripts/quality.sh` are the starting point; the
new parts are time, the matrix and the baselines. A report format change here
also says where a program's compile time goes among its sources, and gives
the build and depth reports one name for each frame quantity. A measured code-quality cost attributable to
assembly's fixed memory effect is recorded against `SR-09` before any narrower
effect is proposed. Its ranked list answers the activations of `SR-231`,
`SR-387`, `SR-596`, `SR-869` and `SR-1023`, and measures x86-64's two-instruction
reach of a thread instance. This takes on `SR-996` and `SR-275`, and carries the
fresh-copy requirement. The instruction count under emulation is the
per-routine cost report `SR-1267` asked for.

Exit evidence: the contract, the runner table and committed baselines for the
whole matrix; the gate failing a deliberately larger image and a deliberately
slower one in each execution class and passing an unchanged one; the pilot's
recorded cost; and a ranked list of each backend's largest measured costs,
from which R16.20 takes its scope.

Done: `docs/measurement.md` is the contract, reviewed twice by an
independent agent before any baseline (D1375-D1382), with its runner table
as `compiler/tests/measure/runners.json`, which `measure.py runners` holds
to `refine targets --json`, now giving each level's features (D1377).
Every push holds each allocated section of 1,566 configurations' images,
every target, level and profile, to committed baselines exactly, and the
instructions of 468 under QEMU, RV64's and Cortex-M's; the schedule and
any dispatch time the hosted workloads in pairs on one processor and the
firmware set by each board's counter. The candidate `25159f4a8` passed its
[gate](https://github.com/701-dev/Landin/actions/runs/44255590398) and
[boards](https://github.com/701-dev/Landin/actions/runs/44259826354),
timing included, and
[main's gate](https://github.com/701-dev/Landin/actions/runs/44265284174);
two never-promoted branches cut from it failed: a larger image
([run](https://github.com/701-dev/Landin/actions/runs/44265298161)) on every
size key of Linux, firmware and FreeBSD and every instruction count, and a
slower one ([run](https://github.com/701-dev/Landin/actions/runs/44265297675),
[dispatch](https://github.com/701-dev/Landin/actions/runs/44265301923)) on
the same and on wall time, 126 of 126 pairs on x86-64, 84 of 84 on arm64 and
62 of 66 on Darwin. Its board legs never ran, since `board-bundles` refuses
a changed image on record drift first; a named rig run timed it on the
ESP32 and STM32H753, 108 of 108 configurations failing by 1.26 to 12.1
times where `a9e880430` passed all 108. On the demonstration branches
Darwin's host suite fails before its size step. `compiler/tests/measure/
pilot.json` records the cost, three jobs a push and three a timed run, and
the noise studies are under `compiler/tests/measure/noise/`: none in size
and instructions once RV64 runs in a reserved address space, per port in
cycles, and up to 1.085 in an A/A wall run, so a pair past its tolerance is
timed again. `compiler/tests/measure/findings.md` is the ranked list:
arm64's allocator unused at `size`, RV64's far jumps, Cortex-M's homes
addressed through r6, then allocation. `SR-09` and `SR-1267` are settled;
`SR-596`, `SR-869`, `SR-231`, `SR-996`, `SR-577`, `SR-583` and `SR-1268` are R16.20's;
`SR-275`, `SR-387` and `SR-1023` are restated with their figures, and `SR-1302`
records the Xtensa reference's boot layout. Findings fixed on the way: the
stack report names its frame quantities as the build report does (D1380),
the stage report gives each source's scanning and parsing (D1381), and an
RV64 count no longer depends on its environment.

### R16.20 — Register allocation

Status: complete
Depends on: R16.10

Keep values in registers where R16.10's ranked costs show stack traffic
leading. R16.10's ranked list (`compiler/tests/measure/findings.md`) orders
the work by measured gain: arm64's existing allocator at `size`, RV64's near
jumps within a routine and then its allocation, Cortex-M's stack homes
addressed from `sp` and then allocation through r0 to r7, then RV32 and
Xtensa. Whether one allocator over `Landin.IR.Liveness` serves every backend
is decided first. This item then takes the two costs that change no
firmware image: arm64's allocator at `size`, on Linux, Darwin and FreeBSD
alike, and RV64's near jumps. The rest is split by backend into R16.21 to
R16.24, each with its backend's rows, so that the board records are made
again only by the items that change a firmware image.

Exit evidence: a direct test of `Landin.IR.Liveness`'s intervals, its
conservative whole-routine fallback included, before any allocator change that
relies on it; measured improvement for affected target/level/profile
combinations against their matching R16.10 baselines, with unchanged behavior,
ABI and debugger evidence. Every supported combination remains under the same
size and time regression gate, including unaffected levels and profiles.

Done: D1403 keeps `Landin.IR.Liveness` the one analysis and placement each
backend's own; `ir opt/slot intervals`, `slot interval fallback` and `loop
depths` test it directly, committed before the allocator change. arm64 runs
its allocator at `size` (D1404): over the seven hosted workloads at
`size-auto` `.text` falls about a third on Linux, Darwin and FreeBSD
(497,380 to 327,272 bytes at Linux armv8-a), and under QEMU mandelbrot
executes 0.30 of its instructions, fannkuch-redux 0.37, fasta 0.38 and
binary-trees 0.66. RV64 jumps near within a routine provably inside JAL's
reach (D1405): `.text` 19.9% smaller at `speed`, counted instructions 9.5%
to 20% fewer. No firmware, x86-64 or arm64 `speed` image changed; the build
modes agree and the scaling bound holds. The candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/44407003576) and
[boards](https://github.com/701-dev/Landin/actions/runs/44413857908).
R16.21 to R16.24 took the other backends and their rows, `SR-586` and
`SR-1302` among them. Findings fixed on the way: LLDB's `GetValueAsSigned`
read a zero-extended `i32` in a register whole, so the Darwin sessions read
integers at their type's width; a failed Darwin LLDB session keeps its
transcripts; a wall pair whose candidate image is the base's is no longer
timed, and each timed image runs once untimed first, since macOS's vetting
of a program's first launch failed two pairs on a single sample;
`measure.py plugin` names a program for a user-mode QEMU; and
`measure_costs.py routines` takes `--library`.

### R16.21 — RISC-V register allocation

Status: complete
Depends on: R16.10

RV64 and RV32 keep every value in a stack home: R16.10 measured a report
share of 37.8% at rv64gc and 53.9% at rv32imc, speed-auto, and RV64
executing five to seven times arm64's instructions on the same runs. Keep
their values in registers over `Landin.IR.Liveness`, as D1403 has each
backend place its own, and with them RV32's 64-bit values, copied through a
scratch home pair before every store to their own home. Its placement is the
first written since D1403: where it agrees with arm64's it is shared rather
than written again, which answers `R551-16`'s activation for the backends'
shared code, and the row stays open for the stage closures. RV32 changes the
firmware images of three boards, whose records are made again.

Exit evidence: RV64's instructions and both targets' sizes measured lower
than their R16.10 baselines, RV32's cycles on the boards no slower, with
unchanged behavior, ABI and debugger evidence and the board records made
again.

Done: D1503 holds RISC-V's slots and values in registers at `size` and
`speed`. Selection names nearly every integer register as scratch, so a
routine is emitted once with every value in its home while what each
position writes is recorded; locations take x10-x17, x9, x18, x19 or x22
only where nothing writes them over their intervals, with arm64's placement,
and the second emission is checked against the plan, keeping the first if
any write meets a held register. RV32 holds eight-byte values in register
pairs, and held operands are read in place. The usage both allocators read
is `Landin.Backend.Placement`, which answered `R551-16`'s activation for the
backends' shared code; arm64's output is byte-identical. Over the seven
hosted workloads RV64's `.text` falls 15.8% at `size` and 19.4% at `speed`,
and under QEMU speed-auto executes 0.55 of mandelbrot's instructions, 0.67
of fasta's, 0.72 of fannkuch-redux's and 0.82 of binary-trees'; RV32's
firmware `.text` falls 17.5% at `size` and 18.4% at `speed`. On the
ESP32-C3, ESP32-C5 and Pico 2's Hazard3 no configuration is slower: at
speed-auto their cycles fall to 0.56-0.82 of R16.10's for the integer
workloads, 0.87-0.93 for SipHash and 0.97-0.98 for mandelbrot, whose
soft-float helpers dominate. Their six records were made again on the rig.
The RV64 GDB sessions, the RV32 lanes and RV64's fixtures pass, the build
modes agree and the scaling bound holds on the host and on RV64. The
candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/44452396582) and
[boards](https://github.com/701-dev/Landin/actions/runs/44459720484).
Findings fixed on the way: the RV64 GDB session's source still assumed a
dead argument stays readable, and is now the LLDB lanes' source, whose
argument is read after the call; `runtime/directory-memory` now fits the
RV32 lanes' 32 KiB and at `size` overruns their 4 KiB stack, recorded as a
D698 lane limit. `SR-1363` files what remains largest, selection's flag
emulation, 22% of RV64's instructions.

### R16.22 — Cortex-M register allocation

Status: complete
Depends on: R16.10

Cortex-M keeps every value in a stack home and forms each home's address in
r6 first: at armv6-m speed-auto 35.2% of the firmware set's instructions are
stack loads and stores and 30.5% form their addresses, and the Thumb-2
levels select Thumb-1. First the homes are addressed from `sp` directly,
then values are allocated through r0 to r7, then at the Thumb-2 levels the
high registers and Thumb-2's forms. This takes on `SR-581`, `SR-582`, `SR-583`
and `SR-584` at the Thumb-2 levels; `SR-596`'s float selection in VFP
registers, measured on `runtime/firmware-mandelbrot` with the AN500
description; `SR-869`'s short `u64` routines on armv6-m; `SR-231`'s atom `match`
arms; `SR-996`'s counterpart against 32 KiB; `SR-577`'s float saves beside an
assembly block; and `SR-586`'s local labels, since every Cortex-M board record
is made again here once.

Exit evidence: the firmware set's size and instructions measured lower than
their R16.10 baselines at every level, the cycles on the boards no slower,
with unchanged behavior, ABI and debugger evidence and the board records
made again.

Done: Cortex-M reaches its homes from sp, a value's home a word written
zero-extended (D1563); at the Thumb-2 levels it branches with one B and
makes constants with MOVW and MOVT (D1564, `SR-584`); a call loads its
scalar register arguments directly (D1565); a comparison only its branch
reads sets that branch's flags (D1566); and at `size` and `speed` it holds
slots and values in r4-r7, r3 and r1 where its first emission writes none of
them over their intervals, over `Landin.Backend.Placement`'s usage, checking
the second emission against the plan (D1567). A kept comparison at the
Thumb-2 levels is an IT block (D1568, part of `SR-582`); code labels are
assembler-local (D1569, `SR-586`), held by the firmware lane's
`unused-import` case, which the starting compiler fails; a routine saves
only the run of d8-d15 its blocks declare (D1570, `SR-577`); and a far
Thumb-1 branch to a trap is a BL (D1571). The firmware set's `.text` falls
to 0.71 of R16.10's at armv6-m `size` and `speed` and 0.57 at the Thumb-2
levels, `none` falling too, and under QEMU speed-auto executes 0.28 to 0.88
of its instructions, size-auto 0.29 to 0.95 and none 0.56 to 0.95. On the
boards no configuration is slower: at speed-auto the RP2040 runs 0.27 to
0.96 of R16.10's cycles, the RP2350's M33 0.29 to 0.89 and the STM32H753
0.23 to 0.83. Prototype 5's counterpart links within the constrained
reference's 32 KiB at `size`, 32,080 bytes, and `speed` (`SR-996`), and
twelve runtime fixtures whose images did not fit it run on Cortex-M0 at
every profile. The seven Cortex-M board records were made again on the rig.
The programs and corpus lanes, the unit suites and the fixtures pass, the
build modes agree and the scaling bound holds. The candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/44578956148) and
[boards](https://github.com/701-dev/Landin/actions/runs/44584549572). R16.27
takes what is left: `SR-581`, `SR-582`'s CBZ, `SR-583`, `SR-596`, `SR-869` and `SR-231`,
each with today's figures. Findings fixed on the way: the devices lane's
cached consumer read a register's address only from literal words; and
`runtime/directory-memory`, which now fits the reference at every profile,
overruns its 4 KiB stack at `none`, which the reference's own
`profile_limit` row could not record, so D698 is amended to let it; the RV32
lanes keep limits at `none` for ten of the twelve, whose RV32 code this item
does not change.

### R16.23 — Xtensa selection

Status: complete
Depends on: R16.10

Xtensa's backend writes RISC-V-form words that its machine layer keeps in
memory (`docs/targets.md`): 414 of the firmware mandelbrot's 545
instructions in `in_set` are `l32i` and `s32i` through the frame, and the
report share is 53.5% at xtensa-esp32. An allocator over the RISC-V form
does not remove that class. This item either selects natively from the IR,
placing values as D1403 says, or records why Xtensa is left out. It takes on
`SR-1024`'s frame budget, `SR-1178`'s test of the outgoing area D1110
counts and `SR-1302`'s boot layout of the reference description.

Exit evidence: the ESP32 and ESP32-S3 images measured smaller than their
R16.10 baselines and their cycles no slower, with unchanged behavior and the
board records made again; or the reason Xtensa is left out recorded with its
measurement.

Done: Xtensa places the words of every routine without an assembly block
over the routine's own text (D1627). The emitter keeps its walk of the IR
and its RISC-V-form words and gives each scalar value and each slot no
address reaches a word of its own; the machine layer computes the words'
liveness, joins their definitions into webs and places them by linear scan
in a2-a6, which a call preserves, and a10-a15, the rest in their homes.
Before placing it folds a word set once to a number into the `mul`, `add`,
`divu` or `remu` that reads it, so a division or remainder by a power of
two is a shift or a mask, which takes the Xtensa half of `SR-1429`, now
restated for RISC-V alone; it drops what nothing reads and makes a flag
and its zero test one branch; and a comparison only its branch reads is
that branch (D1628). A routine of more than 150,000 lines, or whose text
the analysis cannot follow, is selected word by word as before. Over the
firmware set every image is smaller at every profile and both levels,
`.text` 0.37 to 0.76 of R16.10's; the report share of stack loads and
stores at xtensa-esp32 speed-auto is 11.1% against 53.5%, and the firmware
mandelbrot's `in_set` 121 instructions against 545, 30 of them stack loads
and stores against 414. On the boards every configuration runs faster: the
ESP32 0.18 to 0.68 of R16.10's cycles and the ESP32-S3 0.17 to 0.67,
mandelbrot, whose doubles are libgcc's, gaining least. The ESP32's and
ESP32-S3's RAM and boot records were made again on the rig, and both chips'
complete corpus lanes, native controls, boundaries and ABI peers pass.
`SR-1024`: the frame budget counts no saves, the window making them, and
the RISC-V save set is gone. `SR-1178`: a unit case holds a prepared
stack's check to the outgoing area, and a negative fixture a firmware entry
whose area alone exceeds the reference's stack. `SR-1302`: the measurement
reads an Xtensa image as its loader writes it, as D1359 has it, so the
reference's boot layout is measured, and an image it cannot measure is
refused naming the segment, symbol or line it met (D1629). `SR-1433` files
the frame placement leaves: a bank and a home for every word. Findings
fixed on the way: a lane's relative `--refine` was run from another
directory, so `measure.py size` failed with a traceback; it is now made
absolute where it is given; and the parser suite gave its one-file host
the firmware library only for Cortex-M. The candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/44846399913) and
[boards](https://github.com/701-dev/Landin/actions/runs/44849434198).

### R16.24 — The hosted backends' remaining costs

Status: complete
Depends on: R16.10

R16.10 ranked x86-64's costs as mostly not register allocation's: floats
moved through a stack slot inside loops and constants rebuilt in each
iteration, a loop's shape and the bounds check an indexed increment keeps,
`size` giving up the hot loops' registers, and the allocators' treatment of
a routine with an assembly block, which on x86-64 takes no caller-saved
register and whole-routine spans and on arm64 no slot in a register. This
takes on `SR-1268`'s SipHash round state and R551-12, whose atomic and barrier
lowering is taken or recorded with its measurement, and `SR-387`'s heap lock
path, which with no thread started still makes two out-of-line calls an
allocation and free.

Exit evidence: each cost taken measured lower against its R16.10 baseline,
with unchanged behavior, ABI and debugger evidence.

Done: lowering no longer marks every `public` routine exposed, which D415
had ruled out and the routine filling still did, so D339 copies and
specialization reach the library's public routines; the heap reads its
lock flag with the builtin, one load and a branch in `host_alloc` and
`host_free`, and aligns a power-of-two unit with a mask rather than two
divisions (`SR-387`): on x86-64 binary-trees 15 at speed-auto runs in 0.37
s against 0.44 and 0.927 of the instructions. Shifts that rotate are
`rol` and `ror` on x86-64 and arm64 (D1624), and SipHash-1-3 of 16 bytes
takes 730 instructions against 1,041, its round 15, all in registers;
Cortex-M divides by a constant power of two with shifts (D1626); the two
take `SR-1268`. x86-64 keeps floats in XMM registers at `size`, and loads
a float element, field, pointee or datum straight into one (D1625): at
size-auto mandelbrot executes 0.435 of its instructions and fasta and
binary-trees 0.92, and fasta 0.968 at speed-auto. Compiling the hosted set
at speed takes no longer. What stays is filed with its measurement:
`SR-1422` the nine registers x86-64 offers, `SR-1423` the assembly block's
rule, `SR-1424` float constants made in each block, `SR-1425` a loop's two
jumps, `SR-1426` the order D339 copies in, and R551-12 keeps the bounds
check a loop's end does not name and the calls of `core/atomic`'s cells;
`SR-1427`, `SR-1428` and `SR-1429` record what the work met, and `SR-1430` the
STM32H753's binary-search, 9.7% slower at size where the RP2040 and
RP2350 run every configuration faster. Findings fixed on
the way: the public exposure above, and a dead shift kept as if it could
trap. The STM32H753's cached profile's RAM record was made again on the rig.
The candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/44751439289) and
[boards](https://github.com/701-dev/Landin/actions/runs/44756840002), timing
included.

### R16.25 — RISC-V's remaining costs

Status: complete
Depends on: R16.10

After R16.21's allocation (D1503) the largest RISC-V cost is selection's
emulation of Arm's condition flags, `SR-1363`: copies into x20 and x21 before
every comparison and a carry and overflow computed for every addition, 22%
of RV64's instructions over four hosted workloads, and five registers kept
from the allocator. This takes on `SR-1363` and `SR-637`, RV32's frames
reserving a home for every scratch register a routine might save, which
R16.21 left as it was.

Exit evidence: RV64's instructions and both targets' sizes measured lower
than their R16.21 baselines, RV32's frames no larger than their saves need,
with unchanged behavior, ABI and debugger evidence and the board records
made again.

Done: D1687 copies no comparison: the branches after a check read its
operands where they are, a comparison's result is `slt`, `sltu`, `seqz`
or one float comparison, and a carry or overflow is computed only for a
checked sum, into x30, so x20, x21 and x23-x25 are offered to the
allocator. D1688 lays a routine's frame out again for the callee-saved
registers its text names, at both XLENs, which takes `SR-637` and stops
RV64 saving ten registers a routine. `SR-1429`, whose activation was this
item's start, is D1689: an unsigned division by a constant power of two
is a shift or a mask, and a remainder `rem` or `remu`. Against the base,
RV64's `.text` falls 20.5% at `none`, 26.3% at `size` and 24.3% at
`speed`, RV32's 5.9-6.2%, 9.3-10.1% and 9.9-10.8%, and RV64 executes 0.73
of its instructions at `speed`, 0.68 at `size` (fasta 0.56,
fannkuch-redux 0.59, mandelbrot 0.71, binary-trees 0.75 at `speed`); the
lines naming the old flag registers fall from 22% to 1.1-1.4%, now held
values. On the ESP32-C3, ESP32-C5 and Pico 2's Hazard3 all 162 timed
configurations are faster, the integer workloads by 25-34% at
speed-auto, SipHash by 15% and mandelbrot by 2%, and their six records
were made again. The RV64 fixtures under QEMU, the RV32 lanes and the
stack report pass; three corpus programs now fit the RV32 lanes at
`none`, and their D698 limits are removed. Found on the way and fixed: a
first draft computed a checked sum's carry into the register the sum was
held in, which `Holds` cannot see, since a write after an operation's
own result at its position looks like the result's; the measurement's
oracles caught it, and selection's temporaries are now never offered.
Filed: `SR-1468`, an `if`'s comparison computed into a register before its
branch; `SR-1465`-`SR-1467` record the friction met.

### R16.26 — The library's costs

Status: complete
Depends on: R16.10

R16.10 measured costs the library imposes rather than code generation: a
`list` grown by allocate and copy where the text builder grows by `resize`
(`SR-275`), and on Cortex-M0 `text.format` against `text.append` and
`core/mem`'s byte loops (`SR-1023`), with the erased table, `diag.stream`
and `core/README.md`'s Cortex-M size rows not yet measured. This takes on
`SR-275` and `SR-1023`.

Exit evidence: each cost measured, and either lowered against its R16.10
baseline or recorded with its measurement, with the counter fixtures it
changes re-decided.

Done: D1727 grows a storage that holds a block through one call to the
provider's `resize`, so `hosted/heap` moves a large list's pages rather
than copying its bytes: R16.10's 4,000 appends of 64 KiB on x86-64 take
190 ms through `vec.append_bytes` against 383 ms at the base, with 12
`mremap` calls instead of 12 `mremap`, 13 `mmap` and 13 `munmap`, and the
growing builder's 163 ms; an append of the list's own bytes reads them at
the same offset in the grown block (D1122 amended), so no image links two
ways of growing; this takes `SR-275`. A growth through
`core/fault`'s injector is now one attempt and one success, and the
fourteen fixtures and the derived containers' workload that pinned its
counters were rewritten for it; one fixture's provider, which only moved
on `resize`, now grows in place first, as the concept now says a provider
that can should. `SR-1023`'s costs, measured again at its
configurations after the register allocation work, had already fallen:
the format line is 7,020 bytes and 3,889 instructions against 4,480 and
2,259 through `append`, and the byte loops execute 35 instructions a byte
at speed-auto, not 118. Word loops would take 10 instructions a byte on a
4 KiB copy at 1.8 KB more flash, but a program copying short text runs 17%
more instructions with them, so firmware keeps its byte loops, recorded
with these figures in `core/mem/blocks.ldn`. An erased table links only
the entries something projects, and `diag.stream` adds 3.2 KB and 1,000
instructions to the four writes of one note, most of it the decimal
position; recorded. Every Cortex-M size in `core/README.md` was measured
again and corrected, about half what it said, and so were the corpus
records of `runtime/network-addresses`, which now fits at size/auto, and
`runtime/library-map-reserve-rollback`, which fits at size/auto and runs;
this takes `SR-1023`. The k-nucleotide shape's map probe, 2.5 M 12-mers
counted in a `u64` map, takes 2.45 s on x86-64, 39% in `rehash`, 27% in
`locate` and 8% in SipHash, `locate`'s time on the loads after its bucket
and key misses: the map's layout rather than its instructions, recorded in
`compiler/tests/measure/findings.md` for the port. Found on the way and
fixed: the Cortex-M lane's "unreviewed counterpart change" now says how a
counterpart case is made from its hosted fixture.

### R16.27 — Cortex-M's remaining selection

Status: complete
Depends on: R16.10

R16.22 left where its allocation found them the Cortex-M values it does not
hold, eight-byte integers and the floats a unit computes, and the Thumb-2
levels' own registers and forms: SipHash and mandelbrot still spend about
two fifths of their instructions on homes, and r8, r10 and r12 hold nothing.
This takes on `SR-581`'s high registers, `SR-582`'s CBZ and CBNZ, `SR-583`'s
bitfield instructions, `SR-596`'s float selection in VFP registers, `SR-869`'s
short `u64` routines on armv6-m and `SR-231`'s atom `match` arms, and `SR-1430`, the STM32H753's binary-search and merge-sort running
more cycles after R16.24 while the M33 ran them faster: the cause found and
the configurations no slower than R16.22's figures, or the cause recorded
with its measurement.

Exit evidence: each cost taken measured lower than its R16.10 baseline and
R16.22's figures, the cycles on the boards no slower, with unchanged
behavior, ABI and debugger evidence.

Done: with a float unit Cortex-M holds floats in d0-d15 (D1771), which
takes `SR-596`: on the AN500 description the firmware mandelbrot at
speed executes 649,506 instructions under QEMU against 4,117,064, and on
the STM32H753 runs in 1,775,748 cycles against 9,119,914. The Thumb-2
levels' speed holds values in r12, r8 and r10 (D1772, `SR-581`), a test
against zero is CBZ or CBNZ (D1768, `SR-582`) and a packed field UBFX and
BFI (D1773, `SR-583`). At every level a word constant is made where it is
read, as an immediate where the operation has one (D1767), a frame part
and a slot are read and written in place (D1769), integer conversions
within a word take one comparison (D1770) and moves that change nothing
go (D1774). Over the firmware set the executed instructions fall to 0.851
of the base at armv7-m speed and 0.857 at size, 0.897 and 0.863 at
armv6-m, and `.text` 7.5-9.0% and 5.6-6.1%. On the boards every `size`
and `speed` configuration is faster, the RP2040's by 0.918 and 0.894 at
the geometric mean, the RP2350's 0.847 and 0.844, and the STM32H753's
binary-search 2,067 cycles at speed and 2,496 at size, merge-sort 6,440,
all below R16.22's figures. `SR-1430`'s cause was found on that board:
from uncached AXI SRAM the M7 times a home's load by its distance from
the store before it, so `none`'s mandelbrot ran 15.6% slower with its
float homes read straight from sp and 2.2% faster than the base with the
two address instructions between them that D1771 keeps at `none`;
`SR-1430` is taken. That spacing leaves binary-search and SipHash at
`none` on the STM32H753 4.9% and 0.9% slower, recorded as `SR-1508`. `SR-869`'s
`divisor` is 924 bytes and `frame_bits` 210, still the eight-byte pairs,
and `SR-231`'s `failure.words` 1,132 bytes; both are kept with these
figures, and `compiler/tests/measure/findings.md` lists what is left with
what each measured. The RP2040, RP2350 (Arm) and STM32H753 records were
made again on the rig. Found on the way and fixed: a leaf saving d8-d15
had no restore, which no routine needed before. `SR-1505`-`SR-1507` record
the friction met: no command builds and counts one Cortex-M fixture,
`measure.py size`'s unexplained `--environment`, and a silent fallback
of the recorded-writes allocation. The candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/44925345364) and
[boards](https://github.com/701-dev/Landin/actions/runs/44928110636),
timing included.

### R16.28 — x86-64's code from R16.24's list

Status: complete
Depends on: R16.10

What R16.24 measured on x86-64 and left: `SR-1422`'s nine allocatable
registers, `SR-1424`'s float constants made again in every block, `SR-1425`'s
two jumps a loop iteration and the unreachable `jmp` after a branch,
`SR-1426`'s D339 copying no routine that received a copy, and `SR-1427`'s
build report that does not say which calls `--optimize speed` copied and
why the rest stayed calls.
Exit evidence: each cost taken measured lower than its R16.10 and R16.24
figures, no other combination over its own, and the build report naming
the copies.

Done: x86-64 offers `%r10` and `%r11` where selection does not write them
(D2088, `SR-1422`) and reads float constants from a read-only pool (D2092,
`SR-1424`); every hosted target lays a loop out tested at its foot and
emits no block that only jumps on (D2096, `SR-1425`); D339 weighs a routine
without loop as it will run, its scalar slots' loads and stores free, and
a routine with a loop as before (D2100, `SR-1426`), so the heap's
`align_up` carries its mask and is copied; and the build report's `copies`
names every call the inliner considered and the rule that copied or kept
it (D2101, `SR-1427`), which found that the weight, not a received copy,
kept `align_up` a call. Against the base, x86-64 at speed executes 10.2%
fewer instructions on fannkuch-redux, 12.1% on mandelbrot, 12.2% on fasta,
7.5% on reverse-complement, 3.9% on binary-trees, 6.5% on the fibre
switches, 4.5% on a SHA-256 of 64 MiB (8.50 G against gcc's 4.56 G) and
11.4% on SipHash-1-3, and at size 1.0% to 14.6% fewer. Every image's
`.text` is smaller at size; at speed, where more is copied,
fannkuch-redux's, reverse-complement's and binary-trees' grow 0.1% to 0.3%. On arm64 the loop
layout runs SipHash, SHA-256 and fannkuch-redux 3% to 5% fewer. Copying
every small routine with a loop cost fannkuch-redux 3% to 7% more cycles
for fewer instructions, which is why loops keep D339's weight. What stays
is filed: `SR-1650` the slot placement that leaves SHA-256's words in the
frame, `SR-1654` the gain the loop rule gives up, `SR-1655` loop-invariant
values, and `SR-1651` to `SR-1653` what the work met. The candidate passed
its [gate](https://github.com/701-dev/Landin/actions/runs/45078465564) on
the window's branch; it reaches main with the window.

### R16.29 — The small targets' remaining code

Status: complete
Depends on: R16.10

What the Cortex-M, RISC-V and Xtensa items left: `SR-231`'s atom `match`
re-testing its subject at every arm, `SR-869`'s short `u64` routines on
armv6-m, `SR-1433`'s Xtensa frame still reserving the logical-word bank,
`SR-1468`'s `slt` then `bnez` where one `blt` would do, R551-12's bounds
checks and `core/atomic`'s cell calls, and `SR-1578`'s lost backend case for
a Cortex-M `Range_Check` with a bound at one edge; with the tools those
items lacked, `SR-1505`'s command that builds one Cortex-M fixture at a
chosen level and description and counts it, and `SR-1507`'s report of a
routine that kept its first emission.
Exit evidence: each cost taken measured lower than its R16.10 baseline and
the last item's figures, the cycles on the boards no slower, the backend
case restored, and the two tools documented where the measurement recipe
is.

Done: Cortex-M makes an eight-byte constant or widening in the pair that
reads it (D2120), tests nothing a constant or an earlier test settled
(D2121), keeps a value a register still holds rather than reloading it
(D2122) and reads a framed routine's parameters from sp (D2123): SipHash
at armv6-m size executes 31% fewer instructions, the firmware set's
`.text` at size is 6.0% smaller at armv6-m and 9.1% at the Thumb-2
levels, and `runtime/core-text-format` now runs in the 32 KiB reference.
`SR-869`'s `divisor` is 548 bytes and `frame_bits` 178, short of its
completion; it is kept with what remains, a held pair saving only the
stores it removes on Thumb-1. The Xtensa frame is laid out after
placement (D2116, `SR-1433`): the deepest call chain at esp32 speed falls
from 800 to 384 bytes up to 2,240 to 752, every image smaller. RISC-V
branches on a comparison's operands and RISC-V and Xtensa fall through
to a branch's next block (D2112, D2113, `SR-1468`): RV64 executes 3.4%
fewer instructions and its `.text` is 2.0% smaller, RV32's 1.8% and
Xtensa's 0.55%. A refused recorded-writes allocation is allocated again
over every emission's writes and the build report names any that keeps
its homes (D2108, `SR-1507`), placing the twelve corpus routines that
fell back on r6. A loop's end that is a length less one bounds its index
(D2109): fasta on x86-64 executes 9.9% fewer instructions; R551-12 is
kept for `core/atomic`'s cell calls, which follow how D339 copies.
`SR-1578`'s case returns built from IR, and `measure.py count` builds and
counts a fixture at a chosen level, objective and description
(`SR-1505`), documented in `docs/measurement.md`. `SR-231` is retired as
not worth an IR terminator, which the maintainer confirmed on 2026-11-25:
the atom `match` chain tests its subject once and spends 6 bytes an arm, a table about 4, about 56 bytes over
`failure.words`. `compiler/tests/measure/findings.md` has each figure.
Fixed on the way: `measure.py compare` takes the directory `size` writes
(met by two streams). `SR-1660` files a copied `refine` that cannot
find its library, which two streams met. What is left on these targets
is `SR-869`'s pairs and frame record, forwarding blocks on RISC-V and
Xtensa, and the `match` table of constant results: none measured large
enough for another item of its own. Every board's records were made
again on the rig, and the boards are faster: the geometric mean of the
cycles that moved is 0.890 on the RP2040, 0.893 on the RP2350 and 0.921
on its Hazard3, 0.896 on the STM32H753, 0.925 and 0.934 on the ESP32-C3
and C5 and 0.895 and 0.900 on the ESP32 and S3, SipHash at speed down to
0.601. Twelve configurations on the STM32H753 are slower, the sieve at
speed by 14.5%, where one routine's shorter entry moves the unchanged
loops after it; `SR-1661` records it. The candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45088026461), and
the window's head that holds it its
[gate](https://github.com/701-dev/Landin/actions/runs/45096482875) and
[boards](https://github.com/701-dev/Landin/actions/runs/45096506024),
every port and its cycles.

### R16.30 — Loops that keep their values in registers

Status: complete
Depends on: R16.10

What R16.28 left on the hosted targets, the largest cost measured there:
`SR-1650`'s x86-64 slot placement that ignores the pressure inside an
interval, so SHA-256's round keeps two of its eight words and its bound in
the frame (8.50 G instructions against gcc's 4.56 G), and `SR-1655`'s
loop-invariant values remade every iteration, mandelbrot's `4.0` among
them; with the tool those measurements lacked, `SR-1652`'s `measure.py
count` for the hosted Linux targets.
Exit evidence: SHA-256 and mandelbrot measured lower than R16.28's
figures on x86-64 and arm64, no other combination over its own, and the
counting documented in `docs/measurement.md`.

Done: x86-64 reads a value without a register where its one use lies
(D2156), makes a stored value in its slot's register (D2157), adds into
a third register with `lea` (D2158) and gives float slots XMM1-XMM7 over
call-free intervals (D2159); arm64 makes a stored value in its slot's
register (D2164) and complements a 32-bit value in its `w` view (D2165);
a slot's one constant store reaches the loads it dominates (D2148), and
on hosted targets a loop's float constants, invariant arithmetic and the
addresses of arrays it indexes are made once before it, within a budget
of registers (D2149, D2150, `SR-1655`). Against the item's base, at
speed, x86-64 executes 8.7% fewer instructions on SHA-256 of 64 MiB
(8.50 G to 7.76 G; gcc's 4.56 G), whose round fell from 58 to 48
instructions, 8.1% on mandelbrot, 11.4% on reverse-complement and 0.3%
to 3.9% on the rest; at size 0.4% to 13.4% fewer. arm64 under QEMU
executes 23.0% fewer on mandelbrot, 11.7% on SHA-256, 13.0% on fasta,
12.0% on SipHash-1-3, 9.5% on fannkuch-redux and 0.7% to 4.8% on the
rest; RV64's measured workloads 1.75% fewer at speed. Every hosted image's
`.text` is smaller; firmware moves by a few bytes, every board's records were made again on the rig, and the boards' cycles hold but for the STM32H753's SipHash, 4.1% slower at speed and 6.7% faster at size for the same instructions, where a shorter `main` moves its loop (`SR-1661`). `measure.py count`
counts `linux-x86-64` and `linux-arm64` programs and builds hosted
fixtures, with `--library` for a copied compiler (`SR-1652`), and
`debug.sh --help` and `dev-test.sh --help` say which runs a debugger
(`SR-1651`). `SR-1650`'s pressure-weighing placement measured no gain
once its cost was taken this way; Q-204 asks whether to retire it.
`SR-1680` files the checks SHA-256's schedule and load loops still spend
on their own index, the largest cost left against gcc, and `SR-1681`
D2164 for RISC-V and Cortex-M, whose recorded-writes plan refused a
direct port. The candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45151343160) and
[boards](https://github.com/701-dev/Landin/actions/runs/45156048985).

### R16.31 — A loop's index proves its own checks

Status: complete
Depends on: R16.10

What R16.30 left as the largest cost against gcc on the hosted targets:
`SR-1680`'s checks on a loop's own index, which its head's comparison
already bounds. SHA-256's message schedule subtracts constants from `t`
and indexes with the results, its load loop indexes `4 * t + k`, and each
subtraction, multiplication, addition and bounds check is still made:
960 + 2,112 of about 7,400 x86-64 instructions a block, 7.76 G on 64 MiB
against gcc's 4.56 G.
Exit evidence: SHA-256's schedule and load loops measured without the
checks their index's range proves, its instructions lower than R16.30's
figures on x86-64 and arm64, and no other combination over its own.

Done: a checked `x + k`, `x - k` or `x * k` for a constant carries its
operand's bounds, a multiplication by a constant is proved when both
moved bounds fit, and a counted slot, stored with a first value and
stepped by its own content plus a constant, is never below the first
value, the proofs resting on it applied once the walk has seen that the
step cannot wrap (D2207, `SR-1680`); x86-64 selects a product so proved
as `imul` rather than `mul` (D2208). SHA-256's schedule keeps no check,
31 x86-64 instructions an iteration where it spent 44, and its load loop
none but the slice's own length, which is dynamic. Against the item's
base, at speed, x86-64 executes 11.0% fewer instructions on SHA-256 of
64 MiB (7.76 G to 6.90 G; gcc's 4.56 G) and 9.1% at size; arm64 under
QEMU 12.0% fewer at speed and 8.8% at size; binary-trees 0.3% fewer on
both, reverse-complement 0.2% on x86-64, every other hosted program the
same, every image's `.text` smaller and every output the same. What
SHA-256 still spends against gcc is selection rather than checks: `SR-1704`
files the index offsets x86-64 makes in registers rather than in the
address's displacement and the four products of one `4 * t`. Q-204 is
answered: SR-1650 stays open until it is solved. Firmware moved only on
the STM32H753 and the ESP32-C3 and C5; every board's records were made
again on the rig, and all 432 board configurations' cycles stayed within
tolerance. The candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45184619163) and
[boards](https://github.com/701-dev/Landin/actions/runs/45192092129).

### R16.32 — Time the STM32H753 from its tightly coupled memories

Status: complete
Depends on: R16.10

`SR-1661`'s slowdowns, measured to their cause: the timing image's RAM
layout puts the STM32H753's text, data and stack in uncached AXI SRAM,
where the same code moved 2 bytes at a time runs the sieve at speed in
7,317 to 10,652 cycles and SipHash in 510,115 to 541,009, with a period
of 32 bytes, and a load soon after a store to the stack stalls. With
text in ITCM, where the board's own description boots it, and data, BSS
and stack in DTCM, the range falls under 0.6% and nine of the ten
recorded slowdowns are gains or equal, the tenth +0.45%. The maintainer
chose this layout for the board's timing runs on 2026-11-23.
Exit evidence: the STM32H753's timing images placed in ITCM and DTCM,
its cycle baselines recorded again on the rig, its sieve and
binary-search at speed no slower than their R16.27 figures, and why this
port's placement differs from the RAM layout's default said in
`docs/measurement.md`.

Done: `timing.py build` links the STM32H753's timing images with
refine's derived RAM script, text and read-only data moved to the ITCM
past its first eight bytes and data, BSS and stack to the DTCM, the
vectors left where D546's contract fixes them (D2227); `timing.py
noise` keeps the boards a study does not cover, and `timing.py images`
bundles hand-made ELF files for the rig (`SR-1715`). Recorded again on the
rig, every one of the board's 54 configurations is faster: at speed by
46.0% to 52.7% but mandelbrot's 2.1%, the sieve 10,646 to 5,261 cycles
and binary-search 1,787 to 918, against R16.27's 9,295 and 1,737; at
size by 42.5% to 51.2% but mandelbrot's 2.9%; at `none` by 23.3% to
42.3%. Its noise study, made again from the TCMs, keeps the port's
tolerance of 0.5% and 40 cycles. `SR-1661` and `SR-1715` are taken, and
`SR-1714`, kept, comes from the measurement that found the cause; `SR-1716` files
the contract's acceptance of text at address zero, met on the way. The
candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45211342807) and
[boards](https://github.com/701-dev/Landin/actions/runs/45217192089).

### R16.33 — Element addresses and products by a constant

Status: complete
Depends on: R16.10

What R16.31 left as SHA-256's largest cost against gcc on the hosted
targets, now selection rather than checks: `SR-1704`'s index offsets
made in registers of their own rather than in the address's
displacement, the same `4 * t` made four times in one block, and a
multiplication by a power of two made as a product rather than a shift
or a scaled index. The schedule spends 31 x86-64 instructions an
iteration where about 23 would do, the load loop more; 6.90 G on 64 MiB
against gcc's 4.56 G.
Exit evidence: SHA-256's schedule and load loops measured with each
constant offset in the address and each `4 * t` made once and scaled or
shifted, its instructions lower than R16.31's figures on x86-64 and
arm64, and no other combination over its own.

Done: the simplifier moves a constant left operand of a commutative
integer operation to the right (D2247) and numbers equal integer
constants as one class without replacing them (D2248), so SHA-256's four
`4 * t` are one product. x86-64 puts an index's constant offset in the
access's displacement (D2252), as it now does a field behind an address
slot in its home (D2254), compares and scales a slice edge where it
lives (D2250) and does not widen a byte it loaded again (D2249); a proved
product by a power of two is `shl` or `lea` on x86-64 and `lsl` on arm64
(D2251), and arm64 makes a conversion in the register its operand dies
in (D2253). arm64 has no address with both a register index and a
displacement, so its schedule keeps a `sub` before each load (`SR-1704`).
SHA-256's schedule is 23 x86-64 instructions an iteration where it was
31, and its load loop 25 where it was 52. Against the item's base, at
speed, x86-64 executes 12.7% fewer instructions on SHA-256 of 64 MiB
(6.90 G to 6.03 G; gcc's 4.56 G), 9.7% on reverse-complement, 8.0% on
SipHash-1-3, 6.2% on fasta, 2.3% on fibres, 1.3% on fannkuch-redux and
0.03% to 0.15% on the rest; arm64 under QEMU 3.7% on reverse-complement,
3.5% on SHA-256, 2.8% on SipHash-1-3, 1.8% on binary-trees, 1.6% on
fibres and up to 0.1% on the rest. At size x86-64 executes 0.03% to
10.6% fewer and arm64 up to 2.5%. Every hosted image's `.text` is
smaller and every output the same; RV64 executes fewer instructions on
every workload, and Cortex-M0's one firmware workload 0.6% fewer. Every
board's records were made again on the rig. Of the boards' 432 cycle
configurations, 390 held within tolerance and 36 ran faster, fannkuch-redux
by 0.25% to 2.4%. At speed it ran 0.64% slower on the RP2350's M33 and
0.63% on its Hazard3 with two fewer instructions: its flip loop's 32-bit
head and call moved to halfword addresses. `SR-1726` files that alignment.
The candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45252688704) and
[boards](https://github.com/701-dev/Landin/actions/runs/45259337256).

### R16.34 — Stored values in their slots' registers on RISC-V and Cortex-M

Status: complete
Depends on: R16.10

What R16.33 named as the next cost on the firmware and RISC-V targets:
`SR-1681`'s stored value, which arm64 (D2164) and x86-64 (D2157) make in
its slot's register and RISC-V and Cortex-M still make in a register of
its own and move. On arm64 the rule alone took 5.5% to 14% off every
hosted workload at speed; a direct port to RISC-V's recorded-writes
allocator made RV64 execute 7% to 110% more instructions, because the
plan's check refused the value's write inside the slot's interval and
the routine fell back to its homes (D1503, D2108). Beside it, since
every board's records are made again either way, `SR-1726`'s placement:
on the RP2350, whose M33 and Hazard3 fetch from SRAM without a cache,
R16.33's two fewer instructions moved fannkuch-redux's flip loop's 32-bit
head and call to halfword addresses and it ran 0.64% and 0.63% slower at
speed.
Exit evidence: RV64, RV32 and Cortex-M make a stored value in its slot's
register with the plan's check accepting it, RV64's instructions at speed
and the boards' cycles lower than R16.33's figures; at speed on Thumb-2
and compressed RV32 a loop's head at a word address, padded only where
the padding is not executed, the RP2350's fannkuch-redux no slower than
before R16.33; and no other combination over its own.

Done: at speed RISC-V, at either XLEN, and Cortex-M make a value whose
last use stores it into a slot held in a register in that register, and
the recorded-writes check takes the value's own write as the slot's new
contents, and lets it meet a value dying there, refusing every other write
(D2307, `SR-1681`). At speed Thumb-2 and RV32 start a loop's head on a
word where the instruction before it does not fall through, the padding
never executed (D2308, `SR-1726`), with x86-64's loop-head finder now
shared from `Landin.Backend.Placement`; and RV32 settles its jumps per
routine as RV64 does where the firmware profile does not bound them
(D2309), which every RV32 board's profile does not. Against the item's
base, at speed, RV64 under QEMU executes 6.4% fewer instructions on
SipHash-1-3, 6.1% on mandelbrot, 4.5% on fasta, 3.3% on fannkuch-redux,
1.3% on SHA-256 and 0.2% to 0.8% on the rest, every output the same; the
Cortex-M lanes 0.2% to 6.3% fewer at Thumb-2 levels, 12.2% on mandelbrot
with a float unit and up to 5.1% at Armv6-M; `size` and `none` are
unchanged, and every speed image's `.text` 0.1% to 1.4% smaller. Every
board's records were made again on the rig. Of the boards' 432 cycle
configurations, 110 ran faster and one slower: the Hazard3 14.6% to 26.0%
on binary-search, merge-sort, the sieve and fannkuch-redux at every
objective, 2.8% to 5.8% on SipHash and 0.3% to 0.8% on mandelbrot; the
ESP32-C3 and C5 0.4% to 4.1%; the
RP2040 0.4% to 4.0%; the RP2350's M33 0.5% to 4.4%, fannkuch-redux 3.1%,
below its figure before R16.33; and the STM32H753 1.5% to 8.8% but for
SipHash, 1.29% slower for fewer instructions, which placement alone moves
by 1.2% from the TCMs (`SR-1758`). `SR-1757` files firmware's block
order, which leaves most firmware loop heads fallen into. The merged
candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45335016031) and
[boards](https://github.com/701-dev/Landin/actions/runs/45338343665).

### R16.35 — What SHA-256 still costs on x86-64

Status: complete
Depends on: R16.10

What R16.33 left as SHA-256's largest cost against gcc on x86-64, and
what R16.34 did not touch: SHA-256 of 64 MiB executes 6.03 G instructions
at speed against gcc 16.1 `-O2`'s 4.56 G. `SR-1650` names the
compression round, which keeps the word `h` in the frame because slot
placement gives a slot a register over its whole interval without
counting the registers the values inside it still need; R16.30 found
that a register for `h` alone saves two memory accesses a round and no
instruction (Q-204). Measured first, then taken where the instructions
are: the round, the message schedule and load loops, and the program's
own work on each byte.
Exit evidence: SHA-256 at speed on x86-64 executing more than 5% fewer
instructions than at the item's base, each cost it takes measured, the
round's against `SR-1650`'s completion, and no other combination over
its own.

Done: SHA-256's round already executes 48 x86-64 instructions, gcc's
own count; the rest of what the program spent over gcc was its schedule
and load loops, which gcc vectorizes, and its own work on each byte. A
checked integer conversion is proved when its operand's bounds lie in
the result's range (D2367), so `u8(x & 0xff)` converts unchecked; a load
of a slot stored once from another slot stored once stands for that
slot (D2368), so `for i in usize(0)..<lenof bytes` bounds `bytes[i]`
when scalar replacement split the slice from a call's result; and
x86-64 narrows an unchecked integer in its own register (D2369). The
program's byte loop fell from 14 x86-64 instructions to 8. Against the
item's base, at speed, x86-64 executes 6.7% fewer instructions on
SHA-256 of 64 MiB (6.03 G to 5.63 G; gcc's 4.56 G) and 0.7% on
SipHash-1-3, arm64 under QEMU 6.0% and 0.5%, and the rest within
0.001%; at size SHA-256 3.5% on x86-64 and 2.5% on arm64. Every hosted
image's `.text` is smaller and every output the same. `SR-1650` stays
open: its `h` needs a twelfth register, the round holding nine slots and
three temporaries at once where x86-64 offers eleven, and giving every
u32 slot `%r8` and `%r9` made SHA-256 23% worse. `SR-1787` files the
round's majority and choice identities, gcc's, which need the
simplification to make an instruction of its own, and `SR-1788` a slice
element's address not folded into its store; `SR-1789` the Windows
debugger session's stall, met once in the item's gate. The STM32H753's, the
ESP32-C3's, the ESP32-C5's, the ESP32's and the ESP32-S3's records were
made again on the rig. Of the boards' 432 cycle configurations, 78 ran
changed images, all within tolerance: 75 ran 0.01% to 0.76% faster,
binary-search most, and the ESP32-C5's SipHash at size 0.08% slower; the
ESP32-C3's SipHash, which its RAM layout cannot time, keeps that limit
with an instruction segment 16 to 24 bytes smaller.
The merged candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45400339063) and
[boards](https://github.com/701-dev/Landin/actions/runs/45406894479).

### R16.36 — Firmware loops tested at their foot

Status: complete
Depends on: R16.10

`SR-1757`: Cortex-M, RV32 and Xtensa keep lowering's block order, since
D2096 runs `Landin.IR.Layout` for hosted targets alone, so each iteration
of a firmware loop jumps to its step and the step jumps back to the test
at its head, and D2308's word alignment, which pads only a head nothing
falls into, reaches few firmware loops. On x86-64 the hosted layout took
0.5% to 8.9% off every workload at speed. The item lays firmware loops
out tested at their foot where that pays, at `size` and `speed`, and
measures it over the Cortex-M lanes' instructions, every board's cycles
and every firmware image's size.
Exit evidence: a benchmark program executing more than 5% fewer
instructions on a Cortex-M lane, or taking more than 5% fewer cycles on a
board, than at the item's base; every program's instructions, cycles and
image size reported against that base; and no other combination over its
own.

Done: `Landin.IR.Layout` lays out every target's blocks at `size` and
`speed` (D2408), so Cortex-M, RV32 and Xtensa test a loop at its foot and
emit no block that only jumps on, and D2308 puts the head a foot test
branches back to on a word. ARMv6-M's images grew by up to 1.3% at `size`
until an edge within B's reach took B over the inverted branch in place
of a long jump through r7 (D2407). Against the item's base, at `speed`,
the Cortex-M lanes execute 9.6% fewer instructions on the sieve at
ARMv7-M, 4.5% on binary search, 1.9% on merge sort, 1.2% on
fannkuch-redux, 0.3% on SipHash and 0.2% on mandelbrot (4.7% with the
double-precision unit), and ARMv6-M 6.7%, 3.2%, 2.1%, 1.2%, 0.2% and
0.0%; every firmware image at `size` and `speed` is smaller, Thumb-2 by
0.6% to 5.0%, ARMv6-M 0.6% to 5.4%, RV32 0.2% to 1.9% and Xtensa 0.4% to
1.1%, and `none` is unchanged but for ARMv6-M's B. Of the boards' 432
cycle configurations 240 moved: at `speed` the sieve takes 6.7% to 18.7%
fewer cycles, the ESP32's most, binary search 3.0% to 16.3%, merge sort
2.5% to 11.1% but on the STM32H753, fannkuch-redux up to 3.7% and SipHash
up to 2.6% fewer.
21 are slower: the ESP32's and ESP32-S3's fannkuch-redux by 1.1%, which
`SR-1807` files, the STM32H753's SipHash at `speed` by 1.3%, the
placement `SR-1758` keeps, and the ESP32-C3's and the Hazard3's
mandelbrot at `size` by 0.3%. Every board's RAM and boot records were made
again on the rig, and the cycle, size and instruction baselines recorded.
The smaller images run `runtime/map-seed-spreads-chosen-keys` on Cortex-M0
at every profile and on RV32 at `size` and `speed`, where it had
overflowed. `SR-1757` is taken. The merged candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45466768478) and
[boards](https://github.com/701-dev/Landin/actions/runs/45472956351).

### R16.37 — Identities that make an instruction

Status: complete
Depends on: R16.10

`SR-1787`: SHA-256's round on x86-64 executes 48 instructions, gcc 16.1
`-O2`'s count, but gcc writes the majority `(a & b) ^ (a & c) ^ (b & c)`
as `(a & (b ^ c)) ^ (b & c)` and could write the choice `(e & f) ^ (~e &
g)` as `(e & (f ^ g)) ^ g`, about 6.8% of SHA-256 of 64 MiB at speed.
Both identities need a value the source never computed, and
`Landin.IR.Simplification` only rewrites an instruction in place. The
item lets the simplification make an instruction where an identity needs
one, applies the two identities on every target, and measures every
benchmark program against its base.
Exit evidence: SHA-256 at speed on x86-64 executing more than 5% fewer
instructions than at the item's base, its round measured against gcc's;
every program's instructions and image size reported against that base;
and no other combination over its own.

Done: `Landin.IR.Identities`, simplification's last step, rewrites
`(x & y) ^ (x & z)`, and the same with `|`, as `x & (y ^ z)`, and the
choice `(x & y) ^ (~x & z)` as `(x & (y ^ z)) ^ z`, on every target; the
choice's new AND is inserted by the arena rebuild, which now takes
instructions to place before those it keeps (D2447). Those two took 4.8%
off SHA-256 at speed, four instructions a round where `SR-1787`
estimated six, so two rotations joined by a bitwise operation now turn
one chain, `rotl(rotl(a, m - n) op b, n)`, which x86-64's two-address
code copies once where it copied three times (D2448). Against the
item's base, at speed, SHA-256 of 64 MiB executes 11.3% fewer x86-64
instructions (5.63 G to 4.99 G; gcc 16.1 `-O2` 4.56 G) and 2.6% fewer
on arm64 under QEMU, at size 7.7% and 1.7%; its round is 40 x86-64
instructions to gcc's 48. Every other benchmark program executes within
0.001% of its base, and every output is the same. No measured hosted or
firmware image changed, so no size, instruction or cycle baseline and no
board record was made again. `SR-1787` is taken; `SR-1827` and
`SR-1828` file what R16.36 met timing boards by hand, one run where the
gate takes three and the RP2350's boot check needed first. The
candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45496244601) and
[boards](https://github.com/701-dev/Landin/actions/runs/45502295184).

### R16.38 — A growing arena for binary-trees

Status: complete
Depends on: R16.10

`SR-1432`: binary-trees at depth 21 takes 2.4 times C's time on x86-64
at speed, and the cost is its allocator, not code generation. A
`core/region` asks the heap for every node, writes a ledger record of it
and frees each node back at `release`. At depth 18 the port executes
46.4 G instructions in 11.7 G cycles; the same program with each tree
in a `core/arena` over one heap block sized for its depth executes
20.6 G in 5.1 G cycles, with the same output. No allocator in the
library both grows and bump-allocates (`SR-1412`), and a port that sizes
each tree's block from its depth knows more than a program usually
does. The item adds an allocator that bump-allocates from blocks it
takes from a parent, grows by taking another, and gives them back when
it is released through its handle. It puts the port on that allocator
and measures every benchmark program against its base.
Exit evidence: binary-trees at speed on x86-64 executing more than 5%
fewer instructions than at the item's base, measured on arm64 as well;
`docs/benchmarks.md`'s binary-trees figures measured again; every
program's instructions and image size reported against that base; and
no other combination over its own.

Done: `core/zone` (D2449) takes blocks from a parent, each twice as
large as the one before from 1024 bytes less the parent's two-word
header, or just large enough when the request is larger or the parent
refuses the next, and hands out the newest block's bytes in order;
`zone.reset` gives every allocation back through the handle and every
block but the newest to the parent, and `zone.release` gives every block
back. binary-trees takes its stretch tree, its long-lived tree and its
rounds each from a zone over the heap, resetting the rounds' zone after
each tree. Against the item's base it executes 54.8% fewer x86-64
instructions at speed at depth 15 and 58.6% at size, 56.7% and 62.6% on
arm64 under QEMU, and 61.6% and 65.7% on RV64; at depth 21 it runs in
12.8 seconds against 32.4, 0.85 of C's time where it took 2.18, at 128
MB peak against 385. Its image is 0.6% to 1.6% larger, no other
workload's image changed, and every output is the same.
`docs/benchmarks.md` measures it again. `SR-1432` is taken; `SR-1412`
keeps the region's silent single free; Q-274 asks whether the module's
name is `core/zone`, `SR-1829` files the formatting case no
step for a new module names, and `SR-1830` the Debian packages the
embedded tools fetch from a pool that drops superseded versions. The
merged candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45543519666) and
[boards](https://github.com/701-dev/Landin/actions/runs/45547023934).

### R16.39 — An index counted down proves its own checks

Status: complete
Depends on: R16.10

reverse-complement spends 70% of its x86-64 instructions at speed in
`write_reversed`, which walks a sequence from its end, `while at > 0 do
dec at` reading `sequence[at]` from `at = lenof sequence`: 7.10 G on
fasta 25,000,000's output against C's 2.10 G. D2207's counted slot
bounds only an index that counts up, so each byte still pays a bounds
check and a reload of the length it compares with, three of the loop's
sixteen instructions. No open row names the cost. The item proves an
index counted down from a length below that length, and leaves unloaded
a length no remaining check reads.
Exit evidence: reverse-complement at speed on x86-64 executing more than
5% fewer instructions than at the item's base, measured on arm64 as
well; every benchmark program's instructions and image size reported
against that base; and no other combination over its own.

Done: a slot stored with a first value and stepped by its own load less
a constant counts down and is never above that first value, so a
checked `x - k` of its load is below a length the first value names,
the proof waiting for the walk to see the step, as D2207's do (D2491);
x86-64 makes no load of a length only proved checks name (D2492).
reverse-complement keeps no check in its byte loop: against the item's
base under QEMU it executes 12.4% fewer x86-64 instructions at speed
and 12.7% at size, 7.0% and 5.5% on arm64, and 2.5% and 2.0% on RV64;
fasta 4.1% fewer at x86-64 size, every other hosted program within
0.2%, every output the same. Every image's code and data are the same
size or smaller; FreeBSD's reverse-complement at speed is 28 and 16
bytes larger in all, its RELRO padding growing by more than its text
shrinks. Choosing the subject, nested copies of the allocator chain gave
binary-trees under 3%, and a call's failure status, sealed and its test
fused into the branch, 3.9%; `SR-1861` files the second. The merged
candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45708189957) and
[boards](https://github.com/701-dev/Landin/actions/runs/45714601151).

### R16.40 — An element address reaches every access through it

Status: complete
Depends on: R16.10

fannkuch-redux spends 62% of its x86-64 instructions at speed in
`reverse_prefix`, which swaps `values[left]` and `values[right]` in an
`inout [16]u8`. Each element's address reaches its load and its store
through compiler temporaries, so the address is formed once with
`leaq (%rdi,%rsi), %r9` and both accesses read through `%r9`: two of
the loop's fourteen instructions, and on arm64 two `add`s and a copy of
fifteen. The existing fold reaches only an access right after its
address (`SR-1788`). With the two addresses folded by hand into the
four accesses, fannkuch-redux 10 executed 1.631 G instructions against
1.515 G, 7.1% fewer, with the same output. The item reaches every
access an element address is carried to later in its block, through
the registers the address names while they hold.
Exit evidence: fannkuch-redux at speed on x86-64 executing more than 5%
fewer instructions than at the item's base, measured on arm64 as well;
every benchmark program's instructions and image size reported against
that base; and no other combination over its own.

Done: an element address of an array or a slice whose every use is,
later in its block, an indirect access through it or a load of a
temporary carrying it is not formed on x86-64 or arm64 while the
registers its memory operand names hold through the last access; each
access reads through that operand, and the temporaries' stores and loads
move nothing (D2573). A temporary a debugger binding is described
through, as a loop's element is, keeps its address. `reverse_prefix`'s
loop falls from fourteen x86-64 instructions to twelve and from fifteen
arm64 instructions to twelve: against the item's base under QEMU
fannkuch-redux executes 7.1% fewer x86-64 instructions at speed and 6.8%
at size, 10.0% and 7.9% on arm64; reverse-complement 1.2% to 1.9% fewer
on both, every other hosted program within 0.3%, every output the same.
Every image's code is the same size or smaller; 33 FreeBSD arm64 images
are 8 bytes larger in all, their RELRO padding growing by more than
their text shrinks. `SR-1788`'s slice store, SHA-256's byte loop, is folded
as well, and the row is taken. The merged candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45760688726) and
[boards](https://github.com/701-dev/Landin/actions/runs/45760702435).

### R16.41 — A float element is compared where it lies

Status: complete
Depends on: R16.10

fasta spends two thirds of its x86-64 instructions at speed in
`select_symbol`, which counts the cumulative probabilities a random
number reaches: if-conversion makes `if random >= cumulative[at] then
inc index end if` a comparison whose flag is added to the count, ten
instructions a step. Two of them move nothing: the element is loaded
into a register with `movsd` before `ucomisd` reads it, which can read
it from memory, and the flag's zero extension is made in `%eax` and
copied to the register the addition reads. With both left out, ten
instructions become eight, and fasta 2,500,000 executes 2.857 G
instructions against 3.142 G, 9.1% fewer, with the same output. The
item compares a float that only its comparison or arithmetic reads
where it lies, and extends a counted flag into its own register.
Exit evidence: fasta at speed on x86-64 executing more than 5% fewer
instructions than at the item's base; every benchmark program's
instructions and image size reported against that base, arm64 as well;
and no other combination over its own.

Done: at size and speed x86-64 does not make a float load whose one use
is a float comparison, addition, subtraction, multiplication or
division, when only constants with an immediate and loads of a slot
already in its register lie between them; the operation reads the
load's memory operand, and a counted one or zero is extended straight
into its own register (D2574). `select_symbol`'s loop falls from ten
x86-64 instructions to eight: against the item's base under QEMU fasta
executes 9.1% fewer x86-64 instructions at speed and 7.9% at size,
mandelbrot 0.2% fewer and the switch measurements 0.07%, every other
program and every arm64 figure the same, every output the same. Cycles
on a Zen 2 host did not move: about 10.0 G at fasta 25,000,000 either
way. Four workloads' x86-64 images are 31 bytes smaller in all a
configuration on Linux and Windows; FreeBSD's keep their totals, RELRO
padding taking up what the text gives back. Putting if-conversion's
copies before the load as well changed STM32H753 firmware for no gain
and was undone. `SR-1918` records the count's overflow check the loop
keeps, `SR-1919` the refusal `item.py start` met. The candidate passed
its [gate](https://github.com/701-dev/Landin/actions/runs/45795175499)
and [boards](https://github.com/701-dev/Landin/actions/runs/45795196472).

### R16.42 — A byte is loaded into the register it is kept in

Status: complete
Depends on: R16.10

reverse-complement spends seven tenths of its x86-64 instructions at
speed in `write_reversed`, whose loop turns each byte of a line around
through a table of complements. Two of its fifteen instructions a byte
move nothing: the byte is loaded into a register of its own and copied
with `movzbl` into the register its variable `base` is kept in, since
that variable's interval opens only at the store, and widening it to
index the table extends it again into a third register, though every
value `base` ever holds is a loaded byte already zero-extended. With
both left out, reverse-complement executes 1.359 G instructions against
1.488 G, 8.7% fewer, and about 11% fewer cycles on a Zen 2 host, with
the same output. The item makes a value in its slot's register when the
slot's interval opens at the value's store, and widens a byte or
halfword where it lies when its slot holds only zero-extended values.
Exit evidence: reverse-complement at speed on x86-64 executing more than
5% fewer instructions than at the item's base, cycles reported beside
them; every benchmark program's instructions and image size reported
against that base, arm64 as well; and no other combination over its own.

Done: at size and speed x86-64 makes a value in the register of the slot
its first store writes when that slot's interval opens at the store and
nothing holds the register before it, and widens a byte or halfword
slot whose every store leaves its register zero-extended there, with no
move; an unsigned widening may take the register of a variable it reads
for the last time (D2654). `write_reversed`'s loop falls from fifteen
x86-64 instructions a byte to thirteen: against the item's base under
QEMU at speed reverse-complement executes 8.7% fewer instructions,
binary-trees 3.2%, fasta and the switch measurements 0.8% to 0.9%,
every other x86-64 figure within 0.03% and every arm64 figure the same,
every output the same. On a Zen 2 host reverse-complement runs 11.0%
fewer cycles and binary-trees 18 1.4% fewer, the others within 0.2%.
168 x86-64 images on each of Linux and Windows are 24 to 512 bytes
smaller; FreeBSD's keep their totals, RELRO padding taking up what the
text gives back. binary-trees' `aligned_offset`, whose copy into `room` by
hand saved 8.1% of its instructions, stays a call: it weighs 85,
its call recovers with `else`, and copies are one level deep. `SR-1958`
records arm64's three copies in the same loop, 11.4% of
reverse-complement there by a hand patch, and `SR-1959` the overflow
check of the increment after the line's bounds check, 4.0% on x86-64.
The merged candidate, with `gate-watcher` riding it, passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45855807406),
after `freebsd-host-release` was run again over a mirror's refusal, and
its [boards](https://github.com/701-dev/Landin/actions/runs/45855853447).

### R16.43 — A value read after its store is made in its slot's register on arm64

Status: complete
Depends on: R16.10

arm64 makes a value in the register of the slot it is stored into only
when the store is the value's last use (D2164), so a value read again
after its store is made in a register of its own and copied:
reverse-complement's `write_reversed` copies `at - 1` into `at`, the
loaded byte into `base` and `width + 1` into `width`, three `mov`s of
its eighteen instructions a byte. Removed by hand they leave 1.415 G
instructions under QEMU against 1.597 G, 11.4% fewer, with the same
output (`SR-1958`). The item makes such a value in its slot's register
at speed when the slot holds that register over the value's span or
opens it at the store, as x86-64's D2157 and D2654 do.
Exit evidence: reverse-complement at speed on arm64 executing more than
5% fewer instructions than at the item's base, its time on an arm64
host reported beside them; every benchmark program's instructions and
image size reported against that base, x86-64 as well; and no other
combination over its own.

Done: at speed arm64 makes a value read again after its first store in
the register of the slot that store writes when the slot holds that
register over the value's span, or its interval opens at the store,
and nothing else stores the slot inside the span; an indirect load may
take the register of what it reads for the last time (D2714). The
three copies of `write_reversed`'s loop and mandelbrot's two float
moves go. Against the item's base under QEMU at armv8-a speed
mandelbrot executes 12.0% fewer instructions, reverse-complement
11.7%, the switch measurements 1.9%, fasta 1.8% and binary-trees 1.4%;
fannkuch-redux, every size figure and every x86-64 figure are the
same, every output the same. Timed on one 3.9 GHz big core of an arm64 host, where no
cycle counter is open to an unprivileged user, mandelbrot runs 16.1%
faster and reverse-complement 15.5%, the others within 1%. arm64
images at speed are 24 to 2,332 bytes smaller over seven workloads a
configuration; none grew. `SR-1958`, which measured the copies by
hand, is completed and deleted. The register sweep had planned this
work as R16.44 and the increment checks as R16.43; the increment item
is R16.44 now. The merged candidate passed its
[gate](https://github.com/701-dev/Landin/actions/runs/45907130369),
after `windows-arm64-debugger` was run again over `SR-1940`'s step
through the stack switch, and its
[boards](https://github.com/701-dev/Landin/actions/runs/45907141173).

### R16.44 — An increment proved by the check before it

Status: planned
Depends on: R16.10

Two increments keep an overflow check that cannot fail. SR-1959's index,
checked below a constant bound by the bounds check just before it in the
same block, then incremented: reverse-complement's `write_reversed`,
4.0% of its x86-64 instructions at speed by a hand patch. SR-1918's
count, incremented at most once a step of a counted loop from zero:
fasta's `select_symbol`, 5.0% on x86-64 and 5.4% on arm64 by its step
count. The first needs only the fact the block's own check leaves; the
second needs the count's bound related to the loop's, an invariant the
simplifier does not keep. Scheduled by the register sweep of 2026-11-26.
Exit evidence: each check proved and removed on every target, the two
programs' instructions measured against the item's base, and no other
combination over its own.

### R16.45 — A call's failure tested once

Status: planned
Depends on: R16.10

SR-1861: every call that can fail costs x86-64 about eleven instructions
on its succeeding way where two would do, its status stored, loaded back,
validated against its atom set and tested through a byte. R16.39
measured sealing the call's failure slot and fusing the test into its
branch at about 5% of binary-trees' cycles. Sealing changes every
backend's validation, so firmware images and board records move with
it. Scheduled by the register sweep of 2026-11-26. Exit evidence: a
call's succeeding way testing its status once, in a register, on every
target, binary-trees measured against the item's base, and no other
combination over its own.

### The continuous items

Numbered on from R16.20, each is added when it is taken up, or planned when
an item splits it off as R16.20 split R16.21 to R16.24, with its own status
and a dependency on R16.10. Each takes one cost from R16.10's
ranked list, a further backend's register allocation among them.
Exit evidence: the cost measured lower against its R16.10 baseline, and no
other combination over its own.

### R16 gate
The standing invariant: every supported target, level and optimization
combination within its committed baselines on every push.

## R17 — Process, register and skills

The move's own debt; first in the serial lane.

### R17.10 — The register reviewed and typed

Status: complete
Depends on: none

The first item, on a tree `check.py` already accepts: the exchange has moved
every live row into its file. R17.10 reviews each moved row against
"outlives its item", gives it its `kind`, `effort` and `impact`, deletes
those its authority covers and puts the rest it would retire to the
maintainer as questions. It provides the SR allocation script and files the
rows-to-be in `roadmap/inputs/rows-to-be.md`. The rows that describe R22's
additions (`SR-96` math, `SR-97` float text, SR-98 locale and Unicode, `SR-100`
regular expressions, `SR-285` format width and radix) become `scheduled` on
the R22 items that take them.
Exit evidence: every row typed and under the cap; the allocation script and
its control; the cap and age rule refused in a control.

Done: every moved row typed, the rows-to-be filed as `SR-1282` to `SR-1298`,
`scripts/register_next.py` with its controls, and `check.py` refusing a
register over its cap or a row past its age in controls. The maintainer's
answers to Q-1 to Q-5 retired 43 rows and scheduled `SR-195` and `SR-768` on
R17.50, `SR-1178` on R16.20, `SR-1237` on R19.10 and C3 on R20.10; a rig fix
rooting the GPIO shell retired one more, leaving 57 open with R17.50's
fixes merged. The retired rows' standing facts moved to
`docs/capabilities.md`, `docs/targets.md` and `devices/README.md`.

### R17.20 — The question queue

Status: complete
Depends on: R17.10

`roadmap/questions/`, its checks and the open maintainer decisions moved
into it.
Exit evidence: every open maintainer decision a `Q-n` file; `check.py`
refusing a question without options, default or what waits on it.

Done: the Mechanics give a question its form, and `check.py` refuses a
question without its heading, asker, options, recommendation, default,
what waits on it or a well-formed answer, a default given by its option
number alone, a `TODO`, a question cited without its file, and a question
identity outside the roadmap's files, each in a control.
`roadmap/register.md` lists the open questions with their defaults and
what waits. `scripts/register_next.py --question --file` allocates and
writes the next one. Q-1 to Q-6 gained their `What waits on the answer:`
paragraphs, and the one open decision held outside the queue, the Darwin
determinism manifests' compiler, is Q-7.

### R17.30 — Lanes and standing authority in the checks

Status: complete
Depends on: R17.10

`check.py`, the site's progress track and the status pointers read lanes,
continuous items and the promotion opt-out. It takes three rows-to-be:
the phase rule the Mechanics do not state (`SR-1282`), the progress track
that fails on a second active item (`SR-1283`), and a reference before a
full stop that is never resolved (`SR-1295`). It also lets any item whose
dependencies are complete be active, several at once, where `check.py`
allowed one, so that R17.50 said `planned` while it ran; states in the
Mechanics that an item of a serial phase may start beside the serial
lane's item, as R17.50 did, which is neither lane; and makes a real
`Status: blocked` item one the checks and their controls accept, which
the first R17.50 session found they did not.
Exit evidence: the front page showing the serial item beside two active
continuous items in a control; the pointers naming the serial lane's
item, with an item of a serial phase active beside it and with a blocked
item, each in a control.

Done: one reader in `roadmap_order.py`, `roadmap_items` and `lane_state`,
serves `check.py` and the site. The serial lane's item is the first in
execution order that is active, or planned and ready; the pointers name it
alone, and the front page shows it with every other active item beside
it, where it had refused a second active item (`SR-1283`). `check.py`
accepts several active items and refuses one whose dependencies are not
complete, a `Blocked because:` line on an item not blocked, and a
promotion line other than `Promotion: maintainer`; it resolves an
identity before a full stop (`SR-1295`), which found the Mechanics' unit
example naming an item that does not exist. A blocked item's reason no
longer hides its dependencies from the site, and the controls that broke
on a real blocked item, found when the first R17.50 session tried the
status, no longer assume none exists. The Mechanics state the phase rule
(`SR-1282`), that several items may be active, and that an item of a serial
phase may start beside the serial lane's item. The controls show the
serial item beside two active continuous items on the front page, and
the pointers holding to the serial item with an early item active beside
it and with a blocked item.

### R17.40 — The item skill rebuilt

Status: complete
Depends on: R17.30

`landin-change` for the new mechanics; scripts for every step that needs
no agent (starting an item with its worktree, brief and reserved
identities; closing it with its clean-up; promotion; a check for a stalled
agent); reopen-safe session state on disk; and the report form that ends
with what the maintainer must answer, each with the default taken. Fixes
from a review run between items, never across a running one.
Exit evidence: the skill and its scripts used to run the next item start
to finish, and a session reopened in mid-item resuming from
its state on disk.

Done: `scripts/item.py` runs every step that needs no agent: `start`
(worktree and branch from `origin/main`, the item made active and the
pointer moved, reserved decision, row and question numbers that
`register_next.py` gives out first, and the brief), `resume`, `note` and
`run` for a session's state on disk, `gate`, `boards`, `promote`, which
pushes only on the promotion rule's evidence, `finish`, which removes the
worktree and branches once main's gate passed, `status`, `stalled` and
`report`. The state lives under the clone's common Git directory, which
every worktree shares. `landin-change` is rebuilt around those steps, with
the report form beside it, its question section last, and a part for a
session that dispatches items; `docs/process.md` has "Running an item".
This item was taken on with `start --adopt` once the script existed and
ran from there under it: its gate (run 44158296103), its boards (run
44163378136), its promotion, main's gate and its clean-up go through the
script. Closing it met two defects the script's controls had not: `run`
refused its documented form, on the gate's Python 3.12 after a first fix
under the shell's 3.14, and promotion while a boards run was going said to
dispatch one; both are fixed, and the Python the gate's script jobs run,
which nothing names, is `SR-1301`. A fresh session with no context resumed it from
disk with `item.py resume` while the gate ran; it said what the next step
was, but not what came after the wait, nor what to do with an
uncommitted file, which `resume` now says. Whether that run is this
item's exit evidence, with the start-to-finish run left to R16.10 and the
R17 gate, is Q-8; the R17 gate is not claimed until R16.10 has run start
to finish under the scripts. The manager's finding that `agent_hook.py
--check` sees only its own checkout is `SR-1300`.

### R17.50 — Gate wall time

Status: complete
Depends on: none

The gate's wall time cut: Xtensa shards, release build and queueing,
against a measured baseline. It takes on `SR-775`, the stock-user job's
unbounded package downloads, and `SR-1276`, `emit_manifest.py modes` printing
no progress, each a gate-time failure it meets, and two rows-to-be of
`roadmap/inputs/rows-to-be.md`:

- The release-build cache mostly misses (`SR-1296`). Its key names the runner image
  version, and GitHub serves two image versions within one run, so a job
  restores an entry only when it shares an image with the job that saved
  it: on run 44030898347 main's entry was saved on image 20261111.127.1,
  `linux-release-build` ran on 20261111.370.1, found none and took as long
  as the clean build. The key names what the C adapters compile against,
  the C library headers' and the C compiler's versions, instead.
- The cached Darwin release build (`SR-1297`), prepared on the local branch
  `ci-darwin-cached-release`: whole-file identity through `ZERO_AR_DATE=1`,
  a modelled Darwin end of 25 to 30 minutes by kind of change. It is
  rebased onto main, given the cache key's brace fix its Linux sibling
  got, and waits for the key decision above.

It also takes on `SR-195`, the Cortex-M shared-GDB session's failures on a
loaded host, and `SR-768`, the Xtensa corpus's heavy fixture timing out.

The baseline: the gate ended 44 to 51 minutes after its creation before
the second roadmap's last CI rework and 31.1 minutes on run 44030898347
after it, with `flake` (31.0) and the last Darwin job (28.3) last.
Exit evidence: the baseline and the new wall time of the complete gate,
each over several runs.

Done: the gate alone ends 30.3 to 30.5 minutes after its creation (runs
44076856511 and 44082338698, both complete passes; the latter on the
promoted tree, with boards dispatch 44087207692), against 31.1 on both
baseline runs, 44030898347 and 44052328931. Its Linux lanes now end about
21 minutes in rather than 26 to 31, and its end is the account's five
macOS runners, about 115 job-minutes of Darwin work; Q-6 asks about more
macOS capacity. Beside another item's gate the cap is shared: run
44062808053 took 51 minutes. The cache key names the C headers and
compiler (`SR-1296`), and the cache now saves time when it hits: GPRbuild
recompiled every unit whose source's time stamp a checkout had renewed, so
a restored tree saved nothing, and the sources' times now travel with it;
the cached Linux and Darwin builds take 1.6 and 2.1 minutes against 8 and
12 from clean. The Darwin cached build is on main (`SR-1297`), with
main's own entry and its release lanes ordered after the comparison. The
determinism manifests and `modes` deal requests to shards by key digest
(D1374), and `modes` reports progress (`SR-1276`); the flake builds in
three jobs; the stock-user downloads are bounded with an official-mirror
fallback (`SR-775`); and the `documents` job reads full history for the
register's age rule (`SR-1299`).

`SR-195`'s cause: GDB waits `remotetimeout`, two seconds by default, three
times for each reply and then carries on as if it were empty, so an
emulator stalled past that on a loaded host had its late `vCont?` reply
read as the answer to `vMustReplyEmpty`. The shared GDB server now sets
`remotetimeout` to each session's own limit, and the `cpu` lane holds it to
a stub that stalls `vCont?` seven seconds, failing under the default and
passing as served. `SR-768`'s: the Xtensa oracle judged a guest by wall time,
and the heaviest fixture, which needs 11 CPU seconds alone and 16 beside
two or four busy threads per hardware thread, took 32 and 70 wall seconds
there. A guest's 20 seconds are now the wall time less the time Linux kept
QEMU waiting to run; it passed with 16 of them at four threads per
hardware thread, a `nonterminating-control` guest that spins still ends at
its limit, and a host that starves a guest for ten times its limit is named.

### R17 gate
The third roadmap's checks pass on the live file; one item run start to
finish under the new mechanics.

Claimed at R16.10's close, Q-8's default: R16.10 ran under `scripts/item.py`
from `start` through its gates, boards dispatches, two promotions and
main's gates, five parallel streams in their own worktrees, and its
`finish` follows this commit; what in the scripts misled is in its report.

## R18 — refine's commands

`refine` becomes a dispatcher in cargo's manner: the compiler's own commands
stay built in, and a command that links little of the compiler, or is a tool
beside it, becomes its own executable `refine-NAME`. Its input is
`roadmap/inputs/command-inventory.md`: the thirteen commands, what each
links, the rules a command is held to, and eight questions with a default
each. Nothing in it is decided until R18.10 decides it. The items after
R18.10 are written as the inventory's defaults would shape them, and R18.10
may regroup them.

### R18.10 — Decide the commands

Status: complete
Depends on: R17

The maintainer answers the inventory's questions: lockstep linking of
shipped split commands, the discovery rule, what a contributed tool is
released from, the diagnostics a split or contributed tool emits, `lsp`
built in or split, how help and completion list external commands, and
whether cutting the edge from `Driver.Library` to `Driver.Loading` comes
first; and with them whether `dap` is built in or external. Retiring the
bare-source form, the inventory's third question, is already decided and is
not reopened. The output is each answer recorded as a decision in `spec.md`,
the classification of every command as built in or split, and the items
below confirmed or regrouped here.
Exit evidence: the decisions in `spec.md`; this phase's items match them.
Done: the maintainer answered Q-9 to Q-13 on 2026-11-18, each option 1,
and `spec.md` records them as D1383-D1387. `check`, `compile`, `run`,
`fmt`, `explain`, `lsp`, `version`, `help`, `completion` and `targets` stay
built in; `svd`, `bindings`, `site` and the new `dap` are split commands in
lockstep with the compiler's library (D1383). A shipped name is found
beside `refine` alone and any other on PATH (D1384). A contributed tool is
held to nothing and its codes never enter the catalogue; `refine explain`
forwards a code to the one tool claiming its prefix (D1385). The loading
edge is cut first (D1386). On Q-11's condition `refine` refuses an
incompatible `refine-NAME`, judged by a description each prints and, for a
shipped one, its source digest (D1387). R18.20 measures `Source_Maps` too,
R18.50 takes the check and the forwarding, and R18.60 is the split
`refine-dap`; `SR-1277`, `SR-1196` and `SR-1224` with `SR-1275` are scheduled on
R18.40, R18.50 and R18.70. Found on the way: the cut shrinks no executable
shipped today, since `fmt`, `explain` and `version` stay inside `refine`;
it matters for `refine-dap`, which reaches `Driver.Library` through
`Source_Maps`.

### R18.20 — Cut the loading edge

Status: complete
Depends on: R18.10

`Driver.Library`'s body withs `Driver.Loading` for one path helper, which
links the whole front end into `fmt`, `explain` and `version`, and into
`Landin.Source_Maps`, which `refine-dap` reads. The helper moves below
both, so each links what it uses (D1386).
Exit evidence: the release text of `explain`, `version` and `fmt`
measured before and after, near the inventory's 0.5, 0.6 and 1.9 MB, and
`Source_Maps`' closure without the front end.
Done: the helpers became the pure `Landin.Paths`, and `Driver.Library`
became `Landin.Library`, outside `Landin.Driver`, whose body every child
linked with the whole compiler (D1423). Release text of each command's
code closure, before and after: `explain` 6.79 to 0.49 MB, `version` 7.01
to 0.71 MB, `fmt` 7.02 to 1.86 MB; finding the library, 4 units and
0.09 MB. A program withing only the library linked 24.35 MB of text and
now links 0.36 MB. `Source_Maps` went from 7.26 to 6.55 MB and keeps the
front end, since it writes the map from a compilation (Q-19);
`scripts/tests/test_unit_closure.py` holds the library's closure, and
`scripts/unit_closure.py` measures any unit's.

### R18.30 — The docs agree with the tool

Status: complete
Depends on: R18.10

The disagreements the inventory found, each fixed on whichever side is
wrong: `refine targets --identify` against `docs/capabilities.md`
(`SR-1289`); L0004, L0009 and `docs/targets.md` sending the reader to
`refine --identify` (`SR-1290`); README's command table missing `targets`,
`completion` and `help` (`SR-1291`); the `Explain_Command` and
`Format_Command` comments (`SR-1292`, `SR-1293`); and a check that holds
`refine help reference` to the documents, which nothing outside the
`commands` suite does today (`SR-1294`).
Exit evidence: each row-to-be of `roadmap/inputs/rows-to-be.md` it names
closed; the new check refuses a command or flag the documents do not name.

Done: `docs/capabilities.md` says `refine targets --identify` is refused
and only the bare compatibility spelling prints the older summary; L0004,
L0009 and `docs/targets.md` send the reader to `refine targets`, which
lists the targets and their levels both promise. README's command table
has rows for `targets`, `completion` and `help` and both forms of `site`.
The `Explain_Command` comment names `citations.txt`, and the
`Format_Command` comment a directory operand. `refine help reference` is
recorded in `compiler/tests/commands.reference`: a commands-suite case
holds the record to the catalogue, and `check.py` holds README's command
table and `docs/capabilities.md` to the record, refusing a command or
option they do not name, with controls in
`scripts/tests/test_check_inventories.py`. The check found what the
inventory had called clean: `-h`, `--output`, `--option`, `--build-mode`,
`--toolchain`, `--linker`, `--define`, `--system-include-dir` and
`--stdio` were named nowhere in either document, and `--define` and `-h`
in no document at all; each is now named where its command is described.
The first gate (run 44324479031) found the cached release build's
`landin_tests` unequal to the clean build's in its line tables: GNAT's
checksum leaves out comments, so GPRbuild's checksum mode recompiled no
dependent of `landin-driver.ads` after a comment moved its lines.
`scripts/build.sh` now compiles again every unit whose ALI file names a
changed source, and says which file changed without calling it one the
compiler is not built from.

### R18.40 — Retire the bare-source form

Status: complete
Depends on: R18.10

`refine NAME` with an unknown NAME is read today as `refine check NAME`.
That form is refused, naming `refine check NAME`, so an unknown NAME can
name a command. A break of its own, promoted on its own, not held for
R19's window. Every command line `refine` prints for its reader is read
again with it, the closing hint "run it with `refine run ...`" included,
which a recorded report holds with the recording host's target
(`SR-1277`).
Exit evidence: the refusal and its explanation in the catalogue; every
fixture, script and document that used the form rewritten; no recorded
report holds a line that depends on the recording host.
Done: a request with an operand and no command is refused with L0002,
status 2, writing the request again after `check` or after the command
its options belong to, and a first word that is neither a source nor a
path is told that `refine help` lists the commands (D1463). The closing
line went with the form, so `SR-1277` is settled: the 24 reports that
held it are re-recorded and none names a target its fixture does not. A
fixture's `args` are `check`'s unless they name a command (D1464); the
test program, every lane, script and the release smoke test, and the
documents name their command. Found on the way: parallel compiles into
one directory refuse each other with L0005 (`SR-1343`); `SR-1287` fixed
at [1230].

### R18.50 — The dispatcher

Status: complete
Depends on: R18.40

`refine NAME` runs a built-in command; else, for a split command it was
built with, `libexec/landin/refine-NAME` beside the executable, found
through `Landin.Platform` as the library is, and nowhere else; else
`refine-NAME` on PATH (D1384). It refuses an incompatible one, with a
diagnostic that says what to do: each answers `refine-NAME --describe`,
and a shipped one's source digest must be `refine`'s own (D1387). Help
lists external commands under their own heading; completion delegates to
`refine-NAME --complete`; `refine explain` forwards a code outside the
catalogue to the one contributed tool claiming its prefix, and refuses
when none or several do (D1385). `refine version`
describes the installation it runs from: the split commands it finds, and
the `citations.txt` `refine explain` reads and whether it can (`SR-1196`).
The release archive, the flake and the release smoke test ship and run
every split command.
Exit evidence: the dispatch order pinned by fake-filesystem driver cases;
a shipped command of another digest, one without a description and a
contributed one claiming `L` each refused; a contributed test tool found
on PATH and its code forwarded in a native case; the archive and flake
carry `libexec/landin`.
Done: `refine NAME` dispatches its first word alone when it could name
a command and names no built-in one, and passes every word after it as
written (D1484). A split command is looked for at
`libexec/landin/refine-NAME` under the executable's prefix and nowhere
else, refused with L0694 when missing; any other name is the first
`refine-NAME` on PATH. Each is asked `--describe` within ten seconds and
refused with L0695 when its answer does not hold (D1387), and runs with
`LANDIN_REFINE` naming the refine that dispatched it (D1486). `--describe`,
`--help` and `--complete` are a split's whole contract (D1485): help lists
external commands under their own heading and `refine help NAME` runs the
command's own help (D1488), the bash, zsh and fish scripts hand an
external command's words to it, and `refine explain` forwards a code of
another prefix to the one contributed command claiming it (D1385).
`refine version` names the citations file and whether it can be read and
each split command (D1487), settling `SR-1196`. One list,
`compiler/ada/split-commands.json`, names the split commands; the digest's
inputs, the generated built-with list, `build.sh`, `package.sh`, the
flake, the release smoke test and `check.py` read it, and a case holds
that editing a split's own source changes the digest (D1483). It is
empty: the archive and the flake carry an empty `libexec/landin` until
R18.60 and R18.70 add to it. Lockstep is worded without the implementation
language, D1383 and D1385 amended, on the maintainer's answer of
2026-11-18, and Q-19 is answered. Pinned by the commands suite's `the
dispatcher` on the fake host and `scripts/tests/test_cli_native.py`'s
contributed tool on PATH. Found on the way: `item.py run` runs only in the
item's worktree (`SR-1353`), and `unit_closure.py --cut` reports closures no
link can have (`SR-1354`, scheduled on R18.70).

### R18.60 — `refine dap`

Status: complete
Depends on: R18.20, R18.50

The first new command: a Debug Adapter Protocol server over the GDB and
LLDB sessions the targets already script, the split command `refine-dap`
(D1383), in lockstep with `refine` (D1383), shipped in the archive
and the flake and run as `refine dap`, written to the split's rules from
its start.
It reads source maps without `Landin.Source_Maps`, which writes them from
a compilation and keeps the front end (D1423).
Exit evidence: `refine-dap` linked without the front end; scripted DAP sessions in the gate over GDB and LLDB, the
debuggers the targets script today, on every hosted target the debugging
suites run. A further debugger is its own adapter backend.
Done: `refine-dap` is the split command `refine dap` runs, listed in
`compiler/ada/split-commands.json` and so built, digested, packaged and
shipped as every split is. It frames the protocol as the language server
does and reaches a debugger through `Landin.Platform.Debugger_Session`:
GDB over GDB/MI, every request answered from GDB's records, and LLDB
through LLDB's own adapter, `lldb-dap`, relayed and renumbered, the
debugger chosen from the program's format (D1523). A launched program's
output reaches the editor through pipes GDB's shell redirects to, and
`attach` reaches a QEMU or `lldb-server` stub (D1524); library files map
one namespace at a time, since a checkout's library is the whole checkout
(D1525); a stop in `panic_handler` is an exception at the source of its
site (D1526); D1527 lists what is answered over GDB. Source tables are
read through `Landin.Site_Tables`, which `refine site` now shares and
which takes no compilation, so `refine-dap` links 18 units of the
compiler's sources and no front end, pinned in
`scripts/tests/test_unit_closure.py`. The dap suite holds it on the fake
host; `compiler/tests/dap/session.py` scripts a session through `refine
dap` over GDB in the `release` and `arm64-release` jobs and on RV64 under
QEMU's stub, and over LLDB in `darwin-host-release-2` and both FreeBSD
debugger jobs, the guest's `lldb-server` reached from the runner's
`lldb-dap`. Found on the way: the FreeBSD arm64 lane's refusal for a
missing UEFI firmware now says where it looked and what to install, and
looks beside the QEMU on the search path; a program or dispatched command
a closed pipe ends no longer reports itself as a failure (D1528); and the
gate's `measure-time` jobs take `refine`, not the last executable the build
names.

### R18.70 — The existing splits

Status: complete
Depends on: R18.50

`svd`, `bindings` and `site` become `refine-svd`, `refine-bindings` and
`refine-site`, each in lockstep with `refine` (D1383) and each
keeping its suites and its black-box "destroys nothing" and determinism
controls. Those controls take the command they test as an argument, so the
lanes' shared `--refine` becomes one helper (`SR-1224`), and
`compiler/tests/test_compile_publication.py` reports every selected
control's failure rather than the first (`SR-1275`).
Each moves out from under `Landin.Commands`, whose body withs the whole
compiler, and stops withing `Landin.Driver` for `Outcome`. Its own main
parses its own arguments and response files and answers `--help`,
`--describe` and `--complete`, the process surface that is its whole
contract with `refine`, and it enters `compiler/ada/split-commands.json`.
A closure pin for each main in `scripts/tests/test_unit_closure.py` holds
it without the front end, as D1423 pinned `Landin.Library`, and
`scripts/unit_closure.py` refuses or reports a cut parent a real link
would bring back (`SR-1354`). `svd` gains
toy-SVD goldens that run offline through the executable: the output
bytes, and the report and exit status of each fault code. The `SR-1224`
helper takes an executable path, so one suite runs `refine svd` or
`refine-svd`.
Exit evidence: each split linked without the front end; its black-box
suites, and every invocation of the old form, pass through the
dispatcher.
Done: `svd`, `bindings` and `site` are `refine-svd`, `refine-bindings` and
`refine-site`, entered in `compiler/ada/split-commands.json` and built,
packaged and shipped from it. Each is `Landin.Splits.Svd`, `.Bindings` or
`.Site` under `Landin.Splits`, which reads a split's own options and
response files, keeps `refine`'s shared presentation options and answers
`--help`, `--describe` and `--complete` (D1544); none withs `Landin.Driver`
or `Landin.Commands`, since a command's outcome, its presentation and
response files moved out to `Landin.Outcomes`, `Landin.Presentation` and
`Landin.Response_Files` (D1543). A closure pin per main in
`scripts/tests/test_unit_closure.py` holds `refine-svd` to 35 units,
`refine-bindings` to 33 and `refine-site` to 25, where `refine` links 155,
and `scripts/unit_closure.py` refuses a cut a link cannot honour
(`SR-1354`). An option written before a split's name is told its form, the
name first (D1545). Every lane takes `--refine` from
`scripts/lane_refine.py`, which runs `refine NAME` or `refine-NAME` by the
path it is given and judges a split by its description (`SR-1224`, D1307
amended); `test_compile_publication.py` runs every selected control and
lists the failures together (`SR-1275`); `devices/test.py`'s `ToyGoldens`
hold the toy device's output bytes and each fault code's report and
status offline through the executable. The fake-host suites call each
split's entry; the devices, bindings and publication controls pass
through `refine` and through each split directly.

### R18.71 — Concurrent compiles into one directory

Status: complete
Depends on: R18.50

Two `refine compile` runs that publish into one output directory at once,
as `make -j` starts them, can refuse each other with L0005, "another
process holds its lock": each inspects the other's live
`.refine-publication-` workspace and waits two seconds for its lock
(D1049). The refusal reads as a stale lock, and nothing says outputs that
share a directory cannot be built in parallel. It failed R18.10's
concurrent measuring builds, and the harness's own runtime fixtures, which
compile into one `bin` directory at once: `runtime/r420-vec-large-list`
failed `compiler-3` in gate run 44424959169's first attempt. This takes on `SR-1343` so that items and builds can work in
parallel.

Exit evidence: concurrent compiles of different outputs into one
directory succeeding, under a control that starts them together on every
hosted target the publication controls run; a workspace that is truly
abandoned still recovered or refused as D1049 says.
Done: builds of different outputs into one directory run at once. A
build syncs its workspace directory after releasing the workspace's lock
rather than while holding it, so the lock covers a rename or a removal
alone, and an inspector that has waited two seconds for a lock asks
whether the workspace's destination record carries its producer's live
write lease; while it does, it waits on for up to a minute, and a lock no
running build holds is refused after two seconds in words that say so
(D1583). `compiler/tests/test_compile_publication.py`'s
`host-concurrent-compiles`, which every hosted publication lane runs,
holds a live producer's lock for four seconds and starts twelve compiles
into one directory three times; at the item's base the first part failed
with the gate's L0005, and `host-foreign-entries` still refuses a held
lock with no producer. `scripts/measure.py` builds every configuration
into one directory again, the workaround R18.10 added for this refusal
having been reverted with its test. The L0005 explanation says builds may
share a directory. `SR-1343` is settled.

### R18.72 — A contributed `refine build`

Status: complete
Depends on: R18.50

`build` is reserved (D1484): `refine build` refuses with L0002, "build is
reserved for future project orchestration", even with a compatible
`refine-build` on PATH, which is left out of `refine help`, is an unknown
command to `refine help build`, and is asked for no code prefix, so
`refine explain` refuses its codes, and nothing says a `refine-build` was
found and passed over. The maintainer decided on 2026-11-19 to lift the
reservation when a compatible contributed `refine-build` is found, so that
it is dispatched, listed in help, asked for its prefix and given its
explanations as any contributed command is. Whether the reservation goes
outright or L0002 stays for the case where none is found is this item's to
design and record against D1484. Met writing refine-build, a contributed
build tool (its friction entry 16).

Exit evidence: a contributed `refine-build` that answers `--describe`,
`--complete` and `explain` (refine-build at ce197f9, prefix `RB`, is the
subject) dispatched by `refine build`, listed by `refine help`, shown by
`refine help build` and given `refine explain RB...`, under the
dispatcher's black-box controls; the case with no `refine-build` refused
as the item decides; D1484 amended.

Done: `build` is an external command's name like any other (D1603, D1484
amended): a `refine-build` on PATH is described, dispatched with
`LANDIN_REFINE`, listed by `refine help`, run for `refine help build`, asked
for its prefix by `refine explain` and handed its words by the completion
scripts, which no longer keep `build` back. With none on PATH, `refine
build` and `refine help build` are refused with L0002 saying that `refine`
has no build command of its own and runs a contributed `refine-build`,
rather than D1463's unknown command, which offered `refine check build`.
The dispatcher suite and a stand-in `refine-build` in
`scripts/tests/test_cli_native.py` hold both; refine-build at 265c539 was
dispatched, listed, helped, explained (`RB0102`) and completed by hand.
`docs/commands.md` states the whole contract a contributed command meets,
the description's keys and which may be empty, with an example the native
tests run (`SR-1417`).

### R18 gate
Every existing invocation works or is refused with its new form; every
split command ships in the archive and the flake and keeps its controls;
DAP sessions are scripted in the gate.

Claimed after R18.71, on main `9dcc76831`: every item's completing commit
passed its gate, its boards dispatch and main's gate. R18.40 refuses the
bare-source form, naming the command to write. R18.70's old forms pass
through the dispatcher with their controls, and R18.72 dispatches `refine
build` to a contributed command. The full
[pass](https://github.com/701-dev/Landin/actions/runs/44633646164) on that
tree, which main's gate reused, packaged the archive with `refine-bindings`,
`refine-dap`, `refine-site` and `refine-svd`, which `scripts/package.sh`
refuses to leave out. It built the flake's `.#refine`, which installs each.
It scripted DAP sessions over GDB in `release`, `arm64-release` and
`rv64-qemu-1`, and over LLDB in `darwin-host-release-2` and both FreeBSD
debugger jobs. A local run on the same tree reached each split's
`--describe` and `--help` through the archive's `refine` and the flake's.

## R19 — A smaller language

Breaking, serial. Its input is the list of simplification candidates,
SC-01 onward, each with a stable identifier. Nothing in the list is decided
until R19.10 decides it.

### R19.10 — Decide the candidates

Status: complete
Depends on: R18

The maintainer takes each candidate in or leaves it out, and groups the
ones taken in. The output is the accepted list in its groups, with each
group's items added here, and each answer recorded as a decision in
`spec.md`. Range subtypes (SC-16) are already decided: the maintainer
removed them on 2026-11-16, replaced by a `distinct` type with a checking
constructor, and R19.10 records that and groups it. The candidates that
wait on R20 (SC-17, SC-18) are recorded as such, not forced. The answers
on labels, `break with` and `complete` (SC-01, SC-02) settle E1.
It takes on `SR-1288`: the answer on SC-24 either folds the
value-model decisions or marks each boundary a later decision lifted, so
that a superseded boundary no longer reads as a live rule. SC-27 is
decided on a count, not an estimate: R19.10 counted the constructs over
the library, the examples and the corpus on checked trees with
`./scripts/dev-test.sh --census`, which completed `SR-1286`.
R19.10 also decides `SR-1237` itself, whether a type application's fixed
actual folds compiler facts and `sizeof` as an array length does or D135
stands, rather than leave it to R19.20, which runs only if SC-24 is taken.
Its answers are asked as Q-80 (the candidates and their groups), Q-81
(the value-model fold) and Q-82 (fixed actuals).
Done: the maintainer answered Q-80, Q-81 and Q-82 on 2026-11-21, and
each answer is a decision in `spec.md`. Ten candidates leave: SC-01
(D1651, which keeps labels and `when` and says what D157, D158, D159,
D234 and D430 keep), SC-05 (D1652), SC-03 (D1654), SC-22 (D1655), SC-09
(D1656), SC-04 (D1657), SC-08 (D1658), SC-10 (D1659), SC-13 (D1660) and
SC-06 (D1662); SC-16 is recorded as D1661. SC-02, SC-07, SC-11, SC-12,
SC-14, SC-15, SC-19, SC-20, SC-21, SC-23, SC-27, SC-28 and SC-29 stay,
SC-17 and SC-18 wait on R20, and SC-26 is R19.30's (D1653). SC-24 and
SC-25 fold (D1664), so R19.20 runs. A fixed actual folds as an array
length does (D1663), which settles `SR-1237`; D1651 and D1653 settle
`E1`; `SR-1288` moves to the fold's item. The maintainer named no groups,
and the five below group the removals by the part of the compiler each
touches, the declaration spellings taking D1663 with them. The census,
`./scripts/dev-test.sh --census`, completed `SR-1286`; the checker's
reading is `roadmap/inputs/value-model-reading.md`. The item's closing
commit is the first on R19's integration branch, `r19-integration`, made
from main, and does not reach main before R19's gate.

### R19.20 — How far the checker folds

Status: complete
Depends on: R19.10

Taken only if the value-model fold (SC-24) is accepted. It reads the
checker and lowering against D24-D109 and says which per-slice paths
collapse into one rule and which stay, starting from R19.10's sampled
reading, [`roadmap/inputs/value-model-reading.md`](roadmap/inputs/value-model-reading.md). The fold's item takes its scope
from this reading.
Done: `roadmap/inputs/value-model-fold-scope.md` reads all 376 citing
lines and the 86 decisions. Thirteen rules survive, which hold 21 live and
16 partly live decisions, and the other 49 are superseded. The sample
missed four checker sites that repeat the general dispatch: the runtime
halves of a struct literal's and a variant payload's array field, the
scalar `zeroed` allow-list and two refusals in `Synthesise`. It also
missed two inline `zeroed` clears in lowering and a third scalar-element
boundary. That boundary, at module scope, D26 and D35, is outside
D1664's words and is asked as Q-122, kept until answered. The reading
decides the diagnostics the shared check gives, that array fields become
general places, and the fold's order after R19.30. The fold is size L.

### R19.30 — One write order for an aggregate assignment

Status: complete
Depends on: R19.10

SC-26, a behaviour fix as much as a simplification. D29 writes a literal
into its destination element by element; D209 keeps array operands whole
before writing. One rule for both, with in-place writing where no overlap
is shown. Taken unless R19.10 leaves it out.
Done: D1827. An array literal, mixed repetition or struct construction
assigned to a place reads the place as it was before the assignment and
changes it only once complete, as D209's operators do; the write orders
of D29, D37, D52, D53, D64, D65 and D72 are superseded. Lowering writes
in place unless the value names the destination, holds an exit, or, by
how the destination is reached, calls or reads through a pointer, slice
or inout parameter; then it builds a temporary and copies it once. Every
recorded positive program, the library included, lowers as before, so
`hosted/events/events.ldn:158`, the library's one site, takes no copy.
Eight runtime fixtures pin the new order, two renamed to
`reads-old-value`, and a ninth the alias cases. `SR-1538` and `SR-1539` were
filed for refusals met on the way.

### R19.40 — The migration aid

Status: complete
Depends on: R19.10

A `refine fix` rewrite for every accepted change that is mechanical, and a
refusal naming the replacement for every removed form. It grows with each
group item, which lands its rewrite with it. The same command applies the
exact fix a diagnostic carries, which `SR-1242` asks for.
Done: `refine fix` checks a program as `check` does, applies every exact
fix its report carries and checks again until none is left, through an
overlay, so a fix a refusal hid is applied once the refusal is mended and
nothing is written until the last pass; `--check` writes nothing and fails
when a fix would apply, and a likely fix is never applied (D1847). A
removed form's rewrite is its refusal's exact fix, written once in the
stage that refuses it, so each group item's rewrite reaches the report,
the language server and this command together, and a group item adds a
refusal with its fix rather than an entry in a table of this command's.
The routine that applies edits moved from the test harness into
`Landin.Diagnostics.Applying`, and an insertion at the offset a
replacement starts at is now applied before it rather than into it. It
settles `SR-1242`, whose row is deleted.

### Groups accepted in R19.10
One item per group, each depending on R19.10 and on R19.40; the fold's
item also depends on R19.20 and R19.30. Each removes its forms from the
grammar, the highlighters, the tour and `spec.md`'s rules, marks every
decision the removal withdraws as superseded by the one that took it,
refuses each removed form with its replacement named, lands its `refine
fix` rewrite in R19.40's command, and rewrites the corpus, the examples,
the library and the prototypes' live text that wrote the form.

### R19.50 — Loops are statements

Status: complete
Depends on: R19.10, R19.40

SC-01 and SC-05: `break with` and `complete` leave (D1651), and so does
`try for` (D1652). Labels and `when` stay, so D157, D159, D234 and D430
are amended rather than withdrawn, as D1651 says clause by clause, and
L0332 becomes the refusal of `with` after any `break`.

Exit evidence: a negative fixture for each removed form naming its
replacement; `refine fix` rewriting a `break with` search loop into a
mutable local and a plain `break` where the rewrite is mechanical; the
labelled-loop and labelled-block fixtures unchanged and passing; the
complete gate on the item's commit.
Done: the parser refuses each removed form by the shape it was written in,
`with` and `complete` being names now (D1867): a loop where a value belongs
is one L0332 against the loop, a `break with` to a statement loop or block
is L0332, and a `complete` block or `try for` is L0696, a new code for a
removed form whose note names the replacement. A search loop that is the
value of `name: T = loop` or `name = loop` is rewritten by an exact fix into
a mutable local written before each plain `break`, a literal `complete`
value moving to the declaration, and a `complete` block no `break` skips
becomes a bare block after its loop (D1868); `refine fix` rewrote 17 of
the 25 corpus programs that kept a form, three of them in part, and the
rest, inferred `:=` loops, non-literal `complete` values and `try for`,
were rewritten by hand. The checker and
lowering lost their loop-value, completion and fallible-traversal paths, and
nine fixtures that pinned them went or became refusals. D157, D158, D159,
D180, D225, D234, D382 and D430 are marked superseded or amended; D1652's
list of six citing decisions held four that matched only "entry for".
`SR-1558` was filed for `refine fix` applying unrelated warning fixes.

### R19.60 — One spelling for each declaration

Status: complete
Depends on: R19.10, R19.40

SC-03, SC-04, SC-08, SC-09 and SC-22: anonymous functions (D1654), a
written `in` (D1655), several names in one declaration (D1656), the
inline named struct (D1657) and selected-name imports (D1658) leave. With
them the additive rule that a fixed actual folds as an array length does
(D1663), which amends D135 and D1321.

Exit evidence: a negative fixture for each removed form naming its
replacement and a `refine fix` rewrite for each, all five being
mechanical; [1795]'s `->` lookahead gone from the grammar and the
tree-sitter grammar; a positive fixture applying a type to
`compiler.word_size` and to `sizeof` of a scalar; the complete gate on the
item's commit.
Done: anonymous functions, a written `in`, several names in one binding,
field or atom declaration, the inline struct declaration and selected
imports are refused as L0696, each naming its replacement and carrying its
rewrite as an exact fix (D1654-D1658): the parser refuses the first four,
and resolution the selected import once its uses are bound, so the fix
qualifies each of them. D1887 counts atom lists and struct fields among
the declarations that name one thing, D1888 fixes the rewrites' details
and D1889 how a type argument is told from a fixed actual, which now folds
what an array length folds (D1663). [1795] and the tree-sitter grammar lost
the inline body and the `->` lookahead it needed. `refine fix --allow all`
migrated the corpus, and an L0696-only script the negative fixtures, whose
own refusals a full `refine fix` would have mended (`SR-1558`); seventeen
fixtures that pinned only a removed form left with it. SR-1568 is filed for
the anonymous-function paths the stages after the parser still hold.

### R19.70 — Range subtypes become distinct types

Status: complete
Depends on: R19.10, R19.40

SC-16, as D1661 records: `T range a .. b` leaves, and a value known to lie
in a range is a `distinct` type made by a checking function. D188, D236,
D1086, D1087, D1088 and D1100 are withdrawn, [1730] is rewritten around
the checking function, and prototype 1's `baud_rate` is rewritten so. The
compile-time refusal of an out-of-range constant goes with them.

Exit evidence: the negative fixture refusing `range` in a type names the
distinct type and its constructor; a runtime fixture whose checking
constructor fails outside the range; the complete gate on the item's
commit.
Done: `T range a .. b` is refused as L0696, naming a `distinct` type over
the base and a checking function and carrying no fix, since every use that
stored a base value changes type with it (D1907); an exclusive bound is
refused the same way. The parser keeps only the base type, the syntax node
went, and with it the checker's constraint table, owed checks, the six
refused composite positions and the `range a..b` signature text, about two
thousand lines; `Range_Check` stays for the checks that still use it.
D188, D236, D1086, D1087 and D1088 are marked superseded, D1100 amended,
the `subtype.range` guarantee row went and `distinct.identity` covers [0660]
and [1730], which a runtime fixture now executes. [0660] and [1730] teach
the checking function, and prototype 1's `baud_rate` is one. No source was
migrated by `refine fix`, there being no fix: thirty-two fixtures that
pinned only range subtypes left, nine that used one in passing were
rewritten by hand, one of them renamed, and `negative/range-subtype-is-a-distinct-type` and
`runtime/range-checking-constructor-fails` are the exit evidence. No
measured workload wrote a range subtype, so no baseline moved. `SR-1578` is
filed for Cortex-M's partial-bound `Range_Check` paths, whose only case
compiled a range subtype.

### R19.80 — One-atom pointer unions, written layout and named operands

Status: complete
Depends on: R19.10, R19.40

SC-10, SC-13 and SC-06, the three that reach the backends: a pointer union
holds one atom (D1659), so the two-cell form leaves every backend's IR,
call convention and widening; `layout(optimal)` leaves (D1660); and the
positional `assembler.block(text, value)` leaves (D1662), with the two
probe call sites in `environments/cortex-m/probes/core-cpu.ldn` rewritten
to the operand form.

Exit evidence: a negative fixture for each removed form naming its
replacement; the build-modes comparison and the emit manifest unchanged
for every program that wrote none of the three; the Cortex-M lanes passing
with the rewritten probes; the complete gate and a `scope=boards` run on
the item's commit.
Done: a pointer union of two or more atoms is refused as L0696 by the
checker, written in place, through an alias or in a template whether or
not it is applied, naming a one-atom union beside an error set or a struct
of a state and a pointer, with no fix (D1659); the two-cell aggregate left
checking, the IR, lowering, the verifier, scalar replacement, in-place
parameters, the dump and DWARF, with D874's route and the code cell's
reserved zero, and an error set holding a pointer keeps its own refusal.
`layout(optimal)` is refused by the parser, which the grammar now agrees
with, with no fix since its order depended on the target (D1928); the
layout plan lost its order, natural size and saved bytes, and the build
report the fields that showed them. `assembler.block(text, value)` is
refused by the parser with one exact fix that writes `inout value: u32 at
r0 = value` and doubles the text's braces (D1927), and the IR verifier now
holds every operand but a discarded output to a name. D210, D230, D235 and
D874 are superseded, D248 and D429 amended. `refine fix` migrated the three
positional calls in `environments/cortex-m/probes/core-cpu.ldn` (the brief's
two plus a third), `runtime/assembly-operand-free` and
`positive/r670-scalar-assembly`; no union or layout source could be, there
being no fix. Twenty-seven fixtures that pinned only a removed form left,
five were renamed, eleven rewritten by hand, and
`negative/pointer-union-holds-one-atom`,
`negative/layout-optimal-places-fields-as-written` and
`negative/assembly-positional-value-is-an-operand` are the exit evidence.
An atom outside a one-atom union is now refused naming the union and its
atom, a finding met on the way. No measured workload wrote any of the
three, so no size or cycle baseline moved.

### R19.90 — The value model folded

Status: complete
Depends on: R19.10, R19.20, R19.30, R19.40

SC-24 and SC-25, as D1664 records, in the scope and order of R19.20's
reading, `roadmap/inputs/value-model-fold-scope.md`. The 47 superseded
decisions and the 2 that refused syntax are marked, and the 16 partly
live decisions have their false sentences named. The checker's per-slice
sites collapse into `Check_Contextual_Value`: the declaration gate down
to [1940]'s refusals, the binding and assignment dispatch, the runtime
halves of `Check_Array_Field` and `Check_Fixed_Array_Payload`,
`Is_Zeroed_Scalar_Place` and `Synthesise`'s two refusals.
`Admit_Array_Field` goes, because array fields become general places.
Lowering's three inline sites collapse into `Write_Shaped_Value`, after
R19.30 has settled its write order. A counted repetition and `lenof` of
a literal take any element shape, and so does an inferred module array,
a literal or a counted repetition (D26, D35), as the maintainer's answer
to Q-122 chose. Comments, notes and fixture summaries are
re-pointed to the surviving rules. This takes on `SR-1288`.

Exit evidence: no fixture pinning a surviving rule of D24 to D109
changed in meaning; diagnostic changes from L0304 to L0301 listed in the
commit; positive fixtures for a repetition, a `lenof` and an inferred
module array of a non-scalar element; the build-modes comparison and the manifest over lowering's
collapse; the complete gate on the item's commit.
Done: 47 of D24 to D109 are marked superseded, D63 and D73 as refused
syntax later enabled, and 17 partly live ones name the sentences that no
longer hold, D26 among them once D1947 lifted its scalar element; D32
states the compact whole-array rule D28 and D30 first did, and 159
fixture summaries cite the rule that still decides. The checker's gate
keeps only [1940]'s module refusals and "needs a named body or an
initializer"; a binding's and an assignment's aggregate, array and scalar
`zeroed` values, and the runtime halves of `Check_Array_Field` and
`Check_Fixed_Array_Payload`, are one `Check_Contextual_Value` call each;
`Is_Zeroed_Scalar_Place` and `Admit_Array_Field` left, and `Selected_From`
types a whole array field wherever a selection reaches it. `Synthesise`
keeps its refusal of a whole array or struct field where another type is
wanted, in the words it uses for a whole name, since the general mismatch
lost the erased view's `any(addr ...)` hint. A counted repetition, `lenof`
of a literal and an inferred module array take any element shape (D1664,
D1947), through one `Infer_Element_Shape`; five refusing fixtures became
positive ones and `runtime/r1990-repetition-and-lenof-of-structs` runs
them. A match alias of an array is still never copied (D85). Lowering's binding and assignment inline writes went to the general
writer with the recorded IR of every existing program unchanged. No code
moved from L0304 to L0301; twenty-two negative fixtures keep their codes
and take the general check's words, a `zeroed` report still pointing at
the written type. The item removed no form, so it has no `refine fix`
(D1847). `check.py`'s refusal of a pinned fixture that does not exist no
longer assumes it was retired, a finding met on the way. `SR-1288` is
settled.

### R19 gate
R19's breaking window: every accepted group, R19.30 and R19.40 integrate on
one branch and reach main together in one promotion, so main never carries
half of the breaking changes and no release falls between them. Every
removed form is refused with its replacement named, and `refine fix`
rewrites the mechanical ones. The corpus, the library and the examples are
rewritten, and the prototypes reread.

Claimed after R19.90, on `r19-integration` at `b437817bc`, the window's
one promotion to main: every item's completing commit passed its gate on
that branch, and the integrated tree, with main `cfc977b79` merged in,
passed the full
[pass](https://github.com/701-dev/Landin/actions/runs/45022600141), a
[boards dispatch](https://github.com/701-dev/Landin/actions/runs/45025032992)
and the branch's own push gate. Each removed form is refused, as L0332 or
L0696, by a negative fixture that names its replacement; `refine fix`
rewrites the mechanical ones, the loops of R19.50, the five declaration
spellings of R19.60 and the positional assembly block of R19.80, and the
range subtype, the several-atom pointer union and `layout(optimal)` carry
none, since their rewrite is the program's design. The corpus, the library
and the examples compile in that pass with no removed form left. The
prototypes were reread against the ten removals: prototype 1's `baud_rate`
is a distinct type with its checking function, its `available` takes no
written `in`, and prototype 3 imports `core/sort` whole; the forms still
written in their findings sections and in the tour's `WHAT WAS TRIED AND
DROPPED` are kept as rejected wording.

## R20 — The standard library reviewed

A review of structure and concepts, on the smaller language. Its input is
`roadmap/inputs/library-inventory.md`: the module graph, the concepts, how
capabilities are received, the conventions and their departures, and ten
questions with a default each. Its result is one list of breaking renames
and restructurings, applied at once. The items after R20.10 are written as
the inventory's defaults would shape them, and R20.10 may regroup them.

Window: r20-integration

R20 has a breaking window of its own after R19's: each integration
branch lives one phase, and a release can fall between the two, while
R19.40's `refine fix` is reused for R20's renames. `iterable`, `zeroable`
and `caller`, which R19 leaves to R20, land in R20's window.

### R20.10 — Decide the review's questions

Status: complete
Depends on: R19

The maintainer answers the inventory's questions: when a routine takes
`type is C` and when `any C`; one task concept for fibres and threads;
whether `core/failure` keeps importing the modules whose atoms it names;
`platform/posix` below the protocol concepts; how the I/O concepts group;
one name per idea; parameter order; a locale as an explicit value; and
whether the modules only fixtures import have their consumers. How R22
generates its tables is already decided, and the inventory's question on
it is not reopened. With these come the questions R19 left here:
`iterable` (SC-17), `zeroable` (SC-18) and `caller`, and C3, whether a
call tree's host authority gets a checkable boundary. The output is each
answer recorded as a decision in `spec.md` and the items below confirmed
or regrouped here. Its answers are asked as Q-143 to Q-151, the
inventory's questions in its order without the eighth, and Q-152 to
Q-155, `iterable`, `zeroable`, `caller` and C3.
Exit evidence: the decisions in `spec.md`; this phase's items match them.
Done: the maintainer answered Q-143 to Q-155 on 2026-11-22, each a
decision in `spec.md`, D1948 to D1960. A routine takes `type is C` and
`any C` is for a value that stores or mixes providers (D1948); `any C`
converts to `any P` for a concept it builds on, and fibres and threads
share one task concept (D1949), which adds R20.11; `core/failure` keeps
its registry until a firmware image shows a cost (D1950);
`platform/posix` moves below the protocols (D1951); the I/O concepts stay
narrow and `world` loses `lent` (D1952); one name per idea (D1953);
subject, capabilities, inputs (D1954); a locale is an explicit value
(D1955), which R22.50's text takes; the three fixture-only modules stay
(D1956); the library declares `iterable` and its containers conform
(D1957); `zeroable` stays (D1958); `caller` stays with a library routine
(D1959); and a call tree's host authority stays a convention (D1960),
which retires C3. The items below keep the inventory's grouping, each
naming its decisions. The closing commit is the first on R20's
integration branch, `r20-integration`, made from main, and does not reach
main before R20's gate.

### R20.11 — An `any` converts to its concept's parents

Status: complete
Depends on: R20.10

D1949: an `any C` converts implicitly to `any P` for every concept `P`
that `C` builds on, keeping its data pointer and taking `P`'s part of the
table; [1370] and the checker say so, and the backends lower it on every
target.
Exit evidence: a runtime fixture converting along a chain of parents on
every target the gate runs; the refusal where `P` is not a parent.
Done: an `any C` converts to `any P` wherever one is wanted, in a
binding, an assignment, an argument, a result or a field, for every
concept P that C builds on; [1370] and [1390] say so. Its table is D1968's:
an erased table of a concept some `any` is converted from names, after
its entries, the same type's erased table of each concept it builds on,
which the IR's `Evidence_Parent` reads and every backend emits; a
conversion no table of C reaches traps as D377's call does.
`runtime/any-converts-to-parents` runs a chain of three concepts on the
seven product targets and the firmware corpus, and
`negative/any-converts-only-to-parents` refuses a child's and a
sibling's `any`, now naming both types and the `any(addr ...)` that
builds the other, where L0301 had said only that the erased type
differed. `SR-1539`, whose activation the changed refusal met, is taken: a
pointer type applied to an integer is refused naming `ptr(...)` and
[0470] (`negative/pointer-type-applied-to-an-integer`).

### R20.20 — How a capability is received

Status: complete
Depends on: R20.10

The rule for `type is C` against `any C` (D1948) and the order of
parameters (D1954) written into `core/README.md`'s conventions, and every
routine that departs from them put on the breaking list.
Exit evidence: the conventions stated; a check, where one is mechanical,
that holds the library to them.
Done: `core/README.md`'s conventions state both rules, and D1988 says how
they read where the decisions are silent: a concept entry takes `any C`,
since an entry may not take a type of its own; the subject of a
provider's own operation is the provider; the evidence concepts' values
are inputs; a platform binding keeps the system's order. A full
`python3 check.py` holds every public routine and concept entry of the
library to what is mechanical, an erased provider not kept, a capability
after an input, a `caller` before the end, with a table of the departures
the list reshapes that refuses an entry once it no longer departs. Its
controls are `LibraryConventions`. The section "How a capability is
received" of [the breaking list](roadmap/inputs/breaking-list.md) names
seven: `text.format_onto`, which
takes `any outlet` without keeping it; `stacks.round_over`,
`fake.network_over_turns` and the `file_system` entry `make_temporary`,
each with a capability after an input; and `mem.transfer`,
`mem.transfer_prefix` and `random.shuffle`, whose subject is not first,
which the check cannot see. Reordering `mem.transfer_prefix` leaves the
old call valid, so R20.60 must refuse the old form some other way.
A misleading follow-on refusal met on the way joined `SR-1538`.

### R20.30 — The concepts

Status: complete
Depends on: R20.10, R20.11

`core/fibre`'s `task` as the one task concept, which `hosted/thread`
uses, and the fibre group holding one `any scheduler` (D1949); the I/O
concepts kept narrow, `world` giving each of its parts by R20.11's
conversion so `lent`, `lent_writer` and `writer_of` leave, and a pair
merged only where its receivers and failures can be one (D1952); the
library's `iterable`, which `for` takes and `core/map` and `core/tree`
conform to, with `fallible_iterable` out of the tour (D1957); and a
`core` routine that takes its call site through `caller` (D1959).
`zeroable` stays (D1958). It takes on `SR-1284`, which D1957 answers: the
library declares `iterable`. Each change goes on the breaking list.
Exit evidence: the concept changes on the list, prototype 3's concept
uses reread against them.
Done: the concepts section of
[`roadmap/inputs/breaking-list.md`](roadmap/inputs/breaking-list.md)
lists each change, made on `r20-integration` for R20.60 to refuse the old
forms. `core/iter` declares `iterable` and `for` takes no other concept of
that name, L0348 naming the module for a program's own (D2048); the map
conforms over its live entries in insertion order and the tree over its
node identifiers, which `runtime/for-over-map-and-tree` walks on every
hosted product target, `runtime/library-shared-iter` walking a
conformance on Cortex-M0 and RV32, and `fallible_iterable` has left
[1320].
`core/fibre`'s `bridge`, a routine, a state and a keeper of the first
failure, is the one task both groups start, `hosted/thread`'s `job` and
its `launch` leaving, and a fibre group holds one `any scheduler`, the
`unused` provider and its flag leaving (D2049). `io.writer_of`,
`lent_writer` and the adapter left, the examples handing `diag.stream`
the world, and no pair of I/O concepts merges (D2050). `core/panic` gives
`require` over a `call_site`, the tour's [1040] and the C guide's `assert`
now pointing at it (D2051). Prototype 3's concept uses were reread: its
iteration sketch conforms to `iter.iterable`, and its allocator, sort and
`any drawable` uses are unchanged. `SR-1284`, which D1957 answered, is
taken. The server example's comment said an `any turns` does not convert
to an `any scheduler`, and `core/diag` and `core/io` said an erased world
was not a writer, which R20.11 had made untrue; each now says it
converts.

### R20.40 — Layers and consumers

Status: complete
Depends on: R20.10

`platform/posix` moved below the protocol layer as far as its types
allow, `hosted/system` adapting it (D1951); what importing `core/fibre`
costs a firmware image measured, and `core/failure`'s registry kept or
split on that measurement (D1950); an example program for `core/random`
and `hosted/thread`, `core/io/fake` kept as a test provider (D1956).
Exit evidence: the import graph without the upward edges; the firmware
measurement recorded.
Done: `platform/posix` imports nothing that reaches `core/io` or
`core/net`, and `check.py` refuses a `platform` module that does, naming
the chain (D1951). The layer keeps `core/text` for host strings, and three
things moved (D2008): the environment variable's record is
`text.host_variable`, with `io.variable` its alias for this window; a
`net.address` becomes the system's record and back in `hosted/system`,
`system.internet_address` and `system.address_of`, over posix's new
`internet_record` and `endpoint_of`; and `posix.reason` and the combined
words are `system.reason` and `system.words`, `posix.words` wording an
errno alone. Each move is on `roadmap/inputs/breaking-list.md` for R20.60's
refusals and `refine fix`. Measured on Cortex-M0 (D1950), importing
`core/fibre` adds no byte to an image, running a group of fibres adds
6,172 bytes, all of them `core/fibre`'s, and only a call of `failure.words`
brings in the registry, 1,852 bytes; the registry stays one, and the
freestanding lane refuses a fibre image that holds `words`. `core/random`
and `hosted/thread` have example programs on the examples page,
`runtime/example-dice-and-cards` and `runtime/example-primes-on-threads`,
and `core/io/fake` keeps its place as a test provider (D1956). A match
cannot name an atom set as one arm, which made `system.words` name forty
atoms; that is `SR-1609`. The dice example pads its columns by hand, as
`SR-285` records. `docs/library.md` said calling `failure.words` costs
about 6 KB on Cortex-M0, which the measurement contradicted, and now says
about 2 KB. A `Kept:` line written in a merge's resolution does not
restart a row's count, `SR-1610`.

### R20.50 — One name per idea

Status: complete
Depends on: R20.10

One name each for absence, running out of room, the end of an iteration,
a length and giving storage back, and one meaning each for the names
that carry several (D1953). Each rename goes on the breaking list.
Exit evidence: the list's naming entries, each with its old and new name.
Done: the list's naming entries are the names section of
[`roadmap/inputs/breaking-list.md`](roadmap/inputs/breaking-list.md),
which this item began for R20.20, R20.30, R20.40 and R20.50 to share,
since the items named a breaking list that had no file: 45 renames, each
with its old and new name, its decision and whether `refine fix` rewrites
it, and what each idea keeps. Absence is one atom, `mem.not_found`
(D2028); running out of room `mem.out_of_memory` (D2029); the end of a
walk `at_end`, never a failure (D2030); how many items a value holds its
`length` (D2031); giving storage back `release` and `core/mem`'s three
`allocate`/`release` pairs, closing `close` (D2032); `host` the provider
and the system's string an `os_string` (D2033); and `new`, `used`, `at`,
`space`, `cursor` and `entry` one meaning each (D2034). Three spellings
are the maintainer's, Q-171 to Q-173, and the list is written with their
defaults. Overlaps were agreed with their owners: R20.40's moved
`io.variable` record, whose alias leaves at R20.60, and the `entries`
parameter R20.20 reorders.

### R20.60 — The breaking list applied

Status: complete
Depends on: R20.20, R20.30, R20.11, R20.40, R20.50, R19.40

The list, applied on R20's own integration branch and promoted alone in
one promotion: every renamed or moved name refused with its replacement,
and rewritten by R19.40's `refine fix` where the rewrite is mechanical.
Exit evidence: the library, the corpus, the examples and the documents
rewritten; `docs/library.md` regenerated.
Done: the library declares only the list's new forms and the library, the
corpus, the examples, the prototypes' code and the documents use them;
`docs/library.md` is written by hand, not generated, and was rewritten, the
site's page being generated from it. Q-171 to Q-173 were answered as
recommended. `mem.transfer_prefix`, whose old order still checked, is
`mem.copy_prefix`, target first (D2128). The compiler keeps the removed
names in one table, `Landin.Modules.Removed`, and refuses each with L0696
naming its successor, a qualified name, a field, a struct value's field
or a conformance label alike; a mechanical rewrite is the refusal's exact
fix, which imports the successor's module and drops a merged atom its set
already names, and `map.end_of_entries`, `io.writer_of` and
`io.lent_writer` are refused saying what to write (D2129). L0348's fix
replaces a program's own `iterable` written as [1320] wrote it with
`iter.iterable`. `check.py`'s table of convention departures is empty.
The fixes suite now checks a fixture whose program or result imports the
library against the real library, which it could not before. A call of a
routine in its old parameter order, a renamed parameter label, the old
`io.variable` type and `posix.words` of a library atom resolve and are
refused only by their types, which is `SR-1670`; a doubled atom in a set
is accepted silently and an unimported library module's name is refused
without naming the import, which is `SR-1671`.

### R20.61 — Refusals that say what to write

Status: complete
Depends on: R20.60

The refusals R20.60's renaming meets next, each made to say what to write
instead: `SR-1406`'s five refusals met writing refine-build and the three
since, `SR-733`'s alias spelled by its structure and L0696 at an alias
application, `SR-1538`'s `-> none` named by neither refusal a newcomer meets,
and `SR-1609`'s union of atom sets, which Q-183 answered: no new form, but
[1210] says a union is split by naming one side's atoms and `_ (rest):`,
and L0333's note at an arm naming a set and L0301's at a wider atom
subject say so. `SR-1558`'s `refine fix` gains a selection of the codes
whose fixes it applies.
Exit evidence: a negative fixture for each refusal pinning its new note,
`docs/diagnostics.md` and the tour sentence agreeing with them, and
`refine fix` applying one code's fixes alone in a native case.
Done: each refusal says what to write. A signature followed by `=` names
`-> none`, `-> ()` is refused with `none` as its exact fix, and a refused
concept entry no longer leaves the concept "never closed" (D2168, D2169);
an import segment that is no identifier is refused at the character that
breaks it (D2170); `lenof` before a text literal says to bind the text
first (D2171); and a bare `else begin` after a call inside an `if` arm that
goes on is refused at that `else`, naming `else (problem)` (D2172, [1820]).
L0201 names a sibling file's import, and a library module the file does
not import, with the import as its fix (D2174); a set naming one atom twice
is the warning L0697 with its fix (D2175); `utf8` and `[]u8` name their
conversions and a text literal for a `[]u8` formal is bound first (D2176);
L0314 spells `escaping inout` (D2177); L0303 at a `[]mut` parameter written
`inout` drops the `inout` (D2178); and L0333 at an arm naming a set, L0301
at a wider atom value and [1210] say a union is split with `_ (rest):`
(D2179). The old parameter orders, `entries:`, `io.variable` as a type and
`posix.words` given a library atom are L0696 with their rewrites where the
argument kinds tell the order apart (D2180); D1659 at an alias application
names the template (D2181); L0301 at a function value names the part that
differs (D2182); and L0344 spells a written alias (D2183). `refine fix
--code=CODE` applies only the named codes' fixes (D2186). This settles
`SR-1406`, `SR-733`, `SR-1538`, `SR-1558`, `SR-1609`, `SR-1670` and
`SR-1671`. Fixed on the way: a second refused import was silent after the
first; check.py's derivable-negative refusal did not name its exemption
list; L0301 called a concept or function value "something unknown"; and
the gate's fuzz round met D1656's rewrite raising a parser defect at a
declaration of several names whose `=` ends the source. Filed:
SR-1693, a library module the program does not reach is still a plain
misspelling.

### R20.62 — Tools that know a window

Status: complete
Depends on: R20.10

The process tools a window's items worked around, mended before R20's
promotion meets them: `SR-1445`'s `item.py`, which starts, pushes, promotes
and finishes against main only; `SR-1548`'s row ages counted across a
window's merge and a `Kept:` line in a merge's resolution; `SR-1455`'s
mirror failure judged as the push's; `SR-1415`'s and `SR-1446`'s row
deletion, questions and decision numbers outside an item; `SR-1466`'s
`run_logged.py --stop` leaving a child holding the build lock; `SR-1467`'s
boards README and ssh options; and `SR-1639`'s `agent_env.sh` cache holding
the caller's environment.
Exit evidence: each script's tests pinning the change, `docs/process.md`
and the landin-change skill saying the window's steps, and R20's
promotion refused for no row its merge alone aged.
Done: R20 declares `Window: r20-integration`, and `item.py` starts,
merges, lands and finishes the phase's items on it, without boards and
with a token of its own, and finishes an item landed by hand. `push` and
`promote` judge a push by GitHub and report the mirror's refusal with the
command to retry; `queue --take` holds a token for work that is no item;
`status` refreshes unfinished runs. A row's age counts only items
completed after it on its line or after the joining merge, and a `Kept:`
line written in a merge counts, so R20's promotion ages no row by the
merge alone. `register_next.py` deletes rows with their citations quoted
and the page regenerated, and gives out decision numbers; a question names
the work that asked it. `run_logged.py` ends a run's process group and a
lock wait names a holder by its descriptor. The boards README times one
Pico 2 port alone and every ssh line says `IdentitiesOnly=yes`.
`agent_env.sh` read `~/.bashrc` when its standard input was a socket; it
now reads no startup file and writes no secret-looking name. The eight
rows are deleted.

### R20 gate
R20's breaking window: the list reached main in one promotion, so main
never carries half of it; every removed name refused with its replacement;
prototypes 3 and 4 reread against the result.

Claimed after R20.61, on `r20-integration` at `ada37f058`, the window's
one promotion to main, with R16.28's and R16.29's work that landed on the
branch: every item's work passed a complete gate on that branch, R20.11's
and R20.20's on the later head that contained them, their own runs having
been cancelled by a sibling's landing. The window's first boards dispatch
failed its wall-time jobs: `scripts/measure.py` built the base's images,
main's, from the candidate's fixtures, which name what main's library
lacks; R16.30's fix, each side building from its own checkout, was taken
onto the branch as `ada37f058`. That integrated tree, of which main
`b6a53edb7` is an ancestor, passed the full
[pass](https://github.com/701-dev/Landin/actions/runs/45142838943) and a
[boards dispatch](https://github.com/701-dev/Landin/actions/runs/45142854548). Every name the breaking list removes is
refused as L0696 naming its successor, from the one table
`Landin.Modules.Removed`, which R20.60's and R20.61's negative fixtures
pin, and `refine fix` rewrites the mechanical ones. Prototypes 3 and 4
were reread against the list: prototype 3's `core/map` sketch, which
declared its own `missing`, and prototype 4's `core/io` sketch, which
declared its own `not_found`, now fail `mem.not_found`, and the map's entry
walk ends at `at_end`; none of their live text names a removed form.

## R21 — Windows

R15's proposal rewritten for today's library, second Io and threads.
R21.60 and R21.61, which the maintainer placed here on 2026-11-24, bring
`refine` itself to FreeBSD, whose programs it already builds. R21.70,
which the maintainer moved here on 2026-11-25, closes the gaps R21's items
recorded on Windows.

### R21.10 — Windows x86-64

Status: complete
Depends on: R20

Win64 convention, COFF, unwind tables, a hosted layer over the Windows
API; assembler and linker chosen here. Decides `utf16`, which R19 leaves
to it.
Exit evidence: the corpus runs on a Windows x86-64 runner in the gate;
the `utf16` decision in `spec.md`.

Done: `windows-x86-64` builds COFF executables through llvm-mingw's
`x86_64-w64-mingw32-clang`, Clang's assembler and LLD against MinGW-w64's
free import libraries, linking kernel32 and no C runtime from
`platform/windows`'s `_landin_start` (D2188, D2189, which also says what
Microsoft's tools would take). C calls take the Windows x64 convention,
LLP64 with `compiler.c_win64_llp64` (D2190); routines carry SEH tables for
their frame records (D2191); a failed check ends with
`STATUS_ILLEGAL_INSTRUCTION`, its report's stack made the thread's first
(D2192); thread variables are module storage until Windows' threads
(D2193); a Windows image holds its static images within 2 GiB, which L0505
says before emission. `utf16` stays, and a Windows host string is not one
(D2187). The gate's `windows-emit` and `windows-runtime` jobs run 3,314
outcomes of 732 runtime fixtures natively on `windows-2025`, passed in
the merged candidate's gate run 45229944797, with boards run 45234631776; `compiler/tests/windows/check.py` runs them under
Wine locally. Found and fixed on the way: Windows refused images past 2 GiB
that Wine loaded; the trap after a prepared stack's report dispatched as
an access violation; a musl-built `refine` named no host target (`SR-1518`
taken). Rows `SR-1694` to `SR-1698` record the C peer lane, the start-up level
check, the TEB bounds a stack switch leaves, the fixture path Git for
Windows cannot check out and the measurement no lane takes of a Windows
image; `hosted/heap`, arguments, environment and thread
storage moved to R21.20.

### R21.20 — Windows' Io and threads

Status: complete
Depends on: R21.10

Both Io providers and `hosted/thread` over the Windows API, with
`hosted/heap`, the process's arguments and environment, and Windows'
thread storage, which R21.10 left to it.
Exit evidence: the Io and thread suites pass on Windows x86-64 in the
gate.

Done: the hosted providers run on Windows over `platform/windows`, which is
now a module of files beside `platform/windows/sockets`. Every hosted
system's own interface is imported on all of them and declares nothing
off its own (D2267), so `hosted/system`, `hosted/blocking`,
`hosted/events`, `hosted/thread` and `hosted/heap` keep their POSIX bodies
under `fixed if compiler.os <> windows` and give Windows arms in files of
their own. A Windows host string is WTF-8 (D2268); the entry splits the
command line as Microsoft's C runtime does and keeps the root itself
(D2269); a file is a handle and a failure its Win32 code (D2270); a child
gets exactly its three streams through named pipes (D2271); the blocking
network waits a socket's limit out with `select` (D2272); `hosted/events`
waits on an I/O completion port (D2277), learns a child's end from a job
(D2278), takes the console's control events as its signals (D2279) and
runs Windows Sockets overlapped (D2280); thread storage is the image's
implicit TLS (D2274, D2193 superseded), a thread starts on a system stack
and switches to its own (D2275), and the heap grows into its reservation
(D2276). Windows Sockets is a module of its own, since its C names are a
program's to declare too (D2281). The Windows lane carries fixtures' files
and runs each outcome apart (D2273), and reports a failed build beside the
other verdicts, a threads stream's finding. The gate's `windows-runtime`
job ran 3,682 outcomes of 818 runtime fixtures natively on `windows-2025`,
the hosted Io and thread corpus among them, all passed, in the merged
candidate's gate run 45303680058, with boards run 45307040095; under Wine
two console fixtures end early now and then when several run at once,
which the native runner has not met. Found and fixed on the way: a
program's own `send` or argument initializer collided on Windows with the
library's, which every Windows program links; `handle_of` stripped only
the socket mark; two names the streams both declared; the library page's
drift check, which now lets a routine of each system's
types describe its own. The heap's and lock's per-system helpers grow
every hosted image at size by about 200 bytes, which the baselines declare
and `SR-1739` records; `SR-1736` to `SR-1738` and `SR-1740` record the
Windows link's `-o` without `.exe`, a program's own path, the library
page's reader and a lane's hung outcome; `SR-1695` and `SR-1696` were
restated.

### R21.30 — Windows debugging

Status: complete
Depends on: R21.10

CodeView in the objects, PDBs from the linker, and the Windows debugger
added as a backend of R18.60's adapter, which is shown only against GDB
and LLDB; it takes nothing from R18.60 but the protocol layer.
Exit evidence: scripted debugger sessions, directly and through `refine
dap`, on Windows x86-64 in the gate.

Done: with `--debug=full` a Windows image's objects carry CodeView,
presented as C as the DWARF description is (D2287), whose lines name each
address once (D2288), and LLD links a PDB beside the image, which names it
by its file name alone (D2289); a `.landin` section holds the build's
digest, so `refine site` and the panic map read a PE image (D2291). The
Windows debugger is LLVM's LLDB as llvm-mingw's Windows release ships it,
free, `lldb.exe` and `lldb-dap.exe`, reading the PDB with LLVM's own
reader (D2292): it joins R18.60's adapter through the relay R18.60 wrote
for `lldb-dap`, a PE image taking LLDB and Windows' and WSL's paths
translated, since `refine` runs on Windows in WSL. The gate's
`windows-debugger` job runs LLDB's batch session at the four profiles
natively on `windows-2025` and the DAP session through `refine dap` from
WSL on the same runner, passed in the merged candidate's gate run
45324523635 with boards run 45328192419; `compiler/tests/windows/debug.py` runs
both under Wine locally. Found and fixed on the way: LLVM's `lldb-dap`
answers `launch` after `configurationDone` and verifies a breakpoint once
the program is loaded, from release 21, which `compiler/tests/dap/session.py`
now allows; a breakpoint on a line whose first value had no code stopped
past its locals (D2288); ranges out of address order joined into one;
and a Windows program WSL starts from a process group other than the
terminal's stalls, which a debugger `refine dap` started in a group of its
own did in about half of the gate's runs, so a Windows adapter now shares
refine dap's group (D2292). Rows SR-1746 to `SR-1748` record the inline
sites CodeView lacks (D2290), the stack-switch session Windows lacks and
two `--debug=full` builds that differ by their temporary object's name.

### R21.40 — Windows arm64

Status: complete
Depends on: R21.30

Exit evidence: the corpus, the Io and thread suites and the debugger
sessions on Windows arm64 in the gate.

Done: `windows-arm64` builds COFF executables through llvm-mingw's
`aarch64-w64-mingw32-clang` from the arm64 backend, whose text around the
instructions is Windows' (D2347-D2350). C calls take Microsoft's variant of
AAPCS64, LLP64 with `compiler.c_windows_arm64_llp64`, signed plain `char`,
and a variadic call's every argument passed as integers (D2347); routines
carry unwind tables for their frame records and CodeView names ARM64's
registers (D2349); thread storage and a report's stack bounds are reached
through x18's TEB, and a failed check's `brk #1` ends the process with
`STATUS_ILLEGAL_INSTRUCTION` as `ud2` does (D2350). The section spellings
both Windows backends write are `Landin.Backend.COFF`'s. MinGW-w64's arm64
import libraries come from the pinned llvm-mingw arm64 release, on Linux
in the development shell and the gate alike (D2348). GitHub's
`windows-11-arm` runner, which the repository's plan offers, runs the
gate's new `windows-arm64-runtime` and `windows-arm64-debugger` jobs; WSL
1 there runs `refine dap` in Ubuntu's arm64 base system, imported from its
pinned archive, since the WSL setup action's distribution is x86-64's.
Every fixture naming `windows-x86-64` names `windows-arm64` too but the
one that selects x86-64's declarations: 3,674 outcomes of 817 runtime
fixtures, the hosted Io and thread corpus among them, and LLDB's batch
sessions at the four profiles and the DAP session from WSL all passed in
the merged candidate's gate run 45381123990, with boards run 45386486954.
Found and fixed on the way: `lldb-dap.exe` run from WSL deadlocked on its
standard streams in about half of all sessions on both architectures,
which probe matrices traced to the streams themselves, with or without
`refine dap` in between; `refine dap` now speaks to a Windows adapter over a
loopback connection (D2351), which takes `SR-1768`. The arm64 backend put
its debug sections before the last line, taking it for a trailer COFF has
none of; `docs/library.md`'s ABI table and `compiler/tests/README.md`'s
target list named neither Windows target. Nothing local runs an arm64
Windows program, which the lane's README says. Nineteen rows the merge and
the completion aged past ten items were kept and `SR-1696` restated for
arm64's stack switch.

### R21.50 — Microsoft's toolchain on Windows

Status: complete
Depends on: R21.10

A second, optional Windows x86-64 toolchain beside llvm-mingw, the one
D2189 describes: the assembly assembled by Clang for
`x86_64-pc-windows-msvc` or by `clang-cl`, or a MASM spelling of the
backend's output if that proves the simpler route; the link by `link.exe`
or `lld-link` with `/ENTRY:_landin_start /NODEFAULTLIB`; and the Windows
SDK's `kernel32.lib` and each `linker.library` as a `.lib` found by
`/LIBPATH:`. A user selects it with `--toolchain`, and llvm-mingw stays
the default and the only toolchain a Windows build requires.
Exit evidence: the corpus links with Microsoft's tools and runs on a
Windows x86-64 runner in the gate, which carries Visual Studio; the
selection in `docs/capabilities.md`.

Done: a `--toolchain` driver whose file name holds `-windows-msvc`, as
Clang's own `x86_64-pc-windows-msvc-clang` does, selects Microsoft's link
(D2327). Clang assembles the same assembly for the MSVC target and hands
the link to Visual Studio's `link.exe`, or to `lld-link` under
`--linker=lld`, with `/ENTRY:_landin_start /SUBSYSTEM:CONSOLE
/STACK:8388608 /NODEFAULTLIB /OPT:REF /INCREMENTAL:NO /Brepro`, each
`linker.library` as `NAME.lib` from the Windows SDK, and under
`--debug=full` a PDB beside the image. llvm-mingw stays the default and the
only toolchain a Windows build requires; the item covers x86-64. refine
cannot run where `link.exe` does, so the Windows lane's `--link=microsoft`
records on Linux each link command refine chooses, and the gate's new
`windows-microsoft` job runs those commands with the runner's Clang,
requires that `link.exe` ran each one, and holds every program to its
fixture: all 3,682 outcomes of the corpus passed, linked by `link.exe` of
Visual Studio 18 through Clang 20.1.8, in the merged candidate's gate run
45350557955 with boards run 45356037718. Locally `lld-link` and MinGW-w64's import libraries
stand in under Wine, where all 3,682 outcomes passed, and `nix develop` now
puts `lld-link` beside `clang-19`. Found and fixed on the way: `link.exe`
folds the thread-storage template into `.rdata` and drops an empty `.tls`
contribution, so every thread-storage offset counted from `.rdata`'s start,
and 54 outcomes, every program with a stack-limit cell, trapped or
faulted; the template's start marker now holds a byte, as the C runtime's
`_tls_start` does, under both linkers. Under Microsoft's link refine asks
the driver about no library: the SDK's directories are invisible to it, so
the linker's own text stands where L0509 would wrongly name every library.
nixpkgs' `clang` wrapper refuses the MSVC target, which the lane's README
now says. `SR-1767` records the job's unpinned Clang and Visual Studio;
`SR-1736` and `SR-1748` were restated: Microsoft's link keeps an output
name without `.exe`, but its debug builds differ just as LLD's MinGW-mode
ones do. `SR-1768` records the `windows-debugger`
DAP session that fell silent after its launch, once, in that gate run.

### R21.51 — Microsoft's toolchain on Windows arm64

Status: complete
Depends on: R21.40, R21.50

R21.50's toolchain for `windows-arm64` as well, on a Windows host: the
assembly assembled by Clang for `aarch64-pc-windows-msvc`, or an
armasm64 spelling if that proves the simpler route, and linked by
`link.exe` or `lld-link` against the Windows SDK's arm64 `.lib` files.
The toolchain is selected per target, as `--toolchain` already is, so
one selection serves both Windows architectures, and llvm-mingw stays
the default on both. Microsoft's tools are not used from a Linux host;
a Windows image built on Linux takes llvm-mingw.
Exit evidence: the corpus links with Microsoft's tools and runs on a
Windows arm64 runner in the gate; the selection for both architectures
in `docs/capabilities.md`.

Done: a `--toolchain` driver named for `-windows-msvc` selects
Microsoft's link on either Windows target, and refine passes the target's
own Clang triple, `aarch64-pc-windows-msvc` for windows-arm64, and names it
in its install advice (D2387). refine now passes `-fuse-ld=link` unless
`--linker` names another (D2388): the `windows-11-arm` image's Clang
22.1.8 runs `lld-link` by default for the MSVC target, which a probe run
showed. The gate's `windows-arm64-emit` job records the arm64 link
commands and the new `windows-arm64-microsoft` job runs them on
`windows-11-arm`: all 3,674 outcomes of the corpus passed, linked by Visual
Studio 18's arm64 `link.exe` through Clang 22.1.8, in gate run
45404993968, and the merged candidate passed gate run 45447103186 with
boards run 45453055695. Locally every arm64 outcome links
under `lld-link` with llvm-mingw's import libraries; nothing local runs
them. Found and fixed on the way: `check.py --prepare-only` now carries its
own lane under `lane/`, as `debug.py` does, so the emit jobs copy nothing
by hand, and the lane's README says how to run the bundles on a Windows
host, which only `gate.yml` showed. Filed `SR-1797`, the lane's error mode
not keeping Windows Error Reporting away off GitHub's images, and
`SR-1798`, `item.py gate --main` listing the branch's runs beside main's;
`SR-1767` restated for the arm64 job's unpinned Clang.

### R21.60 — refine on FreeBSD x86-64

Status: complete
Depends on: none

The maintainer decided on 2026-11-24 that `refine` runs natively on
FreeBSD beside Linux, and placed that work here. FreeBSD's programs are
emitted on Linux today and run in the gate's FreeBSD guests, which
compile no Landin. GNAT-FSF-builds publishes no pinned GNAT for FreeBSD,
and its packages carry GNAT 12 to 15 and a GPRbuild that moves with the
ports, so this item builds the pinned GNAT and GPRbuild on FreeBSD x86-64
from source, as `compiler/ada/TOOLCHAIN.md`
allows a host to, cached by their inputs, and records how. `refine` and
its commands are built with them; `Landin.Platform`'s native body takes
FreeBSD in its POSIX arm wherever it differs from Linux and Darwin, as
it already does for the executable's own path; and `freebsd-x86-64` is a
FreeBSD x86-64 host's default target, where the host defaults name only
Linux and Darwin today.
Exit evidence: the gate's `freebsd` job, whose amd64 guest runs under KVM
on a GitHub-hosted Linux runner, builds `refine` in that guest, where the
test program, the native adapter's cases and the hosted corpus compiled
by that `refine` pass; the host in `docs/capabilities.md` and a release
archive for it.

Done: `refine` builds and runs on FreeBSD x86-64. GNAT 16.1.0 and GPRbuild
26.0.0 are built from source in a FreeBSD 14.4 guest by
`environments/freebsd/gnat.py` (D2428): GCC with FreeBSD ports'
`lang/gcc16` patches and binutils, compiled once by `gnat14`, and GPRbuild
with its own commit `6421e350274b`, which GNAT 16 needs; every source is
pinned in `environments/pins.sh`, and the 111 MB archive is cached under a
digest of its inputs, ten minutes to build on 16 processors and twenty on
the gate's four. A compiler built there defaults to `freebsd-x86-64` and
links with the base system's `cc` and binutils' `as` (D2427). The gate's new
`freebsd-toolchain` job restores or builds the archive, `freebsd-toolchain-main`
keeps it in main's cache, and `compiler/tests/freebsd/host.py` builds
`refine` in an amd64 guest under KVM and runs the complete local native
suite there as `freebsd-host-1` and `freebsd-host-2`, where fixture
execution compiles, links and runs the hosted corpus with that `refine`,
and `freebsd-host-release` packages `landin-VERSION-x86_64-freebsd.tar.gz`,
whose `refine` loads only `libthr` and `libc` and ran with the GNAT moved
away; the release workflow publishes it. All 1,294 cases passed in a local
guest, and the merged candidate passed gate run 45513329197 with boards
run 45517462370. The test program's native lane
learned FreeBSD (D2429): its C driver is the one `refine` would take, a level
is confirmed by the emitted lane's CPUID probe, the two fixtures that name
Linux's fault endpoints run with that lane's endpoints preloaded, the level
note and `-no-pie` stay Linux's, and its links take refine's FreeBSD
options. `Landin.Platform`'s native body counts FreeBSD's allocator through
jemalloc, flushing the thread's cache, and knows UFS and tmpfs compare
names as bytes. Found and fixed on the way: the item's text said the ports
carry GNAT 14, where FreeBSD's packages carry 12 to 15; the arm64 guest
asked QEMU for an iPXE ROM its firmware does not need, so `ipxe-qemu` is no
longer installed. Filed `SR-1817`, the FreeBSD arm64 lane's use of an arm64
host's KVM; `SR-1818`, the release build's memory at default parallelism;
`SR-1819`, the Windows lane's README on local arm64 hosts; and `SR-1820`,
`install.sh` not serving FreeBSD yet.

### R21.61 — refine on FreeBSD arm64

Status: complete
Depends on: R21.60

R21.60 on FreeBSD arm64. The gate's arm64 guest is emulated, where
building a compiler may outlast a job, and the gate runs on no host of
its own but the lab rig, so the evidence is a run on the maintainer's
arm64 host.
Exit evidence: a named run recorded in the item, in the FreeBSD arm64
guest under KVM on the maintainer's arm64 host, of R21.60's evidence:
`refine` built there with the pinned GNAT, and the test program, the
native adapter's cases and the hosted corpus it compiles passing; the
host in `docs/capabilities.md` and a release archive for it.

Done: `refine` builds and runs on FreeBSD arm64, where it defaults to
`freebsd-arm64` (D2469) and links with the base system's `cc`, whose
Clang also assembles. The named run (D2470) was in the FreeBSD 14.4 arm64
guest under KVM on the maintainer's arm64 host, 20 processors in 8 GiB:
`environments/freebsd/gnat.py --runner-ssh`, new, built the pinned GNAT
16.1.0 and GPRbuild 26.0.0 there in ten minutes (archive key
`b07aa20481369ea7`, 104 MB); `compiler/tests/freebsd/host.py` built
`refine` at a535c1593 and ran the complete local native suite, 1,295 of
1,295 cases in 17 minutes, fixture execution compiling, linking and
running the hosted corpus with that `refine`; and its release leg at
1bdd0677 packaged `landin-0.2.11-aarch64-freebsd.tar.gz` (sha256
`81c05fff…f53177999`), whose `refine` loads only `libthr` and `libc` and
ran with the GNAT moved away. No release publishes that archive until
Q-279 is answered. Findings fixed: the test program's native FreeBSD
arm64 C link lacked `-Wa,-L`, so the two `r440-native` ABI fixtures'
foreign `.L` names were undefined, and its level refusal expected GNU
as's words rather than Clang's; `host.py` left FreeBSD arm64's 1 GiB data
ceiling, which refuses `large-array-offset-is-addressed`, as `check.py`'s
lanes do not; a release build killed `gnat1` in 8 GiB at one job per
processor, so `scripts/build.sh` now runs one job per 2 GiB of memory
when no `-jN` is named (`SR-1818`, settled); and the gate's Cortex-M and
Xtensa installs failed because Debian's pool dropped two locked packages,
which `environments/cortex-m/setup.py` now takes from
`snapshot.debian.org` at the lock's time.

### R21.70 — What Windows still lacks

Status: complete
Depends on: R21.61

The gaps R21's items recorded on Windows, scheduled by the register sweep
of 2026-11-25: `SR-1697`'s debugger case whose file name Git for Windows
refuses, so that a Windows runner checks the repository out; `SR-1694`'s
C peers, which run against no Windows image; `SR-1695`'s entry, which
checks no processor level; `SR-1696`'s stack switch, which leaves the
TEB's bounds naming the first stack, and `SR-1747`'s switch and start
routines without the unwind tables a Windows debugger walks; `SR-1698`'s
images, which no lane measures; `SR-1736`'s executable named without
`.exe` and the private directory a failed link leaves; `SR-1748`'s two
`--debug=full` builds that differ; and `SR-1797`'s lane, which keeps
Windows Error Reporting away only where the image has disabled it.
The maintainer moved it into R21 behind R21.61 in answering Q-285, so
that R21's gate waits for the Windows gaps.

Exit evidence: each row's completion on both Windows architectures where
it names one, in the gate's Windows jobs, and switch_frames.py's session
in the Windows debugger lane.

Done: every row the item names is closed on both Windows architectures,
in gate run 45606318679, whose 100 jobs passed. The repository checks out
on Windows: the debugger case's oddly named source is written at run time
and `check.py` refuses a tracked path Windows cannot hold, and
`windows-runtime` and `windows-arm64-runtime` run their lane from a
checkout. Those jobs also run `compiler/tests/windows/check.py
--kind=abi`, which links each ABI fixture's C peer with llvm-mingw's
Clang and C runtime on the runner (D2473): 22 fixtures now name both
Windows targets and two new ones hold variadic floats and, on x86-64,
every register Win64 makes a callee save across a callback C enters. The
first run found two Win64 defects, fixed: an imported function's address
was read through a GOT COFF does not have, which loaded the function's
first instructions (D2471), and a `distinct f32` crossed in RCX (D2472).
A Windows image holds the processor to its level before `main`, sharing
x86-64's reading with Linux in the new `platform/x86_64`, Windows arm64
by `IsProcessorFeaturePresent`, which reports no RDM (D2475-D2477). A
stack switch carries the TEB's bounds, a fixture traps in kernel32 on a
prepared stack, and the switch and start routines carry unwind tables and
PDB procedures, so `switch_frames.py`'s session runs in both Windows
debugger jobs at four profiles (D2479-D2481). The `measure-size` job
measures both Windows targets, `size-only` in the runner table, through a
PE reader. An image named without `.exe` keeps its name and a failed link
leaves no private directory (D2485); two links of one program, with or
without `--debug=full`, are the same bytes (D2486), which the gate showed
held only inside the flake's `SOURCE_DATE_EPOCH` until the MinGW link took
`/Brepro` (D2487). The lane keeps Windows Error Reporting away with a job
object (D2474): with WER on, the whole x86-64 corpus passed 3,706 of 3,706
on a Windows 11 host, where the error mode alone had left 14 traps past
their limit. The usability findings met building the project's Windows
hosts are closed by the Windows lane's README, which now names the route
a Windows arm64 guest gives and the checkout; the rows the item filed are
`SR-1851`, `SR-1852` and `SR-1859`.

### R21 gate
The corpus and debugger sessions on both architectures on GitHub's Windows
runners, and the corpus linked by Microsoft's toolchain on both; `refine`
built and tested on FreeBSD x86-64 in the gate and on FreeBSD arm64 in
R21.61's recorded run; and the Windows gaps R21.70 names closed by its
exit evidence.

Claimed after R21.70, on main `fac832822`. R21 declared no window, so
each item reached main by its own promotion after its candidate's complete
pass and boards dispatch, and main's gate passed after each. That tree
passed the full
[pass](https://github.com/701-dev/Landin/actions/runs/45640994727), 92
jobs passed and 8 skipped by their conditions, and a
[boards dispatch](https://github.com/701-dev/Landin/actions/runs/45648808530),
which main's [gate](https://github.com/701-dev/Landin/actions/runs/45653929208)
reused. In that pass the Windows runners ran the corpus and the debugger
sessions on x86-64 and arm64 (`windows-runtime`, `windows-debugger`,
`windows-arm64-runtime`, `windows-arm64-debugger`), and the corpus linked
by Microsoft's toolchain on both (`windows-microsoft`,
`windows-arm64-microsoft`). `refine` was built and tested on FreeBSD
x86-64 (`freebsd-toolchain`, `freebsd-host-1`, `freebsd-host-2`,
`freebsd-host-release`); FreeBSD arm64 rests on R21.61's recorded run
(D2470). R21.70's rows are closed in the same jobs: both runtime jobs ran
from a checkout and linked the ABI fixtures' C peers, both debugger jobs
ran `switch_frames.py`'s session at its four profiles, and `measure-size`
measured both Windows targets. Q-279 is answered; until a release
publishes the FreeBSD arm64 archive, `SR-1892` holds that work.

## R22 — Library additions

What a newcomer expects to find, written against the library R20 left: a
mathematical basis broad enough that people in most fields need no
foreign library first, float text, Unicode, encodings, locale formatting
and regular expressions, the five programs the Benchmarks Game comparison
lacks, and at the end a measured basis for the library's optimization
with a continuous lane, as R16 has for code generation.

Placement, data and evidence for each are in `library-inventory.md`'s
appendix B §5. A table derived from outside data (the Unicode Character
Database, the WHATWG and IANA encodings, CLDR) comes from a generator
program with a pinned input, its output checked in and held current by a
check, the route `refine svd` and `scripts/linux_syscalls.py` take. No
build tool is assumed and nothing runs at compile time. Each module has a
consumer outside its fixtures: a port, another module, or an example
program in `examples.md`.

The mathematics is divided by subject and by what depends on what.
R22.10 to R22.19 are the numbers and linear algebra: elementary
functions, complex numbers, special functions, exact big numbers, fixed
point, dense matrices, linear systems, eigenvalues, small geometry and
sparse matrices. R22.70 to R22.76 are the numerical methods built on
them. Coverage is broad, not complete: each item says what it covers and
what it leaves out, and a part left out waits for a consumer. C's
`<math.h>`, GMP, BLAS, LAPACK, Eigen, OpenFOAM and mlpack are checks of
breadth, not interfaces to copy; nothing is bound from them and no
C-callable BLAS or LAPACK names are offered.

Every mathematical module is freestanding in `core/*`: storage is the
caller's, scratch comes from a passed allocator or a caller buffer whose
size the routine states, and nothing keeps global state. Each
floating-point routine comes in `f32` and `f64` on every target, through soft float where there
is no unit; whether it is written once over a concept both meet is R20's
answer on `type is C`. Accuracy is stated per routine and pinned against
an oracle computed outside the program, and each module's image size on
Cortex-M0's soft float is measured. Everything is single-threaded.

### R22.10 — Elementary functions

Status: complete
Depends on: R20

`core/math`, `SR-96`: the functions of C's `<math.h>` that most programs
use, over `f32` and `f64`, written in Landin so that results agree across
targets. Classification and manipulation of the representation, rounding
and remainders; `sqrt` and `fma` as instructions where the target has
them, since IEEE makes both exact, through a builtin, which D630 has so
far refused, or an assembly block per target, decided here; `cbrt` and
`hypot`; exponentials and logarithms with
their `expm1` and `log1p` forms; powers; the trigonometric and hyperbolic
functions and their inverses; `erf`, `erfc`, `tgamma` and `lgamma`; the
constants. Ported from musl's and FreeBSD's msun or CORE-MATH, each
function's error in units in the last place stated. From R20: the naming
of its module and routines, and whether floats get ordering evidence.

Leaves out: correct rounding where it is not cheap, rounding modes other
than to nearest and the floating-point environment's flags, C23's
pi-scaled, narrowing and decimal functions, and any other format.

Exit evidence: every function within its stated error of MPFR's
correctly rounded values, one-argument `f32` functions exhaustively and
the rest on a random and a hard-case set, on every target; image size on
Cortex-M0's soft float measured.

Done: `core/math` holds the functions R22.10 names, each generic over
`math.floating`, which `f32` and `f64` meet, under C's names where they are
the mathematics' own and words elsewhere (D2552). It is ported from msun's
files under Sun's notice, and `exp2`, the software `fma` and `gamma` are
written here, since msun's are under other licences (D2554, Q-306); the
square root and `fma` are the float unit's instructions in assembly where
there is one, and computed from the bits on Cortex-M0, RV32 and Xtensa
(D2551). Every routine's error is stated in its doc comment (D2553): zero
for the exact ones, the square root and `fma`; below an ulp for most; up
to 4.2 for the hyperbolic functions, `erfc`, `log_gamma` above -2, `atan2`
and `hypot` at f32, as msun's own are, which `SR-1898` holds; and
`log_gamma` loses its relative accuracy near its zeros below -2,
`SR-1897`. `scripts/math_oracle.py` builds compiler/tests/math/oracle.c
against MPFR and writes the 36 `math-*` fixtures, whose tables of
specials, random and hardest-to-round inputs pass on every target the
gate runs, the firmware lanes included, thirteen of them past Cortex-M0's
flash at `none/off` alone and executed at its other profiles. A million
random inputs per routine and width, and every input of each
one-argument f32 routine, `log_gamma`'s above -2, were measured against
MPFR on Linux x86-64, and those routines' 2^32 f32 results compared bit
for bit, every NaN as one, on Linux arm64 and RV64 under QEMU (Q-307). Each
fixture's Cortex-M0 image is measured in compiler/tests/math/README.md,
and `examples.md` computes great-circle distances with it. The
trigonometric stream found x86-64's `size` allocator giving a value its
slot's register while an earlier value still held it (D2157), fixed with
`runtime/slot-register-keeps-an-earlier-store`; the Cortex-M0 lane found
the software square root's exponent and f32 pairing wrong; `log_gamma` at
f32 overflowed to the largest float; and the oracle now rounds a special
to its width, checks in resumable parts and takes a domain. Filed:
`SR-1895`, a NaN's bits differing between targets unsaid; `SR-1896`, a
hexadecimal float without its point refused without saying so. Q-306,
Q-307 and Q-308, floats' ordering evidence, are open with their
defaults.

### R22.11 — Complex numbers

Status: complete
Depends on: R22.10

A complex number over `f32` and `f64`: arithmetic with C's Annex G
treatment of infinities, absolute value, argument and polar form, and the
complex elementary functions: `exp`, `log`, powers, `sqrt`, and the
trigonometric and hyperbolic functions and their inverses. R22.17's
eigenvalues, R22.70's polynomial roots and R22.73's transforms use it.

Leaves out: complex special functions; matrices of complex elements, a
later addition by Q-67's answer.

Exit evidence: each function within its stated error of MPC's values,
with branch cuts and signed zeros as Annex G gives them, on every target.

Done: `core/complex` holds `number(item)`, a struct of `real` and
`imaginary` over `math.floating`, and every routine R22.11 names, each
written once over the concept with the parts' own arithmetic, under C's
names where they are the mathematics' own and words elsewhere: `add`,
`subtract`, `multiply`, `divide`, `negate`, `conjugate`, `project`,
`polar` and `from_polar` (D2634). Annex G's special values and its signed
zeros on each side of a cut hold throughout; a sign the annex leaves open
is whatever the arithmetic gives (D2635). Nothing is ported, msun's
complex files being BSD-2-Clause under Q-306's default: the square root,
`tanh` and `atanh` are Kahan's, the arcsine and arccosine Hull, Fairgrieve
and Tang's, and `multiply` and `divide` sum their products with an fma's
recovered error, each product over its own exponents, so that no
magnitudes overflow or lose a part (D2637). Each routine states its error
per part, from 1.0 ulp for `multiply` to 6.1 for `tanh`, and `pow`'s, 19
ulp of the larger part on bounded domains, grows with |w·log z|
(`SR-1949`). `scripts/math_oracle.py` gained MPC beside MPFR: complex
shapes of up to four input floats, MPC evaluated in MPFR's whole exponent
range, where its intermediates no longer underflow, a part beside NaN
compared by magnitude, and a normwise bound for `pow` (D2636). The 30
`complex-*` fixtures and `library-shared-complex` pass on every target the
gate runs, the firmware lanes included. A single elementary function at
`f64`, or a trigonometric one at either width, is past Cortex-M0's 32 KiB
with the `core/math` it calls and the soft float, whose `f32` sine
reduces in `f64` (`SR-1950`); so the families whose `f32` half fits have
a fixture per width, thirteen fixtures run on Cortex-M0, eight at every
profile, and the rest are recorded as image limits and run on the
Cortex-M7 lane. That lane found `tanh` taking the sign of an imaginary
zero from the sine of an overflowed `2y`, a NaN whose sign is each
target's own (`SR-1895`), fixed with `sin y · cos y`. A million random
inputs per routine and width were measured against MPC on Linux x86-64.
Filed: `SR-1948`, generic float code naming no width's facts, and
`SR-1951`, `item.py boards --watch` dispatching again over a queued run.

### R22.12 — Special functions

Status: planned
Depends on: R22.10

The functions statistics, physics and engineering reach for after the
elementary ones: the incomplete gamma and beta functions and their
inverses, the logarithm of the beta function, the digamma function, the
inverse error function, the exponential integral, and the Bessel
functions of the first and second kind and their modified forms for real
order and argument. R22.74's distributions stand on them. SR-1897's
`math.log_gamma` below -2, on which the incomplete gamma and beta
stand, and SR-1948's facts of a width, which generic code over
`math.floating` cannot name, are scheduled here by the register sweep of
2026-11-26.

Leaves out: elliptic integrals and functions, hypergeometric and Airy
functions, the zeta function, spherical harmonics, and complex arguments.

Exit evidence: each function within its stated error of MPFR's or
another higher-precision reference's values over its stated domain, on
every target.

### R22.13 — Big integers and rationals

Status: complete
Depends on: R20

Arbitrary-precision arithmetic in two layers. The lower works on
caller-supplied limbs with no allocator, as GMP's `mpn` does, so that
firmware and R22.20's parser can use it: addition, subtraction,
multiplication from schoolbook through Karatsuba to Toom-3, division with
remainder, shifts, comparison, and decimal and hexadecimal text. The
upper is a signed integer and a rational that grow through the caller's
allocator: arithmetic, floor and truncating division, powers, integer
roots, the greatest common divisor, modular inverse and exponentiation,
bit operations, and conversion to and from the machine integers and
floats with stated rounding. By Q-69's answer, arbitrary-precision
floating point is a later addition, and the two layers are designed so
that it can stand on them.

Leaves out: arbitrary-precision floating point, FFT multiplication and
the Toom variants above three, primality proofs and factoring, and
constant-time operations, since Landin writes no cryptography.

Exit evidence: an oracle set computed by another implementation passes
on every target; multiplication and division timed from one limb to a
million bits; the lower layer's image size on Cortex-M0 measured.

Done: `core/big/limbs` holds naturals in the caller's 32-bit limbs on
every target, with no allocator, and `core/big` the `integer` and the
`rational` over them, each routine writing a destination the caller's
allocator grows (D2594). A destination may be an operand, a copy is made
with `set` (D2595), and every loop keeps its temporaries, so an arena
holds a call whatever its length (D2596). A zero divisor stops the
program and only foreseeable conditions fail (D2597); conversions to a
float round once, ties to even (D2598); bit operations read two's
complement without end (D2599); rationals stay in lowest terms under
`rational_` names (D2600); multiplication is schoolbook, Karatsuba and
Toom-3, division Knuth's Algorithm D (D2601). `scripts/big_oracle.py`
writes the 16 `big-*` fixtures from Python's integers and fractions,
with operands to 320 limbs drawn from `core/random` and compared by
digest; they pass on every target the gate runs. On Cortex-M0's 32 KiB
reference, sums, products, quotients, powers, the greatest common
divisor, bits, conversions and text execute at every optimized profile;
roots, the modular inverse and power and the rationals need both
multiplication and division and outgrow it, so their corpus rows record
profile limits and the `mps2-an500` lane executes them, `SR-1929`. The
limb layer is 20,310 bytes at `size/auto` there, and a million-bit
product takes 58 ms on x86-64 against 2.1 s for a division, whose
subquadratic form waits in `SR-1928` (compiler/tests/big/README.md).
`examples.md` computes 50 factorial and a harmonic number exactly. The
`mps2-an500` lane found Cortex-M frames freeing a deferred widening's
operand home at the widening rather than at its reader, so that at
`armv7-m` and `armv8-m.main` `u64(a[i]) + u64(b[i])` after a call added
`b[i]` twice (D2120), fixed with
`runtime/widened-operands-keep-their-homes`. Fixed on the way:
`refine fmt core/big core/big/limbs` refused the nested directory as
holding no source (D385), and `scripts/add_fixture.py` printed that
command.

### R22.14 — Fixed-point arithmetic

Status: planned
Depends on: R22.10

For targets without a float unit, the Q15 and Q31 formats firmware signal
processing uses: saturating and rounding arithmetic, conversion to and
from floats, square root, reciprocal, the trigonometric functions, `exp`
and `log`, and dot products and FIR filters, which R22.73's fixed-point
transforms use. It stays by Q-70's answer.

Leaves out: other Qm.n formats and fixed-point matrix factorizations.

Exit evidence: each operation within its stated error of an exact or
MPFR reference on every target; its cycles against the same routine in
soft float recorded on Cortex-M0 on the rig.

### R22.15 — Dense vectors and matrices

Status: complete
Depends on: R22.10

The dense array as linear algebra sees it: a vector or matrix as a view
over caller storage, with rows, columns and strides in either order, and
transposed and sub-matrix views without copying; element-wise operations,
reductions and norms; and the products everything after it stands on, in
the breadth of the BLAS's three levels: scaled sums and dot products,
matrix-vector products and rank-one updates, matrix products, triangular
products and solves, and symmetric rank-k updates. The matrix product is
blocked and packed for the cache from the start, the established
strategy. Small fixed-size vectors are R22.18's. By Q-67's answer the
elements are real, and the matrix's design leaves room for complex
elements as a later addition.

Leaves out: banded and packed storage, complex elements,
extended-precision accumulation, arrays of more than two dimensions, and
lazily fused expressions, which need templates Landin does not have.

Exit evidence: the cases of BLAS's own test programs translated as a
fixture, every test ratio under their threshold of 16, on every target;
the `f64` matrix product at n=1000 timed against OpenBLAS on one core.

Done: `core/dense` holds `vector(item)` and `matrix(item)` over
`math.floating`, views over the caller's storage with a step for rows and
one for columns, so either layout, a leading dimension, a transpose and a
block are views of one storage (D2694); a view holds a writable slice and
a routine writes only its `into` (D2695); steps are unsigned, so the
BLAS's negative increments have no counterpart (D2696); a transposed
operand is a transposed view and a triangle the view's own, with
`upper`/`lower`, `stored`/`unit` and `left`/`right` atoms in place of the
BLAS's flags (D2697). A shape mismatch or a view past its storage stops
the program at the call (D2698); `beta` 0 reads no output, `alpha` 0 no
operand, and an empty product is `beta` times the output where the
reference BLAS returns early (D2699). The element-wise operations,
reductions and norms, the rotations, the second level and the third are
written from the mathematics (D2702); `norm_two` and `rotation` scale as
Anderson's Algorithm 978 does, and `modified_rotation` keeps its rescaled
entries where the reference resets them on a second pass (D2701). The
product packs `b`'s panels and `a`'s blocks into a scratch the caller
gives, `product_scratch` long, and multiplies with a 4 by 2 register
kernel, which beat a 4 by 4 one that spilled its sums; a short scratch
cuts smaller blocks and none multiplies unpacked (D2700). `dblat1`,
`dblat2` and `dblat3` of Reference-LAPACK 3.12.1 are translated, their
licence in each fixture's NOTICE and named in `LICENSE`, into
`runtime/dense-blas-level-1`, `-level-2`, `-level-3-f64` and
`-level-3-f32`: every case at both widths, laid out by columns with a
leading dimension and again by rows, every test ratio under 16, the
largest 2.3, on every hosted target; firmware runs every eighth case of
level 2 and every sixth of level 3 in its 20 seconds, and the five large
fixtures, past the 32 KiB of Cortex-M0 and the RV32 lanes, are image
limits there and run on the Cortex-M7 and Xtensa lanes. `runtime/dense-views-and-norms` and `runtime/library-shared-dense`
check the rest exactly. `scripts/dense_timing.py` times the `f64` product
at n=1000 on one Zen 2 core: 0.41 s against OpenBLAS 0.3.33's 0.049 s,
8.2 times, mostly vector instructions refine does not emit (D2703).
Found and fixed: a trap given a `caller` parameter whose type `site` is
declared nowhere stopped checking on an internal defect, pinned by
`negative/compiler-unreachable-undeclared-site`; and `check.py`'s
parameter-order control counted a `math.floating` operand as a
capability. Level 2's own check on the Cortex-M7 lane met the Cortex-M
backend freeing a deferred widening's operand home (D2120) while the
widening was still read, `k * ((k + 1) * k)` giving 4 for 2 at size;
R22.13 fixed the same on main first, and the merge keeps its fix with
`runtime/widening-operand-outlives-product` beside its fixture. Filed: `SR-1978`, the scalar kernel's loop and the missing
vector instructions, and `SR-1979`, an `if` expression's or a literal
range's type taken from a literal or an atom with no note of the written
type that fixes it. It landed in R22.36's train: gate run 45920421418,
passed on its second attempt after the first failed only in SR-1882's
cancellation race and SR-1940's stack-switch step, and boards run
45920432106.

### R22.16 — Linear systems and least squares

Status: planned
Depends on: R22.15

The factorizations and what they solve: LU with partial pivoting,
Cholesky, symmetric indefinite LDLᵀ with Bunch–Kaufman pivoting, QR by
Householder reflections with and without column pivoting, and the
complete orthogonal factorization; solving for one or many right-hand
sides, the determinant, the inverse and condition estimates; linear least
squares for full-rank and rank-deficient problems, minimum-norm
solutions included; tridiagonal systems. Blocked over R22.15's products
as LAPACK's are.

Leaves out: banded and packed forms beyond tridiagonal, constrained and
generalized least squares, equilibration, extended-precision refinement,
updating a factorization after a low-rank change, and complex matrices
(Q-67's answer).

Exit evidence: LAPACK's scaled residual tests for these families, such as
`norm(A - LU) / (n norm(A) eps)`, under its threshold of 20 over its generator's matrix
kinds, on every target; n=1000 timed against LAPACK over OpenBLAS on one
core.

### R22.17 — Eigenvalues and singular values

Status: planned
Depends on: R22.16, R22.11

The symmetric eigenproblem by tridiagonal reduction and implicit QL or
divide and conquer; the singular value decomposition by bidiagonal
reduction; the general eigenproblem by balancing, Hessenberg reduction
and the shifted QR algorithm, its eigenvalues as R22.11's complex
numbers; eigenvectors on request. On them, the functions of a matrix
most fields use: the exponential by scaling and squaring, the square
root, the pseudo-inverse and the rank.

Leaves out: generalized problems over a pair of matrices and the
generalized SVD, eigensolvers for banded and sparse matrices, selecting
eigenvalues by range, reordering a Schur form, the CS decomposition,
other functions of a matrix, and complex matrices (Q-67's answer).

Exit evidence: LAPACK's residual and orthogonality tests for its
symmetric, general and SVD paths under its threshold, on every target;
times at n=1000 recorded against LAPACK over OpenBLAS on one core.

### R22.18 — Small vectors, rotations and transforms

Status: planned
Depends on: R22.10

Vectors and matrices of two, three and four elements as plain values,
the cross product, rotations as matrices, quaternions and axis and angle
with their conversions and interpolation, rigid and affine transforms,
and a perspective projection: what graphics, robotics and a firmware
program fusing an inertial sensor's readings reach for, with no
allocator.

Leaves out: computational geometry (hulls, triangulation, intersection),
dual quaternions and camera models beyond the perspective projection.

Exit evidence: the identities pinned within stated error on every
target, a rotation's inverse its transpose and a quaternion's round trip
among them; image size on Cortex-M0 measured.

### R22.19 — Sparse matrices and iterative solvers

Status: planned
Depends on: R22.15

Sparse matrices in compressed row and column form built from triplets,
their products with dense vectors and matrices, and the iterative
solvers for the systems discretized fields and graphs give: conjugate
gradients, BiCGSTAB and restarted GMRES, with Jacobi, symmetric
Gauss–Seidel and zero-fill incomplete Cholesky and LU preconditioners.
By Q-68's answer the solvers are iterative, and the format is chosen so
that sparse direct factorizations fit as a later addition.

Leaves out: sparse direct factorizations and fill-reducing orderings,
algebraic multigrid, sparse eigensolvers, and block and hierarchical
formats.

Exit evidence: each solver reaching its stated residual on a set of
matrices from the SuiteSparse collection, fetched by hash, on the hosted
targets, and on a small Poisson problem on Cortex-M0; iterations and
times recorded.

### R22.20 — Float text

Status: complete
Depends on: R22.13

Shortest round-trip writing, correctly rounded fixed-precision writing
and correctly rounded parsing of `f32` and `f64` in `core/text`, `SR-97`,
with floats made `formattable`; the parser's slow path uses R22.13's
lower layer. With them `SR-285`: width, padding, alignment, radix and a
float's precision inside a template's `{}`, Rust's format specification
the reference and the spelling decided here. It uses hexadecimal float
literals as R19.10 left them (SC-29). From R20: the byte-sink shape
`formattable` writes to and the names of its failures.

Exit evidence: every `f32` round-tripped exhaustively and `f64` against
an oracle; fixed-precision output byte-equal to C's `printf` over an
oracle set; `docs/from-c.md`'s `printf` entry written with the template;
image size on Cortex-M0 measured.

Done: `core/text` writes a float as the shortest text that reads back,
spelled as a Landin float literal, `1.0`, `0.1`, `1.0e16` (D2754), by
Ryu's method written from the paper, its 668 powers of five computed from
28 bases and two-bit corrections, 620 bytes where the table would be
10.7 KB (D2755); rounded once to places after the point or after the
first digit, byte for byte C's `printf` (D2756); and reads decimal text
rounded once, by Clinger's fast path or exactly over a power of five in
`core/big/limbs` (D2757), an `f32` at its own width throughout. `f32` and
`f64` are `formattable`, and a placeholder takes Rust's format
specification, fill, alignment, `+`, `#`, `0`, a width in scalars,
precision and the kinds `x`, `X`, `o`, `b`, `e` and `E`, without named,
positional or counted arguments (D2758); a conformance reads it from the
builder through `text.placeholder`, so `formattable` and every
conformance written against it are unchanged, and the template pads
what a conformance wrote (D2759). The byte sink stays R20's builder with
`mem.out_of_memory`, and no hexadecimal float literal was needed: the
powers of ten an `f64` holds exactly are decimal literals. `scripts/float_text.py`
writes the powers and the four `float-text-*` fixtures from Python's
`repr`, its exact fractions and C's `snprintf`; with
`runtime/core-text-format-spec` they pass on every hosted target and
the firmware lanes that hold them. Every one of the 4,278,190,080 finite
`f32`s reads back from its shortest text, which is the nearest decimal of
its length or that decimal's neighbour inside the interval, and no
decimal a digit shorter reads back, checked against the exact digits,
and a million drawn `f64`s agree with Python's `repr`, `printf` and
Python's exact parse (compiler/tests/float-text/README.md). `docs/from-c.md`'s
`printf` entry is the template, and two examples print with `{:.1}`.
On Cortex-M0 at `size/auto`, over a program that appends one integer,
`append_f64` is 12.5 KiB, `append_f64_fixed` 11.8, `parse_f64` 21.7 with
soft double's arithmetic, and a float's `format` 28.4; formatting an
integer went from 2.6 KiB to 8.2 with the specification's parsing and
padding, so eight format fixtures' corpus rows record limits at
`none/off` and RV32's 32 KiB maps, with their sizes, and
`compiler/tests/float-text/README.md` holds the figures. Settled: `SR-97`, `SR-285`. The renamed
`negative/format-array-names-its-type` keeps D880's pin now that an
`f64` is formattable. Met on the way: SR-1939's grammar defect again,
in `core/text/shortest.ldn`, and restated; filed: SR-2012, L0102's
`else begin return end` that L0329 then refuses in an `if` arm.

### R22.21 — n-body and spectral-norm ported

Status: planned
Depends on: R22.10, R22.20

The Benchmarks Game's two numeric programs, ported beside its five
already in the repository, with R22.10's `sqrt` and R22.20's nine-place
writing, from the game's single-threaded programs.

Exit evidence: both as runtime fixtures printing the game's small-input
output (n-body within its `ndiff -abserr 1e-8`, held byte for byte), the
digests pinned in `check.py`, both in `examples.md` and in
`workloads.json`'s hosted set.

### R22.22 — k-nucleotide ported

Status: complete
Depends on: R22.20

Counted with `core/map`, as the game requires the library's table: the
key type declares its own `hashable` with a cheap mixer, as the game
allows, while the map keeps D1360's keyed SipHash; percentages written to
three places by R22.20.

Exit evidence: the game's output for its 1,000 input as a runtime
fixture, pinned and published as R22.21's are; the time at 25,000,000
recorded with the map's share measured.

Done: `runtime/benchmark-game-k-nucleotide` reads FASTA's output, takes
record THREE's bases as two-bit codes and counts every run of 1, 2, 3,
4, 6, 12 and 18 of them in a `core/map` table, one a length, and prints
the game's 1,000 file byte for byte, the shares through `{:.3}`; its
input and output digests are pinned in `check.py`, it is in
`examples.md`, and `workloads.json`'s hosted set times it over the
game's file repeated 300 times, a later header left out of the sequence.
The key is a distinct word of two bits a base whose hash is its own
bits, which the map's finalizer spreads, and the map is the library's
with a constant seed (D2934). At 25,000,000 the run took 61 s on the
EPYC host, loaded by another item's job, its counts equal to Python's;
with `cmp.hash_word` as the key's hash it took 96 s. The map's share is
85 per cent: `locate`'s probing 60, the key's equality and hash, called
rather than inlined, 17, and the storage's length and view 9; the calls
are `R551-12`'s evidence entries D339 never copies, where the
measurement is added.

### R22.23 — pidigits ported

Status: complete
Depends on: R22.13

Gibbons' spigot over R22.13's integers, with no GMP.

Exit evidence: the game's output for 30 digits as a runtime fixture,
pinned and published as R22.21's are; 10,000 digits timed.

Done: `runtime/benchmark-game-pidigits` runs the game's step-by-step
spigot over `core/big`, both extractions kept, and prints the game's
30-digit file byte for byte, its digest pinned in `check.py`; it is in
`examples.md` and in `workloads.json`'s hosted set, timed at 500 digits.
10,000 digits, the output equal to Python's, took 9.5 s on the EPYC
host, 4.5 of them the system's: a product written over an operand above
64 limbs and every division's scratch each took a block of their own,
which the hosted heap maps and unmaps. `big.multiply` by one limb now
works in place and a division takes its scratch from the remainder's
block (D2735, pinned by `runtime/big-integer-in-place` in an 8 KiB
arena), and the run takes 4.6 s, 0.02 of it the system's, against 0.49 s
for the game's C program over GMP; 56% of it is Algorithm D's
normalizing passes for a quotient of a limb or two, so `SR-1928` is
restated rather than met. Met on the way and fixed: `compiler/tests/README.md`
counted twenty-three examples where the gate runs thirty, and `measure.py
time` refused a hosted workload the base's tree has no fixture for, so the
commit adding one failed every dispatch's timing; it is now named new.
Landed on R22.33's train: gate 45932328693, boards 45927672738 and
45933311148.

### R22.24 — Tools that say what they need

Status: complete
Depends on: none

The process and measurement tools' refusals and defaults that sent their
users to the source, scheduled by the register sweep of 2026-11-25:
`SR-1756`'s `item.py push` that checks no register age and `merge-main`
that takes a continuous item to main alone; `SR-1798`'s `item.py gate
--main` listing that does not say which run is main's; `SR-1653`'s cited
decision number `spec.md` does not define and the `citations.txt` every
stream regenerates; `SR-1660`'s copied `refine` that does not find its
library in `measure.py count` and the corpora; `SR-1827`'s and
`SR-1828`'s `timing.py`, which takes one run where the gate takes three
and needs a boot check nothing names; `SR-1829`'s `add_fixture.py` and
"Adding a module", which name the corpus's formatting case and not the
library's; `SR-1738`'s library page reader, which refuses an extern
whose name stands on the next line, one line at a time; and `SR-1849`'s
promotion token, for which work that is no item cannot wait in line.
Placed here so that no phase gate waits for it; it depends on no other item.

Exit evidence: each script's or check's tests pinning its change, and the
documents that name a step saying the new one.

Done: `item.py push` refuses a tree the register's age check refuses, or
the whole `check.py` when the push changes the roadmap, before anything
is pushed, and `merge-main` exits 1 naming a row its merge aged;
`merge-main --branch` merges a named branch, a window a continuous item
also lands on, under the same declaration rules and without the token
(`SR-1756`). `item.py gate` names each run's branch and event and says
when main's own gate has not started (`SR-1798`). `check.py` refuses a
decision a compiler comment or reference cites and `spec.md` lacks, and
a local run only notes a citations file whose source line alone is
stale, which the gate and `push` still refuse (`SR-1653`, D2511).
`measure.py count` and the Cortex-M and Xtensa corpora take `--library`
and name a missing library as one; `measure.py time` takes
`--base-checkout` (`SR-1660`). `timing.py run` and `remote` take the
gate's three runs from the constant the gate reads, and refuse to time
the Pico 2's Arm port before its boot check (`SR-1827`, `SR-1828`; the
switch itself is SR-1871). `add_fixture.py` names `refine fmt` of a
changed library module and the library's formatting case, as core's
"Adding a module" does (`SR-1829`). The library page's reader names
every declaration it refuses at once (`SR-1738`), and `item.py queue`
puts work that is no item in line (`SR-1849`). Met on the way and fixed:
`register_next.py --delete` quoted a citation twice after a code span
that wraps a line.

### R22.26 — What refine-build wanted from the library

Status: complete
Depends on: none

The hosted and allocator calls that writing refine-build, the contributed
build command, routed around, scheduled by the register sweep of
2026-11-25 against the library R20 left: `SR-1408`'s child started in a
directory, a PATH search with an executable bit and the program's own
name on every hosted system; `SR-1409`'s copy of bytes into the caller's
allocator that returns the `[]u8`; `SR-1414`'s heap and process memory
readable from a program; and `SR-1412`'s region whose single free gives
nothing back and says nothing, and `core/README.md` naming `core/zone`
(Q-274) as the allocator a nested lifetime takes.

Exit evidence: each call with a runtime fixture on every hosted target and
its fake where the concept has one, `docs/library.md` saying where a
reader looks, and refine-build's workaround for each removed or named.

Done: a child's working directory is the spawn's (D2534): `io.spawn_in`
names one, and `programs`' `spawn` entry, `posix.spawn_in` and
`system.start` take it, a relative program found from the child's
directory on every system, `chdir` in Linux's cloned child,
`posix_spawn_file_actions_addchdir_np` on Darwin and FreeBSD, and on
Windows `CreateProcessW`'s directory with a relative program joined to
it. `io.status` says `executable` and `io.find_program` finds a name on a
`PATH` value as a shell does, passing empty entries over (D2535);
`io.program_name` lends `argv[0]` on every hosted system, Windows' parsed
command line among them, and `io.memory_named` names the memory world
(D2536). `mem.allocate_copy` keeps lent bytes as a `[]mut u8` (D2532).
`heap.in_use`, `heap.peak_in_use` and `heap.peak_resident`, the last
`getrusage` or `K32GetProcessMemoryInfo` (D2533). The region's type,
`vec.release`, `core/README.md` and `docs/library.md` say that a free
into a region gives nothing back and that a nested lifetime takes a zone
(D2531). Pinned by `runtime/run-itself-in-directory` and
`runtime/heap-in-use` and `runtime/find-program-volume` on every hosted
target and `runtime/programs-by-name-memory` and
`runtime/mem-allocate-copy` on every target, the scripted programs, the
volume and the memory world their fakes. refine-build's workarounds, each named here and left to its
own repository: `env -C VIEW PROGRAM` is `io.spawn_in`; the search in
`files/files.ldn` is `io.find_program`; the name written into its
`--describe` is `io.program_name`; `strings.keep` is
`mem.allocate_copy`; the heap handed beside a region is a zone over the
region's parent; and `time -f %M` is `heap.in_use` and
`heap.peak_resident`. `SR-1408`, `SR-1409`, `SR-1412` and `SR-1414` are taken;
SR-1881 records the misleading refusal a new Linux wrapper meets.

### R22.27 — Process tools' remaining faults

Status: planned
Depends on: none

The faults of the process tools met since R22.24, scheduled by the
register sweep of 2026-11-26. In `item.py`: SR-1905's older copy whose
queue wait drops waiters that are no item; and SR-1919's `start`
refusing a continuous item whose text the branch adds without naming
`--base`. In the other tools: SR-1906's `register_next.py --decision` that answers
from a branch behind main's reservations; SR-1917's age rule that differs
during an uncommitted merge; SR-1859's full `check.py` reading untracked
notes; SR-1871's `timing.py`, which leaves the Pico 2's switch to Arm and
back to its user; and SR-1991's item identity that no rule retires.
Placed here so that no phase gate waits for it; it depends on no other
item.

Exit evidence: each script's or check's tests pinning its change, and the
documents that name a step saying the new one.

### R22.28 — What Windows still lacks after R21.70

Status: planned
Depends on: none

The Windows gaps R21.70 left or met, scheduled by the register sweep of
2026-11-26: SR-1746's inlined copies, which CodeView does not describe;
SR-1767's Microsoft lanes, which link with whatever Clang and Visual
Studio the runner image carries; SR-1851's C symbol whose link name
begins with `.L`, which COFF's assembler takes as private; SR-1852's
eight ABI fixtures whose C peers are not Windows C; and SR-1940's arm64
LLDB session that did not step through `landin.stack_switch` once.
Placed here so that no phase gate waits for it; it depends on no other
item.

Exit evidence: each row's completion on both Windows architectures, in
the gate's Windows lanes.

### R22.29 — Release archives that say where they run

Status: planned
Depends on: none

What a user installing a release meets, scheduled by the register sweep
of 2026-11-26, before the next release: SR-1850's macOS archive, which
needs macOS 26 and says so nowhere, Q-347 asking which minimum it states;
SR-1820's `install.sh`, which refuses the FreeBSD archive the release
workflow now publishes; SR-1516's flake, which nothing builds on
`aarch64-linux`; and SR-1894's locked Debian packages, which nothing
fetches until a candidate's gate does. Placed here so that no phase gate
waits for it; it depends on no other item.

Exit evidence: the release workflow's checks and `install.sh`'s tests
holding each change, the flake built for `aarch64-linux` in the gate,
and the scheduled package fetch's first run.

### R22.30 — Text and Unicode

Status: complete
Depends on: R20

Character properties, case, normalisation and segmentation over `utf8`,
from a generated UCD table: SR-98's Unicode half. Settles how a large constant table is laid
out and what it costs a firmware image. From R20: where it lives, the
sink it writes to, the end-of-iteration form segmentation uses, and
whether it iterates through `iterable`.
Exit evidence: the Unicode conformance test files pass; the generator's
check in the gate; table cost on Cortex-M0 measured.

Done: `core/unicode` (D2615) has the general category, the combining
class and six binary properties, simple and full case mapping with the
final sigma and title case (D2619), the four normalization forms with no
buffer (D2620), and grapheme, word and sentence boundaries with `for`
walks over `iter.iterable` (D2618), every text routine appending whole or
nothing to a `text.utf8_builder` (D2616). `scripts/unicode_tables.py`
writes its tables from the pinned Unicode 18.0.0 database in stages of
repeated blocks (D2614), and the fixtures' oracles: Unicode's normalization test
and its three break test files pass on every hosted target, every table
is checked against the database by a digest of every scalar, and firmware
walks every Nth scalar within the corpus's 20 seconds; the script test
holds the tables to the pin in the gate. On Cortex-M0 at `size/auto` a
program links only the tables it reaches (D2617): 5,388 bytes for
grapheme clusters, 12,420 for the general category, 19,817 for NFC and
NFD, and 36,084 for all four forms, which do not fit the 32 KiB profile.
Q-321 asks how Unicode's notice goes with a program; SR-1938 records the
hosted backends' writable sections for immutable data, met laying out
the tables.

### R22.31 — Refusals that say what to do

Status: planned
Depends on: none

Refusals met since R20.61 that do not say what to do, or say something
misleading, scheduled by the register sweep of 2026-11-26: SR-1693's
L0201 at a library module no import reaches, and SR-1881's at an
undeclared `*_number` of `platform/linux`, both with [1860]'s note to
check the spelling; SR-1896's L0011 at a hexadecimal float without its
point; SR-1714's internal defect where a firmware assembly operand is
linked; SR-1716's developer's linker script that puts a routine at
address zero without a refusal; and SR-1214's misuse traps of the root,
which carry no words. Placed here so that no phase gate waits for it; it
depends on no other item.

Exit evidence: each refusal pinned by a negative fixture or a driver
case, and `docs/diagnostics.md` saying the new notes.

### R22.32 — Defects the library work met

Status: planned
Depends on: none

Defects R19 to R22.30 met beside their own work, scheduled by the
register sweep of 2026-11-26: SR-1938's immutable module arrays in a
hosted image's writable section; SR-1939's Tree-sitter grammar, which
misreads a sum of three operands followed by a statement; SR-1568's
anonymous-function paths that nothing reaches since D1654; SR-1882's
cancellation test, which signals `refine` before its handlers are
installed on a loaded host; and SR-1740's runtime outcome that never
ends and holds the whole test program until the job's limit. Placed
here so that no phase gate waits for it; it depends on no other item.

Exit evidence: each row's completion with the fixture, corpus test or
control it names.

### R22.33 — Boards reused on identical images

Status: complete
Depends on: none

A promotion's boards taken from the last passed boards run when every
input of the board jobs is the same bytes, which the maintainer accepted
on 2026-11-26 from the gate-time study of that day: 31 of the 39 boards
runs from 2026-11-20 ran images byte-identical to the passed run before
them, while the rig, one leg at a time, was busy seven to eleven hours a
day and found two defects in about 270 runs, both in its own harness.
The identity is every boot, RAM and timing image and link script
`board-bundles` builds, the harness the legs run and the hardware
records the strict build reads, each path named by the item, and the
board jobs' own workflow text. `files.sha256` mixes in `bundle.json`,
`timing.json` and `commands.json`, which name the commit, so the
identity is a list of its own that leaves out what names the tree and
nothing else. A boards dispatch, or main's push, whose identity equals
that of a passed boards run under a week old takes that run's legs and
cycles, as main's push already takes a passed run of the same tree
(D1647), and the aggregate names the run it took. The weekly boards run
becomes daily on main when main moved, so a board or probe that degrades
shows within a day, until R22.37's daily complete gate takes it over. Placed here so that no phase gate
waits for it; it depends on no other item.

Exit evidence: controls that an image, harness, record or workflow change
each breaks the identity and a change that only names another commit
does not; a dispatch whose images match a passed run's taking it and one
whose images differ running the legs, both named runs; the nightly run's
first pass; process.md's "Physical boards and promotion" and AGENTS.md's
gate paragraph saying the rule.

Done: `board-bundles` writes the board identity as its annotation, digests
of the bundles' files less what names the tree or the build's clock, of the
timing bundle when the event times, of the blobs under
`environments/boards/` and `compiler/tests/board/` with the hardware
records apart, and of the board jobs' text less comments, and
`gate_inputs.py legs` takes the legs of a passed run under a week old whose
identity matches part for part, naming each part that differed (D2774); the
aggregate reads the taken run's evidence, held to its run id, and compares
its cycles. The schedule runs daily and leaves out a commit a passed
schedule run already ran (D2775). Two board-bundles artifacts of different
commits, runs 45840509189 and 45855853447, give one identity. Boards run
45893119145 ran every leg and passed; dispatch 45906315984 on the same
head took its legs and passed in 13 minutes. On the train with R22.23,
boards 45927672738 refused that run's legs, its harness alone differing,
and ran them, and 45933311148 on the next commit took 45927672738's legs,
timing images included; the train's gate is 45932328693. `item.py boards` met no
`SR-1988` of its own: the item fixes that landed first record a queued
dispatch as boards.

### R22.34 — Figures recorded from the run that measured them

Status: planned
Depends on: none

The size, instruction-count and cycles figures an emission change moves,
the gate's largest single cause of failure since the week of 2026-11-16:
48 of the 254 defects the gate-time study of 2026-11-26 classified, 18
that week and 25 in the three days after it, each a whole gate cycle
spent only to record what the failed run had measured. The maintainer
accepted the change that day. On a branch push the measurement lanes,
`measure-size`, Darwin's and FreeBSD's size steps, the Cortex-M
instruction counts and the boards' cycles comparison, report an
undeclared move in the run's summary and artifact and pass. A commit
that records exactly the figures of a passed run's artifact
(`measure.py record --from-run`, `timing.py record`) and changes nothing
else reuses that run's pass, as the cycles baselines' leaving the key
already lets (D1650); the `inputs` job holds the recorded files to the
artifact rather than trusting the declaration. A pass that reported a
move can be reused only by the commit that records it, and main's push
refuses a tree whose last pass reported a move not recorded since.
Placed here so that no phase gate waits for it; it depends on no other
item.

Exit evidence: controls that a branch push with an undeclared move passes
and names it, that main refuses one not recorded, and that a recording
commit reuses only when its figures equal the artifact's; one
emission-changing candidate landed on one gate, its recording commit
reusing it, named runs; `docs/measurement.md` and process.md saying the
steps.

### R22.35 — Checks too long for a gate, by record

Status: planned
Depends on: none

The exhaustive and other checks too long for any regular gate, which the
maintainer excluded from them in general on 2026-11-26, answering Q-307.
Such a check runs on a host and is recorded in a file beside it: the
command, the host, the date, the result and the digest of the emitted
code it checked, for R22.10's exhaustive `f32` run each checked
function's object code on each target the record claims. A script the
`scripts` job runs in seconds compiles the same code and says whether
each record is fresh or stale since a commit. A stale record fails no
push; it blocks a release, or a phase-gate claim, that cites it. The
rule is recorded as a decision in `spec.md`, and R22.10's runs are the
first record. Placed here so that no phase gate waits for it; it
depends on no other item.

Exit evidence: the script's tests, a record fresh after a change
elsewhere and stale after a change to the code it checked; R22.10's
record and its check in the `scripts` job; the release checklist in
process.md naming stale records.

### R22.36 — Failure causes recorded, and the selection in shadow

Status: active
Depends on: none

Why a gate job failed is recorded nowhere: the gate-time study of
2026-11-26 rebuilt it from 1,024 job logs. The gate records it itself:
for each failed job, whether a re-run of the same tree passed it and
whether the branch's next push changed the tree, the rule that agreed
with the study's readers on 90% of the jobs it called defects and found
97% of theirs, refined by recorded outside signatures, a mirror's 403 or
a probe's DMI timeout among them. From that history a script keeps the
lane table the selection reads, a file in the tree, so the same tree
always selects the same lanes; each lane declares its inputs there, and
a control keeps every gate job in it. A branch job whose failure matches
an outside signature is re-run once, automatically, and the summary
names the re-run; main's gate is still investigated, never rerun
blindly.

The `inputs` job then computes the selected gate and writes into the
summary what it would have skipped, skipping nothing: it keeps each lane
whose declared inputs the change reaches; each lane that runs emitted
code whose target's emission digest, from the determinism manifests,
its harness or its expectations differ from those of a passed run; each
lane that in the last eight weeks was the only lane to show a defect, is
under four weeks old, costs under five job-minutes or checks the
evidence itself, the build comparisons; and every other lane on one
selected gate in four, drawn from the tree's hash. The maintainer
accepted those values on 2026-11-26, and that shadow mode comes first.
It runs for about 200 complete gates, the length Q-364 asks the
maintainer to confirm. Placed here so that no phase gate
waits for it; it depends on no other item.

Exit evidence: a cause recorded for every failed job of the shadow
period, with the outside signatures that re-ran; the lane table and its
control; every gate's summary naming the lanes it would have skipped;
and the measured miss rate, the defects that only skipped lanes showed,
set against the study's replay of November, 1.7 a week.

Landed, the shadow period to run: `scripts/gate_history.py`, the lane
table `.github/gate-lanes.json` with its control, the causes of the
1,025 failed jobs from 2026-09-21 in `.github/gate-causes.jsonl`, the
`inputs` job's selection and the aggregate's record of it and of the
outside signatures, and `gate-rerun.yml` (D2794-D2798). Against the
study's readers the rule with its signatures agreed on 96.5% of its
defects and found 97.3% of theirs, on the logs the signatures came from.
On the history to that day it samples `arm64-compiler`,
`arm64-compiler-checks`, `build-modes`, `darwin-host`,
`darwin-debug-build`, `rv64-qemu`, the three determinism hosts and
`freebsd-arm64-runtime`; the study's replay sampled the same but
`rv64-qemu` and `darwin-debug-build`. No lane is keyed by its emission
yet (SR-2032). The miss rate is read with `gate_history.py shadow` and in
the table's `shadow` entry, which the weekly `table --write` keeps.
Its own gate run 45902780283 and boards run 45902794687 passed; it landed
with R22.15 as one train on gate run 45920421418, passed on its second
attempt after two known flakes (SR-1882, SR-1940), and boards run
45920432106. The shadow period, the causes it records and the measured
miss rate remain for the item to close.

### R22.37 — The selected gate applied

Status: planned
Depends on: R22.36
Promotion: maintainer

The selected gate R22.36 measured, applied once the maintainer accepts
its miss rate. A development push runs it unless it asks for the
complete gate, and an item lands on main on the selected gate and main's
own gate: an item's landing is no longer tied to a complete gate
(the maintainer, 2026-11-26). The complete gate, every lane and the
boards with no reuse, runs at every phase's gate claim, and on main once
a day when no phase gate ran that day and main moved (the maintainer's
answer to Q-363); a phase gate is claimed on a commit a complete gate
passed, and R22.38 puts each release on such a tree. A scheduled
complete gate that fails holds only the landings whose changes reach the
failing lanes; those lanes alone are dispatched on each tree landed
since the last complete pass to name the commit, and its item fixes
forward at the head of the line.
Mechanics' completion rule, "the complete gate passed on the completing
commit", becomes the selected gate on the landed tree and the first
complete gate that covers it; R16's and R22's standing baselines hold on
every push that changes the emitted code and on every complete gate.
Placed here so that no phase gate waits for it; it depends on R22.36
alone.

Exit evidence: controls that a selected pass is enough for a branch and
for main's push, and that a phase-gate claim refuses a commit no
complete gate covered; the search command's tests; the first
scheduled complete gate; a week of landings on the selected gate with
the complete gates that covered them named; AGENTS.md's "The mechanical
gate", process.md's gate reference and the landin-change skill saying
the rule.

### R22.38 — Releases on a gate that runs anyway

Status: planned
Depends on: R22.37

A release runs no complete gate of its own: the maintainer asked on
2026-11-26 that releases be planned to reuse or share an existing gate.
Today the recipe's declaration commit is a candidate like any other, its
own gate, boards and promotion, and the flake-hash commit after the tag
is gated and promoted again, two complete gates for one release. The
recipe in process.md's "Releasing a version" changes so that the
declaration lands on, or provably beside, a tree a complete gate passes
anyway: made before a phase-gate claim, so that the claim's complete
gate is also the release's, or onto the day's complete gate. It can
then reuse that pass only if it changes nothing a lane reads, which it
does not today: besides the explanatory README, `handoff.md`,
`docs/capabilities.md` and the site's `VERSION_LINE`, it edits the
version line of `tour.md` and each prototype's "Current with" line, so
the item either leaves those lines out of the key or moves the version
out of them, and `release.py gated` accepts a tag on the declaration
when the pass it reused was complete. The flake-hash commit changes only
`releaseVersion` and `releaseHashes`, which no lane but the flake jobs
reads: it reuses the pass and runs those jobs alone. The version, the
declaration and the tag stay the maintainer's; the item changes the
recipe and releases nothing. Placed here so that no phase gate waits for
it; it depends on R22.37 alone.

Exit evidence: controls that a declaration commit reuses a complete pass
and a change to anything a lane reads does not, that `release.py gated`
takes a declaration on a reused complete pass, and that a flake-hash
commit reuses and runs the flake jobs; a rehearsal of the release
workflow on such a tree; process.md's recipe saying the steps.

### R22.40 — Character encodings

Status: planned
Depends on: R22.30, R21.10

Conversions between `utf8`, `utf16` and the legacy encodings from
generated WHATWG tables, whole scalars or nothing into a caller's buffer.
Implements `utf16` as R21.10 decided it. From R20: the failure names and
the buffer conventions.
Exit evidence: the WHATWG test data pass on every target the namespace
admits.

### R22.50 — Locale formatting

Status: planned
Depends on: R22.20, R22.30

Numbers and text formatted for a locale, an explicit value from a BCP 47
identifier and never global state, from generated CLDR data a program
uses in part: SR-98's locale half, with R22.20's template width and
precision applied to a locale's digits and separators. From R20: a
locale is an explicit value (D1955), and the host's preferred one is read
through `hosted/system`; how formatting evidence takes one is this item's.
Exit evidence: CLDR's own test data pass for the locales generated; a
program that uses one locale carries only its data.

### R22.60 — Regular expressions

Status: complete
Depends on: R22.30

`core/regex`, `SR-100`: patterns compiled at run time with the caller's
allocator and matched in linear time; Unicode classes from R22.30's
tables; a match's position and captures, iteration over the matches, and
replacing every match from a template. Built on the established
strategies, the basis R22.80 later measures: a literal prefilter for a
leading byte, a substring or a small set of literals; a one-pass engine
where the pattern allows; a lazy DFA with a bounded cache, run in reverse
for a match's start; and a Pike VM for captures and as the fallback,
chosen per pattern as RE2 and Rust's `regex` choose. From R20: the
allocator and capability shape, and how a match position is named.

Leaves out: backreferences and look-around, which lose linear time; a
DFA compiled ahead of time; vectorised literal search; sets of patterns.

Exit evidence: linear time pinned on adversarial patterns on a hosted
target and on Cortex-M0; Rust's `regex` test suite passing for the
supported syntax, regex-redux's patterns among the cases; every engine
checked against the Pike VM on generated patterns and inputs, as RE2's
tester does.

Done: `core/regex` reads the `regex` crate's syntax, less backreferences
and look-around, with four failure atoms (D2674), compiles it to a byte
program whose classes are UTF-8 tries (D2675) into storage its searches
reuse, allocating nothing after `compile` (D2677), and chooses per
pattern among a literal prefilter, a lazy DFA run forward and reversed,
the one-pass DFA and the Pike VM (D2678); a DFA state holds its threads'
step targets, so its closure keeps the Pike VM's order (D2679). Walks,
`for` over `matches` and `replace_all` follow the crate's empty-match
rule (D2681), and `(?i)` takes each scalar's simple folding orbit
(D2682). Unicode's tables come through the options' function values, so
`lean()` links none (D2676), and `core/unicode` gains
`category_run_end` and `property_run_end`, from per-block tables its
generator writes, so `\w` compiles a run at a time. The crate 1.12.2's
suite, pinned by hash, passes all 897 cases the library can state
(`runtime/regex-rust-suite`), and regex-redux's patterns count and
replace over the game's FASTA as Python's `re` does
(`runtime/regex-redux-patterns`);
`runtime/regex-engines-agree` checks every engine against the Pike VM on
seeded generated patterns, and `runtime/regex-linear-time` pins linear
work on ten adversarial patterns on every hosted target and on the
Cortex-M7 corpus lane (D2680): the engines are 140 KB of Thumb code, so
the 32 KiB ARMv6-M profile records a size limit, which Q-336 asks about
and SR-1968 records. `SR-100` is taken.

### R22.61 — A finished `for` no longer holds its source

Status: complete
Depends on: none

`SR-1405`, a checker defect met writing refine-build (its friction entry 3)
and scheduled by the maintainer on 2026-11-19 ahead of its phase: inside
an outer loop, releasing a list after a `for` over it has ended is L0315,
naming the `for`'s element as still viewing the list. D1084 holds a
`for`'s source only for a call in its body, and D1370 makes a declaration
that runs again a new binding; the reference check's back-edge scan reads
the element in the `for`'s body as the binding asked about. Placed here
so that the R18 gate does not wait for it; it depends on no other item.

Exit evidence: the release accepted after the `for` under `loop`,
`loop ... break when` and `while`, with the list declared inside or
outside the outer loop, by a runtime fixture; a negative fixture still
refusing the release inside the `for`'s body.

Done: D1623 makes a `for`'s element and index new bindings on every walk,
and the reference check's back-edge scan stops at a `for` that binds the
view asked about, reading only its traversal bounds (`SR-1405`).
`runtime/for-finished-in-outer-loop` runs the release after the `for`
under `loop` with its test first and last, `while`, a list declared
outside and a deferred release; `negative/for-source-held-in-outer-loop`
still refuses the release inside the body and one while a kept element
views the list. Gate run 44525120865 (attempt 2; attempt 1's Darwin
artifact upload failed on DNS) and boards run 44535495255 on f968ab7f3.

### R22.62 — regex-redux ported

Status: planned
Depends on: R22.60

The Benchmarks Game's regex program over `core/regex`, its five
replacements by R22.60's replace-all.

Exit evidence: the game's output for its 1,000 input as a runtime
fixture, pinned and published as R22.21's are; 5,000,000 timed.

### R22.63 — The ten programs measured

Status: planned
Depends on: R22.21, R22.22, R22.23, R22.62

`docs/benchmarks.md` compares all ten programs of The Computer Language
Benchmarks Game with the same languages, single-threaded as its method
is, from a script kept in the repository that fetches the other
languages' programs by hash and pins their toolchains, so that one
command reproduces the table. The repository's documents call the game
by its own name.

Exit evidence: the script, the table it wrote for the ten, and its run
recorded.

### R22.70 — Functions of one variable

Status: planned
Depends on: R22.11

Roots by bisection, Brent's method and bracketed Newton; minimization by
golden section and Brent's method; numerical differentiation;
quadrature by Gauss–Legendre and adaptive Gauss–Kronrod rules, over
infinite intervals by substitution; interpolation by barycentric
polynomials, cubic and monotone splines and tables; polynomials, their
arithmetic and all their roots as R22.11's complex numbers; Chebyshev
approximation.

Leaves out: cubature in several dimensions, rational and minimax
approximation, and symbolic differentiation.

Exit evidence: each method on test problems with known answers within
its stated tolerance on every target, its function evaluations recorded.

### R22.71 — Optimization

Status: planned
Depends on: R22.16, R22.70

Minimizing a function of many variables with line searches: BFGS,
limited-memory BFGS with bounds, and nonlinear conjugate gradients;
Nelder–Mead without derivatives; nonlinear least squares and curve
fitting by Gauss–Newton and Levenberg–Marquardt; systems of nonlinear
equations by Newton's method and Powell's hybrid method; dense linear
programs by the simplex method. Derivatives come from the caller or by
finite differences.

Leaves out: general nonlinear constraints, integer and mixed-integer
programming, global and stochastic methods, automatic differentiation,
and conic and semidefinite programming.

Exit evidence: the Moré–Garbow–Hillstrom problems and a set of small
linear programs solved to stated tolerances on every target, evaluations
recorded.

### R22.72 — Differential equations

Status: planned
Depends on: R22.16, R22.70

Initial value problems of ordinary differential equations: fixed-step
Runge–Kutta, adaptive embedded pairs with dense output, an implicit
method for stiff systems over R22.16's factorizations, symplectic
integrators for mechanics, and events located by R22.70's roots.

Leaves out: boundary value problems, delay, stochastic and
differential-algebraic equations; partial differential equations are
R22.75's.

Exit evidence: problems with known solutions within tolerance, stiff
problems such as Robertson's and van der Pol's among them, on every
target; steps and evaluations recorded.

### R22.73 — Fourier transforms and signals

Status: planned
Depends on: R22.11, R22.14

The fast Fourier transform of any length, by mixed radix and Bluestein's
algorithm, for complex and real data in one and two dimensions, with its
inverse and the DCT-II and DCT-III; convolution and correlation directly
and by transform; window functions; FIR filters, IIR filters as biquad
sections, and the design of windowed-sinc and Butterworth filters. The
transform and filters in Q15 and Q31 through R22.14, for firmware.
SR-1949's `core/complex` errors, `tanh`, `tan` and `pow`, are brought
within a few ulp first, since the transforms take its arithmetic and
`exp` as their kernels (register sweep of 2026-11-26).

Leaves out: wavelets, the other DCT and DST kinds, more than two
dimensions, number-theoretic transforms, and adaptive filters.

Exit evidence: transforms against a direct transform computed in higher
precision, error growing with log n, on every target; filters against
reference responses; the Q15 transform's cycles on Cortex-M0 recorded on
the rig.

### R22.74 — Statistics and probability

Status: planned
Depends on: R22.12, R22.16, R22.70

Descriptive statistics, streaming and stable: mean, variance and higher
moments, quantiles, histograms, covariance and correlation. The common
distributions' density, distribution and quantile functions and sampling
over `core/random`'s generator: uniform, normal, log-normal, exponential,
gamma, beta, chi-squared, Student's t, F, Weibull, binomial, Poisson,
geometric, negative binomial and the multivariate normal. The standard
tests with their p-values: t-tests, chi-squared, Kolmogorov–Smirnov and
the rank tests; linear regression with its standard errors.

Leaves out: generalized linear models beyond R22.76's logistic
regression, Bayesian inference and Markov chain Monte Carlo, time-series
models, survival analysis and data frames.

Exit evidence: values against a reference computed outside the program,
named with its version; sampling checked by goodness of fit at fixed
seeds; streaming moments against two-pass results on ill-conditioned
data; on every target.

### R22.75 — Fields on meshes

Status: planned
Depends on: R22.19, R22.72

Partial differential equations discretized: finite differences on
structured grids, and finite volumes on unstructured polygonal and
polyhedral meshes in OpenFOAM's form, cells and faces with an owner and a
neighbour; gradient, divergence and Laplacian operators with upwind and
central interpolation; fixed-value and fixed-gradient boundaries;
assembly into R22.19's sparse matrices; time stepping by R22.72's methods
or implicitly. Its consumer is an example program for heat conduction
and scalar transport.

Leaves out: mesh generation and mesh file formats, finite elements,
pressure–velocity coupling for flow, turbulence models, adaptive
refinement and parallel decomposition.

Exit evidence: manufactured solutions converging at each scheme's order
on structured and unstructured meshes on the hosted targets; the example
program in `examples.md`.

### R22.76 — Learning from data

Status: planned
Depends on: R22.17, R22.71, R22.74

The methods most data work starts with: k-means clustering with
k-means++ seeding, principal component analysis by R22.17's SVD, k
nearest neighbours over a k-d tree, linear, ridge and logistic regression
with regularization, naive Bayes, decision trees for classification and
regression, and the usual scalings and cross-validation splits.

Leaves out: neural networks, support vector machines, ensembles such as
forests and boosting, Gaussian mixtures, kernel methods and
reinforcement learning.

Exit evidence: each method's results on public datasets fetched by hash
against an established implementation's, recorded with its version; k-d
tree queries against brute force; on every target.

### R22.80 — The library measured

Status: planned
Depends on: R22.18, R22.40, R22.50, R22.63, R22.73, R22.75, R22.76

The basis of R22's continuous lane, as R16.10 is of R16's: the time and
size of the library's own code measured, held in the gate and ranked.
Its workloads are each module's operations at stated sizes, the ten
programs of R22.63, and the reference libraries' times on one core for
the same operations (msun, GMP, OpenBLAS and LAPACK, FFTW, RE2 and PCRE2
among them). It measures by R16.10's contract in `docs/measurement.md`
and keeps its baselines beside R16's. A cost of the code the compiler
emits goes to R16's lane; a cost of the library's algorithm, data layout
or blocking goes to R22's.

Exit evidence: the workloads and baselines on every target their
namespaces admit, held as R16.10's are; a ranked list of each part's
largest costs against its reference, from which R22.90 takes its scope.

### R22.90 — The library's first costs

Status: planned
Depends on: R22.80

The costs at the head of R22.80's ranked list.

Exit evidence: each cost taken measured lower than its R22.80 baseline,
and no other workload over its own.

### The library's continuous items

Numbered on from R22.90, each is added when it is taken up, or planned
when an item splits it off, with its own status and a dependency on
R22.80. Each takes one cost from R22.80's ranked list, in any part of the
library. Exit evidence: the cost measured lower against its R22.80
baseline, and no other workload over its own.

### R22 gate
Each addition on every target its namespace admits, with its oracle; each
generated table held by its check; the ten programs measured by the kept
script. Once R22.80 is complete, the library's baselines are a standing
invariant every push keeps, as R16's are.

## R23 — Install routes

Four routes to an installed `refine`, which the maintainer added on
2026-11-20. Today a release archive (Linux x86-64, Linux arm64 and macOS
arm64, the Linux ones linked against glibc), nix, which builds from source
in minutes, a Homebrew tap kept outside the repository, and a build from
source are the ways in; a newcomer on NixOS, Alpine or in a container has
none that is quick. These items make the releases that exist reachable:
they add steps to the release recipe and the flake, and make no release
and change no version, which stay outside this roadmap. Package
repositories (apt, rpm, the AUR) and further hosts (Windows, an Intel Mac,
FreeBSD) are not among them; R21 owns Windows and `refine` on FreeBSD.

Their dependencies are inside the phase, so each may start beside the
serial lane's item, as R17.50 did; while R19 to R22 have an item, the
pointers keep naming it. An item that changes a step of the release
recipe writes that step into `docs/process.md`. The recipe, a declaration
commit, the gate, the tag, the release workflow's publication and the
commit that records the published hashes in the flake, is written today
only in comments of `.github/workflows/release.yml` and `flake.nix`, so
the first such item writes the whole recipe down.

### R23.10 — Container images on releases

Status: complete
Depends on: none

Two images under `ghcr.io/701-dev`, for Linux amd64 and arm64 in one
manifest each, published by the release workflow and only at a release,
never from main or a commit. The user image holds a release archive's
prefix (`bin/refine`, `libexec/landin`, `lib/landin`) and the C compiler
and binutils `refine` links with, under the GNU triplet name it asks for
(`libexec/landin/<triplet>-gcc`, as `flake.nix`'s `refineBin` arranges);
it is built from the two Linux release archives without compiling. The
contributor image is the pinned GNAT and GPRbuild environment for building
the compiler, grown from `environments/linux-amd64/Containerfile` with an
arm64 counterpart; it reads `environments/pins.sh`, so `check.py`'s pin
agreement covers it. Neither carries a Cortex-M, RISC-V or Xtensa
toolchain; the installing documentation says how a user adds the
dependencies for a cross build, and that debugging inside a container
needs `--cap-add=SYS_PTRACE`. A base image's packages move only at a
release. Whether a release also moves a `latest` tag is Q-65.

Exit evidence: a gate job that builds the user image from the gate's
packaged release compiler and compiles and runs the first program inside
it, as `outside-user-stock` does outside one, on amd64 and arm64; the
contributor image built and the compiler built inside it, in the gate or,
where its cost forbids, in the release workflow; the release workflow
building and checking both images before its approval and pushing them
after it, shown on a run whose push is withheld; both images in the
installing documentation and `docs/capabilities.md`; the release recipe's
image step, and how to check a published image, written in
`docs/process.md`. The first published images are the next release's
evidence, not this item's.

Done: `environments/images/user.Containerfile` unpacks a Linux
release archive into `/usr/local` over Debian 13's own `gcc` and
`libc6-dev`, whose driver names `refine` already asks for, so no
`libexec/landin/<triplet>-gcc` link is made (D1667);
`environments/images/contributor.Containerfile`, the former
`environments/linux-amd64/Containerfile`, installs the toolchain through
`pins.sh` for amd64 or arm64 and names no version, and `check.py` holds
both recipes to the pins (D1668). `scripts/container_image.py` builds,
checks, saves and publishes both; the gate builds the user image from its
packaged compiler in `outside-user-stock` and `arm64-release` and runs
the first program in it as the README says. `release.yml` builds and
checks both images, the contributor one by building the compiler inside
it, and assembles each into one two-platform index before the approval,
then pushes and attests them after the release is public, tagged with the
version alone (Q-65's default); a `rehearse` dispatch runs all of it on
any ref and publishes nothing (D1669). Rehearsal run 44823357861 on
bddf062e7 is the run whose push is withheld; its two predecessors found
that an untagged commit's compiler is `refine dev` and that podman could
not push a list made from loaded archives, now assembled with skopeo. It
also measured that GDB in the user image stops at `main` without
`--cap-add=SYS_PTRACE`, which then only leaves the address-randomisation
warning in place, so the README says that instead. `docs/process.md`
writes the whole release recipe down in a section of its own, image step
and published-image checks included. Gate run 44823246775 on bddf062e7.

### R23.20 — Nix installs the prebuilt compiler

Status: complete
Depends on: none

`nix profile install github:701-dev/Landin` builds `refine` from source,
which takes minutes, though the flake already has `refine-bin`, the
published release archive for the same three hosts, which the installing
documentation does not name; and the flake defines no `apps`, so `nix run`
has nothing to run. The route the documentation gives takes the prebuilt
compiler on a host the release covers and the source build elsewhere, and
`nix run github:701-dev/Landin -- ...` runs `refine`. The source build
stays one name away for a contributor and for a host without an archive.

Exit evidence: `nix profile install` and `nix run` of the documented
reference fetching the release archive rather than compiling, and the
source build still reachable, in the gate's flake jobs; the installing
documentation giving both commands; the release recipe's flake-hash step
in `docs/process.md` checking `nix run` against the newly published
archives before that commit is promoted.

Done: the flake's default package is `refine-bin`, the release archive,
on every system whose release hash it records, all three today, and the
source build stays `#refine`; `apps.default` runs `bin/refine` from the
default, so `nix run github:701-dev/Landin -- ...` runs the released
compiler (D1707). The README gives `nix profile install`, `nix run` and
`#refine`, and keeps `profile install`, which Nix 2.34 calls an alias of
`add`, because older Nix has no `add`. `scripts/nix_route.py` installs the
flake into a scratch profile and holds it to the `refine-bin` store path
and version, runs the first program through `nix run`, and refuses a
`#refine` that is not the source build; the gate's `flake-compiler` leg runs it after building both
packages, and `test_nix_route` holds its refusals. The release recipe's
flake step runs it on the branch that moves the hashes and checks
`nix run github:701-dev/Landin -- version` once that is on `main`. Gate
run 44873069309 and boards run 44875115933 on the merged tree 9e62c8b88.

### R23.30 — A one-line install script

Status: complete
Depends on: none

A script a user pipes from `curl` into `sh`: it names the release archive
for the host it runs on, downloads it and its `.sha256`, refuses on a
mismatch, unpacks it into a directory of the user's choosing or a default
under the home directory, and says what to put on `PATH`. A host no
archive serves is refused with the routes that do serve it. It installs a
named version or the newest, and says it can check the archive's
attestation with `gh` when that is installed. Where the script is served
from, the address the documentation prints, is Q-66.

Exit evidence: the script run in the gate on Linux x86-64, Linux arm64
and macOS arm64 against the gate's packaged compiler served as a release
would be, installing a program that runs the first program, and refusing
a damaged archive and an unserved host, each in a control; the
installing documentation's command; the release recipe's step that checks
the script's archive names against the assets the release workflow
publishes, in `docs/process.md`.

Done: `install.sh`, served unchanged at `https://www.701.dev/install.sh`
(Q-66's answer), which the site's render copies from the repository,
installs the host's release archive into `~/.landin` or `--dir`, the
newest release or `--version`, after checking it against its `.sha256`;
it replaces an earlier install whole, refuses a directory holding anything
else, edits no shell profile, prints the `PATH` line and, when `gh` is
installed, the attestation commands; it refuses a host no archive serves,
NixOS and a Linux without glibc's loader among them, naming nix and the
source build (D1747). `scripts/install_check.py` serves a packaged
compiler from 127.0.0.1 in a release's layout and runs the script against
it: the newest and a named version installed and running the first
program, a reinstall, a foreign directory, a damaged archive, a missing
version and two unserved hosts refused; the gate runs it in `release`,
`arm64-release` and `darwin-host-release`, and
`test_install_script` runs the cases against a stand-in archive and holds
the script's names to `release.yml`'s. The README gives the command first
among six routes, and the release recipe's check of the published
release runs `install_check.py --published`, holding the names to the
release's assets, and the documented command. Met on the way and fixed:
the links check would race the Pages deployment on the push that
publishes the script, so `lychee.toml` leaves that one address to the
render and the recipe. Q-65 is answered too: version tags only. Gate run
44896732794 and boards run 44898787764 on the merged tree fcd9ada74.

### R23.40 — Whether a static Linux `refine` can be built

Status: complete
Depends on: none

A Linux `refine` linked statically, against musl, would run on Alpine,
NixOS and a minimal container without the glibc loader the Linux archives
ask for. Nobody knows whether the pinned GNAT makes that hard: its runtime
is built for glibc, and its tasking, exceptions and the C adapters each
need a look. This item looks, tries a static build of `refine` and the
split commands on Linux x86-64 and arm64, and writes what it found, with
the cost and the toolchain it would pin, under `roadmap/inputs/`.

Exit evidence: the finding in `roadmap/inputs/`, with a static `refine`
that passed the release test program if one was built; R23.50 confirmed or
rewritten to match, or, if it cannot be done at a cost worth paying, a
question asking the maintainer to retire it.

Done: the pinned GNAT links `refine`, its four split commands and the
test program statically against glibc with no source change: the GNAT
runtime was static already, nothing calls the name service, `dlopen` or
`iconv`, and the build only adds `-largs -static` or `-static-pie`. On
Linux x86-64 both builds passed the whole release test program, 1279
cases each. The arm64 build, made under emulation, passed the suites it
reached before runtime fixture execution, which emulation could not finish;
R23.50's gate job runs it natively. Both architectures' archives ran in
Alpine 3.24's minirootfs with no glibc, the first program through Alpine's
`gcc` and five `--link=libc` fixtures against musl. The archive grows
3.7 %. musl would need a GNAT 16.1 toolchain built and maintained by the
project, since none is published, for no reach static glibc lacks; the
finding is `roadmap/inputs/static-linux-refine.md`, R23.50 is rewritten to
it, and Q-116 asks whether the static archive replaces the glibc ones,
defaulting to yes. Met on the way and fixed: the flake's `aarch64-linux`
shell and `refine` package did not build, GPRbuild's arm64 archive wanting
`libgmp.so.10`, which the flake now supplies. Rows `SR-1515` to `SR-1517` hold
what outlives the item.

### R23.50 — A static Linux archive

Status: complete
Depends on: R23.10, R23.30, R23.40

The release workflow publishes a Linux `refine` linked statically against
glibc with `-static-pie`, for x86-64 and arm64, as R23.40 found it builds
with the pinned toolchain and no source change
(`roadmap/inputs/static-linux-refine.md`); a musl build is not attempted,
since no published GNAT targets musl. The static archive takes the glibc
archives' names and the dynamic one is published beside it, as Q-118
answered, reopening Q-116.
The install script takes it on a musl or NixOS host, and the user image
takes it where it makes the image simpler. The archive carries glibc's
licence and names the glibc it holds, and the build is refused when a
static link prints glibc's warning that a call needs that glibc's shared
libraries at run time.

Exit evidence: a gate job that runs the packaged static compiler on
Alpine and in an image with no C library of its own beyond the linker it
needs, compiling and running the first program and the `--link=libc`
runtime fixtures against musl, or a row for each that does not run there;
the release test program passed by the static build on both
architectures; the install script choosing it on Alpine in its control;
the archive in the installing documentation; the release recipe's step for
it in `docs/process.md`.

Done: a Linux release build links `refine`, its split commands and the
test program with `-static-pie` (D1787): `scripts/env.sh` chooses the
link and `landin_common.gpr` applies it, so every release lane tests what
a release publishes. A release publishes it under the platform's name and
the dynamic archive beside it as `-dynamic`, built again in the release
workflow alone, and `install.sh --variant static|dynamic` chooses, static
by default (D1791, Q-118, which reopened Q-116). A static link that warns
is refused, and
`scripts/package.sh` packages one with `LICENSE-GLIBC` and `NOTICE-GLIBC`
from the host's `libc6-dev` (D1788); whether naming Ubuntu's source
package meets the LGPL is asked as Q-117. `install.sh` no longer refuses
a host by its loader but an archive whose `refine` does not start there
(D1789). `scripts/static_check.py`, in `release` and
`arm64-release-checks` and in the release workflow before approval, runs
the packaged compiler alone in an empty root and, on Alpine 3.24.4,
installs it with `install.sh`, runs the first program and links all 19
`link: libc` runtime fixtures against musl, 31 checks passing on both
architectures (D1790); `arm64-release` passed the whole release test
program with the static build natively, 1279 cases. The user image keeps
Debian's `gcc`, which it needs to link, and takes the static archive
unchanged. The README records the musl and jemalloc build the spike
tested, which the project neither builds nor publishes, and what making
one needs; the host-target refusal it met, `SR-1518`, R21.10 fixed. Met on the way
and fixed: glibc's static start kills an
executable naming a run path, which the gate's release lanes built
without `-R`, so `build.sh` adds it; the reuse check then refused the
`-R`; the dynamic archives' undocumented floor of glibc 2.38, from one
symbol, now in the README; `SR-1517`, `package.sh` refusing another
architecture's executable first; and `SR-1515`, the static build being
the release mode `test.sh` runs; and `package.sh` writing gzip under any
suffix, now refused. Gate run 44944750687 and boards run 44947292024 on
65efe1ccb, and release rehearsal 44944776550, which built and checked both
archives of each Linux architecture.

### R23 gate
Every route in the installing documentation and exercised by the gate or,
where only a release can, by the release workflow; the release recipe
written in `docs/process.md` with each route's step.

Claimed after R23.50, on main `42fb0001f`, as Q-142 answered: every
item's completing commit passed its gate and boards dispatch. The full
[pass](https://github.com/701-dev/Landin/actions/runs/44944750687) on
`65efe1ccb`, which main's gate reused, exercised five of the README's six
routes: the install script through `install_check.py` in `release`,
`arm64-release` and both `darwin-host-release` shards; the release archive
as the packaged compiler, with `static_check.py` in `release` and
`arm64-release-checks`; the user image in `outside-user-stock` and
`arm64-release`; nix through `nix_route.py` in `flake-compiler`; and the
source build in every lane. The release workflow checks both archives of
each Linux architecture and both images before its approval, shown by
rehearsal 44944776550. Homebrew, which only a release can exercise, is
checked by hand in step 8 of the release recipe, which `docs/process.md`
writes down with each route's step.

## Successor families

The first roadmap named six families as destinations for what it did not do,
and the second added Usability. They are kept as the owners of register records, not as roadmaps of their
own; a record that an item here takes on says so, and one that none does
waits for its activation.

- **Scale and self-hosting:** separate compilation and interface files,
  caching, cross-language stage transport and the incremental replacement of
  tested Ada stages.
- **Companion tool and ecosystem:** a build tool, package acquisition, version
  solving, manifests, locks, publishing, naming authority and generator
  orchestration. A build description between Zig's build program and a
  makefile was discussed when this roadmap was written and left out of it.
- **Broader standard library:** library facilities beyond what the prototypes
  needed.
- **Competitive optimization:** optimization beyond correct deterministic
  baseline code.
- **Language evolution:** parked constructs, watches and proposals whose
  triggers have not fired.
- **Release readiness:** distribution beyond R23's routes, production
  claims and every release or version decision.
- **Usability:** what a person meets using Landin from its documentation
  alone: knowledge a newcomer cannot guess, workarounds, refusals that do
  not say what to do, and documentation that disagrees with the tool.
  `AGENTS.md` makes recording it everyone's job.

## The concurrency execution model

Carried from the first roadmap, because a settled position written nowhere
reads as an open question and gets reopened.

Concurrency is not a property of a function. It is a capability — an Io the
caller hands down, an ordinary parameter like an allocator, commonly minted at
the entry point [1660]. Code using only that Io blocks or does not according to
the provider it was given. The argument list does not prevent a routine from
minting a separate host root [1680]. No keyword, second calling convention or
colored function type is used to say it. The refusal this replaces is recorded
in `tour.md` under WHAT WAS TRIED AND DROPPED.

- **Two Io providers share one interface.** `hosted/blocking` blocks the
  thread while it waits and `hosted/events` lets other fibres run; the
  caller chooses which one to hand down, and `core` code written against
  the interface runs over either.
- **Stackless coroutines are a non-goal.** Cutting functions into state
  machines is a compiler project of its own, and it puts the property into
  every function type that reaches one — the coloring the ambient environment
  was removed to avoid. This is a refusal, not a park: no trigger reopens it,
  only a decision to reverse it.
- **Stackful fibres are the route, and the backends keep them reachable on
  purpose.** A backend decision that forecloses switching stacks is a defect
  in that backend rather than a trade-off. The conditions are held for other
  reasons already: call-bearing frames retain a frame pointer, the callee-saved
  discipline is explicit, and no capability rides in a reserved register.
  Call-free Cortex-M leaves may omit the pointer because they cannot switch
  stacks. The case to design against is a single-core freestanding target, where the
  honest answer to a request for concurrency is that there is none.

## Retained positions

Six positions an outside review challenged and the project kept. Reopen one
only with new evidence that answers its rationale, and record the reopening.
They are numbered RP1 to RP6, apart from `spec.md`'s decisions D1 onward,
and are cited by those numbers here and in `spec.md`.

| Position | What was kept, and why |
| --- | --- |
| RP1 | Integer indexing of UTF-8 text by codepoint ordinal, linear, for ergonomics [0610]; reopen only with program or measurement evidence. |
| RP2 | No weak conformances and no orphan rule: a collision is an error, answered with `distinct` or an explicit function [1280], because a weak conformance lets an application silently change a generic library's behaviour; reopen on ecosystem-scale evidence. |
| RP3 | No compile-time execution and no macros; generated source comes from programs the build runs [1540]. Reviewed when the third kind of generated source appeared, and held for now: SVD modules, C bindings and `platform/linux/numbers` are each generated by a program run outside compilation, `refine svd`, `refine bindings` and `scripts/linux_syscalls.py`; none needed compile-time execution or a macro, and each generated file is checked in and held current by a check. The build-tool suggestion in [the roadmap discussion](https://github.com/701-dev/Landin/discussions/2#discussioncomment-19264955) may bring a generalized source-generator stage, which would be reviewed against this position. |
| RP4 | `escaping` and `from` are written, not inferred, to keep checking local and because an allocator is a counterexample to inferred `from` [0790] [0900]. |
| RP5 | Landin's own backends emitting assembly; not LLVM, a dependency larger than the language, and not C, which loses the calling convention, the traps and the debug information [1550]. |
| RP6 | One version of a package name per program: 32 KB of flash, nominal types and one conformance register [1470]. |
