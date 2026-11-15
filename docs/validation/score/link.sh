#!/usr/bin/env bash
# link.sh <session_cpp build dir> <out binary> [old|bop]: score_drv.cpp compiled with that build's flags, linked
# against its objects (no library is rebuilt).
set -euo pipefail
B=$(cd "$1" && pwd); OUT=$2; ENTRY=${3:-old}
HERE=$(cd "$(dirname "$0")" && pwd)
MAIN=/home/user/wood_research/session/session_cpp/build
SRC=$(sed -n 's/^CMAKE_HOME_DIRECTORY:INTERNAL=//p' "$B/CMakeCache.txt")
FLAGS=""
if [ "$ENTRY" = bop ]; then
  [ -f "$SRC/src/bop.h" ] || { echo "entry bop: $SRC/src/bop.h does not exist yet (bop::apply not written)" >&2; exit 3; }
  [ -f "$B/CMakeFiles/session_core.dir/src/bop.cpp.o" ] || { echo "entry bop: $B has no bop.cpp.o (build it first)" >&2; exit 3; }
  FLAGS="-DSCORE_BOP"
  grep -q "enum class Operation" "$SRC/src/bop.h" && FLAGS="$FLAGS -DSCORE_OP=session_cpp::bop::Operation"
elif [ "$ENTRY" != old ]; then
  echo "entry must be old or bop" >&2; exit 2
fi
cd "$B"
CC=$(ninja -t commands point_minitest | grep "brep_boolean.cpp.o -c" | sed 's/ -MD .*//; s/ -Winvalid-pch -include [^ ]*//; s/.*&& //')
nice $CC $FLAGS -w -c "$HERE/score_drv.cpp" -o "$OUT.o"
LINK=$(ninja -t commands point_minitest | tail -1 | sed 's/^: && //; s/ && :$//')
ARGS=""
for w in $LINK; do
  case $w in
    CMakeFiles/point_minitest.dir/*) ;;
    -o) ARGS="$ARGS -o $OUT $OUT.o" ;;
    point_minitest) ;;
    _deps/*) if [ -e "$B/$w" ]; then ARGS="$ARGS $B/$w"; else ARGS="$ARGS $MAIN/$w"; fi ;;
    *) ARGS="$ARGS $w" ;;
  esac
done
nice $ARGS
rm -f "$OUT.o"
