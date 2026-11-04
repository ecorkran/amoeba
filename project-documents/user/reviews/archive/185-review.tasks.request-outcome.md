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
reviewedSha: d3874a405132de98fd60021fa6e99b4086d7e688
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
effort: xhigh
turns: 25
promptTokens: 1121317
cachedTokens: 941575
cacheWriteTokens: 179724
completionTokens: 70833
durationSeconds: 362.0
costUsd: 0.267048
costBasis: provider
runId: run-20261104-tasks-plan-3bf84a0f
squadronVersion: 0.24.20
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "The commit after Task 3.2 fails pyright: `finish.py` still routes `decide_answer` results to `Declined`"
    location: "src/amoeba/runner/answering/finish.py:110-112"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Adding `request_id` to `QuestionRecord` breaks its direct constructors"
    location: "src/amoeba/store/question_models.py:99"
  - id: F003
    severity: concern
    category: correctness
    summary: "\"Store None, add no default value\" would make `request_limit` required and reject existing configs"
    location: "src/amoeba/runner/project_config.py:99"
  - id: F004
    severity: concern
    category: completeness
    summary: "The request gate's `prior_answers` has no named source, and the count's consumer is never wired"
    location: "src/amoeba/store/answer_submission.py:138"
  - id: F005
    severity: concern
    category: precondition
    summary: "Migration 017 assumes 183's 016 lands first, and the preflight does not check it"
    location: "src/amoeba/store/migrations.py:36"
  - id: F006
    severity: concern
    category: consistency
    summary: "The design says 183's and 184's design text gets updated; the task forbids editing those designs and never does it"
    location: "project-documents/user/slices/185-slice.request-outcome.md:408"
  - id: F007
    severity: concern
    category: coverage
    summary: "Task 10.2 drops two scenario variants that the walkthrough names"
    location: "project-documents/user/slices/185-slice.request-outcome.md:460"
  - id: F008
    severity: concern
    category: granularity
    summary: "The task file is heavier than the slice warrants; four merges cut it without losing coverage"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:88"
  - id: F009
    severity: note
    category: accuracy
    summary: "Task 6.2 says \"nine refusals\", but there are ten decline reasons"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:164"
  - id: F010
    severity: note
    category: coverage
    summary: "The load case is already CI-gated; its base file is not preflighted"
    location: ".github/workflows/ci.yml:54"
  - id: F011
    severity: note
    category: coverage
    summary: "\"A need in the asker's own part is not requested\" rests on the check model"
    location: "project-documents/user/slices/185-slice.request-outcome.md:423"
  - id: F012
    severity: pass
    category: coverage
    summary: "Every success criterion has a task, and nothing is out of scope"
    location: "project-documents/user/slices/185-slice.request-outcome.md:418"
  - id: F013
    severity: pass
    category: verification
    summary: "Names, files and dependencies match main; the 181–184 gaps are handled by the BLOCKED rule"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:67"
  - id: F014
    severity: pass
    category: sequencing
    summary: "Commit markers sit at working points, with one formatting nit"
    location: "project-documents/user/tasks/185-tasks.request-outcome.md:97"
---

# Review: tasks — slice 185

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] The commit after Task 3.2 fails pyright: `finish.py` still routes `decide_answer` results to `Declined`

Task 3.2 (lines 117–120) makes `decide_answer` return `Requested`, and the marker at task line 122 commits 3.1–3.2. The only caller, `settle_run_result`, narrows with `isinstance(decided, Confirmed)` (line 110) and passes the remainder to `_decline(store, record, decided: Declined)` (line 112; signature at line 168). With `Requested` in the union, pyright strict fails at line 112, and the plan's own gate says to run pyright before markers. Task 6.5 is the first task that handles `Requested`. Fix: have 3.2 add an explicit `Requested` arm that raises `NotImplementedError` until 6.5, or move the marker at line 122 to after 6.5.

### [CONCERN] Adding `request_id` to `QuestionRecord` breaks its direct constructors

`QuestionRecord` is a frozen dataclass with no defaults. Task 1.2 (line 81) adds `request_id: str | None` and its row mapping, but not the constructors. Direct construction exists in `tests/runner/answering/test_settle.py` and in the row mapper, `store/mapping_questions.py`. Pyright strict then fails at the marker on line 97. Fix: have 1.2 name both sites and state that every direct construction passes `request_id=None`.

### [CONCERN] "Store None, add no default value" would make `request_limit` required and reject existing configs

`AnswererSettings` is a pydantic `BaseModel`. In pydantic v2, an `X | None` field with no `= None` is still required. Task 2.1 (line 102) says both "store None" and "add no default value", which can be read as forbidding the `= None` that makes absence work. Result: an existing `projects.yaml` without the key would fail to load, breaking the criterion that such a file "loads unchanged" (design line 430). Fix: say the field is declared `= None`. That is the absent value, not a magic default, which matches D11's "not a default value" intent.

### [CONCERN] The request gate's `prior_answers` has no named source, and the count's consumer is never wired

Task 1.4 (lines 88–91) exposes the count as `answerer_answers_in_run`, but never names the code it renames: `_prior_answers`, defined at `answer_submission.py:138` and used by the existing answer gate at line 112 (`gate(record.question, self._prior_answers(record))`). No later task calls the new public method. Task 6.2 (line 163) calls `evaluate_request_gate` without saying where `prior_answers`, `settings`, `asking_project` or `facts` come from. Fix: name `_prior_answers` as the code form in 1.4, and have 6.2 state `prior_answers = store.answerer_answers_in_run(record)` and where `settings` comes from (the answerer section via `RequestContext`).

### [CONCERN] Migration 017 assumes 183's 016 lands first, and the preflight does not check it

The schema directory ends at 015 and `EXPECTED_SCHEMA_VERSION` is 15 (line 36). The number 017 is correct only if 183 adds `016_slice_heads.sql` first (183 design lines 109 and 375, "project schema version 16"). Task 0.1 (lines 60–69) does not check for 016 or for the expected version. Task 1.2 (line 81) says "raise the constant" without the from and to values. Fix: 0.1 checks that `store/schema/016_slice_heads.sql` exists and `EXPECTED_SCHEMA_VERSION` is 16. 1.2 states "16 to 17."

### [CONCERN] The design says 183's and 184's design text gets updated; the task forbids editing those designs and never does it

The design's Provides section says "184's Integration Points line for 185 and 183's D8 are updated to say so." Task 0.1 (line 68) says "Do not edit the other slices' designs," and no task makes the update. Neither outcome is planned. Fix: either add a doc-only step (in 10.5 or 10.6) that updates those two design lines, or remove the sentence from the design, and say which in the task.

### [CONCERN] Task 10.2 drops two scenario variants that the walkthrough names

The walkthrough says the scenario file holds "each gate refusal, a non-member asker, and a kill at each of the four crash points" (line 460). Line 473 says a request from a project with no `request_limit` "declines `request_limit_unconfigured` (a variant in step 1's scenario file)". Task 10.2 (line 235) keeps one refusal and omits the `request_limit_unconfigured` variant without saying so. The non-member case is covered by 10.3 and the crash points by 6.7, which is defensible, but the walkthrough's file reference is now wrong. Task 11.2 (line 266) then checks step 3's expected decline only by hand. Fix: add the `request_limit_unconfigured` case to 10.2, and record in 10.2 where the other variants live.

### [CONCERN] The task file is heavier than the slice warrants; four merges cut it without losing coverage

The file has 37 top-level tasks in 12 sections and 15 commit markers, in 277 lines. The design rates the slice "Relative effort: 3" and lists nine development steps. Merges that keep every criterion covered: 1.4 into 1.3 (one public method, one test file); 2.2 into 10.5 (both are one doc line); 7.3 into 7.2 (test-only, same module); 10.3's one added case into 10.2 (it runs through the real stage, as the scenario tests do). That removes four tasks.

### [NOTE] Task 6.2 says "nine refusals", but there are ten decline reasons

The nine checks produce ten reasons, because check 7 yields two (`requests_initiative_full` and `requests_band_collision`) and checks 3 and 4 reuse 142's reasons. Task 5.2 (line 151) lists the ten correctly. Parametrize 6.2 over those ten, and say "ten reasons" in the task.

### [NOTE] The load case is already CI-gated; its base file is not preflighted

`ci.yml:54` runs `uv run pytest tests/load` as its own step, so Task 10.4's new case in `tests/load/test_program_load.py` is gated without a new CI task. That file is absent on main, since 181 adds it, and Task 0.1 does not check for it. Add it to 0.1's list. 10.4 traces to the design's Cost bullet (line 506), not to a success criterion, which fits the 181–184 pattern. No change beyond the preflight.

### [NOTE] "A need in the asker's own part is not requested" rests on the check model

The plan covers the mechanism through the check-`no` decline (3.2, 10.2) and pins the instruction text (8.1). The placement judgment itself is the check model's, and a stub writes the check reply, so no deterministic test can prove it. Say so in the verification summary, so nobody reads 8.1's pinned text as a test of the behavior.

### [PASS] Every success criterion has a task, and nothing is out of scope

Functional: F1 → 6.3, 10.1; F2 → 3.2, 10.2; F3 → 5.2, 6.2; F4 → 6.7; F5 → 6.2, 6.6, 10.2; F6 → 1.5, 10.1; F7 → 5.2, 10.3; F8 → 7.1–7.3; F9 → 2.1. Technical: purity → 3.2, 5.2, 7.1; parser shapes → 3.1; stage with stub `sq` → 10.1, 10.2; no-program regression → 0.2, 10.3; migration 017 on every 140 state → 1.2; format, lint, typecheck → 11.1; docs → 2.2, 10.5, 10.6, 11.3. Integration → 10.1, 10.3; walkthrough → 11.2. Every task traces to a design item.

### [PASS] Names, files and dependencies match main; the 181–184 gaps are handled by the BLOCKED rule

These names exist on main: `QUESTION_TRANSITIONS` (`question_models.py:73`), `_OPEN_STATES` (`answer_submission.py:41`), `COUNT_ANSWERER_ANSWERS_IN_RUN` (`store/sql_questions.py:119`), `RESULT_DECISION` (`finish.py:55`), `_settle_stranded` (`stage.py:114`), `QuestionInvariantError` (`settle.py:14`), `_settle_question_on_acknowledgment` (`store/questions.py:225`), `AnswererSettings` (`project_config.py:85`). The test files and four contract docs the plan names exist, and so do the `.claude/rules/` paths. `DeclineReason` has no SQL CHECK, so no migration is needed for the new reasons. Absent from main, as expected: the 181–184 code, `tests/load/test_program_load.py`, and migration 016. Task 0.1's BLOCKED rule covers those. Dependencies have no cycles, and tests sit with their implementation.

### [PASS] Commit markers sit at working points, with one formatting nit

Markers close each functional group, and every one except the 3.2 marker (CONCERN above) is at a point where its tests can pass. The marker at line 171 has no blank line before "- [ ] **6.4" at line 172. It renders as a list, but a blank line keeps the section structure clear.

### Run Digest

- Response length: 12262 chars
- Response is newline-free: no
- Tool calls made: 24
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 25
- Tokens — prompt / cached / cache write / completion / reasoning: 1121317 / 941575 / 179724 / 70833 / not computed
- Duration: 362.0 s
- Cost: $0.27 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
