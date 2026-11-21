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
reviewedSha: f84b513c308e6d7d07401f101c2c6ff8a81c43e3
reviewedBlob: cabb78873e96718021c7b10163d02fddfb6c8308
reviewedBlobCurrent: true
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 82
injected:
  - key: input
    path: "project-documents/user/tasks/261-tasks.members-by-name.md"
    chars: 59218
    sha256: 91bf033bef400033c08bb310fc75f90252a8c6beb077a6199bed5c2af82b1bed
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
  - "src/amoeba/operations/members.py"
  - "src/amoeba/operations/set_up_resolve.py"
  - "src/amoeba/operations/member_reference.py"
  - "src/amoeba/upstream/context_forge/project_of.py"
  - "src/amoeba/upstream/context_forge/projects.py"
  - "src/amoeba/operations/pause_context.py"
  - "src/amoeba/operations/pause_eligibility.py"
  - "tests/store/test_members_queried_in_one_place.py"
  - "src/amoeba/store/programs.py"
  - "src/amoeba/store/sql.py"
  - "tests/store/test_schema_holds_no_mirrored_state.py"
  - "src/amoeba/operations/set_up.py"
  - "src/amoeba/operations/state_move.py"
  - "scripts/update_live.py"
  - "src/amoeba/operations/standing.py"
  - "tests/operations/test_standing.py"
  - "tests/test_import_boundaries.py"
  - "tests/upstream/test_git_read.py"
  - "tests/store/seed.py"
  - "tests/operations/test_resolve_recipient.py"
  - "src/amoeba/upstream/git_read.py"
  - "src/amoeba/store/migrations.py"
  - "src/amoeba/wiring_messages.py"
  - "tests/test_message_timing.py"
  - "tests/scripts/test_update_live.py"
  - "tests/operations/test_list_registry.py"
  - "src/amoeba/operations/set_up_models.py"
searches:
  - "list_files src/amoeba/{operations/members.py,operations/member_reference.py,operations/project_lookup.py,operations/errors.py,operations/caller.py,operations/deps.py,operations/set_up.py,operations/set_up_resolve.py,operations/set_up_remove_resolve.py,operations/set_up_models.py,operations/pause_context.py,ope\u2026 in /Users/manta/source/repos/manta/amoeba"
  - "list_files {tests/store/schema_11.py,tests/store/seed.py,tests/store_open.py,tests/cf_stub.py,tests/git_repo.py,tests/user_configs.py,tests/fault_injection.py,tests/hub_fixture.py,tests/hub/in_process_hub.py,tests/load/test_door_load.py,tests/load/test_no_cf_under_write_lock.py,tests/test_message_timing.py,tes\u2026 in /Users/manta/source/repos/manta/amoeba"
  - "list_files {docs/store-contract.md,docs/cli-contract.md,docs/mcp-server.md,docs/program-rules.md,docs/rules.md,.github/workflows/*.yml,pyproject.toml,src/amoeba/mcp/message_tools.py,src/amoeba/wiring_messages.py,src/amoeba/wiring_door.py,src/amoeba/wiring_results.py,src/amoeba/wiring_registry.py} in /Users/manta/source/repos/manta/amoeba"
  - "list_files {scripts/*.py,src/amoeba/hub/*.py,src/amoeba/wire/*.py,tests/hub/*.py,tests/load/*.py,tests/live/**/*.py,src/amoeba/store/schema/*.sql} in /Users/manta/source/repos/manta/amoeba"
  - "grep EXPECTED_SCHEMA_VERSION\\s*= in /Users/manta/source/repos/manta/amoeba"
  - "grep pytest|tests/load|tests/live|markers|addopts|testpaths in /Users/manta/source/repos/manta/amoeba"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep project_names|project_details|project_of\\(|reference= in /Users/manta/source/repos/manta/amoeba/src"
  - "grep operations\\.members|operations\\.member_reference|operations\\.project_lookup|from amoeba\\.operations import members|member_reference|project_lookup|ContextForgeError|NotInProgram|NotAProject in /Users/manta/source/repos/manta/amoeba"
  - "grep ProjectOf|cli_call|project_of|_checkout_of|CF_PROJECT_FLAG|-p|PauseTarget|cf_project|read_target|def gather|def resolve_slice|def _read_committed|def pause_claim|def _handle_polled|def _resolve_concept|concept in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep resolve_slice\\(|gather\\(|_read_committed\\(|project_id in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep MESSAGE_LOOKUPS|resolve_caller|resolve_actor|resolve_recipient|project_path|wake_command|class Recipient|def can_wake|def claim_wake|worst_case|105|75 s|75 seconds|105 seconds in /Users/manta/source/repos/manta/amoeba"
  - "grep members|MEMBER|upsert_member|wake_command in /Users/manta/source/repos/manta/amoeba/src/amoeba/store"
  - "grep INSERT INTO members|upsert_member\\(|insert_member\\(|Member\\(|MemberSettings\\(|wake_command=|MemberRow\\(|MemberState\\(|settings\\.wake_command in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep INSERT INTO members|upsert_member\\(|Member\\(\\s*$|[^a-zA-Z_]Member\\(|wake_command in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep wake_command in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep (^|[^A-Za-z_.])Member\\(|RowMember|MemberRow\\(|MemberState\\(|MemberRef\\(|MemberName\\( in /Users/manta/source/repos/manta/amoeba"
  - "grep def |_write_member|upsert_member|wake|project_names|cf|working|ResolvedMember|resolve_request|NOT_A_PROJECT|MALFORMED|class  in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/set_up.py"
  - "grep refuse_door_fields|add_door|def add\\(|def rm\\(|Door\\b|class Door|def remove|find_member|resolve_removal|known_to_cf|_Lookups|project_names|deps\\.|cf_run|git_run in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep resolve_member\\b|resolve_scope|resolve_release_member|project_or_rejection|anchor\\(|Anchor\\b in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep ^def |list_registry|list_members|project_details|names\\b|deps\\. in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/list_view.py"
  - "grep ^def |project_details|cf_run|run\\b|def list_members|def list_programs|def list_dependencies|def list_standing in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/list_registry.py"
  - "grep GIT_SUBCOMMANDS|def git_read|SUBCOMMAND|ValueError|allow|def _args|class |def  in /Users/manta/source/repos/manta/amoeba/src/amoeba/upstream/git_read.py"
  - "grep Deps\\(|project_names=|cf_run= in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep def open_state_store|def open_hub_store|act_as_local|def open_|LOCAL_MACHINE|name_members|name_by_id in /Users/manta/source/repos/manta/amoeba/src"
  - "grep PATH|def |subprocess|monkeypatch in /Users/manta/source/repos/manta/amoeba/tests/cf_stub.py"
  - "grep class |def |migrate|CalledProcessError|UpdateError|cf_projects|check_store|installed-commit|restore|read_back|readback|list in /Users/manta/source/repos/manta/amoeba/scripts/update_live.py"
  - "grep class FakeSteps|def test_|cf_projects|migrate|def _|update_live\\.(update|restore|main) in /Users/manta/source/repos/manta/amoeba/tests/scripts/test_update_live.py"
  - "list_files {src/amoeba/wiring_releases.py,src/amoeba/cli/registration_arguments.py,src/amoeba/cli/render/registry.py,src/amoeba/cli/render/registration.py,src/amoeba/operations/wake_status.py,src/amoeba/operations/changes_models.py,src/amoeba/operations/set_up_models.py,src/amoeba/operations/status_runs.py,src\u2026 in /Users/manta/source/repos/manta/amoeba"
  - "grep start_failed|def test_|project_of|monkeypatch in /Users/manta/source/repos/manta/amoeba/tests/operations/test_wake_after_send.py"
  - "grep project_of|monkeypatch|def test_ in /Users/manta/source/repos/manta/amoeba/tests/cli/test_standing_cli.py"
  - "grep migrate|EXPECTED|INSERT INTO members|def |schema in /Users/manta/source/repos/manta/amoeba/tests/store/test_migration_010.py"
  - "grep INSERT INTO members|migrate|EXPECTED_SCHEMA_VERSION|def test_ in /Users/manta/source/repos/manta/amoeba/tests/store/test_migrations.py"
  - "grep Frozen|class SetUpProblemCode|NOT_A_PROJECT|MALFORMED|NOT_IN_PROGRAM|= \\\"|class |class SetUpRequest|project|attach|new_member|wake_command|depends_on|bulk in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/set_up_models.py"
  - "grep def test_|count|TABLE|table|flag|--|problem|SetUpProblemCode|RefusalCode|store-contract|cli-contract in /Users/manta/source/repos/manta/amoeba/tests/test_contract_docs.py"
  - "grep def test_|wake|set_up|WakeCommand|wake_command in /Users/manta/source/repos/manta/amoeba/tests/test_import_boundaries.py"
  - "grep GIT_SUBCOMMANDS|frozenset|\"show\"|ls-tree|reference= in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep reference|project_names|def test_ in /Users/manta/source/repos/manta/amoeba/tests/upstream/context_forge/test_project_of.py"
  - "grep from amoeba\\.operations\\.(send|inbox|reply|cancel|changes|report_release|standing|list_view|status|rm|add|message_member|release_member|pause_eligibility|set_up_remove|set_up)\\b|from amoeba\\.wiring in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep CREATE TABLE members|project_id|registered_at|PRIMARY KEY|CREATE TRIGGER|RAISE in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/schema"
  - "grep def split_statements|def migrate|def _split|BEGIN|END|;|executescript|execute\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/migrations.py"
  - "grep RUN_POLL_TIMEOUT_SECONDS|def read_run_facts|def read_calls|calls_log|def list_runs|def poll|def run_poll|read_run_facts\\(|project_of\\(|scratch|prune in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep RUN_POLL_TIMEOUT_SECONDS|LIST_RUNS_TIMEOUT|TIMEOUT_SECONDS: Final = 30 in /Users/manta/source/repos/manta/amoeba/src"
  - "grep ^COLUMN_REASONS|^def get_member\\b|^class Eligible|wake_command: |^from amoeba.upstream.context_forge.project_of|cf_project_id|MESSAGE_LOOKUPS: Final|^    OperationName\\.|class OperationName in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep COLUMN_REASONS|def test_every_column in /Users/manta/source/repos/manta/amoeba/tests/store/test_schema_holds_no_mirrored_state.py"
  - "list_files project-documents/user/{slices/260-slice.hub-and-door.md,tasks/260-tasks.hub-and-door*.md,slices/244*.md} in /Users/manta/source/repos/manta/amoeba"
  - "grep owner_id|TRIGGER|RAISE|open_hub_store|act_as_local|LOCAL_MACHINE_NAME|OPERATION_ERRORS|ServedEdges|id_names|id_resolver|rm_machine|result_from_document|wiring_door|store_open\\.py|in_process_hub in /Users/manta/source/repos/manta/amoeba/project-documents/user/slices/260-slice.hub-and-door.md"
  - "grep act_as|LOCAL|local machine|machines\\.py|served\\.py|ServedEdges|run_served|id_names|id_resolver|handle_call|rm_machine|rm-machine|SERVED_OPERATIONS|WRITING_CALLS|UNKNOWN_ADVICE|RefusalCode|wire\\.protocol|wire/protocol|errors\\.py|hub/calls|hub/admin|in_process_hub|hub_fixture|store_open|test_door_load\u2026 in /Users/manta/source/repos/manta/amoeba/project-documents/user/slices/260-slice.hub-and-door.md"
  - "grep act_as_local|LOCAL_MACHINE_NAME|store_open|in_process_hub|hub_fixture|test_door_load|run_served|ServedEdges|id_resolver|id_names|served\\.py|handle_call|hub/admin|rm_machine|WRITING_CALLS|UNKNOWN_ADVICE|RefusalCode|store/machines|machines\\.py in /Users/manta/source/repos/manta/amoeba/project-documents/user/tasks/260-tasks.hub-and-door.md"
  - "grep malformed_call|not_served|hub_error|bad_token|RefusalCode in /Users/manta/source/repos/manta/amoeba/project-documents/user/slices/260-slice.hub-and-door.md"
  - "grep from amoeba\\.operations\\.(inbox|send|reply|cancel|changes|report_release|list_view|status|rm|add|standing|message_member|release_member|pause_eligibility|set_up|list_registry|decisions|wake)\\b|from amoeba\\.operations import|from amoeba\\.operations\\.(\\w+) import in /Users/manta/source/repos/manta/amoeba/src/amoeba/mcp"
  - "grep \\b(send|inbox|reply|cancel)\\( in /Users/manta/source/repos/manta/amoeba/tests/operations"
sectionsInDocument: 19
sectionsCovered: 19
effort: xhigh
turns: 83
promptTokens: 10727046
cachedTokens: 10409997
cacheWriteTokens: 316943
completionTokens: 206146
durationSeconds: 903.7
costUsd: 1.238604
costBasis: provider
runId: run-20261121-p5-01fb5c21
squadronVersion: 0.24.35
findings:
  - id: F001
    severity: fail
    category: deferral
    summary: "Restore point deferred to #45 although section 16 rewrites that flow"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:409"
  - id: F002
    severity: fail
    category: test-plan
    summary: "16.2's \"update passes both checks\" cannot pass with the plan's fixture"
    location: "tests/scripts/test_update_live.py:87"
  - id: F003
    severity: concern
    category: ci
    summary: "No CI wiring task for the door load test"
    location: ".github/workflows/ci.yml:40"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Naming clears the wake command before the wake path reads checkouts"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:147"
  - id: F005
    severity: concern
    category: sequencing
    summary: "7.4 gives standing a caller lookup that D5 does not call for, and misses a test"
    location: "tests/operations/test_standing.py:129"
  - id: F006
    severity: concern
    category: test-coverage
    summary: "8.1 does not name tests whose assertions change"
    location: "tests/operations/test_resolve_recipient.py:45"
  - id: F007
    severity: concern
    category: test-coverage
    summary: "11.1 changes a pinned key set that 11.2 does not name"
    location: "tests/operations/test_list_registry.py:305"
  - id: F008
    severity: concern
    category: architecture
    summary: "The hub's `name_by_id` pulls the client part into the hub's imports"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:150"
  - id: F009
    severity: concern
    category: security
    summary: "Git's stderr can carry the raw address into an exception the task does not forbid"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:135"
  - id: F010
    severity: concern
    category: correctness
    summary: "\"A free name\" in step 4 of `add` leaves out the member-id check"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:253"
  - id: F011
    severity: concern
    category: sequencing
    summary: "The 9.2 commit marker sits where `add` still calls `cf`"
    location: "src/amoeba/operations/add.py:167"
  - id: F012
    severity: concern
    category: sequencing
    summary: "Interim writes bind Context Forge names under a unique index"
    location: "src/amoeba/operations/set_up.py:249"
  - id: F013
    severity: concern
    category: proportionality
    summary: "The size note omits `store/programs.py`, which 2.2 pushes past the guideline"
    location: "src/amoeba/store/programs.py"
  - id: F014
    severity: concern
    category: proportionality
    summary: "7.5 and 13.6 each bundle several modules into one unit"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:200"
  - id: F015
    severity: concern
    category: contract
    summary: "`not_served` means two things"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:360"
  - id: F016
    severity: note
    category: consistency
    summary: "2.1 and 2.3 give `insert_checkout` two signatures"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:84"
  - id: F017
    severity: note
    category: completeness
    summary: "12.2 leaves `gather_runs` without a signature"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:329"
  - id: F018
    severity: note
    category: existing-code
    summary: "2.2 names a file that builds `MemberState`, not `Member`"
    location: "tests/cli/render/test_registration.py:33"
  - id: F019
    severity: note
    category: test-coverage
    summary: "The new import rules need new test code"
    location: "tests/test_import_boundaries.py:45"
  - id: F020
    severity: note
    category: test-coverage
    summary: "New columns must sit under their `COLUMN_REASONS` heading in the store contract"
    location: "tests/store/test_schema_holds_no_mirrored_state.py:222"
  - id: F021
    severity: note
    category: test-coverage
    summary: "No named test asserts `working_directory` is null for `add` and `rm` that name a member"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md:394"
  - id: F022
    severity: pass
    category: verified
    summary: "The interim checkout path is never null"
    location: "src/amoeba/upstream/context_forge/project_of.py:81"
  - id: F023
    severity: pass
    category: verified
    summary: "The trigger in 1.1 parses through the migration runner"
    location: "src/amoeba/store/migrations.py:61"
  - id: F024
    severity: pass
    category: verified
    summary: "7.6's account of the member-id `cf -p` calls is accurate"
    location: "src/amoeba/operations/pause_context.py:193"
---

# Review: tasks — slice 261

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Restore point deferred to #45 although section 16 rewrites that flow

Line 409 says a rerun after a killed `update` "can lose the pre-update backup", calls that "outside this slice's design", and says it is "tracked as #45". The slice changes this flow (16.1 edits `update`'s failure path), and its own design (D16, design lines 462–467, and the Operator Walkthrough's "run `update` again") tells operators to rerun. The code confirms the loss: `update` takes a new backup (`scripts/update_live.py:227`) and, on success, deletes every other backup (`:240–242`). A rerun after a kill on the migrated store therefore deletes the pre-migration backup. The Amoeba rules say a task breakdown never defers in-scope behavior to an issue. Build the case into 16.1 with a test in 16.2, or remove the claim from the design.

### [FAIL] 16.2's "update passes both checks" cannot pass with the plan's fixture

`FakeSteps._migrate` only runs `Store.open(store_path()).close()` (lines 87–89). That migrates to 12 but does not name members, because naming runs in `open_state_store` (5.3, line 153). After the fake migrate, every member of the `schema_11.py` store has a null name. 16.1 (line 412) adds "no member has a null name" to `check_store`, so `update` fails its read-back, restores, and raises `UpdateError`. 16.2 (line 417) requires `update` to pass both checks. 16.1 (line 414) gives FakeSteps only `cf_projects`. Fix: have the fake migrate run the naming step with a `cf` stub on `PATH` (`tests/cf_stub.py`), or seed names and say so. The "update again" case also needs a later `now`, because `take_backup` makes the directory with `mkdir` and no `exist_ok` (`scripts/update_live.py:160–161`).

### [CONCERN] No CI wiring task for the door load test

15.4 (line 401) says `tests/load/test_door_load.py` "runs in the normal tier, so CI runs it." The only gate is the bare `uv run pytest` at `ci.yml:40`, and `addopts = ["--ignore=tests/live"]` (`pyproject.toml:64`) excludes only the live tier. No task names the CI step or checks that the load bounds run there, so gating is implicit. Add a short task that names the step and confirms the load test is in it.

### [CONCERN] Naming clears the wake command before the wake path reads checkouts

5.1 step 4 copies the old command to a checkout and sets `members.wake_command` to null, in section 5. The wake path still reads the member's column until 8.1: `store/wakes.py:125` reads `member.settings.wake_command`, and `store/programs.py:53` maps it. Commits at lines 164 through 231 therefore stop waking every named member. No test catches it, because the wake tests seed members directly. The Context Summary (line 37) says the opposite: "the wake command stays on `members` until section 8." Move the null-out into 8.1, or keep 5.1 from nulling until 8.1, and correct line 37.

### [CONCERN] 7.4 gives standing a caller lookup that D5 does not call for, and misses a test

7.4 (line 196) says the CLI `cf`-failure test "now gathers the caller's failure." Standing has no caller. D5's table (design lines 250–256) has no `standing` row, and standing's only `cf` call is `_member_project_id` (`operations/standing.py:111–118`), which 7.4 replaces with `find_member`. After the change standing makes no `cf` call, so `tests/cli/test_standing_cli.py:166–172` and `tests/operations/test_standing.py:129–139` (which expects `ContextForgeError`) have no failure to produce. Only the CLI test is named. Say standing makes no `cf` call, then rewrite or delete both tests, naming both.

### [CONCERN] 8.1 does not name tests whose assertions change

The file asserts `Recipient(KNOWN_ID, str(CHECKOUT), COMMAND)` (line 45) and `Recipient(UNKNOWN_TO_CF, None, None)` (line 51). 8.1 removes `Recipient.project_path` and `wake_command`, and 7.1 changes `resolve_recipient`'s signature. Neither 7.1 nor 8.1 names the file. The raw `UPDATE members SET wake_command` seeds at `tests/operations/test_wake_status.py:62`, `tests/operations/wake_send_support.py:77`, `tests/store/test_wakes.py:74` and `:222` set a column that 8.1 stops reading. 8.1 names only the `insert_member(wake_command=...)` seeds. Line 48 requires every test whose assertion changes to be named. Name each file and say what it asserts after the change.

### [CONCERN] 11.1 changes a pinned key set that 11.2 does not name

The test asserts the exact key set of a members row (lines 305–317, including `wake_command`). 11.1 adds `origin` and `checkouts` to `MemberRow`, so the assertion changes. 11.2 (line 317) names only `tests/operations/test_list_members.py`. `tests/cli/test_list_cli.py:162` lists the same key and should be checked. Name both under 11.1 or 11.2.

### [CONCERN] The hub's `name_by_id` pulls the client part into the hub's imports

5.2 puts `name_by_id` in `operations/naming.py`. 5.1 has that module import `project_details` (upstream) and `ORIGIN_READ_TIMEOUT_SECONDS` from `operations.here`, and `here.py` imports `upstream.context_forge.project_of`. 5.3 (line 153) has `open_hub_store` call it, so the hub imports upstream transitively. Line 40 says `here_document.py` is added "so the hub can parse what the client gathers without importing the client part." 13.6 (line 365) asserts that `amoeba.hub` imports nothing from upstream, but `tests/test_import_boundaries.py:57–66` checks direct imports only, so that test would pass. 9.2 also places `gather_add` (client, importing `here`) in `add.py`, next to the add path the door calls in 13.4. Move `name_by_id` and the timeout constant to modules with no upstream import, keep `gather_add` out of the hub's path, or state that the rule covers direct imports only.

### [CONCERN] Git's stderr can carry the raw address into an exception the task does not forbid

`git_read` returns `GitReadResult.stderr_head` (`upstream/git_read.py:44–46`, `:131–135`). 4.3 says a non-zero exit other than 2 "raises `ContextForgeError` naming the command". It forbids only the raw address and git's stdout in exception text, not git's stderr. D3 (design line 203) says no exception includes the raw address. A failing `remote get-url` that echoes `user:secret@` into stderr would reach the message. The 4.3 test uses a stub that prints no address, so nothing catches it. The message should name the command and exit code only. Add a test whose stub writes a password URL to stderr and assert it appears in neither the exception nor a log line.

### [CONCERN] "A free name" in step 4 of `add` leaves out the member-id check

D1 (design line 172) says a name equal to another member's id is refused as `name_taken`. 9.5 applies that to step 3 only. Step 4 says "a free name (`--name`, else the Context Forge name) makes a member" and never defines "free." Step 5 defines "taken" as held by an active member. A new project whose Context Forge name equals another member's id would therefore create a member that breaks D1's invariant. 9.8 tests the id clash only through `--name`, and 9.6 only through step 3. Define "free" as no active member's name and no other member's id in any case, and add a test for the Context Forge name path.

### [CONCERN] The 9.2 commit marker sits where `add` still calls `cf`

The commit marker at line 243 follows 9.2, whose test (line 240) says "no cf call for `--project`." The engine still calls `project_of(reference=request.project)` at `add.py:167` until 9.9 (line 270) removes it. If that test drives `add()`, it fails at this commit, so the marker is not at a tested point. Say the test runs through `gather_add` only, or move the marker to after 9.9.

### [CONCERN] Interim writes bind Context Forge names under a unique index

1.1 (line 73) and 2.3 (line 98) have `_write_member` bind each project's Context Forge name under a unique index on active names. Two projects sharing a name now make `add` raise a store integrity error in sections 1–9. Today `add` succeeds, because names are not stored. The naming test deliberately creates this case (5.4, line 156). The task does not say what the interim does on a clash. State it: a refusal with a clear problem, or the id as the name.

### [CONCERN] The size note omits `store/programs.py`, which 2.2 pushes past the guideline

`store/programs.py` is 284 lines. 2.2 adds six functions to it, and 5.1 and 8.1 add more, with no split. The size note (line 41) names only `store/models.py`, `set_up_models.py` and `pause_context.py`. `store/sql.py` (488 lines) stays because of the scan test (`tests/store/test_members_queried_in_one_place.py:18` and `:57–63`). 260's task file (line 42) says that file takes no new logic, and 261 does not note the departure. Put the name and origin functions in a module named for their concern, and state the `sql.py` departure in the note.

### [CONCERN] 7.5 and 13.6 each bundle several modules into one unit

7.5 covers `list_view`, `status`, `pause_eligibility`, `wiring_presence`, the `Deps.project_names` deletion, and tests across five modules. 13.6 covers five wiring modules, the result rebuild, and two import rules. Each has its own failure surface. Split 7.5 into list and status, and pause_eligibility and presence, with the `Deps` deletion last. Split 13.6 by placement.

### [CONCERN] `not_served` means two things

260's refusal table defines `not_served` as "the name is not in the served list", HTTP 404 (260 slice design, line 348). 13.5 and D12 use the same code for a `send` that is refused because a wake is due, on a name that is served. Callers cannot tell the two apart, and 404 is wrong for the wake case. Either document the overload in 260's table, or add a code. Adding a code changes 260's contract, so that choice is the PM's.

### [NOTE] 2.1 and 2.3 give `insert_checkout` two signatures

2.1 has `insert_checkout(..., wake_command, now)`. 2.3 gives the seed `insert_checkout(..., wake_command=None, added_at)`. Use one signature, with the seed passing `now=added_at`, or say which is which.

### [NOTE] 12.2 leaves `gather_runs` without a signature

The task reads "`gather_runs(...)`" and never states its parameters. A junior agent would have to design the signature. Name it, for example `gather_runs(run, git-free sq runner, runs_dir, calls_dir, timeout)`, once the caller shape is fixed.

### [NOTE] 2.2 names a file that builds `MemberState`, not `Member`

The file constructs `MemberState` (line 33), not `Member`. 11.1 covers `MemberState`, so no edit is lost, but the claim in 2.2 is wrong.

### [NOTE] The new import rules need new test code

7.6 (line 209) and 13.6 (line 365) describe module-level rules. The file's `FORBIDDEN` and `ONLY_ALLOWED` tables are package-level, so these rules need a new test function. Say so, so nobody tries to add table rows.

### [NOTE] New columns must sit under their `COLUMN_REASONS` heading in the store contract

The test asserts `documented == COLUMN_REASONS` for each reason. `members.name`, `members.origin` and each `checkouts` column must appear under the right heading in `docs/store-contract.md`. 1.1 (line 74) names the file, not the placement.

### [NOTE] No named test asserts `working_directory` is null for `add` and `rm` that name a member

The design requires this (design line 567). 11.1 implements it, but 11.2 covers only `list members`, and 15.3 (line 394) asserts "no `here`, no `cf` call" only. 17.2 (line 431) would catch it, but naming the assertion in 15.3 is cheaper.

### [PASS] The interim checkout path is never null

`_project` returns a `CFProject` only when `id`, `name` and `projectPath` are all non-empty strings. So 2.3's `ResolvedMember.path` cannot be null, and the `NOT NULL` on `checkouts.path` holds for the interim write.

### [PASS] The trigger in 1.1 parses through the migration runner

`split_statements` accumulates lines until `sqlite3.complete_statement` is true, so `CREATE TRIGGER ... BEGIN ...; END;` stays one statement. Migration 012 needs no runner change for its trigger.

### [PASS] 7.6's account of the member-id `cf -p` calls is accurate

`gather` passes `member.project_id` to `resolve_slice` (line 193), and `_read_committed` passes it to `read_target` (line 226). `program_sources.py:172` does the same for the concept member. 7.6 names these correctly.

### Run Digest

- Response length: 34450 chars
- Response is newline-free: no
- Tool calls made: 82
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 83
- Tokens — prompt / cached / cache write / completion / reasoning: 10727046 / 10409997 / 316943 / 206146 / not computed
- Duration: 903.7 s
- Cost: $1.24 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 24
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 24
- Finding-shaped matches — surviving validation: 24
