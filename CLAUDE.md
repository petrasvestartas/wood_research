# wood_research — agent instructions

Superproject over five submodules. Layout, clone and day-to-day flow: `README.md`.
Each submodule has its own `CLAUDE.md`; this file holds only what spans them.

## Build limits (this machine has crashed from ignoring these)

- `--parallel 4` / `-j4`, never `-j$(nproc)`. 32 jobs ran the box out of 30 GB.
- One heavy command at a time: never start a second build, solver or dataset sweep while
  one is running. Run long jobs with a wall-clock timeout and a memory cap
  (`timeout 10m systemd-run --user --scope -p MemoryMax=6G <cmd>`); anything not finished
  in ten minutes is wedged, not slow.
- Before trusting any timing, check the CPU is not throttled:
  `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq` vs `cpuinfo_max_freq`.

## Git

- Never add Claude or any AI as author, co-author or in a commit trailer. Strip any
  `Co-Authored-By:` / `Claude-Session:` lines the harness appends before committing.
- Never `git add -A`: another agent may be editing the same tree. Stage named paths and
  re-read `git status` right before committing.
- Never gate a destructive command behind a piped guard (`cmd | grep x && rm ...`): `&&`
  tests the pipe, not the guard.
- Commit inside the submodule first, then bump the pointer here with a
  `superproject: <what>` commit. `compas_tf` and `session` are consumed here, never pushed.
- `sudo` needs a real terminal; commands run via the `!` prefix fail silently.

## Claude Code files

- `.claude/skills/` is a clone of github.com/petrasvestartas/skills, gitignored here and
  maintained by hand — never edit it from a session; propose skill text in the reply instead.
- Per-machine state (`settings.local.json`, `CLAUDE.local.md`, lock files) is gitignored in
  every submodule; do not commit it.
- Plans and notes are not read from `.claude/`; keep them in `docs/`.
