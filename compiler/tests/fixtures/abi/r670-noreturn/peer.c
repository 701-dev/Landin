#include <stdint.h>
#include <stdlib.h>
#if defined(_WIN32)
#include <stdio.h>
#include <string.h>
#include <windows.h>
#else
#include <signal.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

extern void run_path(uint32_t mode);
static volatile uint32_t *events;

void mark(uint32_t value) { *events = value; }
void finish(uint32_t value) { _Exit(value == 42 ? 42 : 1); }
/* Deliberate foreign contract violation: Landin must guard the return. */
void wrongly_returns(void) { *events = 8; }

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

int main(int argc, char **argv)
{
    if (argc == 3) {
        events = inherited_page(argv[2]);
        if (events == NULL) _Exit(98);
        run_path((uint32_t)strtoul(argv[1], NULL, 10));
        _Exit(99);
    }
    HANDLE handle;
    events = shared_page(&handle);
    if (events == NULL) return 2;
    for (uint32_t mode = 0; mode < 7; ++mode) {
        *events = 0;
        char arguments[48];
        snprintf(arguments, sizeof arguments, "%u %llu", (unsigned)mode,
                 (unsigned long long)(uintptr_t)handle);
        DWORD code = ended(arguments, TRUE);
        if (*events != (mode == 4 ? 7u : mode == 6 ? 8u : 0u)) return 5;
        if (code != (mode < 6 ? 42 : (DWORD)STATUS_ILLEGAL_INSTRUCTION)) return 6;
    }
    if (!UnmapViewOfFile((void *)events) || !CloseHandle(handle)) return 8;
    return 42;
}
#else

int main(void)
{
    struct rlimit limit = {0, 0};
    if (setrlimit(RLIMIT_CORE, &limit) != 0) return 1;
    events = mmap(NULL, 4096, PROT_READ | PROT_WRITE,
                  MAP_SHARED | MAP_ANON, -1, 0);
    if (events == MAP_FAILED) return 2;
    for (uint32_t mode = 0; mode < 7; ++mode) {
        *events = 0;
        pid_t child = fork();
        if (child < 0) return 3;
        if (child == 0) { run_path(mode); _exit(99); }
        int status;
        if (waitpid(child, &status, 0) != child) return 4;
        if (*events != (mode == 4 ? 7u : mode == 6 ? 8u : 0u)) return 5;
        if (mode < 6) {
            if (!WIFEXITED(status) || WEXITSTATUS(status) != 42) return 6;
        } else {
/* The arm64 backend traps with brk, SIGTRAP on Darwin and Linux alike;
   x86-64 traps with ud2 and RV64 with unimp, both SIGILL. */
#if defined(__aarch64__)
            const int expected = SIGTRAP;
#else
            const int expected = SIGILL;
#endif
            if (!WIFSIGNALED(status) || WTERMSIG(status) != expected) return 7;
        }
    }
    if (munmap((void *)events, 4096) != 0) return 8;
    return 42;
}
#endif
