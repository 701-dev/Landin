# core/text's float text against Python and C

`core/text` writes floats as text and reads them back: the shortest text
that reads back as the same float (D2754, D2755), the exact value
rounded once to places after the point or after the first digit (D2756),
and decimal text read rounded once (D2757). Each is checked against an
implementation that shares no code with it:

- **The `float-text-*` runtime fixtures**, which run on every target a
  runtime fixture runs on, the firmware lanes included. Each holds a table
  of edge values and the text the oracle gives for them, and a count of
  values drawn inside the program from `core/random`'s xoshiro256\*\*,
  which `scripts/float_text.py` draws alike, whose texts are compared by a
  64-bit FNV-1a digest. The oracles are Python's `repr` for the shortest
  `f64` digits, an exact search over Python's fractions for the shortest
  `f32` digits, C's `snprintf` called through `ctypes` for the rounded
  forms, and Python's exact fractions, rounded as `scripts/big_oracle.py`
  rounds them, for parsing.

  | fixture | what it checks |
  |---|---|
  | `float-text-shortest` | `append_f64` and `{:e}` over 223 edge values and 10,000 drawn `f64`s |
  | `float-text-rounded` | `append_f64_fixed` and `append_f64_exponent` at two and seventeen places over 130 of the edge values, and `{:.N}`, `{:.Ne}` and `{:+.NE}` over sixty drawn values and precisions |
  | `float-text-parse` | `parse_f64` over halfway decimals and their neighbours, long digit strings, refusals and limits, 5,000 drawn decimals, and the shortest text of 5,000 drawn `f64`s read back |
  | `float-text-single` | the same for `f32`: shortest and rounded text over 58 edge values, parsing rounded once from the decimal, and 8,000 drawn `f32`s |

- **The drawn run** of a million `f64`s, `drawn.ldn`: each one's shortest
  text against Python's `repr`, its text rounded to a drawn number of
  places, zero to nineteen, both ways against C's `printf`, the shortest
  read back as the same bits and the rounded texts read as Python's exact
  fractions round them. Run on 2026-11-26 on x86-64: all 1,000,000
  agreed, in 46 seconds.

- **The exhaustive run** of every `f32`, `exhaustive.ldn`: each finite
  value's shortest text must read back as the same bits, no decimal of
  one digit fewer near it may, and it must be the decimal of its length
  nearest the value, as `append_f32_exponent` rounds the exact value, or
  that decimal's neighbour when the nearest does not read back. The
  writer's digits and the exact digits come from different code, Ryu's
  scaled interval and big/limbs' multiplication, so the run checks each
  against the other as well as against the parser.

- **The Cortex-M0 sizes**, read from the firmware lane's images.

The drawn counts are what the slowest lane runs inside its time: the
Xtensa emulator gives a guest 20 seconds, and the rounded writers' exact
value of a subnormal is 80 limbs worked a limb at a time.

## Files

| file | what it is |
|---|---|
| `scripts/float_text.py` | the generator: `core/text/powers.ldn`, each fixture's program and its oracle's texts and digests, and the exhaustive run |
| `drawn.ldn` | the program the drawn run compiles at `--optimize speed`, which prints a line a value |
| `exhaustive.ldn` | the program the exhaustive run compiles at `--optimize speed` and runs in slices |
| `probes/` | the Cortex-M0 size probes, one routine each |

## Commands

Inside `nix develop`:

```sh
python3 scripts/float_text.py tables [--check]
python3 scripts/float_text.py fixtures [NAME...] [--check]
python3 scripts/float_text.py drawn [--count N] [--jobs N]
python3 scripts/float_text.py exhaustive [--parts N] [--jobs N] [--output DIR]
python3 environments/cortex-m/backend_corpus.py --tools TOOLS --refine REFINE \
    --output DIR $(for p in compiler/tests/float-text/probes/*.ldn; do echo --program $p; done)
```

## The exhaustive run

Run on 2026-11-26 on x86-64 at `--optimize speed`, in 256 slices fourteen
at a time beside other work: all 4,278,190,080 finite `f32`s, both
zeros included, passed every check, in 3,174 seconds and 30,983 CPU
seconds. The infinities and NaNs, 16,777,216 patterns, are left out; the
`float-text-single` fixture writes and reads them. The run before it
found its own checker wrong at 2^87, 2^90 and their negatives, where the
nearest decimal of the shortest's length ends in a zero that does not
read back, and the writer right.

## Sizes on Cortex-M0

Each figure is the flash of a probe program under `probes/` on the
constrained reference, `environments/cortex-m/backend_corpus.py --program`
at `size/auto`, that calls one routine with one value; the program that appends one `u32` and
nothing else is 2,044 bytes, and every float routine stands on its own,
so a program links only the ones it calls. The stack is the deepest the
harness saw of the 4 KiB reservation.

| what the program calls | flash | stack |
|---|---|---|
| `append_f32`, the shortest text | 14,472 | 1,704 |
| `append_f64` | 14,512 | 1,744 |
| `append_f32_fixed` | 13,700 | 1,456 |
| `append_f64_fixed` | 13,820 | 2,456 |
| `parse_f32` | 19,160 | 1,776 |
| `parse_f64`, soft double's arithmetic included | 23,792 | 3,264 |
| `format` of an `f32` with `{}` and `{:.3}`, every float path and the specification | 30,276 | 2,264 |
| `format` of an `f64` the same way | 30,412 | 3,064 |
| `format` of one `u32` with `{}` | 10,280 | 880 |

The last was 4,572 bytes before a placeholder took Rust's specification:
parsing it, padding to a width and the radixes cost about 5.7 KiB of
every image that formats, and `runtime/core-text-format-firmware`, the
corpus's firmware use of `format`, went from 7,548 bytes to 13,368. At
`none/off` the backend gives every IR slot a frame home of its own and
the images roughly double: a float's `format` and both parsers then
outgrow 32 KiB, and the corpus rows of the fixtures that format record
where they do, on each lane. The shortest writer's 64-bit arithmetic,
`__aeabi_lmul` and `__udivmoddi4` among it, is soft on Cortex-M0, which
is most of its size beside 620 bytes of powers.
