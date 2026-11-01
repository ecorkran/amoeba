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
reviewedSha: 4202b61320438ed61ea1697f38f469120b8de619
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 103400
cachedTokens: 8813
cacheWriteTokens: 94583
completionTokens: 5875
durationSeconds: 54.8
costUsd: 0.43881
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: concern
    category: integration-points
    summary: "D2 makes `answered` terminal but 144's \"PM answered first\" discard has no defined path"
    location: "project-documents/user/slices/141-slice.question-record.md#D2 — \"Answered by the PM\" is decided inside `acknowledge_resolution`, from the record"
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency direction"
    location: "project-documents/user/slices/141-slice.question-record.md#Architecture"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes and crash safety for the new write paths"
    location: "project-documents/user/slices/141-slice.question-record.md#D1 — The record is written in the block's transaction, keyed by its journal entry"
  - id: F004
    severity: note
    category: proportionality
    summary: "`decline_detail` and the `answerer: {}` null-rejection are early"
    location: "project-documents/user/slices/141-slice.question-record.md#D3, #D6"
  - id: F005
    severity: note
    category: scope
    summary: "Feed kinds go beyond what the architecture lists"
    location: "project-documents/user/slices/141-slice.question-record.md#D7 — Question changes are on the feed"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Architecture rules honored: sources, precedent and `HUMAN` blocking"
    location: "project-documents/user/slices/141-slice.question-record.md#D2"
---

# Review: slice — slice 141

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] D2 makes `answered` terminal but 144's "PM answered first" discard has no defined path

The architecture says that when the PM resolves a block while an answering run is in flight, the run's result is discarded "in one transaction with the record's note that the PM answered first". The slice conflicts with this in two ways:
- D2 marks the record `answered` (pm) as soon as the Runner acknowledges the PM's resume, and the slice says `answered` is terminal. When the answering run later ends, 144 cannot move that record anywhere, because the transition table has no `answered → declined`. `decline_question` would raise `InvalidTransitionError`.
- D3 still lists `pm_answered_first` as a `DeclineReason` that 144 will add, and the transition table has `answering → declined`. That reads as though the PM-first outcome is a decline. Under D2 the record is already `answered` by then.

The slice does not say how 144 records a discarded answering result on an already-`answered` record. It also does not say whether `pm_answered_first` should exist.

The slice is the source of the record's lifecycle for 142–144, and its Provides section promises that they can be designed against it. So it should settle this now. One option is to drop `pm_answered_first` and state that 144's discard is a no-op against an `answered` record. The other is to define a record-only note path. Also record that this changes the architecture's step 2 and step 7 wording. The architecture still describes the stage settling a PM-resolved block as answered, and D2 explicitly moves that to `acknowledge_resolution`. The architecture should be updated to match.

### [PASS] Layering and dependency direction

- The store owns the vocabularies, SQL and transitions, and the Runner stage is store-only.
- `settle_pending` is pure.
- The block stays `HUMAN` and keeps 132's payload.
- The tick order matches the architecture: after ingest and before act, with fault isolation.
- The three 132-owned edits (outcome plan, ingest routing, `acknowledge_resolution`) are named and bounded.
- D5's per-project escalation avoids losing a fault on a node that is already blocked.

### [PASS] Failure modes and crash safety for the new write paths

- The block and record are written under one `BEGIN IMMEDIATE`.
- `source_entry_id` is unique, so a retry after a crash writes nothing twice.
- A kill inside `record_question` leaves neither the block nor the record, and a harness test covers it.
- Illegal transitions raise and roll back.
- The Risk section names the two shared-transaction edits and their mitigations.

### [NOTE] `decline_detail` and the `answerer: {}` null-rejection are early

No 141 writer sets `decline_detail`. Its only consumer is 142's matched reserved term, though it is a column, a parameter, and a listing field in 141. 144 already adds its own columns by a later migration, so 142 could add this one too. The `answerer` section is also empty in 141, which needs the null-value load error and its test. Both are small and justified, because the section's presence is what makes `answerer_not_configured` reachable. Cutting `decline_detail` is optional.

### [NOTE] Feed kinds go beyond what the architecture lists

The architecture names the decline state for 160 and the blocked listing, but not new `ChangeKind` members. The slice justifies them as the point 160 attaches to, and it cites the slice plan for that. I treat this as assigned scope. The cost is two triggers and an invariant-test step. Adding them later would cost a separate migration.

### [PASS] Architecture rules honored: sources, precedent and `HUMAN` blocking

- `answered_by` is a field read from the record, never from `submitted_by`.
- A resume without instructions is recorded as answered with a null answer, which matches the architecture's "not precedent".
- There are no hard-coded defaults.
- A project without an `answerer` section behaves as 132 does.
- A question on an already-blocked node is still recorded and declined at once, as the architecture requires.

### Run Digest

- Response length: 5122 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 103400 / 8813 / 94583 / 5875 / not computed
- Duration: 54.8 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
