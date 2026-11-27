# session_cpp on brep-bench

[brep-bench](https://brepbench.org) ([repo](https://github.com/bmander/brep-bench), MIT/Apache-2.0) grades each
solid against closed-form volume and area, from the STEP file the kernel writes, measured by the harness's own
reader (`harness/mass`, 1e-6 relative). Nothing here is submitted upstream.

- `bb_session.cpp`: the runner (SPEC.md 1.19): every case implementation in one program, `bb_session CASE OUT.stl
  [OUT.step]`; booleans through `bop::apply`, STEP through `file_step::write_file_step_brep`. A case it does not build
  is refused with the reason (`--list` prints what is built, refused, or a workaround).
- `build.sh [build dir] [out]`: compiles it with the session_cpp build's flags and links the build's objects
  (as `../score/link.sh`); nothing is rebuilt.
- `setup_harness.py`: adds the `session_cpp` kernel to a *copy* of the clone's `kernels.json`.
- `run.sh <clone> <board.json> [out]`: build, copy the clone, build the harness's measurers (`cargo -j2`), run
  `harness/run.py --kernel session_cpp --jobs 2` (whole suite, about 30 s), then `report.py`.
- `report.py`: `results.tsv` (one row per case: our outcome, OCCT's and SMLib's from board.json, our own seconds,
  OCCT's own seconds, measured vs expected volume and area, the harness's reason) and `results.md` (counts, the
  wrong/crashed list, times).
- `pics.py` (OCP venv python): shaded pictures of our STEP results for chosen cases.

```
S=/tmp/claude-0/-home-user-wood-research/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad
bash run.sh $S/../../-home-user/8b288b7c-72c4-56e2-9565-a39939e050f9/scratchpad/brepbench/repo \
            <path>/brepbench/board.json $S/brepbench_out
```

Workarounds (the case's natural construction needs a feature session_cpp lacks; flagged as SPEC.md asks):
`primitives/revolved-washer`, `primitives/revolved-sector` (no revolve: tube difference, sector by a box),
`parts/v-belt-pulley` (no revolve: groove as a ring less two cones), `boolean/boss-on-a-lobe-of-the-same-radius`
(no extrude of a curved outline: polygon prism less blend cylinders plus lobe cylinders).

## Run of 2026-11-27 (session_cpp 07827941)

See `results.md` for the tables. 111 cases implemented (83 pass, 24 wrong, 1 crashed, 3 refused by `bop::apply`
returning an empty result); everything else refused with a reason (no sweep, fillet, chamfer, draft, loft, revolve/extrude of curves,
paraboloid/ellipsoid; offset/shell/thicken/NURBS-face cases not written here though `BRep::offset`, `hollow` and
`brep_thicken` exist). Of the 24 wrong results, 17 came back from `bop::apply` with `Report::failure` set ("result
is not a closed solid", or a tolerance check) and were written anyway; the runner refuses only an empty result.
The open STEP files are open in the kernel too (`volume_exact` throws "requires a closed oriented solid"), not a
writer fault. OCCT's seconds are the board's, from another machine: compare orders of magnitude only.
