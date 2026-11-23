---
docType: review
layer: project
reviewType: code
slice: members-by-name
conventionsSource: AGENTS.md
projectRules: [general.md, python.md, sql.md, testing.md]
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/261-slice.members-by-name.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261123
dateUpdated: 20261123
reviewedSha: 4af4d12caa2284311a97b643d85c4f195fb91623
reviewedBlob: 77860aa127b303940a03767ab70df526b1c97f4d
reviewedBlobCurrent: true
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 75
injected:
  - key: conventions
    path: "AGENTS.md"
    chars: 24525
    sha256: 2387512002bb2a73aa247bc36bc98d7162c5b5110ded41f56319d098d282ddbc
    whole: true
filesRead:
  - "src/amoeba/store/schema/012_members_by_name.sql"
  - "src/amoeba/store/member_names.py"
  - "src/amoeba/store/migrations.py"
  - "src/amoeba/store/checkouts.py"
  - "src/amoeba/store/machines.py"
  - "src/amoeba/store/sql_checkouts.py"
  - "src/amoeba/operations/naming.py"
  - "src/amoeba/operations/add_names.py"
  - "src/amoeba/operations/add_member.py"
  - "src/amoeba/upstream/git_read.py"
  - "src/amoeba/operations/origin.py"
  - "src/amoeba/operations/add_origin.py"
  - "src/amoeba/operations/state_move.py"
  - "tests/store/test_migration_012.py"
  - "tests/store/schema_11.py"
  - "tests/store/test_member_names.py"
  - ".git/HEAD"
  - "src/amoeba/operations/name_by_id.py"
  - "src/amoeba/operations/here_document.py"
  - "src/amoeba/operations/set_up_plan.py"
  - "src/amoeba/hub/store_open.py"
  - "scripts/update_live.py"
  - "tests/scripts/test_update_live.py"
  - "src/amoeba/operations/add.py"
  - "src/amoeba/operations/add_gather.py"
  - "src/amoeba/operations/set_up_remove.py"
  - "src/amoeba/wiring_gather.py"
  - "src/amoeba/operations/set_up_resolve.py"
  - "src/amoeba/store/sql.py"
  - "src/amoeba/operations/caller.py"
  - "tests/upstream/context_forge/test_projects.py"
  - "src/amoeba/upstream/context_forge/projects.py"
  - "src/amoeba/operations/set_up.py"
  - "src/amoeba/store/store.py"
searches:
  - "grep SELECT_UNNAMED_MEMBERS|SELECT_MEMBER_BY_NAME|SELECT_MEMBER_BY_ORIGIN|SELECT_REMOVED_MEMBER_BY_ORIGIN|SELECT_NAME_IS_OTHER_MEMBERS_ID|SET_MEMBER_NAME|SET_MEMBER_ORIGIN|CLEAR_MEMBER_WAKE_COMMAND|f\"|f' in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/sql.py"
  - "grep CREATE TABLE (IF NOT EXISTS )?(members|owners|machines)\\b|project_id\\s+TEXT|machine_id\\s+INTEGER|owner_id\\s+INTEGER|UNIQUE|PRIMARY KEY in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/schema"
  - "list_files src/amoeba/store/schema/*.sql in /Users/manta/source/repos/manta/amoeba"
  - "grep name_members\\(|def open_state_store|ContextForgeError in /Users/manta/source/repos/manta/amoeba/src"
  - "grep def run_cf|class CfCallFailed|class CfRun|def output_head|detail=|CfCallFailed\\(|TimeoutExpired|OSError|CfRun\\s*= in /Users/manta/source/repos/manta/amoeba/src/amoeba/upstream/context_forge/cli_call.py"
  - "grep is_reduced_origin|is_member_name\\(|set_member_origin\\(|set_member_name\\(|insert_member\\(|count_rows\\(|select_all_rows\\(|row_counts\\( in /Users/manta/source/repos/manta/amoeba/src"
  - "grep is_reduced_origin|count_rows\\(|row_counts\\( in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep MEMBER_NAME|def is_member_name|_NAME_PATTERN|re\\.compile in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/vocabulary.py"
  - "grep name_by_id\\(|name_members\\(|act_as_local\\(|from_backup|open_hub_store|def open_hub in /Users/manta/source/repos/manta/amoeba/src"
  - "grep project_id|PROJECT_ID|id_pattern|re\\.compile in /Users/manta/source/repos/manta/amoeba/src/amoeba/upstream/context_forge/projects.py"
  - "grep cf list projects|cf is down|cf fails|cf failed|cannot name|every command in /Users/manta/source/repos/manta/amoeba/project-documents"
  - "grep ^### \\[ in /Users/manta/source/repos/manta/amoeba/project-documents/user/reviews"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep AMOEBA_HOME|monkeypatch|store_path|state_home|config_path in /Users/manta/source/repos/manta/amoeba/tests/scripts"
  - "grep def amoeba_home|AMOEBA_HOME|XDG_STATE_HOME|XDG_CONFIG_HOME|HOME\" in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep def state_home|def config_path|def store_path|def state_layout|AMOEBA_HOME|XDG_STATE_HOME|XDG_CONFIG_HOME in /Users/manta/source/repos/manta/amoeba/src/amoeba/config/home.py"
  - "grep DELETE FROM members|DELETE_MEMBER\\b|delete_checkouts_of_member\\(|REMOVE_MEMBER|REMOVE_MEMBER\\b|def remove_member|UPDATE members SET removed_at in /Users/manta/source/repos/manta/amoeba/src"
  - "grep remove_member\\( in /Users/manta/source/repos/manta/amoeba/src"
  - "grep here|wake_command|machine|origin|name in /Users/manta/source/repos/manta/amoeba/src/amoeba/hub/calls.py"
  - "grep wake_command|def refuse_door_fields|WAKE in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/add_door.py"
  - "grep refuse_door_fields|gather_add|def run_served|def _add|add\\(|Door\\.|wake_command in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep name_by_id|delete_checkouts_at_path|remove_machine|first_wakeable_checkout|set_checkout_wake_command|clear_member_wake_command|checkout_listing|SELECT_ACTIVE_MEMBERS_WITHOUT_CHECKOUT_ON|active_members_without|first_checkout_on|checkouts_on_machine in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep def test_|parametrize in /Users/manta/source/repos/manta/amoeba/tests/operations/test_naming.py"
  - "grep rename_to|name_is_taken|check_given_name|is_member_name in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations"
  - "grep IntegrityError|except sqlite3|def write\\(|def apply_set_up|def set_up\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep INSERT_MEMBER|UPSERT|def insert_member|def upsert_member|def member_from_row|def _member_insert in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/programs.py"
  - "grep def _member_name|ACTIVE_MEMBER: Final|_MEMBER_COLUMNS: Final in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "list_files **/member_reference*.py in /Users/manta/source/repos/manta/amoeba"
  - "grep member_reference|MemberReference in /Users/manta/source/repos/manta/amoeba"
  - "grep operations\\.members\\b|operations import members|from amoeba\\.operations\\.members|project_lookup|project_names|_project_names|test_members\\b in /Users/manta/source/repos/manta/amoeba"
  - "grep def git_root|rev-parse|ORIGIN_READ_TIMEOUT_SECONDS|NO_SUCH_REMOTE_EXIT_CODE|timeout|subprocess in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/here.py"
  - "grep checkout|delete_checkouts_at_path|def  in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/rm.py"
  - "grep name_before_write|upsert_member\\(|apply_plan\\(|_write_member\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/set_up.py"
  - "grep rename|renam|same name|NAME_TAKEN in /Users/manta/source/repos/manta/amoeba/tests/operations"
  - "grep first_checkout_on|checkout_listing|first_wakeable_checkout|set_checkout_wake_command|checkouts_on_machine|delete_checkout\\b|delete_checkout\\(|acting_machine_id|machine_name\\(|clear_member_wake_command|SELECT_CHECKOUT_MACHINE|SELECT_MACHINE_NAME in /Users/manta/source/repos/manta/amoeba/src"
  - "grep first_checkout_on|checkout_listing|first_wakeable_checkout|set_checkout_wake_command|SELECT_FIRST_CHECKOUT_ON|SELECT_CHECKOUT_LISTING|SELECT_WAKEABLE_CHECKOUT in /Users/manta/source/repos/manta/amoeba"
  - "grep SELECT_MACHINE_NAME\\b|SELECT_MACHINE_BY_NAME\\b|SELECT name FROM machines in /Users/manta/source/repos/manta/amoeba/src/amoeba/store"
diffTruncated: true
diffCutFiles:
  - "scripts/update_live.py"
  - "src/amoeba/cli/commands.py"
  - "src/amoeba/cli/registration_arguments.py"
  - "src/amoeba/cli/render/dispatch.py"
  - "src/amoeba/cli/render/messages.py"
  - "src/amoeba/cli/render/registration.py"
  - "src/amoeba/cli/render/registry.py"
  - "src/amoeba/cli/render/releases.py"
  - "src/amoeba/cli/render/text.py"
  - "src/amoeba/client/call.py"
  - "src/amoeba/hub/admin.py"
  - "src/amoeba/hub/calls.py"
  - "src/amoeba/hub/store_open.py"
  - "src/amoeba/mcp/tools.py"
  - "src/amoeba/operations/add.py"
  - "src/amoeba/operations/add_gather.py"
  - "src/amoeba/operations/add_member.py"
  - "src/amoeba/operations/add_names.py"
  - "src/amoeba/operations/add_origin.py"
  - "src/amoeba/operations/caller.py"
  - "src/amoeba/operations/cancel.py"
  - "src/amoeba/operations/cf_readers.py"
  - "src/amoeba/operations/changes.py"
  - "src/amoeba/operations/changes_models.py"
  - "src/amoeba/operations/decisions.py"
  - "src/amoeba/operations/deps.py"
  - "src/amoeba/operations/errors.py"
  - "src/amoeba/operations/handle_pause.py"
  - "src/amoeba/operations/here.py"
  - "src/amoeba/operations/here_document.py"
  - "src/amoeba/operations/inbox.py"
  - "src/amoeba/operations/list_registry.py"
  - "src/amoeba/operations/list_view.py"
  - "src/amoeba/operations/member_reference.py"
  - "src/amoeba/operations/members.py"
  - "src/amoeba/operations/message_member.py"
  - "src/amoeba/operations/name_by_id.py"
  - "src/amoeba/operations/naming.py"
  - "src/amoeba/operations/origin.py"
  - "src/amoeba/operations/pause_claim.py"
  - "src/amoeba/operations/pause_context.py"
  - "src/amoeba/operations/pause_eligibility.py"
  - "src/amoeba/operations/pause_results.py"
  - "src/amoeba/operations/program_sources.py"
  - "src/amoeba/operations/project_lookup.py"
  - "src/amoeba/operations/question_sweep_scope.py"
  - "src/amoeba/operations/release_member.py"
  - "src/amoeba/operations/reply.py"
  - "src/amoeba/operations/report_release.py"
  - "src/amoeba/operations/rm.py"
  - "src/amoeba/operations/run_gather.py"
  - "src/amoeba/operations/runs_document.py"
  - "src/amoeba/operations/send.py"
  - "src/amoeba/operations/served.py"
  - "src/amoeba/operations/served_runners.py"
  - "src/amoeba/operations/served_types.py"
  - "src/amoeba/operations/set_up.py"
  - "src/amoeba/operations/set_up_models.py"
  - "src/amoeba/operations/set_up_plan.py"
  - "src/amoeba/operations/set_up_remove.py"
  - "src/amoeba/operations/set_up_remove_resolve.py"
  - "src/amoeba/operations/set_up_resolve.py"
  - "src/amoeba/operations/set_up_state.py"
  - "src/amoeba/operations/set_up_wake.py"
  - "src/amoeba/operations/standing.py"
  - "src/amoeba/operations/state_move.py"
  - "src/amoeba/operations/status.py"
  - "src/amoeba/operations/status_calls.py"
  - "src/amoeba/operations/status_local.py"
  - "src/amoeba/operations/status_models.py"
  - "src/amoeba/operations/status_placement.py"
  - "src/amoeba/operations/status_requests.py"
  - "src/amoeba/operations/status_runs.py"
  - "src/amoeba/operations/status_waiting.py"
  - "src/amoeba/operations/wake.py"
  - "src/amoeba/operations/wake_door.py"
  - "src/amoeba/operations/wake_status.py"
  - "src/amoeba/store/checkouts.py"
  - "src/amoeba/store/machines.py"
  - "src/amoeba/store/member_names.py"
  - "src/amoeba/store/migrations.py"
  - "src/amoeba/store/models.py"
  - "src/amoeba/store/programs.py"
  - "src/amoeba/store/schema/012_members_by_name.sql"
  - "src/amoeba/store/sql.py"
  - "src/amoeba/store/sql_checkouts.py"
  - "src/amoeba/store/vocabulary.py"
  - "src/amoeba/store/wakes.py"
  - "src/amoeba/upstream/context_forge/project_of.py"
  - "src/amoeba/upstream/context_forge/projects.py"
  - "src/amoeba/upstream/git_read.py"
  - "src/amoeba/wire/protocol.py"
  - "src/amoeba/wiring.py"
  - "src/amoeba/wiring_door.py"
  - "src/amoeba/wiring_gather.py"
  - "src/amoeba/wiring_messages.py"
  - "src/amoeba/wiring_presence.py"
  - "src/amoeba/wiring_registry.py"
  - "src/amoeba/wiring_releases.py"
  - "tests/answering/test_default_rules_reads.py"
  - "tests/cli/cli_support.py"
  - "tests/cli/message_cli_support.py"
  - "tests/cli/render/test_registration.py"
  - "tests/cli/render/test_registry.py"
  - "tests/cli/render/test_releases.py"
  - "tests/cli/render/test_status_requests.py"
  - "tests/cli/requests_support.py"
  - "tests/cli/test_add_cli.py"
  - "tests/cli/test_add_secrets_cli.py"
  - "tests/cli/test_add_wake_command_cli.py"
  - "tests/cli/test_hold_release_cli.py"
  - "tests/cli/test_inbox_cli.py"
  - "tests/cli/test_legacy_move_cli.py"
  - "tests/cli/test_list_cli.py"
  - "tests/cli/test_pause_cli.py"
  - "tests/cli/test_read_side_cli.py"
  - "tests/cli/test_release_cli.py"
  - "tests/cli/test_reply_cli.py"
  - "tests/cli/test_requests_scenario.py"
  - "tests/cli/test_rm_cli.py"
  - "tests/cli/test_send_cli.py"
  - "tests/cli/test_send_note_cli.py"
  - "tests/cli/test_standing_cli.py"
  - "tests/hub/call_support.py"
  - "tests/hub/test_admin.py"
  - "tests/hub/test_app.py"
  - "tests/hub/test_chain.py"
  - "tests/hub/test_clients_fixture.py"
  - "tests/hub/test_door_client.py"
  - "tests/hub/test_door_operations.py"
  - "tests/hub/test_handle_call.py"
  - "tests/hub/test_join.py"
  - "tests/hub/test_joined_entry_points.py"
  - "tests/hub/test_members_door.py"
  - "tests/hub/test_two_machines.py"
  - "tests/hub_clients.py"
  - "tests/hub_fixture.py"
  - "tests/live/messaging/repos.py"
  - "tests/live/messaging/test_two_machines_live.py"
  - "tests/live/pause/harness.py"
  - "tests/live/program/consumer.py"
  - "tests/load/messages_worker.py"
  - "tests/load/test_door_load.py"
  - "tests/load/test_messages_load.py"
  - "tests/load/test_no_cf_under_write_lock.py"
  - "tests/load/test_report_release_load.py"
  - "tests/load/test_wake_claim_load.py"
  - "tests/mcp_server/presence_rig.py"
  - "tests/mcp_server/test_call_tool.py"
  - "tests/mcp_server/test_in_process.py"
  - "tests/mcp_server/test_message_tools.py"
  - "tests/mcp_server/test_note_push.py"
  - "tests/mcp_server/test_presence.py"
  - "tests/mcp_server/test_presence_serving.py"
  - "tests/mcp_server/test_release_tools.py"
  - "tests/operations/add_placed.py"
  - "tests/operations/gather_rig.py"
  - "tests/operations/held_support.py"
  - "tests/operations/list_support.py"
  - "tests/operations/message_placed.py"
  - "tests/operations/message_support.py"
  - "tests/operations/pause_support.py"
  - "tests/operations/program_rig.py"
  - "tests/operations/release_placed.py"
  - "tests/operations/release_support.py"
  - "tests/operations/reply_worker.py"
  - "tests/operations/rm_placed.py"
  - "tests/operations/runs_doc_support.py"
  - "tests/operations/set_up_support.py"
  - "tests/operations/standing_support.py"
  - "tests/operations/status_placed.py"
  - "tests/operations/status_support.py"
  - "tests/operations/test_add.py"
  - "tests/operations/test_add_by_checkout.py"
  - "tests/operations/test_add_gather.py"
  - "tests/operations/test_add_member.py"
  - "tests/operations/test_add_wake_command.py"
  - "tests/operations/test_answering_settle.py"
  - "tests/operations/test_caller.py"
  - "tests/operations/test_cancel.py"
  - "tests/operations/test_changes.py"
  - "tests/operations/test_decisions.py"
  - "tests/operations/test_handle_pause.py"
  - "tests/operations/test_handle_pause_registers.py"
  - "tests/operations/test_held_question_exits.py"
  - "tests/operations/test_here.py"
  - "tests/operations/test_here_document.py"
  - "tests/operations/test_inbox.py"
  - "tests/operations/test_inbox_notes.py"
  - "tests/operations/test_list_members.py"
  - "tests/operations/test_list_registry.py"
  - "tests/operations/test_list_standing.py"
  - "tests/operations/test_list_view.py"
  - "tests/operations/test_mark_read.py"
  - "tests/operations/test_member_answering.py"
  - "tests/operations/test_members.py"
  - "tests/operations/test_message_member.py"
  - "tests/operations/test_message_names.py"
  - "tests/operations/test_message_sweep_wrapper.py"
  - "tests/operations/test_naming.py"
  - "tests/operations/test_origin.py"
  - "tests/operations/test_pause_cf_ids.py"
  - "tests/operations/test_pause_eligibility.py"
  - "tests/operations/test_program_sources.py"
  - "tests/operations/test_prune.py"
  - "tests/operations/test_prune_wiring.py"
  - "tests/operations/test_release_names.py"
  - "tests/operations/test_release_notes.py"
  - "tests/operations/test_release_notes_match_changes.py"
  - "tests/operations/test_reply.py"
  - "tests/operations/test_reply_concurrent.py"
  - "tests/operations/test_report_release.py"
  - "tests/operations/test_report_release_notes.py"
  - "tests/operations/test_request_release_child.py"
  - "tests/operations/test_request_state_exits.py"
  - "tests/operations/test_resolve_recipient.py"
  - "tests/operations/test_retract.py"
  - "tests/operations/test_rm.py"
  - "tests/operations/test_rm_by_name.py"
  - "tests/operations/test_rm_cascade.py"
  - "tests/operations/test_run_gather.py"
  - "tests/operations/test_runs_document.py"
  - "tests/operations/test_send.py"
  - "tests/operations/test_send_note.py"
  - "tests/operations/test_served.py"
  - "tests/operations/test_set_up_checks.py"
  - "tests/operations/test_set_up_outcomes.py"
  - "tests/operations/test_set_up_remove.py"
  - "tests/operations/test_set_up_remove_request.py"
  - "tests/operations/test_set_up_rules.py"
  - "tests/operations/test_set_up_validation.py"
  - "tests/operations/test_standing.py"
  - "tests/operations/test_status.py"
  - "tests/operations/test_status_calls.py"
  - "tests/operations/test_status_matches_handle_pause.py"
  - "tests/operations/test_status_names.py"
  - "tests/operations/test_status_placement.py"
  - "tests/operations/test_status_requests.py"
  - "tests/operations/test_status_runs.py"
  - "tests/operations/test_status_runs_document.py"
  - "tests/operations/test_status_scope.py"
  - "tests/operations/test_status_sessions.py"
  - "tests/operations/test_status_sweep.py"
  - "tests/operations/test_status_waiting.py"
  - "tests/operations/test_wake_after_send.py"
  - "tests/operations/test_wake_status.py"
  - "tests/operations/test_withdraw.py"
  - "tests/operations/wake_run_support.py"
  - "tests/operations/wake_send_support.py"
  - "tests/program/flow_support.py"
  - "tests/scripts/test_update_live.py"
  - "tests/store/decision_support.py"
  - "tests/store/message_support.py"
  - "tests/store/release_support.py"
  - "tests/store/schema_11.py"
  - "tests/store/seed.py"
  - "tests/store/test_acting_machine.py"
  - "tests/store/test_checkouts.py"
  - "tests/store/test_machines.py"
  - "tests/store/test_member_names.py"
  - "tests/store/test_member_removal.py"
  - "tests/store/test_members_queried_in_one_place.py"
  - "tests/store/test_message_cascade.py"
  - "tests/store/test_message_sweep.py"
  - "tests/store/test_migration_012.py"
  - "tests/store/test_migrations.py"
  - "tests/store/test_old_wake_column.py"
  - "tests/store/test_programs.py"
  - "tests/store/test_schema.py"
  - "tests/store/test_schema_holds_no_mirrored_state.py"
  - "tests/store/test_wake_on_checkout.py"
  - "tests/store/test_wakes.py"
  - "tests/store/wake_support.py"
  - "tests/test_cf_ids_never_member_ids.py"
  - "tests/test_ci_gates_load.py"
  - "tests/test_contract_docs.py"
  - "tests/test_import_boundaries.py"
  - "tests/test_message_timing.py"
  - "tests/test_read_side_defined_once.py"
  - "tests/test_report_release_sweep.py"
  - "tests/test_wiring.py"
  - "tests/test_wiring_release.py"
  - "tests/test_wiring_results.py"
  - "tests/upstream/context_forge/test_project_of.py"
  - "tests/upstream/context_forge/test_projects.py"
  - "tests/upstream/test_git_read.py"
  - "tests/wire/test_protocol.py"
effort: xhigh
turns: 76
promptTokens: 6618987
cachedTokens: 6379539
cacheWriteTokens: 239364
completionTokens: 105025
durationSeconds: 466.6
costUsd: 0.686034
costBasis: provider
runId: run-20261123-p6-ca3ac353
squadronVersion: 0.24.37
categoriesNormalized: true
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "`restore` overwrites the live store before it checks the backup"
    location: "scripts/update_live.py:224"
  - id: F002
    severity: concern
    category: correctness
    summary: "Two renames to one name in one request surface as a raw store error"
    location: "src/amoeba/operations/set_up_resolve.py:172"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "Naming's fallback to the member's id is silent"
    location: "src/amoeba/operations/naming.py:104"
  - id: F004
    severity: concern
    category: error-handling-observability
    summary: "The update's failure handler drops the traceback"
    location: "scripts/update_live.py:310"
  - id: F005
    severity: concern
    category: security-hygiene
    summary: "A test helper builds SQL from a runtime table name"
    location: "tests/store/schema_11.py:124"
  - id: F006
    severity: note
    category: correctness
    summary: "`name_by_id`'s \"cannot clash\" claim ignores the case-insensitive index"
    location: "src/amoeba/operations/name_by_id.py:32"
  - id: F007
    severity: note
    category: security-hygiene
    summary: "The hub's `add` relies on a client-side check for `wake_command`"
    location: "src/amoeba/operations/add_door.py:56"
  - id: F008
    severity: note
    category: correctness
    summary: "Writes made during the update are lost on a restore, and the docstring does not say so"
    location: "scripts/update_live.py:162"
  - id: F009
    severity: note
    category: security-hygiene
    summary: "Wake commands are logged verbatim"
    location: "src/amoeba/operations/naming.py:182"
  - id: F010
    severity: note
    category: architectural-decay
    summary: "`SELECT_MACHINE_NAME` is defined twice"
    location: "src/amoeba/store/sql_checkouts.py:54"
  - id: F011
    severity: note
    category: architectural-decay
    summary: "`store/sql.py` is 543 lines"
    location: "src/amoeba/store/sql.py"
  - id: F012
    severity: note
    category: documentation-drift
    summary: "Docstrings and an import guard still name the removed `project_names`"
    location: "tests/upstream/context_forge/test_projects.py:1"
  - id: F013
    severity: note
    category: performance-resource
    summary: "A hung mount can block naming before the time budget applies"
    location: "src/amoeba/operations/naming.py:58"
  - id: F014
    severity: note
    category: type-contract-debt
    summary: "`name_is_taken` returns `Member | bool`"
    location: "src/amoeba/operations/add_names.py:27"
  - id: F015
    severity: pass
    category: correctness
    summary: "Migration 012's foreign keys and column order check out"
    location: "src/amoeba/store/schema/012_members_by_name.sql:29"
  - id: F016
    severity: pass
    category: performance-resource
    summary: "No `cf` or `git` call runs inside a write transaction"
    location: "src/amoeba/operations/naming.py:203"
  - id: F017
    severity: pass
    category: security-hygiene
    summary: "Origin input is checked at the trust boundary"
    location: "src/amoeba/operations/here_document.py:44"
---

# Review: code — slice 261

**Verdict:** FAIL
**Model:** claude-haiku-5-5
**Diff:** truncated: 0 of 1014565 characters reached the model
  - scripts/update_live.py: omitted (0 of 11034 characters)
  - src/amoeba/cli/commands.py: omitted (0 of 2875 characters)
  - src/amoeba/cli/registration_arguments.py: omitted (0 of 3109 characters)
  - src/amoeba/cli/render/dispatch.py: omitted (0 of 1509 characters)
  - src/amoeba/cli/render/messages.py: omitted (0 of 904 characters)
  - src/amoeba/cli/render/registration.py: omitted (0 of 5444 characters)
  - src/amoeba/cli/render/registry.py: omitted (0 of 4222 characters)
  - src/amoeba/cli/render/releases.py: omitted (0 of 484 characters)
  - src/amoeba/cli/render/text.py: omitted (0 of 994 characters)
  - src/amoeba/client/call.py: omitted (0 of 1584 characters)
  - src/amoeba/hub/admin.py: omitted (0 of 526 characters)
  - src/amoeba/hub/calls.py: omitted (0 of 3367 characters)
  - src/amoeba/hub/store_open.py: omitted (0 of 985 characters)
  - src/amoeba/mcp/tools.py: omitted (0 of 2232 characters)
  - src/amoeba/operations/add.py: omitted (0 of 11402 characters)
  - src/amoeba/operations/add_gather.py: omitted (0 of 2136 characters)
  - src/amoeba/operations/add_member.py: omitted (0 of 11841 characters)
  - src/amoeba/operations/add_names.py: omitted (0 of 2073 characters)
  - src/amoeba/operations/add_origin.py: omitted (0 of 2478 characters)
  - src/amoeba/operations/caller.py: omitted (0 of 3003 characters)
  - src/amoeba/operations/cancel.py: omitted (0 of 1801 characters)
  - src/amoeba/operations/cf_readers.py: omitted (0 of 1914 characters)
  - src/amoeba/operations/changes.py: omitted (0 of 4696 characters)
  - src/amoeba/operations/changes_models.py: omitted (0 of 549 characters)
  - src/amoeba/operations/decisions.py: omitted (0 of 4616 characters)
  - src/amoeba/operations/deps.py: omitted (0 of 2467 characters)
  - src/amoeba/operations/errors.py: omitted (0 of 1504 characters)
  - src/amoeba/operations/handle_pause.py: omitted (0 of 514 characters)
  - src/amoeba/operations/here.py: omitted (0 of 4578 characters)
  - src/amoeba/operations/here_document.py: omitted (0 of 3478 characters)
  - src/amoeba/operations/inbox.py: omitted (0 of 1767 characters)
  - src/amoeba/operations/list_registry.py: omitted (0 of 13582 characters)
  - src/amoeba/operations/list_view.py: omitted (0 of 7768 characters)
  - src/amoeba/operations/member_reference.py: omitted (0 of 1653 characters)
  - src/amoeba/operations/members.py: omitted (0 of 2053 characters)
  - src/amoeba/operations/message_member.py: omitted (0 of 8274 characters)
  - src/amoeba/operations/name_by_id.py: omitted (0 of 2481 characters)
  - src/amoeba/operations/naming.py: omitted (0 of 8095 characters)
  - src/amoeba/operations/origin.py: omitted (0 of 4071 characters)
  - src/amoeba/operations/pause_claim.py: omitted (0 of 432 characters)
  - src/amoeba/operations/pause_context.py: omitted (0 of 4202 characters)
  - src/amoeba/operations/pause_eligibility.py: omitted (0 of 5264 characters)
  - src/amoeba/operations/pause_results.py: omitted (0 of 484 characters)
  - src/amoeba/operations/program_sources.py: omitted (0 of 2615 characters)
  - src/amoeba/operations/project_lookup.py: omitted (0 of 1757 characters)
  - src/amoeba/operations/question_sweep_scope.py: omitted (0 of 4150 characters)
  - src/amoeba/operations/release_member.py: omitted (0 of 2368 characters)
  - src/amoeba/operations/reply.py: omitted (0 of 1843 characters)
  - src/amoeba/operations/report_release.py: omitted (0 of 2979 characters)
  - src/amoeba/operations/rm.py: omitted (0 of 11187 characters)
  - src/amoeba/operations/run_gather.py: omitted (0 of 8422 characters)
  - src/amoeba/operations/runs_document.py: omitted (0 of 9161 characters)
  - src/amoeba/operations/send.py: omitted (0 of 3659 characters)
  - src/amoeba/operations/served.py: omitted (0 of 13901 characters)
  - src/amoeba/operations/served_runners.py: omitted (0 of 7427 characters)
  - src/amoeba/operations/served_types.py: omitted (0 of 3359 characters)
  - src/amoeba/operations/set_up.py: omitted (0 of 12817 characters)
  - src/amoeba/operations/set_up_models.py: omitted (0 of 4535 characters)
  - src/amoeba/operations/set_up_plan.py: omitted (0 of 3106 characters)
  - src/amoeba/operations/set_up_remove.py: omitted (0 of 1927 characters)
  - src/amoeba/operations/set_up_remove_resolve.py: omitted (0 of 2303 characters)
  - src/amoeba/operations/set_up_resolve.py: omitted (0 of 14828 characters)
  - src/amoeba/operations/set_up_state.py: omitted (0 of 4641 characters)
  - src/amoeba/operations/set_up_wake.py: omitted (0 of 2543 characters)
  - src/amoeba/operations/standing.py: omitted (0 of 4195 characters)
  - src/amoeba/operations/state_move.py: omitted (0 of 1650 characters)
  - src/amoeba/operations/status.py: omitted (0 of 13008 characters)
  - src/amoeba/operations/status_calls.py: omitted (0 of 3034 characters)
  - src/amoeba/operations/status_local.py: omitted (0 of 2379 characters)
  - src/amoeba/operations/status_models.py: omitted (0 of 725 characters)
  - src/amoeba/operations/status_placement.py: omitted (0 of 6227 characters)
  - src/amoeba/operations/status_requests.py: omitted (0 of 3185 characters)
  - src/amoeba/operations/status_runs.py: omitted (0 of 5591 characters)
  - src/amoeba/operations/status_waiting.py: omitted (0 of 2618 characters)
  - src/amoeba/operations/wake.py: omitted (0 of 3694 characters)
  - src/amoeba/operations/wake_door.py: omitted (0 of 2319 characters)
  - src/amoeba/operations/wake_status.py: omitted (0 of 979 characters)
  - src/amoeba/store/checkouts.py: omitted (0 of 7063 characters)
  - src/amoeba/store/machines.py: omitted (0 of 2189 characters)
  - src/amoeba/store/member_names.py: omitted (0 of 3558 characters)
  - src/amoeba/store/migrations.py: omitted (0 of 611 characters)
  - src/amoeba/store/models.py: omitted (0 of 1291 characters)
  - src/amoeba/store/programs.py: omitted (0 of 4463 characters)
  - src/amoeba/store/schema/012_members_by_name.sql: omitted (0 of 2411 characters)
  - src/amoeba/store/sql.py: omitted (0 of 4689 characters)
  - src/amoeba/store/sql_checkouts.py: omitted (0 of 3483 characters)
  - src/amoeba/store/vocabulary.py: omitted (0 of 1077 characters)
  - src/amoeba/store/wakes.py: omitted (0 of 6584 characters)
  - src/amoeba/upstream/context_forge/project_of.py: omitted (0 of 2940 characters)
  - src/amoeba/upstream/context_forge/projects.py: omitted (0 of 1359 characters)
  - src/amoeba/upstream/git_read.py: omitted (0 of 2809 characters)
  - src/amoeba/wire/protocol.py: omitted (0 of 2842 characters)
  - src/amoeba/wiring.py: omitted (0 of 5239 characters)
  - src/amoeba/wiring_door.py: omitted (0 of 3811 characters)
  - src/amoeba/wiring_gather.py: omitted (0 of 4135 characters)
  - src/amoeba/wiring_messages.py: omitted (0 of 3570 characters)
  - src/amoeba/wiring_presence.py: omitted (0 of 1672 characters)
  - src/amoeba/wiring_registry.py: omitted (0 of 1688 characters)
  - src/amoeba/wiring_releases.py: omitted (0 of 1972 characters)
  - tests/answering/test_default_rules_reads.py: omitted (0 of 578 characters)
  - tests/cli/cli_support.py: omitted (0 of 3565 characters)
  - tests/cli/message_cli_support.py: omitted (0 of 570 characters)
  - tests/cli/render/test_registration.py: omitted (0 of 5969 characters)
  - tests/cli/render/test_registry.py: omitted (0 of 8242 characters)
  - tests/cli/render/test_releases.py: omitted (0 of 1636 characters)
  - tests/cli/render/test_status_requests.py: omitted (0 of 725 characters)
  - tests/cli/requests_support.py: omitted (0 of 1191 characters)
  - tests/cli/test_add_cli.py: omitted (0 of 5441 characters)
  - tests/cli/test_add_secrets_cli.py: omitted (0 of 2827 characters)
  - tests/cli/test_add_wake_command_cli.py: omitted (0 of 1588 characters)
  - tests/cli/test_hold_release_cli.py: omitted (0 of 1159 characters)
  - tests/cli/test_inbox_cli.py: omitted (0 of 1513 characters)
  - tests/cli/test_legacy_move_cli.py: omitted (0 of 1479 characters)
  - tests/cli/test_list_cli.py: omitted (0 of 3325 characters)
  - tests/cli/test_pause_cli.py: omitted (0 of 1684 characters)
  - tests/cli/test_read_side_cli.py: omitted (0 of 2062 characters)
  - tests/cli/test_release_cli.py: omitted (0 of 1881 characters)
  - tests/cli/test_reply_cli.py: omitted (0 of 988 characters)
  - tests/cli/test_requests_scenario.py: omitted (0 of 2750 characters)
  - tests/cli/test_rm_cli.py: omitted (0 of 4498 characters)
  - tests/cli/test_send_cli.py: omitted (0 of 1363 characters)
  - tests/cli/test_send_note_cli.py: omitted (0 of 1004 characters)
  - tests/cli/test_standing_cli.py: omitted (0 of 4775 characters)
  - tests/hub/call_support.py: omitted (0 of 1407 characters)
  - tests/hub/test_admin.py: omitted (0 of 3460 characters)
  - tests/hub/test_app.py: omitted (0 of 1010 characters)
  - tests/hub/test_chain.py: omitted (0 of 4944 characters)
  - tests/hub/test_clients_fixture.py: omitted (0 of 3748 characters)
  - tests/hub/test_door_client.py: omitted (0 of 9694 characters)
  - tests/hub/test_door_operations.py: omitted (0 of 10374 characters)
  - tests/hub/test_handle_call.py: omitted (0 of 2044 characters)
  - tests/hub/test_join.py: omitted (0 of 1149 characters)
  - tests/hub/test_joined_entry_points.py: omitted (0 of 532 characters)
  - tests/hub/test_members_door.py: omitted (0 of 13685 characters)
  - tests/hub/test_two_machines.py: omitted (0 of 784 characters)
  - tests/hub_clients.py: omitted (0 of 5666 characters)
  - tests/hub_fixture.py: omitted (0 of 5678 characters)
  - tests/live/messaging/repos.py: omitted (0 of 659 characters)
  - tests/live/messaging/test_two_machines_live.py: omitted (0 of 7269 characters)
  - tests/live/pause/harness.py: omitted (0 of 688 characters)
  - tests/live/program/consumer.py: omitted (0 of 442 characters)
  - tests/load/messages_worker.py: omitted (0 of 739 characters)
  - tests/load/test_door_load.py: omitted (0 of 5884 characters)
  - tests/load/test_messages_load.py: omitted (0 of 4042 characters)
  - tests/load/test_no_cf_under_write_lock.py: omitted (0 of 1728 characters)
  - tests/load/test_report_release_load.py: omitted (0 of 897 characters)
  - tests/load/test_wake_claim_load.py: omitted (0 of 2370 characters)
  - tests/mcp_server/presence_rig.py: omitted (0 of 1117 characters)
  - tests/mcp_server/test_call_tool.py: omitted (0 of 612 characters)
  - tests/mcp_server/test_in_process.py: omitted (0 of 1397 characters)
  - tests/mcp_server/test_message_tools.py: omitted (0 of 1301 characters)
  - tests/mcp_server/test_note_push.py: omitted (0 of 1965 characters)
  - tests/mcp_server/test_presence.py: omitted (0 of 1583 characters)
  - tests/mcp_server/test_presence_serving.py: omitted (0 of 1131 characters)
  - tests/mcp_server/test_release_tools.py: omitted (0 of 4074 characters)
  - tests/operations/add_placed.py: omitted (0 of 1443 characters)
  - tests/operations/gather_rig.py: omitted (0 of 2189 characters)
  - tests/operations/held_support.py: omitted (0 of 568 characters)
  - tests/operations/list_support.py: omitted (0 of 723 characters)
  - tests/operations/message_placed.py: omitted (0 of 2179 characters)
  - tests/operations/message_support.py: omitted (0 of 2970 characters)
  - tests/operations/pause_support.py: omitted (0 of 3077 characters)
  - tests/operations/program_rig.py: omitted (0 of 4353 characters)
  - tests/operations/release_placed.py: omitted (0 of 1438 characters)
  - tests/operations/release_support.py: omitted (0 of 1867 characters)
  - tests/operations/reply_worker.py: omitted (0 of 534 characters)
  - tests/operations/rm_placed.py: omitted (0 of 1113 characters)
  - tests/operations/runs_doc_support.py: omitted (0 of 3009 characters)
  - tests/operations/set_up_support.py: omitted (0 of 6908 characters)
  - tests/operations/standing_support.py: omitted (0 of 847 characters)
  - tests/operations/status_placed.py: omitted (0 of 1976 characters)
  - tests/operations/status_support.py: omitted (0 of 1755 characters)
  - tests/operations/test_add.py: omitted (0 of 9474 characters)
  - tests/operations/test_add_by_checkout.py: omitted (0 of 6754 characters)
  - tests/operations/test_add_gather.py: omitted (0 of 3844 characters)
  - tests/operations/test_add_member.py: omitted (0 of 16980 characters)
  - tests/operations/test_add_wake_command.py: omitted (0 of 4559 characters)
  - tests/operations/test_answering_settle.py: omitted (0 of 501 characters)
  - tests/operations/test_caller.py: omitted (0 of 6235 characters)
  - tests/operations/test_cancel.py: omitted (0 of 1102 characters)
  - tests/operations/test_changes.py: omitted (0 of 3862 characters)
  - tests/operations/test_decisions.py: omitted (0 of 9684 characters)
  - tests/operations/test_handle_pause.py: omitted (0 of 1803 characters)
  - tests/operations/test_handle_pause_registers.py: omitted (0 of 2331 characters)
  - tests/operations/test_held_question_exits.py: omitted (0 of 1565 characters)
  - tests/operations/test_here.py: omitted (0 of 7612 characters)
  - tests/operations/test_here_document.py: omitted (0 of 3050 characters)
  - tests/operations/test_inbox.py: omitted (0 of 938 characters)
  - tests/operations/test_inbox_notes.py: omitted (0 of 680 characters)
  - tests/operations/test_list_members.py: omitted (0 of 3220 characters)
  - tests/operations/test_list_registry.py: omitted (0 of 11504 characters)
  - tests/operations/test_list_standing.py: omitted (0 of 2761 characters)
  - tests/operations/test_list_view.py: omitted (0 of 1862 characters)
  - tests/operations/test_mark_read.py: omitted (0 of 1463 characters)
  - tests/operations/test_member_answering.py: omitted (0 of 391 characters)
  - tests/operations/test_members.py: omitted (0 of 3508 characters)
  - tests/operations/test_message_member.py: omitted (0 of 10999 characters)
  - tests/operations/test_message_names.py: omitted (0 of 4491 characters)
  - tests/operations/test_message_sweep_wrapper.py: omitted (0 of 1977 characters)
  - tests/operations/test_naming.py: omitted (0 of 16790 characters)
  - tests/operations/test_origin.py: omitted (0 of 3865 characters)
  - tests/operations/test_pause_cf_ids.py: omitted (0 of 4242 characters)
  - tests/operations/test_pause_eligibility.py: omitted (0 of 2607 characters)
  - tests/operations/test_program_sources.py: omitted (0 of 1946 characters)
  - tests/operations/test_prune.py: omitted (0 of 1702 characters)
  - tests/operations/test_prune_wiring.py: omitted (0 of 1618 characters)
  - tests/operations/test_release_names.py: omitted (0 of 3036 characters)
  - tests/operations/test_release_notes.py: omitted (0 of 844 characters)
  - tests/operations/test_release_notes_match_changes.py: omitted (0 of 1167 characters)
  - tests/operations/test_reply.py: omitted (0 of 1633 characters)
  - tests/operations/test_reply_concurrent.py: omitted (0 of 1510 characters)
  - tests/operations/test_report_release.py: omitted (0 of 1010 characters)
  - tests/operations/test_report_release_notes.py: omitted (0 of 1034 characters)
  - tests/operations/test_request_release_child.py: omitted (0 of 1218 characters)
  - tests/operations/test_request_state_exits.py: omitted (0 of 1976 characters)
  - tests/operations/test_resolve_recipient.py: omitted (0 of 4099 characters)
  - tests/operations/test_retract.py: omitted (0 of 1666 characters)
  - tests/operations/test_rm.py: omitted (0 of 7241 characters)
  - tests/operations/test_rm_by_name.py: omitted (0 of 6303 characters)
  - tests/operations/test_rm_cascade.py: omitted (0 of 851 characters)
  - tests/operations/test_run_gather.py: omitted (0 of 8994 characters)
  - tests/operations/test_runs_document.py: omitted (0 of 4764 characters)
  - tests/operations/test_send.py: omitted (0 of 1767 characters)
  - tests/operations/test_send_note.py: omitted (0 of 729 characters)
  - tests/operations/test_served.py: omitted (0 of 10263 characters)
  - tests/operations/test_set_up_checks.py: omitted (0 of 4366 characters)
  - tests/operations/test_set_up_outcomes.py: omitted (0 of 3056 characters)
  - tests/operations/test_set_up_remove.py: omitted (0 of 5548 characters)
  - tests/operations/test_set_up_remove_request.py: omitted (0 of 1492 characters)
  - tests/operations/test_set_up_rules.py: omitted (0 of 2644 characters)
  - tests/operations/test_set_up_validation.py: omitted (0 of 4394 characters)
  - tests/operations/test_standing.py: omitted (0 of 4603 characters)
  - tests/operations/test_status.py: omitted (0 of 3698 characters)
  - tests/operations/test_status_calls.py: omitted (0 of 2314 characters)
  - tests/operations/test_status_matches_handle_pause.py: omitted (0 of 1656 characters)
  - tests/operations/test_status_names.py: omitted (0 of 2156 characters)
  - tests/operations/test_status_placement.py: omitted (0 of 11553 characters)
  - tests/operations/test_status_requests.py: omitted (0 of 1673 characters)
  - tests/operations/test_status_runs.py: omitted (0 of 13949 characters)
  - tests/operations/test_status_runs_document.py: omitted (0 of 6646 characters)
  - tests/operations/test_status_scope.py: omitted (0 of 1911 characters)
  - tests/operations/test_status_sessions.py: omitted (0 of 2037 characters)
  - tests/operations/test_status_sweep.py: omitted (0 of 3116 characters)
  - tests/operations/test_status_waiting.py: omitted (0 of 1361 characters)
  - tests/operations/test_wake_after_send.py: omitted (0 of 3093 characters)
  - tests/operations/test_wake_status.py: omitted (0 of 3106 characters)
  - tests/operations/test_withdraw.py: omitted (0 of 1283 characters)
  - tests/operations/wake_run_support.py: omitted (0 of 788 characters)
  - tests/operations/wake_send_support.py: omitted (0 of 1457 characters)
  - tests/program/flow_support.py: omitted (0 of 1925 characters)
  - tests/scripts/test_update_live.py: omitted (0 of 15116 characters)
  - tests/store/decision_support.py: omitted (0 of 1598 characters)
  - tests/store/message_support.py: omitted (0 of 1202 characters)
  - tests/store/release_support.py: omitted (0 of 1133 characters)
  - tests/store/schema_11.py: omitted (0 of 4817 characters)
  - tests/store/seed.py: omitted (0 of 1814 characters)
  - tests/store/test_acting_machine.py: omitted (0 of 2631 characters)
  - tests/store/test_checkouts.py: omitted (0 of 8297 characters)
  - tests/store/test_machines.py: omitted (0 of 715 characters)
  - tests/store/test_member_names.py: omitted (0 of 5232 characters)
  - tests/store/test_member_removal.py: omitted (0 of 1264 characters)
  - tests/store/test_members_queried_in_one_place.py: omitted (0 of 1280 characters)
  - tests/store/test_message_cascade.py: omitted (0 of 591 characters)
  - tests/store/test_message_sweep.py: omitted (0 of 1067 characters)
  - tests/store/test_migration_012.py: omitted (0 of 5160 characters)
  - tests/store/test_migrations.py: omitted (0 of 809 characters)
  - tests/store/test_old_wake_column.py: omitted (0 of 1732 characters)
  - tests/store/test_programs.py: omitted (0 of 4008 characters)
  - tests/store/test_schema.py: omitted (0 of 279 characters)
  - tests/store/test_schema_holds_no_mirrored_state.py: omitted (0 of 1524 characters)
  - tests/store/test_wake_on_checkout.py: omitted (0 of 4420 characters)
  - tests/store/test_wakes.py: omitted (0 of 4066 characters)
  - tests/store/wake_support.py: omitted (0 of 2809 characters)
  - tests/test_cf_ids_never_member_ids.py: omitted (0 of 2128 characters)
  - tests/test_ci_gates_load.py: omitted (0 of 3590 characters)
  - tests/test_contract_docs.py: omitted (0 of 543 characters)
  - tests/test_import_boundaries.py: omitted (0 of 4706 characters)
  - tests/test_message_timing.py: omitted (0 of 8132 characters)
  - tests/test_read_side_defined_once.py: omitted (0 of 1036 characters)
  - tests/test_report_release_sweep.py: omitted (0 of 1868 characters)
  - tests/test_wiring.py: omitted (0 of 5776 characters)
  - tests/test_wiring_release.py: omitted (0 of 2804 characters)
  - tests/test_wiring_results.py: omitted (0 of 1110 characters)
  - tests/upstream/context_forge/test_project_of.py: omitted (0 of 1594 characters)
  - tests/upstream/context_forge/test_projects.py: omitted (0 of 2449 characters)
  - tests/upstream/test_git_read.py: omitted (0 of 2587 characters)
  - tests/wire/test_protocol.py: omitted (0 of 1960 characters)
**Evidence:** 71 successful tool call(s) of 75 made; 0 of 1014565 diff characters reached the model

## Findings

### [FAIL] `restore` overwrites the live store before it checks the backup

`restore()` copies the backup's store over `store_path()` (line 226) and its config (227) before it reads `PREVIOUS_VERSION` (228). `take_backup()` writes that file last (168), so a backup whose take was interrupted has no version file, and its store copy may be partial (166). `restore` then overwrites the live store with that file, and `copy_database` writes into the live store page by page, so a copy that fails partway leaves no guarantee the live store is intact. The script then dies with an uncaught `FileNotFoundError`, because `main` catches only `UpdateError` (423).

The same state stalls the next `update`: `reusable_backup()` reads that file without checking it exists (274), so every later run crashes. The natural next step is `restore`, which picks the same directory (`newest_backup`, 234). Nothing in the script clears the directory, so the only way out is deleting files by hand. That breaks the Amoeba rule that every state has an exit.

The tool should validate the backup before it writes anything: the version file exists, the store opens, `integrity_check` is `ok`, and the schema is one it knows. Only then should it copy. `restore` also reads its target from the environment (`store_path()`), where the sql.md rule asks maintenance tools to take an explicit argument. The kill tests (`tests/scripts/test_update_live.py:498` and `:533`) cover a kill after the migration and a kill before it, but not a kill during `take_backup`. This finding rests on reading the code; I did not run it.

### [CONCERN] Two renames to one name in one request surface as a raw store error

`resolve_request` checks each rename with `_rename` against committed names only (173). Nothing records names that an earlier entry in the same request claims. Two entries that rename two members to the same free name both pass. `apply` then writes the first rename, and the second hits `members_active_name` (set_up.py:160-161). `Transaction.execute` turns that into a `StoreIntegrityError`, the write rolls back, and the caller sees a store error with a logged traceback instead of a `NAME_TAKEN` refusal. A rename that takes the name a new member is being given fails the same way. Nothing is corrupted, but the one free-or-taken rule is bypassed for bulk requests. No test covers two renames in one request. Track claimed names in `resolve_request` and refuse them as `NAME_TAKEN`.

### [CONCERN] Naming's fallback to the member's id is silent

`_name_for` returns the project id with no log line in three cases: cf does not list the project (115), the cf name fails `is_member_name` (114-115), or another active member holds the name (118-121). The origin fallback in the same module logs a warning (134-138), and `name_by_id` logs each id it uses (name_by_id.py:42). A user whose `list` shows opaque ids gets no explanation in the log. Log each fallback with its reason.

### [CONCERN] The update's failure handler drops the traceback

`update()` catches `Exception`, restores, and re-raises `UpdateError ... from error` (315-317). The `noqa` comment calls this the process boundary, but `update()` is not one; `main()` is. The handler does not log the exception, and `main` prints only `str(error)` (424), so the failing frame is lost. That frame is what an operator needs to diagnose a failed migration. Print or log the traceback to stderr before the restore.

### [CONCERN] A test helper builds SQL from a runtime table name

`row_counts` builds `SELECT COUNT(*) FROM {table}` from names read out of `sqlite_master`. The Amoeba rule "SQL composes from constants only" allows f-strings only over module-level constants, never runtime values. The input here is trusted, so this is a rule breach, not an injection risk. `store/sql.py:47-54` already has `count_rows` and `select_all_rows` for this job, so the helper should use them. Those two functions use the same runtime-table pattern, so the rule's wording may need an explicit exception for `sqlite_master` identifiers.

### [NOTE] `name_by_id`'s "cannot clash" claim ignores the case-insensitive index

Names compare case-insensitively (the index collation is NOCASE), but ids compare case-sensitively. Two unnamed members whose ids differ only by case, such as `Abc` and `abc`, would make the second write fail, and hub start fails with it, because `open_hub_store` calls `name_by_id` (store_open.py:92). The fixtures use lowercase ids, so this is unlikely, but the docstring's guarantee is false. The function also does not check that an id meets the name pattern, which `naming._name_for` does for cf names. Check both, or correct the docstring.

### [NOTE] The hub's `add` relies on a client-side check for `wake_command`

`refuse_door_fields` runs only on the client (`add_gather.py:38`, reached from `wiring_gather.py:62`). The hub's served `add` never sees the door and does not repeat the check, so a hand-built request to the hub can set a wake command on the caller's own checkout. The docstring says the check "rejects a call that passes it anyway," which holds only on the client. The CLI can set wake commands anyway, so the practical exposure is small. If the refusal is meant as a boundary, the hub needs the check too.

### [NOTE] Writes made during the update are lost on a restore, and the docstring does not say so

`take_backup` runs before the install, the migration and the read-back. Running `amoeba-mcp` servers keep writing throughout (they are only listed at the end, 426-429). A failed read-back calls `restore`, which overwrites the live store and discards every write made in between. The docstring says the update "restores automatically" and does not mention this. Say so in the docstring.

### [NOTE] Wake commands are logged verbatim

`_retire_wake_command` logs the command with `%r` at WARNING, and `name_by_id.py:47-51` does the same. A command can carry an inline credential, such as a webhook URL with a token, and the log keeps it. The same module reduces git addresses so that passwords stay out of logs. Either redact the command in the log, or record that these commands are the PM's own and may be logged.

### [NOTE] `SELECT_MACHINE_NAME` is defined twice

The same query text is in `sql_machines.py:41`, and `checkouts.py:198` uses the copy in `sql_checkouts`. `sql_checkouts` can import `sql_machines` without a cycle, so use that constant.

### [NOTE] `store/sql.py` is 543 lines

The guidance is about 300 lines. The slice already split out `sql_checkouts.py` and `member_names.py`, and the members section could follow the same pattern. `add_member.py` (305), `programs.py` (313) and `set_up_resolve.py` (313) are also just over.

### [NOTE] Docstrings and an import guard still name the removed `project_names`

The task file removed `projects.project_names`, but this module's docstring still says it tests that function. The test imports only `project_details`, so it runs. `tests/test_import_boundaries.py:244` still lists the removed name in `CF_CALL_FUNCTIONS`. Update both.

### [NOTE] A hung mount can block naming before the time budget applies

`_gather_origins` bounds the git time, but `here.git_root(path)` runs first and calls `path.resolve()` and `.exists()` (here.py:78-80) with no bound. Those stats can hang on a stale network mount, which the naming docstring names as a case to handle. I have not verified this on a real mount; a bound would need a thread or a timeout on the stat.

### [NOTE] `name_is_taken` returns `Member | bool`

Callers branch on `is not False` (add_names.py:46), on `isinstance(taken, Member)` (add_member.py:245), and on truthiness (add_member.py:248). Return a small result type with explicit kinds, so changing one return value cannot quietly change the others.

### [PASS] Migration 012's foreign keys and column order check out

`members.project_id` is the primary key (001_baseline.sql:20), so the `checkouts` foreign key is valid. `_MEMBER_COLUMNS` (sql.py:93-96) matches the indexes `member_from_row` reads (8 `rules_from`, 9 `name`, 10 `origin`). The 11 bind values in `upsert_member` (programs.py:207-221) match `_MEMBER_INSERT_COLUMNS`. `removed_at IS NOT NULL` yields an integer that `unnamed_members` reads with `integer()`. `RTRIM` in SQL and `rstrip("/")` in Python agree (sql_checkouts.py:42, checkouts.py:175). `test_migration_012.py` runs against a real schema-11 store with legacy rows.

### [PASS] No `cf` or `git` call runs inside a write transaction

`name_members` reads, then calls `cf` and `git`, then writes (203-215). `add` gathers before its write (add.py:174, add_gather.py:48). `test_no_cf_or_git_runs_while_the_write_lock_is_held` (tests/operations/test_naming.py:353) guards this.

### [PASS] Origin input is checked at the trust boundary

The `HereCheckout` `origin` validator runs `is_reduced_origin` on every parsed `here` document (44-49). The checkout's machine comes from the token (`store.act_as`, hub/calls.py). `set_checkout_wake_command` checks the machine against the acting one (checkouts.py:190-204), and `rm --checkout` deletes only the acting machine's rows (rm.py:141). The deleted modules `operations/member_reference.py`, `members.py` and `project_lookup.py` have no remaining importers in `src` or `tests`.

### Run Digest

- Response length: 22430 chars
- Response is newline-free: no
- Tool calls made: 75
- Tool calls failed: 4
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 76
- Tokens — prompt / cached / cache write / completion / reasoning: 6618987 / 6379539 / 239364 / 105025 / not computed
- Duration: 466.6 s
- Cost: $0.69 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17
