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
reviewedSha: d704c0ef59f97cbf0f7d777415882884323a89c3
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 115096
cachedTokens: 11266
cacheWriteTokens: 103826
completionTokens: 8044
durationSeconds: 64.4
costUsd: 0.497683
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Boundaries, routing authority and tick order match the architecture"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#Technical Decisions"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for the new I/O paths"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md:248-256, 280-296"
  - id: F003
    severity: concern
    category: scope
    summary: "Gate-disagreement criterion is deferred out of this slice"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md:298-304"
  - id: F004
    severity: concern
    category: under-specification
    summary: "The situation table is ambiguous for failed resumes"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md:194-202, 295"
  - id: F005
    severity: concern
    category: proportionality
    summary: "The design is heavier than the slice needs"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md:324-333, 413-414, 531"
  - id: F006
    severity: note
    category: dependencies
    summary: "Known pruning defect sits on this slice's main path"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md:76"
  - id: F007
    severity: note
    category: documentation
    summary: "Architecture edits listed in the design are incomplete"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md:205-212, 544-559"
---

# Review: slice — slice 127

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Boundaries, routing authority and tick order match the architecture

- **Routing and vocabulary.** `ResolutionDecision`, `Situation`, `ALLOWED`, `Continuation` and `ResumeFailure` are each defined once.
  - The accepted-CONCERNS case is handled by a new routing input and a table rule (D8), not a code branch. This honors "one edit point for routing".
- **Resolution stage.** It runs after intents and before Observe, as the architecture's loop describes.
- **Store access and inbox.** The store and inbox contract changes land first (D9), as "Respect the store's rules" requires.
  - The inbox does not import Runner vocabulary (D1), consistent with 124 D3.
- **Resume rules.**
  - A paused run is never restarted. `rerun` is absent from the `paused_run` set.
  - A missing run launches nothing.
  - Exit 2 on a resume escalates the node and does not stop the process.
  - `accept` is offered only when `is_loop` is true.
- **Performance targets.** The tick-never-waits obligations are restated with concrete handling.
  - The budget is checked before each `sq` call.
  - The pre-poll runs under `tick_call_timeout_seconds`.
  - Confirmation polls are paced by `run_poll_interval_seconds`.
  - The resolution stage starts no subprocess.

### [PASS] Failure modes are enumerated for the new I/O paths

- **Pre-poll.** The design handles four cases:
  - spent budget;
  - `PollFailure`;
  - `not_found`;
  - run not at the recorded pause.
- **Resume child.** The design handles five cases:
  - exit 2;
  - other exit;
  - never claims;
  - spawn error;
  - restart with no tracked child.
- **Crash points.** The design covers a crash between acknowledgment and journaling, and between journaling and launch.
- **Store failure and unexpected exceptions.** Both reach 122's one catch.
- **Poll failure during confirmation.** It is covered only by reference to 122's `run_observation_failed` and 126's time bound. That is adequate, but it could be one explicit sentence.

### [CONCERN] Gate-disagreement criterion is deferred out of this slice

- **What moved.** The plan entry for this slice assigns a criterion: an accepted outcome that CF's gate still fails is recorded on the node.
  - D7 moves it to 128 and edits the plan to match.
  - The architecture's accept text ("recorded on the node and shown to the PM") now points at 128's gate read as well.
- **The cost.** Until 128 lands, an accept advances the step and dispatches the successor with no disagreement recorded. The first signal is a Squadron refusal at the successor's run.
  - The design bounds this with "128 lands before 129" and scratch-only driving.
  - Dropping assigned scope is a CONCERN under the review criteria, however well argued.
- **Why the rationale holds.** `cf status --json` reports the gate only for the active slice, so the comparison cannot be made reliably at accept time.
  - The Project Manager should confirm the deferral. It should not stay a design-only edit.
- **What to do.** Keep the deferral, but record it as a named, dated plan change with the Project Manager's acknowledgment. Add an explicit entry-9 criterion that 128 cannot merge without.

### [CONCERN] The situation table is ambiguous for failed resumes

- **The conflict.** D2's `ended_run` row includes "a launch or resume failure", but D6 says a failed resume keeps `outcome: paused`.
  - D2's `paused_run` row keys on the recorded outcome being `paused`. Every resume failure except `run_missing` is therefore `paused_run`, which is what D6 intends.
  - Only `run_missing` yields `ended_run`.
- **The risk.** `classify` is pure and will be table-tested row by row. The overlapping rows leave precedence undefined.
  - A wrong reading would offer `rerun` on a paused run, which the architecture forbids.
- **What to do.** Restrict the `ended_run` row to resume failures whose recorded outcome is not `paused`. Alternatively, state the test order, as the document already does for `unexpected_state` and `outcome_not_routed`.

### [CONCERN] The design is heavier than the slice needs

- **The weight.** The slice is nine decisions, seven new columns, three store methods, four contract documents and a six-file subpackage.
  - It also edits 122, 125 and 126, and its effort estimate rose from 2 to 3.
  - Most of it traces to a requirement. These items can be cut or deferred:
    - **`runner_outcome_at`:** nothing in the design reads it.
    - **`amoeba inspect resolutions`:** `blocked_state(id)` already serves submitters.
      - The listing serves 128 and the 129 write-up, so defer it unless the plan entry assigns it.
      - Keep the `blocked_state_id` column on `inspect blocked`, which the PM needs.
    - **`unexpected_state` and `outcome_not_routed`:** both are reject-only situations with distinct codes but identical handling. One situation with a detail field would remove a row and a vocabulary member.
- **What to do.** Cut or defer these three, or state which requirement each one serves.

### [NOTE] Known pruning defect sits on this slice's main path

A paused run can be pruned while its resolution is pending (issue #14), because pruning holds runs by `sq.run_id` and the Runner never sets it. The design contains this by surfacing the pruned run as `run_missing`, which blocks the node and launches nothing. That matches the architecture's missing-resume rule. It should be fixed before real-project use.

### [NOTE] Architecture edits listed in the design are incomplete

Two behaviors go beyond the architecture's text, and the "Plan and arch edits" list does not name them:
- Rule 6 in D2 rejects `retry` at an interactive checkpoint, which the architecture's retry bullet does not exclude.
- "Any other blocked pipeline step: rerun or stop" is not in the architecture's resolution section.

Add both to the architecture edits so the document stays the source of truth.

### Run Digest

- Response length: 6987 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 115096 / 11266 / 103826 / 8044 / not computed
- Duration: 64.4 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
