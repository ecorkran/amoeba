---
docType: review
layer: project
reviewType: tasks
slice: members-by-name
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/261-tasks.members-by-name.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261121
dateUpdated: 20261121
reviewedSha: 00bcb024172b746c07f462c9fefd41ef6fa8863f
reviewedBlob: b91de3a9bfb03e60a2b8c6e91ae8e8ea478626f7
reviewedBlobCurrent: false
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 89
injected:
  - key: input
    path: "project-documents/user/tasks/261-tasks.members-by-name.md"
    chars: 77336
    sha256: 446e858d65bd4738a961ac907fd3e823fac21b021b3d856f41ddd858eacbcbcb
    whole: true
  - key: against
    path: "project-documents/user/slices/261-slice.members-by-name.md"
    chars: 83536
    sha256: 8d68f43817bb65721749dd2b86adca2c7f54cbe2f32c97def4628861f0a682d6
    whole: true
  - key: conventions
    path: "AGENTS.md"
    chars: 23952
    sha256: 9b993051f9050d1c957047099dab80641d2fc9a22a808766fe481968eaee78ce
    whole: true
filesRead:
  - "tests/store/test_members_queried_in_one_place.py"
  - "tests/test_message_timing.py"
  - "tests/cli/test_add_cli.py"
  - "tests/cli/test_rm_cli.py"
  - "tests/cli/test_list_cli.py"
  - "tests/operations/test_message_member.py"
  - "tests/cli/render/test_registry.py"
  - "tests/cli/test_add_wake_command_cli.py"
  - "src/amoeba/store/wakes.py"
  - "src/amoeba/operations/set_up.py"
  - "src/amoeba/operations/set_up_resolve.py"
  - "src/amoeba/upstream/git_read.py"
  - "scripts/update_live.py"
  - "tests/scripts/test_update_live.py"
  - "tests/upstream/test_git_read.py"
  - "tests/test_import_boundaries.py"
  - "tests/store/test_migrations.py"
  - "tests/store/seed.py"
  - "src/amoeba/store/programs.py"
  - "docs/mcp-server.md"
  - "src/amoeba/operations/deps.py"
  - "src/amoeba/operations/add.py"
  - "src/amoeba/wiring.py"
  - "src/amoeba/operations/list_registry.py"
  - "src/amoeba/operations/program_sources.py"
  - "tests/operations/test_set_up_validation.py"
  - "src/amoeba/wiring_presence.py"
  - "src/amoeba/operations/pause_eligibility.py"
searches:
  - "list_files src/amoeba/store/**/*.py in ."
  - "list_files src/amoeba/operations/*.py in ."
  - "list_files src/amoeba/wire/**/*.py in ."
  - "list_files src/amoeba/hub/**/*.py in ."
  - "list_files src/amoeba/upstream/**/*.py in ."
  - "list_files src/amoeba/store/schema/*.sql in ."
  - "grep ContextForgeError|CfCallFailed in /Users/manta/source/repos/manta/amoeba/src"
  - "grep ContextForgeError|CfCallFailed in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/sql.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/set_up.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/programs.py"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/models.py"
  - "grep upsert_member\\(|INSERT INTO members|UPDATE members|wake_command in /Users/manta/source/repos/manta/amoeba"
  - "grep claim_wake\\(|can_wake\\(|NO_CHECKOUT_DETAIL|project_path|directory= in /Users/manta/source/repos/manta/amoeba/src"
  - "grep operations\\.members|member_reference|project_lookup|NotInProgram|NotAProject|resolve_member\\b|resolve_caller|resolve_actor|resolve_recipient in /Users/manta/source/repos/manta/amoeba"
  - "grep project_names|project_details|project_of\\(|ProjectOf in /Users/manta/source/repos/manta/amoeba"
  - "grep \\b(Member|MemberRow|MemberState|MemberRef|Recipient|PauseTarget|Eligible|ResolvedMember|Anchor|Deps)\\( in /Users/manta/source/repos/manta/amoeba"
  - "grep SELECT_MEMBER|MEMBER_COLUMNS|_MEMBER_INSERT|REREGISTER_MEMBER|INSERT_MEMBER|def get_member|def members_|ACTIVE_MEMBER|removed_at IS|OTHER_MEMBER|ACTIVE_READS in /Users/manta/source/repos/manta/amoeba/src"
  - "grep ACTIVE_READS|OTHER_MEMBER_STATEMENTS|ACTIVE_MEMBER|def test_|SQL_NAMED|_STATEMENTS in /Users/manta/source/repos/manta/amoeba/tests/store/test_members_queried_in_one_place.py"
  - "grep COLUMN_REASONS|members\\.|checkouts|def test_ in /Users/manta/source/repos/manta/amoeba/tests/store/test_schema_holds_no_mirrored_state.py"
  - "grep def test_(a_)?cf_?fail|def test_.*cf_failure|def test_.*cf_is_down|def test_.*(timeout|propagates) in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep directory|NO_CHECKOUT|start_failed|def test_the_limit|def test_.*null|def test_.*directory in /Users/manta/source/repos/manta/amoeba/tests/store/test_wakes.py"
  - "grep _checkout_of|def _git_root|\\.git|resolve\\(\\) in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/pause_eligibility.py"
  - "grep ^(class |def |from |import )|installed-commit|exist_ok|previous|SELECT_SCHEMA_VERSION|CalledProcessError|UpdateError\\(|KeyboardInterrupt in /Users/manta/source/repos/manta/amoeba/scripts/update_live.py"
  - "grep ^(class |def |from |import )|class FakeSteps|def _migrate|def cf_|naming|exist_ok|monkeypatch|def test_ in /Users/manta/source/repos/manta/amoeba/tests/scripts/test_update_live.py"
  - "list_files tests/{load,live/messaging,hub,wire,store/test_migration_01*,store/schema*,scripts}/**/*.py in /Users/manta/source/repos/manta/amoeba"
  - "list_files {.github/workflows/*.yml,pyproject.toml,tests/test_import_boundaries.py,tests/test_contract_docs.py,tests/upstream/test_git_read.py,tests/cli/test_requests_scenario.py,tests/hub_fixture.py,tests/operations/test_members.py,tests/store/test_schema.py,tests/store/test_migrations.py,tests/operations/hel\u2026 in /Users/manta/source/repos/manta/amoeba"
  - "grep addopts|ignore|deselect|markers|testpaths in /Users/manta/source/repos/manta/amoeba/pyproject.toml"
  - "grep name:|run:|pytest in /Users/manta/source/repos/manta/amoeba/.github/workflows/ci.yml"
  - "grep TABLES|def test_.*tables|def test_.*count|EXPECTED_SCHEMA_VERSION|== 11|== 10|== 9\\b|schema_meta|migrate\\(|def _ in /Users/manta/source/repos/manta/amoeba/tests/store/test_schema.py"
  - "grep EXPECTED_SCHEMA_VERSION|== 10\\b|== 9\\b|== 11\\b|version.*10|version.*9\\b in /Users/manta/source/repos/manta/amoeba/tests"
  - "list_files src/amoeba/wiring*.py in /Users/manta/source/repos/manta/amoeba"
  - "grep _member_project_id|project_of|run\\b.*CfRun|def standing|def decisions|cf_run|project_names in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/standing.py"
  - "grep cf_run|run=|project_names|deps\\.|def |resolve_member|project_of|Eligible\\(|resolve_member in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/pause_eligibility.py"
  - "grep cf_run|run=|resolve_member|project_of|anchor|Eligible|def |deps\\. in /Users/manta/source/repos/manta/amoeba/src/amoeba/wiring_presence.py"
  - "grep MESSAGE_LOOKUPS|MESSAGE_STORE_WAITS|def worst_case_seconds|105|75 s|75 seconds|105 seconds|START_AFTER_OPERATIONS\\s*[:=]|RUN_POLL_TIMEOUT_SECONDS\\s*[:=]|CF_GET_TIMEOUT_SECONDS\\s*[:=]|BUSY_TIMEOUT_SECONDS\\s*[:=] in /Users/manta/source/repos/manta/amoeba"
  - "grep MESSAGE_LOOKUPS|MESSAGE_STORE_WAITS|def worst_case_seconds|START_AFTER_OPERATIONS\\s*[:=]|RUN_POLL_TIMEOUT_SECONDS\\s*[:=]|CF_GET_TIMEOUT_SECONDS\\s*[:=]|BUSY_TIMEOUT_SECONDS\\s*[:=]|takes up to|105 s|75 s|worst_case in /Users/manta/source/repos/manta/amoeba/src"
  - "grep 105|75|worst|seconds in /Users/manta/source/repos/manta/amoeba/src/amoeba/mcp/message_tools.py"
  - "grep def open_state_store|def act_as_local|LOCAL_MACHINE_NAME|act_as_local\\(|from amoeba\\.operations|import subprocess|def build_deps|def default_deps|def make_deps|Deps\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep def open_state_store|def open_hub_store|def act_as_local|LOCAL_MACHINE_NAME\\s*[:=]|def act_as\\b|def acting in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep known_to_cf|lookup|class Reference|not_a_member|NOT_A_MEMBER|def resolve_removal|def _member|project_of|CFProject in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations"
  - "grep class SetUpProblemCode|NAME_TAKEN|name_taken|not_a_checkout|member_has|class SetUpOutcome|class SetUpRequest|remove:|class RemoveRequest|checkout in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations"
  - "grep \"--project\"|project=|\\\"project\\\"|def test_ in /Users/manta/source/repos/manta/amoeba/tests/operations/test_add_wake_command.py"
  - "grep start_failed|no checkout|project_path|def test_ in /Users/manta/source/repos/manta/amoeba/tests/operations/test_wake_after_send.py"
  - "grep def resolve_slice|def _read_committed|def gather\\b|def gather\\(|-p|def read_target|def read_plan|project_id|member_id|\\\"-p\\\"|'-p' in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations"
  - "grep def refuse_door_fields|def project_or_rejection|class AddRequest|class RemoveRequest|project:|attach|new_member|checkout|def single_member_request|def rm\\(|def place_rm|def place_add|def place_list|anchors|def _anchors|Anchor\\b in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep claim_wake\\(|can_wake\\(|claim\\( in /Users/manta/source/repos/manta/amoeba/tests"
  - "list_files docs/{store-contract,cli-contract,mcp-server,program-rules,rules,config-contract}.md in /Users/manta/source/repos/manta/amoeba"
  - "grep MemberRow|members\\(|list_registry|project_details in /Users/manta/source/repos/manta/amoeba/tests/cli/test_list_cli.py"
  - "grep claim_wake\\(|can_wake\\(|wake_support import|from store.wake_support|from operations.wake_run_support in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep directory|def claim|def seed_waking_member|claim_wake|insert_member|wake_command in /Users/manta/source/repos/manta/amoeba/tests/store/wake_support.py"
  - "grep claim\\(|directory= in /Users/manta/source/repos/manta/amoeba/tests/store/test_wakes_rows.py"
  - "grep not_a_project|NOT_A_PROJECT|project_of|reference=|resolve_member|known_to_cf|project_names in /Users/manta/source/repos/manta/amoeba/tests/operations"
  - "grep def resolve_scope|read_run_facts\\(|read_calls|calls_log_dir|squadron_runs_dir|list_runs\\(|def status\\(|def list_view\\(|def place_runs in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations"
sectionsInDocument: 19
sectionsCovered: 18
sectionsNotCovered:
  - "Context Summary"
effort: xhigh
turns: 90
promptTokens: 8377095
cachedTokens: 8063569
cacheWriteTokens: 313450
completionTokens: 186350
durationSeconds: 796.1
costUsd: 1.07933
costBasis: provider
runId: run-20261121-p5-01fb5c21
squadronVersion: 0.24.36
findings:
  - id: F001
    severity: concern
    category: test-plan
    summary: "Message-timing test pins 3/2/2/2 lookups and is not named"
    location: "tests/test_message_timing.py:118"
  - id: F002
    severity: concern
    category: test-plan
    summary: "`list members` / `list dependencies` cf-failure test is not named"
    location: "tests/cli/test_list_cli.py:201"
  - id: F003
    severity: concern
    category: test-plan
    summary: "Explicit-member cf-failure test in test_message_member.py is not covered"
    location: "tests/operations/test_message_member.py:160"
  - id: F004
    severity: concern
    category: test-plan
    summary: "`MemberRow` dict construction and exact render text in test_registry.py are not named"
    location: "tests/cli/render/test_registry.py:38"
  - id: F005
    severity: concern
    category: contract
    summary: "Existing test asserts `add --project … --wake-command` sets the command, which D7 refuses"
    location: "tests/cli/test_add_wake_command_cli.py:95"
  - id: F006
    severity: concern
    category: contract
    summary: "Unknown references have no specified problem code, and existing tests pin `NOT_A_PROJECT`"
    location: "tests/operations/test_set_up_validation.py:135"
  - id: F007
    severity: concern
    category: safety
    summary: "The update exit-code test would run a real `uv tool install`"
    location: "scripts/update_live.py:292"
  - id: F008
    severity: concern
    category: sequencing
    summary: "The commit at line 257 ships `add` request fields that are accepted and then ignored"
    location: "src/amoeba/operations/add.py:56"
  - id: F009
    severity: concern
    category: sequencing
    summary: "The commit at line 377 lands with `send` served before its wake refusal exists"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md"
  - id: F010
    severity: concern
    category: size
    summary: "Four files past 300 lines have a move the size rule requires but no task performs"
    location: "src/amoeba/operations/set_up_models.py"
  - id: F011
    severity: concern
    category: size
    summary: "Tasks 8.1 and 9.9 each bundle several concerns"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md"
  - id: F012
    severity: concern
    category: size
    summary: "Overall size: 65 numbered tasks in a 467-line file"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md"
  - id: F013
    severity: concern
    category: contract
    summary: "Checkouts-joins-members statement cannot go in `sql_checkouts.py`"
    location: "tests/store/test_members_queried_in_one_place.py:106"
  - id: F014
    severity: note
    category: docs
    summary: "Task 4.1 says `members.py` imports `ContextForgeError`; it defines it"
    location: "src/amoeba/operations/members.py:24"
  - id: F015
    severity: note
    category: code-detail
    summary: "Positional row mapper: new member columns must be appended"
    location: "src/amoeba/store/programs.py:44"
  - id: F016
    severity: note
    category: test-plan
    summary: "Task 5.4 does not say which `name_members` to monkeypatch"
    location: "src/amoeba/operations/state_move.py:117"
  - id: F017
    severity: note
    category: scope
    summary: "Task 7.7 changes `handle_pause`, which the design excludes"
    location: "src/amoeba/operations/handle_pause.py:132"
  - id: F018
    severity: note
    category: docs
    summary: "Naming the hub's `name_by_id` departs from design D2's text"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md"
  - id: F019
    severity: note
    category: docs
    summary: "Garbled bullet in 7.1"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md"
  - id: F020
    severity: pass
    category: code-match
    summary: "Wake claim surface matches task 8.1"
    location: "src/amoeba/store/wakes.py:146"
  - id: F021
    severity: pass
    category: code-match
    summary: "Raw member inserts after a full migrate are named"
    location: "tests/store/test_migrations.py:363"
  - id: F022
    severity: pass
    category: code-match
    summary: "Git allowlist and `_checkout_of` match tasks 3.2 and 4.3"
    location: "src/amoeba/upstream/git_read.py:32"
---

# Review: tasks — slice 261

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Message-timing test pins 3/2/2/2 lookups and is not named

Task 7.1 sets `MESSAGE_LOOKUPS` to 1 for each operation. `test_send_makes_three_lookups_and_the_others_two` (lines 118-125) asserts `{SEND: 3, INBOX: 2, REPLY: 2, CANCEL: 2}`, so it fails after 7.1. Task 7.2 (line 192) names only the `len(cf.calls) == MESSAGE_LOOKUPS[name]` assertion as unchanged. This test's dict assertion and its name need a named edit.

### [CONCERN] `list members` / `list dependencies` cf-failure test is not named

`test_a_failing_cf_exits_three` runs `list members` and `list dependencies` with a failing `cf` and expects exit 3. Design D5 and D11 make both cf-free, so after 11.1/11.2 this test fails. Neither task (lines 325-334) names it, and the preamble rule at line 50 does not cover `list` CLI tests. Name it for deletion, with a "`cf` stub that fails if called" test in its place.

### [CONCERN] Explicit-member cf-failure test in test_message_member.py is not covered

Line 50 names "its directory test moves to the placement, its recipient test is deleted". The test at lines 160-171 (`test_a_cf_failure_on_the_explicit_member_propagates`) is neither. After 7.1 an explicit `member` is a store read (`find_member`), so `resolve_caller` never calls `cf` and the test fails. Name it for deletion.

### [CONCERN] `MemberRow` dict construction and exact render text in test_registry.py are not named

`_member` builds `MemberRow` with `model_validate` from a dict without the `origin` and `checkouts` fields that 11.1 adds, so it raises. The file's header says it pins the registered views' text exactly, and 11.1 (line 329) changes the `list members` rendering. Neither 11.1 nor 11.2 (lines 331-334) names this file.

### [CONCERN] Existing test asserts `add --project … --wake-command` sets the command, which D7 refuses

`test_project_sets_it_from_another_directory` runs `add --project <name> --wake-command COMMAND` and asserts the member's command is set. Design D7 and task 9.9 (line 283) make that `malformed`. No task names this test (8.1, 9.9 and 9.10 at lines 230-289 do not).

### [CONCERN] Unknown references have no specified problem code, and existing tests pin `NOT_A_PROJECT`

Task 9.9 (line 282) makes each reference one `find_member` read, with no `cf` lookup. The code then cannot say "not a project", but the task never says what code an unknown `members.project`, `depends_on` provider or concept member gets; line 282 gives `not_a_member` only for `--file` entries. Three tests here pin `NOT_A_PROJECT` (lines 135-143 and 146-162). The design's Migration Plan (line 532) allows one kind of test edit, "a reference to a Context Forge project that is not a member now refers to a member", and changing the asserted code is not that. Decide the code (`not_a_member` is the consistent reading) and name the assertion changes.

### [CONCERN] The update exit-code test would run a real `uv tool install`

Task 16.2 (line 446) says to run `update_live.main` with "the names it uses to build the real steps" monkeypatched. `PRODUCTION` (lines 292-294) binds `_uv_install`, `_amoeba_list` and `_installed_tools` at import time, so patching those names does not change `PRODUCTION.install`. The test would run `uv tool install --force --reinstall` on the checkout and replace the user's installed tool. The task should say to patch `update_live.PRODUCTION`, or to pass the steps in, and to fail the test if real `uv` is reached.

### [CONCERN] The commit at line 257 ships `add` request fields that are accepted and then ignored

Task 9.1 (line 250) adds `name`, `attach_to` and `new_member` to the `add` request, and `checkout` to `rm`. The commit marker at line 257 falls after 9.2 and before 9.3 and 9.7 give those fields behaviour. Until then `add()` reads none of them, so `attach_to` runs as a plain `add`. That is a silent fallback, and the commit is not a working point. Move the field additions to 9.7, or have `add()` refuse them until they are built.

### [CONCERN] The commit at line 377 lands with `send` served before its wake refusal exists

Task 13.1 (line 361) adds `send` to `SERVED_OPERATIONS`. The commit at line 377 ("run nine more operations") follows 13.4 and precedes 13.5 (lines 379-381), which adds the `not_served` refusal that D9 requires. At that commit the door either serves `send` with no wake check, which is the outcome design D9 rejects, or errors, depending on how `run_served` treats a served name with no case. Either way the title and the content disagree. Move `send` into `SERVED_OPERATIONS` and `WRITING_CALLS` in 13.5, or move the commit marker after 13.5.

### [CONCERN] Four files past 300 lines have a move the size rule requires but no task performs

The Context Summary (line 42) says `store/models.py` (302), `operations/set_up_models.py` (290) and `operations/pause_context.py` (297) move "the new part to a module named for its concern and note it". No task does it: 2.2 changes `models.py`, 9.1 adds fields to `set_up_models.py`, and 7.7 adds a parameter to `pause_context.py`. Task 17.2 (line 460) checks only files "added or grew" and splits only new files. The same paragraph says `set_up.py`'s edits "replace or remove existing lines", but 2.3, 8.1 and 10.1 add lines to it (344 lines now). Name the task and target module for each move.

### [CONCERN] Tasks 8.1 and 9.9 each bundle several concerns

Task 8.1 (lines 230-236) covers the settings removal, SQL and mapper, null-out, engine wake path, `can_wake`/`claim_wake`, `Recipient`, two readers, and a dozen test files with named assertion changes. Task 9.9 (lines 281-286) covers reference resolution, the removal resolver, the bulk document, the wake command, `add()`'s signature, placement, and interim removal. Split 8.1 into (a) the store's wake scope and claim with `Recipient` and its readers, and (b) the settings removal, null-out and engine wake path. Split 9.9 into (a) reference resolution and the removal resolver, and (b) `add()`'s signature, placement, wake command and interim removal.

### [CONCERN] Overall size: 65 numbered tasks in a 467-line file

Section 9 alone has twelve subtasks (lines 247-301). Merges that keep each test with its implementation: 3.1 into 3.2 (the origin functions and their `git_read` call are one unit); 9.1 into 9.2, once the field additions move (see the commit finding above); 12.1 into 12.2. Drop the "tried once and noted" mutation check in 13.7 (line 390) and the "shown once and noted" check in 15.4 (line 427), since no success criterion names them.

### [CONCERN] Checkouts-joins-members statement cannot go in `sql_checkouts.py`

Task 16.1 (line 439) puts its two new statements in `store/sql.py` and `store/sql_checkouts.py` without saying which holds which. The scan test (lines 106-117) fails any string literal outside `sql.py` that matches `FROM|JOIN|INTO|UPDATE members`. "Every active member in cf_projects has a checkout" reads `members`, so it must go in `sql.py`. Say so.

### [NOTE] Task 4.1 says `members.py` imports `ContextForgeError`; it defines it

Line 128 says "(`members.py` imports it until deleted)". Line 24 is `class ContextForgeError(Exception)`, a definition. The move is still right, and the grep-derived importer list is still correct.

### [NOTE] Positional row mapper: new member columns must be appended

`_member` reads columns by index (`row[0]` to `row[9]`). Tasks 1.1 and 2.2 (lines 95-96) add `name` and `origin` to the members SELECT, and 8.1 removes `wake_command` (`row[9]`). Append `name` and `origin` at the end of `_MEMBER_COLUMNS`, or the indexes of `rules_from` and `wake_command` shift. Say so in 2.2.

### [NOTE] Task 5.4 does not say which `name_members` to monkeypatch

Line 163 says "With `name_members` monkeypatched to do nothing". Once 5.3 runs naming from `open_state_store` (state_move.py:117), the function is looked up in `state_move`'s namespace. Patching `amoeba.operations.naming.name_members` would not reach it. Name the target.

### [NOTE] Task 7.7 changes `handle_pause`, which the design excludes

The design's Excluded list (line 65) puts `handle_pause` in slice 262. D6 requires `PauseTarget.cf_project_id` (task 7.7, line 219), built at `handle_pause.py:132`, so the change is needed. Task 17.3 (line 464) should record it as a departure.

### [NOTE] Naming the hub's `name_by_id` departs from design D2's text

Design D2 (line 188) says the hub's `name_by_id` "is in that module" (`operations.naming`). D4 and the import rules say the hub may not import `naming`. Task 5.2 (line 153) and 13.7 (line 390) use a separate module, which is the right call. Task 17.3 does not list it; the generic clause covers "design text changed under the small-conflict rule", so name it there.

### [NOTE] Garbled bullet in 7.1

Line 189 reads "An existing test that seeds a member and then calls as it seeds its checkout with `insert_checkout` (...)". The sentence has no verb. The intended edit is probably: an existing test that seeds a member and then calls an operation seeds its checkout with `insert_checkout`. Rewrite it.

### [PASS] Wake claim surface matches task 8.1

`claim_wake` takes `directory` (line 152). `NO_CHECKOUT_DETAIL` is defined at line 38 and used in the null-directory branch (line 182). `tests/store/test_wakes.py` imports it (line 17) and has the named tests (lines 172, 190).

### [PASS] Raw member inserts after a full migrate are named

`test_a_closed_question_needs_a_known_reason` migrates to the latest version and then inserts a member with no name. Task 1.1 names this file for the name binding, so the 012 trigger will not break it unnoticed.

### [PASS] Git allowlist and `_checkout_of` match tasks 3.2 and 4.3

`GIT_SUBCOMMANDS` holds the three read commands, and the module docstring (lines 4-7) says "three read commands", as 3.2 describes. `GitReadResult.stderr_head` exists (line 46). `pause_eligibility._checkout_of` (line 125) is the function 4.3 replaces.

### Run Digest

- Response length: 25808 chars
- Response is newline-free: no
- Tool calls made: 89
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 90
- Tokens — prompt / cached / cache write / completion / reasoning: 8377095 / 8063569 / 313450 / 186350 / not computed
- Duration: 796.1 s
- Cost: $1.08 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 22
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 22
- Finding-shaped matches — surviving validation: 22

## Resolution

- [concern] Message-timing test pins 3/2/2/2: fixed. 7.2 names `test_send_makes_three_lookups_and_the_others_two`, which becomes `test_each_message_operation_makes_one_lookup` (1 each, `MESSAGE_STORE_WAITS` unchanged).
- [concern] `list members`/`list dependencies` cf-failure test: fixed. The Context Summary's cf-failure list puts `tests/cli/test_list_cli.py` `test_a_failing_cf_exits_three` under 11.1. 11.2 deletes it, and the four `list` subjects are tested with a `cf` stub that fails if called.
- [concern] Explicit-member cf-failure test in `test_message_member.py`: fixed. The 7.1 entry deletes `test_a_cf_failure_on_the_explicit_member_propagates`.
- [concern] `test_registry.py` `MemberRow` dict and exact text: fixed. 11.2 names the file: `_member` gains `origin` and `checkouts`, and the `list members` texts change to the new layout.
- [concern] `add --project … --wake-command` CLI test: fixed. The refusal lands in the new 8.2 (engine wake path), which names `test_project_sets_it_from_another_directory` → `test_project_with_a_wake_command_is_malformed`.
- [concern] Unknown references have no code: fixed. 9.8 makes an unknown reference `not_a_member` with its field path, names the two `test_set_up_validation.py` assertion changes, and 17.3 records the departure from the design's allowed edit.
- [concern] Update exit-code test would run real `uv`: fixed. 16.2 patches `update_live.PRODUCTION` (bound at import), `check_checkout` and `previous_commit`, and patches `_uv_install` to fail the test if called.
- [concern] Commit after 9.2 ships ignored request fields: fixed. The old 9.1 is gone: the problem codes go to 9.2 (`add_member`, which takes the new values as keyword arguments), the `add` request fields go to 9.9 where `add()` starts calling `add_member`, and `rm.checkout` goes to 10.1. The commit after 9.1 now holds only `gather_add`.
- [concern] Commit after 13.4 serves `send` without its wake refusal: fixed. 13.1 leaves `send` out of `SERVED_OPERATIONS` and `WRITING_CALLS`, and 13.5 adds it there together with its case and the refusal.
- [concern] Four files past 300 lines with a move no task performs: fixed by removing the promise. The size note now says what each file gains (two `Member` fields, the request fields, one parameter), which cannot move out of the class or function it extends, so each is left a few lines past 300 and noted. `set_up.py` ends no longer than 344 lines: interim lines are removed in 9.9, the checkout write replaces `_merged_wake_command`, and 10.1's delete goes in `set_up_remove.py`. 17.2 checks both.
- [concern] 8.1 and 9.9 bundle concerns: fixed. 8.1 is now the claim, `Recipient` and readers with the seed edits; 8.2 is the settings removal, null-out and engine; old 8.2 is 8.3. 9.8 is now the references and removal resolver; 9.9 is `add()`'s signature, request fields, placement, bulk document, wake command and interim removal.
- [concern] Overall size: fixed. The origin rule and its `git_read` call merged into 3.1 (tests are 3.2), old 9.1 dissolved, 12.1 merged with 12.2, and the "tried once" (13.7) and "shown once" (15.4) checks dropped. With the two splits there are 64 tasks.
- [concern] Checkouts-joins-members statement: fixed. 16.1 puts both statements in `store/sql.py`, because both read `members`.
- [note] 4.1 says `members.py` imports `ContextForgeError`: fixed. It now says `members.py` defines it today and imports it from `errors.py` until 10.3 deletes the module.
- [note] Positional row mapper: fixed. 2.2 appends `name` and `origin` at the end of `_MEMBER_COLUMNS`; 8.2 says their indexes move down by one when `wake_command` leaves.
- [note] 5.4 monkeypatch target: fixed. It names `amoeba.operations.state_move.name_members`.
- [note] 7.7 changes `handle_pause`: fixed. 17.3 records it as a departure from the Excluded list.
- [note] `name_by_id` departs from D2's text: fixed. 17.3 names it.
- [note] Garbled 7.1 bullet: fixed. It is rewritten.
- [pass] Wake claim surface matches 8.1: no change (8.1's claim part is unchanged by the split).
- [pass] Raw member inserts after a full migrate are named: no change.
- [pass] Git allowlist and `_checkout_of` match 3.2 and 4.3: no change (the `git_read` part is now in 3.1).
