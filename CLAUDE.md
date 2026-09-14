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

## Full session review

`full session review` means: run the `session-reviewer` agent step by step until nothing is
left, one run at a time (its quicktests build), then report once. It runs to completion
however long it takes - never stop early, never skip a class, never ask "continue?" between
runs; the only question is `pushmono` at the end. The gap table is shown, not asked about.

1. `inventory all classes, read-only` → the gap table: missing test files, test-count
   mismatches, API differences, style offenders. Show it to the user, then continue without
   waiting.
2. Fix one class per run, in the dependency order listed in the agent file (tolerance, color,
   matrix … point, vector … polyline … mesh … brep … element … session): a class is only
   touched once every class it contains is green in all three kernels. Each run:
   `fix <class>`; it ends with quicktest green for that class in cpp, py and rust. Never launch
   two reviewer runs at once. Repeat until the table is empty. Re-inventory once at the end to
   prove it.
3. `style pass` over the kernels in the same order. `session_viewer` is a separate project and
   is not reviewed; after the last run that touched `session_rust`, build it once to prove
   nothing broke.
4. One merged report (per class: parity / tests / style / ran), then ask before `pushmono`.

## Claude Code files

- `.claude/skills/` is a clone of github.com/petrasvestartas/skills, gitignored here and
  maintained by hand — never edit it from a session; propose skill text in the reply instead.
- Per-machine state (`settings.local.json`, `CLAUDE.local.md`, lock files) is gitignored in
  every submodule; do not commit it.
- Plans and notes are not read from `.claude/`; keep them in `docs/`.


## Side-notes Claude must ignore, these are user comments only
- Learning: https://master.dev/courses/claude-code/plugins-overview/
- SKILL runs in the main context: type `/name args`, or Claude loads it when its description matches.
- AGENT runs in its own context: say "use <agent-name> to ..." and it returns one report.
- HOOK costs no tokens, only runs a shell command on an event: wire it in `.claude/settings.json`, trigger words like `pushmono` are typed as a prompt.
- AGENT TEAM shares a task list and messages between teammates: say "start an agent team: ..." and the main session leads it.
