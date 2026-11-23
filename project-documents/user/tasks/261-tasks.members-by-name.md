---
docType: tasks
slice: members-by-name
project: amoeba
lld: user/slices/261-slice.members-by-name.md
dependencies:
- 260-slice.hub-and-door
projectState: Slices 220 to 244 are merged on main. Package version 0.2.3. Slice 260
  (hub and door, schema 11) has its design and task file and is not built as of 20261121;
  this slice starts only after 260 is merged on the target. Today a member is a Context
  Forge project id and every member lookup runs the local cf.
dateCreated: 20261121
dateUpdated: 20261123
status: in_progress
turns: 83
promptTokens: 7241565
cachedTokens: 6819324
cacheWriteTokens: 422093
completionTokens: 106040
durationSeconds: 994.1
costUsd: 6.863088
usageRounds: 5
pricedRounds: 5
usageByModel:
  claude-opus-5-5:
    rounds: 5
    costUsd: 6.8630882
    completionTokens: 106040
revision_number: 4
---

# Tasks: Members by Name

## Context Summary

- Working on slice 261 (design: `user/slices/261-slice.members-by-name.md`; decisions D1 to D16 are cited by number). A member gets its own id and a name; a Context Forge id now belongs to a **checkout** (one copy of the repo on one machine). Members are found by name in the store, `cf` is asked only about the caller's own directory, and ten more operations are served through 260's door. Next slice: 262.
- **Precondition: slice 260 is built and merged on the target.** It is not built as of 20261121, so task 0.1 stops `BLOCKED` until it is. This file uses 260's names: `wire.protocol` (`SERVED_OPERATIONS`, `WRITING_CALLS`, `UNKNOWN_ADVICE`, `RefusalCode`), `operations/served.py` (`run_served`, `ServedEdges`, `id_names`, `id_resolver`), `operations/errors.py` (`OPERATION_ERRORS`), `hub/calls.py` (`handle_call`), `hub/admin.py` (`rm_machine`), `store/machines.py` (`act_as_local`, `LOCAL_MACHINE_NAME`), `open_hub_store`, `wiring_door.py`, `wiring_results.result_from_document`, `tests/hub_fixture.py`, `tests/hub/in_process_hub.py` and `tests/load/test_door_load.py`. Where 260's slice notes record a different module or name, use 260's and note it under the task.
- Order: each commit leaves the suite passing on the local store; sections 1 and 2 share one commit. Interim steps: 1.1 and 2.3 make the existing `add` bind the Context Forge name (the id when that name is taken or not a valid member name) and write a checkout row (with the Context Forge id as the member id) until 9.9 replaces it; the wake command stays on `members`, read and written there, until section 8, which comes before `add`'s rewrite; naming (section 5) copies it to the checkout and leaves the member's copy, and 8.2 is what nulls it.
- Terms: "checkout" means a `checkouts` row. The existing `questions.checkout` column is a directory path and is not changed.
- Paths: a path with no prefix is under `src/amoeba/`. `tests/`, `docs/`, `scripts/` and `project-documents/` are from the repo root; `user/` means `project-documents/user/`.
- New modules (Component Structure): `store/schema/012_members_by_name.sql`, `store/checkouts.py`, `store/sql_checkouts.py`, `operations/origin.py`, `operations/here.py`, `operations/naming.py`, `operations/caller.py`, `operations/run_gather.py`, `operations/runs_document.py`. Added by this breakdown, so the hub never imports the client part (the modules that run `cf`, `git` or `sq`: `here`, `naming`, `run_gather`, `add_gather`): `operations/here_document.py` (what the client gathers, parsed on the hub), `operations/name_by_id.py` (5.2), `operations/add_gather.py` (9.1), and `store/member_names.py` (2.2). Test helper: `tests/store/schema_11.py` (1.2).
- Size: `store/sql.py` (488 lines) takes the new `members` statements, because `tests/store/test_members_queried_in_one_place.py` requires every statement on `members` there (D2); `checkouts` SQL goes in `store/sql_checkouts.py`. This departs from 260's task file, which says `sql.py` takes no new logic: the scan test leaves no other place, and only statements are added, no logic. `store/programs.py` (284) takes no new function: the name and `origin` functions go in `store/member_names.py` (2.2), and 8.2 only removes lines from it. `operations/set_up.py` (344) is already over and ends no longer than it starts: 2.3's interim lines are removed in 9.9, 8.2's checkout write (one `set_checkout_wake_command` call) replaces `_merged_wake_command`, 10.1's checkout delete goes where removal runs (`operations/set_up_remove.py`, 172 lines), and new logic goes in new modules (`operations/add_member.py`, 9.2). `store/models.py` (302) gains two fields on `Member` (2.2), `operations/set_up_models.py` (290) the request fields and their check (9.9), and `operations/pause_context.py` (297) one parameter (7.7). None of these can move out of the class or function it extends, so each is left a few lines past 300 and its length is noted in 17.2. Every new source file stays near 300 lines; 17.2 checks them all.
- Closed values are defined once and imported: the member-name pattern and length (2.2), `ORIGIN_READ_TIMEOUT_SECONDS` (`here`), `NAMING_GIT_SECONDS` (`naming`), `RUNS_GATHER_SECONDS` (`run_gather`), `RUNS_DOCUMENT_MAX_BYTES` (`runs_document`), the two `CallRefused` codes (`operations/errors.py`), the body keys `here` and `runs` (`wire.protocol`), and the five new `SetUpProblemCode` values. No silent fallbacks: a missing gathered value is refused, never guessed (D5).
- Secrets: the raw `origin` address git prints can hold a password. It never leaves the client part: not sent, stored, logged, returned or put in an exception's text (D3). Tests assert this (4.3, 9.12, 15.3).
- No `cf`, `git` or `sq` under a write lock: every gather runs before the transaction. `tests/load/test_no_cf_under_write_lock.py` keeps its lock assertion and is moved onto the placement in 7.3; naming gets the same check in 5.4.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. "Checks pass" means all four, with no failure beyond the baseline noted in 0.2.
- Tests use the autouse `AMOEBA_HOME` fixture, `tests/store/seed.py`, `tests/store_open.py` (260), `tests/cf_stub.py`, `tests/git_repo.py`, `tests/user_configs.py`, `tests/fault_injection.py` and a settable clock. Destructive SQL runs only against throwaway stores.
- `tests/test_contract_docs.py` requires every new table, column, flag and problem code in the contract docs, so the task that adds one adds its entry. Task 17.1 writes the prose.
- **Existing tests.** In the task that makes a change, update mechanically every existing test that constructs a changed type, calls a changed signature, monkeypatches a moved or deleted name, or pins a set, count or text the change alters, without changing what it asserts; the task's checks include them, and a note under the task lists the modules touched. A test whose assertion changes is named in its task. The design allows two kinds of edit beyond that. A test that addressed a member by the name its `cf` stub gave it seeds that name (`insert_member(name=...)`), assertions unchanged (7.1). A test that referred to a Context Forge project that is not a member seeds or registers it first (9.8). If any other test fails, fix the code, not the test. 17.3 records these edits in the design's Migration Plan.
- **Existing `cf`-failure tests.** A test that expects `ContextForgeError` (or exit 3) from an operation whose `cf` call this slice moves or removes changes in the task that does it, and is named here. Where the operation still has a gather (`gather_caller`, `gather_checkout`, `gather_runs`), the test drives the `wiring*` placement or the CLI with a failing `cf` stub and asserts the same error and that nothing was written. Where no `cf` call is left (a named recipient or member, `standing`, `decisions`, `rm <name>`, `add --project`, the `list` registry views), the test is deleted and that task's "`cf` stub that fails if called" test stands in its place. By task, all under `tests/operations/` unless a path is given: 7.1 `test_send.py`, `test_reply.py`, `test_cancel.py`, `test_message_member.py` (its directory test moves to the placement, its recipient test and `test_a_cf_failure_on_the_explicit_member_propagates` are deleted, and its other `resolve_caller` calls follow the new signature); 7.3 `test_changes.py`, `test_report_release.py`; 7.4 `test_standing.py`, `tests/cli/test_standing_cli.py`, `test_decisions.py`; 7.5 and 12.2 `test_status.py`, `test_status_scope.py`, `test_status_sweep.py`; 7.6 `test_pause_eligibility.py`; 9.8 `test_set_up_validation.py`; 9.9 `test_add.py`; 10.1 `test_rm.py`; 11.1 `test_list_registry.py` and `tests/cli/test_list_cli.py` (`test_a_failing_cf_exits_three`, for `list members` and `list dependencies`). Before each of those tasks, `grep -rn "ContextForgeError\|CfCallFailed" tests` finds any other, which is handled the same way and noted.
- **Call sites move with their operation.** A task that changes what an operation takes (a `here` in place of `directory` and a `cf` runner) changes its call site in `wiring*.py` in the same task, so every commit leaves the CLI and MCP paths working: the placement runs the gather and passes the result. Until section 13 the placement always runs the hub part in process.
- Production state: no task writes the live store or config. The live migration and naming ride the next release through `scripts/update_live.py update` (D16); section 16 tests the script on copies only.
- Work on branch `261-slice.members-by-name` (created in 0.2). Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.

## 0. Setup (effort 1)

- [x] **0.1 Target and prerequisites**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty. `git checkout {target}`. The design and this task file are committed there, with no other uncommitted change
  - [x] Confirm 260 is merged: `store/schema/011_hub_and_door.sql` exists and `EXPECTED_SCHEMA_VERSION` is 11; the names in the Context Summary's precondition exist (`grep -rn` each). If any is missing, write `BLOCKED: slice 260 is not merged (<what is missing>)` under this task and stop
  - [x] Confirm the files this slice edits exist: `operations/members.py`, `operations/member_reference.py`, `operations/project_lookup.py`, `upstream/context_forge/project_of.py`, `upstream/context_forge/projects.py`, `upstream/git_read.py`, `scripts/update_live.py`, `tests/scripts/test_update_live.py`, `tests/store/test_members_queried_in_one_place.py`, `tests/test_message_timing.py`, `tests/cli/test_requests_scenario.py` (240's chain), `tests/live/messaging/test_messaging_live.py`
  - [x] Run `cf --version` and `git --version` and note both. If `cf get --json` in this repo, or `cf list projects --json`, no longer gives `id`, `name` and `projectPath`, write `BLOCKED:` with the shape found and stop
  - [x] Success: the target is checked out and clean; a note gives the target and both versions
  - Note: target is `main` (no integration branch); `cf` 0.19.28, `git` 2.50.1; 260 is merged (schema 11, every named module exists); `cf get --json` and `cf list projects --json` give `id`, `name`, `projectPath`.
- [x] **0.2 Branch and baseline**
  - [x] `git checkout -b 261-slice.members-by-name {target}`; if the branch exists, `git checkout 261-slice.members-by-name`
  - [x] Run the checks once and note the baseline; failures present before this slice are listed by test name and not fixed
  - [x] Success: `git branch --show-current` prints `261-slice.members-by-name`; the baseline is noted
  - Note: baseline clean: ruff format, ruff check, pyright 0 errors, 4877 tests pass.

## 1. Migration 012 (D1, D2; effort 3)

- [x] **1.1 `store/schema/012_members_by_name.sql` and the inserts that need a name**
  - [x] `members.name TEXT COLLATE NOCASE` and `members.origin TEXT`, both nullable; a unique index on each `WHERE removed_at IS NULL`; a `BEFORE INSERT` trigger on `members` that aborts when `name` is null, worded like 260's owner triggers
  - [x] `checkouts`: `checkout_id` integer key; `member_id` not null referencing `members(project_id)`; `machine_id` not null referencing `machines`; `cf_project_id` not null; `path` not null; `wake_command` nullable; `owner_id` referencing `owners`; `added_at`, `updated_at` not null. Unique `(machine_id, cf_project_id)`; an index on `member_id`; 260's `owner_id` trigger for this table
  - [x] The migration only adds; `members.wake_command` stays (D2). `EXPECTED_SCHEMA_VERSION` becomes 12. Pins updated: the schema-version pins; the two table-count pins, each one more than 260 left it (`assert len(schema) == N` in `tests/test_contract_docs.py`, and the `TABLES` set in `tests/store/test_schema.py`, whose test name states a count and is renamed to the true one); and `COLUMN_REASONS` in `tests/store/test_schema_holds_no_mirrored_state.py`
  - [x] The reason for each new column, with no reason added, so the contract's "one of eight things" stays true: `members.name`, `members.origin` and `checkouts.checkout_id`, `member_id`, `machine_id`, `cf_project_id`, `path`, `added_at`, `updated_at` are **membership** (a checkout is the registration of one copy of a repo on one machine); `checkouts.wake_command` is **settings**; `checkouts.owner_id` takes the reason 260 gave its other `owner_id` columns. The test matches a `- **reason**:` bullet in `docs/store-contract.md`, so each column is added to its reason's bullet. The contract's sentence that the schema holds no state Context Forge already says gains one line: a checkout's Context Forge id and path and a member's `origin` are the keys Amoeba recognises a caller and a repo by, taken when `add` runs in that checkout and never read as Context Forge's or git's current state
  - [x] Raw member inserts in existing tests made after a full `migrate` (`tests/store/test_migrations.py`, and any other that `grep -rn "INSERT INTO members" tests` finds migrating to the latest version first) bind a `name`
  - [x] `store/sql.py`: `INSERT_MEMBER` binds `name` (and `origin`, null here). `upsert_member` (in `store/programs.py`) gains a required keyword `name` that the insert binds; an update leaves the stored name unchanged. Its callers: `set_up._write_member` (next item) and the direct calls in tests (`grep -rn "upsert_member(" tests`), which pass `name=` the project id
  - [x] Interim (replaced in 9.9): `set_up_resolve.ResolvedMember` gains `name` and `path`, from the `CFProject` the resolver already reads for that member; `set_up._write_member` passes `name` to `upsert_member`. The name it passes is naming's rule (D4), so the unique index is never hit: the Context Forge name when it passes `is_member_name` (written in 2.2, so build 2.2's vocabulary item before this one; they share a commit), no active member has it in any case and it is no other member's id; else the project id. Re-registering a removed member keeps its stored name (`REREGISTER_MEMBER`), so the interim applies the same rule to it: kept when still free, else replaced by the project id with `set_member_name` (2.2), in the same transaction. Tests in 2.3
  - [x] Store contract: the two columns, indexes, trigger and `checkouts` in `docs/store-contract.md`
  - [x] Success: a fresh store migrates to 12
  - Note: the interim naming rule and checkout insert are in a new small module `operations/set_up_interim.py` (not lines in `set_up.py`, which is already over 300 lines); 9.9 deletes the module instead of removing lines. `store/programs.py`'s `_member` was renamed `member_from_row` (public) so `store/member_names.py` can use it. `tests/store/test_schema.py` has no test whose name states a count, so nothing was renamed; its `TABLES` gained `checkouts`. Raw member inserts fixed in `test_migrations.py` and `test_machines.py`; all `upsert_member(` calls in tests pass `name=` (tests: cli/test_pause_cli, operations/gather_rig, test_members, pause_support, mcp_server/presence_rig, store/test_programs, test_message_cascade, test_acting_machine, test_member_removal). `Member(...)` constructions in `program_rig.py`, `test_status_placement.py`, `test_status_runs.py` pass a name and origin.
- [x] **1.2 Migration tests**
  - [x] `tests/store/schema_11.py`: builds a schema-11 store the way `tests/store/test_migration_010.py` builds its schema-9 store (migrate to 11, insert rows by plain SQL), with members (some with wake commands), pairs and messages; shared by 1.2, 5.4, 15.3 and 16.2
  - [x] `tests/store/test_migration_012.py`: row counts unchanged; every existing member has a null `name`; an insert with a null name is refused; two active members with one name are refused, in either case (`forge`, `Forge`); a removed member's name can be taken; two null `origin`s are allowed; `(machine_id, cf_project_id)` is unique; a `checkouts` insert with a null `owner_id` is refused
  - [x] Success: this file's tests pass. No commit here: section 1 commits with section 2

## 2. Store functions for names, `origin` and checkouts (D1, D2, D7, D8; effort 3)

- [x] **2.1 `store/checkouts.py` and `store/sql_checkouts.py`**
  - [x] `Checkout` (frozen): `checkout_id`, `member_id`, `machine_id`, `cf_project_id`, `path`, `wake_command`, `added_at`, `updated_at`. `insert_checkout(transaction, *, member_id, cf_project_id, path, wake_command, now)`: machine and owner from `transaction.acting()`
  - [x] Reads: `checkout_at(transaction, machine_id, cf_project_id)`; `checkouts_of_member` and `checkouts_on_machine`, ordered by `added_at`, then `checkout_id` ("the one added first", D9, D11, D13); `first_checkout_on(transaction, member_id, machine_id)`
  - [x] Deletes: `delete_checkouts_of_member`; `delete_checkouts_on_machine`; `delete_checkouts_at_path(transaction, machine_id, path)`, comparing as text after trailing slashes are dropped from both sides, returning the number deleted (D8)
  - [x] `set_checkout_wake_command(transaction, checkout_id, command)`: raises `StoreError` naming both machines when the checkout is not on the acting machine (D7)
  - [x] Tests, `tests/store/test_checkouts.py`: insert and read back; order by `added_at`; `first_checkout_on` per machine; `delete_checkouts_at_path` with and without a trailing slash on either side, and two rows at one path both deleted; deletes by member and by machine; `set_checkout_wake_command` on another machine's checkout raises and changes nothing
  - [x] Success: pyright clean; this file's tests pass
  - Note: `set_checkout_wake_command` takes a fourth parameter `now` (small conflict: `updated_at` must move when the command changes).
- [x] **2.2 Member names and `origin` in the store**
  - [x] `store/vocabulary.py`: `MEMBER_NAME_PATTERN` (`[A-Za-z0-9][A-Za-z0-9._-]*`), `MEMBER_NAME_MAX_LENGTH` (64), `is_member_name(text)` (D1)
  - [x] The store's `Member` gains `name: str` and `origin: str | None`; the row reader raises `StoreError` naming the member id when `name` is null (D4; tested in 5.4). `store/programs.py`'s `_member` reads by index, so `name` and `origin` are appended at the end of `_MEMBER_COLUMNS` and the existing indexes stay. Direct `Member(...)` constructions in tests (`tests/operations/program_rig.py`, `test_status_placement.py`, `test_status_runs.py`, and any other `grep` finds) pass a name
  - [x] New statements in `store/sql.py`, functions in the new `store/member_names.py`: `active_member_by_name` (case-insensitive), `active_member_by_origin`, `removed_member_by_origin` (most recently removed), `name_is_other_members_id(transaction, name, member_id)` (case-insensitive over all members), `set_member_name`, `set_member_origin`. Add each new statement to `tests/store/test_members_queried_in_one_place.py`: the two active-only reads to `ACTIVE_READS` (they carry `ACTIVE_MEMBER`), the others to `OTHER_MEMBER_STATEMENTS`
  - [x] Tests, `tests/store/test_member_names.py`: lookups by name in another case; a removed member is not found by name or `origin`; `removed_member_by_origin` returns the most recently removed; `name_is_other_members_id` in another case, and false for the member's own id; `is_member_name` for valid, `:`, leading `.`, 64 and 65 characters
  - [x] Success: pyright clean; this file's tests pass
- [x] **2.3 Seed helpers and the interim checkout**
  - [x] `tests/store/seed.py`: `insert_member` gains `name: str | None = None`, binding the project id when none is given (naming's rule for a member `cf` does not know); add `insert_checkout(transaction, *, member_id, cf_project_id, path, wake_command=None, now)`, which calls 2.1's function with the same keywords (`now` is the row's `added_at`)
  - [x] Interim (replaced in 9.9): `set_up._write_member`, for each member it writes with no checkout at (acting machine, its Context Forge id), inserts one with the Context Forge id as `member_id` and `cf_project_id` and `ResolvedMember.path`, so section 7's caller lookup finds members `add` made
  - [x] Tests: an `add` creates the member under its Context Forge name with one checkout on `local`; a second `add` there adds none; an `add` of a second project with the first's Context Forge name (either case), and one whose name has a space, each succeed with the project id as the name; a removed member re-registered after an active member took its name comes back named by its project id
  - [x] Success: checks pass
  - Note: tests for the interim are in `tests/operations/test_set_up_interim.py`. Checks run once on the final tree: format, lint and pyright pass; the one full-suite failure `tests/hub/test_joined_entry_points.py::test_a_running_mcp_server_that_is_then_joined_hits_the_store_error_handler` passed when run alone afterward (order-dependent, not caused by this slice's code as far as seen).

**Commit**: `feat: add migration 012 with member names, origin and checkouts`

## 3. The `origin` rule (D3; effort 2)

- [ ] **3.1 `operations/origin.py` and `git remote get-url origin` through `git_read`**
  - [ ] `reduce_origin(address) -> str | None`, pure, never raises: accepts `scheme://[user[:password]@]host[:port]/path` and `[user@]host:path`; drops scheme, user and password; keeps a port; lower-cases; removes a trailing slash, then `.git`, then a slash. No host (a path, `file://`) or unreadable text gives `None`
  - [ ] `is_reduced_origin(value) -> bool`: `host[:port]/path` with a host and a path, lower case, no `://`, no `@` in the host, no trailing slash, no trailing `.git`. Imports only the standard library
  - [ ] `upstream/git_read.py`: `SUBCOMMAND_REMOTE = "remote"` joins `GIT_SUBCOMMANDS`; `remote_origin_args()` returns the tuple for `remote get-url origin`. For `remote`, `git_read` accepts only that exact tuple and raises `ValueError` otherwise, so no write is reachable
  - [ ] `tests/upstream/test_git_read.py`: the allowlist pin gains `"remote"`, and the test's title states the new count. `git_read.py`'s module docstring, which says the allowlist is three read commands, names the fourth and that only `remote get-url origin` is accepted
  - [ ] Success: pyright clean; the `git_read` tests pass
- [ ] **3.2 Tests**
  - [ ] `tests/operations/test_origin.py`: D3's two forms of this repo, `git@github.com:ecorkran/amoeba.git` and `https://github.com/ecorkran/Amoeba/`, both reduce to `github.com/ecorkran/amoeba`; a URL with `user:password@` reduces with no password; a port is kept (`https://host:8443/org/repo`); `ssh://git@host/org/repo.git`; a local path, `file:///x/y` and empty text give `None`; every non-`None` output passes `is_reduced_origin`
  - [ ] `is_reduced_origin` refuses: upper case, `https://...`, `git@host:...`, a trailing slash, a trailing `.git`, no path, no host
  - [ ] `git_read` with `("remote", "add", ...)` and `("remote", "set-url", ...)` raises `ValueError` and runs nothing
  - [ ] Success: checks pass

**Commit**: `feat: add the origin rule that decides when two checkouts are one repo`

## 4. The client part (D5, D10, D12; effort 3)

- [ ] **4.1 Errors in `operations/errors.py`**
  - [ ] Move `ContextForgeError` from `operations/members.py` to `operations/errors.py`; update every importer `grep -rln "ContextForgeError" src tests` lists (`members.py`, which defines it today, imports it from `errors.py` until 10.3 deletes the module). `OPERATION_ERRORS` keeps its members
  - [ ] `CallRefused(Exception)` with `code` and `message`; `MALFORMED_CALL = "malformed_call"` and `NOT_SERVED = "not_served"` as plain strings. Not in `OPERATION_ERRORS` (D12). The module imports nothing from `upstream`, `wire` or any client-part module
  - [ ] Success: checks pass
- [ ] **4.2 `operations/here_document.py`**
  - [ ] Frozen models: `HereCaller(project_id)`, `HereCheckout(project_id, name, path, origin: str | None)`, `HereNotAProject(not_a_project: str)`. `here_to_document(value)` and `parse_here(value: object, *, checkout: bool)`: the model, or `CallRefused(MALFORMED_CALL, ...)` when missing, unparseable, the wrong kind, or with an `origin` failing `is_reduced_origin` (D3, D5); the message names the key and field, never the `origin` value. Imports only `operations.origin`, `operations.errors`, `pydantic` and the standard library
  - [ ] Tests, `tests/operations/test_here_document.py`: round-trip of each model; missing, wrong kind, unknown shape and unreduced `origin` each raise `CallRefused` with `MALFORMED_CALL`; `MALFORMED_CALL` and `NOT_SERVED` are each a `RefusalCode` value
  - [ ] Success: checks pass
- [ ] **4.3 `operations/here.py`**
  - [ ] `ORIGIN_READ_TIMEOUT_SECONDS: Final = 10.0`. `gather_caller(directory, run) -> HereCaller | HereNotAProject`: one `project_of(directory=...)` call; not a project is a value; a `cf` failure or timeout raises `ContextForgeError`
  - [ ] `git_root(path) -> Path | None`: resolves `path` first (as `_checkout_of` does), then the nearest of it and its parents with a `.git` entry, or `None`. `pause_eligibility._checkout_of` becomes `git_root(directory)` or `directory.resolve()`, keeping its result unchanged
  - [ ] `gather_checkout(directory, run, git) -> HereCheckout | HereNotAProject`, where `git` is the runner `git_read` takes: the same `cf` call; `git_root(project path)` of `None` gives `origin` null with no git call; exit 2 gives null; any other non-zero exit, a missing `git`, a directory that cannot be entered, or no answer within the timeout raises `ContextForgeError` whose text is the command and the exit code (or `timed out`) and nothing else. The output is reduced before return; the raw address, git's stdout and git's stderr (`GitReadResult.stderr_head`, which can echo the address) reach no exception or log line
  - [ ] `operations/deps.py`: `Deps` gains `git_run`, built from `subprocess.run` in the default builder, for `gather_add` (9.1); test builders of `Deps` (`tests/operations/pause_support.py` and others) pass one
  - [ ] Tests, `tests/operations/test_here.py`, with `tests/cf_stub.py` and repos from `tests/git_repo.py`: a project gives `HereCaller`; not a project gives `HereNotAProject` with `cf`'s message; a `cf` failure raises; `gather_checkout` with an SSH `origin`, an HTTPS `origin` with a password (in no returned field and no log record, `caplog`), no remote, a path with no `.git` (a git stub that fails if called), and a git stub exiting 128 or sleeping past a short timeout, each raising `ContextForgeError` with no address in its text; a git stub that exits 128 after writing `https://user:secret@host/org/repo` to stderr: `secret` is in neither the exception text nor any log record (`caplog`); `git_root` for a repo, a subdirectory, a symlinked path, a linked worktree's `.git` file, and none
  - [ ] Success: checks pass

**Commit**: `feat: add the client part that gathers the caller and the checkout`

## 5. Naming the members that exist (D2, D4; effort 4)

- [ ] **5.1 `operations/naming.py`: `name_members`**
  - [ ] `NAMING_GIT_SECONDS: Final = 30.0`. `store/sql.py` gains the statement that reads unnamed members with their `wake_command`, added to `OTHER_MEMBER_STATEMENTS` in the scan test. The wake path reads `members.wake_command` until 8.1 (`store/wakes.py`, `store/programs.py`), so naming does not null it here; 8.2 adds the null-out
  - [ ] Step 1, one read: no unnamed member returns at once. Step 2, one `project_details` call; a failure raises `ContextForgeError` and nothing is written. Step 3, `git remote get-url origin` per unnamed member whose project has a path, one after another, each bounded by `ORIGIN_READ_TIMEOUT_SECONDS` and all by `NAMING_GIT_SECONDS`; a failed or timed-out call, and each member not read once the budget is spent, gets no `origin` and a warning with the path. All before any write
  - [ ] Step 4, one write over the members still unnamed, in `registered_at` order, by D4's rules: the name (the Context Forge name when listed, valid, not taken by an active member and not another member's id; else the id); the `origin` (reduced, or null with a log line when an active member has it); for an active member listed with a path, one `local` checkout with the member's id as `cf_project_id`, the path and a copy of the member's wake command (the member's own copy stays until 8.2). A removed member gets a name and `origin` without the clash checks and no checkout. The write re-reads which members are unnamed, so a second concurrent call writes nothing
  - [ ] Success: pyright clean
- [ ] **5.2 `operations/name_by_id.py`: `name_by_id`**
  - [ ] Its own module, importing only the store and the standard library, because the hub calls it and `naming.py` imports the client part. The same step-1 read (a store function both modules call); when it finds an unnamed member, one write naming each by its id. Inserts nothing, needs no acting machine, takes no lock when nothing is unnamed (D4). 8.2 adds the wake-command null-out and its log line
  - [ ] Success: pyright clean
- [ ] **5.3 Run them when a store opens**
  - [ ] `open_state_store`: after `act_as_local`, `name_members` with `cf` and git runners built from `subprocess.run`. `open_hub_store`: after the migration, `name_by_id`. `open_state_store` is in `state_move.py`, which now imports `operations.naming` and through it the client part. The hub must not reach that: if 260 put `open_hub_store` in `state_move.py` or in a module that imports it, move `open_hub_store` to a module of its own that imports neither, and note it. 13.7's import walk checks it
  - [ ] Success: checks pass (seeded members are named, so step 1 returns at once)
- [ ] **5.4 Tests**
  - [ ] `tests/operations/test_naming.py`, on a `tests/store/schema_11.py` store opened with `open_state_store`, a `cf` stub whose `list projects` lists some members, leaves one out, gives one no path and gives two the same name, and real repos, each case its own test: every member named; the unlisted one by its id with no checkout; of two with one name, the first registered has it and the other its id; a name the pattern refuses gives the id; a Context Forge name that is another member's id gives the member's own id; each listed member with a path has a `local` checkout with its path and old wake command; `members.wake_command` is unchanged on every row (8.3 tests the null-out); the member with no path has no checkout; two with one `origin`: the first keeps it, the second has none, logged; a removed member has no checkout and keeps a Context Forge name an active member also has
  - [ ] `origin` null, one test each: path missing, not a repo, no `origin` remote, address with no host
  - [ ] Two calls at once: two gathers before either write; the second write writes nothing and leaves the first's names and checkouts
  - [ ] Failures: a failing `cf` stub raises `ContextForgeError`, nothing is named, and a later open with a working stub names them; through the CLI it exits 3. A hanging git stub: naming ends within `NAMING_GIT_SECONDS` plus one `ORIGIN_READ_TIMEOUT_SECONDS` (both short), the members not read have no `origin`, and the warning says so
  - [ ] No gather under a write lock: with `cf` and git stubs that, while they run, open a second connection and take `BEGIN IMMEDIATE`, naming completes (the probe `tests/load/test_no_cf_under_write_lock.py` uses)
  - [ ] A second open makes no `cf` call. With `amoeba.operations.state_move.name_members` (the name `open_state_store` calls) monkeypatched to do nothing, the first member read raises `StoreError` naming the member
  - [ ] `name_by_id`: a schema-11 store opened with `open_hub_store` names each member by its id and creates no checkout or machine; a second open takes no write lock (a connection holding `BEGIN IMMEDIATE` does not block it)
  - [ ] Success: checks pass

**Commit**: `feat: name existing members on the first call after the upgrade`

## 6. The caller and reference lookups (D6; effort 2)

- [ ] **6.1 `operations/caller.py`**
  - [ ] Move `NotInProgram` and `NotAProject` here from `operations/members.py`, shapes unchanged; update their importers
  - [ ] `find_caller(transaction, machine, here) -> Member | NotInProgram | NotAProject`: `checkout_at(machine, here.project_id)`, then the active member by its `member_id` with the existing `get_member`, so no new `members` statement is needed
  - [ ] `find_member(transaction, reference) -> Member | None`: the active member with that name, else with that id. `find_member_for_removal`: as `find_member`, then a removed member by id only (D6, D8). Imports nothing from `upstream`
  - [ ] Success: pyright clean
- [ ] **6.2 Tests**
  - [ ] `tests/operations/test_caller.py`: caller by machine and project id; the same project id on another machine is `NotInProgram`; a removed member's checkout is not found; `HereNotAProject` gives `NotAProject`; `find_member` by name in another case, by id, unknown is `None`; a removed member is not found by `find_member`, and by `find_member_for_removal` only by id
  - [ ] Success: checks pass

**Commit**: `feat: add the store lookups for the caller and named members`

## 7. Operations moved onto the caller (D5, D6, D10; effort 5)

Each operation takes the gathered `here` in place of a directory and a `cf` runner, and finds members and names in the store; its `wiring*` placement runs the client part first and is changed in the same task (Context Summary). "A `cf` stub that answers only the caller" answers `cf get --json` for the caller's directory and fails every other command.

- [ ] **7.1 Messages: `send`, `inbox`, `reply`, `cancel`**
  - [ ] `message_member.py`: `resolve_caller`, `resolve_actor` and `resolve_recipient` take the transaction, the acting machine and `here`, and use `find_caller` and `find_member` (for `to` and an explicit `member`). Until section 8, `Recipient.project_path` is the recipient's first checkout path on the acting machine (null when none) and `wake_command` still comes from the member row. `tests/operations/test_resolve_recipient.py` follows the new signature here, its assertions unchanged until 8.1. The `member_mismatch` rule in `resolve_caller` and `UnknownActor` for a `cancel` with no member in `resolve_actor` are kept as they are; the tests that pin them (`test_send.py`, `test_reply.py`, `test_cancel.py`, `test_inbox.py`, `test_message_member.py`) change only their seeding
  - [ ] `send.py`, `inbox.py`, `reply.py`, `cancel.py` take `here`; `wiring_messages.py` calls `gather_caller` once per placement. `MESSAGE_LOOKUPS` becomes 1 for each, with its comment; the bounds in `mcp/message_tools.py` descriptions and the sentence in `docs/mcp-server.md` that states them (105 s and 75 s today) are updated from `worst_case_seconds` (D10)
  - [ ] Each existing test that seeds a member and then calls an operation as that member also seeds the member's checkout with `insert_checkout` (the `local` machine, its stub's project id and path)
  - [ ] Each existing test that addresses a member by a name its `cf` stub maps to a seeded id seeds that name with `insert_member(name=...)`, since `to` and `member` are now store reads; assertions unchanged. `tests/operations/message_support.py` seeds `RECIPIENT_NAME` this way, which covers the send, reply, cancel and inbox tests built on it; `tests/load/test_wake_claim_load.py` does the same. `grep -rn "_NAME\b" tests/operations tests/cli tests/load` and the stubs' name maps find the rest
  - [ ] Load files that call the four with `directory=` follow the new signature, bounds and assertions unchanged: `tests/load/test_wake_claim_load.py`, `tests/load/messages_worker.py`, `tests/load/test_messages_load.py`. The send bound in `test_wake_claim_load.py` is computed from `worst_case_seconds` and so falls with it (record in 17.3)
  - [ ] Success: pyright clean
- [ ] **7.2 Tests**
  - [ ] `tests/test_message_timing.py` asserts one lookup each. The lookup is now in the placement, so the test calls the four through `wiring_messages`' placements with its recording `cf` runner in place of calling the operations directly; its assertion `len(cf.calls) == MESSAGE_LOOKUPS[name]` is unchanged. Named assertion change: `test_send_makes_three_lookups_and_the_others_two` becomes `test_each_message_operation_makes_one_lookup`, asserting `MESSAGE_LOOKUPS` is 1 for each of the four, with `MESSAGE_STORE_WAITS` unchanged. With a `cf` stub that answers only the caller: `send` reaches a recipient by name and by id, including one whose project `cf` does not know; `inbox`, `reply` and `cancel` find the caller and an explicit `member` by name
  - [ ] Success: checks pass

**Commit**: `feat: find the message caller and recipient in the store`

- [ ] **7.3 `changes` and `report_release`**
  - [ ] `changes.py`, `release_member.py` (`resolve_release_member`) and `report_release.py`: caller by `find_caller`, names from the store (no `deps.project_names`). `wiring_releases.py`'s two call sites run `gather_caller` and pass `here`. Their CLI and operation tests follow the new signatures, as does `tests/load/test_report_release_load.py`. Named assertion change: `tests/load/test_no_cf_under_write_lock.py` calls `report_release` directly and asserts the operation called `cf`; the operation no longer does, so the test drives the `wiring_releases` placement, asserts the placement's gather called `cf`, and keeps its assertion that no write lock was held during the call
  - [ ] Tests: with a `cf` stub that answers only the caller, `changes` names its providers from the store and `report_release` finds the caller and its consumers by name
  - [ ] Success: checks pass
- [ ] **7.4 `standing` and `decisions`**
  - [ ] `standing.py`: the member by `find_member` in place of `_member_project_id`; its `project_of` import and its `run` parameter go, and `wiring_standing.py` stops passing `run=deps.cf_run`. Standing has no caller and no row in D5's table, so after this it makes no `cf` call at all. `tests/cli/test_standing_cli.py`'s monkeypatches of `project_of` become seeded members. Named deletions, because no `cf` failure can happen any more: `test_a_cf_failure_exits_three_with_nothing_written` (`tests/cli/test_standing_cli.py`) and `test_a_cf_failure_raises_and_writes_nothing` (`tests/operations/test_standing.py`); the test below with a `cf` stub that fails if called replaces them. `decisions.py`: names from the store
  - [ ] Delete 260's `id_names` and `id_resolver`, the reader fields of `ServedEdges` and their builders in `wiring_door.local_served_edges`; `hub/calls.py` stops passing them; 260's tests of them (`tests/operations/test_served.py`, `tests/hub/test_handle_call.py`) test the store reads instead
  - [ ] Tests: `standing --member <name>` and `<id>` are given; unknown is `no_such_member`; `standing` through the CLI and `decisions` both work with a `cf` stub that fails if called; `handle_call` runs both with no reader in `ServedEdges`
  - [ ] Success: checks pass
- [ ] **7.5 `list` and `status` names**
  - [ ] `list_view.py` and `status.py`: names from the store; `resolve_scope` uses `find_caller`. Call sites: `list_view` in `wiring_registry.py` and `status` in `wiring.py` run `gather_caller` and pass `here`; `status` still gets the directory too, for `status_placement`, which keeps its directory lookups until 12.2
  - [ ] Tests: with a `cf` stub that answers only the caller and an `sq` stub with no runs, `list` and `status` name members from the store
  - [ ] Success: checks pass
- [ ] **7.6 `pause_eligibility`, presence, and the end of `Deps.project_names`**
  - [ ] `pause_eligibility.py` and `wiring_presence.py`: each `resolve_member` call becomes `gather_caller` plus `find_caller`; `Eligible` gains `cf_project_id` (the caller's `here.project_id`)
  - [ ] Last, once nothing reads the `Deps` field (`grep -rn "deps.project_names\|project_names=" src` finds only its definition and builder; `cli/commands.py` calls `projects.project_names` directly and keeps doing so until 10.3): delete `Deps.project_names`; test builders of `Deps` (`tests/operations/pause_support.py` and the others `grep -rn "project_names" tests` lists) drop it
  - [ ] Tests: presence registers a caller found by checkout, and a directory with no checkout is a non-member in the log line; a pause from a member's checkout is eligible with `cf_project_id` set
  - [ ] Success: checks pass

**Commit**: `feat: find the caller in the store for releases, standing, list, status and pauses`

- [ ] **7.7 The pause path never gives the member id to `cf`**
  - [ ] `PauseTarget` gains `cf_project_id` (`tests/operations/held_support.py` builds one positionally and passes the new field), set in `handle_pause._handle_polled` from `Eligible.cf_project_id`; `pause_claim` passes it to `pause_context.gather`, whose `resolve_slice` and `_read_committed` pass it to `cf -p`
  - [ ] `program_sources.py`: the concept member's first-added checkout on the acting machine gives the path and the `cf_project_id` for `read_target`; with none, the `missing` problem says it has no checkout on this machine. Its `project_of(reference=...)` call goes
  - [ ] Tests, `tests/operations/test_pause_cf_ids.py`: a member with an id `cf` does not know and a checkout with another `cf_project_id`, a concept member likewise, and a `cf` stub failing any `-p` but the checkout ids: the plan, the target branch and the concept file are read, through `handle_pause`; with two concept checkouts here, the first added is read; with none, `missing`. `tests/test_cf_ids_never_member_ids.py` (AST): no `cf` argument list in `pause_context.py` or `program_sources.py` is built from `Member.project_id`. `tests/test_import_boundaries.py`: `operations.caller` and `operations.here_document` import nothing from `upstream`. That file's `FORBIDDEN` and `ONLY_ALLOWED` tables are per package, so a rule about one module is a new test function, not a table row
  - [ ] Success: checks pass

**Commit**: `feat: give the pause path checkout ids, never member ids`

## 8. The wake command on the checkout (D2, D7, D9; effort 4)

Before `add`'s rewrite, so a command is never written to a checkout while the claim reads the member.

- [ ] **8.1 The claim, `Recipient` and the readers use the checkout**
  - [ ] `store/wakes.py`: `can_wake` takes a scope (acting machine's checkouts, or every machine's), the other three conditions written once; `claim_wake` reads, in its transaction, the recipient's first-added checkout on the acting machine with a command and copies its path and command to the wake row; none, no wake. `claim_wake` loses its `directory` parameter (`log_stem` stays), and its `start_failed` branch for a null directory goes with `NO_CHECKOUT_DETAIL`: a recipient with no such checkout gets no claim and no wake row (D9). Callers that pass `directory` drop it: `wake.py`, `tests/store/wake_support.py`, `tests/operations/wake_run_support.py`, `tests/operations/test_message_sweep_wrapper.py`
  - [ ] `Recipient` loses `project_path` and `wake_command`; `wake.py` acts on the claim; `send` with no client file claims and starts as today. `wake_status.py` and `list_registry.py` (`MemberRow.wake_command`) take the command a claim on the acting machine would run (D13)
  - [ ] Test edits: wake commands seeded with `insert_member(wake_command=...)` move to `insert_checkout`, and the parameter goes. So do the raw `UPDATE members SET wake_command` seeds, which set a column nothing reads now: `tests/operations/test_wake_status.py`, `tests/operations/wake_send_support.py`, `tests/store/test_wakes.py` (two places), `tests/store/test_message_sweep.py`, `tests/operations/test_message_sweep_wrapper.py` and `tests/load/test_wake_claim_load.py` seed the command on a checkout with `insert_checkout`; `grep -rn "wake_command" tests` is the full list, and any other is edited the same way and noted. Every caller that passes `wake_command=None` to `insert_member` or builds `MemberSettings(wake_command=...)` drops the argument when the parameter and field go (here and in 8.2); `grep -rln wake_command tests` lists 39 files today, among them `tests/store/test_programs.py`, `tests/operations/program_rig.py`, `tests/operations/test_members.py`, `tests/store/test_member_removal.py`, `tests/store/test_message_cascade.py` and `tests/answering/test_default_rules_reads.py`, and the note under this task lists every one touched. Named assertion changes: the test of the null-directory branch in `tests/store/test_wakes.py` asserts no claim and no wake row, and its import of `NO_CHECKOUT_DETAIL` goes; `test_the_limit_counts_start_failed_rows` in the same file, which fills the daily limit by claiming with a null directory, fills it with real claims each ended as `start_failed` the way `wake.py`'s failed start ends one, and keeps its assertion that those rows count toward the limit; `tests/operations/test_resolve_recipient.py` asserts a `Recipient` with no `project_path` or `wake_command` for both the known and the unknown-to-`cf` member, and the path and command it asserted move to a claim test in 8.3; in `tests/operations/test_wake_after_send.py`, the `start_failed` test for a member with no checkout path asserts no wake row and the request still open (D9's departure from 244)
  - [ ] Success: pyright clean; `uv run pytest -q tests/store` and the waking tests pass. The `add` wake-command tests fail until 8.2, and that is expected here; the section commits after 8.3
- [ ] **8.2 The member's command goes: settings, null-out and the engine**
  - [ ] Remove `MemberSettings.wake_command`. In `store/sql.py`, `_MEMBER_INSERT_COLUMNS`, `_MEMBER_COLUMNS`, `UPDATE_MEMBER` and `REREGISTER_MEMBER` stop naming it (the column stays, D2); `store/programs.py`'s `_member` mapper and `upsert_member`'s binds drop it, and the indexes `_member` reads for `name` and `origin` move down by one. Then `grep -rn "settings.wake_command" src` finds nothing
  - [ ] The null-out, now that nothing reads the column: `store/sql.py` gains the statement that sets `members.wake_command` to null (in `OTHER_MEMBER_STATEMENTS`). Naming's step 4 (5.1) and `name_by_id` (5.2) run it for each member they name, logging the member id and the command when no checkout took it (always, for `name_by_id`). Only `operations/naming.py` and `operations/name_by_id.py` use the two old-column statements
  - [ ] The engine: `ResolvedMember.wake_command_given` and `wake_command` stay as intent; `set_up._merged_wake_command` goes; when given, the engine sets the caller's checkout at (acting machine, the working directory's Context Forge id) with `set_checkout_wake_command` in its transaction, after `_write_member`, so for a member this call creates the interim checkout (2.3) already exists; no checkout there is `malformed`. The top-level `wake_command` (`add.py`) and a bulk entry's (`set_up_models.py`) are accepted only on the working directory's entry; on another, `malformed`, saying a wake command is set from its own checkout (D7)
  - [ ] Named assertion changes: `tests/operations/test_add_wake_command.py` reads the caller's checkout command; `test_project_sets_it_from_another_directory` in `tests/cli/test_add_wake_command_cli.py` becomes `test_project_with_a_wake_command_is_malformed`, asserting `malformed` and that no member's command is set (D7)
  - [ ] Success: checks pass, waking tests included
- [ ] **8.3 Tests**
  - [ ] `tests/store/test_wake_on_checkout.py`: of two checkouts on one machine, the claim uses the one with a command, or the first added when both have one; a command only on another machine gives no claim with the acting-machine scope and `can_wake` true with the every-machine scope; no checkout, no claim; the claim's wake row carries the checkout's path and command (what `test_resolve_recipient.py` asserted before 8.1)
  - [ ] `add --wake-command` then `send` wakes from the checkout's path; a bulk entry for another member with `wake_command` is `malformed`; `status` shows the checkout's command
  - [ ] `tests/store/test_old_wake_column.py`: only the read (5.1) and the null-out (8.2) name `wake_command` among the `members` statements, and only `operations/naming.py` and `operations/name_by_id.py` import them
  - [ ] Naming after this task, added to `tests/operations/test_naming.py`: `members.wake_command` is null on every row; the member with no path has no checkout and the dropped command's log line holds its id and the command; `name_by_id` nulls each command and logs it
  - [ ] Success: checks pass

**Commit**: `feat: move the wake command from the member to the checkout`

## 9. `add` (D1, D5, D6, D7; effort 5)

- [ ] **9.1 The client part of `add`**
  - [ ] `operations/add_gather.py` (client part, kept out of `add.py` so the hub's add path never imports `here`): `gather_add(request, directory, run, git, door)` decides by D5's table whether `here` is needed (an entry naming no member: bare `add`, `--attach-to`, `--new-member`, a bulk entry with no member) and returns `gather_checkout`'s value, else none and no `cf` call. `refuse_door_fields(document, door)` (from `add_door.py`) runs here first, with the `Door` the placement was called through; the hub part takes no `Door`. Nothing calls `gather_add` until 9.9
  - [ ] Tests, calling `gather_add` only (the engine `add()` still calls `project_of` at this commit, until 9.9): no `cf` call for `--project` or an all-named bulk file; bare `add` returns the checkout; an MCP `add` with `wake_command` is refused before any gather
  - [ ] Success: checks pass

**Commit**: `feat: add the client part of add`

- [ ] **9.2 `operations/add_member.py`: problem codes, `--project`, step 1 and step 2**
  - [ ] `SetUpProblemCode` gains `name_taken`, `origin_taken`, `no_origin`, `member_has_checkouts`, `not_a_checkout`, with entries in `docs/cli-contract.md`. `add_member` takes the gathered value and `project`, `program`, `name`, `attach_to` and `new_member` as keyword arguments; the request models gain the last three in 9.9, where `add()` starts calling it, so no commit accepts a field it ignores
  - [ ] With `project`: `find_member`; none is `not_a_member`; no checkout read or written. `HereNotAProject` is `not_a_project`
  - [ ] Step 1: the checkout at (acting machine, project id) gives its member; the stored path is kept. A checkout whose member is removed is not on record: it is deleted in this transaction and `add` goes on to step 2 (until 10.1 the old `rm` can leave one). The three `origin` rules, in a helper 9.6 reuses: record when the member has none and no active member has it; keep when the checkout has none; replace when they differ, both values in the change record, or `origin_taken` naming both members and the way on when another active member has the new one. Step 2: an active member with this `origin` gets the checkout. Details and change records show reduced `origin`s only
  - [ ] Success: pyright clean
- [ ] **9.3 Tests**
  - [ ] `tests/operations/test_add_member.py`, hub part with hand-built `HereCheckout` values, one test each: `--project` unknown; step 1 `unchanged` again; step 1 in a second worktree is `unchanged` with the first path kept; records a missing `origin`; keeps the member's when the checkout has none; replaces a changed one with both values; `origin_taken` names both; step 2 attaches by `origin` (SSH and HTTPS forms) and after a rename
  - [ ] Success: checks pass
- [ ] **9.4 Steps 3 to 5**
  - [ ] Step 3: the most recently removed member with this `origin` is registered again in its program unless `--program`; `name_taken` if its name is now taken or another member's id and no `--name`. Step 4: a free name (`--name`, else the Context Forge name) makes a member. "Free" and "taken" mean one check, written once and used by steps 3 to 5 and 9.6: a name is taken when an active member has it or it equals any other member's id, in any case (D1); otherwise it is free. The new member is made with id `uuid4().hex` and a new program named for it unless `--program`; a Context Forge name failing `is_member_name` is `malformed`, saying to give `--name`. Step 5 has two cases. A name that equals another member's id is always `name_taken`, with or without an `origin`, saying to give `--name` (D1). A name an active member has is `name_taken` when this checkout has an `origin` (both reduced remotes, `none recorded` when the member has none, and D7's ways on by whether the member has a checkout), else `no_origin` (why, and the two ways on)
  - [ ] Success: pyright clean
- [ ] **9.5 Tests**
  - [ ] Step 3 re-registers with its program, and `name_taken` when its name is taken; step 4 gives a 32-hex id that is not the Context Forge id; a new project whose Context Forge name equals another member's id (either case), with no `--name`, is `name_taken` and creates nothing, once with an `origin` and once with none; a Context Forge name with a space is `malformed` naming `--name`; step 5 `name_taken` with both remotes and with `none recorded`; `no_origin` with its detail; the same-repo path: after a remote is added to the member's checkout and `add` is run there, `add` in the second checkout attaches
  - [ ] Success: checks pass
- [ ] **9.6 `--attach-to`, `--new-member` and `--name`**
  - [ ] `--attach-to <name>`: `malformed` naming `amoeba rm --checkout` when this checkout is on record; `member_has_checkouts` when the member has any checkout; else attach, then 9.2's `origin` rules. `--new-member`: `malformed` the same way when on record; skips steps 2 and 3; the name must be free; with an `origin` another active member has, created with none. `--name`: sets or changes the name; a value failing `is_member_name` is `malformed`, giving the pattern and the length; another active member's name, or another member's id in any case, is `name_taken`
  - [ ] Success: pyright clean; `add_member.py` near 300 lines (split by concern if not, and note it)
- [ ] **9.7 Tests**
  - [ ] `--attach-to` on a member with no checkout and no `origin`; `member_has_checkouts`; `malformed` when on record; `origin_taken`, naming both members, when another active member has this checkout's `origin` (D7). `--new-member` after the checkout row is deleted gives a new member with this checkout and leaves the first unchanged; with a taken `origin`, none recorded. `--name` with another member's id, in either case, is `name_taken`; `--name "a b"`, `--name x:y` and a 65-character name are each `malformed` and write nothing
  - [ ] Success: checks pass

**Commit**: `feat: choose or create the member for a checkout`

- [ ] **9.8 The engine's references and the removal resolver**
  - [ ] `set_up_resolve.py`: the `cf` lookups and `_Lookups` go; each reference (`depends_on`, pair ends, concept member, `--project`) is one `find_member` read in the engine's transaction. The request's `remove.members` and `remove.pairs` go through `resolve_removal`, whose `lookup` is the `cf` lookup being deleted, so `set_up_remove_resolve.py` is converted here too: its references come from `find_member_for_removal` (a removed member is found by id only), and `Reference.known_to_cf` and `set_up_remove`'s sentence built from it go. A test: an `add` document with `remove` naming a member by name, a removed member by id, and an unknown name, with a `cf` stub that fails if called.
  - [ ] An unknown reference (`members.N.project`, a `depends_on` provider, a pair end, the concept member) is `not_a_member` with its field path in the detail, where today it is `not_a_project`. Named assertion changes in `tests/operations/test_set_up_validation.py`: `test_a_bad_reference_is_not_a_project` and `test_a_bad_provider_and_concept_member_are_not_a_project` assert `NOT_A_MEMBER` with the same field paths and are renamed to say so (record in 17.3: the design's allowed edit does not cover a changed code)
  - [ ] The design's allowed edit, done here because this task is what breaks them: every test that passed `--project`, a bulk entry, `--depends-on`, `--pair` or `--concept` for a Context Forge project that is not a member, most through the `projects=` stub of `tests/operations/set_up_support.py`, seeds or registers that member first. The note lists the modules
  - [ ] Success: checks pass
- [ ] **9.9 `add()` takes the gathered checkout: request fields, placement, bulk document and wake command**
  - [ ] The `add` request gains `name`, `attach_to`, `new_member` (`project`, `attach_to`, `new_member` mutually exclusive, else `malformed`); each bulk entry gains `name`. `add()` runs `add_member` for `project` or for the entry that names no member, passing these fields
  - [ ] `add()` takes the value `gather_add` returned (a `HereCheckout`, a `HereNotAProject`, or none) in place of `directory`, `run` and `door`, and no longer calls `project_of`. `place_add` in `wiring_registry.py` calls `gather_add` with `subprocess.run`, `deps.git_run` and its `door`, then `add()`; the MCP path goes through the same placement. `SetUpResult.working_directory` is null when the call gathered nothing
  - [ ] The engine: `set_up()` and `resolve_request` take that gathered value in place of `directory` and `run`, and the `project_of(directory=...)` call in `set_up_resolve.py` goes. The gathered value gives `working_directory` and the default project for an entry that names none; with none gathered, `working_directory` is null and an entry naming no member is `malformed`. `rm.py` still has its directory until 10.1, so here it calls `gather_caller` and passes the result. `run_set_up` in `tests/operations/set_up_support.py` builds the gathered value from its stub, so the modules using it change nothing else
  - [ ] `--file`: at most one entry names no member and follows `add_member` (more is `malformed`); an entry naming a non-member is `not_a_member`, saying to run `amoeba add` in that repo
  - [ ] The wake command goes to the checkout `add_member` chose or made; with `project` it is `malformed`
  - [ ] Remove the interim code of 1.1 and 2.3 (`ResolvedMember.name` and `path`, the name rule and the checkout insert in `_write_member`). This is the last interim code in the slice (7.1's `Recipient` fields went in 8.1)
  - [ ] Success: pyright clean
- [ ] **9.10 Tests**
  - [ ] `add --project <name>` and an all-named bulk file work from a directory that is not a project, with `working_directory` null; `add --project <name> --wake-command x` is `malformed`; `--wake-command` with no member named sets only the caller's checkout; `--no-wake-command` clears it; two unnamed bulk entries are `malformed`; a non-member entry is `not_a_member` with the detail
  - [ ] Success: checks pass
- [ ] **9.11 `pause_eligibility`, the CLI and MCP**
  - [ ] `pause_eligibility`: a project in no program is registered by `gather_add` then `add` with the empty document; a refusal is the existing skip carrying its text (D6)
  - [ ] `cli/registration_arguments.py`: `--name`, `--attach-to`, `--new-member` (exclusive with `--project`, which takes a name or id), each with its entry in `docs/cli-contract.md`; `cli/render/registration.py` renders the new codes. `mcp/tools.py`: the `add` tool gains `name`, `attach_to`, `new_member`
  - [ ] Success: checks pass
- [ ] **9.12 Tests**
  - [ ] A pause in a project in no program registers it; the member's id is not its Context Forge id; with a `cf` stub failing any `-p` but the checkout ids, its plan, target branch and another member's concept file are read; a `name_taken` refusal is the skip with its text
  - [ ] CLI: the three flags reach the request; `--project` with `--attach-to` is a usage error
  - [ ] Secrets: a repo whose `origin` holds `user:secret@`, and one with a malformed address holding a password: after `add` through the CLI the secret is in no stdout, stderr, log file or store byte
  - [ ] Success: checks pass

**Commit**: `feat: rewrite add around checkouts with --name, --attach-to and --new-member`

## 10. `rm` (D8, D10; effort 3)

- [ ] **10.1 Removal by name, by caller and by checkout**
  - [ ] `rm.py`: named members by `find_member_for_removal`, through `set_up_remove_resolve.py` as 9.8 left it (a removed one by id is `unchanged`); nothing named reads the caller; `here` is gathered only in D5's case. `rm`'s anchors and its `cf` call per member go. `rm()` takes the gathered caller or none in place of `directory` and `run`; `place_rm` in `wiring_registry.py` runs `gather_caller` only in D5's case and passes it. The result's `working_directory` is null when nothing was gathered
  - [ ] The `rm` request gains `checkout`. `--checkout <path>`: relative, or combined with members, `--pair` or `--concept`, is `malformed`; `delete_checkouts_at_path` on the acting machine; none deleted is `not_a_checkout` listing this machine's stored paths; the member stays
  - [ ] Removing a member also runs `delete_checkouts_of_member` in the same transaction, after today's steps, in `set_up_remove.py` where the removal runs
  - [ ] Success: pyright clean
- [ ] **10.2 Tests**
  - [ ] `tests/operations/test_rm_by_name.py`: `rm <name>` from a non-project directory, with no `cf` call and `working_directory` null in the result, removes a member with no checkout and cancels its open requests as `member_removed`; its checkouts on every machine go; `rm <id>` twice is `unchanged`; `rm <name>` twice is `not_a_member`; bare `rm` removes the caller
  - [ ] `--checkout`: removes it and leaves the member, with or without a trailing slash and with the directory deleted; two rows at one path both go; unknown is `not_a_checkout` listing paths; relative and combined are `malformed`; the last one leaves a member with none. A moved repo: after `rm --checkout <old path>`, `add` in the new directory (same `origin`, new Context Forge id) attaches with the new path
  - [ ] Success: checks pass
- [ ] **10.3 Delete the old lookups**
  - [ ] Delete `operations/members.py`, `operations/member_reference.py`, `operations/project_lookup.py` and `tests/operations/test_members.py` (add to `test_caller.py` any case it pins that 6.2 lacks); afterwards `grep -rn "operations.members\b\|member_reference\|project_lookup" src tests` finds nothing
  - [ ] `project_of.py`: the `reference` parameter goes, with the tests in `tests/upstream/context_forge/test_project_of.py` that pass it. `projects.py`: `project_names` goes with its tests (unused after this task)
  - [ ] `cli/commands.py`: `_project_names` and its import go; change records print the names they carry. `rm --checkout PATH` in `cli/registration_arguments.py` with its `docs/cli-contract.md` entry; the MCP `rm` tool gains `checkout`
  - [ ] Tests: `amoeba rm --checkout <path>` reaches the request; `amoeba add` and `amoeba rm` print change records with a `cf` stub that fails `list projects`
  - [ ] Success: checks pass

**Commit**: `feat: remove members by name from anywhere and add rm --checkout`

## 11. Results and `list members` (D11, D13; effort 3)

- [ ] **11.1 Result fields**
  - [ ] `MemberState` gains `name` (direct constructions in tests pass it). `SetUpResult` change records name members by name (`working_directory` is already null when nothing was gathered, from 9.9 and 10.1)
  - [ ] `MemberRef.name` (`changes_models.py`) and any other `id`/`name` pair whose `name` is `str | None` because `cf` might not list the member become `str`, from the store (D13). Named: `tests/test_wiring.py` and `tests/cli/test_release_cli.py` build `MemberRef(..., name=None)`; each passes the member's name and asserts that name where it asserted none
  - [ ] `list_registry.py`: `MemberRow` gains `origin` and `checkouts` (machine name, path, Context Forge id, wake command); `path` is the first-added checkout on the calling machine or null; `in_context_forge` says whether it has one there; `project_details` and its import go. `list programs`, `list dependencies` and `list standing` read names from the store
  - [ ] `cli/render/registry.py`: `list members` shows name, id, program, `origin`, settings and checkouts; marks a member with no checkout, and one named by its id with `amoeba add --project <id> --name <name>`. Contract entries for the added fields
  - [ ] Success: pyright clean
- [ ] **11.2 Tests**
  - [ ] Named assertion changes: the exact key set of a members row in `tests/operations/test_list_registry.py` gains `origin` and `checkouts`; `tests/cli/test_list_cli.py` lists the same keys and gains them too, and its `test_a_failing_cf_exits_three` is deleted, replaced by the no-`cf` test below; `tests/cli/render/test_registry.py`'s `_member` builds rows with `origin` and `checkouts`, and its exact `list members` texts change to the new layout (name, id, program, `origin`, settings, checkouts, and the no-checkout and named-by-id marks); `test_the_cli_contract_gives_each_registered_view_its_fields_in_order` checks field order against the `members` paragraph of `docs/cli-contract.md`, so 11.1's contract entry lists `origin` and `checkouts` in the model's order
  - [ ] `tests/operations/test_list_members.py`: checkouts on two machines both listed, `path` and `wake_command` from the calling machine's first-added checkout; no-checkout and named-by-id members marked; the four `list` subjects work with a `cf` stub that fails if called
  - [ ] Success: checks pass

**Commit**: `feat: show names, origins and checkouts in results and list members`

## 12. The `runs` document (D11; effort 4)

- [ ] **12.1 `operations/runs_document.py` and `operations/run_gather.py`**
  - [ ] `RUNS_DOCUMENT_MAX_BYTES: Final = 768 * 1024`. Plain models: each open run as listed, its directory lookup (missing, project id, not a project, or failure text), a paused run's run-file facts or read problem and newest calls-log line with read problems, completed runs as id and status, left-out counts per kind, or instead of all of it the listing's problem text. A builder adding paused runs, then other open runs, then completed ones, while the encoded document stays under the limit; `parse_runs(value)`, raising `CallRefused(MALFORMED_CALL, ...)` when missing or unparseable. Imports nothing from `upstream`
  - [ ] Tests, `tests/operations/test_runs_document.py`: an over-limit document is cut with paused runs kept first and counts per kind; round-trip; `parse_runs` refuses missing and bad values
  - [ ] `RUNS_GATHER_SECONDS: Final = 60.0`. `gather_runs(*, list_runs, run, runs_dir, calls_dir, clock) -> RunsDocument`, where `list_runs` is the callable `Deps.list_runs` holds, `run` is the `cf` runner `project_of` takes, `runs_dir` and `calls_dir` are the directories `status` passes today to `read_run_facts` and the calls-log reader, and `clock` is a monotonic clock for the time limit. It does: the `sq` listing (`RUN_POLL_TIMEOUT_SECONDS`), one `cf get` per distinct directory sharing `RUNS_GATHER_SECONDS` (then each remaining directory is a failed lookup saying the gather time ran out), the paused runs' run files and calls-log lines; answering scratch directories left out
  - [ ] Tests, `tests/operations/test_run_gather.py`: with an `sq` stub, each kind of run and lookup; with a hanging `cf` stub and a short `RUNS_GATHER_SECONDS`, the remaining directories carry the ran-out text
  - [ ] Success: checks pass
- [ ] **12.2 `status` and `list` read the document**
  - [ ] `status.py`, `status_placement.py`, `status_runs.py`, `status_calls.py` and `list_view.py` take the document and read no disk; a run goes under the member whose checkout is (calling machine, that project id); left-out counts go in `file_problems`; a listing problem raises `SquadronError`. `status_placement.py` drops its `project_of` and `cli_call` imports and `ProjectOf`; `status.py` drops its `project_of` import and call
  - [ ] Named rewrites: `tests/operations/test_status_placement.py` and `test_status_runs.py` build `runs` documents in place of `ProjectOf` stubs and disk fixtures, keeping each case's expected placement
  - [ ] The close sweep closes by the document's completed runs; for a run the document lacks it keeps `run_file_exists` and leaves the question open while the file exists. Paused and calls-log times are matched by equality, never against the store clock. The sweep, pruning and `start_after` run as today, which at this commit is always the no-client-file path; 13.3 adds the `ServedEdges` flag that turns them off on the hub. The message expiry sweep always runs. `wiring` runs `gather_runs` before `status` and `list` and passes the document
  - [ ] `tests/test_message_timing.py`: its docstring and `UNBOUNDED_START_OPERATIONS` say `add`, `rm`, `status` and `list` make a number of `cf` calls no constant bounds. That set is deleted. `rm` makes at most one gather; `add` makes at most one `cf` call and one `git` call (`ORIGIN_READ_TIMEOUT_SECONDS`). `status` and `list` make one `cf get` per distinct run directory, bounded by time and not by count: `RUN_POLL_TIMEOUT_SECONDS` for the listing plus `RUNS_GATHER_SECONDS` plus one call's timeout. A table in the test gives each of the four its worst-case seconds from those constants, the coverage assertion becomes "the message operations in `RUNS` and that table's keys together equal `START_AFTER_OPERATIONS`", and the docstring says so
  - [ ] Tests: placement by checkout on the calling machine (the same project id on another machine is not placed); gather time run out leaves paused runs unplaced; `file_problems` reports left-out runs; with no client file, an open question whose run was cut stays open while its run file exists
  - [ ] Success: checks pass

**Commit**: `feat: gather the machine's runs into a document that status and list read`

## 13. The ten operations through the door (D5, D9, D12; effort 5)

- [ ] **13.1 `wire.protocol`**
  - [ ] `SERVED_OPERATIONS` gains `add`, `rm`, `list`, `status`, `inbox`, `reply`, `cancel`, `changes`, `report_release`; `WRITING_CALLS` gains `add`, `rm`, `reply`, `cancel`, `report_release` (`send` joins both in 13.5, with its wake refusal); `UNKNOWN_ADVICE` gains D12's six entries; the body keys `here` and `runs`. `DOOR_VERSION` unchanged
  - [ ] Tests, `tests/wire/test_protocol.py`: every new writing call has advice; `inbox` and `changes` are not writing calls
  - [ ] Success: checks pass
- [ ] **13.2 `handle_call`'s branch for `CallRefused`**
  - [ ] `hub/calls.py`: before the two existing branches, `CallRefused` rolls back the operation's savepoint, commits the touch, keeps no result, refuses with its code and message, and logs the usual one line
  - [ ] Tests, `tests/hub/test_handle_call.py`: an operation raising `CallRefused` gives that refusal; the touch is committed, nothing else written, no result kept, one line logged
  - [ ] Success: checks pass
- [ ] **13.3 `run_served`: the reads**
  - [ ] `operations/served.py`: parsing of `here` and `runs` with `parse_here` and `parse_runs` when D5's table needs them (else ignored), the acting machine as the calling machine, and `ServedEdges` saying whether a wake may start and the sweep, pruning and `start_after` may run (no on the hub, yes with no client file). Cases: `list`, `status`, `inbox`, `changes`. A hub part needing `config.yaml` reads the hub's; none is `hub_error` naming the file (260 D6). `operations.served` imports nothing from `here`, `naming` or `run_gather`
  - [ ] Tests, `tests/operations/test_served.py`: each of the four on a seeded store with hand-built `here` and `runs`; missing or unparseable `here` or `runs` raises `CallRefused` with `malformed_call`; `list members` ignores a `here` sent
  - [ ] Success: checks pass
- [ ] **13.4 `run_served`: the writes**
  - [ ] Cases: `add`, `rm`, `reply`, `cancel`, `report_release`, each running its hub part
  - [ ] Tests: each of the five on a seeded store; an `add` whose `origin` is not reduced raises `CallRefused` with `malformed_call` and writes nothing
  - [ ] Success: checks pass

**Commit**: `feat: run nine more operations in run_served`

- [ ] **13.5 `run_served`: `send`**
  - [ ] `wire.protocol`: `send` joins `SERVED_OPERATIONS` and `WRITING_CALLS`, and `run_served` gains its case
  - [ ] When wakes may not start, `send`'s hub part checks `can_wake` with the every-machine scope before writing; if due, `CallRefused(NOT_SERVED, ...)` naming the member and each machine with a checkout of it that has a command, saying the door does not start wakes yet. `not_served` is the same code an unserved name gets, on purpose: it means the door does not serve this yet, the message says which case, the client goes by the body and not the 404, and 262 removes the refusal. No new code is added; 260's refusal table says so in its `not_served` row. With no client file the check does not run, and a `CallRefused` raised there is a bug that nothing catches (D12): only `hub/calls.py` has an `except` for it
  - [ ] Tests, through `handle_call`: to a member with a wake command and no live session, `not_served` and nothing written; to one with none, sent. An AST test: no module but `hub/calls.py` catches `CallRefused`
  - [ ] Success: checks pass
- [ ] **13.6 The client side of the ten**
  - [ ] The rule for every placement: it runs the client part (already there since sections 7 to 12), then the hub part in process (no client file) or one door call with `here` and `runs` through `wiring_door`; a `ContextForgeError` is raised before any hub call, and `wiring_results.result_from_document` rebuilds the result
  - [ ] `wiring_registry.py`: `place_add` (through `gather_add`), `place_rm`, `place_list`. Tests: `result_from_document` round-trips the three; with a client file and a failing `cf` stub, a bare `add` raises `ContextForgeError` and 260's in-process hub sees no call
  - [ ] `wiring_messages.py`: `place_message` for `send`, `inbox`, `reply`, `cancel`. Tests: the four round-trip; a failing `cf` stub makes `send` raise with no hub call
  - [ ] `wiring_releases.py` (`changes`, `report_release`) and the `status` case of `wiring._dispatch`, which sends `runs` from `gather_runs`. Tests: the three round-trip; a failing `cf` stub makes `status` raise with no hub call
  - [ ] Success: checks pass
- [ ] **13.7 Import rules**
  - [ ] New test functions in `tests/test_import_boundaries.py` (its tables are per package and check direct imports only). Direct imports: only `operations.here`, `operations.naming` and `operations.run_gather` import the call functions `project_of`, `project_details` or `project_names` (`operations.add_gather` reaches them through `here`); type-only imports (`CFProject`, `CFProjectNotFound`) are allowed, narrowing the design's rule because `working_directory` keeps its `CFProject` shape (record in 17.3); `amoeba.hub` imports nothing from `upstream` directly. Followed through every import, by walking the import graph from the source files: neither `amoeba.hub` nor `operations.served` reaches `operations.here`, `operations.naming`, `operations.run_gather` or `operations.add_gather`, the module holding `open_hub_store` included (5.3)
  - [ ] Success: checks pass

**Commit**: `feat: serve send and place the ten operations through the door`

## 14. `rm-machine` deletes checkouts (D14; effort 1)

- [ ] **14.1 Implementation and test**
  - [ ] `hub/admin.py` `rm_machine`: `delete_checkouts_on_machine` in its one transaction; members stay
  - [ ] `tests/hub/test_admin.py`: the machine's checkouts go, another's remain, and a member left with none is marked in `list members`
  - [ ] Success: checks pass

**Commit**: `feat: delete a retired machine's checkouts`

## 15. The two-machine fixture and cross-machine tests (D15; effort 5)

- [ ] **15.1 `tests/hub_fixture.py` (test infrastructure)**
  - [ ] Each client home gets its own `cf` stub on its `PATH`, so one repo has a different project id on each machine; a helper clones a repo into each client home with `origin` in the SSH form on one and the HTTPS form on the other. The hub's `PATH` still holds no `cf`, `sq` or `git`
  - [ ] Success: 260's fixture tests still pass

**Commit**: `test: give the two-machine fixture per-machine Context Forge and clones`

- [ ] **15.2 `tests/hub/test_chain.py`**
  - [ ] 240's three-repo chain (`tests/cli/test_requests_scenario.py`) by CLI, the repos split across the machines, each step followed by `inbox` from the other; no wake commands, so every `send`, the child with its `parent`, is served
  - [ ] Success: passes in the normal tier
- [ ] **15.3 `tests/hub/test_members_door.py`**, through the door, one test each:
  - [ ] `add` on `alpha` (SSH) then `beta` (HTTPS) gives one member with two checkouts, seen from both, also after a rename in between; the recorded `origin` equals the reduced form sent, port kept
  - [ ] `add` of another repo under a taken name is `name_taken` with both remotes, then `--name` creates it; a second checkout with no `origin` is `no_origin`; `add --project <name> --wake-command x` is refused from either machine
  - [ ] An `add` body with an unreduced `origin` (260's client call directly) is `malformed_call` and writes nothing; a call lacking `here` or `runs` is `malformed_call` with the touch committed
  - [ ] `list members`, `rm <name>`, `rm --checkout` and `add --project` send no `here` and make no `cf` call; the `add --project` and `rm <name>` results have `working_directory` null
  - [ ] Two worktrees of one clone and the clone on the other machine read one request from `inbox`; of two `reply` accepts the first wins and the second is told so
  - [ ] `status` and `list` from a client show its runs under the right members (an `sq` stub in the client home)
  - [ ] A raw `origin` with a password is in no call body, hub log, result, log or store row
  - [ ] A hub started on a `tests/store/schema_11.py` store names each member by its id; then `add --project <id> --name`, `add --attach-to <id>` and `rm <id>` each work
  - [ ] Success: passes
- [ ] **15.4 Load and live**
  - [ ] `tests/load/test_door_load.py` adds `send` and `inbox` callers and keeps both bounds (each call within 2 seconds with 16 clients; median of 100 idle calls under 200 ms). Note the measured figures
  - [ ] The CI gate for the load bounds is the `Tests` step of `.github/workflows/ci.yml`, which runs a bare `uv run pytest` over everything `addopts` in `pyproject.toml` does not ignore (only `tests/live`). `tests/test_ci_gates_load.py` pins it: it parses both files and fails if that step's command names paths or markers that leave `tests/load` out, or if `addopts` ignores or deselects `tests/load`
  - [ ] `tests/live/messaging/test_messaging_live.py`: a CLI-only variant of walkthrough steps 3 to 8 with the repos on two fixture machines, each with its own Context Forge data directory and real `cf` and `git`
  - [ ] Success: the load test passes; the live variant passes with `uv run pytest tests/live/messaging` and the `AMOEBA_LIVE_*` variables set (a bare `uv run pytest` skips `tests/live`), and its result is noted

**Commit**: `test: run the request chain and member registration across two machines`

## 16. `scripts/update_live.py` (D16; effort 2)

A rerun after a killed `update` loses the pre-update backup today (#45): the rerun backs up the already migrated store and, on success, deletes the backup taken before the migration. The design tells the operator to run `update` again, so 16.1 fixes it and the section's commit closes #45.

- [ ] **16.1 Read-back checks, restore on a failed `amoeba list`, and a rerun that keeps the restore point**
  - [ ] `update` takes no new backup when an earlier one is still the restore point: if the newest backup set records `previous` as its commit and its store's schema version is lower than the live store's, an earlier `update` migrated the store and never recorded the install (it was killed). `update` then uses that set as its backup, takes none, and prints that it did. In every other case it takes a backup as today. The deletion of other sets on success is unchanged, and the kept set is the pre-migration one
  - [ ] `Steps` gains `cf_projects` (production: the project ids `cf list projects --json` lists with a path, through `project_details`). `check_store` adds: no member has a null name; every active member in `cf_projects` has a checkout on the `local` machine. Its two new statements are constants in `store/sql.py` (both read `members`, and the scan test allows a `members` statement nowhere else), imported as `sql.SELECT_SCHEMA_VERSION` is, never written in the script. Both are registered in `tests/store/test_members_queried_in_one_place.py`: the null-name read in `OTHER_MEMBER_STATEMENTS`, and the active-members-without-a-local-checkout read in `ACTIVE_READS`, interpolating `{sql.ACTIVE_MEMBER}` as every active read must. `project_details` returns `CfCallFailed`; `cf_projects` raises on it. Everything after the install (`migrate`, `check_store`, `cf_projects`, `list_tools`) runs so that anything it raises is a failed read-back: restore, then `UpdateError` saying what failed
  - [ ] A failed `steps.migrate()` (`subprocess.CalledProcessError`, as `amoeba list` exiting 3 on a `cf` failure raises) restores the store, the config and the previous commit as a failed read-back does, and raises `UpdateError` saying what failed; `backups/installed-commit` is unchanged
  - [ ] The existing `FakeSteps` in `tests/scripts/test_update_live.py` gains `cf_projects`, returning an empty set by default, so the existing tests' read-back is unchanged (their members are seeded with names). Its `_migrate` only runs `Store.open`, which migrates and names nobody, so `FakeSteps` also gains a `naming` option for 16.2: with it, `_migrate` opens the store with `open_state_store` under a `tests/cf_stub.py` stub on `PATH` that lists the schema-11 store's members with paths, as the real `amoeba list` does, and `cf_projects` returns those ids
  - [ ] Success: checks pass
- [ ] **16.2 Tests**
  - [ ] In `tests/scripts/test_update_live.py`, calling `update_live.update` and `update_live.restore` with `FakeSteps` (`main` installs with `uv`, so only the exit-code test below calls it), on a `tests/store/schema_11.py` store in the throwaway home, with the `naming` option: `update` passes both checks; a listed member with no checkout fails the read-back and restores; a `cf_projects` that raises and a `list_tools` that raises each restore the same way; a `migrate` raising `CalledProcessError` restores the schema-11 store, the config and the previous commit with `installed-commit` unchanged; `update` again with a working step succeeds; `restore` then puts the schema-11 store back with the commit that reads it. Every second `update` in a test passes a later `now`, because `take_backup` makes its directory with no `exist_ok`
  - [ ] The killed update (#45): a `migrate` step that migrates and names, then raises `KeyboardInterrupt`, leaves a schema-12 store, one backup and `installed-commit` unchanged. `update` again takes no second backup and succeeds, the one backup left holds the schema-11 store, and `restore` puts it back with the commit that reads it. A rerun after a kill before the migration (store still at 11) takes a new backup as today
  - [ ] The exit code the design requires: `update_live.main` for `update`, with `update_live.PRODUCTION` monkeypatched to the `FakeSteps` (it is bound at import, so patching `_uv_install` and the other step functions would not reach it), `check_checkout` and `previous_commit` monkeypatched to return fixed commits, and `_uv_install` monkeypatched to fail the test if anything calls it, and a `migrate` that raises `CalledProcessError`: it returns 1 and stderr says what failed and which commit was restored
  - [ ] Success: checks pass

**Commit**: `feat: check names and checkouts in the live update and restore on a failed naming`, with `Fixes #45` in the body

## 17. Documents and final checks (D16; effort 2)

- [ ] **17.1 Contract documents**
  - [ ] `docs/store-contract.md`: `members.project_id` as an opaque key never parsed, `name`, `origin`, `checkouts`, and the retired `members.wake_command`
  - [ ] `docs/cli-contract.md`: the prose for `add --name`, `--project` as a name or id, `--attach-to`, `--new-member`, `rm <name>`, `rm --checkout`, the five codes, the added result fields, `working_directory` null when nothing was gathered, `list members`
  - [ ] `docs/mcp-server.md`: the `add` and `rm` tool fields. `docs/program-rules.md` and `docs/rules.md` where they say a member is named by its Context Forge name or id
  - [ ] Success: `tests/test_contract_docs.py` passes
- [ ] **17.2 Full validation**
  - [ ] Run the checks once; failures beyond the 0.2 baseline are fixed in the code
  - [ ] `wc -l` on every source file this slice added or grew: note each, and split by concern any new file over 300 lines; `operations/set_up.py` is no longer than its 344 lines, and the other files in the Context Summary's size note are noted against the figures there
  - [ ] Map each Functional Requirement in the design to the test that proves it, as a note; a requirement with no test gets one before this task is checked
  - [ ] Success: checks pass; the map is complete
- [ ] **17.3 Slice notes**
  - [ ] `user/slices/261-slice.members-by-name.md`: in Verification Walkthrough drop "Draft" and the sentence that the flags do not exist yet, and match what was built; an Implementation Notes entry with the load figures (15.4), the restore command `uv run python scripts/update_live.py restore`, the rerun rule that closed #45 (16.1), the modules beyond Component Structure (`operations/here_document.py`, `operations/name_by_id.py`, `operations/add_gather.py`, `operations/add_member.py`, `store/member_names.py`, any split), the narrowed import rule (13.7), `name_by_id` in its own module where D2's text puts it in `operations.naming` (5.2), the `handle_pause` change the design's Excluded list leaves to 262, needed for `PauseTarget.cf_project_id` (7.7), `not_a_member` for unknown references (9.8), the edits to existing `tests/load` files (7.1, 7.3, 8.1) and the lower send bound, the test edits noted under tasks in the Migration Plan's "Behavior kept" line, and any design text changed under the small-conflict rule
  - [ ] Success: the notes are in the design

**Commit**: `docs: update the contracts and slice notes for members by name`
