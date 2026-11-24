# FreeBSD ports' GCC 16 patches

Every `files/patch-*` of FreeBSD ports' `lang/gcc16`, the port of the GCC
16.1.0 release, at ports commit `a9844c5f4e09f61d7f32547bba99636395fd9341`,
the commit `environments/pins.sh` names as `LANDIN_FREEBSD_PORTS_COMMIT`.
They are copied unchanged, under GCC's own licence, and `../build.sh`
applies them all with `patch -p0` before it configures GCC.

Upstream GCC 16.1.0 does not build on FreeBSD without them: on aarch64
libgcc's `config/aarch64/cpuinfo.c` calls glibc's `getauxval`, and
`unwind-dw2-fde-dip.c` takes FreeBSD's `ElfW` for GCC's own. The others
are for languages and architectures the build does not make, and apply
cleanly all the same; taking the port's set whole keeps it one comparison
with the port.

To move to a later ports commit, copy that commit's `lang/gcc16/files/patch-*`
here, name the commit in `environments/pins.sh`, and build: the archive's
digest covers every patch, so the gate builds the toolchain again.
