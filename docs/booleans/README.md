# Native BRep booleans: state and what is left

State on 2026-11-27, session_cpp at `07827941`, all in petrasvestartas/wood_research#2. The goal is OCCT's results
and speed on real parts, with no OCCT in the kernel (OCCT and SMLib are references and oracles only).

## Where it stands

Measured against OCCT by `docs/validation/score` (equal by counts: valid closed solid, same face/edge/vertex counts,
volume within the operands' and the solids' own leak; by geometry: also vertices, edges and face areas; draws: every
face meshes with its true area).

| set | equal by counts | by geometry | draws | not equal |
| --- | --- | --- | --- | --- |
| key, 30 | 28 | 28 | 29 | 2 counts only |
| subset, 145 | 134 (92 %) | 131 | 138 | 9 counts only, 2 fail; 5 apart where OCCT is wrong |
| full, 2494 counted | 2123 (85 %) | sampled: 515 of 520 | sampled | 171 counts only, 59 different, 141 fail; 211 apart |
| chairs, 70 | 70 | 70 | 70 | 0 |

Old pipeline on the subset: 51 of 145. Full run: `docs/validation/score/full_run/` (summary, judged.tsv,
different.txt, speed/).

Speed per boolean, ours / OCCT (load about 1, best of 3):

| set | ours | OCCT | median ratio |
| --- | --- | --- | --- |
| 75 primitive rows | 3.1 s | 5.4 s | 0.78 |
| 70 chairs | 24.6 s | 74.2 s | 0.72 |
| subset, 144 | 131.5 s | 96.4 s | 3.06 (worst 102, joint30_rot ∩; cylinder600bore ∪ 17 s, ×13) |

## Done

- Analytic types (`Surface`, `Curve`, `Curve2d`: plane, cylinder, cone, sphere, torus, revolution, extrusion; line,
  circle, ellipse, parabola, hyperbola) in true parameters, periodic; edges and pcurves as ranges on shared curves.
- STEP reader and writer keep the file's analytic entities and placements; degenerated edges only at poles and apexes;
  edge tolerances raised to the measured gap to their pcurves, as OCCT's reader.
- Boolean core `bop` on OCCT's BOPAlgo logic, running on analytic data natively; closed-form intersections for
  analytic pairs; never refuses.
- `brep_check`: one validity check with named statuses on every result.
- Volume with closed loops, a radial field and a closure error; mesher in stretched parameters; every face draws or
  raises a named error.
- Scoreboard in three tiers with geometry comparison, SMLib as second oracle, pictures through session_viewer.

## Left to do

### Wrong results and failures (first)

1. Full run: 59 "different" and 141 failures (101 not closed, 25 timeouts, 15 tolerance). Rank by cause as was done for
   the subset; the list is `full_run/different.txt`. Known: `elem16_self` all five ops (ours returns pieces where A∩B = A);
   `KnurledKnob10` and `defaultamacchina` ∩ empty where OCCT has a result; volume off by ×0.05–2.8 on
   `00275424_fillet_17#rot30x`, `sample_round#rot30x`, `revit#rot30x`, `bottle#box`, `Pump_TopCover#rot30x`.
2. Found and not fixed: the union of a box and a cylinder tangent along its edge leaves malformed faces; an edge grazing
   a face within tolerance gets two vertices where OCCT makes one; `ee_point` misses the edge/edge vertex in
   `elem08_self`.
3. Subset: `revit#rot5z` b-a not closed (DS equal to OCCT's but for vertex placement); `threaded_rod_cutter#rot5z` ∪
   fails at edge/face on a helicoid (OCCT wrong too); `flange#rot30x` ∪ (cones with apexes 2.6e-8 apart: boundary
   blocks split after FF); `joint33` a-b (OCCT keeps BE24 as an internal edge).
4. Robustness sweep on random primitive placements (touching, tangent, coincident), every result through `brep_check`
   and union = ∩ + a−b + b−a.

A partial patch for items 2–4 (unreviewed, interrupted by the usage limit) is in the scratch worktree `wt_sd`
(340 lines); scratch does not survive the container, so redo rather than rely on it.

### Speed

5. Real parts are 3× slower than OCCT in the median (primitives and chairs are faster). Profile the 10 slowest
   (`full_run/speed/both.tsv`): cylinder600bore ∪ 17 s, elem11_self ⊕ 10.5 s, fillet_11 a-b 6.9 s, screw ⊕ 4.7 s,
   joint30_rot ∩ ×102. The core still calls `nurbs()` for the point classifier, numeric edge/edge and edge/face, and
   walked sections; item 7 removes most of that.

### Convention differences (last; the solids are right)

6. 171 "counts only" results: OCCT's vertices where a walked section starts (IntPatch start search), at a surface's
   angle origin in specific cases, the IntAna cone/cone split, reader edges OCCT adds to close uv gaps on freeform
   faces (chamfer_12, chamfer_16, screw_driver1, Bottom), 4 unused edges left in `m_edges` by the reader's splits.

### Kernel (plan: `docs/plans/2026-11-26-kernel-improvements.md`)

7. Native interface on `Surface` / `Curve` so no consumer converts to NURBS: point classification, numeric
   intersections in `bop`, `volume_exact`, the mesher. `as_nurbs()` only for export and the old pipeline.
8. Healing at read as one step (ShapeFix): edges and pcurves agree, missing seams, orientation, faces on one surface
   share one pool entry.
9. Per-face queries; history on results (operand face/edge each result entity came from).
10. Remove the old pipeline (`brep_boolean`, `brep_section`, `split`, `brep_assemble`, `brep_classify`) once `bop`
    passes it everywhere: it does on the subset and the chairs; check the full tier and the 75 rows.
11. Tests that expect inside-out solids or pcurves far off their edges (about 25, listed in the `brep_check` merge):
    review and correct them instead of skipping statuses in `is_valid` / `is_solid`.
12. Protobuf for the new types and ranges (design in the b4 notes: `Curve`, `Surface` messages, typed pools, ranges).
13. Python and Rust ports of the types, BRep ranges, `brep_check`, `update_tolerances`.

### Before merging the PR

14. CI green on Linux, macOS and Windows for the last commits (not checked since `b5d709e8`).
15. `pushmono` / bump the `session` pointer only after the session_cpp branch is reviewed.

## How to measure

```bash
bash docs/validation/score/score.sh session/session_cpp/build <out> key|subset|full bop --jobs 2 --timeout 40
```

Pictures: `python3 docs/validation/score/viewer_pics.py <run> --cases <file> --ops <tier.tsv> --out <dir>` (session
viewer, needs its build; `pics.py` with the same arguments is the three.js fallback).
