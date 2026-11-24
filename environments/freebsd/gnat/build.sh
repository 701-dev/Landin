#!/bin/sh
#  Builds the pinned GNAT and GPRbuild from source on a FreeBSD host, as
#  compiler/ada/TOOLCHAIN.md allows a host GNAT-FSF-builds publishes no
#  archive for.  Run as root in a FreeBSD guest by environments/freebsd/
#  gnat.py, which verifies every source against environments/pins.sh
#  before it copies it in; run by hand it takes the same arguments:
#
#      build.sh SOURCES PREFIX
#
#  SOURCES holds gcc-VERSION.tar.xz, gprbuild-, xmlada- and
#  gprconfig_kb-VERSION.tar.gz, patches/, FreeBSD ports' lang/gcc16
#  patches (patches/README.md), and gprbuild-6421e350274b.patch.  The
#  result is PREFIX/gnat-VERSION and PREFIX/gprbuild-VERSION, the
#  directories LANDIN_GNAT_HOME and LANDIN_GPRBUILD_HOME name; what each
#  step took goes to standard output.
#
#  GCC is built once by FreeBSD's gnat14 package rather than bootstrapped
#  in three stages, as the ports build their own GNAT from the one before
#  it: the result is the pinned version's compiler and runtime, a third of
#  the time.  gnat14 rather than gnat15 because gnat15 cannot build GCC on
#  aarch64 (its arm_neon.h includes a header it does not ship), and one
#  recipe serves both architectures.  The link is binutils', since GCC's
#  driver asks ld for an emulation the base system's LLVM ld refuses on
#  aarch64, and the ports configure GCC the same way.
set -eu

Sources=$1
Prefix=$2
Gcc_Version=16.1.0
Gpr_Version=26.0.0
Gnat=$Prefix/gnat-$Gcc_Version
Gpr=$Prefix/gprbuild-$Gpr_Version
Work=${LANDIN_GNAT_WORK:-/var/tmp/landin-gnat}
#  GCC's largest units take about a GiB each to compile; more jobs than
#  that run out of memory before they run out of processors.
Memory_Gib=$(( $(sysctl -n hw.physmem) / 1073741824 ))
Jobs=$(sysctl -n hw.ncpu)
[ "$Jobs" -le "$Memory_Gib" ] || Jobs=$Memory_Gib
[ "$Jobs" -ge 1 ] || Jobs=1

Started=$(date +%s)
say() { echo "gnat: $(( $(date +%s) - Started )) s: $*"; }

say "packages"
env ASSUME_ALWAYS_YES=yes pkg bootstrap -f >/dev/null
#  GCC's configure finds gmp, mpfr, mpc and isl here, and the compiler it
#  builds loads them at run time (gnat.py's RUNTIME_PACKAGES).
pkg install -qy gnat14 binutils gmake gmp mpfr mpc isl >/dev/null
Boot=/usr/local/gnat14/bin

rm -rf "$Work" "$Gnat" "$Gpr"
mkdir -p "$Work" "$Prefix"
cd "$Work"

say "GCC $Gcc_Version source, $(ls "$Sources/patches" | grep -c '^patch-') ports patches"
tar -xf "$Sources/gcc-$Gcc_Version.tar.xz"
( cd "gcc-$Gcc_Version" \
  && for Patch in "$Sources"/patches/patch-*; do patch -p0 -s -f < "$Patch"; done )
#  The ports' gnat recipe: a program GCC links finds the runtime it was
#  linked with, and libgcc builds without -Werror.
find "gcc-$Gcc_Version/gcc/config" -name '*freebsd.h' -o -name '*freebsd64.h' \
    | xargs sed -i '' -e "s|!static:[[:blank:]]|!static: --hash-style=gnu -rpath $Gnat/lib |"
sed -i '' -e 's|-Werror||' "gcc-$Gcc_Version/libgcc/config/aarch64/t-aarch64" \
    "gcc-$Gcc_Version/libgcc/configure"

mkdir gcc-build
cd gcc-build
say "GCC configure"
PATH=$Boot:/usr/local/bin:$PATH CC=$Boot/gcc CXX=$Boot/g++ \
    "../gcc-$Gcc_Version/configure" --prefix="$Gnat" \
    --enable-languages=c,c++,ada --disable-bootstrap --disable-multilib \
    --disable-nls --disable-libssp --enable-threads=posix \
    --with-as=/usr/local/bin/as --with-ld=/usr/local/bin/ld \
    --with-gmp=/usr/local --with-system-zlib --without-zstd \
    --with-pkgversion="Landin FreeBSD build" > configure.log 2>&1 \
    || { tail -40 configure.log; exit 1; }
say "GCC build, $Jobs jobs"
PATH=$Boot:/usr/local/bin:$PATH gmake -j"$Jobs" > make.log 2>&1 \
    || { tail -60 make.log; exit 1; }
say "GCC install"
PATH=$Boot:/usr/local/bin:$PATH gmake install-strip > install.log 2>&1 \
    || { tail -40 install.log; exit 1; }
cd "$Work"

#  GPRbuild's own bootstrap: gnatmake builds gprbuild with XML/Ada and the
#  knowledge base, as the ports' gprbuild recipe begins.  That gprbuild is
#  the pinned version and is what the build needs; libgpr and the shared
#  libraries are left out.  The new GNAT compiles it, with GPRbuild's own
#  later commit 6421e350274b (gprbuild-6421e350274b.patch): GNAT 16 refuses
#  26.0.0's gpr-compilation-process.adb, which names a map's "<" the map
#  does not declare, and gnat14 lacks a unit 26.0.0 needs.  GCC's runtime
#  is linked in, so gprbuild needs no library from PREFIX.
say "GPRbuild $Gpr_Version"
for Name in gprbuild xmlada gprconfig_kb; do
    mkdir "$Name"
    tar -xzf "$Sources/$Name-$Gpr_Version.tar.gz" -C "$Name" --strip-components=1
done
#  The source names a development version; a release build names its
#  own, as GNAT-FSF-builds' recipe does.
sed -i '' -e "s/\"18.0w\"/\"$Gpr_Version\"/" -e 's/:= Gnatpro;/:= FSF;/' \
    gprbuild/gpr/src/gpr-version.ads
( cd gprbuild && patch -p1 -s -f < "$Sources/gprbuild-6421e350274b.patch" )
( cd gprbuild \
  && PATH=$Gnat/bin:/usr/local/bin:$PATH CC=$Gnat/bin/gcc \
     GNATMAKEFLAGS="-j$Jobs -largs -static-libgcc" ./bootstrap.sh --with-xmlada=../xmlada \
     --with-kb=../gprconfig_kb --prefix="$Gpr" > ../gprbuild.log 2>&1 ) \
    || { tail -40 gprbuild.log; exit 1; }

"$Gnat/bin/gcc" --version | sed -n 1p
"$Gpr/bin/gprbuild" --version | sed -n 1p
say "done"
rm -rf "$Work"
