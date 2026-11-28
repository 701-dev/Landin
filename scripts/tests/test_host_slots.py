#!/usr/bin/env python3
"""The host's heavy-job slots across worktrees, and detached runs in scopes.

Each "worktree" here is a directory with its own copy of the scripts, so
its build locks are its own and the slots' directory is the one thing the
two share, as two worktrees of a clone share only the host's.  A worker
takes the build lock in `mode` scope, as `build.sh` and `test.sh` do, says
`ready` and holds it until told to finish.
"""
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
#  Seconds before a command that should have answered is called hung; the
#  scripts job runs this beside fifteen other workers.
HANG = 300


def user_scopes():
    """Whether this host's user systemd starts a scope with a memory cap."""
    if not sys.platform.startswith("linux") or not shutil.which("systemd-run"):
        return False
    try:
        return subprocess.run(
            ["systemd-run", "--user", "--scope", "--quiet", "-p", "MemoryMax=1G",
             "--", "true"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class Slots(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="landin-slots-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.slots = self.base / "slots"
        self.trees = [self.worktree("one"), self.worktree("two")]

    def worktree(self, name):
        scripts = self.base / name / "scripts"
        scripts.mkdir(parents=True)
        for each in ("env.sh", "build_lock.py", "host_slots.py", "run_logged.py"):
            shutil.copy2(ROOT / "scripts" / each, scripts / each)
        worker = scripts / "worker.sh"
        worker.write_text('''#!/bin/sh
. "$(dirname -- "$0")/env.sh"
landin_build_lock mode "$@"
echo ready
read -r Finish
''')
        worker.chmod(0o755)
        return self.base / name

    def environment(self, **extra):
        return {**os.environ, "LANDIN_BUILD_TAG": "test", "LANDIN_BUILD_MODE": "debug",
                "LANDIN_HEAVY_JOBS_DIR": str(self.slots), "LANDIN_HEAVY_JOBS": "1",
                "LANDIN_RUN_SCOPE": "no", **extra}

    def start(self, tree, command=None, **extra):
        process = subprocess.Popen(
            command or [str(tree / "scripts/worker.sh")], cwd=tree,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=self.environment(**extra))

        def finish():
            if process.poll() is None:
                process.kill()
            process.wait()
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
        self.addCleanup(finish)
        return process

    def read_until(self, process, stream, wanted):
        """The text STREAM gives until a line holding WANTED."""
        selector = selectors.DefaultSelector()
        self.addCleanup(selector.close)
        selector.register(stream, selectors.EVENT_READ)
        said = ""
        deadline = time.monotonic() + HANG
        while wanted not in said:
            if not selector.select(timeout=max(0, deadline - time.monotonic())):
                self.fail("no %r within %d s; said %r" % (wanted, HANG, said))
            line = stream.readline()
            if not line:
                self.fail("ended before %r; said %r, stderr %r"
                          % (wanted, said, process.stderr.read()))
            said += line
        return said

    def test_a_second_job_waits_names_the_holder_and_starts_when_freed(self):
        one, two = self.trees
        first = self.start(one)
        self.read_until(first, first.stdout, "ready")
        second = self.start(two)
        waiting = self.read_until(second, second.stderr, "waiting for")
        self.assertIn("1 heavy-job slots", waiting)
        self.assertIn("slot-0: pid %d, in %s: " % (first.pid, one), waiting)
        self.assertIn("worker.sh", waiting)
        #  Still waiting while the first job runs.
        time.sleep(2)
        self.assertIsNone(second.poll())
        first.stdin.write("done\n")
        first.stdin.flush()
        self.assertEqual(first.wait(timeout=HANG), 0)
        self.assertIn("took heavy-job slot-0",
                      self.read_until(second, second.stderr, "took heavy-job"))
        self.read_until(second, second.stdout, "ready")
        second.stdin.write("done\n")
        second.stdin.flush()
        self.assertEqual(second.wait(timeout=HANG), 0)

    def test_a_job_inside_a_logged_run_takes_no_second_slot(self):
        one, two = self.trees
        output = self.base / "run"
        run = self.start(one, [sys.executable, str(one / "scripts/run_logged.py"),
                               "--output", str(output), "--",
                               str(one / "scripts/worker.sh")])
        log = output / "command.log"
        deadline = time.monotonic() + HANG
        while "ready" not in (log.read_text() if log.exists() else ""):
            self.assertLess(time.monotonic(), deadline, "the logged worker never started")
            if run.poll() is not None:
                self.fail("the logged run ended: %s" % run.stderr.read())
            time.sleep(0.1)
        #  The one slot is the run's; a job in the other worktree waits for it.
        other = self.start(two)
        waiting = self.read_until(other, other.stderr, "waiting for")
        self.assertIn("pid %d, in %s: " % (run.pid, one), waiting)
        run.stdin.close()
        run.terminate()
        run.wait(timeout=HANG)
        self.read_until(other, other.stdout, "ready")
        result = json.loads((output / "result.json").read_text())
        self.assertEqual(result["heavy_job_slot"], "slot-0")

    def test_a_light_run_and_a_limit_of_zero_take_no_slot(self):
        one, two = self.trees
        first = self.start(one)
        self.read_until(first, first.stdout, "ready")
        light = subprocess.run(
            [sys.executable, str(two / "scripts/run_logged.py"), "--output",
             str(self.base / "light"), "--light", "--", "true"], cwd=two,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            env=self.environment(), timeout=HANG)
        self.assertEqual(light.returncode, 0, light.stdout)
        self.assertIsNone(json.loads((self.base / "light/result.json").read_text())
                          .get("heavy_job_slot"))
        off = self.start(two, LANDIN_HEAVY_JOBS="0")
        self.read_until(off, off.stdout, "ready")

    def test_the_host_setting_is_the_number_in_the_slots_file(self):
        script = str(ROOT / "scripts/host_slots.py")
        environment = self.environment()
        del environment["LANDIN_HEAVY_JOBS"]
        said = subprocess.run([sys.executable, script, "--set", "3"], env=environment,
                              stdout=subprocess.PIPE, text=True, timeout=HANG)
        self.assertEqual(said.returncode, 0)
        self.assertEqual((self.slots / "slots").read_text(), "3\n")
        listed = subprocess.run([sys.executable, script], env=environment,
                                stdout=subprocess.PIPE, text=True, timeout=HANG)
        self.assertIn("%s: 3 slots" % self.slots, listed.stdout)


@unittest.skipUnless(user_scopes(), "needs a user systemd that starts scopes")
class Scopes(unittest.TestCase):
    """Detached runs in scope units of their own, on a host with user systemd."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="landin-scopes-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.environment = {**os.environ, "LANDIN_HEAVY_JOBS": "0"}
        self.environment.pop("LANDIN_RUN_SCOPE", None)

    def logged(self, *arguments, **extra):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/run_logged.py"), *arguments],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            env={**self.environment, **extra}, timeout=HANG)

    def wait(self, output):
        said = self.logged("--wait", str(output), "--timeout", str(HANG))
        return json.loads((output / "result.json").read_text()), said.stdout

    def test_a_run_over_its_cap_is_killed_and_the_run_beside_it_goes_on(self):
        hog, beside = self.base / "hog", self.base / "beside"
        started = self.logged(
            "--output", str(hog), "--detach", "--limit", "120", "--", sys.executable,
            "-c", "import time\nb = []\nwhile True:\n"
            "    b.append(bytearray(32 << 20))\n    time.sleep(0.02)",
            LANDIN_RUN_MEMORY_MAX="160M")
        self.assertIn("scope: landin-run-hog-", started.stdout)
        self.assertIn("memory cap 160M", started.stdout)
        self.logged("--output", str(beside), "--detach", "--limit", "120", "--",
                    "sh", "-c", "sleep 3; echo beside")
        killed, said = self.wait(hog)
        self.assertNotEqual(killed["exit_status"], 0, said)
        self.assertGreaterEqual(killed["oom_kills"], 1, killed)
        self.assertEqual(killed["memory_max"], 160 << 20)
        self.assertTrue(killed["scope"].startswith("landin-run-hog-"))
        self.assertIn("memory cap", (hog / "command.log").read_text())
        went_on, said = self.wait(beside)
        self.assertEqual(went_on["exit_status"], 0, said)
        self.assertEqual(went_on.get("oom_kills"), 0)

    def test_a_run_outlives_the_service_that_launched_it(self):
        unit = "landin-test-launcher-%d" % os.getpid()
        survivor, unscoped = self.base / "survivor", self.base / "unscoped"
        launcher = self.base / "launch.sh"
        run_logged = ROOT / "scripts/run_logged.py"
        launcher.write_text(
            "#!/bin/sh\nexport PATH='%s'\n"
            "LANDIN_HEAVY_JOBS=0 '%s' '%s' --output '%s' --detach --limit 120"
            " -- sh -c 'sleep 4; echo survived'\n"
            "LANDIN_HEAVY_JOBS=0 LANDIN_RUN_SCOPE=no '%s' '%s' --output '%s'"
            " --detach --limit 120 -- sh -c 'sleep 4; echo survived'\n"
            "touch '%s/launched'\nexec sleep 600\n"
            % (os.environ.get("PATH", ""), sys.executable, run_logged, survivor,
               sys.executable, run_logged, unscoped, self.base))
        launcher.chmod(0o755)
        subprocess.run(["systemd-run", "--user", "--quiet", "--unit=" + unit, "--",
                        str(launcher)], check=True, timeout=HANG)
        self.addCleanup(subprocess.run, ["systemctl", "--user", "stop", unit],
                        stderr=subprocess.DEVNULL, timeout=HANG)
        deadline = time.monotonic() + HANG
        while not (self.base / "launched").exists():
            self.assertLess(time.monotonic(), deadline, "the launcher never ran")
            time.sleep(0.1)
        subprocess.run(["systemctl", "--user", "stop", unit], check=True, timeout=HANG)
        lived, said = self.wait(survivor)
        self.assertEqual(lived["exit_status"], 0, said)
        self.assertIn("survived", (survivor / "command.log").read_text())
        #  As before the change: a run in the service's cgroup ends with it.
        #  Its wrapper either records the command's death or, killed with
        #  it as on a GitHub runner, leaves no result: `--wait` says lost.
        said = self.logged("--wait", str(unscoped), "--timeout", str(HANG))
        if (unscoped / "result.json").exists():
            died = json.loads((unscoped / "result.json").read_text())
            self.assertNotEqual(died["exit_status"], 0, said.stdout)
            self.assertNotIn("scope", died)
        else:
            self.assertTrue(said.stdout.startswith("state=lost"), said.stdout)
        self.assertNotIn("survived", (unscoped / "command.log").read_text())


if __name__ == "__main__":
    unittest.main()
