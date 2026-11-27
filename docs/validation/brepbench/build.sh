#!/usr/bin/env bash
# build.sh [session_cpp build dir] [out binary]: compile bb_session.cpp with that build's flags and link it
# against the build's objects (as ../score/link.sh does); no session_cpp library is rebuilt.
set -euo pipefail
B=$(cd "${1:-/home/user/wood_research/session/session_cpp/build}" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${2:-${BB_OUT:-/tmp/brepbench_out}/bb_session}
mkdir -p "$(dirname "$OUT")"
cd "$B"
CC=$(ninja -t commands point_minitest | grep "brep_boolean.cpp.o -c" | sed 's/ -MD .*//; s/ -Winvalid-pch -include [^ ]*//; s/.*&& //')
nice $CC -w -c "$HERE/bb_session.cpp" -o "$OUT.o"
LINK=$(ninja -t commands point_minitest | tail -1 | sed 's/^: && //; s/ && :$//')
ARGS=""
for w in $LINK; do
  case $w in
    CMakeFiles/point_minitest.dir/*) ;;
    -o) ARGS="$ARGS -o $OUT $OUT.o" ;;
    point_minitest) ;;
    *) ARGS="$ARGS $w" ;;
  esac
done
nice $ARGS
rm -f "$OUT.o"
echo "built $OUT"
