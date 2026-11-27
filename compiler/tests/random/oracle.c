/*  The values runtime/random-draws and runtime/random-normal-draws
    expect, printed from xoshiro256**'s reference implementation and
    core/random's draws ported to C over it.

    `rotl`, `next` and `jump` below are copied unchanged from Blackman and
    Vigna's xoshiro256starstar.c, https://prng.di.unimi.it/, whose notice
    follows; the file read had SHA-256
    01d518abeb28cdfc86d2d019f0ae4678fff37f25bc306c7367ee5298a7f443a7.
    `splitmix` is their splitmix64.c's `next` over a seed passed in.  The
    draws after them are ports of core/random/random.ldn's, line for line;
    `normal` and `exponential` call the C library's log and sqrt, which
    core/math's may differ from in the last place, so the fixture compares
    those within a stated distance rather than bit for bit.

    Build and run inside `nix develop`:

        cc -O2 -o /tmp/random-oracle compiler/tests/random/oracle.c -lm
        /tmp/random-oracle
*/

/*  Written in 2018 by David Blackman and Sebastiano Vigna (vigna@acm.org)

To the extent possible under law, the author has dedicated all copyright
and related and neighboring rights to this software to the public domain
worldwide.

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR
IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE. */

#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static inline uint64_t rotl(const uint64_t x, int k) {
	return (x << k) | (x >> (64 - k));
}


static uint64_t s[4];

uint64_t next(void) {
	const uint64_t result = rotl(s[1] * 5, 7) * 9;

	const uint64_t t = s[1] << 17;

	s[2] ^= s[0];
	s[3] ^= s[1];
	s[1] ^= s[2];
	s[0] ^= s[3];

	s[2] ^= t;

	s[3] = rotl(s[3], 45);

	return result;
}


/* This is the jump function for the generator. It is equivalent
   to 2^128 calls to next(); it can be used to generate 2^128
   non-overlapping subsequences for parallel computations. */

void jump(void) {
	static const uint64_t JUMP[] = { 0x180ec6d33cfd0aba, 0xd5a61266f0c9392c, 0xa9582618e03fc9aa, 0x39abdc4529b1661c };

	uint64_t s0 = 0;
	uint64_t s1 = 0;
	uint64_t s2 = 0;
	uint64_t s3 = 0;
	for(int i = 0; i < sizeof JUMP / sizeof *JUMP; i++)
		for(int b = 0; b < 64; b++) {
			if (JUMP[i] & UINT64_C(1) << b) {
				s0 ^= s[0];
				s1 ^= s[1];
				s2 ^= s[2];
				s3 ^= s[3];
			}
			next();	
		}
		
	s[0] = s0;
	s[1] = s1;
	s[2] = s2;
	s[3] = s3;
}

/* The end of the reference implementation's code. */

static uint64_t splitmix(uint64_t *x) {
	uint64_t z = (*x += 0x9e3779b97f4a7c15);
	z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9;
	z = (z ^ (z >> 27)) * 0x94d049bb133111eb;
	return z ^ (z >> 31);
}

static void seed(uint64_t value) {
	for (int i = 0; i < 4; i++) s[i] = splitmix(&value);
}

static uint64_t below(uint64_t bound) {
	uint64_t mask = bound - 1;
	mask |= mask >> 1; mask |= mask >> 2; mask |= mask >> 4;
	mask |= mask >> 8; mask |= mask >> 16; mask |= mask >> 32;
	for (;;) {
		uint64_t value = next() & mask;
		if (value < bound) return value;
	}
}

static double unit_f64(void) { return (double)(next() >> 11) * 0x1.0p-53; }
static float unit_f32(void) { return (float)(next() >> 40) * 0x1.0p-24f; }

static uint64_t between_u64(uint64_t low, uint64_t high) {
	uint64_t width = high - low;
	return width == UINT64_MAX ? next() : low + below(width + 1);
}

static int64_t between_i64(int64_t low, int64_t high) {
	uint64_t place = between_u64((uint64_t)low ^ (UINT64_C(1) << 63),
	                             (uint64_t)high ^ (UINT64_C(1) << 63));
	return (int64_t)(place ^ (UINT64_C(1) << 63));
}

static void sample(int *into, size_t wanted, const int *from, size_t left) {
	size_t at = 0;
	for (size_t i = 0; wanted > 0; i++) {
		if (below(left) < wanted) { into[at++] = from[i]; wanted--; }
		left--;
	}
}

static size_t weighted(const uint64_t *weights, size_t count) {
	uint64_t total = 0, running = 0;
	for (size_t i = 0; i < count; i++) total += weights[i];
	uint64_t drawn = below(total);
	for (size_t i = 0; i < count; i++) {
		running += weights[i];
		if (drawn < running) return i;
	}
	return count;
}

static double normal(void) {
	for (;;) {
		double u = 2.0 * unit_f64() - 1.0;
		double v = 2.0 * unit_f64() - 1.0;
		double t = u * u + v * v;
		if (t < 1.0 && t > 0.0) return u * sqrt(-2.0 * log(t) / t);
	}
}

static double exponential(void) { return 0.0 - log(1.0 - unit_f64()); }

static uint64_t bits_f64(double x) { uint64_t b; memcpy(&b, &x, 8); return b; }
static uint32_t bits_f32(float x) { uint32_t b; memcpy(&b, &x, 4); return b; }

static void list_u64(const char *name, const uint64_t *values, int count) {
	printf("%s: [%d]u64 = [", name, count);
	for (int i = 0; i < count; i++)
		printf("%s0x%016" PRIx64, i ? (i % 3 ? ", " : ",\n    ") : "", values[i]);
	printf("]\n");
}

int main(void) {
	uint64_t v[64];

	seed(42);
	for (int i = 0; i < 8; i++) v[i] = bits_f64(unit_f64());
	list_u64("unit_f64_bits", v, 8);
	seed(42);
	for (int i = 0; i < 8; i++) v[i] = bits_f32(unit_f32());
	list_u64("unit_f32_bits", v, 8);

	{
		static const uint64_t ranges[][2] = {
			{1, 6}, {0, UINT64_MAX}, {UINT64_MAX - 1, UINT64_MAX},
			{10, (UINT64_C(1) << 63) + 10}};
		seed(0x0123456789abcdef);
		int at = 0;
		for (int r = 0; r < 4; r++)
			for (int i = 0; i < 4; i++) v[at++] = between_u64(ranges[r][0], ranges[r][1]);
		list_u64("between_u64_draws", v, 16);
	}
	{
		static const int64_t ranges[][2] = {
			{-3, 3}, {INT64_MIN, INT64_MAX}, {INT64_MIN, INT64_MIN + 1},
			{-1000, 1000}};
		seed(0x0123456789abcdef);
		int at = 0;
		for (int r = 0; r < 4; r++)
			for (int i = 0; i < 4; i++) v[at++] = (uint64_t)between_i64(ranges[r][0], ranges[r][1]);
		printf("-- between_i64_draws, as i64:");
		for (int i = 0; i < 16; i++) printf(" %" PRId64, (int64_t)v[i]);
		printf("\n");
	}
	{
		seed(7);
		printf("-- pick of 0..9 from seed 7:");
		for (int i = 0; i < 8; i++) printf(" %" PRIu64, below(10));
		printf("\n");
	}
	{
		int from[10] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}, into[4];
		seed(9);
		printf("-- sample 4 of 0..9 from seed 9, three times:");
		for (int k = 0; k < 3; k++) {
			sample(into, 4, from, 10);
			for (int i = 0; i < 4; i++) printf(" %d", into[i]);
			printf(" |");
		}
		printf("\n");
	}
	{
		static const uint64_t w[4] = {1, 0, 3, 6};
		seed(11);
		printf("-- weighted [1, 0, 3, 6] from seed 11:");
		for (int i = 0; i < 12; i++) printf(" %zu", weighted(w, 4));
		printf("\n");
	}
	{
		uint8_t bytes[21];
		seed(5);
		for (int i = 0; i < 21; i += 8) {
			uint64_t x = next();
			for (int j = 0; j < 8 && i + j < 21; j++) bytes[i + j] = (uint8_t)(x >> (8 * j));
		}
		printf("-- fill 21 bytes from seed 5:");
		for (int i = 0; i < 21; i++) printf(" %u", bytes[i]);
		printf("\n");
	}
	seed(3);
	for (int i = 0; i < 8; i++) v[i] = bits_f64(normal());
	list_u64("normal_bits", v, 8);
	seed(3);
	for (int i = 0; i < 8; i++) v[i] = bits_f64(exponential());
	list_u64("exponential_bits", v, 8);

	seed(0);
	jump();
	for (int i = 0; i < 4; i++) v[i] = next();
	seed(0);
	jump();
	jump();
	for (int i = 4; i < 8; i++) v[i] = next();
	list_u64("jumped_draws", v, 8);
	{
		uint64_t hash = 0xcbf29ce484222325;
		seed(1);
		for (int i = 0; i < 1000; i++) {
			uint64_t b = bits_f64(normal()) ^ bits_f64(exponential());
			for (int j = 0; j < 8; j++) { hash ^= (b >> (8 * j)) & 0xff; hash *= 0x100000001b3; }
		}
		printf("-- digest of 1000 normal ^ exponential from seed 1, by this C library's log;\n-- the fixture pins core/math's, which differs in the last place: 0x%016" PRIx64 "\n", hash);
	}
	return 0;
}
