---
docType: review
layer: project
reviewType: tasks
slice: network-api
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/109-tasks.network-api-1.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261017
dateUpdated: 20261017
reviewedSha: e5b1908e439d674939e91e52b6f4e261c36dd51a
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 191455
cachedTokens: 97118
cacheWriteTokens: 94331
completionTokens: 4131
durationSeconds: 38.1
costUsd: 0.429025
costBasis: provider
runId: run-20261017-p5-dcc30257
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: task-scoping
    summary: "Task 2.5 bundles too many independent changes into one task"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md"
  - id: F002
    severity: concern
    category: scope-traceability
    summary: "Task 2.5 puts the option-definition locations in the task, not in the LLD"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md"
  - id: F003
    severity: concern
    category: test-sufficiency
    summary: "Task 1.2 asks for a test that may duplicate existing coverage and has a weak criterion"
    location: "tests/test_cli_inspect.py"
  - id: F004
    severity: note
    category: granularity
    summary: "Tasks 1.1 and 1.3 are setup/capture steps with no commit"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md"
  - id: F005
    severity: note
    category: proportionality
    summary: "Task 3.1's \"ask the PM\" guard for file size is appropriate"
    location: "src/amoeba/store/feed.py"
  - id: F006
    severity: pass
    category: sequencing
    summary: "Migration sequencing and byte-identical gate"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md"
  - id: F007
    severity: pass
    category: commit-checkpoints
    summary: "Test-with pattern and commit distribution"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md"
  - id: F008
    severity: pass
    category: accuracy
    summary: "File and path references check out against the repo"
    location: "tests/cli/test_inspect_evidence.py"
  - id: F009
    severity: note
    category: coverage
    summary: "Load test, CI wiring, and later-section coverage not assessed here"
    location: "unverified"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 2.5 bundles too many independent changes into one task

Task 2.5 (effort 3) does five things:
- `git mv` of five source modules, each with its own option definitions and row conversions.
- Conversion of the four core row functions in `cli/inspect.py`.
- A rewrite of `run_listing`.
- A rewrite of `_add_inspect_parser` in `cli/main.py`.
- Four test-file moves plus edits to two other test files.

The only reason it is a single task is "this commit is green". A junior AI can hit a broken intermediate state anywhere in it with no checkpoint to fall back to. The task already lists the five modules as numbered sub-steps, so a split along those lines is cheap.

The split could be:
- 2.5a: converts the rows and the `run_listing` and `main.py` adapter while the modules are still in `cli/`. It stays green and is committed.
- 2.5b: pure `git mv` plus import fixes. It is a separate commit and keeps git history clean.

If the PM prefers the single commit, add an intermediate "suite green" check after the module moves and before the `cli/main.py` edit.

### [CONCERN] Task 2.5 puts the option-definition locations in the task, not in the LLD

The "Task-level additions" list says the guard order, bind-rule order, and exception mapping are task-level choices that change only with the PM. It does not flag the placement of the option objects. `CHANNEL_OPTION`, `JUDGE_INVOCATION_OPTION`, `VERDICT_OPTION`, `OUTCOME_OPTION`, and `UNRESOLVED_OPTION` are each defined in the row module that reads them, and `NODE_OPTION` is shared in `listing.py`. The LLD says only that options gain a `name` and that rows read `request.option(NODE_OPTION)`.

The placement is a reasonable choice, but it is not recorded as an addition to the LLD. Add one line to the "Task-level additions" list so reviewers of later tasks, such as the server's query-parameter derivation, know where the option objects live.

### [CONCERN] Task 1.2 asks for a test that may duplicate existing coverage and has a weak criterion

Task 1.2 adds a "every listing returns at least one row" test "if one does not already assert it". That conditional leaves a junior AI to decide whether the test is needed. The criterion "`test_cli_inspect.py` is shorter" is a proxy, not a behavior.

Replace the conditional with a direct instruction. For example: grep for an existing all-listings non-empty assertion, and add one only if none exists. Alternatively drop the line-count criterion and keep "no test removed".

### [NOTE] Tasks 1.1 and 1.3 are setup/capture steps with no commit

Both tasks are explicitly non-committing, and both are needed. 1.1 gates on 107/108 being merged, and 1.3 produces the artifact that Tasks 2.8 and 3.4 diff against. They could be merged, but keeping the baseline capture separate from the branch setup is defensible. No change needed.

### [NOTE] Task 3.1's "ask the PM" guard for file size is appropriate

Task 3.1 adds two methods to the store's feed mixin (`src/amoeba/store/feed.py`, which exists). The "if it passes ~300 lines, ask the PM before splitting" step respects the repo's file-size rule without over-specifying. No change needed.

### [PASS] Migration sequencing and byte-identical gate

The order is sound:
- Task 1.3 captures the baseline once.
- Tasks 2.1 to 2.7 move code, each leaving the suite green.
- Task 2.8 diffs against the baseline before any server code lands.
- Task 3.4 re-diffs after the read-path change in Task 3.3, then deletes the scratch directory.

This matches the LLD "Behavior preserved" paragraph and the Technical Requirement that the migration commit leaves `inspect` and `--help` output identical.

### [PASS] Test-with pattern and commit distribution

Every implementation task is immediately followed by its test task, or contains its own test:
- 2.1 is followed by 2.2.
- 2.4 includes `test_wire.py`.
- 2.7 is the layering test.
- 3.1 is followed by 3.2.
- 3.3 is followed by 3.4.

Commits are spread through the section, with seven commits across fourteen tasks. Joint commits are stated explicitly ("Committed with Task N.M"). Nothing commits untested behavior.

### [PASS] File and path references check out against the repo

The paths the tasks move or modify exist: `tests/cli/test_inspect_{evidence,feed,checks,cf}.py`, `tests/cli/test_feed.py`, `src/amoeba/feed/`, `src/amoeba/store/{feed,sql_feed,paths}.py`, `tests/feed/`, and `tests/store/`. `tests/inspection/` and `tests/feed/test_wire.py` are correctly listed as files to create. The dependency chain on 107 and 108 is confirmed by the presence of `test_inspect_checks.py` and `test_inspect_cf.py`.

### [NOTE] Load test, CI wiring, and later-section coverage not assessed here

The LLD's load tier (`tests/load/test_serve_load.py`) and its p95 latency NFR belong to the serve sections. They should appear in Section 9 of File 3, together with a CI task that gates on them. This file correctly contains neither. Whoever reviews `109-tasks.network-api-3.md` should verify both the load-test task and the CI wiring task. The "Open item for the PM" about `ServeRefusedError` mapping gates only Task 8.1.

### Run Digest

- Response length: 6389 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 191455 / 97118 / 94331 / 4131 / not computed
- Duration: 38.1 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: no
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
