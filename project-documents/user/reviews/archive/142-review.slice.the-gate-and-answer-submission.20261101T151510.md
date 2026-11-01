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
reviewedSha: 98e1e258b0e45ec6fbfe166db6e1cc7020ea1937
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 316035
cachedTokens: 229232
cacheWriteTokens: 86795
completionTokens: 4037
durationSeconds: 34.4
costUsd: 0.411326
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Single-transaction submission and gate placement match the architecture"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D1 — The gate runs inside the submission transaction, passed in as a pure function"
  - id: F002
    severity: concern
    category: dependency-direction
    summary: "Store operation depends on runner-owned constants and vocabulary"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md:192-195"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Gate failure inside the write lock is not specified"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D1 — The gate runs inside the submission transaction, passed in as a pure function"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Some mechanisms can be cut or deferred"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md:219"
  - id: F005
    severity: note
    category: dependencies
    summary: "141 is a design-only dependency"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#Prerequisites"
  - id: F006
    severity: pass
    category: configuration
    summary: "Configuration, probe wiring and failure paths follow the architecture"
    location: "project-documents/user/slices/142-slice.the-gate-and-answer-submission.md#D7 — Two required configuration keys, no defaults"
---

# Review: slice — slice 142

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Single-transaction submission and gate placement match the architecture

`submit_answer` is one `BEGIN IMMEDIATE` operation in 100's store. It fills the slot, writes the submission row and marks the record, so the architecture's "the record is the memory" rule holds. Passing the gate in as a pure callable keeps the count read under the lock. The store holds no terms or limit. The outcomes `block_resolved` and `settled` match the architecture's "PM answered first" handling, where the acknowledgment marks the record answered by the PM. Excluding `apply_submission`, `acknowledge_resolution` and the judge from changes is consistent with the architecture.

### [CONCERN] Store operation depends on runner-owned constants and vocabulary

D5 has `submit_answer`, a store method, write `decision = ResolutionDecision.RESUME` and `detail = ANSWERER_DETAIL`. `ResolutionDecision` lives in `runner/resolutions/vocabulary.py`, and `ANSWERER_DETAIL` is defined in `runner/answering/gate.py`. The store's `_write_resolution` takes `decision` as a plain `str`, and no store module imports the runner today. The public signature `submit_answer(question_id, *, answer, instructions, submitted_by, gate)` has no `detail` or `decision` parameter, so the store would have to import from the runner. That reverses the dependency direction (the runner depends on the store, not the reverse). Resolve this one of two ways:
- Pass `detail` explicitly into `submit_answer`.
- Add a store-side constant for the `resume` decision, and have a test assert it equals `ResolutionDecision.RESUME`.

Name the choice in the API contract, since 144 is designed against that signature.

### [CONCERN] Gate failure inside the write lock is not specified

`submit_answer` calls a caller-supplied callable while holding the write lock. The crash tests cover injected SQL failures. They do not cover the gate raising, for example from a bad `partial` binding or a misconfigured `settings`. State that a gate exception rolls the transaction back, writes nothing, and propagates as a programming error. Add one test for it. The contract says only that the method "raises only on programming errors", which stops short of this case.

### [CONCERN] Some mechanisms can be cut or deferred

The following go beyond what the slice plan's success criteria require:
- The duplicate-term load error (D7), which the design itself calls "harmless to the gate".
- A dedicated index on `(project_id, run_id, answered_by)`. The count runs once per answer under the lock, and the design states no volume that needs the index.
- The `reserved_term` suffix in the `outcome` column of the `questions` listing. The slice plan only asks that the listing show state, question, answerer and outcome. The `reserved_term` column and the `declined` outcome already convey this.
- The "identical blocks" test in the Risk Assessment, which partly repeats the existing `apply_submission` suite and the resolution-judge tests.

Cutting the first three would reduce the slice's surface without losing anything the plan assigns it.

### [NOTE] 141 is a design-only dependency

The design is written against 141's unimplemented API and declares that its tasks follow 141's names. This is acceptable given the slice plan's build order. Re-check the names against 141 before the task breakdown.

### [PASS] Configuration, probe wiring and failure paths follow the architecture

`answer_limit` and `reserved_terms` are required with no defaults. An empty list is accepted only when written explicitly, and the probe runs only when an answerer section exists. All three match the architecture and the slice plan's Interfaces entry. The crash-injection tests cover the slot write, the submission insert and the record update. Race ordering between the PM and the answerer is enumerated for both orders, and the answerer's resolution being rejected by the Runner (D6) is handled explicitly.

### Run Digest

- Response length: 5191 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 316035 / 229232 / 86795 / 4037 / not computed
- Duration: 34.4 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
