/* Independently observe shared backing after a child traps before its store. */
#define _GNU_SOURCE
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#if defined(_WIN32)
#include <stdio.h>
#include <string.h>
#include <windows.h>
#else
#include <signal.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <sys/resource.h>
#include <unistd.h>
#endif
uint32_t invalid(uint32_t mode) { return mode ? 0 : 0x100; }
extern void guarded(uint32_t *, uint32_t);
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

/* A page both copies map: the parent's mapping handle, inherited, is
   named to the copy on its command line. */
static void *shared_page(HANDLE *handle) {
    SECURITY_ATTRIBUTES inheritable = {sizeof inheritable, NULL, TRUE};
    *handle = CreateFileMappingA(INVALID_HANDLE_VALUE, &inheritable, PAGE_READWRITE,
                                 0, 4096, NULL);
    if (*handle == NULL) return NULL;
    return MapViewOfFile(*handle, FILE_MAP_ALL_ACCESS, 0, 0, 4096);
}

static void *inherited_page(const char *named) {
    HANDLE handle = (HANDLE)(uintptr_t)strtoull(named, NULL, 10);
    return MapViewOfFile(handle, FILE_MAP_ALL_ACCESS, 0, 0, 4096);
}

int main(int argc, char **argv) {
    if (argc == 3) {
        uint32_t *word = inherited_page(argv[2]);
        assert(word != NULL);
        guarded(word, (uint32_t)strtoul(argv[1], NULL, 10));
        _Exit(99);
    }
    HANDLE handle;
    uint32_t *word = shared_page(&handle);
    assert(word != NULL);
    for (uint32_t mode = 0; mode != 2; ++mode) {
        *word = 0xdeadbeef;
        char arguments[48];
        snprintf(arguments, sizeof arguments, "%u %llu", (unsigned)mode,
                 (unsigned long long)(uintptr_t)handle);
        assert(ended(arguments, TRUE) == (DWORD)STATUS_ILLEGAL_INSTRUCTION);
        assert(*word == 0xdeadbeef);
    }
    assert(UnmapViewOfFile(word) && CloseHandle(handle));
    return 42;
}
#else
int main(void) {
    const struct rlimit no_core = {0, 0};
    assert(setrlimit(RLIMIT_CORE, &no_core) == 0);
    uint32_t *word = mmap(NULL, 4096, PROT_READ | PROT_WRITE,
                         MAP_SHARED | MAP_ANON, -1, 0);
    assert(word != MAP_FAILED);
    for (uint32_t mode = 0; mode != 2; ++mode) {
        *word = 0xdeadbeef;
        pid_t child = fork();
        assert(child >= 0);
        if (child == 0) { guarded(word, mode); _Exit(99); }
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
        assert(*word == 0xdeadbeef);
    }
    assert(munmap(word, 4096) == 0);
    return 42;
}
#endif
