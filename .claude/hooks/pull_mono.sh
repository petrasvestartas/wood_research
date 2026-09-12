#!/usr/bin/env bash
# Bring wood_research and every submodule to the tip of the branch it tracks.
#
#   .claude/hooks/pull_mono.sh
#
# As a Claude Code hook (UserPromptSubmit, wired in .claude/settings.json with --hook) the
# prompt `pullmono` runs it; every other prompt passes through untouched and the output
# goes to Claude as context.
#
# The mirror of push_mono.sh: the same repos in the same dependency order (session
# kernels -> session -> wood -> wood_nano -> compas_wood), then compas_tf, and the
# superproject itself - whose bash/, README.md, docs/ and .claude/ are authored here, so a
# run that moved only the submodules would leave the tooling that drives them behind.
#
# `git submodule update` alone is not enough. It checks each submodule out at the commit
# the superproject pins, on a DETACHED HEAD - correct for reproducing a commit, wrong for
# working in one: an edit committed there sits on no branch and the next update silently
# leaves it behind. So every submodule is put back on the branch named in .gitmodules
# (wood/wood_nano/compas_wood: dev, compas_tf: assembly-steps, session: main) and
# fast-forwarded.
#
# A submodule with uncommitted changes is fetched but NOT moved. Pulling over local work
# is how it gets lost; the script reports it and goes on to the next one.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ "${1:-}" = "--hook" ]; then
    # Hook mode: run only for the prompt `pullmono`, re-run as a plain command and hand
    # everything it printed to Claude. Always exit 0 so the output becomes context.
    prompt=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("prompt",""))' 2>/dev/null || true)
    [ "$prompt" = "pullmono" ] || exit 0
    echo "pullmono: running .claude/hooks/pull_mono.sh"
    set +e; bash "$0" 2>&1; rc=$?
    echo "pullmono: exited $rc - report the result above to the user, do nothing else."
    exit 0
fi

step() { printf '\n== %s ==\n' "$*"; }

step "wood_research"
branch=$(git rev-parse --abbrev-ref HEAD)
if [ -n "$(git status --porcelain --ignore-submodules=all)" ]; then
    echo "   local changes - not moved, still at $(git log --oneline -1)"
elif git pull -q --ff-only origin "$branch"; then
    echo "   $(git log --oneline -1)"
else
    echo "   not a fast-forward - merge it yourself, then re-run" >&2
    exit 1
fi

step "checkout"
# --init for a fresh clone. NOT --recursive: `session` is the whole monorepo and recursing
# would drag in session_rust, session_py and session_data at the top level - gigabytes this
# stack never compiles. Only the kernel is pulled out of it, below.
git submodule update --init

# The same order push_mono.sh uses. Pulling is independent per repo, so this changes no
# outcome today - it is here so that reordering .gitmodules cannot silently reorder a run,
# and so a stack pulled top to bottom can be built as it goes. compas_tf follows: consumed
# here, authored elsewhere.
ORDER=(session wood wood_nano compas_wood)
rest=()
for path in $(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}'); do
    case " ${ORDER[*]} " in *" $path "*) ;; *) rest+=("$path") ;; esac
done

dirty=()
for path in "${ORDER[@]}" "${rest[@]}"; do
    branch=$(git config -f .gitmodules "submodule.$path.branch" || echo main)
    printf '\n-- %s (%s) --\n' "$path" "$branch"

    git -C "$path" fetch -q origin

    if [ -n "$(git -C "$path" status --porcelain)" ]; then
        dirty+=("$path")
        echo "   local changes - not moved, still at $(git -C "$path" log --oneline -1)"
        # `submodule update` above leaves a submodule detached whenever the pin and the
        # branch disagree, and this one is not being moved, so say so: uncommitted work on
        # a detached HEAD is the case where a later update really does throw it away.
        git -C "$path" symbolic-ref -q HEAD >/dev/null \
            || echo "   WARNING: detached HEAD with uncommitted changes - commit on a branch before updating"
        continue
    fi

    git -C "$path" checkout -q "$branch"
    git -C "$path" pull -q --ff-only
    echo "   $(git -C "$path" log --oneline -1)"
done

# The kernel is `session/session_cpp`, which wood and wood_nano resolve as
# `../session/session_cpp`. --recursive because session_cpp has its own two (session_proto,
# session_data) and a kernel without its generated protobuf sources fails to CONFIGURE
# rather than to build - a confusing place to land.
git -C session submodule update --init --recursive session_cpp

# The kernels are authored here too (push_mono.sh pushes them), so each one that is checked
# out goes back on its branch and fast-forwards, under the same dirty rule as above.
for kernel in session_cpp session_py session_rust; do
    path="session/$kernel"
    [ -f "$path/.git" ] || [ -d "$path/.git" ] || continue
    branch=$(git -C session config -f .gitmodules "submodule.$kernel.branch" || echo main)
    printf '\n-- %s (%s) --\n' "$path" "$branch"
    git -C "$path" fetch -q origin
    if [ -n "$(git -C "$path" status --porcelain)" ]; then
        dirty+=("$path")
        echo "   local changes - not moved, still at $(git -C "$path" log --oneline -1)"
        continue
    fi
    git -C "$path" checkout -q "$branch"
    git -C "$path" pull -q --ff-only
    echo "   $(git -C "$path" log --oneline -1)"
done

step "summary"
git submodule status
if [ ${#dirty[@]} -gt 0 ]; then
    printf '\nNOT updated (uncommitted changes): %s\n' "${dirty[*]}"
    echo "Commit or stash there, then re-run."
fi
