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
reviewedSha: b5da659741742529433c377b91c455da5186e39a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
durationSeconds: 153.3
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Wrong forward references to the sidecar task (9.6 vs 9.9)"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:244"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 9.3's state function depends on layout that 9.9 creates"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:245"
  - id: F003
    severity: concern
    category: task-scoping
    summary: "Single-transaction recording is left as an open design choice"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:288"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "Tick-level `unreachable` transitions and logging are untested"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:265"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "Version-label fallback and reactivation behavior have no test"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:289"
  - id: F006
    severity: concern
    category: commit-checkpoints
    summary: "Two implementation tasks run before any test in Section 10, and one commit batches three"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:409"
  - id: F007
    severity: note
    category: nfr-coverage
    summary: "Load test and CI gating not required"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:314"
  - id: F008
    severity: note
    category: scope
    summary: "Scope and traceability look sound"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:114"
  - id: F009
    severity: pass
    category: coverage
    summary: "Follower, CLI, sources, settle rule, defer and skip, and ledger idempotence are covered and ordered"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:22"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Wrong forward references to the sidecar task (9.6 vs 9.9)

Task 9.3 (line 244) says the baseline bounded-failure key is "built in Task 9.6". Task 9.5 (line 286) says the parked-sidecar check is "(Task 9.6)". Task 9.6 is the detection test task. The sidecar layout and `AttemptsSidecar` logic are built in Task 9.9.

A junior following these references would look in the wrong place. They could also try to implement the parked-sidecar skip in 9.5 before any sidecar module exists. Fix the references to 9.9. State in 9.5 that the parked check is a no-op hook until 9.9, or move the sidecar layout module ahead of 9.3.

### [CONCERN] Task 9.3's state function depends on layout that 9.9 creates

Task 9.3 asks for "a pure function that computes the state from the filesystem and the sidecar directory", and for the `failed` state in particular. The sidecar directory layout and reader are only defined in Task 9.9 (lines 371 and 374). The state derivation is also deferred to "decide in Task 10.1".

So 9.3 cannot be finished or tested as written. 9.4 does not test it. Task 10.1 then says "use the pure functions from Tasks 9.3 and 9.9", so the function may be split across two tasks. Pick one owner for the state derivation, preferably 9.9 or 10.1. Remove it from 9.3 or limit 9.3 to `unreachable` and `baseline_pending`.

### [CONCERN] Single-transaction recording is left as an open design choice

Task 9.5 requires `record_verdict` and `record_detection(ingested)` in one transaction. It tells the junior to add a store method such as `record_detected_verdict` if the existing API cannot share a transaction. Nothing in file 1 (Sections 1–6) builds that method, and no store-side test task covers it.

This is the central atomicity property of the tenant. Settle it before 9.5, in a small store task with a test, such as a crash between the two calls leaving neither row. Otherwise a junior will make this decision unreviewed inside a 4-effort tenant task.

### [CONCERN] Tick-level `unreachable` transitions and logging are untested

The slice design says "A watched directory that is removed shows `unreachable`; the process keeps running and resumes when it returns." It also requires one ERROR when the directory goes bad and one INFO on recovery. Task 8.4 tests the source raising `ReviewDirectoryUnavailableError`. Task 9.4 tests only a directory missing at registration (line 265). No test covers an already-baselined watch whose directory is removed and then restored. None asserts that the ERROR and INFO each fire once.

Add that case to 9.4 or 9.6.

### [CONCERN] Version-label fallback and reactivation behavior have no test

Task 9.5 passes the start-up `sq` label as the fallback `upstream_version`, but 9.6 never asserts the recorded verdict carries it. The slice design also says that after reactivation, "files that arrived while inactive are detected". Task 9.4 checks only that reactivation does not re-baseline. It does not check that files added during the inactive period are ingested. Add both assertions.

### [CONCERN] Two implementation tasks run before any test in Section 10, and one commit batches three

Task 10.1 (listings) and Task 10.2 (wiring) are both implementation tasks, and the first test is 10.3. Their success criteria say "Committed with Task 10.3", so three tasks land in one commit. This breaks the test-with pattern used everywhere else in the file. The no-subprocess-per-tick test sits inside 10.2's steps rather than in the test task. Add a test and commit after 10.1, for example by moving the listing tests into a 10.2 and renumbering. Alternatively, commit 10.1 on its own.

### [NOTE] Load test and CI gating not required

The slice design states no NFR. It says "The parent architecture sets no numeric targets, so these are this slice's choices". The scan, follow and timeout values are tuning defaults, not restated NFRs, so a `tests/load/` task and CI gating task are not required.

### [NOTE] Scope and traceability look sound

Every task traces to the slice design.
- Task 8.1 edits 105's code, but that is the pass-through 105 deferred to this slice (design D7).
- The shared version-label refactor in 9.1 supports the `sq --version` requirement.
- The sidecar layout module in 9.9 and the `failed` rows in 10.1 support the bounded-failure rule.

The 105 gate in 8.1 fails explicitly instead of stubbing the parser. Task 6.1 does provide the open-entry read that 9.7 uses, which I checked in file 1.

### [PASS] Follower, CLI, sources, settle rule, defer and skip, and ledger idempotence are covered and ordered

These design criteria each map to a task and a paired test:
- Follower resume with no gap and no repeat, and the killed follower: 7.1–7.4.
- Settle rule and file races: 8.3–8.4.
- Baseline and the failure table: 9.3–9.4.
- Ingest, attribution, series separation, hand edits, unparseable files, restart idempotence, and the hand-ingest `recorded_since` path: 9.5–9.6.
- SQ_RUN defer, `runner_issued` skip, and `CF_WRITE` not deferring: 9.7–9.8.
- Bounded failure at and below the limit, and sidecar removal: 9.9–9.10.
- Listings and process wiring: 10.1–10.3.

There are no circular dependencies. Task sizes (effort 1–4) are suitable for a junior AI, and commits are spread through the file.

### Run Digest

- Response length: 6947 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 153.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
