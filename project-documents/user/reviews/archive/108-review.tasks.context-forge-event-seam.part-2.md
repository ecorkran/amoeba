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
reviewedSha: fc660a6040b82597a1cda97452f62011ffa226c7
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 39.9
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "File-level states can overwrite `failed` and bypass parking"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:56"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Parking skip logic is split across 6.5 and 6.6, leaving 6.5 incomplete"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:121"
  - id: F003
    severity: concern
    category: testing
    summary: "Negative assertions are required but \"no fixed sleeps\" gives no method for them"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:218"
  - id: F004
    severity: concern
    category: task-scope
    summary: "Task 6.3 bundles too much"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:70"
  - id: F005
    severity: note
    category: scope
    summary: "6.5 and 6.6 add behaviour beyond the LLD, and both are reported to the PM"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:122"
  - id: F006
    severity: note
    category: task-scope
    summary: "Non-code tasks 8.5, 8.6 and 8.7 could be fewer"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:327"
  - id: F007
    severity: note
    category: nfr
    summary: "No performance NFR, so no `tests/load/` task is needed"
    location: "unverified"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage and sequencing"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:342"
---

# Review: tasks — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] File-level states can overwrite `failed` and bypass parking

Task 6.2 sets every active watch to `unreachable` or `unrecognized` through `set_cf_watch_state`. It makes no exception for `failed` watches. Task 6.6 finds parked watches by cache state `failed` (line 141), and the parked sidecar is meant to persist. A parked watch that passes through `unreachable` (file removed, then restored) loses its `failed` marker. After recovery it is no longer `failed`, so the 6.6 existence check never sees it. Dispatch would then re-attempt the recording unless it also tests the sidecar. Line 141 says a watch is skipped "while its sidecar exists", but it keys retry detection on state. Decide the intended behaviour: either file-level states leave `failed` watches alone, or dispatch skips on sidecar presence regardless of state. Add a test for the `failed` → `unreachable` → restored sequence in `test_cf_watch_retry.py` or `test_cf_watch_file_states.py`.

### [CONCERN] Parking skip logic is split across 6.5 and 6.6, leaving 6.5 incomplete

Task 6.5 sets a watch to `failed` at the attempt limit. The rule that dispatch skips a parked watch is added only in Task 6.6 (line 141). Between the two commits, any later dirty scan or signature change re-attempts a `failed` watch. Each retry increments the sidecar past `cf_max_attempts`, which contradicts the 6.5 objective. Move the "skip while parked" check into 6.5 and keep only the sidecar-removal retry in 6.6. Alternatively, state that 6.5's bounded failure is incomplete until 6.6.

### [CONCERN] Negative assertions are required but "no fixed sleeps" gives no method for them

Task 7.4 ("restart, assert nothing new is recorded") and Task 8.1 ("restart with no CF change → nothing new"; no feed line for `missing` or for a restored file) assert that something did not happen. A condition-with-deadline wait cannot prove that. The tasks forbid fixed sleeps but give no positive signal to wait on. A junior would either sleep or write a test that passes before the tenant has scanned. Specify the synchronization point. For example, wait until `inspect cf-watches` shows the watch `ok` after the restart, or until a second scan has happened. Then assert the snapshot count or the follower output. A short bounded settle, with the reason stated, would also be acceptable.

### [CONCERN] Task 6.3 bundles too much

Task 6.3 covers the diff-and-record loop, the version-label capture, the tightening of the 3.6 writer test, and two new test files. That is effort 4 for one session. The label path (`capture_label` once per recording read, `unavailable` handling, `test_cf_watch_label.py`) is separable from snapshot recording. Splitting it into its own task would keep each unit about the size of 6.2 and 6.4.

### [NOTE] 6.5 and 6.6 add behaviour beyond the LLD, and both are reported to the PM

Two things go beyond the LLD text. Task 6.5 deletes a stale sidecar in the empty-diff branch. Task 6.6 adds one existence check per `failed` watch per scan, an exception to the LLD's "one `stat`" idle guarantee. Both are defensible and are surfaced in 8.6 or documented in 8.3. The label-capture-per-recording-read deviation from the LLD's "per detected change" (line 78) is surfaced the same way. I traced all three to a reasonable intent, so none is scope creep.

### [NOTE] Non-code tasks 8.5, 8.6 and 8.7 could be fewer

Task 8.6 is effort 1 and is just a final-message list. It could be folded into 8.5 or 8.7. This is optional.

### [NOTE] No performance NFR, so no `tests/load/` task is needed

The slice has no numeric throughput or latency NFR. The idle-tick guarantee is a structural property and is verified by the spy tests in `test_cf_watch_idle.py` and `test_cf_watch_label.py`. No load test or CI gating task is required.

### [PASS] Success-criteria coverage and sequencing

Every Functional and Technical Requirement in the slice maps to a task and a named test in Task 8.7. Dependencies are linear with no cycles. Listings (7.1–7.2) precede wiring (7.3–7.4). The end-to-end test, docs, and boundary pins follow. Commits are distributed per task or per implementation/test pair, and none are batched at the end.

### Run Digest

- Response length: 5563 chars
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
- Duration: 39.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
