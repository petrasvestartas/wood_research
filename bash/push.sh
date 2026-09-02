#!/usr/bin/env bash
# Push the timber stack in DEPENDENCY ORDER, then the superproject.
#
#   bash/push.sh                 push what is already committed
#   bash/push.sh -m "message"    commit every tracked change first, then push
#
# The order is wood -> wood_nano -> compas_wood, and it is not cosmetic. wood_nano
# compiles wood, compas_wood runs on wood_nano, and each one's CI builds the OTHER TWO
# from their pushed branches - so a wood_nano pushed before the wood commit it needs is
# a red CI run against a wood that does not exist yet.
#
# compas_tf and session_cpp are NOT pushed here. compas_tf belongs to BRG-research and
# session_cpp is developed inside the `session` monorepo; both are consumed here, not
# authored here. Their pointers still move in the superproject commit at the end.
#
# wood_research itself IS pushed, and not only its submodule pointers: README.md, bash/,
# the plans and .claude/ are authored in this repository and nowhere else.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ORDER=(wood wood_nano compas_wood)

MESSAGE=""
while [ $# -gt 0 ]; do
    case "$1" in
        -m|--message) MESSAGE="${2:-}"; shift 2 ;;
        -h|--help)    sed -n '2,12p' "$0"; exit 0 ;;
        *)            echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

step() { printf '\n== %s ==\n' "$*"; }

# One pass over everything BEFORE anything is pushed: a stack half-pushed because repo
# three turned out to be dirty is worse than one that refused to start.
if [ -z "$MESSAGE" ]; then
    blocked=()
    for repo in "${ORDER[@]}"; do
        [ -n "$(git -C "$repo" status --porcelain)" ] && blocked+=("$repo")
    done
    # This repository's OWN files, checked the same way. --ignore-submodules=all because the
    # pointers are SUPPOSED to be dirty here - moving them is what the commit at the end is
    # for - and counting them would make the script refuse to run precisely when it has work.
    if [ -n "$(git status --porcelain --ignore-submodules=all)" ]; then
        blocked+=("wood_research")
    fi
    if [ ${#blocked[@]} -gt 0 ]; then
        echo "uncommitted changes in: ${blocked[*]}" >&2
        echo "commit them yourself, or re-run with -m \"message\" to commit all tracked changes." >&2
        exit 1
    fi
fi

for repo in "${ORDER[@]}"; do
    branch=$(git -C "$repo" rev-parse --abbrev-ref HEAD)
    step "$repo ($branch)"

    if [ "$branch" = "HEAD" ]; then
        echo "   detached HEAD - run bash/pull.sh first to get back on a branch" >&2
        exit 1
    fi

    if [ -n "$MESSAGE" ] && [ -n "$(git -C "$repo" status --porcelain)" ]; then
        git -C "$repo" add -A
        git -C "$repo" commit -q -m "$MESSAGE"
        echo "   committed: $(git -C "$repo" log --oneline -1)"
    fi

    # --ff-only: if the remote moved, stop and let a human merge. A push script is the
    # last place that should be resolving someone else's history.
    git -C "$repo" pull -q --ff-only origin "$branch"
    git -C "$repo" push -q origin "$branch"
    echo "   pushed: $(git -C "$repo" log --oneline -1)"
done

# The superproject records WHICH commit of each submodule this stack was last known to
# work at. Without this commit the pushes above are invisible to a fresh clone: it would
# still check out the old pins.
#
# `git add -A`, not the submodule paths alone: wood_research is a REPOSITORY, not just a set
# of pins. Staging only the pointers left every file authored here behind - committed
# nothing, pushed nothing, and still printed "pushed". The pre-flight above is what makes
# this safe with no -m: it refuses to start when something here needs a commit message.
step "wood_research"
git add -A
if git diff --cached --quiet; then
    echo "   nothing to commit"
else
    git commit -q -m "${MESSAGE:-superproject: $(git diff --cached --name-only | tr '\n' ' ')}"
    echo "   committed: $(git log --oneline -1)"
fi
git push -q origin "$(git rev-parse --abbrev-ref HEAD)"
echo "   pushed"

step "state"
git submodule status
