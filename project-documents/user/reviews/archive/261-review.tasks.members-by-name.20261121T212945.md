---
docType: review
layer: project
reviewType: tasks
slice: members-by-name
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/261-tasks.members-by-name.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261121
dateUpdated: 20261121
reviewedSha: 1a95fc785763049a0b5769bbed9a9583d609eac3
reviewedBlob: e57760afce1adfae18048786eef82dfc1a9cc4c5
reviewedBlobCurrent: false
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 81
injected:
  - key: input
    path: "project-documents/user/tasks/261-tasks.members-by-name.md"
    chars: 66399
    sha256: ba17bc4afd1a974314b8b85fb1f392c25953ed2718b6a3e18641da8cd1da6ab2
    whole: true
  - key: against
    path: "project-documents/user/slices/261-slice.members-by-name.md"
    chars: 82894
    sha256: 4c6bf88502a7a858bec3879be1c38908e4641a956a71029c60c943d85719cb72
    whole: true
  - key: conventions
    path: "AGENTS.md"
    chars: 23952
    sha256: 9b993051f9050d1c957047099dab80641d2fc9a22a808766fe481968eaee78ce
    whole: true
filesRead:
  - "src/amoeba/store/sql.py"
  - "tests/store/test_members_queried_in_one_place.py"
  - "src/amoeba/store/programs.py"
  - "src/amoeba/operations/set_up.py"
  - "src/amoeba/operations/set_up_resolve.py"
  - "src/amoeba/upstream/context_forge/project_of.py"
  - "src/amoeba/upstream/context_forge/projects.py"
  - "src/amoeba/upstream/git_read.py"
  - "src/amoeba/operations/pause_eligibility.py"
  - "src/amoeba/operations/pause_claim.py"
  - "tests/upstream/test_git_read.py"
  - "tests/operations/pause_support.py"
  - "src/amoeba/operations/status_placement.py"
  - "scripts/update_live.py"
  - "tests/scripts/test_update_live.py"
  - "tests/test_contract_docs.py"
  - "src/amoeba/wiring_messages.py"
  - "tests/test_import_boundaries.py"
  - ".github/workflows/ci.yml"
  - "tests/store/seed.py"
  - "tests/store/test_migration_010.py"
  - "tests/load/test_no_cf_under_write_lock.py"
searches:
  - "list_files src/amoeba/**/*.py in ."
  - "list_files tests/**/*.py in ."
  - "list_files {docs,scripts}/**/* in ."
  - "list_files project-documents/user/{architecture,slices,tasks}/*260* in ."
  - "list_files src/amoeba/{operations/errors.py,operations/member_reference.py,operations/add_door.py,operations/here*.py,operations/caller.py,operations/naming.py,operations/origin.py,operations/served.py,store/vocabulary.py,store/checkouts.py,store/sql_checkouts.py,store/schema/*.sql,store/migrations.py,store/st\u2026 in ."
  - "list_files tests/{store/seed.py,store/test_migration_010.py,store/test_schema_holds_no_mirrored_state.py,test_contract_docs.py,test_import_boundaries.py,user_configs.py,store/test_members_queried_in_one_place.py,test_message_timing.py,scripts/test_update_live.py,cli/test_requests_scenario.py,live/messaging/tes\u2026 in ."
  - "grep EXPECTED_SCHEMA_VERSION\\s*[:=] in /Users/manta/source/repos/manta/amoeba/src"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/sql.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/set_up.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/pause_context.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/models.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/set_up_models.py"
  - "grep \\bMEMBER|INSERT INTO members|UPDATE members|FROM members|members\\b.*wake_command|wake_command in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/sql.py"
  - "grep wake_command in /Users/manta/source/repos/manta/amoeba/src"
  - "grep def upsert_member|def _member\\b|def insert_member|upsert_member\\( in /Users/manta/source/repos/manta/amoeba"
  - "grep _checkout_of|def pause_eligibility|resolve_member|project_names|project_details|project_of\\(|ContextForgeError|MESSAGE_LOOKUPS|worst_case_seconds in /Users/manta/source/repos/manta/amoeba/src"
  - "grep pause_context|\\bgather\\(|read_target|resolve_slice|_read_committed|program_sources|ProjectOf in /Users/manta/source/repos/manta/amoeba/src"
  - "grep GIT_SUBCOMMANDS|git_read\\(|SUBCOMMAND_|GIT_EXECUTABLE|\"remote\" in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep class PauseTarget|PauseTarget\\(|class Eligible|Eligible\\(|checkout: Path|member: Member in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep project_of|project_names|project_details|operations\\.members|member_reference|project_lookup|resolve_member in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep ContextForgeError in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep wake_command=|MemberSettings\\( in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep project_of|ProjectOf|project_names|project_details|wake_command= in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep project_of|ProjectOf|project_names|project_details|wake_command= in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep project_names=|project_of|monkeypatch\\.setattr in /Users/manta/source/repos/manta/amoeba/tests/operations/test_standing.py"
  - "grep ^def |^class |installed-commit|update\\.partial|CalledProcessError|UpdateError|def main|restore|take_backup|\\.check_store|cf_projects in /Users/manta/source/repos/manta/amoeba/scripts/update_live.py"
  - "grep ^def |^class |FakeSteps|def test_|restore\\(|update\\( in /Users/manta/source/repos/manta/amoeba/tests/scripts/test_update_live.py"
  - "grep COLUMN_REASONS|def test_|members|wake_command|table|TABLES|len\\( in /Users/manta/source/repos/manta/amoeba/tests/store/test_schema_holds_no_mirrored_state.py"
  - "grep  s\\.|\\bs\\b\\)|up to \\d+ s|worst in /Users/manta/source/repos/manta/amoeba/docs/mcp-server.md"
  - "grep --attach-to|--new-member|--checkout|--name\\b|--wake-command|--no-wake-command in /Users/manta/source/repos/manta/amoeba/docs/cli-contract.md"
  - "grep INSERT INTO members in /Users/manta/source/repos/manta/amoeba"
  - "grep known_to_cf|class Reference|anchor\\b|def anchor|name_taken|origin_taken|no_origin|member_has_checkouts|not_a_checkout|refuse_door_fields in /Users/manta/source/repos/manta/amoeba/src"
  - "grep operations|project_of|project_details|project_names|cf_get|list_projects|glob|rglob in /Users/manta/source/repos/manta/amoeba/tests/test_read_side_defined_once.py"
  - "grep def open_state_store|def act_as_local|def acting\\b|def act_as\\b|class ActingMachine|LOCAL_MACHINE_NAME|RUN_POLL_TIMEOUT_SECONDS:|def resolve_release_member|def result_from_document|def resolve_scope|def resolve_caller|def resolve_actor|def resolve_recipient|def gather_|start_failed in /Users/manta/source/repos/manta/amoeba/src"
  - "list_files src/amoeba/operations/{status_runs,status_calls,list_view,status,changes,report_release,release_member,standing,decisions,inbox,send,reply,cancel,rm,message_member,deps,list_registry,wake,wake_status,changes_models,handle_pause,pause_results,pause_claim,claim_waiting,set_up_remove,set_up_remove_reso\u2026 in ."
  - "grep start_failed|project_path|no path|directory in /Users/manta/source/repos/manta/amoeba/tests/operations/test_wake_after_send.py"
  - "grep 010_standing_answers|009_wakes|schema/0 in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep acting\\(\\)|act_as_local|act_as\\b|LOCAL_MACHINE_NAME|open_hub_store|result_from_document|10\\.1b|id_names|id_resolver|local_served_edges|ServedEdges|in_process_hub|hub_fixture|store_open|RefusalCode|SERVED_OPERATIONS|WRITING_CALLS|UNKNOWN_ADVICE|rm_machine|OPERATION_ERRORS|run_served|lock probe|wiring\u2026 in /Users/manta/source/repos/manta/amoeba/project-documents/user"
  - "grep schema|012|standing_answers|sql in /Users/manta/source/repos/manta/amoeba/tests/test_wheel_contents.py"
  - "grep acting\\(\\)|act_as_local|LOCAL_MACHINE_NAME|10\\.1b|id_names|id_resolver|local_served_edges|open_hub_store|result_from_document|store_open|hub_fixture|in_process_hub|rm_machine|OPERATION_ERRORS|lock probe|wiring_results|ServedEdges|act_as\\( in /Users/manta/source/repos/manta/amoeba/project-documents/user/tasks/260-tasks.hub-and-door.md"
  - "list_files .github/workflows/*.{yml,yaml} in ."
  - "grep addopts|markers|testpaths|norecursedirs|ignore|load|live|-m  in /Users/manta/source/repos/manta/amoeba/pyproject.toml"
  - "grep tests/load|test_door_load|door load|load test in /Users/manta/source/repos/manta/amoeba/project-documents/user/tasks/260-tasks.hub-and-door.md"
  - "grep wake in /Users/manta/source/repos/manta/amoeba/tests/cli/test_requests_scenario.py"
  - "grep class Deps|^    \\w+: |cf_run|git in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/deps.py"
  - "grep ^def |^class |wake_command|settings\\.|scope in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/wakes.py"
  - "grep \"-p\"|-p\\b|project_id|read_program_sources|read_target|resolve_slice|gather\\( in /Users/manta/source/repos/manta/amoeba/tests/operations/test_program_sources.py"
  - "grep \"-p\"|CF_PROJECT_FLAG|project_id=|gather\\( in /Users/manta/source/repos/manta/amoeba/tests/operations/test_pause_context_slice.py"
  - "list_files src/amoeba/{mcp/tools.py,cli/registration_arguments.py,cli/render/registry.py,operations/status_runs.py,store/checkouts.py,operations/list_view.py} in ."
  - "grep project_details|project_names|_project_names|commands\\.project_names|details= in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep project_details|project_names|_project_names|details= in /Users/manta/source/repos/manta/amoeba/tests/operations/test_list_registry.py"
  - "grep project_names|_project_names|project_details|cf list|list projects in /Users/manta/source/repos/manta/amoeba/tests/cli"
  - "grep project_names|project_details|project_of in /Users/manta/source/repos/manta/amoeba/tests/test_wiring.py"
  - "grep def open\\(|migrate\\(|def migrate|EXPECTED_SCHEMA_VERSION in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/store.py"
  - "grep def test_|project_of|project_names|project_details|resolve_member|MESSAGE|OPERATIONS|parametrize|\\.write\\(\\)|write\\( in /Users/manta/source/repos/manta/amoeba/tests/load/test_no_cf_under_write_lock.py"
  - "grep class MemberRef|class MemberName|name: str \\| None|name: str in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/changes_models.py"
  - "grep \\bMember\\(|\\bMemberState\\(|\\bMemberRow\\(|\\bMemberRef\\( in /Users/manta/source/repos/manta/amoeba"
  - "grep \\bMember\\(|\\bMemberState\\(|\\bMemberRow\\( in /Users/manta/source/repos/manta/amoeba/tests"
sectionsInDocument: 19
sectionsCovered: 19
effort: xhigh
turns: 82
promptTokens: 6467580
cachedTokens: 6176803
cacheWriteTokens: 290707
completionTokens: 179524
durationSeconds: 761.9
costUsd: 0.950531
costBasis: provider
runId: run-20261121-p5-01fb5c21
squadronVersion: 0.24.35
findings:
  - id: F001
    severity: fail
    category: test-breakage
    summary: "Named test-edit list leaves out the `Deps` builders that 7.7 breaks"
    location: "tests/operations/pause_support.py:157"
  - id: F002
    severity: fail
    category: test-breakage
    summary: "Status placement tests are rewritten by 12.5 but not named"
    location: "tests/operations/test_status_placement.py:58"
  - id: F003
    severity: fail
    category: test-breakage
    summary: "Standing and report_release tests break on the signature and monkeypatch changes of 7.3 and 7.5"
    location: "tests/cli/test_standing_cli.py:42"
  - id: F004
    severity: fail
    category: test-breakage
    summary: "Required new fields break direct `Member` and `MemberState` constructions, and none is named"
    location: "tests/operations/program_rig.py:152"
  - id: F005
    severity: fail
    category: sequencing
    summary: "`upsert_member` gains a `name` without a plan for its callers"
    location: "src/amoeba/store/programs.py:184"
  - id: F006
    severity: fail
    category: test-breakage
    summary: "The members-statement scan test rejects the statements 2.2, 5.1 and 6.1 add"
    location: "tests/store/test_members_queried_in_one_place.py:24"
  - id: F007
    severity: fail
    category: test-breakage
    summary: "The `git_read` allowlist test pins the set 3.2 changes"
    location: "tests/upstream/test_git_read.py:82"
  - id: F008
    severity: fail
    category: contract-docs
    summary: "Message bounds change at 7.1, but the MCP doc that pins them is updated only in 17.1, which does not cover it"
    location: "docs/mcp-server.md:127"
  - id: F009
    severity: fail
    category: contract-docs
    summary: "New CLI flags land without the contract entries the test requires"
    location: "tests/test_contract_docs.py:236"
  - id: F010
    severity: fail
    category: missing-caller
    summary: "The pause path has no way to get the caller's Context Forge id to `gather`"
    location: "src/amoeba/operations/pause_claim.py:262"
  - id: F011
    severity: concern
    category: interface-gap
    summary: "`gather_add` and `gather_checkout` take a git runner that nothing supplies"
    location: "src/amoeba/operations/deps.py:45"
  - id: F012
    severity: concern
    category: scope
    summary: "The `update.partial` guard is outside the design and contradicts its operator walkthrough"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:467"
  - id: F013
    severity: concern
    category: test-breakage
    summary: "The update-script tests break under the new read-back checks, and the schema-11 fixture is not provided"
    location: "tests/scripts/test_update_live.py:40"
  - id: F014
    severity: concern
    category: accuracy
    summary: "The `set_up.py` size claim is wrong"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:42"
  - id: F015
    severity: concern
    category: test-design
    summary: "Pinning this clone's `origin` makes 3.3 environment-dependent and can BLOCK"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:123"
  - id: F016
    severity: concern
    category: proportionality
    summary: "13.3 is too large for one step"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:403"
  - id: F017
    severity: concern
    category: proportionality
    summary: "Section 9 is one commit of twelve subtasks"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:261"
  - id: F018
    severity: concern
    category: behavior
    summary: "The `_checkout_of` rewrite may drop the path resolution it depends on"
    location: "src/amoeba/operations/pause_eligibility.py:125"
  - id: F019
    severity: concern
    category: proportionality
    summary: "Overweight task file with granular sections"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:1"
  - id: F020
    severity: note
    category: accuracy
    summary: "2.2 and 2.3 cross-reference"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:43"
  - id: F021
    severity: note
    category: dead-code
    summary: "`projects.project_names` is unused in `src` after 10.3"
    location: "src/amoeba/upstream/context_forge/projects.py:49"
  - id: F022
    severity: note
    category: traceability
    summary: "The load test path is not named"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:456"
  - id: F023
    severity: note
    category: accuracy
    summary: "Importer count is off"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:133"
  - id: F024
    severity: note
    category: sequencing
    summary: "Test-with pattern is loose in sections 2 and 4"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:86"
  - id: F025
    severity: note
    category: commits
    summary: "Commit markers sit at section ends, but several are red as written"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:109"
  - id: F026
    severity: pass
    category: coverage
    summary: "Success criteria are covered by tasks"
    location: "project-documents/user/slices/261-slice.members-by-name.md:553"
  - id: F027
    severity: pass
    category: gating
    summary: "CI runs the load test in the normal tier"
    location: ".github/workflows/ci.yml:40"
  - id: F028
    severity: pass
    category: precondition
    summary: "Names from 260 match 260's task file"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:128"
  - id: F029
    severity: pass
    category: accuracy
    summary: "Existing files and line counts match"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:58"
---

# Review: tasks — slice 261

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Named test-edit list leaves out the `Deps` builders that 7.7 breaks

7.7 deletes `Deps.project_names` (`src/amoeba/operations/deps.py:65`). `build_deps` in `tests/operations/pause_support.py:157-172` builds `Deps(...)` with `project_names=` at line 168. `tests/operations/status_support.py:165` does the same. Other tests change that field with `replace(... project_names=...)`: `test_decisions.py:87`, `test_mark_read.py:145`, `test_prune.py:248`, `test_retract.py:57`, `test_status_matches_handle_pause.py:199,225`, `test_held_question_exits.py:214`, `test_status_sessions.py:193`. Each one raises `TypeError` once 7.7 lands, so the section 7 commit (line 239) is red. Line 49 allows one kind of test edit and says "fix the new code, not the test", but no code can keep a field the design removes. Add these modules to line 49 as fixture edits.

### [FAIL] Status placement tests are rewritten by 12.5 but not named

12.5 (lines 380-386) drops `ProjectOf` and the `project_of` parameter of `place_runs` (`src/amoeba/operations/status_placement.py:27,54-59,80`). Every test in `tests/operations/test_status_placement.py` passes a `_ProjectOf` stand-in as the fourth argument (`_place` at lines 58-59, call sites through line 248). The module breaks at the section 12 commit (line 391). `status_support.py` and the scripted `list_runs`/`project_names` deps in the `test_status*.py` files depend on status inputs that 12.5 changes. Name these edits, or say 12.5 rewrites them.

### [FAIL] Standing and report_release tests break on the signature and monkeypatch changes of 7.3 and 7.5

7.5 removes standing's `project_of` lookup (`src/amoeba/operations/standing.py:113`). `test_standing_cli.py` monkeypatches `standing_operation.project_of` at lines 42 and 172, and `monkeypatch.setattr` raises `AttributeError` for a name the module no longer has. 7.3, with the section 7 intro (line 197), moves `report_release` to take `here` in place of `directory`. `tests/load/test_no_cf_under_write_lock.py:60-65` calls `report_release(store, ..., directory=PROVIDER_DIR, deps=deps)`, and line 45 says that test "keeps passing". It cannot without a call-site change. Neither edit is in line 49.

### [FAIL] Required new fields break direct `Member` and `MemberState` constructions, and none is named

2.2 adds `Member.name: str` with no default (line 96), and 11.1 adds `MemberState.name` (line 351). Direct constructions exist at `tests/operations/program_rig.py:152`, `tests/operations/test_status_placement.py:20` (module level), `tests/operations/test_status_runs.py:39`, and `tests/cli/render/test_registration.py:33` (`MemberState`). The `Member` ones break the section 2 commit (line 109), and the `MemberState` one breaks the section 11 commit (line 362). Add them to line 49.

### [FAIL] `upsert_member` gains a `name` without a plan for its callers

Line 76 says `upsert_member` gains a `name` keyword "that the insert binds". The insert path (`programs.py:184-199`) calls `INSERT_MEMBER`, and migration 012's trigger (line 71) aborts a null name. So every caller that does not pass a name fails. Callers include `set_up.py:249` (line 77 covers it) and these tests: `tests/store/test_programs.py:91,130,137,164,166,187,191,231,282`, `tests/store/test_member_removal.py:202,224,244`, `tests/store/test_message_cascade.py:111`, `tests/operations/pause_support.py:193`, `tests/operations/gather_rig.py:97`, `tests/mcp_server/presence_rig.py:97`, `tests/cli/test_pause_cli.py:116`, `tests/operations/test_members.py:44`. The task does not say whether `name` is required or defaulted. If required, each call changes. If defaulted to null, the trigger aborts. Choose one and list the test call sites in line 49.

### [FAIL] The members-statement scan test rejects the statements 2.2, 5.1 and 6.1 add

The test pins hard-coded sets: `ACTIVE_READS` (lines 24-33) and `OTHER_MEMBER_STATEMENTS` (35-43). `test_only_the_named_sql_constants_query_members` (75-85) fails for any constant in `store/sql.py` that matches `FROM|JOIN|INTO|UPDATE members` and is not in those sets. `test_every_active_read_carries_the_predicate` (88-93) requires `ACTIVE_MEMBER` in each active read. `test_the_predicate_is_written_once` (96-103) requires the literal `removed_at IS NULL` only inside `ACTIVE_MEMBER`. 2.2 adds seven member statements (line 97), 5.1 adds two naming statements (line 158), and none is in the sets. The file is listed in 0.1 (line 58), but no edit is planned. Also, `test_no_other_module_names_the_members_table_in_sql` (106-117) fails on any `JOIN members` outside `sql.py`, so the checkout-to-member join that 6.1 needs (line 185) cannot live in `sql_checkouts.py` (line 92). Name the set edits, and put that join in `sql.py` using `{ACTIVE_MEMBER}`.

### [FAIL] The `git_read` allowlist test pins the set 3.2 changes

3.2 adds `remote` to `GIT_SUBCOMMANDS` (line 119). `test_the_allowlist_holds_the_two_read_commands` asserts `GIT_SUBCOMMANDS == {"show", "log", "ls-tree"}` (lines 82-83). Line 120 says "the existing git_read tests pass", and line 49 forbids assertion changes. The docstring at `src/amoeba/upstream/git_read.py:1-7` also says "three read commands". Name the test edit and the docstring change.

### [FAIL] Message bounds change at 7.1, but the MCP doc that pins them is updated only in 17.1, which does not cover it

7.1 sets `MESSAGE_LOOKUPS` to 1 for each of the four operations (line 201). Today it is send 3 and the rest 2 (`src/amoeba/wiring_messages.py:41-46`). That changes `worst_case_seconds`. `docs/mcp-server.md:127` states "105 s (`send`) or 75 s (`inbox`, `reply`, `cancel`)". `tests/test_contract_docs.py:394-399` requires the doc to state each value from `worst_case_seconds`. 17.1 (line 481) lists only the `add` and `rm` tool fields. The section 7 commit (line 239) is red. Add the bound text to 7.1.

### [FAIL] New CLI flags land without the contract entries the test requires

9.11 adds `--name`, `--attach-to` and `--new-member`, and 10.3 adds `rm --checkout`. `test_the_cli_contract_names_every_flag_of_add_rm_and_list` (236-247) requires every `--flag` the parser gives `add`, `rm` and `list` to appear in `docs/cli-contract.md`. None of the four appears there today. Line 48 says each task that adds a contract item adds its entry then. 9.1 (line 266) covers "the new fields", and 17.1 (line 480) writes the prose later. The commits at lines 322 and 346 are red. Put the flag entries in 9.11 and 10.3.

### [FAIL] The pause path has no way to get the caller's Context Forge id to `gather`

7.9 (line 230) makes `pause_context.gather` take `here.project_id`. Its only caller is `pause_claim._prepare` (`pause_claim.py:262-270`), which receives a `PauseTarget` (`src/amoeba/operations/pause_results.py:36-45`: key, question, checkout, member, run_facts). `handle_pause.py:132` builds that target. `pause_eligibility.Eligible` (`pause_eligibility.py:64-73`) carries the member but no Context Forge id. No task names any of these, so the value has no path from `here` to `gather`. Name the field added to `Eligible` and `PauseTarget`, and every call site in `handle_pause.py` and `pause_claim.py`. The design's pause criterion (line 559) depends on this.

### [CONCERN] `gather_add` and `gather_checkout` take a git runner that nothing supplies

4.3 (line 146) and 9.2 (line 269) pass `git` into the client part. `Deps` holds `cf_run` only (`deps.py:45-71`). `pause_eligibility._registered` passes `deps.cf_run` to `add` (`pause_eligibility.py:164`), and 9.11 (line 311) runs `gather_add` from there. No task says where `git` comes from in `Deps` or in `wiring`. Adding a `Deps` field also breaks every builder listed in the first finding. Name the runner and its source.

### [CONCERN] The `update.partial` guard is outside the design and contradicts its operator walkthrough

16.1 (line 467) makes `update` write `update.partial` before install and refuse to start while it exists. The design's D16 (lines 460-470) has no killed-update case. No success criterion covers one: the criterion at design line 584 covers only a failing `cf`. The design's operator walkthrough (design line 677) and D16 (design line 465) say a failed install is fixed by running `update` again. With the guard, an exception from `steps.install` leaves `update.partial`, so the next `update` refuses and says to run `restore`. 17.3 (line 488) updates only the Verification Walkthrough. Either add the decision and a criterion to the design, or cut the guard. Either way, correct design line 677.

### [CONCERN] The update-script tests break under the new read-back checks, and the schema-11 fixture is not provided

16.1 adds `cf_projects` to `Steps` (line 465). `FakeSteps.steps()` (lines 80-85) builds `Steps` from three fields, so it breaks unless it supplies the new one. The new check, "every active member in `cf_projects` has a checkout on `local`", fails for the members `_seed_member` inserts (lines 40-59, no checkouts). So `test_update_backs_up_installs_migrates_and_records` (98-112), the restore tests and the tests expecting success would restore and raise. None of this is named. 16.2 asks for "a copy of a schema-11 store", but the `live` fixture (lines 62-70) calls `Store.open`, which migrates to the current version (`src/amoeba/store/store.py:105`). Name the fixture edits and say how schema 11 is built, as 1.2 does.

### [CONCERN] The `set_up.py` size claim is wrong

Line 42 says `operations/set_up.py` (344 lines) "takes only the interim lines of 1.1 and 2.3, removed in 9.9". 8.1 deletes `_merged_wake_command` (`set_up.py:186-192`) and moves the wake write into the engine. 9.9 changes the references, and 9.3 and 9.7 move the member choice out. The file is already above the ~300-line norm. Correct the claim, state where the engine's wake write goes, or plan a split.

### [CONCERN] Pinning this clone's `origin` makes 3.3 environment-dependent and can BLOCK

3.3 says to run `git remote get-url origin` in the repo root, pin the output as a test literal, and BLOCK if it prints nothing. That value is this clone's remote. CI checks out the repo on a runner (`.github/workflows/ci.yml:17`), where the remote is not the author's, so the literal fails there. A clone with no `origin` blocks a test that needs no remote. Pin the forms the design names as literal cases (design D3: `git@github.com:ecorkran/amoeba.git` and `https://github.com/ecorkran/Amoeba/` both reduce to `github.com/ecorkran/amoeba`), and drop the BLOCKED step.

### [CONCERN] 13.3 is too large for one step

13.3 covers ten `run_served` cases, each with parsing, the acting machine, the hub part, the `send` wake check that raises `CallRefused`, and the `config.yaml` refusal. 13.4 has matching tests. Split it into 13.3a (four reads: `list`, `status`, `inbox`, `changes`) and 13.3b (six writes: `add`, `rm`, `send`, `reply`, `cancel`, `report_release`).

### [CONCERN] Section 9 is one commit of twelve subtasks

Section 9 holds twelve subtasks at effort 5, in one commit (line 322). They cover the request fields, the client gather, `add`'s five steps, the flags, the engine's references, the CLI and MCP changes, and their tests. Split it into a commit after 9.8 (the checkout steps) and one after 9.12 (flags, engine, CLI, MCP). Line 295 requires `add_member.py` to stay near 300 lines.

### [CONCERN] The `_checkout_of` rewrite may drop the path resolution it depends on

`_checkout_of` resolves the directory before walking (`directory.resolve()` at line 128) and falls back to the resolved path. The `_wrong_checkout` docstring (lines 138-139) relies on symlinked paths passing. 4.3 (line 145) says to rewrite it on `git_root(...)` "or the directory itself" without saying that `git_root` resolves, or that the fallback keeps the resolved path. State it, and keep the symlink behavior covered by a test.

### [CONCERN] Overweight task file with granular sections

The file is 491 lines, with 18 sections and about 75 tasks. Cuts:
- Fold 14.1 into section 10. `rm-machine` is one line of code and one test, and its own commit adds little.
- Fold 17.2 into 17.1.
- Shorten the Context Summary (lines 36-51). It restates design decisions the design already gives; keep the precondition, the order and the naming rules.
- List tests by their criterion number rather than full case lists (2.4, 5.4, 9.4, 15.3). The criteria at design lines 553-585 already name the cases.

### [NOTE] 2.2 and 2.3 cross-reference

Line 43 gives the member-name pattern and length as "(2.3)". They are defined in 2.2 (line 95). Fix the reference.

### [NOTE] `projects.project_names` is unused in `src` after 10.3

Its only `src` callers are `deps.py:99` (removed in 7.7) and `cli/commands.py:219` (removed in 10.3). The plan does not delete it. Decide, and list it in 10.3 if it goes.

### [NOTE] The load test path is not named

15.4 says "260's door load test" without a path. 260's task 15.6 puts it in `tests/load/test_door_load.py` (`project-documents/user/tasks/260-tasks.hub-and-door.md:504`). Name the path.

### [NOTE] Importer count is off

Line 133 says "about 14 source" modules import `ContextForgeError` from `operations.members`. Grep finds 11: `changes`, `decisions`, `list_registry`, `list_view`, `member_reference`, `project_lookup`, `set_up`, `set_up_resolve`, `standing`, `status`, `wiring`. The grep rule governs, so this is only a count correction.

### [NOTE] Test-with pattern is loose in sections 2 and 4

2.1 to 2.3 and 4.1 to 4.3 are gated only by "pyright clean", and their tests come in 2.4 and 4.4. This is acceptable because each test task follows its group. But 2.3 changes existing behavior (the interim checkout insert) and is not tested until 2.4.

### [NOTE] Commit markers sit at section ends, but several are red as written

Section-end markers are the right kind of point. As written, these are red because of the findings above: 109 (Member constructions, `upsert_member`, members-scan), 128 (`git_read`), 179 (members-scan), 239 (`Deps`, standing, MCP bounds), 322 and 346 (CLI flag docs), 362 (`MemberState`), and 391 (status placement).

### [PASS] Success criteria are covered by tasks

I traced each Functional, Technical and Integration criterion to a task and a test. Each has one, except the pause-path id threading (finding above).

### [PASS] CI runs the load test in the normal tier

`uv run pytest` runs `tests/load` (`pyproject.toml` `addopts` ignores only `tests/live`), so 15.4's claim holds and the load bound is gated by the existing CI step.

### [PASS] Names from 260 match 260's task file

`Transaction.acting()`, `act_as_local`, `LOCAL_MACHINE_NAME`, `tests/store_open.py`, `open_hub_store`, `ServedEdges`, `id_names`, `id_resolver`, `wiring_door.py`, `OPERATION_ERRORS` and task 10.1b all appear in 260's tasks with the names this plan uses. They are unbuilt, so I checked names against the task file, not code.

### [PASS] Existing files and line counts match

Every file 0.1 names exists. The counts in line 42 are correct: `store/sql.py` 488, `set_up.py` 344, `pause_context.py` 297, `store/models.py` 302, `set_up_models.py` 290.

### Run Digest

- Response length: 37396 chars
- Response is newline-free: no
- Tool calls made: 81
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 82
- Tokens — prompt / cached / cache write / completion / reasoning: 6467580 / 6176803 / 290707 / 179524 / not computed
- Duration: 761.9 s
- Cost: $0.95 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 29
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 29
- Finding-shaped matches — surviving validation: 29
