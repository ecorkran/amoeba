---
docType: review
layer: project
reviewType: slice
slice: resolutions-and-resumption
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/127-slice.resolutions-and-resumption.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: c84763020e8bd215658ec62f5c750483cb63f2a7
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 113795
cachedTokens: 11266
cacheWriteTokens: 102525
completionTokens: 10918
durationSeconds: 91.3
costUsd: 0.521219
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Resolution vocabulary and boundaries match the architecture"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#Technical Decisions"
  - id: F002
    severity: concern
    category: data-model
    summary: "Rejection code lives only inside a free-text reason"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#D3 and #API Contracts (\"Learning the outcome\")"
  - id: F003
    severity: concern
    category: error-handling
    summary: "One bad resolution halts Observe for the whole project, against the arch's fault-isolation rule"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#D2 (last bullet) and #D3 (Store failures)"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Act's journal-then-poll order has unspecified failure paths"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#D4 (Act, in order)"
  - id: F005
    severity: concern
    category: scope
    summary: "Defers a criterion that plan entry 8 assigns to this slice"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#D7"
  - id: F006
    severity: concern
    category: proportionality
    summary: "Proportionality: some bundled work is separable"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#D9 and #Implementation Notes"
  - id: F007
    severity: note
    category: documentation
    summary: "Tick-order change is not in the arch edit list"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#Special Considerations"
  - id: F008
    severity: note
    category: robustness
    summary: "Timestamp comparison decides whether a resolution is newer than the latest entry"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#D5"
---

# Review: slice — slice 127

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Resolution vocabulary and boundaries match the architecture

- The closed decision set (D2) matches the arch's "Resolution and resumption" section.
- `rerun` is never offered for a paused run, as the arch requires.
- Instructions pass through as data and only on `retry` or `accept`.
- The inbox validates shape only and imports no Runner vocabulary (D1, following 124 D3).
- Dependency direction is correct. Contract changes to 100 land first (D9), and the Runner codes against them.
- The departures from the arch (stop held as a block, the `handled` journal entry, gate disagreement detected by 128) are named and carry matching arch edits.
- The design restates the arch's exit-2-on-resume rule correctly: the node escalates and the process does not stop.

### [CONCERN] Rejection code lives only inside a free-text reason

- The Runner's answer is stored as `runner_outcome` plus `runner_reason`, where the reason is the string `"<code>: <detail>"`.
- The slice advertises the rejection codes as part of the vocabulary for 160 and the notification bridge.
- Those consumers can only get the code by parsing a prefix out of display text. That is the "user-accessible label as logical structure" pattern the project rules forbid, and it is fragile if the detail format changes.
- The code is stored as a separate field in the stop and rejection block payloads (`code`, `allowed`), but not on the acknowledged row that submitters read.
- Fix: store the code in its own column (for example `runner_code`), or make `runner_reason` the bare code and put the detail elsewhere. This is cheap to change now because migration `012` is not yet written.

### [CONCERN] One bad resolution halts Observe for the whole project, against the arch's fault-isolation rule

- The arch says a fault on a node whose run is in flight must not stop that run from being observed and ingested.
- Here the resolution stage runs before Observe. Any non-store exception reaches 122's catch, and "the rest of that project's tick does not run."
- The resolution stays flagged, so the same exception recurs every tick. Observe never runs for that project, and no other in-flight run in it is ingested.
- `classify` deliberately raises `ValueError` for a blocked step with an unresolved latest entry. Reading the checkpoint from `outcome_document` can also fail on a malformed document. Only null `kind` or `paused_at` is covered, by `checkpoint_unknown`.
- That unparseable-document case is exactly where the arch's "unknown escalates" principle applies.
- Fix, either of:
  - Map an unreadable checkpoint or unexpected journal state to a rejection, so it is acknowledged and the node escalates.
  - Isolate failures per resolution, so the stage logs and skips that resolution while Observe still runs.
- Add a test that a poisoned resolution does not block another node's run from being ingested.

### [CONCERN] Act's journal-then-poll order has unspecified failure paths

- Act journals the continuation entry first, then pre-polls "under `TickBudget`". The arch requires the budget and per-call timeout to be checked before every subprocess call.
- If the budget is exhausted, or the poll times out or errors after journaling, the entry exists but nothing is launched.
- By the design's own rules (D6), the next ticks see the old pause still showing and fail the entry as `no_claim_within_grace`. A budget cut, which is routine, then turns into a `resume_failed` escalation. The PM must resubmit, and the retry's paid round is not run.
- The doc covers the crash case between journal and launch. It does not cover these non-crash paths.
- The pre-poll is also an extra `sq runs wait` call (about 1 second each, per the arch). It is not stated whether it respects `run_poll_interval_seconds`.
- Fix: check the budget before journaling, and say what happens on a pre-poll timeout or error. For example, resolve the entry as not issued, or leave the step in `RESUME`.

### [CONCERN] Defers a criterion that plan entry 8 assigns to this slice

- Plan entry 8 asks that an accepted outcome CF's gate still fails be recorded on the node. D7 moves that to 128.
- The reasoning is sound: only a CF gate read can detect it, and 128 owns that read.
- It is still a deferral of assigned scope.
- Until 128 lands, an accept advances the step in the store, and the successor is dispatched, with no record of any gate disagreement. The first sign is a later Squadron refusal.
- The "Special Considerations" list says plan entry 9 is edited to absorb the criterion. Confirm that edit exists and carries the criterion.
- The "identifiable accept" this slice provides (an applied `accept` on a `completed_outcome` step, plus the verdict ids) should be a stated acceptance criterion for 128. Today it appears only under "Provides".

### [CONCERN] Proportionality: some bundled work is separable

- The slice is rated 3/5 against a plan estimate of 2. It adds a subpackage, a migration, a new journal shape, two actions, a planner, a routing input and rule, observer and pruning changes, two CLI changes, and four contract documents.
- Most of this follows from the requirement. The **pruning held-set rewrite** (`run_pruning.py`, `cli/prune.py`, process-contract rule 3) does not belong to resolutions.
  - The doc itself says the held set reads `sq.run_id`, which "the Runner never sets". That is a defect in the existing 100/125 integration, and it already affects every paused run.
  - Under the project's fix rules this is an issue or `fix:`, not slice scope.
  - Cutting it removes a change to 100's pruning code, a contract-doc rewrite, and a test group from this slice.
- If the PM wants it kept here, say why resumption specifically requires it. The pending-resolution wait is the same as any paused wait.
- `amoeba inspect resolutions` is justified by 129 and D7. Keep it, but keep it minimal (no `--node` filter unless a consumer needs it).

### [NOTE] Tick-order change is not in the arch edit list

- The arch states a fixed per-project tick order: intents, observe and ingest, route, decide and act. This slice inserts a resolution stage after intents.
- The arch edit list covers "Resolution and resumption" and "Observe, decide, act", but not the tick-order passage in "The tick never waits" or the Envisioned State loop paragraph.
- Add that edit so the arch does not contradict the implemented order.

### [NOTE] Timestamp comparison decides whether a resolution is newer than the latest entry

- "Acknowledged after the step's latest entry was issued" compares `runner_outcome_at` with the entry's `issued_at`.
- In the normal flow the entry is journaled after the acknowledgment, so a tie resolves safely. Say whether the comparison is strict, and whether it uses store ordering or wall-clock timestamps, so clock resolution cannot flip it.

### Run Digest

- Response length: 8180 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 113795 / 11266 / 102525 / 10918 / not computed
- Duration: 91.3 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
