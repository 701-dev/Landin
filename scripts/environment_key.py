#!/usr/bin/env python3
"""Whether the development shell in use is this checkout's flake's.

flake.nix exports LANDIN_ENV_KEY, the first sixteen hex digits of the
SHA-256 of flake.nix, flake.lock and environments/pins.sh, and
scripts/agent_env.sh caches the shell's exports by the same key.  A
session whose environment was sourced before a merge changed one of those
files keeps the old shell's tools, and a check that reads the tools then
fails for a cause the change did not make.  `note()` says so, for
check.py and script_tests.py to print before they run.

    python3 scripts/environment_key.py      # this checkout's key
"""
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ("flake.nix", "flake.lock", "environments/pins.sh")


def key(root=ROOT):
    """This checkout's key, or None where a file is missing."""
    digest = hashlib.sha256()
    for name in FILES:
        path = Path(root) / name
        if not path.exists():
            return None
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def note(root=ROOT, environ=None):
    """A line saying the shell is another flake's, or None."""
    environ = os.environ if environ is None else environ
    theirs = environ.get("LANDIN_ENV_KEY")
    mine = key(root)
    if not theirs or mine is None or theirs == mine:
        return None
    return ("note: the development shell in use is another flake.nix,"
            " flake.lock or pins.sh's (LANDIN_ENV_KEY=%s, this checkout's is"
            " %s), as after a merge that changed them: a check that reads"
            " the tools may fail for that alone; source `. \"$(./scripts/"
            "agent_env.sh)\"` again, or enter `nix develop`, and rerun"
            % (theirs, mine))


if __name__ == "__main__":
    print(key())
    sys.exit(0)
