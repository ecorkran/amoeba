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
reviewedSha: 83dc6cd39c6794622d44874573de6613cdafb6cb
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 15
effort: xhigh
turns: 16
promptTokens: 819800
cachedTokens: 662753
cacheWriteTokens: 157033
completionTokens: 60434
durationSeconds: 260.7
costUsd: 0.213358
costBasis: provider
runId: run-20261104-tasks-plan-3bf84a0f
squadronVersion: 0.24.20
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 6.3 depends on a type that Task 6.4 defines"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:159"
  - id: F002
    severity: concern
    category: error-handling
    summary: "An unreadable provider becomes `band = None`, and the gate passes it"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:137"
  - id: F003
    severity: concern
    category: coverage
    summary: "Nothing automated checks that program-blocked shows the asker's edge and the provider's request"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:217"
  - id: F004
    severity: concern
    category: load-testing
    summary: "The new per-question reads have no load test"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:183"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Task 6.2 is too large for one task"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:154"
  - id: F006
    severity: concern
    category: coverage
    summary: "Task 0.2 names the no-program regression without a file path"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:71"
  - id: F007
    severity: note
    category: sequencing
    summary: "Task 0.1's BLOCKED rule and its inputs"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:69"
  - id: F008
    severity: note
    category: proportionality
    summary: "Task 1.1 bundles four separable changes"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:76"
  - id: F009
    severity: note
    category: proportionality
    summary: "Some tests repeat each other across tasks"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:160"
  - id: F010
    severity: note
    category: conventions
    summary: "`-k` selects by name, not by marker"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:217"
  - id: F011
    severity: pass
    category: coverage
    summary: "Success criteria are covered by tasks"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md"
  - id: F012
    severity: pass
    category: scope
    summary: "No scope creep, no merge or push task, sound commit points, and a proportionate file"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md"
  - id: F013
    severity: pass
    category: consistency
    summary: "Names and paths the task file relies on exist"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:63"
---

# Review: tasks — slice 185

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 6.3 depends on a type that Task 6.4 defines

Task 6.3 says `finish_answering` takes the `RequestContext` "(Task 6.4)", but 6.4 comes after 6.3 and the file says to work tasks in file order. The 6.3 test ("a finished run with a confirmed request ends with the entry resolved once") cannot run until `RequestContext` exists. Move the definition of `RequestContext` into 6.3 and leave the per-tick wiring in 6.4, or swap 6.3 and 6.4.

### [CONCERN] An unreadable provider becomes `band = None`, and the gate passes it

Task 5.1 says an unreadable provider store "gives `band = None`", and Task 5.2 says a `None` band skips check 7 and passes. That turns a read failure into a permissive value, which CLAUDE.md forbids ("Never use silent fallback values"). The design also contradicts itself: its API has `band: BandState | None  # None: provider unreadable` (slice design line 357), while its Integration Points say the failure is `Unreadable` (line 416). 181 already has a `Readable` result from `read_member`. Before 5.1 is worked, decide this. The likely fix is an explicit `Unreadable` state from `request_facts`, with the gate's pass recorded as a named decision and covered by a gate-level test. Task 5.2's test list has no case for an unreadable band passing check 7; only the facts-level case in 5.1 exists.

### [CONCERN] Nothing automated checks that program-blocked shows the asker's edge and the provider's request

Success criterion 1 (slice design line 422) requires that the block stays open and that `program-blocked` shows the asker's edge row and the provider's request row. Task 10.1 asserts store state (pending request, open unbound edge, `requested` record), not the listing and not that the block is still open. Task 9.1 asserts only that no new row appears on `program-blocked`. The listing is checked only by hand in 11.2. Add an assertion to 10.1 at the mid-request point: `program-blocked` lists the asker's edge row with `request_open` and the provider's `request` row, and the asker's block is still open.

### [CONCERN] The new per-question reads have no load test

`.claude/rules/python.md:56` requires at least one load test for code on the concurrency or environment-layer paths, and says CI must gate it. Task 7.2 adds reads to every member question's assembly (`edges_waiting`, `edges_provided_by`, and `request_for_edge` for each listed edge, which is N+1 per tick). Task 5.1 also opens a member store per request. The design's Cost paragraph states the bound: "two or three program-store reads" per member question (slice design line 506). 182 applied the same rule to its tick-time reads (182's Task 7.3 adds `tests/load/test_program_passages_load.py`). 185 only re-runs three existing files in 11.1. Add a task under `tests/load/`, such as `test_request_reads_load.py`, that asserts a read-count and time bound for a tick with several member questions and edges. No CI task is needed: `.github/workflows/ci.yml:54` already runs `uv run pytest tests/load`, so a new file there is gated. The task should say so, as 181 and 182 do.

### [CONCERN] Task 6.2 is too large for one task

Task 6.2 covers the block check, the refusal path, four writes (`journal_resolve` with an eight-key result, `create_request`, `mark_requested`), the asking-slice label derivation, the new `QuestionOutcome.REQUESTED`, and five test scenarios, all in one function that the task says must stay "under ~50 lines." That is hard to fit with the project's function size rule. Split it into 6.2a (step 0, the gate call, and the refusal path, with the refusal tests) and 6.2b (the pass path: a result builder, the three writes, the label helper, and `QuestionOutcome.REQUESTED`, with the invariant and key-shape tests). Name the builder and the label helper as separate functions.

### [CONCERN] Task 0.2 names the no-program regression without a file path

Task 0.2 says "182's no-program answering regression" with no path. In 182 it is not a separate file: 182's Task 7.1 extends "Task 0.2's baseline test (same file, name contains `baseline`)" (182-tasks.program-concept-as-a-source.md:231). A junior would have to infer the file. Tasks 0.2 and 10.3 both depend on it. Name the file in both tasks, as 0.2 already does for 183's test. If it is not on the target, 0.2 should say so as a BLOCKED case.

### [NOTE] Task 0.1's BLOCKED rule and its inputs

- The BLOCKED rule names only 182, 183 and 184. Task 0.1 also checks 181 and 140, and says nothing about a missing 181 or 140.
- Task 1.1 creates migration 017 on top of 183's `016_slice_heads.sql`. The schema directory currently ends at 015, so 016 comes from 183. 0.1 should record that 016 exists and that the expected version is 16.
- Line 62 says "change nothing", and line 68 tells the junior to write a name list into the task file. Say that the list is a task-file edit, not a code change.

### [NOTE] Task 1.1 bundles four separable changes

The task covers the state, transitions, eight decline reasons, `request_id`, migration 017 with the version bump, `mark_requested`, and the `answerer_answers_in_run` rename. That spans four source files and four test files. A junior can do it, but splitting it into state and migration, `mark_requested`, and the rename would give cleaner checks. Optional.

### [NOTE] Some tests repeat each other across tasks

- Task 6.3's crash-after-write-1 test repeats the first crash point in 6.6. Keep the crash assertions in 6.6.
- A non-member asker with a `kind: request` reply is tested in 6.4, 10.2 and 10.3. Keep the end-to-end case in 10.2 and the writes-equal-decline comparison in 10.3.
- Task 6.5's PM-after-write-2 test overlaps 10.2's end-to-end case. 6.5 needs only the sweep-side assertion.

None of these leaves a success criterion uncovered. Each costs an extra test to maintain.

### [NOTE] `-k` selects by name, not by marker

Task 10.1 says "A `-k mid_request` marked test." `-k` matches test names and keywords, not markers. Name the test `test_mid_request_...`, which is the form the design's walkthrough uses (slice design line 467).

### [PASS] Success criteria are covered by tasks

- Request path and block: 6.2, 10.1. Refusals with their reasons: 5.2, 6.2, 10.2. Crash points: 6.3, 6.5, 6.6.
- PM before and after write 2: 6.2, 6.5, 10.2. Release: 1.2, 10.1. No program: 6.4, 10.2, 10.3.
- `program_requests` and its size rule: 7.1, 7.2. Visibility: 7.3. `request_limit`: 2.1.
- Purity: 3.2, 5.2, 7.1. Parser fixtures: 3.1. Stub-`sq` stage tests: 10.1, 10.2. Migration 017 on every 140 state: 1.1.
- Docs: 2.2, 10.4, 10.5, 11.3. Walkthrough: 9.1, 10.1, 11.2.
- The one gap is the program-blocked listing, covered above.

### [PASS] No scope creep, no merge or push task, sound commit points, and a proportionate file

Every task traces to a decision D1–D12. No task merges or pushes. Commit markers sit at the end of each section, after working and tested points (lines 88 to 255). Tests are inside their tasks, so the test-with pattern holds. One 256-line file with 32 tasks is a reasonable size for a slice with twelve decisions, and no split is needed.

### [PASS] Names and paths the task file relies on exist

Checked against the target: `QUESTION_TRANSITIONS` (`store/question_models.py:73`), `COUNT_ANSWERER_ANSWERS_IN_RUN` (`store/sql_questions.py:119`), `_OPEN_STATES` (`store/answer_submission.py:41`), `AnswererSettings` and `answer_limit` (`runner/project_config.py:85,99`), `RESULT_DECISION` and `Settlement` (`runner/answering/finish.py:55,74`), `evaluate_gate` (`runner/answering/gate.py:29`), `decide_answer` (`decide.py:189`), `_settle_stranded` (`stage.py:114`), `decline_question`, `_write_evidence` and `_settle_question_on_acknowledgment` (`store/questions.py`), `journal_resolve` (`store/journal.py:153`), `QuestionInvariantError` (`runner/answering/settle.py:14`), and `finish.py` at 206 lines (matches the design). The `.claude/rules/` files, the test files and the docs the task file cites all exist. 183's and 184's modules are not on the target yet, so 0.1 will stop there, as designed.

### Run Digest

- Response length: 10834 chars
- Response is newline-free: no
- Tool calls made: 15
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 16
- Tokens — prompt / cached / cache write / completion / reasoning: 819800 / 662753 / 157033 / 60434 / not computed
- Duration: 260.7 s
- Cost: $0.21 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
