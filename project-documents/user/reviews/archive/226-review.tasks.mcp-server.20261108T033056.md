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
reviewedSha: 2ab4a6d004173f9a4ade5d1a51c4d7d1148899ff
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 106423
cachedTokens: 11198
cacheWriteTokens: 95221
completionTokens: 3399
durationSeconds: 28.5
costUsd: 0.416844
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "HandlePauseCall is needed by tasks 2.1 and 2.2 but only created in task 3.1"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:86-93,115"
  - id: F002
    severity: concern
    category: sequencing
    summary: "`mcp` dependency is declared in task 4.3 but imported from task 4.1"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:133-147"
  - id: F003
    severity: concern
    category: gap
    summary: "No task enables ruff `ASYNC` rules"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:44,108"
  - id: F004
    severity: note
    category: testing
    summary: "`main()` fail-fast on a missing `amoeba` script is untested"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md:142"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Success criteria traceability"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Sizing, commits and proportionality"
    location: "project-documents/user/tasks/226-tasks.mcp-server.md"
---

# Review: tasks — slice 226

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] HandlePauseCall is needed by tasks 2.1 and 2.2 but only created in task 3.1

Task 2.1 builds the `handle_pause` row of `TOOLS`, which needs a `request_model`. Task 2.2's `input_schema` uses `HandlePauseCall` as the base for `handle_pause`. Task 0.2 allows for `HandlePauseCall` being absent, and task 3.1 is the one that creates it. If it is absent, tasks 2.1 and 2.2 cannot import or pass their tests, and the Section 2 commit would not be a working point. Fix: move the "ensure `HandlePauseCall` exists" step into task 2.1 (or a step just before it) and leave only `StartedCall` in 3.1.

### [CONCERN] `mcp` dependency is declared in task 4.3 but imported from task 4.1

`mcp/server.py` imports `mcp.server.lowlevel` and the SDK types in tasks 4.1 and 4.2. The `mcp>=2.3,<3` dependency and `uv sync` only arrive in task 4.3. Task 0.2 only records whether `mcp` is declared. The 4.1 and 4.2 tests may pass only because the package happens to be installed. Fix: add the dependency line (and `uv sync`) at the start of 4.1, or in task 0.2 if it is missing, and leave the console script and boundary test in 4.3.

### [CONCERN] No task enables ruff `ASYNC` rules

The slice success criterion is "ruff's `ASYNC` rules are clean". The context summary says they "must be enabled", and task 2.4 requires `ruff check` clean "with `ASYNC` rules selected". No step edits the ruff config in `pyproject.toml` to select them, and task 0.2 does not check whether they are already selected. As written, an implementer could pass 2.4 without ever turning them on. Fix: add a step to 2.4 (or 0.2) to select `ASYNC` in `[tool.ruff.lint]` if absent.

### [NOTE] `main()` fail-fast on a missing `amoeba` script is untested

D6 says `amoeba-mcp` exits at start-up when the script is missing. Task 3.2 tests `resolve_amoeba_script()` raising. Task 4.2 specifies the exit-non-zero behavior of `main()` but has no test for it. A small test that `main()` exits non-zero with a stderr message when resolution fails would close this. It is optional.

### [PASS] Success criteria traceability

- **Same inputs and JSON results over MCP:** tasks 2.1 to 2.4, 3.2 and 4.1.
- **No operation logic, boundary and no print:** task 4.3.
- **Off-loop execution:** the 2.4 off-the-loop test.
- **Checks pass and CLI tests unchanged:** tasks 1.1, 1.2 and 4.4.
- **Docs and README link:** task 5.1.
- **227 can add an operation with a name, subcommand and row:** the "same names" tests in 1.1 and 2.1.

Every D10 test maps to a task. No task falls outside the design, and no scope creep was found.

### [PASS] Sizing, commits and proportionality

- **Single file:** one task file for a slice of effort 2 is appropriate.
- **Granularity:** tasks are sized for a junior AI, and tests sit with their implementations.
- **Commit markers:** they fall at working, tested points after tasks 1.2, 2.4, 3.2, 4.4 and 5.2.
- **Test tasks:** none exceed what the success criteria and D10 require.
- **Load tests:** there is no NFR, so no load test or CI gating is needed.

### Run Digest

- Response length: 3760 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 106423 / 11198 / 95221 / 3399 / not computed
- Duration: 28.5 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
