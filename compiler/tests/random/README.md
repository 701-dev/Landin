# core/random against its reference

`core/random`'s generator is xoshiro256\*\* 1.0, and its draws are written
over it in Landin. `oracle.c` prints the values that `runtime/random-draws`
and `runtime/random-normal-draws` expect. It holds Blackman and Vigna's
`next` and `jump` unchanged from their reference implementation,
`xoshiro256starstar.c` from <https://prng.di.unimi.it/>, and ports of
`core/random`'s own draws to C over them, line for line, so a fixture
that agrees with it agrees with the reference.

Two of the draws, `normal` and `exponential`, call `log`. The oracle
uses the C library's, which can differ from `core/math`'s in the last
place, so `runtime/random-normal-draws` compares those draws within two
units in the last place. It pins `core/math`'s bits with a digest of a
thousand draws instead, which every target must reproduce. The oracle
prints the C library's digest beside it, which is expected to differ.

`runtime/random-distributions` and `runtime/random-float-distributions`
need no oracle: they test each draw's distribution over a sample its
seed pins (D3055).

## Commands

Inside `nix develop`:

```sh
cc -O2 -o /tmp/random-oracle compiler/tests/random/oracle.c -lm
/tmp/random-oracle
```
