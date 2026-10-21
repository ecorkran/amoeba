---
docType: review
layer: project
reviewType: slice
slice: batch-dispatch
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/130-slice.batch-dispatch.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261021
dateUpdated: 20261021
reviewedSha: 2d4f5f8d86baf1569865dbb6585974c75d8feaf6
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 460244
cachedTokens: 357347
cacheWriteTokens: 102887
completionTokens: 8431
durationSeconds: 78.1
costUsd: 0.532418
costBasis: provider
squadronVersion: 0.23.6
findings:
  - id: F001
    severity: concern
    category: architecture-boundaries
    summary: "Reads and a decision inside Act break observe/decide/act"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D4 (The checkout is still confirmed) and #D9 (Act, step 1)"
  - id: F002
    severity: concern
    category: architecture-boundaries
    summary: "`sq_batch_item` is a result record placed in the command journal"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D10"
  - id: F003
    severity: concern
    category: proportionality
    summary: "The design carries several mechanisms that can be cut or merged"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D6, #D7, #D11"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Blocking the initiative node on a paused batch is under-specified"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D6 (Only an ended batch fans out) and #D8 (A paused batch)"
  - id: F005
    severity: concern
    category: dependency-risk
    summary: "Selection drift is caught only after the money is spent"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D3"
  - id: F006
    severity: note
    category: documentation
    summary: "Arch edits are present"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md:100, 158"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Failure modes and NFRs for the new I/O paths are enumerated"
    location: "project-documents/user/slices/130-slice.batch-dispatch.md#D9 (Failure modes table)"
---

# Review: slice — slice 130

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Reads and a decision inside Act break observe/decide/act

The arch says Decide is pure and does no I/O. Act "issues each action as a journaled command … and nothing else." Observe reads the checkout state and CF status. The design puts two things in Act:
- **D4:** `cf get --json` runs inside Act's `LaunchBatch`, before journaling. Its mismatch result blocks every item step with `checkout_unresolved`.
- **D9:** `ResumeItem` reads the report in Act. If the record differs from the routed entry's `item_record`, it swaps the action for an `ObserveItem` result with `resume_skipped: record_changed`. That is a branch on the action chosen, taken outside Decide, and the arch forbids it.

D9's check is a reasonable guard against acting on stale state. Both reads belong in Observe, with the result recorded where Decide can see it, and D4 can reuse the checkout state Observe already reads each tick. The design should do one of two things:
- Move both reads into Observe.
- Name 127 D4's pre-poll pattern as the precedent, and state the exception the arch makes for it.

### [CONCERN] `sq_batch_item` is a result record placed in the command journal

The arch defines journal kinds as commands with side effects, each with required keys, an observer and a re-issue rule. In v1 they are `sq_run` and `cf_write`. `sq_item_resume` is a real command, and a new kind for it is justified. `sq_batch_item` is never issued, never unresolved and never recovered. Its observer exists only to answer "a store defect".

The design uses the journal to make "a step's latest run entry" uniform through `RUN_RESULT_KINDS`. That is a coherent goal. But it widens the journal's meaning, and the design never says so, and the arch's list of kinds is not updated. Either:
- Record the widening, by stating in the contract text and the arch that the journal also holds store-written outcome entries; or
- Show why the existing run-result surface, with a per-item result stored on the step, can't carry the outcome.

### [CONCERN] The design carries several mechanisms that can be cut or merged

The design is large: a five-module subpackage, two store kinds, a new store transaction, a new observer, a new classify situation and two upstream asks. Some of it serves cases the shipped table doesn't use yet:
- **`not_selected` and `not_reached`.** These are two of the four new outcome values. They route the same way (catch-all escalate) and allow the same decisions (`ended_run`: `rerun`, `stop`, and `handled`). One `no_record` outcome plus a reason in the payload meets every stated requirement.
- **`flag_kind` as a routing input.** It adds seven values to the closed vocabulary, and D7 says no rule uses it: "table edits, made when evidence asks." The flag kind is already in the block payload and the item record. Add the input when a rule needs it.
- **The unpredicted-but-linked-slice path.** D6 records a review and a ledger row for a slice nobody drove. That path is reached only after the selection prediction has failed. The mismatch escalation alone covers the PM's need. Detection would later record the review as an external one.
- **A per-item time bound.** `per_item: true` and the multiplier change 126's bound function and table schema. Ten items give a 40-hour bound. A single configured batch bound would do until timing evidence exists.

The design already says step 5 (item resume) can move to a follow-on. The arch requires per-item resume, so that step stays in scope. The four cuts above should happen first.

### [CONCERN] Blocking the initiative node on a paused batch is under-specified

A paused batch blocks the initiative node on `SQ_CHECKPOINT`, which the arch's "paused run becomes a blocked node" requires. The store allows one open blocked state per node, and the initiative node may already be blocked (for example by an orphan escalation or an initiative-level human step). The design doesn't say what happens to the pause block in that case, or how the item steps stay `IN_FLIGHT` while their parent is blocked. The failure mode needs an explicit rule. Either way, the design should state that a runnable step under a blocked initiative still dispatches and is observed.

### [CONCERN] Selection drift is caught only after the money is spent

D3 copies `undesigned_slices` from Squadron source, which isn't a published surface. The arch says the Runner depends on shapes, and that an unreadable shape escalates. This design is open about the risk: opt-in, labelled experimental, and `batch_selection_mismatch` plus S15. The mitigation is acceptable for a first release. But the arch's rule that hold stops anything new is only enforced after a paid, unattended run. The design should record a closing condition: remove the prediction, or make the batch default off, once S15 lands. It should also say that a drifted predicate (an extra or missing excluded status) is checked at every launch and not just at the first one.

### [NOTE] Arch edits are present

The `design_dispatch` entry under "Where each value lives" and the batch pointer rule are both in the arch. The arch's `dateUpdated` still reads 20261020, while the design says the edits were made on 20261021.

### [PASS] Failure modes and NFRs for the new I/O paths are enumerated

The table covers:
- the report read: missing, malformed, or slow;
- the pre-fan-out plan read: failure or timeout;
- a host crash mid-transaction;
- an item-resume child that hangs, is refused, or is left unobserved after a restart.

Each has an explicit handling strategy. The arch's tick-deadline NFR is applied before the report read and the plan read. The `P4`-derived 240-minute time bound is restated with its source. Launch, confirmation and recovery of the batch run stay with 122 and 120, unchanged, and the dependency direction (batch code consuming 122–129) is correct.

### Run Digest

- Response length: 7041 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 460244 / 357347 / 102887 / 8431 / not computed
- Duration: 78.1 s
- Cost: $0.53 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
