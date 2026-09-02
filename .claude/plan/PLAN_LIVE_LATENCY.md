# Plan: cut the live-viewer loop from 7.5 s to under 2 s (next session)

Goal: keep the viewer on the internet, not on localhost, and make the time from "go" to
geometry on screen short enough that it stops being a thing you wait for. The previous plan
(`PLAN_LIVE_VIEWER.md`) got the loop working; this one is about what it costs.

Everything below was measured on 2026-09-02, on this machine, against the deployed page. The
numbers are the whole argument: three of the four steps are only worth doing because of what
they measure, and one obvious-sounding idea (step 2) turns out to buy less than it looks.

## The loop today, leg by leg

| leg | measured | what it is |
| --- | --- | --- |
| `cmake --build` (incremental, nothing changed) | 0.50 s | negligible |
| run `main_face_to_face` | 0.14 s | negligible |
| `git push` to `session_viewer_data` | ~3.4 s | 1.6 s of bytes, ~1.8 s of git protocol |
| `curl` the sha to ntfy.sh | ~0.5 s | |
| page notices the message | <=0.5 s | `NOTIFY_TICK_MS` in `live.rs` |
| page downloads `live.pb` | ~2.4 s | 3.83 MB, uncompressed |
| **total** | **~7.5 s** | observed end to end: 6.3 s to "notified" |

Two measurements matter more than the rest.

**Upstream is 650 KB/s.** (1 MB POST to `speed.cloudflare.com/__up`: 650723 B/s.) This is a
floor under every option here. Whatever the transport, the compressed scene is 1.07 MB and
takes 1.6 s to leave this machine. Nothing in this plan beats that except step 4.

**GitHub will not compress the scene.** Asked exactly as a browser asks
(`Accept-Encoding: gzip, deflate, br`), `raw.githubusercontent.com` answers with no
`content-encoding`, `content-type: application/octet-stream`, and the full
`content-length: 3834753`. Meanwhile git compresses the same file to 1.05 MB to upload it. So
the download leg ships 3.6x more bytes than the upload leg does, and it is the single most
wasteful part of the loop. That asymmetry is what step 1 is for.

## What already exists (verified 2026-09-02)

- `bash/publish_scene.sh` is now the whole loop in one command: builds `main_face_to_face`,
  runs it, publishes `wood/data/output/pb/live.pb` as a parentless commit on
  `session_viewer_data`, and POSTs the sha to the ntfy relay. Build and run output is shown
  only on failure so stdout stays one line.
- That one line is fixed in shape - slot, size, commit, viewer status - because `/view`
  (`.claude/skills/view/SKILL.md`) now quotes it verbatim instead of composing a sentence.
- `session_viewer/src/app/live.rs` holds the notification lane: `DEFAULT_NOTIFY` (the ntfy SSE
  topic, paired with `NOTIFY_URL` in the script), `NOTIFY_TICK_MS = 500`,
  `API_MIN_GAP_MS = 120_000`, `DEFAULT_POLL_SECONDS = 5.0`.
- `session_viewer/src/app/persistence.rs:111`:
  `pub async fn session_from_bytes_chunked(url: &str, bytes: &[u8]) -> Session`. **The decoder
  already takes bytes, not a URL** - `url` is only sniffed for a `.json` suffix, and the real
  work is `proto::Session::decode(bytes)`. Every step below feeds this same function. No step
  in this plan changes the wire format, the schema, or anything in `wood`.
- The localhost lane is gone. `bash/serve_scenes.py` served `wood/data/output` for it and was
  deleted: nothing called it, and the goal is the internet lane. Recover it with
  `git show 98cc9eb -- bash/serve_scenes.py` if an offline fallback is ever wanted.

### The scene itself

`main_face_to_face` currently writes 4781 polylines and 2651 meshes (2651 face pairs in real
contact, out of 1472 broad-phase candidate pairs):

    raw     3,834,753 B   (3.66 MiB)
    gzip    1,072,578 B   (1.023 MiB)

Note that second number against a 1 MiB cap. It comes back in step 3.

### The relay is not reliable

During the 2026-09-02 session `ntfy.sh` went down for several minutes: both `159.203.148.75`
and `2604:a880:800:14:0:1:73c0:2000` refused connections, then recovered on their own. This is
not a footnote. **When the relay is down there is no notification, and `API_MIN_GAP_MS` means
an open page can be up to 120 s behind a push.** That, not the 7.5 s loop, is what "so slow"
has probably felt like in practice.

Two things already changed because of it: the failed POST no longer burns 5 idle seconds
(`--connect-timeout 1 -m 3`, was `-m 5`), and the failure is now shouted on the one line you
read rather than buried on stderr. Neither makes the relay reliable. Step 3 removes it.

## Steps

### 1. Gzip the payload (free, no infrastructure, biggest single win)

Publish `pb/live.pb.gz`; decompress in the viewer. The download leg goes from 3.83 MB to
1.07 MB, which at the measured 1.65 MB/s is **2.4 s -> ~0.65 s**. The push does not change
much: git was already sending a compressed pack, so the pack stays ~1.07 MB either way. The
win is entirely on the page side, and it is the cheapest 1.7 s in this document.

- Publisher: gzip into the slot in `bash/publish_scene.sh`. The slot name changes, so
  `session_viewer.toml` on `session_viewer_data` has to name the new path.
- Viewer: `DecompressionStream("gzip")` in the browser, or `flate2` in the wasm. Decide by
  suffix in `session_from_bytes_chunked`, next to the existing `.json` check - that function is
  already the right place, and it already branches on the name.
- **Sequencing: ship the viewer first.** See the warning below.

### 2. Replace git with a plain PUT (smaller win than it looks)

Upload to object storage (Cloudflare R2 free tier, or any presigned PUT) instead of pushing a
commit. This removes the ~1.8 s of git ref negotiation and pack work, and it removes the
`max-age=300` staleness on the raw CDN that `live.rs` currently works around by pinning URLs to
a commit sha. Expected total after steps 1+2: **~4.0 s**.

Worth being honest about the ceiling here: it saves 1.8 s and costs an account, a bucket, a
credential to keep out of the repo, and the loss of the parentless-commit trick that currently
makes republishing free forever. If step 3 is going to happen anyway, **step 2 is skippable** -
it is on this list as the fallback if step 3's server turns out not to be worth running.

### 3. WebSocket relay (the only step that removes the download)

The page holds a socket; the publisher pushes the bytes into it; the browser gets them as they
upload. The second leg does not get faster, it **stops existing**, and so do the relay POST and
the `NOTIFY_TICK_MS` wait. Expected total: **~2.3 s**, of which 1.65 s is the upstream floor.

Still the same `.pb` bytes. A binary frame goes straight into `session_from_bytes_chunked`.

Four things to settle before writing any of it:

- **Message size cap picks the host.** Cloudflare Durable Objects cap a WebSocket message at
  1 MiB (1,048,576 B). The gzipped scene is 1,072,578 B, about 24 KB *over*, and scenes only
  grow. So either chunk across frames (the decoder is already chunked internally) or host
  somewhere without that cap, such as fly.io. Do not start on Durable Objects assuming it fits.
- **A public relay is required, and cannot be avoided.** The page cannot open a socket to this
  laptop: no public IP behind NAT, and an `https://` page on github.io may not connect to a
  private address regardless (mixed content, plus Chrome's Private Network Access check, which
  refuses any local server that does not answer the preflight with
  `Access-Control-Allow-Private-Network`). Both sides dial out to a shared server.
- **Compression stays explicit.** `permessage-deflate` may give the 3.6x for free, but it is
  negotiated per connection and server-dependent. Gzip deliberately (step 1) rather than hope.
- **Decide what carries the placement.** `session_viewer.toml` names a file *and* its transform
  and can list several. A socket carrying one raw Session has nowhere to put that. Either send
  a small JSON header frame before the bytes, or accept that the WS lane is one scene at
  identity transform and keep the manifest for the GitHub path.

Keep the GitHub lane after this. It is the one that still works when the relay is down, and it
is what a link to someone else's browser resolves to.

### 4. Shrink the scene (multiplies every step above)

2651 contact meshes and 4781 polylines is what makes the file 3.8 MB. Earlier publishes in this
same viewer were 24 faces. This is the only step that lowers the 1.65 s upstream floor, because
it is the only one that sends fewer bytes rather than sending them faster.

Question to answer first, in `examples/main_face_to_face.cpp` and `fill_session`: do the contact
meshes need to be *on screen*, or are they intermediate results that got written because they
were in hand? If a scene of a few hundred KB is enough to see what you need to see, this step
is worth more than steps 1 through 3 combined, and it is pure deletion.

## Expected budget

| after | total | notes |
| --- | --- | --- |
| today | ~7.5 s | |
| step 1 | ~5.8 s | gzip; no new infrastructure, keeps GitHub |
| steps 1+2 | ~4.0 s | plain PUT; skippable if going straight to 3 |
| steps 1+3 | ~2.3 s | 1.65 s of it is the upstream floor |
| steps 1+3+4 | ~1.5 s | depends entirely on how much smaller the scene gets |

Recommended order if time is short: **1, then 4, then 3.** Steps 1 and 4 need no server, no
account and no credential, and together they land around 3 s.

## The one way to break this for everyone

Every step changes the format or the transport that a *deployed, already-open* page is reading.
A publisher that starts sending gzip, or sending frames, before the viewer that understands it
is deployed will blank or break every open page until each one reloads.

So for each step, in this order: **change the viewer, deploy it to Pages, confirm it still reads
the current format, and only then change the publisher.** Steps 1 and 3 both want the viewer to
accept old and new for one release - a suffix check for step 1, and for step 3 a page that
falls back to the GitHub lane when the socket is not there. `live.rs` already has that shape:
the notification is an accelerator and polling stays the source of truth.

## Notes

- Viewer work is in `~/brg/code_rust/session/session_viewer` (Rust/wasm, Trunk), a different
  superproject from this one. Its push script is `bash/git_push.sh` there, and it runs
  `minitest.sh --no-web` before it will push. Quote the commit message: it does `m="$1"`, so an
  unquoted message silently keeps only the first word.
- `session_cpp`'s nested `session_proto` pointer is 3 commits behind its own main, including
  the `[proto-breaking]` brep rewrite. It does **not** affect the build: CMake consumes the
  committed `session_cpp/generated/*.pb.cc`, no protoc runs, and those files are already
  regenerated from the newer proto. It is bookkeeping lag, not breakage. Do not "fix" it in the
  middle of this work.
- The measurements above are from one machine on one connection on one afternoon. Re-measure
  before concluding a step did not help.
