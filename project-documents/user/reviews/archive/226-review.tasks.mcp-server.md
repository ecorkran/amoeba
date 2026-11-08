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
reviewedSha: 9c4eac61472a7362794505f4a017a5513fdcfa45
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 106692
cachedTokens: 11198
cacheWriteTokens: 95490
completionTokens: 4110
durationSeconds: 33.4
costUsd: 0.42503
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit markers"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:87"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 3.1 is too granular"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:120-123"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Tasks 2.1, 2.2 and 2.3 split one small file into three tasks"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:91-106"
  - id: F005
    severity: concern
    category: dependencies
    summary: "No step confirms the SDK 2.x API names before coding"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:145-151"
  - id: F006
    severity: concern
    category: proportionality
    summary: "Redundant and unanchored tests"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:149"
  - id: F007
    severity: note
    category: clarity
    summary: "Ambiguity in the detached and smoke tests"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:130"
---

# Review: tasks — slice 226

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage

Each success criterion from the slice design maps to tasks:
- **Same inputs and JSON across all six operations:** 2.1–2.4 and 4.1. `handle_pause` is the declared exception and is covered by 3.2.
- **No operation logic, boundary test and `ASYNC` rules:** the 4.3 AST test, the 0.3 `ASYNC` setup and the 2.4 off-the-loop test.
- **Format, lint, pyright and suite pass, CLI tests unchanged:** the "unchanged" success lines in 1.1 and 1.2, the 4.4 checks and the 5.2 step 1.
- **`docs/mcp-server.md` and README link:** 5.1.
- **227 can add an operation with a name, a subcommand and a table row:** structurally covered by 1.1 and 2.1.

Every D10 test (same names, functions and argv, boundary, off the loop, detached, stdio smoke) has a home. No task lacks a design anchor. No NFR is restated in the slice, so no load test or CI-gating task is needed.

### [PASS] Sequencing and commit markers

Dependencies run forward with no cycles: names and wiring, then table and in-process runner, then detached, then server and packaging, then docs. `HandlePauseCall` is created in 1.1 before 2.1 and 3.2 use it. `RequestError` is defined in 2.3 before 3.2 and 4.1 use it. Tests sit with their implementation tasks. Commit markers follow 1.2, 2.4, 3.2, 4.4 and 5.2, each at a working, tested state.

### [CONCERN] Task 3.1 is too granular

Task 3.1 creates one frozen pydantic model and tests a JSON round-trip. That is too small to be its own task. Merge it into 3.2, whose `start_handle_pause` returns `StartedCall`. The 3.2 detached test already exercises the model, so the standalone round-trip test can go.

### [CONCERN] Tasks 2.1, 2.2 and 2.3 split one small file into three tasks

These three tasks all edit `mcp/tools.py`: the table, then `input_schema`, then `prepare_arguments`. Each is a short function with a few assertions. Merge 2.2 and 2.3 into one "schema and argument preparation" task, or all three into one task with sub-items. The slice is "relative effort 2", so the current granularity is heavier than the work needs.

### [CONCERN] No step confirms the SDK 2.x API names before coding

The Context Summary says to confirm `Server`, `on_list_tools`, `on_call_tool`, `stdio_server` and the stdio client names against the installed package. No task item does this. Task 0.2 only records the `mcp` version. The slice says the tool guide describes v1 and the design follows 2.x. A junior AI could code to v1 names from the guide. Add a 0.2 or 0.3 item that checks those names against the installed `mcp` and records the import paths. Alternatively, add it as the first sub-item of 4.2.

### [CONCERN] Redundant and unanchored tests

- **`list_tools` test (4.2):** it asserts six tool names equal to `OperationName` and each with a schema. The 2.1 names test and the 4.4 smoke test, which lists six tools through the real client, already cover this. Cut the 4.2 test, or drop the listing from 4.4.
- **`print(` scan (line 156):** this is not in D10. The 4.3 success line ("starts without printing to stdout") and the 4.4 smoke test, where stdout noise would break the protocol, already cover it. Cut the scan or fold it into the AST test.
- **"Store closed" test (2.4):** this traces to D4 but not to D10. Keep it only if the slice treats it as required.

### [NOTE] Ambiguity in the detached and smoke tests

- **Fake script injection (3.2):** the detached test uses a fake `amoeba` script but does not say how it is injected. `resolve_amoeba_script` derives its path from `sys.executable`, so the task should say to monkeypatch it.
- **Home override (4.4):** `AMOEBA_HOME` "or the equivalent" leaves the mechanism open. Task 0.2 already records how `amoeba_home` works, so point 4.4 at that note.
- **Wording (2.3):** "tools without `takes_directory` ignore nothing and strip nothing" is hard to parse. Say that arguments pass through unchanged and `directory` is not required.

### Run Digest

- Response length: 4910 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 106692 / 11198 / 95490 / 4110 / not computed
- Duration: 33.4 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
