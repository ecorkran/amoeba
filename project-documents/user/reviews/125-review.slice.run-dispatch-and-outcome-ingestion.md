---
docType: review
layer: project
reviewType: slice
slice: run-dispatch-and-outcome-ingestion
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: df5dc64b9459d5afc7b90d9382f85f2ac4debdc0
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 431932
cachedTokens: 318782
cacheWriteTokens: 113140
completionTokens: 7553
durationSeconds: 69.6
costUsd: 0.560795
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: proportionality
    summary: "Overweight for one slice: two separable mechanisms and heavy restated material"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#Implementation Notes"
  - id: F002
    severity: concern
    category: scope
    summary: "Per-pipeline time bound deferred out of the slice that the plan assigned it to"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#D12"
  - id: F003
    severity: concern
    category: architecture-alignment
    summary: "Clean-tree dispatch precondition is skipped, and the mitigation is only procedural"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#Risk Assessment"
  - id: F004
    severity: concern
    category: contract-ordering
    summary: "Evidence-contract change is binding on the Runner but lands last"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#D7"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Failure handling for a timed-out `cf set` is implied, not stated"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#D2"
  - id: F006
    severity: note
    category: architecture-alignment
    summary: "Hold lifecycle and pointer-claim lapse add complexity but match the architecture's intent"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#D4"
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "Layering, dependency direction and NFR restatement"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#Architecture"
---

# Review: slice — slice 125

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Overweight for one slice: two separable mechanisms and heavy restated material

The slice carries the contract changes to 100, a new migration, a detection refactor and a new `cf_write` key. It adds the pointer-move check (D11), the `not_applied` reissue (D9), and edits to five contract documents. Only two of these are separable, and the slice's own "If the slice overruns" paragraph says so.
- **Reissue (D9).** Plan entry 6 does not assign it. The plan text names only issue #10, and the only `not_applied` match in the plan is in Foundation Work (line 38).
- **Pointer-move check (D11).** Plan entry 6 does assign it. Moving it out would need a plan edit, the way D12 did. It also needs its own `pointer_watch.py`, a project-scoped escalation with a deduplication limit it admits to, and a `FaultKind`.

Both mechanisms can come out. Without D9, a `REISSUE` step blocks on `HUMAN`, which the slice already says is safe. Without D11, the move goes unescalated for now.

Prose that can be cut:
- The Special Considerations list of plan and architecture edits restates edits that are already committed.
- The "Interfaces Required" Squadron and CF field catalogs repeat what the contract documents will hold.
- The rejected-alternative bullets in D7 and D8 repeat the decisions above them.

I suggest cutting or deferring D9 and D11 and trimming the restatements.

### [CONCERN] Per-pipeline time bound deferred out of the slice that the plan assigned it to

The architecture says a run that never ends hits a per-pipeline time bound, after which the node escalates. D12 moves that bound to 126. Plan entries 6 and 7 are already edited to match, and the architecture text at line 133 points to D12, so the plan and architecture are consistent. The deferral is still real. The first production planner ships with no bound, and a hung run holds its checkout indefinitely. The Risk Assessment says this and offers only "visible in `inspect journal --unresolved`" as mitigation. The slice should say what stops the planner launching production runs between this slice's merge and 126. It should also confirm that plan entry 126 carries the `started_at` input it relies on (it records `started_at` here).

### [CONCERN] Clean-tree dispatch precondition is skipped, and the mitigation is only procedural

The architecture says the Runner dispatches only if the tree is clean and on the target or the node's slice branch. This slice puts `DispatchPlanner` in the production tuple (step 7) without that check. The stated mitigation is that the Runner "is driven only on scratch copies or checkouts the PM is not working in". That is a convention and nothing enforces it. The plan ordering gives the check to 128, so the gap is intentional. The design should still say what limits the exposure in the meantime: a PM drive is the only trigger, and the pause intent stops launches.

### [CONCERN] Evidence-contract change is binding on the Runner but lands last

D7 changes the evidence contract's rule for where a Runner journals a review command. The run is journaled on the step node, the verdict goes on the slice node, and `journal_entry_id` is null. The architecture says "where the Runner needs something the contract lacks, the contract changes first". D10 puts the code-level contract changes first. The evidence-contract text for D7 and the process-contract text are only updated in step 7, after the dispatch and ingest code. Move the evidence-contract wording change into step 1 with the D10 contract tasks.

### [CONCERN] Failure handling for a timed-out `cf set` is implied, not stated

D2 covers a non-zero `cf set`, a cut-off between the set and the read-back, and each read-back failure. It does not say what happens when `cf set` itself exceeds `tick_call_timeout_seconds`, where the write may or may not have landed. The cut-off rule probably covers it. If so, a write that did not land will read back as a different index and block as `pointer_write_failed`, not retry. State that outcome explicitly, and also say whether the launch-log read (D9) and the review-file read (D7) have a size bound.

### [NOTE] Hold lifecycle and pointer-claim lapse add complexity but match the architecture's intent

Starting the checkout hold at the pointer write departs from the architecture's "held from launch". The slice states the departure and gives the matching architecture edit. The lapse rule (a claim ends when the step stops being current) and `POINTED` revalidation by a per-tick `cf get` are an extra mechanism, though they are bounded by `TickBudget`. They are justified by the shared-pointer hazard, so I raise no finding.

### [PASS] Layering, dependency direction and NFR restatement

The Runner writes through 100's public store API, and contract changes to 100 are landed first, following 122's precedent. Decide stays pure: the planner, `dispatch_state`, `resolve_checkout` and `pointer_moved` do no I/O. Every `cf` and `sq` call in the dispatch path goes through `TickBudget`, which restates the architecture's tick-never-waits requirement, and a test asserts it. Unknown values escalate (`ReviewUnknown`, `checkout_unresolved`, absent read-back fields). Verdict ids are content digests, which matches the corrected "Run identity" text. The slice states what it provides to 126, 127 and 128 and what it consumes from 120 through 124.

### Run Digest

- Response length: 6710 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 431932 / 318782 / 113140 / 7553 / not computed
- Duration: 69.6 s
- Cost: $0.56 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
