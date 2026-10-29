---
docType: review
layer: project
reviewType: tasks
slice: pipeline-supervisor
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/132-tasks.pipeline-supervisor.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261029
dateUpdated: 20261029
reviewedSha: 39c247abde8e63b356971dfb6f7665d17744f3f3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 212456
cachedTokens: 103424
cacheWriteTokens: 109026
completionTokens: 6975
durationSeconds: 56.7
costUsd: 0.517015
costBasis: provider
runId: run-20261029-p5-cb381f49
squadronVersion: 0.24.9
findings:
  - id: F001
    severity: concern
    category: task-sizing
    summary: "Task 9.4 is overweight and should be split"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:262-272"
  - id: F002
    severity: concern
    category: sequencing
    summary: "\"Commit with Task X\" breaks the one-commit-per-task rule"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:137"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Tasks 7.5 and 12.1 duplicate the same transient-resume scenarios"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:207-213"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Task 9.3 contradicts Task 10.4 on `predecessors.py`"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:258"
  - id: F005
    severity: note
    category: coverage
    summary: "Task 2.1 defers the \"unknown key\" load check to Task 10.4"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:89"
  - id: F006
    severity: note
    category: clarity
    summary: "Task 1.1's success line contradicts its steps"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:74"
  - id: F007
    severity: note
    category: process
    summary: "Tasks 13.2 and 13.3 may produce empty commits"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:357"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md:423-453"
  - id: F009
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:45-49"
---

# Review: tasks — slice 132

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 9.4 is overweight and should be split

Task 9.4 is rated effort 5. It bundles five separable pieces of work:
- retargeting reconcile, the view, governance and the `decide` guard to slice nodes;
- the planner and `params.py` switching to the configured pipeline;
- the new `PIPELINE_UNCONFIGURED` fault;
- removing `HumanStepPlanner` and merge observation;
- rewriting the tick tests across `tests/runner/test_tick*.py`, `tests/runner/dispatch/` and `tests/runner/resolutions/test_tick_*.py`, plus new tests for four scenarios.

It has five dependencies, so a junior AI cannot verify it in pieces. A suggested split, each with its own commit and green suite:
- (a) slice-only reconcile, `current_slices` and governance;
- (b) the planner launching the configured pipeline with params;
- (c) the `pipeline_unconfigured` fault and removing `HumanStepPlanner` and merge observation.

The new tests and the test rewrites would go with their pieces.

### [CONCERN] "Commit with Task X" breaks the one-commit-per-task rule

The header says "each task ends in one commit" and that the suite is green after every task (lines 45 and 47). Tasks 5.1 (line 137), 6.1 (line 158) and 7.2 (line 189) instead say "Commit with Task 5.2 / 6.2 / 7.3". Each of these pairs is really one task, so the header rule does not hold as written.

The pairs are 5.1 and 5.2, 6.1 and 6.2, and 7.2 and 7.3. The 6.1/6.2 pair has a real cause. 6.1 stops marking `awaits_routing` while the tick still routes, so it cannot be committed alone. Either merge each pair into one task, or reorder so each task is independently green. Merging 5.1 and 5.2 is the easy case because both are pure `supervise.py` work. Merging 6.1 and 6.2 gives effort 7, so reorder that pair instead of merging it.

### [CONCERN] Tasks 7.5 and 12.1 duplicate the same transient-resume scenarios

Task 7.5 builds tick-level tests for these scenarios:
- two transient failures then `done`;
- four failures blocking `auto_resume_exhausted`;
- a `usage_limit` wait;
- a crash mid-resume.

Task 12.1 (lines 330-334) then rewrites the end-to-end test for the same transient scenarios: two failures then done, and four failures to exhaustion. Task 7.5 also adds stub `sq` scripts to `tests/sq_stub_scripts.py` that 12.1 adds again. The Verification Walkthrough requires the e2e `-k transient` run (step 5). So keep that run in 12.1 and cut 7.5 to what it alone proves: the per-step count, the `usage_limit` clock, release-after-hold, and the crash test. This avoids building the same stub scenarios twice.

### [CONCERN] Task 9.3 contradicts Task 10.4 on `predecessors.py`

Task 9.3 says `predecessors.py` "reduces to `_previous_eligible_slice` made public", and also says "the step versions stay until Task 9.4". Task 10.4 (line 301) then deletes "the step rules in `completion.py`, `predecessors.py` and `tree.py`". Both cannot hold. Either the step predecessor code survives 9.3 and 10.4 deletes it, or 9.3 deletes it and 10.4 has nothing to delete. Pick one. The same applies to renaming `test_ready_steps.py` to `test_ready_slices.py` in 9.3 while the step tests it contains must still pass until 9.4.

### [NOTE] Task 2.1 defers the "unknown key" load check to Task 10.4

Slice D2 lists "an unknown key beside `pipeline` and `params`" as a load failure. Task 2.1 omits it because `merge_policy` is still accepted, and Task 10.4 (line 302) adds it. The criterion is covered. The gap between those two tasks is intentional, so I raise no action.

### [NOTE] Task 1.1's success line contradicts its steps

A step commits the LLD fold-in to the target as `docs:`, but the success line says "No commit". The success line should say "no commit on the slice branch". Task 1.1 is also rated effort 1, though it edits multiple LLD sections. Raise the effort to 2.

### [NOTE] Tasks 13.2 and 13.3 may produce empty commits

Task 13.2 commits `test: close the supervisor's success criteria` even when every criterion already has a test, and Task 13.3 commits `chore: verify...` for a verification run. Both commits can be empty. The LLD (Integration Requirements) does require the before and after line counts in a commit message. A short condition would help: commit only if files changed, and put the line counts in the final commit that does change files.

### [PASS] Success-criteria coverage is complete

Each criterion traces to a task:
- Launch and no `cf set`: 9.2 and 9.4.
- Params and config validation: 2.1.
- Pipeline not found and `pipeline_unconfigured`: 9.4.
- Slice ordering: 9.3 and 9.4.
- Git pre-dispatch and dirty-tree resume: 7.2 and 9.1.
- D4 rows and the crash harness: 5.1, 6.1 and 6.2.
- Bound, `usage_limit`, held slice: 5.2, 7.2, 7.3 and 7.5.
- Question block: 6.1.
- Resolutions: 8.1.
- `until`: 8.2.
- Blocked list: 11.1.
- Import boundaries and grep test: 10.5.
- `supervise.py` coverage: 5.2.
- Contract test: 4.1.
- Docs: 13.1.

The slice's D5 edit to the 120 plan (`usage_limit` with `resets_at`) appears to be in place already. `resets_at` occurs once in the plan file.

### [PASS] Sequencing and test-with pattern

No circular dependencies. The order differs from the LLD's Migration Plan, and that is justified and recorded. Each implementation task carries its tests, and commits are spread across all thirteen sections rather than batched at the end. Deletions follow dependency order (routing, gates, pointers, steps, fault kinds), and the import-boundary pin lands last.

### Run Digest

- Response length: 6631 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 212456 / 103424 / 109026 / 6975 / not computed
- Duration: 56.7 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
