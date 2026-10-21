---
docType: review
layer: project
reviewType: slice
slice: gates-git-and-human-steps
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/128-slice.gates-git-and-human-steps.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261021
dateUpdated: 20261021
reviewedSha: 374636ac7b405a8a8ab67361dff97712b5add6e0
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 118089
cachedTokens: 11266
cacheWriteTokens: 106819
completionTokens: 5476
durationSeconds: 51.8
costUsd: 0.483974
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.6
findings:
  - id: F001
    severity: concern
    category: routing-correctness
    summary: "PM `accept` on a hatch- or vacuity-escalated outcome cannot advance"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md:277-279"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Design is heavier than a 3/5 slice needs; name what to cut"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md#Technical Decisions"
  - id: F003
    severity: note
    category: scope
    summary: "Default `human` policy blocks the next slice's planning in a checkout until the PM merges"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md:356"
  - id: F004
    severity: note
    category: scope
    summary: "Departures from the slice plan are explained and already reflected in the architecture"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md:329"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Layer boundaries, dependency direction and read-only git"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md#Architecture"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure modes and NFRs are enumerated for each new I/O path"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md#D2, #D5, #D9, #D11"
---

# Review: slice — slice 128

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] PM `accept` on a hatch- or vacuity-escalated outcome cannot advance

D3 makes `advance-on-accepted-review` require `check_standing: passed`. D4 makes a present hatch `failed` and a missing design `vacuous`. Both escalate. The architecture lets the PM resolve an escalated completed outcome with `accept: advance` (120 arch, "Resolution and resumption"). Under this table, accepting a hatch-flagged outcome re-routes to `escalate-everything-else`, so the PM is blocked again with no explanation.

The doc says `review: none` "cannot clear a slice silently". It does not say whether a PM's explicit accept is allowed to clear it. If the intent is that a hatch can never be accepted, the doc should say so. It should also say which resolutions are offered, so `accept` is not offered where it cannot work. If accept should work, the rule needs a different condition on checks. D3 sentence 294 explains why `gate_state` is omitted from this rule but not why `check_standing` is kept. The Success Criteria never test "accept a hatch outcome".

### [CONCERN] Design is heavier than a 3/5 slice needs; name what to cut

The mechanisms the architecture requires are all present and justified: the gate reads, the hatches, the clean-tree and branch checks, the per-project config, and merge observation. The extra weight comes from these additions:

- **Seven new `FaultKind` members.** The block kinds `cf_gate_blocks`, `cf_behind_store` and `cf_gate_unknown` differ only in payload. They could be one `cf_gate` kind with a `reason` field. The PM's answer to each is identical (D5, last bullet).
- **Three-way `DispatchCheck` (`Ok | Wait | Block`).** `Wait(pointer_moved)` has one use, and "no result" already exists as a fourth outcome. `pointer_moved` could be folded into "no result".
- **Four `MergeObservation` outcomes, including `unobservable`.** It adds a branch condition keyed on the entry's `merge_policy`. It exists only for the case where `P6` ended on the target under `human`. That case could be a plain `not_merged`, so the step stays human.
- **A `dispatch_check` evidence blob** is written into every launch's journal parameters, on top of the block and check records.
- **Four contract documents plus the plan and arch edits.** These restate decisions made in this doc.

Dropping or folding these would leave the architecture's requirements met and shrink the test matrix, which is already table-driven over D1, D3, D4, D5, D6 and D9.

### [NOTE] Default `human` policy blocks the next slice's planning in a checkout until the PM merges

Under the default policy, `P6` leaves the slice branch checked out. Every later `P4` or `P5` in that checkout then blocks with `checkout_branch` until the PM merges and reruns. This is consistent with the architecture's one-pipeline-per-checkout rule and is explicitly deferred to issue #18. It is acceptable for 129's single-slice proof. Multi-slice use will hit it on every slice.

### [NOTE] Departures from the slice plan are explained and already reflected in the architecture

There are two departures: a resume is checked for branch only (D5), and planning runs need the target (D6). Both carry rationale: Squadron refuses planning commits off the target, and a paused run's tree holds its own work. The 120 arch's "Squadron does the git work" paragraph already states both. The plan entry edit is listed under Special Considerations. This is not dropped scope.

### [PASS] Layer boundaries, dependency direction and read-only git

- **Observe, decide, act.** Subprocess reads happen only in Observe. Routing inputs are reduced from the store alone, which keeps 126's rule that routing is a pure function. `BlockDispatch` is store-only, matching the architecture's rule for actions without side effects.
- **Git.** One allowlisted function (`status`, `merge-base`) matches the architecture, with `--no-optional-locks` and a source test. Merge policy is static config recorded on each `P6` dispatch, as the arch requires. Merges are observed by reachability.
- **Gate reads.** CF's gate is read at the two points the arch names. The hatches escalate through the table rather than code, and the Runner never writes frontmatter.
- **No store changes.** The Excluded section confirms none are needed.

### [PASS] Failure modes and NFRs are enumerated for each new I/O path

- **Outcome observation (D2).** A failed or unparsable read is recorded and routed as `unknown`. A `TickBudget` cut-off defers ingestion safely. A crash between the check writes and the report is covered by the deterministic check ids and `record_check`'s retry rule.
- **Pre-dispatch and merge reads (D5, D9, D11).** A read failure raises the project-scoped `checkout_read_failed`. It closes on the first clean tick, and no step is blocked for it.
- **Timeouts.** Every call goes through `TickBudget` and `tick_call_timeout_seconds`. The worst-case tick bound is restated as the deadline plus one call timeout.
- **Git hangs.** Git runs with stdin closed and prompts disabled.

### Run Digest

- Response length: 5920 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 118089 / 11266 / 106819 / 5476 / not computed
- Duration: 51.8 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
