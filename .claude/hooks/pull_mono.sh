#!/usr/bin/env bash
# Force-sync wood_research and its working submodules to their configured remote branches.
#
#   .claude/hooks/pull_mono.sh
#
# WARNING: REMOTE WINS.
# This intentionally discards local commits, staged/unstaged changes, and untracked files
# (ignored files are kept) in every repository that this script updates.
#
# Unlike a normal `git pull` / pinned `git submodule update`, this script does not require
# old submodule SHAs recorded by a previous local checkout to still exist on the remote.
# It fetches branch tips with submodule recursion disabled, then hard-resets each repository
# to origin/<configured-branch>.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ "${1:-}" = "--hook" ]; then
    prompt=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("prompt",""))' 2>/dev/null || true)
    [ "$prompt" = "pullmono" ] || exit 0
    echo "pullmono: FORCE syncing to remotes; local work will be discarded"
    set +e; bash "$0" 2>&1; rc=$?
    echo "pullmono: exited $rc - report the result above to the user, do nothing else."
    exit 0
fi

step() { printf '\n== %s ==\n' "$*"; }

# Reset one repository to exactly the current tip of origin/<branch>.
# --no-recurse-submodules is important: otherwise a fetch/pull can try to retrieve stale
# submodule SHAs before we have a chance to move those submodules to their branch tips.
force_repo() {
    local repo="$1"
    local branch="$2"

    git -C "$repo" fetch -q --prune --no-recurse-submodules origin "$branch"

    # Throw away tracked local changes/commits first, then put the requested local branch
    # directly on the freshly fetched remote branch.
    git -C "$repo" reset -q --hard
    git -C "$repo" clean -q -fd
    git -C "$repo" checkout -q -B "$branch" "origin/$branch"
    git -C "$repo" reset -q --hard "origin/$branch"
    git -C "$repo" clean -q -fd

    echo "   $(git -C "$repo" log --oneline -1)"
}

# Initialise a submodule from the tip of its configured branch, NOT from the SHA pinned by
# the parent commit. Then attach it to that branch and hard-reset it to origin/<branch>.
force_submodule() {
    local parent="$1"
    local path="$2"
    local branch="$3"
    local full

    if [ "$parent" = "." ]; then
        full="$path"
    else
        full="$parent/$path"
    fi

    # --remote makes the branch tip authoritative instead of the gitlink SHA in the parent.
    git -C "$parent" -c fetch.recurseSubmodules=false \
        submodule update -q --init --remote --force -- "$path"

    force_repo "$full" "$branch"
}

step "wood_research"
branch=$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)
if [ -z "$branch" ]; then
    branch=$(git remote show origin 2>/dev/null | sed -n '/HEAD branch/s/.*: //p')
fi
branch=${branch:-main}
force_repo "." "$branch"

# The reset above may have replaced .gitmodules, so sync URLs/config only afterwards.
git submodule sync -q

# Same dependency order as push_mono.sh. Any remaining top-level submodules follow after it.
ORDER=(session wood wood_nano compas_wood)
rest=()
while read -r _ path; do
    case " ${ORDER[*]} " in
        *" $path "*) ;;
        *) rest+=("$path") ;;
    esac
done < <(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' || true)

step "submodules"
for path in "${ORDER[@]}" "${rest[@]}"; do
    # Skip names from ORDER that are not present in this checkout's .gitmodules.
    name=$(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' 2>/dev/null \
        | awk -v p="$path" '$2 == p {k=$1; sub(/^submodule\./,"",k); sub(/\.path$/,"",k); print k; exit}')
    [ -n "$name" ] || continue

    branch=$(git config -f .gitmodules "submodule.$name.branch" 2>/dev/null || true)
    branch=${branch:-main}
    printf '\n-- %s (%s) --\n' "$path" "$branch"
    force_submodule "." "$path" "$branch"
done

# `session` is itself a monorepo. Only session_cpp is guaranteed to be initialised here;
# session_py/session_rust are force-synced only if they already exist, matching the old
# script's intent and avoiding a large accidental checkout.
if [ -d session ] && [ -f session/.gitmodules ]; then
    git -C session submodule sync -q

    for kernel in session_cpp session_py session_rust; do
        name=$(git -C session config -f .gitmodules --get-regexp '^submodule\..*\.path$' 2>/dev/null \
            | awk -v p="$kernel" '$2 == p {k=$1; sub(/^submodule\./,"",k); sub(/\.path$/,"",k); print k; exit}')
        [ -n "$name" ] || continue

        path="session/$kernel"
        if [ "$kernel" != "session_cpp" ] && [ ! -e "$path/.git" ]; then
            continue
        fi

        branch=$(git -C session config -f .gitmodules "submodule.$name.branch" 2>/dev/null || true)
        branch=${branch:-main}
        printf '\n-- %s (%s) --\n' "$path" "$branch"
        force_submodule "session" "$kernel" "$branch"
    done
fi

# session_cpp has its own small required submodules (for example generated proto/data).
# Follow their configured remote branches too, one by one, so no stale pinned SHA is needed.
if [ -d session/session_cpp ] && [ -f session/session_cpp/.gitmodules ]; then
    git -C session/session_cpp submodule sync -q

    while read -r key dep; do
        name=${key#submodule.}
        name=${name%.path}
        branch=$(git -C session/session_cpp config -f .gitmodules "submodule.$name.branch" 2>/dev/null || true)
        branch=${branch:-main}
        printf '\n-- session/session_cpp/%s (%s) --\n' "$dep" "$branch"
        force_submodule "session/session_cpp" "$dep" "$branch"
    done < <(git -C session/session_cpp config -f .gitmodules --get-regexp '^submodule\..*\.path$' || true)
fi

step "summary"
git status --short --branch --ignore-submodules=dirty
git submodule status || true
printf '\nForce sync complete. Remote branch tips won; local commits/changes/untracked files were discarded.\n'
