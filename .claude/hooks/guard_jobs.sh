#!/usr/bin/env bash
# PreToolUse(Bash): refuse a build with more than 8 parallel jobs. -j$(nproc) on 32 cores
# once ran this machine out of 30 GB; cargo -j8 and ninja -j6 were measured safe (2026-09-26).
# exit 2 blocks the call and hands the reason to Claude.
set -u
cmd=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null)
if grep -qE -- '-j *\$\(nproc\)|-j *\$\{?NPROC|--parallel[ =]+(9|[1-9][0-9]+)\b|-j *(9|[1-9][0-9]+)\b' <<<"$cmd"; then
    echo "blocked: more than 8 build jobs; -j\$(nproc) ran this machine out of memory once. Use cargo -j8 or ninja -j6 through buildslot." >&2
    exit 2
fi
exit 0
