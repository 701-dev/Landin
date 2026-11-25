/* SR-1694: Win64 makes a callee save rbx, rbp, rdi, rsi, r12 to r15 and
 * xmm6 to xmm15 whole.  r_probe sets each to a sentinel, enters the
 * Landin callback through the pointer it is given, and records in
 * r_probe_clobbered a bit for each register that came back changed. */
#include <stdint.h>
#include <stdio.h>

uint64_t r_probe_clobbered;
extern int64_t landin_churn(int64_t);
int64_t r_probe(int64_t (*callback)(int64_t), int64_t seed);

int64_t c_mix(int64_t value, double scale)
{
    /* Volatile registers are the callee's to clobber. */
    __asm__ volatile ("" : : : "rax", "rcx", "rdx", "r8", "r9", "r10", "r11",
                      "xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "memory");
    return (value + (scale > 1.0 ? 1 : 2)) % 1000003;
}

#define SAVE_XMM(n, at) "movdqu %%xmm" #n ", " #at "(%%rsp)\n"
#define LOAD_XMM(n, at) "movdqu " #at "(%%rsp), %%xmm" #n "\n"
#define SENTINEL_XMM(n) "movabsq $0x6000000000000" #n "0" #n ", %%rax\n" \
    "movq %%rax, %%xmm" #n "\n" "punpcklqdq %%xmm" #n ", %%xmm" #n "\n"
/* Both halves of xmm N against the sentinel; bit B on a difference. */
#define CHECK_XMM(n, b) "movq %%xmm" #n ", %%r10\n" \
    "pshufd $0xEE, %%xmm" #n ", %%xmm0\n" "movq %%xmm0, %%r9\n" \
    "movabsq $0x6000000000000" #n "0" #n ", %%rax\n" \
    "cmpq %%rax, %%r10\n" "jne 1f\n" "cmpq %%rax, %%r9\n" "je 2f\n" \
    "1: orq $" #b ", %%r11\n" "2:\n"
#define CHECK_GP(r, v, b) "movabsq $" #v ", %%rax\n" "cmpq %%rax, %%" #r "\n" \
    "je 3f\n" "orq $" #b ", %%r11\n" "3:\n"

__attribute__((naked)) int64_t r_probe(int64_t (*callback)(int64_t), int64_t seed)
{
    __asm__ volatile (
        "pushq %%rbx\n" "pushq %%rbp\n" "pushq %%rdi\n" "pushq %%rsi\n"
        "pushq %%r12\n" "pushq %%r13\n" "pushq %%r14\n" "pushq %%r15\n"
        /* 8 pushes after the return address leave rsp 8 off sixteen; 200
         * bytes hold the shadow area, ten xmm saves and the result. */
        "subq $200, %%rsp\n"
        SAVE_XMM(6, 32) SAVE_XMM(7, 48) SAVE_XMM(8, 64) SAVE_XMM(9, 80)
        SAVE_XMM(10, 96) SAVE_XMM(11, 112) SAVE_XMM(12, 128)
        SAVE_XMM(13, 144) SAVE_XMM(14, 160) SAVE_XMM(15, 176)
        "movq %%rcx, %%r10\n" "movq %%rdx, %%rcx\n"
        "movabsq $0x1111111111111111, %%rbx\n"
        "movabsq $0x2222222222222222, %%rbp\n"
        "movabsq $0x3333333333333333, %%rdi\n"
        "movabsq $0x4444444444444444, %%rsi\n"
        "movabsq $0x5555555555555555, %%r12\n"
        "movabsq $0x6666666666666666, %%r13\n"
        "movabsq $0x7777777777777777, %%r14\n"
        "movabsq $0x0888888888888888, %%r15\n"
        SENTINEL_XMM(6) SENTINEL_XMM(7) SENTINEL_XMM(8) SENTINEL_XMM(9)
        "movabsq $0x600000000000010a, %%rax\n" "movq %%rax, %%xmm10\n" "punpcklqdq %%xmm10, %%xmm10\n"
        "movabsq $0x600000000000011b, %%rax\n" "movq %%rax, %%xmm11\n" "punpcklqdq %%xmm11, %%xmm11\n"
        "movabsq $0x600000000000012c, %%rax\n" "movq %%rax, %%xmm12\n" "punpcklqdq %%xmm12, %%xmm12\n"
        "movabsq $0x600000000000013d, %%rax\n" "movq %%rax, %%xmm13\n" "punpcklqdq %%xmm13, %%xmm13\n"
        "movabsq $0x600000000000014e, %%rax\n" "movq %%rax, %%xmm14\n" "punpcklqdq %%xmm14, %%xmm14\n"
        "movabsq $0x600000000000015f, %%rax\n" "movq %%rax, %%xmm15\n" "punpcklqdq %%xmm15, %%xmm15\n"
        "callq *%%r10\n"
        "movq %%rax, 192(%%rsp)\n"
        "xorl %%r11d, %%r11d\n"
        CHECK_GP(rbx, 0x1111111111111111, 0x1)
        CHECK_GP(rbp, 0x2222222222222222, 0x2)
        CHECK_GP(rdi, 0x3333333333333333, 0x4)
        CHECK_GP(rsi, 0x4444444444444444, 0x8)
        CHECK_GP(r12, 0x5555555555555555, 0x10)
        CHECK_GP(r13, 0x6666666666666666, 0x20)
        CHECK_GP(r14, 0x7777777777777777, 0x40)
        CHECK_GP(r15, 0x0888888888888888, 0x80)
        CHECK_XMM(6, 0x100) CHECK_XMM(7, 0x200) CHECK_XMM(8, 0x400)
        CHECK_XMM(9, 0x800)
        "movq %%xmm10, %%r10\n" "pshufd $0xEE, %%xmm10, %%xmm0\n" "movq %%xmm0, %%r9\n"
        "movabsq $0x600000000000010a, %%rax\n" "cmpq %%rax, %%r10\n" "jne 1f\n" "cmpq %%rax, %%r9\n" "je 2f\n" "1: orq $0x1000, %%r11\n" "2:\n"
        "movq %%xmm11, %%r10\n" "pshufd $0xEE, %%xmm11, %%xmm0\n" "movq %%xmm0, %%r9\n"
        "movabsq $0x600000000000011b, %%rax\n" "cmpq %%rax, %%r10\n" "jne 1f\n" "cmpq %%rax, %%r9\n" "je 2f\n" "1: orq $0x2000, %%r11\n" "2:\n"
        "movq %%xmm12, %%r10\n" "pshufd $0xEE, %%xmm12, %%xmm0\n" "movq %%xmm0, %%r9\n"
        "movabsq $0x600000000000012c, %%rax\n" "cmpq %%rax, %%r10\n" "jne 1f\n" "cmpq %%rax, %%r9\n" "je 2f\n" "1: orq $0x4000, %%r11\n" "2:\n"
        "movq %%xmm13, %%r10\n" "pshufd $0xEE, %%xmm13, %%xmm0\n" "movq %%xmm0, %%r9\n"
        "movabsq $0x600000000000013d, %%rax\n" "cmpq %%rax, %%r10\n" "jne 1f\n" "cmpq %%rax, %%r9\n" "je 2f\n" "1: orq $0x8000, %%r11\n" "2:\n"
        "movq %%xmm14, %%r10\n" "pshufd $0xEE, %%xmm14, %%xmm0\n" "movq %%xmm0, %%r9\n"
        "movabsq $0x600000000000014e, %%rax\n" "cmpq %%rax, %%r10\n" "jne 1f\n" "cmpq %%rax, %%r9\n" "je 2f\n" "1: orq $0x10000, %%r11\n" "2:\n"
        "movq %%xmm15, %%r10\n" "pshufd $0xEE, %%xmm15, %%xmm0\n" "movq %%xmm0, %%r9\n"
        "movabsq $0x600000000000015f, %%rax\n" "cmpq %%rax, %%r10\n" "jne 1f\n" "cmpq %%rax, %%r9\n" "je 2f\n" "1: orq $0x20000, %%r11\n" "2:\n"
        "movq %%r11, r_probe_clobbered(%%rip)\n"
        "movq 192(%%rsp), %%rax\n"
        LOAD_XMM(6, 32) LOAD_XMM(7, 48) LOAD_XMM(8, 64) LOAD_XMM(9, 80)
        LOAD_XMM(10, 96) LOAD_XMM(11, 112) LOAD_XMM(12, 128)
        LOAD_XMM(13, 144) LOAD_XMM(14, 160) LOAD_XMM(15, 176)
        "addq $200, %%rsp\n"
        "popq %%r15\n" "popq %%r14\n" "popq %%r13\n" "popq %%r12\n"
        "popq %%rsi\n" "popq %%rdi\n" "popq %%rbp\n" "popq %%rbx\n"
        "retq\n" : : : );
}

int main(void)
{
    int64_t direct = landin_churn(5);
    int64_t probed = r_probe(landin_churn, 5);
    if (r_probe_clobbered != 0) {
        printf("clobbered %#llx\n", (unsigned long long)r_probe_clobbered);
        return 1;
    }
    if (probed != direct) return 2;
    return 42;
}
