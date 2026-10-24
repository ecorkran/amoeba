---
docType: review
layer: project
reviewType: code
slice: intent-vocabulary
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/124-slice.intent-vocabulary.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: a67b5beaf3d5450becc0030d0f250e30182f630d
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 114792
cachedTokens: 43337
cacheWriteTokens: 71453
completionTokens: 2662
durationSeconds: 24.4
costUsd: 0.322349
costBasis: provider
runId: run-20261024-p56-53bc46f9
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: design
    summary: "Intent pipeline is pure, ordered and atomic"
    location: "src/amoeba/runner/intent/apply.py#apply_pending_intents"
  - id: F002
    severity: pass
    category: design
    summary: "Drive and hold are enforced in `decide`, not left to each planner"
    location: "src/amoeba/runner/decide.py:103-130"
  - id: F003
    severity: note
    category: dry
    summary: "\"project\" target label is stated twice"
    location: "src/amoeba/inspection/desired_states.py:14"
  - id: F004
    severity: note
    category: testing
    summary: "Weak assertions in a few tests"
    location: "tests/runner/intent/test_apply_pending.py:243"
  - id: F005
    severity: note
    category: structure
    summary: "`governance.py` holds two types"
    location: "src/amoeba/runner/intent/governance.py"
---

# Review: code — slice 124

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Intent pipeline is pure, ordered and atomic

`interpret` and `merge_intent` are pure and cover every intent kind. Bad input from the PM comes back as `REJECTED` outcomes with a coded reason, not as exceptions. Each acknowledgment and its row change share one store call. The crash-injection test checks that an intent stays pending after a failure and is applied once on the next call. Reading the row inside the loop means several intents for the same target apply in order. Store failures propagate to the tenant fault boundary.

### [PASS] Drive and hold are enforced in `decide`, not left to each planner

`decide` raises `ValueError` for any action on a node outside `view.current_steps`. Tests cover the held, undriven, excluded and unknown-node cases, and the tick-level fault test shows one escalation across repeated ticks. `HumanStepPlanner` now plans over current steps only. The new test confirms that linking a project escalates nothing.

### [NOTE] "project" target label is stated twice

`PROJECT_TARGET = "project"` repeats `TargetKind.PROJECT.value`. The module avoids importing the Runner on purpose, and `test_the_project_label_matches_the_runner_target_kind` catches any drift. If the inspection layer ever gets a shared constants module, define the value there once.

### [NOTE] Weak assertions in a few tests

`pytest.raises(ValueError)` has no `match=`, so any `ValueError` passes (ruff `PT011`). In `tests/runner/test_tick_governance.py`, `assert step.id == entry.node_id` checks test setup, not behavior. The merge-table tests slice `case[1:3] + case[4:]`; a named tuple or dataclass for `CASES` would be easier to read.

### [NOTE] `governance.py` holds two types

`DesiredStateIndex` and the `Governance` dataclass share a file, which loosely goes against the one-class-per-file guideline. They are small and closely related, so this is acceptable. `LifecycleStep(until)` in `_within_until` raises on a corrupt stored value, which fails loudly as intended.

### Run Digest

- Response length: 2375 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 114792 / 43337 / 71453 / 2662 / not computed
- Duration: 24.4 s
- Cost: $0.32 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
