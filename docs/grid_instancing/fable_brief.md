# Fable grid pass: brief

These are petras's requirements, collected 2026-09-23. This file wins over every other document in this folder. The older design (`grid_design.md`) and the current ~1000-line `wood/src/templates/grid.h` are input, not a spec: redo them lean.

## Scope

1. **Geometry only.** No sizing, loads, carbon, fire, suppliers or cost.
   - Sizes are inputs: profiles per role.
   - Leave attributes a later pass can read (roles, spans, storey), and nothing more.
2. **Many grid patterns for multistorey buildings:** orthogonal with uneven bays, skewed, radial, triangular, hexagonal and irregular. Also footprints of any polygon: L, U, courtyard and cores.
   - The configurations Branch3D and FAST+EPP offer must be reproducible: see `branch3d_topologies.md`, `branch3d_framing.md`, `branch3d_configuration_model.md` and `fastepp_reference.md`.
   - Structural methods:
     - point supported (plate on columns, with heads)
     - post and beam (girders one way, deck spanning to them)
     - purlin on girder (girders + purlins at a spacing)
   - For each method: span direction, perimeter beams, and cores as concrete wall plates with floor holes.
3. **An extremely simple, straightforward API.** A user draws a rough shape and gets a filled building in a few lines. There are three input workflows, all feeding the same core:
   - **A. Massing solid.** A closed solid (Mesh or BRep) with orthogonal or non-orthogonal outlines, tapered faces, curved faces (approximated) and holes (atria, courtyards, cores). It is sliced into levels. Each level section (outer loop + holes) is filled with the plan grid pattern, and the elements are built between the levels. Define what tapers do to columns and perimeter members (for example vertical columns inside, perimeter following the section, members the next level cannot carry are dropped or transferred) and keep it simple.
   - **B. 2D axes.** Grid lines drawn in plan (any angles), plus level heights. The building is built layer by layer: axes → intersections → bays → members per level.
   - **C. Line by line.** 3D lines (columns, beams, braces) and flat surfaces (decks, walls, cores) as the direct representation of each member (compas_grid style, e.g. the crea dataset in `crea_reference.md`). The same joint resolution then makes the elements.
4. **Clean joints: the hard geometric job, and the core of this pass.**
   - Every generated element must touch its neighbours face to face, with no intersections (no overlapping solids).
   - Where elements meet, one is cut at a specific plane by a rule, using the kernel `Mesh::cut_by_plane` / `BRep::cut_by_plane` and the wood `cuts` split modifier on Column/Beam/Block. For plates, use parametric outline cuts.
   - Joints to define as small, general rules, not per-case code:
     - column ↔ level (on the deck, or through with beams framing into it)
     - column ↔ head
     - girder ↔ column/head/core wall
     - purlin ↔ girder (flush, hung, as FAST+EPP, or stacked)
     - beam ↔ beam at any angle (mitre, through/butt)
     - deck ↔ beams/columns/core (holes, notches)
     - core wall ↔ core wall (corners)
     - wall ↔ deck
     - perimeter at non-orthogonal angles
     - tapered-level transitions
   - Prove it for every example:
     - a clash check: pairwise solid overlap volume ≈ 0; write the check as a reusable test/tool
     - contacts found for every element (`compute_contacts`)
     - screenshots
   - Study how Branch3D, FAST+EPP and compas_grid handle joints; they are known to be schematic or overlapping (see the references: Branch girders drop 8 in so purlins cut into them, purlins run through core voids). Do better.
5. **Keep from earlier decisions:**
   - kernel Graph double attributes for semantics
   - instancing readiness (deterministic world-space elements; `instance_by_key()` dedups)
   - no colours (default grey transparent)
   - Beam/Column profiles (rectangular, W, HSS, round, double, slab band, T) as Part E describes
   - house style (session-format / session-comments skills)
   - examples with CAPS consts and the usage block
6. **Deliverables:**
   - a lean `grid.h`, with any geometry helpers placed where they belong (kernel geometry → kernel, wood types → wood)
   - examples for many patterns across workflows A, B and C
   - side-by-side comparisons with Branch, FAST+EPP and crea
   - `wood/docs/templates.md` with screenshots and code
   - updated docs and diagrams
   - screenshots shown to petras in the chat

## Process (Fable)

1. A fresh Branch3D review from all captures (what did we miss?).
2. A critique of the current `grid.h` for leanness.
3. Three competing lean designs: settings-first, axes/graph-first, solid-first. Judge them and synthesise one.
4. Implement it.
5. Clash, contact and comparison verification, looping until clean.
6. Docs and screenshots.
