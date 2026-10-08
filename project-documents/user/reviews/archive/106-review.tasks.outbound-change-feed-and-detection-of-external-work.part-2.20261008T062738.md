---
docType: review
layer: project
reviewType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 5d387ea192f7f4469f164ec1550234e2cd0c06c8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 51.6
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: task-sizing
    summary: "Task 9.6 is oversized and will likely exceed the ~300-line file guideline"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:420-446"
  - id: F002
    severity: concern
    category: completeness
    summary: "Task 9.9 does not spell out the baseline-failure path or which recording paths the counter wraps"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:487-503"
  - id: F003
    severity: concern
    category: ambiguity
    summary: "Task 9.7's wording could be read as deferring baselining"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:457"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "Task 6.5 does not test the hand-edit shape of `record_detected_verdict`"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:105-110"
  - id: F005
    severity: note
    category: traceability
    summary: "Task 7.2 does not repeat the D1a follower-suite test, but it is covered"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:325-340"
  - id: F006
    severity: note
    category: cross-file-coverage
    summary: "Criteria whose verification falls in file 3"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md"
  - id: F007
    severity: note
    category: design-consistency
    summary: "Slice design is internally inconsistent on the `attribute_review` signature"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:90"
  - id: F008
    severity: note
    category: nfr
    summary: "No NFR load test or CI gating task is required"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:314"
  - id: F009
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern, and commit cadence"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md"
  - id: F010
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for Sections 6–9"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 9.6 is oversized and will likely exceed the ~300-line file guideline

Task 9.6 bundles about 13 distinct scenarios into one task and one test file (`tests/process/test_review_detection.py`): ingest rounds, provider failure, series, hand edit, unattributed (zero and several), unparseable, restart, version-label variants, directory removal, interval, reactivation, delete/restore, and manual ingest. Task 9.8 then appends more cases to the same file. That is likely well over 300 lines and too much for one junior pass. Split it, for example into 9.6a (ingest, series, hand edit, restart, version label) and 9.6b (attribution outcomes, unparseable, unreachable, reactivation, interval, manual ingest). Put them in separate modules, and put the 9.8 cases in a third module or in the matching one.

### [CONCERN] Task 9.9 does not spell out the baseline-failure path or which recording paths the counter wraps

Task 9.3 defers baseline counting and parking to 9.9. Task 9.9's steps only say "before the recording transaction, write or increment the sidecar", which reads as the ingest path. Baseline-key sidecar handling appears only as a trailing clause ("A parked baseline leaves the watch `failed`…"). The slice design says the same bounded rule covers `unparseable` and `unattributed` ledger writes (the store write can fail there too) and the baseline write. Add explicit steps for each. The baseline step needs: increment the `baseline-{sha}` sidecar, skip baselining when parked, and don't scan a `failed` watch. The record step needs: wrap all three recording outcomes, not only `ingested`. Also, the line "Detection skips any `(project, digest)` with a parked sidecar" duplicates step 2 and can be dropped.

### [CONCERN] Task 9.7's wording could be read as deferring baselining

"Before scanning a project… skip that project this tick" does not say that baselining of unbaselined watches is exempt. The slice design applies the defer rule only to "each active, baselined watch". A junior could place the check ahead of the baseline branch from Task 9.3, so a watch registered during an open `SQ_RUN` would sit un-baselined. Say explicitly that the check applies to the scan branch only, and add a Task 9.8 case showing a baseline still happens while an `SQ_RUN` entry is open.

### [CONCERN] Task 6.5 does not test the hand-edit shape of `record_detected_verdict`

Task 6.4 specifies the case where the same verdict id comes with a new ledger key (the hand-edit scenario). The verdict is a retry no-op and the new `ingested` row is added. Task 6.5 tests only the same-key repeat and a duplicate-key failure. The core atomicity method is first exercised for the hand-edit shape in Task 9.6 through the tenant. Add one store-level case: same verdict id, different digest, so no second verdict, one new ledger row, and one `review_detected` change.

### [NOTE] Task 7.2 does not repeat the D1a follower-suite test, but it is covered

The slice design says the `read_transaction()` test lives in "the follower test suite". The task breakdown places it in `tests/store/test_read_transaction.py` (Task 4.4). That is a reasonable placement, and Task 4.4 includes a control case. No action needed.

### [NOTE] Criteria whose verification falls in file 3

These slice criteria are not fully closed within this file and depend on Sections 10–11. The "`failed` in `inspect detections`" listing, from Task 9.10 and `parked_files`, needs Task 10.1. "`sq --version` runs once, before the loop; no tick starts a subprocess" needs the Task 10.3 wiring plus a test. "`amoeba feed --follow` started while the process is stopped" is in Task 11.2. I did not verify file 3's coverage of these. The reviewer of file 3 should confirm them. This file correctly defers to them.

### [NOTE] Slice design is internally inconsistent on the `attribute_review` signature

The Component Structure lists `attribute_review(nodes, slice_name)`. The API Contracts table lists `attribute_review(store, project_id, slice_name)`. Task 6.2 follows the API table, which is the right choice. Consider correcting the Component Structure line in the slice design.

### [NOTE] No NFR load test or CI gating task is required

The slice states that the parent architecture sets no numeric targets. The intervals are configuration defaults, not NFR commitments. The only contract bound is the follower's wake-up interval, which Task 7.2 tests functionally. No `tests/load/` or CI gate task is warranted.

### [PASS] Sequencing, test-with pattern, and commit cadence

Each implementation task is immediately followed by its test task: 6.1–6.3, 6.4/6.5, 7.1/7.2, 7.3/7.4, 8.2–8.4, 9.1/9.2, 9.3/9.4, 9.5/9.6, 9.7/9.8, and 9.9/9.10. Task 9.2a pairs its layout module with its tests. Dependencies run forward only, with no cycles. The Task 8.1 gate on slice 105 stops work and asks the PM rather than stubbing the parser. Commits fall at least once per section, not batched at the end.

### [PASS] Success-criteria coverage for Sections 6–9

These slice criteria each map to a task:
- Follower resume and no-repeat, and killed follower: Tasks 7.2 and 7.4.
- Ingest as `artifact_frontmatter` with `source_path`: Task 9.6.
- Provider-failure standing: Task 9.6.
- Part-1/part-2 series separation: Task 9.6, with the grouping built in file 1.
- Hand-edit produces no second verdict: Task 9.6.
- Unattributed with candidates, unparseable not retried, baseline-only for existing files: Tasks 9.4 and 9.6.
- Unreachable directory and unreadable-file baseline: Task 9.4.
- Manual `ingest review` yields `recorded_since`: Task 9.6.
- `SQ_RUN` defer and `runner_issued` skip: Task 9.8.
- Restart idempotence: Task 9.6.
- Deleted-between-list-and-read: Tasks 8.4 and 9.6.
- Bounded failure: Task 9.10.

I found no scope creep. Task 6.4 (`record_detected_verdict`) is an addition to the design's API table, but it is justified by the design's "one transaction" requirement.

### Run Digest

- Response length: 7660 chars
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
- Duration: 51.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
