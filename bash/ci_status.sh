#!/usr/bin/env bash
# GitHub Actions status for the HEAD of every repository push_mono.sh pushes.
#
#   bash/ci_status.sh           one snapshot, exit 1 when anything failed
#   bash/ci_status.sh --wait    poll every 2 minutes until nothing is queued or running
#
# Authenticates with the github.com token git already stores (credential helper), so it
# needs no gh CLI and is not held to the 60 requests/hour anonymous limit. Read-only.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPOS=(session/session_cpp/session_proto session/session_cpp session/session_py session/session_rust session wood wood_nano compas_wood .)
TOKEN=$(printf "protocol=https\nhost=github.com\n\n" | git credential fill 2>/dev/null | sed -n 's/^password=//p')
AUTH=()
[ -n "$TOKEN" ] && AUTH=(-H "Authorization: Bearer $TOKEN")

snapshot() {
    for repo in "${REPOS[@]}"; do
        local sha slug
        sha=$(git -C "$ROOT/$repo" rev-parse HEAD)
        slug=$(git -C "$ROOT/$repo" remote get-url origin | sed -E 's#.*github.com[:/]##; s#\.git$##')
        curl -s "${AUTH[@]}" "https://api.github.com/repos/$slug/actions/runs?head_sha=$sha&per_page=50" |
            python3 -c '
import json, sys
slug, sha = sys.argv[1], sys.argv[2]
data = json.load(sys.stdin)
if "workflow_runs" not in data:
    print(slug, sha, "API", data.get("message"))
    sys.exit()
if not data["workflow_runs"]:
    print(slug, sha, "(no runs)")
for run in data["workflow_runs"]:
    print(slug, sha, run["status"], run["conclusion"], run["name"], run["html_url"])
' "$slug" "${sha:0:8}"
    done
}

failed_steps() {
    local url="$1" slug run
    slug=$(echo "$url" | sed -E 's#https://github.com/([^/]+/[^/]+)/actions/runs/.*#\1#')
    run=$(echo "$url" | sed -E 's#.*/runs/([0-9]+).*#\1#')
    curl -s "${AUTH[@]}" "https://api.github.com/repos/$slug/actions/runs/$run/jobs?per_page=100" |
        python3 -c '
import json, sys
for job in json.load(sys.stdin).get("jobs", []):
    steps = [step["name"] for step in job["steps"] if step["conclusion"] == "failure"]
    if job["conclusion"] == "failure":
        print("   ", job["name"] + ":", ", ".join(steps), " (log: actions/jobs/" + str(job["id"]) + "/logs)")
'
}

out=$(snapshot)

if [ "${1:-}" = "--wait" ]; then
    while echo "$out" | grep -qE " (in_progress|queued|pending|waiting|requested) "; do
        sleep 120
        out=$(snapshot)
    done
fi

echo "$out"
bad=$(echo "$out" | grep -E " (failure|timed_out|cancelled|startup_failure) | API " || true)

if [ -n "$bad" ]; then
    echo
    echo "FAILED:"
    while read -r line; do
        echo "  $line"
        url=$(echo "$line" | grep -o 'https://github.com/[^ ]*' || true)
        [ -n "$url" ] && failed_steps "$url"
    done <<< "$bad"
    exit 1
fi
