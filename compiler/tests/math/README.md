# core/math against MPFR

`core/math`'s routines are measured against MPFR's correctly rounded
values, computed outside the program under test. Three kinds of evidence
come from here:

- **The `math-*` runtime fixtures**, which run on every target a runtime
  fixture runs on, the firmware lanes' Cortex-M, RV32 and Xtensa included.
  Each holds tables of inputs and the correctly rounded result for each,
  and exits 42 only when every result `core/math` gives is within the
  table's bound of it, counted in representable floats: 0 for a routine
  that is exact or correctly rounded, 1 for one whose error is below one
  unit in the last place. A table holds the specials its description
  names, random inputs drawn from its domains, and the inputs of a larger
  random pool whose exact results lie nearest a rounding boundary, which
  are the hardest to round.
- **`measure`**, a million random inputs of one routine at one width,
  drawn from the same domains, run on the host and checked by MPFR, which
  reports the largest error in units in the last place of the exact
  result and an input that gives it.
- **`exhaustive`**, every one of the 2^32 inputs of a one-argument `f32`
  routine, checked the same way.

The results are the same bits on every target, save which NaN a NaN
result is, since the routines use only IEEE arithmetic, which every target
rounds alike; the fixtures check the values on each, and `digest` compares
all 2^32 `f32` results of a routine between targets bit for bit, every NaN
counted as one.

## Files

| file | what it is |
|---|---|
| `oracle.c` | the MPFR program: case tables, input sets and the check; its header says how each is computed |
| `cases/*.json` | one file per family of routines: each fixture's tables, with their bound, domains and specials |
| `evaluate.ldn` | generated: the program `measure` and `exhaustive` run, which applies one routine to inputs it reads or enumerates |

## Commands

Inside `nix develop`:

```sh
python3 scripts/math_oracle.py fixtures [NAME...]
python3 scripts/math_oracle.py measure FUNCTION WIDTH [--count N]
python3 scripts/math_oracle.py exhaustive FUNCTION [--jobs N]
```

`fixtures` writes each `compiler/tests/fixtures/runtime/math-*` fixture a
description names, and `evaluate.ldn`; a new fixture is then made known
with `scripts/add_fixture.py`. The oracle is built against the MPFR and GMP
of `flake.lock`'s nixpkgs, which `nix build --inputs-from .` fetches, or
the prefixes `$LANDIN_MPFR` and `$LANDIN_GMP` name.

## Size on Cortex-M0

What each fixture's image holds on Cortex-M0's constrained reference at
`size/auto`, measured by the firmware lane's map of the linked image, in
bytes. `core/math` is the routines the fixture calls and their private
helpers, at both widths unless the name says one, with the concept's
evidence tables, 192 bytes each; libgcc is the soft float and division
helpers those routines need, which any program's float arithmetic shares;
the rest is the fixture's own tables and checks.

| fixture | `core/math` | libgcc | the fixture | text |
|---|---:|---:|---:|---:|
| the constants, `floor`, `round`, `round_even`, `split`, `scale`, `classify` (`library-shared-math`) | 3794 | 5882 | 1806 | 10928 |
| `math-acosh` | 13256 | 14114 | 3536 | 30356 |
| `math-arcsine` | 9536 | 14334 | 5204 | 28516 |
| `math-arctangent` | 7590 | 13250 | 7308 | 27636 |
| `math-asinh` | 13518 | 14114 | 3536 | 30620 |
| `math-atanh` | 6594 | 13498 | 3560 | 23136 |
| `math-cbrt` | 2690 | 11806 | 3488 | 17424 |
| `math-cosh` | 11154 | 13498 | 3632 | 27768 |
| `math-cosine` | 15542 | 10504 | 3648 | 29076 |
| `math-erf` | 12136 | 13498 | 3640 | 28756 |
| `math-erfc` | 12366 | 13498 | 3688 | 29036 |
| `math-exp` | 4880 | 13498 | 3704 | 21564 |
| `math-exp2` | 4920 | 13250 | 3752 | 21404 |
| `math-expm1` | 5924 | 13498 | 3752 | 22656 |
| `math-floor` | 2894 | 2132 | 6080 | 10524 |
| `math-fma-f32` | 2520 | 9808 | 1848 | 13592 |
| `math-fma-f64` | 6862 | 5292 | 3262 | 15188 |
| `math-gamma` | 10420 | 13718 | 3760 | 27384 |
| `math-hypot-f32` | 2506 | 4712 | 1548 | 8716 |
| `math-hypot-f64` | 4564 | 9370 | 2676 | 16408 |
| `math-log` | 4996 | 13498 | 3608 | 21584 |
| `math-log-gamma` | 11554 | 8930 | 2352 | 22676 |
| `math-log-gamma-f32` | 5950 | 8668 | 1388 | 16040 |
| `math-log10` | 4168 | 13498 | 3680 | 20828 |
| `math-log1p` | 5366 | 13498 | 3704 | 22052 |
| `math-log2` | 4002 | 13498 | 3656 | 20636 |
| `math-pow-f32` | 5960 | 4856 | 1980 | 12748 |
| `math-pow-f64` | 9724 | 9474 | 3540 | 22536 |
| `math-remainder` | 3264 | 6910 | 3784 | 13440 |
| `math-remainder-nearest` | 5270 | 13250 | 3784 | 21788 |
| classification and the representation (`math-representation`) | 8312 | 12866 | 4776 | 25404 |
| `math-round` | 2586 | 2132 | 4724 | 8856 |
| `math-sine` | 15498 | 10504 | 3648 | 29032 |
| `math-sinh` | 11292 | 13498 | 3632 | 27908 |
| `math-sqrt` | 3636 | 8802 | 3488 | 15364 |
| `math-tangent` | 15680 | 12498 | 3648 | 31236 |
| `math-tanh` | 7348 | 13498 | 3536 | 23864 |

The trigonometric fixtures carry the Payne-Hanek argument reduction and
its table, about 9 KiB at `none/off` and 5 at `size/auto`, which every
`sin`, `cos` and `tan` takes at both widths. At `none/off` the images of
the trigonometric, hyperbolic, error and gamma fixtures and `pow` at `f64`
exceed the 32 KiB of flash, which `compiler/tests/cortex-m/corpus.json`
records as their profile limits; the other profiles execute them.

## A description

```json
{"fixtures": {"math-roots": {"summary": "...", "tables": [
  {"fn": "cbrt", "width": 64, "bound": 1, "random": 32, "hard": 16,
   "pool": 20000, "domains": ["bits", "log:-1074:1024:+-"],
   "specials": ["0", "-0", "inf", "nan", "0x1p-1074"]}]}}}
```

A domain is `bits`, every bit pattern alike; `uniform:LO:HI`; or
`log:E1:E2:SIGN`, a power of two drawn from [E1, E2) with a uniform
significand, signed `+`, `-` or `+-`. `domains2` and `domains3` are the
second and third argument's. A special is a decimal or hexadecimal float
Python reads, rounded to the table's width, or a list of one per argument. A
fixture's image must fit Cortex-M0's 32 KiB of flash, so a family's tables
are split among several fixtures where they do not.
