#!/usr/bin/env python3
"""core/text's float text: its tables, its fixtures and its exhaustive run.

    python3 scripts/float_text.py tables [--check]
    python3 scripts/float_text.py fixtures [--check]
    python3 scripts/float_text.py drawn [--count N] [--jobs N]
    python3 scripts/float_text.py exhaustive [--parts N] [--jobs N] [--output DIR]

`tables` writes core/text/powers.ldn, the powers of five the shortest
writer multiplies by, from Python's integers: thirteen and fifteen
128-bit bases a 64-bit factor scales to every power the writer meets,
and the two-bit corrections that make each scaled power the exact one.
`--check` says whether the file is current and writes nothing.

`fixtures` writes the `float-text-*` runtime fixtures: programs whose
tables hold floats and the text Python writes for them, its own `repr`
for the shortest digits and C's `printf`, called through `ctypes`, for
fixed and exponent precision, and decimal text with the float Python
reads from it; each exits 42 when core/text agrees with every record.
`--check` says whether they are current.

`drawn` compiles compiler/tests/float-text/drawn.ldn at `--optimize
speed` and checks the texts and readings of `--count` drawn `f64`s, a
million by default, against Python's repr, C's printf and Python's exact
fractions.

`exhaustive` compiles compiler/tests/float-text/exhaustive.ldn at
`--optimize speed` and runs it over every `f32` bit pattern in `--parts`
slices, `--jobs` at a time: each slice writes every value's shortest
text, reads it back, and checks it against the exact digits rounded to
its length.  The programs are compiled with `--refine`, $LANDIN_REFINE,
or the refine this checkout built last.
"""

import argparse
from fractions import Fraction
import math
import random
import re
import struct
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import big_oracle  # noqa: E402
import lane_refine  # noqa: E402

POWERS = ROOT / 'core/text/powers.ldn'
EXHAUSTIVE = ROOT / 'compiler/tests/float-text/exhaustive.ldn'
DRAWN = ROOT / 'compiler/tests/float-text/drawn.ldn'


class Failure(Exception):
    """A refusal to report on one line."""


def default_refine():
    """The refine this checkout built last."""
    found = sorted(ROOT.glob('compiler/ada/build/*/*/bin/refine'),
                   key=lambda path: path.stat().st_mtime)
    if not found:
        raise Failure('no refine: build one with ./scripts/dev-build.sh, or name'
                      ' one with --refine')
    return found[-1]

#  The power of five the bases are spaced by: 5^25 is the greatest that
#  fits the 64-bit factor, so every power is a base times one factor.
STRIDE = 26
#  The bits each power keeps, as Ryu keeps them for a double.
KEPT = 125
#  The powers the writer meets for an `f64`: 5^q's inverse for q below
#  342 and 5^i for i below 326, which also cover every `f32`.
INVERSES = 342
POWERS_COUNT = 326


def power_bits(exponent):
    """The bits of 5^exponent, by the writer's own formula."""
    return ((exponent * 1217359) >> 19) + 1


def split(index):
    """5^index scaled to exactly KEPT bits, the top ones kept."""
    value = 5 ** index
    length = value.bit_length()
    if length >= KEPT:
        return value >> (length - KEPT)
    return value << (KEPT - length)


def inverse(index):
    """2^(bits - 1 + KEPT) / 5^index, rounded down, plus one."""
    value = 5 ** index
    length = value.bit_length()
    return (1 << (length - 1 + KEPT)) // value + 1


def scaled(base, factor, shift):
    """What the writer computes: base times factor, shifted right."""
    return (base * factor) >> shift


def tables():
    """The bases, the factors and the corrections, each checked."""
    for exponent in range(4000):
        assert exponent == 0 or power_bits(exponent) == (5 ** exponent).bit_length()
    factors = [5 ** offset for offset in range(STRIDE)]
    assert factors[-1] < 1 << 64
    split_bases = [split(STRIDE * at) for at in range((POWERS_COUNT - 1) // STRIDE + 1)]
    inverse_bases = [inverse(STRIDE * at)
                     for at in range((INVERSES - 1 + STRIDE - 1) // STRIDE + 1)]
    split_deltas = []
    for index in range(POWERS_COUNT):
        at, offset = divmod(index, STRIDE)
        shift = power_bits(index) - power_bits(STRIDE * at)
        assert 0 <= shift < 64
        delta = split(index) - scaled(split_bases[at], factors[offset], shift)
        assert 0 <= delta <= 3, (index, delta)
        split_deltas.append(delta)
    inverse_deltas = []
    for index in range(INVERSES):
        at = (index + STRIDE - 1) // STRIDE
        offset = STRIDE * at - index
        shift = power_bits(STRIDE * at) - power_bits(index)
        assert 0 <= shift < 64
        delta = inverse(index) - scaled(inverse_bases[at], factors[offset], shift)
        assert -1 <= delta <= 2, (index, delta)
        inverse_deltas.append(delta + 1)
    for value in split_bases + inverse_bases:
        assert value < 1 << 128
    return factors, split_bases, inverse_bases, split_deltas, inverse_deltas


def packed(deltas):
    """Two-bit corrections sixteen to a u32, the first in the low bits."""
    words = []
    for start in range(0, len(deltas), 16):
        word = 0
        for place, delta in enumerate(deltas[start:start + 16]):
            word |= delta << (2 * place)
        words.append(word)
    return words


def array(name, kind, values, width):
    """A Landin array declaration, a few hexadecimal values a line."""
    per_line = 4 if width == 16 else 6
    lines = [f'{name}: [{len(values)}]{kind} = [']
    for start in range(0, len(values), per_line):
        chunk = ', '.join(f'0x{value:0{width}x}' for value in values[start:start + per_line])
        last = start + per_line >= len(values)
        lines.append(f'    {chunk}{"" if last else ","}')
    lines.append(']')
    return '\n'.join(lines)


def halves(values):
    """Each 128-bit value as its low and its high 64 bits."""
    words = []
    for value in values:
        words.append(value & ((1 << 64) - 1))
        words.append(value >> 64)
    return words


def powers_source():
    factors, split_bases, inverse_bases, split_deltas, inverse_deltas = tables()
    parts = [
        '--  Generated by scripts/float_text.py: edit that and run',
        '--  `python3 scripts/float_text.py tables`, never this file.',
        '--  The powers of five the shortest writer multiplies by (shortest.ldn).',
        f'--  A power 5^i keeps its top {KEPT} bits, and an inverse is',
        f'--  2^(bits of 5^q - 1 + {KEPT}) / 5^q rounded down, plus one, as Ryu',
        '--  keeps them; each is a base, one every 26 powers, times a power of',
        '--  five below 2^64, shifted down and corrected by its two bits.',
        '',
        '--  5^0 to 5^25, the factors.',
        array('five_factors', 'u64', factors, 16),
        '',
        '--  5^(26 n) to 125 bits, the low half first.',
        array('five_bases', 'u64', halves(split_bases), 16),
        '',
        '--  The inverse of 5^(26 n), the low half first.',
        array('inverse_bases', 'u64', halves(inverse_bases), 16),
        '',
        '--  What to add to each scaled power, two bits each, sixteen to a word.',
        array('five_corrections', 'u32', packed(split_deltas), 8),
        '',
        '--  One more than what to add to each scaled inverse.',
        array('inverse_corrections', 'u32', packed(inverse_deltas), 8),
        '',
    ]
    return '\n'.join(parts)


def command_tables(arguments):
    source = powers_source()
    if arguments.check:
        current = POWERS.read_text() if POWERS.exists() else ''
        if current != source:
            print(f'{POWERS.relative_to(ROOT)} is not current: run '
                  '`python3 scripts/float_text.py tables`', file=sys.stderr)
            return 1
        return 0
    POWERS.write_text(source)
    return 0


FIXTURES = ROOT / 'compiler/tests/fixtures/runtime'
MASK = (1 << 64) - 1
#  Every target a runtime fixture runs on; the firmware lanes take theirs
#  from compiler/tests/cortex-m/corpus.json.
TARGETS = ('linux-x86-64, linux-arm64, darwin-arm64, freebsd-x86-64, '
           'freebsd-arm64, linux-rv64, cortex-m0, windows-x86-64, '
           'windows-arm64')
#  The fixtures whose image passes the Cortex-M0 reference's 32 KiB, every
#  one with its tables of texts, which corpus.json records as a profile
#  limit with the measured sizes, and which leave cortex-m0 out of their
#  targets: the mps2-an500 lane runs them.
FIRMWARE_LIMITED = {'float-text-shortest', 'float-text-rounded', 'float-text-parse',
                    'float-text-single'}

_LIBC = []


def printf(form, value):
    """C's snprintf of one double, the oracle for the rounded forms."""
    import ctypes
    import ctypes.util
    if not _LIBC:
        _LIBC.append(ctypes.CDLL(ctypes.util.find_library('c') or None))
    room = ctypes.create_string_buffer(4096)
    _LIBC[0].snprintf(room, 4096, form.encode('ascii'), ctypes.c_double(value))
    return room.value.decode('ascii')


def from_bits(bits, single=False):
    if single:
        return struct.unpack('<f', struct.pack('<I', bits))[0]
    return struct.unpack('<d', struct.pack('<Q', bits))[0]


def bits_of(value, single=False):
    if single:
        return struct.unpack('<I', struct.pack('<f', value))[0]
    return struct.unpack('<Q', struct.pack('<d', value))[0]


def is_nan(value):
    return value != value


def shortest_digits(value, single=False):
    """The shortest digits that read back, without trailing zeros, and the
    power of ten of the first: Python's repr finds them for an f64; for an
    f32 each length is searched, the decimals nearest the value tried and
    read back by exact rounding."""
    if single:
        bits = bits_of(value, single=True)
        exact = abs(Fraction(value))
        sign = -1 if bits >> 31 else 1
        for length in range(1, 10):
            mantissa, power = ('%.*e' % (length - 1, abs(value))).split('e')
            digits = int(mantissa.replace('.', ''))
            best = None
            for candidate in (digits - 1, digits, digits + 1):
                if candidate <= 0 or len(str(candidate)) != length:
                    continue
                decimal = Fraction(candidate) * Fraction(10) ** (int(power) - length + 1)
                back = big_oracle.float_bits(sign * decimal, big_oracle.SINGLE)
                if back == bits:
                    distance = abs(decimal - exact)
                    if best is None or distance < best[0] or (
                            distance == best[0] and candidate % 2 == 0):
                        best = (distance, candidate)
            if best is not None:
                return str(best[1]).rstrip('0'), int(power)
        raise Failure('no shortest digits for %r' % value)
    text = repr(abs(value))
    mantissa, _, power = text.partition('e')
    whole, _, part = mantissa.partition('.')
    digits = (whole + part).lstrip('0')
    leading = len(whole + part) - len(digits)
    place = len(whole) - leading - 1 + (int(power) if power else 0)
    return digits.rstrip('0'), place


def literal_text(value, single=False, exponent=False, letter='e', plus=False):
    """The shortest text as core/text writes it."""
    if is_nan(value):
        return 'NaN'
    sign = '-' if math.copysign(1.0, value) < 0 else ('+' if plus else '')
    if math.isinf(value):
        return sign + 'inf'
    if value == 0:
        return sign + ('0.0' if not exponent else '0.0' + letter + '0')
    digits, place = shortest_digits(value, single)
    if not exponent and -4 <= place < 16:
        point = place + 1
        if point <= 0:
            body = '0.' + '0' * -point + digits
        elif point >= len(digits):
            body = digits + '0' * (point - len(digits)) + '.0'
        else:
            body = digits[:point] + '.' + digits[point:]
    else:
        body = digits[0] + '.' + (digits[1:] or '0') + letter + str(place)
    return sign + body


def fixed_text(value, places, plus=False):
    if is_nan(value):
        return 'NaN'
    return printf('%' + ('+' if plus else '') + '.' + str(places) + 'f', value)


def places_text(value, places, letter='e', plus=False):
    if is_nan(value):
        return 'NaN'
    text = printf('%' + ('+' if plus else '') + '.' + str(places) + 'e', value)
    if 'e' not in text:
        return text
    mantissa, power = text.split('e')
    return mantissa + letter + str(int(power))


FNV_START = 0xcbf29ce484222325


def fnv(value, data):
    for byte in data:
        value = ((value ^ byte) * 0x100000001b3) & MASK
    return value


def shaped(raw):
    """A drawn f64's bits, shaped as the fixtures shape them: any bits, a
    moderate exponent, a subnormal or the least normals, or a short
    significand."""
    kind = raw & 3
    if kind == 0:
        return raw
    if kind == 1:
        return (raw & 0x800fffffffffffff) | ((953 + (raw >> 2) % 141) << 52)
    if kind == 2:
        return raw & 0x801fffffffffffff
    return raw & 0xfffff00000000000


def shaped_32(raw):
    """A drawn f32's bits, shaped alike."""
    kind = raw & 3
    if kind == 0:
        return raw
    if kind == 1:
        return (raw & 0x807fffff) | ((97 + (raw >> 2) % 61) << 23)
    if kind == 2:
        return raw & 0x80ffffff
    return raw & 0xfffc0000


def landin_text(text):
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'


HEADER = """\
--  Generated by scripts/float_text.py: edit that and run
--  `python3 scripts/float_text.py fixtures`, never this file.
"""

COMMON = """
float_64: (bits: u64) -> (value: f64) =
    view: ptr f64 = ptr(usize(addr bits))
    value = view.val
end float_64

float_32: (bits: u32) -> (value: f32) =
    view: ptr f32 = ptr(usize(addr bits))
    value = view.val
end float_32

bits_64: (value: f64) -> (bits: u64) =
    view: ptr u64 = ptr(usize(addr value))
    bits = view.val
end bits_64

bits_32: (value: f32) -> (bits: u32) =
    view: ptr u32 = ptr(usize(addr value))
    bits = view.val
end bits_32

--  FNV-1a over the bytes, from `hash`.
mixed: (hash: u64, bytes: []u8) -> (result: u64) =
    mut value: u64 = hash
    for byte in bytes do
        value = (value ^ u64(byte)) *% 0x100000001b3
    end for
    result = value
end mixed

same: (left: []u8, right: utf8) -> (yes: bool) =
    yes = cmp.compare(left, text.bytes(right)) == cmp.equal
end same

shaped: (raw: u64) -> (bits: u64) =
    kind: u64 = raw & 3
    bits = if kind == 0 then raw
           elsif kind == 1 then (raw & 0x800fffffffffffff) | ((953 + (raw >> 2) % 141) << 52)
           elsif kind == 2 then raw & 0x801fffffffffffff
           else raw & 0xfffff00000000000 end if
end shaped

shaped_32: (raw: u32) -> (bits: u32) =
    kind: u32 = raw & 3
    bits = if kind == 0 then raw
           elsif kind == 1 then (raw & 0x807fffff) | ((97 + (raw >> 2) % 61) << 23)
           elsif kind == 2 then raw & 0x80ffffff
           else raw & 0xfffc0000 end if
end shaped_32
"""


def unique(values):
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def edge_bits(spacing=1):
    """The f64 bit patterns the tables hold: the ends of each range, powers
    of two and ten, and values whose rounding is a tie or near one.  A
    `spacing` above one takes every so many of the powers, for a table
    whose texts take long to compute on the slowest lanes."""
    values = [0, 1 << 63, 1, 2, 3, 0x000fffffffffffff, 0x0010000000000000,
              0x0010000000000001, 0x7fefffffffffffff, 0x7ff0000000000000,
              0xfff0000000000000, 0x7ff8000000000000, 0x7ff0000000000001,
              0xfff8000000000000]
    for power in range(-1074, 1024, 37 * spacing):
        values.append(bits_of(math.ldexp(1.0, power)))
    for power in range(-323, 309, 7 * spacing):
        values.append(bits_of(float('1e%d' % power)))
    for text in ['0.1', '0.2', '0.3', '1.5', '2.5', '0.125', '0.375', '1e15', '1e16',
                 '9007199254740993', '123456.789', '5e-324', '1.7976931348623157e308',
                 '2.2250738585072014e-308', '9.999999999999999e22', '1e23', '0.0001',
                 '0.00009999999999999999', '1e-5', '3.141592653589793', '2.718281828459045',
                 '299792458.0', '6.02214076e23', '1.602176634e-19', '0.5', '0.05', '0.005',
                 '1.005', '2.675', '1.45', '1e21', '1e22', '4.35', '0.045',
                 '1234567890123456789']:
        for sign in (1.0, -1.0):
            values.append(bits_of(sign * float(text)))
    return unique(values)


def edge_bits_32():
    values = [0, 0x80000000, 1, 2, 0x007fffff, 0x00800000, 0x7f7fffff, 0x7f800000,
              0xff800000, 0x7fc00000, 0x3f800000, 0x3dcccccd, 0x4b800001]
    for power in range(-149, 128, 11):
        values.append(bits_of(math.ldexp(1.0, power), single=True))
    for text in ['0.1', '0.3', '1.5', '2.5', '1e10', '3.4028235e38', '1e-45', '16777217',
                 '3.1415927', '0.0001', '1e-5', '1.1754944e-38', '1.17549435e-38']:
        for sign in (1.0, -1.0):
            values.append(bits_of(sign * float(text), single=True))
    return unique(values)


def shortest_program():
    cases = []
    for bits in edge_bits():
        value = from_bits(bits)
        cases.append('    (bits: 0x%016x, literal: %s, exponent: %s)' % (
            bits, landin_text(literal_text(value)),
            landin_text(literal_text(value, exponent=True))))
    generator = big_oracle.Generator(2220)
    draws = 10000
    hash_value = FNV_START
    for _ in range(draws):
        value = from_bits(shaped(generator.next()))
        line = literal_text(value) + ' ' + literal_text(value, exponent=True) + '\n'
        hash_value = fnv(hash_value, line.encode('ascii'))
    return HEADER + """\
--  core/text's shortest float text against Python's repr: `append_f64`
--  and `{{:e}}` for each record of `cases`, and the FNV-1a digest of both
--  for {draws} f64s drawn from core/random's xoshiro256** seeded with
--  2220, as the generator draws them.  It exits 42 when every text agrees.
import core/cmp
import core/random
import core/text

case_value: type = struct
    bits: u64
    literal: utf8
    exponent: utf8
end case_value

cases: [{count}]case_value = [
{cases}
]
{common}
public main: () -> (code: i32) =
    code = 1
    mut storage: [64]u8 = zeroed
    for case in cases do
        value: f64 = float_64(case.bits)
        mut line := text.over(storage[0..<64])
        text.append_f64(line, value) else begin return end
        return when not same(text.used(line), case.literal)
        text.clear(line)
        text.format(line, "{{:e}}", [any(addr value)]) else begin return end
        return when not same(text.used(line), case.exponent)
    end for
    mut source := random.new(2220)
    mut hash: u64 = 0xcbf29ce484222325
    for draw in usize(0)..<{draws} do
        _ = draw
        value: f64 = float_64(shaped(random.next(source)))
        mut line := text.over(storage[0..<64])
        text.format(line, "{{}} {{:e}}\\n", [any(addr value), any(addr value)])
            else begin return end
        hash = mixed(hash, text.used(line))
    end for
    return when hash <> 0x{digest:016x}
    code = 42
end main
""".format(draws=draws, count=len(cases), cases=',\n'.join(cases), common=COMMON,
           digest=hash_value)


def rounded_program():
    cases = []
    for bits in edge_bits(spacing=3):
        value = from_bits(bits)
        for places in (2, 17):
            cases.append('    (bits: 0x%016x, places: %d, point: %s, exponent: %s)' % (
                bits, places, landin_text(fixed_text(value, places)),
                landin_text(places_text(value, places))))
    generator = big_oracle.Generator(2221)
    draws = 60
    hash_value = FNV_START
    for _ in range(draws):
        value = from_bits(shaped(generator.next()))
        places = generator.next() % 21
        exponent = generator.next() % 18
        line = (fixed_text(value, places) + ' ' + places_text(value, exponent) + ' '
                + places_text(value, exponent, letter='E', plus=True) + '\n')
        hash_value = fnv(hash_value, line.encode('ascii'))
    return HEADER + """\
--  core/text's rounded float text against C's printf: `append_f64_fixed`
--  and `append_f64_exponent` at each record's places, and the FNV-1a
--  digest of `{{:.N}}`, `{{:.Ne}}` and `{{:+.NE}}` for {draws} f64s and
--  places drawn from core/random's xoshiro256** seeded with 2221.  It
--  exits 42 when every text agrees.
import core/cmp
import core/random
import core/text

case_value: type = struct
    bits: u64
    places: usize
    point: utf8
    exponent: utf8
end case_value

cases: [{count}]case_value = [
{cases}
]
{common}
public main: () -> (code: i32) =
    code = 1
    mut storage: [1200]u8 = zeroed
    for case in cases do
        value: f64 = float_64(case.bits)
        mut line := text.over(storage[0..<1200])
        text.append_f64_fixed(line, value, case.places) else begin return end
        return when not same(text.used(line), case.point)
        text.clear(line)
        text.append_f64_exponent(line, value, case.places) else begin return end
        return when not same(text.used(line), case.exponent)
    end for
    mut source := random.new(2221)
    mut hash: u64 = 0xcbf29ce484222325
    mut format: [40]u8 = zeroed
    for draw in usize(0)..<{draws} do
        _ = draw
        value: f64 = float_64(shaped(random.next(source)))
        places: usize = usize(random.next(source) % 21)
        exponent: usize = usize(random.next(source) % 18)
        mut line := text.over(storage[0..<1200])
        text.append_f64_fixed(line, value, places) else begin return end
        text.append_byte(line, u8(' ')) else begin return end
        text.append_f64_exponent(line, value, exponent) else begin return end
        text.append_byte(line, u8(' ')) else begin return end
        --  The precision is written into the template.
        mut template := text.over(format[0..<40])
        text.append(template, "{{:+.") else begin return end
        text.append_usize(template, exponent) else begin return end
        text.append(template, "E}}\\n") else begin return end
        spelled: utf8 = text.from_bytes(text.used(template)) else begin return end
        text.format(line, spelled, [any(addr value)]) else begin return end
        hash = mixed(hash, text.used(line))
    end for
    return when hash <> 0x{digest:016x}
    code = 42
end main
""".format(draws=draws, count=len(cases), cases=',\n'.join(cases), common=COMMON,
           digest=hash_value)


def exact_decimal(value):
    """A positive rational whose denominator divides a power of ten, as
    decimal text."""
    scale = 0
    while (value * 10 ** scale).denominator != 1:
        scale += 1
    digits = str((value * 10 ** scale).numerator).rjust(scale + 1, '0')
    return (digits[:-scale] + '.' + digits[-scale:]) if scale else digits


def halfway_texts(draw, count):
    """Exact decimals of the points halfway between neighbouring f64s, and
    a little above and below some, which decide a parse's rounding."""
    texts = []
    for _ in range(count):
        exponent = draw.choice([draw.randrange(0, 2046), draw.randrange(1000, 1080),
                                draw.randrange(0, 3)])
        bits = (exponent << 52) | draw.getrandbits(52)
        if bits + 1 >= 0x7ff0000000000000:
            continue
        middle = (Fraction(from_bits(bits)) + Fraction(from_bits(bits + 1))) / 2
        text = exact_decimal(middle)
        texts.append(text)
        nudge = draw.randrange(3)
        if nudge == 1:
            texts.append(text + ('1' if '.' in text else '.000000001'))
        elif nudge == 2:
            places = len(text) + 3
            texts.append(exact_decimal(middle - Fraction(1, 10 ** places)))
    return texts


def parsed(text, single=False):
    """What parse_f64 or parse_f32 gives for TEXT: its bits, or the name of
    its refusal."""
    body = text[1:] if text.startswith('-') else text
    lowered = body.lower()
    if lowered in ('inf', 'infinity'):
        value = float('-inf' if text.startswith('-') else 'inf')
        return 'bits', bits_of(value, single)
    if lowered == 'nan':
        return 'bits', 0x7fc00000 if single else 0x7ff8000000000000
    if not re.fullmatch(r'-?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?', text):
        return 'invalid', 0
    form = big_oracle.SINGLE if single else big_oracle.DOUBLE
    mantissa, _, power = body.lower().partition('e')
    exponent = int(power) if power else 0
    if exponent > 100000 or exponent < -100000:
        nonzero = any(digit not in '0.' for digit in mantissa)
        if not nonzero:
            bits = 0
        elif exponent > 0:
            return 'overflow', 0
        else:
            bits = 0
    else:
        bits = big_oracle.float_bits(Fraction(mantissa) * Fraction(10) ** exponent, form)
    infinity = 0x7f800000 if single else 0x7ff0000000000000
    if bits == infinity:
        return 'overflow', 0
    if text.startswith('-'):
        bits |= 0x80000000 if single else 0x8000000000000000
    return 'bits', bits


PARSE_TEXTS = [
    '0', '-0', '0.0', '-0.0', '00000.00000', '1', '1.', '.5', '-.5', '1e0', '1E+2', '1e-2',
    '1.5e10', '2.2250738585072011e-308', '2.2250738585072012e-308', '4.9e-324', '5e-324',
    '2.4703282292062327e-324', '2.4703282292062328e-324', '2.47032822920623272e-324',
    '1.7976931348623157e308', '1.7976931348623158e308', '1.7976931348623159e308',
    '1e308', '1e309', '1e-400', '1e-324', '1e-323', '9007199254740993', '9007199254740992.5',
    '123456789012345678901234567890', '0.1', '0.2', '0.3', '3.141592653589793238462643383279',
    'inf', '-inf', 'Infinity', '-INFINITY', 'nan', 'NaN', '-nan', '',
    '-', '+1', ' 1', '1 ', '1_000', '0x10', '1e', '1e+', '1.2.3', 'e5', '.', '-.', '1..',
    '1e1000000000000', '1e-1000000000000', '0e1000000000', '0.' + '0' * 400 + '1e400',
    '1' + '0' * 400 + 'e-400', '7.' + '9' * 20, '1.000000000000000111022302462515654042363166809',
    '1.0000000000000001110223024625156540423631668090820312500000000001',
    '1.00000000000000011102230246251565404236316680908203125', 'infinite', 'nana', 'in',
    '3.4028235e38', '1.4e-45', '7e-46', '16777217', '0.000000000000000000000000000001',
]

KINDS = {'bits': 0, 'invalid': 1, 'overflow': 2}


def parse_program():
    draw = random.Random(2222)
    texts = list(PARSE_TEXTS) + halfway_texts(draw, 120)
    for _ in range(200):
        digits = ''.join(draw.choice('0123456789') for _ in range(draw.randrange(1, 30)))
        texts.append(digits + 'e' + str(draw.randrange(-345, 320)))
    cases = []
    for item in texts:
        kind, bits = parsed(item)
        cases.append('    (written: %s, kind: %d, bits: 0x%016x)' % (
            landin_text(item), KINDS[kind], bits))
    generator = big_oracle.Generator(2223)
    draws = 5000
    hash_value = FNV_START
    for _ in range(draws):
        count = 1 + generator.next() % 25
        digits = ''.join(str(generator.next() % 10) for _ in range(count))
        power = int(generator.next() % 660) - 340
        kind, bits = parsed(digits + 'e' + str(power))
        word = bits if kind == 'bits' else (MASK if kind == 'overflow' else 1)
        hash_value = fnv(hash_value, struct.pack('<Q', word))
    return HEADER + """\
--  core/text's float parsing against Python's exact fractions: each
--  record of `cases` is text and what `parse_f64` gives for it, its bits
--  or its refusal, decimals halfway between neighbouring f64s and either
--  side of them among them; the FNV-1a digest of what it gives for
--  {draws} decimals drawn from core/random's xoshiro256** seeded with
--  2223; and the shortest text of as many drawn f64s, read back as the
--  same bits.  It exits 42 when every one agrees.
import core/cmp
import core/random
import core/text

case_value: type = struct
    written: utf8
    kind: u8
    bits: u64
end case_value

cases: [{count}]case_value = [
{cases}
]
{common}
public main: () -> (code: i32) =
    code = 1
    for case in cases do
        mut kind: u8 = 0
        value: f64 = text.parse_f64(text.bytes(case.written)) else (problem)
            kind = if problem == text.invalid_number then 1 else 2 end if
            0.0
        end
        return when kind <> case.kind
        return when kind == 0 and bits_64(value) <> case.bits
    end for
    mut source := random.new(2223)
    mut hash: u64 = 0xcbf29ce484222325
    mut storage: [64]u8 = zeroed
    for draw in usize(0)..<{draws} do
        _ = draw
        count: u64 = 1 + random.next(source) % 25
        mut line := text.over(storage[0..<64])
        for digit in u64(0)..<count do
            _ = digit
            text.append_byte(line, u8('0') + u8(random.next(source) % 10))
                else begin return end
        end for
        power: i64 = i64(random.next(source) % 660) - 340
        text.append_byte(line, u8('e')) else begin return end
        text.append_i64(line, power) else begin return end
        mut word: u64 = 0
        mut refused: bool = false
        value: f64 = text.parse_f64(text.used(line)) else (problem)
            refused = true
            word = if problem == text.number_overflow then 0xffffffffffffffff else 1 end if
            0.0
        end
        if not refused then word = bits_64(value) end if
        mut bytes: [8]u8 = zeroed
        for at in usize(0)..<8 do
            bytes[at] = u8((word >> u64(8 * at)) & 0xff)
        end for
        hash = mixed(hash, bytes[0..<8])
    end for
    return when hash <> 0x{digest:016x}
    for draw in usize(0)..<{draws} do
        _ = draw
        bits: u64 = shaped(random.next(source))
        value: f64 = float_64(bits)
        mut line := text.over(storage[0..<64])
        text.append_f64(line, value) else begin return end
        back: f64 = text.parse_f64(text.used(line)) else begin return end
        if bits & 0x7ff0000000000000 <> 0x7ff0000000000000 then
            return when bits_64(back) <> bits
        end if
    end for
    code = 42
end main
""".format(draws=draws, count=len(cases), cases=',\n'.join(cases), common=COMMON,
           digest=hash_value)


def single_program():
    cases = []
    for bits in edge_bits_32():
        value = from_bits(bits, single=True)
        cases.append('    (bits: 0x%08x, literal: %s, point: %s, exponent: %s)' % (
            bits, landin_text(literal_text(value, single=True)),
            landin_text(fixed_text(value, 9)), landin_text(places_text(value, 5))))
    texts = ['0.1', '1e-45', '7e-46', '7.1e-46', '1.4e-45', '3.4028235e38', '3.4028236e38',
             '3.40282357e38', '16777217', '16777216.5', '16777217.000001', '1.17549435e-38',
             '1.1754942e-38', '0.3', '1e39', '1e-50', 'inf', 'nan', '-0', '+1', '1.5e',
             '8.589973e9', '8.589974e9', '1.00000005960464477539062500001',
             '1.000000059604644775390625', '1.0000000596046447753906249999']
    draw = random.Random(2224)
    for _ in range(150):
        digits = ''.join(draw.choice('0123456789') for _ in range(draw.randrange(1, 14)))
        texts.append(digits + 'e' + str(draw.randrange(-55, 42)))
    readings = []
    for item in texts:
        kind, bits = parsed(item, single=True)
        readings.append('    (written: %s, kind: %d, bits: 0x%08x)' % (
            landin_text(item), KINDS[kind], bits))
    generator = big_oracle.Generator(2225)
    draws = 8000
    hash_value = FNV_START
    for _ in range(draws):
        value = from_bits(shaped_32(generator.next_u32()), single=True)
        places = generator.next() % 12
        line = (literal_text(value, single=True) + ' '
                + literal_text(value, single=True, exponent=True) + ' '
                + fixed_text(value, places) + '\n')
        hash_value = fnv(hash_value, line.encode('ascii'))
    return HEADER + """\
--  core/text's `f32` text against Python: `append_f32`, `{{:.9}}` and
--  `{{:.5e}}` for each record of `cases`, the shortest digits found by
--  exact rounding and the rounded ones by C's printf of the `f32`'s exact
--  value; each record of `readings` and what `parse_f32` gives, rounded
--  once from the decimal; and the FNV-1a digest of `{{}}`, `{{:e}}` and
--  `append_f32_fixed` for {draws} f32s and places drawn from core/random's
--  xoshiro256** seeded with 2225.  It exits 42 when every one agrees.
import core/cmp
import core/random
import core/text

case_value: type = struct
    bits: u32
    literal: utf8
    point: utf8
    exponent: utf8
end case_value

reading_value: type = struct
    written: utf8
    kind: u8
    bits: u32
end reading_value

cases: [{count}]case_value = [
{cases}
]

readings: [{reading_count}]reading_value = [
{readings}
]
{common}
public main: () -> (code: i32) =
    code = 1
    mut storage: [128]u8 = zeroed
    for case in cases do
        value: f32 = float_32(case.bits)
        mut line := text.over(storage[0..<128])
        text.append_f32(line, value) else begin return end
        return when not same(text.used(line), case.literal)
        text.clear(line)
        text.format(line, "{{:.9}}", [any(addr value)]) else begin return end
        return when not same(text.used(line), case.point)
        text.clear(line)
        text.format(line, "{{:.5e}}", [any(addr value)]) else begin return end
        return when not same(text.used(line), case.exponent)
    end for
    for reading in readings do
        mut kind: u8 = 0
        value: f32 = text.parse_f32(text.bytes(reading.written)) else (problem)
            kind = if problem == text.invalid_number then 1 else 2 end if
            0.0
        end
        return when kind <> reading.kind
        return when kind == 0 and bits_32(value) <> reading.bits
    end for
    mut source := random.new(2225)
    mut hash: u64 = 0xcbf29ce484222325
    for draw in usize(0)..<{draws} do
        _ = draw
        value: f32 = float_32(shaped_32(random.next_u32(source)))
        places: usize = usize(random.next(source) % 12)
        mut line := text.over(storage[0..<128])
        text.format(line, "{{}} {{:e}} ", [any(addr value), any(addr value)])
            else begin return end
        text.append_f32_fixed(line, value, places) else begin return end
        text.append_byte(line, u8('\\n')) else begin return end
        hash = mixed(hash, text.used(line))
    end for
    return when hash <> 0x{digest:016x}
    code = 42
end main
""".format(draws=draws, count=len(cases), cases=',\n'.join(cases), common=COMMON,
           reading_count=len(readings), readings=',\n'.join(readings), digest=hash_value)


FIXTURE_SUMMARIES = {
    'float-text-shortest': "core/text's shortest f64 text against Python's repr, as a literal"
                           " and in the exponent form, over edge values and ten thousand"
                           " drawn ones",
    'float-text-rounded': "core/text's f64 text rounded to places after the point or after"
                          " the first digit against C's printf, over edge values at two"
                          " precisions and sixty drawn values and places",
    'float-text-parse': "core/text's f64 parsing against Python's exact fractions, halfway"
                        " decimals and refusals included, and the shortest text of drawn"
                        " f64s read back",
    'float-text-single': "core/text's f32 text, shortest and rounded, and f32 parsing rounded"
                         " once from the decimal, against Python's exact arithmetic and C's"
                         " printf",
}

PROGRAMS = {
    'float-text-shortest': shortest_program,
    'float-text-rounded': rounded_program,
    'float-text-parse': parse_program,
    'float-text-single': single_program,
}

META = """\
class: runtime
profiles: standard
summary: {summary}
program: main.ldn
root: ../../../../..
status: 42
targets: {targets}
constructs: 0150, 0290
"""


def fixture_meta(name):
    targets = TARGETS.replace('cortex-m0, ', '') if name in FIRMWARE_LIMITED else TARGETS
    return META.format(summary=FIXTURE_SUMMARIES[name], targets=targets)


def command_fixtures(arguments, refine):
    stale = []
    for name, make in PROGRAMS.items():
        if arguments.names and name not in arguments.names:
            continue
        directory = FIXTURES / name
        with tempfile.TemporaryDirectory() as scratch:
            source = Path(scratch) / 'main.ldn'
            source.write_text(make(), encoding='utf-8')
            formatted = subprocess.run([str(refine), 'fmt', str(source)], capture_output=True,
                                       text=True, check=False)
            if formatted.returncode != 0:
                raise Failure('refine fmt refused %s:\n%s' % (name, formatted.stderr))
            program = source.read_text(encoding='utf-8')
        meta = fixture_meta(name)
        if arguments.check:
            for file, wanted in (('main.ldn', program), ('fixture.meta', meta)):
                path = directory / file
                if not path.exists() or path.read_text(encoding='utf-8') != wanted:
                    stale.append(name)
                    break
            continue
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'main.ldn').write_text(program, encoding='utf-8')
        (directory / 'fixture.meta').write_text(meta, encoding='utf-8')
        print(directory.relative_to(ROOT))
    if stale:
        print('not current: %s: run `python3 scripts/float_text.py fixtures`'
              % ', '.join(stale), file=sys.stderr)
        return 1
    return 0


def checked_lines(lines):
    """How many of drawn.ldn's LINES disagree with Python and C, and the
    first few that do."""
    refused = bits_of(-1.0)
    bad = []
    for line in lines:
        parts = line.split()
        bits = int(parts[0], 16)
        value = from_bits(bits)
        if is_nan(value) or math.isinf(value):
            continue
        shortest, fixed, exponent = parts[1:4]
        places = len(fixed.split('.')[1]) if '.' in fixed else 0
        ok = [shortest, fixed, exponent] == [literal_text(value), fixed_text(value, places),
                                            places_text(value, places)]
        ok = ok and int(parts[4], 16) == bits
        for got, written in ((parts[5], fixed), (parts[6], exponent)):
            kind, want = parsed(written)
            ok = ok and int(got, 16) == (want if kind == 'bits' else refused)
        if not ok:
            bad.append(line.strip()[:300])
    return bad


def command_drawn(arguments, refine):
    """drawn.ldn's values checked line by line, in parallel."""
    with tempfile.TemporaryDirectory() as scratch:
        program = Path(scratch) / 'drawn'
        subprocess.run([str(refine), 'compile', '--optimize', 'speed', '--library',
                        str(ROOT), str(DRAWN), '-o', str(program)], check=True)
        done = subprocess.run([str(program), str(arguments.count)], capture_output=True,
                              text=True, check=True)
    lines = done.stdout.splitlines()
    step = max(1, len(lines) // max(1, arguments.jobs))
    chunks = [lines[at:at + step] for at in range(0, len(lines), step)]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=arguments.jobs) as pool:
        results = list(pool.map(checked_lines, chunks))
    bad = [line for result in results for line in result]
    print('checked %d failed %d' % (len(lines), len(bad)))
    for line in bad[:10]:
        print('failed: ' + line)
    return 0 if not bad and len(lines) == arguments.count else 1


def command_exhaustive(arguments, refine):
    """Every f32 in slices: each slice's verdict and the whole's."""
    output = Path(arguments.output) if arguments.output else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    total = 1 << 32
    step = total // arguments.parts
    bounds = [(at * step, total if at == arguments.parts - 1 else (at + 1) * step)
              for at in range(arguments.parts)]
    with tempfile.TemporaryDirectory() as scratch:
        program = Path(scratch) / 'exhaustive'
        subprocess.run([str(refine), 'compile', '--optimize', 'speed', '--library',
                        str(ROOT), str(EXHAUSTIVE), '-o', str(program)], check=True)
        started = time.monotonic()

        def run(bound):
            done = subprocess.run([str(program), str(bound[0]), str(bound[1])],
                                  capture_output=True, text=True, check=False)
            return bound, done.returncode, done.stdout

        failed = 0
        checked = 0
        lines = []
        with ThreadPoolExecutor(max_workers=arguments.jobs) as pool:
            for bound, code, text in pool.map(run, bounds):
                last = text.strip().splitlines()[-1] if text.strip() else ''
                words = last.split()
                if len(words) == 4 and words[0] == 'checked':
                    checked += int(words[1])
                    failed += int(words[3])
                else:
                    failed += 1
                if code != 0 or text.count('failed 0x'):
                    lines.append('%#010x..%#010x: %s' % (bound[0], bound[1], text.strip()))
        seconds = time.monotonic() - started
    summary = {'checked': checked, 'failed': failed, 'parts': arguments.parts,
               'seconds': round(seconds, 1), 'failures': lines}
    print(json.dumps(summary, indent=2))
    if output:
        (output / 'exhaustive.json').write_text(json.dumps(summary, indent=2) + '\n')
    return 0 if failed == 0 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    lane_refine.argument(parser, required=False, environment=True)
    commands = parser.add_subparsers(dest='command', required=True)
    table = commands.add_parser('tables', help='write core/text/powers.ldn')
    table.add_argument('--check', action='store_true',
                       help='say whether the file is current, writing nothing')
    written = commands.add_parser('fixtures', help='write the float-text-* fixtures')
    written.add_argument('names', nargs='*')
    written.add_argument('--check', action='store_true',
                         help='say whether they are current, writing nothing')
    drawn = commands.add_parser('drawn', help='check drawn f64s against Python and C')
    drawn.add_argument('--count', type=int, default=1000000)
    drawn.add_argument('--jobs', type=int, default=os.cpu_count() or 1)
    every = commands.add_parser('exhaustive', help='check every f32')
    every.add_argument('--parts', type=int, default=256,
                       help='the slices the bit patterns are run in')
    every.add_argument('--jobs', type=int, default=os.cpu_count() or 1,
                       help='how many slices run at once')
    every.add_argument('--output', help='a directory for exhaustive.json')
    arguments = parser.parse_args()
    try:
        if arguments.command == 'tables':
            return command_tables(arguments)
        refine = arguments.refine or default_refine()
        if arguments.command == 'fixtures':
            return command_fixtures(arguments, refine)
        if arguments.command == 'drawn':
            return command_drawn(arguments, refine)
        if arguments.command == 'exhaustive':
            return command_exhaustive(arguments, refine)
    except Failure as failure:
        print('float_text: %s' % failure, file=sys.stderr)
        return 1
    return 2


if __name__ == '__main__':
    sys.exit(main())
