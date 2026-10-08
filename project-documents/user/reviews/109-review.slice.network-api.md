---
docType: review
layer: project
reviewType: slice
slice: network-api
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/109-slice.network-api.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 3c50fa2729eafebf95d4359ca4235bd5d0f112e7
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 52.5
runId: run-20261008-p4-76c1c140
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Core architectural constraints are honored"
    location: "project-documents/user/slices/109-slice.network-api.md#Technical Decisions"
  - id: F002
    severity: concern
    category: dependency-direction
    summary: "Moved registry keeps `argparse.Namespace` as its row-function contract"
    location: "project-documents/user/slices/109-slice.network-api.md#D3 — Reads are the inspect listing registry"
  - id: F003
    severity: concern
    category: scope-and-sequencing
    summary: "Registry move edits code owned by slices 105–108, with an ordering coupling"
    location: "project-documents/user/slices/109-slice.network-api.md#Migration Plan"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Stalled-peer failure mode on streams has no timeout"
    location: "project-documents/user/slices/109-slice.network-api.md#D5 — The stream runs follow() in a bounded worker thread"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Open read snapshot may be held during backpressure"
    location: "project-documents/user/slices/109-slice.network-api.md#Data Flow — The feed stream"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Token-file failure after startup and mid-request is unspecified"
    location: "project-documents/user/slices/109-slice.network-api.md#State Management"
  - id: F007
    severity: concern
    category: security-boundary
    summary: "Authorization is all-or-nothing for any valid principal"
    location: "project-documents/user/slices/109-slice.network-api.md#D6 — Authentication is explicit configuration"
  - id: F008
    severity: concern
    category: failure-modes
    summary: "Unbounded response size and incomplete slow-request handling"
    location: "project-documents/user/slices/109-slice.network-api.md#API Contracts"
  - id: F009
    severity: note
    category: nfr
    summary: "Push latency and NFR statement"
    location: "project-documents/user/slices/109-slice.network-api.md#Value"
  - id: F010
    severity: note
    category: scope
    summary: "Scope additions at the edge of the architecture"
    location: "project-documents/user/slices/109-slice.network-api.md#Technical Scope"
  - id: F011
    severity: note
    category: dependencies
    summary: "New runtime dependencies and ratification gates"
    location: "project-documents/user/slices/109-slice.network-api.md#D2 — Starlette on uvicorn"
  - id: F012
    severity: note
    category: integration
    summary: "Integration with slice 110 is acknowledged but unresolved"
    location: "project-documents/user/slices/109-slice.network-api.md#Provides to Other Slices"
---

# Review: slice — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Core architectural constraints are honored

The slice follows each constraint from the architecture's "Network surface" section:
- `amoeba serve` is a separate process that takes no lock (D8).
- Stores are opened read-only.
- The only write is `inbox.submit()`, which preserves the sole-writer model (D4).
- The feed tails `follow()` and resumes by `seq` (D1, D5).
- The default bind is localhost, and a non-loopback bind requires auth (D6).
- A writer-guard test covers `amoeba.serve` and `amoeba.inspection`.

Stricter-than-required choices (TLS for non-loopback binds, principal binding) are flagged for PM ratification. Protocol, auth scheme, and endpoint shape are decisions the architecture leaves to slice design.

### [CONCERN] Moved registry keeps `argparse.Namespace` as its row-function contract

The slice moves the registry into `amoeba.inspection` to avoid `serve` importing `cli`. The row functions still take `(store, argparse.Namespace)`, so a CLI-parsing type remains the contract of a layer the server depends on. The server must build a synthetic `Namespace` with `json=True` from query parameters. This hides a CLI dependency inside the shared layer and ties the server to argparse semantics. The slice rejected a typed options class only because options would be declared twice. A thin typed options mapping derived from `Listing`'s declared options would remove the type leak without duplicating declarations. At minimum, the slice should state why `Namespace` is acceptable as a stable inspection-layer contract.

### [CONCERN] Registry move edits code owned by slices 105–108, with an ordering coupling

The architecture says the network API "changes no contract in 101–108". The migration relocates 102's registry and also the 106 modules. It reaches 107 and 108 modules too ("the listing modules 107 and 108 add"), yet the slice says those slices are not prerequisites. If 107 or 108 land after 109, they must be authored in `amoeba.inspection`. If they land before, 109 must move them. The "no re-export shims" rule makes the second case a hard cross-slice edit. The slice should state which ordering is assumed, who owns the update to 107 and 108 task docs, and how a late-landing listing finds its new home. The slice-plan or task docs for 107 and 108 should be updated.

### [CONCERN] Stalled-peer failure mode on streams has no timeout

A client that holds the TCP connection open but stops reading blocks the worker thread on the full buffer indefinitely. The thread is released only on disconnect, shutdown, or a failed heartbeat write, and a stalled-but-open connection may take a long time to produce a failed write. Enough stalled clients exhaust `max_feed_streams` and make the feed unavailable. The slice says "the client is behind, not lost" but sets no maximum stall duration or write timeout. Add an explicit send-stall timeout, or state why unbounded stall is accepted.

### [CONCERN] Open read snapshot may be held during backpressure

The architecture puts the resident process as sole writer of a store that remote streams will now tail. When a stream thread blocks on the full buffer, the slice does not say whether `follow()` is holding a read transaction or connection. If it is, a slow remote client could pin a snapshot against the resident writer. In SQLite WAL mode this stalls checkpointing and grows the WAL. This depends on 106's `follow()`. The slice should state that each poll uses a short-lived read transaction released before the thread blocks, or that the buffer-full wait occurs outside any transaction. The same applies to read-endpoint behavior under writer lock contention. Say which status is returned and add a bounded timeout rather than leaving it implicit in `store_unavailable`.

### [CONCERN] Token-file failure after startup and mid-request is unspecified

Startup refuses a missing, unreadable, empty, or malformed token file. The file is re-read on every authenticated request, though, and the post-startup cases are not specified. The file might be deleted, become unreadable, be hand-edited into a malformed line, or have its last token revoked. The slice must state that auth fails closed with an explicit status and code (for example 503, not 401, so operators can distinguish a broken file from bad credentials), and that the error is logged. A silent fall-through to "no tokens, deny all" and one to "skip bad line" must both be excluded. Also, `ApiErrorCode` has no code for this case.

### [CONCERN] Authorization is all-or-nothing for any valid principal

Authentication binds `submitted_by` to the principal, but any valid token can read every project and listing, including payloads in `messages` and `submissions`. It can also submit any `SubmissionKind`, including `create_project` and `resolution`. The architecture requires authentication only, so this is not a violation. But this is the first network exposure of the only write path, and a remote agent or status UI would get the same power as the notification bridge. The slice should either record per-principal scopes (read-only vs submit, optionally allowed kinds or projects) as a deliberate exclusion with rationale, or add a minimal scope field to the token file format while it is still cheap to define.

### [CONCERN] Unbounded response size and incomplete slow-request handling

Listing endpoints return all rows with no limit or pagination, and `encode_rows()` builds the full JSON in memory. A large `journal` or `submissions` listing can exhaust server memory, and this is now reachable by remote clients. `max_request_bytes` is enforced for bodies, but there is no read timeout for a slow request body (slowloris). That matters for a non-loopback bind. State either a row cap with a truncation or paging behavior, or the explicit acceptance, and the uvicorn timeout settings used for slow request bodies. Also state the response when `submit()` is retried by a client after a timeout with the same `submission_id`. Duplicate handling depends on 103, but the HTTP status and any needed `ApiErrorCode` should be stated here.

### [NOTE] Push latency and NFR statement

The architecture sets no numeric NFR for this path, and the slice says so. The "Push, not poll" goal is met at the client edge, but `follow()` itself polls the store at `follow_interval_seconds`. End-to-end latency is therefore bounded by that interval, not instantaneous ("sent the moment `follow()` sees it"). Restating that bound as the effective latency target would be accurate. The walkthrough's "within a second or two" is an untested claim until it is tied to the `FeedSettings` default.

### [NOTE] Scope additions at the edge of the architecture

The architecture asks for reads, inbox submission, and the feed. These additions go beyond that, each with a rationale:
- `GET /listings` discovery.
- The `/changes` JSON page.
- `amoeba token add | list | revoke`.
- TLS handling.

The token CLI follows from the auth requirement. The `/changes` page and discovery are small and justified in the slice, but they widen the contract surface. The `/projects/{p}/changes` endpoint also shares a name with the `changes` listing under `/listings/changes`. That is a likely source of confusion. Consider renaming the endpoint to `feed/page`, or documenting the distinction in `network-contract.md`.

### [NOTE] New runtime dependencies and ratification gates

`starlette` and `uvicorn` are the first runtime dependencies beyond pydantic. The slice already marks D2 and D6 as requiring PM ratification. The status is `not_started`, so these should be resolved before task breakdown. Alternatives are well reasoned. The implied scale (a handful of clients) makes the dependency cost the main tradeoff against the project's "resist complexity" principle.

### [NOTE] Integration with slice 110 is acknowledged but unresolved

The slice correctly notes that 110's design has no network actor. It prescribes a fix in 110's task breakdown. That is a cross-slice gap, not a defect in 109, but the 110 design doc should be amended before 110 proceeds, so the architecture-level goal of proving the contract through the network surface is traceable.

### Run Digest

- Response length: 10042 chars
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
- Duration: 52.5 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
