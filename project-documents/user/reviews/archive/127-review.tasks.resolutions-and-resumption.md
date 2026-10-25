---
docType: review
layer: project
reviewType: tasks
slice: resolutions-and-resumption
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/127-tasks.resolutions-and-resumption.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261025
dateUpdated: 20261025
reviewedSha: 0c069a7dc0614dcfa090b00753c2727807c0d9bb
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 118662
cachedTokens: 11222
cacheWriteTokens: 107436
completionTokens: 9342
durationSeconds: 71.9
costUsd: 0.525101
costBasis: provider
runId: run-20261025-p5-ce38b28c
squadronVersion: 0.24.4
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Several tasks omit a real prerequisite from their Dependencies line"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:256-272"
  - id: F002
    severity: concern
    category: task-scoping
    summary: "Changing the `dispatch_state` signature conflicts with \"existing state tests pass\""
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:211-213"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Task granularity is slightly off for a 3/5 slice with 34 tasks"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:101-114"
  - id: F004
    severity: note
    category: task-scoping
    summary: "Task 6.4 commits a `NotImplementedError` branch"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:270"
  - id: F005
    severity: note
    category: traceability
    summary: "Pointer-watch task has no explicit success criterion"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:307-312"
  - id: F006
    severity: pass
    category: coverage
    summary: "Success criteria are fully covered"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md"
  - id: F007
    severity: pass
    category: process
    summary: "Test-with pattern, commit cadence and process rules are sound"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:54"
---

# Review: tasks — slice 127

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Several tasks omit a real prerequisite from their Dependencies line

The file says that if a task is `BLOCKED:`, work continues with the next task whose listed dependencies are all checked off (line 52). That makes the lists load-bearing, and these are incomplete:
- **Task 6.3** lists only 3.1. Its test asserts that `classify` reads `paused_run` after a failed resume and `ended_run` after `run_missing`, which needs `classify` from Task 3.2.
- **Task 6.4** lists 5.3 and 6.3. It is "called from `runner/act.py`", which Task 1.2 creates. Task 6.1 lists 1.2, but 6.4 does not.
- **Task 4.2** edits `runner/tick.py`, which is already at 324 lines, and Task 1.2 is the refactor that makes room for it. Its Dependencies line (4.1) does not include 1.2.

Add 3.2 to 6.3, and 1.2 to 4.2 and 6.4.

### [CONCERN] Changing the `dispatch_state` signature conflicts with "existing state tests pass"

Task 5.1 changes the signature to `dispatch_state(entries, resolution, *, pointer_confirmed)`. Its success line says existing state tests pass "with `resolution=None`", but the existing callers and tests have the old two-argument shape. Either the task must say to update those call sites, or `resolution` should be a keyword-only argument. This is also why 5.1 cannot commit alone and is bundled with 5.2.

### [CONCERN] Task granularity is slightly off for a 3/5 slice with 34 tasks

Some adjacent tasks are small enough to merge:
- **Tasks 2.1 and 2.2:** the migration and the models and mapping that read its columns. They are tightly coupled, and 2.1's own tests cannot exercise the columns through the models.
- **Tasks 9.3 and 9.4:** both are `docs:` commits that describe the same changes, and 9.4 is effort 1 with no work beyond the entry.

Task 2.5 does the opposite. It mixes a store read method, the journal keys, supervisor wiring and the observer rules, at effort 3. It would be easier to hand off as two tasks: keys plus `recorded_result_run_nodes`, then the observer rules.

### [NOTE] Task 6.4 commits a `NotImplementedError` branch

The `ResumeRun` launch branch raises `NotImplementedError` until Task 6.5. It is unreachable in production because `ContinuationPlanner` joins `PRODUCTION_PLANNERS` only in Task 7.3. The raise is loud rather than silent, so it is acceptable. It does conflict slightly with the file's rule that a commit never holds untested behavior (line 54). Merging 6.4 and 6.5 would remove the placeholder, but would make one large task.

### [NOTE] Pointer-watch task has no explicit success criterion

Task 7.4 traces to "Consumes from Other Slices" (125's pointer-move check covering continuation entries), not to a numbered success criterion. It is a legitimate integration requirement and the task is small, so no change is needed. Consider adding a line to the slice's success criteria so the trace is explicit.

### [PASS] Success criteria are fully covered

- **Decisions:** retry/accept are covered by 6.1, 6.2 and 6.5. `handled` is covered by 6.4. Accept of a completed outcome, `rerun` and `stop` are covered by 3.3, 5.1, 5.4 and 9.2.
- **Rejections:** 3.3 tests every check (0–7), including the human-step and unparseable-document cases.
- **Instructions:** 6.1, 6.2 and 6.5 prove they arrive byte for byte, and the source test in 9.2 covers the "no Runner path adds instructions" criterion.
- **Identifiable accept:** 9.2.
- **Missing run:** 6.4, with recovery never reissuing a continuation in 2.5.
- **Confirmation and failures:** 7.1–7.3.
- **Moved by hand:** 6.4.
- **Accept over CONCERNS:** 8.1 and 8.2.
- **Crash safety:** 7.5.
- **Cut-off and failed pre-poll:** 6.4.
- **Poisoned resolution:** 4.2.
- **Hold:** 9.2.
- **Partial-index `EXPLAIN QUERY PLAN` test and migration on a populated v11 store:** 2.1 and 2.4.
- **Contract suite stand-in:** 2.6.
- **Contract documents and CHANGELOG:** 9.3 and 9.4.

### [PASS] Test-with pattern, commit cadence and process rules are sound

- Every implementation task carries its tests. Where a commit is deferred (4.1→4.2, 5.1→5.2, 8.1→8.2), the file states it.
- Commits are spread across all nine sections.
- No task merges. Merging is left to Phase 7.
- No step waits on Project Manager approval. `BLOCKED:` is used only for real failures.
- The file notes the one place it departs from the LLD (`resume_skipped` as a parameter, per D4).
- The file makes no load-test or CI-gate demand, which fits a slice that restates no NFR.

### Run Digest

- Response length: 5481 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 118662 / 11222 / 107436 / 9342 / not computed
- Duration: 71.9 s
- Cost: $0.53 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
