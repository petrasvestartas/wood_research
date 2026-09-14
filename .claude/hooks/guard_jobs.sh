#!/usr/bin/env bash
# PreToolUse(Bash): refuse a build with more than 4 parallel jobs. -j$(nproc) on 32 cores
# once ran this machine out of 30 GB; exit 2 blocks the call and hands the reason to Claude.
set -u
cmd=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null)
if grep -qE -- '-j *\$\(nproc\)|-j *\$\{?NPROC|--parallel[ =]+([5-9]|[1-9][0-9]+)\b|-j *([5-9]|[1-9][0-9]+)\b' <<<"$cmd"; then
    echo "blocked: more than 4 build jobs ran this machine out of memory once. Use -j4 / --parallel 4 and one build at a time." >&2
    exit 2
fi
exit 0
