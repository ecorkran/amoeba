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
reviewedSha: d580473e73ebb147e1e300aeb526b89d5e7cb32f
reviewedBlob: aaae7697eea2b90f432f1c9e1aa9ca5b4cdd5b3e
reviewedBlobCurrent: false
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 76
injected:
  - key: input
    path: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md"
    chars: 43242
    sha256: 807b988a34ea6024cb98ab2707668f009adfa2f9758ff11302efa69fd745cc12
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
  - "src/amoeba/operations/resume.py"
  - "tests/store/test_migration_012.py"
  - "tests/store/test_schema_holds_no_mirrored_state.py"
  - "tests/wire/test_times.py"
  - "src/amoeba/wire/times.py"
  - "tests/hub/test_door_operations.py"
  - "tests/hub/test_joined_entry_points.py"
  - "tests/store/test_migrations.py"
  - "tests/hub_fixture.py"
  - "src/amoeba/operations/status.py"
  - "src/amoeba/operations/pause_class.py"
  - "src/amoeba/operations/request_release.py"
  - "src/amoeba/operations/handle_pause.py"
  - "src/amoeba/operations/question_sweep.py"
  - "src/amoeba/wiring_release.py"
  - "src/amoeba/wiring.py"
  - "src/amoeba/wiring_door.py"
  - "tests/load/test_start_ended_held_load.py"
  - "src/amoeba/store/held_questions.py"
  - "src/amoeba/answering/values.py"
  - "src/amoeba/operations/state_move.py"
  - "src/amoeba/wire/protocol.py"
  - "src/amoeba/hub/calls.py"
  - "src/amoeba/client/call.py"
  - "pyproject.toml"
  - "src/amoeba/store/schema/011_hub_and_door.sql"
searches:
  - "list_files src/amoeba/store/schema/*.sql in ."
  - "grep EXPECTED_SCHEMA_VERSION|DOOR_VERSION|CALL_BOUND_SECONDS\\s*= in /Users/manta/source/repos/manta/amoeba"
  - "grep def resume_bound_seconds|def answering_wait_seconds|resume_bound|pause_claim|MAX_STARTS_PER_CALL|def classify_run_only|classify_run_only in /Users/manta/source/repos/manta/amoeba/src"
  - "grep MACHINE_REMOVED|class ClosedReason|class WakeOutcome|class DeclineReason|class SkipReason|class ClaimResult|STARTS_EXHAUSTED in /Users/manta/source/repos/manta/amoeba/src"
  - "grep EXPECTED_SCHEMA_VERSION|DOOR_VERSION|CALL_BOUND_SECONDS\\s*[:=]|STORE_WAIT|BUSY_TIMEOUT_SECONDS\\s*[:=] in /Users/manta/source/repos/manta/amoeba/src"
  - "grep EXPECTED_SCHEMA_VERSION|DOOR_VERSION|schema_version|== 12|, 12\\)|\\b12\\b.*version in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep CREATE (TABLE|INDEX|TRIGGER|UNIQUE INDEX)|CHECK|REFERENCES|ALTER TABLE|PRAGMA|DROP|RENAME in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/schema"
  - "grep ^- \\*\\*[a-z ]+\\*\\*: in /Users/manta/source/repos/manta/amoeba/docs/store-contract.md"
  - "grep INSERT INTO (questions|wakes|answers|messages)\\b in /Users/manta/source/repos/manta/amoeba"
  - "grep def (insert_question|insert_held|claim_wake|can_wake|mark_resume_started|record_resume|settle_answered|settle_waiting|settle_held_waiting|replace_claim|claim_held|mark_start_attempted|close_question|finish_wake|wake_summary|effective_state)\\b in /Users/manta/source/repos/manta/amoeba/src"
  - "grep def (act_as_local|act_as|call_scope|open_state_store|open_hub_store|rm_machine|refuse_if_joined|start_after|start_claimed|invoke|check_deadline|_dispatch|steps_for)\\b|OPERATIONAL_ERRORS|OPERATION_ERRORS|NotServedError in /Users/manta/source/repos/manta/amoeba/src"
  - "grep resume_wait_seconds|answering_wait_seconds|RUN_POLL_TIMEOUT_SECONDS\\s*[:=]|TERMINATE_GRACE_SECONDS\\s*[:=]|prune_after_days|wake_timeout_seconds|max_wakes_per_day in /Users/manta/source/repos/manta/amoeba/src"
  - "grep can_wake\\(|mark_resume_started\\(|claim_wake\\(|mark_start_attempted\\(|record_resume\\(|request_release|start_ended_held|_due_rows|sweep_candidates|wake_door|not_served in /Users/manta/source/repos/manta/amoeba"
  - "list_files tests/{live/hold,live/waking,hub/in_process_hub.py,hub_fixture.py,load/test_door_load.py,scripts/test_update_live.py,test_contract_docs.py,test_import_boundaries.py,test_wiring_release.py,operations/test_pause_eligibility.py,operations/test_pause_claim_held.py,operations/test_question_sweep.py,store\u2026 in /Users/manta/source/repos/manta/amoeba"
  - "list_files src/amoeba/{operations/steps,operations/store_steps.py,operations/work_start.py,operations/resume_run.py,wiring_steps.py,cli/resume_command.py,operations/resume_attempt.py,hub/call_work.py,operations/wake_door.py,operations/request_release.py,wiring_release.py,mcp/detached.py,operations/state_move.p\u2026 in /Users/manta/source/repos/manta/amoeba"
  - "grep two_machine_hub|class DoorHooks|sq_stub|PATH|SQ_STUB|runs_dir|squadron|def clock|settable|set_clock|now\\s*=|200|2\\.0|16|median|CLIENTS|BOUND in /Users/manta/source/repos/manta/amoeba/tests"
  - "list_files tests/live/* in /Users/manta/source/repos/manta/amoeba"
  - "grep def (update|restore|_read_back|read_back|_check|main|_backup|_restore|_list)\\b|add_argument|subcommand|\"list\"|amoeba list|STORE_BACKUP|CONFIG_BACKUP|def _verify|read-back|readback in /Users/manta/source/repos/manta/amoeba/scripts/update_live.py"
  - "grep class |clock|DoorHooks|def |hooks in /Users/manta/source/repos/manta/amoeba/tests/hub/in_process_hub.py"
  - "grep class DoorHooks|DoorHooks|def handle_call|def _store_call|after_commit|drop|def _refuse|OPERATION_ERRORS|MAX_CALL_BYTES|not_served|NOT_SERVED|SERVED_OPERATIONS|WRITING_CALLS|HELLO_CALL in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep def classify_runs|answering_wait|claim_age|limit|updated_at|claimed_at in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/status_runs.py"
  - "grep def route|def run_served|return None|return result|def place_served|check_deadline\\(|def _refuse_in_a_hub_home|def open_store|def load_config in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep def test_|wiring_release|start_after|request_release|import in /Users/manta/source/repos/manta/amoeba/tests/test_wiring_release.py"
  - "grep def test_.*(answering|answer_run|own_pause|cf|skip)|def test_.*(unresumed|not_delivered|bound)|def test_.*(limit|held) in /Users/manta/source/repos/manta/amoeba/tests/operations"
  - "grep request_release|wiring_release|start_ended_held|MAX_STARTS_PER_CALL|START_FAILED_OUTCOME|REQUEST_RELEASE_LOG_DIRECTORY|start_after in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep request_release|wiring_release|REQUEST_RELEASE|def test_|FORBIDDEN|RULES|store\\.store|amoeba\\.store in /Users/manta/source/repos/manta/amoeba/tests/test_import_boundaries.py"
  - "grep request_release|wiring_release|start_ended_held in /Users/manta/source/repos/manta/amoeba/tests/test_message_timing.py"
  - "grep DeclineReason|ClosedReason|WakeOutcome|def test_|waiting_reason in /Users/manta/source/repos/manta/amoeba/tests/store/test_vocabulary_pinning.py"
  - "grep act_as_local\\(|act_as\\(|ActingMachine|machine_id in /Users/manta/source/repos/manta/amoeba/src/amoeba/store"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/hub/calls.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/wiring.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/handle_pause.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/cli/main.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/sql.py"
  - "list_files tests/live/hold/** in /Users/manta/source/repos/manta/amoeba"
  - "grep def squadron_runs_dir|SQUADRON_|\\.config/squadron|expanduser|Path\\.home in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep runs|HOME|environ|sq in /Users/manta/source/repos/manta/amoeba/tests/sq_stub.py"
  - "list_files tests/live/waking/*.py in /Users/manta/source/repos/manta/amoeba"
  - "grep UNKNOWN_ADVICE|def run_served|case OperationName|case \"|class ServedEdges|def _refuse in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep def _needs_config|_NEEDS_CONFIG|NEEDS_CONFIG|def _loaded|def find_kept|def keep in /Users/manta/source/repos/manta/amoeba/src/amoeba/hub"
  - "grep ^SERVED|SERVED: |needs_config|class ServedOperation|SERVED = |import.*SERVED in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep \"answer\"|'answer'|not_served|NOT_SERVED in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep answering_wait_seconds|resume_bound|dead|claim in /Users/manta/source/repos/manta/amoeba/docs/config-contract.md"
  - "grep def test_|requires|contract|columns|docs/ in /Users/manta/source/repos/manta/amoeba/tests/test_contract_docs.py"
  - "grep ^class (ClientFileError|HubUnreachableError|HubRefusedError|StepReplyError)|^def (find_caller|find_member|here|run_gather)\\b|^class ServedEdges|ServedEdges\\b.*import|import.*ServedEdges|^from amoeba.operations.served_types import|^def (run_served|gather_caller_always) in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep ^def (run_handle_pause|run_wake_run|prune|handle_pause|wake_run|resume_record|answer|send|status_runs_entry)\\(|^def (run_handle_pause|run_wake_run) in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep refuse_if_joined|NotServedError in /Users/manta/source/repos/manta/amoeba/src/amoeba/cli"
  - "list_files {.github/workflows/*.yml,.github/workflows/*.yaml,pyproject.toml,tests/load/conftest.py,tests/conftest.py} in /Users/manta/source/repos/manta/amoeba"
  - "grep load|markers|addopts|testpaths|norecursedirs|ignore in /Users/manta/source/repos/manta/amoeba/pyproject.toml"
  - "grep pytest|load|live|run:|ruff|pyright|uv  in /Users/manta/source/repos/manta/amoeba/.github/workflows/ci.yml"
sectionsInDocument: 12
sectionsCovered: 12
effort: xhigh
turns: 77
promptTokens: 6597957
cachedTokens: 6316301
cacheWriteTokens: 281590
completionTokens: 136873
durationSeconds: 597.8
costUsd: 0.834681
costBasis: provider
runId: run-20261124-p5-86ef1af7
squadronVersion: 0.24.38
findings:
  - id: F001
    severity: fail
    category: test-allowlist
    summary: "The test-edit allowlist forbids the changes 5.1, 7.1 and 7.4 require"
    location: "tests/hub/test_handle_call.py:173"
  - id: F002
    severity: fail
    category: sequencing
    summary: "The after-step never runs on a joined machine"
    location: "src/amoeba/wiring.py:168"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Writing steps are not wired into the keep, advice, or config paths"
    location: "src/amoeba/hub/calls.py:228"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "No test for the first-poll refusal"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:135"
  - id: F005
    severity: concern
    category: existing-code
    summary: "The migration-012 test pins schema 12 and is not in the plan"
    location: "tests/store/test_migration_012.py:44"
  - id: F006
    severity: concern
    category: existing-code
    summary: "Raw SQL inserts fail under the new machine trigger"
    location: "tests/store/test_migrations.py:363"
  - id: F007
    severity: concern
    category: contract-docs
    summary: "The reason labels for the new columns do not exist"
    location: "tests/store/test_schema_holds_no_mirrored_state.py:23"
  - id: F008
    severity: concern
    category: sequencing
    summary: "The claim-age list in 2.1 is incomplete"
    location: "src/amoeba/operations/question_sweep.py:190"
  - id: F009
    severity: concern
    category: existing-code
    summary: "Deleting two modules breaks test files the plan does not name"
    location: "tests/load/test_start_ended_held_load.py:33"
  - id: F010
    severity: concern
    category: task-clarity
    summary: "The fixture shares one HOME, and 7.5 does not name the mechanism"
    location: "tests/hub_fixture.py:198"
  - id: F011
    severity: concern
    category: scope
    summary: "`steps_for` takes inputs that nothing in this slice uses"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:232"
  - id: F012
    severity: concern
    category: granularity
    summary: "4.5 and 6.5 are each too large for one pass"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:167"
  - id: F013
    severity: concern
    category: ci-gating
    summary: "CI gating for the door load test is implicit"
    location: ".github/workflows/ci.yml:40"
  - id: F014
    severity: note
    category: test-coverage
    summary: "Two design rules in D3 have no test"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:256"
  - id: F015
    severity: note
    category: granularity
    summary: "1.1 is too small to be its own item, and 1.5 needs a consistency fix"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:67"
  - id: F016
    severity: note
    category: structure
    summary: "Two large source files will grow"
    location: "src/amoeba/store/sql.py"
  - id: F017
    severity: note
    category: sequencing
    summary: "5.1 uses a body key that 7.1 creates"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:187"
  - id: F018
    severity: note
    category: test-coverage
    summary: "Nothing tests that a removed machine's wakes name it"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:305"
  - id: F019
    severity: note
    category: process
    summary: "The slice branch's target has an uncommitted change"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:54"
  - id: F020
    severity: note
    category: facts
    summary: "The tool versions are unverified"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md:13"
  - id: F021
    severity: pass
    category: coverage
    summary: "Success criteria are covered by tasks"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md"
  - id: F022
    severity: pass
    category: sequencing
    summary: "Each implementation section is followed by its tests"
    location: "project-documents/user/tasks/262-tasks.local-work-through-the-hub.md"
---

# Review: tasks — slice 262

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] The test-edit allowlist forbids the changes 5.1, 7.1 and 7.4 require

The Context Summary (task line 46) says "If any other test fails, fix the code, not the test", and allows five kinds of edit. Three changes the plan requires break tests that pin the old refusals, and none of the five kinds covers them:
- `answer` joins `SERVED_OPERATIONS` (7.1, line 248). `tests/hub/test_handle_call.py:173-176` and `:365-372` use `answer` as the unserved probe. `tests/hub/test_app.py:121` and `:144` do the same. `tests/operations/test_served.py:118-119` expects `run_served("answer")` to raise `ValueError`.
- `send` stops refusing `not_served` (5.1, line 189). `tests/hub/test_door_operations.py:237-274` asserts `NOT_SERVED` for a due wake, twice.
- `handle-pause` and `wake-run` stop refusing on a joined machine (7.4, line 261). `tests/hub/test_joined_entry_points.py:69-86` expects `NotServedError` and exit 3 for `answer`, `handle-pause` and `wake-run`.

Read literally, line 46 requires restoring the refusals, which contradicts 5.1 and 7.1, and the checks cannot pass. Add these to the Migration Plan's allowed edits and to 5.1, 7.1 and 7.4. Each probe should use a name that stays unserved, such as `handle_pause`. The `send` and joined-CLI assertions should be rewritten to the new behavior.

### [FAIL] The after-step never runs on a joined machine

6.5 (line 233) says `wiring.invoke` calls `after_call` after every CLI operation. The existing `start_after` sits in the `finally` of the local branch (`wiring.py:173-180`). `invoke` returns earlier when `route` returns a door result (`wiring.py:168-172`). `route` returns for every served operation on a joined machine (`wiring_door.py:109-124`). So on a joined machine no after-step runs. Criterion 676 (alpha's next call resumes the run), the first 8.1 test (line 277), and the walkthrough's `amoeba list` on alpha all depend on it. 6.5 or 7.3 must state that `after_call` also runs on the `route` result, with `steps_for` choosing `DoorSteps`.

### [CONCERN] Writing steps are not wired into the keep, advice, or config paths

7.1 and 7.2 add the step names and say a step's "kept result" commits with it. They never say what decides that, and the existing code keys everything on names that exclude steps:
- The hub keeps a result only when `request.name in WRITING_CALLS` (`calls.py:228`). The client adds `UNKNOWN_ADVICE` only for `WRITING_CALLS` (`client/call.py:146`). Both checks are false for every step. Writing steps' results would not be kept, so a dropped `claim_work` or `resume_record` reply could not be replayed, which 8.2 depends on. Their advice would never print.
- `_needs_config` looks names up in the `SERVED` table (`calls.py:110-113`, `served.py:109`) and returns False for an unknown name. Any step whose edges call `load_config` then hits `_loaded` and an `AssertionError` (`calls.py:215-218`, `241-244`).

7.2 should say that keep and advice use `WRITING_STEPS` as well as `WRITING_CALLS`. It should also register each step in the `needs_config` table, with `resume_record`, `wake_set_pid` and `wake_finish` false, as D10 requires.

### [CONCERN] No test for the first-poll refusal

D6 (design line 318) and the Integration Requirements (design line 748) say a first poll that cannot be read records `refused` with the reason, where today nothing is stored, and that this frees the claim. 3.3 (line 134) describes it. 3.4 (lines 136-139) covers the started-with-unreadable-poll case, the attempt-file table, and a failed write. It does not cover the case with no attempt file. Add that test: no file, first poll unreadable, `refused` recorded with the reason, and the next `claim_resume` gets the claim.

### [CONCERN] The migration-012 test pins schema 12 and is not in the plan

The fixture asserts `migrate(opened) == read_schema_version(opened) == 12`. After 1.2 sets `EXPECTED_SCHEMA_VERSION` to 13, every test in that file errors. 1.2 (line 75) names only `test_schema_holds_no_mirrored_state.py` as a schema-version pin. Name this file and line in 1.2, or the commit at line 89 does not pass its suite.

### [CONCERN] Raw SQL inserts fail under the new machine trigger

1.2 (line 74) adds a `BEFORE INSERT` trigger that aborts when `machine_id` is null. `test_a_closed_question_needs_a_known_reason` runs `migrate` to the latest schema (line 366), then inserts a question with no machine (line 382, not wrapped in `pytest.raises`). It fails with `IntegrityError` before its assertions. The test at line 342 passes for the wrong reason. 1.5 (line 86) covers insert tests that bind through the acting machine, not raw-SQL fixtures. Name these tests in 1.5 and say to add `machine_id` to their inserts.

### [CONCERN] The reason labels for the new columns do not exist

1.2 (line 75) gives claim id and start counts the reason "run state". The test requires one of the keys in `COLUMN_REASONS`: record, membership, settings, messages, waking, marker, rulings, ownership, presence. Each is also a bullet in `docs/store-contract.md`. "run state" is none of them. The stamps beside these columns (`answers.resume_started_at`, `questions.start_attempted_at`) are under "record", so use record. "membership" is the PM's program registration, so it does not fit the machine columns either. "ownership" already covers which machine wrote a row (`sessions.machine_id`, `call_results.machine_id`).

### [CONCERN] The claim-age list in 2.1 is incomplete

2.1 (line 95) says every place that judges a claim stale at `answering_wait_seconds` moves to `pause_claim_seconds`, and lists `classify_pause`, `pause_existing` and `mcp/detached.py`. Two more do this. The close sweep closes claimed rows by `claimed_at` at `answering_wait_seconds` (`question_sweep.py:190`). The status classifier passes that limit into `classify_runs` (`status.py:197`), which calls `classify_pause` (`status_runs.py:178`). Left as written, the sweep and `status` would call a claim dead at 600 s while its owner is still inside its own limit, which D5 exists to prevent. 4.4 (line 164) does not name the sweep's claim check either. Name both sites in 2.1 or 4.4, with a test.

### [CONCERN] Deleting two modules breaks test files the plan does not name

6.5 (line 234) deletes `request_release.py` and `wiring_release.py`, and says to move their remaining tests. These importers are not named anywhere in the plan:
- `tests/load/test_start_ended_held_load.py:33-37`. This load test guards the busy-store, no-double-start contract, which the recent #48 fix made a regression test. No task carries that contract forward. 6.3 covers `claim_work` threads, not a busy writer.
- `tests/test_message_timing.py:39` and `:52`.
- `tests/release_child_wait.py:11`.
- `tests/operations/test_request_release.py`, `test_request_release_child.py`, `test_held_question_exits.py`.
- `tests/operations/test_handle_pause.py:27` (`MAX_STARTS_PER_CALL`).
- `tests/operations/test_status_calls.py:22` (`START_FAILED_OUTCOME`).
- `tests/test_wiring_release.py:41` imports `START_AFTER_OPERATIONS` from the deleted module. 235 assumes the import can be renamed.

Assign the load test to 6.3, rewritten for `claim_work`, or name its deletion. List the other importers under 6.5, and add them to 0.1's file list.

### [CONCERN] The fixture shares one HOME, and 7.5 does not name the mechanism

`env_for` gives the hub and every client the same `HOME` (line 198). `squadron_runs_dir()` is `Path.home()/.config/squadron/runs` (`src/amoeba/config/home.py:221-223`). The sq stub keeps its state under `$HOME/.sq-stub/runs` (`tests/sq_stub.py:73-74`). Today both fixture homes read and write one runs directory. The design's statement that two fixture homes have separate runs (design line 88) is therefore not true of the fixture. 7.5 (line 266) asks for "its own Squadron runs directory under that home" but does not say the change is a per-home `HOME`. Name it, so the test at line 267 can be built.

### [CONCERN] `steps_for` takes inputs that nothing in this slice uses

6.5 gives `steps_for` the door times and an optional session identity (263's four header values). No caller, test or criterion in 262 uses them. 263's tick adds them. D3 mentions them, but the plan should not build them before the slice that needs them. Drop them here.

### [CONCERN] 4.5 and 6.5 are each too large for one pass

4.5 moves ten modules to `Steps`, adds the `register` callable and two new skips, rewires `cli.commands.run_handle_pause`, adds an import rule, updates skip docs, and edits a test. Split it into (a) the modules take `Steps`, with no new behavior, and (b) `register`, the skips `OTHER_MACHINE` and `RESUME_IN_PROGRESS`, the answering-run ordering, and the docs. 6.5 bundles the after-step, `steps_for`, the `invoke` wiring, two deletions and the test moves. Put the deletions and test moves in their own task.

### [CONCERN] CI gating for the door load test is implicit

8.4 adds load bounds (2 s per call, 200 ms median) but names no CI wiring. CI runs a bare `uv run pytest` (`ci.yml:40`), and `pyproject.toml:70` ignores only `tests/live`, so `tests/load` does run in CI today. The gate exists but the plan does not name it. Say in 8.4 and 10.2 that this CI step gates `tests/load/test_door_load.py`.

### [NOTE] Two design rules in D3 have no test

D3 (design lines 204-205) says a machine that joins during a `LocalSteps` command fails its next store step with `LocalStoreClosedError`. It also says a hub home refuses the local opener with `HubHomeError`, so no client-run command runs on a hub's store. 7.3 and 7.4 test only the reverse direction. Add one test for each.

### [NOTE] 1.1 is too small to be its own item, and 1.5 needs a consistency fix

1.1 adds two enum members. Merge it into 1.2, where the `CHECK` lists are edited. The Context Summary (line 40) says `tests/store/schema_12.py` is added by 1.2, but 1.5 (line 82) is where it is first used.

### [NOTE] Two large source files will grow

`sql.py` is 543 lines and `wiring.py` is 297. 1.3 adds machine reads to `sql.py`, and 3.5, 6.5 and 7.x add to `wiring.py`. 10.2 (line 321) checks only new files. Put the machine reads in a new module, and put the after-step in `wiring_steps.py`, so `wiring.py` does not grow.

### [NOTE] 5.1 uses a body key that 7.1 creates

5.1 sets `log_stem` from "the new body key `logs_dir`". 7.1 (line 248) is where that key is added. Before 7, the local `send` has no body. Say how the local path passes the logs directory, for example as a parameter of the hub part, so 5.2's wake tests have a path.

### [NOTE] Nothing tests that a removed machine's wakes name it

Criterion 692 says the wakes `rm-machine` ends name the machine in their detail. 9.1 (line 305) tests the `log_stem` and the open questions, not the detail.

### [NOTE] The slice branch's target has an uncommitted change

0.1 requires that the design and this file are committed with no other uncommitted change. At review time the working tree shows this task file as modified (`M`). That is expected until the planning commit is made, but 0.1 cannot pass before then.

### [NOTE] The tool versions are unverified

The frontmatter says `sq` 0.24.38 and `cf` 0.19.28 on 20261123. The design says `sq` 0.24.34. I could not run `sq --version` or `cf --version` here. 0.1 (line 57) runs them, so keep that step.

### [PASS] Success criteria are covered by tasks

I traced each functional criterion (design lines 676-727) and the technical and integration requirements to a task. The gaps are the ones listed above. No task is out of scope for the criteria. The fixture's PATH check for `cf`, `sq` and `git` already exists (`tests/hub_fixture.py:80-84`), so 3.1 does not need a new one.

### [PASS] Each implementation section is followed by its tests

Sections 1 to 9 pair each implementation task with its tests, and each section ends with a plain `**Commit**:` line. The commit points are right only once the test-edit gaps above are closed.

### Run Digest

- Response length: 20396 chars
- Response is newline-free: no
- Tool calls made: 76
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 77
- Tokens — prompt / cached / cache write / completion / reasoning: 6597957 / 6316301 / 281590 / 136873 / not computed
- Duration: 597.8 s
- Cost: $0.83 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 22
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 22
- Finding-shaped matches — surviving validation: 22
