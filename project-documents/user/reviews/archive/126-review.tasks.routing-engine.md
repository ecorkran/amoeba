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
reviewedSha: 79795258f6c051c280a56b59e59c2a5443a5adc6
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 111065
cachedTokens: 11222
cacheWriteTokens: 99839
completionTokens: 7968
durationSeconds: 60.2
costUsd: 0.48097
costBasis: provider
runId: run-20261025-p5-97da57a1
squadronVersion: 0.24.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every slice success criterion maps to a task"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 3.2 validation conflicts with the \"Route compared only in engine.py\" test in Task 4.6"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:177-189"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Task count is heavy for a 3/5 slice; thin test tasks can merge"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:94-109"
  - id: F004
    severity: note
    category: commit-checkpoints
    summary: "\"One commit per task\" conflicts with implementation tasks that carry no commit"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:55"
  - id: F005
    severity: note
    category: testing
    summary: "The wheel-contents test can skip silently"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:204"
  - id: F006
    severity: note
    category: design-fidelity
    summary: "Overrun check placement departs from the slice's data-flow diagram"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:66"
  - id: F007
    severity: note
    category: coverage
    summary: "A walkthrough-named test is missing from Task 4.5"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:243"
---

# Review: tasks — slice 126

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Every slice success criterion maps to a task

I checked each Functional, Technical and Integration requirement in the slice design against the tasks. Each has a covering task:
- **Recomputation across table versions:** 4.5 and 6.5.
- **Advance:** 6.5 (`test_advance_dispatches_successor_next_tick`).
- **Rerun and the rerun limit:** 4.2 and 6.2.
- **Escalate cases:** 6.2.
- **Load refusal:** 3.3 and the 5.2 CLI exit-7 test.
- **Unknown inputs:** 4.2.
- **No route chosen in code:** 4.6.
- **Time bound:** 7.1 and 7.3.
- **Crash and hold:** 6.5.
- **Default table and wheel contents:** 3.4.
- **Gates and CHANGELOG:** 9.2 and 9.3.
- **Plan and arch edits:** 1.1.

I found no scope creep. Every task traces to a slice decision (D1–D9), the Verification Walkthrough, or a documented task-level addition.

### [CONCERN] Task 3.2 validation conflicts with the "Route compared only in engine.py" test in Task 4.6

Task 3.2 puts per-route parameter rules in `validate.py`:
- `rerun` needs `max_attempts`.
- `escalate` needs `judge_eligible`.
- `advance` takes neither.
- `advance` and `rerun` must name `outcome: completed`.

These rules branch on `Route` members. Task 4.6 (line 248) asserts that `Route.<member>` appears in a comparison, `match` case or mapping key only in `runner/routing/engine.py`. As written, 4.6 fails once 3.2 lands, or it gets weakened to pass.

Moving the checks into `engine.py` doesn't work either. `engine.py` depends on `table.py` (4.1 depends on 3.1), and `table.py` calls `validate.py`, so that would create an import cycle.

The tasks need to say where route-specific parameter rules live. One option is a per-route spec mapping defined once in `engine.py` or a small neutral module, which `validate.py` reads without comparing members. The other is to scope the 4.6 test explicitly to exclude validation. This conflict needs fixing before 3.2 is implemented.

### [CONCERN] Task count is heavy for a 3/5 slice; thin test tasks can merge

The file has 34 tasks for a slice rated effort 3/5. Several split a small unit from its tests without a reason:
- **2.1 and 2.2:** 2.2 only checks that the vocabulary sets contain `UNKNOWN` and that the constructor rejects bad values. Merge it into 2.1 as one commit.
- **4.3 and 4.4 with 4.1 and 4.2:** `effect_for` is a small pure function in the same `engine.py` file. Fold 4.3 and 4.4 into 4.1 and 4.2.
- **9.1 and 9.2:** the CHANGELOG entry is 1–2 lines. Merge it into 9.1.
- **6.2 and 6.5:** the store-level stage tests overlap the tick-level tests. The 6.2 cases are still worth keeping, but the file doesn't need both as separate test tasks.

Some steps also dictate more than the slice requires. Task 2.3 fixes the `OutcomeEvidence` field list, and 3.1 names the exact exception types to catch. Task 9.3 includes a generic line-count audit and a "coverage check" that restate the repo-wide rules. These can be trimmed to a pointer. Keep the single task file.

### [NOTE] "One commit per task" conflicts with implementation tasks that carry no commit

The cadence note says one commit per task. Tasks 2.1, 2.3, 2.5, 2.7, 3.1, 3.2, 4.1, 4.3, 6.1, 7.2 and 8.1 have no commit step. Each is committed with the test task that follows it, which satisfies the test-with pattern. Commits are spread through all nine sections, not batched at the end. Reword the note to say implementation tasks commit with their test task.

### [NOTE] The wheel-contents test can skip silently

The slice's Technical Requirements say a wheel-build test finds `default.yaml` in the package. Task 3.4 calls `pytest.skip` when `hatchling` isn't cached offline. The skip gives a reason, but the requirement goes unverified in that environment. Task 9.3 should record whether the test ran or skipped, and run it with network access if it skipped.

### [NOTE] Overrun check placement departs from the slice's data-flow diagram

The slice puts the overrun check after the route stage (D7 and the Data Flow diagram). Task 7.2 puts it beside `watch_pointers`, before `raise_expected_faults`, so the existing raise path records it. The reasoning holds: routing touches only finished entries and the check reads only in-flight ones. The task file documents the change, and 9.1 must describe the actual order in the contract text. No action beyond that.

### [NOTE] A walkthrough-named test is missing from Task 4.5

The Verification Walkthrough cites `test_decision_recomputes_from_stored_version` as an example name. Task 4.5 describes the cases but doesn't name that test. Add it so the walkthrough's expected test names exist.

### Run Digest

- Response length: 5263 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 111065 / 11222 / 99839 / 7968 / not computed
- Duration: 60.2 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
