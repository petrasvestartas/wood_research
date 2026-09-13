# Codex agents

`agents/session-reviewer.toml` is the Codex counterpart of
`.claude/agents/session-reviewer.md`. It follows the
[official custom-agent format](https://learn.chatgpt.com/docs/agent-configuration/subagents#custom-agents):
one TOML file containing `name`, `description`, and `developer_instructions`.
The reviewer uses `gpt-5.6-sol` with high reasoning effort. Permissions inherit
from the parent session.

Start Codex from `wood_research` so the project agent is available:

```bash
cd /home/petras/code/code_cpp/wood_research
codex
```

Then ask:

```text
Use session-reviewer to inventory all classes, read-only.
Use session-reviewer to fix point.
Use session-reviewer for a style pass on session_cpp/src.
Use session-reviewer for a full session review.
```

Starting the reviewer without a mode defaults to a full corrective review: inventory,
fixes, tests, style corrections and final verification. `Review <class>` also means
correct and validate that class. Only explicit `read-only` or `inventory only` requests
stop at reporting. Full reviews run one class at a time in dependency order, with C++
first, then Python and Rust, without asking whether to continue between classes.
Never run two reviewers that edit the kernels simultaneously.

Order corrective passes from foundational types to complex dependents using actual
includes/imports, resolving cycles before progressing. After every class pass, build and
run the full C++, Python and Rust test suites, then build and test the viewer. Every
required build and test must pass before the next class starts. Run heavy commands sequentially
with at most four jobs, a ten-minute timeout and a 6 GB memory cap.

Include Rust debug/release minitests, ordinary feature-enabled tests, separate Rust
documentation tests, and the viewer's wasm/native tests with GPU tests explicitly run.
Fix current/new lint findings; existing findings in later classes remain assigned to
those corrective passes and keep the overall review open.

The active review records each class and its actual validation results in
[`docs/session-review-progress.md`](../docs/session-review-progress.md), with source,
type and test registration coverage in `docs/session-review-inventory.json`.

All-class inventories and full reviews discover classes and modules from the union of
all three source trees, including types sharing a file and modules without tests. The
agent's dependency list is a starting order, not a coverage limit. Reports must account
for every discovered class/module and explicitly label exclusions and unchecked areas.

The agent explicitly reads the existing `session-format` and `session-comments`
references in `.claude/skills/`; keep those available in this checkout. Claude hooks,
settings, and frontmatter are not copied into Codex configuration. Kernel `AGENTS.md`
instructions continue to apply. Source instructions are preserved in the original
Claude file; future changes to that file are not automatically synchronized.

If an already-open chat does not expose the new agent, start a new Codex session
from this directory, or ask it to read the TOML file and delegate a reviewer using
its `developer_instructions`.
