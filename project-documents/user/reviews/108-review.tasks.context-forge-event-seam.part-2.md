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
reviewedSha: 95aff093a99aecc6276d9fd65207b9a720969886
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 48.6
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "File-level states can silently un-park a `failed` watch"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:57"
  - id: F002
    severity: concern
    category: requirements-conflict
    summary: "Known conflict with an LLD Technical Requirement is deferred to the final report"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:101"
  - id: F003
    severity: note
    category: scope
    summary: "Idle-tick mechanism differs from the LLD; disclosed"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:36"
  - id: F004
    severity: note
    category: task-clarity
    summary: "Task 7.2 process test leaves the \"change the file while down\" step unspecified"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:206"
  - id: F005
    severity: note
    category: granularity
    summary: "Tasks 8.6 and 8.7 are not separately completable"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:317"
  - id: F006
    severity: note
    category: nfr
    summary: "No load test or CI gate is required"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:19"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success criteria coverage is complete"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:332"
  - id: F008
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern hold"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:24"
---

# Review: tasks — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] File-level states can silently un-park a `failed` watch

Task 6.2 sets "every active watch" to `unreachable` or `unrecognized`. Once the file is recognized again, it moves those watches back to `pending`. It never says what happens to a watch already `failed`.
- Task 6.6 (line 142) skips a watch only while its cache state is `failed` and its sidecar is at the limit.
- Task 6.7 (line 162) retries only watches whose state is `failed`.
- If the file goes missing or unrecognized and then recovers, a parked watch moves `failed` → `unreachable` → `pending`. It is then retried without the sidecar being removed.
- That contradicts the LLD: "skipped until the sidecar is removed".

Fix: have Task 6.2 exclude `failed` watches from the file-level transitions, or require Task 6.6's skip rule to check the sidecar instead of the cache state. Add a test in `test_cf_watch_file_states` or `test_cf_watch_failure` for `failed` → file missing → file back → still parked.

### [CONCERN] Known conflict with an LLD Technical Requirement is deferred to the final report

Task 6.4 chooses to spawn `cf --version` inside a tick whenever a snapshot is about to be recorded. The task itself admits this conflicts with the LLD's Technical Requirement "No tick starts a subprocess". It asks the PM to amend the LLD only in Task 8.6, after the work is built and tested.
- Task 8.7 then traces "no subprocess" back to tests that assume the new reading.
- The subprocess runs synchronously in the shared tick thread, bounded by `cf_timeout_seconds`. It can delay the inbox and detection tenants during a recording.
- A junior AI cannot settle this. The PM should decide before Section 6 starts: either amend the LLD, or capture the label off the tick path.

### [NOTE] Idle-tick mechanism differs from the LLD; disclosed

The LLD describes an in-memory cache of known watch ids, updated when `watch_cf` submissions are applied. The tasks use a store-side `cf_watch_revision` counter (Task 4.3), cached per project (Task 6.1). Task 6.7 adds an existence check per `failed` watch. Both are listed in Task 8.6, and Task 8.3 documents them. The tasks are internally consistent and the deviation is traceable. I'm raising it only so the PM confirms the idle-tick criterion wording is amended.

### [NOTE] Task 7.2 process test leaves the "change the file while down" step unspecified

Task 7.2's process test starts from a copy of `projects_two_projects.json`. It says to "change the file while it is down" but not how. Name the Task 1.3 `rewrite_projects_file` helper, or use the real `cf` as Task 8.1 does. That keeps the catch-up case inside the "files written by the real `cf`" rule from the LLD's Technical Requirements.

### [NOTE] Tasks 8.6 and 8.7 are not separately completable

Task 8.6 assembles a list but delivers it only in Task 8.7's final message, and it has no commit and no checkable output of its own. Fold it into Task 8.7, or make the list a file the task checks in. Task 8.5 is similar: it produces only a report, which suits a verification step.

### [NOTE] No load test or CI gate is required

The LLD states no throughput or latency NFR. "Within about two scan intervals" and "one `stat` per idle tick" are functional criteria, and the tasks cover them with fake-clock tests and spies (Tasks 6.1, 6.4). The file's statement that no load test or CI gate is planned is consistent with the checklist. If the PM later treats the idle-tick guarantee as an NFR, a `tests/load/` task and CI wiring would be needed.

### [PASS] Success criteria coverage is complete

Each Functional and Technical Requirement maps to a task and a named test, and Task 8.7 re-checks every one against a named test:
- Snapshot recording, noise filtering and unlinked projects: Task 6.3.
- Absence, restoration, `missing`, deactivate/reactivate, restart and catch-up: Task 6.5.
- `unreachable` and the four `unrecognized` shapes: Task 6.2.
- Bounded failure and retry: Tasks 6.6 and 6.7.
- Idle tick: Task 6.1.
- Listings, wiring and end-to-end: Tasks 7.1, 7.2 and 8.1.
- `cf-contract.md` and the other contracts: Tasks 8.2 and 8.3.
- Import and single-definition boundaries: Task 8.4.

I found no scope creep beyond the disclosed items above. `cf_layout.py` is justified by D3 and reported.

### [PASS] Sequencing and test-with pattern hold

The dependency chain 6.1 → 6.7 → 7.2 → 8.1 → 8.5 is acyclic. Task 7.1 depends only on Task 3.6 and is ordered before the Task 7.2 test that reads it. Each implementation task carries its own tests. The writer-guard test is moved into Task 6.3, where it asserts something real. Every code task has a commit step spread across the sections, not batched at the end. Task sizes (efforts 2–4) are reasonable for a junior AI. Task 6.1 is the densest, with the cache, signature and gate.

### Run Digest

- Response length: 6056 chars
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
- Duration: 48.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
