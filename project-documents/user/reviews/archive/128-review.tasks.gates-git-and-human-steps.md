---
docType: review
layer: project
reviewType: tasks
slice: gates-git-and-human-steps
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261026
dateUpdated: 20261026
reviewedSha: 5bfb3d63c20185340717c824bc1a5cebfd3dbc37
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 120142
cachedTokens: 11222
cacheWriteTokens: 108916
completionTokens: 10145
durationSeconds: 78.2
costUsd: 0.539055
costBasis: provider
runId: run-20261026-p5-c2177fb8
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Dependency lists omit real prerequisites"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:183-189"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 7.2 depends on a type that task 8.1 defines"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:232-237"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 7.4 is too large"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:246-252"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "No test asserts the dispatch evidence or the recorded target"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:134"
  - id: F006
    severity: concern
    category: task-clarity
    summary: "The \"git calls are status and merge-base only\" check in 10.1 is vague"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:307"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Section 11 is split finer than its work needs"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:320-340"
  - id: F008
    severity: note
    category: documentation
    summary: "The task file overrides the LLD without amending it"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:50"
---

# Review: tasks — slice 128

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria trace to tasks

- **Clean tree and branch:** tasks 7.2 and 7.5.
- **Gate at the outcome:** 5.1–5.3 and 6.1–6.2.
- **Gate at dispatch:** 7.5.
- **Hatches:** 5.1 and 6.2.
- **Issue #15:** 8.1–8.2. The commit carries `Fixes #15`, and 11.1 updates the substrate guide.
- **Merge policy:** 3.1–3.3.
- **Merge observation:** 9.1–9.2.
- **No git writes:** 2.2 and 10.1.
- **Technical requirements:**
  - Both guard tests (git only in `git_read.py`, and the `decide()` guard) are in 10.1 and 7.5.
  - The captured-fixture tests are in 2.1 and 4.1.
  - Budget coverage is in 10.1.
  - The contract docs and CHANGELOG are in 11.1 and 11.2.
  - The full suite and the 100 contract suite are in 11.3.
- **Scope:** the extra modules (`checks.py`, `stage.py`, `dispatch_reads.py`, `cf_reads.py`) and the `journal_extra`/`payload_extra` fields are placement or plumbing for LLD decisions, not new scope.
- **Load tests:** the slice states no load or throughput NFR, so none is needed. Its only bound is the tick deadline, which 10.1 covers.

### [CONCERN] Dependency lists omit real prerequisites

The file says a `BLOCKED:` task lets later tasks continue once their listed dependencies are checked off. So the lists must be complete, and several are not:
- **5.2** (lines 183–189) lists 4.4 and 5.1. It runs `git status` for `implementation` through `git_read`, which is built in 2.2. 2.2 is not reachable through 4.4 (which depends on 2.1 and 4.1), 5.1 or 4.3.
- **7.3** (line 241) runs `read_dispatch_facts` tests "with the stub `cf`", which needs 4.4's stub modes and rig helpers. 4.4 is not listed or reachable.
- **7.4** (lines 246–252) edits `GateStage`, which 5.3 creates, and uses 4.4's helpers in the rig update. Neither 5.3 nor 4.4 is reachable from 3.3 or 7.3.
- **7.5** uses the stub through 7.4, so it is covered once 7.4 is fixed.

Add the missing dependencies.

### [CONCERN] Task 7.2 depends on a type that task 8.1 defines

`entry_gate(step, active_slice, slice_index, accepted)` in 7.2, and `check_candidate(..., accepted)` in 7.3, take the `AcceptedOutcome` result of `accepted_by_pm`. 8.1 defines that type and comes later. 7.4 then says `Disagreement` is treated as `Ok` until 8.2, so nothing passes a real value before 8.1.

Either move 8.1 (which depends only on 1.1) ahead of 7.2, or have 7.2 take a plain boolean or optional that 8.2 later narrows. State which in the task.

### [CONCERN] Task 7.4 is too large

7.4 does four things in one commit:
- adds `GateStage.check_dispatch`;
- rewires `DispatchPlanner`, `ContinuationPlanner` and `resolutions/act.py`;
- adds the `decide()` guard;
- updates every shared tick rig and the crash harness, then fixes whatever the full suite breaks.

The guard makes every existing launch test fail until the rigs are right, so a junior has no checkpoint between the pieces.

Split it. First, a rig-only task: a clean git repository on `main` plus a stub gate answer. It is harmless before any check exists, so the suite stays green. Second, the stage, planners and journal evidence. Third, the guard, last.

9.2 (`observe_merges`, `HumanStepPlanner` and about ten real-git tick tests) is borderline. It could be split at the `HumanStepPlanner` change.

### [CONCERN] No test asserts the dispatch evidence or the recorded target

The slice criterion for `merge_policy: auto` says the entry records `auto` and the target. Task 3.3 tests only `merge_policy`. Task 7.4 adds `target` and `dispatch_check` to `journal_extra`. Neither 7.4 nor 7.5 asserts that a `P6` entry holds `target`, or that any launch or resume holds `dispatch_check` with the evidence keys. A reissue copying `merge_policy` and `target` is also untested for `target`.

The hatch criterion says `amoeba inspect checks --node <slice>` shows the design path and examined values. Only 8.2 exercises `inspect checks`, and only for the disagreement record.

Add these assertions to 7.5 and to the 5.3 or 6.2 tick tests.

### [CONCERN] The "git calls are status and merge-base only" check in 10.1 is vague

The third bullet says "the stub log or a recording runner over the gates tick tests". It names no mechanism and does not say where the recording runner is injected. A junior cannot tell whether this is one fixture or a change to every tick test. The runtime allowlist (2.2) and the source test (first bullet) already cover most of the criterion.

Pick one mechanism. For example, wrap the injected runner once in a shared `tests/runner/gates/` fixture that records subcommands, and add a final assertion. Alternatively, drop the bullet and note that 2.2's allowlist test plus the source test satisfy the criterion.

### [CONCERN] Section 11 is split finer than its work needs

- 11.2 is a one-line CHANGELOG edit (effort 1) that belongs with the contract text in 11.1.
- 11.3 makes no change of its own and says "Commit with Task 11.4". It should be merged into 11.4.

Merging them leaves two tasks, each with a real commit. The slice has 29 tasks for a 3/5 slice, so trimming the trivial ones is worthwhile.

### [NOTE] The task file overrides the LLD without amending it

The file says that where its "Task-level additions" differ from the LLD, the task file wins and the LLD is not amended. The `launch_candidates(current, facts, holders)` signature, the `payload_extra` and `journal_extra` fields, and the `complete_step` rename all differ from or extend the LLD. These are reasonable placement decisions. But 129 and the code review will read the LLD's `launch_candidates(tree, desired, entries, held)` and `_complete` references and find them stale. Consider a short "as built" note in the LLD after implementation.

### Run Digest

- Response length: 6886 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 120142 / 11222 / 108916 / 10145 / not computed
- Duration: 78.2 s
- Cost: $0.54 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
