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

### `src/amoeba/runner/` (other than `answering/`) and `src/amoeba/process/`

TODO: section 2.

### `src/amoeba/upstream/`, `program/`, `cli/`, `inspection/`, `serve/`, `inbox/`, `feed/`

TODO: section 2.

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

TODO: section 2.

## Slice 182

TODO: verdict and the changed files sorted into take, rewrite, drop.

## Live tests

TODO: each file under `tests/live/answering/`.

## Move to Squadron

TODO: each item with its issue link.

## Differences from the architecture

TODO: each place the verdicts differ from the Current State table.
