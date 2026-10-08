---
docType: review
layer: project
reviewType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 5aade9e5d6aebd988061a3975597c6e24b572def
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
durationSeconds: 468.6
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are covered across the three task files"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:30"
  - id: F002
    severity: pass
    category: process
    summary: "Test-with pattern, commit cadence, and the NFR/load-test check"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:26"
  - id: F003
    severity: concern
    category: sequencing
    summary: "The riskiest test (feed invariant) arrives after Sections 3–5"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:465-479"
  - id: F004
    severity: concern
    category: task-clarity
    summary: "Task 1.4 has unclear or conditional instructions"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:108-109"
  - id: F005
    severity: concern
    category: task-sizing
    summary: "Task 5.1 bundles too many distinct pieces"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:348-366"
  - id: F006
    severity: note
    category: assumption
    summary: "`recorded_since` assumes verdict id equals `record_id`"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:355"
  - id: F007
    severity: note
    category: test-quality
    summary: "Task 5.8's literal check is coarse"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:491"
  - id: F008
    severity: note
    category: cross-document
    summary: "Task 8.1 (file 2) and the slice describe 105's `source_document` handling differently"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:211-227"
  - id: F009
    severity: note
    category: scope
    summary: "`read_only` constructor flag is a disclosed contract addition"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:313-315"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are covered across the three task files

I mapped each slice success criterion to a task. Task numbers below are from file 1 unless marked otherwise.
- **Triggers and replay:** triggers and the replay invariant are in 2.1–2.3 and 5.7–5.9.
- **`resolution` change:** the `resolution` to `node_status_changed` criterion is in 2.2, with 11.2 (file 3) as the end-to-end check.
- **`read_transaction()`:** atomicity is in 4.3–4.4.
- **Schema upgrade:** the 5→6 upgrade is in 1.3–1.4.
- **`source_document`:** the D7 series rule is in 3.1–3.3.
- **Feed reads and ledger:** the feed API is in 4.1–4.2. The ledger and `watch_reviews` are in 5.1–5.6.
- **Follower and CLI:** the follower and `amoeba feed` are in 7.x (file 2).
- **Detection:** attribution, baselining, defer/skip and bounded failure are in 6.x and 9.x (file 2).
- **Listings, docs, end-to-end:** listings, docs and end-to-end tests are in 10.x and 11.x (file 3).

I found no scope creep. The additions beyond the design text (the `read_only` flag, `recorded_since`, `DetectionInput`, `record_detected_verdict`, `watch_state`) are all disclosed. Each traces to a stated criterion. Tasks 4.3, 5.1, 11.7 and 11.11 route them to the contract docs and the PM report.

### [PASS] Test-with pattern, commit cadence, and the NFR/load-test check

Every implementation task is followed immediately by its test task, or carries its tests inline (1.2, 2.1–2.3, 3.1–3.2). Commits are spread through all sections, and no task merges. The slice restates no NFR with a load or throughput target. The scan, follow and timeout values are explicitly design choices. So no `tests/load/` task or CI-gating task is required.

### [CONCERN] The riskiest test (feed invariant) arrives after Sections 3–5

The slice's own Development Approach lists the migration, triggers and invariant test first because they are the riskiest piece. Task 5.7 says "it gates the rest", but it comes after the source_document writer changes (3.1–3.2), the feed API and `read_transaction` (4.x), and the ledger (5.1–5.6).
- A wrong trigger payload or a drifted literal in Section 2 would only surface at 5.7. By then four sections and several commits sit on top of it.
- The nodes, verdicts and messages reconciliation does not depend on the ledger. Only the `detected_reviews` leg does.

Suggestion: build the reconciliation helper right after Task 4.2, covering nodes, verdicts and messages. Extend it with the ledger leg in 5.7. Alternatively, drop the "gates the rest" wording.

### [CONCERN] Task 1.4 has unclear or conditional instructions

Two lines would trip a junior AI.
- **`change_head`:** step 108 asserts "`change_head` source (max seq) is 0", but `change_head` does not exist until Task 4.1. The step should say to assert `SELECT MAX(seq)` or an empty `changes` table through raw SQL.
- **Re-apply test:** step 109 says "same as 005's test, if it has one". A conditional that can be skipped silently is a weak success criterion. State that the task must read `test_migration_005.py` first and mirror its failure case. If 005 has none, the task should either add one or say explicitly that none is needed.

### [CONCERN] Task 5.1 bundles too many distinct pieces

Task 5.1 combines the following in one effort-3 task:
- the SQL statements;
- three public methods (`record_detection`, `detections`, `recorded_since`);
- a private no-transaction insert shared with 5.5 and 6.4;
- the `review_detected` trigger with its silent-outcome literals;
- the transaction-shape decision;
- two contract additions to document.

The trigger and the transaction shape are the likeliest to go wrong. They sit in an implementation task whose tests land only in 5.2. Consider splitting it: 5.1a for the private insert, `record_detection` and `detections` (with the trigger), and 5.1b for `recorded_since`. Each half would get its tests immediately.

### [NOTE] `recorded_since` assumes verdict id equals `record_id`

Task 5.1 states "`record_id` is the verdict id 105 uses". 105's design makes `review_record_id(parsed)` the default verdict id. But it also allows overrides: `to_verdict_input(record_id=…)` and `amoeba ingest review --id`. A Runner-supplied or hand-supplied id would make `recorded_since` false even though a verdict exists. This matches the slice's current definition, so it needs no change. A one-line docstring on `recorded_since` would record the default-id dependency.

### [NOTE] Task 5.8's literal check is coarse

The check asserts that each `ChangeKind` and `SILENT_OUTCOMES` value appears somewhere in the concatenated trigger SQL. A literal sitting in the wrong trigger would still pass this check. Task 5.7's reconciliation and 5.9's dropped-trigger cases cover that gap, so no change is needed.

### [NOTE] Task 8.1 (file 2) and the slice describe 105's `source_document` handling differently

The slice design says 105's design already carries `sourceDocument` into `VerdictInput.source_document`. Task 8.1 says 105 deliberately left that pass-through to this slice, and edits `to_verdict_input` and 105's tests accordingly. The task is internally consistent, since `VerdictInput.source_document` only exists after Task 3.1. But if the merged 105 already passes it, the "update the test that asserts it does not" step is moot. Task 8.1 should say "if already present, skip".

### [NOTE] `read_only` constructor flag is a disclosed contract addition

The design only says `read_transaction()` lives on the read-only handle. Task 4.3 adds a `Store.__init__` keyword so the method can refuse read-write handles. This is a reasonable mechanism and is tracked for `store-contract.md` (11.7) and the PM report (11.11). It may touch several direct `Store(...)` constructions in tests, so treat the effort of 3 as a floor.

### Run Digest

- Response length: 7217 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 468.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
