---
docType: review
layer: project
reviewType: tasks
slice: store-contract-changes-for-the-runner
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: fdb01df5231472b1f17a178b0a7a3fdd28c82198
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 202016
cachedTokens: 101330
cacheWriteTokens: 100680
completionTokens: 5050
durationSeconds: 41.7
costUsd: 0.46417
costBasis: provider
runId: run-20261023-p56-87870251
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "StatusEffect would skip update_node_status's \"node is currently blocked\" refusal"
    location: "src/amoeba/store/nodes.py:124-127"
  - id: F002
    severity: concern
    category: completeness
    summary: "`record_routing_decision` is never pinned in `CONTRACT_METHODS`"
    location: "tests/test_public_api.py:120"
  - id: F003
    severity: concern
    category: task-scoping
    summary: "Task 7.2 commits a public method that validates but does not write"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md (Task 7.2 / 7.3)"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Task 2.2 adds public vocabulary and types without exporting them, against the task-level rule"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md (Task 2.2, 4.3, 7.1)"
  - id: F005
    severity: concern
    category: edge-cases
    summary: "BlockEffect on an already-blocked node is unspecified"
    location: "src/amoeba/store/_block_writer.py#_write_block"
  - id: F006
    severity: note
    category: process
    summary: "Test tasks follow their implementation, and commits are spread out"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md"
  - id: F007
    severity: note
    category: coverage
    summary: "Success criteria trace to tasks; no scope creep found"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md:327-348"
  - id: F008
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable for a 3/5 slice"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md"
---

# Review: tasks — slice 121

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] StatusEffect would skip update_node_status's "node is currently blocked" refusal

`update_node_status` does two blocked checks: `_refuse_blocked_status(current.status, ...)` for a node that is already blocked, and the same check for the target status. Task 3.2 keeps both in `nodes.py` and moves only the done checks and the status write into `_write_status`.

Task 7.3 then says `StatusEffect` calls `_write_status` and so gets "the done-is-terminal and unresolved-entry refusals". Task 7.2 adds only the blocked-target check. Nothing refuses a `StatusEffect` on a node that is currently blocked.

That contradicts D5, which says `StatusEffect` "follows `update_node_status`'s rules". It would let a routing decision silently move a node out of a blocked state, and no test in 7.4 would catch it.

Fix: have 3.2 put the current-status blocked check in the shared helper, or have 7.2 or 7.3 call it explicitly. Add a 7.4 case for a `StatusEffect` on a blocked node.

### [CONCERN] `record_routing_decision` is never pinned in `CONTRACT_METHODS`

The task-level addition says each task that adds a public method updates `CONTRACT_METHODS` in the same commit. Task 7.1 pins the five reads. Neither 7.2 nor 7.3, which introduce and complete `record_routing_decision`, pins it. The slice design lists it in its API Contracts table.

Task 9.2's check would eventually catch the omission. By then it breaks the stated per-task rule, and 9.2 is not a place to add code. Add the pin to 7.2 (where the method first appears) or 7.3.

### [CONCERN] Task 7.2 commits a public method that validates but does not write

Task 7.2 is committed as `feat: validate routing decisions` with a public `record_routing_decision` that "does not write yet". This breaks the rule that "a commit never holds untested behavior" and leaves a public contract method that does nothing for one commit.

The 7.2 tests also assert only that exceptions are raised. Task 7.4 then re-asserts the same failures with "writes nothing".

Merge 7.2 into 7.3 and put all the tests in 7.4. If you want the validation kept as its own unit, make it a private `_validate_decision` function in 7.2, with no public method yet. That also settles where the pin belongs.

### [CONCERN] Task 2.2 adds public vocabulary and types without exporting them, against the task-level rule

Task 2.2 creates `AcknowledgmentOutcome`, `Route`, `RoutingDecisionInput`, `RoutingDecision`, `RoutingTableVersion`, `StatusEffect`, `BlockEffect`, `DesiredState`, `SetDesiredState` and `ClearDesiredState`. Exports are deferred to 4.3, 5.1 and 7.1. The "Public API pin" rule says that "any task that adds a public name" updates `__all__` and `EXPECTED_EXPORTS` in the same commit.

Either state in the rule that types defined in 2.2 are exported by the task that first uses them, or move the type definitions into the tasks that use them. Moving them would also shrink Task 2.2, which at effort 4 covers five new or changed modules and is the largest non-compound task.

### [CONCERN] BlockEffect on an already-blocked node is unspecified

The docstring of `_write_block` says the caller has already checked that the node exists and is not blocked. Task 7.3 routes `BlockEffect` straight through `_write_block`. It names no precondition check and no failure mode for a node that is already blocked, and Task 7.4's list has no such case.

An unguarded call could write a second blocked state or fail with a raw integrity error mid-transaction. Specify the check, using whatever `block()` does today, and add a 7.4 case that asserts nothing is recorded.

### [NOTE] Test tasks follow their implementation, and commits are spread out

Each implementation group is followed by its test task and committed together, so every Section 2–8 group ends in a commit. Section 3 commits per task. Task 5.2 inserts a rollback test (the `_execute`-patching pattern), and 5.3 and 7.4 cover the rollback criteria. Dependencies are linear with no cycles.

### [NOTE] Success criteria trace to tasks; no scope creep found

- **Terminal `done`, `journal_issue` refusal, unresolved-entry refusal and the writer-inventory test:** Tasks 3.1–3.4.
- **Acknowledgment outcomes, `intent_for_submission` and the contract suite:** 4.1–4.3.
- **Atomic desired state and rollback:** 5.1–5.3.
- **Project escalation dedup and the direct-SQL index test:** 6.2 and 2.3.
- **Decision transaction, rollback, duplicate entry and table content mismatch:** 7.3–7.4.
- **Migration on a populated v8 store and read-only open at v8:** 2.3.
- **Inspection columns:** 8.1–8.2.
- **Both contract documents:** 9.1–9.2.
- **Verification walkthrough:** 9.3.

No task lacks a traceable criterion. The slice states no NFR, so no load-test or CI-gating task is needed.

### [NOTE] Proportionality is acceptable for a 3/5 slice

Twenty-six tasks in one file for nine decisions, four tables and two documents is heavy but defensible. The split into several files is not needed. Two places are mildly over-specified for a junior reader: the "may be imported from, or defined in" choice in 2.2, and the two-way file split hints in 7.2 and 7.4. Both are low-risk. Task 9.3's step 5 ("tick each criterion") duplicates what 9.3's earlier validation steps already show and could be dropped.

### Run Digest

- Response length: 6364 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 202016 / 101330 / 100680 / 5050 / not computed
- Duration: 41.7 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
