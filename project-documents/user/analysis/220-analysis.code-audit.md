---
docType: analysis
project: amoeba
topic: code-audit
dateCreated: 20261108
dateUpdated: 20261108
status: complete
---

# Analysis: Code Audit

Slice design: `user/slices/220-slice.code-audit.md`. Architecture: `user/architecture/220-arch.program-tool.md`.

## Summary

**What stays.** The answering pipeline and its pure parts (`pipeline_file`, `artifacts`, `decide`, `gate`, passage cutting, `answering.yaml`), reworked at their edges: `node_id`, journal entries and the tick budget come out, a slice value and the caller's checkout go in, and the settings move to a user-level config. Also kept: the `sq` launch, argv, run-id and resume-confirm helpers, `process/sq_outcome.py` (the one reader of `sq runs wait --json`), the bounded `cf` and `git` reads, the SQLite plumbing in `store/` (`connection.py`, `row_values.py`; 221 deletes the directory whole and 222 re-creates them), the program and member reads (for `set_up`), a thin `cli/main.py` and the `amoeba` entry point, the Context Forge plan parsers, the fake `sq` and `cf` test doubles, and three live answering tests. Everything else is deleted: the tick, nodes, journal, blocked states, the host and its lock, dispatch and lifecycle, the inbox, feed, HTTP server, inspection views, all review and verdict code, `upstream/` apart from the plan parsers, the old migrations, the slice-writing pipeline (D5), and their tests, scripts and contract docs. The architecture's "keep `upstream/`" was wrong.

**Slice 182: reuse parts.** Take the program passage kinds, `program_passages.py`, the pipeline text and the git helper renames; rewrite the tick wiring (`e0a4615`) and the concept read's store dependencies; drop the no-program path. Do not merge; 221 would turn a late merge into delete-modify conflicts. The 223 plan entry carries a note.

**Gaps.** Sixteen replacements the architecture does not cover are listed under Differences, for 222 to 224. The main ones: where the answering run's scratch directory is recorded, how a per-member authorize list reaches the static pipeline file, where `handle_pause` gets a run's slice, and the question record's real new key (`paused_at` exists nowhere in today's code).

**Squadron issues filed: none.** #299, #302 and #303 are closed and in `sq` 0.24.24; #304 stays on hold.

Verdicts for `src/amoeba`, `tests`, `scripts`, `docs` and packaged resources are by hand and by import and test-name scan; most test files were not read in full.

## Verdicts

Verdicts: `keep`, `rework`, `squadron`, `delete`. Scenarios: A pause handling, B program dependencies, C status, decisions and MCP, set-up. A row is a whole file unless it names functions.

### `src/amoeba/runner/answering/`

| Path | Verdict | Reason |
|---|---|---|
| `__init__.py` | keep | Package marker for the scenario A answering code. |
| `answering.yaml` | rework | Scenario A pipeline (answer step, then independent check). The "may not authorize" list is hard-coded in both prompts, but it becomes a per-member setting; the 182 program passage kinds also need naming in the prompts. |
| `pipeline_file.py` | keep | Scenario A: the one definition of step, param and file names. Needs only the generic `shipped_pipeline_path` helper. |
| `artifacts.py` | keep | Scenario A: parses `answer.json` and `check.json`; pure. |
| `inputs.py` | rework | Scenario A: writes `question.md`, `passages.md`, `rules/` and the cost cap for the scratch directory. `render_question` rejects a blank slice label, but a run with no slice must still be answered; the hook opt-out must be added to what it writes or passes. |
| `decide.py`: `decide_answer`, the `*_REASONS` maps, `Confirmed`, `Declined`, `sources_reason`, `_after_answer` | keep | Scenario A: the pure six-check decision on whether an answer stands. |
| `decide.py`: `RunSummary.of`, `_ended`, `RunState` | rework | Scenario A: built today from the tick's observed-run types; must be built from the `sq runs wait --json` result. Also imports `cut_to_bound` from `runner/ingest/`, which must move. |
| `gate.py` | rework | Scenario A: the answer screen and per-run answer limit are pure and stay; they read `AnswererSettings` (a per-project YAML section), which becomes the user-level config plus per-member settings. |
| `passages.py`: `cut_passages`, `render_passages`, `check_citations`, `glob_matches`, `select_plan_files`, `PlanRow`, `parse_git_date` | keep | Scenario A: pure passage cutting, rendering and citation check. Needs only `GLOB_WILDCARD`. |
| `passages.py`: `PmAnswer.node_id`, `_pm_order`, `assemble(question_node_id=...)`, `PassageKind` | rework | Scenario A: "same slice first" ordering is keyed on `node_id`; it must key on a slice value on the question record. `PassageKind` gains the 182 program kinds. |
| `source_reads.py` | rework | Scenario A: reads rules and plan files at the target commit through git, and knows where Context Forge keeps documents. Every function takes a `TickBudget` and returns `None` when it refuses; remove both. |
| `sources.py` | rework | Scenario A: assembles the passage sources. Every function reads node rows (see Dependencies). |
| `launch.py`: `passage_refs`, `_prepare_scratch`, `_discard_scratch`, argv build | rework | Scenario A: scratch preparation, `sq run` argv for the answering pipeline, passage provenance. |
| `launch.py`: `LaunchContext`, `launch_answering`, `LaunchStatus.STOPPED` and `SKIPPED`, tracker and log-path use | delete | Tick-launched, tied to `LaunchTracker`, `TickBudget` and a journal entry. `handle_pause` waits on the answering run instead (223). |
| `finish.py` | delete | Changed from `rework` in 221 (D1, D2): every part is keyed on journal entries or writes the store (settle, submit, decline, discard-if-the-PM-answered-first). The pure remainder is reading the two reply files and calling `decide_answer`, which 223 writes against the new record. `QuestionInvariantError` has no kept importer and went with it. |
| `settle.py` | delete | Pure tick logic over blocked states. Two outcomes survive as `handle_pause` declines (blank question text, answerer not configured). `QuestionInvariantError` lives here but `finish.py` imports it, so it needs a new home. |
| `stage.py` | delete | `AnsweringStage` exists only to be called from the tick, over journal entries, blocked states and the run observer. Its stranded-claim idea is the architecture's dead-claim rule (223). |

### `src/amoeba/store/`: question and answer units

| Path | Verdict | Reason |
|---|---|---|
| `questions.py`: `question`, `questions`, `decline_question`, `_write_evidence`, `require_transition` | rework | Scenarios A and C: the question record read and decline paths. `questions()` filters on `node_id`; the states are pending, answering, answered and declined, not claimed, answered, waiting, then resumed, refused or not delivered. |
| `questions.py`: `record_question`, `_insert_question`, `question_for_block`, `_settle_question_on_acknowledgment`, `pending_questions` | delete | Writes a human block plus the record, keyed on a journal entry and node. The claim becomes an operation keyed on run id and `paused_at` (222, 223). |
| `question_models.py`: `QuestionState`, `AnsweredBy`, `DeclineReason`, `PassageRef`, `AnsweringEvidence`, `GateRefusal`, `AnswerGate`, `AnswerOutcome` | rework | Scenario A: the question vocabulary. `QUESTION_TRANSITIONS` is rewritten for the new states; `NODE_ALREADY_BLOCKED` and `ANSWER_DISCARDED` are dead. |
| `question_models.py`: `QuestionCatch`, `QuestionRecord`, `AnsweringLaunch`, `BeginStatus`, `BeginOutcome`, `ANSWER_DECISION`, `AnswerSubmission` | rework | Scenario A: the record shape. Drop `node_id`, `source_entry_id`, `blocked_state_id`, `answering_entry_id`, `step`; add `paused_at`, the checkout, the answering run id and the resume state. |
| `sql_questions.py` | rework | Scenario A: the one site for question SQL. Columns and queries keyed on node, journal entry and block change; `COUNT_ANSWERER_ANSWERS_IN_RUN` already fits the per-run limit. |
| `mapping_questions.py` | rework | Scenario A: row mapper over the question columns; the list and passage-index encoders carry over unchanged. |
| `answer_submission.py` | rework | Scenario A: the gated, atomic "answered plus evidence" write stays. It also resolves a blocked state, fills a resolution slot and inserts an inbox submission, all of which go. The most entangled kept unit. |
| `answering.py` | rework | Scenario A: the atomic claim that records source commit, passage index and dropped PM answers. It also writes a journal entry; it reduces to a claim keyed on run id and `paused_at` with the answering run id, folded into the new questions module. |
| `project_escalations.py` | delete | Tick-fault escalation messages; pull-not-push plus `status` replaces them. |
| `routing_decisions.py` | delete | Nothing uses it: no caller outside `store/` and tests; old supervisor routing tables. |

### `src/amoeba/store/`: everything else

| Path | Verdict | Reason |
|---|---|---|
| `nodes.py`, `mapping.py`, node and blocked parts of `models.py` and `sql.py` | delete | No nodes or blocked states in the new design. |
| `blocking.py`, `_block_writer.py` | delete | Blocked states, runner queries and escalation messages. |
| `journal*.py`, `mapping_journal.py`, `sql_journal.py` | delete | Command journal and recovery. `decode_mapping` and `decode_timestamp` are used by kept code and move to `row_values.py`. |
| `desired_states.py`, `messages.py`, `runner_models.py`, `runner_report.py`, `mapping_runner.py`, `sql_runner.py`, `write_values.py` | delete | Tick desired state, message queue, routing tables and runner report. `write_values.py` is imported only by the two deleted routing and escalation units. |
| `inbox.py`, `inbox_models.py`, `mapping_inbox.py`, `sql_inbox.py`, `_submission_writer.py` | delete | The submission inbox. `BEGIN_IMMEDIATE` lives in `sql_inbox.py` and moves to `sql.py`. |
| `feed*.py`, `mapping_feed.py`, `sql_feed.py` | delete | The change feed, review watches and detection ledger. |
| `cf_snapshots.py`, `cf_models.py`, `mapping_cf.py`, `sql_cf.py` | delete | Context Forge links and snapshots filled by the resident watcher. |
| `checks.py`, `check_models.py`, `_check_writer.py`, `sql_checks.py` | delete | Check results and progress records; nothing in A to C. |
| `verdicts.py`, `verdict_payload.py`, `_verdict_writer.py`, `evidence_models.py`, `mapping_evidence.py`, `sql_evidence.py`, `finding_identity.py`, `calibration.py` | delete | Review verdicts and findings. Importers are the review parser in `upstream/squadron/`, `inbox/`, `cli/ingest.py` and `inspection/checks.py`, all deleted. |
| `review_sources.py`, `attribution.py`, `discovery.py` | delete | Review file polling, review-to-slice-node attribution, and scanning for per-project store files. |
| `schema/001` to `015*.sql` | delete | No data to migrate; 222 writes one baseline. 013 to 015 hold `question_records` keyed on node, journal entry and block, and the feed triggers. |
| `program_schema/001_program_record.sql` | delete | Holds `requests_initiative`, `consumption_overrides` and `program_submissions`; the 222 baseline replaces it. |
| `__init__.py` | rework | Re-exports about 150 names; shrinks to the new store surface. Set-up, A. |
| `store.py` | rework | `Store` mixes 17 operation classes over per-project files; becomes one class over the single user-level store. Set-up, A. |
| `connection.py` | rework | Set-up: opens with WAL, busy timeout, read-only mode and typed errors, taking package and version as arguments; the code is wanted. 221 deletes `store/` whole (task 2.12), so 222 re-creates it in the new store and may restore the old version from the commit 221 branched from (changed from `keep` on 20261108 after 221 and 222 were updated). |
| `migrations.py` | rework | Set-up: the version stamp and runner stay for one baseline package; the program migration line goes and the expected version becomes 1. Needs a race guard (see Differences). |
| `paths.py` | rework | Set-up: keep `store_dir`, the `AMOEBA_STORE_DIR` test override, the path validators and `GLOB_WILDCARD`. Delete `store_path`, `project_store_path`, `program_dir`, `program_store_path`, `STORE_CREATING_SUFFIX`, `validate_project_id`. |
| `_base.py` | rework | Set-up, A: keep `StatementRunner`, `now`, `isoformat`, `new_id`; drop the node and message lookups. |
| `sql.py` | rework | Set-up: keep the busy timeout, PRAGMAs and `schema_meta` statements; drop node and blocked statements; add `BEGIN_IMMEDIATE`. |
| `models.py` | rework | Set-up, A: keep the `StoreError` family, `UnknownVocabularyValueError` and `QuestionNotFoundError`; the rest goes with nodes. |
| `row_values.py` | rework | Set-up, A: typed column reads used by the question and program mappers, plus the `decode_mapping` and `decode_timestamp` helpers from `mapping_journal.py`. Re-created by 222 in the new store like `connection.py` (changed from `keep` on 20261108). |
| `program_models.py` | rework | Set-up, B: `ConsumptionMode` stays. `Program` and `Member` lose `requests_initiative` and overrides; `Member` gains per-member settings and dependency pairs. `ProgramSubmission*` and the override and requests rejections go. |
| `program_store.py`, `_program_reads.py`, `mapping_program.py`, `sql_program.py` | rework | Set-up, B: the program and member reads and typed mapping stay as the programs, members and dependencies layer. The separate-file `ProgramStore` merges into the single store; overrides and submissions statements go. |
| `_program_writer.py`, `_program_specs.py` | rework | Set-up: the validate-in-one-`BEGIN IMMEDIATE`-transaction shape is reusable for `set_up`. `apply_submission`, `program_submissions`, overrides and `requests_initiative` go. |

### `src/amoeba/runner/` (other than `answering/`)

The code that starts, polls and resumes `sq` runs lives here and in `process/`, not in `upstream/`. The rows marked "223 base" are what slice 223 builds `handle_pause` and the resume from.

| Path | Verdict | Reason |
|---|---|---|
| `launch.py`: `mint_run_id`, `SQUADRON_RUN_ID_PATTERN`, `build_argv`, `param_problem`, `spawn`, `stderr_confirms`, `stderr_tail`, `LaunchError`, `PopenFactory`, `STDERR_TAIL_LIMIT_BYTES` | rework | Scenario A, 223 base: starts the answering run and the detached resume (`start_new_session`, log file, `cwd=checkout`). Log naming is tied to the journal entry id today. |
| `launch.py`: `launch(entry, ...)`, `text_parameter`, `_params_parameter`, `PARAM_*` journal keys, `LaunchTracker`, `TrackedLaunch`, `LAUNCH_LOGS_DIRNAME` | delete | Launching a journaled command and reaping children each tick. |
| `resolutions/argv.py` | keep | Scenario A, 223 base: `resume_argv` builds `sq run --resume <id> --instructions <text>`. Only its `SQ_RUN_COMMAND` import path changes. |
| `resolutions/confirm.py`: `ResumedFrom`, `has_left`, `is_at`, `resume_progress` | rework | Scenario A, 223 base: the checkpoint compare and resumed or refused judgment. Its inputs come from journal entries today. |
| `resolutions/confirm.py`: `resumed_from_entry`, `STOPPED_OUTCOMES` | delete | Reads journal entries. |
| `resolutions/` (`act`, `classify`, `judge`, `planner`, `prepoll`, `stage`, `vocabulary`) | delete | PM resolutions of blocked nodes; the `answer` operation replaces them. |
| `cf_call.py` | keep | Scenario A: `run_cf`, a bounded subprocess call with `CfCallFailed`, used by the git and Context Forge reads. |
| `git_read.py`: `git_read`, `show_object_args`, `resolve_commit_args`, `last_change_args`, `parse_tree_*` | rework | Scenario A: reads committed files for passages. Remove the `TickBudget` parameter. |
| `git_read.py`: `status_args`, `parse_porcelain_v2`, `GitStatus`, `is_ancestor_args` | delete | Used only by the dispatch checkout check. |
| `dispatch/checkout_reads.py`: `read_config`, `read_target` | rework | Scenario A: reads `git.integration_branch` through `cf config get` in the checkout, which the passage sources need. Move out of `dispatch/`. |
| `dispatch/` (everything else) | delete | Launches a slice's pipeline from the tick; Amoeba starts no work. |
| `lifecycle/plan_read.py`: `cf_argv`, `config_get_command`, `CF_KEY_INTEGRATION_BRANCH` | rework | Scenario A: needed by `read_target`. Move into the same small Context Forge read module. |
| `lifecycle/` (everything else) | delete | The node tree reconciled from a plan read; there are no nodes. |
| `observed.py`: `RunEnded`, `RunVanished`, `LaunchFailed`, `ResumeFailed`, `Finished` | rework | Scenario A: outcome values the answering decision consumes. Keep as plain values. |
| `observed.py`: `ObservedRun`, `Observed`, `TickResult` | delete | Wrappers over in-flight runs, journal and tick. |
| `faults.py`: `LaunchFailure`, `ResumeFailure` | rework | Scenario A: two standalone enums used by launch, observed, confirm and the answering code. Move them. |
| `faults.py` (the rest) | delete | Node, blocked-state and escalation code. |
| `ingest/outcome.py`: `cut_to_bound` | rework | Scenario A: bounded text cutting used by `decide.py` and `launch.py`. Move it. |
| `ingest/outcome.py` (the rest), `ingest/record.py`, `ingest/reviews.py` | delete | Node-block planning and review recording. |
| `project_config.py`: `AnswererSettings` | rework | Scenario A, set-up: the answering settings move to the user-level config and the member's settings. |
| `project_config.py` (the rest) | delete | Per-project pipeline and params, `max_concurrent_runs`, the YAML file model. |
| `pipeline_resource.py` | keep | Scenario A: `shipped_pipeline_path` locates the packaged `answering.yaml`. |
| `supervise.py`, `observe.py`, `observe_resume.py` | delete | Outcome classification, the tick's run observer and journal resume observer. Reference only for 223; `observe_resume.tail_or_error` is worth copying. |
| `tick.py`, `act.py`, `decide.py`, `finish.py`, `record_runs.py`, `project_view.py`, `budget.py`, `factory.py`, `tenant.py` | delete | The tick loop and its journal and node plumbing; nothing in A to C uses them. |
| `probes.py` | delete | Resident start-up probes. The `--validate` check of `answering.yaml` is worth keeping as a test, not as runtime code. |
| `intent/` | delete | PM intents applied to nodes. |
| `program/` | delete | `ProgramStage` is a read-only tick stage; the store's program lookup is the real one. |
| `request_run/`, `slice_writing.yaml` | delete | Slice 180's slice-writing pipeline (D5). Scenarios A to C start no work, so no scenario calls it; its only source importer is `probes.py`. Slices 183 to 186 are retired. |
| `tests/runner/request_run/` (6 test modules and `__init__.py`), `tests/runner/test_probes_request_run.py`, `tests/live/request_run/` (all files), `tests/live_request_settings.py`, `tests/fixtures/slice_writing/` (`already_met/reply.json`, `new_slice/reply.json`) | delete | Tests, live tests and settings helper of the slice-writing pipeline, which goes (D5). The Tests section below repeats this for coverage. |
| `__init__.py` | delete | Exports `runner_tenant`; imported only by the old CLI. |

### `src/amoeba/process/`

| Path | Verdict | Reason |
|---|---|---|
| `sq_outcome.py` | rework | Scenario A, 223 base: the one reader of `sq runs wait --json` (`poll_run`, `RunOutcomeDocument`, `RunCheckpoint`, kind enums). It hard-codes `--timeout 0`, models no working directory, run parameters or `execution_mode`, and carries `RunReview`, which only deleted ingest uses. |
| `__init__.py` | rework | Scenario A: its exports are the facade the answering code imports; drop the host, tenant, observer, recovery and review exports. |
| `settings.py`: `sq_timeout_seconds`, `cf_timeout_seconds`, `launch_grace_seconds`, `cf_data_dir`, `sq_runs_dir` | rework | Scenario A, set-up: these move into the user-level config. Defaults must not stay as magic values in code. |
| `settings.py` (the rest) | delete | Idle, shutdown, tick, inbox, review-scan and cf-scan settings, `auto_resume_limit`, `project_config_path`. |
| `errors.py`: `StartupFailedError` | rework | Scenario A, set-up: imported by `project_config`; keep or replace with the new config error. |
| `errors.py` (the rest) | delete | `AlreadyRunningError`, `GraceExpiredError`, `UpstreamShapeError`. |
| `host.py`, `supervisor.py`, `tenants.py`, `grace.py`, `project_stores.py`, `instance_lock.py`, `log_limit.py` | delete | The resident process: tenant loop, instance lock, shutdown grace, single-writer opener. There is no resident process. |
| `recovery.py`, `observers/` | delete | Recovery of journaled commands by observation. `observers/sq_runs.py` is the legacy run-file matcher; `sq runs list --json` now gives the working directory. |
| `inbox_drain.py`, `inbox_tenant.py`, `program_inbox_tenant.py` | delete | The inbox goes. |
| `cf_watch.py` | delete | A resident watch for Context Forge pointer moves. |
| `review_detection.py`, `review_scan.py` | delete | A resident review-file scan that records verdicts on nodes. |
| `run_pruning.py` | delete | Prune candidates from journal ownership; `sq runs prune` already exists in Squadron. |
| `version_label.py` | delete | A provenance label on journal ticks; the question record has no such field. |

### `src/amoeba/upstream/`, `program/`, `cli/`, `inspection/`, `serve/`, `inbox/`, `feed/`

| Path | Verdict | Reason |
|---|---|---|
| `__init__.py` | keep | Package root; set-up. |
| `upstream/context_forge/plan.py`: `parse_initiatives`, `parse_slice_list`, `CFInitiative`, `CFSliceList`, `CFErrorDocument` | rework | Scenario A: the kept answering code needs a slice's initiative index from Context Forge in the checkout, and these parse that output. Drop the plan-status and `reported_complete` helpers; 223 drops the whole file if it reads the index another way. |
| `upstream/context_forge/checkout.py` | delete | Picks a checkout from a stored snapshot; the checkout is now the run's working directory passed in. Imports `amoeba.store.CFSnapshot`. |
| `upstream/context_forge/projects_file.py`, `diff.py`, `slice_stem.py`, `__init__.py` | delete | `projects.json` projection and snapshot diff for the resident watcher; `slice_stem` is used only by node machinery. |
| `upstream/squadron/` (`review*.py`, `__init__.py`) | delete | Parses `sq review` output into verdict records; no scenario uses review verdicts. |
| `program/members.py`, `__init__.py` | rework | Scenario C, `status`: a member that cannot be read must show with a reason. Only the closed `Readable` and `Unreadable` vocabulary survives; all five reasons depend on deleted things. If 224 does not want readability, this is a delete. |
| `cli/main.py`, `cli/__init__.py` | rework | All scenarios: the `amoeba` entry point and the single process-boundary handler stay as the thin shell over the eight operations. The old parsers and most exit codes go. |
| `cli/lifecycle.py`, `settings_flags.py` | delete | Start, stop and status of the resident process; its settings flags. |
| `cli/inspect.py` | delete | Prints the inspection registry; `status` and `decisions` (224) replace it. |
| `cli/submit.py`, `cli/ingest.py` | delete | Writes inbox submissions; submits a review as a verdict. |
| `cli/feed.py`, `cli/serve.py` | delete | The feed follower and the HTTP server command. |
| `cli/prune.py` | delete | Prunes runs the resident runner owns; `sq runs prune` already exists. Not a Squadron candidate, since it depends on Amoeba owning the runs. |
| `inspection/` (11 modules) | delete | Every row function reads nodes, journal, blocked states, verdicts, snapshots, inbox or the feed. `questions.py` is a column reference for `status` and `decisions` (224), not code to keep. |
| `serve/` | delete | HTTP and SSE server; the only user of `starlette` and `uvicorn`. |
| `inbox/` | delete | File inbox drained by the resident tenant, including the program envelope and payload files. |
| `feed/` | delete | Change-feed follower for a feed that goes. |

### `tests/`

Rule (D1, D2): tests follow the code they exercise. A test of deleted code is `delete`. A test of kept code is `rework` only if its claim holds without nodes, journal entries, blocked states or the tick, otherwise `delete` and the slice that rebuilds that code writes new ones (222 for the store, 223 for pause handling, 224 for the CLI and status). Verdicts here come from each file's imports and test names; most files were not read in full. "Keep" means it works unchanged once the source deletions are made.

Test directories named `runner`, `store`, `process` and `live` are importable top-level packages, and some kept tests import helpers from them. A deleted directory's helpers must go in the same commit as their importers, and every kept directory keeps its `__init__.py`.

**Top-level files in `tests/`**

| Path | Verdict | Reason |
|---|---|---|
| `conftest.py` | rework | Set-up, A: keep `pytest_sessionstart` (orphan reaping), `store_file`, `store`, `supervisor_dir`. Drop the fixtures that import `inbox_harness` and `serve_harness`. |
| `answerer_settings.py` | rework | A: builder for the answering settings; follows the 222 config move. |
| `ast_strings.py`, `cf_stub_gates.py`, `test_cf_stub_gates.py` | keep | A: generic AST helper for "spelled once" tests; the `cf config get` stub for `read_target` and its self-test. |
| `cf_stub.py` | rework | A: keep `cf config get`, `cf list initiatives` and `cf list slices`; drop the `cf status --json` probe parts. |
| `sq_stub.py`, `sq_stub_scripts.py`, `test_sq_stub_run.py` | rework | A, 223 base: the fake `sq` (run, runs wait, validate) and its self-test. Drop the review scripts (they import `review_fixtures`), `runs prune`, and any `--timeout 0` assumption. |
| `sq_stub_resume.py`, `test_sq_stub_resume.py` | keep | A, 223 base: the fake `sq run --resume` and its self-test. |
| `process_containment.py`, `test_process_containment.py` | keep | Test hygiene for every scenario: file-size cap and orphan reaping for child processes. |
| `fault_injection.py` | delete | Changed from `rework` in 221 (D1, D8): it patches the old `Store` and its SQL constants, which go whole. 222 and 223 write their own for the new store. |
| `cli_harness.py` | delete | Changed from `rework` in 221 (D1, D8): it runs `amoeba.cli.main`, which no longer exists, and nothing uses it until 224 writes the commands. |
| `test_observer_sq_outcome.py`, `test_observer_sq_outcome_fields.py` | rework | A, 223 base: tests of the one `sq runs wait --json` reader. The exact-argv test changes with the timeout; drop the review tests. |
| `test_process_public_api.py`, `test_public_api.py` | delete | Changed from `rework` in 221 (D1, D8): they pin the export lists of `amoeba.process` and `amoeba.store`, both deleted; 222 writes export tests for the new surface. |
| `test_migrations.py` | delete | Changed from `rework` in 221 (D1, D8): it tests `store/migrations.py` and the 15 old migrations, which go whole. 222 writes the stamp, newer-than-code, corrupt-file, failed-migration and no-op claims against its baseline. |
| `test_paths.py`, `test_read_only_open.py`, `test_failure_modes.py` | delete | Changed from `rework` in 221 (D1, D8): they test `store/paths.py`, `connection.py` and the node and journal writes, all deleted. 222 writes store location, env override, read-only open, busy timeout and WAL claims. |
| `test_store_safety.py` | rework | Set-up: guard that no test touches the central store; it builds its forbidden names from `paths.store_path`, which goes. |
| `test_import_boundaries.py` | rework | Set-up: keep the store, cli and runner layering rules; drop the feed, serve, inspection and run-pruning rules. It already fails on deleted names. |
| `live_environment.py`, `live_harness.py`, `live_settings.py` | keep | A: the live tier's helpers; they import only kept units. See Live tests. |
| `test_store.py`, `test_queries.py`, `test_models.py`, `test_journal.py`, `test_journal_models.py`, `test_create_node_guard.py`, `test_writer_guard.py`, `legacy_nodes.py`, `routing_helpers.py`, `sq_run_fixtures.py` | delete | Nodes, blocked states, the journal and their guards and seed helpers. |
| `test_host.py`, `test_host_program_store.py`, `test_instance_lock.py`, `host_harness.py`, `local_host_harness.py` | delete | The resident host and instance lock. |
| `test_recovery.py`, `test_recovery_sq_answer.py`, `test_observer_sq_run_id.py`, `test_observer_sq_runs.py`, `test_observer_cf_readback.py`, `test_version_label.py` | delete | Journal recovery, the observers and the version label. |
| `test_cli_inspect.py`, `test_cli_lifecycle.py`, `test_settings_flags.py` | delete | Deleted CLI commands; 224 writes new. |
| `test_demo_evidence_payloads.py`, `detection_e2e_harness.py`, `detection_harness.py`, `evidence_harness.py`, `review_fixtures.py` | delete | Review evidence and detection. |
| `cf_fixture.py`, `cf_harness.py`, `cf_watch_harness.py` | delete | The `projects.json` fixture, snapshots and the resident watcher. |
| `feed_harness.py`, `inbox_harness.py`, `ingest_e2e_harness.py`, `inspection_harness.py`, `serve_harness.py`, `program_harness.py` | delete | Rigs for the feed, inbox, ingest, inspection, server and old program submissions. |
| `question_harness.py` | delete | Seeds question records through nodes and journal entries. 222 and 223 need their own seeding helper; seeding any state through the store's SQL constants is worth copying. |
| `test_answerer_walkthrough_script.py`, `live_request_settings.py` | delete | Tests the old walkthrough script setup (`amoeba start`, `projects.yaml`); the slice-writing live tier's settings. |

**Directories**

| Path | Verdict | Reason |
|---|---|---|
| `tests/live/` | see Live tests | Per-file verdicts for `answering/` are in the Live tests section. `live/request_run/` is deleted (D5, in the runner table above). `live/conftest.py` stays with the live tier. |
| `tests/load/` (14 files) | delete | Resident-host and tick load, server load, crash loops and inbox concurrency. |
| `tests/contract/` | delete | The slice 110 proof harness: start, submit, journal recovery and the public-API rule over inbox, feed and inspection. |
| `tests/feed/`, `tests/inbox/`, `tests/inspection/`, `tests/serve/` | delete | Tests of deleted source packages. |
| `tests/cli/` (15 files) | delete | They exercise submit, ingest, feed, serve, inbox, evidence, judge and watch commands; 224 writes new CLI tests. |
| `tests/process/` (21 files) | delete | cf watch, inbox tenants, project stores, prune, review detection, tenant order, log limit. |
| `tests/program/test_read_member.py` | delete | Member readability through cf links, snapshots and per-project store files. 224 writes new if readability stays. |
| `tests/upstream/test_cf_plan.py` | rework | A: `parse_initiatives` and `parse_slice_list` over the fixtures; drop the plan-status tests. |
| `tests/upstream/test_import_direction.py` | delete | Changed from `rework` in 221 (D1, D6): its only live rule ("upstream does not import the inbox, process or store") is trivially true now; `tests/test_import_boundaries.py` enforces the one D6 rule. |
| `tests/upstream/context_forge/` (5 files), `test_field_names_defined_once.py`, `test_review_*.py` (7 files) | delete | Tests of the deleted watcher units and the review parser. |
| `tests/store/test_migration_004.py` to `test_migration_015.py` | delete | No data to migrate; 222 writes one baseline. |
| `tests/store/` question and answer group: `test_question_records`, `_question_answering_fields`, `_question_record_catch`, `_question_acknowledgment`, `_answering_evidence`, `_answer_submission`, `_begin_answering`, `_resolutions` | delete | All seeded through `question_harness` (nodes, journal entries, blocked states, resolution slot, inbox submission). 222 and 223 write new ones for the new states and the per-run answer count. |
| `tests/store/` program group: `test_program_apply_member`, `_apply_program`, `_reject_program`, `_program_schema`, `_program_store_open` | delete | Submissions, overrides, `requests_initiative` and the separate program file; 222 writes new for B. |
| `tests/store/` node, routing, inbox, feed, cf, check, verdict and evidence groups (`test_terminal_done`, `_read_transaction`, `test_routing_*`, `_unrouted_outcomes`, `_desired_state`, `_messages`, `_runner_report`, `_project_escalation`, `_attribution`, `_inbox_*`, `_feed_*`, `_mapping_feed`, `_cf_snapshots`, `_link_cf_project`, `_watch_reviews`, `_review_sources`, `_detections`, `_record_detected_verdict`, `_checks`, `_check_*`, `_evidence_models`, `_finding_*`, `_verdict*`, `_calibration`, `_judge_samples`, `_provider_failure_problem`) | delete | Tests of deleted store units. |
| `tests/runner/answering/`: `test_read_answer.py`, `test_read_check.py`, `test_pipeline_yaml.py`, `test_wheel_contents.py`, `test_question_tails_fixture.py`, `fixtures/sources/`, `expected_passages.md` | keep | A: parsing of the answer and check files, the shipped pipeline file, captured question tails (which read the live fixture file), and the passage fixtures. `test_pipeline_yaml.py` changes only when the authorize-list claim is settled. |
| `tests/runner/answering/`: `test_passages.py`, `test_inputs_render.py`, `test_prepare_scratch.py`, `test_decide.py`, `test_stub_answering.py`, `test_source_reads.py`, `sources_repo.py` | rework | A: passage cutting, question rendering, scratch preparation, the six-check decision, the stub run, git reads at the target commit. Each changes for a reason named in the src rows: `node_id` to a slice value, blank-slice flip, hook opt-out, `RunSummary.of` inputs, no `TickBudget`. |
| `tests/runner/answering/`: `test_sources.py`, `test_walkthrough_fixture.py`, `sources_assembly.py`, `fixtures/expected_end_to_end.md`, `test_launch_prepare.py`, `test_launch_answering.py`, `launch_rig.py`, `test_finish_answering.py`, `test_settle.py`, `test_stage_observe.py`, `test_stage_pending.py`, `test_stage_stranded.py` | delete | Assembly over node trees and snapshots, launching through nodes, journal and the tracker, settling keyed on journal entries, and the deleted `settle.py` and `stage.py`. 223 writes new for each claim. |
| `tests/runner/answering/test_live_tier_rules.py` | keep | A: checks `live_settings` and the question tails; follows `tests/live`. |
| `tests/runner/`: `test_answer_gate.py`, `test_git_read.py`, `test_git_read_only_place.py`, `test_launch.py`, `test_launch_ids.py`, `test_launch_logs.py`, `test_cf_commands_defined_once.py`, `test_cf_stub_plan.py` | rework | A, 223 base: the screen, git reads, launch argv and run ids, launch logs, the Context Forge command scan and stub plan reads. Drop the budget, journal-entry, tracker, porcelain-status and log-by-entry-id tests. |
| `tests/runner/test_cf_call.py`, `git_repo.py`, `purity.py`, `__init__.py` | keep | A: `run_cf`; real temp git repos; the "no I/O" check; the package marker. |
| `tests/runner/observe_support.py` | delete | Changed from `rework` in 221 (D1, D8): the kept tests used `Clock` and `Host` only to build a `TickBudget`, which goes, and nothing uses `FakeCf`, so no generic fake needed splitting out. The kept source-read and git-read tests count calls through a wrapper on `run` instead. |
| `tests/runner/dispatch/test_checkout_target.py` | rework | A: `read_config` and `read_target`. Drop the budget test; its `main` default is the magic default flagged above. |
| `tests/runner/resolutions/test_argv.py` | keep | A, 223 base: `resume_argv`. |
| `tests/runner/resolutions/test_confirm.py` | rework | A, 223 base: the `resume_progress` table; drop the `resumed_from_entry` tests. |
| `tests/runner/test_live_environment.py`, `test_watch_run.py` | keep | A: tests of the live helpers that sit outside `tests/live`; follow `tests/live`. |
| `tests/runner/` the tick, crash and plumbing group (`test_tick*`, `test_tenant*`, `test_crash_*`, `test_decide.py`, `test_budget*`, `test_factory`, `test_faults`, `test_finish`, `test_observe_*`, `test_supervise`, `test_sq_answer_readers`, `test_end_to_end*`, `test_project_config.py`, `test_probes*.py`; helpers `tick_support`, `plan_tick_support`, `crash_*`, `gate_rig`, `conftest.py`) | delete | The tick loop, journal and node plumbing, the per-project config file model (222 writes new for the answering settings), and the probes. `conftest.py` only installs `passing_checks` from `tick_support`. |
| `tests/runner/dispatch/` (everything else), `resolutions/` (everything else), `ingest/`, `intent/`, `lifecycle/`, `program/`, `request_run/` | delete | Tests of deleted runner subpackages (see the runner table). |
| `tests/fixtures/answering/` | keep | A: the `answer.json` and `check.json` captures. |
| `tests/fixtures/sq_outcomes/` | rework | A: keep the paused and failed captures; drop the review captures. |
| `tests/fixtures/cf/` | rework | A: keep `list_initiatives_a.json`, `list_slices_*.json` and `config/`; delete `projects.json` and `cf_get_amoeba.json`. |
| `tests/fixtures/git/`, `slice_writing/`, `sq_reviews/`, `sq_runs/` | delete | Porcelain-status captures, slice-writing replies, the review parser's captures, the legacy run-file matcher's captures. |
| `tests/fixtures/README.md` | rework | Set-up: trim to the kept fixture sets. |

Helpers kept tests need that sit in deleted areas, which 221 must split out before deleting: `observe_support.py` (generic fakes), `tests/conftest.py` (imports `inbox_harness` and `serve_harness`), `sq_stub_scripts.py` (imports `review_fixtures`), `sources_repo.py` (imports `runner.budget`), and `test_question_tails_fixture.py` (reads a file under `tests/live/answering/fixtures/`).

### `scripts/` and `docs/`

| Path | Verdict | Reason |
|---|---|---|
| `scripts/answerer_walkthrough.py` | delete | Changed from `rework` in 221 (D1, D9): once `amoeba start`, the store directory and `projects.yaml` are dropped it only builds a scratch checkout and prints instructions for commands that do not exist. 223 rebuilds it against `handle_pause`; the scratch git checkout, throwaway Context Forge project (`cf init`, `cf set`, `cf get --json`) and `.env` copy are in git history. |
| `scripts/answerer_walkthrough/project/` (six fixture files) | rework | Scenario A: the project content the walkthrough's passages come from. Kept as data, now without its script. Used by `test_walkthrough_fixture.py` (deleted); 223 rebuilds a passage-assembly test on it. |
| `scripts/demo_detection.py` | delete | Seeds nodes and takes the resident instance lock. |
| `scripts/demo_evidence.py`, `scripts/demo_evidence/` (three JSON files and a README) | delete | Seeds a node for verdict submission walkthroughs. |
| `scripts/demo_inbox.py` | delete | Seeds a human-blocked node. |
| `docs/answerer-walkthrough.md` | delete | Changed from `rework` in 221 (D1, D9): its steps (`amoeba start`, journal entries, inspect, nodes) describe the old design, and `handle_pause`, `answer` and `status` do not exist yet, so a rewrite would name code that is not there. 223 and 224 write the new walkthrough. |
| `docs/context-forge-contract.md` | delete | The `projects.json` watch, snapshots, plan reads and the runner's use of Context Forge. |
| `docs/evidence-contract.md` | delete | Verdicts, findings, judge samples and calibration. |
| `docs/feed-contract.md`, `docs/inbox-contract.md`, `docs/network-contract.md` | delete | The change feed, the inbox and messages, the HTTP server. |
| `docs/process-contract.md` | delete | The resident process, tenants, recovery and the old CLI. |
| `docs/store-contract.md` | delete | The old store (nodes, journal, blocked states); 222 documents the new one. |
| `docs/substrate-guide.md` | delete | An index to initiatives 120, 140 and 160 and the old contracts. |

### Packaged resources

| Resource | Verdict | Reason |
|---|---|---|
| `pyproject.toml` `[project.scripts] amoeba = "amoeba.cli.main:main"` | keep | The one console entry point for every scenario; the `main` it names is reworked. |
| `pyproject.toml` artifact `store/schema/*.sql` (15 migrations) | delete | No data to migrate; 222 adds a baseline and updates this entry. |
| `pyproject.toml` artifact `store/program_schema/*.sql` | delete | Holds `requests_initiative`, `consumption_overrides` and `program_submissions`; the 222 baseline replaces it. |
| `pyproject.toml` artifact `runner/answering/answering.yaml` | keep | Scenario A answering pipeline (the file itself is a rework row above; the packaging entry stays). |
| `pyproject.toml` artifact `runner/request_run/slice_writing.yaml` | delete | D5: no scenario calls the slice-writing pipeline. |
| `pyproject.toml` dependencies `starlette`, `uvicorn`, dev `httpx2` | delete | Imported only by `serve/`, `cli/serve.py` and the server tests. `pydantic` and `pyyaml` stay until 222 and 223 show whether the kept code still needs them (the answering settings and `plan.py` use pydantic; `project_config.py` is the only YAML reader). |
| `pyproject.toml` `description`, pytest `addopts` | rework | Set-up: the description ("Orchestration runner...") is stale. Drop `--ignore=tests/load` with the load tests; keep `--ignore=tests/live`. `.github/workflows/ci.yml` also has a "Load tests" step to remove. |
| Other packaged files | none | No non-Python file under `src/` other than the 16 SQL files and the two YAML files. |

## Dependencies of kept code

Each entry names one replacement: a new-store table or field (222), an operation (223 or 224), a value the caller passes in, or nothing with the reason. "NOT COVERED" marks a replacement the architecture lacks; those are also listed under Differences from the architecture and are not designed here.

### The four things the new design removes

| Removed | Where kept answering code touches it | Replacement |
|---|---|---|
| **Nodes** | `sources.py` (`_slice_ref`, `slice_label`, `pm_precedent` read `Node`, `parent_id`, `NodeKind`, `cf.index`); `launch.py` `prepare_launch` (`get_node(record.node_id)`); `passages.py` (`PmAnswer.node_id`, `assemble(question_node_id=...)`); the `question_records.node_id` column | Slice label and index on the question record; slice from the paused run's parameters; initiative index from Context Forge in the recorded checkout. |
| **Journal entries** | `finish.py` (entry id, `PARAM_SCRATCH`, `PARAM_RUN_ID`, `journal_resolve`); `launch.py` (`begin_answering` inserts an `sq_answer` entry, log path from the entry id); `store/answering.py` (journal insert); `question_records.source_entry_id` and `answering_entry_id` | The answering run id and log path as fields on the claim; no journal. |
| **Blocked states** | `store/questions.py` (`record_question` writes a human block), `answer_submission.py` (`_block_is_resolved`, resolution slot); `question_records.blocked_state_id` | The question's own state (claimed, answered, waiting on the PM, resumed, refused, not delivered) and `handle_pause` / `answer` (223). |
| **The tick loop** | `stage.py` (the only caller of `launch_answering` and `finish_answering`, from `tick.py`); every `TickBudget` parameter in `source_reads.py`, `sources.py`, `launch.py`; `probes.py` imports `answering_pipeline_path` and `factory.py` calls it at resident start | `handle_pause` calls the answering code directly in one short process; the budget goes because each call has its own timeout. |

### Answering and store

| Unit | Relies on (being deleted) | Replacement |
|---|---|---|
| `decide.py` `RunSummary.of` | `runner/observed.py` `Finished` variants from the tick's run observer | Value passed in: built from the `sq runs wait --json` result (223). |
| `decide.py`, `launch.py` | `cut_to_bound` in `runner/ingest/outcome.py`; `STDERR_TAIL_LIMIT_BYTES` in `runner/launch.py` | Nothing: pure helpers that move with the code. 221 must relocate them before deleting `ingest/`. |
| `gate.py`, `finish.py`, `launch.py`, `sources.py` | `AnswererSettings` in `runner/project_config.py` (per-project YAML keyed on an Amoeba project id) | 222: user-level config (models, cost cap, answer limit, authorize list) and per-member settings (rule paths). `max_concurrent_runs` is dropped; nothing enforces it. |
| `gate.py`, `decide.py`, `finish.py`, `launch.py` | `DeclineReason`, `AnsweringEvidence`, `GateRefusal`, `QuestionRecord` in `store/question_models.py` | 222 baseline models, re-homed. |
| `evaluate_gate` (called by the store under the write lock) | `COUNT_ANSWERER_ANSWERS_IN_RUN` keyed on project and run id | 222 query keyed on member and run id. The semantics (automatic answers only) already match. |
| `finish.py` | `JournalEntry`, `question_for_answering_entry`, `journal_resolve`, `answering_entry_id` | 222 field: the answering run id on the claim. "No longer waiting on this run" becomes a state and run-id compare; the journal resolve goes. |
| `finish.py` `_read_replies` | Scratch directory path read from the journal entry's parameters | NOT COVERED: where the scratch directory is recorded or derived. A later explicit call needs it to read a finished run's `answer.json` and `check.json`. |
| `finish.py` | `submit_answer` also fills a resolution slot | 223: `handle_pause` records the answer, then resumes. The slot goes. |
| `launch.py` `prepare_launch` | `get_node`, `node.cf.project`, `latest_cf_snapshots`, `slice_label(node)` | Value passed in: slice from the run's parameters, checkout recorded on the claim, Context Forge project read from that checkout. |
| `launch.py` | `LaunchTracker`, `TickBudget`, `begin_answering`, `log_paths(supervisor_dir, entry.id)` | Nothing for tracker and budget. 222 field for a log path on the record. |
| `sources.py` `pm_precedent`, `_slice_ref` | `store.get_node` per answered question; `NodeKind.INITIATIVE` | 222: slice label stored on the record; precedent scoped per member. Initiative index from Context Forge in the checkout. |
| `sources.py` | `resolve_checkout(CFSnapshot, slice_index)` in `upstream/context_forge/checkout.py`, `latest_cf_snapshots`, `cf_links` | Value passed in: `handle_pause` records the checkout from the run's working directory (Squadron #303, now closed). The snapshot tables need no replacement. |
| `sources.py` | `read_target` in `runner/dispatch/checkout_reads.py`; `cf_argv`, `config_get_command` in `runner/lifecycle/plan_read.py` | Nothing: move `read_config`, `read_target` and the three Context Forge pieces into one small module and drop the budget. Its `DEFAULT_TARGET_BRANCH = "main"` is Context Forge's own documented default (an empty `git.integration_branch` means `main`); it stays as one named constant, moved by 221 and covered by tests in 223. |
| `source_reads.py`, `git_read.py` | `TickBudget.allows_call()` | Nothing: one short process, each call under its own timeout. |
| `passages.py` | `PmAnswer.node_id` | Slice label or index on the question record (222), passed by the caller. |
| `inputs.py` | Blank slice label rejected | Allow "no slice" (the architecture requires a run with no slice to be answered). |
| `answering.yaml` | Authorize list hard-coded in both prompts | NOT COVERED: how a per-member list reaches a static pipeline file, and whether it is the same setting as `reserved_terms`. |
| Answering run started by the pause hook | `inputs.py` and the argv build have no hook opt-out | NOT COVERED by existing code: the answering run is always launched with the hook's opt-out; the exact flag comes from Squadron #302 (closed) and is a 223 task. |
| `finish.py`, `stage.py` | `QuestionInvariantError` defined in `settle.py` | New home in the questions module. |
| `store/questions.py`, `answering.py`, `answer_submission.py`, `_program_writer.py` | `BEGIN_IMMEDIATE` in `store/sql_inbox.py` | Move to `store/sql.py`. |
| `store/mapping_questions.py`, `mapping_program.py` | `decode_mapping`, `decode_timestamp` in `mapping_journal.py` | Move to `store/row_values.py`. |
| `store/questions.py` | `BlockWriter` base class (and so nodes); it is also a base of `BlockingOperations` | Nothing for the block parts; keep a generic begin-immediate helper. |
| `store/question_models.py`, `answering.py` | `JournalEntry`, `JournalOperations`, `CommandKind` | Plain values and a claim row. |
| `store/answer_submission.py` | `_submission_writer`, `inbox_models` (`SubmissionKind.RESOLUTION`), `map_blocked_state` | 223: `answer` writes the answer on the question record directly. |
| `question_records` schema (013 to 015) | `node_id NOT NULL REFERENCES nodes`, `source_entry_id UNIQUE REFERENCES command_journal`, `blocked_state_id`, `answering_entry_id`, and triggers writing the `changes` feed | 222 baseline: unique on run id and `paused_at`, no node, no feed triggers. The evidence fields (`reserved_term`, `proposed_answer`, `cited_passages`, `check_verdict`, `check_reason`, `decline_detail`, `passage_index`, `dropped_pm_answers`, `source_commit`) carry over. |
| Question record, resume lifecycle | No field for resumed, refused or not delivered, or for the resume log file | NOT COVERED by existing code: 222 adds them (the architecture describes the states). |
| `store/program_*`, `mapping_program.py`, `sql_program.py` | `requests_initiative`, `consumption_overrides`, `program_submissions`; `consumed` on the member; member key an Amoeba project id mapped to Context Forge through `cf_links` | 222 baseline: `consumed` on the dependency pair; member id is the Context Forge project; dependency pairs, releases, per-member settings and the PM marker are all new. |
| Program `concept_member`, `concept_path` | Not in the architecture's baseline list | NOT COVERED: the 182 concept passage needs them, or another way to find the concept. |
| `store/migrations.py` | No guard between two processes opening a new store: both read version 0 and the second fails with "table already exists" | 222: `BEGIN IMMEDIATE` plus a version re-read inside it, or a create-if-missing guard. |
| `store/paths.py` | Also reads `XDG_CONFIG_HOME`, a second location source | 222 decides whether to keep it; the architecture allows one test env var and nothing else. |

### Runner, process, upstream, program, cli

Nodes, journal entries, blocked states and the tick appear in the table at the top of this section. Entries here add what the runner and process units rely on.

| Unit | Relies on (being deleted) | Replacement |
|---|---|---|
| `runner/launch.py` kept parts | `JournalEntry`, `PARAM_CHECKOUT`, `PARAM_RUN_ID`, `launch(entry, ...)` | Values passed in by the caller: checkout, run id, pipeline, params. |
| `runner/launch.py` `spawn` | `log_paths(supervisor_dir, entry.id)` | 222 field: the log file named on the question record, as the architecture's resume step requires. |
| `runner/launch.py` | `LaunchTracker` (in-memory children reaped each tick) | Nothing: `handle_pause` waits on its own answering child, and the detached resume needs no reaping. |
| `resolutions/confirm.py` | `resumed_from_entry` reading `JournalEntry.result["outcome_document"]` through `supervise.recorded_document` | 222: `paused_at` and the checkpoint on the question record, passed into `has_left` and `is_at`. |
| `resolutions/confirm.py` | A tracked child's exit code and `past_grace` from `issued_at` | Value passed in: 223 starts the child itself and knows its exit code and start time. The architecture's "wait briefly for `running`" step is not in `resume_progress`; 223 builds it. |
| `observed.py` kept values | `ObservedRun.run: InFlightRun`, an unresolved journal entry | Nothing: drop the wrappers; the `Finished` variants stay as plain values. |
| `git_read.py`, `checkout_reads.py` | `TickBudget` | Nothing (see the tick row above). |
| `project_config.py` | Per-project YAML keyed on an Amoeba project id; the `answerer:` section's presence turns the answerer on | `set_up` per-member settings and the user-level config (222). NOT COVERED: how a member opts in or out of answering besides program membership. |
| `process/sq_outcome.py` | `--timeout 0` hard-coded in `RUNS_WAIT_FLAGS`; the tick re-polls | NOT COVERED: whether `handle_pause` loops `poll_run` or passes a real timeout. A 223 choice. |
| `process/sq_outcome.py` | `RunOutcomeDocument` has no `execution_mode`, run parameters or working directory, all of which `handle_pause` needs (steps 2 and 4, and the recorded checkout) | NOT COVERED: whether `sq runs wait --json` emits them. Checked 20261108 against `sq` 0.24.24: `sq runs list --json` (Squadron #303, shipped) gives `run_id`, `pipeline`, `status`, `working_directory` and `checkpoint` only (older runs show a null working directory), so it has no parameters or `execution_mode` either. `sq runs wait --json` documents status, checkpoint and failure only. Where the slice and `execution_mode` come from is open; `RunOutcomeDocument` or a new reader must grow, and that is a 223 task. |
| `process/sq_outcome.py` | `RunReview` and `reviews`, used only by deleted `ingest/reviews.py` | Nothing: remove. |
| `process/sq_outcome.py` | `SQ_EXECUTABLE` is defined here but imported by `runner/launch.py`, `resolutions/argv.py` and `probes.py`; the package name `process` stops describing it | The surviving `sq` and `cf` helpers need one home; 221 or 223 picks it. |
| `process/settings.py` kept fields | A frozen dataclass with hard-coded numeric defaults and `Path.home()` paths | User-level config file (architecture, "Where things live"), with no defaults in code. |
| Resume run-lock handling | No module reads or reasons about Squadron's run lock; `resume_progress` calls exit code 2 `REFUSED` | NOT COVERED: whether a held lock exits 2 is unverified. 223 checks it against the real `sq`. |
| `upstream/context_forge/plan.py` | Nothing deleted, but it exists for the plan sync | Operation in 223: the slice's initiative index, read through `cf list` in the checkout. |
| `program/members.py` | `Store.cf_links`, `latest_cf_snapshots`, `member.requests_initiative`, per-project store files | The member is the Context Forge project for the working directory (222, `set_up`). NOT COVERED: whether `status` reports member readability at all, and what a member's checkout is when all worktrees are one member. |
| `cli/main.py` | `process.errors` and `process.host` types, `InboxSubmitError`, `VerdictNotFoundError`, `UpstreamShapeError`, `VERSION` from the PID file | The new store's own error type (222); nothing for the rest. NOT COVERED: the CLI's argument shapes, output format and exit-code table for the eight operations; 223 and 224 define them. |
| `scripts/answerer_walkthrough.py`, `docs/answerer-walkthrough.md` | `amoeba start`, `AMOEBA_STORE_DIR`, `projects.yaml`, `inspect`, `submit` | `set_up`, the user-level config, `handle_pause`, `answer`, `status`. |

## Slice 182

**Verdict: reuse parts.** Do not merge the branch; port the take group by copy or cherry-pick when 223 builds the context step.

Branch `182-slice.program-concept-as-a-source`, 11 commits (`6c2499b` to `a2619fb`), 28 files, +2,295 and -197 lines, about 55% of it tests. Merge-base is `1d00846` ("mark slice 181 complete"); main is 37 commits ahead, all docs only, so the base is old but no code moved. `git merge-tree` against main is clean today. It will not stay clean: 221 deletes `stage.py`, `launch.py`, `tick.py` and `tenant.py` and moves or reshapes the rest of `runner/answering/`, which turns a late merge into delete-modify conflicts and carries code that imports deleted modules (`Member`, `Program`, `ProgramStore`, `QuestionRecord`, `JournalEntry`, `read_member`, `TickBudget`, `checkout_reads.read_target`, `project_config`).

Commit `e0a4615` ("pass the tick's program to the answering launch") adds `LaunchContext.program`, changes `AnsweringStage.run(budget, faults, program)` and builds a `ProgramContext` from the tick's `ProgramStage` result and `ProgramStore.members`; `ProjectTick` takes a `program_store`. Every hook in it is tick- or store-shaped, so all of it is rewrite; the one lasting idea is `assemble_sources(..., program=)`.

### Take (works on the new base once imports are re-pointed)

| File | Why |
|---|---|
| `src/amoeba/runner/answering/answering.yaml` | Both prompts name the kinds `program_concept` and `program_members`, identical in both steps. Moves with the file in 221. |
| `src/amoeba/runner/answering/passages.py` | Adds `PROGRAM_CONCEPT` and `PROGRAM_MEMBERS` kinds, `Passage.member`, `SourceFile.member`, member-line rendering and `assemble(program_sources=)`. Its only deleted-code import is `GLOB_WILDCARD`, which 221 relocates anyway. |
| `src/amoeba/runner/answering/program_passages.py` | Pure, 75 lines: `ProgramSources`, `member_list_text`, `member_list_date`, marker constants. Re-point `Member` and `Program` to 222's types. |
| `src/amoeba/runner/answering/source_reads.py` | Public names for the git helpers (`GitReads`, `Listings`, `in_context`, `read_file`) and `member=None` on `SourceFile`. A pure rename. |
| `tests/runner/answering/test_passages.py` | The program-kind render and `assemble` tests. Re-point the `passage_refs` import. |
| `tests/runner/answering/test_pipeline_yaml.py` | Both steps name every kind with identical sentences. |
| `tests/runner/answering/test_program_passages.py` | Pure tests; re-point the store type imports. |
| `project-documents/user/tasks/182-tasks.program-concept-as-a-source.md` | Stays on the branch as history. It holds 182's decisions D1 to D7, which 223 cites: D3 (the asker's own pinned commit), D4 (member-list wording and markers), D5 (early size stop), D6 (visibility: no rules, plan or PM answers from other members). |

### Rewrite (the idea is wanted, the code is bound to deleted code)

| File | Why |
|---|---|
| `src/amoeba/runner/answering/program_sources.py` (227 lines) | The concept read is wanted. Keep the git logic: `_read_concept_file`, `_within_limit`, `without_path`, `_read_from_asker`, the `SourcesProblem` kinds. Replace `ProgramContext` (carries `store_dir` and a member tuple), `read_member`, `_read_target` and `TickBudget` with 223's context step: checkout from the claim, members from the store, the target read through the moved `read_target`. |
| `src/amoeba/runner/answering/sources.py` | The `assemble_sources(program=...)` hunk, `_project_files` and `_program_sources` budget the characters left after the project's own text and keep the concept once. Keyed to `Store`, `Node` and `TickBudget`. |
| `src/amoeba/runner/answering/launch.py` | The `program: ProgramContext | None` field and its pass-through. The launch is rebuilt in 223. |
| `src/amoeba/runner/answering/stage.py`, `src/amoeba/runner/tick.py`, `src/amoeba/runner/tenant.py` | The `_with_program` method, the `ProgramStage` result passed on, and `program_store=`: the e0a4615 wiring. Files deleted in 221; 223 builds the program context from the store instead. |
| `tests/runner/answering/program_rig.py`, `tests/runner/answering/test_program_rig.py` | The temporary git concept-repo fixtures are reusable; the rig imports `amoeba.program`, `project_store_path` and `TickBudget`. |
| `tests/runner/answering/test_program_sources.py` | About 20 concept-read cases (missing, unreadable, non-UTF-8, timeout, too large, call order, asker holds the concept). The assertions port; the call-count and budget cases need new shapes. |
| `tests/runner/answering/test_sources.py` (program section only) | The program-question render, concept-once, problem-as-value and visibility tests. The file is node-bound and a `delete` row, so its program assertions port into 223's new sources test. |
| `tests/load/test_program_passages_load.py` | One Context Forge call and four git calls whatever the size. It lives in `tests/load/`, a `delete` row, so it moves to `tests/runner/answering/` with the rewrite or goes with the directory. |
| `tests/live/answering/stage_harness.py` | A signature-only edit; the file waits on 223 (see Live tests). |

### Drop (the no-program path, and edits to code that is deleted)

| File or change | Why |
|---|---|
| `program: ProgramContext | None` optionality in `LaunchContext` and `assemble_sources` | A lone repo is a program of one, so the parameter is never optional. |
| Commit `6c2499b` entirely, and 182's D1 rule that nothing beyond the project's own reads is made | The baseline pin for a project in no program. Its tests: `test_baseline_a_project_in_no_program_launches_as_after_144`, `test_baseline_holds_with_no_program_store_and_with_an_unrelated_program`, `_forbid_program_reads`, `test_program_none_renders_the_hand_written_file_as_before`, `test_a_project_in_no_program_launches_with_no_context_and_no_members_read`, `test_no_program_sources_gives_the_set_as_before`, the `_Baseline` class and `_seed_baseline_answers`. |
| `tests/runner/answering/launch_rig.py`, `sources_assembly.py`, `test_launch_prepare.py`, `test_stage_observe.py`, `test_stage_pending.py`; `tests/runner/test_end_to_end_answering.py`, `test_tick_answering.py`, `tick_support.py` | Signature-only edits (`program=None`, `run(budget, faults, None)`, `program_store=`) and program-context launch cases in files that are `delete` rows. 223's new launch and context tests cover the same claims. |

**Gap in the branch:** slice 222 allows a program whose concept columns are both null, but `ProgramContext` requires `concept_member` to be a real member. The concept must be optional in the rewrite, and no branch test covers that case.

**What 223's context step reuses:** the passage kinds and rendering, `ProgramSources` and the member-list helpers, the prompt sentences, the concept git read with the asker-holds-concept shortcut, the concept-repo test fixtures, and 182's decisions D3 to D6. `passage_refs` already records the member list's source through `passage.source or question_id`.

Not read in full by the research: the program test bodies, the `answering.yaml` change beyond its diff, and 182's tasks-file diff. The sort rests on the full `src` diff and the full text of `program_passages.py` and `program_sources.py`.

## Live tests

Every file under `tests/live/answering/`. "Waits on 223" files are deleted in 221 and restored by 223 from the commit named; the restore hash is the last commit on main that touched the file. The live tests need `sq` 0.24.24 or later (tool-less steps on Claude models, Squadron #299, closed 20261108).

| File | Verdict | Decisive imports | Scenario A claim it covers | Restore commit |
|---|---|---|---|---|
| `__init__.py` | stays | none | Package marker. | n/a |
| `conftest.py` | stays | helpers `live_environment`, `live_settings`, `live/answering/harness.py` | Builds one throwaway Context Forge project and gives `sq` a whitelisted environment. | n/a |
| `harness.py` | stays | `amoeba.process` (`RunOutcome`, `RunOutcomeDocument`), `runner.answering.inputs`; via `live_harness`: `process.SQ_EXECUTABLE`, `poll_run`, `pipeline_file`, `cf_call.OUTPUT_HEAD_CHARS`, `launch.mint_run_id` | Runs the real shipped `answering.yaml` through `sq run` in a scratch directory with real models. Stays only if those names keep their signatures (see below). | n/a |
| `question_tails.py` | stays | none (string constants) | Question wording shaped like Squadron's truncated tails; `test_live_tier_rules.py` checks each fits `QUESTION_TAIL_CHARS`. | n/a |
| `fixtures/question_tails.json` | stays | none | Ten real question tails from the slice 145 walkthrough, used by `test_question_tails_fixture.py` and a corpus for how `handle_pause` meets real wording. | n/a |
| `test_pipeline_run.py` | stays | `artifacts`, `inputs.QuestionInput`, `pipeline_file`, `harness` | Answer and check steps run tool-less on real models and write four parsable files; a hostile passage instruction produces no extra file; the check step's prompt holds the question, passages and answer but not the answer step's instruction, and neither prompt carries Squadron's project-rules block. | n/a |
| `test_precedence.py` | stays | `artifacts`, `inputs.QuestionInput`, `harness.passage` | The check enforces later-date precedence and per-slice PM-answer matching on real models (four cases). It tests the prompt wording in `answering.yaml`, so a prompt change affects its result, not its imports. | n/a |
| `stage_harness.py` | waits on 223 | `AnsweringStage`, `TickBudget`, `NodeContext`, `TickFaults`, `RunObserver`, `Node`, `Store`; helpers `question_harness`, `launch_rig`, `observe_support` | Drives the real answering stage and store with real models until a question settles. 223 replaces it with a `handle_pause` harness. | `ed6041a` |
| `test_answering_run.py` | waits on 223 | `stage_harness`; reads `store.blocked_state(...)`, `block.resolution.instructions`, `live.rig.node`, `other_slice(...)` | Four end-to-end cases: a plan-rules passage answers the question; a reworded question on the same slice is answered from the PM's earlier answer; the same meaning on another slice is answered from an all-slices PM answer; a slice whose answer differs is declined. The only tests of the whole path from a real pause to the record. | `ed6041a` |
| `test_sdk_refusal.py` | delete | `inputs`, `pipeline_file`, `live_settings.SDK_MODEL_VARIABLE`, `harness` | Asserted that a check step on an SDK-session alias is refused by Squadron's no-tools guard. With #299 closed, a tool-less step on a Claude alias now runs, which is what scenario A relies on and `test_pipeline_run.py` already covers; the refusal is Squadron's behavior, not an Amoeba claim. Also remove `SDK_MODEL_VARIABLE` from `live_settings.py`. | n/a |

Notes for 221 and 223:

- **Helpers the kept files need:** `tests/live_settings.py`, `live_environment.py`, `live_harness.py` and `process_containment.py`, and the root `tests/conftest.py`, which must be trimmed to `reap_orphans` because it imports the inbox and server rigs. `tests/live/conftest.py` only puts `tests/` on `sys.path`.
- **Names that must not change:** `amoeba.process` keeps `SQ_EXECUTABLE`, `RunOutcome`, `RunOutcomeDocument`, `PollFailure`, `RunPoll`, `poll_run` and `QUESTION_TAIL_CHARS`; `mint_run_id` keeps its signature; `prepare_scratch(directory, question, passages_markdown, max_cost_usd)` keeps its signature. The live tests always pass a slice, so allowing "no slice" in `render_question` does not break them.
- **Restoring from `ed6041a` brings back only the two files**, not `launch_rig.py`, `observe_support.py` or `question_harness.py`, which are deleted too. 223 treats them as a template to rewrite.
- **What no live test covers today:** the pause hook and its opt-out (`--no-pause-hook`, Squadron #302). The answering run must always pass the opt-out, so 223 needs a live case for it.
- **Selection:** `addopts` ignores `tests/live`, so `uv run pytest` skips them and `uv run pytest tests/live` runs them. Collection fails if `AMOEBA_LIVE_ANSWER_MODEL`, `AMOEBA_LIVE_CHECK_MODEL` or `AMOEBA_LIVE_MAX_COST_USD` is unset; there are no defaults and no skip. A provider key must be in the shell, and `sq` and `cf` must be on `PATH`.

## Move to Squadron

**None.** No unit is marked `squadron` and no issue was filed. Checked 20261108 against `gh issue list -R ecorkran/squadron --state open` (the full open list, #305 to #9) and `sq` 0.24.24.

Candidates considered and why none qualifies:

| Candidate | Outcome |
|---|---|
| Tool-less Claude steps, command started on pause, working directory in the run file, JSON from `sq runs list` | Already Squadron issues #299, #302 and #303, all closed 20261108 and present in 0.24.24. Squadron #192 ("`sq runs list --json` for out-of-process consumers") is still open although the feature now exists; that is Squadron's housekeeping, not an Amoeba item. |
| A command step in pipelines | Squadron #304, open and on hold. Amoeba depends on it only if agents skip the scenario B rule lines. |
| Pruning runs (`process/run_pruning.py`, `cli/prune.py`) | `sq runs prune` already exists. The Amoeba code depends on Amoeba owning the runs, so it is deleted. |
| Detached process start, bounded `cf` and `git` reads, run-id minting (`runner/launch.py`, `cf_call.py`, `git_read.py`) | Useful only to Amoeba; nothing a Squadron user would ask for. |
| The markdown passage cutter (`passages.py` `cut_passages`) | The only thing remotely general, and no Squadron user need exists. |
| Review parsing and verdict records (`upstream/squadron/`, `store/finding_identity.py`) | Serve only the deleted review ingest and are Amoeba-specific design. |
| A rolling-window cost cap | Squadron #242 already asks for one; Amoeba's own future-work item (spend cap per time window) can lean on it. |

## Differences from the architecture

The architecture is not edited here (slice scope); these are the places the verdicts differ from its Current State table and facts, and the replacements it does not cover.

### Against the Current State table

| Area | Architecture expected | Audit result |
|---|---|---|
| `upstream/` | Keep | **Delete, except `context_forge/plan.py` (rework).** `upstream/squadron/` is only review-output parsing for the deleted verdict store. `upstream/context_forge/` is snapshot, watch and node-plan code. The slice 221 plan line "the upstream readers stay" is wrong; a note was added to the 221 entry. |
| Where `sq` launch, poll and resume code lives | Not stated | `process/sq_outcome.py` (`sq runs wait --json`), `runner/launch.py` (`spawn`, argv, run ids), `runner/resolutions/argv.py` (resume argv) and `confirm.py` (checkpoint compare). These are the 223 base and sit in packages the table says mostly go. `process` is a poor name for what survives there. |
| `runner/` | Keep answering pipeline, passages, decision logic, answer screen; rewrite launching and polling | Agrees, with more named survivors outside `answering/`: `launch.spawn` and argv, `confirm.py`, `cf_call.py`, `git_read.py`, `read_target`, `observed.py` values, two fault enums, `cut_to_bound`, `AnswererSettings`, `pipeline_resource.py`. Everything else, including `stage.py`, `settle.py` and the tick-launched `launch_answering`, goes. |
| `store/` questions | "Keep questions and programs, re-keyed" | The question record is **new design, not a re-key.** Today it is keyed on a journal entry (`source_entry_id`), and no `paused_at` exists anywhere in the code. Every question and answer unit is rework or delete, and every store test of them is deleted. Nothing in `store/` survives as-is: 221 deletes the directory whole and 222 re-creates `connection.py` and `row_values.py` (their code is wanted, so they may be restored from the base commit). |
| `store/` single-writer | "The single-writer checks go" | The store has none (`store.py` says it does not enforce single-writer); the lock is `process/instance_lock.py`. The store already uses `BEGIN IMMEDIATE` and typed busy errors, which fit as-is. A real new risk instead: two processes opening a fresh store can both read version 0 and the second fails (see Dependencies). |
| `process/` | Goes, apart from reading Squadron's output | Agrees: `sq_outcome.py` stays; `settings.py` and `errors.py` keep a few fields; `observers/sq_runs.py` goes because `sq runs list --json` now gives the working directory. |
| `cli/` | Replaced by the operations | `cli/main.py` and `__init__.py` are reworked (the entry point and boundary handler stay); every command file goes. |
| `serve/`, `inbox/`, `feed/` | Goes (`feed/` goes with the change feed) | Agrees: all three are deleted whole. |
| `inspection/` | Mostly replaced by `status` and `decisions` | All deleted; `inspection/questions.py` is only a column reference for 224. |
| `program/` | Kept and reworked | Rework, effectively a rewrite: only the `Readable` and `Unreadable` vocabulary survives, and it is a delete if 224 does not want member readability. |
| Live answering tests | "Stay and become the check on scenario A" | Three stay unchanged (`test_pipeline_run.py`, `test_precedence.py`, `question_tails.py` and its fixture); two wait on 223 (`stage_harness.py`, `test_answering_run.py`); `test_sdk_refusal.py` is deleted. |
| Squadron changes table | #299, #302, #303 open | All three are closed and in `sq` 0.24.24; #304 is open. The architecture's facts were read from 0.24.23. |

### Verdicts changed while cutting (slice 221, D1)

Each row above marked "Changed from `rework` in 221" has its reason there. Beyond those rows, the cut did these things the audit left open:

| Unit | What 221 did |
|---|---|
| `answering/launch.py` | Kept only `passage_refs` and the scratch-directory helpers (`prepare_scratch_directory`, `discard_scratch`, public names for the old private ones). `prepare_launch`, the argv and params build, and `ANSWERING_DIRNAME` went: 223 builds them against the new record. |
| `answering/sources.py` | `assemble_sources` takes the checkout, the Context Forge project id, a `SliceRef`, the slice label and a tuple of `PmAnswer`. `slice_label`, `pm_precedent` and `_slice_ref` went (they read nodes and the store). |
| `answering/passages.py` | `PmAnswer.node_id` is gone; `assemble(question_slice_label=...)` orders same-slice answers by the label. |
| `upstream/git_read.py` | The allowlist is `show` and `log`; `status` and `merge-base` went with their builders and parsers. |
| `upstream/context_forge/plan.py` | The `status` field and every status type went with `reported_complete`; `extra="ignore"` still accepts the key. |
| Test doubles | `cf_stub` lost the `cf status --json` probe; `sq_stub` lost `runs prune` and accepts any `--timeout` value for `runs wait`; `sq_stub_scripts` lost the review scripts. |
| Fixtures | Removed the review captures in `sq_outcomes/`, `cf/projects.json` and `cf/cf_get_amoeba.json`, and the `git/`, `sq_reviews/`, `sq_runs/` and `slice_writing/` sets. |
| `tests/conftest.py` | Only `pytest_sessionstart` (orphan reaping) is left. |

### Replacements the architecture does not cover

Not designed here; each is raised for the slice named.

| Gap | Slice |
|---|---|
| Where an answering run's scratch directory is recorded or derived. A later explicit call needs it to read `answer.json` and `check.json` of a finished run. | 222 or 223 |
| How a per-member authorize list reaches the static `answering.yaml` prompts, and whether it is the same setting as `reserved_terms`. | 222 and 223 |
| The hook opt-out flag for the answering run, and a live case for it. The shape comes from Squadron #302. | 223 |
| Record fields for the resume outcome (resumed, refused, not delivered) and the resume log file. | 222 |
| `concept_member` and `concept_path` on the program, which the 182 concept passage needs but the architecture's baseline list omits; and the concept must be optional (222 allows a program with none). | 222 and 223 |
| How a member opts in or out of answering besides program membership (today the presence of an `answerer:` section). | 222 |
| Whether `handle_pause` loops `poll_run` or passes a real timeout; `poll_run` hard-codes `--timeout 0`. | 223 |
| Where `handle_pause` gets the run's slice and `execution_mode`. Neither `sq runs list --json` nor `sq runs wait --json` documents them. | 223 |
| Whether a held run lock makes `sq run --resume` exit 2, which `resume_progress` reads as refused. Unverified. | 223 |
| Whether `status` reports member readability, and what a member's checkout is when all worktrees are one member. | 224 |
| The CLI's argument shapes, output format and exit-code table for the eight operations. | 223 and 224 |
| A fresh-store creation race guard (`BEGIN IMMEDIATE` plus a version re-read). | 222 |
| Whether `XDG_CONFIG_HOME` stays as a location source; the architecture allows one env var and nothing else. | 222 |
| A run with no slice must be answered; `render_question` rejects a blank slice label today. | 223 |
| `DEFAULT_TARGET_BRANCH = "main"` in `checkout_reads.py` looks like a magic default, but it is Context Forge's documented empty-value meaning. Settled: one named constant, moved by 221, tested in 223 (task 4.6). A failed `cf config get` is still a typed error. | 221 and 223 |
| The surviving `sq` and `cf` helpers need one home outside `process/`. | 221 or 223 |

### Ordering constraints for 221

Kept code imports these from modules that go, so they must move first or in the same commit: `cut_to_bound` (`runner/ingest/outcome.py`), `STDERR_TAIL_LIMIT_BYTES` (`runner/launch.py`), `QuestionInvariantError` (`settle.py`), `BEGIN_IMMEDIATE` (`sql_inbox.py`), `decode_mapping` and `decode_timestamp` (`mapping_journal.py`), `read_config`, `read_target` and the `cf_argv` pieces (`dispatch/checkout_reads.py`, `lifecycle/plan_read.py`), `SQ_EXECUTABLE` (`process/sq_outcome.py`), `LaunchFailure` and `ResumeFailure` (`faults.py`), `Finished` values (`observed.py`). Test helpers split the same way: `observe_support.py`, `tests/conftest.py`, `sq_stub_scripts.py`, `sources_repo.py`. The `store_path` name goes with `test_store_safety.py`'s forbidden-name set. `pyproject.toml` loses `starlette`, `uvicorn`, `httpx2`, the schema artifacts and the slice-writing artifact, and CI loses its load-test step.

### Slice 182 files that sit in `delete` rows

Restated from the Slice 182 section: `stage.py`, `tick.py`, `tenant.py`, `launch.py` (the `LaunchContext` and `launch_answering` parts), `tests/runner/answering/launch_rig.py`, `sources_assembly.py`, `test_launch_prepare.py`, `test_sources.py`, `test_stage_observe.py`, `test_stage_pending.py`, `tests/runner/test_end_to_end_answering.py`, `test_tick_answering.py`, `tick_support.py` and `tests/load/test_program_passages_load.py`. The branch edits to them are signature-only or program-context wiring; the wanted ideas (program context reaching the launch, the program-question render and visibility tests, the one-call load shape) are in the rewrite group and port to 223's new code and tests, so no verdict changes.
