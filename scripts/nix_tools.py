#!/usr/bin/env python3
"""Build flake packages from the binary cache and put them on PATH.

    python3 scripts/nix_tools.py PACKAGE...

PACKAGE is a package of this repository's flake, such as `llvm-19` or
`qemu-system` (flake.nix, ciTools).  .github/actions/nix-tools runs this
after installing Nix with the nix-packages cache as its only substituter.

First it asks Nix what building them would take.  A derivation to build
other than the flake's own wrappers, whose names start with `landin-`, is a
store path the cache lacks: the script names each and stops, rather than
compile a toolchain on the runner or fetch it from somewhere the gate does
not record.  docs/environments.md says how a path reaches the cache.
Then it builds them and appends each one's bin directory to the file
GITHUB_PATH names, or prints the directories when that is unset.
"""

import os
import re
import subprocess
import sys

#  The flake's own derivations: runCommand wrappers that link or exec the
#  cached tools, built in a moment and never substituted.
OWN = "landin-"


def to_build(dry_run_output):
    """The store derivations a `nix build --dry-run` says it would build."""
    paths = []
    listing = False
    for line in dry_run_output.splitlines():
        if re.search(r"will be (built|fetched)", line):
            listing = "will be built" in line
            continue
        if listing and line.startswith("  /nix/store/"):
            paths.append(line.strip())
        elif not line.startswith("  "):
            listing = False
    return paths


def name(derivation):
    """A store derivation's name, without its hash and `.drv`."""
    base = os.path.basename(derivation)
    return base.split("-", 1)[1].removesuffix(".drv")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    installables = [".#" + package for package in argv]
    plan = subprocess.run(["nix", "build", "--dry-run", "--no-link", *installables],
                          capture_output=True, text=True)
    sys.stderr.write(plan.stderr)
    if plan.returncode != 0:
        return plan.returncode
    missing = [name(path) for path in to_build(plan.stderr) if not name(path).startswith(OWN)]
    if missing:
        print("nix_tools: the nix-packages cache lacks what these need, so they"
              " would be built here: " + ", ".join(sorted(missing)), file=sys.stderr)
        print("nix_tools: upload them from 701-dev/nix-packages at the flake's"
              " nixpkgs revision (docs/environments.md, \"Tools from"
              " nix-packages\"), then run the job again", file=sys.stderr)
        return 1
    built = subprocess.run(["nix", "build", "--no-link", "--print-out-paths", *installables],
                           stdout=subprocess.PIPE, text=True)
    if built.returncode != 0:
        return built.returncode
    directories = [path + "/bin" for path in built.stdout.split() if os.path.isdir(path + "/bin")]
    target = os.environ.get("GITHUB_PATH")
    if target:
        with open(target, "a", encoding="utf-8") as out:
            out.writelines(directory + "\n" for directory in directories)
    for directory in directories:
        print(directory)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
