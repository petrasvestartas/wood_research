# Grid lean critique (2026-09-25)

What the grid template at wood `451299f` carries that does no work, measured against
`fable_brief.md`. Core 3,466 lines over seven files, 24 `templates_grid_*` examples of 1,190 lines.

## Duplicated or over-general

- **Three parallel geometry idioms for one job.** `grid_plan.cpp` hand-rolls ring booleans
  (`compute_regions` over Clipper2), a per-side mitre offset (`compute_offset`), and then
  `grid_joints.cpp` re-derives deck corners by cases (`compute_deck_corner`, `compute_partner`,
  `is_core_corner`: five branches, 60 lines) to avoid the overlap Clipper resolves in one call.
  One Clipper difference per deck (minus the earlier decks, the column notches and the core wall
  quads) replaces all of it.
- **Two weld systems.** `compute_crossings` welds stops in four priority orders with two radii
  (`tolerance`, `merge`), then `Mesh::from_lines` welds again at `tolerance / 10`. One greedy weld
  in ring-first order is enough; the core-ring special case (`is_on_core`, order 3) exists for one
  Branch preset whose core corner sits 1 m from a crossing.
- **Purlin stations carry a `Support` record** (kind, edge, along, t) plus `compute_landing`,
  `compute_corner_vertex`, `compute_station_half`, `compute_station_cuts` (130 + 55 lines) to decide
  one plane per end: the exit face of whatever stands on the side the station lands on.
- **`is_covered` / `compute_overhang` / `compute_run`** (90 lines) detect a member wider than the
  column it butts into and mitre the corner. The general rule (every member cut by its supports,
  the through member's sides and the bisectors with its equal neighbours) already leaves no
  overlap there; the special case buys a nicer corner on the W and HSS profile bays only.
- **`compute_slivers`, `compute_joined`, `compute_far_face`, `compute_merged`** (110 lines) merge a
  floor face narrower than a wall into its neighbour, for one core in one Branch preset that sits
  off the pattern lines.
- **`compute_start` / `compute_started`** (40 lines) rotate a corner head's loops so rotated copies
  hash alike for `instance_by_key`; instancing is deferred and the key can canonicalise later.
- **`compute_resampled` / `compute_anchors`** (70 lines) drop facet corners of a curved section so
  columns stand on the rays; picking a facet that matches the sectors gives the same plan.
- **`compute_cell`** stations purlins over the unclipped pattern cell to hit Branch's numbers in
  clipped bays; stationing over the bay is what a user expects and 25 lines shorter.
- **`Context` holds three column maps** (`columns`, `through`, `feet`) built three ways in
  `to_elements`; two (the columns standing in the storey and the ones rising from the level) say
  everything, the node mode picks which cut, notch or reach.

## Types, fields and functions carrying no weight

- `Level.rings` is written by every constructor and read by none of the builders.
- `Building.pattern` exists only for `compute_cell` and `compute_edge_family`; the plan edges
  already carry `family`.
- `Profiles.edge_girder` / `edge_beam` and roles 4 / 5: a perimeter member is a girder, beam or
  purlin on the perimeter; one `boundary` bit and one shared rank say so.
- `Framing.edge`: system 0 (plate on columns) has no members; that is the only use.
- Edge attributes `width`, `depth`, `drop`, face attributes `spacing`, `thickness`, vertex
  attribute `through`: per-member overrides no example sets.
- `compute_planes` (grid_plan) is dead since `clash.h` went; `is_level`, `compute_interior`
  (30 lines for an interior point a nudged edge midpoint gives in three).
- `to_mesh(BRep)` duplicates `BRep::mesh()` plus a weld; the one curved example calls it.
- `compute_name`, `compute_rank`, `compute_range`, `compute_role_profile`, `compute_edge_profile`:
  five switch functions over the same six roles; one table row per role does it.

## Overloads to fold

- One `from_solid(Mesh)`; a BRep is meshed by the caller (`BRep::mesh()`), no BRep overload.
- `compute_member` / `compute_members`, `add_plane` / `add_exit` / `add_column_cut`,
  `compute_side` / `compute_partner`: each pair folds into one function with the general rule.
- `to_block` + `to_head` + `compute_head_cuts` + `compute_edge_cuts`: one `to_head`.

## Examples that say the same thing

| Kept idea | Files saying it today |
|---|---|
| B, footprint + pattern | `templates_grid`, `_skewed`, `_radial`, `_triangular`, `_hex`, `_irregular`, `_courtyard`, `_pentagon` (8) |
| A, massing sliced | `_solid_box`, `_solid_prism`, `_solid_taper`, `_solid_setback`, `_solid_atrium`, `_solid_curved` (6) |
| C, drawn lines | `_braced`, `_crea` (2) |
| references | `_branch_square`, `_branch_residential`, `_branch_office`, `_branch_institutional`, `_point_supported`, `_fastepp` (6) |
| joints and sections | `_framings`, `_profiles` (2) |

Every file in a row is the previous one with other consts and a different name; the office and
institutional presets add nothing the residential L and the courtyard do not show. One example per
row, its variants side by side in one scene, is five files.

## Moved to the kernel (2026-09-26)

The plan geometry now calls session_cpp/py/rust (branch `grid-helpers`); wood no longer calls
Clipper2 in the grid. `Mesh::section_by_plane` replaces `compute_section`, `Line::split_at_crossings`
replaces `compute_crossings` (the ring priority is a `boundary` line list), `Mesh::from_arrangement`
is the `Mesh::from_lines` half of `compute_arrangement` (the grid keeps the id mapping), core wall
rings use the existing `Intersection::offset_in_3d`, per-side deck offsets the new
`Polyline::offset_sides`, and the ring booleans `BooleanPolyline::compute_regions`, the existing
Vatti port taking ring lists with holes. Sections, split, arrangement and offsets leave every
count unchanged. The booleans do not: the port works at full precision where the grid ran
Clipper2 on a 0.001 grid, so deck differences keep sub-micron vertex clusters and the union of
sections keeps other collinear points. Counts that moved: solid `curved` 348 to 344 purlins and
4912 to 4895 contacts; footprint `courtyard` 864 to 866, `skewed` 837 to 840, `triangular` 1239
to 1236 contacts; reference `branch_residential` 1975 to 1979 contacts. Core 2,427 to 2,164 lines.
