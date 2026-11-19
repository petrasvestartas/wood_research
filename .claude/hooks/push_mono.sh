
#!/usr/bin/env bash
# Push all current working branches in the monorepo stack.
#
# - Recursively discovers submodules.
# - Pushes children before parents.
# - Preserves each repository's current branch.
# - Supports detached HEAD using .gitmodules branch configuration.
# - Commits local changes when -m is provided.
# - Updates parent submodule pointers after pushing children.
# - Uses force-with-lease when remote history has diverged.
#
# Usage:
#   push_mono.sh
#   push_mono.sh -m "Update session viewer"
#
# Claude Code hook:
#   pushmono
#   pushmono Update session viewer

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ORDER=()
BRANCHES=()
MESSAGE=""

step() {
    printf '\n========== %s ==========\n' "$*"
}

# Resolve the branch to publish.
# Attached HEAD always takes priority.
# Detached HEAD uses the configured submodule branch.
resolve_branch() {
    local repo="$1"
    local fallback="${2:-main}"
    local branch

    branch=$(git -C "$repo" symbolic-ref --quiet --short HEAD || true)

    if [[ -n "$branch" ]]; then
        echo "$branch"
    else
        echo "$fallback"
    fi
}

# Claude Code hook mode.
if [[ "${1:-}" == "--hook" ]]; then
    prompt=$(python3 -c \
        'import json,sys; print(json.load(sys.stdin).get("prompt",""))' \
        2>/dev/null || true)

    case "$prompt" in
        pushmono)
            args=()
            ;;
        pushmono\ *)
            args=(-m "${prompt#pushmono }")
            ;;
        *)
            exit 0
            ;;
    esac

    echo "pushmono: publishing monorepo"

    set +e
    bash "$0" "${args[@]}" 2>&1
    rc=$?
    set -e

    echo "pushmono: exited $rc"
    exit 0
fi

# Arguments.
while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--message)
            MESSAGE="${2:?Missing commit message}"
            shift 2
            ;;
        -h|--help)
            echo "Usage: push_mono.sh [-m MESSAGE]"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

# Discover repositories recursively.
collect_repos() {
    local parent="$1"
    local parent_branch="$2"
    local entry key path full name configured branch
    local paths=()

    [[ -f "$parent/.gitmodules" ]] || return 0

    # Preserve dependency order.
    if [[ "$parent" == "." ]]; then
        paths=(session wood wood_nano)
    fi

    while IFS= read -r -d '' entry; do
        key="${entry%%$'\n'*}"
        path="${entry#*$'\n'}"

        case " ${paths[*]:-} " in
            *" $path "*) ;;
            *) paths+=("$path") ;;
        esac
    done < <(
        git -C "$parent" config -z -f .gitmodules \
            --get-regexp '^submodule\..*\.path$' || true
    )

    for path in "${paths[@]}"; do

        # Only actual submodules.
        git -C "$parent" ls-files --stage -- "$path" |
            grep -q '^160000 ' || continue

        full="$parent/$path"

        # Initialize missing submodules at their recorded commit.
        if ! git -C "$full" rev-parse --git-dir >/dev/null 2>&1; then
            echo "Initializing $full"
            git -C "$parent" submodule update --init -- "$path"
        fi

        # Find submodule configuration name.
        name=""

        while IFS= read -r -d '' entry; do
            key="${entry%%$'\n'*}"
            configured="${entry#*$'\n'}"

            if [[ "$configured" == "$path" ]]; then
                name="${key#submodule.}"
                name="${name%.path}"
                break
            fi
        done < <(
            git -C "$parent" config -z -f .gitmodules \
                --get-regexp '^submodule\..*\.path$'
        )

        # Resolve configured branch for detached HEAD.
        configured=""

        if [[ -n "$name" ]]; then
            configured=$(
                git -C "$parent" config -f .gitmodules \
                    "submodule.$name.branch" || true
            )
        fi

        if [[ "$configured" == "." ]]; then
            configured="$parent_branch"
        elif [[ -z "$configured" ]]; then
            configured="main"
        fi

        # Attached branch wins; detached HEAD uses configuration.
        branch=$(resolve_branch "$full" "$configured")

        git check-ref-format --branch "$branch" >/dev/null || {
            echo "Invalid branch $branch in $full" >&2
            exit 1
        }

        echo "Discovered: $full -> $branch"

        collect_repos "$full" "$branch"

        # Postorder: child before parent.
        ORDER+=("$full")
        BRANCHES+=("$branch")
    done
}

# Root must have a named branch.
ROOT_BRANCH=$(resolve_branch "." "")

if [[ -z "$ROOT_BRANCH" ]]; then
    echo "Root repository is detached. Checkout a branch first." >&2
    exit 1
fi

collect_repos "." "$ROOT_BRANCH"

# Root goes last.
ORDER+=(".")
BRANCHES+=("$ROOT_BRANCH")

step "DISCOVERED REPOSITORIES"

for i in "${!ORDER[@]}"; do
    printf "%-35s -> %s\n" "${ORDER[$i]}" "${BRANCHES[$i]}"
done

# Validate everything before modifying anything.
step "VALIDATION"

for repo in "${ORDER[@]}"; do

    git -C "$repo" rev-parse --verify HEAD >/dev/null

    if ! git -C "$repo" remote get-url origin >/dev/null 2>&1; then
        echo "Missing origin remote: $repo" >&2
        exit 1
    fi

    if [[ -n "$(git -C "$repo" ls-files -u)" ]]; then
        echo "Unresolved conflicts in $repo" >&2
        exit 1
    fi

    if [[ -z "$MESSAGE" ]] &&
       [[ -n "$(git -C "$repo" status --porcelain --ignore-submodules=all)" ]]; then
        echo "Uncommitted changes in $repo." >&2
        echo "Run again with -m \"your message\"." >&2
        exit 1
    fi

    echo "OK: $repo"
done

# Commit local changes and submodule pointer changes.
step "COMMIT"

for repo in "${ORDER[@]}"; do

    echo
    echo "Repository: $repo"

    git -C "$repo" add -A

    if ! git -C "$repo" diff --cached --quiet; then

        commit_message="${MESSAGE:-Update submodule pointers}"

        git -C "$repo" commit -m "$commit_message"

        echo "Committed: $(git -C "$repo" log -1 --oneline)"
    else
        echo "Nothing to commit."
    fi
done

# Push every repository to its resolved branch.
step "PUSH"

for i in "${!ORDER[@]}"; do

    repo="${ORDER[$i]}"
    branch="${BRANCHES[$i]}"

    echo
    step "$repo -> origin/$branch"

    # Ensure remote branch state is known.
    remote_sha=$(
        git -C "$repo" ls-remote origin "refs/heads/$branch" |
            awk 'NR == 1 {print $1}'
    )

    if [[ -n "$remote_sha" ]]; then

        # Fetch remote branch into a private tracking ref.
        git -C "$repo" fetch --no-tags origin \
            "+refs/heads/$branch:refs/remotes/push_mono/$branch"

        remote_sha=$(
            git -C "$repo" rev-parse "refs/remotes/push_mono/$branch"
        )

        # Publish local HEAD, even when detached.
        # Force-with-lease prevents overwriting a concurrent update.
        git -C "$repo" push \
            --force-with-lease="refs/heads/$branch:$remote_sha" \
            origin "HEAD:refs/heads/$branch"

    else

        # New remote branch.
        git -C "$repo" push \
            origin "HEAD:refs/heads/$branch"

    fi

    echo "PUSHED: $repo -> origin/$branch"
    echo "Commit: $(git -C "$repo" log -1 --oneline)"
done

step "FINAL STATE"

git submodule status --recursive

echo
echo "======================================"
echo "SUCCESS: ALL REPOSITORIES PUSHED"
echo "======================================"
