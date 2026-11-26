#!/usr/bin/env python3
"""Follow a gate run and return at its first failed job.

A failed gate says so only when its final `gate` job runs, after every
other lane: a scripts failure at eleven minutes was reported at seventy-one,
a Darwin parity failure at twelve was reported at 135.  `gh run watch`
waits for the same end.  This prints each job as it finishes and exits as
soon as one fails, naming its failed step and the command that shows the
log, so the fix can start while the other lanes run on.  Pushing the fix
cancels the superseded run, because the gate's concurrency group does.

    python3 scripts/gate_watch.py [--run ID | --commit SHA] [--interval S]
                                  [--all | --verdict] [--event E]
                                  [--branch B]

`--all` follows the run to its end instead and names every failed job,
for a round whose fixes should all go in one push: returning at the first
failure once left a second failed lane of the same run unseen, and the
next push failed on it again.  Each failed job is named again at the end
with the step it failed at, so a second cause is not lost among the first's
lines.

`--verdict` follows the run until its aggregate `gate` job concludes,
naming every failure before it, and returns then with that job's verdict:
on main's push the jobs that save main's caches run on after it, are no
evidence and took the promotion token seven to nine minutes longer.

With neither, it follows the gate run for HEAD, waiting for one to appear.
A commit may be anything `git rev-parse` names here, a short hash among
them; GitHub matches only a full one, so it is expanded before asking, and
a name that is neither a commit here nor a full hash is refused rather
than waited for.

One commit can have several gate runs: a branch's push, a boards dispatch
of the same commit, and main's push once it is promoted.  The first line
says which run is followed, with its event and branch.  `--event` and
`--branch` narrow the choice and wait for a run of that kind, so
`--commit C --event push --branch main` started right after a promotion
waits for main's own gate rather than following the branch's finished
dispatch, which is all GitHub lists for the first seconds.

A job is judged by its latest attempt, read from the complete listing.  A
failure left from an earlier attempt, while a rerun is still replacing
jobs, is printed as such and does not end the watch: it counts only if it
is still the job's latest attempt when the run ends.  Failures a rerun
replaced are named apart from the verdict.

Each poll is one query to GitHub's GraphQL API, for the run's status and
every attempt's check runs, which are its jobs; GraphQL's quota is apart
from REST's, which the job listing's pages once spent in an hour for every
watch on the host.  A server error, a rate limit or a hung request is asked
again a bounded number of times.  A request that still fails is named, with
GitHub's answer, and ends the watch with status 3.  Only the command that
shows a failed job's log, printed for whoever reads it, is REST's.

A failed run whose board legs all passed and whose only failures are the
timing jobs, `measure-time-*` and the aggregate after them, is named a
timing failure rather than a boards one, with the command that re-runs only
the failed jobs once their log reads as noise (docs/process.md, physical
boards and promotion).  A failure of the aggregate alone, every job before
it passed, is its verdict or its cycles comparison: re-running it would
judge the same figures again.

The exit status is 0 when the run succeeded, 1 when a job failed, and 2
when the run ended otherwise, for instance cancelled by a newer push, and
3 when GitHub could not be asked.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

FAILED = ("failure", "timed_out", "startup_failure")
#  Times one request is asked while GitHub answers a server error.
TRIES = 4
#  A rate limit and a connection that broke before an answer are asked
#  again as a server error is: one of them ended a watch with exit 3.
SERVER_ERROR = re.compile(r"HTTP (5\d\d|429)|timed? ?out|connection "
                          r"(reset|refused)|unexpected EOF|rate.?limit",
                          re.IGNORECASE)
#  Seconds before one request is called hung and asked again.
REQUEST_LIMIT = 120
#  Seconds between those tries; main lowers it to a shorter --interval.
retry_pause = 5.0


class Unanswered(Exception):
    """A request GitHub did not answer, with what `gh` said."""


def gh(*arguments, label=None):
    """`gh ARGUMENTS`'s JSON answer, asking again after a server error.

    A 502 from the job listing once ended the watch with a traceback.  A
    server error, a rate limit or a request hung past REQUEST_LIMIT is
    asked again TRIES times; any other refusal, or the last server error,
    raises Unanswered naming the request, by LABEL when given rather than
    by a query's whole text.
    """
    said = ""
    named = "gh %s" % (" ".join(arguments[:2]) + " (%s)" % label if label
                       else " ".join(arguments))
    for attempt in range(1, TRIES + 1):
        try:
            done = subprocess.run(("gh",) + arguments, capture_output=True,
                                  text=True, timeout=REQUEST_LIMIT)
        except subprocess.TimeoutExpired:
            said = "timed out after %d s" % REQUEST_LIMIT
        else:
            if done.returncode == 0:
                return json.loads(done.stdout)
            said = (done.stderr.strip() or done.stdout.strip()
                    or "exit status %d" % done.returncode)
        if not SERVER_ERROR.search(said):
            break
        if attempt < TRIES:
            print("%s: %s; asking again (%d of %d)"
                  % (named, said.splitlines()[-1], attempt + 1, TRIES),
                  flush=True)
            time.sleep(retry_pause * attempt)
    raise Unanswered("%s\n  %s" % (named, said))


def full_commit(name):
    """The full hash `name` stands for, or None when it names nothing here.

    GitHub compares the whole hash, so a short one matches no run, and the
    watcher used to wait for ever beside a run that had passed.  A full
    hash this clone lacks is still a commit GitHub may know.
    """
    found = subprocess.run(
        ("git", "rev-parse", "--verify", "--quiet", name + "^{commit}"),
        capture_output=True, text=True)
    if found.returncode == 0:
        return found.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", name):
        return name
    return None


# ------------------------------------------------------ GitHub's GraphQL API
#
#  Four items' watches spent the account's 5,000 REST requests an hour in
#  one hour: each poll was a run view and a job listing of four pages.  One
#  GraphQL query answers the status and every check run of several runs and
#  the gate runs of several commits at once, and GraphQL keeps a quota apart
#  from REST's, of points: such a query costs one.  A job's check run is the
#  job: the same number, the same name and conclusion.

#  The GitHub Actions app, whose check suites are the workflow runs.
ACTIONS_APP = 15368
WORKFLOW = ".github/workflows/gate.yml"
#  Check runs to a page; GraphQL's limit.
CHECKS_PAGE = 100

RUN_FIELDS = """databaseId runAttempt event url displayTitle createdAt
file { path }
checkSuite { status conclusion branch { name }
  checkRuns(first: %d%%s, filterBy: {checkType: ALL}) {
    totalCount pageInfo { hasNextPage endCursor }
    nodes { id databaseId name status conclusion startedAt completedAt } } }
""" % CHECKS_PAGE

COMMIT_FIELDS = """checkSuites(first: 50, filterBy: {appId: %d}) { nodes {
  status conclusion branch { name }
  workflowRun { databaseId runAttempt event url displayTitle createdAt
    file { path } } } }""" % ACTIONS_APP


def repository(cwd=None):
    """OWNER/NAME of the GitHub repository: $GH_REPO, as `gh` reads it, or
    the `origin` of the clone at CWD."""
    named = os.environ.get("GH_REPO", "")
    if not named:
        url = subprocess.run(("git", "remote", "get-url", "origin"), cwd=cwd,
                             capture_output=True, text=True).stdout.strip()
        found = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", url)
        named = found.group(1) if found else ""
    if not named:
        named = gh("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]
    return named.split("github.com/")[-1]


def graphql(query, label):
    """The data GitHub's GraphQL API answers QUERY with; LABEL names the
    request when it is not answered."""
    return gh("api", "graphql", "-f", "query=" + query, label=label)["data"]


def lower(value):
    return (value or "").lower()


def checks_of(suite):
    return [{"node": check["id"], "id": check["databaseId"],
             "name": check["name"], "status": lower(check["status"]),
             "conclusion": lower(check["conclusion"]),
             "started_at": check.get("startedAt") or "",
             "completed_at": check.get("completedAt") or ""}
            for check in suite["checkRuns"]["nodes"]]


def ask(repo, runs=(), commits=()):
    """One query for RUNS' views and COMMITS' gate runs.

    Returns ({run: view or None}, {commit: [run, newest first] or None}),
    None for a run or commit GitHub does not know.  A view holds the run's
    status, conclusion, url, attempt, event, branch and title, and `checks`,
    every attempt's check runs; a run of more than a page of them is asked
    again for the rest, those runs alone.
    """
    owner, name = repo.split("/", 1)
    parts = ["r%d: resource(url: \"https://github.com/%s/actions/runs/%d\")"
             " { ... on WorkflowRun { %s } }" % (run, repo, run,
                                                  RUN_FIELDS % "")
             for run in runs]
    if commits:
        parts.append("repository(owner: \"%s\", name: \"%s\") { %s }" % (
            owner, name, " ".join(
                "c%d: object(oid: \"%s\") { ... on Commit { %s } }"
                % (index, commit, COMMIT_FIELDS)
                for index, commit in enumerate(commits))))
    label = "gate runs %s" % " ".join(
        [str(run) for run in runs] + [commit[:12] for commit in commits])
    data = graphql("{ %s }" % " ".join(parts), label)
    views, cursors = {}, {}
    for run in runs:
        found = data.get("r%d" % run)
        if not found or not found.get("checkSuite"):
            views[run] = None
            continue
        suite = found["checkSuite"]
        views[run] = {"run": run, "status": lower(suite["status"]),
                      "conclusion": lower(suite["conclusion"]),
                      "url": found["url"], "attempt": found["runAttempt"],
                      "event": found["event"],
                      "headBranch": (suite.get("branch") or {}).get("name")
                      or "",
                      "displayTitle": found.get("displayTitle") or "",
                      "checks": checks_of(suite),
                      "total": suite["checkRuns"]["totalCount"]}
        page = suite["checkRuns"]["pageInfo"]
        if page["hasNextPage"]:
            cursors[run] = page["endCursor"]
    while cursors:
        more = graphql("{ %s }" % " ".join(
            "r%d: resource(url: \"https://github.com/%s/actions/runs/%d\")"
            " { ... on WorkflowRun { %s } }" % (
                run, repo, run, RUN_FIELDS % (", after: \"%s\"" % cursor))
            for run, cursor in cursors.items()), label + " (more checks)")
        for run in list(cursors):
            suite = (more.get("r%d" % run) or {}).get("checkSuite")
            if not suite or not suite["checkRuns"]["nodes"]:
                raise Unanswered("the check runs of run %d ended at %d of"
                                 " its %d" % (run, len(views[run]["checks"]),
                                              views[run]["total"]))
            views[run]["checks"].extend(checks_of(suite))
            page = suite["checkRuns"]["pageInfo"]
            cursors[run] = page["endCursor"] if page["hasNextPage"] else None
            if cursors[run] is None:
                del cursors[run]
    listed = {}
    for index, commit in enumerate(commits):
        found = (data.get("repository") or {}).get("c%d" % index)
        if found is None:
            listed[commit] = None
            continue
        gates = []
        for suite in found["checkSuites"]["nodes"]:
            run = suite.get("workflowRun")
            if not run or (run.get("file") or {}).get("path") != WORKFLOW:
                continue
            gates.append({"databaseId": run["databaseId"],
                          "event": run["event"],
                          "headBranch": (suite.get("branch") or {}).get(
                              "name") or "",
                          "status": lower(suite["status"]),
                          "conclusion": lower(suite["conclusion"]),
                          "displayTitle": run.get("displayTitle") or "",
                          "createdAt": run.get("createdAt") or "",
                          "attempt": run.get("runAttempt") or 1,
                          "url": run.get("url") or ""})
        listed[commit] = sorted(gates, key=lambda run: -run["databaseId"])
    return views, listed


def steps_of(nodes):
    """{check node: [{name, conclusion}]} for the check runs NODES."""
    if not nodes:
        return {}
    data = graphql("{ nodes(ids: [%s]) { ... on CheckRun { id steps(first:"
                   " 100) { nodes { name number conclusion } } } } }"
                   % ", ".join('"%s"' % node for node in nodes),
                   "the steps of %d failed jobs" % len(nodes))
    return {found["id"]: [{"name": step["name"],
                           "conclusion": lower(step["conclusion"])}
                          for step in found["steps"]["nodes"]]
            for found in data["nodes"] if found}


def runs_of_commit(commit, event=None, branch=None, repo=None):
    """COMMIT's gate runs, newest first, of EVENT and BRANCH when given, in
    the fields `gh run list --json` names: databaseId, event, headBranch,
    status, conclusion, displayTitle, createdAt, attempt."""
    _, listed = ask(repo or repository(), commits=[commit])
    return [run for run in listed[commit] or []
            if (not event or run["event"] == event)
            and (not branch or run["headBranch"] == branch)]


def find_run(commit, interval, event=None, branch=None, source=None):
    """The newest gate run of COMMIT, of EVENT and BRANCH when given.

    Waits until GitHub lists one.  Without EVENT and BRANCH the newest run
    of any kind is taken, which right after a promotion is the branch's
    finished run, not main's.
    """
    kind = " ".join(part for part in (event, "on " + branch if branch else "")
                    if part)
    source = source or Direct()
    while True:
        runs = [run for run in source.runs(commit)
                if (not event or run["event"] == event)
                and (not branch or run["headBranch"] == branch)]
        if runs:
            return runs[0]["databaseId"]
        print("no %sgate run for %s yet" % (kind + " " if kind else "",
                                            commit[:12]), flush=True)
        time.sleep(interval)


def split(view):
    """A view's jobs, each name's latest attempt, and the jobs of earlier
    attempts that a later attempt of their name replaced.

    `gh run view --json jobs` once named three of a run's 47 jobs, and the
    watcher called the run green on those three, so every attempt's check
    runs are read.  A check run says no attempt: a re-run, of every job or
    of the failed ones, lists every job of the run again under a new number
    (the jobs it does not run are copied, with their old times), so a
    name's check runs in the order of their numbers are its attempts.  A
    run of one attempt keeps every job of a name.
    """
    named = {}
    for check in sorted(view["checks"], key=lambda check: check["id"]):
        named.setdefault(check["name"], []).append(check)
    latest, replaced = [], []
    for checks in named.values():
        if view["attempt"] <= 1:
            latest.extend((1, check) for check in checks)
            continue
        replaced.extend((number, check)
                        for number, check in enumerate(checks[:-1], 1))
        latest.append((len(checks), checks[-1]))

    def shown(number, check):
        return {"databaseId": check["id"], "name": check["name"],
                "status": check["status"], "conclusion": check["conclusion"],
                "attempt": number, "startedAt": check["started_at"],
                "completedAt": check["completed_at"],
                "node": check.get("node"),
                "steps": check.get("steps") or []}
    return ([shown(*pair) for pair in latest],
            [shown(*pair) for pair in replaced])


def add_steps(jobs, known):
    """Give each failed job of JOBS its steps, asking GitHub only for those
    KNOWN, {check node: steps}, does not hold yet."""
    wanted = [job["node"] for job in jobs if job["conclusion"] in FAILED
              and job.get("node") and job["node"] not in known]
    known.update(steps_of(wanted))
    for job in jobs:
        if job.get("node") in known:
            job["steps"] = known[job["node"]]


class Direct:
    """Asks GitHub itself at each poll."""

    def __init__(self, repo=None):
        self.repo = repo
        self.steps = {}

    def name(self):
        if self.repo is None:
            self.repo = repository()
        return self.repo

    def view(self, run):
        views, _ = ask(self.name(), runs=[run])
        if views[run] is None:
            raise Unanswered("GitHub names no workflow run %d in %s"
                             % (run, self.name()))
        return views[run]

    def runs(self, commit):
        _, listed = ask(self.name(), commits=[commit])
        return listed[commit] or []


def jobs_of(run, source=None, view=None):
    """RUN's jobs, each name's latest attempt, and the earlier attempts'
    jobs replaced since, each failed one with its steps."""
    source = source or Direct()
    view = view or source.view(run)
    jobs, replaced = split(view)
    add_steps(jobs + replaced, source.steps)
    return jobs, replaced


TIMING_PREFIX = "measure-time-"
BOARD_JOBS = ("board-bundles", "board-")


def failure_kind(jobs):
    """What failed among JOBS, each name's latest attempt: None when nothing
    did, `timing` when only timing jobs (and the aggregate after them)
    failed while every board job passed, `aggregate` when only the
    aggregate `gate` failed, and `jobs` otherwise."""
    #  A cancelled job is missing evidence too: a cancelled leg makes the
    #  run a boards failure, and a cancelled timing job a timing one.
    failed = [job["name"] for job in jobs
              if job["conclusion"] in FAILED + ("cancelled",)]
    if not failed:
        return None
    boards_passed = all(job["conclusion"] in ("success", "skipped")
                        for job in jobs
                        if job["name"].startswith(BOARD_JOBS))
    timing = [name for name in failed if name.startswith(TIMING_PREFIX)]
    if boards_passed and timing and set(failed) <= set(timing) | {"gate"}:
        return "timing"
    if failed == ["gate"]:
        return "aggregate"
    return "jobs"


def minutes(job):
    started, completed = job.get("startedAt"), job.get("completedAt")
    if not started or not completed or started.startswith("0001"):
        return ""
    elapsed = (datetime.fromisoformat(completed.replace("Z", "+00:00"))
               - datetime.fromisoformat(started.replace("Z", "+00:00")))
    return " %.1f min" % (elapsed.total_seconds() / 60)


def log_commands(run, job, active):
    """The lines naming the command that shows failed JOB's log.

    `gh run view --log-failed` refuses while the run is ACTIVE, saying logs
    are available only when it completes; the job's own log endpoint
    answers as soon as the job has ended.  The pinned `gh` refuses to
    print that log to a terminal, because it holds the job's colour escape
    sequences, until told `--allow-escape-sequences`.
    """
    whole = "gh run view %s --job %s --log-failed" % (run, job["databaseId"])
    if not active:
        return ["log:    " + whole]
    return ["log:    gh api --allow-escape-sequences "
            "repos/{owner}/{repo}/actions/jobs/%s/logs" % job["databaseId"],
            "        (the job's whole log, readable while run %s is still "
            "active;" % run,
            "        once the run ends: %s)" % whole]


VERDICT_JOB = "gate"


def failed_step(job):
    """The name of the first step JOB failed at, or None."""
    steps = [step["name"] for step in job.get("steps", ())
             if step.get("conclusion") in FAILED]
    return steps[0] if steps else None


def watch(run, interval, every=False, verdict=False, source=None, view=None):
    """Follow RUN; the verdict is read from the last complete listing.

    A failed job of the run's current attempt ends the watch at once unless
    EVERY or VERDICT.  One left from an earlier attempt is held back while
    the run is active, because the rerun that made the newer attempt may be
    about to replace it; whether it failed the run is read when the run
    ends.  With VERDICT the watch ends when the aggregate job of the
    current attempt concludes, with its conclusion.  VIEW, when given, is
    the run as already asked for, taken as the first poll's.
    """
    source = source or Direct()
    reported = set()
    held_back = set()
    while True:
        view = view or source.view(run)
        jobs, replaced = jobs_of(run, source, view)
        ended = view["status"] == "completed"
        current = view.get("attempt") or max(
            [job["attempt"] for job in jobs] or [1])
        for job in jobs:
            if job["status"] != "completed" or job["databaseId"] in reported:
                continue
            failed = job["conclusion"] in FAILED
            if failed and not ended and job["attempt"] < current:
                if job["databaseId"] not in held_back:
                    held_back.add(job["databaseId"])
                    print("%-10s %s in attempt %d; the run is at attempt %d, "
                          "which may replace it"
                          % (job["conclusion"], job["name"], job["attempt"],
                             current), flush=True)
                continue
            reported.add(job["databaseId"])
            print("%-10s %s%s" % (job["conclusion"], job["name"], minutes(job)),
                  flush=True)
            if failed:
                step = failed_step(job)
                print("FAILED: %s%s" % (job["name"],
                                        " at %s" % step if step else ""))
                for line in log_commands(run, job, not ended):
                    print(line)
                print("run:    %s" % view["url"], flush=True)
                if not every and not verdict and not ended:
                    return 1
        aggregate = [job for job in jobs if job["name"] == VERDICT_JOB
                     and job["attempt"] >= current
                     and job["status"] == "completed"]
        if verdict and aggregate and not ended:
            failed = [job for job in jobs if job["conclusion"] in FAILED]
            going = [job["name"] for job in jobs
                     if job["status"] != "completed"]
            conclusion = aggregate[0]["conclusion"]
            print("run %s: its verdict, the `%s` job, is %s  %s"
                  % (run, VERDICT_JOB, conclusion, view["url"]))
            for job in failed:
                step = failed_step(job)
                print("  failed: %s%s" % (job["name"], " at %s" % step
                                          if step else ""))
            if going:
                print("still running, outside the verdict: %s"
                      % ", ".join(going))
            return 0 if conclusion == "success" else 1
        if ended:
            #  The verdict: this listing's failures and nothing remembered.
            failed = [job["name"] for job in jobs if job["conclusion"] in FAILED]
            earlier = sorted({job["name"] for job in replaced
                              if job["conclusion"] in FAILED}
                             - set(failed))
            print("run %s: %s, judged on %d jobs  %s"
                  % (run, view["conclusion"], len(jobs), view["url"]))
            if earlier:
                print("failed in an earlier attempt and since replaced, "
                      "not part of the verdict: %s" % ", ".join(earlier))
            if failed:
                print("failed jobs: %s" % ", ".join(failed))
                for job in jobs:
                    if job["conclusion"] in FAILED:
                        step = failed_step(job)
                        print("  %s: %s" % (job["name"], "at %s" % step
                                            if step else "no failed step"
                                            " listed"))
                kind = failure_kind(jobs)
                if kind == "timing":
                    print("a timing failure, not a boards one: every board "
                          "leg passed.  Read the failed timing log; if it "
                          "reads as noise, re-run only the failed jobs: "
                          "gh run rerun %s --failed" % run)
                elif kind == "aggregate":
                    print("only the aggregate failed: read its log (the "
                          "verdict or the cycles comparison); a rerun "
                          "judges the same figures again")
                return 1
            return 0 if view["conclusion"] == "success" else 2
        view = None
        time.sleep(interval)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--run", type=int)
    which.add_argument("--commit")
    parser.add_argument("--interval", type=float, default=30)
    ends = parser.add_mutually_exclusive_group()
    ends.add_argument("--all", action="store_true",
                      help="follow the run to its end, naming every failure")
    ends.add_argument("--verdict", action="store_true",
                      help="follow the run until its aggregate `gate` job "
                      "concludes, naming every failure, and return with "
                      "that verdict")
    parser.add_argument("--event", help="with a commit, wait for a run of "
                        "this event: push, workflow_dispatch, pull_request, "
                        "schedule")
    parser.add_argument("--branch", help="with a commit, wait for a run on "
                        "this branch")
    args = parser.parse_args(argv[1:])
    if args.run is not None and (args.event or args.branch):
        parser.error("--event and --branch choose among a commit's runs; "
                     "--run already names one")
    global retry_pause
    retry_pause = min(retry_pause, args.interval)
    run = args.run
    source = Direct()
    try:
        if run is None:
            commit = full_commit(args.commit or "HEAD")
            if commit is None:
                parser.error("%s names no commit in this clone; fetch it, or "
                             "give its full hash" % args.commit)
            run = find_run(commit, args.interval, args.event, args.branch,
                           source)
        about = source.view(run)
        print("following gate run %s (%s on %s)"
              % (run, about.get("event") or "unknown event",
                 about.get("headBranch") or "no branch"), flush=True)
        return watch(run, args.interval, args.all, args.verdict, source,
                     about)
    except Unanswered as error:
        print("gate_watch: GitHub did not answer: %s" % error, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
