#!/usr/bin/env bash
# Force-sync wood_research and all its submodules to their configured remote branches.
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

    git -C "$repo" fetch -q --prune --no-recurse-submodules origin "+refs/heads/$branch:refs/remotes/origin/$branch"

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

# Read each repository after resetting it: its remote may add or remove submodules.
force_children() {
    local parent="$1"
    local entry key path name branch full
    [ -f "$parent/.gitmodules" ] || return 0
    git -C "$parent" submodule sync -q
    while IFS= read -r -d '' entry; do
        key=${entry%%$'\n'*}
        path=${entry#*$'\n'}
        if ! git -C "$parent" ls-files --stage -- "$path" | grep -q '^160000 '; then
            printf '   skipping stale .gitmodules entry: %s/%s\n' "$parent" "$path"
            continue
        fi
        name=${key#submodule.}
        name=${name%.path}
        branch=$(git -C "$parent" config -f .gitmodules "submodule.$name.branch" || true)
        branch=${branch:-main}
        if [ "$branch" = "." ]; then
            branch=$(git -C "$parent" symbolic-ref --short HEAD)
        fi
        full="$parent/$path"
        printf '\n-- %s (%s) --\n' "$full" "$branch"
        force_submodule "$parent" "$path" "$branch"
        force_children "$full"
    done < <(git -C "$parent" config -z -f .gitmodules --get-regexp '^submodule\..*\.path$' || true)
}

step "submodules"
force_children "."

step "summary"
git status --short --branch --ignore-submodules=dirty
git submodule status --recursive
printf '\nForce sync complete. Remote branch tips won; local commits/changes/untracked files were discarded.\n'
