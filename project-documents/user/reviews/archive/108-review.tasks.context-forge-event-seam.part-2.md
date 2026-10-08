---
docType: review
layer: project
reviewType: tasks
slice: context-forge-event-seam
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: bd800af745253d59f5b55593780327acd05bc420
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
durationSeconds: 47.1
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are covered by tasks and named tests"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:262-289"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Dependencies are linear and the code is verified where it is cited"
    location: "src/amoeba/process/observers/cf_readback.py:91"
  - id: F003
    severity: concern
    category: test-integrity
    summary: "Real-`cf` success-path tests skip silently when `cf` is absent"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:81"
  - id: F004
    severity: concern
    category: spec-consistency
    summary: "The `failed`-watch sidecar check cuts against the \"one `stat`\" idle-tick guarantee"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:119"
  - id: F005
    severity: concern
    category: task-sizing
    summary: "Task 6.3 is oversized, and Task 6.5 is close behind"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:70-88"
  - id: F006
    severity: note
    category: task-sizing
    summary: "Task 6.4 is test-only and overlaps Task 6.3's label assertion"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:92-107"
  - id: F007
    severity: note
    category: clarity
    summary: "Task 6.5 refers to itself as a consumer of `cf_layout.py`"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:117"
  - id: F008
    severity: note
    category: coverage
    summary: "customData-only coverage lives in file 1 and is only referenced here"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:328"
---

# Review: tasks — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are covered by tasks and named tests

- **Functional criteria:** each of the 12 maps to a task.
  - First snapshot, `cf set phase`, noise-only writes and unlinked changes: 6.3.
  - Catch-up and restart: 6.3, 7.4, 8.1.
  - Removed and restored projects, and `missing`: 6.3.
  - `unreachable` and `unrecognized`, including re-read only on a changed signature: 6.2.
  - Deactivate and reactivate: 6.3.
  - Bounded failure: 6.5.
  - Idle tick: 6.1.
- **Technical and integration criteria:**
  - Migration upgrade and the feed invariant are covered by file 1, and 8.7 re-checks both.
  - Import boundaries and the single definition of `IGNORED_KEYS`, `$present` and the CF location rule: 8.4.
  - Real-`cf` end-to-end run: 8.1.
  - `cf-contract.md` and the contract updates: 8.2 and 8.3.
  - Verification walkthrough: 8.5.
- **Scope creep:** I found none. Every task traces to a criterion or to a doc or integration requirement.
- **NFR load tests:** the slice restates no throughput or latency NFR, so no `tests/load/` task or CI gating task is needed.

### [PASS] Dependencies are linear and the code is verified where it is cited

Tasks 6.1 to 8.7 chain without cycles. Tests sit next to their implementation, and commits come at the end of nearly every task. Tasks 6.4 and 7.1/7.3 defer their commit to the paired test task, which is acceptable. The code that Tasks 6.4 and 7.3 rely on exists: `capture_version_label(timeout_seconds)` and `VERSION_UNAVAILABLE`, which `src/amoeba/process/settings.py:57` also feeds through `cf_timeout_seconds`.

### [CONCERN] Real-`cf` success-path tests skip silently when `cf` is absent

Task 6.3 and Task 8.1 skip "with a clear reason" if `cf` is not on `PATH`. The slice requires that success-path tests use real `cf`-written files, with no hand-built stand-ins. On a machine or CI runner without `cf`, the main snapshot tests would skip, the suite would still pass, and the criterion would go unchecked. Add a rule that the skip is allowed only locally, and that an environment variable or CI marker turns absence into a failure. Also state where the 6.3 and 8.1 tests are expected to run. That keeps the repo's "fail explicitly" principle.

### [CONCERN] The `failed`-watch sidecar check cuts against the "one `stat`" idle-tick guarantee

Task 6.5 adds one existence check per `failed` watch on every scan interval. The slice criterion says an idle tick performs one `stat`. Task 8.3 documents the idle-tick guarantee as "one `stat`, no query, no subprocess", and Task 8.7 traces it to `test_cf_watch_idle`. When a failed watch exists, the tick does more than one filesystem call. Task 8.6 reports the sidecar check to the PM, which is good, but two things are still missing.
- State the exception in the `process-contract.md` text of Task 8.3: the guarantee holds when no watch is `failed`.
- Say in Task 6.5 where the sidecar check sits relative to Task 6.1's early return on an unchanged signature, and add a test that no sidecar check happens when no watch is `failed`.

### [CONCERN] Task 6.3 is oversized, and Task 6.5 is close behind

Task 6.3 carries the whole diff-and-record loop (label capture, state transitions, no node writes). It also carries about 13 test cases against the real `cf` CLI, including restart and catch-up. A junior AI would have to hold a lot at once. Consider splitting it: first the record and state logic with the core cases (link, `cf set`, noise-only, unlinked), then the remaining cases (remove/restore, never-present, deactivate/reactivate, batching, restart/catch-up). Task 6.5 combines a new module, a transaction wrapper, `failed` skipping, sidecar-removal retry and its tests. That is acceptable at effort 4, but it is a split candidate if it stalls.

### [NOTE] Task 6.4 is test-only and overlaps Task 6.3's label assertion

The label behaviour is implemented in 6.3, and 6.3's success criteria already assert the counting fake. Task 6.4 adds label-provenance tests as a separate task with no implementation. It could be folded into 6.3, or into the 6.3 split suggested above. Keeping it separate is harmless; the test follows the implementation immediately.

### [NOTE] Task 6.5 refers to itself as a consumer of `cf_layout.py`

"Task 6.5 and the tests import it" reads as a self-reference. The likely intent is that the tenant code and the tests import the module. Rewording would avoid confusing a junior AI.

### [NOTE] customData-only coverage lives in file 1 and is only referenced here

Task 6.3's tests cover a write that touches only `updatedAt`. The `customData`-only case is attributed in Task 8.7 to `test_cf_watch_snapshots`, but 6.3's case list has no `customData` case (`test_cf_diff` handles it at diff level). Task 8.7 would add the assertion where it is missing, but it is cheaper to add a `customData`-only case to 6.3 up front.

### Run Digest

- Response length: 5996 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 47.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
