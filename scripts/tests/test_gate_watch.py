#!/usr/bin/env python3
"""Hold the gate watcher to returning at the first failed job, or at the end
naming every failed job when asked to."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
#  Seconds before a subprocess here is called hung.  It ends in well under
#  a second on an idle host; the limit only stops a hang, and is wide
#  because scripts/script_tests.py's own workers load the host.
HANG = 300
WATCH = ROOT / "scripts" / "gate_watch.py"
sys.path.insert(0, str(ROOT / "scripts"))
import gate_watch  # noqa: E402 -- the module under test
#  The workflow file whose runs the watcher follows, as GitHub names it.
WORKFLOW_PATH = gate_watch.WORKFLOW

#  Answers GitHub's GraphQL API as gate_watch.py asks it.  A query naming
#  runs is answered with the next recorded state, holding the last; its
#  check runs are the state's jobs, a page of the size asked for after the
#  cursor given, and a query for steps gives the failed steps of the state
#  last answered.  A query naming commits lists run 7 for each.  Every
#  call's arguments are appended to STATES.calls.  STATES.fail, when
#  present, is [count, message]: that many requests are refused with the
#  message before one is answered.  STATES.unlisted is the number of commit
#  queries answered with no run.
FAKE_GH = '''#!%s
import json, os, re, sys
base = os.environ["STATES"]
states = json.load(open(base))
with open(base + ".calls", "a") as calls:
    calls.write(json.dumps(sys.argv[1:]) + "\\n")
def number(suffix):
    return int(open(base + suffix).read()) if os.path.exists(base + suffix) else 0
if os.path.exists(base + ".fail"):
    left, message = json.load(open(base + ".fail"))
    if left:
        json.dump([left - 1, message], open(base + ".fail", "w"))
        sys.stderr.write(message + "\\n")
        sys.exit(1)
if sys.argv[1:3] != ["api", "graphql"]:
    sys.exit("the fake answers only GraphQL: %%s" %% sys.argv[1:])
query = sys.argv[sys.argv.index("-f") + 1][len("query="):]
seen = number(".count")
data = {}
def upper(value):
    return value.upper() if value else None
for run, first, after in re.findall(
        r'r(\\d+): resource\\(url: "[^"]*"\\) \\{ \\.\\.\\. on WorkflowRun'
        r' \\{[^(]*checkRuns\\(first: (\\d+)(?:, after: "(\\d+)")?', query):
    if not after:
        open(base + ".count", "w").write(str(seen + 1))
    held = states[min(seen if not after else max(seen - 1, 0),
                      len(states) - 1)]
    start, size = int(after or 0), int(first)
    jobs = held["jobs"]
    data["r" + run] = {"databaseId": int(run),
        "runAttempt": held.get("attempt", 1), "event": "push",
        "url": held["url"], "displayTitle": "gate", "createdAt": "",
        "file": {"path": os.environ["WORKFLOW"]},
        "checkSuite": {"status": upper(held["status"]),
            "conclusion": upper(held["conclusion"]),
            "branch": {"name": "main"},
            "checkRuns": {"totalCount": len(jobs),
                "pageInfo": {"hasNextPage": start + size < len(jobs),
                             "endCursor": str(start + size)},
                "nodes": [{"id": "N%%d" %% j["databaseId"],
                    "databaseId": j["databaseId"], "name": j["name"],
                    "status": upper(j["status"]),
                    "conclusion": upper(j["conclusion"]),
                    "startedAt": j["startedAt"],
                    "completedAt": j["completedAt"]}
                    for j in jobs[start:start + size]]}}}
commits = re.findall(r'c(\\d+): object\\(oid: "(\\w+)"\\)', query)
if commits:
    unlisted = number(".unlisted")
    if unlisted:
        open(base + ".unlisted", "w").write(str(unlisted - 1))
    suites = [] if unlisted else [{"status": "COMPLETED",
        "conclusion": "SUCCESS", "branch": {"name": "main"},
        "workflowRun": {"databaseId": 7, "runAttempt": 1, "event": "push",
            "url": "", "displayTitle": "gate", "createdAt": "",
            "file": {"path": os.environ["WORKFLOW"]}}}]
    data["repository"] = {"c" + index: {"checkSuites": {"nodes": suites}}
                          for index, _ in commits}
ids = re.search(r"nodes\\(ids: \\[([^]]*)\\]", query)
if ids:
    held = states[min(max(seen - 1, 0), len(states) - 1)]
    steps = {"N%%d" %% j["databaseId"]: j["steps"] for j in held["jobs"]}
    data["nodes"] = [{"id": node, "steps": {"nodes": [
        {"name": step["name"], "number": 1,
         "conclusion": step["conclusion"].upper()}
        for step in steps.get(node, [])]}}
        for node in re.findall(r'"([^"]+)"', ids.group(1))]
print(json.dumps({"data": data}))
'''


def job(number, name, status="completed", conclusion="success", steps=()):
    return {"databaseId": number, "name": name, "status": status,
            "conclusion": conclusion if status == "completed" else "",
            "startedAt": "2026-10-16T12:00:00Z",
            "completedAt": "2026-10-16T12:03:00Z",
            "steps": [{"name": step, "conclusion": "failure"} for step in steps]}


def attempt(number, held):
    return {**held, "run_attempt": number}


def state(status, jobs, conclusion="", attempt=1):
    return {"status": status, "conclusion": conclusion, "attempt": attempt,
            "url": "https://example.invalid/run/7", "jobs": jobs}


class Fixture(unittest.TestCase):
    """A fake `gh` answering recorded states, and the watcher run on them."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="landin-watch-")
        self.addCleanup(self.temporary.cleanup)
        directory = Path(self.temporary.name)
        gh = directory / "gh"
        gh.write_text(FAKE_GH % sys.executable)
        gh.chmod(0o755)
        self.states = directory / "states.json"
        #  The shared poller's directory, apart from the host's.
        self.shared = directory / "shared"

    def watch(self, states, *arguments):
        self.states.write_text(json.dumps(states))
        environment = {**os.environ, "STATES": str(self.states),
                       "LANDIN_GATE_WATCH_DIR": str(self.shared),
                       "GH_REPO": "example/landin",
                       "WORKFLOW": WORKFLOW_PATH,
                       "PATH": "%s%s%s" % (self.temporary.name, os.pathsep,
                                           os.environ["PATH"])}
        return subprocess.run(
            [sys.executable, str(WATCH), "--interval=0", "--alone",
             *arguments],
            capture_output=True, text=True, timeout=HANG, env=environment,
            cwd=ROOT)

    def calls(self):
        recorded = self.states.parent / "states.json.calls"
        if not recorded.exists():
            return []
        return [json.loads(line) for line in recorded.read_text().splitlines()]

    def queries(self):
        return [call[call.index("-f") + 1] for call in self.calls()
                if call[:2] == ["api", "graphql"]]

    def asked_for(self):
        import re
        return [re.search(r'oid: "(\w+)"', query).group(1)
                for query in self.queries() if "oid:" in query][0]


class GateWatch(Fixture):
    def test_the_first_failed_job_ends_the_watch_while_others_run(self):
        result = self.watch([
            state("in_progress", [job(1, "documents"),
                                  job(2, "compiler", status="in_progress")]),
            state("in_progress", [job(1, "documents"),
                                  job(2, "compiler", status="in_progress"),
                                  job(3, "scripts", conclusion="failure",
                                      steps=["scripts/tests"])]),
        ], "--run=7")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAILED: scripts at scripts/tests", result.stdout)
        self.assertEqual(result.stdout.count("documents"), 1)

    def test_a_failed_job_of_an_active_run_gets_a_log_command_that_answers(self):
        #  `gh run view --log-failed` refuses until the whole run ends; the
        #  job's own endpoint answers at once, printed with the flag the
        #  pinned gh needs before it writes the log's escape sequences to a
        #  terminal.  Both name run 7 and job 3.
        result = self.watch([
            state("in_progress", [job(2, "compiler", status="in_progress"),
                                  job(3, "scripts", conclusion="failure")]),
        ], "--run=7")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("log:    gh api --allow-escape-sequences "
                      "repos/{owner}/{repo}/actions/jobs/3/logs",
                      result.stdout)
        self.assertIn("readable while run 7 is still active", result.stdout)
        self.assertIn("once the run ends: gh run view 7 --job 3 --log-failed",
                      result.stdout)

    def test_a_failed_job_of_an_ended_run_gets_the_failed_step_command(self):
        result = self.watch([
            state("completed", [job(3, "scripts", conclusion="failure")],
                  conclusion="failure"),
        ], "--run=7")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("log:    gh run view 7 --job 3 --log-failed",
                      result.stdout)
        self.assertNotIn("actions/jobs/3/logs", result.stdout)

    def test_all_names_every_failed_job_once_the_run_ends(self):
        result = self.watch([
            state("in_progress", [job(1, "documents"),
                                  job(2, "scripts", conclusion="failure"),
                                  job(3, "compiler", status="in_progress")]),
            state("completed", [job(1, "documents"),
                                job(2, "scripts", conclusion="failure"),
                                job(3, "editor-grammar", conclusion="failure",
                                    steps=["The integration pass"])],
                  conclusion="failure"),
        ], "--run=7", "--all")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAILED: editor-grammar at The integration pass",
                      result.stdout)
        self.assertIn("failed jobs: scripts, editor-grammar", result.stdout)
        self.assertIn("run 7: failure", result.stdout)
        #  Each failed job named again with its step, so a second cause is
        #  not lost among the first's lines.
        self.assertIn("  editor-grammar: at The integration pass",
                      result.stdout)
        self.assertIn("  scripts: no failed step listed", result.stdout)

    def test_verdict_returns_when_the_aggregate_concludes(self):
        #  Main's cache jobs run on after the aggregate; the verdict is the
        #  aggregate's, and the watch does not wait for them.
        result = self.watch([
            state("in_progress", [job(1, "documents"),
                                  job(2, "gate", status="in_progress"),
                                  job(3, "linux-release-main-cache",
                                      status="in_progress")]),
            state("in_progress", [job(1, "documents"), job(2, "gate"),
                                  job(3, "linux-release-main-cache",
                                      status="in_progress")]),
        ], "--run=7", "--verdict")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("its verdict, the `gate` job, is success",
                      result.stdout)
        self.assertIn("still running, outside the verdict:"
                      " linux-release-main-cache", result.stdout)

    def test_verdict_names_every_failure_before_it(self):
        result = self.watch([
            state("in_progress", [job(1, "scripts", conclusion="failure"),
                                  job(2, "gate", status="in_progress")]),
            state("in_progress", [job(1, "scripts", conclusion="failure"),
                                  job(2, "gate", conclusion="failure")]),
        ], "--run=7", "--verdict")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("is failure", result.stdout)
        self.assertIn("  failed: scripts", result.stdout)

    def test_verdict_and_all_are_exclusive(self):
        result = self.watch([state("completed", [], "success")], "--run=7",
                            "--verdict", "--all")
        self.assertEqual(result.returncode, 2, result.stdout)

    def test_a_timing_failure_with_every_board_passed_is_named_so(self):
        result = self.watch([
            state("completed", [job(1, "board-bundles"),
                                job(2, "board-rp2040"),
                                job(3, "measure-time-darwin-arm64",
                                    conclusion="failure"),
                                job(4, "gate", conclusion="failure")],
                  conclusion="failure"),
        ], "--run=7", "--all")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("a timing failure, not a boards one", result.stdout)
        self.assertIn("gh run rerun 7 --failed", result.stdout)

    def test_a_failed_board_leg_is_not_a_timing_failure(self):
        result = self.watch([
            state("completed", [job(2, "board-rp2040", conclusion="failure"),
                                job(3, "measure-time-linux-x86-64",
                                    conclusion="failure"),
                                job(4, "gate", conclusion="failure")],
                  conclusion="failure"),
        ], "--run=7", "--all")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertNotIn("timing failure", result.stdout)
        self.assertNotIn("rerun", result.stdout)

    def test_the_failure_kinds(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import gate_watch

        def jobs(*pairs):
            return [{"name": name, "conclusion": conclusion}
                    for name, conclusion in pairs]
        self.assertIsNone(gate_watch.failure_kind(jobs(("gate", "success"))))
        self.assertEqual(gate_watch.failure_kind(jobs(
            ("board-esp32", "success"), ("measure-time-linux-arm64", "failure"),
            ("gate", "failure"))), "timing")
        self.assertEqual(gate_watch.failure_kind(jobs(
            ("board-esp32", "success"), ("gate", "failure"))), "aggregate")
        self.assertEqual(gate_watch.failure_kind(jobs(
            ("board-bundles", "failure"), ("measure-time-linux-arm64", "failure"),
            ("gate", "failure"))), "jobs")
        self.assertEqual(gate_watch.failure_kind(jobs(
            ("documents", "failure"), ("measure-time-linux-arm64", "failure"))),
            "jobs")
        self.assertEqual(gate_watch.failure_kind(jobs(
            ("board-esp32", "cancelled"), ("gate", "failure"))), "jobs")

    def test_a_run_that_succeeds_exits_zero(self):
        result = self.watch([
            state("in_progress", [job(1, "documents")]),
            state("completed", [job(1, "documents"), job(2, "gate")],
                  conclusion="success"),
        ], "--commit=" + "a" * 40)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("following gate run 7 (push on main)", result.stdout)

    def test_a_named_event_and_branch_are_waited_for(self):
        #  Right after a promotion GitHub lists only the branch's finished
        #  runs of the commit; the caller names main's push and the watcher
        #  asks for exactly that until it is listed.
        (self.states.parent / "states.json.unlisted").write_text("2")
        result = self.watch([
            state("completed", [job(1, "gate")], conclusion="success"),
        ], "--commit=" + "a" * 40, "--event=push", "--branch=main")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            result.stdout.count("no push on main gate run for aaaaaaaaaaaa yet"),
            2, result.stdout)
        listed = [query for query in self.queries() if "oid:" in query]
        self.assertEqual(len(listed), 3)

    def test_an_event_with_a_run_number_is_refused(self):
        result = self.watch([state("completed", [job(1, "gate")],
                                   conclusion="success")],
                            "--run=7", "--event=push")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("--run already names one", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_a_short_hash_is_asked_for_in_full(self):
        head = subprocess.run(("git", "rev-parse", "HEAD"), cwd=ROOT,
                              check=True, capture_output=True,
                              text=True).stdout.strip()
        result = self.watch([state("completed", [job(1, "gate")],
                                   conclusion="success")],
                            "--commit=" + head[:8])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.asked_for(), head)

    def test_a_name_that_is_no_commit_is_refused_at_once(self):
        result = self.watch([state("completed", [job(1, "gate")],
                                   conclusion="success")],
                            "--commit=0decafbad")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("names no commit in this clone", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_a_rerun_job_is_judged_by_its_latest_attempt(self):
        failed = job(2, "scripts", conclusion="failure")
        failed["run_attempt"] = 1
        passed = job(3, "scripts")
        passed["run_attempt"] = 2
        result = self.watch([state("completed", [job(1, "documents"), failed,
                                                 passed], conclusion="success",
                                   attempt=2)],
                            "--run=7", "--all")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("FAILED", result.stdout)
        self.assertIn("judged on 2 jobs", result.stdout)

    def test_a_failure_being_rerun_is_not_the_verdict(self):
        #  The watcher starts while attempt 2 reruns the failed jobs.  The
        #  aggregate's new attempt is not listed until its needs end, so
        #  its old failure is the latest one listed for a while.
        old_scripts = attempt(1, job(2, "scripts", conclusion="failure"))
        old_gate = attempt(1, job(3, "gate", conclusion="failure"))
        new_scripts = attempt(2, job(4, "scripts"))
        new_gate = attempt(2, job(5, "gate"))
        states = [
            state("in_progress", [job(1, "documents"), old_scripts, old_gate,
                                  attempt(2, job(4, "scripts",
                                                 status="in_progress"))],
                  attempt=2),
            state("completed", [job(1, "documents"), old_scripts, old_gate,
                                new_scripts, new_gate],
                  conclusion="success", attempt=2),
        ]
        for arguments in (("--run=7", "--all"), ("--run=7",)):
            for suffix in (".count", ".calls"):
                (self.states.parent / ("states.json" + suffix)).unlink(
                    missing_ok=True)
            result = self.watch(states, *arguments)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("failure    gate in attempt 1; the run is at "
                          "attempt 2, which may replace it", result.stdout)
            self.assertNotIn("FAILED", result.stdout)
            self.assertNotIn("failed jobs:", result.stdout)
            self.assertIn("run 7: success, judged on 3 jobs", result.stdout)
            self.assertIn("failed in an earlier attempt and since replaced, "
                          "not part of the verdict: gate, scripts",
                          result.stdout)

    def test_an_earlier_failure_no_rerun_replaced_still_fails_the_run(self):
        #  Attempt 2 reran one other job; `scripts` keeps its failure.
        old_scripts = attempt(1, job(2, "scripts", conclusion="failure"))
        result = self.watch([
            state("in_progress", [old_scripts,
                                  attempt(2, job(4, "compiler",
                                                 status="in_progress"))],
                  attempt=2),
            state("completed", [old_scripts, attempt(2, job(4, "compiler"))],
                  conclusion="failure", attempt=2),
        ], "--run=7")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAILED: scripts", result.stdout)
        self.assertIn("failed jobs: scripts", result.stdout)

    def test_a_run_of_more_than_a_page_of_jobs_is_read_whole(self):
        #  GraphQL gives a hundred check runs to a page; the rest of a run
        #  of 171 is asked for after the first page's cursor.
        jobs = [job(number, "lane-%d" % number) for number in range(1, 172)]
        result = self.watch([state("completed", jobs, conclusion="success")],
                            "--run=7")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("judged on 171 jobs", result.stdout)
        runs = [query for query in self.queries() if "resource(" in query]
        self.assertIn('after: "100"', runs[-1])
        self.assertNotIn("after:", runs[-2])

    def test_one_query_asks_for_a_run_and_its_jobs(self):
        #  The REST listing cost a run view and a page per thirty jobs at
        #  every poll; the GraphQL query is one request.
        jobs = [job(number, "lane-%d" % number) for number in range(1, 60)]
        result = self.watch([state("in_progress", jobs),
                             state("completed", jobs, conclusion="success")],
                            "--run=7")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.calls()), 2, self.calls())

    def test_a_server_error_is_asked_again(self):
        (self.states.parent / "states.json.fail").write_text(json.dumps(
            [2, "gh: Server Error (HTTP 502)"]))
        result = self.watch([state("completed", [job(1, "gate")],
                                   conclusion="success")], "--run=7")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("asking again"), 2, result.stdout)
        self.assertIn("gh: Server Error (HTTP 502); asking again (2 of 4)",
                      result.stdout)

    def test_a_broken_connection_or_rate_limit_is_asked_again(self):
        for said in ("Get \"https://api.github.com/repos\": read tcp: "
                     "connection reset by peer",
                     "gh: API rate limit exceeded (HTTP 429)",
                     "dial tcp: i/o timeout"):
            with self.subTest(said=said):
                (self.states.parent / "states.json.fail").write_text(
                    json.dumps([1, said]))
                result = self.watch([state("completed", [job(1, "gate")],
                                           conclusion="success")], "--run=7")
                self.assertEqual(result.returncode, 0,
                                 result.stdout + result.stderr)
                self.assertIn("asking again (2 of 4)", result.stdout)

    def test_a_request_that_stays_unanswered_is_named_without_a_traceback(self):
        (self.states.parent / "states.json.fail").write_text(json.dumps(
            [99, "gh: Server Error (HTTP 502)"]))
        result = self.watch([state("completed", [job(1, "gate")],
                                   conclusion="success")], "--run=7")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("gate_watch: GitHub did not answer: gh api graphql "
                      "(gate runs 7)", result.stderr)
        self.assertIn("HTTP 502", result.stderr)
        self.assertEqual(
            len([call for call in self.calls() if call[0] == "api"]), 4)

    def test_a_refusal_that_is_no_server_error_is_not_asked_again(self):
        (self.states.parent / "states.json.fail").write_text(json.dumps(
            [99, "gh: Not Found (HTTP 404)"]))
        result = self.watch([state("completed", [job(1, "gate")],
                                   conclusion="success")], "--run=7")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("HTTP 404", result.stderr)
        self.assertEqual(
            len([call for call in self.calls() if call[0] == "api"]), 1)

    def test_a_cancelled_run_is_neither_pass_nor_failure(self):
        result = self.watch([
            state("completed", [job(1, "compiler", conclusion="cancelled")],
                  conclusion="cancelled"),
        ], "--run=7")
        self.assertEqual(result.returncode, 2, result.stdout)


class SharedPoller(Fixture):
    """Watches read one poller's answers instead of each asking GitHub."""

    def setUp(self):
        super().setUp()
        self.addCleanup(self.stop_poller)

    def stop_poller(self):
        found = self.shared / "poller.json"
        if found.exists():
            pid = json.loads(found.read_text())["pid"]
            try:
                os.kill(pid, 15)
            except ProcessLookupError:
                pass

    def environment(self, **settings):
        return {**os.environ, "STATES": str(self.states),
                "GH_REPO": "example/landin", "WORKFLOW": WORKFLOW_PATH,
                "LANDIN_GATE_WATCH_DIR": str(self.shared),
                "LANDIN_GATE_WATCH_FLOOR": "0.2",
                "LANDIN_GATE_WATCH_IDLE": "1",
                "PATH": "%s%s%s" % (self.temporary.name, os.pathsep,
                                    os.environ["PATH"]),
                **{"LANDIN_GATE_WATCH_" + name: str(value)
                   for name, value in settings.items()}}

    def start(self, *arguments, **settings):
        return subprocess.Popen(
            [sys.executable, str(WATCH), "--interval=0.2", *arguments],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=self.environment(**settings), cwd=ROOT)

    def finish(self, process):
        out, err = process.communicate(timeout=HANG)
        return process.returncode, out + err

    def running(self, polls):
        """POLLS states of a running run, then its success."""
        return [state("in_progress", [job(1, "documents"),
                                      job(2, "gate", status="in_progress")])
                ] * polls + [state("completed", [job(1, "documents"),
                                                 job(2, "gate")],
                                   conclusion="success")]

    def test_two_watches_share_one_query_a_poll(self):
        self.states.write_text(json.dumps(self.running(25)))
        first = self.start("--run=7")
        second = self.start("--run=8", "--all")
        for process in (first, second):
            status, out = self.finish(process)
            self.assertEqual(status, 0, out)
            self.assertIn("success    gate", out)
        both = [query for query in self.queries()
                if "r7: resource" in query and "r8: resource" in query]
        self.assertTrue(both, self.queries())
        self.assertFalse((self.shared / "follow").exists()
                         and list((self.shared / "follow").iterdir()))

    def test_the_poller_ends_once_nothing_is_followed(self):
        self.states.write_text(json.dumps(self.running(1)))
        status, out = self.finish(self.start("--run=7"))
        self.assertEqual(status, 0, out)
        pid = json.loads((self.shared / "poller.json").read_text())["pid"]
        deadline = time.time() + 30
        while time.time() < deadline and "ending" not in (
                self.shared / "poller.log").read_text():
            time.sleep(0.1)
        self.assertIn("nothing followed for 1 s; ending",
                      (self.shared / "poller.log").read_text())
        time.sleep(0.5)
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_a_dead_poller_is_started_again(self):
        #  poller.json left by a poller that is gone, its lock free.
        self.shared.mkdir()
        (self.shared / "poller.json").write_text(json.dumps(
            {"pid": 2 ** 22 + 1, "polled": 0}))
        self.states.write_text(json.dumps(self.running(1)))
        status, out = self.finish(self.start("--run=7"))
        self.assertEqual(status, 0, out)
        self.assertIn("the shared gate poller had ended; started it again",
                      out)

    def test_a_stuck_poller_is_routed_around(self):
        #  A poller holds the lock and answers nothing: the watch asks
        #  GitHub itself and says so.
        import fcntl
        self.shared.mkdir()
        lock = open(self.shared / "poller.lock", "a")
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX)
        self.states.write_text(json.dumps(self.running(0)))
        status, out = self.finish(self.start("--run=7", STUCK=1))
        self.assertEqual(status, 0, out)
        self.assertIn("has not answered for", out)
        self.assertIn("asking GitHub directly meanwhile", out)

    def test_a_commit_is_waited_for_through_the_poller(self):
        (self.states.parent / "states.json.unlisted").write_text("2")
        self.states.write_text(json.dumps(self.running(0)))
        status, out = self.finish(self.start(
            "--commit=" + "a" * 40, "--event=push", "--branch=main"))
        self.assertEqual(status, 0, out)
        self.assertIn("no push on main gate run for aaaaaaaaaaaa yet", out)
        self.assertIn("following gate run 7 (push on main)", out)

    def test_a_refusal_ends_the_watch_with_the_pollers_error(self):
        (self.states.parent / "states.json.fail").write_text(json.dumps(
            [99, "gh: Not Found (HTTP 404)"]))
        self.states.write_text(json.dumps(self.running(0)))
        status, out = self.finish(self.start("--run=7"))
        self.assertEqual(status, 3, out)
        self.assertIn("HTTP 404", out)
        self.assertNotIn("Traceback", out)


if __name__ == "__main__":
    unittest.main()
