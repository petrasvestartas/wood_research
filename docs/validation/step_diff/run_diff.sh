#!/usr/bin/env bash
# run_diff.sh <out dir> <file.step>...: per-stage STEP differ of session_cpp against OCCT 8.0.1; then diff.py <out dir> writes the table.
# Needs: ours_side and ours_roundtrip built by build.sh <session_cpp build dir>, PY a Python with OCP (cadquery-ocp 8.0.1), the bench tools in
# /home/user/session_data/brep_boolean_bench/tools. READER=1 skips the writer stage 6. Then: $PY diff.py <out dir> > table.md
H=$(dirname "$0"); O=$1; shift; mkdir -p $O/written $O/occt_written
PY=${PY:-python3}
B=${BIN:-$H}
for f in "$@"; do
  n=$(echo $f | sed 's|[^A-Za-z0-9_.-]|_|g')
  timeout 900 $B/ours_side $f > $O/$n.ours 2>/dev/null
  timeout 900 $PY -I $H/occt_side.py $f > $O/$n.occt 2>/dev/null
  [ "$READER" ] && { echo "$f" >> $O/files.txt; continue; }
  timeout 900 $B/ours_roundtrip $f $O/written > $O/$n.rt 2>/dev/null
  for w in $(grep -o "$O/written/[^ ]*\.step" $O/$n.rt); do timeout 900 $PY -I $H/occt_side.py $w >> $O/$n.rtocct 2>/dev/null; done
  timeout 900 $PY -I $H/occt_write.py $f $O/occt_written/$n.step > /dev/null 2>&1 && timeout 900 $B/ours_side $O/occt_written/$n.step > $O/$n.occtw.ours 2>/dev/null
  echo "$f" >> $O/files.txt
done
