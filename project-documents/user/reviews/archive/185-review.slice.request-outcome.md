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
reviewedSha: a4903fe6aea248a24cbb7e00b1310e772c12e6e9
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 107153
cachedTokens: 11162
cacheWriteTokens: 95987
completionTokens: 4660
durationSeconds: 41.9
costUsd: 0.432515
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: concern
    category: architectural-boundary
    summary: "Required `request_limit` breaks config loading for projects outside any program"
    location: "project-documents/user/slices/185-slice.request-outcome.md:310-315"
  - id: F002
    severity: concern
    category: failure-modes
    summary: "An unbounded, never-trimmed `program_requests` passage can block unrelated questions"
    location: "project-documents/user/slices/185-slice.request-outcome.md:292-308"
  - id: F003
    severity: note
    category: architecture-alignment
    summary: "Reverse-request refusal is deliberately broader than the architecture's wording"
    location: "project-documents/user/slices/185-slice.request-outcome.md:237-243"
  - id: F004
    severity: note
    category: dependencies
    summary: "Amendments to 183 and 184 are declared and bounded"
    location: "project-documents/user/slices/185-slice.request-outcome.md:402-408"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Failure modes for the cross-store writes are enumerated"
    location: "project-documents/user/slices/185-slice.request-outcome.md:245-281"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Gate centralization and layer boundaries match the architecture"
    location: "project-documents/user/slices/185-slice.request-outcome.md:207-227"
  - id: F007
    severity: pass
    category: proportionality
    summary: "Scope is proportionate to the slice plan"
    location: "project-documents/user/slices/185-slice.request-outcome.md#Technical-Scope"
---

# Review: slice — slice 185

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Required `request_limit` breaks config loading for projects outside any program

The architecture's goal "Each project stays a project" says a project in no program "behaves exactly as it does after 140". D11 makes `answerer.request_limit` required for every project with an `answerer` section, "member or not". It also says a non-member never reads the value (D4, check 1). An existing non-member project's `projects.yaml` would therefore fail to load after this slice, and `amoeba serve` would fail to start. The doc offers the rationale that the loader cannot see program membership. That explains the choice but does not meet the goal.

A lighter option keeps the no-silent-defaults rule. Make the field optional in the schema and add a check-7 precondition. If a member's request reaches the request limit check with no configured value, decline with an explicit reason such as `request_limit_unconfigured`. That declines an unconfigured member's request and leaves non-members untouched. Alternatively, state in the architecture that a config-schema change is an accepted exception to the "exactly as after 140" goal. The current text neither takes the lighter path nor records that exception.

### [CONCERN] An unbounded, never-trimmed `program_requests` passage can block unrelated questions

D1 says the need is never cut. D10 renders each live edge's full `need` into the passage. D10 also counts the passage with the untrimmed rules, plan and program passages, and says a set too large for it is `sources_too_large`. The number of live edges is bounded only by `request_limit` per provider, multiplied by the number of providers and by edges where the asker is the provider. The need text itself is unbounded. A project with a few large open requests could therefore decline every member question with `sources_too_large`. That includes questions unrelated to those requests. A secondary effect is that the PM sees an unrelated decline reason. The doc does not enumerate this failure mode or say how it is handled.

Cut to what the answer step needs. Its only use of the passage is duplicate detection (D2). The passage can list provider, state and a bounded need excerpt or the request id. That keeps the passage proportional and removes the failure mode. Alternatively, state a bound explicitly and make the passage the first thing trimmed.

### [NOTE] Reverse-request refusal is deliberately broader than the architecture's wording

The architecture refuses a request to a member "whose checkout is held by a slice that is itself waiting on a request from the requester". D6 refuses any open edge from the provider waiting on the asker. It does so to avoid a `resolve_checkout` call and snapshot read inside the asker's finish. The deviation and its cost (over-refusal costs one PM answer) are named. The direction is safe, since it can only over-refuse. The architecture's "that one check" wording could be updated so the two documents agree.

### [NOTE] Amendments to 183 and 184 are declared and bounded

185 asks 184 for a required `request_id` on `create_request` and for idempotency on it, and asks 183 to add `requested` to `RELEASABLE_STATES`. The latter matches the architecture's "and `requested` once it exists". The slice lists both amendments under "Provides" and says the upstream docs will be updated. The dependency direction stays correct because 185 consumes 183 and 184. 184 is not yet implemented, so the cost is only edits to its design text.

### [PASS] Failure modes for the cross-store writes are enumerated

The slice meets the architecture's requirement that the stranded sweep check before declining. D7 and D8 give a four-point crash table in which every state is finished by the next tick. The result is written before the request row, so a crash can never become `answer_discarded`. A PM resolution racing the writes is handled. An unreadable provider is a pass, which keeps the "blocked reason, not a failure" rule. A program store failure exits the process (181, D7). A test kills the sequence at each point.

### [PASS] Gate centralization and layer boundaries match the architecture

The request gate sits in `gate.py` beside the answer gate and shares the answer-limit and reserved-term checks. `gate.py`, `decide.py` and `requests_text` stay pure, and the I/O goes into two new modules and the stage. The request limit is per provider across askers, matching the architecture. Refusals are declines with distinct reasons. The deterministic outside-program check guarantees that a non-member never produces a request, whatever the model replies.

### [PASS] Scope is proportionate to the slice plan

No extra `program-blocked` row is added, since 183 and 184's rows already cover the wait (D12). There is no separate request step and no extra model call (D1). `finish.py` only gains a branch. Deferred items (cycle checks across three or more members, merging duplicates, separate checkouts) are explicitly left out as the architecture directs. The `program_requests` passage is the one scope item that could be slimmed (see the concern above).

### Run Digest

- Response length: 6238 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 107153 / 11162 / 95987 / 4660 / not computed
- Duration: 41.9 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
