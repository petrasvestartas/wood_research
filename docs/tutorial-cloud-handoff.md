# Viewer tutorial cloud handoff

Continue in `session/session_viewer`. Read root and session `CLAUDE.md`, the viewer `AGENTS.md`, `session/.claude/rules/viewer-docs.md`, and `docs/maintaining.md` first. Initialize the recorded submodules recursively; do not update them to remote heads. The local auxiliary checkouts `compas_wood` and `session/session_statics` are independent repositories, not untracked source to embed in this repository.

The goal is one cumulative course from an empty wgpu application to the current production viewer, using the fewest coherent subjects and lean code. Finish a subject's implementation once; apply this rule to existing content too. Archive unused tutorials. Explain the current design, with a visible goal, runnable checkpoint, prediction experiment and question. Keep changelogs to one to three concise bullets. Do not change viewer behavior.

Current work is incomplete. The active journey still has 1361 checkpoints. `first-frame.md` and `first-frame-subject.json` describe a proposed consolidation; it is not active in `course.json`. `subjects.ts` can collapse edits while preserving endpoint bytes, and `course -- subject-audit --all` audits candidates without rewriting the course. The ownership check still reports thousands of later-subject rewrites; do not weaken it to claim success.

`docs/lessons/03a-math` contains the complete production stage core, with a browser harness and an authored deck. The current full checkpoint still needs native tests, wasm build and browser validation. Its older equation-only screenshots do not validate the full checkpoint. Fifteen focused tooling tests pass, including exact stage-source parity and first-frame endpoint equality. Production source changes included in this checkpoint belong to the parallel viewer validation work; preserve them, and do not attribute them to the tutorial rewrite.

Next work:

1. Validate the full mathematics checkpoint, then integrate it early beside the first 2D painting. Teach the real-scene stage later, after its camera, object-row, stroke, arrow, marker and loading prerequisites.
2. Consolidate actual executable checkpoints, not just navigation headings. Keep the final endpoint equal to maintained production source; explicitly explain any deliberately untaught file in the coverage ledger.
3. Update the owning subjects for current row placement/reveal/non-pickability, strokes and trims, field-by-field arrow shader arguments and the Android probe technique, BRep display, matrices, decoding, hierarchy, rendering and self-tests. Verify kernel motion APIs in the docs site.
4. Run course checks and strict docs build. Record current failures honestly, obtain current browser evidence, then publish a batch and wait for CI. Do not cancel queued Pages workflows.

Use shared caches and the repository storage/build guards. No new local heavy builds are requested: continue calculation in the selected cloud environment. Public source and proofs belong in Git; build caches, credentials, personal settings and temporary recovery copies do not.
