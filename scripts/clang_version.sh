#!/bin/sh
#  Refuse a clang-19 on PATH other than the one environments/pins.sh pins,
#  LANDIN_CLANG_NIX, and print its version line.  The gate's jobs run it
#  after .github/actions/nix-tools has put the flake's llvm-19 on PATH.
set -eu
here=$(dirname "$0")
. "$here/../environments/pins.sh"
line=$(clang-19 --version | sed -n '1p')
echo "$line"
case "$line" in
    *"clang version $LANDIN_CLANG_NIX"|*"clang version $LANDIN_CLANG_NIX "*) ;;
    *) echo "clang-19 is not the pinned Clang $LANDIN_CLANG_NIX" >&2; exit 1 ;;
esac
