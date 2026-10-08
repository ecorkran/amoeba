---
docType: review
layer: project
reviewType: tasks
slice: context-forge-event-seam
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: c4b926e479bff0342f550112a9bb5fcb7c841b84
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 394.4
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 6.2 tests depend on per-watch state transitions that arrive in Task 6.3"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:57-60"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Task 6.3 bundles several independent concerns"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:71-91"
  - id: F003
    severity: concern
    category: coverage
    summary: "Task 8.7 relies on boundary tests that this file never creates"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:333"
  - id: F004
    severity: concern
    category: requirements-alignment
    summary: "Idle-path guarantee is knowingly weakened and diverges from the slice text"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:144"
  - id: F005
    severity: note
    category: nfr-coverage
    summary: "No load test or CI gate for the idle-tick guarantee"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:275"
  - id: F006
    severity: note
    category: sequencing
    summary: "Task 8.6's \"final message\" precedes Task 8.7"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:305"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success criteria coverage and traceability"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:24-341"
  - id: F008
    severity: pass
    category: process
    summary: "Test-with pattern and commit cadence"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:40-345"
---

# Review: tasks — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 6.2 tests depend on per-watch state transitions that arrive in Task 6.3

Task 6.1 leaves dispatch as a stub. Task 6.2 handles only the file-wide failures. Its tests also expect behavior that needs per-watch processing:
- "file appears → INFO once and the state leaves `unreachable`".
- "a recognized file after [unrecognized] restores the state".

Nothing sets `ok` or `missing` on a recognized read until Task 6.3 (and 6.4 for `missing`). The INFO-on-leave log likewise needs a transition to a non-failure state. As written, a junior can't satisfy the 6.2 success criteria.

Either move the recovery cases to Task 6.3 or 6.4, or make 6.2 explicitly set a placeholder state on a recognized read, to be replaced in 6.3.

### [CONCERN] Task 6.3 bundles several independent concerns

Task 6.3 contains four separable pieces:
- The writer-guard AST test.
- The diff and record loop.
- Label capture, which includes the LLD-conflict reasoning.
- Two new test files.

It's rated effort 4 but touches `cf_watch.py`, `test_writer_guard.py`, and two test files. Consider splitting into "snapshot recording" (with `test_cf_watch_snapshots`) and "version label + writer guard" (with `test_cf_watch_label` and the guard test). Each half would then be a single reviewable commit.

### [CONCERN] Task 8.7 relies on boundary tests that this file never creates

Task 8.7 maps "Enums, SQL, and constants defined once; store imports nothing upstream" to `test_import_boundaries`. Task 8.4 adds only these checks:
- The import direction.
- A single definition of `IGNORED_KEYS`, the marker, `resolve_cf_data_dir`, and the `CONTEXT_FORGE_DATA_DIR` string.

The slice's Technical Requirements also say "Each word list is a `StrEnum` defined once. All SQL is in `sql_cf.py`." No task in this file adds those assertions. File 1 may cover them, but I couldn't verify that. Confirm file 1 has them, or add them to Task 8.4.

### [CONCERN] Idle-path guarantee is knowingly weakened and diverges from the slice text

The slice says an idle tick is "one `stat`, no file read, no new-watch detection beyond an in-memory cache". Task 6.6 adds a per-interval sidecar existence check for each `failed` watch. Task 6.3 also narrows label capture to "once per recording read" and conflicts with the slice's "No tick starts a subprocess".

Both departures are disclosed in Tasks 8.6 and 8.3 and are reasonable in themselves. But they contradict the slice's Success Criteria as written, and the file header says the slice governs. The slice should be amended before implementation, so that Task 8.7's "confirm every requirement" step doesn't have to reconcile a known contradiction.

### [NOTE] No load test or CI gate for the idle-tick guarantee

The slice restates a performance-style guarantee: an idle tick is one `stat`, no read, no query. The breakdown has no `tests/load/` task or CI wiring task, and the header defers to file 1 for the reason. Task 6.1 instead enforces the guarantee deterministically with call-count spies and an injected clock. That seems adequate because the requirement is structural rather than a throughput number. Have the PM confirm this exception is accepted.

### [NOTE] Task 8.6's "final message" precedes Task 8.7

Tasks 8.5 and 8.6 both emit reports to the PM "in the final message", but Task 8.7 runs after them and may add tests or find gaps. Either move the report tasks after 8.7 or merge them into it, so the PM gets one final report that includes the coverage-gap outcome.

### [PASS] Success criteria coverage and traceability

Every Functional Requirement from the slice has a task and a named test:
- First snapshot, a pointer change, and the noise cases: Tasks 6.3 and 8.1.
- Remove/restore and `missing`: Task 6.4.
- `unreachable` and `unrecognized`: Task 6.2.
- Deactivate/reactivate: Task 6.4.
- Bounded failure and sidecar retry: Tasks 6.5 and 6.6.
- Catch-up and restart: Tasks 6.4, 7.2, and 8.1.

The Integration Requirements are covered by Tasks 8.1 and 8.2, and the walkthrough by Task 8.5. The only unrequested addition is `cf_layout.py`, which is justified and reported in Task 8.6.

### [PASS] Test-with pattern and commit cadence

Each implementation task creates its tests in the same task and commits with a semantic message. Commits are spread across Sections 6 to 8 rather than batched at the end. Sequencing is acyclic, and the 7.1 → 7.2 dependency is correctly declared because the process test reads `inspect cf-snapshots`. The failure handling in Task 6.5 follows the project's exception-handling rule.

### Run Digest

- Response length: 5791 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 394.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
