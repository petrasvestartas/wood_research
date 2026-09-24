# Grid v2: the one design (Fable step 3 synthesis)

The spec the builders follow. Inputs: `fable_brief.md` (wins), the three candidate designs (`design_settings.md`, `design_axes.md`, `design_solid.md`), the three judges' verdicts, `research_joints.md`, `research_inputs.md`, `research_api.md`, `research_branch.md`, `wood/src/templates/grid.h` at wood `563d1a4` with its five examples, and the Branch3D / FAST+EPP / crea captures. Every kernel and wood signature quoted here was read from the headers on 2026-09-23 (`mesh.h`, `polyline.h`, `intersection.h`, `closest.h`, `brep.h`, `graph.h`, `wood_element_{plate,beam,column,block}.h`, `wood_session.h`). Units mm, z up. Wood-side only: nothing under `session/` is edited in this pass.

## 0. Decisions

Judges: solid 32 / axes 31 / settings 30, solid 8-8-8-8 / axes 6-9-8-6 / settings 7-8-7-6, and one vote for axes on the joint lens. The synthesis is **solid-first as the core and the API**, with the ten grafts the judges agreed on. Where the judges disagreed, the choice and the reason:

| Question | Chosen | Why |
|---|---|---|
| Core container | `Level{z, rings, holes, cores, plan}` with the plan a kernel `Mesh`; `Building{levels, braces}` | ordered vertex fans, O(1) `edge_faces` / `vertex_faces`, attributes and `*_where` already on the kernel type (mesh.h:645, 609, 636, 717-787); no mirror of Mesh incidence (the critique told step 3 to delete it) |
| Entry points | `Building::from_solid` (Mesh, BRep) / `from_footprint` / `from_lines`, then `to_session(session, framing)` | names the thing the designer drew; `Framing` is applied at build time so one building serves several framings and every attribute override wins |
| Semantics on the plan | kernel `Mesh` double attributes (vertex, edge, face), defaults through `update_default_*_attributes` | the same kernel attribute API the brief calls "kernel Graph double attributes"; a `Graph` mirror would add string keys and positions-as-attributes for nothing. **To confirm with petras** (both solid judges asked); a `to_graph()` export is one function if he wants the Graph type itself |
| Datum | `Level.z` = framing top = deck underside; deck `[z, z + deck]`, member tops hang from `z − drop(role)` | Branch and FAST+EPP overlay with nothing moved (two of three judges); Branch storey heights are datum to datum |
| Sections | two per level, `z − ε` and `z + ε`, plan on their union, the intersection ring `C_k = S_k⁺ ∩ S_{k+1}⁻` added as lines to both plans; level 0 at `z + ε` only, the top at `z − ε` only | the probes showed an exact slice loses a podium roof and that setback column feet need to be nodes (`research_inputs.md` §3.5) |
| Columns between levels | node identity `(line_a, line_b)` first, then same point within `tolerance`, then same pattern line within `taper`, else `transfer` | a key lookup instead of polygon matching (axes graft 8); `merge` is only the in-plan weld, never the vertical test |
| Purlin stations | `Line`s per face, one code path through `to_beam`, each end remembering the member it lands on | Mesh has no edge split; stations as edges would split every bay face and its deck; two of three judges kept lines. `Mesh::split_edge` is a kernel proposal |
| Girders | one two-point `Beam` per plan edge, no chains | stations are not edges, so a girder is never split by them |
| Deck holes | `Plate` with `features = {[outer, holes...], [outer, holes...]}` | verified: `Plate::compute_model_geometry` lofts `features.bottom` / `features.top` (`wood_element_plate.cpp:190`); no `Block` fallback |
| Open holes vs cores | `Level.holes` (atrium, courtyard: face dropped, no walls, edge beams on the ring when it is in the arrangement) and `Level.cores` (void face, walls on the ring, deck hole) | axes graft 7; trimmers for a hole inside one bay are a later structural refinement, the deck keeps the bay through `face_holes` (probe 4) |
| Empty footprint | every bounded cell of the pattern (`Mesh::from_lines(..., true)`) | radial, hexagonal and triangular need no hand-computed outline |
| Footprint with holes | `from_footprint` takes `std::vector<Polyline>` rings, outer counter-clockwise, holes clockwise | a courtyard in B without a massing |
| Profiles | a named `Profiles` struct, one field per role, fallbacks per field | autocomplete instead of a role typo that silently takes the default |
| Perimeter layer | a boundary edge on a girder-family line is an edge girder (girder layer, takes `drop`); on any other line an edge beam (purlin layer, never drops) | what keeps a stacked purlin off the perimeter |
| Stubs | a girder or purlin piece shorter than its own width after a core cut is dropped | Branch's 3 mm stubs go |
| Head | bottom = direction polygon at the column profile's support distance per direction; top at `reach` | circumscribes W, HSS and round columns |
| Column orientation | profile x axis along the through member at the head node | FAST+EPP's 315 along x |
| Facade | `Framing.facade`: a wall under every perimeter member; C keeps drawn wall runs as plan edges with `wall` 1 (facade) or 2 (core) | crea's facade and core walls that compas drops get built |
| Free lines | family −1 carries a beam of rank 5; `span = −1` makes every line a beam | hexagonal, irregular and hand-drawn grids get V mitres |
| Panels | `Framing.panel > 0` splits a deck into equal strips across the deck span | parallel-plane splits cannot create overlap |
| Verification | the test compares member lists (start, end, section, elevations) with the Branch / FAST+EPP / crea captures, plus zero clashes and one contact per element | pixels alone prove nothing |

Not taken, on purpose: the axes `Graph` with face nodes and member chains; the four-knob framing (`girders / beams / spacing / edges`; `system / span / spacing` reads as Branch's wizard does); settings' single-section slicing; a `wood_grid::core()` rectangle helper (`Polyline::rectangle` exists, the session-polyline-rectangle skill forbids a second one); a `std::map<std::string, ...>` of profiles; a `Bay` takeoff row or any sizing data.

## 1. Public API

As built (2026-09-24): the code is compiled, not header-only, in three stages under `wood/src/templates/`: `grid.h` (the public API and `to_mesh`), `grid_levels.cpp` (patterns, sections resampled on the pattern, level plans, workflows A, B, C), `grid_joints.h/.cpp` (the joint rules), `grid.cpp` (roles, columns, stations, elements, `to_elements`/`to_session`), with `grid_plan.h/.cpp` the plan geometry they share (moved from `wood_elements/wood_plan_geometry`) and `clash.h/.cpp`. The rest of this section is the original plan.

Four headers under `wood/src/templates/` (`plan.h`, `grid.h`, `grid_joints.h`, `clash.h`) and one under `wood/src/joinery_solver/wood_elements/` (`wood_profile.h` + `.cpp`). Everything in `namespace wood_grid` except the profiles, which are `wood_session` free functions beside the elements they feed. All template code is header-only `inline`, house style (`compute_*` for derivations, `to_*` / `from_*` for conversions, one-line `///` docstrings, banners from the session-comments skill, no `auto` except iterators and lambdas, no prints).

### 1.1 `grid.h`: the five structs a user meets

```cpp
#pragma once
#include "wood_session.h"
#include "wood_profile.h"
#include "src/templates/plan.h"
#include "src/templates/grid_joints.h"

namespace wood_grid {

// ═══════════════════════════════════════════════════════════════════════════
// Pattern
// ═══════════════════════════════════════════════════════════════════════════

/// Plan lines a building is drawn on, at z 0, each in a parallel family: 0 and 1 the two directions a rectangular system names, 2 a third family, -1 a free line.
struct Pattern {
    std::vector<session_cpp::Line> lines; // Segments in plan, as long as the pattern extends; a footprint beyond them gets no members there.
    std::vector<int> families; // One per line.

    /// Lines along x at the running sums of ys (family 0) and along y at the running sums of xs (family 1), the y axis leaning skew degrees towards x.
    static Pattern orthogonal(const std::vector<double>& xs, const std::vector<double>& ys, double skew = 0.0);

    /// Rays from the first radius to the last (family 0) and ring chords at every radius (family 1) over sweep degrees; a first radius of 0 gives a centre point.
    static Pattern radial(const std::vector<double>& radii, int sectors, double sweep = 360.0);

    /// Three families of lines at 0, 60 and 120 degrees, side apart, over nx by ny rhombi.
    static Pattern triangular(double side, int nx, int ny);

    /// Edges of pointy-top hexagons of side in nx columns and ny rows, every edge a free line (family -1).
    static Pattern hexagonal(double side, int nx, int ny);

    /// Lines as drawn with a family per line, all free when families is empty.
    static Pattern from_lines(const std::vector<session_cpp::Line>& lines, const std::vector<int>& families = {});

    /// A copy moved by xform: the pattern's origin and rotation under the building.
    Pattern transformed(const session_cpp::Xform& xform) const;
};

/// Bay widths over length at spacing, Branch's rule: whole bays from the start while the rest is at least remainder long, the rest as the last bay.
inline std::vector<double> compute_bays(double length, double spacing, double remainder = 304.8);

// ═══════════════════════════════════════════════════════════════════════════
// Framing
// ═══════════════════════════════════════════════════════════════════════════

/// Section per role, each a profile in its own frame (loop 0 outer counter-clockwise centred on the axis, x width, y depth up; loops 1.. holes); an empty role falls back as noted.
struct Profiles {
    std::vector<session_cpp::Polyline> column = wood_session::profile_rectangle(300.0, 300.0);
    std::vector<session_cpp::Polyline> girder = wood_session::profile_rectangle(200.0, 600.0);
    std::vector<session_cpp::Polyline> beam; // Members on free lines and under span -1; empty takes girder.
    std::vector<session_cpp::Polyline> purlin; // Purlin rows and stations; empty takes beam.
    std::vector<session_cpp::Polyline> edge_girder; // Perimeter members on girder-family lines; empty takes girder.
    std::vector<session_cpp::Polyline> edge_beam; // Perimeter members on any other line or ring edge; empty takes purlin under system 2, else beam.
    std::vector<session_cpp::Polyline> brace; // Workflow C braces; empty takes beam.
};

/// How every level is framed and jointed: the structural method, the joint choices and the sizes; per-bay and per-member changes are attributes on the level plans.
struct Framing {
    int system = 1; // 0 point supported (deck on columns or heads, no members), 1 post and beam (girders on the span family, the deck spans between them), 2 purlin on girder (girders plus purlin rows at spacing).
    int span = 0; // Pattern family the girders run on; -1 every line carries a beam (two-way, hexagonal, irregular).
    double spacing = 3000.0; // Largest purlin spacing under system 2; ceil(cell / spacing) intervals per unclipped cell, one row on every interior cross line.
    int edge = 1; // Perimeter members on the section rings and hole rings: 1 built, 0 none.
    int node = 0; // Column joint: 0 head (capital under the members), 1 flush (column top at the datum, members into its faces, deck over all), 2 through (column datum to datum, deck notched, members into its faces).
    double drop = 0.0; // Girder top below the datum: 0 flush with the purlins, 203.2 hung as Branch, the purlin depth stacked.
    double deck = 200.0; // Deck thickness above the datum.
    double wall = 200.0; // Facade and core wall thickness, centred on the line.
    double head = 300.0; // Head height under node 0.
    double reach = 400.0; // Head top half-width, and how far an open member end runs past its node when nothing butts into it.
    double panel = 0.0; // Largest deck strip width across the deck span; 0 one deck per bay.
    double merge = 1000.0; // Column points closer than this weld to the earlier one in a plan: ring vertices, then ring crossings, then interior crossings.
    double taper = 30.0; // Largest lean in degrees of a perimeter column following a moving section; beyond it the vertex is a transfer.
    double angle = 10.0; // Tilt tolerance in degrees: horizontal within angle, vertical within 90 - angle.
    double tolerance = 1.0; // Weld distance, coplanarity and clash tolerance.
    bool facade = false; // A wall under every perimeter member.
    Profiles profiles; // Sections per role.
};

// ═══════════════════════════════════════════════════════════════════════════
// Building
// ═══════════════════════════════════════════════════════════════════════════

/// One level: its datum, the section rings at it, the open holes, the cores, and the plan the pattern fills into the section; faces are bays, edges member lines, vertices column points, every meaning a double attribute (section 3).
struct Level {
    double z = 0.0; // Datum: the framing top, the deck underside.
    std::vector<session_cpp::Polyline> rings; // Section at z, the union of the slices just below and just above: outer rings counter-clockwise seen from above, holes clockwise, all at z 0.
    std::vector<session_cpp::Polyline> holes; // Open holes (atria, courtyards drawn as holes): no deck, no walls, edge members round them when they are in the arrangement.
    std::vector<session_cpp::Polyline> cores; // Core rings on the wall centre line, counter-clockwise: a void face, a wall per side, a deck hole, a support for the members that reach them.
    session_cpp::Mesh plan; // Arrangement of the pattern and the rings inside the section; a hole or core ring that meets no line is a face hole of its bay.
};

/// A building as its levels: the same pipeline from a massing, a footprint or drawn lines; elements per storey from a Framing.
struct Building {
    std::vector<Level> levels; // Ascending; storey k spans levels[k] to levels[k + 1]; levels[0] is the ground and carries the column feet.
    std::vector<session_cpp::Line> braces; // Tilted lines from from_lines, built as beams cut by what they meet.
    double tolerance = 1.0; // Weld distance the plans were built with.

    /// A. A closed massing sliced at elevations: sections just below and just above each, their union filled with pattern, cores as rings through every level; columns follow the sections within taper.
    static Building from_solid(const session_cpp::Mesh& massing, const std::vector<double>& elevations, const Pattern& pattern, const std::vector<session_cpp::Polyline>& cores = {}, double tolerance = 1.0, double merge = 1000.0);

    /// A. The same for a BRep: cut exactly when every face is planar, else through mesh() with facet degrees per curved face.
    static Building from_solid(const session_cpp::BRep& massing, const std::vector<double>& elevations, const Pattern& pattern, const std::vector<session_cpp::Polyline>& cores = {}, double tolerance = 1.0, double merge = 1000.0, double facet = 15.0);

    /// B. Footprint rings (outer counter-clockwise, holes clockwise; empty means every bounded cell of the pattern) at the level elevations, the first the ground, the same section on every level, cores on every level above the ground.
    static Building from_footprint(const std::vector<session_cpp::Polyline>& footprint, const std::vector<double>& elevations, const Pattern& pattern, const std::vector<session_cpp::Polyline>& cores = {}, double tolerance = 1.0, double merge = 1000.0);

    /// C. Members and surfaces as drawn: horizontal lines and floors make the plan of their level, vertical lines its column points, vertical surfaces its walls (2 when named core, 1 otherwise), tilted lines braces; duplicates in either direction merged, lines split at every node and crossing.
    static Building from_lines(const std::vector<session_cpp::Line>& lines, const std::vector<session_cpp::Polyline>& surfaces, double tolerance = 1.0, double angle = 10.0);

    /// Every element of storey k with its joints resolved, world space, in plan order so instance_by_key() dedups them: columns and walls standing in the storey, then the heads, members, stations and decks of the level that caps it, then its braces.
    std::vector<std::shared_ptr<session_cpp::Element>> to_elements(const Framing& framing, size_t storey) const;

    /// Every storey's elements added to session under a group per storey named storey_k.
    void to_session(wood_session::WoodSession& session, const Framing& framing) const;
};

} // namespace wood_grid
```

Counts: 5 structs, 16 public callables (`orthogonal`, `radial`, `triangular`, `hexagonal`, `from_lines`, `transformed`, `compute_bays`, `from_solid` ×2, `from_footprint`, `from_lines`, `to_elements`, `to_session`, plus `compute_clashes` / `compute_overlap` in `clash.h`), 18 attribute names (section 3), 3 coded ints (`system`, `span`, `node`). Nothing to order by hand: one constructor, one `to_session`.

An override is a kernel call between the two: `building.levels[3].plan.set_face_attribute(5, "system", 0.0)`, `building.levels[3].plan.set_vertex_attribute(7, "column", 0.0)`, `building.levels[2].plan.set_edge_attribute({4, 9}, "role", 0.0)`; a per-storey framing is `to_elements(other_framing, k)` for that storey instead of `to_session`.

### 1.2 `plan.h`: pure geometry, the kernel queue (≈ 220 lines)

No building meaning; each function is a rename away from the kernel (section 10).

```cpp
/// Rings of the cap faces of solid cut at the horizontal plane through z: outer rings counter-clockwise seen from above, face_holes as clockwise holes, all dropped to z 0; empty above the solid.
inline std::vector<session_cpp::Polyline> compute_section(const session_cpp::Mesh& solid, double z, double tolerance);

/// Intersection (0), union (1) or difference (2) of two ring lists with holes kept, output rings oriented as compute_section; Clipper2.
inline std::vector<session_cpp::Polyline> compute_regions(const std::vector<session_cpp::Polyline>& a, const std::vector<session_cpp::Polyline>& b, int clip);

/// Rings inflated by distance with mitre joins, holes kept; Clipper2 InflatePaths.
inline std::vector<session_cpp::Polyline> compute_offset(const std::vector<session_cpp::Polyline>& rings, double distance);

/// Even-odd inside test over all rings, so a ring inside a hole is an island.
inline bool compute_inside(const std::vector<session_cpp::Polyline>& rings, const session_cpp::Point& point);

/// Every line split at every crossing and T-junction with another, collinear overlaps merged first; ids follow their source line.
inline std::pair<std::vector<session_cpp::Line>, std::vector<double>> compute_crossings(const std::vector<session_cpp::Line>& lines, const std::vector<double>& ids, double tolerance);

/// Mesh::from_lines of split lines with the outer face deleted, edge attribute line from the split's ids and vertex attributes line_a, line_b from the two lowest ids meeting there; slivers below tolerance squared dropped.
inline session_cpp::Mesh compute_arrangement(const std::vector<session_cpp::Line>& lines, const std::vector<double>& ids, double tolerance);

/// Vertices closer than merge welded onto the earlier one in priority order: the given first vertices win.
inline session_cpp::Mesh compute_weld(const session_cpp::Mesh& plan, const std::vector<size_t>& priority, double merge);

/// One plane per face of a closed mesh, normal out; exact for the swept and lofted solids the builders make.
inline std::vector<session_cpp::Plane> compute_planes(const session_cpp::Mesh& solid);

/// Planes of the faces the ray from origin along direction leaves the solid through, within tolerance of the first exit, normals flipped to keep the outside.
inline std::vector<session_cpp::Plane> compute_exit(const std::vector<session_cpp::Plane>& planes, const session_cpp::Point& origin, const session_cpp::Vector& direction, double tolerance);

/// Plane through origin containing up, bisecting unit directions a and b, normal towards a; perpendicular to a when b is opposite.
inline session_cpp::Plane compute_bisector(const session_cpp::Point& origin, const session_cpp::Vector& a, const session_cpp::Vector& b, const session_cpp::Vector& up);

/// Closed polygon about centre whose side j is perpendicular to directions[j] at distances[j]; the direction polygon of a node.
inline session_cpp::Polyline compute_polygon(const std::vector<session_cpp::Vector>& directions, const session_cpp::Point& centre, const std::vector<double>& distances);

/// Unit plan directions of the edges at a plan vertex and their opposites, counter-clockwise, closer than 1 degree merged; one edge adds its perpendicular, none gives x and y.
inline std::vector<session_cpp::Vector> compute_directions(const session_cpp::Mesh& plan, size_t vertex);
```

Kernel calls underneath, all verified by the probes: `Mesh::cut_by_plane` (mesh.h:885) with `get_face_holes` (483) and `face_polygon` (696) for sections; Clipper2 (vendored, compiled into `wood_core`, `wood/CMakeLists.txt:133`) for `compute_regions` and `compute_offset`; `Polyline::point_in_polygon_2d` (polyline.h:141); `Intersection::line_line_parameters` (intersection.h:53, clamped) and `Polyline::line_line_overlap` (255) for the split; `Mesh::from_lines(lines, true, tolerance)` (mesh.h:347); `Mesh::remove_face` (570) for faces outside the section; `Mesh::vertex_neighbors(key, true)` (645) for the ordered fan; `Plane::from_point_normal` (plane.h:112).

### 1.3 `grid_joints.h`: the rule system, readable on its own (≈ 200 lines)

```cpp
/// Rank of a role at a node, highest through: core wall 9, column under node 1 or 2 8, edge girder and edge beam 7, girder 6, beam 5, purlin 4, deck 3, facade wall 2, brace 1, none 0.
inline int compute_rank(int role, const Framing& framing);

/// Top and bottom of a member of role at a level, relative to its datum: deck [0, +deck], purlin, beam, edge beam and brace [-d, 0], girder and edge girder [-drop - d, -drop], d the profile depth from compute_size.
inline std::pair<double, double> compute_range(int role, const Framing& framing, double drop);

/// The edge that runs through vertex: the highest rank among the horizontal members there, then one with a straight continuation within 45 degrees, then the smallest angle from x; the vertex attribute through overrides.
inline std::optional<std::pair<size_t, size_t>> compute_through(const session_cpp::Mesh& plan, size_t vertex, const Framing& framing);

/// Cut planes of the member on edge at its vertex end: exit faces of every dominant member at the vertex whose range overlaps the member's (the column under node 1 and 2, the through member, a core wall), bisectors with equal angular neighbours, the plane at the farthest butting end-face corner when it is through and open, reach past the vertex when nothing meets it.
inline std::vector<session_cpp::Plane> compute_cuts(const session_cpp::Mesh& plan, std::pair<size_t, size_t> edge, size_t vertex, const Framing& framing, double z, const std::vector<std::shared_ptr<wood_session::Column>>& columns);

/// Deck loops of a face: boundary sides on the outer face of the boundary member or the column there, whichever is further out; interior sides on the line; core sides on the core wall's outer face; minus every through column section (node 2); face_holes as core outer rings or open hole rings.
inline std::vector<session_cpp::Polyline> compute_outline(const session_cpp::Mesh& plan, size_t face, const Framing& framing, const std::vector<std::shared_ptr<wood_session::Column>>& columns);

/// Loops of the deck of a face cut into ceil(width / panel) equal strips across the deck span; one loop set when panel is 0.
inline std::vector<std::vector<session_cpp::Polyline>> compute_panels(const std::vector<session_cpp::Polyline>& loops, const session_cpp::Vector& span, double panel);
```

### 1.4 `clash.h`: the proof (≈ 80 lines)

```cpp
/// Volume of other inside convex, the face half-spaces of convex pulled in by tolerance so faces that touch or lie within tolerance count for nothing: repeated Mesh::cut_by_plane, then Mesh::volume().
inline double compute_overlap(const session_cpp::Mesh& convex, const session_cpp::Mesh& other, double tolerance);

/// Every pair of world elements overlapping by more than tolerance as (guid, guid, volume), largest first, AABB pairs inflated by tolerance; a plate is the disjoint union of triangle prisms from its cap triangulation; empty means no clash.
inline std::vector<std::tuple<std::string, std::string, double>> compute_clashes(const wood_session::WoodSession& session, double tolerance = 1.0);
```

### 1.5 `wood_profile.h` (Part E, `namespace wood_session`)

```cpp
/// A profile is loops in the section frame: loop 0 the outline counter-clockwise centred on the axis, x across, y up; loops 1.. holes clockwise.
std::vector<session_cpp::Polyline> profile_rectangle(double width, double depth);
std::vector<session_cpp::Polyline> profile_round(double diameter, int segments = 16);
std::vector<session_cpp::Polyline> profile_w(double width, double depth, double flange, double web);
std::vector<session_cpp::Polyline> profile_hss(double width, double depth, double thickness);
std::vector<session_cpp::Polyline> profile_double(double width, double depth, double gap); // Two outlines; the builder makes two members side by side with the same cuts.
std::vector<session_cpp::Polyline> profile_slab_band(double width, double depth);
std::vector<session_cpp::Polyline> profile_t(double width, double depth, double web, double flange);

/// Width and depth of a profile from its loop 0 bounding box.
std::pair<double, double> compute_size(const std::vector<session_cpp::Polyline>& profile);

/// Support distance of a profile in a plan direction: half its extent along that direction, what a head bottom needs to circumscribe it.
double compute_support(const std::vector<session_cpp::Polyline>& profile, const session_cpp::Vector& direction);
```

Element changes (E2, E3, unchanged from `grid_design.md` Part E): `Beam` gains `std::vector<session_cpp::Polyline> profile` and `Beam(const Polyline& axis, const std::vector<Polyline>& profile, const std::vector<Vector>& directions = {}, const std::string& name = "beam")`; `sections()` places the profile at each axis vertex with x along the side and y along `directions[i]`; `sweep_sections` / `brep_sections` loft holes; `Column` gains `Column(const Line& axis, const std::vector<Polyline>& profile, double rotation = 0.0, const std::string& name = "column")` placing the profile in the plane perpendicular to the axis, x along world x projected then rotated; `cuts`, `transformed`, `place`, `element_key` and the protos (`element_beam.proto`, `element_column.proto`: `repeated session_proto.Polyline profile`) carry it. The square-from-`radius` path stays. Open web joist is out of scope, documented.

## 2. File layout and budget

| File | Lines | Content |
|---|---|---|
| `wood/src/templates/plan.h` | ≈ 220 | the twelve geometry functions of 1.2, banners: Sections, Arrangement, Planes |
| `wood/src/templates/grid_joints.h` | ≈ 200 | rank / range / through 50, cuts 80, outline and panels 70 |
| `wood/src/templates/grid.h` | ≈ 480 | structs 90, patterns 70, levels 70, constructors 110, roles / columns / stations 80, builders and `to_elements` / `to_session` 60 |
| `wood/src/templates/clash.h` | ≈ 80 | overlap 25, clashes 55 |
| `wood/src/joinery_solver/wood_elements/wood_profile.{h,cpp}` | ≈ 40 + 130 | seven profiles, `compute_size`, `compute_support` |
| `Beam` / `Column` profile support + protos | ≈ 150 changed | E2, E3 |
| `wood/tests/wood_grid_test.cpp` | ≈ 250 | one case per example: counts, clashes, contacts, member lists |
| each example | 30–45 | consts 6–12, `main` 8, usage block |

Include order: `grid.h` includes `plan.h` and `grid_joints.h`; `grid_joints.h` includes `plan.h` and `wood_profile.h` and forward-declares `Framing` (or `grid.h` defines the structs first and includes `grid_joints.h` after them; the builder picks whichever compiles with `pch.h`). `clash.h` includes only `wood_session.h`. The old `grid.h` (1088 lines) is replaced whole; `1_elements_flat`, `1_elements_tree`, `templates_grid`, `templates_grid_radial`, `templates_grid_hex` and `tests/wood_instance_test.cpp` (it builds the tree scene through the template) are rewritten on the new API in the same commit. CMake: one `ADD_EXE` line per example, `ADD_EXE(wood_grid_test tests/wood_grid_test.cpp)` under `BUILD_TESTING` with an `add_test` through `tools/run_guarded.sh -n wood-solver` and `RUN_SERIAL TRUE`, exactly as `wood_instance` (CMakeLists.txt:272-279).

## 3. Attributes on `Level.plan` (kernel `Mesh` doubles; absent = 0; a rule fills only what is absent, so a user's value wins)

| On | Name | Values | Written by |
|---|---|---|---|
| face | `floor` | 1 a deck is built; 0 inside a core, a hole, on level 0 unless a floor was drawn | constructor; user |
| face | `core` | 1 a core void | constructor |
| face | `hole` | 1 an open hole (atrium, courtyard) | constructor |
| face | `system`, `span`, `spacing`, `thickness` | per-bay override of `Framing.system`, `.span` (family index, same meaning), `.spacing`, `.deck` | user |
| edge | `family` | pattern family of the line; −1 on rings | constructor |
| edge | `line` | arrangement line id: pattern index `i`, or `1000000 + 1000·r + e` for edge `e` of ring `r` (section rings, then holes, cores, `C` rings, in order) | constructor |
| edge | `boundary` | 1 on a section-ring or hole-ring edge | constructor |
| edge | `wall` | 0 none, 1 facade (section-ring edge when `facade`, C's vertical surfaces), 2 core | constructor (cores, C); `to_elements` (facade) |
| edge | `role` | 0 none, 1 girder, 2 beam, 3 purlin, 4 edge girder, 5 edge beam, 6 brace | `compute_roles`; user |
| edge | `drop` | overrides `Framing.drop` for this member | user |
| edge | `width`, `depth` | scale the role profile for this member | user |
| vertex | `column` | 1 a column rises to this vertex from the level below; 0 none (core rings, inside cores and holes, station ends, user); 2 transfer (no support found), written by `compute_columns` | constructor; `compute_columns`; user |
| vertex | `boundary` | 1 on a section ring | constructor |
| vertex | `line_a`, `line_b` | ids of the two arrangement lines that made the vertex, lowest first: the identity used across levels | constructor |
| vertex | `through` | index of the edge (its position in `plan.vertex_neighbors(vertex, true)`) that runs through; absent lets the rank decide | user |

Eighteen names, three of them (`line`, `line_a`, `line_b`) bookkeeping a user never writes. `storey` is the level index and needs none. Positions are mesh vertices. Level 0 carries `column` 1 on every vertex that is a column point (the feet) and `floor` 0 on every face unless a floor was drawn (C) or the user sets it.

## 4. Pipeline

```
A  Mesh / BRep ── compute_section at z ± ε ─┐
B  rings × elevations ─ same rings per level ──┼─► levels[k]{z, rings, holes, cores, plan}  ─► to_elements(framing, k)
C  lines + surfaces ── group by z ───────────┘         ▲                                     │ working copies of plans k, k + 1
                                                       │                                     ├─ compute_roles      edge role, face floor
   pattern ── compute_plan(pattern, rings, holes, cores) per level                           ├─ compute_columns    feet on level k, identity, taper
                                                                                             ├─ compute_stations   purlin lines per bay
                                                                                             ├─ compute_cuts       exit faces, bisectors, ranges
                                                                                             └─ to_column / to_head / to_beam / to_deck / to_wall
```

### 4.1 Level producers

**A, `from_solid(Mesh)`.** `orient_outward()` on a copy. For elevation `z_k`: `S_k⁻ = compute_section(solid, z_k − ε)` and `S_k⁺ = compute_section(solid, z_k + ε)`, `ε = tolerance`; level 0 uses `S⁺` only, the last level `S⁻` only. `rings = compute_regions(S⁻, S⁺, 1)`; `holes` = the clockwise rings of that union (atria, courtyards come back as `face_holes` of the caps, `research_inputs.md` §1); `cores` = the given core rings whose centroid is inside the union. `C_k = compute_regions(S_k⁺, S_{k+1}⁻, 0)` per storey; its rings that are not already rings of level k or k + 1 (compared after `compute_crossings`' collinear merge) are added as extra lines to both plans, so a setback tower's column feet are vertices of the podium roof plan (T1 of `research_inputs.md` §3.5). Rings go through `Polyline::merge_collinear` so a faceted curved face keeps only its facet corners. Then `compute_plan` per level.

**A, `from_solid(BRep)`.** When every face is planar: `BRep::cut_by_plane` (brep.h:318) per section and the cap rings read from `face_rings` the same way. Otherwise `mesh()` once through `face_meshes_q(true, facet, chord)` (brep.h:294) welded with `Mesh::from_polylines`, then the Mesh path (a curved BRep cut returns empty, verified).

**B, `from_footprint`.** `levels[k].z = elevations[k]` (the one vertical convention of A, B and C: `Level.z` is an elevation); `rings` = the footprint on every level (an empty footprint means every bounded cell: `compute_plan` runs `Mesh::from_lines(lines, true)` on the pattern alone and takes every remaining face as a bay, its outer edges as `boundary`); `holes` = the clockwise footprint rings; `cores` on every level above the ground. No extrusion and no slicing: the result equals `from_solid` of the prism and costs nothing. The plan is computed once and copied to every level with equal `Level` fields (the prismatic shortcut; instancing for free).

**C, `from_lines`.** Cluster line ends and surface corners by z within `tolerance` into elevations (`angle` decides horizontal / vertical: a line is horizontal when its tilt is within `angle`, vertical within `90 − angle`, else a brace; a surface by its normal the same way). Per level: the horizontal lines at that z and the edges of the horizontal surfaces there go through `compute_crossings` (this merges crea's ten direction-reversed duplicates and splits T-junctions) and `compute_arrangement`; faces whose centroid is inside a drawn floor get `floor` 1, the others 0; `rings` = `compute_regions` union of the floor faces (so `boundary` and perimeter roles still work); every vertex of a drawn line gets `column` 1 when a vertical line ends or starts there, else 0; a vertical surface sets `wall` 1 (2 when its name contains `core`) on the plan edge under its top side, welded within `tolerance` by `Closest::line_point` (closest.h:36, clamped; never `Polyline::closest_distance_and_point`, which is unclamped, polyline.cpp:542); a vertical line whose foot is at the ground adds a lone vertex to level 0 (`Mesh::add_vertex`, mesh.h:561) with `column` 1. Tilted lines go to `braces`. A drawn wall run whose edge is not already a plan edge is added as a line before the arrangement, so the wall has an edge to stand on. `Pattern` families are absent, so every drawn line is family −1: `span = −1` in the framing makes every line a beam, or a user sets `family` on the edges.

### 4.2 `compute_plan(pattern, rings, holes, cores, tolerance, merge) → Mesh`

1. Lines: pattern segments with ids `i`; ring edges (section rings, holes, cores, `C` rings) with ids `1000000 + 1000·r + e`. A hole or core ring that crosses no other line is held back (probe 4: an isolated loop makes `from_lines` drop its surrounding face).
2. `compute_crossings` (collinear overlaps merged, then every crossing and T-junction split, O(n²) over ≤ 60 lines for Branch, 889 for crea: milliseconds).
3. `compute_arrangement`: `Mesh::from_lines(segments, true, tolerance)`, edge `line`, vertex `line_a` / `line_b`, sliver faces below `tolerance²` removed.
4. Faces whose centroid fails `compute_inside(rings)` or lies inside a hole ring: `remove_face`. Faces inside a core ring: `floor` 0, `core` 1. Faces inside a hole ring that is in the arrangement: `floor` 0, `hole` 1, then removed (their edges on the ring stay as boundary edges of the neighbours).
5. Held-back rings inside a kept face become its `face_holes` (`set_face_holes`, mesh.h:486): a core one is remembered as a core hole (its walls come from `Level.cores`, the deck hole from `compute_outline`), an open one is a deck hole with no members (trimmers: later refinement).
6. `compute_weld(plan, priority, merge)`: priority = section vertices, then section crossings, then interior crossings; a vertex within `merge` of an earlier one welds onto it (Branch's 1 m rule, first wins); edges shorter than `merge` that this creates collapse. `merge` is a plan weld only; it never decides a column between levels.
7. Attributes: `family` per edge from its pattern line (−1 on rings), `boundary` on section and hole ring edges and their vertices, `wall` 2 on core ring edges, `column` 1 on every vertex that is pattern ∩ pattern, pattern ∩ section ring, or a section vertex; `column` 0 on core ring vertices, inside cores, inside holes and on hole rings; `floor` 1 on the kept faces.

Verified shape: Branch's P20 L gives 20 columns, 19 with a core, 10 bays (9 quads + 1 hexagon); skewed families give 52 nodes / 27 bays; a tapered L sliced at three levels gives 20 nodes per level (`research_inputs.md` §2).

### 4.3 `compute_columns(building, k, framing) → std::vector<std::pair<Point, Point>>` (feet on level k, heads on level k + 1)

For every vertex `v` of level k + 1 with `column` 1 (a `through` or user override respected):

1. A vertex of level k with the same `(line_a, line_b)`: vertical when the points coincide within `tolerance`; inclined when the lean from vertical is within `taper`; else no match.
2. No identity match: a vertex of level k at the same plan point within `tolerance` (a footprint drawn per level, C's drawn columns).
3. Still none and `v` is a section vertex or lies on pattern line `L` (its `line_a` or `line_b` is a pattern id): the nearest vertex of level k on the same line `L`, or a section vertex, within `taper`: inclined.
4. Otherwise no column; `v` is written `column` 2 (transfer); its members and deck stay, a later pass reads the flag.
5. A vertex inside or on a core ring on either level: no column (Branch's rule, confirmed on the Residential preset: on-ring counts too).

Storey 0 feet are the level-0 plan vertices with `column` 1, which exist wherever the pattern crosses the bottom section (or where C drew a foot). Prismatic buildings hit rule 1 only. A level-k vertex with nothing above is a roof vertex for that deck (a podium terrace). The inclined column solid is the profile swept perpendicular to its axis, over-length, cut by the foot and top planes of section 5.3.

### 4.4 `compute_roles(plan, framing)` on a working copy, filling only absent `role`

| Edge | `role` |
|---|---|
| section-ring or hole-ring edge (`boundary` 1) | `framing.edge` 0 → 0; else 4 (edge girder) when the edge is parallel within `angle` to the span family, 5 (edge beam) otherwise; under `span` −1 always 5. A pattern line coincident with a ring edge is the ring edge: the perimeter wins |
| core-ring edge | 0 (its wall is `wall` 2) |
| pattern edge, system 0 | 0 |
| pattern edge, family = span family | 1 (girder) |
| pattern edge, `span` −1 or family −1 | 2 (beam), rank 5 |
| pattern edge, cross family, system 2 | 3 (purlin on the cross line, Branch's station 0) |
| pattern edge, cross family, system 1 | 0 (Branch: post and beam carries nothing across) |
| C drawn line | as the rows above with its family; −1 gives 2 |
| C brace | 6, built from `Building.braces` |

Face: `floor` stays; `system`, `span`, `spacing`, `thickness` read with the framing as default. The facade flag sets `wall` 1 on every `boundary` edge that has no `wall` yet.

### 4.5 `compute_stations(plan, face, framing) → std::vector<std::pair<Line, support>>`

System 2 faces only. Girder direction = the mean direction of the face's span-family edges (or the face `span` override). Stations run parallel to the face's cross-family edges when it has any, else perpendicular to the girders. Count: the unclipped cell width is the distance between the two consecutive cross-family pattern lines bounding the face (read from the edge `line` ids and the pattern), `n = ceil(cell / spacing)` intervals, stations at `k · cell / n`, `k = 1..n − 1` (station 0 is the cross line, already a role-3 edge). Each station is clipped to the face and its `face_holes` (crossings with the face polygon and the hole rings sorted along the station and paired), and each end remembers the edge or ring it landed on as its support (the girder, an edge member, a core wall). Stationing over the **unclipped** cell gives Branch's purlin at 15240 in the L stem and the pentagon, not 16002 (`research_branch.md` §3.5); a station piece shorter than the purlin width is dropped.

### 4.6 Builders (`grid.h`, all internal)

- `to_column(foot, head, plan, vertex, framing, datum_below, datum)`: `Column(axis, profiles.column, rotation)` with the profile x axis along the through member's direction at the head vertex (FAST+EPP: 315 along x); the axis over-length, `cuts` = the foot plane (deck top of the level below under node 0 and 1, the datum below under node 2, `z₀` on storey 0) and the top plane by `node` (section 5.3). For a square profile at a non-orthogonal node the section is the direction polygon at `compute_support` per direction, so members meet faces squarely at radial and hex nodes.
- `to_head(plan, vertex, framing, columns)`: `Block({bottom, top})` (wood_element_block.h:26), bottom = `compute_polygon(directions, centre, support per direction)` at the head bottom plane, top = the same polygon at `reach` on the head top plane; node 0 only, and only where a column arrives under a member or a deck.
- `to_beam(axis, role, cuts, framing, plan edge or station)`: `Beam(axis, profile of the role scaled by width / depth, {z})`, `cuts` from `compute_cuts` at both ends; plan edges and stations both go through it, a station's cuts being the exit faces of the member it remembered; a `profile_double` gives two beams offset by `gap / 2` with the same cuts; the element name is the role name (`girder`, `beam`, `purlin`, `edge_girder`, `edge_beam`, `brace`).
- `to_deck(plan, face, framing, columns)`: `Plate(bottom, top)` from loop 0 of `compute_outline`, then `features = {outline loops at the bottom plane, outline loops at the top plane}` when there are holes or notches (`Plate::features`, lofted by `compute_model_geometry`, `wood_element_plate.cpp:190`; `invalidate_geometry()` after assigning); `panel > 0` builds one plate per strip of `compute_panels`. A sheared notch under an inclined through column has the section at each plane.
- `to_wall(plan, edge, storey, framing, columns)`: `Plate::from_rectangle(origin, x_axis, y_axis, width, height, thickness)` (wood_element_plate.h:45) in the vertical plane of the edge over the storey, thickness centred (origin moved by `−wall / 2` along the normal), then `cuts` like a beam: the column faces at both ends, the head faces under node 0, the member bottom above (or the deck bottom when nothing runs there), the deck top below; a core wall walks its ring so each wall runs through at its far corner and butts at its near corner (pinwheel, section 5.6).
- `to_elements(framing, storey)`: working copies of plans k and k + 1 with roles filled; then in this order: columns of the storey, walls, heads of level k + 1, beams on role edges, stations, decks, braces of the storey; every element in world space, guids from the constructors, so `instance_by_key` dedups congruent ones (key = frame, profile, local cuts rounded to 3 decimals, `wood_instance.h`).
- `to_session(session, framing)`: `for storey < levels.size() − 1: group = session.add_group(fmt::format("storey_{}", storey)); for element : to_elements(framing, storey): session.add(element, group)`. That is the whole storey loop, and no example repeats it.

## 5. Joint rules

Two rules make every joint (`research_joints.md` §2, adopted whole). **Unequal pair:** the subordinate member is cut by the exit face(s) of the dominant member, the plane(s) of the dominant solid the subordinate's axis ray leaves through, normal flipped so the subordinate keeps its outside. **Equal pair:** both are cut by their bisector plane through the shared vertex (the perpendicular plane when collinear), one keeping each side. A plan cut is made only when the two members' elevation ranges overlap by more than `tolerance`; ranges that touch make a top / bottom contact and no cut. Every cut face is coplanar with a face of its neighbour, so `compute_contacts` finds it and the overlap volume is zero by construction.

### 5.1 Rank in plan (per vertex, highest through)

| Rank | Role | Note |
|---|---|---|
| 9 | core wall | everything stops on its outer face |
| 8 | column under node 1 or 2 | members butt into its faces; under node 0 the column is not in plan |
| 7 | edge girder, edge beam | the facade line stays continuous; interior members butt into it at any angle |
| 6 | girder | |
| 5 | beam (span −1, family −1, C's drawn lines) | equal beams mitre pairwise |
| 4 | purlin (cross-line rows and stations) | |
| 3 | deck | outline arithmetic, never cut in plan |
| 2 | facade wall | between column faces, under the member |
| 1 | brace | cut by whatever it reaches |

Ties within a rank: the member with a straight continuation within 45° runs through (the pair meets on its bisector, the perpendicular when collinear); then the smallest angle from x. The vertex attribute `through` overrides. A through member with no continuation and no partner is open-ended: cut by the plane perpendicular to it at the farthest end-face corner of the members butting into it, or at `reach` when nothing butts.

### 5.2 Layer in elevation (per level, datum z = framing top; t = deck, d = profile depth from `compute_size`)

| Layer | Member | Top | Bottom |
|---|---|---|---|
| 0 | deck | z + t | z |
| 1 | purlin, beam, edge beam, brace end | z | z − d |
| 2 | girder, edge girder | z − drop | z − drop − d |
| 3 | head (node 0) | the lowest layer-1 / 2 bottom at the vertex; z when only the deck arrives | top − head |
| 4 | column | node 0: the head bottom; node 1: z; node 2: z (end to end with the column above) | node 0, 1: the deck top of the level below (z_below + t), or z₀ on storey 0; node 2: z_below |

`drop` (per edge attribute, else `Framing.drop`) is the one number that selects the purlin joint: 0 flush (ranges overlap fully, the purlin is cut by the girder side, FAST+EPP), 0 < drop < d(purlin) hung (Branch 203.2, a partial-height contact), drop = d(purlin) stacked (ranges touch, no plan cut, the purlin runs over the girder and bears on its top). Edge beams sit in layer 1 and never drop, so a stacked purlin never clashes with the perimeter; edge girders drop with the girders.

### 5.3 Node modes

| `node` | Column top | Members at the vertex | Deck | Next column |
|---|---|---|---|---|
| 0 head | head bottom | bear on the flat head top; through / butt / mitre among themselves | on the member tops | stands on the deck top |
| 1 flush | z | every member whose range overlaps the column's and whose axis enters its footprint is cut by the column's exit faces; tops at z | over the column top and the member tops | stands on the deck top |
| 2 through | z, continuous | as node 1 | notched by the column section (`compute_outline`) | starts at z, end to end |

System 0 under node 0 is a head with no members (head top = z); under node 1 the column top meets the deck underside directly. Branch's Plate presets are system 0, edge 0.

### 5.4 Pair table

| Pair | Dominant | Cut | Contact that proves it |
|---|---|---|---|
| column ↔ level, node 0 | head | column top = head bottom plane; the next column starts on the deck top | column top on the head bottom |
| column ↔ level, node 1 | column | column top = z; members cut by the column's exit faces; deck over everything | member ends on the column faces; deck bottom on the column top |
| column ↔ level, node 2 | column | column z_below → z, end to end with the next; members cut by its faces; deck notched | member ends on the faces; notch sides on the faces; column ↔ column end faces |
| head ↔ member | head | none: the member bottom is the head top plane | member bottom on the head top |
| girder ↔ core wall | wall | cut by the wall's outer face; a piece shorter than its own width after the cut is dropped | girder end on the wall outer face |
| purlin ↔ girder, flush / hung | girder | cut by the girder side plane (ranges overlap) | purlin end on the girder side, full or partial height |
| purlin ↔ girder, stacked | none | none, ranges touch | purlin bottom on the girder top |
| purlin ↔ core | wall | the station is split at the hole ring; each piece cut by the wall's outer face | purlin end on the wall |
| member ↔ member, unequal rank | higher | exit face: the side plane, or the end plane when the ray leaves through the end region at a shallow angle | end on the side |
| member ↔ member, equal, collinear | none | perpendicular plane at the vertex | end to end |
| member ↔ member, equal, at an angle | none | bisector; three or more equal members mitre pairwise with their angular neighbours | end faces on the bisector |
| two subordinates adjacent in angle | the through member | both cut by it, then mitred against each other | as today |
| deck ↔ members | none | deck bottom = z, the member tops | deck bottom on the tops |
| deck ↔ deck | none | shared side on the vertical plane through the line; a re-entrant overhang mitres on the corner bisector | side faces coplanar |
| deck ↔ column (node 2) | column | outline minus the section | notch sides on the column faces |
| deck ↔ core | wall | outline minus the core outer ring (`compute_offset` by `wall / 2`) | hole sides on the walls' outer faces |
| deck at the boundary | edge member / column | the side moved onto the outer face of the edge member, or of the column when it reaches further out (FAST+EPP panels to the outer column faces) | deck side flush with the outer face |
| core wall ↔ core wall | the wall entering the corner | pinwheel: the leaving wall is cut by the entering wall's inner face; the entering wall runs to the leaving wall's outer face | leaving wall end on the entering wall's inner face |
| facade wall ↔ column / head / member / deck | column, head, member, deck | cut by the column faces at both ends, the head faces, the member bottom above (or the deck bottom), the deck top below | four contacts |
| brace ↔ anything | anything | cut at both ends by every member the ray leaves through: column sides, the deck top at the foot, the member bottom at the head | brace end faces on those faces |
| perimeter at a non-orthogonal angle | edge member | interior members cut by its inner face: oblique ends; the column section is the direction polygon so members meet its faces squarely | end on the inner face |
| tapered transition | as above | inclined column faces are planes: the same cuts; a sheared deck notch under node 2 | |

### 5.5 Worked cases (column 300², girder 200 × 600, beam 200 × 400, purlin 150 × 400, deck 200, wall 200, head 300, reach 400, z = 4000, tolerance 1)

**Interior node, two-way girders, node 0.** E / W girders through (smallest angle), N / S subordinate. E: bisector `x = 0` (normal +x), W mirror: end to end, contact 200 × 600. N: exit face of E / W along +y: `y = 100`, normal +y: contact 200 × 600 on the through girders' north side. Head: bottom 300² at 3100 (girder bottom 3400 − head 300), top 800² at 3400; every girder bottom near the node lies on it. Column: 300² from the deck top below up to 3100, `cuts = {z = 3100, −z}`. Decks: bottom at 4000 on the girder tops. Nothing overlaps: N / S occupy |x| ≤ 100, |y| ≥ 100; E / W occupy |y| ≤ 100.

**Same node, node 2.** Column from z_below to 4000 as a prism, `cuts` the two datum planes. E, W, N, S each cut by the column's exit face along its ray: `x = ±150` or `y = ±150`, normal outward: four 200 × 600 contacts on the column faces. Decks: `features` = outline minus the 150² quadrant at the corner: eight 150 × 200 deck ↔ column contacts round the node. No head.

**FAST+EPP v1 purlin into girder, node 1, drop 0.** Girder 265 wide on `y = 0`, purlin 215 × 456 at `x = 2250` running +y, tops at z. Ranges [z − 456, z] and [z − 608, z] overlap, so the plan rule applies: exit face `y = 132.5`, normal +y: the purlin runs `y 132.5 → 8867.5`, the reference's numbers; contact 215 × 456 inside the girder's 608. Girders: cut by the column faces `x = 157.5` (column 315 along x): `x 157.5 → 8842.5`; edge purlins by `y = 171`: `y 171 → 8829`. Hung (`drop` 203.2): girder [z − 811.2, z − 203.2], overlap 253: the same cut, contact 215 × 253. Stacked (`drop` 456): ranges touch, no plan cut, the purlin runs across and bears 215 × 265 on each girder top; the edge purlins in layer 1 run over the edge girders at the corner, so the corner column is cut by the girder-layer bottom.

**Radial ring node (radii 4000 / 8000 / 12000, 12 sectors, rays girders, chords beams).** N = (8000, 0). Rays: bisector `x = 8000`, end to end. Chord up (direction 105° from +x, 75° from the inward ray): exit face of the ray solid `y = 100`, met at t = 100 / sin 75° = 103.5 from N; end face 200 / sin 75° = 207 wide, 400 high, straddling `x = 8000`: contacts 131 × 400 and 76 × 400 with the two rays. Head: octagon (four directions and their opposites) at the support distances and at 400. Outer ring node (12000, 0): the chords are edge beams (rank 7), equal and adjacent: both cut by the vertical plane along the ray direction (their bisector), contact 200 / cos 15° = 207 × 400; the ray (rank 6) exits the union of the two chords through the inner corner where both inner faces meet within tolerance, so it receives both inner face planes: an arrow end with two 103.5 × 600 faces. No `reach` anywhere.

**Hex node, three beams at 120°, span −1.** All three are rank 5 with no continuation: pairwise bisectors at 150°, 270°, 30°; each beam ends in a V with its tip at N; three mitre faces of 100 / sin 60° = 115.5 × 400. With one of them a girder (family 0 span): it is through, its open end is the plane perpendicular to it at the farthest butting corner (`y = 57.7`), the other two are cut by its sides (`x = ±100`) with 231 × 400 contacts.

**Deck round a core.** Bay [0, 6000]², core ring (2000, 2000) → (4000, 4000) held back (it crosses no line), walls 200 centred: outer ring [1900, 4100]². `features = {[outline, hole [1900, 4100]²] at z, the same at z + 200}`: four 2200 × 200 hole-side contacts on the walls' outer faces. Purlin station at `x = 3000` split into (3000, 0 → 1900) and (3000, 4100 → 6000), each cut by the wall's outer face plane: two 150 × 400 contacts. Girders on core lines are cut at the outer faces and dropped when shorter than 200.

**Core corner, pinwheel.** W0 (2000, 2000) → (4000, 2000), W1 (4000, 2000) → (4000, 4000). At (4000, 2000) W0 enters, W1 leaves: W0's open end runs to W1's outer face `x = 4100`; W1 is cut by W0's inner face `y = 2100` (normal +y). Contact 200 × storey height. Every wall is 2200 long, all four congruent, one instance definition. The deck hole corner (4100, 1900) is W0's outer end corner, so the deck touches both walls with no gap.

**Tapered perimeter (A).** Levels 3600 and 7200, the east edge moving from `x = 12000` to `x = 11400` (9.46°). P1 = (12000, 6000) and P2 = (11400, 6000) share `(line_a, line_b)` (the y = 6000 pattern line and east ring edge), so the column is `Column(Line(P1', P2'), profile)` over-length, cut by the deck top plane at level 1 (node 0 / 1) and by the head bottom (or `z = 7200` under node 1, 2). The level-2 edge member sits on the inclined column's head (horizontal polygons about the axis at each elevation); under node 1 the interior girder is cut by the column's inclined west face, an end tilted 9.46°. The facade wall under the level-2 edge member is `Plate::from_rectangle` in the inclined plane through P1, P2 and the edge direction, cut by the two inclined column faces, the member bottom and the deck top. A vertex past `taper` has no partner: no column, `column` 2, the edge member spans between its neighbours.

**Setback (A).** Podium `S_1⁻` ⊃ tower `S_1⁺` at level 1: the plan fills the union, the deck covers it (a terrace over the podium ring), `C_0 = S_0⁺ ∩ S_1⁻` = the podium and `C_1 = S_1⁺ ∩ S_2⁻` = the tower ring, added as lines to plans 1 and 2, so every tower column foot is a vertex of plan 1 with `(line_a, line_b)` = (pattern line, tower ring edge) on both, hence vertical columns standing on the podium roof deck (node 0 / 1) or through it (node 2). A tower edge that falls mid-bay on the podium is still a ring line of plan 1: its crossings with the pattern are column points sitting on the podium girders' line, so the columns below are found by rule 1 and the podium deck carries them; nothing is a transfer unless the tower overhangs the podium.

## 6. Clash check

`compute_overlap(convex, other, tolerance)`: `part = other; for plane in compute_planes(convex): part = part.cut_by_plane(Plane::from_point_normal(plane.origin() − plane.z_axis() · tolerance, −plane.z_axis())); return part.face_count() == 0 ? 0 : part.volume()`. Pulling every half-space in by `tolerance` makes the test binary: two solids sharing a face give an empty part, any interpenetration deeper than `tolerance` a positive volume (`cut_by_plane` snaps distances below `1e-9 × diagonal` onto the plane, mesh.cpp:4776, so a face on the plane survives whole). Column, one-segment Beam and Block are convex; a Plate with holes, notches or a concave outline is the disjoint union of triangle prisms from its cap triangulation extruded between its two planes, and the overlap is the sum over prisms (exact, the prisms do not overlap); two plates meet only on vertical side planes, so either side can be the prism side.

`compute_clashes(session, tolerance)`: broad phase over `Element::aabb(inflate)` pairs (the search `compute_contacts` already uses), narrow phase `compute_overlap` with the convex one as `convex`, output sorted by volume descending so the first line names the worst joint. Cost: 6–10 faces per beam mesh, microseconds per clip, well under a second for 10 000 members.

`wood/tests/wood_grid_test.cpp` (registered like `wood_instance_test`) builds every example's building and asserts: (1) element counts per role per storey against section 8; (2) `compute_clashes(session, 1.0).empty()`; (3) after `compute_contacts(0)` every element has at least one `ContactFace` except a ground column's foot; (4) every pair the rules cut has a contact polygon above `tolerance²`; (5) every subordinate end contact equals the subordinate's end-face area within tolerance, or the pair is listed as partial bearing (a warning, silenced for hung purlins where the elevation overlap is less than the purlin depth); (6) `1_elements_tree` gives 5 definitions after `instance_by_key`, and the Branch square gives one definition per congruent girder, purlin, deck and core wall; (7) the member lists of section 9.

## 7. Profiles

`wood_profile.{h,cpp}` as 1.5. `Profiles` picks one per role with the fallbacks in its comments; per-edge `width` / `depth` scale it. The elevation table reads `d` from `compute_size`, never from a square side. The head bottom is the direction polygon at `compute_support(profiles.column, direction)` per direction, so a W8X31 (`profile_w(206, 210, 14.2, 10.2)`), an HSS (`profile_hss(178, 178, 12.7)`) and a round column (`profile_round(360)`) all get a head that circumscribes them; a round column's exit face is one facet (known approximation). `profile_double` builds two members with the same cuts. Checks per profile (E5): the swept member is closed, mesh and BRep volumes equal area × length with holes subtracted, cuts close the solid, contacts land on the correct faces. Everything runs on the square fallback until E2 / E3 land, so the profile work can go in parallel with the template.

## 8. Examples

Every example: CAPS consts, an 8-line `main`, `INSTANCES` (`if constexpr (INSTANCES) wood_session.instance_by_key();`), `compute_contacts(0)` (a column touches the deck of the storey below), `pb_dump(pb_path("live").string())`, the `|||||||| DESCRIPTION ||||||||` usage block, no colours. `X = Vector(1, 0, 0)`, `Y = Vector(0, 1, 0)`. Counts are per level unless stated; targets come from `research_branch.md` §3 and the captures and are asserted by the test together with 0 clashes; a count marked † is fixed by the test on its first green run.

The three `main`s (everything else differs only in the consts):

```cpp
int main() {

    WoodSession wood_session("templates_grid_residential");
    wood_grid::Building::from_footprint(FOOTPRINT, ELEVATIONS, wood_grid::Pattern::orthogonal(XS, YS), CORES).to_session(wood_session, FRAMING);

    if constexpr (INSTANCES)
        wood_session.instance_by_key();

    wood_session.compute_contacts(0);
    wood_session.pb_dump(pb_path("live").string());

    return 0;
}
```

A: `wood_grid::Building::from_solid(Mesh::loft({BOTTOM}, {TOP}), ELEVATIONS, PATTERN).to_session(wood_session, FRAMING);` (`Mesh::loft`, mesh.h:357; or `Mesh::create_box` joined through `Mesh::from_polylines` of both shells' faces; a `BRep` goes in as is). C: `const Session input = Session::pb_load(data_path(INPUT + "_input.pb").string());` then `lines` from `input.select_by_type<Polyline>()` two-point polylines and `surfaces` from the four-point ones (the crea `.pb` files hold lines as two-point polylines and floors, walls and cores as quads named by layer; the four files move from `reference/crea/pb/` to `wood/data/crea/`), then `wood_grid::Building::from_lines(lines, surfaces).to_session(wood_session, FRAMING);`. `1_elements_tree` keeps its own loop: three `from_footprint` buildings translated by `Pattern::transformed`, one `bay_i` group each from `to_elements(FRAMING, 0)`, `compute_contacts(1)`.

GLULAM = `Profiles{.column = profile_rectangle(360, 360), .girder = profile_rectangle(320, 800), .purlin = profile_rectangle(260, 640), .edge_girder = profile_rectangle(300, 720), .edge_beam = profile_rectangle(260, 600)}` (Branch's reference sections). FASTEPP1 = `Profiles{.column = profile_rectangle(315, 342), .girder = profile_rectangle(265, 608), .purlin = profile_rectangle(215, 456)}`.

| # | File | Workflow | Exact parameters | Expected |
|---|---|---|---|---|
| 1 | `1_elements_flat` | B | footprint `{Polyline::rectangle(Point(0, 0, 0), X, Y, 4000, 3000)}`, `ELEVATIONS {0, 3700}`, `orthogonal({4000}, {3000})`, `Framing{.system = 1, .span = 0, .node = 0, .deck = 200, .head = 300, .reach = 200, .profiles = {.column = rect(200, 200), .girder = rect(200, 200)}}` | 4 columns, 4 heads, 2 girders through (x sides), 2 edge beams butting, 1 deck; 20 contacts as today |
| 2 | `1_elements_tree` | B | three of #1 at `Xform::translation(i · (4000 + 2 · 200 + 2000), 0, 0)`, groups `bay_i`, `compute_contacts(1)` | 3 × (4, 4, 4, 1); 5 definitions under `INSTANCES` (the instance test) |
| 3 | `templates_grid` | B | today's L: `XS {9140, 8530, 9140}`, `YS {7600, 7600}`, footprint `(0,0) (26810,0) (26810,7600) (17670,7600) (17670,15200) (0,15200)`, `ELEVATIONS {0, 4500, 8300, 12100}`, `Framing{.system = 2, .span = 0, .spacing = 3000, .node = 0, .facade = true, .deck = 175, .wall = 175, .profiles = {.column = rect(365, 365), .girder = rect(365, 365), .purlin = rect(265, 265)}}` | 10 columns, 10 heads, 3 girders (y = 7600), 8 edge members, 2 cross-line purlins (x = 9140, 17670 interior pieces), 12 stations (2 per 9140 bay, 2 per 8530 bay, from the unclipped cells), 5 decks, 8 facade walls per storey |
| 4 | `templates_grid_radial` | B | `radial({4000, 8000, 12000}, 12)`, empty footprint, `ELEVATIONS {0, 4000, 8000}`, `Framing{.system = 1, .span = 0, .node = 0, .profiles = {.column = rect(240, 240), .girder = rect(240, 240)}}`; `RADII_CENTRE` const variant `{0, 4000, 8000}` for a centre node and triangles | 36 columns, 36 heads, 24 ray girders, 12 inner chords as edge beams (the inner ring is a boundary of the empty-footprint plan) + 12 outer chords mitred, 12 middle chords role 0 under system 1 (cross family): set `.span = -1` in a second const for a full ring grid; 24 decks |
| 5 | `templates_grid_hex` | B | `hexagonal(4000, 3, 2)`, empty footprint, `ELEVATIONS {0, 4000, 7600}`, `Framing{.span = -1, .node = 0}` | 6 hexagonal decks, every interior vertex three equal beams in V mitres, hexagon heads; boundary edges are edge beams |
| 6 | `templates_grid_triangular` | B | `triangular(6000, 4, 3)`, empty footprint, `ELEVATIONS {0, 4000}`, `Framing{.system = 1, .span = 0, .node = 0}`; `SPAN` const −1 for the full triangular beam grid | 20 columns, 24 triangular decks; span 0: girders on family 0 only, boundary edges as edge members; span −1: every side a beam, three-way heads |
| 7 | `templates_grid_skewed` | B | `orthogonal({6000 ×4}, {6000 ×3}, 30)`, footprint the skewed parallelogram, `ELEVATIONS {0, 4000, 8000}`, `Framing{.system = 2, .span = 0, .spacing = 2500, .node = 1}` | 20 columns; oblique butts against rectangular columns (exit faces), purlins parallel to the skewed cross lines; 12 decks |
| 8 | `templates_grid_branch_square` | B | Branch (a) / (b) / (c) by a `SYSTEM` const: 18288², `orthogonal(compute_bays(18288, 4572), compute_bays(18288, 4572))`, `ELEVATIONS {0, 3657.6, 7315.2}`, `.deck = 189.8`, `.node = 2`; (a) system 1 span 0, girder rect(220, 520), edge_girder rect(220, 440), edge_beam rect(220, 280); (b) system 2 span 1 spacing 3048 drop 203.2, girder rect(220, 520), purlin rect(220, 400); (c) system 0 edge 0 node 0 head 300 reach 600, deck 365.1, panel 3505.2 (a point supported deck needs a bearing: `to_elements` reads node 2 as 1 under system 0) | (a) 25 columns (16 boundary), 12 girders on y = 4572, 9144, 13716, 16 edge members, 16 decks; (b) 12 girders on x = 4572 …, 8 edge girders, 8 edge beams, 28 purlins in rows y = 2286 … 16002 (station 0 on the cross lines are role-3 edges: 12 more), 16 decks; (c) 25 columns, 25 heads, 0 members, 32 deck strips per storey: two equal 2286 strips per 4572 bay, `compute_panels` counting strips as `compute_bays` does (one 3505.2 panel plus a 1066.8 rest) |
| 9 | `templates_grid_branch_residential` | B | Branch (d): footprint `(0,0) (21945.6,0) (21945.6,45720) (43891.2,45720) (43891.2,67056) (0,67056)`, `XS = compute_bays(43891.2, 9144)` = `{9144 ×4, 7315.2}`, `YS = compute_bays(67056, 9144)` = `{9144 ×7, 3048}`, `CORES {Polyline::rectangle(Point(7467.6, 19354.8, 0), X, Y, 7010.4, 7010.4)}`, `ELEVATIONS {0, 3657.6, 7315.2, 10972.8}` (three of twelve storeys), `Framing{.system = 2, .span = 1, .spacing = 3048, .node = 2, .drop = 203.2, .deck = 189.8, .wall = 250, .profiles = GLULAM}` | 45 columns (no crossing inside the core), 23 girders running Y with two 1066.8 core stubs (18288 → 19354.8 and 26365.2 → 27432 on x = 9144, kept: longer than 320), 27 edge members, 77 purlin pieces (Branch's 75 rows, the two rows y = 21336 and 24384 through the core split at its walls), 4 core walls per storey (pinwheel, one definition), decks per bay with a hole where the core sits inside a bay; girder tops z − 203.2; 540 columns over 12 storeys; 0 clashes against Branch's overlaps |
| 10 | `templates_grid_branch_office` | B | Branch framing sweep, `VARIANT` const: 45720 × 54864, cores `rectangle(Point(15240, 27432, 0), X, Y, 9144, 9144)` and `rectangle(Point(18288, 14020.8, 0), X, Y, 6096, 3048)`, `ELEVATIONS {0, 4267.2, 8534.4, 12801.6}` (three of six storeys), `.node = 2`, `.deck = 241.8`; 0: `XS = compute_bays(45720, 9144)`, `YS = compute_bays(54864, 6096)`, system 1, span 0, girder rect(320, 720); 1: the same, system 2, spacing 3048, drop 203.2, purlin rect(240, 520); 2: `YS = compute_bays(54864, 9144)`, system 2, span 1, spacing 3048, purlin rect(260, 640); 3: as 2 with spacing 6096 | 58 columns in every variant (60 crossings minus (18288, 30480) and (18288, 36576) inside or on core 1); 0: 40 girders (four core-supported: y = 30480 and 36576 pieces 9144 → 15240 and 24384 → 27432), 28 edge members; 1: 40 girders, 126 purlins; 2: 36 girders, 85 purlins; 3: 36 girders, 40 purlins on the cross lines (two-way); 8 core walls per storey |
| 11 | `templates_grid_branch_institutional` | B | Branch T9: U `(0,0) (45720,0) (45720,21336) (18288,21336) (18288,48768) (45720,48768) (45720,70104) (0,70104)`, `XS = compute_bays(45720, 9144)`, `YS = compute_bays(70104, 9144)` = `{9144 ×7, 6096}`, cores `rectangle(Point(12192, 48768, 0), X, Y, 6096, 9144)` (a notch on the courtyard's inner corner) and `rectangle(Point(15240, 15240, 0), X, Y, 3048, 6096)`, `ELEVATIONS {0, 4876.8, 9753.6, 14630.4}` (three of eight storeys), `Framing{.system = 2, .span = 1, .spacing = 3048, .node = 2, .drop = 203.2, .profiles = GLULAM}` | 49 columns (32 boundary), 24 girders, 34 edge members, 80 purlins; the notch core gives a deck notch, not a hole |
| 12 | `templates_grid_point_supported` | B | Branch T1: `(0,0) (21031.2,0) (21031.2,45720) (42062.4,45720) (42062.4,67056) (0,67056)`, `XS = compute_bays(42062.4, 3505.2)` (12), `YS = compute_bays(67056, 4572)` (14 + 3048), cores `rectangle(Point(14935.2, 45720, 0), X, Y, 6096, 9144)` and `rectangle(Point(11582.4, 9144, 0), X, Y, 3048, 6096)`, `ELEVATIONS {0, 3657.6, 7315.2, 10972.8}` (three of twelve storeys), `Framing{.system = 0, .span = 1, .edge = 0, .node = 0, .deck = 291.4, .panel = 3505.2, .head = 300, .reach = 600}` (under system 0 `span` is the family the deck strips run along) | 140 columns (53 boundary), 140 heads, 0 members, deck strips 3505.2 wide running along the y lines, one per bay, their joints on the column lines, 8 core walls; a pattern line hugging a core (x = 24536.4 beside core A of the office point supported case) leaves no sliver plate: `compute_slivers` joins a floor face narrower than the wall into its neighbour |
| 13 | `templates_grid_pentagon` | B | Branch P19: `(0,0) (13716,13716) (36576,13716) (36576,27432) (0,27432)`, `orthogonal(compute_bays(36576, 9144), compute_bays(27432, 9144))`, `ELEVATIONS {0, 3657.6, 7315.2, 10972.8}`, `Framing{.system = 2, .span = 1, .spacing = 3048, .node = 2, .drop = 203.2, .profiles = GLULAM}` | 17 columns (the exact vertex included), 6 girders, 14 edge members, 21 purlins (two at x = 15240 from the unclipped cell); oblique cuts on the diagonal edge |
| 14 | `templates_grid_courtyard` | B | rings `{outer (0,0) (36576,0) (36576,27432) (0,27432) counter-clockwise, hole (12192,9144) (24384,9144) (24384,18288) (12192,18288) clockwise}`, `orthogonal(compute_bays(36576, 9144), compute_bays(27432, 9144))`, `ELEVATIONS {0, 3657.6, 7315.2, 10972.8}`, `Framing{.system = 1, .span = 0, .node = 2, .facade = true}` | 20 columns (the 4 hole vertices coincide with crossings), edge members on the hole ring too, 8 decks, facade walls on both rings |
| 15 | `templates_grid_fastepp` | B | `VARIANT` 0..3: v1 `orthogonal({9000}, {9000})`, `ELEVATIONS {0, 4500}`, `Framing{.system = 2, .span = 0, .spacing = 2250, .node = 1, .drop = 0, .deck = 87, .panel = 3114, .profiles = FASTEPP1}` (edge_beam falls back to purlin); v2 `({6000}, {12000})`, spacing 1500, column rect(265, 380), girder rect(265, 532), purlin rect(215, 532), panel 3095; v3 `({6000}, {9000})`, system 1, span 1, edge 1, edge_beam rect(215, 836), deck 243, panel 3126.67, plus `set_edge_attribute` role 0 on the two y-side ring edges (documented: FAST+EPP draws nothing there); v4 `({8000}, {12000})`, spacing 1333.33, column rect(365, 418), girder rect(265, 684), purlin rect(215, 494), panel 3104.5 | v1: 4 columns z −4500 → 0, 2 girders x 157.5 → 8842.5, 2 edge purlins y 171 → 8829, 3 purlins y 132.5 → 8867.5 at x = 2250, 4500, 6750, 3 strips over x −157.5 → 9157.5 in bands from y −171: the 12 boxes of `members.json` to the millimetre; v3: 4 columns, 2 beams on x = 0 and 6000, 3 strips spanning 6000; 0 clashes in all four |
| 16 | `templates_grid_framings` | B | three 9000² purlin bays in a row (`Pattern::transformed`, three buildings, one group each as #2): `DROP` = 0 flush, 203.2 hung, 640 stacked, purlin rect(260, 640), girder rect(320, 800), node 1 | purlin ↔ girder contacts: side, full depth / side, 437 high / bottom on top; 0 clashes in all three |
| 17 | `templates_grid_profiles` | B | seven 6000² purlin bays in a row, spacing 2000, node 1, bay i: girders `profile_rectangle(265, 608)` / `profile_round(300)` / `profile_w(250, 250, 15, 10)` / `profile_hss(250, 250, 10)` / `profile_double(120, 600, 60)` / `profile_slab_band(1200, 300)` / `profile_t(300, 500, 100, 80)` with a matching column (`profile_w(206, 210, 14.2, 10.2)` W8X31, `profile_hss(178, 178, 12.7)`, `profile_round(360)` among them) | 28 columns, 14 girders (+ 7 for the double bay), 14 edge purlins, 14 purlins, 7 decks; every solid closed, volume = area × length; 0 clashes |
| 18 | `templates_grid_solid_taper` | A | `BOTTOM = Polyline::rectangle(Point(0, 0, 0), X, Y, 30000, 20000)`, `TOP = Polyline::rectangle(Point(1500, 1500, 14400), X, Y, 27000, 17000)`, `Mesh::loft({BOTTOM}, {TOP})`, `ELEVATIONS {0, 3600, 7200, 10800, 14400}`, `orthogonal(compute_bays(30000, 6000), compute_bays(20000, 5000))`, `Framing{.system = 2, .span = 0, .spacing = 3000, .node = 0, .taper = 30}` | per storey 12 interior columns vertical, 18 perimeter columns inclined (5.9° on the sides, 8.4° at the corners) matched by identity, 0 transfers; `taper` 5 flags all 18 as `column` 2; decks and edge members on each level's own section |
| 19 | `templates_grid_solid_setback` | A | podium `Mesh::create_box(40000, 30000, 8000)` and tower `create_box(20000, 20000, 14400)` moved to (10000, 5000, 8000), joined as one mesh (`Mesh::from_polylines` of both shells' face polygons; the shared roof / floor square is a coplanar internal face and is removed first), `ELEVATIONS {0, 4000, 8000, 11600, 15200, 18800, 22400}`, `orthogonal(compute_bays(40000, 5000), compute_bays(30000, 5000))`, `Framing{.system = 1, .span = 1, .node = 1}` | level 2: 63 columns below, 25 above standing on the podium roof deck (identity through the `C_1` ring), terrace deck over the podium ring; decks 48 then 16; 0 transfers |
| 20 | `templates_grid_solid_atrium` | A | box 36000 × 36000 × 20000 with a through hole 12000² centred (`BRep::create_block_with_hole` style through `Block({outer, outer_top, hole, hole_top}).element_geometry(true)`, or a loft), `ELEVATIONS (0, 4000 … 20000)`, `orthogonal(compute_bays(36000, 6000), compute_bays(36000, 6000))`, `Framing{.system = 2, .span = 0, .spacing = 3000, .node = 2}` | 49 − 1 = 48 columns (the centre crossing is in the hole); the atrium ring in the arrangement: 8 columns and 8 edge members round it; every deck at a column notched 150²; 0 clashes |
| 21 | `templates_grid_solid_curved` | A | `BRep` cylinder radius 15000, height 15200, `facet` 22.5 (16 facets), `ELEVATIONS (0, 3800, 7600, 11400, 15200)`, `radial({5000, 10000, 15000}, 16)`, `Framing{.system = 2, .span = 0, .spacing = 2500, .node = 0}` | 16 facet corners = 16 perimeter columns + 32 interior + the inner ring; edge members mitred at 22.5°; rays through, chords as cross purlins |
| 22 | `templates_grid_crea` | C | `INPUT` const over `crea_4x4`, `crea_4x4_ground`, `crea_4x4_beams_without_column`, `crea_full`; `Framing{.system = 1, .span = -1, .node = 0, .deck = 200, .wall = 200, .head = 300, .reach = 360, .profiles = {.column = rect(300, 300), .girder = rect(300, 300)}}` | 4x4: 16 columns, 16 heads, 20 beams, 6 decks, 12 walls (8 facade, 4 core) that compas drops; beam ends on head tops and on each other's sides; ground: + 3 ground decks, no ground beams; beams_without_column: 17 columns, the two beam ends at (12000, 24000, 7600) open and their vertex `column` 2; full: 340 columns, 340 heads, 539 beams (549 drawn lines minus 10 duplicates; compas's 94 floor-edge and 54 ground beams not built), 248 decks, 256 walls, the 40 core-centre ends `column` 2; 0 clashes |
| 23 | `templates_grid_braced` | C | hand `Line` consts: 2 × 2 bays of 6000, 2 storeys of 3800, X braces in the two end bays, 8 floor quads, `Framing{.span = -1, .node = 1}` | 18 columns, 24 beams, 8 decks, 8 braces cut by the column faces, the deck top and the beam bottom |

Minimum set for the pass, in build order: 1, 2, 3, 4, 5, 8, 9, 10, 13, 15, 16, 19, 22 (thirteen). The rest are one-line parameter changes of those and are added as the comparison pages need them.

Side-by-side pairs for `wood/docs/templates.md` (rendered with `INSTANCES = false`, the reference models stripped of colour): #8 against `reference/branch3d/{a_beam_x, b_purlin_y, c_plate_x}` (`plan_framing`, `iso_framing`); #9 against `d_residential_l_purlin` (`plan_core_zoom_*`); #10 against `reference/branch3d_framing/{beam_clt_spanX, purlin_clt_spanX_10ft, purlin_clt_spanY_10ft, purlin_clt_spanY_20ft}`; #11 and #12 against `reference/branch3d_topologies/*`; #15 against `reference/fastepp/v*/members.json` and the `shots/v1_*` renders; #22 against `reference/crea/pb/crea_4x4_compas.pb` and `png/crea_4x4_node_detail_front_f`.

## 9. Verification loop

1. **Counts and clashes** in `wood_grid_test.cpp` (section 6), one case per example in the minimum set, run through `tools/run_guarded.sh`.
2. **Member lists, not pixels.** A small python beside the shots pipeline (`scratchpad/shots/compare_members.py`, later `wood/tools/`) reads our `live.pb` through `session_py` and lists every Column / Beam / Plate as (role, start, end, width, depth, top z, bottom z), then diffs against: Branch's level-0 members (`reference/branch3d*/*.json`: `start_mm` / `end_mm`, sections, `top`) with the known deltas applied (Branch beams run centre to centre and are not cut; ours end on faces; Branch's 3.05 render offset; purlins through cores split; stubs); FAST+EPP `members.json` boxes to the millimetre with no translation (datum = framing top = 0 in both); crea's `oracle_compas.json` counts per level plus the walls compas drops. The diff reports per role: count, missing, extra, and the largest end-point delta; the acceptance is count equality and end deltas explained by the delta list.
3. **Contacts.** `compute_contacts(0)` on every scene; rules (3)–(5) of section 6.
4. **Instancing.** `INSTANCES = true` on #2, #8 and #9: definition counts asserted (5 for the tree; one per congruent girder, purlin, deck, core wall for the square and the L).
5. **Screenshots** through the shots pipeline for every example in the minimum set and the pairs of section 8, shown to petras in the chat and placed in `wood/docs/templates.md` with the consts and the `main`.
6. Loop until every case is green; a failing joint is fixed in the rule (`grid_joints.h`), never in a builder or an example.

## 10. Proposed kernel helpers (later, three-kernel parity, listed for wood-research-60; nothing under `session/` moves now)

| Wood now (`plan.h` / `clash.h`) | Kernel later | Why |
|---|---|---|
| `compute_section` | `Mesh::section_by_plane(const Plane&) → std::vector<std::vector<Polyline>>` (outer + holes per region), `BRep::section_by_plane` (planar exact, curved through the tessellation) | the cap extraction of `cut_by_plane`, exposed; the docstring should state the cap winding and the snap tolerance |
| `compute_regions`, `compute_offset` | `Polyline::boolean_op` backed by Clipper2 returning regions with holes; `Polyline::offset(distance)` with holes via `InflatePaths` | the Vatti path drops holes and fails on shared collinear edges (`research_inputs.md` §1) |
| `compute_crossings` | `Line::split_at_crossings(lines, tolerance)` or `Mesh::from_lines(lines, delete_boundary_face, precision, split_crossings)` | `from_lines` welds endpoints only |
| `compute_arrangement` provenance | `Mesh::from_lines` keeping a source index per edge | one map |
| station edges | `Mesh::split_edge(u, v, point)` and an edge chain across a face | would make purlin stations real plan edges with per-purlin overrides |
| `compute_planes`, `compute_overlap` | `Mesh::face_planes()`, `Mesh::is_convex()`, `Mesh::compute_overlap(const Mesh& convex, double tolerance)` | once the wood version has run on every example |
| `compute_polygon` | `Polyline::from_planes` or `Intersection` fan (chevron.h has `polygon_from_planes`) | the direction polygon is general |
| per-side offset in `compute_outline` | `Polyline::offset(const std::vector<double>&)` | the mitre formula is general |
| Newell normal | `Polyline::normal()` public (the private `average_normal`) | one line |
| `compute_bisector`, `compute_exit` | not worth a kernel slot | six lines each |
| **bug** | `Polyline::closest_distance_and_point` never clamps `t` (polyline.cpp:542): it returns the distance to the infinite line; callers `wood_contact_detection.cpp:300`, `wood_assignment.cpp:15`, `polyline_test.cpp:322` | clamp to [0, 1]; wood uses `Closest::line_point` / `polyline_point` meanwhile |

Stays in wood for good: `Pattern`, `Framing`, `Profiles`, `Level`, `Building`, roles, columns, stations, cuts, outlines, builders, `wood_profile`, the clash test.

## 11. Risks and open points

1. **Mesh attributes versus "kernel Graph attributes"** (brief §5): same kernel API, different type; confirm with petras before the first commit; `to_graph()` is a one-function fallback.
2. **`Mesh::from_lines` with partially overlapping collinear lines** is unverified (only exact duplicates were probed); `compute_crossings` merges overlaps with `Polyline::line_line_overlap` first.
3. **Slivers**: a pattern line within `tolerance` of a section vertex leaves a sliver face; the `merge` weld and the `tolerance²` area filter guard it, untested on adversarial input.
4. **Ring edge ids across levels** are stable for a prism, a loft and a tapered solid (the cap rings come from the same faces in the same order); undefined across a setback, where the `C_k` rings and rule 2 / 3 of 4.3 apply by design.
5. **Exit through a corner**: a member wider than the column it butts into is clipped by the column's side planes too; reported as partial bearing, not fixed. Round profiles end on one facet.
6. **Coplanarity for contacts**: the rules make faces exactly coplanar; `transformed` round trips keep them within 1e-12; the instancing test compares contact polygons within tolerance.
7. **Full crea** (889 lines, 340 columns): the O(n²) split per level and the O(N²) `instance_by_key` are estimated under a second, not measured; measure on the first run.
8. **Purlins over the unclipped cell** move two purlins in the L and pentagon against today's clipped stations; the test tables use Branch's positions.
9. **Branch quirks deliberately not copied**: purlins through cores (split here: #9 gives 77, not 75), 3 mm stubs, strips from `min + 3 mm` with a sliver, the `|| 0` tributary, the "both ends boundary" drop, columns through decks; FAST+EPP v3's missing y-side beams are two per-edge overrides, not a mode.
10. **Roof volume above the last elevation** (pitched roofs) is ignored; the last level is a flat roof deck.
11. **Trimmers** for an open hole inside one bay are not built; the deck keeps the bay through `face_holes` and the hole has no members; listed as the next structural refinement.
12. **Grouping by storey** puts level k + 1's horizontal members with storey k's columns; `compute_contacts(0)` over the whole scene stays for that reason.

## 12. Build and verify (machine rules)

```
cd /home/petras/code/code_cpp/wood_research/wood
buildslot timeout 10m systemd-run --user --scope -p MemoryMax=6G cmake --build build --parallel 4 --target templates_grid
tools/run_guarded.sh -t 3 -m 3 -- build/templates_grid
buildslot timeout 10m systemd-run --user --scope -p MemoryMax=6G -E MINITEST_JOBS=4 cmake --build build --parallel 4 --target wood_grid_test
tools/run_guarded.sh -t 3 -m 3 -- build/wood_grid_test
```

One target at a time, never more than `--parallel 4`; screenshots through `browserslot` and the shots pipeline (`serve.py`, a `viewer/scenes/<name>.yaml` like `proto.yaml`, the pb copied to `viewer/pb/`, `shot.cjs`) with `INSTANCES = false`. No `git add / commit / push / stash / reset` from the builder sessions; nothing under `session/` is touched.
