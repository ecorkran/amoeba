---
docType: review
layer: project
reviewType: tasks
slice: network-api
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/109-tasks.network-api-2.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 43bc228b48f1f049e126d7936d3a492272bbe50f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 44.8
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Stream implementation tasks go untested and uncommitted across four tasks"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:205-276"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Task 5.6 is oversized"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:259-276"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Shutdown tests depend on wiring from a later task"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:235"
  - id: F004
    severity: concern
    category: interface-gap
    summary: "Source of `feed_settings` for the stream and page endpoints is unspecified"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:181-212"
  - id: F005
    severity: concern
    category: nfr-coverage
    summary: "Latency requirement has no load-test task or CI gate"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:280-292"
  - id: F006
    severity: concern
    category: task-sizing
    summary: "Task 4.5 bundles implementation, a large race matrix and a round trip without a separate commit"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:153-168"
  - id: F007
    severity: note
    category: coverage
    summary: "Stall-then-resume is not asserted"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:263-272"
  - id: F008
    severity: note
    category: coverage
    summary: "POST invalid project id is not tested"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:114-149"
  - id: F009
    severity: pass
    category: coverage
    summary: "Success-criteria coverage within this file's scope"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:22-292"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Stream implementation tasks go untested and uncommitted across four tasks

Tasks 5.3 (stream worker) and 5.4 (limiter and SSE endpoint) have no tests of their own. The success criterion of each is "Commit with Task 5.4" or "Commit with Task 5.5". Task 5.5 commits "with Task 5.6 only if it passes", and Task 5.6 closes with a single commit covering 5.3–5.5. That leaves roughly 16 effort points (4+4+3+5) of the riskiest code in the slice (threads, backpressure, stall handling) with no commit and no test of the endpoint's own behaviour until Task 5.6. This breaks the test-with pattern and the commit-checkpoint rule. Suggested fix:
- Add a minimal test and commit directly after 5.3: stop, close and thread-count behaviour using a fake `follow`.
- Add a basic SSE smoke test and commit after 5.4.
- Keep 5.5 as the gate.
- Commit 5.6 separately.

### [CONCERN] Task 5.6 is oversized

Task 5.6 has effort 5 and seven independent test groups: ordering and transcript parity, resume, heartbeat, cap, thread counts after three kinds of end, pre-stream errors, and backpressure. It also needs a real-server fixture. Split it into two or three tasks, each with a commit:
- Ordering and resume.
- Heartbeat, cap and pre-stream errors.
- Thread-count and backpressure.

### [CONCERN] Shutdown tests depend on wiring from a later task

Task 5.4 says shutdown handling is wired to uvicorn in Task 7.3. Task 5.6 requires a thread-count assertion "after server shutdown". It also says to use a real uvicorn server, with no launcher yet. Task 5.5 hedges with "use the Task 7 launcher if it exists; otherwise `uvicorn.Server` directly". Task 5.6 does not say how to trigger shutdown (for example `server.should_exit`) or whether the hook that sets every stream's stop event is exercised at all. The subprocess `SIGTERM` test is in Task 7.3 (file 3). State in 5.6 how shutdown is triggered in-process, or move that assertion to Task 7.3 and say so explicitly.

### [CONCERN] Source of `feed_settings` for the stream and page endpoints is unspecified

Task 5.3 passes `settings=feed_settings` to `follow()`. Task 5.1 uses `FeedSettings.feed_batch_size`. Task 5.7 needs a small `follow_interval_seconds` injected. `ServeSettings` has no feed-settings field, and `build_app(supervisor_dir, settings, authenticator)` takes no `FeedSettings`. Nothing in this file says where it comes from. A junior will either hard-code a default, which CLAUDE.md forbids, or invent a seam. Add a step in 5.1 or 5.3 that fixes the injection:
- Pass `FeedSettings` to `build_app` explicitly, or
- Hold it on an app-state object.

Say that tests override it through that same path.

### [CONCERN] Latency requirement has no load-test task or CI gate

The slice restates a latency bound under Value and Functional Requirements: a change reaches the wire within `follow_interval_seconds` plus delivery time. It also states `max_feed_streams` and `max_connections` capacity bounds. Task 5.7 covers latency as a unit-style timing test in `tests/serve/`, with a deliberately loose margin and no exact timings. A grep of tasks files 2 and 3 finds no `tests/load/` task and no CI wiring task. File 3 should be checked for one before this is treated as final. If none exists, add a `tests/load/` task for the latency bound and stream-cap behaviour, plus a CI gating task. Alternatively, the PM can record that the slice's own wording ("a timing test with a generous margin") is the intended coverage.

### [CONCERN] Task 4.5 bundles implementation, a large race matrix and a round trip without a separate commit

Task 4.5 adds `SubmissionState`, a two-pass status algorithm, five state tests, three race tests and a host-harness round trip, all at effort 4 and in one commit. The round trip also assumes a "host harness" that this file never establishes; Task 4.4 says only "no host in the test". Consider splitting into:
- The endpoint plus basic state tests.
- Race and round-trip tests.

Confirm the harness exists, or name where it comes from.

### [NOTE] Stall-then-resume is not asserted

The slice criterion "reconnecting with `Last-Event-ID` resumes with no gap" after a stall closure is covered only for voluntary disconnect in Task 5.6. Task 5.5 checks the stall close and slot release but not the resumed transcript. Add a one-line assertion to 5.5 or 5.6.

### [NOTE] POST invalid project id is not tested

Task 4.3 calls `validate_project_id`, but Task 4.4 does not assert `400 invalid_project_id` for a bad id on POST or on the status endpoint. Add it to the error-case list.

### [PASS] Success-criteria coverage within this file's scope

Each of these criteria maps to a task:
- Registry parity (3.9).
- Snapshot consistency (3.9).
- `max_listing_rows`, `store_busy` and `store_unavailable` (3.9).
- Writer guard for `amoeba.serve` (3.9).
- `locate` and its race (4.1, 4.2).
- Submission 202, 422, retry and body bounds (4.3, 4.4).
- Status states and races (4.5).
- `feed/page` parity (5.1, 5.2).
- SSE ordering, resume, heartbeat, cap and thread cleanup (5.6).
- Drain verification with a stop-and-ask gate (5.5).
- Checkpoint and latency (5.7).

I found no scope creep. Authentication, startup refusal, kill tests and docs are correctly deferred to file 3. Dependency order is acyclic, and the 3.8/3.9, 4.1/4.2 and 4.3/4.4 pairs follow the test-with pattern with commits.

### Run Digest

- Response length: 6589 chars
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
- Duration: 44.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
