---
docType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
lld: user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md
dependencies: [101, 102, 103, 104, 105]
projectState: Slices 101–105 are merged (store schema 5, tenant seam, inbox, verdicts and findings, 105's parser and `amoeba ingest review` in `amoeba.upstream.squadron`). Nothing in the store emits changes and no tenant reads review files. This slice adds migration 006 with emission triggers, the feed read API, `amoeba.feed.follow` and `amoeba feed`, the `watch_reviews` kind, `attribute_review`, `ReviewDetectionTenant`, and two listings.
dateCreated: 20261015
dateUpdated: 20261015
status: not_started
---

## Context Summary

- Working on the **outbound-change-feed-and-detection-of-external-work** slice (106), the sixth slice of initiative 100. The design was trimmed on 20261015; `read_transaction()`, `change_head()`, `record_runner_report`, and `source_document` are **deferred** (LLD "Deferred", GitHub issue #3) and appear in no task here.
- **Current state:** `Store` is built from mixins (`store/store.py`); SQL lives in `sql_*.py`, row mapping in `mapping_*.py`, word lists in `*_models.py`. `EXPECTED_SCHEMA_VERSION` is 5 (`store/migrations.py`). `Store.open_read_only` is the only out-of-process handle. An inbox kind is a `SubmissionKind` member, a payload model in `KIND_PAYLOAD_MODELS` (`inbox/envelope.py`), and an effect in `KIND_EFFECTS` (`store/inbox.py`). Tenants implement `Tenant.tick(host) -> bool` (`process/host.py`); `InboxTenant` is the model. `LISTINGS` in `cli/inspect.py` is the listing registry. `capture_version_label` and `VERSION_UNAVAILABLE` are in `process/observers/cf_readback.py` and are cf-specific today. `nodes_for_project` and `unresolved_journal_entries` exist on `Store`. `store_path_for` lives in `process/supervisor.py`.
- **Dependencies:** 101–105 through their documented contracts. `amoeba.upstream.squadron` exports `parse_review_artifact`, `ParsedReview` (with a `slice` field), `to_verdict_input` (keyword `node_id`, `upstream_version`, `source_path`), `review_record_id`, and `SquadronReviewError`. File 1 does not use 105's code.
- **What this slice delivers:** see the LLD "Technical Scope, Included".
- **Next planned slice:** 107 (judge samples), then 108 (Context Forge event seam), which extends this slice's trigger convention.

**Branch:** all implementation happens on `106-slice.outbound-change-feed-and-detection-of-external-work`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges; merging follows the code review (Phase 7).

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md` at the named section. Exact payload columns, word lists, and failure tables are settled there. Keep every new source file near 300 lines.

**Commit cadence:** a commit never holds untested behavior. A task that says "committed with Task N.M" is committed together with its test task, which follows immediately; every other task commits on its own.

**Migration 006 grows in place.** It is unreleased until this slice merges, so Tasks 1.3, 2.1, 2.3, and 4.1 each add to the one file. Never create a 007.

**Task-level additions to the LLD API table** (the LLD describes the behavior but names no method): `DetectionInput`'s fields, `recorded_since`, `baseline_watch` with `BaselineEntry`, `record_detected_verdict`, `project_store_path`, and `ReviewDirectoryUnavailableError`. Each is recorded in the contract docs (Task 9.4) and listed to the PM (Task 9.6).

**Section map.** This file: 1 models and migration; 2 emission triggers and the invariant test; 3 feed reads, follower, `amoeba feed`; 4 detection storage and the `watch_reviews` kind. **File 2:** 5 attribution and review-producing kinds; 6 review sources; 7 the detection tenant; 8 listings and wiring; 9 end-to-end, docs, validation.

---

## Section 1: Models and Migration

### Task 1.1: Create the branch and record the starting state
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 1
**Objective**: Work on the right branch from a clean baseline.

**Steps**:
- [ ] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [ ] Create `106-slice.outbound-change-feed-and-detection-of-external-work` from the target; if it exists, switch to it
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each. If any fails before changes, stop and tell the PM

**Success Criteria**:
- [ ] On the slice branch; baseline suite, `ruff`, and `pyright` clean
- [ ] No commit needed

---

### Task 1.2: Add `feed_models.py`
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 2
**Objective**: Define every feed word list and record type once (LLD "Patterns and Conventions", "API Contracts").

**Steps**:
- [ ] Create `src/amoeba/store/feed_models.py` in the style of `journal_models.py` (no SQL, no `sqlite3`)
- [ ] `ChangeKind` and `DetectionOutcome` as `StrEnum`s with exactly the LLD's members
- [ ] `SILENT_OUTCOMES`: a frozenset of `baseline` and `runner_issued`, the outcomes that emit no change (D8). Defined once here
- [ ] Frozen dataclasses: `Change` (`seq, project_id, kind, node_id, subject_id, payload: Mapping[str, object], recorded_at`), `ReviewWatch` (the `review_watches` columns), `DetectedReview` (the `detected_reviews` columns), `DetectionInput` (`project_id, path, digest, outcome`, and optional `node_id, verdict_id, record_id, detail`), `BaselineEntry` (`path, digest`)
- [ ] No test module of its own: these are declarations, exercised by the mapping tests (Task 1.5) and the invariant test (Task 2.5)

**Success Criteria**:
- [ ] `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(store): add feed models`

**Files to Create**: `src/amoeba/store/feed_models.py`

---

### Task 1.3: Write migration 006 tables and `sql_feed.py`
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 3
**Objective**: Create the three tables (LLD "Database / Storage Schema") with every name defined once in Python.

**Steps**:
- [ ] Read `005_verdicts_and_findings.sql` and `sql_evidence.py` for the pairing convention
- [ ] Create `src/amoeba/store/schema/006_change_feed_and_detection.sql` with `changes`, `review_watches`, `detected_reviews` exactly per the LLD: `changes` index on `(project_id, seq)` and no FK on `changes.node_id`; `review_watches` primary key `(project_id, reviews_dir)`; `detected_reviews` UNIQUE `(project_id, path, digest)` with nullable FKs on `node_id` and `verdict_id`. No `IF NOT EXISTS` (migration convention). `verdicts` is not touched
- [ ] Create `src/amoeba/store/sql_feed.py` for the table and column names of these tables. Statements are added by later tasks. No SQL outside `sql_*.py` and the migration
- [ ] Set `EXPECTED_SCHEMA_VERSION` to 6
- [ ] Update only the existing tests that pin version 5 or the table set (search `tests/` for `EXPECTED_SCHEMA_VERSION`, `schema_version`, and `5`)

**Success Criteria**:
- [ ] A fresh store reaches version 6 with the three tables
- [ ] Full suite passes with the updated pins
- [ ] Committed with Task 1.4

**Files to Create**: `006_change_feed_and_detection.sql`, `src/amoeba/store/sql_feed.py`
**Files to Modify**: `store/migrations.py`, version-pinning tests

---

### Task 1.4: Test the 5 → 6 upgrade
**Owner**: Junior AI
**Dependencies**: Task 1.3
**Effort**: 2
**Objective**: A version-5 store upgrades intact (LLD Technical Requirements).

**Steps**:
- [ ] Add `tests/store/test_migration_006.py` modeled on `test_migration_005.py`
- [ ] Build a version-5 store holding nodes, journal entries, submissions, messages, and a verdict with findings; migrate to 6
- [ ] Assert every pre-existing row is intact, the three new tables exist and are empty (the feed of an upgraded store starts empty)

**Success Criteria**:
- [ ] New tests pass; full suite passes
- [ ] Commit, e.g. `feat(store): add migration 006 tables`

**Files to Create**: `tests/store/test_migration_006.py`

---

### Task 1.5: Add `mapping_feed.py` and test it
**Owner**: Junior AI
**Dependencies**: Task 1.4
**Effort**: 2
**Objective**: Row → record mapping that fails on unknown values, like the other `mapping_*.py` files.

**Steps**:
- [ ] Create `src/amoeba/store/mapping_feed.py` with `map_change`, `map_watch`, `map_detected_review`, following `mapping_journal.py`: an unknown `kind` or `outcome` raises `UnknownVocabularyValueError`; `payload` JSON is decoded; `active` maps from 0/1
- [ ] Add `tests/store/test_mapping_feed.py`: a valid row of each type maps; an unknown kind and an unknown outcome raise; a malformed payload raises rather than returning `{}`

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(store): add feed row mapping`

**Files to Create**: `src/amoeba/store/mapping_feed.py`, `tests/store/test_mapping_feed.py`

---

### Task 1.6: Pin import boundaries and single definitions
**Owner**: Junior AI
**Dependencies**: Task 1.5
**Effort**: 2
**Objective**: Hold the LLD Technical Requirements on layering and single definition from the first module on, so a violation fails in the task that introduces it.

**Steps**:
- [ ] Create `tests/test_import_boundaries.py`, AST-based like `tests/test_writer_guard.py`. Read `tests/upstream/test_import_direction.py` first and reuse its approach
- [ ] Rule 1: nothing under `src/amoeba/store/` imports `amoeba.upstream`, `amoeba.process`, or `amoeba.feed`
- [ ] Rule 2: nothing under `src/amoeba/feed/` imports `amoeba.process`. A directory that does not exist yet passes; the rule applies once it appears
- [ ] Rule 3: no string constant (docstrings excluded) equals a `ChangeKind` or `DetectionOutcome` value in the modules this slice creates, listed once in the test: `store/feed.py`, `store/mapping_feed.py`, `store/sql_feed.py`, `store/attribution.py`, `feed/follower.py`, `process/review_sources.py`, `process/review_scan.py`, `process/review_detection.py`, `cli/feed.py`, `cli/inspect_feed.py`. A listed module that does not exist yet is skipped. Older modules are out of scope, since words like `ingested` occur there legitimately
- [ ] One test function per rule, so a failure names the rule

**Success Criteria**:
- [ ] All three tests pass on the current tree
- [ ] Commit, e.g. `test: pin store and feed import boundaries`

**Files to Create**: `tests/test_import_boundaries.py`

---

## Section 2: Emission Triggers and the Invariant Test

All triggers go in migration 006 (LLD D8). Each writes one `changes` row in the writer's transaction, with `payload` built by `json_object` and `recorded_at` copied from the row's own timestamp column. Columns follow the LLD payload table. **No writer method changes in this section.** Until Task 3.1, tests read raw `changes` rows through a small helper in `tests/feed_harness.py` (created in Task 2.2), which Task 3.1 switches to the public API.

### Task 2.1: Triggers for node creation and node status change
**Owner**: Junior AI
**Dependencies**: Task 1.6
**Effort**: 2
**Objective**: `node_created` (payload `kind`, `parent_id`, `status`) and `node_status_changed` (payload `from`, `to`).

**Steps**:
- [ ] Add `AFTER INSERT ON nodes` per the LLD payload table (`node_id` and `subject_id` both the node)
- [ ] Add `AFTER UPDATE OF status ON nodes ... WHEN old.status IS NOT new.status`; `recorded_at` is the node's `updated_at`
- [ ] Put a comment above the triggers: the kind literals mirror `ChangeKind` in `feed_models.py`, and the invariant test (Task 2.5) ties them together

**Success Criteria**:
- [ ] `git diff` shows no edits under `store/nodes.py` or `store/blocking.py`
- [ ] Committed with Task 2.2

**Files to Modify**: migration 006

---

### Task 2.2: Test the node triggers
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 2
**Objective**: Pin node emission through the store's real methods.

**Steps**:
- [ ] Create `tests/feed_harness.py` with `raw_changes(store, project_id)` (reads `changes` via the column names in `sql_feed.py`)
- [ ] Add `tests/store/test_feed_triggers.py`: `create_node` adds exactly one `node_created` with the initial status; a status update emits one `node_status_changed` with `from`/`to`; an update to the same status emits none; `block` and `resolve` (`store/blocking.py`) each emit the right `from`/`to`; `recorded_at` equals the row's own timestamp; a rolled-back write leaves no `changes` row

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(store): emit node changes by trigger`

**Files to Create**: `tests/feed_harness.py`, `tests/store/test_feed_triggers.py`

---

### Task 2.3: Triggers for verdicts and messages
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 2
**Objective**: `verdict_recorded` and `message_posted`, covering every writer including recovery's escalation messages (D8 "Why").

**Steps**:
- [ ] Add `AFTER INSERT ON verdicts`: payload `verdict`, `review_type`, `provider_failure` as a JSON boolean (not 0/1); no trust label
- [ ] Add `AFTER INSERT ON messages`: payload `channel`; `node_id` may be null

**Success Criteria**:
- [ ] `git diff` shows no edits to `_verdict_writer.py`, `verdicts.py`, or `messages.py`
- [ ] Committed with Task 2.4

**Files to Modify**: migration 006

---

### Task 2.4: Test the verdict and message triggers
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 2
**Objective**: Every existing writer emits, and a retry emits nothing.

**Steps**:
- [ ] Add to `tests/store/test_feed_triggers.py`, each as its own case: `record_verdict` emits one `verdict_recorded`; a retried `record_verdict` with the same id emits none; a provider-failure verdict has `provider_failure` true; the payload keys are exactly `verdict`, `review_type`, `provider_failure`
- [ ] An intent submission through `apply_submission` emits one `message_posted`
- [ ] A `resolution` submission through `apply_submission` on a blocked node emits `node_status_changed` from the blocked status to `runnable`
- [ ] A recovery escalation message (stage a journal entry whose kind has no observer and run reconciliation as `tests/test_recovery.py` does) emits one `message_posted`

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(store): emit verdict and message changes by trigger`

**Files to Modify**: `tests/store/test_feed_triggers.py`

---

### Task 2.5: The invariant test
**Owner**: Junior AI
**Dependencies**: Task 2.4
**Effort**: 3
**Objective**: Replaying the feed from seq 0 reconciles with every tracked table (LLD "The invariant test checks every tracked table"). Built now over three tables; Task 4.2 adds `detected_reviews`.

**Steps**:
- [ ] Create `tests/store/test_feed_invariant.py` with a scripted sequence driving every write path that exists: node create, status updates, block and resolve, verdicts (including a retry and a provider failure), an intent message, and a recovery escalation
- [ ] One function `reconcile(store, project_id) -> list[str]` returning differences (empty means consistent): node ids from `node_created` equal the `nodes` rows; each node's status rebuilt from `node_created.status` plus `node_status_changed` equals the stored status; verdict ids equal the `verdicts` rows; message ids equal the `messages` rows
- [ ] Test: the sequence on a real migrated store reconciles with no differences
- [ ] Every-kind test: each `ChangeKind` appears at least once in the sequence's changes, except the members in one named constant `NOT_YET_EMITTED = {ChangeKind.REVIEW_DETECTED}` that Task 4.2 deletes. This also catches a trigger literal that drifted from the enum, since mapping would reject it or the kind would never appear

**Success Criteria**:
- [ ] Both invariant tests pass
- [ ] Commit, e.g. `test(store): reconcile the feed with the tracked tables`

**Files to Create**: `tests/store/test_feed_invariant.py`

---

## Section 3: Feed Reads, Follower, and `amoeba feed`

### Task 3.1: Add `changes` (the `FeedOperations` mixin)
**Owner**: Junior AI
**Dependencies**: Task 2.5
**Effort**: 2
**Objective**: The feed read API (LLD "API Contracts").

**Steps**:
- [ ] Add to `sql_feed.py` a select of changes with `seq > ?` for a project, in `seq` order, with a limit
- [ ] Create `src/amoeba/store/feed.py` with `FeedOperations(StoreBase)` providing `changes(project_id, *, after=0, limit)`. `limit` has no default; `limit < 1` raises `ValueError`
- [ ] Add the mixin to `Store`'s bases; export `Change`, `ChangeKind`, `DetectionOutcome`, `ReviewWatch`, `DetectedReview`, `DetectionInput`, `BaselineEntry` from `store/__init__.py`
- [ ] Replace `raw_changes` in `tests/feed_harness.py` with a call to `changes()` so later tests read through the public API

**Success Criteria**:
- [ ] `ruff`, `pyright` clean; existing trigger and invariant tests still pass
- [ ] Committed with Task 3.2

**Files to Create**: `src/amoeba/store/feed.py`
**Files to Modify**: `store/sql_feed.py`, `store/store.py`, `store/__init__.py`, `tests/feed_harness.py`

---

### Task 3.2: Test `changes`
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 2
**Objective**: Pin ordering, cursor, scoping, limit.

**Steps**:
- [ ] Add `tests/store/test_feed_reads.py`: empty project gives `[]`; `after` returns only later rows in order; `limit` caps the result; two projects' feeds are independent; `seq` has no gaps after a mixed sequence of writes; payload is a decoded mapping
- [ ] Add the new names to `tests/test_public_api.py`

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(store): add the changes read`

**Files to Create**: `tests/store/test_feed_reads.py`
**Files to Modify**: `tests/test_public_api.py`

---

### Task 3.2a: Add `project_store_path` and `Store.data_version()`
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 2
**Objective**: The two store-side pieces the follower needs, each tested directly.

**Steps**:
- [ ] `amoeba.feed` must not import `amoeba.process`. Add `project_store_path(store_dir, project_id)` to `store/paths.py` and make `store_path_for` in `process/supervisor.py` delegate to it (no behavior change)
- [ ] Put the `PRAGMA data_version` statement in `store/sql.py` behind a small `Store.data_version()` method
- [ ] Tests: in `tests/test_paths.py`, `project_store_path` and `store_path_for` return the same path for the same inputs. In `tests/store/test_feed_reads.py`, a read-only handle's `data_version()` is unchanged by its own reads and changes after another connection commits

**Success Criteria**:
- [ ] Tests pass; existing supervisor tests pass
- [ ] Commit, e.g. `feat(store): add project_store_path and data_version`

**Files to Modify**: `store/paths.py`, `process/supervisor.py`, `store/sql.py`, `store/store.py`, `tests/test_paths.py`, `tests/store/test_feed_reads.py`

---

### Task 3.3: Implement `amoeba.feed.follow`
**Owner**: Junior AI
**Dependencies**: Task 3.2a
**Effort**: 3
**Objective**: The subscriber-side blocking iterator (LLD "Following the feed", D2, and the follower failure table).

**Steps**:
- [ ] Create `src/amoeba/feed/__init__.py` and `follower.py`. `FeedSettings` is a frozen dataclass with `follow_interval_seconds = 0.25` and `feed_batch_size = 500`, defined here once
- [ ] `follow(store_dir, project_id, *, after, settings, stop=None) -> Iterator[Change]`: open `project_store_path(...)` with `Store.open_read_only`; read `changes(after=cursor, limit=feed_batch_size)`, yield each, advance the cursor; when empty, wait until `data_version()` changes, checking every `follow_interval_seconds`; check `stop` between waits and between yielded changes. The follower holds no SQL
- [ ] Failure table exactly per the LLD: a busy or locked read (`sqlite3.OperationalError` whose message says busy/locked — check how 101 classifies it and reuse that) is retried on the next interval; a schema-version mismatch, unknown project, or missing store directory raises the store's error; a raising `stop` propagates; `stop` returning true ends cleanly. Comment the one specific `except` per CLAUDE.md
- [ ] Close the store in a `finally`

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 3.4

**Files to Create**: `src/amoeba/feed/__init__.py`, `src/amoeba/feed/follower.py`

---

### Task 3.4: Test the follower
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 3
**Objective**: Resume, waking, shutdown, and every row of the failure table (LLD Functional Requirements, follower bullets).

**Steps**:
- [ ] Add `tests/feed/__init__.py` and `tests/feed/test_follower.py`; build a small `FeedSettings` (a few milliseconds) in the test, never the production default
- [ ] `after=N` yields exactly the changes after N; `after=0` yields all; with `feed_batch_size` 2 and five changes, all five arrive in order
- [ ] Waking: `follow` in a thread; commit a node from a read-write store; the change arrives within a generous multiple of the interval
- [ ] Resume: consume part of the stream, restart from the last `seq`, no gap and no repeat; the `changes` row count is unchanged by following
- [ ] Failure table: unknown project and a store at another schema version each raise before any yield; a busy read is retried (hold a write lock from another connection across one interval, then release); a raising `stop` propagates; `stop` true ends the iterator and closes the store
- [ ] Store directory gone: absent before `follow` starts raises a `StoreError` subclass before any yield; removed after the first yield raises a `StoreError` subclass on a later read

**Success Criteria**:
- [ ] Tests pass on three consecutive runs of the module
- [ ] Commit, e.g. `feat(feed): add follow, the subscriber-side change follower`

**Files to Create**: `tests/feed/__init__.py`, `tests/feed/test_follower.py`

---

### Task 3.5: Add the `amoeba feed` command
**Owner**: Junior AI
**Dependencies**: Task 3.4
**Effort**: 2
**Objective**: Print changes as JSON lines (LLD CLI table).

**Steps**:
- [ ] Create `src/amoeba/cli/feed.py`; register `feed` in `cli/main.py` the way `inspect` and `submit` are, with `--project` (required), `--after` (non-negative int, default 0), `--follow`
- [ ] One JSON object per line with the `Change` keys (`recorded_at` as ISO text), flushed per line
- [ ] Without `--follow`: read changes after `--after` in batches until a read returns none, then exit 0. With `--follow`: use `follow()` until interrupted; `KeyboardInterrupt` and `SIGTERM` exit with `ExitCode.OK`
- [ ] `StoreError` subclasses go through the existing boundary mapping in `main.py`; add no new exit code (if none fits, ask the PM)
- [ ] Takes no lock; works with the process running or stopped

**Success Criteria**:
- [ ] `amoeba feed --help` lists the three flags
- [ ] Committed with Task 3.6

**Files to Create**: `src/amoeba/cli/feed.py`
**Files to Modify**: `src/amoeba/cli/main.py`

---

### Task 3.6: Test `amoeba feed` through the CLI
**Owner**: Junior AI
**Dependencies**: Task 3.5
**Effort**: 3
**Objective**: Real-subprocess behavior, using `tests/cli_harness.py`.

**Steps**:
- [ ] Add `tests/cli/test_feed.py`: seeded store, `amoeba feed --project P` prints lines that each parse as JSON with exactly the `Change` keys; exit 0
- [ ] `--after N` prints only later lines; an unknown project exits with the existing not-found code and prints nothing on stdout
- [ ] `--follow` as a subprocess with no process running: existing lines print; a new node committed through a separate read-write store prints; `SIGTERM` exits cleanly. (The process-starts-later case is end-to-end, Task 9.1)
- [ ] Killed follower: `kill -9` mid-stream, restart with `--after` its last printed `seq`: no gap, no repeat

**Success Criteria**:
- [ ] Tests pass; the `changes` row count is unchanged by any run
- [ ] Commit, e.g. `feat(cli): add amoeba feed`

**Files to Create**: `tests/cli/test_feed.py`

---

## Section 4: Detection Storage and the `watch_reviews` Kind

### Task 4.1: `record_detection`, `detections`, `recorded_since`, and the `review_detected` trigger
**Owner**: Junior AI
**Dependencies**: Task 3.6
**Effort**: 3
**Objective**: The ledger write path and its change emission (LLD API Contracts, D8).

**Steps**:
- [ ] Add to `sql_feed.py`: insert-or-ignore on `(project_id, path, digest)`; select by key; select a project's ledger in detection order with an optional outcome filter
- [ ] Write one private method that inserts a ledger row **without** opening a transaction. `record_detection(DetectionInput) -> DetectedReview` wraps it in its own transaction using the `apply_submission` pattern (`with self._connection:` then the existing `BEGIN IMMEDIATE` constant). A repeated key returns the existing row unchanged. Tasks 4.5 and 4.7 reuse the private method
- [ ] `detections(project_id, *, outcome=None) -> list[DetectedReview]`
- [ ] `recorded_since(project_id, record_id) -> bool`: true when a verdict whose id equals `record_id` exists (LLD CLI table). Implement it with 104's existing `verdict(verdict_id)` read; add no verdict SQL to `sql_feed.py`. Docstring states the consequence: a verdict recorded under an overridden id (`amoeba ingest review --id`) is not seen
- [ ] Add the `AFTER INSERT ON detected_reviews ... WHEN new.outcome NOT IN ('baseline', 'runner_issued')` trigger with payload `outcome`, `path`; comment that the literals mirror `SILENT_OUTCOMES`

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 4.2

**Files to Modify**: `store/sql_feed.py`, `store/feed.py`, migration 006

---

### Task 4.2: Test the ledger and extend the invariant test
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 3
**Objective**: Pin idempotency, filtering, silent outcomes, `recorded_since`, and the fourth tracked table.

**Steps**:
- [ ] Add `tests/store/test_detections.py`: each outcome records; a repeated key returns the first row and inserts nothing; `detections(outcome=...)` filters; order is detection order
- [ ] `recorded_since`: false, then true after a verdict whose id equals the `record_id` is recorded (direct call and through `apply_submission`); a verdict under another id leaves it false
- [ ] In `test_feed_triggers.py`: `ingested`, `unattributed`, `unparseable` each emit one `review_detected`; `baseline` and `runner_issued` emit none; a repeated `record_detection` emits none
- [ ] In `test_feed_invariant.py`: add detections of all five outcomes to the sequence; `reconcile` also compares `review_detected` subject ids against ledger rows whose outcome is not in `SILENT_OUTCOMES`; delete `NOT_YET_EMITTED`

**Success Criteria**:
- [ ] All tests pass with no exception constant left
- [ ] Commit, e.g. `feat(store): add detection ledger and review_detected changes`

**Files to Create**: `tests/store/test_detections.py`
**Files to Modify**: `tests/store/test_feed_triggers.py`, `tests/store/test_feed_invariant.py`

---

### Task 4.3: Add the `watch_reviews` inbox kind
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 3
**Objective**: Register or deactivate a directory (LLD "Registering a directory", "Inbox, the `watch_reviews` kind").

**Steps**:
- [ ] Follow the three-part rule in `SubmissionKind`'s docstring: add `WATCH_REVIEWS` to `SubmissionKind` (`store/inbox_models.py`); add `WatchReviewsPayload` (`reviews_dir: str` validated absolute by pydantic, `active: bool`) to `inbox/envelope.py` and `KIND_PAYLOAD_MODELS`; add the effect to `KIND_EFFECTS` with its payload key constants beside the other kinds' keys
- [ ] Effect: upsert `review_watches` through a statement in `sql_feed.py`. First activation sets `registered_at` and leaves `baselined_at` null; a later submission updates `active` and `updated_at` and never clears `baselined_at`
- [ ] Confirm `amoeba submit watch-reviews` appears (`cli/submit.py` derives subcommands from the payload model; `--active` takes `true|false` under 104's flag rule). Edit `cli/submit.py` only if it does not
- [ ] Update only the kind-set pins found by searching `tests/` for `SubmissionKind`

**Success Criteria**:
- [ ] `amoeba submit watch-reviews --help` lists `--reviews-dir` and `--active`; `ruff`, `pyright` clean
- [ ] Committed with Task 4.4

**Files to Modify**: `store/inbox_models.py`, `inbox/envelope.py`, `store/inbox.py`, `store/sql_feed.py`, kind-set pins

---

### Task 4.4: Test the `watch_reviews` kind
**Owner**: Junior AI
**Dependencies**: Task 4.3
**Effort**: 2
**Objective**: Pin registration semantics.

**Steps**:
- [ ] Add `tests/store/test_watch_reviews.py` (the read is checked through raw SQL until Task 4.5): registering creates a watch with `baselined_at` null; deactivate then reactivate keeps a `baselined_at` staged directly in the test; a replayed submission is a no-op
- [ ] A relative path is quarantined as invalid at the envelope (`tests/inbox/test_envelope.py` style)
- [ ] Extend `tests/cli/test_submit.py` with `--active true` and `--active false`

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(inbox): add the watch_reviews kind`

**Files to Create**: `tests/store/test_watch_reviews.py`
**Files to Modify**: `tests/cli/test_submit.py`

---

### Task 4.5: Add `watches` and `baseline_watch`
**Owner**: Junior AI
**Dependencies**: Task 4.4
**Effort**: 2
**Objective**: The store side of the all-or-nothing baseline (LLD "Registering a directory").

**Steps**:
- [ ] `watches(project_id) -> list[ReviewWatch]`
- [ ] `baseline_watch(project_id, reviews_dir, entries: Sequence[BaselineEntry])`: one transaction (same pattern as Task 4.1) that inserts one `baseline` row per entry through the private insert, then sets `baselined_at`. A `(path, digest)` already in the ledger is skipped
- [ ] The `baselined_at` update runs after the inserts and must affect exactly one row: an unregistered or already-baselined watch raises `StoreError`, rolling back the inserts
- [ ] Switch `tests/store/test_watch_reviews.py` from raw SQL to `watches()`

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 4.6

**Files to Modify**: `store/sql_feed.py`, `store/feed.py`, `tests/store/test_watch_reviews.py`

---

### Task 4.6: Test `watches` and `baseline_watch`
**Owner**: Junior AI
**Dependencies**: Task 4.5
**Effort**: 2
**Objective**: Pin atomicity and read shape.

**Steps**:
- [ ] Add to `tests/store/test_watch_reviews.py`: `watches` lists every column; `baseline_watch` writes one row per entry plus `baselined_at`; it emits no change; a duplicate entry is skipped
- [ ] Atomicity: (a) an unregistered directory raises `StoreError` and leaves no ledger rows; (b) in a scratch store, a temporary `BEFORE INSERT ON detected_reviews` trigger that does `RAISE(ABORT, ...)` for one path makes the call raise, with no rows and `baselined_at` still null

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(store): add watch reads and the atomic baseline`

**Files to Modify**: `tests/store/test_watch_reviews.py`

---

### Task 4.7: Add `record_detected_verdict` (one-transaction ingest)
**Owner**: Junior AI
**Dependencies**: Task 4.6
**Effort**: 3
**Objective**: Record a verdict and its `ingested` ledger row in one transaction (LLD "Detecting a review", "exactly one → one transaction").

**Steps**:
- [ ] Read `_verdict_writer.py` and `apply_submission` in `store/inbox.py`, which already records a verdict inside its own transaction. If the verdict write cannot run inside an open transaction, extract its body into an inner method with no behavior change (104's tests prove it)
- [ ] `record_detected_verdict(verdict: VerdictInput, detection: DetectionInput) -> tuple[VerdictRecord, DetectedReview]` in `FeedOperations`. `detection.outcome` must be `ingested` (else `ValueError`, nothing written). In one transaction: if the ledger key already exists, raise `ValueError` naming it and write nothing (the tenant skips known keys first, so this is a guard only); record the verdict (104's retry rule applies); insert the ledger row with the verdict's id and node id
- [ ] Docstring states the hand-edit case: a new key with an existing verdict id records no new verdict and one new `ingested` row pointing at it

**Success Criteria**:
- [ ] 104's tests pass unchanged; `ruff`, `pyright` clean
- [ ] Committed with Task 4.8

**Files to Modify**: `store/feed.py`, `store/sql_feed.py`, `store/_verdict_writer.py` (only if the inner method is needed)

---

### Task 4.8: Test `record_detected_verdict`
**Owner**: Junior AI
**Dependencies**: Task 4.7
**Effort**: 2
**Objective**: Pin atomicity, the existing-key guard, and the hand-edit case.

**Steps**:
- [ ] Add `tests/store/test_record_detected_verdict.py`: success writes one verdict and one `ingested` row and emits `verdict_recorded` then `review_detected`; a non-`ingested` outcome raises and writes nothing
- [ ] Atomicity: a temporary `RAISE(ABORT, ...)` trigger on `detected_reviews` inserts makes the call raise and leaves no verdict, ledger row, or `changes` row
- [ ] An existing key raises `ValueError` and writes nothing
- [ ] Hand edit (new key, existing verdict id): still one verdict, a second `ingested` row pointing at it, one `review_detected` and no `verdict_recorded`

**Success Criteria**:
- [ ] Tests pass; full suite passes
- [ ] Commit, e.g. `feat(store): record a detected verdict and its ledger row atomically`

**Files to Create**: `tests/store/test_record_detected_verdict.py`
