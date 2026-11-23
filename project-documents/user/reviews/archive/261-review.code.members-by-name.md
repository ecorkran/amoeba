---
docType: review
layer: project
reviewType: code
slice: members-by-name
conventionsSource: AGENTS.md
projectRules: [general.md, python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/261-slice.members-by-name.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261123
dateUpdated: 20261123
reviewedSha: 8038ab876ed56c1e12a914d4953a64e75d86df01
reviewedBlob: 15a494270f008458be5eda5a31dee428b060cb70
reviewedBlobCurrent: true
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 59
injected:
  - key: conventions
    path: "AGENTS.md"
    chars: 24525
    sha256: 2387512002bb2a73aa247bc36bc98d7162c5b5110ded41f56319d098d282ddbc
    whole: true
filesRead:
  - ".git/HEAD"
  - "src/amoeba/store/schema/012_members_by_name.sql"
  - "src/amoeba/store/member_names.py"
  - "src/amoeba/store/migrations.py"
  - "scripts/update_live.py"
  - "src/amoeba/store/sql.py"
  - "src/amoeba/operations/naming.py"
  - "src/amoeba/store/checkouts.py"
  - "src/amoeba/store/sql_checkouts.py"
  - "src/amoeba/operations/add.py"
  - "src/amoeba/operations/add_names.py"
  - "src/amoeba/operations/origin.py"
  - "src/amoeba/operations/add_member.py"
  - "src/amoeba/operations/rm.py"
  - "src/amoeba/operations/add_origin.py"
  - "src/amoeba/operations/caller.py"
  - "src/amoeba/store/models.py"
  - "src/amoeba/store/programs.py"
  - "src/amoeba/operations/set_up_plan.py"
  - "src/amoeba/operations/name_by_id.py"
  - "src/amoeba/operations/set_up.py"
  - "src/amoeba/operations/set_up_resolve.py"
  - "src/amoeba/operations/state_move.py"
  - "tests/scripts/test_update_live.py"
  - "tests/store/test_migration_012.py"
  - "src/amoeba/operations/add_door.py"
  - "src/amoeba/operations/add_gather.py"
  - "src/amoeba/cli/registration_arguments.py"
  - "src/amoeba/upstream/git_read.py"
  - "tests/operations/test_naming.py"
  - "src/amoeba/config/starter.py"
  - "tests/store/test_members_queried_in_one_place.py"
  - "src/amoeba/operations/names.py"
searches:
  - "grep SELECT_UNNAMED_MEMBERS|SELECT_MEMBER_BY_NAME|SELECT_MEMBER_BY_ORIGIN|SELECT_REMOVED_MEMBER_BY_ORIGIN|SELECT_NAME_IS_OTHER_MEMBERS_ID|SET_MEMBER_NAME|SET_MEMBER_ORIGIN|CLEAR_MEMBER_WAKE_COMMAND|SELECT_ACTIVE_MEMBERS_WITHOUT_CHECKOUT_ON|^ACTIVE_MEMBER|UPSERT_SCHEMA_VERSION|SELECT_SCHEMA_VERSION|TABLE_\u2026 in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/sql.py"
  - "list_files src/amoeba/store/*.py in /Users/manta/source/repos/manta/amoeba"
  - "list_files src/amoeba/operations/*naming*.py in /Users/manta/source/repos/manta/amoeba"
  - "grep upsert_member\\(|set_member_name\\(|set_member_origin\\(|delete_checkouts_of_member\\(|delete_checkout\\(|insert_checkout\\(|remove_member\\(|clear_member_wake_command|name_members\\(|renamed_from|stale_checkout_id|IntegrityError in /Users/manta/source/repos/manta/amoeba/src"
  - "grep removed|reregister|name_is_taken|check_given_name|NAME_TAKEN|ORIGIN_TAKEN|origin in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/set_up_resolve.py"
  - "grep removed|reregister|name_is_taken|check_given_name|NAME_TAKEN|ORIGIN_TAKEN|active_member_by_name|rename_to|origin in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/set_up_checks.py"
  - "grep CREATE TABLE (IF NOT EXISTS )?(members|machines|owners)\\b|project_id\\s+TEXT\\s+PRIMARY KEY|owner_id\\s+INTEGER|machine_id\\s+INTEGER\\s+PRIMARY|name_members|name_by_id\\( in /Users/manta/source/repos/manta/amoeba/src"
  - "grep FileHandler|basicConfig|RotatingFileHandler|getLogger\\(|log_path|\\.log\"|logs_dir|logging\\. in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep wake_command|WakeCommand in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/set_up_models.py"
  - "grep refuse_door_fields|def refuse|\"checkout\"|\"wake_command\"|\"attach_to\"|\"new_member\"|\"project\"|REFUSED_FROM|_DOOR_FIELDS|door_fields in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep WAKE_COMMAND_DOORS|refuse_door_fields|wake_command|WAKE_FROM_OWN_CHECKOUT in /Users/manta/source/repos/manta/amoeba/src"
  - "grep set_up|SET_UP|gather_add|refuse_door|door= in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep OperationName\\.SET_UP|\"set_up\"|set_up\\b|set_up\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep ^def (integer|optional_text|text|encode_timestamp|acting_machine_id|is_member_name|project_details|git_read|remote_origin_args|git_root|starter_values|fill_missing_keys|state_home|config_path|store_path|state_layout|logs_dir|starter_values|checkout_listing|acting)\\b|^(class (Transaction|CfCallFailed\u2026 in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep detail|def run_cf|def output_head|TimeoutExpired|OSError|stderr|stdout in /Users/manta/source/repos/manta/amoeba/src/amoeba/upstream/context_forge/cli_call.py"
  - "grep by its id|by id|clash|IntegrityError|collid|same name|another member already in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep IntegrityError in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/errors.py"
  - "grep id|uuid|slug in /Users/manta/source/repos/manta/amoeba/src/amoeba/upstream/context_forge/projects.py"
  - "grep wake_command|\\bname\\b\\s+TEXT|origin|CREATE TABLE (wakes|checkouts) in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/schema"
  - "grep extra=|forbid|unknown key|Extra inputs|model_config in /Users/manta/source/repos/manta/amoeba/src/amoeba/config"
  - "grep checkout in /Users/manta/source/repos/manta/amoeba/src/amoeba/cli/registration_arguments.py"
  - "grep cannot be combined|parser\\.error in /Users/manta/source/repos/manta/amoeba/src/amoeba/cli/registration_arguments.py"
  - "grep TODO|FIXME|XXX|later slice|deferred|for now|follow-up|print\\(|breakpoint\\(|pdb in /Users/manta/source/repos/manta/amoeba/src/amoeba"
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
  - "src/amoeba/operations/add_door.py"
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
turns: 60
promptTokens: 4592942
cachedTokens: 4402263
cacheWriteTokens: 190613
completionTokens: 73021
durationSeconds: 327.0
costUsd: 0.500444
costBasis: provider
runId: run-20261123-p6-ca3ac353
squadronVersion: 0.24.37
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "update_live writes the config before install, and an install failure is not restored"
    location: "scripts/update_live.py:342-343"
  - id: F002
    severity: concern
    category: error-handling-observability
    summary: "A backup killed or failed mid-copy blocks every later update"
    location: "scripts/update_live.py:310"
  - id: F003
    severity: concern
    category: correctness
    summary: "Naming falls back to a member id with no clash check, so the write fails and every command with it"
    location: "src/amoeba/operations/naming.py:139-159"
  - id: F004
    severity: concern
    category: architectural-decay
    summary: "The \"wake command dropped\" logic is duplicated in two modules"
    location: "src/amoeba/operations/name_by_id.py:64-73"
  - id: F005
    severity: note
    category: security-hygiene
    summary: "The wake command text is written to the log verbatim"
    location: "src/amoeba/operations/naming.py:222-226"
  - id: F006
    severity: note
    category: correctness
    summary: "`rm --checkout` silently ignores `--program`"
    location: "src/amoeba/operations/rm.py:130-138"
  - id: F007
    severity: note
    category: error-handling-observability
    summary: "The update's blanket catch restores and re-raises, but does not log through logger.exception"
    location: "scripts/update_live.py:346-355"
  - id: F008
    severity: note
    category: performance-resource
    summary: "`with` on a sqlite3 connection does not close it"
    location: "scripts/update_live.py:136-137"
  - id: F009
    severity: pass
    category: correctness
    summary: "Migration 012 is additive, with correct name and origin uniqueness and the checkouts table"
    location: "src/amoeba/store/schema/012_members_by_name.sql:15-48"
  - id: F010
    severity: pass
    category: security-hygiene
    summary: "The wake-command door check covers both places `add` can carry the field"
    location: "src/amoeba/operations/add_door.py:56-83"
---

# Review: code — slice 261

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Diff:** truncated: 0 of 1028553 characters reached the model
  - scripts/update_live.py: omitted (0 of 13480 characters)
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
  - src/amoeba/operations/add_door.py: omitted (0 of 1114 characters)
  - src/amoeba/operations/add_gather.py: omitted (0 of 2136 characters)
  - src/amoeba/operations/add_member.py: omitted (0 of 11928 characters)
  - src/amoeba/operations/add_names.py: omitted (0 of 2312 characters)
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
  - src/amoeba/operations/name_by_id.py: omitted (0 of 3447 characters)
  - src/amoeba/operations/naming.py: omitted (0 of 9907 characters)
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
  - src/amoeba/operations/set_up_resolve.py: omitted (0 of 15933 characters)
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
  - src/amoeba/store/checkouts.py: omitted (0 of 7076 characters)
  - src/amoeba/store/machines.py: omitted (0 of 2189 characters)
  - src/amoeba/store/member_names.py: omitted (0 of 3558 characters)
  - src/amoeba/store/migrations.py: omitted (0 of 611 characters)
  - src/amoeba/store/models.py: omitted (0 of 1291 characters)
  - src/amoeba/store/programs.py: omitted (0 of 4463 characters)
  - src/amoeba/store/schema/012_members_by_name.sql: omitted (0 of 2411 characters)
  - src/amoeba/store/sql.py: omitted (0 of 4689 characters)
  - src/amoeba/store/sql_checkouts.py: omitted (0 of 3404 characters)
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
  - tests/operations/test_naming.py: omitted (0 of 19463 characters)
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
  - tests/operations/test_set_up_validation.py: omitted (0 of 5258 characters)
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
  - tests/scripts/test_update_live.py: omitted (0 of 16906 characters)
  - tests/store/decision_support.py: omitted (0 of 1598 characters)
  - tests/store/message_support.py: omitted (0 of 1202 characters)
  - tests/store/release_support.py: omitted (0 of 1133 characters)
  - tests/store/schema_11.py: omitted (0 of 5591 characters)
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
  - tests/test_import_boundaries.py: omitted (0 of 4670 characters)
  - tests/test_message_timing.py: omitted (0 of 8132 characters)
  - tests/test_read_side_defined_once.py: omitted (0 of 1036 characters)
  - tests/test_report_release_sweep.py: omitted (0 of 1868 characters)
  - tests/test_wiring.py: omitted (0 of 5776 characters)
  - tests/test_wiring_release.py: omitted (0 of 2804 characters)
  - tests/test_wiring_results.py: omitted (0 of 1110 characters)
  - tests/upstream/context_forge/test_project_of.py: omitted (0 of 1594 characters)
  - tests/upstream/context_forge/test_projects.py: omitted (0 of 2669 characters)
  - tests/upstream/test_git_read.py: omitted (0 of 2587 characters)
  - tests/wire/test_protocol.py: omitted (0 of 1960 characters)
**Evidence:** 56 successful tool call(s) of 59 made; 0 of 1028553 diff characters reached the model

## Findings

### [CONCERN] update_live writes the config before install, and an install failure is not restored

`update()` calls `add_missing_keys` (which writes the config, `src/amoeba/config/starter.py:94`) before `steps.install(...)`. The `try` that restores on failure begins only after the install. If `uv tool install` fails, for example because the version is not on PyPI yet, `UpdateError` propagates with the config already changed and nothing restored. `UserConfig` is `extra="forbid"` (`src/amoeba/config/user_config.py:73`). When the release has added a required key, the still-installed previous version then rejects its config on every command, and the message says only that uv could not install. `test_a_version_not_on_pypi_is_an_update_error_not_a_traceback` covers only `_uv_install`, not the config left behind. Fix: restore `backup/CONFIG_BACKUP` when the install fails, or put the install and the config write inside the restore path.

### [CONCERN] A backup killed or failed mid-copy blocks every later update

`take_backup` (lines 164-171) creates the directory, copies the store, copies the config, and writes `previous-version` last. A failure or kill during the copy leaves a directory with no `previous-version`. The next `update` reaches `reusable_backup`, which reads `newest / PREVIOUS_VERSION` at line 310 with no guard. The result is an uncaught `FileNotFoundError` before anything else runs, since `main` catches only `UpdateError`. `restore` also refuses, because `check_backup` finds no previous-version in the newest backup. The only exit is deleting the directory by hand, which breaks the design rule that every state has an exit. No test covers an incomplete backup directory; the kill tests interrupt after the backup is complete. Fix: write the backup into a temporary directory and rename it into place only when complete, or treat an incomplete newest backup as absent and let a successful update delete it.

### [CONCERN] Naming falls back to a member id with no clash check, so the write fails and every command with it

`_name_for` falls back to `_by_id` in four cases: no listing, an invalid Context Forge name, an active name clash, or another member's id. `_by_id` returns the member's own id without checking D1. If an active member already has that id as its name, ignoring case, `set_member_name` violates `members_active_name`, and `errors.py:91-92` maps that to `StoreIntegrityError`. The write rolls back, `open_state_store` closes the store and re-raises, and naming runs again on every open, so every command fails until the data changes. The hub path has the check (`src/amoeba/operations/name_by_id.py:32-40`, `_refuse_a_clash`), but the Context Forge path does not. `tests/operations/test_naming.py:472-490` checks the fallback reasons but never an id that clashes. The trigger is rare: an unlisted or unnamed member whose id matches another project's name, ignoring case. Fix: apply the D1 check to the id before falling back, refuse with a message that names both members, as the hub path does, and add a test for the collision.

### [CONCERN] The "wake command dropped" logic is duplicated in two modules

`name_by_id` clears the retired wake command and logs the same warning text as `naming._retire_wake_command` (`src/amoeba/operations/naming.py:215-226`). The modules are kept apart so the hub does not import the client part, as the docstring says. That reason does not apply to `src/amoeba/store/member_names.py`, which both modules can import. Fix: move a shared helper into `member_names.py` and call it from both.

### [NOTE] The wake command text is written to the log verbatim

Both naming paths log the retired `wake_command` (`naming.py:222-226`, `name_by_id.py:68-73`). Those warnings reach the hub's rotating `hub.log` (`src/amoeba/hub/hub_log.py`) and the MCP server's stderr. The design accepts this because the store already holds the text in plain text. `src/amoeba/cli/registration_arguments.py:46-53` says wake commands are shown in plain text and must carry no secret. `tests/operations/test_naming.py:452-455` asserts the text is logged. This is a decision rather than a defect, but logs are copied and kept differently from the database, so a token in a command would spread further. Consider logging only the first token.

### [NOTE] `rm --checkout` silently ignores `--program`

`_remove_checkout` rejects members, pairs, and the concept with `--checkout`, but not `program`. The CLI does not reject the combination either (`src/amoeba/cli/registration_arguments.py:202-208, 308-311`), so `amoeba rm --checkout /p --program X` removes the checkout and never uses `X`. Reject it as malformed, as the other flags are rejected.

### [NOTE] The update's blanket catch restores and re-raises, but does not log through logger.exception

The `except Exception` after install is deliberate and documented. It restores the previous state, prints the traceback to stderr, and raises `UpdateError ... from error`, which meets the intent. It does not meet the repo's rule (a) as written, which requires `logger.exception` and a re-raise. The script has no logger. Either accept it as a process-boundary handler and say so in the rules, or log through `logger.exception`.

### [NOTE] `with` on a sqlite3 connection does not close it

`_read_only` returns a `sqlite3.Connection`, and callers use `with _read_only(...) as connection:` (lines 141, 177, 238, 291). The sqlite3 context manager commits but does not close. CPython closes the connection when the function returns, so nothing leaks in practice. The repo's convention, visible in the tests, is `contextlib.closing`. Switch the callers to `closing`.

### [PASS] Migration 012 is additive, with correct name and origin uniqueness and the checkouts table

I read the migration against the schema it depends on: `members.project_id` is the primary key, and `owners` and `machines` exist from migration 011. The name index uses the NOCASE column and covers active members only. Origin is unique among active members. The trigger refuses a new member with no name. `tests/store/test_migration_012.py` covers each of these. I did not run it.

### [PASS] The wake-command door check covers both places `add` can carry the field

The MCP door reaches only `add` and `rm` (`src/amoeba/operations/names.py`), and `set_up` has no door entry point. So the `add` check is the only one that matters. `refuse_door_fields` checks the top-level document and each `bulk.members` entry, and `add_gather.py` runs it before anything is gathered.

### Run Digest

- Response length: 14896 chars
- Response is newline-free: no
- Tool calls made: 59
- Tool calls failed: 3
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 60
- Tokens — prompt / cached / cache write / completion / reasoning: 4592942 / 4402263 / 190613 / 73021 / not computed
- Duration: 327.0 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
