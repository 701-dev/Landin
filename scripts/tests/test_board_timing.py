#!/usr/bin/env python3
"""Offline controls of environments/boards/timing.py: what a timing bundle
calls one image, what it refuses before the rig, how a clock and a run are
read, and how a run is held to its oracle.  No probe, rig or compiler."""
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'environments/boards'))
import build  # noqa: E402
import common  # noqa: E402
import timing  # noqa: E402


def elf(segments, entry=0x20000000, tail=b''):
    """An ELF32 with SEGMENTS, [(address, bytes, memory size)], as PT_LOADs,
    and TAIL after them: bytes no segment loads, as line tables are."""
    at = 52 + 32 * len(segments)
    body, programs = bytearray(), bytearray()
    for address, data, memory in segments:
        programs += struct.pack('<8I', 1, at + len(body), address, address, len(data), memory, 5, 4)
        body += data
    header = bytearray(b'\x7fELF\x01\x01\x01' + bytes(9))
    header += struct.pack('<HHIIIIIHHHHHH', 2, 40, 1, entry, 52, 0, 0, 52, 32,
                          len(segments), 40, 0, 0)
    return bytes(header + programs + body + tail)


# The RAM script refine derives for the STM32H753 (--emit=linker-script
# --firmware-layout=ram), which a timing build rewrites for its TCMs.
DERIVED_H753 = (
    'OUTPUT_FORMAT("elf32-littlearm")\n'
    'OUTPUT_ARCH(arm)\n'
    'ENTRY(_landin_firmware_reset)\n'
    'MEMORY {\n'
    '  FLASH (rx) : ORIGIN = 134217728, LENGTH = 2097152\n'
    '  ITCM (rwx) : ORIGIN = 0, LENGTH = 65536\n'
    '  DTCM (rw) : ORIGIN = 536870912, LENGTH = 131072\n'
    '  AXI_SRAM (rwx) : ORIGIN = 603979776, LENGTH = 524288\n'
    '  SRAM1 (rw) : ORIGIN = 805306368, LENGTH = 131072\n'
    '  SRAM2 (rw) : ORIGIN = 805437440, LENGTH = 131072\n'
    '  SRAM3 (rw) : ORIGIN = 805568512, LENGTH = 32768\n'
    '  SRAM4 (rw) : ORIGIN = 939524096, LENGTH = 65536\n'
    '}\n'
    '_landin_firmware_stack_top = ORIGIN(AXI_SRAM) + LENGTH(AXI_SRAM);\n'
    '_landin_firmware_stack_bottom = _landin_firmware_stack_top - 16384;\n'
    'SECTIONS {\n'
    '  .isr_vector ORIGIN(AXI_SRAM) : { KEEP(*(.isr_vector)) } > AXI_SRAM\n'
    '  .text : { *(.text .text.*) } > AXI_SRAM\n'
    '  .ramtext : ALIGN(8) {\n'
    '    _landin_firmware_ramtext_start = .;\n'
    '    *(.ramtext.*)\n'
    '    _landin_firmware_ramtext_end = .;\n'
    '  } > AXI_SRAM\n'
    '  .rodata : { *(.rodata .rodata.*) } > AXI_SRAM\n'
    '  .ARM.extab : { *(.ARM.extab*) } > AXI_SRAM\n'
    '  .ARM.exidx : { *(.ARM.exidx*) } > AXI_SRAM\n'
    '  .data : ALIGN(8) {\n'
    '    _landin_firmware_data_start = .;\n'
    '    *(.data .data.*)\n'
    '    _landin_firmware_data_end = .;\n'
    '  } > AXI_SRAM\n'
    '  _landin_firmware_data_load = LOADADDR(.data);\n'
    '  _landin_firmware_ramtext_load = LOADADDR(.ramtext);\n'
    '  .bss (NOLOAD) : AT(ADDR(.bss)) ALIGN(8) {\n'
    '    _landin_firmware_bss_start = .;\n'
    '    *(.bss .bss.* COMMON)\n'
    '    _landin_firmware_bss_end = .;\n'
    '  } > AXI_SRAM\n'
    '  /DISCARD/ : { *(.comment .note.GNU-stack) }\n'
    '}\n'
    'ASSERT(ADDR(.isr_vector) == 603979776, "vectors must start at 0x24000000")\n'
    'ASSERT(SIZEOF(.isr_vector) == 664, "vectors must contain 166 words")\n'
    'ASSERT((_landin_firmware_stack_top & 7) == 0, "unaligned initial stack")\n'
    'ASSERT(_landin_firmware_bss_end <= _landin_firmware_stack_bottom,\n'
    '       "AXI_SRAM RAM capacity exceeded: image overlaps the reserved 16 KiB stack; use --firmware-layout=boot for the board boot check")\n'
)


class Images(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_an_image_is_what_the_board_loads_not_the_elf_file(self):
        """Profiles whose ELF files differ only in what is not loaded, their
        line and frame tables, are one image; a different BSS size, entry or
        byte is another."""
        code = [(0x20000000, b'\x01\x02\x03\x04', 4), (0x20000100, b'', 64)]
        one = timing.loaded_digest(self.write('a.elf', elf(code, tail=b'debug one')))
        self.assertEqual(one, timing.loaded_digest(self.write('b.elf', elf(code, tail=b'other'))))
        for changed in (elf([code[0], (0x20000100, b'', 68)]),
                        elf(code, entry=0x20000002),
                        elf([(0x20000000, b'\x01\x02\x03\x05', 4), code[1]])):
            self.assertNotEqual(one, timing.loaded_digest(self.write('c.elf', changed)))

    def test_the_h753_times_text_from_itcm_and_data_and_stack_from_dtcm(self):
        """The timing script moves every executable and read-only section to
        the ITCM past its first eight bytes, data, BSS and the stack to the
        DTCM, and leaves the vectors where the RAM layout's contract fixes
        them; a derived script of another shape fails."""
        script = timing.timing_script(DERIVED_H753, **timing.TIMING_REGIONS['stm32h753'])
        self.assertIn('.isr_vector ORIGIN(AXI_SRAM) : { KEEP(*(.isr_vector)) } > AXI_SRAM', script)
        self.assertIn('.text : { . = . + (ABSOLUTE(.) < 8 ? 8 - ABSOLUTE(.) : 0); *(.text .text.*) } > ITCM',
                      script)
        for section in ('.rodata', '.ARM.extab', '.ARM.exidx'):
            self.assertRegex(script, r'%s : .*> ITCM\n' % section.replace('.', r'\.'))
        self.assertEqual(script.count('> DTCM'), 2)
        self.assertIn('_landin_firmware_stack_top = ORIGIN(DTCM) + LENGTH(DTCM);', script)
        self.assertEqual(script.count('> AXI_SRAM'), 1)
        for broken in (DERIVED_H753.replace('  .rodata :', '  .unknown :'),
                       DERIVED_H753.replace('*(.rodata .rodata.*) } > AXI_SRAM', '*(.rodata .rodata.*) } > SRAM1'),
                       DERIVED_H753.replace('_landin_firmware_stack_top = ORIGIN(AXI_SRAM)', 'x = ORIGIN(AXI_SRAM)'),
                       DERIVED_H753.replace('{ *(.text .text.*) }', '{\n *(.text .text.*)\n }')):
            with self.assertRaises(common.Failed):
                timing.timing_script(broken, 'ITCM', 'DTCM')

    def test_hand_made_images_are_a_bundle_held_to_their_workload_s_oracle(self):
        """`images` names each file's image by the workload and the file,
        keeps the workload's status, and refuses two files that load the
        same bytes."""
        one = self.write('moved-2.elf', elf([(0x00000008, b'\x01\x02\x03\x04', 4)]))
        two = self.write('moved-4.elf', elf([(0x0000000c, b'\x01\x02\x03\x04', 4)]))
        arguments = dict(board='stm32h753', workload='sieve-of-eratosthenes', profile='speed-all')
        with mock.patch.object(common, 'validate_ram_image'), \
                mock.patch.object(timing, 'placement', return_value='text:itcm,data:dtcm,stack:dtcm'), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(timing.images(SimpleNamespace(
                output=self.root / 'bundle', elf=[one, two], **arguments)), 0)
            with self.assertRaises(common.Failed):
                timing.images(SimpleNamespace(output=self.root / 'again', elf=[one, one], **arguments))
        made = timing.read_bundle(self.root / 'bundle')['boards']['stm32h753']['images']
        self.assertEqual([image['workload'] for image in made],
                         ['sieve-of-eratosthenes@moved-2', 'sieve-of-eratosthenes@moved-4'])
        self.assertEqual({image['status'] for image in made}, {
            timing.firmware_workloads(['sieve-of-eratosthenes'])[0]['meta'].status_at('armv7e-m')})
        self.assertEqual(made[0]['profiles'], ['speed-all'])

    def test_instruction_sram_that_is_not_whole_words_is_refused_before_the_rig(self):
        self.assertIsNone(timing.refused('esp32c3', self.write(
            'ok.elf', elf([(0x40380000, bytes(8), 8), (0x3fca0000, bytes(3), 3)]))))
        reason = timing.refused('esp32c3', self.write(
            'odd.elf', elf([(0x40380180, bytes(0x201), 0x201)])))
        self.assertRegex(reason, r'instruction SRAM segment at 0x40380180 holds 513 bytes')
        self.assertIsNone(timing.refused('rp2040', self.write(
            'arm.elf', elf([(0x20000000, bytes(3), 3)]))))

    def test_every_board_is_a_port_with_a_counter_file_a_probe_and_its_ram(self):
        self.assertEqual({b: build.TARGETS[b] for b in timing.BOARDS}, timing.BOARDS)
        self.assertEqual(set(build.TARGETS) - set(timing.BOARDS), {'stm32h753_cached'})
        for board in timing.BOARDS:
            text = (ROOT / timing.COUNTERS / (board + '.ldn')).read_text()
            self.assertIn('import descriptions/%s\n' % board, text)
            self.assertIn('counted: () -> (count: u32) =', text)
            self.assertIn(board, timing.PROBES)
            self.assertEqual({(lo, hi) for lo, hi, _ in timing.REGIONS[board]},
                             set(common.RAM_REGIONS[board]))
        entry = (ROOT / timing.ENTRY).read_text()
        for word in (timing.STATUS, timing.BEFORE, timing.AFTER):
            self.assertIn('mut %s:' % word, entry)

    def test_the_firmware_set_names_fixtures_with_a_status(self):
        workloads = timing.firmware_workloads()
        self.assertTrue(workloads)
        for workload in workloads:
            self.assertIsNotNone(workload['meta'].status, workload['name'])
        with self.assertRaisesRegex(common.Failed, 'no firmware workload named nothing'):
            timing.firmware_workloads(['nothing'])

    def test_a_rooted_workload_is_named_by_its_files_so_the_entry_can_join(self):
        rooted = dict(meta={'root': '../../../../..'}, directory=ROOT / 'compiler/tests/fixtures/runtime/cmp-siphash-vectors')
        named = timing.sources(rooted)
        self.assertEqual(named[0], '--root=' + str(ROOT))
        self.assertTrue(all(p.endswith('.ldn') for p in named[1:]) and named[1:])


class Clocks(unittest.TestCase):
    def test_known_states_decode_and_others_keep_their_registers(self):
        stm = lambda cr, cfgr, d1: dict(registers={'0x58024400': cr, '0x58024410': cfgr,
                                                    '0x58024418': d1})
        self.assertEqual(timing.decode_clock('stm32h753', stm(0x25, 0, 0)), dict(source='hsi', hz=64000000))
        self.assertEqual(timing.decode_clock('stm32h753', stm(0x25 | 1 << 3, 0, 0))['hz'], 32000000)
        self.assertEqual(timing.decode_clock('stm32h753', stm(0x25, 0, 8 << 8))['hz'], 32000000)
        self.assertEqual(timing.decode_clock('stm32h753', stm(0x25, 3 << 3, 0))['source'], 'registers')
        c3 = lambda sysclk: dict(registers={'0x600c0008': 12, '0x600c0058': sysclk})
        self.assertEqual(timing.decode_clock('esp32c3', c3(0xa8001)), dict(source='xtal', hz=20000000))
        self.assertEqual(timing.decode_clock('esp32c3', c3(0xa8000))['hz'], 40000000)
        self.assertEqual(timing.decode_clock('esp32c3', c3(0xa8400))['source'], 'registers')
        c5 = lambda sysclk, cpu: dict(registers={'0x60096110': sysclk, '0x60096114': 0xd,
                                                 '0x60096118': cpu, '0x6009611c': 0})
        self.assertEqual(timing.decode_clock('esp32c5', c5(0xb0000200, 0)), dict(source='xtal', hz=48000000))
        self.assertEqual(timing.decode_clock('esp32c5', c5(0xa8000200, 1))['hz'], 20000000)
        self.assertEqual(timing.decode_clock('esp32c5', c5(0xb0020200, 0))['source'], 'registers')
        self.assertEqual(timing.decode_clock('rp2040', dict(source='xosc', hz=12000000, x=1)),
                         dict(source='xosc', hz=12000000))
        self.assertEqual(timing.clock_key(dict(source='xtal', hz=40000000)), 'xtal-40000000hz')
        self.assertEqual(timing.clock_key(timing.decode_clock('esp32c3', c3(0xa8400))),
                         'registers-0x600c0008=0xc-0x600c0058=0xa8400')


class Runs(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.out = Path(self.temporary.name)

    def run_with(self, timed, image=None, board='esp32', reported=None):
        """time_load's verdict on a helper that reports TIMED, its report's
        other fields changed by REPORTED."""
        image = image or dict(workload='w', digest='d' * 64, elf_sha256='e' * 64, status=42)
        report = dict(format_version=1, status='passed', mode='time', flash_written=False,
                      board=board, elf_sha256=image['elf_sha256'],
                      helper_source_sha256=common.helper_source_hash(), timing=timed)
        report.update(reported or {})
        args = SimpleNamespace(probe='p', seconds=5, ram_loader='helper',
                               pace=mock.Mock())
        plans = []

        def helper(run, name, argv, **_):
            plans.append(json.loads(Path(argv[argv.index('--plan') + 1]).read_text()))
            Path(argv[argv.index('--output') + 1]).write_text(json.dumps(report))
        with mock.patch.object(common, 'probe_command', helper):
            return timing.time_load(SimpleNamespace(out=self.out), args, board, image,
                                    self.out / 'x.elf', 1), plans

    def timed(self, before, after, **more):
        timed = dict(status=42, count=999, unit='cycles', host_seconds=0.01,
                     clock=dict(source='xtal', hz=40000000),
                     words={timing.BEFORE: [before], timing.AFTER: [after]})
        timed.update(more)
        return timed

    def test_the_figure_is_what_the_program_read_around_main(self):
        got, (plan,) = self.run_with(self.timed(0xfffffff0, 0x10))
        self.assertEqual((got['count'], got['probe_count']), (0x20, 999))
        self.assertEqual(plan['mode'], 'time')
        self.assertEqual(plan['status'], timing.STATUS)
        self.assertEqual([w['symbol'] for w in plan['words']], [timing.BEFORE, timing.AFTER])

    def test_a_wrong_status_or_a_long_count_fails_and_a_checksum_is_kept(self):
        with self.assertRaisesRegex(common.Failed, 'returned 7, expected 42'):
            self.run_with(self.timed(0, 1, status=7))
        with self.assertRaisesRegex(common.Failed, r'past 2\^31'):
            self.run_with(self.timed(0, 1 << 31))
        with self.assertRaisesRegex(common.Failed, 'long enough for its counter to pass'):
            self.run_with(self.timed(0, 1, host_seconds=60.0))
        # The program holds its checksum to the expected one before it
        # returns 42; the run reads the word and keeps it.
        image = dict(workload='w', digest='d' * 64, elf_sha256='e' * 64, status=42,
                     checksum='checksum')
        timed = self.timed(0, 1)
        timed['words']['checksum'] = [0x1234]
        got, (plan,) = self.run_with(timed, image)
        self.assertEqual(plan['words'][-1], dict(symbol='checksum', count=1))
        self.assertEqual(got['checksum'], 0x1234)

    def test_a_report_for_another_image_is_not_evidence(self):
        with self.assertRaisesRegex(common.Failed, 'did not return matching timing evidence'):
            self.run_with(self.timed(0, 1), reported=dict(elf_sha256='f' * 64))
        with self.assertRaisesRegex(common.Failed, 'did not return matching timing evidence'):
            self.run_with(self.timed(0, 1), reported=dict(mode='warm'))


def figure(cycles, clock='xtal-40000000hz', placement='text:iram0,data:dram0,stack:dram0', **more):
    return dict(dict(figure=cycles, unit='cycles', counter='CCOUNT', clock=clock, placement=placement,
                     runs=3, spread=0, image='i' * 64, compiler='c' * 64), **more)


class Baselines(unittest.TestCase):
    """compare and record against baselines in a temporary directory: the
    base commit's are what read_baseline gives for a revision, the
    candidate's what the directory holds."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.base = {}
        noise = self.root / 'noise.json'
        noise.write_text(json.dumps(dict(tolerance=dict(esp32=dict(relative=0.002, absolute=8)))))
        real = timing.read_baseline
        for name, value in (('BASELINES', self.root / 'baselines'), ('NOISE', noise)):
            patcher = mock.patch.object(timing, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(timing, 'read_baseline', lambda board, rev=None: (
            self.base.get(board, {}) if rev else real(board)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def figures(self, found):
        path = self.root / ('figures-%d.json' % len(list(self.root.glob('figures-*'))))
        path.write_text(json.dumps(dict(schema=1, kind='cycles', figures=found)))
        return path

    def compare(self, found, report=False):
        printed = io.StringIO()
        with redirect_stdout(printed), mock.patch.object(sys, 'stderr', io.StringIO()), \
                mock.patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': ''}):
            code = timing.compare(SimpleNamespace(figures=self.figures(found), base='BASE',
                                                  report=report))
        return code, printed.getvalue()

    def test_a_branch_s_comparison_reports_a_move_and_passes(self):
        # D2854: the cycles comparison on a branch's dispatch names what
        # no baseline records, in moves.json beside the figures, and passes.
        key = 'esp32/xtensa-esp32/size-auto/sieve'
        new = 'esp32/xtensa-esp32/size-auto/search'
        self.recorded_base({key: figure(10000)})
        code, said = self.compare({key: figure(12000), new: figure(5)}, report=True)
        self.assertEqual(code, 0, said)
        self.assertIn('REPORTED, not failed: 2 cycles figures', said)
        moves = json.loads((self.root / 'moves.json').read_text())
        self.assertEqual(moves, dict({'class': 'cycles', 'undeclared': [key], 'unrecorded': [new]}))
        code, _ = self.compare({key: figure(10000)}, report=True)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads((self.root / 'moves.json').read_text())['undeclared'], [])

    def record(self, found, **more):
        with redirect_stdout(io.StringIO()):
            timing.record(SimpleNamespace(figures=self.figures(found), board=None, key=None, **more))

    def recorded_base(self, found):
        self.record(found)
        self.base['esp32'] = json.loads(timing.baseline_path('esp32').read_text())

    def test_a_figure_within_tolerance_passes_and_beyond_it_fails_either_way(self):
        key = 'esp32/xtensa-esp32/size-auto/sieve'
        self.recorded_base({key: figure(10000)})
        self.assertEqual(self.compare({key: figure(10020)})[0], 0)
        for changed in (10021, 9979, 20000):
            code, said = self.compare({key: figure(changed)})
            self.assertEqual(code, 1, changed)
            self.assertIn('UNDECLARED', said)
            self.assertIn(key, said)
        # The absolute floor holds a small figure.
        small = 'esp32/xtensa-esp32/size-auto/search'
        self.recorded_base({small: figure(100)})
        self.assertEqual(self.compare({small: figure(108)})[0], 0)
        self.assertEqual(self.compare({small: figure(109)})[0], 1)

    def test_a_change_the_candidate_records_is_declared(self):
        key = 'esp32/xtensa-esp32/size-auto/sieve'
        self.recorded_base({key: figure(10000)})
        self.record({key: figure(12000)})
        code, said = self.compare({key: figure(12001)})
        self.assertEqual(code, 0, said)
        self.assertIn("declared by the candidate's baselines: 1", said)
        self.assertIn('10000 -> 12001 (+20.01%)', said)

    def test_a_configuration_without_a_baseline_or_with_a_new_placement_fails(self):
        key = 'esp32/xtensa-esp32/size-auto/sieve'
        code, said = self.compare({key: figure(10000)})
        self.assertEqual(code, 1)
        self.assertIn('UNRECORDED: 1 configurations', said)
        self.recorded_base({key: figure(10000)})
        code, said = self.compare({key: figure(10000, placement='text:iram0,data:iram0,stack:dram0')})
        self.assertEqual(code, 1)
        self.assertIn('placement text:iram0,data:dram0,stack:dram0 -> text:iram0', said)

    def test_another_clock_is_the_runner_s_and_is_recorded_rather_than_failed(self):
        key = 'esp32/xtensa-esp32/size-auto/sieve'
        self.recorded_base({key: figure(10000)})
        code, said = self.compare({key: figure(15000, clock='xtal-20000000hz')})
        self.assertEqual(code, 0, said)
        self.assertIn('the base ran at xtal-40000000hz, this at xtal-20000000hz', said)

    def test_a_limit_is_compared_as_its_reason(self):
        key = 'esp32/xtensa-esp32/size-auto/siphash'
        self.recorded_base({key: dict(limit='not whole words')})
        self.assertEqual(self.compare({key: dict(limit='not whole words')})[0], 0)
        self.assertEqual(self.compare({key: figure(5)})[0], 1)

    def test_record_writes_one_file_per_board_keyed_by_level_profile_and_workload(self):
        self.record({'esp32/xtensa-esp32/size-auto/sieve': figure(10, checksum='0x00000001'),
                     'rp2040/armv6-m/none-off/sieve': figure(7, clock='xosc-12000000hz')})
        esp32 = json.loads(timing.baseline_path('esp32').read_text())
        self.assertEqual((esp32['board'], esp32['target'], esp32['level']), ('esp32', 'xtensa', 'xtensa-esp32'))
        self.assertEqual(esp32['entries']['xtensa-esp32/size-auto/sieve'],
                         dict(cycles=10, unit='cycles', counter='CCOUNT', clock='xtal-40000000hz',
                              placement='text:iram0,data:dram0,stack:dram0', image='i' * 64, runs=3,
                              checksum='0x00000001'))
        self.assertEqual(json.loads(timing.baseline_path('rp2040').read_text())['level'], 'armv6-m')
        # A whole record replaces the board's baseline; --key adds to it.
        self.record({'esp32/xtensa-esp32/size-auto/other': figure(11)})
        self.assertEqual(list(json.loads(timing.baseline_path('esp32').read_text())['entries']),
                         ['xtensa-esp32/size-auto/other'])
        self.record({'esp32/xtensa-esp32/none-off/x': figure(12)}, )
        with redirect_stdout(io.StringIO()):
            timing.record(SimpleNamespace(figures=self.figures({
                'esp32/xtensa-esp32/none-off/y': figure(13)}), board=None,
                key=['esp32/xtensa-esp32/none-off/y']))
        self.assertEqual(sorted(json.loads(timing.baseline_path('esp32').read_text())['entries']),
                         ['xtensa-esp32/none-off/x', 'xtensa-esp32/none-off/y'])

    def test_a_study_of_one_board_keeps_the_others_and_the_tolerances(self):
        output = self.root / 'study.json'
        output.write_text(json.dumps(dict(boards=dict(esp32=dict(kept=1), rp2040=dict(kept=2)),
                                          tolerance=dict(esp32=dict(relative=0.002, absolute=8)))))
        results = self.root / 'results' / 'esp32'
        results.mkdir(parents=True)
        image = dict(workload='sieve', digest='d', profiles=['size-auto'], counts=[5] * 10,
                     counter='CCOUNT', unit='cycles', clock_key='xtal-40000000hz',
                     placement='text:iram0,data:dram0,stack:dram0')
        (results / 'result.json').write_text(json.dumps(dict(
            status='passed', board='esp32', images=[image], compiler=dict(sha256='c'),
            bundle_source='b', seconds=1)))
        with redirect_stdout(io.StringIO()):
            timing.noise(SimpleNamespace(results=[self.root / 'results'], least=10, note='n',
                                         output=str(output)))
        study = json.loads(output.read_text())
        self.assertEqual(study['boards']['rp2040'], dict(kept=2))
        self.assertEqual(study['boards']['esp32']['workloads']['sieve']['median'], 5)
        self.assertEqual(study['tolerance'], dict(esp32=dict(relative=0.002, absolute=8)))

    def test_the_committed_baselines_cover_every_board_with_a_tolerance(self):
        noise = json.loads((ROOT / 'compiler/tests/measure/noise/cycles.json').read_text())
        self.assertEqual(set(noise['tolerance']), set(timing.BOARDS))
        for board in timing.BOARDS:
            path = ROOT / 'compiler/tests/measure/baselines' / ('%s.cycles.json' % board)
            if not path.exists():
                continue
            kept = json.loads(path.read_text())
            self.assertEqual((kept['board'], kept['target']), (board, timing.BOARDS[board][0]))


class Evidence(unittest.TestCase):
    def test_each_port_s_latest_attempt_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for attempt, port, boards in ((1, 'pico2', ('rp2350', 'rp2350_hazard3')),
                                          (2, 'pico2', ('rp2350_hazard3',)), (1, 'esp32', ('esp32',))):
                leg = root / ('board-evidence-%s-%d' % (port, attempt)) / port
                leg.mkdir(parents=True)
                (leg / 'transfer.json').write_text(json.dumps(dict(port=port, run_attempt=str(attempt))))
                for board in boards:
                    (leg / 'evidence' / (board + '-time')).mkdir(parents=True)
                    (leg / 'evidence' / (board + '-time') / 'result.json').write_text('{}')
                (leg / 'evidence' / 'esp32-ram').mkdir(parents=True)
            found = [path.relative_to(root).as_posix() for path in timing.latest_legs(root)]
            self.assertEqual(found, ['board-evidence-esp32-1/esp32/evidence/esp32-time/result.json',
                                     'board-evidence-pico2-2/pico2/evidence/rp2350_hazard3-time/result.json'])


class Remote(unittest.TestCase):
    def test_the_rig_host_is_reached_with_the_named_key_alone(self):
        """`remote` logs in as run.py does, IdentitiesOnly included: with
        several keys in an agent, BatchMode otherwise ended in "too many
        authentication failures"."""
        import subprocess
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from expected_runs import expect
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'bundle').mkdir()
            args = SimpleNamespace(bundle=root / 'bundle', output=root / 'out', host='rigpi',
                                   identity=Path('/the key'))
            refused = expect({'ssh': SimpleNamespace(returncode=255, stdout='', stderr='refused')})
            with mock.patch.object(timing, 'read_bundle'), \
                    mock.patch.object(timing.bundle, 'snapshot'), \
                    mock.patch.object(timing.subprocess, 'run', side_effect=refused):
                with self.assertRaisesRegex(common.Failed, 'remote staging failed: refused'):
                    timing.remote(args, [])
        self.assertEqual(refused.calls, [['ssh', '-i', '/the key', '-o', 'IdentitiesOnly=yes',
                                          '-o', 'BatchMode=yes', 'rigpi',
                                          'umask 077; mktemp -d /tmp/landin-timing.XXXXXXXX']])


class Runs(unittest.TestCase):
    """`run` and `remote` by hand, the board operations faked."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def parsed(self, command, *more):
        """The arguments COMMAND is given by its parser, as main gives them."""
        got = {}
        target = 'run_board' if command == 'run' else command
        with mock.patch.object(timing, target, lambda args, *rest: got.setdefault('args', args) and 0):
            timing.main([command, '--bundle=b', '--output=o', *(['--board=esp32'] if command == 'run'
                                                                else []), *more])
        return got['args']

    def test_run_and_remote_take_the_gate_s_three_runs_unless_told_otherwise(self):
        """A figure by hand is the gate's figure: the gate's time steps pass
        the same constant the tools default to."""
        import gate
        self.assertEqual(timing.REPEAT, 3)
        self.assertEqual(gate.TIMING_REPEAT, timing.REPEAT)
        for command in ('run', 'remote'):
            self.assertEqual(self.parsed(command).repeat, timing.REPEAT, command)
            self.assertEqual(self.parsed(command, '--repeat=1').repeat, 1, command)
        printed = io.StringIO()
        with redirect_stdout(printed), self.assertRaises(SystemExit):
            timing.main(['run', '--help'])
        self.assertIn("not the gate's figure", ' '.join(printed.getvalue().split()))

    def run_pico(self, board, attach):
        """run_board for BOARD, a Pico 2 port, whose architecture read
        ATTACH answers; returns the result written and the images timed."""
        manifest = dict(source_identity='s', compiler=dict(sha256='c'), boards={board: dict(images=[
            dict(workload='w', digest='d' * 64, elf='images/w.elf', profiles=['none-off'],
                 placement='text:sram,data:sram,stack:sram')])})
        args = SimpleNamespace(board=board, bundle=self.root / 'bundle', image=None, profile=None,
                               output=self.root / ('out-%d' % len(list(self.root.glob('out-*')))), probe=None, spacing=0, quiet=0,
                               ram_loader=Path('/helper'), hub='.3.3', port=2, power_only=True,
                               hub_group='dialout', repeat=timing.REPEAT, seconds=20)
        timed, written = [], {}

        def probe_command(run, name, argv, **kw):
            run.commands.append(dict(name=name, status=attach))
            if attach:
                raise common.Failed('%s failed' % name)
            Path(run.out / (name + '.json')).write_text(json.dumps(dict(
                format_version=1, status='passed', mode='read', board=board, flash_written=False,
                helper_source_sha256='h', address=0x10000000, count=1, words=[0])))
            return ''
        import pico2
        with mock.patch.object(timing, 'read_bundle', return_value=manifest), \
                mock.patch.object(common, 'verify_ram_helper'), \
                mock.patch.object(common, 'place_hubs'), \
                mock.patch.object(common, 'Pace'), \
                mock.patch.object(common, 'rig_lock'), \
                mock.patch.object(common, 'retain_kernel_usb'), \
                mock.patch.object(common, 'helper_source_hash', return_value='h'), \
                mock.patch.object(common, 'probe_command', side_effect=probe_command), \
                mock.patch.object(common, 'write_result',
                                  side_effect=lambda path, result, run: written.update(result)), \
                mock.patch.object(pico2, 'refuse_bootsel'), \
                mock.patch.object(timing, 'time_load', side_effect=lambda run, a, b, image, elf, n: (
                    timed.append(n) or dict(count=100 + n, clock=dict(source='xtal', hz=12000000),
                                            counter='CYCCNT', unit='cycles', probe_count=0,
                                            halted_drift=0, host_seconds=0.1, setup={}))), \
                redirect_stdout(io.StringIO()):
            timing.run_board(args)
        return written, timed

    def test_the_rp2350_is_read_as_arm_before_any_image_and_refused_on_another_image(self):
        """A warm load never changes the Pico 2's architecture: the Arm port's
        timing run reads the board as RP235x first and, where its cores run
        Hazard3, refuses before any timing load, naming the boot check that
        puts the board on Arm as the gate's pico2 port runs it."""
        written, timed = self.run_pico('rp2350', attach=1)
        self.assertEqual((written['status'], written['outcome'], timed), ('failed', 'needs-setup', []))
        said = written['failure']
        for part in ('does not answer as RP235x', 'run the rp2350 boot check first',
                     'run.py --board=rp2350 --mode=boot', 'rp2350_hazard3 boot check'):
            self.assertIn(part, said)
        self.assertEqual([c['name'] for c in written['commands']], ['architecture-RP235x'])
        written, timed = self.run_pico('rp2350', attach=0)
        self.assertEqual((written['status'], timed), ('passed', [1, 2, 3]))
        self.assertEqual(written['images'][0]['median'], 102)
        written, timed = self.run_pico('rp2350_hazard3', attach=1)
        self.assertIn('run.py --board=rp2350_hazard3 --mode=boot', written['failure'])
        self.assertEqual([c['name'] for c in written['commands']], ['architecture-RP235x_riscv'])


if __name__ == '__main__':
    unittest.main()
