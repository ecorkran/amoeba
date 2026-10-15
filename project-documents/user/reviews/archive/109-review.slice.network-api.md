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
reviewedSha: 6969de4056e02d0d60dc360abc143e6e700a39d4
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 99335
cachedTokens: 11028
cacheWriteTokens: 88303
completionTokens: 5726
durationSeconds: 50.5
costUsd: 0.412249
costBasis: provider
runId: run-20261015-slices-plan-fa1ba72e
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Network surface matches the architecture's required shape and constraints"
    location: "project-documents/user/slices/109-slice.network-api.md#Technical Decisions"
  - id: F002
    severity: pass
    category: dependency-direction
    summary: "Layering and writer-model boundaries are enforced structurally"
    location: "project-documents/user/slices/109-slice.network-api.md#Component Structure"
  - id: F003
    severity: concern
    category: proportionality
    summary: "End-to-end restart test and load tier duplicate slice 110's role"
    location: "project-documents/user/slices/109-slice.network-api.md:364-366"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Request-side stall and start-up I/O failures are not enumerated"
    location: "project-documents/user/slices/109-slice.network-api.md:138-145"
  - id: F005
    severity: note
    category: architecture-alignment
    summary: "Architecture's \"changes no contract in 101–108\" is slightly out of date"
    location: "project-documents/user/slices/109-slice.network-api.md:39"
  - id: F006
    severity: note
    category: dependencies
    summary: "Design is written against unmerged 107 and 108"
    location: "project-documents/user/slices/109-slice.network-api.md:62"
---

# Review: slice — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Network surface matches the architecture's required shape and constraints

The architecture's "Network surface" section requires:
- a separate `amoeba serve` process;
- read-only store reads;
- writes only as inbox submissions;
- the feed served from `follow()` with a `seq` resume cursor;
- loopback by default;
- authentication for any non-local bind.

D1, D3, D5, D6 and D7 meet each of these:
- **Process and writes:** there is no instance lock and no PID file, and the only write is `submit()`.
- **Feed:** SSE `id` and `Last-Event-ID` map directly onto 106's cursor rule.
- **Bind policy:** non-loopback requires a token plus TLS, enforced by a pure `check_bind` table. That is stricter than the architecture's floor.

The decisions the architecture left to slice design (protocol, auth scheme, endpoint shape) are made and justified.

### [PASS] Layering and writer-model boundaries are enforced structurally

`amoeba.serve` may not import `amoeba.cli` or `amoeba.process`, so the server cannot reach the resident process's tenants or stores. `amoeba.inspection` is likewise independent of both, and `amoeba.cli.serve` is the only importer of `amoeba.serve`. Each rule is an AST test, and the writer guard's allow-list is untouched. A further test asserts that `serve` calls no inbox function except `submit`. This keeps the architecture's "not a second writer" promise checkable.

### [CONCERN] End-to-end restart test and load tier duplicate slice 110's role

Integration Requirements asks for a subprocess test that runs:
- `kill -9` of the resident process,
- a second submission,
- a restart,
- `kill -9` of the server, and
- a restart.

The slice also lists 110 as the slice that will "run reads, submissions, and a follower over HTTP, with a restart of each process mid-sequence" (line 324). These are the same scenario.

Slice 109 already carries:
- the full `amoeba.inspection` migration,
- two store methods,
- a custom SSE response class,
- a threaded stream bridge, and
- a load tier (32 followers × 2,000 changes, plus p95 gates).

Cut the restart matrix from 109 and keep it in 110. 109's integration coverage can be a single smoke test: serve, read, submit, follow. Step 5 of the Verification Walkthrough (each process survives the other) already covers the mutual-survival check manually. The load tier is defensible because the Python rules require it for network paths. Consider trimming the 2,000-change burst to what proves ordering and no loss.

### [CONCERN] Request-side stall and start-up I/O failures are not enumerated

Stream sends and store waits have explicit timeouts and handling. Two other I/O paths do not:
- **POST body read.** The body is read chunk by chunk with a size cap, but there is no read timeout or minimum rate. A client that sends headers and then trickles or stops sending holds one of the `max_connections` (128) slots and a handler indefinitely. Authentication runs first, so this only matters for token holders, or for any local process on a loopback bind with no token. Name the strategy, such as a body-read deadline under `anyio.fail_after` mapped to an `ApiErrorCode` (e.g. 408), or state that uvicorn's timeouts cover it and pin that with a test.
- **TLS file errors at start-up.** D3 covers the policy refusals (exit 13). A missing, unreadable, or mismatched cert/key pair is not covered. D7 says a port in use exits 1 via uvicorn's error. Say which of these start-up failures exits 13 and which exit 1, and whether the message is user-readable. As written, only the "files not supplied" case is specified.

### [NOTE] Architecture's "changes no contract in 101–108" is slightly out of date

The architecture says the API "changes no contract in 101–108". The slice makes these changes:
- It replaces `argparse.Namespace` with `ListingRequest` in the listing row signature.
- It moves `discover_project_ids` and `change_line`.
- It rewrites `feed-contract.md`'s "Current state, then follow" section.
- It adds `read_transaction()` and `change_head()` to the store contract.

106 explicitly deferred the last two, and the slice states that no row or behavior changes and that the migration commit must leave output byte-identical. The design is sound. Add a one-line amendment to the architecture's Network surface bullet so it does not contradict the slice, for example "no behavior change; the listing registry moves to `amoeba.inspection`."

### [NOTE] Design is written against unmerged 107 and 108

The migration table and component tree name `inspect_checks.py` and `inspect_cf.py`, whose designs are `not_started`. The slice handles this by making "confirm 107 and 108 are merged, stop for the PM otherwise" the first task. That is an adequate gate. Re-check the module names and row signatures against the merged code before step 2, because the design records their shape only from the other slices' designs.

### Run Digest

- Response length: 5828 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 99335 / 11028 / 88303 / 5726 / not computed
- Duration: 50.5 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
