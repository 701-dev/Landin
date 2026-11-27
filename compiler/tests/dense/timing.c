/* The BLAS's side of scripts/dense_timing.py: the product timing.ldn
   computes, with cblas_dgemm over column-major storage, and the same
   checksum line, with the nanoseconds the product alone took.  Built against OpenBLAS and run on one thread. */
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <cblas.h>

enum { size = 1000 };

int main(void) {
    double *a = malloc(sizeof(double) * size * size);
    double *b = malloc(sizeof(double) * size * size);
    double *c = malloc(sizeof(double) * size * size);
    if (!a || !b || !c) return 1;
    for (long j = 0; j < size; j++)
        for (long i = 0; i < size; i++) {
            a[i + j * size] = (double)((i * 7 + j * 13) % 17) - 8.0;
            b[i + j * size] = (double)((i * 11 + j * 5) % 17) - 8.0;
        }
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    cblas_dgemm(CblasColMajor, CblasNoTrans, CblasNoTrans, size, size, size,
                1.0, a, size, b, size, 0.0, c, size);
    clock_gettime(CLOCK_MONOTONIC, &end);
    long long nanoseconds = (long long)(end.tv_sec - start.tv_sec) * 1000000000LL
                            + (end.tv_nsec - start.tv_nsec);
    long long checksum = 0;
    for (long k = 0; k < (long)size * size; k++) checksum += (long long)c[k];
    printf("checksum %lld nanoseconds %lld\n", checksum, nanoseconds);
    return 0;
}
