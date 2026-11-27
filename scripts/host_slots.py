#!/usr/bin/env python3
"""A host-wide limit on heavy jobs: a few slots every checkout shares.

A host that many agents share ran out of memory on 2026-11-27 when each of
them built the compiler and ran complete suites at once, and the kernel's
kill took the agents' service with every run under it.  So a heavy job
takes one of a small number of slots first: a compiler build or test run
(`build.sh`, `test.sh` and the other scripts that take a build lock in
`mode` scope, the developer wrappers among them), a `run_logged.py` run,
and the determinism manifests and measurements (`emit_manifest.py emit`
and `modes`, `measure.py size`, `instructions` and `time`).

The slots are files in one directory outside every worktree, so every
worktree and clone of the host counts against the same number:
`$LANDIN_HEAVY_JOBS_DIR`, or `$XDG_STATE_HOME/landin/heavy-jobs`, which is
`~/.local/state/landin/heavy-jobs` by default.  A slot is a `flock` on
`slot-N`; the kernel gives it up when its last holder exits, so a killed
job frees its slot.  The number of slots is the host's setting: the
number in the directory's file `slots`, written once by whoever runs the
host (`host_slots.py --set N`), and 2 without it.  `$LANDIN_HEAVY_JOBS`
overrides it for one command, and 0 there takes no slot, for a host or a
test that runs one job at a time anyway.

A job that finds every slot taken waits, says so once on standard error
with every holder's process, working directory and command, says so
again when the holders change, and starts when a slot is freed.  A job
started by a job that holds a slot -- the test program's build inside
`dev-test.sh`, a suite inside `run_logged.py` -- runs in its caller's slot:
the holder's pid is in `$LANDIN_HEAVY_SLOT`, which its children inherit.

    python3 scripts/host_slots.py                   who holds the slots
    python3 scripts/host_slots.py --set N           the host's number
    python3 scripts/host_slots.py -- COMMAND ...    run COMMAND in a slot
"""
import atexit
import fcntl
import os
from pathlib import Path
import sys
import time


DEFAULT_SLOTS = 2
#  The pid of the process holding the slot this process tree runs in.
HELD = "LANDIN_HEAVY_SLOT"
COUNT = "LANDIN_HEAVY_JOBS"
DIRECTORY = "LANDIN_HEAVY_JOBS_DIR"
#  Seconds between looks while every slot is taken.
POLL = 1.0

_held = []


def directory():
    given = os.environ.get(DIRECTORY)
    if given:
        return Path(given)
    state = os.environ.get("XDG_STATE_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "state")
    return Path(state) / "landin" / "heavy-jobs"


def count(where=None):
    """The number of slots: $LANDIN_HEAVY_JOBS, the host's file, or 2."""
    given = os.environ.get(COUNT, "").strip()
    if given:
        if not given.isdigit():
            raise ValueError("%s=%s is not a number of slots" % (COUNT, given))
        return int(given)
    try:
        text = ((where or directory()) / "slots").read_text().strip()
    except OSError:
        return DEFAULT_SLOTS
    if not text.isdigit() or int(text) < 1:
        raise ValueError("%s holds %r, not a number of slots of at least 1"
                         % ((where or directory()) / "slots", text))
    return int(text)


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _record_path(where, pid):
    return where / ("holder-%d" % pid)


def holders(where=None):
    """(slot, pid, text) for every live recorded holder, by slot."""
    where = where or directory()
    found = []
    try:
        entries = sorted(where.glob("holder-*"))
    except OSError:
        return found
    for entry in entries:
        pid = entry.name.partition("-")[2]
        if not pid.isdigit():
            continue
        try:
            slot, _, text = entry.read_text().partition("\n")
        except OSError:
            continue
        if not _alive(int(pid)):
            try:
                entry.unlink()
            except OSError:
                pass
            continue
        found.append((slot, int(pid), text.strip()))
    return sorted(found)


def _inherited(where):
    """Whether this process runs inside a job that holds a slot."""
    held = os.environ.get(HELD, "")
    if not held.isdigit():
        return False
    pid = int(held)
    return pid == os.getpid() or (
        _alive(pid) and _record_path(where, pid).exists())


def _forget(where):
    try:
        _record_path(where, os.getpid()).unlink()
    except OSError:
        pass


def describe(found):
    return "; ".join("%s: pid %d, %s" % (slot, pid, text.replace("\n", ", "))
                     for slot, pid, text in found) or "no holder is recorded"


def hold(command=None, say=None, give_up=None):
    """Take a slot for this process and its children, waiting for one.

    Returns the slot's name, or None when none is needed: the limit is
    off, a caller already holds one, or GIVE_UP said so while it waited.
    The slot is held until the process exits; a program it execs keeps it.
    """
    where = directory()
    if _inherited(where):
        return None
    slots = count(where)
    if slots == 0:
        return None
    say = say or (lambda text: print(text, file=sys.stderr, flush=True))
    try:
        where.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        say("landin: no heavy-job slot taken: %s cannot be made: %s"
            % (where, error))
        return None
    command = command or " ".join(sys.argv)
    shown = None
    while True:
        for number in range(slots):
            name = "slot-%d" % number
            fd = os.open(where / name, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                continue
            os.set_inheritable(fd, True)
            _held.append(fd)
            _record_path(where, os.getpid()).write_text(
                "%s\nin %s: %s\n" % (name, os.getcwd(), command))
            os.environ[HELD] = str(os.getpid())
            atexit.register(_forget, where)
            if shown is not None:
                say("landin: took heavy-job %s" % name)
            return name
        found = holders(where)
        if found != shown:
            say("landin: waiting for one of the host's %d heavy-job slots"
                " (%s; the number is %s), held by %s"
                % (slots, where, "$%s" % COUNT if os.environ.get(COUNT)
                   else "the file slots there" if (where / "slots").exists()
                   else "the default", describe(found)))
            shown = found
        if give_up is not None and give_up():
            return None
        time.sleep(POLL)


def main(arguments):
    if arguments[:1] == ["--set"] and len(arguments) == 2:
        if not arguments[1].isdigit() or int(arguments[1]) < 1:
            raise ValueError("--set needs a number of slots of at least 1")
        where = directory()
        where.mkdir(parents=True, exist_ok=True)
        (where / "slots").write_text(arguments[1] + "\n")
        print("%s: %s slots" % (where, arguments[1]))
        return 0
    if arguments[:1] == ["--"] and len(arguments) > 1:
        hold(" ".join(arguments[1:]))
        os.execvp(arguments[1], arguments[1:])
    if arguments:
        print(__doc__.rsplit("\n\n", 1)[1], file=sys.stderr)
        return 2
    where = directory()
    print("%s: %d slots" % (where, count(where)))
    for slot, pid, text in holders(where):
        print("%s: pid %d, %s" % (slot, pid, text.replace("\n", ", ")))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (OSError, ValueError) as error:
        print("landin: heavy-job slots: %s" % error, file=sys.stderr)
        sys.exit(2)
