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
reviewedSha: 22dc87252bc12ef4efec7290f20dcfbb1044f0b2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 49.7
runId: run-20261015-p5-a36b1511
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "Follower failure table: \"store directory gone\" has no test"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:332"
  - id: F002
    severity: concern
    category: scope
    summary: "`record_detected_verdict` specifies key-case behavior the slice never requires"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:515"
  - id: F003
    severity: concern
    category: architecture
    summary: "Verdict-existence query placed in `sql_feed.py`"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:393"
  - id: F004
    severity: concern
    category: test-design
    summary: "Task 1.6 Rule 3 is a broad scan that will probably hit unrelated code"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:145"
  - id: F005
    severity: note
    category: coverage
    summary: "Slice criteria that belong to File 2 are covered there"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:31"
  - id: F006
    severity: note
    category: sequencing
    summary: "Sequencing and commit cadence are sound"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:25"
  - id: F007
    severity: note
    category: proportionality
    summary: "Proportionality: the slice is heavy but justified"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:35"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Follower failure table: "store directory gone" has no test

The LLD failure table has the row "Unknown project, or store directory gone (at start or mid-follow) → raises `StoreError` subclasses". Task 3.3 implements it. Task 3.4's failure-table step tests only an unknown project, a schema mismatch, a busy read, a raising `stop`, and `stop` returning true. Neither the file's tests nor its success criteria cover a missing directory at start or mid-follow. Task 3.6 doesn't cover it either. Add two cases to Task 3.4: the directory absent before `follow` starts, and the directory removed after the first yield.

### [CONCERN] `record_detected_verdict` specifies key-case behavior the slice never requires

Task 4.7 defines three key cases, and Task 4.8 tests all three. The LLD tenant loop skips any `(path, digest)` already in the ledger before it calls the write. So these two cases are unreachable from the tenant:
- same key with the same verdict id, which returns both existing records;
- same key with a different or missing verdict id, which raises `ValueError`.

Only the third case (new key, existing verdict id) is needed. It is the hand-edit success criterion. Cut the first two cases from 4.7 and 4.8, or reduce them to a single "same key is rejected" guard. This trims about a third of 4.8's assertions.

### [CONCERN] Verdict-existence query placed in `sql_feed.py`

Task 4.1 adds "a select of whether a verdict with a given id exists" to `sql_feed.py`. Task 1.3 scopes that file to the three feed tables. That statement reads `verdicts`, which `sql_evidence.py` owns, and 104's retry rule already looks up a verdict by id. A second query duplicates it and splits ownership of the `verdicts` columns, which breaks the DRY and single-definition rules. Reuse or expose the existing `sql_evidence.py` lookup for `recorded_since`. If none exists, add the statement there.

### [CONCERN] Task 1.6 Rule 3 is a broad scan that will probably hit unrelated code

Rule 3 fails on any string constant under `src/amoeba/` that equals a `ChangeKind` or `DetectionOutcome` value. Values like `ingested` and `baseline` are ordinary words. Task 105's `amoeba ingest review` and the CLI help text may well contain them. The task's answer to a false hit is to stop and ask the PM, and a junior AI shouldn't hit that on a routine task. Settle it up front. Either restrict the scan to specific modules (store, feed, process) and exclude help and message strings, or name the permitted exceptions. Rules 1 and 2 are sound and trace to the LLD's layering requirement.

### [NOTE] Slice criteria that belong to File 2 are covered there

I checked `-2.md` for the criteria File 1 doesn't test:
- The `resolution` submission producing a blocked-to-`runnable` change is in the end-to-end test (Test A).
- "Feed `--follow` started while the process is stopped" is also in Test A.
- The store-exception-stops-the-process case is a File 2 test.
- Hand-recovery of `unattributed` files, and `recorded_since` flipping, are covered.

File 1 itself tests block and resolve only through `store/blocking.py`, which is fine at this level.

### [NOTE] Sequencing and commit cadence are sound

Dependencies run in one direction with no cycles. Every implementation task is followed immediately by its test task, and the "committed with Task N.M" pairs are explicit. The invariant test is built over three tables in Task 2.5 and extended in Task 4.2. The `NOT_YET_EMITTED` constant gives a clean handoff. Destructive SQL (`DROP TRIGGER`, `RAISE(ABORT)` triggers) is confined to scratch stores, which satisfies the project's database-protection rule.

### [NOTE] Proportionality: the slice is heavy but justified

File 1 has 30 tasks, and Section 4 alone has 8. The split into two task files fits the roughly 50 tasks the design needs. Task 1.2's test of enum values and frozen dataclasses is close to tautological, and `mapping_feed.py` plus its test (Task 1.5) is a thin task. Neither is worth restructuring. Consider merging 1.2 into 1.5 only if you want to cut the count.

### Run Digest

- Response length: 5372 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 49.7 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
