---
docType: tasks
slice: context-forge-event-seam
project: amoeba
lld: user/slices/108-slice.context-forge-event-seam.md
dependencies: [101, 102, 103, 106]
projectState: Slices 101–104 are merged (store schema 5, tenant seam, inbox, verdicts and findings). Slices 105–107 are planned with reviewed tasks and may not be merged when this file starts. 108 needs 106's `changes` table, `ChangeKind`, feed invariant test, and attempts-sidecar helpers. There is no `amoeba.upstream.context_forge`, no CF watch storage, and no tenant that reads `projects.json`. This slice adds migration 008, the `watch_cf` kind, the reader and diff, `CFWatchTenant`, two listings, and `docs/cf-contract.md`.
dateCreated: 20261007
dateUpdated: 20261007
status: not_started
---

## Context Summary

- Working on the **context-forge-event-seam** slice (108), the eighth slice of initiative 100.
- **Current state:** `Store` is built from mixins; SQL lives in `sql_*.py`, row mapping in `mapping_*.py`, vocabularies in `*_models.py`. Inbox kinds are a `SubmissionKind` member + a payload model in `inbox/envelope.py` (`KIND_PAYLOAD_MODELS`) + an effect (`KIND_EFFECTS`, `store/inbox.py`). Tenants implement `Tenant.tick(host) -> bool` (`process/host.py`); `InboxTenant` (`process/inbox_tenant.py`) is the model, and the host gives `project_ids()` and `store_for(project_id)` (one shared `Store` per project). `LISTINGS` in `cli/inspect.py` is the listing registry. `capture_version_label(timeout_seconds)` and `VERSION_UNAVAILABLE` are in `process/observers/cf_readback.py`. `tests/fixtures/cf/` holds only `cf_get_amoeba.json`.
- **Dependencies:** 101–103 through their contracts. **106 supplies** the `changes` table and trigger convention, `ChangeKind`, `tests/store/test_feed_invariant.py`, `AttemptsSidecar` use, and the durable-write helper. Task 1.1 checks that 106 is merged; if it is not, stop.
- **What this slice delivers:** `amoeba.upstream.context_forge` (location rule, reader, diff); migration 008 (`cf_watches`, `cf_snapshots`, feed trigger); `ChangeKind.cf_project_changed`; the `watch_cf` kind; `CFWatchTenant`; three settings with flags; `inspect cf-watches` and `cf-snapshots`; `docs/cf-contract.md` and contract updates; `CHANGELOG.md`.
- **Not in this slice:** any change to Context Forge; writing to nodes (D2); gate and review state; `customData`; per-field `worktrees` diffs; recovering intermediate CF states; changes to 102's `cf get --json` observer.
- **Next planned slice:** 109, then 110 (end-to-end).

**Branch:** all implementation happens on `108-slice.context-forge-event-seam`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging comes after the code review (Phase 7).

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/108-slice.context-forge-event-seam.md` at the named section (Data Flow, D1–D5, Patterns and Conventions, API Contracts, Database / Storage Schema). Exact signatures, column lists, and failure tables are settled there. Keep every new source file near 300 lines.

**Commit cadence:** a commit never holds untested behavior. A task that says "committed with Task N.M" is committed together with its test task, which follows immediately; every other task commits on its own.

**Triggers and tables grow in place.** Migration 008 is unreleased until this slice merges; later tasks that touch it edit the one file. Never create another migration.

**Task-level mechanisms the LLD does not spell out** (each is flagged where it appears and reported to the PM in Task 8.6): the watch-revision counter (Task 4.3), the idle-tick subprocess reading (Task 6.4), and the `cf_max_attempts` flag (Task 5.1).

**Section map (this file):** 1 branch and real fixtures; 2 upstream reader and diff; 3 store models, migration, operations, feed; 4 the `watch_cf` kind; 5 settings. **File 2 (`...-2.md`):** 6 `CFWatchTenant`; 7 listings and wiring; 8 end-to-end, docs, final validation.

---

## Section 1: Branch and Real Fixtures

### Task 1.1: Create the branch, confirm prerequisites, record the starting state
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 2
**Objective**: Work on the right branch, on top of 106, with a known baseline.

**Steps**:
- [ ] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [ ] Create `108-slice.context-forge-event-seam` from the target; if it exists, switch to it
- [ ] Confirm 106 is merged: `src/amoeba/store/schema/006_*.sql` exists and `ChangeKind` is defined in `src/amoeba/store/feed_models.py`. If either is missing, stop and tell the PM
- [ ] Record in your notes: the highest file in `src/amoeba/store/schema/` and `EXPECTED_SCHEMA_VERSION`. The new migration is `max + 1`. The LLD assumes 007 exists, making this `008`; if the highest is `006` (107 unmerged), this slice takes `007`, and you tell the PM. Use the actual number wherever these tasks say "008"
- [ ] Find and note where 106's `AttemptsSidecar` consumers and the durable-write helper live (`grep -rn "write_durably" src/`); Task 6.5 imports them
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once and note any pre-existing failure. If any fail before changes, stop and tell the PM

**Success Criteria**:
- [ ] On the slice branch; baseline suite, `ruff`, `pyright` clean
- [ ] Migration number and helper locations noted; no commit needed

---

### Task 1.2: Capture real `projects.json` fixtures
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 3
**Objective**: Byte-real upstream input for the reader tests (LLD Technical Requirements: no hand-built file stands in for the real shape).

**Steps**:
- [ ] Run `cf --version` and note it. The LLD observed the shape on CF 0.18.0; if the installed version differs, that is expected (versions are not pinned), but compare the captured shape to the LLD's "Interfaces Required" and stop and tell the PM about any difference in the two facts Amoeba depends on (a JSON array of objects, each with a string `id`)
- [ ] In a throwaway `CONTEXT_FORGE_DATA_DIR` (`mktemp -d`), never the user's real CF data directory, run `cf init --lite --no-ide --name fixture-a` from a temp project directory, then a second `cf init` for `fixture-b`. Run `cf set phase "Phase 4: Slice Design" -p fixture-a` so the first record carries a pointer. Create a worktree overlay with `cf worktree` only if the installed `cf` supports it without side effects outside the temp directory; otherwise record that no overlay fixture could be captured and tell the PM
- [ ] Save the resulting `projects.json` as `tests/fixtures/cf/projects_two_projects.json`. Scan it for `customData`, paths, or secrets; the file is expected to hold only temp paths. Do not hand-edit values, with one exception: if `customData` is present, remove only that key and say so in the README entry
- [ ] Add a `projects.json` section to `tests/fixtures/README.md` in the existing style: capture date 20261007, how it was produced, which records and keys it holds, and what is deliberately absent (no overlay, if none was captured)

**Success Criteria**:
- [ ] The fixture parses as a JSON array of objects with string `id`s
- [ ] README entry written; no real user data in the fixture
- [ ] Commit, e.g. `test: add real projects.json fixture`

**Files to Create**: `tests/fixtures/cf/projects_two_projects.json`
**Files to Modify**: `tests/fixtures/README.md`

---

## Section 2: The Upstream Reader and Diff

### Task 2.1: `resolve_cf_data_dir`, with tests
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 2
**Objective**: Mirror CF's location rule in exactly one place (LLD "Interfaces Required", Location; Settings).

**Steps**:
- [ ] Create `src/amoeba/upstream/__init__.py` and `src/amoeba/upstream/context_forge/__init__.py`, and `projects_file.py`. Define the file name `projects.json` and the environment variable names once as constants
- [ ] `resolve_cf_data_dir(environ, platform, home) -> Path` taking its inputs as arguments (no hidden reads, so tests need no monkeypatching): `CONTEXT_FORGE_DATA_DIR` if set and non-empty; else `~/.config/context-forge` on `darwin`; else `$XDG_CONFIG_HOME/context-forge`, falling back to `~/.config/context-forge`. A docstring says the rule is copied from CF and names where `cf-contract.md` records that
- [ ] Add `tests/upstream/__init__.py` and `tests/upstream/test_cf_location.py`: each branch (override set, empty override, macOS, Linux with and without `XDG_CONFIG_HOME`)

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(upstream): add Context Forge data directory resolution`

**Files to Create**: the package files above, `tests/upstream/test_cf_location.py`

---

### Task 2.2: `read_projects_file` and its errors, with tests
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 3
**Objective**: Read the file into records keyed by `id`, depending on exactly two facts (LLD "Upstream reader", D1).

**Steps**:
- [ ] In `projects_file.py` define `CFRecord` (an immutable mapping of the object's keys to opaque JSON values, with `id` exposed), `ProjectsFileMissing`, and `ProjectsFileUnrecognized`, both carrying the path and a reason string
- [ ] `read_projects_file(path) -> Mapping[str, CFRecord]`: missing or unreadable file → `ProjectsFileMissing`; not JSON, not an array, an element that is not an object, an element without a string `id`, or a duplicate `id` → `ProjectsFileUnrecognized` with a reason naming which. No other key is interpreted
- [ ] The reason text for a non-array must contain "not an array" (the LLD walkthrough asserts it)
- [ ] Add `tests/upstream/test_cf_projects_file.py`. Success paths use `projects_two_projects.json` only: both records returned by id; unknown keys survive untouched. Failure paths write small files in `tmp_path`: not JSON, `{}`, an element that is a string, an object without `id`, a numeric `id`, a duplicate `id`, and a missing file. Also: a file with an extra, never-seen key still parses (the contract is two facts)

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(upstream): read the Context Forge projects file`

**Files to Create**: `tests/upstream/test_cf_projects_file.py`
**Files to Modify**: `src/amoeba/upstream/context_forge/projects_file.py`, package `__init__.py`

---

### Task 2.3: `diff.py` — tracked fields and changed keys, with tests
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 3
**Objective**: The diff rule of LLD D4, with `IGNORED_KEYS` defined once.

**Steps**:
- [ ] Create `src/amoeba/upstream/context_forge/diff.py` with `IGNORED_KEYS = {"updatedAt", "customData"}` and the reserved marker for a vanished record (`"$present"`) as a named constant
- [ ] `tracked_fields(record) -> Mapping`: the record minus `IGNORED_KEYS`, and the same stripping applied to each entry of `worktrees` (recursive into overlays only, per D4). Do not mutate the input
- [ ] `changed_keys(before, after) -> tuple[str, ...]`: `before`/`after` are tracked-field mappings or `None`. `(None, x)` → every key of `x`; `(x, None)` → the marker; both `None` or equal → empty; otherwise the sorted keys whose values differ (deep JSON equality, including keys present on only one side). `worktrees` is reported as one key, never per sub-field
- [ ] Add `tests/upstream/test_cf_diff.py`: only `updatedAt` moved → empty; only `customData` moved → empty; `developmentPhase` moved → that key; key added and key removed → each reported; an overlay's own `updatedAt` moved → empty, an overlay's `activeSlice` moved → `["worktrees"]`; first sight → every key; vanished → `["$present"]`; reappeared (`None`→ fields after a vanish) → every key. Use records taken from the real fixture, modified in memory, where a value is needed

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(upstream): add Context Forge field diff`

**Files to Create**: `src/amoeba/upstream/context_forge/diff.py`, `tests/upstream/test_cf_diff.py`

---

## Section 3: Store Models, Migration, Operations, Feed

### Task 3.1: `cf_models.py`, with tests
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 2
**Objective**: Define the vocabulary and transfer objects once (LLD "Patterns and Conventions", "API Contracts").

**Steps**:
- [ ] Create `src/amoeba/store/cf_models.py` (no SQL, no `sqlite3`, no import from `amoeba.upstream`), following `feed_models.py` style
- [ ] `CFWatchState` as a `StrEnum` with exactly `pending, ok, missing, unreachable, unrecognized, failed`
- [ ] Frozen dataclasses: `CFWatch` (`project_id, cf_project_id, active, state, detail, registered_at, updated_at`), `CFSnapshot` (per the LLD API table), and `CFSnapshotInput` (what `record_cf_snapshot` takes: project, cf id, present, fields, changed, cf_updated_at, version_label)
- [ ] Add `ChangeKind.CF_PROJECT_CHANGED = "cf_project_changed"` in `feed_models.py` (106's enum) and update 106's test that pins the exact member set
- [ ] Add `tests/store/test_cf_models.py`: the state set and values are exact; dataclasses are frozen

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass; the 106 member-set test is updated, not weakened
- [ ] Commit, e.g. `feat(store): add Context Forge watch models`

**Files to Create**: `src/amoeba/store/cf_models.py`, `tests/store/test_cf_models.py`
**Files to Modify**: `src/amoeba/store/feed_models.py`, the test pinning `ChangeKind`

---

### Task 3.2: Migration 008 (tables and trigger) and `sql_cf.py`
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 3
**Objective**: Create the schema and emission trigger (LLD "Database / Storage Schema") with every name defined once in Python.

**Steps**:
- [ ] Read 106's migration for the trigger convention (payload built with `json_object`, `recorded_at` copied from the row) and `sql_feed.py` for the pairing convention
- [ ] Create `src/amoeba/store/schema/008_cf_watches_and_snapshots.sql` (use the number from Task 1.1): `cf_watches` and `cf_snapshots` exactly per the LLD, including the `(project_id, cf_project_id, id)` index. No `IF NOT EXISTS`; no `CHECK` on vocabulary columns; nothing to backfill
- [ ] In the same file, the `AFTER INSERT ON cf_snapshots` trigger per the LLD: kind `'cf_project_changed'`, `node_id` null, `subject_id` the snapshot id, payload `cf_project_id`, `present` as a JSON boolean literal (`json(iif(new.present, 'true', 'false'))`), and `changed` copied via `json(new.changed)`; `recorded_at = new.observed_at`
- [ ] Create `src/amoeba/store/sql_cf.py` holding every table and column name and every statement for the two tables. Statements arrive with Tasks 3.5–3.6; here define names and the insert and select-by-key statements the migration test needs
- [ ] Set `EXPECTED_SCHEMA_VERSION` to the new number in `store/migrations.py`; update every test pinning the old version or table set (search `tests/` for `EXPECTED_SCHEMA_VERSION`, `schema_version`)

**Success Criteria**:
- [ ] A fresh store reaches the new version with both tables and the trigger
- [ ] Full suite passes with updated pins
- [ ] Committed with Task 3.3

**Files to Create**: `008_cf_watches_and_snapshots.sql`, `src/amoeba/store/sql_cf.py`
**Files to Modify**: `store/migrations.py`, version-pinning tests

---

### Task 3.3: Test migration 008
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 2
**Objective**: Prove a version-7 store upgrades intact (LLD Technical Requirements).

**Steps**:
- [ ] Add `tests/store/test_migration_008.py` modeled on 106's `test_migration_006.py`: build a store at the previous version (`migrate(connection, expected_version=<previous>)`) holding nodes, a verdict, a message, and `changes` rows; migrate to the new version
- [ ] Assert every pre-existing row is intact, `cf_watches` and `cf_snapshots` are empty, the `changes` count is unchanged (the upgrade emits nothing), and the index and trigger exist in `sqlite_master`

**Success Criteria**:
- [ ] New tests pass; full suite passes
- [ ] Commit, e.g. `feat(store): add migration 008 for Context Forge watches and snapshots`

**Files to Create**: `tests/store/test_migration_008.py`

---

### Task 3.4: `mapping_cf.py`, with tests
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 2
**Objective**: Row → record mapping that fails on unknown vocabulary, like the other `mapping_*.py` files.

**Steps**:
- [ ] Create `src/amoeba/store/mapping_cf.py` with `map_cf_watch` and `map_cf_snapshot`. Follow `mapping_feed.py`: an unknown `state` raises `UnknownVocabularyValueError`; `fields` decodes to a mapping and `changed` to a tuple of strings; `present` and `active` from 0/1; a malformed JSON column raises rather than returning `{}`
- [ ] Add `tests/store/test_mapping_cf.py`: a valid row of each maps; an unknown state raises; malformed `fields` and a non-array `changed` raise

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(store): add Context Forge row mapping`

**Files to Create**: `src/amoeba/store/mapping_cf.py`, `tests/store/test_mapping_cf.py`

---

### Task 3.5: Snapshot operations (`CFWatchOperations`, part 1)
**Owner**: Junior AI
**Dependencies**: Task 3.4
**Effort**: 3
**Objective**: Record and read snapshots (LLD "API Contracts", store additions).

**Steps**:
- [ ] Add statements to `sql_cf.py` and create `src/amoeba/store/cf_watches.py` with `CFWatchOperations(StoreBase)`: `cf_snapshots(project_id, *, cf_project_id=None)` (oldest first), `latest_cf_snapshot(project_id, cf_project_id)`, `cf_snapshot(project_id, snapshot_id)` (raises `CFSnapshotNotFoundError`, defined in `cf_models.py` beside the other store errors' style), and `record_cf_snapshot(CFSnapshotInput)`
- [ ] `record_cf_snapshot` is in-process only (writer guard) and stores `fields` and `changed` as JSON text exactly as given; it does not import `amoeba.upstream`. Use 106's transaction pattern (`with self._connection:` then the `BEGIN IMMEDIATE` constant, imported not redefined). It does not set watch state; the tenant does that in the same transaction through Task 3.6's method, so expose a private no-transaction insert for that composition
- [ ] Add `CFWatchOperations` to `Store`'s bases; export `CFWatch`, `CFWatchState`, `CFSnapshot`, `CFSnapshotInput`, `CFSnapshotNotFoundError` from `store/__init__.py`

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 3.6

**Files to Create**: `src/amoeba/store/cf_watches.py`
**Files to Modify**: `store/sql_cf.py`, `store/store.py`, `store/__init__.py`, `store/cf_models.py`

---

### Task 3.6: Watch operations (`CFWatchOperations`, part 2) and tests for 3.5–3.6
**Owner**: Junior AI
**Dependencies**: Task 3.5
**Effort**: 3
**Objective**: Read watches, set state, and pin the whole mixin.

**Steps**:
- [ ] Add `cf_watches(project_id)` and `set_cf_watch_state(project_id, cf_project_id, state, detail)`. The latter is a no-op (no write, no `updated_at` change) when state and detail are unchanged, and raises if the watch does not exist. Add the composition used by the tenant: one method that records a snapshot and sets the watch state in a single transaction
- [ ] Add `tests/store/test_cf_watches.py`: a snapshot round-trips (fields, changed, `present`, `cf_updated_at` kept as written); `latest_cf_snapshot` is the newest per key and `None` before any; `cf_snapshots` filters by cf id and is oldest first; `cf_snapshot` of an unknown id raises; two cf ids and two projects stay independent; state set to the same value writes nothing; a failure partway through the combined method leaves neither the snapshot nor the state change (force it with an invalid state)
- [ ] Add a public-API check that the new names are exported (follow `tests/test_public_api.py`)

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(store): add Context Forge snapshot and watch operations`

**Files to Create**: `tests/store/test_cf_watches.py`
**Files to Modify**: `store/cf_watches.py`, `store/sql_cf.py`, `tests/test_public_api.py`

---

### Task 3.7: Trigger tests and the invariant extension
**Owner**: Junior AI
**Dependencies**: Task 3.6
**Effort**: 3
**Objective**: Pin the feed entry, and extend 106's invariant (LLD "Feed invariant").

**Steps**:
- [ ] Add to `tests/store/test_feed_triggers.py`: recording a snapshot emits exactly one `cf_project_changed` with `node_id` null, `subject_id` the snapshot id, and payload keys `cf_project_id`, `present` (a JSON boolean, not 0/1), `changed` (an array equal to the stored value); a rolled-back record emits none; `set_cf_watch_state` alone emits none
- [ ] Extend the scripted sequence in `tests/store/test_feed_invariant.py` with a linked CF project: a first snapshot, a change, a disappearance. Add the reconciliation rule: snapshot ids from `cf_project_changed` equal the `cf_snapshots` table
- [ ] Extend 106's "dropped trigger" parametrized test with the `cf_snapshots` trigger
- [ ] Confirm 106's "every `ChangeKind` appears" and "trigger literals match the enums" checks pass with the new member; do not weaken them

**Success Criteria**:
- [ ] All feed trigger and invariant tests pass, including the dropped-trigger case for the new trigger
- [ ] Commit, e.g. `test(store): reconcile Context Forge snapshots with the feed`

**Files to Modify**: `tests/store/test_feed_triggers.py`, `tests/store/test_feed_invariant.py`

---

## Section 4: The `watch_cf` Kind

### Task 4.1: Add the `watch_cf` inbox kind and its effect
**Owner**: Junior AI
**Dependencies**: Task 3.7
**Effort**: 3
**Objective**: Link or unlink a CF project (LLD "Inbox, the `watch_cf` kind", "Linking a CF project").

**Steps**:
- [ ] Follow the three-part rule in `SubmissionKind`'s docstring: add `WATCH_CF = "watch_cf"`; add `WatchCFPayload` (`cf_project_id: str`, non-empty, validated by pydantic; `active: bool`) to `inbox/envelope.py` and `KIND_PAYLOAD_MODELS`; add the effect to `KIND_EFFECTS` in `store/inbox.py`
- [ ] Effect: upsert `cf_watches`. A new watch, or one going from inactive to active, starts `pending` with null detail. Deactivating sets `active` false and leaves state as it is. A replay of the same submission is a no-op. The id is stored verbatim; it is never parsed (D3)
- [ ] Confirm `amoeba submit watch-cf` appears automatically with `--cf-project` and `--active true|false` (`cli/submit.py` derives subcommands from `SubmissionKind`). Fix only if it does not
- [ ] Update the tests pinning the kind set and any kind-coverage tests

**Success Criteria**:
- [ ] `amoeba submit watch-cf --help` lists `--cf-project` and `--active`
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 4.2

**Files to Modify**: `store/inbox_models.py`, `inbox/envelope.py`, `store/inbox.py`, `store/sql_cf.py`

---

### Task 4.2: Test the kind and its effect
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 2
**Objective**: Pin registration semantics.

**Steps**:
- [ ] Add `tests/store/test_watch_cf.py`: link creates a `pending` watch; link, deactivate, reactivate returns it to `pending`; deactivating an id never linked creates an inactive watch (the effect is an upsert, per the LLD); a replayed submission changes nothing; an empty `cf_project_id` is rejected at the envelope (`tests/inbox/test_envelope.py` style)
- [ ] Extend `tests/cli/test_submit.py` with `submit watch-cf` flag parsing (`--active true`, `--active false`, a missing `--cf-project`)

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(inbox): add watch_cf kind`

**Files to Create**: `tests/store/test_watch_cf.py`
**Files to Modify**: `tests/cli/test_submit.py`

---

### Task 4.3: The watch-revision counter
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 3
**Objective**: Let the tenant's idle tick detect a newly added or reactivated watch without a query (LLD Data Flow; Functional Requirements, last bullet). **Task-level mechanism: the LLD requires the in-memory cache but not how it learns of `watch_cf` applies. Report this choice to the PM in Task 8.6.**

**Steps**:
- [ ] Confirm by reading `process/project_stores.py` and `process/inbox_tenant.py` that the `Store` returned by `host.store_for(project_id)` is the same handle the inbox applies submissions on. If it is not, stop and tell the PM
- [ ] Add to the `CFWatchOperations` mixin an in-memory integer `cf_watch_revision` (property, starts 0), incremented after the `watch_cf` effect commits any change to a watch row (link, reactivate, deactivate). It is process memory only, never persisted. A replay that changes nothing does not bump it, and `set_cf_watch_state` (the tenant's own writes) never does. The tenant (Task 6.1) re-reads the project's watches only when the revision differs from the one it last saw, so a deactivation is noticed too
- [ ] Add `tests/store/test_cf_watch_revision.py`: a link bumps it; a replay does not; a deactivate does; a reactivate does; `set_cf_watch_state` does not; a failed (rolled-back) apply does not; a fresh `Store` handle starts at 0

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(store): track watch additions in memory for the idle tick`

**Files to Create**: `tests/store/test_cf_watch_revision.py`
**Files to Modify**: `store/cf_watches.py`, `store/inbox.py`

---

## Section 5: Settings

### Task 5.1: Add the three settings and flags
**Owner**: Junior AI
**Dependencies**: Task 4.3
**Effort**: 2
**Objective**: `cf_data_dir`, `cf_scan_interval_seconds`, `cf_max_attempts` (LLD "Settings"). **`cf_max_attempts` has no flag in the LLD's text, which lists flags only for the data directory; add one for consistency with `--detection-max-attempts` and report it in Task 8.6.**

**Steps**:
- [ ] Add to `ProcessSettings`: `cf_data_dir: Path` defaulting through `resolve_cf_data_dir` (call it once at module import with the real environment, as `DEFAULT_SQ_RUNS_DIR` is built; no second copy of the rule), `cf_scan_interval_seconds = 2.0`, `cf_max_attempts = 3`, with docstring entries stating what each bounds, in the file's style
- [ ] Add `start` flags in `cli/settings_flags.py`: `--cf-data-dir`, `--cf-scan-interval-seconds`, `--cf-max-attempts` (use `positive_int`), and map them where the other flags are mapped
- [ ] Extend the existing settings and flag tests: defaults come from `ProcessSettings` (flags repeat none); each flag overrides; `--cf-max-attempts 0` is refused; `--cf-data-dir` beats `CONTEXT_FORGE_DATA_DIR`. `start --help` lists the three flags

**Success Criteria**:
- [ ] Existing settings, flag, and lifecycle tests pass; new cases pass
- [ ] Commit, e.g. `feat(process): add Context Forge watch settings`

**Files to Modify**: `process/settings.py`, `cli/settings_flags.py`, existing settings and flag tests

---
