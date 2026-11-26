/*  The oracle core/math and core/complex are measured against: MPFR's
    and MPC's correctly rounded values, computed outside the program
    under test.

    scripts/math_oracle.py builds this file against the MPFR, MPC and GMP
    of flake.lock's nixpkgs and runs it; see compiler/tests/math/README.md.

    A function of core/math takes and gives floats.  A function of
    core/complex, named `complex.NAME`, takes and gives complex numbers,
    each written as two floats, the real part first; `complex.abs` and
    `complex.arg` give one float and `complex.from_polar` takes two.  So
    a record or a case is the inputs' words, then the result's: up to
    four words in and two out.  Each part of a complex result is rounded
    and measured on its own, against that part of MPC's result.

      oracle cases --fn NAME --width 32|64 --seed N --random N --hard N
                   [--pool N] [--domain SPEC]... [--domain2 SPEC]...
                   [--domain3 SPEC]... [--domain4 SPEC]...
                   [--special HEX[,HEX]...]...
          Prints one case per line: the inputs' bits and the correctly
          rounded result's bits, in hexadecimal at the width.  The cases
          are the specials, then `random` inputs drawn from the domains,
          then the `hard` inputs of a pool of `pool` draws whose exact
          results lie nearest a rounding boundary of the width, the
          nearer of a complex result's two parts deciding.

      oracle inputs --fn NAME --width 32|64 --seed N --count N
                    [--domain SPEC]... [--domain2 SPEC]... [--domain3 SPEC]...
                    [--domain4 SPEC]...
          Writes `count` input records to standard output, each input in
          little-endian bytes at the width, for compiler/tests/math/
          evaluate.ldn to read.

      oracle check --fn NAME --width 32|64 [--bound ULP] [--show N] [--norm yes]
          Reads records from standard input, each the inputs then the
          result under test, little-endian at the width, and prints one
          JSON object: the count, the largest error in units in the last
          place of the exact result and an input that gives it, the count
          of results not correctly rounded and the count past `bound`.  A
          complex result's error is the larger of its parts' errors, each
          in units of its own last place or, with `--norm yes`, of the
          larger part's.

    A domain is `bits` (every bit pattern of the width alike), `uniform:
    LO:HI` (a real drawn uniformly from [LO, HI], then rounded to the
    width) or `log:E1:E2:SIGN` (a magnitude of 2 to a power drawn
    uniformly from [E1, E2), with a uniform significand, signed `+`, `-`
    or `+-`).  Several domains of one argument are drawn from in turn.

    The error of a result c against the exact value z is |c - z| / ulp(z),
    ulp(z) being 2 to the exponent of z's last significand bit at the
    width, the subnormal ulp at the bottom of the range.  A NaN result
    where z is a number, or a number where z is NaN, an infinity where
    the correctly rounded result is finite, or the reverse, is an
    infinite error.  A zero result whose sign differs from the correctly
    rounded zero's is an infinite error too.  A part of a complex result
    beside a NaN part is compared by magnitude alone: Annex G leaves the
    sign of nearly every such zero or infinity unspecified. */

#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <gmp.h>
#include <mpfr.h>
#include <mpc.h>

enum { exact_precision = 320 };

/* xoshiro256** seeded through splitmix64, as core/random does. */
static uint64_t rng[4];

static uint64_t splitmix(uint64_t *seed) {
    uint64_t z = (*seed += 0x9e3779b97f4a7c15ULL);
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    return z ^ (z >> 31);
}

static void seed_rng(uint64_t seed) {
    for (int i = 0; i < 4; i++) rng[i] = splitmix(&seed);
}

static uint64_t rotl(uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }

static uint64_t next_u64(void) {
    uint64_t result = rotl(rng[1] * 5, 7) * 9;
    uint64_t t = rng[1] << 17;
    rng[2] ^= rng[0];
    rng[3] ^= rng[1];
    rng[1] ^= rng[2];
    rng[0] ^= rng[3];
    rng[2] ^= t;
    rng[3] = rotl(rng[3], 45);
    return result;
}

static double next_unit(void) { return (double)(next_u64() >> 11) * 0x1.0p-53; }

/* The two formats. */
typedef struct {
    int width, precision;
    mpfr_exp_t emin, emax; /* MPFR's: x = m * 2^e, 1/2 <= m < 1 */
    int subnormal_ulp;     /* the exponent of the least subnormal */
} format_t;

static const format_t binary32 = {32, 24, -148, 128, -149};
static const format_t binary64 = {64, 53, -1073, 1024, -1074};

static double bits_to_double(const format_t *f, uint64_t bits) {
    if (f->width == 64) {
        double d;
        memcpy(&d, &bits, 8);
        return d;
    }
    uint32_t b = (uint32_t)bits;
    float s;
    memcpy(&s, &b, 4);
    return (double)s;
}

static uint64_t double_to_bits(const format_t *f, double d) {
    if (f->width == 64) {
        uint64_t b;
        memcpy(&b, &d, 8);
        return b;
    }
    float s = (float)d;
    uint32_t b;
    memcpy(&b, &s, 4);
    return b;
}

/* The functions. */
typedef enum {
    F_SQRT, F_CBRT, F_HYPOT, F_FMA, F_FLOOR, F_CEIL, F_TRUNC, F_ROUND,
    F_ROUND_EVEN, F_REMAINDER, F_REMAINDER_NEAREST,
    F_EXP, F_EXP2, F_EXPM1, F_LOG, F_LOG2, F_LOG10, F_LOG1P, F_POW,
    F_SIN, F_COS, F_TAN, F_ASIN, F_ACOS, F_ATAN, F_ATAN2,
    F_SINH, F_COSH, F_TANH, F_ASINH, F_ACOSH, F_ATANH,
    F_ERF, F_ERFC, F_GAMMA, F_LOG_GAMMA,
    C_ADD, C_SUBTRACT, C_MULTIPLY, C_DIVIDE, C_NEGATE, C_CONJUGATE,
    C_PROJECT, C_ABS, C_ARG, C_FROM_POLAR,
    C_EXP, C_LOG, C_POW, C_SQRT, C_SIN, C_COS, C_TAN, C_ASIN, C_ACOS,
    C_ATAN, C_SINH, C_COSH, C_TANH, C_ASINH, C_ACOSH, C_ATANH
} fn_kind;

/* A function's inputs and result, counted in floats. */
typedef struct {
    const char *name;
    fn_kind kind;
    int inputs, outputs;
} fn_t;

static const fn_t functions[] = {
    {"sqrt", F_SQRT, 1, 1}, {"cbrt", F_CBRT, 1, 1}, {"hypot", F_HYPOT, 2, 1},
    {"fma", F_FMA, 3, 1}, {"floor", F_FLOOR, 1, 1}, {"ceil", F_CEIL, 1, 1},
    {"trunc", F_TRUNC, 1, 1}, {"round", F_ROUND, 1, 1},
    {"round_even", F_ROUND_EVEN, 1, 1}, {"remainder", F_REMAINDER, 2, 1},
    {"remainder_nearest", F_REMAINDER_NEAREST, 2, 1},
    {"exp", F_EXP, 1, 1}, {"exp2", F_EXP2, 1, 1}, {"expm1", F_EXPM1, 1, 1},
    {"log", F_LOG, 1, 1}, {"log2", F_LOG2, 1, 1}, {"log10", F_LOG10, 1, 1},
    {"log1p", F_LOG1P, 1, 1}, {"pow", F_POW, 2, 1},
    {"sin", F_SIN, 1, 1}, {"cos", F_COS, 1, 1}, {"tan", F_TAN, 1, 1},
    {"asin", F_ASIN, 1, 1}, {"acos", F_ACOS, 1, 1}, {"atan", F_ATAN, 1, 1},
    {"atan2", F_ATAN2, 2, 1},
    {"sinh", F_SINH, 1, 1}, {"cosh", F_COSH, 1, 1}, {"tanh", F_TANH, 1, 1},
    {"asinh", F_ASINH, 1, 1}, {"acosh", F_ACOSH, 1, 1}, {"atanh", F_ATANH, 1, 1},
    {"erf", F_ERF, 1, 1}, {"erfc", F_ERFC, 1, 1}, {"gamma", F_GAMMA, 1, 1},
    {"log_gamma", F_LOG_GAMMA, 1, 1},
    {"complex.add", C_ADD, 4, 2}, {"complex.subtract", C_SUBTRACT, 4, 2},
    {"complex.multiply", C_MULTIPLY, 4, 2}, {"complex.divide", C_DIVIDE, 4, 2},
    {"complex.negate", C_NEGATE, 2, 2}, {"complex.conjugate", C_CONJUGATE, 2, 2},
    {"complex.project", C_PROJECT, 2, 2}, {"complex.abs", C_ABS, 2, 1},
    {"complex.arg", C_ARG, 2, 1}, {"complex.from_polar", C_FROM_POLAR, 2, 2},
    {"complex.exp", C_EXP, 2, 2}, {"complex.log", C_LOG, 2, 2},
    {"complex.pow", C_POW, 4, 2}, {"complex.sqrt", C_SQRT, 2, 2},
    {"complex.sin", C_SIN, 2, 2}, {"complex.cos", C_COS, 2, 2},
    {"complex.tan", C_TAN, 2, 2}, {"complex.asin", C_ASIN, 2, 2},
    {"complex.acos", C_ACOS, 2, 2}, {"complex.atan", C_ATAN, 2, 2},
    {"complex.sinh", C_SINH, 2, 2}, {"complex.cosh", C_COSH, 2, 2},
    {"complex.tanh", C_TANH, 2, 2}, {"complex.asinh", C_ASINH, 2, 2},
    {"complex.acosh", C_ACOSH, 2, 2}, {"complex.atanh", C_ATANH, 2, 2},
};

enum { max_inputs = 4, max_outputs = 2 };

static const fn_t *find_function(const char *name) {
    for (size_t i = 0; i < sizeof functions / sizeof functions[0]; i++)
        if (strcmp(functions[i].name, name) == 0) return &functions[i];
    fprintf(stderr, "oracle: no function %s\n", name);
    exit(2);
}

/* y = f(a[, b[, c]]) rounded to y's precision; returns MPFR's ternary. */
static int evaluate_real(const fn_t *fn, mpfr_t y, mpfr_t *a) {
    mpfr_rnd_t r = MPFR_RNDN;
    int sign;
    switch (fn->kind) {
    case F_SQRT: return mpfr_sqrt(y, a[0], r);
    case F_CBRT: return mpfr_cbrt(y, a[0], r);
    case F_HYPOT: return mpfr_hypot(y, a[0], a[1], r);
    case F_FMA: return mpfr_fma(y, a[0], a[1], a[2], r);
    case F_FLOOR: return mpfr_floor(y, a[0]);
    case F_CEIL: return mpfr_ceil(y, a[0]);
    case F_TRUNC: return mpfr_trunc(y, a[0]);
    case F_ROUND: return mpfr_round(y, a[0]);
    case F_ROUND_EVEN: return mpfr_roundeven(y, a[0]);
    case F_REMAINDER: return mpfr_fmod(y, a[0], a[1], r);
    case F_REMAINDER_NEAREST: return mpfr_remainder(y, a[0], a[1], r);
    case F_EXP: return mpfr_exp(y, a[0], r);
    case F_EXP2: return mpfr_exp2(y, a[0], r);
    case F_EXPM1: return mpfr_expm1(y, a[0], r);
    case F_LOG: return mpfr_log(y, a[0], r);
    case F_LOG2: return mpfr_log2(y, a[0], r);
    case F_LOG10: return mpfr_log10(y, a[0], r);
    case F_LOG1P: return mpfr_log1p(y, a[0], r);
    case F_POW: return mpfr_pow(y, a[0], a[1], r);
    case F_SIN: return mpfr_sin(y, a[0], r);
    case F_COS: return mpfr_cos(y, a[0], r);
    case F_TAN: return mpfr_tan(y, a[0], r);
    case F_ASIN: return mpfr_asin(y, a[0], r);
    case F_ACOS: return mpfr_acos(y, a[0], r);
    case F_ATAN: return mpfr_atan(y, a[0], r);
    case F_ATAN2: return mpfr_atan2(y, a[0], a[1], r);
    case F_SINH: return mpfr_sinh(y, a[0], r);
    case F_COSH: return mpfr_cosh(y, a[0], r);
    case F_TANH: return mpfr_tanh(y, a[0], r);
    case F_ASINH: return mpfr_asinh(y, a[0], r);
    case F_ACOSH: return mpfr_acosh(y, a[0], r);
    case F_ATANH: return mpfr_atanh(y, a[0], r);
    case F_ERF: return mpfr_erf(y, a[0], r);
    case F_ERFC: return mpfr_erfc(y, a[0], r);
    case F_GAMMA:
        /* C's tgamma(-0) is -infinity and tgamma of a negative integer
           NaN, as MPFR's gamma gives. */
        return mpfr_gamma(y, a[0], r);
    case F_LOG_GAMMA:
        /* C's lgamma: the logarithm of |gamma|, +infinity at a
           nonpositive integer, where MPFR's lgamma gives +infinity too. */
        return mpfr_lgamma(y, &sign, a[0], r);
    default: break;
    }
    return 0;
}

/* (r + i s) * u, u real, with IEEE's products: the parts are r * u and
   s * u, an infinity times a zero NaN, as Annex G's sample multiply has
   it before its recovery, and from_polar's parts are. */
static int mpc_times_real(mpc_t y, mpc_t x, mpfr_t u) {
    int a = mpfr_mul(mpc_realref(y), mpc_realref(x), u, MPFR_RNDN);
    int b = mpfr_mul(mpc_imagref(y), mpc_imagref(x), u, MPFR_RNDN);
    return MPC_INEX(a, b);
}

/* y[0..outputs) = f(a), each rounded to its own precision; the parts'
   ternary values go to t. */
static void evaluate(const fn_t *fn, mpfr_t *y, mpfr_t *a, int *t) {
    if (fn->kind < C_ADD) {
        t[0] = evaluate_real(fn, y[0], a);
        return;
    }
    mpfr_prec_t p = mpfr_get_prec(y[0]);
    mpc_t x, w, z;
    mpc_init2(x, mpfr_get_prec(a[0]));
    mpc_init2(w, mpfr_get_prec(a[0]));
    mpc_init2(z, p);
    mpfr_set(mpc_realref(x), a[0], MPFR_RNDN);
    mpfr_set(mpc_imagref(x), a[1], MPFR_RNDN);
    if (fn->inputs == 4) {
        mpfr_set(mpc_realref(w), a[2], MPFR_RNDN);
        mpfr_set(mpc_imagref(w), a[3], MPFR_RNDN);
    }
    mpc_rnd_t r = MPC_RNDNN;
    int inex = 0;
    switch (fn->kind) {
    case C_ADD: inex = mpc_add(z, x, w, r); break;
    case C_SUBTRACT: inex = mpc_sub(z, x, w, r); break;
    case C_MULTIPLY: inex = mpc_mul(z, x, w, r); break;
    case C_DIVIDE: inex = mpc_div(z, x, w, r); break;
    case C_NEGATE: inex = mpc_neg(z, x, r); break;
    case C_CONJUGATE: inex = mpc_conj(z, x, r); break;
    case C_PROJECT: inex = mpc_proj(z, x, r); break;
    case C_ABS: t[0] = mpc_abs(y[0], x, MPFR_RNDN); goto done;
    case C_ARG: t[0] = mpc_arg(y[0], x, MPFR_RNDN); goto done;
    case C_FROM_POLAR: {
        /* magnitude * cos(angle) and magnitude * sin(angle), each from
           a cosine or sine far more precise than the result. */
        mpc_t u;
        mpfr_t m;
        mpc_init2(u, exact_precision + 64);
        mpfr_init2(m, mpfr_get_prec(a[0]));
        mpfr_set(m, a[0], MPFR_RNDN);
        mpfr_sin_cos(mpc_imagref(u), mpc_realref(u), a[1], MPFR_RNDN);
        mpc_t v;
        mpc_init2(v, exact_precision + 128);
        mpc_times_real(v, u, m);
        int re = mpfr_set(mpc_realref(z), mpc_realref(v), MPFR_RNDN);
        int im = mpfr_set(mpc_imagref(z), mpc_imagref(v), MPFR_RNDN);
        inex = MPC_INEX(re, im);
        mpc_clear(u);
        mpc_clear(v);
        mpfr_clear(m);
        break;
    }
    case C_EXP: inex = mpc_exp(z, x, r); break;
    case C_LOG: inex = mpc_log(z, x, r); break;
    case C_POW: inex = mpc_pow(z, x, w, r); break;
    case C_SQRT: inex = mpc_sqrt(z, x, r); break;
    case C_SIN: inex = mpc_sin(z, x, r); break;
    case C_COS: inex = mpc_cos(z, x, r); break;
    case C_TAN: inex = mpc_tan(z, x, r); break;
    case C_ASIN: inex = mpc_asin(z, x, r); break;
    case C_ACOS: inex = mpc_acos(z, x, r); break;
    case C_ATAN: inex = mpc_atan(z, x, r); break;
    case C_SINH: inex = mpc_sinh(z, x, r); break;
    case C_COSH: inex = mpc_cosh(z, x, r); break;
    case C_TANH: inex = mpc_tanh(z, x, r); break;
    case C_ASINH: inex = mpc_asinh(z, x, r); break;
    case C_ACOSH: inex = mpc_acosh(z, x, r); break;
    case C_ATANH: inex = mpc_atanh(z, x, r); break;
    default: break;
    }
    mpfr_swap(y[0], mpc_realref(z));
    mpfr_swap(y[1], mpc_imagref(z));
    t[0] = MPC_INEX_RE(inex);
    t[1] = MPC_INEX_IM(inex);
done:
    mpc_clear(x);
    mpc_clear(w);
    mpc_clear(z);
}

/* The correctly rounded result at the format, as doubles.  MPFR's
   functions are evaluated within the format's exponent range, MPC's
   in MPFR's whole range, since MPC's intermediate values would
   underflow in the format's: the result then is brought into the
   format's range by its ternary value, rounding once. */
static void correctly_rounded(const format_t *f, const fn_t *fn, mpfr_t *a, double *out) {
    mpfr_exp_t old_min = mpfr_get_emin(), old_max = mpfr_get_emax();
    mpfr_t y[max_outputs];
    int t[max_outputs] = {0};
    for (int k = 0; k < fn->outputs; k++) mpfr_init2(y[k], f->precision);
    if (fn->kind >= C_ADD) evaluate(fn, y, a, t);
    mpfr_set_emin(f->emin);
    mpfr_set_emax(f->emax);
    if (fn->kind < C_ADD) evaluate(fn, y, a, t);
    for (int k = 0; k < fn->outputs; k++) {
        t[k] = mpfr_check_range(y[k], t[k], MPFR_RNDN);
        mpfr_subnormalize(y[k], t[k], MPFR_RNDN);
        out[k] = mpfr_get_d(y[k], MPFR_RNDN);
    }
    mpfr_set_emin(old_min);
    mpfr_set_emax(old_max);
    for (int k = 0; k < fn->outputs; k++) mpfr_clear(y[k]);
}

/* The exact result, at exact_precision. */
static void exact(const fn_t *fn, mpfr_t *z, mpfr_t *a) {
    int t[max_outputs];
    evaluate(fn, z, a, t);
}

static void set_inputs(const format_t *f, int arity, const uint64_t *bits, mpfr_t *a) {
    for (int i = 0; i < arity; i++) {
        mpfr_init2(a[i], 64);
        mpfr_set_d(a[i], bits_to_double(f, bits[i]), MPFR_RNDN);
    }
}

static void clear_inputs(int arity, mpfr_t *a) {
    for (int i = 0; i < arity; i++) mpfr_clear(a[i]);
}

/* |c - z| / ulp(z) for the exact z, or INFINITY as the header says.
   Measured normwise, ulp(z) is that of `norm`, the larger of a complex
   result's parts in magnitude, and a zero's sign counts only where
   both parts are zero. */
static double ulp_error(const format_t *f, double c, double rounded, mpfr_t z,
                        mpfr_t norm, int signed_zero) {
    if (mpfr_nan_p(z)) return isnan(c) ? 0.0 : INFINITY;
    if (isnan(c)) return INFINITY;
    if (isinf(rounded) || isinf(c)) return c == rounded ? 0.0 : INFINITY;
    if (signed_zero && c == 0.0 && rounded == 0.0 && signbit(c) != signbit(rounded))
        return INFINITY;
    if (mpfr_zero_p(norm)) return fabs(c) / ldexp(1.0, f->subnormal_ulp);
    long e = mpfr_get_exp(norm) - f->precision;
    if (e < f->subnormal_ulp) e = f->subnormal_ulp;
    mpfr_t d;
    mpfr_init2(d, exact_precision);
    mpfr_set_d(d, c, MPFR_RNDN);
    mpfr_sub(d, d, z, MPFR_RNDN);
    mpfr_abs(d, d, MPFR_RNDN);
    mpfr_mul_2si(d, d, -e, MPFR_RNDN);
    double err = mpfr_get_d(d, MPFR_RNDU);
    mpfr_clear(d);
    return err;
}

/* How near the exact result lies to a rounding boundary: the distance
   of z / ulp(z)'s fraction from one half, small for a hard case.  A
   result that is an infinity, NaN, zero, or exact, is never hard. */
static double hardness(const format_t *f, mpfr_t z) {
    if (!mpfr_regular_p(z)) return 1.0;
    long e = mpfr_get_exp(z) - f->precision;
    if (e < f->subnormal_ulp) e = f->subnormal_ulp;
    if (mpfr_get_exp(z) > f->emax) return 1.0;
    mpfr_t s, w;
    mpfr_init2(s, exact_precision);
    mpfr_init2(w, exact_precision);
    mpfr_abs(s, z, MPFR_RNDN);
    mpfr_mul_2si(s, s, -e, MPFR_RNDN);
    mpfr_frac(w, s, MPFR_RNDN);
    double frac = mpfr_get_d(w, MPFR_RNDN);
    mpfr_clear(s);
    mpfr_clear(w);
    if (frac == 0.0) return 1.0;
    return fabs(frac - 0.5);
}

/* Domains. */
typedef struct {
    enum { D_BITS, D_UNIFORM, D_LOG } kind;
    double lo, hi;
    int sign; /* 1 +, -1 -, 0 either */
} domain_t;

typedef struct {
    domain_t items[16];
    int count, next;
} domains_t;

static void parse_domain(domains_t *ds, const char *spec) {
    if (ds->count == 16) {
        fprintf(stderr, "oracle: too many domains\n");
        exit(2);
    }
    domain_t *d = &ds->items[ds->count++];
    if (strcmp(spec, "bits") == 0) {
        d->kind = D_BITS;
    } else if (strncmp(spec, "uniform:", 8) == 0) {
        d->kind = D_UNIFORM;
        if (sscanf(spec + 8, "%lf:%lf", &d->lo, &d->hi) != 2) goto bad;
    } else if (strncmp(spec, "log:", 4) == 0) {
        char sign[4] = "";
        d->kind = D_LOG;
        if (sscanf(spec + 4, "%lf:%lf:%3s", &d->lo, &d->hi, sign) != 3) goto bad;
        d->sign = strcmp(sign, "+") == 0 ? 1 : strcmp(sign, "-") == 0 ? -1 : 0;
    } else {
        goto bad;
    }
    return;
bad:
    fprintf(stderr, "oracle: bad domain %s\n", spec);
    exit(2);
}

static uint64_t draw(const format_t *f, domains_t *ds) {
    domain_t *d = &ds->items[ds->next];
    ds->next = (ds->next + 1) % ds->count;
    switch (d->kind) {
    case D_BITS:
        return f->width == 64 ? next_u64() : next_u64() >> 32;
    case D_UNIFORM:
        return double_to_bits(f, d->lo + (d->hi - d->lo) * next_unit());
    case D_LOG: {
        double e = floor(d->lo + (d->hi - d->lo) * next_unit());
        double m = 1.0 + next_unit();
        double v = ldexp(m, (int)e);
        int s = d->sign != 0 ? d->sign : (next_u64() >> 63) ? -1 : 1;
        if (f->width == 32 && fabs(v) > 0x1.fffffep127) v = 0x1.fffffep127;
        return double_to_bits(f, s * v);
    }
    }
    return 0;
}

static void print_case(const format_t *f, const fn_t *fn, const uint64_t *in,
                       const double *out) {
    int digits = f->width / 4;
    for (int i = 0; i < fn->inputs; i++) printf("%0*" PRIx64 " ", digits, in[i]);
    for (int k = 0; k < fn->outputs; k++)
        printf("%0*" PRIx64 "%s", digits, double_to_bits(f, out[k]),
               k + 1 < fn->outputs ? " " : "\n");
}

typedef struct {
    uint64_t in[max_inputs];
    double hard;
} candidate_t;

static int by_hardness(const void *a, const void *b) {
    double x = ((const candidate_t *)a)->hard, y = ((const candidate_t *)b)->hard;
    return x < y ? -1 : x > y;
}

static int parse_width(const char *s, const format_t **f) {
    if (strcmp(s, "32") == 0) *f = &binary32;
    else if (strcmp(s, "64") == 0) *f = &binary64;
    else return 0;
    return 1;
}

static void case_line(const format_t *f, const fn_t *fn, const uint64_t *in) {
    mpfr_t a[max_inputs];
    double out[max_outputs];
    set_inputs(f, fn->inputs, in, a);
    correctly_rounded(f, fn, a, out);
    print_case(f, fn, in, out);
    clear_inputs(fn->inputs, a);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: oracle cases|inputs|check --fn NAME --width 32|64 ...\n");
        return 2;
    }
    const char *mode = argv[1];
    const fn_t *fn = NULL;
    const format_t *f = NULL;
    uint64_t seed = 1, count = 0, random_count = 0, hard_count = 0, pool = 100000;
    double bound = INFINITY;
    long show = 0;
    int normwise = 0;
    domains_t domains[max_inputs] = {{0}};
    static uint64_t specials[256][max_inputs];
    int special_count = 0;
    for (int i = 2; i < argc; i++) {
        const char *o = argv[i];
        const char *v = i + 1 < argc ? argv[i + 1] : NULL;
        if (!v) {
            fprintf(stderr, "oracle: %s needs a value\n", o);
            return 2;
        }
        i++;
        if (strcmp(o, "--fn") == 0) fn = find_function(v);
        else if (strcmp(o, "--width") == 0) {
            if (!parse_width(v, &f)) {
                fprintf(stderr, "oracle: width is 32 or 64\n");
                return 2;
            }
        } else if (strcmp(o, "--seed") == 0) seed = strtoull(v, NULL, 0);
        else if (strcmp(o, "--count") == 0) count = strtoull(v, NULL, 0);
        else if (strcmp(o, "--random") == 0) random_count = strtoull(v, NULL, 0);
        else if (strcmp(o, "--hard") == 0) hard_count = strtoull(v, NULL, 0);
        else if (strcmp(o, "--pool") == 0) pool = strtoull(v, NULL, 0);
        else if (strcmp(o, "--bound") == 0) bound = strtod(v, NULL);
        else if (strcmp(o, "--show") == 0) show = strtol(v, NULL, 0);
        else if (strcmp(o, "--norm") == 0) normwise = strcmp(v, "yes") == 0;
        else if (strcmp(o, "--domain") == 0) parse_domain(&domains[0], v);
        else if (strcmp(o, "--domain2") == 0) parse_domain(&domains[1], v);
        else if (strcmp(o, "--domain3") == 0) parse_domain(&domains[2], v);
        else if (strcmp(o, "--domain4") == 0) parse_domain(&domains[3], v);
        else if (strcmp(o, "--special") == 0) {
            if (special_count == 256) {
                fprintf(stderr, "oracle: too many specials\n");
                return 2;
            }
            char *end = (char *)v;
            for (int k = 0; k < max_inputs; k++) {
                specials[special_count][k] = strtoull(end, &end, 16);
                if (*end != ',') break;
                end++;
            }
            special_count++;
        } else {
            fprintf(stderr, "oracle: unknown option %s\n", o);
            return 2;
        }
    }
    if (!fn || !f) {
        fprintf(stderr, "oracle: --fn and --width are required\n");
        return 2;
    }
    int arity = fn->inputs, outputs = fn->outputs;
    for (int k = 0; k < arity; k++)
        if (domains[k].count == 0) parse_domain(&domains[k], "bits");
    seed_rng(seed);
    mpfr_t a[max_inputs];

    if (strcmp(mode, "cases") == 0) {
        for (int s = 0; s < special_count; s++) case_line(f, fn, specials[s]);
        for (uint64_t n = 0; n < random_count; n++) {
            uint64_t in[max_inputs];
            for (int k = 0; k < arity; k++) in[k] = draw(f, &domains[k]);
            case_line(f, fn, in);
        }
        if (hard_count > 0) {
            candidate_t *c = calloc(pool, sizeof *c);
            mpfr_t z[max_outputs];
            for (int k = 0; k < outputs; k++) mpfr_init2(z[k], exact_precision);
            for (uint64_t n = 0; n < pool; n++) {
                for (int k = 0; k < arity; k++) c[n].in[k] = draw(f, &domains[k]);
                set_inputs(f, arity, c[n].in, a);
                exact(fn, z, a);
                c[n].hard = 1.0;
                for (int k = 0; k < outputs; k++) {
                    double h = hardness(f, z[k]);
                    if (h < c[n].hard) c[n].hard = h;
                }
                clear_inputs(arity, a);
            }
            qsort(c, pool, sizeof *c, by_hardness);
            for (uint64_t n = 0; n < hard_count && n < pool; n++) {
                if (c[n].hard >= 1.0) break;
                case_line(f, fn, c[n].in);
            }
            for (int k = 0; k < outputs; k++) mpfr_clear(z[k]);
            free(c);
        }
        return 0;
    }

    if (strcmp(mode, "inputs") == 0) {
        size_t bytes = f->width / 8;
        for (uint64_t n = 0; n < count; n++)
            for (int k = 0; k < arity; k++) {
                uint64_t b = draw(f, &domains[k]);
                fwrite(&b, bytes, 1, stdout);
            }
        return 0;
    }

    if (strcmp(mode, "check") == 0) {
        size_t bytes = f->width / 8;
        uint64_t records = 0, wrong = 0, past = 0;
        double worst = -1.0;
        uint64_t worst_in[max_inputs] = {0}, worst_out[max_outputs] = {0};
        mpfr_t z[max_outputs];
        for (int k = 0; k < outputs; k++) mpfr_init2(z[k], exact_precision);
        for (;;) {
            uint64_t in[max_inputs] = {0}, out[max_outputs] = {0};
            int k;
            for (k = 0; k < arity; k++)
                if (fread(&in[k], bytes, 1, stdin) != 1) break;
            if (k < arity) break;
            for (k = 0; k < outputs; k++)
                if (fread(&out[k], bytes, 1, stdin) != 1) break;
            if (k < outputs) break;
            records++;
            set_inputs(f, arity, in, a);
            double rounded[max_outputs];
            correctly_rounded(f, fn, a, rounded);
            int same = 1;
            for (k = 0; k < outputs; k++) {
                double c = bits_to_double(f, out[k]);
                if (!(double_to_bits(f, rounded[k]) == out[k]
                      || (isnan(rounded[k]) && isnan(c))))
                    same = 0;
            }
            if (same) {
                clear_inputs(arity, a);
                continue;
            }
            wrong++;
            exact(fn, z, a);
            double err = 0.0;
            mpfr_t norm;
            mpfr_init2(norm, exact_precision);
            if (normwise && outputs == 2) {
                mpfr_abs(norm, z[0], MPFR_RNDN);
                if (mpfr_cmpabs(z[1], norm) > 0) mpfr_abs(norm, z[1], MPFR_RNDN);
            }
            int both_zero = outputs == 2 && rounded[0] == 0.0 && rounded[1] == 0.0;
            for (k = 0; k < outputs; k++) {
                int whole = normwise && outputs == 2 && !mpfr_nan_p(norm) && !mpfr_inf_p(norm);
                double c = bits_to_double(f, out[k]), r = rounded[k];
                if (outputs == 2 && isnan(rounded[1 - k])) {
                    c = fabs(c);
                    r = fabs(r);
                    mpfr_abs(z[k], z[k], MPFR_RNDN);
                }
                double e = ulp_error(f, c, r, z[k], whole ? norm : z[k],
                                     !normwise || both_zero);
                if (e > err) err = e;
            }
            mpfr_clear(norm);
            clear_inputs(arity, a);
            if (err > bound) {
                past++;
                if (show > 0) {
                    show--;
                    fprintf(stderr, "past bound:");
                    for (int j = 0; j < arity; j++)
                        fprintf(stderr, " %a", bits_to_double(f, in[j]));
                    fprintf(stderr, " ->");
                    for (k = 0; k < outputs; k++)
                        fprintf(stderr, " %a", bits_to_double(f, out[k]));
                    fprintf(stderr, ", correctly rounded");
                    for (k = 0; k < outputs; k++) fprintf(stderr, " %a", rounded[k]);
                    fprintf(stderr, ", error %g ulp\n", err);
                }
            }
            if (err > worst) {
                worst = err;
                memcpy(worst_in, in, sizeof in);
                memcpy(worst_out, out, sizeof out);
            }
        }
        for (int k = 0; k < outputs; k++) mpfr_clear(z[k]);
        printf("{\"function\": \"%s\", \"width\": %d, \"records\": %" PRIu64
               ", \"not_correctly_rounded\": %" PRIu64 ", \"past_bound\": %" PRIu64,
               fn->name, f->width, records, wrong, past);
        if (worst < 0) {
            printf(", \"max_ulp\": 0}\n");
        } else {
            printf(", \"max_ulp\": %.4f, \"at\": [", isinf(worst) ? 1e300 : worst);
            for (int j = 0; j < arity; j++)
                printf("%s\"%a\"", j ? ", " : "", bits_to_double(f, worst_in[j]));
            printf("], \"gives\": ");
            if (outputs == 1) {
                printf("\"%a\"}\n", bits_to_double(f, worst_out[0]));
            } else {
                printf("[");
                for (int k = 0; k < outputs; k++)
                    printf("%s\"%a\"", k ? ", " : "", bits_to_double(f, worst_out[k]));
                printf("]}\n");
            }
        }
        return past > 0;
    }

    fprintf(stderr, "oracle: unknown mode %s\n", mode);
    return 2;
}
