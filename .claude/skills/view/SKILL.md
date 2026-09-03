---
name: view
description: Publish the current wood scene to the live viewer at https://petrasvestartas.github.io/session/. Use when asked to publish, update the viewer, push a scene, or see the geometry live.
model: haiku
context: fork
background: false
allowed-tools: Bash
---

Run exactly this, and reply with the command's output verbatim - the single line it printed,
copied character for character. Nothing added, nothing summarised, nothing rephrased. The script
already decides what the line says; a run that describes the scene in its own words instead is
the bug this instruction exists to prevent.

```bash
bash/publish_scene.sh
```

The script builds `main_face_to_face`, runs it, uploads the `wood/data/output/pb/live.pb` it
wrote to the R2 bucket the viewer reads, and tells the open pages. On success it prints one line
naming the key, its size, the file's short md5, and whether the viewer was notified - or
`unchanged - nothing published` when the bytes are identical to what is already live. On failure
it prints the build or run log and exits non-zero - pass that through as it is too.
