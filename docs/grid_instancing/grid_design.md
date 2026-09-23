# grid_design.md: the design to implement (orchestrator-approved)

This file supersedes the DESIGN bullets and examples in your prompt. It has two parts:
- **Part A:** the orchestrator's amendments. They win wherever they conflict with Part B.
- **Part B:** the full design draft. Follow it for everything Part A does not change.

Background, all in this scratchpad:
- `branch_mapping.md`, `branch_app.md`: StructureCraft Branch3D. The user says this is the CLOSEST to what they need.
- `grid_fastepp_tool.md`, `grid_bay_typologies.md`, `grid_grid_datastructures.md`: FAST+EPP bay tool and precedents.
- `report_compas_grid.md`: compas_grid.

The user asked that the grid be general enough for other kinds of grid structure (FAST+EPP / Branch3D applied to various grids).

## Part A: amendments (Branch3D vocabulary and rules)

**A1. Structural system per bay, Branch names.** Replace the face attribute `system` with `structural_system`:

| value | Branch name | UI label | what it builds |
|---|---|---|---|
| 0 | plate | "Point supported" | No beams belong to the bay. The deck sits on the heads. |
| 1 | beam | "Post and beam" | Girders run parallel to the bay's `span` side. The deck spans between the girders. |
| 2 | purlin | "Purlin on girder" | Girders as in 1, plus purlins between them. |

The default comes from `update_default_face_attributes`. The examples set it.

**A2. `span` is the GIRDER direction,** Branch's `spanDirection` generalised to any polygon. It holds the local side index i, and girders run parallel to side i.
- Purlins run from girder to girder, **across** the girder direction. They are stationed along s, the girder direction, at t = lo + (hi − lo)·j/(n + 1).
  - This is the draft's station algorithm with the roles of s and m swapped: station lines are lines of constant (p − p0)·s.
  - Their ends are the crossings with the bay's girder sides, paired as in the draft.
  - They are cut by those girders' side planes.
- `compute_spans(grid, bool longest = false)` picks the shortest side by default. That is FAST+EPP "PLSS, Beams with Long Purlins": girders on the short span, purlins long. `longest = true` picks the longest side. On ties the first side within tolerance wins.
- A user value set before the rule survives.

**A3. Purlin count, Branch `max_purlin_spacing`.** `compute_purlins(grid, double max_purlin_spacing)` writes `purlins` on system-2 floors: n = max(0, ceil(width / max_purlin_spacing − 1e−9) − 1), where width is the extent along s. Other systems get 0. A fixed FAST+EPP count still works through `update_default_face_attributes({{"purlins", N}})` before the rule.

**A4. Rule order and edge roles, Branch rules.** Replace `compute_members` with this sequence; every step fills only absent values:
1. `compute_faces(grid, angle)`: `floor`, `wall`, `roof` by tilt, as in the draft's face pass.
2. `compute_spans(grid, longest)`: see A2.
3. `compute_members(grid, angle)`: line edges become `column`, `beam` or `brace` by tilt, as in the draft. Then, for horizontal line edges:
   - `is_boundary` = 1 when the edge borders at most one floor face (Branch `isBoundary`). Nodes on such edges also get `is_boundary`.
   - `girder` = 1 on a beam that runs parallel (within `angle`) to the `span` side of an adjacent floor with system 1 or 2.
   - A beam that is **not** a girder, **not** `is_boundary`, and whose adjacent floors are all system 1 gets `beam` = 0. This is Branch post-and-beam: interior cross lines carry no beam, and the deck spans onto the girders.
   - Under system 2 such a line keeps its beam and also gets `purlin` = 1. Branch puts a purlin on the cross gridline, so it is built at purlin size.
   - An edge whose adjacent floors are all system 0 gets `beam` = 0 unless it is `is_boundary`. Branch drops even the perimeter beams, but wood keeps them so the deck edge has support; document this.
4. `compute_purlins(grid, max_purlin_spacing)`: see A3.
5. `compute_supports(grid)`: `support`, `head`, as in the draft.
6. `compute_bay` as in the draft.

The through beam at a node is still a girder first (draft `compute_through`).

**A5. Element names are roles:** `"column"`, `"head"`, `"girder"`, `"beam"` (a non-girder beam), `"purlin"` (a purlin-sized beam on a cross line and the bay purlins), `"deck"`, `"wall"`.
- `to_beam` picks `"girder"`, `"purlin"` or `"beam"` from the edge flags, and the section from `Dimensions.beam` or `.purlin`.
- The viewer and `face_contacts(..., names)` can filter on these names.

**A6. Voids, cores and footprints (Branch).**
- A plan face with `top = 0` is a void, as in the draft. That gives Branch's L- and U-shaped presets and core holes.
- Walls come from the plan edge attribute `wall` = 1, with core edges included. `core` = 1 on those edges is informational.

**A7. Instancing readiness.** Do **not** implement instancing in grid.h; a separate task adds it (kernel definitions + InstanceRef, viewer GPU instancing, WoodSession dedup). Builders stay world-space and deterministic, one element per call, so a later dedup pass can find congruent elements: columns of one storey and direction polygon, heads, beams of equal length and cuts, purlins, decks, walls.

**A8. Examples** (house style: CAPS consts, the `|||||||| DESCRIPTION ||||||||` block at the end, no count prints; `std::cout << wood_session;` only in `1_elements_*`):
- `1_elements_flat`: one bay, `structural_system` 1, all four sides `is_boundary`, so 4 beams, 2 of them girders.
  - Expected: 13 elements (4 column, 4 head, 2 girder, 2 beam, 1 deck) and 20 contacts (column–head 4, head–beam 8, beam–beam 4, beam–deck 4).
  - The girders run through; the other two beams butt against them and are cut by the girders' side planes.
- `1_elements_tree`: the same bay three times, 2000 apart, in `bay_i` groups, `compute_contacts(1)`. Expected 39 elements and 60 contacts, none across bays.
- `templates_grid`: Branch-like multistorey orthogonal building:
  - non-uniform bays `XS {9140, 8530, 9140}`, `YS {7600, 7600}`, `HEIGHTS {4500, 3800, 3800}`;
  - `structural_system` 2, `max_purlin_spacing` 3000;
  - one corner bay void (`top = 0`) for an L-shaped footprint, and walls on the boundary edges;
  - `storey_k` groups, `compute_contacts(0)`.
- `templates_grid_radial` and `templates_grid_hex`: as in the draft (§5), with `structural_system` 2.
- Register the three `templates_grid*` targets in CMakeLists.txt. Report the element counts per role and the contact count for every example, and check that every element has at least one contact.

**A9. Prerequisites that already exist.**
- The kernel `Graph` double-attribute API: `vertex_attribute`, `set_vertex_attribute`, `edge_attribute(tuple, name)`, `set_edge_attribute`, `vertices_where`, `edges_where`, `*_where_predicate`, `update_default_*`. Defaults count in `*_where`: check it, and do not assume.
- `Mesh::cut_by_plane` / `BRep::cut_by_plane`.
- The wood `cuts` field on Column, Beam and Block, landing now. Read the current headers for its exact name and behaviour before use.

---

## Part B: the design draft (follow it except where Part A says otherwise)

# General building grid for `wood/src/templates/grid.h` (`namespace wood_grid`): implementer's design

This design replaces section 7 of `report_wood_side.md`. Nothing was built or run. The counts in §6 come from working the geometry by hand plus one Python script that counts plan topology and purlins. The script is `scratchpad/griddesign/counts.py`, under `/tmp/claude-1000/-home-petras-code-code-cpp-wood-research/cd17883b-ad50-44cc-bbcd-c4f797944a70/scratchpad/griddesign/counts.py`.

## 0. Decisions in one screen

- **Three layers.**
  - The plan is any planar n-gon kernel `Mesh`.
  - The building is a 3D node/edge/face network: a kernel `Graph` plus face loops.
  - The elements are derived from (grid, `Dimensions`).
  - Grid types differ only in the plan mesh. Free 3D input bypasses the plan.
- **Every meaning is a `double` attribute:**
  - vertex and edge attributes: kernel `Graph` API;
  - face attributes: a Mesh-named mirror in `Grid`.
- **Rules only fill names that have no value yet, stored or default.** A user override set before the rules therefore survives. Per-bay FAST+EPP inputs (`system`, `purlins`, `span`) are data, not code.
- **Datum: a grid node is the top of the deck.** Every member hangs below it. `heights` are floor-to-floor, like FAST+EPP "Story Height" `dy` and the IFC SSL elevation.
- **Node joint = the 1_elements capital.** The column stops under a head block, the beams sit on the head, the deck sits on the beams, and the upper column stands on the deck.
- **Beam ends at a node:**
  - one **through** beam per node: girders first;
  - the through beam's straight **continuation** meets it on the bisector plane;
  - every other beam **butts** against the through beam's side plane and is mitred against its butting neighbours;
  - an open end runs `reach` past the node, flush with the head's top edge.
- **All trimming uses the new `cuts` (keep the side the normal points to).** Nothing snaps to cardinal directions.
- **Heads are a frustum built from the incident beam directions.** The polygon has one edge perpendicular to each incident direction and its opposite. The bottom loop sits at `column/2` and the top loop at `reach`, so both loops have the same count and distinct points. That makes the head a valid `Block`, so a Mesh `Column(solid, …)` is never needed.

## 1. Representation

```cpp
/// A building grid: nodes and members in a graph, floor, roof and wall loops over its nodes, levels by elevation; every meaning is a double attribute.
struct Grid {
    session_cpp::Graph graph;                                  // Nodes "0", "1", ... carrying x, y, z; edges are grid lines and members.
    std::vector<std::vector<std::string>> faces;               // Node loops of floors, roofs and walls; floors counter-clockwise seen from above.
    std::vector<std::map<std::string, double>> facedata;       // Per-face values, parallel to faces.
    std::map<std::string, double> default_face_attributes;     // Values every face falls back to.
    std::vector<double> levels;                                // Distinct node elevations, ascending; storey k spans levels[k] to levels[k + 1].
    double tolerance = 1.0;                                    // Weld distance and elevation gap, in model units.
};
```

Why this is general enough, in five lines:
1. **Any plan.** The plan is only the generator's input: orthogonal, skewed, radial, triangular, hexagonal, Voronoi or irregular plans are just different n-gon `Mesh`es fed to one extruder, `from_plan`.
2. **Multi-storey with varying heights.** `heights` feed `levels`. Per-face `bottom`/`top` give setbacks, voids and double-height bays. Per-vertex `column = 0` gives transfers and cantilevers.
3. **Free 3D input.** Nodes are true 3D points, so `from_lines(lines, surfaces)` takes compas_grid-style input directly: inclined columns, sloped beams, braces, sloped roofs and walls. This is CellNetwork without cells; compas_grid never uses cells.
4. **Semantics are data.** Everything is a double in the kernel Graph attribute API (`vertex_attribute`, `edges_where`, …) plus a same-named face mirror. FAST+EPP per-bay settings and IFC-style roles are attribute values, not code paths.
5. **Directions come from topology.** Heads, joints, purlins and decks read incident edge directions and face polygons, never world X/Y. This fixes compas_grid's 8-direction snap. A future kernel CellNetwork can adopt the fields mechanically.

Conventions:
- **Node keys** are `std::to_string(i)` in creation order. Positions are the vertex attributes `x`, `y`, `z` (the compas default). `vertex_point` reads them, so editing `z` (for example a roof pitch) is honoured.
- **Every face side is also a graph edge.** A side that is only a face side has no `line` attribute.
- **Avoid the name `level` for tree depth.** Grid grouping uses `storey`, and `compute_contacts(level)` keeps its tree meaning.

Grid methods, in Mesh names:

```cpp
    /// Grid from member lines and surface loops: ends welded within tolerance, lines flagged "line", surfaces as faces, levels computed.
    static Grid from_lines(const std::vector<session_cpp::Line>& lines, const std::vector<session_cpp::Polyline>& surfaces, double tolerance = 1.0);

    /// Grid from a planar plan over storeys of heights: floors per plan face and level, grid lines, columns, walls on plan edges flagged "wall".
    static Grid from_plan(const session_cpp::Mesh& plan, const std::vector<double>& heights, double tolerance = 1.0);

    /// Key of the node within tolerance of point, a new node carrying x, y, z when none is.
    std::string add_vertex(const session_cpp::Point& point);

    /// Index of a new face over loop; its missing sides become graph edges.
    size_t add_face(const std::vector<std::string>& loop);

    session_cpp::Point vertex_point(const std::string& key) const;                                   /// Position from x, y, z.
    session_cpp::Line edge_line(const std::tuple<std::string, std::string>& edge) const;             /// First key to second.
    std::vector<session_cpp::Point> face_points(size_t face) const;                                  /// Loop points, open.
    std::vector<size_t> edge_faces(const std::tuple<std::string, std::string>& edge) const;          /// Faces with the edge as a side.
    std::vector<size_t> vertex_faces(const std::string& key) const;                                  /// Faces through the node.
    std::optional<double> face_attribute(size_t face, const std::string& name) const;                /// Stored, else default, else nullopt.
    void set_face_attribute(size_t face, const std::string& name, double value);
    void update_default_face_attributes(const std::vector<std::pair<std::string, double>>& attrs);
    std::vector<size_t> faces_where(const std::vector<std::pair<std::string, double>>& conditions) const;
```

Each of those four accessor lines gets its own `///` docstring above it in the header. `add_vertex` welds with a linear scan over existing nodes on true distance. That is O(n²), which is fine for a few thousand nodes; replace it with a spatial hash later if needed. Test the neighbour with `graph.has_edge` before `add_edge`: re-adding an edge resets its legacy string.

## 2. Attribute vocabulary (all `double`; a flag is 1, and absent means 0)

**Vertex (node)**

| name | set by | meaning |
|---|---|---|
| `x` `y` `z` | generators | Position. The node is the top of the deck. |
| `level` | `compute_levels` | Index into `levels`: the largest i with `levels[i] ≤ z + tolerance`. |
| `storey` | `compute_levels` | `max(0, level − 1)`: the storey this node caps. |
| `support` | `compute_supports` | Bottom of a column stack: a column goes up, none comes down. |
| `head` | `compute_supports` | A column comes up, and a beam or a floor face meets the node. |
| `column` (plan vertex input) | user on the plan | 0 means `from_plan` adds no columns at this plan vertex (cantilever tip or transfer). |

**Edge**

| name | set by | meaning |
|---|---|---|
| `line` | generators | A member line: drawn (`from_lines`) or generated (`from_plan`). Face-only sides lack it. |
| `column` | `compute_members` | A line within `angle` of vertical. Any direction inside that cone builds a column. |
| `beam` | `compute_members` | A line within `angle` of horizontal, unless every adjacent floor has `system == 2`. |
| `brace` | `compute_members` | Any other line. It is vocabulary only; no builder. |
| `girder` | `compute_spans` | A beam an adjacent floor's purlin direction crosses (with 0 purlins, the one it would cross). Girders run through heads. |
| `storey` | `compute_levels` | `max(0, max(level of ends) − 1)`: columns of storey k, and beams under floor k+1. |
| `wall` (plan edge input) | user on the plan | 1 means `from_plan` adds a wall face under this edge in every storey whose top has the edge. |

**Face**

| name | set by | meaning |
|---|---|---|
| `floor` | `compute_members` | Newell-normal tilt from ±z below `90 − angle`. Floors and roofs both get decks. |
| `wall` | `compute_members` | Tilt at least `90 − angle`. |
| `roof` | `from_plan` (k == top), else `compute_members` | A floor none of whose nodes has a column going up. Informational (loads). |
| `storey` | `compute_levels` | `max(0, max level of loop − 1)`. |
| `system` | user (default 0) | 0 = PLSS "Beams with Long Purlins": purlins parallel to the longest edge. 1 = PSSL "Short Purlins": parallel to the shortest. 2 = PointSupported: no span, no purlins, no beams of its own. |
| `span` | `compute_spans` or user | Local loop index i; purlins run parallel to side (i, i+1). −1 means none. This is Revit's `curveIndexForDirection`. |
| `purlins` | `compute_purlins` or user | Purlin count; FAST+EPP `Npurlin`. Spacing is derived as width/(n+1). |
| `bottom` `top` (plan face input) | user on the plan | Lowest and highest level this bay has a floor on. Defaults are 1 and `heights.size()`. `top = 0` makes a void. |

## 3. Generators, plan builders, rules

**Definition order in the file.** Some functions call others, so define them in this order:
1. structs;
2. Grid accessors;
3. `compute_normal`, `compute_levels`;
4. `Grid::from_lines`, `Grid::from_plan`;
5. plans;
6. rules;
7. helpers;
8. builders.

### 3.1 Generators

**`from_lines(lines, surfaces, tolerance)`**
1. For each line, `a = add_vertex(start)` and `b = add_vertex(end)`. If `a != b`, add the edge and set `line = 1`.
2. For each surface:
   - weld its points;
   - drop the closing duplicate and any consecutive duplicates;
   - skip it if fewer than 3 points remain;
   - reverse the loop when it is not a wall (its Newell normal is not within 45° of horizontal) and the normal's z is below 0;
   - call `add_face`.
3. Call `compute_levels`.

For compas_grid data, pass `mesh.face_outlines()` of the Floor, Facade and Core meshes as `surfaces`. Floor-face sides do **not** become beams, which answers critic item C. Lines must be split at every node.

**`from_plan(plan, heights, tolerance)`**
1. Set `z = {0, h0, h0+h1, …}` and let `n = heights.size()`.
2. For each plan face f:
   - `loop = *plan.face_vertices(f)`. If the Newell normal's z is below 0, reverse the loop and remap a stored `span` with i → (m − 2 − i + m) % m, where m is the loop size.
   - Read `bottom = face_attribute(f,"bottom").value_or(1)` and `top = …value_or(n)`.
   - For each k in [bottom, top]:
     - add the face over `add_vertex(Point(x, y, z[k]))`;
     - copy `plan.facedata[f]` into it;
     - set `roof = 1` when k == top;
     - set `line = 1` on every side.
   - For each k in [0, top) and each loop vertex v whose `plan.vertex_attribute(v,"column").value_or(1) != 0`, add the vertical edge between (v, z[k]) and (v, z[k+1]) with `line = 1`.
3. For each plan edge (u,v) with `plan.edge_attribute({u,v},"wall") == 1`, and each k in [0, n): if the edge at level k+1 exists, `add_face({(u,k), (v,k), (v,k+1), (u,k+1)})`.
4. Merge `plan.default_face_attributes` into `default_face_attributes`.
5. Call `compute_levels`.

**`compute_levels(grid)`** always overwrites.
1. Cluster the sorted node z values into `levels`: start a new level when z − the last level > tolerance.
2. Write `level` and `storey` as defined in §2.

### 3.2 Plan builders

Each builder collects **open** point lists (counter-clockwise) and returns `Mesh::from_polylines(polygons, 0.001)`, the `std::vector<std::vector<Point>>` overload. That call welds the 360° seam and turns `[c, a, b, c]` into the triangle `[c, a, b]` by popping the closing duplicate. Irregular or Voronoi plans skip the builders: the user calls `Mesh::from_polylines(cells, tol)` or `Mesh::from_lines(lines, true, tol)` directly.

```cpp
/// Bays of widths xs along x and depths ys along y from the origin, the y axis leaning skew degrees towards x; skew 0 is orthogonal.
inline session_cpp::Mesh create_orthogonal(const std::vector<double>& xs, const std::vector<double>& ys, double skew = 0.0);
/// Rings at radii cut into sectors over sweep degrees, rings as chords; a first radius of 0 gives a centre node and triangles.
inline session_cpp::Mesh create_radial(const std::vector<double>& radii, int sectors, double sweep = 360.0);
/// Equilateral triangles of side, nx by ny rhombi each split in two.
inline session_cpp::Mesh create_triangular(double side, int nx, int ny);
/// Pointy-top hexagons of side in nx columns and ny rows, odd rows shifted half a cell.
inline session_cpp::Mesh create_hexagonal(double side, int nx, int ny);
```

- **Orthogonal:** `X_i = Σxs[<i]`, `Y_j = Σys[<j]`, `p(i,j) = (X_i + Y_j·sin s, Y_j·cos s, 0)`. The face is `[p(i,j), p(i+1,j), p(i+1,j+1), p(i,j+1)]`, so side 0 runs along x.
- **Radial:** `θ_j = sweep·j/sectors` in degrees and `p(i,j) = r_i(cos θ_j, sin θ_j, 0)`. The face is `[p(i,j), p(i+1,j), p(i+1,j+1), p(i,j+1)]`, so side 0 is a ray.
- **Triangular:** `p(i,j) = side·(i + j/2, j·√3/2)`. The faces are `[p(i,j), p(i+1,j), p(i,j+1)]` and `[p(i+1,j), p(i+1,j+1), p(i,j+1)]`.
- **Hexagonal:** the centre is `(√3·side·(i + (j%2)/2), 1.5·side·j)`, and corner k is at angle `30° + 60°k` for k = 0..5.

### 3.3 Rules

```cpp
/// Clusters node elevations into levels; level on nodes, storey on nodes, edges and faces.
inline void compute_levels(Grid& grid);
/// Faces into floor, wall and roof by tilt; line edges into column, beam and brace by tilt within angle degrees.
inline void compute_members(Grid& grid, double angle = 10.0);
/// Span side per floor from its system, longest or shortest side, first on ties; girder on beams its purlins cross.
inline void compute_spans(Grid& grid, double angle = 10.0);
/// Purlin count per floor: ceil(width / spacing) - 1, 0 without a span or spacing.
inline void compute_purlins(Grid& grid, double spacing);
/// Support at the foot of every column stack, head where a column arrives under a beam or a floor.
inline void compute_supports(Grid& grid);
/// Bay table row of a floor: area, girder, purlin and deck spans, purlin count and length.
inline Bay compute_bay(const Grid& grid, size_t face);
```

Every rule writes a name only where `…_attribute(...)` returns `nullopt`.

**`compute_members`** runs in three passes, in this order:
1. **Faces.** The tilt is `acos(|n̂·z|)` in degrees. Tilt ≥ `90 − angle` gives `wall`; otherwise `floor`.
2. **Line edges.** The tilt is `atan2(|dz|, horizontal length)`.
   - Tilt ≥ `90 − angle`: `column`.
   - Tilt ≤ `angle`: `beam`, unless the edge's floor faces are non-empty and all of them have `system == 2`.
   - Otherwise: `brace`.
3. **Roof.** A floor gets `roof` when none of its nodes has a `column` neighbour above it.

The 10° default is topologicpy's `Decompose(tiltAngle=10)`.

**`compute_spans`**, for each floor:
1. Read `system` (`value_or(0)`). System 2 writes `span = −1`.
2. Otherwise, take the first side whose horizontal length is within `tolerance` of the maximum (system 0) or of the minimum (system 1). The tolerance matters: regular hexagons tie up to float noise.
3. With `s` = the horizontal unit of the span side, set `girder = 1` on every side that has `beam` and satisfies `|ê·s| < cos(angle)`.

**`compute_purlins`**, for each floor:
- If `span < 0` or `spacing ≤ 0`, write 0.
- Otherwise:
  - set `m = z × s`;
  - take `width = max − min` of `(p − p0)·m` over the loop;
  - write `max(0, ceil(width/spacing − 1e−9) − 1)`.

This is Revit's `LayoutRuleMaximumSpacing`. For a fixed FAST+EPP count, call `update_default_face_attributes({{"purlins", N}})` before the rule.

**`compute_supports`:**
- `support` goes on nodes with a `column` neighbour above and none below.
- `head` goes on nodes with a `column` neighbour below plus a `beam` neighbour or a floor face.

**`compute_bay`** returns this struct:

```cpp
/// One row of a bay table, what a bay design tool sizes members from.
struct Bay {
    double area = 0.0;    // Plan area, |Newell| / 2.
    double girder = 0.0;  // Longest girder side, the girder span.
    double purlin = 0.0;  // Longest station line, centre to centre, the purlin span.
    double deck = 0.0;    // width / (purlins + 1), the deck span.
    int purlins = 0;      // Purlin count.
    double length = 0.0;  // Summed station lengths.
};
```

It runs on every face. FAST+EPP sizes one interior bay only; here corner and edge bays and non-uniform bays each get their own row.

## 4. Element builders

**Dimensions**

```cpp
/// Member sizes every element of a grid shares, in model units.
struct Dimensions {
    double column = 200.0; // Column width across flats; also the head bottom.
    double head = 300.0;   // Head height, column top to beam underside.
    double reach = 200.0;  // Head top half-width; through beams and decks also run this far past an open end.
    double beam = 200.0;   // Beam section side, girders included (Beam is square).
    double purlin = 200.0; // Purlin section side, top flush with the beams.
    double deck = 200.0;   // Deck thickness; nodes are the deck top.
    double wall = 100.0;   // Wall thickness, centred on the grid line.
};
```

**Height stack at a node of elevation z.** `head top = z − deck − (node has a beam ? beam : 0)`, which is `compute_head_top`.

| part | bottom | top |
|---|---|---|
| deck | z − deck | z |
| beam (axis z − deck − beam/2) | z − deck − beam | z − deck |
| purlin (axis z − deck − purlin/2) | z − deck − purlin | z − deck (flush, as in FAST+EPP) |
| head | head top − head | head top |
| column | lower node z (deck top or ground) | upper head bottom (upper z when there is no head) |
| wall | lower node z | upper z − deck − beam |

### 4.1 Helpers

```cpp
/// Newell normal of a loop, unnormalised.
inline session_cpp::Vector compute_normal(const std::vector<session_cpp::Point>& points);
/// Unit plan directions of the horizontal edges at a node and their opposites, sorted by angle, closer than 1 degree merged; one line adds its perpendicular, none gives x and y.
inline std::vector<session_cpp::Vector> compute_directions(const Grid& grid, const std::string& node);
/// Polygon at centre whose edge j is perpendicular to directions[j] at distance.
inline session_cpp::Polyline compute_polygon(const std::vector<session_cpp::Vector>& directions, const session_cpp::Point& centre, double distance);
/// Loop with side i moved out by distances[i] in its plane.
inline std::vector<session_cpp::Point> compute_offset(const std::vector<session_cpp::Point>& points, const session_cpp::Vector& normal, const std::vector<double>& distances);
/// Neighbour whose beam runs through node: girder first, then one with a continuation, then the smallest angle from x.
inline std::optional<std::string> compute_through(const Grid& grid, const std::string& node);
/// Other beam neighbour at node within 45 degrees of straight on from other, the straightest.
inline std::optional<std::string> compute_continuation(const Grid& grid, const std::string& node, const std::string& other);
/// Elevation of the head top at node.
inline double compute_head_top(const Grid& grid, const std::string& node, const Dimensions& dimensions);
/// End point and cut planes of the beam from node towards other, at its node end.
inline std::pair<session_cpp::Point, std::vector<session_cpp::Plane>> compute_cuts(const Grid& grid, const std::string& node, const std::string& other, const Dimensions& dimensions);
/// Purlin centre lines of a floor, on its sides' centre lines.
inline std::vector<session_cpp::Line> compute_stations(const Grid& grid, size_t face);
```

**`compute_directions`** starts from all incident edges except those flagged `column` or `brace`. It keeps those whose horizontal projection is longer than tolerance, adds each direction and its negative, then sorts by `atan2` and merges directions closer than 1°, including across the wrap. The result is symmetric with at least 4 directions, so every gap is below 180°.

**`compute_polygon`:** vertex j is `centre + (u_j + u_{j+1}) · distance / (1 + u_j·u_{j+1})`, closed. The same directions give the same point count at any distance. No points repeat, because every edge has length `distance·(tan(θ₁/2) + tan(θ₂/2)) > 0`.

**`compute_offset`**, at vertex i, with `o = (edge unit) × normal` pointing outward for a counter-clockwise loop and `c = o_{i−1}·o_i`:
- if `1 − c² < 1e−9`, then `q = p_i + o_i·max(d_{i−1}, d_i)`;
- otherwise `α = (d_{i−1} − c·d_i)/(1 − c²)`, `β = (d_i − c·d_{i−1})/(1 − c²)` and `q = p_i + α·o_{i−1} + β·o_i`.

**`compute_cuts(node, other)`.** Let `p = node point − z·(deck + beam/2)`, `a` = horizontal unit from node to other, and `t = compute_through(node)`.
1. **This beam is the through beam** (`*t == other`):
   - Let `b = compute_continuation(node, other)`.
   - If there is none, the end is open: return `{p − a·reach, {}}`. The end sits flush with the head's top edge, because −a is one of the directions.
   - Otherwise, with ĉ = unit(b − node): return `{p − a·reach, {Plane::from_point_normal(p, (a − ĉ).normalized())}}`. This is the bisector plane: perpendicular for a straight line, a true mitre for radial chords.
2. **Otherwise the beam butts:**
   - Let `u` = unit(t − node), `s = z × u`, and flip s if `s·a < 0`.
   - The planes are `Plane::from_point_normal(p + s·beam/2, s)`, the through beam's side face.
   - Add a bisector `Plane(p, (a − ĉ).normalized())` for each angular neighbour ĉ of `other` among the node's beams (previous and next by `atan2`) that is neither `t` nor `compute_continuation(node, *t)`. Without these mitres, two butting beams on the same side (as at a triangular-grid node) would overlap.
   - Return `{p, planes}`.

**`compute_stations`:**
1. Let `n = purlins` and `i = span`. Return nothing if `n ≤ 0` or `i < 0`.
2. Let `s` = horizontal unit of side i, `m = z × s`, and `[lo, hi]` the range of `(p − p0)·m`.
3. For j = 1..n, with `t = lo + (hi − lo)·j/(n+1)`:
   - for every side where `da = (p_k − p0)·m − t` and `db` have different signs, record the crossing `q = p_k + (p_{k+1} − p_k)·da/(da − db)` (0 counts as positive);
   - sort the crossings by `(q − p0)·s` and pair them (0,1), (2,3), … into lines. This handles non-convex bays.

### 4.2 Builders

```cpp
/// Column on a column edge: lower node to the head bottom, section the node's direction polygon at column / 2.
inline std::shared_ptr<wood_session::Column> to_column(const Grid& grid, const std::tuple<std::string, std::string>& edge, const Dimensions& dimensions);
/// Head block on a head node: direction polygon at column / 2 on the column top, at reach at the head top.
inline std::shared_ptr<wood_session::Block> to_head(const Grid& grid, const std::string& node, const Dimensions& dimensions);
/// Beam on a beam edge, its ends from compute_cuts at both nodes.
inline std::shared_ptr<wood_session::Beam> to_beam(const Grid& grid, const std::tuple<std::string, std::string>& edge, const Dimensions& dimensions);
/// Purlins of a floor on its stations, cut by the side planes of the girders they end on.
inline std::vector<std::shared_ptr<wood_session::Beam>> to_purlins(const Grid& grid, size_t face, const Dimensions& dimensions);
/// Deck plate of a floor: sides alone at their level pushed out by reach, shared sides on the centre line.
inline std::shared_ptr<wood_session::Plate> to_deck(const Grid& grid, size_t face, const Dimensions& dimensions);
/// Wall plate of a wall face: between the column faces, chamfered along the head faces, deck top to beam underside.
inline std::shared_ptr<wood_session::Plate> to_wall(const Grid& grid, size_t face, const Dimensions& dimensions);
```

- **`to_column`**
  - Order the ends by z into `lo` and `hi`. Take `zb = z(lo)`, and `zt = compute_head_top(hi) − head` if `hi` has `head`, else `z(hi)`.
  - The axis points lie on the line lo→hi at zb and zt; the line is parametrised by z, so inclined columns work.
  - The section is `compute_polygon(compute_directions(hi), bottom, column/2)`.
  - Build `Column(Line::from_points(bottom, top), section, "column")`. The kernel sweeps a horizontal section, so an inclined column is a sheared prism with horizontal ends, and its top face equals the head's bottom loop.
- **`to_head`**
  - `lo` is the `column` neighbour below the node.
  - Take `zt = compute_head_top(node)` and `zb = zt − head`. The centres lie on the line lo→node at zb and zt.
  - Build `Block({compute_polygon(D, at(zb), column/2), compute_polygon(D, at(zt), reach)}, "head")`, where D = `compute_directions(node)`.
  - The loops have equal counts, distinct points, and the same start direction, so the Block is valid.
- **`to_beam`**
  - With `st = compute_cuts(u, v)` and `en = compute_cuts(v, u)`, build `Beam(Polyline({st.first, en.first}), beam/2, "beam")`.
  - Set `cuts = st.second` and append `en.second`.
- **`to_purlins`**
  - The drop is `z·(deck + purlin/2)`.
  - For each end q, and for every loop side whose segment passes within tolerance of q (1 side, or 2 at a vertex), add `Plane(q + in·beam/2, in)` with `in = (z × (p_{k+1} − p_k)).normalized()`.
  - Build `Beam(Polyline({a − drop, b − drop}), purlin/2, "purlin")` with those cuts.
- **`to_deck`**
  - Let n̂ be the unit face normal.
  - `distances[i] = reach` if `edge_faces(side i)` contains no other `floor` face, else 0.
  - `top = Polyline(compute_offset(points, n̂, distances)).closed()`.
  - Build `Plate(top.translated(n̂·−deck), top, "deck")`.
- **`to_wall`**
  - Take the two lowest loop nodes `a0, b0` and the nodes above them, `a1, b1`.
  - Let `e` = horizontal unit from a0 to b0, `n = z × e`, `z0 = z(a0)`, `z1 = z(a1) − deck − beam` and `zh = z1 − head`.
  - At an end whose top node has `head`, the outline goes up along `c/2` to zh, then along the head face to `reach` at z1. At other ends it stays on the node line at full height.
  - The outline is `A(a0+e·c/2, z0) B(b0−e·c/2, z0) C(b0−e·c/2, zh) D(b0−e·reach, z1) E(a0+e·reach, z1) F(a0+e·c/2, zh)`.
  - Build `Plate(outline − n·wall/2, (outline + n·wall/2).closed(), "wall")`.
  - The chamfer is coplanar with the head face in direction e, because e is always in D. The wall therefore touches the column, the head, the beam above and the deck below.

**Prerequisite.** Column, Beam and Block need a public `std::vector<session_cpp::Plane> cuts`, with the kept side being the one the normal points to. The `element_*.proto` files and `wood_element_{column,block}.cpp` (`cut_geometry(element_geometry(), cuts)` → `set_geometry`) already have it. The `.h` files did not have it yet on 2026-09-22, because another agent is mid-edit.

**Header budget, about 650 lines:**
- structs: 60
- Grid accessors and face API: 90
- generators and levels: 110
- plans: 70
- rules and bay: 120
- helpers: 110
- builders: 130

## 5. Examples

Every example starts with `#include "wood_session.h"`, `#include "src/templates/grid.h"`, `using namespace session_cpp; using namespace wood_session;`. Options are CAPS consts at file scope. Every example ends with the existing `|||||||| DESCRIPTION ||||||||` banner block. Only the `1_elements_*` examples keep `std::cout << wood_session;`, as they print today.

Add the templates to CMake; `1_elements_*` are already registered:
```cmake
ADD_EXE(templates_grid examples/templates_grid.cpp)
ADD_EXE(templates_grid_radial examples/templates_grid_radial.cpp)
ADD_EXE(templates_grid_hex examples/templates_grid_hex.cpp)
```

**1_elements_flat.** One bay built through the grid, identical in geometry to today's example.
```cpp
const std::vector<double> XS = {4000.0};
const std::vector<double> YS = {3000.0};
const std::vector<double> HEIGHTS = {3700.0};
const double SYSTEM = 1.0;
const double ANGLE = 10.0;
const wood_grid::Dimensions DIMENSIONS{.column = 200.0, .head = 300.0, .reach = 200.0, .beam = 200.0, .purlin = 200.0, .deck = 200.0, .wall = 100.0};

int main() {

    wood_grid::Grid grid = wood_grid::Grid::from_plan(wood_grid::create_orthogonal(XS, YS), HEIGHTS);
    grid.update_default_face_attributes({{"system", SYSTEM}});
    wood_grid::compute_members(grid, ANGLE);
    wood_grid::compute_spans(grid, ANGLE);
    wood_grid::compute_supports(grid);

    WoodSession wood_session("elements_flat");

    for (const std::tuple<std::string, std::string>& edge : grid.graph.edges_where({{"column", 1.0}}))
        wood_session.add(wood_grid::to_column(grid, edge, DIMENSIONS));

    for (const std::string& node : grid.graph.vertices_where({{"head", 1.0}}))
        wood_session.add(wood_grid::to_head(grid, node, DIMENSIONS));

    for (const std::tuple<std::string, std::string>& edge : grid.graph.edges_where({{"beam", 1.0}}))
        wood_session.add(wood_grid::to_beam(grid, edge, DIMENSIONS));

    for (const size_t face : grid.faces_where({{"floor", 1.0}}))
        wood_session.add(wood_grid::to_deck(grid, face, DIMENSIONS));

    wood_session.compute_contacts(0);

    std::cout << wood_session;
    wood_session.pb_dump(pb_path("live").string());

    return 0;
}
```
`HEIGHT 3700 = 3000 column + 300 head + 200 beam + 200 deck`. `SYSTEM 1` puts the short purlins along y, so the girders run along x and the x beams run through, as today.

**1_elements_tree.** The same constants plus `const double GAP = 2000.0;`. The main body becomes:
```cpp
    WoodSession wood_session("elements_tree");

    for (int i = 0; i < 3; i++) {

        const Mesh plan = wood_grid::create_orthogonal(XS, YS).transformed(Xform::translation(i * (XS[0] + 2 * DIMENSIONS.reach + GAP), 0.0, 0.0));
        wood_grid::Grid grid = wood_grid::Grid::from_plan(plan, HEIGHTS);
        grid.update_default_face_attributes({{"system", SYSTEM}});
        wood_grid::compute_members(grid, ANGLE);
        wood_grid::compute_spans(grid, ANGLE);
        wood_grid::compute_supports(grid);

        const std::shared_ptr<TreeNode> branch = wood_session.add_group(fmt::format("bay_{}", i));
        // the four loops of 1_elements_flat, each ending in wood_session.add(..., branch)
    }

    wood_session.compute_contacts(1);
```

**templates_grid.** Multistorey and orthogonal, with non-uniform bays (the CWC 9.14 / 8.53 m example), purlins, end walls and storey branches.
```cpp
const std::vector<double> XS = {9140.0, 8530.0, 9140.0};
const std::vector<double> YS = {7600.0, 7600.0};
const std::vector<double> HEIGHTS = {4500.0, 3800.0, 3800.0};
const double SYSTEM = 1.0;
const double SPACING = 3000.0;
const double ANGLE = 10.0;
const wood_grid::Dimensions DIMENSIONS{.column = 365.0, .head = 400.0, .reach = 400.0, .beam = 365.0, .purlin = 265.0, .deck = 175.0, .wall = 175.0};

int main() {

    Mesh plan = wood_grid::create_orthogonal(XS, YS);
    for (const std::pair<size_t, size_t>& edge : plan.edges_on_boundary())
        if (std::abs((*plan.vertex_point(edge.first))[0] - (*plan.vertex_point(edge.second))[0]) < 1.0)
            plan.set_edge_attribute(edge, "wall", 1.0);

    wood_grid::Grid grid = wood_grid::Grid::from_plan(plan, HEIGHTS);
    grid.update_default_face_attributes({{"system", SYSTEM}});
    wood_grid::compute_members(grid, ANGLE);
    wood_grid::compute_spans(grid, ANGLE);
    wood_grid::compute_purlins(grid, SPACING);
    wood_grid::compute_supports(grid);

    WoodSession wood_session("templates_grid");
    std::vector<std::shared_ptr<TreeNode>> storeys;
    for (size_t storey = 0; storey < HEIGHTS.size(); storey++)
        storeys.push_back(wood_session.add_group(fmt::format("storey_{}", storey)));

    const auto branch = [&](const std::optional<double>& storey) { return storeys[static_cast<size_t>(storey.value_or(0.0))]; };

    for (const std::tuple<std::string, std::string>& edge : grid.graph.edges_where({{"column", 1.0}}))
        wood_session.add(wood_grid::to_column(grid, edge, DIMENSIONS), branch(grid.graph.edge_attribute(edge, "storey")));

    for (const std::string& node : grid.graph.vertices_where({{"head", 1.0}}))
        wood_session.add(wood_grid::to_head(grid, node, DIMENSIONS), branch(grid.graph.vertex_attribute(node, "storey")));

    for (const std::tuple<std::string, std::string>& edge : grid.graph.edges_where({{"beam", 1.0}}))
        wood_session.add(wood_grid::to_beam(grid, edge, DIMENSIONS), branch(grid.graph.edge_attribute(edge, "storey")));

    for (const size_t face : grid.faces_where({{"floor", 1.0}})) {
        wood_session.add(wood_grid::to_deck(grid, face, DIMENSIONS), branch(grid.face_attribute(face, "storey")));
        for (const std::shared_ptr<Beam>& purlin : wood_grid::to_purlins(grid, face, DIMENSIONS))
            wood_session.add(purlin, branch(grid.face_attribute(face, "storey")));
    }

    for (const size_t face : grid.faces_where({{"wall", 1.0}}))
        wood_session.add(wood_grid::to_wall(grid, face, DIMENSIONS), branch(grid.face_attribute(face, "storey")));

    wood_session.compute_contacts(0);
    wood_session.pb_dump(pb_path("live").string());

    return 0;
}
```
`compute_contacts(0)` is required: the storey groups would otherwise hide the contact between a column and the deck of the storey below.

**templates_grid_radial.** The same main as `templates_grid` without the wall loop, with:
- `plan = wood_grid::create_radial({4000.0, 8000.0, 12000.0}, 12)`: an atrium annulus, so there is no 12-valent centre;
- `HEIGHTS = {4000.0}`, `SYSTEM = 0.0`, so purlins run parallel to the longest side, the outer chord; they are tangential, and the rays become through girders;
- `SPACING = 2000.0`;
- `DIMENSIONS{.column = 240, .head = 300, .reach = 400, .beam = 240, .purlin = 200, .deck = 160, .wall = 120}`.

**templates_grid_hex.** The same, with:
- `plan = wood_grid::create_hexagonal(4000.0, 3, 2)`;
- `HEIGHTS = {4000.0, 3600.0}`, `SYSTEM = 1.0` (every side ties, so side 0 wins in every cell), `SPACING = 2500.0`;
- the radial DIMENSIONS.

## 6. Expected counts

**1_elements_flat: 13 elements, 20 contacts.**
- Elements: 4 `column`, 4 `head`, 4 `beam`, 1 `deck`.
- Geometry, which equals today's file:
  - columns: 200 squares, z 0–3000;
  - heads: 200 square at z 3000 to 400 square at z 3300;
  - x beams: axis z 3400, x −200 to 4200, no cuts;
  - y beams: axis 0 to 3000, cut at y=100 (normal +y) and y=2900 (normal −y);
  - deck: (−200,−200)–(4200,3200), z 3500–3700.
- Contact pairs:
  - column–head ×4;
  - head–beam ×8: each head carries its through x beam and its butting y beam;
  - beam–beam ×4: each y beam's cut face against an x beam's side face;
  - beam–deck ×4.

**1_elements_tree: 39 elements, 60 contacts.** That is 20 per `bay_i` branch and none across branches.

**Element counts for the templates.** Plan V/E/F and purlin counts come from `counts.py`.

| example | columns | heads | beams | purlins | decks | walls | total |
|---|---|---|---|---|---|---|---|
| templates_grid (plan V12 E17 F6, 3 storeys, purlins per bay 3/2/3) | 36 | 36 | 51 | 48 | 18 | 12 | **201** |
| templates_grid_radial (V36 E60 F24, 1 purlin per bay) | 36 | 36 | 60 | 24 | 24 | 0 | **180** |
| templates_grid_hex (V22 E27 F6, 2 storeys, 2 purlins per cell) | 44 | 44 | 54 | 24 | 12 | 0 | **178** |

For the templates, the checkable properties are the element counts above, and that every element has at least one contact. I did not derive exact contact totals for them.

## 7. FAST+EPP Bay Design Tool mapping

| FAST+EPP (v2 id / v1 name) | Grid |
|---|---|
| `dx` "Grid Dimension X", `Nx` bays | `xs = std::vector<double>(Nx, dx)`; unequal lists are allowed |
| `dz` "Grid Dimension Y", `Nz` | `ys = std::vector<double>(Nz, dz)` |
| `dy` "Story Height", `Nstories` | `heights = std::vector<double>(Nstories, dy)` |
| `framingSystem` `PLSS` / `PSSL` / `PointSupported` | face `system` 0 / 1 / 2, settable per bay |
| `Npurlin` / "No. of Purlins" | face `purlins`, per bay |
| v1 "Purlin Width (mm)", "Girder Width (mm)" | `Dimensions.purlin`, `.beam` (square sections) |
| "Total Structural Depth" = deck + max(purlin, girder) (flush) | `deck + max(beam, purlin)`; purlin tops sit flush with beam tops |
| "Bay Data" / "Takeoffs" | `compute_bay` per face; counts from the element lists |
| materials, `FRR`, `fire_protection`, SDL/LL | out of scope; store as extra face or edge doubles if needed |

## 8. Limits and what I could not find

**Out of scope, by design:**
- **Column-through nodes.** FAST+EPP hangs its beams on continuous column faces. That would be a node attribute plus a second branch in `to_column`/`to_beam`.
- **Stacked framing.** It would add one offset per role.
- **Rectangular sections.** `Beam` is square; a rectangular section needs a Column with a horizontal axis, or Beam heights plus a proto field.
- **Braces.** They have no builder: a plain `Beam` on the edge line works.
- **Serializing the grid.** Only the elements go to pb.
- **Different grids per level** need separate Grids or `from_lines`.
- **Offsets are vertical.** Roofs steeper than `angle` get approximate decks and purlins.

**Degenerate cases:**
- A purlin station through a bay vertex gets both sides' planes, which is correct only at a convex corner. The hexagon example with 1 purlin would hit this; with 2 it does not.
- A high-valence centre node (radial with `radii[0] = 0`) gives a large 2n-gon head. Oblique rays may then end beyond `reach` and touch only other beams. Use an atrium, or a larger `reach`.

**Not verified:**
- that `Graph::vertices_where` and `edges_where` match defaults as well as stored values;
- that `Mesh::cut_by_plane` stays robust when a cut plane contains a face;
- that the `cuts` field lands in the element headers with this name;
- that `Mesh::transformed` keeps halfedges.

**Not found:**
- the FAST+EPP v2 server geometry, so the exact PLSS/PSSL meaning is known only from the labels (the site returns 521, and `/api/updateBay` needs a login);
- any documented multi-storey timber floor on hexagonal, triangular or Voronoi grids (the roles and rules above are extrapolated).

Sources: FAST+EPP bundle ids and defaults (Wayback `bay-design-tool.fastepp.com/assets/auth-4a5c4e64.js`); IFC 4.3 `IfcGridTypeEnum` (RECTANGULAR/RADIAL/TRIANGULAR/IRREGULAR); Revit `BeamSystem` `curveIndexForDirection` and `LayoutRuleMaximumSpacing`; topologicpy `Decompose(tiltAngle=10)`; compas_grid `gridmodel.py` rules (`is_column`, `is_beam`, `is_floor`); the CWC 3-storey design example (9.14 / 8.53 m bays, purlins at 3.05 m).

Local files read:
- `/home/petras/code/code_cpp/wood_research/session/session_cpp/src/graph.h`
- `/home/petras/code/code_cpp/wood_research/session/session_cpp/src/mesh.h` (from_polylines at mesh.cpp:274, add_face at 2301)
- `/home/petras/code/code_cpp/wood_research/wood/src/joinery_solver/wood_elements/*.h`, `.cpp`
- `/home/petras/code/code_cpp/wood_research/wood/examples/1_elements_flat.cpp`, `1_elements_tree.cpp`
---

## Part C: cores (user request 2026-09-23, Branch3D `cores` / `coreData`)

Branch models 0–2 cores as rectangles `{width, depth, position = min corner}` placed anywhere in the plan, independent of the bays. Their effects:
- they make holes in every floor;
- they remove the columns inside them;
- they remove the beams entirely inside them;
- they split crossing beams at the core boundary, and that end is supported on the core;
- the core itself is concrete walls ("Carbon Summary (excl Core)").

In wood the core walls are `Plate` elements.

**C1. Data.** A core is a closed plan polygon plus a storey range. `Grid.cores` is a vector of `{Polyline outline; int bottom; int top;}`, with defaults of 0 and the top storey.

Helpers:
- `core_from_rectangle(width, depth, position)`, where position is the min corner (Branch).
- `compute_core_position(grid, width, depth)`: optional auto placement, Branch `S_e`. It takes the candidate farthest from the perimeter and from other cores.

**C2. Rule `compute_cores(grid, thickness)`.** Run it after `compute_members` and before `compute_supports`.
- **Columns.** A column edge whose plan point lies strictly inside a core gets `column = 0` for the storeys the core spans.
- **Beams.** A beam edge entirely inside a core gets `beam = 0`. A beam crossing the core boundary keeps `beam = 1` and gets `core = 1` on the edge. `to_beam` then adds a cut plane: the core wall's outer face, offset by `thickness / 2`, with the kept side outside the core. The beam ends on the wall and gets a face contact with it (Branch's `{type:"core"}` support).
- **Floors.** A floor face that overlaps a core gets face attribute `core_hole = 1`. `to_deck` then builds the deck outline minus the core polygon, offset by `thickness / 2`.
  - If `Plate` cannot hold a hole, split the deck along the core's lines into pieces instead: one Plate per piece, with no overlap.
  - Report which approach you used.
- **Walls.** One wall per core side per storey, thickness `thickness` centred on the core outline, named `"core"`.
  - Vertically, it runs from the storey's lower level to its upper level minus the deck. Decks then sit on the core walls at their edges, as a face contact.
  - Corners meet with a butt joint: the first wall runs through, the second is cut by its side plane, as beams do. This avoids overlapping plates.

**C3. Builders.**
- `to_core_walls(grid, core_index, dimensions)` returns one Plate per side per storey.
- `Dimensions.core` is the core wall thickness, default 250 mm (concrete).

**C4. Examples and checks.**
- `templates_grid_core`: a Branch-default 18288 × 18288 mm square with 4572 mm increments, 2 storeys at 3658 mm, post and beam along x, and one 6096 × 6096 core with its min corner at (6096, 6096). That is Branch's 20 × 20 ft at (20, 20).
- Compare it with the Branch3D capture of the same settings. Its column count per storey must match Branch's rule: grid points and perimeter points, minus the ones inside the core. Split beams must end on the core walls.
- Every element has at least one contact, and no plates overlap (clash check).
- `templates_grid` (the L-shape) may use a core in place of its void bay, whichever reads better.

---

## Part D: no colours (user request 2026-09-23)

3D output stays in the viewer's default grey transparent look:
- **Elements and features:** no colour is assigned to any element, feature, contact or joint outline. Remove the `paint(...)` calls and the linecolor assignments in wood (`contact_feature`, the plate joint sides, the beam joint volumes).
- **Name and colour tables:** `contact_type_name` / `joint_type_name` stay. The colour tables `contact_color` / `joint_color` go, unless something outside the viewer path still needs them.
- **Screenshots:** strip colours from reference models too (FAST+EPP glTF, Branch3D, crea layers) before rendering side-by-side comparisons or doc images.

---

## Part E: section profiles for Beam and Column (user request 2026-09-23, Branch3D profiles)

Branch3D's profile vocabulary:
- **column:** `"Square" | "Rectangular" | "Round" | "W" | "HSS" | "Circular"`
- **girder:** `"Rectangular" | "Square" | "Double girder" | "Slab band" | "Precast girder" | "W" | "HSS" | "Open web joist"`
- **purlin:** `"Rectangular Timber" | "W" | "Double purlin" | "Rectangular Concrete" | "Slab band" | "HSS" | "Open web joist"`

Today our Beam is square only (`radius`), and Column takes a world-placed section polyline.

**E1. Profile library.** A new file, `wood/src/joinery_solver/wood_elements/wood_profile.{h,cpp}` (or `wood_element_geometry`, if that keeps it smaller):
- A profile is `std::vector<session_cpp::Polyline>` in its own 2D frame. Loop [0] is the outer loop, counter-clockwise, centred on the member axis at (0,0). Loops [1..] are holes, clockwise. x is the width and y is the depth (up for beams).
- Functions, named with `to_*` / `from_*` / `compute_*` where they convert or derive, otherwise nouns as the kernel uses them:
  - `profile_rectangle(width, depth)`
  - `profile_circle(diameter, segments = 16)`
  - `profile_w(width, depth, flange, web)`: I or W
  - `profile_hss(width, depth, wall)`: outer loop plus one hole
  - `profile_double(width, depth, gap)`: two rectangles. If one element cannot hold two disjoint loops, build two members.
  - `profile_slab_band(width, depth)`: a wide rectangle
  - `profile_t(width, depth, web, flange)`: compas_grid `from_t_profile`
- Open web joist is out of scope; document it.

**E2. Beam.**
- Add `std::vector<session_cpp::Polyline> profile;`. When it is empty, the square from `radius` is used as today.
- `sections()` places the profile at each axis vertex: x along `side`, y along `rise`, the frame from `square_section`'s logic.
- `sweep_sections` / `brep_sections` handle holes: the loft with holes, the Block path.
- Proto: `element_beam.proto` gets `repeated session_proto.Polyline profile = <next free>`.
- Keep the `Beam(axis, radius)` constructor. Add `Beam(axis, profile)`.
- `cuts`, `transformed`, `place` and `element_key` must include the profile.

**E3. Column.**
- Add `Column(const Line& axis, const std::vector<Polyline>& profile, double rotation = 0)`. It places the profile at the axis base in the plane perpendicular to the axis (x along world x projected, or rotated by `rotation`). Holes give a hollow column.
- Proto: `element_column.proto` gets `repeated session_proto.Polyline profile = <next free>` (the local profile), next to the existing world `section`.

**E4. Grid.**
- `Dimensions` holds a profile per role: `column`, `girder`, `purlin`, `wall` / `core` thickness, `deck`.
- The builders read width and depth from the profile's bounding box for stacking:
  - girder top at deck underside;
  - purlin tops flush with the girders (FAST+EPP top-flush);
  - head top at girder underside.
- The examples show at least one non-square case: rectangular glulam girders (for example 215 × 456, the FAST+EPP v1 output) and W or HSS in one example.

**E5. Checks.** Per profile, the swept member is closed. Mesh and BRep volumes equal the profile area × length, holes subtracted. Cuts still close the solid. Contacts on rectangular beams find the correct faces.
