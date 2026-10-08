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
reviewedSha: f5d55a58aa9aabb0a35ac75ec7b1518452b70078
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
durationSeconds: 45.0
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Functional success criteria all map to a task and a named test"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:23-224"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern, and commit cadence"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:27-368"
  - id: F003
    severity: concern
    category: completeness
    summary: "Sidecar cleanup is specified inconsistently between Tasks 6.5 and 6.6"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:138-140"
  - id: F004
    severity: concern
    category: design-clarity
    summary: "How the tenant learns `failed` state, and where the existence check sits in the tick, is unspecified"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:35-37"
  - id: F005
    severity: note
    category: error-handling
    summary: "Exception-handling wording in Task 6.5 should match project rules"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:120"
  - id: F006
    severity: note
    category: scope
    summary: "Task-level deviations from the slice are surfaced to the PM"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:78"
  - id: F007
    severity: note
    category: sequencing
    summary: "Task 7.1 depends on the tenant unnecessarily"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:155"
---

# Review: tasks — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Functional success criteria all map to a task and a named test

Each Functional Requirement in the slice traces to a task and a test file:
- First snapshot, `cf set phase`, noise-only writes, and unlinked projects: Task 6.3.
- Removal, restore, never-present ids, reactivation, multiple writes, and catch-up: Task 6.4.
- `unreachable` and the four `unrecognized` shapes, re-read only when the signature changes: Task 6.2.
- Bounded failure, parking, and sidecar retry: Tasks 6.5 and 6.6.
- Idle tick: Task 6.1.
- Restart and catch-up in a real process: Task 7.4.
- Integration Requirements: the end-to-end test in Task 8.1 and `cf-contract.md` in Task 8.2.
- The Verification Walkthrough: Task 8.5.
- Requirement-to-test traceability: Task 8.7.

The reader, diff, migration, trigger, kind, and settings criteria are delegated to file 1, per the Context Summary.

### [PASS] Sequencing, test-with pattern, and commit cadence

- **Dependencies:** Section 6 is a linear chain (6.1 to 6.6) with no cycles, and each task builds on the previous one's tenant code.
- **Tests:** Section 6 tasks each carry their own tests. Pairs 7.1/7.2 and 7.3/7.4 explicitly defer the commit to the test task, so implementation and test land together.
- **Commits:** They are spread through Sections 6, 7, and 8, not batched at the end. Tasks 8.5 to 8.6 are reporting-only and correctly need none.
- **Size:** The largest tasks (6.3, 8.1) are at effort 4 and still bounded. No task needs splitting or merging.
- **Load tests:** The slice restates no NFR, so no load-test or CI-gating task is required. The idle-tick guarantee is covered functionally in Task 6.1.

### [CONCERN] Sidecar cleanup is specified inconsistently between Tasks 6.5 and 6.6

- **Step vs. test:** Task 6.6's step says a leftover sidecar is deleted "for a watch that then records successfully". The test it specifies stages a leftover sidecar for an already-recorded watch, and expects it to be "cleaned on the next dispatch and records nothing new". When nothing has changed, no recording happens, so the step describes no code path that deletes the sidecar.
- **Duplicated rule:** Task 6.5 already says "On success delete the sidecar after commit", so the success-path deletion is owned twice.
- **Fix:** State one rule in one place: the tenant deletes any sidecar for a watch whose dispatch ends in `ok`, whether or not a snapshot was recorded. Say which of 6.5 and 6.6 owns it.

### [CONCERN] How the tenant learns `failed` state, and where the existence check sits in the tick, is unspecified

- **Stale cache:** Task 6.1 refreshes the watch cache only when `cf_watch_revision` changes. Task 4.3 ties that counter to link changes, not state changes. A watch the tenant itself sets to `failed` therefore won't appear in the cache. Task 6.6 needs the set of `failed` watches each scan interval, but doesn't say whether that comes from tenant memory, the cache, or a query. A query would break the idle guarantee.
- **Tick ordering:** Task 6.1's early returns (no active watch, unchanged signature, not dirty) would skip a sidecar-removal check placed after them. Task 6.6 must say the check runs before the "signature unchanged" return.
- **Fix:** Say the tenant tracks `failed` watches in memory, populated from the dispatch that parks them and from first-sight cache loads. Also add a Task 6.6 test that deletes the sidecar while the file signature is unchanged. The retry test may already cover this, but the step should say so.

### [NOTE] Exception-handling wording in Task 6.5 should match project rules

"If that write also fails, log and continue" swallows an exception. The project rules require `logger.exception` at ERROR level, or a specific exception with a comment explaining why swallowing is correct. Name the exception type and require `logger.exception` so the implementer doesn't write a bare handler.

### [NOTE] Task-level deviations from the slice are surfaced to the PM

Two deviations from the slice design are intentional and routed to the PM through Task 8.6:
- **Version label:** The slice says the label is re-captured on every file-signature change. The tasks capture it once per recording read, which still honours "no subprocess in a tick".
- **New-watch detection:** The slice describes an in-memory cache of known watch ids. The tasks use the `cf_watch_revision` counter.

Both are reasonable and reported. If the PM prefers the slice's literal wording, the slice document should be amended.

### [NOTE] Task 7.1 depends on the tenant unnecessarily

Task 7.1 lists Task 6.6 as a dependency, but the listings only read store methods built in file 1. The dependency is harmless because it doesn't create a cycle. It does serialize work that could proceed in parallel after Section 5.

### Run Digest

- Response length: 5876 chars
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
- Duration: 45.0 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
