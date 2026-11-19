# BRep geometry types, 2026-11-19

The topology of `BRep` (vertex, edge, wire, face, shell, solid, a tolerance on each, a pcurve per surface) is the
same as OCCT's and stays. What differs from OCCT, SMLib and every production kernel is the geometry under it:

| | ours now | OCCT / SMLib |
| --- | --- | --- |
| surface | always `NurbsSurface`; plane, cylinder, cone, sphere, torus are guessed back from control points on each use | analytic types kept as such, NURBS only for freeform |
| edge curve | always `NurbsCurve` | line, circle, ellipse kept as such |
| pcurve | always `NurbsCurve`, in the rational surface's parameter | 2D line or circle in the true angle and length parameters |
| periodic surface | one fixed seam, domain [0, 1] or knots | periodic: a pcurve lives anywhere modulo the period |
| edge extent | the whole curve; a split copies or refits the curve | one shared curve and a parameter range per edge |

Consequences measured so far: recognition fails on real parts (the bellows' cones); a circle on a rational cylinder
is not a straight pcurve, so edge and pcurve disagree beyond tolerance (the "paired-parameter certificate" and "edge
and pcurve disagree" classes, several hundred failures); every split refits curves and loses accuracy; fixed seams
cut faces and edges where OCCT has none (count differences against OCCT); STEP says CYLINDRICAL_SURFACE and we
throw that away at read time.

Decision, 2026-11-19 (owner): this rewrite comes first. Boolean tuning stops until the kernel stands on these
types; the scoreboard then measures the booleans on an equal base with OCCT and SMLib.

## Types

- `Surface`: plane, cylinder, cone, sphere, torus (frame, radii, semi-angle; true parameters: angle and length;
  periodic in the angle), or NURBS for freeform. One interface: point, derivatives, normal, closest parameter,
  domain, periods, bounds; `nurbs()` on demand.
- `Curve`: line, circle, ellipse (frame, radii; parameter is length or angle), or NURBS; same interface.
- `Curve2d` (pcurve): 2D line, 2D circle or ellipse arc, or NURBS, in the surface's true parameters. On a periodic
  surface a pcurve may lie anywhere modulo the period and cross the seam; no seam edge is forced.
- `BRep`: pools of `Surface`, `Curve`, `Curve2d`. An edge is a curve index and a range `[t0, t1]`; each pcurve use has
  its own range. Split edges share the curve and differ in range only.
- Analytic intersections by closed form: line and conic against plane and quadric, plane against quadric, quadric
  pairs with conic sections, as OCCT's IntAna and SMLib's analytic cases; everything else by the NURBS routes.

Order: types and their tests (standalone); BRep pools, reader, writer, primitives, tessellation, volume on the new
types with old consumers reading `nurbs()`; analytic intersections; `bop` and `bop_ff` on types and ranges; old
pipeline removed when `bop` passes it everywhere. The four steps below are the same work in more detail.

## Change, in steps that each keep the suite green

1. Forms carried, never guessed. Each surface and 3D curve of a `BRep` carries its analytic form when it has one
   (plane, cylinder, cone, sphere, torus; line, circle, ellipse: frame and radii), set by the STEP reader and the
   primitive constructors, kept through transforms, splits and booleans, written back to STEP as the analytic
   entity. `recognize_surface` runs only for surfaces that arrive without one.
2. Ranges. An edge has a parameter range on its 3D curve and on each pcurve; split edges share the curve.
3. Analytic evaluation. Surfaces and curves with a form evaluate, project and intersect by closed form in the true
   parameters (angle, length), periodic where the form is; pcurves on them are 2D lines and arcs. The NURBS is made
   on demand (viewer, export, other kernels).
4. `bop_ff` and the edge/face, edge/edge steps take analytic pairs by closed form (OCCT's IntAna, SMLib's analytic
   cases), freeform by the existing routes.

Python and Rust follow once the C++ types settle. Measured by the same number: real booleans equal to OCCT.

## What the boolean core needs from the types (from the core's present guesses)

1. Surface kind with its axis placement as in STEP (location, axis, reference direction, radii, semi-angle; for a
   plane also whether the placement is right-handed). Parameters in OCCT's units: u the angle in radians from the
   reference direction, v a length (or latitude).
2. The angle origin kept from the file, not moved to a seam edge. OCCT cuts every walked section where it crosses
   u = 0 of either surface and starts closed sections there (the one-vertex differences on round parts).
3. Periods as a property of the surface (2π in u; torus also in v); a face's uv box may run past the period.
4. Pcurves free to cross the seam, and a query "this uv shifted by whole periods into this face's uv box".
5. Seams as data: which edge of a face is its seam and at which u; degenerated edges (poles, apex) with a pcurve.
6. Curve kinds with placement and true parameter: line (origin, direction, length), circle and ellipse (centre,
   normal, X direction, radii, angle). Parameter 0 of a closed section is where OCCT puts its vertex.
7. Edge = shared curve id + range + vertices; a split piece = the same curve id + sub-range.
8. Pcurve = shared 2D curve id + range, with the map from the 3D curve's parameter.
9. Exact 2D kinds for the common cases: line on a plane, cylinder, cone; circle and ellipse on a plane.
10. Closed-form point inversion and distance for every analytic kind.
11. Untrimmed analytic surfaces (a patch that ends short of a loose edge stops sections before the face boundary).
12. Tolerances as OCCT's reader leaves them, the edge tolerance covering the gap to its pcurves on both faces.
13. Surface identity: same surface object, and for analytic kinds an exact "same surface up to parameter shift or
    reversal" test with the relative orientation.
14. Face orientation against the surface normal; handedness of a plane's placement.
15. From face/face: each section as curve + two pcurves with ranges, a closed flag, the parameter origin of a
    closed analytic section; walked curves cut at u = 0 and v = 0 of periodic surfaces.
