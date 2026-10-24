---
docType: review
layer: project
reviewType: code
slice: lifecycle-model-and-reconciliation
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/123-slice.lifecycle-model-and-reconciliation.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: e61c93e349d8eccfbf522c41fad2f34cc947c2fb
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: true
turns: 1
promptTokens: 141068
cachedTokens: 3232
cacheWriteTokens: 137834
completionTokens: 5262
durationSeconds: 45.1
costUsd: 0.66587
costBasis: provider
runId: run-20261024-p56-2b1f04ba
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "A failed read's retry behavior contradicts its documentation and is inconsistent"
    location: "src/amoeba/runner/lifecycle/cadence.py#PlanReadSchedule.record_failed"
  - id: F002
    severity: concern
    category: design
    summary: "Failure state is tracked in two places, and one copy is unused"
    location: "src/amoeba/runner/lifecycle/cadence.py#PlanReadSchedule.last_failed"
  - id: F003
    severity: concern
    category: design
    summary: "`ProjectView` no longer excludes nodes with unresolved journal entries, and the guarantee moved to a test helper"
    location: "src/amoeba/runner/tick.py#ProjectTick._decide"
  - id: F004
    severity: concern
    category: design
    summary: "Node insert is split into two statements to suit test staging"
    location: "src/amoeba/store/nodes.py:93-98"
  - id: F005
    severity: note
    category: style
    summary: "Minor style and DRY items"
    location: "src/amoeba/runner/lifecycle/completion.py:30"
  - id: F006
    severity: pass
    category: testing
    summary: "Exception handling, typing and test coverage"
    location: "src/amoeba/runner/cf_call.py"
---

# Review: code — slice 123

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5
**Diff:** truncated: 256000 of 274863 characters reached the model

## Findings

### [CONCERN] A failed read's retry behavior contradicts its documentation and is inconsistent

`record_failed` sets `trigger_pending = False` and leaves `last_complete_at` unchanged. Its docstring and the `PlanStage` docstring both say "the link stays due". Two cases show the code doesn't do that.
- **Failure after an early read:** a read triggered early by a changed snapshot can fail before the interval has elapsed. The trigger is then consumed, `due()` goes back to the interval check, and the retry waits up to `plan_read_interval_seconds`.
- **Failure on a link that has never completed a read:** `last_complete_at` is still `None`, so `due()` returns True on every tick. A persistently broken link then spawns `cf` subprocesses on every tick, with no backoff, at the idle interval of about 1s.

Decide the intended retry policy and make `record_failed` match it, for example by recording a last-attempt time. Add a test for a failure after an early trigger.

### [CONCERN] Failure state is tracked in two places, and one copy is unused

`PlanReadSchedule` keeps `last_failed` state with a public accessor. `PlanStage._failures` separately holds the faults to replay. Nothing in production reads `last_failed`, and only the cadence tests do. This violates "one value, one source" and invites drift between the two. Either drive the replay from the schedule or drop the flag. `due()` also mutates state (it creates the link entry and consumes snapshot ids), which makes a query method surprising.

### [CONCERN] `ProjectView` no longer excludes nodes with unresolved journal entries, and the guarantee moved to a test helper

The old `_decide` removed any node with an unresolved journal entry before planners saw it. The new view exposes the whole tree. The "not busy" rule now lives in `tests/runner/tick_support.py::runnable_unbusy`, which filters on `view.in_flight` and not on unresolved entries. That is different semantics.

The rewritten test `test_a_node_with_an_unresolved_entry_is_not_offered_to_decide` no longer checks the production guarantee. It checks the helper. This is safe today only because `PRODUCTION_PLANNERS` is empty. Slice 125 must re-add the filter, and nothing mechanical enforces that. Add a tracking issue or an xfail test that pins the requirement.

### [CONCERN] Node insert is split into two statements to suit test staging

`create_node` runs `INSERT_NODE` and then `UPDATE_NODE_CF_INDEX`. The comment in `sql.py` says this is so `INSERT_NODE` stays the version-1 column set for tests that stage old-version stores. Production code is shaped around a test fixture, and there is a window with a node row but no index. The transaction covers it, so the risk is low. Prefer a single insert, and let the migration tests build their old-version rows with their own SQL.

`update_cf_reference` now writes `cf.index` unconditionally. Any caller that builds a fresh `CFReference` without an index will silently unlink the node. The new callers are careful (`dataclasses.replace`, or explicit `index=None` in the orphan rule). The footgun is still in the API, and a `store` test should pin it.

### [NOTE] Minor style and DRY items

- `RESOLVED_BY: str = "runner"` should be `Final`.
- The `" ".join(str(error).split())` normalization is duplicated in `probes.py::_initiatives_problem` and `plan_read.py::_one_line`.
- `read_checks.py` and `orphaning.py` rely on the unread-slice-list case (a failed list for initiative A) when judging "moved" slices listed under initiative B. A slice that is still in A's failed list is treated as moved and orphaned if B lists it. That is a rare edge case, but it needs a test or a comment.

### [PASS] Exception handling, typing and test coverage

- Every `try/except` catches a specific type and carries a justification comment (`TimeoutExpired`, `OSError`, `PlanParseError`, `JSONDecodeError`, `ValidationError`).
- Plan reads return answers instead of raising for expected CF failures.
- `cf` command words are defined once, and a guard test enforces it.
- The migration and unique link index are covered by tests.
- Crash-repair is covered by an exhaustive parametrized test that fails each write in turn.
- Budget cut-off, cadence, safety rules and each reconcile rule have focused tests.
- Each `cf` call runs in a subprocess with a timeout, so there is no event-loop blocking, and tick code is synchronous.

### Run Digest

- Response length: 4872 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 141068 / 3232 / 137834 / 5262 / not computed
- Duration: 45.1 s
- Cost: $0.67 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
