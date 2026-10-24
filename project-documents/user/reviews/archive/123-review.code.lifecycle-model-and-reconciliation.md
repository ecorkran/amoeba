---
docType: review
layer: project
reviewType: code
slice: lifecycle-model-and-reconciliation
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: b0294641aad627f79a75701bd8aa7d0ce3dacb8a
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: true
turns: 2
promptTokens: 329764
cachedTokens: 25664
cacheWriteTokens: 304096
completionTokens: 7203
durationSeconds: 59.3
costUsd: 1.35258
costBasis: provider
runId: run-20261024-p56-2b1f04ba
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: design
    summary: "`runnable_unbusy()` offers container nodes and steps whose predecessors aren't done"
    location: "src/amoeba/runner/decide.py:#ProjectView.runnable_unbusy"
  - id: F002
    severity: concern
    category: correctness
    summary: "\"Busy\" semantics changed from unresolved journal entries to in-flight runs"
    location: "src/amoeba/runner/tick.py:172-183"
  - id: F003
    severity: concern
    category: correctness
    summary: "`update_cf_reference` now clears the link when a caller omits `index`"
    location: "src/amoeba/store/nodes.py:131"
  - id: F004
    severity: concern
    category: dry
    summary: "`PlanObservation` construction is duplicated between reconcile and completion"
    location: "src/amoeba/runner/lifecycle/completion.py:57-76"
  - id: F005
    severity: note
    category: naming
    summary: "`LinkKey` is defined three times with two meanings"
    location: "src/amoeba/runner/lifecycle/tree.py:21"
  - id: F006
    severity: note
    category: dry
    summary: "`PlanReadSchedule` repeats its get-or-create logic"
    location: "src/amoeba/runner/lifecycle/cadence.py:55-58"
  - id: F007
    severity: note
    category: dry
    summary: "The `_string_constants` AST helper is copy-pasted between two tests"
    location: "tests/runner/test_cf_commands_defined_once.py:27-44"
  - id: F008
    severity: note
    category: consistency
    summary: "Failure detail quotes differ between probes and plan reads"
    location: "src/amoeba/runner/probes.py:128"
  - id: F009
    severity: note
    category: performance
    summary: "Reconcile and plan-stage cost grows with project size"
    location: "src/amoeba/runner/lifecycle/reconcile.py:55-75"
  - id: F010
    severity: pass
    category: standards
    summary: "Exception handling, typing and test coverage"
    location: "src/amoeba/runner/cf_call.py"
---

# Review: code — slice 123

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5
**Diff:** truncated: 256000 of 282051 characters reached the model

## Findings

### [CONCERN] `runnable_unbusy()` offers container nodes and steps whose predecessors aren't done

`runnable_unbusy` returns every `RUNNABLE` node that has no run in flight. Reconcile now creates initiative and slice container nodes plus step nodes, all `RUNNABLE`. That set therefore includes containers, blocked-by-predecessor steps and unlinked nodes.

The `ProjectView` docstring says planners "start work from" this method or from `tree.ready_steps()`, which reads as if both are safe. Test planners (`Planner`, `OncePerNode`, `ProofPlanner`) now use it. Slice 125's real planners could launch work out of order if they copy that pattern. The docstring should say `ready_steps()` is the only dispatch-safe source. Alternatively, rename or narrow the legacy accessor.

### [CONCERN] "Busy" semantics changed from unresolved journal entries to in-flight runs

Before, `_decide` excluded every node with any unresolved journal entry. Now `runnable_unbusy` excludes only nodes with an unfinished observed run. `_run_entries` already filters to run entries, and FAULT-state runs stay in `in_flight`, so the current behaviour holds.

Any non-run journal command kind, such as the planned `WriteCFPointer` in slice 125, would no longer hide its node from planners. The `ProjectView` docstring still claims "A node with an unresolved entry is never offered twice". Either restore the store-based check or narrow the claim to run entries.

### [CONCERN] `update_cf_reference` now clears the link when a caller omits `index`

`UPDATE_CF_REFERENCE` now overwrites `cf_index` with the value on the passed `CFReference`. Any caller that builds a fresh `CFReference` without `index` silently unlinks the node. `orphaning._orphan` does this on purpose. `references.py` uses `dataclasses.replace`, which is safe. The test helpers `TreeBuilder.orphan` and `_named` also rebuild the reference by hand.

Clearing the link is the same silent-fallback hazard the project rules warn about. Consider a distinct `unlink_node` store method for the orphan case and make `update_cf_reference` preserve the index. Alternatively, document the full-replace semantics on the method.

### [CONCERN] `PlanObservation` construction is duplicated between reconcile and completion

`completion._observations` and `reconcile._Creator._ensure_initiative_steps` / `_ensure_slice` each build `PlanObservation` from `CFInitiative` and `CFSliceEntry`, including the `slice_list_read` scoping. The create rule and the complete rule must agree on what "complete" means. If one changes and the other doesn't, steps would be created `DONE` and then handled differently on the next read. Put one `observe_initiative(initiative, scope)` / `observe_slice(entry)` pair in `steps.py` and call it from both.

### [NOTE] `LinkKey` is defined three times with two meanings

`tree.py` defines `LinkKey` as `(NodeKind, str, int)`. `cadence.py` and `plan_stage.py` each define `LinkKey` as `(str, str)`, which is project plus CF link. The same name for different shapes will confuse maintainers. Rename the schedule ones to `ScheduleKey`, or define it once.

### [NOTE] `PlanReadSchedule` repeats its get-or-create logic

`due()` inlines the same get-or-create that `_state()` already does with `setdefault`. `record_cut_off` only calls `_state` for its side effect, so it is effectively a no-op. The test and docstring justify it, but a short comment saying "intentionally leaves state untouched" would help.

### [NOTE] The `_string_constants` AST helper is copy-pasted between two tests

The same helper appears in `tests/runner/lifecycle/test_steps.py`. Move it to a shared test-support module.

### [NOTE] Failure detail quotes differ between probes and plan reads

`probe_link` quotes `completed.stdout[:OUTPUT_HEAD_CHARS]`. `plan_read._head` quotes stdout, or stderr when stdout is empty. A failing probe whose message is on stderr therefore shows an empty head. Reuse `_head` from `plan_read` or move it to `cf_call.py`.

### [NOTE] Reconcile and plan-stage cost grows with project size

Each due read calls `store.nodes_for_project` and rebuilds the tree up to five times (`PlanStage._read_link`, then `_tree` several times in `reconcile`). `ready_steps` also re-derives eligible slices per step. This is fine at current scale and the reads are interval-limited. It is worth a load-test if projects grow large. The Python rules require load tests for simulation, network and concurrency paths, and I saw none in the diff, which is truncated. This is also synchronous subprocess work inside the tick. It follows the existing probe pattern, and I did not verify the calling context.

### [PASS] Exception handling, typing and test coverage

Every `try/except` catches a specific type and carries a justifying comment (`TimeoutExpired`, `OSError`, `PlanParseError`, `ValidationError`, `JSONDecodeError`). Types are modern (`type` aliases, `|` unions, `StrEnum`). Command words and step values are defined once, and guard tests enforce that. The crash-at-every-write parametrized test is a strong check on the reconcile design, and the tests include real captured CF fixtures.

### Run Digest

- Response length: 6177 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 2
- Tokens — prompt / cached / cache write / completion / reasoning: 329764 / 25664 / 304096 / 7203 / not computed
- Duration: 59.3 s
- Cost: $1.35 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
