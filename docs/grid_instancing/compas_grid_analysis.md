# USER UPDATE — READ FIRST (supersedes the DESIGN section of your prompt)

The user asked that the grid data structure be GENERAL: usable for other kinds of grid structure, like the
FAST+EPP bay design tools (https://www.fastepp.com/concept-lab/apps/) applied to various grids — not a
one-off orthogonal column/beam/head generator. The orchestrator is writing the general design to:

    /tmp/claude-1000/-home-petras-code-code-cpp-wood-research/cd17883b-ad50-44cc-bbcd-c4f797944a70/scratchpad/grid_design.md

Before writing any grid code, read that file and follow it. If it does not exist yet, wait for it
(Bash: `sleep 120` with a 150000 ms timeout, re-check, up to 20 times). Its design replaces the DESIGN
bullet list in your prompt; the examples it names replace the examples in your prompt.

---

# compas_grid analysis: grid data structure for multistorey buildings

Repo root: `/tmp/claude-1000/-home-petras-code-code-cpp-wood-research/cd17883b-ad50-44cc-bbcd-c4f797944a70/scratchpad/compas_grid` (HEAD `d5f494a`, 0.6.7, 2025-03-12). Paths below are relative to that root.

**compas_model version (important).** compas_grid imports `compas_model.interactions.{Modifier, SlicerModifier, BooleanModifier}`. Those classes were removed in compas_model 0.8.0 (its CHANGELOG, "Removed `compas_model.interactions.modifiers`"). The only copies on disk are 0.9.3: `~/code/code_py/compas_tf/.venv`, `wood/data/face_to_face_detection/.venv`, `compas_cnc/.venv` and the uv cache. compas_wood's venv has no compas_model at all. compas_grid therefore does not import on any installed version; it targets compas_model **v0.7.0**, released 2025-03-12. I fetched the v0.7.0 sources with `curl` from raw.githubusercontent.com into `scratchpad/cm070/`: `slicer_modifier.py`, `boolean_modifier.py`, `modifier.py`, `models_model.py`, `elements_element.py`. Nothing was run. Every behaviour below comes from reading the code, and hand-derived geometry is marked as such.

---

## 1. Data model: lines → graph → CellNetwork with semantic attributes

`CellNetwork.from_lines_and_surfaces(column_and_beams: list[Line], floor_surfaces: list[Mesh], tolerance: int = 3)` (`src/compas_grid/models/gridmodel.py:43-126`). `GridModel.from_lines_and_surfaces` (`:230-257`) only wraps it and stores the result as `model.cell_network`.

**Step 1, a graph from lines plus the floor-mesh edges** (`:66-75`):
```python
for line in column_and_beams: lines_from_user_input.append(Line(line[0], line[1]))
for mesh in floor_surfaces:
    for line in mesh.to_lines(): lines_from_user_input.append(Line(line[0], line[1]))
graph: Graph = Graph.from_lines(lines_from_user_input, precision=tolerance)
```
- **Node dedup** happens in compas `Graph.from_lines` (compas 2.15 `datastructures/graph/graph.py`). Each endpoint gets the key `TOL.geometric_key(xyz, precision)`, which is the string of the coordinates rounded to `precision` decimals. Equal strings become one node, and node ids are `enumerate` order. `tolerance` is really a count of decimals: 3 means 0.001 units. It is not a distance, so two points 1e-9 apart on either side of a rounding boundary become two nodes.
- Lines are **not split** at T-junctions or intersections, and overlapping lines are not merged.
- **Implicit rule: every floor-face edge becomes a graph edge, and therefore a beam** (see step 3). A beam the user never drew still appears.

**Step 2, copy into a CellNetwork** (`:80-91`). Vertices are added in node order, so CellNetwork keys equal graph node ids by construction (an implicit assumption). A `gkey → vertex` map is built at `:87`.

**Step 3, the rules that assign semantics.** These are all the rules in the model:
```python
# :97-105  vertex attribute "neighbors" = horizontal neighbours only
for vertex in cell_network.vertices():
    z0 = graph.node_attributes(vertex, "xyz")[2]
    neighbor_beams = []
    for neighbor in graph.neighbors(vertex):
        if abs(z0 - graph.node_attributes(neighbor, "xyz")[2]) < 1 / max(1, tolerance):
            neighbor_beams.append(neighbor)
    cell_network.vertex_attribute(vertex, "neighbors", neighbor_beams)

# :112-118  edge rule: not horizontal -> column, horizontal -> beam
for u, v in graph.edges():
    if not abs(xyz_u[2] - xyz_v[2]) < 1 / max(1, tolerance):
        cell_network.edge_attribute((u, v), "is_column", True)
    else:
        cell_network.edge_attribute((u, v), "is_beam", True)

# :121-124  face rule: every input surface is a floor
for mesh in floor_surfaces:
    gkeys = mesh.vertex_gkey(precision=tolerance)
    v = [cell_network_vertex_keys[key] for key in gkeys.values() if key in cell_network_vertex_keys]
    cell_network.add_face(v, attr_dict={"is_floor": True})
```
- The horizontal threshold is `1/max(1, tolerance)`, which is 0.333 units when tolerance is 3. It mixes a decimal count with a distance: 0.33 mm when working in millimetres, 33 cm in metres.
- Any edge that is not horizontal, including a brace or a sloped member, becomes `is_column`.
- The face loop order is taken from **mesh vertex order, not the face cycle**. The Rhino exporter compensates by swapping vertices 2 and 3 (`data/crea/crea_rhino_to_compas.py:50-53`).
- `CellNetwork.add_face` also adds the face edges if they are missing (compas 2.15 `cell_network.py`, `add_face`).
- **Only floors are implemented.** The exporter writes the layers `Model::Mesh::Facade` and `Model::Mesh::Core` (`crea_rhino_to_compas.py:2`), but `from_lines_and_surfaces` has no parameter for them. The comment at `gridmodel.py:108` promises "is_facade, is_core" and nothing implements it. `gridmodel.py:292` notes that vertical wall faces would break the column-head face lookup.

**Rules outside the network that live in the GridModel methods:**
- `add_column_head(head, edge)` (`:259-302`): the head goes at the **higher-z end of a column edge** (`:274-277`). Nodes without a column below, such as the ground or a beam-only node, get no head.
- The head's adjacency comes from the `"neighbors"` attribute (beams) plus every face at the node carrying `is_floor` (`:286-292`).
- The model keeps element↔graph maps (`:181-184`): `column_head_to_vertex[v] = head`, `column_to_edge[edge] = column`, `beam_to_edge[edge] = beam` and `vertex_to_plates_and_faces[v] = [(plate, face_vertices)]`. The docstring (`:145-152`) has the direction of the first three backwards; they map key → element.
- The example scripts, not the model, use these maps to create interactions.

compas_model v0.7.0 `Model.__init__` already has `self._cellnet = None` (`cm070/models_model.py:120`), which shows the authors meant the network to live inside the model. GridModel keeps it in a separate `cell_network` attribute and leaves it out of `__data__` (`gridmodel.py:156-169`). The network and all the maps are lost on serialization.

---

## 2. Element-building pipeline

Every `add_*` method mutates the element it is given (sets transformation and length) and then calls `Model.add_element` with no parent.

| Kind | Code | Local geometry | Placement from the graph |
|---|---|---|---|
| Column | `elements/column.py:65-76`, `gridmodel.py:304-326` | Box with x = width, y = height, z = length, spanning z ∈ [0, length]. `Box.from_width_height_depth(width, length, height)` maps to xsize = w, ysize = h, zsize = L. | Axis runs from the lower to the higher endpoint and `length = axis.length`. The frame is `Frame(axis.start, [1,0,0], [0,1,0])`, **always world-vertical**, so a sloped "column" is drawn vertical from its lower end. |
| Beam | `elements/beam.py:77-88`, `gridmodel.py:328-352` | Same box: local z is the axis, local y is the height. | `length = edge length + 2*extend`. `orientation = Frame(axis.start, cross(dir, -Z), Z)` gives local x = horizontal normal, local y = world Z, local z = axis. The full transform is `orientation * T(0,0,-extend) * T(0, height/2, 0)`, so the **beam bottom sits on the line**. It fails for vertical edges because the cross product is zero. If a transformation already exists it composes `existing * orientation * ...` (`:347`). |
| Plate | `elements/plate.py:59-98`, `gridmodel.py:354-380` | The user-supplied polygon is extruded along `-normal * thickness`. The example's clockwise polygon has normal -Z, so the plate is extruded upward. | Only the **face centroid** is used: `Frame(centroid, X, Y) * T(0,0,thickness+offset)`. The face outline is ignored. The example passes a hard-coded ±2850 square (`002…py:55`): a 6000 bay inset by 150, which is the head half-width. When a transformation exists the order is `orientation * existing * ...` (`:370`), which does not match the beam. |
| Column head | `elements/column_head.py` | Described below. | `Frame(node point) world-XY * T(0,0,length)` (`gridmodel.py:297-298`). There is no rotation, so the grid must be world-aligned. |
| BeamProfile | `beam.py:255-552` | `_loft` (`:323-363`): each section point is projected along the axis onto the start and end planes, then capped by ear-clipping. Features (`:374-394`) are boolean-*intersected* with a loft of `feature.section` scaled 2× in z. `from_t_profile` (`:483-552`) builds an 8-point T or inverted-T section. | Used by the barrel examples with `add_beam(..., extend=150)`. |
| Block | `elements/block.py:258-395` | Any mesh (`from_box`, `from_polyhedron`, `from_mesh`). `BlockMesh.slice/split/trim` are `pass` stubs (`:239-246`). | Barrel voussoirs, translated to z = 3800. |
| Cable | `elements/cable.py` | A polygon section with 24 sides by default, extruded along z. `extend` works like the beam's. | Tie cables in `barrel/301`. |
| CutElement | `elements/cut.py:17-131` | **Not a cutter or modifier.** It is a generic element that wraps a given Mesh/Brep `shape` with bounding-box helpers and no modifier methods, and nothing in `src/` or `docs/` uses it. The real plane cut is compas_model's `SlicerModifier`, described below. | — |

### Column head (`column_head.py`, 713 lines; about 120 of them are the algorithm)

**Inputs.** `add_column_head` collects:
- `v = {v1: pt, n: pt …}`, the node plus its horizontal neighbours;
- `e = [[v1, n] …]`;
- `f` = vertex lists of the floor faces at `v1`.

The parameters (`:412-444`) are `width = w` and `height = h`, which are **half** sizes in x and y, `offset = o` (the arm projection), and `length = L` (the head height). Example values: 150 / 150 / 210 / 300.

**Step A: occupancy rules** (`_generate_rules`, `:144-202`). The rules are an 8-bool mask indexed by `CardinalDirections`: N=0, NW=1, W=2, SW=3, S=4, SE=5, E=6, NE=7, counter-clockwise from north (`:55-62`).
- For each edge, `closest_direction(p1-p0)` takes the argmax of the dot product with world ±X/±Y (`:645-681`). Only N, E, S and W are candidates, so a 45° edge ties and falls to dict order. `vector.unitize()` also mutates its argument. The result sets `rules[dir] = True` and records the direction for (u,v) and (v,u).
- For each face, the loop is walked and the directions of consecutive pairs that are known edges are collected. These are the two face edges at the node. There must be exactly 2, otherwise `ValueError`. Then `rules[get_direction_combination(d0, d1)] = True` via `{N,W}→NW, {W,S}→SW, {S,E}→SE, {N,E}→NE` (`:700-710`). An opposite pair, for example a node in the middle of a floor edge, raises `KeyError`.
- The rules become a tuple and serve as the cache key.

**Step B: the mesh** (`_generate_mesh`, `:204-326`), in a local frame with the top at z = 0 and the bottom at z = -L.
- 16 vertices:
  - outer ring 0-7 at z = -L, two per arm: N `0=(w,h+o)`, `1=(-w,h+o)`; W `2=(-w-o,h)`, `3=(-w-o,-h)`; S `4=(-w,-h-o)`, `5=(w,-h-o)`; E `6=(w+o,-h)`, `7=(w+o,h)`;
  - inner square 8-11 at z = -L: `(w,h), (-w,h), (-w,-h), (w,-h)`;
  - top square 12-15 with the same xy as 8-11 at z = 0.
- A sanity pass (`:251-254`) clears a corner whose two arms are not both set. It assigns into a **tuple** and would raise `TypeError`, but step A already guarantees the arms, so it never fires.
- Faces:
  - always the bottom inner square `[8,9,10,11]` and the top `[12,13,14,15]`;
  - each arm i∈{N,W,S,E}: a bottom rectangle, e.g. `[0,1,9,8]`, and a **sloped quad** from the outer bottom edge to the top-square edge, e.g. `[0,1,13,12]`, tagged `direction=i`;
  - each corner: a bottom triangle `[1,2,9]` and a **sloped triangle** `[1,2,13]` tagged with the diagonal;
  - each empty ring slot next to a filled one: a vertical closing triangle (`:298-314`), e.g. `[1,9,13]`;
  - each missing arm: a vertical core wall `[8+i, 8+(i+1)%4, +4, +4]` (`:317-323`);
  - then `remove_unused_vertices`.
- **Equivalent and much simpler (derived by hand, checked face by face against `:263-323`):** the head is a **loft from a bottom outline to the top square**. The bottom outline is the inner square plus one o×2w rectangle per beam arm plus one triangle per floor corner. Each bottom vertex maps to the nearest top corner; for example N-arm vertex 1, notch vertex 9 and W-arm vertex 2 all map to 13. Quads appear where two bottom vertices map to two top vertices, and triangles where they collapse to one.

**Step C: placement.** After `orientation * T(0,0,L)` the wide outline sits **at node z** and the narrow top at **node z + L**. The head is a truncated pyramid whose inclined arm faces seat the beams and whose inclined corner faces seat the plate corners.
- With the example sizes: head = beam = z ∈ [node, node+300], and the plate is z ∈ [node+300, node+500] because `thickness+offset = 200+100`.
- The line model is therefore the **underside of the beams**. Note that `wood/examples/1_elements_tree.cpp` uses the opposite head, a capital that is narrow at the column and wide on top, with the beams resting on top of it.

**Step D: modifiers**, dispatched by class-name reflection `_add_modifier_with_<basename>` (`:520-545`).
- `_with_column` (`:547-564`):
  - `p` = head origin in world, i.e. node + (0,0,L).
  - If the column's start is farther from `p` than its end, the column is the one below. It gets `frame0` from face 0 with the y-axis negated (`:559`) so the normal is -Z. This works around face 0 being wound CCW with normal +Z, which is inconsistent winding.
  - Otherwise the column is above and gets `frame1` from face 1 (normal +Z).
  - The variable name `column_head_is_closer_to_base` reads backwards.
- `_with_beam` (`:566-583`): find the beam end nearest `p`, compute `closest_direction(far - near)`, and pick the face tagged with that direction. The plane is `Frame(centroid, p1-p0, p2-p1)`. For E this gives normal ∝ (L, 0, o), pointing outward and up.
- `_with_plate` (`:585-613`): find the plate vertex closest to `p`, get the diagonal from its two neighbours, and take the face tagged with that diagonal, **falling back to face 5, which is arbitrary**. The plane is `polygon.frame`.
- `SlicerModifier.apply` (`cm070/slicer_modifier.py:35-58`):
  - Brep target: `make_solid()` then `trim(flipped plane)`.
  - Mesh target: `target.slice(plane)[0]`, i.e. keep the side the normal points to.
  - Any exception is printed and swallowed, returning the target unchanged. `__data__` references `self.source`, which does not exist.
- Results (hand-derived, not run):
  - The column below is cut exactly at its top face, so nothing changes.
  - The column above loses [node, node+L].
  - Beam ends get a sloped cut: the bottom edge stops w+o = 360 from the node and the top edge stops w = 150 from it. The beam overhangs and rests on the inclined arm face.
  - The plate corner at (w, h, z ≥ L) only touches the diagonal plane, so it is effectively not cut.

**Mesh slicing that `SlicerModifier` relies on** (compas `datastructures/mesh/slice.py`):
- It splits every edge crossed by the plane, but the "not an endpoint" test is an exact float `!=` (`:147`).
- Side classification uses `> 0.0` and `< 0.0` with no tolerance (`:105, :136`).
- It splits only faces that contain exactly 2 intersection vertices, silently skipping failures (`:162-169`).
- It caps with a single `vertices_on_boundary()` loop (`:94-95`).
- It returns `None` when there are fewer than 3 intersections.
- The authors' own failure case, `data/crea/error.py`, nudges the plane by 0.001 to get past a plane that passes through a vertex.

**Other modifiers:**
- `BooleanModifier` (`cm070/boolean_modifier.py:92-132`): mesh boolean difference, then Mesh→Brep→`simplify`→Mesh to merge coplanar faces.
- Users: `ColumnElement._add_modifier_with_beam` (`column.py:204-206`), `BeamElement._add_modifier_with_beam` and `_with_block` (the latter only when `block.is_support`, `beam.py:212-223`), and `CableElement._add_modifier_with_beam`.
- `BeamElement._create_slicer_modifier` (`beam.py:225-252`), which ray-casts the target's centre line against the source's faces, is dead code.

---

## 3. Contacts, interactions, tree

- **Element tree:** flat. Every `add_element` call has no parent (`gridmodel.py:299, 324, 349, 372`), so there are no storey or type groups. Type partitioning walks the class hierarchy (`:186-196`), and the `columns`, `beams`, `floors` and `columnheads` properties test an undefined `self.reset_partitions` (`:200-218`), which raises `AttributeError`.
- **Interaction graph (compas_model v0.7.0):**
  - one node per element;
  - `add_interaction(a, b)` adds the edge a→b and marks b dirty (`models_model.py:363-398`);
  - `add_modifier(a, b)` calls `a.add_modifier(b)` and stores the result in the edge attribute `"modifiers"` (`:400-436`). A **second** modifier on the same edge hits a bug: it calls `edge_attribute((a,b), modifier).append(...)` with the modifier object as the attribute name (`:434`).
  - `Element.compute_modelgeometry` transforms `elementgeometry` and applies the modifiers of every in-neighbour in sequence (`elements_element.py`, `compute_modelgeometry`). It is lazy, cached, and reset through `is_dirty`.
- **How the grid wires interactions** (`docs/examples/gridmodel/003_gridmodel_add_interfaces.py:62-77`), in the example and not in the model:
  - for every column edge and both endpoints, if a head exists: head→column;
  - for every beam edge and both endpoints, if a head exists: head→beam;
  - for every vertex with plates: head→`plates_and_faces[0][0]` only, so **only the first plate at a node is cut**.
- **Contacts:** the grid examples never call `compute_contacts`. The barrel examples do (`303:11`, `306:45`, `309:42`, with `tolerance=1, minimum_area=1, k=6 or 8`). In v0.7.0 it uses a BVH or KDTree for neighbour candidates, then `mesh_mesh_contacts` (coplanar face overlap), and stores the result as the edge attribute `"contacts"` (`models_model.py:631-677`).
- **A likely crash (by reading):** `ColumnHeadCrossElement.compute_aabb` and `compute_obb` do `box.xsize += inflate` without checking for `None` (`column_head.py:480-482, 500-502`). The v0.7.0 `aabb` property calls `compute_aabb()` with no arguments, so `.aabb`, `compute_point` and any BVH contact search on a model with heads would raise `TypeError`. `PlateElement.compute_aabb` reads `self.modelgeometry.aabb` without calling it (`plate.py:117`).

---

## 4. Example inputs (what defines the grid)

All of it is axis-aligned, in mm, with Z up.

| File | Keys | Grid |
|---|---|---|
| `data/frame.json` (written by `barrel/300_input.py`) | `lines`, `meshes` | One 6000×6000 bay (±3000), one storey of 3800. 4 vertical lines plus 4 beams at z = 3800, and 1 floor quad at z = 3800. **The gridmodel examples 001-006 read keys `Model::Line::Segments` / `Model::Mesh::Floor`, which the committed file lacks** (`000_frame.py` writes those keys to the same path), so they would raise `KeyError`. |
| `data/crea/crea_4x4.json` (same counts as `data/crea_4x4.json`) | `Model::Line::Segments` (36), `Model::Mesh::Floor` (6), `Facade` (8), `Core` (4) | x {0, 6000, 12000}, y {24000, 30000, 36000}, z {0, 3800, 7600}: 2 storeys of 3.8 m and an **L-shaped plan**. Node (12000, 24000) and bay [6000-12000]×[24000-30000] are absent. 8 column positions × 2 storeys = 16 columns. 10 beams per level at z = 3800 and 7600, none at z = 0. 3 floor bays per level. Facade walls on x = 0 and y = 36000 only. Core walls on y = 30000 (x 6000-12000) and x = 6000 (y 24000-30000), which are the edges between the void bay and the plan. Walls are one quad per bay per storey. |
| `crea_4x4_ground.json` | same | Adds 3 floors at z = 0 but no beams, so the z = 0 beams come only from the implicit floor-edge rule. |
| `crea_4x4_beams_without_column.json` | same | 4 bays per level at 3800 and 7600 plus 3 at z = 0 (11 floors), an extra ground column at (12000, 24000) from 0 to 3800, and the same 20 drawn beams. The file name suggests it tests beams that exist only through floor edges; I am inferring that. |
| `data/crea/crea.json` (full building) | `Line::Column` 340, `Line::Beam` 549 (259 along x, 290 along y), `Mesh::Floor` 248 quads, `Mesh::Facade` 176, `Mesh::Core` 80 | x 0…24000 step 6000 (5 nodes), y 0…36000 step 6000 (7 nodes), z 0…38000 step 3800 (11 levels, 10 storeys). |
| Barrel (`barrel/200`, `302`, `307-309`) | `meshes`, `frames` | `from_barrel_vault(span=6000, length=6000, thickness=250, rise=600, vou_span=5, vou_length=5)`: a circular segment with radius `rise/2 + span²/(8·rise)`, voussoirs made by rotating the intrados/extrados pair around the centre, a running bond with half-blocks, and `is_support` set on the first and last course. Blocks are raised to z = 3800 between two T-beams (`from_t_profile` width 300, height 700, step 75×150, extend 150) on beam edges 0 and 3. The beams boolean-cut the support blocks. |

Element sizes used by the grid examples:
- head w = h = 150, o = 210, L = 300;
- column 300×300;
- beam 300×300;
- plate 200 thick, inset 150 per side, offset 100.

**A parametric generator** that reproduces all of these datasets:
- inputs: `nx, ny` nodes, spacing `sx, sy`, `storey_heights`, a mask of inactive cells, and optional wall tags per cell edge and storey;
- a node exists when any incident cell is active;
- a column is placed per storey at each existing node;
- a beam is placed on each cell edge at levels ≥ 1 that borders an active cell;
- a floor is placed on each active cell at levels ≥ 1, with an optional flag for ground floors;
- walls come from tags. The data does not wall the whole boundary (y = 24000 and x = 12000 have none), so "boundary → facade" can only be a default rule, not a replacement for tags.

Example: `crea_4x4` = 3×3 nodes, 6000 spacing, storeys {3800, 3800}, inactive cell (1,0). `crea.json` = 5×7 nodes, 10 × 3800.

---

## 5. What is bad, and a clean C++ design

**Main defects** (besides the ones already cited above):
1. The tolerance is a decimal count used as a distance, and dedup is by string rounding. There is no line splitting or overlap merge.
2. Face loops come from vertex order.
3. Floor edges silently become beams.
4. Anything non-horizontal is a column, and sloped members are forced vertical (`gridmodel.py:320`).
5. Walls are exported but ignored.
6. Directions snap to world axes, so rotated or non-orthogonal grids fail. Opposite-direction face edges raise `KeyError`.
7. The `CrossBlockShape` singleton means the first instance's `w/h/L/o` win for every head, and the cache is keyed only on the rules (`column_head.py:115-142`), so two head sizes cannot coexist in one model.
8. The plate ignores the face outline.
9. Transform composition order differs between beam and plate.
10. Element-type dispatch is string reflection. The `type` parameter shadows the builtin, so the error path `type(target_element)` itself raises `TypeError` (`column_head.py:543`, `cable.py`).
11. Mutable default arguments (`column_head.py:414-427`) and a no-op statement `column_head.length` (`gridmodel.py:296`).
12. Examples are broken against the code:
    - `barrel/301, 307-309` call `BeamProfileElement(width=…, step_width_left=…)`, but the constructor is `(polygon, length, …)`; they should call `from_t_profile`.
    - `beam_raw.py` and `beam_model/001-002` import a non-existent `BeamProfileFeature`.
    - `BeamShapeElement.length` uses a non-existent `self.points` (`beam.py:654`).
13. The mesh slice is fragile, as described in section 2.
14. Nothing grid-related serializes.

**What the kernel has today** (read-only grep):
- `session_cpp/src/graph.h`: string-keyed `Vertex` and `Edge`, each with **one `std::string attribute`**, no coordinates, and no `from_lines` or `*_where`.
- **No Mesh or BRep plane split/trim**: nothing in `mesh.h` or `brep.h` besides `BRep::face_planes` (`brep.h:184`).
- `Polyline::cut_by_plane` (`polyline.h:198`) and `Polyline::trim_rectangles_by_plane` (`:319`).
- `Mesh::from_polylines(polys, precision)` (`mesh.h:426`), `Mesh::loft` (`:439`) and `BRep::from_polylines(polylines, holes)` (`brep.h:129`).
- wood elements: `Column(Line axis, Polyline section)`, `Beam(Polyline axis, double radius)`, `Plate::from_rectangle(...)` / `Plate(bottom, top)`, and `Block(std::vector<Polyline> loops)` (`wood/src/joinery_solver/wood_elements/*.h`).
- Existing templates are header-only files in `wood/src/templates/*.h`, e.g. `chevron.h`.
- `wood/examples/1_elements_tree.cpp` hand-builds bays out of Column + Block head (capital) + Beam + Plate. A grid template would replace that.

**Proposed `wood/src/templates/grid.h`.** Plain int-indexed arrays, rules as small free functions, and elements computed directly with no general booleans:
```cpp
enum class EdgeKind { beam, column, brace };
enum class FaceKind { floor, wall };

struct Grid {
    std::vector<Point> nodes;
    std::vector<std::array<int, 2>> edges;      // column edges stored lower node first
    std::vector<EdgeKind> edge_kind;
    std::vector<std::vector<int>> faces;        // node loops in cycle order
    std::vector<FaceKind> face_kind;
    std::vector<std::string> face_tag;          // "floor" "facade" "core" from layer or rule
    std::vector<double> levels;                 // sorted unique z, clustered within tolerance
    std::vector<int> node_level;
    std::vector<std::vector<int>> node_edges;   // incidence, built once
    std::vector<std::vector<int>> node_faces;
    Plane frame;                                // grid axes for arm directions (rotated grids ok)
};

Grid grid_from_lines(const std::vector<Line>& lines, const std::vector<Polyline>& floors, const std::vector<Polyline>& walls, const std::vector<std::string>& wall_tags, double tolerance);
Grid grid_regular(int nx, int ny, double sx, double sy, const std::vector<double>& storey_heights, const std::vector<std::array<int, 2>>& inactive_cells);

EdgeKind classify_edge(const Point& a, const Point& b, double tolerance);   // |dz|<=tol beam, parallel to Z column, else brace
FaceKind classify_face(const Polyline& loop, double tolerance);             // normal parallel to Z floor, perpendicular to Z wall
int arm_of(const Grid& grid, int node, int edge);                           // 0..3 in grid.frame; -1 if not horizontal
std::uint8_t node_arms(const Grid& grid, int node);                         // 4-bit beam directions
std::uint8_t node_corners(const Grid& grid, int node);                      // 4-bit floor quadrants (corner requires both arms)
bool has_head(const Grid& grid, int node);                                  // a column ends here from below

struct GridSizes { double column = 300; double head_half = 150; double head_offset = 210; double head_length = 300; double beam_width = 300; double beam_height = 300; double plate_thickness = 200; double beam_extend = 0; };
void grid_elements(const Grid& grid, const GridSizes& sizes, WoodSession& session);   // one tree group per storey
```

**Element rules, computed rather than modified:**
- **Column:** the axis is trimmed analytically, starting at `z_bottom + head_length` when the bottom node has a head and ending at the top node.
- **Head:** `Mesh::loft` or a direct mesh from `(node_arms, node_corners)` using the loft rule from §2 (bottom outline → top square), placed in `grid.frame`. The same function flips to the capital variant used in `1_elements_tree` by swapping the bottom and top outlines. I have not checked whether `Block`'s loft accepts repeated top points.
- **Beam:** node-to-node axis with `beam_extend`. Its ends are cut by the head's arm plane, which is known in closed form: through the outer bottom edge at distance `head_half + head_offset` and the top edge at `head_half`. Only the end section is **projected along the axis onto the plane** (the idea of compas `_loft`, `beam.py:323-337`), which is exact and cannot fail.
- **Plate:** the **face outline inset** by `head_half` (or by half the beam width), sitting at `level + head_length`. Its corners are optionally chamfered by the head's diagonal plane.
- **Wall:** a plate from a vertical face, with thickness to the inside and height between the plate levels. Facade and core come from the tag.
- **Interactions come from incidence, not a BVH:** node→head, edge→column/beam, face→plate/wall. The pairs are column–head at a node, beam–head per arm, plate–head per corner, plate–beam per edge and wall–plate per edge. Store element ids on the grid so `wood_session.compute_contacts` only verifies them.

**Plane cut for the kernel** (the user asked for it; it needs parity with py/rust):
- Signatures: `Mesh Mesh::trim_by_plane(const Plane& plane, double tolerance) const` (keep the +normal side) and `std::pair<Mesh, Mesh> Mesh::split_by_plane(...)`.
- Algorithm:
  1. compute signed distances, snapping |d| < tol to 0;
  2. clip each face polygon against the half-space (Sutherland–Hodgman), sharing edge-intersection points through an edge→point map so the result stays watertight;
  3. collect the cut segments that lie on the plane and chain them into loops, allowing several;
  4. add each loop as a planar cap;
  5. rebuild with `Mesh::from_polylines(polys, tolerance)`.
- The same polygon pipeline gives `BRep::trim_by_plane` for planar-faced BReps through `BRep::from_polylines`. That covers every grid element; NURBS BReps are out of scope.
- `Polyline::cut_by_plane` already handles 2D outlines and can serve features.

**Graph enhancements, if the user wants them in `session_cpp::Graph`** (3-kernel parity rules apply):
- `static Graph from_lines(const std::vector<Line>&, double tolerance)` with a real distance merge (spatial hash or sort + union-find, not string rounding) and an option to split at T-junctions;
- a `Point` per vertex (`vertex_point`, `edge_line`);
- a per-vertex/edge `std::map<std::string, std::string> attributes` with defaults, in the manner of compas `update_default_node_attributes` / `node_attribute(k, name, value)`;
- `vertices_where(key, value)` / `edges_where(key, value)`, as in compas `nodes_where({"is_column": True})`.

Keeping the rules and faces in `grid.h` instead needs no kernel change and no parity work.