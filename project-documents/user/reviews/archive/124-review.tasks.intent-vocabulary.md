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
reviewedSha: cb3c09e92041db3b15230b613a505ff6b0403ff6
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 146188
cachedTokens: 105571
cacheWriteTokens: 40613
completionTokens: 3866
durationSeconds: 30.9
costUsd: 0.212483
costBasis: provider
runId: run-20261024-p56-53bc46f9
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Tasks 5.2 and 5.3 depend on the apply stage that Task 6.1 wires, so their commits cannot be green"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:206"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 5.1's success criteria describe a behavior change that does not happen until later tasks"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:210"
  - id: F003
    severity: concern
    category: traceability
    summary: "Task 7.1's commit message and title promise idempotence, which the task does not test"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:274"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Several tasks are granular enough to merge"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md:162"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Coverage of the slice's functional success criteria"
    location: "project-documents/user/tasks/124-tasks.intent-vocabulary.md"
---

# Review: tasks — slice 124

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [FAIL] Tasks 5.2 and 5.3 depend on the apply stage that Task 6.1 wires, so their commits cannot be green

- Task 5.1 defines `drive_project`, which submits a project-level drive intent through the inbox "so the next tick applies it".
- Task 5.2 requires every store-ticking test to call `drive_project` before the tick. It also changes `runnable_unbusy` to read `view.current_steps`.
- Task 5.3 makes `HumanStepPlanner` read `view.current_steps` and tells the 123 human-step tests to drive the project in their setup.
- The tick does not apply intents until Task 6.1 replaces the `# [apply intents - slice 124]` slot. Until then the intent stays pending and the index is empty.
- Both tasks would then see no current steps, and the migrated 122 and 123 tick tests would fail. Their success criteria ("`uv run pytest tests/runner -q` passes") cannot be met.
- Fix: move the apply wiring ahead of 5.2.
  - Split 6.1 into two parts. The first covers `apply_pending_intents` at the top of `run` and passing the index from one read. It depends only on 3.3 and 5.1, and is tested with a stub planner.
  - The second part is the "driven initiative blocks `architecture` in one tick" test. It stays after 5.4.
- Alternative: have `drive_project` write the desired-state row directly in the store until the apply stage lands. The slice's own apply path would then go unused by those tests.
- Task 6.1's dependency on 5.4 is also looser than it needs to be.

### [CONCERN] Task 5.1's success criteria describe a behavior change that does not happen until later tasks

- Task 5.1 says tests "that rely on ungoverned planners … now use the helper to drive the project".
- In 5.1 the guard does not exist and `HumanStepPlanner` still reads `ready_steps`, so no existing test should change behavior. The migration belongs to 5.2 and 5.3.
- Restate 5.1 as a pure refactor, with the existing tests passing unchanged apart from the `ProjectView` construction. This also keeps its `refactor:` commit type honest.

### [CONCERN] Task 7.1's commit message and title promise idempotence, which the task does not test

- The commit is `test: prove idempotence and hold through the tick`, but the task body covers only hold and the guard.
- The Section 7 preamble says idempotence is already proven in 3.2 and 3.3.
- Rename the commit to cover hold only, for example `test: prove hold through the tick`.

### [CONCERN] Several tasks are granular enough to merge

- Task 4.1 (`DesiredStateIndex`, two methods) is trivial on its own and its tests are a few lines. Merge it into 4.2, or have 4.2 build it.
- Task 2.3 (`TargetKind` and `until_applies`, a single predicate) can fold into 2.2. It already edits the same file and test file.
- Task 3.3 has seven test bullets. The test that every `applied` case in 3.2's table is accepted by the store overlaps the per-outcome store test. Collapse them into a single parametrized test that seeds the current row and asserts the stored row.
- Task 5.2 asks the junior to record the migrated test files in the commit message. That detail is not needed by any success criterion.

### [PASS] Coverage of the slice's functional success criteria

- Idempotence and order: 3.2, 3.3.
- Hold wins, nearest-target drive resolution, and governance as a pure lookup: 4.2, 4.3, 7.1.
- One acknowledgment per intent, with every outcome and every rejection code: 3.1 to 3.3.
- Held targets issue nothing new, and a held human step is not blocked: 5.2, 5.3, 7.1.
- Observe continuing under hold: 7.2.
- `HumanStepPlanner` in production, quiet linking, and drive blocking `architecture`: 5.4, 6.1, 7.2.
- Crash safety: 3.3.
- Technical and integration requirements: 9.3.
- Contract text and CHANGELOG: 9.1, 9.2.
- Walkthrough steps 2–4: 9.3.
- No task falls outside a success criterion. The slice states no NFR, so no load test or CI gating task is required. Commits are spread one per task across the file.

### Run Digest

- Response length: 4399 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 146188 / 105571 / 40613 / 3866 / not computed
- Duration: 30.9 s
- Cost: $0.21 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
