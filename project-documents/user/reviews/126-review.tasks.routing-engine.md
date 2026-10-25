---
docType: review
layer: project
reviewType: tasks
slice: routing-engine
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/126-tasks.routing-engine.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261024
dateUpdated: 20261024
reviewedSha: 16f8477c4dd42ef557a0dfd63b9f9941987f2219
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 207189
cachedTokens: 103253
cacheWriteTokens: 103930
completionTokens: 6573
durationSeconds: 54.5
costUsd: 0.492592
costBasis: provider
runId: run-20261025-p5-97da57a1
squadronVersion: 0.24.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:93-369"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Small-table test helper is created after the tasks that need it"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:254"
  - id: F003
    severity: concern
    category: task-scope
    summary: "Task 5.2 is overloaded"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:249-257"
  - id: F004
    severity: concern
    category: task-scope
    summary: "Task 6.1 mixes implementation and a long test matrix, and leaves \"tick context\" vague"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:263-274"
  - id: F005
    severity: concern
    category: traceability
    summary: "Task 4.4 and Task 7.2 depart from the slice text without updating it"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:66-67"
  - id: F006
    severity: note
    category: code-structure
    summary: "Task 7.2 may push `tick.py` over the size guideline"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:276-281"
  - id: F007
    severity: note
    category: verification
    summary: "Wheel test may skip, so the criterion is only conditionally proven"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:200"
  - id: F008
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:76-369"
---

# Review: tasks — slice 126

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage is complete

Each success criterion maps to at least one task:
- **Recomputation:** 4.3 and 6.4 (two table versions).
- **Advance:** 6.1 and 6.4.
- **Rerun**, including the `step`-unknown pass-over: 4.2 and 6.1.
- **Escalate:** 4.2 and 6.1.
- **Load refusal:** 3.3, plus the exit-7 CLI test in 5.2.
- **Unknown matching:** 4.2.
- **No route in code:** 4.4.
- **Time bound:** 7.3.
- **Crash and hold:** 6.4.
- **Default table and wheel-build test:** 3.4.
- **CHANGELOG:** 9.1.
- **Walkthrough steps 1–4:** 9.2.

Nothing in the tasks lacks a criterion to trace to. The Task-level additions (split into `reduce.py` and `validate.py`, retiring the stand-in) are needed to meet the criteria and the 300-line limit. The slice states no NFR, so no load-test or CI-gating task is required.

### [CONCERN] Small-table test helper is created after the tasks that need it

Tasks 4.2 (line 220) and 4.3 (line 228) build small tables with `parse_table`. `parse_table` runs `validate.py`, which requires a catch-all and a positive time bound for every `STEP_MAP` pipeline. Every small test table must therefore carry those, so the boilerplate is easy to get wrong or duplicate.

The shared `small_table(...)` helper is only created in Task 5.2, in `tests/runner/routing/table_support.py`. Tasks 3.3, 4.2 and 4.3 would each hand-roll their own tables. Move the helper's creation into Task 3.3, or an earlier test-support task, and have 4.2, 4.3 and 5.2 reuse it.

Dependencies for 4.2 and 4.3 also list only 4.1, though they rely on 3.2's validation through `parse_table`. File order covers this today, but the dependency lines should say so.

### [CONCERN] Task 5.2 is overloaded

Task 5.2 is rated effort 2 but bundles five changes:
- the `runner_tenant()` loading and error translation;
- new `RunnerTenant` fields;
- the plumbing into `ProjectTick`;
- changes to the test constructors (`tick_support.py` and "any other direct constructor callers");
- a factory test group and a separate CLI exit-code test.

Split it into two tasks:
1. Load and validate at start, with the factory and CLI tests.
2. Thread `routing_table` and `amoeba_version` through `RunnerTenant` and `ProjectTick`, plus the helper and constructor updates.

Each would then commit separately.

### [CONCERN] Task 6.1 mixes implementation and a long test matrix, and leaves "tick context" vague

Task 6.1 writes the stage and also covers about nine distinct scenarios in `test_stage.py`, at effort 3. It is the only implementation task not split from its tests.

Its step "set the tick context to the entry's node" does not name the API. The code has `NodeContext` in `runner/faults.py:119`, with `context.set(node_id)` used at `runner/tick.py:203` and `runner/observe.py:119`. The task should name `NodeContext.set(entry.node_id)` and say it is the same pattern as `observe.py`. Otherwise a junior may invent a mechanism. Consider splitting into "implement stage" and "test stage".

### [CONCERN] Task 4.4 and Task 7.2 depart from the slice text without updating it

- **Task 4.4:** the success criterion says `Route` members are compared "only in the evaluator and the effect mapping". The task allows `engine.py` and `validate.py`. The reasoning is sound and written down in the Task-level additions. But the slice design (D-Patterns and Success Criteria) still says otherwise. Add a step to Task 9.1, or a note in Task 4.4, to amend the LLD text.
- **Task 7.2:** the overrun check moves from "after the route stage" (LLD Data Flow and D7) to before `raise_expected_faults`. The contract text in Task 9.1 correctly says to record the actual place. The LLD data-flow diagram should be corrected the same way.

### [NOTE] Task 7.2 may push `tick.py` over the size guideline

Task 6.2 gives a size trigger for `tick.py` (move the view building out past about 330 lines), but 6.3 and 7.2 add more lines to the same file and neither repeats the check. Add "re-check `tick.py` length" to the Success line of 7.2.

### [NOTE] Wheel test may skip, so the criterion is only conditionally proven

The slice requires "a wheel-build test finds it in the package". Task 3.4 allows `pytest.skip` when hatchling is not cached offline. Task 9.2 handles this by recording whether the test ran and re-running it online if it skipped, so the requirement is met. Just make sure that 9.2 step is not dropped.

### [NOTE] Proportionality is acceptable

There are 28 tasks in 9 sections in a single file, for a slice rated 3/5. The count is high but traceable to the slice's components. Splitting `reduce` into outcome and review parts is justified by file size. Commits are spread through the file, and each implementation task without its own commit is paired with the test task right after it. Two spots could be tightened:
- The full case list in Task 3.3 repeats the slice's "Load refusal" list. It is needed, but could point to the LLD list instead of restating it.
- Task 2.1 prescribes type signatures (`VALUE_SETS: Mapping[...]`) that the slice's API Contracts section does not require.

### Run Digest

- Response length: 6229 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 207189 / 103253 / 103930 / 6573 / not computed
- Duration: 54.5 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
