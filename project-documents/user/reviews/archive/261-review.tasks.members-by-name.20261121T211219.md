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
reviewedSha: fb327d04f3259f2878279e377f54893b529f7815
reviewedBlob: 79b622f6eec89e4a6d27b6a955d7f26d1704a6c9
reviewedBlobCurrent: false
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 81
injected:
  - key: input
    path: "project-documents/user/tasks/261-tasks.members-by-name.md"
    chars: 57347
    sha256: ba7a8ec8145aaad53c962e228e5cf0005f5bd4798eec73c57e7ba2c36e0d1082
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
  - "src/amoeba/operations/wake_status.py"
  - "src/amoeba/operations/wake.py"
  - ".github/workflows/ci.yml"
  - "src/amoeba/operations/members.py"
  - "scripts/update_live.py"
  - "src/amoeba/store/programs.py"
  - "tests/store/test_members_queried_in_one_place.py"
  - "tests/store/seed.py"
  - "src/amoeba/operations/add.py"
  - "src/amoeba/operations/set_up.py"
  - "src/amoeba/operations/set_up_resolve.py"
  - "src/amoeba/wiring_messages.py"
  - "tests/test_message_timing.py"
  - "src/amoeba/upstream/git_read.py"
  - "src/amoeba/operations/pause_eligibility.py"
  - "src/amoeba/operations/inbox.py"
  - "src/amoeba/store/wakes.py"
  - "tests/store/wake_support.py"
  - "tests/operations/test_wake_after_send.py"
  - "src/amoeba/wiring.py"
  - "tests/store/test_schema_holds_no_mirrored_state.py"
  - "src/amoeba/operations/program_sources.py"
  - "src/amoeba/operations/status.py"
  - "tests/cli/test_requests_scenario.py"
  - "tests/store/test_migrations.py"
  - "src/amoeba/operations/pause_context.py"
searches:
  - "list_files src/amoeba/store/schema/*.sql in ."
  - "grep EXPECTED_SCHEMA_VERSION\\s*= in /Users/manta/source/repos/manta/amoeba"
  - "grep wake_command in /Users/manta/source/repos/manta/amoeba/src"
  - "grep project_of\\(|ContextForgeError|operations\\.members|member_reference|project_lookup in /Users/manta/source/repos/manta/amoeba"
  - "grep project_of\\(|ContextForgeError|operations\\.members|member_reference|project_lookup|project_details|project_names|known_to_cf|_Lookups|MESSAGE_LOOKUPS in /Users/manta/source/repos/manta/amoeba/src"
  - "grep EXPECTED_SCHEMA_VERSION|SCHEMA_VERSION in /Users/manta/source/repos/manta/amoeba/src"
  - "grep wake_command|project_of|project_details|project_names|ContextForgeError|operations\\.members|project_lookup|member_reference|known_to_cf in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep operations\\.members|operations\\.member_reference|operations\\.project_lookup|from amoeba\\.operations import members|project_of\\(reference|reference= in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep settings\\.wake_command|recipient\\.wake_command|\\.wake_command\\b|wake_command= in /Users/manta/source/repos/manta/amoeba/tests"
  - "list_files {src/amoeba/store/vocabulary.py,src/amoeba/store/checkouts.py,src/amoeba/operations/errors.py,src/amoeba/operations/origin.py,src/amoeba/operations/here.py,src/amoeba/operations/naming.py,src/amoeba/operations/caller.py,src/amoeba/operations/add_door.py,src/amoeba/operations/status_runs.py,src/amoeb\u2026 in ."
  - "list_files {tests/test_import_boundaries.py,tests/store/test_members_queried_in_one_place.py,tests/test_message_timing.py,tests/cli/test_requests_scenario.py,tests/live/messaging/test_messaging_live.py,tests/store_open.py,tests/store/seed.py,tests/ast_strings.py,tests/hub_fixture.py,tests/hub/in_process_hub.py\u2026 in ."
  - "list_files {scripts/update_live.py,docs/store-contract.md,docs/cli-contract.md,docs/mcp-server.md,docs/program-rules.md,docs/rules.md,src/amoeba/upstream/git_read.py,src/amoeba/upstream/context_forge/project_of.py,src/amoeba/upstream/context_forge/projects.py,src/amoeba/operations/members.py,src/amoeba/operati\u2026 in ."
  - "grep def |^[A-Z_]+ *[:=]|class  in /Users/manta/source/repos/manta/amoeba/scripts/update_live.py"
  - "grep addopts|markers|testpaths|\\[tool\\.pytest|live|load in /Users/manta/source/repos/manta/amoeba/pyproject.toml"
  - "grep upsert_member\\(|insert_member\\(|INSERT INTO members|project_names\\(|project_of\\( in /Users/manta/source/repos/manta/amoeba"
  - "grep upsert_member\\(|checkout: str|checkout TEXT|\\bcheckout\\b.*path|\\.checkout\\b in /Users/manta/source/repos/manta/amoeba/src"
  - "grep def |^[A-Z_]+\\s*[:=]|GIT_SUBCOMMANDS|SUBCOMMAND_ in /Users/manta/source/repos/manta/amoeba/src/amoeba/upstream/git_read.py"
  - "grep def |checkout|\\.git\\b|CHECKOUT in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/pause_eligibility.py"
  - "grep def refuse_door_fields|def _wake|def [a-z_]+\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/add_door.py"
  - "grep class Recipient|project_path|wake_command|def resolve_recipient|def resolve_actor|def resolve_caller|def [a-z_]+\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/message_member.py"
  - "grep def open_state_store|def open_hub_store|def act_as|def acting|LOCAL_MACHINE_NAME|act_as_local|RUN_POLL_TIMEOUT_SECONDS|CF_PROJECTS_TIMEOUT_SECONDS|CF_GET_TIMEOUT_SECONDS|def run_file_exists|run_file_exists|def write\\(|\\.write\\(\\) in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep Store\\.open|open_state_store\\(|open_read_only\\( in /Users/manta/source/repos/manta/amoeba/src"
  - "grep NO_CHECKOUT_DETAIL|start_failed|START_FAILED|directory=None|project_path=None|project_path is None in /Users/manta/source/repos/manta/amoeba"
  - "grep def test_|SCHEMA|schema|EXPECTED|version|def _build|def build|migrate\\( in /Users/manta/source/repos/manta/amoeba/tests/store/test_migration_010.py"
  - "grep wake_command|--wake-command|no_wake_command|settings\\.|\\.settings in /Users/manta/source/repos/manta/amoeba/tests/operations/test_add_wake_command.py"
  - "list_files project-documents/user/{slices,tasks,architecture}/*260* in ."
  - "grep id_names|id_resolver|ServedEdges|SERVED_OPERATIONS|WRITING_CALLS|UNKNOWN_ADVICE|RefusalCode|run_served|rm_machine|act_as_local|LOCAL_MACHINE_NAME|open_hub_store|result_from_document|store_open|in_process_hub|hub_fixture|OPERATION_ERRORS|011_hub_and_door|load|act_as in /Users/manta/source/repos/manta/amoeba/project-documents/user/slices/260-slice.hub-and-door.md"
  - "grep id_names|id_resolver|ServedEdges|act_as_local|LOCAL_MACHINE_NAME|in_process_hub|store_open\\.py|handle_call|rm_machine|result_from_document|test_store_opened_only|lock probe|lock_probe|BEGIN IMMEDIATE|wiring_door|hub_fixture in /Users/manta/source/repos/manta/amoeba/project-documents/user/tasks/260-tasks.hub-and-door.md"
  - "grep upstream|project_of|projects|ALLOW|allowed|operations in /Users/manta/source/repos/manta/amoeba/tests/test_import_boundaries.py"
  - "grep table|TABLE|== \\d+|len\\( in /Users/manta/source/repos/manta/amoeba/tests/test_contract_docs.py"
  - "grep wake_command|members\\.wake in /Users/manta/source/repos/manta/amoeba/tests/store/test_schema_holds_no_mirrored_state.py"
  - "grep NO_CHECKOUT_DETAIL|def test_.*(directory|path|checkout) in /Users/manta/source/repos/manta/amoeba/tests/store/test_wakes.py"
  - "grep ContextForgeError|__all__|project_names|project_of|upsert_member in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/set_up.py"
  - "grep def test_|assert|for table|CATEGORIES|EXPECTED|missing|unclassified in /Users/manta/source/repos/manta/amoeba/tests/store/test_schema_holds_no_mirrored_state.py"
  - "grep ContextForgeError in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep \"-p\"|-p\\b|project_id|member\\.|def gather|def resolve_slice|def _read_committed|read_target|project_of|integration_branch in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/pause_context.py"
  - "grep \"-p\"|project_id|project_of|def read_target|def _concept|def read_concept|missing|member\\.|integration_branch|\\.id\\b in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/program_sources.py"
  - "grep read_target\\(|def read_target|from amoeba.upstream.context_forge.target_read in /Users/manta/source/repos/manta/amoeba/src"
  - "grep SetUpProblemCode|assert_never|class MemberState|class MemberName|class MemberRef|class SetUpResult|working_directory: in /Users/manta/source/repos/manta/amoeba/src"
  - "grep def test_|PRODUCTION|main\\(|Steps\\(|monkeypatch|AMOEBA_HOME|XDG|def _steps|fake in /Users/manta/source/repos/manta/amoeba/tests/scripts/test_update_live.py"
  - "grep def store_path|def config_path|def backups_root|def state_home|def checkout_root|AMOEBA|XDG|Path\\.home|expanduser in /Users/manta/source/repos/manta/amoeba/scripts/update_live.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep resolve_member|resolve_release_member|worst_case_seconds|def project_of|reference: str|add\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep project_of|import|def |lookup in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/status_placement.py"
  - "grep from amoeba\\.upstream\\.context_forge\\.(project_of|projects) import|import amoeba\\.upstream\\.context_forge\\.(project_of|projects) in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep CFProject|CFProjectNotFound|working_directory|WorkingDirectory in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/set_up.py"
  - "grep CFProject|working_directory|WorkingDirectory in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/set_up_resolve.py"
  - "grep mark\\.live|pytestmark|markers|addopts|--ignore in /Users/manta/source/repos/manta/amoeba"
  - "grep INSERT INTO members|sql\\.INSERT_MEMBER|INSERT_MEMBER\\b in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep def test_|twelve|TABLES|EXPECTED_TABLES|== \\{|table set|len\\( in /Users/manta/source/repos/manta/amoeba/tests/store/test_schema.py"
  - "grep name: |class MemberName|class MemberRef in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/decisions_models.py"
  - "grep class MemberRef|    name: |project_id:  in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/changes_models.py"
  - "grep wake_command=None in /Users/manta/source/repos/manta/amoeba/tests"
sectionsInDocument: 19
sectionsCovered: 19
effort: xhigh
turns: 82
promptTokens: 7440697
cachedTokens: 7138368
cacheWriteTokens: 302255
completionTokens: 182077
durationSeconds: 778.0
costUsd: 1.010614
costBasis: provider
runId: run-20261121-p5-01fb5c21
squadronVersion: 0.24.35
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Interim naming never reaches the member insert, so `add` breaks from 1.1"
    location: "src/amoeba/operations/set_up.py:249"
  - id: F002
    severity: fail
    category: testing
    summary: "Existing test pins the `start_failed` wake row that D9 removes"
    location: "tests/operations/test_wake_after_send.py:184"
  - id: F003
    severity: fail
    category: testing
    summary: "`add --wake-command` tests assert the member's command, which 8.5 removes"
    location: "tests/operations/test_add_wake_command.py:57"
  - id: F004
    severity: fail
    category: sequencing
    summary: "7.3 deletes the hub readers that 260's `handle_call` still uses"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:301"
  - id: F005
    severity: concern
    category: testing
    summary: "Null-name trigger breaks an existing test that inserts after a full migration"
    location: "tests/store/test_migrations.py:366"
  - id: F006
    severity: concern
    category: testing
    summary: "1.1 misses the schema pins for the new table and columns"
    location: "tests/store/test_schema_holds_no_mirrored_state.py:208"
  - id: F007
    severity: concern
    category: accuracy
    summary: "4.1's importer list is wrong: 14 source modules and 20 test modules import `ContextForgeError` from `members`"
    location: "src/amoeba/operations/members.py:24"
  - id: F008
    severity: concern
    category: testing
    summary: "9.2 deletes `reference` and `members.py` while existing tests pin them"
    location: "tests/upstream/context_forge/test_project_of.py:110"
  - id: F009
    severity: concern
    category: sequencing
    summary: "10.1 misses the member column list and mapper that read `wake_command`"
    location: "src/amoeba/store/sql.py:92"
  - id: F010
    severity: concern
    category: sequencing
    summary: "10.1 misses the consumers that read the removed field"
    location: "src/amoeba/operations/wake_status.py:42"
  - id: F011
    severity: concern
    category: testing
    summary: "Twelve test modules pass `wake_command=None` to `MemberSettings`, which 10.1 removes"
    location: "tests/store/test_programs.py:50"
  - id: F012
    severity: concern
    category: sequencing
    summary: "8.5 writes the command to the checkout while the claim still reads the member until 10"
    location: "src/amoeba/operations/wake.py:87"
  - id: F013
    severity: concern
    category: scope
    summary: "The bulk entry's `wake_command` key and the engine's wake path are unassigned"
    location: "src/amoeba/operations/set_up_models.py:98"
  - id: F014
    severity: concern
    category: scope
    summary: "8.3 is too large for one task"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:230"
  - id: F015
    severity: concern
    category: process
    summary: "The test-with pattern is broken in sections 7, 8, 9, 12 and 13"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:210"
  - id: F016
    severity: concern
    category: coverage
    summary: "FR6's second half has no test"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:289"
  - id: F017
    severity: concern
    category: coverage
    summary: "FR7's registration case omits the concept file"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:268"
  - id: F018
    severity: concern
    category: testing
    summary: "Two design rules have no test, though D15 requires one per case"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:163"
  - id: F019
    severity: concern
    category: process
    summary: "Hallucination trap in 3.3"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:117"
  - id: F020
    severity: concern
    category: security
    summary: "`git_read` will accept any `remote` subcommand, so writes become reachable"
    location: "src/amoeba/upstream/git_read.py:119"
  - id: F021
    severity: concern
    category: accuracy
    summary: "4.3 cannot reuse the checkout finder to detect \"not a repo\""
    location: "src/amoeba/operations/pause_eligibility.py:132"
  - id: F022
    severity: concern
    category: accuracy
    summary: "The 12.3 claim about `status_placement` is wrong, and the import rule in 13.5 still fails"
    location: "src/amoeba/operations/status_placement.py:21"
  - id: F023
    severity: concern
    category: accuracy
    summary: "7.4 names a `resolve_member` call in `wiring.py` that does not exist"
    location: "src/amoeba/wiring.py:35"
  - id: F024
    severity: concern
    category: sequencing
    summary: "A killed `update` leaves a state that a rerun turns into a lost restore point"
    location: "scripts/update_live.py:224"
  - id: F025
    severity: concern
    category: testing
    summary: "16.2 cannot test `update` through `main` safely, and the test file already exists"
    location: "scripts/update_live.py:297"
  - id: F026
    severity: concern
    category: accuracy
    summary: "15.4 names a \"live marker\" that does not exist"
    location: "pyproject.toml:64"
  - id: F027
    severity: note
    category: dependencies
    summary: "260 is not built, so 0.1 will stop BLOCKED"
    location: "src/amoeba/store/migrations.py:25"
  - id: F028
    severity: note
    category: sequencing
    summary: "The Context Summary says each section leaves the suite passing, but 1.2 says it may fail"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:37"
  - id: F029
    severity: note
    category: docs
    summary: "The fixture-edit record does not match the tasks"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:47"
  - id: F030
    severity: note
    category: scope
    summary: "`MemberRef.name` is still nullable, though D13 says `name` is never null"
    location: "src/amoeba/operations/changes_models.py:53"
  - id: F031
    severity: note
    category: process
    summary: "The door load test is already gated by CI"
    location: ".github/workflows/ci.yml:40"
  - id: F032
    severity: note
    category: docs
    summary: "`questions.checkout` already means a directory path"
    location: "src/amoeba/store/models.py:120"
  - id: F033
    severity: pass
    category: coverage
    summary: "Functional requirements trace to tasks, with two exceptions"
    location: "project-documents/user/slices/261-slice.members-by-name.md:553"
---

# Review: tasks — slice 261

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Interim naming never reaches the member insert, so `add` breaks from 1.1

Task 1.1 (line 69) adds a trigger that aborts an insert when `members.name` is null, and line 72 gives `upsert_member` a `name` keyword. Line 73 says the interim is in `operations/add.py` only. But `add.py:148–155` passes a built request to `set_up()`, and the member row is written at `set_up.py:249` by `upsert_member(...)`, which gets no name. Bulk entries have no name source until 8.1 (line 223). From 1.1 onward every `add` that creates a member, single or bulk, fails, so the success of 2.3 (line 98, "the full suite is at baseline") cannot hold. The task never says how the name reaches `_write_member`.

### [FAIL] Existing test pins the `start_failed` wake row that D9 removes

D9 (design line 345) says a member with no path gets no checkout and no wake is claimed, "where today the wake would be claimed and end as start_failed". `test_wake_after_send.py:184–210` asserts that row and the text "Context Forge" in its detail. `tests/store/test_wakes.py:190–199` pins the same branch of `claim_wake` (`store/wakes.py:167–184`). Task 10.1 (line 298) rewrites `claim_wake` but names neither test. Line 47 says no assertion changes except where a task names it, and that a failing test is fixed in the code. Followed literally, the implementer must keep the behaviour D9 removes. 10.1 should name both assertions as edits, or state which branch is dropped.

### [FAIL] `add --wake-command` tests assert the member's command, which 8.5 removes

`test_add_wake_command.py:57` returns `settings.wake_command` from the member after `add --wake-command`, and line 149 reads `row.wake_command` from the member view. Task 8.5 (lines 245–246) writes the command to the checkout and stops `add` writing the member's column. These assertions fail at 8.5 and no task names them. 8.10 adds new tests but does not edit these. `tests/cli/test_add_wake_command_cli.py` needs the same check. This is the same rule conflict as the previous finding.

### [FAIL] 7.3 deletes the hub readers that 260's `handle_call` still uses

Task 7.3 (line 199) deletes 260's `id_names`, `id_resolver` and the names and resolver fields of `ServedEdges`. 260's task (line 301) says the `handle_call` run "uses `id_names` and `id_resolver` from `operations.served`". No task before 13.3 rewires `hub/calls.py`, and 13.3 (line 360) only adds a branch. After section 7 the hub cannot import, so the commit at line 217 is broken and 7.4's "full suite is at baseline" cannot hold. Either move the hub to store-read edges in 7.3, or move the deletion after 13.3.

### [CONCERN] Null-name trigger breaks an existing test that inserts after a full migration

`test_a_closed_question_needs_a_known_reason` calls `migrate(connection)` at line 363 (the latest schema) and then inserts a member with no name at 365–369. The 012 trigger (line 69) aborts that insert. Task 2.3 (line 96) updates only `tests/store/seed.py`, and 1.2 names no fix for this test.

### [CONCERN] 1.1 misses the schema pins for the new table and columns

`test_every_column_is_pinned_under_one_reason` (208–213) requires every column in `COLUMN_REASONS`. `test_the_store_contract_lists_the_same_columns_under_the_same_reasons` (219–224) requires a matching item in `docs/store-contract.md`. Adding `members.name`, `members.origin` and nine `checkouts` columns breaks both. `tests/store/test_schema.py:24` (`TABLES`) and `:86` (`test_a_new_store_has_all_thirteen_tables`) pin the table set, so the new table breaks that test too. Task 1.1 (line 71) names only `test_contract_docs.py`'s count.

### [CONCERN] 4.1's importer list is wrong: 14 source modules and 20 test modules import `ContextForgeError` from `members`

Task 4.1 (line 126) says "update its importers (`wiring.py`, `members.py` until it is deleted)". The source importers are `changes.py:24`, `decisions.py:33`, `list_registry.py:16`, `list_view.py:34`, `member_reference.py:12`, `message_member.py:14`, `pause_eligibility.py:21`, `project_lookup.py:10`, `release_member.py:12`, `set_up.py:22` (also re-exported in `__all__` at line 65), `set_up_resolve.py:13`, `standing.py:16`, `status.py:24`, and `wiring.py:35`. Test importers include `tests/operations/test_add.py:14`, `test_rm.py:21`, `test_status.py:14` and `tests/test_wiring.py:33`, about sixteen more. "Full suite at baseline" fails until all are updated. Name them, or keep a re-export in `members.py` until 9.2 and say so.

### [CONCERN] 9.2 deletes `reference` and `members.py` while existing tests pin them

`test_project_of.py:110` and `:151` call `project_of(reference=...)`. `tests/operations/test_members.py:19` imports from `operations.members`. Task 9.2 (lines 282–283) deletes both and says the grep finds nothing in `tests`, but names neither test file.

### [CONCERN] 10.1 misses the member column list and mapper that read `wake_command`

`_MEMBER_COLUMNS` (`sql.py:92–95`) ends with `wake_command`, and `programs._member` reads it positionally at index 9 (`programs.py:53`). `_MEMBER_INSERT_COLUMNS` (87–89) is also a member column list. Task 10.1 (line 297) covers `INSERT_MEMBER` and the update statements only, not these columns, the mapper, or `upsert_member`'s uses at `programs.py:197, 210, 231`. The 10.2 pin (line 304), that only the naming statements name the column, fails with them left in.

### [CONCERN] 10.1 misses the consumers that read the removed field

`wake_status.read_member_wakes` reads `member.settings.wake_command` (line 42). `operations/wake.py:87` gates the wake on `recipient.wake_command` and `:114` on `recipient.project_path`. `message_member.py:143` builds `Recipient` from the member's command. Task 10.1 (lines 296–301) names only `store/wakes.py`, `Recipient` and `send`. The status wake display and the send path break at removal. The task should say what `wake_status` shows for a member whose command now lives on checkouts.

### [CONCERN] Twelve test modules pass `wake_command=None` to `MemberSettings`, which 10.1 removes

`wake_command=None` is a keyword in `MemberSettings(...)` constructions at `tests/store/test_programs.py:50`, `test_member_removal.py:90`, `test_message_cascade.py:120`, `tests/operations/program_rig.py:160`, `gather_rig.py:106`, `pause_support.py:202`, `test_members.py:53`, `test_answering_settle.py:180`, `test_member_answering.py:29`, `tests/mcp_server/presence_rig.py:106`, `tests/cli/test_pause_cli.py:125` and `tests/answering/test_default_rules_reads.py:136`. Task 10.1's fixture edit (line 300) covers only `insert_member(wake_command=...)`. Without an edit here the suite fails at 10.1.

### [CONCERN] 8.5 writes the command to the checkout while the claim still reads the member until 10

Task 8.5 (line 245) writes the command to the caller's checkout, and line 246 says `add` no longer writes the member's command. The claim still reads the member's column until 10.1: `wake.py:87`, `message_member.py:143` and `store/wakes.py:125`. An `add --wake-command` committed at the end of section 8 (line 272) therefore wakes nothing. Line 37 says the command "stays on `members` until section 10", which contradicts 8.5. Either write both until section 10, or move the write into 10.1.

### [CONCERN] The bulk entry's `wake_command` key and the engine's wake path are unassigned

`set_up_models.py:98` gives bulk entries a `wake_command` field. `set_up_resolve.py:179–180` carries it into `ResolvedMember`, and `set_up.py:186–214` merges it into `MemberSettings`. Task 8.5 covers only the CLI flags. The design (D7, line 322) moves the command to the caller's checkout, and line 324 says the bulk document keeps its shape. The task should say whether a bulk entry's `wake_command` is refused, ignored, or sets the entry's checkout.

### [CONCERN] 8.3 is too large for one task

Task 8.3 (lines 230–238) holds five steps with their branches, two flags, `--name`, the change records and every refusal detail, all in one new module. Line 238 expects that module to pass 300 lines. Split it into the five steps, and the flags with `--name`.

### [CONCERN] The test-with pattern is broken in sections 7, 8, 9, 12 and 13

Tests come after several implementation tasks: 7.1–7.5 are followed by 7.6 (line 210), 8.1–8.8 by 8.9 (line 259), 9.1–9.2 by 9.3 (line 288), 12.1–12.3 by 12.4 (line 340), and 13.1–13.4 by 13.5 (line 366). Several implementation tasks (8.2, 8.4, 12.1, 12.2) have only "pyright clean" as success, so nothing checks them for a long time. Move each test task right after the task it proves.

### [CONCERN] FR6's second half has no test

Design line 558 requires that after `rm --checkout <old path>`, `add` in the new directory attaches to the same member with the new path. Task 8.9 (lines 259–263) covers `--new-member` after `rm --checkout`, a different case. Task 9.3 (line 289) covers `rm --checkout` alone. The attach-after-move case is untested.

### [CONCERN] FR7's registration case omits the concept file

Design line 559 requires that a pause which registers the repo still reads the plan, the target branch and another member's concept file. Task 8.10 (line 268) checks only the plan and target branch.

### [CONCERN] Two design rules have no test, though D15 requires one per case

D15 (design line 443) requires a unit test per naming case. The "two calls at once" behaviour (D4, design line 231; task 5.1 line 153) has no test in 5.4. D11's client-times rule (design line 385: paused and calls-log times matched by equality, never compared with the hub clock) has no test in 12.4 (lines 341–344).

### [CONCERN] Hallucination trap in 3.3

Task 3.3 tells the implementer to read this repo's own `origin` with `git remote get-url origin` and pin it, and places example addresses (`git@host:org/repo.git`, `https://host/Org/Repo/`) in the same bullet. `git remote get-url` exits 2 with no remote, and the example is then the nearest plausible value. AGENTS.md forbids this shape. The task should say what to do when the command prints nothing (stop with `BLOCKED:`), or pin a fixture address instead.

### [CONCERN] `git_read` will accept any `remote` subcommand, so writes become reachable

`git_read` checks only the first non-option argument against `GIT_SUBCOMMANDS` (`_subcommand` at 96–101; the check at 119–121). Task 3.2 (line 114) adds `remote` to that set, so `("remote", "remove", "origin")` or `("remote", "set-url", ...)` pass the read guard. The module is a read runner. Either check the whole argument tuple against `remote get-url origin`, or add a separate guard for `remote`.

### [CONCERN] 4.3 cannot reuse the checkout finder to detect "not a repo"

Task 4.3 (line 138) says to move `pause_eligibility`'s checkout finder and reuse it so that "no `.git` entry in the project path or any parent gives `origin` null with no git call". `_checkout_of` (125–132) returns the directory itself when it finds no `.git`, so a caller cannot tell "not a repo" from "is a repo". `_wrong_checkout` (135–142) depends on the current fallback. The finder needs a distinct not-a-repo result, and `pause_eligibility` must adapt. Name that in 4.3.

### [CONCERN] The 12.3 claim about `status_placement` is wrong, and the import rule in 13.5 still fails

Task 12.3 (line 335) says `status_placement` "loses its `project_of` import". It does not import `project_of`: it receives it as the parameter `project_of: ProjectOf` (line 58). It does import `CFProject` and `CFProjectNotFound` from the `project_of` module (line 21). Task 13.5 (line 369) allows only `operations.here`, `naming` and `run_gather` to import `project_of` or `projects`. The type imports also remain in `set_up.py:62` (`_working_directory`, lines 114–124), `set_up_resolve.py:26` (the `working_directory` type, line 80) and `program_sources.py:36`. The plan does not say how the engine's `working_directory` is built from `here`.

### [CONCERN] 7.4 names a `resolve_member` call in `wiring.py` that does not exist

Task 7.4 (line 203) lists `wiring.py` among the files with a `resolve_member` call to replace. `wiring.py` imports only `ContextForgeError` (line 35) and calls no `resolve_member`. The real callers are `message_member.py:90`, `pause_eligibility.py:171, 189`, `release_member.py:41`, `status.py:127` and `wiring_presence.py:67`.

### [CONCERN] A killed `update` leaves a state that a rerun turns into a lost restore point

`update()` takes a backup (227), installs (229), migrates (230), checks (231), records the commit (239) and deletes older backups (240–242). Task 16.1 covers a failed check or a failed `amoeba list` by restoring. A process killed between 230 and 239 leaves a migrated store, the old `installed-commit`, and the pre-migration backup. Running `update` again takes a new backup of the migrated store and then deletes the pre-migration backup at 240–242. D16 names that danger for the failed case but not for a kill. Task 16.1 should refuse `update` while a backup is newer than the recorded commit, and point to `restore`.

### [CONCERN] 16.2 cannot test `update` through `main` safely, and the test file already exists

`main()` always uses `PRODUCTION` (line 310). Its `_uv_install` runs `uv tool install --force --reinstall` on the real tool (248), and `_amoeba_list` runs the real `amoeba list` (253). A test calling `main(["update"])` reinstalls the user's tool. `tests/scripts/test_update_live.py` already exists with a `FakeSteps` helper and failed-read-back and restore tests (lines 81, 146, 184), so 16.2 should extend that file, not create it. `_amoeba_list` uses `check=True`, so a failed `amoeba list` raises `CalledProcessError`, which `main` does not catch (only `UpdateError`, line 315). 16.1 should wrap it.

### [CONCERN] 15.4 names a "live marker" that does not exist

Task 15.4 (line 409) says the live variant "passes when run with the live marker". No marker is defined. `pyproject.toml:64` ignores `tests/live` by default, and that directory is collected only when named explicitly, for example `uv run pytest tests/live/messaging`.

### [NOTE] 260 is not built, so 0.1 will stop BLOCKED

`EXPECTED_SCHEMA_VERSION` is 10. `011_hub_and_door.sql`, `operations/served.py`, `errors.py`, `machines.py`, `wiring_door.py`, `tests/hub_fixture.py`, `tests/hub/in_process_hub.py` and `tests/store_open.py` do not exist. The BLOCKED gate is the correct response.

### [NOTE] The Context Summary says each section leaves the suite passing, but 1.2 says it may fail

Line 37 says each section leaves the suite passing. Line 78 says the full suite may fail until 2.3. The commit at line 104 covers both, so no commit is broken, but the rule as written is wrong.

### [NOTE] The fixture-edit record does not match the tasks

Line 47 names two small-conflict fixture edits (7.1 and 10.1). Task 8.8 (line 257) adds a third kind, and 17.3 (line 437) records only the Migration Plan's "Behavior kept" line. The record should list all three.

### [NOTE] `MemberRef.name` is still nullable, though D13 says `name` is never null

D13 says `MemberName` and `MemberRef` keep their shape and "`name` is never null now". `changes_models.py:53` still declares `name: str | None`, and no task changes it.

### [NOTE] The door load test is already gated by CI

CI runs `uv run pytest`, and `pyproject.toml` ignores only `tests/live`. So `tests/load/test_door_load.py` runs in CI without new wiring. Task 15.4 should say so instead of leaving it implicit.

### [NOTE] `questions.checkout` already means a directory path

The question record's `checkout` field is a directory path, and `insert_question` takes the same kind of value (`tests/store/seed.py:105`). The new `checkouts` table uses the same word for a different thing. Nothing breaks, but the store contract should say which is which.

### [PASS] Functional requirements trace to tasks, with two exceptions

I traced the 32 functional requirements (design lines 553–584) to named tasks and tests. All of them map except the FR6 attach-after-move case and the FR7 concept-file case, which are the coverage findings above.

### Run Digest

- Response length: 38361 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 7440697 / 7138368 / 302255 / 182077 / not computed
- Duration: 778.0 s
- Cost: $1.01 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 33
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 33
- Finding-shaped matches — surviving validation: 33
