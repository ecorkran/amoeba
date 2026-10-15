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
sourceDocument: project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 22dc87252bc12ef4efec7290f20dcfbb1044f0b2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
durationSeconds: 59.7
runId: run-20261015-p5-a36b1511
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Functional criteria for attribution, sources, tenant, listings and wiring all trace to tasks"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:23-395"
  - id: F002
    severity: concern
    category: scope-proportionality
    summary: "Duplicate kill -9 / restart process test in Task 8.5 and Task 9.2 Test B"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:388"
  - id: F003
    severity: concern
    category: scope-proportionality
    summary: "Task 9.1 gives test helpers their own smoke-test module"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:409-410"
  - id: F004
    severity: concern
    category: scope-proportionality
    summary: "Doc-drift test extended to four other contracts has no matching success criterion"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:487"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "Store-failure criterion is asserted only up to \"the tick raises\""
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:249"
  - id: F006
    severity: note
    category: sequencing
    summary: "Minor sequencing and cohesion points"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:131"
  - id: F007
    severity: note
    category: nfr
    summary: "No load test is expected, and Task 9.7 reports that decision"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:277"
  - id: F008
    severity: note
    category: coverage
    summary: "Deferred-issue filing is not tracked in this file"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:57"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Functional criteria for attribution, sources, tenant, listings and wiring all trace to tasks

Each criterion in this file's scope has an implementing task and a test task that follows it.
- Verdict ingest, the provider-failure file, the hand edit producing no second verdict, `unattributed` with candidate ids, `unparseable` without retry, and hand recovery with `recorded_since` are all in 7.6.
- Baseline cases, including the all-or-nothing unreadable file, are in 7.4.
- Defer, `runner_issued`, directory removal and restore, and reactivation are in 7.8.
- `sq --version` once and no subprocess per tick are in 8.5.
- Follow-while-stopped and the `resolution` → `runnable` change are in 9.2 Test A.
- The `deferred` and `unreachable` precedence is in 8.2.

Commit checkpoints are spread through the file, and each implementation task is followed by its test task.

### [CONCERN] Duplicate kill -9 / restart process test in Task 8.5 and Task 9.2 Test B

Task 8.5 adds `test_review_detection_process.py`. It starts the real CLI, seeds, registers a directory, ingests a file, runs `kill -9`, restarts, and asserts counts are unchanged. Task 9.2 Test B (line 429) covers the same crash-and-restart scenario through the same launcher, and also covers the provider-failure file and follower resume. 7.6 already pins the same restart assertion in-process.

This has two costs:
- It adds a second slow subprocess test and a long scripted sequence.
- It forces 8.5 to create the launcher conditionally, which 9.1 then wraps. That is an awkward dependency between sections.

Cut the process test from 8.5. Keep the label-once and no-subprocess-per-tick tests, which don't need a real process. Let 9.2 own the real-CLI restart, with the launcher created in 9.1.

### [CONCERN] Task 9.1 gives test helpers their own smoke-test module

No slice success criterion requires `tests/cli/test_detection_e2e_harness.py`, which holds one smoke test per helper and must pass three consecutive times. The helpers are exercised directly by the two end-to-end tests in 9.2, which already run three times consecutively and each alone. Fold 9.1 into 9.2 and drop the smoke module. If the helpers are worth a separate commit, keep the harness file and remove the test file.

### [CONCERN] Doc-drift test extended to four other contracts has no matching success criterion

The slice requires `feed-contract.md` to be enough for initiative 160, and the 9.4 drift test is a reasonable check of that. Step 9.5 then extends `tests/test_contract_docs.py` with required-term lists for `store-contract.md`, `inbox-contract.md`, `process-contract.md` and `evidence-contract.md`. No success criterion asks for that. These docs are prose updates, and term-list tests will be brittle against wording changes. Drop that step from 9.5 and keep the 9.4 test for `feed-contract.md` only.

### [CONCERN] Store-failure criterion is asserted only up to "the tick raises"

The slice criterion is "A store exception while recording a detection is logged at ERROR and **stops the process**." Task 7.6 patches `record_detected_verdict` and asserts the tick raises, the ERROR is logged with the path, and nothing is written. Task 7.5 (line 222) separately tells the implementer to read `ResidentProcess.run` and ask the PM if it doesn't stop. Neither task requires a test that a raising tenant actually ends the host. Add one assertion to 7.6 that runs the tenant under `LocalHost` or `ResidentProcess` and sees it stop. Alternatively, name the existing 102 test that pins this, and have 9.8 verify it.

### [NOTE] Minor sequencing and cohesion points

- Task 7.1 (settings and the version-label helper) depends on 6.2 but uses nothing from Section 6. This is harmless, but it implies an ordering that isn't real.
- Task 5.1's tests arrive two tasks later in 5.3, with 5.2 between them. The "committed with 5.3" note keeps the commits coherent.
- Task 7.8 is named for ownership, but it also carries the directory-removed/restored and reactivation tests (line 289). These fit the baseline or detection modules better. Moving them would make the 7.8 module name honest and the task smaller.

### [NOTE] No load test is expected, and Task 9.7 reports that decision

The slice states that the parent architecture sets no numeric targets. It makes only the follower-interval latency bound a contract promise, which the follower tests cover. No `tests/load/` task or CI gating task is therefore needed. Task 9.7 tells the PM that no load test was added, so the PM can overrule that.

### [NOTE] Deferred-issue filing is not tracked in this file

The slice says each deferred item is "filed as a GitHub issue". They are `read_transaction()`/`change_head()`, `record_runner_report`, and `source_document`. This file has no task or check for that, and I did not verify that the issues exist. If they were filed during the design trim, no action is needed. Otherwise, add a one-line check to 9.7 or 9.8.

### Run Digest

- Response length: 6414 chars
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
- Duration: 59.7 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
