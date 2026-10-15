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
reviewedSha: 63eb9efb6b38fec581d2cdbd1f514efa2e462865
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 65.1
runId: run-20261015-p5-a36b1511
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "File 1 covers its share of the slice success criteria"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit checkpoints"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:25"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 3.3 bundles five separable pieces"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:298-317"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Overlapping verification mechanisms add weight beyond what the criteria need"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:234-252"
  - id: F005
    severity: note
    category: coverage
    summary: "The `resolution` → `runnable` criterion is first asserted end to end in file 2"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:215-230"
  - id: F006
    severity: note
    category: nfr
    summary: "No load-test task, consistent with the design"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:19"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] File 1 covers its share of the slice success criteria

Each criterion that file 1 owns has a task, with its test following immediately:
- **Reconciliation and version upgrade:** feed replay reconciles with every tracked table (Task 2.5, extended in 4.2). The 5→6 upgrade is Task 1.4.
- **Follower and CLI:** the `--after`/resume criterion (3.4, 3.6) and the follower failure table (3.4).
- **Ledger and registration:** unattributed recovery via `recorded_since` (4.2). Baseline atomicity (4.5, 4.6) and the `watch_reviews` kind (4.3, 4.4).
- **Detection write path:** the one-transaction `ingested` write (4.7, 4.8).

The detection-tenant, defer, listing, end-to-end and docs criteria are covered in file 2 (Sections 5–9). I found no unmet requirement and no task without a source in the design.

### [PASS] Sequencing and commit checkpoints

- **Order:** dependencies run linearly with no cycles.
- **Test-with:** each implementation task is followed immediately by its test task (1.3→1.4, 2.1→2.2, 2.3→2.4, 3.1→3.2, 3.3→3.4, 3.5→3.6, 4.1→4.2, 4.3→4.4, 4.5→4.6, 4.7→4.8).
- **Commits:** checkpoints are spread across all four sections. The pairing rule ("a commit never holds untested behavior") is stated once and followed.
- **Migration 006:** growing it in place across Tasks 1.3, 2.1, 2.3 and 4.1 is explained, and the "no 007" rule is explicit.
- **`NOT_YET_EMITTED`:** the constant added in 2.5 and deleted in 4.2 keeps the suite green between tasks.

### [CONCERN] Task 3.3 bundles five separable pieces

Task 3.3 is rated effort 3 but combines five pieces:
- `FeedSettings`.
- Moving `project_store_path` into `store/paths.py` and making `process/supervisor.py` delegate to it.
- `Store.data_version()` plus its statement in `sql.py`.
- The `follow` loop.
- The failure table, including busy-versus-other `OperationalError` classification.

The path refactor and `data_version()` touch four existing files and are independent of the follower logic. As written, `data_version()` is only checked indirectly through the follower test, and the refactor rides on "existing supervisor tests". Split out a small preceding task, "`project_store_path` delegation and `Store.data_version()`", with a direct assertion for each. Task 3.3 then holds only `FeedSettings`, `follow` and the failure handling, which is what a junior AI can complete in one pass.

### [CONCERN] Overlapping verification mechanisms add weight beyond what the criteria need

These overlap, and the slice's own invariant-test criterion is already met by the reconcile test and the every-kind check:
- **Task 2.5** has three overlapping mechanisms. The every-kind test fails if a literal drifts, because the kind never appears in the sequence's changes. The literal test (trigger SQL contains each kind) is therefore redundant. The parametrized dropped-trigger test checks the test itself rather than a success criterion. Keep `reconcile` plus the every-kind check, and cut the literal test, or fold it into the dropped-trigger check. Task 4.2 repeats the extra mechanisms ("the literal test also checks each `SILENT_OUTCOMES` value", "the dropped-trigger parametrization gains the new trigger"), so cut those there too.
- **Follower resume** is asserted in Task 3.4, again with `kill -9` in Task 3.6, and again in Task 9.2 Test B. Keep the full resume case in 3.4 and the real-process kill in 3.6. In 9.2, assert only what needs the running process.
- **Task 1.2's `test_feed_models.py`** (enums have exactly their values, dataclasses are frozen) mostly restates the declarations. Task 1.5 and the invariant test already catch a wrong value. Consider dropping the "frozen" and "exact values" checks.
- **Task 1.6** is justified by the "defined once" and layering requirements and is reasonable. Its Rule 3 module list is long, so it needs upkeep as files change.

### [NOTE] The `resolution` → `runnable` criterion is first asserted end to end in file 2

The criterion "a `resolution` submission applied by the process produces `node_status_changed` blocked→`runnable`" is tested only in Task 9.2 through the real CLI. Task 2.2 covers `block` and `resolve` on the store, and Task 2.4 covers an `intent` submission through `apply_submission`. Adding one `resolution` submission case to Task 2.4 would catch a trigger regression eight sections earlier. This is optional.

### [NOTE] No load-test task, consistent with the design

The slice sets no numeric NFR. Its only latency promise is "within `follow_interval_seconds` of the commit". Task 3.4's "generous multiple of the interval" check covers that. File 2 states that no load test is added and tells the PM in Task 9.7, so there is no CI-gating gap.

### Run Digest

- Response length: 5839 chars
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
- Duration: 65.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
