#!/usr/bin/env python3
"""The local checks for a change: the gate's lanes it reaches, each lane's
local selectors.

    ./scripts/dev-test.sh --base=REV [--run]
    python3 scripts/local_selection.py --base=REV [--run]
    python3 scripts/local_selection.py --check

"Test what changed" is one rule locally and in the gate.  The gate's
selection (`scripts/gate_history.py`) reads `.github/gate-lanes.json`: a
lane runs when a path its `inputs` name changed.  Each lane there also
says what stands for it on a developer's host, its `local` entry:

  - a list of rules, each `when` (globs) paired with what a path they
    match calls for: `test`, `dev-test.sh` selectors, all joined into one
    invocation; `script_tests`, modules for one `script_tests.py`
    invocation; `commands`, other commands.  A `*` in a `when` glob
    matches one path component and is `{1}`, `{2}`... in what it calls
    for, with `_` read as a space where the rule says `"spaces": true`;
    `**` matches any rest.  For each path the lane's first matching rule
    is taken;
  - or `{"none": WHY}` for a lane with no local work, such as one that
    runs on a Mac, under Windows or on the rig.

The change is every path that differs between the merge base of REV and
HEAD and the working tree, untracked files included, renames as both
their paths.  The command prints each lane the change reaches, with the
path that reaches it, and the commands that stand for them, or says that
it reaches none with local work; with `--run` it then runs them, the
`dev-test.sh` invocation first, and exits with the first failure's
status.  `--check` holds the table to the rule above, as `check.py`
does.  None of this replaces the gate: the complete suite and the other
hosts' lanes are the candidate's gate's.
"""
import argparse
import fnmatch
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / ".github/gate-lanes.json"
TESTS = ROOT / "compiler/ada/tests/src/landin_tests.adb"
SCRIPT_TESTS = ROOT / "scripts/tests"
RULE_KEYS = {"when", "test", "script_tests", "commands", "spaces"}


def expand(globs, sets):
    """GLOBS with each `@set` replaced by the table's set of that name, as
    gate_history.expand does."""
    out = []
    for glob in globs:
        if glob.startswith("@"):
            out.extend(expand(sets[glob[1:]], sets))
        else:
            out.append(glob)
    return out


def reaches(paths, globs):
    """The first path of PATHS a glob of GLOBS matches, by the gate's own
    rule (gate_history.reaches)."""
    for path in paths:
        for glob in globs:
            if fnmatch.fnmatchcase(path, glob) or (
                    glob.endswith("/**") and path.startswith(glob[:-2])):
                return path
    return None


def pattern(glob):
    """GLOB as a regular expression: `**` any rest, `*` one captured
    component, `?` one character."""
    out, index = "", 0
    while index < len(glob):
        if glob.startswith("**", index):
            out += ".*"
            index += 2
        elif glob[index] == "*":
            out += "([^/]+)"
            index += 1
        elif glob[index] == "?":
            out += "[^/]"
            index += 1
        else:
            out += re.escape(glob[index])
            index += 1
    return re.compile(out + r"\Z")


def captured(path, globs):
    """The captures of the first glob of GLOBS that PATH matches, or None."""
    for glob in globs:
        found = pattern(glob).match(path)
        if found:
            return found.groups()
    return None


def fill(text, groups, spaces):
    for number, value in enumerate(groups, 1):
        text = text.replace("{%d}" % number,
                            value.replace("_", " ") if spaces else value)
    return text


def suites():
    """The test program's suite names, read from its source as
    `dev-test.sh --help` reads them."""
    text = TESTS.read_text(encoding="utf-8")
    block = text[text.index("Expected_Suites : constant"):]
    block = block[:block.index("];")]
    return {name.strip() for name in re.findall(r'"([^"]*)"', block)}


class Selection:
    def __init__(self):
        self.lanes = []        # (lane, path, [what it calls for])
        self.unchecked = []    # (lane, path): reached, no rule matches
        self.none = []         # (lane, path, why)
        self.test = []
        self.script_tests = []
        self.commands = []
        self.notes = []

    def add(self, kind, value):
        target = getattr(self, kind)
        if value not in target:
            target.append(value)


def select(table, changed, known_suites=None):
    """What CHANGED calls for, lane by lane."""
    sets = table.get("sets", {})
    chosen = Selection()
    for lane, row in table["lanes"].items():
        path = reaches(changed, expand(row.get("inputs", []), sets))
        if path is None:
            continue
        local = row.get("local")
        if isinstance(local, dict):
            chosen.none.append((lane, path, local.get("none", "")))
            continue
        called, unmatched, first = [], [], None
        for each in changed:
            if not reaches([each], expand(row.get("inputs", []), sets)):
                continue
            for rule in local or []:
                groups = captured(each, expand(rule["when"], sets))
                if groups is None:
                    continue
                spaces = rule.get("spaces", False)
                for selector in rule.get("test", []):
                    selector = fill(selector, groups, spaces)
                    suite = selector.partition("--suite=")[2]
                    if known_suites is not None and suite and suite not in known_suites:
                        chosen.add("notes", "%s: no suite %r for %s; the gate's"
                                   " %s lane runs what it would have" % (
                                       lane, suite, each, lane))
                        continue
                    chosen.add("test", selector)
                    called.append(selector)
                for module in rule.get("script_tests", []):
                    module = fill(module, groups, spaces)
                    if not (SCRIPT_TESTS / (module + ".py")).is_file():
                        chosen.add("notes", "%s: no script test module %s for %s"
                                   % (lane, module, each))
                        continue
                    chosen.add("script_tests", module)
                    called.append(module)
                for command in rule.get("commands", []):
                    command = [fill(part, groups, spaces) for part in command]
                    chosen.add("commands", command)
                    called.append(shlex.join(command))
                first = first or (each if called else None)
                break
            else:
                unmatched.append(each)
        if called:
            chosen.lanes.append((lane, first, list(dict.fromkeys(called))))
        elif not row.get("always"):
            #  A lane every gate runs, whatever changed, is named only
            #  when a path calls for its local check.
            chosen.unchecked.append((lane, unmatched[0] if unmatched else path))
    return chosen


def invocations(chosen):
    """The commands, in the order they run: one dev-test.sh invocation,
    one script_tests.py invocation, then the rest.  A dev-test.sh run
    builds, so a build command beside it is dropped."""
    out = []
    if chosen.test:
        out.append(["./scripts/dev-test.sh", *chosen.test])
    if chosen.script_tests:
        out.append(["python3", "scripts/script_tests.py", *chosen.script_tests])
    for command in chosen.commands:
        if chosen.test and command == ["./scripts/dev-build.sh"]:
            continue
        out.append(command)
    return out


def changed_paths(base, cwd=ROOT):
    def git(*arguments):
        return subprocess.run(["git", *arguments], cwd=cwd, check=True, text=True,
                              stdout=subprocess.PIPE).stdout
    since = git("merge-base", base, "HEAD").strip()
    paths = git("diff", "--name-only", "--no-renames", since).splitlines()
    paths += git("ls-files", "--others", "--exclude-standard").splitlines()
    return since, sorted(set(paths))


def report(chosen, base, since, paths):
    lines = ["The change since %s (merge base %s, %d paths) reaches these lanes of"
             " .github/gate-lanes.json:" % (base, since[:12], len(paths))]
    if not (chosen.lanes or chosen.unchecked or chosen.none):
        lines.append("  none")
    for lane, path, called in chosen.lanes:
        lines.append("  %s, by %s: %s" % (lane, path, ", ".join(called)))
    for lane, path in chosen.unchecked:
        lines.append("  %s, by %s: no local selector names that path; the gate runs"
                     " the lane" % (lane, path))
    if chosen.none:
        lines.append("  with no local work, the gate's alone:")
        reasons = {}
        for lane, path, why in chosen.none:
            reasons.setdefault(why, []).append(lane)
        for why, lanes in reasons.items():
            lines.append("    %s: %s" % (", ".join(lanes), why))
    for note in chosen.notes:
        lines.append("note: " + note)
    commands = invocations(chosen)
    if commands:
        lines.append("Local checks for it (FILTERED; the gate runs the rest):")
        lines.extend("  " + shlex.join(command) for command in commands)
    else:
        lines.append("It reaches no local selector: nothing to run here; the"
                     " gate's lanes above check it.")
    return "\n".join(lines)


def check_table(table, known_suites):
    """Problems with the table's `local` entries: every lane has one, a
    lane with local work names selectors, each rule is well formed and
    names suites the test program has."""
    problems = []
    sets = table.get("sets", {})
    for lane, row in table["lanes"].items():
        local = row.get("local")
        if local is None:
            problems.append("lane %s has no `local` entry: name its local selectors,"
                            " or {\"none\": WHY}" % lane)
        elif isinstance(local, dict):
            if set(local) != {"none"} or not str(local["none"]).strip():
                problems.append("lane %s: a `local` object is {\"none\": WHY}, the"
                                " reason it has no local work" % lane)
        elif not isinstance(local, list) or not local:
            problems.append("lane %s: `local` is a list of rules or {\"none\": WHY}"
                            % lane)
        else:
            for number, rule in enumerate(local, 1):
                where = "lane %s, local rule %d" % (lane, number)
                if not isinstance(rule, dict) or set(rule) - RULE_KEYS:
                    problems.append("%s: keys are %s" % (where, ", ".join(sorted(RULE_KEYS))))
                    continue
                if not rule.get("when"):
                    problems.append("%s: names no `when` paths" % where)
                    continue
                if not any(rule.get(kind) for kind in ("test", "script_tests", "commands")):
                    problems.append("%s: names no selector: `test`, `script_tests` or"
                                    " `commands`" % where)
                try:
                    globs = expand(rule["when"], sets)
                except KeyError as error:
                    problems.append("%s: no set %s" % (where, error))
                    continue
                for selector in rule.get("test", []):
                    if not selector.startswith(("--suite=", "--case=", "--fixture=")):
                        problems.append("%s: %r is not a --suite, --case or --fixture"
                                        " selector" % (where, selector))
                    suite = selector.partition("--suite=")[2]
                    if suite and "{" not in suite and suite not in known_suites:
                        problems.append("%s: the test program has no suite %r"
                                        % (where, suite))
                    case = selector.partition("--case=")[2].partition("/")[0]
                    if case and case not in known_suites:
                        problems.append("%s: the test program has no suite %r for"
                                        " %r" % (where, case, selector))
                for module in rule.get("script_tests", []):
                    if "{" not in module and not (SCRIPT_TESTS / (module + ".py")).is_file():
                        problems.append("%s: no scripts/tests/%s.py" % (where, module))
                inputs = expand(row.get("inputs", []), sets)
                for glob in globs:
                    probe = glob.replace("**", "x").replace("*", "x").replace("?", "x")
                    if not reaches([probe], inputs):
                        problems.append("%s: %s is not among the lane's inputs, so"
                                        " no change it matches reaches the lane"
                                        % (where, glob))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="dev-test.sh --base", description=__doc__.split("\n\n")[0],
        epilog=__doc__.split("\n\n", 1)[1], allow_abbrev=False,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--base", metavar="REV",
                       help="the commit the change is measured from, such as origin/main")
    which.add_argument("--check", action="store_true",
                       help="hold the lane table's local entries to their rule")
    parser.add_argument("--run", action="store_true",
                        help="run the commands it prints")
    args = parser.parse_args(argv)
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    known = suites()
    if args.check:
        problems = check_table(table, known)
        for problem in problems:
            print("gate-lanes.json: " + problem, file=sys.stderr)
        return 1 if problems else 0
    try:
        since, paths = changed_paths(args.base)
    except subprocess.CalledProcessError as error:
        print("dev-test.sh --base: git could not read the change since %s (%s)"
              % (args.base, error), file=sys.stderr)
        return 2
    chosen = select(table, paths, known)
    print(report(chosen, args.base, since, paths), flush=True)
    if not args.run:
        return 0
    for command in invocations(chosen):
        print("running: " + shlex.join(command), flush=True)
        status = subprocess.run(command, cwd=ROOT).returncode
        if status:
            print("failed (exit %d): %s" % (status, shlex.join(command)), flush=True)
            return status
    return 0


if __name__ == "__main__":
    sys.exit(main())
