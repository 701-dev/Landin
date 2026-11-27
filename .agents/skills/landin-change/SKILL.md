---
name: landin-change
description: Carry a Landin roadmap item, or any other repository change, from its start to main - worktree, brief, reserved identities, checks, gate, boards, promotion, clean-up and the report - and dispatch items to agents. Use for compiler, fixture, tooling, process and roadmap work; exclude read-only language questions and release/version changes.
---

# Carry a Landin item or change to main

Read the checkout's [AGENTS.md](../../../AGENTS.md), then the item's text in
`ROADMAP.md` (its heading, the Mechanics section and the rows and questions
it names; never the file whole) and the authorities it touches. The
[development loop](../../../docs/process.md#the-loop-that-runs-now) owns the
commands and gate conditions; this skill puts them in order.
`scripts/item.py` does every step that needs no judgement, and keeps the
item's state on disk, so a reopened session loses nothing: `python3
scripts/item.py --help` lists the steps.

## After any reopen, first

A restart, a resume or a change of account ends the session's background
commands. Run `python3 scripts/item.py resume ITEM` (or without ITEM from
the item's worktree) before anything else: it prints the worktree's state,
every recorded run as running, finished or lost, the gate runs, the
journal's last lines and the next step. A detached run survives a reopen;
wait on it again rather than starting it anew. Write a decision or a
finding into the journal as you make it, `item.py note ITEM TEXT`, so that
what a successor needs is never only in the conversation.

## An item, start to finish

1. **Start.** `python3 scripts/item.py start ITEM`, run from the clone's
   main checkout, fetches, refuses a complete item or one whose
   dependencies are not complete, makes the worktree `../Landin-ITEM` and
   its branch from `origin/main`, reserves decision, row and question
   numbers no other running item of the clone holds, marks the item
   active, moves the pointer if it names the item, commits that
   (`Gate: explanatory`) and writes the brief. `--adopt WORKTREE` takes on
   one made by hand. The brief says what runs beside the item; an item
   beside another coordinates shared ground (register rows, item text, the
   controls that read the live roadmap) with that item's owner.
2. **Work** only in the worktree. Choose exact `dev-test.sh` selectors in one
   invocation; run anything longer than a few minutes as `item.py run ITEM
   NAME --limit SECONDS -- COMMAND`, which is `run_logged.py --detach` kept
   in the state, and wait with the `run_logged.py --wait DIR` it prints, or
   by the harness's notification. Script controls: `python3
   scripts/script_tests.py NAME ...` runs named modules and shards
   `check.py`'s controls; whole `test_check_controls` under plain unittest
   takes over ten minutes. A new script that names `ROADMAP.md`,
   `README.md` or `roadmap/` needs an entry in `scripts/tests/
   test_gate_inputs.py`'s `READERS`, or the scripts job fails.
3. **Close** by [the checklist](../../../docs/process.md#closing-an-item):
   activations against the item's base, the passes it lists, the `Done:`
   paragraph naming the findings fixed, rows deleted or filed, the
   register's cap and age rule, the pointer, the full `python3 check.py`.
4. **Commit it complete and report.** The complete gate belongs to a
   batch, not to an item: an item does not push or gate alone, and
   `item.py push` and `promote` refuse it. Commit it complete on its
   branch, its closing commit included, and report the branch and head.
   The session that runs the roadmap adds it to
   [a batch](../../../docs/process.md#a-batch), `item.py batch add BATCH
   ITEM`; leave the branch alone from then on. A failed job the batch's
   gate routes to the item (`item.py batch route`, written into its
   journal) is fixed on the batch's branch, in the batch's worktree; an
   item that cannot be fixed there is dropped and joins a later batch.
   A change to the toolchain, CI or the rig gates alone, as a batch of
   one, by steps 5 to 8 itself.
5. **Push and boards**, the batch's integrator, or an item that gates
   alone: `item.py push NAME --boards --watch` refuses a stale
   `citations.txt`, runs the pre-push checks the changed paths select
   (`--no-check` when a failure is not the change's), pushes, records the
   head's runs, follows the gate in two detached watches and dispatches
   the boards beside it once main is the head's ancestor. Wait on the
   first watch: it returns at the first failed job, so read that job's
   log and route it at once; push the fixes when the `--all` watch ends.
   `item.py boards NAME --watch` follows a boards run already on the head
   rather than dispatching another. A run that failed only in timing,
   every board leg passed, is not a boards failure: `item.py boards NAME
   --rerun-failed --watch` re-runs only the failed jobs. After the gate
   and the boards pass, one commit declared `Gate: explanatory` names
   them in every member's `Done:` paragraph; it reuses the gate.
6. **Promote** with `item.py promote NAME` (`--dry-run` first if unsure).
   It refuses unless the head is the pushed head, main is its ancestor, a
   push gate on the head passed with every job passed or skipped, a
   boards run passed on the same tree or before only explanatory commits,
   and every member is complete in the candidate. If main moved,
   `item.py merge-main NAME`, once: it takes the clone's promotion token,
   merges `origin/main`, and declares the merge `Gate: explanatory` when
   everything main brings is declared and the gate key is unchanged, so
   the pass and the boards are reused; otherwise push the merged tree with
   its boards beside its gate. If another holds the token, wait with
   `item.py queue --wait NAME` rather than merging twice. Promotion takes
   the token too, and main's gate verdict or `finish` gives it up. A
   batch with a member that says `Promotion: maintainer` stops at the
   passed candidate: report it, and the maintainer promotes it.
7. **Follow main**: `item.py gate NAME --main --watch`, to its verdict,
   the aggregate `gate` job; the cache jobs after it are no evidence.
   Main's push takes the boards of the candidate's passed dispatch, so its
   gate is short. A failure there is investigated, never rerun blindly.
8. **Finish**: `item.py finish NAME` for the batch and for each member,
   from anywhere in the clone, refuses until main's gate passed, then
   removes the worktree, the local and remote branch, and moves the state
   to `landin-items/done/`, where it stays. The session's shell is then
   in a removed directory; `cd` to the clone's main checkout.
9. **Report** in [the report form](report.md); `item.py report ITEM`
   drafts it from the state, with the open questions the item asked last.

**In a breaking window**, a phase whose opening says `Window: BRANCH`,
the same commands land the item on that integration branch in place of
main ([process](../../../docs/process.md#a-breaking-window)): `start`
branches from it, a batch formed with `--target BRANCH` takes it,
`promote` pushes the batch to it once the push gate on the head passed,
without step 5's boards, and `finish` follows at once. The window reaches main once, at its phase's gate, by
the ordinary steps.

A push the mirror refuses while GitHub takes it is no failed push:
`push` and `promote` say so and print the command that brings the mirror
up to date. Work that is no item takes a token with `item.py queue
--take NAME --why TEXT`, decision numbers with `register_next.py
--decision`, and asks a question with `--asked-by` saying what it is.

A decision only the maintainer can take is a question file, never only a
line in a report: `python3 scripts/register_next.py --question --file
--asked-by ITEM`. Carry on with its default and with all the work its
answer cannot change. A finding the item fixes is named in its commit and
`Done:` paragraph; only one that outlives the item becomes a row under
`roadmap/register/`, and a usability finding met on the way is one too, as
AGENTS.md's "Friction is a finding" says.

The item's agent commits its item complete and cleans up its own
worktrees and branches; a batch's integrator pushes, gates and promotes
the batch unless a member says `Promotion: maintainer` (`ROADMAP.md`'s
Mechanics), and an item that gates alone does so itself; other work
promotes only when that action is authorized. Releases and versions are never covered.

## Dispatching items to agents

A session that runs the roadmap rather than an item keeps no state of its
own beyond what `item.py` keeps:

- `item.py start ITEM` makes the item's worktree and brief; the brief is
  the agent's whole first message. Create the agent in that worktree, one
  item each, with the host's own rules for model and account.
- `item.py status` lists the running items; `item.py stalled` names any
  that nothing has moved for an hour, with its next step, and exits 1. An
  idle agent is not proof that its runs ended: the state says.
- Act on reports, not raw material: the report's runs and commits are what
  to check (`gh run view RUN`, `git log -1 COMMIT`).
- Form batches from the items reported complete: `item.py batch form
  NAME --integrator WHO`, `item.py batch add NAME ITEM ...` (it says
  which it left out and why), `item.py push NAME --boards --watch`, the
  explanatory `Done:` commit, `item.py promote NAME`, `item.py gate NAME
  --main --watch`, then `finish` for the batch and each member. Tell each
  member's agent it is in the batch and must leave its branch alone. On a
  failed gate, read the first failed job, `item.py batch route NAME --run
  RUN`, send the member its job, and `item.py batch drop` one that cannot
  be fixed there, as [a batch](../../../docs/process.md#a-batch) says.
- A successor to such a session needs only `item.py status` and the open
  questions, which `roadmap/register.md` lists with their defaults.

## Improving this skill

Fix the skill and `item.py` from a review held between items, never
while an item runs on them: a running item keeps the steps it started
with. Record what an item met in its report's FRICTION, and as a register
row when it outlives the item.

## Other changes

A change that is no roadmap item follows the same order without `item.py`:
its own worktree and branch from an explicit base, the exact checks, the
push, the gate, and promotion only when authorized. For parallel streams
within one item use the
[ownership and integration recipe](../../../docs/process.md#parallel-sessions-and-shared-resources):
each writer its own worktree, branch and identity range, a named
integrator. Hardware work needs its authorized operator and the rig's
common lock. A review request returns findings without assuming
permission to implement or publish.
