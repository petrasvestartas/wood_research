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
├── bash/          pull.sh, push.sh
└── update_session.sh
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

Without `--recurse-submodules` the five directories arrive empty; `bash/pull.sh` fills them.

## The two scripts

**`bash/pull.sh`** — check out and fast-forward every submodule to the tip of the branch
recorded for it in `.gitmodules` (`dev`, except `session_cpp` on `main` and `compas_tf` on
`assembly-steps`), including `session_cpp`'s own two submodules. `git submodule update`
alone leaves each one on a **detached HEAD**: right for reproducing a commit, wrong for
working in one, because a commit made there is on no branch and the next update loses it.
A submodule with uncommitted changes is fetched but never moved, and reported at the end.

**`bash/push.sh`** — push in dependency order: **wood → wood_nano → compas_wood**, then the
superproject. The order is not cosmetic: `wood_nano` compiles `wood`, `compas_wood` runs on
`wood_nano`, and each one's CI builds the others from their *pushed* branches, so a
`wood_nano` pushed ahead of the `wood` commit it needs is a red CI run against a `wood`
that does not exist yet.

```bash
bash/push.sh                      # push what is already committed; refuses if anything is dirty
bash/push.sh -m "contact areas"   # commit every tracked change in the three, then push
```

It ends by committing the moved submodule pointers in `wood_research` and pushing that too
— without which the pushes are invisible to a fresh clone, which would still check out the
old pins. `compas_tf` and `session_cpp` are not pushed (they are authored elsewhere), but
their pointers do move in that commit.

## Build

```bash
./update_session.sh              # pull session_cpp, rebuild wood + wood_nano, update session_py
./update_session.sh --no-build   # sources and Python packages only
```

Idempotent, one build at a time (4 jobs). It prints the `session_cpp` commit and the
`wood_nano` provenance stamp (`wood_nano.__wood_sha__`, `__session_sha__`) at the end, so
you can see exactly what was built.

By hand, from `wood_research/`:

```bash
cmake -S wood -B wood/build -DCMAKE_BUILD_TYPE=Release   # wood: compiles ../session_cpp
cmake --build wood/build --parallel 4
cd wood_nano && uv pip install --no-build-isolation -e . && cd ..   # compiles ../wood too
uv pip install -U session_py session_rhino --python compas_wood/.venv/bin/python
```

### How the kernel is found

`wood/CMakeLists.txt` and `wood_nano/CMakeLists.txt` resolve `session_cpp` the same way,
first hit wins:

1. `-DSESSION_CPP_LOCAL=<dir>`, or the `SESSION_CPP_LOCAL` environment variable
2. `../session_cpp` next to the repo — this layout, i.e. the submodule
3. a fresh clone of `github.com/petrasvestartas/session_cpp` `main` (CI and wheels)

`wood/cmake/ext/session_cpp` is a legacy submodule the build does not read.

### Editor

`.vscode/c_cpp_properties.json` at this root points IntelliSense at
`wood/build/compile_commands.json`. VS Code only reads `.vscode/` from the folder that is
open, so open `wood_research` (not `wood`) — or open `wood` and use its own copy. Either
way `wood/build` has to exist: configure once before expecting includes to resolve.

---

# Publishing geometry to the session viewer

`session_viewer` is the WebGPU viewer in the [`session`](https://github.com/petrasvestartas/session)
monorepo, deployed to **https://petrasvestartas.github.io/session/**. This is how geometry
computed here gets onto that page.

## 1. Write a Session with the geometry in it

`wood/examples/main_face_to_face.cpp`, scenario C, is the worked example. It writes a
`Session` holding **plain kernel geometry and nothing else** — the element outlines as
`Polyline`s and every detected contact polygon as a `Mesh`:

```cpp
Session session("face_to_face_viewer");

auto g_inputs = session.add_group("Inputs");
for (size_t i = 0; i < elements.size(); ++i)
    for (size_t f = 0; f < elements[i].polylines.size(); ++f) {
        auto pl = std::make_shared<Polyline>(elements[i].polylines[f]);
        pl->name = fmt::format("element_{}_face_{}", i, f);
        session.add_polyline(pl, g_inputs);
    }

auto g_contacts = session.add_group("Contacts");
for (const FaceContact& c : contacts) {
    auto mesh = std::make_shared<Mesh>(Mesh::from_polygon_with_holes({c.area.get_points()}, false));
    mesh->name = fmt::format("contact_{}_{}", c.element_a, c.element_b);
    mesh->set_objectcolor(Color(220, 80, 180, 255, "magenta"));
    session.add_mesh(mesh, g_contacts);
}

session.pb_dump(".../pb/face_to_face_viewer.pb");
```

Two things there are worth copying more than the geometry itself:

- **Serialize geometry, not solver types.** A `WoodElement` written with `to_element()`
  carries `element_type = "WoodElement"` and an `element_data` payload. The viewer draws it
  — it degrades to a plain `Element` — but nothing on the page reads that payload, so it is
  weight for no picture. Polylines and meshes are the whole contract.
- **Colour lives on the object, not the group.** The viewer paints each object from its own
  `linecolor` / `objectcolor`; a colour set only on the group leaves everything default.

Run it:

```bash
cmake --build wood/build --target main_face_to_face --parallel 4
wood/build/main_face_to_face
```

which writes, under `wood/data/output/`:

```
pb/face_to_face_viewer.pb          the geometry
scenes/face_to_face_viewer.toml    the manifest naming it
```

That `pb/` + `scenes/` pair **is** the viewer's own layout, so `wood/data/output` is already
a viewer root.

## 2. The scene manifest

A manifest says which files a scene is made of and where each one sits. The example writes
one item with no transform, so the geometry lands at its authored origin:

```toml
# wood face-to-face contact detection: plate outlines and the detected contact areas.
name = "wood - face to face contacts"

[[items]]
file = "pb/face_to_face_viewer.pb"
name = "plates + contact areas"
at = [0, 0, 0]
```

`Manifest::parse` tries JSON first and TOML second, so either extension works; the session
repo's own scenes are all `.toml`, because a scene is meant to be edited by hand and TOML
takes comments. Use `at = [x, y, z]` to place a file, `xform = [...16 numbers...]` when it
needs rotation or scale, and neither to get an auto-grid slot.

**You add a new `.toml`. You do not edit an existing one.** There is no scene index to
register in — a scene is selected entirely by the `?scene=` query string. The only file
that could be called "the main one" is the *default* the bare site URL loads, and that is
not a toml at all: it is `DEMO_SCENE_URL` in `session_viewer/src/lib.rs`. Change that only
if you want your scene to be what the site opens with, and note that it needs a viewer
rebuild, not a data push.

## 3. Publish to the `session_viewer_data` branch

The one hard constraint: the viewer fetches with `RequestMode::SameOrigin`
(`session_viewer/src/app/persistence.rs`), and `?scene=` is rejected if it is absolute,
contains `:` or `//`, or has a `..` segment (`scene_url()` in `src/lib.rs`). So the data
must be served **from the Pages origin itself**. Pointing the deployed viewer at
`raw.githubusercontent.com`, at another Pages site, or at a CDN loads nothing, with no
visible error. A data branch is therefore *storage*; CI is what folds it into the site.

**Create the branch** (orphan, so it carries none of the source history):

```bash
cd ~/brg/code_rust/session
git worktree add --orphan -b session_viewer_data ../session_viewer_data
cd ../session_viewer_data
mkdir -p pb scenes
cp ~/brg/code_cpp/wood_research/wood/data/output/pb/face_to_face_viewer.pb       pb/
cp ~/brg/code_cpp/wood_research/wood/data/output/scenes/face_to_face_viewer.toml scenes/
git add pb scenes
git commit -m "wood: face-to-face contact scene"
git push -u origin session_viewer_data
```

**Teach the deploy to overlay it.** In `.github/workflows/viewer-pages.yml`, between the
`Build` step and `upload-pages-artifact`:

```yaml
      - name: Scene data
        uses: actions/checkout@v4
        with: { ref: session_viewer_data, path: viewer-data }
      - name: Overlay onto dist
        run: |
          mkdir -p session_viewer/dist/pb session_viewer/dist/scenes
          cp -r viewer-data/pb/.     session_viewer/dist/pb/
          cp -r viewer-data/scenes/. session_viewer/dist/scenes/
```

Do **not** add `session_viewer_data` to that workflow's `branches:` trigger. Its first job
is `uses: ./.github/workflows/viewer-check.yml`, which resolves from the branch that fired
the run, and an orphan data branch has no `.github/`. Push data, then redeploy explicitly:

```bash
gh workflow run viewer-pages.yml --ref main
```

The scene is then live at

```
https://petrasvestartas.github.io/session/?scene=scenes/face_to_face_viewer.toml
```

**Shortcut for a one-off:** committing the same two files to `session_viewer/assets/pb/` and
`assets/scenes/` on `main` deploys them with no workflow change — `index.html` already
`copy-dir`s both into `dist`. The data branch exists to keep binary `.pb` churn out of the
source repo's history, which pays off as soon as there is more than one scene.

## 4. Check it before pushing

The browser is not the fastest way to find out that a `.pb` is wrong. The viewer's own
render harness draws a scene headlessly, through the same manifest parser and the same
kernel the page uses:

```bash
cd ~/brg/code_rust/session/session_viewer
cargo run --example selftest --target x86_64-unknown-linux-gnu --release -- \
    out.ppm ~/brg/code_cpp/wood_research/wood/data/output/scenes/face_to_face_viewer.toml
```

It prints object, draw and vertex counts and the share of non-background pixels, and writes
the frame. Zero non-background pixels means the scene is empty however healthy the file
looks. To check it in a real browser instead, copy the two files into
`session_viewer/assets/pb` and `assets/scenes`, `trunk serve`, and open
`http://localhost:8770/?scene=scenes/face_to_face_viewer.toml`.

---

## Element and ElementFeature

`wood` types are composed over the kernel's `session_cpp::Element` and `ElementFeature`
(`wood/src/joinery_solver/wood_element.h`):

| wood type | owns | written as |
|---|---|---|
| `WoodElement` (plate) | `session_cpp::Element element` | `Element` with `element_type = "WoodElement"`, loft mesh, `insertion_vectors`, `dimensions` (x/y extent, z thickness), face features, and the two outlines in `element_data` |
| `BlockElement` (loose closed loops) | `session_cpp::Element element` | `Element` with `element_type = "BlockElement"`, one mesh face per loop |
| `WoodJoint` | `std::array<ElementFeature, 2> element_features` | one `"joint"` feature on each of its two elements, outlines = that side's cut outlines |

Every type has `jsondump/jsonload`, `file_json_dump(s)/load(s)` and (elements) `pb_dumps/pb_loads`,
`pb_dump/pb_load`, plus `to_element()` / `from_element()` to move between the wood type and the
kernel one. Feature vocabulary on a plate: `joint_type_<code>` (a face's assigned joint type),
`cut` (merged outlines on a face with no assignment), `joint` (a detected joint, name = the
joint-library variant). A viewer without wood loads the plate as a plain `Element` and keeps
the payload on re-save.

`wood/examples/main_face_to_face.cpp` exercises all of it and exits non-zero on any failure;
`wood/examples/main_element_mapping_check.cpp` checks the field mapping both ways.

## Contact detection

`wood/src/joinery_solver/wood_face_to_face.h`: `adjacency_search` (oriented boxes in each
element's own frame → BVH → SAT) gives candidate element pairs; `faces_coplanar` +
`face_overlap_area` (Clipper2, int64 at 1e-6 mm) test each face pair; `face_contacts` wires the
two together for any element type. Works for plates (`WoodElement`) and for elements given as
a list of closed polylines (`BlockElement`).

## Next: live viewer

`PLAN_LIVE_VIEWER.md` is the plan for connecting the solvers to `session_viewer` so the browser
redraws in place after every run (no Pyodide). The publishing route above is the static half
of it.

## Environments as they stand

All three use **CPython 3.13**, supplied by `uv` (the system Python is 3.14; both Python repos
pin 3.13 in `.python-version`). Each repo has its own `SETUP.md`.

| Repo | Python? | Setup |
|---|---|---|
| [`compas_wood`](compas_wood/SETUP.md) | yes, pure Python | `uv venv && uv pip install -e ".[dev,docs]"` |
| [`wood_nano`](wood_nano/SETUP.md) | yes, compiles C++ | `uv venv && uv pip install nanobind scikit-build-core numpy pytest ninja cmake && uv pip install --no-build-isolation -e .` |
| [`wood`](wood/SETUP.md) | no | `cmake -B build && cmake --build build --parallel 4` |

Every `.venv/` self-ignores (uv writes a `.gitignore` containing `*` inside it), so the repos
report a clean `git status` after setup.
