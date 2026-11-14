# Complex in-house BReps: session_cpp booleans against OCCT

The earlier OCCT comparison (`../occt_bench`) used only primitives. This one uses our own models:

- the two Rhino chairs;
- the Rhino twisted pair (the only non-primitive pair in `rhino_booleans`);
- the timber shoring elements in `session_data/elements`.

There are 171 cases with 5 booleans each, run on both kernels: 855 booleans per kernel. Each case has a picture.

- Kernel: `session_cpp` at **f7d1711e**, in its own worktree, Release build (Ninja, `-O3 -DNDEBUG`). The drivers are linked with `fuzz/build.sh`.
- OCCT: 8.0, our own build (Release, shared libraries). OCCT is the oracle only.
- Not committed.

## Verdict

- **Chairs (12 cases, 60 booleans): all 60 booleans succeed and are valid.**
  - Volumes agree with OCCT to between 5e-10 and 2e-8.
  - Face, edge and vertex counts are identical to OCCT in every boolean.
  - Ours is **2.39x slower in total** on the single booleans (81.3 s against 34.0 s); per boolean the geometric mean is 2.32x, and per case it runs from 1.58x to 3.13x.
  - On xor, ours takes 19.4 s against 9.0 s for OCCT's one-fuse CellsBuilder xor (2.15x in total, geometric mean 2.11x) and 70.4 s for OCCT's three-boolean xor (0.28x).
  - Chairs as stored: our volumes match the reference volumes in `native_chair_booleans.cpp` to 5e-9 or better: 310.4983643, 5578.9103242, 2634.2059799, 2634.2059799, 5268.4119598. The solid counts are 2, 1, 2, 1, 3.
- **Rhino twisted pair (2 cases, 10 booleans): all succeed, valid, volumes agree to 3e-10, ours 0.48x of OCCT's time** (ours is faster).
- **Timber elements (157 cases, 785 booleans): not one boolean of ours produced a non-trivial result.** OCCT does 782 of the 785 validly. Three things block us, in this order:
  1. **The STEP reader returns nothing for `schoring_body_start_1.step`** (20 cases, 100 booleans). `parse_step_file` (`file_step.cpp:438`) finds the DATA section with `text.find("DATA")`. In this file that matches inside the header line `FILE_SCHEMA (('TECHNICAL_DATA_PACKAGING'))`, so the reader parses an empty section, returns 0 BReps and reports no error. The other 10 element files use the schema `CONFIG_CONTROL_DESIGN` and load.
  2. **Face orientation as read** (90 cases, 450 booleans refused at the input check with *"Native BRep Booleans require closed oriented solid operands"*). 14 of the 28 element BReps we read are `is_valid()` but not `is_solid()`: edges are used twice in the same direction.
     - The faces that come out wrong are the ones written `ADVANCED_FACE(..., .F.)`. For example, `foot_1` has 8 `.F.` faces (bore cylinders), and the driver repair below flips exactly 8 faces; `body_end_1` has 1 and the repair flips 1.
     - So the reader probably ignores or misapplies `same_sense = .F.`. This is inferred from those counts, not traced in the code.
     - With a **driver-side** repair (`OURS_REPAIR=1`, not kernel code), every one of these BReps becomes `is_solid()` and its volume matches OCCT. The repair flips face uses so every edge is used once each way, keeping the majority of each connected piece as read. The 450 booleans were then rerun (second table).
  3. **Edge/pcurve correspondence of the BReps as read** (the rest).
     - Every element BRep has edges whose pcurve the kernel's own `same_parameter` rejects at 1e-7. These are 2 to 48 pcurves per BRep, almost all on cylindrical faces (`run/pcheck_ours.txt`). The chairs and the twisted solids have none: 108/108 and 24/24 pcurves certified.
     - The gap is between 1e-5 and 1e-3: at 1e-3 most pass.
     - OCCT builds pcurves for the same edges with edge tolerance ≤ 2.7e-7, so the 3D curves lie on the surfaces. The mismatch therefore comes from the **pcurves our STEP reader builds**, not from the data.
     - The booleans then fail mostly in **split**: *"Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance …"* and *"Required edge event lacks an original raw curve/trim law: Certified common-interval point residual …"*. 417 of the 665 boolean failures (130 as read, 287 after repair) carry this "common-interval point residual" diagnostic on an original edge.
     - The rest fail in section: SSI pullback, interferences, boundary events. After the repair, a few also fail in assembly and classification.
     - Raising the boolean tolerance to 1e-4 does not help: elem03_box still fails with the same message.
  - After the repair, 20 of those 450 booleans return. All 20 are trivial: an empty intersection of disjoint operands, or an operand returned unchanged.
    - 16 agree with OCCT in volume.
    - The other 4 also have the right topology. Their volume is off by 0.5% only because `volume_exact` throws on the 3-face, 2-vertex dowel solid (head_0.u0/u6/u7/u8), and the driver then falls back to the mesh volume.

The elements are not exotic: planes and cylinders, with a few B-spline faces in head_0 and body_end_0. Most real cases look like this, so for us **the STEP import of these files is the first thing to fix** (DATA search, `.F.` faces, pcurves on cylinders). The boolean failures on the elements cannot be judged until the operands are right.

### Where our time goes (callgrind, the two slowest booleans of ours)

| boolean | ours wall | callgrind Ir in the boolean | section (`brep_section::interferences`) | of it SSI (`Intersection::surface_surface`) | SSI seeding (`surface_surface_seeds`) | `seed_cell_covered` | marching continuation (`continuation_arcs`) | split + partition (`brep_boolean::partition`) | rest (classify, assemble) |
|---|---|---|---|---|---|---|---|---|---|
| chair_self ∩ | 3.61 s | 23.9 G | 92.4% | 85.2% | 76.8% | 54.0% | 6.3% | 6.2% | ~1.4% |
| chair_pose10 B−A | 2.53 s | 15.2 G | 91.0% | 84.9% | 74.3% | 52.7% | 7.7% | 7.6% | ~1.4% |

About three quarters of each boolean is the SSI seed search. Its cost is mostly the interval Bézier bounds of seed cells (`seed_cell_covered` → `nurbs_interval::surface_bounds` / `blossom`). Marching itself is under 8%, and split plus partition about 7%.

Our `volume_exact` on the result is not timed in the tables. It costs more than the boolean itself: 14.1 G and 29.0 G Ir, against 0.03 s for OCCT's GProp.

## How it was run

- **Operands.**
  - Our side reads every STEP file with `file_step::read_file_step_breps`; each returned BRep is one operand.
  - OCCT reads the same file with its STEP reader. OCCT 8.0.1 through OCP is used for reading only, because the self-built OCCT has no TKDESTEP (it needs TKXCAF, which needs Visualization). The shapes are written as exact `.brep` files and read by the C++ driver (`drivers/occt_cx.cpp`), which links the self-built OCCT 8.0.
  - Where OCCT splits one of our BReps into several solids (foot_0.u1 and head_0.u4: two disjoint pieces in one shell), the OCCT operand is the compound of those solids (`drivers/map_units.py`, `raw/units.txt`).
- **Moves.** Every rotation or shift is one rigid 3x4 matrix, generated once (`drivers/gen_cases.py`, seeded) and given to both kernels.
- **Cases.**
  - Chairs: as stored, at tolerance 1e-6 as in `native_chair_booleans.cpp`; the 10 poses rotate chair B by up to ±90° about a random axis through its box centre and shift it by up to ±1 unit; chair A against itself rotated 25°.
  - Twisted pair: as stored, and with B rotated 7°.
  - 38 joint pairs: solids of one assembly whose boxes touch or overlap (body_start with foot, body_end with head, per variant), as stored and with B rotated 2–6° about its centre.
  - 27 elements, each against: itself rotated 15° about its centre; a box slab across its longest axis, 0.3 of its length thick, tilted 6°; and a cylinder through its thinnest axis, off centre, radius 0.25 of the middle extent.
  - Kernel tolerance is 1e-7 except for the chairs.
- **Processes and limits.** One process per boolean, ours then OCCT back to back. Limit 120 s, the process killed at 180 s, 6 GB address-space cap. No boolean of ours timed out or crashed; the slowest took 3.6 s.
- **Validity.**
  - Ours: `is_valid() && is_solid()`, or an empty result.
  - OCCT: `BRepCheck_Analyzer`.
- **Volumes.**
  - Ours: `volume_exact()`, falling back to the mesh `volume()` (marked "(mesh)") when it throws.
  - OCCT: `BRepGProp::VolumeProperties(…, 1e-9)`.
  - They "agree" when `|ours − OCCT| ≤ 1e-6 · max(|OCCT|, 1e-3 · OCCT union volume)`.
- **Times.**
  - Wall time of the boolean call only, one run each. Load, the validity check and the volume are not included.
  - The machine has 4 cores and was shared with another agent's STEP runs (load average 7–12) during the whole run. Ratios from adjacent runs are fair; absolute times are noisy.
  - Ratios use only booleans where both kernels returned. "Geo-mean" is the geometric mean of the per-boolean ratios; "total" is the sum of ours over the sum of OCCT's.
  - Single booleans (∩ ∪ A−B B−A) are reported separately from xor.
  - For xor, OCCT appears twice: **CellsBuilder**, one general fuse that keeps the cells in exactly one argument (used for the ratios and pictures), and **3-bool**, `Fuse(Cut(a,b), Cut(b,a))` as in the earlier drivers.
- **Pictures.**
  - `session_data/complex_bench/images/cmp_<case>.png`, one per case, 171 in all, in the layout of `../occt_bench/images`: top row ours, bottom row OCCT; columns operands, A∩B, A∪B, A−B, B−A, A⊕B; red squares vertices, black edges.
  - Under each panel: face, edge and vertex counts (red where the kernels differ), then volume, time and validity.
  - Ours is meshed with `face_meshes()`.
  - A failed load or boolean is an empty panel labelled with its error.
  - In cases our kernel refused as read, the top row shows the driver-repaired run, and the title says so.
  - Joint pictures are framed on OCCT's A∩B (the contact), widened 3x.

## What was and was not verified

**Verified:**

- every number in the tables comes from the raw lines in `raw/`;
- OCCT's chair results match the reference volumes in `native_chair_booleans.cpp` to 3e-10;
- our chair and twisted results match OCCT in volume (≤ 2e-8), counts, solid counts and validity;
- every as-read failure has its message recorded;
- the `DATA` search bug was read in the source;
- the edge/pcurve mismatch was checked with the kernel's own `same_parameter` at load, before any boolean (`raw/pcheck_ours.txt`), and against OCCT's edge tolerances;
- I looked at 3 of the 171 pictures (chair_pose4, joint00, joint01) to check the rendering.

**Not verified:**

- the `.F.` hypothesis was not traced in the reader code; the evidence is face counts only;
- the driver repair is a workaround, not a kernel fix;
- the 20 successful booleans after the repair are trivial ones (disjoint operands), so the joinery booleans of the kernel itself remain untested;
- timings are single runs on a loaded shared machine;
- callgrind was run on two chair booleans only. The binary has no `-g`, so the breakdown is per function, not per line;
- I did not look at every picture.

## Loads

OCCT is OCCT 8.0.1's STEP reader through OCP. Ours is `read_file_step_breps`.

"kinds" counts face kinds:

- OCCT: the surface type of each face.
- Ours: what `nurbs_implicit::recognize` recognises at 1e-6 (everything is NURBS in ours).

"ours valid & solid" counts BReps with both `is_valid()` and `is_solid()` as read.

The two backup files `schoring_body_end_0.stpbak` and `schoring_body_start_0.stepbak` also load in both kernels. Their per-file lines are in `raw/load_occt_bak.txt` and `raw/load_ours_bak.txt`. They are not used in the cases.

| file | OCCT read | OCCT solids | OCCT faces | OCCT kinds plane/cyl/cone/sphere/torus/bspline/other | OCCT valid | OCCT volume | ours read | ours breps | ours faces | ours kinds plane/cyl/cone/sphere/torus/free (recognised) | ours valid & solid | ours volume (sum) | rel diff |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| solidbrep.stp | ok 0.066 s | 2 | 40 | 0,0,0,0,0,40,0 | 1 | 5889.408688 | ok 0.038 s | 2 | 40 | 0,0,0,0,0,40 | 2 of 2 | 5889.408688 | 8e-11 |
| InputTwisted-object-0.step | ok 0.011 s | 1 | 6 | 0,0,0,0,0,6,0 | 1 | 20907.00092 | ok 0.001 s | 1 | 6 | 0,0,0,0,0,6 | 1 of 1 | 20907.00092 | 2.2e-10 |
| InputTwisted-object-1.step | ok 0.009 s | 1 | 6 | 0,0,0,0,0,6,0 | 1 | 20907.00092 | ok 0.001 s | 1 | 6 | 0,0,0,0,0,6 | 1 of 1 | 20907.00092 | 2.2e-10 |
| schoring_body_end_0.stp | ok 0.024 s | 1 | 15 | 6,6,0,0,0,3,0 | 1 | 0.03624548614 | ok 0.007 s | 1 | 15 | 6,7,0,0,0,2 | 1 of 1 | 0.03624612806 | 1.8e-05 |
| schoring_body_end_1.step | ok 0.003 s | 1 | 4 | 2,2,0,0,0,0,0 | 1 | 0.005819438125 | ok 0.001 s | 1 | 4 | 2,2,0,0,0,0 | 0 of 1 | 0.005782695302 (mesh) | 0.0063 |
| schoring_body_start_0.step | ok 0.119 s | 3 | 81 | 46,35,0,0,0,0,0 | 1 | 0.05581914257 | ok 0.014 s | 3 | 81 | 46,35,0,0,0,0 | 1 of 3 | 0.05580149533 (mesh) | 0.00032 |
| schoring_body_start_1.step | ok 0.261 s | 4 | 160 | 160,0,0,0,0,0,0 | 1 | 0.0926252232 | ok 0.001 s | 0 | 0 | 0,0,0,0,0,0 | 0 of 0 | 0 | 1 |
| schoring_body_start_2.step | ok 0.162 s | 4 | 99 | 68,31,0,0,0,0,0 | 1 | 0.09107437169 | ok 0.016 s | 4 | 99 | 68,31,0,0,0,0 | 2 of 4 | 0.09133660645 (mesh) | 0.0029 |
| schoring_body_start_3.step | ok 0.229 s | 5 | 125 | 90,35,0,0,0,0,0 | 1 | 0.126342718 | ok 0.019 s | 5 | 125 | 90,35,0,0,0,0 | 3 of 5 | 0.1266049527 (mesh) | 0.0021 |
| schoring_foot_0.step | ok 0.049 s | 4 | 38 | 29,9,0,0,0,0,0 | 1 | 0.0005629621655 | ok 0.006 s | 3 | 38 | 29,9,0,0,0,0 | 1 of 3 | 0.000563078129 (mesh) | 0.00021 |
| schoring_foot_1.step | ok 0.021 s | 1 | 18 | 10,8,0,0,0,0,0 | 1 | 0.0004600305857 | ok 0.003 s | 1 | 18 | 10,8,0,0,0,0 | 0 of 1 | 0.0004602178324 (mesh) | 0.00041 |
| schoring_head_0.step | ok 0.087 s | 10 | 75 | 46,25,0,0,0,4,0 | 1 | 0.001667877766 | ok 0.015 s | 9 | 75 | 46,25,4,0,0,0 | 6 of 9 | 0.001666675407 (mesh) | 0.00072 |
| schoring_head_1.step | ok 0.017 s | 1 | 18 | 10,8,0,0,0,0,0 | 1 | 0.0004600305857 | ok 0.003 s | 1 | 18 | 10,8,0,0,0,0 | 0 of 1 | 0.0004602178324 (mesh) | 0.00041 |

### Edge/pcurve correspondence as read (ours, `same_parameter` at 1e-7)

```
solidbrep.stp 0 pcurves 108 matched 108 mismatched 0 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,0,0,0,0
solidbrep.stp 1 pcurves 108 matched 108 mismatched 0 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,0,0,0,0
InputTwisted-object-0.step 0 pcurves 24 matched 24 mismatched 0 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,0,0,0,0
InputTwisted-object-1.step 0 pcurves 24 matched 24 mismatched 0 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,0,0,0,0
schoring_body_end_0.stp 0 pcurves 66 matched 40 mismatched 26 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,22,0,0,4
schoring_body_end_1.step 0 pcurves 12 matched 8 mismatched 4 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,4,0,0,0
schoring_body_start_0.step 0 pcurves 92 matched 56 mismatched 36 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,36,0,0,0
schoring_body_start_0.step 1 pcurves 156 matched 144 mismatched 12 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,12,0,0,0
schoring_body_start_0.step 2 pcurves 180 matched 132 mismatched 48 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=18,0,30,0,0,0
schoring_body_start_2.step 0 pcurves 144 matched 136 mismatched 8 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,8,0,0,0
schoring_body_start_2.step 1 pcurves 70 matched 34 mismatched 36 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,36,0,0,0
schoring_body_start_2.step 2 pcurves 154 matched 142 mismatched 12 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,12,0,0,0
schoring_body_start_2.step 3 pcurves 180 matched 132 mismatched 48 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=18,0,30,0,0,0
schoring_body_start_3.step 0 pcurves 180 matched 132 mismatched 48 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=18,0,30,0,0,0
schoring_body_start_3.step 1 pcurves 154 matched 142 mismatched 12 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,12,0,0,0
schoring_body_start_3.step 2 pcurves 144 matched 136 mismatched 8 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,8,0,0,0
schoring_body_start_3.step 3 pcurves 70 matched 34 mismatched 36 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,36,0,0,0
schoring_body_start_3.step 4 pcurves 144 matched 136 mismatched 8 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,8,0,0,0
schoring_foot_0.step 0 pcurves 98 matched 88 mismatched 10 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,10,0,0,0
schoring_foot_0.step 1 pcurves 88 matched 72 mismatched 16 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,16,0,0,0
schoring_foot_0.step 2 pcurves 20 matched 12 mismatched 8 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,8,0,0,0
schoring_foot_1.step 0 pcurves 96 matched 80 mismatched 16 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,16,0,0,0
schoring_head_0.step 0 pcurves 6 matched 4 mismatched 2 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,2,0,0,0
schoring_head_0.step 1 pcurves 20 matched 12 mismatched 8 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,8,0,0,0
schoring_head_0.step 2 pcurves 92 matched 56 mismatched 34 unresolved 2 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,28,8,0,0
schoring_head_0.step 3 pcurves 98 matched 88 mismatched 10 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,10,0,0,0
schoring_head_0.step 4 pcurves 88 matched 72 mismatched 16 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,16,0,0,0
schoring_head_0.step 5 pcurves 20 matched 12 mismatched 8 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,8,0,0,0
schoring_head_0.step 6 pcurves 6 matched 4 mismatched 2 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,2,0,0,0
schoring_head_0.step 7 pcurves 6 matched 4 mismatched 2 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,2,0,0,0
schoring_head_0.step 8 pcurves 6 matched 4 mismatched 2 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,2,0,0,0
schoring_head_1.step 0 pcurves 96 matched 80 mismatched 16 unresolved 0 not_matched_on(plane,sphere,cylinder,cone,torus,free)=0,0,16,0,0,0
```

# Booleans as read (both kernels on the files as they are)

## Summary by group

| group | cases | booleans | ours ok / invalid / failed | OCCT ok / invalid / failed | volumes agree (1e-6) | ours s (4 single ops) | OCCT s | total ratio | geo-mean ratio | xor: ours s / OCCT cells s / OCCT 3-bool s | xor geo-mean ratio vs cells / vs 3-bool |
|---|---|---|---|---|---|---|---|---|---|---|---|
| chairs | 12 | 60 | 60 / 0 / 0 | 60 / 0 / 0 | 60 of 60 | 81.29 | 34.04 | 2.39 | 2.32 | 19.39 / 9.03 / 70.37 | 2.11 / 0.275 |
| twisted | 2 | 10 | 10 / 0 / 0 | 10 / 0 / 0 | 10 of 10 | 0.87 | 1.82 | 0.479 | 0.48 | 0.26 / 0.40 / 3.40 | 0.634 / 0.0748 |
| joints as stored | 38 | 190 | 0 / 0 / 190 | 188 / 2 / 0 | 0 of 0 | 0.00 | 0.00 | – | – | 0.00 / 0.00 / 0.00 | – / – |
| joints rotated | 38 | 190 | 0 / 0 / 190 | 189 / 1 / 0 | 0 of 0 | 0.00 | 0.00 | – | – | 0.00 / 0.00 / 0.00 | – / – |
| element vs rotated self | 27 | 135 | 0 / 0 / 135 | 135 / 0 / 0 | 0 of 0 | 0.00 | 0.00 | – | – | 0.00 / 0.00 / 0.00 | – / – |
| element vs box | 27 | 135 | 0 / 0 / 135 | 135 / 0 / 0 | 0 of 0 | 0.00 | 0.00 | – | – | 0.00 / 0.00 / 0.00 | – / – |
| element vs cylinder | 27 | 135 | 0 / 0 / 135 | 135 / 0 / 0 | 0 of 0 | 0.00 | 0.00 | – | – | 0.00 / 0.00 / 0.00 | – / – |
| ALL | 171 | 855 | 70 / 0 / 785 | 852 / 3 / 0 | 70 of 70 | 82.16 | 35.86 | 2.29 | 1.86 | 19.64 / 9.43 / 73.77 | 1.78 / 0.228 |

### Failures of ours by stage (as read)

| booleans | stage |
|---|---|
| 450 | input check (brep_boolean.cpp): operand not a closed oriented solid as read |
| 120 | split (split.h): original edge/pcurve not same-parameter |
| 100 | load: STEP reader returned no BRep for this file |
| 75 | section: SSI pullback (intersection.cpp) |
| 14 | section: interferences (brep_section.cpp) |
| 10 | split (split.cpp) |
| 10 | section: boundary events (brep_section.cpp) |
| 5 | section: SSI (intersection.cpp) |
| 1 | section: curve/surface (curve_surface_intersection.cpp) |

## Per case

Times are the sum of the four single booleans (∩ ∪ A−B B−A) where both kernels returned; xor separately (OCCT: CellsBuilder, one general fuse). ratio = ours / OCCT. "agree" counts booleans whose volumes agree to 1e-6 relative.

| case | ours ok/inv/fail | OCCT ok/inv/fail | agree | max rel vol diff | ours s | OCCT s | ratio | geo-mean | xor ours s | xor OCCT cells s | xor OCCT 3-bool s | picture |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chair_pose0 | 5/0/0 | 5/0/0 | 5/5 | 5.3e-09 | 4.884 | 2.611 | 1.87 | 1.88 | 1.18 | 0.679 | 4.75 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_chair_pose0.png) |
| chair_pose1 | 5/0/0 | 5/0/0 | 5/5 | 5.5e-10 | 6.189 | 2.770 | 2.23 | 2.28 | 1.75 | 0.577 | 5.55 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_chair_pose1.png) |
| chair_pose2 | 5/0/0 | 5/0/0 | 5/5 | 7.3e-09 | 6.236 | 3.018 | 2.07 | 2.06 | 1.48 | 0.712 | 5.35 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_chair_pose2.png) |
| chair_pose3 | 5/0/0 | 5/0/0 | 5/5 | 4.5e-09 | 5.230 | 2.435 | 2.15 | 2.23 | 1.36 | 1.23 | 5.15 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_chair_pose3.png) |
| chair_pose4 | 5/0/0 | 5/0/0 | 5/5 | 6.7e-09 | 6.351 | 2.853 | 2.23 | 2.23 | 1.46 | 0.765 | 9.59 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_chair_pose4.png) |
| chair_pose5 | 5/0/0 | 5/0/0 | 5/5 | 1.3e-08 | 5.443 | 2.487 | 2.19 | 2.2 | 1.22 | 0.649 | 5.28 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_chair_pose5.png) |
| chair_pose6 | 5/0/0 | 5/0/0 | 5/5 | 5.2e-09 | 6.518 | 2.219 | 2.94 | 2.95 | 1.61 | 0.527 | 4.63 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_chair_pose6.png) |
| chair_pose7 | 5/0/0 | 5/0/0 | 5/5 | 1.8e-09 | 3.095 | 1.955 | 1.58 | 1.58 | 0.818 | 0.495 | 2.79 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_chair_pose7.png) |
| chair_pose8 | 5/0/0 | 5/0/0 | 5/5 | 6.6e-09 | 7.590 | 3.159 | 2.4 | 2.41 | 1.87 | 1.1 | 7.67 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_chair_pose8.png) |
| chair_pose9 | 5/0/0 | 5/0/0 | 5/5 | 7.4e-10 | 7.096 | 2.974 | 2.39 | 2.4 | 1.44 | 0.66 | 4.27 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_chair_pose9.png) |
| chair_pose10 | 5/0/0 | 5/0/0 | 5/5 | 2e-08 | 9.680 | 3.095 | 3.13 | 3.23 | 1.92 | 0.727 | 7.13 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_chair_pose10.png) |
| chair_self | 5/0/0 | 5/0/0 | 5/5 | 3.1e-09 | 12.974 | 4.466 | 2.91 | 2.94 | 3.25 | 0.905 | 8.21 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_chair_self.png) |
| twisted_pose0 | 5/0/0 | 5/0/0 | 5/5 | 4.7e-11 | 0.417 | 0.903 | 0.462 | 0.464 | 0.109 | 0.188 | 1.63 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_twisted_pose0.png) |
| twisted_rot | 5/0/0 | 5/0/0 | 5/5 | 2.9e-10 | 0.453 | 0.914 | 0.496 | 0.497 | 0.149 | 0.214 | 1.77 | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_twisted_rot.png) |
| joint00 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint00.png) |
| joint00_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint00_rot.png) |
| joint01 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint01.png) |
| joint01_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint01_rot.png) |
| joint02 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint02.png) |
| joint02_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint02_rot.png) |
| joint03 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint03.png) |
| joint03_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint03_rot.png) |
| joint04 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint04.png) |
| joint04_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint04_rot.png) |
| joint05 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint05.png) |
| joint05_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint05_rot.png) |
| joint06 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint06.png) |
| joint06_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint06_rot.png) |
| joint07 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint07.png) |
| joint07_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint07_rot.png) |
| joint08 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint08.png) |
| joint08_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint08_rot.png) |
| joint09 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint09.png) |
| joint09_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint09_rot.png) |
| joint10 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint10.png) |
| joint10_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint10_rot.png) |
| joint11 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint11.png) |
| joint11_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint11_rot.png) |
| joint12 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint12.png) |
| joint12_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint12_rot.png) |
| joint13 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint13.png) |
| joint13_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint13_rot.png) |
| joint14 | 0/0/5 | 4/1/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint14.png) |
| joint14_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint14_rot.png) |
| joint15 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint15.png) |
| joint15_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint15_rot.png) |
| joint16 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint16.png) |
| joint16_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint16_rot.png) |
| joint17 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint17.png) |
| joint17_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint17_rot.png) |
| joint18 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint18.png) |
| joint18_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint18_rot.png) |
| joint19 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint19.png) |
| joint19_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint19_rot.png) |
| joint20 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint20.png) |
| joint20_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint20_rot.png) |
| joint21 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint21.png) |
| joint21_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint21_rot.png) |
| joint22 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint22.png) |
| joint22_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint22_rot.png) |
| joint23 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint23.png) |
| joint23_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint23_rot.png) |
| joint24 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint24.png) |
| joint24_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint24_rot.png) |
| joint25 | 0/0/5 | 4/1/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint25.png) |
| joint25_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint25_rot.png) |
| joint26 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint26.png) |
| joint26_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint26_rot.png) |
| joint27 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint27.png) |
| joint27_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint27_rot.png) |
| joint28 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint28.png) |
| joint28_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint28_rot.png) |
| joint29 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint29.png) |
| joint29_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint29_rot.png) |
| joint30 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint30.png) |
| joint30_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint30_rot.png) |
| joint31 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint31.png) |
| joint31_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint31_rot.png) |
| joint32 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint32.png) |
| joint32_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint32_rot.png) |
| joint33 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint33.png) |
| joint33_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint33_rot.png) |
| joint34 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint34.png) |
| joint34_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint34_rot.png) |
| joint35 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint35.png) |
| joint35_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint35_rot.png) |
| joint36 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint36.png) |
| joint36_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint36_rot.png) |
| joint37 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint37.png) |
| joint37_rot | 0/0/5 | 4/1/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint37_rot.png) |
| elem00_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem00_self.png) |
| elem00_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem00_box.png) |
| elem00_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem00_cyl.png) |
| elem01_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem01_self.png) |
| elem01_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem01_box.png) |
| elem01_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem01_cyl.png) |
| elem02_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem02_self.png) |
| elem02_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem02_box.png) |
| elem02_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem02_cyl.png) |
| elem03_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem03_self.png) |
| elem03_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem03_box.png) |
| elem03_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem03_cyl.png) |
| elem04_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem04_self.png) |
| elem04_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem04_box.png) |
| elem04_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem04_cyl.png) |
| elem05_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem05_self.png) |
| elem05_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem05_box.png) |
| elem05_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem05_cyl.png) |
| elem06_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem06_self.png) |
| elem06_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem06_box.png) |
| elem06_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem06_cyl.png) |
| elem07_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem07_self.png) |
| elem07_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem07_box.png) |
| elem07_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem07_cyl.png) |
| elem08_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem08_self.png) |
| elem08_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem08_box.png) |
| elem08_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem08_cyl.png) |
| elem09_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem09_self.png) |
| elem09_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem09_box.png) |
| elem09_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem09_cyl.png) |
| elem10_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem10_self.png) |
| elem10_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem10_box.png) |
| elem10_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem10_cyl.png) |
| elem11_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem11_self.png) |
| elem11_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem11_box.png) |
| elem11_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem11_cyl.png) |
| elem12_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem12_self.png) |
| elem12_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem12_box.png) |
| elem12_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem12_cyl.png) |
| elem13_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem13_self.png) |
| elem13_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem13_box.png) |
| elem13_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem13_cyl.png) |
| elem14_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem14_self.png) |
| elem14_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem14_box.png) |
| elem14_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem14_cyl.png) |
| elem15_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem15_self.png) |
| elem15_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem15_box.png) |
| elem15_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem15_cyl.png) |
| elem16_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem16_self.png) |
| elem16_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem16_box.png) |
| elem16_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem16_cyl.png) |
| elem17_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem17_self.png) |
| elem17_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem17_box.png) |
| elem17_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem17_cyl.png) |
| elem18_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem18_self.png) |
| elem18_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem18_box.png) |
| elem18_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem18_cyl.png) |
| elem19_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem19_self.png) |
| elem19_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem19_box.png) |
| elem19_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem19_cyl.png) |
| elem20_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem20_self.png) |
| elem20_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem20_box.png) |
| elem20_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem20_cyl.png) |
| elem21_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem21_self.png) |
| elem21_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem21_box.png) |
| elem21_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem21_cyl.png) |
| elem22_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem22_self.png) |
| elem22_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem22_box.png) |
| elem22_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem22_cyl.png) |
| elem23_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem23_self.png) |
| elem23_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem23_box.png) |
| elem23_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem23_cyl.png) |
| elem24_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem24_self.png) |
| elem24_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem24_box.png) |
| elem24_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem24_cyl.png) |
| elem25_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem25_self.png) |
| elem25_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem25_box.png) |
| elem25_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem25_cyl.png) |
| elem26_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem26_self.png) |
| elem26_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem26_box.png) |
| elem26_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem26_cyl.png) |

## Cases where ours did not return (as read): first message per case

| case | ops not returned | stage | first message |
|---|---|---|---|
| joint00 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint00_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint01 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint01_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint02 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint02_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint03 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint03_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint04 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint04_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint05 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint05_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint06 | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| joint06_rot | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| joint07 | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint07_rot | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint08 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint08_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint09 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint09_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint10 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint10_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint11 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint11_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint12 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint12_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint13 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint13_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint14 | intersection union a-b b-a xor | section: interferences (brep_section.cpp) | FAIL: Interference lacks whole original paired agreement |
| joint14_rot | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| joint15 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint15_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint16 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint16_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint17 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint17_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint18 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint18_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint19 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint19_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint20 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint20_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint21 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint21_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint22 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint22_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint23 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint23_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint24 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint24_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint25 | intersection union a-b b-a xor | section: interferences (brep_section.cpp) | FAIL: Interference lacks whole original paired agreement |
| joint25_rot | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| joint26 | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| joint26_rot | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| joint27 | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| joint27_rot | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| joint28 | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| joint28_rot | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| joint29 | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| joint29_rot | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| joint30 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint30_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint31 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint31_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint32 | intersection union a-b b-a xor | section: boundary events (brep_section.cpp) | FAIL: Boundary event has invalid original raw coordinates |
| joint32_rot | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| joint33 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint33_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint34 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint34_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint35 | intersection union a-b b-a xor | section: boundary events (brep_section.cpp) | FAIL: Boundary event has invalid original raw coordinates |
| joint35_rot | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| joint36 | intersection union a-b b-a xor | section: interferences (brep_section.cpp) | FAIL: Interference lacks whole original paired agreement |
| joint36_rot | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| joint37 | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| joint37_rot | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem00_self | intersection union a-b b-a xor | section: SSI (intersection.cpp) | FAIL: Native SSI paired fit exceeded its refinement budget with 566 samples, t=0.494518, error/tol=10932.619053, lifts/tol=10932.619053/3283.863625, UV=1.51 |
| elem00_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem00_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem01_self | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem01_box | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem01_cyl | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem02_self | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem02_box | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem02_cyl | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem03_self | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem03_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem03_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem04_self | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem04_box | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem04_cyl | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem05_self | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| elem05_box | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| elem05_cyl | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| elem06_self | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| elem06_box | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| elem06_cyl | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| elem07_self | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| elem07_box | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| elem07_cyl | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| elem08_self | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| elem08_box | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| elem08_cyl | intersection union a-b b-a xor | load: STEP reader returned no BRep for this file | LOADFAIL: stoul |
| elem09_self | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem09_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem09_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem10_self | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem10_box | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem10_cyl | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem11_self | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem11_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem11_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem12_self | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem12_box | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem12_cyl | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem13_self | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem13_box | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem13_cyl | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem14_self | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem14_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem14_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem15_self | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem15_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem15_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem16_self | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem16_box | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem16_cyl | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem17_self | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem17_box | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem17_cyl | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem18_self | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Common parameter partition failed |
| elem18_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem18_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem19_self | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem19_box | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem19_cyl | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem20_self | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem20_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem20_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem21_self | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem21_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem21_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem22_self | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem22_box | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem22_cyl | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem23_self | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem23_box | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem23_cyl | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem24_self | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem24_box | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem24_cyl | intersection union a-b b-a xor | input check (brep_boolean.cpp): operand not a closed oriented solid as read | FAIL: Native BRep Booleans require closed oriented solid operands |
| elem25_self | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem25_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem25_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem26_self | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem26_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem26_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |

## OCCT booleans that failed or were invalid

| case | op | status | valid | s | message |
|---|---|---|---|---|---|
| joint14 | xorcells | ok | 0 | 0.006 |  |
| joint25 | xorcells | ok | 0 | 0.006 |  |
| joint37_rot | union | ok | 0 | 0.110 |  |

OCCT's three invalid results: joint14 and joint25 pair a dowel with an identical coincident copy (head_0.u0/u7 and u6/u8 are the same solid at the same place in the file); joint37_rot is body_start_3.u3 with u4 rotated.

# Booleans after the driver-side orientation repair (ours only rerun; the 90 cases refused as read)

OCCT columns are the same OCCT runs as above. The 20 booleans of ours that return here are all trivial (disjoint operands: empty intersection or an unchanged operand), so the time ratios in this section say nothing about real joinery booleans.

## Summary by group

| group | cases | booleans | ours ok / invalid / failed | OCCT ok / invalid / failed | volumes agree (1e-6) | ours s (4 single ops) | OCCT s | total ratio | geo-mean ratio | xor: ours s / OCCT cells s / OCCT 3-bool s | xor geo-mean ratio vs cells / vs 3-bool |
|---|---|---|---|---|---|---|---|---|---|---|---|
| joints as stored | 27 | 135 | 9 / 0 / 126 | 135 / 0 / 0 | 7 of 9 | 0.03 | 0.08 | 0.314 | 0.209 | 0.00 / 0.00 / 0.00 | – / – |
| joints rotated | 27 | 135 | 7 / 0 / 128 | 134 / 1 / 0 | 5 of 7 | 0.01 | 0.04 | 0.327 | 0.219 | 0.00 / 0.00 / 0.00 | – / – |
| element vs rotated self | 12 | 60 | 0 / 0 / 60 | 60 / 0 / 0 | 0 of 0 | 0.00 | 0.00 | – | – | 0.00 / 0.00 / 0.00 | – / – |
| element vs box | 12 | 60 | 0 / 0 / 60 | 60 / 0 / 0 | 0 of 0 | 0.00 | 0.00 | – | – | 0.00 / 0.00 / 0.00 | – / – |
| element vs cylinder | 12 | 60 | 4 / 0 / 56 | 60 / 0 / 0 | 4 of 4 | 0.00 | 0.02 | 0.161 | 0.152 | 0.00 / 0.00 / 0.00 | – / – |
| ALL | 90 | 450 | 20 / 0 / 430 | 449 / 1 / 0 | 16 of 20 | 0.04 | 0.14 | 0.299 | 0.199 | 0.00 / 0.00 / 0.00 | – / – |

### Failures of ours by stage (after repair)

| booleans | stage |
|---|---|
| 164 | split (split.cpp) |
| 160 | split (split.h): original edge/pcurve not same-parameter |
| 50 | assembly (brep_assemble.cpp) |
| 25 | section: SSI pullback (intersection.cpp) |
| 15 | classification (split.cpp) |
| 11 | section: SSI (intersection.cpp) |
| 5 | section: interferences (brep_section.cpp) |

## Per case

Times are the sum of the four single booleans (∩ ∪ A−B B−A) where both kernels returned; xor separately (OCCT: CellsBuilder, one general fuse). ratio = ours / OCCT. "agree" counts booleans whose volumes agree to 1e-6 relative.

| case | ours ok/inv/fail | OCCT ok/inv/fail | agree | max rel vol diff | ours s | OCCT s | ratio | geo-mean | xor ours s | xor OCCT cells s | xor OCCT 3-bool s | picture |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| joint00 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint00.png) |
| joint00_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint00_rot.png) |
| joint01 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint01.png) |
| joint01_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint01_rot.png) |
| joint02 | 1/0/4 | 5/0/0 | 1/1 | 0 | 0.001 | 0.016 | 0.0662 | 0.0662 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint02.png) |
| joint02_rot | 1/0/4 | 5/0/0 | 1/1 | 0 | 0.001 | 0.007 | 0.144 | 0.144 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint02_rot.png) |
| joint03 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint03.png) |
| joint03_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint03_rot.png) |
| joint04 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint04.png) |
| joint04_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint04_rot.png) |
| joint05 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint05.png) |
| joint05_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint05_rot.png) |
| joint08 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint08.png) |
| joint08_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint08_rot.png) |
| joint09 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint09.png) |
| joint09_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint09_rot.png) |
| joint10 | 1/0/4 | 5/0/0 | 1/1 | 0 | 0.001 | 0.009 | 0.112 | 0.112 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint10.png) |
| joint10_rot | 1/0/4 | 5/0/0 | 1/1 | 0 | 0.001 | 0.009 | 0.118 | 0.118 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint10_rot.png) |
| joint11 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint11.png) |
| joint11_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint11_rot.png) |
| joint12 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint12.png) |
| joint12_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint12_rot.png) |
| joint13 | 2/0/3 | 5/0/0 | 1/2 | 0.0051 | 0.004 | 0.019 | 0.22 | 0.139 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint13.png) |
| joint13_rot | 2/0/3 | 5/0/0 | 1/2 | 0.0051 | 0.004 | 0.009 | 0.423 | 0.264 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint13_rot.png) |
| joint15 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint15.png) |
| joint15_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint15_rot.png) |
| joint16 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint16.png) |
| joint16_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint16_rot.png) |
| joint17 | 1/0/4 | 5/0/0 | 1/1 | 0 | 0.001 | 0.011 | 0.102 | 0.102 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint17.png) |
| joint17_rot | 1/0/4 | 5/0/0 | 1/1 | 0 | 0.001 | 0.006 | 0.197 | 0.197 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint17_rot.png) |
| joint18 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint18.png) |
| joint18_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint18_rot.png) |
| joint19 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint19.png) |
| joint19_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint19_rot.png) |
| joint20 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint20.png) |
| joint20_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint20_rot.png) |
| joint21 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint21.png) |
| joint21_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint21_rot.png) |
| joint22 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint22.png) |
| joint22_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint22_rot.png) |
| joint23 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint23.png) |
| joint23_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint23_rot.png) |
| joint24 | 2/0/3 | 5/0/0 | 1/2 | 0.0051 | 0.004 | 0.007 | 0.583 | 0.342 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint24.png) |
| joint24_rot | 2/0/3 | 5/0/0 | 1/2 | 0.0051 | 0.006 | 0.010 | 0.628 | 0.32 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint24_rot.png) |
| joint30 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint30.png) |
| joint30_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint30_rot.png) |
| joint31 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint31.png) |
| joint31_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint31_rot.png) |
| joint33 | 1/0/4 | 5/0/0 | 1/1 | 0 | 0.007 | 0.009 | 0.792 | 0.792 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint33.png) |
| joint33_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint33_rot.png) |
| joint34 | 1/0/4 | 5/0/0 | 1/1 | 0 | 0.008 | 0.014 | 0.566 | 0.566 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint34.png) |
| joint34_rot | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint34_rot.png) |
| joint37 | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint37.png) |
| joint37_rot | 0/0/5 | 4/1/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_joint37_rot.png) |
| elem01_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem01_self.png) |
| elem01_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem01_box.png) |
| elem01_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem01_cyl.png) |
| elem02_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem02_self.png) |
| elem02_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem02_box.png) |
| elem02_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem02_cyl.png) |
| elem04_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem04_self.png) |
| elem04_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem04_box.png) |
| elem04_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem04_cyl.png) |
| elem10_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem10_self.png) |
| elem10_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem10_box.png) |
| elem10_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem10_cyl.png) |
| elem12_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem12_self.png) |
| elem12_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem12_box.png) |
| elem12_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem12_cyl.png) |
| elem13_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem13_self.png) |
| elem13_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem13_box.png) |
| elem13_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem13_cyl.png) |
| elem16_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem16_self.png) |
| elem16_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem16_box.png) |
| elem16_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem16_cyl.png) |
| elem17_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem17_self.png) |
| elem17_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem17_box.png) |
| elem17_cyl | 2/0/3 | 5/0/0 | 2/2 | 0 | 0.002 | 0.011 | 0.139 | 0.13 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem17_cyl.png) |
| elem19_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem19_self.png) |
| elem19_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem19_box.png) |
| elem19_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem19_cyl.png) |
| elem22_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem22_self.png) |
| elem22_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem22_box.png) |
| elem22_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem22_cyl.png) |
| elem23_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem23_self.png) |
| elem23_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem23_box.png) |
| elem23_cyl | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem23_cyl.png) |
| elem24_self | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem24_self.png) |
| elem24_box | 0/0/5 | 5/0/0 | 0/0 | 0 | 0.000 | 0.000 | – | – | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem24_box.png) |
| elem24_cyl | 2/0/3 | 5/0/0 | 2/2 | 0 | 0.001 | 0.007 | 0.198 | 0.178 | – | – | – | [png](https://github.com/petrasvestartas/session_data/blob/claude/clever-ramanujan-dkse3b/complex_bench/images/cmp_elem24_cyl.png) |

## Cases where ours did not return (after repair): first message per case

| case | ops not returned | stage | first message |
|---|---|---|---|
| joint00 | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint00_rot | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| joint01 | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| joint01_rot | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| joint02 | union a-b b-a xor | assembly (brep_assemble.cpp) | FAIL: edge and pcurve disagree inside their ranges; tolerance=9.9999999999999995e-08; world=59 CVs [0.020698825913240099,0.062096461872559502]; pcurve=48 CV |
| joint02_rot | union a-b b-a xor | assembly (brep_assemble.cpp) | FAIL: edge and pcurve disagree inside their ranges; tolerance=9.9999999999999995e-08; world=59 CVs [0.020698825913240099,0.062096461872559502]; pcurve=48 CV |
| joint03 | intersection union a-b b-a xor | classification (split.cpp) | FAIL: Native Boolean face classification is unresolved |
| joint03_rot | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| joint04 | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,0.99999999999 |
| joint04_rot | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,0.99999999999 |
| joint05 | intersection union a-b b-a xor | section: interferences (brep_section.cpp) | FAIL: Interference lacks whole original paired agreement |
| joint05_rot | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,0. |
| joint08 | intersection union a-b b-a xor | section: SSI (intersection.cpp) | FAIL: Empty support inventory has unowned original root graphs |
| joint08_rot | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| joint09 | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint09_rot | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint10 | union a-b b-a xor | assembly (brep_assemble.cpp) | FAIL: edge and pcurve disagree inside their ranges; tolerance=9.9999999999999995e-08; world=7 CVs [0,0.0212572617382711]; pcurve=48 CVs [0,47]; surface=5x2  |
| joint10_rot | union a-b b-a xor | assembly (brep_assemble.cpp) | FAIL: edge and pcurve disagree inside their ranges; tolerance=9.9999999999999995e-08; world=7 CVs [0,0.0212572617382711]; pcurve=48 CVs [0,47]; surface=5x2  |
| joint11 | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint11_rot | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint12 | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint12_rot | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint13 | union b-a xor | assembly (brep_assemble.cpp) | FAIL: pcurve reparameterization is unresolved: On-surface overlap needs a certified parameter mapping; tolerance=9.9999999999999995e-08; world=5 CVs [1.0675 |
| joint13_rot | union b-a xor | assembly (brep_assemble.cpp) | FAIL: pcurve reparameterization is unresolved: On-surface overlap needs a certified parameter mapping; tolerance=9.9999999999999995e-08; world=5 CVs [1.0675 |
| joint15 | intersection union a-b b-a xor | classification (split.cpp) | FAIL: Native Boolean face classification is unresolved |
| joint15_rot | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint16 | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint16_rot | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint17 | union a-b b-a xor | assembly (brep_assemble.cpp) | FAIL: pcurve reparameterization is unresolved: Unresolved curve/surface coincidence or excessive root count; tolerance=9.9999999999999995e-08; world=9 CVs [ |
| joint17_rot | union a-b b-a xor | assembly (brep_assemble.cpp) | FAIL: pcurve reparameterization is unresolved: Unresolved curve/surface coincidence or excessive root count; tolerance=9.9999999999999995e-08; world=9 CVs [ |
| joint18 | intersection union a-b b-a xor | split (split.cpp) | FAIL: Cannot keep an adjacent trim on its original shared edge |
| joint18_rot | intersection union a-b b-a xor | split (split.cpp) | FAIL: Cannot keep an adjacent trim on its original shared edge |
| joint19 | intersection union a-b b-a xor | split (split.cpp) | FAIL: Cannot keep an adjacent trim on its original shared edge |
| joint19_rot | intersection union a-b b-a xor | split (split.cpp) | FAIL: Cannot keep an adjacent trim on its original shared edge |
| joint20 | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint20_rot | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint21 | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint21_rot | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint22 | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint22_rot | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint23 | intersection union a-b b-a xor | classification (split.cpp) | FAIL: Native Boolean face classification is unresolved |
| joint23_rot | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| joint24 | union a-b xor | assembly (brep_assemble.cpp) | FAIL: pcurve reparameterization is unresolved: On-surface overlap needs a certified parameter mapping; tolerance=9.9999999999999995e-08; world=5 CVs [1.0675 |
| joint24_rot | union a-b xor | assembly (brep_assemble.cpp) | FAIL: pcurve reparameterization is unresolved: On-surface overlap needs a certified parameter mapping; tolerance=9.9999999999999995e-08; world=5 CVs [1.0675 |
| joint30 | intersection union a-b b-a xor | section: SSI (intersection.cpp) | FAIL: Analytic section pcurve has no certified original raw parameter law |
| joint30_rot | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| joint31 | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint31_rot | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint33 | union a-b b-a xor | assembly (brep_assemble.cpp) | FAIL: pcurve reparameterization is unresolved: On-surface overlap needs a certified parameter mapping; tolerance=9.9999999999999995e-08; world=3 CVs [7.7098 |
| joint33_rot | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,0. |
| joint34 | union a-b b-a xor | assembly (brep_assemble.cpp) | FAIL: pcurve reparameterization is unresolved: On-surface overlap needs a certified parameter mapping; tolerance=9.9999999999999995e-08; world=3 CVs [-3.522 |
| joint34_rot | intersection union a-b b-a xor | split (split.cpp) | FAIL: Cannot keep an adjacent trim on its original shared edge |
| joint37 | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| joint37_rot | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem01_self | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem01_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem01_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem02_self | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem02_box | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem02_cyl | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem04_self | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified endpoint residual exceeds tolerance |
| elem04_box | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem04_cyl | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem10_self | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem10_box | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem10_cyl | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem12_self | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem12_box | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem12_cyl | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem13_self | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified endpoint residual exceeds tolerance |
| elem13_box | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem13_cyl | intersection union a-b b-a xor | section: SSI pullback (intersection.cpp) | FAIL: Analytic pullback did not obtain a complete paired-parameter certificate: Certified endpoint residual exceeds tolerance |
| elem16_self | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,0. |
| elem16_box | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,0. |
| elem16_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,0.99999999999 |
| elem17_self | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem17_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,0.99999999999 |
| elem17_cyl | union a-b xor | assembly (brep_assemble.cpp) | FAIL: pcurve reparameterization is unresolved: On-surface overlap needs a certified parameter mapping; tolerance=9.9999999999999995e-08; world=5 CVs [5.3376 |
| elem19_self | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem19_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem19_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem22_self | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem22_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem22_cyl | intersection union a-b b-a xor | split (split.cpp) | FAIL: Cannot keep an adjacent trim on its original shared edge |
| elem23_self | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem23_box | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem23_cyl | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem24_self | intersection union a-b b-a xor | split (split.cpp) | FAIL: Required edge event lacks an original raw curve/trim law: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1] |
| elem24_box | intersection union a-b b-a xor | split (split.h): original edge/pcurve not same-parameter | FAIL: Split curve/trim correspondence is mismatched: Certified common-interval point residual exceeds tolerance; interval=[0.97872340425531912,1]; depth=0;  |
| elem24_cyl | union a-b xor | assembly (brep_assemble.cpp) | FAIL: pcurve reparameterization is unresolved: On-surface overlap needs a certified parameter mapping; tolerance=9.9999999999999995e-08; world=5 CVs [1.0675 |

## Booleans of ours that failed, were invalid, disagree in volume, or took over 10 s

| case | op | what | ours s | ours faces/edges/vertices | OCCT s | OCCT faces/edges/vertices | ours volume | OCCT volume | rel diff | ours message |
|---|---|---|---|---|---|---|---|---|---|---|
| joint13 | a-b | VOLUME | 0.00 | 3/3/2 | 0.009 | 3/3/2 | 4.922770131e-05 (mesh) | 4.948008429e-05 | 0.0051 |  |
| joint13_rot | a-b | VOLUME | 0.00 | 3/3/2 | 0.004 | 3/3/2 | 4.922770131e-05 (mesh) | 4.948008429e-05 | 0.0051 |  |
| joint24 | b-a | VOLUME | 0.00 | 3/3/2 | 0.004 | 3/3/2 | 4.922770131e-05 (mesh) | 4.948008429e-05 | 0.0051 |  |
| joint24_rot | b-a | VOLUME | 0.01 | 3/3/2 | 0.005 | 3/3/2 | 4.922770131e-05 (mesh) | 4.948008429e-05 | 0.0051 |  |


(Rows with status FAIL are omitted above; every per-boolean line is in raw/raw_ours_repair.txt.)

# Files

- `raw/raw_ours.txt`, `raw/raw_occt.txt`, `raw/raw_ours_repair.txt`: one line per boolean: `<case> OP <op> <status> bool_s <s> counts <faces> <edges> <vertices> shells <n> solids <n> valid <0|1> solid <0|1> vol_s <s> volume <v> [message]`. OCCT's xor appears as `xorcells` and `xor3`.
- `raw/cases.tsv` (name, title, tolerance, operand specs for ours and for OCCT, including the move matrices), `raw/units.txt`, `raw/load_*.txt`, `raw/solids_occt.txt`, `raw/pcheck_ours.txt`, `raw/callgrind_*.txt` (callgrind_annotate --inclusive output, top functions).
- `drivers/`: ours_cx.cpp (our side; build with `cd build && bash fuzz/build.sh ours_cx.cpp ours_cx`), occt_cx.cpp (OCCT side; `g++ -O2 -std=c++17 -I<occt>/include/opencascade occt_cx.cpp -L<occt>/lin64/gcc/lib -lTKBO -lTKMesh -lTKPrim -lTKTopAlgo -lTKGeomAlgo -lTKBRep -lTKGeomBase -lTKG3d -lTKG2d -lTKMath -lTKernel`), step2brep.py / solids_occt.py / map_units.py (OCCT STEP read through OCP, operand pairing), gen_cases.py, run_cases.py (`--repair` for the second pass), make_pics.py + page.html + shoot.cjs (pictures), summarize.py, load_table.py, case_failures.py.
