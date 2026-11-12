# Viewer tutorial cloud handoff

Continue in `session/session_viewer`. Read root and session `CLAUDE.md`, the viewer `AGENTS.md`, `session/.claude/rules/viewer-docs.md`, and `docs/maintaining.md` first. Initialize the recorded submodules recursively; do not update them to remote heads. The local auxiliary checkouts `compas_wood` and `session/session_statics` are independent repositories, not untracked source to embed in this repository.

The goal is one cumulative course from an empty wgpu application to the current production viewer, using the fewest coherent subjects and lean code. Finish a subject's implementation once; apply this rule to existing content too. Archive unused tutorials. Explain the current design, with a visible goal, runnable checkpoint, prediction experiment and question. Keep changelogs to one to three concise bullets. Do not change viewer behavior.

Current work is incomplete. The active journey has 1,336 executable checkpoints. The first frame, first egui painting and command dock are active consolidated subjects, replacing 3, 3 and 22 checkpoints respectively. Their archived originals remain available. The dock's three focus corrections now belong to its owning subject; layers no longer rewrite that implementation. The latest ownership audit still fails with 4,961 later-subject rewrites across 305 files. Do not weaken this check or call the course finished.

`docs/lessons/03a-math` contains the complete production stage core, with a browser harness and an authored deck. Exact parity of 17 core modules, 24 native tests, wasm compilation and desktop/upright browser checks pass. The old equation-only screenshots are not its acceptance evidence; use `full-browser-evidence.json`. Cumulative integration is still pending. Production source changes in this checkpoint belong to the parallel viewer validation work; preserve them and do not attribute them to the tutorial rewrite.

The three consolidated foundation subjects have native scene-pixel and browser evidence. The dock also has four passing native focus/option-button regressions. All 24 course tooling tests and nine consolidation tests pass; strict docs builds pass. The structural check still fails on 20 production stage files missing from the historical inventory. The four reconstructed protobuf fixtures match across processes, but their browser interaction acceptance remains pending. These local checks do not establish current-viewer parity or full course completion.

Latest published submodule batch: [b2b922817](https://github.com/petrasvestartas/session/commit/b2b922817). Runtime GitHub API access works after the saved environment settings; no network-unblocking action is needed. Check that commit's CI before reporting it green.

Next work:

1. Integrate the validated full mathematics checkpoint early beside the first 2D painting. Teach the real-scene stage later, after its camera, object-row, stroke, arrow, marker and loading prerequisites.
2. Consolidate actual executable checkpoints, not just navigation headings. Keep the final endpoint equal to maintained production source; explicitly explain any deliberately untaught file in the coverage ledger.
3. Update the owning subjects for current row placement/reveal/non-pickability, strokes and trims, field-by-field arrow shader arguments and the Android probe technique, BRep display, matrices, decoding, hierarchy, rendering and self-tests. Verify kernel motion APIs in the docs site.
4. Run course checks and strict docs build. Record current failures honestly, obtain current browser evidence, then publish a batch and wait for CI. Do not cancel queued Pages workflows.

Use shared caches and the repository storage/build guards. No new local heavy builds are requested: continue calculation in the selected cloud environment. Public source and proofs belong in Git; build caches, credentials, personal settings and temporary recovery copies do not.
