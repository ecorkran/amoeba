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
reviewedSha: be114b706bc5a0281c9424b2e9d726d20158defb
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 214692
cachedTokens: 108089
cacheWriteTokens: 106597
completionTokens: 8188
durationSeconds: 69.1
costUsd: 0.519895
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: architectural-boundary
    summary: "A paused run with an unknown review stops holding its checkout"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md:254-258, 302-307"
  - id: F002
    severity: concern
    category: integration
    summary: "The `POINTED` claim can go stale, and the hold starts earlier than the architecture says"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md:246, 258-260, 467-469"
  - id: F003
    severity: note
    category: scope
    summary: "Moving the per-pipeline time bound to 126 fits the architecture and the slice plan"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md:370-373"
  - id: F004
    severity: note
    category: error-handling
    summary: "One open `pointer_moved` per project can hide a second moved node"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md:359-361"
  - id: F005
    severity: note
    category: layering
    summary: "Contract changes to 100 are bundled into this slice"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md:336-354"
  - id: F006
    severity: note
    category: proportionality
    summary: "Size is high, but each piece traces to the architecture or plan"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md:595"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Failure modes and NFRs are explicit on the new I/O paths"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md#Technical Decisions"
---

# Review: slice — slice 125

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] A paused run with an unknown review stops holding its checkout

The architecture says a checkout is held "until its run is no longer running or paused", because a paused run still has its slice branch checked out. D4 takes that to mean "a node is `blocked_on_sq_checkpoint` and its latest `sq_run` entry has that checkout". D7 then moves a paused run whose review is unknown to `blocked_on_human`, so the checkout-hold rule no longer sees it. The checkout is released while the paused run's branch is still checked out. Another slice can then write a pointer and launch a pipeline in the same working tree, which is the corruption the slice's Value section says it prevents.

The same path has a second gap. The architecture's resolution vocabulary (retry, accept, handled, stop) is defined for `blocked_on_sq_checkpoint` nodes. A paused run on a `HUMAN`-blocked node has no stated resume route for 127.

Fix: derive the hold from the latest `sq_run` entry's recorded outcome (`paused`), not from the block kind. Add a success criterion for the paused-plus-`review_unknown` case that checks the checkout stays held. State in "Provides to 127" how a paused run on a `HUMAN` block is resumed.

### [CONCERN] The `POINTED` claim can go stale, and the hold starts earlier than the architecture says

`POINTED` is derived from journal history, and D4 lets the claim lapse when a step stops being current. After a lapse, another slice may write the checkout's pointer. The first step is still `POINTED`, but CF's active slice is no longer its slice. "Provides to 128" says `POINTED` is "the point to check gates … before `LaunchRun`" and that after the pointer write "CF's active slice is the node's slice for the gate read". After a lapse, 128's gate read would see another slice's `activeSlice.status`, and nothing in this slice prevents that.

Either re-verify the pointer before a `POINTED` launch (a store read of the latest snapshot would do), or tell 128 that it must not rely on `POINTED` implying the pointer value.

The architecture also says a checkout is held "from launch", while D4 holds it from the pointer write. The "Arch edits" list in Special Considerations doesn't mention this. Add it to that list.

### [NOTE] Moving the per-pipeline time bound to 126 fits the architecture and the slice plan

D12 defers the time bound that the plan originally gave to 125. The architecture puts "per-pipeline time bounds" in the routing table, which is 126's. The plan's 126 entry already carries the criterion "A run in flight past its pipeline's time bound escalates, without being killed". The deferral is a reallocation, not dropped scope, so it isn't a CONCERN.

I couldn't read plan entry 6's body, so the departures from it in D11 (no `cf_updated_at` matching, project-scoped escalation) are checked against the architecture only. The architecture text already matches them.

### [NOTE] One open `pointer_moved` per project can hide a second moved node

The architecture dedupes project-scoped escalations on (project, fault kind). With runs in flight in two worktrees, a second moved pointer is invisible while the first escalation is open, because the payload names one `node_id`. This is acceptable in v1. Say it explicitly, or put all affected nodes in the payload.

### [NOTE] Contract changes to 100 are bundled into this slice

The `cf_write` keys, the `record_runner_report` signature, migration `011` and the routing-flag clearing all change 100's contract inside a Runner slice. The architecture says "the contract changes first". D10 meets that by making these the first code tasks, following 122's precedent. Each change traces to an architectural need: issue #10's bounded unrouted-work read, run-level attribution, and the worktree write rule. No change is needed.

### [NOTE] Size is high, but each piece traces to the architecture or plan

The slice is effort 4/5, with 12 decisions and three areas of change (dispatch, ingest, store). I found nothing to cut:
- The architecture requires reissue (D9), the pointer-move escalation (D11), block-by-outcome (D6), the one-pipeline-per-checkout hold (D4) and multi-part review recording (D7).
- The `merge=false` fixed value is minimal and defined once.
- The "Arch edits" list describes edits the architecture text already contains (the pointer rule, time bounds, verdict on the slice node). Those edits are done, so the list needs no further action beyond the hold-start item above.

### [PASS] Failure modes and NFRs are explicit on the new I/O paths

- **Pointer write (D2).** It covers `cf set` exiting non-zero, a cut-off between the write and the read-back, a read-back that fails (timeout, non-JSON), an index, path or worktree mismatch, and an unknown read-back going through `journal_escalate`.
- **Reissue (D9).** The launch-log check covers a log with the run id line, an unreadable log and no log. It also covers a state that appears before relaunch, and a run that appears between the check and the launch.
- **Review ingestion (D7).** Every unreadable or unattributable review maps to `ReviewUnknown`, and a crash mid-ingest is idempotent.
- **Tick NFR.** Every `cf` and `sq` call goes through `TickBudget`, with a test asserting it. This matches the architecture's tick-never-waits rule and its per-call timeout.
- **Unknown handling.** `CheckpointKind` and `FailureKind` keep raw text, so an unrecognized kind never fails a poll.

### Run Digest

- Response length: 6751 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 214692 / 108089 / 106597 / 8188 / not computed
- Duration: 69.1 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
