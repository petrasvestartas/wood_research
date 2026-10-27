#!/usr/bin/env bash
# Force-sync wood_research and its working submodules to their configured remote branches.
#
#   bash .claude/hooks/pull_mono.sh [--all-sources]
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

main() {
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ALL_SOURCES=false
HOOK=false
NESTED_ONLY=false
FORCE=false
for argument in "$@"; do
    case "$argument" in
        --all-sources) ALL_SOURCES=true ;;
        --nested-only) NESTED_ONLY=true; ALL_SOURCES=true ;;
        --hook) HOOK=true ;;
        --force) FORCE=true ;;
        --help|-h)
            echo 'Usage: bash .claude/hooks/pull_mono.sh [--all-sources | --nested-only] [--hook] [--force]'
            echo 'Sync remote branches. Refuses local changes or unpublished commits unless --force is explicit.'
            echo '--all-sources initializes every nested submodule, including the Python and Rust kernels and data.'
            echo '--nested-only resumes nested source synchronization without resetting top-level repositories.'
            return 0 ;;
        *) echo "Unknown option: $argument" >&2; return 2 ;;
    esac
done

if $HOOK; then
    # Windows Store python aliases are not usable interpreters. Git Bash can use PowerShell.
    if command -v powershell.exe >/dev/null 2>&1; then
        prompt=$(powershell.exe -NoProfile -NonInteractive -Command \
            'try { ([Console]::In.ReadToEnd() | ConvertFrom-Json).prompt } catch { exit 1 }' 2>/dev/null || true)
        prompt=${prompt//$'\r'/}
    else
        prompt=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("prompt",""))' 2>/dev/null || true)
    fi
    case "$prompt" in
        pullmono|"pull mono") ;;
        "pullmono --all-sources"|"pull mono --all-sources") ALL_SOURCES=true ;;
        *) return 0 ;;
    esac
    echo "pullmono: syncing remote branches; local work requires explicit --force"
    options=()
    $FORCE && options+=(--force)
    $ALL_SOURCES && options+=(--all-sources)
    set +e; bash "$0" "${options[@]}" 2>&1; rc=$?
    echo "pullmono: exited $rc - report the result above to the user, do nothing else."
    exit 0
fi

# Check every existing checkout before any mutation, including the parent reset.
if ! $FORCE; then
    if [ -n "$(git status --porcelain --untracked-files=normal --ignore-submodules=none)" ] ||
       [ -n "$(git log -1 --format=%H HEAD --branches --not --remotes)" ] ||
       ! git submodule foreach --quiet --recursive 'test -z "$(git status --porcelain --untracked-files=normal --ignore-submodules=none)" && test -z "$(git log -1 --format=%H HEAD --branches --not --remotes)"'; then
        echo 'Local changes or unpublished commits detected. Preserve them before syncing; --force explicitly discards them.' >&2
        return 2
    fi
fi

step() { printf '\n== %s ==\n' "$*"; }

# Reset one repository to exactly the current tip of origin/<branch>.
# --no-recurse-submodules is important: otherwise a fetch/pull can try to retrieve stale
# submodule SHAs before we have a chance to move those submodules to their branch tips.
force_repo() {
    local repo="$1"
    local branch="$2"

    git -C "$repo" fetch -q --prune --no-recurse-submodules origin "+refs/heads/$branch:refs/remotes/origin/$branch"
    if ! $FORCE && ! git -C "$repo" merge-base --is-ancestor HEAD "origin/$branch"; then
        echo "Refusing divergent history in $repo; preserve it before using --force." >&2
        return 2
    fi

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
if ! $NESTED_ONLY; then
branch=$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)
if [ -z "$branch" ]; then
    branch=$(git remote show origin 2>/dev/null | sed -n '/HEAD branch/s/.*: //p')
fi
branch=${branch:-main}
force_repo "." "$branch"
fi

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
    $NESTED_ONLY && continue
    # Skip names from ORDER that are not present in this checkout's .gitmodules.
    name=$(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' 2>/dev/null \
        | awk -v p="$path" '$2 == p {k=$1; sub(/^submodule\./,"",k); sub(/\.path$/,"",k); print k; exit}')
    [ -n "$name" ] || continue

    branch=$(git config -f .gitmodules "submodule.$name.branch" 2>/dev/null || true)
    branch=${branch:-main}
    printf '\n-- %s (%s) --\n' "$path" "$branch"
    force_submodule "." "$path" "$branch"
done

sync_children() {
    local parent="$1" entry key path name branch
    [ -f "$parent/.gitmodules" ] || return 0
    git -C "$parent" submodule sync -q
    while IFS= read -r -d '' entry; do
        key=${entry%%$'\n'*}
        path=${entry#*$'\n'}
        if ! git -C "$parent" ls-files --stage -- "$path" | grep -q '^160000 '; then
            printf '   Skipping stale .gitmodules entry: %s/%s (no gitlink)\n' "$parent" "$path"
            continue
        fi
        name=${key#submodule.}
        name=${name%.path}
        branch=$(git -C "$parent" config -f .gitmodules "submodule.$name.branch" 2>/dev/null || true)
        if [ "$branch" = "." ]; then
            branch=$(git -C "$parent" symbolic-ref --quiet --short HEAD)
        fi
        branch=${branch:-main}
        printf '\n-- %s/%s (%s) --\n' "$parent" "$path" "$branch"
        force_submodule "$parent" "$path" "$branch"
        sync_children "$parent/$path"
    done < <(git -C "$parent" config -z -f .gitmodules --get-regexp '^submodule\..*\.path$' || true)
}

if $ALL_SOURCES; then
    for path in "${ORDER[@]}" "${rest[@]}"; do
        [ -e "$path/.git" ] || continue
        sync_children "$path"
    done
fi

# `session` is itself a monorepo. Only session_cpp is guaranteed to be initialised by default;
# session_py/session_rust are force-synced only if they already exist, matching the old
# script's intent and avoiding a large accidental checkout.
if ! $ALL_SOURCES && [ -d session ] && [ -f session/.gitmodules ]; then
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
if ! $ALL_SOURCES && [ -d session/session_cpp ] && [ -f session/session_cpp/.gitmodules ]; then
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
}

# Parse the complete function before resetting: origin may replace this script while it runs.
main "$@"
