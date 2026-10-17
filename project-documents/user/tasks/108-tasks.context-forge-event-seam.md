---
docType: tasks
slice: context-forge-event-seam
project: amoeba
lld: user/slices/108-slice.context-forge-event-seam.md
dependencies: [101, 102, 103, 106, 107]
projectState: Slices 101–107 are merged (store schema 7, tenant seam and `ProcessSettings`, listing registry, inbox kinds through `check`, 106's change feed with `ChangeKind` and the feed invariant test, 107's migration 007). No Context Forge file watcher, `cf_links`/`cf_snapshots` tables, or `link_cf_project` kind exists. This slice adds migration 008, the `amoeba.upstream.context_forge` parser and diff, `CFWatchTenant`, the `link_cf_project` kind, `ChangeKind.CF_PROJECT_CHANGED`, two listings, two settings, and `docs/context-forge-contract.md`.
dateCreated: 20261016
dateUpdated: 20261016
status: in_progress
---

## Context Summary

- Working on the **context-forge-event-seam** slice (108), the eighth slice of initiative 100.
- **Current state:** `Store` is built from mixins (`store/store.py`); SQL lives in `sql_*.py`, row mapping in `mapping_*.py`, word lists and records in `*_models.py`. `EXPECTED_SCHEMA_VERSION` is 7 (`store/migrations.py`). An inbox kind is a `SubmissionKind` member and payload-key constants (`store/inbox_models.py`), a payload model in `KIND_PAYLOAD_MODELS` (`inbox/envelope.py`), and an effect in `KIND_EFFECTS` (`store/inbox.py`, 319 lines, over budget). Tenants are built in `build_tenants` (`cli/lifecycle.py`); `ReviewDetectionTenant` (`process/review_detection.py`) is the pattern. `ProcessSettings` is in `process/settings.py`, its flags in `cli/settings_flags.py`. Listings are registered in `LISTINGS` (`cli/inspect.py`), with siblings `inspect_checks.py`, `inspect_evidence.py`, `inspect_feed.py`. `tests/store/test_feed_invariant.py` ties triggers to `ChangeKind`. `tests/fixtures/cf/` already holds `cf_get_amoeba.json`.
- **Dependencies:** 101–103, 106, 107 through their documented contracts.
- **What this slice delivers:** a stat-signature watch of CF's `projects.json` in a tenant; per-link snapshots of a field projection; one `cf_project_changed` feed entry per real change; failures recorded as outcomes. See the LLD "Technical Scope".
- **Next planned slice:** 109 (moves every `inspect` listing module into `amoeba.inspection`), then 110.

**Branch:** all implementation happens on `108-slice.context-forge-event-seam`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges; merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/108-slice.context-forge-event-seam.md` at the named section (D1–D9, "Observed shape", "API Contracts", "Database / Storage Schema"). Exact field lists, outcome table, payload shapes, and the tick algorithm are settled there. Keep every new source file near 300 lines; `store/inbox.py` and `cli/inspect.py` are at or over budget, so new concerns go in the new modules the LLD names.

**Commit cadence:** a commit never holds untested behavior. A task that says "committed with Task N.M" is committed together with its test task, which follows immediately; every other task commits on its own.

**Open item for the PM (LLD D7):** the LLD says the PM must confirm D7 (`cf_data_dir` setting with `--cf-data-dir`, no read of `CONTEXT_FORGE_DATA_DIR`) before this phase. Task 1.1 gates on it. If D7 changes, Tasks 6.1, 6.2, 6.4, 6.5, and 6.6 change.

**Task-level additions to the LLD** (named by no LLD table): none. Anything a task needs that the LLD does not settle is a question for the PM, not a guess.

**Section map.** 1 baseline and fixture; 2 parser and diff (pure); 3 migration 008 and store; 4 the `link_cf_project` kind; 5 `CFWatchTenant`; 6 settings, wiring, listings, end-to-end, docs, validation.

---

## Section 1: Baseline and Fixture

### Task 1.1: Create the branch and record the starting state
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 1
**Objective**: Work on the right branch from a clean baseline, with 107 confirmed merged.

**Steps**:
- [x] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [x] Confirm `src/amoeba/store/schema/007_judge_samples_checks_and_progress.sql` exists and `EXPECTED_SCHEMA_VERSION` is 7. If not, stop and tell the PM (LLD "Prerequisites")
- [x] Ask the PM to confirm LLD D7. If not confirmed, stop and wait
- [x] Create `108-slice.context-forge-event-seam` from the target; if it exists, switch to it
- [x] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each. If any fails before changes, stop and tell the PM

**Success Criteria**:
- [x] On the slice branch; baseline suite, `ruff`, and `pyright` clean
- [x] No commit needed

---

### Task 1.2: Capture and reduce the real `projects.json` fixture
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 2
**Objective**: A real CF data file for the parser tests (LLD Technical Requirements, "Privacy of the fixture").

**Steps**:
- [x] Copy `~/.config/context-forge/projects.json` (or the directory `CONTEXT_FORGE_DATA_DIR` names; ask the PM if neither exists) into a scratch directory outside the repo. Do not write to the original
- [x] Reduce to exactly three entries: this repository's entry (it has `worktrees`), one entry without `worktrees`, and one other. Leave entries otherwise unedited
- [x] Check the result for secrets and local content you would not publish. `customData` values may be emptied (no test reads them); no other edit is allowed. Anything else suspicious: ask the PM
- [x] Save as `tests/fixtures/cf/projects.json`. Add a `tests/fixtures/README.md` entry: capture date (today), source, the reduction, and any `customData` edit. Record the observed CF version as a dated observation, not a pin
- [x] Confirm the fixture matches the LLD "Observed shape": array of objects with string `id`; the amoeba entry has `worktrees` with a `default` worktree holding `developmentPhase`, `activeSlice`, `activeTaskFile`. If the real shape differs, stop and tell the PM

**Success Criteria**:
- [x] Fixture valid JSON, three entries, README entry present
- [x] Commit, e.g. `test: add real Context Forge projects.json fixture`

**Files to Create**: `tests/fixtures/cf/projects.json`
**Files to Modify**: `tests/fixtures/README.md`

---

## Section 2: Parser and Diff (pure, no store)

### Task 2.1: Add the result types and field lists
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 2
**Objective**: Define the projection's types and the field lists once (LLD D2, D3, D4).

**Steps**:
- [x] Create package `src/amoeba/upstream/context_forge/` with `__init__.py`, in the style of `upstream/squadron/`
- [x] In `projects_file.py` define: `PROJECTS_FILE_NAME = "projects.json"`; two tuples, the project-level and worktree-level projected field names, exactly as the LLD "Observed shape" lists them (`updatedAt` is not in either)
- [x] Define frozen types: `CFProjectState` (project fields mapping, worktree-id → fields mapping, `cf_updated_at | None`, with `to_json()` producing `{"project": {...}, "worktrees": {...}}` holding only keys present), `CFFieldChange` (`worktree_id: str | None`, `field`, optional `from`/`to`, with a JSON form that omits an absent `from`/`to`), and `CFReadFailure` (outcome word, detail)
- [x] Hold `CFReadFailure`'s outcome as a `str` that Task 5.1 maps to `CFSnapshotOutcome`, and say so in a module comment: the store imports nothing from upstream, and upstream imports nothing from the store (`tests/upstream/test_import_direction.py`)

**Success Criteria**:
- [x] `ruff`, `pyright` pass
- [x] Committed with Task 2.4

**Files to Create**: `upstream/context_forge/__init__.py`, `projects_file.py`

---

### Task 2.2: Implement `parse`
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 3
**Objective**: `parse(data: bytes, cf_project_id: str) -> CFProjectState | CFReadFailure`, applying exactly the rules of the LLD D4 table.

**Steps**:
- [x] Return the outcome, scope, and detail for each case in the D4 table; only the rules that decide which entry and worktree a value belongs to are checked
- [x] Only keys present are projected, copied as given. `updatedAt` goes to `cf_updated_at` when it is a string
- [x] Each detail string is specific enough to identify the rule that failed; define each message where it is raised, not duplicated in tests (tests check a distinguishing substring)

**Success Criteria**:
- [x] `ruff`, `pyright` pass
- [x] Committed with Task 2.4

**Files to Modify**: `upstream/context_forge/projects_file.py` (split into a sibling module if it passes ~300 lines)

---

### Task 2.3: Implement `diff_states`
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 3
**Objective**: A pure `diff_states(previous | None, current) -> tuple[CFFieldChange, ...]` per LLD D3.

**Steps**:
- [x] Create `diff.py`. `previous=None` lists every present field as added (`to` only)
- [x] Absent vs `null` are different: `from` omitted when the key was absent, `to` omitted when it became absent. A worktree added or removed appears as its fields added or removed
- [x] Order: project level (`worktree_id` None) first, then by worktree id, then by field name; equal states give an empty tuple

**Success Criteria**:
- [x] `ruff`, `pyright` pass
- [x] Committed with Task 2.4

**Files to Create**: `upstream/context_forge/diff.py`

---

### Task 2.4: Table-test the parser and diff
**Owner**: Junior AI
**Dependencies**: Tasks 2.2, 2.3
**Effort**: 3
**Objective**: Every row of D4's table and every D3 rule, on the real fixture.

**Steps**:
- [x] Create `tests/upstream/context_forge/` (with `__init__.py` if neighbours have one) and a loader for `tests/fixtures/cf/projects.json`
- [x] Parser, unedited fixture: the amoeba entry parses with the `default` worktree's `activeSlice`; the entry without `worktrees` parses with an empty worktree map; an unknown id → `missing`
- [x] Parser defects, each derived from the fixture bytes by one stated edit (state the edit in the test): non-JSON; top-level object; element with no `id`; duplicated linked id; `worktrees` not an array; duplicate worktree ids; empty file. Also: the same defect in a *different* entry's `worktrees` leaves the link `observed`
- [x] Parser: a changed `customData` or `updatedAt` alone gives equal projections; `cf_updated_at` is copied
- [x] Diff: first snapshot (all added); changed value (`from`/`to`); field added; field removed; absent vs `null`; worktree added; worktree removed; project-level change (`worktree_id` None); ordering is stable regardless of input key order; equal states → empty
- [x] Add a test that the field tuples are defined once, modeled on `tests/upstream/test_field_names_defined_once.py`; extend `test_import_direction.py` if it enumerates packages

**Success Criteria**:
- [x] New tests pass; full suite, `ruff`, `pyright` pass
- [x] Commit, e.g. `feat(upstream): parse projects.json into a watched projection and diff it`

**Files to Create**: `tests/upstream/context_forge/test_projects_file.py`, `test_diff.py`

---

## Section 3: Migration 008 and Store

### Task 3.1: Add `cf_models.py`
**Owner**: Junior AI
**Dependencies**: Task 2.4
**Effort**: 2
**Objective**: Define the outcome word list and record types once (LLD "API Contracts", "Patterns and Conventions").

**Steps**:
- [ ] Create `src/amoeba/store/cf_models.py` in the style of `check_models.py` (no SQL, no `sqlite3`, no pydantic, no import from `amoeba.upstream`)
- [ ] `CFSnapshotOutcome` (`observed`, `unreadable`, `unrecognized`, `missing`) as a `StrEnum`
- [ ] Frozen dataclasses `CFLink`, `CFSnapshot` (fields exactly as the LLD gives), and `CFSnapshotInput` (everything except `id`); `state` and `changed` are plain JSON-compatible values the store does not interpret

**Success Criteria**:
- [ ] `ruff`, `pyright` pass
- [ ] Committed with Task 3.3

**Files to Create**: `src/amoeba/store/cf_models.py`

---

### Task 3.2: Write migration 008 and bump the schema version
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 3
**Objective**: Two tables and one trigger, per the LLD "Database / Storage Schema" and D6.

**Steps**:
- [ ] Read `006_…` and `007_…` for trigger and table style. Create `src/amoeba/store/schema/008_context_forge_snapshots.sql`: `cf_links` (primary key `(project_id, cf_project_id)`), `cf_snapshots` (columns per the LLD, `INTEGER PRIMARY KEY AUTOINCREMENT`, index on `(project_id, cf_project_id, id)`)
- [ ] Trigger `changes_cf_project_changed`, `AFTER INSERT ON cf_snapshots`, every outcome, following 106's convention: `node_id` null, `subject_id` the snapshot id, payload `json_object('cf_project_id', …, 'outcome', …, 'changed', json(new.changed))`, `recorded_at = new.observed_at`. `changed` is null for failures. Do not repeat the outcome words in SQL. No trigger on `cf_links`
- [ ] Set `EXPECTED_SCHEMA_VERSION` to 8 in `store/migrations.py`; update any test that pins 7
- [ ] Add `ChangeKind.CF_PROJECT_CHANGED = "cf_project_changed"` in `store/feed_models.py`; export per `store/__init__.py` conventions

**Success Criteria**:
- [ ] A fresh store opens at version 8; `ruff`, `pyright` pass
- [ ] Committed with Task 3.3

**Files to Create**: `schema/008_context_forge_snapshots.sql`
**Files to Modify**: `store/migrations.py`, `store/feed_models.py`, `store/__init__.py`, tests pinning the version

---

### Task 3.3: Add SQL, mapping, and `CFOperations`
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 3
**Objective**: The store methods of the LLD "API Contracts" table.

**Steps**:
- [ ] `sql_cf.py`: every statement and column name for the two tables. `mapping_cf.py`: row → record, decoding the JSON columns
- [ ] `cf_snapshots.py` `CFOperations` mixin, added to `Store`: `cf_links(project_id)` (link order), `cf_snapshots(project_id)` (id order), `latest_cf_snapshots(project_id, cf_project_id) -> (latest | None, latest observed | None)`, `record_cf_snapshot(CFSnapshotInput) -> CFSnapshot` (in-process only; one insert; the trigger writes the change in the same transaction)
- [ ] Use 101's timestamp convention and the writer guard as `_check_writer.py` does. `observed_at` comes from the input, not from the store reading a clock
- [ ] Export the new names from `amoeba.store`; the store imports nothing from `amoeba.upstream`, `amoeba.process`, or `amoeba.feed`

**Success Criteria**:
- [ ] `ruff`, `pyright` pass
- [ ] Committed with Task 3.4

**Files to Create**: `store/sql_cf.py`, `store/mapping_cf.py`, `store/cf_snapshots.py`
**Files to Modify**: `store/store.py`, `store/__init__.py`

---

### Task 3.4: Test the store, the trigger, and the 7 → 8 upgrade
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 3
**Objective**: Pin the schema, the operations, and the feed invariant.

**Steps**:
- [ ] `tests/store/test_migration_008.py`, modeled on `test_migration_007.py`: a version-7 store with data from every earlier slice upgrades to 8 intact
- [ ] `tests/store/test_cf_snapshots.py`: record each of the four outcomes and read back; `latest_cf_snapshots` returns the latest row and the latest `observed` row (including when they differ, and when none exist); each insert adds exactly one `cf_project_changed` change with the payload keys of D6 and `changed` null for failures; `cf_links` and `cf_snapshots` order
- [ ] Extend `tests/store/test_feed_invariant.py`: its script gains one snapshot row per outcome plus a no-op re-check that must add nothing. The suite must fail if the trigger is missing (verify once by temporarily dropping it, then restore)
- [ ] Extend `tests/store/test_import_direction`-style check (wherever the store's import rule is tested) to cover `cf_*` modules

**Success Criteria**:
- [ ] New tests pass; full suite, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(store): add Context Forge links and snapshots (migration 008)`

**Files to Create**: `tests/store/test_migration_008.py`, `tests/store/test_cf_snapshots.py`
**Files to Modify**: `tests/store/test_feed_invariant.py`

---

## Section 4: The `link_cf_project` Kind

### Task 4.1: Add the kind, payload model, and effect
**Owner**: Junior AI
**Dependencies**: Task 3.4
**Effort**: 3
**Objective**: Linking through 103's three-part seam (LLD D5).

**Steps**:
- [ ] `store/inbox_models.py`: `SubmissionKind.LINK_CF_PROJECT = "link_cf_project"` and the payload key constant for `cf_project_id`, defined once
- [ ] `inbox/envelope.py`: `LinkCFProjectPayload` (`cf_project_id: str`, non-empty, no format check) in `KIND_PAYLOAD_MODELS`. An empty id is quarantined as invalid by the existing path
- [ ] Effect function in `cf_snapshots.py` (not `inbox.py`): insert `cf_links(project, cf_project_id, linked_at)`; linking again is a no-op. Register only its `KIND_EFFECTS` line in `store/inbox.py`
- [ ] The store reads no file and does not check that the id exists in CF

**Success Criteria**:
- [ ] `ruff`, `pyright` pass
- [ ] Committed with Task 4.2

**Files to Modify**: `store/inbox_models.py`, `inbox/envelope.py`, `store/inbox.py`, `store/cf_snapshots.py`

---

### Task 4.2: Test the kind and `amoeba submit link-cf-project`
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 3
**Objective**: Extend 103's completeness tests and prove the CLI form.

**Steps**:
- [ ] Update every test that pins the kind set or `KIND_EFFECTS` completeness (`tests/inbox/`, `tests/store/test_inbox_*`); read how 107's `check` kind extended them and do the same
- [ ] Effect test: first submission inserts a link; the second identical submission leaves one row; two Amoeba projects may link the same CF id; one project may link several
- [ ] Empty `cf_project_id` is quarantined as invalid
- [ ] `tests/cli/test_submit.py`: `amoeba submit link-cf-project --project P --by pm --cf-project-id ID` writes one inbox file whose flags come from the payload model (104's flag rule). Check the CLI help lists the new subcommand

**Success Criteria**:
- [ ] New tests pass; full suite, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(inbox): add link_cf_project submission kind`

**Files to Modify**: the tests named above

---

## Section 5: `CFWatchTenant`

### Task 5.1: Implement the tenant
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 4
**Objective**: One `tick` per the LLD "Data Flow" algorithm and D1, D3, D4, D9.

**Steps**:
- [ ] Read `process/review_detection.py` first and follow its structure: a small host protocol (settings, `stop_requested`, `project_ids`, `store_for`), injected clock, constructor takes `version_label`, injected data directory/file path, `name` property
- [ ] Add `cf_scan_interval_seconds` (1.0, with docstring entry) to `ProcessSettings` in `process/settings.py`; no flag
- [ ] Create `process/cf_watch.py`. `tick` does nothing until `cf_scan_interval_seconds` has passed since the last check. Then: gather links across open projects; `stat` the file to `(st_ino, st_size, st_mtime_ns)` or the OS error; if `(signature, links)` equals the remembered key, return with no read
- [ ] Otherwise read the bytes (an OS error means every link is `unreadable` with detail `{error class}: {strerror}`), `parse` once per link, load `latest_cf_snapshots`, and apply the LLD rules: for a state, diff against the latest `observed` row and record when there are changes **or** the latest row was not `observed` (then `changed: []` if nothing moved); for a failure, record only when the outcome or detail differs from the latest row. The remembered signature is the one taken before the read (D1)
- [ ] Remember `(signature, links)` only if every record succeeded. A store exception while recording is logged with `logger.exception` at ERROR and re-raised (D4). A broken CF file is not an exception: one ERROR log when the file goes bad, one INFO when it recovers, the process keeps running
- [ ] Map the parser's outcome strings to `CFSnapshotOutcome` in this module (the one place that knows both). Record `cf_updated_at` and the tenant's `version_label` on each row. No subprocess is started in `tick`
- [ ] Log the resolved file path at INFO on first tick (D7)
- [ ] Keep functions near 50 lines: split the per-link logic from the file read

**Success Criteria**:
- [ ] `ruff`, `pyright` pass
- [ ] Committed with Tasks 5.2 and 5.3

**Files to Create**: `src/amoeba/process/cf_watch.py`

---

### Task 5.2: Test the tenant's change recording
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 4
**Objective**: Pin the success-path behavior with an injected clock and a scratch directory; no `cf` on PATH.

**Steps**:
- [ ] Create `tests/process/test_cf_watch.py`, reusing `tests/process/conftest.py` and `detection_harness.py` patterns. The data file is written by temp-file-and-rename, as CF does, copied from `tests/fixtures/cf/projects.json`
- [ ] First check records one `observed` snapshot listing every present projected field as added (including the `default` worktree's `activeSlice`) and one `cf_project_changed` change
- [ ] Rewrite with the `default` worktree's `developmentPhase` moved: exactly one new snapshot whose `changed` names that worktree id and field with `from` and `to`. A project-level change has `worktree_id` None
- [ ] Rewrites that touch only another project, only `customData`, or only `updatedAt`: no new snapshot
- [ ] Interval gating: after the file is rewritten, a tick before `cf_scan_interval_seconds` has passed (by the injected clock) records nothing; advancing the clock past it records the change
- [ ] Unchanged signature and link set: nothing recorded. A new link with an unchanged file is checked. Re-checking an unchanged link writes nothing
- [ ] Two Amoeba projects linking the same CF id each record their own snapshots
- [ ] Restart: a new tenant instance over the same store, after the file changed while "down", records one snapshot per link on its first tick, and none when nothing changed

**Success Criteria**:
- [ ] New tests pass; full suite, `ruff`, `pyright` pass
- [ ] Committed with Task 5.3

**Files to Create**: `tests/process/test_cf_watch.py`

---

### Task 5.3: Test the tenant's failure handling
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 3
**Objective**: Failures are outcomes recorded once per transition (LLD D4 and Functional Requirements).

**Steps**:
- [ ] Create `tests/process/test_cf_watch_failures.py`
- [ ] File absent and permission denied → `unreadable` for every link, detail `{error class}: {strerror}`; invalid JSON and `{}` → `unrecognized` for every link; unknown id → `missing` for that link only; malformed `worktrees` in the linked entry → `unrecognized` for that link, and the same defect in another entry leaves the link `observed`
- [ ] Several intervals with the file still broken record one row per link, not one per interval. A changed detail records a new row
- [ ] Recovery: the next good read records `observed` with `changed: []` when nothing moved, and the diff after recovery is against the last `observed` row, not the failure row
- [ ] Log assertions: one ERROR when the file goes bad, one INFO when it recovers; the tick returns normally
- [ ] A store that raises on `record_cf_snapshot`: the error is logged at ERROR and re-raised, and the remembered key is not updated (the next tick tries again)
- [ ] Assert `tick` starts no subprocess (patch `subprocess` to fail if called)

**Success Criteria**:
- [ ] New tests pass; full suite, `ruff`, `pyright` pass
- [ ] Commit (with Tasks 5.1 and 5.2), e.g. `feat(process): add CFWatchTenant for projects.json changes`

**Files to Create**: `tests/process/test_cf_watch_failures.py`

---

## Section 6: Settings, Wiring, Listings, End-to-End, Docs

### Task 6.1: Add the settings and flag
**Owner**: Junior AI
**Dependencies**: Task 5.3
**Effort**: 2
**Objective**: `cf_data_dir` with a flag (LLD D7).

**Steps**:
- [ ] `process/settings.py`: `DEFAULT_CF_DATA_DIR = ~/.config/context-forge`; `ProcessSettings.cf_data_dir`, with a docstring entry. No environment read (`cf_scan_interval_seconds` was added in Task 5.1)
- [ ] `cli/settings_flags.py`: `--cf-data-dir PATH`, default taken from `ProcessSettings`, none repeated; map it back into `ProcessSettings`. No flag for the interval
- [ ] Update any test that enumerates settings or `start` flags

**Success Criteria**:
- [ ] `ruff`, `pyright` pass
- [ ] Committed with Task 6.2

**Files to Modify**: `process/settings.py`, `cli/settings_flags.py`

---

### Task 6.2: Wire the tenant and capture `cf --version` once
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 2
**Objective**: Register `CFWatchTenant` third in `build_tenants` (LLD D9).

**Steps**:
- [ ] Read `process/version_label.py` and `process/observers/cf_readback.capture_version_label`; reuse the existing capture with its explicit unavailable marker, do not write a new one
- [ ] In `cli/lifecycle.py` `build_tenants`, capture the CF label before the loop and register `CFWatchTenant(version_label=..., data_file=settings.cf_data_dir / PROJECTS_FILE_NAME)` after `ReviewDetectionTenant`, so the inbox drains first
- [ ] Update tests that pin the tenant set or order (`tests/test_cli_lifecycle.py`, `tests/process/test_review_detection_wiring.py` as a model); add a test that `cf --version` is captured once in `build_tenants`, and that an unavailable `cf` yields the marker and not a crash

**Success Criteria**:
- [ ] `ruff`, `pyright` pass; wiring tests pass
- [ ] Commit (with Task 6.1), e.g. `feat(cli): add --cf-data-dir and register CFWatchTenant`

**Files to Modify**: `cli/lifecycle.py`, tests named above

---

### Task 6.3: Add the `cf-links` and `cf-snapshots` listings and test them
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 3
**Objective**: The two listings of the LLD "CLI" table, each taking `--project` only.

**Steps**:
- [ ] Read `cli/inspect_checks.py` and its test `tests/cli/test_inspect_checks.py`. Create `cli/inspect_cf.py` with row functions; append two `Listing` entries to `LISTINGS` in `cli/inspect.py` (one line each plus the import)
- [ ] `cf-links`: columns `cf_project_id, linked_at`. `cf-snapshots`: `id, observed_at, cf_project_id, outcome, changed, detail, cf_updated_at`, where `changed` is summarized as field names in text mode and full in `--json`
- [ ] Create `tests/cli/test_inspect_cf.py`: empty project; rows after links and each outcome; text vs `--json`; no other flags accepted
- [ ] Update the test that pins the listing set (`tests/inbox/test_listings.py`, `tests/test_cli_inspect.py`)

**Success Criteria**:
- [ ] New tests pass; full suite, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(cli): add inspect cf-links and cf-snapshots`

**Files to Create**: `cli/inspect_cf.py`, `tests/cli/test_inspect_cf.py`
**Files to Modify**: `cli/inspect.py`, listing-set tests

---

### Task 6.4: End-to-end test through the real CLI
**Owner**: Junior AI
**Dependencies**: Task 6.3
**Effort**: 4
**Objective**: The LLD "Integration Requirements" test, with subprocesses and a scratch CF data directory.

**Steps**:
- [ ] Read `tests/cli/test_detection_end_to_end.py` and `tests/detection_e2e_harness.py`; build `tests/cli/test_cf_watch_end_to_end.py` on the same harness, extending it only where needed
- [ ] Steps per the LLD: create a project and link the fixture's amoeba entry; start a follower, then the process with `--cf-data-dir`; rewrite the file by temp-file-and-rename with one moved pointer; `kill -9` the process, rewrite again, start it
- [ ] Assert the follower output and `inspect cf-snapshots` agree, with one change per rewrite and nothing recorded twice. The test needs no `cf` on PATH (the `cf --version` marker path is exercised)
- [ ] Keep it deterministic: poll with a bounded timeout, no fixed sleeps as assertions

**Success Criteria**:
- [ ] Test passes repeatedly (run it 3 times); full suite passes
- [ ] Commit, e.g. `test: end-to-end CF watch across a kill -9 restart`

**Files to Create**: `tests/cli/test_cf_watch_end_to_end.py`

---

### Task 6.5: Write the contract docs and CHANGELOG
**Owner**: Junior AI
**Dependencies**: Task 6.4
**Effort**: 3
**Objective**: Document the observed shape and the deltas, without restating 106's trigger convention or 102's process semantics (LLD Technical Scope, last Included bullet).

**Steps**:
- [ ] Read `file-naming-conventions` for frontmatter. Create `docs/context-forge-contract.md`: the observed shape (dated, with the CF version it was observed on, as an observation not a dependency); the projection and why `updatedAt`/`customData` are excluded; the four outcomes and their scope; the change payload; D3's rules (first snapshot, recovery row); D7's directory rule; D8 (a snapshot claims no author; match a Runner write through `cf_updated_at`); D9 (label captured at start-up only); the in-place-write noise note
- [ ] Add only deltas to `docs/store-contract.md` (tables, methods, `CFSnapshotOutcome`), `docs/inbox-contract.md` (the kind and payload), `docs/feed-contract.md` (the `cf_project_changed` kind and payload), `docs/process-contract.md` (the tenant, two settings, flag). Add a `CHANGELOG.md` entry in its existing style
- [ ] `docs/store-contract.md` is already large: if the delta pushes a file past its limits, ask the PM before splitting

**Success Criteria**:
- [ ] Docs match shipped names (grep each documented name in `src/`); no restatement of 106/102 material
- [ ] Commit, e.g. `docs: add Context Forge contract and 108 deltas`

**Files to Create**: `docs/context-forge-contract.md`
**Files to Modify**: the four contract docs, `CHANGELOG.md`

---

### Task 6.6: Run the verification walkthrough and final validation
**Owner**: Junior AI
**Dependencies**: Task 6.5
**Effort**: 3
**Objective**: Confirm the slice against the LLD "Verification Walkthrough" with the real `cf`, and leave the branch clean for review.

**Steps**:
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright`, once each
- [ ] Run walkthrough steps 1–5 in bash against a scratch store and a scratch CF directory only (never the PM's real `projects.json`). First confirm which level (worktree or project) `cf set` writes to from the current directory, and adjust the expected `worktree_id` accordingly. If `cf` is not on PATH, stop and tell the PM
- [ ] Record the walkthrough output (as 107 did) and correct the LLD draft wherever reality differs, flagging each correction to the PM
- [ ] Clean up with `uv run amoeba stop; rm -rf "$AMOEBA_STORE_DIR" "$CFDIR"`
- [ ] Delegate checklist updates to the `task-checker` agent; set this file's `status` to `complete`

**Success Criteria**:
- [ ] Suite, `ruff`, `pyright` clean; every walkthrough step matches its expected result, or the difference is reported
- [ ] Commit, e.g. `docs: record 108 walkthrough output`

**Files to Modify**: `user/slices/108-slice.context-forge-event-seam.md` (walkthrough note), this task file
