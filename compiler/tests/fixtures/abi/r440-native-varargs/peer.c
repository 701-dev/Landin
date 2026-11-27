#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>

static int32_t collect(int32_t count, va_list arguments) {
    static const int expected[] = {-7, 250, -30000, 60000, 1, 6, 7, 8, 9, 10};
    if (count != 10) return 1;
    for (int i = 0; i < count; ++i) {
        int integer = va_arg(arguments, int);
        double real = va_arg(arguments, double);
        if (integer != expected[i] || real != i + 0.5) return 2;
    }
    return 42;
}
int32_t c_collect(int32_t count, ...) {
    va_list arguments;
    va_start(arguments, count);
    int32_t result = collect(count, arguments);
    va_end(arguments);
    return result;
}
int32_t c_fixed(double bias, int32_t count, ...) {
    va_list arguments;
    va_start(arguments, count);
    int32_t result = collect(count, arguments);
    va_end(arguments);
    return bias == 12.5 ? result : 3;
}

#if defined(_WIN32)
/* Windows has no vector count: Win64 puts each variadic double in the
   first four slots in both banks, the integer register and the XMM
   register of its slot, and arm64 Windows puts every variadic in the
   integer registers and the stack.  The probe answers what al's would, the
   count of floats capped at the eight vector registers, from the floats C
   reads by va_arg, and on x86-64 its assembly first holds each float in
   the register slots to both banks. */
#if defined(__x86_64__)
#define PROBE_COUNT probe_count
#else
#define PROBE_COUNT probe_al
#endif
int32_t PROBE_COUNT(int32_t count, ...) {
    va_list arguments;
    va_start(arguments, count);
    int32_t result = count < 8 ? count : 8;
    for (int i = 0; i < count; ++i)
        if (va_arg(arguments, double) != i + 0.5) result = -1;
    va_end(arguments);
    return result;
}
#if defined(__x86_64__)
__asm__(".text\n"
        ".globl probe_al\n"
        "probe_al:\n"
        "cmpl $1, %ecx\n"
        "jl 1f\n"
        "movq %xmm1, %rax\n"
        "cmpq %rax, %rdx\n"
        "jne 2f\n"
        "cmpl $2, %ecx\n"
        "jl 1f\n"
        "movq %xmm2, %rax\n"
        "cmpq %rax, %r8\n"
        "jne 2f\n"
        "cmpl $3, %ecx\n"
        "jl 1f\n"
        "movq %xmm3, %rax\n"
        "cmpq %rax, %r9\n"
        "jne 2f\n"
        "1: jmp probe_count\n"
        "2: movl $-1, %eax\n"
        "ret\n");
#endif
#else
/* Only this observation needs assembly: C's va_start distinguishes zero
   from nonzero but does not expose the exact vector-register count. The
   actual variadic transport above is independently checked by C va_arg. */
__asm__(".text\n"
        ".globl probe_al\n"
        ".type probe_al, @function\n"
        "probe_al:\n"
        "movzbl %al, %eax\n"
        "ret\n"
        ".size probe_al, .-probe_al\n");
#endif
extern int32_t landin_check(void);
int main(void) {
    if (c_collect(10, -7, 0.5, 250, 1.5, -30000, 2.5, 60000, 3.5,
                  1, 4.5, 6, 5.5, 7, 6.5, 8, 7.5, 9, 8.5, 10, 9.5) != 42)
        return 1;
    if (landin_check() != 42) return 2;
    puts("native varargs ok");
    return 42;
}
