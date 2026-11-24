#!/usr/bin/env python3
"""Controls for the Windows lane's Microsoft pass (D2327): the recording
driver refine is given on Linux, and the replay of what it kept."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('windows_lane', ROOT / 'compiler/tests/windows/check.py')
LANE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LANE)


class Recorder(unittest.TestCase):
    def test_keeps_the_assembly_and_the_command_with_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            driver = LANE.recorder(tmp)
            self.assertEqual(driver.name, 'x86_64-pc-windows-msvc-clang')
            stage = tmp / 'stage'
            stage.mkdir()
            (stage / 'main.exe.s').write_text('ret\n')
            prefix = tmp / 'case-none-off-default'
            done = subprocess.run(
                [str(driver), '--target=x86_64-pc-windows-msvc', '-nostdlib',
                 '-Wl,/ENTRY:_landin_start', 'main.exe.s', '-lkernel32', '-o', 'main.exe'],
                cwd=stage, env=dict(os.environ, LANDIN_DEFERRED_LINK=str(prefix)),
                capture_output=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(json.loads(Path(str(prefix) + '.link.json').read_text()),
                             ['--target=x86_64-pc-windows-msvc', '-nostdlib',
                              '-Wl,/ENTRY:_landin_start', '{assembly}', '-lkernel32',
                              '-o', '{output}'])
            self.assertEqual(Path(str(prefix) + '.s').read_text(), 'ret\n')
            #  refine moves the output into place, so the recorder leaves one.
            self.assertTrue((stage / 'main.exe').is_file())

    def test_refuses_an_operand_it_cannot_carry(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            driver = LANE.recorder(tmp)
            done = subprocess.run(
                [str(driver), 'extra.obj', '-o', 'main.exe'], cwd=tmp,
                env=dict(os.environ, LANDIN_DEFERRED_LINK=str(tmp / 'case')),
                capture_output=True)
            self.assertNotEqual(done.returncode, 0)
            self.assertIn(b'extra.obj', done.stderr)


class Replay(unittest.TestCase):
    def prepared(self, tmp):
        (tmp / 'case.s').write_text('ret\n')
        return {'label': 'case', 'assembly_sha256': LANE.sha(tmp / 'case.s'),
                'link': ['--target=x86_64-pc-windows-msvc', '{assembly}', '-o', '{output}']}

    def run_link(self, tmp, result, log, expect):
        def fake(argv, cwd, capture_output, timeout):
            self.assertEqual(argv, ['clang', '-v', '--target=x86_64-pc-windows-msvc',
                                    str(tmp / 'case.s'), '-o', str(tmp / 'case.exe')])
            (tmp / 'case.exe').write_bytes(b'MZ')
            return subprocess.CompletedProcess(argv, 0, log, b'')
        with patch.object(LANE.subprocess, 'run', fake):
            LANE.linked(tmp, result, ['clang'], expect)

    def test_names_the_linker_that_ran_and_requires_the_expected_one(self):
        log = (b'clang version 20.1.8\n'
               b' "C:\\\\Program Files\\\\LLVM\\\\bin\\\\clang.exe" -cc1as -o case.o case.s\n'
               b' "C:\\\\Program Files\\\\Microsoft Visual Studio\\\\2022\\\\VC\\\\bin\\\\Hostx64'
               b'\\\\x64\\\\link.exe" -out:case.exe case.o\n')
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            result = self.prepared(tmp)
            self.run_link(tmp, result, log, 'link.exe')
            self.assertTrue(result['linker'].endswith('link.exe'))
            self.assertEqual(result['executable_sha256'], LANE.sha(tmp / 'case.exe'))
            with self.assertRaisesRegex(LANE.Refused, 'not lld-link.exe'):
                self.run_link(tmp, self.prepared(tmp), log, 'lld-link.exe')

    def test_refuses_a_changed_assembly(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            result = self.prepared(tmp)
            (tmp / 'case.s').write_text('nop\n')
            with self.assertRaisesRegex(LANE.Refused, 'assembly checksum'):
                LANE.linked(tmp, result, ['clang'], '')


if __name__ == '__main__':
    unittest.main()
