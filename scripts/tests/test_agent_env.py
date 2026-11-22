"""scripts/agent_env.sh prints a path that is safe to source in every
shell, the one that already has the environment among them."""

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/agent_env.sh"
RECIPE = ROOT / "docs/process.md"


def session_start_command():
    """The SessionStart hook's command, as docs/process.md gives it."""
    text = RECIPE.read_text(encoding="utf-8")
    for block in re.findall(r"```json\n(.*?)```", text, re.S):
        if '"SessionStart"' in block:
            hooks = json.loads(block)["hooks"]["SessionStart"]
            return hooks[0]["hooks"][0]["command"]
    raise AssertionError("docs/process.md gives no SessionStart hook")


class AgentEnvTest(unittest.TestCase):
    def path_with(self, directory, tools):
        """A PATH holding the shell's own tools and fakes named TOOLS."""
        for tool in ("bash", "sh", "dirname", "cat", "sha256sum", "cut"):
            os.symlink(shutil.which(tool), directory / tool)
        for tool in tools:
            fake = directory / tool
            fake.write_text("#!/bin/sh\nexit 0\n")
            fake.chmod(0o755)
        return str(directory)

    def test_nothing_to_add_is_still_a_file_to_source(self):
        #  A shell that has python3 and gprbuild, and one with no nix: the
        #  file adds nothing, and sourcing it neither fails nor changes PATH.
        for tools in (("python3", "gprbuild", "nix"), ()):
            with self.subTest(tools=tools), \
                    tempfile.TemporaryDirectory() as scratch:
                path = self.path_with(Path(scratch), tools)
                printed = subprocess.run(
                    [str(SCRIPT)], env={"PATH": path}, capture_output=True,
                    text=True, timeout=60, check=True).stdout
                self.assertEqual(printed, "/dev/null\n")
                for shell in ("sh", "bash"):
                    sourced = subprocess.run(
                        [shell, *(["--noprofile", "--norc"]
                                  if shell == "bash" else []), "-c",
                         '. "$("$0")" && printf %s "$PATH"', str(SCRIPT)],
                        env={"PATH": path}, stdin=subprocess.DEVNULL,
                        capture_output=True, text=True, timeout=60)
                    self.assertEqual(sourced.returncode, 0, sourced.stderr)
                    self.assertEqual(sourced.stdout, path)

    def key(self):
        """This checkout's key, as the helper and flake.nix compute it."""
        import hashlib
        digest = hashlib.sha256()
        for name in ("flake.nix", "flake.lock", "environments/pins.sh"):
            digest.update((ROOT / name).read_bytes())
        return digest.hexdigest()[:16]

    def test_this_checkouts_shell_is_left_as_it_is(self):
        #  The flake's shell exports its key; the helper computes the same.
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        self.assertIn("export LANDIN_ENV_KEY=${environmentKey}", flake)
        with tempfile.TemporaryDirectory() as scratch:
            path = self.path_with(Path(scratch),
                                  ("python3", "gprbuild", "nix"))
            for tag in ("nix-x86_64-linux", ""):
                with self.subTest(tag=tag):
                    completed = subprocess.run(
                        [str(SCRIPT)], env={"PATH": path,
                                            "LANDIN_ENV_KEY": self.key(),
                                            "LANDIN_BUILD_TAG": tag},
                        capture_output=True, text=True, timeout=60,
                        check=True)
                    self.assertEqual(completed.stdout, "/dev/null\n")
                    self.assertEqual(completed.stderr, "")

    def flake_shell(self, scratch, script="", toolchain=False):
        """A PATH with a nix whose shell's script puts a store directory
        on PATH, sets the build tag and key, and then runs SCRIPT, and with
        python3 and gprbuild when TOOLCHAIN; the store directory."""
        tools = scratch / "bin"
        store = scratch / "store/bin"
        tools.mkdir()
        store.mkdir(parents=True)
        path = self.path_with(
            tools, ("python3", "gprbuild") if toolchain else ())
        for tool in ("env", "mkdir", "mktemp", "mv", "rm", "sed", "grep",
                     "sort"):
            os.symlink(shutil.which(tool), tools / tool)
        nix = tools / "nix"
        nix.write_text(
            "#!/bin/sh\n"
            "cat <<'EOF'\n"
            "PATH=${PATH:-}\n"
            "nix_saved_PATH=\"$PATH\"\n"
            f"PATH='{store}'\n"
            "export PATH\n"
            "LANDIN_BUILD_TAG=nix-x86_64-linux\n"
            "export LANDIN_BUILD_TAG\n"
            f"LANDIN_ENV_KEY={self.key()}\n"
            "export LANDIN_ENV_KEY\n"
            "PATH=\"$PATH${nix_saved_PATH:+:$nix_saved_PATH}\"\n"
            + script +
            "EOF\n")
        nix.chmod(0o755)
        return path, store

    def run_helper(self, scratch, path, caller=None, stdin=None):
        completed = subprocess.run(
            [str(SCRIPT)],
            env={"PATH": path, "HOME": str(scratch),
                 "XDG_CACHE_HOME": str(scratch / "cache"), **(caller or {})},
            stdin=subprocess.DEVNULL if stdin is None else stdin,
            capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        printed = Path(completed.stdout.strip())
        self.assertEqual(printed, scratch / f"cache/landin/agent-env/{self.key()}.sh")
        return printed, completed.stderr

    def exported(self, printed):
        return re.findall(r"^export ([A-Za-z_][A-Za-z0-9_]*)=",
                          printed.read_text(), re.M)

    def test_another_checkouts_shell_gets_this_ones(self):
        #  A session started in one checkout has that checkout's shell on
        #  PATH in every worktree: the helper says so, and prints this
        #  checkout's exports, every one of them, the build tag the other
        #  shell set to the same value among them.
        for caller in ({"LANDIN_BUILD_TAG": "nix-x86_64-linux"},
                       {"LANDIN_BUILD_TAG": "nix-x86_64-linux",
                        "LANDIN_ENV_KEY": "0123456789abcdef"}):
            with self.subTest(caller=caller), \
                    tempfile.TemporaryDirectory() as scratch:
                scratch = Path(scratch)
                path, store = self.flake_shell(scratch, toolchain=True)
                printed, said = self.run_helper(scratch, path, caller)
                self.assertIn("the shell of another flake.nix, flake.lock or"
                              " pins.sh", said)
                self.assertIn(self.key(), said)
                sourced = subprocess.run(
                    ["sh", "-c", '. "$0" && printf "%s %s %s" "$PATH"'
                     ' "$LANDIN_BUILD_TAG" "$LANDIN_ENV_KEY"', str(printed)],
                    env={"PATH": path, **caller}, capture_output=True,
                    text=True, timeout=60)
                self.assertEqual(sourced.returncode, 0, sourced.stderr)
                self.assertEqual(sourced.stdout.split(" "), [
                    f"{store}:{path}", "nix-x86_64-linux", self.key()])

    def test_the_callers_startup_files_stay_out(self):
        #  A SessionStart hook's standard input is a socket, and
        #  bash under `env -i` with no SHLVL then reads ~/.bashrc as if
        #  sshd had started it.  On 2026-11-21 that put the maintainer's
        #  whole login environment, a daemon's password among it, into
        #  five cached files, and the hook into every command's argument.
        #  BASH_ENV and a login profile are the other ways in.
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            path, _ = self.flake_shell(scratch)
            for startup in (".bashrc", ".bash_profile", ".profile",
                            "bash_env"):
                (scratch / startup).write_text(
                    "export FROM_STARTUP_%s=1\n"
                    % startup.strip(".").upper())
            ours, theirs = socket.socketpair()
            with ours, theirs:
                printed, said = self.run_helper(
                    scratch, path, {"BASH_ENV": str(scratch / "bash_env")},
                    stdin=ours)
            self.assertEqual(sorted(self.exported(printed)),
                             ["LANDIN_BUILD_TAG", "LANDIN_ENV_KEY", "PATH"])
            self.assertNotIn("FROM_STARTUP", said)

    def test_names_that_look_secret_are_left_out(self):
        #  The shell's own script naming one is refused as firmly as the
        #  caller's would be: the hook would show it to `ps`.  The name is
        #  said, its value never.  A name the script does not mention, here
        #  one a file it sources sets, is not the flake's and is left out.
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            (scratch / "elsewhere.sh").write_text("export ELSEWHERE_SET=1\n")
            secrets = ("DAEMON_PASSWORD", "GITHUB_TOKEN", "my_secret_key",
                       "AWS_CREDENTIALS")
            path, _ = self.flake_shell(scratch, "".join(
                f"{name}=value-{name}; export {name}\n" for name in secrets)
                + "KEPT_NAME=kept; export KEPT_NAME\n"
                + ". \"$HOME/elsewhere.sh\"\n")
            printed, said = self.run_helper(scratch, path)
            self.assertEqual(sorted(self.exported(printed)), [
                "KEPT_NAME", "LANDIN_BUILD_TAG", "LANDIN_ENV_KEY", "PATH"])
            for name in secrets:
                self.assertIn(f"{name} looks secret", said)
                self.assertNotIn(f"value-{name}", said)
                self.assertNotIn(f"value-{name}", printed.read_text())
            self.assertIn("ELSEWHERE_SET is left out", said)

    def test_a_cached_file_that_holds_a_secret_is_written_again(self):
        #  A file an earlier version wrote is replaced, the poisoned ones
        #  aloud, rather than kept while its store paths last.
        for line, aloud in (("export PASEO_PASSWORD=hidden\n", True),
                            ("", False)):
            with self.subTest(aloud=aloud), \
                    tempfile.TemporaryDirectory() as scratch:
                scratch = Path(scratch)
                path, store = self.flake_shell(scratch)
                cached = scratch / f"cache/landin/agent-env/{self.key()}.sh"
                cached.parent.mkdir(parents=True)
                cached.write_text(f"export PATH='{store}':\"$PATH\"\n"
                                  "export STALE_NAME=1\n" + line)
                printed, said = self.run_helper(scratch, path)
                self.assertEqual(sorted(self.exported(printed)),
                                 ["LANDIN_BUILD_TAG", "LANDIN_ENV_KEY", "PATH"])
                self.assertEqual("holds a name that looks secret" in said,
                                 aloud, said)
                self.assertNotIn("hidden", said)
                #  The file now written is the one kept.
                again, said = self.run_helper(scratch, path)
                self.assertEqual(said, "")
                self.assertEqual(again.read_text(), printed.read_text())


class SessionStartHookTest(unittest.TestCase):
    """The hook docs/process.md gives leaves a session one environment.

    Claude Code names the file a SessionStart hook writes after the hook's
    place among those it runs, keeps it across resumes, and puts every such
    file of the session into the one argument each Bash command runs as,
    which Linux limits to 128 KiB.  Appending on each resume, and under a
    second number when the hook's place moved, took a session to 137.8 KB
    on 2026-11-17, and every command failed with E2BIG.
    """

    LIMIT = 64 * 1024

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="landin-hook-")
        self.addCleanup(temporary.cleanup)
        scratch = Path(temporary.name)
        self.exports = scratch / "agent-env.sh"
        helper = scratch / "project/scripts/agent_env.sh"
        helper.parent.mkdir(parents=True)
        helper.write_text("#!/bin/sh\nprintf '%s\\n' '" + str(self.exports) + "'\n")
        helper.chmod(0o755)
        self.project = helper.parents[1]
        self.session = scratch / "session-env/63700778-8ea9-41f2-86a8-07f32a41b1e4"
        self.session.mkdir(parents=True)

    def environment(self, generation, padding=23000):
        """An environment like the flake's: its key, a probe and its bulk."""
        self.exports.write_text(
            "export LANDIN_ENV_KEY=%016x\nexport LANDIN_HOOK_PROBE=%d\n"
            "export PADDING='%s'\n" % (generation, generation, "x" * padding))

    def start(self, place):
        completed = subprocess.run(
            ["sh", "-c", session_start_command()],
            env={"PATH": os.environ["PATH"],
                 "CLAUDE_PROJECT_DIR": str(self.project),
                 "CLAUDE_ENV_FILE": str(self.session / ("sessionstart-hook-%d.sh" % place))},
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed.stderr

    def argument(self):
        """What Claude Code puts ahead of a command: every hook file, trimmed."""
        return "\n".join(
            text for text in (path.read_text().strip()
                              for path in sorted(self.session.glob("*-hook-*.sh")))
            if text)

    def sourced(self):
        completed = subprocess.run(
            ["sh", "-c", self.argument() + '\nprintf %s "$LANDIN_HOOK_PROBE"'],
            env={"PATH": os.environ["PATH"]}, capture_output=True, text=True,
            timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed.stdout

    def test_reopens_and_moved_places_leave_one_environment(self):
        #  The files of the session that failed: the same environment four
        #  times, three of them from a hook that wrote no marker, and two
        #  environments under the next number.
        self.environment(1)
        unmarked = self.exports.read_text()
        (self.session / "sessionstart-hook-0.sh").write_text(
            unmarked * 3 + "# landin agent_env 1 2\n" + unmarked)
        (self.session / "sessionstart-hook-1.sh").write_text(
            "# landin agent_env 1 2\n" + unmarked + "# landin agent_env 3 4\n" + unmarked)
        #  Another tool's hook is not Landin's to empty.
        other = self.session / "sessionstart-hook-5.sh"
        other.write_text("export OTHER_TOOL=1\n")
        for generation, place in enumerate([1, 1, 0, 2, 2, 0, 1, 3, 0, 0, 2, 1], 2):
            if generation % 3:
                self.environment(generation)
            self.assertEqual(self.start(place), "")
            argument = self.argument()
            self.assertEqual(argument.count("export LANDIN_ENV_KEY="), 1, argument[:200])
            self.assertLess(len(argument.encode()), self.LIMIT)
            self.assertEqual(self.sourced(), self.exports.read_text().split(
                "LANDIN_HOOK_PROBE=")[1].split("\n")[0])
            self.assertTrue((self.session / ("sessionstart-hook-%d.sh" % place))
                            .read_text().startswith("# landin agent_env "))
        self.assertEqual(other.read_text(), "export OTHER_TOOL=1\n")

    def test_an_environment_that_would_pass_the_limit_is_refused_aloud(self):
        other = self.session / "sessionstart-hook-0.sh"
        other.write_text("export OTHER_TOOL='%s'\n" % ("y" * 45000))
        self.environment(1, padding=15000)
        self.assertEqual(self.start(1), "")
        self.assertEqual(self.sourced(), "1")
        #  A larger environment would take the session's files past 64 KiB:
        #  none is loaded, the file is left empty, and the hook says why.
        self.environment(2, padding=21000)
        said = self.start(1)
        self.assertIn("start a fresh session", said)
        self.assertIn("is not loaded", said)
        self.assertEqual((self.session / "sessionstart-hook-1.sh").read_text(), "")
        self.assertLess(len(self.argument().encode()), self.LIMIT)
        self.assertEqual(self.sourced(), "")

    def test_a_host_without_the_helper_is_left_alone(self):
        command = session_start_command()
        with tempfile.TemporaryDirectory() as scratch:
            target = Path(scratch) / "claude-env"
            completed = subprocess.run(
                ["sh", "-c", command],
                env={"PATH": os.environ["PATH"], "CLAUDE_PROJECT_DIR": scratch,
                     "CLAUDE_ENV_FILE": str(target)},
                capture_output=True, text=True, timeout=60)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
