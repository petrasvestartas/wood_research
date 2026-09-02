#!/usr/bin/env bash
# Build the example, run it, publish the scene it wrote, then TELL the open pages instead of
# letting them find out. One command is the whole loop from source to geometry on screen.
#
#   bash/publish_scene.sh                 build main_face_to_face, run it, publish its live.pb
#   bash/publish_scene.sh --no-build      publish the live.pb already in wood/data/output
#   bash/publish_scene.sh --target NAME   build and run a different example
#   bash/publish_scene.sh some/other.pb   publish a file produced elsewhere (implies --no-build)
#   bash/publish_scene.sh --no-notify     publish without telling the pages (they poll it up)
#
# WHY the notification. A push is on GitHub in about a second; everything after that is the page
# waiting for permission to ask whether anything moved. Anonymous browsers get 60 GitHub API
# calls an hour per address, so session_viewer budgets one every two minutes - that quota, not
# the network, is the whole delay. The machine that pushed already knows the sha, so it says so,
# on a relay the page has held an SSE connection to since it loaded. The topic is paired with
# DEFAULT_NOTIFY in session_viewer/src/app/live.rs - change one, change the other. It carries a
# commit sha and nothing else, never geometry, and the viewer refuses anything that is not hex.
#
# ONE SLOT, ONE COMMIT. Everything is published as pb/live.pb, the path the manifest already
# names, so no manifest edit is ever needed. And each publish is a PARENTLESS commit that
# replaces the branch: what it replaces becomes unreachable the moment it lands, so republishing
# this slot forever costs the repository nothing. The trade is that the branch keeps no history -
# it is a snapshot of what is published, not a record of what was - and only this script writes
# to it. Nothing is built or deployed ON GITHUB by a push; see README.md.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_URL="https://github.com/petrasvestartas/session.git"
BRANCH="session_viewer_data"
SLOT="pb/live.pb"                                    # the one path the manifest names
MANIFEST="session_viewer.toml"
NOTIFY_URL="https://ntfy.sh/wood-live-84eaac4a04729911"
# A persistent checkout, not a temp dir: the clone is partial and shallow, but re-cloning it on
# every publish would still be the network round trip this whole script exists to avoid.
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/wood_research/$BRANCH"

TARGET="main_face_to_face"                           # the example whose live.pb is the scene
JOBS=4
NOTIFY=1
BUILD=1
PB=""
while [ $# -gt 0 ]; do
    case "$1" in
        --no-notify) NOTIFY=0; shift ;;
        --no-build)  BUILD=0; shift ;;
        --target)    TARGET="${2:?--target needs an example name}"; shift 2 ;;
        -h|--help)   sed -n '2,9p' "$0"; exit 0 ;;
        -*)          echo "unknown argument: $1" >&2; exit 2 ;;
        *)           PB="$1"; shift ;;
    esac
done

# t0 covers EVERYTHING, build included, because the number in the report is meant to answer the
# only question anyone asks here: how long from "go" to geometry on screen.
t0=$(( $(date +%s%N) / 1000000 ))

# BUILD AND RUN FIRST, so that what is published is what this source tree currently produces.
# Publishing without it ships whatever live.pb an earlier run happened to leave behind - which
# looks identical and is the one failure mode this script cannot report.
#
# Incremental: ~0.5 s when nothing changed, and only the cost of what actually recompiled when
# something did. Skipped when a .pb argument names a file this script did not produce and does
# not know how to rebuild, and skipped by --no-build to republish what is already on disk.
#
# Build and run output goes to a log and is shown ONLY ON FAILURE. Callers quote this script's
# stdout verbatim, so stdout stays the single report line at the bottom: a broken build has to
# be loud, a working one silent.
if [ "$BUILD" = 1 ] && [ -z "$PB" ]; then
    LOG=$(mktemp)
    trap 'rm -f "$LOG"' EXIT
    if ! cmake --build "$ROOT/wood/build" --config Release --target "$TARGET" --parallel "$JOBS" >"$LOG" 2>&1; then
        cat "$LOG" >&2
        echo "build failed: $TARGET" >&2
        exit 1
    fi
    # Single-config generators (make, ninja) write build/NAME; multi-config (MSVC) build/Release/NAME.exe.
    BIN="$ROOT/wood/build/$TARGET"
    [ -x "$BIN" ] || BIN="$ROOT/wood/build/Release/$TARGET.exe"
    [ -x "$BIN" ] || { echo "built $TARGET, but no executable at wood/build/$TARGET" >&2; exit 1; }
    if ! "$BIN" >>"$LOG" 2>&1; then
        cat "$LOG" >&2
        echo "run failed: $TARGET" >&2
        exit 1
    fi
fi

PB="${PB:-$ROOT/wood/data/output/pb/live.pb}"

# -s, not -f: a zero-byte .pb is a run that died mid-write, and it publishes an empty page.
[ -s "$PB" ] || { echo "not a scene: $PB is missing or empty" >&2; exit 1; }

# --filter=blob:none + a sparse checkout of two paths: the branch is 130 MB of published scenes
# and none of it needs to be here to add one file to it.
if [ ! -d "$CACHE/.git" ]; then
    echo "first run: cloning $BRANCH into $CACHE"
    git clone --quiet --filter=blob:none --no-checkout --depth 1 --branch "$BRANCH" "$REPO_URL" "$CACHE"
    git -C "$CACHE" sparse-checkout set --no-cone "$SLOT" "$MANIFEST"
    git -C "$CACHE" checkout --quiet
fi

# A commit with NO PARENT. git keeps every version of every file it is given and offers no
# per-file opt out, so the only way to republish one slot indefinitely without the repository
# growing is to leave nothing behind: this tree still carries every scene the branch publishes
# (unchanged blobs are already on the remote), while the live.pb it replaces goes unreachable.
stage() {
    mkdir -p "$CACHE/$(dirname "$SLOT")"
    cp "$PB" "$CACHE/$SLOT"
    git -C "$CACHE" add -- "$SLOT"
}
commit() { git -C "$CACHE" commit-tree "$(git -C "$CACHE" write-tree)" -m "live: $(date -u +%FT%TZ)"; }

stage
# NO PRE-FETCH: this checkout is the only thing that writes here, so it is already at the tip.
git -C "$CACHE" diff --cached --quiet && { echo "$SLOT  unchanged - nothing published"; exit 0; }

SHA=$(commit)
git -C "$CACHE" push --quiet --force-with-lease origin "$SHA:refs/heads/$BRANCH" 2>/dev/null || {
    # The lease was refused: the branch is not where this checkout left it, so something else
    # published. Take its tip and replay this scene on top - never overwrite a stranger's push
    # without having looked at it first.
    echo "branch moved under us - replaying this publish on top of it" >&2
    git -C "$CACHE" fetch --quiet --depth 1 origin "$BRANCH"
    git -C "$CACHE" reset --quiet --hard "origin/$BRANCH"
    stage
    SHA=$(commit)
    git -C "$CACHE" push --quiet --force origin "$SHA:refs/heads/$BRANCH"
}
git -C "$CACHE" update-ref "refs/heads/$BRANCH" "$SHA"
git -C "$CACHE" reset --quiet --soft "$SHA"

# ONE LINE, ALWAYS THE SAME SHAPE: which slot was updated, how big it is, and whether the viewer
# was told. Callers quote this line verbatim, so it must not vary with what the scene contains.
#
# "notified" is the honest claim and the strongest one available here: the relay accepted the
# sha. Whether a page was open to hear it, and whether it finished drawing, is something only
# the page knows - this script never hears back. It is also why no on-screen time is guessed any
# more: the page still has to fetch the whole uncompressed file from raw.githubusercontent, so
# an estimate that ignored the size was wrong by seconds on a scene like this one.
MB=$(awk -v b="$(stat -c%s "$PB" 2>/dev/null || stat -f%z "$PB")" 'BEGIN{printf "%.1f", b/1048576}')
if [ "$NOTIFY" = 0 ]; then
    echo "$SLOT  ${MB} MB  ${SHA:0:7}  published in $(( $(date +%s%N) / 1000000 - t0 )) ms, viewer not notified (--no-notify)"
# --connect-timeout 1: the relay is a free public service and it does go down (measured
# 2026-09-02, both A and AAAA refusing). When it does, a 5 s ceiling meant every publish sat
# waiting out a dead socket - 5 s added to a 4 s job, to learn nothing. One second to open the
# connection is generous for a POST that carries 40 bytes, and losing the notification only
# costs what the line below says: the pages fall back to polling.
elif curl -sf --connect-timeout 1 -m 3 -o /dev/null -d "$SHA" "$NOTIFY_URL"; then
    echo "$SLOT  ${MB} MB  ${SHA:0:7}  viewer notified in $(( $(date +%s%N) / 1000000 - t0 )) ms"
else
    echo "$SLOT  ${MB} MB  ${SHA:0:7}  VIEWER NOT NOTIFIED - relay down, open pages poll it up within 2 min" >&2
fi

# The manifest is what the page reads; a push it does not name shows nothing.
grep -q "$SLOT" "$CACHE/$MANIFEST" || {
    echo "WARNING: $MANIFEST on $BRANCH does not list \"$SLOT\" - the page will not show this." >&2
    echo "         Add, once:  [[items]] / file = \"$SLOT\" / name = \"live\" / at = [0, 0, 0]" >&2
}
