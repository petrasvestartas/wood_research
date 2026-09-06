# BRep as the element model, flat polylines as the detection view

**Date:** 2026-09-06
**Status:** approved, not yet implemented
**Repos touched:** `session_cpp` (kernel), `wood` (consumer), `compas_tf` (producer)

## Problem

`floor_model.pb` stores every element as a triangulated `Mesh`. Measured face-vertex
histogram, identical in the COMPAS source model and in the `.pb`:

```
3 verts: 10820    4: 2804    5: 32    6: 8    8: 48    9: 8    12: 8
```

79% triangles. Nothing in the session pipeline triangulated this — `compas_tf`'s
`_mesh()` preserves n-gons faithfully; the COMPAS `modelgeometry` is already
triangulated. The triangulation then reaches two consumers at once, because
`Element::compute_polylines()` returns one closed polyline **per mesh face** and
`wood_session` uses that same vector for both drawing and detection:

- **Display** — `add_faces_impl` draws all 13,728 face outlines, so the viewer shows
  internal triangulation between columns and rib connectors.
- **Detection** — `contact_view` → `face_contacts` runs face-to-face on triangles.
  `main_face_to_face floor_model` reports **3917 contacts, 3429 of them `unknown`**
  (87%): each real planar face is shattered into fragments the classifier cannot type.

The affected classes are exactly the reported symptom: `ColumnElement` (4),
`OuterRibConnectorElement` (4), `ConnectorElement` (8), `ConnectorWedgeElement` (8),
`ConnectorCylinderElement` (32), `DowelCylinderElement` (32).

## Decision

Store a **BRep** as the element's geometry. Derive **flat polylines** from it for
contact detection. The BRep is the model at rest; the polylines are a derived view.

Every compas_tf element already has `get_brep()` (`BrepMixin`, `element.py:99`) —
"meshes to a solid Brep with coplanar faces merged, via compas_occt". That merge is
the un-triangulation.

Two decisions taken during design:

1. **Non-planar faces are skipped for detection.** A cylinder contributes its two flat
   caps and nothing for the barrel. Rejected: sampling the barrel into one polyline
   (produces a polyline that lies about being flat — the same class of wrongness as the
   triangles) and splitting it into N planar strips (adds a tuning knob that silently
   changes detection results). Accepted consequence: a dowel touching a plate through
   its barrel produces no contact.
2. **Holes are ignored for detection.** Only `wires[0]`, the outer boundary. Holes stay
   in the stored BRep; the contact pipeline has no hole concept and gaining one would
   mean changing `ContactElement` from "one polyline is one face" to a list of loops.
   Out of scope here.

## Prerequisites — all verified present

| Piece | Status |
|---|---|
| `ElementGeometry = std::variant<std::monostate, Mesh, BRep>` | `element.h:23` |
| `session_py` BRep binding, full kernel API | 0.167.0: `add_wire`, `add_pcurve`, `add_shell`, `add_solid`, `wire_edges`, `face_meshes`, `vertex_points` |
| BRep element round-trips through `.pb` | verified: returns as `BRep` |
| Viewer accepts BRep | `session_viewer/src/app/walk/brep.rs` — but by CPU tessellation, see below |
| `NurbsSurface::is_planar(Plane*, tol)` | tests planarity **and** writes the plane |
| `compas_occt` OCCBrep traversal | `vertices`, `edges`, `loops`, `faces`, `shells`, `solids`, `surfaces`, `curves`, `trims` |

Note: `session_py 0.80.0` in `wood_nano/.venv` is stale and lacks most of this. The
producer venv (`wood/data/face_to_face_detection/.venv`) has 0.167.0. Only the producer
venv matters for writing; `wood_nano`'s should be refreshed separately.

### The viewer does not benefit for free

`walk_brep` is 25 lines and calls `b.mesh()` — the welded **triangle** mesh of every
face — then hands it to `walk_mesh`. There is no BRep shader and no NURBS shader;
`walk_surface` does the same. The wireframe comes from `mesh_ink.rs` ("one pipe per
visible edge") of that triangle mesh, so the lines on screen are triangulation edges.

**Storing BReps therefore fixes detection but not display**: `b.mesh()` would
re-triangulate at render time and the same triangles would appear.

A GPU surface shader is not the fix. WebGPU has no tessellation shader stage, so the
options would be compute-shader tessellation or analytic ray-marching per surface type —
a large project that would not change what is wrong here. What is wrong is the *ink*.
Section 5 fixes that instead, reusing paths that already exist.

## Design

### Data flow

```
compas_tf element
  └─ get_brep()          OCCBrep, coplanar faces merged            [compas_occt]
     └─ _brep()          topological walk → session_py BRep        [compas_tf]
        └─ .pb           Element.geometry = BRep (replaces Mesh)
           ├─ viewer     walk/brep.rs, unchanged
           └─ wood       Element::compute_polylines()
                          └─ BRep::face_polylines()  planar faces, outer wire
                             └─ face_contacts()
```

The `Mesh` branch stays. Existing `.pb` files keep working unchanged.

### 1. session_cpp — `BRep::face_polylines()` / `face_planes()`

```cpp
/// One closed Polyline per PLANAR face: the outer wire (wires[0]) walked in wire
/// order, inner wires ignored. A face on a non-planar surface yields nothing —
/// contact detection is flat-only, and a sampled cylinder ring would be a polyline
/// that lies about being flat. Index-aligned with face_planes().
std::vector<Polyline> face_polylines() const;

/// The plane of each face face_polylines() emitted, in the same order. Taken from
/// NurbsSurface::is_planar, so it is exact rather than a Newell estimate, and
/// flipped when face_orientation() reports the face Reversed in its shell.
std::vector<Plane> face_planes() const;
```

Both delegate to one private helper that walks faces once and returns
`(polylines, planes)`. Index alignment is then structural, not a convention two
functions must both remember — `compute_polylines()` and `compute_planes()` callers
in wood already rely on it.

Per face:

1. `m_surfaces[face.surface_index].is_planar(&plane)` — false ⇒ skip the face entirely
   (contributes to neither vector). One call yields both the skip decision and the plane.
2. `wire_edges(face.wires[0])` — edges composed with the wire's own orientation.
3. Per edge, in orientation order: a degenerated edge is skipped; a degree-1 3D curve
   contributes its start vertex (exact); a higher-degree curve is sampled along
   `NurbsCurve::point_at()`. A planar face may legitimately carry an arc edge, so
   vertices alone are not sufficient in general.
4. Close the loop (first point repeated last), matching `Mesh::face_outlines()`.
5. Flip the plane normal when `face_orientation(fi)` is `Reversed`, so normals point
   out of the solid.

### 2. session_cpp — `Element`

`compute_polylines()` and `compute_planes()` gain a `BRep` branch:

```cpp
if (const BRep* brep = std::get_if<BRep>(&_geometry)) { return brep->face_polylines(); }
```

Behaviour for `Mesh` and `monostate` is unchanged.

### 3. wood — consumer

Smaller than it looks: `sync_faces()` already only calls `element.polylines()/planes()`.

- `BlockElement::from_element` and `WoodColumn::from_element` — relax the
  `std::holds_alternative<Mesh>` guard to "carries geometry". Today they warn and
  return an empty element for anything that is not a Mesh, which would silently drop
  every BRep element.
- `WoodColumn::mesh()` — add a `brep.mesh()` branch alongside the Mesh one.
- `add_faces_impl`, `contact_view`, `face_contacts` — unchanged.

### 4. session_viewer — true-edge wireframe

Two changes in `src/app/walk/brep.rs`, neither touching wgpu API or WGSL. Rows are built
CPU-side through the same `SegRows`/`push_polyline` path `walk_nurbscurve` already uses,
so there is no pipeline, bind group or host-shareable struct in scope. (wgpu pin: `29.0`,
`session_viewer/Cargo.toml:16`.)

- **Suppress triangulation ink.** `mesh_ink.rs:37` already documents `width 0 = hidden`,
  and `width_at` broadcasts a single entry to every edge. So the tessellated fill asks
  for no wireframe via `set_linecolors(vec![...], vec![0.0])`.
- **Draw the real edges.** Iterate `b.m_edges` — all fields on `session_rust::BRep` are
  public — and sample each `m_curves_3d[curve_3d_index]` through the existing
  `sample_nurbscurve()`. Iterating edges rather than face wires means a shared edge is
  drawn once, not twice.

A cylinder then draws as two exact circles plus its seam, and a planar face as its true
outline. No binding change is needed: `session_rust` is a full Rust port of the kernel,
not a thin binding, and already exposes `wire_edges()` and `face_orientation()`.

Note this means `face_polylines()` exists only in C++. The viewer does not need it — it
draws edges, not face loops — so the Rust port is deliberately NOT kept in step here.

### 5. compas_tf — producer

- New `_brep(sp, element)`: `element.get_brep()` → OCCBrep → walk vertices, 3D curves,
  2D pcurves, edges, wires, faces, shells, solids into the session_py builders.
- `model_to_session` calls `_brep()` where it now calls `_mesh()`.
- On failure (no `compas_occt`, or a solid `get_brep()` cannot produce) fall back to
  `_mesh()` and report the count, the way `demoted` is already reported. A bad solid
  degrades to today's behaviour instead of vanishing.

## Testing

**session_cpp minitests** (`brep_test.cpp`), using the existing primitives:

- `create_box()` → 6 polylines, each a closed quad (5 points); 6 planes, normals outward.
- `create_cylinder()` → 2 polylines (the caps only); the barrel is skipped.
- `create_block_with_hole()` → the holed face yields its outer wire only; the inner
  wire does not appear.
- A BRep with no planar faces (`create_sphere()`) → both vectors empty, not a crash.

**session_cpp** (`element_test.cpp`): a BRep-geometry `Element` yields non-empty
`polylines()`/`planes()` of equal length.

**wood**, the acceptance criterion:

`main_face_to_face floor_model` today prints **3917 contacts, 3429 `unknown` (87%)**.
After the change `unknown` must collapse and the classified counts
(`side_side`/`side_top`/`top_top`) must dominate. That number is the pass/fail — it is
the same measurement that exposed the problem.

Visual check: republish and confirm the columns and rib connectors draw as flat faces
rather than triangle meshes.

## Risks

- **Barrel contacts disappear.** Accepted by decision 1. If dowel-through-barrel
  contacts turn out to matter, revisit with planar strips — but measure first.
- **`get_brep()` cost.** 237 elements through compas_occt is a one-off offline
  conversion in `model_to_pb.py`, not a per-run cost. Not optimised here.
- **`.pb` size.** A BRep carries NURBS surfaces and pcurves; it may be larger or
  smaller than the triangulated mesh. Measured after implementation, not predicted.
- **Stale `session_py` in `wood_nano/.venv`** (0.80.0) is unrelated to this change but
  will confuse anyone testing from the wrong venv.

## Out of scope

- Holes in contact detection (`ContactElement` as a list of loops).
- Curved-face contact detection.
- Re-baking the COMPAS model itself so `modelgeometry` is not triangulated.
