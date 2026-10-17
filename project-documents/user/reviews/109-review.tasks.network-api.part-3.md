---
docType: review
layer: project
reviewType: tasks
slice: network-api
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/tasks/109-tasks.network-api-3.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261017
dateUpdated: 20261017
reviewedSha: e5b1908e439d674939e91e52b6f4e261c36dd51a
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 219589
cachedTokens: 179436
cacheWriteTokens: 40147
completionTokens: 3296
durationSeconds: 28.3
costUsd: 0.21217
costBasis: provider
runId: run-20261017-p5-dcc30257
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Stream, slot and shutdown criteria are fully traced"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:41-150"
  - id: F002
    severity: pass
    category: load-testing
    summary: "Load tier and CI gating are explicit"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:219-237"
  - id: F003
    severity: pass
    category: coverage
    summary: "CLI, smoke, docs and validation match the slice"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:153-277"
  - id: F004
    severity: note
    category: test-design
    summary: "Pin behavior 2 asserts a library limitation and may be brittle"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:142"
  - id: F005
    severity: note
    category: proportionality
    summary: "The memory-growth pin duplicates the stalled-reader test"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:139-141"
  - id: F006
    severity: note
    category: sequencing
    summary: "Task 9.2 depends on 9.1 only for ordering"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:223"
  - id: F007
    severity: note
    category: sequencing
    summary: "Task 8.1 begins with a PM-blocking item"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:162"
---

# Review: tasks — slice 109

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Stream, slot and shutdown criteria are fully traced

Tasks 7.2–7.6 cover each stream criterion in the slice's Functional Requirements:
- **Delivery:** every change once and in order, with resume by `Last-Event-ID` or `?after=`, and header precedence.
- **Cursor and routing errors:** `invalid_cursor`, 404 and 503 before the 200, and traversal ids.
- **Mid-stream failure:** the store deleted mid-stream produces an `event: error` frame.
- **Keepalive and slots:** the keepalive, the `max_streams` 503 while reads still work, and slot release after an abrupt close.
- **Stalled reader:** slot release and thread exit when the follow thread is blocked in the hand-off.
- **Shutdown:** an open stream is cleaned up when the server stops.

### [PASS] Load tier and CI gating are explicit

Task 9.2 covers the three Technical Requirements load assertions: 32 followers each receiving a 600-change burst, p95 ≤ 1 s, and no starvation. It also states the CI gating. `.github/workflows/ci.yml:54` already runs `uv run pytest tests/load`, and `tests/load/conftest.py`, `tests/load/load_harness.py` and `tests/feed_harness.py` all exist. The `tests/cli_harness.py` that Task 8.2 uses exists too. The task correctly adds no workflow change and says to stop if the step is missing.

### [PASS] CLI, smoke, docs and validation match the slice

- **Task 8.2** covers the exit-13 matrix, HTTPS with 401 and 200, the port in use exiting 1, and SIGTERM within the grace period. It also checks that no stdout or stderr carries the token, and that `inspect` never loads uvicorn.
- **Task 9.1** covers the integration smoke test. It also covers "resident stopped, server keeps serving", which the Functional Requirements ask for.
- **Task 9.3** covers the contract doc, the four deltas and the CHANGELOG.
- **Task 9.4** runs the walkthrough, the suite, ruff and pyright, and the final status update.

### [NOTE] Pin behavior 2 asserts a library limitation and may be brittle

Task 7.6 asserts that a new stream request 0.5 s after a clean close still gets 503. That documents the ASGI "disconnect is noticed on send" behavior the design depends on, and the slice does say a test pins each behavior. A future uvicorn that detects disconnects earlier would fail this test even though nothing is wrong. Add a comment in the test saying that a failure means the library got better and the heartbeat rationale should be revisited, not that the server regressed.

### [NOTE] The memory-growth pin duplicates the stalled-reader test

"Pin behavior 1" asserts that the follow thread is blocked in the hand-off and has sent a bounded number of changes. The stalled-reader bullet above already sets up the same scenario and checks the thread is blocked. Fold the bounded-send assertion into that test, so there is one scenario instead of two.

### [NOTE] Task 9.2 depends on 9.1 only for ordering

The load test needs `running_server` (Task 7.1) and the feed route, not the smoke test. The chain is harmless, but 9.2 does not truly depend on 9.1. Task 8.2 also relies on the Task 4.4 cert fixture from file 1 without listing it, which is fine because it is reached transitively.

### [NOTE] Task 8.1 begins with a PM-blocking item

The first step stops and waits for the PM's answer on where `ServeRefusedError` is mapped. It is flagged clearly and was raised in file 1, so it is not a defect. Getting the answer before Section 7 starts would avoid a stall at this point.

### Run Digest

- Response length: 4437 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 219589 / 179436 / 40147 / 3296 / not computed
- Duration: 28.3 s
- Cost: $0.21 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
