#!/usr/bin/env python3
"""Allocate the next register or question identities, and file them.

A new register row takes the next SR number: one past every SR number the
register has had.  A retired or completed row has no file, so the files
alone undercount; the script also reads every file name the register
directory has had in this repository's history, on every local branch, and
the second roadmap's last number, which its retired rows took with them.

    python3 scripts/register_next.py            # the next identity
    python3 scripts/register_next.py 3          # the next three
    python3 scripts/register_next.py --file 2   # and write their files

`--file` writes `roadmap/register/SR-n.md` with the keys every row has and
`opened` set to today; it leaves each `TODO` for the writer, and
`python3 check.py` refuses the file until they are filled in.

    python3 scripts/register_next.py --question --file --asked-by ITEM

does the same for a question for the maintainer, Q-n, under
`roadmap/questions/`: the next number past every question file this
repository has had, and with `--file` a file with the parts `ROADMAP.md`'s
Mechanics ask for, each a `TODO` that `python3 check.py` refuses.  Two branches
that take the same number collide as an add/add conflict on the file when
they meet: that is the detection, and the integrator renumbers the later
one.  The numbers are only proposed; a number becomes taken when its file
is committed.

    python3 scripts/register_next.py --question --file \
        --asked-by "the register sweep of 2026-11-22"

files a question asked by work that is no roadmap item: `--asked-by`
names an item, or says what the work is.

    python3 scripts/register_next.py --decision 2

gives the next decision numbers, D-n of `spec.md`'s register: past every
number `spec.md` holds, in the working tree and at the head of every
branch of the clone, `origin/main` among them, and every running item's
reserved block, the running item's own block first.  A number given
outside a running item's block is claimed in the clone's item state for
fourteen days, so that neither a later `--decision` nor `item.py start`'s
reservation gives it again before a branch's `spec.md` cites it.

    python3 scripts/register_next.py --delete ROW ...

deletes rows the work fixed, or that duplicate another: it removes their
files, puts every citation of them in `ROADMAP.md` in a code span, which
`check.py` asks of a row that has left the register, and regenerates
`roadmap/register.md`.  The commit says why each went.

Items started with `scripts/item.py start` reserve blocks of numbers, kept
in the clone's item state.  Run from a running item's worktree, this gives
out that item's own block first; from anywhere it skips every other running
item's block, so two items of one clone do not propose the same number.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = "roadmap/register"
#  The second roadmap's register ended at this number; its retired rows
#  were not moved into files, so no file name in the history shows it.
SECOND_ROADMAP_LAST = 1281
NUMBER = re.compile(r"SR-(\d+)\.md")
DECISION = re.compile(r"\bD(\d{2,})\b")
ROADMAP = "ROADMAP.md"
#  A row's identity in prose; the one check.py reads as a citation.
ROW = re.compile(
    r"(?<![A-Za-z0-9_.])(R551-\d\d|R730-\d\d|SR-\d{2,})(?![A-Za-z0-9_])")
QUESTION_DIRECTORY = "roadmap/questions"
QUESTION_NUMBER = re.compile(r"Q-(\d+)\.md")
QUESTION_TEMPLATE = """# {identity} — TODO, the question?

Asked by {asker} on {date}.

TODO: what the maintainer needs to decide it, and why it is theirs.

**Options:**

1. TODO
2. TODO

**Recommendation:** TODO

**Default until answered:** TODO, in words, not an option's number alone.

**What waits on the answer:** TODO, or nothing.
"""
TEMPLATE = """---
kind: TODO
family: TODO
status: open
opened: {date}
activation: TODO
effort: TODO
impact: TODO
---

TODO: what stands, in a few lines.

Completion: TODO
"""


def numbers_in(names, number=NUMBER):
    """The numbers of the file names among NAMES that NUMBER matches."""
    return {int(found.group(1)) for name in names
            for found in [number.fullmatch(os.path.basename(name.strip()))]
            if found}


def taken(root, question=False):
    """Every number the register, or the questions, have used, here and in
    the history."""
    directory_name, number = ((QUESTION_DIRECTORY, QUESTION_NUMBER)
                              if question else (DIRECTORY, NUMBER))
    used = {0 if question else SECOND_ROADMAP_LAST}
    directory = Path(root) / directory_name
    if directory.is_dir():
        used |= numbers_in((path.name for path in directory.iterdir()),
                           number)
    try:
        log = subprocess.run(
            ["git", "log", "--all", "--format=", "--name-only",
             "--diff-filter=A", "--", directory_name], cwd=root,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        print("register_next.py: the history cannot be read (%s); counting"
              " the files alone" % error, file=sys.stderr)
    else:
        used |= numbers_in(log.stdout.decode("utf-8").splitlines(), number)
    return used


#  Decision numbers handed out to work that is no running item, kept in
#  the clone's item state until a branch's `spec.md` holds them.
CLAIMS = "decisions-claimed.json"
CLAIM_DAYS = 14


def branch_specs(root):
    """The text of `spec.md` at the head of every local and remote branch
    of ROOT's clone, each different text once."""
    def run(*arguments, data=None):
        return subprocess.run(["git", *arguments], cwd=root, input=data,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, check=True).stdout
    try:
        refs = run("for-each-ref", "--format=%(refname)", "refs/heads",
                   "refs/remotes").decode("utf-8").split()
        if not refs:
            return []
        names = "".join("%s:spec.md\n" % ref for ref in refs).encode()
        listed = run("cat-file", "--batch-check=%(objectname) %(objecttype)",
                     data=names).decode("utf-8").splitlines()
        blobs = sorted({line.split()[0] for line in listed
                        if line.endswith(" blob")})
        if not blobs:
            return []
        out = run("cat-file", "--batch",
                  data="".join(blob + "\n" for blob in blobs).encode())
    except (OSError, subprocess.CalledProcessError):
        return []
    texts, at = [], 0
    while at < len(out):
        header_end = out.index(b"\n", at)
        size = int(out[at:header_end].split()[2])
        texts.append(out[header_end + 1:header_end + 1 + size].decode(
            "utf-8", "replace"))
        at = header_end + 1 + size + 1
    return texts


def claims_path(root):
    """The clone's file of claimed decision numbers, or None outside a
    clone."""
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=True).stdout.decode("utf-8").strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(common) / "landin-items" / CLAIMS if common else None


def claims(root, today=None):
    """The decision numbers claimed in the last CLAIM_DAYS days."""
    path = claims_path(root)
    if path is None or not path.exists():
        return {}
    today = today or datetime.date.today()
    try:
        recorded = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {int(number): claim for number, claim in recorded.items()
            if (today - datetime.date.fromisoformat(claim["date"])).days
            <= CLAIM_DAYS}


def claim(root, numbers, by):
    """Record NUMBERS, handed out to BY, in the clone's claims."""
    path = claims_path(root)
    if path is None:
        return
    kept = claims(root)
    date = datetime.date.today().isoformat()
    kept.update({number: {"by": by, "date": date} for number in numbers})
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({str(n): kept[n] for n in sorted(kept)},
                                    indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def decisions_taken(root):
    """Every decision number taken: in `spec.md`'s working tree, at the
    head of every branch of the clone, `origin/main`'s among them, and
    claimed by work that is no running item."""
    texts = branch_specs(root)
    spec = Path(root) / "spec.md"
    if spec.exists():
        texts.append(spec.read_text(encoding="utf-8"))
    return ({int(n) for text in texts for n in DECISION.findall(text)}
            | set(claims(root)) | {0})


def blocks(root, question=False, kind=None):
    """The reserved blocks: the running item's own, and every other's.

    Each is a list of (low, high).  Outside a Git clone, or with no item
    running, both are empty.
    """
    kind = kind or ("Q" if question else "SR")
    sys.path.insert(0, str(ROOT / "scripts"))
    import item
    try:
        mine = item.item_of_branch(root)
        own, others = [], []
        for state in item.running_states(root):
            low, high = state.get("reserved", {}).get(kind, (None, None))
            if low is not None:
                (own if state["item"] == mine else others).append((low, high))
        return own, others
    except (OSError, ValueError, item.Refused) as error:
        print("register_next.py: the running items' reservations cannot be"
              " read (%s); the numbers given skip none of them" % error,
              file=sys.stderr)
        return [], []


def allocate(root, count, question=False, decision=False):
    """The next COUNT identities, in order: the running item's reserved
    block first, then past every number used or reserved."""
    if decision:
        used = decisions_taken(root)
        own, others = blocks(root, kind="D")
        spelling = "D%d"
    else:
        used = taken(root, question)
        own, others = blocks(root, question)
        spelling = "Q-%d" if question else "SR-%d"
    numbers = [n for low, high in own for n in range(low, high + 1)
               if n not in used][:count]
    start = max(used | {high for _, high in own + others}) + 1
    numbers += range(start, start + count - len(numbers))
    return [spelling % n for n in numbers]


def quote_citations(text, gone):
    """TEXT with every citation of a row in GONE put in a code span; a
    span already there is left as it is.  A span may wrap onto the next
    line of its paragraph, as Markdown's do, and ends at a blank line."""
    out = []
    for piece in re.split(r"(`(?:[^`\n]|\n(?![ \t]*\n))*`)", text):
        if piece.startswith("`") and piece.endswith("`") and len(piece) > 1:
            out.append(piece)
        else:
            out.append(ROW.sub(lambda found: "`%s`" % found.group(1)
                               if found.group(1) in gone
                               else found.group(1), piece))
    return "".join(out)


def delete(root, identities):
    """Remove the rows IDENTITIES, quote their citations in ROADMAP.md and
    regenerate the register's page; the paths changed."""
    root = Path(root)
    missing = [identity for identity in identities
               if not (root / DIRECTORY / (identity + ".md")).exists()]
    if missing:
        raise SystemExit("register_next.py: no row %s under %s"
                         % (", ".join(missing), DIRECTORY))
    gone = set(identities)
    changed = []
    for identity in identities:
        path = root / DIRECTORY / (identity + ".md")
        #  The rows merged into it leave with it.
        text = path.read_text(encoding="utf-8")
        if "Merged:" in text:
            gone.update(ROW.findall(text.split("Merged:", 1)[1]))
        path.unlink()
        changed.append(str(path.relative_to(root)))
    gone -= {path.stem for path in (root / DIRECTORY).glob("*.md")}
    roadmap = root / ROADMAP
    if roadmap.exists():
        text = roadmap.read_text(encoding="utf-8")
        quoted = quote_citations(text, gone)
        if quoted != text:
            roadmap.write_text(quoted, encoding="utf-8")
            changed.append(ROADMAP)
    if (root / "check.py").exists():
        subprocess.run([sys.executable, "check.py", "--register"], cwd=root,
                       check=True, stdout=subprocess.DEVNULL)
        changed.append("roadmap/register.md")
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("count", nargs="?", type=int, default=1,
                        help="how many identities (default 1)")
    parser.add_argument("--file", action="store_true",
                        help="write each row's file with its keys to fill")
    parser.add_argument("--question", action="store_true",
                        help="a question for the maintainer, Q-n, rather"
                        " than a register row")
    parser.add_argument("--asked-by", metavar="ITEM", default="TODO",
                        help="with --question --file, the item asking it,"
                        " or what the work is when it is no item")
    parser.add_argument("--decision", action="store_true",
                        help="decision numbers, D-n of spec.md's register")
    parser.add_argument("--delete", nargs="+", metavar="ROW",
                        help="delete these rows: their files, citations"
                        " quoted, the register's page regenerated")
    parser.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if arguments.delete:
        for path in delete(arguments.root, arguments.delete):
            print(path)
        return 0
    if arguments.decision and (arguments.file or arguments.question):
        parser.error("--decision files nothing and is no question")
    if arguments.count < 1:
        parser.error("count must be at least 1")
    identities = allocate(arguments.root, arguments.count, arguments.question,
                          arguments.decision)
    if arguments.decision:
        #  Numbers past the running item's own block are claimed, so that
        #  no item started before they reach a branch reserves them.
        own, _ = blocks(arguments.root, kind="D")
        outside = [int(identity[1:]) for identity in identities
                   if not any(low <= int(identity[1:]) <= high
                              for low, high in own)]
        if outside:
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=arguments.root, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL).stdout.decode("utf-8").strip()
            claim(arguments.root, outside, branch or "a checkout")
    date = datetime.date.today().isoformat()
    for identity in identities:
        if arguments.file:
            if arguments.question:
                path = (Path(arguments.root) / QUESTION_DIRECTORY
                        / (identity + ".md"))
                path.parent.mkdir(parents=True, exist_ok=True)
                text = QUESTION_TEMPLATE.format(
                    identity=identity, asker=arguments.asked_by, date=date)
            else:
                path = Path(arguments.root) / DIRECTORY / (identity + ".md")
                text = TEMPLATE.format(date=date)
            path.write_text(text, encoding="utf-8")
            print(path.relative_to(arguments.root))
        else:
            print(identity)
    return 0


if __name__ == "__main__":
    sys.exit(main())
