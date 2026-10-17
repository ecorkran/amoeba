---
docType: review
layer: project
reviewType: tasks
slice: context-forge-event-seam
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/108-tasks.context-forge-event-seam.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261016
dateUpdated: 20261016
reviewedSha: 5079c9d405a59f686555435837639140bc75faf4
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 136567
cachedTokens: 95430
cacheWriteTokens: 41133
completionTokens: 4161
durationSeconds: 34.0
costUsd: 0.216362
costBasis: provider
runId: run-20261017-p56-7ed94110
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Tenant depends on a settings field that is added two sections later"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam.md:297"
  - id: F002
    severity: concern
    category: task-clarity
    summary: "Task 2.1 contains an unresolved either/or instruction"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam.md:89"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Task file restates the LLD it says it does not restate"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam.md:105-110"
  - id: F004
    severity: note
    category: dependencies
    summary: "D7 PM confirmation is not gated by any task, and the impact list is incomplete"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam.md:27"
  - id: F005
    severity: note
    category: testing
    summary: "Interval-gating test may require a new seam"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam.md:323"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Success-criteria coverage and test-with ordering"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam.md"
---

# Review: tasks — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Tenant depends on a settings field that is added two sections later

Task 5.1 builds `tick` around `cf_scan_interval_seconds` read from `settings` on the host protocol. Task 5.2's interval-gating test also depends on it. `ProcessSettings.cf_scan_interval_seconds` is not added until Task 6.1 (line 368). Task 5.1 therefore cannot pass `pyright`, and Tasks 5.2 and 5.3 cannot run. The Section 5 commit would fail its own build.

Fix by moving the `ProcessSettings` part of 6.1 (both fields) ahead of Task 5.1. Alternatively, have 5.1 add the settings fields itself. The `--cf-data-dir` flag can stay in Section 6.

### [CONCERN] Task 2.1 contains an unresolved either/or instruction

The last step of Task 2.1 offers two options ("import `CFSnapshotOutcome`… or hold the outcome as a `str`"), then says "Choose the second". It also cites `tests/upstream/test_import_direction.py` as justification. The task should state the decision directly: `CFReadFailure.outcome` is a `str` that Task 5.1 maps. The first option cannot be taken anyway, because it names an import from a Task 3.1 module that does not exist yet and would break the import direction. Remove the dead alternative so the junior AI does not spend time deliberating.

### [CONCERN] Task file restates the LLD it says it does not restate

The reading note (line 23) says the file does not restate the LLD. Tasks 2.2 and 5.1 nonetheless re-list the D4 table rows and the tick algorithm in prose. Task 5.1 also dictates implementation structure, such as splitting per-link logic from the file read and the order of record versus remember. The LLD already settles all of this, and a second copy can drift from it.

Cut these steps to "implement per D4 / Data Flow", keeping only the details the LLD leaves open. Task 1.1 (branch and baseline only, no commit) could also be folded into Task 1.2. Together that is 21 tasks for an LLD that declares itself effort 2.

### [NOTE] D7 PM confirmation is not gated by any task, and the impact list is incomplete

The LLD says the PM must confirm D7 before the implementation phase, but Task 1.1 does not check for that confirmation. The open item lists only Tasks 6.1, 6.2 and 6.5 as affected by a D7 change. Tasks 6.4 (the end-to-end test passes `--cf-data-dir`) and 6.6 (the walkthrough uses it) also depend on D7. Add a step to Task 1.1 to confirm D7 is approved, and correct the impact list.

### [NOTE] Interval-gating test may require a new seam

Task 5.2 asserts that no `stat` or read happens before the interval elapses, "via an injected stat/reader seam or a call counter". Task 5.1 does not provide a stat seam. Pick one approach in 5.1, for example a call counter wrapping the real `os.stat` via monkeypatch. That avoids adding a production-code seam purely for testing.

### [PASS] Success-criteria coverage and test-with ordering

- **Coverage:** the functional criteria are covered as follows.
  - Pointer move, project-level `worktree_id` null, first-check all-added, and unrelated writes recording nothing: 5.2.
  - Down-time changes (restart): 5.2 and 6.4.
  - Failure outcomes once per transition, recovery, and malformed `worktrees` scoping: 2.4 and 5.3.
  - `missing` for an unknown id and idempotent relinking: 4.2 and 5.3.
  - No subprocess in `tick` and `cf --version` captured once: 5.3 and 6.2.
  - Store errors logged and re-raised: 5.3.
- **Technical requirements:**
  - Fields defined once: 2.4.
  - Store import direction: 3.4.
  - Feed invariant: 3.4.
  - 7 → 8 upgrade: 3.4.
  - Fixture: 1.2.
  - Docs: 6.5.
  - End-to-end: 6.4.
  - Walkthrough: 6.6.
- **Ordering and commits:** each implementation task is followed by its test task. Commits fall at the end of each section, which is well distributed. There is no circular dependency.
- **Load testing:** the LLD states no NFR that needs a load test, so none is required.

### Run Digest

- Response length: 4737 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 136567 / 95430 / 41133 / 4161 / not computed
- Duration: 34.0 s
- Cost: $0.22 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
