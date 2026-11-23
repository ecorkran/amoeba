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
reviewedSha: 2a90a2b9e5fda3fbf5d55226177dc5d3af8937d1
reviewedBlob: 15a494270f008458be5eda5a31dee428b060cb70
reviewedBlobCurrent: true
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 77
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
  - "src/amoeba/store/row_values.py"
  - "src/amoeba/operations/naming.py"
  - "src/amoeba/operations/origin.py"
  - "src/amoeba/operations/add.py"
  - "src/amoeba/operations/add_member.py"
  - "src/amoeba/operations/add_names.py"
  - "src/amoeba/operations/add_origin.py"
  - "src/amoeba/operations/add_gather.py"
  - "src/amoeba/operations/add_door.py"
  - "src/amoeba/hub/calls.py"
  - "src/amoeba/hub/store_open.py"
  - "src/amoeba/hub/admin.py"
  - "src/amoeba/wire/protocol.py"
  - "src/amoeba/operations/name_by_id.py"
  - "src/amoeba/operations/caller.py"
  - "src/amoeba/hub/call_refusals.py"
  - "src/amoeba/cli/hub_commands.py"
  - "src/amoeba/operations/state_move.py"
  - "src/amoeba/upstream/context_forge/projects.py"
  - "src/amoeba/upstream/git_read.py"
  - "src/amoeba/upstream/context_forge/cli_call.py"
  - "src/amoeba/operations/here.py"
  - "src/amoeba/operations/here_document.py"
  - "src/amoeba/store/checkouts.py"
  - "src/amoeba/store/programs.py"
  - "src/amoeba/store/vocabulary.py"
  - "src/amoeba/store/models.py"
  - "src/amoeba/store/sql_checkouts.py"
  - "src/amoeba/store/machines.py"
  - "src/amoeba/store/sql.py"
  - "src/amoeba/operations/set_up.py"
  - "src/amoeba/operations/set_up_plan.py"
  - "src/amoeba/operations/set_up_resolve.py"
  - "src/amoeba/operations/set_up_wake.py"
  - "src/amoeba/operations/set_up_remove.py"
  - "src/amoeba/operations/rm.py"
  - "src/amoeba/operations/served.py"
  - "src/amoeba/operations/served_runners.py"
  - "src/amoeba/client/call.py"
  - "src/amoeba/mcp/tools.py"
  - "src/amoeba/operations/pause_eligibility.py"
  - "src/amoeba/wiring_gather.py"
  - "src/amoeba/cli/registration_arguments.py"
  - "src/amoeba/cli/commands.py"
  - "scripts/update_live.py"
  - "tests/scripts/test_update_live.py"
  - "tests/store/test_members_queried_in_one_place.py"
  - "tests/test_import_boundaries.py"
  - "tests/operations/test_origin.py"
  - "tests/operations/test_naming.py"
searches:
  - "list_files src/amoeba/store/*member* in /Users/manta/source/repos/manta/amoeba"
  - "list_files src/amoeba/store/schema/*.sql in /Users/manta/source/repos/manta/amoeba"
  - "grep SELECT_UNNAMED_MEMBERS|SELECT_MEMBER_BY_NAME|SELECT_MEMBER_BY_ORIGIN|SELECT_REMOVED_MEMBER_BY_ORIGIN|SELECT_NAME_IS_OTHER_MEMBERS_ID|SET_MEMBER_NAME|SET_MEMBER_ORIGIN|CLEAR_MEMBER_WAKE_COMMAND|SET_MEMBER_NAME in /Users/manta/source/repos/manta/amoeba/src/amoeba/store"
  - "grep members|removed_at|project_id in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/schema/001_baseline.sql"
  - "grep refuse_unless_a_ready_hub|open_hub_store|name_members|name_by_id\\( in /Users/manta/source/repos/manta/amoeba/src"
  - "grep def open_state_store|def open_store|def open\\(|migrate\\( in /Users/manta/source/repos/manta/amoeba/src"
  - "grep subprocess\\.run|CfRun in /Users/manta/source/repos/manta/amoeba/src"
  - "grep _MEMBER_COLUMNS|ACTIVE_MEMBER\\b.*=|^SELECT_MEMBER|^SELECT_UNNAMED|member_from_row|FROM members in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/sql.py"
  - "grep gather_add\\(|refuse_door_fields\\(|Door\\.MCP|Door\\.CLI|door= in /Users/manta/source/repos/manta/amoeba/src"
  - "grep wake.command|--name|--attach-to|--new-member|--project|--checkout in /Users/manta/source/repos/manta/amoeba/src/amoeba/cli"
  - "grep \\.git\\.git|is_reduced_origin|reduce_origin\\( in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep another case|refuse_id_clash|StoreRowError|named by its id|name_by_id in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep except(\\s+Exception|\\s*:)|except BaseException in /Users/manta/source/repos/manta/amoeba/src"
  - "grep os\\.environ|os\\.path\\.|\\.format\\(|from typing import (List|Dict|Tuple|Optional|Union) in /Users/manta/source/repos/manta/amoeba/src"
  - "grep wake_command in /Users/manta/source/repos/manta/amoeba/src/amoeba/store"
  - "grep first_wakeable_checkout|first_checkout_on|members\\.wake_command|SELECT_MEMBER_WAKE|wake_command in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations"
  - "grep name_members|open_state_store|naming|reduce_origin|add_member|gather_checkout|CI_GATE|load in /Users/manta/source/repos/manta/amoeba/tests/load"
  - "grep load in /Users/manta/source/repos/manta/amoeba/tests/test_ci_gates_load.py"
  - "grep name_members|open_state_store|naming|add_member|gather_checkout|_read_origin|git_root in /Users/manta/source/repos/manta/amoeba/tests/load"
  - "grep open_store\\(|def invoke|def open_store in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep 262|remove_machine|rm-machine in /Users/manta/source/repos/manta/amoeba/project-documents"
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
turns: 78
promptTokens: 6158691
cachedTokens: 5870116
cacheWriteTokens: 288503
completionTokens: 98954
durationSeconds: 432.7
costUsd: 0.721413
costBasis: provider
runId: run-20261123-p6-ca3ac353
squadronVersion: 0.24.37
categoriesNormalized: true
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "A case-only name clash blocks every command, and the fix it names cannot run"
    location: "src/amoeba/store/member_names.py:96-112"
  - id: F002
    severity: concern
    category: correctness
    summary: "`reduce_origin` can return a value that `is_reduced_origin` rejects"
    location: "src/amoeba/operations/origin.py:38"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "A probe thread that dies turns into an `IndexError` that hides the real error"
    location: "src/amoeba/operations/naming.py:68-71"
  - id: F004
    severity: concern
    category: architectural-decay
    summary: "Origin reading is duplicated, and only one copy is guarded against a hung mount"
    location: "src/amoeba/operations/naming.py:74"
  - id: F005
    severity: concern
    category: test-debt
    summary: "No load test covers the naming step"
    location: "tests/operations/test_naming.py:505-511"
  - id: F006
    severity: note
    category: consistency-rot
    summary: "Two identical `Gathered` aliases and two functions named `gather_add`"
    location: "src/amoeba/operations/add_gather.py:24"
  - id: F007
    severity: note
    category: consistency-rot
    summary: "`\"\"` and `None` both mean \"no member excluded\""
    location: "src/amoeba/operations/add_member.py:250"
  - id: F008
    severity: note
    category: architectural-decay
    summary: "Some files and functions are over the size guideline"
    location: "src/amoeba/operations/set_up_resolve.py:132"
  - id: F009
    severity: note
    category: security-hygiene
    summary: "The naming warning writes a whole wake command to the log"
    location: "src/amoeba/store/member_names.py:115-131"
  - id: F010
    severity: note
    category: correctness
    summary: "A caller's `extra` body keys can silently override `document`"
    location: "src/amoeba/client/call.py:175"
  - id: F011
    severity: note
    category: error-handling-observability
    summary: "The update script can end in a traceback where its test promises an `UpdateError`"
    location: "scripts/update_live.py:399-409"
  - id: F012
    severity: note
    category: type-contract-debt
    summary: "Hub-side checkout fields are not constrained at the trust boundary"
    location: "src/amoeba/operations/here_document.py:36-42"
  - id: F013
    severity: pass
    category: correctness
    summary: "Every hub admin action is guarded before a store opens"
    location: "src/amoeba/cli/hub_commands.py:184-185"
  - id: F014
    severity: pass
    category: correctness
    summary: "Wake-command reads go through checkouts"
    location: "src/amoeba/store/wakes.py:149-156"
  - id: F015
    severity: pass
    category: correctness
    summary: "Migration 012 and the member SQL are consistent"
    location: "src/amoeba/store/sql.py:93-96"
---

# Review: code — slice 261

**Verdict:** FAIL
**Model:** claude-haiku-5-5
**Diff:** truncated: 0 of 1035115 characters reached the model
  - scripts/update_live.py: omitted (0 of 17026 characters)
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
  - src/amoeba/operations/name_by_id.py: omitted (0 of 2471 characters)
  - src/amoeba/operations/naming.py: omitted (0 of 9265 characters)
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
  - src/amoeba/operations/rm.py: omitted (0 of 11217 characters)
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
  - src/amoeba/store/member_names.py: omitted (0 of 5461 characters)
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
  - tests/operations/test_naming.py: omitted (0 of 20225 characters)
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
  - tests/operations/test_rm_by_name.py: omitted (0 of 6360 characters)
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
  - tests/scripts/test_update_live.py: omitted (0 of 18788 characters)
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
**Evidence:** 75 successful tool call(s) of 77 made; 0 of 1035115 diff characters reached the model

## Findings

### [FAIL] A case-only name clash blocks every command, and the fix it names cannot run

`refuse_id_clash` raises `StoreRowError` when an unnamed member's id equals, in another case, an active member's name. Naming calls it from `_by_id` (src/amoeba/operations/naming.py:158-166) inside the single write transaction (naming.py:239-242), so one clash aborts naming for every member and nothing is written. `open_state_store` runs `name_members` on every open (src/amoeba/operations/state_move.py:185-200). `wiring.open_store` and `invoke` go through it (src/amoeba/wiring.py:121-174), so `add`, `rm`, `list`, and `init` all fail before they run. The hub's `open_hub_store` calls `name_by_id` the same way (src/amoeba/hub/store_open.py:88-96), so `amoeba hub serve` cannot start.

The error and the `_by_id` docstring say `amoeba add --project ID --name NAME` renames the member. That command opens the store through the same path, so it fails too. I found no command that gets past the refusal. The only exit I can see is hand-editing the SQLite file, which the Amoeba rule "every state has an exit, with nobody editing files" forbids. The live upgrade is affected too: `update_live.py` migrates by running `amoeba list` (scripts/update_live.py:348, 420-421), so a store in this state fails its read-back and restores.

`tests/operations/test_naming.py:518-549` checks the loud refusal and the rollback. Nothing checks a way out.

The trigger is narrow: two unnamed members whose ids differ only by case, or an unnamed member whose id equals an active member's name in another case when Context Forge gives no usable name. I did not check what Context Forge ids look like. The state is still reachable and has no exit.

Direction: stop the open from refusing. Leave the clashing member unnamed or give it a deterministic, logged name. Then make the read paths cope with a null name (`programs.member_from_row` raises on one, `programs.py:44-51`) so `add --project` and `rm` can rename it.

### [CONCERN] `reduce_origin` can return a value that `is_reduced_origin` rejects

`_join` removes one `.git` suffix. For `https://github.com/org/repo.git.git`, the result is `github.com/org/repo.git`. `is_reduced_origin` (origin.py:93) refuses any path ending in `.git`, so the module's own invariant breaks. Reading the code: `here.gather_checkout` builds `HereCheckout(origin=...)` (src/amoeba/operations/here.py:118-123), and its validator (here_document.py:44-49) raises, so `add` fails with an uncaught validation error before any hub call. The naming step also writes the non-reduced value (naming.py:99 to `set_member_origin`). `test_every_output_passes_the_check` (tests/operations/test_origin.py:81-94) has no `.git.git` case. The input is rare, but the rule is violated. Suggested fix: have `reduce_origin` return `None` when its result would not pass `is_reduced_origin`, so the two agree.

### [CONCERN] A probe thread that dies turns into an `IndexError` that hides the real error

After `probe.join(seconds)`, `_git_root_within` returns `(True, found[0])`. If `here.git_root` raised inside the probe thread, the thread ends with nothing in `found`, `is_alive()` is False, and `found[0]` raises `IndexError`. The real error appears only in the thread's exception hook. Naming runs on every open and writes nothing when it raises, so while the path problem persists every command fails with this `IndexError`. No test covers an exception inside the probe. Fix: capture the probe's exception and re-raise it in the caller.

### [CONCERN] Origin reading is duplicated, and only one copy is guarded against a hung mount

`_read_origin` repeats `here._origin_of` (src/amoeba/operations/here.py:85-102): the git-root check, `git remote get-url origin`, the no-remote and non-zero exit handling, and the reduce. Only the failure policy differs (log versus raise). The guard differs too. Naming runs the stat in a daemon thread with a timeout (naming.py:58-62), because "a hung mount can block [the stat] for good". `_origin_of` calls `git_root(path)` directly (here.py:92), so `add` and the pause registration path (`pause_eligibility._registered`) can hang on the same stat, with no timeout. Fix: one origin reader with one policy, shared by both callers.

### [CONCERN] No load test covers the naming step

The testing rules require a `tests/load/` test for any environment-layer or concurrency path. The naming step runs `cf` and `git` subprocesses under a 30-second budget and a daemon-thread probe, on every command that opens the store. A grep of `tests/load` finds no reference to `name_members`, `naming`, `add_member`, or `gather_checkout`. The only coverage is unit tests, including a timing check on a hung probe.

### [NOTE] Two identical `Gathered` aliases and two functions named `gather_add`

`add_gather.py:24` and `set_up_resolve.py:34` both define `type Gathered = HereCheckout | HereNotAProject | None`. `served_runners.gather_add` (served_runners.py:58) and `add_gather.gather_add` (add_gather.py:27) share a name but do different jobs. Consolidate the alias and rename one of the functions.

### [NOTE] `""` and `None` both mean "no member excluded"

`add_member._create` passes `""` to `name_is_other_members_id`, while `check_given_name` and `name_holder` use `None`, and `add_names.py:41` converts `None` to `""`. No project id is empty, so this is harmless, but there should be one sentinel.

### [NOTE] Some files and functions are over the size guideline

`set_up_resolve.py` is 339 lines, `hub/calls.py` is 326, and `add_member.py` is 307. `resolve_request` runs from line 132 to 245, about 110 lines, against a guideline of about 50 per function. Split the per-entry loop body out of `resolve_request`.

### [NOTE] The naming warning writes a whole wake command to the log

`retire_wake_command` logs the full command with `%r` when no checkout takes it (the hub's `name_by_id` does the same). `WAKE_COMMAND_HELP` (src/amoeba/cli/registration_arguments.py:45-53) tells users a wake command "must carry no secret". D4 accepts this and says the store already holds the text in plain text. The log is one more place it persists, so the PM should confirm that is acceptable.

### [NOTE] A caller's `extra` body keys can silently override `document`

`json.dumps({DOCUMENT_KEY: document, **(extra or {})})` lets `extra` replace `document`. The current callers pass only `here` and `runs`, so nothing is hit today. Reject a key collision.

### [NOTE] The update script can end in a traceback where its test promises an `UpdateError`

`_uv_install` catches only `CalledProcessError`. A missing `uv` raises `FileNotFoundError`. `check_checkout` (line 110) and `installed_version` (line 414) have the same gap, and `main` (lines 476-502) catches only `UpdateError`. `test_a_version_not_on_pypi_is_an_update_error_not_a_traceback` covers only the non-zero exit.

### [NOTE] Hub-side checkout fields are not constrained at the trust boundary

`HereCheckout.project_id`, `name`, and `path` are bare `str`, so the hub accepts empty or relative values and stores them on the caller's own checkout. The effect stays on that machine, and `name` is checked later by `is_member_name`. Add `min_length` and an absolute-path check at the model.

### [PASS] Every hub admin action is guarded before a store opens

`run_hub` calls `refuse_unless_a_ready_hub` for every action except `serve`, which matches the docstring in `hub/store_open.py`.

### [PASS] Wake-command reads go through checkouts

Every reader I found (`wakes.py`, `list_registry.py`, `wake_status.py`, `wake_door.py`) reads `checkouts.wake_command`. `members.wake_command` is written only by naming and `retire_wake_command`.

### [PASS] Migration 012 and the member SQL are consistent

`members.project_id` is the primary key, so `checkouts`' foreign key is valid. `_MEMBER_COLUMNS` puts `name` and `origin` at positions 9 and 10, matching `member_from_row` (`programs.py:54-70`). The `INSERT_MEMBER` placeholder count (eleven) matches its binds. The members-table guard test passes by reading.

### Run Digest

- Response length: 20719 chars
- Response is newline-free: no
- Tool calls made: 77
- Tool calls failed: 2
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 78
- Tokens — prompt / cached / cache write / completion / reasoning: 6158691 / 5870116 / 288503 / 98954 / not computed
- Duration: 432.7 s
- Cost: $0.72 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15
