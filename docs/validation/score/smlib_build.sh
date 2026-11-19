#!/usr/bin/env bash
# smlib_build.sh <usd-brep repo> <out dir> [jobs=2]: SMLib and SM_API alone (libSMLib.so, libSM_API.so), release flags of
# the repo's premake files, no USD, no Packman. TBB (the only dependency) comes from the PyPI wheels tbb and tbb-devel.
set -euo pipefail
REPO=$(cd "$1" && pwd); OUT=$2; JOBS=${3:-2}
mkdir -p "$OUT/tbb" "$OUT/obj"; OUT=$(cd "$OUT" && pwd)
if [ ! -e "$OUT/tbb/include/tbb/parallel_for.h" ]; then
  pip download tbb==2021.13.1 tbb-devel==2021.13.1 --no-deps -q -d "$OUT/tbb/wheels"
  for w in "$OUT"/tbb/wheels/*.whl; do python3 -I -m zipfile -e "$w" "$OUT/tbb/x"; done
  mkdir -p "$OUT/tbb/lib"
  cp -a "$OUT"/tbb/x/tbb_devel-*.data/data/include "$OUT/tbb/"
  cp -a "$OUT"/tbb/x/tbb-*.data/data/lib/libtbb.so* "$OUT"/tbb/x/tbb-*.data/data/lib/libtbbmalloc.so* "$OUT/tbb/lib/"
fi
FLAGS="-O2 -std=c++17 -fPIC -w -DNDEBUG -DNOMINMAX -DSM_GRAPHICS_CALLBACKS=1 -DTBB_SUPPRESS_DEPRECATED_MESSAGES -DTBB_USE_DEBUG=0 -D_GLIBCXX_USE_CXX11_ABI=1"
{
  echo "rule cc"; echo "  command = g++ $FLAGS \$inc -MD -MF \$out.d -c \$in -o \$out"; echo "  depfile = \$out.d"; echo "  deps = gcc"
  echo "rule so"; echo "  command = g++ -shared -o \$out \$in \$libs -Wl,-rpath,$OUT -Wl,-rpath,$OUT/tbb/lib"
  for lib in SMLib SM_API; do
    objs=
    for f in "$REPO"/source/$lib/src/*.cpp; do
      [ "$(basename "$f")" = StdAfx.cpp ] && continue
      o=obj/$lib/$(basename "$f" .cpp).o; objs="$objs $o"
      echo "build $o: cc $f"; echo "  inc = -I$REPO/source/$lib/inc -I$REPO/source/SMLib/inc -isystem $OUT/tbb/include"
    done
    if [ $lib = SMLib ]; then echo "build libSMLib.so: so $objs"; echo "  libs = -L$OUT/tbb/lib -ltbb -ltbbmalloc -lpthread"
    else echo "build libSM_API.so: so $objs | libSMLib.so"; echo "  libs = -L$OUT -lSMLib -L$OUT/tbb/lib -ltbb"; fi
  done
} > "$OUT/build.ninja"
nice ninja -C "$OUT" -j "$JOBS"
