/* Literal independent membership oracle; every byte is exercised. */
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#if defined(_WIN32)
#include <stdio.h>
#include <string.h>
#include <windows.h>
#else
#include <signal.h>
#include <sys/wait.h>
#include <sys/resource.h>
#if defined(__linux__)
#include <sys/prctl.h>
#endif
#include <unistd.h>
#endif
extern int32_t decode(uint8_t);
#if defined(_WIN32)
/* Windows has no fork: the program starts itself again with the case as
   its arguments and reads how that copy ended from its exit code, which a
   trap makes STATUS_ILLEGAL_INSTRUCTION, ud2's on x86-64 and brk's on
   arm64.  The copy inherits the parent's error mode and job, so a trap
   reaches no error report.  1 is no copy's code here: a failure to start
   one. */
static DWORD ended(const char *arguments, BOOL inherit) {
    char path[MAX_PATH];
    DWORD length = GetModuleFileNameA(NULL, path, MAX_PATH);
    if (length == 0 || length == MAX_PATH) return 1;
    char line[MAX_PATH + 64];
    snprintf(line, sizeof line, "\"%s\" %s", path, arguments);
    STARTUPINFOA start;
    memset(&start, 0, sizeof start);
    start.cb = sizeof start;
    PROCESS_INFORMATION process;
    if (!CreateProcessA(path, line, NULL, NULL, inherit, 0, NULL, NULL, &start, &process))
        return 1;
    DWORD code = 1;
    if (WaitForSingleObject(process.hProcess, INFINITE) != WAIT_OBJECT_0
        || !GetExitCodeProcess(process.hProcess, &code)) code = 1;
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return code;
}

int main(int argc, char **argv) {
    if (argc == 2) { (void)decode((uint8_t)strtoul(argv[1], NULL, 10)); _Exit(99); }
    for (unsigned raw = 0; raw != 256; ++raw) {
        unsigned field = (raw / 4) % 8;
        if (field == 0 || field == 1 || field == 4) {
            assert(decode((uint8_t)raw) == (field == 0 ? 10 : field == 1 ? 20 : 30));
        } else {
            char argument[8];
            snprintf(argument, sizeof argument, "%u", raw);
            assert(ended(argument, FALSE) == (DWORD)STATUS_ILLEGAL_INSTRUCTION);
        }
    }
    return 42;
}
#else
int main(void) {
    const struct rlimit no_core = {0, 0};
    assert(setrlimit(RLIMIT_CORE, &no_core) == 0);
#if defined(__linux__)
    /* A piped core handler ignores RLIMIT_CORE; suppress it for these forks. */
    assert(prctl(PR_SET_DUMPABLE, 0L, 0L, 0L, 0L) == 0);
#endif
    for (unsigned raw = 0; raw != 256; ++raw) {
        unsigned field = (raw / 4) % 8;
        if (field == 0 || field == 1 || field == 4) {
            assert(decode((uint8_t)raw) == (field == 0 ? 10 : field == 1 ? 20 : 30));
        } else {
            pid_t child = fork();
            assert(child >= 0);
            if (child == 0) { (void)decode((uint8_t)raw); _Exit(99); }
            int status;
            assert(waitpid(child, &status, 0) == child);
            assert(WIFSIGNALED(status));
/* The arm64 backend traps with brk, SIGTRAP on Darwin and Linux alike;
   x86-64 traps with ud2 and RV64 with unimp, both SIGILL. */
#if defined(__aarch64__)
            assert(WTERMSIG(status) == SIGTRAP);
#else
            assert(WTERMSIG(status) == SIGILL);
#endif
        }
    }
    return 42;
}
#endif
