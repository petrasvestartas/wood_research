# Gridshell v3 - brief for a cloud session

BUDGET IS STRICT: a one-off promotional credit, no top-up. Work economically: read only what you need, build only the
targets you need, never loop on retries, stop at the pull requests. On a blocker, write it in the PR and stop.

## Setup
- Repos: this superproject (`petrasvestartas/wood_research`), submodule `wood` (branch `dev`, template at `a286722`),
  submodule `session` with the kernel `session/session_cpp` (wood's CMake finds it at `../session/session_cpp`).
- `git submodule update --init wood session`, then `git -C session submodule update --init session_cpp session_proto`.
- Build Release with `cmake --build <dir> --parallel 4`, only the targets you need (`templates_gridshell`, any new example,
  `main_all_datasets` once at the end).
- Style: `.claude/agents/session-reviewer.md` sections 3-4 (no file headers, one-line docstrings, no one-line function
  bodies, `using namespace session_cpp;`, functions under ~60 lines, one input type per concept, no overload families).
  No colours in 3D models. wood has NO tests: proof lives in the examples and their printed checks (exit 1 on failure).

## Current state (wood `a286722`)
- `wood/src/templates/shells/lamella_gridshell.h`, `Gridshell::from_surface(const NurbsSurface&, int curves /*0 iso,
  1 asymptotic*/, int count_top, int count_bottom, const Lamella&)`; Lamella {height, thickness, gap, spacing, overrun,
  step}. Asymptotic directions from II(d,d)=0, RK4 in (u,v), seeded along a spine. Each lamella = two upright boards
  (height along the local surface normal, thickness along n x t) with a gap, as wood Beams (segmented swept MESH);
  studs = fitted hexagons (Columns) at the crossings.
- `wood/examples/templates_gridshell.cpp` prints: asymptotic 36 boards, 47/47 studs touch 4 boards, normal curvature
  9.1e-8 1/mm, unrolled deviation 0.004 mm; iso 313 mm; 576 contacts, overlap 0.

## Tasks, in order

### 1. Paper analysis (careful reasoning)
Read: Wang, Almaskin, Pottmann, "Computational design of asymptotic geodesic hybrid gridshells via propagation
algorithms", Computer-Aided Design 178 (2025) 103800, doi 10.1016/j.cad.2024.103800 (code github.com/wangbolun300/WebsViaPropagation);
https://www.geometrie.tuwien.ac.at/geom/ig/publications/asymgeogridshell/asymgeogridshell.pdf; the relevant parts of
Schling's dissertation https://mediatum.ub.tum.de/doc/1468896/document.pdf (lamellas, double boards with a gap,
hexagonal stud, AA and AG joints, minimal surfaces); github.com/oberbichler/Bowerbird (curve tracing).
Already known from the journal paper: normal slats along asymptotic curves and tangential slats along geodesics are
straight flat strips; webs of 3 families (AAG, AGG, GGG); discrete asymptotic curves satisfy n_i.(p_i - p_{i+-1}) = 0;
discrete geodesics n_i.b_i = 0; global objective E_c + l_fair E_fair + l_appro E_appro by Levenberg-Marquardt;
propagation from an initial strip with guide curves; asymptotic curves exist only where K < 0, the first curve must be
free of inflection points.
Write `docs/grid_instancing/gridshell_design.md` (under 250 lines): key ideas with equations, critique of the current
template, recommended algorithm for surfaces and for meshes, fabrication geometry, 3-5 main example scenes, minimal
API, kernel candidates.

### 2. BRep boards and NURBS lattices - smooth lofts, no little segments
petras: "you draw gridshells as meshes but they must be breps and lattices are nurbs", and "the lamellas must be
lofted curves, not these little segments".
- Lamella centre and edge curves are `NurbsCurve` (`NurbsCurve::create_interpolated` through the traced samples).
- Each board is ONE closed BRep solid whose faces are single smooth NURBS surfaces along the whole lamella, never one
  face or one mesh band per segment: the two side faces and the top and bottom faces are each ONE lofted/ruled
  surface through the full-length edge curves (`primitives.h`: `NurbsSurface::create_ruled` / `create_loft`), plus
  two planar end caps. Assemble with the BRep builder (`brep.h` `add_surface/add_vertex/add_edge/add_pcurve/add_wire/
  add_face/add_shell/add_solid`; see `BRep::create_box` for a closed solid), sharing edges and vertices.
- The edge curves come from the local frame at each sample: offsets +-b*(gap/2), +-b*(gap/2 + thickness) and +-n*h/2
  along the LOCAL surface normal n and binormal b = n x t, then interpolated as NurbsCurves.
- Studs are BRep prisms. The element carries the BRep (`element_geometry_brep()`); its tessellated mesh still feeds
  `compute_contacts` and the overlap check. Keep the printed numbers the same or better. The viewer must draw smooth
  boards (no ladder of section rings).

### 3. Minimal meshes (explore topologies)
petras: "for asymptotic use not only surfaces but also minimal meshes to really explore different topologies".
- Add `Gridshell::from_mesh(const Mesh&, ...)` next to `from_surface`.
- Build minimal meshes of different topologies: disk (4-sided saddle), annulus (catenoid between two rings), a third
  (helicoid, Enneper or Scherk) - boundary-fixed cotangent-Laplacian relaxation or parametric minimal surfaces.
- Asymptotic curves on the mesh (on minimal surfaces the two families are orthogonal): direction-field tracing across
  triangles, or the paper's discrete A-net propagation + optimization, whichever your analysis recommends. Same smooth
  BRep boards and studs.
- Print per scene: residual mean curvature, max normal curvature along the lamellas, unrolled straightness, stud
  contacts, max overlap.
- Generic geometry helpers stay in the template for now, listed as kernel candidates in the design doc.

### 4. Docs
Update `wood/docs/templates.md` (text and code; keep the image references, screenshots are taken locally later) and
the example table in `wood/README.md`.

### 5. Deliver
- PR on `petrasvestartas/wood` from branch `gridshell-v3` into `dev`; PR on `petrasvestartas/wood_research` from
  branch `gridshell-v3` with only `docs/grid_instancing/gridshell_design.md`.
- No AI / Co-Authored-By trailers in commit messages.
- PR body: what was done, every printed number per scene, the `main_all_datasets` `*.pb_coords.txt` / `*.pb_meta.txt`
  diff against dev `a286722` (must be identical), and what is left. Do not merge. Stop after the PRs.
