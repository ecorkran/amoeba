---
docType: review
layer: project
reviewType: code
slice: lifecycle-model-and-reconciliation
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: imposed
sourceDocument: project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: f325d58135f1deda5c1836949e3f07af024834e6
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: true
turns: 1
promptTokens: 140884
cachedTokens: 12832
cacheWriteTokens: 128050
completionTokens: 4556
durationSeconds: 38.3
costUsd: 0.620539
costBasis: provider
runId: run-20261024-p56-2b1f04ba
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: review-coverage
    summary: "Diff truncated; the omitted part was never read"
  - id: F002
    severity: pass
    category: design
    summary: "Lifecycle reconcile is crash-safe, failure-isolated and well covered"
    location: "src/amoeba/runner/lifecycle/reconcile.py#reconcile"
  - id: F003
    severity: pass
    category: conventions
    summary: "Single definition sites are enforced mechanically"
    location: "src/amoeba/runner/lifecycle/plan_read.py"
  - id: F004
    severity: note
    category: dry
    summary: "Linked-node predicates are repeated across modules"
    location: "src/amoeba/runner/lifecycle/plan_stage.py#_initiatives_with_linked_slices"
  - id: F005
    severity: note
    category: consistency
    summary: "Inconsistent null rendering in the nodes listing"
    location: "src/amoeba/inspection/core.py#node_rows"
  - id: F006
    severity: note
    category: style
    summary: "Minor readability points"
    location: "src/amoeba/runner/lifecycle/steps.py#StepSpec.__post_init__"
  - id: F007
    severity: note
    category: process
    summary: "Review coverage limit"
    location: "unverified"
---

# Review: code — slice 123

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5
**Diff:** truncated: 256000 of 285780 characters reached the model

## Findings

### [CONCERN] Diff truncated; the omitted part was never read

The diff was 285780 characters; the first 256000 reached the model (review.max_file_size_bytes). The model made no successful tool calls, so the remaining 29780 characters were not reviewed. The model's own verdict was PASS. Raise review.max_file_size_bytes, narrow the diff, or use a tool-enabled model.

### [PASS] Lifecycle reconcile is crash-safe, failure-isolated and well covered

Reconcile applies the rules in a fixed order (orphan, create, block, update, complete). Each rule checks the store before it writes, and the safety checks in `read_checks.py` run first and decide what each rule may touch. Orphaning blocks before it unlinks, so a crash can't leave an unlinked node nobody can find. `test_reconcile_crash.py` fails every k-th write and checks the tree converges to the uninterrupted result, with no duplicate links. Expected `cf` failures (timeout, missing executable, error document) come back as typed answers. Every `try/except` is narrow and has a justifying comment, which meets the exception-handling rule. The one broad except in the runner package stays in the tenant, and the tests pin that.

### [PASS] Single definition sites are enforced mechanically

The `cf` command words, the step values and the `Store.create_node` caller each have one definition site. AST-based guard tests (`test_cf_commands_defined_once.py`, `test_steps.py`) enforce this. Payload keys and `RUNNER_ACTOR` are constants. The new interval default sits in `ProcessSettings`, is validated in `validate_settings`, and is exposed as a CLI flag. This follows the "no scattered values / no magic defaults" rules.

### [NOTE] Linked-node predicates are repeated across modules

`_initiatives_with_linked_slices` re-implements "linked initiatives that have linked slice children". `read_checks._linked_initiatives` and `_linked_slices` already express the same predicates. Reconcile also repeats the `cf.index is not None` and `cf.project == link` filter in `orphaning.py`, `completion.py` and `read_checks.py`. A shared helper on `LifecycleTree`, such as `linked_children`, would keep the definition of "linked" in one place. This doesn't block the slice.

### [NOTE] Inconsistent null rendering in the nodes listing

`parent_id` is rendered as `""` when absent, while the new `cf_index` is `None`, which is a JSON null. The table cell fix in `inspect._cell` handles it, and the tests pin the behaviour. The two columns still follow different conventions.

### [NOTE] Minor readability points

- The nested conditional f-string in the `ValueError` message is hard to read. Two plain messages would be clearer.
- The `PlanStage` class docstring ("once per lifetime state") is garbled.
- `tests/runner/lifecycle/crash_support.py` and `test_reconcile_crash.py` use `Any` heavily. Check this against the strict pyright config, since test code is included in strict checking.

### [NOTE] Review coverage limit

The supplied diff was truncated at the end, in the `tick_support.py` hunk. I judged the later test-support changes only from the visible portions. I inferred behaviour outside the shown hunks (for example `Store.latest_cf_snapshots` and `BLOCKED_STATUSES`) from how it is used here, and didn't open those files.

### Run Digest

- Response length: 3378 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 140884 / 12832 / 128050 / 4556 / not computed
- Duration: 38.3 s
- Cost: $0.62 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
