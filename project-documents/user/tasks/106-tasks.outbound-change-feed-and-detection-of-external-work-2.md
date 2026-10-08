---
docType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
lld: user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md
dependencies: [101, 102, 103, 104, 105]
projectState: Sections 1–5 (file 1) are complete — migration 006, triggers, `source_document`, the feed read API with `read_transaction()`, the detection ledger, and the `watch_reviews` kind with watch storage. This file adds attribution, the one-transaction ingest, the follower, the review sources, and the detection tenant. Sections 8 onward require slice 105's parser to be merged.
dateCreated: 20261007
dateUpdated: 20261007
status: not_started
---

## Context Summary

- Working on the **outbound-change-feed-and-detection-of-external-work** slice (106), continued from `106-tasks.outbound-change-feed-and-detection-of-external-work-1.md`. Read that file's Context Summary, branch, reading note, and commit cadence; they apply here unchanged.
- **Sections in this file:** 6 attribution, review-producing kinds, and the one-transaction ingest (continued from file 1's Section 5); 7 follower and `amoeba feed`; 8 review sources; 9 `ReviewDetectionTenant`. Sections 10–11 are in `106-tasks.outbound-change-feed-and-detection-of-external-work-3.md`.
- **Models for new code:** `InboxTenant` (`process/inbox_tenant.py`) for the tenant's host protocol, attempts sidecar, and bounded-failure shape; `inbox/sidecars.py` and `inbox/durable.py` for `AttemptsSidecar` and `write_durably`; `cli/inspect_inbox.py` and `cli/inspect_evidence.py` for listing modules; `cli/settings_flags.py` for flags.
- **Branch:** still `106-slice.outbound-change-feed-and-detection-of-external-work`. No task here merges.

---

## Section 6: Attribution and Review-Producing Kinds

### Task 6.1: Define the review-producing kinds set
**Owner**: Junior AI
**Dependencies**: Task 5.9
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

### Task 6.4: Add `record_detected_verdict` (one-transaction ingest)
**Owner**: Junior AI
**Dependencies**: Task 6.3
**Effort**: 3
**Objective**: Record a verdict and its `ingested` ledger row in one transaction, so detection can never leave a verdict with no ledger row (LLD "Detecting a review").

**Steps**:
- [ ] Read `_verdict_writer.py` and `apply_submission` in `store/inbox.py`. `apply_submission` already runs the verdict write inside its own `BEGIN IMMEDIATE`; reuse that shape. If the verdict write is not callable inside an already-open transaction, extract its body into an inner method (no behavior change; 104's tests prove it)
- [ ] Add `record_detected_verdict(verdict: VerdictInput, detection: DetectionInput) -> tuple[VerdictRecord, DetectedReview]` to `FeedOperations`. The detection's outcome must be `ingested` (else `ValueError`, nothing written). In one transaction: record the verdict (a retry returning the existing record is fine), then insert the ledger row with that verdict's id and node id
- [ ] Idempotent: a repeat with the same verdict id and the same ledger key returns the existing records and writes nothing
- [ ] Export nothing new beyond the method; document in the docstring that it exists for the detection tenant

**Success Criteria**:
- [ ] 104's tests pass unchanged; `ruff`, `pyright` clean
- [ ] Committed with Task 6.5

**Files to Modify**: `store/feed.py`, `store/_verdict_writer.py` (only if the inner method is needed), `store/sql_feed.py`

---

### Task 6.5: Test `record_detected_verdict`
**Owner**: Junior AI
**Dependencies**: Task 6.4
**Effort**: 2
**Objective**: Pin atomicity and idempotence.

**Steps**:
- [ ] Add `tests/store/test_record_detected_verdict.py`: success writes one verdict and one `ingested` row, emitting one `verdict_recorded` then one `review_detected`; a repeat writes nothing; a failure injected on the ledger insert (e.g. a duplicate key with a different verdict id, or a patched statement) leaves no verdict behind; a non-`ingested` outcome raises `ValueError` and writes nothing

**Success Criteria**:
- [ ] Tests pass; full suite passes
- [ ] Commit, e.g. `feat(store): record a detected verdict and its ledger row atomically`

**Files to Create**: `tests/store/test_record_detected_verdict.py`

---

---

## Section 7: The Follower and `amoeba feed`

### Task 7.1: Implement `amoeba.feed.follow`
**Owner**: Junior AI
**Dependencies**: Task 6.3
**Effort**: 4
**Objective**: The subscriber-side blocking iterator (LLD "Following the feed", D2).

**Steps**:
- [ ] Create `src/amoeba/feed/__init__.py` and `follower.py`. `FeedSettings` is a frozen dataclass with `follow_interval_seconds = 0.25` and `feed_batch_size = 500`, defined here once (no other default for either anywhere)
- [ ] `follow(store_dir, project_id, *, after, settings, stop=None) -> Iterator[Change]`. Open the project store with `Store.open_read_only` (path from `store_dir`; reuse `store_path_for` in `process/supervisor.py` only if importing it does not make `amoeba.feed` depend on `amoeba.process` — otherwise use `store/paths`). An unknown project raises the store's error before yielding anything
- [ ] Loop per the LLD: read `changes(after=cursor, limit=feed_batch_size)`, yield each, advance the cursor to the last `seq`; when empty, wait until `PRAGMA data_version` changes, checking every `follow_interval_seconds`; check `stop` between waits and between yielded changes, and return when it is true
- [ ] Put the `PRAGMA data_version` statement in `store/sql.py` and expose it as a small `Store` method (e.g. `data_version()`); the follower holds no SQL
- [ ] Close the store in a `finally` (generator closure included)
- [ ] `amoeba.feed` must not import `amoeba.process`

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 7.2

**Files to Create**: `src/amoeba/feed/__init__.py`, `src/amoeba/feed/follower.py`
**Files to Modify**: `store/sql.py`, `store/store.py`

---

### Task 7.2: Test the follower
**Owner**: Junior AI
**Dependencies**: Task 7.1
**Effort**: 4
**Objective**: Resume, catch-up, waiting, and shutdown (LLD Functional Requirements, feed bullets).

**Steps**:
- [ ] Add `tests/feed/__init__.py` (if other test packages use one) and `tests/feed/test_follower.py`; use a small `FeedSettings` (e.g. a few milliseconds) built in the test, never the production default
- [ ] `after=N` yields exactly the changes after N; `after=0` yields all
- [ ] Wake-up: start `follow` in a thread, commit a node from a read-write store, assert the change arrives within a generous multiple of the interval; no change arrives while idle
- [ ] Resume: consume part of a stream, record the last `seq`, start a new `follow` from it, and assert no gap and no repeat; the `changes` table row count is unchanged by following
- [ ] `stop` returning true ends the iterator; closing the generator closes the store (no open handle left)
- [ ] Unknown project raises before any yield; a store at the wrong schema version raises `StoreSchemaError`
- [ ] Batching: with `feed_batch_size` of 2 and five changes, all five arrive in order

**Success Criteria**:
- [ ] Tests pass, no sleeps longer than needed, no flakiness over three consecutive runs of the module
- [ ] Commit, e.g. `feat(feed): add follow, the subscriber-side change follower`

**Files to Create**: `tests/feed/test_follower.py`

---

### Task 7.3: Add the `amoeba feed` command
**Owner**: Junior AI
**Dependencies**: Task 7.2
**Effort**: 3
**Objective**: Print changes as JSON lines (LLD CLI table).

**Steps**:
- [ ] Create `src/amoeba/cli/feed.py` and register `feed` in `cli/main.py` the way `inspect` and `submit` are registered, with `--project` (required), `--after` (non-negative int, default stated in `--help`: from the start), `--follow`
- [ ] One JSON object per line, keys as in `Change` (`seq, project_id, kind, node_id, subject_id, payload, recorded_at` with `recorded_at` as ISO text), flushed per line so a pipe consumer sees it at once
- [ ] Without `--follow`: print everything after `--after` and exit 0 (loop `follow` with a `stop` that is true once the head read at start is reached — or read in batches; choose the simpler and note it in the docstring). With `--follow`: run until interrupted; `KeyboardInterrupt` and `SIGTERM` exit cleanly with `ExitCode.OK`
- [ ] Unknown project or missing store maps to the existing `ExitCode` for those errors (see `_dispatch` / the boundary handler in `main.py`); add no new exit code unless none fits, and then ask the PM
- [ ] The command takes no lock and works with the process running or stopped

**Success Criteria**:
- [ ] `amoeba feed --help` lists the three flags
- [ ] Committed with Task 7.4

**Files to Create**: `src/amoeba/cli/feed.py`
**Files to Modify**: `src/amoeba/cli/main.py`

---

### Task 7.4: Test `amoeba feed` through the CLI
**Owner**: Junior AI
**Dependencies**: Task 7.3
**Effort**: 3
**Objective**: Real-subprocess behavior (use `tests/cli_harness.py`).

**Steps**:
- [ ] Add `tests/cli/test_feed.py`: seed a store (via the supervisor-dir harness other CLI tests use), run `amoeba feed --project P`; each line parses as JSON with exactly the `Change` keys; exit code 0; process stopped
- [ ] `--after N` prints only later lines; an unknown project exits with the not-found code and prints nothing on stdout
- [ ] `--follow` as a subprocess: read the first lines, write a new change from a read-write store, assert the new line arrives, send SIGTERM, assert clean exit
- [ ] `--follow` started while no process is running (store exists, no lock held): it prints existing changes, then, when a separate read-write store handle commits a new node (standing in for the process), prints the new line. The full process-starts case is in Task 11.2
- [ ] Killed follower: `kill -9` a `--follow` subprocess mid-stream, restart with `--after` its last printed `seq`, assert no gap and no repeat

**Success Criteria**:
- [ ] Tests pass; the `changes` table row count is unchanged by any run
- [ ] Commit, e.g. `feat(cli): add amoeba feed`

**Files to Create**: `tests/cli/test_feed.py`

---

## Section 8: Review Sources

### Task 8.1: Gate on slice 105 and pass `source_document` through the parser
**Owner**: Junior AI
**Dependencies**: Task 7.4
**Effort**: 2
**Objective**: Confirm the parser exists, and finish the pass-through 105 deliberately left to this slice (105 LLD, `source_document` note).

**Steps**:
- [ ] Check that `amoeba.upstream.squadron` exports `parse_review_artifact`, `ParsedReview`, `to_verdict_input`, and `review_record_id`, and that `ParsedReview` has `slice` and `source_document`. **If any is missing, stop and tell the PM: Sections 8–11 cannot proceed until 105 is merged into the target.** Do not stub the parser
- [ ] In `to_verdict_input`, pass `ParsedReview.source_document` to `VerdictInput.source_document` (one line). `slice` still does not reach `VerdictInput`
- [ ] Update 105's test(s) that assert `source_document` does not reach `VerdictInput`, to assert it does. Change nothing else in 105's tests
- [ ] Confirm `review_record_id` is a digest of the parsed review (changes only with parsed content). Add one test here if 105's suite lacks "a `resolution:` key added to a real fixture leaves the id unchanged"; otherwise rely on it

**Success Criteria**:
- [ ] 105's suite passes with only the intended assertion changed
- [ ] Commit, e.g. `feat(upstream): pass source_document into VerdictInput`

**Files to Modify**: `src/amoeba/upstream/squadron/review.py` (or wherever `to_verdict_input` lives), the 105 test that pinned the old behavior

---

### Task 8.2: Define `ReviewSource` and `DetectedFile`
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 1
**Objective**: The one interface for where reviews come from (LLD D6).

**Steps**:
- [ ] Create `src/amoeba/process/review_sources.py` with `DetectedFile` (frozen: `path`, `content: bytes`, `observed_at`) and a `ReviewSource` protocol with `poll() -> Sequence[DetectedFile]`
- [ ] Docstring states the S8 swap: an event-based source implements the same method; the tenant, ledger, attribution, and feed do not change

**Success Criteria**:
- [ ] Committed with Task 8.4

**Files to Create**: `src/amoeba/process/review_sources.py`

---

### Task 8.3: Implement `DirectoryReviewSource`
**Owner**: Junior AI
**Dependencies**: Task 8.2
**Effort**: 4
**Objective**: Top-level `*.md` listing with the settle rule and the file-race table (LLD "Settled", D6).

**Steps**:
- [ ] Constructor takes the directory and keeps the last-scan `(size, mtime_ns)` per path in memory
- [ ] `poll()` lists regular `*.md` files at the top level only (no recursion; ignore directories, sockets, other suffixes). A file is returned only when its signature equals the one remembered from the previous poll; a first sighting is remembered and not returned
- [ ] Read bytes only for settled files. The `DetectedFile` content is the bytes actually read; a file that changed between the settle check and the read is not specially handled (its new signature will differ next poll)
- [ ] Race table, exactly per D6: `FileNotFoundError` on stat or read drops the file and forgets its signature (no row, no error); `PermissionError` logs one WARNING per file until it becomes readable, then it is returned normally; neither is a ledger row
- [ ] A missing or unreadable directory raises a typed error (`ReviewDirectoryUnavailableError`, defined next to the source) so the tenant can report `unreachable`; never returns an empty list for it
- [ ] The source does not write anywhere and does not resolve symlinks (paths as given)

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 8.4

**Files to Modify**: `src/amoeba/process/review_sources.py` (split a `directory_source.py` if the file passes ~300 lines)

---

### Task 8.4: Test the review sources
**Owner**: Junior AI
**Dependencies**: Task 8.3
**Effort**: 3
**Objective**: Pin settling and every race row, using real review files from `tests/fixtures/sq_reviews/`.

**Steps**:
- [ ] Add `tests/process/test_review_sources.py`. Copy real fixtures into a `tmp_path` directory; never hand-build a review
- [ ] Settle: first poll returns nothing; second poll (no change) returns the file; a size or mtime change resets settling
- [ ] Ignored: subdirectory (with an `.md` inside, proving non-recursion), a non-`.md` file, a directory named `x.md`
- [ ] Races: a file removed between polls produces no result and no error; a patch of `os.stat`/read raising `FileNotFoundError` mid-poll is dropped and, if it returns, settles from scratch; an unreadable file (mode 000, skipped where the test runner is root) warns once across several polls, then is returned after `chmod`
- [ ] A removed directory raises `ReviewDirectoryUnavailableError`; restoring it resumes
- [ ] `DetectedFile.content` equals the file's bytes

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(process): add ReviewSource and DirectoryReviewSource`

**Files to Create**: `tests/process/test_review_sources.py`

---

## Section 9: `ReviewDetectionTenant`

### Task 9.1: Add the three settings and the `sq --version` label
**Owner**: Junior AI
**Dependencies**: Task 8.4
**Effort**: 3
**Objective**: Settings (LLD "Settings") and the once-at-start label.

**Steps**:
- [ ] Add `review_scan_interval_seconds = 2.0`, `sq_timeout_seconds = 10.0`, `detection_max_attempts = 3` to `ProcessSettings` with docstring entries stating what each bounds, in the file's style. Add the three `start` flags in `cli/settings_flags.py` (use `positive_int` for attempts) and map them in the settings-building code that reads those flags
- [ ] Generalize `capture_version_label` in `process/observers/cf_readback.py`: extract its subprocess logic into a shared helper parameterized by executable name, used by both cf and sq. cf behavior, logging, and `VERSION_UNAVAILABLE` stay the same; existing cf tests pass unchanged. Define the `sq` executable name and version args once, next to the helper
- [ ] No tick may start a subprocess. The tenant takes the label from a value captured before the loop (Task 10.3 does the capture and wiring); here only the helper exists

**Success Criteria**:
- [ ] Existing observer, settings, and lifecycle tests pass; `--help` for `start` lists the three flags
- [ ] Committed with Task 9.2

**Files to Modify**: `process/settings.py`, `cli/settings_flags.py`, `process/observers/cf_readback.py` (or a new shared module)

---

### Task 9.2: Test the settings, flags, and label helper
**Owner**: Junior AI
**Dependencies**: Task 9.1
**Effort**: 2
**Objective**: Pin defaults, flag mapping, and the sq label path.

**Steps**:
- [ ] Extend the existing settings/flag tests: the three defaults come from `ProcessSettings` (flags repeat none); a flag overrides each; `--detection-max-attempts 0` is refused
- [ ] Label helper: with a fake `sq` executable on `PATH` (a tmp script), the label is its trimmed stdout; a missing executable, a non-zero exit, and a timeout each return `VERSION_UNAVAILABLE`. Follow `tests/test_observer_cf_readback.py` for the fake-executable pattern

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(process): add detection settings and shared version-label capture`

**Files to Modify**: existing settings/flag tests; **Create** `tests/test_version_label.py` if no fitting file exists

---

### Task 9.2a: Sidecar layout, parked-file reader, and `watch_state`, with tests
**Owner**: Junior AI
**Dependencies**: Task 9.2
**Effort**: 3
**Objective**: Define the on-disk attempts layout and the pure read functions once, before the tenant and the listings use them.

**Steps**:
- [ ] Create `src/amoeba/process/detection_layout.py`: the path `{store_dir}/detection/attempts/{project_id}/{key}.attempts.json` with directory names and suffix defined once, and the two key forms (`{digest}` for files; `baseline-{sha256 of the dir}` for baselines)
- [ ] Add `parked_files(store_dir, project_id, max_attempts) -> list[ParkedFile]` (key, attempts, last error, last failed time) reading `AttemptsSidecar` files at or above `max_attempts`. This module owns the reader; Task 9.9 and Task 10.1 import it and define no reader of their own. A malformed sidecar is reported (raise `SidecarError`'s subtype or skip with a WARNING naming the file — pick the warning, since one bad sidecar must not hide the others)
- [ ] Add `watch_state(watch, directory_listable, store_dir, max_attempts) -> str` returning `failed` (a baseline sidecar at or above the limit), `baseline_pending` (active, `baselined_at` null, directory listable), `unreachable` (not listable), else `ok`. The state strings are a `StrEnum` defined here once. Pure: it takes the listability as an argument and touches no filesystem except the sidecar directory
- [ ] Add `tests/process/test_detection_layout.py`: path and key forms; `parked_files` returns only sidecars at or above the limit and tolerates one malformed file; `watch_state` returns each of the four values, including `failed` staged with a real written sidecar

**Success Criteria**:
- [ ] Tests, `ruff`, `pyright` pass
- [ ] Commit, e.g. `feat(process): add detection sidecar layout and watch_state`

**Files to Create**: `src/amoeba/process/detection_layout.py`, `tests/process/test_detection_layout.py`

---

### Task 9.3: Implement the tenant skeleton and baselining
**Owner**: Junior AI
**Dependencies**: Task 9.2a
**Effort**: 3
**Objective**: Tenant registration shape, scan cadence, and the all-or-nothing baseline (LLD "Registering a directory" and its failure table).

**Steps**:
- [ ] Create `src/amoeba/process/review_detection.py` with `ReviewDetectionTenant(supervisor_dir, *, version_label, source_factory)`; `name` property; `tick(host) -> bool` using the same `Host` protocol shape as `InboxTenant`. `source_factory` builds a `ReviewSource` for a directory (default `DirectoryReviewSource`) so tests can substitute a source
- [ ] A tick does nothing unless `review_scan_interval_seconds` has elapsed since the last scan (use a clock passed in or `time.monotonic`; tests must not sleep for the real interval)
- [ ] For each open project, for each **active** watch: if `baselined_at` is null, baseline it; otherwise call a scan method that Task 9.5 fills in (here it is a stub that returns without work)
- [ ] Baseline: list and read every top-level `*.md` (not through the settle rule); any failure → write nothing, retry next scan. On success call the store's `baseline_watch` once. Failure table: missing/unreadable directory → `unreachable` (one ERROR on the transition, one INFO on recovery); one unreadable file → one WARNING naming it, watch stays `baseline_pending`; a file deleted between list and read is dropped; a store failure follows the bounded-failure rule keyed `baseline-{sha256 of the dir}` (counting and parking are built in Task 9.9, using the layout from Task 9.2a)
- [ ] Write one small reachability helper used by both baselining and scanning (Task 9.5): given a watch and whether its directory could be listed, it logs exactly one ERROR on the good→bad transition and one INFO on bad→good, remembering the last state per watch in memory, and never logs on repeat ticks
- [ ] Never write into a watched directory

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 9.4

**Files to Create**: `src/amoeba/process/review_detection.py`

---

### Task 9.4: Test baselining
**Owner**: Junior AI
**Dependencies**: Task 9.3
**Effort**: 3
**Objective**: Every row of the baseline failure table, plus the happy path.

**Steps**:
- [ ] Add `tests/process/test_review_detection_baseline.py` using `local_host` from `tests/process/conftest.py` and real fixtures copied into `tmp_path`
- [ ] Registration then tick: existing files become `baseline` rows, `baselined_at` is set, no verdict, no change on the feed
- [ ] Directory missing at registration: `watch_state` is `unreachable`, nothing ingested; created later, baselined on the next scan
- [ ] Transitions and logging (`caplog`) while baselining: across several ticks while the directory stays missing, exactly one ERROR is logged (no repeat per tick); when it appears, exactly one INFO (the scan-time case for already-baselined watches is tested in Task 9.6)
- [ ] One unreadable file: no rows, state `baseline_pending`, one WARNING; after `chmod`, whole directory baselined at once
- [ ] File deleted between list and read: dropped; a later reappearance is detected as new (Task 9.5 asserts the detection; here assert it is absent from the baseline)
- [ ] Scan interval: with an unreadable file making the baseline retry each scan, two ticks inside the interval attempt it once (count calls on a substitute `source_factory`; fake clock)
- [ ] An inactive watch is never baselined; a watch with `baselined_at` already set is never baselined again

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(process): add ReviewDetectionTenant with baselining`

**Files to Create**: `tests/process/test_review_detection_baseline.py`

---

### Task 9.5: Implement the detection path
**Owner**: Junior AI
**Dependencies**: Task 9.4
**Effort**: 4
**Objective**: Digest, ledger check, parse, attribute, record (LLD "Detecting a review").

**Steps**:
- [ ] For each `DetectedFile` from the source: `sha256` of the bytes; skip if `(project, path, digest)` is in the ledger (the parked-sidecar skip is added in Task 9.9)
- [ ] Parse with `parse_review_artifact`. On `SquadronReviewError`: `record_detection(unparseable, detail=error text)`. Catch only that base class; log at INFO, since a parse failure is an outcome. Do not catch anything wider
- [ ] Attribute with `attribute_review(store, project, parsed.slice)`. Zero or several: `record_detection(unattributed, detail=candidate ids, record_id=review_record_id(parsed))`. Exactly one: call `store.record_detected_verdict(verdict_input, detection_input)` (built and tested in Task 6.4–6.5), with `verdict_input = to_verdict_input(parsed, node_id=..., source_path=str(path), upstream_version=<label>)`. That one call records both in one transaction; the tenant never calls `record_verdict` and `record_detection` separately for an ingest
- [ ] Version label: the file's own stamp wins (105's D4 rule inside `to_verdict_input`); the tenant passes the start-up label only as the caller's fallback
- [ ] Fill in the scan method from Task 9.3: obtain the source, call `poll()`; if it raises `ReviewDirectoryUnavailableError`, report it through the reachability helper (same ERROR-once / INFO-once rule as baselining) and move on to the next watch; a successful poll reports reachable
- [ ] Set `record_id` on the ledger row for every file that parsed, including `unattributed`
- [ ] Do not retry `unparseable` or `unattributed` files: the ledger row is terminal for that digest; changed bytes make a new digest and a new attempt

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 9.6

**Files to Modify**: `src/amoeba/process/review_detection.py` (move scan logic to `review_scan.py` if the file passes ~300 lines)

---

### Task 9.6: Test the detection path with real fixtures
**Owner**: Junior AI
**Dependencies**: Task 9.5
**Effort**: 4
**Objective**: The LLD's functional bullets for ingest, attribution, and idempotence.

**Steps**:
- [ ] Add `tests/process/test_review_detection.py`. Seed a slice node with `cf.slice_name` of `resident-process-and-recovery` (the 102 series' slice) and a registered, baselined watch; copy fixtures in; tick twice (settle), assert results
- [ ] Round 1 and round 2 of part 1: two verdicts on the node, `source: artifact_frontmatter`, `source_path` the copied file, ledger `ingested`, one `verdict_recorded` and one `review_detected` change each
- [ ] The captured provider-failure file is recorded with standing `provider_failure`
- [ ] Series: `finding_changes` on part 1 round 2 names part 1 round 1 as previous, never part 2
- [ ] Hand edit: append a `resolution: accepted` frontmatter key to a detected file; next scans add one `ingested` ledger row (new digest) pointing at the **same** verdict id, and no second verdict
- [ ] No slice node for the review's slice (use the 104 review in `project-documents/user/reviews/`): `unattributed`, empty candidates, nothing written to any node. Two matching nodes: both ids in `detail`
- [ ] `# not a review` in a `.md`: `unparseable` with the parser's error, not retried until its bytes change
- [ ] Restart: build a new tenant over the same store; nothing re-ingested
- [ ] Version label: construct the tenant with a distinctive test label. A copied fixture whose frontmatter has no `squadronVersion` is recorded with that label as `upstream_version`; one whose frontmatter has a stamp keeps its own stamp; with the label set to the `VERSION_UNAVAILABLE` marker, the recorded version is that marker, not empty. Pick fixtures by checking which real files carry the key
- [ ] Already-baselined directory removed: across several ticks exactly one ERROR is logged and the process keeps ticking; restored, exactly one INFO and detection resumes with a newly copied file
- [ ] Scan interval: with a substitute source counting `poll()` calls and a fake clock, two ticks inside the interval poll once
- [ ] Reactivation: register, baseline, deactivate (`active false`), copy a new fixture in, tick (nothing happens), reactivate, tick twice: the file is detected as new and the earlier baseline rows are unchanged
- [ ] A file deleted between listing and read and later restored is detected normally (patched source)
- [ ] `unattributed` then slice node created then `ingest review` (105's function, called in-process) by hand: `recorded_since` true, a second ingest records nothing

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(process): detect external reviews and record them as verdicts`

**Files to Create**: `tests/process/test_review_detection.py`

---

### Task 9.7: Implement the defer and skip rules (D5)
**Owner**: Junior AI
**Dependencies**: Task 9.6
**Effort**: 2
**Objective**: Detection yields to the Runner for reviews the Runner launches.

**Steps**:
- [ ] Before scanning a project, call the open-review-entry read from Task 6.1; if true, skip that project this tick (no listing, no reads)
- [ ] The skip rule needs no tenant code: a `runner_issued` ledger row for `(path, digest)` already makes the existing ledger check skip the file. Confirm that by test rather than adding code
- [ ] Add a comment citing the ownership rule and the five requirements it rests on, with the two that fall on 120 (ledger mark in the resolving transaction; record from the artifact through 105's parser)

**Success Criteria**:
- [ ] Committed with Task 9.8

**Files to Modify**: `src/amoeba/process/review_detection.py`

---

### Task 9.8: Test defer and skip
**Owner**: Junior AI
**Dependencies**: Task 9.7
**Effort**: 2
**Objective**: Pin LLD bullets "While the project has an open `SQ_RUN` entry…" and "A file already marked `runner_issued`…".

**Steps**:
- [ ] Add cases to `test_review_detection.py`: with an open `SQ_RUN` entry, a settled new file is not processed and the source is not polled; after the entry resolves, it is ingested on the next scan
- [ ] A file whose `(path, digest)` is pre-marked `runner_issued` is never ingested and emits no change
- [ ] A project with an open `CF_WRITE` entry is **not** deferred

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(process): defer detection while the runner owns a review`

**Files to Modify**: `tests/process/test_review_detection.py`

---

### Task 9.9: Implement bounded failure for recording errors
**Owner**: Junior AI
**Dependencies**: Task 9.8
**Effort**: 4
**Objective**: A store failure on one file must not crash-loop the process (LLD Errors, "Counter first").

**Steps**:
- [ ] Sidecars use `AttemptsSidecar` and `write_durably` at the paths from `detection_layout.py` (Task 9.2a); do not define any path or key form here
- [ ] Add the parked-sidecar skip to the scan path from Task 9.5: a file whose digest has a sidecar at or above `detection_max_attempts` is skipped before parsing
- [ ] Before the recording transaction, write or increment the sidecar. On exception: below `detection_max_attempts`, `logger.exception` at ERROR and re-raise; at the limit, `logger.exception`, leave the sidecar, move on to the next file. On success delete the sidecar after commit. A leftover sidecar for a file already in the ledger is deleted on the next scan
- [ ] Detection skips any `(project, digest)` with a parked sidecar (count at or above the limit). Removing the sidecar by hand retries. A parked baseline leaves the watch `failed` and unscanned until the sidecar is removed

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 9.10

**Files to Modify**: `src/amoeba/process/review_detection.py`

---

### Task 9.10: Test bounded failure
**Owner**: Junior AI
**Dependencies**: Task 9.9
**Effort**: 3
**Objective**: Pin LLD bullet "A store failure while recording one file stops the process below `detection_max_attempts`…".

**Steps**:
- [ ] Add `tests/process/test_review_detection_failure.py`; inject the failure by wrapping the store's record call to raise (as `tests/process/test_inbox_tenant.py` does for apply)
- [ ] Below the limit: attempt 1 and 2 re-raise and log ERROR; the sidecar count increments; the file is not in the ledger
- [ ] At the limit: logged, no raise, a later file in the same scan is still detected, the parked file is skipped on later scans
- [ ] Removing the sidecar retries and succeeds once the failure is lifted; success deletes the sidecar
- [ ] A crash between commit and sidecar delete (simulate by leaving a sidecar for a recorded file): the next scan deletes it and records nothing new
- [ ] Baseline failure: same bounded shape; at the limit the watch reads `failed`

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(process): bound detection failures with attempts sidecars`

**Files to Create**: `tests/process/test_review_detection_failure.py`

---
