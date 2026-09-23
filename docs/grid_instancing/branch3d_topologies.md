# Branch3D Concept Lite: every "Reset your model" wizard topology

**Source.** I drove https://concept.branch3d.com/ (bundle `index-CxNXZKiq.js`) in Chrome with Playwright at 1600x1000. For every combination I pressed **Reset your model** (the 4th header button; its tooltip text is checked each run and saved as `reset_tooltip.png`), then clicked through the wizard (Building Type, then Structural System, then Structural Material) and pressed **Generate my model!**. Each preset check (`preset_check: []` in the JSON) confirms that the store the app ended up with equals `KT(Uwe(type, system, material))`, the app's own preset function.

**Units.** Branch stores everything in feet. I converted to mm as ft x 304.8.

**Files.** All captures are under `reference/branch3d_topologies/`, one folder `<type>_<system>_<material>/` per combination. Each folder holds:
- `wizard.png`: the wizard state just before Generate
- `ui.png`: the whole UI, Metric
- `panel_1.png`, `panel_2.png`: the left settings panel, scrolled
- `iso.png`, `plan.png`: 3/4 view and top view
- `iso_framing.png`, `plan_framing.png`: the same two views with the floor slab, the CLT panel lines and the steel deck hidden in the three.js scene
- `<combo>.json`: the full store in ft and the footprint, grid, cores, storeys and profiles in mm, counts per level, every member of one typical level in mm (columns, girders, perimeter beams, purlins with sections), floor span data, `statistics`, piece counts and the left-panel values

The capture script is `capture_topologies.js` (run as `node capture_topologies.js <Residential|Office|Institutional|Current> [combo...]`). The summary script is `analyze.py`.

## 1. What the wizard offers

- **First visit:** Residential, Office and Institutional. **After a model exists:** Current as well. For each: Point supported, Post and beam, Purlin on girder, and Mass Timber, Concrete, Steel.
- **Point supported and Steel exclude each other**: each greys the other out (`wizard_disabled.png`). That leaves **8 combinations per type**. I captured 8 x 4 = **32 models**; the 4 disabled combinations have a stub JSON and a screenshot.
- **Current** keeps the current model's polyline, cores and storeys, and only applies the new system and material plus the `zM.Current` spacing table. That table equals the Office table except Point supported + Steel, which is disabled anyway. I ran Current on top of Office / Post and beam / Mass Timber. It never switches to the trimmed "point-supported" footprint, so Current + Point supported on the 150 ft Office leaves a 12 ft remainder bay.
- **Sub-stories are 0 in every preset.** Loads are Normal (SDL 0.7 kN/m², LL 3.1 kN/m²) with a 2 h fire rating. Suppliers are Kalesnikoff for Mass Timber and "North America" for the others. The same values appear in every combination.

**Grid rule (`ZW`).** Interior grid lines sit at `min + k*spacing` while `< max - 1 ft` (304.8 mm). The polyline's bbox edges close the grid, so the **last bay is the remainder**. Columns go:
- at every grid intersection inside the polygon,
- at every point where a grid line crosses the perimeter,
- at every polygon vertex.

Columns closer than 1 m are merged, and columns inside a core are dropped. Perimeter beams run on every polygon edge. Beams are cut at core edges, and cores become floor holes.

**Span direction.** The girders run along `spanDirection`, and the deck spans the other way.
- Purlins run perpendicular to the girders, `ceil(bay / 10 ft)` per bay, so at 3048 mm for a 30 ft bay. There is also one on each grid line.
- `spanDirection = X` for Mass Timber (Point supported and Post and beam) and for Steel (all systems). It is `Y` for Concrete (all systems) and for Mass Timber Purlin on girder.

## 2. The six footprint + core sets (the geometry behind every combination)

"PS" means the Point-supported variant. Its footprint width is trimmed to a multiple of the 11.5 ft (3505.2 mm) panel module, and the cores are shifted by the same amount. This trimming depends on the system, not the material, so PS + Concrete uses the trimmed footprint too.

| Set | Shape | Polyline (mm, CCW from origin) | Overall (mm) | Cores (min corner x,y; size x by y; mm) | Storeys |
|---|---|---|---|---|---|
| **R** Residential | **L**: 21945.6 wide leg (y 0 to 45720) plus a 43891.2 x 21336 head at the top | (0,0) (21945.6,0) (21945.6,45720) (43891.2,45720) (43891.2,67056) (0,67056) | 43891.2 x 67056 | A (15849.6, 45720) 6096x9144, in the re-entrant corner with its east face on the leg facade line x=21945.6<br>B (12496.8, 9144) 3048x6096, inside the leg near its south end | 12 x 3657.6 = 43891.2 |
| **R-PS** | L, trimmed to 69/138 ft | (0,0) (21031.2,0) (21031.2,45720) (42062.4,45720) (42062.4,67056) (0,67056) | 42062.4 x 67056 | A (14935.2, 45720) 6096x9144<br>B (11582.4, 9144) 3048x6096 | 12 x 3657.6 |
| **O** Office | **Rectangle** | (0,0) (45720,0) (45720,54864) (0,54864) | 45720 x 54864 | A (15240, 27432) 9144x9144, centre (19812, 32004)<br>B (18288, 14020.8) 6096x3048<br>Both interior, off-centre to the west | 6 x 4267.2 = 25603.2 |
| **O-PS** | Rectangle, 149.5 ft | (0,0) (45567.6,0) (45567.6,54864) (0,54864) | 45567.6 x 54864 | same as O (the Office preset has no PS cores) | 6 x 4267.2 |
| **I** Institutional | **U / C** open to +x. The west spine is 18288 wide; south and north wings are 45720 x 21336 each; the courtyard is 27432 x 27432 (x 18288 to 45720, y 21336 to 48768) | (0,0) (45720,0) (45720,21336) (18288,21336) (18288,48768) (45720,48768) (45720,70104) (0,70104) | 45720 x 70104 | A (12192, 48768) 6096x9144, at the courtyard's NW inner corner (east face x=18288, south face y=48768)<br>B (15240, 15240) 3048x6096, at the SW inner corner (its NE corner touches (18288, 21336)) | 8 x 4876.8 = 39014.4 |
| **I-PS** | U, trimmed to 149.5 / 57.5 ft | (0,0) (45567.6,0) (45567.6,21336) (17526,21336) (17526,48768) (45567.6,48768) (45567.6,70104) (0,70104) | 45567.6 x 70104 | A (11430, 48768) 6096x9144<br>B (14478, 15240) 3048x6096 | 8 x 4876.8 |

## 3. All combinations

- Spacing is `[X, Y]` in mm.
- Bays are listed x then y, with the remainder bay last.
- Counts are for **one typical level**: columns (of which on the boundary), girders, perimeter beams and purlins. Every level is the same, so the total is the count x storeys.
- Floor thickness excludes the 50.8 mm topping that the timber options carry.

| Combination | Set | Spacing mm | Bays x | Bays y | Span | Columns | Girders | Perim. beams | Purlins | Floor |
|---|---|---|---|---|---|---|---|---|---|---|
| residential / PS / Mass Timber | R-PS | 3505.2 x 4572 | 12x3505.2 | 14x4572 + 3048 | X | 140 (53) | 0 | 0 | 0 | CLT two-way plate 291.4 + 50.8 |
| residential / PS / Concrete | R-PS | 7620 x 7620 | 5x7620 + 3962.4 | 8x7620 + 6096 | Y | 50 (30) | 0 | 0 | 0 | Flat plate 346.1 |
| residential / PS / Steel | disabled | | | | | | | | | |
| residential / Post+beam / Mass Timber | R | 7620 x 4572 | 5x7620 + 5791.2 | 14x4572 + 3048 | X | 79 (41) | 56 | 42 | 0 | CLT 189.8 + 50.8 |
| residential / Post+beam / Concrete | R | 9144 x 4572 | 4x9144 + 7315.2 | 14x4572 + 3048 | Y | 73 (40) | 38 | 41 | 0 | Flat plate 359.9 (spans 9144) |
| residential / Post+beam / Steel | R | 9144 x 3657.6 | 4x9144 + 7315.2 | 18x3657.6 + 1219.2 | X | 94 (49) | 68 | 50 | 0 | Composite deck 190.5 |
| residential / Purlin / Mass Timber | R | 9144 x 9144 | 4x9144 + 7315.2 | 7x9144 + 3048 | Y | 42 (26) | 21 | 27 | 75 | CLT 189.8 + 50.8 |
| residential / Purlin / Concrete | R | 9144 x 9144 | same | same | Y | 42 (26) | 21 | 27 | 75 | Flat plate 152.4 |
| residential / Purlin / Steel | R | 9144 x 9144 | same | same | X | 42 (26) | 25 | 27 | 77 | Composite deck 171.5 |
| office / PS / Mass Timber | O-PS | 3505.2 x 4572 | 13x3505.2 | 12x4572 | X | 176 (50) | 0 | 0 | 0 | CLT plate 295.8 + 50.8 |
| office / PS / Concrete | O-PS | 7620 x 7620 | 5x7620 + 7467.6 | 7x7620 + 1524 | Y | 60 (28) | 0 | 0 | 0 | Flat plate 345.2 |
| office / PS / Steel | disabled | | | | | | | | | |
| office / Post+beam / Mass Timber | O | 9144 x 6096 | 5x9144 | 9x6096 | X | 58 (28) | 40 | 28 | 0 | CLT 241.8 + 50.8 |
| office / Post+beam / Concrete | O | 9144 x 4572 | 5x9144 | 12x4572 | Y | 75 (34) | 47 | 34 | 0 | Flat plate 365.8 |
| office / Post+beam / Steel | O | 9144 x 3657.6 | 5x9144 | 15x3657.6 | X | 92 (40) | 70 | 40 | 0 | Composite deck 190.5 |
| office / Purlin / Mass Timber | O | 9144 x 9144 | 5x9144 | 6x9144 | Y | 40 (22) | 24 | 22 | 85 | CLT 189.8 + 50.8 |
| office / Purlin / Concrete | O | 9144 x 9144 | 5x9144 | 6x9144 | Y | 40 (22) | 24 | 22 | 85 | Flat plate 152.4 |
| office / Purlin / Steel | O | 9144 x 9144 | 5x9144 | 6x9144 | X | 40 (22) | 25 | 22 | 84 | Composite deck 171.5 |
| institutional / PS / Mass Timber | I-PS | 3505.2 x 4572 | 13x3505.2 | 15x4572 + 1524 | X | 201 (74) | 0 | 0 | 0 | CLT plate 294.3 + 50.8 |
| institutional / PS / Concrete | I-PS | 7620 x 7620 | 5x7620 + 7467.6 | 9x7620 + 1524 | Y | 71 (40) | 0 | 0 | 0 | Flat plate 345.4 |
| institutional / PS / Steel | disabled | | | | | | | | | |
| institutional / Post+beam / Mass Timber | I | 9144 x 6096 | 5x9144 | 11x6096 + 3048 | X | 66 (39) | 40 | 41 | 0 | CLT 239.7 + 50.8 |
| institutional / Post+beam / Concrete | I | 9144 x 4572 | 5x9144 | 15x4572 + 1524 | Y | 87 (48) | 46 | 50 | 0 | Flat plate 365.8 |
| institutional / Post+beam / Steel | I | 9144 x 3657.6 | 5x9144 | 19x3657.6 + 609.6 | X | 98 (53) | 66 | 55 | 0 | Composite deck 190.5 |
| institutional / Purlin / Mass Timber | I | 9144 x 9144 | 5x9144 | 7x9144 + 6096 | Y | 49 (32) | 24 | 34 | 80 | CLT 189.8 + 50.8 |
| institutional / Purlin / Concrete | I | 9144 x 9144 | same | same | Y | 49 (32) | 24 | 34 | 80 | Flat plate 152.4 |
| institutional / Purlin / Steel | I | 9144 x 9144 | same | same | X | 49 (32) | 26 | 34 | 94 | Composite deck 171.5 |
| current* / PS / Mass Timber | O (not trimmed) | 3505.2 x 4572 | 12x3505.2 + 3657.6 | 12x4572 | X | 176 (50) | 0 | 0 | 0 | CLT plate 295.8 + 50.8 |
| current* / PS / Concrete | O | 7620 x 7620 | 6x7620 | 7x7620 + 1524 | Y | 60 (28) | 0 | 0 | 0 | Flat plate 345.2 |
| current* / PS / Steel | disabled | | | | | | | | | |
| current* / Post+beam / MT, Concrete, Steel | O | same as office | | | | same as office | | | | |
| current* / Purlin / MT, Concrete, Steel | O | same as office | | | | same as office | | | | |

\*Current was run on the Office / Post and beam / Mass Timber base.

The whole-building totals equal the per-level counts x storeys. For example:
- Residential Post+beam Mass Timber: 948 columns, 672 girders, 504 perimeter beams.
- Residential Purlin Mass Timber: 504 columns, 252 girders, 324 perimeter beams, 900 purlins.

Each JSON has `counts_per_level` and `totals`.

## 4. What changes with material

- **Bay spacing (table `zM`, ft).**

  | System | Mass Timber | Concrete | Steel |
  |---|---|---|---|
  | Post and beam | 25x15 (Residential), 30x20 (Office, Institutional) | 30x15 | 30x12 |
  | Point supported | 11.5x15 (the panel module) | 25x25 | disabled |
  | Purlin on girder | 30x30 | 30x30 | 30x30 |

  Purlin-on-girder grids are therefore **identical for all three materials**.
- **Framing direction.**
  - Post and beam, timber: girders run X over the long 7620/9144 span, and the CLT spans the short 4572/6096 in Y.
  - Post and beam, concrete: beams run Y on the 9144-apart x lines over the short 4572, and the flat plate spans 9144 in X.
  - Post and beam, steel: girders run X over 9144, and the deck spans 3657.6.
  - Purlin on girder, timber and concrete: girders run Y, and purlins run X at 3048.
  - Purlin on girder, steel: girders run X, and purlins run Y at 3048. This gives slightly more girders and purlins, because the direction flips relative to the footprint.
- **Floors.**
  - Timber: CLT, 189.8 mm (one-way ≤ 4572 or on purlins), 239.7 to 241.8 mm (6096 span), 291 to 296 mm (two-way plate on columns), always with a 50.8 mm topping.
  - Concrete: flat plate, 345 to 366 mm without beams or with the 9144 one-way span, 152.4 mm on purlins.
  - Steel: composite slab on metal deck, 190.5 mm (Post and beam) or 171.5 mm (on purlins).
- **Sections (ground-floor level in the JSON, all combinations together).**
  - Glulam: square columns 280 to 560 mm; girders from 220x200 to 320x800; purlins 220x360 to 260x640 (260x640 on a 9144 span).
  - Concrete: square columns 400 to 750 mm; beams and purlins 300 wide, 300 to 740 deep.
  - Steel: columns W8X18 to W12X152, girders W8 to W24, purlins W10X12 to W18X40.
- **Point-supported footprints** are trimmed by the system, not the material: Residential 72→69 / 144→138 ft, Institutional 150→149.5 / 60→57.5, Office 150→149.5.

## 5. DISTINCT topologies to reproduce with our wood grid

A topology here means footprint + cores + spacing + storeys. There are **18 distinct ones** among the presets, plus 2 more from Current, built on only 6 footprint/core sets (§2). For the wood grid, the **9 Mass Timber ones are the targets**. The rest are the same footprints with other spacings.

| # | Name | Footprint + cores | Grid x lines (mm, incl. edges) | Grid y lines (mm, incl. edges) | Storeys | Framing |
|---|---|---|---|---|---|---|
| **T1** | Residential PS timber | R-PS | 0, 3505.2 … 42062.4 (12 x 3505.2) | 0, 4572 … 64008, 67056 (14 x 4572 + 3048) | 12 x 3657.6 | columns + two-way CLT, 140 cols/level |
| **T2** | Residential post+beam timber | R | 0, 7620, 15240, 22860, 30480, 38100, 43891.2 | 0, 4572 … 64008, 67056 | 12 x 3657.6 | girders ∥X, 79 cols / 56 girders / 42 perimeter |
| **T3** | Residential purlin timber | R | 0, 9144, 18288, 27432, 36576, 43891.2 | 0, 9144 … 64008, 67056 (7 x 9144 + 3048) | 12 x 3657.6 | girders ∥Y, purlins ∥X at 3048; 42 / 21 / 27 / 75 |
| **T4** | Office PS timber | O-PS | 0 … 45567.6 (13 x 3505.2, exact) | 0 … 54864 (12 x 4572, exact) | 6 x 4267.2 | 176 cols/level |
| **T5** | Office post+beam timber | O | 0, 9144 … 45720 (5 x 9144) | 0, 6096 … 54864 (9 x 6096) | 6 x 4267.2 | girders ∥X, 58 / 40 / 28 |
| **T6** | Office purlin timber | O | 5 x 9144 | 6 x 9144 | 6 x 4267.2 | girders ∥Y, purlins ∥X at 3048; 40 / 24 / 22 / 85 |
| **T7** | Institutional PS timber | I-PS | 13 x 3505.2 = 45567.6 | 15 x 4572 + 1524 = 70104 | 8 x 4876.8 | 201 cols/level |
| **T8** | Institutional post+beam timber | I | 5 x 9144 | 11 x 6096 + 3048 | 8 x 4876.8 | girders ∥X, 66 / 40 / 41 |
| **T9** | Institutional purlin timber | I | 5 x 9144 | 7 x 9144 + 6096 | 8 x 4876.8 | girders ∥Y, purlins ∥X at 3048; 49 / 24 / 34 / 80 |

**Other distinct topologies, lower priority:**
- **C1 to C3, Concrete Post and beam 9144 x 4572:**
  - R: x 4x9144 + 7315.2; y 14x4572 + 3048
  - O: 5x9144 by 12x4572
  - I: 5x9144 by 15x4572 + 1524
- **C4 to C6, Concrete PS 7620 x 7620:**
  - R-PS: 5x7620 + 3962.4 by 8x7620 + 6096
  - O-PS: 5x7620 + 7467.6 by 7x7620 + 1524
  - I-PS: 5x7620 + 7467.6 by 9x7620 + 1524
- **S1 to S3, Steel Post and beam 9144 x 3657.6:**
  - R: y 18x3657.6 + 1219.2
  - O: y 15x3657.6
  - I: y 19x3657.6 + 609.6
- **Current extras:** full-width Office with the PS grids, 12x3505.2 + 3657.6 and 6x7620.
- **Purlin-on-girder concrete and steel** reuse the T3 / T6 / T9 grids. Only the steel span direction flips.

**Suggested minimal set.** The three footprints R (L), O (rectangle) and I (U), each with its two cores, at the three timber systems (T1 to T9), cover every shape feature Branch has:
- the re-entrant L corner with a core on it,
- a plain rectangle with interior cores,
- a U with a courtyard and cores at both inner corners,
- remainder bays (5791.2, 3048, 1524, 6096),
- an exact-fit panel module (3505.2),
- both girder directions.
