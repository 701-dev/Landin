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
Python reads, exact at the table's width, or a list of one per argument. A
fixture's image must fit Cortex-M0's 32 KiB of flash, so a family's tables
are split among several fixtures where they do not.
