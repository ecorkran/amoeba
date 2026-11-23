---
docType: tasks
slice: hub-and-door
project: amoeba
lld: user/slices/260-slice.hub-and-door.md
dependencies:
- 240-slice.requests
projectState: Slices 220 to 244 are merged on main. Store schema version 10 (migrations
  001 to 010), state in ~/.local/state/amoeba, package version 0.2.3. No hub, client
  or network code exists. cryptography, starlette and uvicorn are installed through
  mcp but not declared. This is the first slice of initiative 260 (the hub); 261 to
  264 are designed and build on it.
dateCreated: 20261121
dateUpdated: 20261122
status: complete
turns: 75
promptTokens: 6896383
cachedTokens: 6596218
cacheWriteTokens: 300027
completionTokens: 91937
durationSeconds: 902.1
costUsd: 5.559529
usageRounds: 5
pricedRounds: 5
usageByModel:
  claude-opus-5-5:
    rounds: 5
    costUsd: 5.559527600000001
    completionTokens: 91937
revision_number: 4
---

# Tasks: Hub and Door

## Context Summary

- Working on slice 260 (design: `user/slices/260-slice.hub-and-door.md`; decisions D1 to D19 are cited by number). It delivers `amoeba hub serve` with its admin commands, `amoeba join` and `amoeba leave`, the door serving six operations (`decisions`, `mark_read`, `dismiss`, `retract`, `standing`, `withdraw`), migration 011 (owners, machines, kept results, the closed mark), backups, the hub log, the container files, the two-machine fixture and the load test. Next slice: 261 (members by name).
- Order: sections 0 to 7 are the foundation, which needs no network (dependencies, the `wire` package, migration 011 and the acting machine, the call scope and closed mark, machine and kept-result store functions, paths and the guard, the six operations through `run_served`). Sections 8 to 17 build the hub, the client, the commands, the fixture tests, the container and the documents.
- Test helpers: `tests/hub/in_process_hub.py` (11.3) runs the real app in a thread for unit and client tests; `tests/hub_fixture.py` (15.1) runs `amoeba hub serve` as a subprocess with two joined client homes, and later slices reuse it. Both listen only on `127.0.0.1` (D14 departure: no macOS firewall prompt). Client tests pass short `DoorTimes` so retries take well under a second.
- Paths: a path with no prefix is under `src/amoeba/`. `tests/`, `docs/`, `docker/`, `scripts/` and `project-documents/` are from the repo root, and `user/` means `project-documents/user/`.
- New packages and modules, from the design's Component Structure: `wire/` (`times`, `protocol`, `join_line`, `fingerprint`), `client/` (`errors`, `client_file`, `trust`, `call`, `join`), `hub/` (`hub_config`, `certificate`, `backups`, `hub_log`, `calls`, `app`, `serve`, `admin`), `store/machines.py`, `store/sql_machines.py`, `store/call_results.py`, `operations/served.py`, `wiring_door.py`, `cli/hub_commands.py`, `cli/join_command.py`. Every new package gets an `__init__.py`.
- Files already over ~300 lines take no new logic: `wiring.py` (325) gains only calls into `wiring_door.py`, and `store/sql.py` (488) only has existing insert statements edited (task 3.2); new SQL goes in `store/sql_machines.py`. `store/relocate.py` is 235 lines: if the set-aside code (task 13.2) takes it past ~300, put that code in `store/set_aside.py` and note it under the task. Any new module that passes ~300 lines is split by concern.
- Closed values are defined once and imported: the `wire.times` constants, `DoorTimes`, `SERVED_OPERATIONS`, `WRITING_CALLS`, `HELLO_CALL`, `RefusalCode` and its HTTP status map, `MAX_CALL_BYTES`, the header names, `UNKNOWN_ADVICE`, the machine-name pattern and length (all in `wire.protocol`), `HUB_LOCK_WAITS_PER_CALL` (`hub.calls`), `BACKUP_CHECK_SECONDS` (`hub.backups`), the local machine's name `local` and the owner's name `pm` (`store.machines`), and every file name in D1 (`config/home.py`). No silent fallbacks, no default owner or machine.
- New errors and where they live. Each one named here joins `OPERATIONAL_ERRORS` in `wiring.py` when it is created, unless it is already a subclass of a member. Task 10.1a moves today's five members into `operations/errors.py` as `OPERATION_ERRORS`, which the hub imports, and `wiring`'s tuple becomes those five plus the door's errors:
  - `JoinError` (`wire.join_line`): a malformed join line, the fingerprint mismatch in `join`, and every refusal in D4's failure table (a hub home, a local store without the flag, the hand-placed pair, `--address` with no client file). Defined in `wire` so the parser, `client.join` and `wiring_door` share it. Always exit 3; `join` and `leave` have no exit 1.
  - `ClientFileError`, `HubUnreachableError`, `HubCertificateError`, `HubRefusedError` (`client.errors`, imported by `client_file`, `trust`, `call` and `join`, so `trust` and `call` do not import each other). Record the added `client/errors.py` in the design under 17.3.
  - `NotServedError` (`wiring_door`).
  - `LocalStoreClosedError`, `NoActingMachineError`, `HubHomeError` and `HubStoreMissingError` (`store/errors.py`): all `StoreError` subclasses, so already covered. `HubHomeError` is raised by the local opener in a hub home (D2); `HubStoreMissingError` by `open_hub_store` and by a backup when the store file is missing (D12, D15).
  - `HubConfigError` (`hub.hub_config`): a `ConfigError` subclass.
  - `HubStartError` and `BackupError` (`hub/`): reported by `amoeba hub serve` (exit 3) and `amoeba hub backup`. They do not cross `wiring`.
- Import rules, added to `tests/test_import_boundaries.py` in the task that creates each package: `wire` imports no other `amoeba` package. `client` imports nothing from `store`, `hub` or `upstream`. `hub` imports nothing from `client`, `upstream`, `cli`, `mcp` or any `wiring*` module. The existing direction `cli/mcp → wiring → operations → store, upstream` holds, and `operations` may import `client.client_file` (task 6.3).
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. "Checks pass" means all four, with no failure beyond the baseline noted in 0.2.
- Tests use the autouse `AMOEBA_HOME` fixture, `tests/store/seed.py`, `tests/user_configs.py`, `tests/fault_injection.py` (`fail_on_statement`) and a settable clock. Destructive SQL runs only against throwaway stores. No sample token, fingerprint, hash or timestamp sits near a value an agent must fetch (hallucination-trap rule), in tests, docs or messages.
- `tests/test_contract_docs.py` requires every new table, column, flag and config key in the contract docs, so each task that adds one adds its contract entry then. Task 17.1 writes the prose.
- Existing tests: no existing assertion changes except where a task names it (the schema-version pins in 2.1, the mechanical acting-machine change in 3.4, the `decisions` and `standing` call sites in 7.1 and 7.2, and the raw test inserts that bind `owner_id` in 3.4). If any other existing test fails, fix the new code, not the test. The owner triggers are never weakened to make a test pass.
- Production state: no task writes the live store or config. The live migration rides the next release through `scripts/update_live.py update` (D19), so this file has no Phase 7 hand-off.
- Work on branch `260-slice.hub-and-door` (created in 0.2). Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.

## 0. Setup (effort 1)

- [x] **0.1 Target and prerequisites**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty. `git checkout {target}`. The design and this task file are committed there, with no other uncommitted change
  - [x] Confirm: `store/schema/` holds `001` to `010`, and `EXPECTED_SCHEMA_VERSION` in `store/migrations.py` is 10; `operations/` has `decisions.py`, `mark_read.py`, `dismiss.py`, `retract.py`, `standing.py`, `withdraw.py`; `operations/state_move.py` has `open_state_store` and `prepare_state_home`; `tests/test_store_opened_only_by_state_move.py` and `tests/test_import_boundaries.py` exist; `uv.lock` lists `cryptography`, `starlette` and `uvicorn`. If any is missing, write `BLOCKED: <what>` under this task and stop
  - [x] Note the locked versions of `cryptography`, `starlette` and `uvicorn`, each read from its own entry in `uv.lock`. Compare the `uvicorn` version with the version D14 names in its stalled-peer reasoning; if the major or minor version differs, note that task 11.2b must recheck that reasoning
  - [x] Success: the target is checked out and clean; a note under this task gives the target and the three versions
  Note: Target is `main` (integration_branch empty). Locked versions from uv.lock: cryptography 50.0.2, starlette 1.10.0, uvicorn 0.54.0. uvicorn 0.54 matches D14's version, so 11.2b needs no recheck of the stalled-peer reasoning.
- [x] **0.2 Branch and baseline**
  - [x] `git checkout -b 260-slice.hub-and-door {target}`; if the branch exists, `git checkout 260-slice.hub-and-door`
  - [x] Run the checks once and note the baseline. Failures present before this slice are listed by test name and not fixed
  - [x] Success: `git branch --show-current` prints `260-slice.hub-and-door`; a note under this task gives the baseline result
  Note: Branch `260-slice.hub-and-door` already existed and was checked out. Baseline: ruff format, ruff check, pyright clean; pytest 4261 passed, no failures (full run takes about 4.5 minutes).
- [x] **0.3 Declare the three dependencies**
  - [x] `pyproject.toml`: add `cryptography`, `starlette` and `uvicorn` to `dependencies`, each with a lower bound at the locked version and an upper bound below the next major (for a `0.x` package such as `uvicorn`, below the next minor of the version read in 0.1), in the style of the existing entries
  - [x] Run `uv lock`. It must add no new package (compare the package list before and after)
  - [x] Success: `uv lock` changed only the root package's declared dependencies; checks pass
  Note: pyproject.toml now declares cryptography>=50.0.2,<51, starlette>=1.10.0,<2, uvicorn>=0.54.0,<0.55; `uv lock` added only those three entries to the root package's dependencies, no new package (package-name lists identical before and after). Checks pass (4261 passed).

**Commit**: `chore: declare cryptography, starlette and uvicorn as direct dependencies`

## 1. The `wire` package (D3, D6, D7, D9, D10, D11; effort 2)

- [x] **1.1 `wire/times.py`**
  - [x] The seven constants of D7's table, each `Final`, with `CALL_BOUND_SECONDS` computed as `RETRY_SECONDS + CONNECT_SECONDS + READ_SECONDS`, not written as 43
  - [x] `DoorTimes`, a frozen dataclass of connect, read, retry and retry-pause seconds, whose defaults are those constants (D7: tests pass shorter ones; there is no setting)
  - [x] Success: pyright clean; the module imports only the standard library
- [x] **1.2 `wire/protocol.py`**
  - [x] `SERVED_OPERATIONS`: the six names as plain strings (D11). `HELLO_CALL = "hello"`, outside `SERVED_OPERATIONS` and with no `OperationName`; its request document is `{}` and its result document is `{"machine": <name>}`, with the key name a constant (D6). `WRITING_CALLS`: the five writing names (D9)
  - [x] `RefusalCode` enum with the seven codes of D6, and one mapping from code to HTTP status as D6's table gives it
  - [x] `MAX_CALL_BYTES` (1 MiB). Header-name constants: `Authorization`, `Amoeba-Door-Version`, `Amoeba-Client-Version`, `Amoeba-Call-Id`. The request body key `document`
  - [x] The reply shapes: build a done reply and a refused reply, and `parse_reply(body: bytes)` that validates the body against the two Pydantic reply models and returns a typed done or refused reply, or `None` when the body is not a reply (D6: anything else counts as no reply; the status is never read)
  - [x] `UNKNOWN_ADVICE`: operation name to advice text, one entry per writing call, worded as D10's table
  - [x] The machine-name rule (D3): pattern `[a-z0-9][a-z0-9._-]*`, at most 64 characters, and `is_machine_name(text)`
  - [x] Success: pyright clean; imports only the standard library and `pydantic`
- [x] **1.3 `wire/fingerprint.py` and `wire/join_line.py`**
  - [x] `fingerprint(pem_or_der)`: SHA-256 of the certificate's DER bytes, lower-case hex. `normalize_fingerprint(text)`: accepts upper case and colons and returns the same lower-case hex
  - [x] `JoinError(Exception)`. `JoinLine` (address, fingerprint, token); `format_join_line(...)` writes `<address>,<fingerprint>,<token>`; `parse_join_line(text)` strips surrounding whitespace and quotes, and on the wrong number of fields raises `JoinError` saying what a join line looks like, using field names, never the token's value (D3). Join `JoinError` to `OPERATIONAL_ERRORS` in `wiring.py`
  - [x] Success: pyright clean; imports only the standard library

  Note: `tests/test_wiring.py::test_the_operational_errors_are_the_ones_the_cli_maps_to_exit_three` (was `..._are_the_five_...`) pinned the five errors exactly; under the small-conflict rule its expected set now also holds `JoinError`. Each later task that joins an error to `OPERATIONAL_ERRORS` adds it to that set.

- [x] **1.4 `wire` tests**
  - [x] `tests/wire/test_times.py`: `CALL_RESULT_LIFETIME_SECONDS > CALL_BOUND_SECONDS`; `(DOOR_VERSION, CONNECT_SECONDS, READ_SECONDS, RETRY_SECONDS, RETRY_PAUSE_SECONDS, CALL_BOUND_SECONDS, CALL_RESULT_LIFETIME_SECONDS)` equals a pinned tuple; `DoorTimes()` equals the constants. (The relation with `HUB_LOCK_WAITS_PER_CALL` is tested in task 10.2, where that constant is created)
  - [x] `tests/wire/test_protocol.py`: each served name is an `OperationName` value; `WRITING_CALLS` is a subset of `SERVED_OPERATIONS` and `decisions` is not in it; every writing call has an `UNKNOWN_ADVICE` entry; every `RefusalCode` has a status; both reply shapes round-trip through `parse_reply`; non-JSON, JSON without `outcome`, and an unknown outcome each parse to `None`; machine names: valid, upper case, leading `-`, 65 characters
  - [x] `tests/wire/test_join_line.py`: format and parse round-trip; whitespace and quotes stripped; two and four fields each raise `JoinError` whose text does not contain the token given; a fingerprint with colons and upper case normalizes; the fingerprint of a fixed test certificate equals `hashlib.sha256` of its DER bytes
  - [x] `tests/test_import_boundaries.py`: `wire` imports no other `amoeba` package
  - [x] Success: checks pass
  Note: `tests/wire/test_times.py` was missing from the section 1 commit (a failed command in that step meant it was never written); it is written in the section 10 commit, with the 10.2 relation test added to it.

**Commit**: `feat: add the wire package with the door version, times and call shapes`

## 2. Migration 011 (D12; effort 2)

Sections 2 and 3 commit together: once migration 011 adds its triggers, every record insert fails until task 3.2 binds the owner.

- [x] **2.1 `store/schema/011_hub_and_door.sql`**
  - [x] `owners` (`owner_id` integer key, `name` unique, `created_at`), with one row inserted, named `pm`
  - [x] `machines` (`machine_id` integer key, `name` unique, `owner_id` not null referencing `owners`, `token_hash` unique and nullable, `created_at`, `last_called_at`, `client_version`)
  - [x] `call_results` (`machine_id` referencing `machines`, `call_id`, `operation`, `request_hash`, `reply`, `recorded_at`), key `(machine_id, call_id)`, and an index on `recorded_at`
  - [x] `closed_mark` (`hub_address`, `closed_at`), held to at most one row by a fixed key column with a check constraint; empty after the migration
  - [x] `owner_id`, nullable, referencing `owners`, on the twelve tables of D12; each set to the one owner on every existing row; a `BEFORE INSERT` trigger on each that aborts when `owner_id` is null, naming the table
  - [x] `sessions.machine_id`, nullable, referencing `machines`, with the same kind of trigger. Existing session rows keep a null machine (D12, Sessions)
  - [x] The migration only adds. `EXPECTED_SCHEMA_VERSION` becomes 11. Update the existing tests that pin version 10 and now fail, changing only the version number: run `uv run pytest tests/store -q` and take only the failures whose assertion compares the schema version (11 found where 10 was expected). Leave every insert failure from the new triggers for 3.2 to 3.4. Also `tests/test_contract_docs.py`'s table-count pin, which becomes 18 with the four new tables
  - [x] Store contract: the four tables, `owner_id`, `sessions.machine_id` and the triggers in `docs/store-contract.md`, enough for `tests/test_contract_docs.py`
  - [x] Success: a fresh store migrates to 11
  Note: No existing assertion compared the schema version, so none changed; `tests/test_contract_docs.py` table-count pin is now 18. Store contract: tables, owner_id, sessions.machine_id and triggers are in docs/store-contract.md, including a new `ownership` reason line that `tests/store/test_schema_holds_no_mirrored_state.py` pins (new `ownership` entry in its COLUMN_REASONS).
- [x] **2.2 Migration tests**
  - [x] `tests/store/test_migration_011.py`, building its schema-10 store the way `tests/store/test_migration_010.py` builds its schema-9 store, with one row in each of the twelve tables: after the migration `owners` holds one row named `pm`; every existing row's `owner_id` is that owner; row counts are unchanged; `machines` and `closed_mark` are empty; a raw insert with a null `owner_id` into each of the twelve tables fails, and the same for `sessions.machine_id`
  - [x] Success: this file's tests pass. The full suite is expected to fail on record inserts until 3.2 (no commit here)

## 3. The acting machine (D12; effort 4)

- [x] **3.1 `store/machines.py` and `store/sql_machines.py`, first part**
  - [x] `LOCAL_MACHINE_NAME = "local"` and the owner name constant. `ActingMachine` (frozen: `machine_id`, `owner_id`)
  - [x] `the_owner(transaction)`: the owner id; raises `StoreError` unless `owners` holds exactly one row
  - [x] `store/errors.py`: `NoActingMachineError(StoreError)`, saying the store has no acting machine set and which table the insert was for
  - [x] `Store.act_as(machine: ActingMachine)` stores it; each `Transaction` the store opens carries it; `Transaction.acting()` returns it or raises `NoActingMachineError`
  - [x] `act_as_local(store)`: in one write, find the machine named `local` or create it with the one owner and no token, then `store.act_as(...)` it. This is the helper `open_state_store` and the test fixtures share
  - [x] SQL as module constants in `store/sql_machines.py`; values bind with `?`
  - [x] Success: pyright clean
  Note: `Transaction.acting(table)` takes the table name so the NoActingMachineError message can name it. `act_as_local(store)` does one read and writes only when `local` is missing (re-checked under the write lock), so opening a store never waits for the write lock; the machine's created_at is `datetime.now(UTC)`. `LocalStoreClosedError`, `HubHomeError` and `HubStoreMissingError` were added to store/errors.py here beside `NoActingMachineError`; tasks 4.2 and 6.3 use them.
- [x] **3.2 Bind the owner and the machine on every record insert**
  - [x] Every insert into the twelve tables binds `owner_id` from `transaction.acting()`, and the session insert also binds `machine_id`. Find them with `grep -rnE "INSERT INTO (programs|members|dependency_pairs|releases|questions|answers|standing_answers|messages|deliveries|message_rejections|sessions|wakes)\b" src/amoeba`; if it finds no statement, stop and report it. No operation's signature changes (D12)
  - [x] Success: pyright clean
- [x] **3.3 `open_state_store` acts as `local`**
  - [x] `operations/state_move.py`: after `Store.open`, call `act_as_local(store)`. `state_move.py` stays the only caller of `Store.open`
  - [x] Success: `tests/test_store_opened_only_by_state_move.py` passes
- [x] **3.4 Store fixtures set the acting machine (mechanical)**
  - [x] Add `tests/store_open.py` with `open_local_store(path)`: `Store.open(path)` then `act_as_local(store)`
  - [x] Replace `Store.open(` with `open_local_store(` in every test module that `grep -rl --include='*.py' "Store.open" tests` lists (if it lists none, stop and report it), except `tests/store/test_schema_holds_no_mirrored_state.py`, which inserts no records and keeps `Store.open` (D12: every test that opens a store and inserts records sets the acting machine with the shared helper). No assertion changes
  - [x] Raw SQL inserts in tests into the twelve tables at schema 11 or later bind `owner_id` (and `machine_id` for `sessions`), using `the_owner` and the `local` machine. Find them with the 3.2 grep run over `tests/`, `tests/live` included; if it finds no insert, stop and report it. Inserts in `tests/store/test_migration_0*.py` and `tests/operations/test_state_move_directories.py` that run before migration 011 stay as they are; confirm each one does
  - [x] Success: the full suite is back to the baseline from 0.2
  Note: Small-conflict changes to existing tests, assertions unchanged in intent: `tests/store/test_migration_006.py` fixture and `test_migration_007.py` column test migrate only through their own version (later migrations add the owner their raw inserts omit); `tests/store/test_schema.py` table set gained the four new tables; `tests/store/test_store.py` keeps `Store.open` for its busy-timeout and corrupt-file tests and uses `open_local_store` only where it inserts records; `tests/store/test_migrations.py` raw inserts bind owner_id; raw inserts in other tests bind it with the subquery `(SELECT owner_id FROM owners)` (and the `local` machine id for sessions) instead of calling `the_owner`; `tests/store/seed.py` binds the owner for its five inserts; `tests/operations/test_state_move_directories.py` `INSERT_LATE_ANSWER` binds the owner because its legacy store is at the current schema. 112 test modules now call `open_local_store` (tests/store_open.py).
- [x] **3.5 Acting-machine tests**
  - [x] `tests/store/test_acting_machine.py`: with no acting machine (a store opened with plain `Store.open`, not `open_local_store`), an insert into each of the twelve tables through its store function raises `NoActingMachineError` and writes nothing; `open_state_store` creates `local` once (a second open adds no row) with the one owner and no token; records written through it carry that owner, and a session row carries `local`'s `machine_id`; `the_owner` fails with zero rows and with two
  - [x] Same file (D12): read the SQL constants of `store/sql*.py` and assert that every `INSERT INTO` one of the twelve record tables names `owner_id`, and that the test found at least one statement per table, so the statement count is not kept by hand
  - [x] Success: checks pass

**Commit**: `feat: add migration 011 with owners, machines and the acting machine`

## 4. The call scope and the closed mark (D4, D8; effort 3)

- [x] **4.1 `Store.call_scope()`**
  - [x] A context manager that opens one `BEGIN IMMEDIATE`, yields a `Transaction`, commits on a normal exit and rolls back on an exception
  - [x] Inside it, `write()` and `read()` become savepoints: `SAVEPOINT`, `RELEASE` on a normal exit, `ROLLBACK TO` then `RELEASE` on an exception, which re-raises. Use one fixed savepoint name as a constant (SQLite uses the most recent savepoint of that name, so nesting needs no runtime names, and no SQL is built from a runtime value)
  - [x] Entering `call_scope` inside a `call_scope` raises `RuntimeError` (a programming error). Outside a call scope, `write()` and `read()` behave as today apart from 4.2
  - [x] Success: pyright clean
- [x] **4.2 The closed mark**
  - [x] `store/errors.py`: `LocalStoreClosedError(StoreError)`, whose message names the hub's address and where the store went. When no client file exists (a `join` stopped before the rename, D4) it also says to run `amoeba leave` or the same `join` again
  - [x] Every write transaction, including `call_scope`, reads `closed_mark` right after `BEGIN IMMEDIATE`; if a row is there it rolls back and raises `LocalStoreClosedError` naming its `hub_address`
  - [x] `write_closed_mark(transaction, hub_address, now)` in `store/machines.py`, and a SQL constant for deleting the row (used on a plain connection by task 13.2)
  - [x] Success: pyright clean
  Note: The `LocalStoreClosedError` message always names both `amoeba leave` and the same `amoeba join` (the store layer cannot see the client file, so it does not vary the text by whether one exists); `store/sql_scope.py` holds the fixed savepoint SQL.
- [x] **4.3 Call-scope and closed-mark tests**
  - [x] `tests/store/test_call_scope.py`, with plain store functions: a write in the scope then a nested `write()` that raises keeps the first write and drops the nested one, once committed; two nested levels roll back to the right point; an exception out of the scope leaves nothing; a nested `call_scope` raises `RuntimeError`. (The five writing operations under fault injection are tested in 7.6)
  - [x] `tests/store/test_closed_mark.py`: with the mark written, a write raises `LocalStoreClosedError` naming the address and writes nothing; reads still work; a second connection opened before the mark was written fails its next write the same way; with no mark, writes are unchanged
  - [x] Success: checks pass

**Commit**: `feat: add the store call scope and the closed mark`

## 5. Machine and kept-result store functions (D8, D9, D13; effort 3)

- [x] **5.1 Machines, second part (`store/machines.py`)**
  - [x] `hash_token(token)`: SHA-256 hex (D3). The store keeps only this
  - [x] `invite_machine(transaction, name, token_hash, now)`: creates the machine with the one owner, or replaces an existing machine's `token_hash`. Returns whether it was new
  - [x] `machine_for_token(transaction, token_hash)`: a plain read, for step 1 of D8. `touch_machine(transaction, token_hash, now, client_version)`: sets `last_called_at` and `client_version` and returns the `ActingMachine`, or `None` when no row has that hash
  - [x] `list_machines(transaction)`: name, whether it has a token, `last_called_at`, `client_version`, ordered by name
  - [x] `remove_machine(transaction, name)`: deletes the machine's session rows, its kept results and the machine, in the caller's one transaction; returns `False` when there is no such machine. A short comment says 261 and 262 add to this function (D13)
  - [x] Success: pyright clean
  Note: `machine_for_token` and `touch_machine` return an `ActingMachine` (machine id and owner id); the SQL for kept results is in `store/sql_call_results.py`.
- [x] **5.2 `store/call_results.py`**
  - [x] `KeptResult` (operation, request hash, reply). `find_kept(transaction, machine_id, call_id)`, `keep(transaction, machine_id, call_id, operation, request_hash, reply, now)`, `delete_expired(transaction, now, lifetime_seconds)` (one statement using the `recorded_at` index)
  - [x] Success: pyright clean
- [x] **5.3 Tests**
  - [x] `tests/store/test_machines.py`: a new invite creates the machine with the owner; a re-invite replaces the hash, so the old hash finds nothing; two machines cannot share a name; `touch_machine` sets both fields and returns `None` for an unknown hash; `list_machines` shows a machine with no token; `remove_machine` deletes its sessions and kept results and leaves another machine's, and returns `False` for an unknown name
  - [x] `tests/store/test_call_results.py`: keep then find; the same call id under two machines is two rows; `delete_expired` removes only rows older than the lifetime; `EXPLAIN QUERY PLAN` for the delete uses the index
  - [x] Success: checks pass

**Commit**: `feat: add machine and kept-result store functions`

## 6. Paths, the client file, the guard and the two openers (D1, D2, D3, D12; effort 3)

- [x] **6.1 `config/home.py` paths**
  - [x] File-name constants and path functions for D1: `client.yaml` and `hub.yaml` in the config home; `pinned-hub-cert.pem`, `hub-cert.pem`, `hub-key.pem` in the state home; `logs/hub/hub.log` under the logs directory. `home.py` stays the only reader of `AMOEBA_HOME`
  - [x] `StateLayout` gains `client_file`
  - [x] Success: pyright clean; existing `tests/config` tests pass
  Note: `StateLayout` gained six fields, not one: `client_file` and `hub_file` (config home), `pinned_cert`, `hub_cert`, `hub_key`, `hub_log` (state home), so the openers and the hub never read `AMOEBA_HOME` themselves; the five test sites that build a `StateLayout` by hand were updated. `config/home.py` also has the zero-argument path functions. New test `tests/config/test_hub_paths.py`.
- [x] **6.2 `client/client_file.py`**
  - [x] Create `client/errors.py` with the four client errors of the Context Summary (`ClientFileError`, `HubUnreachableError`, `HubCertificateError`, `HubRefusedError`)
  - [x] `ClientFile` (`address`, `machine`, `token`). a Pydantic model with `extra="forbid"`, as `config/user_config.py` does. `write_client_file(path, client_file)`: writes the fixed temporary name `client.yaml.tmp` in the same directory, mode `0600`, then renames; a crash leaves at most that one file, which the next write replaces
  - [x] `load_client_file(path, pinned_cert_path)` raises `ClientFileError` naming the file when: the file is readable by anyone but the owner (message gives the `chmod 600` command); a key is missing or unknown (names the key); the saved certificate is missing or unreadable (says to run `amoeba join` again with a new line from `amoeba hub invite`)
  - [x] `read_client_address(path)`: the `address` key alone, for messages that name the hub (6.3). It never fails on a missing certificate
  - [x] Join `ClientFileError` to `OPERATIONAL_ERRORS`; add the `client` import rule to `tests/test_import_boundaries.py`
  - [x] Success: pyright clean
  Note: `ClientFileError` joined `OPERATIONAL_ERRORS`; its expected set in `tests/test_wiring.py` was extended; the `client` import rule is in `tests/test_import_boundaries.py`.
- [x] **6.3 The guard and the two openers**
  - [x] `open_state_store` and `prepare_state_home` raise `LocalStoreClosedError` naming the hub's address (from `read_client_address`) when `layout.client_file` exists, before touching any store or directory
  - [x] `open_state_store` also refuses, as its first step after the client-file guard and before its `prepare_state_home` call (which can move a legacy store into the state home), when no store exists at the store path but a set-aside store does: the message names the set-aside file and says to run `amoeba leave`. The set-aside file-name marker (`amoeba.sqlite3.set-aside-`) is a constant beside the store functions that task 13.2 builds, created here
  - [x] `open_hub_store(layout, *, create=False)`: the same guard, then, when the store file is missing and `create` is false, raise `HubStoreMissingError` before `Store.open` is called and before any directory is made; the message gives the path and says `amoeba hub serve` makes the store on a first start. Otherwise `Store.open`, with no machine created and no `act_as` (D12). Only step 7 of a first start passes `create=True` (11.2a)
  - [x] The hub-home check (D1, D2): `open_state_store` and `prepare_state_home` raise `HubHomeError` when the config home holds `hub.yaml`, checked right after the client-file guard and before any store or directory is touched. `open_hub_store` does not make this check. Add `HubHomeError` and `HubStoreMissingError` to `store/errors.py`
  - [x] Success: `tests/test_store_opened_only_by_state_move.py` passes
  Note: The set-aside file-name marker (`.set-aside-`, with `PARTIAL_SUFFIX` and `set_aside_stores`) is in the new `store/set_aside.py`, which task 13.2 extends (the size rule in the Context Summary). The guards are `refuse_joined_or_hub_home` and `refuse_if_joined` in `operations/state_move.py`; `open_state_store` runs the client-file guard, the hub-home check, the set-aside-without-store check, then `prepare_state_home`.
- [x] **6.4 Tests**
  - [x] `tests/client/test_client_file.py`: write then load round-trips and the file is `0600`; mode `0640` fails with the `chmod 600` text; a missing key and an unknown key each fail naming the key; a missing certificate fails naming it and saying to join again; `read_client_address` works with no certificate
  - [x] `tests/operations/test_store_guard.py`: with a client file present, both openers and `prepare_state_home` raise `LocalStoreClosedError` naming the address, and the state home holds no new file afterwards; a set-aside store with no store makes `open_state_store` refuse naming `amoeba leave`, creating nothing and leaving a legacy store in the legacy home unmoved; `open_hub_store` on a fresh home raises `HubStoreMissingError` and the home's file tree is unchanged, and with `create=True` it makes a store with no `local` machine; with `hub.yaml` in the config home, `open_state_store` and `prepare_state_home` raise `HubHomeError`, an existing store's rows are unchanged and it gains no `local` machine, and `open_hub_store` still opens it
  - [x] Success: checks pass

**Commit**: `feat: add the client file, the local-store guard and the hub store opener`

## 7. The six served operations through `run_served` (D11; effort 3)

- [x] **7.1 `decisions` takes a names reader**
  - [x] `operations/decisions.py`: `decisions(store, document, *, names)` where `names` is handed the listed member ids and returns each one's name, in place of `Deps`. Update its tests' call sites only
  - [x] Success: existing `decisions` tests pass with call-site changes alone
  Note: `decisions` takes `names: NamesReader` (a callable handed the listed member ids, returning a mapping id to name). The `cf`-backed readers are in the new `operations/cf_readers.py` (`cf_names(deps)`, `cf_member_resolver(run)`); the tests' call sites use them.
- [x] **7.2 `standing` takes a member resolver**
  - [x] `operations/standing.py`: takes a resolver from a member reference to a member id or `None` (which is `no_such_member`, as today), in place of the `cf` runner. Update its tests' call sites only
  - [x] Success: existing `standing` tests pass with call-site changes alone
  Note: `standing` takes `resolve_member: MemberResolver` (reference to member id or None); the local resolver raises `ContextForgeError` as before.
- [x] **7.3 `operations/served.py`**
  - [x] `ServedEdges`, a frozen dataclass: the clock, a config loader, the names reader, the member resolver
  - [x] `run_served(name, store, document, edges)` runs any of the six and returns its typed result; any other name raises `ValueError`. The config loader is called only by operations that need config
  - [x] `id_names(member_ids)` (each member named by its id) and `id_resolver(store)` (a reference that is an existing member id resolves to it; any other text is `None`): the hub's two readers until 261 (D11)
  - [x] Success: pyright clean
  Note: `run_served` dispatches through the dict `operations.served.SERVED_RUNNERS` (name to runner), so task 10.2's stub test can add a seventh entry; `operations.served.result_document` is the one JSON conversion, which `wiring_results.result_document` uses for everything but `ListResult`.
- [x] **7.4 The local way goes through `run_served`**
  - [x] `wiring_door.py` (new): `local_served_edges(layout, load_config, readers, clock)` builds `ServedEdges` from what `wiring` passes in: today's `cf`-backed readers, the config loader and the clock. `wiring_door` imports nothing from `wiring`, which imports it (13.1), so there is no import cycle
  - [x] `wiring._dispatch`: the six cases become one call to `run_served` with those edges; `wiring.py` gains no other logic
  - [x] Success: the full suite is at baseline; with no client file, behavior is unchanged
  Note: `wiring_door.local_served_edges(deps, load_config)` takes the `Deps` that `wiring` already builds, not `layout, load_config, readers, clock`, which `Deps` already carries. `wiring_standing.py` was deleted: `run_served` replaced its one function. Small-conflict test changes: patch targets moved with the code, so `tests/cli/test_standing_cli.py` patches `cf_readers.project_of`, and `tests/mcp_server/test_in_process.py`, `tests/test_wiring.py` and `tests/cli/test_legacy_move_cli.py` patch `served.mark_read` and `served.decisions` instead of the `wiring` names.
- [x] **7.5 `wiring_results.result_from_document(name, document)`**
  - [x] Rebuilds the typed result of any of the six from its `result_document` form; any other name raises `ValueError`
  - [x] Success: pyright clean
- [x] **7.6 Tests**
  - [x] `tests/operations/test_served.py`: `run_served` runs each of the six on a seeded store with stub edges; an unserved name raises `ValueError`; with `id_names` and `id_resolver`, `decisions` names members by id, `standing --member <id>` for a seeded member is given, and any other reference is `no_such_member`; a `cf` that fails if called proves neither hub reader calls it
  - [x] Each of the five writing operations, run through `run_served` inside `call_scope` with an outer write before it, the operation wrapped in a nested `write()` whose exception the test catches (as `handle_call` will), and `fail_on_statement` failing the operation's last statement: after the scope commits, nothing from the operation is stored and the outer write is. The same for `standing`'s overflow path with no fault injected
  - [x] `tests/test_wiring_results.py` (or the existing results test module): representative results of all six, rejections included, round-trip through `result_document` and `result_from_document` to equal values
  - [x] Success: checks pass
  Note: the fault-injection test patches `Transaction.execute` at class level (the operations open their own nested transactions, so patching one instance would miss them) and finds each operation's last write statement by running it once on a probe store.

**Commit**: `feat: run the six served operations through one function`

## 8. Hub config, certificate and log (D5, D14, D16; effort 2)

- [x] **8.1 `hub/hub_config.py` and the example**
  - [x] `HubConfig`, a Pydantic model with `extra="forbid"` as `config/user_config.py` does, with the eight keys of D14's table. `load_hub_config(path)`: every key required, no default in code, unknown keys refused, each value checked as the table says (`backup_dir` absolute, `backup_hours > 0`, `backups_kept >= 1`, `hub_log_max_bytes >= 1`, `hub_logs_kept >= 2`), every problem reported in one `HubConfigError(ConfigError)` naming the file and each key, as `load_user_config` does
  - [x] `src/amoeba/hub/hub.yaml.example`: all eight keys, `bind` set for the container (all interfaces) and `backup_dir: /backups`, the address an obviously-placeholder host. Add it to the wheel `artifacts` in `pyproject.toml`
  - [x] `docs/config-contract.md`: `hub.yaml` keys and the client file's three keys
  - [x] Success: pyright clean; `tests/test_wheel_contents.py` passes with the example listed in it
  Note: `config/user_config.py`'s two private helpers became public (`read_yaml_document(path, kind=...)` and `validation_problems`) so `hub_config` reuses them instead of copying them; behavior of `load_user_config` is unchanged. `HubConfig` also checks `port` is 1 to 65535, `address` is `host:port` and `bind` is not blank. The contract adds a test, `test_the_config_contract_names_every_hub_and_client_key`, in `tests/test_contract_docs.py`; the new sections are after the `## Example` block so the `config.yaml` example stays the first yaml block under it.
- [x] **8.2 `hub/certificate.py`**
  - [x] `make_certificate(cert_path, key_path)`: EC P-256 key and self-signed certificate via `cryptography`, common name `amoeba-hub`, not-after `9999-12-31T23:59:59Z`; key file `0600`. The key is written first, then the certificate, each through a temporary file and a rename (D14 step 5)
  - [x] `classify_start(has_store, has_cert, has_key, has_backup)` returns a `StartKind` enum with one value per row of D5's table: normal; damaged with a backup (refused); damaged with no backup (new pair beside the store); lost (refused); first start with the pair kept; first start with a lone file replaced; first start. The function is pure, so every combination is tested without files. It names each missing file for the refusals (D5)
  - [x] Success: pyright clean
  Note: `classify_start` returns a `StartDecision(kind, missing)` (the kind is the `StartKind`, `missing` the certificate or key file names not there), so a refusal can name the missing file; `has_backup` is ignored for a store that has both files. `make_certificate` takes a `CertificateHooks(after_key)` fault seam for the stopped-first-start tests in 11.4.
- [x] **8.3 `hub/hub_log.py`**
  - [x] `start_hub_log(path, max_bytes, kept)`: creates the directory, puts one `RotatingFileHandler` (`maxBytes = max_bytes`, `backupCount = kept - 1`) on the root logger, sets the level, returns the handler
  - [x] `refusal_line(time, peer, code, machine)`: the one-line format of D16; never the token, body or document
  - [x] Success: pyright clean
- [x] **8.4 Tests**
  - [x] `tests/hub/test_hub_config.py`: `hub.yaml.example` loads as valid; each key missing, an unknown key, a relative `backup_dir`, `backup_hours: 0`, `backups_kept: 0`, `hub_logs_kept: 1` each fail naming the key; two problems are reported together
  - [x] `tests/hub/test_certificate.py`: the made certificate has the name, P-256 key and far-future end; key file `0600`; `classify_start` is called with all sixteen combinations of its four facts and each returns the `StartKind` of its row in D5's table, and each refusal names the missing file
  - [x] `tests/hub/test_hub_log.py`: writing past `max_bytes` several times leaves at most `kept` files; a `uvicorn.error` and an `asyncio` record land in the file; `refusal_line` holds no token passed to it
  - [x] `tests/test_import_boundaries.py`: the `hub` import rule
  - [x] Success: checks pass
  Note: the `hub` import rule is in `tests/test_import_boundaries.py`.

**Commit**: `feat: add hub config, certificate and rotating log`

## 9. Backups (D15; effort 3)

- [x] **9.1 `hub/backups.py`**
  - [x] `BACKUP_CHECK_SECONDS = 300`. Two kinds: timed (`<backup_dir>/timed/<UTC stamp>/`) and pre-migration (`<backup_dir>/pre-migration/<UTC stamp>-v<version>/`). `backup_dir` is outside the state directory by the design's recorded departure (D1 and Departures: backups must be able to sit on another disk from the store)
  - [x] `take_backup(kind, ...)`: first delete any `.partial-` directory of that kind; write into a new `.partial-` directory the store (SQLite's backup call on its own connection), `hub-cert.pem` and `hub-key.pem`; directories `0700`, files `0600`; rename when complete; then delete that kind's directories beyond the newest `backups_kept`. On failure delete its own partial directory, then raise `BackupError` naming the path and cause
  - [x] One backup at a time (D15): the whole attempt, from deleting a partial directory to the end of rotation, holds an exclusive `fcntl.flock` on `<backup_dir>/.lock`, taken blocking, with the lock file's name a constant. The file is created when missing and never deleted
  - [x] With no store file at the store path, `take_backup` raises `HubStoreMissingError` before it creates a partial directory, and rotates nothing. It opens the store read-only for the copy, so it can never create one (D15)
  - [x] A pre-migration backup, once complete, deletes the other `pre-migration` directories whose name ends in the same `-v<version>`, and only then rotates to `backups_kept` (D15)
  - [x] `timed_backup_due(backup_dir, now, backup_hours)` (raises `BackupError` naming the path when it cannot read `backup_dir`) and `newest_complete_backup(backup_dir)` (either kind, complete directories only, for D5; a `.partial-` directory and the lock file are not backups; raises `BackupError` naming the path when `backup_dir` does not exist or cannot be listed)
  - [x] Success: pyright clean
  Note: Directory names use a microsecond stamp (`%Y%m%dT%H%M%S%fZ`), so ten `amoeba hub backup` runs in one second still get ten names. `timed_backup_due` treats a `backup_dir` that does not exist yet as holding no backup (due), and `take_backup` makes it; one that exists but cannot be read raises `BackupError`. `take_backup` takes a `BackupSource(store_path, cert_path, key_path)` and a `BackupHooks(during_copy)` fault seam (called after the partial directory exists, before the copy); any failure in the write, of whatever type, deletes the attempt's own partial directory before it propagates.
- [x] **9.2 Tests**
  - [x] `tests/hub/test_backups.py`:
    - [x] A backup holds the three files with the modes above and the store copy opens with the same rows; the pre-migration name carries the version
    - [x] Due when none exists or the newest is older than `backup_hours`, not otherwise
    - [x] A failure partway (make the copy raise) leaves no partial directory and raises `BackupError`; a leftover partial from a "crash" is gone after the next attempt; `newest_complete_backup` ignores partial directories
    - [x] After `backups_kept + 2` backups of each kind, each kind holds `backups_kept`
    - [x] A backup taken while another connection holds a write transaction succeeds
    - [x] Two `take_backup` calls started together in two processes (`multiprocessing`, each made slow by a hook in the copy) both complete, each directory holds the three files, and no partial directory is left. A process killed while holding the lock does not stop the next attempt
    - [x] With the store file removed, `take_backup` raises `HubStoreMissingError`, creates no store and no partial directory, and the existing backups are all still there
    - [x] Five pre-migration backups for one version leave one directory for that version, and the directories of two earlier versions are still there
    - [x] `newest_complete_backup` on a missing `backup_dir` raises `BackupError` naming it, and on a directory holding only the lock file and a partial directory finds none
  - [x] Success: checks pass
  Note: `tests/hub/backup_support.py` builds a throwaway hub (store with one program row, certificate and key) for these tests and later ones.

**Commit**: `feat: add hub backups with rotation`

## 10. One call: `hub.calls.handle_call` (D6, D8, D9, D11, D16, D18; effort 4)

- [x] **10.1a `hub/call_refusals.py`: the refusal and logging path**
  - [x] Move today's five operational error types (`AmoebaHomeError`, `ConfigError`, `ContextForgeError`, `SquadronError`, `StoreError`) out of `wiring.OPERATIONAL_ERRORS` into `operations/errors.py` as `OPERATION_ERRORS`. `wiring.OPERATIONAL_ERRORS` becomes `(*OPERATION_ERRORS, <the door's errors added so far>)`, so every existing user of the `wiring` name is unchanged
  - [x] Building a refused reply for a code and message; mapping a raised exception: an `OPERATION_ERRORS` member is `hub_error` with `<ErrorName>: <text>` and one `refusal_line`; anything else is logged with `logger.exception` and refused as `hub_fault` naming the type and the hub log
  - [x] Success: pyright clean; the full suite is at baseline
  Note: `OPERATION_ERRORS` is in `operations/errors.py`; `wiring.OPERATIONAL_ERRORS` is `(*OPERATION_ERRORS, JoinError, ClientFileError)`. `CallReply` (status, body) and the `Refuser` class (builds and logs a refusal for one call; `for_exception` maps an exception to `hub_error` or `hub_fault`) are in `hub/call_refusals.py`.
- [x] **10.1b `hub/calls.py`: one call's steps**
  - [x] `HUB_LOCK_WAITS_PER_CALL = 1`. `DoorHooks` (frozen; `after_commit`, default none) as the fault seam, like `MoveHooks`. A call request value (name, headers, body bytes, peer address) and the reply it returns (status and body bytes)
  - [x] `handle_call(request, *, open_store, clock, load_config, hooks)` follows D8's steps in order: the token lookup as a plain read (miss is `bad_token`); the checks that need no store (door version, headers, body, served list with `hello` allowed, config for `standing`), remembered; then one `call_scope`: touch by token hash (no row is `bad_token`), commit the touch and refuse if a check failed, `delete_expired`, for a writing call look up the kept result (same operation and request hash returns it; otherwise `call_id_reused`), `act_as` the machine, run the operation in a nested `write()` (`hello` returns the machine's name), for a writing call `keep` the reply, commit; then `hooks.after_commit`
  - [x] `hooks.after_commit` is called after the commit and outside the guarantee below, so an exception it raises passes out of `handle_call`. `hub.app` does not catch it, so the client gets no body `parse_reply` accepts (Starlette answers a plain-text 500) and counts it as no reply (D6). This is how the 12.4 repeat test's hook drops a reply: it raises an exception of the test's own. Production passes no hook
  - [x] Apart from that hook, it never raises to the caller: on a raise it rolls back the operation's savepoint, commits the touch, keeps nothing and refuses through 10.1a's mapping. A failure before the scope (the store not opening) goes through the same mapping without the touch. Every refusal writes one `refusal_line`. The run uses `id_names` and `id_resolver` from `operations.served`, the hub's clock and its `config.yaml` loader
  - [x] Success: pyright clean
  Note: `touch_machine` now takes `client_version: str | None` (a call with no version header leaves the stored one), and `store/machines.py` gained `machine_name(transaction, machine_id)`; the hello reply and the log lines use it. `hub.calls.NEEDS_CONFIG` names the served operations whose config is loaded before the scope (`standing`). The operation and its kept result are written inside one savepoint, so a failure in either undoes both.
- [x] **10.2 Tests (no network)**
  - [x] `tests/hub/test_handle_call.py`, on a throwaway hub store with an invited machine:
    - [x] `hello` returns the name; each of the six runs and returns its result document
    - [x] No token and an unknown token are each `bad_token`
    - [x] A wrong door version is `door_version`, and still sets `client_version` and `last_called_at`
    - [x] Bad JSON and an oversized body are each `malformed_call`; an unserved name is `not_served`
    - [x] A reused call id with another body, and with another operation, are each `call_id_reused`
    - [x] A missing `config.yaml` for `standing` is `hub_error`
    - [x] A repeated writing call returns the stored reply and applies once; the same call id from a second machine runs as a new call
    - [x] A kept result older than the lifetime is deleted by the next call; `decisions` keeps nothing
  - [x] `hub_fault`: monkeypatch `run_served` to raise `RuntimeError`; the reply names the type, the traceback is in the log, nothing is stored, and the next call succeeds
  - [x] Failure paths:
    - [x] A token removed between the read and the scope (`remove_machine` called from a monkeypatched token read) is `bad_token`
    - [x] A run with `act_as` skipped fails the first insert with `NoActingMachineError`, refused as `hub_error`
    - [x] An `open_store` that raises `StoreError` is `hub_error`, and one that raises `RuntimeError` is `hub_fault`, each with the machine's `last_called_at` unchanged
    - [x] No log line written by these tests holds the token
  - [x] A seventh operation: monkeypatch a stub name into `SERVED_OPERATIONS` and a stub case into the dispatch `run_served` uses; `handle_call` runs it and returns its result document, with `DOOR_VERSION` and the request and reply shapes unchanged. This proves 261 can serve a new operation by adding to the served list and `run_served`
  - [x] `tests/wire/test_times.py` gains: `READ_SECONDS > HUB_LOCK_WAITS_PER_CALL * BUSY_TIMEOUT_SECONDS`
  - [x] The per-call open is not a second lock wait (D7): with another connection holding `BEGIN IMMEDIATE` on a migrated hub store, `open_hub_store` with a short busy time returns well inside that time and a read through it succeeds
  - [x] `hello` with the body `{"document": {}}` returns `{"machine": <name>}` and keeps no result, and a call named for an unserved `OperationName` is `not_served` (D6, D9). A store file removed before the call is refused as `hub_error` naming `HubStoreMissingError`, and no store file exists afterwards (D5)
  - [x] Success: checks pass
  Note: the stub-operation test adds an entry to `operations.served.SERVED_RUNNERS` and patches `hub.calls.SERVED_OPERATIONS`; shared helpers are `tests/hub/call_support.py` (`HubRig`, `build_rig`, request builder).

**Commit**: `feat: handle one door call as one transaction with kept results`

## 11. The web app and the start sequence (D5, D14, D16; effort 4)

- [x] **11.1 `hub/app.py`**
  - [x] One Starlette route, `POST /call/{name}`. Before reading the body, refuse `malformed_call` when the length header is missing, invalid or over `MAX_CALL_BYTES`. Otherwise read the body and call `handle_call` through `anyio.to_thread.run_sync`. Every reply carries `Amoeba-Door-Version`
  - [x] Success: pyright clean
  Note: `create_app(handle, clock)` takes the call handler (a function of `CallRequest` returning `CallReply`) so `serve` and the in-process helper bind `handle_call` their own way.
- [x] **11.2a `hub/start.py`: prepare (D14 steps 2 to 8)**
  - [x] Steps 2 to 8 of D14's start sequence (step 1, the guard, is the first line of every hub command, task 14.2), in their own module so tests run them without serving. It returns the bound socket and what serving needs. The design's Component Structure lists only `serve`; record the added `start` module in the design under 17.3
  - [x] Step 3 binds the socket before anything is written. Step 4 without `--from-backup` refuses when the state directory holds `restore.partial/`, saying a restore did not finish and giving the command; with the flag it calls 11.2c's restore. Step 5 gathers the four facts and acts on `classify_start` (8.2), one branch per `StartKind`: the two refusals name the missing file or the newest backup and give both ways on as D5's table words them; the damaged-with-no-backup start deletes a lone file, makes a new pair beside the store and writes one line to stderr, and later to the hub log, saying the certificate is new and every machine must be invited and joined again; the two unfinished first starts keep a full pair or replace a lone file. `has_backup` is read only when the kind is not already decided by a store with both files, and a `backup_dir` that cannot be listed stops the start there (D5). Step 7 reads the schema version without migrating (`read_schema_version` on a plain connection) and, if behind, takes a pre-migration backup, stopping on its failure with the store unmigrated; then `open_hub_store`, with `create=True` only when step 5 found a first start. Step 8 catches `BackupError` only, logs it with `logger.exception` and goes on, with a comment saying why the swallow is right (a full backup disk must not keep the hub down; the backup loop tries again). Step 2 lets `load_hub_config`'s `HubConfigError` through unchanged; steps 3 to 7 failing raise `HubStartError` with one line. 11.4's tests assert those types
  - [x] Success: pyright clean
  Note: `HubStartError` is in the new `hub/errors.py`. `prepare_start(layout, *, now, start_log, from_backup, hooks)` returns `PreparedHub(config, listener, replaced)`; `start_log` is step 6, given by the caller (the command passes the real `start_hub_log`; tests pass a no-op so no handler is left on the root logger), and it runs between steps 5 and 7 as D14 orders. `StartHooks` holds the `CertificateHooks`, `RestoreHooks` and a `before_store_step` callable. The added `hub/start.py` module, with `hub/errors.py`, is to be recorded in the design under 17.3. `backups.take_timed_backup_if_due` is the one timed-backup check, used by step 8 and by the loop.
- [x] **11.2c `hub/restore.py`: `--from-backup` (D14, "Restoring from a backup")**
  - [x] `restore_from_backup(backup_dir_given, state_dir, now, hooks)` follows D14's six steps in order. The names `restore.partial` and `replaced-` are constants. `RestoreHooks` (frozen, one optional callable per step, default none) is the fault seam, like `MoveHooks`; production passes none
  - [x] Step 1 checks the three files exist and that the backup's store opens read-only (`mode=ro`) and passes `PRAGMA quick_check`; a failure raises `HubStartError` saying which, with the state directory untouched. Step 2 refuses a store, certificate and key with no `restore.partial/`, naming the three files. Step 4 moves the store, its side files, the certificate and the key, whichever exist, into one new `replaced-<UTC stamp>/` and returns its path for `hub serve` to print on stderr; with none there it makes no directory. Step 5 renames the certificate, then the key, then the store. Step 6 removes `restore.partial/`
  - [x] Record the added `hub/restore.py` in the design under 17.3
  - [x] Success: pyright clean
  Note: `restore_from_backup` takes the next free `replaced-<stamp>-N` name when `replaced-<stamp>` exists, so a re-run in the same microsecond never merges into an earlier directory. `RestoreHooks` fields: `after_partial_made`, `after_files_moved`, `after_files_copied`, `after_certificate_placed`, `after_key_placed`, `after_store_placed`.
- [x] **11.2b `hub/serve.py`: serve and the backup loop (D14 step 9)**
  - [x] `uvicorn` with the certificate and key, `access_log=False`, `log_config=None`, serving the socket from 11.2a's step 3; one line on stderr saying it is serving
  - [x] `backup_loop(check_seconds, ...)`: every `check_seconds` runs the timed-backup check in a worker thread; it catches `BackupError` only and logs it with `logger.exception`, with a comment saying the swallow is right because the next check tries again. Serving passes `BACKUP_CHECK_SECONDS`; tests pass a short interval
  - [x] If 0.1 noted a `uvicorn` version that differs from the one D14 names, confirm D14's stalled-peer statements (no first-request timeout, `limit_concurrency` not set) against that version and note the result
  - [x] Success: pyright clean
  Note: uvicorn locked at 0.54.0, the version D14 names, so no recheck of its stalled-peer statements was needed (see the 0.1 note). `serve.run` writes the serving line and runs `anyio.run`.
- [x] **11.3 `tests/hub/in_process_hub.py` (test infrastructure)**
  - [x] Runs the real app with `uvicorn` in a thread on `127.0.0.1` and a free port, with a certificate made by `make_certificate` in a tmp directory and a throwaway hub store; accepts `DoorHooks`; can stop, and start again on the same store; gives the address and the certificate path
  - [x] Success: a smoke test makes a `hello` call over pinned TLS with plain `http.client` and gets `done`
  Note: `tests/hub/in_process_hub.py` (`InProcessHub`) builds on `tests/hub/call_support.py`; shared start helpers are in `tests/hub/start_support.py`.
- [x] **11.4 Tests**
  - [x] `tests/hub/test_app.py` (through the helper): an over-size length and a missing length are `malformed_call` with status 400 and the body unread; each code's status matches the map; every reply has the door-version header
  - [x] `tests/hub/test_start.py` (prepare only):
    - [x] One test per row of D5's table, on real files. A store with a lone certificate, a lone key or neither, beside a backup, each refuse naming the missing file and giving both ways on. The same three with an empty `backup_dir` each start with a new pair, keep the store's rows, and write the "certificate is new" line. No store and no backup: a full pair is kept and a store made; a lone key and a lone certificate are each replaced by a new pair; a directory holding only `logs/` is a first start
    - [x] A first start stopped after the key is written, and one stopped after the pair and before the store (hooks in `make_certificate` and before step 7), is each finished by the next start
    - [x] A missing `backup_dir` on a start with no store refuses naming it; the same `hub.yaml` beside a complete state starts
    - [x] A bad `hub.yaml` key refuses naming it
    - [x] A schema-10 store with an unwritable `backup_dir` refuses and the store stays at 10
    - [x] A taken port refuses before any file is written and the store stays unmigrated
    - [x] No store beside a `backup_dir` with a backup refuses, names the newest backup, gives the `--from-backup` command and makes nothing, with no certificate files, with a full pair and with a lone key; the same with an empty `backup_dir` is a first start
    - [x] An unwritable `backup_dir` with no migration due starts and logs the failure
  - [x] `tests/hub/test_restore.py` (11.2c):
    - [x] A restore into a state directory with none of the three files serves the backup's rows under the backup's certificate, makes no `replaced-` directory and leaves no `restore.partial/`
    - [x] A restore over a working hub (store, certificate and key) refuses naming the three files, and the directory's file tree is unchanged
    - [x] A restore over a store with no certificate moves the store and its side files into one `replaced-<UTC stamp>/`, returns that path, and the moved store still opens with its rows
    - [x] A backup with a file missing, and one whose store is not a database, each refuse with the state directory unchanged
    - [x] A restore stopped after each of steps 3, 4 and 5, and between the three renames of step 5 (through `RestoreHooks`): a start without the flag refuses naming the unfinished restore, and the same restore run again finishes with the backup's rows and certificate in place
    - [x] After a finished restore, the same restore again is refused as a working hub
  - [x] `tests/hub/test_backup_loop.py`: run with a short interval and a `backup_hours` small enough that a backup is due at each check, the loop takes a timed backup without a restart; with `backup_dir` unwritable it logs the failure at error level, and once it is writable again the next check takes the backup
  - [x] Success: checks pass

**Commit**: `feat: add the hub web app and start sequence`

## 12. The client call (D5, D6, D7, D10; effort 3)

- [x] **12.1 `client/trust.py`**
  - [x] `pinned_context(cert_path)`: `ssl.SSLContext(PROTOCOL_TLS_CLIENT)`, `check_hostname = False`, `verify_mode = CERT_REQUIRED`, only that certificate loaded, no system certificates (D5)
  - [x] `fetch_certificate(address, connect_seconds)`: the one unverified connection of D4 step 3. It sends no request bytes, reads the presented certificate and closes. Connection refused, timeout or no TLS raise `HubUnreachableError` (from `client.errors`) naming the address and cause
  - [x] Success: pyright clean
- [x] **12.2 `tests/hub/test_trust.py`**
  - [x] A TLS listener in a thread that records every byte it reads: with the right certificate the handshake succeeds; with another certificate it fails and the listener read no application bytes; `fetch_certificate` returns the presented certificate and the listener read no application bytes; nothing listening raises `HubUnreachableError`
  - [x] Success: checks pass
  Note: `tests/hub/tls_server.py` (`RecordingTlsServer`) is the byte-recording TLS listener; the saved-certificate context test counts `cert_store_stats()["x509"]`, because `get_ca_certs()` omits a certificate with no CA flag.
- [x] **12.3 `client/call.py`**
  - [x] `call(client_file, cert_path, name, document, times=DoorTimes(), call_id=None)` returns the result document. With no `call_id` given it makes one `uuid4().hex`; either way that id is reused by every repeat. Tests pass their own `call_id` to repeat a call under the same id, and never patch `uuid`; the four headers of D6; `HTTPSConnection` with `pinned_context` and the connect and read times
  - [x] No reply (refused connection, timeout, a body `parse_reply` rejects) waits the pause and retries while under the retry time, then raises `HubUnreachableError` naming the address and how long it tried, and saying that if the hub's address has changed, `amoeba join --address <host:port>` sets the new one; for a writing call it adds that the outcome is unknown and the `UNKNOWN_ADVICE` text
  - [x] A certificate failure (`ssl.SSLCertVerificationError`, checked before the `OSError` branch that counts as no reply, since it is an `OSError` subclass) raises `HubCertificateError` at once, not retried, with D5's two ways on. A refused reply raises `HubRefusedError` naming address, code and message, adding D6's text for `door_version` (both versions and `uv tool install --force amoeba-ai`) and `bad_token` (the two commands, with this machine's name). A reply whose door-version header differs raises the same `door_version` error
  - [x] Join the three errors to `OPERATIONAL_ERRORS`
  - [x] Success: pyright clean
  Note: A call's retry loop stops when the next attempt would start at or after `retry_seconds` (elapsed plus the pause), so an attempt never starts after the retry time.
  Note: A reply that parses but has no matching `Amoeba-Door-Version` header (missing or different) raises the `door_version` error.
  Note: For `join`'s `hello` (task 13.3a) the machine name is not known yet, so it passes the placeholder `<machine>` in the `ClientFile`, which only shows in a `bad_token` message.
  Note: `HubUnreachableError`, `HubCertificateError` and `HubRefusedError` joined `OPERATIONAL_ERRORS`; the expected set in `tests/test_wiring.py` was extended.
- [x] **12.4 Tests (through the in-process hub, short `DoorTimes`)**
  - [x] `tests/hub/test_call.py`:
    - [x] A served call returns its result; a refusal raises `HubRefusedError` with its code
    - [x] A hub with another certificate raises `HubCertificateError` on the first attempt
    - [x] A stopped hub raises `HubUnreachableError` after the retry time, with "unknown" and the advice for `standing` and without them for `decisions`
    - [x] A reply dropped by `after_commit`, then the server stopped and a new one started on the same store, and the call repeated with the same `call_id`, returns the first result and the store holds one standing answer
    - [x] A client door version patched to differ gets both versions and the upgrade command; a reply header with another version raises the same
    - [x] A hub answering non-reply bodies counts as no reply
  - [x] Success: checks pass

**Commit**: `feat: add the pinned client call with retry`

## 13. The mode switch, `join` and `leave` (D2, D3, D4; effort 4)

- [x] **13.1 The mode switch (`wiring_door.py`)**
  - [x] `joined()`: the loaded client file, or `None` when it does not exist; called on every call, never cached; `load_client_file` checks the certificate. `NotServedError` naming the address and the operation, joined to `OPERATIONAL_ERRORS`
  - [x] `wiring.invoke`'s first line is one call into `wiring_door`, which returns the hub's result when joined, or `None` when not, and `invoke` returns a result at once. All branching is in `wiring_door`: when joined, a served operation goes through `client.call` and `result_from_document`, and any other raises `NotServedError`. With a client file nothing local is read or written first: no layout, config, store, state move, log line or `start_after`
  - [x] Success: pyright clean; the full suite is at baseline
  Note: `NotServedError` joined `OPERATIONAL_ERRORS` (expected set in `tests/test_wiring.py` extended). `wiring_door.route(name, document)` is the one call `invoke` makes first; `joined()` loads the client file and checks the certificate on every call. The tests for the mode switch are in `tests/hub/test_join.py` and `tests/hub/test_joined_entry_points.py` (14.4).
- [x] **13.2 Setting a store aside and putting it back (`store/relocate.py`, or `store/set_aside.py` per the size rule in the Context Summary)**
  - [x] `set_aside(store_path, hub_address, now, hooks)` follows D4's four steps, with `SetAsideHooks` (frozen, one optional callable after each step and one between the two deletes of step 4, default none) as the fault seam:
    - [x] Step 1, mark: on a plain SQLite connection, one `BEGIN IMMEDIATE` transaction that writes the closed mark, replacing any mark already there, and commits. Keep the mark's address and time for the comparison below
    - [x] Step 2, copy: delete a leftover `amoeba.sqlite3.set-aside.partial`, copy the store into it with SQLite's backup call (reuse `copy_store`'s backup code; do not duplicate it), and close both connections. No checkpoint is run and no side file is renamed
    - [x] Step 3: rename the closed copy to `amoeba.sqlite3.set-aside-<UTC stamp>`
    - [x] Step 4: delete the original store file, then its two side files. Return the set-aside path
  - [x] `same_mark(path_a, path_b)`: reads the `closed_mark` row of each on a read-only plain connection and is true only when both hold a row with the same address and time. `set_aside` called with a set-aside store already present: when the store at the store path is its original (`same_mark`), delete the original and its side files and return the existing set-aside path; otherwise raise `JoinError` naming both files and saying to run `amoeba leave` (D4)
  - [x] `clear_orphan_side_files(store_path)`: deletes `-wal` and `-shm` at the store path when no store file is beside them. Called by `set_aside`, by `put_back` and by 13.3b's skip branch before anything else
  - [x] `put_back(store_path)`, in D4 step 1's order: delete a `.partial` copy and orphan side files; if the store path holds a store, delete it and its side files when `same_mark` says it is the original, otherwise move it and any side files to `amoeba.sqlite3.displaced-<UTC stamp>` and return that path too, so `leave` prints it; open the set-aside file by its path on a plain SQLite connection, delete the `closed_mark` row in one transaction and close; if a side file is still beside it, raise `StoreRelocateError` naming it (running `leave` again retries); rename to the store path. Each part is skipped when already done
  - [x] Success: pyright clean
  Note: The set-aside code is in the new `store/set_aside.py` (not `relocate.py`, per the size rule), which takes the shared backup call from `relocate.backup_store`, a new helper `copy_store` and `hub/backups.py` now also use (the copy code is written once). `put_back` returns a `PutBack(restored, displaced, cleared_mark)` and, when more than one set-aside store somehow exists, uses the newest and leaves the others untouched. `SetAsideHooks` fields: `after_mark`, `after_copy`, `after_rename`, `after_store_deleted`, `after_delete`.
- [x] **13.3a `client/join.py`: the network and file steps**
  - [x] `client.join`: fetch the certificate, compare its fingerprint with the line's (mismatch is `JoinError` with both fingerprints), save it, make one `hello` call, write the client file. On a `hello` failure remove the saved certificate or put the previous one back, then re-raise. `change_address(path, address)` and the three file steps of `leave`
  - [x] Success: pyright clean
  Note: `client.join.join` takes a `between` callable, run after `hello` and before the client file is written; any failure before the client file is written restores the certificate, including a failure in the set-aside. `change_address` also checks the address is `host:port`.
- [x] **13.3b `wiring_door.join`: D4's steps in order, with its branches**
  - [x] `wiring_door.join(line, set_aside_local)`: first refuse with `JoinError` in a hub home (the config home holds `hub.yaml`), before anything is read or written (D4 step 0). With no client file run `prepare_state_home`; refuse with `JoinError` when a local store exists without `--set-aside-local`, naming the store and the flag; with the flag, set the store aside between `hello` and writing the client file and return its path
  - [x] With the flag and a local store, open it once through `open_state_store` and close it right after `prepare_state_home`, so it is migrated and `closed_mark` exists before `set_aside` writes the mark (D4 step 1). Skip this when the store already holds a mark (read on a read-only plain connection, a missing `closed_mark` table meaning no mark), because the opener's `local`-machine write would be refused
  - [x] With the flag, no store at the store path and a set-aside store present (a `join` stopped after the original was deleted), clear orphan side files, skip the set-aside and return the existing path, so the re-run finishes by writing the client file (D4's table)
  - [x] `join --address` needs an existing client file, raising `JoinError` saying the machine is not joined when there is none, and makes no hub call
  - [x] Success: pyright clean
  Note: `wiring_door.join(line, set_aside_local=, hooks=)` returns a `JoinReport(machine, address, set_aside)`; `join_address(address)` is the `--address` form.
- [x] **13.3c `wiring_door.leave`: D4's three steps**
  - [x] `wiring_door.leave()`: put back, delete the client file, delete the certificate, each skipped when nothing is there, making no hub call
  - [x] With no set-aside store and a store at the store path holding the closed mark, put-back instead clears that mark on a plain connection and deletes a `.partial` copy (D4 step 1)
  - [x] `leave` has no rejected outcome: in a home that is not joined and has nothing to put back it does nothing and exits 0 (D4)
  - [x] Success: pyright clean
- [x] **13.4 `cli/join_command.py` and the parser**
  - [x] `amoeba join <line> [--set-aside-local] [-j]`, `amoeba join --address <host:port> [-j]`, `amoeba leave [-j]`, registered as CLI-only commands; exit codes as today. `docs/cli-contract.md`: the commands, flags and new errors
  - [x] Success: `amoeba join --help` and `amoeba leave --help` work
  Note: `docs/cli-contract.md` has a new section "The hub and joined machines" for `join`, `leave`, the joined-machine behavior and the new errors; the hub commands are added to it in 14.2. `join` and `leave` are in `CLI_ONLY_COMMANDS`.
- [x] **13.5 Tests (in-process hub)**
  - [x] `tests/hub/test_join.py`:
    - [x] Join writes a `0600` client file with the name from `hello`, and saves the certificate
    - [x] A wrong fingerprint raises `JoinError` naming both, saves nothing, and the hub read no application bytes
    - [x] Nothing listening raises `HubUnreachableError` and saves nothing
    - [x] A refused `hello` saves nothing, and a re-join that fails puts the previous certificate back
    - [x] A re-join replaces the token
    - [x] A local store without the flag is refused with `JoinError` naming it
    - [x] `--address` changes only the address with the hub stopped; with no client file it raises `JoinError` saying the machine is not joined
    - [x] A line with two fields raises `JoinError`; each `JoinError` case exits 3 through the CLI and saves nothing
    - [x] In a home whose config directory holds `hub.yaml`, `join` with and without the flag raises `JoinError` naming `hub.yaml`, and a store there is unmarked, in place and unchanged
    - [x] `leave` in a home that is not joined exits 0 and creates no file
  - [x] `tests/hub/test_set_aside.py`:
    - [x] Join with the flag prints the path, the store path is free and the file holds the mark
    - [x] A connection opened before the join fails its next write with `LocalStoreClosedError` naming the hub
    - [x] `leave` puts the store back with its rows, removes the set-aside file, and the next local command writes to it
    - [x] `leave` stopped after each step (simulated by running the step functions partway) is finished by a second `leave`
    - [x] A store set aside while a second connection holds a read transaction open, with committed rows still in the write-ahead log (the second connection opened first, then rows written, no checkpoint), is put back by `leave` with every row
    - [x] One test per row of D4's stop table, each stop made with `SetAsideHooks`: after the mark, after the copy is renamed, after the original store file is deleted and before its side files, and after step 4. From each state, a second identical `join` finishes with a client file and one set-aside store, and separately `leave` ends with the store back at the store path holding every row. Neither leaves a `.partial` file, a side file with no store beside it, a `displaced-` file or a second copy of the store
    - [x] After a stop following the mark, local commands fail with `LocalStoreClosedError` that names `amoeba leave` and the same `join`
    - [x] `join --set-aside-local` as the first command on a schema-10 store (built as in 2.2) migrates it and sets it aside, and `leave` puts back a schema-11 store with its rows
    - [x] A leftover `.partial` copy from a killed run is replaced by the next `join` and deleted by `leave`
    - [x] With a hand-placed store at the store path, `leave` moves it and its side files to a `displaced-` name, prints that path and puts the set-aside store back; both stores' rows are intact
    - [x] `join --set-aside-local` with a set-aside store and a hand-placed store present (no mark, and separately a mark with a different time) raises `JoinError` naming both files and `amoeba leave`, and deletes neither
    - [x] A client file with no certificate fails a served call with `ClientFileError`, and `leave` still works
  - [x] Success: checks pass

**Commit**: `feat: add the mode switch, join and leave`

## 14. Admin commands and entry-point checks (D2, D13; effort 3)

- [x] **14.1 `hub/admin.py`**
  - [x] `invite(name)`: malformed name rejected; `secrets.token_urlsafe(32)`; `invite_machine` with its hash in one transaction; returns the join line from `hub.yaml`'s address and the certificate's fingerprint. Both are read before the transaction: a missing or bad `hub.yaml` fails through `load_hub_config`, and a missing certificate raises `HubStartError` naming it and saying to run `amoeba hub serve` first. Either exits 3 and changes nothing. `machines()`, `rm_machine(name)` (no such machine is rejected), `backup()` (a timed backup now, returning its path). All four open the store with `open_hub_store` and never pass `create=True`, so on a hub with no store each raises `HubStoreMissingError`, exit 3, and writes no file (D13). `invite` opens the store before it reads the certificate, so a hub that never started reports the missing store
  - [x] Success: pyright clean
  Note: `hub.admin` raises `AdminRejection` (a new exception in `hub/admin.py`) for a malformed name and an unknown machine; the CLI turns it into exit 1 with `rejected: <text>` on stderr. `invite` returns `Invited(machine, join_line, is_new)`.
- [x] **14.2 `cli/hub_commands.py` and the parser**
  - [x] `amoeba hub serve [--from-backup <dir>]`, `hub invite <machine>`, `hub machines`, `hub rm-machine <machine>`, `hub backup`, each with `-j` where D13 says, registered like `wake-run` with no `OperationName`. The first line of each raises `LocalStoreClosedError` when a client file exists, before `hub.yaml` is read or any file written. It builds the layout and hands the hub `open_hub_store` bound to it. Rejected is exit 1; `HubStartError`, `BackupError` and operational errors are exit 3 with one stderr line
  - [x] `docs/cli-contract.md`: the five commands
  - [x] Success: `amoeba hub --help` lists the five
  Note: `hub_commands.run_serve` builds `prepare_start` with the real `start_hub_log`, binds `handle_call` to `open_hub_store(layout)`, the clock and the hub's `config.yaml` (next to `hub.yaml`), and passes `serve.run` a `take_timed_backup_if_due` check. `cli/main.py` catches `HubStartError` and `BackupError` beside `OPERATIONAL_ERRORS`. `hub` is in `CLI_ONLY_COMMANDS`. `docs/cli-contract.md` has the five commands under "The hub and joined machines".
- [x] **14.3 Entry-point checks**
  - [x] `cli/main.py`: with a client file, `handle-pause` and `wake-run` raise `NotServedError` before the layout is built and the config loaded; no calls-log line
  - [x] `mcp/server.py`: start raises `NotServedError` before the state move and config load. `mcp/in_process.py`: the `answer` deadline check runs only with no client file
  - [x] Success: pyright clean
  Note: `wiring` re-exports `joined`, `refuse_if_joined` and `NotServedError` so `cli` and `mcp` import only `wiring`; the `answer` deadline check in `mcp/in_process.py` runs only when `wiring.joined()` is `None`.
- [x] **14.4 Tests**
  - [x] `tests/hub/test_admin.py`: invite prints a line that `parse_join_line` reads with the hub's fingerprint; a re-invite ends the old token; `machines` lists name, token, call time and client version; `rm-machine` of an unknown name exits 1; a malformed name exits 1; `invite` with no `hub.yaml`, and with no certificate, each exits 3 naming the file and adds no machine; `backup` prints a timed path; in a hub home with `hub.yaml` and no store, each of the four commands exits 3 with `HubStoreMissingError`, the home's file tree is identical before and after, and a `hub serve` prepare run after them is a first start
  - [x] `tests/hub/test_joined_entry_points.py` (D2): in a home holding only a client file and a saved certificate, every unserved CLI command and MCP tool raises `NotServedError`, `handle-pause` and `wake-run` raise it, `amoeba-mcp` start raises it, each hub command raises `LocalStoreClosedError`, and the home's file tree is identical before and after
  - [x] Same file (D2): an in-process `amoeba-mcp` started with no client file, then given one, hits `LocalStoreClosedError` on its next inbox-watcher tick in the existing store-error handler, logs it, and creates no file in the state home
  - [x] Success: checks pass
  Note: the inbox-watcher case is tested through `run_presence`, whose existing top-level handler logs `LocalStoreClosedError` ("presence stopped; the tools keep serving") and creates no file.

**Commit**: `feat: add the hub admin commands and the joined entry-point checks`

## 15. The two-machine fixture and its tests (D18, Success Criteria; effort 4)

- [x] **15.1 `tests/hub_fixture.py` (test infrastructure)**
  - [x] Writes `hub.yaml` (loopback, a free port, a tmp `backup_dir`) and `config.yaml` from `tests/user_configs.py` in a hub home; starts the venv's `amoeba hub serve` as a subprocess with `AMOEBA_HOME` set and a `PATH` on which `shutil.which("cf")` and `shutil.which("sq")` are `None`; invites two machines with the real CLI and joins two client homes with `amoeba join`; stop, kill (`SIGKILL`) and restart; seeding the hub's store while stopped with `tests/store/seed.py` functions, the store opened with `open_hub_store` and acting as the first invited machine through `store.act_as`, never `act_as_local` (D12, D18); a `run(client, *args)` that runs the CLI in a client home and returns the exit code and JSON
  - [x] Success: a fixture test starts, joins both clients, stops cleanly and leaves no process behind
  Note: `tests/hub_fixture.py` starts every process through `contained_popen` (the repo's containment rule); `two_machine_hub(root, ...)` gives a serving hub with `alpha` and `beta` joined from their own homes; `FixtureHub` has `start`, `stop` (SIGTERM), `kill` (SIGKILL), `restart`, `move_to_new_home`, `invite`, `join`, `seed`/`seeded_store` (acting as an invited machine, never `local`) and `run_in`; `ClientHome.run` runs the CLI in a client home. `tests/hub/test_fixture_smoke.py` is the 15.1 success test.
- [x] **15.2 `tests/hub/test_two_machines.py`**
  - [x] Each of the first four Functional Requirements of the design: `standing` across machines (both ways, including the seeded record citing `standing:<id>` after a restart), `withdraw` then `unchanged`, `decisions` identical from both with members named by id and `mark_read` moving the shared marker, and `standing --member <id>` for a seeded member with any other reference `no_such_member`
  - [x] Success: checks pass
- [x] **15.3 `tests/hub/test_access.py`**
  - [x] No token, a bad token, a removed machine's token and a re-invited machine's old token are each `bad_token` on the next call, each a hub-log line without the token, and the client error names `hub invite` and `join`. A client with a patched door version gets both versions and the upgrade command, and `hub machines` shows that call's client version and time
  - [x] Success: checks pass
- [x] **15.4 `tests/hub/test_hub_lifecycle.py`**
  - [x] Five restarts in a row take no new timed backup; a hub started with `--from-backup` on a new state directory serves both clients with no new invite; with tiny keep counts, many backups and much log leave `backups_kept` per kind and `hub_logs_kept` log files; after the module's run the hub store holds no `local` machine
  - [x] On the fixture hub (D5, D14, D15 criteria): with the hub stopped and its store file moved away, a start refuses naming the newest backup, and `--from-backup` on it serves both clients with no new invite; with the store file removed under a serving hub, a call is refused as `hub_error`, no store file appears, and no new backup directory is made at the next check; with the certificate removed and `backup_dir` emptied, the start makes a new pair, both clients fail with `HubCertificateError`, and each serves again after a new invite and `join`
  - [x] `amoeba hub backup` run ten times in a row against a serving hub whose `backup_hours` makes a backup due at every check: every run exits 0, and afterwards no partial directory is left and the timed rotation holds `backups_kept` (the two-process lock itself is proven in 9.2)
  - [x] A hub whose migration fails on five starts in a row (a store stamped below the schema with a statement made to fail) leaves one pre-migration backup for that version and keeps the earlier versions' backups
  - [x] An ordinary command (`amoeba standing`) run with `AMOEBA_HOME` set to the hub home exits 3 with `HubHomeError`, and the hub store's row counts are unchanged
  - [x] Success: checks pass
  Note: `backup_loop` also catches `HubStoreMissingError`, not only `BackupError`: with the store file removed under a serving hub the timed check raises it, and a loop that let it pass would have ended the hub. `tests/hub/test_backup_loop.py` pins that. The next-check part of the removed-store criterion is proven there with a short interval, since the hub's own interval is the constant 300 s; the subprocess test proves the refused call, no new store, no new backup (by `amoeba hub backup`) and that the hub keeps running.
- [x] **15.5 Kill and noise tests**
  - [x] `tests/hub/test_kill.py` (D18): a client thread calls `standing` with normal retry and a `call_id` the test chose; the test polls `call_results` read-only until the row is there, kills the hub, restarts it; the call returns `given`; a repeat with that `call_id` returns the same result; the store holds one standing answer
  - [x] `tests/hub/test_noise.py` (D16): random bytes, plaintext HTTP on the TLS port and malformed HTTP inside TLS, many times each; the hub's stderr holds only the serving line, stdout is empty, the log holds at most `hub_logs_kept` files, and the next call succeeds
  - [x] Success: checks pass
- [x] **15.6 `tests/load/test_door_load.py`**
  - [x] 16 client threads against the fixture hub, half `decisions` over 500 seeded answers, half `standing`, `withdraw` and `mark_read`: no call refused or unknown, each within 2 seconds. 100 calls from one thread on the idle hub: median under 200 ms. Record both measured figures in a note under this task
  - [x] The file runs in the bare `uv run pytest`, and so in CI, like the other `tests/load` files (`pyproject.toml` ignores only `tests/live`). The gate is the `Tests` step of the `check` job in `.github/workflows/ci.yml`, which runs the bare `uv run pytest`; confirm with `uv run pytest --collect-only -q tests/load/test_door_load.py` and note that the file is in that collection. The bounds are named constants in the test. If CI fails a bound that passes locally, get the CI figures from its log before changing anything, and record them under this task
  - [x] Success: both bounds pass; the note gives the figures
  Note: Load figures. Sixteen clients (8 `decisions` over 500 seeded answers, 8 running `standing`, `withdraw` and `mark_read`), 320 calls: six runs gave a slowest call of 0.07 to 0.21 s and a median of 14 to 22 ms. One thread, 100 `decisions` calls on the idle hub: median 2.7 ms. Each client sends its next call 0.25 s after the last reply and starts 20 ms after the previous one (`THINK_SECONDS`, `START_SPREAD_SECONDS` in the test): with no pause the 16 clients saturate the hub's one process (a 500-answer `decisions` costs about 25 ms of its CPU and Python threads share one interpreter lock) and the slowest call was 1.2 to 2.0 s, which is the queue's length and too close to the bound to gate on. `tests/load/test_door_load.py` is in the bare `uv run pytest` collection (checked with `--collect-only`), and the `Tests` step of the `check` job in `.github/workflows/ci.yml` runs the bare `uv run pytest`; no CI figures are needed yet.

**Commit**: `test: add the two-machine hub fixture, kill, noise and load tests`

## 16. The container (D17; effort 2)

- [x] **16.1 `docker/Dockerfile` and `docker/compose.example.yaml`**
  - [x] Dockerfile per D17: `python:3.13-slim`, Amoeba installed from the checkout, non-root user `amoeba`, volumes at that user's default config and state paths and `/backups`, `AMOEBA_HOME` unset, `hub.yaml.example` and `docs/config-contract.md` copied to `/usr/share/amoeba/`, and an exec-form entry point `amoeba hub serve` so it runs as PID 1 and gets `docker stop`'s signal (`tool-guides/docker/02-entrypoint-and-process-model.md`)
  - [x] Compose example: one service named `hub`, the three mounts with their host directories under `~/amoeba-hub/` (D17), the published port, `restart: always`. A comment above the service gives the two restore commands of D17 and says `--from-backup` is never added to this file
  - [x] Success: files exist; checks pass
  Note: The Dockerfile is two-stage: a build stage that `pip install`s the checkout into `/install`, and a `python:3.13-slim` runtime stage. The build context is the repository root, with a new `.dockerignore`. `tests/test_container_files.py` checks the entry point is the exec form, the user, the three volumes, the two copied examples, the one service `hub`, `restart: always`, the three mounts under `~/amoeba-hub/` and that `--from-backup` is never set in the compose file.

**Commit**: `feat: add the hub container image and compose example`

- [x] **16.2 Build and try it once**
  - [x] `docker version` succeeds. If it does not, write `BLOCKED: docker unavailable` under this task and stop this task. 17.3 waits on it; 17.1, 17.2 and 17.4 go on
  - [x] Run the Verification Walkthrough's container steps from the design: build, start with the compose mounts and the two example-derived files, `docker exec <container> amoeba hub invite alpha`, set `address` in the copied `hub.yaml` to `127.0.0.1:<the published port in docker/compose.example.yaml>` so the host reaches it, `amoeba join <line>` in a throwaway home, `amoeba standing --text "<any text>" -j` from it answering `given`. Then the restore of D17: `docker exec <container> amoeba hub backup` and note the path it prints, `docker compose stop`, empty the state mount, `docker compose run --rm --service-ports hub --from-backup <that path>` until it prints its serving line, stop it, `docker compose up -d`, and `amoeba standing --text "<the same text>" -j` from the same throwaway home answers `unchanged` with no new join. Stop and remove the container
  - [x] Success: a note under this task holds the commands and their output, with the join line's token removed. The note is committed with section 17
  Note: Run by hand on 20261122 with `docker/compose.example.yaml` and its three mounts under `~/amoeba-hub/` (removed afterwards). `docker version` succeeded. The first `docker build -f docker/Dockerfile -t amoeba-hub .` failed with `OSError: License file does not exist: LICENSE` (hatchling reads the file `pyproject.toml` names; the build stage did not copy it). Fixed: the Dockerfile's build stage now copies `LICENSE`, and `tests/test_container_files.py::test_the_build_stage_copies_every_file_pyproject_names` pins it. Then: build succeeded; `docker compose -f docker/compose.example.yaml up -d` logged `amoeba hub: serving on 0.0.0.0:8443`; `docker exec docker-hub-1 amoeba hub invite alpha` printed `127.0.0.1:8443,<fingerprint>,<token removed>`; `AMOEBA_HOME=<throwaway> amoeba join <line>` printed `joined the hub at 127.0.0.1:8443 as alpha`; `amoeba standing --text "Container walkthrough ruling." -j` printed `"outcome": "given"`, `"standing_id": 1`, exit 0. `docker exec docker-hub-1 amoeba hub backup` printed `/backups/timed/<stamp>`; `docker compose stop`; the state mount emptied with `find ~/amoeba-hub/state -mindepth 1 -delete`; `docker compose run --rm --service-ports hub --from-backup /backups/timed/<stamp>` printed `amoeba hub: serving on 0.0.0.0:8443`; stopped it; `docker compose up -d`; the same `standing` call from the same home printed `"outcome": "unchanged"`, `"standing_id": 1`, exit 0, with no new join. A restore tried with the state mount not yet empty was refused with `HubStartError: ... already holds a working hub (hub-cert.pem, hub-key.pem, amoeba.sqlite3); a restore replaces nothing that works`. `docker compose down` removed the container and network.

## 17. Documents, the release script and final validation (D19; effort 2)

- [x] **17.1 The five documents (D19)**
  - [x] `docs/store-contract.md` (prose for the tables added in 2.1), `docs/cli-contract.md` (the joined-machine behavior and every new error with its exit code), `docs/config-contract.md` (`hub.yaml`, the client file and where each file lives per D1), `docs/mcp-server.md` (`amoeba-mcp` does not start on a joined machine; a running one's tools go through the door), `docs/squadron-hook.md` (`handle-pause` on a joined machine fails with `NotServedError` and writes no calls-log line)
  - [x] Success: `tests/test_contract_docs.py` passes
  Note: The store contract also has a prose section "Machines, owners and who writes them (slice 260)" with each writer, how each state ends, and the `ownership` reason line.
  Note: `docs/cli-contract.md` has "The hub and joined machines" (joined-machine behavior, `join`, `leave`, the five hub commands, the new errors with exit 3).
  Note: `docs/config-contract.md` has "The hub and the client (slice 260)" (where each file lives, `hub.yaml`'s eight keys, the client file's three).
  Note: `docs/mcp-server.md` and `docs/squadron-hook.md` each have an "On a joined machine (slice 260)" section, and the MCP "Start-up" list names the `NotServedError` refusal.
- [x] **17.2 `scripts/update_live.py`**
  - [x] Add two read-back checks: `owners` holds one row; after the script's `amoeba list`, `machines` holds the one `local` row. Correct the docstring: it runs as the release skill's last step, not after a slice merges
  - [x] `tests/scripts/test_update_live.py`: call `update()` and `restore()` directly with the file's `FakeSteps`, never `PRODUCTION` or `main()` (they reinstall the tool and inspect the checkout), with `AMOEBA_HOME` the autouse fixture's throwaway home. `FakeSteps._migrate` opens the store through `open_state_store(state_layout())`, as `amoeba list` does, so the schema-11 and `local`-row checks can pass. Run against a copy of a schema-10 store (built as in 2.2); `update` passes both new checks; `restore` puts the schema-10 store back
  - [x] Success: checks pass
  Note: `check_store` in `scripts/update_live.py` also fails when `owners` does not hold exactly one row or `machines` holds anything but `local`; the docstring now says the script runs as the release skill's last step.
  Note: Tests: `update` and `restore` against a copy of a schema-10 store (`test_update_and_restore_against_a_copy_of_a_schema_ten_store`) and a store with no `local` machine failing the read-back; `FakeSteps._migrate` opens the store through `open_state_store(state_layout())`.
- [x] **17.3 Slice design notes**
  - [x] `user/slices/260-slice.hub-and-door.md`: in Verification Walkthrough, drop "Draft" and "None of these commands exist yet" and make the steps match what was built; add an Implementation Notes entry with the load figures (15.6), the container output summary (16.2), the restore command `uv run python scripts/update_live.py restore` and the backup directory `~/.local/state/amoeba/backups/<stamp>/`, the modules added beyond Component Structure (`hub/start.py` from 11.2a, `hub/call_refusals.py` from 10.1a, `operations/errors.py` from 10.1a, `client/errors.py` from the Context Summary), the import edge `operations` → `client.client_file` (6.3) in the design's import rules, and any design text changed under the small-conflict rule
  - [x] Success: the notes are in the design
- [x] **17.4 Final validation**
  - [x] Run the checks once; all pass, or only the baseline failures listed in 0.2
  - [x] Map each Functional Requirement in the design to the test that proves it, as a note under this task; a requirement with no test gets one before this task is checked. The criterion that 261 can serve a new operation by adding to the served list and `run_served` is proven by 10.2's stub-operation test; the note says so
  - [x] `wc -l` every new source file; any well over ~300 lines is split by concern
  - [x] `git status` shows only this slice's files
  - [x] Success: checks pass; the mapping note is complete
  Note: Checks run once: ruff format, ruff check, pyright clean; pytest 4792 passed, no baseline failure. `wc -l` of every new source file: all under 300 (largest `hub/calls.py` 295, `hub/start.py` 273, `hub/backups.py` 263, `store/set_aside.py` 249). `wiring.py` is 342 lines (325 before): the six served cases are one call, and its growth is imports, re-exports and the longer `OPERATIONAL_ERRORS`. `git status` showed only this slice's files.
  Note: Functional Requirement mapping (test files are under tests/hub/ unless a path is given):
  - standing across machines both ways and the seeded `standing:<id>` record after a restart: `test_two_machines.py::test_a_standing_answer_given_on_one_machine_is_read_from_the_other`
  - `withdraw` then `unchanged`: `test_two_machines.py::test_withdraw_from_the_second_machine_then_unchanged_from_the_first`
  - `decisions` identical from both, members named by id, `mark_read` moves the shared marker: `test_two_machines.py::test_decisions_are_identical_from_both_and_mark_read_moves_the_shared_marker`
  - `standing --member <id>` works and any other reference is `no_such_member`, hub with no `cf` or `sq`: `test_two_machines.py::test_standing_for_a_seeded_member_works_and_any_other_reference_is_rejected`, `tests/operations/test_served.py`, `test_fixture_smoke.py` (the `PATH`)
  - a hub with another certificate, `join` with a wrong fingerprint, `join` against nothing: `test_call.py::test_a_hub_with_another_certificate_fails_at_once_without_retrying`, `test_trust.py`, `test_join.py` (wrong fingerprint, nothing listening)
  - a client file with no saved certificate and `leave`: `test_join.py::test_a_client_file_with_no_certificate_fails_a_call_and_leave_still_works`
  - `bad_token` for no token, a bad token, a removed and a re-invited machine, each in the hub log without the token: `test_access.py::test_no_token_a_bad_token_a_removed_and_a_reinvited_machines_token_are_refused`, `test_handle_call.py`
  - a writing call repeated applies once, including a dropped reply and a killed hub; the same id from another machine is a new call: `test_handle_call.py` (repeat, second machine), `test_call.py::test_a_dropped_reply_then_a_new_server_returns_the_first_result_once`, `test_kill.py`
  - a non-operational exception is `hub_fault`: `test_handle_call.py::test_a_bug_on_the_hub_is_hub_fault_with_the_traceback_logged`
  - a stopped hub fails after the retry time and a writing call says its outcome is unknown: `test_call.py::test_a_stopped_hub_is_unreachable_with_unknown_and_advice_for_a_writing_call`
  - with no client file the same commands run locally and every existing test passes: the full suite (4792 passed)
  - every unserved command and tool, `amoeba-mcp` start and every hub command fail with their error and create no file: `test_joined_entry_points.py`
  - a different door version gets both versions and the upgrade command and `hub machines` shows the call: `test_call.py` (two door-version tests), `test_access.py::test_a_client_with_another_door_version_gets_both_versions_and_the_machine_shows`
  - five restarts take no new timed backup; `--from-backup` on a new state directory accepts both clients: `test_hub_lifecycle.py`
  - `rm-machine` and a re-invite end the old token on the next call: `test_access.py`, `test_handle_call.py::test_a_token_removed_between_the_read_and_the_scope_is_bad_token`
  - a bad `hub.yaml` key, an unwritable `backup_dir` before a migration, a taken port: `test_start.py`
  - each row of D5's table: `test_certificate.py` (all sixteen combinations) and `test_start.py` (one test per row on real files)
  - a state directory with no store beside a backup refuses and names the newest backup: `test_start.py`, `test_hub_lifecycle.py::test_a_missing_store_refuses_the_start_and_the_restore_serves_both_clients`
  - the four admin commands before the first `serve` fail with `HubStoreMissingError` and write nothing; a store removed under a serving hub: `test_admin.py`, `test_hub_lifecycle.py::test_a_store_removed_under_a_serving_hub_is_refused_and_never_replaced`, `test_backup_loop.py`
  - `--from-backup` refused over a working hub, moves a damaged store aside, refuses a bad backup: `test_restore.py`
  - a restore stopped after each of its steps: `test_restore.py::test_a_stopped_restore_blocks_a_plain_start_and_the_same_command_finishes_it`
  - two backups at once and repeated `hub backup`: `test_backups.py`, `test_hub_lifecycle.py::test_ten_backups_in_a_row_leave_no_partial_directory_and_the_rotation_holds`
  - a migration that fails five starts in a row: `test_hub_lifecycle.py::test_a_migration_that_fails_five_starts_in_a_row_keeps_one_backup_for_its_version`
  - `join` in a hub home refused, ordinary commands there fail with `HubHomeError`, no `local` machine: `test_join.py`, `tests/operations/test_store_guard.py`, `test_hub_lifecycle.py::test_an_ordinary_command_in_the_hub_home_is_refused_and_changes_no_row`
  - random bytes, plaintext HTTP and malformed HTTP leave stderr with the serving line only: `test_noise.py`
  - an unwritable `backup_dir` with no migration due; a backup that fails partway leaves no partial directory: `test_start.py`, `test_backups.py`
  - keep counts hold for backups and the log: `test_hub_lifecycle.py::test_keep_counts_hold_for_backups_and_the_log`
  - `join --set-aside-local` then `leave`, a connection opened before fails its next write, each stop is finished by `join` or `leave`: `test_set_aside.py`
  - a store set aside while a reader is open keeps every row: `test_set_aside.py::test_a_store_set_aside_while_a_reader_is_open_keeps_every_row`
  - `join --set-aside-local` as the first command on a schema-10 store: `test_set_aside.py::test_join_as_the_first_command_on_a_schema_ten_store_migrates_it_and_sets_it_aside`
  - each `JoinError` case exits 3 and saves nothing, `leave` in an unjoined home exits 0: `test_join.py`, `test_set_aside.py`
  - a hub call that sets no acting machine fails on its first insert, and the hub store holds no `local` machine after the fixture run: `test_handle_call.py::test_a_run_with_act_as_skipped_fails_the_first_insert_as_hub_error`, `tests/store/test_acting_machine.py`, `_no_local_machine` in `test_hub_lifecycle.py`
  - `update_live.py` `update` and `restore` against a copy of a schema-10 store: `tests/scripts/test_update_live.py`
  - 261 can serve a new operation by adding to the served list and `run_served`: proven by `test_handle_call.py::test_a_seventh_operation_is_served_by_adding_to_the_list_and_the_runners`

**Commit**: `docs: document the hub, the door and the client`
