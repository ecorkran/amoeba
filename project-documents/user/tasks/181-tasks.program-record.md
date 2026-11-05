---
docType: tasks
slice: program-record
project: amoeba
lld: user/slices/181-slice.program-record.md
dependencies:
- 101
- 103
- 122
- 123
- 128
- 144
projectState: Initiatives 100, 120 and 140 are complete and merged. The project store
  is at schema version 15 (`src/amoeba/store/schema/`). `process/inbox_tenant.py`
  owns the inbox file lifecycle; `process/project_stores.py` is the one module that
  opens a store read-write; `runner/tick.py` has no program stage; `inspection/` has
  no program listings. Nothing under `src/amoeba/program/`, `store/program_schema/`
  or `programs/` exists. The parent slice plan and architecture already carry decision
  D4 (the requests initiative index lives on the member registration).
dateCreated: 20261104
dateUpdated: 20261104
status: not_started
turns: 23
promptTokens: 1182786
cachedTokens: 1083463
cacheWriteTokens: 99293
completionTokens: 22018
durationSeconds: 159.5
costUsd: 0.726052
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.7260517
    completionTokens: 22018
---

## Context Summary

- Working on the **program-record** slice (181), the second slice of initiative 180 (program coordination). It adds a program store, a program inbox, a read-only program stage in the Runner's tick, member readability, and program listings. Nothing runs differently afterwards: a project in no program, and a supervisor with no program store, tick exactly as after 140.
- **Current state:** see `projectState`.
- **Dependencies:** the store machinery, inbox layout and drain (100), the tick and the tenant's failure handling (120), `resolve_checkout` (128), the blocked rows as extended through slice 144 (initiative 140). No dependency on slice 180's pipeline.
- **What this slice delivers:** `ProgramStore` and `store/program_schema/`; `inbox/program_envelope.py`, `submit_program()` and the `register-program` / `register-member` subcommands; `process/inbox_drain.py` and `process/program_inbox_tenant.py`; the `amoeba.program` package with `read_member`; `runner/program/stage.py`; `inspection/program.py` and the `inbox` `queue` column; the updated locality rule and proof; contract docs and CHANGELOG.
- **Next planned slice:** 182 (program concept as a source).

**Branch:** read the target (`cf config get git.integration_branch`; empty means `main`). Before Task 1.1, create `181-slice.program-record` from the target and work there. No task merges or pushes. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/181-slice.program-record.md` at the named decision (D1 to D10) or section. Source paths are relative to `src/amoeba/` unless they start with `tests/`, `docs/` or `project-documents/`. Follow `.claude/rules/python.md`: ruff and strict pyright, no silent fallbacks, every `try/except` justified. Read each file before editing it. Keep source files near 300 lines and functions near 50. Every vocabulary is a `StrEnum` defined once; no comparison value is repeated as a literal elsewhere.

**Order:** work tasks in file order. Section 1 is five pure refactors, each committed on its own before any program code exists (LLD, Risk Assessment): after each, every existing test must pass unchanged, except the test moves and additions Tasks 1.4 and 1.5 name. No task needs a model, a key or live CF; only the walkthrough in Task 9.2 needs `sq`.

**Commit cadence:** commit only at the `**Commit**:` markers. Run `uv run ruff format .` before each commit, and `uv run ruff check .` and `uv run pyright` before markers that follow Python changes.

---

## 1. Refactors with no behavior change

- [x] **1.1 Parameterize `store/migrations.py`** (effort 2)
  - [x] Make the migrations package and the expected version **required parameters with no default** of `_migration_files` and of the runner (rename the runner's generalized form, e.g. `migrate_package`), so a new store line that omits its version fails instead of silently getting 15. Keep `migrate(connection, expected_version=EXPECTED_SCHEMA_VERSION)` as the project store's thin wrapper over it, so existing callers and tests are unchanged; `Store` passes `amoeba.store.schema` and 15, each constant defined once.
  - [x] `read_schema_version` and the error behavior (`StoreSchemaError` on newer or missing migrations) are unchanged.
  - [x] Success: `uv run pytest tests/test_migrations.py tests/store` passes with no test edited; `uv run pyright` passes.

Note: tests/test_migrations.py's monkeypatch of _migration_files had to take the new package argument (typed function replaces the zero-arg lambda); no other test edited.

**Commit**: `refactor: parameterize the migration runner by package and version`

- [x] **1.2 Lift the connection helpers to a shared module** (effort 3)
  - [x] Create `store/connection.py` holding what `Store._connect`, `_connect_read_only` and `_migrate_or_close` do today, plus the read-only version check (version must equal the expected one, never migrates, never creates). Parameterize by migrations package and expected version. Error mapping to `StoreCorruptError`, `StoreBusyError`, `StorePermissionError`, `StoreSchemaError` is preserved exactly, with the same log lines.
  - [x] `Store.open`, `open_read_only` and `open_temporary` call it. `Store` keeps its public signatures.
  - [x] Success: `uv run pytest tests/test_store.py tests/test_read_only_open.py tests/test_store_safety.py tests/test_failure_modes.py` passes with no test edited.

Note: tests/test_failure_modes.py's open_temporary failure test patched Store._connect and store.migrate; it now patches amoeba.store.connection.connect and migrate_package (patch points only, same assertions).

**Commit**: `refactor: lift the store connection helpers into a shared module`

- [x] **1.3 Extract `process/inbox_drain.py` from `InboxTenant`** (effort 4)
  - [x] Read `process/inbox_tenant.py` and `inbox/layout.py`. Move the per-file lifecycle (drain order and batch, parse and quarantine on an envelope error, apply, attempt counting, parking at the limit, durable moves, sidecar writes, the reused-id warning) into one class parameterized by the inbox root, the parse function, and the apply function. Project attribution (`no_store_for_project`, `create_project` routing) and `_apply` stay in `InboxTenant`.
  - [x] The drain reads `inbox_batch_size` and `inbox_max_attempts` from the host's settings, as the tenant does today. No new setting.
  - [x] `InboxTenant` is behaviorally identical: same terminal places, same log messages, same exception behavior below and at the attempt limit.
  - [x] Success: `uv run pytest tests/inbox tests/process` passes with no test edited; no lifecycle logic remains duplicated between the two modules.

**Commit**: `refactor: extract the inbox file lifecycle into a shared drain`

- [x] **1.4 Move `resolve_checkout` to `amoeba.upstream.context_forge`** (effort 2)
  - [x] Move `resolve_checkout`, `Checkout` and `CheckoutUnresolved` from `runner/dispatch/checkout.py` into the `upstream/context_forge` package (a module beside the snapshot types, exported from the package). They depend only on `amoeba.store` types and CF constants; check no `amoeba.runner` import comes along.
  - [x] Update the callers: `runner/dispatch/facts.py`, `build_view.py`, `planner.py` and `candidates.py`; `runner/resolutions/planner.py`; `runner/answering/sources.py`. Confirm with `grep -rn "dispatch.checkout import" src tests` (the `checkout_check` and `checkout_reads` modules stay where they are). Delete `runner/dispatch/checkout.py` once nothing imports it.
  - [x] Move `tests/runner/dispatch/test_checkout.py` to the matching `tests/upstream/` location; update imports in `tests/runner/dispatch/test_planner.py`, `test_checkout_reads.py` and `dispatch_support.py`.
  - [x] Success: `uv run pytest tests/runner tests/upstream tests/test_import_boundaries.py` passes; behavior is unchanged.

Note: the one 'projectPath' literal in the moved module now uses FIELD_PROJECT_PATH, so the package's field-names-spelled-once test passes unedited.

**Commit**: `refactor: move resolve_checkout to the context_forge upstream module`

- [x] **1.5 Move the repo-relative path rule to `store/paths.py`** (effort 2)
  - [x] Add `validate_repo_relative_path(entry, *, glob_allowed)` to `store/paths.py`, carrying the checks of `_checked_rules_path` in `runner/project_config.py` (not absolute, no `..` segment, names a file, `*` in the last segment only when `glob_allowed`). `GLOB_WILDCARD` moves from `runner/answering/passages.py` into `store/paths.py`, defined once there; `passages.py` and `project_config.py` import it from `amoeba.store.paths`.
  - [x] The `AfterValidator` on the `RulesPath` annotation in `runner/project_config.py` (which `rules_paths` uses) calls it with `glob_allowed=True`; delete `_checked_rules_path`. Error messages stay the same.
  - [x] Add tests in `tests/test_paths.py` for both modes: each rejection and an accepted path. Existing project-config tests stay unedited and green.
  - [x] Success: `uv run pytest tests/test_paths.py tests/runner` passes.

**Commit**: `refactor: move the repo-relative path rule to store paths`

## 2. The program store

- [x] **2.1 Paths, vocabularies and models** (effort 2)
  - [x] In `store/paths.py` define once `program_dir(store_dir)` (`programs/`) and `program_store_path(store_dir)` (`programs/programs.sqlite3`), and the directory and file names as constants. Tests in `tests/test_paths.py`: both paths; `discover_project_ids` on a directory holding `programs/programs.sqlite3` and a top-level `programs.sqlite3` (a project named `programs`) lists only the project.
  - [x] Create `store/program_models.py` with the `StrEnum`s `ProgramSubmissionKind` (`register_program`, `register_member`), `ConsumptionMode` (`from_source`, `from_release`), `ProgramRejection` (the five codes in the LLD API Contracts), and frozen dataclasses `Program`, `Member` and `ProgramSubmissionRecord` with the fields in LLD "API Contracts" and "Provides to Other Slices" (`updated_at` on `Program` and `Member`). Reuse `SubmissionOutcome` (`applied`, `rejected`) from `store/inbox_models.py`.
  - [x] Define the requests-initiative range (100, 799) once, as constants beside the models. Export the new names from `amoeba.store`.
  - [x] Success: the path tests pass; `uv run pyright` passes.

Note: tests/test_public_api.py's expected export set gained the new names (the export is this task's own requirement).

- [x] **2.2 Schema 001 and the pinning test** (effort 2)
  - [x] Create the package `store/program_schema/` (mirror how `store/schema/` is packaged, including package data) with `001_program_record.sql` exactly as the LLD "Database / Storage Schema" gives it; fill `schema_meta` to the same shape as the project store's `001`.
  - [x] Test in `tests/store/test_program_schema.py`: apply the migration to a scratch connection through the parameterized runner (package `amoeba.store.program_schema`, version 1); assert the table set; assert each enum's values equal the `CHECK` list of its column and the initiative range equals the `BETWEEN` bounds (read from `sqlite_master`); assert two members with one `project_id` in different programs is refused by `UNIQUE`; assert an override naming its own provider is refused by `CHECK`.
  - [x] Success: tests pass; a newer-stamped program store raises `StoreSchemaError`.
- [x] **2.3 `ProgramStore`: opens and reads** (effort 3)
  - [x] Create `store/program_store.py`: `ProgramStore.open(path)`, `open_read_only(path)`, `close`, context manager, over `store/connection.py` with `amoeba.store.program_schema` and version 1 (constant defined once). Same guarantees as `Store`: `open_read_only` never migrates, never creates, cannot write.
  - [x] Reads: `programs()`, `members(program_id)`, `program_of(project_id)`, `submission(id)`, `submissions()` in `applied_seq` order. Overrides are carried on `Member` as a mapping. SQL statements and row mapping follow the existing `sql_*.py` / `mapping_*.py` split; keep each file near 300 lines.
  - [x] Success: `uv run pyright` passes.

Note: ProgramStore is exported from amoeba.store, as are validate_repo_relative_path and GLOB_WILDCARD (Runner import rule 11 allows only public store names, so the Task 1.5 imports in passages.py and project_config.py now come from amoeba.store rather than amoeba.store.paths); tests/test_public_api.py's expected export set gained these names.

- [x] **2.4 Tests for opens and reads** (effort 3)
  - [x] `tests/store/test_program_store_open.py`, mirroring `tests/test_read_only_open.py`: `open` creates and stamps version 1; reopen is idempotent; `open_read_only` on a missing file raises `StorePermissionError` and creates nothing; on a corrupt file raises `StoreCorruptError`; on a file at another version raises `StoreSchemaError` and leaves it unchanged; a write through the read-only handle raises.
  - [x] Reads against rows inserted by the test with plain SQL: `program_of` for a member, a non-member and an empty store; `members` with overrides; `submissions` order.
  - [x] Success: tests pass.

**Commit**: `feat: add the program store with schema 001, vocabularies and reads`

- [x] **2.5 `apply_submission` and `register_program` writes** (effort 3)
  - [x] Add `apply_submission(*, submission_id, kind, submitted_by, submitted_at, payload) -> ProgramSubmissionRecord`, in a new module (as `Store` does with `_submission_writer.py`) composed into `ProgramStore`. One `BEGIN IMMEDIATE` transaction: a reused id returns the existing record untouched (first wins); otherwise apply the kind's writes and record the submission `applied` with `applied_seq` and `applied_at`.
  - [x] `register_program` (LLD D3): creates the program or replaces it whole, so the concept location, member set and override set become exactly the body. An identical re-submission is `applied` and changes no row.
  - [x] Timestamps use the apply time (the submission's `applied_at`). `registered_at` is set on creation and never changes. `Member.updated_at` advances only when that member's index, mode or overrides change (a new member gets it at creation). `Program.updated_at` advances when the concept location changes, a member is added or removed, or any member changes, so it dates the member list; an identical re-submission moves neither.
  - [x] Success: `uv run pyright` passes.
- [x] **2.6 Tests for `register_program` writes** (effort 3)
  - [x] `tests/store/test_program_apply_program.py`: create; replace with a member left out (it is gone, with its overrides); an identical re-submission is `applied` and every table, `updated_at` included, is unchanged except the new submission row; the timestamp rules in Task 2.5 (a changed mode advances that member and the program only; a removed member advances the program only; `registered_at` never moves).
  - [x] First wins: a reused id is a no-op, also with different content, and writes no second submission row. A failure inside the transaction leaves no submission row.
  - [x] Success: tests pass.
- [x] **2.7 `register_program` rejections** (effort 3)
  - [x] Checks run before any write, in this order; the first failure records the submission `rejected` with reason `"<code>: <detail>"` and writes nothing else: `member_of_other_program` (a listed project is in a different program; checked in code before the `UNIQUE` can fire), `concept_member_not_member` (against the set being written), `override_not_member` (against the set being written).
  - [x] `member_referenced` is reserved: define the check as a named hook that currently finds nothing, run after the three above, and say so in a comment.
  - [x] Success: `uv run pyright` passes.
- [x] **2.8 Tests for `register_program` rejections** (effort 2)
  - [x] `tests/store/test_program_reject_program.py`: each of the three codes from a body that triggers it, recorded `rejected` with the `"<code>: <detail>"` reason and `applied_seq` rising; no other row written (compare table contents before and after); with two problems in one body the first in the order above is the one recorded.
  - [x] Success: tests pass.
- [x] **2.9 `apply_submission`: `register_member`** (effort 3)
  - [x] Upsert one member into an existing program; removes nothing; replaces that member's whole override set; timestamps by the rules in Task 2.5. Rejections, same recording as Task 2.7: `unknown_program`, `member_of_other_program`, `override_not_member` (override dependent not a member after the write).
  - [x] Success: `uv run pyright` passes.
- [x] **2.10 Tests for `register_member`** (effort 2)
  - [x] `tests/store/test_program_apply_member.py`: add a new member; update an existing member's index, mode and overrides (override set replaced, other members untouched, timestamps per Task 2.5); an identical member re-submission changes no row; each rejection (`unknown_program`, `member_of_other_program`, `override_not_member`) recorded and nothing else written; the concept member still a member afterwards.
  - [x] Success: tests pass.

**Commit**: `feat: apply program and member registration in one transaction`

## 3. Program envelope, submission and CLI

- [ ] **3.1 Payload models** (effort 3)
  - [ ] Create `inbox/program_envelope.py` (or a sibling `program_payloads.py` to stay near 300 lines). Define the payload field names as constants beside `ProgramSubmissionKind` and pin them to the models by a test, as `inbox_models.py` does for project kinds.
  - [ ] Pydantic models per the LLD "Bodies" table, **unknown keys refused**: `program_id` (`validate_path_component`), `concept_member` and member `project_id` (`validate_project_id`), `concept_path` (`validate_repo_relative_path(glob_allowed=False)`, stripped, non-blank), `members` (non-empty, no project id twice), `member`, `requests_initiative` (strict integer in the range constants), `consumed` (`ConsumptionMode`), `overrides` (required mapping, may be `{}`, must not name the member itself, values are modes). Validation errors name the field.
  - [ ] Success: `uv run pyright` passes.
- [ ] **3.2 Tests for payload models** (effort 3)
  - [ ] `tests/inbox/test_program_payloads.py`: a valid body of each kind; each failure in LLD Success Criteria (missing `requests_initiative`, `concept_member` or `concept_path`; index 99, 800, `true`, `"790"`, `790.0`; unknown mode; self override; duplicate member; unknown key; empty members; wrong-kind fields such as `member` on `register_program`) with the field named in the error; the pin test for field names.
  - [ ] Success: tests pass.
- [ ] **3.3 Envelope and `parse_program_envelope`** (effort 3)
  - [ ] Envelope fields: `envelope_version`, `id`, `kind`, `submitted_by`, `submitted_at`, `payload`; **no project id**. `parse_program_envelope(raw)` raises the existing `EnvelopeError` with the existing `QuarantineReason` values that apply: `unparseable_envelope`, `unknown_envelope_version`, `unknown_kind`, `invalid_payload`. Mirror `inbox/envelope.py` and reuse its helpers rather than copying them.
  - [ ] Tests `tests/inbox/test_program_envelope.py`: valid envelope of each kind; each of the four reasons from a real-format envelope file (write the JSON the way `submit_program` will); for `invalid_payload`, the error detail names the offending field (a body missing `requests_initiative` gives a detail containing it); a project kind sent to the program parser is `unknown_kind`.
  - [ ] Success: tests pass.
- [ ] **3.4 `submit_program()`** (effort 3)
  - [ ] In `inbox/submit.py` (or a sibling module if it would pass ~300 lines) add `submit_program(kind, payload, submitted_by, submission_id=None, store_dir=None)`: validates first and raises `InvalidSubmissionError` with nothing written; otherwise writes durably (`write_durably`) to `programs/inbox/new/` using `layout` called with `program_dir(store_dir)`. Returns the id; first id wins, as `submit()`. Export from `amoeba.inbox`; update `tests/inbox/test_inbox_public_api.py`.
  - [ ] Tests `tests/inbox/test_submit_program.py`, mirroring `test_submit.py`: file lands in `programs/inbox/new/` and nowhere in `inbox/`; invalid payload writes nothing; supplied id is reused; `store_dir` resolution matches `submit()`.
  - [ ] Success: tests pass.
- [ ] **3.5 CLI subcommands** (effort 3)
  - [ ] Read `cli/submit.py`. Add `register-program` and `register-member` derived from `ProgramSubmissionKind` and the payload fields by the existing flag rule; program kinds take no `--project`; `--members` and `--member` take JSON. Each prints the submission id; `--id` reuses one; an invalid body exits 9 (`SUBMISSION_REFUSED`) naming the field.
  - [ ] Tests (extend `tests/cli/` using `cli_harness.py`): both commands against a temporary supervisor directory; the exit-9 refusal for a missing `requests_initiative`; `--project` is not accepted.
  - [ ] Success: tests pass; `amoeba submit --help` lists both.

**Commit**: `feat: add program submissions, the program envelope and submit subcommands`

## 4. Program inbox tenant and host wiring

- [ ] **4.1 Atomic creation and the program store holder** (effort 3)
  - [ ] In `process/project_stores.py`, make `_create_atomically` take the store class and use it for both kinds. Add the program store's read-write holder in the same module (the writer guard's one module): `open_program_store()` opens it if the file exists (start-up), `ensure_program_store()` creates it atomically if absent, a `program_store` property (`None` when absent), and `close_all` closes it. A failure to open at start is `StartupFailedError` naming the program store.
  - [ ] Tests (extend the `ProjectStores` tests in `tests/process/`): creation leaves no `.creating` file and no stranded WAL; an interrupted creation (a leftover `.creating` file) is replaced; start with a junk `programs.sqlite3` raises `StartupFailedError`; `close_all` closes it.
  - [ ] Success: tests pass; existing project-store tests unedited.
- [ ] **4.2 `ProgramInboxTenant`** (effort 4)
  - [ ] Create `process/program_inbox_tenant.py`: drains `programs/inbox/new/` through the shared drain (Task 1.3) with `parse_program_envelope`; the apply creates the store atomically if absent and calls `ProgramStore.apply_submission`. No project attribution. A store failure is counted beside the file, stops the process below `inbox_max_attempts`, and parks the file at the limit, exactly as for project submissions. Tenant name is a constant.
  - [ ] Compose it directly after `InboxTenant` in `process/tenants.py`, sharing `inbox_batch_size` and `inbox_max_attempts`.
  - [ ] Success: `uv run pyright` passes.
- [ ] **4.3 Tests for `ProgramInboxTenant`** (effort 4)
  - [ ] `tests/process/test_program_inbox_tenant.py`, mirroring the `InboxTenant` tests: a valid file applies, creates `programs/programs.sqlite3` on first use and is deleted after the commit; a rejection (`unknown_program`) is recorded and the file deleted; each of the four quarantine reasons moves the file to `programs/inbox/quarantine/` with its `.reason.json`, and for `invalid_payload` the sidecar's `detail` names the offending field; a store failure below the limit re-raises with a counter beside the file, and run through the process harness (`tests/host_harness.py`) the resident process exits as a store failure; at the limit the file is parked in `failed/`; a reused id with different content logs a warning and leaves the first record; a project file in `inbox/` is untouched by this tenant and the reverse; `standard_tenants` order is inbox, program inbox, then the rest.
  - [ ] Success: tests pass.
- [ ] **4.4 Start-up open and the Runner host member** (effort 3)
  - [ ] In `process/host.py` open the program store at start through the holder (4.1) and expose `program_store`; add `program_store: ProgramStore | None` to `RunnerHost` in `runner/tenant.py` (read every tick: it can appear at runtime). Update test hosts that implement the protocol.
  - [ ] Tests in `tests/test_host.py` style: no program store, the property is `None`; after a registration is drained, the same host's property is the open store; a corrupt program store at start is `STARTUP_FAILED` naming the program store (CLI exit via `tests/test_cli_lifecycle.py` patterns).
  - [ ] Success: tests pass.

**Commit**: `feat: drain the program inbox into the program store at runtime`

## 5. Member readability

- [ ] **5.1 `amoeba.program.members`** (effort 4)
  - [ ] Create the package `amoeba.program` with `members.py`: `MemberUnreadableReason` (`store_missing`, `store_unreadable`, `unlinked`, `snapshot_missing`, `checkout_unresolved`), `Readable` (keeps the resolved `Checkout` and the CF project id of the member's one link), `Unreadable(reason, detail)`, the alias `MemberState = Readable | Unreadable`, and `read_member(store_dir, member) -> MemberState`. Order per LLD D6; first failure wins.
  - [ ] The `detail` of each reason: `store_missing` names the expected file (`{project_id}.sqlite3`); `store_unreadable` is the `StoreError` text; `unlinked` says no link or how many links; `snapshot_missing` names the CF project id of the link that has no `observed` snapshot; `checkout_unresolved` is `CheckoutUnresolved`'s reason.
  - [ ] One directory check (`Path.is_dir` through `resolve_checkout`), no subprocess. A `StoreError` from the member's read-only open or reads becomes `store_unreadable`, in a specific `except` with the comment D6 requires; nothing else is caught. Zero links and two links are both `unlinked`, and none is chosen.
  - [ ] The package imports only `amoeba.store` and `amoeba.upstream`.
  - [ ] Success: `uv run pyright` passes.
- [ ] **5.2 Tests for `read_member` and the import rule** (effort 4)
  - [ ] `tests/program/test_read_member.py`, with stores, links and snapshots written by the test (use `tests/cf_fixture.py` helpers where they fit; no live CF or `sq`). One test per reason, each asserting the reason and a `detail` with the content named in Task 5.1: `store_missing`; `store_unreadable` for a corrupt file, a wrong schema version and a lock held past a short timeout; `unlinked` for no link and for two links; `snapshot_missing`; `checkout_unresolved`; and the readable case with a project that has no worktrees (checkout is the project path) and one whose worktree owns the member's index.
  - [ ] Precedence: a member failing two checks reports the earlier one. No exception escapes `read_member` for any reason above. The member's store file is unchanged after the call.
  - [ ] Import rule: read `tests/test_import_boundaries.py`; add the `amoeba.program` rule (imports only `amoeba.store` and `amoeba.upstream`) and confirm inspection may import `amoeba.program` but not `amoeba.runner`. The rule fails when a deliberate `amoeba.runner` import is added to `program/members.py` (revert it).
  - [ ] Success: `uv run pytest tests/program tests/test_import_boundaries.py` passes.

**Commit**: `feat: add member readability with a closed vocabulary of reasons`

## 6. The program stage

- [ ] **6.1 `ProgramStage` and its place in the tick** (effort 3)
  - [ ] Create `runner/program/stage.py`: `ProgramStage.run(project_id) -> Program | None`. `None` when the host has no program store, or the project is in no program; otherwise one `program_of` read. No member store opened, nothing written, `tick.wrote` untouched.
  - [ ] Read `runner/tick.py` and `runner/tenant.py` to see how `ProjectTick` is built each tick. Pass the host's current `program_store` into the tick on every tick, and in `ProjectTick.run` call the stage directly after `_answer_resolutions()` and before Observe, discarding the result (two lines; extract nothing from `tick.py`, D7).
  - [ ] A `StoreError` from the program store propagates (it is in `STORE_FAILURES`); any other exception is left to the tenant's existing project-scoped `unexpected_fault`.
  - [ ] Success: `uv run pyright` passes.
- [ ] **6.2 Tests for the stage** (effort 4)
  - [ ] `tests/runner/program/test_stage.py`: `None` with no store; `None` for a project in no program; the `Program` for a member; the store appearing between two ticks is seen on the second; a closed or corrupt program store raises a `STORE_FAILURES` member through the tenant and the process exits as a store failure; a non-store exception reaches `unexpected_fault` for that project only and other projects still tick.
  - [ ] Order: with a recording stage, assert it runs after a resolution is answered and before the observer is called.
  - [ ] Regression: tick the same scripted project with no program store, with a program store holding an unrelated program, and with a program store holding its own program; the store writes, issued commands and journal entries are identical across the three (reuse the harness in `tests/runner/test_end_to_end.py`).
  - [ ] Success: tests pass; the existing Runner suite passes.
- [ ] **6.3 Load tests for the program inbox and the tick's program read** (effort 3)
  - [ ] Add `tests/load/test_program_load.py`, using `tests/load/load_harness.py` and mirroring `test_inbox_concurrent.py` and `test_runner_tick_load.py` (read both first). Case 1: several submitter processes concurrently `submit_program()` a few hundred `register_member` bodies (some ids resubmitted) while `ProgramInboxTenant` drains; afterwards every reported id has exactly one record, no `applied_seq` repeats, and `programs/inbox/new/`, `quarantine/` and `failed/` are empty. Case 2: many projects, each in the program store's program, tick under the harness; every tick still stays within its deadline and the program read adds no member-store open.
  - [ ] Set each bound by measuring first, then at roughly twice the slowest observation (the rule `test_inbox_concurrent.py` states), and record the measurement and date in the module docstring.
  - [ ] Success: `uv run pytest tests/load/test_program_load.py` passes. `.github/workflows/ci.yml` already runs `tests/load`, so no CI change.

**Commit**: `feat: add the program stage to the Runner tick, read-only`

## 7. Program listings

Read `inspection/__init__.py` (the registry), `inspection/listing.py` and `inspection/core.py` (`_blocked_rows`, `all_blocked_rows`) first. Listings open the program store read-only; with no program store each returns no rows; a program store at the wrong schema version raises, as a project store does.

- [ ] **7.1 `program` listing** (effort 3)
  - [ ] Create `inspection/program.py` with the rows of LLD D8: `program_id`, `project_id`, `requests_initiative`, `consumed`, `overrides` (`dependent=mode`, comma-separated, empty when none), `concept_path` (concept member's row only), `state` (`readable` or the reason value), `detail`. State comes from `read_member`. Register it as a supervisor-level listing.
  - [ ] Tests `tests/inspection/test_program.py`: no program store gives no rows; two members, one readable and one per unreadable reason; the override string; `concept_path` only on the concept row; a wrong-version store raises.
  - [ ] Success: tests pass.
- [ ] **7.2 `program-submissions` listing** (effort 2)
  - [ ] Rows `id`, `kind`, `submitted_by`, `submitted_at`, `outcome`, `reason` in `applied_seq` order; register it.
  - [ ] Tests (same file or a sibling): applied and rejected rows with their reasons; order; empty without a store.
  - [ ] Success: tests pass.
- [ ] **7.3 `program-blocked` listing** (effort 4)
  - [ ] Define the `member_unreadable` blocked-on kind once (`StrEnum` or constant beside the other blocked-on values; read how `blocked_on` is produced today). Columns are `program_id` followed by the `blocked` listing's columns.
  - [ ] For each program and member: if the member's store opens read-only, its rows from `_blocked_rows` unchanged, with `program_id`; if `read_member` is unreadable, one extra row with `blocked_on` = `member_unreadable`, `reason` = `"<reason>: <detail>"` and the node columns empty. A member whose store opens but is unlinked appears both ways. A member store that does not open adds only the unreadable row.
  - [ ] No member's failure raises. A `StoreError` from reading the blocked rows of a store that did open is caught in a specific `except` (with a comment saying why), and that member gets the `member_unreadable` row with `store_unreadable: <error>` and no node rows. Only the program store's own failures raise.
  - [ ] Tests: members' blocked nodes carry `program_id`; each unreadable reason yields its row; the both-ways case; a corrupt member store does not stop the other members' rows; a member whose store opens but whose blocked-row read fails (inject the fault; see `tests/fault_injection.py`) gives the `store_unreadable` row and the other members' rows still list; inspection works with the process stopped and writes nothing.
  - [ ] Success: tests pass.
- [ ] **7.4 `inbox` listing gains `queue`** (effort 3)
  - [ ] In `inspection/inbox.py` list both roots; add a **last** column `queue` (`project` or `program`, defined once). Existing column names and positions are unchanged; a supervisor with no program files lists exactly the rows it listed before, plus the key.
  - [ ] Update the existing tests that assert the full column tuple (`tests/inbox/test_listings.py` and any CLI or serve test that does). Add cases: a program file in `new/`, a program quarantine with its reason, a program file in `failed/`.
  - [ ] Success: tests pass.
- [ ] **7.5 Registry, CLI and server** (effort 2)
  - [ ] Confirm `amoeba inspect program | program-blocked | program-submissions` appear through the registry-derived CLI, and `/v1/listings/{name}` serves them with no route change. Update tests that enumerate listing names (`tests/test_cli_inspect.py`, `tests/serve/`).
  - [ ] Success: `uv run pytest tests/inspection tests/inbox tests/serve tests/test_cli_inspect.py` passes.

**Commit**: `feat: add program, program-blocked and program-submissions listings`

## 8. Locality rule, proofs and contract docs

- [ ] **8.1 Locality proof** (effort 4)
  - [ ] Read `tests/contract/oracle.py` (`locality_problems`) and the harness that builds its scenario. Extend the scenario so a program is registered through the program inbox before the proof runs.
  - [ ] Add two checks to `locality_problems`: the program store's tables are exactly the allowed set (programs, members, overrides, program submissions, `schema_meta`), and no project store has a program table. The top-level `*.sqlite3` check is unchanged.
  - [ ] Negative tests in `tests/contract/test_oracle.py`: add a `nodes` table, separately a `blocked_states` and a `question_records` table, to a scratch program store, and a program table to a project store; each makes the proof fail naming the table.
  - [ ] Success: `uv run pytest tests/contract` passes, including the negatives.
- [ ] **8.2 Writer guard** (effort 2)
  - [ ] In `tests/test_writer_guard.py` also flag `ProgramStore.open(` (read-write) outside `process/project_stores.py`, not `open_read_only`. Add scan tests beside the existing ones: a violation is found, a wrapped call is found, `open_read_only` is ignored.
  - [ ] Success: `uv run pytest tests/test_writer_guard.py` passes against the real source tree.

**Commit**: `test: extend the locality proof and the writer guard to the program store`

- [ ] **8.3 `docs/store-contract.md`** (effort 2)
  - [ ] "Store locality" per LLD D9; a new section "The program store" (the `ProgramStore` methods, the schema line starting at 1, creation on first submission, read-only access, failure modes); the migrations section notes the second line and the parameterized runner.
  - [ ] Success: each LLD "API Contracts" method appears; no claim contradicts the code.
- [ ] **8.4 `docs/inbox-contract.md`** (effort 2)
  - [ ] New section "Program submissions": the root and layout, the envelope (no project id), the two bodies and their field rules, the rejection codes (with `member_referenced` marked reserved), quarantine reasons, how to read an outcome; the inspection listings, including the `queue` column.
  - [ ] Success: the field table matches `inbox/program_envelope.py`.
- [ ] **8.5 `docs/process-contract.md`** (effort 2)
  - [ ] "The supervisor directory" table gains `programs/`; the tenants list gains the program inbox tenant after the inbox; the Runner tick gains the program stage between resolutions and Observe, with its failure rule (a program store failure exits the process, so it stops projects in no program too); "The writer model" says the program store has the same single writer; inspection lists the three listings.
  - [ ] Success: the stage's place matches `ProjectTick.run`.

## 9. Final validation

- [ ] **9.1 Full checks** (effort 1)
  - [ ] Run `uv run ruff format .`, `uv run ruff check .`, `uv run pyright` and `uv run pytest` (the bare run, which excludes the live and load tiers).
  - [ ] Run the load tests that cover the changed paths, by explicit path because the bare run ignores `tests/load`: `uv run pytest tests/load/test_runner_tick_load.py tests/load/test_inbox_concurrent.py tests/load/test_program_load.py`. The two existing files' asserted bounds must hold without edits.
  - [ ] Success: all pass, with no existing test skipped, weakened or edited to pass, apart from the moves and edits Tasks 1.4, 1.5, 3.4, 4.4, 7.4, 7.5, 8.1 and 8.2 name. Tests added to existing files by other tasks are not edits. If a check fails, fix its cause and re-run.

**Commit**: `docs: document the program store, program inbox and program stage`

- [ ] **9.2 Verification walkthrough** (effort 3)
  - [ ] Run `command -v sq`. If it is absent, write a line starting `BLOCKED:` under this task saying `amoeba start` cannot run without `sq`, leave the task unchecked and stop. Nothing before this task depends on it.
  - [ ] Run steps 1 to 5 of the LLD "Verification Walkthrough" against a throwaway supervisor directory (`mktemp -d`), never the real one. Step 5's `pytest` command must pass.
  - [ ] Success: every step shows what the LLD says it shows; any difference is fixed in code, and the closing report says what each step showed. After any fix, re-run Task 9.1's checks.
  - [ ] Delete the throwaway directory when done.

Write no walkthrough note into this file. If a step needed a code fix, commit it at the marker below; this task's check-off commits with Task 9.3.

**Commit**: `feat: correct what the program record walkthrough found` (only when a step needed a code fix; use `test:` when only tests changed)

- [ ] **9.3 CHANGELOG** (effort 1)
  - [ ] Under `[Unreleased] / Added`, one or two lines for slice 181 in the existing style: the program store and inbox, `register-program` and `register-member`, member readability, the program stage, the three listings and the `queue` column, 100's locality rule updated. Note that nothing runs differently yet.
  - [ ] Success: entry present, concise.

**Commit**: `docs: add slice 181 to the changelog`
