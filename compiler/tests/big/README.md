# core/big against Python

`core/big` and `core/big/limbs` are checked against another
implementation of arbitrary-precision arithmetic: Python's own integers
and its `fractions.Fraction`, which share no code with them. Three kinds
of evidence come from here:

- **The `big-*` runtime fixtures**, which run on every target a runtime
  fixture runs on, the firmware lanes included. Each holds a table of
  operations, their operands and the results Python gives, and exits 42
  only when every result `core/big` gives agrees, limb for limb and sign
  for sign, or for a float bit for bit. Operands too long for a table, up
  to 320 limbs, are drawn inside the program from `core/random`'s
  xoshiro256\*\*, which `scripts/big_oracle.py` draws alike, and their
  products, quotients and remainders are compared by a 64-bit FNV-1a
  digest of their limbs. An operation numbered from 0x100 in a table
  writes its result over its first operand, as D2595 allows.
- **`time`**, a multiplication of two numbers of n limbs and a division of
  2n limbs by n, timed on the host from one limb to a million bits.
- **The Cortex-M0 sizes** of the layers, read from the firmware lane's
  images of the fixtures.

A limb is 32 bits on every target (D2594), so every routine gives the
same limbs everywhere; the fixtures check it on each.

## Files

| file | what it is |
|---|---|
| `scripts/big_oracle.py` | the generator: Python's results for each table, the drawn operands' digests, and each fixture's program |
| `timing.ldn` | the program `time` runs |

## Commands

Inside `nix develop`:

```sh
python3 scripts/big_oracle.py fixtures [NAME...]
python3 scripts/big_oracle.py time [--most LIMBS] [--spend SECONDS]
```

`fixtures` writes each `compiler/tests/fixtures/runtime/big-*` fixture,
or the ones named; a new one is then made known with
`scripts/add_fixture.py`. `time` compiles `timing.ldn` at `--optimize
speed` and prints a line for each length: its bits, and the nanoseconds a
multiplication and a division took.

## The fixtures

Each fixture holds one area, so that its image fits a small part where it
can. On the Cortex-M0 reference, whose probes link into 32 KiB of flash,
`compiler/tests/cortex-m/corpus.json` records a profile limit for each
image that does not fit, with its measured size; such a fixture leaves
`cortex-m0` out of its `targets:`, every profile that fits still runs
there, and the `mps2-an500` lane, with 4 MiB, runs every profile.

| fixture | what it checks | Cortex-M0 at `size/auto` |
|---|---|---|
| `big-limbs` | every routine of `core/big/limbs` but multiplication and division, results over an operand among them, decimal and hexadecimal text both ways, and text that is no number refused | 15,764 bytes; none/off over |
| `big-limbs-products` | products and quotients of drawn operands from 1 to 320 limbs, on each side of the Karatsuba and Toom-3 thresholds, operands of all one bits among them | 21,908 bytes; none/off over |
| `big-integer` | sums, differences, comparison, sign, negation, absolute value | 13,180 bytes, every profile |
| `big-integer-products` | products, and products of drawn operands to 160 by 151 limbs | 26,676 bytes; none/off over |
| `big-integer-quotients` | both divisions, and those of drawn operands | 23,076 bytes; none/off over |
| `big-integer-powers` | powers | 25,256 bytes; none/off over |
| `big-integer-roots` | integer roots, of negative values at odd degrees | over, 36,588 bytes |
| `big-integer-gcd` | the greatest common divisor | 16,652 bytes, every profile |
| `big-integer-modular` | the inverse modulo a modulus, the power modulo one | over, 39,508 bytes |
| `big-integer-bits` | and, or, exclusive or, complement, shifts, single bits, bit lengths, of negative values among them | 20,240 bytes; none/off over |
| `big-integer-conversion` | to and from `i64`, `u64`, `f64` and `f32`: the limits of each, ties to even, overflow to infinity | 18,436 bytes; none/off over |
| `big-integer-text` | decimal and hexadecimal text written and read back, and refusals | 21,556 bytes; none/off over |
| `big-rational` | lowest terms, sums, differences, comparison, sign, negation | over, 43,128 bytes |
| `big-rational-products` | products, quotients, powers, floor and truncation | over, 48,788 bytes |
| `big-rational-floats` | the nearest `f64` and `f32`: ties, quotients in the subnormal range, overflow; exact values of floats | over, 50,968 bytes |
| `big-rational-text` | text written, read back and refused | over, 47,212 bytes |

`library-shared-big`, the module's small probe, is 11,584 bytes at
`size/auto` and runs at every profile. A routine that loops keeps its
temporaries (D2596), so each record runs in an arena of a few KiB, inside
the reference's 16 KiB of RAM.

## Size on Cortex-M0

What `core/big/limbs` takes in an image on Cortex-M0's constrained
reference at `size/auto`, from the lane's map of `big-limbs` and
`big-limbs-products`, in bytes. A program takes only the routines it
calls.

| part | bytes |
|---|---:|
| the whole layer | 20,310 |
| multiplication: schoolbook, Karatsuba and Toom-3 with their helpers | 9,724 |
| division by Algorithm D | 1,918 |
| decimal and hexadecimal text both ways | 2,884 |
| the rest: sums, differences, one-limb products and quotients, shifts, comparison | 5,784 |

The integers above it add their storage and the routines a program
calls: `library-shared-big`, which adds and compares in an arena, is
11,584 bytes all told. A program that both multiplies and divides, as an
integer root, a modular inverse or power and every rational routine do,
outgrows the reference's 32 KiB.

## Timing

`python3 scripts/big_oracle.py time` on Linux x86-64, one core of an AMD
EPYC host shared with other work, 2026-11-26, at `--optimize speed`:
nanoseconds per call.

| bits | multiply n by n | divide 2n by n |
|---:|---:|---:|
| 32 | 92 | 94 |
| 256 | 206 | 492 |
| 1,280 | 1,929 | 4,719 |
| 4,320 | 15,917 | 43,586 |
| 9,696 | 60,936 | 210,681 |
| 32,672 | 365,811 | 2,287,690 |
| 110,208 | 2,678,617 | 27,461,071 |
| 371,936 | 13,507,173 | 292,073,599 |
| 1,000,000 | 58,421,261 | 2,128,890,581 |

Multiplication grows as Toom-3's n^1.47 above its threshold. Division is
Algorithm D's schoolbook, whose work grows with the square of the length,
and so is decimal text; divide-and-conquer methods for both wait for a
consumer that needs them (D2601).
