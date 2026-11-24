/* A debugger's session for refine-dap: one long-lived program spoken to
   over pipes on its standard input and output, its standard error left
   as refine-dap's own, and, when asked, two more pipes whose write ends
   the debugger holds as descriptors 3 and 4 for the program it debugs to
   write its output to (GDB starts that program through a shell, whose
   redirections name them).  Waiting polls the editor's standard input
   beside the session's read ends, so one thread serves both.

   Every descriptor refine-dap keeps is close-on-exec, and SIGPIPE is
   ignored while a session is open: a debugger that has ended makes a
   write fail with EPIPE, which the adapter reports, rather than ending
   refine-dap.  Nothing here reads a file or reaches a target fact.

   When asked to connect, the debugger is spoken to over a loopback TCP
   connection instead of its standard streams, which are /dev/null: it is
   started listening on a port free a moment before, and the session's
   input and output are the connection's two ends.  LLVM's lldb-dap.exe,
   run from WSL, deadlocks on standard streams WSL gives it, a read
   pending on one holding a write on the other, in about half of all
   sessions; over a socket it does not (D2351). */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <spawn.h>
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdio.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

extern char **environ;

enum { LANDIN_DEBUGGER_ABOVE = 10 };

int landin_debugger_start(char *const args[], char *const settings[],
                          int pipes, int own_group, int over_socket,
                          int *child, int descriptors[4]);
int landin_debugger_wait(const int descriptors[4], int milliseconds,
                         int ready[5]);
long landin_debugger_read(int descriptor, char *into, long length);
int landin_debugger_write(int descriptor, const char *item, long length);
int landin_debugger_stop(int child, int descriptors[4], int milliseconds,
                         int *status);

/* DESCRIPTOR moved above every number a child is given, close-on-exec;
   -1 when the host refuses. */
static int landin_debugger_lift(int descriptor)
{
    int lifted = fcntl(descriptor, F_DUPFD_CLOEXEC, LANDIN_DEBUGGER_ABOVE);
    int saved = errno;
    close(descriptor);
    errno = saved;
    return lifted;
}

static int landin_debugger_pipe(int ends[2])
{
    int made[2];
    if (pipe(made) != 0)
        return -1;
    ends[0] = landin_debugger_lift(made[0]);
    ends[1] = landin_debugger_lift(made[1]);
    if (ends[0] < 0 || ends[1] < 0) {
        if (ends[0] >= 0) close(ends[0]);
        if (ends[1] >= 0) close(ends[1]);
        return -1;
    }
    return 0;
}

/* Whether ENTRY, NAME=VALUE, sets the variable SETTING sets. */
static int landin_debugger_same_name(const char *entry, const char *setting)
{
    const char *equals = strchr(setting, '=');
    size_t length = equals ? (size_t)(equals - setting) : strlen(setting);
    return strncmp(entry, setting, length) == 0 && entry[length] == '=';
}

/* A loopback port nothing listens on now, in host order; 0 when the host
   refuses. */
static int landin_debugger_free_port(void)
{
    struct sockaddr_in address;
    socklen_t length = sizeof address;
    int port = 0, probe = socket(AF_INET, SOCK_STREAM, 0);
    if (probe < 0)
        return 0;
    memset(&address, 0, sizeof address);
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (bind(probe, (struct sockaddr *)&address, sizeof address) == 0
        && getsockname(probe, (struct sockaddr *)&address, &length) == 0)
        port = ntohs(address.sin_port);
    close(probe);
    return port;
}

/* A connection to PORT on the loopback address, tried every 50 ms for up
   to 20 s while the debugger starts listening; -1 when none was made. */
static int landin_debugger_connect(int port)
{
    struct sockaddr_in address;
    struct timespec pause = {0, 50000000};
    int tries;
    memset(&address, 0, sizeof address);
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = htons((unsigned short)port);
    for (tries = 0; tries < 400; tries++) {
        int made = socket(AF_INET, SOCK_STREAM, 0);
        if (made < 0)
            return -1;
        if (connect(made, (struct sockaddr *)&address, sizeof address) == 0)
            return landin_debugger_lift(made);
        close(made);
        nanosleep(&pause, NULL);
    }
    return -1;
}

/* Start ARGS[0], found on PATH when it has no slash, with ARGS, in this
   process's environment with each NAME=VALUE of SETTINGS in place of the
   inherited one, in a process group of its own when OWN_GROUP.
   DESCRIPTORS receives the write end of its standard
   input, the read end of its standard output and, when PIPES, the read
   ends of the pipes it holds as 3 and 4; else -1.  When OVER_SOCKET, ARGS
   gain `--connection listen://127.0.0.1:PORT` and the first two are the
   connection's ends instead.  0, or an errno. */
int landin_debugger_start(char *const args[], char *const settings[],
                          int pipes, int own_group, int over_socket,
                          int *child, int descriptors[4])
{
    char listen[48];
    char **words = NULL;
    size_t length = 0;
    int port = 0;
    int input[2] = {-1, -1}, output[2] = {-1, -1};
    int program[2] = {-1, -1}, errors[2] = {-1, -1};
    posix_spawn_file_actions_t actions;
    posix_spawnattr_t attributes;
    sigset_t defaults;
    size_t inherited = 0, given = 0, count = 0, index, other;
    char **environment;
    pid_t pid;
    int error = 0;

    *child = 0;
    descriptors[0] = descriptors[1] = descriptors[2] = descriptors[3] = -1;
    signal(SIGPIPE, SIG_IGN);
    while (environ[inherited] != NULL) inherited++;
    while (settings[given] != NULL) given++;
    environment = calloc(inherited + given + 1, sizeof *environment);
    if (environment == NULL)
        return ENOMEM;
    for (index = 0; index < inherited; index++) {
        int replaced = 0;
        for (other = 0; other < given; other++)
            if (landin_debugger_same_name(environ[index], settings[other]))
                replaced = 1;
        if (!replaced)
            environment[count++] = environ[index];
    }
    for (other = 0; other < given; other++)
        environment[count++] = settings[other];
    environment[count] = NULL;

    if (over_socket) {
        port = landin_debugger_free_port();
        while (args[length] != NULL) length++;
        words = calloc(length + 3, sizeof *words);
        if (port == 0 || words == NULL) {
            error = port == 0 ? (errno != 0 ? errno : EADDRNOTAVAIL) : ENOMEM;
            goto failed;
        }
        snprintf(listen, sizeof listen, "listen://127.0.0.1:%d", port);
        memcpy(words, args, length * sizeof *words);
        words[length] = "--connection";
        words[length + 1] = listen;
        words[length + 2] = NULL;
    }
    if ((!over_socket && (landin_debugger_pipe(input) != 0
                      || landin_debugger_pipe(output) != 0))
        || (pipes && (landin_debugger_pipe(program) != 0
                      || landin_debugger_pipe(errors) != 0))) {
        error = errno != 0 ? errno : EMFILE;
        goto failed;
    }
    error = posix_spawn_file_actions_init(&actions);
    if (error != 0)
        goto failed;
    error = posix_spawnattr_init(&attributes);
    if (error != 0) {
        posix_spawn_file_actions_destroy(&actions);
        goto failed;
    }
    sigemptyset(&defaults);
    sigaddset(&defaults, SIGPIPE);
    sigaddset(&defaults, SIGINT);
    error = posix_spawnattr_setsigdefault(&attributes, &defaults);
    /* Its own process group when OWN_GROUP: a signal meant for
       refine-dap's group, an editor's interrupt among them, is not the
       debugger's.  A Windows program WSL starts in a group of its own
       stalls (D2292), so a Windows debugger shares refine-dap's. */
    if (error == 0 && own_group)
        error = posix_spawnattr_setpgroup(&attributes, 0);
    if (error == 0)
        error = posix_spawnattr_setflags
            (&attributes, POSIX_SPAWN_SETSIGDEF
                          | (own_group ? POSIX_SPAWN_SETPGROUP : 0));
    if (error == 0 && over_socket)
        error = posix_spawn_file_actions_addopen
            (&actions, 0, "/dev/null", O_RDONLY, 0);
    if (error == 0 && over_socket)
        error = posix_spawn_file_actions_addopen
            (&actions, 1, "/dev/null", O_WRONLY, 0);
    if (error == 0 && !over_socket)
        error = posix_spawn_file_actions_adddup2(&actions, input[0], 0);
    if (error == 0 && !over_socket)
        error = posix_spawn_file_actions_adddup2(&actions, output[1], 1);
    if (error == 0 && pipes)
        error = posix_spawn_file_actions_adddup2(&actions, program[1], 3);
    if (error == 0 && pipes)
        error = posix_spawn_file_actions_adddup2(&actions, errors[1], 4);
    if (error == 0)
        error = posix_spawnp(&pid, args[0], &actions, &attributes,
                             over_socket ? words : args, environment);
    posix_spawn_file_actions_destroy(&actions);
    posix_spawnattr_destroy(&attributes);
    if (error != 0)
        goto failed;
    free(environment);
    free(words);
    if (pipes) {
        close(program[1]);
        close(errors[1]);
    }
    *child = (int)pid;
    if (over_socket) {
        input[1] = landin_debugger_connect(port);
        output[0] = input[1] < 0 ? -1 : fcntl(input[1], F_DUPFD_CLOEXEC,
                                                LANDIN_DEBUGGER_ABOVE);
        if (output[0] < 0) {
            /* No connection: the debugger is ended, as a session that
               fails to start leaves nothing running. */
            int status;
            if (input[1] >= 0) close(input[1]);
            kill(pid, SIGKILL);
            waitpid(pid, &status, 0);
            *child = 0;
            if (pipes) {
                close(program[0]);
                close(errors[0]);
            }
            return ECONNREFUSED;
        }
    } else {
        close(input[0]);
        close(output[1]);
    }
    descriptors[0] = input[1];
    descriptors[1] = output[0];
    descriptors[2] = program[0];
    descriptors[3] = errors[0];
    return 0;

failed:
    free(environment);
    free(words);
    {
        int *all[4] = {input, output, program, errors};
        for (index = 0; index < 4; index++) {
            if (all[index][0] >= 0) close(all[index][0]);
            if (all[index][1] >= 0) close(all[index][1]);
        }
    }
    return error;
}

/* Wait up to MILLISECONDS, or without end when negative, until standard
   input or one of the read ends DESCRIPTORS[1..3] has bytes, an end or a
   hang-up.  READY[0] is standard input's, READY[1..3] those descriptors';
   a descriptor of -1 is never ready.  0, or -1 when the host refuses. */
int landin_debugger_wait(const int descriptors[4], int milliseconds,
                         int ready[5])
{
    struct pollfd watched[4];
    int index;

    watched[0].fd = 0;
    for (index = 1; index < 4; index++)
        watched[index].fd = descriptors[index];
    for (index = 0; index < 4; index++) {
        watched[index].events = POLLIN;
        watched[index].revents = 0;
        ready[index] = 0;
    }
    ready[4] = 0;
    for (;;) {
        int got = poll(watched, 4, milliseconds);
        if (got >= 0)
            break;
        if (errno != EINTR)
            return -1;
    }
    for (index = 0; index < 4; index++)
        ready[index] = watched[index].fd >= 0
            && (watched[index].revents & (POLLIN | POLLHUP | POLLERR)) != 0;
    return 0;
}

/* The bytes read, 0 at the end, or -1 when the host refuses. */
long landin_debugger_read(int descriptor, char *into, long length)
{
    for (;;) {
        ssize_t got = read(descriptor, into, (size_t)length);
        if (got >= 0)
            return (long)got;
        if (errno != EINTR)
            return -1;
    }
}

/* 0 when every byte was written, -1 when the host refused one. */
int landin_debugger_write(int descriptor, const char *item, long length)
{
    long done = 0;

    while (done < length) {
        ssize_t wrote = write(descriptor, item + done, (size_t)(length - done));
        if (wrote < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        done += (long)wrote;
    }
    return 0;
}

/* Close the session's descriptors, which a debugger reading its input
   takes for the end, and reap CHILD within MILLISECONDS; past them, end
   its process group with SIGKILL and reap it.  STATUS is its exit status,
   or 128 plus the signal that ended it.  0, or -1 when it cannot be
   reaped. */
int landin_debugger_stop(int child, int descriptors[4], int milliseconds,
                         int *status)
{
    int index, word = 0;
    long waited = 0;
    pid_t reaped = 0;

    for (index = 0; index < 4; index++)
        if (descriptors[index] >= 0) {
            close(descriptors[index]);
            descriptors[index] = -1;
        }
    *status = -1;
    if (child <= 0)
        return 0;
    for (;;) {
        reaped = waitpid((pid_t)child, &word, WNOHANG);
        if (reaped < 0 && errno == EINTR)
            continue;
        if (reaped != 0 || waited >= milliseconds)
            break;
        {
            struct timespec pause = {0, 10 * 1000 * 1000};
            nanosleep(&pause, NULL);
            waited += 10;
        }
    }
    if (reaped == 0) {
        kill(-(pid_t)child, SIGKILL);
        kill((pid_t)child, SIGKILL);
        do {
            reaped = waitpid((pid_t)child, &word, 0);
        } while (reaped < 0 && errno == EINTR);
    }
    if (reaped < 0)
        return -1;
    *status = WIFEXITED(word) ? WEXITSTATUS(word)
        : WIFSIGNALED(word) ? 128 + WTERMSIG(word) : -1;
    return 0;
}
