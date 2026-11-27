#!/usr/bin/env python3
"""Run the suites a cut-off complete `dev-test.sh` run did not pass.

A complete local run takes hours, and one stopped by its time limit near
the end had to start again from the first suite.  The test program prints
`progress: SUITE: N cases, F failed, Ts` as each suite ends; this reads
those lines from the cut-off run's log, and runs every other suite, and
every suite that failed, in one `dev-test.sh` invocation:

    python3 scripts/resume_tests.py RUN_DIRECTORY_OR_LOG
    python3 scripts/resume_tests.py --print LOG   # the selectors alone

The resumed run is FILTERED, as every selection is: with the log's passed
suites it covers the complete suite only when both ran on the same tree,
which this checks when the log is a `run_logged.py` run's and says
otherwise.  Run it through `item.py run` or `run_logged.py --detach` like
the run it continues.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = re.compile(r"^progress: (.+?): (\d+) cases, (\d+) failed,", re.M)
#  A run_logged.py run's files: the log, and what ran where.
LOG_NAME = "command.log"
RESULT_NAME = "result.json"


def passed_suites(log_text):
    """The suites the log shows ended with no case failed."""
    passed, failed = set(), set()
    for suite, _, failures in PROGRESS.findall(log_text):
        (failed if int(failures) else passed).add(suite)
    return passed - failed


def all_suites(cases_text):
    """The suites in `dev-test.sh --cases`' listing, in its order."""
    suites = []
    for line in cases_text.splitlines():
        if "/" not in line or line.startswith(("built:", "landin:")):
            continue
        suite = line.split("/", 1)[0]
        if suite not in suites:
            suites.append(suite)
    return suites


def remaining(log_text, cases_text):
    done = passed_suites(log_text)
    return [suite for suite in all_suites(cases_text) if suite not in done]


def log_of(path):
    path = Path(path)
    return path / LOG_NAME if path.is_dir() else path


def tree_note(path):
    """What can be said of the tree the cut-off run ran on."""
    directory = Path(path) if Path(path).is_dir() else Path(path).parent
    result = directory / RESULT_NAME
    if not result.exists():
        return "the log names no tree: make sure it was this one"
    cwd = json.loads(result.read_text(encoding="utf-8")).get("cwd")
    if not cwd or os.path.realpath(cwd) != os.path.realpath(str(ROOT)):
        return ("the cut-off run ran in %s, not here: its passed suites"
                " count for this tree only if that one is the same" % cwd)
    return ("the cut-off run ran in this checkout; its passed suites count"
            " only if HEAD and the working tree are as they were then")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("log", help="the cut-off run's directory or log")
    parser.add_argument("--print", action="store_true",
                        help="print the selectors and run nothing")
    arguments = parser.parse_args(argv)
    log = log_of(arguments.log)
    if not log.exists():
        print("resume_tests.py: no log at %s" % log, file=sys.stderr)
        return 2
    text = log.read_text(encoding="utf-8", errors="replace")
    if not PROGRESS.search(text):
        print("resume_tests.py: %s holds no `progress:` line: no suite"
              " ended, so run the complete suite again" % log,
              file=sys.stderr)
        return 2
    listing = subprocess.run([str(ROOT / "scripts/dev-test.sh"), "--cases"],
                             cwd=ROOT, stdout=subprocess.PIPE, text=True)
    if listing.returncode != 0:
        print("resume_tests.py: `dev-test.sh --cases` failed",
              file=sys.stderr)
        return listing.returncode
    left = remaining(text, listing.stdout)
    selectors = ["--suite=%s" % suite for suite in left]
    print("resume_tests.py: %d suite(s) passed in %s, %d left; %s"
          % (len(passed_suites(text)), log, len(left), tree_note(
              arguments.log)), file=sys.stderr)
    if not left:
        print("resume_tests.py: nothing is left to run", file=sys.stderr)
        return 0
    if arguments.print:
        print(" ".join("'%s'" % selector for selector in selectors))
        return 0
    os.execv(str(ROOT / "scripts/dev-test.sh"),
             [str(ROOT / "scripts/dev-test.sh"), *selectors])


if __name__ == "__main__":
    sys.exit(main())
