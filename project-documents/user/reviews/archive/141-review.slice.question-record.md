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
reviewedSha: fe1fd22bffcc73129882c9589d15dae1459c12ae
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 103786
cachedTokens: 11162
cacheWriteTokens: 92620
completionTokens: 4668
durationSeconds: 43.1
costUsd: 0.419123
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: concern
    category: integration
    summary: "\"Answered by the PM\" is decided structurally, but the architecture defines it as a resume"
    location: "project-documents/user/slices/141-slice.question-record.md#D2 — \"Answered by the PM\" is decided inside `acknowledge_resolution`, from the record"
  - id: F002
    severity: concern
    category: error-handling
    summary: "The ingest failure path for `record_question` is not stated"
    location: "project-documents/user/slices/141-slice.question-record.md#API Contracts"
  - id: F003
    severity: note
    category: scope
    summary: "The architecture's list of changes to 132-owned code is now incomplete"
    location: "project-documents/user/slices/141-slice.question-record.md#D1 and #D2"
  - id: F004
    severity: note
    category: proportionality
    summary: "Proportionality: the slice is sized acceptably, with some optional trimming"
    location: "project-documents/user/slices/141-slice.question-record.md#D6, #D7, #D8"
  - id: F005
    severity: pass
    category: architecture
    summary: "Layering, dependency direction and vocabulary ownership match the architecture"
    location: "project-documents/user/slices/141-slice.question-record.md#Architecture"
  - id: F006
    severity: pass
    category: integration
    summary: "Failure modes and integration contracts for 142–144 and 160 are explicit"
    location: "project-documents/user/slices/141-slice.question-record.md#Integration Points"
---

# Review: slice — slice 141

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] "Answered by the PM" is decided structurally, but the architecture defines it as a resume

The architecture says a question counts as answered by the PM "only when its block was resolved by a resume that did not come through that operation". Slice D2 deliberately does not read the decision. It marks the record `answered` (pm) on any acknowledgment that is "applied and no new block". That is equivalent to the architecture's rule only if 127's resolution decisions that unblock a node are all resumes. The slice never enumerates 127's decisions.

If 127 has an applied decision that unblocks without resuming (an abandon or skip, for example), the record would be marked `answered` by the PM with a null answer. The question would then be terminal and would never be declined or answered. The Risk section covers only a third acknowledgment shape that neither re-blocks nor unblocks. It does not cover an unblocking shape that is not a resume.

Fix: list 127's decisions in D2 and state that each one that unblocks is a resume. Alternatively, add the non-resume unblock to the acknowledgment-shape test with its expected record result. Without this, a requirement the architecture states is left unmet.

### [CONCERN] The ingest failure path for `record_question` is not stated

`record_question` can raise `NodeNotFoundError` (missing node) or `InvalidTransitionError` (done node). Ingest now calls it in place of `block_once`, and the slice does not say what ingest does when it raises.

The slice does cover crash retry, the already-blocked node, and a fault in the stage. It does not say whether a raise leaves the journal entry unresolved and retries every tick, or is reported through per-project escalation. A permanent error on a done node could repeat forever, or a question could be dropped without a record. The architecture's "question record is never skipped" depends on this being explicit.

Fix: add one sentence naming the ingest behavior and whether it matches what `block_once` did for the same node states.

### [NOTE] The architecture's list of changes to 132-owned code is now incomplete

The architecture says there are "three changes to 132-owned code". 141 also:
- changes ingest's block write path;
- changes `ProjectTick` ordering;
- adds a step to 127's `acknowledge_resolution`;
- alters one retry behavior (D1, the PM resolving the block between a crash and the retry).

The architecture's "record is the memory" principle authorizes the acknowledgment change. The D1 behavior change is called out clearly in the slice and is reasonable. The architecture's sentence should be reconciled so later slices don't rely on a stale list.

### [NOTE] Proportionality: the slice is sized acceptably, with some optional trimming

Most of the surface traces to an architecture requirement or the slice plan: the record, the `answerer` section (needed for `answerer_not_configured`), the decline state, the blocked-listing columns, and the feed kinds that 160 attaches to. Small items could be deferred without leaving a requirement unmet:
- the `QUESTION_CELL_CHARS` table truncation;
- the `question_recorded` feed kind, if 160 only needs `question_state_changed`;
- the `answerer:` null-value load error, if the load path already rejects non-mapping values generically.

None of these needs to block progress. The seven-step approach and effort rating of 3 are reasonable.

### [PASS] Layering, dependency direction and vocabulary ownership match the architecture

The record lives in 100's store. `settle_pending` is pure and the stage is store-only. The Runner reads store enums and never writes literals. The block stays `HUMAN` with an unchanged payload (D1, byte-identical test). The stage sits after ingest and before the act and `CUT_OFF` steps, as the architecture's tick order requires. The slice incorporates the architecture's revised "queue" step, where the acknowledgment settles a PM-resolved block (D2, D5). The `answered_by` and `answered`-terminal semantics match the architecture's "PM answered first" note.

### [PASS] Failure modes and integration contracts for 142–144 and 160 are explicit

The slice covers:
- crash between record and report (idempotent on `source_entry_id`, with a crash-harness test);
- a node already blocked (declined record, no link);
- a stage fault (per-project escalation, with the reason the node context is cleared);
- PM resolutions that are rejected or are a `stop` (re-point, state unchanged);
- the race with the answerer (skip, then acknowledgment).

Provides and Consumes name the transitions, `QUESTION_TRANSITIONS`, the precedent predicate for 143 and the feed kinds for 160. The architecture states no latency or throughput NFRs for this path, and the stage takes no tick budget, so no NFR restatement is needed.

### Run Digest

- Response length: 5544 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 103786 / 11162 / 92620 / 4668 / not computed
- Duration: 43.1 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
