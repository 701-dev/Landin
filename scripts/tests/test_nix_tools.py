#!/usr/bin/env python3
"""nix_tools.py refuses to build anything but the flake's own wrappers."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import nix_tools  # noqa: E402

PLAN = """this derivation will be built:
  /nix/store/6gh12yx2xmg8ms4fri0fkr9admza4nqr-landin-llvm-19.drv
these 2 derivations will be built:
  /nix/store/a45llqgzdydyb80qjl84bwz6kiiybb1r-qemu-system-11.1.0.drv
  /nix/store/aaxnlgvqfl6xsxasl2bwdgx1qk1brngc-landin-cross-riscv64-linux-gnu.drv
these 2 paths will be fetched (1.0 MiB download, 2.0 MiB unpacked):
  /nix/store/lqndphylsxqwbwm804n473pb4sqb98sh-bubblewrap-0.11.2
  /nix/store/a5fizm6hyiy29y7143qnhl43rkmn1xn1-neovim-0.12.4
"""


class Plan(unittest.TestCase):
    def test_only_the_derivations_to_build_are_listed(self):
        names = [nix_tools.name(path) for path in nix_tools.to_build(PLAN)]
        self.assertEqual(names, ["landin-llvm-19", "qemu-system-11.1.0",
                                 "landin-cross-riscv64-linux-gnu"])

    def test_a_fetch_alone_builds_nothing(self):
        fetch = PLAN.split("these 2 paths", 1)[1]
        self.assertEqual(nix_tools.to_build("these 2 paths" + fetch), [])

    def test_the_action_runs_it_with_the_cache_alone(self):
        action = (ROOT / ".github/actions/nix-tools/action.yml").read_text()
        self.assertIn("substituters = ${{ steps.pins.outputs.cache }}", action)
        self.assertIn("trusted-public-keys = ${{ steps.pins.outputs.key }}", action)
        self.assertIn("python3 scripts/nix_tools.py $PACKAGES", action)
        pins = (ROOT / "environments/pins.sh").read_text()
        self.assertIn("LANDIN_NIX_PACKAGES_CACHE=https://", pins)
        self.assertIn("LANDIN_NIX_PACKAGES_KEY=701-nix-packages-1:", pins)


if __name__ == "__main__":
    unittest.main()
