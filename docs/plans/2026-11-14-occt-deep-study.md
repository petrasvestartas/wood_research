# What still makes single booleans slower than OCCT

Study of 2026-11-14, read-only on both code bases. `session_cpp` at `124f36e8`, OCCT at `d3056ef8`.
Measured per single boolean (intersection, union, a-b, b-a): the bench total flatters us because OCCT's
exclusive-or is two cuts and a fuse (three booleans) and ours is one native boolean. Our xor costs 0.31 to
0.75 times OCCT's instructions on every pair below except sphere x sphere; the single booleans are where
we are slower.

Eight pairs: the five of the request and the three the coordinator added.

| Label | Pair |
| --- | --- |
| `6 2 2 0` | drilled block x sphere |
| `1 2 1 0` | cylinder x sphere |
| `4 2 1 0` | pyramid x sphere |
| `5 3 2 0` | torus x cone |
| `2 2 1 0` | sphere x sphere (one inside the other) |
| `1 5 4 0` | cylinder x torus |
| `3 2 5 0` | cone x sphere |
| `6 1 7 0` | drilled block x cylinder |

## 0. What was measured and what is estimated

Measured:

- Callgrind instruction counts (Ir) of every operation separately, both kernels, all eight pairs: the
  drivers build the operands outside the collect window, warm the library up with one box boolean, then
  collect and dump each of the five operations (`$S/study2/src/ours_cg.cpp`, `occt_cg.cpp`). Stage costs
  are inclusive costs of the functions named in the tables, counted where they are entered from a
  function outside the stage (no double counting of nesting). PLT stubs and lazy binding are resolved.
- The same for a snapshot of WP15 (its working-tree diff of `brep_assemble.cpp`, `brep_boolean.cpp`,
  `brep_classify.cpp` at 11:33, applied to `124f36e8`).
- Wall-clock, both kernels back to back, five rounds, minimum per operation, load 4.4 to 5.8.
- Call counts. Caveat: callgrind keeps counting calls while collection is off, so the first operation's
  counts include the warm-up and operand construction; counts below are from the union, which is clean.

Estimated: every saving in section 4 and the projection in section 5. Each is a stated fraction of a
measured sub-stage cost; the fraction is a judgement, marked as such. Overlaps between changes (for
example `is_valid` inside a proof that another change removes) are not subtracted: up to about 10 %.

Build note: ours was linked against the object files of the main tree, which `ninja -n` reported up to
date with `124f36e8` (no edits there, nothing built there). A separate `-g` build in `$S/wt_study` was
started and stopped at 33 of 65 objects to give the two compile slots back; `-g` changes no code, and
callgrind attributes by symbol, so function-level counts are the same.

## 1. Where we stand, per single boolean

| Pair | ours, M Ir (mean of 4) | OCCT | ratio Ir | ours, s (4 singles) | OCCT, s | ratio time | xor ratio (time) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 6 2 2 0 | 1113 | 475 | 2.34 | 0.521 | 0.190 | 2.74 | 0.69 |
| 1 2 1 0 | 359 | 198 | 1.81 | 0.178 | 0.081 | 2.21 | 0.83 |
| 4 2 1 0 | 287 | 114 | 2.52 | 0.131 | 0.058 | 2.26 | 0.70 |
| 5 3 2 0 | 659 | 424 | 1.55 | 0.328 | 0.173 | 1.90 | 0.38 |
| 2 2 1 0 | 15.5 | 4.2 | 3.7 | 0.0077 | 0.0039 | 1.99 | 1.47 |
| 1 5 4 0 | 501 | 362 | 1.38 | 0.249 | 0.154 | 1.62 | 0.41 |
| 3 2 5 0 | 329 | 193 | 1.70 | 0.152 | 0.083 | 1.83 | 0.50 |
| 6 1 7 0 | 264 | 147 | 1.80 | 0.129 | 0.068 | 1.91 | 0.45 |
| all eight | 3528 | 1918 | 1.84 | 1.697 | 0.809 | 2.10 | 0.53 |

Ours runs fewer instructions per second than OCCT (time ratio 2.10 against instruction ratio 1.84 over
the eight pairs), most likely the interval arithmetic with outward rounding and its divisions (not
measured). Time parity therefore needs an
instruction ratio of about 0.85 to 0.9, not 1.0.

## 2. Stage by stage

OCCT stages are `BRepAlgoAPI_BuilderAlgo::IntersectShapes` (the pave filler) and `BuildResult`
(`BOPAlgo_BOP`); ours are `brep_section::interferences`, `partition`, `select`, `assemble`. Matched as
follows.

| Row | ours | OCCT |
| --- | --- | --- |
| face/face section | `Intersection::surface_surface` minus the next two rows, plus empty-pair proofs in `surface_section::intersect` | `IntPatch_Intersection::Perform` |
| walk certificate | `continuation_arcs` (`seed_cell_covered`, root boxes) | nothing |
| approximation and pcurves | `piece_triple`, `quintic_section`, `certified_run_curve`, `analytic_side_pcurve` | `GeomInt_WLApprox::Perform` and the rest of `PerformFF` (`MakeCurve`, pcurve building) |
| reached tolerance / agreement | `same_parameter` in `surface_section::intersect`, `brep_section::paired` | `IntTools_FaceFace::ComputeTolReached3d` |
| edge/edge, edge/face, nodes | `boundary_pair`, `boundary_nodes`, `trim_parameters`, rest of `interferences` | `PerformVV/VE/EE/VF/EF`, `MakeBlocks`, `MakeSplitEdges`, `MakePCurves`, init |
| split faces | `brep_boolean::partition` | `BOPAlgo_Builder::FillImagesFaces` |
| classification, solids | `select` + `assemble` + `joined_edges` | `FillImagesSolids`, `BuildShape/BuildRC/BuildSolid`, post-treat |

### 2.1 All pairs, mean of the four single booleans (M Ir, ours / OCCT)

| stage | 6 2 2 0 | 1 2 1 0 | 4 2 1 0 | 5 3 2 0 | 2 2 1 0 | 1 5 4 0 | 3 2 5 0 | 6 1 7 0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| face/face section | 32 / 40 | 11 / 25 | 26 / 2 | 30 / 115 | 8.2 / 0.0 | 42 / 114 | 9 / 46 | 15 / 7 |
| walk certificate | 407 / 0 | 69 / 0 | 0 / 0 | 191 / 0 | 0 / 0 | 79 / 0 | 94 / 0 | 47 / 0 |
| approximation and pcurves | 195 / 149 | 45 / 75 | 89 / 11 | 70 / 105 | 0 / 0.2 | 53 / 78 | 84 / 47 | 10 / 53 |
| reached tolerance / agreement | 118 / 174 | 47 / 53 | 39 / 39 | 96 / 102 | 0 / 0 | 79 / 74 | 28 / 53 | 39 / 29 |
| edge/edge, edge/face, nodes | 78 / 22 | 45 / 9 | 77 / 26 | 109 / 52 | 0.1 / 0.8 | 111 / 51 | 47 / 12 | 98 / 19 |
| of which section trimmed in uv (ours) | 31 | 20 | 33 | 66 | 0 | 67 | 20 | 43 |
| split faces | 226 / 25 | 74 / 7 | 36 / 9 | 135 / 15 | 0.1 / 0 | 78 / 12 | 55 / 7 | 43 / 12 |
| classification, solids | 55 / 65 | 67 / 29 | 21 / 27 | 28 / 35 | 7.1 / 3.0 | 59 / 33 | 11 / 27 | 11 / 28 |
| other | 1.0 / 0.3 | 0.4 / 0.2 | 0.6 / 0.3 | 0.6 / 0.2 | 0.1 / 0.1 | 0.5 / 0.2 | 0.3 / 0.2 | 0.9 / 0.4 |
| **single boolean** | **1113 / 475** | **359 / 198** | **287 / 114** | **659 / 424** | **15.5 / 4.2** | **501 / 362** | **329 / 193** | **264 / 147** |
| xor (OCCT: 2 cuts + fuse) | 1228 / 2177 | 545 / 808 | 311 / 413 | 700 / 2225 | 20 / 8 | 550 / 1602 | 345 / 769 | 283 / 680 |

Gap summed over the eight pairs (ours minus OCCT, mean single boolean, M Ir): walk certificate +888,
split faces +558, edge/edge, edge/face and trim +374 (of it 281 the uv trim), approximation and pcurves
+29 net (+161 on 6 2 2 0, 4 2 1 0, 3 2 5 0; we are cheaper on the other marched curves), classification
+12 net (+64 on the two outliers WP15 removes, cheaper elsewhere), face/face search -175 (we are
cheaper), agreement -77 (we are cheaper), other +2. Total gap 1 611.

Where we are already cheaper than OCCT: the agreement certificate (our `same_parameter` 0.1 to 0.6 M per
call, OCCT's swarm search `GeomLib_CheckCurveOnSurface` 1.3 to 14.5 M per check), the search on torus
pairs (OCCT's `IntPatch_ImpPrmIntersection` 106 M per op on 5 3 2 0 and 1 5 4 0, ours 30 to 42 M), the
approximation of marched curves on 1 2 1 0, 5 3 2 0, 1 5 4 0, 6 1 7 0, and classification on five pairs
(OCCT's `BOPAlgo_BuilderSolid::PerformAreas` casts rays from infinity, `PerformInfinitePoint`, 7 to 9 per
op at 1.7 to 6.1 M each).

### 2.2 Per pair and per operation (M Ir)

#### "6 2 2 0" drilled block x sphere

| stage | ours I | U | A-B | B-A | OCCT I | U | A-B | B-A |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| face/face section | 32.9 | 33.1 | 33.1 | 29.5 | 40.3 | 40.2 | 40.2 | 40.2 |
| walk certificate | 405.7 | 405.8 | 405.8 | 411.8 | - | - | - | - |
| approximation and pcurves | 191.7 | 191.7 | 191.6 | 203.8 | 149.2 | 148.8 | 149.1 | 149.0 |
| reached tolerance / agreement | 118.2 | 118.2 | 118.3 | 118.9 | 173.6 | 173.7 | 173.6 | 173.5 |
| edge/edge, edge/face, nodes | 78.3 | 78.5 | 78.5 | 78.2 | 22.2 | 21.8 | 21.8 | 21.8 |
| of which section trimmed in uv | 31.3 | 31.4 | 31.4 | 31.3 | - | - | - | - |
| split faces | 225.7 | 225.7 | 225.7 | 226.1 | 25.1 | 25.0 | 25.0 | 25.2 |
| classification, solids | 42.9 | 38.5 | 38.1 | 100.9 | 60.9 | 75.4 | 63.5 | 61.0 |
| other | 0.8 | 1.1 | 1.0 | 0.9 | 0.3 | 0.3 | 0.2 | 0.3 |
| total | 1096.3 | 1092.6 | 1092.1 | 1170.2 | 471.6 | 485.5 | 473.3 | 471.0 |

#### "1 2 1 0" cylinder x sphere

| stage | ours I | U | A-B | B-A | OCCT I | U | A-B | B-A |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| face/face section | 10.9 | 10.9 | 11.0 | 11.7 | 24.7 | 24.4 | 24.4 | 24.4 |
| walk certificate | 69.2 | 69.2 | 69.2 | 69.4 | - | - | - | - |
| approximation and pcurves | 44.7 | 44.6 | 44.6 | 45.0 | 75.8 | 75.3 | 75.3 | 75.3 |
| reached tolerance / agreement | 46.5 | 46.5 | 46.5 | 47.1 | 52.9 | 52.8 | 52.8 | 52.8 |
| edge/edge, edge/face, nodes | 45.2 | 45.3 | 45.2 | 45.3 | 9.1 | 8.8 | 8.8 | 8.8 |
| of which section trimmed in uv | 20.3 | 20.4 | 20.3 | 20.3 | - | - | - | - |
| split faces | 74.0 | 73.9 | 73.9 | 74.6 | 7.2 | 7.2 | 7.2 | 7.2 |
| classification, solids | 234.3 | 11.7 | 11.7 | 11.7 | 27.7 | 34.0 | 27.7 | 27.7 |
| other | 0.4 | 0.4 | 0.4 | 0.4 | 0.2 | 0.2 | 0.2 | 0.2 |
| total | 525.1 | 302.4 | 302.4 | 305.2 | 197.5 | 202.7 | 196.3 | 196.4 |

#### "4 2 1 0" pyramid x sphere

| stage | ours I | U | A-B | B-A | OCCT I | U | A-B | B-A |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| face/face section | 26.1 | 26.1 | 26.1 | 26.3 | 1.7 | 1.6 | 1.6 | 1.6 |
| walk certificate | 0.0 | 0.0 | 0.0 | 0.0 | - | - | - | - |
| approximation and pcurves | 89.3 | 89.2 | 89.2 | 89.2 | 11.4 | 11.2 | 11.2 | 11.1 |
| reached tolerance / agreement | 38.5 | 38.5 | 38.5 | 38.5 | 39.1 | 39.1 | 39.1 | 39.1 |
| edge/edge, edge/face, nodes | 76.5 | 76.5 | 76.5 | 76.7 | 26.1 | 25.5 | 25.5 | 25.5 |
| of which section trimmed in uv | 33.3 | 33.3 | 33.3 | 33.3 | - | - | - | - |
| split faces | 35.7 | 35.6 | 35.6 | 35.6 | 9.1 | 9.1 | 9.1 | 9.0 |
| classification, solids | 15.7 | 29.1 | 29.0 | 9.4 | 26.6 | 28.8 | 26.4 | 26.2 |
| other | 0.6 | 0.6 | 0.6 | 0.6 | 0.3 | 0.3 | 0.3 | 0.3 |
| total | 282.4 | 295.7 | 295.6 | 276.2 | 114.2 | 115.5 | 113.2 | 112.8 |

#### "5 3 2 0" torus x cone

| stage | ours I | U | A-B | B-A | OCCT I | U | A-B | B-A |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| face/face section | 31.0 | 31.2 | 31.1 | 25.2 | 115.5 | 115.3 | 115.2 | 115.2 |
| walk certificate | 188.4 | 188.4 | 188.4 | 198.5 | - | - | - | - |
| approximation and pcurves | 70.7 | 70.6 | 70.6 | 69.2 | 104.9 | 104.4 | 104.4 | 104.4 |
| reached tolerance / agreement | 95.4 | 95.4 | 95.4 | 98.4 | 102.4 | 102.3 | 102.3 | 102.3 |
| edge/edge, edge/face, nodes | 109.0 | 109.1 | 109.1 | 109.7 | 52.3 | 51.7 | 51.7 | 51.7 |
| of which section trimmed in uv | 66.0 | 66.1 | 66.1 | 66.5 | - | - | - | - |
| split faces | 134.0 | 134.0 | 134.0 | 136.0 | 14.7 | 14.7 | 14.7 | 14.7 |
| classification, solids | 30.4 | 26.5 | 26.3 | 28.1 | 33.3 | 39.5 | 33.5 | 33.3 |
| other | 0.6 | 0.6 | 0.6 | 0.6 | 0.2 | 0.3 | 0.2 | 0.2 |
| total | 659.4 | 655.8 | 655.3 | 665.8 | 423.4 | 428.3 | 422.2 | 422.0 |

#### "2 2 1 0" sphere x sphere

| stage | ours I | U | A-B | B-A | OCCT I | U | A-B | B-A |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| face/face section | 8.2 | 8.2 | 8.2 | 8.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| walk certificate | 0.0 | 0.0 | 0.0 | 0.0 | - | - | - | - |
| approximation and pcurves | 0.0 | 0.0 | 0.0 | 0.0 | 0.2 | 0.2 | 0.2 | 0.2 |
| reached tolerance / agreement | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| edge/edge, edge/face, nodes | 0.1 | 0.1 | 0.1 | 0.1 | 0.9 | 0.8 | 0.8 | 0.8 |
| of which section trimmed in uv | 0.0 | 0.0 | 0.0 | 0.0 | - | - | - | - |
| split faces | 0.1 | 0.1 | 0.1 | 0.1 | 0.0 | 0.0 | 0.0 | 0.0 |
| classification, solids | 6.7 | 6.5 | 3.6 | 11.7 | 3.1 | 3.2 | 2.6 | 3.0 |
| other | 0.1 | 0.1 | 0.0 | 0.1 | 0.1 | 0.1 | 0.1 | 0.1 |
| total | 15.2 | 14.9 | 12.0 | 20.0 | 4.4 | 4.3 | 3.8 | 4.1 |

#### "1 5 4 0" cylinder x torus

| stage | ours I | U | A-B | B-A | OCCT I | U | A-B | B-A |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| face/face section | 40.2 | 40.4 | 40.3 | 47.4 | 114.3 | 114.0 | 114.1 | 114.1 |
| walk certificate | 71.0 | 71.0 | 71.0 | 102.4 | - | - | - | - |
| approximation and pcurves | 53.1 | 53.0 | 53.1 | 52.8 | 78.0 | 77.6 | 77.6 | 77.6 |
| reached tolerance / agreement | 79.7 | 79.7 | 79.7 | 78.1 | 73.8 | 73.7 | 73.7 | 73.7 |
| edge/edge, edge/face, nodes | 110.1 | 110.2 | 110.2 | 111.4 | 51.2 | 50.7 | 50.8 | 50.9 |
| of which section trimmed in uv | 66.8 | 66.9 | 66.8 | 66.7 | - | - | - | - |
| split faces | 78.3 | 78.3 | 78.3 | 77.0 | 12.4 | 12.3 | 12.3 | 12.3 |
| classification, solids | 27.1 | 87.0 | 86.7 | 35.2 | 32.0 | 36.5 | 32.1 | 31.9 |
| other | 0.5 | 0.5 | 0.5 | 0.5 | 0.2 | 0.2 | 0.2 | 0.2 |
| total | 459.9 | 520.0 | 519.6 | 504.8 | 362.0 | 365.1 | 360.6 | 360.7 |

#### "3 2 5 0" cone x sphere

| stage | ours I | U | A-B | B-A | OCCT I | U | A-B | B-A |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| face/face section | 9.2 | 9.2 | 9.2 | 9.5 | 46.4 | 46.2 | 46.2 | 46.2 |
| walk certificate | 94.2 | 94.2 | 94.2 | 94.4 | - | - | - | - |
| approximation and pcurves | 84.3 | 84.2 | 84.2 | 84.3 | 47.8 | 47.2 | 47.2 | 47.2 |
| reached tolerance / agreement | 27.8 | 27.8 | 27.9 | 27.8 | 53.1 | 53.0 | 53.0 | 53.0 |
| edge/edge, edge/face, nodes | 47.3 | 47.3 | 47.3 | 45.9 | 12.8 | 12.3 | 12.3 | 12.3 |
| of which section trimmed in uv | 19.6 | 19.6 | 19.6 | 19.6 | - | - | - | - |
| split faces | 54.7 | 54.6 | 54.6 | 54.6 | 7.1 | 7.1 | 7.1 | 7.1 |
| classification, solids | 12.0 | 11.5 | 11.5 | 9.7 | 25.8 | 30.9 | 25.8 | 25.6 |
| other | 0.3 | 0.3 | 0.3 | 0.3 | 0.2 | 0.2 | 0.2 | 0.2 |
| total | 329.8 | 329.2 | 329.3 | 326.5 | 193.1 | 196.9 | 191.8 | 191.6 |

#### "6 1 7 0" drilled block x cylinder

| stage | ours I | U | A-B | B-A | OCCT I | U | A-B | B-A |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| face/face section | 16.1 | 16.1 | 16.1 | 13.3 | 6.8 | 6.8 | 6.8 | 6.8 |
| walk certificate | 52.3 | 52.3 | 52.3 | 31.6 | - | - | - | - |
| approximation and pcurves | 10.3 | 10.3 | 10.3 | 7.6 | 53.0 | 52.5 | 52.5 | 52.5 |
| reached tolerance / agreement | 39.0 | 39.0 | 39.0 | 38.5 | 28.5 | 28.4 | 28.4 | 28.6 |
| edge/edge, edge/face, nodes | 98.2 | 98.1 | 98.1 | 97.5 | 18.9 | 18.4 | 18.5 | 18.5 |
| of which section trimmed in uv | 43.6 | 43.5 | 43.5 | 42.7 | - | - | - | - |
| split faces | 43.5 | 43.4 | 43.4 | 42.9 | 12.2 | 12.2 | 12.2 | 12.2 |
| classification, solids | 9.3 | 12.9 | 13.5 | 9.1 | 26.3 | 32.5 | 26.4 | 26.2 |
| other | 0.8 | 0.9 | 0.9 | 0.8 | 0.4 | 0.5 | 0.4 | 0.4 |
| total | 269.5 | 273.2 | 273.7 | 241.3 | 146.1 | 151.3 | 145.3 | 145.3 |

Every operation of a pair repeats the same section and partition on both sides (OCCT runs a full
`BOPAlgo_PaveFiller` per `BRepAlgoAPI_*` call too); only classification and assembly differ.

### 2.3 Counts and cost per call (union; in brackets M Ir per call)

| count | side | 6 2 2 0 | 1 2 1 0 | 4 2 1 0 | 5 3 2 0 | 2 2 1 0 | 1 5 4 0 | 3 2 5 0 | 6 1 7 0 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| face pairs intersected | ours | 6 (125) | 2 (84) | 5 (23) | 2 (193) | 1 (8.2) | 2 (120) | 2 (104) | 13 (8.4) |
| | OCCT | 3 (120) | 2 (76) | 5 (10) | 2 (160) | 1 (0.14) | 2 (132) | 2 (73) | 8 (11) |
| marched pairs (ours) / ALine->WLine or ImpPrm walks (OCCT) | ours | 1 (503) | 1 (109) | 0 | 1 (256) | 0 | 1 (116) | 1 (112) | 1 (74) |
| | OCCT | 2 (19) | 1 (23) | 0 | 2 (53) | 0 | 2 (53) | 2 (22) | 0 |
| walk-certificate cell proofs (`seed_cell_covered`) | ours | 909 | 165 | 0 | 396 | 0 | 180 | 186 | 174 |
| interval surface enclosures (`nurbs_interval::surface_bounds`) | ours | 6860 | 1253 | 20 | 3105 | 6 | 1327 | 1430 | 1257 |
| curve-on-surface certificates / tolerance checks | ours | 340 (0.54) | 186 (0.32) | 262 (0.38) | 240 (0.45) | 4 (0.20) | 200 (0.46) | 116 (0.64) | 461 (0.10) |
| | OCCT | 12 (14.5) | 6 (8.8) | 14 (2.8) | 14 (7.3) | 0 | 12 (6.1) | 6 (8.8) | 22 (1.3) |
| edge/face | ours | 13 (3.0) | 5 (4.2) | 13 (3.1) | 6 (6.0) | 0 | 7 (5.0) | 4 (6.0) | 42 (1.0) |
| | OCCT | 4 (0.28) | 4 (0.21) | 12 (1.7) | 5 (7.6) | 2 (0.04) | 4 (9.0) | 4 (1.8) | 16 (0.43) |
| curve/curve (ours, all callers) / edge/edge (OCCT) | ours | 168 (0.57) | 97 (0.49) | 81 (0.62) | 129 (0.81) | 0 | 85 (0.97) | 36 (0.92) | 101 (0.50) |
| | OCCT | 6 (0.56) | 4 (0.31) | 11 (0.10) | 8 (0.35) | 1 (0.03) | 8 (0.49) | 5 (0.19) | 16 (0.21) |
| face splits / faces built | ours | 4 (54) | 3 (22) | 6 (5.2) | 3 (40) | 0 | 3 (24) | 3 (16) | 7 (4.7) |
| | OCCT | 4 (6.1) | 3 (2.3) | 6 (1.4) | 3 (4.8) | 0 | 3 (4.0) | 3 (2.3) | 7 (1.7) |
| point-in-solid queries | ours | 8 (2.4) | 4 (1.2) | 4 (0.8) | 5 (2.8) | 2 (1.7) | 4 (1.9) | 4 (1.2) | 4 (0.8) |
| | OCCT | 9 (6.1) | 7 (3.3) | 7 (2.1) | 7 (3.6) | 6 (0.2) | 7 (2.9) | 7 (3.2) | 7 (1.7) |
| ray/face intersections | ours | 88 (0.12) | 20 (0.27) | 42 (0.57) | 17 (0.76) | 5 (1.0) | 36 (2.2) | 15 (0.41) | 60 (0.09) |
| | OCCT | 43 (0.90) | 21 (0.66) | 36 (0.21) | 30 (0.44) | 8 (0.07) | 29 (0.40) | 18 (0.79) | 62 (0.13) |
| surface point evaluations | ours | 81 774 | 20 291 | 27 321 | 42 435 | 717 | 33 078 | 25 504 | 22 014 |
| | OCCT | 175 726 | 59 482 | 53 837 | 143 098 | 615 | 118 976 | 64 027 | 44 864 |

OCCT's 0 point-in-solid queries in face classification: all of OCCT's classifier calls above are in
`BuilderSolid` (shell containment); split faces are classified by angle at a shared edge (section 3.6).
Ours evaluates surfaces half as often as OCCT; evaluation count is not the difference.

## 3. The stages where we cost more, against OCCT's source

### 3.1 Walk certificate: 887 M Ir of the 1 609 M gap

Ours (`intersection.cpp`, `marched_section_triples` -> `continuation_arcs` -> `continuation_arc` ->
`seed_cell_covered`): after the march and the quintic fit of a section piece, every consecutive pair of
march points is proved to be joined by exactly one branch of the section: a box in the four parameters
of both surfaces around the two points, a Krawczyk-style test with one parameter fixed (a 3 x 3 interval
Jacobian from `nurbs_interval::surface_bounds` of both NURBS patches with derivatives), then root boxes at
both ends (`point_gap`, `graph_root_box`). Failure bisects the segment. Cost on 6 2 2 0: 909 cell proofs
at 0.38 M, 5 410 interval surface enclosures at 49 000 Ir each, 406 M per operation, more than OCCT's
whole boolean (475 M). Same structure on 5 3 2 0 (396 cells, 188 M), 3 2 5 0 (186, 94 M), 1 5 4 0
(180, 71 M), 1 2 1 0 (165, 69 M), 6 1 7 0 (174, 52 M).

OCCT has no equivalent. Quadric pairs (cylinder x sphere, cone x sphere, cylinder x cylinder) go through
`IntPatch_ImpImpIntersection` -> `IntAna_QuadQuadGeo` / `IntAna_IntQuadQuad`: the section is written down
as a curve of the angle on one quadric (0.7 to 6.6 M per op, measured), turned into points by
`IntPatch_ALineToWLine` (19 to 44 M) and approximated. Torus pairs go through
`IntPatch_ImpPrmIntersection`: the zero set of the quadric's implicit function on the torus's two
parameters, walked from start points on the boundary and from an inside sample grid (106 M per op on
5 3 2 0 and 1 5 4 0, more than our search). Neither proves that a walk did not jump branches; the closed
form needs no such proof, the walk has none.

What we can adopt and keep the certificate: every curved pair of the bench has a recognised surface on
one side (WP9 already seeds there in two parameters, `nurbs_implicit.h`). The same reduction applies to
the walk certificate: on the other surface's parameters the section is the zero set of one function
g(s, t) = F(S(s, t)), F the recognised implicit. A box is certified to hold exactly one arc, a graph over
s, when an interval enclosure of dg/dt excludes zero and g changes sign on the two t-sides; the arc is the
march's arc when both march points are inside and their root boxes are proved, as now. That needs one
enclosure of S with first derivatives on a two-parameter box plus the polynomial F (a few hundred Ir for
a quadric) instead of about six four-parameter enclosures and a 3 x 3 interval solve. The pcurve on the
recognised side keeps its own certificate (the agreement `same_parameter`, which runs anyway). For quadric
x quadric the box test becomes the sign of a trigonometric discriminant in one angle, as IntAna's.

Saving, estimate: 80 % of the walk certificate (the 2026-11-13 speed study's standalone two-parameter search
resolved each bench pair in 16 to 150 cells, 0.02 to 0.46 ms). 326 M on 6 2 2 0, 153 M on 5 3 2 0,
55 to 75 M on the other four marched pairs. Lower-risk first step with the same proof: start
`continuation_arcs` from every k-th march point and let its existing bisection refine; not measured.

### 3.2 Splitting faces: 561 M Ir of the gap

Ours (`split.cpp`, `split_face` -> `compute_spans`, `compute_graph`): every face split re-derives the
arrangement of its cuts and boundary edges in uv. In `compute_spans`, `self_events` runs a certified
`curve_self_intersection::intersect` on every source curve, boundary edges included, on every split
(6 2 2 0: 56 calls, 74 M per op), and `parameter_events` intersects cut pairs of one family, sections of
the same two surfaces (25 calls, 46 M). `compute_graph` checks every piece against vertex balls by
`vertex_interval` (1 866 calls, 22 M). Whole stage per face split: 54 M on 6 2 2 0, 40 M on 5 3 2 0,
5 to 24 M elsewhere. No fallback from placed to unplaced arrangement occurred in any measured split.

| per op, M Ir (calls) | 6 2 2 0 | 1 2 1 0 | 4 2 1 0 | 5 3 2 0 | 1 5 4 0 | 3 2 5 0 | 6 1 7 0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| self-intersection proofs | 73.8 (56) | 16.2 (35) | 10.6 (44) | 38.8 (47) | 20.4 (37) | 18.2 (23) | 10.0 (77) |
| curve/curve between cuts | 46.4 (25) | 26.9 (15) | 1.0 (1) | 36.2 (19) | 16.6 (9) | 5.7 (3) | 6.0 (4) |
| `compute_graph` | 56.1 (4) | 13.7 (3) | 9.1 (6) | 27.0 (3) | 16.8 (3) | 14.5 (3) | 6.4 (7) |
| of which `vertex_interval` | 22.1 (1866) | 6.5 (576) | 4.0 (405) | 12.0 (1041) | 7.7 (675) | 6.0 (528) | 2.9 (417) |
| cycles and nesting | 27.5 | 4.0 | 3.1 | 9.5 | 6.1 | 4.9 | 4.4 |
| `split_face` total | 214.3 (4) | 67.0 (3) | 31.5 (6) | 119.7 (3) | 72.6 (3) | 49.3 (3) | 32.7 (7) |
| OCCT `FillImagesFaces` | 25.0 | 7.2 | 9.1 | 14.7 | 12.3 | 7.1 | 12.2 |

OCCT (`BOPAlgo_BuilderFace`, `BOPAlgo_WireSplitter`, 1 to 3 M): no intersection while building faces.
Edges arrive split at their paves; vertices are shared objects; loops are traced by angle at each vertex.
Section edges that cross each other are found once, in 3D, by a nested `BOPAlgo_PaveFiller` on the new
section edges in `PostTreatFF` (0.8 to 9.5 M per op). Self-intersection of a section curve is never
checked.

What we can adopt and keep the certificate: the facts are already proved before the split. A marched
section piece is certified to be one graph branch (3.1), so it cannot cross itself; an analytic section
(conic) is simple by construction; original boundary edges are proved simple once per operand, not per
split. Two pieces of one family (same surface pair) can meet only at section nodes, which
`brep_section::FaceResult` already holds. Carry a "simple" flag and the family's node list on
`split::FaceCut` and skip `self_events` and same-family `parameter_events` for flagged sources; place
vertex membership by node identity where WP10's nodes name it. Saving, estimate: self-intersection +
same-family pairs + half of `vertex_interval`: 131 M on 6 2 2 0, 81 M on 5 3 2 0, 14 to 46 M elsewhere.

### 3.3 Trimming the section in uv, and edge against face: 350 M Ir of the gap

Ours: `brep_section::support_curves` -> `trim_parameters` intersects every section pcurve with the uv
boundary curves of its face by certified `curve_intersection::intersect` (6 1 7 0: 94 calls, 43 M; 5 3 2 0
and 1 5 4 0: 66 to 67 M), although `boundary_pair` has just intersected the same boundary edges with the
other surface in 3D (`curve_surface_intersection::intersect`, 4 to 42 calls per op at 1 to 6 M each, the
general route `intersect_general` subdividing the surface: `NurbsSurface::split` and `bounds` on every
level).

OCCT: the section line's ends come from the intersection itself (`IntPatch` line vertices on the
restriction arcs); edge/face points come from `PerformEF` (`IntTools_EdgeFace`: closed forms for
lines against planes and quadrics, sampling plus Newton otherwise, 0.04 to 9 M per call) and are put on
section curves by projection in `PutPavesOnCurve` (0.1 to 3.5 M per op). No curve/curve intersection
in uv.

What we can adopt and keep the certificate: (a) trim from the 3D events: each boundary event of
`boundary_pair` has a point on the edge and, through the section, a candidate parameter on the section
curve; certify it with a root box (as the walk certificate's end boxes) and prove the stretches between
events clear of the boundary by the existing enclosures. The plan's note that a graze within tolerance
would be missed is the reason for the root box plus a clearance proof, not a reason to keep the uv
intersection. Saving, estimate: 80 % of `trim_parameters`, 16 to 53 M per op. (b) Edge against a
recognised surface by composing the edge (rational) into the implicit F: one univariate polynomial per
span in Bernstein form, roots isolated by the existing certified `bernstein_roots`, parameters on the
surface by the recognised inverse. WP14 did this for rays. Saving, estimate: 80 % of the curve/surface
calls in `boundary_pair`, 17 to 34 M per op.

### 3.4 Pcurves of analytic sections on NURBS quadrics: 160 M Ir on three pairs

Ours: a plane x sphere or plane x cone section is an exact conic, but its pcurve on our NURBS sphere or
cone is fitted (`analytic_side_pcurve` -> `certified_run_curve`: samples, quintic proposals, then
`same_parameter` as acceptance, refined on failure). 4 2 1 0: 7 pcurves, 89 M per op, of it 53 M in
`same_parameter`; 3 2 5 0: 1 pcurve, 71 M; 6 2 2 0: 2 pcurves, 106 M. Then `brep_section::paired`
certifies the trimmed pieces of the same curves again (4 2 1 0: 12 calls, 38 M), because a trimmed piece
is a different curve to the memo.

OCCT: plane x sphere is a `IntPatch_GLine` circle; its pcurves come from `ProjLib` on the analytic sphere,
11 M per op for all seven on 4 2 1 0 including the face/face bookkeeping, with no acceptance proof (the
tolerance check comes later, 39 M, and is an estimate).

What we can adopt: let a certificate on [a, b] cover any piece trimmed from it: trimming re-expresses the
same polynomial on a sub-interval, and the rounding of the new control points has a bound in closed form;
add that bound to the margin the certificate stored. Saving, estimate: all of `paired` on these pairs
(38 M on 4 2 1 0, 8 M on 3 2 5 0 and 6 1 7 0) plus half of the pullback fit if the first proposal is
accepted more often (WP12's "certified on controls" applies to the plane side only). Total 44 to 83 M on
the three pairs with analytic sections, small elsewhere.

### 3.5 Fixed overhead that OCCT does not pay

| per op, M Ir (calls) | 6 2 2 0 | 1 2 1 0 | 4 2 1 0 | 5 3 2 0 | 2 2 1 0 | 1 5 4 0 | 3 2 5 0 | 6 1 7 0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `is_valid` of curves, surfaces, models | 51.1 (52 989) | 14.3 (21 405) | 24.8 (33 418) | 30.4 (34 675) | 1.0 (1 245) | 26.6 (29 492) | 19.1 (21 375) | 11.2 (27 916) |
| cell boxes of `SurfaceSurfaceField` | 15.3 | 4.6 | 0 | 8.2 | 6.5 | 8.2 | 4.6 | 2.8 |
| heap (malloc, free), share of instructions | 5.0 % | 6.2 % | 8.3 % | 5.2 % | 12.2 % | 5.8 % | 6.0 % | 9.6 % |
| OCCT heap, share of instructions | 6.6 % | 7.4 % | 9.5 % | 5.4 % | 22.3 % | 5.5 % | 7.2 % | 9.7 % |

`NurbsSurface::point_at`, `evaluate`, `NurbsCurve::trim`, `get_span_vector`, `is_clamped`, `clamp_end`
validate their object on every call (11 556 `point_at` calls cost 12 M of `is_valid` on 6 2 2 0). The
plan already decided that intermediate validation leaves the release path. `SurfaceSurfaceField` builds
the cell boxes of both surfaces for the four-parameter search even where `boundary_first_seeds` decides
in two parameters: on 2 2 1 0 that is 6.5 of 15 M. Heap use is not a difference: OCCT's share is larger.

### 3.6 Classification and assembly: not a difference, except outliers; WP15 measured

Ours is cheaper than OCCT on five pairs. OCCT classifies split faces by the angle at a shared section edge
(`BOPAlgo_FillIn3DParts` -> `BOPTools_AlgoTools::IsInternalFace` -> `GetFaceOff`, 6 calls, 0.7 M on
6 2 2 0, no ray) and pays for rays in `BOPAlgo_BuilderSolid::PerformAreas` (`PerformInfinitePoint`,
12 to 55 M per op). Ours casts rays for 4 to 8 witness points per op in `select` (0.8 to 2.8 M each) and
for shell orientation in `nest_shells` / `outward`. The latter had outliers: 1 2 1 0 intersection 225 M,
1 5 4 0 union and a-b 75 M, 6 2 2 0 b-a 69 M.

WP15 snapshot (one `brep_classify::Solid` per shell, rays in general directions, box tests before
rays), measured, faces/edges/vertices identical on all 40 results:

| pair | singles before, M Ir (I, U, A-B, B-A) | after | change | xor before -> after |
| --- | --- | --- | ---: | --- |
| 6 2 2 0 | 1096, 1093, 1092, 1170 | 1088, 1091, 1090, 1139 | -1.0 % | 1228 -> 1141 |
| 1 2 1 0 | 525, 302, 302, 305 | 304, 303, 303, 305 | -15.4 % | 545 -> 313 |
| 4 2 1 0 | 282, 296, 296, 276 | 274, 274, 274, 275 | -4.6 % | 311 -> 279 |
| 5 3 2 0 | 659, 656, 655, 666 | 655, 667, 667, 673 | +1.0 % | 700 -> 680 |
| 2 2 1 0 | 15.2, 14.9, 12.0, 20.0 | 14.9, 14.9, 12.0, 19.0 | -2.2 % | 20.2 -> 19.2 |
| 1 5 4 0 | 460, 520, 520, 505 | 457, 446, 446, 500 | -7.8 % | 550 -> 464 |
| 3 2 5 0 | 330, 329, 329, 327 | 330, 329, 329, 327 | 0.0 % | 345 -> 339 |
| 6 1 7 0 | 270, 273, 274, 241 | 269, 270, 270, 241 | -0.8 % | 283 -> 276 |

All eight pairs: -3.2 % of single-boolean instructions. It removes the outliers; on 5 3 2 0 union and
a-b `nest_shells` grows from 5.9 to 17.6 M (general-direction rays against the torus), worth a look by
WP15. Classification at the section edge (OCCT's angle test, with our certified normals and a ray as
fallback) would take most of the remaining 3 to 15 M of `select` per op.

## 4. Ranked changes

Savings are M Ir per single boolean, estimates applied to the measured sub-stage costs above.

| # | Change | 6 2 2 0 | 1 2 1 0 | 4 2 1 0 | 5 3 2 0 | 2 2 1 0 | 1 5 4 0 | 3 2 5 0 | 6 1 7 0 | Files | Risk to results |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| R1 | Walk certificate in two parameters on the recognised implicit (closed form for quadric pairs); four-parameter proof as fallback | 326 | 55 | 0 | 153 | 0 | 63 | 75 | 38 | `intersection.cpp` (`continuation_arcs`, `continuation_arc`, `seed_cell_covered`), `nurbs_implicit.h` | None to the curves (march and fit unchanged, only the proof); soundness at seams, poles, apex and tangency, where the gradient enclosure contains zero and the fallback runs |
| R2 | Face split trusts what the section stage proved: no self-intersection proof of certified cuts and original edges, no same-family cut pairs, vertex membership by node identity | 131 | 46 | 14 | 81 | 0 | 41 | 27 | 17 | `split.cpp` (`compute_spans`, `self_events`, `compute_graph`), `brep_boolean.cpp` (`partition`, `FaceCut` flags), `brep_section.h` | Low if flags are only set from certificates; output identical |
| R3 | Section trimmed from the 3D edge/face events with root boxes and clearance proofs instead of uv curve/curve | 25 | 16 | 27 | 53 | 0 | 53 | 16 | 35 | `brep_section.cpp` (`trim_parameters`, `support_curves`, `boundary_pair`), `curve_intersection.cpp` | Medium: grazes within tolerance need the clearance proof; keep the uv route as fallback |
| R4 | Edge against a recognised surface by composition into its implicit and Bernstein roots | 32 | 17 | 32 | 29 | 0 | 28 | 19 | 34 | `curve_surface_intersection.cpp` (`intersect`), `nurbs_implicit.h`, reuse of `surface_ray::Form` | Low to medium: tangential contact; general route as fallback |
| R5 | Certificate of a pcurve inherited by its trimmed pieces (rounding bound of the trim); fewer refits in the analytic pullback | 53 | 8 | 83 | 1 | 0 | 4 | 44 | 8 | `brep_section.cpp` (`paired`), `intersection.cpp` (`certified_run_curve`), `nurbs_memo.h`, `curve_surface_intersection.cpp` | Low: the inherited bound is a proof; margins stored with the certificate |
| R6 | Validation out of the evaluators (input checked once, result once) | 49 | 13 | 22 | 28 | 1 | 24 | 17 | 10 | `nurbscurve.cpp`, `nurbssurface.cpp` (`point_at`, `evaluate`, `trim`, `get_span_vector`, ...) | Low; keep in debug and test builds |
| R7 | Cell boxes of `SurfaceSurfaceField` only when the four-parameter search runs | 14 | 4 | 0 | 7 | 6 | 7 | 4 | 3 | `intersection.cpp` (`SurfaceSurfaceField`, `surface_cell_boxes`) | None |
| R8 | Split faces classified at a shared section edge by certified normals, ray as fallback | 15 | 4 | 2 | 11 | 3 | 6 | 4 | 3 | `brep_boolean.cpp` (`select`), `brep_classify.cpp` | Medium: tangent faces at the edge decide nothing and fall back |
| R9 | WP15 (measured snapshot) | 11 | 55 | 13 | -6 | 0 | 39 | 0 | 2 | `brep_assemble.cpp`, `brep_boolean.cpp`, `brep_classify.cpp` | Running; results identical in the snapshot |

## 5. What parity per single boolean takes

| M Ir per single boolean | 6 2 2 0 | 1 2 1 0 | 4 2 1 0 | 5 3 2 0 | 2 2 1 0 | 1 5 4 0 | 3 2 5 0 | 6 1 7 0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ours now | 1113 | 359 | 287 | 659 | 16 | 501 | 329 | 264 |
| OCCT | 475 | 198 | 114 | 424 | 4 | 362 | 193 | 147 |
| ours after R1 to R9 (estimate) | 457 | 139 | 95 | 303 | 6 | 237 | 123 | 116 |
| ratio after / now | 0.96 / 2.34 | 0.70 / 1.81 | 0.83 / 2.52 | 0.71 / 1.55 | 1.39 / 3.7 | 0.65 / 1.38 | 0.63 / 1.70 | 0.79 / 1.80 |
| smallest set to reach an instruction ratio of about 0.9 | all of R1 to R9 (0.96) | R1 to R4, R9 (0.86) | R2 to R6, R9 (0.84) | R1, R2, R3 (0.88) | not reached (R6 to R8 give 1.4; 2 ms in all) | R1, R2, R3, R9 (0.84) | R1, R2, R3, R5 (0.87) | R1 to R4, R6 (0.88) |

Read with the instruction-per-second factor of section 1 (about 1.15): 6 2 2 0 at 0.96 in instructions
is about 1.1 in time; it needs everything above plus some of the fixed overhead or WP7's per-span cache.
R1 and R2 alone (1 067 M over the eight pairs, 66 % of the gap) bring 5 3 2 0 to 1.00, 1 5 4 0 to 1.10
and 3 2 5 0 to 1.18 in instructions. Sphere x sphere stays slower in ratio and is 2 ms against 1 ms in
absolute terms: what is left is the empty-pair proof in two parameters (1.1 M), two classification rays
against a sphere and one orientation ray, against OCCT's closed-form "no section" for two spheres.

Where a certificate is the cost and stays a cost after R1 to R9 (estimate): the agreement certificate
(28 to 118 M per op, already at or below OCCT's tolerance estimate), the walk certificate's remaining
20 % (10 to 80 M), root boxes at section ends. OCCT pays instead for its swarm search and for walking
torus pairs; in instructions the two policies end up close once the repeats are gone.

## 6. Raw data

`$S = /tmp/claude-0/-home-user-wood-research/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad`

| What | Where |
| --- | --- |
| callgrind, one dump per operation (`.out.2` intersection ... `.out.6` xor, `.out.1` setup) | `$S/study2/ours_<pair>.out.*`, `occt_<pair>.out.*`, `wp15_<pair>.out.*` |
| drivers and binaries | `$S/study2/src/ours_cg.cpp`, `occt_cg.cpp`; `ours_cg_main`, `ours_cg_wp15`, `occt_cg`, `ours_time`, `occt_time` |
| stage tables per pair and operation | `$S/study2/stage_{ours,occt,wp15}_<pair>.md`, `perpair.md`, `match_ours.md`, `match_wide.md`, `project.md` |
| back-to-back timing | `$S/study2/timing/{ours,occt}.txt` |
| WP15 snapshot | `$S/study2/wp15_snapshot.diff`, `$S/study2/wp15src/` |
| analysis scripts | `$S/study2/tools/` (`cg.py` parser, `stages.py`, `match.py`, `project.py`, `tree.py`, `callers.py`, `callees.py`, `sub.py`, `subo.py`) |
