#!/usr/bin/env python3
"""Hold every workflow to actionlint and shellcheck, at the versions
environments/pins.sh pins.

    python3 scripts/actionlint.py

Both come from the flake: `nix develop` puts them on PATH, and the gate's
scripts job takes the same packages from the nix-packages cache through
.github/actions/nix-tools (`actionlint shellcheck`).  Outside either,
`nix build .#actionlint .#shellcheck` gives them.  A program of any other
version is refused rather than run: a linter whose version nobody pinned
is a verdict nobody can repeat.

It reads `.github/actionlint.yaml`, which names the runner labels GitHub
does not host, and lints every workflow under `.github/workflows`.
actionlint's shellcheck pass runs the pinned shellcheck, named by its path,
over every `run:` script, so a finding there fails the run as actionlint's
own do.  The pyflakes pass is turned off: no step runs Python as its shell,
so it has nothing to read.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PINS = ROOT / "environments/pins.sh"
CONFIG = ROOT / ".github/actionlint.yaml"
WORKFLOWS = ROOT / ".github/workflows"

#  The two programs, by the pins' name for each.
TOOLS = {"actionlint": "ACTIONLINT", "shellcheck": "SHELLCHECK"}

#  How to get them, said by every refusal.
GET_THEM = ("`nix develop` provides the pinned ones, as does `nix build "
            ".#actionlint .#shellcheck`; the gate's scripts job takes them "
            "through .github/actions/nix-tools")


class Refusal(Exception):
    """A run that cannot give a verdict; its text says what to do."""


def pins(path=PINS):
    """environments/pins.sh's NAME=value assignments."""
    return dict(re.findall(r"^(LANDIN_\w+)=(\S+)$",
                           path.read_text(encoding="utf-8"), re.M))


def located(values):
    """The actionlint and shellcheck on PATH, {tool: path}; refused when
    one is missing.  Their versions are lint's to judge."""
    found = {tool: shutil.which(tool) for tool in TOOLS}
    missing = [tool for tool in TOOLS if found[tool] is None]
    if missing:
        raise Refusal(
            "actionlint: no %s on PATH: it needs %s.  %s." % (
                " or ".join(missing),
                " and ".join("%s %s" % (tool, values["LANDIN_%s_VERSION"
                                                    % TOOLS[tool]])
                             for tool in TOOLS), GET_THEM))
    return {tool: Path(path) for tool, path in found.items()}


def version_of(binary, tool="actionlint"):
    """The version TOOL's BINARY says it is: actionlint's first line of
    `-version`, shellcheck's `version:` line of `--version`."""
    flag = "-version" if tool == "actionlint" else "--version"
    completed = subprocess.run([str(binary), flag], capture_output=True,
                               text=True, timeout=60)
    if completed.returncode != 0:
        return None
    lines = completed.stdout.splitlines()
    if tool == "actionlint":
        return lines[0].strip() if lines else None
    for line in lines:
        if line.startswith("version:"):
            return line[len("version:"):].strip()
    return None


def workflows(directory=WORKFLOWS):
    return sorted(path for path in directory.iterdir()
                  if path.suffix in (".yml", ".yaml") and path.is_file())


def lint(binaries, values, root=ROOT):
    """actionlint's exit status over every workflow, with the pinned
    shellcheck's pass over each `run:` script; its report is printed."""
    for tool, binary in sorted(binaries.items()):
        version = values["LANDIN_%s_VERSION" % TOOLS[tool]]
        found = version_of(binary, tool)
        if found != version:
            raise Refusal(
                "actionlint: %s is %s version %s and environments/pins.sh "
                "pins %s; %s" % (binary, tool, found, version, GET_THEM))
    files = workflows(root / ".github/workflows")
    command = [str(binaries["actionlint"]),
               "-config-file", str(root / ".github/actionlint.yaml"),
               "-shellcheck=" + str(binaries["shellcheck"]), "-pyflakes=",
               "-no-color",
               *(str(path.relative_to(root)) for path in files)]
    completed = subprocess.run(command, cwd=root, timeout=300)
    if completed.returncode == 0:
        print("actionlint %s with shellcheck %s: %d workflows clean" % (
            values["LANDIN_ACTIONLINT_VERSION"],
            values["LANDIN_SHELLCHECK_VERSION"], len(files)))
    return completed.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args(argv)
    values = pins()
    try:
        return lint(located(values), values)
    except Refusal as refusal:
        print(refusal, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
