---
docType: review
layer: project
reviewType: slice
slice: question-record
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/141-slice.question-record.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: a016644bf0f5bbb51af2ddb7465af311cb53dc68
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 104481
cachedTokens: 11162
cacheWriteTokens: 93315
completionTokens: 3881
durationSeconds: 36.5
costUsd: 0.414033
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Alignment with the architecture's catch, queue and PM-answer steps"
    location: "project-documents/user/slices/141-slice.question-record.md#Technical Decisions"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for the new write paths"
    location: "project-documents/user/slices/141-slice.question-record.md#D1 — The record is written in the block's transaction, keyed by its journal entry"
  - id: F003
    severity: concern
    category: proportionality
    summary: "`block_closed` decline branch handles a case the slice itself shows cannot occur"
    location: "project-documents/user/slices/141-slice.question-record.md:123-124 (Data Flow, settle) and D3 `DeclineReason`"
  - id: F004
    severity: note
    category: architecture-alignment
    summary: "Transition table admits `pending → answered (answerer)`, which the architecture does not"
    location: "project-documents/user/slices/141-slice.question-record.md:163 (State Management table)"
  - id: F005
    severity: note
    category: proportionality
    summary: "Listing surface is wider than the architecture's \"view of questions and answers\""
    location: "project-documents/user/slices/141-slice.question-record.md#D8 — Listings: `questions` is new, and `blocked` gains two columns"
---

# Review: slice — slice 141

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Alignment with the architecture's catch, queue and PM-answer steps

- **Catch (arch step 1):** D1 writes the block and the record under one `BEGIN IMMEDIATE`, keyed by `source_entry_id`. It declines at once with `node_already_blocked` when the node is already blocked, and never skips the record.
- **Queue (arch step 2):** D5 declines `answerer_not_configured` and `question_missing`. When the PM has already resolved the block, it skips the record and leaves it for the acknowledgment.
- **PM answer (arch step 7):** D2 marks the record `answered` by the PM inside `acknowledge_resolution`. It never reads `submitted_by`, which is the arch's "who answered is a field, not a label" rule.
- **Precedent:** a resume without instructions leaves a null `answer`, which matches "a resume without instructions is not precedent".
- **Dependency direction:** `settle_pending` is pure. The store owns the vocabularies, and the Runner imports the store and not the reverse.
- **Scope boundary:** 142–144 keep their writers, columns and config keys.

### [PASS] Failure modes are enumerated for the new write paths

- **`record_question` errors:** they propagate to the tenant boundary, 122's per-project escalation fires, the entry stays unresolved, and the next tick retries.
- **Crash between `record_question` and `record_runner_report`:** covered by the idempotency key and a crash-harness test.
- **Stage fault:** D5 clears the node context so the escalation is per project and deduplicated.
- **Illegal transitions:** they raise `InvalidTransitionError` and the transaction rolls back.
- **Architecture NFRs:** the architecture states none for this path, so nothing needs restating.

### [CONCERN] `block_closed` decline branch handles a case the slice itself shows cannot occur

- **The branch:** the slice adds the decline reason `block_closed` and a `settle_pending` branch for a record that is still `pending` when its block is resolved and no longer awaiting the Runner.
- **Why it cannot occur:**
  - D2 says an applied resume marks the record `answered` in the acknowledgment's transaction.
  - A rejection or a `stop` re-points the record to a new open block.
  - The only other way to unblock is an applied `StatusEffect`. The slice states the judge never produces one, and it is only a hypothetical test case.
- **Not in the architecture:** the arch's queue step (2) lists only "answerer not configured", "block resolved, run does not start" and "no text". It has no `block_closed` reason.
- **Cost:** a vocabulary member, a branch, a decline path and tests, all for an unreachable state.
- **Suggested change:** cut `block_closed`. If the PM wants a guard against a stuck `pending` record, make that state fail loudly with `InvalidTransitionError` or a store-invariant error. Do not add a decline reason that 142–144 and 160 inherit.

### [NOTE] Transition table admits `pending → answered (answerer)`, which the architecture does not

The architecture's flow has the record pass through `answering` before the answerer's resolution (steps 3, 6). The table also lets 142's submission go from `pending` straight to `answered`. 142 does not need that edge, because the answering run (144) is the only caller and it always goes through `answering`. Dropping the edge would make `QUESTION_TRANSITIONS` match the architecture exactly. This does not block progress, and it is for 142's design to settle.

### [NOTE] Listing surface is wider than the architecture's "view of questions and answers"

`--json` and the server carry extra fields (`blocked_state_id`, `source_entry_id`, `updated_at`, `question_id`). 143 needs `updated_at`, so that one is justified. The rest are cheap because the listing registry derives them, so I raise no finding. Check that each extra field has a consumer before it is committed to the JSON contract.

### Run Digest

- Response length: 4970 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 104481 / 11162 / 93315 / 3881 / not computed
- Duration: 36.5 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
