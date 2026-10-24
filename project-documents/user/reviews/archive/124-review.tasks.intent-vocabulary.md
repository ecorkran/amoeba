---
docType: review
layer: project
reviewType: tasks
slice: intent-vocabulary
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/124-tasks.intent-vocabulary.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: 42f8f0679d2bbbb0bf4b4b765fcab6ac9dd86da5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 286821
cachedTokens: 188274
cacheWriteTokens: 98539
completionTokens: 6067
durationSeconds: 48.3
costUsd: 0.474476
costBasis: provider
runId: run-20261024-p56-53bc46f9
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 5.2 under-specifies the migration of the existing test planners"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:208"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Task 3.2's success criterion is verified by a test that no task writes"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:139"
  - id: F003
    severity: concern
    category: scope
    summary: "`current_unbusy()` has no consumer in this slice"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:195"
  - id: F004
    severity: concern
    category: clarity
    summary: "Task 2.3 leaves the target-level type undecided"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:104"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Tick-level tests in 7.1 and 6.1 overlap with earlier tests"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:261"
  - id: F006
    severity: note
    category: task-size
    summary: "Task 4.2 is the largest task"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:171"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success-criteria coverage and sequencing"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md"
---

# Review: tasks — slice 124

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 5.2 under-specifies the migration of the existing test planners

Task 5.2 says to update the 122 test planners "by driving the project in their fixtures". Those planners use `runnable_unbusy` in `tests/runner/tick_support.py:38`. Its own docstring says it returns more than `ProjectView.ready_unbusy` does, which offers only ready steps. The new guard refuses any node outside `view.current_steps`. Driving the project may therefore not be enough: any node `runnable_unbusy` returns that isn't a ready step will raise `ValueError`.

The affected callers are `tests/runner/test_tenant.py:54`, `test_end_to_end.py:67`, `test_tick.py:65` and the subprocess entry point `crash_entry.py:84`. The task names none of them and does not say whether to change the helper or the fixtures. Task 5.1 also says it updates "existing view construction", and its own success criterion says tests relying on ungoverned planners are migrated there. So 5.1 and 5.2 both claim the same migration.

Fix: assign the migration to one task. List the four callers by file. State whether `runnable_unbusy` should become current-steps-based (for example, delegating to `view.current_unbusy()`) and whether `crash_entry.py` needs fixture rework.

### [CONCERN] Task 3.2's success criterion is verified by a test that no task writes

The 3.2 success criterion says every `SetDesiredState` produced "satisfies 121's shape rules", to be asserted by feeding each into a temporary store's `acknowledge_message` "in Task 3.3". Task 3.3's test list has no such test. The nearest is the monkeypatched `interpret` that returns a shape-violating result, and that tests the reverse case. As written, the 3.2 commit's claim is deferred and nothing in 3.3 delivers it.

Fix: either add a 3.3 test that replays the 3.2 merge table through `acknowledge_message` on `Store.open_temporary()`, or drop the claim from 3.2.

### [CONCERN] `current_unbusy()` has no consumer in this slice

The LLD (D7) adds `ProjectView.desired` and `.current_steps` and changes `HumanStepPlanner` to read `current_steps`. It does not call for a `current_unbusy()` method. Task 5.1 adds one speculatively for slice 125. Production code never calls the existing `ready_unbusy` (see the comment at `tick.py:180`, the docstring at `decide.py:66` and `test_decide.py:82`). The `HumanStepPlanner` change in 5.3 does not use a busy filter either. The method serves only the test helper discussed above, or 125.

Fix: add it only if the migrated test helper needs it. Otherwise drop it and let 125 add it. Either way, state explicitly that `ready_unbusy` is removed.

### [CONCERN] Task 2.3 leaves the target-level type undecided

The `until_applies(level: StepLevel, step)` signature takes a `StepLevel`, but the rule needs three target kinds: project, initiative and slice. The task says to "define the target level as a small enum or reuse `StepLevel` plus an explicit 'container' notion". Task 3.1 then has to pass the target kind in. A junior AI is left to design the type, and 2.3 and 3.1 could settle on different types.

Fix: specify the parameter. For example, take `is_slice_target: bool`, or the target `Node` kind, and say how project and initiative map to "accepts any step".

### [CONCERN] Tick-level tests in 7.1 and 6.1 overlap with earlier tests

The 7.1 test of a planner that acts on a held step, which faults with a deduplicated `unexpected_fault`, repeats two earlier tests. One is the guard test in 5.2. The other is the 6.1 test of repeated bugs adding no second escalation row. The 7.1 same-intent-twice test also repeats the table rows in 3.2 and the 3.3 `seq`-ordering test. Section 7 is the backfill of Functional Requirements at the tick level, so some overlap is deliberate. Even so, each repeated case adds a stub-tick fixture to maintain.

Fix: keep one tick-level case per Functional Requirement. In 7.1, keep only the production-tuple "held human step blocks nothing" case and the pause/resume sequence. Drop the planner-fault and dedupe case already covered by 5.2 and 6.1.

### [NOTE] Task 4.2 is the largest task

Task 4.2 has effort 4. It covers `Governance`, `governing` and `current_steps`, plus a test list of about ten table cases. It is acceptable because the tests are table-driven over one pure module. If it runs long, split `current_steps` and its ordering test into a follow-on task.

### [PASS] Success-criteria coverage and sequencing

- **Idempotence and order:** tasks 3.2 and 7.1.
- **Hold wins, nearest-target drive and governance as a lookup:** task 4.2.
- **One acknowledgment per intent, with all four rejection codes:** tasks 3.1 to 3.3.
- **Held targets and the `HumanStepPlanner` production behavior:** tasks 5.2 to 5.4, 7.1 and 7.2.
- **Crash safety:** task 3.3.
- **`desired-states` listing:** task 8.1.
- **Contract text and CHANGELOG:** tasks 9.1 and 9.2.
- **Full validation and walkthrough:** task 9.3.

Dependencies run forward with no cycles. Each implementation task carries its tests and ends in its own commit, so commits are spread across the slice. No task waits on the Project Manager. The only `BLOCKED:` path is a failed baseline in 1.1, which is legitimate. The slice states no NFRs, so no load-test or CI task is needed.

### Run Digest

- Response length: 6241 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 286821 / 188274 / 98539 / 6067 / not computed
- Duration: 48.3 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
