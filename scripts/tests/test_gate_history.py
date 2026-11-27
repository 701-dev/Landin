#!/usr/bin/env python3
"""The failure causes, the lane table and the selection in shadow.

Lanes holds `.github/gate-lanes.json` to the gate: every job the
aggregate needs is in exactly one lane, every lane's needs and sets
resolve, and every outside signature matches its own example and compiles.
Causes holds the study's mechanical rule; Selection the rule of the
selection, its draw and its closure over needs; Shadow the miss count;
Rerun when a branch run is re-run once; Wiring that the workflows compute
the selection without ever making a job fail or skip for it.
"""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


history = load("gate_history", ROOT / "scripts/gate_history.py")
sys.path.insert(0, str(ROOT / "scripts/tests"))
inputs_tests = load("test_gate_inputs_for_history", ROOT / "scripts/tests/test_gate_inputs.py")

TODAY = datetime(2026, 11, 26, tzinfo=timezone.utc)


def workflows():
    directory = ROOT / ".github/workflows"
    called = {".github/workflows/" + path.name: path.read_text()
              for path in directory.glob("*.yml")}
    return (directory / "gate.yml").read_text(), called


class Lanes(unittest.TestCase):
    def setUp(self):
        self.table = history.load_table()

    def test_every_gate_job_is_in_exactly_one_lane(self):
        gate, called = workflows()
        needed = inputs_tests.required_workflow_names(gate, called) - {"gate"}
        listed = [job for row in self.table["lanes"].values() for job in row["jobs"]]
        self.assertEqual(len(listed), len(set(listed)), "a job is in two lanes")
        self.assertEqual(set(listed) - needed, set(), "lanes name jobs the gate does not run")
        self.assertEqual(needed - set(listed), set(),
                         "gate jobs no lane names: add each to .github/gate-lanes.json")

    def test_needs_and_sets_resolve(self):
        sets = self.table["sets"]
        for lane, row in self.table["lanes"].items():
            with self.subTest(lane=lane):
                for need in row.get("needs", []):
                    self.assertIn(need, self.table["lanes"])
                history.expand(row.get("inputs", []), sets)
                self.assertTrue(row.get("inputs") or row.get("always"),
                                "a lane declares its inputs or runs always")

    def test_signatures_match_their_examples(self):
        names = [row["name"] for row in self.table["signatures"]]
        self.assertEqual(len(names), len(set(names)))
        for row in self.table["signatures"]:
            with self.subTest(signature=row["name"]):
                self.assertTrue(re.search(row["pattern"], row["example"]))
                self.assertIn("rerun", row)
                self.assertEqual(history.signature_of(
                    "2026-11-26T10:00:00.1234567Z " + row["example"],
                    history.signatures(self.table)), row["name"])

    def test_a_signature_counts_only_where_the_job_failed(self):
        patterns = history.signatures(self.table)
        retried = "\n".join(["E: Failed to fetch http://m/x  503  Service Unavailable"]
                             + ["building"] * 100
                             + ["##[error]Process completed with exit code 1."])
        self.assertIsNone(history.signature_of(retried, patterns))
        near = "\n".join(["E: Failed to fetch http://m/x  503  Service Unavailable"]
                          + ["building"] * 10
                          + ["##[error]Process completed with exit code 100."])
        self.assertEqual(history.signature_of(near, patterns), "apt-mirror-failure")
        self.assertIsNone(history.signature_of(
            "curl: (22) The requested URL returned error: 404", patterns),
            "a removed pin is the change's, not outside")

    def test_the_rules_are_the_accepted_values(self):
        self.assertEqual({key: self.table["rules"][key] for key in
                          ("alone_weeks", "new_weeks", "cheap_minutes", "one_in")},
                         {"alone_weeks": 8, "new_weeks": 4, "cheap_minutes": 5, "one_in": 4})


def run(number, branch, sha, tree, created, jobs, event="push", gates=()):
    return {"run": number, "event": event, "branch": branch, "sha": sha, "tree": tree,
            "created": created, "status": "COMPLETED", "conclusion": None,
            "jobs": [list(job) for job in jobs], "gates": [list(gate) for gate in gates]}


def job(number, name, conclusion, end="2026-11-20T10:10:00Z"):
    return (number, name, conclusion, "2026-11-20T10:00:00Z", end)


class Causes(unittest.TestCase):
    def rows(self, runs, seeded=None):
        return {(row["run"], row["job"], row["attempt"]): (row["cause"], row["by"])
                for row in history.causes(runs, seeded)}

    def test_the_next_push_changing_the_tree_makes_a_defect(self):
        runs = [run(1, "b", "s1", "t1", "2026-11-20T10:00:00Z", [job(10, "compiler-1", "FAILURE")]),
                run(2, "b", "s2", "t2", "2026-11-20T11:00:00Z", [job(20, "compiler-1", "SUCCESS")])]
        self.assertEqual(self.rows(runs), {(1, "compiler-1", 1): ("defect", "next-push")})

    def test_a_passed_rerun_or_identical_tree_is_outside(self):
        runs = [run(1, "b", "s1", "t1", "2026-11-20T10:00:00Z",
                    [job(10, "compiler-1", "FAILURE"), job(11, "compiler-1", "SUCCESS"),
                     job(12, "scripts", "FAILURE")]),
                run(2, "c", "s9", "t1", "2026-11-20T10:30:00Z", [job(20, "scripts", "SUCCESS")]),
                run(3, "b", "s2", "t2", "2026-11-20T11:00:00Z", [])]
        rows = self.rows(runs)
        self.assertEqual(rows[(1, "compiler-1", 1)], ("outside", "rerun"))
        self.assertEqual(rows[(1, "scripts", 1)], ("outside", "same-tree"))

    def test_a_signature_decides_first(self):
        runs = [run(1, "b", "s1", "t1", "2026-11-20T10:00:00Z", [job(10, "compiler-1", "FAILURE")],
                    gates=[["2026-11-20T10:20:00Z",
                            {history.CAUSE_NOTE: "compiler-1=apt-mirror-failure"}]]),
                run(2, "b", "s2", "t2", "2026-11-20T11:00:00Z", [])]
        self.assertEqual(self.rows(runs), {(1, "compiler-1", 1): ("outside", "apt-mirror-failure")})
        self.assertEqual(self.rows(runs[1:] + [dict(runs[0], gates=[])], {10: "disk-full"}),
                         {(1, "compiler-1", 1): ("outside", "disk-full")})

    def test_an_aggregate_before_the_job_ended_records_nothing_of_it(self):
        runs = [run(1, "b", "s1", "t1", "2026-11-20T10:00:00Z", [job(10, "compiler-1", "FAILURE")],
                    gates=[["2026-11-20T10:05:00Z",
                            {history.CAUSE_NOTE: "compiler-1=apt-mirror-failure"}]]),
                run(2, "b", "s2", "t2", "2026-11-20T11:00:00Z", [])]
        self.assertEqual(self.rows(runs)[(1, "compiler-1", 1)][0], "defect")

    def test_no_next_push_is_pending_and_the_same_tree_unresolved(self):
        first = run(1, "b", "s1", "t1", "2026-11-20T10:00:00Z", [job(10, "compiler-1", "FAILURE")])
        self.assertEqual(self.rows([first]), {(1, "compiler-1", 1): ("pending", "no-next-push")})
        again = run(2, "b", "s2", "t1", "2026-11-20T11:00:00Z", [job(20, "compiler-1", "FAILURE")])
        self.assertEqual(self.rows([first, again])[(1, "compiler-1", 1)],
                         ("unresolved", "same-tree-pushed"))

    def test_the_aggregate_and_skipped_jobs_are_no_cause(self):
        runs = [run(1, "b", "s1", "t1", "2026-11-20T10:00:00Z",
                    [job(10, "gate", "FAILURE"), job(11, "compiler-1", "SKIPPED"),
                     job(12, "compiler-2", "CANCELLED")])]
        self.assertEqual(self.rows(runs), {})


def table(**lanes):
    return {"rules": {"alone_weeks": 8, "new_weeks": 4, "cheap_minutes": 5, "one_in": 4,
                      "shadow_gates": 200, "study_misses_per_week": 1.7},
            "sets": {"compiler": ["compiler/ada/**"]}, "signatures": [],
            "lanes": {name: dict({"jobs": [name], "first_seen": "2026-09-01",
                                  "minutes": 20, "alone": None}, **row)
                      for name, row in lanes.items()}}


class Selection(unittest.TestCase):
    BASE = (7, "b" * 40)

    def chosen(self, lanes, changed=(), tree="t", base=BASE):
        return history.close(lanes, history.select(lanes, list(changed), tree, TODAY, base))

    def test_standing_reasons_keep_a_lane(self):
        lanes = table(docs={"always": True}, boards={"physical": True, "inputs": ["x"]},
                      compare={"evidence": True, "inputs": ["x"]},
                      young={"first_seen": "2026-11-10", "inputs": ["x"]},
                      cheap={"minutes": 4.9, "inputs": ["x"]},
                      alone={"alone": "2026-10-10", "inputs": ["x"]})
        chosen = self.chosen(lanes)
        for lane in lanes["lanes"]:
            self.assertEqual(chosen[lane][0], "keep", lane)
        stale = table(alone={"alone": "2026-09-20", "inputs": ["x"]})
        self.assertNotEqual(self.chosen(stale, tree=self.undrawn("alone"))["alone"][0], "keep")

    def undrawn(self, lane):
        return next(tree for tree in ("t%d" % n for n in range(100))
                    if not history.drawn(tree, lane, 4))

    def test_inputs_reached_keep_and_unreached_are_drawn(self):
        lanes = table(darwin={"inputs": ["@compiler", "environments/macos-arm64/**"]})
        tree = self.undrawn("darwin")
        self.assertEqual(self.chosen(lanes, ["compiler/ada/a.adb"], tree)["darwin"],
                         ["keep", "inputs: compiler/ada/a.adb"])
        self.assertEqual(self.chosen(lanes, ["docs/x.md"], tree)["darwin"][0], "skip")

    def test_the_draw_is_the_trees_and_one_in_four(self):
        trees = ["%040x" % n for n in range(2000)]
        share = sum(history.drawn(tree, "darwin-host", 4) for tree in trees) / len(trees)
        self.assertAlmostEqual(share, 0.25, delta=0.04)
        self.assertEqual(history.drawn("abc", "x", 4), history.drawn("abc", "x", 4))

    def test_no_base_keeps_every_lane(self):
        lanes = table(darwin={"inputs": ["x"]})
        self.assertEqual(self.chosen(lanes, base=None)["darwin"][0], "keep")

    def test_a_kept_lane_keeps_what_it_needs(self):
        lanes = table(build={"inputs": ["nothing"]},
                      suite={"inputs": ["@compiler"], "needs": ["build"]})
        tree = self.undrawn("build")
        chosen = self.chosen(lanes, ["compiler/ada/a.adb"], tree)
        self.assertEqual(chosen["build"], ["keep", "needed by suite"])

    def test_emission_lanes_are_settled_by_their_targets_digests(self):
        lanes = table(windows={"inputs": ["compiler/tests/windows/**"],
                               "emission": ["windows-x86-64"]})
        tree = self.undrawn("windows")
        chosen = self.chosen(lanes, ["compiler/ada/a.adb"], tree)
        self.assertEqual(chosen["windows"][0], "emission")
        ours = {"f|windows-x86-64|debug|o": "1", "f|linux-x86-64|debug|o": "2"}
        same = history.decide_emission(lanes, dict(chosen), tree, ours,
                                       dict(ours, **{"f|linux-x86-64|debug|o": "3"}))
        self.assertEqual(same["windows"], ["skip", "emission unchanged"])
        moved = history.decide_emission(lanes, dict(chosen), tree, ours,
                                        dict(ours, **{"f|windows-x86-64|debug|o": "9"}))
        self.assertEqual(moved["windows"], ["keep", "emission changed: windows-x86-64"])
        self.assertEqual(history.decide_emission(lanes, dict(chosen), tree, ours, None)["windows"],
                         ["keep", "emission unknown"])

    def test_the_record_survives_its_round_trip(self):
        chosen = {"a": ["keep", "inputs: x;y"], "b": ["skip", "sampled, not drawn"]}
        self.assertEqual(history.expanded(history.compact(chosen)),
                         {"a": ["keep", "inputs: x,y"], "b": ["skip", "sampled, not drawn"]})

    def test_the_live_table_selects(self):
        live = history.load_table()
        chosen = self.chosen(live, ["docs/process.md"], "0" * 40)
        self.assertEqual(chosen["documents"][0], "keep")
        self.assertIn("Would skip", history.summary(live, chosen, self.BASE, final=True))


class Shadow(unittest.TestCase):
    def test_a_defect_only_skipped_lanes_showed_is_a_miss(self):
        lanes = table(a={"inputs": ["x"]}, b={"inputs": ["x"]})
        note = {history.SHADOW_NOTE: "base=7 skip=a"}
        runs = [run(1, "x", "s1", "t1", "2026-11-20T10:00:00Z", [job(10, "a", "FAILURE")],
                    gates=[["2026-11-20T10:20:00Z", note]]),
                run(2, "x", "s2", "t2", "2026-11-20T11:00:00Z", [job(20, "a", "FAILURE")],
                    gates=[["2026-11-20T11:20:00Z", note]]),
                run(3, "x", "s3", "t3", "2026-11-21T10:00:00Z", [job(30, "b", "FAILURE")],
                    gates=[["2026-11-21T10:20:00Z", note]]),
                run(4, "x", "s4", "t4", "2026-11-27T10:00:00Z", [],
                    gates=[["2026-11-27T10:20:00Z", note]])]
        found = history.shadow_summary(lanes, runs, history.causes(runs))
        self.assertEqual((found["complete_gates"], found["missed_runs"], found["missed_defects"]),
                         (4, 2, 1))
        self.assertEqual(found["weeks"], 1.0)


class Rerun(unittest.TestCase):
    RUN = {"head_branch": "r22-36", "event": "push", "run_attempt": 1, "head_sha": "abc"}
    RERUNNABLE = {"apt-mirror-failure"}

    def decide(self, found, run=None, head="abc"):
        return history.rerun_decision(run or self.RUN, found, head, self.RERUNNABLE)[0]

    def test_a_branch_run_failed_only_outside_is_rerun_once(self):
        self.assertTrue(self.decide({"compiler-1": "apt-mirror-failure"}))
        self.assertFalse(self.decide({"compiler-1": "apt-mirror-failure", "scripts": None}))
        self.assertFalse(self.decide({"compiler-1": "stale-ubuntu-qemu-8"}))
        self.assertFalse(self.decide({}))
        self.assertFalse(self.decide({"compiler-1": "apt-mirror-failure"},
                                     dict(self.RUN, run_attempt=2)))

    def test_main_a_moved_branch_and_other_events_are_never_rerun(self):
        found = {"compiler-1": "apt-mirror-failure"}
        self.assertFalse(self.decide(found, dict(self.RUN, head_branch="main")))
        self.assertFalse(self.decide(found, head="def"))
        self.assertFalse(self.decide(found, dict(self.RUN, event="workflow_dispatch")))

    def test_logs_beyond_the_limit_count_as_unmatched(self):
        jobs = [{"id": n, "name": "j%d" % n, "conclusion": "failure"} for n in range(3)]
        jobs.append({"id": 9, "name": "gate", "conclusion": "failure"})
        found = history.classify_logs(jobs, lambda _: "E: Unable to acquire the dpkg frontend lock",
                                      history.signatures(history.load_table()), limit=2)
        self.assertEqual(found, {"j0": "apt-dpkg-lock", "j1": "apt-dpkg-lock", "j2": None})


def job_body(source, name):
    match = re.search(r"^  %s:\n(.*?)(?=^  [\w-]+:\n|\Z)" % re.escape(name), source, re.S | re.M)
    return match.group(1)


def job_conditions(source):
    """Every job's `if:`, continuation lines included."""
    found, inside = [], False
    for line in source.splitlines():
        if line.startswith("    if:"):
            found.append(line)
            inside = True
        elif inside and line.startswith("      "):
            found.append(line)
        else:
            inside = False
    return found


class Wiring(unittest.TestCase):
    def test_the_selection_never_fails_or_skips_a_job(self):
        gate, _ = workflows()
        inputs = job_body(gate, "inputs")
        self.assertIn("gate_history.py select", inputs)
        step = inputs[inputs.index("gate_history.py select") - 600:]
        self.assertIn("continue-on-error: true", step[:700])
        aggregate = job_body(gate, "gate")
        self.assertIn("gate_history.py finish", aggregate)
        finish = aggregate[aggregate.rindex("- name:", 0, aggregate.index("gate_history.py finish")):]
        self.assertIn("continue-on-error: true", finish)
        #  No job's condition reads the selection: shadow mode skips nothing.
        self.assertNotIn("outputs.shadow", "\n".join(job_conditions(gate)))

    def test_the_rerun_is_a_branch_push_first_attempt_only(self):
        source = (ROOT / ".github/workflows/gate-rerun.yml").read_text()
        self.assertIn("workflows: [gate]", source)
        for condition in ("github.event.workflow_run.conclusion == 'failure'",
                          "github.event.workflow_run.event == 'push'",
                          "github.event.workflow_run.head_branch != 'main'",
                          "github.event.workflow_run.run_attempt == 1"):
            self.assertIn(condition, source)
        self.assertIn("gate_history.py rerun", source)


if __name__ == "__main__":
    unittest.main()
