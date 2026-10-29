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
reviewedSha: e54e5aa47759dc2fd5d690a229386b42340f670a
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 114239
cachedTokens: 11176
cacheWriteTokens: 103059
completionTokens: 6900
durationSeconds: 59.6
costUsd: 0.483169
costBasis: provider
runId: run-20261029-p5-cb381f49
squadronVersion: 0.24.9
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are covered"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:13.2"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit cadence"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:50"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Tasks 9.5 and 6.2 are too large for one junior AI task"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:270-278"
  - id: F004
    severity: concern
    category: task-clarity
    summary: "Test-rewrite instructions in Task 6.2 leave coverage loss to the implementer's judgement"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:165"
  - id: F005
    severity: concern
    category: task-clarity
    summary: "The resume pre-dispatch rule has two owners, and Task 7.2 states it as an open check"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:188"
  - id: F006
    severity: note
    category: sequencing
    summary: "Some dependency edges are tighter than needed"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:332"
---

# Review: tasks — slice 132

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are covered

I traced each Functional, Technical and Integration criterion to a task:
- **Config and launch:** config validation (2.1), launch with params and the pipeline-not-found block (9.5), `pipeline_unconfigured` (9.6), and index-ordered slices (9.3, 9.5).
- **Git rules and outcome map:** dirty-tree and branch rules (7.2, 9.1), each D4 row (6.1), and atomic completion with its crash test (4.1, 6.2).
- **Resume:** the bound, `usage_limit` timing and held slices (5.2, 7.3, 7.5), and `resume` with instructions, `stop` and the rejected decisions (8.1).
- **Intents, inspection and cleanup:** `until` (8.2), the cross-project blocked list (11.1), the import-boundary grep and the CF-write grep (9.2, 10.5), contract docs (13.1), and the before and after line counts (1.1, 13.2, 13.3).

Task 13.2 maps each criterion to a named test and adds a test for any criterion with no proof. I found no task that lacks a source in the design. The extra work, such as folding the task-level additions into the slice design in 1.1, serves review traceability.

### [PASS] Sequencing and commit cadence

- The dependencies are acyclic.
- The re-ordering against the slice design's Migration Plan is explained and justified.
- Every implementation task carries its own tests and ends in one commit, so checkpoints are spread across all 13 sections.
- Deletion tasks remove their tests in the same commit, and the suite stays green after each task.
- The atomic-completion store option (4.1) lands before any task uses it, as the slice design requires.

### [CONCERN] Tasks 9.5 and 6.2 are too large for one junior AI task

Task 9.5 (Effort 4) bundles four separate pieces of work:
- the reconcile change to slice-only nodes;
- the `current_steps` to `current_slices` rename through `ProjectView`, governance and the `decide` guard;
- the planner and params rewrite;
- a rewrite of every tick test that drove step nodes, across `tests/runner/test_tick*.py`, `tests/runner/dispatch/` and `tests/runner/resolutions/test_tick_*.py`, plus new tests.

Task 6.2 (Effort 4) combines the ingest rewire, removing three tick stages, rewriting four named test files, and a new crash test.

Split 9.5 into:
- (a) reconcile, view and governance retargeted to slice nodes, with the existing tick tests rewritten;
- (b) the planner and params launch of the configured pipeline, with the new `p456` and not-found tests.

Split 6.2 into the ingest and tick rewire, and a separate crash-test task. Task 8.1 touches six modules plus a full test rewrite. It is also a candidate to split into a vocabulary and classification half and an act and argv half.

### [CONCERN] Test-rewrite instructions in Task 6.2 leave coverage loss to the implementer's judgement

The task says to rewrite the listed tick tests "to assert the D4 effect instead, or delete them where the behaviour no longer exists", and the step is open-ended. A junior AI can delete a test without checking that the behaviour is covered elsewhere. Give a disposition for each named file (rewrite or delete) and a one-line reason, or add a check that each deleted test's behaviour is covered by a named D4 test from 6.1.

### [CONCERN] The resume pre-dispatch rule has two owners, and Task 7.2 states it as an open check

Task 7.2 says "Confirm 128's resume rule already does this; change it only where it differs". Task 9.1 later sets "one allowed-branch rule for every pipeline", with a resume that may be on the target or the slice's own branch and an uncleaned tree. It is unclear which task owns the resume branch and cleanliness rule. Task 7.2's tests (resume on the slice branch with a dirty tree passes) rely on it. Decide now what 128's rule is, then either move the rule change into 7.2 and have 9.1 only remove the CF rows, or keep it in 9.1 and give 7.2 no rule change. Replace "confirm" with a concrete instruction.

### [NOTE] Some dependency edges are tighter than needed

Task 11.1 depends on 10.5, and 12.1 depends on 11.1. Task 11.1 only needs the inspection registry that 10.1 changes. The end-to-end rewrite in 12.1 needs the blocked listing only if it asserts via `inspect blocked`. This does no harm in a linear file order, but the chain makes the "continue past a BLOCKED task" rule in the file header less useful than it could be.

### Run Digest

- Response length: 5115 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 114239 / 11176 / 103059 / 6900 / not computed
- Duration: 59.6 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
