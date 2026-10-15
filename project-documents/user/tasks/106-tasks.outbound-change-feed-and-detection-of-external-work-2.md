---
docType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
lld: user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md
dependencies: [101, 102, 103, 104, 105]
projectState: Sections 1–4 (file 1) are complete — migration 006 with triggers, the invariant test, the `changes` read, `follow()` and `amoeba feed`, the detection ledger, `watch_reviews`, `baseline_watch`, and `record_detected_verdict`. This file adds attribution, the review source, `ReviewDetectionTenant`, the listings, `start` wiring, end-to-end tests, and docs.
dateCreated: 20261015
dateUpdated: 20261015
status: not_started
---

## Context Summary

- Continued from `106-tasks.outbound-change-feed-and-detection-of-external-work-1.md`. Its Context Summary, branch, reading note, commit cadence, and list of task-level additions apply unchanged.
- **Sections in this file:** 5 attribution and review-producing kinds; 6 review sources; 7 `ReviewDetectionTenant`; 8 listings, demo script, and `start` wiring; 9 end-to-end, docs, final validation.
- **Models for new code:** `InboxTenant` (`process/inbox_tenant.py`) for the tenant's host usage; `cli/inspect_evidence.py` for listing modules; `cli/settings_flags.py` for flags; `scripts/demo_evidence.py` for the demo script; `tests/local_host_harness.py` and `tests/process/conftest.py` for in-process tenant tests.
- **Real fixtures** (`tests/fixtures/sq_reviews/`, slice `resident-process-and-recovery`): round 1 part 1 `102-review.tasks.resident-process-and-recovery.part-1.20260921T112529.md`; round 1 part 2 `...part-2.20260921T112635.md`; round 2 part 1 `...part-1.md`; round 2 part 2 `...part-2.md` (the captured provider failure). Files carrying `squadronVersion`: the 105, 106, and 928 fixtures. Never hand-build a review.
- **No load test:** the LLD sets no numeric targets. Task 9.7 tells the PM so it can be overruled.

---

## Section 5: Attribution and Review-Producing Kinds

### Task 5.1: Define the review-producing kinds and the open-entry read
**Owner**: Junior AI
**Dependencies**: Task 4.8
**Effort**: 1
**Objective**: One definition of which journal kinds produce reviews (LLD D5).

**Steps**:
- [ ] Add `REVIEW_PRODUCING_KINDS: frozenset[CommandKind]` to `store/journal_models.py` holding `CommandKind.SQ_RUN` only, with a comment: initiative 120 adds its review command kind here
- [ ] Add `has_unresolved_review_entry(project_id) -> bool` to the journal mixin, built on `unresolved_journal_entries` (no new SQL unless that read cannot serve)

**Success Criteria**:
- [ ] Committed with Task 5.3

**Files to Modify**: `store/journal_models.py`, `store/journal.py`

---

### Task 5.2: Implement `attribute_review`
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 1
**Objective**: The attribution rule (LLD D4), pure, defined once, exported.

**Steps**:
- [ ] Create `src/amoeba/store/attribution.py` with the frozen `Attribution(node_id: str | None, candidates: tuple[str, ...])` and `attribute_review(slice_nodes: Sequence[Node], slice_name: str) -> Attribution`, exactly the LLD D4 signature
- [ ] Match nodes with `kind == NodeKind.SLICE` and `cf.slice_name == slice_name`. The function filters `kind` itself, so a caller may pass all of a project's nodes (`nodes_for_project`). One match → `node_id` set and `candidates` holding that id; zero or several → `node_id` None and `candidates` every match id (empty for zero)
- [ ] No I/O. Export both names from `store/__init__.py`

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 5.3

**Files to Create**: `src/amoeba/store/attribution.py`
**Files to Modify**: `store/__init__.py`

---

### Task 5.3: Test attribution and the kinds set
**Owner**: Junior AI
**Dependencies**: Task 5.2
**Effort**: 2
**Objective**: The LLD's table of cases.

**Steps**:
- [ ] Add `tests/store/test_attribution.py`: one match; zero; two matches (both ids); right name but not a slice node; a slice node with no `cf` reference
- [ ] `has_unresolved_review_entry`: false with no entries; true with an open `SQ_RUN`; false with an open entry of another kind; false after the `SQ_RUN` entry resolves
- [ ] Add the new exports to `tests/test_public_api.py`

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(store): add review attribution and review-producing kinds`

**Files to Create**: `tests/store/test_attribution.py`
**Files to Modify**: `tests/test_public_api.py`

---

## Section 6: Review Sources

### Task 6.1: Implement `ReviewSource` and `DirectoryReviewSource`
**Owner**: Junior AI
**Dependencies**: Task 5.3
**Effort**: 3
**Objective**: The one source interface and its directory implementation with the settle rule and race table (LLD D6, "Settled").

**Steps**:
- [ ] Create `src/amoeba/process/review_sources.py`: frozen `DetectedFile(path, content: bytes, observed_at)`; `ReviewSource` protocol with `poll() -> Sequence[DetectedFile]`; docstring states the S8 swap
- [ ] `DirectoryReviewSource(directory)` keeps the last-scan `(size, mtime_ns)` per path in memory. `poll()` lists regular top-level `*.md` files only. A file is returned only when its signature equals the previous poll's; a first sighting is remembered, not returned
- [ ] Read bytes only for settled files; `content` is the bytes actually read
- [ ] Race table exactly per D6: `FileNotFoundError` on stat or read drops the file and forgets its signature; `PermissionError` logs one WARNING per file until readable; neither raises
- [ ] Add `list_review_files(directory) -> list[Path]` here as the one listing rule (regular, top-level, `*.md`), used by `poll()`, the tenant's baseline (Task 7.3), and the listing (Task 8.1)
- [ ] A directory that cannot be listed raises `ReviewDirectoryUnavailableError` (defined here); never an empty list. No writes, no symlink resolution

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 6.2

**Files to Create**: `src/amoeba/process/review_sources.py`

---

### Task 6.2: Test the review sources
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 3
**Objective**: Pin settling and every race row with real fixtures copied into `tmp_path`.

**Steps**:
- [ ] Add `tests/process/test_review_sources.py`
- [ ] Settle: first poll returns nothing; a second unchanged poll returns the file with its exact bytes; a size or mtime change resets settling
- [ ] Ignored: a subdirectory holding an `.md` (non-recursion), a non-`.md` file, a directory named `x.md`
- [ ] Races: a file removed between polls produces nothing and no error; a patched read raising `FileNotFoundError` drops the file, and when it returns it settles from scratch; a mode-000 file warns once across several polls, then is returned after `chmod` (skip where the runner is root)
- [ ] A removed directory raises `ReviewDirectoryUnavailableError`; restored, polling resumes

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(process): add ReviewSource and DirectoryReviewSource`

**Files to Create**: `tests/process/test_review_sources.py`

---

## Section 7: `ReviewDetectionTenant`

### Task 7.1: Add the settings and the shared version-label helper
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 2
**Objective**: Settings (LLD "Settings") and an `sq --version` capture that reuses cf's.

**Steps**:
- [ ] Add `review_scan_interval_seconds = 2.0` and `sq_timeout_seconds = 10.0` to `ProcessSettings` with docstring entries; add both `start` flags in `cli/settings_flags.py`, with defaults read from `ProcessSettings` only
- [ ] Generalize `capture_version_label` in `process/observers/cf_readback.py`: extract the subprocess logic into a helper parameterized by executable (e.g. `capture_executable_version(executable, timeout_seconds)`), move it with `VERSION_UNAVAILABLE` to a new `process/observers/version_label.py`, and keep `capture_version_label` as the cf call. Define `SQ_EXECUTABLE` and its version args once there. cf behavior and logging are unchanged
- [ ] Update imports of `VERSION_UNAVAILABLE`; existing cf tests pass unchanged

**Success Criteria**:
- [ ] Existing observer, settings, and lifecycle tests pass; `amoeba start --help` lists the two flags
- [ ] Committed with Task 7.2

**Files to Create**: `src/amoeba/process/observers/version_label.py`
**Files to Modify**: `process/settings.py`, `cli/settings_flags.py`, `process/observers/cf_readback.py`

---

### Task 7.2: Test the settings and label helper
**Owner**: Junior AI
**Dependencies**: Task 7.1
**Effort**: 2
**Objective**: Pin defaults, flags, and the sq label path.

**Steps**:
- [ ] Extend the existing settings/flag tests: both defaults come from `ProcessSettings`; a flag overrides each
- [ ] Add `tests/test_version_label.py` following `tests/test_observer_cf_readback.py`'s fake-executable pattern: a fake `sq` on `PATH` gives its trimmed stdout; a missing executable, a non-zero exit, and a timeout each give `VERSION_UNAVAILABLE`

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(process): add detection settings and shared version-label capture`

**Files to Create**: `tests/test_version_label.py`

---

### Task 7.3: Implement the tenant skeleton and baselining
**Owner**: Junior AI
**Dependencies**: Task 7.2
**Effort**: 3
**Objective**: Registration shape, scan cadence, reachability logging, and the all-or-nothing baseline (LLD "Registering a directory").

**Steps**:
- [ ] Create `src/amoeba/process/review_detection.py`: `ReviewDetectionTenant(*, version_label: str, source_factory: Callable[[Path], ReviewSource] = DirectoryReviewSource, clock: Callable[[], float] = time.monotonic)` with `name` and `tick(host) -> bool`, using the host as `InboxTenant` does. Check `InboxTenant`'s constructor for what else it needs (e.g. `supervisor_dir`) and mirror it
- [ ] A tick does nothing until `review_scan_interval_seconds` has passed since the last scan, measured with `clock()` only
- [ ] For each open project, for each **active** watch: if `baselined_at` is null, baseline it; else call a scan method (a stub here, filled in Task 7.5). Sources are kept per watch so settle signatures persist across ticks
- [ ] Baseline: list with `list_review_files` and read every file; a file deleted between list and read is dropped; any other failure (directory unlistable, a file unreadable) writes nothing and retries next scan. On success, one `baseline_watch` call
- [ ] One reachability helper used by baselining and scanning: one ERROR on the good→bad transition, one INFO on recovery, nothing on repeat ticks. An unreadable file during baseline logs one WARNING naming it, on change of reason only
- [ ] Never write into a watched directory

**Success Criteria**:
- [ ] `ruff`, `pyright` clean
- [ ] Committed with Task 7.4

**Files to Create**: `src/amoeba/process/review_detection.py`

---

### Task 7.4: Test baselining
**Owner**: Junior AI
**Dependencies**: Task 7.3
**Effort**: 3
**Objective**: Each baseline case in the LLD, with a fake clock.

**Steps**:
- [ ] Create `tests/process/detection_harness.py` (shared by Tasks 7.4–7.8): seed a project and a slice node with `cf.slice_name` `resident-process-and-recovery`; register a watch through `apply_submission`; copy a named fixture into a `tmp_path` directory; build the tenant with a fake clock and a distinctive label; `run_scans(n)` that advances the clock past the interval before each tick
- [ ] Add `tests/process/test_review_detection_baseline.py`: existing files become `baseline` rows, `baselined_at` is set, no verdict, no change
- [ ] A directory registered before it exists: one ERROR over several ticks, nothing written; created later, one INFO and baselined
- [ ] One unreadable file: no rows, `baselined_at` null, one WARNING; after `chmod`, the whole directory is baselined at once
- [ ] Two ticks inside the interval baseline once (count calls on a substitute `source_factory` or patched listing)
- [ ] An inactive watch is never baselined; a baselined watch is never baselined again

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(process): add ReviewDetectionTenant with baselining`

**Files to Create**: `tests/process/detection_harness.py`, `tests/process/test_review_detection_baseline.py`

---

### Task 7.5: Implement the detection path
**Owner**: Junior AI
**Dependencies**: Task 7.4
**Effort**: 3
**Objective**: Digest, ledger check, parse, attribute, record (LLD "Detecting a review", Errors).

**Steps**:
- [ ] Create `src/amoeba/process/review_scan.py` holding the per-file path, called by the tenant's scan method. The scan method polls the watch's source; `ReviewDirectoryUnavailableError` goes to the reachability helper and the next watch
- [ ] Per `DetectedFile`: `sha256` of `content`; skip if `(project, path, digest)` is in the ledger
- [ ] `parse_review_artifact`; on `SquadronReviewError` only: `record_detection(unparseable, detail=str(error))`, logged at INFO
- [ ] `attribute_review(store.nodes_for_project(project), parsed.slice)`. Zero or several: `record_detection(unattributed, detail=<candidate ids>, record_id=review_record_id(parsed))`. Exactly one: `record_detected_verdict(to_verdict_input(parsed, node_id=..., source_path=str(path), upstream_version=label), DetectionInput(..., outcome=ingested, record_id=review_record_id(parsed)))`. Check how `to_verdict_input` combines a frontmatter stamp with the passed `upstream_version` (105 D4); the file's stamp must win, the start-up label is only the fallback
- [ ] Store errors (LLD Errors): wrap each recording call so any exception is logged with `logger.exception` at ERROR, naming the project and path, then re-raised. No counter, no parked state. Read how `ResidentProcess.run` (`process/host.py`) handles a raising tenant and confirm it stops the process; if it does not, stop and ask the PM
- [ ] `unparseable` and `unattributed` are terminal for that digest; changed bytes make a new digest

**Success Criteria**:
- [ ] `ruff`, `pyright` clean; both modules near 300 lines or less
- [ ] Committed with Task 7.6

**Files to Create**: `src/amoeba/process/review_scan.py`
**Files to Modify**: `src/amoeba/process/review_detection.py`

---

### Task 7.6: Test the detection path
**Owner**: Junior AI
**Dependencies**: Task 7.5
**Effort**: 3
**Objective**: The LLD's functional bullets for ingest, refusal, label, hand edit, restart, and store failure.

**Steps**:
- [ ] Add `tests/process/test_review_detection.py` using `detection_harness.py`
- [ ] Round 1 then round 2 of part 1: each a verdict on the slice node with `source: artifact_frontmatter`, `source_path` the copied file, an `ingested` row, and one `verdict_recorded` plus one `review_detected`
- [ ] The round 2 part 2 file is recorded with standing `provider_failure`
- [ ] Hand edit: add a `resolution: accepted` frontmatter line to a detected file; the next scans add one `ingested` row pointing at the **same** verdict id and no second verdict
- [ ] Restart: a new tenant over the same store re-ingests nothing
- [ ] Refusals: a project with no slice node → `unattributed`, empty candidates, `record_id` set, no node written; two matching nodes → both ids in `detail`; `# not a review` in an `.md` → `unparseable`, not retried until its bytes change
- [ ] Label: a fixture without `squadronVersion` records the tenant's label; one with it keeps its own stamp; with the label `VERSION_UNAVAILABLE`, the recorded version is that marker
- [ ] Hand recovery: `unattributed`, then create the slice node and ingest the file the way `amoeba ingest review` does (`apply_submission` with the `verdict` kind and `verdict_to_payload`); `recorded_since` is true and a second ingest records nothing
- [ ] Store failure: patch `record_detected_verdict` to raise; the tick raises, the ERROR is logged with the path (`caplog`), nothing is written

**Success Criteria**:
- [ ] Tests pass; split into a second module if this one passes ~300 lines
- [ ] Commit, e.g. `feat(process): detect external reviews and record them as verdicts`

**Files to Create**: `tests/process/test_review_detection.py`

---

### Task 7.7: Implement the defer rule (D5)
**Owner**: Junior AI
**Dependencies**: Task 7.6
**Effort**: 2
**Objective**: Detection yields to the Runner for reviews it launches; deferral is visible.

**Steps**:
- [ ] Defer applies to scanning only. An unbaselined watch is still baselined (it writes only silent rows). For a baselined watch, if `has_unresolved_review_entry(project)` is true, skip the project's scan this tick (no `poll()`)
- [ ] Log one WARNING when a project starts deferring and one INFO when it resumes, tracked per project in memory
- [ ] The skip rule needs no code: a `runner_issued` row already makes the ledger check skip the file
- [ ] Comment citing D5 and its five points, naming points 3 and 5 as requirements on 120

**Success Criteria**:
- [ ] Committed with Task 7.8

**Files to Modify**: `src/amoeba/process/review_detection.py`

---

### Task 7.8: Test defer and skip
**Owner**: Junior AI
**Dependencies**: Task 7.7
**Effort**: 2
**Objective**: Pin the LLD's defer and `runner_issued` bullets.

**Steps**:
- [ ] Add `tests/process/test_review_detection_ownership.py` using the harness: with an open `SQ_RUN` entry (`journal_issue`), a settled new file is not processed and the source is not polled; one WARNING over several ticks; after the entry resolves, one INFO and the file is ingested
- [ ] An open `SQ_RUN` entry and a new watch: the baseline is still taken
- [ ] A file pre-marked with `record_detection(outcome=runner_issued)` for its `(path, digest)` is never ingested and emits no change
- [ ] An open entry of a non-review kind does not defer
- [ ] Remaining LLD lifecycle bullets: an already-baselined directory removed → one ERROR, ticks continue; restored → one INFO and a newly copied file is ingested. Reactivation: deactivate, copy a file in, tick (nothing), reactivate, tick past settle: the file is detected and the earlier baseline rows are unchanged

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(process): defer detection while the runner owns a review`

**Files to Create**: `tests/process/test_review_detection_ownership.py`

---

## Section 8: Listings, Demo Script, and Wiring

### Task 8.1: Add `inspect watches` and `inspect detections`
**Owner**: Junior AI
**Dependencies**: Task 7.8
**Effort**: 3
**Objective**: Two registry entries with the LLD's columns and watch states.

**Steps**:
- [ ] Create `src/amoeba/cli/inspect_feed.py` with `watch_rows` and `detection_rows`, registered in `LISTINGS` (project-scoped) like `cli/inspect_evidence.py`
- [ ] `WatchState` `StrEnum` defined once here: `inactive`, `unreachable`, `baseline_pending`, `deferred`, `ok`. One function computes it in the LLD's precedence: inactive first; then `unreachable` (`list_review_files` raises), `baseline_pending`, `deferred` (`has_unresolved_review_entry`), `ok`. Read-only; writes nothing
- [ ] `detections`: the LLD columns; `recorded_since` from the store read; `--outcome` choices from `DetectionOutcome`
- [ ] Update the test that pins the listing set (search `tests/` for `LISTINGS`)

**Success Criteria**:
- [ ] `amoeba inspect --help` lists both; `ruff`, `pyright` clean
- [ ] Committed with Task 8.2

**Files to Create**: `src/amoeba/cli/inspect_feed.py`
**Files to Modify**: `src/amoeba/cli/inspect.py`, the listing-set test

---

### Task 8.2: Test the listings
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 2
**Objective**: Each state and column, staged by writing store rows directly (no tenant).

**Steps**:
- [ ] Add `tests/cli/test_inspect_feed.py`: `watches` shows each of the five states, including `unreachable` winning over `baseline_pending` and `deferred`
- [ ] `detections` lists every outcome, filters with `--outcome`, and `recorded_since` flips true once a verdict with that id exists
- [ ] `--json` has the same columns as the table

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(cli): add inspect watches and detections`

**Files to Create**: `tests/cli/test_inspect_feed.py`

---

### Task 8.3: Write `scripts/demo_detection.py` and test it
**Owner**: Junior AI
**Dependencies**: Task 8.2
**Effort**: 2
**Objective**: The seeding helper the walkthrough and end-to-end tests use (LLD Verification Walkthrough).

**Steps**:
- [ ] Model on `scripts/demo_evidence.py` (takes the instance lock, refuses while a process runs, requires `AMOEBA_STORE_DIR`): seed a slice node with `cf.slice_name` `resident-process-and-recovery` and a `blocked_on_human` node in project `demo`; print both ids on one line, slice node first
- [ ] Add it to the permitted list in `tests/test_writer_guard.py`, with a comment, as 103 and 104 did
- [ ] Add `tests/test_demo_detection.py`: against a scratch store with project `demo`, exit 0, two ids on stdout, and a read-only open shows both nodes; while the lock is held, non-zero exit, empty stdout, store unchanged

**Success Criteria**:
- [ ] Both test modules pass
- [ ] Commit, e.g. `feat(scripts): add demo_detection seeding script`

**Files to Create**: `scripts/demo_detection.py`, `tests/test_demo_detection.py`
**Files to Modify**: `tests/test_writer_guard.py`

---

### Task 8.4: Wire the tenant into `start`
**Owner**: Junior AI
**Dependencies**: Task 8.3
**Effort**: 2
**Objective**: Register the second tenant; capture `sq --version` once, before the loop.

**Steps**:
- [ ] In `cli/lifecycle.py`, extract tenant assembly into `build_tenants(settings, supervisor_dir) -> tuple[Tenant, ...]`. It captures the sq label with the Task 7.1 helper and `settings.sq_timeout_seconds` and builds `ReviewDetectionTenant` with it, after `InboxTenant` (comment: a backlog of submissions, including `watch_reviews`, drains first)
- [ ] Recovery still runs before any tenant ticks

**Success Criteria**:
- [ ] `tests/test_cli_lifecycle.py` passes
- [ ] Committed with Task 8.5

**Files to Modify**: `src/amoeba/cli/lifecycle.py`

---

### Task 8.5: Test the wiring
**Owner**: Junior AI
**Dependencies**: Task 8.4
**Effort**: 3
**Objective**: Label once, no subprocess per tick, and restart through the real CLI.

**Steps**:
- [ ] Add `tests/process/test_review_detection_wiring.py`: `build_tenants` with the label helper patched to count calls → exactly one call, and the label reaches the tenant; with no `sq` on `PATH`, it completes and the label is `VERSION_UNAVAILABLE`
- [ ] No subprocess per tick: with a tenant on a `LocalHost` and `subprocess.run` patched to raise, run several ticks that baseline and ingest files; no call occurs
- [ ] Real CLI restart in `tests/process/test_review_detection_process.py`: read `tests/cli_harness.py` and `tests/test_cli_lifecycle.py` for launching a long-lived `amoeba start`; if no helper exists, add one `start_cli_process(env)` to `tests/cli_harness.py` (the only launcher; Task 9.1 wraps it). Put a fake `sq` first on `PATH`. Sequence: start, create project `demo`, stop, run the demo script, start, register a temp directory, wait for `baselined_at`, copy round 1 part 1 in, wait for its verdict, `kill -9`, start, run past two scan intervals; verdict and detection counts are unchanged
- [ ] Every wait is a condition wait with a timeout

**Success Criteria**:
- [ ] Tests pass three times consecutively
- [ ] Commit, e.g. `feat(cli): register the detection tenant in start`

**Files to Create**: `tests/process/test_review_detection_wiring.py`, `tests/process/test_review_detection_process.py`
**Files to Modify**: `tests/cli_harness.py` (only if the launcher is needed)

---

## Section 9: End-to-End, Docs, Final Validation

### Task 9.1: Build and smoke-test the end-to-end helpers
**Owner**: Junior AI
**Dependencies**: Task 8.5
**Effort**: 3
**Objective**: One tested helper set for the end-to-end tests.

**Steps**:
- [ ] Create `tests/cli/detection_e2e_harness.py` over the launcher from Task 8.5: process start/stop/kill with condition waits; `start_follower(project, after=None)` collecting `amoeba feed --follow` JSON lines in a thread, with `wait_for(predicate, timeout)` (fails showing the lines so far), `last_seq`, `terminate`, `kill`; `seed_demo(env)`; `copy_fixture(name, directory)`; `inspect_json(env, listing, project, *args)`
- [ ] Add `tests/cli/test_detection_e2e_harness.py`, one smoke test per helper. Helpers hold no detection assertions

**Success Criteria**:
- [ ] Smoke tests pass three times consecutively
- [ ] Commit, e.g. `test(cli): add end-to-end helpers for detection`

**Files to Create**: `tests/cli/detection_e2e_harness.py`, `tests/cli/test_detection_e2e_harness.py`

---

### Task 9.2: End-to-end test
**Owner**: Junior AI
**Dependencies**: Task 9.1
**Effort**: 4
**Objective**: LLD Integration Requirements through the real CLI.

**Steps**:
- [ ] Create `tests/cli/test_detection_end_to_end.py`. Test A: create `demo`, stop, seed, start the follower **while the process is stopped**, start the process, submit a `resolution` for the blocked node, pre-place round 1 part 2 in a temp directory, register it, wait for the baseline, copy round 1 part 1 then (after it is detected) round 2 part 1
- [ ] Assert follower content in order: two `node_created`, the blocked node's `node_status_changed`, `node_status_changed` to `runnable`, then per round one `verdict_recorded` and one `review_detected`; no lines for the baseline file. `inspect verdicts --json` shows two verdicts with `source` `artifact_frontmatter` and `source_path` built from the registered directory string (compare named keys only)
- [ ] Test B, self-contained: ingest the two part 1 rounds, `kill -9`, restart, copy round 2 part 2 in. It records standing `provider_failure`; verdicts total three; no verdict id appears twice in `verdict_recorded` lines. Kill the follower, restart it with `--after` its last `seq`; it prints nothing old, then exactly one new change after a further `resolution` or file
- [ ] Both tests: non-empty follower lines, and every `verdict_recorded`/`review_detected` subject id matches a row in `inspect verdicts`/`inspect detections` and conversely

**Success Criteria**:
- [ ] Both pass three times consecutively, and each alone
- [ ] Commit, e.g. `test(cli): add detection end-to-end test`

**Files to Create**: `tests/cli/test_detection_end_to_end.py`

---

### Task 9.3: Write `docs/feed-contract.md`
**Owner**: Junior AI
**Dependencies**: Task 9.2
**Effort**: 3
**Objective**: Enough for initiative 160 to consume the feed without reading code.

**Steps**:
- [ ] Front matter per `file-naming-conventions.md`; structure like `docs/inbox-contract.md`
- [ ] Cover: `Change` shape and the payload table; `amoeba feed` and its line format; `follow()` and `FeedSettings`; the delivery guarantees as the LLD words them (save the cursor after acting); the latency bound; the follower failure table; "the feed says a change happened, the store is the truth"; bounded coverage (no blocked-state, finding, or journal changes); submission outcomes are not a kind and rejections are not on the feed (D8); nothing is deleted; "current state, then follow" before 109 means reading state, then following from 0 and applying idempotently; the trust boundary
- [ ] Take names and values from the code

**Success Criteria**:
- [ ] Committed with Task 9.4

**Files to Create**: `docs/feed-contract.md`

---

### Task 9.4: Test the feed contract against the code
**Owner**: Junior AI
**Dependencies**: Task 9.3
**Effort**: 2
**Objective**: A doc that drifts from the code fails a test.

**Steps**:
- [ ] Add `tests/test_contract_docs.py` with one reusable helper (document path, required terms): for `feed-contract.md`, every `ChangeKind` value, every `Change` field, every `amoeba feed` flag (from the argparse parser), and every `FeedSettings` field appear; every backticked `amoeba.` dotted name resolves via `importlib` and `getattr`

**Success Criteria**:
- [ ] Test passes; deleting one `ChangeKind` from the doc fails it (check once, then restore)
- [ ] Commit, e.g. `docs: add feed contract`

**Files to Create**: `tests/test_contract_docs.py`

---

### Task 9.5: Update the other contracts and `CHANGELOG.md`
**Owner**: Junior AI
**Dependencies**: Task 9.4
**Effort**: 2
**Objective**: Record every contract change (LLD Technical Scope).

**Steps**:
- [ ] `store-contract.md`: schema 6 and the trigger convention; `changes`, `watches`, `detections`, `record_detection` with `DetectionInput`, `recorded_since` (and its overridden-id limit), `baseline_watch` with `BaselineEntry`, `record_detected_verdict`, `attribute_review`, `has_unresolved_review_entry`, `data_version`, `project_store_path`
- [ ] `inbox-contract.md`: the `watch_reviews` kind and payload
- [ ] `process-contract.md`: `ReviewDetectionTenant`, both settings, cadence and settle rule, local-directory posture, the once-at-start label, defer and its logging, the store-error-stops-the-process rule, absolute-as-given paths, the tick budget, parser-drift remedy
- [ ] `evidence-contract.md`: the attribution rule and that **120 must use it**; D5 points 3 and 5 as requirements on 120 (point 3's one-call method is deferred); the label meaning; `unattributed` recovery by hand; the accepted multi-part series limit
- [ ] `CHANGELOG.md` under Unreleased: the feed and detection
- [ ] Extend `tests/test_contract_docs.py` with required-terms lists for these documents

**Success Criteria**:
- [ ] The doc test passes
- [ ] Commit, e.g. `docs: update contracts and changelog for slice 106`

**Files to Modify**: four `docs/*-contract.md` files, `CHANGELOG.md`, `tests/test_contract_docs.py`

---

### Task 9.6: Run the full checks
**Owner**: Junior AI
**Dependencies**: Task 9.5
**Effort**: 1
**Objective**: Final gate.

**Steps**:
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each; fix failures at their cause
- [ ] `wc -l` every new source file; split any well past ~300 lines by concern and rerun

**Success Criteria**:
- [ ] All clean; commit only if a fix was needed

---

### Task 9.7: Run the Verification Walkthrough and report
**Owner**: Junior AI
**Dependencies**: Task 9.6
**Effort**: 2
**Objective**: Compare real output with the LLD walkthrough.

**Steps**:
- [ ] Run walkthrough steps 1–7 in bash against a scratch `AMOEBA_STORE_DIR`. Record each difference (command, expected, actual); do not edit the LLD
- [ ] In the final message to the PM, list: those differences (or "none"); the task-level additions from file 1's Context Summary; that no load test was added

**Success Criteria**:
- [ ] All seven steps run, or the blocked step is named with its reason
- [ ] A defect found here is fixed in its own commit with a test

---

### Task 9.8: Trace the LLD Success Criteria to tests
**Owner**: Junior AI
**Dependencies**: Task 9.7
**Effort**: 2
**Objective**: Every Functional, Technical, and Integration requirement has a passing test that asserts it.

**Steps**:
- [ ] Walk the LLD Success Criteria in order. For each, name the test (from Tasks 1.4–9.4) and run it by name
- [ ] A missing assertion is a defect in the owning task: add it in the named test and list it (requirement, test, owning task) for the PM

**Success Criteria**:
- [ ] Every requirement maps to a passing test; additions are listed for the PM (or "none")
- [ ] Working tree committed on the slice branch; no merge performed
