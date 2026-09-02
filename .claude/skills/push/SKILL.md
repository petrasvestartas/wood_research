---
name: push
description: Commit and push wood, wood_nano, compas_wood in dependency order, then this repo. Use when asked to push the stack.
allowed-tools: Bash
---

```bash
bash/push.sh -m "<message>"
```

Use the message given as the argument. With no argument, run `bash/push.sh` with no flags: it
pushes what is already committed and refuses to start if anything is uncommitted.

Report each repo's result. If it stops - uncommitted changes, a detached HEAD, or a non
fast-forward pull - report exactly that and stop. Never resolve someone's history for them.
