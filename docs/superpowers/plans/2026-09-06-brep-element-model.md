# BRep Element Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store element geometry as a BRep and derive flat polylines from its planar faces for contact detection, so neither the viewer nor the detector sees mesh triangulation.

**Architecture:** `compas_tf.get_brep()` (compas_occt, coplanar faces merged) produces a BRep that is written into the `.pb` as the element's geometry. `session_cpp` gains `BRep::face_polylines()/face_planes()`, which emit one closed polyline per *planar* face from its outer wire; `Element::compute_polylines()/compute_planes()` route to it. `wood` is unchanged below `sync_faces()`. The viewer stops drawing triangulation ink and draws the BRep's real edges instead.

**Tech Stack:** C++20 (`session_cpp`, `wood`), Rust + wgpu 29.0 (`session_viewer`, `session_rust`), Python 3 (`compas_tf`, `session_py` 0.167.0, `compas_occt`).

**Spec:** `docs/superpowers/specs/2026-09-06-brep-as-element-model-design.md`

## Global Constraints

- **Non-planar faces are skipped for detection.** A cylinder contributes its two flat caps only. Never sample a curved wire into a "flat" polyline.
- **Holes are ignored for detection.** `wires[0]` only. Holes remain in the stored BRep.
- **The `Mesh` branch stays.** Existing `.pb` files must keep working; no behaviour change for `Mesh` or `monostate` geometry.
- **`face_polylines()` and `face_planes()` are index-aligned.** They share one private helper; wood relies on the alignment.
- **Repo paths:** `session_cpp` is at `session/session_cpp` (a submodule of the `session` submodule). Kernel edits are committed and pushed there, then the pointer moves.
- **Kernel tests:** `cmake --build build --parallel 4 && ./build/point_minitest`. All tests must pass (baseline: 750/750).
- **wgpu pin is 29.0** (`session_viewer/Cargo.toml:16`). Tasks 6–7 touch no wgpu API and no WGSL — if you find yourself editing a pipeline, bind group, shader, or host-shareable struct, stop: you have left the plan.
- **Producer venv is `wood/data/face_to_face_detection/.venv`** (session_py 0.167.0). The `wood_nano/.venv` copy is stale at 0.80.0 and lacks most of the BRep API — do not test against it.

---

### Task 1: `BRep::face_polylines()` / `face_planes()`

**Files:**
- Modify: `session/session_cpp/src/brep.h` (declare, after `vertex_points()` around line 192)
- Modify: `session/session_cpp/src/brep.cpp` (implement)
- Test: `session/session_cpp/src/brep_test.cpp`

**Interfaces:**
- Consumes: `NurbsSurface::is_planar(Plane*, double)`, `BRep::wire_edges(const BRepRef&)`, `BRep::face_orientation(int)`, members `m_faces`, `m_surfaces`, `m_edges`, `m_vertices`, `m_curves_3d`.
- Produces: `std::vector<Polyline> BRep::face_polylines() const` and `std::vector<Plane> BRep::face_planes() const`, index-aligned. Task 2 calls both.

- [ ] **Step 1: Write the failing tests**

Append to `session/session_cpp/src/brep_test.cpp`:

```cpp
MINI_TEST("BRep", "FacePolylinesBox") {
    BRep b = BRep::create_box(2.0, 2.0, 2.0);
    std::vector<Polyline> pls = b.face_polylines();
    std::vector<Plane> pls_planes = b.face_planes();
    MINI_CHECK(pls.size() == 6);                 // every face of a box is planar
    MINI_CHECK(pls_planes.size() == pls.size()); // index-aligned
    for (const Polyline& p : pls) {
        MINI_CHECK(p.point_count() == 5);        // closed quad
        MINI_CHECK(p.get_point(0) == p.get_point(4));
    }
}

MINI_TEST("BRep", "FacePolylinesCylinderCapsOnly") {
    // Two planar caps and one cylindrical barrel; the barrel must contribute nothing.
    BRep b = BRep::create_cylinder(1.0, 4.0);
    MINI_CHECK(b.face_count() == 3);
    MINI_CHECK(b.face_polylines().size() == 2);
    MINI_CHECK(b.face_planes().size() == 2);
}

MINI_TEST("BRep", "FacePolylinesIgnoresHoles") {
    // The holed face has an outer wire and an inner wire; only the outer one is emitted,
    // so the face still yields exactly ONE polyline.
    BRep b = BRep::create_block_with_hole(4.0, 4.0, 2.0, 1.0);
    std::vector<Polyline> pls = b.face_polylines();
    MINI_CHECK(!pls.empty());
    MINI_CHECK(pls.size() == b.face_planes().size());
    // No emitted polyline may be the hole circle: every point sits on the block bounds.
    for (const Polyline& p : pls) {
        for (size_t i = 0; i < p.point_count(); ++i) {
            const Point pt = p.get_point(i);
            const bool on_bounds = std::fabs(std::fabs(pt[0]) - 2.0) < 1e-6
                                || std::fabs(std::fabs(pt[1]) - 2.0) < 1e-6
                                || std::fabs(std::fabs(pt[2]) - 1.0) < 1e-6;
            MINI_CHECK(on_bounds);
        }
    }
}

MINI_TEST("BRep", "FacePolylinesNoPlanarFaces") {
    BRep b = BRep::create_sphere(1.0);           // one non-planar face
    MINI_CHECK(b.face_polylines().empty());
    MINI_CHECK(b.face_planes().empty());
}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd session/session_cpp && cmake --build build --parallel 4
```

Expected: compile error, `'face_polylines' is not a member of 'session_cpp::BRep'`.

- [ ] **Step 3: Declare in `brep.h`**

Insert after the `vertex_points()` declaration:

```cpp
    /// One closed Polyline per PLANAR face: the outer wire (wires[0]) walked in wire
    /// order, inner wires ignored. A face on a non-planar surface yields nothing -
    /// contact detection is flat-only, and a sampled cylinder ring would be a polyline
    /// that lies about being flat. Index-aligned with face_planes().
    std::vector<Polyline> face_polylines() const;

    /// The plane of each face face_polylines() emitted, in the same order. Taken from
    /// NurbsSurface::is_planar, so exact rather than a Newell estimate, and flipped when
    /// face_orientation() reports the face Reversed in its shell.
    std::vector<Plane> face_planes() const;

private:
    /// Both public accessors in one walk, so their index alignment is structural rather
    /// than a convention two functions must separately remember.
    std::pair<std::vector<Polyline>, std::vector<Plane>> planar_faces() const;
public:
```

- [ ] **Step 4: Implement in `brep.cpp`**

```cpp
namespace {
/// Samples per curved edge of a planar face. A planar face may carry an arc edge (a
/// rounded corner, a circular boss); its two vertices alone would cut the corner off.
constexpr int CURVED_EDGE_SAMPLES = 16;
}

std::pair<std::vector<Polyline>, std::vector<Plane>> BRep::planar_faces() const {
    std::vector<Polyline> polylines;
    std::vector<Plane> planes;

    for (int fi = 0; fi < (int)m_faces.size(); ++fi) {
        const BRepFace& face = m_faces[fi];
        if (face.surface_index < 0 || face.wires.empty()) { continue; }

        // One call decides the skip AND yields the plane, so the two outputs cannot drift.
        Plane plane;
        if (!m_surfaces[face.surface_index].is_planar(&plane)) { continue; }

        std::vector<Point> points;
        for (const BRepRef& er : wire_edges(face.wires[0])) {
            if (er.index < 0 || er.index >= (int)m_edges.size()) { continue; }
            const BRepEdge& edge = m_edges[er.index];
            if (edge.degenerated) { continue; }
            const bool reversed = (er.orientation == BRepOrientation::Reversed);

            const bool curved = edge.curve_3d_index >= 0
                             && m_curves_3d[edge.curve_3d_index].degree() > 1;
            if (curved) {
                const NurbsCurve& c = m_curves_3d[edge.curve_3d_index];
                const std::pair<double, double> d = c.domain();
                // Half-open: the next edge contributes this edge's end point.
                for (int s = 0; s < CURVED_EDGE_SAMPLES; ++s) {
                    const double u = (double)s / (double)CURVED_EDGE_SAMPLES;
                    const double t = reversed ? d.second + (d.first - d.second) * u
                                              : d.first + (d.second - d.first) * u;
                    points.push_back(c.point_at(t));
                }
            } else {
                const int start = reversed ? edge.end_vertex : edge.start_vertex;
                if (start >= 0 && start < (int)m_vertices.size()) {
                    points.push_back(m_vertices[start].point);
                }
            }
        }
        if (points.size() < 3) { continue; }
        points.push_back(points.front());   // closed, as Mesh::face_outlines() is

        // Point out of the solid, not along the surface's own parametrisation.
        if (face_orientation(fi) == BRepOrientation::Reversed) {
            Point origin = plane.origin();
            Vector normal = plane.z_axis();
            normal.reverse();
            plane = Plane::from_point_normal(origin, normal);
        }

        polylines.emplace_back(points);
        planes.push_back(plane);
    }
    return {polylines, planes};
}

std::vector<Polyline> BRep::face_polylines() const { return planar_faces().first; }
std::vector<Plane>    BRep::face_planes()    const { return planar_faces().second; }
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd session/session_cpp && cmake --build build --parallel 4 && ./build/point_minitest
```

Expected: PASS, and the total rises from 750 to 754+.

- [ ] **Step 6: Commit**

```bash
cd session/session_cpp
git add src/brep.h src/brep.cpp src/brep_test.cpp
git commit -m "brep: face_polylines/face_planes - planar faces as flat outlines"
```

---

### Task 2: `Element` routes to the BRep

**Files:**
- Modify: `session/session_cpp/src/element.cpp` (`compute_polylines`, `compute_planes`)
- Test: `session/session_cpp/src/element_test.cpp`

**Interfaces:**
- Consumes: `BRep::face_polylines()`, `BRep::face_planes()` from Task 1.
- Produces: `Element::polylines()` / `Element::planes()` non-empty for BRep geometry. Task 3 relies on this.

- [ ] **Step 1: Write the failing test**

Append to `session/session_cpp/src/element_test.cpp`:

```cpp
MINI_TEST("Element", "PolylinesFromBRep") {
    Element e(BRep::create_box(2.0, 2.0, 2.0), "brep_element");
    MINI_CHECK(e.polylines().size() == 6);
    MINI_CHECK(e.planes().size() == e.polylines().size());
    MINI_CHECK(e.polylines()[0].point_count() == 5);
}

MINI_TEST("Element", "PolylinesFromBRepSkipsCurvedFaces") {
    Element e(BRep::create_cylinder(1.0, 4.0), "cylinder_element");
    MINI_CHECK(e.polylines().size() == 2);      // caps only
    MINI_CHECK(e.planes().size() == 2);
}
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd session/session_cpp && cmake --build build --parallel 4 && ./build/point_minitest
```

Expected: FAIL — `polylines()` returns empty, because `compute_polylines()` only handles `Mesh`.

- [ ] **Step 3: Add the BRep branch**

In `element.cpp`, `compute_polylines()` becomes:

```cpp
std::vector<Polyline> Element::compute_polylines() const {
    if (const Mesh* mesh = std::get_if<Mesh>(&_geometry)) { return mesh->face_outlines(); }
    if (const BRep* brep = std::get_if<BRep>(&_geometry)) { return brep->face_polylines(); }
    return {};
}
```

and `compute_planes()` gains the matching branch as its FIRST statement, before the
existing mesh-derived loop:

```cpp
    if (const BRep* brep = std::get_if<BRep>(&_geometry)) { return brep->face_planes(); }
```

The BRep path does not go through the Newell loop: `is_planar` already gave an exact plane.

- [ ] **Step 4: Run to verify it passes**

```bash
cd session/session_cpp && cmake --build build --parallel 4 && ./build/point_minitest
```

Expected: PASS, all tests green.

- [ ] **Step 5: Commit and push the kernel**

```bash
cd session/session_cpp
git add src/element.cpp src/element_test.cpp
git commit -m "element: polylines/planes from a BRep's planar faces"
git push origin main
```

---

### Task 3: `wood` accepts BRep geometry

**Files:**
- Modify: `wood/src/joinery_solver/wood_element.cpp` (`BlockElement::from_element` ~line 315, `WoodColumn::from_element` ~line 358, `WoodColumn::mesh()`)

**Interfaces:**
- Consumes: `Element::polylines()/planes()` for BRep, from Task 2.
- Produces: `BlockElement`/`WoodColumn` with populated `polylines`/`planes` for BRep elements. Task 5 measures this.

- [ ] **Step 1: Point the superproject at the new kernel**

```bash
cd session/session_cpp && git pull --ff-only origin main && cd ../..
cmake -S wood -B wood/build -DCMAKE_BUILD_TYPE=Release -Wno-deprecated
cmake --build wood/build --target main_face_to_face --parallel 4
```

- [ ] **Step 2: Relax both geometry guards**

`sync_faces()` needs no change — it already only calls `element.polylines()/planes()`.
In `BlockElement::from_element`, replace the Mesh guard:

```cpp
    if (std::holds_alternative<std::monostate>(e.geometry())) {
        fprintf(stderr, "  WARNING: BlockElement::from_element: element '%s' carries no "
                        "geometry - block left empty.\n", e.name.c_str());
        fflush(stderr);
        return out;
    }
    out.sync_faces();
```

Make the identical substitution in `WoodColumn::from_element`, with `WoodColumn` and
"column" in the message. Both previously rejected anything that was not a `Mesh`, which
would silently empty every BRep element.

- [ ] **Step 3: Give `WoodColumn::mesh()` a BRep branch**

```cpp
Mesh WoodColumn::mesh() const {
    if (const Mesh* m = std::get_if<Mesh>(&element.geometry())) { return *m; }
    if (const BRep* b = std::get_if<BRep>(&element.geometry())) { return b->mesh(); }
    return Mesh{};
}
```

- [ ] **Step 4: Verify nothing regressed on mesh input**

```bash
cmake --build wood/build --target main_face_to_face --parallel 4
./wood/build/main_face_to_face floor_model
```

Expected: identical to the current baseline — `153 plates, 4 columns, 80 solids`,
`Contacts (3917)` with `unknown 3429`. The `.pb` is still meshes at this point, so
nothing should change yet. A different number here means Task 3 broke the Mesh path.

- [ ] **Step 5: Commit**

```bash
git -C wood add src/joinery_solver/wood_element.cpp
git -C wood commit -m "wood: accept BRep element geometry, not only Mesh"
```

---

### Task 4: `compas_tf` writes BReps

**Files:**
- Modify: `compas_tf/src/compas_tf/session.py` (add `_brep`, change `model_to_session`)

**Interfaces:**
- Consumes: `element.get_brep()` (OCCBrep), `session_py.BRep` builders.
- Produces: a `.pb` whose elements carry `BRep` geometry. Task 5 consumes it.

- [ ] **Step 1: Probe the surface/curve mapping**

This is the one call shape not verified while writing this plan — `session_py`'s NURBS
constructors must be matched to what `compas_occt` hands back. Run this first and read
its output before writing `_brep`:

```bash
cd /home/petras/code/code_cpp/wood_research
wood/data/face_to_face_detection/.venv/bin/python - <<'PY'
import inspect
import session_py as sp
from compas.geometry import Cylinder
from compas_occt.brep import OCCBrep

b = OCCBrep.from_cylinder(Cylinder(0.5, 2.0))
f = b.faces[0]
srf = f.nurbssurface
print("compas NurbsSurface attrs:", [n for n in dir(srf) if not n.startswith("_")])
for name in ("points", "weights", "knots_u", "knots_v", "mults_u", "mults_v",
             "degree_u", "degree_v", "is_rational"):
    print("  ", name, "=", repr(getattr(srf, name, "<absent>"))[:120])
print()
for ctor in ("create", "create_raw", "create_from_parameters", "create_planar"):
    fn = getattr(sp.NurbsSurface, ctor, None)
    print("sp.NurbsSurface." + ctor, ":", (fn.__doc__ or "<no doc>").strip()[:200])
print()
e = b.edges[0]
print("compas edge attrs:", [n for n in dir(e) if not n.startswith("_")])
for ctor in ("create", "create_raw", "create_from_parameters"):
    fn = getattr(sp.NurbsCurve, ctor, None)
    print("sp.NurbsCurve." + ctor, ":", (fn.__doc__ or "<no doc>").strip()[:200])
PY
```

Record the two constructor signatures in the task notes; Steps 2–3 use them.

- [ ] **Step 2: Write the failing round-trip test**

Create `compas_tf/tests/test_session_brep.py`:

```python
"""A model element must reach the .pb as a BRep, not a Mesh."""
import session_py as sp
from compas.geometry import Box
from compas_occt.brep import OCCBrep

from compas_tf.session import _brep


def test_brep_survives_pb_round_trip(tmp_path):
    occ = OCCBrep.from_box(Box(2.0, 2.0, 2.0))
    brep = _brep(sp, occ)

    assert brep.face_count() == 6
    assert brep.is_valid()

    session = sp.Session("t")
    session.add_element(sp.Element(brep, "box"))
    out = tmp_path / "rt.pb"
    session.pb_dump(str(out))

    back = sp.Session.pb_load(str(out)).objects.elements[0].geometry
    assert type(back).__name__ == "BRep"
    assert back.face_count() == 6
```

- [ ] **Step 3: Run to verify it fails**

```bash
cd compas_tf && ../wood/data/face_to_face_detection/.venv/bin/python -m pytest tests/test_session_brep.py -v
```

Expected: FAIL with `ImportError: cannot import name '_brep'`.

- [ ] **Step 4: Implement `_brep`**

Add to `compas_tf/src/compas_tf/session.py`, next to `_mesh`. Fill the two marked
constructor calls from the Step 1 probe output:

```python
def _brep(sp, occ_brep):
    """compas_occt OCCBrep -> session_py BRep, topology preserved.

    Both are the OCCT model (vertices, edges with pcurves, wires, faces, shells,
    solids), so this is a table-for-table transfer rather than a conversion. Index
    maps carry OCCT's identity into session's integer tables.
    """
    out = sp.BRep()
    vmap, emap, smap, cmap = {}, {}, {}, {}

    for i, v in enumerate(occ_brep.vertices):
        p = v.point
        vmap[i] = out.add_vertex(sp.Point(float(p[0]), float(p[1]), float(p[2])))

    for i, f in enumerate(occ_brep.faces):
        smap[i] = out.add_surface(_nurbssurface(sp, f.nurbssurface))   # from Step 1 probe

    for i, e in enumerate(occ_brep.edges):
        cmap[i] = out.add_curve_3d(_nurbscurve(sp, e.nurbscurve))      # from Step 1 probe
        emap[i] = out.add_edge(cmap[i],
                               vmap[occ_brep.vertices.index(e.vertices[0])],
                               vmap[occ_brep.vertices.index(e.vertices[-1])])

    for i, f in enumerate(occ_brep.faces):
        wires = [out.add_wire([emap[occ_brep.edges.index(e)] for e in loop.edges])
                 for loop in ([f.outerloop] + list(f.innerloops))]
        out.add_face(smap[i], wires)

    return out
```

- [ ] **Step 5: Run to verify it passes**

```bash
cd compas_tf && ../wood/data/face_to_face_detection/.venv/bin/python -m pytest tests/test_session_brep.py -v
```

Expected: PASS.

- [ ] **Step 6: Use it in `model_to_session`, with a fallback**

Replace `out = sp.Element(_mesh(sp, geometry), element.name)` with:

```python
        try:
            shape = _brep(sp, element.get_brep())
        except Exception as exc:                 # no compas_occt, or an unbuildable solid
            fell_back.append("{} ({})".format(element.name, type(exc).__name__))
            shape = _mesh(sp, geometry)
        out = sp.Element(shape, element.name)
```

Declare `fell_back = []` beside `demoted = []`, and report it beside the `demoted`
report so a degraded element is named rather than silently different:

```python
    if fell_back:
        print("  {} element(s) fell back to a mesh: {}".format(
            len(fell_back), ", ".join(sorted(set(fell_back)))))
```

- [ ] **Step 7: Commit**

```bash
git -C compas_tf add src/compas_tf/session.py tests/test_session_brep.py
git -C compas_tf commit -m "session: write elements as BReps, falling back to meshes"
```

---

### Task 5: Regenerate the model and measure

**Files:**
- Modify: `wood/data/floor_model.pb` (regenerated)

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: the acceptance measurement. Nothing consumes this; it is the gate.

- [ ] **Step 1: Record the baseline**

```bash
./wood/build/main_face_to_face floor_model | tee /tmp/f2f_before.txt
```

Expected, unchanged from today: `Contacts (3917)` with `unknown 3429`.

- [ ] **Step 2: Regenerate the model as BReps**

```bash
cd wood/data/face_to_face_detection && .venv/bin/python model_to_pb.py
```

Expected: the element/group summary prints, and any fallbacks are named. Investigate
before continuing if more than a handful fell back.

- [ ] **Step 3: Confirm the .pb actually carries BReps**

```bash
wood/data/face_to_face_detection/.venv/bin/python - <<'PY'
import collections
from session_py.session import Session
s = Session.pb_load("wood/data/floor_model.pb")
print(collections.Counter(type(e.geometry).__name__ for e in s.objects.elements))
PY
```

Expected: `Counter({'BRep': 237})`. A non-zero `Mesh` count is the Task 4 fallback firing.

- [ ] **Step 4: Measure — this is the acceptance gate**

```bash
./wood/build/main_face_to_face floor_model | tee /tmp/f2f_after.txt
diff /tmp/f2f_before.txt /tmp/f2f_after.txt
```

Expected: `unknown` collapses from 3429 and the classified counts
(`side_side`/`side_top`/`top_top`) dominate. If `unknown` is still the majority, STOP —
the BReps are reaching wood but their faces are not being read as planar. Do not
continue to Task 6; return to Task 1 and check `is_planar` tolerance against the model's
units.

- [ ] **Step 5: Commit the regenerated model**

```bash
git -C wood add data/floor_model.pb
git -C wood commit -m "data: floor_model as BReps, coplanar faces merged"
```

---

### Task 6: Viewer stops drawing triangulation ink

**Files:**
- Modify: `session/session_viewer/src/app/walk/brep.rs`

**Interfaces:**
- Consumes: `session_rust::Mesh::set_linecolors(Vec<Color>, Vec<f64>)`, `mesh_ink`'s `width 0 = hidden` rule.
- Produces: BReps drawn as fill only. Task 7 adds the edges back.

- [ ] **Step 1: Suppress the ink**

`mesh_ink.rs:37` documents `width 0 = hidden`, and `width_at` broadcasts a single entry
to every edge, so one zero hides the whole tessellation. In `walk_brep`:

```rust
pub fn walk_brep(arena: &mut ArenaRows, ink: &mut Ink, b: &BRep, cx: &WalkCx) -> Row {
    let mut bm = b.mesh();
    bm.set_objectcolor(b.surfacecolor.clone());
    // The tessellation is a fill, not a wireframe: its triangle edges are an artifact of
    // meshing, not features of the solid. Width 0 hides them (mesh_ink::hidden); the real
    // edges are drawn from the BRep's own curves below.
    bm.set_linecolors(vec![b.surfacecolor.clone()], vec![0.0]);
    walk_mesh(arena, ink, &bm, &MeshCx { cx, opts: &MeshOpts::MODEL })
}
```

- [ ] **Step 2: Verify it compiles and renders**

```bash
cd session/session_viewer && cargo check
cargo run --example selftest --target x86_64-unknown-linux-gnu --release -- /tmp/before.ppm assets/view_local.yaml
```

Expected: compiles; the printed ink count DROPS sharply versus the previous run (that
count is the evidence — a silent shader change would not move it).

- [ ] **Step 3: Commit**

```bash
git -C session/session_viewer add src/app/walk/brep.rs
git -C session/session_viewer commit -m "viewer: a BRep's tessellation is a fill, not a wireframe"
```

---

### Task 7: Viewer draws the BRep's real edges

**Files:**
- Modify: `session/session_viewer/src/app/walk/brep.rs`
- Modify: `session/session_viewer/src/app/walk/curves.rs` (widen `sample_nurbscurve` visibility if needed)

**Interfaces:**
- Consumes: `session_rust::BRep` public fields `m_edges`, `m_curves_3d`; `curves::sample_nurbscurve`; `SegRows`/`push_polyline`.
- Produces: BReps drawn with true edges. Terminal task.

- [ ] **Step 1: Draw one polyline per edge**

Iterating `b.m_edges` rather than face wires means an edge shared by two faces is drawn
ONCE. Add to `brep.rs`:

```rust
/// The solid's real edges: every non-degenerated edge sampled off its own 3D curve.
/// Iterating edges (not face wires) draws a shared edge once. A cylinder becomes two
/// exact circles plus its seam - no polygonised ring, because nothing is polygonised.
fn walk_brep_edges(seg: &mut SegRows, b: &BRep, row: u32, bounds: &mut Aabb) {
    let color = pack_rgba(b.surfacecolor.to_f32());
    let pen = Pen { row, radius: encode_width(b.width), color };
    for e in &b.m_edges {
        if e.degenerated || e.curve_3d_index < 0 { continue; }
        let pts: Vec<[f32; 3]> = sample_nurbscurve(&b.m_curves_3d[e.curve_3d_index as usize])
            .into_iter()
            .map(|p| p.map(|v| v as f32))
            .collect();
        if pts.len() < 2 { continue; }
        push_polyline(seg, &pts, &pen, bounds);
    }
}
```

Import what `curves.rs` already uses for `walk_nurbscurve` — `Pen`, `encode_width`,
`pack_rgba`, `push_polyline`, `Aabb`, `SegRows` — and make `sample_nurbscurve` reachable
(it is `pub(super)`, so `use super::curves::sample_nurbscurve;` works from `brep.rs`).

- [ ] **Step 2: Call it from `walk_brep`**

`walk_brep` must merge the fill's row with the edge bounds it just produced. Follow the
shape `walk_mesh` returns; extend the `Row`'s bounds with `bounds` before returning it
so framing still includes the edges.

- [ ] **Step 3: Verify**

```bash
cd session/session_viewer && cargo check && cargo xtest
cargo run --example selftest --target x86_64-unknown-linux-gnu --release -- /tmp/after.ppm assets/view_local.yaml
```

Expected: compiles, tests pass, ink count rises from Task 6's floor but stays far below
the original triangulated count. Compare `/tmp/before.ppm` and `/tmp/after.ppm`.

- [ ] **Step 4: Publish and look**

```bash
cd /home/petras/code/code_cpp/wood_research
./wood/build/main_face_to_face floor_model && bash/publish-scene.sh --no-build
```

Expected: columns and rib connectors draw as flat faces with clean outlines; cylinders
show circular caps, not polygons.

- [ ] **Step 5: Commit**

```bash
git -C session/session_viewer add src/app/walk/brep.rs src/app/walk/curves.rs
git -C session/session_viewer commit -m "viewer: draw a BRep's real edges instead of its tessellation"
```

---

## Wrap-up

- [ ] Push `session_cpp`, then move the `session` submodule pointer, then `wood` and `compas_tf` (see `bash/push.sh` for the dependency order).
- [ ] Record the before/after contact numbers in the spec's Testing section.
