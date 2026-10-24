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
reviewedSha: 65a6b279ec4d8602394d63ee67079d9f93d0025d
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 120689
cachedTokens: 11222
cacheWriteTokens: 109463
completionTokens: 6714
durationSeconds: 52.9
costUsd: 0.506931
costBasis: provider
runId: run-20261024-p56-2b1f04ba
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are fully covered, with tests alongside implementation"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md"
  - id: F002
    severity: concern
    category: interface-design
    summary: "`reconcile` returns only \"wrote something\", but 9.2 needs to know whether the read failed"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:271"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 9.2 is too large for one junior task"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:360-371"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 8.3 bundles the create rule with unrelated deliverables"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:297-309"
  - id: F005
    severity: note
    category: task-sizing
    summary: "Task 8.6 holds the whole-reconcile crash-repair test"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:340"
  - id: F006
    severity: note
    category: clarity
    summary: "Task 9.2 does not say how `linked_slice_initiatives` is computed"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:233"
  - id: F007
    severity: note
    category: task-sizing
    summary: "Tasks 2.2 and 4.1 are small enough to merge into neighbours"
    location: "project-documents/user/tasks/123-tasks.lifecycle-model-and-reconciliation.md:85-93"
---

# Review: tasks — slice 123

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are fully covered, with tests alongside implementation

- **Linking, new slice, rename, renumber/move, completed slice leaving the plan:** covered by 8.2, 8.3, 8.5 and 9.2.
- **Bad-read and no-plan handling:** 6.3, 8.1, 8.2 and 8.6.
- **Cut-off and early reads:** 6.4 and 9.2.
- **Human steps:** 10.1.
- **Predecessors and ready steps:** 5.3 and 5.4.
- **Deferred, deprecated and unknown status:** 8.3 and 8.4.
- **Crash and fault during reconcile:** 8.6 and 9.3.
- **Technical and integration requirements:**
  - Migration 010 is covered by 2.1.
  - Fixture-based parser tests are covered by 3.1 and 3.2.
  - The `create_node` guard is in 8.3.
  - Budget coverage is in 9.2.
  - Contract documents and the CHANGELOG are in 11.1 and 11.2.
  - The walkthrough is in 11.3.
- **Test-with pattern:** every implementation task carries its own tests.
- **Commits:** each task commits, so checkpoints are spread throughout.
- **Load tests:** the slice states no NFR, so a load test and CI-gating task are not required.
- **Scope:** nothing traces to no criterion. The `runnable_unbusy` helper and the `cf_call.py` extraction both serve stated requirements.

### [CONCERN] `reconcile` returns only "wrote something", but 9.2 needs to know whether the read failed

- The Section 8 preamble defines `reconcile(...) -> bool` as "whether anything was written".
- Task 9.2 (line 365) says the tick calls `record_complete` or `record_failed` from that outcome. It also says "a read with any slice-level failure counts as failed".
- Several failures are only detected inside reconcile, in Task 8.1's `checked_scope`: a duplicate index, or an empty list while linked nodes exist. They add `plan_read_failed` to `faults`, but the tick can't see them through a bool.
- The closure rule (D8) depends on `record_failed`: the fault must stay open on ticks that skip the read, until a read of that link succeeds. As written, a duplicate-index read could be recorded complete. The fault would then close on the next tick, contradicting the 9.2 test that it "stays open on later ticks".
- Fix: have `reconcile` return a result that states whether the read was clean. Alternatively, make `checked_scope` failure state available to the tick. Name that contract in 8.3 and use it in 9.2.

### [CONCERN] Task 9.2 is too large for one junior task

- It covers five things in one task:
  - tick wiring through `tick.py`, `factory.py` and `tenant.py`;
  - cadence integration;
  - closure semantics;
  - about 15 scenario tests across three test files;
  - budget-coverage extension.
- Split it into two tasks. The first wires the read, reconcile and cut-off behaviour, with the happy-path, interval, early-trigger and cut-off tests plus budget coverage. The second covers failure and closure behaviour (`plan_read_failed` lifecycle, independent link state, dedupe, probe-failed links).
- Task 9.3 already follows that shape and could sit beside the second half.

### [CONCERN] Task 8.3 bundles the create rule with unrelated deliverables

- It introduces the `reconcile` entry point, the create rule and the D6 statuses. It also adds a new `slugs.py` module and the AST-based `create_node` guard test with a self-test, and it carries about ten test groups.
- Move the guard test and its self-test into a small task of its own. It is independent of the create logic, and the guard makes a clean checkpoint. That leaves 8.3 focused on create behaviour.

### [NOTE] Task 8.6 holds the whole-reconcile crash-repair test

The k-th-write crash-repair test exercises all four rules, not just the complete rule. It is correctly placed after the last rule exists. Consider making it its own `test:` task, so the complete-rule commit stays small and the crash test gets its own checkpoint.

### [NOTE] Task 9.2 does not say how `linked_slice_initiatives` is computed

- Task 6.3's `read_plan` needs the set of initiative indexes that already have linked slice nodes, to separate "no plan" from a failure (D8).
- The LLD builds the `LifecycleTree` after reconcile, so that set must come from a pre-read `nodes_for_project` call.
- Task 9.2 should state that the tick computes the set from the store before the read.

### [NOTE] Tasks 2.2 and 4.1 are small enough to merge into neighbours

- 2.2 (inspect index column) could fold into 2.1.
- 4.1 is a behaviour-preserving extraction. Keeping it separate matches the refactor-versus-feat commit convention, so this is optional.

### Run Digest

- Response length: 5495 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 120689 / 11222 / 109463 / 6714 / not computed
- Duration: 52.9 s
- Cost: $0.51 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
