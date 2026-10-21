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
reviewedSha: 78977debffee544e0a8056bae3ddeecfd6f61840
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 150693
cachedTokens: 100361
cacheWriteTokens: 50328
completionTokens: 8207
durationSeconds: 68.8
costUsd: 0.239896
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Core batch model matches the architecture's \"Dispatch granularity\" decision"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#Overview"
  - id: F002
    severity: concern
    category: architectural-boundaries
    summary: "Paused-batch handling diverges from the architecture's pause model without a sourced justification"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D4, D8"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Design is heavier than the slice needs; cuttable scope is identifiable"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D6, D9, Development Approach"
  - id: F004
    severity: note
    category: alignment
    summary: "Pointer-write omission is a documented deviation from the architecture's dispatch rule"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D4"
  - id: F005
    severity: note
    category: error-handling
    summary: "New-pipeline launch failure stops the whole resident process"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D4"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure modes for the new I/O paths are enumerated"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D5, D6, D9"
---

# Review: slice — slice 130

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Core batch model matches the architecture's "Dispatch granularity" decision

The slice implements what 120 sets out for batch dispatch:
- one dispatch (`slices-plan`) with per-item outcomes from the batch report's `items[]`;
- outcomes mapped onto per-slice nodes;
- the Runner acting only at flagged items;
- per-item resume carrying the resolution's decision.

Other points that hold up against the architecture:
- **Scope:** `slices-plan` only, as the architecture's "After the first proof" list says.
- **Observation surface:** the public report file, not the run-state file.
- **Routing:** the shipped table gains no rules, and the catch-all escalates every new outcome value. That fits "before 140, every such point routes to a human."
- **Dependency direction:** correct. Store contract changes land first, as in 122 D3 and 125 D10.
- **Atomicity:** `record_batch_report` writes the whole batch in one transaction and uses digest-based verdict ids, so a crash retries safely.

### [CONCERN] Paused-batch handling diverges from the architecture's pause model without a sourced justification

Three points depart from the architecture's pause rules.

1. **No `blocked_on_sq_checkpoint`.**
   - The architecture says a paused run becomes a `blocked_on_sq_checkpoint` node holding its run id.
   - Under D6 and D8, a paused item (`flagKind: paused`) is just another `flagged_item` blocked on `HUMAN`.
   - 127 D2 refuses `retry` at an interactive checkpoint, because a non-TTY resume re-pauses. `flagged_item` allows `retry` for every flagged record with no such refusal.
   - The only safety net is a post-hoc `resume_failed` after a paid launch.
   - D8 should either refuse `retry` for `flag_kind: paused`, or state why Squadron's per-item resume does not re-pause.
2. **Checkout hold released on a paused run.**
   - The architecture holds a checkout "until its run is no longer running or paused."
   - D4 releases the hold on the claim "a planning batch leaves no slice branch checked out." That claim is not tied to a Squadron source, unlike other Squadron facts in the doc.
   - If a paused item leaves the tree dirty or on a branch, another dispatch in that checkout would collide. Cite the source, or keep the hold while any item is `paused`.
3. **Ambiguous "answered with `rerun`".**
   - D8 says "Items with no record are answered with `rerun`," with no actor named.
   - Read as the Runner choosing automatically, it breaks the architecture's rule that unknown escalates, and that only the table or a PM decision picks a route.
   - It should say these items block on a human and `rerun` is an allowed decision.

### [CONCERN] Design is heavier than the slice needs; cuttable scope is identifiable

The design rates itself 4/5 against the plan's 3 and adds a store module, a new observer, two journal kinds and five Runner modules. Two pieces handle cases that D3's exactness rule makes reachable only through selection drift:
- **D6 row 4 (record for an unpredicted slice that has a node).**
  - It writes an item entry, verdicts and a block on a slice nobody drove.
  - The `batch_selection_mismatch` escalation already tells the PM.
  - Cut this to the escalation plus the review recording that attribution requires. Skip the routing and block machinery on an undriven step.
- **D9 recovery branches.**
  - The three-way recovery (`record_before` comparison, log-file absence giving `not_applied`, and `Unknown`) is elaborate for an operation the design itself says can move to a follow-on.
  - A simpler recovery after restart is a changed record means finished, otherwise `Unknown` escalates. `handled` then recovers it, and S14 removes the case. This drops the log-existence inference.

Neither cut loses a requirement from the architecture, which asks only for per-item resume with the resolution's decision.

### [NOTE] Pointer-write omission is a documented deviation from the architecture's dispatch rule

The architecture says the Runner sets CF's pointers itself (a journaled `cf_write`) before dispatching a node. It also says a pointer moved away from a node with a run in flight raises a project-scoped escalation. D4 drops both for batches: Squadron's `each` step moves the pointer, and the pointer-move check skips batch entries. The reasoning holds, and the checkout is still verified by a read. The cost is that a human moving the pointer mid-batch is undetected. The architecture's "Where each value lives" lists only the merge policy under per-project config. `design_dispatch` extends that list, and the architecture text should be updated when this lands.

### [NOTE] New-pipeline launch failure stops the whole resident process

The architecture makes a launch exit 2 stop the resident process. `slices-plan -p plan=` cannot be probed at start, so an upstream parameter change would stop every project on the first batch launch. The behavior is inherited from 122 and is deliberate. The operator guide could mention it alongside the opt-in, since batching is the first non-`P4` launch shape.

### [PASS] Failure modes for the new I/O paths are enumerated

- **Report read:** missing, unreadable, wrong schema, mismatched ids and out-of-set values all become `ReportUnknown`, and every predicted item goes to `unknown`.
- **Plan read before ingestion:** a failed read retries on the next tick, then escalates after the launch grace period.
- **Item resume:** a table covers exit codes 0, 1, 2 and 3, an unchanged record, and a child that is still running.
- **Restart mid-resume:** the recovery cases are listed.
- **Time bound:** the per-item bound is multiplied across the batch.

### Run Digest

- Response length: 6280 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 150693 / 100361 / 50328 / 8207 / not computed
- Duration: 68.8 s
- Cost: $0.24 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
