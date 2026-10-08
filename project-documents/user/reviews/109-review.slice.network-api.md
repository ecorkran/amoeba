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
reviewedSha: be189d63a745e6baa86db39be1915e94384dcede
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 38.2
runId: run-20261008-p4-76c1c140
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: dependency-direction
    summary: "Import rule conflicts with where `discover_project_ids` and `store_path_for` live"
    location: "project-documents/user/slices/109-slice.network-api.md:129"
  - id: F002
    severity: concern
    category: under-specification
    summary: "Stream-slot limiter and thread-pool separation is under-specified"
    location: "project-documents/user/slices/109-slice.network-api.md:243"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Mid-stream terminal behavior for non-auth failures is implicit"
    location: "project-documents/user/slices/109-slice.network-api.md:246"
  - id: F004
    severity: concern
    category: scope
    summary: "Group A rewrites finished code from slices 102–108 inside this slice"
    location: "project-documents/user/slices/109-slice.network-api.md:57-62"
  - id: F005
    severity: note
    category: architecture-alignment
    summary: "Architecture's \"push, not poll\" is met at the client edge only"
    location: "project-documents/user/slices/109-slice.network-api.md:27"
  - id: F006
    severity: note
    category: scope
    summary: "TLS, scopes, and principal binding go beyond the architecture and are routed to PM ratification"
    location: "project-documents/user/slices/109-slice.network-api.md:296-306"
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "Boundaries and writer model preserved"
    location: "project-documents/user/slices/109-slice.network-api.md#Technical Decisions"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Failure modes and bounds enumerated for new I/O paths"
    location: "project-documents/user/slices/109-slice.network-api.md#D5a"
---

# Review: slice — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Import rule conflicts with where `discover_project_ids` and `store_path_for` live

The slice says `amoeba.serve` "does not import `amoeba.process`" and lists this as a technical requirement (line 453). The read path calls `store_path_for(supervisor_dir, project)` (line 139), and D8 relies on `discover_project_ids`. In the repo, both functions are defined in `src/amoeba/process/supervisor.py:28` and `:44`. As written, the server cannot meet its own boundary rule. The slice's Migration Plan doesn't mention relocating these two functions. Either move them to a neutral module such as `amoeba.store.paths`, with `amoeba.process` re-importing them, or relax the rule. Add the relocation to Group A and to the Consumers list. This matters because the architecture's reason for a separate process is that the server must not depend on recovery-critical code.

### [CONCERN] Stream-slot limiter and thread-pool separation is under-specified

D5 says streams draw "their own limiter" separate from Starlette's sync pool, so "too many streams cannot starve reads". The slice doesn't say how that is built. Starlette and anyio sync endpoints and `run_in_threadpool` share one default 40-token limiter. Dedicated threads or a separate executor would give the isolation. The success criterion (line 439) tests the outcome, but the mechanism is left open. Name the mechanism, because this property protects the architecture's read-availability goal.

### [CONCERN] Mid-stream terminal behavior for non-auth failures is implicit

Auth failures get an explicit `event: closed` with a code. Store errors after streaming starts (schema bump, `StoreBusyError`, worker-thread exception) just "end the stream". The client cannot tell that from a network drop and has to reconnect to learn the cause. The strategy is acceptable, but state it for each case. Also say whether the worker thread logs the exception, per the project's exception rules. The POST path has a similar gap: a client disconnecting mid-body is covered only by the timeout, not stated as a case.

### [CONCERN] Group A rewrites finished code from slices 102–108 inside this slice

The row-function signature change, `Listing.abbreviated_columns`, the `change_as_json` move, and the relocation of every listing module are a cross-slice refactor of five or more slices' code. The slice explicitly rejects making it a separate slice. It does mitigate the risk with a hard merge gate, a byte-for-byte output comparison, and the group boundary. The rationale is sound, but effort 4 and two task groups push this toward over-scoping. Keep Group A independently committable and reviewable, as the doc says. Phase 5 should be ready to split it if the gate task finds 105–108 unmerged.

### [NOTE] Architecture's "push, not poll" is met at the client edge only

The server's `follow()` still polls the store every `follow_interval_seconds`. The slice states this honestly and restates the latency bound (0.25 s plus encode time, and up to 1.0 s idle tick for submissions). The architecture sets no numeric NFR, so this is consistent.

### [NOTE] TLS, scopes, and principal binding go beyond the architecture and are routed to PM ratification

Required TLS off-loopback, `read` and `submit` scopes, `submitted_by` bound to the principal, the new exit code 12, and the Starlette and uvicorn dependencies are each tabled with a fallback. Listing discovery is called out as an addition. The architecture left the protocol, authentication scheme, and endpoint shape to slice design, so these are within latitude. Phase 5 should honor the stated ratification gate.

### [PASS] Boundaries and writer model preserved

The server is a separate, lock-free process that opens stores only read-only and writes only inbox files. Its writer guard covers `amoeba.serve` and `amoeba.inspection`. It binds to loopback by default and refuses off-loopback binds without tokens and TLS. It never infers trust from the peer address. The feed uses 106's `follow()` with a client-owned `seq` cursor. Resident-process status is excluded for a stated reason (D7). The same-host limit for WAL and the inbox is stated. Together these match the architecture's network-surface constraints and add no write path.

### [PASS] Failure modes and bounds enumerated for new I/O paths

D5a lists every remote-caused wait with a bound and an outcome. These cover store contention, a slow body, a stalled stream reader, a full socket buffer, idle connections, connection cap, and slow headers. The doc also specifies:
- fail-closed handling when the token file goes bad at runtime, with once-only ERROR and INFO logging;
- re-checking authentication on open streams at each heartbeat;
- the submission-status race handled by scan order and two passes;
- an explicit stop-and-ask path if uvicorn's `send` does not apply backpressure.

### Run Digest

- Response length: 6047 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 38.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
