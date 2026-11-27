#!/usr/bin/env python3
"""scripts/records.py on refine's own assembly: a routine's digest stays
when the source changes elsewhere and moves when its own code changes.

Runs with LANDIN_REFINE naming the built compiler, as the gate's
compiler-checks job runs it; it compiles a copy of the library, edited,
for Linux x86-64 and arm64 on the real host's refine.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

import records  # noqa: E402

REFINE = os.environ.get('LANDIN_REFINE')
PROGRAM = '''import core/math

public main: () -> (code: i32) =
    x: f32 = 0.5
    y := math.sin(x) + math.tan(x)
    code = if y > 0.0 then 0 else 1 end if
end main
'''
TARGETS = ('linux-x86-64', 'linux-arm64')
#  sin_kernel_f32's last coefficient, which sin_f32 reaches and tan_f32
#  does not.
KERNEL = 's4: f64 = 0x1.6cd878c3b46a7p-19'


@unittest.skipUnless(REFINE, 'set LANDIN_REFINE for records on refine\'s assembly')
class NativeRecords(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='records native ')
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.library = self.dir / 'library'
        for part in ('core', 'hosted', 'platform'):
            shutil.copytree(ROOT / part, self.library / part)
        self.program = self.dir / 'main.ldn'
        self.program.write_text(PROGRAM)
        self.trigonometric = self.library / 'core/math/trigonometric.ldn'

    def digests(self):
        found = {}
        for target in TARGETS:
            text = records.emit(REFINE, self.program, target, ['--optimize', 'speed'],
                                self.dir, self.library)
            for symbol in ('sin_f32', 'tan_f32'):
                found[symbol, target] = records.digest(text, symbol)[0]
        return found

    def edit(self, old, new):
        text = self.trigonometric.read_text()
        self.assertIn(old, text)
        self.trigonometric.write_text(text.replace(old, new, 1))

    def test_fresh_after_a_change_elsewhere_and_stale_after_its_own(self):
        before = self.digests()
        # Elsewhere: tan_f32 changed, a routine added above it, and every
        # line of the file moved down by more than its trap positions' digits.
        self.edit('tan_f32: (x: f32) -> (result: f32) =',
                  'unrelated_f32: (x: f32) -> (result: f32) =\n    result = x + x\n'
                  'end unrelated_f32\n\ntan_f32: (x: f32) -> (result: f32) =')
        self.edit('if ix < 0x39800000 then x else tan_kernel_f32',
                  'if ix < 0x39800001 then x else tan_kernel_f32')
        text = self.trigonometric.read_text()
        first = text.index('\n\n') + 2
        self.trigonometric.write_text(text[:first] + '--  moved\n' * 120 + '\n' + text[first:])
        elsewhere = self.digests()
        for target in TARGETS:
            self.assertEqual(elsewhere['sin_f32', target], before['sin_f32', target], target)
            self.assertNotEqual(elsewhere['tan_f32', target], before['tan_f32', target], target)
        # Its own: a coefficient of the kernel sin_f32 calls.
        self.edit(KERNEL, KERNEL.replace('a7p-19', 'a8p-19'))
        changed = self.digests()
        for target in TARGETS:
            self.assertNotEqual(changed['sin_f32', target], elsewhere['sin_f32', target], target)
            self.assertEqual(changed['tan_f32', target], elsewhere['tan_f32', target], target)

    def test_the_records_check_runs(self):
        checked = subprocess.run([sys.executable, str(ROOT / 'scripts/records.py'),
                                  '--refine', REFINE, 'check'],
                                 capture_output=True, text=True, timeout=1200, cwd=ROOT)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertRegex(checked.stdout, r'(?m)^(fresh|stale)  compiler/tests/records/')


if __name__ == '__main__':
    unittest.main()
