#!/usr/bin/env python3
"""Why gate jobs failed, the lane table, and the selected gate in shadow.

The gate's history says why a job failed only to someone who reads its
log: the gate-time study of 2026-11-26 rebuilt the causes from 1,024 job
logs.  This script records them by rule, keeps the lane table the selected
gate reads, and computes that selection beside every complete gate without
skipping anything, in shadow mode (docs/process.md, "Failure causes
and the selection in shadow").

The cause of a failed job, the study's mechanical rule:

  - `outside`, by a signature, when its log matches one of the lane
    table's outside signatures (a mirror's 403, a probe's DMI timeout...),
    which the aggregate `gate` job records on the run as it ends;
  - `outside`, by `rerun`, when a later attempt of the same run, or a run
    of the identical tree, passed the same job;
  - `defect` when the branch's next push changed the tree;
  - `pending` while the branch has no next push, and `unresolved` when it
    pushed the same tree again.

The rule agreed with the study's readers on 90% of the jobs it called
defects and found 97% of theirs.

The lane table, `.github/gate-lanes.json`, groups the gate's jobs into
lanes.  Each lane declares the paths whose change reaches it, the targets
whose emitted code it runs, if it runs nothing else, and whether it checks
the evidence itself; `table --write` keeps the rest from the history: when
the lane was first seen, what it costs in job-minutes, and when it was last
the only lane to show a defect.  The table is in the tree, so the same tree
always selects the same lanes.

The selection keeps a lane when
  - its declared inputs changed since the base, the newest passed complete
    gate on this commit's history;
  - it runs emitted code and its targets' emission, read from the
    x86-64 determinism manifests, differs from the base's;
  - in the last eight weeks it was the only lane to show a defect, it is
    under four weeks old, it costs under five job-minutes, or it checks
    the evidence;
  - or the tree's hash draws it, one gate in four for each lane alone;
and every lane a kept lane needs.  The rest it would have skipped.  In
shadow mode the `inputs` job computes it, the `gate` job completes the
emission part from the manifests and records it on the run, and nothing
is skipped.

    fetch [--since DATE]       cache the gate's runs and jobs by GraphQL
    causes                     print each failed job's cause
    table [--write]            the lane table's kept figures and the
                               causes file, from the cached history
    shadow                     the shadow period: complete gates, the
                               lanes they would have skipped, the misses
    select                     (inputs job) the selection, as `shadow=`
    finish                     (gate job) the emission part, the record
    rerun RUN                  (gate-rerun.yml) re-run a branch run's
                               failed jobs once when every one of them
                               failed by an outside signature

Locally it asks GitHub's GraphQL API through `gh`, whose quota is apart
from REST's that the watches share; the jobs' logs, which only REST
serves, are read in the workflows with their own token.  The cache is
`~/.cache/landin/gate-history`, or $LANDIN_GATE_HISTORY.
"""
from datetime import datetime, timedelta, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / ".github/gate-lanes.json"
CAUSES = ROOT / ".github/gate-causes.jsonl"
#  gate.yml's node, from `gh api repos/OWNER/REPO/actions/workflows/gate.yml`.
WORKFLOW_NODE = "W_kwDOUHUaks4Vq8xu"
FAILED = ("FAILURE", "TIMED_OUT", "STARTUP_FAILURE")
#  Run once a complete gate ran its software lanes.
MARKER = "determinism / agree"
#  Annotation titles the `gate` job writes.
SHADOW_NOTE = "gate-shadow"
CAUSE_NOTE = "gate-causes"
#  Logs read in one run: a run with more failed jobs is past one cause.
MAX_LOGS = 12


def cache_dir():
    return Path(os.environ.get("LANDIN_GATE_HISTORY")
                or Path.home() / ".cache/landin/gate-history")


def when(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")) if text else None


# ------------------------------------------------------------ the lane table

def load_table(path=TABLE):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def write_table(table, path=TABLE):
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(table, stream, indent=1, sort_keys=False)
        stream.write("\n")


def lane_index(table):
    """Job name -> lane."""
    return {job: lane for lane, row in table["lanes"].items() for job in row["jobs"]}


def lane_of(name, index):
    """NAME's lane: the table's, or for a job the table no longer has, its
    name without a shard number."""
    if name in index:
        return index[name]
    found = re.match(r"^(determinism / manifest \([\w-]+) \d+\)$", name)
    if found:
        return found.group(1) + ")"
    found = re.match(r"^(.*)-\d$", name)
    return found.group(1) if found else name


def expand(globs, sets):
    """GLOBS with each `@set` replaced by the table's set of that name."""
    out = []
    for glob in globs:
        if glob.startswith("@"):
            out.extend(expand(sets[glob[1:]], sets))
        else:
            out.append(glob)
    return out


def reaches(paths, globs):
    """The first path of PATHS a glob of GLOBS matches, or None."""
    for path in paths:
        for glob in globs:
            if fnmatch.fnmatchcase(path, glob) or (
                    glob.endswith("/**") and path.startswith(glob[:-2])):
                return path
    return None


def signatures(table):
    return [(row["name"], re.compile(row["pattern"]))
            for row in table.get("signatures", [])]


STAMP = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ?")
#  Lines before a job's first error that a signature is looked for in.
WINDOW = 60


def failure_lines(log, window=WINDOW):
    """The lines that say why LOG's job failed: the WINDOW lines up to its
    first `##[error]` and the few errors beside it, or its last WINDOW.  A
    retry earlier in the job that met a mirror's 403 and then succeeded is
    no cause of a later failure."""
    lines = [STAMP.sub("", line) for line in log.splitlines()]
    for number, line in enumerate(lines):
        if line.startswith("##[error]"):
            return lines[max(0, number - window):number + 6]
    return lines[-window:]


def signature_of(log, patterns):
    """The first outside signature a line of LOG's failure matches, or
    None.  Lines lose their runner timestamp first."""
    for line in failure_lines(log):
        for name, pattern in patterns:
            if pattern.search(line):
                return name
    return None


# ------------------------------------------------------------------ GitHub

def gh_graphql(query):
    """Locally: `gh`, its GraphQL quota."""
    for attempt in range(4):
        done = subprocess.run(["gh", "api", "graphql", "-f", "query=" + query],
                              capture_output=True, text=True, timeout=120)
        if done.returncode == 0:
            answer = json.loads(done.stdout)
            if "errors" not in answer:
                return answer["data"]
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("GraphQL did not answer: %s" % (done.stderr or done.stdout)[:300])


def token_request(url, data=None, accept="application/vnd.github+json"):
    """In a workflow: the job's own token, never the shared one."""
    request = urllib.request.Request(url, data=data, headers={
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Accept": accept})
    if data is not None:
        request.method = "POST"
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def token_graphql(query):
    url = os.environ.get("GITHUB_GRAPHQL_URL", "https://api.github.com/graphql")
    answer = json.loads(token_request(url, json.dumps({"query": query}).encode()))
    if "errors" in answer:
        raise RuntimeError("GraphQL: %s" % answer["errors"][:1])
    return answer["data"]


def token_rest(path, data=None, raw=False):
    url = "%s/repos/%s/%s" % (os.environ.get("GITHUB_API_URL", "https://api.github.com"),
                              os.environ["GITHUB_REPOSITORY"], path)
    body = token_request(url, data)
    return body if raw else json.loads(body or b"{}")


RUN_FIELDS = """databaseId event createdAt
checkSuite { id status conclusion branch { name } commit { oid tree { oid } }
  checkRuns(first: 100, filterBy: {checkType: ALL}) {
    pageInfo { hasNextPage endCursor }
    nodes { id databaseId name conclusion startedAt completedAt } } }"""


def runs_page(graphql, cursor=None, first=20, fields=RUN_FIELDS):
    after = ', after: "%s"' % cursor if cursor else ""
    data = graphql('{ node(id: "%s") { ... on Workflow { runs(first: %d%s) {'
                   ' pageInfo { hasNextPage endCursor } nodes { %s } } } } }'
                   % (WORKFLOW_NODE, first, after, fields))
    return data["node"]["runs"]


def more_checks(graphql, suite, cursor):
    nodes = []
    while cursor:
        data = graphql('{ node(id: "%s") { ... on CheckSuite { checkRuns(first: 100,'
                       ' after: "%s", filterBy: {checkType: ALL}) { pageInfo'
                       ' { hasNextPage endCursor } nodes { id databaseId name'
                       ' conclusion startedAt completedAt } } } } }' % (suite, cursor))
        checks = data["node"]["checkRuns"]
        nodes += checks["nodes"]
        cursor = checks["pageInfo"]["endCursor"] if checks["pageInfo"]["hasNextPage"] else None
    return nodes


def notes(graphql, ids):
    """Check run id -> {annotation title: message} for the `gate` jobs."""
    found = {}
    for start in range(0, len(ids), 40):
        part = ids[start:start + 40]
        #  The aggregate writes few; 50 leaves room for warnings beside them.
        data = graphql('{ nodes(ids: [%s]) { ... on CheckRun { id annotations(first: 50)'
                       ' { nodes { title message } } } } }'
                       % ", ".join('"%s"' % node for node in part))
        for node in data["nodes"]:
            if node:
                found[node["id"]] = {row["title"]: row["message"]
                                     for row in node["annotations"]["nodes"]
                                     if row["title"] in (SHADOW_NOTE, CAUSE_NOTE)}
    return found


def normal(node, checks):
    suite = node["checkSuite"]
    return {"run": node["databaseId"], "event": node["event"], "created": node["createdAt"],
            "branch": (suite.get("branch") or {}).get("name"),
            "sha": suite["commit"]["oid"], "tree": suite["commit"]["tree"]["oid"],
            "status": suite["status"], "conclusion": suite["conclusion"],
            "jobs": [[c["databaseId"], c["name"], c["conclusion"], c["startedAt"],
                      c["completedAt"]] for c in checks],
            "gate_ids": [[c["id"], c["startedAt"]] for c in
                         sorted(checks, key=lambda c: c["databaseId"]) if c["name"] == "gate"]}


def fetch(graphql, directory, since):
    """Cache every gate run created since SINCE, newest first, until a page
    holds only runs already cached complete."""
    runs = directory / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    cursor, fetched = None, 0
    while True:
        page = runs_page(graphql, cursor)
        new, old = [], 0
        for node in page["nodes"]:
            if node["createdAt"] < since:
                old += 1
                continue
            path = runs / ("%d.json" % node["databaseId"])
            if path.exists() and json.loads(path.read_text())["status"] == "COMPLETED":
                old += 1
                continue
            suite = node["checkSuite"]
            checks = suite["checkRuns"]["nodes"]
            if suite["checkRuns"]["pageInfo"]["hasNextPage"]:
                checks += more_checks(graphql, suite["id"],
                                      suite["checkRuns"]["pageInfo"]["endCursor"])
            new.append(normal(node, checks))
        gate_ids = [node for run in new if run["status"] == "COMPLETED"
                    for node, _ in run["gate_ids"]]
        found = notes(graphql, gate_ids) if gate_ids else {}
        for run in new:
            #  Each attempt's aggregate, in order, with what it recorded.
            run["gates"] = [[started, found.get(node, {})]
                            for node, started in run.pop("gate_ids")]
            (runs / ("%d.json" % run["run"])).write_text(json.dumps(run))
        fetched += len(new)
        if not page["pageInfo"]["hasNextPage"] or old == len(page["nodes"]):
            return fetched
        cursor = page["pageInfo"]["endCursor"]


def cached_runs(directory):
    runs = []
    for path in sorted((directory / "runs").glob("*.json")):
        runs.append(json.loads(path.read_text()))
    runs.sort(key=lambda run: (run["created"], run["run"]))
    return runs


# --------------------------------------------------------------- the causes

def attempts(run):
    """Job name -> its check runs in attempt order."""
    by = {}
    for job in sorted(run["jobs"], key=lambda job: job[0]):
        by.setdefault(job[1], []).append(job)
    return by


def complete(run):
    """Whether RUN ran the software lanes, read from its marker job."""
    return any(job[1] == MARKER and job[2] not in (None, "SKIPPED") for job in run["jobs"])


def recorded_signature(run, job):
    """JOB's signature as the aggregate that ran after it recorded it."""
    for started, notes in run.get("gates", []):
        if started and job[4] and started >= job[4]:
            for part in (notes.get(CAUSE_NOTE) or "").split(";"):
                name, _, signature = part.strip().rpartition("=")
                if name == job[1] and signature != "-":
                    return signature
            return None
    return None


def shadow_note(run):
    """The selection the run's first aggregate recorded, or None."""
    for _, notes in run.get("gates", []):
        if SHADOW_NOTE in notes:
            return notes[SHADOW_NOTE]
    return None


def causes(runs, seeded=None):
    """One row per failed attempt of a job: the run, the job, its cause and
    what decided it.  SEEDED maps a job's id to a signature found apart."""
    seeded = seeded or {}
    by_branch, passed_on = {}, {}
    for run in runs:
        by_branch.setdefault(run["branch"], []).append(run)
        for name, tries in attempts(run).items():
            if tries[-1][2] == "SUCCESS":
                passed_on.setdefault((run["tree"], name), []).append(run["run"])
    rows = []
    for run in runs:
        later = [other for other in by_branch[run["branch"]]
                 if other["created"] > run["created"] and other["sha"] != run["sha"]
                 and other["event"] == "push"]
        for name, tries in attempts(run).items():
            if name == "gate":
                continue
            for number, job in enumerate(tries, 1):
                if job[2] not in FAILED:
                    continue
                signature = seeded.get(job[0]) or recorded_signature(run, job)
                if signature:
                    cause, by = "outside", signature
                elif any(other[2] == "SUCCESS" for other in tries[number:]):
                    cause, by = "outside", "rerun"
                elif [other for other in passed_on.get((run["tree"], name), [])
                      if other != run["run"]]:
                    cause, by = "outside", "same-tree"
                elif not later:
                    cause, by = "pending", "no-next-push"
                elif later[0]["tree"] != run["tree"]:
                    cause, by = "defect", "next-push"
                else:
                    cause, by = "unresolved", "same-tree-pushed"
                rows.append({"run": run["run"], "attempt": number, "job": name,
                             "date": run["created"][:10], "branch": run["branch"],
                             "cause": cause, "by": by})
    return rows


# ------------------------------------------------------------ table figures

def minutes(job):
    start, end = when(job[3]), when(job[4])
    if not start or not end or job[2] in (None, "SKIPPED"):
        return None
    return max(0.0, (end - start).total_seconds() / 60)


def figures(table, runs, rows, today):
    """Each lane's kept figures from the history, as of TODAY."""
    index = lane_index(table)
    ignored = set(table["rules"].get("ignored_branches", []))
    runs = [run for run in runs if run["branch"] not in ignored]
    rows = [row for row in rows if row["branch"] not in ignored]
    window = today - timedelta(weeks=table["rules"]["alone_weeks"])
    first, cost, shown, alone, outside = {}, {}, {}, {}, {}
    for run in runs:
        day = run["created"][:10]
        totals = {}
        for name, tries in attempts(run).items():
            lane = lane_of(name, index)
            first.setdefault(lane, day)
            spent = minutes(tries[-1])
            if spent is not None:
                totals[lane] = totals.get(lane, 0.0) + spent
        if complete(run) and when(run["created"]) >= window:
            for lane, spent in totals.items():
                cost.setdefault(lane, []).append(spent)
    by_run = {}
    for row in rows:
        lane = lane_of(row["job"], index)
        if row["cause"] == "defect":
            by_run.setdefault(row["run"], set()).add(lane)
            if when(row["date"] + "T00:00:00Z") >= window:
                shown[lane] = shown.get(lane, 0) + 1
        elif row["cause"] == "outside" and when(row["date"] + "T00:00:00Z") >= window:
            outside[lane] = outside.get(lane, 0) + 1
    dates = {row["run"]: row["date"] for row in rows}
    for run, lanes in by_run.items():
        if len(lanes) == 1:
            lane = next(iter(lanes))
            alone[lane] = max(alone.get(lane, ""), dates[run])
    out = {}
    for lane in table["lanes"]:
        out[lane] = {"first_seen": first.get(lane, today.date().isoformat()),
                     "minutes": round(statistics.median(cost[lane]), 1) if cost.get(lane) else None,
                     "alone": alone.get(lane), "defect_jobs": shown.get(lane, 0),
                     "outside_jobs": outside.get(lane, 0)}
    return out


KEPT = ("first_seen", "minutes", "alone", "defect_jobs", "outside_jobs")


def update_table(table, runs, rows, today):
    figured = figures(table, runs, rows, today)
    for lane, row in table["lanes"].items():
        found = figured[lane]
        #  A cache that starts later never makes a lane younger, nor
        #  forgets a day it was alone.
        if row.get("first_seen"):
            found["first_seen"] = min(row["first_seen"], found["first_seen"])
        if row.get("alone") and (found["alone"] or "") < row["alone"]:
            found["alone"] = row["alone"]
        row.update(found)
    table["history"] = {"from": runs[0]["created"][:10] if runs else None,
                        "to": runs[-1]["created"][:10] if runs else None,
                        "runs": len(runs), "failed_jobs": len(rows),
                        "updated": today.date().isoformat()}
    table["shadow"] = shadow_summary(table, runs, rows)
    return table


# ---------------------------------------------------------------- selection

def drawn(tree, lane, one_in):
    """Whether TREE's hash draws LANE, one tree in ONE_IN for each lane."""
    return int(hashlib.sha256(("%s:%s" % (tree, lane)).encode()).hexdigest()[:8], 16) % one_in == 0


def standing(row, rules, today):
    """Why LANE runs whatever changed, or None."""
    if row.get("always"):
        return "always"
    if row.get("physical"):
        return "physical: its own rule"
    if row.get("evidence"):
        return "checks the evidence"
    if not row.get("first_seen") or when(row["first_seen"] + "T00:00:00Z") > \
            today - timedelta(weeks=rules["new_weeks"]):
        return "under %d weeks old" % rules["new_weeks"]
    if row.get("minutes") is None:
        return "no cost measured yet"
    if row["minutes"] < rules["cheap_minutes"]:
        return "under %d job-minutes" % rules["cheap_minutes"]
    if row.get("alone") and when(row["alone"] + "T00:00:00Z") >= \
            today - timedelta(weeks=rules["alone_weeks"]):
        return "alone showed a defect on %s" % row["alone"]
    return None


def select(table, changed, tree, today, base):
    """Lane -> [verdict, why] before the emission is known: `keep`, `skip`,
    or `emission` for a lane the emission part decides."""
    rules, sets = table["rules"], table.get("sets", {})
    chosen = {}
    for lane, row in table["lanes"].items():
        why = standing(row, rules, today)
        if why:
            chosen[lane] = ["keep", why]
            continue
        if base is None:
            chosen[lane] = ["keep", "no passed complete gate on this history"]
            continue
        path = reaches(changed, expand(row.get("inputs", []), sets))
        if path:
            chosen[lane] = ["keep", "inputs: " + path]
        elif row.get("emission"):
            chosen[lane] = ["emission", ",".join(row["emission"])]
        elif drawn(tree, lane, rules["one_in"]):
            chosen[lane] = ["keep", "drawn"]
        else:
            chosen[lane] = ["skip", "sampled, not drawn"]
    return chosen


def close(table, chosen):
    """Keep every lane a kept lane needs."""
    queue = [lane for lane, (verdict, _) in chosen.items() if verdict == "keep"]
    while queue:
        lane = queue.pop()
        for need in table["lanes"][lane].get("needs", []):
            if chosen.get(need, ["keep"])[0] != "keep":
                chosen[need] = ["keep", "needed by " + lane]
                queue.append(need)
    return chosen


def emission_digests(manifest, target):
    return {key: value for key, value in manifest.items() if key.split("|")[1:2] == [target]}


def decide_emission(table, chosen, tree, ours, theirs):
    """Settle each `emission` lane by its targets' digests in OURS against
    THEIRS (merged manifests, or None when absent)."""
    for lane, (verdict, targets) in list(chosen.items()):
        if verdict != "emission":
            continue
        if not ours or not theirs:
            chosen[lane] = ["keep", "emission unknown"]
            continue
        moved = [target for target in targets.split(",")
                 if emission_digests(ours, target) != emission_digests(theirs, target)]
        if moved:
            chosen[lane] = ["keep", "emission changed: " + ",".join(moved)]
        elif drawn(tree, lane, table["rules"]["one_in"]):
            chosen[lane] = ["keep", "emission unchanged; drawn"]
        else:
            chosen[lane] = ["skip", "emission unchanged"]
    return close(table, chosen)


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()


BASE_FIELDS = """databaseId event createdAt
checkSuite { conclusion commit { oid }
  checkRuns(first: 5, filterBy: {checkType: ALL, checkName: "%s"}) { nodes { conclusion } } }""" % MARKER


def find_base(graphql, is_ancestor, pages=3):
    """The newest passed complete push run whose commit is an ancestor of
    HEAD, as (run, sha), or None."""
    cursor = None
    for _ in range(pages):
        page = runs_page(graphql, cursor, first=40, fields=BASE_FIELDS)
        for node in page["nodes"]:
            suite = node["checkSuite"]
            marks = [row["conclusion"] for row in suite["checkRuns"]["nodes"]]
            if node["event"] != "push" or suite["conclusion"] != "SUCCESS" \
                    or not marks or marks[-1] != "SUCCESS":
                continue
            sha = suite["commit"]["oid"]
            if is_ancestor(sha):
                return node["databaseId"], sha
        if not page["pageInfo"]["hasNextPage"]:
            return None
        cursor = page["pageInfo"]["endCursor"]
    return None


def ancestor(sha):
    return subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"], cwd=ROOT,
                          capture_output=True).returncode == 0


def compact(chosen):
    return ";".join("%s=%s:%s" % (lane, verdict, why.replace(";", ","))
                    for lane, (verdict, why) in sorted(chosen.items()))


def expanded(text):
    chosen = {}
    for part in text.split(";"):
        lane, _, rest = part.partition("=")
        verdict, _, why = rest.partition(":")
        if lane:
            chosen[lane] = [verdict, why]
    return chosen


def summary(table, chosen, base, final):
    """The step summary's Markdown."""
    skipped = sorted(lane for lane, (verdict, _) in chosen.items() if verdict == "skip")
    pending = sorted(lane for lane, (verdict, _) in chosen.items() if verdict == "emission")
    saved = sum(table["lanes"][lane].get("minutes") or 0 for lane in skipped)
    lines = ["## The selected gate, in shadow", "",
             "Nothing is skipped: this is what the selected gate would have done.", "",
             "Base: %s." % ("run %s, commit %s" % (base[0], base[1][:12]) if base
                            else "no passed complete gate on this history, so every lane")]
    lines.append("")
    lines.append("Would skip %d lanes, about %.0f job-minutes: %s." % (
        len(skipped), saved, ", ".join("`%s`" % lane for lane in skipped) or "none"))
    if pending and not final:
        lines.append("")
        lines.append("Decided by their emission at the end: %s."
                     % ", ".join("`%s`" % lane for lane in pending))
    lines += ["", "| lane | would | why |", "|---|---|---|"]
    for lane, (verdict, why) in sorted(chosen.items()):
        lines.append("| `%s` | %s | %s |" % (lane, {"keep": "run", "skip": "skip",
                                                  "emission": "emission"}[verdict], why))
    return "\n".join(lines) + "\n"


def read_manifests(directory):
    """The merged manifest of every JSON file under DIRECTORY, or None."""
    merged = {}
    if not directory or not Path(directory).is_dir():
        return None
    for path in sorted(Path(directory).rglob("*.json")):
        with open(path, encoding="utf-8") as stream:
            merged.update(json.load(stream))
    return merged or None


# ------------------------------------------------------------ shadow figures

def shadow_runs(runs):
    return [run for run in runs if (shadow_note(run) or "").startswith("base=")]


def shadow_summary(table, runs, rows):
    """The shadow period's figures: complete gates, misses and the rate."""
    index = lane_index(table)
    ignored = set(table["rules"].get("ignored_branches", []))
    gates = [run for run in shadow_runs(runs) if run["branch"] not in ignored]
    defects = {}
    for row in rows:
        if row["cause"] == "defect":
            defects.setdefault(row["run"], set()).add(lane_of(row["job"], index))
    misses, episodes, seen = [], 0, set()
    for run in gates:
        note = shadow_note(run)
        skipped = set(filter(None, note.partition(" skip=")[2].split(",")))
        shown = defects.get(run["run"], set())
        if shown and shown <= skipped:
            misses.append({"run": run["run"], "date": run["created"][:10],
                           "branch": run["branch"], "lanes": sorted(shown)})
            episode = (run["branch"], tuple(sorted(shown)))
            if episode not in seen:
                seen.add(episode)
                episodes += 1
    if gates:
        span = (when(gates[-1]["created"]) - when(gates[0]["created"])).days / 7 or 1 / 7
    else:
        span = 0
    return {"since": gates[0]["created"][:10] if gates else None,
            "complete_gates": len(gates), "target_gates": table["rules"]["shadow_gates"],
            "weeks": round(span, 1), "missed_runs": len(misses), "missed_defects": episodes,
            "per_week": round(episodes / span, 2) if span else None,
            "study_per_week": table["rules"]["study_misses_per_week"],
            "misses": misses[-20:]}


# ------------------------------------------------------------- the re-run

def failed_jobs(jobs):
    """The failed jobs of one attempt's listing, the aggregate's left out."""
    #  A job past its time limit may say `cancelled`; counted, it holds a
    #  re-run back rather than letting it through.
    return [job for job in jobs if job.get("conclusion") in ("failure", "timed_out", "cancelled")
            and job["name"] != "gate"]


def classify_logs(jobs, read_log, patterns, limit=MAX_LOGS):
    """Job name -> signature or None, for each failed job of JOBS."""
    found = {}
    for job in failed_jobs(jobs)[:limit]:
        try:
            found[job["name"]] = signature_of(read_log(job["id"]), patterns)
        except (urllib.error.URLError, OSError, ValueError, subprocess.SubprocessError):
            found[job["name"]] = None
    for job in failed_jobs(jobs)[limit:]:
        found[job["name"]] = None
    return found


def rerun_decision(run, found, head, rerunnable):
    """(rerun, why) for a finished branch run whose failed jobs FOUND names
    with their signatures; HEAD is its branch's commit now.  RERUNNABLE
    names the signatures a second attempt can pass: a stale image's does
    not."""
    if run.get("head_branch") == "main":
        return False, "main's gate is investigated, never re-run blindly"
    if run.get("event") != "push":
        return False, "only a branch push is re-run"
    if run.get("run_attempt", 1) != 1:
        return False, "already re-run once"
    if head != run.get("head_sha"):
        return False, "the branch has moved on to %s" % (head or "nothing")[:12]
    if not found:
        return False, "no failed job to re-run"
    plain = sorted(name for name, signature in found.items()
                   if not signature or signature not in rerunnable)
    if plain:
        return False, "matched no outside signature a re-run can pass: " + ", ".join(plain)
    return True, "every failed job failed outside the change: " + ", ".join(
        "%s (%s)" % item for item in sorted(found.items()))


def attempt_jobs(run_id, attempt):
    jobs, page = [], 1
    while True:
        listing = token_rest("actions/runs/%s/attempts/%s/jobs?per_page=30&page=%d"
                             % (run_id, attempt, page))
        jobs += listing.get("jobs", [])
        if not listing.get("jobs") or len(jobs) >= listing.get("total_count", 0):
            return jobs
        page += 1


def job_log(job_id):
    """A job's log.  GitHub answers with a redirect to storage that refuses
    the token, which `gh` drops there and urllib would send on."""
    done = subprocess.run(["gh", "api", "repos/%s/actions/jobs/%s/logs"
                           % (os.environ["GITHUB_REPOSITORY"], job_id)],
                          capture_output=True, timeout=20)
    if done.returncode:
        raise OSError("no log for job %s: %s" % (job_id, done.stderr.decode()[:200]))
    return done.stdout.decode("utf-8", "replace")


# -------------------------------------------------------------------- main

def write_output(name, value):
    path = os.environ.get("GITHUB_OUTPUT")
    line = "%s=%s\n" % (name, value)
    if path:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(line)
    else:
        sys.stdout.write(line)


def write_summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(text)
    else:
        sys.stdout.write(text)


def today_utc():
    return datetime.now(timezone.utc)


def command_select():
    """The inputs job's half.  Any failure says so and selects every lane:
    shadow mode never changes what runs."""
    table = load_table()
    tree = git("rev-parse", "HEAD^{tree}")
    try:
        base = find_base(token_graphql, ancestor)
        #  Without renames, a moved file names its old path too.
        changed = git("diff", "--name-only", "--no-renames", base[1], "HEAD").splitlines() \
            if base else []
        chosen = close(table, select(table, changed, tree, today_utc(), base))
    except Exception as error:  # noqa: BLE001 -- shadow mode must not fail the run
        write_summary("## The selected gate, in shadow\n\nNot computed: %s: %s\n"
                      % (type(error).__name__, error))
        write_output("shadow", "")
        write_output("shadow-base", "")
        return 0
    write_summary(summary(table, chosen, base, final=False))
    write_output("shadow", compact(chosen))
    write_output("shadow-base", base[0] if base else "")
    write_output("shadow-sha", base[1] if base else "")
    return 0


def command_finish(ours, theirs):
    """The gate job's half: settle the emission lanes, record the selection
    and each failed job's outside signature on the run."""
    table = load_table()
    tree = git("rev-parse", "HEAD^{tree}")
    text = os.environ.get("SHADOW", "")
    base_run, base_sha = os.environ.get("SHADOW_BASE", ""), os.environ.get("SHADOW_SHA", "")
    if os.environ.get("REUSED") == "true":
        write_summary("## The selected gate, in shadow\n\nThis run reused a pass;"
                      " nothing was selected.\n")
        print("::notice title=%s::reused" % SHADOW_NOTE, flush=True)
    elif text:
        chosen = decide_emission(table, expanded(text), tree,
                                 read_manifests(ours), read_manifests(theirs))
        base = (base_run, base_sha) if base_run else None
        write_summary(summary(table, chosen, base, final=True))
        skipped = sorted(lane for lane, (verdict, _) in chosen.items() if verdict == "skip")
        print("::notice title=%s::base=%s skip=%s" % (SHADOW_NOTE, base_run or "-",
                                                      ",".join(skipped)), flush=True)
    else:
        write_summary("## The selected gate, in shadow\n\nNot computed on this run.\n")
    try:
        jobs = attempt_jobs(os.environ["GITHUB_RUN_ID"], os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
        found = classify_logs(jobs, job_log, signatures(table))
    except Exception as error:  # noqa: BLE001
        print("gate_history: could not read the failed jobs: %s" % error, file=sys.stderr)
        return 0
    if found:
        print("::notice title=%s::%s" % (CAUSE_NOTE, ";".join(
            "%s=%s" % (name, signature or "-") for name, signature in sorted(found.items()))),
            flush=True)
        write_summary("\n## Failed jobs' outside signatures\n\n" + "".join(
            "- `%s`: %s\n" % (name, signature or "none; a cause is the change's until shown otherwise")
            for name, signature in sorted(found.items())))
    if int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")) > 1:
        write_summary("\nAttempt %s, started by %s.\n" % (
            os.environ["GITHUB_RUN_ATTEMPT"], os.environ.get("GITHUB_TRIGGERING_ACTOR", "?")))
    return 0


def command_rerun(run_id):
    table = load_table()
    run = token_rest("actions/runs/%s" % run_id)
    try:
        head = token_rest("branches/%s" % urllib.parse.quote(run["head_branch"], safe=""))[
            "commit"]["sha"]
    except urllib.error.HTTPError:
        head = None
    jobs = attempt_jobs(run_id, run.get("run_attempt", 1))
    found = classify_logs(jobs, job_log, signatures(table))
    rerun, why = rerun_decision(run, found, head, {
        row["name"] for row in table.get("signatures", []) if row.get("rerun")})
    write_summary("## Gate run [%s](%s), attempt %s\n\n%s: %s.\n" % (
        run_id, run.get("html_url", ""), run.get("run_attempt", 1),
        "Re-run its failed jobs once" if rerun else "Not re-run", why))
    print("gate_history: %s" % why, file=sys.stderr)
    if rerun:
        token_rest("actions/runs/%s/rerun-failed-jobs" % run_id, data=b"{}")
    return 0


def main(argv):
    if argv[:1] == ["fetch"]:
        since = argv[argv.index("--since") + 1] if "--since" in argv else \
            (today_utc() - timedelta(weeks=10)).date().isoformat()
        print("%d runs fetched" % fetch(gh_graphql, cache_dir(), since))
        return 0
    if argv == ["causes"]:
        for row in causes(cached_runs(cache_dir()), seeded_signatures()):
            print("%(date)s %(run)s/%(attempt)s %(job)s: %(cause)s (%(by)s)" % row)
        return 0
    if argv[:1] == ["table"]:
        table = load_table()
        runs = cached_runs(cache_dir())
        rows = causes(runs, seeded_signatures())
        update_table(table, runs, rows, today_utc())
        if "--write" in argv:
            write_table(table)
            with open(CAUSES, "w", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row, sort_keys=True) + "\n")
        else:
            json.dump({lane: {key: row.get(key) for key in KEPT}
                       for lane, row in table["lanes"].items()}, sys.stdout, indent=1)
            print()
        return 0
    if argv == ["shadow"]:
        table = load_table()
        runs = cached_runs(cache_dir())
        json.dump(shadow_summary(table, runs, causes(runs, seeded_signatures())),
                  sys.stdout, indent=1)
        print()
        return 0
    if argv == ["select"]:
        return command_select()
    if argv[:1] == ["finish"] and len(argv) == 3:
        return command_finish(argv[1], argv[2])
    if argv[:1] == ["rerun"] and len(argv) == 2:
        return command_rerun(argv[1])
    print(__doc__.split("\n\n    fetch")[0][:0] + "usage: gate_history.py fetch [--since DATE]"
          " | causes | table [--write] | shadow | select | finish OURS THEIRS | rerun RUN",
          file=sys.stderr)
    return 2


def seeded_signatures():
    """Signatures found for runs before the gate recorded them: job id ->
    name, in the cache's seeded.json."""
    path = cache_dir() / "seeded.json"
    if not path.exists():
        return {}
    return {int(key): value for key, value in json.loads(path.read_text()).items()}


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
