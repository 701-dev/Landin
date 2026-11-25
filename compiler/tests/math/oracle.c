/*  The oracle core/math is measured against: MPFR's correctly rounded
    values, computed outside the program under test.

    scripts/math_oracle.py builds this file against the MPFR and GMP of
    flake.lock's nixpkgs and runs it; see compiler/tests/math/README.md.

      oracle cases --fn NAME --width 32|64 --seed N --random N --hard N
                   [--pool N] [--domain SPEC]... [--domain2 SPEC]...
                   [--domain3 SPEC]... [--special HEX[,HEX[,HEX]]]...
          Prints one case per line: the inputs' bits and the correctly
          rounded result's bits, in hexadecimal at the width.  The cases
          are the specials, then `random` inputs drawn from the domains,
          then the `hard` inputs of a pool of `pool` draws whose exact
          results lie nearest a rounding boundary of the width.

      oracle inputs --fn NAME --width 32|64 --seed N --count N
                    [--domain SPEC]... [--domain2 SPEC]... [--domain3 SPEC]...
          Writes `count` input records to standard output, each input in
          little-endian bytes at the width, for compiler/tests/math/
          evaluate.ldn to read.

      oracle check --fn NAME --width 32|64 [--bound ULP] [--show N]
          Reads records from standard input, each the inputs then the
          result under test, little-endian at the width, and prints one
          JSON object: the count, the largest error in units in the last
          place of the exact result and an input that gives it, the count
          of results not correctly rounded and the count past `bound`.

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
    rounded zero's is an infinite error too. */

#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <gmp.h>
#include <mpfr.h>

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
    F_ERF, F_ERFC, F_GAMMA, F_LOG_GAMMA
} fn_kind;

typedef struct {
    const char *name;
    fn_kind kind;
    int arity;
} fn_t;

static const fn_t functions[] = {
    {"sqrt", F_SQRT, 1}, {"cbrt", F_CBRT, 1}, {"hypot", F_HYPOT, 2},
    {"fma", F_FMA, 3}, {"floor", F_FLOOR, 1}, {"ceil", F_CEIL, 1},
    {"trunc", F_TRUNC, 1}, {"round", F_ROUND, 1},
    {"round_even", F_ROUND_EVEN, 1}, {"remainder", F_REMAINDER, 2},
    {"remainder_nearest", F_REMAINDER_NEAREST, 2},
    {"exp", F_EXP, 1}, {"exp2", F_EXP2, 1}, {"expm1", F_EXPM1, 1},
    {"log", F_LOG, 1}, {"log2", F_LOG2, 1}, {"log10", F_LOG10, 1},
    {"log1p", F_LOG1P, 1}, {"pow", F_POW, 2},
    {"sin", F_SIN, 1}, {"cos", F_COS, 1}, {"tan", F_TAN, 1},
    {"asin", F_ASIN, 1}, {"acos", F_ACOS, 1}, {"atan", F_ATAN, 1},
    {"atan2", F_ATAN2, 2},
    {"sinh", F_SINH, 1}, {"cosh", F_COSH, 1}, {"tanh", F_TANH, 1},
    {"asinh", F_ASINH, 1}, {"acosh", F_ACOSH, 1}, {"atanh", F_ATANH, 1},
    {"erf", F_ERF, 1}, {"erfc", F_ERFC, 1}, {"gamma", F_GAMMA, 1},
    {"log_gamma", F_LOG_GAMMA, 1},
};

static const fn_t *find_function(const char *name) {
    for (size_t i = 0; i < sizeof functions / sizeof functions[0]; i++)
        if (strcmp(functions[i].name, name) == 0) return &functions[i];
    fprintf(stderr, "oracle: no function %s\n", name);
    exit(2);
}

/* y = f(a[, b[, c]]) rounded to y's precision; returns MPFR's ternary. */
static int evaluate(const fn_t *fn, mpfr_t y, mpfr_t *a) {
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
    }
    return 0;
}

/* The correctly rounded result at the format, as a double. */
static double correctly_rounded(const format_t *f, const fn_t *fn, mpfr_t *a) {
    mpfr_exp_t old_min = mpfr_get_emin(), old_max = mpfr_get_emax();
    mpfr_t y;
    mpfr_init2(y, f->precision);
    mpfr_set_emin(f->emin);
    mpfr_set_emax(f->emax);
    int t = evaluate(fn, y, a);
    t = mpfr_check_range(y, t, MPFR_RNDN);
    mpfr_subnormalize(y, t, MPFR_RNDN);
    double d = mpfr_get_d(y, MPFR_RNDN);
    mpfr_set_emin(old_min);
    mpfr_set_emax(old_max);
    mpfr_clear(y);
    return d;
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

/* |c - z| / ulp(z) for the exact z, or INFINITY as the header says. */
static double ulp_error(const format_t *f, double c, double rounded, mpfr_t z) {
    if (mpfr_nan_p(z)) return isnan(c) ? 0.0 : INFINITY;
    if (isnan(c)) return INFINITY;
    if (isinf(rounded) || isinf(c)) return c == rounded ? 0.0 : INFINITY;
    if (c == 0.0 && rounded == 0.0 && signbit(c) != signbit(rounded))
        return INFINITY;
    if (mpfr_zero_p(z)) return fabs(c) / ldexp(1.0, f->subnormal_ulp);
    long e = mpfr_get_exp(z) - f->precision;
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

static void print_case(const format_t *f, int arity, const uint64_t *in, double out) {
    int digits = f->width / 4;
    for (int i = 0; i < arity; i++) printf("%0*" PRIx64 " ", digits, in[i]);
    printf("%0*" PRIx64 "\n", digits, double_to_bits(f, out));
}

typedef struct {
    uint64_t in[3];
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
    domains_t domains[3] = {{0}};
    uint64_t specials[256][3];
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
        else if (strcmp(o, "--domain") == 0) parse_domain(&domains[0], v);
        else if (strcmp(o, "--domain2") == 0) parse_domain(&domains[1], v);
        else if (strcmp(o, "--domain3") == 0) parse_domain(&domains[2], v);
        else if (strcmp(o, "--special") == 0) {
            if (special_count == 256) {
                fprintf(stderr, "oracle: too many specials\n");
                return 2;
            }
            char *end = (char *)v;
            for (int k = 0; k < 3; k++) {
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
    for (int k = 0; k < fn->arity; k++)
        if (domains[k].count == 0) parse_domain(&domains[k], "bits");
    seed_rng(seed);
    int arity = fn->arity;
    mpfr_t a[3];

    if (strcmp(mode, "cases") == 0) {
        for (int s = 0; s < special_count; s++) {
            set_inputs(f, arity, specials[s], a);
            print_case(f, arity, specials[s], correctly_rounded(f, fn, a));
            clear_inputs(arity, a);
        }
        for (uint64_t n = 0; n < random_count; n++) {
            uint64_t in[3];
            for (int k = 0; k < arity; k++) in[k] = draw(f, &domains[k]);
            set_inputs(f, arity, in, a);
            print_case(f, arity, in, correctly_rounded(f, fn, a));
            clear_inputs(arity, a);
        }
        if (hard_count > 0) {
            candidate_t *c = calloc(pool, sizeof *c);
            mpfr_t z;
            mpfr_init2(z, exact_precision);
            for (uint64_t n = 0; n < pool; n++) {
                for (int k = 0; k < arity; k++) c[n].in[k] = draw(f, &domains[k]);
                set_inputs(f, arity, c[n].in, a);
                evaluate(fn, z, a);
                c[n].hard = hardness(f, z);
                clear_inputs(arity, a);
            }
            qsort(c, pool, sizeof *c, by_hardness);
            for (uint64_t n = 0; n < hard_count && n < pool; n++) {
                if (c[n].hard >= 1.0) break;
                set_inputs(f, arity, c[n].in, a);
                print_case(f, arity, c[n].in, correctly_rounded(f, fn, a));
                clear_inputs(arity, a);
            }
            mpfr_clear(z);
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
        uint64_t worst_in[3] = {0}, worst_out = 0;
        mpfr_t z;
        mpfr_init2(z, exact_precision);
        for (;;) {
            uint64_t in[3] = {0}, out = 0;
            int k;
            for (k = 0; k < arity; k++)
                if (fread(&in[k], bytes, 1, stdin) != 1) break;
            if (k < arity || fread(&out, bytes, 1, stdin) != 1) break;
            records++;
            set_inputs(f, arity, in, a);
            double rounded = correctly_rounded(f, fn, a);
            double c = bits_to_double(f, out);
            if (double_to_bits(f, rounded) == out
                || (isnan(rounded) && isnan(c))) {
                clear_inputs(arity, a);
                continue;
            }
            wrong++;
            evaluate(fn, z, a);
            double err = ulp_error(f, c, rounded, z);
            clear_inputs(arity, a);
            if (err > bound) {
                past++;
                if (show > 0) {
                    show--;
                    fprintf(stderr, "past bound:");
                    for (int j = 0; j < arity; j++)
                        fprintf(stderr, " %a", bits_to_double(f, in[j]));
                    fprintf(stderr, " -> %a, correctly rounded %a, error %g ulp\n",
                            c, rounded, err);
                }
            }
            if (err > worst) {
                worst = err;
                memcpy(worst_in, in, sizeof in);
                worst_out = out;
            }
        }
        mpfr_clear(z);
        printf("{\"function\": \"%s\", \"width\": %d, \"records\": %" PRIu64
               ", \"not_correctly_rounded\": %" PRIu64 ", \"past_bound\": %" PRIu64,
               fn->name, f->width, records, wrong, past);
        if (worst < 0) {
            printf(", \"max_ulp\": 0}\n");
        } else {
            printf(", \"max_ulp\": %.4f, \"at\": [", isinf(worst) ? 1e300 : worst);
            for (int j = 0; j < arity; j++)
                printf("%s\"%a\"", j ? ", " : "", bits_to_double(f, worst_in[j]));
            printf("], \"gives\": \"%a\"}\n", bits_to_double(f, worst_out));
        }
        return past > 0;
    }

    fprintf(stderr, "oracle: unknown mode %s\n", mode);
    return 2;
}
