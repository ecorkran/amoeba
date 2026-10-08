---
docType: review
layer: project
reviewType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 0fee83708104833e2eac43087fc2ac55009feebd
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 66.1
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria for attribution, follower, sources, and tenant all trace to tasks"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:24-570"
  - id: F002
    severity: pass
    category: coverage
    summary: "D1a read-transaction criterion is owned by file 1, with a follower-level check here"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:161"
  - id: F003
    severity: pass
    category: sequencing
    summary: "Test-with pattern and commit cadence are respected"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:24-570"
  - id: F004
    severity: note
    category: consistency
    summary: "Task 8.1 correctly follows slice 105 where slice 106 words it differently"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:216-232"
  - id: F005
    severity: note
    category: nfr
    summary: "No load test or CI gate, with the reasoning stated to the PM"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:20"
  - id: F006
    severity: note
    category: task-scope
    summary: "Large tenant file and a shared lifecycle test module may exceed ~300 lines"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:374"
  - id: F007
    severity: note
    category: sequencing
    summary: "Task 7.1 depends on Task 6.3 without needing it"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:127"
  - id: F008
    severity: note
    category: task-clarity
    summary: "Minor clarity items for junior execution"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:180"
---

# Review: tasks — slice 106

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria for attribution, follower, sources, and tenant all trace to tasks

Each criterion this file can prove maps to a task:
- **Attribution (D4):** Tasks 6.2–6.3.
- **Feed (follower and CLI):** Tasks 7.1–7.4 cover the `--after` exactness, the kill-and-resume case, and following with the process stopped.
- **Registration and baselining:** Tasks 9.3–9.4 cover baselining, `unreachable`, `baseline_pending`, and the scan interval.
- **Ingest, series, and hand edit:** Task 9.6 covers the ingest rounds, the `provider_failure` file, the part-1/part-2 series, the hand edit, and restart.
- **Refusals and the label rule:** Task 9.6a covers `unattributed` with zero and two candidates, `unparseable`, the version-label rule, and `recorded_since` after a hand ingest.
- **Availability and races:** Task 9.6b covers directory loss and recovery, and the delete-and-restore race.
- **Defer and skip (D5):** Tasks 9.7–9.8 cover the open `SQ_RUN` defer and `runner_issued` skip.
- **Bounded failure:** Tasks 9.9–9.10 cover each wrapped path and sidecar removal.

The deferred criteria are routed to file 3: `inspect watches`/`inspect detections` states, the no-subprocess-per-tick and label-captured-once criteria, and the whole-system tests. Task 11.12 traces each of them.

### [PASS] D1a read-transaction criterion is owned by file 1, with a follower-level check here

The design's `read_transaction()` atomicity test is Task 4.4 in file 1. It includes a control case without the transaction. Task 7.2's last bullet adds the snapshot-then-follow usage test, so the criterion is covered at both levels.

### [PASS] Test-with pattern and commit cadence are respected

Every implementation task is followed immediately by its test task:
- 6.1–6.3 and 6.4–6.5
- 7.1–7.2 and 7.3–7.4
- 8.2–8.3 with 8.4
- 9.1 with 9.2
- 9.3 with 9.4
- 9.5 with 9.6, 9.6a, and 9.6b
- 9.7 with 9.8
- 9.9 with 9.10

Commit points fall at 6.3, 6.5, 7.2, 7.4, 8.1, 8.4, 9.2, 9.2a, 9.4, 9.6, 9.6a, 9.6b, 9.8, and 9.10. No dependency is circular. Task 9.2a defines the sidecar layout and reader before the tenant and listings use them, which avoids duplicated readers.

### [NOTE] Task 8.1 correctly follows slice 105 where slice 106 words it differently

Slice 106 ("Interfaces Required") says 105's `to_verdict_input` already carries `sourceDocument` into `VerdictInput`. Slice 105 (line 51) says the opposite: the parser exposes it and "slice 106 adds … the one-line pass-through in `to_verdict_input`." Task 8.1 follows 105 and gates on the parser's exports, so the task is right. The 106 slice wording is stale. Consider correcting it, but nothing here depends on that.

### [NOTE] No load test or CI gate, with the reasoning stated to the PM

The slice states no numeric NFR. The ~5 s detection and 0.25 s follow figures are its own sizing choices, and only the follower bound is called a contract promise. The breakdown adds no `tests/load/` task or CI gate, says so, and defers the PM override to Task 11.11. Task 7.2 does exercise the follower's wake-up bound. That is acceptable. If the PM treats the follower bound as an NFR, a load task and a CI wiring task would be needed.

### [NOTE] Large tenant file and a shared lifecycle test module may exceed ~300 lines

`review_detection.py` accumulates the skeleton, baselining, the reachability helper, the scan path, the defer rule, and `_guarded` across Tasks 9.3, 9.5, 9.7, and 9.9. Task 9.5 allows a conditional split into `review_scan.py`. `test_review_detection_lifecycle.py` also absorbs Task 9.8's cases on top of 9.6b's. Both splits are conditional on the file passing ~300 lines. Making the split an explicit step in Task 9.5, so the later tasks edit the right module, would reduce junior-AI ambiguity.

### [NOTE] Task 7.1 depends on Task 6.3 without needing it

The follower depends only on the feed read API and `read_transaction()` from file 1. It does not use attribution. The chain is harmless in a linear plan, but the dependency is artificial and would block parallel work.

### [NOTE] Minor clarity items for junior execution

- **Task 7.3:** "choose the simpler" of two implementations for the no-follow exit leaves a decision to the junior AI. Pick one.
- **Task 8.3:** the `FileNotFoundError` drop is a deliberate swallow. CLAUDE.md's exception rule (b) requires a comment explaining why, and the task doesn't ask for one.
- **Numbering:** 9.2a, 9.6a, and 9.6b are out of the integer sequence. That is fine if the task-checker handles it.

### Run Digest

- Response length: 5817 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 203
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 66.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
