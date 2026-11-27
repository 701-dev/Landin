#!/usr/bin/env python3
"""Write core/regex's conformance fixture from Rust's `regex` test suite.

    scripts/regex_tests.py --fetch [DIR]
    scripts/regex_tests.py --crate regex-VERSION.crate
    scripts/regex_tests.py --crate regex-VERSION.crate --check
    scripts/regex_tests.py --check

The cases are the `regex` crate's own, the TOML files under `testdata/`
of the release named by VERSION, URL and SHA256 below, read out of the
crate archive and never typed by hand.  `--fetch` downloads the archive
into DIR, new or empty, or without one into the inputs cache,
$LANDIN_INPUTS or ~/.cache/landin/inputs, as regex-VERSION/regex.crate;
`--crate` names one already downloaded.  Either way its SHA-256 must be
the pinned one before a byte of it is read.

It writes `cases.ldn` of the fixture runtime/regex-rust-suite, whose
`main.ldn` runs every case: it compiles the pattern, walks every match
with its groups, and compares each with the case's.  `--check` compares
the file with what the archive gives instead of writing it; with no
archive named it holds the file to having been written under the pin.

A case is taken when it is one core/regex can state: one pattern, the
default leftmost-first match kind and leftmost search, the whole
haystack, the default line terminator and a haystack that is UTF-8.
The other options are written into the pattern (`(?i)` for
case-insensitive, `(?-u)` for unicode off) or kept as the case's flags
(anchored, compiles, a match limit).  SKIPPED below names the cases
taken out for what core/regex leaves out, each with its reason; every
other case must pass.  The count of each is in the file's header.

Standard library only, so it runs wherever check.py does.
"""

import argparse
import hashlib
import io
import os
import pathlib
import sys
import tarfile
import tomllib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "compiler/tests/fixtures/runtime/regex-rust-suite"
OUTPUT = FIXTURE / "cases.ldn"

VERSION = "1.12.2"
URL = "https://static.crates.io/crates/regex/regex-%s.crate" % VERSION
SHA256 = "843bc0191f75f3e22651ae5f1e72939ab2f72a4bc30fa80a066bd66edefc24d4"

#  The cases taken out by name, `file/name`, for what core/regex leaves
#  out: the reason is the text after each.
SKIPPED = {
    "unicode/class-gencat17": "\\p{Math}, a property core/unicode holds no"
                              " table for",
}
#  The same for every case whose name begins with one of these.
SKIPPED_PREFIXES = {
    "regex-lite/": "regex-lite's own cases, whose ASCII-only meanings the"
                   " regex crate does not share",
    "unicode/class-emoji": "Emoji properties, which core/unicode holds no"
                           " table for",
    "unicode/class-gcb": "Grapheme_Cluster_Break as a class, which"
                         " core/unicode does not offer as one",
    "unicode/class-word-break": "Word_Break as a class, which core/unicode"
                                " does not offer as one",
    "unicode/class-sentence-break": "Sentence_Break as a class, which"
                                    " core/unicode does not offer as one",
}

#  A case's flags in the fixture.
ANCHORED = 1
NO_COMPILE = 2
FIRST_ONLY = 4

NONE = 0xFFFFFFFF


class GeneratorError(Exception):
    """An archive the generator refuses, and why."""


def cached_crate():
    named = os.environ.get("LANDIN_INPUTS")
    root = (pathlib.Path(named) if named
            else pathlib.Path.home() / ".cache/landin/inputs")
    return root / ("regex-%s" % VERSION) / "regex.crate"


def fetch(directory=None):
    directory = (pathlib.Path(directory) if directory
                 else cached_crate().parent)
    if directory.exists() and any(directory.iterdir()):
        raise GeneratorError("%s is not empty" % directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "regex.crate"
    with urllib.request.urlopen(URL) as response:
        target.write_bytes(response.read())
    read_crate(target)
    return target


def read_crate(path):
    """Each testdata TOML file of a verified crate, by its name under it."""
    data = pathlib.Path(path).read_bytes()
    found = hashlib.sha256(data).hexdigest()
    if found != SHA256:
        raise GeneratorError("%s has SHA-256 %s, not the pinned %s"
                             % (path, found, SHA256))
    files = {}
    prefix = "regex-%s/testdata/" % VERSION
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            if (member.isfile() and member.name.startswith(prefix)
                    and member.name.endswith(".toml")):
                name = member.name[len(prefix):]
                files[name] = archive.extractfile(member).read()
    if not files:
        raise GeneratorError("%s holds no testdata" % path)
    return files


def unescaped(text):
    """The bytes of a haystack the suite writes with escapes, as its
    `unescape` option reads them: \\xNN, \\n, \\t, \\r and \\\\."""
    out = bytearray()
    encoded = text.encode("utf-8")
    index = 0
    while index < len(encoded):
        byte = encoded[index]
        if byte == 0x5C and index + 1 < len(encoded):
            following = chr(encoded[index + 1])
            if following == "x":
                out.append(int(encoded[index + 2:index + 4], 16))
                index += 4
                continue
            simple = {"n": 10, "t": 9, "r": 13, "\\": 92, "0": 0}
            if following in simple:
                out.append(simple[following])
                index += 2
                continue
        out.append(byte)
        index += 1
    return bytes(out)


def exclusion(test):
    """Why a case is not one core/regex can state, or None."""
    if isinstance(test["regex"], list):
        return "a set of patterns"
    if test.get("match-kind", "leftmost-first") != "leftmost-first":
        return "a match kind other than leftmost-first"
    if test.get("search-kind", "leftmost") != "leftmost":
        return "a search kind other than leftmost"
    if "bounds" in test:
        return "bounds"
    if "line-terminator" in test:
        return "a line terminator"
    if test.get("utf8", True) is False:
        return "matches that may split a scalar"
    return None


def spans_of(match):
    """A match's groups as (begin, end) pairs, None for one that took no
    part."""
    if isinstance(match, dict):
        match = match["span"]
    if match and isinstance(match[0], int):
        return [(match[0], match[1])]
    groups = []
    for group in match:
        if isinstance(group, dict):
            group = group["span"]
        groups.append(None if group is None or group == [] else
                      (group[0], group[1]))
    return groups


def collect(files):
    taken, left = [], {}
    for name in sorted(files):
        document = tomllib.loads(files[name].decode("utf-8"))
        stem = name[:-len(".toml")]
        for test in document.get("test", []):
            label = "%s/%s" % (stem, test["name"])
            reason = exclusion(test) or SKIPPED.get(label)
            for prefix, why in SKIPPED_PREFIXES.items():
                if reason is None and label.startswith(prefix):
                    reason = why
            if reason is None:
                haystack = test["haystack"]
                data = (unescaped(haystack) if test.get("unescape")
                        else haystack.encode("utf-8"))
                try:
                    data.decode("utf-8")
                except UnicodeDecodeError:
                    reason = "a haystack that is not UTF-8"
            if reason is not None:
                left[reason] = left.get(reason, 0) + 1
                continue
            pattern = test["regex"]
            prefix = ""
            if test.get("case-insensitive"):
                prefix += "(?i)"
            if test.get("unicode", True) is False:
                prefix += "(?-u)"
            flags = 0
            if test.get("anchored"):
                flags |= ANCHORED
            if test.get("compiles", True) is False:
                flags |= NO_COMPILE
            if test.get("match-limit") == 1:
                flags |= FIRST_ONLY
            matches = [spans_of(match) for match in test.get("matches", [])]
            taken.append((label, (prefix + pattern).encode("utf-8"), data,
                          flags, matches))
    return taken, left


def rows(values, indent="    ", limit=79):
    lines, line = [], indent
    for value in values:
        piece = "%s, " % value
        if len(line) + len(piece) - 1 > limit:
            lines.append(line.rstrip())
            line = indent
        line += piece
    lines.append(line.rstrip().rstrip(","))
    return lines


def array(name, element, values):
    return ["%s: [%d]%s = [" % (name, len(values), element)] \
        + rows(values) + ["]"]


HEADER = """\
--  Generated by scripts/regex_tests.py from the regex crate {version}'s
--  testdata, {url}
--  SHA-256 {sha256}; do not edit it.
--  It holds the {count} cases core/regex can state; {left} others are
--  left out, as the script's docstring says why.  The crate's suite is
--  MIT-licensed: LICENSE-MIT.regex beside this file is its notice.
--
--  Each case is eight words of `case_table`: its pattern's and its
--  haystack's first and last byte in `case_texts`, its flags (1
--  anchored, 2 must not compile, 4 only the first match counts), its
--  first match in `case_spans`, how many matches, and how many groups
--  each has.  A match's groups are begin and end pairs, 0xffffffff for a
--  group that took no part.  `case_names` holds each case's file and
--  name, from the offsets in `case_name_ends`.
"""


def render(taken, left):
    texts, table, spans, names, name_ends = bytearray(), [], [], bytearray(), []
    for label, pattern, haystack, flags, matches in taken:
        pattern_at = len(texts)
        texts += pattern
        haystack_at = len(texts)
        texts += haystack
        groups = max((len(match) for match in matches), default=1)
        first = len(spans) // 2
        for match in matches:
            for index in range(groups):
                group = match[index] if index < len(match) else None
                spans.extend(group if group else (NONE, NONE))
        table += [pattern_at, haystack_at, haystack_at, len(texts), flags,
                  first, len(matches), groups]
        names += label.encode("utf-8")
        name_ends.append(len(names))
    lines = HEADER.format(version=VERSION, url=URL, sha256=SHA256,
                          count=len(taken),
                          left=sum(left.values())).rstrip("\n").split("\n")
    lines += ["", "case_count: usize = %d" % len(taken), ""]
    lines += array("case_table", "u32", table) + [""]
    lines += array("case_spans", "u32",
                   ["0xffffffff" if value == NONE else value
                    for value in spans]) + [""]
    lines += array("case_texts", "u8", list(texts)) + [""]
    lines += array("case_names", "u8", list(names)) + [""]
    lines += array("case_name_ends", "u32", name_ends)
    return "\n".join(lines) + "\n"


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--fetch", metavar="DIR", nargs="?", const="")
    source.add_argument("--crate", metavar="PATH")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--list", action="store_true",
                        help="print each case taken and its index")
    options = parser.parse_args(arguments)
    try:
        path = options.crate
        if options.fetch is not None:
            path = fetch(options.fetch or None)
        if path is None:
            if not options.check:
                parser.error("name the release with --crate or --fetch")
            header = HEADER.split("{count}")[0].format(
                version=VERSION, url=URL, sha256=SHA256)
            if not OUTPUT.exists() or not OUTPUT.read_text().startswith(
                    header):
                print("regex_tests.py: %s does not name the pinned crate %s"
                      % (OUTPUT.relative_to(ROOT), VERSION), file=sys.stderr)
                return 1
            return 0
        taken, left = collect(read_crate(path))
        if options.list:
            for index, case in enumerate(taken):
                print(index, case[0], case[1].decode("utf-8", "replace"))
            for reason, count in sorted(left.items()):
                print("left out: %d %s" % (count, reason))
            return 0
        text = render(taken, left)
        if options.check:
            if not OUTPUT.exists() or OUTPUT.read_text() != text:
                print("regex_tests.py: %s is not what the pinned crate"
                      " gives; run scripts/regex_tests.py --crate"
                      " regex.crate" % OUTPUT.relative_to(ROOT),
                      file=sys.stderr)
                return 1
            return 0
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(text)
        return 0
    except GeneratorError as problem:
        print("regex_tests.py: %s" % problem, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
