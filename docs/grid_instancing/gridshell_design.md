# Gridshell v3 - asymptotic lamella gridshells, design

Template: `wood/src/templates/shells/lamella_gridshell.h`, example `wood/examples/templates_gridshell.cpp`.
Sources: Wang, Almaskin, Pottmann, *Computational design of asymptotic geodesic hybrid gridshells via
propagation algorithms*, CAD 178 (2025) 103800, code github.com/wangbolun300/WebsViaPropagation; Schling,
*Repetitive structures* (TUM dissertation, 2018); Bowerbird (Oberbichler) for curve tracing. The TU Wien and
TUM PDFs were not reachable from the cloud session that wrote this (egress blocked); the paper notes below
come from the brief's summary, the WebsViaPropagation README and the published work as known.

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
guide curves to steer AGG. Then a **global optimisation** E = E_c + l_fair E_fair + l_appro E_appro by
Levenberg-Marquardt: E_c the squared constraint residuals above, E_fair second differences along each
polyline, E_appro squared distance to the reference surface (or boundary curves). The first curve must be
free of inflection points, since at an inflection the asymptotic direction degenerates.

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

- **One tracer over a `Field`.** `SurfaceField` works in (u, v) exactly as before; `MeshField` works in xyz on
  a triangle or quad mesh. The field answers directions, tangent, point, normal and a clipped move; RK4,
  seeding along a spine, frames, crossings (now segment against segment in the local tangent plane, with a
  dedupe) and stations are shared.
- **Mesh curvature.** Vertex normals with Max's weights (exact on a sphere); a shape operator per face from
  the turn of the vertex normals along its edges (least squares, Rusinkiewicz 2004), area-averaged per
  vertex; both blended barycentrically. A mesh point is the closest facet point lifted by half of Phong
  tessellation, which puts it on the circle through a chord's ends, so traced curves do not follow the
  facets (with flat facets and area-weighted normals the largest normal curvature was 3e-4 to 1.3e-3 1/mm). Tracing stops at the band of triangles
  touching the boundary, whose one-sided normals are poor (that cut the largest error about four times).
- **BRep boards: `BeamCurved`**, a new wood element (`wood_element_beam_curved.h/.cpp`, `wood_proto.BeamCurved`,
  registered). It holds a central axis (the cubic `NurbsCurve::create_interpolated` through the lamella's
  stations, shared by both boards), the station parameters on it, an up direction per station (the surface
  normal) and one closed cross-section in the station frame (x across, y up). The sweep places the section
  at every station and interpolates one rail per section corner; `Primitives::create_ruled` faces between
  neighbouring rails and two planar caps are assembled into one closed BRep solid with shared rail and cap
  edges and pcurves on the domain sides, so the kernel meshes each face directly. The board kinks only at
  its section's corners and two ends. Studs are `Column` prisms, already BRep. Every element is written as
  BRep, and a saved session loads back as `BeamCurved` (the example checks all 156).
- **Contact mesh.** `BeamCurved`'s mesh is the sweep through its placed sections: every vertex lies on a rail, so it
  is a tessellation of the BRep, and its faces at a crossing are exactly the flats the stud touches. A BRep
  tessellation by the kernel's adaptive grid lost 3 of 25 iso contacts (faces straddling the straight run)
  and was dropped for contacts.

## 4. Numbers (example, Release, this cloud box)

| scene | boards | mesh H share | studs touching 4 | max k_n 1/mm | unrolled dev mm | face tilt deg | overlap |
|---|---|---|---|---|---|---|---|
| asymptotic surface 10 m | 36 | - | 47 / 47 | 9.11e-08 | 0.004 | 0.0478 | 0 |
| iso surface 6 m | 20 | - | 25 / 25 | 1.43e-04 | 312.899 | 0.0025 | 0 |
| minimal saddle disk 10 m | 36 | 0.0096 | 41 / 41 | 4.63e-05 | 1.211 | 0.0746 | 0 |
| catenoid annulus 6 m | 32 | 0.0013 | 46 / 46 | 4.21e-05 | 7.218 | 0.6239 | 0 |
| Enneper disk 9 m | 32 | 0.0238 | 40 / 40 | 1.14e-04 | 12.345 | 0.4547 | 0 |

H share = max |k1 + k2| / sqrt(2 (k1^2 + k2^2)) off the boundary band (0 minimal, 1 sphere). Face tilt =
angle between a side face's ruling halfway between two sections and the averaged normal; on the twisting
mesh lamellas it is the ruled face's own twist between stations. The mesh k_n is a max; the median on the
Enneper lamellas was 7e-6 (measured before the boundary band). The residual peaks sit at the straight run past a stud and at lamella ends.

## 5. Recommended algorithm

**Surfaces (NURBS).** Keep the (u, v) RK4 tracer: exact, fast, 9e-8 1/mm. Add: seeding from a user curve
instead of the centre spine; stop at inflection points of the first curve (K -> 0).

**Meshes.** Two stages, the second optional:
1. *Direction-field tracing* (done): robust, any topology, good to ~1e-4 1/mm max, 1e-5 median on 3-4k
   triangle meshes. Seeds: along a spine of the other family; on an annulus the families spiral and cover
   most of it from one spine.
2. *Discrete A-net optimisation* (next): take the traced polylines, resample them to a quad web with
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
Gridshell { top, bottom /*Board*/, studs /*Column*/, frames };
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
