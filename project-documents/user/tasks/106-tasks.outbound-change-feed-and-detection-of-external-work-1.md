---
docType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
lld: user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md
dependencies: [101, 102, 103, 104, 105]
projectState: Slices 101–104 are merged (store schema 5, tenant seam, inbox, verdicts and findings). Slice 105 (parser and `amoeba ingest review`) is planned and its tasks are reviewed; it may or may not be merged when this file starts. Nothing in the store emits changes, `verdicts` has no `source_document`, and no tenant reads review files. This slice adds migration 006, the feed, the follower, `watch_reviews`, and `ReviewDetectionTenant`.
dateCreated: 20261007
dateUpdated: 20261007
status: not_started
---

## Context Summary

- Working on the **outbound-change-feed-and-detection-of-external-work** slice (106), the sixth slice of initiative 100.
- **Current state:** `Store` is built from mixins (`store/store.py`); SQL lives in `sql_*.py`, row mapping in `mapping_*.py`, vocabularies in `*_models.py`. `EXPECTED_SCHEMA_VERSION` is 5 (`store/migrations.py`). `Store.open_read_only` is the only out-of-process handle. Inbox kinds are a `SubmissionKind` member + a payload model in `inbox/envelope.py` (`KIND_PAYLOAD_MODELS`) + an effect in `InboxOperations` (`KIND_EFFECTS`). Tenants implement `Tenant.tick(host) -> bool` (`process/host.py`); `InboxTenant` is the model for a tenant (host protocol, attempts sidecars, bounded failure). `LISTINGS` in `cli/inspect.py` is the listing registry. `capture_version_label` and `VERSION_UNAVAILABLE` are in `process/observers/cf_readback.py`.
- **Dependencies:** 101–104 through their contracts. 105 supplies `parse_review_artifact`, `ParsedReview`, `to_verdict_input`, `review_record_id`. Sections 1–7 do not need 105's code; **Section 8 onward does** (Task 8.1 checks).
- **What this slice delivers:** migration 006 (`changes`, `review_watches`, `detected_reviews`, `verdicts.source_document`, emission triggers); the feed read API and `read_transaction()`; `amoeba.feed.follow` and `amoeba feed`; the `watch_reviews` inbox kind; `attribute_review`; `ReviewSource` / `DirectoryReviewSource`; `ReviewDetectionTenant`; two listings; docs.
- **Not in this slice:** Context Forge events (108), Runner-launched review completion (120), backfill of old reviews, a network transport (109), cross-project feeds, retention, non-Squadron parsing.
- **Next planned slice:** 107 (judge samples), then 108.

**Branch:** all implementation happens on `106-slice.outbound-change-feed-and-detection-of-external-work`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging comes after the code review (Phase 7).

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md` at the named section (Data Flow, D1–D8, Patterns and Conventions, API Contracts, Database / Storage Schema). Exact signatures, payload columns, and failure tables are settled there. Keep every new source file near 300 lines.

**Commit cadence:** a commit never holds untested behavior. A task that says "committed with Task N.M" is committed together with its test task, which follows immediately; every other task commits on its own.

**Triggers grow in place.** Migration `006_change_feed_and_detection.sql` is unreleased until this slice merges, so Tasks 1.3, 2.1–2.3 and 5.1 each add to the one file. Never create a 007.

**Section map (this file):** 1 models and migration; 2 emission triggers; 3 `source_document` (D7); 4 feed reads and `read_transaction`; 5 detection storage and the `watch_reviews` kind; 6 attribution and review-producing kinds. **Sections 7–10 are in `...-2.md`:** 7 follower and `amoeba feed`; 8 review sources; 9 detection tenant; 10 listings and wiring. **Section 11 is in `...-3.md`:** end-to-end, docs, final validation.

---

## Section 1: Models and Migration

### Task 1.1: Create the branch and record the starting state
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 1
**Objective**: Work on the right branch and know the baseline.

**Steps**:
- [ ] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [ ] Create `106-slice.outbound-change-feed-and-detection-of-external-work` from the target; if it exists, switch to it
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once and note any pre-existing failure. If any fail before changes, stop and tell the PM

**Success Criteria**:
- [ ] On the slice branch; baseline suite, `ruff`, `pyright` clean
- [ ] No commit needed

---

### Task 1.2: Add `feed_models.py`
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 2
**Objective**: Define every feed vocabulary and transfer object once (LLD "Patterns and Conventions", "API Contracts").

**Steps**:
- [ ] Create `src/amoeba/store/feed_models.py`, no SQL, no `sqlite3`, following `journal_models.py` style
- [ ] `ChangeKind` and `DetectionOutcome` as `StrEnum`s with exactly the members in the LLD word lists
- [ ] Frozen dataclasses: `Change` (`seq, project_id, kind, node_id, subject_id, payload: Mapping[str, object], recorded_at`), `ReviewWatch` (columns of `review_watches`), `DetectedReview` (columns of `detected_reviews`), and `DetectionInput` (what `record_detection` takes: project, path, digest, outcome, optional node id, verdict id, record id, detail)
- [ ] A comment on `DetectionOutcome` names the two outcomes that emit no change (`baseline`, `runner_issued`) and says `failed` is a listing state, not a member
- [ ] Define the set of silent outcomes once here (e.g. `SILENT_OUTCOMES`) for the trigger-consistency test in Task 5.5

**Success Criteria**:
- [ ] Module imports; `ruff` and `pyright` clean
- [ ] Committed with Task 1.5

**Files to Create**: `src/amoeba/store/feed_models.py`

---

### Task 1.3: Write migration 006 (tables and column) and `sql_feed.py`
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 3
**Objective**: Create the schema (LLD "Database / Storage Schema") with every name defined once in Python.

**Steps**:
- [ ] Read `005_verdicts_and_findings.sql` and `sql_evidence.py` for the pairing convention (SQL file names match constants)
- [ ] Create `src/amoeba/store/schema/006_change_feed_and_detection.sql`: tables `changes`, `review_watches`, `detected_reviews` exactly per the LLD (including `changes` index on `(project_id, seq)`, `detected_reviews` UNIQUE `(project_id, path, digest)`, no FK on `changes.node_id`)
- [ ] In the same file: `ALTER TABLE verdicts ADD COLUMN source_document TEXT`; drop `idx_verdicts_previous_round` and recreate it on `(project_id, node_id, review_type, source_document, recorded_seq)`. No `IF NOT EXISTS` (migration convention)
- [ ] Create `src/amoeba/store/sql_feed.py` holding every table/column name and statement for these tables (inserts and selects are added by Tasks 4.1, 5.1, 5.2). No SQL outside `sql_*.py`
- [ ] Set `EXPECTED_SCHEMA_VERSION` to 6 in `store/migrations.py`
- [ ] Update every existing test that pins version 5 or the table/column set (search `tests/` for `EXPECTED_SCHEMA_VERSION`, `schema_version`, `== 5`)

**Success Criteria**:
- [ ] A fresh store reaches version 6 with the three tables and the new column
- [ ] Full suite passes with the updated pins
- [ ] Committed with Task 1.5

**Files to Create**: `006_change_feed_and_detection.sql`, `src/amoeba/store/sql_feed.py`
**Files to Modify**: `store/migrations.py`, version-pinning tests

---

### Task 1.4: Test migration 006
**Owner**: Junior AI
**Dependencies**: Task 1.3
**Effort**: 2
**Objective**: Prove the upgrade preserves a version-5 store (LLD Technical Requirements).

**Steps**:
- [ ] Add `tests/store/test_migration_006.py` modeled on `test_migration_005.py`
- [ ] Build a version-5 store (use `migrate(connection, expected_version=5)`) holding nodes, journal entries, submissions, messages, and a verdict with findings; migrate to 6
- [ ] Assert every pre-existing row is intact, `changes` is empty, `change_head` source (max seq) is 0, existing verdicts have a null `source_document`, and the previous-round index has the new column list
- [ ] Assert the duplicate-column / re-apply case fails loudly rather than silently (same as 005's test, if it has one)

**Success Criteria**:
- [ ] New tests pass; full suite passes
- [ ] Committed with Task 1.5

**Files to Create**: `tests/store/test_migration_006.py`

---

### Task 1.5: Add `mapping_feed.py` and test it
**Owner**: Junior AI
**Dependencies**: Task 1.4
**Effort**: 2
**Objective**: Row → record mapping that fails on unknown vocabulary values, like the other `mapping_*.py` files.

**Steps**:
- [ ] Create `src/amoeba/store/mapping_feed.py` with `map_change`, `map_watch`, `map_detected_review`. Follow `mapping_journal.py`: an unknown `kind` or `outcome` raises `UnknownVocabularyValueError`; `payload` JSON is decoded; booleans from 0/1
- [ ] Add `tests/store/test_mapping_feed.py`: a valid row of each type maps; an unknown kind and an unknown outcome raise; a malformed payload raises rather than returning `{}`

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(store): add migration 006 tables, feed models, and mapping`

**Files to Create**: `src/amoeba/store/mapping_feed.py`, `tests/store/test_mapping_feed.py`

---

## Section 2: Emission Triggers

All triggers go in `006_change_feed_and_detection.sql`. Each trigger writes one `changes` row in the writer's transaction, with `payload` built by `json_object` and `recorded_at` copied from the row's own timestamp. Column and kind literals follow the LLD payload table; the invariant test (Task 5.5) ties the literals to the enums.

### Task 2.1: Trigger for node creation
**Owner**: Junior AI
**Dependencies**: Task 1.5
**Effort**: 2
**Objective**: `node_created` change, carrying `kind`, `parent_id`, and the initial `status`.

**Steps**:
- [ ] Add `AFTER INSERT ON nodes` trigger per the LLD payload table (`node_id` and `subject_id` both the node)
- [ ] Add `tests/store/test_feed_triggers.py` with a helper that reads raw `changes` rows (the read API arrives in Task 4.1)
- [ ] Test: creating a node via the store's own method adds exactly one `node_created` row in the same transaction; a rolled-back creation adds none

**Success Criteria**:
- [ ] Both tests pass; no writer code changed (`git diff` shows no edits under `store/nodes.py`)
- [ ] Committed with Task 2.2

**Files to Modify**: migration 006
**Files to Create**: `tests/store/test_feed_triggers.py`

---

### Task 2.2: Trigger for node status change
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 2
**Objective**: `node_status_changed` with `from` and `to`, only when status actually changes (D8).

**Steps**:
- [ ] Add `AFTER UPDATE OF status ON nodes ... WHEN old.status IS NOT new.status`
- [ ] Tests, using the store's real methods: a status update emits one row; an update to the same status emits none; block and resolve (via `blocking.py` paths) each emit the right `from`/`to`; the `recorded_at` equals the node's `updated_at`

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(store): emit node changes by trigger`

**Files to Modify**: migration 006, `tests/store/test_feed_triggers.py`

---

### Task 2.3: Triggers for verdicts and messages
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 3
**Objective**: `verdict_recorded` and `message_posted` (LLD payload table), covering every writer including recovery's escalation messages.

**Steps**:
- [ ] Add `AFTER INSERT ON verdicts` (payload `verdict`, `review_type`, `provider_failure` as a JSON boolean, not 0/1) and `AFTER INSERT ON messages` (payload `channel`; `node_id` may be null)
- [ ] Tests, each as its own case: a verdict recorded with `record_verdict` emits one row; a retried `record_verdict` with the same id emits none; a provider-failure verdict has `provider_failure` true; an intent submission posts a message and emits one `message_posted`; a recovery escalation message (stage a journal entry whose kind has no observer, run `reconcile` as `tests/test_recovery.py` does) emits one `message_posted`
- [ ] Confirm no `verdict_recorded` payload carries a trust label

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(store): emit verdict and message changes by trigger`

**Files to Modify**: migration 006, `tests/store/test_feed_triggers.py`

---

## Section 3: `source_document` (D7)

### Task 3.1: Add `source_document` to `VerdictInput`, the writer, mapping, and payload
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 3
**Objective**: Carry the reviewed document through the store (LLD D7). This changes 104's contract additively.

**Steps**:
- [ ] Add `source_document: str | None = None` to `VerdictInput` and the matching field to `VerdictRecord` (`store/evidence_models.py`)
- [ ] Add the column to the insert statement and select columns in `sql_evidence.py`; map it in `mapping_evidence.py`; pass it in `_verdict_writer.py`
- [ ] Add the optional field to `VerdictPayload` (`inbox/evidence_payloads.py`) and to `_apply_verdict` / `verdict_from_payload` / `verdict_payload.py`. If `verdict_payload.py` keeps `VERDICT_*` key constants, add one for it (defined once)
- [ ] Do not edit any existing test to make it pass; if one fails, stop and diagnose

**Success Criteria**:
- [ ] Every existing 104 test passes unchanged
- [ ] A verdict recorded with a `source_document` reads back with it; one without reads back `None`
- [ ] Committed with Task 3.3

**Files to Modify**: `store/evidence_models.py`, `store/sql_evidence.py`, `store/mapping_evidence.py`, `store/_verdict_writer.py`, `store/verdict_payload.py`, `inbox/evidence_payloads.py`

---

### Task 3.2: Group `finding_changes` by `source_document`
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 3
**Objective**: Previous round = same node, same `review_type`, same `source_document` (compared with `IS`, so two nulls match).

**Steps**:
- [ ] Read `SELECT_EARLIER_ROUNDS` in `sql_evidence.py` and `_previous_round` in `verdicts.py`
- [ ] Add the `source_document` condition (using `IS`) and pass the target's value as a parameter
- [ ] Do not touch the comparable-standings filter

**Success Criteria**:
- [ ] All 104 `finding_changes` tests pass unchanged
- [ ] Committed with Task 3.3

**Files to Modify**: `store/sql_evidence.py`, `store/verdicts.py`

---

### Task 3.3: Test series separation by `source_document`
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 2
**Objective**: One new test covers the part-1 / part-2 case (LLD D7); 104's behavior is unchanged for nulls.

**Steps**:
- [ ] Add `tests/store/test_finding_changes_source_document.py`, using `tests/evidence_harness.py` helpers where they fit
- [ ] Case 1: on one node and one review type, record part 1 round 1, part 2 round 1, part 1 round 2 (distinct `source_document`s). Part 1 round 2's previous round is part 1 round 1, never part 2
- [ ] Case 2: all verdicts with null `source_document` behave as before (previous round is the latest earlier comparable one)
- [ ] Case 3: the `verdict` inbox payload accepts and stores the optional field (one assertion through `apply_submission`)

**Success Criteria**:
- [ ] Tests pass; full suite passes
- [ ] Commit, e.g. `feat(store): separate review series by source document`

**Files to Create**: `tests/store/test_finding_changes_source_document.py`

---

## Section 4: Feed Reads and `read_transaction`

### Task 4.1: Add `changes` and `change_head` (the `FeedOperations` mixin)
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 3
**Objective**: The feed read API (LLD "API Contracts").

**Steps**:
- [ ] Add select statements to `sql_feed.py`: changes with `seq > after` for a project in `seq` order with a limit; max `seq` for a project (0 when none)
- [ ] Create `src/amoeba/store/feed.py` with `FeedOperations(StoreBase)` providing `changes(project_id, *, after=0, limit)` and `change_head(project_id)`. `limit` has no default (no magic defaults); reject `limit < 1` with `ValueError`
- [ ] Add the mixin to `Store`'s bases (`store/store.py`) and export `Change`, `ChangeKind`, `DetectionOutcome`, `ReviewWatch`, `DetectedReview`, `DetectionInput` from `store/__init__.py`
- [ ] Switch `tests/store/test_feed_triggers.py` to the read API where convenient

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 4.2

**Files to Create**: `src/amoeba/store/feed.py`
**Files to Modify**: `store/sql_feed.py`, `store/store.py`, `store/__init__.py`

---

### Task 4.2: Test `changes` and `change_head`
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 2
**Objective**: Pin ordering, cursor, scoping, limit.

**Steps**:
- [ ] Add `tests/store/test_feed_reads.py`: empty project gives `[]` and head 0; `after` returns only later rows in order; `limit` caps the result; two projects' feeds are independent; `seq` has no gaps after a mixed sequence of writes; payload is a decoded mapping
- [ ] Add a public-API check that the new names are exported (follow `tests/test_public_api.py`)

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(store): add changes and change_head`

**Files to Create**: `tests/store/test_feed_reads.py`
**Files to Modify**: `tests/test_public_api.py`

---

### Task 4.3: Add `read_transaction()` to the read-only handle (D1a)
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 3
**Objective**: Make a state snapshot and `change_head` atomic against a concurrent commit.

**Steps**:
- [ ] Read `Store.open_read_only` and `_connect_read_only`; the connection uses `isolation_level="DEFERRED"`
- [ ] Add `read_transaction() -> AbstractContextManager[None]` to `Store`: `BEGIN` on entry, `COMMIT` on normal exit; if the block raises, roll back to release the read lock, then re-raise. Statement text comes from `sql.py` constants. Raise a clear error if called on a handle with a transaction already open (no nesting)
- [ ] Per the LLD it lives on the read-only handle. `Store` is one class for both modes, so if the class cannot tell its mode, document in the docstring that it is intended for read-only handles; do not add mode tracking
- [ ] Docstring shows the snapshot-then-head usage from the LLD

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 4.4

**Files to Modify**: `store/store.py`, `store/sql.py`

---

### Task 4.4: Test `read_transaction()` against a concurrent commit
**Owner**: Junior AI
**Dependencies**: Task 4.3
**Effort**: 3
**Objective**: The LLD D1a test: a write committed between two reads is observed by neither.

**Steps**:
- [ ] Add `tests/store/test_read_transaction.py`. Seed state with a read-write store in a temp dir; open a second, read-only handle on the same file
- [ ] Inside `read_transaction()`: read state, commit a new node from the read-write store, then read `change_head()`. Assert the head equals the pre-write head. After the block, a fresh read sees the new head
- [ ] Control case: the same sequence **without** `read_transaction()` sees the write in the second read (proves the primitive is what makes the difference). If the control does not differ, stop and tell the PM rather than weakening the test
- [ ] An exception inside the block rolls back and releases the lock: afterward a writer commit is not blocked and the exception propagates

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(store): add read_transaction to the read-only handle`

**Files to Create**: `tests/store/test_read_transaction.py`

---

## Section 5: Detection Storage and the `watch_reviews` Kind

### Task 5.1: `record_detection`, `detections`, and the `review_detected` trigger
**Owner**: Junior AI
**Dependencies**: Task 4.4
**Effort**: 3
**Objective**: The ledger write path (LLD API Contracts) and its change emission (D8).

**Steps**:
- [ ] Add to `sql_feed.py`: insert-or-ignore on `(project_id, path, digest)`, select by key, select ledger in detection order with an optional outcome filter, and `recorded_since` support (a select of whether a verdict with a given `record_id` exists; `record_id` is the verdict id 105 uses)
- [ ] Add to `FeedOperations`: `record_detection(DetectionInput) -> DetectedReview` (idempotent: a repeat returns the existing row unchanged, no second row), `detections(project_id, *, outcome=None)`, and `recorded_since(project_id, record_id) -> bool`
- [ ] Add the `AFTER INSERT ON detected_reviews ... WHEN new.outcome NOT IN (...)` trigger. Take the excluded literals from the silent set in `feed_models.py`; write them into the SQL once, with a comment pointing at the enum
- [ ] `ingested` and `unattributed` rows with a node carry that `node_id`; payload is `outcome` and `path`

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 5.2

**Files to Modify**: `store/sql_feed.py`, `store/feed.py`, migration 006

---

### Task 5.2: Test the ledger and its trigger
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 2
**Objective**: Pin idempotency, ordering, filtering, and silent outcomes.

**Steps**:
- [ ] Add `tests/store/test_detections.py`: each outcome records; a repeated key returns the first row and inserts nothing; `detections(outcome=...)` filters; order is detection order
- [ ] Trigger cases in `test_feed_triggers.py`: `ingested`, `unattributed`, `unparseable` each emit one `review_detected`; `baseline` and `runner_issued` emit none; a repeated `record_detection` emits none
- [ ] `recorded_since` is false, then true after a verdict with that id is recorded by any path

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(store): add detection ledger and review_detected changes`

**Files to Create**: `tests/store/test_detections.py`
**Files to Modify**: `tests/store/test_feed_triggers.py`

---

### Task 5.3: Add the `watch_reviews` inbox kind, watch reads, and baseline write
**Owner**: Junior AI
**Dependencies**: Task 5.2
**Effort**: 4
**Objective**: Register or deactivate a directory (LLD "Registering a directory", "Inbox, the `watch_reviews` kind").

**Steps**:
- [ ] Follow the three-part rule in `SubmissionKind`'s docstring: add `WATCH_REVIEWS = "watch_reviews"`; add `WatchReviewsPayload` (`reviews_dir: str`, absolute path validated by pydantic, `active: bool`) to `inbox/envelope.py` and `KIND_PAYLOAD_MODELS`; add the effect to `KIND_EFFECTS` in `store/inbox.py`
- [ ] Effect: upsert `review_watches`; first activation leaves `baselined_at` null; reactivating an existing watch updates `active` and `updated_at` and does **not** clear `baselined_at`. A relative path is quarantined as invalid by the envelope layer, not rejected by the effect
- [ ] Add `watches(project_id)` and `baseline_watch(project_id, reviews_dir, entries)` to `FeedOperations`. The latter, in one transaction, inserts one `baseline` ledger row per `(path, digest)` and sets `baselined_at`; nothing is written if it raises
- [ ] Confirm the `amoeba submit watch-reviews` subcommand appears automatically (`cli/submit.py` derives subcommands from `SubmissionKind`; flag `--active` must accept `true|false` under 104's flag rule). Fix only if it does not
- [ ] Update the test that pins the kind set and any envelope-version/kind-coverage tests

**Success Criteria**:
- [ ] `amoeba submit watch-reviews --help` lists `--reviews-dir` and `--active`
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 5.4

**Files to Modify**: `store/inbox_models.py`, `inbox/envelope.py`, `store/inbox.py`, `store/feed.py`, `store/sql_feed.py`

---

### Task 5.4: Test the kind, watches, and baseline write
**Owner**: Junior AI
**Dependencies**: Task 5.3
**Effort**: 3
**Objective**: Pin registration semantics.

**Steps**:
- [ ] Add `tests/store/test_watch_reviews.py`: register creates a watch with `baselined_at` null; deactivate then reactivate keeps `baselined_at`; a replayed submission is a no-op; a relative path is rejected at the envelope (`tests/inbox/test_envelope.py` style)
- [ ] `baseline_watch` writes one row per file plus `baselined_at` atomically; force a failure partway (an invalid outcome in the batch) and assert no rows and `baselined_at` still null
- [ ] Extend `tests/cli/test_submit.py` with `submit watch-reviews` flag parsing (`--active true`, `--active false`)

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(inbox): add watch_reviews kind and watch storage`

**Files to Create**: `tests/store/test_watch_reviews.py`
**Files to Modify**: `tests/cli/test_submit.py`

---

### Task 5.5: The invariant test
**Owner**: Junior AI
**Dependencies**: Task 5.4
**Effort**: 4
**Objective**: Prove the triggers are right (LLD "The invariant test checks every tracked table"). Riskiest piece; it gates the rest.

**Steps**:
- [ ] Create `tests/store/test_feed_invariant.py` with a scripted sequence through every write path that exists: node create, status updates, block and resolve, verdicts (including a retried one and a provider failure), an intent message, a recovery escalation, and detections of all five outcomes
- [ ] Replay the feed from seq 0 and reconcile table by table, exactly as the LLD lists: node ids and rebuilt statuses; verdict ids; message ids; ledger ids excluding `baseline` and `runner_issued`
- [ ] Assert every `ChangeKind` member appears at least once
- [ ] Assert the literals in the migration SQL match the enums: read the trigger SQL from `sqlite_master` and check each `ChangeKind` value and each silent outcome appears in it
- [ ] Prove the test catches a miss: temporarily drop one trigger in a scratch copy of the store inside the test (not in the migration) and assert the reconciliation then fails

**Success Criteria**:
- [ ] All assertions pass on the real migration; the drop-a-trigger case fails reconciliation as expected
- [ ] Full suite, `ruff`, `pyright` clean
- [ ] Commit, e.g. `test(store): add feed invariant test`

**Files to Create**: `tests/store/test_feed_invariant.py`

---

## Section 6: Attribution and Review-Producing Kinds

### Task 6.1: Define the review-producing kinds set
**Owner**: Junior AI
**Dependencies**: Task 5.5
**Effort**: 1
**Objective**: One definition of which journal kinds produce reviews (LLD D5).

**Steps**:
- [ ] Add a frozen set in `store/journal_models.py` (e.g. `REVIEW_PRODUCING_KINDS`) containing `CommandKind.SQ_RUN` only, with a comment: initiative 120 adds its review command kind here
- [ ] Add a store read (in `journal.py`/`sql_journal.py`, following existing conventions) answering whether a project has an unresolved entry whose kind is in the set. Reuse the existing unresolved-entries select if one exists

**Success Criteria**:
- [ ] Committed with Task 6.3

**Files to Modify**: `store/journal_models.py`, `store/journal.py`, `store/sql_journal.py`

---

### Task 6.2: Implement `attribute_review`
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 2
**Objective**: The attribution rule (LLD D4), defined once and exported.

**Steps**:
- [ ] Create `src/amoeba/store/attribution.py`: `Attribution(node_id: str | None, candidates: tuple[str, ...])` frozen dataclass and `attribute_review(store, project_id, slice_name) -> Attribution`. Match nodes with `kind == slice` and `cf.slice_name == slice_name` in that project only
- [ ] Exactly one match: `node_id` set. Zero or several: `node_id` None and `candidates` lists every match id (empty for zero). A `slice_name` of `None` (a review with no `slice`) is handled explicitly as zero matches, not by a crash
- [ ] Use an existing node listing read; add SQL only if none fits (in `sql.py`). Export both names from `store/__init__.py`

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 6.3

**Files to Create**: `src/amoeba/store/attribution.py`
**Files to Modify**: `store/__init__.py`

---

### Task 6.3: Test attribution and the kinds set
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 2
**Objective**: The LLD's "table of cases".

**Steps**:
- [ ] Add `tests/store/test_attribution.py`: one matching slice node; zero matches; two matching nodes (both ids listed); a node with the right name but `kind` not slice; same name in another project; `slice_name` None
- [ ] Test the open-entry read: false with no entries; true with an open `SQ_RUN` entry; false with an open `CF_WRITE` entry; false after the `SQ_RUN` entry resolves

**Success Criteria**:
- [ ] Tests pass; full suite passes
- [ ] Commit, e.g. `feat(store): add review attribution and review-producing kinds`

**Files to Create**: `tests/store/test_attribution.py`

---
