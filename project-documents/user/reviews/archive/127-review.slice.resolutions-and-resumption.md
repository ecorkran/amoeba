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
reviewedSha: bf6b10be2a7d2dfd04791ccef45cb93785004820
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 115339
cachedTokens: 11266
cacheWriteTokens: 104069
completionTokens: 6702
durationSeconds: 55.0
costUsd: 0.485235
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Plan-assigned gate-disagreement criterion is moved out of this slice"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#D7 — Accepting an outcome CF's gate still fails is detected by 128"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Design is heavier than the plan entry, and its component list contradicts its own exclusions"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#Component Structure"
  - id: F003
    severity: pass
    category: architecture-alignment
    summary: "Boundaries and dependency direction match the arch"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#D1 — Decisions ride on the existing resolution kind"
  - id: F004
    severity: pass
    category: error-handling
    summary: "Failure modes and the tick-budget NFR are explicit"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#D4 — Continuation entries"
  - id: F005
    severity: note
    category: dependencies
    summary: "Pruning defect is a known prerequisite for 129"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#Technical Scope (Excluded)"
  - id: F006
    severity: note
    category: integration
    summary: "Bare resolutions of pipeline steps are now rejected"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#D2 — Situations and the allowed decisions"
---

# Review: slice — slice 127

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Plan-assigned gate-disagreement criterion is moved out of this slice

The slice plan entry for 127 asks that an accepted outcome CF's gate still fails be recorded on the node. D7 moves that criterion to entry 9 (128). The arch's "Resolution and resumption" section was edited to match, so the two documents agree. But the slice still defers scope the plan assigned to it, and the Runner has a gap until 128 lands.

- **Reason given:** only 128 reads the CF gate (`activeSlice.status` and `gateInfo`).
- **What 127 delivers:** an accept that can be identified later. It does not record the disagreement.
- **The window:** between 127 and 128, an accept advances the step and dispatches the successor with nothing recorded. The first signal is a Squadron refusal at the successor's run.
- **How it is bounded:** the document says 128 follows directly and lands before 129, and that the Runner is driven only on scratch copies until then. Plan entry 9 and issue #15 carry the criterion, and the plan Notes record the dated change (20261020).
- **Why it is still a CONCERN:** the deferral rests on a plan edit and an issue, not on anything in this slice. Before approval, confirm that entry 9 lists the criterion as required before 128 merges and lists 127's identifiable accept as its input. The design must not rely on prose alone to keep this from being dropped.

### [CONCERN] Design is heavier than the plan entry, and its component list contradicts its own exclusions

The plan sized this slice at effort 2. The design says 3/5. The growth comes from Squadron's resume behaviour, which is a legitimate cause, and the added mechanisms mostly trace to an arch requirement or a named risk. Two items can be cut or fixed:

- **Contradiction on `inspect resolutions`.**
  - The Component Structure lists `amoeba/inspection/ CHANGED resolutions listing; blocked gains blocked_state_id`.
  - Technical Scope excludes `amoeba inspect resolutions`, deferred to issue #16.
  - Remove "resolutions listing" from the component list so the implementer does not build it.
- **The `resume_skipped: run_not_at_pause` observation entry (D4 step 1).** It adds a third journal-entry flavor beyond resume and observe. It does address the named "resuming the wrong pause" risk, so I would keep it. The design should say the entry reuses the `observe` continuation path, so it needs no new planner state or confirmation rule. As written, D4 doesn't make that clear.
- **Rejection codes.** There are eight (`UNKNOWN_DECISION`, `DECISION_REQUIRED`, `DECISION_NOT_APPLICABLE`, `NOT_AT_LOOP`, `CHECKPOINT_UNKNOWN`, `INTERACTIVE_CHECKPOINT`, `INSTRUCTIONS_NOT_APPLICABLE`, `UNRESOLVABLE`). Every one is tested and consumed by 160's whitelist, so I do not recommend cutting any of them.
- **The "Plan and arch edits" list in Special Considerations.** It restates arch text that already contains those edits. Trim it to the plan edits that are still pending.

### [PASS] Boundaries and dependency direction match the arch

- **Inbox boundary:** the inbox validates only the shape of `decision` and `instructions`. The decision vocabulary stays in the Runner, so no Runner vocabulary is imported into the inbox.
- **Store contract:** the store holds `runner_code` as text. 100's contracts change first (D9, following 125's D10), and the Runner codes against them.
- **Table-only routing:** the Runner does not choose accepted-review routing in code. The slice adds the `review_accepted` input and one table rule (D8), which keeps the arch's "one edit point for routing" intact.
- **Resolution answers:** these are the closed set the arch defines. Anything else is rejected explicitly.
- **Stop:** the arch records that a stop is held as a block. This matches D3.
- **Interactive checkpoint:** a retry there is refused. This matches D2 rule 6.
- **Exit 2 on a resume:** the node is escalated rather than the process stopped. This matches the arch's Resume rule.
- **Tick order:** resolutions are acknowledged after intents and before Observe. This matches the arch's "loop, per tick" text.
- **Recovery:** a continuation with no run state is `Unknown` and never `NotApplied`, so a resume is never relaunched under the old id.

### [PASS] Failure modes and the tick-budget NFR are explicit

- **Pre-poll, in order:** budget spent, poll failure or timeout, `not_found`, run moved off the pause, and the `observe` case are each handled explicitly.
- **Journaling:** nothing is written until the pre-poll has answered and the budget allows the launch.
- **Resume failure:** D6 covers a child that exits 2, a child that exits with another code, a child that never claims (including after a restart), a spawn error, and a missing run. Each is decided on observed state and exit code, never on message text.
- **Crash points:** two are covered, after acknowledgment and after journaling.
- **Poisoned resolutions:** a bad resolution is contained as a rejection, not a project fault.
- **NFR restatement:** the arch's tick-deadline and per-call-timeout obligations are restated as "Every `sq` call in the continuation path goes through `TickBudget`".

### [NOTE] Pruning defect is a known prerequisite for 129

Pruning holds runs by node `sq.run_id`, which the Runner never sets. A paused run can therefore be pruned while its resolution is pending, and it then surfaces as `run_missing`. The design handles that safely (the node blocks and nothing is launched). It names issue #14 and gates it before 129. No change is needed, but the gate should appear in 129's plan entry too.

### [NOTE] Bare resolutions of pipeline steps are now rejected

A resolution with no decision on a pipeline step used to just return the node to runnable. It is now rejected as `decision_required`. This follows the arch ("Anything else is rejected explicitly") and is justified in the design. It is a behavioral change for existing submitters, so `docs/inbox-contract.md` and the CHANGELOG should say so.

### Run Digest

- Response length: 6855 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 115339 / 11266 / 104069 / 6702 / not computed
- Duration: 55.0 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
