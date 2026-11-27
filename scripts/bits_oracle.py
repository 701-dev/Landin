#!/usr/bin/env python3
"""core/bits's bit operations at u32 and u64 against Python's integers.

    python3 scripts/bits_oracle.py [--refine REFINE]

Writes the runtime fixture `bits-oracle`: a program that draws its
operands from splitmix64, written out in the program so that it shares
no code with core/bits, shapes each into a random word, a single bit, a
single clear bit or a run of low ones, and folds every operation's
results at each width into a 64-bit FNV-1a digest.  This script draws
the same operands, computes each result with Python's integers, and
writes the digests into the program, which exits 42 when every one
agrees and 10 plus the operation's number, 30 plus it at u64, for the
first that does not.  The u8 and u16 widths need no oracle: the
`bits-every-u8` and `bits-every-u16` fixtures check every input against
bit-by-bit references in the program itself.
"""

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import lane_refine  # noqa: E402

FIXTURE = ROOT / 'compiler/tests/fixtures/runtime/bits-oracle'
MASK = (1 << 64) - 1
CASES = 2048
SEED = 0x5eed0b175
OPERATIONS = ('ones', 'leading_zeros', 'trailing_zeros', 'bit_length',
              'rotate_left', 'rotate_right', 'reverse_bytes', 'reverse_bits',
              'multiply_high', 'multiply_low', 'add_sum', 'add_carry',
              'subtract_difference', 'subtract_borrow')


class Failure(Exception):
    """A refusal to report on one line."""


class Splitmix:
    def __init__(self, seed):
        self.state = seed & MASK

    def next(self):
        self.state = (self.state + 0x9e3779b97f4a7c15) & MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xbf58476d1ce4e5b9) & MASK
        z = ((z ^ (z >> 27)) * 0x94d049bb133111eb) & MASK
        return z ^ (z >> 31)


def shaped(source, width):
    """One operand: as the program's `shaped` draws it."""
    mask = (1 << width) - 1
    draw = source.next()
    raw = source.next() & mask
    k = (draw >> 2) % width
    shape = draw & 3
    if shape == 0:
        return raw
    if shape == 1:
        return 1 << k
    if shape == 2:
        return ~(1 << k) & mask
    return raw >> k


def results(x, y, count, carry, width):
    mask = (1 << width) - 1
    length = x.bit_length()
    leading = width - length
    trailing = width if x == 0 else (x & -x).bit_length() - 1
    k = count % width
    left = ((x << k) | (x >> (width - k))) & mask
    right = ((x >> k) | (x << (width - k))) & mask
    swapped = int.from_bytes(x.to_bytes(width // 8, 'little'), 'big')
    mirrored = int(format(x, '0%db' % width)[::-1], 2)
    product = x * y
    total = x + y + carry
    difference = x - y - carry
    return (bin(x).count('1'), leading, trailing, length, left, right,
            swapped, mirrored, product >> width, product & mask,
            total & mask, int(total > mask), difference & mask,
            int(difference < 0))


def digests():
    source = Splitmix(SEED)
    found = {}
    for width in (32, 64):
        hashes = [0xcbf29ce484222325] * len(OPERATIONS)
        for _ in range(CASES):
            x = shaped(source, width)
            y = shaped(source, width)
            c = source.next()
            count = c & 0xff
            carry = (c >> 8) & 1
            for index, value in enumerate(results(x, y, count, carry, width)):
                hashes[index] = ((hashes[index] ^ value) * 0x100000001b3) & MASK
        found[width] = hashes
    return found


def landin_digests(name, hashes):
    rows = ',\n'.join('    0x%016x' % value for value in hashes)
    return 'expected_%s: [%d]u64 = [\n%s\n]\n' % (name, len(hashes), rows)


def width_routine(name, item, mask, steps):
    """The program's fold over one width's cases."""
    return '''\
--  The digest of every operation's results over the {item} cases.
{name}: (inout source: u64, inout hashes: [14]u64) -> none =
    for case in usize(0)..<{cases} do
        _ = case
        x: {item} = {item}(shaped(source, {steps}) & {mask})
        y: {item} = {item}(shaped(source, {steps}) & {mask})
        c: u64 = splitmix(source)
        count: u32 = u32(c & 0xff)
        carry: bool = (c >> 8) & 1 == 1
        (high: high, low: low) := bits.multiply_wide(x, y)
        (sum: sum, carry_out: carry_out) := bits.add_carry(x, y, carry)
        (difference: difference, borrow_out: borrow_out) :=
            bits.subtract_borrow(x, y, carry)
        fold(hashes[0], u64(bits.ones(x)))
        fold(hashes[1], u64(bits.leading_zeros(x)))
        fold(hashes[2], u64(bits.trailing_zeros(x)))
        fold(hashes[3], u64(bits.bit_length(x)))
        fold(hashes[4], u64(bits.rotate_left(x, count)))
        fold(hashes[5], u64(bits.rotate_right(x, count)))
        fold(hashes[6], u64(bits.reverse_bytes(x)))
        fold(hashes[7], u64(bits.reverse_bits(x)))
        fold(hashes[8], u64(high))
        fold(hashes[9], u64(low))
        fold(hashes[10], u64(sum))
        fold(hashes[11], if carry_out then 1 else 0 end if)
        fold(hashes[12], u64(difference))
        fold(hashes[13], if borrow_out then 1 else 0 end if)
    end for
end {name}
'''.format(name=name, item=item, mask=mask, steps=steps, cases=CASES)


def program():
    found = digests()
    return '''\
--  Written by scripts/bits_oracle.py; edit that and run it again.
--
--  core/bits's operations at u32 and u64 against Python's integers: each
--  operation's results over {cases} drawn cases per width fold into a
--  64-bit FNV-1a digest, which the script computed from the same draws.
--  The operands come from splitmix64, written out here so that they share
--  no code with core/bits, each shaped into a random word, one set bit,
--  one clear bit or a run of low ones.  The program exits 42 when every
--  digest agrees, 10 plus an operation's number at u32 and 30 plus it at
--  u64 for the first that does not.
import core/bits

{expected32}
{expected64}
--  splitmix64's step.
splitmix: (inout state: u64) -> (value: u64) =
    state = state +% 0x9e3779b97f4a7c15
    mut z: u64 = state
    z = (z ^ (z >> 30)) *% 0xbf58476d1ce4e5b9
    z = (z ^ (z >> 27)) *% 0x94d049bb133111eb
    value = z ^ (z >> 31)
end splitmix

--  An operand of `width` bits: a random word, one set bit, one clear bit
--  or a random word shifted down, chosen by the low bits of a draw.
shaped: (inout source: u64, width: u64) -> (value: u64) =
    draw: u64 = splitmix(source)
    mask: u64 = if width == 64 then 0xffffffffffffffff
                else (u64(1) << width) - 1 end if
    raw: u64 = splitmix(source) & mask
    k: u64 = (draw >> 2) % width
    shape: u64 = draw & 3
    value = if shape == 0 then raw
            elsif shape == 1 then u64(1) << k
            elsif shape == 2 then ~(u64(1) << k) & mask
            else raw >> k end if
end shaped

fold: (inout hash: u64, value: u64) -> none =
    hash = (hash ^ value) *% 0x100000001b3
end fold

{routine32}
{routine64}
public main: () -> (code: i32) =
    mut source: u64 = 0x{seed:x}
    mut hashes: [14]u64 = zeroed
    for index in usize(0)..<14 do
        hashes[index] = 0xcbf29ce484222325
    end for
    narrow(source, hashes)
    for index in usize(0)..<14 do
        code = 10 + i32(index)
        return when hashes[index] <> expected_32[index]
        hashes[index] = 0xcbf29ce484222325
    end for
    wide(source, hashes)
    for index in usize(0)..<14 do
        code = 30 + i32(index)
        return when hashes[index] <> expected_64[index]
    end for
    code = 42
end main
'''.format(cases=CASES, seed=SEED,
           expected32=landin_digests('32', found[32]),
           expected64=landin_digests('64', found[64]),
           routine32=width_routine('narrow', 'u32', '0xffffffff', 32),
           routine64=width_routine('wide', 'u64', '0xffffffffffffffff', 64))


META = '''\
class: runtime
profiles: standard
summary: core/bits's bit operations at u32 and u64 agree with Python's integers over 2048 drawn cases a width, each operation's results compared by a digest scripts/bits_oracle.py computed
program: main.ldn
root: ../../../../..
status: 42
targets: linux-x86-64, linux-arm64, darwin-arm64, freebsd-x86-64, freebsd-arm64, linux-rv64, cortex-m0, windows-x86-64, windows-arm64
constructs: 0150, 0290, 0320, 0330
'''


def default_refine():
    found = sorted(ROOT.glob('compiler/ada/build/*/*/bin/refine'),
                   key=lambda path: path.stat().st_mtime)
    if not found:
        raise Failure('no refine: build one with ./scripts/dev-build.sh, or name'
                      ' one with --refine')
    return found[-1]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    lane_refine.argument(parser, required=False, environment=True)
    args = parser.parse_args()
    try:
        refine = args.refine or default_refine()
        FIXTURE.mkdir(parents=True, exist_ok=True)
        source = FIXTURE / 'main.ldn'
        source.write_text(program(), encoding='utf-8')
        formatted = subprocess.run([str(refine), 'fmt', str(source)],
                                   capture_output=True, text=True, check=False)
        if formatted.returncode != 0:
            raise Failure('refine fmt refused %s:\n%s' % (source, formatted.stderr))
        (FIXTURE / 'fixture.meta').write_text(META, encoding='utf-8')
        print(FIXTURE.relative_to(ROOT))
        return 0
    except Failure as failure:
        print('bits_oracle: %s' % failure, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
