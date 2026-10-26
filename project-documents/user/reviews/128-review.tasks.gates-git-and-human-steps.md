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
reviewedSha: 772f7e23eed2c58451afb821d954db4d776cf9b5
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 226445
cachedTokens: 112988
cacheWriteTokens: 113451
completionTokens: 6354
durationSeconds: 48.6
costUsd: 0.529465
costBasis: provider
runId: run-20261026-p5-c2177fb8
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 7.1 needs a type that only Task 9.1 creates"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:224-231"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Task 7.5 bundles the behavior change with a suite-wide rig rewrite"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:254-259"
  - id: F003
    severity: concern
    category: proportionality
    summary: "\"This file wins\" creates a second source of truth for the design"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:48-71"
  - id: F004
    severity: concern
    category: coverage
    summary: "The hatch criterion \"`inspect checks` shows each check with design path and examined values\" has no test"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:216"
  - id: F005
    severity: concern
    category: coverage
    summary: "The `target` on a `P6` entry is deferred past the task that adds the other journal keys"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:133-136"
  - id: F006
    severity: note
    category: scope
    summary: "Stub `cf` `list slices` already exists"
    location: "tests/cf_stub.py:15-18"
  - id: F007
    severity: note
    category: nfr
    summary: "Load-test and CI-gating checks do not apply"
    location: "project-documents/user/slices/128-slice.gates-git-and-human-steps.md:552"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks with no scope creep"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:77-337"
  - id: F009
    severity: pass
    category: process
    summary: "Test-with pattern and commit distribution hold"
    location: "project-documents/user/tasks/128-tasks.gates-git-and-human-steps.md:54"
---

# Review: tasks — slice 128

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 7.1 needs a type that only Task 9.1 creates

Task 7.1 lists only Task 1.1 as a dependency. It adds `ProjectView.merge_observations` to `decide.py`, typed `Mapping[str, MergeObservation]`. `MergeObservation` is created in Task 9.1 (`runner/gates/merge.py`). A junior AI working in file order has no definition to import when it reaches 7.1. Either define `MergeObservation` in 7.1 (for example, in `predispatch.py` or a small shared module) and have 9.1 reuse it. Or move the `merge_observations` field from 7.1 to 9.2, which already edits the view.

### [CONCERN] Task 7.5 bundles the behavior change with a suite-wide rig rewrite

Task 7.5 changes both planners, adds the `decide()` guard and edits `runner/resolutions/act.py`. It also rewrites the shared tick rigs, the crash harness and the stubbed gate answers, then fixes whatever else fails. The rig work is open-ended because it depends on how many earlier tests break. Splitting it would keep the suite green only if the guard and planner filter and the rig update are done together, so keep one commit. But make the rig update its own sub-section with an explicit list of the rig files, and say that a failure outside the rigs and the planners is `BLOCKED:`. Tasks 5.3 (record.py, finish.py, `GateStage`, tick wiring and a suite fix-up) and 5.2 (five reads, `OutcomeObservation` and `gate_state_at_exit`) are similarly heavy. Their Effort of 3 is borderline.

### [CONCERN] "This file wins" creates a second source of truth for the design

The "Task-level additions" list overrides the LLD in several places:
- the `launch_candidates` signature;
- new modules (`gates/checks.py`, `gates/stage.py`, `gates/dispatch_reads.py`, `gates/accepted.py`);
- `journal_extra` and `payload_extra` on the actions;
- where the exit and entry gate constants live.

Task 1.1 adds one pointer line to the LLD, so a reader of the LLD still sees the old signatures. Some of these overrides are driven by the 300-line limit, so they are legitimate. The cost is that Phase 7 review will compare the code against a design that no longer matches it. Fold the changed interfaces into the LLD's "API Contracts" and "Component Structure" in Task 1.1 instead of adding only a pointer. Keep only the genuinely task-local notes in this file.

### [CONCERN] The hatch criterion "`inspect checks` shows each check with design path and examined values" has no test

The Hatches success criterion requires `amoeba inspect checks --node <slice>` to show each hatch check with the design path and the values examined. Task 8.2 checks `inspect checks` only for the disagreement record. Task 6.2's hatch tests assert escalation and `vacuous` standing but never the inspect output. Task 5.1 tests `examined` content, but not through the CLI. Add one `inspect checks --node` assertion to Task 6.2's `review: none` test.

### [CONCERN] The `target` on a `P6` entry is deferred past the task that adds the other journal keys

The Merge policy criterion requires that `auto` records the policy "and the target". Task 3.3 adds `PARAM_TARGET` and the `journal_extra` plumbing, but records only `merge_policy`. `target` is not written until Task 7.5, and is not tested until Task 7.6. This is workable, because the target comes from the pre-dispatch read, but the "Success" line in 3.3 and the test list should not imply otherwise. Note in 3.3 that `target` and `dispatch_check` arrive in 7.5, so the 3.3 tests are not expected to cover them.

### [NOTE] Stub `cf` `list slices` already exists

The slice design lists `list slices <i> --json` among the stub's new modes. Task 4.4 correctly adds only `status --json` and `config get --json`, because the stub already answers `list slices` (123). This is not a gap. The slice design's wording is stale.

### [NOTE] Load-test and CI-gating checks do not apply

The slice states a tick-time bound only as a technical requirement ("the tick deadline plus one `tick_call_timeout_seconds`"), not as a performance NFR. Task 10.1 extends the budget-coverage test to drive the new calls. No `tests/load/` task or CI-wiring task is needed.

### [PASS] Success criteria trace to tasks with no scope creep

Each criterion group has implementation and test tasks:
- **Clean tree and branch:** 7.2, 7.6.
- **Gate at outcome:** 5.2, 5.3, 6.2.
- **Gate at dispatch:** 7.3, 7.6.
- **Hatches:** 5.1, 6.2.
- **Issue #15:** 8.1, 8.2 (the commit carries `Fixes #15`).
- **Merge policy:** 3.1–3.3.
- **Merge observation:** 9.1, 9.2.
- **No git writes and the two invariant tests:** 10.1 and the `decide()` guard test in 7.6.
- **Contract text and CHANGELOG:** 11.1.
- **Verification Walkthrough steps 1–5:** 11.2.

I found no task without a matching design decision. The extra files (`checks.py`, `stage.py`, `dispatch_reads.py`) are placement choices, not new behavior.

### [PASS] Test-with pattern and commit distribution hold

Each implementation task carries its tests, and tasks that share a commit are named (3.1 with 3.2, 4.2 with 4.3, 5.2 with 5.3, 6.1 with 6.2, 7.2 with 7.3, 8.1 with 8.2). Commits fall in every section, not at the end. No task writes a merge, which matches the git rules. Dependencies are acyclic, and `BLOCKED:` handling lets independent tasks continue.

### Run Digest

- Response length: 6422 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 226445 / 112988 / 113451 / 6354 / not computed
- Duration: 48.6 s
- Cost: $0.53 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
