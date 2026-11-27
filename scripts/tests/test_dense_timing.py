"""dense_timing.py's parsing, its summary and its report."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dense_timing  # noqa: E402


class Parsing(unittest.TestCase):
    def test_the_line_both_programs_print(self):
        self.assertEqual(dense_timing.parse("checksum -2020 nanoseconds 412254580\n"),
                         (-2020, 412254580))

    def test_anything_else_is_refused(self):
        with self.assertRaisesRegex(dense_timing.Failure, "unexpected output"):
            dense_timing.parse("checksum -2020\n")

    def test_the_programs_are_in_the_tree(self):
        for name in ("timing.ldn", "timing.c", "README.md"):
            self.assertTrue((dense_timing.DENSE / name).is_file(), name)


class Report(unittest.TestCase):
    def test_the_median_rate_and_multiple(self):
        landin = dense_timing.summary([400_000_000, 500_000_000, 450_000_000])
        blas = dense_timing.summary([50_000_000, 50_000_000, 60_000_000])
        self.assertEqual(landin["median_seconds"], 0.45)
        self.assertAlmostEqual(blas["gflops"], 40.0)
        results = {"landin": landin, "openblas": blas, "multiple": 9.0}
        text = dense_timing.report(results)
        self.assertIn("median of 3 runs", text)
        self.assertIn("9.0 times OpenBLAS's time", text)


if __name__ == "__main__":
    unittest.main()
