# Branch3D Concept Lite: framing by structural method, floor system and span direction

Base directory (written `$F` below): `/tmp/claude-1000/-home-petras-code-code-cpp-wood-research/cd17883b-ad50-44cc-bbcd-c4f797944a70/scratchpad/reference/branch3d_framing/`

## 0. How this was captured

- **Browser:** Chrome driven by Playwright, headed, 1600×1000. The bundle was the live `index-CxNXZKiq.js` with two read-only hooks added (`$F/patch_bundle.js` → `index.patched.js`); they expose the zustand store, the sizing store and the generated model.
- **Base model:** the start wizard, set to Office / Post and beam / Mass Timber.
  - Footprint 150 × 180 ft (45720 × 54864 mm), 6 storeys at 14 ft (4267.2 mm).
  - Bays 30 × 20 ft. X grid lines at 0, 30, 60, 90, 120, 150 ft; Y grid lines at 0, 20, …, 180 ft.
  - Two cores: 30×30 ft at (50, 90) and 20×10 ft at (60, 46).
  - 2-hour fire rating; Normal loads, 15/65 psf.
  - Timber floors carry a 2" topping.
- **How settings were changed:** every combination was set by clicking the left panel only. That means the Framing System icons, the floor-material tiles, the floor-system icons and the Span X/Y toggle, plus typing into the Purlin Spacing box. The bay grid stays at the wizard's 30×20 ft throughout.
- **Validity checks:** after each change the script compared the store with the requested setting and checked that the footprint, grid and cores had not moved. One early run accidentally clicked the canvas, which added a perimeter control point; those cases were thrown away and captured again. All 39 final panel-driven cases passed (47 cases in total with the 8 wizard cases).
- **Material comparison (§7):** eight extra cases were captured straight from the wizard (`wizard_*`), with no changes made in the panel.
- **Units:** all JSON values are in mm (Branch stores feet; ×304.8). Z points up. The level datum is D = 4267.2·(i+1). Level 0 is stored in full in each JSON; every level is summarised in `per_level`.

**Files in each case folder `$F/<case>/`:**
- 3D views: `iso.png`, `iso_framing.png` (slab hidden), `closeup.png`, `closeup_framing.png` (corner bay), `from_below_framing.png`
- Plans: `plan.png`, `plan_framing.png` (top view, slab hidden)
- Left panel: `left_panel_top.png`, `left_panel_bottom.png` (scrolled down to show Purlin Spacing)
- Right panel: `right_quantities.png`, `right_summary.png`
- Whole window: `ui_full.png`

**`$F/<case>.json` holds:**
- `controls`, `grid_mm`, `cores_mm`, `per_level` (counts and section histograms)
- `level0`: every column, girder/perimeter beam and purlin with `start_mm`/`end_mm`/`top_z_mm`/`bottom_z_mm`/`width_mm`/`depth_mm`/`cross_section`/`tributary_width_mm`/`supports`; plus the floor (thickness, topping, holes, raw sizing data), `panel_strips` (lines_mm and approximate panel count) and `span_information_mm`
- `sizing_warnings` (flagged grid lines, maximum spans), `statistics_raw_ft`
- The text of the left panel, Quantities and Summary panels
- `panel_options`, in the `wizard_*` cases only

**Tooltips and MORE:**
- Tooltips: `$F/tooltips/*.png` (a full screenshot and a `_crop` for each) and `$F/tooltips/tooltips.json`
- MORE: `$F/more/more_{plate,beam,purlin}.png` (plus `_crop`) and `$F/more_{plate,beam,purlin}.md`

**Tooling:**
- `run_batch.js` (batches `beam`, `purlin1`, `purlin2`, `plate`, `materials`)
- `driver.js` + `lib.js` (used interactively for the tooltips)
- `analyze.py` (summaries), `fix_options.py`
- `batch_log.txt`

## 1. The framing controls on the left panel

| Control | Options (tooltip text) | Notes |
|---|---|---|
| Typical Bay: Span X / Span Y | "Girders / primary beams span along the model's X-axis" / "…Y-axis" | Both icons are greyed out, with no message, for Flat plate + Concrete. |
| Structural System (3 icons) | "Flat plate / point-supported" MORE · "Post and beam" MORE · "Purlin on girder / girder with secondary beams" MORE | All three MORE links open the same popover (§8). |
| Floor Slabs: floor-system icons for Timber | CLT · MPP/VLT · DLT · GLT (coming soon, greyed) | Tooltips have a title and a description, but no MORE link. |
| Floor Slabs: floor-system icons for Concrete | Flat plate · Precast hollow-core planks (coming soon) · Precast double tees (coming soon) | |
| Floor Slabs: floor-system icons for Composite | Slab on metal deck · Roof deck (coming soon) | |
| Floor material tiles | Timber · Concrete · Composite | With Concrete or Composite the supplier box becomes a region picker (North America / Global, or North America / Europe / Global for Composite) and the Concrete Topping slider is greyed. Fire Protection is greyed for Concrete; for Composite it offers Exposed / SAFP 1/2", 1.5", 2" / Intumescent paint. |
| Beams card: Purlin / Secondary Beam | Profile: Rectangular · Steel W · Double purlins (coming soon). Purlin Spacing: "Maximum spacing between purlins / secondary beams". | Imperial range 2–20 ft in 1 ft steps; metric range 0.6–6.095 m in 0.05 m steps. The heading reads "Secondary Beam" whenever the beam material is not Glulam. |

## 2. Combinations the UI disables, and why (verbatim tooltip text)

| Selected | Disabled | Tooltip |
|---|---|---|
| Floor = Composite | Flat plate icon | "System incompatible with materials — Slab-on-metal deck, as a one-way spanning system, cannot be used in a point-supported scheme." |
| Floor = DLT | Flat plate icon | "Material incompatible with system — Dowel-Laminated Timber cannot be used in a point-supported scheme." |
| System = Flat plate | DLT icon | "Material incompatible with system — Dowel-Laminated Timber cannot be used in a point-supported scheme." |
| System = Flat plate | Composite tile | "Material incompatible with system — Slab-on-metal deck, as a one-way spanning system, cannot be used in a point-supported scheme." |
| System = Flat plate | Beam material tiles and the whole Beams card | "Not in system — No beams are used in a point-supported system" |
| System = Post and beam | Purlin / Secondary Beam section (profile and spacing) | "Not in system — No purlins are used in a post and beam system" |
| System = Flat plate + floor = Concrete | Span X / Span Y | (no message; the toggle is simply greyed out) |
| Always | GLT, hollow-core, double tee, roof deck, square/double girders, open-web joists, double purlins | "Future feature: …" |
| Wizard | Point supported ⟷ Steel | These exclude each other. See `$F/ui/wizard_point_supported_disables_steel.png` and `$F/ui/wizard_steel_disables_point_supported.png`. |

**Limit warnings.** These are not disabled states; the combination is still allowed.
- **Flat plate with 30×20 ft bays.**
  - The X/Y spacing field turns red with "Exceeds maximum span of 11'-6"" or "…22'".
  - The flagged grid lines are coloured orange.
  - The deck is extrapolated, which gives "exceeds typically manufactured panel thicknesses. Branch has assumed a custom, over-standard panel thickness…".
- **Composite deck with spans of 15, 20 or 30 ft.**
  - The warning reads "Slab on metal deck exceeds typical slab-on-metal-deck span limits. Branch has assumed a mild slab shored during construction…".
  - The deck thickness falls back to the value for a one-way concrete slab.
  - With Purlin on girder, the purlin field shows "Typical span exceeds maximum for current loads." (`typicalPurlinOversize`).

## 3. Rules common to all methods (observed)

- **Grid.** The grid is two sorted lists of axis-aligned line positions, plus the edges of the footprint.
- **Columns.**
  - A column stands at every grid crossing inside the footprint and at every footprint vertex or edge crossing (`is_boundary`).
  - Columns inside a core, or on a core's edge, are removed. The reference model therefore has 58 columns: 60 crossings minus (60,100) and (60,120), both in core 1.
  - Columns are square in glulam and concrete and W in steel.
  - Each column runs from D(i−1) up to D(i), so its top is flush with the level datum.
- **Floor deck.**
  - The deck occupies [D, D+t].
  - Timber floors get a topping on top: [D+t, D+t+50.8] for the 2" default.
  - Concrete and composite floors have no topping; the topping control is disabled for them.
- **Beam tops.**
  - All beams hang below the datum.
  - The top is D − 3.05 mm, from a 0.01 ft render offset, and the bottom is top − depth.
  - The single exception is the dropped girder in §5.3.
- **Cores.**
  - Cores are holes in every floor.
  - A girder that crosses a core is split at the core face and ends on a `{"type":"core"}` support, which can leave short stubs (e.g. 60,40→60,46 and 60,56→60,60 at core 2). A girder lying entirely inside a core is removed.
  - Purlins are **not** cut at cores: they run straight through the voids.
- **Panel strips (timber floors only).** These are drawn as thin lines and stored in `panel_strips`.
  - **Direction.** The strip lines run parallel to the direction the deck spans. The rule is `d = (span=="X") != (system=="Purlin")`:
    - Beam or Plate with Span X: lines at constant x (strips run in Y).
    - Purlin with Span X: lines at constant y.
    - Span Y reverses each of these.
  - **Width.** Strips are the supplier's panel width, starting at footprint min + 3 mm. They are **not** aligned to the grid:

    | Floor | Supplier | Strip width |
    |---|---|---|
    | CLT | Element 5 or Kalesnikoff | 11.5 ft (3505.2 mm) |
    | MPP | Boise Cascade | 4 ft (1219.2 mm) |
    | DLT | DowelLam | 14 ft (4267.2 mm) |

  - **Panel ends.** A panel end joint falls on a grid line whenever the running sum of bays exceeds `maxPanelLength` = 60 ft. So panels are continuous over 3 × 20 ft bays (joints at y = 18288 and 36576) or over 2 × 30 ft bays (joints at x = 18288 and 36576).
  - **Concrete and composite.** No lines are drawn. `approximatePanelCount` becomes the bay count, because the maximum length is forced to 1.

## 4. Summary table (level 0, reference model; mm)

**Case name:** method_floor_span[_purlin spacing]. The span direction is X or Y and the purlin spacing is in feet.

**Columns:**
- **Girders** and **Purlins:** count and typical section.
- **G top:** girder top relative to the datum.
- **Deck:** thickness t, plus the panel ID the app sized.
- **Deck span:** the direction the deck spans and the distance it covers.
- **Panels:** approximate panel count per level.
- **Assembly / clear:** the app's figures, taken from Summary: "floor assembly depth" and "Minimum clear height".
- **Quantities:** pieces over 6 storeys as D (deck) / G (girder) / P (purlin) / C (column). The Girder count includes the perimeter beams.

Every case has 58 columns, and every Beam and Purlin case has 28 perimeter beams. Columns are glulam squares: 340–440 mm with timber floors (up to 459 under the extrapolated timber Plate decks), up to 560 mm under concrete or composite floors, and up to 580 mm for the concrete Plate.

| Case | Girders (typical) | G top | Purlins (typical, spacing) | Deck t (panel) | Deck span | Panels | Assembly / clear | Quantities D/G/P/C |
|---|---|---|---|---|---|---|---|---|
| plate_clt_spanX | 0 | – | 0 | 574.7 (extrapolated, two-way) | two-way; X bay flagged (> 11.5 ft) | 39 | 625 / 3642 | 234/–/–/348 |
| plate_clt_spanY | 0 | – | 0 | 574.7 (extrapolated) | two-way; X and Y bays both flagged | 48 | 625 / 3642 | 288/–/–/348 |
| plate_mpp_spanX / Y | 0 | – | 0 | 533.4 (extrapolated) | two-way; X bay flagged (> 4 ft) | 114 / 135 | 584 / 3683 | 684 or 810/–/–/348 |
| plate_concrete (X = Y; toggle locked) | 0 | – | 0 | 415.6 (two-way flat plate) | two-way | 117 / 75 | 416 / 3852 | –/–/–/348 |
| beam_clt_spanX | 40, 320x720 | −3 | – | 241.8 (E5 7-ply) | Y, 6096 | 39 | 1013 / 3255 | 234/408/–/348 |
| beam_clt_spanY | 36, 280x680 | −3 | – | 365.8 (E5 9-ply) | X, 9144 | 48 | 1097 / 3171 | 288/384/–/348 |
| beam_mpp_spanX / Y | 40 / 36 | −3 | – | 239.8 / 320.8 (Boise 7-7/16, 10-5/8) | Y 6096 / X 9144 | 114 / 135 | 1011 / 1052 | 684 or 810/…/348 |
| beam_dlt_spanX / Y | 40 / 36 | −3 | – | 228.8 / 330.8 (2x8, 2x12 SPF) | Y 6096 / X 9144 | 33 / 39 | 1000 / 1062 | 198 or 234/…/348 |
| beam_concrete_spanX / Y | 40 360x840 / 36 340x800 | −3 | – | 243.8 / 365.8 (one-way slab) | Y 6096 / X 9144 | 117 / 75 | 1084 / 1166 | –/408 or 384/–/348 |
| beam_composite_spanX / Y | same as concrete | −3 | – | 243.8 / 365.8 (fell back to concrete; oversize) | Y / X | 117 / 75 | 1084 / 1166 | –/…/348 |
| purlin_clt_spanX_10ft | 40, 300x720 | −206.3 | 126 run in Y, 240x520, @3048 | 189.8 (E5 5-ply) | X, 3048 | 48 | 1481 / 2787 | 288/408/756/348 |
| purlin_clt_spanY_10ft | 36, 280x640 | −206.3 | 85 run in X, 260x640, @3048 | 189.8 | Y, 3048 | 39 | 1521 / 2747 | 234/384/510/348 |
| purlin_clt_spanX_2ft | 40, 320x720 | −206.3 | 666, 220x320, @609.6 | 189.8 (5-ply is the fire minimum) | X, 610 | 48 | 1281 / 2987 | 288/408/3996/348 |
| purlin_clt_spanX_20ft | 40, 320x720 | −206.3 | 81, 240x600, @4572 | 241.8 (7-ply) | X, 4572 | 48 | 1613 / 2655 | 288/408/486/348 |
| purlin_clt_spanY_2ft | 36, 280x640 | −206.3 | 445, 220x440, @609.6 | 189.8 | Y, 610 | 39 | 1321 / 2947 | 234/384/2670/348 |
| purlin_clt_spanY_20ft | 36, 280x640 | −206.3 | 40, 320x720, @6096 (on grid lines only) | 241.8 | Y, 6096 | 39 | 1693 / 2575 | 234/384/240/348 |
| purlin_mpp_spanX_2ft / 20ft | 40 | −206.3 | 666 220x280 / 81 240x600 | 104.8 / 239.8 | X | 135 | 1156 / 1611 | 810/408/3996 or 486/348 |
| purlin_mpp_spanY_2ft / 20ft | 36 | −206.3 | 445 220x400 / 40 320x720 | 104.8 / 239.8 | Y | 114 | 1196 / 1691 | 684/384/2670 or 240/348 |
| purlin_dlt_spanX_2ft / 20ft | 40 | −206.3 | 666 220x320 / 81 240x600 | 135.8 / 228.8 (2x4, 2x8) | X | 39 | 1227 / 1600 | 234/408/…/348 |
| purlin_dlt_spanY_2ft / 20ft | 36 | −206.3 | 445 220x400 / 40 300x720 | 135.8 / 228.8 | Y | 33 | 1227 / 1680 | 198/384/…/348 |
| purlin_concrete_spanX_2ft / 20ft | 40 320x800 / 360x840 | −206.3 (beams still Glulam) | 666 220x320 / 81 280x640 | 152.4 / 243.8 | X | 75 | 1272 / 1724 | –/408/…/348 |
| purlin_concrete_spanY_2ft / 20ft | 36 | −206.3 | 445 220x480 / 40 360x840 | 152.4 / 243.8 | Y | 117 | 1352 / 1844 | –/384/…/348 |
| purlin_composite_spanX_2ft / 20ft | 40 | −206.3 | 666 220x320 / 81 280x640 | 171.5 (PLW2-22 4.5") / 243.8 (oversize) | X | 75 | 1251 / 1724 | –/408/…/348 |
| purlin_composite_spanY_2ft / 20ft | 36 | −206.3 | 445 220x440 / 40 360x840 | 171.5 / 243.8 (oversize) | Y | 117 | 1291 / 1844 | –/384/…/348 |

Two more cases:
- `beam_clt_spanX_wizard_kalesnikoff` is the untouched wizard state. It uses supplier Kalesnikoff 5-ply E1.2. Every later CLT case uses Element 5, because the UI resets the supplier to the first one in its list whenever the floor type changes.
- The geometry, the 241.8 mm deck and the 11.5 ft strips are identical to beam_clt_spanX.

## 5. Member layout rules per structural method

### 5.1 Flat plate / point-supported (`Plate`)

- **Members:**
  - Columns at the crossings (as in §3) and the deck. That is all.
  - The generator builds the girders and perimeter beams and then deletes them on every above-ground level, so there are no perimeter beams either.
  - No purlins.
- **Deck:**
  - A two-way slab or panel sits on the columns. Its bottom is at D and its top at D+t.
  - Timber two-way panels are sized from a table of major and minor spans.
  - In the wizard's own Plate bay (Office, Mass Timber: 11.5 × 15 ft on a 149.5 × 180 ft footprint), the deck is Kalesnikoff 7-ply V2 at 295.8 mm, with 176 columns.
  - With the 30 × 20 ft bays it is extrapolated: CLT 574.7 mm, MPP 533.4 mm.
  - A concrete flat plate is 415.6 mm at 30 × 20 ft and 345.2 mm at the wizard's 25 × 25 ft.
- **What the Span X/Y toggle does:**
  - **Span X:** the panel strips run in Y (joints at constant x). The X bay may be at most the panel width (CLT 11.5 ft, MPP 4 ft), and the Y bay at most the maximum panel span (CLT 22, MPP 24 ft). Any X grid line that breaks this is flagged.
  - **Span Y:** the reverse; the limits swap.
  - In the wizard's Plate preset, the X bay equals the CLT width (11.5 ft), so the panel joints land on the column lines. With any other bay they do not: strips always start at x = 0 + 3 mm.
- **Floor systems allowed:** CLT, MPP and concrete Flat plate. DLT and Composite are disabled (§2). With concrete the span toggle is locked; X and Y give identical members, and only the approximate panel count changes (117 vs 75).
- **Stacking:** there are no beams, so the floor assembly depth equals t plus the topping (625 mm for CLT with the 574.7 mm deck).

### 5.2 Post and beam (`Beam`)

**Span X ("girders span along X"):**
- **Girders:**
  - Placement: on every **interior Y grid line**, running in X.
  - Splitting: split at every X grid line, so each member is one 30 ft bay (5 per line), and again at cores.
  - Count and supports: 8 lines × 5 = 40. Each end sits on a column, or on a core where the line crosses one.
  - Sizing: tributary width = half the distance to each neighbouring line (6096 for 20 ft bays).
- Interior X grid lines carry **no beam**.
- **Perimeter beams:**
  - Placement: on every footprint edge, split at each grid crossing: 2 × 5 + 2 × 9 = 28.
  - Sides parallel to the girders (y = 0 and 180): trib 3048 (half a bay); section 280x680 here.
  - Sides perpendicular to the girders (x = 0 and 150): trib 0; 220x360. They carry only the facade line load of one storey height.
- **Deck:** spans **Y** between girder lines, i.e. the Y bay of 6096. The strips run in Y and are continuous for 60 ft (3 bays), with end joints at y = 18288 and 36576.
- **Elevations:** girders and perimeter beams all share one top level, D − 3. They hang below the deck. The deck bottom is at D.

**Span Y:**
- The layout rotates: 4 interior X lines × 9 Y-bays = 36 girders running in Y, each 20 ft long.
- The deck now spans **X**, 9144 (30 ft).
- The perimeter beams on x = 0 and 150 get trib 4572 (260x600). Those on y = 0 and 180 get trib 0 (220x480).
- The deck is much thicker because it spans the long bay: CLT 241.8 → 365.8, MPP 239.8 → 320.8, DLT 228.8 → 330.8, concrete 243.8 → 365.8.

**What the floor system changes** (girder layout is identical for all five):
- Deck thickness and panel strips (§3, §4).
- Girder size, through the deck's self-weight: 320x720 for timber vs 360x840 for concrete or composite at span X.
- Column sizes.
- The topping, which timber floors have and the others do not.

### 5.3 Purlin on girder / girder with secondary beams (`Purlin`)

**Span X:**
- **Girders:** exactly as Post and beam Span X: interior Y lines, running X, split at every X line, 40 in total.
- **Purlins (secondary beams):**
  - Direction: run in **Y**, perpendicular to the girders.
  - Extent: each spans one Y-bay from girder line to girder line, the perimeter lines included. Length 6096; one member per bay.
- **Purlin rows, per X-bay [x_k, x_k+1]:**
  - Count: n = ceil(bay / p).
  - Positions: equally spaced at x_k + j·bay/n for j = 0 … n−1.
  - The row on the footprint edge is skipped, because the perimeter beam is there.
  - A row on an **interior** X grid line is kept, so a purlin always sits on each interior column line and frames column to column. No girder sits there.
  - With 30 ft bays:

    | p | Spacing | Rows | Purlins (rows × 9 Y-bays) |
    |---|---|---|---|
    | 10 ft | 10 ft | 14 | 126 |
    | 2 ft | 2 ft (609.6) | 74 | 666 |
    | 20 ft | 15 ft (4572) | 9 | 81 |

  - Purlins are not reduced at cores; they pass straight through.
- **Deck:**
  - Spans **X** between purlins, over a span equal to the purlin spacing. It is sized for that spacing; e.g. `panelSizingDebug.span` = 10 ft.
  - The strips therefore run in X, with end joints at x = 18288 and 36576.
  - `span_information` still reports the girder-direction bays: X, 9144.
- **Perimeter beams:** 28 as before.
  - Sides parallel to the girders (y = 0 and 180): trib = half the Y-bay, 3048.
  - Sides perpendicular to them (x = 0 and 150): trib = p/2, e.g. 1524 at 10 ft. These carry the edge strip of deck that the first purlin would otherwise take.
- **Tributary widths:** girders take the Y-bay (6096); purlins take their actual spacing (3048).

**Span Y:**
- Rotated: 36 girders run in Y on the interior X lines.
- Purlins run in **X**, each spanning a 30 ft X-bay (length 9144), with rows spaced along Y.
- Per 20 ft Y-bay the number of purlins is ceil(20/p):

  | p | Spacing | Rows | Purlins (rows × 5 X-bays) |
  |---|---|---|---|
  | 10 ft | 10 ft | 17 | 85 |
  | 2 ft | 2 ft | 89 | 445 |
  | 20 ft | 20 ft, i.e. only on the Y grid lines | 8 | 40 |

- At p ≥ bay the "purlins" become beams on the column lines, crossing the girders, so the result is a full two-way beam grid (`purlin_clt_spanY_20ft/plan_framing.png`).
- The deck spans Y.

**Stacking (elevations):**
- The deck bottom is at D, and purlins and perimeter beams have their tops at D − 3.
- **When the beam material is Glulam, the girders are dropped:** top = D − 3 − min(purlin depth, 203.2), i.e. D − 206.3 in every case here. The drop is capped at 8 in (0.6667 ft) whatever the purlin depth.
- The purlins are deeper than 203 mm (320–720 mm), so they **overlap the girders vertically** rather than sitting on top of them. With 240x520 purlins on 300x720 girders, the purlin bottom (D−523) lies 317 mm below the girder top (D−206.3).
- Perimeter beams are never dropped.
- With **Steel or Concrete beams** (`wizard_purlin_steel`, `wizard_purlin_concrete`), girders are **not** dropped. Girder and purlin tops are flush at D − 3.
- The app's own statistics nevertheless treat deck + topping + girder + purlin as fully stacked. E.g. 1481 mm assembly and 9'-2" minimum clear height for purlin_clt_spanX_10ft, which does not match the geometry.

**What the floor system changes:**
- Deck thickness at the purlin spacing (§6).
- Strip width and direction.
- Purlin and girder sizes.
- It does not change the layout.
- Composite needs p ≤ about 12–14 ft; beyond that it is flagged oversize and sized as a one-way concrete slab.

### 5.4 What Span X / Span Y flips, in short

| | Span X | Span Y |
|---|---|---|
| Girders (Beam, Purlin) | on interior Y lines, run X, one per X-bay | on interior X lines, run Y, one per Y-bay |
| Purlins (Purlin) | run Y (one Y-bay long), rows spaced along X, ceil(Xbay/p) per bay | run X (one X-bay long), rows spaced along Y, ceil(Ybay/p) per bay |
| Deck span, Beam | Y (girder spacing = Y bay) | X |
| Deck span, Purlin | X (between purlins) | Y |
| Timber strip joints, Beam and Plate | constant x (strips run Y) | constant y |
| Timber strip joints, Purlin | constant y (strips run X) | constant x |
| Perimeter beams that carry floor | Beam: y = 0 and 180 sides (half the Y bay). Purlin: those, plus x sides at p/2. | swapped |
| Plate span limits | X ≤ panel width, Y ≤ max panel span | swapped |

## 6. What the floor system changes geometrically

**Deck thickness t, in mm, at the 2-hour rating.**
- The timber t includes a 2" (50.8 mm) fire allowance on top of the catalogue panel (`fireRatingThickness` = 0.1667 ft). For example, CLT 5-ply is 139 + 50.8 = 189.8 and DLT 2x4 is 85 + 50.8 = 135.8.
- Timber floors also carry the 50.8 mm concrete topping above t.

| Deck span | CLT (Element 5) | MPP (Boise Cascade) | DLT (DowelLam) | Concrete one-way | Composite (slab on metal deck) |
|---|---|---|---|---|---|
| 2 ft (purlin at 2 ft) | 189.8 (5-ply, the fire minimum) | 104.8 (2-1/8") | 135.8 (2x4) | 152.4 (6" minimum) | 171.5 (PLW2-22, 4.5" slab) |
| 10 ft (purlin at 10 ft) | 189.8 (5-ply) | – | – | 152.4 (`wizard_purlin_concrete`) | 171.5 (PLW2-18, `wizard_purlin_steel`) |
| 12 ft (Steel P&B bay) | – | – | – | – | 190.5 (PLW3-18) |
| 15–20 ft | 241.8 (7-ply) | 239.8 (7-7/16") | 228.8 (2x8) | 243.8 | 243.8, flagged oversize (falls back to the concrete value) |
| 30 ft (Beam, Span Y) | 365.8 (9-ply) | 320.8 (10-5/8") | 330.8 (2x12) | 365.8 | 365.8, flagged oversize |
| Two-way (Plate) 30×20 | 574.7, extrapolated | 533.4, extrapolated | disabled | 415.6 | disabled |
| Two-way 11.5×15 (wizard Plate) | 295.8 (Kalesnikoff 7-ply V2) | | | | |
| Two-way 25×25 (wizard Plate) | | | | 345.2 | |

**Other effects of the floor system:**
- **Strips (timber only):** CLT 3505.2, MPP 1219.2, DLT 4267.2 wide, laid in the deck span direction, at most 60 ft long with the end joint on a grid line. Concrete and composite draw no strips.
- **Topping:** timber only (2" = 50.8 mm by default). The control is disabled for concrete and composite.
- **Loads:** a heavier deck means deeper girders and purlins and larger columns (e.g. Beam span X: timber floors give 320x720 girders, concrete or composite give 360x840).

## 7. Material switch (wizard Mass Timber / Concrete / Steel, Office preset)

The material chosen in the wizard sets the column, beam and purlin materials all together, plus the floor material. It also sets the bay size and the span direction. The rule for span is X when the material is Mass Timber and the system is not Purlin, or when the material is Steel; otherwise it is Y.

| Case | Bay (ft) | Span | Columns | Girders (count, typical) | Purlins | Floor, t | G top |
|---|---|---|---|---|---|---|---|
| wizard_beam_mt | 30×20 | X | 58 Glulam Square | 40, 320x720 Glulam | – | CLT Kalesnikoff, 241.8 + 2" topping | −3 |
| wizard_beam_concrete | 30×15 | Y | 75 Concrete Square 400–475 | 47, 300x500 concrete Rectangular | – | Concrete Flat plate, 365.8 (30 ft one-way) | −3 |
| wizard_beam_steel | 30×12 | X | 92 Steel W (W8X31–W8X48) | 70, W21X44 (perimeter W18X35 / W6X9) | – | Composite slab on metal deck, 190.5 (PLW3-18) | −3 |
| wizard_purlin_mt | 30×30 | Y | 40 Glulam | 24, 320x800 | 85, 260x640 @10 ft | CLT, 189.8 | −206.3 (dropped) |
| wizard_purlin_concrete | 30×30 | Y | 40 Concrete | 24, 300x740 | 85 "Secondary Beam" Rectangular Concrete, 300x500 | Flat plate, 152.4 | −3 (flush) |
| wizard_purlin_steel | 30×30 | X | 40 Steel W (W10X60–W10X100) | 25, W24X68 | 84 "Secondary Beam", W18X40 | Composite, 171.5 (PLW2-18) | −3 (flush) |
| wizard_plate_mt | 11.5×15 on a 149.5×180 footprint | X | 176 Glulam 320–360 | – | – | CLT two-way, 295.8 | – |
| wizard_plate_concrete | 25×25 | Y (toggle locked) | 60 Concrete 400–550 | – | – | Flat plate two-way, 345.2 | – |
| wizard Point supported + Steel | disabled in the wizard | | | | | | |

**Profile options the panel shows for each beam material.** Taken from `panel_options` in `wizard_*.json`. `*` marks the default, `~` a disabled option.

| Material | Girder profiles | Purlin / Secondary Beam profiles | Column types |
|---|---|---|---|
| Glulam (Mass Timber) | *Rectangular; ~Square (coming soon); ~Double girders (coming soon) | *Rectangular (timber); Steel W; ~Double purlins (coming soon) | *Square; ~Rectangular; ~Round |
| Concrete | *Rectangular; ~Slab band (coming soon); ~Precast girders (coming soon) | *Rectangular (concrete); ~Slab band beams (coming soon) | *Square; ~Rectangular; ~Round |
| Steel | *Steel W; ~Steel HSS (disabled); ~Open web joists (coming soon) | Rectangular (timber); *Steel W; ~Double purlins (coming soon) | *Steel W; Steel HSS; ~Round HSS / Pipe (coming soon) |

**Floor options per floor material:**

| Floor material | Options |
|---|---|
| Timber | CLT, MPP/VLT, DLT (disabled under Plate), GLT (coming soon) |
| Concrete | Flat plate; hollow-core and double tees coming soon |
| Composite | Slab on metal deck; roof deck coming soon. The whole tile is disabled under Plate. |

**Other effects of the material:**
- Choosing a non-Glulam beam material relabels the section "Secondary Beam".
- It also switches supplier selection to a region picker.
- It removes the girder drop.

## 8. MORE texts (verbatim)

**Tooltips on the three structural-method icons:**
- "Flat plate / point-supported" MORE
- "Post and beam" MORE
- "Purlin on girder / girder with secondary beams" MORE

Every MORE opens the same popover. The files `more_plate.md`, `more_beam.md` and `more_purlin.md` hold identical text:

> - **Flat plate / point-supported:** Floor system spans two ways and is supported at discrete column locations. There are no beams or girders.
> - **Post and beam:** Floor system spans one way onto beams, which transfer loads to columns.
> - **Purlin on girder:** Floor system is supported by closely-spaced purlins / secondary beams, which then span between larger girders.
>
> These are common structural systems, but it's far from an exhaustive list.
> **If you want to explore further options for your project, use the Contact button to reach out to a StructureCraft engineer.**

**Floor-system tooltips** have no MORE link. Verbatim:
- "Cross-Laminated Timber (CLT) — Multi-layered wood panels with alternating grain directions. Typically available in odd numbers of lamination lay-ups."
- "Mass Plywood Panel (MPP) / Veneer Laminated Timber (VLT) — Large-scale plywood-like panels made from many thin veneer layers glued together."
- "Dowel-Laminated Timber (DLT) — Parallel timber laminations are connected by timber dowels. Typically available in depths corresponding to readily available lumber widths."
- "Future feature: Glulam beams on flat (GLT) — Layers of lumber bonded with adhesive form tall, slender glulam planks. These planks are laid on their side and used as decking."
- "Flat plate"
- "Future feature: Precast hollow-core planks"
- "Future feature: Precast double tees"
- "Slab on metal deck"
- "Future feature: Roof deck"

## 9. Oddities worth knowing before copying these rules

1. **Purlins ignore cores.** They run through the core voids, while the girders are split and supported on the core.
2. **The girder drop is capped at 203.2 mm, and only for glulam.** Purlins therefore cut into the girders instead of sitting on them. The Summary statistics still add the depths as if the members were stacked.
3. **Perimeter beams are never dropped**, so a dropped girder meets them 203 mm lower.
4. **Strips and panel joints ignore the column grid.** They start at x or y = 0 + 3 mm with the supplier's width. They coincide with column lines only when the bay equals the panel width, as in the wizard's 11.5 ft Plate bay.
5. **Changing the floor profile resets the supplier** to the first one in its list (CLT becomes Element 5).
6. **The Plate span toggle** affects only the strip orientation and which bay is checked against the panel width. Under Concrete it is locked.
7. **Unused beam material under Purlin + Concrete floor.** With the floor switched to concrete but the beams left as Glulam, the girders are still dropped (`purlin_concrete_*`).