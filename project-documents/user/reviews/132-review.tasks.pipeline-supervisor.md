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
reviewedSha: 6b8ef22ecd8d906c92567219b236dd329e1d5c64
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 114959
cachedTokens: 11176
cacheWriteTokens: 103779
completionTokens: 5402
durationSeconds: 43.0
costUsd: 0.471069
costBasis: provider
runId: run-20261029-p5-cb381f49
squadronVersion: 0.24.9
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Task 8.1 bundles too much for one task"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:229-236"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 9.5 is the largest change and rewrites tests across several directories"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:280-287"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 10.2 combines mass deletion with a module move"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:313-319"
  - id: F005
    severity: concern
    category: test-continuity
    summary: "The supervise purity test may be deleted with `gates/`"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:137"
  - id: F006
    severity: concern
    category: coverage
    summary: "The slice design's edit to the plan entry has no task"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md:234"
  - id: F007
    severity: note
    category: task-clarity
    summary: "The `gate` grep in Task 10.5 will be noisy"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:340"
  - id: F008
    severity: note
    category: sequencing
    summary: "Behaviour is temporarily degraded between 6.2 and 6.3"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:160-176"
  - id: F009
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit cadence"
    location: "project-documents/user/tasks/132-tasks.pipeline-supervisor.md:46-48"
---

# Review: tasks — slice 132

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage

- **Launch and config:** pipeline launch with no `cf set` maps to 9.2 and 9.5. `params` and config refusal map to 2.1 and 9.5. A missing pipeline and `pipeline_unconfigured` map to 9.7. Index order maps to 9.3 and 9.5.
- **Pre-dispatch:** the dirty-tree and wrong-branch rules map to 9.1.
- **Outcome map and resume:**
  - The D4 rows and the crash test map to 6.1 and 6.3.
  - The bound and `usage_limit` wait map to 5.2, 7.3 and 7.5.
  - Hold and release map to 7.3 and 7.5.
  - Questions map to 6.1.
- **Resolutions and intents:** the resolution vocabulary maps to 8.1. `until` rejection maps to 8.2.
- **Blocked list:** the cross-project list maps to 11.1.
- **Technical and integration:** the grep and import tests map to 9.2 and 10.5. `supervise.py` coverage maps to 5.2. Docs map to 13.1. The line-count record maps to 1.1 and 13.3.

I found no scope creep. Every task traces to a decision or criterion in the slice design.

### [CONCERN] Task 8.1 bundles too much for one task

Task 8.1 is Effort 4. It rewrites the vocabulary enums, changes six modules (`classify`, `judge`, `planner`, `act`, `argv`, `prepoll`), removes `ObserveRun` and `ResumeRun.decision`, edits the inbox contract, and rewrites the whole resolution test suite in one commit. A junior AI would struggle to keep the suite green while all of that is in flight.

Split it into two tasks:
- **Vocabulary and classification/judge:** enums, `Situation` and rejection codes, with their tests.
- **Planner, act, argv and prepoll:** the `ResumeRun(cause=resolution)` and no-run relaunch behaviour, plus the docs.

### [CONCERN] Task 9.5 is the largest change and rewrites tests across several directories

Task 9.5 is Effort 4. It switches the view and governance to slices, changes the planner and params, and rewrites every tick test that drove step nodes. That covers `tests/runner/test_tick*.py`, `tests/runner/dispatch/` and `tests/runner/resolutions/test_tick_*.py`. The "full suite green" gate cannot be reached until all of these are rewritten together.

Split it into two tasks:
- **Production switch:** `current_slices`, governance and the planner launch.
- **Test migration:** rewrite the tick tests, in groups by directory.

### [CONCERN] Task 10.2 combines mass deletion with a module move

Task 10.2 deletes eight or more modules and removes `read_gate`. It also moves four surviving modules into `dispatch/` under new names, rewrites imports, relocates their tests, and prunes the stub and rig helpers. A bad import rewrite is hard to tell apart from a bad deletion. Do the move and rename as a `refactor:` commit first, then delete the dead gate modules.

### [CONCERN] The supervise purity test may be deleted with `gates/`

Task 5.1 adds `supervise.py` to `tests/runner/gates/purity.py`. Task 10.2 deletes `gates/` and "the gate tests whose modules went", and nothing says the purity check survives. The slice design requires `supervise.py` to stay pure ("Patterns and Conventions"; Technical Requirements), so that guarantee could be dropped silently.

Task 5.1 should put the purity test in `tests/runner/test_supervise.py` or `tests/test_import_boundaries.py`. Otherwise Task 10.2 should say explicitly where `purity.py` moves.

### [CONCERN] The slice design's edit to the plan entry has no task

D5 says "The plan entry is edited to say so", meaning `usage_limit` with `resets_at` is added to the resume list. No task edits that document. Task 1.1 folds only the task-level additions into the LLD, and #22 covers only the arch body text. The result is a plan that contradicts the delivered behaviour. Add a sub-item to Task 1.1 or 13.1 that edits that plan entry.

### [NOTE] The `gate` grep in Task 10.5 will be noisy

`grep -rn "pointer\|routing\|merge_policy\|gate"` also matches `investigate`, `propagate` and `aggregate`. The task already says "each remaining hit is justified or removed". Using `-w` or a word-boundary pattern would stop the junior AI from chasing false hits.

### [NOTE] Behaviour is temporarily degraded between 6.2 and 6.3

Task 6.2 takes routing off the tick, so completed runs are not marked `done` until Task 6.3. The suite stays green because the affected tests are deleted, and 6.3 depends on 6.2, so the order is correct. The two tasks should stay adjacent, and the branch is not usable end to end between them.

### [PASS] Sequencing, test-with pattern and commit cadence

- **Dependencies:** they are acyclic and sufficient. Atomic completion (4.1) lands before it is used (6.3). Resume machinery (7.1 to 7.4) comes before the vocabulary cut (8.1). The slice switch (9.5) comes after the dependencies it needs (2.1, 8.1, 8.2, 9.3, 9.4). Deletions come last.
- **Tests and commits:** each implementation task carries its own tests. Every task ends in its own commit, spread across all sections rather than batched.
- **Load testing:** the slice restates no NFR, so no load-test or CI-gating task is needed.

### Run Digest

- Response length: 6249 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 114959 / 11176 / 103779 / 5402 / not computed
- Duration: 43.0 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
