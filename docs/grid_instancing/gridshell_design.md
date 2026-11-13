# Gridshell v3 - asymptotic lamella gridshells, design

Template: `wood/src/templates/shells/lamella_gridshell.h`, example `wood/examples/templates_gridshell.cpp`.
Sources: Wang, Almaskin, Pottmann, *Computational design of asymptotic geodesic hybrid gridshells via
propagation algorithms*, CAD 178 (2025) 103800, code github.com/wangbolun300/WebsViaPropagation; Schling,
*Repetitive structures* (TUM dissertation, 2018); Bowerbird (Oberbichler) for curve tracing. The Wang,
Almaskin, Pottmann paper was read in full (all 15 pages, text and figures) from the copy petras uploaded;
section 1's paper notes and the net in section 3 follow it, equation numbers are the paper's. Schling's
dissertation was not reachable; the **Schling** paragraph is unverified background.

## 1. Key ideas

**Asymptotic curves.** On a surface with unit normal n and second fundamental form
II(d, d) = L du^2 + 2 M du dv + N dv^2, a direction d is asymptotic when II(d, d) = 0, i.e. its normal
curvature k_n(d) = II(d, d) / I(d, d) vanishes. Real solutions exist only where K = (LN - M^2) / (EG - F^2) <= 0;
with H the mean and K the Gaussian curvature, the two asymptotic directions make the angle
theta with cos(theta) = -H / sqrt(H^2 - K) (the code's `spread`), symmetric about the principal directions. On a
minimal surface (H = 0) they are orthogonal everywhere and bisect the principal directions.

**Why they matter for timber.** A strip standing on the surface normal along a curve bends about its strong
axis by k_n and about its weak axis by the geodesic curvature k_g, and twists by the geodesic torsion t_g.
Along an asymptotic curve k_n = 0, so an upright board bends only about its weak axis and **unrolls to a
straight flat strip**; along an asymptotic curve t_g = +-sqrt(-K), so the board twists. Both are cheap for a
thin board, which is why straight flat lamellas can be bent and twisted on site (Schling). Along a geodesic
k_g = 0 and a tangential strip (lying in the tangent plane) is the one that unrolls straight.

**Discrete conditions (journal paper).** For a polyline p_i with vertex normals n_i:
- asymptotic: n_i . (p_{i+1} - p_i) = 0 and n_i . (p_{i-1} - p_i) = 0 - the osculating plane contains the normal
  plane's complement, i.e. the curve's binormal lies in the tangent plane;
- geodesic: n_i . b_i = 0 with b_i the discrete binormal (p_{i-1} - p_i) x (p_{i+1} - p_i) normalised - the
  osculating plane contains the normal.

**Webs.** Three families on one surface (AAG, AGG, GGG) form a triangular web; two families (AA) form the
quad web built here. The paper computes webs by **propagation**: from an initial strip (two neighbouring
polylines) the next polyline is solved row by row so that the new quads satisfy the family conditions, with
guide curves to steer AGG. Then a **global optimisation** E = E_c + l_fair E_fair + l_appro E_appro (Eq. 11)
by Levenberg-Marquardt to E_c ~ 1e-5: E_c the squared constraint residuals above with the normals as extra
unknowns (Eq. 3: unit, orthogonal to two curves' tangents), E_fair second differences along each polyline
(Eq. 8), and E_appro the squared distance to the **first strip** only (Eq. 10) - the paper has no reference
surface. The first curve must be free of inflection points (a third asymptotic direction, only at flat
points). The gridshell is extracted from the inner vertices; each strip's medial line is a web polyline and
passes straight through every node: nothing at a node is straightened or frozen (Figs. 1-3).

**Schling.** Lamellas are pairs of timber or steel boards with a gap, held apart by spacers; the node is a
stud passing through both layers, which suits the AA crossing because both families are normal to the
surface there; AG joints mix an upright and a tangential strip. Design surfaces are minimal (Enneper, the
catenoid-like annulus, helicoid patches) because both asymptotic families then cross at 90 degrees and are
evenly spread.

## 2. Critique of the template before v3 (wood `a286722`)

- Boards were `Beam` sweeps: a mesh with a section ring at every station, drawn as a ladder of rings, and
  one quad band per segment - faceted, not the smooth board petras asked for.
- Only NURBS surfaces: no way to explore topologies (annulus, disk with holes) that a single untrimmed patch
  cannot carry.
- Tracing, crossings and frames all lived in (u, v); nothing was reusable on a mesh.
- Good: the RK4 tracer is accurate (9e-8 1/mm normal curvature), studs are exact hexagons touching four
  boards, contacts and clash are verified.

## 3. What v3 does

- **One tracer over a `Field`.** `SurfaceField` in (u, v); `MeshField` in xyz on a triangle or quad mesh
  (Max-weight vertex normals, per-face shape operators averaged per vertex, barycentric blending, the point
  lifted by half of Phong tessellation, triangles bucketed in a grid for the closest point, tracing stopped at
  the band of triangles touching the boundary). RK4 steps, seeds along a spine of the other family.
- **A discrete net, as in the paper.** A node at every crossing, every traced sample between crossings a
  vertex of its own lamella. An asymptotic net is optimised by block-coordinate descent on Eq. 11 with
  carrier closeness in place of E_appro (we start from a carrier): node normals in closed form as the best fit
  to the node's star (both lamellas share it: the A-net condition), then positions by Jacobi-preconditioned
  least squares over Eq. 1 at both ends of every edge, fairness (Eq. 8, weight 1e-3), carrier distance
  (0.1) and damping (1e-3); 30 sweeps. The optimised net is kept only when it lowers the residual (on the
  exact NURBS tracing it does not, so that net stays as traced). Iso nets are never optimised.
- **Boards: `BeamCurved`**, a wood element (`wood_element_beam_curved.h/.cpp`, `wood_proto.BeamCurved`,
  registered): central axis the cubic through the lamella's net vertices, the vertex normal as up at each,
  one closed section; swept to one rail per section corner, ruled faces between rails, planar caps, one
  closed BRep. Boards are continuous and twist through every node (the v3 first cut straightened them for a
  gap either side of each stud and froze the twist there - the "broken" nodes).
- **Studs** on the shared node normal: exact at the node section (<= 0.07 mm); away from it the boards
  twist against the straight prism by twist x distance x radius (reported, 0.2 mm on the surface, 2-3 mm on
  the 10-15 deg/m meshes).

## 4. Numbers (example, Release, this cloud box, 2 min 40 s)

| scene | net residual traced / optimised | twist deg/m | max k_n 1/mm | unrolled dev mm | stud fit at node mm | twist mismatch mm | overlap |
|---|---|---|---|---|---|---|---|
| asymptotic surface 10 m | 3.2e-06 / kept traced | 2.6 | 1.99e-08 | 0.002 | 0.000 | 0.205 | 0 |
| iso surface 6 m | 4.4e-03 / not optimised | 0.2 | 8.71e-05 | 312.899 | 0.000 | 0.024 | 0 |
| minimal saddle disk 20 m | 2.9e-03 / 7.1e-05 | 9.2 | 1.87e-06 | 2.630 | 0.058 | 2.518 | 0 |
| catenoid annulus 20 m rings | 2.4e-03 / 1.3e-04 | 13.9 | 2.60e-06 | 28.269 | 0.073 | 3.326 | 0 |
| Enneper disk 30 m | 4.9e-03 / 1.3e-04 | 14.5 | 2.68e-06 | 40.719 | 0.054 | 2.344 | 0 |

Net residual = max |n . e| / |e| over both ends of every edge. The mesh normal curvature fell from 4e-5 -
1.1e-4 (traced lamellas, v3 first cut) to ~2e-6. The catenoid tracing is correct (each spiral keeps
theta +- w constant to 0.015 rad) and covers 262 of 360 degrees from one spine.

## 5. Recommended algorithm

**Surfaces (NURBS).** Keep the (u, v) RK4 tracer: exact, fast, 9e-8 1/mm. Add: seeding from a user curve
instead of the centre spine; stop at inflection points of the first curve (K -> 0).

**Meshes.** Two stages, the second optional:
1. *Direction-field tracing* (done): robust, any topology, good to ~1e-4 1/mm max, 1e-5 median on 3-4k
   triangle meshes. Seeds: along a spine of the other family; on an annulus the families spiral and cover
   most of it from one spine.
2. *Discrete A-net optimisation* (done, section 3; still to do: a true Levenberg-Marquardt with the normals
   as joint unknowns, which should reach the paper's 1e-5): take the traced polylines, resample them to a quad web with
   vertices at the crossings, and minimise E = E_c + l_fair E_fair + l_appro E_appro with
   E_c = sum (n_i . (p_{i+-1} - p_i))^2 over both families, the normal n_i the unit normal of the web vertex
   (cross product of the two diagonals), E_appro the squared distance to the mesh (closest point, Phong
   lifted), by Gauss-Newton / Levenberg-Marquardt. This removes the field's discretisation error at the
   nodes, where it matters for the stud, and is the paper's method. Propagation from a strip is the
   alternative when there is no reference surface.

**Minimal meshes.** Cotangent Laplacian relaxation with a fixed boundary (done for the disk, 400 sweeps,
H share 0.01), or parametric (catenoid, Enneper, helicoid, Scherk). A stable catenoid needs z / c < ~1.2 per
half; the example uses 1.3 without relaxing it.

## 6. Fabrication geometry

- Board = four rails + four ruled faces + two caps. Unrolled blank: the centre line's geodesic curvature
  integrated gives the plan curve of the flat board (straight within the unrolled deviation above); the
  height is constant. Export the rails and the unrolled outline per board.
- Twist per metre = t_g = sqrt(-K); check it against the board's allowed twist before fabrication.
- Stud: hexagon of three flat pairs `gap` apart, length spacing + height + 2 overrun, drilled for a through
  bolt along the normal; one stud type per crossing angle band.
- Crossing: both layers straight for `gap` either side, so the stud flats are planar contacts.
- Ends: one `gap` past the last trace point on the tangent; cut square to the tangent.

## 7. Example scenes (3-5)

1. Asymptotic saddle surface 10 m (reference, exact).
2. Iso-curve saddle 6 m (the counter-example: 313 mm unrolled deviation).
3. Minimal disk relaxed in a skew saddle boundary 10 m.
4. Catenoid annulus between two 6 m rings (spiralling families, a closed topology no single patch covers).
5. Enneper disk 9 m (orthogonal families, a round boundary). Next: helicoid strip, Scherk tower, an AG web.

## 8. Minimal API

```cpp
Gridshell::from_surface(const NurbsSurface&, int curves /*0 iso, 1 asymptotic*/, int count_top, int count_bottom, const Lamella&);
Gridshell::from_mesh(const Mesh&, int count_top, int count_bottom, const Lamella&);   // asymptotic
Gridshell { top, bottom /*BeamCurved*/, studs /*Column*/, frames };
BeamCurved(points, directions, section) { axis, parameters, directions, section; sections(); rails(); element_geometry_brep(); }
```
Next: `from_mesh(..., const Polyline& seed)` for a user spine, and `Gridshell::optimise()` for stage 2.

## 9. Kernel candidates (session_cpp)

- `compute_asymptotic(l, m, n)` - asymptotic directions of a quadratic form; `NurbsSurface::asymptotic_directions(u, v)`.
- `MeshField` pieces: `Mesh::vertex_normals_max()`, `Mesh::shape_operators()` (per-vertex tensor),
  `Mesh::closest_point` with barycentrics (brute force now - needs the AABB tree), Phong-lifted point.
- `BRep::from_rails(rails)` - a closed solid from n corner rails, ruled faces, planar caps (the `BeamCurved` sweep).
- `NurbsCurve::create_interpolated(points, parameters)` - explicit parameters, so several rails share them.
- `Mesh::relax_minimal(fixed, sweeps)` - cotangent Laplacian relaxation.
- A generic RK4 field tracer over a surface or mesh (Bowerbird's role).

## 10. Left

- Stage-2 A-net optimisation on meshes (section 5); AG and AAG webs; seeding from a user curve.
- `MeshField::compute_foot` is brute force: 34 s for the five scenes, almost all of it mesh queries.
- `BeamCurved` has no cuts and takes no part in the beam joinery (axis contacts) yet; face contacts work.
- Screenshots of the new scenes (`templates_gridshell.png`) are to be retaken locally.
