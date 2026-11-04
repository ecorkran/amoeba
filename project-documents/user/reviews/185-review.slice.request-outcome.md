---
docType: review
layer: project
reviewType: slice
slice: request-outcome
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/185-slice.request-outcome.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 65e3ac4466913f3e3deb1f2af250761c133c4429
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 107449
cachedTokens: 11162
cacheWriteTokens: 96283
completionTokens: 5723
durationSeconds: 50.4
costUsd: 0.444329
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Request flow matches the architecture's cross-store ordering and crash-safety rules"
    location: "project-documents/user/slices/185-slice.request-outcome.md#D7 — The three writes, each idempotent, in the architecture's order"
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "Gate, check step and `requested` state match the \"Changes to 140\" section"
    location: "project-documents/user/slices/185-slice.request-outcome.md#D2, D3, D4, D9"
  - id: F003
    severity: pass
    category: layer-boundaries
    summary: "Layer boundaries and dependency directions hold"
    location: "project-documents/user/slices/185-slice.request-outcome.md#Architecture"
  - id: F004
    severity: note
    category: architecture-alignment
    summary: "Reverse-request refusal is deliberately broader than the architecture's wording"
    location: "project-documents/user/slices/185-slice.request-outcome.md:238-244"
  - id: F005
    severity: note
    category: dependencies
    summary: "Amendments to 183 and 184 land after those slices merge"
    location: "project-documents/user/slices/185-slice.request-outcome.md:259, 408"
  - id: F006
    severity: note
    category: proportionality
    summary: "The `program_requests` passage is the heaviest optional part"
    location: "project-documents/user/slices/185-slice.request-outcome.md:294-309"
  - id: F007
    severity: note
    category: concurrency
    summary: "Lock-free gate relies on sequential ticking"
    location: "project-documents/user/slices/185-slice.request-outcome.md:227"
---

# Review: slice — slice 185

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Request flow matches the architecture's cross-store ordering and crash-safety rules

The three writes follow the architecture's order: answering entry resolved, then program-store request and edge, then record moved to `requested`. The asker's tick owns all three. D8 closes the gap the architecture names, where a crash between the first two writes turns a request into `answer_discarded`. It does this by reading the request from the entry's result, which is always written before the request row, so there is no need to check for a request row. The four-point crash table and the kill-at-each-point test cover every crash position. A caller-supplied `request_id`, derived from the entry id, makes the retries safe.

### [PASS] Gate, check step and `requested` state match the "Changes to 140" section

- **Gate:** it sits beside the answer gate in `gate.py` and shares the answer limit and reserved screen with it, so each rule is written once, as the architecture asks.
- **Check step:** it confirms only that the need is real and belongs to the provider's part of the program. It is explicitly told not to judge whether the provider already meets the need, which is the request run's call.
- **Refusals:** each one declines with a distinct reason, which matches "a refused request is a decline with a reason".
- **`coordinator`:** `RELEASABLE_STATES` gains `requested` and the `coordinator` `answered_by` value is treated as a non-answerer.
- **Purity:** `decide.py` and `gate.py` stay pure, with all I/O in the new facts and writes modules.

### [PASS] Layer boundaries and dependency directions hold

The asker's tick writes only the asker's store and the program store, and it opens the provider's store read-only. It writes no desired-state rows and issues no new `sq`, `cf` or `git` command. The program store is never imported by `runner/lifecycle`. An unreadable provider skips the band check rather than failing or declining. This matches "a member that cannot be read is a blocked reason, not a failure", and 184 re-checks the band before launch. A program-store failure exits the process through 181's rule, as the architecture requires.

### [NOTE] Reverse-request refusal is deliberately broader than the architecture's wording

The architecture refuses a request to a member "whose checkout is held by a slice that is itself waiting on a request from the requester". D6 refuses on any open edge from the provider that waits on the requester. It avoids resolving the provider's checkout and snapshot inside the asker's finish, and the document states the deviation and its cost. For single-checkout members the two forms give the same answer. A member with several checkouts may be over-refused to the PM, which fits the gate's existing bias. This is lighter than the architecture's form and I accept it. The architecture's wording could be updated to match when 185 lands, so the two documents do not drift.

### [NOTE] Amendments to 183 and 184 land after those slices merge

Making `create_request` idempotent on a caller-supplied `request_id` and adding `requested` to `RELEASABLE_STATES` change APIs that 184 and 183 own. The design handles this by updating their design text and by starting 185's tasks only after 184 merges. Folding both changes into the 183 and 184 designs before they are implemented would avoid reopening merged code. This is optional, and the current approach is workable.

### [NOTE] The `program_requests` passage is the heaviest optional part

The architecture requires the answerer to see the edges and requests its project is party to, and 182 left this to 185, so the passage is in scope. Its fitting mechanism is a separate size budget, a need preview cut and a one-line fallback. That is more than the rest of the slice needs, because the request limit already bounds duplicates. If the tasks run long, the fallback line and the preview constant are the first things to simplify. I am not raising it as a CONCERN, because it keeps request state from ever causing `sources_too_large`.

### [NOTE] Lock-free gate relies on sequential ticking

The gate's facts span three stores, so it runs without the asker store's write lock. The justification is that one resident process ticks projects one at a time and only the asker creates its own requests. That holds under the architecture's single-Runner model. If ticks were ever parallelized, the request limit, which counts across askers, could be exceeded. A one-line statement of this assumption in the process contract would help.

### Run Digest

- Response length: 5370 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 107449 / 11162 / 96283 / 5723 / not computed
- Duration: 50.4 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
