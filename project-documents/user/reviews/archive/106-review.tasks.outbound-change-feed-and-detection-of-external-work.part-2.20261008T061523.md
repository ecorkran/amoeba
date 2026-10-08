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
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: cd233625952d49b287a151eea6dede5de055abfd
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 35.8
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 9.4 tests scan behavior that is not implemented until Task 9.5"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:330-376"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 9.5 depends on a parked-sidecar skip that Task 9.9 builds"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:384-390"
  - id: F003
    severity: concern
    category: coverage-gap
    summary: "No task owns the unreachable/recovery logging for already-baselined watches"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:340-363"
  - id: F004
    severity: note
    category: task-sizing
    summary: "Task 9.3 is heavy and bundles several concerns"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:330-349"
  - id: F005
    severity: note
    category: coverage
    summary: "Criterion \"feed --follow started while the process is stopped\" has no test in this file"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:188-204"
  - id: F006
    severity: pass
    category: coverage
    summary: "Review-producing kinds, attribution, and atomic ingest are fully covered"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:22-114"
  - id: F007
    severity: pass
    category: coverage
    summary: "Follower, `amoeba feed`, review sources, and detection tests trace to the slice's functional requirements"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:118-504"
  - id: F008
    severity: pass
    category: nfr
    summary: "No load-test task is required"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:312-321"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 9.4 tests scan behavior that is not implemented until Task 9.5

Task 9.3 defers scanning with "otherwise scan (Task 9.4)". But 9.4 is the baseline *test* task, and the scan path is built in Task 9.5. Task 9.4 nonetheless asserts scan-path behavior:
- "removing a baselined directory later and restoring it logs the same pair and the process keeps ticking"
- "Inactive watch is not scanned; reactivation does not re-baseline"
- the scan-interval gating

A junior AI following the order has no scan code to test. Two options:
- Move those cases into the 9.6 tests, or into a test step under 9.5.
- Have 9.3 implement the scan-interval gating and the active/inactive filter, and fix the reference to say Task 9.5.

### [CONCERN] Task 9.5 depends on a parked-sidecar skip that Task 9.9 builds

Task 9.5's first step says to skip a file if it "has a parked sidecar (Task 9.9)". That is a forward dependency on a task four steps later. Task 9.9 repeats the rule ("Detection skips any `(project, digest)` with a parked sidecar"), so the same logic is described twice. Remove the sidecar clause from 9.5 and let 9.9 add the skip, or move the skip into 9.5 and drop it from 9.9. The skip check is the only piece that needs the sidecar layout, which already exists after 9.3.

### [CONCERN] No task owns the unreachable/recovery logging for already-baselined watches

The slice's Errors section and the success criterion "A watched directory that is removed shows `unreachable`; the process keeps running and resumes when it returns" apply to scanning, not just baselining.
- Task 9.3 describes the one-ERROR/one-INFO transition only inside the baseline failure table.
- Task 9.5 (the scan path) never mentions catching `ReviewDirectoryUnavailableError` or the transition logging.
- Task 9.4 tests the behavior without any task implementing it.

Add an explicit step to 9.5 for handling `ReviewDirectoryUnavailableError` during scan. It should cover the transition-only logging, the in-memory state kept per watch, and ensuring that error never propagates out of `tick`.

### [NOTE] Task 9.3 is heavy and bundles several concerns

Task 9.3 holds:
- the tenant skeleton and scan cadence
- the baseline with a five-row failure table
- the `detection_layout.py` module
- the `watch_state` function

It is rated effort 4 and creates two files. The layout module and `watch_state` are pure and could be their own small task, tested with the sidecar cases in 9.4. This is borderline, not blocking.

### [NOTE] Criterion "feed --follow started while the process is stopped" has no test in this file

The slice requires that `amoeba feed --follow` started while the process is stopped prints new changes once the process starts and applies submissions. Task 7.4 follows with a read-write store and covers the kill/resume case. It never starts the follower with the process down and then starts the process. The end-to-end test in file 3 may cover it. Confirm that, or add a case to 7.4.

### [PASS] Review-producing kinds, attribution, and atomic ingest are fully covered

Tasks 6.1–6.5 cover D4/D5, the table of attribution cases (zero, one, several, wrong kind, other project, `None` slice), the open-entry read for `SQ_RUN` versus `CF_WRITE`, and `record_detected_verdict` atomicity and idempotence. Each implementation task is followed by its test task, and the commit lands at the test task.

### [PASS] Follower, `amoeba feed`, review sources, and detection tests trace to the slice's functional requirements

Sections 7–9 map to these slice criteria:
- cursor resume with no gap or repeat
- killed follower
- the `FeedSettings` defaults defined once
- the file-race table
- `source_document` pass-through
- the provider-failure file
- series separation across parts
- hand-edit idempotence
- `unattributed`/`unparseable`
- restart
- version label precedence
- reactivation
- defer/skip
- bounded failure

The tests use real fixtures. Commit checkpoints are spread across the sections. I found no scope creep. The `capture_version_label` generalization and the `source_document` pass-through both trace to the slice's sq label requirement and D7.

### [PASS] No load-test task is required

The slice states no NFR that calls for a load test. The interval and timeout values are sizing choices, and the architecture sets no numeric targets. So `tests/load/` and CI gating are not needed.

### Run Digest

- Response length: 5833 chars
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
- Duration: 35.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
