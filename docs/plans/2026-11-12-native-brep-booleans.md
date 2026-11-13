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

## Measured after the fixes

| Suite | Result |
| --- | --- |
| `brep_boolean_test` | 62/62 |
| `brep_test` | 72/72 |
| `intersection_test` | 115/115 |
| `brep_section_test`, `surface_section_test` | 25/25, 23/23 |
| thicken, hollow, offset, tessellation | 15/15, 11/11, 14/14, 7/7 |
| whole suite, before the last two fixes | 1570/1571; the one failure reads the bunny from `session_data`, not checked out here |
| fuzz sweep, 49 ordered pairs, seeds 1 and 2, generic poses | 96/98 |
| fuzz sweep, same, axis-parallel poses | 98/98 |

On main the first generic sweep passed 68 of 98 pairs. That run used an earlier draft of the driver with other random cases and counted an exceeded volume budget as a failure, so the two numbers are not the same measurement.

## Open, in order

1. **Self intersection of a fitted pcurve** - an axis-parallel plane through a cone gives a
   hyperbola whose cone pcurve is fitted as 60 quintic pieces; the arrangement's
   self-intersection check gives up on it. Needs either an exact pcurve for that conic on the
   cone chart or a fit with fewer, smoother pieces.
2. **Torus against cone, one generic pose** - "could not certify walking continuation" with a
   walked point at v = 7e-20, a hair off the seam: the marched route has the same seam-start
   weakness the plane route had.
3. **Sphere against drilled block, one pose, one operation** - "paired fit exceeded its
   refinement budget".
4. **Cone against drilled block, one generic pose** - "Curve intersection exceeded its
   subdivision limit" and "Tangent fan has an unresolved common endpoint".
5. **Exact volume of torus results** - `volume_exact` runs out of its quadrature budget on some
   torus booleans. The solids themselves pass validity and membership probes.
6. Viewer images of the chair results and the Windows/macOS CI run for the branch.
7. Only after these: Rust and Python ports, then offsets.

## Rules kept

- Build with at most four jobs here (four cores), one heavy job at a time.
- No tolerance was relaxed and no test was skipped; every fix has a test that failed before it.
- Commits carry no AI author or trailer.
