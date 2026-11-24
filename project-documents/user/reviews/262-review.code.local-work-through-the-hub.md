---
docType: review
layer: project
reviewType: code
slice: local-work-through-the-hub
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [general.md, python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS  # resolved 20261124, see Resolution
verdictSource: stated
sourceDocument: project-documents/user/slices/262-slice.local-work-through-the-hub.md
aiModel: minimax/minimax-m3.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261124
dateUpdated: 20261124
reviewedSha: cd44ea06906538a7346f7760213ce8088382752e
reviewedBlob: e6c1e7352e57a0a11b50f16f4c5184626a2d729c
reviewedBlobCurrent: true
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
injected:
  - key: conventions
    path: "AGENTS.md"
    chars: 24525
    sha256: 2387512002bb2a73aa247bc36bc98d7162c5b5110ded41f56319d098d282ddbc
    whole: true
filesRead:
  - "src/amoeba/store/sql_local_work.py"
  - "src/amoeba/store/schema/013_local_work.sql"
  - "src/amoeba/store/work.py"
  - "src/amoeba/wiring.py"
  - "src/amoeba/operations/work_start.py"
  - "src/amoeba/operations/claim_waiting.py"
  - "src/amoeba/hub/call_work.py"
  - "src/amoeba/operations/deps.py"
  - "src/amoeba/operations/steps/work.py"
  - "src/amoeba/operations/steps/models_work.py"
  - "src/amoeba/operations/steps/dispatch.py"
  - "src/amoeba/operations/steps/models.py"
  - "src/amoeba/store/wakes.py"
  - "src/amoeba/store/answers.py"
  - "src/amoeba/store/held_questions.py"
  - "src/amoeba/store/vocabulary.py"
  - "src/amoeba/store/sql_held.py"
  - "src/amoeba/store/sql_wakes.py"
  - "src/amoeba/store/machines.py"
  - "src/amoeba/store/machine_removal.py"
  - "src/amoeba/wire/protocol.py"
  - "src/amoeba/wire/times.py"
  - "src/amoeba/hub/calls.py"
  - "src/amoeba/client/call.py"
  - "src/amoeba/cli/commands.py"
  - "src/amoeba/cli/hub_commands.py"
  - "src/amoeba/cli/parser.py"
  - "src/amoeba/cli/main.py"
  - "src/amoeba/cli/render/messages.py"
  - "src/amoeba/cli/render/simple.py"
  - "src/amoeba/cli/render/waiting.py"
  - "src/amoeba/cli/render/waking.py"
  - "src/amoeba/operations/wake_start.py"
  - "src/amoeba/operations/wake_run.py"
  - "src/amoeba/operations/wake_status.py"
  - "src/amoeba/operations/resume_run.py"
  - "src/amoeba/operations/steps/limits.py"
  - "src/amoeba/operations/steps/context.py"
  - "src/amoeba/operations/steps/resume.py"
  - "src/amoeba/operations/store_steps.py"
  - "src/amoeba/wiring_steps.py"
  - "src/amoeba/wiring_door.py"
  - "src/amoeba/wiring_gather.py"
  - "src/amoeba/hub/admin.py"
  - "src/amoeba/store/migrations.py"
  - "src/amoeba/store/question_rows.py"
  - "src/amoeba/store/sql.py"
  - "src/amoeba/answering/values.py"
  - "src/amoeba/operations/answer.py"
  - "src/amoeba/operations/pause_class.py"
  - "src/amoeba/operations/pause_eligibility.py"
  - "src/amoeba/operations/pause_existing.py"
  - "src/amoeba/operations/pause_held.py"
  - "src/amoeba/store/questions.py"
  - "src/amoeba/store/question_closing.py"
  - "src/amoeba/operations/pause_claim.py"
  - "src/amoeba/operations/errors.py"
  - "src/amoeba/store/store.py"
  - "src/amoeba/operations/served.py"
searches:
  - "list_files * in ."
  - "list_files * in src/amoeba"
diffTruncated: true
diffCutFiles:
  - "scripts/update_live.py"
  - "src/amoeba/answering/decide.py"
  - "src/amoeba/answering/values.py"
  - "src/amoeba/cli/commands.py"
  - "src/amoeba/cli/hub_commands.py"
  - "src/amoeba/cli/main.py"
  - "src/amoeba/cli/parser.py"
  - "src/amoeba/cli/render/messages.py"
  - "src/amoeba/cli/render/simple.py"
  - "src/amoeba/cli/render/waiting.py"
  - "src/amoeba/cli/render/waking.py"
  - "src/amoeba/cli/resume_command.py"
  - "src/amoeba/cli/wake_command.py"
  - "src/amoeba/client/call.py"
  - "src/amoeba/hub/admin.py"
  - "src/amoeba/hub/call_work.py"
  - "src/amoeba/hub/calls.py"
  - "src/amoeba/operations/add_register.py"
  - "src/amoeba/operations/answer.py"
  - "src/amoeba/operations/answering_settle.py"
  - "src/amoeba/operations/claim_waiting.py"
  - "src/amoeba/operations/deps.py"
  - "src/amoeba/operations/handle_pause.py"
  - "src/amoeba/operations/list_view.py"
  - "src/amoeba/operations/message_results.py"
  - "src/amoeba/operations/pause_claim.py"
  - "src/amoeba/operations/pause_class.py"
  - "src/amoeba/operations/pause_context.py"
  - "src/amoeba/operations/pause_eligibility.py"
  - "src/amoeba/operations/pause_existing.py"
  - "src/amoeba/operations/pause_held.py"
  - "src/amoeba/operations/pause_models.py"
  - "src/amoeba/operations/pause_observed.py"
  - "src/amoeba/operations/pause_results.py"
  - "src/amoeba/operations/processes.py"
  - "src/amoeba/operations/program_sources.py"
  - "src/amoeba/operations/prune.py"
  - "src/amoeba/operations/prune_models.py"
  - "src/amoeba/operations/question_judge.py"
  - "src/amoeba/operations/question_sweep.py"
  - "src/amoeba/operations/question_sweep_scope.py"
  - "src/amoeba/operations/request_release.py"
  - "src/amoeba/operations/resume.py"
  - "src/amoeba/operations/resume_attempt.py"
  - "src/amoeba/operations/resume_run.py"
  - "src/amoeba/operations/resume_timing.py"
  - "src/amoeba/operations/run_gather.py"
  - "src/amoeba/operations/runs_document.py"
  - "src/amoeba/operations/send.py"
  - "src/amoeba/operations/send_write.py"
  - "src/amoeba/operations/served.py"
  - "src/amoeba/operations/served_runners.py"
  - "src/amoeba/operations/served_types.py"
  - "src/amoeba/operations/state_move.py"
  - "src/amoeba/operations/status.py"
  - "src/amoeba/operations/status_local.py"
  - "src/amoeba/operations/status_models.py"
  - "src/amoeba/operations/status_runs.py"
  - "src/amoeba/operations/status_waiting.py"
  - "src/amoeba/operations/steps/__init__.py"
  - "src/amoeba/operations/steps/begin.py"
  - "src/amoeba/operations/steps/context.py"
  - "src/amoeba/operations/steps/dispatch.py"
  - "src/amoeba/operations/steps/limits.py"
  - "src/amoeba/operations/steps/model_base.py"
  - "src/amoeba/operations/steps/models.py"
  - "src/amoeba/operations/steps/models_pause.py"
  - "src/amoeba/operations/steps/models_resume.py"
  - "src/amoeba/operations/steps/models_runs.py"
  - "src/amoeba/operations/steps/models_wake.py"
  - "src/amoeba/operations/steps/models_work.py"
  - "src/amoeba/operations/steps/open_runs.py"
  - "src/amoeba/operations/steps/pause.py"
  - "src/amoeba/operations/steps/resume.py"
  - "src/amoeba/operations/steps/settle.py"
  - "src/amoeba/operations/steps/sources.py"
  - "src/amoeba/operations/steps/wake.py"
  - "src/amoeba/operations/steps/work.py"
  - "src/amoeba/operations/store_steps.py"
  - "src/amoeba/operations/wake.py"
  - "src/amoeba/operations/wake_door.py"
  - "src/amoeba/operations/wake_run.py"
  - "src/amoeba/operations/wake_start.py"
  - "src/amoeba/operations/wake_status.py"
  - "src/amoeba/operations/work_start.py"
  - "src/amoeba/store/answers.py"
  - "src/amoeba/store/held_questions.py"
  - "src/amoeba/store/machine_removal.py"
  - "src/amoeba/store/machines.py"
  - "src/amoeba/store/migrations.py"
  - "src/amoeba/store/models.py"
  - "src/amoeba/store/question_closing.py"
  - "src/amoeba/store/question_rows.py"
  - "src/amoeba/store/questions.py"
  - "src/amoeba/store/schema/013_local_work.sql"
  - "src/amoeba/store/sql.py"
  - "src/amoeba/store/sql_held.py"
  - "src/amoeba/store/sql_local_work.py"
  - "src/amoeba/store/sql_machines.py"
  - "src/amoeba/store/sql_wakes.py"
  - "src/amoeba/store/vocabulary.py"
  - "src/amoeba/store/wakes.py"
  - "src/amoeba/store/work.py"
  - "src/amoeba/upstream/squadron/checkpoint_kind.py"
  - "src/amoeba/upstream/squadron/run_outcome.py"
  - "src/amoeba/wire/protocol.py"
  - "src/amoeba/wire/times.py"
  - "src/amoeba/wiring.py"
  - "src/amoeba/wiring_door.py"
  - "src/amoeba/wiring_gather.py"
  - "src/amoeba/wiring_pause.py"
  - "src/amoeba/wiring_release.py"
  - "src/amoeba/wiring_steps.py"
  - "tests/cli/test_hold_release_cli.py"
  - "tests/cli/test_legacy_move_cli.py"
  - "tests/hub/call_support.py"
  - "tests/hub/in_process_hub.py"
  - "tests/hub/test_across_machines.py"
  - "tests/hub/test_app.py"
  - "tests/hub/test_clients_fixture.py"
  - "tests/hub/test_door_client.py"
  - "tests/hub/test_door_faults.py"
  - "tests/hub/test_door_operations.py"
  - "tests/hub/test_door_steps.py"
  - "tests/hub/test_handle_call.py"
  - "tests/hub/test_join.py"
  - "tests/hub/test_joined_entry_points.py"
  - "tests/hub/test_rm_machine_work.py"
  - "tests/hub/test_step_calls.py"
  - "tests/hub/test_two_machines.py"
  - "tests/hub/two_homes.py"
  - "tests/hub_fixture.py"
  - "tests/live/conftest.py"
  - "tests/live/hold/conftest.py"
  - "tests/live/hold/split.py"
  - "tests/live/hold/test_hold_split_live.py"
  - "tests/live/machines.py"
  - "tests/live/messaging/test_two_machines_live.py"
  - "tests/live/pause/harness.py"
  - "tests/live/waking/conftest.py"
  - "tests/live/waking/split.py"
  - "tests/live/waking/test_waking_split_live.py"
  - "tests/live/waking/world.py"
  - "tests/load/test_after_step_load.py"
  - "tests/load/test_door_load.py"
  - "tests/load/test_door_steps_load.py"
  - "tests/mcp_server/test_deadline.py"
  - "tests/mcp_server/test_detached.py"
  - "tests/operations/gather_rig.py"
  - "tests/operations/handle_rig.py"
  - "tests/operations/held_support.py"
  - "tests/operations/message_placed.py"
  - "tests/operations/pause_support.py"
  - "tests/operations/status_placed.py"
  - "tests/operations/status_support.py"
  - "tests/operations/test_add_wake_command.py"
  - "tests/operations/test_after_step_starts.py"
  - "tests/operations/test_answer.py"
  - "tests/operations/test_answering_settle.py"
  - "tests/operations/test_claim_steps.py"
  - "tests/operations/test_claim_work.py"
  - "tests/operations/test_decisions.py"
  - "tests/operations/test_dismiss.py"
  - "tests/operations/test_door_clock.py"
  - "tests/operations/test_every_state_exits.py"
  - "tests/operations/test_handle_pause.py"
  - "tests/operations/test_handle_pause_child.py"
  - "tests/operations/test_handle_pause_message_sweep.py"
  - "tests/operations/test_held_question_exits.py"
  - "tests/operations/test_list_view.py"
  - "tests/operations/test_message_sweep_wrapper.py"
  - "tests/operations/test_pause_begin.py"
  - "tests/operations/test_pause_claim_held.py"
  - "tests/operations/test_pause_class.py"
  - "tests/operations/test_pause_context_gather.py"
  - "tests/operations/test_pause_door_faults.py"
  - "tests/operations/test_pause_eligibility.py"
  - "tests/operations/test_pause_existing.py"
  - "tests/operations/test_pause_held.py"
  - "tests/operations/test_pause_on_steps.py"
  - "tests/operations/test_prune.py"
  - "tests/operations/test_prune_wiring.py"
  - "tests/operations/test_question_sweep.py"
  - "tests/operations/test_resume.py"
  - "tests/operations/test_resume_attempt.py"
  - "tests/operations/test_resume_claim.py"
  - "tests/operations/test_run_gather.py"
  - "tests/operations/test_send_wakes_across_machines.py"
  - "tests/operations/test_served.py"
  - "tests/operations/test_settle_step.py"
  - "tests/operations/test_status_calls.py"
  - "tests/operations/test_status_matches_handle_pause.py"
  - "tests/operations/test_status_open_runs.py"
  - "tests/operations/test_status_runs_document.py"
  - "tests/operations/test_status_sweep.py"
  - "tests/operations/test_status_waiting.py"
  - "tests/operations/test_step_limits.py"
  - "tests/operations/test_step_machinery.py"
  - "tests/operations/test_wake_after_send.py"
  - "tests/operations/test_wake_mark.py"
  - "tests/operations/test_wake_run.py"
  - "tests/operations/test_wake_run_faults.py"
  - "tests/operations/test_wake_status.py"
  - "tests/operations/test_work_start.py"
  - "tests/operations/test_work_waiting.py"
  - "tests/operations/test_wrong_checkout.py"
  - "tests/operations/wake_run_support.py"
  - "tests/operations/ways.py"
  - "tests/operations/work_support.py"
  - "tests/prune_support.py"
  - "tests/release_child_wait.py"
  - "tests/scripts/test_update_live.py"
  - "tests/store/schema_12.py"
  - "tests/store/seed.py"
  - "tests/store/test_acting_machine.py"
  - "tests/store/test_answers.py"
  - "tests/store/test_held_questions.py"
  - "tests/store/test_machine_on_rows.py"
  - "tests/store/test_migration_012.py"
  - "tests/store/test_migration_013.py"
  - "tests/store/test_migrations.py"
  - "tests/store/test_question_closing.py"
  - "tests/store/test_schema_holds_no_mirrored_state.py"
  - "tests/store/test_settled.py"
  - "tests/store/test_wake_due.py"
  - "tests/store/test_wake_on_checkout.py"
  - "tests/store/test_wakes.py"
  - "tests/store/wake_support.py"
  - "tests/test_after_step.py"
  - "tests/test_import_boundaries.py"
  - "tests/test_message_timing.py"
  - "tests/test_read_side_defined_once.py"
  - "tests/test_wiring.py"
  - "tests/test_wiring_results.py"
  - "tests/upstream/squadron/test_run_outcome_fields.py"
  - "tests/wire/test_protocol.py"
  - "tests/wire/test_times.py"
turns: 20
promptTokens: 1341144
cachedTokens: 1122106
completionTokens: 11559
reasoningTokens: 7578
durationSeconds: 67.0
costUsd: 0.056623
costBasis: alias_pricing
squadronVersion: 0.24.38
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "`claim_work` counts a resume start before the claim can be taken, and the refused path records the count as the refusal reason"
    location: "src/amoeba/operations/steps/work.py:99-125"
  - id: F002
    severity: concern
    category: correctness
    summary: "`SELECT_HELD_WORK` treats a `note` request as due, but `messages.state` is NULL for notes and the \"no message row\" branch also matches notes"
    location: "src/amoeba/store/sql_local_work.py:92-110"
  - id: F003
    severity: concern
    category: correctness
    summary: "`mark_start_attempted` uses `IS` for the previous-start guard, but the previous value is written as a bound timestamp string while `start_attempted_at` is stored via `encode_timestamp` — the two encodings must match exactly"
    location: "src/amoeba/store/held_questions.py:120-146"
  - id: F004
    severity: concern
    category: error-handling-observability
    summary: "`work_start.start_claimed` resolves the amoeba script once for all items, but a `LaunchError` for a resume is recorded as `refused` while the claim is not freed"
    location: "src/amoeba/operations/work_start.py:120-141"
  - id: F005
    severity: note
    category: dependency-config-debt
    summary: "The `except Exception` in `hub/calls.py` has a `# noqa: BLE001` but the repo's stated ruff baseline does not include `BLE`"
    location: "src/amoeba/hub/calls.py:302"
  - id: F006
    severity: note
    category: other
    summary: "`sql_local_work.SELECT_RESUME_WORK` joins `questions` on `(run_id, paused_at)` but selects `answers.resume_start_count` — an answer whose question was closed still matches"
    location: "src/amoeba/store/sql_local_work.py:76-92"
  - id: F007
    severity: pass
    category: other
    summary: "SQL composes from module-level constants only, with every runtime value bound"
    location: "src/amoeba/store/sql_local_work.py:1-50"
  - id: F008
    severity: pass
    category: other
    summary: "The schema rebuild in migration 013 is documented, reversible in shape, and the triggers are created after the copy"
    location: "src/amoeba/store/schema/013_local_work.sql:1-40"
  - id: F009
    severity: pass
    category: other
    summary: "The step registry really is the single table, and the protocol lists agree with it"
    location: "src/amoeba/operations/steps/models.py:75-95"
  - id: F010
    severity: pass
    category: other
    summary: "The work flag is additive and the client's result document is rebuilt without it"
    location: "src/amoeba/wire/protocol.py:143-146"
---

# Review: code — slice 262

**Verdict:** CONCERNS
**Model:** minimax/minimax-m3.1-flash
**Diff:** truncated: 0 of 870663 characters reached the model
  - scripts/update_live.py: omitted (0 of 1854 characters)
  - src/amoeba/answering/decide.py: omitted (0 of 847 characters)
  - src/amoeba/answering/values.py: omitted (0 of 586 characters)
  - src/amoeba/cli/commands.py: omitted (0 of 1657 characters)
  - src/amoeba/cli/hub_commands.py: omitted (0 of 637 characters)
  - src/amoeba/cli/main.py: omitted (0 of 2586 characters)
  - src/amoeba/cli/parser.py: omitted (0 of 872 characters)
  - src/amoeba/cli/render/messages.py: omitted (0 of 791 characters)
  - src/amoeba/cli/render/simple.py: omitted (0 of 1034 characters)
  - src/amoeba/cli/render/waiting.py: omitted (0 of 1744 characters)
  - src/amoeba/cli/render/waking.py: omitted (0 of 1056 characters)
  - src/amoeba/cli/resume_command.py: omitted (0 of 2160 characters)
  - src/amoeba/cli/wake_command.py: omitted (0 of 1908 characters)
  - src/amoeba/client/call.py: omitted (0 of 748 characters)
  - src/amoeba/hub/admin.py: omitted (0 of 1688 characters)
  - src/amoeba/hub/call_work.py: omitted (0 of 4405 characters)
  - src/amoeba/hub/calls.py: omitted (0 of 4490 characters)
  - src/amoeba/operations/add_register.py: omitted (0 of 1662 characters)
  - src/amoeba/operations/answer.py: omitted (0 of 10457 characters)
  - src/amoeba/operations/answering_settle.py: omitted (0 of 7500 characters)
  - src/amoeba/operations/claim_waiting.py: omitted (0 of 5688 characters)
  - src/amoeba/operations/deps.py: omitted (0 of 1058 characters)
  - src/amoeba/operations/handle_pause.py: omitted (0 of 8645 characters)
  - src/amoeba/operations/list_view.py: omitted (0 of 1870 characters)
  - src/amoeba/operations/message_results.py: omitted (0 of 1567 characters)
  - src/amoeba/operations/pause_claim.py: omitted (0 of 15420 characters)
  - src/amoeba/operations/pause_class.py: omitted (0 of 4785 characters)
  - src/amoeba/operations/pause_context.py: omitted (0 of 4326 characters)
  - src/amoeba/operations/pause_eligibility.py: omitted (0 of 13500 characters)
  - src/amoeba/operations/pause_existing.py: omitted (0 of 5802 characters)
  - src/amoeba/operations/pause_held.py: omitted (0 of 7959 characters)
  - src/amoeba/operations/pause_models.py: omitted (0 of 617 characters)
  - src/amoeba/operations/pause_observed.py: omitted (0 of 4270 characters)
  - src/amoeba/operations/pause_results.py: omitted (0 of 4455 characters)
  - src/amoeba/operations/processes.py: omitted (0 of 821 characters)
  - src/amoeba/operations/program_sources.py: omitted (0 of 1975 characters)
  - src/amoeba/operations/prune.py: omitted (0 of 3508 characters)
  - src/amoeba/operations/prune_models.py: omitted (0 of 1207 characters)
  - src/amoeba/operations/question_judge.py: omitted (0 of 6463 characters)
  - src/amoeba/operations/question_sweep.py: omitted (0 of 6716 characters)
  - src/amoeba/operations/question_sweep_scope.py: omitted (0 of 3951 characters)
  - src/amoeba/operations/request_release.py: omitted (0 of 7122 characters)
  - src/amoeba/operations/resume.py: omitted (0 of 10666 characters)
  - src/amoeba/operations/resume_attempt.py: omitted (0 of 3902 characters)
  - src/amoeba/operations/resume_run.py: omitted (0 of 1808 characters)
  - src/amoeba/operations/resume_timing.py: omitted (0 of 2005 characters)
  - src/amoeba/operations/run_gather.py: omitted (0 of 2601 characters)
  - src/amoeba/operations/runs_document.py: omitted (0 of 1625 characters)
  - src/amoeba/operations/send.py: omitted (0 of 2951 characters)
  - src/amoeba/operations/send_write.py: omitted (0 of 3094 characters)
  - src/amoeba/operations/served.py: omitted (0 of 4540 characters)
  - src/amoeba/operations/served_runners.py: omitted (0 of 2624 characters)
  - src/amoeba/operations/served_types.py: omitted (0 of 2521 characters)
  - src/amoeba/operations/state_move.py: omitted (0 of 974 characters)
  - src/amoeba/operations/status.py: omitted (0 of 5416 characters)
  - src/amoeba/operations/status_local.py: omitted (0 of 2061 characters)
  - src/amoeba/operations/status_models.py: omitted (0 of 1738 characters)
  - src/amoeba/operations/status_runs.py: omitted (0 of 2161 characters)
  - src/amoeba/operations/status_waiting.py: omitted (0 of 2694 characters)
  - src/amoeba/operations/steps/__init__.py: omitted (0 of 484 characters)
  - src/amoeba/operations/steps/begin.py: omitted (0 of 8233 characters)
  - src/amoeba/operations/steps/context.py: omitted (0 of 1217 characters)
  - src/amoeba/operations/steps/dispatch.py: omitted (0 of 3876 characters)
  - src/amoeba/operations/steps/limits.py: omitted (0 of 2206 characters)
  - src/amoeba/operations/steps/model_base.py: omitted (0 of 1469 characters)
  - src/amoeba/operations/steps/models.py: omitted (0 of 2634 characters)
  - src/amoeba/operations/steps/models_pause.py: omitted (0 of 10737 characters)
  - src/amoeba/operations/steps/models_resume.py: omitted (0 of 2381 characters)
  - src/amoeba/operations/steps/models_runs.py: omitted (0 of 922 characters)
  - src/amoeba/operations/steps/models_wake.py: omitted (0 of 1898 characters)
  - src/amoeba/operations/steps/models_work.py: omitted (0 of 1638 characters)
  - src/amoeba/operations/steps/open_runs.py: omitted (0 of 1480 characters)
  - src/amoeba/operations/steps/pause.py: omitted (0 of 6695 characters)
  - src/amoeba/operations/steps/resume.py: omitted (0 of 6782 characters)
  - src/amoeba/operations/steps/settle.py: omitted (0 of 4306 characters)
  - src/amoeba/operations/steps/sources.py: omitted (0 of 2573 characters)
  - src/amoeba/operations/steps/wake.py: omitted (0 of 2906 characters)
  - src/amoeba/operations/steps/work.py: omitted (0 of 8046 characters)
  - src/amoeba/operations/store_steps.py: omitted (0 of 2365 characters)
  - src/amoeba/operations/wake.py: omitted (0 of 10319 characters)
  - src/amoeba/operations/wake_door.py: omitted (0 of 2323 characters)
  - src/amoeba/operations/wake_run.py: omitted (0 of 9214 characters)
  - src/amoeba/operations/wake_start.py: omitted (0 of 4835 characters)
  - src/amoeba/operations/wake_status.py: omitted (0 of 3200 characters)
  - src/amoeba/operations/work_start.py: omitted (0 of 6583 characters)
  - src/amoeba/store/answers.py: omitted (0 of 6180 characters)
  - src/amoeba/store/held_questions.py: omitted (0 of 1918 characters)
  - src/amoeba/store/machine_removal.py: omitted (0 of 2595 characters)
  - src/amoeba/store/machines.py: omitted (0 of 5111 characters)
  - src/amoeba/store/migrations.py: omitted (0 of 611 characters)
  - src/amoeba/store/models.py: omitted (0 of 1560 characters)
  - src/amoeba/store/question_closing.py: omitted (0 of 2447 characters)
  - src/amoeba/store/question_rows.py: omitted (0 of 951 characters)
  - src/amoeba/store/questions.py: omitted (0 of 1251 characters)
  - src/amoeba/store/schema/013_local_work.sql: omitted (0 of 6131 characters)
  - src/amoeba/store/sql.py: omitted (0 of 6354 characters)
  - src/amoeba/store/sql_held.py: omitted (0 of 2583 characters)
  - src/amoeba/store/sql_local_work.py: omitted (0 of 7564 characters)
  - src/amoeba/store/sql_machines.py: omitted (0 of 660 characters)
  - src/amoeba/store/sql_wakes.py: omitted (0 of 3230 characters)
  - src/amoeba/store/vocabulary.py: omitted (0 of 825 characters)
  - src/amoeba/store/wakes.py: omitted (0 of 7753 characters)
  - src/amoeba/store/work.py: omitted (0 of 4394 characters)
  - src/amoeba/upstream/squadron/checkpoint_kind.py: omitted (0 of 2142 characters)
  - src/amoeba/upstream/squadron/run_outcome.py: omitted (0 of 2692 characters)
  - src/amoeba/wire/protocol.py: omitted (0 of 4203 characters)
  - src/amoeba/wire/times.py: omitted (0 of 491 characters)
  - src/amoeba/wiring.py: omitted (0 of 4499 characters)
  - src/amoeba/wiring_door.py: omitted (0 of 4211 characters)
  - src/amoeba/wiring_gather.py: omitted (0 of 6442 characters)
  - src/amoeba/wiring_pause.py: omitted (0 of 4967 characters)
  - src/amoeba/wiring_release.py: omitted (0 of 2596 characters)
  - src/amoeba/wiring_steps.py: omitted (0 of 9556 characters)
  - tests/cli/test_hold_release_cli.py: omitted (0 of 674 characters)
  - tests/cli/test_legacy_move_cli.py: omitted (0 of 1265 characters)
  - tests/hub/call_support.py: omitted (0 of 738 characters)
  - tests/hub/in_process_hub.py: omitted (0 of 569 characters)
  - tests/hub/test_across_machines.py: omitted (0 of 7561 characters)
  - tests/hub/test_app.py: omitted (0 of 1399 characters)
  - tests/hub/test_clients_fixture.py: omitted (0 of 1650 characters)
  - tests/hub/test_door_client.py: omitted (0 of 648 characters)
  - tests/hub/test_door_faults.py: omitted (0 of 11031 characters)
  - tests/hub/test_door_operations.py: omitted (0 of 2678 characters)
  - tests/hub/test_door_steps.py: omitted (0 of 11031 characters)
  - tests/hub/test_handle_call.py: omitted (0 of 2905 characters)
  - tests/hub/test_join.py: omitted (0 of 3124 characters)
  - tests/hub/test_joined_entry_points.py: omitted (0 of 1017 characters)
  - tests/hub/test_rm_machine_work.py: omitted (0 of 5756 characters)
  - tests/hub/test_step_calls.py: omitted (0 of 6058 characters)
  - tests/hub/test_two_machines.py: omitted (0 of 2220 characters)
  - tests/hub/two_homes.py: omitted (0 of 5910 characters)
  - tests/hub_fixture.py: omitted (0 of 1096 characters)
  - tests/live/conftest.py: omitted (0 of 694 characters)
  - tests/live/hold/conftest.py: omitted (0 of 1218 characters)
  - tests/live/hold/split.py: omitted (0 of 6256 characters)
  - tests/live/hold/test_hold_split_live.py: omitted (0 of 3407 characters)
  - tests/live/machines.py: omitted (0 of 3486 characters)
  - tests/live/messaging/test_two_machines_live.py: omitted (0 of 2873 characters)
  - tests/live/pause/harness.py: omitted (0 of 2014 characters)
  - tests/live/waking/conftest.py: omitted (0 of 1373 characters)
  - tests/live/waking/split.py: omitted (0 of 3922 characters)
  - tests/live/waking/test_waking_split_live.py: omitted (0 of 2310 characters)
  - tests/live/waking/world.py: omitted (0 of 1306 characters)
  - tests/load/test_after_step_load.py: omitted (0 of 3393 characters)
  - tests/load/test_door_load.py: omitted (0 of 686 characters)
  - tests/load/test_door_steps_load.py: omitted (0 of 12475 characters)
  - tests/mcp_server/test_deadline.py: omitted (0 of 593 characters)
  - tests/mcp_server/test_detached.py: omitted (0 of 1411 characters)
  - tests/operations/gather_rig.py: omitted (0 of 1720 characters)
  - tests/operations/handle_rig.py: omitted (0 of 4258 characters)
  - tests/operations/held_support.py: omitted (0 of 3907 characters)
  - tests/operations/message_placed.py: omitted (0 of 1064 characters)
  - tests/operations/pause_support.py: omitted (0 of 1064 characters)
  - tests/operations/status_placed.py: omitted (0 of 2279 characters)
  - tests/operations/status_support.py: omitted (0 of 569 characters)
  - tests/operations/test_add_wake_command.py: omitted (0 of 933 characters)
  - tests/operations/test_after_step_starts.py: omitted (0 of 9292 characters)
  - tests/operations/test_answer.py: omitted (0 of 4178 characters)
  - tests/operations/test_answering_settle.py: omitted (0 of 7936 characters)
  - tests/operations/test_claim_steps.py: omitted (0 of 8527 characters)
  - tests/operations/test_claim_work.py: omitted (0 of 9175 characters)
  - tests/operations/test_decisions.py: omitted (0 of 632 characters)
  - tests/operations/test_dismiss.py: omitted (0 of 1923 characters)
  - tests/operations/test_door_clock.py: omitted (0 of 4151 characters)
  - tests/operations/test_every_state_exits.py: omitted (0 of 3952 characters)
  - tests/operations/test_handle_pause.py: omitted (0 of 6886 characters)
  - tests/operations/test_handle_pause_child.py: omitted (0 of 1337 characters)
  - tests/operations/test_handle_pause_message_sweep.py: omitted (0 of 2912 characters)
  - tests/operations/test_held_question_exits.py: omitted (0 of 1207 characters)
  - tests/operations/test_list_view.py: omitted (0 of 724 characters)
  - tests/operations/test_message_sweep_wrapper.py: omitted (0 of 888 characters)
  - tests/operations/test_pause_begin.py: omitted (0 of 8847 characters)
  - tests/operations/test_pause_claim_held.py: omitted (0 of 5017 characters)
  - tests/operations/test_pause_class.py: omitted (0 of 2465 characters)
  - tests/operations/test_pause_context_gather.py: omitted (0 of 2188 characters)
  - tests/operations/test_pause_door_faults.py: omitted (0 of 3939 characters)
  - tests/operations/test_pause_eligibility.py: omitted (0 of 3548 characters)
  - tests/operations/test_pause_existing.py: omitted (0 of 4239 characters)
  - tests/operations/test_pause_held.py: omitted (0 of 5386 characters)
  - tests/operations/test_pause_on_steps.py: omitted (0 of 6796 characters)
  - tests/operations/test_prune.py: omitted (0 of 3552 characters)
  - tests/operations/test_prune_wiring.py: omitted (0 of 4552 characters)
  - tests/operations/test_question_sweep.py: omitted (0 of 4694 characters)
  - tests/operations/test_resume.py: omitted (0 of 14565 characters)
  - tests/operations/test_resume_attempt.py: omitted (0 of 8330 characters)
  - tests/operations/test_resume_claim.py: omitted (0 of 6382 characters)
  - tests/operations/test_run_gather.py: omitted (0 of 1713 characters)
  - tests/operations/test_send_wakes_across_machines.py: omitted (0 of 4320 characters)
  - tests/operations/test_served.py: omitted (0 of 1451 characters)
  - tests/operations/test_settle_step.py: omitted (0 of 8967 characters)
  - tests/operations/test_status_calls.py: omitted (0 of 1714 characters)
  - tests/operations/test_status_matches_handle_pause.py: omitted (0 of 1536 characters)
  - tests/operations/test_status_open_runs.py: omitted (0 of 1667 characters)
  - tests/operations/test_status_runs_document.py: omitted (0 of 2090 characters)
  - tests/operations/test_status_sweep.py: omitted (0 of 5252 characters)
  - tests/operations/test_status_waiting.py: omitted (0 of 1069 characters)
  - tests/operations/test_step_limits.py: omitted (0 of 4019 characters)
  - tests/operations/test_step_machinery.py: omitted (0 of 5664 characters)
  - tests/operations/test_wake_after_send.py: omitted (0 of 2491 characters)
  - tests/operations/test_wake_mark.py: omitted (0 of 2939 characters)
  - tests/operations/test_wake_run.py: omitted (0 of 8831 characters)
  - tests/operations/test_wake_run_faults.py: omitted (0 of 4729 characters)
  - tests/operations/test_wake_status.py: omitted (0 of 1813 characters)
  - tests/operations/test_work_start.py: omitted (0 of 6541 characters)
  - tests/operations/test_work_waiting.py: omitted (0 of 5064 characters)
  - tests/operations/test_wrong_checkout.py: omitted (0 of 1986 characters)
  - tests/operations/wake_run_support.py: omitted (0 of 2755 characters)
  - tests/operations/ways.py: omitted (0 of 1914 characters)
  - tests/operations/work_support.py: omitted (0 of 6233 characters)
  - tests/prune_support.py: omitted (0 of 1335 characters)
  - tests/release_child_wait.py: omitted (0 of 1358 characters)
  - tests/scripts/test_update_live.py: omitted (0 of 3205 characters)
  - tests/store/schema_12.py: omitted (0 of 3735 characters)
  - tests/store/seed.py: omitted (0 of 2569 characters)
  - tests/store/test_acting_machine.py: omitted (0 of 850 characters)
  - tests/store/test_answers.py: omitted (0 of 1620 characters)
  - tests/store/test_held_questions.py: omitted (0 of 1880 characters)
  - tests/store/test_machine_on_rows.py: omitted (0 of 5940 characters)
  - tests/store/test_migration_012.py: omitted (0 of 967 characters)
  - tests/store/test_migration_013.py: omitted (0 of 7278 characters)
  - tests/store/test_migrations.py: omitted (0 of 2326 characters)
  - tests/store/test_question_closing.py: omitted (0 of 5447 characters)
  - tests/store/test_schema_holds_no_mirrored_state.py: omitted (0 of 1508 characters)
  - tests/store/test_settled.py: omitted (0 of 532 characters)
  - tests/store/test_wake_due.py: omitted (0 of 7199 characters)
  - tests/store/test_wake_on_checkout.py: omitted (0 of 2104 characters)
  - tests/store/test_wakes.py: omitted (0 of 3468 characters)
  - tests/store/wake_support.py: omitted (0 of 2375 characters)
  - tests/test_after_step.py: omitted (0 of 7830 characters)
  - tests/test_import_boundaries.py: omitted (0 of 4134 characters)
  - tests/test_message_timing.py: omitted (0 of 6850 characters)
  - tests/test_read_side_defined_once.py: omitted (0 of 722 characters)
  - tests/test_wiring.py: omitted (0 of 1054 characters)
  - tests/test_wiring_results.py: omitted (0 of 615 characters)
  - tests/upstream/squadron/test_run_outcome_fields.py: omitted (0 of 716 characters)
  - tests/wire/test_protocol.py: omitted (0 of 2001 characters)
  - tests/wire/test_times.py: omitted (0 of 499 characters)
**Evidence:** 20 successful tool call(s) of 20 made; 0 of 870663 diff characters reached the model

## Findings

### [CONCERN] `claim_work` counts a resume start before the claim can be taken, and the refused path records the count as the refusal reason

In `_claim_resumes`, `count_resume_start(transaction, work.answer_seq)` is called after `claim_resume` returns `ResumeClaimed`, so the count is right in the happy path. But the exhausted path (`_refuse_resume`) is reached *before* the room check and before any claim is taken, and it calls `record_resume(..., claim_id=None)`. `sql.RECORD_RESUME` clears `resume_claim_id` only when the caller's id matches (`CASE WHEN resume_claim_id = ? THEN NULL ELSE resume_claim_id END`), and `None` matches nothing, so the claim is correctly not freed — but the row is left holding a stale `resume_claim_id` while `resume_outcome` is now `refused`. The next `resume_work` read still returns this answer (the query filters `resume_outcome IS NULL`, so it drops out — fine), yet `SELECT_RESUME_WORK` does not filter on `resume_outcome = 'refused'` the way `CLAIM_RESUME` does, and `resume_work`'s docstring says "no outcome". The two predicates disagree: `CLAIM_RESUME` accepts `refused` as takeable, `SELECT_RESUME_WORK` does not select it. A refused answer is therefore never handed out again by `claim_work`, while `claim_resume` would still let `resume_claim` take it. This is the exact "two ways of doing the same thing" the rules forbid; the two predicates should be defined once.

### [CONCERN] `SELECT_HELD_WORK` treats a `note` request as due, but `messages.state` is NULL for notes and the "no message row" branch also matches notes

The comment says "A row that names a note, which has no state, is due too", and the SQL does include `messages.state IS NULL` in the terminal-or-open test. But the first branch is `NOT EXISTS (SELECT 1 FROM messages WHERE messages.message_id = questions.request_id)`, which matches a request id that names no message at all. A held question whose request row was pruned (or whose `request_id` was never a message id) is therefore reported as due work, and `claim_work` will start `handle-pause` for it, which the design says should report a corrupt row. The two branches (missing message vs. note message) are not distinguishable in the current SQL, so the "note" case and the "corrupt/missing" case collapse into one. The docstring in `store/work.py` (`held_work`) repeats this: "whose request has ended or is gone" — gone and note are the same predicate.

### [CONCERN] `mark_start_attempted` uses `IS` for the previous-start guard, but the previous value is written as a bound timestamp string while `start_attempted_at` is stored via `encode_timestamp` — the two encodings must match exactly

`mark_start_attempted` binds `None if previous is None else encode_timestamp(previous)` and compares with `start_attempted_at IS ?`. The `previous` value the caller passes comes from `QuestionRecord.start_attempted_at`, which was decoded by `decode_timestamp` from the stored text. If `encode_timestamp` and `decode_timestamp` are not exact inverses (for example a timezone suffix normalisation or a precision difference), the guard never matches and `mark_start_attempted` always returns False, so no `handle-pause` is ever started and no start count is kept. I could not confirm the two functions are inverses from the files I read — `store/row_values.py` was not in the diff and I did not open it — so treat this as needing verification rather than a confirmed defect.

### [CONCERN] `work_start.start_claimed` resolves the amoeba script once for all items, but a `LaunchError` for a resume is recorded as `refused` while the claim is not freed

`_record_refused_resume` calls `steps.run(RESUME_RECORD, ResumeRecordRequest(..., claim_id=item.claim_id, ...))`. `record_resume` binds `claim_id` and `sql.RECORD_RESUME` frees the claim only when it matches — so the claim *is* freed here (the id matches), and the answer's outcome becomes `refused`. Good. However, `_record_refused_resume` catches `(StoreError, HubUnreachableError, HubRefusedError)` and logs, leaving the answer with a live claim that will run out and be re-handed-out. The module docstring says exactly that ("the claim runs out and is handed out again"), so this is intended — but the interaction with the `MAX_AUTOMATIC_STARTS` cap is not: `resume_start_count` was already incremented by `claim_work` before the failed start, so a persistently broken script burns the three starts and the answer ends as `refused` with a detail about "no attempt recorded an outcome" rather than about the script being missing. The detail text in `_refuse_resume` ("no attempt recorded an outcome") is misleading when the real cause was a missing script. Consider recording the start failure's detail as the answer's detail.

### [NOTE] The `except Exception` in `hub/calls.py` has a `# noqa: BLE001` but the repo's stated ruff baseline does not include `BLE`

The rules name the required ruff selection as `["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]`, and `BLE` is in that list, so the noqa is correct and needed. Flagging only to note that the `# noqa: BLE001` here is on a deliberate process-boundary handler (rule (c)), which is allowed — no action required beyond confirming the ruff config actually selects `BLE`.

### [NOTE] `sql_local_work.SELECT_RESUME_WORK` joins `questions` on `(run_id, paused_at)` but selects `answers.resume_start_count` — an answer whose question was closed still matches

The join is on the question key and the question's `state = 'answered'`. A question closed by `rm-machine` (D13) is `closed`, so it drops out — correct. But an answer whose question was never inserted (fixture rows, or an answer inserted before its question) is invisible to `resume_work` while still visible to `latest_answer` and `resume_claim`. This asymmetry is intentional for the "answered" state filter, but it means the two places that find "an answer waiting for a resume" do not agree on the row set.

### [PASS] SQL composes from module-level constants only, with every runtime value bound

Every statement in the new SQL module builds from `QUESTION_COLUMNS` and `OPEN_QUESTION_CLAUSE` (module constants) and binds all runtime values through `?`. `SELECT_OPEN_QUESTIONS_OF_MACHINE` and `SELECT_OPEN_ROWS_OF_RUN_ON_MACHINE` f-string only the shared column list and clause, which is exactly what the repo's "SQL composes from constants only" rule permits.

### [PASS] The schema rebuild in migration 013 is documented, reversible in shape, and the triggers are created after the copy

The file explains why the two tables are rebuilt (SQLite cannot alter a `CHECK`), lists what is carried across, and creates the `machine_id IS NULL` triggers last — with the reason given (a trigger fires on `INSERT ... SELECT`). The runner turns foreign keys off around the transaction and runs `foreign_key_check` before commit (`store/migrations.py`), which the file's comment relies on. Column order in the new tables matches `QUESTION_COLUMNS` in `store/sql.py` and `sql_wakes._WAKE_COLUMNS`, which the positional readers (`question_from_row`, `wakes._wake`) depend on.

### [PASS] The step registry really is the single table, and the protocol lists agree with it

`STEP_MODELS` is built from one `Step` per step, `dispatch.STEP_FUNCTIONS` names each function once, and `wire/protocol.py` lists `STEP_CALLS` and `WRITING_STEPS` separately with a comment saying a test asserts they equal the `STEP_MODELS` names. `claim_work` is registered in both places with `writes=True, needs_config=True`, and `call_work.needs_config` reads the flag from the same row, so the hub and the local way cannot disagree about whether a step needs the config.

### [PASS] The work flag is additive and the client's result document is rebuilt without it

`WORK_REPLY_KEY` and `WORK_PROBLEM_REPLY_KEY` are separate keys, `hub/call_work.work_keys` returns `work_problem` *instead of* `work` when the config cannot load (never a false flag), and `wiring_steps.take_work_keys` pops both out of the result document before it is rebuilt. A kept result is stored without the flag and re-flagged on each return, so the flag is never stale.

### Run Digest

- Response length: 9311 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 524288 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 30305
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 1341144 / 1122106 / not computed / 11559 / 7578
- Duration: 67.0 s
- Cost: $0.06 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10

## Resolution (20261124)

- **`claim_work` and refused resumes.** The two predicates differ by design: a refused resume is not pending work and is taken again only by a new `answer` or a `handle-pause` (D6, D10), so `SELECT_RESUME_WORK` leaves `refused` out while `CLAIM_RESUME` accepts it. The comment on `SELECT_RESUME_WORK` now says so. Fixed what was left: when `claim_work` records an exhausted answer `refused`, it now also clears the last attempt's run-out claim (`steps/work._refuse_resume`), asserted in `tests/operations/test_claim_work.py`.
- **`SELECT_HELD_WORK` and a request no longer stored.** Intended: a pruned request counts as ended, as 242 made it, and its `handle-pause` waits on the PM as `request_unknown` (D10's "ended or no longer stored"). The comment now says so; no code change.
- **`mark_start_attempted`'s previous-start guard.** Verified by tests that pass through it with a previous start set: `tests/operations/test_claim_work.py::test_a_dead_claim_is_started_three_times_and_the_fourth_is_starts_exhausted` and `tests/store/test_held_questions.py::test_mark_start_attempted_loses_to_a_start_recorded_since_the_read`. No change.
- **A failed resume start and the cap.** A failed start is recorded `refused` with the launch error as its detail, which frees the claim and ends the work, so it does not burn the three starts. Only when that record itself fails does the claim run out; the exhausted detail is then accurate. No change.
- **Notes.** `BLE` is selected in the ruff config; the answer/question join is intended. No change.

