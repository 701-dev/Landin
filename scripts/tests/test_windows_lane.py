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

    def test_names_each_target_for_its_microsoft_triple(self):
        #  D2387: the name selects Microsoft's link for its own architecture.
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(LANE, 'TARGET', 'windows-arm64'):
            self.assertEqual(LANE.recorder(Path(tmp)).name, 'aarch64-pc-windows-msvc-clang')

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
            self.assertEqual(result['linker'], 'C:\\Program Files\\Microsoft Visual Studio'
                             '\\2022\\VC\\bin\\Hostx64\\x64\\link.exe')
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


class MicrosoftTools(unittest.TestCase):
    """D2969: the toolset and SDK the gate names, selected among what the
    host installs, and the link held to them."""

    def host(self, tmp):
        vs = tmp / 'VS'
        for toolset, machines in (('14.29.30133', ('x64', 'arm64')), ('14.44.35207', ('x64',))):
            for machine in machines:
                link = vs / 'VC/Tools/MSVC' / toolset / 'bin/Hostx64' / machine / 'link.exe'
                link.parent.mkdir(parents=True)
                link.write_bytes(b'')
        for sdk in ('10.0.22621.0', '10.0.26100.0'):
            lib = tmp / 'Kits/Lib' / sdk / 'um/x64/kernel32.lib'
            lib.parent.mkdir(parents=True)
            lib.write_bytes(b'')
        return [{'installationPath': str(vs), 'displayName': 'Visual Studio Enterprise 2026',
                 'installationVersion': '18.12.12405.243'}]

    def test_selects_the_named_toolset_and_sdk(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            tools = LANE.microsoft_tools('14.44.35207', '10.0.26100.0', self.host(tmp),
                                         str(tmp / 'Kits'))
            self.assertEqual(tools['root'], str(tmp / 'VS/VC/Tools/MSVC/14.44.35207'))
            self.assertEqual(tools['visual_studio'], 'Visual Studio Enterprise 2026 18.12.12405.243')
            self.assertEqual(LANE.tools_options(tools)[-2:],
                             ['-Xmicrosoft-windows-sdk-version', '10.0.26100.0'])

    def test_refuses_what_the_host_lacks_and_names_what_it_carries(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            installations = self.host(tmp)
            with self.assertRaisesRegex(
                    LANE.Refused, r'no MSVC toolset 14\.52\.37025 .*carries 14\.29\.30133,'
                    r' 14\.44\.35207; .*LANDIN_MSVC_TOOLSET_VERSION'):
                LANE.microsoft_tools('14.52.37025', '10.0.26100.0', installations,
                                     str(tmp / 'Kits'))
            with self.assertRaisesRegex(LANE.Refused, r'no Windows SDK 10\.0\.28000\.0 .*'
                                        r'carries 10\.0\.22621\.0, 10\.0\.26100\.0; .*'
                                        r'LANDIN_WINDOWS_SDK_VERSION'):
                LANE.microsoft_tools('14.44.35207', '10.0.28000.0', installations,
                                     str(tmp / 'Kits'))
            #  A toolset with no linker for the target's machine is not one.
            with patch.object(LANE, 'TARGET', 'windows-arm64'), \
                    self.assertRaisesRegex(LANE.Refused, 'it carries 14\\.29\\.30133;'):
                LANE.microsoft_tools('14.44.35207', '10.0.26100.0', installations,
                                     str(tmp / 'Kits'))

    def test_holds_the_link_to_the_selected_toolset_and_sdk(self):
        tools = {'toolset': '14.44.35207', 'root': 'C:\\VS\\VC\\Tools\\MSVC\\14.44.35207',
                 'windows_sdk': '10.0.26100.0', 'sdk_root': 'C:\\Kits\\10', 'machine': 'x64'}

        def log(linker, sdk):
            return (b'clang version 23.1.6\n "' + linker.replace('\\', '\\\\').encode()
                    + b'" "-libpath:C:\\\\Kits\\\\10/Lib/' + sdk.encode()
                    + b'/um/x64" -out:case.exe case.o\n')

        def link(tmp, text):
            def fake(argv, cwd, capture_output, timeout):
                (tmp / 'case.exe').write_bytes(b'MZ')
                return subprocess.CompletedProcess(argv, 0, text, b'')
            result = Replay.prepared(None, tmp)
            with patch.object(LANE.subprocess, 'run', fake):
                LANE.linked(tmp, result, ['clang'], 'link.exe', tools)
            return result
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ours = 'C:\\VS\\VC\\Tools\\MSVC\\14.44.35207/bin/Hostx64/x64/link.exe'
            self.assertEqual(link(tmp, log(ours, '10.0.26100.0'))['linker'], ours)
            with self.assertRaisesRegex(LANE.Refused, "not MSVC toolset 14.44.35207's"):
                link(tmp, log('C:\\VS\\VC\\Tools\\MSVC\\14.52.37025\\bin\\Hostx64'
                              '\\x64\\link.exe', '10.0.26100.0'))
            with self.assertRaisesRegex(LANE.Refused, "Windows SDK 10.0.26100.0's"):
                link(tmp, log(ours, '10.0.22621.0'))


if __name__ == '__main__':
    unittest.main()
