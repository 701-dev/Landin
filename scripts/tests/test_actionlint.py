"""scripts/actionlint.py runs the pinned actionlint over every workflow, with
the pinned shellcheck's pass over their `run:` scripts, and refuses, saying
how to get them, an actionlint or a shellcheck that is missing or another
version."""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import actionlint  # noqa: E402

PINNED = actionlint.pins()["LANDIN_ACTIONLINT_VERSION"]
SHELLCHECK = actionlint.pins()["LANDIN_SHELLCHECK_VERSION"]


def fake(directory, version, status=0, shellcheck=SHELLCHECK):
    """An actionlint answering VERSION that records its arguments, beside a
    shellcheck answering SHELLCHECK, or none when it is None."""
    program = Path(directory) / "actionlint"
    program.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = -version ]; then echo %s; echo built; exit 0; fi\n'
        'printf "%%s\\n" "$@" > "$0.arguments"\n'
        "exit %d\n" % (version, status))
    program.chmod(0o755)
    if shellcheck is not None:
        checker = Path(directory) / "shellcheck"
        checker.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = --version ]; then\n'
            "  echo 'ShellCheck - shell script analysis tool'\n"
            "  echo 'version: %s'; exit 0\n"
            "fi\n"
            "exit 1\n" % shellcheck)
        checker.chmod(0o755)
    return program


def run(argv, path):
    out, err = io.StringIO(), io.StringIO()
    with patch.dict(os.environ, {"PATH": path}), redirect_stdout(out), \
            redirect_stderr(err):
        status = actionlint.main(argv)
    return status, out.getvalue(), err.getvalue()


class Located(unittest.TestCase):
    def test_a_missing_actionlint_says_how_to_get_it(self):
        with tempfile.TemporaryDirectory() as empty:
            status, _, said = run([], empty)
        self.assertEqual(status, 2)
        self.assertIn("no actionlint or shellcheck on PATH", said)
        self.assertIn("it needs actionlint " + PINNED
                      + " and shellcheck " + SHELLCHECK, said)
        self.assertIn("`nix develop` provides the pinned ones", said)
        self.assertIn(".github/actions/nix-tools", said)

    def test_a_missing_shellcheck_is_refused_rather_than_skipped(self):
        #  actionlint would pass over every `run:` script without one.
        with tempfile.TemporaryDirectory() as directory:
            program = fake(directory, PINNED, shellcheck=None)
            status, _, said = run([], directory)
            self.assertFalse(Path(str(program) + ".arguments").exists())
        self.assertEqual(status, 2)
        self.assertIn("no shellcheck on PATH", said)

    def test_another_version_is_refused_rather_than_run(self):
        with tempfile.TemporaryDirectory() as directory:
            program = fake(directory, "1.6.0")
            status, _, said = run([], directory + os.pathsep + os.environ["PATH"])
            self.assertFalse(Path(str(program) + ".arguments").exists())
        self.assertEqual(status, 2)
        self.assertIn("is actionlint version 1.6.0 and environments/pins.sh"
                      " pins " + PINNED, said)

    def test_another_shellcheck_is_refused_rather_than_run(self):
        with tempfile.TemporaryDirectory() as directory:
            program = fake(directory, PINNED, shellcheck="0.9.0")
            status, _, said = run([], directory + os.pathsep + os.environ["PATH"])
            self.assertFalse(Path(str(program) + ".arguments").exists())
        self.assertEqual(status, 2)
        self.assertIn("is shellcheck version 0.9.0 and environments/pins.sh"
                      " pins " + SHELLCHECK, said)

    def test_every_workflow_is_linted_with_the_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            program = fake(directory, PINNED)
            status, said, _ = run([], directory + os.pathsep + os.environ["PATH"])
            arguments = Path(str(program) + ".arguments").read_text().splitlines()
        self.assertEqual(status, 0)
        workflows = sorted(path.relative_to(ROOT).as_posix()
                           for path in (ROOT / ".github/workflows").iterdir()
                           if path.suffix in (".yml", ".yaml"))
        self.assertGreaterEqual(len(workflows), 5)
        self.assertEqual(arguments[:2], ["-config-file", str(ROOT / ".github/actionlint.yaml")])
        #  The pinned shellcheck, named by its path, checks every `run:`
        #  script, and no host's pyflakes decides the verdict.
        self.assertIn("-shellcheck=" + str(Path(directory) / "shellcheck"),
                      arguments)
        self.assertIn("-pyflakes=", arguments)
        self.assertEqual(sorted(a for a in arguments if a.startswith(".github/")), workflows)
        self.assertIn("with shellcheck %s: %d workflows clean"
                      % (SHELLCHECK, len(workflows)), said)

    def test_a_finding_fails_the_run(self):
        with tempfile.TemporaryDirectory() as directory:
            fake(directory, PINNED, status=1)
            status, said, _ = run([], directory + os.pathsep + os.environ["PATH"])
        self.assertEqual(status, 1)
        self.assertNotIn("clean", said)

    def test_the_configuration_names_the_rig(self):
        text = (ROOT / ".github/actionlint.yaml").read_text(encoding="utf-8")
        self.assertIn("self-hosted-runner:", text)
        self.assertIn("- landin-rig\n", text)

    def test_no_step_runs_python_as_its_shell(self):
        #  The pyflakes pass stays off because it would have nothing to
        #  read: a step that runs Python as its shell needs it pinned too.
        for path in (ROOT / ".github/workflows").iterdir():
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"(?m)^\s*shell:\s*python", path.name)


if __name__ == "__main__":
    unittest.main()
