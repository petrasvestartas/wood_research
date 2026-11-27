#!/usr/bin/env bash
# run.sh <brep-bench clone> <board.json> [out dir]: build the runner, run the whole suite on it through the
# brep-bench harness (in a copy of the clone, the clone itself untouched), and write results.tsv / results.md here.
set -euo pipefail
CLONE=$(cd "$1" && pwd); BOARD=$2
OUT=${3:-/tmp/brepbench_out}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
bash "$HERE/build.sh" /home/user/wood_research/session/session_cpp/build "$OUT/bb_session"
rm -rf "$OUT/bb_repo"; mkdir -p "$OUT/bb_repo"
(cd "$CLONE" && tar --exclude=.git -cf - .) | (cd "$OUT/bb_repo" && tar xf -)
python3 -I "$HERE/setup_harness.py" "$OUT/bb_repo" "$OUT/bb_session"
for c in mass measure; do
  (cd "$OUT/bb_repo" && timeout 600 nice cargo build --release -j2 --manifest-path "harness/$c/Cargo.toml")
done
(cd "$OUT/bb_repo" && ulimit -v 8000000 && timeout 1800 python3 -I harness/run.py --kernel session_cpp --jobs 2 --timeout 60) \
  > "$OUT/run_all.log" 2>&1
tail -1 "$OUT/run_all.log"
python3 -I "$HERE/report.py" "$OUT/bb_repo" "$BOARD" "$HERE"
