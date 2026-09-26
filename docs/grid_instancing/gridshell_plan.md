# Gridshell plan - asymptotic lamella gridshells after Bowerbird, Schling and Pottmann

Sources read in full: Wang, Almaskin, Pottmann, CAD 178 (2025) 103800 (propagation webs); Schling, Wang,
Hoyer, Pottmann, *Designing asymptotic geodesic hybrid gridshells* (CAD 2022 preprint); Bowerbird source
(`Curvature/Path, NormalCurvaturePath, Pathfinder, PrincipalCurvature, CurveOnSurface`).
Code: `wood/src/templates/shells/lamella_gridshell.h`, `wood/examples/templates_gridshell.cpp`, element
`BeamCurved` (`wood_element_beam_curved.h/.cpp`). Branch `gridshell-v3`, PR petrasvestartas/wood#3.

## Rules that do not change

- Lamellas are continuous strips through every node; nothing is straightened or frozen at a crossing.
- Two asymptotic families form an A-net: every vertex star planar, one unit normal per node shared by both.
- Every stage ends with: example exit 0, numbers printed, screenshots (overview + node close-up), commit,
  push. Runtime under 2 min for NURBS stages, under 5 min total. Runs through `tools/run_guarded.sh`.
- No AI trailers in commits; stage named paths only; leave the superproject tree clean.

## Stage 1 - simple NURBS, Bowerbird-exact

- [ ] Lamella = curve on surface: a (u, v) polyline traced by RK4 as `Pathfinder.FindPath` (direction by
      largest |dot| with the last 3D step, clip at boundary, stop on no direction, loop tolerance).
- [ ] Directions by Euler's formula as `FindNormalCurvature`: cos 2a = (2 kn - k1 - k2) / (k1 - k2),
      kn = 0 for asymptotic curves.
- [ ] Seeds are input: uv points, or evenly spaced along a seed curve; no hidden spine.
- [ ] Exact per-lamella metrics as `CurveOnSurface`: normal curvature, geodesic curvature, geodesic torsion
      (Schling Eq. 3: kn = k1 cos^2 p + k2 sin^2 p, tg = (k2 - k1)/2 sin 2p).
- [ ] Board = the lamella's rectifying developable (Schling Sec. 2.2): rulings r = tg t + kg n in the
      Darboux frame, far edge c(t) + w / (r . e3) r; unrolls exactly straight. Report the ruling angle
      atan(tg / kg) against the normal.
- [ ] Stud on the exact surface normal at each crossing; report the fit at the node section (<= 0.1 mm) and
      the twist of the strip against the straight node axis (expected, Schling Sec. 3.4).
- [ ] Scenes: cubic saddle (asymptotic and iso), a hyperbolic paraboloid patch.

## Stage 2 - harder NURBS

- [ ] Surfaces with varying curvature (skewed saddle, NURBS fit of a minimal surface).
- [ ] Several seed layouts; constant normal curvature paths (kn != 0) if cheap.
- [ ] Stop at flat points (K -> 0); the first curve free of inflection points.

## Stage 3 - meshes and discrete A-nets (Pottmann)

- [ ] Initialise: rotational surfaces (catenoid) from ONE traced asymptotic curve, rotated and reflected
      copies (full 360 degrees); general meshes from traced curves or asymptotic directions + quad mesh.
- [ ] Constraints: planar vertex stars n . (v_i - v) = 0, |n|^2 = 1 (Schling Eqs. 6-7).
- [ ] Solver: guided projection, regularised Gauss-Newton on vertices and normals jointly (Schling Eq. 14):
      fairness 5e-4 (5e-3 when far off) -> 0 for the last 2-5 iterations after residual < 1e-6,
      self-closeness 0.01 -> 0, proximity to the surface 0.1 -> 0, damping 0.001. Target 1e-10 or better.
- [ ] Refine: bilinear subdivision of the coarse net, optimise the refined polylines with normals from the
      other polylines ((v- - v+) . n = 0).
- [ ] Strips: C3 quintic spline through the nodes, osculating plane tangent to S at the nodes; boards as
      rectifying developables as in stage 1.
- [ ] Scenes: relaxed minimal disk, catenoid (rotational A-net), Enneper disk.

## Stage 4 - construction and delivery

- [ ] Node as Schling's timber prototype: double slats with spacer blocks leaving gaps, the two families on
      separate levels with a spacer, a bolt or stud through the gaps as a scissor joint.
- [ ] Unrolled strips per board (straight), fabrication list.
- [ ] Docs (`wood/docs/templates.md`, README row, design doc), screenshots, PR #3 description and comment,
      `main_all_datasets` byte-identical if anything under `src/joinery_solver` changed.

## Later, only on request

- Geodesic family and AAG / AGG webs, propagation from a strip (Wang 2025 Eqs. 13-22), guide curves.
