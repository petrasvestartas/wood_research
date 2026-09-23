# FAST+EPP Timber Bay Tool v1: four reference variants

All four variants came back from the live ShapeDiver model and are saved as glb files, session `.pb` files and screenshots. From the vertices, the tool does not stack purlins on girders. Every beam frames into the side of its support with its top at the same level. The only thing sitting on top of anything is the panel, which rests on the beam tops and the column tops.

One more thing to know before comparing: the tool swaps A and B so that X is always the shorter side.

## Files
Everything is under `/tmp/claude-1000/-home-petras-code-code-cpp-wood-research/cd17883b-ad50-44cc-bbcd-c4f797944a70/scratchpad/reference/fastepp/`:
- **Session files for our viewer:** `v1_A9_B9_P3.pb`, `v2_A6_B12_P3.pb`, `v3_A9_B6_P0.pb`, `v4_A12_B8_P5.pb`.
  - Each has one Mesh per glTF node, named `Columns`, `Girder`, `Purlin` and `Panels`. Every member is a closed box of 8 vertices and 6 quads, in mm with Z up.
  - A second group, `centre lines`, holds one 2-point polyline per member, named like `Purlin_2 interior purlin`.
  - I loaded all four back with `Session.pb_load` and rendered them in https://petrasvestartas.github.io/session/.
- **Frame-only copies** (no panels, so the beams are visible): `site/pb/v*_frame.pb`, with scene files in `site/scenes/*.yaml`. To view them, run `python3 serve.py 8811 site` in this folder and open `?data=http://127.0.0.1:8811/&scene=<variant>`. My server stops when this run ends.
- **Merged glTF 2.0:** `v*.glb`, one node per member. The root node converts mm to m and Z-up to Y-up.
- **Raw ShapeDiver outputs:** `v*/<Output>_<id>_0.glb`.
  - The model has no "Download 3D Model" export any more; the session lists no exports. So these are the files the viewer itself loads.
  - They arrive gzipped. Inside is glTF 1.0 (KHR_binary_glTF) with one merged mesh per output, plus a ShapeDiver `sdgTF` chunk at the end that holds the edge and dimension polylines.
  - Each folder also has `response.json`, `data.json` (text outputs), `parameters.json` and `members.json` (every member: centre line, bounding box, section, elevations).
- **Screenshots:** in `shots/`.
  - ShapeDiver viewer: `v*_shapediver_iso.png` and `v*_shapediver_top.png`, with the tool's output text overlaid.
  - Our viewer: `v*_session_viewer.png` and `v*_frame_session_viewer.png`.
- **Scripts:** `run_variants.py`, `glb_read.py`, `convert.py`, `sd_shot.cjs`, `sd_viewer.html`, `viewer_shot.cjs`.

## Parameters
Only A, B and the purlin count changed. Everything else stayed at its default:
- PANEL TYPE = CLT
- Loading = Residential
- Fire = 0
- Purlin Width = 215
- Girder Width = 265
- Building Storeys = 6
- Dimensions = true

## Layout rules read from the vertices
X is the short side, Y the long side (Xs = min(A,B), Ys = max(A,B)). Columns sit on the four corners (0,0), (Xs,0), (Xs,Ys) and (0,Ys).

| Member | Count | Centre line | Length (face to face) | Elevation |
|---|---|---|---|---|
| Column | 4 | vertical at each corner | 4500, one storey only | z −4500..0 |
| Girder | 2 | y=0 and y=Ys, runs along X | column face to column face: x from colX/2 to Xs−colX/2 | top at z=0 |
| Edge purlin (on a column line) | 2 | x=0 and x=Xs, runs along Y | column face to column face: y from colY/2 to Ys−colY/2 | top at z=0 |
| Interior purlin | N | x = k·Xs/(N+1), runs along Y | girder face to girder face: y from 132.5 to Ys−132.5 | top at z=0, hangs from the girders |
| Panel strip | 3 or 4 | runs along X, strips side by side in Y | x from −colX/2 to Xs+colX/2, one piece over every purlin | z 0..t |

- **Panels:** the strips cover the full outer column footprint, from −colY/2 to Ys+colY/2 in Y, in equal widths of 3095–3127 mm. Their joints do not line up with any member.
- **CLT layers** (from the layer lines): 87 mm is 35/17/35 and 243 mm is nine layers of 35/17. The strong direction runs along X, across the purlins.
- **Structural depth** = panel thickness + max(girder depth, purlin depth). This matches the reported value in all four variants.
- **Stacking:** column tops, girder tops and purlin tops all sit at z=0, and the panel lies on them. No beam sits on another beam.

## Members per variant (mm; sections are width × depth)
**v1: A=9, B=9, N=3 (Xs=9000, Ys=9000)**
- **Tool reports:** panel 87V CLT (3PLY), purlin 215w×456h, girder 265w×608h, column 342w×315h, depth 695, column spacing 9000mm x 9000mm.
- **Columns:** 315 in X × 342 in Y.
- **Girders:** at y=0 and y=9000, x 157.5→8842.5 (8685 long), 265×608, z −608..0.
- **Edge purlins:** at x=0 and x=9000, y 171→8829 (8658 long), 215×456.
- **Interior purlins:** at x=2250, 4500 and 6750, y 132.5→8867.5 (8735 long), 215×456, z −456..0.
- **Panels:** 3 strips, x −157.5→9157.5 (9315 long), y bands [−171, 2943], [2943, 6057], [6057, 9171], 87 thick.

**v2: A=6, B=12, N=3 (Xs=6000, Ys=12000)**
- **Tool reports:** panel 87V CLT, purlin 215×532, girder 265×532, column 380w×265h, depth 619, column spacing 12000mm x 6000mm.
- **Columns:** 265 in X × 380 in Y.
- **Girders:** x 132.5→5867.5 (5735 long), 265×532.
- **Edge purlins:** y 190→11810 (11620 long), 215×532.
- **Interior purlins:** at x=1500, 3000 and 4500, y 132.5→11867.5 (11735 long), 215×532.
- **Panels:** 4 strips, x −132.5→6132.5, bands of 3095 starting at y=−190, 87 thick.

**v3: A=9, B=6, N=0 (Xs=6000, Ys=9000)**
- **Tool reports:** panel 243V CLT (9PLY), purlin "No Purlin", girder 265w×836h, column 380w×265h, depth 1079, column spacing 9000mm x 6000mm.
- **Columns:** 265 in X × 380 in Y.
- **Girders:** none; the Girder output is empty.
- **Beams on the column lines:** 2, in the Purlin output, at x=0 and x=6000, y 190→8810 (8620 long), drawn 215×836.
- **No beam** on the short gridlines y=0 and y=9000.
- **Panels:** 3 strips, x −132.5→6132.5, each a single span of 6000, bands of 3126.67, 243 thick.

**v4: A=12, B=8, N=5 (Xs=8000, Ys=12000)**
- **Tool reports:** panel 87V CLT, purlin 215×494, girder 265×684, column 418w×365h, depth 771, column spacing 12000mm x 8000mm.
- **Columns:** 365 in X × 418 in Y.
- **Girders:** x 182.5→7817.5 (7635 long), 265×684.
- **Edge purlins:** y 209→11791 (11582 long), 215×494.
- **Interior purlins:** at x=1333.33, 2666.67, 4000, 5333.33 and 6666.67, y 132.5→11867.5, 215×494.
- **Panels:** 4 strips, x −182.5→8182.5, bands of 3104.5 starting at y=−209, 87 thick.

**Volumes the tool reports** (glulam / panel / total, m³/m²):

| Variant | Glulam | Panel | Total |
|---|---|---|---|
| v1 | 0.075 | 0.087 | 0.162 |
| v2 | 0.105 | 0.087 | 0.192 |
| v3 | 0.043 | 0.243 | 0.286 |
| v4 | 0.113 | 0.087 | 0.2 |

## Things that look wrong or surprising in the reference
1. **A and B are swapped silently.** X is always the shorter side, and "Column Spacing" is written long × short (A=6, B=12 gives "12000mm x 6000mm").
2. **With 0 purlins the beam width is wrong.** "Girder Size" says 265w, but the drawn beams are 215 wide (the purlin width) and sit in the Purlin layer. The short gridlines get no beam at all.
3. **The column labels are misleading.** In "342w x 315h", "w" is the Y size (a multiple of the 38 mm lamination: 342, 380, 418). "h" is the X size, taken from the width list.
4. **Edge purlins are not sized separately.** They use the interior purlin section even though they carry half the load. In v2 the girder is forced down to the purlin depth (532 = 532).
5. **Panels reach past the grid.** They extend half a column beyond each gridline, to the outer column faces. Strip joints follow an equal split, not the members.
6. **Only one storey is drawn** (z −4500..0, fixed height). The storey count only changes the column size. Columns stop at the beam tops and the panel runs over them.
7. **Small formatting slips.**
   - Purlin positions are float32, so 1333.33 is stored as 1333.3334.
   - v4 reports "16100.0kg*" where the other variants have whole numbers.
8. **Don't use "Glulam Volume" as a check.** I could not reproduce it from the drawn members: the simple rules I tried for sharing edge members between bays came out 2–8% off. The panel volume is exactly the panel thickness per m².
9. **Screenshot quirks.**
   - The ShapeDiver viewer draws a blank canvas with the Vulkan ANGLE flags. I took its screenshots with `--use-angle=gl`; our viewer's screenshots used the flags you gave.
   - The dimension text labels do not appear in the ShapeDiver screenshots, only the dimension lines.