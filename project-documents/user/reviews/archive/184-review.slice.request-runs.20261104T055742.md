---
docType: review
layer: project
reviewType: slice
slice: request-runs
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/184-slice.request-runs.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 6025650b876d630213766e02068b60dd7c2d0156
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 305695
cachedTokens: 198292
cacheWriteTokens: 107395
completionTokens: 7155
durationSeconds: 61.2
costUsd: 0.521818
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency direction match the architecture"
    location: "project-documents/user/slices/184-slice.request-runs.md#Architecture"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for each new I/O path"
    location: "project-documents/user/slices/184-slice.request-runs.md#D2, D7, D8"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Design is overweight for the slice; several mechanisms can be cut or collapsed"
    location: "project-documents/user/slices/184-slice.request-runs.md#Technical Scope"
  - id: F004
    severity: concern
    category: architecture-alignment
    summary: "\"Second request slice is not held up by a stopped first one\" is narrowed without being reconciled to the slice plan"
    location: "project-documents/user/slices/184-slice.request-runs.md:333-338, 488"
  - id: F005
    severity: note
    category: error-handling
    summary: "Replied requests can stall later requests with no timeout"
    location: "project-documents/user/slices/184-slice.request-runs.md:248-253, 289-299"
  - id: F006
    severity: note
    category: dependencies
    summary: "184 rewrites 183's seams before 183 is implemented"
    location: "project-documents/user/slices/184-slice.request-runs.md:168, 322-325, 477"
---

# Review: slice — slice 184

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Layering and dependency direction match the architecture

- The program stage and the request stage run inside the Runner tick, and every `sq`, `cf` and `git` call goes through the existing journaled path.
- `runner/lifecycle` still receives only node-id sets, and `program/band.py` imports only `store` and `upstream`.
- The provider's tick owns request rows and binding, and the asker's tick owns edge observation. This matches the architecture's one-owner-per-transition rule.
- Each cross-store write has a defined order, and the owner finishes any partial state on its next tick:
  - Launch: provider-store journal, then program-store `running`.
  - Finish: program-store write, then entry resolved.
  - Bind: compare-and-set in `bind_edge`.
- A crash between launch writes is covered by adopting the existing entry (D7 step 4), and nothing relaunches a lost run.

### [PASS] Failure modes are enumerated for each new I/O path

- D2 enumerates the waits and failures.
- D7 puts every step that can fail cleanly before the journal.
- D8 covers a failed head read, a paused run, recovery of a lost run, and spawn failure.
- D10 covers the supersession race.
- The design restates no numeric NFR. The architecture states none for this path, so nothing is missing.

### [CONCERN] Design is overweight for the slice; several mechanisms can be cut or collapsed

The slice touches the schema (including an `edges` rebuild), the request state machine, a new node kind and journal kind, the checkout hold, readiness, governance, sort key, plan freshness, config, probe wiring, inspection and three contract docs. Effort is 4. Candidates to cut or defer:
- **D12 membership-drive restriction.** The `membership_driven` intersection with `standalone_initiatives` exists only to guard "a future producer that binds an edge to a planned slice". No such producer exists in 184 or 185. `standalone_initiatives` is still needed for no-implicit-predecessor. Drop the intersection and use `ProgramView.providing` directly until a producer exists.
- **D2 `RequestWait` has nine stored, CHECK-pinned values.**
  - `provider_unreadable`, `checkout_unresolved` and `read_failed` are all "cannot evaluate" cases. They could share one wait, with the reason in `wait_detail`.
  - A smaller vocabulary means a smaller SQL `CHECK` and fewer enum-to-SQL pin tests.
- **D15 `member_has_live_requests` is nearly redundant.** Every `pending`, `running`, `replied` or `failed` request has an open edge, and 183's `member_has_live_edges` already rejects removal for an open edge on either side. The only gap is a running request whose edge was superseded. Cover that by extending the 183 rule with a request-state check inside it, or defer it. Note 183, D11 does say "184 extends it to requests", so this is a trim, not a removal.
- **Verification walkthrough and docs.** The seven-step walkthrough, the kept-scenario-directory env var and the long component table restate what the tests and Technical Requirements already say. Trim them to one scenario test plus the inspection check.

### [CONCERN] "Second request slice is not held up by a stopped first one" is narrowed without being reconciled to the slice plan

- The slice plan's success criterion says a second request slice "is not held up by a stopped first one".
- D13 says the opposite in practice: a stopped first request slice holds its checkout, so the second waits "as any slice does".
- The slice's own criterion at line 488 redefines the test as "ready while a first one is stopped, and launches when the checkout is free".
- The architecture does accept the normal checkout rule for the request slice, and it also says "one stopped or waiting request never holds up another."
- The design should say plainly that it delivers readiness independence, not runtime independence. It should record this as a deviation from the plan criterion, with the same cost statement the architecture gives for held checkouts. Otherwise the criterion reads as met when it is only half met.

### [NOTE] Replied requests can stall later requests with no timeout

- D6 serializes requests per provider, and a `replied` request stays in place until a plan read completes.
- A plan read that never succeeds, or a run that never finishes (there is a cost cap but no wall-clock limit), blocks every later request to that provider.
- The exits are the PM's resolution of the asker's block (D10 withdrawal) and the `plan_read_failed` escalation. Both are visible on the blocked list, so this is handled and needs no change.
- The design could say in one line that no request timeout exists by design.

### [NOTE] 184 rewrites 183's seams before 183 is implemented

- 184 wraps 183's `waiting` argument in `ProgramReadiness`, amends 183's two-writer statement, and rebuilds `edges`.
- The prerequisite ("184 starts after 183 merges; tasks follow the code") is adequate.
- If 183's design changes, consider having 183 expose `ProgramReadiness` up front. That would avoid a signature change on freshly merged code.

### Run Digest

- Response length: 5930 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 305695 / 198292 / 107395 / 7155 / not computed
- Duration: 61.2 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
