---
docType: review
layer: project
reviewType: tasks
slice: mcp-server
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/226-tasks.mcp-server.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 63f563187b885a9fe67351eb04e8b295e1441b0c
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 106784
cachedTokens: 11198
cacheWriteTokens: 95582
completionTokens: 3822
durationSeconds: 30.7
costUsd: 0.422519
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit markers"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:88"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "`call_tool` dispatch to the detached path is untested"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:132-133"
  - id: F004
    severity: concern
    category: scope
    summary: "No-print AST test is redundant and not in the slice"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:146"
  - id: F005
    severity: note
    category: granularity
    summary: "Task 0.2 discovery list is long but justified"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:59"
  - id: F006
    severity: note
    category: proportionality
    summary: "Task file size matches the slice"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md"
---

# Review: tasks — slice 226

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria trace to tasks

- **Same inputs and JSON results:** tasks 2.1, 2.2, 4.1 and 4.2 cover this.
- **No operation logic, boundary and `ASYNC` lint:** tasks 0.3, 2.2 and 4.3 cover these.
- **Format, lint, pyright and suite pass, CLI tests unchanged:** tasks 1.1, 1.2 and 4.4 cover these.
- **`docs/mcp-server.md` and README link:** task 5.1 covers these.
- **Design tests:** each of the design's D10 test families (same names, same functions, same argv, boundary, off the loop, detached, stdio smoke) has a task.
- **Scope creep:** almost none; the exceptions are in the proportionality findings below.

### [PASS] Sequencing and commit markers

- **Dependencies:** they run forward with no cycles. `HandlePauseCall` is created in 1.1 and used in 2.1 and 3.1. `build_parser()` comes from 1.1 and is used by the tests in 2.1 and 3.1. The SDK names noted in 0.3 are consumed in 4.1, 4.2 and 4.4.
- **Test-with pattern:** each implementation task carries its own tests.
- **Commit markers:** they sit at working, tested points: after the refactor, after the tool table and runner, after detached `handle_pause`, after the server, and after the docs. Markers are plain lines, not checkboxes.

### [CONCERN] `call_tool` dispatch to the detached path is untested

- **The success criterion:** the first one requires `handle_pause` to return a `StartedCall` over MCP.
- **What 4.1 tests:** the `rejected`-style result, the three error mappings, the unexpected exception, an unknown tool name, and `structuredContent` equalling the text block.
- **What 3.1 tests:** `start_handle_pause` in isolation.
- **What 4.4 tests:** the smoke test calls only `decisions`.
- **The gap:** no test drives `call_tool("handle_pause", …)` and checks the `mode` dispatch. The only path that serialises a `StartedCall` through `structuredContent` is also untested.
- **Fix:** add one 4.1 test using a recording fake for `start_handle_pause`. It should assert that dispatch reaches it and that `structuredContent` equals the `StartedCall` JSON.

### [CONCERN] No-print AST test is redundant and not in the slice

- **Where it comes from:** D1 states that nothing in `amoeba.mcp` prints. D10 and the success criteria list no test for it.
- **Why it is redundant:** a stray `print` to stdout corrupts the stdio protocol, so the 4.4 smoke test would fail on it. The 4.3 success line (starts without printing to stdout) also checks it.
- **Fix:** drop the AST test, or enforce it by selecting ruff's `T20` rule in 0.3 instead of writing a test.
- **Related item:** the 4.4 `decisions` call on an empty store is also beyond the design's "lists six tools". It is cheap, so it can stay.

### [NOTE] Task 0.2 discovery list is long but justified

- **What it is:** a single bullet enumerates about 15 symbols to locate.
- **Why it can stay:** it prevents guessing at 222–224's paths, which the project rules require, and it is a read-only task.
- **Not required:** splitting it.

### [NOTE] Task file size matches the slice

- **Size:** one file, six groups and 13 tasks for a slice of effort 2.
- **Why it fits:** each task maps to a named module or decision, and the design specifies the signatures and test names it repeats.
- **Not required:** merging or cutting beyond the item above.

### Run Digest

- Response length: 3959 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 106784 / 11198 / 95582 / 3822 / not computed
- Duration: 30.7 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

## Resolution

- [pass] Success criteria trace to tasks: no change needed.
- [pass] Sequencing and commit markers: no change needed.
- [concern] `call_tool` dispatch to the detached path untested: added a dispatch test to task 4.1 (`handle_pause` reaches only `start_handle_pause`; in-process names reach only `run_in_process`).
- [concern] No-print AST test redundant and not in the slice: removed the test from task 4.3; the stdout-silence success check and the stdio smoke test remain.
- [note] Task 0.2 discovery list long but justified: no change needed.
- [note] Task file size matches the slice: no change needed.
