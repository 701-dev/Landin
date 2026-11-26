#!/usr/bin/env python3
"""Controls for scripts/item.py, which runs a roadmap item's mechanical steps.

Each case builds a clone with a remote, a ROADMAP.md of invented items and
the pointer files, and runs the script against it.  GitHub is never asked:
the gate cases give the state the runs a listing would have produced.  The
items' identities are built at run time, so this file names none.
"""
import contextlib
import io
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import item  # noqa: E402
import register_next  # noqa: E402
from temporary_git import environment  # noqa: E402

FIRST = "R%d.%d" % (0, 10)
SECOND = "R%d.%d" % (0, 20)
THIRD = "R%d.%d" % (0, 30)
ROADMAP = """\
# Roadmap

## R0 — A phase

### {first} — The first

Status: planned
Depends on: none

Exit evidence: x.

### {second} — The second

Status: planned
Depends on: none
Promotion: maintainer

Exit evidence: x.

### {third} — The third

Status: planned
Depends on: {first}

Exit evidence: x.
""".format(first=FIRST, second=SECOND, third=THIRD)
POINTER = "**Next roadmap item: %s — The first (planned).**\n" % FIRST


def git(root, *arguments):
    return subprocess.run(["git", *arguments], cwd=root, check=True,
                          env=environment(), text=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout.strip()


class Clone(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.top = Path(self.scratch.name)
        self.origin = self.top / "origin.git"
        self.clone = self.top / "Landin"
        git(self.top, "init", "-q", "--bare", "-b", "main", str(self.origin))
        git(self.top, "init", "-q", "-b", "main", str(self.clone))
        (self.clone / "ROADMAP.md").write_text(ROADMAP)
        (self.clone / "README.md").write_text(POINTER)
        (self.clone / "handoff.md").write_text(POINTER)
        (self.clone / "spec.md").write_text("D41 and D42 are decisions.\n")
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", "base")
        git(self.clone, "remote", "add", "origin", str(self.origin))
        git(self.clone, "push", "-q", "origin", "main")
        git(self.clone, "fetch", "-q", "origin")
        #  A main run's verdict is read from GitHub's job listing, which
        #  these cases never ask for.
        self.saved_verdict = item.verdict_of
        item.verdict_of = lambda run: None

    def tearDown(self):
        item.verdict_of = self.saved_verdict
        item.REPOSITORY[0] = item.ROOT
        self.scratch.cleanup()

    def item(self, *arguments):
        out, err = io.StringIO(), io.StringIO()
        if arguments[:1] != ("--repo",):
            arguments = ("--repo", str(self.clone)) + arguments
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                _environment(), _directory():
            status = item.main(list(arguments))
        item.REPOSITORY[0] = self.clone
        return status, out.getvalue() + err.getvalue()


@contextlib.contextmanager
def _directory():
    """The test's working directory back, whatever the script chdir'd to."""
    import os
    saved = os.getcwd()
    try:
        yield
    finally:
        os.chdir(saved)


@contextlib.contextmanager
def _environment():
    """Git's settings for a temporary repository, for the script's own git."""
    import os
    saved = dict(os.environ)
    os.environ.update(environment())
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


class Start(Clone):
    def test_start_makes_the_worktree_state_brief_and_active_status(self):
        status, out = self.item("start", FIRST)
        self.assertEqual(status, 0, out)
        worktree = self.top / ("Landin-" + item.slug(FIRST))
        self.assertTrue(worktree.is_dir())
        self.assertEqual(git(worktree, "rev-parse", "--abbrev-ref", "HEAD"),
                         item.slug(FIRST))
        self.assertIn("### %s — The first\n\nStatus: active\n" % FIRST,
                      (worktree / "ROADMAP.md").read_text())
        for name in item.POINTER_FILES:
            self.assertEqual((worktree / name).read_text(),
                             "**Current roadmap work: %s — The first.**\n"
                             % FIRST)
        self.assertIn(item.EXPLANATORY, git(worktree, "log", "-1",
                                            "--format=%B"))
        state = item.load(FIRST)
        self.assertEqual(state["phase"], "started")
        #  Past the specification's last decision and the second
        #  roadmap's last row.
        self.assertEqual(state["reserved"]["D"][0], 43)
        self.assertEqual(state["reserved"]["SR"][0],
                         register_next.SECOND_ROADMAP_LAST + 1)
        brief = (item.item_directory(FIRST) / "brief.md").read_text()
        self.assertIn(str(worktree), brief)
        self.assertIn("item.py resume %s" % FIRST, brief)
        self.assertIn("Authority paragraph", brief)
        #  The brief rules of docs/process.md: selectors, workers, the
        #  environment and the wait.
        for rule in ("exact `dev-test.sh` selectors", "no `-j` or `taskset`",
                     "agent_env.sh", "run_logged.py --wait"):
            self.assertIn(rule, brief)

    def test_start_from_another_worktree_places_it_beside_the_main_one(self):
        elsewhere = self.top / "elsewhere" / "checkout"
        git(self.clone, "worktree", "add", "-q", "--detach", str(elsewhere))
        status, out = self.item("--repo", str(elsewhere), "start", FIRST)
        self.assertEqual(status, 0, out)
        worktree = self.top / ("Landin-" + item.slug(FIRST))
        self.assertTrue(worktree.is_dir(), out)
        self.assertIn(str(worktree.resolve()), out)

    def test_two_items_reserve_apart_and_register_next_honours_them(self):
        self.assertEqual(self.item("start", FIRST)[0], 0)
        self.assertEqual(self.item("start", SECOND)[0], 0)
        first, second = item.load(FIRST), item.load(SECOND)
        for kind in item.BLOCKS:
            self.assertLess(first["reserved"][kind][1],
                            second["reserved"][kind][0])
        #  From the second item's worktree, its own block comes first.
        worktree = Path(second["worktree"])
        self.assertEqual(register_next.allocate(worktree, 1),
                         ["SR-%d" % second["reserved"]["SR"][0]])
        #  From the main checkout, past both.
        self.assertEqual(register_next.allocate(self.clone, 1),
                         ["SR-%d" % (second["reserved"]["SR"][1] + 1)])
        brief = (item.item_directory(SECOND) / "brief.md").read_text()
        self.assertIn("Promotion: maintainer", brief)
        self.assertIn(FIRST + " on branch", brief)

    def test_an_unmet_dependency_refuses(self):
        status, out = self.item("start", THIRD)
        self.assertEqual(status, 2)
        self.assertIn("depends on %s" % FIRST, out)
        self.assertFalse((self.top / ("Landin-" + item.slug(THIRD))).exists())

    def test_starting_twice_refuses(self):
        self.item("start", FIRST)
        status, out = self.item("start", FIRST)
        self.assertEqual(status, 2)
        self.assertIn("already running", out)

    def test_adopt_takes_an_existing_worktree(self):
        worktree = self.top / "elsewhere"
        git(self.clone, "worktree", "add", "-q", "-b", "mine", str(worktree),
            "origin/main")
        status, out = self.item("start", FIRST, "--adopt", str(worktree))
        self.assertEqual(status, 0, out)
        self.assertEqual(item.load(FIRST)["branch"], "mine")


class Resume(Clone):
    def test_resume_reads_the_state_a_new_session_needs(self):
        self.item("start", FIRST)
        self.item("note", FIRST, "halfway", "through")
        worktree = Path(item.load(FIRST)["worktree"])
        (worktree / "new.txt").write_text("x")
        status, out = self.item("resume", FIRST)
        self.assertEqual(status, 0, out)
        self.assertIn("uncommitted changes", out)
        self.assertIn("halfway through", out)
        self.assertIn("next: the uncommitted changes listed above", out)
        self.assertIn("then continue the work", out)

    def test_a_running_run_is_the_next_step_and_a_lost_one_is_named(self):
        self.item("start", FIRST)
        state = item.load(FIRST)
        going = item.item_directory(FIRST) / "runs" / "suite"
        going.mkdir(parents=True)
        (going / "running.json").write_text(json.dumps({"pid": 1}))
        state["runs"].append({"name": "suite", "directory": str(going),
                              "command": "x", "started": item.stamp()})
        item.save(state)
        step = item.next_step(item.load(FIRST))
        self.assertIn("wait for run suite", step)
        self.assertIn("; then continue the work", step)
        (going / "result.json").write_text(json.dumps({"exit_status": 0}))
        self.assertEqual(item.run_state(going), "finished, exit 0")

    def test_stalled_names_an_item_nothing_moved(self):
        self.item("start", FIRST)
        status, out = self.item("stalled", "--minutes", "0")
        self.assertEqual(status, 1)
        self.assertIn("STALLED " + FIRST, out)
        status, out = self.item("stalled", "--minutes", "600")
        self.assertEqual(status, 0)
        self.assertIn("moving " + FIRST, out)

    def test_report_ends_with_the_open_questions_and_their_defaults(self):
        self.item("start", FIRST)
        worktree = Path(item.load(FIRST)["worktree"])
        questions = worktree / "roadmap" / "questions"
        questions.mkdir(parents=True)
        (questions / "Q-0.md").write_text(
            "# Q-0 — Which?\n\nAsked by %s on 2026-01-01.\n\nWhy.\n\n"
            "**Options:**\n\n1. this\n2. that\n\n**Recommendation:** this\n\n"
            "**Default until answered:** this one\n\n"
            "**What waits on the answer:** nothing\n" % FIRST)
        status, out = self.item("report", FIRST)
        self.assertEqual(status, 0, out)
        tail = out.split("NEEDS JAN:")[1]
        self.assertIn("Default taken: this one", tail)
        self.assertEqual(out.rstrip().splitlines()[-2], "NEEDS JAN:")


class Promote(Clone):
    def setUp(self):
        super().setUp()
        self.item("start", FIRST)
        self.state = item.load(FIRST)
        self.worktree = Path(self.state["worktree"])

    def commit(self, message):
        (self.worktree / "work.txt").write_text(message)
        git(self.worktree, "add", "-A")
        git(self.worktree, "commit", "-q", "-m", message)
        return git(self.worktree, "rev-parse", "HEAD")

    def gate(self, commit, kind):
        return {"run": len(self.state["gates"]) + 1, "commit": commit,
                "tree": git(self.worktree, "rev-parse", commit + "^{tree}"),
                "kind": kind, "status": "completed", "conclusion": "success"}

    def problems(self, commit):
        saved = item.complete_listing
        item.complete_listing = lambda run: None
        try:
            return item.evidence(self.state, commit)
        finally:
            item.complete_listing = saved

    def test_without_runs_both_passes_are_missing(self):
        head = self.commit("work")
        problems = self.problems(head)
        self.assertEqual(len(problems), 2, problems)

    def test_boards_on_the_same_tree_suffice(self):
        head = self.commit("work")
        self.state["gates"] += [self.gate(head, "software"),
                                self.gate(head, "boards")]
        self.assertEqual(self.problems(head), [])

    def test_an_explanatory_close_keeps_the_earlier_boards(self):
        work = self.commit("work")
        self.state["gates"].append(self.gate(work, "boards"))
        close = self.commit("Close\n\n" + item.EXPLANATORY)
        self.state["gates"].append(self.gate(close, "software"))
        self.assertEqual(self.problems(close), [])
        later = self.commit("more work")
        self.state["gates"].append(self.gate(later, "software"))
        self.assertEqual(len(self.problems(later)), 1)

    def test_a_mention_of_the_declaration_is_not_one(self):
        work = self.commit("work")
        self.state["gates"].append(self.gate(work, "boards"))
        mention = self.commit("Say why `%s` is written" % item.EXPLANATORY)
        self.state["gates"].append(self.gate(mention, "software"))
        problems = self.problems(mention)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("no passed boards dispatch", problems[0])

    def test_a_boards_run_still_going_is_named_not_dispatched_again(self):
        head = self.commit("work")
        going = dict(self.gate(head, "boards"), status="in_progress",
                     conclusion="")
        self.state["gates"] += [self.gate(head, "software"), going]
        problems = self.problems(head)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("has not finished", problems[0])

    def test_run_takes_its_options_before_the_command(self):
        status, out = self.item("run", FIRST, "echo", "--limit", "60", "--",
                                sys.executable, "-c", "print('ran')",
                                "--limit")
        self.assertEqual(status, 0, out)
        directory = item.item_directory(FIRST) / "runs" / "echo"
        waited = subprocess.run(
            [sys.executable, str(item.ROOT / "scripts/run_logged.py"),
             "--wait", str(directory), "--timeout", "60"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(waited.returncode, 0, waited.stdout)
        self.assertIn("ran", (directory / "command.log").read_text())
        self.assertEqual(item.load(FIRST)["runs"][0]["command"],
                         shlex.join([sys.executable, "-c", "print('ran')",
                                     "--limit"]))

    def test_a_rerun_of_the_same_commit_is_watched_afresh(self):
        #  The watch is named by the run and its attempt: a finished watch
        #  of attempt 1 does not answer for attempt 2 of the same commit.
        head = self.commit("work")
        git(self.worktree, "push", "-q", "origin", self.state["branch"])
        listing = [{"databaseId": 5, "event": "push",
                    "headBranch": self.state["branch"], "status": "completed",
                    "conclusion": "failure", "displayTitle": "x",
                    "attempt": 1}]
        started = []

        def run(arguments):
            directory = item.item_directory(FIRST) / "runs" / arguments.name
            directory.mkdir(parents=True)
            (directory / "result.json").write_text('{"exit_status": 1}')
            started.append((arguments.name, arguments.command[-2:]))
            return 0

        saved = item.runs_of, item.run
        item.runs_of, item.run = (lambda commit: listing), run
        try:
            self.item("gate", FIRST, "--watch")
            status, out = self.item("gate", FIRST, "--watch")
            self.assertIn("already watched", out)
            listing[0].update(attempt=2, status="in_progress", conclusion="")
            status, out = self.item("gate", FIRST, "--watch")
        finally:
            item.runs_of, item.run = saved
        self.assertEqual(status, 0, out)
        prefix = "gate-branch-%s-run5-attempt" % head[:12]
        #  Each attempt is watched twice: to its first failed job, which
        #  wakes the agent, and with --all to its end.
        self.assertEqual(started, [(prefix + "1-first", ["--run", "5"]),
                                   (prefix + "1", ["--run", "5"]),
                                   (prefix + "2-first", ["--run", "5"]),
                                   (prefix + "2", ["--run", "5"])])

    def test_run_in_another_directory_is_kept_and_reported(self):
        elsewhere = self.top / "stream"
        elsewhere.mkdir()
        status, out = self.item("run", FIRST, "where", "--limit", "60",
                                "--cwd", str(elsewhere), "--",
                                sys.executable, "-c",
                                "import os; print(os.getcwd())")
        self.assertEqual(status, 0, out)
        directory = item.item_directory(FIRST) / "runs" / "where"
        subprocess.run([sys.executable,
                        str(item.ROOT / "scripts/run_logged.py"),
                        "--wait", str(directory), "--timeout", "60"],
                       check=True, stdout=subprocess.DEVNULL)
        self.assertIn(str(elsewhere.resolve()),
                      (directory / "command.log").read_text())
        self.assertEqual(item.load(FIRST)["runs"][0]["cwd"],
                         str(elsewhere.resolve()))
        status, out = self.item("resume", FIRST)
        self.assertIn("in %s" % elsewhere.resolve(), out)

    def test_passed_runs_move_the_phase_on(self):
        head = self.commit("work")
        self.state["gates"].append(self.gate(head, "software"))
        item.advance(self.state, head)
        self.assertEqual(self.state["phase"], "gate-passed")
        self.state["gates"].append(self.gate(head, "boards"))
        item.advance(self.state, head)
        self.assertEqual(self.state["phase"], "boards-passed")
        self.assertIn("promote", item.phase_step(self.state))

    def test_a_maintainer_item_is_not_promoted(self):
        self.item("start", SECOND)
        status, out = self.item("promote", SECOND)
        self.assertEqual(status, 2)
        self.assertIn("Promotion: maintainer", out)

    def test_finish_from_the_items_own_worktree(self):
        #  As an item's agent runs it: the script's checkout is the one
        #  it removes.
        status, out = self.item("--repo", str(self.worktree), "finish",
                                FIRST, "--unpromoted")
        self.assertEqual(status, 0, out)
        self.assertFalse(self.worktree.exists())
        self.assertEqual(git(self.clone, "branch", "--list",
                             self.state["branch"]), "")

    def test_finish_when_the_worktree_is_already_gone(self):
        self.state["promoted"] = git(self.clone, "rev-parse", "HEAD")
        self.state["gates"].append(
            self.gate(self.state["promoted"], "main"))
        item.save(self.state)
        git(self.clone, "worktree", "remove", str(self.worktree))
        saved = item.record_gates
        item.record_gates = lambda state, commit: (
            item.place(state), state)[1]
        try:
            status, out = self.item("finish", FIRST)
        finally:
            item.record_gates = saved
        self.assertEqual(status, 0, out)
        self.assertTrue((item.state_root() / item.DONE_DIRECTORY
                         / FIRST).is_dir())

    def test_finish_unpromoted_removes_worktree_and_branch(self):
        status, out = self.item("finish", FIRST)
        self.assertEqual(status, 2)
        self.assertIn("not promoted", out)
        status, out = self.item("finish", FIRST, "--unpromoted")
        self.assertEqual(status, 0, out)
        self.assertFalse(self.worktree.exists())
        self.assertEqual(git(self.clone, "branch", "--list",
                             self.state["branch"]), "")
        self.assertTrue((item.state_root() / item.DONE_DIRECTORY / FIRST
                         / "journal.md").exists())
        status, out = self.item("resume", FIRST)
        self.assertIn("is finished", out)


class Queue(Clone):
    """The promotion token: one holder, the others in line, in order."""

    def setUp(self):
        super().setUp()
        self.item("start", FIRST)
        self.item("start", SECOND)
        item.REPOSITORY[0] = self.clone

    def test_one_holder_and_a_line(self):
        self.assertEqual(item.take(FIRST, "test"), (True, None))
        taken, why = item.take(SECOND, "test")
        self.assertFalse(taken)
        self.assertIn("%s holds the promotion token" % FIRST, why)
        self.assertIn("queue --wait %s" % SECOND, why)
        status, out = self.item("status")
        self.assertIn("promotion token: %s since" % FIRST, out)
        self.assertIn("waiting: %s" % SECOND, out)
        self.assertTrue(item.release(FIRST, "test"))
        self.assertEqual(item.take(SECOND, "test"), (True, None))

    def test_the_line_keeps_its_order(self):
        self.item("start", THIRD, "--force")
        item.REPOSITORY[0] = self.clone
        item.take(FIRST, "test")
        item.take(SECOND, "test")
        item.release(FIRST, "test")
        taken, why = item.take(THIRD, "test")
        self.assertFalse(taken)
        self.assertIn("%s waits for the promotion token before %s"
                      % (SECOND, THIRD), why)
        self.assertEqual(item.take(SECOND, "test"), (True, None))

    def test_a_holder_this_clone_no_longer_runs_holds_nothing(self):
        item.take(FIRST, "test")
        status, out = self.item("finish", FIRST, "--unpromoted")
        self.assertEqual(status, 0, out)
        item.REPOSITORY[0] = self.clone
        self.assertEqual(item.take(SECOND, "test"), (True, None))

    def test_a_holder_whose_main_gate_ended_holds_nothing(self):
        item.take(FIRST, "test")
        asked = []
        saved = item.main_gate_ended
        item.main_gate_ended = lambda held, commit: asked.append(
            (held, commit)) or held == FIRST
        try:
            #  Not promoted under this hold: an earlier promotion's ended
            #  gate does not end it.
            self.assertFalse(item.take(SECOND, "test")[0])
            self.assertEqual(asked, [])
            item.mark_promoted(FIRST, "c0ffee")
            self.assertFalse(item.take(SECOND, "test", ask=False)[0])
            self.assertEqual(item.take(SECOND, "test"), (True, None))
            self.assertEqual(asked, [(FIRST, "c0ffee")])
        finally:
            item.main_gate_ended = saved

    def test_wait_returns_once_the_token_is_the_items(self):
        item.take(FIRST, "test")
        status, out = self.item("queue", "--wait", SECOND, "--timeout", "0")
        self.assertEqual(status, 124, out)
        self.assertIn("holds the promotion token", out)
        item.release(FIRST, "test")
        status, out = self.item("queue", "--wait", SECOND, "--timeout", "0")
        self.assertEqual(status, 0, out)
        status, out = self.item("queue")
        self.assertIn("promotion token: %s since" % SECOND, out)
        status, out = self.item("queue", "--release", SECOND)
        self.assertIn("released", out)


class MergeMain(Clone):
    """`merge-main` declares a merge explanatory only when reuse allows."""

    def setUp(self):
        super().setUp()
        self.item("start", FIRST)
        self.state = item.load(FIRST)
        self.worktree = Path(self.state["worktree"])
        (self.worktree / "work.txt").write_text("work\n")
        git(self.worktree, "add", "-A")
        git(self.worktree, "commit", "-q", "-m", "work")

    def on_main(self, path, text, message):
        target = self.clone / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", message)
        git(self.clone, "push", "-q", "origin", "main")
        return git(self.clone, "rev-parse", "HEAD")

    def merged_message(self):
        return git(self.worktree, "log", "-1", "--format=%B")

    def test_an_explanatory_main_makes_an_explanatory_merge(self):
        self.on_main("roadmap/questions/Q-0.md", "a question\n",
                     "Ask\n\n" + item.EXPLANATORY)
        status, out = self.item("merge-main", FIRST)
        self.assertEqual(status, 0, out)
        self.assertIn(item.EXPLANATORY, self.merged_message())
        self.assertIn("reuses the candidate's pass", out)
        self.assertEqual(len(git(self.worktree, "log", "-1",
                                 "--format=%P").split()), 2)
        self.assertEqual(item.take(FIRST, "again"), (True, None))
        status, out = self.item("merge-main", FIRST)
        self.assertIn("nothing to merge", out)

    def test_an_undeclared_commit_makes_a_new_tree(self):
        brought = self.on_main("roadmap/questions/Q-0.md", "a question\n",
                               "Ask")
        status, out = self.item("merge-main", FIRST)
        self.assertEqual(status, 0, out)
        self.assertNotIn(item.EXPLANATORY, self.merged_message())
        self.assertIn("commits from main without", out)
        self.assertIn(brought[:12], out)

    def test_a_declared_change_outside_the_set_makes_a_new_tree(self):
        self.on_main("spec.md", "D41 changed.\n",
                     "Change\n\n" + item.EXPLANATORY)
        status, out = self.item("merge-main", FIRST)
        self.assertEqual(status, 0, out)
        self.assertNotIn(item.EXPLANATORY, self.merged_message())
        self.assertIn("paths outside the explanatory set differ: spec.md",
                      out)

    def test_a_conflict_stops_and_keeps_the_token(self):
        self.on_main("work.txt", "other\n", "Clash\n\n" + item.EXPLANATORY)
        status, out = self.item("merge-main", FIRST)
        self.assertEqual(status, 2, out)
        self.assertIn("conflicts in work.txt", out)
        item.REPOSITORY[0] = self.clone
        self.assertFalse(item.take(SECOND, "test")[0])
        git(self.worktree, "merge", "--abort")

    def test_a_held_token_refuses_the_merge(self):
        self.item("start", SECOND)
        item.REPOSITORY[0] = self.clone
        item.take(SECOND, "test")
        self.on_main("roadmap/questions/Q-0.md", "q\n", "Ask")
        head = git(self.worktree, "rev-parse", "HEAD")
        status, out = self.item("merge-main", FIRST)
        self.assertEqual(status, 2, out)
        self.assertIn("%s holds the promotion token" % SECOND, out)
        self.assertEqual(git(self.worktree, "rev-parse", "HEAD"), head)

    def test_boards_refuse_a_head_main_is_not_an_ancestor_of(self):
        git(self.worktree, "push", "-q", "origin", self.state["branch"])
        self.on_main("roadmap/questions/Q-0.md", "q\n", "Ask")
        status, out = self.item("boards", FIRST)
        self.assertEqual(status, 2, out)
        self.assertIn("merge-main %s" % FIRST, out)
        self.assertIn("--unmerged", out)

    def test_push_refuses_stale_citations(self):
        (self.worktree / "check.py").write_text(
            "def citations_dump():\n    return 'fresh'\n"
            "def regenerating(path):\n    return 'the regeneration'\n")
        (self.worktree / "citations.txt").write_text("stale")
        git(self.worktree, "add", "-A")
        git(self.worktree, "commit", "-q", "-m", "citations")
        status, out = self.item("push", FIRST)
        self.assertEqual(status, 2, out)
        self.assertIn("citations.txt is stale", out)
        self.assertIn("the regeneration", out)
        self.assertIsNone(git_or_none(self.worktree, "rev-parse",
                                      "origin/" + self.state["branch"]))
        (self.worktree / "citations.txt").write_text("fresh")
        git(self.worktree, "commit", "-q", "-am", "regenerated")
        saved = item.runs_of
        item.runs_of = lambda commit: []
        try:
            status, out = self.item("push", FIRST)
        finally:
            item.runs_of = saved
        self.assertEqual(status, 0, out)
        self.assertIn("no gate run for", out)
        self.assertEqual(git(self.worktree, "rev-parse", "HEAD"),
                         git(self.worktree, "rev-parse",
                             "origin/" + self.state["branch"]))


    def fake_check(self, ages=(), whole=0):
        """A check.py whose age check refuses AGES and whose whole run
        exits WHOLE."""
        (self.worktree / "check.py").write_text(
            "import sys\nROOT = '.'\n"
            "def register_ages(root):\n    return {}\n"
            "def register_age_problems(root, ages):\n"
            "    return %r\n"
            "if __name__ == '__main__':\n"
            "    print('roadmap/register/SR-1.md:1: the whole check refused')\n"
            "    sys.exit(%d)\n" % (list(ages), whole))
        git(self.worktree, "add", "-A")
        git(self.worktree, "commit", "-q", "-m", "a check")

    def test_push_runs_the_whole_check_over_a_changed_roadmap(self):
        #  The item's start changed ROADMAP.md, so the whole check runs.
        self.fake_check(whole=1)
        status, out = self.item("push", FIRST)
        self.assertEqual(status, 2, out)
        self.assertIn("`python3 check.py` refuses this tree", out)
        self.assertIn("the whole check refused", out)
        self.assertIn("nothing was pushed", out)
        self.assertIsNone(git_or_none(self.worktree, "rev-parse",
                                      "origin/" + self.state["branch"]))

    def test_merge_main_names_a_row_the_merge_aged(self):
        self.fake_check(ages=[("roadmap/register/SR-1.md", 1,
                               "SR-1 has stood open through 11 items")])
        self.on_main("roadmap/questions/Q-0.md", "q\n",
                     "Ask\n\n" + item.EXPLANATORY)
        status, out = self.item("merge-main", FIRST)
        self.assertEqual(status, 1, out)
        self.assertIn("the register's age check refuses this tree", out)
        self.assertIn("SR-1 has stood open", out)
        self.assertIn("`item.py push %s` refuses" % FIRST, out)

    def test_merge_main_merges_a_named_branch_without_the_token(self):
        self.item("start", SECOND)
        git(self.clone, "checkout", "-q", "-b", "w", "origin/main")
        (self.clone / "roadmap").mkdir(exist_ok=True)
        (self.clone / "roadmap" / "window.md").write_text("window\n")
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", "Window\n\n" + item.EXPLANATORY)
        git(self.clone, "push", "-q", "origin", "w:r9-integration")
        git(self.clone, "checkout", "-q", "main")
        status, out = self.item("merge-main", FIRST, "--branch",
                                "r9-integration")
        self.assertEqual(status, 0, out)
        self.assertIn("merged origin/r9-integration", out)
        self.assertIn(item.EXPLANATORY, self.merged_message())
        self.assertTrue((self.worktree / "roadmap" / "window.md").exists())
        item.REPOSITORY[0] = self.clone
        self.assertEqual(item.take(SECOND, "test"), (True, None))
        status, out = self.item("merge-main", FIRST, "--branch", "absent")
        self.assertEqual(status, 2, out)
        self.assertIn("no branch origin/absent", out)


class GateListing(Promote):
    def test_main_listing_names_branches_and_main_not_started(self):
        head = self.commit("work")
        self.state["promoted"] = head
        item.save(self.state)
        saved = item.runs_of
        item.runs_of = lambda commit: [{
            "databaseId": 7, "event": "push",
            "headBranch": self.state["branch"], "status": "completed",
            "conclusion": "success", "displayTitle": "work", "attempt": 1}]
        try:
            status, out = self.item("gate", FIRST, "--main")
        finally:
            item.runs_of = saved
        self.assertEqual(status, 0, out)
        self.assertIn("run 7  software %s (push)" % self.state["branch"],
                      out)
        self.assertIn("main's own push gate on %s has not started yet"
                      % head[:12], out)

class Timing(Promote):
    """A boards run that failed in timing alone is re-run, not dispatched."""

    def boards_run(self, head):
        git(self.worktree, "push", "-q", "origin", self.state["branch"])
        entry = dict(self.gate(head, "boards"), conclusion="failure",
                     attempt=1)
        self.state["gates"].append(entry)
        item.save(self.state)
        return entry

    def rerun(self, kind):
        asked = []
        saved = item.record_gates, item.failure_of, item.rerun_failed_jobs
        item.record_gates = lambda state, commit: state
        item.failure_of = lambda run: kind
        item.rerun_failed_jobs = asked.append
        try:
            status, out = self.item("boards", FIRST, "--rerun-failed")
        finally:
            item.record_gates, item.failure_of, item.rerun_failed_jobs = saved
        return status, out, asked

    def test_a_timing_failure_reruns_its_failed_jobs(self):
        entry = self.boards_run(self.commit("work"))
        status, out, asked = self.rerun("timing")
        self.assertEqual(status, 0, out)
        self.assertEqual(asked, [entry["run"]])
        self.assertIn("attempt 2", out)

    def test_a_board_failure_is_not_rerun(self):
        self.boards_run(self.commit("work"))
        for kind in ("jobs", "aggregate"):
            with self.subTest(kind=kind):
                status, out, asked = self.rerun(kind)
                self.assertEqual(status, 2, out)
                self.assertEqual(asked, [])
                self.assertIn("did not fail in timing alone", out)

    def boards_beside(self, listed, *extra):
        """`item.py boards` with LISTED as GitHub's runs of the head; the
        dispatches it asked for, and its status and output."""
        head = getattr(self, "head", None) or self.commit("work")
        self.head = head
        git(self.worktree, "push", "-q", "origin", self.state["branch"])
        asked, real = [], item.subprocess.run

        def run(command, *arguments, **options):
            if command[0] == "gh":
                asked.append(command)
                return item.subprocess.CompletedProcess(
                    command, 1, "", "refused by the test")
            return real(command, *arguments, **options)
        saved = item.runs_of, item.record_gates, item.subprocess.run
        item.runs_of = lambda commit: [dict(found, headBranch=self.state[
            "branch"]) for found in listed]
        item.record_gates = lambda state, commit: state
        item.subprocess.run = run
        try:
            status, out = self.item("boards", FIRST, *extra)
        finally:
            item.runs_of, item.record_gates, item.subprocess.run = saved
        return head, asked, status, out

    def test_a_queued_boards_run_is_followed_not_dispatched_again(self):
        queued = {"databaseId": 9, "event": "workflow_dispatch",
                  "status": "queued", "conclusion": "",
                  "displayTitle": "gate (boards)", "attempt": 1}
        head, asked, status, out = self.boards_beside([queued])
        self.assertEqual(status, 0, out)
        self.assertEqual(asked, [])
        self.assertIn("boards run 9 on %s is queued: followed, not"
                      " dispatched again" % head[:12], out)

    def test_a_passed_boards_run_is_named_not_dispatched_again(self):
        passed = {"databaseId": 9, "event": "workflow_dispatch",
                  "status": "completed", "conclusion": "success",
                  "displayTitle": "gate (boards)", "attempt": 1}
        _, asked, status, out = self.boards_beside([passed])
        self.assertEqual(status, 0, out)
        self.assertEqual(asked, [])
        self.assertIn("boards run 9 on", out)
        self.assertIn("passed: not dispatched again", out)

    def test_again_or_a_failed_boards_run_dispatches(self):
        failed = {"databaseId": 9, "event": "workflow_dispatch",
                  "status": "completed", "conclusion": "failure",
                  "displayTitle": "gate (boards)", "attempt": 1}
        queued = dict(failed, status="queued", conclusion="")
        for listed, extra in (([failed], ()), ([queued], ("--again",))):
            with self.subTest(extra=extra):
                _, asked, status, out = self.boards_beside(listed, *extra)
                self.assertEqual(len(asked), 1, out)
                self.assertEqual(asked[0][:3], ["gh", "workflow", "run"])
                self.assertIn("refused by the test", out)

    def test_a_timing_failure_reads_as_timing(self):
        entry = dict(self.gate(self.commit("work"), "boards"),
                     conclusion="failure", failed="timing")
        self.state["gates"].append(entry)
        text = "\n".join(item.describe(self.state))
        self.assertIn("timing only, every board leg passed", text)
        self.assertIn("boards %s --rerun-failed" % FIRST, text)


WINDOW_BRANCH = "r0-integration"


class Window(Clone):
    """A phase's breaking window: its items land on its integration
    branch, not on main."""

    def setUp(self):
        super().setUp()
        text = (self.clone / "ROADMAP.md").read_text().replace(
            "## R0 — A phase\n", "## R0 — A phase\n\nWindow: %s\n"
            % WINDOW_BRANCH)
        (self.clone / "ROADMAP.md").write_text(text)
        git(self.clone, "commit", "-q", "-am", "the window")
        git(self.clone, "push", "-q", "origin",
            "main:refs/heads/" + WINDOW_BRANCH)
        #  Main moves on without the window.
        (self.clone / "main.txt").write_text("main\n")
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", "on main")
        git(self.clone, "push", "-q", "origin", "main")
        self.window = git(self.clone, "rev-parse", "origin/" + WINDOW_BRANCH)

    def started(self):
        status, out = self.item("start", FIRST)
        self.assertEqual(status, 0, out)
        state = item.load(FIRST)
        worktree = Path(state["worktree"])
        (worktree / "work.txt").write_text("work\n")
        git(worktree, "add", "-A")
        git(worktree, "commit", "-q", "-m", "work")
        return state, worktree, out

    def offline(self, passed=True):
        """GitHub as a listing would give it: the head's push gate passed
        or not, and nothing else running."""
        saved = (item.record_gates, item.complete_listing, item.gh)
        def record(state, commit):
            if passed and not any(entry["commit"] == commit
                                  for entry in state["gates"]):
                state["gates"].append({
                    "run": 1, "commit": commit, "kind": "software",
                    "tree": git(state["worktree"], "rev-parse",
                                commit + "^{tree}"),
                    "status": "completed", "conclusion": "success"})
            return state
        item.record_gates = record
        item.complete_listing = lambda run: None
        item.gh = lambda *arguments: []
        self.addCleanup(lambda: (
            setattr(item, "record_gates", saved[0]),
            setattr(item, "complete_listing", saved[1]),
            setattr(item, "gh", saved[2])))

    def test_start_branches_from_the_window_and_says_so(self):
        state, worktree, out = self.started()
        self.assertEqual(state["target"], WINDOW_BRANCH)
        self.assertEqual(state["base"], self.window)
        self.assertIn("lands on %s" % WINDOW_BRANCH, out)
        brief = (item.item_directory(FIRST) / "brief.md").read_text()
        self.assertIn("land it on the window's integration branch %s"
                      % WINDOW_BRANCH, brief)
        self.assertFalse((worktree / "main.txt").exists())

    def test_promote_lands_on_the_window_without_boards(self):
        state, worktree, _ = self.started()
        self.offline()
        status, out = self.item("promote", FIRST, "--partial")
        self.assertEqual(status, 2, out)
        self.assertIn("HEAD is not the branch's pushed head", out)
        status, out = self.item("push", FIRST)
        self.assertEqual(status, 0, out)
        status, out = self.item("promote", FIRST, "--partial")
        self.assertEqual(status, 0, out)
        head = git(worktree, "rev-parse", "HEAD")
        self.assertEqual(git(self.clone, "ls-remote", "origin",
                             WINDOW_BRANCH).split()[0], head)
        self.assertNotEqual(git(self.clone, "ls-remote", "origin",
                                "refs/heads/main").split()[0], head)
        #  The window's token is given up at the landing, and main's was
        #  never taken.
        self.assertEqual(item.take(SECOND, "test", target=WINDOW_BRANCH),
                         (True, None))
        self.assertEqual(item.take(SECOND, "test"), (True, None))
        self.assertIn("`item.py finish %s`" % FIRST,
                      item.next_step(item.load(FIRST)))
        status, out = self.item("finish", FIRST)
        self.assertEqual(status, 0, out)
        self.assertFalse(worktree.exists())

    def test_merge_main_merges_the_window(self):
        state, worktree, _ = self.started()
        git(self.clone, "fetch", "-q", "origin")
        git(self.clone, "checkout", "-q", "-b", "w", "origin/" + WINDOW_BRANCH)
        (self.clone / "sibling.txt").write_text("a sibling landed\n")
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", "sibling")
        git(self.clone, "push", "-q", "origin", "w:" + WINDOW_BRANCH)
        status, out = self.item("merge-main", FIRST)
        self.assertEqual(status, 0, out)
        self.assertIn("merged origin/%s" % WINDOW_BRANCH, out)
        self.assertTrue((worktree / "sibling.txt").exists())
        self.assertFalse((worktree / "main.txt").exists())

    def test_a_state_from_before_windows_reads_its_roadmap(self):
        state, worktree, _ = self.started()
        del state["target"]
        item.save(state)
        self.assertEqual(item.target_of(item.load(FIRST)), WINDOW_BRANCH)

    def test_finish_takes_a_head_landed_by_hand(self):
        state, worktree, _ = self.started()
        status, out = self.item("finish", FIRST)
        self.assertEqual(status, 2, out)
        self.assertIn("neither origin/%s nor origin/main" % WINDOW_BRANCH, out)
        git(worktree, "push", "-q", "origin", "HEAD:" + WINDOW_BRANCH)
        status, out = self.item("finish", FIRST)
        self.assertEqual(status, 0, out)
        journal = (item.state_root() / item.DONE_DIRECTORY / FIRST
                   / "journal.md").read_text()
        self.assertIn("its head is in %s" % WINDOW_BRANCH, journal)


class Mirror(Clone):
    """A mirror among origin's push URLs that refuses fails no step."""

    def test_a_refusing_mirror_is_reported_and_the_push_stands(self):
        git(self.clone, "remote", "set-url", "--add", "--push", "origin",
            str(self.origin))
        git(self.clone, "remote", "set-url", "--add", "--push", "origin",
            str(self.top / "no-such-mirror.git"))
        self.item("start", FIRST)
        state = item.load(FIRST)
        saved = item.gh
        item.gh = lambda *arguments: []
        self.addCleanup(setattr, item, "gh", saved)
        status, out = self.item("push", FIRST)
        self.assertEqual(status, 0, out)
        self.assertIn("GitHub took the push; the mirror", out)
        self.assertIn("git push %s" % (self.top / "no-such-mirror.git"), out)
        worktree = Path(state["worktree"])
        self.assertEqual(git(worktree, "rev-parse", "origin/"
                             + state["branch"]),
                         git(worktree, "rev-parse", "HEAD"))
        self.assertIn("the mirror refused",
                      (item.item_directory(FIRST) / "journal.md").read_text())

    def test_credentials_in_a_url_are_not_shown(self):
        self.assertEqual(item.shown_url("https://user:secret@example.org/x"),
                         "https://example.org/x")


class SessionToken(Clone):
    def test_work_that_is_no_item_takes_and_releases_the_token(self):
        self.item("start", FIRST)
        status, out = self.item("queue", "--take", "sweep", "--why",
                                "a register sweep")
        self.assertEqual(status, 0, out)
        taken, why = item.take(FIRST, "test")
        self.assertFalse(taken)
        self.assertIn("until it releases it", why)
        #  Not dropped for want of an item's state.
        status, out = self.item("queue")
        self.assertIn("promotion token: sweep since", out)
        status, out = self.item("queue", "--take", FIRST)
        self.assertEqual(status, 2, out)
        status, out = self.item("queue", "--release", "sweep")
        self.assertIn("released", out)
        self.assertEqual(item.take(FIRST, "test"), (True, None))


    def test_work_that_is_no_item_waits_in_line(self):
        self.item("start", FIRST)
        self.item("start", SECOND)
        item.REPOSITORY[0] = self.clone
        item.take(FIRST, "test")
        status, out = self.item("queue", "--take", "sweep", "--why", "sweep")
        self.assertEqual(status, 1, out)
        self.assertIn("sweep is number 1 in line", out)
        self.assertIn("queue --wait sweep --why", out)
        taken, why = item.take(SECOND, "test")
        self.assertFalse(taken)
        self.assertIn("%s is number 2 in line" % SECOND, why)
        item.release(FIRST, "test")
        taken, why = item.take(SECOND, "test")
        self.assertIn("sweep waits for the promotion token before %s"
                      % SECOND, why)
        status, out = self.item("queue", "--wait", "nobody")
        self.assertEqual(status, 2, out)
        self.assertIn("--why TEXT", out)
        status, out = self.item("queue", "--wait", "sweep", "--why", "sweep",
                                "--timeout", "0")
        self.assertEqual(status, 0, out)
        self.assertIn("until `item.py queue --release sweep`", out)
        self.item("queue", "--release", "sweep")
        self.assertEqual(item.take(SECOND, "test"), (True, None))

    def test_a_session_that_stopped_asking_leaves_the_line(self):
        self.item("start", FIRST)
        self.item("start", SECOND)
        item.REPOSITORY[0] = self.clone
        item.take(FIRST, "test")
        self.assertFalse(item.take("sweep", "x", session=True)[0])
        saved = item.SESSION_LINE
        item.SESSION_LINE = -1
        try:
            taken, why = item.take(SECOND, "test")
        finally:
            item.SESSION_LINE = saved
        self.assertIn("%s is number 1 in line" % SECOND, why)

class Clashes(Clone):
    def test_a_merged_branch_that_took_a_reserved_number_is_named(self):
        self.item("start", FIRST)
        state = item.load(FIRST)
        low = state["reserved"]["D"][0]
        sr = state["reserved"]["SR"][0]
        (self.clone / "spec.md").write_text("D41, D42 and D%d.\n" % low)
        rows = self.clone / "roadmap/register"
        rows.mkdir(parents=True)
        (rows / ("SR-%d.md" % sr)).write_text("a row\n")
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", "taken outside the item")
        git(self.clone, "push", "-q", "origin", "main")
        git(state["worktree"], "fetch", "-q", "origin")
        said = item.reserved_clashes(state, "origin/main")
        self.assertEqual(len(said), 2, said)
        self.assertIn("D%d of %s's reserved block" % (low, FIRST), said[0])
        self.assertIn("SR-%d" % sr, said[1])


def git_or_none(root, *arguments):
    result = subprocess.run(["git", *arguments], cwd=root, env=environment(),
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    return result.stdout.strip() if result.returncode == 0 else None


if __name__ == "__main__":
    unittest.main()


class History(Clone):
    def test_every_change_of_holder_and_line_is_kept(self):
        self.item("start", FIRST)
        item.REPOSITORY[0] = self.clone
        self.assertEqual(item.take(FIRST, "test"), (True, None))
        self.assertFalse(item.take("sweep", "a sweep", session=True)[0])
        item.mark_promoted(FIRST, "c0ffee")
        item.release(FIRST, "test")
        self.assertEqual(item.take("sweep", "a sweep", session=True),
                         (True, None))
        path = item.state_root() / ("queue" + item.HISTORY)
        events = [(entry["event"], entry["name"]) for entry in map(
            json.loads, path.read_text().splitlines())]
        self.assertEqual(events, [
            ("taken", FIRST), ("joined line", "sweep"),
            ("promoted", FIRST), ("released", FIRST),
            ("taken", "sweep"), ("left line", "sweep")])


class Verdict(Promote):
    """Main's token and finish wait end at the aggregate's verdict."""

    def main_run(self, verdict):
        head = self.commit("work")
        self.state["promoted"] = head
        self.state["phase"] = "promoted"
        item.save(self.state)
        item.take(FIRST, "test")
        item.mark_promoted(FIRST, head)
        item.verdict_of = lambda run: verdict
        saved = item.runs_of
        item.runs_of = lambda commit: [{
            "databaseId": 9, "event": "push", "headBranch": "main",
            "status": "in_progress", "conclusion": "",
            "displayTitle": "work", "attempt": 1}]
        self.addCleanup(setattr, item, "runs_of", saved)
        return head

    def test_a_passed_verdict_releases_the_token_and_passes_main(self):
        self.main_run("success")
        status, out = self.item("gate", FIRST, "--main")
        self.assertEqual(status, 0, out)
        self.assertIn("has its verdict: the promotion token is released",
                      out)
        self.assertIn("the cache jobs after it are still running", out)
        self.assertEqual(item.load(FIRST)["phase"], "main-passed")
        status, out = self.item("queue")
        self.assertIn("promotion token: free", out)

    def test_no_verdict_yet_holds_the_token(self):
        self.main_run(None)
        status, out = self.item("gate", FIRST, "--main")
        self.assertNotIn("released", out)
        status, out = self.item("queue")
        self.assertIn("promotion token: %s" % FIRST, out)

    def test_main_passed_reads_the_verdict_or_the_run(self):
        self.assertTrue(item.main_passed({"kind": "main",
                                          "verdict": "success",
                                          "conclusion": "failure"}))
        self.assertFalse(item.main_passed({"kind": "main",
                                           "verdict": "failure",
                                           "conclusion": ""}))
        self.assertTrue(item.main_passed({"kind": "main",
                                          "conclusion": "success"}))
        self.assertFalse(item.main_passed({"kind": "software",
                                           "conclusion": "success"}))


class PrePush(Promote):
    """The cheap checks a push's paths select, run before it."""

    def change(self, path, text="x\n", message="change"):
        target = self.worktree / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        git(self.worktree, "add", "-A")
        git(self.worktree, "commit", "-q", "-m", message)

    def selected(self, since):
        return [command for _, command in item.prepush_checks(
            str(self.worktree), since)]

    def test_a_new_library_module_selects_its_checks(self):
        base = git(self.worktree, "rev-parse", "HEAD")
        self.change("core/new.ldn")
        checks = self.selected(base)
        self.assertEqual(checks[0], [
            "./scripts/dev-test.sh", "--case=" + item.FORMAT_CASE,
            "--suite=lowering", "--case=" + item.CLOSURE_CASE])
        self.assertEqual(checks[1][1:], ["scripts/script_tests.py",
                                         "test_library_docs"])
        self.assertEqual(len(checks), 2)
        self.assertIn("measured sizes", item.baseline_warning(
            str(self.worktree), base))

    def test_a_changed_compiler_source_selects_lowering_alone(self):
        self.change("compiler/ada/src/a.adb", message="first")
        base = git(self.worktree, "rev-parse", "HEAD")
        self.change("compiler/ada/src/a.adb", "y\n")
        self.assertEqual(self.selected(base),
                         [["./scripts/dev-test.sh", "--suite=lowering"]])

    def test_a_document_selects_nothing_and_a_merge_the_whole_check(self):
        base = git(self.worktree, "rev-parse", "HEAD")
        self.change("docs/a.md")
        self.assertEqual(self.selected(base), [])
        self.assertIsNone(item.baseline_warning(str(self.worktree), base))
        (self.clone / "other.md").write_text("main\n")
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", "main moves")
        git(self.clone, "push", "-q", "origin", "main")
        git(self.worktree, "fetch", "-q", "origin")
        git(self.worktree, "merge", "-q", "--no-edit", "origin/main")
        self.assertEqual(self.selected(base)[-1][1:], ["check.py"])

    def test_a_failed_check_refuses_the_push_and_no_check_skips_it(self):
        saved = item.prepush_checks
        item.prepush_checks = lambda worktree, since, roadmap_checked=False: [
            ("a failing check", [sys.executable, "-c",
                                 "print('the cause'); raise SystemExit(3)"])]
        self.addCleanup(setattr, item, "prepush_checks", saved)
        saved_runs = item.runs_of
        item.runs_of = lambda commit: []
        self.addCleanup(setattr, item, "runs_of", saved_runs)
        self.commit("work")
        status, out = self.item("push", FIRST)
        self.assertEqual(status, 2, out)
        self.assertIn("the pre-push check of a failing check failed (exit 3)",
                      out)
        self.assertIn("the cause", out)
        self.assertIn("--no-check", out)
        self.assertIsNone(git_or_none(self.worktree, "rev-parse",
                                      "origin/" + self.state["branch"]))
        status, out = self.item("push", FIRST, "--no-check")
        self.assertEqual(status, 0, out)
        self.assertIn("pushed with --no-check",
                      (item.item_directory(FIRST) / "journal.md").read_text())

    def test_push_with_boards_dispatches_beside_the_gate(self):
        saved_runs, saved_boards = item.runs_of, item.boards
        item.runs_of = lambda commit: []
        dispatched = []
        item.boards = lambda arguments: dispatched.append(
            (arguments.item, arguments.unmerged)) or 0
        self.addCleanup(setattr, item, "runs_of", saved_runs)
        self.addCleanup(setattr, item, "boards", saved_boards)
        self.commit("work")
        status, out = self.item("push", FIRST, "--boards")
        self.assertEqual(status, 0, out)
        self.assertEqual(dispatched, [(FIRST, False)])


class Train(Clone):
    """A train: the holder's final merge brings other gated candidates."""

    def setUp(self):
        super().setUp()
        self.item("start", FIRST)
        self.item("start", THIRD, "--force")
        self.item("start", SECOND)
        item.REPOSITORY[0] = self.clone
        self.saved = (item.runs_of, item.complete_listing)
        item.runs_of = lambda commit: []
        item.complete_listing = lambda run: None
        self.holder = Path(item.load(FIRST)["worktree"])

    def tearDown(self):
        item.runs_of, item.complete_listing = self.saved
        super().tearDown()

    def gated(self, name, path):
        """NAME's candidate: complete, pushed, its push gate passed."""
        state = item.load(name)
        worktree = Path(state["worktree"])
        roadmap = (worktree / "ROADMAP.md").read_text()
        heading = roadmap.index("### %s " % name)
        start = roadmap.index("Status: active", heading)
        roadmap = roadmap[:start] + "Status: complete" + roadmap[
            start + len("Status: active"):]
        (worktree / "ROADMAP.md").write_text(roadmap)
        (worktree / path).write_text(name + "\n")
        git(worktree, "add", "-A")
        git(worktree, "commit", "-q", "-m", "Close " + name)
        git(worktree, "push", "-q", "origin", "HEAD:" + state["branch"])
        head = git(worktree, "rev-parse", "HEAD")
        state = item.load(name)
        state["gates"].append({"run": 100 + len(state["gates"]),
                               "commit": head, "tree": "t", "kind":
                               "software", "status": "completed",
                               "conclusion": "success"})
        item.save(state)
        git(self.holder, "fetch", "-q", "origin")
        return head

    def test_a_gated_member_rides_and_lands_with_the_holder(self):
        self.gated(FIRST, "first.txt")
        head = self.gated(THIRD, "third.txt")
        item.take(THIRD, "test")
        item.release(THIRD, "test")
        item.take(FIRST, "test")
        self.assertFalse(item.take(THIRD, "test")[0])
        status, out = self.item("merge-main", FIRST, "--with", THIRD)
        self.assertEqual(status, 0, out)
        self.assertIn("%s's train: %s %s" % (FIRST, THIRD, head[:12]), out)
        self.assertTrue((self.holder / "third.txt").exists())
        member = item.load(THIRD)
        self.assertEqual(member["train"]["holder"], FIRST)
        status, out = self.item("queue")
        self.assertIn("waiting: nobody", out)
        #  A member does not push, wait for the token or promote itself.
        for command in (("push", THIRD), ("queue", "--wait", THIRD),
                        ("promote", THIRD), ("merge-main", THIRD)):
            status, out = self.item(*command)
            self.assertEqual(status, 2, (command, out))
            self.assertIn("rides %s's train" % FIRST, out)
        status, out = self.item("resume", THIRD)
        self.assertIn("ride %s's train" % FIRST, out)
        #  Promotion writes the member as promoted, with the holder's runs.
        holder = item.load(FIRST)
        commit = git(self.holder, "rev-parse", "HEAD")
        items, _ = item.roadmap_items((self.holder / "ROADMAP.md").read_text())
        self.assertEqual(item.train_landing_problems(holder, commit, items,
                                                     False), [])
        holder["gates"].append({"run": 7, "commit": commit, "tree": "t",
                                "kind": "software", "status": "completed",
                                "conclusion": "success"})
        item.land_train(holder, commit)
        member = item.load(THIRD)
        self.assertEqual((member["phase"], member["promoted"]),
                         ("promoted", commit))
        self.assertEqual([entry.get("via") for entry in member["gates"]
                          if entry["run"] == 7], [FIRST])
        self.assertIsNone(item.riding(member))

    def test_a_member_that_moved_is_named_at_promotion(self):
        self.gated(FIRST, "first.txt")
        self.gated(THIRD, "third.txt")
        item.take(FIRST, "test")
        self.assertEqual(self.item("merge-main", FIRST, "--with", THIRD)[0],
                         0)
        worktree = Path(item.load(THIRD)["worktree"])
        (worktree / "later.txt").write_text("later\n")
        git(worktree, "add", "-A")
        git(worktree, "commit", "-q", "-m", "later")
        git(worktree, "push", "-q", "origin", "HEAD:" + item.load(
            THIRD)["branch"])
        commit = git(self.holder, "rev-parse", "HEAD")
        items, _ = item.roadmap_items((self.holder / "ROADMAP.md").read_text())
        git(self.holder, "fetch", "-q", "origin")
        problems = item.train_landing_problems(item.load(FIRST), commit,
                                               items, False)
        self.assertTrue(any("moved past" in one for one in problems),
                        problems)

    def test_maintainer_ungated_and_conflicting_members_are_refused(self):
        self.gated(FIRST, "first.txt")
        item.take(FIRST, "test")
        status, out = self.item("merge-main", FIRST, "--with", SECOND)
        self.assertEqual(status, 1, out)
        self.assertIn("`Promotion: maintainer`", out)
        self.assertIn("no passed push gate", out)
        self.assertNotIn("train", item.load(SECOND))
        self.gated(THIRD, "first.txt")
        status, out = self.item("merge-main", FIRST, "--with", THIRD)
        self.assertEqual(status, 1, out)
        self.assertIn("conflicts outside the generated files: first.txt",
                      out)
        self.assertEqual(git(self.holder, "status", "--porcelain"), "")
        self.assertNotIn("train", item.load(THIRD))

    def test_drop_rebuilds_without_the_member_and_puts_it_first(self):
        self.gated(FIRST, "first.txt")
        self.gated(THIRD, "third.txt")
        item.take(FIRST, "test")
        self.assertEqual(self.item("merge-main", FIRST, "--with", THIRD)[0],
                         0)
        (self.holder / "done.txt").write_text("done\n")
        git(self.holder, "add", "-A")
        git(self.holder, "commit", "-q", "-m", "Done paragraphs")
        git(self.holder, "push", "-q", "origin", "HEAD:" + item.load(
            FIRST)["branch"])
        status, out = self.item("merge-main", FIRST, "--drop", THIRD)
        self.assertEqual(status, 0, out)
        self.assertIn("1 commit(s) made after the members' merges", out)
        self.assertFalse((self.holder / "third.txt").exists())
        self.assertIsNone(item.riding(item.load(THIRD)))
        self.assertTrue(item.load(FIRST)["train"]["rebuilt"])
        status, out = self.item("queue")
        self.assertIn("waiting: %s" % THIRD, out)
        #  The rebuilt branch replaces the pushed one, which it does not
        #  contain.
        status, out = self.item("push", FIRST, "--no-check")
        self.assertEqual(status, 0, out)
        self.assertEqual(git(self.holder, "rev-parse", "HEAD"),
                         git(self.holder, "rev-parse", "origin/" + item.load(
                             FIRST)["branch"]))
        self.assertNotIn("rebuilt", item.load(FIRST)["train"])
