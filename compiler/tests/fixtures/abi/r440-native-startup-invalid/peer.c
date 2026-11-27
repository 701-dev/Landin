#include <stddef.h>

extern char **environ;
extern void _landin_host_initialize_arguments(int argc, char **argv,
                                              char **envp);
extern size_t l_root(void);

int main(int argc, char **argv)
{
    (void)argc;
    /* A negative count is no argument vector; the call is told so. */
    _landin_host_initialize_arguments(-1, argv, environ);
    (void)l_root();
    return 1;
}
