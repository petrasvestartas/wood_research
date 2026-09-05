---
name: update-session
description: Move session_cpp to the latest kernel and rebuild wood and wood_nano against it. Use when asked to update the session kernel or rebuild the stack.
allowed-tools: Bash
---

```bash
bash/update_session.sh
```

Pass `--no-build` through if asked to update sources only. It takes minutes and rebuilds C++;
run it once and wait. Report the versions it prints, or the first build error if it fails.
