---
docType: review
layer: project
reviewType: tasks
slice: request-outcome
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/185-tasks.request-outcome.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 9752aefd6ab2191604ffeaa7e0c1d0dbb265a8fb
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 27
effort: xhigh
turns: 28
promptTokens: 949042
cachedTokens: 780267
cacheWriteTokens: 168759
completionTokens: 57761
durationSeconds: 253.8
costUsd: 0.22892
costBasis: provider
runId: run-20261104-tasks-plan-3bf84a0f
squadronVersion: 0.24.20
findings:
  - id: F001
    severity: concern
    category: coverage
    summary: "D11's decline detail for `request_limit_unconfigured` has no task"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:143"
  - id: F002
    severity: concern
    category: coverage
    summary: "\"Every member question gets the passage\" is stated but not tested"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:192"
  - id: F003
    severity: note
    category: coverage
    summary: "\"Asker's own part is not requested\" is proven only at the decline path"
    location: "project-documents/user/slices/185-slice.request-outcome.md:423"
  - id: F004
    severity: note
    category: consistency
    summary: "Slice design frontmatter omits dependency 181"
    location: "project-documents/user/slices/185-slice.request-outcome.md:6"
  - id: F005
    severity: note
    category: consistency
    summary: "Design's `AMOEBA_KEEP_SCENARIO_DIR=1` conflicts with the task file"
    location: "project-documents/user/slices/185-slice.request-outcome.md:453"
  - id: F006
    severity: note
    category: verification
    summary: "Task 0.1 should check the 183 reader's function name"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:65"
  - id: F007
    severity: note
    category: granularity
    summary: "Task 5.2 bundles a behavior-preserving refactor with the new gate"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:143"
  - id: F008
    severity: note
    category: proportionality
    summary: "Some tests exceed what the success criteria need"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:80"
  - id: F009
    severity: note
    category: sequencing
    summary: "The 3.2 commit ships a reachable `NotImplementedError`"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:114"
  - id: F010
    severity: pass
    category: coverage
    summary: "Success criteria map to tasks with no gaps"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md"
  - id: F011
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit markers hold"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md"
  - id: F012
    severity: pass
    category: verification
    summary: "The load case has a CI gate"
    location: ".github/workflows/ci.yml:53"
  - id: F013
    severity: pass
    category: verification
    summary: "Named code and paths exist on the target"
    location: "src/amoeba/store/question_models.py:73"
  - id: F014
    severity: pass
    category: proportionality
    summary: "Size is in line with sibling slices"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md"
---

# Review: tasks — slice 185

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] D11's decline detail for `request_limit_unconfigured` has no task

Slice design D11 requires the `request_limit_unconfigured` reason to tell the PM which key to add. Task 5.2 specifies detail for the provider, for check 8 (count and limit) and for check 9 (waiting slice and edge), but not for check 2. The tests in 5.2 and 10.2 assert only the reason code. Task 10.5 (line 247) then documents that the reason "names" the key, which describes behavior no task builds. Add the check-2 detail to 5.2 (naming `projects.<id>.answerer.request_limit`), assert it in 5.2's test list, and assert it in 10.2's refusal test.

### [CONCERN] "Every member question gets the passage" is stated but not tested

D10 requires every member question to get the passage, including the none-text `No open requests involve this project.`, "so its absence never has to be interpreted." Task 7.2 states the rule at line 192, but its test list (line 193) covers placement, the size fallback, `sources_too_large`, and the non-member baseline. An implementation that omits the passage when there are no edges would pass every listed test. Add a 7.2 test: a member question with no edges gets the none-text passage, and a non-member gets none.

### [NOTE] "Asker's own part is not requested" is proven only at the decline path

The criterion depends on the check model's judgment. Task 10.2 (line 229) proves only that `check: no` declines `check_said_no`, and defers real behavior to 186. The split is explicit and honest. Make sure 186's inputs say that this criterion is model-judged.

### [NOTE] Slice design frontmatter omits dependency 181

The design's Dependencies section requires 181 (`ProgramStore`, `read_member`, the tick's `Program | None`), and the task file lists it. The frontmatter list (lines 7–11) does not. Add `181-slice.program-record`.

### [NOTE] Design's `AMOEBA_KEEP_SCENARIO_DIR=1` conflicts with the task file

The walkthrough shows the variable as `1`. Tasks 10.1 (line 224) and 11.2 (line 259) use a path, which matches 183 and 184 and the 184 review's finding that `=1` would not produce a directory. The deviation is stated in the task file, so it is safe. Correct the design at its next refresh.

### [NOTE] Task 0.1 should check the 183 reader's function name

Tasks 0.1 and 4.2 use 183's `edges_providing`, which matches 183's design (`edges_providing(project_id)`, open only). 184's task file (line 66) names it `edges_by_provider`, which is the SQL index name in 183's design. Task 0.1 already requires recording mismatches, so this is covered. A line stating which name is the function would stop a junior AI from using the index name.

### [NOTE] Task 5.2 bundles a behavior-preserving refactor with the new gate

5.2 is effort 4 and does two things: it factors the answer-limit and reserved-term checks out of `evaluate_gate`, and it adds the nine-check `evaluate_request_gate` with about a dozen tests. The refactor is verifiable alone by 142's unedited tests. Split it into a first sub-item with its own green run, then the new gate.

### [NOTE] Some tests exceed what the success criteria need

Candidates to cut: 1.1's "every new value is unique" check, which no criterion needs, and 1.3's "change-feed event fires once," which tests a trigger that predates this slice. Neither is harmful. Cutting them shortens the task list.

### [NOTE] The 3.2 commit ships a reachable `NotImplementedError`

The commit at the 3.2 marker (line 118) leaves `settle_run_result` raising `NotImplementedError` for `Requested`. Nothing teaches the request shape until 8.1, so no run reaches the branch, and the error is explicit rather than a silent fallback. This is acceptable as written.

### [PASS] Success criteria map to tasks with no gaps

Each functional criterion has a task: the main path and mid-request snapshot (10.1), refusals (5.2, 6.2, 10.2), crash points (6.7), PM resolutions (6.2, 10.2), release (1.4, 10.1), the no-program refusal (10.2), the passage and its visibility (7.1–7.3), and config (2.1). The technical requirements, the integration requirements and the walkthrough steps also map to tasks.

### [PASS] Sequencing, test-with pattern and commit markers hold

Each implementation task carries its own tests. Dependencies run forward: store (1), then config (2), parser (3), program-store reads (4), facts and gate (5), writes and sweep (6), passage (7), instructions (8), listings (9), scenarios and docs (10), validation (11). There are no cycles. The 15 markers fall at tested points.

### [PASS] The load case has a CI gate

10.4 extends `tests/load/test_program_load.py`. CI runs `uv run pytest tests/load` as its own named step (line 54), and `pyproject.toml` excludes `tests/load` from the bare run. The case is therefore gated without a new CI task.

### [PASS] Named code and paths exist on the target

Confirmed on the target: `QUESTION_TRANSITIONS` (question_models.py:73), `_OPEN_STATES` and `_prior_answers` (answer_submission.py:41, 138), `COUNT_ANSWERER_ANSWERS_IN_RUN` (sql_questions.py:119), `AnswererSettings.answer_limit` (project_config.py:99), `RESULT_DECISION` (finish.py:55), `_settle_question_on_acknowledgment` (questions.py:225), and `015` as the highest schema file. Migrations 013–015 have no SQL `CHECK` on state or decline reason, so 1.1 and 1.2 need no SQL change for the new values. The test, doc and stub paths exist. The missing ones belong to 181–184 and are covered by the BLOCKED rules in 0.1 and 0.2.

### [PASS] Size is in line with sibling slices

The file has 33 top-level tasks and 142 checkboxes. For comparison, 181 has 42 and 171, 183 has 39 and 158, and 184 has 41 and 170. Nothing here is overweight, and a single file fits the slice.

### Run Digest

- Response length: 9310 chars
- Response is newline-free: no
- Tool calls made: 27
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 28
- Tokens — prompt / cached / cache write / completion / reasoning: 949042 / 780267 / 168759 / 57761 / not computed
- Duration: 253.8 s
- Cost: $0.23 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14

## Resolution

- [concern] D11's decline detail for `request_limit_unconfigured` has no task: fixed. Task 5.3 now says the check 2 detail names `projects.<asking_project>.answerer.request_limit`, and its tests assert the key path.
- [concern] "Every member question gets the passage" is not tested: fixed. Task 7.2's tests add a member question whose asker is party to no edge and still gets the passage with the none-text.
- [note] "Asker's own part is not requested" is proven only at the decline path: rejected. Whether a need belongs in the asker's own part is the check model's judgment, which no offline test can prove. Task 10.2 already states that its `check_said_no` test proves only the decline path, and that real-model behavior is 186's.
- [note] Slice design frontmatter omits dependency 181: fixed. Added `181-slice.program-record` to the dependencies in `185-slice.request-outcome.md`.
- [note] Design's `AMOEBA_KEEP_SCENARIO_DIR=1` conflicts with the task file: fixed. The design's walkthrough command now sets the variable to `"$(mktemp -d)"`, and Task 11.2 drops its "use the path instead" workaround and runs step 1 with the path.
- [note] Task 0.1 should check the 183 reader's function name: fixed. Task 0.1 now says the LLD and 183's design call the provider-side reader `edges_providing`, while 184's tasks call it `edges_by_provider` (183's index name). It tells the implementer to confirm which function exists, and that Task 4.2 copies its ordering.
- [note] Task 5.2 bundles a refactor with the new gate: fixed. Split into Task 5.2 (share the two checks, with 142's gate tests passing unedited) and Task 5.3 (`evaluate_request_gate`). References in Tasks 6.2 are renumbered.
- [note] Some tests exceed what the success criteria need: fixed in part. Removed the `DeclineReason` uniqueness and no-SQL-change test clause from Task 1.1 and the "read no `requested` record" listing assertion from Task 1.4. The remaining tests each back a success criterion or a design decision.
- [note] The 3.2 commit ships a reachable `NotImplementedError`: fixed. The interim branch in `finish.py` now declines a `Requested` result `artifact_malformed` with a "not handled yet" detail, so a stray request reply becomes a PM question and never a tick crash. A test covers it, and Task 6.5 replaces the branch and its test.
- [pass] Success criteria map to tasks with no gaps: no change needed.
- [pass] Sequencing, test-with pattern and commit markers hold: no change needed.
- [pass] The load case has a CI gate: no change needed.
- [pass] Named code and paths exist on the target: no change needed.
- [pass] Size is in line with sibling slices: no change needed. The Task 5.2 split adds one task.
