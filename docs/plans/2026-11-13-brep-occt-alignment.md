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

### WP4 - Structure taken from OCCT (code, one package per accepted row)

Each row of the difference table marked "adopt" becomes a package of its own with its files and
gate written when WP0 is in. Candidates known already: edges with a parameter range on a shared
curve instead of trimmed copies; tolerances that grow on vertices and edges where a boolean had
to merge; analytic curve types kept through the boolean. Rows that would change the public
data model or the file formats are listed for the owner, not started.

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
| Tolerances | per vertex, edge and face, only ever raised (`BRep_TEdge.lxx:33`, `BOPAlgo_PaveFiller_10.cxx`), vertex >= edge >= face; a fuzzy value widens every test | one global tolerance; the fields exist on vertex, edge and face but are stamped, never grown or read | near-coincident ends must be joined exactly; no way to record that a fit reached 3e-8 | **WP4b, owner decides**: changes what a tolerance means in files |
| Edge on its curve | a range on a shared curve (`BRep_GCurve` first/last), SameParameter and SameRange flags | a trimmed copy of the curve per edge piece, the curve domain is the range | trims that lose a knot by a rounding; the 6 November range work was about this | **WP4c, owner decides**: data model and file formats |
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
