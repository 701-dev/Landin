#!/usr/bin/env python3
"""Run a roadmap item from start to finish: every step that needs no agent.

    python3 scripts/item.py start ITEM          # worktree, branch, brief, identities
    python3 scripts/item.py resume [ITEM]       # where a reopened session stands
    python3 scripts/item.py note ITEM TEXT      # one line in the item's journal
    python3 scripts/item.py run ITEM NAME --limit S [--cwd DIR] -- COMMAND ...
    python3 scripts/item.py push ITEM [--watch] [--boards] [--no-check]
                                                # pre-push checks, push, gate
    python3 scripts/item.py gate ITEM [--watch] # the gate runs of the branch head
    python3 scripts/item.py boards ITEM [--watch] [--rerun-failed] [--again]
                                                # dispatch scope=boards
    python3 scripts/item.py merge-main ITEM     # merge main; a batch takes the queue
    python3 scripts/item.py batch form NAME --integrator WHO [--target BRANCH]
    python3 scripts/item.py batch add|drop NAME MEMBER ...
    python3 scripts/item.py batch route NAME [--run RUN] [JOB ...]
    python3 scripts/item.py batch list [NAME]
    python3 scripts/item.py queue [--wait ITEM | --release ITEM]
    python3 scripts/item.py promote ITEM        # check the evidence, push to main
    python3 scripts/item.py finish ITEM         # remove worktree and branches
    python3 scripts/item.py status              # every item this clone runs
    python3 scripts/item.py stalled             # active items nothing moves
    python3 scripts/item.py report ITEM         # the report, with what is known

An item's state lives on disk, not in a session: a directory per item under
the clone's common Git directory, `landin-items/ITEM/`, which every worktree
of the clone shares and no worktree removal deletes.  It holds `state.json`
(branch, worktree, base, reserved identities, runs and gate runs),
`journal.md` (one dated line per `note`), `brief.md` (what `start` wrote for
the agent) and `runs/`, the retained directories of the item's detached
`scripts/run_logged.py` runs.  A session that is reopened, by a restart, a
resume or a change of account, runs `resume` and continues from what it
prints; nothing it needs is only in the conversation.

`start` reads the item from ROADMAP.md at the base, refuses one that is
complete or whose dependencies are not, makes the worktree and branch from
the base, reserves identities no other running item of this clone holds
(decisions, register rows and questions, each a block of numbers that
`scripts/register_next.py` then gives out first), marks the item active,
moves the README.md and handoff.md pointer from the next form to the
current one when it names the item, commits that, and writes the brief.

The complete gate belongs to a batch, not to an item.  An item is
checked locally with the exact selectors for what it touches and committed
complete on its branch, its closing commit included; it does not push or
gate alone, and `push` and `promote` refuse it.  `batch form NAME` makes a
batch, work that is no item with its own worktree and branch from its
target, `main` or a phase's window branch, naming its integrator; `batch
add` merges members' local branches after the target, in order, items of
this clone or branches that are no item's, none of them gated first; `batch
drop` rebuilds it without one; `batch route` names the member a failed job
belongs to, the one whose change reaches the job's lane's inputs in
`.github/gate-lanes.json`, the last joined when none does.  The batch is
pushed, gated, given its boards and promoted as one, and `promote` writes
every member item as promoted with the batch's runs, marked `via`.  A
change to the toolchain (`environments/pins.sh`, `flake.nix`, `flake.lock`),
to CI (`.github/`) or to the rig (`environments/boards/`, the board
harness) still gates alone, as a batch of one: `batch add` refuses it
beside other members, and the item may push and promote on its own gate.
So may a change every commit of which says `Gate: explanatory`.  A batch
with a `Promotion: maintainer` member is the maintainer's to promote.

`promote` pushes the head to its target only when the head is the branch's
pushed head, the target is its ancestor, a push gate on the head passed
with every job of its listing passed or skipped, and a boards dispatch
passed on the same tree, or on an earlier commit from which every later
commit says `Gate: explanatory`.  It does not follow main's gate: `gate
--main --watch` does, and `finish` refuses until main's gate on the
promoted commit passed.

Promotions queue, so that a batch merges main once rather than once for
every batch that lands before it.  The clone holds one promotion token,
`landin-items/queue.json`.  `merge-main` takes it before the item's final
merge and `promote` takes it before pushing; the holder keeps it until
main's gate on its promoted commit has its verdict, which `gate --main` and
`finish` see, or until `queue --release` gives it up.  An item that finds
it held is put in line and told the wait command; `queue --wait ITEM`
returns once the token is the item's, taking it.  A holder whose state is
gone, or whose main gate has its verdict, holds nothing.  An item that
does not gate alone never waits for the token: its `merge-main` only picks
up the target, and its batch takes the token.

`merge-main` merges `origin/main`.  When every commit it brings says
`Gate: explanatory` and the merged tree has the candidate's gate key
(`scripts/gate_inputs.py key`), the merge says `Gate: explanatory` too, and
the gate reuses the candidate's pass and the boards dispatch still counts,
as the reuse rule already allows; otherwise it says which commits or paths
make the merged tree new.  `boards` refuses to dispatch on a head main is
not an ancestor of, since promotion would refuse that tree; `--unmerged`
dispatches anyway, for board feedback before the final merge.  A head
whose boards run is queued, running or passed is not dispatched again: the
run is followed, or named, unless `--again`.  After a
boards run whose board legs passed and whose only failures were timing
jobs, `boards --rerun-failed` re-runs only the failed jobs of that run.
`push` refuses a stale `citations.txt` before pushing, then runs the cheap
checks the changed paths select (the formatting case, the lowering suite,
the debugger workloads' closures, the library's comments, the whole
`check.py` after a merge), refusing on the first that fails unless
`--no-check`; `--boards` dispatches the boards beside the gate.

A member of a batch refuses to push, merge, wait for the token or promote
until the batch lands, and its `finish` then follows main's gate as any
promoted item's does.

The token goes to a batch, or an item that gates alone, only once its head
has a passed push gate: until then `merge-main` and `queue --wait` keep its
place in line and the token passes over it to the first ready.

A phase that declares a breaking window, a line `Window: BRANCH` in its
opening paragraphs, keeps its serial items on that integration branch
until its gate, and the script lands them there in place of main: `start`
branches from it (from main while it has not been made), `merge-main`
merges it, a batch formed with `--target BRANCH` takes them, and `promote`
pushes its head to it once the push gate on the head passed, without boards, which the window's one promotion to main runs on
the integrated tree, and gives its token up at once, and `finish` follows
the landing rather than main's gate.  Each window has its own token,
`landin-items/queue-BRANCH.json`.  An item started before the script knew
windows reads its phase's line from its worktree's ROADMAP.md.  `finish`
also takes an item whose head reached its landing branch or main by hand.

`push` and `promote` push to GitHub, origin's fetch URL, and judge the
step by it alone; a mirror among origin's push URLs that refuses is
reported with the command that brings it up to date, and the step stands.
`queue --take NAME` holds a token for work that is no item, until `queue
--release NAME`.  `merge-main` says when the branch it merges took a
number of the item's reserved blocks.

Releases and versions are never this script's.
"""
import argparse
import contextlib
import datetime
import fcntl
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
#  The clone the item runs in; --repo names another, as the tests do.
REPOSITORY = [ROOT]
STATE_DIRECTORY = "landin-items"
DONE_DIRECTORY = "done"
#  How many of each identity an item reserves when it starts.
BLOCKS = {"D": 20, "SR": 10, "Q": 5}
DECISION = re.compile(r"\bD(\d{2,})\b")
ITEM = re.compile(r"R(\d+)\.(\d+)")
PHASE_OR_ITEM = re.compile(r"R\d+(?:\.[1-9]\d*)?")
CURRENT = "**Current roadmap work: %s — %s.**"
NEXT = "**Next roadmap item: %s — %s (planned).**"
POINTER_FILES = ("README.md", "handoff.md")
EXPLANATORY = "Gate: explanatory"
#  check.py's flag that regenerates every generated file.
GENERATE_ALL = "--generate"
#  The aggregate job whose conclusion is a gate run's verdict.
VERDICT_JOB = "gate"
QUEUE = "queue.json"
#  The rules a queue file is written under.  Every `item.py` of the clone's
#  worktrees writes the one file, each its own branch's copy, so a copy
#  refuses to rewrite a file a newer copy wrote; raise it whenever a change
#  to `settle` or the file's keys would make an older copy drop or misread
#  what a newer one keeps, as an older copy once dropped the waiters
#  that are no item.  A file without the key is the rules of 1.
QUEUE_SCHEMA = 2
#  Every change of a queue's holder or line, one JSON object a line, beside
#  the queue's own file: queue.json keeps only the present, and the
#  holds of work that is no item were otherwise lost.
HISTORY = "-history.jsonl"
MAIN = "main"
#  A phase's breaking window: a line of its opening paragraphs, before its
#  first item, naming the integration branch its serial items land on.
WINDOW = re.compile(r"^Window: (\S+)$")
#  Seconds between looks while `queue --wait` waits, and between asking
#  GitHub whether the holder's main gate has its verdict.
QUEUE_POLL = 15
QUEUE_ASK = 60
#  Work that is no item waits in line only while it keeps asking: one whose
#  `queue --wait` has not asked for this long has left the line.
SESSION_LINE = 900
#  An item nothing has moved for this long is reported as stalled.
STALL_MINUTES = 60
PHASES = ("started", "pushed", "gate-passed", "boards-passed", "promoted",
          "main-passed", "finished")


class Refused(Exception):
    """A step that must not be taken, with what to do instead."""


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def stamp():
    return now().isoformat().replace("+00:00", "Z")


def repository(cwd=None):
    return cwd if cwd is not None else REPOSITORY[0]


#  What git says when another worktree of the clone holds a ref's lock:
#  the worktrees share their refs, so one's fetch can find another's lock.
REF_LOCK_RACE = re.compile(r"cannot lock ref|Unable to create '[^']*\.lock'"
                           r"|unable to update local ref")
#  Times a fetch that met another's ref lock is asked again.
REF_LOCK_TRIES = 5


def git(*arguments, cwd=None, check=True):
    for attempt in range(1, REF_LOCK_TRIES + 1):
        result = subprocess.run(["git", *arguments], cwd=repository(cwd),
                                text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        #  A fetch is safe to ask again; `push --boards` once ended on such
        #  a race in the fetch after its push, before it dispatched.
        if result.returncode == 0 or arguments[:1] != ("fetch",) or \
                not REF_LOCK_RACE.search(result.stderr) or \
                attempt == REF_LOCK_TRIES:
            break
        time.sleep(attempt)
    if check and result.returncode != 0:
        raise Refused("git %s failed: %s" % (" ".join(arguments),
                                             result.stderr.strip()))
    return result.stdout.strip() if result.returncode == 0 else None


def gh(*arguments):
    result = subprocess.run(["gh", *arguments], cwd=repository(), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise Refused("gh %s failed: %s" % (" ".join(arguments),
                                            result.stderr.strip()))
    return json.loads(result.stdout) if result.stdout.strip() else None


def main_checkout(cwd=None):
    """The clone's main worktree, which outlives every item's."""
    listing = git("worktree", "list", "--porcelain", cwd=cwd)
    return Path(listing.splitlines()[0].split(" ", 1)[1])


def place(state):
    """Where to ask Git about STATE's item: its worktree while it exists,
    the clone's main checkout once it is gone."""
    worktree = Path(state["worktree"])
    return worktree if worktree.is_dir() else main_checkout()


#  A roadmap item's identity, and the name of work that is no item.
ITEM_NAME = re.compile(r"R\d+\.\d+")
WORK_NAME = re.compile(r"[a-z][a-z0-9-]*")


def slug(item):
    return item.lower().replace(".", "-")


# ---------------------------------------------------------------- the roadmap

def roadmap_items(text):
    """Every item: its title, status, dependencies, promotion line and the
    line its heading is on."""
    items, order = {}, []
    lines = text.splitlines()
    for n, line in enumerate(lines):
        found = re.match(r"^### (R\d+\.\d+) — (\S.*)$", line)
        if not found:
            continue
        identity = found.group(1)
        entry = {"title": found.group(2), "line": n + 1, "status": None,
                 "depends": [], "maintainer": False}
        if found.group(2).endswith(" (retired)"):
            entry["status"] = "retired"
        for following in lines[n + 1:]:
            if following.startswith("#"):
                break
            if following.startswith("Status: "):
                entry["status"] = following.split(": ", 1)[1].strip()
            elif following.startswith("Depends on: "):
                value = following.split(": ", 1)[1].strip()
                entry["depends"] = ([] if value == "none"
                                    else PHASE_OR_ITEM.findall(value))
            elif following.strip() == "Promotion: maintainer":
                entry["maintainer"] = True
        items[identity] = entry
        order.append(identity)
    return items, order


def unmet(items, item):
    """The dependencies of ITEM that are not complete."""
    missing = []
    for needed in items[item]["depends"]:
        if "." in needed:
            if items.get(needed, {}).get("status") != "complete":
                missing.append(needed)
        else:
            missing.extend(other for other, entry in items.items()
                           if other.split(".")[0] == needed
                           and entry["status"] != "complete")
    return missing


def roadmap_at(revision, cwd=None):
    return git("show", "%s:ROADMAP.md" % revision, cwd=cwd)


def roadmap_windows(text):
    """{phase: integration branch} of every phase that declares a breaking
    window with a `Window:` line before its first item."""
    windows, phase = {}, None
    for line in text.splitlines():
        heading = re.match(r"^## (R\d+) — ", line)
        if heading:
            phase = heading.group(1)
        elif line.startswith("#"):
            phase = None
        elif phase:
            found = WINDOW.match(line)
            if found:
                windows[phase] = found.group(1)
    return windows


def window_of(item, cwd=None, revisions=()):
    """The integration branch ITEM's phase lands on while its breaking
    window is open, or None.  Read from ROADMAP.md at each of REVISIONS,
    then at origin/main, then at the phase's conventional branch
    `origin/rNN-integration`, where the window's first commit can declare
    it before main has the line."""
    phase = item.split(".")[0]
    for revision in (*revisions, "origin/" + MAIN,
                     "origin/%s-integration" % phase.lower()):
        text = git("show", "%s:ROADMAP.md" % revision, cwd=cwd, check=False)
        if text:
            branch = roadmap_windows(text).get(phase)
            if branch:
                return branch
    return None


def target_of(state):
    """The branch STATE's item lands on: main, or its phase's integration
    branch while the phase's breaking window is open.  A state written
    before item.py knew windows has no `target`; its worktree's ROADMAP.md
    says."""
    if "target" not in state:
        where = place(state)
        state["target"] = window_of(
            state["item"], where,
            ("HEAD",) if Path(state["worktree"]).is_dir() else ()) or MAIN
    return state["target"]


def landing_base(target, cwd=None):
    """What a target branch is on GitHub now: origin/TARGET, or origin/main
    while a window's branch has not been made."""
    ref = "origin/" + target
    if target != MAIN and git("rev-parse", "-q", "--verify", ref, cwd=cwd,
                              check=False) is None:
        return "origin/" + MAIN
    return ref


# -------------------------------------------------------------------- state

def common_directory(cwd=None):
    path = Path(git("rev-parse", "--git-common-dir", cwd=cwd))
    return path if path.is_absolute() else (Path(repository(cwd)) / path).resolve()


def state_root(cwd=None):
    return common_directory(cwd) / STATE_DIRECTORY


def item_directory(item, cwd=None):
    return state_root(cwd) / item


def load(item, cwd=None):
    path = item_directory(item, cwd) / "state.json"
    if not path.exists():
        done = state_root(cwd) / DONE_DIRECTORY / item / "state.json"
        if done.exists():
            raise Refused("%s is finished; its state is in %s"
                          % (item, done.parent))
        raise Refused("this clone runs no item %s: `item.py start %s` starts"
                      " it, `item.py status` lists those it runs"
                      % (item, item))
    return json.loads(path.read_text(encoding="utf-8"))


def save(state, cwd=None):
    directory = item_directory(state["item"], cwd)
    directory.mkdir(parents=True, exist_ok=True)
    state["updated"] = stamp()
    temporary = directory / "state.json.tmp"
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, directory / "state.json")


def journal(item, text, cwd=None):
    directory = item_directory(item, cwd)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "journal.md").open("a", encoding="utf-8") as stream:
        stream.write("- %s %s\n" % (stamp(), " ".join(text.split())))


def running_states(cwd=None):
    root = state_root(cwd)
    if not root.is_dir():
        return []
    states = []
    for path in sorted(root.glob("*/state.json")):
        states.append(json.loads(path.read_text(encoding="utf-8")))
    return states


def reserved(cwd=None, exclude=None):
    """The identity blocks running items hold: {kind: [(low, high, item)]}."""
    blocks = {kind: [] for kind in BLOCKS}
    for state in running_states(cwd):
        if state["item"] == exclude:
            continue
        for kind, (low, high) in state.get("reserved", {}).items():
            blocks.setdefault(kind, []).append((low, high, state["item"]))
    return blocks


def item_of_branch(cwd):
    """The running item whose branch CWD has checked out, or None."""
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd, check=False)
    for state in running_states(cwd):
        if state["branch"] == branch:
            return state["item"]
    return None


def next_free(used, blocks, size):
    """The low end of SIZE free numbers past USED and every block."""
    start = max(used | {0}) + 1
    for low, high, _ in sorted(blocks):
        if high >= start:
            start = max(start, high + 1)
    return start, start + size - 1


def decisions_used(revision, cwd):
    spec = git("show", "%s:spec.md" % revision, cwd=cwd, check=False) or ""
    return {int(n) for n in DECISION.findall(spec)}


def reserve(item, revision, cwd):
    sys.path.insert(0, str(ROOT / "scripts"))
    import register_next
    others = reserved(cwd, exclude=item)
    used = {"D": decisions_used(revision, cwd)
                 | register_next.decisions_taken(str(repository(cwd))),
            "SR": register_next.taken(str(repository(cwd))),
            "Q": register_next.taken(str(repository(cwd)), question=True)}
    return {kind: list(next_free(used[kind], others.get(kind, []), size))
            for kind, size in BLOCKS.items()}


# -------------------------------------------------------------------- start

BRIEF = """\
# {item} — {title}

You carry out roadmap item {item} of Landin. Its text is in ROADMAP.md
under "### {item}" (line {line} at the base); read it, the Mechanics
section and the rows and questions it names, not the file whole. Follow
AGENTS.md, docs/process.md's current loop and its closing checklist, and
the skill landin-change, which takes the item through this script's steps.

Where things are:
- Worktree {worktree}, branch {branch}, made from {base}. Work only there;
  the clone's other checkouts are not yours.
- State on disk: {state}. After any reopen, or when unsure, run
  `python3 scripts/item.py resume {item}` first and continue from it.
- Reserved identities, no other running item of this clone holds them:
  decisions D{D[0]}-D{D[1]}, register rows SR-{SR[0]}-{SR[1]} and questions
  Q-{Q[0]}-{Q[1]}. `scripts/register_next.py` gives these out first.

Running beside it:
{beside}

How to work: exact `dev-test.sh` selectors for what the item changes, all
in one invocation, leaving the complete suite to the gate; the build's
worker count and CPU placement at their defaults, no `-j` or `taskset`;
the pinned environment by `. "$(./scripts/agent_env.sh)"` or `nix develop`;
a long run through `item.py run`, waited on by the harness's completion
notification, `run_logged.py --wait DIR` where there is none
(docs/process.md, "Local agent feedback"). A brief you write for a
subagent or a stream carries these rules itself.

What you may do without asking: {authority} Releases and versions never.
A decision only the maintainer can take is a question file
(`python3 scripts/register_next.py --question --file --asked-by {item}`);
carry on with its default and with everything its answer cannot change.

Your reply: exactly one message in the form of
.agents/skills/landin-change/report.md (`python3 scripts/item.py report
{item}` drafts it), sent when everything you started has finished.
"""

AUTHORITY = (
    "check the candidate with the exact selectors for what it touches and"
    " commit it complete on its branch, its closing commit included. It"
    " does not push or gate alone: the complete gate belongs to a batch,"
    " which merges it with others onto {target} (`item.py batch`), and one"
    " gate and boards on the batch's merged tree are its evidence. A change"
    " to the toolchain, CI or the rig gates alone, as a batch of one: then"
    " push it, promote it once its gate and boards pass (`item.py"
    " promote`), and remove its worktree and branches (`item.py finish`),"
    " as ROADMAP.md's Authority paragraph says.")
MAINTAINER = (
    "check the candidate with the exact selectors for what it touches and"
    " commit it complete on its branch, its closing commit included. It"
    " does not push or gate alone: the complete gate belongs to a batch"
    " (`item.py batch`). The item says `Promotion: maintainer`: a batch"
    " holding it is the maintainer's to promote; report the committed"
    " candidate and stop there.")


def beside_text(item, items, cwd):
    lines = []
    for state in running_states(cwd):
        if state["item"] != item:
            lines.append("- %s on branch %s in %s (state %s)"
                         % (state["item"], state["branch"], state["worktree"],
                            state.get("phase")))
    for other, entry in items.items():
        if other != item and entry["status"] == "active" and not any(
                other in line for line in lines):
            lines.append("- %s is active in ROADMAP.md, not run from this"
                         " clone" % other)
    return "\n".join(lines) or "- nothing"


def mark_active(worktree, item, entry):
    """Set ITEM's status active and move a pointer naming it as next."""
    changed = []
    roadmap = worktree / "ROADMAP.md"
    text = roadmap.read_text(encoding="utf-8")
    heading = "### %s — %s\n\nStatus: " % (item, entry["title"])
    if heading + "planned\n" in text:
        roadmap.write_text(text.replace(heading + "planned\n",
                                        heading + "active\n", 1),
                           encoding="utf-8")
        changed.append("ROADMAP.md")
    for name in POINTER_FILES:
        path = worktree / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        old = NEXT % (item, entry["title"])
        if old in text:
            path.write_text(text.replace(old, CURRENT % (item, entry["title"])),
                            encoding="utf-8")
            changed.append(name)
    return changed


def start(arguments):
    item = arguments.item
    cwd = REPOSITORY[0]
    if (item_directory(item, cwd) / "state.json").exists():
        raise Refused("%s is already running from this clone: `item.py resume"
                      " %s` says where" % (item, item))
    if arguments.work is not None and (
            WORK_NAME.fullmatch(item) is None or ITEM_NAME.fullmatch(item)):
        raise Refused("%r is no name for work that is no item: lower-case"
                      " letters, digits and hyphens, as nix-packages-4, and"
                      " never an item's identity" % item)
    if not arguments.no_fetch and not arguments.adopt:
        git("fetch", "-q", "origin", cwd=cwd)
    target = MAIN if arguments.work is not None else (
        window_of(item, cwd) or MAIN)
    landing = landing_base(target, cwd)
    if arguments.adopt:
        worktree = Path(arguments.adopt).resolve()
        branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=worktree)
        base = arguments.base or git("merge-base", "HEAD", landing,
                                     cwd=worktree)
    else:
        base = git("rev-parse", arguments.base or landing, cwd=cwd)
        branch = arguments.branch or slug(item)
        #  Beside the clone's main checkout, whichever of its worktrees
        #  runs this, so a checkout under /tmp does not put it there.
        worktree = Path(arguments.worktree or main_checkout(cwd).parent
                        / ("Landin-" + slug(item))).resolve()
    items, _ = roadmap_items(roadmap_at(base, cwd))
    if arguments.work is not None:
        #  Work that is no item: its own state, reservations, pushes,
        #  gates and boards, and no roadmap entry to read or mark.
        items = dict(items)
        items[item] = {"title": arguments.work, "line": 0, "status":
                       "planned", "depends": [], "maintainer": False}
    if item not in items and arguments.adopt and not arguments.base:
        #  A continuous item whose text the adopted branch adds itself
        #  starts from the branch's head, which has the text.
        head = git("rev-parse", "HEAD", cwd=worktree)
        at_head, _ = roadmap_items(roadmap_at(head, cwd))
        if item in at_head:
            base, items = head, at_head
    if item not in items:
        raise Refused(
            "ROADMAP.md at %s has no item %s: an item whose text a branch"
            " adds starts from the commit that adds it; commit the text in"
            " its worktree, then `item.py start %s --adopt WORKTREE`, which"
            " starts from the branch's head, or `--base COMMIT`"
            % (base[:12], item, item))
    entry = items[item]
    if entry["status"] == "complete":
        raise Refused("%s is complete at %s" % (item, base[:12]))
    if entry["status"] == "retired":
        raise Refused("%s is retired at %s; its heading's paragraph says why,"
                      " and its identity is not used again" % (item, base[:12]))
    if entry["status"] == "blocked":
        raise Refused("%s is blocked at %s; its Blocked because: line says"
                      " what it waits for" % (item, base[:12]))
    missing = unmet(items, item)
    if missing and not arguments.force:
        raise Refused("%s depends on %s, not complete at %s; --force starts"
                      " it regardless" % (item, ", ".join(missing), base[:12]))
    if not arguments.adopt:
        if worktree.exists():
            raise Refused("%s exists; name another with --worktree, or"
                          " --adopt it" % worktree)
        git("worktree", "add", "-q", "-b", branch, str(worktree), base,
            cwd=cwd)
    reservation = {} if getattr(arguments, "no_reserve", False) else \
        reserve(item, base, cwd)
    changed = [] if arguments.no_commit or arguments.work is not None \
        else mark_active(worktree, item, entry)
    if changed:
        git("add", *changed, cwd=worktree)
        git("commit", "-q", "-m", "Start %s\n\n%s, made active by"
            " scripts/item.py start.\n\n%s" % (item, entry["title"],
                                               EXPLANATORY), cwd=worktree)
    state = {"item": item, "title": entry["title"], "branch": branch,
             "worktree": str(worktree), "base": base, "started": stamp(),
             "phase": "started", "maintainer": entry["maintainer"],
             "target": target,
             "reserved": reservation, "runs": [], "gates": []}
    if arguments.work is not None:
        state["work"] = True
    save(state, cwd)
    if not reservation:
        #  A batch: no brief and no reservations of its own; its members
        #  bring theirs.
        journal(item, "started from %s in %s on %s" % (base[:12], worktree,
                                                       branch), cwd)
        print("started %s in %s on branch %s from %s" % (
            item, worktree, branch, base[:12]))
        return 0
    brief = BRIEF.format(
        item=item, title=entry["title"], line=entry["line"],
        worktree=worktree, branch=branch, base=base[:12],
        state=item_directory(item, cwd), D=reservation["D"],
        SR=reservation["SR"], Q=reservation["Q"],
        beside=beside_text(item, items, cwd),
        authority=MAINTAINER if entry["maintainer"] else
        AUTHORITY.format(target=target))
    if arguments.work is not None:
        brief = re.sub(r"You carry out roadmap item .*? not the file whole\. ",
                       "You carry out %s, work of Landin that is no roadmap"
                       " item: %s.\n" % (item, arguments.work), brief,
                       count=1, flags=re.S)
    (item_directory(item, cwd) / "brief.md").write_text(brief,
                                                         encoding="utf-8")
    journal(item, "started from %s in %s on %s%s" % (
        base[:12], worktree, branch,
        "; committed %s" % ", ".join(changed) if changed else ""), cwd)
    print("started %s in %s on branch %s from %s" % (item, worktree, branch,
                                                     base[:12]))
    if target != MAIN:
        print("it lands on %s, its phase's breaking window" % target)
    print("brief: %s" % (item_directory(item, cwd) / "brief.md"))
    if reservation:
        print("reserved: D%d-D%d, SR-%d-%d, Q-%d-%d" % (
            *reservation["D"], *reservation["SR"], *reservation["Q"]))
    return 0


# ----------------------------------------------------------- runs and gates

def run_state(directory):
    """finished (with its status), running, or lost, for a run directory."""
    directory = Path(directory)
    result = directory / "result.json"
    if result.exists():
        data = json.loads(result.read_text(encoding="utf-8"))
        return "finished, exit %s" % data.get("exit_status", "?")
    running = directory / "running.json"
    if running.exists():
        pid = json.loads(running.read_text(encoding="utf-8")).get("pid")
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return "lost: its wrapper ended without a result"
        except (PermissionError, TypeError):
            pass
        return "running"
    return "not started"


def run(arguments):
    item = arguments.item
    state = load(item)
    command = arguments.command
    if not command:
        raise Refused("name the command after --")
    where = Path(getattr(arguments, "cwd", None) or state["worktree"])
    if not where.is_dir():
        raise Refused("--cwd %s is not a directory" % where)
    where = where.resolve()
    directory = item_directory(item) / "runs" / arguments.name
    if directory.exists():
        raise Refused("%s exists: name the run anew, or `run_logged.py --wait"
                      " %s` for the one it holds" % (directory, directory))
    directory.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/run_logged.py"),
                    "--output", str(directory), "--detach", "--limit",
                    str(arguments.limit), "--", *command],
                   cwd=where, check=True)
    state["runs"].append({"name": arguments.name, "directory": str(directory),
                          "command": shlex.join(command), "cwd": str(where),
                          "started": stamp()})
    save(state)
    journal(item, "run %s started in %s: %s" % (arguments.name, where,
                                                 shlex.join(command)))
    print("wait: python3 scripts/run_logged.py --wait %s" % directory)
    return 0


def runs_of(commit):
    """COMMIT's gate runs, newest first, from one GraphQL query: the REST
    listing this was spent the account's REST quota beside the watches."""
    gate_watch = gate_module("gate_watch")
    try:
        return gate_watch.runs_of_commit(
            commit, repo=gate_watch.repository(repository()))
    except gate_watch.Unanswered as error:
        raise Refused("GitHub did not list the gate runs of %s: %s"
                      % (commit[:12], error))


def kind_of(run_entry, target=MAIN):
    """A run's kind: `main` is the push gate of the branch the item lands
    on, main or its window's integration branch."""
    if run_entry["event"] == "workflow_dispatch" and "boards" in \
            run_entry.get("displayTitle", ""):
        return "boards"
    if run_entry["event"] == "push" and run_entry["headBranch"] in (
            MAIN, target):
        return "main"
    return "software" if run_entry["event"] == "push" else run_entry["event"]


def record_gates(state, commit):
    """Add COMMIT's gate runs to STATE, refreshing those it holds."""
    tree = git("rev-parse", commit + "^{tree}", cwd=place(state))
    known = {entry["run"]: entry for entry in state["gates"]}
    for found in runs_of(commit):
        entry = known.get(found["databaseId"])
        if entry is None:
            entry = {"run": found["databaseId"], "commit": commit,
                     "tree": tree}
            state["gates"].append(entry)
        #  Judged again at every refresh: a boards dispatch recorded while
        #  queued has no title yet, so it was kept as `workflow_dispatch`,
        #  and the promotion never counted it as the boards.
        entry["kind"] = kind_of(found, target_of(state))
        attempt = found.get("attempt") or 1
        if (entry.get("attempt"), entry.get("conclusion")) != (
                attempt, found.get("conclusion") or ""):
            entry.pop("failed", None)
        entry["status"] = found["status"]
        entry["branch"] = found.get("headBranch") or ""
        entry["event"] = found.get("event") or ""
        entry["conclusion"] = found.get("conclusion") or ""
        entry["attempt"] = attempt
        if entry["kind"] == "boards" and entry["conclusion"] == "failure" \
                and entry.get("failed", "unknown") == "unknown":
            entry["failed"] = failure_of(entry["run"])
        if entry["kind"] == "main" and not entry.get("verdict"):
            verdict = verdict_of(entry["run"])
            if verdict:
                entry["verdict"] = verdict
    return state


def verdict_of(run_number):
    """The conclusion of RUN's aggregate `gate` job once it has one, else
    None.  Main's gate has its verdict there: the jobs that save main's
    caches after it are no evidence and end later."""
    try:
        jobs, _ = gate_module("gate_watch").jobs_of(run_number)
    except Exception:  # noqa: BLE001 -- a listing GitHub did not give
        return None
    for job in jobs:
        if job["name"] == VERDICT_JOB and job["status"] == "completed":
            return job["conclusion"] or None
    return None


def main_passed(entry):
    """Whether a main gate entry's verdict, or its whole run, passed."""
    return entry["kind"] == "main" and (
        entry.get("verdict") == "success" or (
            entry.get("conclusion") == "success"))


def main_ended(entry):
    """Whether a main gate entry has its verdict, or its run ended."""
    return entry["kind"] == "main" and bool(
        entry.get("verdict") or entry.get("status") == "completed")


def failure_of(run_number):
    """What failed in a boards run: `timing` when only timing jobs (and
    the aggregate after them) failed and every board leg passed,
    `aggregate` when only the aggregate did, `jobs` otherwise, or
    `unknown` when GitHub could not list its jobs."""
    try:
        gate_watch = gate_module("gate_watch")
        jobs, _ = gate_watch.jobs_of(run_number)
        return gate_watch.failure_kind(jobs) or "unknown"
    except Exception:  # noqa: BLE001 -- a listing GitHub did not give
        return "unknown"


FAILURE_TEXT = {
    "timing": "timing only, every board leg passed: read the timing log,"
              " and if it reads as noise `item.py boards %s --rerun-failed`",
    "aggregate": "the aggregate alone, every job before it passed: its"
                 " verdict or the cycles comparison; read its log",
    "jobs": "board or other jobs failed: read their logs",
    "unknown": "its jobs could not be listed: `item.py gate %s` again",
}


def gate_text(entry, item):
    """A gate entry's status and conclusion, with what a failure was."""
    text = "%s %s" % (entry.get("status", ""), entry.get("conclusion", ""))
    if entry.get("failed"):
        explained = FAILURE_TEXT.get(entry["failed"], entry["failed"])
        text += " (%s)" % (explained % item if "%s" in explained
                           else explained)
    return text


def complete_listing(run_number):
    """None when RUN's every job passed or was skipped, else what did not."""
    jobs, _ = gate_module("gate_watch").jobs_of(run_number)
    bad = [job["name"] for job in jobs
           if job["conclusion"] not in ("success", "skipped")]
    if not any(job["name"] == "gate" and job["conclusion"] == "success"
               for job in jobs):
        bad.append("gate (the aggregate) not passed")
    return ", ".join(bad) or None


def gate(arguments):
    item = arguments.item
    state = load(item)
    worktree = state["worktree"]
    git("fetch", "-q", "origin", cwd=worktree)
    if arguments.main:
        commit = state.get("promoted")
        if not commit:
            raise Refused("%s has not been promoted" % item)
    else:
        commit = git("rev-parse", "HEAD", cwd=worktree)
        pushed = git("rev-parse", "origin/" + state["branch"], cwd=worktree,
                     check=False)
        if pushed != commit:
            raise Refused("HEAD %s is not the pushed head of %s (%s): push"
                          " it, `git push -u origin %s`" % (
                              commit[:12], state["branch"],
                              (pushed or "absent")[:12], state["branch"]))
        if state["phase"] == "started":
            state["phase"] = "pushed"
    record_gates(state, commit)
    advance(state, commit, arguments.main)
    save(state)
    shown = [entry for entry in state["gates"] if entry["commit"] == commit]
    target = target_of(state)
    if arguments.main and any(main_ended(entry) for entry in shown):
        if release(item, "%s's gate on %s has its verdict" % (
                target, commit[:12])):
            print("%s's gate has its verdict: the promotion token is"
                  " released" % target)
    for entry in shown:
        print("run %s  %-8s %-24s %s" % (
            entry["run"], entry["kind"], "%s (%s)" % (
                entry.get("branch") or "?", entry.get("event") or "?"),
            gate_text(entry, item)))
        if entry["kind"] == "main" and entry.get("verdict") and (
                entry.get("status") != "completed"
                or entry.get("conclusion") != entry["verdict"]):
            print("  its verdict, the `%s` job: %s; %s" % (
                VERDICT_JOB, entry["verdict"],
                "the cache jobs after it are still running"
                if entry.get("status") != "completed" else
                "a job outside the verdict, one saving main's caches,"
                " ended %s: read it (`gh run view %s`); it is no evidence"
                % (entry.get("conclusion"), entry["run"])))
    if not shown:
        print("no gate run for %s yet" % commit[:12])
    elif arguments.main and not any(entry["kind"] == "main"
                                    for entry in shown):
        print("%s's own push gate on %s has not started yet: the runs above"
              " are the candidate branch's, not %s's" % (
                  target, commit[:12], target))
    if arguments.watch:
        return watch_gate(arguments, state, commit, shown)
    return 0


def watch_gate(arguments, state, commit, shown):
    """Follow COMMIT's newest gate run of the kind asked for.

    The watch is named by that run and its attempt, so a rerun on the same
    commit, a newer attempt or a new run, is watched afresh rather than
    answered with the finished watch of the old one.  Until GitHub lists a
    run the watch is named by the commit and waits for one.
    """
    item = arguments.item
    event, branch = (("push", target_of(state)) if arguments.main
                     else ("push", state["branch"]))
    prefix = "gate-%s-%s" % ("main" if arguments.main else "branch",
                             commit[:12])
    runs = item_directory(item) / "runs"
    for going in sorted(runs.glob(prefix + "*")):
        if run_state(going) == "running":
            print("already watched: python3 scripts/run_logged.py --wait %s"
                  % going)
            return 0
    kind = "main" if arguments.main else "software"
    newest = max((entry for entry in shown if entry["kind"] == kind),
                 key=lambda entry: entry["run"], default=None)
    if newest is None:
        name = prefix
        command = ["--commit", commit, "--event", event, "--branch", branch]
    else:
        name = "%s-run%s-attempt%s" % (prefix, newest["run"],
                                       newest.get("attempt", 1))
        command = ["--run", str(newest["run"])]
    directory = runs / name
    if directory.exists():
        print("already watched: python3 scripts/run_logged.py --wait %s"
              % directory)
        return 0
    watcher = ["python3", str(ROOT / "scripts/gate_watch.py")]
    if arguments.main:
        #  The token and the finish wait end at the verdict: the cache
        #  jobs after it are no evidence.
        arguments.name, arguments.limit = name, 7200
        arguments.command = watcher + ["--verdict", *command]
        return run(arguments)
    #  Two watches: the first returns at the first failed job, so the fix
    #  starts at once; the second names every failure at the run's end,
    #  for the push that fixes them all.
    arguments.name, arguments.limit = name + "-first", 7200
    arguments.command = watcher + command
    run(arguments)
    print("  it returns at the first failed job, or when the run passes:"
          " read that job's log and start the fix")
    arguments.name = name
    arguments.command = watcher + ["--all", *command]
    status = run(arguments)
    print("  it names every failed job at the run's end: push the fix"
          " once it ends, or once every job still running is of a kind the"
          " fix does not touch")
    return status


def advance(state, commit, main=False):
    """Move the phase on as far as COMMIT's passed runs take it."""
    passed = {entry["kind"] for entry in state["gates"]
              if entry["commit"] == commit
              and entry.get("conclusion") == "success"}
    if main:
        if "main" in passed or any(
                main_passed(entry) for entry in state["gates"]
                if entry["commit"] == commit):
            state["phase"] = "main-passed"
        return
    if state["phase"] in ("started", "pushed", "gate-passed") and \
            "software" in passed:
        state["phase"] = "gate-passed"
    if state["phase"] == "gate-passed" and "boards" in passed:
        state["phase"] = "boards-passed"


def boards(arguments):
    item = arguments.item
    state = load(item)
    commit = git("rev-parse", "HEAD", cwd=state["worktree"])
    pushed = git("rev-parse", "origin/" + state["branch"],
                 cwd=state["worktree"], check=False)
    if pushed != commit:
        raise Refused("push the head first: the dispatch runs the branch as"
                      " GitHub holds it")
    if arguments.rerun_failed:
        return rerun_boards(arguments, state, commit)
    git("fetch", "-q", "origin", cwd=state["worktree"])
    target = target_of(state)
    if not arguments.unmerged and git(
            "merge-base", "--is-ancestor",
            landing_base(target, state["worktree"]), commit,
            cwd=state["worktree"], check=False) is None:
        raise Refused("%s has moved past %s, so promotion would refuse"
                      " this tree and its boards would be dispatched again:"
                      " merge it first (`item.py merge-main %s`), or"
                      " --unmerged for board feedback before the final merge"
                      % (target, commit[:12], item))
    listed = runs_of(commit)
    going = [found for found in listed if kind_of(found, target) == "boards"
             and (found["status"] != "completed"
                  or found.get("conclusion") == "success")]
    if going and not arguments.again:
        #  A queued dispatch is not listed as running, and dispatching
        #  again beside it ran the boards twice on one tree.
        found = going[0]
        record_gates(state, commit)
        save(state)
        if found["status"] == "completed":
            print("boards run %s on %s passed: not dispatched again"
                  " (--again dispatches another)" % (found["databaseId"],
                                                     commit[:12]))
            return 0
        print("boards run %s on %s is %s: followed, not dispatched again"
              " (--again dispatches another)" % (
                  found["databaseId"], commit[:12], found["status"]))
        if arguments.watch:
            return watch_boards(arguments, found["databaseId"],
                                found.get("attempt") or 1)
        return 0
    if arguments.unmerged:
        journal(item, "boards dispatched with --unmerged")
    before = {found["databaseId"] for found in listed}
    result = subprocess.run(["gh", "workflow", "run", "gate.yml", "--ref",
                             state["branch"], "-f", "scope=boards"],
                            cwd=repository(), text=True,
                            stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise Refused("the dispatch failed: %s" % result.stderr.strip())
    for _ in range(30):
        new = [found for found in runs_of(commit)
               if found["databaseId"] not in before
               and found["event"] == "workflow_dispatch"]
        if new:
            record_gates(state, commit)
            save(state)
            journal(item, "boards dispatched: run %s on %s"
                    % (new[0]["databaseId"], commit[:12]))
            print("boards run %s on %s" % (new[0]["databaseId"], commit[:12]))
            if arguments.watch:
                return watch_boards(arguments, new[0]["databaseId"], 1)
            return 0
        time.sleep(4)
    raise Refused("the dispatch was accepted but GitHub lists no run yet;"
                  " `item.py gate %s` records it once it does" % item)


def watch_boards(arguments, run_number, attempt):
    arguments.name = "boards-%s" % run_number + (
        "-attempt%d" % attempt if attempt > 1 else "")
    arguments.limit = 7200
    arguments.command = ["python3", str(ROOT / "scripts/gate_watch.py"),
                         "--all", "--run", str(run_number)]
    return run(arguments)


def rerun_failed_jobs(run_number):
    """Ask GitHub to re-run RUN's failed jobs and the jobs that need them,
    the aggregate among them, as the run's next attempt."""
    result = subprocess.run(["gh", "run", "rerun", str(run_number),
                             "--failed"], cwd=repository(), text=True,
                            stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise Refused("the re-run failed: %s" % result.stderr.strip())


def rerun_boards(arguments, state, commit):
    """Re-run only the failed jobs of the head's newest boards run, when
    every board leg passed and only timing jobs failed."""
    item = arguments.item
    record_gates(state, commit)
    save(state)
    boards_runs = [entry for entry in state["gates"]
                   if entry["commit"] == commit and entry["kind"] == "boards"]
    if not boards_runs:
        raise Refused("no boards run on %s to re-run: `item.py boards %s`"
                      % (commit[:12], item))
    newest = max(boards_runs, key=lambda entry: entry["run"])
    if newest.get("status") != "completed":
        raise Refused("boards run %s has not ended" % newest["run"])
    if newest.get("conclusion") != "failure":
        raise Refused("boards run %s ended %s, not failed: nothing to re-run"
                      % (newest["run"], newest.get("conclusion")))
    kind = failure_of(newest["run"])
    newest["failed"] = kind
    save(state)
    if kind != "timing":
        raise Refused("boards run %s did not fail in timing alone (%s):"
                      " re-running its failed jobs would not give the"
                      " missing evidence" % (newest["run"], gate_text(
                          newest, item)))
    rerun_failed_jobs(newest["run"])
    attempt = newest.get("attempt", 1) + 1
    journal(item, "boards run %s: failed timing jobs re-run as attempt %d"
            % (newest["run"], attempt))
    print("boards run %s: its failed jobs re-run as attempt %d"
          % (newest["run"], attempt))
    if arguments.watch:
        return watch_boards(arguments, newest["run"], attempt)
    return 0


# ------------------------------------------------------- the promotion queue

def gate_module(name):
    """One of this script's sibling modules, gate_inputs or gate_watch."""
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    return __import__(name)


def queue_file(target=MAIN):
    """The promotion token's file for the branch items land on: main's, or
    one for each breaking window's integration branch."""
    return QUEUE if target == MAIN else "queue-%s.json" % target


@contextlib.contextmanager
def queue_locked(cwd=None, target=MAIN):
    """The promotion queue of TARGET, read and written under one lock:
    {"holder": {"item", "why", "taken"} or None, "waiting": [ITEM, ...],
    "sessions": {NAME: when it last asked}}.  A holder that is no item says
    `"session": true`; a waiter that is no item is in "sessions" too."""
    root = state_root(cwd)
    root.mkdir(parents=True, exist_ok=True)
    name = queue_file(target)
    with open(root / (name + ".lock"), "a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = root / name
        data = (json.loads(path.read_text(encoding="utf-8"))
                if path.exists() else {})
        schema = data.get("schema", 1)
        if schema > QUEUE_SCHEMA:
            raise Refused(
                "%s was written by a newer scripts/item.py, under the queue's"
                " rules of %d where this copy, %s, knows those of %d: run the"
                " newer copy, as `python3 %s/scripts/item.py` once the clone's"
                " main checkout is current, or merge main into this branch"
                % (path, schema, Path(__file__).resolve(), QUEUE_SCHEMA,
                   common_directory(cwd).parent))
        data["schema"] = QUEUE_SCHEMA
        data.setdefault("holder", None)
        data.setdefault("waiting", [])
        data.setdefault("sessions", {})
        before = json.dumps(data, sort_keys=True)
        yield data
        if json.dumps(data, sort_keys=True) != before:
            old = json.loads(before)
            temporary = root / (name + ".tmp")
            temporary.write_text(json.dumps(data, indent=2) + "\n",
                                 encoding="utf-8")
            os.replace(temporary, path)
            record_history(root / (name[:-len(".json")] + HISTORY), old,
                           data)


def holder_name(holder):
    return holder["item"] if holder else None


def record_history(path, old, new):
    """Append to PATH what changed between the queue's OLD and NEW: who
    took or gave up the token, and who joined or left the line."""
    events = []
    before, after = old.get("holder"), new.get("holder")
    if holder_name(before) != holder_name(after):
        if before:
            events.append({"event": "released", "name": before["item"],
                           "held_since": before.get("taken"),
                           "session": bool(before.get("session"))})
        if after:
            events.append({"event": "taken", "name": after["item"],
                           "why": after.get("why"),
                           "session": bool(after.get("session"))})
    elif after and before and after.get("promoted") != before.get("promoted"):
        events.append({"event": "promoted", "name": after["item"],
                       "commit": after.get("promoted")})
    waiting_before, waiting_after = old.get("waiting", []), new.get(
        "waiting", [])
    events += [{"event": "joined line", "name": name}
               for name in waiting_after if name not in waiting_before]
    events += [{"event": "left line", "name": name}
               for name in waiting_before if name not in waiting_after]
    if not events:
        return
    with open(path, "a", encoding="utf-8") as out:
        for event in events:
            out.write(json.dumps(dict(at=stamp(), **event)) + "\n")


def queue_targets(cwd=None):
    """Every branch with a queue file: main first, then the windows'."""
    root = state_root(cwd)
    found = [MAIN]
    if root.is_dir():
        found += sorted(path.name[len("queue-"):-len(".json")]
                        for path in root.glob("queue-*.json"))
    return found


def alive(item, cwd=None):
    """Whether this clone still runs ITEM: its state exists, unfinished."""
    path = item_directory(item, cwd) / "state.json"
    if not path.exists():
        return False
    return json.loads(path.read_text(encoding="utf-8"))["phase"] != "finished"


def main_gate_ended(item, commit):
    """Whether main's gate on COMMIT, which ITEM promoted while holding the
    token, has its verdict, its aggregate `gate` job concluded, as GitHub lists
    it now; False when GitHub cannot say.  An earlier promotion of the same item, a --partial one, is not
    asked about: its gate ended before this hold began."""
    try:
        state = load(item)
        record_gates(state, commit)
        save(state)
    except (Refused, OSError, ValueError):
        return False
    return any(main_ended(entry) for entry in state["gates"]
               if entry["commit"] == commit)


def settle(data, ask):
    """Drop a holder or waiter this clone no longer runs, and, when ASK,
    a holder whose main gate has its verdict.  A session that is no item holds
    the token until it releases it, and waits in line while it keeps
    asking, at most SESSION_LINE seconds apart."""
    holder = data["holder"]
    if holder and holder.get("session"):
        pass
    elif holder and not alive(holder["item"]):
        data["holder"] = None
    elif holder and ask and holder.get("promoted") and \
            main_gate_ended(holder["item"], holder["promoted"]):
        journal(holder["item"], "promotion token released: main's gate on"
                " the promoted commit has its verdict")
        data["holder"] = None
    fresh = time.time() - SESSION_LINE
    data["sessions"] = {name: asked for name, asked
                        in data["sessions"].items() if asked >= fresh}
    data["waiting"] = [waiting for waiting in data["waiting"]
                       if waiting in data["sessions"] or alive(waiting)]


def wait_command(item, session=False):
    if session:
        return ("python3 scripts/item.py queue --wait %s --why TEXT, again"
                " on exit 124 (the line keeps %s while it asks at least every"
                " %d seconds)" % (item, item, SESSION_LINE))
    return ("python3 scripts/item.py run %s queue-wait --limit 7200 --"
            " python3 scripts/item.py queue --wait %s --timeout 7000, then"
            " wait on the run it names; or python3 scripts/item.py queue"
            " --wait %s, again on exit 124" % (item, item, item))


def gated(item, refresh=False):
    """Whether ITEM's worktree head has a passed push gate as its state
    records it, asking GitHub first when REFRESH and it does not."""
    if not alive(item):
        return False
    state = load(item)
    head = git("rev-parse", "HEAD", cwd=state["worktree"], check=False) \
        if Path(state["worktree"]).exists() else None

    def passed():
        return bool(head) and any(
            entry["commit"] == head and entry.get("kind") == "software"
            and entry.get("conclusion") == "success"
            for entry in state["gates"])
    if not passed() and refresh and head and shutil.which("gh"):
        try:
            record_gates(state, head)
            save(state)
        except Refused:
            pass
    return passed()


def take(item, why, ask=True, target=MAIN, session=False):
    """(True, None) when ITEM holds TARGET's promotion token, taking it if
    it is free and nobody waits before ITEM; else (False, why not), with
    ITEM put in line.  SESSION takes it for work that is no item, which
    keeps its place in line while it keeps asking.  A member of a batch
    is refused: the batch's token serves it.

    An item takes the token only once its head has a passed push gate:
    one that took it for its final merge while its candidate still gated
    held main for a hundred minutes.  Until then it keeps its place in
    line and the token passes over it to the first that is ready; work
    that is no item says itself when it is ready."""
    if not session and alive(item):
        refuse_riding(load(item), "wait for the token")
    ready = session or gated(item, refresh=ask)
    with queue_locked(target=target) as data:
        if session:
            data["sessions"][item] = time.time()
        settle(data, ask)
        holder = data["holder"]
        if holder and holder["item"] == item:
            data["sessions"].pop(item, None)
            return True, None
        if holder:
            if item not in data["waiting"]:
                data["waiting"].append(item)
            return False, (
                "%s holds the promotion token of %s since %s (%s), until %s;"
                " %s. A merge or promotion now would be gated again once it"
                " lands. Wait: %s" % (
                    holder["item"], target, holder["taken"], holder["why"],
                    "it releases it" if holder.get("session") else
                    "main's gate on its promotion has its verdict" if target == MAIN
                    else "it lands", "%s is number %d in line" % (
                        item, data["waiting"].index(item) + 1),
                    wait_command(item, session)))
        ahead = [other for other in (
            data["waiting"][:data["waiting"].index(item)]
            if item in data["waiting"] else data["waiting"])
            if other in data["sessions"] or gated(other)]
        if not ready:
            if item not in data["waiting"]:
                data["waiting"].append(item)
            return False, (
                "%s's head has no passed push gate yet, so it does not take"
                " the promotion token, which passes to the first ready in"
                " line; it keeps its place.  Push the head and let its gate"
                " pass (`item.py push %s --watch`), then ask again."
                " Wait: %s" % (item, item, wait_command(item, session)))
        if ahead:
            if item not in data["waiting"]:
                data["waiting"].append(item)
            return False, ("%s waits for the promotion token before %s."
                           " Wait: %s" % (", ".join(ahead), item,
                                          wait_command(item, session)))
        data["waiting"] = [other for other in data["waiting"]
                           if other != item]
        data["sessions"].pop(item, None)
        data["holder"] = {"item": item, "why": why, "taken": stamp()}
        if session:
            data["holder"]["session"] = True
    if not session:
        journal(item, "promotion token of %s taken (%s)" % (target, why))
    return True, None


def mark_promoted(item, commit, target=MAIN):
    """Record on ITEM's hold the commit it promoted, whose main gate
    ending ends the hold."""
    with queue_locked(target=target) as data:
        if data["holder"] and data["holder"]["item"] == item:
            data["holder"]["promoted"] = commit


def release(item, why, target=None):
    """Give up ITEM's token or place in line, of TARGET's queue or, with
    none named, of every queue; whether it held a token."""
    held = False
    for each in ([target] if target else queue_targets()):
        with queue_locked(target=each) as data:
            if data["holder"] and data["holder"]["item"] == item:
                data["holder"] = None
                held = True
            data["waiting"] = [other for other in data["waiting"]
                               if other != item]
            data["sessions"].pop(item, None)
    if held and alive(item):
        journal(item, "promotion token released: %s" % why)
    return held


def queue_target(arguments, item=None):
    """The queue a `queue` command means: --target, else ITEM's landing
    branch, else main."""
    if arguments.target:
        return arguments.target
    if item and alive(item):
        return target_of(load(item))
    return MAIN


def queue(arguments):
    if arguments.release and alive(arguments.release):
        refuse_riding(load(arguments.release), "leave by giving up a place"
                      " in line")
    if arguments.release:
        held = release(arguments.release, "given up with `queue --release`",
                       arguments.target)
        print("%s %s" % (arguments.release, "released the promotion token"
                         if held else "holds no token; left the line"))
        return 0
    if arguments.take and alive(arguments.take):
        #  Work this clone runs, a batch say, takes it as an item does,
        #  once its head has a passed push gate; batch-1's integrator was
        #  refused here ("is an item") and released by hand.
        target = queue_target(arguments, arguments.take)
        taken, why = take(arguments.take, arguments.why or "taken by hand",
                          target=target)
        if not taken:
            print(why)
            return 1
        print("%s holds the promotion token of %s" % (arguments.take, target))
        return 0
    if arguments.take:
        target = arguments.target or MAIN
        taken, why = take(arguments.take, arguments.why or "taken by hand",
                          target=target, session=True)
        if not taken:
            print(why)
            return 1
        print("%s holds the promotion token of %s until `item.py queue"
              " --release %s`" % (arguments.take, target, arguments.take))
        return 0
    if arguments.wait:
        session = not alive(arguments.wait)
        if session and not arguments.why:
            raise Refused("this clone runs no item %s: work that is no item"
                          " waits for the token with `queue --wait %s --why"
                          " TEXT`, saying what it is for" % (
                              arguments.wait, arguments.wait))
        target = queue_target(arguments, arguments.wait)
        deadline = time.monotonic() + arguments.timeout
        asked = 0.0
        while True:
            ask = time.monotonic() - asked >= QUEUE_ASK
            if ask:
                asked = time.monotonic()
            taken, why = take(arguments.wait, arguments.why if session
                              else "waited in line", ask=ask, target=target,
                              session=session)
            if taken:
                print(("%s holds the promotion token of %s until `item.py"
                       " queue --release %s`" if session else
                       "%s holds the promotion token of %s: merge it"
                       " (`item.py merge-main %s`) or promote")
                      % (arguments.wait, target, arguments.wait))
                return 0
            if time.monotonic() >= deadline:
                print(why.split(" Wait: ")[0])
                return 124
            time.sleep(min(QUEUE_POLL, max(0.0, deadline - time.monotonic())))
    for target in ([arguments.target] if arguments.target
                   else queue_targets()):
        with queue_locked(target=target) as data:
            settle(data, ask=True)
            holder, waiting = data["holder"], list(data["waiting"])
        label = "" if target == MAIN else " of %s" % target
        print("promotion token%s: %s" % (label, (
            "%s since %s (%s)" % (holder["item"], holder["taken"],
                                  holder["why"])
            if holder else "free")))
        print("waiting%s: %s" % (label, ", ".join(waiting) or "nobody"))
    return 0


def queue_line():
    """The tokens' holders and lines, for `status`, without asking
    GitHub."""
    lines = []
    for target in queue_targets():
        path = state_root() / queue_file(target)
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        holder = data.get("holder")
        if not holder and not data.get("waiting"):
            continue
        lines.append("promotion token%s: %s; waiting: %s" % (
            "" if target == MAIN else " of %s" % target,
            "%s since %s" % (holder["item"], holder["taken"]) if holder
            else "free", ", ".join(data.get("waiting") or []) or "nobody"))
    return "\n".join(lines) or None


# ------------------------------------------------------- merging and pushing

def citations_problem(worktree):
    """Why the worktree's citations.txt is stale, or None.  It names the
    compiler sources' digest, so a merge that brings a compiler change
    leaves it stale, and the documents job fails minutes into the gate."""
    worktree = Path(worktree)
    if not (worktree / "check.py").exists() or \
            not (worktree / "citations.txt").exists():
        return None
    probe = ("import sys\nsys.path.insert(0, '.')\nimport check\n"
             "fresh = check.citations_dump()\n"
             "held = open('citations.txt', encoding='utf-8').read()\n"
             "if fresh is not None and fresh != held:\n"
             "    print(check.regenerating('citations.txt'))\n"
             "    sys.exit(1)\n")
    result = subprocess.run([sys.executable, "-B", "-c", probe],
                            cwd=worktree, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode == 0:
        return None
    if result.returncode == 1 and result.stdout.strip():
        return ("citations.txt is stale over this tree: regenerate it with"
                " %s, commit it, then push" % result.stdout.strip())
    return "the citations check could not run: %s" % (
        result.stderr.strip().splitlines() or ["no output"])[-1]


REGISTER_PATHS = ("ROADMAP.md", "roadmap/")


def register_problem(worktree, since=None):
    """What `check.py` refuses in the worktree's register, or None.

    A merge can bring completed items that age an open row past its limit,
    and a push that changes the roadmap or the register can break its other
    rules; the documents job refused either only after the heavy jobs had
    run.  When the commits since SINCE change ROADMAP.md or roadmap/, the
    whole `check.py` runs; otherwise its register-age check alone.
    """
    worktree = Path(worktree)
    if not (worktree / "check.py").exists():
        return None
    changed = since and git("diff", "--name-only", since, "HEAD", "--",
                            *REGISTER_PATHS, cwd=worktree, check=False)
    if changed:
        result = subprocess.run([sys.executable, "check.py"], cwd=worktree,
                                text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        if result.returncode == 0:
            return None
        lines = result.stdout.strip().splitlines() or ["no output"]
        return ("`python3 check.py` refuses this tree, which changes the"
                " roadmap or the register:\n%s" % "\n".join(lines[-20:]))
    probe = ("import sys\nsys.path.insert(0, '.')\nimport check\n"
             "if not hasattr(check, 'register_age_problems'):\n"
             "    sys.exit(0)\n"
             "found = check.register_age_problems(check.ROOT,"
             " check.register_ages(check.ROOT))\n"
             "for where, line, text in found:\n"
             "    print('%s:%s: %s' % (where, line, text))\n"
             "sys.exit(1 if found else 0)\n")
    result = subprocess.run([sys.executable, "-B", "-c", probe],
                            cwd=worktree, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode == 0:
        return None
    if result.returncode == 1 and result.stdout.strip():
        return ("the register's age check refuses this tree, as the gate's"
                " documents job would:\n%s" % result.stdout.strip())
    return "the register's age check could not run: %s" % (
        result.stderr.strip().splitlines() or ["no output"])[-1]


#  The pre-push checks: what made whole gates fail in minutes on
#  2026-11-24 and 11-25, each selected by the paths the push changes.
LIBRARY_ROOTS = ("core/", "hosted/", "platform/")
COMPILER_ROOTS = ("compiler/",) + LIBRARY_ROOTS
FORMAT_CASE = "formatting/core and the examples are formatted"
#  A new fixture's sources are held to `refine fmt`'s layout; a push that
#  added one once did not select it.
CORPUS_CASE = "formatting/the corpus is formatted"
FIXTURE_ROOT = "compiler/tests/fixtures/"
CLOSURE_CASE = ("fixture execution/debugger workload inventories are their"
                " closures")
#  Paths whose change moves emitted sizes or instruction counts.
EMISSION_ROOTS = LIBRARY_ROOTS + ("compiler/ada/src/", "compiler/tests/")


def changed_paths(worktree, since, added=False):
    """The paths the commits since SINCE change (only those they add,
    with ADDED), deletions left out."""
    if not since:
        return []
    return (git("diff", "--name-only", "--diff-filter=%s" % (
        "A" if added else "ACMR"), since, "HEAD", cwd=worktree,
        check=False) or "").splitlines()


def prepush_checks(worktree, since, roadmap_checked=False):
    """The cheap checks the push's changes since SINCE call for, as
    (what they hold, command) pairs: one dev-test.sh invocation with every
    selector, the library's comment check, and the whole check.py after a
    merge, which brings other items' rows and completions."""
    paths = changed_paths(worktree, since)
    added = changed_paths(worktree, since, added=True)
    selectors = []
    if any(path.endswith(".ldn") for path in paths):
        selectors.append("--case=" + FORMAT_CASE)
    if any(path.startswith(FIXTURE_ROOT) and path.endswith(".ldn")
           for path in added):
        selectors.append("--case=" + CORPUS_CASE)
    if any(path.startswith(COMPILER_ROOTS) for path in paths):
        selectors.append("--suite=lowering")
    if any(path.startswith(LIBRARY_ROOTS) and path.endswith(".ldn")
           for path in added):
        selectors.append("--case=" + CLOSURE_CASE)
    checks = []
    if selectors:
        checks.append(("the formatting, the recorded lowering and the"
                       " debugger workloads' closures, as the changed paths"
                       " select", ["./scripts/dev-test.sh", *selectors]))
    if any(path.startswith(LIBRARY_ROOTS) for path in paths):
        checks.append(("the library's per-target comments",
                       [sys.executable, "scripts/script_tests.py",
                        "test_library_docs"]))
    merged = since and git("rev-list", "--merges", "%s..HEAD" % since,
                           cwd=worktree, check=False)
    if merged and not roadmap_checked:
        checks.append(("the whole check.py, after a merge",
                       [sys.executable, "check.py"]))
    return checks


def run_prepush(item, worktree, checks):
    """Run CHECKS in WORKTREE, each logged under the item's runs; the
    first that fails as a refusal naming it."""
    logs = item_directory(item) / "runs" / "prepush"
    logs.mkdir(parents=True, exist_ok=True)
    for number, (what, command) in enumerate(checks, 1):
        log = logs / ("%d.log" % number)
        print("pre-push check: %s: %s" % (what, shlex.join(command)),
              flush=True)
        with open(log, "w", encoding="utf-8") as out:
            result = subprocess.run(command, cwd=worktree, text=True,
                                    stdout=out, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL)
        if result.returncode != 0:
            tail = log.read_text(encoding="utf-8",
                                 errors="replace").splitlines()[-15:]
            raise Refused(
                "the pre-push check of %s failed (exit %d): %s\n%s\nits"
                " log: %s\nnothing was pushed; fix it, or push with"
                " --no-check when the failure is not the change's"
                % (what, result.returncode, shlex.join(command),
                   "\n".join("  " + line for line in tail), log,))


def baseline_warning(worktree, since):
    """A note when the push changes what the measured images hold."""
    if not any(path.startswith(EMISSION_ROOTS)
               for path in changed_paths(worktree, since)):
        return None
    return ("note: this push changes the library or the compiler, so the"
            " measured sizes and instruction counts may move.  `measure.py"
            " size` and `instructions` for Linux, RV64 and the firmware"
            " targets show it here in about seven minutes; Darwin's and"
            " FreeBSD's come from the gate, `measure.py record --from-run"
            " RUN` (docs/measurement.md, Size)")


def merge_main(arguments):
    item = arguments.item
    state = load(item)
    refuse_riding(state, "merge main")
    worktree = state["worktree"]
    git("fetch", "-q", "origin", cwd=worktree)
    if git("status", "--porcelain", cwd=worktree):
        raise Refused("the worktree has uncommitted changes: commit them"
                      " first")
    head = git("rev-parse", "HEAD", cwd=worktree)
    target = target_of(state)
    landing = landing_base(target, worktree)
    other = arguments.branch and arguments.branch not in (
        target, "origin/" + target)
    if other:
        #  A continuous item lands on main, and a breaking window's branch
        #  takes it; one that must also land on the window's branch merges
        #  that branch here, under the same rules, without main's token.
        landing = arguments.branch if arguments.branch.startswith(
            "origin/") else "origin/" + arguments.branch
        if git("rev-parse", "-q", "--verify", landing, cwd=worktree,
               check=False) is None:
            raise Refused("there is no branch %s on GitHub to merge"
                          % landing)
    if git("merge-base", "--is-ancestor", landing, head, cwd=worktree,
           check=False) is not None:
        print("%s is already in %s: nothing to merge" % (landing, head[:12]))
        return 0
    #  An item that does not gate alone never takes the token: its batch
    #  does, and its merge only picks up the target; an ungated head was
    #  refused here before.
    lone = lone_problem(state, head) is None or is_batch(state)
    if not arguments.no_queue and not other and lone:
        taken, why = take(item, "final merge of %s" % target, target=target)
        if not taken:
            raise Refused(why)
    for problem in reserved_clashes(state, landing):
        print(problem)
    gate_inputs = gate_module("gate_inputs")
    log = git("log", "--format=%H%x00%B%x01", "HEAD..%s" % landing,
              cwd=worktree)
    brought = [entry.strip("\n").split("\0", 1)
               for entry in log.split("\x01") if entry.strip()]
    undeclared = [sha[:12] for sha, body in brought
                  if not gate_inputs.DECLARATION.search(body)]
    merged = subprocess.run(["git", "merge", "--no-ff", "--no-commit",
                             landing], cwd=worktree, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if merged.returncode != 0:
        conflicted = git("diff", "--name-only", "--diff-filter=U",
                         cwd=worktree, check=False) or ""
        journal(item, "merge of %s stopped on conflicts: %s"
                % (landing, " ".join(conflicted.split())))
        raise Refused(
            "the merge stopped on conflicts in %s: resolve them and commit."
            " A merge with resolved conflicts is a new tree: push it"
            " (`item.py push %s --watch`), then its boards. The promotion"
            " token of %s stays %s's until %s"
            % (", ".join(conflicted.split()) or "the files git names", item,
               target, item, "main's gate on its promotion has its verdict"
               if target == MAIN else "it lands"))
    tree = git("write-tree", cwd=worktree)
    same = gate_inputs.key(tree, cwd=worktree) == \
        gate_inputs.key(head, cwd=worktree)
    declare = same and not undeclared
    message = "Merge %s into %s" % (landing, state["branch"])
    if declare:
        message += ("\n\nEvery commit it brings says it is explanatory, and"
                    " the merged tree has the candidate's gate key.\n\n"
                    + EXPLANATORY)
    git("commit", "-q", "-m", message, cwd=worktree)
    merge = git("rev-parse", "HEAD", cwd=worktree)
    journal(item, "merged %s as %s%s" % (
        landing, merge[:12], ", declared explanatory" if declare else ""))
    print("merged %s as %s" % (landing, merge[:12]))
    if declare:
        print("it says `%s`: the gate reuses the candidate's pass, and a"
              " boards dispatch that passed on %s still counts; push it"
              " (`item.py push %s --watch`) and promote once its gate"
              " passes" % (EXPLANATORY, head[:12], item))
    else:
        reasons = []
        if undeclared:
            reasons.append("commits from %s without `%s`: %s" % (
                landing[len("origin/"):], EXPLANATORY, ", ".join(undeclared[:8])
                + (" and %d more" % (len(undeclared) - 8)
                   if len(undeclared) > 8 else "")))
        if not same:
            changed = [path for path in (git(
                "diff", "--name-only", head, tree, cwd=worktree) or ""
            ).splitlines() if path not in gate_inputs.CONTENT_FREE
                and not path.startswith(gate_inputs.CONTENT_FREE_TREES)]
            reasons.append("paths outside the explanatory set differ: %s" % (
                ", ".join(changed[:8]) + (" and %d more" % (len(changed) - 8)
                                          if len(changed) > 8 else "")
                if changed else "modes or paths of the explanatory files"))
        print("the merged tree is new (%s): push it with its boards beside"
              " its gate (`item.py push %s --boards --watch`)"
              % ("; ".join(reasons), item))
    stale = citations_problem(worktree)
    if stale:
        print(stale)
    refused = register_problem(worktree)
    if refused:
        print(refused)
        print("`item.py push %s` refuses the merge until this is fixed and"
              " committed" % item)
        return 1
    return 0


# ---------------------------------------------------------------- batches

#  What still gates alone, as a batch of one: the toolchain, CI
#  and the rig, the board harness with it.  Everything else an item
#  changes reaches main in a batch.
ALONE_FILES = ("environments/pins.sh", "flake.nix", "flake.lock")
ALONE_TREES = (".github/", "environments/boards/", "compiler/tests/board/")
#  The lane table: each lane's jobs and the paths whose change reaches it.
LANES = ".github/gate-lanes.json"


def alone_paths(paths):
    """The paths of PATHS a change to which gates alone."""
    return [path for path in paths
            if path in ALONE_FILES or path.startswith(ALONE_TREES)]


def change_of(worktree, base, head):
    """The paths HEAD changes since its merge base with BASE."""
    since = git("merge-base", base, head, cwd=worktree, check=False)
    if not since:
        return []
    return (git("diff", "--name-only", since, head, cwd=worktree,
                check=False) or "").splitlines()


def is_batch(state):
    return "batch" in state


def in_batch(state):
    """The batch STATE's item is a member of and has not landed with, or
    None."""
    member = state.get("in_batch")
    if member and not member.get("landed"):
        return member
    return None


riding = in_batch


def refuse_riding(state, doing):
    member = in_batch(state)
    if member:
        raise Refused(
            "%s is a member of batch %s, merged at %s: it does not %s until"
            " the batch lands; `item.py batch drop %s %s` takes it out"
            % (state["item"], member["name"], member["head"][:12], doing,
               member["name"], state["item"]))


def lone_problem(state, commit):
    """Why STATE's head may not reach its target on a gate of its own, or
    None: only a batch, a change to the toolchain, CI or the rig, a batch
    of one, or a change every commit of which says `Gate: explanatory`,
    whose gate reuses a pass, may."""
    if is_batch(state):
        return None
    worktree = place(state)
    landing = landing_base(target_of(state), worktree)
    if alone_paths(change_of(worktree, landing, commit)):
        return None
    since = git("merge-base", landing, commit, cwd=worktree, check=False)
    if since == commit:
        return None
    #  The item's own commits: a merge of the target it made is not its
    #  change, and is declared only when all the target brought is.
    own = (git("log", "--no-merges", "--format=%B%x00", "%s..%s" % (
        since, commit), cwd=worktree, check=False) or "") if since else ""
    bodies = [body for body in own.split("\0") if body.strip()]
    declaration = gate_module("gate_inputs").DECLARATION
    if bodies and all(declaration.search(body) for body in bodies):
        return None
    return ("%s does not gate alone: the complete gate belongs to a batch."
            " Check it with the exact selectors for what it touches, commit"
            " it complete on its branch, its closing commit included, and"
            " report it; a batch takes it (`item.py batch add BATCH %s`)"
            " and one gate and boards on the batch's merged tree are its"
            " evidence. Only a change to the toolchain (%s), CI or the rig"
            " (%s) gates alone, as a batch of one" % (
                state["item"], state["item"], ", ".join(ALONE_FILES),
                ", ".join(ALONE_TREES)))


def batch_states():
    return [state for state in running_states() if is_batch(state)
            and state["phase"] != "finished"]


def generated_files(worktree):
    """The files check.py regenerates, as the worktree's check.py names
    them."""
    probe = ("import sys\nsys.path.insert(0, '.')\nimport check\n"
             "for _, files in check.GENERATED:\n"
             "    for one in files:\n"
             "        print(one)\n")
    result = subprocess.run([sys.executable, "-B", "-c", probe],
                            cwd=worktree, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    return set(result.stdout.split()) if result.returncode == 0 else set()


def merge_member(batch, name, branch, head, worktree, member=None):
    """Merge NAME's HEAD, of BRANCH, into the batch's worktree as one
    commit; None, or why it was not merged, the worktree then as before.
    MEMBER is NAME's state when it is an item."""
    before = git("rev-parse", "HEAD", cwd=worktree)
    merged = subprocess.run(["git", "merge", "--no-ff", "--no-commit", head],
                            cwd=worktree, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    if merged.returncode != 0:
        conflicted = set((git("diff", "--name-only", "--diff-filter=U",
                              cwd=worktree, check=False) or "").split())
        generated = generated_files(worktree)
        if not conflicted or not conflicted <= generated:
            subprocess.run(["git", "merge", "--abort"], cwd=worktree)
            return ("conflicts outside the generated files: %s; the"
                    " integrator resolves no member's source, so %s joins a"
                    " later batch, or this one once its agent has merged the"
                    " batch's branch into its own"
                    % (", ".join(sorted(conflicted - generated))
                       or "the files git names", name))
        git("checkout", "--ours", "--", *sorted(conflicted), cwd=worktree)
        regenerated = subprocess.run([sys.executable, "check.py",
                                      GENERATE_ALL], cwd=worktree, text=True,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
        if regenerated.returncode != 0:
            subprocess.run(["git", "merge", "--abort"], cwd=worktree)
            return ("its conflicts were in generated files, and `check.py"
                    " %s` failed over the merge: %s" % (
                        GENERATE_ALL, (regenerated.stdout.strip().splitlines()
                                       or ["no output"])[-1]))
        git("add", "-A", cwd=worktree)
    git("commit", "-q", "-m", "Merge %s into %s: %s joins the batch\n\n"
        "%s's head %s, checked locally for what it touches." % (
            branch, batch["branch"], name, name, head[:12]), cwd=worktree)
    merge = git("rev-parse", "HEAD", cwd=worktree)
    clashes = reserved_clashes(member, merge) if member else []
    if clashes:
        git("reset", "-q", "--hard", before, cwd=worktree)
        return "; ".join(clashes)
    return None


def member_head(batch, name, worktree):
    """(kind, branch, head, problems) of NAME as a member of BATCH: an
    item this clone runs, or a branch that is no item's."""
    if name == batch["item"] or name in (MAIN, batch["branch"],
                                         target_of(batch)):
        return None, name, None, ["%s is no member's" % name]
    if alive(name):
        member = load(name)
        problems = []
        if is_batch(member):
            return "item", None, None, ["%s is a batch" % name]
        if target_of(member) != target_of(batch):
            problems.append("%s lands on %s, the batch on %s" % (
                name, target_of(member), target_of(batch)))
        joined = in_batch(member)
        if joined and joined["name"] != batch["item"]:
            problems.append("%s is a member of batch %s" % (name,
                                                            joined["name"]))
        head = git("rev-parse", "-q", "--verify", "refs/heads/"
                   + member["branch"], cwd=worktree, check=False)
        if not head:
            problems.append("%s's branch %s is not in this clone" % (
                name, member["branch"]))
            return "item", member["branch"], None, problems
        if not member.get("work"):
            items, _ = roadmap_items(git("show", head + ":ROADMAP.md",
                                         cwd=worktree))
            if items.get(name, {}).get("status") != "complete":
                problems.append("%s is not complete in its own ROADMAP.md at"
                                " %s: its closing commit is part of what it"
                                " brings" % (name, head[:12]))
        return "item", member["branch"], head, problems
    if any(state["branch"] == name and state["phase"] != "finished"
           for state in running_states()):
        return "branch", name, None, ["%s is an item's branch: name the item"
                                      % name]
    head = git("rev-parse", "-q", "--verify", "refs/heads/" + name,
               cwd=worktree, check=False) or git(
        "rev-parse", "-q", "--verify", "origin/" + name, cwd=worktree,
        check=False)
    if not head:
        return "branch", name, None, ["there is no item or branch %s" % name]
    return "branch", name, head, []


def batch_form(arguments):
    name = arguments.name
    if WORK_NAME.fullmatch(name) is None or ITEM_NAME.fullmatch(name):
        raise Refused("%r is no name for a batch: lower-case letters, digits"
                      " and hyphens, as batch-2" % name)
    cwd = REPOSITORY[0]
    git("fetch", "-q", "origin", cwd=cwd)
    target = arguments.target or MAIN
    landing = landing_base(target, cwd)
    if git("rev-parse", "-q", "--verify", landing, cwd=cwd,
           check=False) is None:
        raise Refused("there is no branch %s on GitHub to land on" % landing)
    form = argparse.Namespace(
        item=name, work="a batch: one gate and boards for its members",
        no_fetch=True, adopt=None, base=git("rev-parse", landing, cwd=cwd),
        branch=None, worktree=arguments.worktree, force=False,
        no_commit=True, no_reserve=True)
    start(form)
    state = load(name)
    state["target"] = target
    state["reserved"] = {}
    state["batch"] = {"integrator": arguments.integrator, "members": [],
                      "before": state["base"]}
    save(state)
    journal(name, "formed a batch landing on %s, integrator %s" % (
        target, arguments.integrator))
    print("batch %s lands on %s; its integrator is %s; add its members"
          " with `item.py batch add %s MEMBER ...`" % (
              name, target, arguments.integrator, name))
    return 0


def batch_add(arguments):
    batch = load(arguments.name)
    if not is_batch(batch):
        raise Refused("%s is no batch: `item.py batch form %s` makes one"
                      % (arguments.name, arguments.name))
    name = batch["item"]
    worktree = batch["worktree"]
    git("fetch", "-q", "origin", cwd=worktree)
    if git("status", "--porcelain", cwd=worktree):
        raise Refused("the batch's worktree has uncommitted changes: commit"
                      " them first")
    entry = batch["batch"]
    members = entry["members"]
    landing = landing_base(target_of(batch), worktree)
    if not members and git("merge-base", "--is-ancestor", landing, "HEAD",
                           cwd=worktree, check=False) is None:
        merged = subprocess.run(["git", "merge", "--no-edit", landing],
                                cwd=worktree, text=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        if merged.returncode != 0:
            subprocess.run(["git", "merge", "--abort"], cwd=worktree)
            raise Refused("the merge of %s stopped on conflicts" % landing)
        journal(name, "merged %s before the members" % landing)
    if not members:
        entry["before"] = git("rev-parse", "HEAD", cwd=worktree)
    refused = {}
    for wanted in arguments.members:
        if any(one["name"] == wanted for one in members):
            refused[wanted] = "already a member"
            continue
        kind, branch, head, problems = member_head(batch, wanted, worktree)
        if head:
            #  Measured from the target, not from the batch's first base:
            #  a member that merged the target since brings none of its
            #  changes as its own.
            alone = alone_paths(change_of(worktree, landing, head))
            if alone and (members or len(arguments.members) > 1):
                problems.append(
                    "it changes %s, which gates alone, as a batch of one:"
                    " form a batch of its own for it" % ", ".join(alone[:4]))
            if any(one.get("alone") for one in members):
                problems.append("the batch holds %s, which gates alone" % (
                    ", ".join(one["name"] for one in members
                              if one.get("alone"))))
        if problems:
            refused[wanted] = "; ".join(problems)
            continue
        member = load(wanted) if kind == "item" else None
        why_not = merge_member(batch, wanted, branch, head, worktree, member)
        if why_not:
            refused[wanted] = why_not
            continue
        merge = git("rev-parse", "HEAD", cwd=worktree)
        members.append({
            "name": wanted, "kind": kind, "branch": branch, "head": head,
            "base": git("merge-base", landing, head, cwd=worktree),
            "merge": merge, "joined": stamp(), "alone": bool(alone)})
        if member is not None:
            member["in_batch"] = {"name": name, "head": head, "merge": merge,
                                  "joined": stamp()}
            save(member)
            journal(wanted, "joined batch %s: %s merged into %s; leave the"
                    " branch alone until the batch lands, and fix what its"
                    " gate routes here on the batch's branch" % (
                        name, head[:12], batch["branch"]))
            #  A member never waits for a token: the batch takes it.
            for each in queue_targets():
                with queue_locked(target=each) as data:
                    data["waiting"] = [other for other in data["waiting"]
                                       if other != wanted]
        journal(name, "%s %s's %s merged" % (kind, wanted, head[:12]))
    save(batch)
    for wanted, why_not in refused.items():
        print("not added: %s: %s" % (wanted, why_not))
    print(batch_text(batch))
    if members:
        print("push it once, %s(`item.py push %s%s --watch`); route a failed"
              " job with `item.py batch route %s --run RUN`" % (
                  "with its boards beside its gate " if target_of(batch)
                  == MAIN else "", name, " --boards" if target_of(batch)
                  == MAIN else "", name))
    for problem in filter(None, (citations_problem(worktree),
                                 register_problem(worktree))):
        print(problem)
    return 1 if refused else 0


def batch_drop(arguments):
    """Rebuild the batch from the tree before its members, without those
    named, never by a revert, which would land on the target and undo the
    dropped member's change when it lands later."""
    batch = load(arguments.name)
    if not is_batch(batch):
        raise Refused("%s is no batch" % arguments.name)
    name = batch["item"]
    worktree = batch["worktree"]
    entry = batch["batch"]
    members = entry["members"]
    unknown = [one for one in arguments.members
               if one not in [member["name"] for member in members]]
    if unknown:
        raise Refused("%s is no member of batch %s" % (", ".join(unknown),
                                                        name))
    if git("status", "--porcelain", cwd=worktree):
        raise Refused("the batch's worktree has uncommitted changes")
    original = git("rev-parse", "HEAD", cwd=worktree)
    after = (git("rev-list", "--reverse", "--first-parent", "--no-merges",
                 "%s..HEAD" % entry["before"], cwd=worktree) or "").split()
    git("reset", "-q", "--hard", entry["before"], cwd=worktree)
    kept = []
    for member in members:
        if member["name"] in arguments.members:
            continue
        state = load(member["name"]) if member["kind"] == "item" and alive(
            member["name"]) else None
        why_not = merge_member(batch, member["name"], member["branch"],
                               member["head"], worktree, state)
        if why_not:
            #  Nothing changed: the branch, its fixes and every state are
            #  as they were before the drop.
            git("reset", "-q", "--hard", original, cwd=worktree)
            raise Refused("rebuilding without %s, %s no longer merges: %s;"
                          " the batch is left as it was" % (
                              ", ".join(arguments.members), member["name"],
                              why_not))
        kept.append(dict(member, merge=git("rev-parse", "HEAD",
                                           cwd=worktree)))
    for member in kept:
        if member["kind"] == "item" and alive(member["name"]):
            state = load(member["name"])
            state["in_batch"]["merge"] = member["merge"]
            save(state)
    for member in members:
        if member["name"] not in arguments.members:
            continue
        if member["kind"] == "item" and alive(member["name"]):
            state = load(member["name"])
            state.pop("in_batch", None)
            save(state)
            journal(member["name"], "dropped from batch %s; its branch is"
                    " as it was, and it joins a later batch" % name)
        journal(name, "dropped %s" % member["name"])
    entry["members"] = kept
    entry["rebuilt"] = True
    save(batch)
    print("rebuilt %s from %s without %s" % (batch["branch"],
                                              entry["before"][:12],
                                              ", ".join(arguments.members)))
    if after:
        print("%d commit(s) made on the batch after its merges were taken"
              " off with them; those a kept member needs go back with `git"
              " cherry-pick %s`" % (len(after), " ".join(
                  sha[:12] for sha in after)))
    print(batch_text(batch))
    return 0


def lane_table(worktree):
    path = Path(worktree) / LANES
    if not path.exists():
        raise Refused("%s has no %s to read the lanes from" % (worktree,
                                                              LANES))
    return json.loads(path.read_text(encoding="utf-8"))


def route(batch, jobs):
    """[(job, lane, member, path)] for each failed JOB: the member whose
    change reaches its lane's inputs, the last joined of them when several
    do, with the path that reaches; the one that joined last, with no
    path, when none does."""
    history = gate_module("gate_history")
    worktree = place(batch)
    table = lane_table(worktree)
    index = history.lane_index(table)
    members = batch["batch"]["members"]
    if not members:
        raise Refused("batch %s has no members" % batch["item"])
    out = []
    for job in jobs:
        lane = history.lane_of(job, index)
        row = table["lanes"].get(lane, {"inputs": ["**"]})
        globs = history.expand(row["inputs"], table.get("sets", {}))
        reaching = []
        for member in members:
            paths = (git("diff", "--name-only", member["base"],
                         member["head"], cwd=worktree, check=False)
                     or "").splitlines()
            found = history.reaches(paths, globs)
            if found:
                reaching.append((member["name"], found))
        name, path = reaching[-1] if reaching else (members[-1]["name"], None)
        out.append((job, lane, name, path))
    return out


def batch_route(arguments):
    batch = load(arguments.name)
    if not is_batch(batch):
        raise Refused("%s is no batch" % arguments.name)
    jobs = list(arguments.members or [])
    if arguments.run:
        listed, _ = gate_module("gate_watch").jobs_of(arguments.run)
        jobs += [job["name"] for job in listed
                 if job.get("conclusion") in ("failure", "timed_out",
                                              "cancelled")
                 and job["name"] != VERDICT_JOB]
    if not jobs:
        print("no failed job to route")
        return 0
    for job, lane, name, path in route(batch, jobs):
        print("%s (lane %s): %s, %s" % (
            job, lane, name, "whose change reaches the lane's inputs by %s"
            % path if path else "the member that joined last, since no"
            " member's change reaches the lane's inputs"))
        if alive(name):
            journal(name, "batch %s's job %s failed and is this member's:"
                    " fix it on the batch's branch %s in %s, or `item.py"
                    " batch drop %s %s`" % (batch["item"], job,
                                             batch["branch"],
                                             batch["worktree"],
                                             batch["item"], name))
    return 0


def batch_text(batch):
    entry = batch["batch"]
    lines = ["batch %s: lands on %s, integrator %s, %s, branch %s" % (
        batch["item"], target_of(batch), entry.get("integrator"),
        batch["phase"], batch["branch"])]
    for member in entry["members"]:
        lines.append("  %s %s %s%s" % (member["kind"], member["name"],
                                       member["head"][:12],
                                       ", gates alone" if member.get("alone")
                                       else ""))
    if not entry["members"]:
        lines.append("  no members yet")
    return "\n".join(lines)


def batch_list(arguments):
    states = [load(arguments.name)] if arguments.name else batch_states()
    if not states:
        print("this clone forms no batch")
    for state in states:
        if not is_batch(state):
            raise Refused("%s is no batch" % state["item"])
        print(batch_text(state))
    return 0


def batch(arguments):
    handler = {"form": batch_form, "add": batch_add, "drop": batch_drop,
               "route": batch_route, "list": batch_list}[arguments.action]
    if arguments.action != "list" and not arguments.name:
        raise Refused("name the batch")
    if arguments.action in ("add", "drop") and not arguments.members:
        raise Refused("name the members")
    return handler(arguments)


def batch_landing_problems(state, commit, items, partial):
    """Why the batch STATE cannot land with COMMIT."""
    problems = []
    worktree = state["worktree"]
    for member in state["batch"]["members"]:
        name, head = member["name"], member["head"]
        if member["kind"] == "item":
            if not alive(name):
                problems.append("member %s is no longer run here" % name)
                continue
            joined = in_batch(load(name))
            if not joined or joined["name"] != state["item"] or \
                    joined["head"] != head:
                problems.append("%s is no longer a member at %s: `item.py"
                                " batch drop %s %s`" % (name, head[:12],
                                                        state["item"], name))
        now = git("rev-parse", "-q", "--verify", "refs/heads/"
                  + member["branch"], cwd=worktree, check=False) or git(
            "rev-parse", "-q", "--verify", "origin/" + member["branch"],
            cwd=worktree, check=False)
        if now and now != head:
            problems.append("%s's branch moved past %s since it was merged:"
                            " its work goes on the batch's branch; `item.py"
                            " batch drop %s %s` otherwise" % (
                                name, head[:12], state["item"], name))
        if git("merge-base", "--is-ancestor", head, commit, cwd=worktree,
               check=False) is None:
            problems.append("%s's %s is not in %s" % (name, head[:12],
                                                      commit[:12]))
        if member["kind"] == "item" and not partial and not load(name).get(
                "work") and items.get(name, {}).get("status") != "complete":
            problems.append("member %s is not complete in the batch's"
                            " ROADMAP.md" % name)
    if not state["batch"]["members"]:
        problems.append("batch %s has no members" % state["item"])
    return problems


def land_batch(state, commit):
    """Write every item of the batch STATE as promoted with COMMIT, with
    the batch's gate and boards entries it rests on, marked `via`."""
    tree = git("rev-parse", commit + "^{tree}", cwd=state["worktree"])
    for member in state["batch"]["members"]:
        if member["kind"] != "item" or not alive(member["name"]):
            continue
        name = member["name"]
        own = load(name)
        known = {entry["run"] for entry in own["gates"]}
        for entry in state["gates"]:
            if entry["run"] in known:
                continue
            if entry["commit"] == commit or (
                    entry["kind"] == "boards" and (
                        entry["tree"] == tree
                        or entry.get("conclusion") == "success")):
                own["gates"].append(dict(entry, via=state["item"]))
        own["promoted"] = commit
        own["phase"] = "promoted"
        own["target"] = target_of(state)
        own["in_batch"]["landed"] = commit
        save(own)
        journal(name, "promoted %s to %s with batch %s" % (
            commit[:12], target_of(state), state["item"]))


def shown_url(url):
    """URL without any credentials it carries."""
    return re.sub(r"//[^/@]*@", "//", url)


def push_urls(worktree):
    """(GitHub's URL, [every mirror's]): origin's fetch URL is GitHub's,
    and its other push URLs, such as git.sr.ht's, are mirrors."""
    fetch = git("remote", "get-url", "origin", cwd=worktree)
    pushes = (git("remote", "get-url", "--push", "--all", "origin",
                  cwd=worktree, check=False) or "").splitlines()
    primary = fetch if fetch in pushes or not pushes else pushes[0]
    return primary, [url for url in pushes if url != primary]


def push_origin(item, worktree, refspec):
    """Push REFSPEC to GitHub and judge the step by it alone; then to each
    mirror, a refusal there reported as the mirror's, to retry.  A plain
    `git push origin` pushes both and fails as a whole when only the
    mirror refuses.  The mirrors that refused, as the commands that bring
    them up to date."""
    primary, mirrors = push_urls(worktree)
    if not mirrors:
        git("push", "-q", "origin", refspec, cwd=worktree)
        return []
    git("push", "-q", primary, refspec, cwd=worktree)
    #  A push by URL moves no remote-tracking branch; the fetch does.
    git("fetch", "-q", "origin", cwd=worktree)
    behind = []
    for mirror in mirrors:
        result = subprocess.run(["git", "push", "-q", mirror, refspec],
                                cwd=worktree, text=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        if result.returncode != 0:
            retry = "git push %s %s" % (shown_url(mirror), refspec)
            why = (result.stderr.strip().splitlines() or ["no output"])[-1]
            journal(item, "the mirror refused %s (%s); GitHub took it."
                    " Retry: %s" % (refspec, why, retry))
            print("note: GitHub took the push; the mirror %s refused it (%s)."
                  " GitHub's is what counts; bring the mirror up to date"
                  " later: %s" % (shown_url(mirror), why, retry))
            behind.append(retry)
    return behind


def reserved_clashes(state, other):
    """The numbers of STATE's reserved blocks that OTHER, a branch it
    merges, took without the item: each a line saying so."""
    worktree = state["worktree"]
    since = git("merge-base", "HEAD", other, cwd=worktree, check=False)
    if not since:
        return []
    sys.path.insert(0, str(ROOT / "scripts"))
    import register_next
    reserved_blocks = state.get("reserved", {})
    def block(kind):
        low, high = reserved_blocks.get(kind, (0, -1))
        return set(range(low, high + 1))
    out = ["D%d of %s's reserved block was taken on %s without it:"
           " renumber the item's own, or take the next with"
           " `register_next.py --decision`" % (n, state["item"], other)
           for n in sorted((decisions_used(other, worktree)
                            - decisions_used(since, worktree)) & block("D"))]
    for kind, directory, number in (
            ("SR", register_next.DIRECTORY, register_next.NUMBER),
            ("Q", register_next.QUESTION_DIRECTORY,
             register_next.QUESTION_NUMBER)):
        def files(revision):
            return register_next.numbers_in((git(
                "ls-tree", "--name-only", revision, directory + "/",
                cwd=worktree, check=False) or "").splitlines(), number)
        out += ["%s-%d of %s's reserved block was taken on %s without it:"
                " renumber the item's own, or take the next with"
                " `register_next.py`" % (kind, n, state["item"], other)
                for n in sorted((files(other) - files(since)) & block(kind))]
    return out


def push(arguments):
    item = arguments.item
    state = load(item)
    refuse_riding(state, "push")
    worktree = state["worktree"]
    if git("status", "--porcelain", cwd=worktree):
        raise Refused("the worktree has uncommitted changes: commit them"
                      " first")
    if git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=worktree,
           check=False):
        raise Refused("a merge is in progress: commit it first")
    lone = lone_problem(state, git("rev-parse", "HEAD", cwd=worktree))
    if lone:
        raise Refused(lone + "\nnothing was pushed")
    stale = citations_problem(worktree)
    if stale:
        raise Refused(stale)
    pushed = git("rev-parse", "-q", "--verify", "origin/" + state["branch"],
                 cwd=worktree, check=False)
    if pushed and git("merge-base", "--is-ancestor", pushed, "HEAD",
                      cwd=worktree, check=False) is None:
        #  A rebuilt batch: its old head is no base for what it changes.
        pushed_base = None
    else:
        pushed_base = pushed
    since = pushed_base or git("merge-base", "HEAD", landing_base(
        target_of(state), worktree), cwd=worktree, check=False)
    refused = register_problem(worktree, since)
    if refused:
        raise Refused(refused + "\nnothing was pushed")
    if arguments.no_check:
        journal(item, "pushed with --no-check: the pre-push checks skipped")
    else:
        run_prepush(item, worktree, prepush_checks(
            worktree, since, roadmap_checked=bool(since and git(
                "diff", "--name-only", since, "HEAD", "--", *REGISTER_PATHS,
                cwd=worktree, check=False))))
    warning = baseline_warning(worktree, since)
    if warning:
        print(warning)
    #  A batch rebuilt without a dropped member replaces the branch's
    #  merges; nothing else is pushed over a head it does not contain.
    rebuilt = (state.get("batch") or {}).get("rebuilt") and pushed and git(
        "merge-base", "--is-ancestor", pushed, "HEAD", cwd=worktree,
        check=False) is None
    push_origin(item, worktree, "%sHEAD:refs/heads/%s" % (
        "+" if rebuilt else "", state["branch"]))
    if is_batch(state) and state["batch"].pop("rebuilt", None):
        save(state)
        if rebuilt:
            journal(item, "the rebuilt batch replaced %s on GitHub"
                    % pushed[:12])
    git("branch", "-q", "--set-upstream-to=origin/%s" % state["branch"],
        cwd=worktree, check=False)
    head = git("rev-parse", "HEAD", cwd=worktree)
    journal(item, "pushed %s" % head[:12])
    print("pushed %s to %s" % (head[:12], state["branch"]))
    arguments.main = False
    try:
        status = gate(arguments)
    except Refused as error:
        #  The push stands; the boards are still dispatched beside it.
        print("the gate runs were not recorded: %s; `item.py gate %s`"
              " records them" % (error, item))
        status = 2
    if arguments.boards:
        #  Beside the gate rather than after it: a hold then waits for the
        #  longer of the two, not their sum.
        arguments.unmerged = arguments.rerun_failed = False
        arguments.again = False
        status = boards(arguments) or status
    return status


# ---------------------------------------------------------------- promotion

def explanatory_since(worktree, older, newer):
    """Whether every commit after OLDER up to NEWER says Gate: explanatory."""
    messages = git("log", "--format=%B%x00", "%s..%s" % (older, newer),
                   cwd=worktree)
    bodies = [body for body in messages.split("\0") if body.strip()]
    #  The gate's own reading: the declaration on a line of its own, not a
    #  sentence that mentions it.
    declaration = gate_module("gate_inputs").DECLARATION
    return all(declaration.search(body) for body in bodies)


def unrecorded_figures(run):
    """{class: {target: count}} of what RUN's aggregate recorded as figures
    no baseline records (D2854); {} when it recorded none."""
    jobs, _ = gate_module("gate_watch").jobs_of(run)
    inputs = gate_module("gate_inputs")
    for job in jobs:
        if job["name"] != "gate":
            continue
        notes = gh("api", "repos/{owner}/{repo}/check-runs/%s/annotations"
                   "?per_page=50" % job["databaseId"]) or []
        for note in notes:
            if note.get("title") == inputs.MOVES_TITLE:
                try:
                    return json.loads(note.get("message", ""))
                except ValueError:
                    return {"unreadable": {"annotation": 1}}
    return {}


def figures_problems(state, commit, software, boards):
    """Why COMMIT may not land for figures its gate run SOFTWARE, or the
    boards run BOARDS it takes, reported and no baseline records since:
    main's push would refuse the tree (D2854)."""
    worktree = state["worktree"]
    inputs = gate_module("gate_inputs")
    problems = []
    moved = unrecorded_figures(software) if software else {}
    if moved:
        problems.append(
            "run %s reported figures no baseline records (%s), and main"
            " refuses the tree: `scripts/measure.py record --from-run %s`,"
            " committed alone with `%s`, reuses the run's pass"
            % (software, inputs.describe_moves(moved), software, EXPLANATORY))
    if boards:
        cycles = {kind: targets for kind, targets in unrecorded_figures(
            boards["run"]).items() if kind in ("cycles", "unreadable")}
        if cycles:
            def read(rev, path):
                return git("show", "%s:%s" % (commit if rev == "HEAD" else rev,
                                              path), cwd=worktree, check=False)
            recorded, why = False, "the boards run's tree is this one"
            if boards["commit"] != commit:
                figures, keys = inputs.run_cycles(boards["run"])
                recorded, why = inputs.cycles_recorded(read, figures, keys)
            if not recorded:
                problems.append(
                    "boards run %s reported cycles no baseline records (%s):"
                    " %s; `environments/boards/timing.py record` of its"
                    " measure-cycles artifact, committed with `%s`, records"
                    " them" % (boards["run"], inputs.describe_moves(cycles),
                               why, EXPLANATORY))
    return problems


def evidence(state, commit):
    """Problems standing between COMMIT and main; empty when none."""
    worktree = state["worktree"]
    problems = []
    tree = git("rev-parse", commit + "^{tree}", cwd=worktree)
    software = [entry for entry in state["gates"]
                if entry["commit"] == commit and entry["kind"] == "software"
                and entry["conclusion"] == "success"]
    if not software:
        problems.append("no passed push gate on %s: push it and follow it"
                        " (`item.py gate %s --watch`)" % (commit[:12],
                                                          state["item"]))
    else:
        missing = complete_listing(software[-1]["run"])
        if missing:
            problems.append("run %s's listing does not pass: %s"
                            % (software[-1]["run"], missing))
    if target_of(state) != MAIN:
        #  A window's items land without boards: the window's one
        #  promotion to main dispatches them on the integrated tree.
        if software:
            problems += figures_problems(state, commit, software[-1]["run"], None)
        return problems
    passed_boards = [entry for entry in state["gates"]
                     if entry["kind"] == "boards"
                     and entry["conclusion"] == "success"]
    going = [entry for entry in state["gates"] if entry["kind"] == "boards"
             and entry["tree"] == tree and entry.get("status") != "completed"]
    taken = [entry for entry in passed_boards if entry["tree"] == tree or (
        git("merge-base", "--is-ancestor", entry["commit"], commit,
            cwd=worktree, check=False) is not None
        and explanatory_since(worktree, entry["commit"], commit))]
    problems += figures_problems(state, commit, software[-1]["run"] if software
                                 else None, taken[-1] if taken else None)
    if not taken:
        if going:
            problems.append("boards run %s on this tree has not finished:"
                            " `item.py gate %s` refreshes it"
                            % (going[-1]["run"], state["item"]))
        elif not (passed_boards == [] and explanatory_since(
                worktree, state["base"], commit)):
            problems.append("no passed boards dispatch on this tree, nor on"
                            " a commit after which every commit says `%s`:"
                            " `item.py boards %s`" % (EXPLANATORY,
                                                      state["item"]))
    return problems


def promote(arguments):
    item = arguments.item
    state = load(item)
    maintainers = [item] if state.get("maintainer") else []
    if is_batch(state):
        maintainers = [member["name"] for member in state["batch"]["members"]
                       if member["kind"] == "item" and alive(member["name"])
                       and load(member["name"]).get("maintainer")]
    if maintainers and not arguments.maintainer:
        raise Refused("%s says `Promotion: maintainer`, so %s is the"
                      " maintainer's to promote: report the passed candidate"
                      " instead" % (", ".join(maintainers), item))
    refuse_riding(state, "promote itself")
    worktree = state["worktree"]
    git("fetch", "-q", "origin", cwd=worktree)
    commit = git("rev-parse", "HEAD", cwd=worktree)
    if git("status", "--porcelain", cwd=worktree):
        raise Refused("the worktree has uncommitted changes")
    if git("rev-parse", "origin/" + state["branch"], cwd=worktree,
           check=False) != commit:
        raise Refused("HEAD is not the branch's pushed head")
    target = target_of(state)
    landing = landing_base(target, worktree)
    if git("merge-base", "--is-ancestor", landing, commit, cwd=worktree,
           check=False) is None:
        raise Refused("%s has moved past the candidate's base: `item.py"
                      " merge-main %s` takes the promotion token, merges"
                      " %s and says whether the merged tree reuses"
                      " the pass; push it and gate it" % (landing, item,
                                                          landing))
    lone = lone_problem(state, commit)
    if lone:
        raise Refused("not promoted: " + lone)
    record_gates(state, commit)
    for older in {entry["commit"] for entry in state["gates"]} - {commit}:
        record_gates(state, older)
    save(state)
    problems = evidence(state, commit)
    items, _ = roadmap_items(git("show", commit + ":ROADMAP.md", cwd=worktree))
    if not arguments.partial and not state.get("work") and items.get(
            item, {}).get("status") != "complete":
        problems.append("%s is not complete in the candidate's ROADMAP.md;"
                        " --partial promotes work short of its close" % item)
    if is_batch(state):
        problems += batch_landing_problems(state, commit, items,
                                           arguments.partial)
    try:
        others = gh("run", "list", "--workflow=gate.yml", "--status",
                    "in_progress", "--json", "databaseId,headBranch") or []
    except Refused:
        #  Only a note: an exhausted REST quota does not stop a promotion.
        others = []
    if problems:
        raise Refused("not promoted:\n  " + "\n  ".join(problems))
    if others:
        print("note: gates running now share the runners: %s" % ", ".join(
            "%s (%s)" % (o["databaseId"], o["headBranch"]) for o in others))
    if arguments.dry_run:
        with queue_locked() as data:
            settle(data, ask=True)
            holder = data["holder"]
        print("would push %s to %s; the promotion token is %s" % (
            commit[:12], target,
            "free" if not holder else "%s's" % holder["item"]))
        return 0
    taken, why = take(item, "promotion of %s" % commit[:12], target=target)
    if not taken:
        raise Refused(why)
    try:
        behind = push_origin(item, worktree,
                             "%s:refs/heads/%s" % (commit, target))
    except Refused:
        release(item, "the push to %s failed" % target, target)
        raise
    state["promoted"] = commit
    state["phase"] = "promoted"
    save(state)
    if is_batch(state):
        land_batch(state, commit)
    if target == MAIN:
        mark_promoted(item, commit)
    else:
        #  A sibling may land once this one has: the window's gate on the
        #  landed commit runs the tree the candidate's gate passed.
        release(item, "landed on %s" % target, target)
    journal(item, "promoted %s to %s%s" % (
        commit[:12], target, "; the mirror is behind" if behind else ""))
    print("promoted %s to %s; follow its gate: python3 scripts/item.py gate"
          " %s --main --watch" % (commit[:12], target, item))
    return 0


def finish(arguments):
    item = arguments.item
    state = load(item)
    worktree = Path(state["worktree"])
    target = target_of(state)
    landed = None
    if not state.get("promoted") and not arguments.unpromoted:
        #  An item that reached its landing branch by hand, or a window's
        #  item that reached main with the window, is finished as one
        #  promoted would be.
        git("fetch", "-q", "origin", cwd=place(state))
        head = git("rev-parse", "-q", "--verify", "refs/heads/%s"
                   % state["branch"], cwd=place(state), check=False)
        for branch in dict.fromkeys((target, MAIN)):
            if head and head != state["base"] and git(
                    "merge-base", "--is-ancestor", head, "origin/" + branch,
                    cwd=place(state), check=False) is not None:
                landed = branch
                break
        if not landed:
            raise Refused("%s was not promoted, and its branch head is in"
                          " neither %s; --unpromoted removes its worktree"
                          " and branches regardless" % (
                              item, " nor ".join(dict.fromkeys(
                                  ("origin/" + target, "origin/" + MAIN)))))
    #  Run from the item's own worktree, the script would go on asking Git
    #  in the directory it has just removed: everything after the removal
    #  runs in the clone's main checkout.
    home = main_checkout()
    if Path(home).resolve() == worktree.resolve():
        raise Refused("%s is the clone's main checkout, not an item's"
                      " worktree" % worktree)
    REPOSITORY[0] = home
    os.chdir(home)
    if state.get("promoted") and target != MAIN:
        #  The candidate's gate passed on the landed commit itself, as
        #  promotion asks; a sibling's push may cancel the window's run.
        git("fetch", "-q", "origin")
        if git("merge-base", "--is-ancestor", state["promoted"],
               "origin/" + target, check=False) is None:
            raise Refused("%s is not in origin/%s: was the window's branch"
                          " rewritten?" % (state["promoted"][:12], target))
    elif state.get("promoted"):
        git("fetch", "-q", "origin")
        record_gates(state, state["promoted"])
        main = [entry for entry in state["gates"]
                if entry["commit"] == state["promoted"]
                and entry["kind"] == "main"]
        if not any(main_passed(entry) for entry in main):
            raise Refused("main's gate on %s has not passed: %s" % (
                state["promoted"][:12], ", ".join(
                    "run %s %s" % (e["run"], e.get("verdict")
                                   or e["conclusion"] or e["status"])
                    for e in main) or "no run yet"))
    if worktree.exists():
        if git("status", "--porcelain", cwd=worktree):
            raise Refused("%s has uncommitted changes" % worktree)
        git("worktree", "remove", str(worktree))
    git("branch", "-D", state["branch"], check=False)
    remote = git("ls-remote", "--heads", "origin", state["branch"],
                 check=False)
    if remote:
        git("push", "-q", "origin", "--delete", state["branch"], check=False)
    release(item, "finished")
    state["phase"] = "finished"
    save(state)
    journal(item, "finished: worktree and branch %s removed%s" % (
        state["branch"], "; its head is in %s" % landed if landed else ""))
    done = state_root() / DONE_DIRECTORY
    done.mkdir(parents=True, exist_ok=True)
    os.replace(item_directory(item), done / item)
    print("finished %s; its state is kept in %s" % (item, done / item))
    return 0


# --------------------------------------------------------- status and resume

def last_activity(state):
    """The newest of the item's commits, journal, runs and edits."""
    times = []
    directory = item_directory(state["item"])
    for path in [directory / "journal.md", directory / "state.json"]:
        if path.exists():
            times.append(path.stat().st_mtime)
    for entry in state["runs"]:
        log = Path(entry["directory"]) / "command.log"
        if log.exists():
            times.append(log.stat().st_mtime)
    worktree = Path(state["worktree"])
    if worktree.exists():
        committed = git("log", "-1", "--format=%ct", cwd=worktree, check=False)
        if committed:
            times.append(float(committed))
        for line in (git("status", "--porcelain", cwd=worktree,
                         check=False) or "").splitlines():
            path = worktree / line[3:].split(" -> ")[-1]
            if path.exists():
                times.append(path.stat().st_mtime)
    return max(times) if times else 0


def describe(state, full=False):
    worktree = Path(state["worktree"])
    out = ["%s — %s: %s, branch %s%s" % (
        state["item"], state["title"], state["phase"], state["branch"],
        "" if target_of(state) == MAIN else ", lands on %s"
        % target_of(state))]
    if not worktree.exists():
        out.append("  worktree %s is missing" % worktree)
    else:
        head = git("rev-parse", "--short=12", "HEAD", cwd=worktree)
        ahead = git("rev-list", "--count", "%s..HEAD" % state["base"],
                    cwd=worktree)
        dirty = git("status", "--porcelain", cwd=worktree)
        out.append("  worktree %s at %s, %s commits on base %s%s" % (
            worktree, head, ahead, state["base"][:12],
            ", uncommitted changes" if dirty else ""))
        if full and dirty:
            out.extend("    " + line for line in dirty.splitlines())
    minutes = (time.time() - last_activity(state)) / 60
    out.append("  last activity %d min ago" % minutes)
    for entry in state["runs"]:
        out.append("  run %s: %s (%s)%s" % (
            entry["name"], run_state(entry["directory"]), entry["directory"],
            "" if entry.get("cwd", str(worktree)) == str(worktree)
            else ", in " + entry["cwd"]))
    for entry in state["gates"]:
        out.append("  gate run %s %s on %s: %s%s" % (
            entry["run"], entry["kind"], entry["commit"][:12],
            gate_text(entry, state["item"]), ", via batch %s"
            % entry["via"] if entry.get("via") else ""))
    member = state.get("in_batch") or {}
    if member:
        out.append("  member of batch %s with %s%s" % (
            member["name"], member["head"][:12], ", landed as %s"
            % member["landed"][:12] if member.get("landed") else ""))
    if is_batch(state):
        out.extend("  " + line for line in batch_text(state).splitlines())
    return out


def next_step(state):
    """What the item does next, after any run still going and any edit
    not yet committed."""
    item = state["item"]
    first = []
    running = [entry for entry in state["runs"]
               if run_state(entry["directory"]) == "running"]
    if running:
        first.append("wait for run %s: python3 scripts/run_logged.py --wait"
                     " %s, with --timeout under the calling tool's limit;"
                     " exit 124 means wait again"
                     % (running[0]["name"], running[0]["directory"]))
    worktree = Path(state["worktree"])
    if worktree.exists() and git("status", "--porcelain", cwd=worktree,
                                 check=False):
        first.append("the uncommitted changes listed above are the item's"
                     " work in progress: read them against the journal,"
                     " then finish and commit them; a push supersedes a"
                     " gate run still going")
    return "; then ".join(first + [phase_step(state)])


def phase_step(state):
    item = state["item"]
    lost = [entry for entry in state["runs"]
            if run_state(entry["directory"]).startswith("lost")]
    if lost:
        return ("run %s was lost (%s); read its log and start it anew under"
                " another name" % (lost[0]["name"], lost[0]["directory"]))
    phase = state["phase"]
    member = in_batch(state)
    if member:
        return ("a member of batch %s: leave the branch alone, which its"
                " integrator gates and promotes with %s's %s, and fix what"
                " its gate routes here on the batch's branch; once it lands,"
                " `item.py gate %s --main --watch` and `item.py finish %s`"
                % (member["name"], item, member["head"][:12], item, item))
    if is_batch(state):
        if not state["batch"]["members"]:
            return "`item.py batch add %s MEMBER ...`" % item
        if phase == "started":
            return ("push it once (`item.py push %s%s --watch`); route a"
                    " failed job with `item.py batch route %s --run RUN`"
                    % (item, " --boards" if target_of(state) == MAIN
                       else "", item))
        if phase in ("pushed", "gate-passed", "boards-passed"):
            return ("`item.py gate %s` for the batch's runs; a failed job"
                    " goes to its member (`item.py batch route %s --run"
                    " RUN`), fixed on this branch or dropped (`item.py batch"
                    " drop %s MEMBER`); once the gate%s pass, one `%s`"
                    " commit naming the runs in each member's `Done:`, then"
                    " `item.py promote %s`, the maintainer's when a member"
                    " says `Promotion: maintainer`" % (
                        item, item, item, " and the boards" if target_of(
                            state) == MAIN else "", EXPLANATORY, item))
    if phase == "started" and lone_problem(
            state, git("rev-parse", "HEAD", cwd=place(state))):
        return ("continue the work in the worktree; check it with the exact"
                " selectors for what it touches and commit it complete on"
                " its branch, its closing commit included, then report it:"
                " a batch takes it (`item.py batch add BATCH %s`); it does"
                " not push or gate alone" % item)
    if phase == "started":
        return ("continue the work in the worktree; push once its checks pass"
                ", then `item.py gate %s --watch`" % item)
    target = target_of(state)
    if phase in ("pushed", "gate-passed", "boards-passed") and target != MAIN:
        return ("`item.py gate %s` for the head's runs; when the push gate"
                " passed, the closing checklist and `item.py promote %s`,"
                " which lands it on %s, the window's branch, without boards;"
                " if %s has moved, `item.py merge-main %s` first, once"
                % (item, item, target, target, item))
    if phase in ("pushed", "gate-passed", "boards-passed"):
        return ("`item.py gate %s` for the head's runs; once main is the"
                " head's ancestor, its boards beside its gate (`item.py"
                " boards %s`, or `item.py push %s --boards` at the push),"
                " then the closing checklist and `item.py promote %s`; if"
                " main has moved, `item.py merge-main %s` first, once"
                % (item, item, item, item, item))
    if phase == "promoted" and target != MAIN:
        return ("`item.py finish %s`: the candidate's gate passed on the"
                " landed commit; `item.py gate %s --main` shows %s's run on"
                " it" % (item, item, target))
    if phase == "promoted":
        return "`item.py gate %s --main --watch`, then `item.py finish %s`" \
            % (item, item)
    if phase == "main-passed":
        return "`item.py finish %s`, then `item.py report %s`" % (item, item)
    return "`item.py report %s`" % item


def refresh(state):
    """STATE's gate runs not yet ended, as GitHub gives them now; nothing
    when GitHub cannot be asked.  A boards dispatch recorded as queued
    has often ended since."""
    going = sorted({entry["commit"] for entry in state["gates"]
                    if entry.get("status") != "completed"})
    if not going or not shutil.which("gh"):
        return
    try:
        for commit in going:
            record_gates(state, commit)
        save(state)
    except Refused as error:
        print("gate runs of %s not refreshed: %s" % (state["item"], error))


def status(arguments):
    states = ([load(arguments.item)] if arguments.item
              else running_states())
    if not states:
        print("this clone runs no item")
    for state in states:
        refresh(state)
        print("\n".join(describe(state)))
    line = queue_line()
    if line:
        print(line)
    return 0


def resolve_item(arguments):
    item = arguments.item or item_of_branch(Path.cwd())
    if not item:
        raise Refused("name the item: the current branch is no running"
                      " item's")
    return item


def resume(arguments):
    item = resolve_item(arguments)
    state = load(item)
    if state["gates"] and shutil.which("gh"):
        try:
            for commit in sorted({entry["commit"] for entry in state["gates"]}):
                record_gates(state, commit)
            save(state)
        except Refused as error:
            print("gate runs not refreshed: %s" % error)
    print("\n".join(describe(state, full=True)))
    directory = item_directory(item)
    print("  brief %s" % (directory / "brief.md"))
    entries = (directory / "journal.md").read_text(encoding="utf-8") \
        .splitlines() if (directory / "journal.md").exists() else []
    if entries:
        print("journal, last %d of %d:" % (min(15, len(entries)),
                                          len(entries)))
        print("\n".join(entries[-15:]))
    print("next: " + next_step(state))
    return 0


def note(arguments):
    load(arguments.item)
    journal(arguments.item, " ".join(arguments.text))
    return 0


def stalled(arguments):
    found = 0
    for state in running_states():
        if state["phase"] == "finished":
            continue
        idle = (time.time() - last_activity(state)) / 60
        going = [entry["name"] for entry in state["runs"]
                 if run_state(entry["directory"]) == "running"]
        if idle >= arguments.minutes and not going:
            found += 1
            print("STALLED %s: nothing moved for %d min and no run is going;"
                  " %s" % (state["item"], idle, next_step(state)))
        else:
            print("moving %s: last activity %d min ago%s" % (
                state["item"], idle,
                ", running %s" % ", ".join(going) if going else ""))
    return 1 if found else 0


# ------------------------------------------------------------------- report

QUESTION_PART = re.compile(r"^\*\*(Options|Recommendation|Default until"
                           r" answered|What waits on the answer):\*\*\s*(.*)$")


def open_questions(item, worktree):
    """The questions ITEM asked that have no answer, with their parts."""
    found = []
    directory = Path(worktree) / "roadmap" / "questions"
    if not directory.is_dir():
        return found
    for path in sorted(directory.glob("Q-*.md")):
        text = path.read_text(encoding="utf-8")
        if not re.search(r"^Asked by %s on " % re.escape(item), text, re.M) \
                or "**Answer (" in text:
            continue
        heading = text.splitlines()[0].lstrip("# ").strip()
        parts, current = {}, None
        for line in text.splitlines():
            match = QUESTION_PART.match(line)
            if match:
                current = match.group(1)
                parts[current] = match.group(2)
            elif current and line.strip():
                parts[current] += " " + line.strip()
            elif current and not line.strip() and parts[current]:
                current = None
        found.append((heading, parts))
    return found


def report(arguments):
    item = resolve_item(arguments)
    state = load(item)
    worktree = state["worktree"]
    head = git("rev-parse", "--short=12", "HEAD", cwd=worktree, check=False)
    lines = ["RESULT: TODO done | partly done | stopped | failed",
             "  TODO one sentence: what now exists, and where (%s%s)." % (
                 "promoted %s, on %s" % (state["promoted"][:12],
                                         target_of(state))
                 if state.get("promoted") else "branch %s at %s"
                 % (state["branch"], head), ""),
             "", "EVIDENCE:"]
    for entry in state["gates"]:
        lines.append("  run %s, %s gate on %s: %s" % (
            entry["run"], entry["kind"], entry["commit"][:12],
            entry.get("conclusion") or entry.get("status", "")))
    for entry in state["runs"]:
        lines.append("  %s: %s%s, %s (log %s)" % (
            entry["name"], entry["command"],
            "" if entry.get("cwd", state["worktree"]) == state["worktree"]
            else " in " + entry["cwd"], run_state(entry["directory"]),
            Path(entry["directory"]) / "command.log"))
    lines += ["  TODO what each shows; FILTERED or HOST-ONLY where it is.",
              "", "NOT DONE:", "  TODO, or nothing.", "", "STATE:",
              "  state %s; worktree %s (%s); branch %s." % (
                  item_directory(item), worktree,
                  "present" if Path(worktree).exists() else "removed",
                  state["branch"]),
              "  TODO whether the agent can be archived.", "", "FRICTION:",
              "  TODO one line each, rows filed by identity, or None.", "",
              "NEEDS JAN:"]
    questions = open_questions(item, worktree) if Path(worktree).exists() \
        else []
    for heading, parts in questions:
        lines.append("  %s Options: %s Recommendation: %s Default taken: %s"
                     " Waits: %s" % (heading, parts.get("Options", "?"),
                                     parts.get("Recommendation", "?"),
                                     parts.get("Default until answered", "?"),
                                     parts.get("What waits on the answer",
                                               "?")))
    if not questions:
        lines.append("  nothing")
    print("\n".join(lines))
    return 0


# --------------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n\n".join(__doc__.split("\n\n")[1:]))
    parser.add_argument("--repo", default=str(ROOT), help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command_name", required=True)

    sub = commands.add_parser("start", help="make the worktree, branch,"
                              " brief and reservations; mark the item active")
    sub.add_argument("item")
    sub.add_argument("--base", help="the starting commit (origin/main, or"
                     " the integration branch of the item's breaking"
                     " window)")
    sub.add_argument("--branch", help="the branch (the item, as r19-10)")
    sub.add_argument("--worktree", help="the worktree (Landin-ITEM beside"
                     " the clone's main checkout)")
    sub.add_argument("--adopt", metavar="WORKTREE", help="take on an existing"
                     " worktree and its branch instead of making them")
    sub.add_argument("--force", action="store_true",
                     help="start although a dependency is not complete")
    sub.add_argument("--work", metavar="TEXT", help="work that is no item,"
                     " named ITEM, as nix-packages-4, and said in TEXT: its"
                     " state, reservations, push, gate, boards, promotion"
                     " and finish as an item's, without a roadmap entry")
    sub.add_argument("--no-commit", action="store_true",
                     help="leave the status and pointers as they are")
    sub.add_argument("--no-fetch", action="store_true", help=argparse.SUPPRESS)
    sub.set_defaults(handler=start)

    for name, handler, text in (
            ("resume", resume, "what a reopened session needs: state, live"
             " runs, journal and the next step"),
            ("report", report, "draft the report in the skill's form")):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("item", nargs="?")
        sub.set_defaults(handler=handler)

    sub = commands.add_parser("status", help="every item this clone runs")
    sub.add_argument("item", nargs="?")
    sub.set_defaults(handler=status)

    sub = commands.add_parser("note", help="add a line to the journal")
    sub.add_argument("item")
    sub.add_argument("text", nargs="+")
    sub.set_defaults(handler=note)

    sub = commands.add_parser("run", help="a detached run_logged run kept in"
                              " the item's state")
    sub.add_argument("item")
    sub.add_argument("name")
    sub.add_argument("--limit", type=int, required=True,
                     help="seconds after which the run is ended")
    sub.add_argument("--cwd", metavar="DIR", help="the directory the command"
                     " runs in, such as a stream's worktree (the item's"
                     " worktree)")
    sub.set_defaults(handler=run)

    sub = commands.add_parser("push", help="refuse stale citations, push the"
                              " head, record its gate runs")
    sub.add_argument("item")
    sub.add_argument("--watch", action="store_true", help="follow the gate"
                     " in two detached gate_watch.py runs: one returning at"
                     " the first failed job, one with --all to its end")
    sub.add_argument("--boards", action="store_true", help="dispatch the"
                     " boards on the pushed head beside its gate; main must"
                     " be its ancestor")
    sub.add_argument("--no-check", action="store_true", help="push without"
                     " the pre-push checks the changed paths select")
    sub.set_defaults(handler=push)

    sub = commands.add_parser("merge-main", help="take the promotion token,"
                              " merge origin/main, or the window's"
                              " integration branch for a window's item, and"
                              " declare the merge explanatory when the reuse"
                              " rule allows it")
    sub.add_argument("item")
    sub.add_argument("--branch", metavar="BRANCH", help="merge this branch"
                     " instead of the one the item lands on, such as a"
                     " breaking window's integration branch a continuous"
                     " item also lands on; takes no promotion token")
    sub.add_argument("--no-queue", action="store_true", help="a merge to"
                     " pick up main while work goes on, without the token;"
                     " the final merge still takes it")
    sub.set_defaults(handler=merge_main)

    sub = commands.add_parser("batch", help="form, list, add a member to,"
                              " drop one from, or route a failed job of a"
                              " batch: one gate and boards for its members")
    sub.add_argument("action", choices=("form", "add", "drop", "route",
                                        "list"))
    sub.add_argument("name", nargs="?", help="the batch, as batch-2")
    sub.add_argument("members", nargs="*", metavar="MEMBER", help="with add"
                     " or drop, items of this clone or branches that are no"
                     " item's; with route, the failed jobs' names")
    sub.add_argument("--integrator", default="the session that runs the"
                     " roadmap", help="with form, who merges, pushes and"
                     " follows it")
    sub.add_argument("--target", metavar="BRANCH", help="with form, main"
                     " (the default) or a phase's window branch")
    sub.add_argument("--worktree", help="with form, its worktree"
                     " (Landin-NAME beside the clone's main checkout)")
    sub.add_argument("--run", type=int, help="with route, the gate run"
                     " whose failed jobs to route")
    sub.set_defaults(handler=batch)

    sub = commands.add_parser("queue", help="the promotion token's holder"
                              " and line")
    which = sub.add_mutually_exclusive_group()
    which.add_argument("--wait", metavar="NAME", help="return 0 once the"
                       " item, or with --why the work that is no item, NAME"
                       " holds the token, taking it in its turn; 124 at the"
                       " timeout")
    which.add_argument("--release", metavar="ITEM", help="give up ITEM's"
                       " token or place in line")
    which.add_argument("--take", metavar="NAME", help="take the token for"
                       " work that is no item, such as a register sweep,"
                       " until `--release NAME`; exit 1 when it is held,"
                       " with NAME put in line: `--wait NAME --why TEXT`")
    sub.add_argument("--why", help="with --take or a --wait that is no item,"
                     " what the token is for")
    sub.add_argument("--target", metavar="BRANCH", help="the queue of this"
                     " branch: main, or a window's integration branch"
                     " (the item's own, else main)")
    sub.add_argument("--timeout", type=float, default=270)
    sub.set_defaults(handler=queue)

    sub = commands.add_parser("gate", help="record and show the gate runs of"
                              " the pushed head, or of main after promotion")
    sub.add_argument("item")
    sub.add_argument("--main", action="store_true",
                     help="the push gate on the promoted commit of main,"
                     " or of the window's branch it landed on")
    sub.add_argument("--watch", action="store_true", help="follow it to its"
                     " end in a detached gate_watch.py --all run")
    sub.set_defaults(handler=gate)

    sub = commands.add_parser("boards", help="dispatch scope=boards on the"
                              " pushed head")
    sub.add_argument("item")
    sub.add_argument("--watch", action="store_true", help="follow it to its"
                     " end in a detached gate_watch.py --all run")
    sub.add_argument("--unmerged", action="store_true", help="dispatch"
                     " although main is not an ancestor of the head")
    sub.add_argument("--rerun-failed", action="store_true", help="re-run"
                     " only the failed jobs of the head's boards run that"
                     " failed in timing alone")
    sub.add_argument("--again", action="store_true", help="dispatch although"
                     " the head has a boards run queued, running or passed,"
                     " which is otherwise followed")
    sub.set_defaults(handler=boards)

    sub = commands.add_parser("promote", help="check the evidence and push"
                              " the head to main, or land a window's item on"
                              " its integration branch")
    sub.add_argument("item")
    sub.add_argument("--partial", action="store_true", help="promote work"
                     " short of the item's close")
    sub.add_argument("--dry-run", action="store_true")
    sub.add_argument("--maintainer", action="store_true", help="the"
                     " maintainer's own promotion of an item or a batch"
                     " that says `Promotion: maintainer`; never an agent's")
    sub.set_defaults(handler=promote)

    sub = commands.add_parser("finish", help="after main's gate, or once a"
                              " window's item landed: remove the worktree"
                              " and branches, keep the state")
    sub.add_argument("item")
    sub.add_argument("--unpromoted", action="store_true",
                     help="clean up an item that was never promoted")
    sub.set_defaults(handler=finish)

    sub = commands.add_parser("stalled", help="the running items nothing has"
                              " moved; exit 1 when there is one")
    sub.add_argument("--minutes", type=int, default=STALL_MINUTES)
    sub.set_defaults(handler=stalled)

    #  A run's command follows the first `--` and is never parsed here:
    #  argparse's handling of `--` before a subcommand's positionals
    #  differs between Python versions, and 3.12 refused this form.
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:
        command = argv[argv.index("--") + 1:]
        argv = argv[:argv.index("--")]
    arguments = parser.parse_args(argv)
    arguments.command = command
    REPOSITORY[0] = Path(arguments.repo)
    try:
        return arguments.handler(arguments)
    except Refused as error:
        print("item.py: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
