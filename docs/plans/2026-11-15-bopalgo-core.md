# Boolean core on BOPAlgo's structure, 2026-11-15

Decision: the boolean core is rebuilt on OCCT's BOPAlgo structure, natively, with no OCCT dependency. Every vertex,
edge and face carries its own tolerance, and tolerances grow where the data needs it. Faces on one surface are
grouped. Faces and solids are rebuilt from the split pieces. The interval certificates stay as a check that is
recorded on the result; a failed certificate no longer refuses the boolean.

Why: real files are loose (OCCT's edge tolerance is above 1e-5 in 41 of 98 corpus files). The certified pipeline
refuses wherever its 1e-7 proofs fail, and fixing that one failure class at a time has not converged. On the 1850
corpus booleans 474 equal OCCT and 1180 fail; on the 785 timber booleans 229 fail.

## The one number

The share of the 2635 real booleans (1850 corpus, 785 timber) that equal OCCT. Equal means: both valid; face, edge
and vertex counts equal; volume within 1e-6 relative, or within the operands' own tolerance where they are loose.
Counted only where our operands match OCCT's operands (the reader's job); the rest are listed apart.

Every report gives: equal / volume-only / different / fail, and the failure classes ranked by count. The largest
class is fixed first.

## Gates

- Per change, about 10 minutes: the boolean test groups, the 75 primitive rows, the 15 new pairs, and a fixed
  stratified subset of about 150 real booleans (every failure class and every part family represented).
- Once a day: the full suite, fuzz in both modes, all 2635 real booleans and the 70 chair booleans, all against OCCT,
  with pictures of anything that changed.

## Structure (OCCT source: `src/ModelingAlgorithms/TKBO`)

| step | OCCT | ours |
| --- | --- | --- |
| data structure: shapes with tolerance, paves, pave blocks, common blocks, face info, section curves, interferences | BOPDS_DS, BOPDS_PaveBlock, BOPDS_CommonBlock, BOPDS_FaceInfo, BOPDS_Curve | `bop_ds` |
| vertex/vertex, vertex/edge, edge/edge, vertex/face, edge/face, each within the sum of tolerances; same-domain vertices merged; tolerances grown | BOPAlgo_PaveFiller_1..5, _10 (UpdatePaveBlocksWithSDVertices, UpdateEdgeTolerance), IntTools_EdgeEdge, IntTools_EdgeFace | `bop_filler` |
| face/face: section curves with their tolerance and pcurves on both faces; points; same-domain (coincident) faces | BOPAlgo_PaveFiller_6 (PerformFF, MakeBlocks, PostTreatFF), IntTools_FaceFace | `bop_ff` |
| split edges, common blocks, pcurves, degenerated edges | BOPAlgo_PaveFiller_7, _8 | `bop_filler` |
| split faces from their edges in uv | BOPAlgo_BuilderFace, BOPAlgo_WireSplitter | `bop_builder_face` |
| same-domain faces, images of vertices/edges/faces | BOPAlgo_Builder_1..4 (FillSameDomainFaces, FillImages*) | `bop_builder` |
| shells and solids from faces | BOPAlgo_BuilderSolid, BOPAlgo_ShellSplitter | `bop_builder_solid` |
| classification and selection per operation | BOPAlgo_BOP, BOPTools_AlgoTools (ComputeState, IsSplitToReverse) | `bop_builder` |

The existing geometry routes (section, curve/surface and curve/curve intersection, recognised implicit forms,
freeform seeds, ray classification) are reused behind these steps. Where they would throw, they return what they
found with an error estimate, and the step widens the tolerance as OCCT does.

`brep_boolean::apply` switches to the new core once it scores higher on the number above without losing a primitive
row or a chair; the old pipeline stays until then.

## Work packages (parallel, separate files)

1. `bop_ds` and `bop_filler`, then integration of 2 and 3 into `bop::apply`.
2. `bop_ff`: tolerant face/face sections and same-domain faces.
3. `bop_builder_face` and `bop_builder_solid`: split faces and rebuild solids from plain pieces.
4. The scoreboard: the 10-minute subset, the daily full run, the one number per commit.
5. STEP operands equal to OCCT's (running), so that the number measures the booleans.
