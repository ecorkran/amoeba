---
docType: review
layer: project
reviewType: tasks
slice: squadron-review-parser-and-ingest
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 84d710f653b37956a71877572e68d3073ad5e4c8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
durationSeconds: 50.8
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for Sections 6–9"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:354-392"
  - id: F002
    severity: concern
    category: completeness
    summary: "Task 8.3 does not say how to create the \"store exists\" precondition"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:145-163"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 8.4 is too large for one task"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:167-185"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Fixture path constants have no clear owner before Task 7.2"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:89"
  - id: F005
    severity: note
    category: sequencing
    summary: "Task 7.1 and later dependency chains are more serial than necessary"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:62"
  - id: F006
    severity: note
    category: process
    summary: "Commit cadence relies on test tasks to commit implementation tasks"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:32-36"
  - id: F007
    severity: note
    category: task-sizing
    summary: "Task 7.1 touches four files under one commit"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:62-78"
  - id: F008
    severity: note
    category: nfr
    summary: "No NFR load-test requirement applies"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:354-392"
  - id: F009
    severity: note
    category: scope
    summary: "Task 9.3 repeats the import-direction check from Task 5.3"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:238"
---

# Review: tasks — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage for Sections 6–9

Each criterion in the slice design that falls to this file has a task:
- Payload round trip and key sets: 6.1 and 6.2.
- Migrating 104's four fixture users and deleting the old reader: 7.1 and 7.2.
- `REVIEW_UNREADABLE = 12`: 8.1.
- Ingest data flow and D6/D7: 8.2 and 8.3.
- Read-failure paths, each leaving `inbox/new/` empty: 8.3.
- Stderr node, slice and type line, and the D7 non-check: 8.3.
- Integration requirement (three verdicts, `kill -9`, round 2 against round 1, stopped process, nonexistent project, D5 two-id pair): 8.4.
- Docs, CHANGELOG, and the walkthrough: 9.1 to 9.3.

No task falls outside the slice's scope. The error handling in 8.2 matches the design: explicit branches only, with `InboxSubmitError` left to the boundary handler. Exit code 12 is free; `src/amoeba/cli/main.py` currently ends at `NOT_COMPARABLE = 11`.

### [CONCERN] Task 8.3 does not say how to create the "store exists" precondition

Task 8.3 runs ingest with no process, and its success path and `--id` case need a project whose store file exists at `paths.store_path(project)`. Nothing says how the test gets one. Options include creating a real store through the harness, or touching an empty file, which is only valid if ingest checks existence and nothing else. A junior will have to guess, and a fake empty file could contradict D6's "a store file that exists is complete" rationale. Name the helper in `tests/cli_harness.py` or `tests/cli/test_submit.py` to reuse, or state the fixture approach explicitly. The "project with no store file" case in the same task is fine.

### [CONCERN] Task 8.4 is too large for one task

Task 8.4 is rated Effort 4 but holds four separate subprocess scenarios:
- the full main flow, with a repeated ingest and a `kill -9`
- ingest with the process stopped
- a nonexistent project, with the process both running and stopped
- the 0.15.0 pair D5 test

Each needs its own supervisor lifecycle. Split it into two tasks, 8.4 (main flow plus crash) and 8.5 (stopped, refused, and D5 pair), with a commit after each. The main flow also needs a step to wait until the process has applied the three submissions before `kill -9`. Without it, the "exactly three verdicts" assertion is racy. Poll `inspect submissions` for this.

### [CONCERN] Fixture path constants have no clear owner before Task 7.2

Task 7.2 says to "add path constants for the new fixtures that later tests need". The tests in Tasks 3.3, 4.2 and 5.3 (in the part-1 file) already read those fixtures. If they take paths from `tests/review_fixtures.py`, the constants should be added in Task 1.1/1.2, and 7.2's wording is misleading. If they hardcode paths, Section 7 leaves duplicated path definitions. Decide which, and say so in Tasks 1.1/1.2 or 3.3 and in 7.2. Task 7.2 should also check that no `tests/upstream` module depends on the deleted reader.

### [NOTE] Task 7.1 and later dependency chains are more serial than necessary

Task 7.1 depends on 6.2, but it really needs only Section 5 (`parse_review_artifact` and `to_verdict_input`). Task 8.1 depends on 7.2 for no technical reason, and the same is true of 9.1's dependence on 8.4. The ordering is safe and has no cycles. The chain still blocks parallel work, and a failure in the Section 6 payload work would hold up the test migration. Consider recording the real dependencies.

### [NOTE] Commit cadence relies on test tasks to commit implementation tasks

Tasks 6.1, 8.1 and 8.2 have no commit of their own. 6.1 is committed with 6.2, and 8.2 explicitly with 8.3, which fits the test-with pattern. 8.1 never says where it is committed; add "committed with Task 8.3" to its criteria. Strictly, the project rule is "commit at least once per task". Commits are otherwise spread through the whole file and not batched at the end.

### [NOTE] Task 7.1 touches four files under one commit

Task 7.1 edits four files, one at a time with a test run after each, and makes a single commit. That is acceptable at Effort 3. Per-file commits would give clearer rollback points if an expected value diverges and the junior has to stop and report to the PM.

### [NOTE] No NFR load-test requirement applies

The slice design restates no NFR, so no `tests/load/` task or CI-gating task is required. Task 9.3 runs the existing `tests/load` suite as a regression check, and that directory exists. Neither CI gating nor a new load test is missing.

### [NOTE] Task 9.3 repeats the import-direction check from Task 5.3

Task 5.3 already adds a test for the import rules, and Task 9.3 re-checks them by grep. The repeat is cheap and acts as a final guard, so keep it. A one-line cross-reference to the 5.3 test would show it is intentional.

### Run Digest

- Response length: 6081 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 50.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
