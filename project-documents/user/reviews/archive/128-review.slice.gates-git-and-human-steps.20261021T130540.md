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
reviewedSha: 15e60ed28392847b17dc6ccf8e1912da11978932
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 232548
cachedTokens: 108375
cacheWriteTokens: 124167
completionTokens: 15801
durationSeconds: 130.7
costUsd: 0.666331
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.6
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Core architectural commitments are honored"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md#Technical Decisions"
  - id: F002
    severity: concern
    category: integration
    summary: "Blocked-resume resolution set contradicts the architecture and 127"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md:344"
  - id: F003
    severity: concern
    category: hidden-dependency
    summary: "Dirty-tree check on resume assumes a paused run leaves a clean tree"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md:316-330"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Design is heavier than the plan's effort 3 and carries cuttable items"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md#Implementation Notes"
  - id: F005
    severity: note
    category: nfr
    summary: "Tick-bound NFR is enforced but not restated as a target"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md#Technical Requirements"
  - id: F006
    severity: note
    category: failure-modes
    summary: "`cf config get --json` is a new hard shape outside the architecture's probe list"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md:105"
  - id: F007
    severity: note
    category: coupling
    summary: "Observe computes the same launch candidates Decide will act on"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md:173"
---

# Review: slice — slice 128

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Core architectural commitments are honored

- **Gate reads:** the two read points (D1) match the architecture's "Gates come from CF's structured status" item. Routing never reads prose.
- **Hatches:** they escalate through `check_standing` in the table (D3, D4), and the Runner never writes frontmatter.
- **Git:** it is read-only through `status` and `merge-base` (D10). The merge is observed by reachability (D9). The policy lives in static config, defaults to `human`, and is recorded on each `P6` dispatch (D8).
- **Planning branch:** planning runs are limited to the target, per the architecture's "Squadron does the git work" text.
- **Observe/Decide/Act:** Decide stays pure. `BlockDispatch` is a store-only action like 123's `BlockHumanStep`. Reads are written only when they change something or a decision uses them.
- **Faults:** node blocks and the project-scoped `checkout_read_failed` follow the architecture's fault model.
- **Dependency direction:** the slice builds on 122–127 and exposes 129–131 correctly.

### [CONCERN] Blocked-resume resolution set contradicts the architecture and 127

D5 says a blocked resume stays `paused_run`, and that the PM "resolves with `rerun` or `retry`".
- **The conflict:** the architecture says "A rerun is never used for a paused run, which is always resumed". 127's situation table allows only `retry`, `accept`, `handled` and `stop` for `paused_run`. `rerun` would be rejected as `decision_not_applicable`.
- **Original decision lost:** if the original resume was `accept`, the dispatch block loses it. The PM must choose again, and `retry` is itself rejected at an `interactive_checkpoint`.
- **Fix:** state the allowed answers for a blocked resume as 127's `paused_run` set. Say that the PM re-supplies the decision, and what happens when the original was `accept` or came from an interactive checkpoint.

### [CONCERN] Dirty-tree check on resume assumes a paused run leaves a clean tree

- **The check:** D5 applies the clean-tree and branch rule to `ResumeRun` as well as to launches. The architecture does say "before dispatching any run".
- **The gap:** Interfaces Required cites only that `branch enter` refuses a dirty tree, which applies to fresh entry. Nothing says Squadron's non-interactive checkpoint leaves the slice branch committed and clean.
- **The risk:** if a pause can leave uncommitted state, every `retry` or `accept` resume blocks on `checkout_dirty`. The PM could clear it only by committing or discarding the run's own work. That breaks "unattended between decisions that need a person" for the paused-run path.
- **Fix:** record the Squadron guarantee, observed as the other interfaces are, or define how a resume treats paths the paused run itself left.

### [CONCERN] Design is heavier than the plan's effort 3 and carries cuttable items

The slice rates itself 4/5 against the plan's 3. It adds six modules, two routing inputs, a new action, seven `FaultKind` members, a config file, a setting and a flag. It also changes 123, 125, 126 and 127 code and four contract documents. Items that can be cut or simplified without dropping plan-assigned scope:
- **Config format version:** drop `format: 1` and its "unsupported format" startup failure (D8). Nothing uses a second version yet.
- **Unknown project ids:** drop the WARNING for project ids the store does not hold at start (D8). It checks a case that is not an error.
- **Fault kinds:** collapse `cf_gate_blocks`, `cf_behind_store`, `cf_gate_unknown` and `pending_decision` into one `cf_gate` kind with `reason` in the payload (D11). The PM sees the same information, and four members and four test paths go away.
- **Per-run reads:** D2 makes up to five subprocess calls per completed run. `workflow.review_gate_effective_date` and the plan read could share the per-checkout, per-tick read cache that D5 already defines for `git.integration_branch`.
- **Merge observation:** the slice already calls step 7 separable. If effort has to come down, defer it and keep 123's "CF reports the slice complete" fallback. The architecture's "Merge policy" text lists it, so deferral needs a plan edit.

### [NOTE] Tick-bound NFR is enforced but not restated as a target

The architecture states worst-case tick length as the deadline plus one per-call timeout. The slice requires every `git` and `cf` call to go through `TickBudget` (D2, D5, D10). It does not restate the bound. This slice adds the most subprocess calls per tick of any Runner slice: up to five per completed run, one `merge-base` per slice awaiting merge, and the shared checkout reads. Add one line restating the bound, and a test that a mid-sequence cut-off leaves the run unrecorded and reaches no further reads.

### [NOTE] `cf config get --json` is a new hard shape outside the architecture's probe list

Every dispatch depends on `cf config get git.integration_branch --json`, which the architecture's start-up and per-link probes do not cover. A shape drift is handled: D11 raises `checkout_read_failed`, and nothing launches. It would surface on every tick for every project, though, instead of once at probe time. Consider adding the shape to the per-link `cf` probe, or say explicitly that first use is the check.

### [NOTE] Observe computes the same launch candidates Decide will act on

D5 has Observe predict which steps Decide will launch or resume, using the same pure functions. A divergence trips the `decide()` guard, which raises `ValueError` and faults the whole project. That is a safe failure, but it is coarse. The slice should require a test that drives Observe's candidate set and Decide's launch set from the same fixtures, so any divergence fails there first.

### Run Digest

- Response length: 6704 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 232548 / 108375 / 124167 / 15801 / not computed
- Duration: 130.7 s
- Cost: $0.67 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
