# Plan: live session_viewer for wood / compas_wood (next session)

Goal: run the solver natively (compas_wood in Python, or wood in C++), and have the browser
redraw the result in place, keeping the camera. No Pyodide: that was about running the solver
INSIDE the browser, which is a different goal (runnable docs cells) and stays optional.

## What already exists (verified 2026-09-02)

- `~/brg/code_rust/session/session_viewer` is a static WASM app (Trunk). `dist/` was built
  today from the current `main` (7.5 MB wasm). It loads `index.html?scene=scenes/<name>.json`
  and fetches the manifest and the `.pb` files it lists, relative to the served folder. Any
  static HTTP server works; nothing else is fetched.
- `index.html` listens for `window.postMessage({type: "session-viewer:reload-scene", scene?})`
  and calls the wasm binding `reload_scene(url)` (`src/lib.rs`), which clears the documents
  and re-fetches the manifest WITHOUT restarting WebGPU or resetting the camera. This is the
  hook the whole plan hangs on. `Manifest::parse` (`src/app/scene.rs`) reads JSON first, TOML
  as fallback.
- compas_wood has the writer: `compas_wood.session_scene.publish(scene, name, root)` writes
  `root/pb/<name>.pb` + `root/scenes/<name>.json` in the viewer's layout;
  `tools/build_scenes.py` does it for every example.
- wood writes Session `.pb` files through `fill_session` (see `examples/main_face_to_face.cpp`,
  `main_all_datasets`) into `wood/data/output/`.
- Missing: (1) nothing tells the browser a file changed; (2) the viewer build committed in
  `compas_wood/docs/assets/viewer` is an OLD patched snapshot (`34h_colors_widths` + patch) and
  has NO reload hook; (3) wood writes no manifest.

## Steps

1. **Render check first.** Prove today's `session_viewer/dist` draws a wood `.pb`:
   `cd session_viewer && trunk serve` (or `python -m http.server` in `dist/`), open with a
   WebGPU browser (Linux Chrome needs
   `--ozone-platform=x11 --enable-features=Vulkan,DefaultANGLEVulkan,VulkanFromANGLE`; Firefox
   needs `dom.webgpu.enabled`), load a manifest pointing at
   `wood/data/output/face_to_face_scenario_a.pb`. Alternative without a browser:
   `cargo run --example selftest --target x86_64-unknown-linux-gnu --release -- out.ppm file.pb`.
   If `main` does not render, fall back to the recipe in `compas_wood/docs/assets/viewer/README.md`
   and add the reload hook to that snapshot's `index.html` (it is 10 lines of JS + `reload_scene`
   in `lib.rs`).

2. **`live.html` wrapper** (static, next to the viewer app): an iframe on
   `index.html?scene=scenes/<name>.json`; JS polls the manifest and each listed `.pb` with
   `HEAD` every 500 ms, compares `Last-Modified`/`ETag`/`Content-Length`, and on change posts
   `{type: "session-viewer:reload-scene"}` into the iframe. Query string `?scene=` passed
   through. Python's `http.server` sends `Last-Modified`, so no server code is needed.

3. **compas_wood `serve()`** (new module, e.g. `compas_wood/live.py`, plus `invoke live`):
   copy the viewer app (`index.html`, `.js`, `.wasm`, `live.html`) into a root folder
   (default `docs/assets/viewer` or a temp dir), start `http.server` on it in a thread, open
   `live.html?scene=scenes/<name>.json` in the browser, return the root so every following
   `publish(scene, name, root)` redraws the page. Example flow: run script -> view updates ->
   edit -> rerun. Document in `compas_wood/SETUP.md`.

4. **wood side:** write a one-item manifest next to each `.pb` (a `write_manifest(path)` helper
   beside `fill_session`, or a 5-line Python script) so `wood/data/output` can be served as the
   viewer root. Optionally `examples/main_face_to_face.cpp` writes `scenes/*.json` too.

5. **Refresh the committed viewer** in `compas_wood/docs/assets/viewer` from the verified
   `session_viewer/dist` (`SESSION_VIEWER_DIST=... invoke scenes`), delete `session_viewer.patch`
   and its recipe from that README, keep `pb/` and `scenes/` uncommitted as now.

6. Later, only if needed: a websocket dev server that pushes reloads (for Rhino or several
   machines writing into one page). HEAD polling is enough for one developer.

## Notes

- Everything from the previous session (Element/ElementFeature composition, Clipper2 contact
  detection, `update_session.sh`, `../session_cpp` symlink) is UNCOMMITTED in `wood`,
  `wood_nano` and this folder. Review and commit first: `git -C wood status`,
  `git -C wood_nano status`.
- One process at a time when running solvers; see `wood/CLAUDE.md`.
