#!/usr/bin/env bash
# Bring every submodule to the tip of the branch this superproject tracks for it.
#
#   bash/pull.sh
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

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

step() { printf '\n== %s ==\n' "$*"; }

step "checkout"
# --init for a fresh clone. NOT --recursive: `session` is the whole monorepo and recursing
# would drag in session_rust, session_py and session_data at the top level - gigabytes this
# stack never compiles. Only the kernel is pulled out of it, below.
git submodule update --init

dirty=()
for path in $(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}'); do
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

step "summary"
git submodule status
if [ ${#dirty[@]} -gt 0 ]; then
    printf '\nNOT updated (uncommitted changes): %s\n' "${dirty[*]}"
    echo "Commit or stash there, then re-run."
fi

cat <<'EOF'

Sources are current. To rebuild what compiles against them:
    bash/update_session.sh
EOF
