#!/usr/bin/env python3
"""core/text's generated fixtures are what scripts/text_fixtures.py writes.

The radix oracle's reading of a text and the quoted form's spelling are
held here on cases whose answers are known by hand, and the checked-in
fixture programs to being the generator's output.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "text_fixtures", ROOT / "scripts/text_fixtures.py")
text_fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(text_fixtures)

VALUE = text_fixtures.VALUE
INVALID = text_fixtures.INVALID
OVERFLOW = text_fixtures.OVERFLOW


class Radix(unittest.TestCase):
    def outcome(self, text, radix, signed=False, bits=8):
        return text_fixtures.outcome(text, radix, signed, bits)

    def test_a_prefix_is_read_only_for_its_radix(self):
        self.assertEqual(self.outcome("0xff", 16), (VALUE, 255))
        self.assertEqual(self.outcome("0XFF", 16), (VALUE, 255))
        self.assertEqual(self.outcome("0b1", 16), (VALUE, 0xB1))
        self.assertEqual(self.outcome("0x1", 10), (INVALID, 0))
        self.assertEqual(self.outcome("0x", 16), (INVALID, 0))
        self.assertEqual(self.outcome("0x1", 36, bits=64),
                         (VALUE, int("0x1", 36)))

    def test_the_first_refusal_the_scan_meets_is_kept(self):
        self.assertEqual(self.outcome("256", 10), (OVERFLOW, 0))
        self.assertEqual(self.outcome("2560a", 10), (OVERFLOW, 0))
        self.assertEqual(self.outcome("25a6", 10), (INVALID, 0))
        self.assertEqual(self.outcome("-1", 10), (INVALID, 0))

    def test_a_signed_width_reaches_its_least_value(self):
        self.assertEqual(self.outcome("-80", 16, True), (VALUE, 2**64 - 128))
        self.assertEqual(self.outcome("-81", 16, True), (OVERFLOW, 0))
        self.assertEqual(self.outcome("80", 16, True), (OVERFLOW, 0))
        self.assertEqual(self.outcome("-0x7f", 16, True),
                         (VALUE, 2**64 - 127))

    def test_the_program_writes_every_text_the_oracle_reads(self):
        texts = list(text_fixtures.texts(16, True))
        self.assertIn("-0Xff0", texts)
        self.assertIn("0xffg", texts)
        self.assertEqual(len(texts), len(text_fixtures.MAGNITUDES) * 18)


class Quoted(unittest.TestCase):
    def test_escapes_and_unseen_scalars(self):
        self.assertEqual(text_fixtures.quoted('a"\\\n'), '"a\\"\\\\\\n"')
        self.assertEqual(text_fixtures.quoted("\x00\x7f‮"),
                         '"\\u{0}\\u{7f}\\u{202e}"')
        self.assertEqual(text_fixtures.quoted("é\U0001f600"),
                         '"é\U0001f600"')

    def test_the_spelling_escapes_all_but_printable_ascii(self):
        self.assertEqual(text_fixtures.spelled("aé\""),
                         '"a\\u{e9}\\""')


class CheckedIn(unittest.TestCase):
    def test_the_fixtures_are_what_the_generator_writes(self):
        self.assertEqual(text_fixtures.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
