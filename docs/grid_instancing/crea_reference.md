# crea reference: compas_grid oracle for `from_lines`

## Summary

- **Converted:** all four crea datasets now exist as plain grid JSON with `{lines, floors, walls, cores}`.
- **Rendered:** the raw input is saved as session `.pb` files and rendered in the local viewer.
- **Oracle:** the member counts per level come from running compas_grid's own `CellNetwork.from_lines_and_surfaces` code on compas 2.15.1, not from reading it.
- **Visual reference:** the compas member layout (boxes, heads and beam end cuts) is also rendered, beside the input, so you can check what our grid builds by eye.
- **Oddities:** the reference data has several of its own, listed in section 5. The biggest are beams with no column under them, beams at z = 0, and walls that compas_grid ignores.

## 1. Files

All paths are under `/tmp/claude-1000/-home-petras-code-code-cpp-wood-research/cd17883b-ad50-44cc-bbcd-c4f797944a70/scratchpad/reference/crea/`.

**Simple grid JSON** (in mm, raw coordinates, face loops in cycle order):
- `crea_4x4.json`: 36 lines, 6 floors, 8 walls, 4 cores
- `crea_4x4_ground.json`: 36 lines, 9 floors, 8 walls, 4 cores
- `crea_4x4_beams_without_column.json`: 37 lines, 11 floors, 8 walls, 4 cores
- `crea.json`: 889 lines (Column and Beam layers joined), 248 floors, 176 walls, 80 cores
- The vertex-order swap:
  - `convert.py` checks every quad and swaps vertices 2 and 3 if the quad crosses itself.
  - None needed it: all 504+ quads in the committed files already have the swap applied, so vertex order and face order are the same cycle.
  - Every floor winds counter-clockwise seen from above (normal +Z).

**Oracle data:**
- `oracle_compas.json`: counts produced by compas_grid's code, with tolerance = 3.
- `<name>_compas_members.json`: every member with its axis, z range, head arms and corners, and which beam ends are cut by a head.
- `analyse.txt`: my own independent read of the layout. Its counts match the oracle exactly.

**Session files** in `pb/`, also copied into `shots/viewer/pb/`:
- `crea_{4x4,4x4_ground,4x4_beams_without_column,full}_input.pb`: lines as polylines, surfaces as meshes, one group per layer.
  - Colours: Segments black, Column blue, Beam red, Floor sand, Facade light blue, Core red.
- `..._compas.pb`: the compas member layout.
- `crea_4x4_node_detail.pb`: a close-up of node (6000, 30000, 3800).
- `crea_full_input_nofacade.pb`: the full building without facades, so the core and voids show.

**Scenes** in `shots/viewer/scenes/`:
- `crea_*_input`, `crea_*_compas`, `crea_*_pair` (input beside the members, offset 20000 mm, or 40000 mm for the full building)
- `crea_4x4_node_detail`, `crea_full_input_nofacade`

**Screenshots** in `png/`: 24 files, all checked by eye.
- The most useful are `crea_4x4_pair_iso_f.png`, `crea_4x4_beams_without_column_pair_iso_f.png`, `crea_4x4_ground_pair_iso_f.png`, `crea_4x4_node_detail_front_f.png`, `crea_4x4_compas_front_f.png`, `crea_full_compas_iso_f.png` and `crea_full_input_nofacade_top_f.png`.
- `shot_views.cjs` is a copy of `shot.cjs` that also presses the view keys (7 iso, 5 top, 1 front, 3 left, then f to fit).
- The server on port 57261 stops when I return. To re-serve: `python3 shots/serve.py <port> shots/viewer`, then open `?data=off&scene=<scene>`.

## 2. Parameters

These are the compas_grid example values (`003_gridmodel_add_interfaces.py`):
- **Tolerance:** 3 decimals, used as the node key.
- **Horizontal test:** a line counts as horizontal when its end heights differ by less than 1/3 mm.
- **Column:** 300×300.
- **Beam:** 300×300, extend 0.
- **Head:** w = h = 150, o = 210, L = 300.
- **Plate:** a 5700×5700 square (±2850) centred on the bay, 200 thick, offset 100.

## 3. The oracle: what compas_grid builds

The rules:
- A column is built for each non-horizontal edge.
- A head is built at the top end of each column, including the roof. There is never a head at z = 0.
- A beam is built for each horizontal edge. Every floor edge becomes a beam too, even if nobody drew that line.
- A plate is built for each floor face.
- Walls are never built.

| Dataset | Columns | Heads | Beams | Plates |
|---|---|---|---|---|
| crea_4x4 | 16 (8 per storey: 0-3800 and 3800-7600) | 16 (8 at z 3800, 8 at z 7600) | 20 (10 at 3800, 10 at 7600) | 6 (3 at 3800, 3 at 7600) |
| crea_4x4_ground | 16 | 16 | 30 (10 at z 0, all from floor edges; 10 at 3800; 10 at 7600) | 9 (3 at each of 0, 3800, 7600) |
| crea_4x4_beams_without_column | 17 (9 in 0-3800, 8 in 3800-7600) | 17 (9 at 3800, 8 at 7600) | 34 (10 at 0, 12 at 3800, 12 at 7600) | 11 (3 at 0, 4 at 3800, 4 at 7600) |
| crea (full) | 340 (34 per storey × 10) | 340 (34 at each level from 3800 to 38000) | 633 (54 at 0, 57 at 3800, 58 at each level from 7600 to 38000) | 248 (20 at 0, 22 at 3800, 23 at each level from 7600 to 34200, 22 at 38000) |

- Every beam is 6000 long and every column is 3800 long.
- In the full building, 94 beams exist only because of floor edges, and 10 drawn lines are duplicates.

**crea_4x4 layout in numbers:**
- **Grid axes:** x {0, 6000, 12000}, y {24000, 30000, 36000}, z {0, 3800, 7600}.
- **Columns** (the same 8 positions in both storeys): (0, 24000), (0, 30000), (0, 36000), (6000, 24000), (6000, 30000), (6000, 36000), (12000, 30000), (12000, 36000). There is no column at (12000, 24000).
- **Beams**, the same at z 3800 and 7600:
  - x = 0: from y 24000 to 30000, and from 30000 to 36000
  - x = 6000: from y 24000 to 30000, and from 30000 to 36000
  - x = 12000: from y 30000 to 36000
  - y = 24000: from x 0 to 6000
  - y = 30000: from x 0 to 6000, and from 6000 to 12000
  - y = 36000: from x 0 to 6000, and from 6000 to 12000
- **Floor bays:** [0-6000]×[24000-30000], [0-6000]×[30000-36000] and [6000-12000]×[30000-36000]. Together they make the L shape.
- **Heads:**
  - The re-entrant corner (6000, 30000) has arms on all four sides (E, N, S, W) and 3 floor corners.
  - (0, 30000) and (6000, 36000) have 3 arms and 2 corners.
  - The outer corners have 2 arms and 1 corner.
- **Walls:**
  - Facade on x = 0 (y 24000-36000) and on y = 36000 (x 0-12000).
  - Core on x = 6000 (y 24000-30000) and on y = 30000 (x 6000-12000).
  - Each wall is one 6000×3800 quad per bay per storey, in the plane of the grid line.

**Vertical stacking at a node at height z.** I derived this from compas_grid's transforms and modifiers by hand, then confirmed it in `node_detail_front`:
- The column below ends at z. It is not cut.
- The head sits on z to z+300. It is widest at the bottom, where each arm reaches out 360 (w+o) from the node, and narrows to a 300×300 square on top.
- Beams sit on z to z+300, with their underside on the line. Where a beam meets a head, its bottom edge stops 360 from the node and its top edge 150, so it rests on the sloped face of the head's arm. Beams at z = 0 are not cut.
- Plates sit on z+300 to z+500, on top of the beams. They stay 150 back from each grid line, which leaves a 300 slot.
- The column above starts at z+300 (the head's top face trims it) and passes up through that slot.
- **The lines mark the underside of the beams, not their centre lines.**

## 4. How the datasets relate

- **crea_4x4** is the full building cropped to x 0-12000, y 24000-36000, z up to 7600, with the 3 ground floors and the 2 floors in the core quarter removed.
- **crea_4x4_ground** puts the 3 ground floors back.
- **crea_4x4_beams_without_column** matches the crop exactly, and adds a ground column at (12000, 24000). That column does not exist in `crea.json`.
- **The full building:**
  - Grid: x 0-24000 in steps of 6000, y 0-36000 in steps of 6000, z 0-38000 in steps of 3800.
  - The core is 12000×12000 at x 6000-18000, y 18000-30000. It has 80 wall quads and is complete.
  - The core centre (12000, 24000) has no column in any storey.

## 5. Oddities in the reference itself

1. **Beams with no column under them.**
   - In the full building, the floors from 3800 up cover the core. Their edges create 4 beams per level that meet at the core centre, where there is no column and no head: 40 beams with one unsupported end.
   - `beams_without_column` has the same problem at 7600: 2 beams end at (12000, 24000), which has a column only in the ground storey.
   - In the same file, the core walls on x = 6000 and y = 30000 now sit under a floor bay.
2. **Beams at z = 0.**
   - Ground floors create beams on the ground: 54 in the full building, 10 in `ground`.
   - With no head there, these beams overlap the bottoms of the ground columns and each other at every node.
3. **Duplicate beam lines.** 10 in the full building: x = 12000, y 0-6000, at every level from 3800 to 38000, each drawn twice in opposite directions. compas's Graph keeps both directions, and CellNetwork then merges them. Our `from_lines` has to merge lines regardless of direction.
4. **Stray roof beam.** The beam (12000, 6000)-(12000, 12000) at z = 38000 is drawn between two empty roof bays, so it has no floor on either side. compas still builds it.
5. **Openings move from level to level.** In the region x 6000-18000, y 6000-18000, 1 or 2 floor bays are missing at every level from 3800 up, in a different spot each level, like a stair opening. The beams around each opening are still drawn.
6. **Facade gaps and inconsistent winding.**
   - 24 of the 200 facade panels are missing. They come in pairs, like loggias.
   - Facade normals do not consistently point outward. Both x = 0 and x = 24000 point +x, and both y = 0 and y = 36000 point -y, so the winding cannot tell inside from outside.
   - Core walls are consistent: they all face into the core.
7. **Floating-point noise.** Coordinates are off by up to 1.5e-11 mm (for example 5999.999999999999 or 30000.000000000015). Exact equality tests would fail on these.
8. **compas_grid ignores walls.** The Facade and Core layers are never used. All 12 wall quads in the 4x4 files, and 256 in the full building, have no oracle member.