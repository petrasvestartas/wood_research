#!/usr/bin/env bash
# build.sh <session_cpp build dir>: ours_side and ours_roundtrip next to this script, compiled and linked like point_minitest
set -e
H=$(cd "$(dirname "$0")" && pwd); cd "$1"
CC=$(ninja -t commands point_minitest | grep "file_step.cpp.o -c" | sed 's/ -MD .*//; s/ -Winvalid-pch -include [^ ]*//; s/.*&& //')
LINK=$(ninja -t commands point_minitest | tail -1 | sed 's/^: && //; s/ && :$//' | tr ' ' '\n' | grep -v "CMakeFiles/point_minitest.dir" | tr '\n' ' ')
for t in ours_side ours_roundtrip; do
  $CC -c "$H/$t.cpp" -o "$H/$t.o"
  eval "${LINK/-o point_minitest/-o $H/$t $H/$t.o}"
done
