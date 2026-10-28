# Shared workspace

- Keep this workspace small. Default budgets are 20 GiB total and 8 GiB generated files. Check with `python -B bash/workspace_storage.py check` before and after a heavy stage.
- Run new builds and bulk capture jobs through `python -B <workspace>/bash/workspace_storage.py run -- COMMAND ARGS`. It preserves the command's working directory and monitors only its owned process tree. Use one shared build cache per toolchain; avoid per-checkpoint object, executable, WASM or dependency copies.
- Preserve source, datasets, tutorials, compact proofs and other agents' edits. Coordinate before removing caches, compacting Git, staging, committing or pushing. Never delete an active build or rewrite shared history during another agent's Git work.
- Read any current ownership notes in `docs/coordination/`, `.codex/geometry-coordination-20261028.md` and `.codex/storage-coordination-20261028.md` when present. Preserve other agents' Wood documentation, style and website structure.
- Native C++ geometry and CI fixes belong to the geometry agent. Serialize parent/submodule pointer commits with that agent. Historical floor failures require a fresh run before reporting current counts.
