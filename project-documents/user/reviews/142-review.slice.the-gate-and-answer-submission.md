---
docType: review
layer: project
reviewType: slice
slice: the-gate-and-answer-submission
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/142-slice.the-gate-and-answer-submission.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: c52170f7f919b9252b383e8d31a69096ef440349
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 190903
cachedTokens: 94263
cacheWriteTokens: 96634
completionTokens: 4894
durationSeconds: 43.4
costUsd: 0.445753
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: concern
    category: architectural-boundaries
    summary: "`decision` is caller-supplied, so the gated operation can submit more than a `resume`"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D5 — The answerer's submission is an ordinary resolution with a submission record"
  - id: F002
    severity: concern
    category: under-specification
    summary: "The identity of \"the answerer\" as submitter is left undefined"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D5 — The answerer's submission is an ordinary resolution with a submission record"
  - id: F003
    severity: note
    category: hidden-dependency
    summary: "D6 makes 142's rejected-resolution behavior depend on a 144 test"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D6 — An answerer resolution the Runner rejects"
  - id: F004
    severity: pass
    category: transaction-integrity
    summary: "Gate, count and submission are one transaction, as the architecture requires"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D1 — The gate runs inside the submission transaction, passed in as a pure function"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Race and failure paths are enumerated with explicit handling"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D4 — `submit_answer`'s outcomes, and why a lost race writes nothing"
  - id: F006
    severity: pass
    category: scope
    summary: "Scope and proportionality match the slice plan entry"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#Technical Scope"
  - id: F007
    severity: pass
    category: architectural-alignment
    summary: "Reserved screen and limit semantics align with the architecture"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D2 — The gate's checks, in order"
---

# Review: slice — slice 142

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] `decision` is caller-supplied, so the gated operation can submit more than a `resume`

The architecture's hard bound is that "the answerer can only resume a paused step with instructions". It cites this as one of the three bounds that make a wrong answer cost one rerun of one step. It also says a confirmed answer "becomes a `resume` resolution". `submit_answer` takes `decision` as a free string (API Contracts, D5) and writes it to the slot unread. Only the Runner's judge checks it later. D5 accepts this because the PM path works the same way.

The PM path is not the same case. It is a human-authored path that is meant to allow any decision. This operation is the answerer's only submission path, and the slice's Value section claims "safety by construction". A buggy or later-modified caller in 144 could pass another decision and get it through the gate.

Fix: have the store write `resume` itself, through a store-side constant or enum member. That also keeps the Runner out of the store, which was D5's reason for taking strings. Then drop `decision` from the signature. That removes a parameter and a blank-check, and it puts the bound in the layer that enforces the gate.

### [CONCERN] The identity of "the answerer" as submitter is left undefined

The architecture requires the resolution to be "submitted … with the answerer as the submitter" and the submission record to show who answered. 142 writes the inbox submission row and `resolved_by`. It takes both `submitted_by` and `detail` from the caller and says they are "defined with the caller in 144".

The one operation that writes the provenance row therefore owns neither the submitter identity nor the provenance text. 142's tests pass arbitrary strings, so nothing in this slice verifies the architecture's provenance requirement. Different callers could also write different submitter names, which would fragment the submissions listing.

Fix: define the answerer's submitter name once in the store, beside `AnsweredBy.ANSWERER`. Alternatively, derive it from that value. Keep `detail` as the caller's text. This is also a smaller signature.

### [NOTE] D6 makes 142's rejected-resolution behavior depend on a 144 test

If the Runner rejects the answerer's resume, the record stays `answered` (answerer) and counts toward the limit. The PM's later resume of the re-block is not recorded as precedent. That conflicts with the architecture's "a question the PM already answered stays answered" for that narrow path.

The slice names the dependency openly and ties it to 144's required `sq_answer` acceptance test, so the direction of the dependency is acceptable. Treat it as a tracked obligation: 144's design must keep that test.

### [PASS] Gate, count and submission are one transaction, as the architecture requires

The answer count is read under `BEGIN IMMEDIATE`, and the gate is called once under the write lock. The slot write, the submission insert and the record update commit together. This matches "The record is the memory". The gate is a single function, and the store holds no terms or limit, so dependencies point from Runner to store with no inversion. The rejected alternatives (a split gate, a count read before the call) are the ones that would break the architecture.

### [PASS] Race and failure paths are enumerated with explicit handling

The doc covers the PM-first race (`block_resolved`, left to 141's acknowledgment), the answerer-first race (the inbox rejects the PM's submission), replay (`settled`), a raising gate (rollback and propagate), `StoreBusyError`, and an unknown id or blank input. The crash tests inject failure at each of the three writes. This matches the architecture's step 7 and the "PM wins" rule.

### [PASS] Scope and proportionality match the slice plan entry

Each included item is assigned by the slice plan's 142 entry: the gate, the operation, the two config keys, the start-up probe, and the operation in `docs/store-contract.md`. The two `DeclineReason` members, the `reserved_term` column and the listing column are the items 141 deferred to 142. The exclusions (answering-stage calls, citations, any inbox behavior change) correctly leave 143 and 144 untouched. The extraction of `_insert_submission` is the lightest way to avoid a second insert statement. The design adds no configuration beyond the two required keys, and the plan's no-defaults and explicit-empty-list rules are met (D7).

### [PASS] Reserved screen and limit semantics align with the architecture

The screen is case-insensitive, runs over both question and answer, and takes its terms from per-project config with no defaults. Matching is deliberately over-inclusive, and the doc states the screen is a net, not a security boundary, as the architecture does. The limit counts only the answerer's answers. `block_resolved` is checked before the gate, so an unsubmittable answer is not declined and does not use a limit slot. The architecture states no latency or throughput NFR on this path, so none needs restating.

### Run Digest

- Response length: 6262 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 190903 / 94263 / 96634 / 4894 / not computed
- Duration: 43.4 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
