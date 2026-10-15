---
docType: review
layer: project
reviewType: slice
slice: network-api
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/109-slice.network-api.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 78cb8c202e4eeae6dbc27b2fc3554d6ec42c1352
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 180419
cachedTokens: 91933
cacheWriteTokens: 88480
completionTokens: 2964
durationSeconds: 26.9
costUsd: 0.393432
costBasis: provider
runId: run-20261015-slices-plan-fa1ba72e
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Network constraints from the architecture are met"
    location: "project-documents/user/slices/109-slice.network-api.md#Overview"
  - id: F002
    severity: concern
    category: scope
    summary: "Proportionality: the migration refactor is bundled into this slice"
    location: "project-documents/user/slices/109-slice.network-api.md#Migration Plan"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Failure modes for the stream and submission paths are incomplete"
    location: "project-documents/user/slices/109-slice.network-api.md#Data Flow"
  - id: F004
    severity: concern
    category: security
    summary: "Auth and hardening gaps for the first network exposure"
    location: "project-documents/user/slices/109-slice.network-api.md#D2"
  - id: F005
    severity: concern
    category: nfr
    summary: "Missing NFR targets for the stream and read paths"
    location: "project-documents/user/slices/109-slice.network-api.md#Technical Requirements"
  - id: F006
    severity: note
    category: dependencies
    summary: "Dependency direction and ordering gate are handled well"
    location: "project-documents/user/slices/109-slice.network-api.md#Prerequisites"
  - id: F007
    severity: note
    category: integration
    summary: "Store amendment is small and additive"
    location: "project-documents/user/slices/109-slice.network-api.md#D4"
  - id: F008
    severity: note
    category: scope
    summary: "Documentation deliverables are numerous"
    location: "project-documents/user/slices/109-slice.network-api.md#Technical Requirements"
---

# Review: slice — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Network constraints from the architecture are met

`amoeba serve` is a separate process, has no write path other than `inbox.submit()`, and reads through read-only store handles. Streaming uses 106's `follow()` with `seq` as the resume cursor. The default bind is loopback, and a non-local bind needs a token plus TLS (D3). All of this matches the "Network surface — required, as its own process" section and the sole-writer model. The slice does not touch the resident process, takes no instance lock, and keeps the layering rules (`serve` imports nothing from `process` or `cli`) as AST tests.

### [CONCERN] Proportionality: the migration refactor is bundled into this slice

The slice plan assigns 109 a network transport at relative effort 3. This design also moves the whole `inspect` registry and six listing modules into a new `amoeba.inspection` package. It replaces `argparse.Namespace` with `ListingRequest`, adds option `name` fields with derived flags, and adds a `compact` flag. It also moves `discover_project_ids` to `store/discovery.py` and `change_line` to `feed/wire.py`. This is a cross-cutting refactor of 102, 104, 105, 107 and 108 code, and its byte-identical-output proof is a deliverable in its own right. It also makes 105, 107 and 108 hard prerequisites, and the doc itself says neither 107 nor 108 is merged.

The goal of "same answers as inspect" can be met more cheaply:
- Keep the listings in `amoeba.cli` and have `serve` call them. This breaks the layering rule that `serve` may not import `cli`, which is why the move looks attractive.
- Split the migration into its own preparatory slice, or at least its own gated commit range, so 109's risk and effort are not hidden in it. The Development Approach already commits the migration separately (step 2), so extraction is cheap.

I'd treat the extraction as the lighter option. The doc should either justify keeping it here or defer it.

### [CONCERN] Failure modes for the stream and submission paths are incomplete

The doc covers client disconnect, slot leaks, preflight failures and a mid-stream `event: error`. Several failure modes on the new I/O paths are not handled or stated:
- **Hand-off queue blocks the follow thread.** The thread blocks until the loop takes each change. If the loop is cancelled or the send hangs on a stalled TCP peer, the thread depends on the stop event to exit. The doc claims exit "within one follow interval", but a thread blocked in `from_thread.run` is not inside `follow()` and so does not check `stop`. The doc should state how the hand-off wakes up on cancellation.
- **Stalled peer without a failed send.** Heartbeats only detect a disconnect when a send fails. A client that stops reading while the TCP connection stays open holds a slot until the OS send buffer fills and the write blocks. The design sets no send timeout, so the slot-release bound of "one heartbeat plus one follow interval" holds only for clean closes.
- **Thread-pool saturation on reads.** The default anyio limiter (40 tokens) is shared by reads, submissions and outcome lookups. The doc covers streams starving reads, but not many concurrent slow reads under `store_busy`. There is no timeout or concurrency bound for them.
- **Request-size enforcement for POST.** A 413 is listed, but the doc does not say whether `max_request_bytes` is enforced from `Content-Length` or while the body streams. A chunked body without `Content-Length` could be buffered before the check.
- **Partial inbox write.** `SubmissionWriteError → 503` is handled. Whether a retried POST with the same id is safe after a 503 follows from 103's first-wins rule, but the doc should say so, because that is the case the required id exists for.

### [CONCERN] Auth and hardening gaps for the first network exposure

The architecture says any non-local bind requires authentication, and D2 and D3 meet that. A few points around the shared token are left implicit:
- With no token on a loopback bind, any local process, including a browser page making requests to `127.0.0.1`, can submit `resolution` and `intent`. The doc justifies this by the file-permission trust boundary. Browser-origin requests to loopback do not cross that boundary, and CORS is excluded. Say whether the server checks `Origin` or `Host`, or accept the risk explicitly.
- There is no failed-auth throttling. Rate limiting is excluded, but the 32-character minimum does not by itself cover token leakage through logs. State that the access log omits the `Authorization` header (the doc says uvicorn does this, but the claim is made without a test).
- Token rotation requires a restart, which is acceptable but should be one line in the contract.

### [CONCERN] Missing NFR targets for the stream and read paths

The architecture's constraints include "no slow-client policy inside recovery-critical code" and an ordered, no-gap feed. The slice sets concrete numbers for streams (32 followers, 2,000-change burst, 15 s heartbeat) but leaves the read latency target as "about twice the observed p95, measure first". Nothing states a target for end-to-end change-to-client delivery latency on a live stream, which is what the notification bridge cares about. Either state a target derived from `follow_interval_seconds`, or say explicitly that none is promised.

### [NOTE] Dependency direction and ordering gate are handled well

The first task checks that 107 and 108 are merged and stops for the PM if they are not. The dependency list matches the slice plan's `[101…108]`. The doc records that 105, 107 and 108 are prerequisites for ordering only, not function. This is consistent with the slice plan's own note.

### [NOTE] Store amendment is small and additive

`read_transaction()` and `change_head()` close the "state, then follow" deferral that 106 handed to this slice. They are read-only and add no migration. The doc also commits to updating `store-contract.md` and `feed-contract.md`. This fits the architecture's rule that the network API changes no contract in 101–108.

### [NOTE] Documentation deliverables are numerous

`network-contract.md` is new, and `feed-contract.md`, `inbox-contract.md`, `process-contract.md` and `store-contract.md` each get a delta. The two new dependencies come with dated version notes. This is acceptable, but if the migration is split out (see the proportionality concern), the contract deltas for the moved listings go with it.

### Run Digest

- Response length: 7428 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 180419 / 91933 / 88480 / 2964 / not computed
- Duration: 26.9 s
- Cost: $0.39 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
