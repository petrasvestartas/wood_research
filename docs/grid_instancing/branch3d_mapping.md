# Branch3D mapped onto the wood grid template (`wood/src/templates/grid.h`)

Research only: no repo files were edited and nothing was built. The two input reports came from reading the Concept Lite bundle. I re-read the same bundle (local prettified copy `/tmp/claude-1000/-home-petras-code-code-cpp-wood-research/cd17883b-ad50-44cc-bbcd-c4f797944a70/scratchpad/branch3d/pretty.js`, taken from https://concept.branch3d.com/assets/index-CxNXZKiq.js) to check the generator. All `L…` line numbers refer to `pretty.js`. Branch3D's internal units are feet. Where I give mm, the conversion is mine.

## 0. State of the inputs, and new facts from this pass

**Missing inputs:**
- **`grid.h` does not exist yet.** `wood/src/templates/` holds chevron, diamond_mesh, reciprocal*, reflex_fold, translation_shell and vda_mesh only.
- **`scratchpad/grid_design.md` does not exist.** This is the FAST+EPP-based design the other effort is writing.
- **No FAST+EPP vocabulary to compare against.** `fe_bay.html` is a Cloudflare block page, and `bay.html` / `bay_index.html` are 16-byte stubs.

**Correction to `report_wood_side.md` §6.** The kernel `Graph` now has compas-style double attributes.
- Evidence in `session/session_cpp/src/graph.h`:
  - `std::map<std::string,double> attributes` on `Vertex` (:37) and on `Edge` (:101)
  - `default_vertex_attributes` / `default_edge_attributes` (:175-176)
  - `vertex_attribute(key,name)`, `set_vertex_attribute`, `edge_attribute(tuple,name)`, `set_edge_attribute`, `vertices_where`, `edges_where`, `*_where_predicate`, `update_default_*_attributes` (:262-295)
  - The change came in commit 49ee9b57.
- `Graph` still has **no positions and no faces**.
- Both `Graph` and `Mesh` name the API **`vertex_*`**. The Grid should use `vertex_attribute` / `vertices_where`, not the `node_*` names `report_wood_side.md` §7 proposed.

**New facts about the generator (verified in the code unless marked inferred):**
- **Beam in the Post and beam system (`"Beam"`):**
  - There are no beams on the cross gridlines. Girders run only along one family of lines (`F = spanDirection==="X" ? yIncrements : xIncrements`, L123872).
  - The other family carries only the perimeter beams.
- **Purlin system (`"Purlin"`):**
  - The first purlin of each bay sits *on* the cross gridline: `Xe = Z + We·Re`, `We = 0..Te-1` (L123935).
  - So the column lines at right angles to the girders carry a 120 mm purlin, not a girder.
- **Deck span direction**, `gMe` L124335: `d = (spanDirection === "X") != (structuralSystem === "Purlin")`. The deck always spans at right angles to the members it bears on.
- **`spanDirection` names the girder direction, not the deck direction.** UI: "Girders / primary beams span along the model's X-axis".
- **Girders on a perimeter line are dropped.** A non-boundary beam with both end columns `isBoundary` is skipped at L123803 (`if (Z && se) return;`).
  - Inferred side effect: a one-bay girder that runs perimeter to perimeter is dropped too.
  - The girder tributary width uses `F[$-1] || 0` and `F[$+1] || 0` (L123879-123880). The first and last lines therefore measure from position 0. It is harmless only because perimeter girders are dropped. Do not copy it.
- **Boundary-beam tributary width** (L123840-123857):
  - base: `trib = half the bay on the inside`
  - `Beam`: `trib *= |cos θ|`, where θ is the angle between the edge and the span axis
  - `Purlin`: `trib = p/2 + (trib − p/2)·|cos θ|`, with `p = maxPurlinSpacing`
  - width 140 mm
  - Default widths: girder 180 mm (`Nf` default), purlin 120 mm, perimeter 140 mm.
- **Vertical datum** (`JN` L124248), for the storey with index `i` and height `h`:
  - `column.origin.z = i·h`, `column.height = h`
  - beams, purlins and `floorPlate.area` sit at `z = i·h + h`
  - Rendering (inferred from the three.js transforms `hQ` L143132, `d3` L142907, `LRe` L142854, `IRe` L143208):
    - beam and purlin boxes hang **below** the datum;
    - the deck occupies `[datum, datum+thickness]`;
    - columns run the full storey height, through the beam depth. The geometry is schematic, with overlapping boxes and no joinery.
- **Glulam purlin-on-girder drop** (`ZN` L123088): non-boundary girders are lowered by `min(max purlin depth, 0.6667 ft)`, which is 8 in or about 203 mm. The purlins end up stacked on the girders.
- **Assembly depth.** `floorAssemblyDepth = girderDepth + beamFP + purlinDepth + slab(maxDepth|thickness) + topping(Timber only) + floorFP`, and `clearHeight = storyHeight − floorAssemblyDepth` (L122465-122475).
- **Cores** (`a3e` L68425, `Kb` L68454):
  - `position` is the core's **min corner**; `width` runs along x and `depth` along y.
  - A core that crosses the perimeter is boolean-subtracted as a notch. An interior core becomes a hole.
  - A beam end that is split at a core gets `{type:"core", core:i}`.
- **Automatic core placement** (`S_e` L121547):
  - The core goes at the candidate point farthest from the perimeter and from other cores. The candidates are midpoints of vertex pairs.
  - Its size is `round(clamp(0.65·clearance, 12, 30))` ft, square.
- **Beam cleanup** (`uMe` L124001):
  - Collinear beams meeting at an end with no column are merged, and the merged beam takes the larger `tributaryWidth`.
  - A single missing end is snapped to a column within 3.28 ft.
  - A beam with no support is dropped.
  - Purlins never get `data.columns`: their support on the girders is only implied by the geometry.
- **Point-supported timber span limits** (`f_e` L121260-121285):
  - spanDirection Y: `maximumXSpan` = the panel's maximum span (CLT 22, MPP 24, DLT 22 ft) and `maximumYSpan` = the supplier **panel width**. With X the two swap.
  - **One bay dimension must be ≤ the panel width.** The default mass-timber point-supported bay is therefore 11.5×15 ft.
- **Default span direction**, set by the wizard (`Uwe`/`zwe` L95678-95725): `(Mass Timber && system != "Purlin on girder") || Steel ? "X" : "Y"`.

## 1. Branch3D domain model, distilled

### 1.1 Architecture pattern

`controls` (flat zod settings, `mCe` L91194) and `geometry` (`xIncrements`, `yIncrements`) feed a pure generator `pMe(n)` (L124266), which regenerates everything on every edit.

1. Pipeline: `aMe` (one typical floor) → `C_e` (stamps material and profile on every member) → copy per storey (`PN`, `JN`) → substructure override (`x_e`) → size (`VEe`, which mutates `width`/`depth`/`data.*`) → `Plate` removes beams → `mMe` (grade slab).
2. The output is `{ levels[], gradeSlab, gradients }`, which then feeds statistics (L122450), validation (`f_e`) and carbon.

There is no incremental update and no per-member input: every member is derived from the settings. Semantics are assigned by rules that stamp `data.*` fields on plain member records.

### 1.2 Entities and fields (verbatim identifiers)

| Entity | Source | Fields |
|---|---|---|
| **Settings** (`controls`) | `mCe` L91194 | `numStories`, `subStories`, `storyHeight`, `subStoryHeight`, `spacingX`, `spacingY`, `maxPurlinSpacing`, `maxPanelLength`, `spanDirection`, `polyline`, `cores`, `coreData`, `structuralSystem`, `buildingType`, `deadLoad`, `liveLoad`, `fireRating`, `column/beam/floorFireProtection`, `concreteTopping`, `columnMaterial`, `columnProfile`, `beamMaterial`, `girderProfile`, `purlinMaterial`, `purlinProfile`, `floorSlabMaterial`, `floorSlabProfile`, `*SupplierLocation`, `*Supplier`, `location`, `units`, `singleStoryMode`, `colors`, `debug` |
| **Grid** (`geometry`) | same | `xIncrements: number[]`, `yIncrements: number[]` (absolute positions, sorted) |
| **Gridline** (derived) | `Lq` L123647 | `{segment, editable, increment, index}`. The bounding-box lines have `index -1/-2` and `editable:false`. The segment is extended 1 ft past the bounding box. |
| **Column** | `T7` L123697 | `{type:"Column", origin:[x,y,z], angle, width:1, length:1, height, data:{id, isBoundary, profile, material, neighborBeams:[], crossSection}}` |
| **Beam** (girder, perimeter beam, purlin) | `Nf` L123720 | `{type:"Beam", origin, angle, width, length, depth:1, startPoint, endPoint, data:{id, isBoundary, tributaryWidth, profile, material, columns:[start,end], crossSection}}`. Supports are `{type:"index", index}` or `{type:"core", core}`. Also carries `data.skipped`. |
| **FloorPlate** | `aMe` L123958 | `{area:[[x,y,z]], thickness:0.5, shape, region:{polygon, holes}, data:{material, profile, centroid, maxDepth, steelCrossSection, sizingValidity}, topping?:{thickness, data}}` |
| **Core** | `pCe` | `{width, depth, position:[x,y]}`. `cores` is `"0"`/`"1"`/`"2"`, and `coreData.slice(0, cores)` gives the active ones. |
| **PanelLines** | `gMe` L124327 | `{lines, approximatePanelCount}` |
| **SpanInformation** | `WMe` L124445 | `{mainSpanIntervals, secondSpanIntervals, minorSpan, majorSpan}`. Each interval is `{direction:"X"\|"Y", start, end, span, weight}` (`oversize` is added in `Beam` mode). |
| **Level** | `aMe` return + `hMe` L124256 | `{columns, beams, purlins, floorPlate, panelLines, spanInformation, footings, data:{substructure?}}` |
| **Footing** | `GEe` L123092 | `{origin, width, depth, data:{}}`, only on `levels[0]` |
| **GradeSlab** | `mMe` L124302 | `{area, shape, thickness:0.5, data:{material:"Concrete", profile:"Flat plate", centroid}}` |
| **Validation** | `f_e` L121260 | `oversizeBeams/Columns/Purlins`, `oversizeIntervals`, `maximumXSpan`, `maximumYSpan`, `maximumPurlinSpan`, `typicalX/Y/PurlinOversize`, `badXGridlines`, `badYGridlines`, `gridlineError` |
| **Statistics** | L122487 | `levels`, `subLevels`, `sqftPerLevel`, `grossSqft`, `grossSubSqft`, `floorToFloorHeight`, `subFloorToFloorHeight`, `totalHeight`, `totalSubHeight`, `slabHeight`, `beamHeight`, `girderHeight`, `purlinHeight`, `clearHeight`, `floorAssemblyDepth`, `width`, `length` |

### 1.3 Relationships

- **Beam to column:** `Beam.data.columns[0|1]` points to a column index or to a core. Each `Column.data.neighborBeams` holds the beam ids, which is the inverse incidence.
- **Purlin to girder:** implicit only. There is no reference.
- **Level to members:** every level is a copy of one typical plan. Beams are sized once on `levels[0]` and the sizes copied. Columns are sized per level with `(levels.length − index) × tributary`.
- **Core:** a hole in `floorPlate.region`. Columns inside it are removed, beams inside it removed, crossing beams split, and the split end is supported on the core.
- **Grouping keys in outputs:** `zone` (`"Foundation" | "Substructure" | "Superstructure"`) and `component` (`"Footing" | "Slab on Grade" | "Floor" | "Beam" | "Column" | "Purlin" | "Topping"`).

### 1.4 Enums (verbatim)

- **`structuralSystem`:** `"Plate" | "Beam" | "Purlin"`.
  - Wizard labels: "Point supported" / "Post and beam" / "Purlin on girder".
  - UI labels: "Flat plate / point-supported" / "Post and beam" / "Purlin on girder / girder with secondary beams".
- **`spanDirection`:** `"X" | "Y"`.
- **`cores`:** `"0" | "1" | "2"`.
- **`buildingType`:** `"Normal" | "High" | "Storage" | "Unset"`.
- **`fireRating`:** `"180" | "120" | "60" | "0"`.
- **Materials:**
  - column, beam and purlin: `"Glulam" | "Concrete" | "Steel"`
  - floor slab: `"Timber" | "Concrete" | "Composite"`
- **Profiles:**
  - column: `"Square" | "Rectangular" | "Round" | "W" | "HSS" | "Circular"`
  - girder: `"Rectangular" | "Square" | "Double girder" | "Slab band" | "Precast girder" | "W" | "HSS" | "Open web joist"`
  - purlin: `"Rectangular Timber" | "W" | "Double purlin" | "Rectangular Concrete" | "Slab band" | "HSS" | "Open web joist"`
  - floor slab: `"Cross-laminated timber" | "Mass plywood panel" | "Nail laminated timber / Dowel-laminated timber" | "Glulam beams on flat" | "Flat plate" | "Hollow core" | "Double tee" | "Slab on metal deck" | "Roof deck"`
- **Fire protection:** `"Exposed" | "safp12" | "safp38" | "safp50" | "Intumescent paint" | "gypsum5840" | "gypsum5880" | "gypsum58120"`.
- **Preset and share keys:** `Stories`, `Height`, `SubStories`, `SubStoryHeight`, `Polyline`, `SpacingX`, `SpacingY`, `SpanDirection`, `System`, `PurlinSpacing`, `BeamMaterial`, `ColumnMaterial`, `PurlinMaterial`, `FloorMaterial`, `Cores`.

### 1.5 Generation rules, in the order `aMe` → `pMe` runs them

1. **Gridlines.** `Lq` builds both families, clipped to the polygon's bounding box, then crosses them with the perimeter (`O8`).
2. **Columns** (`b()`), in three passes:
   - at every polygon vertex, with `isBoundary:true`;
   - at every point where a gridline crosses the perimeter, also `isBoundary:true`;
   - while walking the girder lines, at every interior crossing with the other family.
   - Columns closer than **3.28 ft** are merged.
3. **Perimeter beams** (`w(Nf(..., true, trib, 140))`): one per perimeter segment, split at the vertices and at the gridline crossings.
4. **Girders:** along each `F` line, clipped by `hW`, split at every crossing. Their `tributaryWidth` is half the distance to each neighbour line, added together. Non-boundary beams whose ends are both boundary columns, or both within 0.01 of the perimeter, are dropped.
5. **Purlins** (`Purlin` only): per bay between two girder lines. `Te = max(1, ceil(bay/maxPurlinSpacing))` at spacing `Re = bay/Te`, the first one on the gridline, `tributaryWidth = Re`. Duplicates and purlins whose ends are both boundary columns are dropped, and the rest are clipped to the polygon.
6. **Floor plate:** the region is the polygon minus the cores. A `topping` is added when `concreteTopping > 0` and the floor slab material is Timber.
7. **Cleanup** (`uMe`): link ends to columns, merge collinear beams, snap, drop unsupported beams.
8. **Cores** (`fMe`): remove columns inside, remove beams fully inside, split crossing beams and support the split ends on the core.
9. **Panels** (`gMe`): break lines where the running sum of bays exceeds `maxPanelLength`, strips at the supplier panel width, and `approximatePanelCount`. Span intervals come from `WMe`.
10. **Storeys** (`pMe`): stamp material and profile (`C_e`). Substories get a negative index, `substructure`, and are forced to concrete (`x_e`). Superstructure storeys are exact copies.
11. **Sizing** (`VEe`). Then `Plate` empties `beams` on every superstructure level. The grade slab is added (`mMe`) and footings sized (`GEe`).

## 2. What our Grid must represent

The Grid should split the way Branch does: a **`GridSettings`** input (Branch's `controls`, strings allowed) feeds a **`Grid`** (a graph with vertex, edge and face attributes, doubles only), which feeds wood elements. Keep generation a pure function of the settings, as Branch does, but generate **per storey** rather than copying one typical floor. That is the gap Branch Concept names ("assign different structural systems and materials by floor", setbacks).

| Concept | Branch Lite (verbatim) | Branch Concept (announced) | Grid representation |
|---|---|---|---|
| **Storeys** | `numStories`, `storyHeight`, `subStories`, `subStoryHeight`; `levels[]`; `data.substructure`; datum = top of storey | per-floor system/material, stepbacks | A `stories` table `{elevation, height, polyline, holes, substructure}`, bottom-up, with non-uniform heights. Every vertex, edge and face gets `story` (index) and `substructure` (0/1). |
| **Grid lines** | `xIncrements`/`yIncrements`, absolute, axis-aligned, no labels; `Lq {segment, editable, increment, index}` | not described | Two axis families in a grid `Plane frame`, so rotation comes free: `x_increments`, `y_increments` in frame coordinates, plus an optional label table ("A..", "1.."). Vertex attributes `line_x`, `line_y` hold the increment index, or −1 off-grid. |
| **Footprint** | `polyline` (free angles, forced counter-clockwise, grown via control points) | setbacks, irregular forms | A polyline per storey (setback = a different polyline on a higher storey). Holes for cores and openings. |
| **Bays** | implicit: the cells between consecutive increments, clipped | "Multi-bay" | One **face per bay per storey**, clipped to the footprint (cells outside are not created, like compas_grid's inactive cells). Attributes: `is_floor`, `bay_x`, `bay_y`, `span_x`, `span_y`. |
| **Zones** | none (one system for the whole building) | per floor | A face attribute `zone`. A zone table in the settings holds the system parameters and names. |
| **System per bay** | `structuralSystem`, `spanDirection`, `maxPurlinSpacing`, `floorSlabProfile`, panel width, `maxPanelLength` | per floor | Face attributes: `structural_system` (0 plate, 1 beam, 2 purlin), `span_direction` (0 X, 1 Y; the **girder** direction), `max_purlin_spacing`, `purlin_count` (derived), `deck` (profile code), `panel_width`, `max_panel_length`, `deck_direction` (derived; 2 = two-way). |
| **Member roles** | `type:"Column"`, `type:"Beam"` with `isBoundary`, `purlins[]` list, `floorPlate`, `topping`, `footings`, `gradeSlab` | + per-element overrides | Edge flags `is_column`, `is_girder`, `is_purlin`, `is_boundary`. Face flags `is_floor`, `is_topping`, `is_grade_slab`, `is_wall`. Vertex flags `is_boundary`, `is_footing`. Flags rather than one role code, because a perimeter beam is `is_girder` + `is_boundary` and `*_where({{"is_girder",1}})` composes. |
| **Supports** | `data.columns:[{type:"index"},{type:"core"}]`, `neighborBeams` | — | Implicit through incidence (the edge's end vertex carries the column). A vertex on a core wall stores `core` = core index. `neighborBeams` becomes an incidence query, so store nothing. |
| **Tributary** | `tributaryWidth`; column load = Σ `trib·length/2` of the neighbour beams × levels above | — | Edge `tributary_width`. Column vertex/edge `tributary_area` and `stories_above`. This is geometry, so compute it in the template (it is a sizing hook, §4). |
| **Cantilevers** | none ("cantilevers…can't be represented in Concept Lite") | not named | Edge `cantilever` (length past the last support). Face-edge `overhang`. Allowed only through an explicit rule (§5). Branch's cleanup would drop such a beam as unsupported. |
| **Cores / walls** | `coreData {width, depth, position}` rectangles: holes, beams split and supported, "not sized… block out the floor framing and track gravity loads downwards" | "slab openings" | A closed polygon per core plus a storey range. This produces a floor hole, `is_wall` + `is_core` + `core` faces (vertical loops), and `core` on the vertices where a beam is split. Facade walls come from compas_grid-style tags (`is_facade`). |
| **Openings** | none | "Slab openings" | Holes in floor faces, with `opening` index on the face. |
| **Off-grid columns / transfers** | none | "Off-grid columns", "Transfer slabs" | A column vertex with `line_x = line_y = −1`. `is_transfer` on the edge or face that carries a column with no column below. |
| **Panels** | `panelLines`, `approximatePanelCount`, supplier `width` | override panel sizing | Floor faces split into strips at `panel_width` and breaks at `max_panel_length`. `panel_count` on the face. |
| **Vertical stacking** | datum = top of storey; beams hang below; deck on top; glulam girder drop `min(purlinDepth, 8 in)` | clear heights shown | Per-storey `datum`. Edge `depth` and `drop`. Derived `floor_assembly_depth` and `clear_height` on the storey or its faces. |
| **Heads** | none | none | Not a Branch concept. Carry it over from compas_grid: vertex `is_head` where a column top meets beams. |
| **Grade slab, footings** | `gradeSlab`, `footings` (pads + 1.5 ft pedestal in the render) | — | A face `is_grade_slab` at the base of the lowest storey, and a vertex flag `is_footing` under the columns of the lowest storey. |

**Encoding.** Attribute values are `double` in both kernels. Code the enums as numbers (`structural_system`, `span_direction`, `material`, `profile`, `deck`). Keep the string names, supplier choices and the per-zone material and profile in `GridSettings` or a zone table, never in attributes.

## 3. Branch names to adopt verbatim (snake_cased)

| Branch identifier / UI term | Our name | Kind | Encoding / note |
|---|---|---|---|
| `structuralSystem` "Plate"/"Beam"/"Purlin" | `structural_system` | face attribute + setting | 0 `plate`, 1 `beam`, 2 `purlin`. Use the UI names "point supported" / "post and beam" / "purlin on girder" for example names, e.g. `templates_grid_purlin_on_girder`. |
| `spanDirection` "X"/"Y" | `span_direction` | face attribute + setting | 0 X, 1 Y. Document it as the **girder** direction ("Girders / primary beams span along the model's X-axis"). |
| (derived in `gMe`) | `deck_direction` | face attribute | `span_direction XOR (system==purlin)`; 2 = two-way (plate) |
| `xIncrements`, `yIncrements` | `x_increments`, `y_increments` | settings / axis | Absolute positions in the grid frame, not steps |
| `spacingX`, `spacingY` | `spacing_x`, `spacing_y` | settings | Typical bay, used by reset and auto-extend |
| `maxPurlinSpacing` | `max_purlin_spacing` | face attribute + setting | UI: "Maximum spacing between purlins / secondary beams" |
| `maxPanelLength` | `max_panel_length` | face attribute + setting | Default 60 ft = 18288 mm |
| `numStories`, `storyHeight`, `subStories`, `subStoryHeight` | `num_stories`, `story_height`, `sub_stories`, `sub_story_height` | settings | Use **`story`** for the index attribute, not `level`: `compute_contacts(level)` already means tree depth. This replaces `"storey"` in `report_wood_side.md` so the spelling matches Branch. |
| `data.substructure` | `substructure` | attribute on everything | 0/1 |
| `isBoundary` | `is_boundary` | vertex + edge | Perimeter column / perimeter beam |
| `tributaryWidth` | `tributary_width` | edge | Geometric, written by the template |
| `coreData {width, depth, position}`, `cores` | `cores` (width, depth, position) | settings | `position` = min corner. Generalize to a polygon, keeping `from_rectangle(width, depth, position)`. |
| `floorPlate`, `topping`, `gradeSlab`, `footings`, `panelLines`, `approximatePanelCount` | `floor`, `topping`, `grade_slab`, `footing`, `panel_lines`, `panel_count` | roles / outputs | `is_floor`, `is_topping`, `is_grade_slab`, `is_footing` |
| `mainSpanIntervals`, `secondSpanIntervals`, `minorSpan`, `majorSpan`, interval `{direction, start, end, span, weight}` | same, snake_cased | output struct | Geometry only, so it can stay in scope |
| UI roles "Girder", "Purlin", "Secondary Beam", "Column", "Deck", "Core" | `is_girder`, `is_purlin`, `is_column`, `is_floor`, `is_core` | flags / element `name` | Pass `"girder"` / `"purlin"` / `"column"` / `"deck"` as the wood element `name` argument |
| `concreteTopping` | `topping_thickness` | setting / face | A geometry layer (in scope); its self-weight is not |
| `floorAssemblyDepth`, `clearHeight`, `girderHeight`, `purlinHeight`, `slabHeight`, `floorToFloorHeight` | `floor_assembly_depth`, `clear_height`, `girder_depth`, `purlin_depth`, `slab_depth`, `story_height` | derived | Computed from the `depth` attributes |
| `crossSection` ("WxDmm", "WOffChart") | `width`, `depth` (numbers) + `oversize` flag | edge / face | Strings cannot be attributes |
| `badXGridlines`, `badYGridlines` | `bad_gridline` | per-increment flag or vector on the axis | Written by an external check |

**Names not to adopt:**
- **`level` / `levels`:** clashes with the tree-depth meaning.
- **`type:"Beam"` for purlins and perimeter beams:** use separate flags.
- **`"Plate"` as a system value:** it collides in reading with `wood_session::Plate`. Keep the code name `plate`, but call the builder `to_deck`, not `to_plate`.
- **`increment`:** it means a position, not a step.
- **`data.id`:** we use graph indices.

## 4. Out of scope for a geometry template, and the hooks to leave

| Concern | Branch fields (verbatim) | The template writes (a later pass reads) | The later pass writes (the template reads) |
|---|---|---|---|
| Gravity loads, live load reduction | `deadLoad`, `liveLoad`, `buildingType` Normal 15/65, High 25/100, Storage 25/125 psf; `1.2D+1.6L`; `0.25+15/√(K·A)` with K=2 for beams, 4 for columns; perimeter beams take a storey-height line load | edge `tributary_width`, `length`, `span`, `is_boundary`; vertex/column `tributary_area`, `stories_above`; storey `height` | — |
| Member sizing | `crossSection`, `width`, `depth`, `maxDepth`, `oversize`, `extrapolated`, `"WOffChart"` | defaults per role: Branch's initial column 1×1 ft, girder 180 mm, perimeter 140 mm, purlin 120 mm wide × 1 ft deep, slab 0.5 ft | edge `width`, `depth`; face `thickness`; `oversize` (0/1). The builders read these, so the geometry follows the sizes. |
| Per-element override | Concept: "Override individual beam, column, and floor panel sizing" | — | explicit `set_edge_attribute(e,"depth",…)`, which wins over the defaults (`update_default_edge_attributes`) |
| Fire | `fireRating` "180/120/60/0"; `*FireProtection`; char `25.4·1.2·1.5·(t/60)^0.813` mm; `bC` minutes | `fire_rating` (minutes, numeric) passed through per storey or zone | `protection_thickness` on edges and faces. Stacking reads it, because `floorAssemblyDepth` adds the FP layers. |
| Materials, profiles, suppliers | `columnMaterial`, `girderProfile`, `purlinProfile`, `floorSlabMaterial`, `floorSlabProfile`, `*Supplier`, `*SupplierLocation`, panel catalogue `[supplier, type, thickness_mm, plies, panelId, stiffness, strength, width_ft, "y"\|"x"]` | numeric `material` / `profile` codes per element, set by zone rules (like `C_e`/`x_e`) | `panel_width` feeds back into the geometry (it sets the panel strips and the point-supported bay limit) |
| Span validity | `maximumXSpan`, `maximumYSpan`, CLT 22 / MPP 24 / DLT 22 ft, concrete 12.01 m, composite 14/13/12 ft; messages "Exceeds maximum span of …", "Typical span exceeds maximum for current loads." | face `span_x`, `span_y`; the axis intervals | `bad_gridline`, `oversize`. The template can offer a pure geometric `compute_bad_gridlines(max_x, max_y)` that takes the limits as arguments. |
| Footings | `GEe` pads from column load | vertex `is_footing` + `tributary_area × stories_above` | vertex `width`, `depth` |
| Carbon, quantities, cost | `CO2eA1A3`, `CO2eA4`, `CO2eA5`, `biogenicCO2e`, SCORS rating, `*Pieces`, `*Per1000Sqft`, routes | counts via `*_where`, volumes from the element meshes, `panel_count` | — |
| Lateral / core design | none ("does not analyze … wind, earthquake"); "(excl Core)" | wall and core faces exist, with `core` index | — |
| Location, units | `location`, `units` | — (the template works in mm) | — |

## 5. Generators and rules `grid.h` should offer

This follows the `wood_chevron` style: header-only `inline` functions in `namespace wood_grid`, no input throws, and `vertex_*` names mirroring the kernel `Graph`/`Mesh`. Defaults are Branch values converted to mm.

```cpp
namespace wood_grid {

/// Inputs as Branch's controls: grid, storeys, footprint, cores, and per-zone system names.
struct GridSettings {
    session_cpp::Plane frame; // Grid axes; rotated grids come free.
    std::vector<double> x_increments{0, 4572, 9144, 13716, 18288}; // Absolute positions along frame x.
    std::vector<double> y_increments{0, 4572, 9144, 13716, 18288}; // Absolute positions along frame y.
    std::vector<double> story_heights{3658, 3658}; // Bottom-up; the first sub_stories are substructure.
    int sub_stories = 0; // Basement storeys.
    std::vector<session_cpp::Polyline> polylines; // One footprint per storey; one entry means all storeys.
    std::vector<session_cpp::Polyline> cores; // Closed loops cut from every floor.
    double merge_distance = 1000.0; // Branch 3.28 ft.
};

/// Points, lines and bay loops over all storeys with double attributes on every vertex, edge and face.
struct Grid {
    std::vector<session_cpp::Point> vertices;
    std::vector<std::array<size_t, 2>> edges;
    std::vector<std::vector<size_t>> faces;
    std::vector<std::vector<std::vector<size_t>>> face_holes;
    // vertex/edge/face attribute maps + defaults, API named as session_cpp::Graph / Mesh:
    // update_default_{vertex,edge,face}_attributes, {vertex,edge,face}_attribute, set_*_attribute,
    // vertices_where, edges_where, faces_where, *_where_predicate, vertex_edges, edge_faces, edge_line, face_polyline
};
}
```

### A. Generators (constructors)

| # | Function | Branch equivalent | Beyond Branch |
|---|---|---|---|
| A1 | `Grid from_settings(const GridSettings&)`: bay faces per storey, clipped to that storey's footprint, minus cores; no members yet | `aMe`+`pMe` input stage | per-storey footprints (setbacks) |
| A2 | `std::vector<double> increments_from_spacing(double start, double end, double spacing)` and `increments_from_count(start, end, count)` | the "N @ spacing : total" widget, `resetXGrids(spacing)`, `ZW` | — |
| A3 | `Grid from_bays(origin, nx, ny, spacing_x, spacing_y, story_heights)`: rectangle = bounding box of the increments | the wizard with `zM` spacings | — |
| A4 | `Grid from_lines(lines, floors, walls, precision)`: weld and classify arbitrary input | — | compas_grid path; irregular and non-orthogonal |
| A5 | `GridSettings` edit helpers: `set_increment`, `add_increment` (midpoint to the next line), `remove_increment`, `reset_increments(axis, spacing)`, `extend_increments(spacing)` (adds lines when the footprint grows, as `sQ`), `set_polyline` (normalizes to counter-clockwise) | store `setX/addX/removeX/resetXGrids`, `sQ`, perimeter push/pull | — |
| A6 | `Polyline core_from_rectangle(width, depth, position)` (position = min corner) and `core_auto(settings)` (farthest-from-perimeter candidate, side `clamp(0.65·clearance, 3658, 9144)`) | `pCe`, `S_e` | polygon cores |

### B. Rules (`compute_*`, run in this order; each writes attributes only)

| # | Rule | Writes | Branch source / note |
|---|---|---|---|
| B1 | `compute_columns(grid)` | column edges per storey at polygon vertices and perimeter crossings (`is_boundary`=1) and interior crossings; `line_x`, `line_y`; merged within `merge_distance`; dropped inside cores | `T7`/`b()`, `fMe` |
| B2 | `compute_boundary_beams(grid)` | perimeter beam edges split at column vertices, `is_girder`=`is_boundary`=1, `tributary_width` by the \|cos\| rule per system | L123840-123857 |
| B3 | `compute_girders(grid)` | per face `span_direction`: girders on the lines of the other family, split at crossings, perimeter duplicates dropped, `tributary_width` = half-distances (without the `\|\| 0` quirk) | L123872-123916 |
| B4 | `compute_purlins(grid)` | per `structural_system==2` face: `purlin_count = max(1, ceil(bay/max_purlin_spacing))` at equal spacing, first on the gridline, clipped, `tributary_width` = spacing | L123920-123947 |
| B5 | `compute_point_supported(grid)` | removes the beam edges of `structural_system==0` faces above the substructure (perimeter beams included) | `pMe` L124284 |
| B6 | `compute_cores(grid)` | splits beams at core loops, sets `core` on the split vertices, `is_wall`+`is_core` faces per storey, floor holes | `fMe`, `a3e`, `Kb` |
| B7 | `compute_supports(grid, bool cantilever = false)` | merges collinear beams across unsupported ends, snaps within `merge_distance`, drops unsupported beams; with `cantilever` it tags `cantilever` = overhang length instead of dropping | `uMe`; the cantilever branch is beyond Branch |
| B8 | `compute_deck_direction(grid)` | face `deck_direction` | `gMe` L124335 |
| B9 | `compute_panels(grid)` | `panel_lines` per face (breaks where the cumulative bay length exceeds `max_panel_length`, strips at `panel_width`), `panel_count` | `gMe`, `Aq` (CLT 10 ft, MPP 12 ft, DLT 10 ft) |
| B10 | `compute_span_intervals(grid)` | face `span_x`, `span_y`; per-storey `main_span_intervals`, `second_span_intervals`, `minor_span`, `major_span` | `WMe` |
| B11 | `compute_tributary(grid)` | column `tributary_area` (Σ half of each neighbour beam's trib·length), `stories_above` | `VEe` L123029-123036 |
| B12 | `compute_substructure(grid)` | `substructure`=1 and material/profile codes forced to concrete / flat plate on substories | `x_e` |
| B13 | `compute_datums(grid)` | per storey `datum` = top of the storey; girder and purlin tops at the datum; `drop` on girders = `min(max purlin depth, 203)` for glulam purlin-on-girder; deck at `[datum, datum+thickness]`; `floor_assembly_depth`, `clear_height` | `JN`, `ZN` L123088, stats L122465 |
| B14 | `compute_heads(grid)` | vertex `is_head` where a column top meets beams | compas_grid; not in Branch |
| B15 | `compute_transfers(grid)` | `is_transfer` on the girder or floor under a column with none below | Concept "transfer slabs", "off-grid columns" |
| B16 | `compute_grade_slab(grid)`, `compute_footings(grid)` | `is_grade_slab` face, `is_footing` vertices | `mMe`, `GEe` |
| B17 | `compute_bad_gridlines(grid, max_span_x, max_span_y)` | `bad_gridline` on both ends of each interval over the limit | `f_e` (the limits come from outside) |

### C. Assignment rules (the per-zone flexibility Branch lacks)

- `assign_system(grid, faces, structural_system, span_direction, max_purlin_spacing)`: per bay.
- `assign_zone(grid, faces, zone)`, applied from `GridSettings.zones`.
- `assign_story(grid, story, ...)`: Concept's "different structural systems and materials by floor".
- Precedence: element override > bay > zone > storey > `update_default_*_attributes` (global, which equals Lite).
- Run B2-B9 **after** assignment, because they read the per-face system.
- A girder line shared by two bays with different `span_direction` should become a girder if either bay needs it. Branch never faces this; it is our rule to define.
- `add_column(grid, point, story)` / `remove_column(grid, vertex)` for off-grid and one-off column shifts (the FAQ says "one-off column shifts" cannot be done in Lite).
- `add_opening(grid, polyline, story)` for slab openings.

### D. Element builders (`to_*`, which read `width`/`depth`/`thickness` attributes so sizing can drive the geometry)

- **`to_column(grid, edge)`:** trimmed between the datums or heads.
- **`to_girder(grid, edge)` / `to_purlin(grid, edge)`:** hung below the datum, girders applying `drop`. The wood `Beam` is square-only, so rectangular sections need the `Column`-with-horizontal-axis workaround from `report_wood_side.md` §8.
- **`to_deck(grid, face)`:** one `Plate` per panel strip, holes for cores and openings.
- **`to_topping(grid, face)`.**
- **`to_wall(grid, face)`:** cores and facades.
- **`to_head(grid, vertex)`.**
- **`to_grade_slab(grid, face)`, `to_footing(grid, vertex)`:** `Block`s.
- Pass the role as the element `name` (`"column"`, `"girder"`, `"purlin"`, `"deck"`, `"wall"`, `"head"`) so the viewer and `face_contacts(..., names)` can filter on it.

### E. Test oracle (hand-derived, not run)

Branch defaults: 60×60 ft square, increments `[0,15,30,45,60]` on both axes, one core `{20,20,[20,20]}`, Plate system.

**24 columns per storey:**
- 16 on the perimeter (the 5×5 grid perimeter);
- 9 at interior intersections;
- minus 1 at (30,30) inside the core.

There are 0 superstructure beams (Plate).

With the system switched to `Beam` and span X:
- girders on y = 15/30/45, split at x = 15/30/45 (4 segments per line);
- the y=30 segments that touch the core are split at x = 20/40 and supported on the core;
- plus 16 perimeter beams.

## What I could not find / not verified

- **How Branch Concept models things internally** (grids, zones, per-floor data). There are no docs. A web search on 2026-09-22 found only the waitlist ("SUMMER 2026 Branch Concept Pilots"), the homepage and the beta post.
- **Features Branch has no representation for:** grid labels, rotated or radial grids, cantilevers, heads, and walls other than rectangular cores.
- **Inferred, not run:**
  - the vertical placement read from the three.js transforms;
  - the single-bay perimeter-to-perimeter girder drop;
  - the §5E counts.
- **The FAST+EPP vocabulary** could not be cross-checked: the captures are blocked or empty, and `grid_design.md` has not been written.
- **The second loop of `uMe`'s `y()`** reads `i[b]` where `o[b]` is meant (L124102-124104). That is a Branch bug: do not port it literally.

## Sources

- https://concept.branch3d.com/ and bundle https://concept.branch3d.com/assets/index-CxNXZKiq.js (local copy: `scratchpad/branch3d/pretty.js`)
- https://www.branch3d.com/ , https://www.branch3d.com/waitlist , https://www.branch3d.com/help , https://www.branch3d.com/insights/branch-concept-beta-is-coming-this-spring (local: `scratchpad/b3d/`)
- https://canada.constructconnect.com/joc/news/technology/2023/01/structural-engineers-are-heading-to-the-rd-lab
- https://shapetofabrication.com/presentation/branching-innovation-timber-design-and-construction-with-computational-processes/
- Kernel: `/home/petras/code/code_cpp/wood_research/session/session_cpp/src/graph.h` (lines 37, 101, 175-176, 262-295) and `.../session_cpp/src/mesh.h` (lines 724-789)
- Input reports: `/tmp/claude-1000/-home-petras-code-code-cpp-wood-research/cd17883b-ad50-44cc-bbcd-c4f797944a70/scratchpad/report_compas_grid.md`, `/tmp/claude-1000/-home-petras-code-code-cpp-wood-research/cd17883b-ad50-44cc-bbcd-c4f797944a70/scratchpad/report_wood_side.md`