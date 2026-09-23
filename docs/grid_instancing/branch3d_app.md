# Branch3D Concept Lite, read from its JS bundle (read-only)

Concept Lite is one file, `assets/index-CxNXZKiq.js` (3.0 MB). There are no source maps and no other chunks, workers or WASM. It is React plus react-three-fiber, with zustand for state, zod for the schema, and Radix UI. The structural model, sizing and carbon all run in the browser on the main thread. The only network calls are Amplitude analytics, Mapbox geocoding (address search) and a link shortener used for sharing. `manifest.json`, `robots.txt` and `.vite/manifest.json` all just return the page HTML.

Everything I downloaded is in `/tmp/claude-1000/-home-petras-code-code-cpp-wood-research/cd17883b-ad50-44cc-bbcd-c4f797944a70/scratchpad/branch3d/`: `index.html`, `index.js`, `index.css`, and a prettier-formatted `pretty.js`. All line numbers below refer to `pretty.js`.

## 1. Project model: one flat zod schema (L91194–91370)
There are no Site, Building or Level objects that the user edits. The whole project is one flat set of settings (`mCe`, parsed by `UW()`). Every field falls back to its default on its own if it is invalid. Internal units are feet and psf.

```
units: "Metric"|"Imperial" (default "Imperial")
singleStoryMode, debug, colors: bool
numStories=2, subStories=0, storyHeight=12, subStoryHeight=12
spacingX=15, spacingY=15, deadLoad=15 (psf SDL), liveLoad=65
maxPurlinSpacing=10, maxPanelLength=60
spanDirection: "X"|"Y" (default "Y")
polyline: [[x,y,z]...] default 60x60 square
xIncrements / yIncrements: number[] default [0,15,30,45,60]   <- the grid
cores: "0"|"1"|"2";  coreData: [{width, depth, position:[x,y]}]
structuralSystem: "Plate"|"Beam"|"Purlin" (default "Plate")
buildingType: "Normal"|"High"|"Storage"|"Unset"
location: {name, coordinates:{latitude,longitude}, continent: "North America"|"Europe"|"Asia"|"Africa"|"Oceania"|"South America"}
fireRating: "180"|"120"|"60"|"0" (default "120")
columnFireProtection / beamFireProtection / floorFireProtection:
   "Exposed"|"safp12"|"safp38"|"safp50"|"Intumescent paint"|"gypsum5840"|"gypsum5880"|"gypsum58120"
concreteTopping = 2in (stored in ft)
columnMaterial: "Glulam"|"Concrete"|"Steel";  columnProfile: "Square"|"Rectangular"|"Round"|"W"|"HSS"|"Circular"
beamMaterial / purlinMaterial: "Glulam"|"Concrete"|"Steel"
girderProfile: "Rectangular"|"Square"|"Double girder"|"Slab band"|"Precast girder"|"W"|"HSS"|"Open web joist"
purlinProfile: "Rectangular Timber"|"W"|"Double purlin"|"Rectangular Concrete"|"Slab band"|"HSS"|"Open web joist"
floorSlabMaterial: "Timber"|"Concrete"|"Composite"
floorSlabProfile: "Cross-laminated timber"|"Mass plywood panel"|"Nail laminated timber / Dowel-laminated timber"|"Glulam beams on flat"|"Flat plate"|"Hollow core"|"Double tee"|"Slab on metal deck"|"Roof deck"
column/beam/floorPanelSupplierLocation: "North America"|"Europe"|"Global"
columnSupplier/beamSupplier (glulam), floorPanelSupplier (panels) - lists in §6
```

**Other terms used in the app:**
- Levels are generated from the settings. Each level holds `{columns, beams, purlins, floorPlate, panelLines, spanInformation, footings}`, and a level whose `data.substructure` is true is a basement storey.
- Members use the `type` values `"Column"` and `"Beam"`. Purlins are also `"Beam"` objects, kept in a separate `purlins` list.
- The code groups results by `zone` ("Foundation" | "Substructure" | "Superstructure") and `component` ("Footing", "Slab on Grade", "Floor", "Beam", "Column", "Purlin", "Topping").
- The PascalCase names used by presets are `Stories, Height, SubStories, SubStoryHeight, Polyline, SpacingX, SpacingY, SpanDirection, BeamMaterial, ColumnMaterial, PurlinMaterial, FloorMaterial, System, Cores, PurlinSpacing`. `zPe()` at L141000 maps them onto the schema.

**Start wizard (L95525):**
- It has three steps: "Select Building Type" (Residential / Office / Institutional / Current), "Select Structural System" and "Select Structural Material".
- The system choices are "Point supported", "Post and beam" and "Purlin on girder". They map to Plate, Beam and Purlin.
- The material choices are "Mass Timber", "Concrete" and "Steel". Point supported and Steel exclude each other.
- The wizard button reads "Generate my model!".
- Default bay spacing per preset is in table `zM`. For example, Office Post and beam with Mass Timber is [30, 20] ft, and Point supported with Mass Timber is [11.5, 15].
- Presets `WC` hold stories, storyHeight, an L- or U-shaped polyline and cores. There is a separate `pointSupportedPolyline` because it has to fit the panel width.

## 2. Grid and how members are generated (`aMe`, L123772)
- **The grid is only two sorted lists of positions:** `xIncrements` and `yIncrements`. Grid lines are axis-aligned only. There are no rotated, skewed or radial grids, and no grid names (no A/B/1/2 bubbles). Members are identified only by a numeric `data.id`.
- **The footprint is a free polygon.** Its edges can be at any angle. Grid lines are clipped to the polygon (`hW`, `O8`).
- **Columns** (`T7`, profile "Square", default material "Glulam") go at:
  - every polygon vertex (`isBoundary: true`),
  - every point where a grid line crosses the perimeter (`isBoundary: true`),
  - every grid intersection inside the polygon.
  Columns closer than 3.28 ft to each other are merged (`M7` spatial hash).
- **Boundary beams** are created along every perimeter segment (`Nf(..., isBoundary=true, trib, 140mm)`). Their tributary width is half the adjacent bay, reduced by |cos| of the edge angle.
- **Girders** ("Beam" system):
  - `spanDirection` "X" puts girders along each Y grid line, running in the X direction, split at each X grid line.
  - `tributaryWidth` = half the distance to each neighbouring line, added together.
  - UI text: "Girders / primary beams span along the model's X-axis".
- **Purlins** ("Purlin" system):
  - They sit between two girder lines, running perpendicular to the girders.
  - Each bay holds `ceil(bay / maxPurlinSpacing)` purlins at equal spacing, width 120 mm.
  - They are clipped to the polygon.
- **"Plate" system:** beams are deleted on all superstructure levels. The slab is two-way and sits on columns only.
- **Cores** are 0–2 rectangles `{width, depth, position}` and become holes in the floor (`a3e`).
  - Columns inside a core are removed.
  - Beams entirely inside a core are removed.
  - Beams that cross a core boundary are split there, and the split end is supported by `{type:"core", core:i}` (`fMe`).
  - Cores and the lateral system are not designed: "This building's structure (excluding cores and lateral system) is rated …", and the carbon panel is titled "Carbon Summary (excl Core)".
- **Beams are then cleaned up (`uMe`):** each end is linked to a column (`data.columns: [{type:"index",index}]`) and to `neighborBeams`, collinear beams with a missing support are merged, and beams with no support are dropped.
- **Levels (`pMe`):**
  - One plan is generated and copied to each storey.
  - Substories are forced to concrete: Square columns and beams, "Rectangular Concrete" purlins, and a "Flat plate" floor (`x_e`).
  - A concrete grade slab is added (`mMe`), plus a spread footing under each column (`GEe`).
- **Floor panel layout (`gMe`):**
  - Panel break lines are placed where the running sum of bay widths exceeds `maxPanelLength` (60 ft).
  - Panel strips are the supplier's panel `width` (default CLT 10 ft, MPP 12 ft).
  - The output is `panelLines: {lines, approximatePanelCount}`.
  - `spanInformation` is `{mainSpanIntervals, secondSpanIntervals, minorSpan, majorSpan}`, where each interval is `{direction, start, end, span, weight}`.

## 3. Sizing (`VEe`, L122902), all hard-coded
**Loads and fire:**
- Topping self-weight is added at 150 pcf. Combinations are `1.2D+1.6L`, `D+L` and `L`.
- Live load reduction is the ASCE-7 form `0.25+15/sqrt(K·A)`: K = 2 for beams and purlins, K = 4 for columns, with a floor of 0.5 or 0.4.
- Boundary beams also carry an extra line load of one storey height.
- Fire: effective minutes = rating minus the minutes the protection provides (`bC`). For example, gypsum5880 gives 80 min and safp38 gives 120 min.

**Building type presets:** Normal = 15/65 psf, High = 25/100, Storage = 25/125 (SDL/LL). The UI inputs are tagged "SDL" and "LL". Fire rating options are "Unrated", "1 hour fire rating", "2 hour fire rating" and "3 hour fire rating".

**Members:**
- **Glulam beams (`eT`):** bending, fire-reduced bending with char `25.4·1.2·1.5·(t/60)^0.813` mm, and deflection with E = 12410 MPa. Width steps in 20 mm, depth in 40 mm (minimum 200 mm). Depth-to-width ratio is capped at 5, or 4 / 2.5 / 2.2 for rated beams. The result is written as `crossSection: "WxDmm"`.
- **Glulam columns (`nMe`):** Newton solve on a buckling formula, 20 mm steps, minimum 280 mm square.
- **Concrete beams (`Tq`):** 300 mm wide (600 if depth > 750), depth ≥ L/18.5.
- **Concrete columns (`rMe`):** minimum 300 / 400 / 450 mm for 60 / 120 / 180 min, 25 mm steps.
- **Concrete slabs:**
  - One-way: max(5", L/29), with 6"/L/25 and 7"/L/20 by load band.
  - Two-way: L/27, L/22, L/17. Between spans 2 and 3 times the short span it blends toward the one-way thickness.
  - Maximum span 12.01 m.
- **Steel:** lookup charts `{xStart, xIncrement, yStart, yIncrement, data}`.
  - Beams use span (m) by load; composite and non-composite have separate charts.
  - Columns use height by axial load (kN), with "W" or "HSS" charts.
  - Off-chart members become "WOffChart" and are coloured orange.
- **CLT / MPP / DLT one-way (`JEe`):**
  - Checks strength, deflection limit L/240 and a vibration stiffness table keyed by span 8–30 ft.
  - Needs ≥ 5 plies at ≥ 60 min. At 120 min, 2" is added.
  - Takes the first supplier panel that passes. If none passes, it extrapolates and sets `extrapolated: true` (oversize).
- **CLT two-way / Plate (`$Ee`):** table `LN {majorSpan, minorSpan, plies, grade:"V"|"E", thickness}`, for example 5-ply 6.875" up to 14×12 ft. Maximum panel span: CLT 22 ft, MPP 24 ft, DLT 22 ft.
- **"Glulam beams on flat" (GLT):** sized as a 1 ft wide glulam beam. It is marked comingSoon in the UI.
- **Composite deck:** `VM` catalogue ('PLW2-22 (2")' … 'PLW3-16 (4.5")' with `w, d, concreteD, deckD, steelW, averageConcrete`). It is indexed by load `[40,50,70,100,150,200]` psf and span, with a maximum of 14 / 13 / 12 ft depending on fire rating.

**Warnings shown:**
- "Exceeds maximum span of …"
- "Typical span exceeds maximum for current loads."
- "Some elements require custom sizes."
- Offending grid lines are highlighted via `badXGridlines` / `badYGridlines`, with the message "…exceeds typically manufactured panel thicknesses. Branch has assumed a custom, over-standard panel thickness…".

**Not present anywhere in the bundle:** cantilevers, transfer members, lateral loads (no seismic, wind or snow), a user deflection input, or an occupancy input beyond building type.

## 4. Options shown in the UI and their state
**Framing System:**
- "Flat plate / point-supported"
- "Post and beam"
- "Purlin on girder / girder with secondary beams"
- The purlin label changes to "Secondary Beam" when the material is not Glulam.

**Profiles:**

| Member | Material | Options |
|---|---|---|
| Girder | Steel | "Steel W"; "Steel HSS" is disabled; "Open web joists" is comingSoon |
| Girder | Concrete | "Rectangular"; "Slab band" and "Precast girders" are comingSoon |
| Girder | Glulam | "Rectangular"; "Square" and "Double girders" are comingSoon |
| Column | Glulam | "Square" only; Rectangular and Round are disabled |
| Column | Concrete | "Square" only; Rectangular and Round are disabled |
| Column | Steel | "Steel W" and "Steel HSS"; "Round HSS / Pipe" is comingSoon |

**Floors:**
- CLT, "Mass Plywood Panel (MPP) / Veneer Laminated Timber (VLT)", and "Dowel-Laminated Timber (DLT)". DLT cannot be used with Plate.
- "Glulam beams on flat (GLT)" is comingSoon.
- Concrete: "Flat plate". "Precast hollow-core planks" and "Precast double tees" are comingSoon.
- Composite: "Slab on metal deck". It cannot be used with Plate. "Roof deck" is comingSoon.
- NLT has no separate option; it is lumped into the DLT choice.

**Fire protection lists:** Glulam gets Exposed plus gypsum 40 / 80 / 120. Steel gets Exposed, 1/2" / 1.5" / 2" SAFP and Intumescent paint. Concrete gets Exposed only.

## 5. Grid and geometry editing
From the tour text: "Push and pull on faces and edges…", "Add control points to the building perimeter by clicking along the bottom edge", and "Adjust individual gridlines by clicking and dragging, using text inputs to set precise dimensions".

**Perimeter (footprint):**
- Faces move along their own normal; holding Shift constrains the move to an axis.
- Vertices drag freely, can be deleted with a minus button, and snap to grid lines (`U5`, `cRe`).
- When the footprint grows, new grid lines are added automatically at the typical spacing (`sQ`).

**Grid lines:**
- The zustand store actions are `setX/addX/removeX/setY/addY/removeY`, `resetXGrids(spacing)` / `resetYGrids(spacing)`, `setCores`, `setKey`, `setOption` and `setParameters`.
- The + button inserts a line at the midpoint to the next line. The − button deletes the line.
- Each bay has an editable dimension label. Its "setAll" button applies that value to every bay (it sets `spacingX`).
- There is an overall dimension in "N @ spacing : total" form. Changing N or the spacing regenerates uniform grid lines.
- Bays can have different widths, because the stored lists are explicit positions.
- There is a "Reset Grids" button.

**Stories:** edited through a "N @ h = total" dimension, limited to 1–50. Substories use the same form.

**Cores:** there is a 0 / 1 / 2 selector. A new core is auto-placed at the largest empty spot (`S_e`) and can then be dragged or resized.

**Other controls:** "Single-story view", "Color by size" (gradient legend for Beams / Purlins / Columns), and a Metric/Imperial toggle.

## 6. Suppliers and carbon (L121638–122610)
**Suppliers:**
- Glulam: 13 North American suppliers (Anthony Forest Products … Zip-O-Laminators) and 4 European (Binderholz, Hasslacher, Mayr Melnhof, Wiehag).
- Panels:
  - CLT: Element 5, Kalesnikoff, Mercer (WA / Conway AR / Penticton BC), Nordic, Smartlam (AL / MT), Vaagen Timbers, Binderholz, Hasslacher, KLH, Mayr Melnhof, Stora Enso.
  - MPP/VLT: Boise Cascade, Freres Lumber.
  - DLT: DowelLam.
- Panel catalogue `n_e`: rows of `[supplier, type, thickness_mm, plies, panelId, stiffness, strength, width_ft, "y"|"x"]`, where "x" means excluded. Types are CLT, MPP, VLT, "SPF DLT", "Dfir DLT", "EU C24 DLT" and GLT.

**Carbon stages:**
- **A1–A3:** a per-supplier EPD value per m³ (glulam `T_e`, panels `M_e`). Concrete 308.17 (North America) / 458.4. Steel and rebar are regional.
- **A4 (transport):**
  - Emission factors per tonne-km: truck 0.07, rail 0.02, ship 0.012.
  - Distances up to 300 km go by truck. Longer distances are 150 km truck plus rail.
  - Cross-continent routes go through the best pair of named ports, using a sea-distance table.
  - Steel is sourced from the nearest mill in the region (Nucor, US Steel, ArcelorMittal, …).
  - Concrete is a fixed 643.7 km by truck.
- **A5:** 2.1% for timber; per-region factors for steel, rebar and concrete.
- **Biogenic carbon:** negative values per m³.
- **B1–B5, C1–C5 and D** are shown greyed out, i.e. not computed.
- **Rating:** "SCORS" A++ … G in bands of 50 kgCO₂e/m² (50–450).

**Takeoff assumptions:** concrete 150 pcf and steel 490 pcf. Rebar ratios are slab 0.5–1.5% by load, beam and purlin 2.7%, column 3.5%, footing 1.5% and topping 0.56%. Steel gets a 1.15 connection allowance.

## 7. Outputs
- **`statistics`:** `levels, subLevels, sqftPerLevel, grossSqft, floorToFloorHeight, totalHeight, slabHeight, beamHeight, girderHeight, purlinHeight, clearHeight, floorAssemblyDepth, width, length`.
- **`efficiency`:** `volumes, weights, quantities, CO2eA1A3, CO2eA4, CO2eA5, biogenicCO2e, routes, metric*`, plus piece counts `beamPieces, purlinPieces, columnPieces, deckPieces` and matching `…Per1000Sqft` values, and `gradients`.
- **Quantities table:** rows Deck / Girder / Purlin / Column, with columns "Type" / "Size/Source" / "Quantities". Values are volume (ft³) or weight, per kft² (or per 100 m²), and piece counts per kft².
- **Charts:** Weight, GWP and Volume, grouped by "Material" or "Element".
- **No per-member schedule:** "Lite shares the aggregated results, but not the data for specific elements; we're saving that for Concept Pro!"
- **Export and sharing:** there is no PDF, CSV, Excel or IFC export in Lite. "Share" base64-encodes the full state as JSON, posts it to `link-shortener.pmeschke.workers.dev`, and returns a `?scheme=<id>` URL. Sharing asks for an email address first.

## 8. Full Branch Concept ("Coming Soon", from the marketing pages, not in the code)
- "Plan drawing PDFs"
- "Detailed BOM and quantity take-offs with export to Excel"
- "setbacks, irregular forms", "Slab openings", "Transfer slabs", "Off-grid columns"
- Override sizing of individual beams, columns and floor panels
- "US, Canadian, and European code references"
- "Comparison dashboards", saved project workspaces, interoperability with other industry software

Sources: https://concept.branch3d.com/ (bundle `assets/index-CxNXZKiq.js`), https://www.branch3d.com/, https://www.branch3d.com/post/introducing-concept-lite-explore-designs-instantly

**What I could not find:**
- Named design codes. The code shows only formulas (ASCE-7-style live load reduction, glulam and CLT checks). The help page has no FAQ on methodology.
- Grid labels or member naming.
- Rotated, skewed or radial grids.
- Cantilevers, transfer members, or lateral and core design.
- Any export other than the share link.