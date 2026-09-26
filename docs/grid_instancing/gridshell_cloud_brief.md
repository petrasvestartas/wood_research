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
The journal paper is paywalled and must not be committed to this public repo; its content, summarised from a full
reading (2026-09-26), is below - use it instead of the PDF:
- Why straight flat strips: along an asymptotic curve the osculating plane is the tangent plane, so the curve's
  curvature vector lies in the tangent plane; a strip standing orthogonal to the surface (spanned by t and n) is then
  bent only about its weak axis and unrolls to a straight strip (its geodesic curvature in the strip = normal
  curvature of S = 0). Dually, a strip tangent to S along a geodesic unrolls straight. Asymptotic curves exist only
  where K < 0; minimal surfaces (H = 0) have orthogonal asymptotic families.
- Webs: triangular 3-webs sampled from iso-u, iso-v and iso-w (w = u + v) curves of x(u,v). Types: GGG, AGG, AAG
  (A = asymptotic, G = geodesic). AAG is the most constrained, GGG the most flexible. A 2-family AA web is a discrete
  A-net: a quad mesh whose vertex stars are planar.
- Discrete asymptotic curve (vertices p_i, auxiliary normals n_i): n_i.(p_i - p_{i+1}) = 0 and n_i.(p_{i-1} - p_i) = 0;
  E_a = sum (n_i.(p_i - p_{i+1}))^2 + (n_i.(p_{i-1} - p_i))^2. Normals are unit and tangent to the web:
  E_n = sum (|n_i|^2 - 1)^2 + (n_i.(p_{i+1} - p_{i-1}))^2 + (n_i.(p_{i+n} - p_{i-n}))^2 (both families through p_i).
- Discrete geodesic: surface normal lies in the discrete osculating plane, i.e. orthogonal to the binormal b_i:
  E_g = sum (n_i.b_i)^2, with E_b = sum (|b_i|^2 - 1)^2 + (b_i.(p_{i+1} - p_i))^2 + (b_i.(p_i - p_{i-1}))^2.
- Totals: E_aag = E_a^u + E_g^v + E_a^w + E_b^v + E_n (and analogues for AGG, GGG); fairness
  E_f = sum |2 p_i - p_{i-1} - p_{i+1}|^2 per family; approximation of the first strip E_appro = sum |p_i - p_i^ori|^2;
  E = E_c + l_fair E_fair + l_appro E_appro (+ l_guide E_guide), solved by Levenberg-Marquardt. Typical weights
  l_fair 1e-4, l_appro 1 (reduced as the web grows), l_guide 0.1; accuracy target ~1e-5.
- Propagation (their key contribution): start from an initial strip of two neighbouring curves V0, V1; add one new
  curve V_k at a time so the previous curve V_{k-1} satisfies its type, then run 10-20 global LM iterations; repeat.
  Their GGG/AGG/AAG propagation constructs the new vertices from discrete osculating / rectifying planes (for AAG: the
  new point lies on the intersection line of the tangent planes at p_i and p_{i-1}, then a block-coordinate update
  enforces (n'.u) = 0, (n'.w) = 0 and the geodesic det condition). Simple offsetting instead of this propagation
  gives highly non-smooth, self-intersecting webs.
- Initial strip: V0 an arbitrary fair polyline free of inflection points (an inflection forces a third asymptotic
  direction, only possible at flat points); first points placed so the strip triangles are equilateral and lie in
  the rectifying planes of V0. Guide curves steer the surface (a guide acts as a geodesic of the web; its binormals
  must lie nearly tangent to the surface, else it fails).
- Fabrication in their Fig. 1/2: gridshells extracted from the inner vertices of the web; normal lamellas on A curves,
  tangential lamellas on G curves.

Write `docs/grid_instancing/gridshell_design.md` (under 250 lines): key ideas with equations, critique of the current
template, recommended algorithm for surfaces and for meshes, fabrication geometry, 3-5 main example scenes, minimal
API, kernel candidates.

### 2. BRep boards and NURBS lattices - smooth lofts, no little segments
petras: "you draw gridshells as meshes but they must be breps and lattices are nurbs", and "the lamellas must be
lofted curves, not these little segments".
- Lamella centre and edge curves are `NurbsCurve` (`NurbsCurve::create_interpolated` through the traced samples).
- petras, precisely: "not lofted, but along the segments have interpolated curves, with kinks only at the 4 corners
  and the ends of the beams, to form the faces - when lofted they are faceted."
- So each board is built from FOUR RAILS: one smooth interpolated `NurbsCurve` per corner of the rectangular section,
  running the full length of the lamella. The rail points come from the local frame at every sample: corner = centre
  + b*(gap/2 or gap/2 + thickness) + n*(offset +- height/2), with n the LOCAL surface normal and b = n x t; then
  `NurbsCurve::create_interpolated` through them (degree 3, smooth along the length).
- Each of the 4 long faces is ONE ruled surface between two neighbouring rails (`NurbsSurface::create_ruled`), smooth
  along the length and straight across; the only kinks are the 4 corner rails and the 2 ends. Do NOT loft through a
  sequence of section rectangles (that faces the board into bands), and never one face or mesh band per segment.
- The 2 end caps are planar faces bounded by the rail end points. Assemble one closed BRep solid with the BRep builder
  (`brep.h` `add_surface/add_vertex/add_edge/add_pcurve/add_wire/add_face/add_shell/add_solid`; see `BRep::create_box`),
  the rails as the shared long edges.
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
