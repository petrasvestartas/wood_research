#!/usr/bin/env bash
# Build the example, run it, publish the scene it wrote, then TELL the open pages instead of
# letting them find out. One command is the whole loop from source to geometry on screen.
#
#   bash/publish_scene.sh                 build 2_contact_detection, run it, publish its live.pb
#   bash/publish_scene.sh --no-build      publish the live.pb already in wood/data/output
#   bash/publish_scene.sh --target NAME   build and run a different example
#   bash/publish_scene.sh some/other.pb   publish a file produced elsewhere (implies --no-build)
#   bash/publish_scene.sh --no-notify     publish without telling the pages (they poll it up)
#
# WHY the notification. An upload is in the bucket in about a second; everything after that is
# the page waiting for its next poll. The machine that published already knows, so it says so, on
# a relay the page has held an SSE connection to since it loaded. The topic is paired with
# DEFAULT_NOTIFY in session_viewer/src/app/live.rs - change one, change the other. The MESSAGE
# CONTENT is ignored by the viewer: it means only "look now", and the page then re-reads the URLs
# its manifest already named. Nothing a stranger puts on the public topic can name bytes.
#
# Publish compressed immutable geometry before updating the live manifest; preserve its
# authored placements and styles. The stable payload remains an alias for existing readers.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUCKET="session-viewer-data"
ENDPOINT="https://0520459c6817bd96c1e25fcb49461c4e.r2.cloudflarestorage.com"
PUBLIC="https://pub-dfd304db921140a09a9ad44c30e0aceb.r2.dev"
PROFILE="r2"
SLOT="pb/view_live.pb"                               # the one key the manifest names
MANIFEST="scenes/view_live.yaml"                     # what session_viewer defaults to (route.rs / live.rs)
NOTIFY_URL="https://ntfy.sh/wood-live-84eaac4a04729911"

TARGET="2_contact_detection"                         # the example whose live.pb is the scene
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
    WORK="${VIEWER_REVIEW_WORK:-${HOME}/viewer_review_work}"
    mkdir -p "$WORK"
    LOG=$(mktemp "$WORK/build-XXXXXX")
    trap 'rm -f "$LOG"' EXIT
    if ! timeout 10m systemd-run --user --scope -q -p MemoryMax=6G cmake --build "$ROOT/wood/build" --config Release --target "$TARGET" --parallel "$JOBS" >"$LOG" 2>&1; then
        cat "$LOG" >&2
        echo "build failed: $TARGET" >&2
        exit 1
    fi
    # Single-config generators (make, ninja) write build/NAME; multi-config (MSVC) build/Release/NAME.exe.
    BIN="$ROOT/wood/build/$TARGET"
    [ -x "$BIN" ] || BIN="$ROOT/wood/build/Release/$TARGET.exe"
    [ -x "$BIN" ] || { echo "built $TARGET, but no executable at wood/build/$TARGET" >&2; exit 1; }
    if ! timeout 10m systemd-run --user --scope -q -p MemoryMax=6G "$BIN" >>"$LOG" 2>&1; then
        cat "$LOG" >&2
        echo "run failed: $TARGET" >&2
        exit 1
    fi
fi

PB="${PB:-$ROOT/wood/data/output/pb/live.pb}"

# -s, not -f: a zero-byte .pb is a run that died mid-write, and it publishes an empty page.
[ -s "$PB" ] || { echo "not a scene: $PB is missing or empty" >&2; exit 1; }

# Download the current manifest so publishing never discards its other files or styles.
WORK="${VIEWER_REVIEW_WORK:-${HOME}/viewer_review_work}"
mkdir -p "$WORK"
PUBLISH_WORK=$(mktemp -d "$WORK/publish-scene-XXXXXX")
trap 'rm -rf "$PUBLISH_WORK"; rm -f "${LOG:-}"' EXIT
curl -fsS --connect-timeout 10 --max-time 30 "$PUBLIC/$MANIFEST" > "$PUBLISH_WORK/view_live.yaml"
if ! R2_NOTIFY_ENABLED="$NOTIFY" bash "$ROOT/session/bash/view_live.sh" "$PUBLISH_WORK/view_live.yaml" "$PB" > "$PUBLISH_WORK/publish.log" 2>&1; then
    cat "$PUBLISH_WORK/publish.log" >&2
    exit 1
fi
printf '%s published in %s ms (compressed revision, manifest preserved)\n' "$SLOT" "$(( $(date +%s%N) / 1000000 - t0 ))"
