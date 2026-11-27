#!/usr/bin/env python3
"""Write core/unicode's tables, and its conformance fixtures, from a pinned UCD.

    scripts/unicode_tables.py --fetch [DIR]
    scripts/unicode_tables.py --zip UCD.zip
    scripts/unicode_tables.py --zip UCD.zip --check
    scripts/unicode_tables.py --check

The tables are the Unicode Character Database's own, read out of the
release's UCD.zip named by VERSION, URL and SHA256 below and never typed by
hand.  `--fetch` downloads that archive into DIR, which must be new or
empty, and `--zip` names one already downloaded; either way its SHA-256
must be the pinned one before a byte of it is read.  `--fetch` without a
DIR downloads it into the inputs cache, $LANDIN_INPUTS or
~/.cache/landin/inputs, as unicode-VERSION/UCD.zip, where the script test
finds it and then holds every generated file to it.  The members are read
straight out of the archive and nothing is extracted.

It writes core/unicode/tables.ldn, every table core/unicode reads, private
to the module, and the `unicode-*` runtime fixtures under
compiler/tests/fixtures/runtime/ whose programs the conformance files and
the database give: each fixture's `main.ldn`, whose header names the
release.  `--check` compares every one of those files with what the archive
gives instead of writing them.  With no archive named, `--check` holds each
file to having been written under the pin named below, and tables.ldn to
being its own rendering: its arrays read back and written again give the
same bytes.  scripts/tests/test_unicode_tables.py runs that check, and the
generator on a small database of its own.

What each table holds, and how it is laid out, is said in the header
tables.ldn is written with (HEADER below), and the decision that settles
it is D2614.

Standard library only, so it runs wherever check.py does.
"""

import argparse
from array import array as words
import hashlib
import os
import pathlib
import re
import sys
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / "core/unicode"
OUTPUT = MODULE / "tables.ldn"
FIXTURES = ROOT / "compiler/tests/fixtures/runtime"

VERSION = "18.0.0"
URL = "https://www.unicode.org/Public/18.0.0/ucd/UCD.zip"
SHA256 = "7b3e555514060b92290d154f53655c5eb0fa62b16eb04c03434ff72d1a66a0d8"

LIMIT = 0x110000
SURROGATES = range(0xD800, 0xE000)

#  Hangul syllables decompose and compose by arithmetic (Unicode's 3.12),
#  so no table holds them.
S_BASE, L_BASE, V_BASE, T_BASE = 0xAC00, 0x1100, 0x1161, 0x11A7
L_COUNT, V_COUNT, T_COUNT = 19, 21, 28
N_COUNT = V_COUNT * T_COUNT
S_COUNT = L_COUNT * N_COUNT

#  The general categories, in the order `categories` lists their atoms.
CATEGORIES = (
    ("Lu", "uppercase_letter"), ("Ll", "lowercase_letter"),
    ("Lt", "titlecase_letter"), ("Lm", "modifier_letter"),
    ("Lo", "other_letter"), ("Mn", "nonspacing_mark"),
    ("Mc", "spacing_mark"), ("Me", "enclosing_mark"),
    ("Nd", "decimal_number"), ("Nl", "letter_number"),
    ("No", "other_number"), ("Pc", "connector_punctuation"),
    ("Pd", "dash_punctuation"), ("Ps", "open_punctuation"),
    ("Pe", "close_punctuation"), ("Pi", "initial_punctuation"),
    ("Pf", "final_punctuation"), ("Po", "other_punctuation"),
    ("Sm", "math_symbol"), ("Sc", "currency_symbol"),
    ("Sk", "modifier_symbol"), ("So", "other_symbol"),
    ("Zs", "space_separator"), ("Zl", "line_separator"),
    ("Zp", "paragraph_separator"), ("Cc", "control"),
    ("Cf", "format"), ("Cs", "surrogate"), ("Co", "private_use"),
    ("Cn", "unassigned"),
)
CATEGORY_INDEX = {short: index for index, (short, _) in
                  enumerate(CATEGORIES)}

#  The binary properties `flags` holds, one bit each, and the file each
#  comes from.
FLAGS = (
    ("alphabetic", "DerivedCoreProperties.txt", "Alphabetic"),
    ("white_space", "PropList.txt", "White_Space"),
    ("uppercase", "DerivedCoreProperties.txt", "Uppercase"),
    ("lowercase", "DerivedCoreProperties.txt", "Lowercase"),
    ("cased", "DerivedCoreProperties.txt", "Cased"),
    ("case_ignorable", "DerivedCoreProperties.txt", "Case_Ignorable"),
)
#  The first of FLAGS that `case_context_code` holds rather than
#  `flag_code`.
CONTEXT_BIT = 4

#  Each segmentation property's values, in the order of their codes; the
#  first is the default of a scalar its file does not list.
GRAPHEME = ("Other", "CR", "LF", "Control", "Extend", "ZWJ",
            "Regional_Indicator", "Prepend", "SpacingMark", "L", "V", "T",
            "LV", "LVT")
WORD = ("Other", "CR", "LF", "Newline", "Extend", "ZWJ",
        "Regional_Indicator", "Format", "Katakana", "Hebrew_Letter",
        "ALetter", "Single_Quote", "Double_Quote", "MidNumLet", "MidLetter",
        "MidNum", "Numeric", "ExtendNumLet", "WSegSpace")
SENTENCE = ("Other", "CR", "LF", "Extend", "Sep", "Format", "Sp", "Lower",
            "Upper", "OLetter", "Numeric", "ATerm", "STerm", "Close",
            "SContinue")
#  The bits above a grapheme or word class: Extended_Pictographic, and a
#  grapheme's Indic_Conjunct_Break.
PICTOGRAPHIC_GRAPHEME = 16
PICTOGRAPHIC_WORD = 32
CONJUNCT = {"Consonant": 32, "Extend": 64, "Linker": 96}

MEMBERS = (
    "UnicodeData.txt", "PropList.txt", "DerivedCoreProperties.txt",
    "DerivedNormalizationProps.txt", "SpecialCasing.txt", "CaseFolding.txt",
    "emoji/emoji-data.txt", "auxiliary/GraphemeBreakProperty.txt",
    "auxiliary/WordBreakProperty.txt", "auxiliary/SentenceBreakProperty.txt",
    "NormalizationTest.txt", "auxiliary/GraphemeBreakTest.txt",
    "auxiliary/WordBreakTest.txt", "auxiliary/SentenceBreakTest.txt",
)


class GeneratorError(Exception):
    """An archive or a member the generator refuses, and why."""


# ---------------------------------------------------------------- reading

def read_archive(path, digest=SHA256):
    """Every member the generator reads, by name, from a verified archive."""
    data = pathlib.Path(path).read_bytes()
    found = hashlib.sha256(data).hexdigest()
    if found != digest:
        raise GeneratorError(
            "%s has SHA-256 %s, not the pinned %s" % (path, found, digest))
    members = {}
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        for member in MEMBERS:
            if member not in names:
                raise GeneratorError("%s has no %s" % (path, member))
            members[member] = archive.read(member).decode("utf-8")
    return members


def cached_archive():
    """Where `--fetch` without a directory puts the pinned archive."""
    named = os.environ.get("LANDIN_INPUTS")
    root = (pathlib.Path(named) if named
            else pathlib.Path.home() / ".cache/landin/inputs")
    return root / ("unicode-%s" % VERSION) / "UCD.zip"


def fetch(directory=None):
    """Download the pinned archive into DIRECTORY, new or empty."""
    directory = (pathlib.Path(directory) if directory
                 else cached_archive().parent)
    if directory.exists() and any(directory.iterdir()):
        raise GeneratorError("%s is not empty" % directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "UCD.zip"
    with urllib.request.urlopen(URL) as response:
        target.write_bytes(response.read())
    read_archive(target)
    return target


def records(text):
    """(first, last, fields) for each data line of a UCD property file."""
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        fields = [field.strip() for field in line.split(";")]
        span = fields[0].split("..")
        first = int(span[0], 16)
        last = int(span[-1], 16)
        yield first, last, fields[1:]


def scalars(field):
    """The scalars a space-separated list of hexadecimal numbers names."""
    return [int(part, 16) for part in field.split()]


class Database:
    """What the tables and the fixtures need of one release."""

    def __init__(self, members):
        self.members = members
        self.category = [CATEGORY_INDEX["Cn"]] * LIMIT
        self.combining = [0] * LIMIT
        self.mapping = {}           # scalar -> (compatibility, scalars)
        self.upper = {}
        self.lower = {}
        self.title = {}
        self.read_unicode_data(members["UnicodeData.txt"])
        self.flags = [0] * LIMIT
        for bit, (_, member, name) in enumerate(FLAGS):
            for first, last, fields in records(members[member]):
                if fields[0] == name:
                    for scalar in range(first, last + 1):
                        self.flags[scalar] |= 1 << bit
        self.exclusions = set()
        for first, last, fields in records(
                members["DerivedNormalizationProps.txt"]):
            if fields[0] == "Full_Composition_Exclusion":
                self.exclusions.update(range(first, last + 1))
        self.read_casing(members["SpecialCasing.txt"],
                         members["CaseFolding.txt"])
        self.read_segmentation()

    def read_unicode_data(self, text):
        opened = None
        for line in text.splitlines():
            if not line.strip():
                continue
            fields = line.split(";")
            scalar = int(fields[0], 16)
            name = fields[1]
            span = [scalar]
            if name.endswith(", First>"):
                opened = scalar
                continue
            if name.endswith(", Last>"):
                if opened is None:
                    raise GeneratorError("a range's last line has no first")
                span = range(opened, scalar + 1)
                opened = None
            for each in span:
                self.category[each] = CATEGORY_INDEX[fields[2]]
                self.combining[each] = int(fields[3])
            decomposition = fields[5]
            if decomposition:
                compatibility = decomposition.startswith("<")
                if compatibility:
                    decomposition = decomposition.split(">", 1)[1]
                self.mapping[scalar] = (compatibility,
                                        scalars(decomposition))
            for column, into in ((12, self.upper), (13, self.lower),
                                 (14, self.title)):
                if fields[column]:
                    into[scalar] = int(fields[column], 16)

    def read_casing(self, special, folding):
        #  SpecialCasing's unconditional mappings; of its conditional ones
        #  only Final_Sigma holds in every language, and it is the code's.
        self.special = {"upper": {}, "lower": {}, "title": {}}
        for line in special.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            fields = [field.strip() for field in line.split(";")]
            if len(fields) > 5 and fields[4]:
                continue
            scalar = int(fields[0], 16)
            self.special["lower"][scalar] = scalars(fields[1])
            self.special["title"][scalar] = scalars(fields[2])
            self.special["upper"][scalar] = scalars(fields[3])
        self.fold_simple = {}
        self.fold_full = {}
        for first, _, fields in records(folding):
            status, target = fields[0], scalars(fields[1])
            if status in ("C", "S"):
                self.fold_simple[first] = target[0]
            if status in ("C", "F"):
                self.fold_full[first] = target

    def read_segmentation(self):
        members = self.members
        pictographic = set()
        for first, last, fields in records(members["emoji/emoji-data.txt"]):
            if fields[0] == "Extended_Pictographic":
                pictographic.update(range(first, last + 1))
        self.grapheme = self.classes(
            members["auxiliary/GraphemeBreakProperty.txt"], GRAPHEME)
        self.word = self.classes(
            members["auxiliary/WordBreakProperty.txt"], WORD)
        self.sentence = self.classes(
            members["auxiliary/SentenceBreakProperty.txt"], SENTENCE)
        for scalar in pictographic:
            self.grapheme[scalar] |= PICTOGRAPHIC_GRAPHEME
            self.word[scalar] |= PICTOGRAPHIC_WORD
        for first, last, fields in records(
                members["DerivedCoreProperties.txt"]):
            if fields[0] == "InCB":
                for scalar in range(first, last + 1):
                    self.grapheme[scalar] |= CONJUNCT[fields[1]]

    @staticmethod
    def classes(text, values):
        codes = {name: code for code, name in enumerate(values)}
        result = [0] * LIMIT
        for first, last, fields in records(text):
            if fields[0] not in codes:
                raise GeneratorError("an unknown class %s" % fields[0])
            for scalar in range(first, last + 1):
                result[scalar] = codes[fields[0]]
        return result

    # -- what the code computes, from the data directly

    def decomposed(self, scalar, compatibility):
        """The full decomposition of one scalar, Hangul's included."""
        if S_BASE <= scalar < S_BASE + S_COUNT:
            index = scalar - S_BASE
            result = [L_BASE + index // N_COUNT,
                      V_BASE + (index % N_COUNT) // T_COUNT]
            if index % T_COUNT:
                result.append(T_BASE + index % T_COUNT)
            return result
        found = self.mapping.get(scalar)
        if found is None or (found[0] and not compatibility):
            return [scalar]
        result = []
        for part in found[1]:
            result.extend(self.decomposed(part, compatibility))
        return result

    def composites(self):
        """first -> [(second, composite)] for every primary composite."""
        pairs = {}
        for scalar, (compatibility, parts) in sorted(self.mapping.items()):
            if compatibility or len(parts) != 2:
                continue
            if scalar in self.exclusions:
                continue
            pairs.setdefault(parts[0], []).append((parts[1], scalar))
        return pairs

    def simple(self, kind, scalar):
        if kind == "fold":
            return self.fold_simple.get(scalar, scalar)
        return getattr(self, kind).get(scalar, scalar)

    def full(self, kind, scalar):
        if kind == "fold":
            if scalar in self.fold_full:
                return self.fold_full[scalar]
            return [scalar]
        if scalar in self.special[kind]:
            return self.special[kind][scalar]
        return [self.simple(kind, scalar)]


# ----------------------------------------------------------------- layout

def width(count):
    """The narrowest unsigned type holding every value below COUNT."""
    if count <= 256:
        return 8
    if count <= 65536:
        return 16
    return 32


def dedupe(values, size):
    """Split VALUES into blocks of SIZE: the distinct blocks, and each one's."""
    values = list(values)
    if len(values) % size:
        values += [0] * (size - len(values) % size)
    packed = words("I", values).tobytes()
    step = size * 4
    blocks, index, where = [], [], {}
    for start in range(0, len(packed), step):
        block = packed[start:start + step]
        found = where.get(block)
        if found is None:
            found = where[block] = len(blocks)
            blocks.append(tuple(words("I", block)))
        index.append(found)
    return blocks, index


class Trie:
    """A lookup of a value per key below DOMAIN in a few stages.

    A key's low bits index a block of the values, the next bits a block of
    those blocks' numbers, and so on, until the key's remaining high bits
    index the top array.  Blocks repeat, as most of the code space does, so
    each is kept once.  Of every split into at most DEPTH stages below the
    top the generator keeps the smallest.
    """

    DEPTH = 4

    def __init__(self, values, value_width):
        self.value_width = value_width
        self.domain = len(values)
        self.memo = {}
        self.size, self.shifts = self.plan(tuple(values), value_width,
                                           self.DEPTH)
        del self.memo
        #  stages[0] holds the values, stages[-1] is the top array.
        self.stages = [list(values)]
        self.widths = [value_width]
        for shift in self.shifts:
            blocks, numbers = dedupe(self.stages[-1], 1 << shift)
            self.stages[-1] = [value for block in blocks for value in block]
            self.stages.append(numbers)
            self.widths.append(width(len(blocks)))

    def plan(self, values, bits, depth):
        """The smallest (bytes, shifts) storing VALUES at BITS each."""
        key = (values, bits, depth)
        if key in self.memo:
            return self.memo[key]
        best = (len(values) * bits // 8, ())
        if depth:
            for shift in range(1, 9):
                blocks, numbers = dedupe(values, 1 << shift)
                stored = len(blocks) * (1 << shift) * bits // 8
                if stored >= best[0]:
                    continue
                below = self.plan(tuple(numbers), width(len(blocks)),
                                  depth - 1)
                if stored + below[0] < best[0]:
                    best = (stored + below[0], (shift,) + below[1])
        self.memo[key] = best
        return best

    def uniform(self):
        """For each stage below the top, each of its blocks' one value
        when every key under the block has it, and UNIFORM otherwise."""
        found = []
        for level, shift in enumerate(self.shifts):
            size = 1 << shift
            stage = self.stages[level]
            values = []
            for start in range(0, len(stage), size):
                block = stage[start:start + size]
                if level == 0:
                    first = block[0]
                    same = all(value == first for value in block)
                else:
                    below = found[level - 1]
                    first = below[block[0]]
                    same = all(below[number] == first for number in block)
                values.append(first if same else UNIFORM)
            found.append(values)
        return found

    def lookup(self, key):
        if key >= self.domain:
            return 0
        low = sum(self.shifts)
        at = self.stages[-1][key >> low]
        for level in range(len(self.shifts) - 1, -1, -1):
            shift = self.shifts[level]
            low -= shift
            at = self.stages[level][(at << shift)
                                    | ((key >> low) & ((1 << shift) - 1))]
        return at


class Sparse:
    """A map from some scalars to byte strings, most scalars mapping to none.

    A scalar's block of 64 is found by a Trie over the scalar's upper bits,
    zero for a block that maps nothing.  A block holds a 64-bit mask of
    which of its scalars map, and where its entries begin in POOL: one per
    mapped scalar, in scalar order, each its length in bytes then its bytes.
    """

    def __init__(self, entries):
        blocks = {}
        for scalar in sorted(entries):
            blocks.setdefault(scalar >> 6, []).append(scalar)
        numbers = [0] * (LIMIT >> 6)
        self.masks = [0]
        self.bases = [0]
        self.pool = []
        for block in sorted(blocks):
            numbers[block] = len(self.masks)
            mask = 0
            self.bases.append(len(self.pool))
            for scalar in blocks[block]:
                mask |= 1 << (scalar & 63)
                entry = entries[scalar]
                if not 0 < len(entry) < 256:
                    raise GeneratorError("an entry of %d bytes" % len(entry))
                self.pool.append(len(entry))
                self.pool.extend(entry)
            self.masks.append(mask)
        self.blocks = Trie(numbers, width(len(self.masks)))
        if len(self.pool) > 65535:
            raise GeneratorError("a pool of %d bytes, past a u16 base"
                                 % len(self.pool))
        self.base_width = 16
        self.size = (self.blocks.size + len(self.masks) * 8
                     + len(self.bases) * self.base_width // 8
                     + len(self.pool))

    def lookup(self, scalar):
        number = self.blocks.lookup(scalar >> 6)
        mask = self.masks[number]
        bit = scalar & 63
        if not mask >> bit & 1:
            return None
        at = self.bases[number]
        for below in range(bit):
            if mask >> below & 1:
                at += 1 + self.pool[at]
        return bytes(self.pool[at + 1:at + 1 + self.pool[at]])


def encoded(sequence):
    return "".join(chr(scalar) for scalar in sequence).encode("utf-8")


def case_records(database):
    """Each scalar's case record number, the records, and the specials.

    A record is the four simple mappings as differences from the scalar,
    upper, lower, title and fold, and whether a full mapping differs from
    its simple one; a special scalar's four full mappings are its entries.
    """
    kinds = ("upper", "lower", "title", "fold")
    numbers = [0] * LIMIT
    found = {(0, 0, 0, 0, 0): 0}
    table = [(0, 0, 0, 0, 0)]
    specials = {}
    mapped = set(database.upper) | set(database.lower) | set(database.title)
    mapped |= set(database.fold_simple) | set(database.fold_full)
    for kind in ("upper", "lower", "title"):
        mapped |= set(database.special[kind])
    for scalar in sorted(mapped):
        if scalar in SURROGATES:
            continue
        deltas = tuple(database.simple(kind, scalar) - scalar
                       for kind in kinds)
        fulls = [database.full(kind, scalar) for kind in kinds]
        special = any(full != [database.simple(kind, scalar)]
                      for kind, full in zip(kinds, fulls))
        record = deltas + (int(special),)
        if record not in found:
            found[record] = len(table)
            table.append(record)
        numbers[scalar] = found[record]
        if special:
            specials[scalar] = fulls
    return numbers, table, specials


def decompositions(database):
    """The canonical and the compatibility decomposition entries."""
    canonical = {}
    compatibility = {}
    for scalar in range(LIMIT):
        if scalar in SURROGATES or S_BASE <= scalar < S_BASE + S_COUNT:
            continue
        exact = database.decomposed(scalar, False)
        wide = database.decomposed(scalar, True)
        if exact != [scalar]:
            canonical[scalar] = encoded(exact)
        if wide != exact:
            compatibility[scalar] = encoded(wide)
    return canonical, compatibility


def composed_pairs(database):
    """The composition entries: each first scalar's pairs, UTF-8."""
    return {first: encoded([scalar for pair in seconds for scalar in pair])
            for first, seconds in database.composites().items()}


# -------------------------------------------------------------- rendering

HEADER = """\
--  core/unicode's tables, generated by scripts/unicode_tables.py from the
--  Unicode Character Database {version}:
--  {url}
--  SHA-256 {sha256}.
--  Do not edit it: change the pin in the generator and run it again.
--  The values are Unicode, Inc.'s, copyright 1991-2026, under the Unicode
--  License V3, whose notice is core/unicode/LICENSE.unicode.
--
--  Every name is private to core/unicode, whose routines read them, and a
--  table a program's routines never reach is not in its image (D296).
--  Each is immutable, so a firmware image keeps it in flash (D2614).
--
--  A property of every scalar is a three-stage lookup: a scalar's high
--  bits index the top array, which gives a block of the middle array, the
--  next bits a place in that block, which gives a block of the leaves, and
--  the low bits the value there.  Blocks repeat, most of the code space
--  being alike, so each is kept once, and the generator keeps the split
--  that makes the three arrays smallest.  A map that only some scalars
--  have, a decomposition or a composition, is the same lookup of the
--  scalar's block of 64, whose 64-bit mask says which of its scalars have
--  an entry and whose base says where its entries begin in the pool: one
--  for each, in scalar order, its length in bytes and then its bytes,
--  UTF-8 for a sequence of scalars.
"""


def rows(values, indent="    ", limit=79):
    """VALUES as array literal lines no longer than LIMIT."""
    lines, line = [], indent
    for index, value in enumerate(values):
        piece = value + ("," if index + 1 < len(values) else "]")
        if line != indent and len(line) + 1 + len(piece) > limit:
            lines.append(line.rstrip())
            line = indent
        line += ("" if line == indent else " ") + piece
    lines.append(line)
    return lines


def array(name, element, values, hexadecimal=False):
    if hexadecimal:
        written = ["0x%x" % value for value in values]
    else:
        written = [str(value) for value in values]
    return ["%s: [%d]%s = [" % (name, len(values), element)] + rows(written)


def unsigned(bits):
    return "u%d" % bits


def stage_name(name, level, top):
    if level == 0:
        return name + "_leaves"
    if level == top:
        return name + "_top"
    return "%s_stage%d" % (name, level)


#  A block's value in a `_uniform` array when its keys' values differ.
UNIFORM = 255


def render_runs(name, trie):
    """TRIE's `_uniform` arrays and NAME_run, which gives the last key of
    the run of keys from KEY on that share KEY's value: it steps over a
    block whose keys all have that value at once, the largest first."""
    lines = ["", "--  For each block of each stage of `%s` below its top, the"
             % name, "--  value every key under it has, or %d when they differ."
             % UNIFORM]
    top = len(trie.shifts)
    for level, values in enumerate(trie.uniform()):
        lines += array("%s_uniform%d" % (name, level), "u8", values)
    low = sum(trie.shifts)
    lines += [
        "",
        "%s_run: (key: u32) -> (last: u32) =" % name,
        "    last = key",
        "    return when key >= %s" % hex(trie.domain),
        "    value: u8 = u8(%s(key))" % name,
        "    mut next: u32 = key",
        "    loop do",
        "        mut at: usize = usize(%s[usize(next >> %d)])"
        % (stage_name(name, top, top), low),
    ]
    span = low
    indent = "        "
    closes = []
    for level in range(top - 1, -1, -1):
        lines.append("%sif %s_uniform%d[at] == value then" % (indent, name,
                                                             level))
        lines.append("%s    next = (next | %s) + 1" % (indent,
                                                       hex((1 << span) - 1)))
        lines.append("%selse" % indent)
        shift = trie.shifts[level]
        span -= shift
        part = ("usize(next & %d)" % ((1 << shift) - 1) if span == 0 else
                "usize((next >> %d) & %d)" % (span, (1 << shift) - 1))
        read = "%s[(at << %d) | %s]" % (stage_name(name, level, top), shift,
                                       part)
        indent += "    "
        if level:
            lines.append("%sat = usize(%s)" % (indent, read))
        else:
            lines.append("%sbreak when u8(%s) <> value" % (indent, read))
            lines.append("%snext = next + 1" % indent)
        closes.append(indent[:-4] + "end if")
    lines += list(reversed(closes))
    lines += [
        "        last = next - 1",
        "        break when next >= %s" % hex(trie.domain),
        "    end loop",
        "end %s_run" % name,
    ]
    return lines


def render_trie(name, comment, trie, result, runs=False):
    """The arrays of TRIE and the routine that reads it, named NAME, and
    with RUNS its run routine."""
    lines = ["", "--  " + comment]
    top = len(trie.shifts)
    for level in range(top, -1, -1):
        lines += array(stage_name(name, level, top),
                       unsigned(trie.widths[level]), trie.stages[level])
    low = sum(trie.shifts)
    lines += [
        "",
        "%s: (key: u32) -> (value: %s) =" % (name, result),
        "    value = %s(0)" % result,
        "    return when key >= %s" % hex(trie.domain),
    ]
    if top == 0:
        lines.append("    value = %s(%s[usize(key)])"
                     % (result, stage_name(name, 0, 0)))
    else:
        lines.append("    mut at: usize = usize(%s[usize(key >> %d)])"
                     % (stage_name(name, top, top), low))
    for level in range(top - 1, -1, -1):
        shift = trie.shifts[level]
        low -= shift
        part = ("usize(key & %d)" % ((1 << shift) - 1) if low == 0 else
                "usize((key >> %d) & %d)" % (low, (1 << shift) - 1))
        read = "%s[(at << %d) | %s]" % (stage_name(name, level, top),
                                       shift, part)
        if level:
            lines.append("    at = usize(%s)" % read)
        else:
            lines.append("    value = %s(%s)" % (result, read))
    lines.append("end %s" % name)
    if runs:
        lines += render_runs(name, trie)
    return lines


def render_sparse(name, comment, sparse):
    """A Sparse map's arrays and its block lookup, named NAME."""
    lines = render_trie(name + "_block", comment + "; its blocks",
                        sparse.blocks, "usize")
    lines += array(name + "_masks", "u64", sparse.masks, hexadecimal=True)
    lines += array(name + "_bases", unsigned(sparse.base_width),
                   sparse.bases)
    lines += array(name + "_pool", "u8", sparse.pool)
    return lines


def constants(prefix, values, comment):
    lines = ["", "--  " + comment]
    for code, value in enumerate(values):
        lines.append("%s_%s: u8 = %d" % (prefix, value.lower(), code))
    return lines


def render(database, version=VERSION, url=URL, sha256=SHA256):
    """tables.ldn's text."""
    lines = HEADER.format(version=version, url=url,
                          sha256=sha256).rstrip("\n").split("\n")
    lines += ["", "--- The version of the Unicode Character Database every",
              "--- table and routine of core/unicode follows."]
    major, minor, update = (int(part) for part in version.split("."))
    lines += ["public unicode_version: version_number = (major: %d, "
              "minor: %d, update: %d)" % (major, minor, update)]
    lines += ["", "--  The atom of each general category's code."]
    lines += ["categories: [%d]general_category = [" % len(CATEGORIES)]
    lines += rows([atom for _, atom in CATEGORIES])
    lines += render_trie("category_code",
                         "Each scalar's general category, a code of"
                         " `categories`.",
                         Trie(database.category, 8), "u8", runs=True)
    lines += render_trie("combining_code",
                         "Each scalar's canonical combining class.",
                         Trie(database.combining, 8), "u8")
    lines += ["", "--  The bits of `flag_code`, one per binary property, and of",
              "--  `case_context_code`, the two case mapping reads, in a table",
              "--  of their own so that it links no other (D2614)."]
    for bit, (name, _, _) in enumerate(FLAGS):
        lines.append("%s_bit: u8 = %d" % (name, 1 << (bit % CONTEXT_BIT)))
    lines += render_trie("flag_code",
                         "Each scalar's binary properties but the case"
                         " context's, one bit each.",
                         Trie([flags & ((1 << CONTEXT_BIT) - 1)
                               for flags in database.flags], 8), "u8",
                         runs=True)
    lines += render_trie("case_context_code",
                         "Each scalar's Cased and Case_Ignorable bits.",
                         Trie([flags >> CONTEXT_BIT
                               for flags in database.flags], 8), "u8",
                         runs=True)

    numbers, table, specials = case_records(database)
    lines += render_trie("case_code",
                         "Each scalar's case record, an index of the"
                         " `case_` arrays.",
                         Trie(numbers, width(len(table))), "usize")
    lines += ["", "--  Each case record's simple mappings, as differences"
              " from the scalar,", "--  and whether it has full mappings"
              " of its own in `case_full`."]
    for column, kind in enumerate(("upper", "lower", "title", "fold")):
        lines += array("case_" + kind, "i32",
                       [record[column] for record in table])
    lines += array("case_special", "bool",
                   ["true" if record[4] else "false" for record in table])
    full = {scalar: b"".join(bytes([len(encoded(mapping))])
                             + encoded(mapping) for mapping in fulls)
            for scalar, fulls in specials.items()}
    lines += render_sparse(
        "case_full", "The full upper, lower, title and folded mappings of a"
        " scalar whose\n--  record is special, four entries of one", Sparse(full))

    canonical, compatibility = decompositions(database)
    lines += render_sparse("canonical",
                           "Each scalar's full canonical decomposition,"
                           " Hangul's aside", Sparse(canonical))
    lines += render_sparse("compatible",
                           "Each scalar's full compatibility decomposition"
                           " where it is not its\n--  canonical one",
                           Sparse(compatibility))
    composed = composed_pairs(database)
    lines += render_sparse("composite",
                           "The primary composites each first scalar"
                           " begins, as pairs of the second\n--  and the"
                           " composite, Hangul's aside", Sparse(composed))

    lines += constants("grapheme", GRAPHEME,
                       "The grapheme cluster break classes, the low four"
                       " bits of `grapheme_code`.")
    lines += ["pictographic_grapheme_bit: u8 = %d" % PICTOGRAPHIC_GRAPHEME,
              "conjunct_mask: u8 = 96"]
    for name, code in sorted(CONJUNCT.items(), key=lambda item: item[1]):
        lines.append("conjunct_%s: u8 = %d" % (name.lower(), code))
    lines += render_trie("grapheme_code",
                         "Each scalar's grapheme class, Extended_"
                         "Pictographic and Indic_Conjunct_Break.",
                         Trie(database.grapheme, 8), "u8")
    lines += constants("word", WORD,
                       "The word break classes, the low five bits of"
                       " `word_code`.")
    lines += ["pictographic_word_bit: u8 = %d" % PICTOGRAPHIC_WORD]
    lines += render_trie("word_code",
                         "Each scalar's word class and Extended_"
                         "Pictographic.", Trie(database.word, 8), "u8")
    lines += constants("sentence", SENTENCE,
                       "The sentence break classes, `sentence_code`'s"
                       " values.")
    lines += render_trie("sentence_code", "Each scalar's sentence class.",
                         Trie(database.sentence, 8), "u8")
    return "\n".join(fix_comments(lines)) + "\n"


REGEX_FOLDS = ROOT / "core/regex/folds.ldn"

FOLDS_HEADER = """\
--  Generated by scripts/unicode_tables.py from the Unicode Character
--  Database {version}; do not edit it.

--  The scalars whose simple case folding is another's but which no
--  simple mapping of a scalar of their orbit reaches, nor the upper or
--  title case of the orbit's folding: the Kelvin sign, whose folding is
--  k's, among them.  A case-insensitive class adds them by testing each
--  one's folding (`add_orbit`).
"""


def fold_extras(database):
    """The scalars of a simple case-folding orbit that `add_orbit` in
    core/regex/classes.ldn reaches from no other member: it tries a
    scalar's folding, its simple upper, lower and title mappings, and the
    folding's upper and title mappings, then these."""
    def fold(scalar):
        return database.fold_simple.get(scalar, scalar)

    orbits = {}
    for scalar in sorted(set(database.fold_simple)
                         | set(database.fold_simple.values())):
        orbits.setdefault(fold(scalar), set()).add(scalar)
    extras = set()
    for members in orbits.values():
        for scalar in members:
            folded = fold(scalar)
            reached = {folded, database.upper.get(scalar, scalar),
                       database.lower.get(scalar, scalar),
                       database.title.get(scalar, scalar),
                       database.upper.get(folded, folded),
                       database.title.get(folded, folded)}
            extras |= members - {scalar} - {other for other in reached
                                             if fold(other) == folded}
    return sorted(extras)


def render_folds(database, version=VERSION):
    """core/regex/folds.ldn's text."""
    extras = fold_extras(database)
    lines = FOLDS_HEADER.format(version=version).rstrip("\n").split("\n")
    lines += array("fold_extras", "u32", [hex(value) for value in extras])
    return "\n".join(lines) + "\n"


def fix_comments(lines):
    """Split the embedded newlines some comments carry into lines."""
    out = []
    for line in lines:
        out.extend(line.split("\n"))
    return out


def sizes(database):
    """Bytes each table takes, for the report and the decision."""
    numbers, table, specials = case_records(database)
    report = {
        "category": Trie(database.category, 8).size,
        "combining": Trie(database.combining, 8).size,
        "flags": Trie([flags & 15 for flags in database.flags], 8).size,
        "case_context": Trie([flags >> 4 for flags in database.flags],
                             8).size,
        "case": Trie(numbers, width(len(table))).size + 17 * len(table),
        "grapheme": Trie(database.grapheme, 8).size,
        "word": Trie(database.word, 8).size,
        "sentence": Trie(database.sentence, 8).size,
    }
    canonical, compatibility = decompositions(database)
    full = {scalar: b"".join(bytes([len(encoded(mapping))])
                             + encoded(mapping) for mapping in fulls)
            for scalar, fulls in specials.items()}
    report["case_full"] = Sparse(full).size
    report["canonical"] = Sparse(canonical).size
    report["compatible"] = Sparse(compatibility).size
    report["composite"] = Sparse(composed_pairs(database)).size
    return report


# ------------------------------------------------------------------- main

def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--fetch", metavar="DIR", nargs="?", const="")
    source.add_argument("--zip", metavar="PATH")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--sizes", action="store_true")
    options = parser.parse_args(arguments)
    try:
        path = options.zip
        if options.fetch is not None:
            path = fetch(options.fetch or None)
        if path is None:
            if not options.check:
                parser.error("name the release with --zip or --fetch")
            return check_form()
        database = Database(read_archive(path))
        if options.sizes:
            for name, size in sizes(database).items():
                print("%-10s %6d" % (name, size))
            return 0
        problems = white_space_problems(database)
        if problems:
            raise GeneratorError(problems)
        written = {OUTPUT: render(database),
                   REGEX_FOLDS: render_folds(database)}
        import unicode_fixtures
        written.update(unicode_fixtures.render_all(database))
        return write_or_check(written, options.check)
    except GeneratorError as problem:
        print("unicode_tables.py: %s" % problem, file=sys.stderr)
        return 1


#  core/text writes Unicode's White_Space as comparisons in one routine,
#  so that trimming and fields carry no table; the database holds it.
WHITE_SPACE_SOURCE = ROOT / "core/text/parts.ldn"
WHITE_SPACE_BIT = 1


def white_space_written(text):
    """The scalars core/text's `white_space` routine names."""
    found = re.search(r"^white_space: .*?^end white_space$", text,
                      re.MULTILINE | re.DOTALL)
    if found is None:
        return None
    body = found.group(0)
    scalars = set()
    for first, last in re.findall(r"scalar >= (0x[0-9a-f]+) and"
                                  r" scalar <= (0x[0-9a-f]+)", body):
        scalars.update(range(int(first, 16), int(last, 16) + 1))
    for single in re.findall(r"scalar == (0x[0-9a-f]+)", body):
        scalars.add(int(single, 16))
    return scalars


def white_space_problems(database, text=None):
    """What core/text's White_Space list says that the database does not."""
    if text is None:
        text = WHITE_SPACE_SOURCE.read_text()
    written = white_space_written(text)
    if written is None:
        return "%s has no white_space routine" % WHITE_SPACE_SOURCE.relative_to(
            ROOT)
    held = {scalar for scalar in range(LIMIT)
            if database.flags[scalar] & (1 << WHITE_SPACE_BIT)}
    if written == held:
        return ""
    return ("core/text's white_space names %s and leaves out %s, which is"
            " not the database's White_Space"
            % (sorted("%04X" % s for s in written - held),
               sorted("%04X" % s for s in held - written)))


def leftovers(written):
    """Generated fixture programs the generator no longer writes."""
    found = []
    for path in sorted(FIXTURES.glob("unicode-*/main.ldn")):
        if path in written:
            continue
        if path.read_text().startswith("--  Generated by"
                                       " scripts/unicode_tables.py"):
            found.append(path)
    return found


def write_or_check(written, check):
    """Write each file, or with CHECK say which differ; 1 when any is stale."""
    left = leftovers(written)
    for path in left:
        print("unicode_tables.py: %s is a fixture the generator no longer"
              " writes; remove its directory and its corpus row"
              % path.relative_to(ROOT), file=sys.stderr)
    stale = []
    for path, text in sorted(written.items()):
        if check:
            if not path.exists() or path.read_text() != text:
                stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    for path in stale:
        print("unicode_tables.py: %s is not what the pinned release gives;"
              " run scripts/unicode_tables.py --zip UCD.zip"
              % path.relative_to(ROOT), file=sys.stderr)
    return 1 if stale or left else 0


ARRAY = re.compile(r"^(\w+): \[(\d+)\](\w+) = \[$")


def check_form(text=None):
    """Hold tables.ldn to the pin and to being its own rendering."""
    if text is None:
        if not OUTPUT.exists():
            print("unicode_tables.py: %s is missing"
                  % OUTPUT.relative_to(ROOT), file=sys.stderr)
            return 1
        text = OUTPUT.read_text()
    problems = form_problems(text)
    for problem in problems:
        print("unicode_tables.py: %s" % problem, file=sys.stderr)
    return 1 if problems else 0


def form_problems(text):
    problems = []
    header = HEADER.format(version=VERSION, url=URL, sha256=SHA256)
    if not text.startswith(header):
        problems.append("tables.ldn's header does not name the pinned"
                        " release %s" % VERSION)
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        found = ARRAY.match(lines[index])
        if not found:
            index += 1
            continue
        name, count, element = found.groups()
        end = index + 1
        while not lines[end].endswith("]"):
            end += 1
        body = " ".join(line.strip() for line in lines[index + 1:end + 1])
        values = [value.strip() for value in body[:-1].split(",")]
        if len(values) != int(count):
            problems.append("%s holds %d values, not %s"
                            % (name, len(values), count))
        again = ["%s: [%s]%s = [" % (name, count, element)] + rows(values)
        if again != lines[index:end + 1]:
            problems.append("%s is not laid out as the generator writes it"
                            % name)
        index = end + 1
    return problems


if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    sys.exit(main())
