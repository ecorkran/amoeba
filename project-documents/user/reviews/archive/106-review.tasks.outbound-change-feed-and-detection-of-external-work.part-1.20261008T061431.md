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
reviewedSha: cd233625952d49b287a151eea6dede5de055abfd
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 45.3
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Coverage of the slice criteria owned by Sections 1–5"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:34-481"
  - id: F002
    severity: concern
    category: commit-cadence
    summary: "Four tasks batched into one commit at the start"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:68"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Invariant test comes last and bundles five jobs"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:461-479"
  - id: F004
    severity: concern
    category: design-clarity
    summary: "Transaction composition for `record_detection` and `baseline_watch` is unspecified"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:426-440"
  - id: F005
    severity: note
    category: scope
    summary: "`recorded_since` and `DetectionInput` are not in the slice's API table"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:353-354"
  - id: F006
    severity: note
    category: scope
    summary: "Task 4.3 adds a constructor flag to `Store`"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:312"
  - id: F007
    severity: note
    category: nfr
    summary: "No numeric NFR in the parent slice, so no load-test or CI-gating task is required"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:314"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Coverage of the slice criteria owned by Sections 1–5

These criteria each have an implementing task and a test task:
- Migration 006 and the version-5 upgrade (1.3, 1.4).
- Emission by trigger for nodes, verdicts and messages (2.1–2.3).
- `source_document` and the part-1/part-2 series, through both `record_verdict` and the inbox (3.1–3.3).
- The `changes` and `change_head` reads (4.1, 4.2).
- `read_transaction()` against a concurrent commit, with a control case (4.3, 4.4).
- The detection ledger and its silent outcomes (5.1, 5.2).
- The `watch_reviews` kind, baselining, and the invariant test (5.3–5.7).

I found no scope creep. The remaining slice items are planned in the sibling files:
- The D8a edit to the 103 slice document is in file 3, around line 213.
- `scripts/demo_detection.py` and the writer-guard test are in Task 11.1.
- The `store-contract.md` entry for `read_transaction()` is in file 3, around line 208.

### [CONCERN] Four tasks batched into one commit at the start

Tasks 1.2, 1.3, 1.4 and 1.5 all say "Committed with Task 1.5". That puts the models, the migration, the version-pin edits across existing tests, the migration test and the mapping into one commit. The "a task commits with its test task" rule is meant for adjacent pairs.

Task 1.3 has its own test, 1.4, immediately after it. Commit 1.2 and 1.3 with 1.4, and 1.5 on its own. Otherwise a failure in the mapping tests makes the whole schema change hard to bisect.

### [CONCERN] Invariant test comes last and bundles five jobs

The slice's development approach puts the invariant test and the 5→6 upgrade test in step 1 as "riskiest piece". Task 5.7 only arrives after Sections 2–5 are built. Per-trigger tests in 2.x and 5.2 reduce the risk, but the whole-feed reconciliation that would catch a missing trigger runs last.

Task 5.7 is also large (effort 4). It combines four things:
- A scripted sequence across every write path.
- A table-by-table replay.
- A check of the trigger SQL literals against the enums.
- A drop-a-trigger negative case.

Suggestions:
- Split 5.7 into (a) the reconciliation with the "every `ChangeKind` appears" check, and (b) the literal check plus the negative case.
- Add the reconciliation for nodes, verdicts and messages right after 2.3, then extend it in 5.2 for detections.

This also makes the "gates the rest" claim real.

### [CONCERN] Transaction composition for `record_detection` and `baseline_watch` is unspecified

Task 5.5 requires `baseline_watch` to be atomic and to "reuse `record_detection`'s insert statement". It does not say whether `record_detection` opens its own transaction or can run inside an outer one.

The `entries` parameter has no declared type. Task 5.1 defines `DetectionInput`, but 5.5 never says whether `entries` uses it. The ingest in file 2 (`record_detected_verdict`, per file 3) needs the same composition.

State the pattern (a shared private statement helper, or an existing store transaction context) in 5.1 and 5.5, so a junior implementer doesn't invent one. Task 5.6 only tests atomicity through an invalid outcome, which would fail either way.

### [NOTE] `recorded_since` and `DetectionInput` are not in the slice's API table

Task 5.1 adds `recorded_since(project_id, record_id)` and `DetectionInput`. Neither appears in the slice's "Store additions" table. Both trace to the slice: `recorded_since` backs the `inspect detections` column, and `DetectionInput` is the argument to `record_detection`. They are justified, but the contract docs should list them. Task 11.x already names `record_detected_verdict`, so the docs task probably covers them.

### [NOTE] Task 4.3 adds a constructor flag to `Store`

The `read_only` keyword on `Store.__init__` is a design decision made in the task, not in the slice, and it touches existing test constructions. It supports D1a and is explicit about it, so I'm not flagging it. Confirm that "update any direct `Store(...)` constructions in tests" does not force edits to 101–104 tests beyond mechanical ones.

### [NOTE] No numeric NFR in the parent slice, so no load-test or CI-gating task is required

The slice states that the parent architecture sets no numeric targets. The follow-interval and scan-interval figures are design choices, and only the follower bound goes into a contract. No `tests/load/` task or CI-gating task is needed. If the PM wants the "within `follow_interval_seconds` plus read time" bound verified, that belongs in the follower tests in file 2.

### Run Digest

- Response length: 5740 chars
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
- Duration: 45.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
