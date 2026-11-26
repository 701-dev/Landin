# core/dense against the reference BLAS and OpenBLAS

`core/dense`'s evidence is of two kinds: the reference BLAS's own test
programs, translated into runtime fixtures that run on every hosted
target and on the Cortex-M7 and Xtensa emulators, and
the time its `f64` matrix product takes beside OpenBLAS's on one core.

## The translated test programs

The `dense-blas-*` runtime fixtures translate `BLAS/TESTING` of
Reference-LAPACK 3.12.1, whose licence each fixture's NOTICE carries:

| fixture | translates | checks |
|---|---|---|
| `runtime/dense-blas-level-1` | `dblat1.f` and `sblat1.f` | the rotations, norms, sums, `iamax`, `dot`, `axpy`, `copy`, `swap` and `rot` against dblat1's tables, by its own comparison with its scale factor, and `nrm2`'s special values against its threshold |
| `runtime/dense-blas-level-2` | `dblat2.f` with `dblat2.in` | `gemv`, `symv`, `trmv`, `trsv`, `ger`, `syr` and `syr2` by dblat2's test ratio |
| `runtime/dense-blas-level-3` | `dblat3.f` with `dblat3.in` | `gemm`, `symm`, `trmm`, `trsm`, `syrk` and `syr2k` by dblat3's test ratio |

Each keeps its program's data generator, its parameters, its reference
computation and its checks that the operands a routine only reads, and
the triangle it must not touch, are unchanged. A test ratio is the
computed result's error over the error bound a correct routine meets,
`|computed - expected| / (ε · scale)`, which the BLAS's tests hold under
16; each fixture runs every case at `f64` and at `f32`, each with its own
ε, and exits 42 when every ratio is under 16 and every check holds.
They depart from the originals where `core/dense` differs from the BLAS,
and each header says how: a negative increment runs at its magnitude
(D2696), an empty dimension is checked against the mathematical result
rather than against an untouched output (D2699), the error exits and the
routines `core/dense` leaves out are not translated, and every matrix is
also run laid out by rows.

## The timing

`scripts/dense_timing.py` builds `timing.ldn` with refine at `--optimize
speed` and `timing.c` against the pinned nixpkgs's OpenBLAS, and runs them
interleaved, each pinned to one core with OpenBLAS on one thread. Both
multiply the same two 1000 by 1000 `f64` matrices laid out by columns,
whose elements are small integers, so every sum is exact and the
checksums they print agree whatever order the sums take; each prints the
nanoseconds the product alone took on the monotonic clock.

```sh
python3 scripts/dense_timing.py \
    --refine "compiler/ada/build/$LANDIN_BUILD_TAG/debug/bin/refine" \
    --core 15 --output "$(mktemp -d)"
```

Run it inside `nix develop`, alone on its host.

On 26 November 2026, on one core of an AMD EPYC 7302 (Zen 2) under NixOS,
with refine at the x86-64-v1 baseline and OpenBLAS 0.3.33, the
median of five runs:

| product | time | rate |
|---|---|---|
| `core/dense` `multiply` | 0.41 s | 4.9 GFLOP/s |
| OpenBLAS `cblas_dgemm` | 0.049 s | 41 GFLOP/s |

`core/dense` takes 8.2 times OpenBLAS's time (D2703). OpenBLAS's kernel
does eight flops an instruction with AVX2's fused multiply-add; refine
emits scalar SSE2, two, at any `--level`, and the register records
what the scalar kernel's loop still carries.
