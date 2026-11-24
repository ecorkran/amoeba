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
reviewedSha: f54bc4b62b1bd986cd26eb83e2980971029f67b4
reviewedBlob: d654779de4da5c738b331762b307528529d08da2
reviewedBlobCurrent: false
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 80
injected:
  - key: input
    path: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md"
    chars: 48319
    sha256: 2c2bec6e3375bffecb9d1158267d534f3b370d26a19d1d2b5fce9f4f0b15d69a
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
  - "src/amoeba/store/wakes.py"
  - "src/amoeba/store/answers.py"
  - "src/amoeba/store/held_questions.py"
  - "tests/store/test_question_closing.py"
  - "tests/operations/test_question_sweep.py"
  - "tests/store/test_held_questions.py"
  - "src/amoeba/operations/resume.py"
  - "src/amoeba/wire/times.py"
  - "src/amoeba/operations/request_release.py"
  - "src/amoeba/wiring.py"
  - "src/amoeba/store/sql.py"
  - "src/amoeba/hub/calls.py"
  - "tests/load/test_door_load.py"
  - "tests/hub_fixture.py"
  - "tests/test_ci_gates_load.py"
  - "tests/store/test_schema_holds_no_mirrored_state.py"
  - "tests/hub/test_handle_call.py"
  - "tests/hub/test_app.py"
  - "src/amoeba/wire/protocol.py"
  - "src/amoeba/cli/main.py"
  - "src/amoeba/cli/commands.py"
  - "src/amoeba/cli/wake_command.py"
  - "src/amoeba/operations/send.py"
  - "src/amoeba/operations/wake_door.py"
  - "src/amoeba/operations/wake.py"
  - "src/amoeba/operations/pause_existing.py"
  - "src/amoeba/hub/admin.py"
  - "tests/test_import_boundaries.py"
  - "tests/operations/test_every_state_exits.py"
searches:
  - "list_files src/amoeba/store/schema/01*.sql in ."
  - "list_files src/amoeba/operations/{request_release,wiring_release,wake_door,work_start,resume_run,resume_attempt,store_steps,handle_pause,pause_eligibility,pause_class,pause_claim,pause_held,pause_existing,pause_results,pause_context,claim_waiting,answering_settle,resume,wake_run,prune,status_runs,question_swee\u2026 in ."
  - "list_files src/amoeba/{wiring_release,wiring_steps,wiring_door,wiring_messages,wiring,wake_command,cli/*}.py in ."
  - "list_files tests/**/{in_process_hub,hub_fixture,fault_injection,sq_stub,sq_stub_resume,cf_stub,store_open,release_child_wait,schema_11,schema_12,seed,test_start_ended_held_load,test_door_load,test_ci_gates_load,test_update_live,test_vocabulary_pinning,test_import_boundaries,test_wiring_release,test_question_sw\u2026 in ."
  - "list_files src/amoeba/{hub/*,store/{questions,held_questions,wakes,answers,sql,sql_held,sql_wakes,sql_messages,vocabulary,models,store,question_closing,messages}*,wire/*,client/*,answering/values.py}.py in ."
  - "list_files {scripts/update_live.py,docs/*.md,tests/live/**/*,tests/hub/*.py,tests/load/*.py,.claude/skills/release/SKILL.md} in ."
  - "list_files src/amoeba/operations/steps/** in ."
  - "list_files src/amoeba/hub/*.py in ."
  - "list_files src/amoeba/store/*.py in ."
  - "list_files src/amoeba/{wire,client,answering}/*.py in ."
  - "list_files scripts/update_live.py in ."
  - "list_files tests/hub/*.py in ."
  - "grep MAX_STARTS_PER_CALL|request_release|wiring_release|start_after|wake_door|can_wake|mark_resume_started|mark_start_attempted|claim_wake\\b in /Users/manta/source/repos/manta/amoeba"
  - "grep owner_id|owner in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/schema"
  - "grep def acting|owner_id|class Acting|def act_as|def call_scope in /Users/manta/source/repos/manta/amoeba/src/amoeba/store"
  - "grep BOUND|resume_bound|answering_wait|CALL_BOUND|^NOW|^OLD|^LATER|def _sweep|def _answered in /Users/manta/source/repos/manta/amoeba/tests/operations/test_question_sweep.py"
  - "grep def resume_bound_seconds|CALL_BOUND_SECONDS[:= ]|DOOR_VERSION[:=]|BUSY_TIMEOUT_SECONDS[:=]|answering_wait_seconds[:=]|resume_bound_seconds[:=]|def classify_pause|def classify_runs|def _judge|def mark_start_attempted|MAX_AUTOMATIC in /Users/manta/source/repos/manta/amoeba/src"
  - "grep RUN_POLL_TIMEOUT_SECONDS[:=]|TERMINATE_GRACE_SECONDS[:=]|MAX_WORK|wake_timeout|max_wakes_per_day[:=]|session_stale in /Users/manta/source/repos/manta/amoeba/src"
  - "grep OPERATIONAL_ERRORS|OPERATION_ERRORS\\b.*=|class NotServedError|def refuse_if_joined|def route\\b|def invoke|def _dispatch|def check_deadline|class ClientFileError|class HubUnreachableError|class HubRefusedError|class LocalStoreClosedError|class HubHomeError|def run_handle_pause|def run_wake_run|refuse\u2026 in /Users/manta/source/repos/manta/amoeba/src"
  - "grep class DoorHooks|after_commit|def two_machine_hub|def env_for|PATH|HOME|def clock|set_clock|class InProcessHub|def load_test|LOAD_|0\\.2|200|median|500|def _seed|seed_|claim_work|in-process|two_machine in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep insert\\s+into\\s+\"?(questions|wakes|held)|INSERT\\s+INTO\\s+\\\"?(questions|wakes) in /Users/manta/source/repos/manta/amoeba"
  - "grep COLUMN_REASONS|\"record\"|\"waking\"|\"messages\"|mirrored in /Users/manta/source/repos/manta/amoeba/tests/store/test_schema_holds_no_mirrored_state.py"
  - "grep def test_a_send_to_a_member_a_wake_is_due_for_is_not_served|def test_a_hub_part_refusal_keeps_no_result_for_a_repeat|def test_an_unserved_name_is_not_served|not_served|DOOR_VERSION|\\(1,|\"answer\"|'answer'|OperationName.ANSWER|handle-pause|wake-run|HANDLE|WAKE_RUN in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep release|start_ended|START_FAILED|held_start|prune\\(|prune\\b in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep \\bprune\\b|deps\\.prune|\\.prune\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep def open_state_store|def open_hub_store|def act_as_local|def acting_machine_id|def act_as\\b|def call_scope|def acting\\b|def the_owner|def open_store|LOCAL_MACHINE_NAME[:=]|EXPECTED_SCHEMA_VERSION[:=] in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep answering_wait_seconds|classify_run_only|claim_age_limit|claim_stale|updated_at.*claim|stale in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep def rm_machine|def restore|def update|def read_back|list|def _verify|def main|argparse|add_parser|\\\"restore\\\"|'restore'|def _check|amoeba.*list in /Users/manta/source/repos/manta/amoeba/scripts/update_live.py"
  - "grep def rm_machine|DELETE FROM machines|machines WHERE|machine_id|owner|def _ in /Users/manta/source/repos/manta/amoeba/src/amoeba/hub/admin.py"
  - "grep _needs_config|def _serve|def _done|def _keep|def _lookup|kept|def handle_call|def for_exception|load_config\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba/hub"
  - "grep ^from amoeba|^import amoeba|^from \\.|^    from amoeba in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep ^import subprocess|^from subprocess|Popen|def param_problem|def spawn|subprocess\\.|^from amoeba|^import in /Users/manta/source/repos/manta/amoeba/src/amoeba/upstream/squadron/launch.py"
  - "grep open\\(|read_text|Path\\(.*\\)\\.read|read_bytes|from amoeba|import amoeba in /Users/manta/source/repos/manta/amoeba/src/amoeba/answering/artifacts.py"
  - "grep start_after|START_AFTER|wiring_release|^def test_|^from amoeba|^import in /Users/manta/source/repos/manta/amoeba/tests/test_wiring_release.py"
  - "grep \"store\": \\( in /Users/manta/source/repos/manta/amoeba/tests/test_import_boundaries.py"
  - "grep clock|now|class |def  in /Users/manta/source/repos/manta/amoeba/tests/hub/in_process_hub.py"
  - "list_files docs/{store-contract,cli-contract,config-contract,squadron-hook,mcp-server}.md in ."
  - "grep answering_run|def test_.*answering|cf|exit in /Users/manta/source/repos/manta/amoeba/tests/operations/test_pause_eligibility.py"
  - "grep def seed|act_as|def acting|raise .*acting|no acting machine|NoActing|acting machine in /Users/manta/source/repos/manta/amoeba"
  - "grep class ServedEdges|def run_served|class CallRefused|def find_caller|def find_member|class DoorHooks|def remove_machine|def classify_run_only|def runs_document|def build_runs|class RunsDocument|def run_gather|def here\\b|def place_served|def route\\b|OPERATIONAL_ERRORS: Final in /Users/manta/source/repos/manta/amoeba/src"
  - "grep ServedEdges in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/served.py"
  - "grep classify_pause\\(|classify_runs\\(|resume_bound_seconds|answering_wait_seconds|claim_age_limit|BOUND\\s*= in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep NOT_DELIVERED|not_delivered|resume_bound|answering_wait|BOUND in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep unreadable|PollFailure|SquadronError|pytest.raises|nothing is|no write|writes nothing|records nothing in /Users/manta/source/repos/manta/amoeba/tests/operations/test_resume.py"
  - "grep def test_|STRUCT|ENUM|Enum|import|SkipReason|OperationName|wire|protocol|\\.md in /Users/manta/source/repos/manta/amoeba/tests/test_contract_docs.py"
  - "grep def worst_case_seconds|WAKE|START|BUSY|CALL_BOUND|send|SEND|return in /Users/manta/source/repos/manta/amoeba/src/amoeba/wiring_messages.py"
  - "grep ^version\\s*=|^name\\s*= in /Users/manta/source/repos/manta/amoeba/pyproject.toml"
sectionsInDocument: 12
sectionsCovered: 12
effort: xhigh
turns: 81
promptTokens: 9756530
cachedTokens: 9469253
cacheWriteTokens: 287179
completionTokens: 147763
durationSeconds: 651.8
costUsd: 1.028539
costBasis: provider
runId: run-20261124-p5-86ef1af7
squadronVersion: 0.24.38
findings:
  - id: F001
    severity: fail
    category: layering
    summary: "wake_due is placed where store/wakes.py must call it, breaking the store layering rule"
    location: "src/amoeba/store/wakes.py:170"
  - id: F002
    severity: fail
    category: coverage
    summary: "Tests that D9 reverses are not among the named edits"
    location: "tests/operations/test_every_state_exits.py:251"
  - id: F003
    severity: concern
    category: existing-code
    summary: "The 2.5 wake_due signature drops the WakeScope that can_wake takes"
    location: "src/amoeba/store/wakes.py:159"
  - id: F004
    severity: concern
    category: coverage
    summary: "Task 2.2 says \"name each\" but names no test that pins the stale age or resume bound"
    location: "tests/operations/test_every_state_exits.py:229"
  - id: F005
    severity: concern
    category: existing-code
    summary: "Task 3.4 says existing resume tests pass, but one pins the first-poll behaviour that D6 reverses"
    location: "tests/operations/test_resume.py:261"
  - id: F006
    severity: concern
    category: existing-code
    summary: "Task 6.2 makes mark_start_attempted accept claimed rows, against an existing refusal test"
    location: "tests/store/test_held_questions.py:183"
  - id: F007
    severity: concern
    category: existing-code
    summary: "Task 7.1 misses the test that asserts answer is NOT_SERVED"
    location: "tests/hub/test_handle_call.py:365"
  - id: F008
    severity: concern
    category: existing-code
    summary: "Task 2.3 does not list the callers of mark_resume_started that it removes"
    location: "src/amoeba/store/questions.py:27"
  - id: F009
    severity: concern
    category: coverage
    summary: "Import-boundary rules are assigned to no task for resume, prune, resume_run and work_start"
    location: "tests/test_import_boundaries.py:30"
  - id: F010
    severity: concern
    category: sequencing
    summary: "run_handle_pause still loads config and opens the store, which 7.4's no-config test rules out"
    location: "src/amoeba/cli/commands.py:214"
  - id: F011
    severity: concern
    category: consistency
    summary: "6.6 keeps test_wiring_release.py, which imports the deleted module; the 10.2 grep will match it"
    location: "tests/test_wiring_release.py:41"
  - id: F012
    severity: concern
    category: proportionality
    summary: "Task 4.4 bundles pause_begin, the close-sweep change and a test edit"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:165"
  - id: F013
    severity: note
    category: proportionality
    summary: "Context Summary says sql.py gets only edited inserts, but 2.3 must change existing statements"
    location: "src/amoeba/store/sql.py"
  - id: F014
    severity: note
    category: consistency
    summary: "Context Summary places ServedEdges in served.py; it is defined in served_types.py"
    location: "src/amoeba/operations/served_types.py:66"
  - id: F015
    severity: note
    category: consistency
    summary: "Task 9.1 names the wrapper, not the function that holds the transaction"
    location: "src/amoeba/hub/admin.py:90"
  - id: F016
    severity: note
    category: coverage
    summary: "The 10.2 grep omits start_ended_held, so stale docstring references survive"
    location: "src/amoeba/operations/status_runs.py:252"
  - id: F017
    severity: note
    category: coverage
    summary: "The local-store walkthrough in the design has no step in 10.1"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:331"
  - id: F018
    severity: note
    category: coverage
    summary: "Task 8.4 does not say how the 500 requests and the second machine are seeded"
    location: "tests/load/test_door_load.py:130"
  - id: F019
    severity: note
    category: coverage
    summary: "A pinned worst-case figure for send is not covered by any task"
    location: "src/amoeba/wiring_messages.py:42"
  - id: F020
    severity: note
    category: consistency
    summary: "Frontmatter tool versions are not verified in this review"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:13"
---

# Review: tasks — slice 262

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] wake_due is placed where store/wakes.py must call it, breaking the store layering rule

Task 2.5 (lines 111-114) puts `wake_due` in `steps/wake.py` and has `claim_wake` call it. `claim_wake` is defined in `amoeba.store.wakes`. `tests/test_import_boundaries.py:37` forbids the `store` package from importing `amoeba.operations`, so the import 2.5 requires fails that test as soon as it is written. The design's D8 makes the same placement, so the conflict comes from the design. Fix: define `wake_due` in `store/wakes.py`, which needs only store reads (`first_wakeable_checkout`, `live_member_ids`, the live-wake and window counts), and have `operations/steps/wake.py` re-export it or call it. Name the placement change in 2.5.

### [FAIL] Tests that D9 reverses are not among the named edits

Task 4.4 (lines 168-169) names only the split in `test_question_sweep.py`. Two other tests assert what D9 removes:
- `test_every_state_exits.py:251-263` expects the sweep to mark an answered, unresumed answer `NOT_DELIVERED` once its bound passes. D9 says the sweep leaves it.
- `tests/operations/test_status_sweep.py:170-190` expects `status` to mark an old unresumed answer `NOT_DELIVERED`. Task 5.4 (lines 206-210) does not name it.

Line 48 allows only the five named kinds of edit and says a failing test is fixed in the code. An implementer following it cannot implement D9. Name both tests as design-allowed edits in 4.4 and 5.4.

### [CONCERN] The 2.5 wake_due signature drops the WakeScope that can_wake takes

`can_wake(transaction, member_id, now, limits, scope=WakeScope.ACTING_MACHINE)` takes a scope. Task 2.5 (line 113) gives `wake_due(transaction, member, now, limits)` with none. Task 5.1 needs the all-machines check for `wake_waiting_on` (line 193), and `operations/wake_door.py:34-35` passes `WakeScope.ALL_MACHINES`. `tests/store/test_wake_on_checkout.py:123-126` passes the scope as a fifth argument. So the claim in 2.6 (line 118), "existing 244 wake tests pass unchanged apart from the renamed function", is false. Add `scope` to the signature and say so.

### [CONCERN] Task 2.2 says "name each" but names no test that pins the stale age or resume bound

Task 2.2 (line 101) defers the list of tests with "(name each)". Twelve test files reference `answering_wait_seconds`, `resume_bound_seconds`, `classify_pause`, `classify_runs` or `claim_age_limit`. `test_every_state_exits.py:229-239` expects a claim to go stale at `answering_wait_seconds`, which 2.1 moves to `pause_claim_seconds`, so it fails. `test_question_sweep.py:56` still uses `resume_bound_seconds` for BOUND, which passes only by accident. Line 48 requires the names to be in the task, not left to the implementer.

### [CONCERN] Task 3.4 says existing resume tests pass, but one pins the first-poll behaviour that D6 reverses

`test_an_unreadable_first_poll_raises_and_writes_nothing` asserts a `SquadronError` and that nothing is stored. Tasks 3.3 (line 136) and 3.4 (lines 140-141) make an unreadable first poll with no attempt file record `refused` and free the claim. Task 3.4 bullet 1 (line 138) still says existing resume tests pass with `LocalSteps`. Name this test as a changed assertion.

### [CONCERN] Task 6.2 makes mark_start_attempted accept claimed rows, against an existing refusal test

`mark_start_attempted` (`src/amoeba/store/held_questions.py:124-143`) matches only `WAITING_ON_REQUEST`, through `sql_held.MARK_START_ATTEMPTED`. Task 6.2 (line 224) says it applies to `claimed` rows too. `test_mark_start_attempted_refuses_a_row_no_longer_held` (lines 183-188) makes a claimed row and asserts refusal. The test is not in 6.3 or the migration list. The SQL change in `sql_held.py` is also unmentioned.

### [CONCERN] Task 7.1 misses the test that asserts answer is NOT_SERVED

Task 7.1 (lines 258-259) names `test_an_unserved_name_is_not_served` and the `test_app.py` case. `test_hello_with_an_empty_document_keeps_no_result_and_answer_is_not_served` (lines 365-373) asserts `answer` gets `NOT_SERVED`. It fails once `answer` joins `SERVED_OPERATIONS` (line 257). Name it. The `answer` call at line 336 only produces a log side effect, but check it still yields a refusal.

### [CONCERN] Task 2.3 does not list the callers of mark_resume_started that it removes

Task 2.3 (line 106) says `mark_resume_started` is "replaced by claim_resume at every caller". Callers outside `answers.py` and `resume.py` are:
- the re-export in `store/questions.py` (line 27, and line 65 in `__all__`);
- `tests/operations/test_dismiss.py:32,128`;
- `tests/operations/test_question_sweep.py:35,186`;
- `tests/store/test_question_closing.py:16,326-339`.

`record_resume` also gains a claim-id parameter (line 105) that every existing test call must pass. None of this is named.

### [CONCERN] Import-boundary rules are assigned to no task for resume, prune, resume_run and work_start

Task 3.1 (line 129) lists these as client-run modules and says rules are added in the task that moves each one. Tasks 4.5, 4.6 and 5.3 add theirs. Task 3.3 (resume), 5.5 (prune) and 6.4 (`work_start`, `resume_run`) add none. `FORBIDDEN` (lines 30-45) is keyed by package, so per-module rules need a mechanism the task does not describe.

### [CONCERN] run_handle_pause still loads config and opens the store, which 7.4's no-config test rules out

`run_handle_pause` calls `load_config()` (line 215) and `open_store(layout)` (line 218) before `handle_pause`. Tasks 4.5 (lines 173-174) and 7.4 (lines 273-277) say only "builds LocalSteps" and "uses steps_for". The 7.4 test requires a joined machine with no local `config.yaml` to pass, so the `load_config()` call must be removed. The same applies to `run_wake_run`'s `open_store` (`src/amoeba/cli/wake_command.py:67`, task 5.3). Name both removals.

### [CONCERN] 6.6 keeps test_wiring_release.py, which imports the deleted module; the 10.2 grep will match it

Task 6.6 (lines 243-244) keeps the MCP `reply`/`cancel` test in this file. The file imports `START_AFTER_OPERATIONS` from `amoeba.wiring_release` (line 41) and names `start_after` in its docstring (line 5). Deleting `wiring_release.py` breaks it at import. Task 10.2 (line 335) requires `rg ... wiring_release|start_after ... tests` to find nothing. Say in 6.6 that the import and docstring change.

### [CONCERN] Task 4.4 bundles pause_begin, the close-sweep change and a test edit

Task 4.4 (lines 165-170) combines a seven-step transaction, its reply shape, the D9 change to the shared `question_sweep` (which `status` also uses, per 5.4), a design-allowed test split and three test bullets. Split it into `pause_begin` (the transaction and reply, with its tests) and the D9 sweep change (with its tests). Each part can then be checked on its own.

### [NOTE] Context Summary says sql.py gets only edited inserts, but 2.3 must change existing statements

Context Summary line 42 says `store/sql.py` "gets only the edited inserts". Task 2.3 must change the existing `RECORD_RESUME` and `MARK_RESUME_STARTED` statements (`answers.py` calls `sql.RECORD_RESUME` and `sql.MARK_RESUME_STARTED`). Either allow that edit or move the new statements to `sql_local_work.py`.

### [NOTE] Context Summary places ServedEdges in served.py; it is defined in served_types.py

Context Summary line 39 lists `operations/served.py (run_served, ServedEdges)`. `ServedEdges` is defined in `served_types.py:66` and imported into `served.py:79`. Correct the pointer.

### [NOTE] Task 9.1 names the wrapper, not the function that holds the transaction

Task 9.1 (line 318) says "`hub/admin.rm_machine`, in its one transaction". `rm_machine` (`hub/admin.py:90-98`) only opens the transaction and calls `remove_machine` (`src/amoeba/store/machines.py:198`), which is where the closing logic must go. Name it there. It must stay in the store, for the layering reason above.

### [NOTE] The 10.2 grep omits start_ended_held, so stale docstring references survive

Task 6.6 says to remove references, and the module-level docstring mentions survive at `status_runs.py:252` and `store/models.py:140`. Task 10.2 (line 335) searches only `request_release|wiring_release|start_after|wake_door|MAX_STARTS_PER_CALL`. Add `start_ended_held` to that search.

### [NOTE] The local-store walkthrough in the design has no step in 10.1

The design's criterion (design line 793) says the 242 and 244 walkthroughs "behave as before" on the local store. Task 10.1 (lines 331-333) runs the two pytest commands and the by-hand pass, but no step runs those walkthroughs on the local store. Add one line.

### [NOTE] Task 8.4 does not say how the 500 requests and the second machine are seeded

The existing `_seed_answers` seeds 500 answers through `hub.seed(...)`, which acts as `alpha` by default (`tests/hub_fixture.py:331`). Task 8.4 (line 307) asks for 500 questions and 500 requests across both machines. The task does not say how requests are seeded or that `beta`'s share needs `acting_as=SECOND`.

### [NOTE] A pinned worst-case figure for send is not covered by any task

`tests/test_contract_docs.py:408-411` pins `worst_case_seconds(SEND)` in `mcp-server.md`, computed from `MESSAGE_LOOKUPS` and `MESSAGE_STORE_WAITS`. D8 and D10 add a mark write, a wake claim and an after-step to `send`. Nothing says whether the figure still holds. Add a check to 9.2 or 10.2.

### [NOTE] Frontmatter tool versions are not verified in this review

Frontmatter gives `sq 0.24.38` and `cf 0.19.28`, read on 20261123. This review had no shell, so I could not run `sq --version` or `cf --version`. Task 0.1 re-reads them, so this is informational.

### Run Digest

- Response length: 29161 chars
- Response is newline-free: no
- Tool calls made: 80
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 81
- Tokens — prompt / cached / cache write / completion / reasoning: 9756530 / 9469253 / 287179 / 147763 / not computed
- Duration: 651.8 s
- Cost: $1.03 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 20
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 20
- Finding-shaped matches — surviving validation: 20
