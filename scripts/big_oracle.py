#!/usr/bin/env python3
"""core/big against Python's integers and fractions: the fixtures, and the timing.

    python3 scripts/big_oracle.py fixtures [NAME...]
    python3 scripts/big_oracle.py time [--most LIMBS] [--spend SECONDS]

`fixtures` writes the `big-*` runtime fixtures: programs whose tables
hold operands and the results Python's own arbitrary-precision integers
and `fractions.Fraction` give for them, an implementation that shares no
code with core/big, and which exit 42 when core/big gives every one, on
every target a runtime fixture runs on.  Operands too long for a table
are drawn inside the program from core/random's xoshiro256**, which this
script draws alike, and their results compared by a 64-bit FNV-1a digest
of their limbs.  compiler/tests/big/README.md says what each covers.

`time` compiles compiler/tests/big/timing.ldn at `--optimize speed` and
runs it on this host: the nanoseconds a multiplication of two numbers of
n limbs takes, and a division of 2n limbs by n, from one limb to a
million bits.  The programs are compiled with `--refine`, $LANDIN_REFINE,
or the refine this checkout built last.
"""

import argparse
from fractions import Fraction
import math
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import lane_refine  # noqa: E402

FIXTURES = ROOT / 'compiler/tests/fixtures/runtime'
TIMING = ROOT / 'compiler/tests/big/timing.ldn'

#  Every target a runtime fixture runs on; the Cortex-M, RV32 and Xtensa
#  firmware lanes take theirs from compiler/tests/cortex-m/corpus.json.
TARGETS = ('linux-x86-64, linux-arm64, darwin-arm64, freebsd-x86-64, '
           'freebsd-arm64, linux-rv64, cortex-m0, windows-x86-64, '
           'windows-arm64')

#  The fixtures whose image overflows the Cortex-M0 reference's 32 KiB at
#  some profile, which compiler/tests/cortex-m/corpus.json records as a
#  profile limit with the measured sizes, and which therefore leave
#  cortex-m0 out of their targets: the lane still runs every profile that
#  fits, and mps2-an500 every profile.
FIRMWARE_LIMITED = {
    'big-limbs', 'big-limbs-products', 'big-integer-products', 'big-integer-quotients',
    'big-integer-powers', 'big-integer-roots', 'big-integer-modular', 'big-integer-bits',
    'big-integer-conversion', 'big-integer-text', 'big-rational', 'big-rational-products',
    'big-rational-floats', 'big-rational-text',
}

MASK = (1 << 64) - 1


class Failure(Exception):
    """A refusal to report on one line."""


class Generator:
    """core/random's xoshiro256**, seeded through splitmix64 as random.new
    seeds it, drawing next_u32 as the upper half of next."""

    def __init__(self, seed):
        state = seed & MASK
        words = []
        for _ in range(4):
            state = (state + 0x9e3779b97f4a7c15) & MASK
            z = state
            z = ((z ^ (z >> 30)) * 0xbf58476d1ce4e5b9) & MASK
            z = ((z ^ (z >> 27)) * 0x94d049bb133111eb) & MASK
            words.append(z ^ (z >> 31))
        self.s = words

    @staticmethod
    def rotate(value, count):
        return ((value << count) | (value >> (64 - count))) & MASK

    def next(self):
        s = self.s
        result = self.rotate((s[1] * 5) & MASK, 7) * 9 & MASK
        t = (s[1] << 17) & MASK
        s[2] ^= s[0]
        s[3] ^= s[1]
        s[1] ^= s[2]
        s[0] ^= s[3]
        s[2] ^= t
        s[3] = self.rotate(s[3], 45)
        return result

    def next_u32(self):
        return self.next() >> 32


def limbs(value, count=None):
    """The limbs of the natural VALUE, least significant first, COUNT of
    them when given and otherwise as many as it needs."""
    out = []
    while value:
        out.append(value & 0xffffffff)
        value >>= 32
    if count is not None:
        if len(out) > count:
            raise Failure('%d limbs do not fit %d' % (len(out), count))
        out += [0] * (count - len(out))
    return out


def number(words):
    return sum(word << (32 * at) for at, word in enumerate(words))


def digest(words):
    """FNV-1a over 32-bit words, as the fixtures compute it."""
    value = 0xcbf29ce484222325
    for word in words:
        value = ((value ^ word) * 0x100000001b3) & MASK
    return value


def digest_text(text):
    """FNV-1a over bytes, 32 bits."""
    value = 0x811c9dc5
    for byte in text.encode('ascii'):
        value = ((value ^ byte) * 0x01000193) & 0xffffffff
    return value


def signed(value):
    """A signed number as the fixtures read one: its length with the sign
    in the top bit, then its magnitude's limbs."""
    words = limbs(abs(value))
    return [len(words) | (0x80000000 if value < 0 else 0)] + words


def natural(words):
    return [len(words)] + list(words)


#  Rounding a rational to a binary format: its significand's bits with the
#  hidden one, and its least and greatest normal exponents.
DOUBLE = (53, -1022, 1023, 11)
SINGLE = (24, -126, 127, 8)


def float_bits(value, form):
    """The bits of the float of FORM nearest the rational VALUE, ties to
    even, overflow to infinity, the sign of a zero the value's."""
    precision, least, most, field = form
    width = precision + field
    sign = 1 << (width - 1) if value < 0 else 0
    value = abs(Fraction(value))
    if value == 0:
        return sign
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    if Fraction(2) ** exponent > value:
        exponent -= 1
    if Fraction(2) ** (exponent + 1) <= value:
        exponent += 1
    exponent = max(exponent, least)
    unit = Fraction(2) ** (exponent - precision + 1)
    scaled = value / unit
    whole = scaled.numerator // scaled.denominator
    rest = scaled - whole
    if rest > Fraction(1, 2) or (rest == Fraction(1, 2) and whole % 2 == 1):
        whole += 1
    if whole == 1 << precision:
        whole >>= 1
        exponent += 1
    infinity = ((1 << field) - 1) << (precision - 1)
    if exponent > most:
        return sign | infinity
    if whole < 1 << (precision - 1):
        return sign | whole
    return sign | ((exponent - least + 1) << (precision - 1)) | (whole - (1 << (precision - 1)))


def float_value(bits, form):
    """The rational a float's bits hold, or None for an infinity or NaN."""
    precision, least, most, field = form
    width = precision + field
    negative = bits >> (width - 1)
    biased = (bits >> (precision - 1)) & ((1 << field) - 1)
    fraction = bits & ((1 << (precision - 1)) - 1)
    if biased == (1 << field) - 1:
        return None
    if biased == 0:
        value = Fraction(fraction) * Fraction(2) ** (least - precision + 1)
    else:
        value = Fraction(fraction | (1 << (precision - 1))) * Fraction(2) ** (biased + least - precision)
    return -value if negative else value


def check_rounding():
    """The f64 rounding against Python's own float of a fraction, which
    rounds correctly, before a table relies on it."""
    draw = random.Random(7)
    for _ in range(2000):
        value = Fraction(draw.getrandbits(draw.randint(1, 200)) + 1,
                         draw.getrandbits(draw.randint(1, 200)) + 1)
        value *= Fraction(2) ** draw.randint(-1200, 1100)
        try:
            expected = struct.unpack('<Q', struct.pack('<d', float(value)))[0]
        except OverflowError:
            expected = 0x7ff0000000000000
        if float_bits(value, DOUBLE) != expected:
            raise Failure('rounding disagrees with Python at %s' % value)


def landin_array(name, words):
    """A u32 array value NAME of WORDS, wrapped at 76 columns."""
    items = ['0x%08x' % word for word in words] or ['0x00000000']
    lines, line = [], '    '
    for item in items:
        piece = item + ', '
        if len(line) + len(piece) > 76:
            lines.append(line.rstrip())
            line = '    '
        line += piece
    lines.append(line.rstrip().rstrip(','))
    return '%s: [%d]u32 = [\n%s]\n' % (name, len(items), '\n'.join(lines))


# ---------------------------------------------------------------- limbs

def limb_cases(draw):
    """The records of the limb layer's table: an operation, two naturals,
    a limb, the expected limbs and the expected word."""
    records = []

    def record(op, a, b, p, r, w):
        records.append([op] + natural(a) + natural(b) + [p] + natural(r) + [w])

    def any_limbs(count):
        kind = draw.randrange(4)
        if kind == 0:
            return [0xffffffff] * count
        if kind == 1:
            return [draw.getrandbits(32) for _ in range(count)]
        if kind == 2:
            return [draw.choice((0, 1, 0x80000000, 0xffffffff)) for _ in range(count)]
        words = [draw.getrandbits(32) for _ in range(count)]
        if count:
            words[-1] = draw.choice((0, 1, 0xffffffff))
        return words

    sizes = (0, 1, 2, 4)
    for la in sizes:
        for lb in sizes:
            a, b = any_limbs(la), any_limbs(lb)
            long = max(la, lb)
            total = number(a) + number(b)
            record(1, a, b, 0, limbs(total & ((1 << 32 * long) - 1), long), total >> (32 * long))
            if la >= lb:
                difference = number(a) - number(b)
                record(2, a, b, 0, limbs(difference % (1 << 32 * la), la), 1 if difference < 0 else 0)
                record(21, a, b, 0, limbs(total & ((1 << 32 * la) - 1), la), total >> (32 * la))
                record(22, a, b, 0, limbs(difference % (1 << 32 * la), la), 1 if difference < 0 else 0)
            order = (number(a) > number(b)) - (number(a) < number(b)) + 1
            record(12, a, b, 0, [], order)
    for la in (0, 1, 4):
        for p in (0, 0xffffffff, draw.getrandbits(32) | 1):
            a = any_limbs(la)
            value = number(a)
            span = 1 << (32 * la)
            record(3, a, [], p, limbs((value + p) % span, la), (value + p) >> (32 * la))
            record(4, a, [], p, limbs((value - p) % span, la), 1 if value < p else 0)
            product = value * p
            record(5, a, [], p, limbs(product % span, la), product >> (32 * la))
            record(26, a, [], p, limbs(product % span, la), product >> (32 * la))
            base = any_limbs(la)
            added = number(base) + product
            record(6, a, base, p, limbs(added % span, la), added >> (32 * la))
            taken = number(base) - product
            record(7, a, base, p, limbs(taken % span, la),
                   (-(taken // span)) if taken < 0 else 0)
            shift = p % 32
            shifted = value << shift
            record(8, a, [], shift, limbs(shifted % span, la), shifted >> (32 * la))
            record(23, a, [], shift, limbs(shifted % span, la), shifted >> (32 * la))
            out = (value << 32 >> shift) & 0xffffffff if shift else 0
            record(9, a, [], shift, limbs(value >> shift, la), out)
            record(24, a, [], shift, limbs(value >> shift, la), out)
            if p:
                q, r = divmod(value, p)
                record(10, a, [], p, limbs(q, la), r)
                record(25, a, [], p, limbs(q, la), r)
                record(11, a, [], p, [], r)
            record(13, a, [], 0, [], len(limbs(value)))
    for p in (0, 1, 2, 3, 0x80000000, 0x00010000, 0xffffffff, 0x00f00000):
        record(14, [], [], p, [], 32 - p.bit_length())
        record(15, [], [], p, [], 32 if p == 0 else (p & -p).bit_length() - 1)
    for la in (0, 1, 2, 5, 12):
        for _ in range(1):
            a = any_limbs(la)
            record(18, a, [], 0, [], digest_text(str(number(a))))
            record(19, a, [], 0, [], digest_text(format(number(a), 'x')))
    return records


SHAPES = [(1, 1), (2, 1), (1, 3), (3, 3), (5, 2), (47, 47), (48, 48), (49, 48),
          (63, 61), (96, 96), (149, 149), (150, 150), (151, 151), (160, 160),
          (200, 199), (320, 160), (300, 151), (250, 60), (151, 3), (320, 48)]
QUOTIENTS = [(1, 1), (2, 1), (2, 2), (3, 2), (5, 3), (10, 3), (40, 20), (100, 50),
             (320, 160), (300, 151), (200, 1), (64, 63)]


def limb_room():
    """The scratch the limb fixture's longest call needs."""
    return max([multiply_scratch(la, lb) for la, lb in SHAPES]
               + [la + lb + 1 for la, lb in QUOTIENTS] + [64])


def seeded_cases():
    """Products and quotients of operands core/random draws: an operation,
    a seed, two lengths and a pattern, then the digests expected."""
    records = []
    for at, (la, lb) in enumerate(SHAPES):
        for pattern in (0, 3):
            seed = 1000 + at * 4 + pattern
            a, b = operands(seed, la, lb, pattern)
            product = limbs(number(a) * number(b), la + lb)
            records.append([1, seed, la, lb, pattern] + split(digest(product)) + [0, 0])
    for at, (la, lb) in enumerate(QUOTIENTS):
        for pattern in (0, 3):
            seed = 2000 + at * 4 + pattern
            a, b = operands(seed, la, lb, pattern)
            if b[-1] == 0:
                b[-1] = 1
            q, r = divmod(number(a), number(b))
            records.append([2, seed, la, lb, pattern] + split(digest(limbs(q, la - lb + 1)))
                           + split(digest(limbs(r, lb))))
    return records


def operands(seed, la, lb, pattern):
    source = Generator(seed)
    a = [source.next_u32() for _ in range(la)]
    b = [source.next_u32() for _ in range(lb)]
    if pattern & 1:
        a = [0xffffffff] * la
    if pattern & 2:
        b = [0xffffffff] * lb
    return a, b


def thresholds():
    """The lengths core/big/limbs/multiply.ldn changes method at."""
    text = (ROOT / 'core/big/limbs/multiply.ldn').read_text(encoding='utf-8')
    found = {}
    for name in ('karatsuba_from', 'toom_from'):
        for line in text.splitlines():
            if line.startswith(name + ': usize = '):
                found[name] = int(line.split('=')[1])
    return found['karatsuba_from'], found['toom_from']


def balanced_scratch(count, karatsuba, toom):
    """multiply.ldn's balanced_scratch, step for step."""
    if count < karatsuba:
        return 0
    if count < toom:
        half = (count + 1) // 2
        below = max(balanced_scratch(half, karatsuba, toom),
                    balanced_scratch(count - half, karatsuba, toom))
        return 4 * half + max(below, 1)
    third = (count + 2) // 3
    below = max(balanced_scratch(third + 1, karatsuba, toom),
                balanced_scratch(third, karatsuba, toom),
                balanced_scratch(count - 2 * third, karatsuba, toom))
    return 8 * third + 8 + below


def multiply_scratch(left, right):
    """multiply.ldn's multiply_scratch, step for step."""
    karatsuba, toom = thresholds()
    long, short = max(left, right), min(left, right)
    if short < karatsuba:
        return 0
    if long == short:
        return balanced_scratch(short, karatsuba, toom)
    below = balanced_scratch(short, karatsuba, toom)
    if long % short:
        below = max(below, multiply_scratch(short, long % short))
    return 2 * short + below


def split(value):
    return [value & 0xffffffff, value >> 32]


COMMON = '''\
--  FNV-1a over 32-bit words, the digest the generator computes alike.
digest: (values: []u32) -> (hash: u64) =
    hash = 0xcbf29ce484222325
    for value in values do
        hash = (hash ^ u64(value)) *% 0x100000001b3
    end for
end digest

--  FNV-1a over bytes, 32 bits.
digest_text: (values: []u8) -> (hash: u32) =
    hash = 0x811c9dc5
    for value in values do
        hash = (hash ^ u32(value)) *% 0x01000193
    end for
end digest_text

--  Whether two runs of limbs are the same limbs.
same: (left: []u32, right: []u32) -> (yes: bool) =
    yes = lenof left == lenof right
    return when not yes
    for value, at in left do
        if value <> right[at] then
            yes = false
            return
        end if
    end for
end same
'''




# ---------------------------------------------------------------- integers

def integer_cases(draw):
    """The records of the integer table: an operation, three signed
    operands, a 64-bit parameter, two expected integers and a word."""
    records = []

    def record(op, a=0, b=0, c=0, p=0, r=0, s=0, w=0):
        records.append([op] + signed(a) + signed(b) + signed(c) + [p & 0xffffffff, p >> 32]
                       + signed(r) + signed(s) + [w])

    def any_value(count):
        if count == 0:
            return 0
        kind = draw.randrange(4)
        if kind == 0:
            value = (1 << (32 * count)) - 1
        elif kind == 1:
            value = 1 << (32 * count - 1)
        else:
            value = draw.getrandbits(32 * count) | 1
        return -value if draw.randrange(2) else value

    def truncating(a, b):
        q = abs(a) // abs(b)
        q = q if (a < 0) == (b < 0) else -q
        return q, a - q * b

    def root(value, degree):
        size = abs(value)
        x = 0
        if size:
            x = 1 << (-(-size.bit_length() // degree))
            while True:
                y = ((degree - 1) * x + size // x ** (degree - 1)) // degree
                if y >= x:
                    break
                x = y
        return -x if value < 0 else x

    sizes = (0, 1, 2, 4)
    for la in sizes:
        for lb in sizes:
            a, b = any_value(la), any_value(lb)
            record(1, a, b, r=a + b)
            record(2, a, b, r=a - b)
            record(3, a, b, r=a * b)
            record(0x101, a, b, r=a + b)
            record(0x102, a, b, r=a - b)
            record(0x103, a, b, r=a * b)
            if b:
                q, rest = truncating(a, b)
                record(4, a, b, r=q, s=rest)
                record(0x104, a, b, r=q, s=rest)
                record(5, a, b, r=a // b, s=a % b)
                record(0x105, a, b, r=a // b, s=a % b)
            record(8, a, b, r=math.gcd(a, b))
            record(0x108, a, b, r=math.gcd(a, b))
            if la != 4 and lb != 4:
                record(11, a, b, r=a & b)
                record(12, a, b, r=a | b)
                record(13, a, b, r=a ^ b)
            if la == lb:
                record(0x10b, a, b, r=a & b)
                record(0x10d, a, b, r=a ^ b)
            record(19, a, b, w=(a > b) - (a < b) + 1)
            modulus = abs(b) + 1
            try:
                record(9, a, modulus, r=pow(a, -1, modulus))
            except ValueError:
                record(9, a, modulus, w=1)
            exponent = abs(any_value(draw.randrange(3)))
            record(10, a, exponent, modulus, r=pow(a, exponent, modulus))
            record(0x10a, a, exponent, modulus, r=pow(a, exponent, modulus))
    for la in (0, 1, 2, 3):
        for _ in range(2):
            a = any_value(la)
            record(14, a, r=~a)
            for p in (0, 33, draw.randrange(100)):
                record(15, a, p=p, r=a << p)
                record(16, a, p=p, r=a >> p)
                record(17, a, p=p, w=(a >> p) & 1)
            p = draw.randrange(70)
            record(0x10f, a, p=p, r=a << p)
            record(0x110, a, p=p, r=a >> p)
            record(18, a, w=abs(a).bit_length())
            record(20, a, w=(a > 0) - (a < 0) + 1)
            record(21, a, r=-a)
            record(22, a, r=abs(a))
            for p in (0, 1, 2, 5):
                record(6, a, p=p, r=a ** p)
            for p in (1, 2, 3, 7):
                if a >= 0 or p % 2:
                    record(7, a, p=p, r=root(a, p))
            record(29, a, w=digest_text(str(a)))
            record(30, a, w=digest_text(('-' if a < 0 else '') + format(abs(a), 'x')))
    machine = [0, 1, -1, (1 << 63) - 1, 1 << 63, -(1 << 63), -(1 << 63) - 1,
               (1 << 64) - 1, 1 << 64, -(1 << 64), any_value(1), any_value(3)]
    for a in machine:
        if -(1 << 63) <= a < (1 << 63):
            record(23, a, p=a & MASK)
        else:
            record(23, a, w=1)
        if 0 <= a < (1 << 64):
            record(24, a, p=a)
        else:
            record(24, a, w=1)
    doubles = [0, 1, (1 << 53) + 1, (1 << 53) + 3, (1 << 54) + 2,
               ((1 << 53) + 1) << 100, (((1 << 53) + 1) << 100) + 1,
               (1 << 1024) - (1 << 970), (1 << 1024) - (1 << 970) - 1,
               1 << 1024, any_value(2), any_value(4)]
    for a in doubles + [-value for value in doubles[2:6]]:
        record(25, a, p=float_bits(a, DOUBLE))
    singles_of = [(1 << 24) + 1, (1 << 24) + 3, ((1 << 24) + 1) << 200,
                  (((1 << 24) + 1) << 200) + 1, (1 << 128) - (1 << 103),
                  (1 << 128) - (1 << 103) - 1, 3 << 1100, any_value(3)]
    for a in singles_of + [-value for value in singles_of[:3]]:
        record(26, a, p=float_bits(a, SINGLE))
    floats = [0x0000000000000000, 0x8000000000000000, 0x3ff0000000000000,
              0xbff8000000000000, 0x4330000000000001, 0x7fefffffffffffff,
              0xffefffffffffffff, 0x0000000000000001, 0x3fe0000000000000,
              0xc3e0000000000000, 0x7ff0000000000000, 0xfff8000000000000,
              0x7ff0000000000001]
    floats += [draw.getrandbits(64) for _ in range(5)]
    for bits in floats:
        value = float_value(bits, DOUBLE)
        if value is None:
            record(27, p=bits, w=1)
        else:
            record(27, p=bits, r=int(value))
    singles = [0x00000000, 0x80000000, 0x3f800000, 0xbfc00000, 0x4b800001,
               0x7f7fffff, 0xff7fffff, 0x00000001, 0x7f800000, 0xffc00000]
    singles += [draw.getrandbits(32) for _ in range(5)]
    for bits in singles:
        value = float_value(bits, SINGLE)
        if value is None:
            record(28, p=bits, w=1)
        else:
            record(28, p=bits, r=int(value))
    return records


def integer_seeded():
    """Products, quotients and roots of large operands drawn in the
    program: an operation, a seed, two lengths, then the digests."""
    records = []
    for at, (la, lb) in enumerate([(160, 151), (151, 160), (96, 50), (60, 60)]):
        seed = 3000 + at
        a, b = operands(seed, la, lb, 0)
        value = number(a) * number(b)
        records.append([1, seed, la, lb] + split(digest(limbs(value))) + [0, 0])
        if b[-1] == 0:
            b[-1] = 1
        q, r = divmod(number(a), number(b))
        records.append([2, seed, la, lb] + split(digest(limbs(q))) + split(digest(limbs(r))))
    return records




# ---------------------------------------------------------------- rationals

def rational_cases(draw):
    """The records of the rational table: an operation, two rationals as
    signed numerators and denominators, a 64-bit parameter, the expected
    rational and a word."""
    records = []

    def record(op, x=Fraction(0), y=Fraction(0), p=0, r=Fraction(0), w=0, raw=None):
        top, bottom = raw if raw else (x.numerator, x.denominator)
        records.append([op] + signed(top) + signed(bottom) + signed(y.numerator)
                       + signed(y.denominator) + [p & 0xffffffff, (p >> 32) & 0xffffffff]
                       + signed(r.numerator) + signed(r.denominator) + [w])

    def any_value():
        top = draw.getrandbits(draw.choice((1, 8, 33, 70))) * draw.choice((1, -1))
        bottom = draw.getrandbits(draw.choice((1, 8, 33, 70))) + 1
        return Fraction(top, bottom)

    for _ in range(8):
        x, y = any_value(), any_value()
        record(2, x, y, r=x + y)
        record(3, x, y, r=x - y)
        record(4, x, y, r=x * y)
        record(0x102, x, y, r=x + y)
        record(0x104, x, y, r=x * y)
        if y:
            record(5, x, y, r=x / y)
            record(0x105, x, y, r=x / y)
        record(7, x, y, w=(x > y) - (x < y) + 1)
        record(8, x, r=Fraction(math.floor(x)))
        record(9, x, r=Fraction(math.trunc(x)))
        for p in (0, 1, 3, -1, -2):
            if x or p >= 0:
                record(6, x, p=p & MASK, r=x ** p)
        record(14, x, w=digest_text(str(x)))
        record(15, x, w=(x > 0) - (x < 0) + 1)
        record(16, x, r=-x)
    for top, bottom in [(6, 4), (-6, 4), (6, -4), (-6, -4), (0, 5), (0, -5),
                        (12, 1), (7, 7), (1 << 100, 1 << 98), (3 << 70, 9 << 40)]:
        record(1, p=0, r=Fraction(top, bottom), raw=(top, bottom))
    hard = [Fraction(1, 3), Fraction(2, 3), Fraction(1, 10), Fraction(-1, 7),
            Fraction(1, 1 << 1075), Fraction(3, 1 << 1076), Fraction(1, 1 << 1074),
            Fraction((1 << 53) + 1, 1 << 1100), Fraction((1 << 1024) - (1 << 970)),
            Fraction((1 << 1024) - (1 << 970) - 1), Fraction(1, 1 << 150),
            Fraction(3, 1 << 151), Fraction((1 << 24) + 1, 1 << 160),
            Fraction((1 << 128) - (1 << 103)), Fraction(10 ** 30 + 1, 10 ** 30),
            Fraction(-(1 << 60) - 1, 3), Fraction((1 << 53) + 1, 2), Fraction(0)]
    hard += [any_value() for _ in range(4)]
    for x in hard:
        record(10, x, p=float_bits(x, DOUBLE))
        record(11, x, p=float_bits(x, SINGLE))
    floats = [0x0000000000000000, 0x8000000000000000, 0x3ff0000000000000,
              0xbfb999999999999a, 0x0000000000000001, 0x7fefffffffffffff,
              0x7ff0000000000000, 0x7ff8000000000000]
    floats += [draw.getrandbits(64) for _ in range(6)]
    for bits in floats:
        value = float_value(bits, DOUBLE)
        record(12, p=bits, r=value or Fraction(0), w=1 if value is None else 0)
    singles = [0x00000000, 0x3dcccccd, 0x00000001, 0x7f7fffff, 0xff800000]
    singles += [draw.getrandbits(32) for _ in range(4)]
    for bits in singles:
        value = float_value(bits, SINGLE)
        record(13, p=bits, r=value or Fraction(0), w=1 if value is None else 0)
    return records




HEADER = '''\
--  Generated by scripts/big_oracle.py: edit that and run
--  `python3 scripts/big_oracle.py fixtures`, never this file.
'''


def table_words(records):
    return [word for record in records for word in record]


# ---------------------------------------------------------------- limb programs

LIMB_ARMS = {
    1: 'got = limbs.add(out[0..<long], a, b)',
    2: 'got = limbs.subtract(out[0..<la], a, b)',
    3: 'got = limbs.add_limb(out[0..<la], a, p)',
    4: 'got = limbs.subtract_limb(out[0..<la], a, p)',
    5: 'got = limbs.multiply_limb(out[0..<la], a, p)',
    6: 'limbs.copy(out, b)\ngot = limbs.add_multiply_limb(out[0..<la], a, p)',
    7: 'limbs.copy(out, b)\ngot = limbs.subtract_multiply_limb(out[0..<la], a, p)',
    8: 'got = limbs.shift_left(out[0..<la], a, p)',
    9: 'got = limbs.shift_right(out[0..<la], a, p)',
    10: 'got = limbs.divide_limb(out[0..<la], a, p)',
    11: 'got = limbs.remainder_limb(a, p)',
    12: 'order := limbs.compare(a, b)\n'
        'got = if order == cmp.less then 0 elsif order == cmp.equal then 1 else 2 end if',
    13: 'got = u32(limbs.significant(a))',
    14: 'got = limbs.leading_zeros(p)',
    15: 'got = limbs.trailing_zeros(p)',
    16: 'limbs.multiply(out[0..<la + lb], a, b, room[0..<64])',
    17: 'limbs.divide(out[0..<la - lb + 1], out[la - lb + 1..<la + 1], a, b,\n'
        '             room[0..<64])',
    18: 'written: usize = limbs.write_decimal(digits[0..<121], a, room[0..<64])\n'
        'back: usize = (limbs.read_decimal(out, digits[0..<written]) else 9999)\n'
        'yes = back == limbs.significant(a) and same(out[0..<back], a[0..<back])\n'
        '      and digest_text(digits[0..<written]) == word\n'
        'return',
    19: 'written: usize = limbs.write_hex(digits[0..<121], a)\n'
        'back: usize = (limbs.read_hex(out, digits[0..<written]) else 9999)\n'
        'yes = back == limbs.significant(a) and same(out[0..<back], a[0..<back])\n'
        '      and digest_text(digits[0..<written]) == word\n'
        'return',
    21: 'limbs.copy(out, a)\ngot = limbs.add(out[0..<la], out[0..<la], b)',
    22: 'limbs.copy(out, a)\ngot = limbs.subtract(out[0..<la], out[0..<la], b)',
    23: 'limbs.copy(out, a)\ngot = limbs.shift_left(out[0..<la], out[0..<la], p)',
    24: 'limbs.copy(out, a)\ngot = limbs.shift_right(out[0..<la], out[0..<la], p)',
    25: 'limbs.copy(out, a)\ngot = limbs.divide_limb(out[0..<la], out[0..<la], p)',
    26: 'limbs.copy(out, a)\ngot = limbs.multiply_limb(out[0..<la], out[0..<la], p)',
}


def chain(arms, ops, indent):
    """An if-elsif chain over `op`, one arm for each of OPS."""
    pad = ' ' * indent
    lines = []
    for at, op in enumerate(sorted(ops)):
        lines.append('%s%s op == 0x%x then' % (pad, 'if' if at == 0 else 'elsif', op))
        for line in arms[op].split('\n'):
            lines.append(pad + '    ' + line)
    lines.append(pad + 'end if')
    return '\n'.join(lines)


def limb_table_program(records):
    ops = {record[0] for record in records}
    return HEADER + '''\
--  core/big/limbs against Python's integers: each record of `cases` holds
--  an operation, its operands and the result Python gives.  The program
--  exits 42 when every result agrees, and otherwise 1 for the first table
--  that did not and 2 for the refusals.  It uses no allocator: its numbers
--  live in the module's storage, as a firmware program's would.
import core/big/limbs
import core/cmp
import core/text

mut left: [16]u32 = zeroed
mut right: [16]u32 = zeroed
mut result: [48]u32 = zeroed
mut expected: [48]u32 = zeroed
mut room: [64]u32 = zeroed
mut digits: [121]u8 = zeroed

{common}
{cases}
--  A natural from `table` at `at` into `into`, `at` moved past it.
take: (table: []u32, inout at: usize, into: []mut u32) -> (count: usize) =
    count = usize(table[at])
    inc at
    for slot, index in into[0..<count] do
        slot = table[at + index]
    end for
    at = at + count
end take

--  Whether the operation `op` on `a`, `b` and `p` gives the limbs `want`
--  and the word `word`.
agrees: (op: u32, a: []u32, b: []u32, p: u32, want: []u32, word: u32)
        -> (yes: bool) =
    yes = false
    la: usize = lenof a
    lb: usize = lenof b
    long: usize = if la > lb then la else lb end if
    mut got: u32 = 0
    out: []mut u32 = result[0..<48]
{chain}
    yes = got == word and same(out[0..<lenof want], want)
end agrees

--  Whether every record of `cases` agrees.
run_cases: () -> (ok: bool) =
    ok = true
    mut at: usize = 0
    while at < lenof cases do
        op: u32 = cases[at]
        inc at
        la: usize = take(cases, at, left[0..<16])
        lb: usize = take(cases, at, right[0..<16])
        p: u32 = cases[at]
        inc at
        lr: usize = take(cases, at, expected[0..<48])
        word: u32 = cases[at]
        inc at
        if not agrees(op, left[0..<la], right[0..<lb], p, expected[0..<lr], word) then
            ok = false
        end if
    end while
end run_cases

--  Whether `source` is refused as decimal, or as hexadecimal.
refused: (source: []u8, decimal: bool) -> (yes: bool) =
    yes = false
    out: []mut u32 = result[0..<8]
    if decimal then
        count: usize = limbs.read_decimal(out, source) else (problem)
            yes = problem == text.invalid_number
            return
        end
        _ = count
    else
        count: usize = limbs.read_hex(out, source) else (problem)
            yes = problem == text.invalid_number
            return
        end
        _ = count
    end if
end refused

--  Text that is not digits is refused.
refusals: () -> (ok: bool) =
    ok = refused("", true) and refused("-1", true) and refused("1 2", true)
         and refused("9a", true) and refused("", false) and refused("0x1", false)
         and refused("fg", false)
end refusals

public main: () -> (code: i32) =
    code = 42
    if not run_cases() then
        code = 1
    elsif not refusals() then
        code = 2
    end if
end main
'''.format(common=COMMON, cases=landin_array('cases', table_words(records)),
           chain=chain(LIMB_ARMS, ops, 4))


def limb_seeded_program(records, room):
    return HEADER + '''\
--  core/big/limbs's multiplication and division against Python's
--  integers, on operands core/random draws, which the generator draws
--  alike: each record of `seeded` holds an operation, a seed, two lengths
--  and a pattern, operands of all one bits where it says so, and the
--  digests of the product or the quotient and remainder Python gives.
--  The lengths sit on either side of the Karatsuba and Toom-3 thresholds.
--  The program exits 42 when every result agrees, and 1 otherwise.  It
--  uses no allocator: its numbers live in the module's storage.
import core/big/limbs
import core/random

mut left: [320]u32 = zeroed
mut right: [320]u32 = zeroed
mut result: [640]u32 = zeroed
mut room: [{room}]u32 = zeroed

{common}
{seeded}
--  Draw limbs from `source` into `into`, or all ones.
draw: (inout source: random.generator, into: []mut u32, ones: bool) -> none =
    for slot in into do
        slot = random.next_u32(source)
        if ones then slot = 0xffffffff end if
    end for
end draw

--  Whether every record of `seeded` agrees.
run_seeded: () -> (ok: bool) =
    ok = true
    mut at: usize = 0
    while at < lenof seeded do
        op: u32 = seeded[at]
        mut source := random.new(u64(seeded[at + 1]))
        la: usize = usize(seeded[at + 2])
        lb: usize = usize(seeded[at + 3])
        pattern: u32 = seeded[at + 4]
        first: u64 = u64(seeded[at + 5]) | (u64(seeded[at + 6]) << 32)
        second: u64 = u64(seeded[at + 7]) | (u64(seeded[at + 8]) << 32)
        at = at + 9
        draw(source, left[0..<la], pattern & 1 == 1)
        draw(source, right[0..<lb], pattern & 2 == 2)
        if op == 1 then
            limbs.multiply(result[0..<la + lb], left[0..<la], right[0..<lb],
                           room[0..<{room}])
            if digest(result[0..<la + lb]) <> first then ok = false end if
        else
            if right[lb - 1] == 0 then right[lb - 1] = 1 end if
            count: usize = la - lb + 1
            limbs.divide(result[0..<count], result[count..<count + lb],
                         left[0..<la], right[0..<lb], room[0..<{room}])
            if digest(result[0..<count]) <> first
              or digest(result[count..<count + lb]) <> second then
                ok = false
            end if
        end if
    end while
end run_seeded

public main: () -> (code: i32) =
    code = 42
    if not run_seeded() then
        code = 1
    end if
end main
'''.format(common=COMMON.split('--  FNV-1a over bytes')[0], room=room,
           seeded=landin_array('seeded', table_words(records)))


# ---------------------------------------------------------------- integer programs

INTEGER_ARMS = {
    1: 'try big.add(r, memory, a, b)',
    2: 'try big.subtract(r, memory, a, b)',
    3: 'try big.multiply(r, memory, a, b)',
    4: 'try big.divide_truncating(r, s, memory, a, b)',
    5: 'try big.divide_floor(r, s, memory, a, b)',
    6: 'try big.power(r, memory, a, p)',
    7: 'try big.root(r, memory, a, u32(p))',
    8: 'try big.gcd(r, memory, a, b)',
    9: 'big.inverse_modulo(r, memory, a, b) else (problem)\n'
       '    match problem\n'
       '        big.not_invertible: w = 1\n'
       '        mem.out_of_memory: fail mem.out_of_memory\n'
       '    end match\n'
       'end',
    10: 'try big.power_modulo(r, memory, a, b, c)',
    11: 'try big.and_bits(r, memory, a, b)',
    12: 'try big.or_bits(r, memory, a, b)',
    13: 'try big.xor_bits(r, memory, a, b)',
    14: 'try big.complement(r, memory, a)',
    15: 'try big.shift_left(r, memory, a, usize(p))',
    16: 'try big.shift_right(r, memory, a, usize(p))',
    17: 'w = if big.bit(a, usize(p)) then 1 else 0 end if',
    18: 'w = u32(big.bit_length(a))',
    19: 'order := big.compare(a, b)\n'
        'w = if order == cmp.less then 0 elsif order == cmp.equal then 1 else 2 end if',
    20: 'w = u32(big.sign(a) + 1)',
    21: 'try big.set(r, memory, a)\nbig.negate(r)',
    22: 'try big.set(r, memory, a)\nbig.absolute(r)',
    23: 'value: i64 = big.to_i64(a) else (problem)\n'
        '    _ = problem\n'
        '    yes = word == 1\n'
        '    return\n'
        'end\n'
        'try big.set_i64(r, memory, value)\n'
        'bits: u64 = if value < 0 then 0 -% u64(-(value + 1)) -% 1\n'
        '            else u64(value) end if\n'
        'yes = word == 0 and bits == p and equals(r, a)\n'
        'return',
    24: 'value: u64 = big.to_u64(a) else (problem)\n'
        '    _ = problem\n'
        '    yes = word == 1\n'
        '    return\n'
        'end\n'
        'try big.set_u64(r, memory, value)\n'
        'yes = word == 0 and value == p and equals(r, a)\n'
        'return',
    25: 'got: f64 = big.to_f64(a)\n'
        'view: ptr u64 = ptr(usize(addr got))\n'
        'yes = view.val == p\n'
        'return',
    26: 'got: f32 = big.to_f32(a)\n'
        'view: ptr u32 = ptr(usize(addr got))\n'
        'yes = u64(view.val) == p\n'
        'return',
    27: 'bits: u64 = p\n'
        'value: ptr f64 = ptr(usize(addr bits))\n'
        'big.set_f64(r, memory, value.val) else (problem)\n'
        '    match problem\n'
        '        big.not_finite: w = 1\n'
        '        mem.out_of_memory: fail mem.out_of_memory\n'
        '    end match\n'
        'end',
    28: 'bits: u32 = u32(p)\n'
        'value: ptr f32 = ptr(usize(addr bits))\n'
        'big.set_f32(r, memory, value.val) else (problem)\n'
        '    match problem\n'
        '        big.not_finite: w = 1\n'
        '        mem.out_of_memory: fail mem.out_of_memory\n'
        '    end match\n'
        'end',
    29: '(hash: hash, back: back) := try text_of(a, memory, true)\n'
        'yes = hash == word and back\n'
        'return',
    30: '(hash: hash, back: back) := try text_of(a, memory, false)\n'
        'yes = hash == word and back\n'
        'return',
}
for kind, call in ((1, 'add(r, memory, r, b)'), (2, 'subtract(r, memory, r, b)'),
                   (3, 'multiply(r, memory, r, b)'),
                   (4, 'divide_truncating(r, s, memory, r, b)'),
                   (5, 'divide_floor(r, s, memory, r, b)'), (8, 'gcd(r, memory, r, b)'),
                   (10, 'power_modulo(r, memory, r, b, c)'),
                   (11, 'and_bits(r, memory, r, b)'), (13, 'xor_bits(r, memory, r, b)'),
                   (15, 'shift_left(r, memory, r, usize(p))'),
                   (16, 'shift_right(r, memory, r, usize(p))')):
    INTEGER_ARMS[0x100 + kind] = 'try big.set(r, memory, a)\ntry big.' + call

TEXT_OF = '''
--  The digest of `value`'s text in base 10 or 16, and whether reading it
--  back gives `value`.
text_of: (provider: type is mem.allocator, value: big.integer,
          memory: provider, decimal: bool)
         -> (hash: u32, back: bool) ! mem.out_of_memory | text.invalid_number =
    mut out := text.over(buffer[0..<512])
    if decimal then
        try big.append_decimal(out, memory, value)
    else
        try big.append_hex(out, memory, value)
    end if
    hash = digest_text(text.used(out))
    mut read := big.new()
    if decimal then
        try big.parse_decimal(read, memory, text.used(out))
    else
        try big.parse_hex(read, memory, text.used(out))
    end if
    back = equals(read, value)
end text_of
'''

INTEGER_REFUSALS = '''
--  Text that does not spell an integer is refused, the destination left
--  as it was.
refused: (provider: type is mem.allocator, inout into: big.integer,
          memory: provider, source: []u8, decimal: bool) -> (yes: bool) =
    mut seen: bool = false
    if decimal then
        big.parse_decimal(into, memory, source) else (problem)
            seen = problem == text.invalid_number
        end
    else
        big.parse_hex(into, memory, source) else (problem)
            seen = problem == text.invalid_number
        end
    end if
    kept: i64 = (big.to_i64(into) else 0)
    yes = seen and kept == 7
end refused

refusals: () -> (ok: bool) =
    ok = false
    mut space: arena.space = zeroed
    memory := arena.over_unchecked(space, addr backing[0], {backing})
    mut value := big.new()
    big.set_i64(value, memory, 7) else (problem)
        _ = problem
        return
    end
    ok = refused(value, memory, "", true) and refused(value, memory, "-", true)
         and refused(value, memory, "+1", true) and refused(value, memory, " 1", true)
         and refused(value, memory, "12x", true) and refused(value, memory, "1-", true)
         and refused(value, memory, "0x10", false) and refused(value, memory, "g", false)
         and refused(value, memory, "--1", false)
end refusals
'''

INTEGER_SEEDED = '''
--  `count` limbs drawn from `source` made the integer `into`.
draw: (provider: type is mem.allocator, inout source: random.generator,
       inout into: big.integer, memory: provider, count: usize)
      -> none ! mem.out_of_memory =
    for slot in drawn[0..<count] do
        slot = random.next_u32(source)
    end for
    try big.set_limbs(into, memory, drawn[0..<count], false)
end draw

--  Whether one record of `seeded`, from `at`, agrees.
seeded_agrees: (provider: type is mem.allocator, at: usize, memory: provider)
               -> (yes: bool) ! mem.out_of_memory =
    mut source := random.new(u64(seeded[at + 1]))
    first: u64 = u64(seeded[at + 4]) | (u64(seeded[at + 5]) << 32)
    second: u64 = u64(seeded[at + 6]) | (u64(seeded[at + 7]) << 32)
    mut a := big.new()
    mut b := big.new()
    mut r := big.new()
{seeded_s}    try draw(source, a, memory, usize(seeded[at + 2]))
    count: usize = usize(seeded[at + 3])
    try draw(source, b, memory, count)
{seeded_step}
end seeded_agrees

--  Whether every record of `seeded` agrees.
run_seeded: () -> (ok: bool) =
    ok = true
    mut at: usize = 0
    while at < lenof seeded do
        mut space: arena.space = zeroed
        memory := arena.over_unchecked(space, addr backing[0], {backing})
        agreed := seeded_agrees(at, memory) else false
        if not agreed then ok = false end if
        at = at + 8
    end while
end run_seeded
'''


SEEDED_STEPS = {
    1: '''    try big.multiply(r, memory, a, b)
    yes = digest(big.limbs_of(r)) == first
    _ = second''',
    2: '''    if drawn[count - 1] == 0 then
        drawn[count - 1] = 1
        try big.set_limbs(b, memory, drawn[0..<count], false)
    end if
    try big.divide_floor(r, s, memory, a, b)
    yes = digest(big.limbs_of(r)) == first and digest(big.limbs_of(s)) == second''',
}


def integer_program(name, records, seeded, refusals, summary):
    ops = {record[0] for record in records}
    texts = bool(ops & {29, 30}) or refusals
    backing = 7168 if seeded else 4096
    imports = ['core/arena', 'core/big', 'core/cmp', 'core/mem']
    if seeded:
        imports.append('core/random')
    if texts:
        imports.append('core/text')
    storage = ['mut backing: [%d]u8 = zeroed' % backing]
    if ops & {29, 30}:
        storage.append('mut buffer: [512]u8 = zeroed')
    if seeded:
        storage.append('mut drawn: [330]u32 = zeroed')
    failures = 'mem.out_of_memory' + (' | text.invalid_number' if ops & {29, 30} else '')
    common = COMMON if texts else COMMON.replace(
        COMMON[COMMON.index('--  FNV-1a over bytes'):COMMON.index('--  Whether two runs')], '')
    if not seeded:
        common = common.replace(
            common[common.index('--  FNV-1a over 32-bit'):common.index('--  FNV-1a over bytes')
                   if texts else common.index('--  Whether two runs')], '')
    steps = ['if not run_cases() then\n        code = 1']
    if seeded:
        steps.append('elsif not run_seeded() then\n        code = 2')
    if refusals:
        steps.append('elsif not refusals() then\n        code = 3')
    program = HEADER + '''\
--  {summary}
--  Each record of `cases` holds an operation, three signed operands, a
--  parameter and the results Python's integers give; an operation numbered
--  from 0x100 writes its result over its first operand's own value.  Every
--  record runs in an arena that starts empty, and the program exits 42
--  when every result agrees, 1 when a record does not{seeded_note}{refusal_note}.
{imports}

{storage}

{common}
{cases}
{seeded_table}
--  A signed number from `table` at `at` into `into`, `at` moved past it.
take: (provider: type is mem.allocator, table: []u32, inout at: usize,
       inout into: big.integer, memory: provider)
      -> none ! mem.out_of_memory =
    header: u32 = table[at]
    count: usize = usize(header & 0x7fffffff)
    inc at
    try big.set_limbs(into, memory, table[at..<at + count], header >> 31 == 1)
    at = at + count
end take

--  Whether `value` is the signed number `want`.
equals: (value: big.integer, want: big.integer) -> (yes: bool) =
    yes = big.compare(value, want) == cmp.equal
          and same(big.limbs_of(value), big.limbs_of(want))
end equals
{text_of}
--  Whether one record, from `at`, agrees.
agrees: (provider: type is mem.allocator, inout at: usize, memory: provider)
        -> (yes: bool) ! {failures} =
    yes = false
    op: u32 = cases[at]
    inc at
    mut a := big.new()
    mut b := big.new()
    mut c := big.new()
    try take(cases, at, a, memory)
    try take(cases, at, b, memory)
    try take(cases, at, c, memory)
    p: u64 = u64(cases[at]) | (u64(cases[at + 1]) << 32)
    at = at + 2
    mut want := big.new()
    mut also := big.new()
    try take(cases, at, want, memory)
    try take(cases, at, also, memory)
    word: u32 = cases[at]
    inc at
    {r_mut}r := big.new()
    {s_mut}s := big.new()
    {w_mut}w: u32 = 0
{chain}
    yes = w == word and equals(r, want) and equals(s, also)
end agrees

--  Whether every record of `cases` agrees, each in an empty arena.
run_cases: () -> (ok: bool) =
    ok = true
    mut at: usize = 0
    while at < lenof cases do
        mut space: arena.space = zeroed
        memory := arena.over_unchecked(space, addr backing[0], {backing})
        agreed := agrees(at, memory) else false
        if not agreed then
            ok = false
            return
        end if
    end while
end run_cases
{seeded_code}{refusal_code}
public main: () -> (code: i32) =
    code = 42
    {steps}
    end if
end main
'''.format(summary=summary, imports='\n'.join('import ' + m for m in imports),
           storage='\n'.join(storage), common=common,
           cases=landin_array('cases', table_words(records)),
           seeded_table=landin_array('seeded', table_words(seeded)) if seeded else '',
           seeded_note=', 2 when a drawn product or quotient does not' if seeded else '',
           refusal_note=' and 3 when text that is no number is not refused' if refusals else '',
           text_of=TEXT_OF if ops & {29, 30} else '', failures=failures,
           chain=chain(INTEGER_ARMS, ops, 4), backing=backing,
           r_mut='' if ops <= {17, 18, 19, 20, 25, 26, 29, 30} else 'mut ',
           s_mut='mut ' if ops & {4, 5, 0x104, 0x105} else '',
           w_mut='mut ' if ops & {9, 17, 18, 19, 20, 27, 28} else '',
           seeded_code=INTEGER_SEEDED.format(
               backing=backing, seeded_step=SEEDED_STEPS[seeded[0][0]] if seeded else '',
               seeded_s='    mut s := big.new()\n' if seeded and seeded[0][0] == 2 else '',
               second_used='') if seeded else '',
           refusal_code=INTEGER_REFUSALS.format(backing=backing) if refusals else '',
           steps='\n    '.join(steps))
    return program


# ---------------------------------------------------------------- rational programs

RATIONAL_ARMS = {
    1: 'try big.rational_set(r, memory, x)',
    2: 'try big.rational_add(r, memory, x, y)',
    3: 'try big.rational_subtract(r, memory, x, y)',
    4: 'try big.rational_multiply(r, memory, x, y)',
    5: 'try big.rational_divide(r, memory, x, y)',
    6: 'exponent: i64 = if p >> 63 == 1 then -i64(0 -% p) else i64(p) end if\n'
       'try big.rational_power(r, memory, x, exponent)',
    7: 'order := try big.rational_compare(x, y, memory)\n'
       'w = if order == cmp.less then 0 elsif order == cmp.equal then 1 else 2 end if',
    8: 'try big.rational_floor(whole, memory, x)\n'
       'try big.rational_set_integer(r, memory, whole)',
    9: 'try big.rational_truncate(whole, memory, x)\n'
       'try big.rational_set_integer(r, memory, whole)',
    10: 'got: f64 = try big.rational_to_f64(x, memory)\n'
        'view: ptr u64 = ptr(usize(addr got))\n'
        'yes = view.val == p\n'
        'return',
    11: 'got: f32 = try big.rational_to_f32(x, memory)\n'
        'view: ptr u32 = ptr(usize(addr got))\n'
        'yes = u64(view.val) == p\n'
        'return',
    12: 'bits: u64 = p\n'
        'value: ptr f64 = ptr(usize(addr bits))\n'
        'big.rational_set_f64(r, memory, value.val) else (problem)\n'
        '    match problem\n'
        '        big.not_finite: w = 1\n'
        '        mem.out_of_memory: fail mem.out_of_memory\n'
        '    end match\n'
        'end',
    13: 'bits: u32 = u32(p)\n'
        'value: ptr f32 = ptr(usize(addr bits))\n'
        'big.rational_set_f32(r, memory, value.val) else (problem)\n'
        '    match problem\n'
        '        big.not_finite: w = 1\n'
        '        mem.out_of_memory: fail mem.out_of_memory\n'
        '    end match\n'
        'end',
    14: 'mut out := text.over(buffer[0..<256])\n'
        'try big.rational_append(out, memory, x)\n'
        'try big.rational_parse(r, memory, text.used(out))\n'
        'back := try equals(r, x, memory)\n'
        'yes = digest_text(text.used(out)) == word and back\n'
        'return',
    15: 'w = u32(big.rational_sign(x) + 1)',
    16: 'try big.rational_set(r, memory, x)\nbig.rational_negate(r)',
    0x102: 'try big.rational_set(r, memory, x)\ntry big.rational_add(r, memory, r, y)',
    0x104: 'try big.rational_set(r, memory, x)\ntry big.rational_multiply(r, memory, r, y)',
    0x105: 'try big.rational_set(r, memory, x)\ntry big.rational_divide(r, memory, r, y)',
}

RATIONAL_REFUSALS = '''
--  Text that does not spell a rational is refused, the destination left
--  as it was.
refused: (provider: type is mem.allocator, inout into: big.rational,
          memory: provider, source: []u8) -> (yes: bool) =
    yes = false
    big.rational_parse(into, memory, source) else (problem)
        yes = problem == text.invalid_number and big.rational_sign(into) == 1
        return
    end
end refused

refusals: () -> (ok: bool) =
    ok = false
    mut space: arena.space = zeroed
    memory := arena.over_unchecked(space, addr backing[0], 4096)
    mut value := big.rational_new()
    big.rational_parse(value, memory, "5/3") else (problem)
        _ = problem
        return
    end
    ok = refused(value, memory, "1/0") and refused(value, memory, "1/-2")
         and refused(value, memory, "1/") and refused(value, memory, "/2")
         and refused(value, memory, "1//2") and refused(value, memory, "a")
         and refused(value, memory, "")
end refusals
'''


def rational_program(records, refusals, summary):
    ops = {record[0] for record in records}
    texts = 14 in ops or refusals
    imports = ['core/arena', 'core/big', 'core/cmp', 'core/mem']
    if texts:
        imports.append('core/text')
    storage = ['mut backing: [4096]u8 = zeroed']
    if 14 in ops:
        storage.append('mut buffer: [256]u8 = zeroed')
    failures = 'mem.out_of_memory' + (' | text.invalid_number' if 14 in ops else '')
    common = COMMON[COMMON.index('--  FNV-1a over bytes'):COMMON.index('--  Whether two runs')] \
        if 14 in ops else ''
    steps = ['if not run_cases() then\n        code = 1']
    if refusals:
        steps.append('elsif not refusals() then\n        code = 2')
    return HEADER + '''\
--  {summary}
--  Each record of `cases` holds an operation, two rationals as signed
--  numerators and denominators, a parameter and the result Python's
--  fractions give; an operation numbered from 0x100 writes its result over
--  its first operand's own value.  Every record runs in an arena that
--  starts empty, and the program exits 42 when every result agrees, 1 when
--  a record does not{refusal_note}.
{imports}

{storage}

{common}
{cases}
--  A signed number from `cases` at `at` into `into`, `at` moved past it.
take: (provider: type is mem.allocator, inout at: usize,
       inout into: big.integer, memory: provider)
      -> none ! mem.out_of_memory =
    header: u32 = cases[at]
    count: usize = usize(header & 0x7fffffff)
    inc at
    try big.set_limbs(into, memory, cases[at..<at + count], header >> 31 == 1)
    at = at + count
end take

--  A rational from `cases` at `at`, put in lowest terms.
take_rational: (provider: type is mem.allocator, inout at: usize,
                inout into: big.rational, memory: provider)
               -> none ! mem.out_of_memory =
    mut top := big.new()
    mut bottom := big.new()
    try take(at, top, memory)
    try take(at, bottom, memory)
    try big.rational_set_ratio(into, memory, top, bottom)
end take_rational

--  Whether `value` is `want`, part for part.
equals: (provider: type is mem.allocator, value: big.rational,
         want: big.rational, memory: provider)
        -> (yes: bool) ! mem.out_of_memory =
    mut top := big.new()
    mut bottom := big.new()
    mut other_top := big.new()
    mut other_bottom := big.new()
    try big.rational_numerator(top, memory, value)
    try big.rational_denominator(bottom, memory, value)
    try big.rational_numerator(other_top, memory, want)
    try big.rational_denominator(other_bottom, memory, want)
    order := try big.rational_compare(value, want, memory)
    yes = big.compare(top, other_top) == cmp.equal
          and big.compare(bottom, other_bottom) == cmp.equal
          and order == cmp.equal
end equals

--  Whether one record, from `at`, agrees.
agrees: (provider: type is mem.allocator, inout at: usize, memory: provider)
        -> (yes: bool) ! {failures} =
    yes = false
    op: u32 = cases[at]
    inc at
    mut x := big.rational_new()
    mut y := big.rational_new()
    mut want := big.rational_new()
    mut r := big.rational_new()
{whole}    if op == 1 then
        --  The parts as written, not yet in lowest terms.
        mut top := big.new()
        mut bottom := big.new()
        try take(at, top, memory)
        try take(at, bottom, memory)
        try big.rational_set_ratio(x, memory, top, bottom)
    else
        try take_rational(at, x, memory)
    end if
    try take_rational(at, y, memory)
    p: u64 = u64(cases[at]) | (u64(cases[at + 1]) << 32)
    at = at + 2
    try take_rational(at, want, memory)
    word: u32 = cases[at]
    inc at
    {w_mut}w: u32 = 0
{chain}
    matches := try equals(r, want, memory)
    yes = w == word and matches
end agrees

--  Whether every record agrees, each in an empty arena.
run_cases: () -> (ok: bool) =
    ok = true
    mut at: usize = 0
    while at < lenof cases do
        mut space: arena.space = zeroed
        memory := arena.over_unchecked(space, addr backing[0], 4096)
        agreed := agrees(at, memory) else false
        if not agreed then
            ok = false
            return
        end if
    end while
end run_cases
{refusal_code}
public main: () -> (code: i32) =
    code = 42
    {steps}
    end if
end main
'''.format(summary=summary, imports='\n'.join('import ' + m for m in imports),
           storage='\n'.join(storage), common=common,
           cases=landin_array('cases', table_words(records)), failures=failures,
           chain=chain(RATIONAL_ARMS, ops, 4),
           whole='    mut whole := big.new()\n' if ops & {8, 9} else '',
           w_mut='mut ' if ops & {7, 12, 13, 15} else '',
           refusal_note=' and 2 when text that is no rational is not refused' if refusals else '',
           refusal_code=RATIONAL_REFUSALS if refusals else '',
           steps='\n    '.join(steps))


INTEGER_GROUPS = {
    'big-integer': ({1, 2, 19, 20, 21, 22, 0x101, 0x102}, set(), False,
                    "core/big's integers against Python's: sums, differences, "
                    "comparison, sign, negation and absolute value"),
    'big-integer-products': ({3, 0x103}, {1}, False,
                             "core/big's integers against Python's: products, and "
                             "products of drawn operands across the multiplication "
                             "thresholds"),
    'big-integer-quotients': ({4, 5, 0x104, 0x105}, {2}, False,
                              "core/big's integers against Python's: quotients and "
                              "remainders rounded toward zero and down, and those of "
                              "drawn operands"),
    'big-integer-powers': ({6}, set(), False,
                           "core/big's integers against Python's: powers"),
    'big-integer-roots': ({7}, set(), False,
                          "core/big's integers against Python's: integer roots"),
    'big-integer-gcd': ({8, 0x108}, set(), False,
                        "core/big's integers against Python's: the greatest common "
                        "divisor"),
    'big-integer-modular': ({9, 10, 0x10a}, set(), False,
                            "core/big's integers against Python's: the inverse modulo a "
                            "modulus and the power modulo one"),
    'big-integer-bits': ({11, 12, 13, 14, 15, 16, 17, 18, 0x10b, 0x10d, 0x10f, 0x110},
                         set(), False,
                         "core/big's integers against Python's: and, or, exclusive or and "
                         "complement in two's complement, shifts, single bits and bit "
                         "lengths"),
    'big-integer-conversion': ({23, 24, 25, 26, 27, 28}, set(), False,
                               "core/big's integers against Python's: to and from i64, u64, "
                               "f64 and f32, each float rounded once to nearest"),
    'big-integer-text': ({29, 30}, set(), True,
                         "core/big's integers against Python's: decimal and hexadecimal "
                         "text written and read back, and text that is no number refused"),
}

RATIONAL_GROUPS = {
    'big-rational': ({1, 2, 3, 7, 15, 16, 0x102}, False,
                     "core/big's rationals against Python's fractions: lowest terms, "
                     "sums, differences, comparison, sign and negation"),
    'big-rational-products': ({4, 5, 6, 8, 9, 0x104, 0x105}, False,
                              "core/big's rationals against Python's fractions: products, "
                              "quotients, powers, floor and truncation"),
    'big-rational-floats': ({10, 11, 12, 13}, False,
                            "core/big's rationals against Python's fractions: the nearest "
                            "f64 and f32, rounded once, and the exact values of floats"),
    'big-rational-text': ({14}, True,
                          "core/big's rationals against Python's fractions: text written, "
                          "read back and refused"),
}

FIXTURE_SUMMARIES = {
    'big-limbs': "core/big/limbs agrees with Python's integers on every operation of its "
                 "table, results written over an operand included, with no allocator",
    'big-limbs-products': "core/big/limbs's products and quotients of operands drawn from "
                          "core/random agree with Python's across the Karatsuba and Toom-3 "
                          "thresholds, with no allocator",
}
FIXTURE_SUMMARIES.update({name: group[-1] for name, group in INTEGER_GROUPS.items()})
FIXTURE_SUMMARIES.update({name: group[-1] for name, group in RATIONAL_GROUPS.items()})


def programs():
    """Each fixture's name and program text."""
    draw = random.Random(2213)
    check_rounding()
    result = {
        'big-limbs': limb_table_program(limb_cases(draw)),
        'big-limbs-products': limb_seeded_program(seeded_cases(), limb_room()),
    }
    integers = integer_cases(draw)
    for name, (ops, seeded, refusals, summary) in INTEGER_GROUPS.items():
        result[name] = integer_program(name, [r for r in integers if r[0] in ops],
                                       [r for r in integer_seeded() if r[0] in seeded],
                                       refusals, summary + '.')
    rationals = rational_cases(draw)
    for name, (ops, refusals, summary) in RATIONAL_GROUPS.items():
        result[name] = rational_program([r for r in rationals if r[0] in ops], refusals,
                                        summary + '.')
    return result


def default_refine():
    """The refine this checkout built last."""
    found = sorted(ROOT.glob('compiler/ada/build/*/*/bin/refine'),
                   key=lambda path: path.stat().st_mtime)
    if not found:
        raise Failure('no refine: build one with ./scripts/dev-build.sh, or name'
                      ' one with --refine')
    return found[-1]


def write_fixture(name, program, refine):
    directory = FIXTURES / name
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / 'main.ldn'
    source.write_text(program, encoding='utf-8')
    formatted = subprocess.run([str(refine), 'fmt', str(source)], capture_output=True,
                               text=True, check=False)
    if formatted.returncode != 0:
        raise Failure('refine fmt refused %s:\n%s' % (source, formatted.stderr))
    (directory / 'fixture.meta').write_text('''\
class: runtime
profiles: standard
summary: {summary}
program: main.ldn
root: ../../../../..
status: 42
targets: {targets}
constructs: 0150, 0290
'''.format(summary=FIXTURE_SUMMARIES[name],
           targets=TARGETS.replace('cortex-m0, ', '') if name in FIRMWARE_LIMITED
           else TARGETS), encoding='utf-8')
    return directory


def time(args, refine):
    """Compile timing.ldn for speed and run it on this host."""
    with tempfile.TemporaryDirectory() as scratch:
        program = Path(scratch) / 'timing'
        subprocess.run([str(refine), 'compile', '--optimize', 'speed', '--library', str(ROOT),
                        str(TIMING), '-o', str(program)], check=True)
        return subprocess.run([str(program), str(args.most), str(int(args.spend * 1e9))],
                              check=False).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    lane_refine.argument(parser, required=False, environment=True)
    commands = parser.add_subparsers(dest='command', required=True)
    fixtures = commands.add_parser('fixtures', help='write the big-* fixtures')
    fixtures.add_argument('names', nargs='*')
    timed = commands.add_parser('time', help='time multiplication and division')
    timed.add_argument('--most', type=int, default=31250,
                       help='the longest operand, in limbs: 31250 is a million bits')
    timed.add_argument('--spend', type=float, default=0.2,
                       help='the seconds each length is timed for, at least one run')
    args = parser.parse_args()
    try:
        refine = args.refine or default_refine()
        if args.command == 'time':
            return time(args, refine)
        known = programs()
        for name in args.names:
            if name not in known:
                raise Failure('no fixture is named %s' % name)
        for name in args.names or known:
            print(write_fixture(name, known[name], refine).relative_to(ROOT))
        return 0
    except Failure as failure:
        print('big_oracle: %s' % failure, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
