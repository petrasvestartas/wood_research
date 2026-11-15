#!/usr/bin/env bash
# score.sh <session_cpp build dir> <out dir> [subset|full] [--entry old|bop] [--jobs 2] [--timeout s] [--prev <run dir>]
# Links score_drv against the build, runs the real booleans (one process each, per-boolean timeout, results appended
# as they finish so a partial or resumed run is usable) and judges them against OCCT. Data: $SCORE_DATA (cases.tsv,
# ref.tsv, occt_operands.tsv; made by prep.py and occt_ref.py when missing).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
S=/tmp/claude-0/-home-user-wood-research/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad
PY=/tmp/claude-0/-home-user/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad/ocp/venv/bin/python
D=${SCORE_DATA:-$S/score}
[ $# -ge 2 ] || { sed -n 2p "$0"; exit 2; }
BUILD=$1; OUT=$2; shift 2
MODE=subset; [ $# -gt 0 ] && [[ $1 != --* ]] && { MODE=$1; shift; }
ENTRY=old; JOBS=2; LIMIT=; PREV=
while [ $# -gt 0 ]; do
  case $1 in
    --entry) ENTRY=$2 ;; --jobs) JOBS=$2 ;; --timeout) LIMIT=$2 ;; --prev) PREV=$2 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
  shift 2
done
[ "$JOBS" -le 2 ] || { echo "at most --jobs 2 on this machine" >&2; exit 2; }
case $MODE in
  subset) LIMIT=${LIMIT:-60}; SUB=(--subset "$HERE/subset.tsv"); WALL=30m ;;
  full) LIMIT=${LIMIT:-180}; SUB=(); WALL=16h ;;
  *) echo "mode must be subset or full" >&2; exit 2 ;;
esac
mkdir -p "$OUT" "$D"
[ -s "$D/ref.tsv" ] || python3 -I "$HERE/prep.py" "$D"
[ -s "$D/occt_operands.tsv" ] || timeout 90m nice "$PY" -I "$HERE/occt_ref.py" operands "$D/cases.tsv" "$D/occt_operands.tsv"
INFO="$(cd "$BUILD" && pwd) $ENTRY $MODE"
if [ -f "$OUT/run.info" ]; then
  [ "$(cat "$OUT/run.info")" = "$INFO" ] || { echo "$OUT holds a run of $(cat "$OUT/run.info"); use another out dir" >&2; exit 2; }
else
  timeout 10m bash "$HERE/link.sh" "$BUILD" "$OUT/drv" "$ENTRY"
  echo "$INFO" > "$OUT/run.info"
fi
T0=$(date +%s)
timeout "$WALL" python3 -I "$HERE/run.py" "$OUT/drv" "$D/cases.tsv" "$OUT" "${SUB[@]}" --jobs "$JOBS" --timeout "$LIMIT" || echo "run stopped early (status $?); judging what finished"
echo "$MODE run, entry $ENTRY, $(wc -l < "$OUT/results.tsv") booleans, wall $(( $(date +%s) - T0 )) s at --jobs $JOBS"
python3 -I "$HERE/judge.py" "$OUT" --data "$D" ${PREV:+--prev "$PREV"} | tee "$OUT/summary.txt"
