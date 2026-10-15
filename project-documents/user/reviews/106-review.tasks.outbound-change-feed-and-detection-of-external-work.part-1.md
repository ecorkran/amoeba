---
docType: review
layer: project
reviewType: tasks
slice: outbound-change-feed-and-detection-of-external-work
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 4395a7694957241fac827b9f790727d13ccd22ba
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 58.0
runId: run-20261015-p5-a36b1511
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "File 1 covers its share of the success criteria"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:35-558"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Task 1.6 Rule 3 silently skips listed modules that don't exist"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:145"
  - id: F003
    severity: concern
    category: scope
    summary: "Task 4.7/4.8 add an existing-key guard that no success criterion needs"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:530"
  - id: F004
    severity: note
    category: testability
    summary: "Tasks 2.1 and 2.3 have no behavioral success criterion of their own"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:171-173"
  - id: F005
    severity: note
    category: nfr
    summary: "No load test is needed"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:277"
  - id: F006
    severity: note
    category: scope
    summary: "Proportionality is acceptable for this slice"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:1-34"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] File 1 covers its share of the success criteria

Each criterion owned by sections 1–4 has a task, and each implementation task is followed by its test task.
- **Upgrade from version 5 to 6:** Task 1.4.
- **Emission in the writer's transaction, with no writer code changes:** Tasks 2.1–2.4 and the invariant test in 2.5/4.2.
- **`resolution` produces a blocked-to-`runnable` change:** Task 2.4 at store level. Task 9.1 covers it end to end.
- **Follower:** Tasks 3.3/3.4 cover the whole failure table: schema mismatch, unknown project, busy retry, missing directory at start and mid-follow, raising `stop`, and `stop` true. They also cover resume without gap or repeat.
- **`amoeba feed`:** Tasks 3.5/3.6 cover `--after`, `--follow` with the process stopped, and a killed follower.
- **Ledger, `watch_reviews`, baseline atomicity, hand-edit idempotency:** Tasks 4.1–4.8.

The remaining criteria are in file 2: attribution, settle and race handling, defer, `runner_issued`, listings, end-to-end, and docs.

Sequencing is sound. There are no cycles, and the "committed with Task N" pairing keeps untested behavior out of commits. Commit points are spread through the sections, not batched at the end. I confirmed that the existing files the tasks name for modification or modelling are present in the repo (`store/paths.py`, `tests/test_paths.py`, `tests/upstream/test_import_direction.py`, `mapping_journal.py`, `_verdict_writer.py`, `test_migration_005.py`, and others).

### [CONCERN] Task 1.6 Rule 3 silently skips listed modules that don't exist

Rule 3 lists ten modules and says "A listed module that does not exist yet is skipped." The project's core principle is no silent fallbacks. A misspelled or later-renamed module name in the list would pass forever without being checked, and nothing in the task tells anyone to notice. Nothing in file 2's final tasks (9.5/9.7) re-checks the list either.

Fix, either of these:
- Add a final assertion, activated in Task 9.5, that every listed module exists. Or have Task 7.5/8.1 move the list entries into the test as each module lands.
- Drop the skip and add each module to the list in the task that creates it.

Rules 1 and 2 are fine as written.

### [CONCERN] Task 4.7/4.8 add an existing-key guard that no success criterion needs

Task 4.7 makes `record_detected_verdict` raise `ValueError` when the ledger key already exists. The task itself calls this "a guard only", because the tenant skips known keys first. Task 4.8 then adds a dedicated test for it.

The slice design never requires this. The hand-edit criterion uses a *new* key with an existing verdict id, and `record_detection` is already defined as idempotent. The guard adds a branch, an error path and a test for a case the design doesn't specify.

Cut the guard and its 4.8 test. If the UNIQUE constraint fires, let the store's own integrity error surface; that error is already explicit and not a silent fallback. If the PM wants the guard, keep it but say which criterion it protects.

The non-`ingested` outcome `ValueError` is reasonable and can stay.

### [NOTE] Tasks 2.1 and 2.3 have no behavioral success criterion of their own

Task 2.1's criteria, and Task 2.3's, are "git diff shows no edits under…" plus "committed with Task N." A junior can't tell the triggers work until the following test task. This follows the test-with pattern, so it isn't a defect. If cheap, add an interim check such as "migration applies cleanly on a fresh store" to each, so a syntax error in the SQL fails in the task that introduced it.

### [NOTE] No load test is needed

The slice states that the parent architecture sets no numeric targets. The only contract promise is the follower's latency bound. Task 3.4 tests that with a generous multiple of the interval, and file 2 tells the PM that no load test was added. With no restated NFR, no `tests/load/` task or CI gating task is required.

### [NOTE] Proportionality is acceptable for this slice

Across the two files there are about 55 tasks, split in two at the section 4/5 boundary. That is heavy but fits a slice that adds a migration, three tables, a follower, a CLI, an inbox kind, a tenant and two listings. Each task is small enough for a junior AI. Two tasks, 3.2a and 4.7, are inserted prerequisites for the follower and the one-transaction ingest, and both trace to the design. Splitting into two files is justified by size.

### Run Digest

- Response length: 5469 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 58.0 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
