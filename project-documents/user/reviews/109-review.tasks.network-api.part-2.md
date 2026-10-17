---
docType: review
layer: project
reviewType: tasks
slice: network-api
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/109-tasks.network-api-2.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261017
dateUpdated: 20261017
reviewedSha: e5b1908e439d674939e91e52b6f4e261c36dd51a
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 100963
cachedTokens: 10984
cacheWriteTokens: 89975
completionTokens: 7488
durationSeconds: 61.5
costUsd: 0.436553
costBasis: provider
runId: run-20261017-p5-dcc30257
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 5.5's `amoeba.inbox` import rule conflicts with Task 6.1"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:256"
  - id: F002
    severity: concern
    category: test-quality
    summary: "Task 6.2's 413 test may not observe early termination"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:306"
  - id: F003
    severity: concern
    category: clarity
    summary: "Task 4.2 miscounts the `ServeSettings` fields"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:51"
  - id: F004
    severity: note
    category: slice-conformance
    summary: "Task 4.3 rule 3 refuses a half TLS pair on loopback, against D3's table"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:76"
  - id: F005
    severity: note
    category: coverage
    summary: "\"401 on every endpoint\" is only exercised on the read route"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:234"
  - id: F006
    severity: pass
    category: structure
    summary: "Sequencing, test-with pattern, and commit cadence"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md"
  - id: F007
    severity: pass
    category: scope
    summary: "Traceability and proportionality"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 5.5's `amoeba.inbox` import rule conflicts with Task 6.1

Task 5.5 asserts that every name `serve/` imports from `amoeba.inbox` is `submit` or an exception type in `CODE_BY_EXCEPTION`. Task 4.5 says `InvalidSubmissionError` is deliberately not in that table, and Task 6.1 (line 283) adds a dedicated handler for it. So 6.1 must import `InvalidSubmissionError`, and probably `SubmissionKind`, from `amoeba.inbox`. That breaks the rule 5.5 has already committed. Until then the check passes vacuously, since no module imports anything from `inbox` yet.

The slice only requires that `serve` call no inbox function other than `submit` (LLD line 116). An import allow-list is stricter than that. Either name the allowed set explicitly (`submit`, `SubmissionKind`, `InvalidSubmissionError`, and the table's exceptions), or restrict the rule to call sites. Also say that the `submit`-only check bites from 6.1 onward, and have 6.1 re-run it.

### [CONCERN] Task 6.2's 413 test may not observe early termination

The slice criterion is that the server "reads no more than `max_request_bytes + 1` bytes" of an oversized body. Task 6.2 tests this through Starlette's `TestClient`, counting the chunks a generator body yielded. I haven't confirmed this, but I believe `TestClient` consumes the whole request body before dispatching to the ASGI app. If so, the generator is always fully drained and the test can't show the handler stopped reading. Counting chunks is also not counting bytes. A single chunk can overshoot the cap, and Task 6.1 only says to stop "once more than `max_request_bytes` bytes have arrived".

Specify a way to observe this. One option is to call `build_app(...)` directly with a hand-written ASGI `receive` that counts the bytes it hands out and asserts it was not called again after the crossing chunk. Another is a real-uvicorn test, which belongs in file 3. State the exact assertion, for example "bytes delivered ≤ cap + one chunk". If the criterion is meant literally as +1 byte, Task 6.1 must say how the crossing chunk is handled.

### [CONCERN] Task 4.2 miscounts the `ServeSettings` fields

The step lists "the four interval/limit fields, `max_request_bytes`, `shutdown_grace_seconds`". The LLD (Patterns, Settings) has only three before those two: `heartbeat_interval_seconds`, `send_timeout_seconds` and `max_streams`. A junior AI told to add "four" may invent a fourth field, which is scope creep in the one place the project says every default must live. Name each field and default explicitly, or write "the three fields". The `__post_init__` list also leaves `shutdown_grace_seconds` unaddressed (validated or not). Say which.

### [NOTE] Task 4.3 rule 3 refuses a half TLS pair on loopback, against D3's table

D3's table says loopback with any token and any TLS state "serves". Rule 3 refuses exactly one TLS file on every bind, and rule 4 refuses unusable files on every bind. The task labels rule 3 as a task-level choice, which is the right way to do it. Rule 4 is consistent with the LLD prose, but rule 3 is not in the LLD at all. Task 9.4 should carry a contract-doc delta for it, alongside the traversal correction already noted at line 308. The tests in 4.4 already cover the overlap cases.

### [NOTE] "401 on every endpoint" is only exercised on the read route

The slice requires 401 without or with a wrong token "on every endpoint, loopback included". Task 5.4 tests it, and the other guards, on the read endpoint only. The middleware is app-wide, so the behaviour holds. The submission routes arrive in 6.1 and the feed in 7.x, and nothing pins them. A parametrized line over the submission and feed paths would close this at almost no cost. A request that fails auth never reaches routing, so it could be added in 5.4 against paths that don't exist yet.

### [PASS] Sequencing, test-with pattern, and commit cadence

Dependencies run strictly forward (4.1→…→6.2) with no cycles. 4.3, 4.5, 5.1, 5.3 and 6.1 are each paired with the test task that follows them and commit together. Commits land at 4.1, 4.2, 4.4, 4.6, 5.2, 5.4, 5.5 and 6.2, so none are batched at the end. Task 5.1 creates the shared fixtures in `conftest.py` before 5.2 needs them.

### [PASS] Traceability and proportionality

Each task traces to a slice criterion or a Technical Requirement:
- **Bind policy and refusals:** Tasks 4.3–4.4, covering D3.
- **Single-definition error test:** Tasks 4.5–4.6.
- **Reads, parity and traversal:** Tasks 5.1–5.2.
- **Origin, Host, token and content-type guards, plus token secrecy:** Tasks 5.3–5.4.
- **Layering rules:** Task 5.5.
- **Submissions, idempotent retry and 413:** Tasks 6.1–6.2.

I found no unjustified tasks. Task sizes (effort 1–3) fit a junior implementer. Splitting into three task files matches the slice's breadth. This file has no NFR load test, because the load-tier test and its CI gating belong to Sections 7–9 in file 3. I did not check that file.

### Run Digest

- Response length: 5867 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 100963 / 10984 / 89975 / 7488 / not computed
- Duration: 61.5 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
