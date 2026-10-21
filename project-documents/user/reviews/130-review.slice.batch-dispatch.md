---
docType: review
layer: project
reviewType: slice
slice: batch-dispatch
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/130-slice.batch-dispatch.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: 44f1f1d056ee1f3a82bbe1a0ac09a79e1db05fda
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 211048
cachedTokens: 106396
cacheWriteTokens: 104646
completionTokens: 3796
durationSeconds: 34.6
costUsd: 0.330687
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: proportionality
    summary: "Overweight design: per-item resume machinery that the design itself says can be cut"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D9 — The item resume: journaled, observed and recovered by its record"
  - id: F002
    severity: concern
    category: nfr
    summary: "Per-item time bound has no specified value, and the NFR path is left open"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D7 — Time bound (126, D7)"
  - id: F003
    severity: concern
    category: architecture-alignment
    summary: "Arch edits are required, and the design departs from three arch rules"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#Special Considerations"
  - id: F004
    severity: concern
    category: failure-modes
    summary: "Checkout hold during a paused batch can strand the project indefinitely"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D4 — What batch entries do not do"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Failure modes for the new I/O paths are partly implicit"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D6 — Ingestion fans a batch out to its item steps"
  - id: F006
    severity: concern
    category: dependencies
    summary: "Selection prediction duplicates Squadron's predicate, with a known drift path"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D3 — A batch is issued only when its selection is exactly the driven set"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Sections restate other documents"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#Interfaces Required"
  - id: F008
    severity: pass
    category: architecture-alignment
    summary: "Layer boundaries and dependency direction"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#Architecture"
  - id: F009
    severity: pass
    category: scope
    summary: "Plan scope is covered, and the deferral is recorded"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D1 — Only `slice_design` is batched, with `slices-plan`"
---

# Review: slice — slice 130

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Overweight design: per-item resume machinery that the design itself says can be cut

The slice plan entry sizes this at 3/5. The design raises it to 4/5 and says the plan "did not count the store kinds and the item-resume observer". D9 adds a whole lifecycle: the `sq_item_resume` kind, an exit-code/record observation table, tracked and untracked child handling, a recovery observer, a `record_before` comparison, and an `ObserveItem` action. The "If the slice overruns" note says steps 1–4 are a complete, safe slice. Without step 5, `rerun` and `stop` already work through 127's `ended_run`. The plan entry does name per-item resume, so cutting it outright would drop assigned scope. The cut that fits the plan entry is a lighter version of it:
- Launch the resume, observe it only through the report record changing, and escalate on any ambiguity.
- Drop the tracked-child exit-code table, which has four rows and a stderr-tail path.
- Drop the separate recovery observer.
- Drop `ObserveItem`'s "record changed" skip logic as a separate action.

If the full mechanism stays, the design should say why a lighter one does not meet the requirement. The effort estimate should also be reconciled with the plan entry through a plan edit, not only in prose.

### [CONCERN] Per-item time bound has no specified value, and the NFR path is left open

The arch requires a per-pipeline time bound in the routing table, and an overrun always raises a project-scoped escalation. D7 sets `per_item: true` for `slices-plan`, multiplies by the number of predicted items, and says the value is "set at implementation from 129's observed `P4` durations". It also relies on `slices-plan` using different models than `P4` (D2), so `P4` durations are a weak proxy. No target is stated, so a batch of N undesigned slices has an unbounded detection delay until implementation. The design should state the derivation rule, or the interim value, in the slice document. It should also say what bound applies if 129 has no usable `P4` timing. The same applies to an item resume's bound ("the per-item value"), which is used for a different workload (one item).

### [CONCERN] Arch edits are required, and the design departs from three arch rules

The design departs from the arch's explicit dispatch rules in three places, and the arch edits are deferred to "before merge":
- **Pointer rule.** The arch says the Runner sets CF's pointers itself with a journaled `cf_write` before dispatching a node. D4 writes no pointer.
- **Pointer-move rule.** The arch says a pointer moving away from a node with a run in flight raises a project-scoped escalation. D4 skips batch entries, and the design accepts that a person moving the pointer mid-batch goes undetected.
- **Per-project config.** The arch lists only the merge policy there. D2 adds `design_dispatch`.

The arch's Technical Considerations paragraph says "Which lifecycle steps may be dispatched as a batch, and the mapping from report items to nodes, are slice design's." That gives license for the step choice and the item mapping, but not for dropping the pointer and pointer-move guards. The design should make the arch edits a named task in the breakdown, not a note. It should also consider keeping the pointer-move check running for batches. The check could compare against Squadron's own movement, but the design does not show why that is infeasible, only that the batch moves the pointer itself.

### [CONCERN] Checkout hold during a paused batch can strand the project indefinitely

A paused batch holds its checkout until a poll shows the run is no longer `paused`. The Runner never issues a whole-run resume (D8), so only the PM resuming by hand or removing the run releases it. This matches the arch's "a paused run stops that project until the PM handles it". But a batch pause is also the case where later items have no record. D8 then offers those items only `rerun` and `stop`, and `rerun` needs `NEEDS_POINTER` in the very checkout that is held. As written, `rerun` for an unreached item is offered but cannot run until the PM acts on the run outside the Runner. The design should say whether `rerun` is hidden or deferred while the checkout is held, and what the PM sees. As it stands, the hold and the offered decisions conflict.

### [CONCERN] Failure modes for the new I/O paths are partly implicit

Several paths are enumerated well: report unknown, plan read failure with grace, and exit codes 0–3 for the resume. These gaps remain:
- **Report read.** A report file that exists but is mid-write is unlikely, since the write is atomic. But a report read that exceeds the tick budget, or a very large `items[]`, has no stated handling. D6 says the plan read runs "under `TickBudget`" and says nothing about the report load or `record_batch_report`'s single transaction size. The transaction covers every item's verdicts and ledger rows.
- **Resume child that hangs.** The tracked-child table has a row for "still running", but the bound is only "the per-item value" from D7, which is unset (see above). A resume that never exits has no stated end except the time-bound escalation.
- **Host death during the report read between `record_batch_report` and acknowledgment.** This is covered by the crash test. It is named only in the success criteria.

Put an explicit failure table beside D6 and D9 (path, failure, handling) so none of these is implicit.

### [CONCERN] Selection prediction duplicates Squadron's predicate, with a known drift path

`predicted_selection` re-implements Squadron's `undesigned_slices` from the status exclusions (`complete`, `deferred`, `deprecated`) and `designFile`. The arch says "The Runner does not gate on upstream version numbers; it depends on shapes". Here the Runner depends on Squadron's internal selection logic, which is not a documented public shape. D3 and D6 catch a mismatch after the fact (`batch_selection_mismatch`), and the work was already done, unattended and paid. This is a hidden dependency. Two ways to keep it in bounds without more mechanism:
- State the pinned squadron-ai version in the opt-in documentation and make the contract test fail on a change to Squadron's status set.
- Treat S15 (the item filter) as the proper fix and say that `design_dispatch: batch` should stay experimental until it lands.

### [CONCERN] Sections restate other documents

"Interfaces Required" reproduces Squadron's report schema, exit codes, run-shape rules and item-resume semantics at length, and "Consumes from Other Slices" lists nearly every function from 122–128. Squadron's `docs/PIPELINES.md` already documents the report and its handoff contract. Cite it and keep only the fields the Runner routes on (`index`, `outcome`, `flagKind`, `reviewFile`, `finalVerdict`, `unsavedParts`). The "Provides to Other Slices" and "Technology Choices" sections are also mostly restatement. This shortens the design and leaves less to keep in sync.

### [PASS] Layer boundaries and dependency direction

The design keeps observe/decide/act intact: `selection.py` and `fan_out` are pure, `BatchPlanner` only emits actions, and Act journals before it launches. The batch is one `sq_run` entry observed by run id through 122's rules. Squadron is read only through its documented report and `sq runs wait`, and the internal run-state file stays unread. Routing still goes through the single table: the shipped table gains no rules, and the catch-all escalates every new outcome, which matches the arch's "before 140, every such point routes to a human". Store changes land first, as the arch requires of contract changes. The dependencies point from this slice to 122–129, and nothing upstream depends on it.

### [PASS] Plan scope is covered, and the deferral is recorded

The plan entry assigns `slices-plan` first, per-item mapping onto nodes, acting only at flagged items, and per-item resume with the decision. All four are present. The `tasks-plan` and `implement-plan` exclusions are justified (`implement-plan` is excluded because of 123 D4's sequential merge gate), and `tasks-plan` is added to the slice plan's Future Work as item 12, which the plan file confirms.

### Run Digest

- Response length: 9801 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 211048 / 106396 / 104646 / 3796 / not computed
- Duration: 34.6 s
- Cost: $0.33 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
