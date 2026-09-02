# Plan: live session_viewer for compas_wood (what is left)

Trimmed 2026-09-02. The `wood` half of this plan shipped; two compas_wood items did not, and
they are what this file is now for. Latency work has moved to `PLAN_LIVE_LATENCY.md`.

Goal, unchanged: run the solver natively and have the browser redraw the result in place,
keeping the camera. No Pyodide - that was about running the solver INSIDE the browser, a
different goal (runnable docs cells) that stays optional.

## Done, so do not re-plan it

- **The viewer on `session@main` renders.** The old warning in this file, and the recipe for
  falling back to the `34h_colors_widths` snapshot, are withdrawn: the scene layer is wired
  (`add_file`, `src/app/scene.rs:191`), the query string is read, and `Manifest::parse_verbose`
  (`scene.rs:75`) takes TOML *and* JSON with line and column on errors.
- **The `live.html` iframe wrapper was never built and is not wanted.** Polling went inside the
  viewer instead (`src/app/live.rs`), together with a notification lane, so nothing needs to
  wrap it and post messages in. `bash/publish_scene.sh` builds, runs and publishes it.
- **wood writes a manifest**: `wood/data/output/scenes/live.toml` beside `pb/`.
- **The websocket idea** is no longer "later, only if needed" - it is step 3 of
  `PLAN_LIVE_LATENCY.md`, with the measurements that justify it and the message-size cap that
  picks its host.

## 1. compas_wood `live.py`

There is no `live.py` and no `invoke live`. Nothing on the compas_wood side starts a server or
opens a page, so the run -> look -> edit -> rerun loop only exists for `wood` today.

Write it against the CURRENT design, not the one this file used to describe. There is no iframe
and no HEAD polling to build: the deployed viewer already polls a manifest and the files it
lists, so all that is needed is a server it is allowed to read and a URL that points at it.

Three response headers are the whole reason this cannot be `python3 -m http.server`, and they
are the only hard-won part of the job:

- `Access-Control-Allow-Origin: *` - the viewer is served from another origin (github.io, or
  :8770 for a local trunk serve), so without it the browser drops the answer.
- `Access-Control-Allow-Private-Network: true` - Chrome's Private Network Access check
  preflights a public https page reaching anything on this machine, and refuses a server that
  does not opt in. `do_OPTIONS` has to answer that preflight (204, with
  `Access-Control-Allow-Methods` and `-Headers`).
- `Cache-Control: no-store` - a rerun that rewrites a `.pb` must not be hidden by a cache.

`bash/serve_scenes.py` did exactly this for `wood` and was deleted once the internet lane
(`publish_scene.sh`) became the one in use. It is 60 lines and worth reading before rewriting
this: `git show 98cc9eb -- bash/serve_scenes.py` (that copy still defaults `--scene` to the
old `scenes/face_to_face_viewer.toml`; the manifest is `scenes/live.toml` now).

So: serve the folder `publish(scene, name, root)` writes into, open
`<viewer>/?live=http://localhost:<port>/scenes/<name>.json`, and every following `publish` call
redraws the page. Document it in `compas_wood/SETUP.md`.

## 2. Refresh the committed viewer, and drop the patch

`compas_wood/docs/assets/viewer/` still holds the old patched snapshot, and
`session_viewer.patch` is still committed - in `docs/assets/viewer/` **and** in
`site/assets/viewer/`.

This is now worse than stale. That directory's `README.md` justifies the patch with two
upstream bugs, "`?scene=` is ignored" and "manifests are JSON only", and **both are fixed on
`session@main`** (see Done, above). Anyone reading it today is told to maintain a patch against
problems that no longer exist.

- Rebuild `session_viewer` (`trunk build --release`) and copy it in:
  `SESSION_VIEWER_DIST=<path-to-dist> invoke scenes`. `tools/build_scenes.py` handles the copy
  (`copy_viewer_app`, and `VIEWER_DIST` from that environment variable); without it the build
  deliberately reuses the committed app.
- Delete `session_viewer.patch` from both `docs/assets/viewer/` and `site/assets/viewer/`, and
  delete the recipe and the two-bug justification from that README.
- Keep `pb/` and `scenes/` uncommitted, as now - `invoke scenes` writes them on every docs
  build.
- Check the example pages still draw before committing: JSON manifests keep working, since
  `parse_verbose` reads both.

## Notes

- One process at a time when running solvers; see `wood/CLAUDE.md`.
- `wood` and `wood_nano` still show modified content in `git status` here. Review before
  committing anything in this superproject.
