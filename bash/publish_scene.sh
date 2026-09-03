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
# WHY the notification. An upload is in the bucket in about a second; everything after that is
# the page waiting for its next poll. The machine that published already knows, so it says so, on
# a relay the page has held an SSE connection to since it loaded. The topic is paired with
# DEFAULT_NOTIFY in session_viewer/src/app/live.rs - change one, change the other. The MESSAGE
# CONTENT is ignored by the viewer: it means only "look now", and the page then re-reads the URLs
# its manifest already named. Nothing a stranger puts on the public topic can name bytes.
#
# ONE SLOT, OVERWRITTEN. Everything is published as pb/view_live.pb, the key the manifest already
# names, so no manifest edit is ever needed. Cloudflare R2 keeps no versions: this REPLACES the
# object and the bytes it replaces are gone. That is the whole reason the git machinery this
# script used to carry - parentless commits, a sparse checkout, force-with-lease - is gone with
# it. The storage keeps a snapshot of what is published, never a record of what was.
#
# The r2.dev public URL is not CDN-cached, so an overwrite is served on the very next request and
# there is nothing to purge. The viewer notices it because every poll re-reads each listed file
# with If-None-Match and the ETag moved. See session/bash/view_live.sh for publishing by hand.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUCKET="session-viewer-data"
ENDPOINT="https://0520459c6817bd96c1e25fcb49461c4e.r2.cloudflarestorage.com"
PUBLIC="https://pub-dfd304db921140a09a9ad44c30e0aceb.r2.dev"
PROFILE="r2"
SLOT="pb/view_live.pb"                               # the one key the manifest names
MANIFEST="view_live.toml"
NOTIFY_URL="https://ntfy.sh/wood-live-84eaac4a04729911"

# `aws` is installed per-user by `uv tool install awscli`, which can land outside PATH.
aws_r2() {
    local bin=""
    # `|| bin=""` matters: under `set -e` an assignment from a failing command substitution
    # aborts the script, so a missing `aws` would exit 1 with NO message at all.
    bin=$(command -v aws 2>/dev/null) || bin=""
    if [ -z "$bin" ]; then
        for c in "$HOME/.local/bin/aws" "$HOME"/snap/code/*/.local/bin/aws; do
            [ -x "$c" ] && { bin="$c"; break; }
        done
    fi
    [ -n "$bin" ] || { echo "no 'aws' on PATH - install it with: uv tool install awscli" >&2; return 127; }
    "$bin" --profile "$PROFILE" --endpoint-url "$ENDPOINT" "$@"
}

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

grep -q "^\\[${PROFILE}\\]" "$HOME/.aws/credentials" 2>/dev/null || {
    echo "no [${PROFILE}] profile in ~/.aws/credentials - see session/bash/lib/view.sh" >&2
    exit 1
}

# UNCHANGED MEANS UNPUBLISHED. R2 returns the object's md5 as its ETag for a single-part upload,
# so the local digest answers "would this change anything?" without sending the file. A multipart
# ETag carries a `-<parts>` suffix and is not an md5 of the whole object; there is nothing cheap
# to compare then, so those always upload.
if command -v md5sum >/dev/null 2>&1; then
    LOCAL_MD5=$(md5sum "$PB" | cut -d' ' -f1)
else
    LOCAL_MD5=$(md5 -q "$PB")                        # BSD/macOS
fi
REMOTE_ETAG=$(curl -sSI "$PUBLIC/$SLOT" | tr -d '\r' | awk 'tolower($1)=="etag:" {gsub(/"/,"",$2); print $2}')
case "$REMOTE_ETAG" in
    *-*) ;;                                          # multipart: not comparable, upload anyway
    "$LOCAL_MD5") echo "$SLOT  unchanged - nothing published"; exit 0 ;;
esac

aws_r2 s3 cp "$PB" "s3://$BUCKET/$SLOT" --no-progress >/dev/null

# VERIFY IT SERVES, not just that aws accepted it. An upload that lands but is not served leaves
# the page drawing the previous scene, which looks like a success from here.
SIZE=$(stat -c%s "$PB" 2>/dev/null || stat -f%z "$PB")
SERVED=$(curl -sSI "$PUBLIC/$SLOT" | tr -d '\r' | awk 'tolower($1)=="content-length:" {print $2}')
[ "$SERVED" = "$SIZE" ] || {
    echo "published $SIZE bytes but $PUBLIC/$SLOT serves '${SERVED:-nothing}'" >&2
    exit 1
}
TAG="${LOCAL_MD5:0:7}"

# ONE LINE, ALWAYS THE SAME SHAPE: which slot was updated, how big it is, and whether the viewer
# was told. Callers quote this line verbatim, so it must not vary with what the scene contains.
#
# "notified" is the honest claim and the strongest one available here: the relay accepted the
# message. Whether a page was open to hear it, and whether it finished drawing, is something only
# the page knows - this script never hears back. It is also why no on-screen time is guessed any
# more: the page still has to fetch the whole uncompressed file from the bucket, so
# an estimate that ignored the size was wrong by seconds on a scene like this one.
MB=$(awk -v b="$(stat -c%s "$PB" 2>/dev/null || stat -f%z "$PB")" 'BEGIN{printf "%.1f", b/1048576}')
if [ "$NOTIFY" = 0 ]; then
    echo "$SLOT  ${MB} MB  ${TAG}  published in $(( $(date +%s%N) / 1000000 - t0 )) ms, viewer not notified (--no-notify)"
# --connect-timeout 1: the relay is a free public service and it does go down (measured
# 2026-09-02, both A and AAAA refusing). When it does, a 5 s ceiling meant every publish sat
# waiting out a dead socket - 5 s added to a 4 s job, to learn nothing. One second to open the
# connection is generous for a POST that carries a key name, and losing the notification only
# costs what the line below says: the pages fall back to polling.
elif curl -sf --connect-timeout 1 -m 3 -o /dev/null -d "$SLOT" "$NOTIFY_URL"; then
    echo "$SLOT  ${MB} MB  ${TAG}  viewer notified in $(( $(date +%s%N) / 1000000 - t0 )) ms"
else
    echo "$SLOT  ${MB} MB  ${TAG}  VIEWER NOT NOTIFIED - relay down, open pages poll it up within 5 s" >&2
fi

# The manifest is what the page reads; an upload it does not name shows nothing.
curl -sS "$PUBLIC/$MANIFEST" | grep -q "$SLOT" || {
    echo "WARNING: $MANIFEST in $BUCKET does not list \"$SLOT\" - the page will not show this." >&2
    echo "         Add, once:  [[items]] / file = \"$SLOT\" / name = \"live\" / at = [0, 0, 0]" >&2
}
