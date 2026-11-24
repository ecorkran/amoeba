---
docType: review
layer: project
reviewType: tasks
slice: local-work-through-the-hub
conventionsSource: AGENTS.md
projectRules: [general.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/262-tasks.local-work-through-the-hub.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261123
dateUpdated: 20261123
reviewedSha: 6cea70e0a6b62e6e2617da7f0547c3428165704f
reviewedBlob: e34229b8de1b46fdaa0d8656f2dc44507cb137d7
reviewedBlobCurrent: false
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 108
injected:
  - key: input
    path: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md"
    chars: 53181
    sha256: d1ad237974d16eb4b0d50725773feca35acd0a55a2808ca133b110d254f6bf79
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
  - "/Users/manta/.claude/projects/-Users-manta-source-repos-manta-amoeba/974c1990-d92c-42a6-a1c5-e31e1d369dc3/tool-results/toolu_012gWA1o6nofUC4Hmj3nL6k8.txt"
  - "src/amoeba/store/store.py"
  - "tests/store/seed.py"
  - "src/amoeba/store/wakes.py"
  - "tests/operations/wake_run_support.py"
  - "tests/store/test_message_sweep.py"
  - "tests/load/test_wake_claim_load.py"
  - "src/amoeba/operations/question_sweep.py"
  - "src/amoeba/operations/resume.py"
  - "src/amoeba/store/answers.py"
  - "src/amoeba/wire/times.py"
  - "tests/test_message_timing.py"
  - "src/amoeba/wiring.py"
  - "src/amoeba/wiring_release.py"
  - "src/amoeba/operations/request_release.py"
  - "src/amoeba/operations/status.py"
  - "src/amoeba/wire/protocol.py"
  - "src/amoeba/hub/calls.py"
  - "src/amoeba/wiring_door.py"
  - "src/amoeba/cli/main.py"
  - "tests/store/test_schema_holds_no_mirrored_state.py"
  - "tests/test_ci_gates_load.py"
  - "tests/load/test_door_load.py"
  - "tests/load/test_no_cf_under_write_lock.py"
  - "tests/test_contract_docs.py"
  - "src/amoeba/cli/render/waiting.py"
  - "src/amoeba/store/vocabulary.py"
  - "src/amoeba/store/machines.py"
  - "src/amoeba/hub/admin.py"
  - "src/amoeba/operations/answer.py"
  - "src/amoeba/operations/pause_claim.py"
  - "src/amoeba/operations/served.py"
  - "src/amoeba/store/sql.py"
  - "src/amoeba/store/questions.py"
  - "tests/test_import_boundaries.py"
  - "tests/store/wake_support.py"
searches:
  - "list_files src/amoeba/**/*.py in ."
  - "list_files src/amoeba/store/schema/*.sql in ."
  - "list_files tests/**/*.py in ."
  - "list_files scripts/*.py in ."
  - "list_files {src/amoeba/operations/wake_door.py,src/amoeba/operations/request_release.py,src/amoeba/wiring_release.py,src/amoeba/wiring_door.py,src/amoeba/wiring.py,src/amoeba/wiring_messages.py,src/amoeba/wire/*.py,src/amoeba/hub/*.py,src/amoeba/client/*.py,src/amoeba/operations/steps/*.py,src/amoeba/operation\u2026 in ."
  - "grep MAX_STARTS_PER_CALL|START_BOUND_SECONDS|resume_bound_seconds|answering_wait_seconds|def pause_claim_seconds|def resume_claim_seconds in src"
  - "grep DOOR_VERSION|CALL_BOUND_SECONDS|MAX_CALL_BYTES in src"
  - "grep DoorHooks in ."
  - "grep def can_wake|def claim_wake|def mark_resume_started|MARK_RESUME_STARTED|def record_resume|def mark_start_attempted|def finish_wake|def set_command_pid|def settle_answered|def insert_question|def insert_held|def claim_held|def replace_claim|def settle_waiting|def settle_held_waiting|def effective_sta\u2026 in src"
  - "grep mark_resume_started|MARK_RESUME_STARTED|mark_start_attempted|can_wake|claim_wake|insert_question\\(|insert_held\\(|record_resume\\(|\\bclaim_held\\(|settle_held_waiting\\(|settle_waiting\\(|replace_claim\\( in ."
  - "grep act_as|acting_machine|def call_scope|machine_id in src/amoeba/store/store.py"
  - "grep act_as|acting|machine_id|INSERT INTO (questions|wakes) in tests/store/seed.py"
  - "grep INSERT INTO (questions|wakes)|INSERT INTO questions|machine_id in src/amoeba"
  - "list_files tests/load/*.py in ."
  - "grep def (test_claimed_exits_by_the_sweep_once_it_is_old_enough|test_an_old_claim_closes_and_a_young_one_stays|test_an_unresumed_answer_past_the_bound_becomes_not_delivered|test_an_answer_inside_the_bound_stays_including_one_with_a_fresh_resume_start|test_a_refused_answer_is_judged_from_its_newest_sign_o\u2026 in tests"
  - "grep START_AFTER_OPERATIONS|start_after|start_ended_held|wake_door|NotServedError|refuse_if_joined|OPERATIONAL_ERRORS|OPERATION_ERRORS in src"
  - "grep RUN_POLL_TIMEOUT_SECONDS|TERMINATE_GRACE_SECONDS|BUSY_TIMEOUT_SECONDS|resume_wait_seconds|RETRY_SECONDS|CONNECT_SECONDS|READ_SECONDS in src"
  - "grep def classify_pause|def classify_runs|def classify_run_only|def sweep_run|sweep_run\\(|question_sweep|def status_sweep|def _sweep|classify_runs\\(|classify_pause\\(|claim_age_limit|limit in src/amoeba/operations"
  - "grep updated_at|claimed_at in src/amoeba/operations/pause_class.py"
  - "grep updated_at|claimed_at in src/amoeba/operations/status_runs.py"
  - "grep SERVED_OPERATIONS|WRITING_CALLS|UNKNOWN_ADVICE|HELLO_CALL|NOT_SERVED|REPLY_|\"work|body keys|class RefusalCode|= \"not_served\"|malformed_call|hub_error|bad_token in src/amoeba/wire"
  - "grep SERVED_OPERATIONS|WRITING_CALLS|UNKNOWN_ADVICE|HELLO_CALL|_needs_config|def handle_call|not_served|NOT_SERVED in src/amoeba/hub"
  - "grep UNKNOWN_ADVICE|WRITING_CALLS|SERVED_OPERATIONS|_advice|advice in src/amoeba/client"
  - "grep SERVED|needs_config|class ServedEdges|def run_served|def client_values_from_body|def _run|OperationName\\.|local: |def place_served in src/amoeba/operations/served.py"
  - "grep def place_served|def route|def invoke|NOT_SERVED|refuse_if_joined|def joined|class NotServedError|def _not_served|local_way|def served_names|SERVED in src/amoeba"
  - "grep DOOR_VERSION|EXPECTED_SCHEMA_VERSION|== 12|COLUMN_REASONS|\"answer\"|\"handle-pause\"|\"wake-run\"|handle_pause|wake_run|tuple in tests"
  - "list_files {tests/store/test_schema_holds_no_mirrored_state.py,tests/store/test_vocabulary_pinning.py,tests/store/test_migration_012.py,tests/store/test_migrations.py,tests/store/schema_11.py,tests/store/test_migration_011.py,tests/wire/test_times.py,tests/hub/test_joined_entry_points.py,tests/test_import_boun\u2026 in ."
  - "grep ^    \"(record|waking|messages|sessions|answering|settled|config|identity)\"|\"wakes\\.|\"messages\\. in tests/store/test_schema_holds_no_mirrored_state.py"
  - "grep \\(|\\)|def test|\" in tests/store/test_vocabulary_pinning.py"
  - "grep def |hub_fixture|two_machine_hub|env_for|HOME|PATH|class |def clock|set_clock|settable in tests/hub_fixture.py"
  - "list_files .github/workflows/*.y*ml in ."
  - "grep pytest|--ignore|-m |tests/load|deselect|marker in .github"
  - "list_files tests/live/{hold,waking}/**/*.py in ."
  - "grep ^def |^    def |read.back|readback|restore|backup|list|machine|schema|SCHEMA|version in scripts/update_live.py"
  - "list_files tests/scripts/*.py in ."
  - "list_files docs/*.md in ."
  - "grep class (ClosedReason|WakeOutcome|DeclineReason|SkipReason|RequestState|ResumeOutcome|WaitingReason)|_TEXT|DISPLAY|display|def .*text|_LABEL in src/amoeba"
  - "grep ENDED_TEXT|RUN_STATE_TEXT|assert_never|case WakeOutcome|case ClosedReason|case DeclineReason|WakeOutcome\\.EXITED|ClosedReason\\.RUN_GONE|DeclineReason\\.RESERVED_TERM|WakeOutcome\\.START_FAILED in src/amoeba"
  - "grep def rm_machine|def remove|DELETE FROM machines|DELETE FROM|machine_id|def _remove|transaction|write\\(\\) in src/amoeba/hub/admin.py"
  - "grep DELETE FROM machines|def remove|def delete|machines WHERE|REFERENCES machines|ON DELETE in src/amoeba"
  - "grep def act_as_local|act_as_local\\(|def open_state_store|def open_hub_store|LOCAL_MACHINE_NAME|def ensure_local|def acting_machine_for in src"
  - "grep BOUND|resume_bound|answering_wait_seconds|claim_age|claimed_at=|updated_at in tests/operations/test_question_sweep.py"
  - "grep BOUND|resume_bound|answering_wait|LIMIT|def test_an_old_unresumed in tests/operations/test_status_sweep.py"
  - "grep LIMIT|answering_wait|limit|claim_age|def test_|stale in tests/operations/test_pause_class.py"
  - "grep answering_run|answering run|def test_.*answering|cf_fails|exit|skip in tests/operations/test_pause_eligibility.py"
  - "grep clock|now|def |class |hooks|DoorHooks in tests/hub/in_process_hub.py"
  - "grep answering_wait|resume_bound|BOUND|LIMIT|def test_claimed_exits|def test_answered_unresumed|resume_wait in tests/operations/test_every_state_exits.py"
  - "grep def prune|sweep_candidates|prune_after_days|marker|def sweep_due|def _walk|logs_dir|resume|wake|file_problems|problems in src/amoeba/operations/prune.py"
  - "grep def sweep_candidates|def open_questions|def sweep_messages|def sweep_if_local|def prune_if_local|file_problems in src/amoeba/operations"
  - "grep request_release|wiring_release|wake_door|start_after|START_AFTER_OPERATIONS|MAX_STARTS_PER_CALL|START_BOUND_SECONDS|start_ended_held|release_child_wait|can_wake|wake_run_support|claim_wake\\( in tests"
  - "grep request_release|wiring_release|wake_door|start_after|START_AFTER_OPERATIONS|MAX_STARTS_PER_CALL|START_BOUND_SECONDS|start_ended_held|can_wake|mark_resume_started|MARK_RESUME_STARTED in docs"
  - "grep request_release|wiring_release|wake_door|start_after|START_AFTER_OPERATIONS|MAX_STARTS_PER_CALL|START_BOUND_SECONDS|start_ended_held|release_child_wait|can_wake|claim_wake\\(|refuse_if_joined|NotServedError|OPERATIONAL_ERRORS in tests"
  - "grep INSERT_QUESTION|INSERT_WAKE|INSERT_HELD|INSERT_ANSWER|sql_wakes|sql_held|sql\\.INSERT|from amoeba.store import sql|store\\.sql_held|sql_local_work in tests"
  - "grep INSERT INTO (questions|wakes|answers|messages)|INSERT INTO (questions|wakes) in tests"
  - "grep ^ in src/amoeba"
  - "grep answering_wait_seconds|resume_bound|dead claim|dead-claim|claim in docs/config-contract.md"
  - "grep INSERT_QUESTION|INSERT_HELD|INSERT_WAKE|INSERT_ANSWER|MARK_RESUME_STARTED|RECORD_RESUME|MARK_NOT_DELIVERED|SELECT_HELD|held_rows in src/amoeba/store"
  - "grep class (LocalStoreClosedError|HubHomeError|NoActingMachineError|ClientFileError|HubUnreachableError|HubRefusedError|CallRefused|StoreBusyError)\\b|def find_member|def find_caller|def classify_run_only in src/amoeba"
  - "grep REFERENCES questions|REFERENCES wakes|REFERENCES answers|FOREIGN KEY|PRAGMA foreign_keys|legacy_alter_table|DROP TABLE|RENAME TO in src/amoeba/store/schema"
  - "grep EXPECTED_SCHEMA_VERSION\\s*=|def migrate|foreign_keys|PRAGMA in src/amoeba/store"
  - "grep def result_from_document|def result_document|extra=|model_validate|def done_reply|def call\\(|return .*document|work|-> dict in src/amoeba"
  - "grep extra=|ConfigDict\\(|class StrictModel|class Wire|frozen=True, extra in src/amoeba"
  - "grep answering_run|ANSWERING|answering run|cf.*calls|calls == \\[\\]|cf_calls|no cf|not asked in tests"
  - "grep from store\\.seed import|from store import seed|store\\.seed in tests"
  - "grep ^\\s*insert_question,|import insert_question|insert_question\\s*\\}|seed import \\(?insert_question|from store.seed import .*insert_question in tests"
  - "grep MCP_CALL_DEADLINE_SECONDS(: Final)? ?=|MCP_CALL_DEADLINE_SECONDS: Final|MCP_CALL_DEADLINE_SECONDS =  in src/amoeba"
  - "grep def check_deadline|check_deadline\\(|deadline_seconds|MCP_CALL_DEADLINE|wait_for|timeout=|answer_bound_seconds\\( in src/amoeba/mcp"
  - "grep amoeba\\.operations|amoeba\\.store\\.store|def test_|FORBIDDEN|RULES|LAYER|\"amoeba\\. in tests/test_import_boundaries.py"
  - "grep def run_handle_pause|def run_wake_run|load_config\\(\\)|open_store\\(|state_layout\\(\\)|def run_invoked in src/amoeba/cli"
sectionsInDocument: 12
sectionsCovered: 12
effort: xhigh
turns: 109
promptTokens: 14644842
cachedTokens: 14271592
cacheWriteTokens: 373130
completionTokens: 195426
durationSeconds: 851.2
costUsd: 1.490024
costBasis: provider
runId: run-20261124-p5-86ef1af7
squadronVersion: 0.24.38
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "2.5 makes `claim_wake` refuse without a mark, and 2.6 says the existing wake tests pass unchanged"
    location: "src/amoeba/store/wakes.py:170"
  - id: F002
    severity: concern
    category: missing-item
    summary: "The test seed statement binds no machine, and 1.4's search does not find it"
    location: "src/amoeba/store/sql.py:270"
  - id: F003
    severity: concern
    category: doc-drift
    summary: "1.1 adds `machine_removed` to `ClosedReason` with no CLI-contract entry, so the 1.1 commit fails `test_contract_docs`"
    location: "tests/test_contract_docs.py:175"
  - id: F004
    severity: concern
    category: missing-item
    summary: "`list` and `status` have no display text for `machine_removed`, so a removed machine's closed question raises `KeyError`"
    location: "src/amoeba/cli/render/waiting.py:82"
  - id: F005
    severity: concern
    category: spec-gap
    summary: "2.3 changes `record_resume`'s contract without naming the claim-id parameter or what each caller passes"
    location: "src/amoeba/store/answers.py:162"
  - id: F006
    severity: concern
    category: state-hazard
    summary: "`answer()` keeps its refused record, which D6 forbids for a `started` attempt"
    location: "src/amoeba/operations/answer.py:112"
  - id: F007
    severity: concern
    category: spec-gap
    summary: "A served operation's `work` flag never reaches the after-step on a joined machine"
    location: "src/amoeba/wiring_door.py:117"
  - id: F008
    severity: concern
    category: spec-gap
    summary: "The stale-claim age uses `claimed_at` in the sweep and `updated_at` in `classify_pause`, against the design"
    location: "src/amoeba/operations/question_sweep.py:190"
  - id: F009
    severity: concern
    category: missing-item
    summary: "6.6 leaves a test that imports the deleted helper"
    location: "tests/cli/test_hold_release_cli.py:17"
  - id: F010
    severity: concern
    category: test-coverage
    summary: "The `inbox` assertion in `test_message_timing` reverses by design and is not on the reversed-test list"
    location: "tests/test_message_timing.py:192"
  - id: F011
    severity: concern
    category: doc-drift
    summary: "Stale references to deleted code survive 6.6, and 10.2's search does not cover docs"
    location: "docs/store-contract.md:495"
  - id: F012
    severity: concern
    category: size
    summary: "6.5 and 6.6 each bundle several units"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:242"
  - id: F013
    severity: note
    category: spec-gap
    summary: "`mark_start_attempted` gains a required parameter, and other callers are not named"
    location: "tests/store/test_held_questions.py:164"
  - id: F014
    severity: note
    category: spec-gap
    summary: "A `handle-pause` child's log directory is not named"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:239"
  - id: F015
    severity: note
    category: spec-gap
    summary: "The pause path's machine filter is not named"
    location: "src/amoeba/operations/question_sweep.py:145"
  - id: F016
    severity: note
    category: spec-gap
    summary: "The after-step's bound has no value in the task, and its test name is stale"
    location: "tests/test_message_timing.py:188"
  - id: F017
    severity: note
    category: spec-gap
    summary: "Sections 3, 4 and 5 are labelled `refactor:` but change behavior"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:154"
  - id: F018
    severity: note
    category: size
    summary: "Existing source files are at or past the size guide, and 10.2 checks only new files"
    location: "src/amoeba/wiring.py:297"
  - id: F019
    severity: note
    category: spec-gap
    summary: "The load test's \"times each step once\" does not say what state each step needs"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:312"
  - id: F020
    severity: note
    category: verification
    summary: "Tool versions and the read date were not checked"
    location: "unverified"
  - id: F021
    severity: note
    category: spec-gap
    summary: "7.4 leaves the CLI contract's location open"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:281"
  - id: F022
    severity: pass
    category: precondition
    summary: "Precondition names and migration 012 are present"
    location: "src/amoeba/store/schema/012_members_by_name.sql"
  - id: F023
    severity: pass
    category: ci-gating
    summary: "The load test is gated by the existing Tests step"
    location: "tests/test_ci_gates_load.py:58"
  - id: F024
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:672"
---

# Review: tasks — slice 262

**Verdict:** FAIL

> Verdict note: the frontmatter verdict is CONCERNS. The reviewer stated FAIL; its fail finding was fixed; all twenty-one findings were checked against the source 20261124; thirteen changed the task file, eight were dropped, see Resolution.
**Model:** claude-haiku-5-5

## Findings

### [FAIL] 2.5 makes `claim_wake` refuse without a mark, and 2.6 says the existing wake tests pass unchanged

Task 2.5 (line 115) makes `claim_wake` call `wake_due`. Design D8 (slice lines 371, 375) makes rule 1 require a `wake_wanted_at` mark, which only `send` sets. Today `claim_wake` checks the member, the checkout, a live session, a live wake and the daily limit (wakes.py:118-146), with no request needed. Direct callers build a member and a checkout and claim with no request, so they get `None` once the mark is required: `tests/store/wake_support.py:81-96` (`claim`, used by other wake tests), `tests/operations/wake_run_support.py:106-118` (`claimed_store`, which asserts `claimed is not None`), `tests/store/test_wake_on_checkout.py:86`, `tests/operations/test_add_wake_command.py:212`, `tests/operations/test_message_sweep_wrapper.py:173` and `tests/store/test_acting_machine.py:171`. Task 2.6 (line 119) says the 244 wake tests "pass unchanged apart from the renamed function", which cannot hold. The local `send` path (wake.py:111-118) also has to set the mark before its claim, and 2.5 does not order that. Fix: have the helpers set a mark through a `send`, or record the decision that the store-level claim keeps today's checks. Then correct 2.6.

### [CONCERN] The test seed statement binds no machine, and 1.4's search does not find it

`sql.INSERT_QUESTION` (sql.py:270-274, commented as kept for tests) is bound only by `tests/store/seed.py:insert_question` (seed.py:140-155). That helper passes eleven values and no `machine_id`. Once 1.2's trigger aborts on a null machine (line 75), every test that seeds a question through it fails. `tests/store/test_acting_machine.py:40` imports it as `seed_question`. Task 1.4 (line 88) finds raw inserts with `grep "INSERT INTO questions\|INSERT INTO wakes"`, which does not match the constant. Fix: name `sql.INSERT_QUESTION` and `tests/store/seed.py` in 1.2, and say they bind the acting machine, as `seed.py` already binds `owner_id`.

### [CONCERN] 1.1 adds `machine_removed` to `ClosedReason` with no CLI-contract entry, so the 1.1 commit fails `test_contract_docs`

The test (lines 175 and 184) requires every `ClosedReason` value, in backticks, in `docs/cli-contract.md`. Task 1.1 (line 78) names only `docs/store-contract.md`. Task 9.2 (line 326) and design D15 (slice line 558) do not list the value for the CLI contract either. Context line 50 says the task that adds a value adds its entry. Fix: add `machine_removed` to the CLI contract in 1.1, and to 9.2.

### [CONCERN] `list` and `status` have no display text for `machine_removed`, so a removed machine's closed question raises `KeyError`

`ENDED_TEXT` maps `AnsweredBy` and `ClosedReason` to display text (lines 82-88), and the renderer indexes it with a closed question's reason (line 305). Task 1.1 (line 71) says "each with its display text where the enum has one" and does not name this table. Fix: name `ENDED_TEXT` in 1.1 and give `machine_removed` a text.

### [CONCERN] 2.3 changes `record_resume`'s contract without naming the claim-id parameter or what each caller passes

Task 2.3 (line 106) says `record_resume` "clears `resume_claim_id` only when it equals the caller's". The function takes no claim id today (answers.py:162-170). The task does not say whether the parameter is required or optional, or what the sweep, dismiss, close and test callers pass. There are more than twenty call sites across `src` and `tests`, for example `src/amoeba/operations/answer.py:125` and `src/amoeba/operations/resume.py:101`. Before 3.3, the legacy `resume()` must also carry the id from `claim_resume`, and 2.3 does not say so. Fix: name the parameter, say callers with no claim pass `None`, and say how the legacy `resume()` threads the id in 2.3.

### [CONCERN] `answer()` keeps its refused record, which D6 forbids for a `started` attempt

`answer()` catches `SquadronError` from `resume()` and writes `refused` (answer.py:112-115; `_record_refused` at 121-133). Design D6 (slice lines 317-318, 335) makes `resume()` raise without recording when the attempt file holds `started` and the first poll is unreadable, and says a `refused` there would lose `started`. Design line 313 keeps a refused resume out of `claim_work`, so nothing retries it automatically. Tasks 3.4 and 3.5 (lines 141, 144-147) do not change this branch, so the in-process `answer` would record `refused` over an attempt that may have resumed the run. Fix: remove the branch in 3.5, delete `_record_refused`, and add a `started`-in-file case to 3.6.

### [CONCERN] A served operation's `work` flag never reaches the after-step on a joined machine

Task 7.4 (line 282) requires that a joined `list` whose reply has `work: true` makes one `claim_work`. The flag sits in the reply's result document (design D10, slice line 432). `route()` gets that document from `call()`, which returns a dict (client/call.py:159), and returns `result_from_document(...)` (wiring_door.py:117-124). That returns the typed result without the flag (operations/served.py:206-223). Task 6.5 (lines 243-245) has `after_call` read "the last reply the command got", and 7.3 (line 273) keeps that only for `DoorSteps`. The served path has no channel. Fix: name how `route` passes `work` and `work_problem` to `after_call`, and whether they are removed before `result_from_document`.

### [CONCERN] The stale-claim age uses `claimed_at` in the sweep and `updated_at` in `classify_pause`, against the design

Design D5 (slice line 286) defines a stale claim by `updated_at`. `pause_class.classify_pause` uses `updated_at` (pause_class.py:138). The sweep's claimed-row check (question_sweep.py:190) uses `claimed_at`. Task 2.1 (line 98) moves the sweep to `pause_claim_seconds` without naming the stamp, and 2.2 (line 103) requires one boundary across `classify_pause`, `classify_runs` and the sweep. If the two columns can differ, the at-limit test can pass in one place and fail in another. Fix: name one stamp in 2.1 and make D5 match.

### [CONCERN] 6.6 leaves a test that imports the deleted helper

Line 17 imports `release_child_wait`, which 6.6 (line 248) deletes. The file is not in 6.6's list of tests to move or delete.

### [CONCERN] The `inbox` assertion in `test_message_timing` reverses by design and is not on the reversed-test list

Context line 49 lists the tests this slice reverses, and this one is not among them. `test_send_reply_and_cancel_are_followed_by_the_start_and_inbox_is_not` (test_message_timing.py:192-198) asserts that `inbox` is not followed by the start. Design D10 (slice line 452) puts the after-step after every CLI operation, and after every MCP operation but `answer`, so `inbox` now is followed. The task also does not name `OTHER_START_WORST_CASE_SECONDS` (test_message_timing.py:62-69), which keeps the old bound for `rm`, `add`, `status` and `list`. Fix: add both to Context line 49 and to 6.5.

### [CONCERN] Stale references to deleted code survive 6.6, and 10.2's search does not cover docs

`docs/store-contract.md` names `start_ended_held` at lines 205, 495 and 509, and `MAX_STARTS_PER_CALL` at line 495. `tests/test_import_boundaries.py:60` names `amoeba.wiring_release` in the hub's forbidden list, and 6.6 does not mention that list. Task 9.2 (line 326) does not cover these paragraphs. Task 10.2 (line 340) searches only `src` and `tests`, so stale doc text passes the final check. Fix: add these paragraphs to 9.2, replace the import-boundary string in 6.6, and add `docs` to 10.2's search.

### [CONCERN] 6.5 and 6.6 each bundle several units

6.5 (lines 242-245) changes the after-step module and its bound, the timing test, both `wiring.invoke` paths, `run_handle_pause` and `steps_for`. 6.6 (lines 246-249) deletes two modules, edits three source files and moves or deletes nine tests. Split 6.5 into the bound and after-step, then the call sites. Split 6.6 into the deletions, then the test moves.

### [NOTE] `mark_start_attempted` gains a required parameter, and other callers are not named

Task 6.2 (line 227) names only `test_mark_start_attempted_refuses_a_row_no_longer_held`. The tests at lines 164, 177-178 and 188 of this file, and `tests/operations/test_status_calls.py:202`, call the four-argument form. The general rule covers them, but each needs an `expected_state` chosen. Name them.

### [NOTE] A `handle-pause` child's log directory is not named

6.4 names log paths for resumes only. Today the child's logs go under `logs/request-release/` (request_release.py:43). Name the directory the child uses.

### [NOTE] The pause path's machine filter is not named

`sweep_run` reads `open_rows_of_run(transaction, run_id)` with no machine filter. Task 4.4 (line 167) says to close only the calling machine's rows, and 1.2 adds the machine read, but no task says to switch this call to it.

### [NOTE] The after-step's bound has no value in the task, and its test name is stale

6.5 (line 244) introduces `AFTER_STEP_BOUND_SECONDS` as one busy timeout per transaction (up to three). The test at line 188 still pins the old `1 + MAX_STARTS_PER_CALL` formula under its old name. Give the value and rename the test.

### [NOTE] Sections 3, 4 and 5 are labelled `refactor:` but change behavior

The commit markers at lines 154, 191 and 219 are `refactor:`. The sections add refused records, new skips, the sweep change and the `cf`-before-skip order. AGENTS.md defines `refactor` as no behavior change. Relabel them `feat:` or split out the behavior.

### [NOTE] Existing source files are at or past the size guide, and 10.2 checks only new files

`wiring.py` (297), `hub/calls.py` (326), `operations/status.py` (305), `operations/pause_claim.py` (308) and `cli/render/waiting.py` (307) are already at or past about 300 lines. Tasks 3.5, 6.5, 7.2 and 7.3 add code to several of them. Task 10.2 (line 340) measures only new files. Add a check for files the slice grows.

### [NOTE] The load test's "times each step once" does not say what state each step needs

Sixteen steps need different rows (a claim, a request, a wake). An idle hub cannot time each one from empty. Name the seeded state, or the subset of steps.

### [NOTE] Tool versions and the read date were not checked

This review had no shell, so `sq --version` and `cf --version` (frontmatter lines 13-14: 0.24.38 and 0.19.28) are not checked. Lines 13-14 say the versions were read "again at the second revision the same day", but `dateUpdated` is 20261124 (line 16).

### [NOTE] 7.4 leaves the CLI contract's location open

"`docs/cli-contract.md` (or where it lives)" does not name the file. Name it.

### [PASS] Precondition names and migration 012 are present

The schema directory holds 001 to 012. The Context precondition names I checked exist, for example `find_caller` and `find_member` (operations/caller.py), `DoorHooks` (hub/calls.py:72), `DOOR_VERSION` at 1 (wire/times.py:13) and `START_BOUND_SECONDS` (operations/request_release.py:41).

### [PASS] The load test is gated by the existing Tests step

`.github/workflows/ci.yml:40` runs a bare `uv run pytest`, and `addopts` ignores only `tests/live`. `test_ci_gates_load.py` checks both, so 8.4's test under `tests/load` is gated without a new CI task.

### [PASS] Success criteria trace to tasks

I mapped the functional, technical and integration criteria to task items, and each one has at least one. Items for the design's D2, D5, D9 to D11 and D13 also appear. I found no scope creep.

## Resolution

Checked against the source 20261124; fixes are in the task file.

- F001 fixed: 2.5 adds a seed helper that sets the wake mark, the six direct-claim tests call it, the local `send` sets the mark before its claim, and 2.6 no longer says the wake tests are unchanged.
- F002 fixed: 1.2 names `sql.INSERT_QUESTION` and `seed.insert_question` binding the machine.
- F003 fixed: 1.1 adds `machine_removed` to `docs/cli-contract.md`.
- F004 fixed: 1.1 gives `ENDED_TEXT` a `machine_removed` text.
- F005 fixed: 2.3 names `claim_id: str | None`, with no default, and what each caller passes.
- F006 dropped: `answer` always resumes a fresh answer seq, so no earlier attempt file can hold `started`; the raise D6 describes cannot reach `answer`.
- F007 fixed: 6.5 has `route` lift `work` and `work_problem` before `result_from_document` into the holder `DoorSteps` uses.
- F008 fixed: 2.1 measures the stale age from `updated_at` everywhere, as D5 says.
- F009 fixed: 6.6 lists `tests/cli/test_hold_release_cli.py`.
- F010 fixed: Context and 6.5 name the reversed `inbox` assertion and `OTHER_START_WORST_CASE_SECONDS`.
- F011 fixed: 6.6 rewrites the three store-contract passages and the import-boundary strings; 10.2 searches `docs`.
- F012 dropped: size only; each task still has one commit and one test group.
- F013 dropped: Context's existing-tests rule covers the other callers, and 6.2 says which state each kind passes.
- F014 dropped: the log walk prunes everything under `logs/` by age, so the directory name is the implementer's.
- F015 fixed: 4.4 replaces `open_rows_of_run` with the by-machine read on this path.
- F016 dropped: 6.5 already defines the bound and the test it pins.
- F017 fixed: sections 3, 4 and 5 commit as `feat:`.
- F018 dropped: Context already sends the new logic to new modules; existing files get call sites only.
- F019 dropped: 8.4 already seeds the questions and requests the steps read.
- F020 dropped: 0.1 runs both version commands at the start.
- F021 fixed: 7.4 names `docs/cli-contract.md`.

Later the same day the resumed revise round (commit 3db8470f) also worked the dropped F006, F012, F013, F014, F016, F018, F019 and F020 into the task file: `answer` loses its `refused` fallback, 6.5 and 6.6 split into 6.5 to 6.8, the other `mark_start_attempted` callers, the child's log directory, the bound's value, the grown files in 10.2, the steps the load test times, and the version note.

A re-sent revise round on 20261123 local time rechecked all twenty-one findings against the task file and the source: each was already in place, apart from F011's `docs/cli-contract.md` paragraph that still names `logs/request-release/`. 6.7 now rewrites it, and 10.2's search matches `request-release` too. sq 0.24.38 and cf 0.19.28 were read again.

### Run Digest

- Response length: 34893 chars
- Response is newline-free: no
- Tool calls made: 108
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 109
- Tokens — prompt / cached / cache write / completion / reasoning: 14644842 / 14271592 / 373130 / 195426 / not computed
- Duration: 851.2 s
- Cost: $1.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 24
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 24
- Finding-shaped matches — surviving validation: 24
