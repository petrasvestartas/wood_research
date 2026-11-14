# Native BRep booleans in session_cpp: plan and status, 2026-11-12

Work branch: `claude/clever-ramanujan-dkse3b` in `session_cpp`
([petrasvestartas/session_cpp#21](https://github.com/petrasvestartas/session_cpp/pull/21)).
The detailed OCCT-audited record stays in `session/session_cpp/docs/native_brep_plan.md`.

## Where the code stands

`session_cpp` main (`3326d89b`) already holds a complete native pipeline, no OCCT at run time:

1. `brep_section::interferences` - every face pair: surface/surface sections with a pcurve on
   both faces, coincident faces, boundary events, shared nodes.
2. `brep_boolean::partition` - original edges split at the events, each face split by its cuts
   (`split::split_brep_face_by_pcurves`).
3. `brep_boolean::select` - one interior witness per region classified against the other solid
   (`brep_classify::point`), truth table per operation, coincident faces by normal sense.
4. `brep_assemble::assemble` - shared edges, shells, cavities, orientation.

Measured on Linux in this session, on main before any change:

| Suite | Result |
| --- | --- |
| `brep_boolean_test` | 58/58, all seven Rhino families included |
| `brep_test` | 72/72, `Rhino Freeform Chairs Booleans` (five operations) included |

So the fixtures given so far all pass on main. The six tests that failed in the 6 November
qualification pass too: main moved on after that snapshot.

## The recovery branch

`codex/native-brep-recovery-20261112` (parent `0a113afc`) holds 392 patch packets and receipts
from the 6 November work on original curve-use ranges. They apply to a tree that main has since
diverged from, and their own receipts list two red tests and unqualified later packets. They are
not applied here. Reason: main passes what that work was built to fix. The one idea worth
carrying forward is the finding itself - never delete a positive edge because its world trace
fits a vertex cap - and it should come back as a targeted change with its compressed-surface
counterexample as the test, when a failing case needs it.

## Reference kernels

| Repository | Use here |
| --- | --- |
| [Open-Cascade-SAS/OCCT](https://github.com/Open-Cascade-SAS/OCCT) at `d3056ef8` | The algorithmic reference already audited in `docs/native_occt_*`: `BOPAlgo_PaveFiller` (interferences before face building), `BOPAlgo_BuilderFace`, `BOPAlgo_BuilderSolid`, `IntTools_FaceFace`, `IntPatch`, `BRepClass3d`. LGPL: read, never copied without notice. |
| [ricosjp/truck](https://github.com/ricosjp/truck) (`truck-shapeops`) | A small NURBS BRep boolean in Rust: loops store, face division, classification by intersection curves. Readable end to end, useful when the Rust port starts. |
| [andymai/brepkit](https://github.com/andymai/brepkit) | A from-scratch Rust kernel with a General Fuse boolean after OCCT's design, benchmarked against OCCT. |
| [solvespace/solvespace](https://github.com/solvespace/solvespace) (`src/srf`) | Compact C++ NURBS shell booleans: surface/surface curves, trim splitting, shell classification by ray casting. A good map of the failure modes a small kernel meets. |
| [BRL-CAD/brlcad](https://github.com/BRL-CAD/brlcad) (`src/libbrep`) | openNURBS-based boolean and surface/surface intersection by subdivision, the same data model as this kernel's NURBS classes. |
| [elalish/manifold](https://github.com/elalish/manifold) | Mesh booleans only; its symbolic-perturbation treatment of coincidence is the reference for robust selection, not for BRep. |
| [CGAL/cgal](https://github.com/CGAL/cgal) (Nef polyhedra, exact predicates) | Exact arithmetic for the planar case, an oracle for polyhedral inputs. |

## Method: find the gaps by fuzzing, fix one class at a time

Fixed fixtures were green, so a random driver looks for what they miss:
`session_cpp/examples/native_boolean_fuzz.cpp` (CMake option `SESSION_BUILD_BOOLEAN_FUZZ`) builds
a pair from box, cylinder, sphere, cone, pyramid, torus and drilled block, places the second at
random, runs all five operations and checks each result three ways: valid closed solid, volume
identities around the common part, and 150 point-membership probes against the operands.
`examples/native_boolean_fuzz.sh` sweeps all 49 ordered pairs per seed.

Each failure class gets: a reproduction, the cause, a fix in the kernel, a regression test that
is red before and green after, then the full boolean file again.

## Fixed in this session

| Class | Cause | Fix | Test |
| --- | --- | --- | --- |
| Pyramid against any curved solid | A pyramid side is a bilinear patch collapsed at the apex: planar, not affine. The plane routes assumed an affine chart or clamped a closest point when the section left the triangle. | Exact rational pcurve in barycentric form (`triangle_plane_pcurve`), sections cut to the wedge from base to apex (`triangle_clip_ranges`), used in the extrusion/ruling, quadric and general plane routes. | `Pyramid Collapsed Faces Against Tilted Curved Solids` |
| "edge lies entirely inside its vertex tolerance", open edges, missing interior witness | Two section arcs meet on an edge of the other solid; on a sphere their rational pcurves end a hair apart, and `join_cut_ends` skipped rational curves and anything under four uv tolerances. | Ends are joined whatever the weights, from rounding level up. | `Sphere Sections Meeting On An Edge Of The Other Solid` |
| "could not certify walking continuation" on torus and sphere | A short section piece between a knot line and the seam took its period from one sample, which sat on the seam. | The period comes from the middle of the piece's extent. | `Torus Section Dipping Across Its Seam Beside A Knot Line` |
| "trim lost a required original raw event" | A section's world curve and a pcurve hold the same knot one rounding apart; the trim kept each its own. | An exact trim names the cut on all three. | `Section And Pcurve Knots A Rounding Apart` |
| "plane section approximation exceeded its refinement budget" on a torus | A section loop seeded exactly on the tube seam was never cut at its start, so half of its pcurve lay outside the domain, where the surface evaluator extrapolates and the fit can not converge. | The trace is cut at a start on the seam; pieces between two cuts on one point are dropped. | `Surface Plane Loop Seeded On The Torus Seam` |
| "open or inconsistently oriented edge" on a torus against planar faces | A piece end cut on the seam was polished freely afterwards and left the seam by about 1e-8: one piece ended outside the face, the next short of it. | Seam ends are polished along the seam only. | `Surface Plane Pieces End On The Torus Seam` |
| macOS only: "Self intersection has unresolved singular geometry" | A fitted pcurve held two knots one rounding apart; the search could not halve that span. | Spans with no parameter inside are passed over. | `Knot Span One Rounding Wide` |
| "could not certify walking continuation" on torus against cone | A seam crossing was accepted once inside the tolerance, a tolerance along the curve from where it meets the seam. | The crossing is stepped on while a step still halves the gap. | `Surface Surface Torus Cone Crossing Both Seams` |
| "paired fit exceeded its refinement budget" beside a sphere pole | The walk's first step, a quarter of a cell, was never judged and landed across a hairpin of the section. OCCT's `IntWalk_PWalking::TestDeflection` judges every step and halves it when the tangent ahead turns back. | Every step is judged, the first from its own tangent. | `Sphere Section Turning Back Beside Its Pole` |
| "Self intersection ..." then "constant input" on a cone cut parallel to its axis | A seam cut landed one rounding from a sample of the pcurve fit: a span with no width. | Such a sample is dropped before the fit. | `Cone Cut By Planes Parallel To Its Axis` |
| "Curve intersection exceeded its subdivision limit", "Tangent fan ..." on cone against drilled block | An open arc from rim to rim was closed into a loop because its ends lay within the join distance, a cell and a half of a one-span cone. | An arc ending on open sides of the domain is never closed. | `Cone Arc From Rim To Rim Is No Loop` |

## Measured after the fixes

| Suite | Result |
| --- | --- |
| whole C++ suite, Linux | 1580/1581; the one failure reads the bunny from `session_data`, not checked out here |
| `brep_boolean_test` | 67/67, the seven Rhino families included |
| `brep_test` | 72/72, the five chair operations included |
| CI at `f778d5db` | green on Linux, Windows and macOS ARM64 |
| fuzz sweep, 49 ordered pairs, seeds 1, 2 and 3, generic poses | 147/147 valid in all five operations |
| fuzz sweep, same, axis-parallel poses | 147/147 valid in all five operations |

In each mode one pair, drilled block against torus, needs about 280 s and misses the sweep's
240 s limit; run alone it passes.

On main the first generic sweep passed 68 of 98 pairs. That run used an earlier draft of the driver with other random cases and counted an exceeded volume budget as a failure, so the two numbers are not the same measurement.

## Open, in order

1. **Exact volume of torus results** - `volume_exact` runs out of its fixed work budget of
   200000 on some torus booleans, whose fitted pcurves have hundreds of spans. The solids pass
   validity and membership probes. The budget was held fixed on purpose in the earlier work;
   the two honest ways on are fewer spans in fitted pcurves or a budget that scales with the
   spans of the input, and that is a decision for the owner.
2. **Speed** - drilled block against torus takes 280 s for five operations in one pose.
3. **Viewer images of the chair results** - `session_viewer` is not part of this checkout.
4. Only after these: Rust and Python ports, then offsets.

OCCT at `d3056ef8` was read for two of the fixes above (`IntWalk_PWalking.cxx`, start-point and
`TestDeflection` handling) and for one idea that turned out not to be the cause
(`BOPAlgo_PaveFiller::IsExistingPaveBlock`); nothing was copied.

## Rules kept

- Build with at most four jobs here (four cores), one heavy job at a time.
- No tolerance was relaxed and no test was skipped; every fix has a test that failed before it.
- Commits carry no AI author or trailer.
