# Kernel changes that make the booleans simpler, 2026-11-26

Owner's decision: the kernel may change wherever that makes it better. Each item comes from a defect met while
bringing the booleans to OCCT's results; each is gated by the suite and the scoreboard (key, subset: equal by counts,
equal by geometry, draws correctly).

1. One validity check, `brep_check`, as OCCT's BRepCheck: per vertex, edge, wire, face, shell and solid a named
   status (vertex off its edges, edge off its pcurves beyond tolerance, pcurve self-crossing, loop open in uv
   modulo the periods, loop orientation, face boundary on its own seam, tolerance out of proportion, edge used an odd
   number of times, shell open or not orientable, solid inside-out). `is_valid`, the boolean report, the mesher's
   refusal and the scoreboard all read it. Every boolean result is checked; a result that fails is reported, never
   returned as good.
2. Native interface on `Surface`, `Curve`, `Curve2d`, so no consumer converts to NURBS for an analytic entity:
   bounding box of a trimmed piece, ray and line hits, curve/curve and curve/surface intersection dispatch (closed
   form where it exists, numeric otherwise), closest point with all solutions, exact arc length and area elements.
   Then, consumer by consumer: point classification, the numeric steps of `bop`, `volume_exact`, `is_valid`, the
   mesher. `as_nurbs()` remains for export and the old pipeline only.
3. Healing at read, one explicit step after the STEP reader (OCCT's ShapeFix): edge and pcurves made to agree,
   tolerances set from measured gaps, missing seams, shell orientation, faces on one surface sharing one pool
   entry. Booleans then assume a consistent part.
4. Per-face queries: exact area, volume share, closest point, point in face in uv.
5. History on results: for each result face and edge, the operand face or edge it came from.
6. The old pipeline (`brep_boolean`, `brep_section`, `split`, `brep_assemble`, `brep_classify`) is removed once
   `bop` equals or passes it on the 75 primitive rows, the 70 chairs and the full 2705 real booleans.
7. Python and Rust ports of the types and BRep changes, after the C++ settles.

Order: 1 and 2 first (wrong results cannot slip through; the largest source of defects goes), then 3 and 4, then 6.
