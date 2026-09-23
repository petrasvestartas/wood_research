# FAST+EPP Bay Design Tool: research report (read-only)

I recovered the full parameter set for both versions of the tool.
- **v1 (2020):** the ShapeDiver model still responds. I opened a session on it and ran six parameter variants.
- **v2 (2024 to 2025):** the live site is down (Cloudflare 521, "origin down", on 2026-09-22). I read its JavaScript bundles from archive.org instead.

No repo files were edited and nothing was built. Scratch copies are in `/tmp/claude-1000/-home-petras-code-code-cpp-wood-research/cd17883b-ad50-44cc-bbcd-c4f797944a70/scratchpad/arch/`.

## 1. Versions and sources

| | v1 "Timber Bay Design Tool" | v2 "Bay Design Tool 2.0" |
|---|---|---|
| URL | fastepp.com/concept-lab/timber-bay-design-tool/, later /concept-lab/apps/timber-bay-design-tool/ (archived 2020-09 to 2024-07) | https://bay-design-tool.fastepp.com (archived 2024-06 to 2025-12; the old URL now 301-redirects here) |
| Stack | WordPress page, ShapeDiver viewer v2.15, Grasshopper model **"2020.05.20 MT Tool 1.0.2"** (https://app.shapediver.com/m/2020-05-20-mt-tool-1-0-2), ticket in theme `scripts.min.js`, region `eu-central-1` | Vite, three.js and plotly. Clerk login is required before `updateBay` runs. Server call is `POST /api/updateBay` |
| Codes | "CSA O86-14 & BCBC 2018" | CSA O86-19, CSA S16-19, CSA A23.3 |
| Materials | Timber only | Timber, steel and concrete |

Articles (https://www.fastepp.com/news/2020/05/try-our-new-timber-bay-design-tool/, constructconnect, ccr-mag, the ShapeDiver blog, woodworks.news) only say it "sizes the deck, purlins, girders, and columns", shows "structural depth and material takeoffs", is "metric only and run per CSA O86", and uses DF for glulam and SPF for CLT. canadianarchitect.com returned 403 and canadianconsultingengineer.com reset or timed out.

## 2. v1 parameters (verbatim, from the live ShapeDiver session)

| ShapeDiver name | Type / UI | Range / choices | Default | HTML id |
|---|---|---|---|---|
| `Grid Dimension A` | Float slider, 1 dp | 3–14 m | 9.0 | `#span-1` |
| `Grid Dimension B` | Float slider | 3–14 m | 9.0 | `#span-2` |
| `No. of Purlins` | Float, 0 dp | 0–7 | 3 | `#intermediate-beams` |
| `Building Storeys` | Float, 0 dp | 1–18 | 6 | `#building-stories` |
| `PANEL TYPE` | StringList cycle | `CLT`, `NLT/DLT`, `GLT` | CLT | `#mass-timber-system` |
| `Loading` | StringList cycle | `Residential`, `Office`, `Assembly`, `Roof` | Residential | `#occupancy` |
| `Fire Resistance (min)` | StringList | `0`,`30`,`60`,`90`,`120` | 0 | `#fire-exposure` |
| `Purlin Width (mm)` | dropdown | `130`,`175`,`215`,`265`,`315`,`365` | 215 | `#purlin-width-mm` |
| `Girder Width (mm)` | dropdown | same list | 265 | `#girder-width-mm` |
| `Dimensions` | Bool | | true | `#dimensions` |

- **Widths are chosen, depths are solved.** The user picks beam widths from the list; the tool solves the depths.
- **Storey height is fixed.** It is not a parameter; the column glTF is 4500 mm tall.
- **Outputs:** `Panel Size`, `Purlin Size`, `Girder Size`, `Column Size`, `Structural Depth (mm)`, `Column Spacing`, `Glulam Volume`, `Panel Volume`, `Total Timber Volume` (m³/m²), `Glulam Vol. (%)`, `Mass Timber Panel Vol. (%)`.
- **Outputs in the model but not shown on the page:** `Carbon Stored`, `GHG Emissions Avoided` (e.g. "10900kg*"). Export: "Download 3D Model".
- **Value strings seen:**
  - Panels: `87V CLT (3PLY)`, `175E CLT (5PLY)`, `64mm NLT / DLT`, `215mm GLT`
  - Members: `215w x 456h`, `No Purlin`, `9000mm x 9000mm`
  - Failures (strings, not flags): `Span too long for panel vibration.`, `Increase member width for this fire case.`, `Column capacity exceeded!`, `Panel capacity exceeded!`

**Layout, checked from the glTF vertices for A=6, B=12, 3 purlins:**
- 4 corner columns.
- 2 girders run along X (span A) on lines Y=0 and Y=B, between column faces.
- Purlins run along Y (span B) at X = 0, 1500, 3000, 4500, 6000. That is the N intermediate purlins plus purlin-sized beams on both column lines.
- Panels span X between purlins and come in strips about 3.1 m wide.
- Purlin spacing is derived as A/(N+1); it is not an input.
- **Connections are top-flush (hung):** depth 695 = 87 panel + max(456 purlin, 608 girder). A stacked layout would give 1151. With A=6/B=12 the girder was forced to the purlin depth (532/532).

## 3. v2 parameters (verbatim, from archived `auth-4a5c4e64.js` / `messaging-d44c02c0.js`)

GUI groups and controls (label → element id → state key):
- **Toggle** "Imperial Units" `imperialToggle`. Imperial ranges are 9–40 ft for grids and 9–18 ft for storey height. Sizes show in inches rounded to ½", and concrete is always labelled "(5000 psi)".
- **Geometry**
  - "Grid Dimension X (m)" `gridDimX` → `dx`, 3–12, step 0.1
  - "Grid Dimension Y (m)" `gridDimZ` → `dz`, 3–12
  - "Story Height (m)" `gridDimY` → `dy`, 3–5.5
  - "Number of X Grids" `Nx` → `Nx`, 1–10
  - "Number of Y Grids" `Ny` → `Nz`, 1–10
  - "Number of Stories" `Nstories`, 1–18
  - Nx and Nz are bay counts, not gridline counts: the scene is centred at `-Nx*dx/2`. Y is up (three.js).
- **Framing**
  - "Framing Type" `framing-type`: `{"Beams with Long Purlins":"PLSS","Beams with Short Purlins":"PSSL","Flat Slab":"PointSupported"}`
  - "Number of Secondary Beams" `Npurlin`, 0–5
  - "Column Material": `{Glulam:"glulam",Concrete:"concrete","Steel W":"steelW","Steel HSS":"steelHss"}`
  - "Purlin Material" and "Girder Material": `{Glulam, Concrete, Steel:"steelW"}`
  - "Panel Material" for beam systems: `{CLT:"clt",GLT:"glt",Concrete:"concrete","Composite Deck":"steelDeck"}`; for PointSupported: `{CLT, Concrete}`
  - Visibility rules:
    - PointSupported hides Npurlin, purlin and girder.
    - Npurlin=0 hides the girder, so the gridline beams are the "purlins".
    - Fire controls hide when no glulam and no CLT is used.
- **Loading & Fire**
  - "Loading Type" presets are `[SDL, LL]` in kPa: `Residential:[2.8,1.9]`, `Commercial:[3.2,2.4]`, `Assembly:[2.8,4.8]`, `Roof:[1.9,1]`
  - "Fire Rating (min)" `FRR`, 0–120, step 15
  - "Fire Protecton" `fire-portection` (typos are in the source): `{Exposed:"exposed","12.7mm Gypsum (30min)":"12.7mm","15.9mm Gypsum (45min)":"15.9mm","15.9mm x2 Gypsum (60min)":"15.9mm x2","Fully Encapsulated":"unexposed"}`
- **Views** (6 camera buttons plus "Panel Transparency") and **Save / Load** ("Save Settings" → "Scheme N").
- **Defaults:** `{dx:4,dy:3,dz:6,Nx:1,Nstories:1,Nz:1,Npurlin:1,framingSystem:"PLSS",panelMaterial:"clt",purlinMaterial:"glulam",girderMaterial:"glulam",columnMaterial:"glulam",FRR:60,fire_protection:"15.9mm",LL:1.9,SDL:2.8}`

**Request body (verbatim structure):**
```
{metadata:{}, geometry:{dx,dy,dz,Nx,Nz,Nstories,units:"m"},
 loads:{units:"kPA",funits:"kN",live_load_mag,superimposed_dead_load},
 building_system:{type:<PLSS|PSSL|PointSupported>, params:{Npurlin,
   materials:{deck,purlin,girder,column}, fire_rating,
   fire_protection:{deck,purlin,girder,column}}}}
```

**Response, as the client reads it:**
- `metadata.title`
- `archetypes[]`, each with `{name, material, vertices (2D profile), length (extrusion), rotation [rx,ry,rz], elements.positions [[x,y,z]…], designInfo}`. The client renders each archetype as an InstancedMesh.
- `designInfo = {structuralClass: "deck"|"purlin"|"girder"|"column", sectionName, count, volume (m³), ghg (kgCO2/m²), checkNames[], units[], capacities[], demands[]}`
- The failure sentinel is `"No working section."`

**Output tables:**
- "Bay Data": Type | Description, plus "Total Structural Depth" computed as Σ deck height + max(purlin, girder) height, i.e. flush framing.
- "Takeoffs": Type | Count | Vol. (m³) | CO2 (kg/m²), a Total row, and a per-class carbon pie chart.
- "Material Volume": Glulam, Panel, Total Timber.
- A per-member check table ("Check Name / Check Capacity / Check Demand") exists in `UI.js` but is not wired into the page.

**Design assumptions (About page, verbatim points):**
- "Only a single bay of the structure is analyzed, even if more bays are shown."
- "The bay analyzed is an interior bay at the bottom of the building."
- The floor is assumed to span between two beams; panels are "two-span continuous".
- "the primary beams are forced to be as deep as the secondary beams."
- Beams are laterally braced by the floor.
- EPD A1–A3.
- DF glulam, SPF CLT; "CLT with large structural spans (6.5m+ between beams) may require special manufacturing".
- Steel sections are W/HSS from AISC. Composite deck must span unpropped. Fire is ignored for steel and concrete.
- Concrete is precast when mixed with other materials and monolithic when all concrete.

## 4. Sibling apps (shared vocabulary)

- **EC tool** (https://ec-tool.fastepp.com, live, bundle `main.26b34ddf.js`). A1–A3 factors:
  - Concrete, per m³: `concHoriz` 248, `concVert` 198, `concFound` 198; `concRebar` 0.979/kg
  - Steel, per kg: `steelHotRolled` 1.22, `steelHSS` 1.99, `steelOWSJ` 1.38, `steelPlate` 1.73, `steelDeck` 2.37
  - Wood, per m³: `woodCLT` 137, `woodDltNlt` 121.4, `woodMPP` 311, `woodPlywood` 219.32, `woodGlulam` 137.19, `woodPslLslLvl` 361, `woodTJI` 270, `woodLumber` 63.12
  - `*Custom` takes kgCO2e directly. It compares 3 schemes with a building area to give GWP/m².
  - I could not confirm that Bay v2 uses the same factors.
- **Member Calculator:** span-to-depth lookup at https://www.fastepp.com/wp-content/themes/fastepp/assets/json/calculation.json.
  - Row keys: `ZMATERIAL, ZSTRUCTURE (Roof/Floor), ZSPAN (Beam/Joist/Slab), ZTYPE, ZINPUT (span), ZMIN, ZMAX (mm), ZEXCEEDING`. Metric spans 1.5–24 m; 0.0 means not feasible.
  - Types:
    - Concrete: Cast-in-place, Prestressed, 1-Way, 2-Way, Prestressed Panel, Prestressed Double Tee
    - Steel: Wide Flange, Girder Truss, Open Web
    - Wood: Glue Laminated, Sawn Timber, Engineered I-Joists, Solid Wood Panels
  - Example: a 9 m glulam floor beam is 610–760 mm deep.

## 5. Takeaways for a C++ grid data structure

1. **Keep the grid separate from the framing.** The Bay tool is uniform and rectangular only (`dx,dz,Nx,Nz`, no irregular spacing, no cantilevers). To cover "various grids", store:
   - offset lists for the axes (`std::vector<double> x_offsets, y_offsets, level_z`), so spacing can be non-uniform;
   - or, more generally, a planar cell complex: nodes are column points, edges are gridline beam candidates, faces are bays, with levels on top. Radial, skewed and triangular grids then fit.
   - A rectangular generator fed `(dx, dz, Nx, Nz, Nstories, dy)` reproduces the Bay tool exactly.
2. **Give each bay (face) a framing spec, not a global one:**
   - `system` ∈ {BeamsLongPurlins/PLSS, BeamsShortPurlins/PSSL, PointSupported}; for non-quad faces, store a span-direction edge or vector instead;
   - `n_secondary` (0–7), with spacing derived as span/(n+1);
   - `deck_type`, and a `connection` ∈ {flush/hung, stacked}. Both versions only do flush: depth = deck + max(beam).
   - Note that with n=0 the gridline beams become the one-way supports.
3. **Member roles and instancing.** Use the roles `Deck, Purlin(secondary), Girder(primary), Column`. Mirror the v2 response: an `Archetype{role, material, profile polygon, length, rotation}` plus a list of instance frames. This is compact and maps straight onto session meshes and elements.
4. **Material enums.** Take the union of all three apps: `glulam, clt, glt, nlt, dlt, mpp, plywood, lvl_psl_lsl, concrete, steel_w, steel_hss, steel_deck`, plus the discrete glulam widths {130,175,215,265,315,365}. Species and grade are fixed in both tools (DF/SPF). Keep them as data rather than options.
5. **Loads and fire.** Loads are `{sdl_kpa, ll_kpa}` with an occupancy preset table. Fire is `{frr_min, protection enum}` per role.
6. **Results per archetype.** Store `section_name, count, volume_m3, gwp_kg_per_m2, checks[{name, unit, capacity, demand}]` and an explicit `ok` flag, instead of failure strings. Also store the aggregates: total structural depth, volume per class, timber m³/m², GWP/m².
7. **Scope lesson.** Both tools size one interior bay on the bottom storey and copy it everywhere. On a general grid, size each bay and column with its own tributary area and the storeys above it. Edge and corner bays differ, and a non-uniform grid needs this.

## 6. Not found or unverified

- **v2 server output:** no captured `/api/updateBay` responses, the site is down, and v2 is behind a Clerk login. The response schema above is inferred from client code, and v2's sizing algorithm and GWP factors are unknown.
- **Options neither version offers:**
  - NLT, DLT or mass plywood decks in v2; NLT/DLT exist only in v1 and MPP only in the EC tool
  - a concrete topping over timber
  - cantilevers
  - a stacked vs. flush choice
  - a species or grade picker
  - a direct purlin-spacing input
  - irregular or non-rectangular grids
- **Unchecked sources:** vibration criteria details, YouTube and LinkedIn descriptions, and the canadianarchitect and canadianconsultingengineer pages, which were blocked.