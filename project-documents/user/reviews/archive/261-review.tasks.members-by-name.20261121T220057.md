---
docType: review
layer: project
reviewType: tasks
slice: members-by-name
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS (reviewer stated FAIL; both FAIL findings and every concern resolved in the task file after this review, apart from two size cuts judged cosmetic)
verdictSource: stated
sourceDocument: project-documents/user/tasks/261-tasks.members-by-name.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261121
dateUpdated: 20261121
reviewedSha: 7d0264a56c5e06ddaa3292bf94bd74a3ff4b9b38
reviewedBlob: 9ab1147b676f3c6646bb11791152e33d15d8a48d
reviewedBlobCurrent: false
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 65
injected:
  - key: input
    path: "project-documents/user/tasks/261-tasks.members-by-name.md"
    chars: 68124
    sha256: d0f680211db6228fe18662ddb766e2100f8961d132b9cc5b32c9162840828d26
    whole: true
  - key: against
    path: "project-documents/user/slices/261-slice.members-by-name.md"
    chars: 83403
    sha256: fef09424df79bfbcafc738e099fcbdcda3fc04e423ea147ccd6dac6d07e8aea7
    whole: true
  - key: conventions
    path: "AGENTS.md"
    chars: 23952
    sha256: 9b993051f9050d1c957047099dab80641d2fc9a22a808766fe481968eaee78ce
    whole: true
filesRead:
  - "src/amoeba/upstream/context_forge/project_of.py"
  - "src/amoeba/upstream/git_read.py"
  - "src/amoeba/operations/deps.py"
  - "src/amoeba/store/wakes.py"
  - "src/amoeba/operations/message_member.py"
  - "tests/test_message_timing.py"
  - "src/amoeba/operations/list_registry.py"
  - "tests/operations/test_send.py"
  - "tests/operations/test_changes.py"
  - "tests/operations/test_decisions.py"
  - "scripts/update_live.py"
  - "src/amoeba/operations/set_up.py"
  - "src/amoeba/operations/pause_eligibility.py"
  - "src/amoeba/store/programs.py"
  - "src/amoeba/store/sql.py"
  - "tests/store/test_members_queried_in_one_place.py"
  - "tests/store/test_schema.py"
  - "src/amoeba/operations/status_placement.py"
  - "tests/operations/test_rm.py"
  - "tests/operations/test_status_scope.py"
  - "tests/operations/test_message_member.py"
  - "tests/scripts/test_update_live.py"
searches:
  - "list_files src/amoeba/store/schema/*.sql in ."
  - "list_files src/amoeba/operations/{members,member_reference,project_lookup,set_up,set_up_resolve,set_up_remove_resolve,set_up_models,deps,add,add_door,rm,standing,pause_eligibility,pause_context,program_sources,status_placement,status_runs,list_view,list_registry,changes_models,message_member,wake,served,errors\u2026 in ."
  - "list_files {src/amoeba/upstream/context_forge/project_of.py,src/amoeba/upstream/context_forge/projects.py,src/amoeba/upstream/git_read.py,scripts/update_live.py,tests/scripts/test_update_live.py,tests/store/test_members_queried_in_one_place.py,tests/test_message_timing.py,tests/cli/test_requests_scenario.py,te\u2026 in ."
  - "grep ContextForgeError|NotInProgram|NotAProject in /Users/manta/source/repos/manta/amoeba"
  - "grep def (open_state_store|open_hub_store|project_of|project_details|project_names|git_read|resolve_member|resolve_caller|resolve_actor|resolve_recipient|resolve_release_member|checkout_of|_checkout_of|gather|can_wake|claim_wake|upsert_member|_write_member|_merged_wake_command|read_target|resolve_slice|_\u2026 in /Users/manta/source/repos/manta/amoeba/src"
  - "grep project_names|project_of\\(|project_details|cli_call|reference= in /Users/manta/source/repos/manta/amoeba/src"
  - "grep ^(INSERT_MEMBER|_MEMBER_INSERT_COLUMNS|_MEMBER_COLUMNS|UPDATE_MEMBER|REREGISTER_MEMBER|ACTIVE_MEMBER|ACTIVE_READS|OTHER_MEMBER_STATEMENTS|EXPECTED_SCHEMA_VERSION)\\b|wake_command|checkout in /Users/manta/source/repos/manta/amoeba/src/amoeba/store"
  - "grep ACTIVE_READS|OTHER_MEMBER_STATEMENTS|ACTIVE_MEMBER|def test_|members in /Users/manta/source/repos/manta/amoeba/tests/store/test_members_queried_in_one_place.py"
  - "grep EXPECTED_SCHEMA_VERSION|== 11|== 10|== 9\\b|schema_version|COLUMN_REASONS|table count|len\\(.*tables|expected_tables in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep ^class (Recipient|MemberSettings|Member|MemberState|MemberRow|MemberRef|MemberName|SetUpProblemCode|Eligible|PauseTarget|ResolvedMember|ProjectDetails|StandingRequest|StatusRequest|SetUpResult|WorkingDirectory\\w*|MemberReference|Reference|Refusal)\\b|^class SetUpProblemCode|^    NOT_A_MEMBER|not_a_me\u2026 in /Users/manta/source/repos/manta/amoeba/src"
  - "grep claim_wake\\(|NO_CHECKOUT_DETAIL|known_to_cf|start_failed|UPDATE members SET wake_command|insert_member\\([^)]*wake_command in /Users/manta/source/repos/manta/amoeba"
  - "grep MESSAGE_LOOKUPS|worst_case_seconds|105 s|75 s|105 seconds|75 seconds|lookup in /Users/manta/source/repos/manta/amoeba"
  - "grep MESSAGE_LOOKUPS|worst_case_seconds|member_mismatch|MEMBER_MISMATCH in /Users/manta/source/repos/manta/amoeba"
  - "grep def test_a_cf_failure_exits_three_with_nothing_written|def test_a_cf_failure_raises_and_writes_nothing|in_context_forge|def test_.*key|\"wake_command\"|\"in_context_forge\"|keys\\(\\) in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep . in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/sql.py"
  - "grep ^from amoeba\\.operations\\.state_move import|import amoeba\\.operations\\.state_move|open_state_store in /Users/manta/source/repos/manta/amoeba"
  - "list_files src/amoeba/{hub,wire}/**/*.py in ."
  - "grep ^(from|import) |^def _dispatch|^def |project_names in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/state_move.py"
  - "grep ^def |^class |^[A-Z_]+ *(:|=)|installed-commit|previous|CalledProcessError|exist_ok|\\.migrate\\(|cf list|list projects|check_store|def _migrate|def migrate in /Users/manta/source/repos/manta/amoeba/scripts/update_live.py"
  - "grep class FakeSteps|def _migrate|def __init__|def migrate|def (list|check|read_back|install)|naming|cf_projects|exist_ok|def test_ in /Users/manta/source/repos/manta/amoeba/tests/scripts/test_update_live.py"
  - "grep _project_names|project_names|def _ in /Users/manta/source/repos/manta/amoeba/src/amoeba/cli/commands.py"
  - "list_files {src/amoeba/cli/registration_arguments.py,src/amoeba/cli/render/registration.py,src/amoeba/cli/render/registry.py,src/amoeba/mcp/tools.py,src/amoeba/mcp/message_tools.py,src/amoeba/wiring.py,src/amoeba/wiring_registry.py,src/amoeba/wiring_messages.py,src/amoeba/wiring_releases.py,src/amoeba/wiring_p\u2026 in ."
  - "grep _Lookups|def insert_member|wake_command|def upsert_member|name: str|class ResolvedMember|class Member\\b|class MemberSettings|def _member\\b in /Users/manta/source/repos/manta/amoeba"
  - "grep def acting|def act_as|class ActingMachine|LOCAL_MACHINE|def act_as_local|def get_member\\b|def get_member_any|def members_of|def active_member|def list_members|def checkout|def set_member|def member_by|def removed in /Users/manta/source/repos/manta/amoeba/src/amoeba/store"
  - "grep \\b(eleven|eleven tables|twelve|11 tables|TABLES|tables ==|len\\(TABLES|table_count|== 1[0-9]\\b)|INSERT INTO members|Member\\(\\s*$|Member\\(project_id|Member\\( in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep table in /Users/manta/source/repos/manta/amoeba/tests/test_contract_docs.py"
  - "grep pytest|addopts|testpaths|marker|ignore|live|load in /Users/manta/source/repos/manta/amoeba"
  - "grep member_reference|project_lookup|operations\\.members\\b|operations import members|from amoeba\\.operations\\.members in /Users/manta/source/repos/manta/amoeba"
  - "grep project_names|git_run|Deps\\( in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep state_move|_handle_polled|class PauseTarget|result_from_document|def pause_claim|def handle_pause in /Users/manta/source/repos/manta/amoeba/src"
  - "grep CF_PROJECTS_TIMEOUT_SECONDS|def read_run_facts|def run_file_exists|run_file_exists|def read_calls_log|calls_log|def can_wake|can_wake\\(|def list_runs|def poll_run|class FrozenModel|CALL_BOUND_SECONDS in /Users/manta/source/repos/manta/amoeba/src"
  - "grep ^(def |class )|FORBIDDEN|ONLY_ALLOWED in /Users/manta/source/repos/manta/amoeba/tests/test_import_boundaries.py"
  - "grep pytest\\.raises\\(ContextForgeError|ContextForgeError\\)|raises\\(ContextForgeError|error: ContextForgeError|ContextForgeError\\\"|exits? (3|three) in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep directory=|changes\\(|report_release\\(|list_view|resolve_scope\\(|\\brm\\(|status\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep working_directory\\b in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep working_directory ==|working_directory is|\\.working_directory\\b.*(Member|NotInProgram|NotAProject)|WorkingDirectoryMember\\( in /Users/manta/source/repos/manta/amoeba/tests/operations"
  - "grep autouse|AMOEBA_HOME in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep from amoeba\\.operations\\.(add|rm) import|operations\\.add import|operations\\.rm import|from amoeba\\.operations import (add|rm)\\b in /Users/manta/source/repos/manta/amoeba/src"
  - "grep wake_command|claim_wake|worst_case|MESSAGE_LOOKUPS|project_of|ContextForgeError|resolve_ in /Users/manta/source/repos/manta/amoeba/tests/load"
  - "grep project_of|monkeypatch in /Users/manta/source/repos/manta/amoeba/tests/cli/test_standing_cli.py"
sectionsInDocument: 19
sectionsCovered: 19
effort: xhigh
turns: 66
promptTokens: 6403701
cachedTokens: 6119121
cacheWriteTokens: 284518
completionTokens: 182979
durationSeconds: 771.1
costUsd: 0.893579
costBasis: provider
runId: run-20261121-p5-01fb5c21
squadronVersion: 0.24.36
findings:
  - id: F001
    severity: fail
    category: test-plan
    summary: "Existing tests whose `cf`-failure assertions the plan removes are not named"
    location: "tests/operations/test_send.py:429"
  - id: F002
    severity: fail
    category: sequencing
    summary: "Commits at 216 and 312 leave CLI call sites calling changed signatures"
    location: "src/amoeba/wiring_releases.py:38"
  - id: F003
    severity: concern
    category: sequencing
    summary: "9.10 asserts a rule that 11.1 introduces two commits later"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:279"
  - id: F004
    severity: concern
    category: existing-code
    summary: "The table-count pin is in the wrong file and missing from the edit list"
    location: "tests/store/test_schema.py:96"
  - id: F005
    severity: concern
    category: scope
    summary: "8.1 does not address `claim_wake`'s `directory` parameter or its `start_failed` branch"
    location: "src/amoeba/store/wakes.py:146"
  - id: F006
    severity: concern
    category: test-plan
    summary: "The list of raw wake-command seeds in 8.1 is incomplete"
    location: "tests/store/test_message_sweep.py:276"
  - id: F007
    severity: concern
    category: sequencing
    summary: "The precondition for deleting `Deps.project_names` is false until 10.3"
    location: "src/amoeba/cli/commands.py:41"
  - id: F008
    severity: concern
    category: spec-gap
    summary: "Step 5 does not say which refusal an id-equal name gets"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:262"
  - id: F009
    severity: concern
    category: spec-gap
    summary: "`--name` is not checked against the name pattern"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:265"
  - id: F010
    severity: concern
    category: proportionality
    summary: "The file is overweight for one slice"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md"
  - id: F011
    severity: concern
    category: test-coverage
    summary: "The design's \"exits 1\" criterion has no test"
    location: "scripts/update_live.py:315"
  - id: F012
    severity: note
    category: dependency
    summary: "260 is not built, so 0.1 stops the slice, as it should"
    location: "src/amoeba/store/migrations.py:25"
  - id: F013
    severity: note
    category: architecture
    summary: "Naming's import in `state_move.py` may reach the hub's import graph"
    location: "src/amoeba/operations/state_move.py:117"
  - id: F014
    severity: note
    category: store
    summary: "Re-registering a removed member keeps its stored name"
    location: "src/amoeba/store/programs.py:201"
  - id: F015
    severity: note
    category: behavior
    summary: "The member-mismatch and unknown-actor rules are not stated as kept"
    location: "src/amoeba/operations/message_member.py:77"
  - id: F016
    severity: note
    category: structure
    summary: "The placement rule for 13.6–13.8 sits outside any task"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:370"
  - id: F017
    severity: note
    category: sequencing
    summary: "12.3 refers to \"the edges\" before 13.3 defines them"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:342"
  - id: F018
    severity: note
    category: commit
    summary: "The commit at 216 is typed `refactor` but changes behavior"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:216"
  - id: F019
    severity: note
    category: test-coverage
    summary: "`test_message_timing.py`'s comments describe `add`, `rm`, `status` and `list` as unbounded"
    location: "tests/test_message_timing.py:51"
  - id: F020
    severity: note
    category: existing-code
    summary: "One existing load test seeds a parameter that 8.1 removes"
    location: "tests/load/test_wake_claim_load.py:85"
  - id: F021
    severity: pass
    category: ci
    summary: "CI gates the load tier"
    location: ".github/workflows/ci.yml:40"
  - id: F022
    severity: pass
    category: nfr
    summary: "The load NFR has a task"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:421"
  - id: F023
    severity: pass
    category: commits
    summary: "Commit markers sit at working points"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:103"
  - id: F024
    severity: pass
    category: sequencing
    summary: "Dependency order has no cycles, and tests follow their implementation"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:66"
  - id: F025
    severity: pass
    category: coverage
    summary: "Success criteria map to tasks"
    location: "project-documents/user/slices/261-slice.members-by-name.md:553"
---

# Review: tasks — slice 261

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Existing tests whose `cf`-failure assertions the plan removes are not named

Line 49 says an existing test's assertion may change only if its task names it, and otherwise the code is fixed. Only the two standing tests are named (7.4, line 197). The plan removes the `cf` call from these operations, so these tests fail as written:
- `test_send.py:429` (7.1), `test_reply.py:310` and `test_cancel.py:270` (7.1)
- `test_message_member.py:156,170,207` (7.1)
- `test_changes.py:286,291` and `test_report_release.py:304` (7.3)
- `test_decisions.py:270,279` (7.4)
- `test_status.py:237,251`, `test_status_scope.py:105` and `test_status_sweep.py:252` (7.5, 12.3)
- `test_rm.py:292` (10.1)
- `test_add.py:210` and `test_set_up_validation.py:181` (9.9)
- `test_list_registry.py:282` (11.1)

I read the first six in context. The rest are the same `pytest.raises(ContextForgeError)` shape in the named test files. Separately, `test_message_member.py:157,171` call `resolve_caller` with the signature that 7.1 (line 185) changes, and only `test_resolve_recipient.py` is named there. Each test needs to be named with the task that changes it and what its assertion becomes.

### [FAIL] Commits at 216 and 312 leave CLI call sites calling changed signatures

`wiring_releases.py:38-40` calls `report_release(..., directory=...)` and `changes(..., directory=...)`. `wiring_registry.py:35` calls `rm(..., directory=...)` and `wiring_registry.py:45` calls `list_view(..., directory=...)`. `wiring.py:216-220` calls `status(..., directory=...)`. Tasks 7.3 (line 193), 7.5 (lines 201–204) and 10.1 (line 297) change those operations to take `here`, but none names its call site. The section 7 intro (line 182) says each `wiring*` placement "runs the client part first", but no task updates these sites until 12.3 (status) and 13.6–13.8 (rm, list, changes, report_release). The commits at 216, 312, 327 and 346 therefore leave the CLI paths for those commands broken, and the CLI test modules for rm and release exercise them. Task 9.9 (line 276) has the same gap: it makes `add` stop calling `project_of` without saying what `add()` takes instead, and `wiring_registry.py:28` calls it with `directory`. Each task that changes an entry point should update its call site in the same commit.

### [CONCERN] 9.10 asserts a rule that 11.1 introduces two commits later

9.10 (line 279) requires `working_directory` to be null for `add --project` and an all-named bulk file. The null rule is in 11.1 (line 317), which lands in the commit at 327, after the 9.9–9.12 commit at 292. Nothing in 9.9 (lines 273–277) sets it, so the commit at 292 fails its own checks. Move the rule into 9.9 or move the assertion to 11.2.

### [CONCERN] The table-count pin is in the wrong file and missing from the edit list

Line 71 names "`tests/test_contract_docs.py`'s table count" as a pin that 1.1 updates. `test_contract_docs.py` has no table count; it checks that each table and column is named in the docs. The pin that adding `checkouts` breaks is `tests/store/test_schema.py:24-39`, a 14-name `TABLES` set, asserted at line 96 by `test_a_new_store_has_all_thirteen_tables` (line 86). Name that file in 1.1, or the 1.1 checks fail.

### [CONCERN] 8.1 does not address `claim_wake`'s `directory` parameter or its `start_failed` branch

8.1 (line 226) says the claim reads the checkout and that with none there is "no wake". The code still takes `directory` and `log_stem` from callers. When `directory` is null it inserts a `start_failed` row with `NO_CHECKOUT_DETAIL` (`wakes.py:37-41, 157-182`). The task does not say to remove the parameter or the branch. It also does not name `tests/store/test_wakes.py:190-199`, which asserts that branch and imports the constant at line 17. Callers that pass `directory` are `wake.py:118`, `tests/store/wake_support.py:54`, `tests/operations/wake_run_support.py:103` and `tests/operations/test_message_sweep_wrapper.py:174`. None is named. 8.1 (line 225) also has the engine set the checkout's command, but does not say the checkout must already exist. For a new member it comes from the 2.3 interim insert in `_write_member`, so the order inside the transaction matters.

### [CONCERN] The list of raw wake-command seeds in 8.1 is incomplete

Line 228 lists the raw `UPDATE members SET wake_command` seeds as `test_wake_status.py`, `wake_send_support.py` and `test_wakes.py` (two places). `tests/store/test_message_sweep.py:276` and `tests/operations/test_message_sweep_wrapper.py:171` set the same column and then claim a wake. After 8.1 the claim reads checkouts, so both fail unless edited. The general rule at line 49 may cover them, but the list reads as complete.

### [CONCERN] The precondition for deleting `Deps.project_names` is false until 10.3

Line 207 says to delete `Deps.project_names` once `grep -rn "project_names" src` shows only `upstream`. `cli/commands.py:41` imports `projects.project_names`, line 219 calls it in `_project_names`, and line 205 calls that from `_text_of`. Task 10.3 (line 308) removes it, so the grep still matches in `src` at 7.6. Correct the condition (the CLI calls `projects` directly, not through `Deps`) or move the `_project_names` removal into 7.6.

### [CONCERN] Step 5 does not say which refusal an id-equal name gets

Line 259 defines a name as "taken" if an active member holds it or it equals another member's id. Step 5 on the same line refuses a taken name as `name_taken` when the checkout has an `origin`, and as `no_origin` when it has none. So under 9.5's wording, a checkout with no `origin` whose Context Forge name equals another member's id gets `no_origin`. 9.6 (line 262) expects `name_taken` for that case and does not state the origin. D1 (design line 172) says `add` refuses an id-equal name as `name_taken`, and D7 step 5 covers only a name held by an active member. Settle the refusal for the id case and write it into step 5 and 9.6.

### [CONCERN] `--name` is not checked against the name pattern

D1 (design lines 168–174) says a name matches `[A-Za-z0-9][A-Za-z0-9._-]*` and is at most 64 characters. 9.7 (line 265) checks `--name` only against taken names and ids, so `--name "a b"` or `--name x:y` would be stored. Add that a `--name` failing `is_member_name` is `malformed`, with a test in 9.8.

### [CONCERN] The file is overweight for one slice

The file has 460 lines, 18 numbered sections (0–17), 67 tasks and 18 commit markers. Cuts that keep every criterion:
- Merge 13.6–13.8 into one "client placements" task. They share a shape: a round-trip test and a failing-`cf` test.
- Fold 3.2 (three lines) into 3.1.
- Section 9's 9.3, 9.5 and 9.7 each restate the five-step rules. Keep the rule text once, in 9.5, and refer to it from the others.
- The interim code in 1.1, 2.3 and 8.1 is removed by 9.9. It is needed to keep each commit green. Say in 9.9 that it is the only removal.

### [CONCERN] The design's "exits 1" criterion has no test

The functional requirement at design line 584 says that with a failing `cf`, `update` restores and "exits 1". `main` turns `UpdateError` into exit 1 (`update_live.py:315-317`). 16.2 (line 439) calls `update_live.update` directly and says never `main`. No task checks the exit code. Add a test that calls `main` with `PRODUCTION` and `check_checkout` monkeypatched, which avoids `uv`, and asserts return 1 and the stderr line.

### [NOTE] 260 is not built, so 0.1 stops the slice, as it should

`EXPECTED_SCHEMA_VERSION` is 10. Absent: `store/schema/011_hub_and_door.sql`, `operations/errors.py`, `operations/served.py`, `hub/`, `wire/`, `tests/hub_fixture.py`, `tests/store_open.py` and `tests/load/test_door_load.py`. Task 0.1 (line 57) says so and correctly writes BLOCKED. I checked the 260-independent claims against code. Tasks 4.1, 7.4 (`id_names`), 13.x, 14.1 and 15.x depend on 260's files and are checked against the design only.

### [NOTE] Naming's import in `state_move.py` may reach the hub's import graph

`open_state_store` is in `state_move.py`, which `wiring.py:42` imports. Task 5.3 (line 154) puts `name_members` in it, so importing the opener now reaches `operations.naming`, `here` and `upstream`. 13.9 (line 385) requires the hub to reach none of those. The plan does not say where 260's `open_hub_store` lives or that the hub must not import `state_move`. Name the module that keeps the naming call in 5.3, and have 13.9 check it.

### [NOTE] Re-registering a removed member keeps its stored name

`upsert_member` re-registers a removed member through `REREGISTER_MEMBER` (`programs.py:201-216`, `sql.py:117`), which keeps the stored name. 1.1 (line 73) says only the insert binds `name` and an update keeps it. A removed member whose name an active member now holds would violate the unique index. 9.5 step 3 (line 259) covers this in the final flow. The interim `_write_member` path (until 9.9) does not. Say what re-registration binds.

### [NOTE] The member-mismatch and unknown-actor rules are not stated as kept

`resolve_caller` applies `member_mismatch` (line 95), and `resolve_actor` returns `UnknownActor` for a no-member `cancel` (lines 122–127). Existing tests pin both: `test_send.py:348`, `test_reply.py:258`, `test_cancel.py:226`, `test_inbox.py:278` and `test_message_member.py:80,148`. Section 7.1 (lines 184–188) does not mention them. They must stay, and one sentence in 7.1 would say so.

### [NOTE] The placement rule for 13.6–13.8 sits outside any task

Line 370 is a plain paragraph directly after 13.5's Success item (line 369) with no blank line, so it renders as part of that item. It holds the placement rule for 13.6–13.8. D12's "a `CallRefused` raised with no client file is a bug and is not caught" (design line 420) is in no task. Move the rule under 13.6 and add the not-caught rule to 13.5.

### [NOTE] 12.3 refers to "the edges" before 13.3 defines them

12.3 gates the sweep, pruning and `start_after` on "the edges allow". The `ServedEdges` fields are defined in 13.3 (line 359), two commits later. State the no-client-file case in 12.3 and leave the edges to 13.3.

### [NOTE] The commit at 216 is typed `refactor` but changes behavior

AGENTS.md defines `refactor` as restructuring without behavior change. Section 7 changes behavior: the pause path passes checkout ids, and operations find members in the store. Use `feat:`. The section also has the CLI breakage in the FAIL above.

### [NOTE] `test_message_timing.py`'s comments describe `add`, `rm`, `status` and `list` as unbounded

The docstring (lines 7–11) and `UNBOUNDED_START_OPERATIONS` (lines 51–55) say those four make a per-member or per-directory count of `cf` calls that no constant bounds. After this slice each makes a fixed number of gathers. 7.2 (line 190) updates only the message counts. Update the docstring and the set in 7.2 or 12.3.

### [NOTE] One existing load test seeds a parameter that 8.1 removes

D15 says the existing `tests/load/` tests run unchanged. `test_wake_claim_load.py:85` seeds `wake_command=COMMAND` through `insert_member`, and 8.1 removes that parameter. The general rule at 8.1 line 228 covers it, so the task is right and the design's claim is not. Name the file in 8.1.

### [PASS] CI gates the load tier

The Tests step is a bare `uv run pytest`, and `pyproject.toml:64` ignores only `tests/live`, so `tests/load` runs in CI. Task 15.4 (lines 421–422) confirms this and says what to add if it changes. The gate is explicit.

### [PASS] The load NFR has a task

The design's D15 bounds (2 seconds with 16 clients; median under 200 ms over 100 idle calls) are carried by 15.4 in `tests/load/test_door_load.py`, which 260 creates. The task adds `send` and `inbox` callers and keeps both bounds.

### [PASS] Commit markers sit at working points

There are 18 plain `**Commit**:` lines at group ends (103, 121, 141, 165, 178, 216, 237, 249, 271, 292, 312, 327, 346, 388, 397, 426, 443, 460), none after every task. Two need changes for the reasons above: 216 (FAIL and NOTE) and 292 (CONCERN on 9.10).

### [PASS] Dependency order has no cycles, and tests follow their implementation

The order holds: 4.3 (`ORIGIN_READ_TIMEOUT_SECONDS`) comes before 5.1; 6.1 before 7; 12.2 before 12.3; 13 near the end. Tests sit with or right after their code (1.2, 2.x, 3.3, 4.2–4.3, 5.4, 6.2, 7.2, 8.2, 9.4, 9.6, 9.8, 10.2, 11.2, 12.1, 14.1, 15.3, 16.2). The exceptions are the commit-point problems above.

### [PASS] Success criteria map to tasks

I mapped each functional requirement (lines 553–584) and technical requirement (586–593) to a task, and each has one. The one that lacks a test is the "exits 1" check (CONCERN above).

### Run Digest

- Response length: 30932 chars
- Response is newline-free: no
- Tool calls made: 65
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 66
- Tokens — prompt / cached / cache write / completion / reasoning: 6403701 / 6119121 / 284518 / 182979 / not computed
- Duration: 771.1 s
- Cost: $0.89 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 25
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 25
- Finding-shaped matches — surviving validation: 25
