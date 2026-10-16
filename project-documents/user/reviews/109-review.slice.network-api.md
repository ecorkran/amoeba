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
reviewedSha: 0c1033a3ff81d33dec24ab562b2a26edfb338319
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 176131
cachedTokens: 84476
cacheWriteTokens: 91649
completionTokens: 4545
durationSeconds: 39.6
costUsd: 0.421172
costBasis: provider
runId: run-20261015-slices-plan-fa1ba72e
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: pass
    category: architectural-alignment
    summary: "Process boundary, writer model and read/write paths match the architecture"
    location: "project-documents/user/slices/109-slice.network-api.md#Technical Scope"
  - id: F002
    severity: pass
    category: dependency-direction
    summary: "Layering and dependency directions are enforced structurally"
    location: "project-documents/user/slices/109-slice.network-api.md#Architecture"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for every new I/O path"
    location: "project-documents/user/slices/109-slice.network-api.md#Data Flow"
  - id: F004
    severity: pass
    category: nfr
    summary: "NFR restatement is appropriate"
    location: "project-documents/user/slices/109-slice.network-api.md#Technical Requirements"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Design is heavier than an effort-3, medium-risk slice needs; several mechanisms can be cut or deferred"
    location: "project-documents/user/slices/109-slice.network-api.md:258"
    resolution: accepted
    resolvedBy: "Cut: GET /v1/listings catalog, the body-read timeout and 408 path, max_connections/limit_concurrency, and the 200 ms read-latency target (starvation check kept). Kept send_timeout_seconds and shutdown_grace_seconds: no usable library default exists (a stalled reader would hold its slot forever; uvicorn's graceful shutdown waits indefinitely and SSE streams never end). Origin/Host/415 kept, as the reviewer accepted"
  - id: F006
    severity: note
    category: hidden-dependency
    summary: "Migration table names modules from designs that are not yet merged"
    location: "project-documents/user/slices/109-slice.network-api.md:62"
    resolution: no_change_needed
    resolvedBy: "Development Approach step 1 already gates on 107 and 108 being merged and revalidates the Migration Plan table"
  - id: F007
    severity: note
    category: architectural-alignment
    summary: "Design is stricter than the architecture on the non-local bind"
    location: "project-documents/user/slices/109-slice.network-api.md:206"
    resolution: no_change_needed
    resolvedBy: "Stricter bind rules (TLS, token length, Origin, Host) are justified in D2/D3; no action requested"
---

# Review: slice — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Process boundary, writer model and read/write paths match the architecture

`amoeba serve` is a separate foreground process with no instance lock, PID file or tenant coupling (D7). That is the "its own process, not a tenant" decision ratified in the architecture's Network surface bullet. Reads open stores read-only. The only write is `inbox.submit()`, so the sole-writer model and 102/103's crash guarantees carry over unchanged. Streaming is `follow()` resumed by `seq`, as the architecture requires. The slice plan's six 109 success criteria are each covered by a Functional Requirement. These include kill-isolation in both directions and rejection of unauthenticated requests on a non-local bind.

### [PASS] Layering and dependency directions are enforced structurally

`amoeba.serve` and `amoeba.inspection` may not import `amoeba.cli` or `amoeba.process`. Only `cli.serve` may import `amoeba.serve`. These are AST tests, and the writer guard is extended with a "`submit` only" assertion. Moving the registry to `amoeba.inspection` is what the slice plan assigns to 109. The design also rejects the cheaper options (serving from `cli`, or a separate preparatory slice) with reasons tied to the architecture's "server is not the resident process" rule.

### [PASS] Failure modes are enumerated for every new I/O path

- **Submissions:** oversized body, slow body, wrong content type, `InvalidSubmissionError` and `SubmissionWriteError` each have a status, a code and a retry rule. A mandatory `submission_id` makes retry safe.
- **Stream:** slow-client backpressure, a stalled peer (send timeout), a silent disconnect (heartbeat), a blocked hand-off thread, the slot limit, and pre- and post-200 errors are each handled. Each handling has a bounded slot-hold time.
- **Start-up:** failures split into exit 13 for pre-bind configuration and exit 1 for bind-time errors.

### [PASS] NFR restatement is appropriate

The architecture states no numeric NFR for the network path. The design restates 106's delivery bound (`follow_interval_seconds` plus read time) with a 1 s p95 target and tests it under 32 followers. It promises nothing beyond 106's bound plus transport.

### [CONCERN] Design is heavier than an effort-3, medium-risk slice needs; several mechanisms can be cut or deferred

The slice combines these pieces:
- a six-module migration;
- a store amendment;
- four endpoint groups;
- a hand-written `EventStreamResponse`;
- a bind policy with TLS validation;
- a three-check browser-defence set;
- an eleven-field `ServeSettings`;
- a three-part load tier;
- deltas to five contract docs.

The slice plan assigns "Relative Effort: 3". Candidates to cut or defer, none of which the plan's success criteria require:
- **`GET /v1/listings` catalog** (lines 36, 297). Generic reads work by listing name. Nothing in the plan or the architecture needs discovery over HTTP. Defer it until a consumer asks.
- **`body_read_timeout_seconds` with chunked read and `fail_after`** (lines 140-141, 347). No consumer sends slow bodies. A `Content-Length` cap alone, or a uvicorn-level limit, meets the 1 MiB bound. Defer the 408 path.
- **Tunables with no demonstrated need** (line 258). `max_connections`/`limit_concurrency`, `shutdown_grace_seconds`, `body_read_timeout_seconds` and `send_timeout_seconds` could use uvicorn or anyio defaults until a load test shows a problem. The CLAUDE.md rule "resist adding complexity" applies here.
- **Read-latency regression guard** (line 363). The design itself says no read latency is promised, so this p95 ≤ 200 ms test guards a number nobody consumes. Keep the starvation check (reads succeed with streams open) and drop the numeric target.
- **Origin, Host and content-type triple** (lines 198-201). The threat is real. But the 415 rule is already needed for body parsing, and the Origin and Host checks are two small, justified middleware pieces. They are acceptable as written. The load-bearing cut is the catalog, then the body-timeout path, then the tunables.

Dropping these keeps every slice-plan success criterion intact. If the PM wants them kept, the design should say which consumer or criterion each one serves.

### [NOTE] Migration table names modules from designs that are not yet merged

The Migration Plan names `inspect_checks.py` and `inspect_cf.py`, and their row signatures, from 107 and 108's `not_started` designs. The slice plan makes the "107 and 108 are merged" check a hard gate, and Development Approach step 1 stops for the PM and requires the table to be revalidated against merged code. That mitigation is adequate. Until then, the Migration Plan table is provisional.

### [NOTE] Design is stricter than the architecture on the non-local bind

The architecture requires only "any non-local bind requires authentication". The design also requires TLS and a minimum token length (D3). It also adds an `Origin` refusal and a loopback `Host` check on every bind. These tighten the constraint without contradicting it, and they are justified by the cleartext-credential and DNS-rebinding risks. The slice plan's bind-refusal criterion is still met. No action is needed, but the PM should know the design goes beyond the stated minimum.

### Run Digest

- Response length: 6150 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 176131 / 84476 / 91649 / 4545 / not computed
- Duration: 39.6 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
