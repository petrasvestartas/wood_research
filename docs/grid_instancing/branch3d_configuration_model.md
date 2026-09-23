# Branch3D Concept Lite configurations, mapped onto the wood grid template

**Sources.**
- The UI exploration in this folder: 441 shots, `log.md`, `params_*.json` and `sweep*.json`.
- A read of the app bundle `index.patched.js`, for the rules the shots cannot show:
  - `aMe`: the level generator;
  - `fMe`: cores;
  - `ZN` and `JN`: sizing and elevations;
  - `hQ` and `d3`: how members are drawn;
  - `S_e`: core auto-placement;
  - `ZW`: grid regeneration;
  - `zM` and `WC`: the presets.
- The earlier `docs/grid_instancing/branch3d_framing.md` and `branch3d_mapping.md`.

**Status of `grid.h` today** (`wood/src/templates/grid.h`, 1088 lines):
- It has `from_plan`, `from_lines`, four plan builders, `compute_faces`, `compute_spans`, `compute_members`, `compute_purlins`, `compute_supports`, `compute_bay`, the `to_*` builders and a square-section `Dimensions`.
- Parts C (cores) and E (profiles) of `grid_design.md` are designed, not built.
- `Beam` is still square (`radii`).

Branch works in feet (1 ft = 304.8 mm); our grid works in mm. Branch's "girder" is our `girder`, and Branch's "perimeter beam" (`isBoundary`) is our `is_boundary` edge.

## 0. Corrections to the exploration report

1. **Purlins are not stacked on girders in the drawn model; only the statistics stack them** (report §7.1).
   - Every beam and purlin hangs from the level datum D, which is the underside of the deck, with its top at D − 3 mm.
   - With glulam beams in purlin-on-girder, interior girders drop by min(max purlin depth, 8 in = 203.2 mm).
   - Evidence:
     - `ZN`: `!isBoundary && (origin[2] -= min(o, .6667))`;
     - `JN`: beams and purlins at the level top;
     - the renderer's `d3` box hangs below its origin;
     - shot 193, the single-story view;
     - `branch3d_framing.md` §5.3.
   - Purlins are 520–920 mm deep, so they overlap the girders and frame between them.
   - Only `floorAssemblyDepth` = girder + purlin + slab + topping (+ protection) treats the members as stacked. That is why a 12 ft story shows 6.49 ft of clear height.
2. **Purlins are not cut at cores** (the report's B5 says they stop at the core faces).
   - `fMe(columns, beams, state)` never receives the purlin list, and purlins are clipped against the footprint only (`hW(polyline, …)`).
   - All 32 purlins keep their 260×640 section in B5a–c.
   - The plan shots cannot show this, because the core box is opaque.
3. **Columns on a core outline are removed too, not only those strictly inside.**
   - The Residential preset has 45 column points, and 3 of them lie on core 1's outline: (60,150), (60,180) and the corner (72,150).
   - Branch reports 42.
   - Part C's "strictly inside" would give 45.
4. **Some re-shots are unusable.**
   - 433–437 (the B1/B2 `_v2` shots) are off-centre and covered by the cookie card. Use 305, 308, 311, 314 and 317 instead: the floating input panel covers part of the centre-right, but the framing stays readable.
   - 379 and 383 are off-centre; 438 and 439 replace them.
   - 440–483 are good.
5. **The core auto-placement follows a rule** (§2.8); the 29×29 core is its output for this footprint.

## 1. Configuration parameters and our equivalent

Status keys:
- **EXISTS**: in `grid.h` today.
- **PART C** / **PART E**: designed in `grid_design.md`, not in `grid.h`.
- **MISSING**: in neither.
- **BEYOND**: something we have that Branch lacks.
- **OUT**: not geometry; store it as a double later if it is ever needed.

### 1.1 Grid

| Branch (store key, UI) | Values | `grid.h` |
|---|---|---|
| `spacingX`, `spacingY` ("Typical Bay" sliders) | 4–50 ft, step 0.25. Regenerates the lines with `ZW(min, max, s, 1)`: lines at min + k·s while < max − 1 ft, and the last bay takes the remainder (Plate timber at 11.5 ft leaves a 5 ft bay). | EXISTS as bay-width lists: `create_orthogonal(xs, ys)` with `std::vector<double>(n, s)`. The remainder rule is MISSING as a helper. |
| `xIncrements`, `yIncrements` | Absolute positions of the **interior** lines only. The footprint bbox edges are implicit, non-editable lines. "+" appends unsorted, e.g. `[30,60,90,75]`. | EXISTS, relative: `xs` = diff(sort([x0, …increments, x1])). |
| Grid widget | typed bay, "=" (all bays), "+" (line midway to the next), "−", drag (no snap) | edits of `xs` / `ys` |
| — | skew, radial, triangular, hexagonal, Voronoi, free 3D lines | BEYOND, EXISTS: `create_orthogonal(…, skew)`, `create_radial`, `create_triangular`, `create_hexagonal`, `Mesh::from_polylines`, `Grid::from_lines` |

### 1.2 Footprint

| Branch | Values | `grid.h` |
|---|---|---|
| `polyline` | Any simple polygon, counter-clockwise. You can add a point on an edge (slow click just outside), push or pull a face (which moves both vertices), or drag a corner (which crashed). Presets: L (Residential) and U (Institutional). | MISSING: clipping bays to a polygon. Today only whole bays can be removed, via plan face `top = 0`. |
| `pointSupportedPolyline`, `pointSupportedCores` | Presets narrowed to multiples of 11.5 ft for Plate (72 → 69, 150 → 149.5) | data only |
| column merge | Column points closer than 3.28 ft (1 m) are merged | MISSING. Our weld is `Grid::tolerance`, 1 mm. |

### 1.3 Stories

| Branch | Values | `grid.h` |
|---|---|---|
| `numStories`, `storyHeight` | Roof-click panel, dragging the top floor, or the "[n] @ [h]" overlay | EXISTS: `heights`. Non-uniform heights are BEYOND. |
| `subStories`, `subStoryHeight` | Levels below grade: forced to concrete, beams without purlins, flat plate, footings under them (B4b) | MISSING: elevations start at 0. |
| — | Per-bay floor range `bottom` / `top`: setbacks, double-height bays, voids | BEYOND, EXISTS (plan face attributes) |

### 1.4 Cores

| Branch | Values | `grid.h` |
|---|---|---|
| `cores` "0" / "1" / "2", `coreData[{position: min corner, width, depth}]` | Placed freely, no snap; the core panel swaps the dimensions or deletes the core | PART C: `Grid.cores`, `core_from_rectangle`, `compute_cores`, `to_core_walls`, `Dimensions.core`. Nothing in `grid.h` yet. |
| auto-placement (`S_e`) | §2.8 | PART C `compute_core_position`; the rule is now known |
| core solid | From the lowest level to the roof + 2.5 ft; excluded from every quantity ("excl Core") | MISSING: Part C walls stop at the top story. |

### 1.5 Framing system

| Branch | Values | `grid.h` |
|---|---|---|
| `structuralSystem` "Plate" / "Beam" / "Purlin" | global | EXISTS per face: `structural_system` 0 / 1 / 2, default 1 from `compute_faces`. Per-bay mixing is BEYOND. |
| Plate has no beams, perimeter included | — | A deliberate difference (Part A, A4): `compute_members` keeps the `is_boundary` beams under system 0. To match Branch, set `beam` 0 on them after the rule. |
| Disabled combinations (Plate×DLT, Plate×Composite, Plate×Steel) | — | OUT |

### 1.6 Span direction

| Branch | Values | `grid.h` |
|---|---|---|
| `spanDirection` "X" / "Y": the direction the girders run, global | The wizard sets it: `(Mass Timber && system != Purlin) \|\| Steel ? X : Y` | EXISTS in local form: face `span` = loop side index, and `compute_spans(grid, longest)` chooses by length. **MISSING:** choosing by world direction. The workaround `update_default_face_attributes({{"span", 1.0}})` gives Y, but only on unclipped `create_orthogonal` bays. |

### 1.7 Purlins

| Branch | Values | `grid.h` |
|---|---|---|
| `maxPurlinSpacing` | 2–20 ft, default 10 | EXISTS: `compute_purlins(grid, spacing)` gives n = ceil(w/s) − 1 per face, plus a purlin on each interior cross grid line (A4). The count equals Branch's in every sweep case. |
| station origin | Per **unclipped** grid bay (§2.5) | Ours is per face extent, so it differs on clipped bays. MISSING. |
| "Purlin" label becomes "Secondary Beam" for non-glulam beams | — | name only |

### 1.8 Members and profiles per role

| Role | Branch | `grid.h` |
|---|---|---|
| column | Glulam and Concrete: Square (Rectangular and Round disabled). Steel: W, HSS (Round HSS a future feature). Full story height. | `Dimensions.column`, a direction polygon (square on orthogonal grids): EXISTS. W and HSS: PART E. |
| girder | Glulam Rectangular; Concrete Rectangular; Steel W. HSS is disabled with no reason given. Square, Double, Slab band, Precast and Open web are future features. | `Dimensions.beam`, square only. Rectangular and W: PART E. |
| perimeter beam | Same profile family, but sized on its own (`isBoundary`) | Shares `Dimensions.beam`. A per-role size is MISSING. |
| purlin / secondary beam | Rectangular Timber, W, Rectangular Concrete. Hybrids happen: steel girders with glulam purlins when switched in the panel. | `Dimensions.purlin`, square only. PART E. |
| sizes | "Size: varies": every member is sized from its span and tributary width | MISSING: per-edge `width` / `depth` doubles that override `Dimensions` |
| supplier, manufacturer, protection | carbon, panel width and clear height only | OUT |
| — | heads, butt and mitre cuts, contacts, walls | BEYOND, EXISTS |

### 1.9 Floor

| Branch | Values | `grid.h` |
|---|---|---|
| `floorSlabMaterial` + `floorSlabProfile` | Timber: CLT, MPP/VLT, DLT (GLT future). Concrete: Flat plate (hollow-core, double tee future). Composite: Slab on metal deck (roof deck future). | Thickness only: `Dimensions.deck` EXISTS. The profile is OUT. |
| thickness | Sized, e.g. CLT 7.47 in at 10 ft purlin spacing. It is sized from `maxPurlinSpacing`, not the actual spacing (B2). | `Dimensions.deck` |
| `concreteTopping` | 0–6 in, default 2 in, timber floors only, sits on the deck | MISSING |
| panel strips (`panelLines`) | Supplier width (CLT 11.5 ft, MPP 4 ft, DLT 14 ft per `branch3d_framing.md`), `maxPanelLength` 60 ft with end joints on grid lines, direction `(span == X) != (system == Purlin)` | MISSING: `to_deck` builds one plate per bay |
| holes at cores | — | PART C `core_hole` |

### 1.10 Fire, loads and location: OUT

- **Fire:** `fireRating` Unrated / 1 h / 2 h (default) / 3 h. Protection per role: gypsum ×1–3; SAFP ½, 1.5 or 2 in; intumescent paint.
- **Loads:** `buildingType` Normal 15/65, High 25/100, Storage 25/125 psf (SDL/LL). SDL ranges 0–100 psf and LL 0–200.
- **Location:** Mapbox geocoding.
- **Geometry effect:** member sizes and clear height only. Our sizes are inputs.
- **If ever needed:** default face doubles `sdl`, `ll` (kPa) and `fire` (min).

### 1.11 Results

| Branch output | `grid.h` |
|---|---|
| Building Statistics: area per floor (excl cores), total area, height, bbox, floor height, minimum clear height | Partial: `compute_bay` per face (area, spans, purlins). A building summary is MISSING. |
| Quantities, pieces per role. Deck (panels); Girder = girders + perimeter; Purlin; Column. | Countable from the element names `column`, `head`, `girder`, `beam`, `purlin`, `deck`: EXISTS. Branch "Girder" = our `girder` + `beam`. |
| Volumes, carbon, SCO₂RS, cost | OUT (volumes can be derived from the elements) |
| Warnings: custom sizes, span limits (CLT Plate 22 ft × 11.5 ft), "Reset Grids" | MISSING (`compute_bay` has the spans) |
| Color by size, Single-story view, units | Viewer. Part D: no colours. `storey_k` groups give a single-story view. |

### 1.12 Presets (wizard)

**Bay size by preset** (`zM`, [X, Y] ft, rows Current/Office):

| System | Mass Timber | Concrete | Steel |
|---|---|---|---|
| Post and beam | [30, 20] | [30, 15] | [30, 12] |
| Point supported | [11.5, 15] | [25, 25] | [30, 20]; Office and Institutional [33, 26] |
| Purlin on girder | [30, 30] | [30, 30] | [30, 30] |

- Residential Post and beam + Mass Timber is [25, 15].
- The span direction comes from the rule in §1.6.

**Building types** (`WC`):

| Type | Stories | Footprint (ft) | Cores |
|---|---|---|---|
| Residential | 12 × 12 ft | L: (0,0) (72,0) (72,150) (144,150) (144,220) (0,220) | (52,150) 20×30; (41,30) 10×20 |
| Office | 6 × 14 ft | 150×180 | (50,90) 30×30; (60,46) 20×10 |
| Institutional | 8 × 16 ft | U: (0,0) (150,0) (150,70) (60,70) (60,160) (150,160) (150,230) (0,230) | (40,160) 20×30; (50,50) 10×20 |

**Store default** (never reached through the wizard): a 60×60 square, increments every 15 ft and one 20×20 core at (20,20).

## 2. Geometric rules per system

Datum: D_k = k·storyHeight, the framing top and deck underside of level k.

### 2.1 Columns (all systems)

- **Where:**
  - at every interior grid-line crossing inside the footprint;
  - at every footprint vertex;
  - at every point where a grid line crosses the footprint edge.
  - Points within 3.28 ft are merged.
  - Checks: L 20, diagonal pentagon 17, Residential 45 − 3 core = 42.
- **Removed:** inside a core or on its outline.
- **Plan:** the same on every story. There are no transfers or cantilevers; the FAQ says cantilevers cannot be represented.
- **Height:** each column runs the full story, D_{k−1} to D_k, through the beam zone. It is schematic, with no bearing detail.
- **Footings:** sized under the lowest columns; a grade slab sits at the bottom.
- **Ours:** from a clipped plan, `from_plan` puts a column at every plan vertex, which is Branch's rule once the clip creates the crossing vertices. A column stands on the deck top and stops under its head.

### 2.2 Perimeter beams (Beam and Purlin)

- **Where:** one member per footprint segment, split at every column point. A diagonal edge gives a diagonal beam (370).
- **Sizing:** each has its own size.
  - Edges parallel to the girders carry half a bay: 300×720 in the baseline.
  - Edges parallel to the purlins carry p/2: 260×600.
- **Elevation:** never dropped.
- **Plate:** none, not even at the edge (287, 301).
- **Ours:** `is_boundary` edges keep `beam`. Parallel to `span` they are `girder`, otherwise `beam`; both are built at `Dimensions.beam`.

### 2.3 Girders (Beam and Purlin)

- **Where:** along every grid line of the span direction, clipped to the footprint, one member per bay between crossing lines.
- **Dropped cases:**
  - Shorter than 1e-4 ft.
  - A bundle rule (`aMe`, `w`): a non-boundary girder whose two ends are both boundary columns, or which lies on the perimeter, is dropped.
    - That second case is not observed in any shot.
    - A one-bay-deep footprint would lose its girders. Capture a 120×30 ft Beam span Y to confirm (§4, P29).
- **Ours:** `girder` = a beam parallel to the `span` side of an adjacent system-1 or system-2 floor. It runs through heads, and other members butt on its side plane.

### 2.4 Post and beam

- There are no members on the cross grid lines; the deck spans one way onto the girders.
- The deck span is the girder spacing. Because the span direction comes from the material rule, Post and beam + Concrete 30×15 gets girders along Y and a 30 ft deck span (a 14.4 in slab, 281).
- **Ours:** `compute_members` sets `beam` 0 on non-girder, non-boundary lines of system-1 floors. EXISTS, same result.

### 2.5 Purlin on girder

- **Counting:**
  - For each grid bay between two adjacent girder lines, and each cross bay [z_k, z_k+1], n = max(1, ceil(bay/p)) at spacing bay/n.
  - The stations are z_k + j·bay/n for j = 0…n−1. Station j = 0 lies on the cross grid line (column line), so every interior cross line carries a purlin, framing column to column.
- **Dropped stations:**
  - a station whose two ends are both boundary columns, i.e. the footprint edge row, because the perimeter beam is there;
  - duplicates.
- **Clipping:**
  - Purlins are clipped to the footprint (the diagonal gives short purlins, 370). They are **not** clipped at cores.
  - Each purlin spans one girder bay and is split at every girder.
  - Stations come from the **unclipped** grid bay. In the L and the pentagon, the clipped bays (60–120, 45–60) get a purlin at y = 50 ft (375, 370).
- **Checks:** 32 at p = 10, 92 at 4, 20 at 16 and at 20. The steel span-X case has 33.
- **Sizing:** purlins are sized per bay length (B3: 20/30/40/60 ft → 240×520, 260×640, 300×720, 400×920).
- **Ours:**
  - `compute_purlins` gives n − 1 per face, and the cross-line edges get `purlin` 1. The counts match.
  - `compute_stations` stations over the face's own extent. On the two clipped bays that puts them at 52.5 ft, not 50 ft.

### 2.6 Point supported

- Columns only (the §2.1 rule), with a two-way deck on them and no beams.
- **Limits:** CLT spans are capped at 11.5 ft (panel width) × 22 ft. DLT and Composite are disabled.
- **Warnings:** larger bays give "Some elements require custom sizes". "Reset Grids" sets 15 ft × 11.5 ft (430).
- **Ours:** heads act as column capitals under the deck (BEYOND). Boundary beams stay unless switched off.

### 2.7 Stacking (drawn model)

| Part | Branch | Ours today |
|---|---|---|
| deck | [D, D + t] | [z − deck, z]; node z = deck top |
| topping (timber) | [D + t, D + t + 2 in] | none |
| perimeter beams, purlins, cross-line purlins | top at D − 3 mm, hanging | top at z − deck (flush) |
| interior girders | Glulam purlin-on-girder: top at D − 3 − min(purlin depth, 203.2). Steel or concrete beams: flush. | flush with the purlins |
| column | D_{k−1} → D_k, through the beams | lower node → head bottom |
| head | none | frustum; top at z − deck − deepest incident beam |

- In Branch, purlins deeper than the drop overlap the girder vertically: they are framed between the girders, not stacked on them.
- Branch's statistics assume full stacking: `floorAssemblyDepth` = max beam depth + max purlin depth + slab + topping + protection, and clear height = story − that.
- To overlay the two models, translate ours by +deck (+ topping), or compare members relative to their own story.

### 2.8 Cores

- **Rectangles:** a core is `{min corner, width, depth}`, placed anywhere with no snap. It is a hole in every floor and a solid from the lowest level to roof + 2.5 ft.
- **What the core does to the framing** (`fMe`):
  - It removes columns inside or on its outline (B5b: 20 → 19).
  - It removes beams with both ends inside.
  - It splits crossing beams (girders and perimeter beams) at the outline and supports the split ends on the core.
    - Stubs down to 0.01 ft survive: B5a has two 0.5 ft 220×200 stubs between the column at (60,30) and the core face at y = 30.5.
  - Purlins run through (§0.2).
- **Auto-placement** (`S_e`):
  1. The candidates are the footprint vertices plus the corners of the existing cores.
  2. For every pair (i, j ≥ i + 2), take the midpoint.
  3. Score it −∞ if it is inside a core or outside the footprint. Otherwise score it min(distance to the footprint boundary, distance to the nearest core).
  4. The best midpoint is the centre. The side is round(clamp(0.65 · score, 12, 30)) ft, and the core is square.
  - Example: 120×90 gives centre (60,45) and a clearance of 45, so side 29 at (45.5, 30.5) (B5a).

### 2.9 Perimeter and footprint handling

- The grid lists hold interior lines only, and the bbox lines are implicit. A footprint that is not a multiple of the spacing leaves a remainder bay: 5 ft for Plate timber, 24 ft and 10 ft for Residential.
- Grid lines are clipped per segment against the footprint polygon.
- Re-entrant corners get columns, and perimeter beams follow every edge. Edges between grid lines get columns only at vertices and crossings: the L's (45,0)–(45,45) edge has a column at (45,30).
- **Ours:** only whole bays can be removed (`top = 0`). Everything else needs the clip (§3, P1.2).

### 2.10 Basement (substories)

- Levels below grade are concrete, with beams and no purlins (Post-and-beam-like) and a flat plate.
- Columns are 400/425 square; upper columns grow to 360–440.
- Footings sit under the basement.
- **Ours:** MISSING.

## 3. Changes to `grid.h` and the examples, prioritised

### P1: blocks a faithful side-by-side

1. **Span by world direction.**
   - `inline void compute_spans(Grid& grid, const session_cpp::Vector& direction, double angle = 10.0);`
   - It fills `span` with the first loop side within `angle` of ±direction (plan projection). Where no side qualifies, it falls back to the shortest side. The existing `compute_spans(grid, longest)` stays for radial, hex and triangular plans.
   - Branch "X" = (1,0,0) and "Y" = (0,1,0).
   - Needed by every pair: the baseline is span Y, and 30×30 bays tie to side 0 = X today.
2. **Footprint clip.**
   - `inline session_cpp::Mesh create_clipped(const session_cpp::Mesh& plan, const session_cpp::Polyline& footprint);`
   - It intersects each plan face with the footprint and drops pieces with area below tolerance², then welds with `Mesh::from_polylines(polygons, 0.001)`.
   - This gives Branch's column rule automatically, because crossings become vertices. It also gives boundary beams on the clipped edges and diagonal edge beams.
   - Clipping the footprint by each convex bay (Sutherland–Hodgman) is exact while the intersection is one piece. A concave footprint that splits a bay in two needs a real polygon boolean: check `session_cpp` first, do not assume one exists.
   - It works on any plan builder (radial and hex too, BEYOND).
   - Unblocks pairs P19–P22 and, with cores, the presets.
3. **Cores (Part C), with the Branch semantics confirmed here.** These corrections go into `grid_design.md` Part C:
   - Remove columns inside the outline **or within tolerance of it**; "strictly inside" misses 3 in the Residential preset.
   - Split girders **and perimeter beams** at the outline.
   - Stubs:
     - Branch keeps pieces down to 3 mm.
     - For us, a piece shorter than `reach + core / 2` lies inside the head. Drop it and let the head touch the wall.
     - B5a's 152 mm stubs fall under this rule; document the count difference, 10 vs 8 interior girders.
   - Purlins: Branch runs them through the void. We cut them at the wall, consistent with the deck hole (BEYOND). The counts are unchanged in B5a–c.
   - `compute_core_position` implements `S_e` (§2.8) in model units: clamp to 3658–9144 mm and round to 304.8.
   - A core wall top option: roof + 762 mm.
   - Unblocks P16–P18 and P21–P22.
4. **Role sections (Part E).**
   - `Dimensions` gets separate `girder`, `edge` (perimeter beam), `purlin` and `column` profiles, each with width × depth. The builders stack by depth.
   - Until then, compare plans with width-matched squares (girder 320, purlin 260).
   - Branch's girders are 2.5 : 1 (320×800), so the iso pairs need this.

### P2: exact geometry

5. **`Dimensions.drop`**, the drop of interior girders below the purlin tops.
   - It applies to edges with `girder` 1 and no `is_boundary`.
   - Branch glulam = min(purlin depth, 203.2); steel and concrete = 0; FAST+EPP = 0 (today).
   - `compute_head_top` then uses the deepest underside: deck + max(drop + depth).
   - If drop ≥ purlin depth, the purlins sit on the girders (fully stacked, as Branch's statistics assume). They then touch the girder top face and need no side cut; offer this as the second variant.
6. **Per-member sizes.**
   - Edge doubles `width` and `depth`, and face `deck`, read before `Dimensions` in `compute_width`, `to_beam`, `to_purlins` and `to_deck`.
   - This reproduces Branch's "Size: varies".
   - The capture has size tallies only, not sizes per member. Re-capture with coordinates (§4 note).
7. **Grid-bay stationing.**
   - The clip writes the unclipped cell on each face as doubles `cell_x0`, `cell_x1`, `cell_y0`, `cell_y1` (orthogonal plans).
   - `compute_purlins` and `compute_stations` then use the cell's extent along the span: positions cell_lo + k · cell / n. A station that does not cross the clipped face yields nothing.
   - This moves the L's and the pentagon's two purlins from 52.5 ft to 50 ft.
8. **Increment helper** (in the example, or in the header if reused).
   - Bay widths from length and spacing with Branch's rule: lines at k·s while < length − 304.8, and the last bay takes the remainder.
   - Also the conversion from Branch's absolute interior positions: sort, then diff against [0, …, bbox].
9. **Plate perimeter beams.**
   - No header change: the example sets `beam` 0 on `is_boundary` edges of system-0 floors after `compute_members` when `PLATE_EDGE_BEAMS` is false.
   - The deck edge is then unsupported; say so in the description.

### P3: completeness and beyond

10. **Substories.**
    - `Grid::from_plan(plan, heights, tolerance, base = 0.0)` gives the first elevation. Stories below 0 get `substructure` 1 and structural system 1.
    - Pair P15.
11. **Topping:** `Dimensions.topping` and `to_topping`. The node becomes the topping top.
12. **Deck panels:** strips at the panel width along the deck span, with end joints on grid lines at most 60 ft apart. Only for parity with Branch's panel lines.
13. **Summary** for the comparison table:
    - pieces per role;
    - area per floor excluding cores;
    - clear height, both the geometric one and Branch's stacked formula.
14. **Span-limit warnings** from `compute_bay`: CLT Plate 3505 × 6706 mm.
15. **Cantilevers (BEYOND Branch).**
    - Plan vertex `column` = 0 already removes columns. Collinear beams across a column-less node still meet on a bisector, which makes a hinge.
    - Add a merge so the member runs continuously from the last support to the tip. Branch's `uMe` merges collinear beams but cannot cantilever.

### Examples

- **`templates_grid_branch.cpp` (new):** the Branch baseline in mm, with CAPS consts that mirror the store keys:
  - `XS`, `YS`, `HEIGHTS`, `STRUCTURAL_SYSTEM`, `SPAN` (a `Vector`), `SPACING`, `FOOTPRINT`, `CORES`, `PLATE_EDGE_BEAMS`;
  - `storey_k` groups and `compute_contacts(0)`.
  - Each pair in §4 is one set of consts. A const `CONFIG` index into a table of the §4 rows is fine; it is not an option enum or an argument parser.
- **`templates_grid`:** keep the CWC / FAST+EPP case (non-uniform bays, walls). Once P1.2 lands, show the footprint clip next to the `top = 0` void, which Branch cannot do per story.
- **`templates_grid_core` (Part C4):** its settings (the 60×60 store default) have no capture. Retarget it to B5a/B5b (P16, P17), or capture the default first (P30).
- **`templates_grid_radial` and `templates_grid_hex`:** keep them as BEYOND, with no Branch pair. Add `templates_grid_triangular`, which has a builder but no example. A cantilever example follows P3.15.

## 4. Screenshot pairs to reproduce

### Conventions

- **Our settings.** All pairs are Purlin + Mass Timber, 3 stories @ 12 ft (`HEIGHTS {3657.6 ×3}`), a 120×90 ft rectangle (`XS {9144 ×4}`, `YS {9144 ×3}`), span Y, p = 10 ft (3048), no cores, unless a row says otherwise.
- **Branch counts** are per level: columns / interior girders / perimeter beams / purlins, from `log.md`.
- **Our counts** are per story: `column` / `girder` / `beam` / `purlin` / `deck`. Branch's interior + perimeter = our `girder` + `beam`. Heads = columns.
- **Branch cameras** (`helpers.js`), in ft, Z up, 1600×1000:
  - **iso:** S = max(dx, dy, H), eye (cx − 1.25S, cy − 1.6S, H/2 + 1.1S), target (cx, cy, H/2 − sub/2), fov 40°.
  - **plan:** single-story view of the first level with the slabs hidden. S′ = max(dx, dy), eye (cx, cy − 0.05S′, 4S′ + H), target (cx, cy, 0), fov = 2·atan(0.62S′ / (4S′ + H/2)).
  - Our plan equivalent is group `storey_0` with the decks hidden, top view.
- **Colours (Part D).** The shots are coloured. Re-shoot with member colours set to the viewer grey: restore `params_<tag>.json` in the driver, then override `data.color`.
- **Capture per member.** Extend `h.model` to dump every member (startPoint, endPoint, origin z, width, depth, `isBoundary`, profile) so the pairs can be compared as member lists, not only as pixels.

### Layout pairs

| # | Branch shots (iso / plan) | Change from the base, Branch → ours (mm) | Branch per level | Ours per story |
|---|---|---|---|---|
| P1 | 269 / 295 | base (purlin timber) | 20 / 9 / 14 / 32 | 20 / 15 / 8 / 32 / 12 |
| P2 | 272 / 296 | concrete members, no drop | 20 / 9 / 14 / 32 | as P1 |
| P3 | 275 / 297 | steel, span X, composite deck | 20 / 8 / 14 / 33 | 20 / 16 / 6 / 33 / 12 |
| P4 | 278 / 298 | Beam, 30×20 span X; `YS {6096 ×4, 3048}` | 30 / 16 / 18 / 0 | 30 / 24 / 10 / 0 / 20 |
| P5 | 281 / 299 | Beam concrete, 30×15 span Y; `YS {4572 ×6}` | 35 / 18 / 20 / 0 | 35 / 30 / 8 / 0 / 24 |
| P6 | 284 / 300 | Beam steel, 30×12 span X; `YS {3657.6 ×7, 1828.8}` | 45 / 28 / 24 / 0 | 45 / 36 / 16 / 0 / 32 |
| P7 | 287 / 301 | Plate timber, 11.5×15 span X; `XS {3505.2 ×10, 1524}`, `YS {4572 ×6}`, `PLATE_EDGE_BEAMS` false | 84 / 0 / 0 / 0 | 84 / 0 / 0 / 0 / 66 (34 edge beams if kept) |
| P8 | 290 / 294 | Plate concrete, 25×25; `XS {7620 ×4, 6096}`, `YS {7620 ×3, 4572}` | 30 / 0 / 0 / 0 | 30 / 0 / 0 / 0 / 20 (18 if kept) |
| P9 | 307 / 308 | B1: span X | 20 / 8 / 14 / 33 | as P3 |
| P10 | 310, 313, 316 / 311, 314, 317 | B2: p = 4, 16, 20 ft (1219.2, 4876.8, 6096) | purlins 92, 20, 20 | purlins 92, 20, 20 |
| P11 | 323 / 324 | B3a: `xIncrements [20,60,90]` → `XS {6096, 12192, 9144, 9144}` | 20 / 9 / 14 / 32 | 20 / 15 / 8 / 32 / 12 |
| P12 | 330 / 331 | B3c: `[30,60,90,75]` → `XS {9144, 9144, 4572, 4572, 9144}` | 24 / 12 / 16 / 40 | 24 / 18 / 10 / 40 / 15 |
| P13 | 333 / 334 | B3d: `[30,90]` → `XS {9144, 18288, 9144}` | 16 / 6 / 12 / 24 | 16 / 12 / 6 / 24 / 9 |
| P14 | 441 / 440 | B4a: 1 story, `HEIGHTS {3657.6}` | 20 / 9 / 14 / 32 | as P1 |
| P15 | 341 / 342 | B4b: 5 stories + 1 substory (P3.10); floating panel open | above grade as P1; basement concrete, 0 purlins | as P1 per story; basement 20 / 15 / 8 / 0 |
| P16 | 345 / 346 | B5a: core (13868.4, 9296.4), 8839.2 × 8839.2 | 20 / 10 (2 stubs) / 14 / 32 | 20 / 14 or 16 (stub rule) / 8 / 32 / 12 with a hole |
| P17 | 348 / 349 | B5b: + core (4648.2, 6781.8), 4572 × 4572 | 19 / 10 / 14 / 32 | 19 / 14 or 16 (stub rule) / 8 / 32 / 12 |
| P18 | 354 / 355 | B5c: core 2 at (6153.0, 18978.7) | 20 / 11 / 14 / 32 | 20 / 15 or 17 (stub rule) / 8 / 32 / 12 |
| P19 | 369 / 370 | B6c pentagon: `FOOTPRINT` (0,0) (13716,13716) (36576,13716) (36576,27432) (0,27432) | 17 / 6 / 14 / 22 | 17 / 11 / 9 / 21 / 9 |
| P20 | 374 / 375 | B6d L: `FOOTPRINT` (0,0) (13716,0) (13716,13716) (36576,13716) (36576,27432) (0,27432) | 20 / 7 / 16 / 24 | 20 / 14 / 9 / 24 / 10 |
| P21 | 378 / 438 | B6a Residential (below) | 42 / 21 / 27 / 75 | columns 42 (needs the core-edge rule); girder + beam = 48 |
| P22 | 382 / 439 | B6b Institutional (below) | 49 / 24 / 34 / 80 | columns 49; girder + beam = 58 |

**Notes on P16–P22.**
- **P16–P18:** the lower girder count drops the stubs shorter than `reach + core / 2` (the two 152 mm stubs at x = 60 ft; P18's 690 mm stub stays), the higher one keeps them as Branch does.
- **P19:** Branch's shot has the vertex at (45.074, 44.977) ft, which leaves a 0.065 ft purlin stub; hence 22 purlins. Use exact (45,45) and expect 21, or re-shoot Branch with the exact vertex. Two purlins sit at 52.5 ft (ours) vs 50 ft (Branch) until P2.7.
- **P20:** the same 52.5 vs 50 ft purlin difference.
- **P21, Residential:**
  - 12 × 3657.6; `XS {9144 ×4, 7315.2}`, `YS {9144 ×7, 3048}`.
  - Footprint (0,0) (21945.6,0) (21945.6,45720) (43891.2,45720) (43891.2,67056) (0,67056).
  - Cores (15849.6, 45720) 6096 × 9144 and (12496.8, 9144) 3048 × 6096.
- **P22, Institutional:**
  - 8 × 4876.8; `XS {9144 ×5}`, `YS {9144 ×7, 6096}`.
  - Footprint (0,0) (45720,0) (45720,21336) (18288,21336) (18288,48768) (45720,48768) (45720,70104) (0,70104).
  - Cores (12192, 48768) 6096 × 9144 and (15240, 15240) 3048 × 6096.

### Profile pairs (Part E; layout = P1)

| # | Branch iso / plan | Sections (mm, or AISC) |
|---|---|---|
| P23 | 442 / 443 | Steel W columns: W8X24 ×4, W8X31 ×10, W8X48 ×6 |
| P24 | 445 / 446 | Steel HSS columns: HSS5X5X.375 – HSS7X7X.500 |
| P25 | 451 / 452 | W24X76 girders; W24X55 / W18X35 perimeter; glulam purlins 260×640; no drop |
| P26 | 454 / 455 | As P25 plus W21X44 purlins |
| P27 | 457 / 458 | Concrete girders 300×660, perimeter 300×500 / 300×540, purlins 300×500; no drop |
| P28 | 460 / 461 | Glulam girders 320×800 (dropped 203.2), W21X44 purlins |

**Glulam reference sections for P1** (`DIMENSIONS` once Part E lands):

| Member | Section (mm) |
|---|---|
| interior girder | 320×800, drop 203.2 |
| edge girder | 300×720 |
| edge beam | 260×600 |
| purlin | 260×640 |
| column | 360 (range 320–380) |
| deck | 190 (CLT 7.47 in) |
| topping | 51 |

Heads are ours: head 300, reach 400.

### New captures needed

| # | Configuration | Checks |
|---|---|---|
| P29 | Beam span Y on a 120×30 ft footprint | the bundle rule that drops a girder whose two ends are both boundary columns |
| P30 | Store default: 60×60 ft, 15 ft bays, core 20×20 at (20,20), Plate then Beam span X, 2 stories @ 12 ft | Part C4's settings |
| P31 | P19 with the exact (45,45) vertex | the pentagon without the off-grid stub |

**Excluded from comparison:**
- B8 floors (463–474) and B9 fire (475–483) change only thickness and sizes.
- Their `_v2` plans reuse the P1 layout and serve only as section references.
