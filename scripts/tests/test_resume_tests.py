#!/usr/bin/env python3
"""Controls for scripts/resume_tests.py, which continues a cut-off run."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import resume_tests  # noqa: E402

LOG = """\
built: /x/refine
progress: backend: 151 cases, 0 failed, 2.4s
progress: fixture execution: 21 cases, 2 failed, 9968.0s
progress: ir: 26 cases, 0 failed, 0.0s
"""
CASES = """\
built: /x/refine
backend/a case
fixture execution/one
fixture execution/two
ir/a case
server/analysis agrees with refine
"""


class Resume(unittest.TestCase):
    def test_passed_suites_are_left_out_and_failed_ones_run_again(self):
        self.assertEqual(resume_tests.passed_suites(LOG), {"backend", "ir"})
        self.assertEqual(resume_tests.remaining(LOG, CASES),
                         ["fixture execution", "server"])

    def test_a_log_with_no_ended_suite_is_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as scratch:
            log = Path(scratch) / resume_tests.LOG_NAME
            log.write_text("built: /x/refine\n")
            self.assertEqual(resume_tests.main([scratch, "--print"]), 2)


if __name__ == "__main__":
    unittest.main()
