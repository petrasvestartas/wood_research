# Branch3D Concept Lite: UI map and configuration sweep

I explored the whole Concept Lite UI: the wizard, both side panels, the viewport controls, and a configuration sweep with 8 system × material combinations plus about 25 one-at-a-time variations. Everything is saved: 441 PNG screenshots (numbered 010–483; gaps are failed shots I deleted) and a log with one line per screenshot, with no missing or extra entries. The log also records how each shot was taken and the model data behind it (member counts, cross-sections, statistics).

**Output folder:** `/tmp/claude-1000/-home-petras-code-code-cpp-wood-research/cd17883b-ad50-44cc-bbcd-c4f797944a70/scratchpad/reference/branch3d_ui/`
- `log.md`: one line per screenshot.
- `params_<tag>.json`: the full parameter state for each sweep configuration.
- `sweep*.json`: raw capture output, including per-level counts, cross-sections and statistics.
- `driver.js` and `helpers.js`: the Playwright driver.
- It uses a copy of the other agent's patched bundle. Nothing was written to its folder.

**Problems during the run** (all recorded in the log):
- **Stray desktop clicks.** The headful window sits on the live display `:0`. Real mouse clicks landed on it between my steps and changed the model three times: the floor switched to DLT, a face drag collapsed the footprint, and the system switched to Post and beam. The shots affected are marked invalid in the log. After shot 213 the driver ignores all real mouse and keyboard input unless one of my steps is running.
- **Page crash.** Dragging a perimeter corner across the building crashed the page ("Target crashed"). I rebuilt the browser session, and the L-shaped footprint in B6d was then set through the app's internal store (JS) instead of the UI.
- **Wrong camera in some shots.** After the rebuild the page had three camera controllers and my camera code moved only one. The first shots of B6a/B6b (plans only) and B7–B9 are off-centre and marked `CAMERA WRONG`. The `_v2` shots (433–483) replace them.
- **No email given.** The "Tell us about yourself!" email gate (shot 038) was bypassed through localStorage flags, so no email was sent. The link shortener was stubbed locally and analytics were blocked.

## 1. Start wizard (010–024, 196)
- The wizard is a single dialog, "Welcome to Branch Concept Lite!", with three rows. Nothing is pre-selected. Clicking a selected tile deselects it (021).
- **1 Select Building Type** ("Get started by choosing a building shape with preset grid spacing and loading. You can edit everything later."): Residential / Office / Institutional.
  - When reopened with the reset button, a 4th tile "Current" appears and is pre-selected. The title becomes "Welcome back! Refine your model or start over" and a close X is available (196).
- **2 Select Structural System**: Point supported / Post and beam / Purlin on girder.
- **3 Select Structural Material**: Mass Timber / Concrete / Steel.
  - Point supported disables Steel (015), and Steel disables Point supported (020).
- "Generate my model!" is enabled only when all three rows are chosen. Footer: "By proceeding, you agree to our Terms of Service and Privacy Policy".
- I finished once with Office + Purlin on girder + Mass Timber (023–024). That gives a 150'×180' footprint, 6 stories @ 14', 2 cores and 30'×30' bays.
- After Generate, a 12-step tour ran (025–037): "Welcome to Branch!", "Project Location", "Suppliers & Materials", "Model Geometry", "Carbon Calculations", "Inspecting Calculations", "Life Cycle Stages", "Material & Element Toggles", "Color by Size", "Metric & Imperial Units", "Share Your Design", "You're all set!".
- The email gate appears 60 s after first load (038). It has fields Email, roles Architect/Developer/Engineer/Manufacturer/Other, and "Keep me posted…". Its only button is "Keep exploring" and it has no close.

## 2. Top toolbar (180–199; 188, 192–194)
| Button | Tooltip (verbatim) | Effect |
|---|---|---|
| Palette | "Color by size." (MORE: "Concept Lite sizes every beam, column, and floor in real time … the 'Color by size' shows the approximate size of each beam and column.") | Teal gradient on members, plus a legend of size ranges, e.g. "Glulam Beams 2' – 2'-7"", "Steel Columns W8 – W8" (192) |
| Layers | "Single-story view" | Shows one story with the slab above removed and cores as boxes (193) |
| Ruler | "Toggle metric and imperial units" | Switches to m / mm / kN/m² / tonnes (194–195) |
| Circular arrows | "Reset your model" | Reopens the wizard with "Current" (196) |
| Share | "Create a link to share your model." (MORE text in 190) | Posts base64 JSON to the shortener; toast "Link Copied! A link to a snapshot of this model has been copied to your clipboard…" (197) |
| Help | "Videos, tutorials, and FAQs" | Modal "Learn Branch Concept Lite": Take the tour! / Resources: "Access more tutorials for guidance" (YouTube), "FAQ for quick answers" / Settings: "Privacy Settings", which opens the cookie card with Reject / Accept (198, 432) |
| Contact | "Contact an engineer or give feedback" | "Thanks for reaching out! What would you like to do?": "Contact an Engineer" / "Feedback for Branch" (199) |

`<` and `>` collapse the left and right panels (258).

## 3. LEFT panel ("Inputs"; 037–178)
Everything sits under one collapsible "Building Parameters" header; its chevron collapses the whole panel (120).

**Building Parameters**
- Building Type tiles with tooltips:
  - Normal: "Residential, light commercial, and office loading" (15/65 psf)
  - High: "Assembly spaces, educational institutions, and healthcare facilities" (25/100)
  - Storage: "Heavy-duty loading for industrial and storage buildings" (25/125)
- SDL slider + input, 0–100 psf. Tooltip "Superimposed Dead Load: Permanent loads beyond the structure's self-weight … 10 psf … 75 psf …"
- LL slider + input, 0–200 psf. Tooltip "Live Load: … 60 psf … 100 psf …"
- Typing a load deselects the tiles (buildingType becomes "Unset", 123).
- Fire select (flame icon), tooltip "Building-code-required fire rating for structural components.": Unrated / 1 hour fire rating / 2 hour fire rating (default) / 3 hour fire rating (107). The MORE text is in 101.

**Project Location**
- Address box "Enter address for accurate carbon", backed by Mapbox. Typing "Zurich" lists: Zürich, Zurich, Switzerland; Zurich, Switzerland; Zurich, Friesland, Netherlands; Zurich, Ontario, Canada; Zurich, Kansas, United States (117).
- The default is Seattle. Picking Zürich changes the continent to Europe and carbon from 1,304 to 1,523 tCO2e (118).

**Typical Bay**
- Tiles: Span X "Girders / primary beams span along the model's X-axis" and Span Y ("…Y-axis").
- X Spacing / Y Spacing sliders: 4–50 ft in 0.25 steps (metric 1–15.2 m). Changing them regenerates uniform grid lines.
- Errors show on the input, e.g. "Exceeds maximum span of 22'" and "…of 11.5'" for point-supported CLT (129–130).

**Structural System** ("Framing System")
- Flat plate / point-supported, Post and beam, "Purlin on girder / girder with secondary beams". The MORE text defines all three (106).
- Plate is disabled when the floor is Composite or DLT.

**Floor Slabs card**
- Profile row by floor material:
  - **Timber:** Cross-Laminated Timber (CLT); Mass Plywood Panel (MPP) / Veneer Laminated Timber (VLT); Dowel-Laminated Timber (DLT) (disabled for Plate: "Material incompatible with system — Dowel-Laminated Timber cannot be used in a point-supported scheme."); "Future feature: Glulam beams on flat (GLT)". Each tooltip includes a one-line description (051–087).
  - **Concrete:** Flat plate; "Future feature: Precast hollow-core planks"; "Future feature: Precast double tees".
  - **Composite:** Slab on metal deck; "Future feature: Roof deck".
- Supplier (tooltip "Supplier", MORE text in 103), with North America / Europe tabs:
  - CLT: Element 5, Kalesnikoff, Mercer (WA), Mercer Conway (AR), Mercer Penticton (BC), Nordic, Smartlam (AL), Smartlam (MT), Vaagen Timbers | Binderholz, Hasslacher, KLH, Mayr Melnhof, Stora Enso.
  - MPP: Boise Cascade, Freres Lumber.
  - DLT: DowelLam.
  - Concrete: region select North America / Global. Composite: North America / Europe / Global.
- Fire Protection:
  - Timber: Exposed; 5/8" gypsum (40 minutes); 5/8" gypsum x2 (80 minutes); 5/8" gypsum x3 (120 minutes).
  - Composite: Exposed; 1/2" SAFP (60 minutes); 1.5" SAFP (120 minutes); 2" SAFP (180 minutes); Intumescent paint.
  - Concrete: the select is disabled.
- Concrete Topping slider: 0–6 in (metric 0–150 mm), default 2.0". MORE text in 105. Disabled unless the floor is Timber.
- Floor material tiles: Timber / Concrete / Composite. Composite is disabled for Plate: "…Slab-on-metal deck, as a one-way spanning system, cannot be used in a point-supported scheme." (132).

**Beams card**
- Beam material tiles: Glulam / Concrete / Steel. For Plate the whole card is disabled: "Not in system — No beams are used in a point-supported system" (133–134).
- Girder profiles:
  - Glulam: Rectangular; "Future feature: Square"; "Future feature: Double girders".
  - Concrete: Rectangular; "Future feature: Slab band"; "Future feature: Precast girders".
  - Steel: Steel W; Steel HSS (disabled, no explanation); "Future feature: Open web joists".
- Manufacturer (glulam) has two tabs:
  - North America: Anthony Forest Products, Boise Cascade, DR Johnson, Goodlam, Kalesnikoff, Nordic, QB Corporation, Smartlam (AL), Timberlab Laminators, Vaagen Timbers, Western Archrib (AB), Western Archrib (MB), Zip-O-Laminators.
  - Europe: Binderholz, Hasslacher, Mayr Melnhof, Wiehag.
- For Concrete and Steel the manufacturer becomes "Manufacturer location": Concrete NA / Global; Steel NA / Europe / Global.
- Protection lists are the same as for floors. Concrete protection is disabled.
- The "Purlin" sub-card is renamed "Secondary Beam" when the beam material is not Glulam. It is disabled for Post and beam: "Not in system — No purlins are used in a post and beam system" (136).
  - Profiles: Rectangular / Steel W / "Future feature: Double purlins"; Concrete gives Rectangular / "Future feature: Slab band beams".
  - Purlin Spacing slider 2–20 ft, tooltip "Maximum spacing between purlins / secondary beams".

**Columns card**
- Material tiles: Glulam / Concrete / Steel.
- Type: Glulam and Concrete offer Square, with Rectangular and Round disabled. Steel offers Steel W, Steel HSS, and "Future feature: Round HSS / Pipe".
- Manufacturer and Protection lists are the same as for beams.

The illustration in the middle of the panel changes with the chosen system and material.

## 4. RIGHT panel ("Outputs"; 205–257)
Tabs: Summary / Quantities / Carbon / Cost, plus a disabled "Future feature: Structural analysis".

**Summary tab (210, 214–241)**
- **Building Statistics.** Each value's tooltip explains it (214–219): Area per floor, Total floor area, Total building height, Building dimension, Typical floor height, Minimum clear height ("…takes into account any required fire protection layers").
- **Superstructure Summary (excl Core).** Three bars (steel lb/sf 0–60; concrete ft³/sf | rebar pcy 0–1.5; timber ft³/sf 0–1.5). Each (i) opens a formula, e.g. "+96,768.1 ft³ (Floor) +27,404.1 (Purlin) +19,120.6 (Beam) +5,355.2 (Column) = 148,648ft³ / 155,400sf = 0.96" (233–235).
- **Carbon Summary (excl Core).** Total emissions, GWP with and without biogenic carbon, and the SCO₂RS rating A++…G (bands 0–400 kgCO₂e/m²). The (i) says "…rated A+ … Currently, the average building is rated D" (236).
- **Weight by Material donut.**
  - Icons: "Show data for weight" / "Show data for carbon in Global Warning Potential (GWP)" (sic).
  - Switch: "Switch to group data by structural element". By element shows Girders & Purlins / Columns / Floors / Topping / Foundations (240).
  - Clicking a legend item highlights those members in dark red and shows a breakdown (237).

**Quantities tab (211, 242–244)**
- The same summary block, plus the note: "Concept Lite analyzes and sizes every element in real time. 'Lite' shares the aggregated results, but not the data for specific elements; we're saving that for Concept Pro!…"
- Table columns Type / Size/Source / Quantities. Rows are Deck / Girder / Purlin / Column:
  - Size always reads "Size: varies", with the supplier and product.
  - Quantities: volume in ft³ and ft³/kft², or lb and lb/ft² for steel; pieces and pcs/kft².
  - Then Superstructure Total pcs, Concrete Substructure Volume and Weight.
- The chart adds "Show data by volume".

**Carbon tab (212, 246–257)**
- "Cradle to Handover" row: stages A1-A3 "Production", A4 "Transport", A5 "Construction" active; B1-B5 "Operational", C1-C5 "End of Life", D "Afterlife" greyed.
- The expand icon opens the LCA methodology image (252).
- GWP by Material, and GWP by Life Cycle Stage with a table.
- The A4 (i) shows the transport table TCO₂e / Weight / Rail / Truck / Ship km per material, "20 gCO₂e per tonne-km for rail, 70 … trucking, 12 … shipping" (254). Biogenic (i) in 256.

**Cost tab (213):** only a "Contact an Engineer" button and "Request access for real-time pricing of your structure."

**Warnings (427–430):** orange banner "Some elements require custom sizes. LEARN MORE". The Warning card reads: "Custom, larger-than-typically-available sizes are required for: Floor panels in 9/9 grid intervals…" with buttons:
- "View in Model": turns on Color by size and Single-story view, and draws the offending parts orange.
- "Reset Grids": regenerated 15' × 11.5' bays for the plate case.

## 5. Viewport
- **Overlays.** An editable story dimension "[6] @ [14'] = 84'-0"". The overall dimensions (e.g. 180'-0") are read-only; their tooltip says "Try pulling the model directly!" (258–260). Grid bubbles sit only on interior grid lines.
- **ViewCube.** Clicking TOP gives the app's own plan view (266–267).
- **Clicking the roof** opens a floating "TAB to input" panel: Stories, Story height, Substories, Substory height, Cores 0|1|2 (302–303). Dragging the top floor vertically changes the story count.
- **Clicking a core** opens a core panel with Width and Depth, a swap-dimensions icon and a delete icon. Cores drag freely without snapping (351–353).
- **Grid lines:**
  - Right-click (or click) a bubble to open a widget with bay-length inputs, "=" (set all bays to this value) and +/− buttons (264, 321).
  - "+" inserts a line midway to the next one; "−" deletes it (330–335).
  - Dragging a line moves it continuously, with no snapping (x=90 → 99.95, 326–329).
- **Perimeter:**
  - Hovering the ground edge highlights the white polyline and shows an add-point marker.
  - A point is added only by a slow click just outside the edge. Clicking on the edge hits the building face, and clicking at a grid line grabs the grid line (357–364).
  - Faces push and pull along their normal, which moves both end vertices (366–368).
- Color by size and Single-story view are covered in section 2. A hidden `debug` state key has no visible effect (431).

## 6. Configuration sweep
### A. System × material via the wizard "Current" tile
Geometry was kept at a 120'×90' rectangle, 3 stories @ 12', no cores. Per-level counts; clear/depth in ft. Shots are listed as iso, plan, panels, clean plan.

| Config | Spacing / span | Members per level | Floor | Clear / depth | Shots |
|---|---|---|---|---|---|
| Purlin + Timber | 30×30, span Y | 20 col; 9 girders along Y 320×800; 14 perimeter (260×600 / 300×720); 32 purlins along X 260×640 every 10' (also on the Y grid lines) | CLT 7.47" | 6.49 / 5.51 | 269–271, 295 |
| Purlin + Concrete | 30×30, Y | 9 girders 300×740; 32 secondary 300×500; col 400² | flat plate 6" | 7.43 / 4.57 | 272–274, 296 |
| Purlin + Steel | 30×30, **X** | 8 girders along X W24X68; 33 secondary along Y W18X40; col W8X28–58 | composite 6.75" | 7.97 / 4.03 | 275–277, 297 |
| Beam + Timber | 30×20, X | 30 col; 16 girders along X 320×720 / 300×680; 18 perimeter | CLT 9.29" | 8.68 / 3.32 | 278–280, 298 |
| Beam + Concrete | 30×15, Y | 35 col; 18 girders along Y 300×500; 20 perimeter | flat plate **14.4"** (spans 30' between girders) | 9.16 / 2.84 | 281–283, 299 |
| Beam + Steel | 30×12, X | 45 col; 28 girders W21X44 / W18X35; 16 edge W6X9 | composite 7.5" | 9.65 / 2.35 | 284–286, 300 |
| Plate + Timber | 11.5×15, X | 84 col 280–300²; no beams, not even at the perimeter; last X bay only 5' | CLT 11.65" | 10.86 / 1.14 | 287–289, 301 |
| Plate + Concrete | 25×25 | 30 col 400² | flat plate 13.56" | 10.86 | 290–292, 294 |

Plate + Steel is not allowed.

### B. One change at a time from Purlin + Mass Timber
Clean shots for B1/B2 are 433–437 and for B7–B9 are the `_v2` shots 442–483.

- **B1 span direction** (304–309, 433–434): span X puts the girders along X on y=30/60 (9→8) and turns the purlins to run along Y at 10' (32→33). The panel layout changes from 22 to 16 panels. Sizes are unchanged.
- **B2 purlin spacing** (310–319, 435–437):
  - 4': 92 purlins 220×520, purlin volume doubled, clear height +0.4'.
  - 16' and 20': both give the same 20 purlins at 15' on centre. But at 20' the CLT is 9.52" instead of 7.87" and the purlins are 300×680 instead of 280×680, so the floor is sized from the max-spacing input, not the actual spacing. No error is shown.
- **B3 uneven bays** (320–335):
  - Typed 20' gives x=[20,60,90]: purlins sized per bay (240×520 / 300×720 / 260×640), some girders 340×840.
  - Dragged line: similar result.
  - "+" appends 75 unsorted to [30,60,90,75]: 24 columns, 40 purlins.
  - "−" leaves a 60' bay: purlins 400×920, clear height 5.31'.
- **B4 stories** (336–343, 440–441): 1 story gives smaller columns (280–320). 5 stories + 1 substory:
  - The basement is concrete: 400/425 columns, 300×500–640 beams, no purlins, flat plate.
  - Footings sit under the basement, and upper columns grow to 360–440.
- **B5 cores** (344–356):
  - Core 1 is auto-placed at 29×29 and makes a floor hole.
  - The girder crossing it is cut, leaving two 0.5' (220×200) stubs between column and core.
  - Purlins stop at the core faces.
  - Core 2 (15×15) landed on grid node (30,30) and deleted that column.
  - A moved core keeps a continuous position.
- **B6 footprint:**
  - UI edit with a diagonal edge (369–371): sloped edge beam, purlins clipped to it.
  - L-shape set via JS (374–376): a column at the re-entrant corner, and the 15' leg is framed by the x=30 girder plus the edge.
  - Residential preset (377–380, 438): L 144×220, 12 stories, 2 cores, 42 columns per level.
  - Institutional preset (381–384, 439): C-shape 150×230, 8 stories @ 16'.
- **B7 profiles** (442–462):
  - Steel W columns W8X24–48; Steel HSS columns HSS5–7; concrete columns 400² (the 2-hour minimum).
  - Steel girders W24X76, with purlins staying glulam: clear height 7.12.
  - Steel + steel secondary beams W21X44: 7.49.
  - Concrete girders 300×660 and purlins 300×500 under CLT: 7.41.
  - Glulam girders + W21X44 purlins: 6.86.
- **B8 floors** (463–474):
  - MPP 6.25" (Boise Cascade), about 60 panels.
  - DLT 5.35" (DowelLam), 18 panels.
  - Composite 6.75", which makes the glulam heavier (girders 360×840).
  - Flat plate 6" on glulam purlins 280×680 and girders 360×880.
- **B9 fire** (475–483):
  - Unrated: CLT 3.43", girders 200×880, purlins 120×720, columns 280² (the minimum).
  - 2 hours + 5/8" gypsum ×3 everywhere: identical member sizes to unrated, and clear height drops about 0.3'.
  - 3 hours exposed: girders 420×800, purlins 320×680, columns up to 459².

## 7. Surprises
1. **Purlins are stacked on top of girders, not flush-framed.** Floor depth = slab + purlin + girder + topping (0.62 + 2.1 + 2.63 + 0.17 = 5.51 ft), so a 12' story has only 6.5' clear.
2. **The floor is sized from the purlin-spacing input, not the actual spacing** (B2).
3. **The wizard and the panel give different steel models.**
   - Wizard Steel sets steel purlins, span X and a composite floor.
   - Switching beams to Steel in the panel keeps glulam purlins, giving a hybrid.
   - Switching away and back resets the supplier to the first in the list (e.g. Element 5).
4. **Span direction comes from a rule, not the user.** Timber other than purlin-on-girder, and Steel, get span X; everything else gets Y. That is how Post and beam + Concrete ends up with 30' one-way 14.4" slabs.
5. **Grid data is loose.**
   - Grid lists hold interior lines only; the footprint edges are implicit.
   - "+" appends positions unsorted.
   - Dragged lines and cores are not snapped.
   - "Current" keeps the footprint, so non-multiple spacings leave leftover bays (5').
6. **Point-supported is limited.**
   - It has no perimeter beams.
   - CLT spans are capped at 22' × 11.5' (panel width).
   - DLT and Composite are disabled.
7. **Steel HSS girder is disabled with no explanation**, unlike the "Future feature" items.
8. **Perimeter editing is fragile.**
   - Adding a point is finicky.
   - Pushing a face drags both of its vertices, so there is no extrusion.
   - Dragging a corner across the building crashed the renderer.
9. **Privacy and tracking.**
   - After the wizard, `cookies_accepted=true` was already in localStorage without the banner ever showing, which enables analytics and Sentry.
   - Share requires the email gate.
10. **Notes for automation.**
    - The app registers several orbit controllers on one camera.
    - A camera set straight down snaps to the app's own TOP view.
    - The app also caps the camera distance (about 1,064 ft for the large presets).
    - The canvas renders at 1.5× device pixel ratio.