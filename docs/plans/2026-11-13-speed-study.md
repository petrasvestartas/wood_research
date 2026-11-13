# Why the native boolean kernel is slower than OCCT, and the design that closes it

Study of 2026-11-13, read-only on both code bases. `session_cpp` at `814af47f` (after WP3),
OCCT at `d3056ef8`. "Bench" is the 15 pairs of `examples/native_boolean_bench.cpp`, five
operations each: ours 108.2 s, OCCT 6.6 s. Instruction counts are callgrind's and do not
depend on machine load; seconds marked "estimate" are derived from instruction shares.

New measurements taken for the study: OCCT callgrind for box x box, cylinder x sphere, torus x
box, torus x sphere, torus x cone; OCCT on NURBS-converted operands
(`BRepBuilderAPI_NurbsConvert`), the whole bench timed and two pairs profiled; a partial
callgrind of ours on drilled block x sphere; a standalone experiment of a certified search in
two parameters for the bench's curved pairs.

## 1. The five largest causes

Ours splits as section 72 s (seed search 54 s), partition 24 s, assemble 7 s, select 5 s.

| # | Cause | Seconds on the bench | Evidence | Design decision that removes it |
| --- | --- | --- | --- | --- |
| 1 | Start points found by a four-parameter interval proof over the whole curve (`surface_surface_seeds`, `seed_cell_covered`) | 54 | Cylinder x sphere: 65.8 % of the boolean, 1 929 proved cells per surface pair at 2.4 M instructions each. Drilled block x sphere: about 81 % of the boolean is one surface pair (hole x sphere), about 8 000 cells. OCCT's closed form costs 0.36 to 0.7 M instructions per pair. | Keep the guarantee, prove it in two parameters on the composed implicit function. The experiment resolves every curved pair of the bench in 16 to 150 cells and 0.02 to 0.46 ms, none unresolved. This is WP9. |
| 2 | Constant factor of the numeric core | About 48 of 108 as a factor 1.8 on everything; about 24 once cause 1 is gone (estimate) | Cylinder x sphere run: 186 million heap allocations (32 % of instructions), 313 million `nextafter` calls (14.8 %). Box x box: heap 14 %, `Point`/`Vector`/`Color` 17 %, strings 7.7 %; 763 000 allocations per boolean against OCCT's about 16 000. `NurbsSurface::evaluate` costs 13 500 instructions; OCCT's cached B-spline `D0` 278, its torus 359. | WP7. A per-span polynomial cache in the evaluators, as OCCT's `BSplSLib_Cache`, where it can be kept exact. |
| 3 | The same intersection discovered again in every stage because nothing carries it | About 17 to 20 (estimate) | Certified curve/curve calls per boolean: 1 103 on box x box, 762 on torus x box (5.1 M instructions each, 30 % of that boolean). Callers: `trim_parameters`, `boundary_nodes`, `covers`, `compute_spans`, `synchronize`, `equivalent`. OCCT per box x box boolean: 41 edge/edge and 66 edge/face, each once, none during face building. | One interference structure (nodes, segments as ranges, per-face uses). Face building and assembly by identity. `brep_section::FaceResult` already holds the data; the partition does not read it. WP10. |
| 4 | Certificates repeated on trimmed copies, and whole-model validation per face split | About 11 to 15 (estimate) | Torus x box: 229 real `same_parameter` certificates per boolean, 27 % of it. Per certificate we cost 10 to 15 M instructions; OCCT's swarm estimate costs 7 to 12 M. OCCT runs 15 to 25 per boolean. | Certify once per section curve and side, record the reached deviation on the edge, inherit on ranges (WP4b, WP4c). Intermediate `validate` only in test builds. |
| 5 | Exact or certified work where a sign or an estimate decides | About 15 (estimate) | `trace_cycle` polygonises every loop to a quarter of the uv tolerance to get a signed area: 16.6 % of the torus x box boolean. `NurbsCurve::length` in `section_arcs`: 21 075 calls at 313 000 instructions, 10 % of the same boolean. Classification: two agreeing certified rays per split face against every face, 1 094 ray/face tests per box boolean against OCCT's 65. | Signed area in closed form. A fixed quadrature for the arc estimate. Side of a split face decided at its section edge and propagated. |

Three findings that change the picture:

- **Representation accounts for at most 4.4 times of the gap, and no data model change is
  needed to recover it.** OCCT on the same solids converted to NURBS takes 24.9 s instead of
  5.7 s. All 75 results stay valid with the same face counts; volumes agree within 1e-7. On
  NURBS, OCCT is 4.3 times faster than us overall and slower than us on planar pairs (box x
  box 1.62 s against our 0.54 s). `recognize_surface` already supplies the surface kinds.
- **The plane route has no proof today.** `surface_plane_seeds` takes sign changes on a grid
  of four samples per knot span, the same level as OCCT, while the general route proves
  coverage. The guarantee is uneven.
- **Everything up to selecting faces is identical across the five operations of a pair.**
  That is 101 of the 108 s, computed five times. OCCT has the same waste by default; with a
  shared `BOPAlgo_PaveFiller` its bench is 0.68 s for 15 fillers plus 0.64 s for 60 builds.

## 2. Stage by stage

OCCT paths are under `src/ModelingAlgorithms`. Per boolean OCCT averages 0.063 s (6.6 s over
105 booleans, exclusive-or being three). Ours averages 1.44 s: section 0.96 (seeds 0.72),
partition 0.32, assemble 0.09, select 0.07.

### Stage 1: candidate pairs

- **OCCT.** `BOPDS_DS::Init` boxes every vertex, edge and face with its tolerance.
  `BOPDS_Iterator::Intersect` builds one `BOPTools_BoxTree`, traverses it against itself and
  sorts pairs by type. 0.02 to 0.5 % of its time.
- **Ours.** `brep_section::interferences` loops over all face pairs; `excluded()` compares
  interval hulls of the whole surface control net, recomputed per pair, not the trimmed face.
  `brep_assemble::synchronize` is all pairs with a box test; every ray visits every face.
- **Gap.** Quadratic, untrimmed boxes. Negligible on the bench (at most 7 x 7 faces); it will
  matter on many-face models and on results used as operands.
- **Design.** One box tree per operand over faces, edges and vertices, face boxes from the
  trim's uv extent. Low risk.

### Stage 2: face/face section

OCCT (`IntTools_FaceFace::Perform`, then `IntPatch_Intersection::Perform`), on surfaces
restricted to each face's uv bounds:

| Pair kind | Route | What it does |
| --- | --- | --- |
| Plane, cylinder, cone, sphere pairs | `IntPatch_ImpImpIntersection` | `IntAna_QuadQuadGeo` for conics; `IntAna_IntQuadQuad` / `IntAna_Curve` for quartics, parametrised by one surface's angle; then `IntPatch_ALineToWLine` samples the closed form. |
| Torus against a quadric (unless coaxial), thin or flat cones | `IntPatch_ImpPrmIntersection` | Boundary roots by sampling each domain arc (`IntPatch_TheSOnBounds`). Interior starts by Newton from 15 x 15 sample points on a torus or quadric, knots times degree on a B-spline (`IntStart_SearchInside`). Then `IntPatch_TheIWalking`. |
| Anything else | `IntPatch_PrmPrmIntersection` | `IntPolyh_Intersection` meshes both surfaces from at most 2 500 samples each and intersects triangles; if too few hits it repeats with four shifted meshes. Up to five start points per section line, then `IntWalk_PWalking`. |

Measured OCCT costs: closed form 0.36 M instructions per pair; sampling the closed form
22.6 M per line (about 3 400 steps); the torus zero set 13 to 23 % of a torus boolean; on
NURBS operands `IntPolyh` is 1.9 % and walking 15.8 %.

Ours (`surface_section::intersect` on whole surfaces, then `Intersection::surface_surface`):
coincidence tests, then plane closed forms (`extrusion_plane`, `ruling_plane`,
`iso_plane_sections`); `analytic_ssi` (plane with plane, sphere, cylinder and cone; plane x
torus only for a plane across the axis; curved pairs only when coaxial, plus parallel or
Steinmetz cylinders and equal parallel tori); `planar_section_triples` (grid sign changes, no
proof); `marched_section_triples`: `surface_surface_seeds`, `trace_dir`, then
`continuation_arcs`, a second certificate: 172 further `seed_cell_covered` calls per surface
pair prove that consecutive march points lie on one branch. When no curve is found, the same
seed search is run to prove emptiness.

Measured: 54 s of the bench. Per cylinder x sphere surface pair: 171 000 surface evaluations
and 30 000 interval bound evaluations at 219 000 instructions each. `correct_on_seam` (10 s)
is the root finder of the seed search, not tracing: 34 035 of its 34 160 calls come from
`surface_surface_seeds`.

Gap: algorithmic and proof cost, a four-parameter cover of the whole curve against a closed
form or a two-parameter zero set. It is not a missing data type.

### Stage 3: fitting the section and the reached tolerance

- **OCCT.** `GeomInt_WLApprox` with knots from `ApproxInt_KnotTools::BuildKnots`, at 1e-7,
  3D curve and both pcurves together; conics stay exact. `ComputeTolReached3d` calls
  `GeomLib_CheckCurveOnSurface::Perform`: per knot interval a particle swarm with max(3,
  degree) particles, then a Newton minimum; the result becomes the edge tolerance. Fit 8 to
  25 % and check 19 to 30 % of OCCT's time. The estimate is a stochastic search for a
  maximum: a narrow peak between particles is missed and the stored tolerance is too small.
- **Ours.** `even_nodes` plus quintic Hermite pieces from exact jets, accepted at 2e-9. Then
  `same_parameter` at creation, again in `brep_section::paired` after trimming, again in
  `split::validate`, again in `brep_assemble::append_edge`.
- **Design.** One certificate per curve and side with the reached bound stored. A four-point
  Gauss arc estimate in `section_arcs`. Fit at a stated share of the tolerance once the
  reached value is recorded.

### Stage 4: edge/edge, edge/face, and how results are kept

- **OCCT.** `PerformVV`, `VE`, `EE`, `VF`, `EF` each treat a pair once. `IntTools_EdgeEdge`:
  closed form for lines (`ComputeLineLine`, 2 500 instructions), otherwise box subdivision
  of both ranges. `IntTools_EdgeFace` / `IntTools_BeanFaceIntersector`: closed forms, then
  extrema. Results go to `BOPDS_DS` as paves on pave blocks. `MakeSplitEdges` makes one edge
  per pave block on the same curve with a new range (no geometry copied).
  `BOPDS_CommonBlock` joins coincident blocks under one real edge. `BOPDS_FaceInfo` lists
  per face the blocks On, In and Sc. `IntTools_Context` caches per face the 2D classifier,
  point projector, hatcher, surface adaptor, uv bounds and boxes; per edge and per curve a
  projector; per solid a classifier.
- **Ours.** Edge/face is `boundary_pair` calling certified
  `curve_surface_intersection::intersect` per face pair, so a shared edge is done twice (128
  per box boolean against OCCT's 66). There is no edge/edge stage: the same points are found
  three times, `boundary_pair` in 3D, `trim_parameters` by certified 2D curve/curve,
  `boundary_nodes` by certified 3D curve/curve; the arrangement, `append_cut` and the
  assembly then find them again. Results live in `FaceResult` (`nodes`, `boundary_events`,
  `original_trim_laws`, `curve_representatives`) and in the WP3 memo.

### Stage 5: splitting edges and faces

- **OCCT.** `BuildSplitFaces` rebuilds only faces that have In or Sc blocks.
  `BOPAlgo_WireSplitter` orders edges at each vertex by a 2D chord angle; `PerformAreas`
  separates outer loops from holes and places holes by a box tree plus `IntTools_FClass2d`.
  3 to 10 % of its time. Two edges leaving a vertex tangentially can be ordered wrongly by
  the chord angle, which gives wrong loops.
- **Ours.** `split_original_events`; per face `append_cut` deduplicates by certified
  coverage against every boundary and earlier cut; `split::arrange` runs `compute_spans`
  (self-intersection of every source, candidates, certified pairs), `compute_graph`
  (certified fan order `order_sector_fan`), `trace_cycle` (area by polygonising with trimmed
  copies: 94 000 `flat` and 99 000 `interval` calls in five cylinder x sphere booleans) and
  `nest_cycles`; then `BRep result = brep`, a whole-model copy per face (105 per box
  boolean), and `validate` of the whole model.

### Stage 6: classification and solids

- **OCCT.** `BOPTools_AlgoTools::IsInternalFace` decides a face first at a shared edge
  (`GetFaceOff`, the smallest dihedral angle), and only otherwise by `ComputeState` through
  the cached `BRepClass3d_SolidClassifier`. `BOPAlgo_BuilderSolid` connects faces across
  edges and tests each shell with `PerformInfinitePoint`. 10 to 18 % of its time; 65
  ray/face tests per build on box x box.
- **Ours.** `select` per split face: `interior` (a grid search with `face_uv`), then
  `brep_classify::point`: `is_solid`, `boundary_state`, then at least two agreeing rays of
  seven fixed directions against every face (4 to 7 M instructions on a curved surface;
  OCCT's ray/face is 0.7 M). `face_uv` validates the model and extracts the boundary on
  every query (2 331 `is_valid` calls in five box booleans). The assembly adds `outward` (40
  rays, 13.5 % of box x box) and `nest_shells`.

### Stage 7: checks on the result

OCCT validates nothing; `CorrectTolerances` re-measures result edges (1 to 3 %). Ours: input
checks, validation per split, `is_valid` inside the evaluators (4.2 million
`NurbsSurface::is_valid` calls in the cylinder x sphere run), and the assembly's ray checks.
Together 3 to 6 % on curved pairs and about 20 % of box x box.

### Stage 8: volume

OCCT `BRepGProp_Gauss::Compute`, fixed orders: 49 000 surface evaluations per result at about
470 instructions; 1.2 s for 75 results. Ours: 547 000 `NurbsSurface::evaluate` per result at
13 500 instructions; 53.9 s. The WP7 evaluator alone should bring it to roughly 5 s
(estimate from the per-call ratio).

### Stage 9: parallelism

OCCT is off by default (`myGlobalRunParallel = false`). When on, `BOPTools_Parallel::Perform`
covers each intersection type, split faces, split solids and the classification, with one
`IntTools_Context` per thread. Ours has none.

| Loop of ours | Independent today? | What blocks it |
| --- | --- | --- |
| Face pairs in `interferences` | The geometry is | `nurbs_memo::Scope::active` is thread-local; `boundary_pair` snaps a new event to earlier ones, so the result depends on order. Compute per pair in parallel, merge serially in pair order. |
| `partition` of A and of B | Yes | Nothing: two threads at once |
| Faces within one partition | No | Each split copies and replaces the whole model. Independent after WP10. |
| `select` of A and B, and faces within | Yes, read-only | Nothing, once the model check is not repeated per query |
| Volume per face | Yes | Fixed summation order |

Hazard: `Vector::_magnitude` is a mutable cache and races on a shared const `Vector`.

### Stage 10: memory

OCCT makes about 16 000 allocations per box boolean and 120 000 per torus x box boolean, with
`NCollection_IncAllocator` for temporaries. Ours makes 763 000 per box boolean and tens of
millions on curved pairs: `std::vector<std::vector<double>>` in evaluators, 184-byte
`Point`, trimmed copies (200 000 to 400 000 `NurbsCurve::trim` per five booleans), memo keys
built as strings.

## 3. Work packages, ranked

Bench totals are estimates from the measured shares and assume WP7 lands as a factor 1.8,
which is not measured.

| Rank | Package | Change | Risk and verification | Bench total after it | Owner decides |
| --- | --- | --- | --- | --- | --- |
| running | WP7, WP9, WP8 | as started | as started | 108, then 60 (WP7), then 30 (WP9), then about 29.5 (WP8) | none new |
| 1 | **One interference structure** (WP10) | `brep_section`: edge/face once per edge; each node located on its section curves by projection plus the existing ball certificate, replacing the curve/curve calls in `trim_parameters` and `boundary_nodes`; segments emitted (curve, range, two nodes, uses per face). `split`: `FaceCut` carries its end nodes; `compute_spans` builds the graph from ids; `order_sector_fan` stays. `brep_boolean`: `append_cut` deduplicates by identity. `brep_assemble`: edges and vertices by id; `synchronize` and `equivalent` only for coincident faces. | High: four core files. Failure mode: a crossing the old path found geometrically and the node list lacks. A switch runs old and new arrangement and compares graphs on every test; the old path runs when a cut end is not on a node. | about 20.5 | Internal only |
| 2 | **Certificates once** (core of WP4b and WP4c) | Edge as range on a shared curve, reached deviation stored; `same_parameter` returns the bound reached; `validate` and `append_edge` certify only curves created there. | Medium. Every result edge's stored tolerance at least a fresh certificate's bound. | about 14.5 | Decided yes; file formats when ranges are serialised |
| 3 | **Signs and estimates where they decide** | `trace_cycle` area in closed form; one rebuild per operand instead of a copy per face; `section_arcs` without `NurbsCurve::length`; validity checked at `apply`, not per evaluation or query. | Low. Bit-identical except where a loop area is near zero. | about 8.3 | Whether intermediate `validate` moves to test builds |
| 4 | **Classification at the section edge** (WP4a extended) | Across a transversal section edge the side is the sign of one triple product at the edge midpoint with an interval margin; propagate across non-section edges; rays only for parts with no section edge. Orientation from the operands; shell sense by signed volume. | Medium. Classify every face both ways in tests. Tangent sections keep the ray. | about 6.7 | none |
| 5 | **Prepare once, apply per operation** | `prepare(a, b, tol)` returns sections, both partitions and the state of each split face; `apply(prepared, op)` selects and assembles. | Low: same code path. | about 2.2 for the bench's five operations per pair | Public API, or a hidden cache |
| 6 | **Threads** | Face pairs, the two partitions, selection | Medium: determinism of merge order | about 1 to 1.5 on four cores (rough) | Thread pool policy |
| 7 | **Freeform seeding** | A per-surface patch hierarchy with boxes and normal cones; loops excluded where the cones can not hold parallel normals; seeds from patch borders | High | No bench pair uses it; chairs test | none |
| 8 | **Volume** | `brep_measure` on the new evaluators; closed-form primitives for recognised quadric faces | Low | Volume column 54 s to about 5 s | Whether to offer an estimate |
| 9 | **Box trees for candidates** | `brep_section`, `brep_assemble` | Low | Scaling only | none |

## 4. Box x box: OCCT 0.014 s, ours 0.1 s

Per boolean, from call counts (ours over 5 booleans; OCCT over 8 fillers and 11 builds):

| Operation | Ours | OCCT |
| --- | --- | --- |
| Surface pairs intersected | 24 | 20 (`PerformPlanes`, 28 000 instructions each) |
| Curve/curve intersections | 1 103 (968 computed, about 500 000 instructions each) | 41 line/line closed forms (2 500 each) |
| Edge/face | 128 certified | 66 closed forms |
| Ray/face tests | 1 094 (506 computed) | 65 |
| Point-in-solid classifications | 37, plus 8 orientation rays | about 9 `PerformInfinitePoint` |
| `same_parameter` certificates | 258 computed, 1 617 asked | 0 (lines on planes are exact) |
| `BRep::is_valid` | 634 | 0 |
| Whole-model copies | 105 | 0 |
| `NurbsCurve` copies | 21 800 | 0 (edges share curves) |
| `NurbsCurve::point_at` | 320 000 | n/a |
| Heap allocations | 763 000 | about 16 000 |

Shares of our time: certified curve/curve 58 % (from `compute_spans` 16 %, `synchronize`
15 %, `covers` 10 %, `boundary_nodes` 8 %, `trim_parameters` 4 %); classification rays 35 %
(select 10 %, `outward` 13.5 %, the rest in `point`); heap, strings and value objects about
45 % of all instructions across these. OCCT wastes time here too: 20 % of its box x box run
is a particle swarm inside `IntTools_EdgeFace::CheckTouch`.

## 5. Drilled block x sphere: 0.54 s against 25.9 s

- **OCCT, sphere against the hole.** `IntCySp` tries `IntAna_QuadQuadGeo` (conics) and then
  `IntAna_IntQuadQuad`, which returns `IntAna_Curve` objects: the cylinder angle is the
  parameter and the height comes from a quadratic. The analytic step costs 0.7 M
  instructions per pair. `IntPatch_ALineToWLine::MakeWLine` then samples it (about 2 360
  steps), `GeomInt_WLApprox` fits it, and `ComputeTolReached3d` estimates the deviation.
- **OCCT, sphere against the planes.** `IntAna_QuadQuadGeo` gives an exact circle.
- **In the run of nine fillers.** Analytic 0.5 %, sampling 7.7 %, fit 19.7 %, tolerance
  swarm 29 %. No search and no proof of completeness beyond the algebra.
- **Ours.** The planes go through the closed forms. The hole x sphere pair is not coaxial,
  so `analytic_ssi` declines and it goes to the marched route: about 81 % of the boolean is
  `surface_surface_seeds` for this one pair. The curve runs near the sphere's pole region;
  the four-parameter chart degrades there and needs deep subdivision.
- **What is missing.** Nothing in recognition. What is missing is a route for a recognised
  surface against any surface that works in the two parameters of the other one.

The experiment composes the quadric's form with each rational Bezier patch into one Bernstein
polynomial of degree (2p, 2q). A cell is empty when all coefficients have one sign. A cell is
done when all coefficients of one partial derivative have one sign: the zero set is then a
graph, so there is no loop and no singular point inside, and every branch enters and leaves
through the edges.

| Pair | Cells | Deepest level | Time |
| --- | --- | --- | --- |
| cylinder side x sphere | 30 | 4 | 0.019 ms |
| hole x sphere | 64 | 10 | 0.046 ms |
| torus x sphere | 20 | 1 | 0.056 ms |
| torus x cone side | 40 | 4 | 0.066 ms |
| torus x six box planes | 140 | 6 | 0.34 ms |
| torus x six block planes | 148 | 4 | 0.44 ms |

No cell was left unresolved. The margin used is a floating-point allowance, not a rigorous
bound; a rigorous a priori bound is a small constant factor. What it adds to WP9: bound the
composed polynomial, not the surface; do not quarter the spans first; boundary seeds are
univariate Bernstein roots on cell edges; the face's extent on the recognised surface enters
as extra sign tests; choose the implicit side so that poles and apex stay out; the same cells
replace `continuation_arcs` and the emptiness proof; the plane route can move to the same
search and gain a proof; tangent contact needs an explicit node.

## 6. Freeform against freeform

OCCT's seeding is the triangle mesh of `IntPolyh` and costs 1.9 % of its time. It misses a
loop smaller than a mesh triangle and a near-tangent contact the shifted meshes do not cross.
Cheapest design for us that never misses a loop: once per surface, Bezier patches in a box
tree, each with a control-net box and a normal cone; descend both trees; for an overlapping
patch pair, if the two normal cones can not contain parallel normals, no closed loop and no
singular point lies in that pair, and every branch crosses a border of one of the two
patches: seeds are border curve against patch, by the existing certified curve/surface
intersection; subdivide only where the cones overlap, down to the tolerance. The loop
criterion (Sinha, Klassen and Wang 1985; Sederberg and Meyers 1988; Sederberg, Christiansen
and Katz 1989) is cited from memory and must be re-derived and tested before it replaces the
present proof.

## 7. Proof policy

| Certificate | Measured cost | Protects against | OCCT's substitute | Verdict |
| --- | --- | --- | --- | --- |
| Seed coverage in four parameters | 54 s of 108 | A missed branch: a small solid poking through a face without touching its edges gives a valid result with the hole missing | Newton from a 15 x 15 sample grid, or a mesh | **Keep the guarantee, change the proof** (two parameters for recognised pairs, cones and borders for freeform). Under 1 % of today's cost. |
| Plane route seeds | none exists | the same | the same | **Add it**, via the same search |
| Walk continuity (`continuation_arcs`) | 2.5 % of a cylinder x sphere boolean | The marcher jumping to a neighbouring branch | Step control by deflection | **Keep, for free** from monotone cells |
| `same_parameter` | 10 to 15 M instructions each; about 11 to 15 s | 3D curve and pcurve drifting apart between samples: leaks in classification, cracks in tessellation, a later boolean not finding its node | Particle swarm, 7 to 12 M each, 19 to 30 % of OCCT; can underestimate | **Keep, once per curve and side**, reached value stored, inherited on ranges |
| Certified curve/curve | 0.5 M (segments) to 5 M (fitted) each; about 17 to 20 s | A missed crossing of a cut and a boundary: open loop, wrong region | Each pair once with a tolerance | **Keep the primitive, call it rarely**: closed forms for segments, identity in face building, the general routine only for coincident faces |
| Certified fan order at a node | not visible above 1 % | Wrong loop when two cuts leave a node tangentially | Chord angle heuristic | **Keep as is** |
| Certified ray, two agreeing | 4 to 7 M per curved surface; select 5 s plus about 2 to 3 s in assembly; 35 % of box x box | A grazing ray miscounting crossings: a whole face kept or dropped | Tolerance-based ray toward a face point; edge angle first | **Keep, use rarely**: side at the section edge, rays only for parts with no section edge |
| Validation after every split, `is_valid` per query and per evaluation | 3 to 6 % curved, more on planar | Kernel bugs, not input geometry | none | **Drop from release paths**: once on input, once on the result, the rest in test builds |
| Orientation and nesting by rays | 16 % of box x box | An inverted shell, a void attached to the wrong solid | Infinite-point classification per shell | **Keep the check, make it cheap**: sense by signed volume, nesting by one point per overlapping shell pair |
| Fit at 2e-9 | larger curves everywhere downstream | Accumulated deviation across stages | 1e-7 | **Loosen to a stated share of the tolerance** once the reached value is stored |
| Certified volume | 54 s beside the booleans | A wrong number | Fixed Gauss, unknown error | **Keep, make cheap**; offer an estimate |

In one line: the seed, same-parameter, curve/curve and ray guarantees are worth keeping,
because each prevents a wrong but valid-looking solid. Their price today comes from proving
the same thing many times or in too many dimensions, not from proving at all. The
intermediate validations are not guarantees about the result.

## 8. Faster than OCCT

What OCCT does that we need not: the tolerance swarm (19 to 30 % of every curved boolean);
exclusive-or as three booleans (ours is one pass, 1.35 times a union); no reuse across
operations by default; one thread by default; sampling a closed-form curve at about 2 400 to
3 400 points before fitting it; a `BRepClass3d_SolidExplorer` rebuilt per shell test;
`IntTools_FClass2d` rebuilt 30 to 60 times per boolean; and its collapse on NURBS planes,
where we already beat it.

## 9. Targets per pair

Seconds for five operations. Column 2 removes the measured or assigned seed share and applies
closed forms to planar pairs. Column 3 keeps the fraction of the rest that packages 1 to 4 do
not remove. Column 4 divides by 1.8 for WP7. Column 5 shares one preparation across the five
operations, assuming 85 % is independent of the operation.

| Pair | Now | No seed search, planar closed forms | Structure (packages 1 to 4) | With WP7 | One preparation | OCCT |
| --- | --- | --- | --- | --- | --- | --- |
| drilled block x sphere | 25.9 | 4.9 (81 % measured) | 1.7 | 0.93 | 0.30 | 0.54 |
| torus x cone | 15.0 | 3.75 (75 % assigned) | 1.5 | 0.83 | 0.27 | 0.52 |
| torus x sphere | 13.8 | 3.45 (75 % assigned) | 1.4 | 0.77 | 0.25 | 0.42 |
| torus x drilled block | 10.8 | 7.9 (27 % assigned) | 1.4 | 0.79 | 0.25 | 0.68 |
| drilled block x torus | 8.5 | 6.2 (27 % assigned) | 1.1 | 0.62 | 0.20 | 0.92 |
| drilled block x torus, axis-parallel | 6.84 | 5.0 (27 % assigned) | 0.9 | 0.50 | 0.16 | 0.70 |
| cylinder x sphere | 6.57 | 2.25 (65.8 % measured) | 0.79 | 0.44 | 0.14 | 0.18 |
| torus x box | 6.52 | 6.52 | 1.04 | 0.58 | 0.19 | 0.81 |
| torus x box, axis-parallel | 5.83 | 5.83 | 0.93 | 0.52 | 0.17 | 0.74 |
| torus x pyramid | 4.61 | 4.61 | 0.74 | 0.41 | 0.13 | 0.69 |
| pyramid x sphere | 1.51 | 1.51 | 0.30 | 0.17 | 0.05 | 0.12 |
| box x cylinder | 0.86 | 0.5 | 0.15 | 0.085 | 0.03 | 0.08 |
| cone x pyramid | 0.79 | 0.5 | 0.15 | 0.085 | 0.03 | 0.08 |
| box x box | 0.54 | 0.065 | 0.05 | 0.03 | 0.01 | 0.09 |
| sphere x sphere | 0.10 | 0.10 | 0.03 | 0.02 | 0.01 | 0.009 |
| **Total** | **108.2** | **53.1** | **12.2** | **6.8** | **2.2** | **6.6** |

Read honestly: a single boolean from scratch reaches parity overall (6.8 against 6.6); it is
faster than OCCT on planar and torus-with-plane pairs; it stays 1.6 to 2.4 times slower on
quadric pairs, where OCCT writes the curve down and our floor is trace, fit and two
certificates; beating OCCT on the bench as written needs the shared preparation or threads.

## 10. Not determined, and assumptions

- WP7's effect is not measured; the factor 1.8 comes from instruction shares of heap,
  `nextafter` and value objects (45 to 47 %) in profiles that include the volume.
- Per-pair stage shares are measured for four pairs only (box x box, cylinder x sphere, torus
  x box in full; drilled block x sphere from 1.6 booleans). For the other eleven the seed
  share is assigned so that the total matches 54 s.
- The second-level estimates overlap (curve/curve 17 to 20 s, certificates 11 to 15 s,
  `trace_cycle` 10 to 15 s); they are scaled to the per-pair model, not added.
- The experiment is not kernel code: its rounding margin is not a rigorous bound and it uses
  standard rational quadratic patches.
- OCCT timings were taken with builds running beside them (5.66 s in the study against 6.59 s
  in the bench record); the NURBS-mode bench is a single run.
- The freeform chairs case was not profiled after WP3. The loop-exclusion criterion is cited
  from memory.
- The claim that section cuts cross only at nodes assumes valid manifold operands and that
  singular points of a section are emitted as nodes.
