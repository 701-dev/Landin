#!/usr/bin/env python3
"""Controls for scripts/environment_key.py, the stale-shell note."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import environment_key  # noqa: E402


class Key(unittest.TestCase):
    def test_the_key_is_agent_env_shs(self):
        #  agent_env.sh computes it in shell; the two must agree.
        printed = subprocess.run(
            ["bash", "-c", "cat flake.nix flake.lock environments/pins.sh"
             " | sha256sum | cut -c1-16"], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, check=True).stdout.strip()
        self.assertEqual(environment_key.key(), printed)

    def test_a_shell_of_another_flake_is_named(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            for name in environment_key.FILES:
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(name + "\n")
            mine = environment_key.key(root)
            self.assertIsNone(environment_key.note(
                root, {"LANDIN_ENV_KEY": mine}))
            self.assertIsNone(environment_key.note(root, {}))
            said = environment_key.note(root, {"LANDIN_ENV_KEY": "0" * 16})
        self.assertIn("another flake.nix", said)
        self.assertIn(mine, said)
        self.assertIn("agent_env.sh", said)


if __name__ == "__main__":
    unittest.main()
