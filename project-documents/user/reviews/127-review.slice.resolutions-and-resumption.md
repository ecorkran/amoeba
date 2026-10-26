---
docType: review
layer: project
reviewType: slice
slice: resolutions-and-resumption
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/127-slice.resolutions-and-resumption.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261025
dateUpdated: 20261025
reviewedSha: e4ed5217fedd06dbcfca913d74ad1ce7b661eb0e
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 119312
cachedTokens: 8865
cacheWriteTokens: 110443
completionTokens: 5823
durationSeconds: 50.1
costUsd: 0.501702
costBasis: provider
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Layering, dependency direction and tick order match the architecture"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#Technical Decisions"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for the new I/O paths"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#D6 — Resume confirmation and resume failures"
  - id: F003
    severity: concern
    category: error-handling
    summary: "A withheld retry or accept is acknowledged `applied`, so the submitter cannot see it was not carried out"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md:253"
  - id: F004
    severity: concern
    category: scope
    summary: "Plan-assigned scope is deferred: CF-gate disagreement on accept, and `inspect resolutions`"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md:298-304"
  - id: F005
    severity: concern
    category: proportionality
    summary: "The document carries implementation-time records and restated upstream material"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md:471-523"
  - id: F006
    severity: note
    category: operability
    summary: "Stop leaves a paused run's checkout held indefinitely"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md#Special Considerations"
---

# Review: slice — slice 127

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Layering, dependency direction and tick order match the architecture

- **Order:** the resolution stage runs after intents and before Observe and the view. This matches the arch's per-tick order, "acknowledge pending resolutions (slice 127, D3)".
- **Pure decide:** `classify`, `judge_resolution`, `dispatch_state` and the planners stay pure. Reads happen in `gather` and in Act's single pre-poll, which the arch permits as a precondition check.
- **Inbox boundary:** the inbox checks payload shape only and imports no Runner vocabulary (D1, following 124 D3). The Runner's answer goes on the blocked state, not the submission.
- **Contract first:** changes to 100 (migration `012`, the three store methods, the observer rules) land before any Runner code (D9). This is the arch's "contract changes first".
- **Resolution set:** it matches the arch's closed set. Retry and accept are offered only at a loop (`is_loop`) and never at an interactive checkpoint. A rerun is never used for a paused run. Stop is held as a block with reason `stopped`. A missing run is never relaunched.

### [PASS] Failure modes are enumerated for the new I/O paths

- **Pre-poll (D4):** spent budget, `PollFailure` and `not_found` each have an explicit handling and outcome.
- **Resume failures (D6):** the five `ResumeFailure` values are decided on observed state and exit code, not message text.
- **Crash and restart:** a crash between acknowledgment and journaling, a crash after journaling and before launch, and a restart with no tracked child are all covered.
- **Exit 2 on resume:** it escalates the node and does not stop the process, as the arch specifies.
- **Tick NFRs:** the slice restates `TickBudget` and `tick_call_timeout_seconds` for the pre-poll and requires every `sq` call to go through the budget. It notes that the store-only stage needs no budget check, following the arch's "tick never waits".

### [CONCERN] A withheld retry or accept is acknowledged `applied`, so the submitter cannot see it was not carried out

- **What happens:** when the pre-poll finds the run no longer at the recorded pause, D4 withholds the resume. It journals an `observe` entry with `resume_skipped: run_not_at_pause`.
- **The gap:** the resolution was already acknowledged `applied` in the resolution stage (D3). The `resume_skipped` marker exists only in the journal entry's result. It is not on the `blocked_state` row that submitters, 160 and the notification bridge read (`runner_outcome`, `runner_code`, `runner_reason`).
- **Why it matters:** a PM's `retry` can be dropped, and the only visible answer is `applied`. The arch says that what the Runner cannot execute is "rejected explicitly". The slice's own Value section says a resolution is "never ignored".
- **Fix:** record the skip on the blocked state, for example with a `runner_code` that is not a rejection. Otherwise state in the inbox contract that `applied` means "acknowledged", and that the journal is the source for what was done. A related point: the arch's precondition-check sentence (Observe, decide, act) names only `handled` as the journaled-read exception. The converted-to-observe path should be named there too.

### [CONCERN] Plan-assigned scope is deferred: CF-gate disagreement on accept, and `inspect resolutions`

- **Gate disagreement:** D7 moves plan entry 8's last criterion, recording an accepted outcome that CF's gate still fails, to 128. The slice documents the departure as a dated plan change and tracks it as issue #15. The reasoning is sound, because only 128 reads the gate. Even so, it is deferred scope the slice plan assigned to this slice.
- **Interim exposure:** until 128 lands, an accept advances the step and dispatches the successor with no disagreement recorded. The only protection is the "scratch copies only" rule in 125's risk assessment, which is not a mechanical guard.
- **`inspect resolutions` (line 79):** deferred to issue #16 and added to plan entry 10.
- **Fix:** keep the deferrals. Add a hard precondition on 129, and ideally on any non-scratch use of `accept`, that 128's gate comparison is merged. State that it blocks 129 the way issue #14 does (line 76).

### [CONCERN] The document carries implementation-time records and restated upstream material

- **Walkthrough:** the Verification Walkthrough holds session artifacts that belong in task or validation notes, not in the design. Examples are exact pass counts (246, 3952, 594 files, 47 contract tests), the observation that this session's launches lacked `OPENROUTER_API_KEY`, and a "Corrections found while running it" paragraph. These go stale on the next commit. Cut them to the commands and expected behaviour per branch.
- **Squadron surface:** the "Interfaces Required / Squadron" block (lines 93-101) restates Squadron source behaviour that the arch already records. Examples are the `--decision` and `--instructions` semantics, the exit-2 cases, and `run_id=` absent on resume. Keep only what this slice relies on that the arch lacks: no `--run-id` with `--resume`, instructions not persisted, and the claim sequence.
- **Handling for a case the slice says cannot occur:** the `unresolvable` situation for a blocked step with an unresolved latest entry (line 215, "should not exist") is extra vocabulary, a rejection code and a check. D3's single catch for an unexpected exception could cover it.
- **What stays:** the core mechanisms are justified by the arch and by Squadron's observed resume behaviour. These are the resolution stage, the continuation entries, and the confirmation by `paused_at`. The migration and the routing input are also justified. The effort estimate of 3/5 is credible.

### [NOTE] Stop leaves a paused run's checkout held indefinitely

After `stop` on a paused run, the checkout stays held, so a single-worktree project is stalled. The only exits are finishing or removing the run in Squadron and then submitting `handled`. This matches the arch ("a paused run stops that project until the PM handles it", and the Runner never kills runs). The slice states it plainly, so no change is required. It is worth surfacing in the `stopped` escalation text.

### Run Digest

- Response length: 7118 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 119312 / 8865 / 110443 / 5823 / not computed
- Duration: 50.1 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
