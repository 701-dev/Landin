#!/usr/bin/env python3
"""core/unicode's tables are the pinned Unicode Character Database's own.

scripts/unicode_tables.py reads the database out of a pinned UCD.zip and
writes core/unicode/tables.ldn and the unicode-* fixtures' programs.  These
cases run it on a small database of their own, so what it reads, how it
lays a table out and what it refuses are held without the 9 MB archive;
and they hold the checked-in tables.ldn to the pin and to being its own
rendering.  When the pinned archive is in the inputs cache, as
`unicode_tables.py --fetch` leaves it, they also hold every generated file
to being exactly what the archive gives.
"""
import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "unicode_tables", ROOT / "scripts/unicode_tables.py")
unicode_tables = importlib.util.module_from_spec(spec)
spec.loader.exec_module(unicode_tables)

UNICODE_DATA = """\
0041;LATIN CAPITAL LETTER A;Lu;0;L;;;;;N;;;;0061;
0061;LATIN SMALL LETTER A;Ll;0;L;;;;;N;;;0041;;0041
00C0;LATIN CAPITAL LETTER A WITH GRAVE;Lu;0;L;0041 0300;;;;N;;;;00E0;
00DF;LATIN SMALL LETTER SHARP S;Ll;0;L;;;;;N;;;;;
00E0;LATIN SMALL LETTER A WITH GRAVE;Ll;0;L;0061 0300;;;;N;;;00C0;;00C0
0300;COMBINING GRAVE ACCENT;Mn;230;NSM;;;;;N;;;;;
0340;COMBINING GRAVE TONE MARK;Mn;230;NSM;0300;;;;N;;;;;
0316;COMBINING GRAVE ACCENT BELOW;Mn;220;NSM;;;;;N;;;;;
2460;CIRCLED DIGIT ONE;No;0;L;<circle> 0031;;1;1;N;;;;;
0031;DIGIT ONE;Nd;0;EN;;1;1;1;N;;;;;
AC00;<Hangul Syllable, First>;Lo;0;L;;;;;N;;;;;
D7A3;<Hangul Syllable, Last>;Lo;0;L;;;;;N;;;;;
"""
SPECIAL = """\
00DF; 00DF; 0053 0073; 0053 0053; # LATIN SMALL LETTER SHARP S
03A3; 03C2; 03A3; 03A3; Final_Sigma; # GREEK CAPITAL LETTER SIGMA
0049; 0069 0307; 0049; 0049; lt More_Above; # LATIN CAPITAL LETTER I
"""
FOLDING = """\
0041; C; 0061; # LATIN CAPITAL LETTER A
00C0; C; 00E0; # LATIN CAPITAL LETTER A WITH GRAVE
00DF; F; 0073 0073; # LATIN SMALL LETTER SHARP S
"""
MEMBERS = {
    "UnicodeData.txt": UNICODE_DATA,
    "PropList.txt": "0020 ; White_Space # Zs SPACE\n",
    "DerivedCoreProperties.txt": (
        "0041 ; Alphabetic\n0061 ; Alphabetic\n0041 ; Uppercase\n"
        "0061 ; Lowercase\n0041 ; Cased\n0061 ; Cased\n"
        "0300 ; Case_Ignorable\n0915 ; InCB; Consonant\n"),
    "DerivedNormalizationProps.txt":
        "0340 ; Full_Composition_Exclusion\n",
    "SpecialCasing.txt": SPECIAL,
    "CaseFolding.txt": FOLDING,
    "emoji/emoji-data.txt": "1F600 ; Extended_Pictographic\n",
    "auxiliary/GraphemeBreakProperty.txt":
        "000D ; CR\n000A ; LF\n0300 ; Extend\n",
    "auxiliary/WordBreakProperty.txt": "0041 ; ALetter\n0061 ; ALetter\n",
    "auxiliary/SentenceBreakProperty.txt": "002E ; ATerm\n",
    "NormalizationTest.txt": "@Part0\n00C0;00C0;0041 0300;00C0;0041 0300;\n",
    "auxiliary/GraphemeBreakTest.txt": "÷ 0041 × 0300 ÷ 0061 ÷\n",
    "auxiliary/WordBreakTest.txt": "÷ 0041 × 0061 ÷ 0020 ÷\n",
    "auxiliary/SentenceBreakTest.txt": "÷ 0041 × 002E ÷\n",
}


def archive(members=None):
    """A UCD.zip of MEMBERS in memory, and its digest."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as written:
        for name, text in (members or MEMBERS).items():
            written.writestr(name, text)
    data = buffer.getvalue()
    return data, hashlib.sha256(data).hexdigest()


class Small(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.directory))

    def database(self, members=None):
        data, digest = archive(members)
        path = self.directory / "UCD.zip"
        path.write_bytes(data)
        return unicode_tables.Database(
            unicode_tables.read_archive(path, digest))

    def test_an_archive_with_another_digest_is_refused_unread(self):
        data, _ = archive()
        path = self.directory / "UCD.zip"
        path.write_bytes(data)
        with self.assertRaisesRegex(unicode_tables.GeneratorError,
                                    "not the pinned"):
            unicode_tables.read_archive(path)

    def test_a_missing_member_is_refused(self):
        members = dict(MEMBERS)
        del members["CaseFolding.txt"]
        with self.assertRaisesRegex(unicode_tables.GeneratorError,
                                    "has no CaseFolding.txt"):
            self.database(members)

    def test_a_class_the_generator_does_not_know_is_refused(self):
        members = dict(MEMBERS)
        members["auxiliary/SentenceBreakProperty.txt"] = "002E ; Dot\n"
        with self.assertRaisesRegex(unicode_tables.GeneratorError,
                                    "unknown class Dot"):
            self.database(members)

    def test_what_the_database_says_is_read(self):
        found = self.database()
        index = unicode_tables.CATEGORY_INDEX
        self.assertEqual(found.category[0x41], index["Lu"])
        self.assertEqual(found.category[0xAC01], index["Lo"])
        self.assertEqual(found.category[0x42], index["Cn"])
        self.assertEqual(found.combining[0x316], 220)
        self.assertEqual(found.flags[0x20], 2)
        self.assertEqual(found.grapheme[0x915],
                         unicode_tables.CONJUNCT["Consonant"])
        self.assertEqual(found.word[0x1F600],
                         unicode_tables.PICTOGRAPHIC_WORD)
        #  A decomposition is read to the end, through a singleton; a
        #  compatibility one only when asked for.
        self.assertEqual(found.decomposed(0xC0, False), [0x41, 0x300])
        self.assertEqual(found.decomposed(0x340, False), [0x300])
        self.assertEqual(found.decomposed(0x2460, False), [0x2460])
        self.assertEqual(found.decomposed(0x2460, True), [0x31])
        self.assertEqual(found.decomposed(0xAC01, False),
                         [0x1100, 0x1161, 0x11A8])
        #  Only a primary composite the exclusions leave composes.
        self.assertEqual(found.composites(), {0x41: [(0x300, 0xC0)],
                                              0x61: [(0x300, 0xE0)]})
        #  A language's conditional mapping is not read; ß's are.
        self.assertNotIn(0x49, found.special["lower"])
        self.assertEqual(found.full("upper", 0xDF), [0x53, 0x53])
        self.assertEqual(found.full("fold", 0xDF), [0x73, 0x73])
        self.assertEqual(found.simple("upper", 0xDF), 0xDF)
        self.assertEqual(found.simple("fold", 0xC0), 0xE0)

    def test_a_trie_and_a_sparse_map_give_back_their_values(self):
        values = [(scalar * 7 // 300) % 5 for scalar in range(5000)]
        trie = unicode_tables.Trie(values, 8)
        self.assertEqual([trie.lookup(key) for key in range(5000)], values)
        self.assertEqual(trie.lookup(6000), 0)
        entries = {0x41: b"ab", 0x7F: b"c", 0x10FFFD: b"\xc3\xa9"}
        sparse = unicode_tables.Sparse(entries)
        for scalar in (0, 0x41, 0x42, 0x7F, 0x80, 0x10FFFD):
            self.assertEqual(sparse.lookup(scalar), entries.get(scalar))

    def test_what_is_rendered_reads_back(self):
        text = unicode_tables.render(self.database())
        self.assertEqual(unicode_tables.form_problems(text), [])
        changed = text.replace("categories: [30]", "categories: [31]")
        self.assertTrue(unicode_tables.form_problems(changed))
        moved = text.replace("\n    ", "\n     ", 1)
        self.assertTrue(unicode_tables.form_problems(moved))

    def test_the_fixtures_take_their_oracle_from_the_files(self):
        import unicode_fixtures
        written = unicode_fixtures.render_all(self.database())
        graphemes = written[unicode_tables.FIXTURES / "unicode-graphemes"
                            / "main.ldn"]
        #  "A" and its grave are one cluster, ending at byte 3; "a" ends
        #  the text at byte 4.
        self.assertIn("boundaries: [2]u16 = [\n    3, 4]", graphemes)


class CheckedIn(unittest.TestCase):
    def test_the_tables_are_rendered_under_the_pin(self):
        text = unicode_tables.OUTPUT.read_text(encoding="utf-8")
        self.assertEqual(unicode_tables.form_problems(text), [])

    def test_the_fixtures_name_the_pinned_release(self):
        for name in ("category", "properties", "case-scalars",
                     "normalization-canonical", "normalization-compatible",
                     "normalization-sequences", "graphemes", "words",
                     "sentences"):
            path = unicode_tables.FIXTURES / ("unicode-" + name) / "main.ldn"
            self.assertIn("Database %s;" % unicode_tables.VERSION,
                          path.read_text(encoding="utf-8"), path)

    def test_every_file_is_what_the_cached_archive_gives(self):
        cached = unicode_tables.cached_archive()
        if not cached.exists():
            self.skipTest("the pinned UCD.zip is not at %s; run"
                          " scripts/unicode_tables.py --fetch to hold the"
                          " files to it" % cached)
        self.assertEqual(unicode_tables.main(["--zip", str(cached),
                                              "--check"]), 0)


if __name__ == "__main__":
    unittest.main()
