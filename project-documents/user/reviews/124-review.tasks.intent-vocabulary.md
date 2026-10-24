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
reviewedSha: fe6eaf4db541a20c2a5e3760bfe9216538fe22de
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 195741
cachedTokens: 98268
cacheWriteTokens: 97467
completionTokens: 4651
durationSeconds: 37.1
costUsd: 0.447023
costBasis: provider
runId: run-20261024-p56-53bc46f9
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md"
  - id: F002
    severity: pass
    category: accuracy
    summary: "Task-level corrections match the code"
    location: "src/amoeba/runner/factory.py:23"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 4.1 is oversized"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:154-168"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Task 3.3 repeats Task 3.2's table through the store"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:145-146"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Section 7 and Task 6.1 repeat tests from earlier tasks"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:234,248"
  - id: F006
    severity: note
    category: task-sizing
    summary: "Task 5.2 carries a large mechanical test migration"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:204"
  - id: F007
    severity: note
    category: sequencing
    summary: "Section 5 reorder keeps every commit green"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:57"
  - id: F008
    severity: note
    category: clarity
    summary: "Task 2.2 lists `TargetKind` after the tests that precede it"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:97"
---

# Review: tasks — slice 124

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria trace to tasks

- **Idempotence and order:** Task 3.2 covers same-intent-twice, drive-until replacement and pause-then-drive. Task 3.3 covers the `seq` ordering.
- **Hold wins:** Tasks 4.1 and 7.1.
- **Nearest-drive resolution and `until` rank:** Task 4.1.
- **Governance as a pure lookup:** Tasks 4.1 and 4.2.
- **One acknowledgment per intent, with every outcome and every rejection code:** Tasks 3.1 to 3.3.
- **Held targets issue nothing:** Tasks 5.2, 7.1 and 7.2.
- **`HumanStepPlanner` in production, with linking quiet and driving blocks `architecture`:** Tasks 5.3, 6.1 and 7.2.
- **Crash safety:** Task 3.3.
- **Technical requirements:**
  - Contract documents: Task 9.1.
  - CHANGELOG: Task 9.2.
  - Walkthrough and full validation: Task 9.3.
- **Integration requirement, contract suite:** Tasks 7.2 and 9.3.

I found no scope creep. The slice states no NFR, so no load test or CI-gating task is needed.

### [PASS] Task-level corrections match the code

`PRODUCTION_PLANNERS` is in `runner/factory.py`, not `tenant.py` as the LLD says. The slot comment is at `src/amoeba/runner/tick.py:96`. `self.wrote` and `_decide` exist in `tick.py`. `runnable_unbusy` is in `tests/runner/tick_support.py:38`. Tests that pin the empty tuple (`tests/runner/test_factory.py:31`, `tests/runner/lifecycle/test_human_steps.py:90`) are covered by Task 5.3.

### [CONCERN] Task 4.1 is oversized

Task 4.1 is rated Effort 4, the highest in the file. It bundles `DesiredStateIndex`, `drives_anything`, the `Governance` dataclass and `governing` (path walk, nearest-drive, `until` rank, hold). It also adds two test files and a possible `tree.py` accessor. The index is small and independent of the path logic, so a junior AI could stall on the combined task. Split it: the index and `drives_anything` with their tests in one task, then `governing` in the next. `current_steps` (Task 4.2) can stay separate.

### [CONCERN] Task 3.3 repeats Task 3.2's table through the store

Two tests in Task 3.3 go beyond what the success criteria need:
- **The store-acceptance test** re-runs every `applied` row of Task 3.2's table through a temporary store. The crash test and the each-outcome test already exercise `acknowledge_message` with real rows. Cut this to a small set of store-shape edge cases: hold-only, drive-with-`until`, and a deleting `resume`. Alternatively, parametrize one shared case table that 3.2 and 3.3 both use.
- **The `ValueError` propagation test** monkeypatches `interpret`. Task 6.1 already tests the monkeypatched-`interpret` fault path through the tick. Keep only one of the two.

### [CONCERN] Section 7 and Task 6.1 repeat tests from earlier tasks

- **Task 7.1, second bullet.** The guard raising for a held step is already proven at `decide()` level in Task 5.2. The `unexpected_fault` and dedupe path is already proven in Task 6.1. The only new thing here is "a held human step blocks nothing under the production tuple", and Task 5.3's "driven and paused plans nothing" test covers that at planner level. Reduce this bullet to the single tick-level production-tuple check.
- **Task 6.1.** The `STORE_FAILURES` exit and "repeating bug adds no second escalation" are 122's behaviors, and 122's own tests cover them. Keep the one test that proves apply is inside the fault boundary, and drop the other two.
- **Task 7.2.** It bundles two unrelated tests, observe-under-hold and linking-is-quiet. Consider moving the linking test into 7.1 or 6.1 to avoid a two-line task.

### [NOTE] Task 5.2 carries a large mechanical test migration

Adding the guard forces every existing 122 and 123 test planner to be migrated (`runnable_unbusy`, `view_for`, `drive_project`). The task gives a workable discovery method (`grep`, then run `tests/runner` and read the `ValueError`s). The scope is open-ended, but Effort 2 may understate it. If the migration touches many files, split it into "add the guard and its tests" and "migrate existing tests". The guard cannot land with a green suite without the migration, so the two must stay adjacent. Keeping them in one commit, as written, is acceptable.

### [NOTE] Section 5 reorder keeps every commit green

The tasks put the view, guard and planners (Section 5) before the tick's apply stage (Section 6). `drive_project` calls `apply_pending_intents` directly, so no step needs the tick stage early. 5.1 adds an interim `desired_states` read in `_decide`, and 6.1 removes it, so each commit leaves the suite green. There are no circular dependencies.

### [NOTE] Task 2.2 lists `TargetKind` after the tests that precede it

`TargetKind` and `until_applies` come after the body-model tests in the checklist, but they live in the same module and commit. This is fine as written. Reordering the bullets so definitions come before their tests would read more cleanly.

### Run Digest

- Response length: 5883 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 195741 / 98268 / 97467 / 4651 / not computed
- Duration: 37.1 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
