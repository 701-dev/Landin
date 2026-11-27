#!/bin/sh
#  Fast developer tests over GPRbuild's checksum-based incremental objects.
#  A focused run is feedback; the candidate's gate runs the complete suite
#  and every other host's lanes.

set -eu

#  --base=REV prints the local checks for the change since REV, from the
#  gate's lane table, and with --run runs them (scripts/local_selection.py).
case "${1:-}" in
    --base | --base=*)
        exec python3 "$(dirname -- "$0")/local_selection.py" "$@"
        ;;
esac

LANDIN_BUILD_INCREMENTAL=yes
export LANDIN_BUILD_INCREMENTAL

exec "$(dirname -- "$0")/test.sh" "$@"
