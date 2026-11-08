---
docType: analysis
project: amoeba
topic: code-audit
dateCreated: 20261108
dateUpdated: 20261108
status: in_progress
---

# Analysis: Code Audit

Slice design: `user/slices/220-slice.code-audit.md`. Architecture: `user/architecture/220-arch.program-tool.md`.

## Summary

TODO: what stays, the slice 182 verdict, issues filed.

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
| `finish.py` | rework | Scenario A: settling a finished answering run (decide, then submit through the gate or decline) stays, including discard-if-the-PM-answered-first. It is keyed on journal entries today. |
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
| `connection.py` | keep | Set-up: opens with WAL, busy timeout, read-only mode and typed errors, taking package and version as arguments. |
| `migrations.py` | rework | Set-up: the version stamp and runner stay for one baseline package; the program migration line goes and the expected version becomes 1. Needs a race guard (see Differences). |
| `paths.py` | rework | Set-up: keep `store_dir`, the `AMOEBA_STORE_DIR` test override, the path validators and `GLOB_WILDCARD`. Delete `store_path`, `project_store_path`, `program_dir`, `program_store_path`, `STORE_CREATING_SUFFIX`, `validate_project_id`. |
| `_base.py` | rework | Set-up, A: keep `StatementRunner`, `now`, `isoformat`, `new_id`; drop the node and message lookups. |
| `sql.py` | rework | Set-up: keep the busy timeout, PRAGMAs and `schema_meta` statements; drop node and blocked statements; add `BEGIN_IMMEDIATE`. |
| `models.py` | rework | Set-up, A: keep the `StoreError` family, `UnknownVocabularyValueError` and `QuestionNotFoundError`; the rest goes with nodes. |
| `row_values.py` | keep | Set-up, A: typed column reads used by the question and program mappers. |
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

TODO: section 3.

### `scripts/` and `docs/`

TODO: section 3.

### Packaged resources

TODO: section 3.

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
| `sources.py` | `read_target` in `runner/dispatch/checkout_reads.py`; `cf_argv`, `config_get_command` in `runner/lifecycle/plan_read.py` | Nothing: move `read_config`, `read_target` and the three Context Forge pieces into one small module and drop the budget. Its `DEFAULT_TARGET_BRANCH = "main"` is a magic default; 221 centralizes it or fails explicitly. |
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

TODO: verdict and the changed files sorted into take, rewrite, drop.

## Live tests

TODO: each file under `tests/live/answering/`.

## Move to Squadron

TODO: each item with its issue link.

## Differences from the architecture

TODO: each place the verdicts differ from the Current State table.
