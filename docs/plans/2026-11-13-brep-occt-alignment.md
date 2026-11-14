# BRep booleans: OCCT alignment, speed and volume, benchmarks - plan, 2026-11-13

Branch `claude/clever-ramanujan-dkse3b` in `session_cpp`
([petrasvestartas/session_cpp#21](https://github.com/petrasvestartas/session_cpp/pull/21)).
Status before this plan: `docs/plans/2026-11-12-native-brep-booleans.md`.

## How the work is run

- One work package (WP) is one sub-session: a subagent with the brief written below, its own
  files, and a gate it must pass before it reports.
- Research packages run in parallel. Packages that change code run one at a time, in the order
  given, because they share one build tree and this machine has four cores and 15 GB
  (three compile jobs beside a test run were killed once).
- Every code package ends with the same gate, run by the lead, not by the subagent alone:
  1. its own new test, red before the change and green after;
  2. `brep_boolean_test`, `brep_test`, `brep_section_test`, `intersection_test`, `split_test`
     and any test file of a source file it touched;
  3. the measurement script of WP1, compared with the previous row of the table.
- A package that cannot pass its gate reports what it found and changes nothing: no tolerance is
  loosened, no test skipped, no budget raised without the owner's word.
- One commit per package, authored as the repository owner, no AI trailers.

## Brief every code subagent receives

1. Read `session/session_cpp/CLAUDE.md` rules that apply: least code, least comments, no file
   headers, C++ is ground truth, never include `tolerance.h` in production code.
2. Own only the files named in your package. If another file must change, stop and report.
3. Build with `ninja -j2` in `session_cpp/build`; never more. Run one test file at a time with
   `SESSION_MINITEST_FILE=<name>` or one test with `SESSION_MINITEST_NAME`.
4. Reproduce first. State the measured number or the failing test before changing code.
5. When a design question is open, read the OCCT source at revision `d3056ef8` and cite the file
   and function that decides it. Read, never copy.
6. Report: what changed and why, the before and after numbers, the tests run with their counts,
   anything left open. Do not commit; the lead reviews, runs the gate and commits.

## Work packages

### WP0 - Comparison with OCCT (research, parallel, running)

Three read-only studies: OCCT's data model and boolean pipeline, this kernel's, and OCCT's own
hard boolean tests buildable from primitives. Output: the difference table at the end of this
file, each row ranked by what it costs us today.

Gate: every row cites a file and function on both sides.

### WP1 - Measurement harness (code, first)

Files: `examples/native_boolean_bench.cpp`, `CMakeLists.txt` (one option).
A driver that runs a fixed list of pairs through the five operations and prints per case: wall
time, faces, edges, total control points of 3D curves and of pcurves, largest pcurve, and
whether `volume_exact` finished. The list holds the slow and over-budget cases known today
(drilled block against torus in both poses, torus against box and pyramid, sphere against
drilled block, pyramid against sphere) and five ordinary ones.

Gate: runs to the end; its table for the current head is recorded here as the baseline.

Done, `76690d7b`. Baseline at `b1630523`, full table in
`docs/validation/2026-11-13-boolean-bench-baseline.txt` (times taken while other builds ran,
so good to about a fifth):

| Case (a b seed mode) | boolean s, five ops | largest pcurve, control points | volumes over budget |
| --- | --- | --- | --- |
| 6 5 3 0 drilled block, torus | 240 | 1173 | 5 |
| 6 5 3 1 drilled block, torus | 216 | 1139 | 5 |
| 5 0 1 0 torus, box | 133 | 596 | 5 |
| 5 4 1 0 torus, pyramid | 93 | 2749 | 0 |
| 5 0 1 1 torus, box | 99 | 765 | 1 |
| 5 6 2 1 torus, drilled block | 87 | 500 | 0 |
| 6 2 2 0 drilled block, sphere | 43 | 676 | 0 |
| 5 3 2 0 torus, cone | 37 | 496 | 0 |
| 5 2 1 0 torus, sphere | 23 | 156 | 0 |
| 1 2 1 0 cylinder, sphere | 12 | 166 | 0 |
| 4 2 1 0 pyramid, sphere | 5.8 | 661 | 0 |
| 3 4 1 0 cone, pyramid | 1.8 | 166 | 0 |
| 0 1 1 0 box, cylinder | 1.3 | 9 | 0 |
| 0 0 1 0 box, box | 0.7 | 2 | 0 |
| 2 2 1 0 sphere, sphere | 0.1 | 2 | 0 |
| total | 993 | 2749 | 16 of 75 |

### WP2 - Section pcurve fit at the model tolerance (code)

Finding: fitted pcurves carry 300 to 1200 control points because `certified_run_curve` accepts
only at `tight = min(tol, max(tol * 1e-4, reach * 64 eps))`, about 1e-11, and builds quintic
pieces with full-multiplicity knots; the marched route refines to 0.02 of the tolerance.
Question for OCCT (WP0): the tolerance, degree and segment bounds of `GeomInt_WLApprox` /
`ApproxInt` and whether 2D curves are approximated together with the 3D curve.
Files: `src/intersection.cpp` (fit acceptance and piece construction only), its tests.

Gate: on the WP1 list the pcurve control points fall by at least five times with the
same-parameter certificate still at the model tolerance; `volume_exact` finishes on the torus
cases without touching its budget; the exact volumes in existing tests still hold to 1e-6;
the fuzz sweep of three seeds in both modes stays at 147 of 147.

Done, `4ca55030`. Full table in `docs/validation/2026-11-13-boolean-bench-wp2.txt`.

What changed (`intersection.cpp`, `nurbs_hermite.h`):

- `nurbs_hermite::quintic`: a join whose two one-sided jets are equal takes a knot of
  multiplicity 3 (C2): three control points per smooth span, five before.
- `even_nodes`, shared by the plane and marched routes: the nodes of the fit are chosen among
  the walked samples from the measured gap of each span (sixth root of gap over gap allowed),
  moved to equal shares for three passes, then cut. OCCT does the same from the discrete
  curvature (`ApproxInt_KnotTools::BuildKnots`).
- Plane tracer (`quintic_plane_piece`): world curve and pcurve as quintic pieces from the
  exact jets of the section, broken only where the pcurve crosses a knot of the surface; the
  plane's own pcurve stays the affine image of the world curve, as in
  `IntTools_FaceFace::MakeCurve`. All 16 budget overruns came from this route.
- Marched and pullback routes: start from the ends and breaks, refine only the spans that
  are off. The old spline routes remain as the fallback near tangencies.

| Case | boolean s | pcurve control points | largest pcurve | over budget |
| --- | --- | --- | --- | --- |
| 6 5 3 0 drilled block, torus | 240 > 23 | 92454 > 13230 | 1173 > 168 | 5 > 0 |
| 6 5 3 1 drilled block, torus | 216 > 19 | 86406 > 11910 | 1139 > 159 | 5 > 0 |
| 5 0 1 0 torus, box | 133 > 12 | 50328 > 8244 | 596 > 125 | 5 > 0 |
| 5 4 1 0 torus, pyramid | 93 > 9.8 | 84486 > 8718 | 2749 > 201 | 0 > 0 |
| 5 0 1 1 torus, box | 99 > 11 | 39258 > 7146 | 765 > 139 | 1 > 0 |
| 5 6 2 1 torus, drilled block | 87 > 19 | 39788 > 8838 | 500 > 81 | 0 > 0 |
| 6 2 2 0 drilled block, sphere | 43 > 39 | 25314 > 11358 | 676 > 294 | 0 > 0 |
| 5 3 2 0 torus, cone | 37 > 24 | 17753 > 6243 | 496 > 114 | 0 > 0 |
| 5 2 1 0 torus, sphere | 23 > 22 | 11300 > 4602 | 156 > 96 | 0 > 0 |
| 1 2 1 0 cylinder, sphere | 12 > 11 | 7926 > 3534 | 166 > 48 | 0 > 0 |
| 4 2 1 0 pyramid, sphere | 5.8 > 2.6 | 10920 > 2256 | 661 > 122 | 0 > 0 |
| 3 4 1 0 cone, pyramid | 1.8 > 1.3 | 2853 > 1053 | 166 > 36 | 0 > 0 |
| total, 15 cases | 993 > 195 | 470466 > 88812 (5.3x) | 2749 > 294 | 16 > 0 of 75 |

Gate as measured on Linux: intersection 119/119 (three new tests, red on the old kernel),
surface section 23/23, section 25/25, measure 17/17, split 38/38, classify 19/19, boolean
70/70 in 1068 s, BRep 73/73; fuzz 147/147 in both modes; faces, edges and vertices identical
to the baseline in all 75 rows; the 59 volumes the baseline computed unchanged (largest
difference 2.8e-10 at 13 digits on 30 of them); the 16 former overruns now computed and
consistent with the volume identities.

Bounds changed, for the owner to know:

- Pullback route: the measured gap accepted was `tight` (1e-11 below reach 714); it is now
  `fit_gap = min(tol, max(0.02 tol / max(1, reach), 64 eps reach))`: 2e-9 at unit size, the
  share the marched route already used, equal to the old bound from reach 200 up. It
  depends on the unit through `max(1, reach)`.
- Plane tracer: was split while off by more than 0.5 tol (5e-8 measured); now `traced_gap`,
  2e-9 at unit size, tighter than before at every size.
- Marched route above reach 2200: 9.1e-13 x reach instead of 2e-9, looser there; no test or
  bench case is that large.
- The same-parameter certificate at the model tolerance, the volume budget and every test
  tolerance are unchanged.
- Corrected the same day, `463ee549`: Windows CI failed `Vault Strip Drilled And Mortised`,
  the drill through a wall of radius 2000 removing more than 2e-6 too little. The floor of
  `traced_gap` was 64 times the sampling error; measured on Linux the drill's volume error
  follows it: -1.8e-6 at 64, -5.6e-7 at 16, -2.5e-7 at 4, -3.1e-8 at 1. It is 16 now. The
  floor acts only above a reach of about 12, so the unit-size bench is not expected to move
  (not re-run). After it: boolean 70/70 in 1086 s, BRep 73/73, measure 17/17, intersection
  119/119. The test's note that the drill "measures 1.4e-6 low" was fit error as well.

Not reached: the 5x holds for the list total, not for every case (2.2x to 2.8x where marched
pieces or sphere pullbacks dominate). At millimetre sizes the gain is 1.2x to 3.3x. No
reached tolerance is recorded on edges yet (WP4b).

### WP3 - Work done more than once (code)

Findings: every face split re-certifies every pcurve of the whole BRep (`split.cpp` validate);
`brep_classify::face_uv` and `point` call `is_valid` / `is_solid` and re-extract boundaries on
every query; surfaces are recognized again for every face pair; the same section pair is
intersected again in `append_cut`, the arrangement and the assembly.
Files: `src/split.cpp`, `src/brep_classify.cpp`, `src/brep_boolean.cpp`, `src/brep_section.cpp`
(caches and scoping only; no change of what is checked on the final result).

Gate: identical results (face, edge, vertex counts and volumes of the WP1 list and of the
boolean tests) and the drilled block against torus pair under 60 s for five operations; the
whole boolean test file at least a third faster.

Done, `814af47f`. Bench in `docs/validation/2026-11-13-boolean-bench-wp3.txt`: all 75 rows
identical to WP2's in status, counts, control points and printed volume.

| | before | after |
| --- | --- | --- |
| bench, 15 pairs | 194.6 s | 108.2 s |
| `brep_boolean_test`, 70 tests | 1068 s | 514 s |
| `brep_test`, 73 tests | 409 s | 154 s |
| drilled block against torus, five operations | 22.7 s | 8.5 s |
| chairs test | 277 s | 91 s |

What is reused, each for one boolean or less, so nothing can go stale:

- `brep_section boundary_nodes` (`MetCurves`): the intersection of an event's edge with a
  section curve or another event's edge, once per pair of curves instead of once per event.
  428 s of the test file.
- `nurbs_memo::Scope`, alive for one `brep_boolean::apply`: `curve_intersection::intersect`
  and matched `same_parameter` certificates, keyed by the bytes of the whole input. Failures
  are never stored. This answers `split::validate` after each face split and the assembly.
- `brep_classify` (`SurfaceRoots`): one classification ray against one surface once, not once
  per face split from it.
- `nurbs_interval::blossom`: step weights once per span (bit for bit the same, checked on
  400 000 random blossoms); `seed_cell_covered`: the root enclosure once per call.

Gate on Linux: intersection 119/119, surface section 23/23, section 25/25, measure 17/17,
split 38/38, classify 19/19, assemble 18/18, boolean 70/70, BRep 73/73, hollow 11/11, thicken
15/15, offset 14/14.

Left, with the seconds measured before the changes (test file, bench): repeats across the five
operations of one pair, which need a store that outlives a boolean (surface sections 79 s,
52 s; curve pairs 109 s, 19 s); the same curve pair intersected in several stages from
different copies (`trim_parameters` 69 s, 3 s; `covers` 34 s, 8 s; `compute_spans` 30 s, 1 s;
`synchronize` 19 s, 9 s). What remains is mostly not repeated work: the seed search of the
marched route is half of the bench, and tangent curve pairs are the largest test.

Against OCCT after WP3 (`docs/validation/occt_bench/compare.py`): total 108.2 s against
6.6 s, 16 times; box against box 6, torus against box 8, drilled block against sphere 48.

### WP4 - Structure taken from OCCT (code, one package per accepted row)

Each row of the difference table marked "adopt" becomes a package of its own with its files and
gate written when WP0 is in. Candidates known already: edges with a parameter range on a shared
curve instead of trimmed copies; tolerances that grow on vertices and edges where a boolean had
to merge; analytic curve types kept through the boolean. Rows that would change the public
data model or the file formats are listed for the owner, not started.

Owner's decisions, 2026-11-13: growing tolerances yes, edge ranges yes, frustum yes (done).

#### WP4a - Classification per connected block
Files: `src/brep_boolean.cpp` (select), `src/brep_classify.cpp` (validity checked once per
solid, not per query). Split faces of one operand joined across edges that are not section
edges lie on one side of the other solid: one witness decides the block.
Gate: identical results on the WP1 list and the boolean tests; select time down on the list.

#### WP4b - Tolerances that grow
Files: `src/brep.h`/`.cpp` (rule vertex >= edge >= face, `update_tolerances` used), the fit
in `src/intersection.cpp` (the deviation reached is returned), `src/brep_section.cpp`,
`src/brep_assemble.cpp` (edge and vertex tolerances raised to what a fit or a merge reached,
never lowered), `src/brep_classify.cpp` and `src/split.cpp` (read the tolerance of the item,
not only the global one). The fields already exist and already serialize, so file formats
do not change; what changes is that their values mean something.
Gate: every edge of a boolean result has tolerance >= its measured 3D-to-pcurve deviation;
`is_valid` checks the ordering rule; no result of the WP1 list or the tests reports a
tolerance above the requested one unless a test names why; the flush-cap cases are retried.

#### WP4c - Edges as ranges on shared curves
C++ first. Files: `src/brep.h`/`.cpp` (range on the edge and on each curve-on-surface use,
accessors that return the restricted curve), then each consumer in its own step with its
tests: boundary extraction and classification, section, split, assembly, measure,
tessellation, STEP; JSON and protobuf last, versioned, old files still readable.
The 6 November packets on `codex/native-brep-recovery-20261112` are read first for their
design and their counterexample tests, not applied as patches.
Python, Rust and `session_proto` are separate repositories that this session can not push;
their ports are written up as a follow-up, not done here.
Gate: every existing test green after each consumer; a split produces no trimmed copy of a
curve; the tiny-interval witness `[0, 2.949e-17]` of the handoff is a passing test.

### WP5 - Benchmark cases (code, after WP2 and WP3)

Files: `src/brep_boolean_benchmark_test.cpp`, `tests/fixtures/boolean_benchmarks/*.json`,
`CMakeLists.txt` (test list), `bash/lib/common.sh` class list if required.
The primitive-only cases of OCCT's `tests/boolean` and `tests/bugs/modalg_*` with their stated
areas, volumes and shape counts, plus hard cases from other open kernels' test suites
(truck `shapeops`, SolveSpace, BRL-CAD, CGAL Nef), each with its source noted. A case that
fails stays in the file as a failing test with its message recorded; it is not removed.

Gate: every case runs; the pass count and each failure's message are in this file.

### WP6 - Report

Update both plan files, the PR description, CI green on the three platforms.

## Difference table (WP0, done)

OCCT paths are under `src/ModelingAlgorithms` at `d3056ef8`; ours under `session_cpp/src`.

| Topic | OCCT | Here | Costs us today | Decision |
| --- | --- | --- | --- | --- |
| Section curve approximation | `IntTools_FaceFace::MakeCurve` -> `GeomInt_WLApprox` (`ApproxInt_Approx.gxx`): tolerance 1e-7 (`BOPAlgo_PaveFiller_6.cxx:329`), degree 4 to 8, C2, the 3D curve and both 2D curves fitted together as one multi-curve; the deviation reached is measured (`ComputeTolReached3d`) and becomes the edge tolerance | `certified_run_curve` (`intersection.cpp`) accepts only at `tight`, about 1e-11; quintic Hermite pieces joined C0 with full-multiplicity knots (`nurbs_hermite.h`); the marched route refines to 0.02 of the tolerance; each pcurve fitted on its own | 300 to 1200 control points per pcurve: volume budget, speed, one-rounding knot spans | **WP2 adopt**: accept at the model tolerance |
| Where intersections happen | all of them first, in `BOPAlgo_PaveFiller::PerformInternal` (VV, VE, EE, VF, EF, FF), into `BOPDS_DS` as pave blocks and common blocks; edges split once (`MakeSplitEdges`) | sections first (`brep_section::interferences`), then curve/curve work again per face in the arrangement (`split.cpp compute_spans`), in `append_cut` and in the assembly (`brep_assemble synchronize`) | the same pair intersected up to four times | **WP3 adopt in part**: reuse results, no restructure |
| Face building | `BOPAlgo_BuilderFace` / `BOPAlgo_WireSplitter`: loops by angle order at vertices over edges already split; no curve/curve intersection here | `split::arrange`: a full arrangement in uv with curve/curve and self-intersection per cut, then the whole BRep re-certified after every face (`validate`) | most of the boolean's time on fitted curves | **WP3 adopt in part**: certify only what a split touched |
| Classification | one face per connected block of split faces (`BOPAlgo_Tools::ClassifyFaces`), by the angle at a shared edge (`BOPTools_AlgoTools::IsInternalFace`, `GetFaceOff`) before any solid classifier | every split face by a ray-cast witness (`brep_boolean select`, `brep_classify::point`), each query re-validating the solid | time; grazing rays | **WP4a adopt**: classify per connected block, validity checked once |
| Tolerances | per vertex, edge and face, only ever raised (`BRep_TEdge.lxx:33`, `BOPAlgo_PaveFiller_10.cxx`), vertex >= edge >= face; a fuzzy value widens every test | one global tolerance; the fields exist on vertex, edge and face but are stamped, never grown or read | near-coincident ends must be joined exactly; no way to record that a fit reached 3e-8 | **WP4b adopt** (owner, 2026-11-13) |
| Edge on its curve | a range on a shared curve (`BRep_GCurve` first/last), SameParameter and SameRange flags | a trimmed copy of the curve per edge piece, the curve domain is the range | trims that lose a knot by a rounding; the 6 November range work was about this | **WP4c adopt** (owner, 2026-11-13), C++ first |
| Curve types | lines and conics stay `Geom_Line`, `Geom_Circle`, ... with projected pcurves; only walked lines are approximated | everything is NURBS; conics are exact rational NURBS, their pcurves on curved faces are fitted | fits where a closed form exists | **WP4d, owner decides**: data model |
| Volume | `BRepGProp_Gauss`: fixed Gauss orders per edge and face, at most 61 points, not adaptive by default; tests accept 1 % | `brep_measure`: adaptive, certified to the tolerance, one panel per pcurve span, fixed budget 200000 | budget overrun when pcurves have hundreds of spans | keep ours; WP2 removes the spans |
| Seams | walked lines cut at period boundaries (`IntTools_WLineTool::DecompositionOfWLine`), pcurves shifted by periods (`AdjustPCurveOnSurf`) | the same idea in three routes | fixed this week | none |

Reference numbers in OCCT's tests are mostly surface areas within 1 %. Nearly every cone there
is a frustum: `BRep::create_frustum(radius_base, radius_top, height)` was added for them
(owner's request, 2026-11-13).

## Found while adding the frustum

A round cap lying flush on a planar face of the other solid fails for a plain cylinder as well
as for a frustum (OCCT `bop*_simple` ZF5, ZF7, ZN5, ZD2 and the like): a cylinder of radius 1
and height 4 standing in a 4 x 4 x 4 box gives "face classification is unresolved", a frustum
"Curve intersection exceeded its subdivision limit". The same solid moved off the face by half
a unit passes. This is coincident planar faces where one boundary is a circle inside the
other; it becomes its own package after WP3 and its cases go into WP5.

Fixed 2026-11-13 (`session_cpp` `1057fa50`), two causes:

- Cylinder: a witness on the flush plane is on the supporting surface of a face it is not
  inside; every ray from it started on that surface and stayed unresolved. A ray now starts a
  step past such a surface (`brep_classify grazing_ray`); a ray whose direction has less than
  0.1 along the surface normal is given up for another.
- Frustum: the cap rim cut by the box plane was computed afresh, a rounding off the frustum's
  own rim circle. The plane route now takes the surface's own iso circle
  (`iso_plane_sections`) before any computed section.

Tests `Round Caps Flush On Box Faces` and `Frustum Standing On A Box`; classify 19/19,
intersection 116/116, surface section 23/23, section 25/25, boolean 70/70, assemble 18/18,
hollow 11/11, thicken 15/15, offset 14/14, BRep 73/73 on Linux.

## Exact integer kernels (Solidean, EMBER) - does it carry over to BReps

Researched 2026-11-13 from abstracts and search snippets only: solidean.com, the RWTH pages,
arXiv and ACM were not reachable from this environment, so the papers themselves were not read.

- EMBER (Trettner, Nehring-Wirxel, Kobbelt, SIGGRAPH 2022) is exact because meshes are planes:
  a vertex is the intersection of three input planes, planes are closed under booleans, so
  every predicate is a determinant of bounded degree and fits a fixed-width integer.
- That holds for planar BRep faces with straight edges, which is the same setting.
- It does not hold for free-form faces: two bicubic patches meet in an algebraic curve of
  degree 324, which is not a NURBS, so the output edge must be an approximation and a vertex
  is an algebraic number with no fixed-size integer form. Quadrics are possible in principle
  with algebraic numbers, not with fixed-width integers.
- What carries over is the principle: decide topology exactly, or by a certificate that proves
  or refuses, and confine the tolerance to one recorded place, the distance between a fitted
  edge and the true intersection. The kernel already works this way in part (outward interval
  bounds, Matched / Mismatched / Unresolved). It argues for the per-edge reached tolerance of
  row WP4b.
- Options in order of value for cost: an exact sub-kernel for planar faces (most joinery
  solids; `exact_orientation.h` and the vendored integer Clipper2 are a start); certified
  predicates everywhere; exact ordering inside each face's uv arrangement; a mesh boolean
  with an exact kernel as an independent oracle for tests, not as the kernel.

## OCCT on the same bench (measured 2026-11-13)

Measured again in C++ against OCCT built from source at `d3056ef8`, with the results compared
row by row and the time per stage set against the source on both sides:
`docs/validation/occt_bench/README.md`. In short: all 75 results valid on both sides, faces
identical in 75 rows, volumes within 6.3e-9; OCCT 6.6 s, ours 195 s; per boolean the
intersection part is 31 times OCCT's and the building part 100 times. The table below is the
first measurement, through the Python wheel.

The 15 pairs of the WP1 list, same sizes and poses (the driver's generator reimplemented),
five operations each, run through OCCT 8.0.1 from the `cadquery-ocp` wheel on this machine
(`docs/validation/occt_bench/occt_bench.py`). All 75 OCCT results valid; volumes agree with
ours to four to six digits, so the cases are the same.

| Case | OCCT s | ours after WP2 s | ratio |
| --- | --- | --- | --- |
| 6 5 3 0 drilled block, torus | 1.11 | 22.7 | 20 |
| 6 5 3 1 drilled block, torus | 0.79 | 18.7 | 24 |
| 5 0 1 0 torus, box | 0.96 | 12.4 | 13 |
| 5 4 1 0 torus, pyramid | 0.55 | 9.8 | 18 |
| 5 0 1 1 torus, box | 0.74 | 10.6 | 14 |
| 5 6 2 1 torus, drilled block | 0.65 | 18.8 | 29 |
| 6 2 2 0 drilled block, sphere | 0.54 | 39.0 | 72 |
| 5 3 2 0 torus, cone | 0.54 | 23.8 | 44 |
| 5 2 1 0 torus, sphere | 0.34 | 21.5 | 64 |
| 1 2 1 0 cylinder, sphere | 0.18 | 11.1 | 63 |
| 4 2 1 0 pyramid, sphere | 0.14 | 2.6 | 18 |
| 3 4 1 0 cone, pyramid | 0.08 | 1.3 | 18 |
| 0 1 1 0 box, cylinder | 0.08 | 1.4 | 17 |
| 0 0 1 0 box, box | 0.06 | 0.8 | 14 |
| 2 2 1 0 sphere, sphere | 0.006 | 0.14 | 23 |
| total | 6.8 | 195 | 29 |

Before WP2 the total was 993 s, 147 times OCCT. OCCT's exclusive-or is timed as two cuts and a
fuse. The timing ran while a kernel build was running, so it is good to a few tenths.

## Speed packages after WP3 (2026-11-13)

Box against box has no curved geometry and still takes 0.1 s per boolean against OCCT's
0.014 s. Its callgrind profile: 56 % in `curve_intersection::intersect` on straight segments
(`endpoint_matches` -> `closest_parameter` -> `Closest::curve_point` -> `point_at`), 17 % in
`brep_classify::ray` -> `surface_ray::intersect` against planes, 16 % in
`brep_assemble nest_shells` / `outward` (rays again), about 15 % building and destroying
`Point`, `Vector`, `Color` and their strings.

Measured: `sizeof(Point)` 184, `sizeof(Vector)` 104, a plain three-double struct 24; one
`Point - Point` 31.7 ns, the same on the plain struct 1.28 ns.

### WP7 - A plain coordinate triple (owner's request)

- `xyz`: three doubles, 24 bytes, trivially copyable, no name, guid or colour, every operation
  inline. Lower case like `int` and `float` (owner, 2026-11-13). `xyzf` (three floats) and `ijk` (three 32-bit integers) for buffers only. A
  `std::vector<xyz>` is 3N doubles in a row: a display buffer, a numpy `(N, 3)` array, a Rust
  `&[[f64; 3]]` or a packed protobuf field without a loop.
- One type for points and directions inside the kernel, as OCCT's `gp_XYZ`; `Point` and
  `Vector` stay the public, named objects and hold an `xyz`. Their API and the file formats
  do not change.
- Order: the type and its tests; then the closed forms of WP8 written on it; then the
  evaluators (`NurbsCurve` / `NurbsSurface` point and derivatives without heap), `Closest`,
  intersection, classification; then the containers (`Polyline`, `Mesh`, `Line`, ...).
- Gate after each step: every test identical, bench and boolean test file timed.
- Python and Rust: same type, written up as follow-up (repositories not pushable from here).

### WP8 - Closed forms for lines and planes

Segment against segment, point against segment, ray against plane, each exact, in front of the
general routines. Gate: on every call of the test suite the closed form and the general
routine agree (checked by a temporary harness), all tests identical.

### How the speed packages run (owner, 2026-11-13: match OCCT for real, as much effort as it takes)

Owner, 2026-11-13: for any decision the lead asks about, the lead's own recommendation
stands; decide, record it here, and go on. Decided so far under that rule:

- The identity kept + removed = whole of `check_feature` (`brep_boolean_test.cpp`) is held to
  64 units in the last place of the whole volume, 1e-6 where that is less (`session_cpp`
  `c8ecfe14`). Windows landed 34 units off where 33.5 were allowed, Linux 0 to 13; five
  kernel-side changes measured on Linux left the spread as it was (error-free summation, a
  volume tolerance 100 times tighter, the steps between the pieces of a trim loop, the
  rectangle of a cut face by the exact rule of the uncut one, one anchor per loop). The
  face terms summed are about five times the net volume, so the check sat at the rounding
  floor of the method. The check of a removed volume against its reference is unchanged.
- `Point` and `Vector` keep their public form; the kernel computes on `xyz` inside.
- No analytic curve or surface types are added to the data model (the study: recognition
  already supplies the kinds; OCCT on NURBS operands is only 4.4 times slower than on its
  own types).
- Intermediate validation (after every face split, per classification query, per
  evaluation) leaves the release path once the structure that replaces it is gated: input
  checked once, the result checked once.
- One preparation shared by several operations on a pair comes as an added `prepare` /
  `apply` beside the present calls, which stay.

Measured: compiling the largest kernel source peaks at 0.9 GB and the machine has 16 GB, so
memory never limited the work to one package at a time. WP7 runs in the main tree; WP8 and
WP9 each in a git worktree of `814af47f` with its own build directory; the study reads only.
The lead merges them in the order they finish and runs the whole gate on the merged tree.

### WP8 - Planar solids at OCCT's speed (running)

Closed forms in front of the general certified routines, each returning what the general
routine's contract promises: segment against segment (`curve_intersection::intersect`), point
against segment, ray against an affine plane (`surface_ray::intersect`), `same_parameter` of a
segment on a plane, then whatever the profile of box against box shows next. A temporary
harness runs the general routine beside every closed form over the whole test suite and
compares. Target: box against box at or below OCCT's 0.091 s for five operations (0.54 s now).

### WP9 - Section start points from the boundaries (running)

Finding: the plane route (`surface_plane_seeds`) seeds from a plain sample grid with no proof,
as OCCT does, and is 8 times OCCT; the general route (`surface_surface_seeds`) proves coverage
by interval enclosures over cells of all four parameters and is 30 to 50 times OCCT: 54 s of
the 108 s bench. Every curved pair of the bench has a recognised surface on one side.

Design, the structure of OCCT's `IntPatch_ImpPrmIntersection` with a proof kept:

- An open section arc ends on a boundary curve of one of the two parameter domains: its seeds
  are the intersections of those boundary curves with the other surface, by the existing
  certified `curve_surface_intersection::intersect`.
- A closed loop is found on one surface's two parameters as the zero set of the recognised
  surface's implicit function: a quadtree that discards a cell when an enclosure excludes
  zero and stops where the gradient is proved not to turn by a right angle; seeds are sign
  changes on leaf edges.
- The seeds go to the existing tracer and fit. Where the new search can not decide, the old
  one runs: never weaker than today.
- Freeform against freeform keeps the old search in this package.

Gate: all tests, bench rows as before with volumes within 1e-6, a harness that runs the old
route beside the new one and compares the curves found, fuzz 147 of 147 in both modes.

### The study (done) and what follows from it

`docs/plans/2026-11-13-speed-study.md`: causes with measured seconds, stage by stage against
OCCT's source, a proof policy and targets per pair. Its ranked packages after WP7, WP8, WP9:
one interference structure (WP10, running), certificates once with the reached tolerance
stored (WP4b and WP4c), signs and estimates where they decide, classification at the section
edge (WP4a extended), prepare once and apply per operation, threads, freeform seeding. Its
estimate of the bench after each: 108 now, 60, 30, 29.5, then 20.5, 14.5, 8.3, 6.7 against
OCCT's 6.6; 2.2 with one preparation for the five operations; about 1 to 1.5 with threads.
Its corrections to WP8 and WP9 went to the running packages.

### WP10 - One interference structure (running)

Measured: 1 103 certified curve/curve intersections per box x box boolean where OCCT runs 41
line/line and 66 edge/face closed forms, each once and none during face building; 762 per
torus x box boolean at 5.1 M instructions, 30 % of it; a copy of the whole model per face
split (105 per box boolean); every loop polygonised to a quarter of the uv tolerance for its
signed area. `brep_section::FaceResult` already holds nodes and which section curves pass
through each boundary event; the partition does not read it.

- Stage A, the same results with less work: loop area in closed form, one rebuild per
  operand, `validate` of what a split created.
- Stage B: nodes, segments as parameter ranges on their curves, and per face the segments on
  its boundary, inside it and coincident; filled once by the section stage (edge against
  face once per edge; nodes located by projection plus the existing certificate), read by
  the partition (graph from ids, duplicates by identity, the certified fan order kept) and
  by the assembly (shared edges and vertices by id). Where the structure can not answer, the
  present geometric path runs.

Owns `split`, `brep_boolean`, `brep_assemble`, `brep_section`. Gate: a harness that runs the
present arrangement beside the new one on every face split of the tests and the bench; bench
rows as before; all tests; fuzz 147 of 147 in both modes.

### WP9b - Quadric pairs in closed form (after WP9, needs WP4d decision)

Cylinder, cone and sphere against each other in closed form, and against any surface as a zero
set in two parameters, as OCCT's `IntPatch_ImpImpIntersection` and
`IntPatch_ImpPrmIntersection`. This is the 46 to 72 times group of the OCCT comparison.

## WP7 and WP8 results (session_cpp 29c96fd5, 54780946)

- WP7: `xyz`, `xyzf`, `ijk` (`src/xyz.h`); `NurbsCurve`/`NurbsSurface` `point` and `jet` without heap, `point_at` and
  `evaluate` wrap them; `nurbs_interval` without allocation, inline outward rounding. Bit-identical on the 75 bench
  booleans. Bench 108 s to 53 s, volume column 54 s to 6 s, `brep_boolean_test` 514 s to 232 s.
- WP8: closed forms for straight pairs, feet on straight spans and flat patches, rays on flat patches, same parameter of
  a straight edge on a flat face, each falling back to the general routine near a threshold. Differential against the
  general routines over the gate and the bench: no disagreement except `Closest::surface_point` on a 1e-4 patch, where
  the general routine's Newton does not start (absolute determinant test) and the closed form is right.
- Merged, quiet machine: 75 booleans 45.9 s against OCCT 6.6 s (7 times; 16 after WP3). Box against box 0.07 s against
  0.091 s. Rows equal to WP3 in 75 of 75. Suite 1602 of 1603, the one being the bunny file not checked out here.
  Output: `docs/validation/2026-11-13-boolean-bench-wp7-wp8.txt`.
- Left by both for later packages: `BRep::is_valid` per classification query, `parameter_mapping` for plane pairs,
  plane pairs in `surface_section`, `vertex_interval` in `split::arrange`, whole-model copies, `NurbsSurface::domain`
  validating per call, segment against conic arc, per-span polynomial cache for the evaluators, `NurbsCurve::trim`.

## WP10 and WP9 results (session_cpp 3138b5f2 and the commit after it)

- WP10: `FaceCurve::nodes`, `interior`, `FaceResult::joints`, `BoundaryEvent::inside`, `EdgePiece::exact`; cuts placed by
  node identity, assembly by section and range, loop area in closed form, face splits in place. Identical results on
  bench, tests and fuzz. Not built: `trim_parameters` still intersects (needs a seeded certificate, or a graze within
  tolerance would be missed). 27 % of test face splits (coincident configurations) still take the old arrangement.
- WP9: `src/nurbs_implicit.h`, `boundary_first_seeds`; seeds in two parameters for recognised surfaces, old search as
  fallback (freeform pairs, poles, apex, touching, tolerance near 1e-12). Seed search 66 to 73 % of curved booleans
  to under 0.2 %. A section is now cut where it crosses a crease knot (one more vertex in symmetric drills); a loop
  beside a pole is returned once, not twice. Pole, apex and touching sections fail on both routes as before.
- All four merged, quiet machine: 75 booleans 11.6 s against OCCT 6.6 s (2 times; 16 after WP3, 150 at baseline).
  75 of 75 valid, faces, edges, vertices and printed volumes as before. Suite 1622 of 1623 in 350 s (bunny file).
  Output: `docs/validation/2026-11-14-boolean-bench-wp7-wp10.txt`.
- Ready, not applied: `wp9_length.patch` (arc length of the quintic by Gauss on its own derivative, 6 to 10 % fewer
  instructions, rows identical). Next by measured cost: certificates once (`paired`, `validate`), `curve_intersection`
  with a seed for `trim_parameters`, `continuation_arcs`, classification at the section edge, prepare once, threads,
  per-span polynomial cache, freeform seeding, plane-route seeds from the two-parameter search.

## WP12 and WP13 results (session_cpp 7fe88f85 and the commit after it)

- WP12 (section stage): plane side of a section certified on controls (`surface_section::on_flat_patch`), point
  enclosures by one blossom, arc length on the quintic's derivative, empty plane pairs by separating axes,
  `bernstein_roots` by sign. Rows unchanged. Not built: proved seeds on the plane route (1 % of time, still no proof),
  closed forms for quadric pairs (own package: replaces the walk certificate by algebra).
- WP13: `brep_classify::Solid` (model checked once, passed by the caller), one witness per group of faces joined off
  the other solid's boundary in `select` (30 917 propagated faces against per-face classification: no mismatch),
  `curve_bounds` at a point as one blossom (enclosures bit-identical on 100 M cases), knots inserted in place, volume
  integrand on Bezier cells (volumes move at most 1.5e-15 relative). Behaviour change: `NurbsSurface::domain(dir)`
  checks only that direction's knots.
- Merged, WP11 running beside the bench: 75 booleans 6.2 s against OCCT 6.6 s; 150 s at baseline. 75 of 75 valid,
  rows unchanged, suite 1629 of 1630 (bunny file). Output: `docs/validation/2026-11-14-boolean-bench-wp12-wp13.txt`.
- Slower than OCCT still: pyramid x sphere (2 times), sphere x sphere (3 times, rays against curved faces by certified
  subdivision), cylinder x sphere and cone x pyramid (1.2 to 1.3 times); volume of the results 2.3 s against 1.2 s.
- Left: `interior_uv` and `shell_solid` in assembly on `Solid`, `parameter_mapping` copies for plane pairs,
  `Mesh` construction in every `NurbsSurface` copy, ray against recognised quadrics in closed form, WP11.

## WP11 result and the state after it

- WP11: span-pair certificate memo in `nurbs_memo::Scope` (a piece or a moved end re-proves only the spans whose
  polynomial changed), point residuals bounded by outward de Boor triangles before blossom enclosures,
  `curve_intersection::trim_piece` (bit-identical to the whole trim on 1.8 M pieces), control-box rejection before
  span interval bounds, `same_parameter` calls `surface_section::on_flat_patch`. Not built: certify-only
  `trim_parameters` (no sound seeding from the 3D events), coincident cuts by identity.
- Merged under load 5 to 7: 75 booleans 5.7 s against OCCT 6.6 s; quiet on its base 5.5 s. Rows unchanged; suite
  1635 of 1636 (bunny). Slower than OCCT: sphere x sphere, pyramid x sphere, cylinder x sphere, cone x pyramid.
- Found by pictures (`occt_bench/images`): the BRep is right (volume equal to OCCT's to 6e-9) but `face_meshes`
  mis-trims faces with loops on spheres (missing or untrimmed regions) and `tessellate` throws on 1 2 1 0 and does not
  return on 6 2 2 0. Fix in progress; topology (extra section vertices against OCCT) traced in parallel.

## Next phase, once every bench pair is at OCCT's speed: general shapes, any pose, hard cases

Owner's request (2026-11-14): when the bench reaches OCCT's speed, generalise so that speed and accuracy hold for
other shapes, any rotation and the hard cases, not only the 15 bench pairs. Each item below is gated the same way
as the speed packages: results against OCCT (validity, faces/edges/vertices, volume), time against OCCT, tests.

1. A wider bench (`native_boolean_bench` grows a second list, the OCCT driver the same): every pair of the seven
   primitives plus freeform NURBS solids (lofted, swept, a bicubic patch solid), a fillet-like rolling-ball blend
   and the chair models; each pair at many seeds with uniformly random rotations (not only the two poses of today),
   random scales over 1e-3 to 1e6 and translations up to 1e6. Report per class: failures on each side, time ratio
   median and worst, volume difference, topology match.
2. Hard cases as their own list, each with an OCCT reference where OCCT succeeds:
   - tangent contact: sphere on a plane, cylinder on a plane along a line, two spheres touching, internal tangency;
   - coincident faces: box on box sharing a face or part of one, coaxial cylinders, a cylinder in its own hole;
   - sections through singular points: a sphere's pole, a cone's apex, a torus's inner equator, Viviani's curve
     (self-crossing section), a cone tangent to a plane;
   - near cases: offsets of 1e-9 to 1e-6, almost parallel faces, tiny slivers and edges shorter than tolerance;
   - features: thin walls, small holes in large solids, many holes, a result with several shells or cavities.
   Pole, apex and touching sections fail today on both routes (WP9); this phase fixes them, OCCT's
   IntPatch_ImpImpIntersection and IntAna_QuadQuadGeo being the reference for the tangent and singular cases.
3. Generalise what the speed packages built for the bench primitives:
   - the two-parameter seed search (WP9) and the ray closed forms (WP14) to every recognised quadric in any pose,
     and a freeform route without the four-parameter search (designed in WP9, section 7);
   - closed forms for quadric pairs where the marched route still dominates;
   - the edge-joining step (topology) checked on every class of the wider bench, and the same topology as OCCT
     wherever OCCT's extra cuts are not artefacts;
   - meshing (`tessellate`, `face_meshes`) proved watertight on every result of both benches.
4. Robustness rules: every fast path keeps its fallback; a fuzz sweep over the wider bench in CI (a short seed set)
   and a long sweep nightly; no tolerance relaxed to pass a case.
