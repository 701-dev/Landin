#!/usr/bin/env python3
"""`dev-test.sh --base`: the local checks a diff calls for are the lane
table's, for the lanes the gate's own rule says the diff reaches."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import gate_history  # noqa: E402
import local_selection  # noqa: E402

TABLE = json.loads((ROOT / ".github/gate-lanes.json").read_text(encoding="utf-8"))
HANG = 300


def rule_with(lane, glob):
    """The lane's local rule whose `when` names GLOB, read from the table."""
    for rule in TABLE["lanes"][lane]["local"]:
        if glob in rule["when"]:
            return rule
    raise AssertionError("lane %s has no local rule for %s" % (lane, glob))


def git(cwd, *arguments):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
                   cwd=cwd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=HANG)


class ADiff(unittest.TestCase):
    """One change of each kind of lane, through dev-test.sh in a repository
    holding the table, the script and the files they read."""

    #  One path for each kind of lane: a fixture the test program runs by
    #  name, a compiler area that stands as suites, a script with its own
    #  test module, a document that check.py reads, the grammar the editor
    #  lane runs a command for, and a Mac's environment, no local work.
    PATHS = {
        "compiler/tests/fixtures/runtime/add-exits-with-its-sum/main.ldn": "fixture",
        "compiler/ada/src/backend/landin-backend-x86_64.adb": "suites",
        "scripts/gate_watch.py": "script test",
        "tour.md": "document",
        "highlight/tree-sitter/grammar.js": "command",
        "environments/macos-arm64/README.md": "none",
    }

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="landin-selection-")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        for name in (".github/gate-lanes.json", "scripts/local_selection.py",
                     "scripts/dev-test.sh", "compiler/ada/tests/src/landin_tests.adb"):
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, self.repo / name)
        for module in (ROOT / "scripts/tests").glob("test_*.py"):
            (self.repo / "scripts/tests").mkdir(parents=True, exist_ok=True)
            (self.repo / "scripts/tests" / module.name).write_text("")
        git(self.repo, "init", "-q")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")

    def run_base(self, *paths):
        for path in paths:
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("changed\n")
        said = subprocess.run(["sh", str(self.repo / "scripts/dev-test.sh"), "--base=HEAD"],
                              cwd=self.repo, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, timeout=HANG)
        self.assertEqual(said.returncode, 0, said.stdout)
        return said.stdout

    def commands(self, said):
        lines = said.split("Local checks for it", 1)[1].splitlines()[1:]
        return [line.strip() for line in lines if line.startswith("  ")]

    def test_each_kind_of_lane_prints_the_tables_selectors(self):
        said = self.run_base(*self.PATHS)
        commands = self.commands(said)
        test = next(line for line in commands if line.startswith("./scripts/dev-test.sh"))
        fixture = rule_with("compiler", "compiler/tests/fixtures/runtime/*/**")["test"][0]
        self.assertIn(fixture.replace("{1}", "add-exits-with-its-sum"), test)
        for selector in rule_with("compiler", "compiler/ada/src/backend/**")["test"]:
            self.assertIn(selector if " " not in selector else "'%s'" % selector, test)
        for selector in rule_with("compiler", "tour.md")["test"]:
            self.assertIn(selector, test)
        self.assertIn("python3 scripts/script_tests.py test_gate_watch", commands)
        self.assertIn(" ".join(rule_with("documents", "**")["commands"][0]), commands)
        self.assertIn(" ".join(rule_with("editor-grammar", "highlight/**")["commands"][0]),
                      commands)
        self.assertIn("darwin-host", said.split("with no local work", 1)[1])
        self.assertNotIn("./scripts/dev-build.sh", commands)

    def test_the_lanes_named_are_those_the_gates_rule_reaches(self):
        said = self.run_base(*self.PATHS)
        changed = sorted(self.PATHS)
        reached = {lane for lane, row in TABLE["lanes"].items()
                   if gate_history.reaches(changed, gate_history.expand(
                       row["inputs"], TABLE["sets"]))}
        listed = said.split("Local checks for it", 1)[0]
        checked, alone = listed.split("  with no local work, the gate's alone:\n")
        named = {line[2:].split(", by ")[0] for line in checked.splitlines()
                 if line.startswith("  ") and ", by " in line}
        for line in alone.splitlines():
            if line.startswith("    "):
                lanes, _, why = line[4:].partition(": ")
                for lane in lanes.split(", "):
                    self.assertEqual(TABLE["lanes"][lane]["local"], {"none": why})
                    named.add(lane)
        expected = {lane for lane in reached if not (
            TABLE["lanes"][lane].get("always") and lane not in named)}
        self.assertEqual(named, expected)
        self.assertIn("documents", named)

    def test_a_change_no_local_selector_names_says_so(self):
        #  With the real table every change calls for check.py, which the
        #  documents lane names for any path; without it, a FreeBSD
        #  environment reaches only lanes with no local work.
        table = json.loads((self.repo / ".github/gate-lanes.json").read_text())
        table["lanes"]["documents"]["local"] = {"none": "test"}
        (self.repo / ".github/gate-lanes.json").write_text(json.dumps(table))
        git(self.repo, "commit", "-qam", "table")
        said = self.run_base("environments/freebsd/README.md")
        self.assertIn("It reaches no local selector", said)
        self.assertIn("freebsd-host", said)
        self.assertNotIn("dev-test.sh --", said.replace("dev-test.sh --target", ""))

    def test_run_runs_the_printed_commands(self):
        table = json.loads((self.repo / ".github/gate-lanes.json").read_text())
        for row in table["lanes"].values():
            row["local"] = {"none": "test"}
        marker = self.repo / "ran"
        table["lanes"]["documents"]["local"] = [
            {"when": ["**"], "commands": [["touch", str(marker)]]}]
        (self.repo / ".github/gate-lanes.json").write_text(json.dumps(table))
        git(self.repo, "commit", "-qam", "table")
        (self.repo / "README.md").write_text("changed\n")
        said = subprocess.run(["sh", "scripts/dev-test.sh", "--base=HEAD", "--run"],
                              cwd=self.repo, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, timeout=HANG)
        self.assertEqual(said.returncode, 0, said.stdout)
        self.assertIn("running: touch", said.stdout)
        self.assertTrue(marker.exists())


class TheControl(unittest.TestCase):
    """Every lane names its local selectors or why it has none."""

    def test_the_table_passes(self):
        self.assertEqual(local_selection.check_table(TABLE, local_selection.suites()), [])

    def problems(self, change):
        table = copy.deepcopy(TABLE)
        change(table["lanes"])
        return local_selection.check_table(table, local_selection.suites())

    def test_a_lane_with_no_entry_is_named(self):
        said = self.problems(lambda lanes: lanes["compiler"].pop("local"))
        self.assertEqual(len(said), 1)
        self.assertIn("lane compiler has no `local` entry", said[0])

    def test_a_none_needs_a_reason(self):
        said = self.problems(lambda lanes: lanes["board"].update(local={"none": " "}))
        self.assertIn("board", said[0])

    def test_a_rule_names_a_selector(self):
        said = self.problems(lambda lanes: lanes["bindings"]["local"].append(
            {"when": ["bindings/**"]}))
        self.assertIn("names no selector", said[0])

    def test_a_suite_the_test_program_lacks_is_named(self):
        said = self.problems(lambda lanes: lanes["bindings"]["local"].append(
            {"when": ["bindings/**"], "test": ["--suite=no such suite"]}))
        self.assertIn("no suite 'no such suite'", said[0])

    def test_a_path_outside_the_lanes_inputs_is_named(self):
        said = self.problems(lambda lanes: lanes["bindings"]["local"].append(
            {"when": ["darwin/**"], "test": ["--suite=bindings"]}))
        self.assertIn("darwin/** is not among the lane's inputs", said[0])

    def test_check_py_runs_the_control(self):
        source = (ROOT / "check.py").read_text(encoding="utf-8")
        self.assertIn("local_selection", source)


if __name__ == "__main__":
    unittest.main()
