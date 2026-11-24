---
docType: review
layer: project
reviewType: tasks
slice: local-work-through-the-hub
conventionsSource: AGENTS.md
projectRules: [general.md]
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/262-tasks.local-work-through-the-hub.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261123
dateUpdated: 20261123
reviewedSha: 00941d46af41185ad56b05aecc87e77622b05234
reviewedBlob: 8287fb128a68938c56c110c89df1599ee3affff8
reviewedBlobCurrent: false
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 86
injected:
  - key: input
    path: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md"
    chars: 57524
    sha256: 964e41d1360ce64a6fcc3e00c1ecb83cbe750fe54655f13c83ede25a396bedcb
    whole: true
  - key: against
    path: "project-documents/user/slices/262-slice.local-work-through-the-hub.md"
    chars: 105244
    sha256: f5ca635cb693561d6d55dd9d054227c2a03e641bb5482b0e7b5f2b9c0168cd85
    whole: true
  - key: conventions
    path: "AGENTS.md"
    chars: 24525
    sha256: 2387512002bb2a73aa247bc36bc98d7162c5b5110ded41f56319d098d282ddbc
    whole: true
filesRead:
  - "src/amoeba/store/schema/008_waiting_on_request.sql"
  - "src/amoeba/store/schema/009_wakes.sql"
  - "src/amoeba/store/schema/011_hub_and_door.sql"
  - "src/amoeba/operations/prune.py"
  - "src/amoeba/wiring_release.py"
  - "src/amoeba/wiring.py"
  - "src/amoeba/wiring_door.py"
  - "src/amoeba/operations/send.py"
  - "src/amoeba/operations/wake_door.py"
  - "src/amoeba/store/held_questions.py"
  - "src/amoeba/operations/resume.py"
  - "src/amoeba/operations/pause_class.py"
  - "src/amoeba/operations/question_sweep.py"
  - "src/amoeba/store/store.py"
  - "src/amoeba/cli/render/waiting.py"
  - "tests/store/test_wakes.py"
  - "src/amoeba/operations/wake.py"
  - "tests/test_ci_gates_load.py"
  - "tests/hub/test_door_operations.py"
  - "tests/hub/test_join.py"
  - "tests/test_wiring.py"
  - "src/amoeba/hub/calls.py"
  - "src/amoeba/operations/answer.py"
  - "tests/hub_fixture.py"
  - "src/amoeba/store/questions.py"
searches:
  - "grep EXPECTED_SCHEMA_VERSION|DOOR_VERSION|CALL_BOUND_SECONDS|BUSY_TIMEOUT_SECONDS in /Users/manta/source/repos/manta/amoeba/src"
  - "grep refuse_if_joined|class NotServedError|LocalStoreClosedError|class ClientFileError|StepReplyError|OPERATIONAL_ERRORS|^OPERATION_ERRORS in /Users/manta/source/repos/manta/amoeba/src"
  - "grep def resume_bound_seconds|def answering_wait_seconds|resume_bound_seconds|answering_wait_seconds in /Users/manta/source/repos/manta/amoeba/src"
  - "list_files src/amoeba/store/schema/*.sql in /Users/manta/source/repos/manta/amoeba"
  - "grep CHECK|CREATE TRIGGER|CREATE INDEX|CREATE TABLE|DROP TABLE|ALTER TABLE|RENAME in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/schema"
  - "grep def insert_question|def insert_held|def claim_wake|def can_wake|WakeScope|ACTING_MACHINE|ALL_MACHINES|def acting|def act_as|def call_scope|INSERT_QUESTION|def record_resume|def mark_resume_started|MARK_RESUME_STARTED|def mark_start_attempted|def settle_answered|def finish_wake|def set_command_pid|de\u2026 in /Users/manta/source/repos/manta/amoeba"
  - "grep MAX_STARTS_PER_CALL|class ClosedReason|class WakeOutcome|class DeclineReason|class SkipReason|class RefusalCode|ENDED_TEXT|UNKNOWN_ADVICE|SERVED_OPERATIONS|WRITING_CALLS|HELLO_CALL|MAX_CALL_BYTES|UNKNOWN_ADVICE in /Users/manta/source/repos/manta/amoeba/src"
  - "grep record_resume\\(|mark_start_attempted\\(|can_wake\\(|mark_resume_started|claim_held\\(|settle_waiting\\(|settle_held_waiting\\(|replace_claim\\(|insert_held\\(|sweep_run\\(|open_rows_of_run|sweep_candidates in /Users/manta/source/repos/manta/amoeba"
  - "grep def (test_claimed_exits_by_the_sweep_once_it_is_old_enough|test_an_old_claim_closes_and_a_young_one_stays|test_an_unresumed_answer_past_the_bound_becomes_not_delivered|test_an_answer_inside_the_bound_stays_including_one_with_a_fresh_resume_start|test_a_refused_answer_is_judged_from_its_newest_sign_o\u2026 in /Users/manta/source/repos/manta/amoeba/tests"
  - "list_files tests/**/{test_wiring_release,test_request_release,test_request_release_child,test_held_question_exits,test_handle_pause,test_status_calls,test_message_timing,test_import_boundaries,test_hold_release_cli,test_start_ended_held_load,release_child_wait,test_joined_entry_points,test_ci_gates_load,test_u\u2026 in /Users/manta/source/repos/manta/amoeba"
  - "grep DoorHooks|class DoorHooks|def two_machine_hub|def env_for|_seed_answers|def seed|rm_machine|sq-stub|\\.sq-stub in /Users/manta/source/repos/manta/amoeba"
  - "grep request_release|wiring_release|start_after|START_AFTER|start_ended_held|START_BOUND_SECONDS|MAX_STARTS_PER_CALL|wiring_releases|request-release|release_child_wait|child_finished|wait_until in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep wiring_release|wiring_releases|request_release|forbidden|FORBIDDEN in /Users/manta/source/repos/manta/amoeba/tests/test_import_boundaries.py"
  - "grep \"answer\"|'answer' in /Users/manta/source/repos/manta/amoeba/tests/hub"
  - "list_files tests/live/{hold,waking}/**/*.py in /Users/manta/source/repos/manta/amoeba"
  - "grep operations\\.request_release|operations import request_release|from amoeba\\.wiring_release|amoeba\\.wiring_release import|START_AFTER_OPERATIONS|start_after|START_BOUND_SECONDS|MAX_STARTS_PER_CALL|request_release_child|request-release|wake_door|wiring_release\\b|release_child_wait|wiring_releases in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep request_release|wiring_release|start_after|START_AFTER|request-release|wake_door|claim_held|LOG_DIRECTORY|prune\\(|run_prune|prune_after_days in /Users/manta/source/repos/manta/amoeba/src"
  - "grep [Rr]elease|start_ended|hold in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep wake|logs_dir|SEND|def |ANSWER in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/served.py"
  - "grep resume_wait_seconds|answering_wait_seconds|prune_after_days|wake_timeout|max_wakes|RUN_POLL_TIMEOUT_SECONDS: |TERMINATE_GRACE_SECONDS: |RETRY_SECONDS: |CONNECT_SECONDS: |READ_SECONDS: |def classify_pause|def classify_runs|def _judge|def _mark_undelivered|def classify_run_only|def mark_not_delivered|\u2026 in /Users/manta/source/repos/manta/amoeba/src"
  - "grep age|claimed_at|updated_at in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/status_runs.py"
  - "grep DeclineReason|ClosedReason|WakeOutcome|def test_|CHECK|waiting_reason in /Users/manta/source/repos/manta/amoeba/tests/store/test_vocabulary_pinning.py"
  - "grep COLUMN_REASONS|^\\s+\"(record|waiting|messages|answers|questions|wakes|holds|mirror)[a-z_]*\"|: \\(|REASON in /Users/manta/source/repos/manta/amoeba/tests/store/test_schema_holds_no_mirrored_state.py"
  - "grep ^\\s+\"[a-z_]+\": frozenset|\"questions\\.start_attempted_at\"|\"answers\\.resume_started_at\"|\"wakes\\.|\"questions\\.|\"answers\\.|\"messages\\. in /Users/manta/source/repos/manta/amoeba/tests/store/test_schema_holds_no_mirrored_state.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep claim_wake\\(|can_wake\\(|wake_due|import .*wake_support|from .*wake_support|wake_run_support|claimed_store in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep def claim|claim_wake|def seed_waking_member|def confirmed_session|wake_command|checkout in /Users/manta/source/repos/manta/amoeba/tests/store/wake_support.py"
  - "grep claim_wake|def claimed_store|can_wake in /Users/manta/source/repos/manta/amoeba/tests/operations/wake_run_support.py"
  - "grep claim_wake\\(|can_wake\\( in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep def open_state_store|act_as_local|def _claim_and_start|def wake_for_sent_request|can_wake|def open_hub_store|def rm_machine|remove_machine|transaction\\(|store.write\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "list_files .github/workflows/*.y*ml in /Users/manta/source/repos/manta/amoeba"
  - "grep def |amoeba list|restore|read.back|readback|null|machine in /Users/manta/source/repos/manta/amoeba/scripts/update_live.py"
  - "grep DOOR_VERSION|1\\)|2\\)|\\(1|\\(2|pinned|== \\( in /Users/manta/source/repos/manta/amoeba/tests/wire/test_times.py"
  - "grep answer|handle-pause|handle_pause|wake-run|wake_run|amoeba-mcp|UNSERVED|NOT_SERVED|def test_|SERVED in /Users/manta/source/repos/manta/amoeba/tests/hub/test_joined_entry_points.py"
  - "grep CallRefused|NOT_SERVED|raise in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/runs_document.py"
  - "grep NotServedError|refuse_if_joined|does not serve|wake-run.*joined|handle-pause.*joined|joined.*handle in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep NOT_SERVED|not_served|DOOR_VERSION|door_version|Door-Version|HEADER_DOOR_VERSION in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep def _needs_config|def place_served|def gather_values|def body_keys|class ServedEdges|def run_served|def handle_call|keep|def _kept|def _done|def run_served|CALL_RESULT_LIFETIME in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep answering_run|ANSWERING|def check_eligibility|cf|gather|def test_.*answer in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/pause_eligibility.py"
  - "grep def run_handle_pause|load_config|open_store|def run_wake_run|handle_pause\\(|wake_run\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba/cli"
  - "grep answering_run|answering run|def test_ in /Users/manta/source/repos/manta/amoeba/tests/operations/test_pause_eligibility.py"
  - "grep ^version|version =  in /Users/manta/source/repos/manta/amoeba/pyproject.toml"
  - "list_files src/amoeba/{operations/steps,operations/store_steps.py,operations/work_start.py,operations/resume_run.py,operations/resume_attempt.py,wiring_steps.py,cli/resume_command.py,hub/call_work.py,store/sql_local_work.py,store/schema/013_local_work.sql,steps,store/steps.py,operations/steps/models.py} in ."
  - "grep PATH|\\bsq\\b.*hub|cf.*git|assert.*PATH|\"PATH\" in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep def hub_path|def safe_path|SAFE|SYSTEM|/usr/bin|/bin\"|BIN_DIRECTORY|def amoeba_script in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep request-release|request_release|start_ended_held|start_attempted_at|start_after|after seven|seven operations|wiring_release|START_BOUND|5 starts|MAX_STARTS|0\\.6|figure in /Users/manta/source/repos/manta/amoeba/docs"
  - "grep from amoeba\\.store\\.store import|import amoeba\\.store\\.store in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations"
  - "grep FORBIDDEN|\"amoeba\\.|^    \"[a-z_]+\": \\( in /Users/manta/source/repos/manta/amoeba/tests/test_import_boundaries.py"
  - "grep INSERT_QUESTION|INSERT INTO questions|INSERT INTO wakes|INSERT_HELD|INSERT INTO messages|sql_held\\.INSERT|CLAIM_WAKE|INSERT INTO sessions in /Users/manta/source/repos/manta/amoeba"
  - "grep INSERT_NEW_QUESTION|INSERT_QUESTION in /Users/manta/source/repos/manta/amoeba"
  - "grep def read_store_for_judgement|claim_age|answering_wait_seconds|mark_not_delivered|def mark_not_delivered|def latest_answer|def _newest_sign in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep def test_.*(limit|age|stale|claim|old|young|at_limit|just) in /Users/manta/source/repos/manta/amoeba/tests/operations/test_pause_class.py"
  - "grep last_called_at in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep class WakeEntry|class QuestionEntry|machine|wake_entry|WakeEntry\\(|class .*Wake.*Entry|class .*Question.*Entry in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/status_models.py"
  - "grep == 12\\b|EXPECTED_SCHEMA_VERSION|== 12$ in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep wake_waiting|WakeEntry|class .*Wake|wakes: |\"wakes\"|wake_entries|WakeLine|read_member_wakes in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations"
  - "grep _wait|deadline|sleep|monotonic|seconds_left|clock in /Users/manta/source/repos/manta/amoeba/tests/operations/test_wake_run.py"
  - "grep def _wait|deadline_at|sleep|monotonic|clock in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/wake_run.py"
  - "grep /call|\"/call|call/|CALL_PATH|HEADER_CALL_NAME|name_from|request.name|path in /Users/manta/source/repos/manta/amoeba/src/amoeba"
sectionsInDocument: 12
sectionsCovered: 12
effort: xhigh
turns: 87
promptTokens: 9927145
cachedTokens: 9603120
cacheWriteTokens: 323937
completionTokens: 185049
durationSeconds: 799.8
costUsd: 1.14523
costBasis: provider
runId: run-20261124-p5-86ef1af7
squadronVersion: 0.24.38
findings:
  - id: F001
    severity: fail
    category: existing-tests
    summary: "An existing test that 7.1 breaks is not in the named edit list"
    location: "tests/hub/test_join.py:259-273"
  - id: F002
    severity: fail
    category: coverage
    summary: "The wake entries' `machine` field, which a success criterion requires, has no task"
    location: "src/amoeba/operations/status_models.py:193"
  - id: F003
    severity: concern
    category: sequencing
    summary: "The door branch of `send` can claim a wake before the door can carry its log directory or refuse version 1"
    location: "src/amoeba/operations/send.py:88-101"
  - id: F004
    severity: concern
    category: sequencing
    summary: "The local wake mark is placed in a write that comes after the read it has to satisfy"
    location: "src/amoeba/operations/wake.py:110-116"
  - id: F005
    severity: concern
    category: sequencing
    summary: "Task 3.1's import rule covers modules that import the store today"
    location: "tests/test_import_boundaries.py:30-62"
  - id: F006
    severity: concern
    category: sequencing
    summary: "Task 6.6 depends on a per-command holder that 7.3 creates"
    location: "src/amoeba/wiring.py:168-180"
  - id: F007
    severity: concern
    category: existing-tests
    summary: "`can_wake`'s agreement test asserts a due wake before any mark exists"
    location: "tests/store/test_wakes.py:197-208"
  - id: F008
    severity: concern
    category: proportionality
    summary: "Task 10.2's size check omits two files the slice grows"
    location: "src/amoeba/operations/pause_context.py"
  - id: F009
    severity: concern
    category: coverage
    summary: "Task 8.4 narrows \"time each step once\" to three steps"
    location: "tests/load/test_door_load.py"
  - id: F010
    severity: concern
    category: code-fit
    summary: "A kept reply can replay a stale `work` flag"
    location: "src/amoeba/hub/calls.py:191"
  - id: F011
    severity: concern
    category: granularity
    summary: "Two long sections are single commits"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md"
  - id: F012
    severity: note
    category: clarity
    summary: "Task 1.2 names a statement the production path does not use"
    location: "src/amoeba/store/questions.py:197"
  - id: F013
    severity: note
    category: clarity
    summary: "Task 2.3's caller list for `record_resume` does not match the code"
    location: "src/amoeba/store/answers.py:210"
  - id: F014
    severity: note
    category: documentation
    summary: "The `sq` and `cf` versions could not be checked here"
    location: "unverified"
  - id: F015
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md"
  - id: F016
    severity: pass
    category: code-fit
    summary: "Verified figures and named files"
    location: "src/amoeba/operations/resume.py:50-64"
  - id: F017
    severity: pass
    category: code-fit
    summary: "Schema, vocabulary and deletion claims hold"
    location: "src/amoeba/store/schema/011_hub_and_door.sql:95-99"
  - id: F018
    severity: pass
    category: coverage
    summary: "The hub `PATH` requirement and the load gate are enforced"
    location: "tests/hub_fixture.py:79-85"
---

# Review: tasks — slice 262

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] An existing test that 7.1 breaks is not in the named edit list

`test_a_joined_machine_serves_the_served_operations_through_the_hub_and_no_other` asserts that `wiring.invoke(OperationName.ANSWER, ...)` on a joined machine raises `NotServedError` with "does not serve answer yet" (line 267). Task 7.1 adds `answer` to `SERVED_OPERATIONS` (task line 268), so `route` (`wiring_door.py:112`) sends the call to the hub and the assertion fails. Neither 7.1 (lines 270-271) nor 7.4 (lines 284-286) names this file, and task line 49 says to fix the code rather than a test that is not on the named list. Add it to 7.1's named edits and say what the test now asserts.

### [FAIL] The wake entries' `machine` field, which a success criterion requires, has no task

Task 5.4 (line 215) adds `machine` to question entries only. The design lists "machine on question and wake entries of `status`" among the result fields (design line 647) and requires "Question and wake entries show the machine `local`" on the PM's install (design line 751). `WakeStatus` (`status_models.py:193`, built by `read_member_wakes` at `status.py:214`) gets no field in any task. Line 203 mentions "the machine on wake entries" only in the docs. Add the field and its rendering to 5.4.

### [CONCERN] The door branch of `send` can claim a wake before the door can carry its log directory or refuse version 1

Task 5.1 (lines 199-201) makes the hub part of `send` claim a wake with `log_stem` from `logs_dir` and deletes the door refusal in `wake_door.py`. The door path is `local is None` (`send.py:90-101`). `served.py` has no `logs_dir` today, and task 7.2 is what adds it (line 276). `DOOR_VERSION` stays 1 until 7.1 (lines 268-269). Design line 387 says the version bump is what keeps an older client from receiving a wake it cannot start. Between the 5 and 7 commits, a 261 client's `send` can claim a wake with no log stem and no start, or fail on the missing argument. Move the served `send` changes and the version bump before the claim, or leave the door branch refusing until 7.2.

### [CONCERN] The local wake mark is placed in a write that comes after the read it has to satisfy

Line 113 says `send` sets the mark when the request is open after the call. Line 115 says `_claim_and_start` "sets the mark in the write before its claim." In the code, `_claim_and_start` reads `can_wake` (`wake.py:110-111`) and returns before its write (`116-119`). `wake_due` needs the mark (line 114), so a mark set only in the later write is invisible to that read, and no wake starts in the send that set it. That breaks 5.2's first criterion (line 205). Say the mark is written in `write_send`'s transaction, before `wake_for_sent_request` runs (`send.py:92-102`), and remove the phrase about `_claim_and_start`.

### [CONCERN] Task 3.1's import rule covers modules that import the store today

Line 131 adds a client-run rule for `handle_pause`, the `pause_*` modules, `claim_waiting`, `answering_settle`, `resume`, `resume_run`, `wake_run`, `prune` and `work_start` in the same task. The same line then says rules for modules not yet moved come with the task that moves them. Twelve of the listed modules already import `amoeba.store.store` (for example `resume.py:31`, `handle_pause.py`, `prune.py:33`, `wake_run.py`, `pause_claim.py`), so the rule as written fails the existing test. The test's `FORBIDDEN` table is keyed by package, so a per-module rule also needs a mechanism the task does not describe. 3.1 should add only the `operations.steps` rule, and each client-run rule should move with its module.

### [CONCERN] Task 6.6 depends on a per-command holder that 7.3 creates

Line 249 has `route` keep `work` and `work_problem` in "the same per-command holder DoorSteps writes (7.3)." Section 6 is committed before 7.3 (lines 279-280). The door path also returns before the `try/finally` where `start_after` runs (`wiring.py:171-180`), so "after_call on both paths" (line 250) needs that restructuring stated. Until 7.2 no hub reply carries `work`, so the door-path after-step has no flag to read in section 6. Create the holder in 6.6, or move the door-path after-step to 7.3.

### [CONCERN] `can_wake`'s agreement test asserts a due wake before any mark exists

Line 200 calls `can_wake` before any claim and expects True. Under D8 rule 1 there is no mark, so it returns False. Task 2.5's seed-helper list (line 116) names the `claim` helper but not this test's early call, and 2.6 (line 120) says the assertions are unchanged. Add `mark_wake_wanted` before line 200 to the named edits.

### [CONCERN] Task 10.2's size check omits two files the slice grows

Line 346 checks five files for "near 300 lines." Task line 43 says `store/answers.py` (296) gets a claim-id clause, and 4.7 (line 183) has `pause_context.py` (316 lines) take `Steps`. Neither is on 10.2's list. Add both. `store/sql.py` (543 lines, line 43) is already far over and gets edits too. Name it in 10.2 with the reason.

### [CONCERN] Task 8.4 narrows "time each step once" to three steps

Design line 571 says the idle-hub case "times each step once, with the same 200 ms median." Task line 318 keeps only `open_runs`, `pause_sources` and `claim_work`, and does not record a departure. Either time each step, using seeded data it needs, or list the steps left out with the reason.

### [CONCERN] A kept reply can replay a stale `work` flag

`keep` stores the whole reply (`calls.py:228-237`), and `_kept_reply` returns those bytes unchanged (line 191). Task 7.2 (line 275) requires a fresh flag on a kept-result repeat, but does not say the flag is kept out of the stored reply. If `call_work` runs before `keep`, a repeat returns the flag from the first call. State that the flag is added after the kept lookup.

### [CONCERN] Two long sections are single commits

Section 4 covers eight subtasks and about nine modules under one marker (line 194). Section 6 covers nine subtasks under one marker (line 263). Design line 818 orders the pause path "one module at a time," and each step is meant to leave the suite passing. Put markers after 4.3 (`question_settle` and `pause_sources`) and after 4.6, and after 6.5 in section 6, so a regression is caught at a working point.

### [NOTE] Task 1.2 names a statement the production path does not use

Line 80 names `sql.INSERT_QUESTION` and its only binder (`tests/store/seed.py:141`). Production `insert_question` binds `sql.INSERT_NEW_QUESTION` (`questions.py:197`, defined at `sql.py:299`). Name both, so the production statement is not missed.

### [NOTE] Task 2.3's caller list for `record_resume` does not match the code

Line 106 says the sweeps' `not_delivered`, dismiss, close and `rm-machine` pass `None`. In the code, the sweeps and close write through `mark_not_delivered` (`answers.py:210`, `question_closing.py:120`). The only source callers of `record_resume` are `answer.py:125` and `resume.py:101`, and about twenty test call sites need `claim_id`. Say whether `mark_not_delivered` clears the claim id. Design line 300 says only `resume_record` does.

### [NOTE] The `sq` and `cf` versions could not be checked here

Task lines 13 and 60 name sq 0.24.38 and cf 0.19.28. The design (line 88) says sq 0.24.34. This review has no shell, so it could not run `sq --version` or `cf --version`. Step 0.1 re-reads them, so this is a note, not a blocker.

### [NOTE] Proportionality is acceptable

The file is long: 56 tasks across ten sections. Each test list I checked traces to a success criterion or to D16's per-row and per-path tests, so I found nothing to cut except the size list in 10.2. The commit granularity finding above is the only structural change I would make.

### [PASS] Verified figures and named files

With the starter config (`resume_wait_seconds: 60`, `starter_config.yaml:11`), `resume_bound_seconds` is 60 + 0.5 + 2×30 + 2×5 + 5 = 135.5. Replacing the 5-second store wait with `2 × CALL_BOUND_SECONDS` (43, `wire/times.py:23`) gives 216.5, as 2.2 says. `pause_claim_seconds` is 600 + 86 = 686. The files named in 0.1, 6.8 and the Context Summary exist, and the 6.8 import list matches the test imports exactly.

### [PASS] Schema, vocabulary and deletion claims hold

`questions` and `wakes` at schema 12 carry owner triggers (`011:95`, `011:165`), which 1.1's rebuild must carry. `questions.waiting_reason` has no CHECK list, so `starts_exhausted` needs no schema change. The `COLUMN_REASONS` keys `record`, `messages` and `waking` that 1.1 cites exist. `ENDED_TEXT` (`cli/render/waiting.py:82`) is keyed by `ClosedReason`, as 1.1 says. The 6.7 deletion references match the code: `handle_pause.py:33`, `status_runs.py:252`, `store/models.py:140`, `wiring.py:54,180`, `send.py:36`.

### [PASS] The hub `PATH` requirement and the load gate are enforced

`hub_path()` asserts that `cf`, `sq` and `git` are absent from the hub `PATH`, so the Technical Requirement (design line 732) holds with no new task. 8.4's CI gating is explicit: the bare `Tests` step is what `tests/test_ci_gates_load.py` checks (lines 58-62).

### Run Digest

- Response length: 27382 chars
- Response is newline-free: no
- Tool calls made: 86
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 87
- Tokens — prompt / cached / cache write / completion / reasoning: 9927145 / 9603120 / 323937 / 185049 / not computed
- Duration: 799.8 s
- Cost: $1.15 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 18
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 18
- Finding-shaped matches — surviving validation: 18
