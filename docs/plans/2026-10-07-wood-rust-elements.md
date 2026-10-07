# Wood elements in Rust and the viewer's Element commands (2026-10-07)

The viewer only knows the kernel `Element`. Wood's classes ride inside it: `element_type` names the
class ("Plate", "Beam", "Column", "Solid" for a block, "BeamVariable", "Support") and
`element_data` holds the class's own `wood_proto` message. A typed class reads those two fields
(downcast) and writes them back with its plain solid as the geometry (upcast).

- A. `wood/rust` (crate `wood`): prost-generated `wood_proto` from `wood/src/proto`, session
  messages mapped onto `session_rust::proto`; one file per class with `from_element` /
  `to_element`, behind one `WoodElement` trait (TYPE, solid, base plane). Golden files in
  `wood/rust/tests/data`: C++ -> Rust (element examples' dumps read back field for field) and
  Rust -> C++ (a session written in Rust loaded by `WoodSession` in a wood test).
- B. Plain solids ported from C++ on kernel geometry (`Mesh::loft`, `Mesh::from_polylines`):
  plate loft, beam sweep (mitred square or one-loop profile), column loft, block capped loft,
  variable beam `loft_stations`, support plates, nuts and rod; checked against the C++ meshes.
  Joinery, cuts and solid features stay C++.
- C. Viewer: `Element Plate|Beam|Column|Block|Beam Variable|Support` verbs on the selection
  plus typed numbers, one undo step each, the element on the current layer with its hidden
  base plane under `attributes`. The crate comes in as a git dependency on the wood repo
  (session CI checks out session only), patched to the local checkout for development.
