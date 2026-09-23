# Design: element instancing across the session stack (kernel, WoodSession, viewer, grid examples)

This is a read-only design; nothing was edited, built or run. Line numbers are from the working trees as they stand now. Several target files are dirty because other agents are editing them (§7.0), so expect line drift.

## 0. Decisions

| # | Decision | Rejected alternative and why |
|---|---|---|
| D1 | **Definitions live in the kernel**: `Session::definitions` (an `Objects`) plus `definition_lookup`. Proto `Session.definitions = 8`, mirrored as `wood_proto.WoodSession.definitions = 8`. Definitions are not in `order()`, the tree, the graph or `xforms`. | A wood-only `definitions = 102` field: the viewer and Python/Rust could not resolve instances. |
| D2 | **Instances are the existing `InstanceRef`**, made a first-class `Geometry` variant stored in `Objects::instances` (proto `Objects.instances = 18`). They go through `_add_object`, so they get a lookup entry, a tree node named by the guid, a graph node `"instance_<name>"`, and history. | A `wood_session::Instance : Element` subclass (the wood survey's idea): Rust has no subclassing, every consumer would have to special-case `element_type "InstanceRef"`, and it gives two representations of one concept. |
| D3 | **Placement has one source: `Session::xforms[instance_guid]`** (LOCAL to the tree parent, composed by `world_xforms()`). `InstanceRef::xform` stays so the proto change is additive, but inside a Session it is always identity. `add_instance` and the loaders fold it into `xforms`, and `to_proto` skips it when it is identity. | Placing by `InstanceRef.xform`: the viewer gizmo (`app/edit.rs:46-112`), undo (`XformOp`) and group xforms all already go through `xforms`. |
| D4 | **Per-instance data**: guid, name, colour (with a flag bit), flags, and a new `repeated ElementFeature features = 7` stored in the definition's (local) frame. Shared data (mesh/brep, type parameters, cuts, geometry features) stays on the definition. | |
| D5 | **Wood passes run on world views, not on stored copies.** `world_elements<T>()` returns live elements for identity-placed elements. For instances it returns transient typed views: the parameters moved, the definition's cached outlines and planes moved, and **never a mesh**. Results go into Interactions (world coordinates, keyed by the edge between instance guids) and into `InstanceRef::features` (local). Only plate joinery **promotes** an instance to a real element. | Resolving by `clone()`: the Element copy constructor deep-copies `_geometry` (`element.cpp:203-206`). |
| D6 | **Dedup**: `WoodSession::instance_by_key(key_of = element_key)` calls a new kernel `Session::to_instance(guid, definition_guid, frame)`. The guid, name, tree node and graph edges are kept, so existing interactions stay valid. | Geometric duplicate search. |
| D7 | **Viewer in three stages.** A: decode, rows, and walk the definition per instance (correct, no GPU saving). B: each definition walked once into the existing arenas under a `DEF_BIT` row sentinel, plus a per-instance **slot vertex buffer** (`VertexStepMode::Instance`); slot 0 is `DEAD` so the existing full-buffer draws kill definition geometry, and one instanced draw per definition batch runs at the three draw funnels. C: a batch table for ink-visibility projection. | Putting slots in a bind group: it adds one storage buffer to every vertex stage, and the face vertex stage already uses 6 of 8. |

## 1. Kernel data model

### 1.1 Where things live (C++ first; Python and Rust mirror it)

**`session.h:53-65`**, new members:
```cpp
Objects definitions;                                         // Shared geometry that instances place, each in its own frame; never in order(), the tree, the graph or xforms.
std::unordered_map<std::string, Geometry> definition_lookup; // Definitions by guid.
```
- Python: `self.definitions = Objects()` and `self.definition_lookup: dict[str, Any] = {}`.
- Rust: `pub definitions: Objects` with `#[serde(default)]`, and `#[serde(skip)] pub definition_lookup: HashMap<String, Geometry>`. The Rust `Rc` in `lookup` and in `objects` can diverge; see `objects_synced` at `session.rs:1359-1386`.

**`objects.h:66-78`**, a new list (with its copy constructor, `operator=`, JSON, proto and `str` updated):
```cpp
std::shared_ptr<std::vector<std::shared_ptr<InstanceRef>>> instances; // Instances, each placing a definition by guid.
```

**`objects.h:154-165`**: add `std::shared_ptr<InstanceRef>` to the `Geometry` variant. In Rust, add `Geometry::InstanceRef(Rc<InstanceRef>)` at `session.rs:17` with arms in `guid()` and `name()`. The exhaustive `match` then lists every Rust site to update, the viewer's included.

**`session.h:35-48` `COLLECTIONS`**: insert `{"instances", "instance"}` after `{"elements","element"}` and before `components`.
- `order()` (`session.cpp:185-224`) appends an instances loop after elements.
- `with_collection` (`session.cpp:16-41`) gets an `"instances"` branch.
- `_index_objects` (`:1007-1047`) indexes instances into `lookup` and definitions into `definition_lookup`.
- Files without instances keep the same `order()`, the same `_xforms_ordered()` (`:1059-1082`) and the same `.pb` bytes: an empty repeated field writes nothing.

**`InstanceRef`** (`instance_ref.h`, `.proto`, `.py`, `.rs`):
```cpp
std::vector<ElementFeature> features;        // Per-instance features in the definition frame, drawn after the definition's own.
static constexpr uint32_t FLAG_HIDDEN = 1;   // Not drawn.
static constexpr uint32_t FLAG_LOCKED = 2;   // Not selectable.
static constexpr uint32_t FLAG_COLOR = 4;    // color overrides the definition's.
```

Proto changes (all additive):
```proto
// instance_ref.proto (add: import "element.proto")
Xform xform = 4;                       // Unused inside a Session, where Session.xforms places the instance; identity is not written
repeated ElementFeature features = 7;  // Per-instance features in the definition frame
// objects.proto (add: import "instance_ref.proto")
repeated InstanceRef instances = 18;   // Instances; each places a definition of Session.definitions
// session.proto
Objects definitions = 8;               // Shared geometry instances place, each in its own frame; absent when there is none
// wood/src/proto/wood_session.proto — MANDATORY, prost and Python drop unknown fields
session_proto.Objects definitions = 8;
```

Wire rules, the same in all three kernels:
- `InstanceRef::to_proto` (`instance_ref.cpp:147-161`) writes `xform` only when it is not identity, and `color` only when `flags & FLAG_COLOR`.
- `from_proto` must default an absent colour to `Color::white()`. Today `Color::from_proto` of an absent message gives `(0,0,0,0,"")` (`color.cpp:236-244`), which breaks round-trip equality.
- An absent xform already loads as `Xform()`. The name comes back `""`; check that `Xform::operator==` ignores the name.
- `Session::pb_dumps` (`:740-760`) writes `definitions` only when it is non-empty. `jsondump` (`:670-691`) writes a `"definitions"` key only when it is non-empty. Old files and their outputs stay byte-identical.
- `Objects` JSON writes `"instances"` always, like its other lists. Loaders default a missing key to empty: `data.contains` in C++, `.get` in Python, `#[serde(default)]` in Rust.
- Fix `InstanceRef::jsonload`, which throws on a missing key (`instance_ref.cpp:118-127`): default `features` and `flags`.
- Load fold: after `pb_loads` or `jsonload` have read the xforms, move any non-identity `instance.xform` into `xforms[guid] = xform(guid) * instance.xform` and reset it to identity.

Regenerate all generated code: `session_cpp/generated/*.pb.*`, `session_py/proto/*_pb2.py` (grpcio-tools 1.80.0), `session_rust/src/proto/session_proto.rs`, and `wood/generated` (target `wood_regen_proto`, `wood/CMakeLists.txt:170-177`).

### 1.2 Tree, graph and xforms

| | Definition | Instance |
|---|---|---|
| `lookup` | no (`definition_lookup`) | yes, `Geometry::InstanceRef` |
| tree node | none | named by the instance guid, under `parent` or the root |
| graph node | none | `"instance_" + name`; no consumer parses the prefix (grep of wood and viewer) |
| `xforms` | refused: `set_xform` ignores a definition guid | LOCAL; world = `world_xforms()[guid]`; group xforms compose (`session.cpp:250-277`) |
| `order()` / `_xforms_ordered` | no | after elements |
| `get_object<T>` / `select_by_type<T>` | no | only as `InstanceRef`; document that they never return an instance as `T` |

**Per-instance cost (estimated).**
- On the wire: InstanceRef about 100 B, XformEntry about 180-220 B, TreeNode about 80 B, graph vertex about 100 B, so roughly 0.5 KB.
- For comparison, `floor_model.pb` element blobs run 1.1-25 KB each.
- In memory: about 1.2 KB per instance, against 3-5 KB for an empty `Element` base plus its mesh or brep.

### 1.3 History and undo

- **Instances** use the generic `AddOp` / `RemoveOp` / `ReplaceOp` / `XformOp`. A tombstone clones only the `InstanceRef` (about 0.5 KB), never the definition.
- **Definitions** get one new op in `history.h:98-134`:
  ```cpp
  /// A definition added (nullopt before), removed (nullopt after) or replaced.
  class DefinitionOp { public: std::string kind = "definition"; std::string guid; std::optional<Item> before; std::optional<Item> after; DefinitionOp(const std::string& guid, const std::optional<Item>& before, const std::optional<Item>& after); std::string str() const; std::string repr() const; };
  using Op = std::variant<AddOp, RemoveOp, ReplaceOp, XformOp, DefinitionOp>;
  ```
  `_revert` / `_apply` (`history.cpp:211-245`) call `session._define(guid, clone(before or after))`.
- **Required fix, `history.cpp:7-31`**: `clone()` calls `std::make_shared<P>(*live)`, which **slices** Plate, Beam, Column and Block when `P = Element`. For Element use `live->clone()` and then restore the guid. Also restore `ElementFeature` guids: the copy constructor drops them (`element.h:42-44`), and `erase_contacts` finds contact features by guid (`wood_session.cpp:260-264`).
- **Conversions** (`to_instance`, `explode`) are recorded as `RemoveOp` (a `_detach`) plus an `AddOp` that carries the detached `node`, `edges`, `parent_guid`, `index` and `xform`. The existing `Tombstone` already has all these fields (`history.h:26-52`), and `_attach` (`session.cpp:933-978`) restores them. Undo therefore puts the old object back at its exact list index with the same tree node and edges. No new op and no change to `_swap` are needed.
- `remove_definition` is refused while any instance names the definition. A UI "delete block" does `begin`, `remove_object` on each instance, `remove_definition`, `commit`: one undo step.
- Orphans (an instance whose definition is missing on load) are kept, skipped when resolving, and reported by `definition_of` returning `nullopt`.

## 2. Kernel API

C++ goes in `session.h`, in the "Geometry management" block after `add_element` (`:227`). Python and Rust use identical names and parameter order.

```cpp
/// Add a definition, geometry in its own frame that instances share; returns its guid, the stored one when that guid is already defined, "" for null or an InstanceRef.
std::string add_definition(const Geometry& definition);

/// Add an instance under parent, placed by xform relative to the parent; nullptr when null or its definition_guid names no definition.
std::shared_ptr<TreeNode> add_instance(std::shared_ptr<InstanceRef> instance, const Xform& xform = Xform::identity(), std::shared_ptr<TreeNode> parent = nullptr);

/// The definition an instance places; nullopt when guid is no instance or its definition is missing.
std::optional<Geometry> definition_of(const std::string& instance_guid) const;

/// Guids of every instance of a definition, in objects.instances order.
std::vector<std::string> instances_of(const std::string& definition_guid) const;

/// One object in world placement, as a copy: an instance becomes its definition moved by the world transform, carrying the instance's guid, name and features.
std::optional<Geometry> world_geometry(const std::string& guid) const;

/// Swap the geometry of a definition, which keeps its guid, so every instance of it changes at once; false when guid is no definition.
bool replace_definition(const std::string& guid, const Geometry& definition);

/// Remove a definition; false while an instance still names it.
bool remove_definition(const std::string& guid);

/// Turn an object into an instance of a definition, keeping its guid, name, tree node and edges; frame maps the definition onto the object and is folded into its local transform.
bool to_instance(const std::string& guid, const std::string& definition_guid, const Xform& frame);

/// Turn an instance into a standalone copy of its definition in the definition frame, keeping its guid, name, features, transform, tree node and edges.
bool explode(const std::string& instance_guid);

private:
/// Set or drop (nullopt) a definition under guid, unrecorded.
void _define(const std::string& guid, const std::optional<Item>& definition);
```

Rust (`&mut self` for mutators; `xform` by value, as `set_xform` takes it at `session.rs:813`):
```rust
pub fn add_definition(&mut self, definition: Geometry) -> String
pub fn add_instance(&mut self, instance: InstanceRef, xform: Xform, parent: Option<&Rc<RefCell<TreeNode>>>) -> Option<Rc<RefCell<TreeNode>>>
pub fn definition_of(&self, instance_guid: &str) -> Option<Geometry>
pub fn instances_of(&self, definition_guid: &str) -> Vec<String>
pub fn world_geometry(&self, guid: &str) -> Option<Geometry>
pub fn replace_definition(&mut self, guid: &str, definition: Geometry) -> bool
pub fn remove_definition(&mut self, guid: &str) -> bool
pub fn to_instance(&mut self, guid: &str, definition_guid: &str, frame: Xform) -> bool
pub fn explode(&mut self, instance_guid: &str) -> bool
```
Python: `add_instance(self, instance: InstanceRef, xform: Xform | None = None, parent: TreeNode | None = None) -> TreeNode | None`; the other methods mirror Rust.

**Semantics**
- `add_instance`:
  1. Composes `xform * instance->xform` and resets `instance->xform`.
  2. Calls `_add_object("instances", instance, "instance", parent)`.
  3. Calls `set_xform(guid, composed)` when the result is not identity, so a transaction records one `AddOp` and one `XformOp`.
- `to_instance`:
  1. `old = xform(guid)`; record `r = _detach(guid)`.
  2. Build `InstanceRef` with guid = guid and name = the object's name.
  3. Record `AddOp(guid, inst, "instances", size, r.xform, r.parent_guid, r.index, r.node, "instance_"+name, r.edges)`, then `_attach`.
  4. `set_xform(guid, old * frame)`.

  The composition is correct: if the object is `G = frame·D` under local `L`, its world is `P·L·frame·D`. The object's own features are **not** carried by the kernel; wood carries the ones it wants (§3.4).
- `explode`:
  1. `_detach(guid)`.
  2. Copy the definition with `clone()` (virtual for Element) and restore guid and name. On an Element, append the instance's features. On a Mesh or BRep, the features are dropped (documented).
  3. Build an `AddOp` into the definition's collection with the instance's node, edges and xform, then `_attach`.

  The geometry stays in the definition frame; the kept xform places it.
- `world_geometry` / `get_geometry()` (`session.cpp:287-312`): `get_geometry` keeps being the heavy baked export.
  1. For each instance: clone the definition, set guid, name and features, then `place(world)` for an Element or `transform(world)` otherwise.
  2. Push the result into `out.meshes`, `out.breps` or `out.elements`.
  3. Clear `out.instances`.
- **`Element::place` must become `virtual` and correct** (`element.cpp:354-357`). Today it moves only `_geometry`. It must also move `_features[*].outlines` (restoring the feature guids), `_insertion_vectors` (rotation part) and then `reset()`. Wood types override it to move their members (§3.2). This also fixes an existing bug in the three kernels (`element.py:574`, `element.rs:639`).
- **Required small fix: `set_polylines` / `set_planes` must stick** (`element.cpp:374-380`). Add `_is_dirty = false;`. Without it, `polylines()` recomputes and overwrites a seeded cache (`:305-313`). Wood views rely on this.
- **Boxes** (`_compute_boxes`, `:1084-1103`): for an instance, compute `local = compute_bounding_box(definition, identity)` once per definition per call (a local map), then `box = local; box.transform(world)`.
  - Also fix `compute_bounding_box`'s element branch (`:550-556`): `Element copy = **element` slices the element and deep-copies its mesh. Use `std::shared_ptr<Element> copy = (*element)->clone(); OBB box = copy->aabb();`.
  - The public static `compute_bounding_box(InstanceRef, xform)` returns the origin box. Document it.
- **Rays** (`_ray_intersect_geometry`, `:1115-1214`): for an instance, recurse with the definition and the same `placement`. The Mesh branch already inverse-transforms the ray; Element and BRep still return `nullopt`, as they do today.

## 3. WoodSession

### 3.1 Data

No new stored element type. Definitions go to the kernel `definitions`, instances to `objects.instances`. Add one in-memory index to `wood_session.h`, rebuilt lazily from the definitions and never written:
```cpp
std::unordered_map<std::string, std::string> definition_keys; // Class key -> definition guid; rebuilt from definitions on first use, never written.
```

### 3.2 Wood element changes (`wood_elements/*.h`, `*.cpp`)

Each type gets a light typed copy and a correct `place`:
```cpp
/// A copy moved by xform built from the parameters alone: axis, section and cuts moved, no mesh or brep until one is asked for.
std::shared_ptr<Column> transformed(const session_cpp::Xform& xform) const;
/// Move the parameters and drop the four geometry caches.
void place(const session_cpp::Xform& xform) override;
```

| Type | Moved | Care |
|---|---|---|
| Column | `axis`, `section`, `cuts` | |
| Beam | `axis`, `directions`, `cuts` | **Fill missing `directions[i] = xform·z`**: without it, a segment with no direction uses world z (`beam.cpp:88`, `element_geometry.cpp:39`), which is wrong under a non-z rotation. |
| Block | `loops`, `cuts` | |
| Plate | `polylines`, `planes` (`Plane::transform`), `features.top/bottom`, insertion vectors; keeps `thickness`, `reversed`, `feature_types` | **Never re-run the constructor**: it picks side-plane axes by world-axis tests (`plate.cpp:56-78`), and `face_overlap_area` projects onto those axes (`contact_detection.cpp:172-179`). |

The copy must set `guid()` and `name` explicitly, because a construction mints a new guid. Reject `det(xform) < 0` in wood: a mirror flips winding and `reversed`.

### 3.3 WoodSession API

These go in `wood_session.h`, in the "Elements" block (`:198-250`). Add `using Session::add_definition; using Session::add_instance;` so the overloads do not hide the kernel ones.
```cpp
/// Session::add_definition for an element in its own frame; returns the guid already stored under key when key is not empty and was seen.
std::string add_definition(std::shared_ptr<session_cpp::Element> definition, const std::string& key = "");

/// A light placement of an element definition with its own guid and name; nullptr when definition_guid names no element definition or xform mirrors.
std::shared_ptr<session_cpp::TreeNode> add_instance(const std::string& definition_guid, const session_cpp::Xform& xform, const std::string& name = "", std::shared_ptr<session_cpp::TreeNode> parent = nullptr);

/// A light world copy of one instance: its definition's parameters moved by world, the instance's guid, name and features, the definition's cached outlines and planes moved and seeded; lofts nothing.
std::shared_ptr<session_cpp::Element> world_view(const std::string& guid, const session_cpp::Xform& world) const;

/// Every element and element instance in order() sequence as world geometry: an element placed by identity is itself, anything else a world_view.
std::vector<std::shared_ptr<session_cpp::Element>> world_elements() const;

/// world_elements() of type T, instances included as views of T.
template <class T> std::vector<std::shared_ptr<T>> world_elements() const;

/// Put a feature given in world coordinates onto the element or instance guid names, moved into its own frame.
void host_feature(const std::string& guid, session_cpp::ElementFeature feature);

/// Replace each element key_of finds a class for by an instance of that class's definition, keeping guid, name, tree node, edges and its contact and joint features; returns the number made.
size_t instance_by_key(const std::function<std::optional<std::pair<std::string, session_cpp::Xform>>(const session_cpp::Element&)>& key_of = element_key);

/// Write a pass's world view back: an instance is exploded and replaced by the view moved into its frame, an element replaced the same way.
void promote(const std::shared_ptr<session_cpp::Element>& view);
```
Free function in a new file `wood/src/joinery_solver/wood_instance.{h,cpp}`. That file also holds the definitions of the members above, which keeps them out of the dirty `wood_session.cpp`. It needs one line in the explicit source list at `wood/CMakeLists.txt:~105`.
```cpp
/// The class key of a wood element and the frame that maps its canonical local copy onto it; nullopt for a type without a canonical frame.
std::optional<std::pair<std::string, session_cpp::Xform>> element_key(const session_cpp::Element& element);
```

Canonical frames, all right-handed with `y = z × x`, so a mirror automatically gets a different key:

| Type | Frame | Key |
|---|---|---|
| Column | origin `axis.start`; z along the axis; x from the first edge of `section`, made perpendicular to z | type, local section points, local axis end, local cuts |
| Beam | origin `axis[0]`; x along the first segment; z from `directions[0]`, or world z made perpendicular | type, radii, local axis, local directions, `allowed_type`, local cuts |
| Block | origin is the first point of `loops[0]`; x along its first edge; z its normal | type, local loops, local cuts |
| Plate | origin `polylines[0][0]`; x along its first edge; z the normal of `planes[0]` | type, local bottom/top, thickness, reversed, feature_types, local insertion vectors, local merged features |

Numbers are rounded to 3 decimals and `-0` is normalised. Keys are conservative: a value straddling a rounding boundary or an ambiguous frame yields more definitions, never a wrong instance. Correctness follows because a wood shape is a pure function of its parameters in the local frame.

### 3.4 How each pass uses instances

| Pass (today) | Instanced |
|---|---|
| `compute_face_contacts(level)` (`wood_session.cpp:266-291`) iterates `*objects.elements` and forces `element->geometry()` (:284) | Iterate `world_elements()`. Force `geometry()` only on live elements: views are seeded, and forcing one would loft a mesh. Branching by tree node already works on instance guids (:277). `is_plate` / `contact_type` still work because the views are typed (`dynamic_cast<const Plate*>`, `contact_detection.cpp:25`). |
| `compute_line_contacts` (:371-404) | `world_elements()` |
| `compute_cross_contacts` (:342-369), public `Plate` members | `world_elements<Plate>()` |
| `compute_axis_contacts` / `compute_beam_features` (:293-338) | `world_elements<Beam>()`; the joint feature on `beam_a` goes through `host_feature` |
| `place_contact` (:463-472), `add_feature` host sides (:512-518) | `host_feature(guid, f)` |
| `compute_features` (`wood_feature_solver.cpp:555-587`) mutates plates (`flip()` :489, insertion-vector reverse :565-570, `features.top/bottom` :506-531) | Run on `world_elements<Plate>()`. **After `merge_features` and before the host `add_feature`**, `promote()` every view that appears in a pair. A jointed plate is unique anyway. |
| `drop_features` / `set_features_visible` / `erase_contacts` (:201-219, :260-264) | Also walk `objects.instances[*]->features` |
| `element_guids()` (:706-715) | The guids of `world_elements()`, the solver's index space |
| `get_element<T>` (h:212-220), `str()` / `repr()` | Unchanged for live elements; `str()` falls back to `lookup` for instance names; `repr` adds `instances=` |

`host_feature` works like this:
1. `w = world_xform(guid)`.
2. If `w` is not identity, move the outlines by `*w.inverse()` and restore the feature guid.
3. For an `InstanceRef`, push onto `features` (in Rust, through `Rc::make_mut` and then resync `lookup`). Otherwise call `add_feature`.

**Keying.**
- Graph edges, `interactions`, `_edges` and `add_contact(a, b)` use instance guids unchanged.
- Interaction records stay in world coordinates.
- Face indices are the definition's face order, the same for every instance.
- Moving an instance after solving leaves stale contacts, as it does for elements today.

**`world_view` cost.**
- It calls `definition->geometry()` once; the definition is cached and lofted a single time.
- Per instance it moves 6-20 polylines and planes (about 6 KB for a box), held only for the duration of the pass.
- It dispatches on the definition type with `dynamic_pointer_cast`; any other Element falls back to `clone()` plus `place()`.

**Dedup algorithm** (`instance_by_key`), as one `begin("instance by key")` … `commit()`:
1. Snapshot `element_guids()`.
2. For each live element placed by identity, compute `key_of` → `(key, frame)`.
3. For an unseen key: `local = typed transformed(*frame.inverse())` gets a new guid and is added with `add_definition(local, key)`.
4. `carried` = the element's `"contact"` / `"joint"` features moved by `frame⁻¹`, guids kept.
5. `to_instance(guid, def, frame)`, then set `instance->features = carried`.

Run it before the contacts to get the cleanest result; running it after also works.

### 3.5 Serialization

- `WoodSession::pb_dumps` (`wood_session.cpp:642-651`): the kernel writes definitions (each lofted once through `Element::pb_dumps`, `sc/element.cpp:608`) and instances. Views are never written.
- `pb_loads` (:107-128): unchanged. `register_element_types()` runs first, so `Objects::pb_loads` of `definitions` is polymorphic (`objects.cpp:336`), and interactions reattach by edge guid.
- The C++ JSON element load is **not** polymorphic (`objects.cpp:253`). Definitions reloaded from JSON come back as base Elements. This is an existing limitation; document it.
- Instance features must never use `"cut"` or `"joint_type_*"` types, which `Plate::from_element` reads back as merged features (`plate.cpp:124-146`). This applies only to definitions, but state it.

## 4. Viewer (`session/session_viewer/src`)

### Stage A: correct first, no shader change

| File | Change |
|---|---|
| `app/decode.rs:92-119` | Convert `o.instances` (InstanceRef `from_proto` → `Geometry::InstanceRef`) and `p.definitions` into `s.definitions` / `s.definition_lookup`. The `convert!` macro (`:28-55`) needs a target-lookup parameter. Fold legacy instance xforms. **Without this, instances are silently dropped.** |
| `app/validate.rs:170-230` | Count instances and definitions against the limits. An orphan is skipped, not rejected. |
| `app/walk/mod.rs:130,136` | `is_drawable(InstanceRef)` → false; `walk_geometry` arm → `Row::thin(AABB::empty())` (the scene handles instances). |
| `app/scene.rs:301-415` (`add_file`) | For `Geometry::InstanceRef`: look up the definition (skip if missing or not drawable); seed `hidden`, `locked` and `colors` from `flags` / `color`; `push_row(doc, instance_guid, placement(world, place, guid), flags)` (`:267`); walk the **definition** with `cx.row = row`; walk the instance's own features as ribbons in the same row; leave `mesh_previews` / `surface_previews` as `None`. |
| Exhaustive matches | `selection.rs`, `layers.rs`, `inspection.rs`, `inspection/source_memory.rs`, `deform.rs` (3), `splitting.rs` (3), `mesh_preview.rs`, `surface_preview.rs`, `state.rs`. Add arms: not editable, no preview. |
| Edits | A geometry edit on an instance row runs kernel `explode(guid)` and then `rebuild` (`scene.rs:218`), one undo step. `delete_row` → `remove_object(instance)`; gizmo → `set_xform` (`app/edit.rs:46-112`), unchanged. |
| Save | `session_io.rs:63` already calls session_rust `pb_dumps()`, so instances save once the Rust kernel supports them. |

### Stage B: one upload per definition

- **New file `engine/gpu/instanced.rs`:**
  ```rust
  pub const DEF_BIT: u32 = 0x8000_0000; // row id stamped on definition geometry: DEF_BIT | batch
  pub const DEAD: u32 = u32::MAX;       // slot 0: definition geometry in a plain draw dies
  pub struct Batch { pub faces: Range<u32>, pub pipes: Range<u32>, pub ribbons: Range<u32>, pub slots: Range<u32> } // shared ranges, then this definition's instance slots
  pub struct Instanced { slots: GrowBuf /* u32 row per slot, [0] = DEAD */, batches: Vec<Batch>, batch_of_row: Vec<u32> /* u32::MAX = plain */ }
  ```
- **`scene.rs` `add_file`:**
  1. Walk each drawable definition **once** into the existing `Upload` with `cx.row = DEF_BIT | batch`. `patch::Counts` / `Span` (`patch.rs`) already give the ranges.
  2. For each instance, `push_row`, copy bounds, faces and spacing from the definition walk's `Row`, and append the row to `batch.slots`.
  3. Glyphs (feature dots, vertex markers) are copied per instance with the instance row: spheres already use `instance_index` as the glyph index (`glyphs.rs:209`), so they cannot be instanced.
  4. Mesh, BRep and Element definitions go this way. Any other definition type falls back to the Stage A per-instance walk.
- **Shaders.**
  - `scene.wgsl` gets `fn resolve_row(id: u32, slot: u32) -> u32 { if ((id & DEF_BIT) == 0u) { return id; } return slot; }`; `DEAD` → dead vertex, the same path as `FLAG_HIDDEN`.
  - `VsIn` gains `slot` from `@location(K) slot: u32`, an instance-step vertex attribute.
  - `triangle.wgsl:92` resolves `face_objects[vertex]`.
  - `ribbon.wgsl:134-267` resolves every `seg.instance_id`, the neighbours at :160-162 included.
- **Pipelines** (`engine/pipelines/mod.rs:197` next to `instance_id_layout()`): add `slot_layout()` = `VertexBufferLayout { array_stride: 4, step_mode: VertexStepMode::Instance, attributes: [Uint32 @ K] }` to every face, segment and mask pipeline. **Check the exact wgpu 29.0.4 spelling with the `session-viewer-wgpu` skill before writing it.**
- **Draw funnels.** Each binds the slot buffer; the plain draw stays unchanged and reads slot 0 = DEAD, then one draw runs per batch:
  - `faces.rs:248-268` `Faces::draw`: `pass.draw(b.faces.start*3..b.faces.end*3, b.slots.clone())`.
  - `segments.rs:~473-488` `draw_table`: `pass.draw(RIBBON_VERTS*b.pipes.start..RIBBON_VERTS*b.pipes.end, b.slots.clone())`, and the same for ribbons.
  - `arena.rs:~234-251` `draw_run` (masks): `draw_indexed(range, 0, b.slots.clone())`.
  - Print and text lanes are never instanced.
- **Pick.**
  - `faces.rs:160-176` `source` / `address` accept `parent == DEF_BIT | batch_of_row[row]`; `scene.rs:665` `edge_at` does the same.
  - The `selected_face` uniform becomes `[face, row, 0, 0]` and `triangle.wgsl:~108` compares both.
  - `ribbon.wgsl:197` compares the resolved row. Otherwise selecting a face lights it on every instance.
- **Hide, colour, select, lock**: all per row (`scene.rs:267-287`, `objects.rs:560,596`, `mod.rs:439`), so they work per instance unchanged.
- **Sweeps**: `bounds.rs` `is_planar` / `mark_sheet` must skip batch ranges, because definition geometry sits at its local origin and `mark_sheet` rewrites segment radii.
- **Ink visibility** in Stage B: when any batch exists, force the existing physical-depth fallback (`triangle_tiles.rs:~265`).
- **Memory counters.**
  - `inspection.rs:50-54` adds `definitions`, `instances`, `instanced_vertices` (definition vertices, counted once), `drawn_triangles` (plain + Σ nᵢ·tᵢ).
  - `Gpu::allocated_bytes` (`mod.rs:134`) includes the slot buffer.
  - `source_memory.rs` counts each definition payload once plus `InstanceRef` per instance (it already dedups `Rc` by pointer at :83-127).

**Per-instance GPU cost**: `Instance` 96 B + translation 16 B + slot 4 B. A box element today costs about 1.7 KB (24 verts × 44 B, 12 tris × 16 B, 12 pipes × 40 B); a tessellated BRep costs tens of KB.

### Stage C: ink visibility for instances

- A batch table `{first_global, tri_start, tri_count, slot0, n}` in `project_triangles.wgsl` (`:87-125` today reads `physical_objects[...]`).
- `requested_triangles` at `render.rs:44` becomes plain + Σ nᵢ·tᵢ.
- The instanced primitive id becomes `first_global + (instance_index - slot0)·t + local + 1` (`triangle.wgsl:93`, read at `ink_visibility.wgsl:245`).
- This is the one cost instancing does not remove: 96 B per *drawn* triangle (`triangle_tiles.rs:11`), capped at 256 MiB (`device.rs:77`).

## 5. Grid examples

**`wood/examples/1_elements_tree.cpp`** (untracked, 76 lines; 3 bays × 13 elements = 39). Two equivalent options:
- **One line**: `wood_session.instance_by_key();` after the bay loop and before `compute_contacts(1)`. Expected result: **5 definitions** (column, head block, x-beam 4400, y-beam 2800, deck) and 39 instances, with guids, groups and contacts all preserved.
- **Direct API**, the teaching form: build the five shapes once in the bay-origin frame, `add_definition`, then place them:
  ```cpp
  const std::string column_def = wood_session.add_definition(std::make_shared<Column>(Line::from_points(Point(0, 0, 0), Point(0, 0, height)), Polyline::rectangle(Point(-column / 2, -column / 2, 0), xaxis, yaxis, column, column)));
  ...
  for (const Vector& offset : corners)
      wood_session.add_instance(column_def, Xform::translation(origin[0] + offset[0], origin[1] + offset[1], origin[2] + offset[2]), fmt::format("column_{}_{}", i, c), branch);
  ```
  `Xform::translation(double, double, double)` exists (`xform.h:97`). Names can differ per instance: no caller passes the `names` filter (`contact_detection.cpp:56-59`).
- **Check**: `compute_contacts(1)` must give the same (v0, v1) pairs and contact polygons as the world version. The file must shrink by at least the geometry share (84% of `floor_model.pb` is `geometry_data`).

**The grid template (`wood/src/templates/grid.h`, `examples/templates_grid.cpp`)** does **not exist yet**. The orchestrator's `grid_design.md` is not written; see the proposed `wood_grid` API in `scratchpad/report_wood_side.md` §7.
- Keep the builders world-space (`to_column`, `to_head`, `to_beam`, `to_floor`) and call `instance_by_key()` once after building.
- Builders that know their class may instead return `(local element, frame, key)` and use `add_definition(def, key)` plus `add_instance`. For large grids that avoids building N world copies first.
- Expected classes per the wood survey §7: column 1-2; head 3-5, related by 90° z rotations; through beam 1-3; butt beam 1 per span; deck up to 4 before joinery.
- Group xforms are allowed but unnecessary: instance xforms place everything, and each instance keeps its own tree node under `storey_k` / `bay_i`.
- Plate joinery on contiguous decks promotes those decks, as expected; columns, heads and beams stay instanced.

## 6. Test plan

**Kernel.** Identical names, logic and line counts in cpp/py/rust, one test per method; run `quicktest.sh <class>` per class, one at a time.
- `InstanceRef`:
  - extend "Constructor" (features, flag constants, `duplicate` new guid);
  - "Json Roundtrip" (features);
  - "Protobuf Roundtrip" (features; identity xform absent; colour default white).
- `Objects`: add instances to the existing json/pb round-trip tests.
- `History`: "Undo Definition".
- `Element`:
  - "Place Moves Features" (outlines and insertion vectors move, feature guids kept);
  - "Set Polylines Sticks".
- `Session`, new tests:
  - "Add Definition": not in `order()`, the tree, the graph or `xforms`; idempotent; rejects an InstanceRef.
  - "Add Instance": tree node named by the guid; attribute `instance_<name>`; `InstanceRef::xform` folded; unknown definition → null.
  - "Definition Of", "Instances Of".
  - "World Geometry": mesh definition, vertex moved, instance guid and name.
  - "Get Geometry Resolves Instances": `out.instances` empty, meshes count = instances.
  - "Replace Definition".
  - "Remove Definition": refused while referenced.
  - "To Instance": guid, node and edges kept; world boxes equal before and after.
  - "Explode".
  - "Undo Instance": add, `to_instance` and `explode` each undo to an identical `order()`, tree string and edges.
  - "Instance Json Roundtrip", "Instance Protobuf Roundtrip".
  - "Get Collisions Instances", "Ray Cast Instance".
  - "Session Without Instances Unchanged": `pb_dumps` of a fixture has no field 8.
- The history slicing fix needs a derived type. Python can subclass; Rust cannot. Cover it in wood (below) and say so, rather than breaking parity.

**Wood** (new `wood/tests/wood_instance_test.cpp`, `ADD_EXE` next to `CMakeLists.txt:266-267`):
- `element_key` equals for translated copies and 90° z-rotated columns and heads, differs for mirrors.
- `transformed` equals `place` on a copy (Beam under an x rotation, Plate members).
- `1_elements_tree` world vs `instance_by_key`: same interaction pairs and contact polygons within tolerance; 5 definitions.
- `pb_dumps` → `pb_loads` round trip: definitions polymorphic, interactions reattached.
- Undo of `instance_by_key` restores Plate/Column types (the history slicing fix).
- Two identical plate instances in contact: `compute_features` promotes both, keeping their guids.
- File size of the instanced tree well below the world version; set the threshold after the first measurement.

**Viewer** (`cargo xtest`; pattern after the placement test at `scene.rs:~803`):
- decode 1 definition + 3 instances → 3 rows, 1 batch, `arena.vert_count` = definition verts (Stage B);
- pick returns the instance guid;
- a face selection lights one instance only;
- per-instance hide and colour;
- save → reload keeps instances;
- counters match the arena (the memory note says counters must match nvidia-smi);
- measure load time and VRAM before and after on the published tree and grid scenes (the performance-priority note).

## 7. Implementation order and file ownership

**7.0 Wait before starting.** The trees are busy:
- The kernel style pass is uncommitted: `session_cpp` has 64 files dirty, including `session.{h,cpp}`, `element.*`, `instance_ref.*`, `tree.*` and `session_test.cpp`; py and rust match. `session_proto/element.proto` is gaining `visible = 6`.
- Wood's `cuts` work touches `wood_elements/*`, `wood_session.{h,cpp}`, `wood_feature_solver.cpp` and `CMakeLists.txt`.
- The viewer feature push (B1-B10) touches `scene.rs`, `walk/mod.rs`, `faces.rs`, `arena.rs`, `render.rs`, `pipelines/*`, `triangle.wgsl` and `ribbon.wgsl`.
- Start each phase only once its files are committed, and `git pull` / `submodule update` first (`session/CLAUDE.md`).
- **Builds run one at a time** (`-j4`, `timeout 10m systemd-run --user --scope -p MemoryMax=6G`), even when the edits run in parallel.

| Phase | Owner | Files | Depends on |
|---|---|---|---|
| 1a | kernel-proto agent | `session_proto/{instance_ref,objects,session}.proto`, then regenerate cpp/py/rust | 7.0 kernel |
| 1b | kernel-cpp agent | `session_cpp/src/{instance_ref,objects,session,history,element}.{h,cpp}` and their `_test.cpp` (all already in `MINITEST_SOURCES`) | 1a |
| 1c, 1d (in parallel) | py agent, rust agent | the same set in `session_py/src/session_py/`; `session_rust/src/` (+`lib.rs` if exports change) | 1b green (C++ is the reference) |
| 2 | wood agent | `wood/src/proto/wood_session.proto` + regenerate; `wood_elements/*` (`transformed`, `place`); `wood_session.{h,cpp}` (declarations, pass switch, `host_feature`); new `wood_instance.{h,cpp}` + one CMake line; `wood_feature_solver.cpp` (promote); `tests/wood_instance_test.cpp` | 1b; wood `cuts` committed |
| 3 | wood agent | `examples/1_elements_tree.cpp`, later `templates_grid.cpp` | 2 (+ grid template) |
| 4 (in parallel with 2) | viewer agent | Stage A files (§4) | 1d; viewer push committed |
| 5 | viewer agent (loads `session-viewer-wgpu`) | new `engine/gpu/instanced.rs`, `faces.rs`, `segments.rs`, `arena.rs`, `render.rs`, `pipelines/mod.rs`, `scene.wgsl`, `triangle.wgsl`, `ribbon.wgsl`, `bounds.rs`, `inspection.rs`, `source_memory.rs`, `scene.rs` | 4 |
| 6 | viewer agent | `triangle_tiles.rs`, `project_triangles.wgsl`, `ink_visibility.wgsl`, `render.rs:44` | 5 |
| 7 (optional) | kernel agent | guid→`TreeNode*` index (`tree.cpp:330` is O(N)), a `_locate` index (`session.cpp:861` is O(N)), wood `get_element` through `lookup` | 1 |

Commit inside each submodule, then a `superproject: <what>` pointer bump. No AI trailers: strip `Co-Authored-By` / `Claude-Session`.

## 8. Risks

1. **Concurrent edits** (7.0) are the biggest risk; every phase touches files that are dirty right now.
2. **Guid churn.** Element and ElementFeature copies mint new guids (`element.cpp:203-206`, `element.h:42-44`). Every view, explode, history clone and moved feature must restore guids explicitly, or `erase_contacts` misses contact features.
3. **History slicing** (`history.cpp:21`). Undo would restore base Elements. It must be fixed in phase 1.
4. **Wrong resolved geometry.** A non-virtual or incomplete `place` gives wrong `world_geometry` / `get_geometry` for wood instances; wood overrides are required.
5. **Two wood element pitfalls.** Beam's world-z default and the Plate constructor's axis choice: always move members, never rebuild.
6. **Mirrored instances.** The viewer's triangle winding and normals are not verified; wood rejects `det < 0`, the kernel allows it. Test a mirrored mesh instance before relying on it.
7. **O(N) scans.** `_locate` and `get_node_by_name` are O(N), so `instance_by_key` over 10k elements is O(N²). That is fine for the examples; phase 7 fixes it for large grids.
8. **wgpu details.** The instance-step vertex buffer on vertex-pulling pipelines and first-instance behaviour for direct draws follow the WGSL/WebGPU spec; they are not checked against naga or wgpu 29.0.4. The storage-buffer count of the ink pipelines was not counted.
9. **Ink visibility** keeps 96 B per drawn triangle; Stage B uses the depth fallback while there are instances.
10. **Instances silently dropped.** Readers that ignore field 8 or 18 lose them: stale `wood_nano` / `compas_wood` bindings, and old viewer builds. This needs a release note.
11. **Interactions are world snapshots.** Moving an instance after solving leaves them stale, as for elements today.
12. **Rust `Rc::make_mut`** on an instance can diverge `lookup` from `objects`; resync after every mutation (`objects_synced`).
13. **JSON output grows** `"instances": []` in every Objects dump; cross-language JSON fixtures regenerate together.

## 9. What I did not verify

- Nothing was built, run or measured. All byte and memory figures are estimates from member lists, plus `floor_model.pb` numbers taken from the kernel survey.
- The "grid buildings" template does not exist in the tree, and `scratchpad/grid_design.md` is not written. §5 targets `1_elements_tree.cpp` and the proposed `wood_grid` API.
- Not checked:
  - whether `Xform::operator==` ignores `name`, which matters for the absent-xform round trip;
  - the exact `session_rust` JSON key order for Session;
  - the full list of viewer shaders reading rows: glyph, sphere, vector and text_outline also reference row fields and must be audited in Stage B;
  - whether any wood caller depends on `element_guids()` order beyond detection;
  - whether `compute_beam_features` writing only to `beam_a` is intended;
  - `validate.rs` limit semantics beyond lines 145-230.
- Line numbers in the dirty files (`session.*`, `element.*`, `instance_ref.*`, `wood_session.*`, viewer engine and shaders) may drift.

Relevant paths:
- `/home/petras/code/code_cpp/wood_research/session/session_cpp/src/{session,objects,history,instance_ref,element}.{h,cpp}`
- `/home/petras/code/code_cpp/wood_research/session/session_proto/{session,objects,instance_ref}.proto`
- `/home/petras/code/code_cpp/wood_research/wood/src/proto/wood_session.proto`
- `/home/petras/code/code_cpp/wood_research/wood/src/joinery_solver/wood_session.{h,cpp}`
- `/home/petras/code/code_cpp/wood_research/wood/src/joinery_solver/wood_elements/`
- `/home/petras/code/code_cpp/wood_research/wood/examples/1_elements_tree.cpp`
- `/home/petras/code/code_cpp/wood_research/session/session_viewer/src/app/{decode,validate,scene}.rs`
- `/home/petras/code/code_cpp/wood_research/session/session_viewer/src/engine/gpu/{faces,segments,arena,render}.rs`
- `/home/petras/code/code_cpp/wood_research/session/session_viewer/src/shaders/{scene,triangle,ribbon,project_triangles}.wgsl`