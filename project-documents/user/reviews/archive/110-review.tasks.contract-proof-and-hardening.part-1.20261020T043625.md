---
docType: review
layer: project
reviewType: tasks
slice: contract-proof-and-hardening
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261019
dateUpdated: 20261019
reviewedSha: e74eeda4975c66b8d1283514649b5f8c54f3ce03
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
turns: 9
promptTokens: 470480
cachedTokens: 367293
cacheWriteTokens: 103175
completionTokens: 6377
durationSeconds: 50.8
costUsd: 0.513893
costBasis: provider
runId: run-20261020-p5-002cb7ae
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete and traceable"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F002
    severity: concern
    category: sequencing
    summary: "`-k prune` in the walkthrough will not select the `select_prunable` tests"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:177"
  - id: F003
    severity: concern
    category: scope
    summary: "Tasks 2.1–2.3 are too granular"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:90-136"
  - id: F004
    severity: note
    category: sizing
    summary: "`test_lifecycle_proof.py` has no size guard across three tasks"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:75-108"
  - id: F005
    severity: note
    category: feasibility
    summary: "Bootstrap subprocess needs a pinned working directory"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:351"
  - id: F006
    severity: note
    category: proportionality
    summary: "Harness self-tests are justified by the design, though close to the limit"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:362-376"
---

# Review: tasks — slice 110

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage is complete and traceable

Every Functional and Technical requirement in the slice design maps to a task:
- **Scenario and oracles:** the D4 scenario, the end-state oracle and the feed-replay oracle are in 5.1–5.5.
- **Locality (D6):** the D6 checks are in 5.2.
- **Network subset:** 6.1.
- **`record_runner_report`:** 3.1–3.3 cover the one-commit property, each refusal and the `run_id` guard.
- **Tenant order:** 1.2 pins it before the move and 2.4 re-runs it after.
- **Layering and writer guard:** the pruning layering AST rule is 7.1 (rule 9), and the writer guard is 7.3.
- **Pruning:** the four-condition and failure-mode tests are 7.2 and 7.4, and step 12 is 7.5.
- **Store safety:** 4.3.
- **Docs and validation:** 8.1–8.3 and 9.1.

Nothing is scope creep. The task-level additions (`prune_sq_runs` split, `ProofRunner` constructor arguments) are declared as such and justified.

The slice design restates no NFR, so no load test or CI-gating task is required. Commits are spread across all sections, and each implementation task is followed by its test (3.1→3.2, 4.1→4.2, 7.1→7.2, 7.3→7.4).

### [CONCERN] `-k prune` in the walkthrough will not select the `select_prunable` tests

File 1 (line 46) says pruning tests live in `tests/process/` so the walkthrough's `pytest tests/contract tests/process -k prune` selects them. Task 7.2 names its file `tests/process/test_run_pruning.py`. The substring `prune` does not occur in `pruning` or `prunable`, so `-k prune` skips the whole file unless a test name happens to contain `prune`. Walkthrough step 2 and the LLD claim that these tests are covered would then be false, and Task 9.1 would not notice.

Fix: rename the file to `test_prune_selection.py`, or require `prune` in the test names. Alternatively, have 9.1 confirm that the `-k prune` run includes the selection tests.

### [CONCERN] Tasks 2.1–2.3 are too granular

Tasks 2.1, 2.2 and 2.3 are each effort 1 and share one commit. They cover one fixture file, one field and one test, and none can be verified alone. 2.1's criterion can't be checked without 2.2's parser, and 2.2's criteria need 2.1's fixture.

Merge them into one task, "Add `updated_at` and the v5 fixture, with tests". The 2.6/2.7 and 8.2/8.3 pairs are similar but smaller, and merging them is optional.

### [NOTE] `test_lifecycle_proof.py` has no size guard across three tasks

Tasks 5.4, 5.5 and 7.5 all append to `test_lifecycle_proof.py`. That is 12 steps, the step-specific assertions, both oracle calls and the step-12 subprocess. The other files in this slice carry the ~300-line check, such as `scenario.py` and `runner_tenant.py`, but this one does not.

Add a success criterion to 7.5 saying the driver file stays near 300 lines, with per-step helpers split into a sibling module if needed.

### [NOTE] Bootstrap subprocess needs a pinned working directory

Task 4.5 runs `sys.executable -m tests.contract.bootstrap`. `tests/` has no `__init__.py`, so this only works as a namespace package when the subprocess's cwd is the repo root. The harness also changes `HOME`, but that doesn't affect this. Add "set `cwd` to the repo root" to the harness step so a junior doesn't hit an import error and guess at a fix.

### [NOTE] Harness self-tests are justified by the design, though close to the limit

Task 4.6 tests the harness itself: the readiness timeout message and the subscriber-exception re-raise. These trace to the "harness fails loudly" convention in the slice design's Patterns section, so they stay. No further test tasks beyond the design's criteria were found.

### Run Digest

- Response length: 4490 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 470480 / 367293 / 103175 / 6377 / not computed
- Duration: 50.8 s
- Cost: $0.51 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
