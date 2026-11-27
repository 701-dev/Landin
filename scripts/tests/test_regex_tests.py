#!/usr/bin/env python3
"""core/regex's conformance cases are the pinned `regex` crate's own.

scripts/regex_tests.py reads Rust's `regex` test suite out of a crate
archive pinned by SHA-256 and writes runtime/regex-rust-suite's cases.ldn.
These cases run its readers on a small suite of their own, so which cases
it takes and how it writes them are held without the archive; and they
hold the checked-in cases.ldn to the pin.  When the pinned crate is in the
inputs cache, as `regex_tests.py --fetch` leaves it, they also hold the
file to being exactly what the crate gives.
"""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "regex_tests", ROOT / "scripts/regex_tests.py")
regex_tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(regex_tests)

SUITE = b"""\
[[test]]
name = "plain"
regex = "a(b)?"
haystack = "ab a"
matches = [[[0, 2], [1, 2]], [[3, 4], []]]

[[test]]
name = "set"
regex = ["a", "b"]
haystack = "ab"
matches = [[0, 1]]

[[test]]
name = "folded"
regex = "k"
haystack = "K"
matches = [[0, 1]]
case-insensitive = true
anchored = true

[[test]]
name = "bytes"
regex = "."
haystack = "\\\\xFF"
matches = []
unescape = true

[[test]]
name = "refused"
regex = "(a"
haystack = ""
matches = []
compiles = false
"""


class Taking(unittest.TestCase):
    def test_cases_are_taken_or_left_out_for_a_reason(self):
        taken, left = regex_tests.collect({"basic.toml": SUITE})
        self.assertEqual([case[0] for case in taken],
                         ["basic/plain", "basic/folded", "basic/refused"])
        self.assertEqual(left, {"a set of patterns": 1,
                                "a haystack that is not UTF-8": 1})
        plain, folded, refused = taken
        self.assertEqual(plain[4], [[(0, 2), (1, 2)], [(3, 4), None]])
        self.assertEqual(folded[1], b"(?i)k")
        self.assertEqual(folded[3], regex_tests.ANCHORED)
        self.assertEqual(refused[3], regex_tests.NO_COMPILE)

    def test_what_is_rendered_holds_every_group(self):
        taken, left = regex_tests.collect({"basic.toml": SUITE})
        text = regex_tests.render(taken, left)
        self.assertIn("case_count: usize = 3", text)
        self.assertIn("0xffffffff", text)
        self.assertIn("SHA-256 %s" % regex_tests.SHA256, text)

    def test_an_archive_with_another_digest_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "regex.crate"
            path.write_bytes(b"not the crate")
            with self.assertRaises(regex_tests.GeneratorError):
                regex_tests.read_crate(path)


class CheckedIn(unittest.TestCase):
    def test_the_cases_name_the_pinned_crate(self):
        self.assertEqual(regex_tests.main(["--check"]), 0)

    def test_the_cases_are_what_the_cached_crate_gives(self):
        cached = regex_tests.cached_crate()
        if not cached.exists():
            self.skipTest("the pinned crate is not at %s; run"
                          " scripts/regex_tests.py --fetch to hold the"
                          " cases to it" % cached)
        self.assertEqual(regex_tests.main(["--crate", str(cached),
                                           "--check"]), 0)


if __name__ == "__main__":
    unittest.main()
