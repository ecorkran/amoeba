---
docType: review
layer: project
reviewType: slice
slice: contract-proof-and-hardening
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/110-slice.contract-proof-and-hardening.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 182958b9cd6af07040e5b3ae8c3a3d783eb604d3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 181368
cachedTokens: 92579
cacheWriteTokens: 88783
completionTokens: 3196
durationSeconds: 30.5
costUsd: 0.39703
costBasis: provider
runId: run-20261015-slices-plan-fa1ba72e
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: proportionality
    summary: "Design is heavy for an effort-3 slice; several parts can be cut or deferred"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Component Structure"
  - id: F002
    severity: concern
    category: scope
    summary: "Network transport in the proof is a scope expansion beyond what 110 must deliver"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D2"
  - id: F003
    severity: concern
    category: correctness
    summary: "Pruning ownership relies on `recorded_result_run_ids`, and the escalation case is not specified"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D8"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Pruning has a race window between preview and `--yes` with a partial-failure path that is only half specified"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D8"
  - id: F005
    severity: concern
    category: scope
    summary: "Unspecified: how the PM-gated \"stop for the PM\" path interacts with slice completion"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D7"
  - id: F006
    severity: concern
    category: layering
    summary: "H1/H4 relocations touch behavior-bearing modules; \"no behavior change\" rests on existing suites only"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Migration Plan"
  - id: F007
    severity: note
    category: scope
    summary: "Hardening H2 completes a deferral the architecture and slice 106 left open"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D7"
  - id: F008
    severity: pass
    category: architecture-alignment
    summary: "Architecture alignment: writer model, Squadron boundary, and no new state"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#State Management"
  - id: F009
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for the new I/O paths"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D8"
---

# Review: slice — slice 110

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Design is heavy for an effort-3 slice; several parts can be cut or deferred

The slice plan scopes 110 as one lifecycle sequence through the public API, one injected restart, a locality check, pruning, and docs sufficient for 120. The design instead builds:
- A 15-step scenario across two projects.
- Two transports, plus a `Transport` protocol.
- Two oracles.
- Three crash-injection mechanisms: SIGKILL at two named points, a graceful stop, and `kill -9` of both `amoeba serve` and the resident process.
- An AST import rule with a negative fixture.
- A docs-coverage test.
- A guard test extending 101's store-safety scan.
- An opt-in real-`sq` test.

Candidates to cut or defer:
- Steps 12–13 (server crash, resident crash while streaming) test 109's resilience, which 109 should already prove in its own suite. The plan wants only "a restart injected mid-sequence".
- The `amoeba inspect --json` cross-check per step in the network run.
- The second subscriber on beta. The locality check in D6 already proves keying.
- Step 9 (the `projects.json` rewrite) and part of step 8, which re-test 107 and 108 behavior.
- The opt-in real-`sq` test, which duplicates the walkthrough.

The "under 2 minutes" fallback to the load tier is a sign the authors expect it to be heavy.

### [CONCERN] Network transport in the proof is a scope expansion beyond what 110 must deliver

The slice plan adds 109 as a dependency "so the contract is proven through the network surface as well as locally". The design runs the entire scenario a second time, duplicates the end-state oracle across transports, and adds a `NetworkTransport` that re-implements `change_record` conversion. A narrower reading meets the requirement: run the local scenario in full, then run a short subset over the network. That subset would be submit → outcome → SSE resume, including one server restart. The doubling raises cost, flakiness risk, and the chance of drifting from 109's own tests. This is partly a judgment call about the plan's wording, so I'm recommending a cut, not flagging a violation.

### [CONCERN] Pruning ownership relies on `recorded_result_run_ids`, and the escalation case is not specified

D8 says a zero-match escalation's run is never touched "whatever it turns out to be". The architecture says the store's record of owned paused runs "serves reconciliation and pruning". Two points are not worked out.
- Step 4's adopted run and step 10's checkpoint run must both appear in `recorded_result_run_ids`. The design asserts this but does not say where 106/102 guarantee it for `adopted` entries, as opposed to `completed` ones. The suite catches a mismatch only for step 10.
- Condition 3 ignores `sq.run_id` history. After a node goes `done`, its run becomes prunable once the retention period passes. That is correct, but a run the Runner re-links to a new node (a resume that spawns a successor) is not addressed.

State the ownership guarantee as a contract line, or reference where it is already documented.

### [CONCERN] Pruning has a race window between preview and `--yes` with a partial-failure path that is only half specified

The design batches all candidate ids into one `sq runs prune <ids…> --yes` call. A single live run makes sq exit 1. It also says "A file that is already gone counts as removed", which reads as success for ids that were never deleted by this call. Observation after the call decides pruned versus not_pruned, which is sound. Two cases are not stated:
- Whether `--yes` re-runs selection (store reads and run-file parse) immediately before calling sq or reuses the preview. The data-flow diagram implies a fresh selection, but it is not stated as a rule.
- A timeout on `sq` after partial deletion. Observation covers the outcome, but the report should say which ids sq may still be deleting when the timeout fires.

### [CONCERN] Unspecified: how the PM-gated "stop for the PM" path interacts with slice completion

D7 correctly routes non-additive gaps to the PM. But step 5 of the development approach ("fix the gaps it finds") is also named as the main effort uncertainty. A stopped gap means the contract proof cannot go green, and the design does not say whether the slice then ships with a documented known-gap (an expected-fail marker) or blocks. Because the slice plan makes this the gate for 120, state the closure rule.

### [CONCERN] H1/H4 relocations touch behavior-bearing modules; "no behavior change" rests on existing suites only

Moving `build_tenants` into `amoeba.process` changes the dependency graph. `process/tenants.py` would import the CF and Squadron tenants and the observers. The design allows `amoeba.process` to import `upstream.squadron.run_file`, but it does not check whether `standard_tenants` makes `amoeba.process` import `amoeba.upstream.context_forge` (108's `CFWatchTenant`). The architecture keeps process, store, and upstream adapters as separate layers. Add an import-boundary rule for that edge to `test_import_boundaries.py`, since the design extends that file for other rules but not for this one.

### [NOTE] Hardening H2 completes a deferral the architecture and slice 106 left open

`record_runner_report` is additive, composes existing transactions, and closes a deferral that was assigned to "120 (or 110, if earlier)". It fits the stated hardening rule. No schema change is involved.

### [PASS] Architecture alignment: writer model, Squadron boundary, and no new state

- Pruning deletes only through `sq runs prune`, with non-TTY stdin, which matches "no part edits SQ's run files directly" and the non-TTY invariant.
- The slice adds no tables or migrations, and the oracle reads through `Store.open_read_only`.
- The network path uses inbox submissions only.
- Store locality (a central, per-supervisor directory keyed by project) is verified across processes, consistent with slice 101's decision.

### [PASS] Failure modes are enumerated for the new I/O paths

Pruning covers:
- a missing `sq`;
- `sq` failing, timing out, or refusing a run;
- an unreadable store (refuse before `sq` is called);
- an unparseable run file or a missing `updated_at` (kept, with a `KeepReason`).

Crash windows (`AFTER_JOURNAL` and `AFTER_SIDE_EFFECT`) and server and process kills are exercised explicitly. Outcomes are determined by observation, which matches the architecture's reconcile-by-observation principle.

### Run Digest

- Response length: 7820 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 181368 / 92579 / 88783 / 3196 / not computed
- Duration: 30.5 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
