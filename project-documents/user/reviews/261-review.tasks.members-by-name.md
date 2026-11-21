---
docType: review
layer: project
reviewType: tasks
slice: members-by-name
targetKind: slice
rulesSource: project
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
reviewedSha: ede22fc30bc35aa1326d3323fb8c88eecad4641e
reviewedBlob: 4fc22ea463b6ab4086d69c4ca863e2946b082bed
reviewedBlobCurrent: true
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 97
injected:
  - key: input
    path: "project-documents/user/tasks/261-tasks.members-by-name.md"
    chars: 80803
    sha256: 9979251eba76183fba8de776d6178c05235b27cf17988c798e08b60dacbdc2d3
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
  - "src/amoeba/store/wakes.py"
  - "src/amoeba/store/sql.py"
  - "src/amoeba/store/programs.py"
  - "tests/store/test_members_queried_in_one_place.py"
  - "src/amoeba/upstream/git_read.py"
  - "src/amoeba/upstream/context_forge/project_of.py"
  - "src/amoeba/operations/pause_eligibility.py"
  - "tests/upstream/test_git_read.py"
  - "tests/test_import_boundaries.py"
  - "tests/store/test_schema.py"
  - "tests/store/test_schema_holds_no_mirrored_state.py"
  - "scripts/update_live.py"
  - "tests/scripts/test_update_live.py"
  - "tests/test_message_timing.py"
  - "tests/cli/test_rm_cli.py"
  - "tests/cli/test_add_cli.py"
  - "tests/test_contract_docs.py"
  - "docs/store-contract.md"
  - "src/amoeba/operations/set_up_resolve.py"
  - "src/amoeba/operations/set_up.py"
  - "src/amoeba/operations/add.py"
  - "src/amoeba/operations/state_move.py"
  - "tests/operations/set_up_support.py"
  - "src/amoeba/wiring_messages.py"
  - "src/amoeba/operations/message_member.py"
  - "src/amoeba/operations/set_up_remove_resolve.py"
  - "src/amoeba/operations/pause_context.py"
  - "src/amoeba/operations/handle_pause.py"
  - "src/amoeba/operations/program_sources.py"
  - "tests/store/seed.py"
  - "tests/load/test_wake_claim_load.py"
  - "tests/load/test_no_cf_under_write_lock.py"
  - "tests/store/message_support.py"
  - "tests/operations/test_set_up_validation.py"
  - "src/amoeba/operations/deps.py"
  - "src/amoeba/operations/list_registry.py"
  - "tests/store/test_migration_010.py"
  - "tests/store/relocate_support.py"
searches:
  - "list_files src/amoeba/store/schema/*.sql in ."
  - "list_files src/amoeba/operations/*.py in ."
  - "list_files tests/**/*.py in ."
  - "grep ^ in src/amoeba"
  - "grep ContextForgeError|CfCallFailed in src"
  - "grep ContextForgeError|CfCallFailed in tests"
  - "grep class NotInProgram|class NotAProject|def resolve_member|def anchor|def resolve_caller|def resolve_actor|def resolve_recipient|def resolve_release_member|def resolve_scope|def _member_project_id|def _checkout_of|def project_names|def project_details|def project_of in src"
  - "grep MESSAGE_LOOKUPS|MESSAGE_STORE_WAITS|UNBOUNDED_START|START_AFTER_OPERATIONS|worst_case|105|75 s|75 seconds|105 seconds in ."
  - "grep def (test_a_failing_cf_exits_three|test_a_cf_failure_exits_three_with_nothing_written|test_a_cf_failure_raises_and_writes_nothing|test_send_makes_three_lookups_and_the_others_two|test_a_cf_failure_on_the_explicit_member_propagates|test_project_sets_it_from_another_directory|test_a_bad_reference_is_n\u2026 in tests"
  - "grep TABLES|COLUMN_REASONS|EXPECTED_SCHEMA_VERSION|def test_.*(tables|table) in tests"
  - "grep wake_command in src/amoeba"
  - "grep wake_command|UPDATE members SET in tests"
  - "grep NO_CHECKOUT_DETAIL|claim_wake\\(|can_wake\\(|def get_member|upsert_member\\(|insert_member\\(|Member\\( in ."
  - "grep GIT_SUBCOMMANDS|SUBCOMMAND_|git_read\\(|reference=|project_names|project_details|known_to_cf|_Lookups|ProjectOf|refuse_door_fields|class Door\\b|open_state_store\\(|def open_state_store|def act_as_local|list_runs in ."
  - "grep remote|GIT_SUBCOMMANDS|allow|subcommand|ls-tree|\\\"log\\\"|\\\"show\\\" in tests/upstream/test_git_read_only_place.py"
  - "grep ^class |^def |^[A-Z_]+ = |^[A-Z_]+: Final|frozenset|allow in tests/test_import_boundaries.py"
  - "grep ^def |^class |^[A-Z_]+(: Final)? = |Steps|FakeSteps|PRODUCTION|exist_ok|installed-commit|def take_backup|def _uv_install|def check_checkout|def previous_commit|def check_store|def restore|def update|def main in scripts/update_live.py"
  - "list_files {tests/load/*.py,tests/cli/test_requests_scenario.py,tests/live/messaging/*.py,tests/operations/test_resolve_recipient.py,tests/operations/test_wake_after_send.py,tests/store/test_migration_010.py,tests/store/test_migrations.py,tests/test_message_timing.py,tests/scripts/*.py,tests/test_ci_gates_load\u2026 in ."
  - "grep Tests|addopts|testpaths|ignore|deselect|-m |marker|pytest in .github/workflows/ci.yml"
  - "grep addopts|testpaths|ignore|markers|norecurse in pyproject.toml"
  - "grep ^    \"[a-z_]+\": frozenset|^    # |^\\s+\"[a-z_]+\\.[a-z_]+\",?$ in tests/store/test_schema_holds_no_mirrored_state.py"
  - "grep mirror|^- \\*\\*[a-z]+\\*\\*:|^#+ |Context Forge already|copy of in docs/store-contract.md"
  - "grep def test_|TABLES|checkouts|members|sql\\.|sql_|STATEMENT in tests/test_contract_docs.py"
  - "grep set_up\\(|resolve_request\\(|from amoeba\\.operations\\.state_move import|operations\\.state_move|act_as|LOCAL_MACHINE|open_state_store\\b in ."
  - "grep class PauseTarget|PauseTarget\\(|def gather|def resolve_slice|def _read_committed|def read_target|def pause_claim|def _handle_polled|def place_runs|class Eligible|Eligible\\(|def resolve_member|resolve_member\\(|def presence|class ProgramRead|cf_project|\\bdef _read_plan|_plan_read|\"-p\"|CF_PROJECT_FLAG in src/amoeba"
  - "grep PauseTarget\\(|class Eligible|Eligible\\(|resolve_member\\(|project_names=|list_runs=|def _unused|cf_run= in tests"
  - "grep MemberRef\\(|MemberState\\(|MemberRow\\(|Deps\\(|class MemberRef|class MemberState|class MemberName|name: str \\| None|name=None|class MemberRow in ."
  - "grep wake_command|directory=|claim_wake|UPDATE members|insert_member|worst_case|send_bound|assert .*bound in tests/load/test_wake_claim_load.py"
  - "grep UPDATE members SET|wake_command= in tests"
  - "grep \"to\": |to=|\"member\": |--to|\"project\": |_targets|def _targets in tests/load/test_wake_claim_load.py"
  - "grep directory=|\\bsend\\(|\\binbox\\(|\\breply\\(|\\bcancel\\( in tests/load"
  - "grep \"to\": \"[a-z-]+\" in tests/operations"
  - "grep \"to\": |RECIPIENT|ADDRESSEE|\"member\": |_NAME = |_ID =  in tests/operations/test_send.py"
  - "grep ^RECIPIENT_NAME|^RECIPIENT\\b|^RECIPIENT =|^SENDER_NAME|^SENDER =|def seed_members|def message_deps|def message_cf|OUTSIDE_ANY_PROJECT = in tests"
  - "grep INSERT INTO members|seed_members\\(|RECIPIENT_NAME|RECORDED_NAME|project_names|PROJECTS = in tests/operations/message_support.py"
  - "grep INSERT INTO members in tests"
  - "grep START_AFTER_OPERATIONS|OperationName\\.(ADD|RM|STATUS|LIST|SEND|REPLY|CANCEL) in src/amoeba/wiring_release.py"
  - "grep NOT_A_MEMBER|not_a_member|NO_SUCH_MEMBER|no_such_member|NAME_TAKEN|name_taken|ORIGIN_TAKEN|member_has_checkouts|not_a_checkout|class SetUpProblemCode|class SkipReason|class RejectCode in src/amoeba"
  - "grep from amoeba\\.operations\\.add import|add\\(|empty|{}|SetUpResult|register in src/amoeba/operations/pause_eligibility.py"
  - "grep operations\\.add import|\\badd\\(|register|SetUpResult|add_document|empty document in src/amoeba/operations/pause_eligibility.py"
  - "grep git_run|git_read|subprocess\\.run|GIT_EXECUTABLE in src/amoeba/operations"
  - "grep ^def test_|pytest.raises\\(ContextForgeError\\) in tests/operations/test_message_member.py"
  - "grep ^def test_|ContextForgeError in tests/cli/test_release_cli.py"
  - "grep CF_PROJECTS_TIMEOUT_SECONDS|CF_GET_TIMEOUT_SECONDS|RUN_POLL_TIMEOUT_SECONDS|START_BOUND_SECONDS|MAX_STARTS_PER_CALL in src"
  - "list_files docs/*.md in ."
  - "list_files src/amoeba/{wiring*.py,cli/render/registration.py,cli/render/registry.py,cli/commands.py,operations/wake.py,operations/wake_status.py,mcp/message_tools.py} in ."
  - "grep def _dispatch|def status|def list_view|def place_|project_of|cli_call|directory= in src/amoeba/wiring.py"
  - "grep project_of|monkeypatch in tests/cli/test_standing_cli.py"
  - "grep keys|model_fields|== \\{|frozenset\\(\\{ in tests/operations/test_list_registry.py"
  - "grep keys|model_fields|== \\{|frozenset|\"checkouts\"|in_context_forge in tests/cli/test_list_cli.py"
  - "grep operations\\.members|member_reference|project_lookup|operations import members in ."
  - "grep legacy|LEGACY in tests"
  - "grep insert_member|INSERT INTO members|seed_members|migrate\\(|EXPECTED_SCHEMA_VERSION\", 1[01]|_migrate_to in tests/operations/state_move_support.py"
  - "grep Store\\.open|open_state_store|main\\(|members|cf_stub|PATH in tests/cli/test_legacy_move_cli.py"
sectionsInDocument: 19
sectionsCovered: 18
sectionsNotCovered:
  - "Context Summary"
effort: xhigh
turns: 98
promptTokens: 9021100
cachedTokens: 8672328
cacheWriteTokens: 348696
completionTokens: 208094
durationSeconds: 887.0
costUsd: 1.209004
costBasis: provider
squadronVersion: 0.24.36
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Existing message tests address members by Context Forge name, and no task seeds those names"
    location: "tests/store/message_support.py:21"
  - id: F002
    severity: concern
    category: sequencing
    summary: "The engine's working-directory input is never assigned"
    location: "src/amoeba/operations/set_up_resolve.py:121"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "The \"one change to tests/load\" claim is wrong, and one load test's premise goes at 7.3"
    location: "tests/load/test_no_cf_under_write_lock.py:52"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "The table-count pin is missing, and the reason rule is misdescribed"
    location: "tests/test_contract_docs.py:101"
  - id: F005
    severity: concern
    category: design-consistency
    summary: "New columns copy Context Forge and git values, which the store contract forbids, and no reason is chosen"
    location: "docs/store-contract.md:362"
  - id: F006
    severity: concern
    category: test-coverage
    summary: "Naming's gathers have no lock assertion"
    location: "src/amoeba/operations/state_move.py:117"
  - id: F007
    severity: concern
    category: sequencing
    summary: "The two check_store statements are not registered in the scan test"
    location: "tests/store/test_members_queried_in_one_place.py:106"
  - id: F008
    severity: concern
    category: sequencing
    summary: "Task 9.8 leaves the suite red until 9.11 fixes it"
    location: "tests/operations/set_up_support.py:61"
  - id: F009
    severity: concern
    category: scope
    summary: "Task 7.7 changes `handle_pause`, which the design gives to slice 262"
    location: "src/amoeba/operations/handle_pause.py:132"
  - id: F010
    severity: concern
    category: proportionality
    summary: "Task 8.1 is too large, and the test edits for the wake command are underestimated"
    location: "src/amoeba/store/wakes.py:136"
  - id: F011
    severity: concern
    category: proportionality
    summary: "The file restates the design, has granular test-only tasks, and bundles 9.9"
    location: "project-documents/user/tasks/261-tasks.members-by-name.md"
  - id: F012
    severity: note
    category: sequencing
    summary: "Task 1.1's interim uses a function that 2.2 creates"
    location: "src/amoeba/operations/set_up.py:249"
  - id: F013
    severity: note
    category: sequencing
    summary: "Task 8.1's success criterion is unmet at its own end"
    location: "src/amoeba/operations/set_up.py:186"
  - id: F014
    severity: note
    category: requirements-coverage
    summary: "The add time bound omits add's git call"
    location: "tests/test_message_timing.py:53"
  - id: F015
    severity: note
    category: test-coverage
    summary: "The `list members` field order is pinned by a contract test that 11.2 does not name"
    location: "tests/test_contract_docs.py:269"
  - id: F016
    severity: note
    category: sequencing
    summary: "From 9.2 until 10.1, a removed member can keep a checkout that `add` then finds"
    location: "src/amoeba/operations/set_up_remove.py:1"
  - id: F017
    severity: pass
    category: existing-code
    summary: "The precondition, the sizes and the named tests match the code"
    location: "src/amoeba/store/schema/010_standing_answers.sql"
---

# Review: tasks — slice 261

**Verdict:** FAIL
**Model:** claude-haiku-5-5

> Resolution note (2026-11-21): the reviewer stated FAIL. The FAIL finding and nine of the ten concerns were resolved in the task file and design after this review (commit follows this file). Not done: the size finding's folds and splits (3.2 into 3.1, 6.2 into 6.1, splitting 9.9, trimming restated design text), judged cosmetic. Coverage: 18 of 19 sections listed; "Context Summary" was cited in findings but not listed. No further review was run, by the PM's instruction.

## Findings

### [FAIL] Existing message tests address members by Context Forge name, and no task seeds those names

Task 2.3 (line 100) makes `insert_member` bind the project id as the name when none is given. Task 7.1 (lines 185–187) moves `to` lookups to store names, and no task seeds names. Existing tests send to a Context Forge name that the cf stub maps to a seeded id. `RECIPIENT_NAME` is `"recipient-project-name"` (`tests/operations/message_support.py:28`), the stub maps it at `:40`, and the member is seeded by id at `:56`. `tests/operations/test_send.py:76` and `:562` send `to: RECIPIENT_NAME`, and the other send, reply, cancel and inbox tests use the same pattern. After 7.1 these are rejected as `UNKNOWN_RECIPIENT`. `tests/load/test_wake_claim_load.py:68–70` and `:107–115` do the same.

Line 49 says "If any other test fails, fix the code, not the test." The design's one allowed test edit (design line 532; task 9.11, line 297) covers only a reference to a Context Forge project that is not a member. So the implementer must either keep Context Forge-name lookups (against D6) or edit tests outside the allowed kind. Fix: state the rule that a test addressing a member by a name other than its id seeds `name=` with assertions unchanged, add it to the allowed edit, and place it in 2.3 or 7.1.

### [CONCERN] The engine's working-directory input is never assigned

`set_up()` takes `directory` and `run` (`src/amoeba/operations/set_up.py:315–333`). `resolve_request` calls `project_of(directory=…)` (`set_up_resolve.py:121`) to set `SetUpResult.working_directory` and the default project for entries that name none. Task 9.9 (line 286) changes only `add()`, and 10.1 (line 310) changes only `rm()`. The callers that pass `directory=` and `run=` are `add.py:144,155`, `rm.py:98`, and `tests/operations/set_up_support.py:69–83` (`run_set_up`, used by about a dozen test modules).

Nothing says how the engine receives the gathered caller or checkout, or how `working_directory` becomes null when nothing was gathered (design D13). So 10.2's "`rm <name>` from a non-project directory, with no cf call" (line 315) cannot pass while line 121 still calls `cf`. Task 9.8 (line 281) says only "the cf lookups … go." Fix: assign the engine's new input, the null `working_directory` rule and the `run_set_up` change to 9.8 or 9.9.

### [CONCERN] The "one change to tests/load" claim is wrong, and one load test's premise goes at 7.3

Task 8.1 (line 231) says the wake-claim load test's seed edit "is the one change to an existing tests/load file." Several load files call changed operations with `directory=`:
- `test_wake_claim_load.py:111–117` (`send`, changed in 7.1)
- `messages_worker.py:67,78` (`reply`, `inbox`)
- `test_messages_load.py:250–253` (`reply`, `inbox`, `cancel`)
- `test_report_release_load.py:85` (`report_release`, changed in 7.3)

`test_no_cf_under_write_lock.py:60–69` calls `report_release` with `directory=` and asserts at line 68 that the operation called `cf` ("the member is resolved through cf"). After 7.3 the operation makes no `cf` call, so that assertion fails and the lock check passes vacuously. Context Summary line 45 says the file "keeps passing", and no task says how.

Separately, `test_wake_claim_load.py:142–143` bounds sends by `worst_case_seconds`, which falls from 105 s to 45 s under 7.1. So "bounds untouched" (line 231) is not exact. Fix: drop the one-change claim, list these edits in 7.1 and 7.3, make the lock test gather outside the transaction, and record the bound change in 17.3.

### [CONCERN] The table-count pin is missing, and the reason rule is misdescribed

Task 1.1 (line 73) lists the pins to update: schema version, `TABLES`, `COLUMN_REASONS`. It omits `tests/test_contract_docs.py:101` (`assert len(schema) == 14`), which fails once `checkouts` and 260's tables are added. `tests/store/test_schema.py:86` is already named "…all_thirteen_tables" while `TABLES` (lines 24–39) lists 14 names, so "its test's name states the count and is renamed to match" has no correct target.

Line 73 also says each column goes "under the heading of the reason." `test_schema_holds_no_mirrored_state.py:230` matches a bullet `- **reason**:` in `docs/store-contract.md` (lines 367–381), not a heading. The contract says "every column is one of eight things" (`docs/store-contract.md:362–363`), so a ninth reason breaks that sentence. Fix: say bullets, state the sentence change if a reason is added, and state the count to expect after 011 and 012.

### [CONCERN] New columns copy Context Forge and git values, which the store contract forbids, and no reason is chosen

`docs/store-contract.md:362` says "the schema holds no state that Context Forge or Squadron already says." Several new columns break that:
- `members.origin` copies git's `origin` remote. Task 9.2 (design D7 step 1, design line 300) rewrites it when the checkout's remote differs. So it is not "record" (never updated to follow anything else), and it is not a PM setting.
- `checkouts.path` and `checkouts.cf_project_id` copy Context Forge's `projectPath` and project id. They are written once, so "record" may fit.
- `members.name` copies the Context Forge name by default (D4) and is PM-set with `--name`, so "settings" may fit.

Task 1.1 (line 73) says to pin each "under the reason that fits" without naming one, and the design has no sentence on the rule. Fix: choose a reason per column, state the exception for `members.origin` in the design, and amend line 362 if it stays.

### [CONCERN] Naming's gathers have no lock assertion

The Context Summary (line 45) and design D15 (line 450) require that no `cf`, `git` or `sq` runs under a write lock. D15 says the existing `test_no_cf_under_write_lock.py` already asserts it, but that test covers only `report_release`. The naming step adds `cf list projects` and one `git` call per member inside `open_state_store` (`state_move.py:117–120`). Task 5.4 (lines 156–163) has no check of lock state during those calls. Fix: add a naming test that uses the lock probe from `tests/load/test_no_cf_under_write_lock.py`, or asserts that the gather runs before `store.write()`.

### [CONCERN] The two check_store statements are not registered in the scan test

Task 16.1 (line 442) adds two statements on `members` to `store/sql.py` and says "the scan test allows a members statement nowhere else." It does not say to register them. `test_only_the_named_sql_constants_query_members` (lines 75–85) fails for any member statement not in `ACTIVE_READS` or `OTHER_MEMBER_STATEMENTS`. Tasks 2.2, 5.1 and 8.2 each register theirs; 16.1 does not. Also, `test_the_predicate_is_written_once` (lines 96–103) requires active reads to interpolate `{sql.ACTIVE_MEMBER}` rather than repeat the literal. Fix: say which set each statement goes in, and state the interpolation rule once.

### [CONCERN] Task 9.8 leaves the suite red until 9.11 fixes it

Task 9.8 (line 281) makes every reference a store read. That breaks every `set_up` test that resolves a reference through the `projects=` stub (`set_up_support.py:61–66`, used by about a dozen modules). The fix is the allowed edit in 9.11 (line 297), which comes after 9.9 and 9.10. Task 9.8's success criteria (line 283) name only `test_set_up_validation.py`, so the task can be checked off with the suite red. Fix: move the allowed test edit into 9.8 and name the tests it covers.

### [CONCERN] Task 7.7 changes `handle_pause`, which the design gives to slice 262

Design line 65 excludes `handle_pause` from this slice (262). Task 7.7 (line 217) changes `handle_pause._handle_polled` to set `PauseTarget.cf_project_id`, and 17.3 (line 467) records the departure after implementation. The change is needed, because `PauseTarget` is built here (`handle_pause.py:132–138`). But the design's Excluded list is what a 262 planner would read, so it must be amended before 7.7 is built.

### [CONCERN] Task 8.1 is too large, and the test edits for the wake command are underestimated

Task 8.1 (lines 229–231) changes `can_wake` and `claim_wake` (`store/wakes.py:136–190`), `Recipient`, `wake.py`, `wake_status.py` and `list_registry.py`, and it lists about ten test files. `grep -rln wake_command tests` returns 39 files. When `insert_member`'s parameter and `MemberSettings.wake_command` go (8.1, 8.2), every `wake_command=None` caller breaks. The task names none of them, for example `tests/store/test_programs.py:50`, `tests/operations/program_rig.py:160`, `tests/operations/test_members.py:53`, `tests/store/test_member_removal.py:90`, `tests/store/test_message_cascade.py:120` and `tests/answering/test_default_rules_reads.py:136`. Fix: split 8.1 into the store claim with its tests, and the `Recipient` and readers, and list those constructor edits.

### [CONCERN] The file restates the design, has granular test-only tasks, and bundles 9.9

The file is 470 lines with 64 numbered tasks. Several tasks repeat design text: 9.4 (lines 265–266) and 9.6 (lines 271–273) restate D7's steps and flags, 13.2 (lines 366–368) restates D12's refusal path, and 17.3 (line 467) enumerates the design's departures table (design lines 474–501). Test-only tasks that should fold into their implementation tasks: 3.2 into 3.1 (lines 115–119) and 6.2 into 6.1 (lines 174–176). Task 9.9 (lines 284–290) bundles request fields, the engine, the placement, the bulk document, the wake command and interim removal, and should split. Fix: replace restated text with decision references, fold the two test-only tasks, split 9.9, and replace 17.3's list with a pointer to the departures table.

### [NOTE] Task 1.1's interim uses a function that 2.2 creates

Task 1.1 (line 76) has the interim name rule use `is_member_name` "(2.2, same commit)." Sections 1 and 2 share a commit, so the suite is fine, but the order is backwards. Fix: move the interim rule into 2.2, or say so in 1.1.

### [NOTE] Task 8.1's success criterion is unmet at its own end

Task 8.1's success line (line 232) says the `add` wake-command tests pass "after 8.2." Section 8 has one commit, so the commit is fine, but the task cannot be checked off as written. Fix: state the 8.1 check as "waking tests pass; add wake-command tests fail until 8.2."

### [NOTE] The add time bound omits add's git call

Task 12.2 (line 354) gives `add`, `rm`, `status` and `list` their worst cases "from those constants." `add` with no member named makes a `git` call bounded by `ORIGIN_READ_TIMEOUT_SECONDS` (design line 449; task 4.3). Fix: include it in the `add` row.

### [NOTE] The `list members` field order is pinned by a contract test that 11.2 does not name

Task 11.1 adds `origin` and `checkouts` to `MemberRow`. `test_the_cli_contract_gives_each_registered_view_its_fields_in_order` (lines 269–286) checks that every field appears in order in the `members` paragraph of `docs/cli-contract.md`. Task 11.2 names the key-set pins but not this one. Fix: name it.

### [NOTE] From 9.2 until 10.1, a removed member can keep a checkout that `add` then finds

Checkouts are deleted when their member is removed only in 10.1 (line 312). From 2.3 on, the old `rm` leaves an `add`-made checkout pointing at a removed member. Task 9.2 step 1 (line 260) does not say what an on-record checkout of a removed member does. The final state never holds that row, so this matters only inside the branch. Fix: say in 9.2 that such a checkout is not on record.

### [PASS] The precondition, the sizes and the named tests match the code

The newest migration is `010`, so 0.1's BLOCKED stop (line 59) is right. The Context Summary's sizes (line 42) match: `sql.py` 488, `programs.py` 284, `set_up.py` 344, `models.py` 302, `set_up_models.py` 290, `pause_context.py` 297, `set_up_remove.py` 172. All twelve files in 0.1 (line 60) exist. The cf-failure tests, the list and standing tests, and the message-timing test named in 7.2 and 11.2 exist under the names given.

### Run Digest

- Response length: 31250 chars
- Response is newline-free: no
- Tool calls made: 97
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 98
- Tokens — prompt / cached / cache write / completion / reasoning: 9021100 / 8672328 / 348696 / 208094 / not computed
- Duration: 887.0 s
- Cost: $1.21 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17
