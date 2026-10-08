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
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 471687558981a404e164767dfe4136f6e517c8bd
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 40.3
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 7.3 does not depend on the completed tenant"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:192-196"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Behaviour for an absent record between Tasks 6.3 and 6.4 is undefined"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:70-77"
  - id: F003
    severity: concern
    category: task-scoping
    summary: "Where parked watches are skipped is spread over Tasks 6.5 and 6.6"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:121-141"
  - id: F004
    severity: concern
    category: commit-checkpoints
    summary: "Sections 7.1 and 7.3 defer their commits to the following test task"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:168, 204"
  - id: F005
    severity: note
    category: requirements-consistency
    summary: "\"No tick starts a subprocess\" conflicts with the per-change label capture"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:140, 280"
  - id: F006
    severity: note
    category: traceability
    summary: "Settings, flags and idle-check wording differ slightly from the slice"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:35, 141"
  - id: F007
    severity: note
    category: scope
    summary: "`cf_layout.py` is not in the slice's component list"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:120"
  - id: F008
    severity: note
    category: nfr-coverage
    summary: "No load test or CI gate is required"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:275"
  - id: F009
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks in this file"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:23-370"
  - id: F010
    severity: pass
    category: task-scoping
    summary: "Sizing, test-with pattern and checkpoints are sound"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:23-340"
---

# Review: tasks — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 7.3 does not depend on the completed tenant

Task 7.1 depends on Task 3.6, Task 7.2 on 7.1, and Task 7.3 on 7.2. No dependency chain reaches Tasks 6.1–6.6. Task 7.3 wires `CFWatchTenant` into `start`, so it should name Task 6.6, the last tenant task, as a dependency. The file order currently supplies this ordering only by convention. A junior AI could start Section 7 before the tenant is finished.

### [CONCERN] Behaviour for an absent record between Tasks 6.3 and 6.4 is undefined

Task 6.3 says it "covers records that are present; absence … is Task 6.4". Its per-watch loop reads `tracked_fields(record)` from the file, and it never says what happens when the linked id is not in the file. At the end of 6.3, which has its own commit and passing tests, that path is undefined. It would likely raise a `KeyError` or hit an untyped branch. Add a step so 6.3 skips the watch explicitly or leaves a clearly marked stub. Alternatively, move the absent-record branch to 6.3 and keep only the vanish and reactivation semantics in 6.4.

### [CONCERN] Where parked watches are skipped is spread over Tasks 6.5 and 6.6

Task 6.5 sets the watch to `failed` and says "go on to the next watch". Task 6.6 says a sidecar at or above the limit "leaves the watch skipped in dispatch". Neither task has a step for the skip predicate in the dispatch loop. After 6.5, a `failed` watch would be retried on the next dirty dispatch, which contradicts the slice criterion. The Task 6.6 test "a failed watch is skipped on later scans" does check the behaviour, but the implementing step is only implied. Add an explicit step in 6.6 to filter `failed` watches in the dispatch loop, based on sidecar existence.

### [CONCERN] Sections 7.1 and 7.3 defer their commits to the following test task

Tasks 7.1 and 7.3 are "Committed with" 7.2 and 7.4, so their implementation and tests land in one commit. This fits the test-with pattern, and the gap is only one task. The project rule is at least one commit per task, so either commit each task or state the exception in the Context Summary.

### [NOTE] "No tick starts a subprocess" conflicts with the per-change label capture

The slice's Technical Requirements say no tick starts a subprocess. The Data Flow section says to re-capture `cf --version` on each detected change. The tasks resolve this sensibly: Task 6.3 captures the label only on a recording read, it tests that idle ticks never start a subprocess, and Task 8.6 reports the reading to the PM. Consider fixing the slice wording so the contradiction does not reach later readers.

### [NOTE] Settings, flags and idle-check wording differ slightly from the slice

The slice describes an "in-memory cache of known watch ids updated when `watch_cf` submissions are applied". The tasks use a `cf_watch_revision` counter and a per-scan existence check for `failed` sidecars. Task 8.6 reports both as PM-visible decisions, which is the right handling. Task 8.3 documents the idle-tick exception in `process-contract.md`.

### [NOTE] `cf_layout.py` is not in the slice's component list

The small `cf_layout.py` module is not in the slice's Component Structure. It is justified by the DRY rule (one definition of the sidecar path) and its scope is minimal, so it is not scope creep.

### [NOTE] No load test or CI gate is required

The slice restates no throughput or latency NFR. The idle-tick "one `stat`" guarantee is a functional criterion, covered by `test_cf_watch_idle` and `test_cf_watch_label`. A `tests/load/` task and CI wiring are not needed.

### [PASS] Success criteria trace to tasks in this file

Each slice criterion handled here has a task and a named test:
- **First snapshot, `cf set phase`, noise-only writes and unlinked changes:** Task 6.3.
- **Remove and restore, never-present id, deactivate and reactivate, multiple writes, restart and catch-up:** Task 6.4 and Task 7.4.
- **`unreachable` and `unrecognized`, re-read only on signature change:** Task 6.2.
- **Bounded failure and sidecar retry:** Tasks 6.5 and 6.6.
- **Idle tick cost:** Task 6.1.
- **Listings, `start` wiring, and the end-to-end CLI test:** Sections 7 and 8.1.
- **Contract docs and the four contract updates plus `CHANGELOG`:** Tasks 8.2–8.3.
- **Single-definition and import-boundary rules:** Task 8.4.
- **Verification Walkthrough:** Task 8.5.
- **Requirement-to-test trace:** Task 8.7.

I found no gaps and no untraced scope.

### [PASS] Sizing, test-with pattern and checkpoints are sound

Efforts of 1–4 are reasonable for a junior AI. Every implementation task in Section 6 is followed by its own test file. Commits are spread across Tasks 6.1–6.6, 7.2, 7.4 and 8.1–8.4 rather than batched at the end. Tasks 8.5–8.6 are report-only, and they are small enough to leave as separate tasks.

### Run Digest

- Response length: 6390 chars
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
- Duration: 40.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
