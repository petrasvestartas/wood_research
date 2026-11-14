# Real parts: plan, 2026-11-14

The primitive bench is at OCCT's speed per single boolean (2.41 s against 3.13 s over 15 pairs, 60 of 75 rows with
OCCT's topology). Real parts are not. This plan orders the work that makes real, non-primitive BReps load, boolean
correctly and match OCCT's speed. Each package is gated as before: suite, fuzz both modes, primitive bench and new
pairs unchanged, the corpus and complex benches rerun on both kernels with a picture per case.

## Where we stand

| Set | OCCT | ours |
| --- | --- | --- |
| Downloaded corpus, 73 STEP files (`session_data/brep_boolean_bench`) | 72 load as valid solids | 2 load as closed solids |
| Corpus booleans on clean input (forum rebuilds, planar part) | | equal to OCCT, 2.5 to 6 times slower |
| Rhino chairs, 12 poses, 60 booleans (`docs/validation/complex_bench`) | 60 valid | 60 equal to OCCT, 2.3 times slower |
| Twisted freeform pair, 10 booleans | 10 valid | 10 equal, 0.48 times OCCT |
| Timber joinery elements, 785 booleans | 782 valid | 0: input rejected or edge certificate fails |

Defects found and fixed (merging now, after f7d1711e): a wrong classification accepted on an inconsistent operand
(operand check for trims running against the face orientation; rays whose crossings do not alternate count as
undecided), a stack overflow at degree 44 in the implicit edge route.

## 1. STEP reader (running)

Causes, all in `src/file_step.cpp`:
- `.F.` face bounds: edges flipped, loop order not reversed.
- ADVANCED_FACE same_sense `.F.`: face marked reversed but its bounds not reversed (edge order, use orientation,
  seam branches).
- Data section found by `text.find("DATA")`: matches `MATRA-DATAVISION`, `TECHNICAL_DATA_PACKAGING` in the header;
  the file reads as nothing without an error.
- `FACE_SURFACE` not read; faces that cannot be built dropped silently.
- Pcurves built as 48-point polylines over [0, 47]: the parameter does not follow the 3D edge, so the certificate fails
  on the last span (the interval [46/47, 1] in every timber failure, the bellows union).

Done when: every solid OCCT loads also loads in ours, valid and closed, with OCCT's face count, each face's area within
1e-6 and the volume within 1e-9; every edge certified at 1e-7; a picture of the loaded operands per file. Named cases:
NEMA-17 bracket (left plate drawn as a triangle), bellows, timber dowel `elem21_cyl`, joint `joint00`.

## 2. Tolerant input (scoped by the reader's numbers)

If some files are only accurate to their own tolerance (1e-5 to 1e-3 is common in real CAD data), the booleans must
honour a tolerance per edge and vertex, as OCCT does (`BRep_TEdge` tolerance, `BOPAlgo` growing tolerances), instead
of one global 1e-7: certificates measured against the edge's own tolerance, vertices merged within the larger of two
tolerances, result tolerances reported. Started only if package 1 shows loose data in the files themselves.

## 3. Recognising the parts' surfaces

The bellows' 64 cones are not recognised as cones (`recognize_surface` / `fit_cone`), nor `Primitives::cone_surface`
at 1e-6, so they take the general routes. Recognition must cover the surfaces the reader produces from STEP's
CYLINDRICAL_, CONICAL_, SPHERICAL_, TOROIDAL_SURFACE and the parts' B-spline faces that are exactly such surfaces,
in any pose and any parametrisation.

## 4. Freeform sections (running)

The chairs spend 74 to 77 percent of each boolean in the four-parameter seed search, because freeform against
freeform has no recognised side. Route: open arcs from boundary curves against the other surface; loops excluded
where the normal cones of a cell pair have no common direction, else cut by the cell's iso-curves; four-parameter
search only for cells that stay suspect. Target: chair_self at or below OCCT on every operation (now 3 s against 1 s).

## 5. Meshing (running)

`face_meshes` leaves sawtooth needles along trims on spheres and a missing patch in one cavity; `tessellate` throws
or does not finish on some results. Done when every result of both benches meshes closed, each face's area within
the chord error of its exact area.

## 6. Rerun and widen

After 1 to 5: rerun the corpus, the chairs and the timber elements on both kernels with pictures; then the phase
already in the alignment plan (any pose, hard cases: tangency, coincident faces, poles and apexes, slivers), and the
corpus extended with more real parts. Speed work from then on is ranked by the real-part profiles, not the primitives.
