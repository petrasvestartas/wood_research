---
name: pull
description: Fast-forward every submodule to the tip of its branch. Use when asked to pull, sync, or update the stack from the remotes.
allowed-tools: Bash
---

```bash
bash/pull.sh
```

Report what moved. If it reports a skipped or detached submodule, say which and stop - do not
try to move it.
