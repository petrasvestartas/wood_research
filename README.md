# wood_research

The timber-joinery stack as one superproject. Every repo below is a git submodule, pinned
to a commit this superproject knows the others build against, so a clone reproduces a
working stack rather than five checkouts that happen to be on the right day.

```
wood_research/
├── session_cpp/   the geometry kernel everything compiles against     (main)
├── wood/          C++ core: contact detection + joint solver          (dev)
├── wood_nano/     nanobind bindings over wood                         (dev)
├── compas_wood/   COMPAS-friendly wrapper over wood_nano              (dev)
├── compas_tf/     topology-finding, BRG-research         (assembly-steps)
└── bash/          pull.sh, push.sh, update_session.sh, publish_scene.sh
```

Dependency direction: `compas_wood` → `wood_nano` → `wood` → `session_cpp`.

`session_cpp` is one checkout shared by `wood` and `wood_nano`. Both CMake files look for
it as `../session_cpp`, so updating that one directory updates the kernel everywhere and
the two can never disagree about what an `Element` is.

## Clone

```bash
git clone --recurse-submodules https://github.com/petrasvestartas/wood_research.git
cd wood_research
bash/pull.sh          # puts every submodule on its branch, not a detached HEAD
```

## Day to day

```bash
bash/pull.sh                      # fast-forward every submodule to the tip of its branch
bash/update_session.sh            # rebuild wood + wood_nano against the current kernel
bash/push.sh -m "contact areas"   # commit + push wood → wood_nano → compas_wood, then this repo
```

`pull.sh` never moves a submodule with uncommitted changes; it reports it instead.
`push.sh` pushes in dependency order — `wood_nano` compiles `wood`, `compas_wood` runs on
`wood_nano`, and each one's CI builds the others from their *pushed* branches — and ends by
committing the moved submodule pointers here, without which the pushes are invisible to a
fresh clone. `compas_tf` and `session_cpp` are consumed, not authored here, so they are not
pushed; their pointers still move.

## Build by hand

```bash
cmake -S wood -B wood/build -DCMAKE_BUILD_TYPE=Release   # wood: compiles ../session_cpp
cmake --build wood/build --parallel 4
cd wood_nano && uv pip install --no-build-isolation -e . && cd ..   # compiles ../wood too
```

Both CMake files resolve the kernel the same way, first hit wins: `-DSESSION_CPP_LOCAL=<dir>`
(or the env var), then `../session_cpp` (this layout), then a fresh clone of
`github.com/petrasvestartas/session_cpp` `main` (CI and wheels).

`.vscode/c_cpp_properties.json` here points IntelliSense at `wood/build/compile_commands.json`,
so open `wood_research`, not `wood` — and configure once first, or includes will not resolve.

## What is in the repos

- **`wood`** — `WoodElement` (plate), `BlockElement`, `WoodJoint`, all composed over
  `session_cpp::Element`; contact detection in `src/joinery_solver/wood_face_to_face.h`
  (oriented boxes → BVH → SAT for candidate pairs, Clipper2 for the overlap areas).
  Worked example: `examples/main_face_to_face.cpp`. No Python.
- **`wood_nano`** — nanobind bindings, CPython 3.13 via `uv`.
- **`compas_wood`** — pure-Python COMPAS wrapper.

Each repo has its own `SETUP.md`.

## Seeing the geometry

```bash
bash/publish_scene.sh    # build, run, publish; prints one line when the viewer has been told
```

That is the whole loop. It builds `main_face_to_face`, runs it, publishes the
`wood/data/output/pb/live.pb` it wrote to the branch the viewer reads, and tells the open page
so it redraws in place — same canvas, same camera, no reload. Build and run output appears only
if something fails, so what you get back is one line:

```
pb/live.pb  3.7 MB  3368172  viewer notified in 6335 ms
```

`--no-build` republishes what is already on disk, `--target NAME` runs a different example, and
`--no-notify` skips the relay (open pages poll the push up within two minutes instead).

It pushes the file to [`session_viewer_data`](https://github.com/petrasvestartas/session/tree/session_viewer_data)
as the single fixed slot `pb/live.pb` — always the same path, so the manifest never needs an
edit — and then announces the new commit sha on a relay topic. Nothing is built or deployed:
https://petrasvestartas.github.io/session/ reads that branch directly.

The announcement is what makes it feel live. Anonymous browsers get 60 GitHub API calls an hour
per address, so a page that goes looking for changes can only afford to ask every couple of
minutes — that quota, not the network, is the whole delay. The machine that pushed already knows
the sha, so it says so, and every open page (holding an SSE connection since it loaded) goes
straight to that commit. Push ~1 s + relay ~0.1 s + fetch ~0.7 s. Polling stays underneath as the
fallback, so a page opened later, or a push made from anywhere else, still converges.

`main_face_to_face` takes an optional variant number (`main_face_to_face 3`) that tilts one plate,
which is what `--demo` uses to make consecutive publishes visibly different.
`PLAN_LIVE_VIEWER.md` is the plan for the rest.
