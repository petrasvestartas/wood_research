---
name: wood-session
description: If you write or read file for a session using protobuf file use wood_session. Everything related to session file must be done using this file. If functions or classes do not yet exist in wood_session, please add them to this file. 
---

# Existing functionality

Everything below lives in `wood/src/joinery_solver/wood_session.h`, implemented in
`wood_session.cpp`.

- If you have elements and compute contacts between them, write the results using
  `wood_session::write_element_and_contacts(title, elements, contacts, name = "live")`.
  It writes element face outlines under "Inputs" and contact areas under "Contacts",
  and returns the path written. Overloaded for `WoodElement` and `BlockElement`.
- `wood_session::pb_path(name)` is the one place a wood scene's path is spelled out
  (`data/output/pb/<name>.pb`); `wood_session::pb_dump(session, name)` writes one.
  `name` defaults to `"live"`, the file session_viewer watches.
- For a scene that needs more than the above, compose the pieces:
  `add_faces`, `add_contacts`, `add_joints`, `add_lofts`.
- `fill_session(session, elements, joints, include_loft)` is the solver's full
  legacy group layout, for when you want everything the detector produced.