"""scripts/records.py: a routine's code digest, and fresh or stale records.

The digest is held here on assembly written for the purpose, and `check`
on a stand-in refine that writes it, so the scripts job, which has no
compiler, holds the script's logic and every record's form.
test_records_native.py holds the same property on refine's own output.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

import records  # noqa: E402

#  A routine `f` calling `g` and naming a constant and a trap message;
#  `h` is code `f` does not reach.  {n} numbers its local labels and
#  sections, {line} the trap's line, {k} the constant: what refine's
#  order of emission and the source's layout change.
PROGRAM = textwrap.dedent('''\
    \t.text
    \t.section .text.landin_routine_{n},"ax",@progbits
    \t.type f, @function
    f:
    .L{n}_1:
    \tmovsd .Llandin_f64_{k}(%rip), %xmm0
    \tcall g
    \tjb .L{n}_V3_trap_overflow
    \tret
    .L{n}_V3_trap_overflow:
    \tleaq .Llandin_trap_line_{n}(%rip), %rdi
    \tmovl ${length}, %esi
    \tcall .Llandin_trap_report
    \tud2
    \t.size f, .-f
    \t.section .text.landin_routine_{m},"ax",@progbits
    \t.type g, @function
    g:
    \taddl $1, %eax
    \tret
    \t.size g, .-g
    \t.section .text.landin_routine_{h},"ax",@progbits
    \t.type h, @function
    h:
    \tmovl ${hvalue}, %eax
    \tret
    \t.size h, .-h
    \t.section .text.landin_routine_{r},"ax",@progbits
    .Llandin_trap_report:
    \tsyscall
    \t.section .rodata.cst8.landin_f64_{k},"aM",@progbits,8
    .Llandin_f64_{k}:
    \t.quad {k}
    \t.section .rodata.str1.1.landin_trap_{n},"aMS",@progbits,1
    .Llandin_trap_line_{n}:
    \t.asciz "core/math/x.ldn:{line}:9: trap: overflow\\012"
    ''')


def program(n=7, line=42, k=4607182418800017408, hvalue=5):
    message = 'core/math/x.ldn:%d:9: trap: overflow\n' % line
    return PROGRAM.format(n=n, m=n + 1, h=n + 2, r=n + 3, k=k, line=line,
                          length=len(message), hvalue=hvalue)


def digest(text, symbol='f'):
    return records.digest(text, symbol)[0]


class Digest(unittest.TestCase):
    def test_reaches_what_the_routine_names_and_no_more(self):
        body, count = records.closure(program(), 'f')
        self.assertEqual(count, 5)
        self.assertIn('g:', body)
        self.assertIn('.quad 4607182418800017408', body)
        self.assertNotIn('h:', body)

    def test_a_change_elsewhere_leaves_it(self):
        base = digest(program())
        self.assertEqual(digest(program(n=93)), base, 'emission order')
        self.assertEqual(digest(program(line=1042)), base, "the trap's position")
        self.assertEqual(digest(program(hvalue=6)), base, 'a routine it does not reach')
        self.assertNotEqual(digest(program(hvalue=6), 'h'), digest(program(), 'h'))

    def test_a_change_to_its_code_or_a_callee_changes_it(self):
        base = digest(program())
        self.assertNotEqual(digest(program(k=4611686018427387904)), base)
        self.assertNotEqual(digest(program().replace('addl $1', 'addl $2')), base)
        self.assertNotEqual(digest(program().replace('trap: overflow', 'trap: out_of_range')),
                            base)

    def test_pushed_sections_return_to_the_one_they_interrupted(self):
        text = textwrap.dedent('''\
            \t.section .text.landin_routine_1,"ax",@progbits
            f:
            \tldr x0, =.Lpool
            \t.pushsection .bss.landin_datum_9,"aw",@nobits
            .Lpool:
            \t.zero 8
            \t.popsection
            \tbl g
            \t.section .text.landin_routine_2,"ax",@progbits
            g:
            \tret
            ''')
        body, count = records.closure(text, 'f')
        self.assertEqual(count, 3)
        self.assertIn('g:', body)
        self.assertNotEqual(digest(text), digest(text.replace('\tret', '\tnop\n\tret')))

    def test_an_unknown_routine_is_refused(self):
        with self.assertRaises(KeyError):
            records.closure(program(), 'nowhere')


#  A refine that writes $RECORDS_ASM/TARGET.s as the assembly of any
#  program, and refuses a target with no file.
STAND_IN = '''#!/usr/bin/env python3
import os, shutil, sys
args = sys.argv[1:]
target = args[args.index('--target') + 1]
out = args[args.index('-o') + 1]
source = os.path.join(os.environ['RECORDS_ASM'], target + '.s')
if not os.path.exists(source):
    sys.stderr.write('error: unknown target ' + target + '\\n')
    sys.exit(1)
shutil.copy(source, out)
'''

TARGETS = ['linux-x86-64', 'linux-arm64']


class Check(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='records ')
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.asm = self.dir / 'asm'
        self.asm.mkdir()
        self.refine = self.dir / 'refine'
        self.refine.write_text(STAND_IN)
        self.refine.chmod(0o755)
        for target in TARGETS:
            self.write(target, program())
        self.record = self.dir / 'record.json'
        self.record.write_text(json.dumps({
            'schema': 1, 'title': 'a test', 'check': 'every input',
            'commands': ['true'], 'host': 'here', 'date': '2026-11-27',
            'commit': '0' * 40, 'program': 'compiler/tests/math/evaluate.ldn',
            'options': ['--optimize', 'speed'], 'targets': TARGETS,
            'routines': {'f': {'digests': {t: '0' * 64 for t in TARGETS}},
                         'g': {'digests': {t: '0' * 64 for t in TARGETS}}}}))

    def write(self, target, text):
        (self.asm / (target + '.s')).write_text(text)

    def run_records(self, *args):
        environment = dict(os.environ, RECORDS_ASM=str(self.asm))
        environment.pop('GITHUB_STEP_SUMMARY', None)
        return subprocess.run([sys.executable, str(ROOT / 'scripts/records.py'),
                               '--refine', str(self.refine), *args],
                              capture_output=True, text=True, env=environment,
                              timeout=120, cwd=ROOT)

    def stamp(self):
        stamped = self.run_records('stamp', str(self.record))
        self.assertEqual(stamped.returncode, 0, stamped.stderr)

    def test_fresh_after_stamping_and_after_a_change_elsewhere(self):
        self.stamp()
        record = json.loads(self.record.read_text())
        self.assertRegex(record['commit'], '^[0-9a-f]{40}$')
        self.assertEqual(records.validate(record), [])
        self.write('linux-arm64', program(n=300, line=7, hvalue=11))
        checked = self.run_records('check', str(self.record), '--fail-stale')
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertIn('fresh', checked.stdout)

    def test_stale_after_a_change_to_the_code_it_checked(self):
        self.stamp()
        self.write('linux-arm64', program().replace('addl $1', 'addl $2'))
        checked = self.run_records('check', str(self.record), '--github')
        self.assertEqual(checked.returncode, 0, 'a stale record fails no push')
        self.assertIn('stale', checked.stdout)
        self.assertIn('f on linux-arm64', checked.stdout)
        self.assertIn('g on linux-arm64', checked.stdout)
        self.assertNotIn('linux-x86-64', checked.stdout.split('changed since')[1])
        self.assertIn('::warning file=', checked.stdout)
        failed = self.run_records('check', str(self.record), '--fail-stale')
        self.assertEqual(failed.returncode, 1)

    def test_a_routine_no_longer_emitted_is_stale(self):
        self.stamp()
        self.write('linux-x86-64', program().replace('g:', 'renamed:'))
        checked = self.run_records('check', str(self.record))
        self.assertIn('g on linux-x86-64, no longer emitted', checked.stdout)

    def test_a_refusal_is_no_verdict(self):
        (self.asm / 'linux-arm64.s').unlink()
        checked = self.run_records('check', str(self.record))
        self.assertEqual(checked.returncode, 2)
        self.assertIn('refused', checked.stderr)

    def test_a_malformed_record_is_refused(self):
        record = json.loads(self.record.read_text())
        del record['routines']['f']['digests']['linux-arm64']
        record['date'] = 'yesterday'
        self.record.write_text(json.dumps(record))
        checked = self.run_records('check', str(self.record))
        self.assertEqual(checked.returncode, 2)
        self.assertIn('date is not YYYY-MM-DD', checked.stderr)
        self.assertIn('f has digests for linux-x86-64, not the targets', checked.stderr)


class Records(unittest.TestCase):
    def test_every_record_is_well_formed(self):
        found = records.all_records()
        self.assertTrue(found, 'compiler/tests/records holds no record')
        for path in found:
            with self.subTest(record=path.name):
                record = json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(records.validate(record), [])


if __name__ == '__main__':
    unittest.main()
