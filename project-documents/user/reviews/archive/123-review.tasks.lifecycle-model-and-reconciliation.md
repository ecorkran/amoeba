---
docType: review
layer: project
reviewType: tasks
slice: lifecycle-model-and-reconciliation
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: 7cd6a154fb54c712321ed04d1de4fa72e9b9b598
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 119126
cachedTokens: 8843
cacheWriteTokens: 110279
completionTokens: 8433
durationSeconds: 63.9
costUsd: 0.527147
costBasis: provider
runId: run-20261024-p56-2b1f04ba
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage and commit cadence"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md"
  - id: F002
    severity: concern
    category: coverage-gap
    summary: "`plan_read_interval_seconds` positivity check is not assigned to any task"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:192-201"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 8.2's tests depend on `reconcile`, which is not created until Task 8.3"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:259-283"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 9.1 is too large and mixes a refactor with new behavior"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:335-346"
  - id: F005
    severity: concern
    category: task-sizing
    summary: "Task 6.3 bundles a shared-code extraction with a new feature"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:215-226"
  - id: F006
    severity: concern
    category: design-consistency
    summary: "Task 9.1 silently overrides the LLD's `ProjectView` contract"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:47"
  - id: F007
    severity: concern
    category: test-coverage
    summary: "No reconcile-level test for the no-slice-plan state or `slice_plan` completion"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:285-318"
  - id: F008
    severity: concern
    category: structure
    summary: "`ready_steps` in `tree.py` and `predecessors` in a possible `predecessors.py` risk a circular import"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:165-186"
  - id: F009
    severity: note
    category: robustness
    summary: "Fixture capture task has no failure path for its assumptions"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:98-107"
  - id: F010
    severity: note
    category: test-pattern
    summary: "Test-only tasks placed away from their implementation tasks"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:320-366"
  - id: F011
    severity: note
    category: scope
    summary: "Proportionality"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md"
---

# Review: tasks — slice 123

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage and commit cadence

Every Functional and Technical Requirement in the slice maps to a task:
- **Linking:** 8.3 and 11.3.
- **Rename, renumber, and completed-slice orphan:** 8.2 and 8.4.
- **Bad-read non-orphaning:** 8.1, 8.2 and 9.2.
- **Cut-off and early reads:** 6.3, 6.4 and 9.1.
- **Human steps:** 10.1.
- **Ready-step table:** 5.3 and 5.4.
- **Deferred and unknown status:** 8.3.
- **Crash repair and the `create_node` guard:** 8.6.
- **Contract docs and CHANGELOG:** 11.1 and 11.2.

Every task carries its own commit, so checkpoints are distributed through the file rather than batched at the end. The per-section "test-with" pattern is followed. No task lacks a traceable criterion.

### [CONCERN] `plan_read_interval_seconds` positivity check is not assigned to any task

The slice's Settings and CLI section says the value "must be positive, which `runner_tenant()` checks with 122's other bounds". Task 6.1 only adds the field, the flag, and override tests. Task 9.1 mentions passing settings through `factory.py` and `tenant.py` but not the bound. A zero or negative interval would make every read due on every tick, and nothing would catch it. Add to 6.1, or to 9.1, a bound check in `runner_tenant()` plus a test that rejects zero and negative values.

### [CONCERN] Task 8.2's tests depend on `reconcile`, which is not created until Task 8.3

The Section 8 preamble says every test uses a `reconcile_support.py` helper that "runs `reconcile`". Task 8.3 creates `reconcile.py`, so 8.2 (`orphaning.py`) cannot call it. 8.2 also needs pre-existing linked nodes, and in the real code only the create rule makes those. The file does not say which task creates `reconcile_support.py`.

Task 8.2 also splits `test_renumber_yields_one_orphan_and_one_new_node` across itself and 8.3. Fix one of these ways:
- Make 8.2 tests call the orphaning function directly on nodes built through `tree_support`.
- Swap the order so the create rule comes first.
- Name the task that creates `reconcile_support.py`.

### [CONCERN] Task 9.1 is too large and mixes a refactor with new behavior

Task 9.1 has effort 5 and edits `tick.py`, `decide.py`, `factory.py`, `tenant.py` and `tick_support.py`. It also changes every direct `ProjectView(...)` constructor in tests. It adds the plan-read stage, cut-off handling, the failed-read path, the exception-boundary behavior and about nine test scenarios, all under one `feat:` commit.

Split it into two tasks:
- **First task:** the behavior-preserving `ProjectView.tree` field and test-rig update, as a `refactor:` commit.
- **Second task:** the plan-read stage wiring and its tests.

The `record_complete` rule in 9.1 ("clearing `last_failed` only if no initiatives-level or slice-level failure remained") overlaps with 9.2's closure logic. It also never says how `reconcile`'s `faults` argument reaches the tick. Assign each of those to exactly one task.

### [CONCERN] Task 6.3 bundles a shared-code extraction with a new feature

Task 6.3 has effort 5. It extracts `run_cf` into the new `runner/cf_call.py` and rewires `probe_link`. It also adds three result types, the budgeted `read_plan`, and error-document handling. All of this lands in one `feat:` commit. The extraction is a behavior-preserving `refactor:` that stands alone and is covered by the existing `test_probes.py`. Move it into its own task (or into 4.1, which already edits `probes.py`). Also add `cf_call.py` to the "Task-level additions" list, since neither it nor `commands.py` appears in the LLD's component structure.

### [CONCERN] Task 9.1 silently overrides the LLD's `ProjectView` contract

The LLD API Contracts say `ProjectView.tree` "replaces 122's flat runnable-node list". The task file keeps `runnable_nodes` alongside `tree`. This gives Decide two sources of truth. It also adds complexity the project rules say to resist. The task defers the decision to the review, but the choice affects 124's interface. Resolve it before implementation by either:
- editing the LLD to say additive, or
- adding a task step that removes `runnable_nodes` and migrates 122's tests.

### [CONCERN] No reconcile-level test for the no-slice-plan state or `slice_plan` completion

The slice requires that an initiative with no slice plan reads as the no-plan state: `slice_plan` not complete, no fault. It also defines `slice_plan` complete when "the slice list reads successfully". Task 6.3 tests that `NoSlicePlan` is produced, and Task 5.1 tests the predicate on a raw observation. No task tests how `reconcile` turns a `NoSlicePlan` or a `SliceList` into the `PlanObservation`. That includes the flip of `slice_plan` to `done` when a list first becomes readable. Tasks 8.3 and 8.5 omit both cases. Add them to 8.3 (creation) and 8.5 (completion). The test names should mention `NoSlicePlan`.

### [CONCERN] `ready_steps` in `tree.py` and `predecessors` in a possible `predecessors.py` risk a circular import

Task 5.3 says to move `predecessors` into `predecessors.py` "if `tree.py` nears 300 lines". Task 5.4 puts `ready_steps` in `tree.py`, and it calls `predecessors_done`. `predecessors(tree, node)` takes a `LifecycleTree`. If the split happens, `tree.py` and `predecessors.py` import each other. Fix this by choosing the layout now: `predecessors.py` holds the free functions and `ready_steps` lives there or in a third module. Alternatively, say the split must preserve a one-way import. Also reword the garbled "Eligible slice" bullet in 5.3, which reads "CF status not `deferred` or `deprecated` is expressed by 'has step children'".

### [NOTE] Fixture capture task has no failure path for its assumptions

Task 3.1 hard-codes initiative `140` as the one with no slice plan, and `100` and `120` as the other captures. If initiative 140 now has a plan, the error fixture cannot be captured and the task has no instruction. Add "if `cf list slices 140` exits 0, pick another initiative without a plan; if none exists, write `BLOCKED:`". Task 3.1 also depends on 2.2, which has no relation to it. Depending on 1.1 is enough.

### [NOTE] Test-only tasks placed away from their implementation tasks

The `create_node` guard (8.6) is introduced three tasks after `create_node` is first called (8.3). The budget-coverage test (9.3) sits two tasks after the plan-read stage it covers (9.1). Both are cross-cutting checks, and the crash test genuinely needs all rules in place, so this is acceptable. The guard test could move into 8.3 at low cost. That would also remove 8.3's forward reference to "checked by Task 8.6".

### [NOTE] Proportionality

The file has 27 tasks for a slice rated 3/5. It is one task file, which fits the single-slice structure. The LLD's surface area (store, parser, model, read, reconcile, wiring, docs) justifies most of the count. Tasks 2.2 and 6.1 are small enough to merge with 2.1 and 6.2 if the author wants fewer commits. The slice states no load or throughput NFR beyond informal timing remarks, so no `tests/load/` or CI gating task is required.

### Run Digest

- Response length: 8677 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 119126 / 8843 / 110279 / 8433 / not computed
- Duration: 63.9 s
- Cost: $0.53 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
