---
docType: review
layer: project
reviewType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: cd233625952d49b287a151eea6dede5de055abfd
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
durationSeconds: 67.2
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: feasibility
    summary: "Task 10.4 relies on a test harness that cannot register the tenant or patch the host's subprocess calls"
    location: "tests/host_harness.py:95-115"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Task 11.6 bundles too many unrelated edits into one task"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:201-220"
  - id: F003
    severity: concern
    category: task-clarity
    summary: "Task 10.1 leaves ownership of the sidecar reader undecided"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:32"
  - id: F004
    severity: note
    category: coverage
    summary: "Slice criteria that 11.9 does not name a test for"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:259-285"
  - id: F005
    severity: note
    category: coverage
    summary: "Walkthrough steps 7 and 8 are only covered by manual run and unit tests"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:131-154"
  - id: F006
    severity: note
    category: conventions
    summary: "File-size threshold differs from project guideline"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:233"
  - id: F007
    severity: note
    category: nfr
    summary: "No load-test or CI-gating task, which is acceptable here"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:314"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for Sections 10–11 is complete"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:384-423"
  - id: F009
    severity: pass
    category: sequencing
    summary: "Sequencing and commit cadence are sound"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:21-285"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 10.4 relies on a test harness that cannot register the tenant or patch the host's subprocess calls

Task 10.4 uses `start_host` from `tests/host_harness.py` for three things: "a registered directory is baselined and a new file is ingested end to end", patching `subprocess.run` ("in-process host"), and counting calls to the label helper. The harness doesn't support any of these.
- `start_host` launches a real subprocess from a generated bootstrap script. That script builds `ResidentProcess` with only an optional `ThrowawayTenant`. It never registers `ReviewDetectionTenant`, and it never calls the `start` wiring from Task 10.3.
- A `subprocess.run` patch in the test process has no effect on the child process, so "assert zero calls" would pass vacuously. The same applies to counting calls to the label helper.
- The task also says `kill -9` and restart, which only works with the subprocess harness. "In-process host" and `kill -9` contradict each other within one task.

Split the intent in two:
- Run the real CLI (`amoeba start`, as 11.2 does) for the end-to-end and `kill -9` checks.
- Use an in-process `ResidentProcess` built with the real tenants for the "no tick spawns a subprocess" and "label captured once" checks.

If 10.4 needs the harness to accept real tenants, add that harness change as a step with its own file in "Files to Modify". Right now `tests/host_harness.py` isn't listed.

### [CONCERN] Task 11.6 bundles too many unrelated edits into one task

Task 11.6 rewrites four contract documents, `CHANGELOG.md`, and an edit to a different slice's design document (103). It also extends the doc test. It is rated Effort 3, but it is about seven deliverables with many required terms each. A junior AI is likely to miss items, and one commit covers all of it. Split it into three:
- store/inbox contracts
- process/evidence contracts
- CHANGELOG + 103 forward-reference fix + the extended doc test

The 103 edit is a design-document change (D8a) unrelated to the contracts. Giving it its own step or task keeps the "edit only that sentence" constraint reviewable. The line number is given only as "near 319". Quoting the sentence to replace would remove the ambiguity.

### [CONCERN] Task 10.1 leaves ownership of the sidecar reader undecided

"Add the pure sidecar-directory reader here if Task 9.9 did not" makes the scope depend on what an earlier task did. A junior AI can't tell what 9.9 built without reopening it. The reader is also not listed in "Files to Create" or "Files to Modify". Check file 2 and state definitively whether 10.1 owns the reader. If it does, name the module and add it to the file lists.

### [NOTE] Slice criteria that 11.9 does not name a test for

Task 11.9 traces most Functional Requirements to named tests. I found no named test for these criteria:
- "Verdicts recorded with no `source_document` keep 104's behavior" and "104's tests run unchanged". The full suite in 11.7 covers these implicitly.
- "The `changes` table is unchanged by either follower run".
- The `unattributed` case with two matching nodes, which is lumped into "unattributed".
- The `ingest review` after `unattributed` showing `recorded_since` true. This is covered in 10.2 only by "a hand ingest" and isn't in the 11.9 list.
- Reactivating a watch without re-baselining, and registering while the process is stopped. These appear in the slice's design text but not in its Success Criteria.

Add these bullets to 11.9 so the trace is complete.

### [NOTE] Walkthrough steps 7 and 8 are only covered by manual run and unit tests

The end-to-end tests (11.2, 11.3) cover walkthrough steps 1–6 and part of 8: kill, restart, resume. They don't exercise the unattributed file, the non-review file, or the hand-edit-then-restart "same verdict id, three verdicts" check from walkthrough steps 7–8. The slice's Integration Requirements don't require these in the end-to-end test, and 11.8 runs them manually. Unit-level tests (`test_review_detection`) are cited in 11.9 for the hand edit. Adding the hand-edit case to part B would be cheap, since the module already holds the right state.

### [NOTE] File-size threshold differs from project guideline

Task 11.7 splits files "beyond ~330 lines", while the project guideline and the slice say ~300. This is minor. Use ~300 to match.

### [NOTE] No load-test or CI-gating task, which is acceptable here

The slice says explicitly that the parent architecture sets no numeric targets. The 2 s scan, 0.25 s follow and ~5 s detection figures are the slice's own sizing choices, and only the follower interval is promised in the contract. No NFR is restated, so a `tests/load/` task and a CI-gating task aren't required. The tests in this file run in the normal suite, so CI wiring is implicit and sufficient.

### [PASS] Success-criteria coverage for Sections 10–11 is complete

Each in-scope item in this file's range traces to a task:
- Listings → 10.1/10.2
- `start` wiring and label captured once → 10.3/10.4
- `demo_detection.py`, with its writer-guard entry → 11.1
- Integration Requirement 1 (end-to-end through the CLI, `kill -9`, provider failure, agreement between follower and `inspect`) → 11.2/11.3
- `docs/feed-contract.md` → 11.4
- Contract and CHANGELOG updates → 11.6
- Import boundaries → 11.7
- Walkthrough → 11.8
- Requirement trace → 11.9

Tasks 11.2 and 11.3 guard against vacuous passes, assert exact content, and wait on conditions rather than sleeping. I found no scope creep.

### [PASS] Sequencing and commit cadence are sound

Dependencies run linearly (9.10 → 10.1 → … → 11.9) with no cycles. Every implementation task is followed immediately by its test task: 10.1→10.2, 10.3→10.4, 11.4→11.5, and the demo script's test is inside 11.1. Commits land at 10.2, 10.4, 11.1, 11.2, 11.3, 11.5, 11.6, 11.7, and 11.9, so they are spread through the file rather than batched at the end. 11.8 correctly needs no commit unless it exposes a defect.

### Run Digest

- Response length: 7543 chars
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
- Duration: 67.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
