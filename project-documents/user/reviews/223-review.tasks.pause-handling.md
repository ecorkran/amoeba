---
docType: review
layer: project
reviewType: tasks
slice: pause-handling
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/223-tasks.pause-handling.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 3c788f50c8000b10b4390ae1212ae89b0a70544e
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 120003
cachedTokens: 11198
cacheWriteTokens: 108801
completionTokens: 5636
durationSeconds: 45.5
costUsd: 0.493535
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are fully covered"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Task 1.6 is too large for one junior task"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:84-90"
  - id: F003
    severity: concern
    category: code-structure
    summary: "`store/questions.py` will exceed the ~300-line limit"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:71-103"
  - id: F004
    severity: concern
    category: ambiguity
    summary: "Slice parameter key is not named in task 4.2"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:172"
  - id: F005
    severity: concern
    category: sequencing
    summary: "Changing `assemble`'s signature (3.4) leaves callers and existing tests unplanned"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:149-153"
  - id: F006
    severity: concern
    category: sequencing
    summary: "`Deps` is created after the code that needs injected spawner and poller"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:219-226"
  - id: F007
    severity: note
    category: test-coverage
    summary: "Read-side store functions are only partly tested"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:80-98"
  - id: F008
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable but heavy"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md"
---

# Review: tasks — slice 223

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are fully covered

- **Real pause answered and resumed:** tasks 7.4 to 7.10, 9.2 and 10.2.
- **Barred item waits, then is answered after `set_up`:** tasks 3.1 to 3.3, 5.8 and 10.2.
- **`answer` records, resumes and becomes precedent:** tasks 1.8, 7.12 and 7.13.
- **The four checks pass:** tasks 10.1 and 5.3.
- **No hard-coded authorize list in `answering.yaml`:** tasks 3.2 and 10.1.
- **The three contract docs match the code:** tasks 5.3, 8.3 and 9.1.
- **Live tier and restored tests:** tasks 9.2 and 9.3.
- **#303 comment posted:** task 9.4.

All D3 skip reasons, D7 rows and D8 branches have named tests. No task traces to nothing. No merge or push task appears.

### [CONCERN] Task 1.6 is too large for one junior task

Task 1.6 bundles six writes with distinct transaction semantics:
- `insert_question`
- `settle_answered` with the in-transaction gate callback
- `settle_waiting`
- `replace_claim`
- `add_pm_answer`
- `record_resume`

`settle_answered` alone has three outcomes (settled, decline, lost). Split it into the claim and settle writes (`insert_question`, `settle_*`, `replace_claim`) and the PM and resume writes (`add_pm_answer`, `record_resume`). Task 1.7 can then be split to match.

### [CONCERN] `store/questions.py` will exceed the ~300-line limit

Tasks 1.3, 1.5, 1.6 and 1.8 all put code in `store/questions.py`. That covers three serializer pairs, six reads, six write functions and `pm_precedent`. The Context Summary splits `handle_pause` into several modules to respect the file limit, but gives `questions.py` no such split. Add a split, for example `questions_json.py` for the serializers and `questions_writes.py` for the writes, or state why this module is exempt.

### [CONCERN] Slice parameter key is not named in task 4.2

Task 4.2 says to define `TARGET_PARAM_KEY` but never gives its value. The design only says "the run's `slice` parameter". A junior has no way to know the value, and the repo rules say not to guess. State the key name in the task.

The 4.1 success line ("one slice index from the run fixture's range") may not hold either. The walkthrough runs with no `slice` parameter, so the copied real run file likely has none. Say which fixture supplies the slice index.

### [CONCERN] Changing `assemble`'s signature (3.4) leaves callers and existing tests unplanned

Task 3.4 changes `assemble` to take `ProgramSources` and makes plan selection in `source_reads` optional. Nothing in 3.4 or 3.5 updates the existing callers or existing 221 tests. The section 3 commit requires all four checks to pass. Add a sub-item to 3.4 to update existing `assemble` callers and tests, so the commit point is working.

### [CONCERN] `Deps` is created after the code that needs injected spawner and poller

- **Ordering:** `answering_run.start` and `wait` (5.5 and 5.6) use an injected spawner and poller, but `Deps` is only created in 6.0.
- **Unclear signature:** the tasks do not say whether `start` and `wait` take `Deps` or separate arguments. 7.6 later calls them alongside `resume`, which does take `Deps`.
- **Fix:** move 6.0 before section 5, or state that 5.5 takes explicit parameters and that 7.6 adapts them.

### [NOTE] Read-side store functions are only partly tested

Task 1.7 covers `automatic_answer_count`, `latest_answer` and the writes. It does not name `get_question`, `latest_question`, `answers_of` or `any_answering_run_id`. `any_answering_run_id` drives the `answering_run` skip, so a one-line test for it would help. Task 7.3 may cover it indirectly.

### [NOTE] Proportionality is acceptable but heavy

The file has about 60 tasks across 11 sections for an effort-5 slice. Test tasks follow their implementation tasks, and the tests trace to D15. Commit markers sit at working points after each section. No trimming is required. Minor mergeable items are 5.6's "no transaction open during spawn" check, which is nearly trivial because `start` and `wait` take no store, and the revert-once check in 3.6.

### Run Digest

- Response length: 5033 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 120003 / 11198 / 108801 / 5636 / not computed
- Duration: 45.5 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Resolution

- [pass] Success-criteria coverage: no change needed.
- [concern] Task 1.6 too large: split into 1.5/1.6 (question reads, insert, claim moves), 1.7/1.8 (answer reads, PM answer, resume record), 1.9/1.10 (`settle_answered` with gate), each with its own tests.
- [concern] `store/questions.py` size: serializers moved to `store/question_json.py` and answer-side functions to `store/answers.py`, which `questions.py` re-exports so the design's interface holds.
- [concern] Slice parameter key: task 4.2 now names `TARGET_PARAM_KEY = "slice"`.
- [concern] `assemble` signature change: task 3.4 now finds and updates every existing caller of `assemble` and `source_reads` and their tests, and requires all four checks to pass.
- [concern] `Deps` ordering: moved into new task 5.3, before the start/wait/settle tasks that use it; tasks 5.3 to 5.9 renumbered, references updated; task 6.0 now holds only `ResumeResult`.
- [note] Read-side store tests: new task 1.6 covers `get_question`, `latest_question` and `any_answering_run_id`, and 1.8 covers `answers_of`.
- [note] Proportionality: no change; the sizing is acceptable per the review and every task traces to the design, so I removed nothing.

No deferrals, so no GitHub issues were filed.
