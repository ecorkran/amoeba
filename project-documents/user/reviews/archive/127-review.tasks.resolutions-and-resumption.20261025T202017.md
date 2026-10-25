---
docType: review
layer: project
reviewType: tasks
slice: resolutions-and-resumption
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/127-tasks.resolutions-and-resumption.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261025
dateUpdated: 20261025
reviewedSha: 57e1aaf4c6fd06a18b96538152c1ea327bfdaada
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 117607
cachedTokens: 8843
cacheWriteTokens: 108760
completionTokens: 8578
durationSeconds: 66.3
costUsd: 0.52252
costBasis: provider
runId: run-20261025-p5-ce38b28c
squadronVersion: 0.24.4
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Task 6.4 needs `ResumeFailed` and `finish.record`, which Task 7.2 creates later"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:260-270"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 4.2 commits with a red suite until Task 4.3"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:188-199"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Tasks 6.4 and 7.2 are oversized, and Tasks 6.2 to 6.4 land in one commit"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:260-290"
  - id: F004
    severity: concern
    category: task-clarity
    summary: "Task 7.2 requires `observe.py` not to grow, but its own design adds lines to it"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:290"
  - id: F005
    severity: concern
    category: coverage-gap
    summary: "Pointer-move check for continuation entries has no task"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md:427"
  - id: F006
    severity: note
    category: sequencing
    summary: "Task 6.1 can come earlier"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:239-244"
  - id: F007
    severity: note
    category: coverage-gap
    summary: "A new pause after a retry is not asserted to route to escalate"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:289"
  - id: F008
    severity: note
    category: proportionality
    summary: "Task 9.2 repeats some earlier tests"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:328-333"
  - id: F009
    severity: note
    category: design-consistency
    summary: "`resume_skipped` is a parameter, which departs from the LLD's result-key list"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:66"
  - id: F010
    severity: pass
    category: coverage
    summary: "Success criteria coverage and test-with pattern"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md"
---

# Review: tasks — slice 127

**Verdict:** FAIL
**Model:** claude-sonnet-5-5

## Findings

### [FAIL] Task 6.4 needs `ResumeFailed` and `finish.record`, which Task 7.2 creates later

- Task 6.4 must "record `ResumeFailed(run_missing)` through `finish.record`" and record `ResumeFailed(spawn_error)` on a `LaunchError`. Its tests also assert these paths.
- The task-level additions assign `ResumeFailed` (`runner/observed.py`), `RESULT_RESUME_FAILURE` and the `finish.record` handling to Task 7.2. Task 7.2 depends on 6.4.
- A junior AI working in file order cannot finish 6.4.
- Task 3.2 (`classify`) has the same problem. It requires "no `RESULT_RESUME_FAILURE` in the result", but that constant is defined in `runner/finish.py` and no earlier task adds it.
- Fix: move the `ResumeFailed` value, `RESULT_RESUME_FAILURE` and the `finish.record` handling, with their tests from `tests/runner/test_finish.py`, into a task before 3.2. Task 3.1 or a new task between 3.1 and 3.2 would work. Task 7.2 then keeps only the observe-resume logic.

### [CONCERN] Task 4.2 commits with a red suite until Task 4.3

- Task 4.2 turns on the stage that rejects a bare pipeline-step resolution as `decision_required`. Its success criterion is only "tests pass" for its own new tests.
- The existing tests that this rule breaks are fixed in Task 4.3, a separate later commit. That leaves a commit with a failing suite.
- The LLD's Development Approach says each step leaves the suite green.
- Fix: fold 4.3 into 4.2, or state that 4.2 and 4.3 share one commit as 4.1 and 4.2 do.

### [CONCERN] Tasks 6.4 and 7.2 are oversized, and Tasks 6.2 to 6.4 land in one commit

- Task 6.4 is Effort 4. It has four act branches, a journal entry shape, the spawn, the factory wiring and tests. It commits together with 6.2 and 6.3, so a single commit carries about Effort 8.
- Task 7.2 is Effort 4. It covers a new module, the observe dispatch, the tick mapping, the `ResumeFailed` type, the `finish.record` changes and two test files.
- Suggested split:
  - **`finish.record` and `ResumeFailed`:** as its own task. This also fixes the FAIL above.
  - **6.4:** split into the `observe`/`not_found`/`run_not_at_pause` paths and the retry/accept spawn path.
  - **7.2:** the tick's resumed-from mapping in its own step.
- Give 6.3 (the stub `sq` resume mode) its own commit.

### [CONCERN] Task 7.2 requires `observe.py` not to grow, but its own design adds lines to it

- The "Size" addition says `observe.py` "grows by a dispatch line or two". Task 7.2's success criterion says `observe.py` "is no longer than it was". `observe.py` is already 335 lines.
- Both cannot hold. A junior AI will either fail the check or move unrelated code.
- State the real target: for example, no net growth after moving a helper out, or an explicit exception for the dispatch lines.
- Task 9.5's "near 300 lines" check has the same conflict for `tick.py` (324 lines), `observe.py` and `launch.py`.

### [CONCERN] Pointer-move check for continuation entries has no task

- The LLD's "Consumes from 125" says the pointer-move check covers continuation entries. It uses the step's latest pointer write and the continuation's `issued_at` as its start.
- No task changes or tests this. If 125's check keys on launch entries only, a resumed run that follows a moved pointer would go unchecked. The Resume Confirmation and Failures section is the natural place for it.
- Fix: add a verification or test sub-item, in Task 7.2 or 9.2, that a continuation entry is covered by the pointer-move check.

### [NOTE] Task 6.1 can come earlier

- Task 4.2 adds code to `tick.py`, which is already 324 lines. Task 6.1 later extracts the act stage out of it.
- Task 6.1 depends only on 1.1. Running it before 4.2 would stop `tick.py` from growing and shrinking again.

### [NOTE] A new pause after a retry is not asserted to route to escalate

- The LLD criterion for resume confirmation says a new pause after a retry is "ingested, and routed to escalate".
- Task 7.2's tests prove only ingestion. Task 9.2 does not list the case.
- Add the routing assertion to one of them.

### [NOTE] Task 9.2 repeats some earlier tests

- Tasks 6.4 and 8.2 already assert the stub argv log and the accepted-review routing at tick level.
- Task 9.2 follows the LLD's functional bullets one for one, so it is traceable. Keep the tests that go through `amoeba submit resolution`, since those are not yet proven. Drop the ones that duplicate lower-level assertions.

### [NOTE] `resume_skipped` is a parameter, which departs from the LLD's result-key list

- The LLD's Patterns list names `resume_skipped` as a result key. The task file journals it as the parameter `PARAM_RESUME_SKIPPED`, because it is known at issue time.
- The reasoning is sound and documented. Update the LLD's Patterns and Conventions line, or note it in Task 9.3's contract text, so the two documents agree.

### [PASS] Success criteria coverage and test-with pattern

- Every functional, technical and integration criterion maps to at least one task, apart from the gaps above:
  - **Decisions and rejections:** 3.3, 4.x, 6.4 and 9.2.
  - **Poisoned-resolution containment:** 4.2.
  - **Missing run:** 2.5 and 6.4.
  - **Confirmation and failures:** 7.1 and 7.2.
  - **Crash kill points:** 7.3.
  - **Accept over CONCERNS:** 8.2.
  - **Migration plan test:** 2.1 and 2.4.
  - **Contract suite:** 2.6.
  - **Contract text and CHANGELOG:** 9.3 and 9.4.
- Tests sit with or immediately after the implementation they cover.
- Commit checkpoints are spread across all nine sections, and no task merges a branch.
- Nothing is scope creep. Each task-level addition (`recorded_result_run_nodes`, `checkout_holders`, `USAGE_LIMIT`, the `act.py` and `observe_resume.py` splits) traces to a stated LLD need.
- There is no NFR load-test requirement in the slice, so none is expected.

### Run Digest

- Response length: 7102 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 117607 / 8843 / 108760 / 8578 / not computed
- Duration: 66.3 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
