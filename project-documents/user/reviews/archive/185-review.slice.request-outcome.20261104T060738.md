---
docType: review
layer: project
reviewType: slice
slice: request-outcome
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/185-slice.request-outcome.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: af72a949ddf32937d96dd9b84b3d59dada2e148a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 107180
cachedTokens: 11162
cacheWriteTokens: 96014
completionTokens: 4240
durationSeconds: 40.6
costUsd: 0.428422
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: concern
    category: architecture-alignment
    summary: "Request limit is per asker-provider pair, but the architecture defines it as a cap on requests to one provider"
    location: "project-documents/user/slices/185-slice.request-outcome.md#D5 — The request limit counts live requests from this asker to this provider"
  - id: F002
    severity: note
    category: architecture-alignment
    summary: "Reverse-request refusal is broader than the architecture and slice-plan wording"
    location: "project-documents/user/slices/185-slice.request-outcome.md#D6 — The reverse-request refusal: any live edge from the provider waiting on the asker"
  - id: F003
    severity: note
    category: error-handling
    summary: "Cross-store failure modes are enumerated"
    location: "project-documents/user/slices/185-slice.request-outcome.md#D7, D8, D4"
  - id: F004
    severity: pass
    category: architecture-alignment
    summary: "Layering, purity and dependency direction"
    location: "project-documents/user/slices/185-slice.request-outcome.md#Component Structure"
  - id: F005
    severity: pass
    category: scope
    summary: "Scope and proportionality"
    location: "project-documents/user/slices/185-slice.request-outcome.md#Technical Scope"
  - id: F006
    severity: pass
    category: nfr
    summary: "No architecture NFR on these paths"
    location: "project-documents/user/architecture/180-arch.program-coordination.md"
---

# Review: slice — slice 185

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Request limit is per asker-provider pair, but the architecture defines it as a cap on requests to one provider

The architecture (Envisioned State, "Request") describes "a request limit that caps the open requests to one provider, the only throttle on requests going first." D5 instead counts live requests from this asker to this provider.

In a program of three or four repos, a provider that several members ask can have up to the sum of every asker's `request_limit` open at once. Each of those requests is placed ahead of the provider's planned work. The per-pair cap therefore does not bound the load that the architecture says this limit exists to bound.

D5 argues that a per-provider cap would turn each asker's number into a share of a pool. That is a design choice, but it contradicts the architecture's wording and leaves the architecture unamended. Either:
- count per provider, as the architecture says; or
- amend the architecture text and state that the aggregate bound on a provider is the sum of the askers' limits, so the "only throttle" claim stays accurate.

### [NOTE] Reverse-request refusal is broader than the architecture and slice-plan wording

The architecture refuses a request only when the provider's checkout is held by a slice waiting on a request from the requester. D6 refuses on any open edge from the provider that waits on the asker, without resolving checkouts. The design states the deviation, gives the reason (it avoids a snapshot read and `resolve_checkout` failure modes inside the asker's finish) and gives the cost (a multi-checkout member may be over-refused). The over-refusal fails safe, because the question goes to the PM with a reason. This is acceptable. Record it in the architecture's reverse-request paragraph when the contract docs are updated, so the two documents do not diverge.

### [NOTE] Cross-store failure modes are enumerated

The design handles each failure path explicitly:
- A crash at each of the three writes has a defined next-tick outcome, shown in the D8 table, and a kill-at-each-point test.
- A PM resolution before write 1 and after write 1 is handled.
- A request is never turned into `answer_discarded`, which is the architecture's stranded-sweep requirement.
- An unreadable provider is treated as a blocked reason, not a failure, and does not exit the process.
- A program-store failure follows 181's exit rule.

Entry-first ordering and the caller-supplied idempotent `request_id` match the architecture's "owning tick finishes partial state" principle. The only unspecified path is a `ValueError` from `create_request` when an existing row differs from the arguments. If that fires inside the stranded sweep, the tick's response is not stated. It should only be reachable through corruption, so this is minor.

### [PASS] Layering, purity and dependency direction

`gate.py`, `decide.py` and `requests_text` stay pure. All I/O is isolated in `request_facts.py`, `request_writes.py`, `program_sources.py` and the stage. 120's lifecycle does not read the program. The asker's tick writes only the request and edge rows it owns. Release and supersession are left unchanged in 183 and 184. The "Changes to 140" items from the architecture are all covered: the `requested` state and request link, the gate centralized with the answer limit, the request reply shape, a check limited to what B's passages and the program concept can show, and `RELEASABLE_STATES` including `requested`.

### [PASS] Scope and proportionality

The scope matches the slice plan entry. The deferred items (cycle checks beyond two members, merging duplicates, separate request checkouts) stay excluded. `program_requests` is required by the architecture's cross-project visibility rule and is the only way the answer step can decline a duplicate. The two new modules keep `finish.py` under the size guideline. The amendments to 184's API and 183's `RELEASABLE_STATES` are small and named in Provides. `request_limit` is required with no default, which follows the project's no-silent-defaults rule, and the breaking config change is documented.

### [PASS] No architecture NFR on these paths

The architecture states no numeric latency or throughput targets for the paths this slice touches, so nothing needs restating. The slice's cost note (no added model call, two or three program-store reads per member question, at most one read-only member store open per confirmed request) is adequate.

### Run Digest

- Response length: 5628 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 107180 / 11162 / 96014 / 4240 / not computed
- Duration: 40.6 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
