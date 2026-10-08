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
reviewedSha: bfdc52b46eb603ad59837542cc3201017c382925
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 45.0
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: task-sizing
    summary: "Task 5.5 bundles too much work"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:255-272"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Uvicorn backpressure check comes after uvicorn-specific infrastructure is built"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:295-304"
  - id: F003
    severity: concern
    category: coverage-gap
    summary: "Task 3.9 error-matrix tests omit `invalid_query`"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:52-58"
  - id: F004
    severity: concern
    category: clarity
    summary: "Task 4.6 depends on an undefined \"host harness\""
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:182"
  - id: F005
    severity: concern
    category: traceability
    summary: "Task 4.2 points to the wrong task for the apply-and-delete race"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:109"
  - id: F006
    severity: note
    category: nfr-coverage
    summary: "Load-test and CI-gating coverage for the latency bound is deferred to file 3"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:351"
  - id: F007
    severity: note
    category: task-sizing
    summary: "Redundant checkpoint and duplicated shutdown/thread-count assertions"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:66-76"
  - id: F008
    severity: note
    category: test-quality
    summary: "Task 5.9 is dense and timing-sensitive"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:328-343"
  - id: F009
    severity: pass
    category: traceability
    summary: "Success-criteria coverage for this file's scope"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:25-360"
  - id: F010
    severity: pass
    category: sequencing
    summary: "Sequencing and commit cadence"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:25-360"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 5.5 bundles too much work

Task 5.5 is rated Effort 4 but holds four separable deliverables:
- The SSE endpoint, with cursor rules, pre-stream checks, heartbeat, and per-heartbeat re-authentication.
- The app-level lifespan shutdown handler with its worker registry.
- `server_harness.py`, a reusable uvicorn-in-a-thread fixture.
- `server_main.py`, a subprocess entry point.

The harness and `server_main.py` are test infrastructure that later tasks (5.7, 5.9, 7.5) depend on. A junior AI would struggle to complete this in one pass.
- Split into 5.5a (SSE endpoint and registry/lifespan shutdown) and 5.5b (harness and `server_main.py`).
- Alternatively, move the harness pair ahead of the endpoint so the endpoint is written against it.

### [CONCERN] Uvicorn backpressure check comes after uvicorn-specific infrastructure is built

Task 5.7 checks that uvicorn's `send` waits for a non-reading client. Its own text says the remedy on failure is a different ASGI server (Hypercorn). By then 5.5 has built `server_harness.py`, which is uvicorn-specific, and 5.6 has built SSE tests on it. A failed check would force rework of those tasks.

The probe uses no Amoeba code (it needs only `probe_app.py` and a subprocess). It could run as the first task of Section 5, before 5.1. The slice design's step 4 allows this: it says only that the check must pass "before the rest of the stream work".
- Move 5.7 ahead of 5.1, or ahead of 5.5 at the latest.
- If it stays where it is, note that a failure invalidates 5.5 and 5.6.

### [CONCERN] Task 3.9 error-matrix tests omit `invalid_query`

The slice design makes an unknown or malformed query parameter a `400 invalid_query`, so that a misspelled `nod=` cannot silently return every node. The walkthrough demonstrates this. Task 3.8 routes through `query_from_params`, but 3.9's error list covers:
- unknown project
- bad project id
- unknown listing
- unknown verdict
- not comparable

It does not assert `invalid_query` at the project-listing endpoint: unknown parameter, bad choice value, bad flag value, or missing required value option.
- If file 1's tasks (3.7 or earlier) already test this at the supervisor-level endpoint, add one project-endpoint case here.
- Otherwise add the full case.

### [CONCERN] Task 4.6 depends on an undefined "host harness"

Task 4.6 says to "start the host harness" for the round-trip test, and Task 4.4 relies on applying submissions via "the 103 apply helper". Neither this file nor, as far as I can tell, its context summary says where the host harness lives or how to start the resident process in a test. Only `server_harness.py` is defined, in 5.5.
- Name the module or fixture, for example the 108 or 103 test host.
- Say what to do if it does not exist, rather than leaving the junior AI to guess.

### [CONCERN] Task 4.2 points to the wrong task for the apply-and-delete race

Task 4.2 says apply-and-delete "is covered by the status test (Task 4.5)". The apply-and-delete race is actually in Task 4.6 step (c). Task 4.5's tests do not include the race. This could mislead the implementer into thinking 4.5 owns it. Correct the reference to Task 4.6.

### [NOTE] Load-test and CI-gating coverage for the latency bound is deferred to file 3

The slice restates one NFR as a contract promise: a committed change is on the wire within `follow_interval_seconds` plus delivery time. Task 5.10 does the single-client check and refers to a load-tier task (8.1c) for concurrent load. Whether that task creates `tests/load/` coverage, and whether a separate CI-wiring task gates on it, cannot be verified from this file. Confirm in file 3 that:
- The load test lives under `tests/load/`.
- A CI task explicitly gates on it.

### [NOTE] Redundant checkpoint and duplicated shutdown/thread-count assertions

Task 3.10 is a verification-only task (Effort 1) that adds no deliverable, because 3.9 already requires suite, `ruff`, `pyright` clean and a commit. It is harmless as a group boundary but could be folded into 3.9. Separately, "thread count after server shutdown is zero" appears in both Task 5.6 and Task 5.9. Keep one owner for it.

### [NOTE] Task 5.9 is dense and timing-sensitive

Task 5.9 packs five separate scenarios, several using subprocess RSS readings and raw sockets. The flakiness safeguard (three consecutive runs) is on 5.10 but not on 5.9. Consider adding the same "no flakiness over three runs" criterion to 5.9, or splitting out the memory and backpressure cases.

### [PASS] Success-criteria coverage for this file's scope

The following criteria trace to tasks here:
- **Parity and snapshot:** the parity-with-`inspect` check and the `change_head` snapshot check map to 3.8 and 3.9.
- **Listing bounds:** `listing_too_large`, `store_busy`, and schema-mismatch isolation map to 3.9.
- **Locate, submission and status:** the `locate` races map to 4.1, 4.2 and 4.6. `422` parity with the CLI, retry idempotence, `408`/`413`, `no_store_for_project` quarantine, and the pending→applied round trip map to 4.3 through 4.6.
- **Feed:** `feed/page` equals `amoeba feed` (5.1, 5.2). SSE ordering, resume and heartbeat map to 5.5 and 5.6.
- **Stream limits:** stall close and resume, the stream cap with reads still serving, thread cleanup, backpressure, and the checkpoint `busy = 0` check map to 5.8 through 5.10.
- **Latency:** the single-client latency bound is covered by 5.10.

Criteria for auth, the refusal matrix, token-file failure, `kill -9` independence, the `serve` project-name check, and docs are outside this file. Their coverage is unverified here and belongs to file 3.

### [PASS] Sequencing and commit cadence

Dependencies run in a strict chain with no cycles. Implementation tasks pair with their tests (3.8/3.9, 4.1/4.2, 4.3/4.4, 5.1/5.2, 5.3/5.4, 5.5/5.6, 5.8/5.9) and commit together. Commits are distributed through every section rather than batched at the end. The stop-and-ask conditions (uvicorn backpressure, the `follow()` read-transaction check) are explicit and tell the implementer not to work around them.

### Run Digest

- Response length: 7502 chars
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
- Duration: 45.0 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
