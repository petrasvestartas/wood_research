# Branch3D Concept Lite reference: four captured cases (a–d)

All four cases are captured. For (a)–(c), my independent re-derivation of the generator rules matches the live app exactly: every member, every end point and every tributary width.

Base directory: `/tmp/claude-1000/-home-petras-code-code-cpp-wood-research/cd17883b-ad50-44cc-bbcd-c4f797944a70/scratchpad/reference/branch3d/` (written `$R` below).

## 1. What was captured

| Case | JSON (mm, Z up) | Screenshots in |
|---|---|---|
| (a) Beam, spanDirection X | `$R/a_beam_x.json` | `$R/a_beam_x/` |
| (b) Purlin, spanDirection Y, 10 ft purlin spacing | `$R/b_purlin_y.json` | `$R/b_purlin_y/` |
| (c) Plate (point supported), X | `$R/c_plate_x.json` | `$R/c_plate_x/` |
| (d) Residential L preset, Purlin, 1 auto-placed core | `$R/d_residential_l_purlin.json` | `$R/d_residential_l_purlin/` |

**Screenshots in every case folder** (1400×900):
- **3/4 views:**
  - `iso.png` uses the app's own default camera: position (−maxX, −maxY, 2·storeys·h), aimed at the bounding-box centre at half height.
  - `iso_framing_no_slab.png` is the same view with the slabs hidden.
- **Plan views:** `plan.png`, `plan_framing_no_slab.png` and `plan_single_story_mode.png`. The plans use a 3° field of view, so they are close to orthographic.
- **Detail views:**
  - `closeup*.png`
  - `junction_from_below.png`: looking up at the underside of the first floor.
  - `elevation_south*.png`
- **UI panels:** `ui_default.png`, `ui_summary.png`, and `ui_quantities.png` (the Quantities table).
- **Case (d) only:** `plan_core_zoom_single_story_no_slab[_no_core].png`.
- The "no_slab" and "no_core" images hide those meshes through the three.js scene; that is my change, not an app feature. Single-story mode is the app's own toggle.

**Each JSON holds:**
- `parameters_full_ft`: the exact injected state.
- `applied_controls_check`: what the app actually ran, plus the WebGL renderer.
- `counts_per_level`.
- `levels[]`: columns, beams (`kind` girder or perimeter_beam), purlins, floor_plate, panel_lines, span_information and footings. Every member carries its end points, top and bottom z, section, `tributary_width_mm` and supports.
- `cores_mm`, `grade_slab`.
- `statistics_raw` and `efficiency_raw` (in ft).
- The text of the Quantities and Summary panels.
- A summary of the instanced meshes in the scene.
- `<case>/raw_model_ft.json`: the unconverted model.

**Tooling:**
- `$R/patch_bundle.js` builds `index.patched.js`, a local copy of the bundle that exposes the store, `pMe`, and the live model and camera controls.
- `$R/capture.js` is the Playwright driver.
- `$R/derive_abc.py` is the hand re-derivation, used as the cross-check.
- `$R/parameters_full.json` holds all four parameter sets.

**How the settings were loaded:**
- Each case opened at `?scheme=ref_<case>`.
- `page.route` answered `GET https://link-shortener.pmeschke.workers.dev/<id>` with `{"data": btoa(JSON.stringify({parameters}))}`. That is the format `WOe` → `vOe` → `UW` expects (pretty.js L145043–145090, bootstrap `zDe` L154073).
- Amplitude-proxy, Sentry and Mapbox requests were blocked.

**Two capture problems I had to fix:**
- **WebGL.** With the Chrome flags you specified, a WebGL2 context with `powerPreference:"high-performance"` fails to create, and the app crashes. An init script strips that attribute; the renderer is then ANGLE Vulkan on the RTX 4080.
- **Stray input.** In one run `structuralSystem` flipped to Purlin partway through, probably from stray input on the shared `DISPLAY=:0`. The script now compares the live controls with the injected ones at extraction time and retries on a mismatch. All final JSONs passed that check.

## 2. Exact parameters (Branch stores feet; mm = ×304.8)

**(a)–(c):**
- Units Metric, 2 storeys at 12 ft (3657.6 mm), no substories.
- Footprint `[[0,0],[60,0],[60,60],[0,60]]` ft (18288 mm square).
- `xIncrements` = `yIncrements` = [0,15,30,45,60] ft.
- `maxPurlinSpacing` 10 ft (3048), `maxPanelLength` 60 ft.
- `cores:"0"`.
- Glulam columns, girders and purlins; Timber floor, CLT from Kalesnikoff.
- 2 in (50.8 mm) concrete topping, 120 min fire rating, SDL/LL 15/65 psf.
- I forced `columnProfile:"Square"`: the zod default is "Rectangular", but Square is the only glulam option the UI allows.
- System and span per case: (a) Beam/X, (b) Purlin/Y, (c) Plate/X.

**(d):** the app's own wizard mapping `Uwe("Residential","Purlin on girder","Mass Timber")`:
- 12 storeys at 12 ft.
- Polygon `[0,0],[72,0],[72,150],[144,150],[144,220],[0,220]` ft.
- Spacing 30×30 ft, giving `xIncrements` [30,60,90,120] and `yIncrements` [30…210].
- Purlin system, spanDirection Y, purlin spacing 10 ft.
- `cores:"1"` with `coreData=[S_e(polyline,[])]` = `{position:[24.5,63.5], width:23, depth:23}` ft. The preset's own two cores were replaced by this auto-placed one.
- The generator also adds the bounding-box lines. The lines it actually uses are X = 0, 30, 60, 90, 120, 144 and Y = 0, 30, …, 210, 220.

## 3. Reference member layout (mm, per storey i)

**Common to all cases:**
- The level datum is D_i = 3657.6·(i+1).
- Columns run from D_{i−1} (0 for the ground storey) up to D_i, centred on their point.
- Beam and purlin boxes hang below their stored z: top = stored z − 3.05 mm (a 0.01 ft render offset), bottom = top − depth.
- The deck occupies [D_i, D_i + thickness]. The 50.8 mm topping sits on the deck but is only drawn while highlighted.
- Footings are 1219.2 mm pads, 304.8 mm deep, at z = 0 under the ground-storey columns ((d): 2743.2 × 685.8). The grade slab is 152.4 mm.

### (a) Beam, X
- **Columns:** 25, one at every crossing of {0, 4572, 9144, 13716, 18288}²; 16 boundary, 9 interior.
  - Ground storey: 280² on the perimeter, 300² interior.
  - Upper storey: all 280².
- **Perimeter beams:** 16, split at every grid crossing.
  - Sides y = 0 and y = 18288: 220×440, trib 2286.
  - Sides x = 0 and x = 18288: 220×280, trib 0.
- **Girders:** 12, along y = 4572, 9144 and 13716, each split at x = 4572, 9144, 13716. Sections 220×520, trib 4572; both ends sit on columns.
- **Interior x-lines carry no beam.** The deck spans in Y between the girders.
- **Stacking:** all beam tops are at D_i − 3; girder bottoms are at D_i − 523.
- **Deck:** CLT 189.8 mm, laid in 3505.2 mm (11.5 ft) strips running in Y, with joints at x = 3, 3508.2, 7013.4, 10518.6, 14023.8 and 17529. That gives 6 panels per storey.
- **Quantities table:** Girder 56 pieces (28 × 2 storeys, perimeter beams included), Column 50, Deck 12.

### (b) Purlin, Y
- **Columns:** the same 25 points. Ground storey: 10 × 280², 15 × 300².
- **Perimeter beams:** 16.
  - Sides x = 0 and x = 18288: 220×440, trib 2286.
  - Sides y = 0 and y = 18288: 220×400, trib 1524, i.e. p/2.
- **Girders:** 12, along x = 4572, 9144 and 13716, split at every y-line. Sections 220×520, trib 4572.
  - They are dropped: top at D_i − 206.3, bottom at D_i − 726.3.
- **Purlins:** 28, in 4 x-bays × 7 rows. Each runs in X from girder line to girder line.
  - Rows at y = 2286, 4572, 6858, 9144, 11430, 13716, 16002.
  - Sections 220×400, trib 2286; top at D_i − 3, bottom at D_i − 403.
  - The rows at 4572, 9144 and 13716 lie on the column lines: those lines carry a purlin, not a girder.
  - There is no row at y = 0 (the perimeter beam takes it) and none at y = 18288.
- **Deck:** the same CLT strips as (a).
- **Quantities table:** Girder 56, Purlin 56, Column 50, Deck 12.

### (c) Plate
- **Columns:** 25, sized as in (b).
- **No beams and no purlins.** The generator builds the beams, then deletes them.
- **Deck:** two-way CLT 365.1 mm, an extrapolated 9-ply section, which triggers the warning "Some elements require custom sizes". The X gridlines are flagged orange because a 15 ft bay is wider than the 11.5 ft panel width.
- **Panel joints:** the same strips as (a). They do not land on the column lines.

### (d) L-shape, Purlin, 12 storeys
- **Footprint:** (0,0), (21945.6,0), (21945.6,45720), (43891.2,45720), (43891.2,67056), (0,67056).
- **Core:** a 7010.4 mm square with its min corner at (7467.6, 19354.8). It is a hole in every floor.
- **Columns:** 45, on x-lines 0/9144/18288 (9 each), 21945.6 (6) and 27432/36576/43891.2 (4 each). Sizes run from 280² to 560².
- **Girders:** 23, running in Y. Tops at D_i − 206.3, bottoms at D_i − 1006.3.
  - x = 9144: 9 segments. The segment crossing the core is split into two 1066.8 mm stubs (18288–19354.8 and 26365.2–27432), sized 220×240 and supported on the core.
  - x = 18288: 8 segments.
  - x = 27432 and x = 36576: 3 segments each (45720 → 54864 → 64008 → 67056).
  - Sections: 320×800 for the 9144 spans; 220×480 or 220×440 for the 3048 end bay.
  - Trib 9144, except 8229.6 on x = 36576.
- **Perimeter beams:** 27, from 220×320 up to 300×720. Trib by side:
  - x = 0 side: 4572
  - x = 21945.6 side: 1828.8
  - x = 43891.2 side: 3657.6
  - all sides that run in X: 1524
- **Purlins:** 75, in rows every 3048, each with trib 3048:
  - Bays x 0–9144 and 9144–18288: 21 rows each, y = 3048 … 64008.
  - Stem remnant bay 18288–21945.6: 15 rows, y = 3048 … 45720.
  - Each of the three wing bays: 6 rows, y = 48768 … 64008.
  - Sections: 260×640 in 9144 bays, 220×360 in the 3658 bay, 240×600 in the 7315 bay. Top at D_i − 3.
- **Deck:** CLT 189.8 mm, strips from x = 0 every 3505.2 mm. Panel breaks at y = 18288, 36576 and 54864; about 40 panels per storey.

## 4. Cross-check

`derive_abc.py` re-implements the rules of the three generator functions (`aMe`, `uMe`, `fMe`) for a rectangular footprint:
- a column at every crossing, flagged boundary on the perimeter;
- the perimeter tributary rule, with the |cos| factor for Beam and p/2 + (Z − p/2)·|cos| for Purlin;
- girders on the interior lines of one family;
- `ceil(bay/p)` purlins per bay, with the first one on the gridline and perimeter rows dropped;
- Plate deletes all beams.

It matches the app for all three cases:
- **(a):** 25 columns, 16 perimeter beams, 12 girders, 0 purlins.
- **(b):** 25 columns, 16 perimeter beams, 12 girders, 28 purlins.
- **(c):** 25 columns, nothing else.

In all three, the column sets are identical including boundary flags, and member geometry and tributary widths are identical too. I did not script a re-derivation for (d); I checked its layout by reading the output against the rules.

## 5. What looks odd in the reference itself

1. **Purlins are not cut at cores.** In (d), the rows at y = 21336 and 24384 run straight through the core void (x 7467.6–14478) in both bays; the girders are split there, the purlins are not. See `plan_core_zoom_single_story_no_slab_no_core.png`.
2. **Girders and purlins are neither stacked nor flush.**
   - The girder drop is capped at 203.2 mm (8 in), whatever the purlin depth. Purlins therefore cut into the girders by 197 mm in (b) and 437 mm in (d).
   - Perimeter beams are never dropped, so a girder meets the perimeter beam 203 mm lower.
   - The statistics still add girder + purlin + deck + topping as if stacked. The reported "minimum clear height" (2.5 m in (b), 1.98 m in (d)) therefore does not match the geometry.
3. **Columns overlap other members.** Each storey's column starts at the datum below, so it passes through that floor's 240.6 mm of deck and topping. Beam, column and deck boxes overlap at every node, with no trimming.
4. **Girder tributary width uses neighbouring grid lines even where the footprint stops.** In (d), the x = 18288 girder gets trib 9144 through the 21945.6 mm-wide stem, where the true value is about 6401.
5. **Panel strips start at x = 0 and ignore the column grid.**
   - (a)–(c) end with a 759 mm sliver strip.
   - In Plate, the joints do not sit on the column lines.
   - The Plate case with 15 ft bays produces an extrapolated 365 mm, 9-ply deck. The wizard defaults to 11.5×15 ft bays for exactly this reason.
6. **Minor issues:**
   - In (d), the core leaves 1067 mm girder stubs.
   - Purlins are sized with 1.6D + 1.2L, while beams use 1.2D + 1.6L (L123000).
   - Some column sizes are off the 20 mm step (459×459 in (d)).
   - The Quantities table counts perimeter beams as "Girder" pieces.