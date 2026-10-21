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
reviewedSha: 180ba37af2a376fde827398d3698c93faa18a31f
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 261770
cachedTokens: 156103
cacheWriteTokens: 105661
completionTokens: 7784
durationSeconds: 67.8
costUsd: 0.51691
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.6
findings:
  - id: F001
    severity: concern
    category: proportionality
    summary: "Design carries optional machinery that nothing in the slice requires"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md#D8 — Per-project config"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Source-scanning tests and contract-document sweeps add effort beyond the slice's requirements"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md#Success Criteria — Technical Requirements"
  - id: F003
    severity: note
    category: architectural-boundary
    summary: "Pre-dispatch verdicts are computed in Observe, not Decide"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md#Data Flow"
  - id: F004
    severity: note
    category: integration
    summary: "Arch-mandated \"shown to the PM\" for the CF/store disagreement is satisfied only passively"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md#D7"
  - id: F005
    severity: pass
    category: alignment
    summary: "Boundaries, dependencies and git read-only policy match the architecture"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md#D10"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for each new I/O path"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md#D11"
  - id: F007
    severity: pass
    category: scope
    summary: "Plan-entry deviations are explicit and justified"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md#D5"
---

# Review: slice — slice 128

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Design carries optional machinery that nothing in the slice requires

The plan sizes this slice at 3/5 and assigns the gate reads, hatches, clean-tree and branch check, disagreement record, merge policy and merge observation. The design adds several mechanisms those items do not need:
- **`format: 1` version key in the config file.** The file has one key today, and `extra="forbid"` already refuses unknown keys. A format version, an "unsupported `format`" error path and the tests for them are not required by any assigned item. Cut it, and add it when a second format exists.
- **WARNING for project ids the store does not hold.** The warning and its rule ("kept, because projects can be created while the process runs") serve no requirement. Cut it, or reduce it to "unknown ids are ignored".
- **Per-tick sharing of reads per checkout, plus `launch_candidates` as a separate function.** This is an optimisation of subprocess count. The tick deadline and per-call timeout already bound the cost. Start with simple per-candidate reads, and add sharing if a measured tick overruns.
- **`Wait`, `Ok` and `Block` as a three-way sum type with a `WaitReason` enum.** `Wait` has a single member, `pointer_moved`. The next tick's read-back already returns the step to `NEEDS_POINTER`. Reading that case as "no result" would drop the `Wait` type.

Cutting these shrinks the data model, the tests and the contract text. The slice's required outcomes are unaffected.

### [CONCERN] Source-scanning tests and contract-document sweeps add effort beyond the slice's requirements

The design lists three source-level tests:
- git appears only in `git_read.py`.
- Nothing under `amoeba.runner` opens a design file for writing.
- `LaunchRun` and `ResumeRun` are refused without `Ok`.

It also lists doc updates to four contract documents, and the arch edits are already applied. The git allowlist's `ValueError` and the `decide()` guard already enforce the invariants at runtime. The frontmatter-write test restates a "never" that no code path in the slice approaches. Keep the guard test, since it protects spend. Defer the other two source scans, or fold them into a single existing lint rule. Trim the contract-doc changes to the pieces other slices consume: the `cf status` fields and positions, the config format, and the checks' ids and provenance.

### [NOTE] Pre-dispatch verdicts are computed in Observe, not Decide

Arch 120 says Observe "never chooses anything" and Decide is the pure stage. Here Observe produces `dispatch_checks` as `Ok | Wait | Block` values, and Decide only turns them into actions. The D7 disagreement record is also written in Observe, after the accept test has decided that dispatch goes on. The evaluation functions (`entry_gate`, `branch_rule`, `accepted_by_pm`) are pure. So Observe can keep only the reads (`read_dispatch_facts`), and `ProjectView` can carry the raw facts for Decide to evaluate. That would keep the boundary clean and make every `Block` recomputable from recorded facts. The current shape is workable, since the evidence is stored in the block payload or the launch params, but the arch's principle favours moving the evaluation into Decide.

### [NOTE] Arch-mandated "shown to the PM" for the CF/store disagreement is satisfied only passively

Arch 120 says the disagreement is "recorded on the node and shown to the PM". D7 records a check on the slice node, which appears in `inspect checks`, on the feed, and in the launch's `dispatch_check` evidence. No escalation message is raised. This is consistent with "dispatch goes on", and the feed is the arch's stated channel for the notification bridge. Confirm that 129's write-up covers this surface, so the PM actually sees the record.

### [PASS] Boundaries, dependencies and git read-only policy match the architecture

- Git is limited to `status` and `merge-base` through one allowlisted function, as the arch's principle states. Every git and `cf` call runs under `TickBudget` and the per-call timeout.
- Merge policy is static config, defaults to `human`, and is recorded on each P6 dispatch. Nothing merges to `main` when an integration branch is set.
- Both hatches escalate through `check_standing` and the table, not through code. The Runner never writes frontmatter.
- The table keeps the catch-all, and the new inputs go through 126's vocabulary.
- Dependency direction is correct: the slice builds on 122–127 and 107, and provides to 129–131. The `cf config get` shape and the `cf list slices` shape are checked on each read, per the arch's unknown-escalates rule, rather than probed at start.

### [PASS] Failure modes are enumerated for each new I/O path

- **Outcome observation:** failures are recorded and routed to `unknown` or `errored`. Only a `TickBudget` cut-off defers, and the run's entry stays unresolved until the next tick.
- **Pre-dispatch reads:** a failure raises the project-scoped `checkout_read_failed`, which closes on the first clean tick. A cut-off issues nothing.
- **Merge observation:** a failed read blocks nothing, and `auto` never blocks a step it already merged.
- **Crash:** crash-repeat on the observation writes is handled by deterministic check ids and `record_check`'s retry rule.
- **Timing:** the design restates the tick bound as the deadline plus one per-call timeout.

### [PASS] Plan-entry deviations are explicit and justified

The design departs from the plan in three places, and the arch text already carries each change:
- A resume is not checked for a clean tree. A paused run's own uncommitted work would otherwise leave the PM only `handled` or `stop`.
- The allowed branch depends on the pipeline. Squadron refuses planning commits off the target.
- The gate is read at both the outcome and the dispatch boundary. CF evaluates only the boundary at the slice's current position, so one read cannot serve both.

Deferred items (#17 loop-accept counting, #18 waiting out a pending merge, hosting-service merges) are named and tracked as issues, not silently dropped. Everything the plan entry assigns to this slice is delivered.

### Run Digest

- Response length: 7204 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 261770 / 156103 / 105661 / 7784 / not computed
- Duration: 67.8 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
