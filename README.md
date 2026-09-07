# wood_research

The timber-joinery stack as one superproject. Every repo below is a submodule, pinned to a
commit this superproject knows the others build against.

```
wood_research/
├── session/       kernel monorepo; only session_cpp is checked out    (main)
├── wood/          C++ core: contact detection + joint solver           (dev)
├── wood_nano/     nanobind bindings over wood                          (dev)
├── compas_wood/   COMPAS wrapper over wood_nano                        (dev)
├── compas_tf/     topology-finding, BRG-research          (assembly-steps)
└── bash/          pull.sh, push.sh, publish-scene.sh
```

`compas_wood` → `wood_nano` → `wood` → `session_cpp`.

The kernel is not a submodule of its own. It arrives inside `session`, where it is authored,
so this repo can never hold a second copy that drifts; `wood/CMakeLists.txt` and
`wood_nano/CMakeLists.txt` both resolve `../session/session_cpp`.

## Clone

```bash
git clone https://github.com/petrasvestartas/wood_research.git
cd wood_research
bash/pull.sh
```

Plain `clone`, not `--recurse-submodules`: recursing drags in `session_rust`, `session_py` and
`session_data`, gigabytes this stack never compiles.

## Day to day

```bash
bash/pull.sh                      # wood_research, then wood → wood_nano → compas_wood, to each branch tip
bash/push.sh -m "contact areas"   # commit + push wood → wood_nano → compas_wood, then this repo
```

The order is not cosmetic: each repo's CI builds the other two from their *pushed* branches.
Neither script moves a repo with uncommitted changes, and `push.sh` ends by committing the
moved pointers here, without which the pushes are invisible to a fresh clone. `compas_tf` and
`session` are consumed, not authored here — pulled, never pushed. A kernel change is pushed
from a checkout of `session`, then picked up with `bash/pull.sh`.

## Build

```bash
cmake -S wood -B wood/build -DCMAKE_BUILD_TYPE=Release
cmake --build wood/build --parallel 4
cd wood_nano && uv pip install --no-build-isolation -e . && cd ..
```

Kernel resolution, first hit wins: `-DSESSION_CPP_LOCAL=<dir>` (or the env var),
`../session_cpp`, `../session/session_cpp`, then a clone of
`github.com/petrasvestartas/session_cpp`.

Open `wood_research` in the editor, not `wood`: `.vscode/c_cpp_properties.json` points
IntelliSense at `wood/build/compile_commands.json`. Configure once first.

## What is where

- **`wood`** — `WoodElement`, `BlockElement`, `WoodJoint` over `session_cpp::Element`; contact
  detection in `src/joinery_solver/wood_face_to_face.h`, example `examples/main_face_to_face.cpp`
- **`wood_nano`** — nanobind bindings, CPython 3.13 via `uv`
- **`compas_wood`** — pure-Python COMPAS wrapper

## Seeing the geometry

```bash
bash/publish-scene.sh    # build, run, upload, notify
```

Builds `main_face_to_face`, runs it, uploads the `wood/data/output/pb/live.pb` it wrote to the
R2 bucket `session-viewer-data` under the fixed key `pb/view_live.pb`, and pings a relay so
every open page re-reads in place — same canvas, same camera, no reload. Output is one line:

```
pb/view_live.pb  3.7 MB  3368172  viewer notified in 1526 ms
```

https://petrasvestartas.github.io/session/ reads that bucket directly; nothing is deployed.
**R2 keeps no versions** — a publish replaces bytes that are then gone.

`--no-build` republishes what is on disk, `--target NAME` runs another example, `--no-notify`
skips the relay (open pages poll within five seconds instead). Byte-identical content says
`unchanged - nothing published`.

Each repo has its own `SETUP.md`. `PLAN_LIVE_VIEWER.md` is the plan for the rest.
