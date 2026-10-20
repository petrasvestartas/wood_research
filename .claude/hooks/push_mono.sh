#!/usr/bin/env bash
# Push the stack in DEPENDENCY ORDER, then the superproject.
#
#   .claude/hooks/push_mono.sh                 push what is already committed
#   .claude/hooks/push_mono.sh -m "message"    commit every tracked change first, then push
#
# As a Claude Code hook (UserPromptSubmit, wired in .claude/settings.json with --hook) the
# prompt `pushmono` runs the first form and `pushmono <message>` the second; every other
# prompt passes through untouched and the output goes to Claude as context.
#
# Discover and initialize all submodules, pushing children before their parents.
# Keep the package order session -> wood -> wood_nano -> compas_wood so CI can
# resolve dependency commits. Every other configured repository is included too.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ORDER=()

MESSAGE=""
if [ "${1:-}" = "--hook" ]; then
    # Hook mode: decide from the prompt, then re-run this script as a plain command and
    # hand everything it printed to Claude. Always exit 0 so the output becomes context.
    prompt=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("prompt",""))' 2>/dev/null || true)
    case "$prompt" in
        pushmono) args=() ;;
        pushmono\ *) args=(-m "${prompt#pushmono }") ;;
        *) exit 0 ;;
    esac
    echo "pushmono: running .claude/hooks/push_mono.sh ${args[*]:-}"
    set +e; bash "$0" "${args[@]}" 2>&1; rc=$?
    echo "pushmono: exited $rc - report the result above to the user, do nothing else."
    exit 0
fi
while [ $# -gt 0 ]; do
    case "$1" in
        -m|--message) MESSAGE="${2:-}"; shift 2 ;;
        -h|--help)    sed -n '2,9p' "$0"; exit 0 ;;
        *)            echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

step() { printf '\n== %s ==\n' "$*"; }

# Initialize missing submodules and build a postorder traversal.
collect_repos() {
    local parent="$1"
    local entry key path full name branch
    local paths=()
    [ -f "$parent/.gitmodules" ] || return 0
    if [ "$parent" = "." ]; then
        paths=(session wood wood_nano compas_wood)
    fi
    while IFS= read -r -d '' entry; do
        key=${entry%%$'\n'*}
        path=${entry#*$'\n'}
        case " ${paths[*]:-} " in
            *" $path "*) ;;
            *) paths+=("$path") ;;
        esac
    done < <(git -C "$parent" config -z -f .gitmodules --get-regexp '^submodule\..*\.path$' || true)
    for path in ${paths[@]+"${paths[@]}"}; do
        git -C "$parent" ls-files --stage -- "$path" | grep -q '^160000 ' || continue
        full="$parent/$path"
        if [ ! -e "$full/.git" ]; then
            echo "   initializing repository: $full"
            git -C "$parent" -c fetch.recurseSubmodules=false \
                submodule update -q --init --remote -- "$path"
            while IFS= read -r -d '' entry; do
                if [ "${entry#*$'\n'}" = "$path" ]; then
                    key=${entry%%$'\n'*}
                    name=${key#submodule.}
                    name=${name%.path}
                    break
                fi
            done < <(git -C "$parent" config -z -f .gitmodules --get-regexp '^submodule\..*\.path$')
            branch=$(git -C "$parent" config -f .gitmodules "submodule.$name.branch" || true)
            branch=${branch:-main}
            if [ "$branch" = "." ]; then
                branch=$(git -C "$parent" symbolic-ref --short HEAD)
            fi
            git -C "$full" checkout -q -B "$branch" "origin/$branch"
        fi
        collect_repos "$full"
        ORDER+=("$full")
    done
}
collect_repos "."
ORDER+=(".")

# Validate every repository before pushing anything. Pointer changes are committed
# after children are pushed, even when no explicit message was supplied.
for repo in "${ORDER[@]}"; do
    if ! git -C "$repo" symbolic-ref --quiet HEAD >/dev/null; then
        echo "detached HEAD in $repo - run pullmono first" >&2
        exit 1
    fi
    if [ -z "$MESSAGE" ] && [ -n "$(git -C "$repo" status --porcelain --ignore-submodules=all)" ]; then
        echo "uncommitted changes in $repo; commit them or re-run with -m \"message\"" >&2
        exit 1
    fi
done

for repo in "${ORDER[@]}"; do
    branch=$(git -C "$repo" rev-parse --abbrev-ref HEAD)
    step "$repo ($branch)"

    if [ "$branch" = "HEAD" ]; then
        echo "   detached HEAD - run .claude/hooks/pull_mono.sh (pullmono) first to get back on a branch" >&2
        exit 1
    fi

    git -C "$repo" add -A
    if ! git -C "$repo" diff --cached --quiet; then
        git -C "$repo" commit -q -m "${MESSAGE:-Update submodule pointers}"
        echo "   committed: $(git -C "$repo" log --oneline -1)"
    fi

    # Local history is authoritative for this monorepo stack. Do not pull/rebase here:
    # overwrite the remote branch if it diverged so every package is pushed consistently.
    git -C "$repo" push -q --force origin "$branch"
    echo "   pushed: $(git -C "$repo" log --oneline -1)"
done

step "state"
git submodule status --recursive
