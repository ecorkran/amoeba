---
docType: review
layer: project
reviewType: tasks
slice: judge-samples-checks-and-calibration
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: b1a8e2fee89c1042152dd6190c726d0b3ee3f4dd
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
durationSeconds: 44.6
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: task-scoping
    summary: "End-to-end test split across Tasks 8.3 and 8.4 is not independently completable"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:412-445"
  - id: F002
    severity: concern
    category: task-scoping
    summary: "Task 8.7 is too large and bundles unrelated work, including code changes, into a final validation step"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:487-504"
  - id: F003
    severity: concern
    category: task-clarity
    summary: "Task 6.1 lists a test file to modify but says no tests are written there"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:168-173"
  - id: F004
    severity: concern
    category: completeness
    summary: "Fresh judge fixture can be left unresolved while later tasks complete"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:194-210"
  - id: F005
    severity: note
    category: sequencing
    summary: "Dependency chain is more linear than the actual needs"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:270"
  - id: F006
    severity: note
    category: nfr-coverage
    summary: "No NFR in the slice, so no load test or CI gating task is needed"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for this file's scope"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:24-504"
  - id: F008
    severity: pass
    category: process
    summary: "Test-with pattern and commit cadence"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:24-504"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] End-to-end test split across Tasks 8.3 and 8.4 is not independently completable

- **Task 8.3's pass condition.** It must pass "with the process left running". That is not a valid end state for a pytest test, which must tear down its own process.
- **Task 8.3's capture step.** It tells the implementer to "capture each listing's `--json` output for Task 8.4". Task 8.4 is a separate test function that would also have to run after 8.3's wait and then `kill -9`. Two test functions cannot share a live instance or captured output unless the test file keeps module-level state. That would make the tests order-dependent.
- **Task 8.3's commit.** It carries no commit of its own ("Commit with Task 8.4"), so the 8.3 work is uncommitted when the 8.3 checkbox is ticked.

A junior AI will likely guess at one of these. Pick one design explicitly:
- **Option A:** merge 8.3 and 8.4 into one test with one setup, effort about 4–5.
- **Option B:** keep both as separate tests that each build the seeded instance from a shared fixture, with 8.4 capturing its own pre-crash listings.

Either way, give 8.3 a self-contained pass condition and its own commit.

### [CONCERN] Task 8.7 is too large and bundles unrelated work, including code changes, into a final validation step

Task 8.7 combines five things:
- the full suite, lint and typecheck;
- source-file-length refactoring ("anything well over ~300 lines is split");
- widening the metrology-reference test to the CLI modules;
- the fresh-fixture follow-up;
- the seven-step walkthrough plus a traceability pass over all LLD requirements.

The refactor and the test widening are code changes with no test or commit of their own. The metrology widening also overlaps Task 5.7's step. Suggested split:
- Move the metrology widening into Task 7.5 or 7.6, alongside the CLI modules it covers.
- Make the file-length check a step that reports to the PM, as Task 5.3 does, rather than an open-ended refactor.
- Split the walkthrough and traceability pass from the lint, typecheck and suite run.

### [CONCERN] Task 6.1 lists a test file to modify but says no tests are written there

Task 6.1's "Files to Modify" includes 105's round-trip test, but its steps say "No tests here; Task 6.2 owns them". That conflicts with the test-with pattern and confuses the file list. Its step on `verdict_to_payload` is also conditional ("skip if Task 4.3 already did this"), which makes the task's scope ambiguous. Remove the test file from 6.1's list. Make the `verdict_to_payload` step a verification of Task 4.3's work rather than a conditional edit.

### [CONCERN] Fresh judge fixture can be left unresolved while later tasks complete

The slice's Technical Requirements require two fixtures, the 302 file and a fresh capture. Task 6.3 lets the fresh capture be "reported to the PM as blocked", and Task 8.7 only checks that it was reported. The slice can therefore reach final validation without a required fixture, and Task 6.4's tests only run "for each fixture present". That is a reasonable escape hatch for an external dependency. The task should still say the PM must sign off on the gap before Task 8.7 is ticked, so the gap is an explicit decision and not an implicit pass.

### [NOTE] Dependency chain is more linear than the actual needs

Task 7.1 (verdicts column and filter) depends on Task 5.7, though it only needs Task 4.7. Task 7.3 (calibration listing) only needs Task 4.11. This does no harm, since the stated order runs 5, then 7, then 8. It does hide the real parallelism, and it makes the "105 not merged" reordering in the Context Summary look more constrained than it is.

### [NOTE] No NFR in the slice, so no load test or CI gating task is needed

The slice design states no performance or load NFR. The only scale remark is that judge samples per project are few. The load-test and CI-wiring criteria therefore do not apply. The `ruff`, `pyright` and full-suite checks in 5.7, 7.6 and 8.7 stand in as the quality gate.

### [PASS] Success-criteria coverage for this file's scope

Each LLD criterion in this file's scope maps to tasks:

| LLD criterion | Tasks |
| --- | --- |
| Check standing rows and rejections | 5.3–5.4 |
| Replay with WARNING | 5.4, 5.6 |
| `record_work` content rules and `kind` filter | 5.5–5.6 |
| Public API export test | 5.7 |
| `ingest review --judge-invocation-id` on the judge fixture, with standing `unattested` | 6.5–6.6 |
| Judge fixtures with README entries | 6.3–6.4 |
| Four listings, running and stopped | 7.1–7.6 |
| `demo_checks.py` and the writer guard | 8.1–8.2 |
| End-to-end crash proof | 8.3–8.4 |
| Docs and CHANGELOG | 8.5–8.6 |
| Metrology reference test | 5.7 and 8.7 |

Judge samples, D2, D3, the filter, calibration, the migration and the vocabularies are owned by file 1. Its Tasks 1.1–4.12 line up with the LLD development-approach steps 1–3.

### [PASS] Test-with pattern and commit cadence

Every implementation task is immediately followed by its test task, and each pair carries a commit instruction (5.1/5.2, 5.3/5.4, 5.5/5.6, 6.1/6.2, 6.3/6.4, 6.5/6.6, 7.1/7.2, 7.3/7.4, 7.5/7.6, 8.1/8.2). Commits are spread across Sections 5–8, not batched at the end. I found no scope creep: every task traces to an LLD scope item or requirement.

### Run Digest

- Response length: 6523 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 44.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
