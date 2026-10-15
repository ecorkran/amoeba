---
docType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
lld: user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md
dependencies: [101, 102, 103, 104, 105]
projectState: Slices 101–105 are merged, and Sections 1–9 (files 1 and 2) are complete — the feed, follower, `watch_reviews`, attribution, the one-transaction ingest and Runner report-back (`record_runner_report`), and `ReviewDetectionTenant` all exist and are tested. This file holds the listings, demo script, `start` wiring, end-to-end tests, docs, and final validation.
dateCreated: 20261007
dateUpdated: 20261014
status: not_started
---

## Context Summary

- Working on the **outbound-change-feed-and-detection-of-external-work** slice (106), continued from `...-1.md` (Sections 1–5) and `...-2.md` (Sections 6–9). Read file 1's Context Summary, branch, reading note, and commit cadence; they apply here unchanged.
- **Sections in this file:** 10 listings, `start` wiring, and the demo seeding script; 11 end-to-end tests (with a shared helper module), docs, final validation.
- **No load test or CI gate:** the LLD sets no numeric targets, the follower reads one integer on a local file, and a tick is bounded to one pass per watch, so no load-test task is included. Task 11.11 tells the PM so it can be overruled.
- **Branch:** still `106-slice.outbound-change-feed-and-detection-of-external-work`. No task here merges.

---

## Section 10: Listings and Wiring

### Task 10.1: Add `inspect watches` and `inspect detections`
**Owner**: Junior AI
**Dependencies**: Task 9.10
**Effort**: 3
**Objective**: Two registry entries (LLD CLI table).

**Steps**:
- [ ] Create `src/amoeba/cli/inspect_feed.py` with `watch_rows` and `detection_rows`; register both in `LISTINGS` (project-scoped, `rows=`). Columns exactly as in the LLD CLI table
- [ ] `watches`: `state` comes from `watch_state` (Task 9.2a); the listing opens the store read-only plus the supervisor directory and writes nothing
- [ ] `detections`: ledger rows with `--outcome` as a `choice_options` entry (choices from `DetectionOutcome` only, defined once), `recorded_since` from the store read, plus parked files as `failed` rows read from the sidecars through the layout module (they have no store row; leave unknown columns empty, not guessed). Use `parked_files` from `detection_layout.py` (Task 9.2a); this task defines no reader
- [ ] The `--outcome` rule for parked rows, stated in the listing's help text: `failed` is a listing state, not a `DetectionOutcome` (LLD Errors), so it is **not** a choice and `--outcome failed` is refused by argparse like any unknown value. Without `--outcome`, parked rows are listed as `failed`. With any `--outcome`, parked rows are excluded, since they have no outcome to match. No second list of choices exists
- [ ] Update the test that pins the listing set to the new set

**Success Criteria**:
- [ ] `amoeba inspect --help` lists `watches` and `detections`; `ruff`, `pyright` clean
- [ ] Committed with Task 10.2

**Files to Create**: `src/amoeba/cli/inspect_feed.py`
**Files to Modify**: `src/amoeba/cli/inspect.py`, the listing-set test

---

### Task 10.2: Test the listings
**Owner**: Junior AI
**Dependencies**: Task 10.1
**Effort**: 3
**Objective**: Listings show the right state in each scenario.

**Steps**:
- [ ] Add `tests/cli/test_inspect_feed.py`: `watches` shows `ok`, `unreachable`, `baseline_pending`, and `failed`; `detections` shows every outcome, filters with `--outcome`, shows parked files as `failed`, and `recorded_since` flips true after a hand ingest. Stage states by writing store rows and sidecars directly, not by running the tenant
- [ ] Parked rows and the filter: with one parked sidecar and one `unattributed` row staged, no `--outcome` lists both (the parked one as `failed`); `--outcome unattributed` lists only the ledger row; `--outcome failed` exits with argparse's usage error and prints no rows
- [ ] `--json` output has the same columns; table and JSON agree

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(cli): add inspect watches and detections`

**Files to Create**: `tests/cli/test_inspect_feed.py`

---

### Task 10.3: Write `scripts/demo_detection.py` and test it
**Owner**: Junior AI
**Dependencies**: Task 10.2
**Effort**: 3
**Objective**: The seeding helper the Verification Walkthrough, Task 10.6, and the end-to-end tests use (LLD), proven by running it. It needs neither the tenant nor `build_tenants`, so it comes before the wiring and lets Tasks 10.4 and 10.5 sit together.

**Steps**:
- [ ] Model it on `scripts/demo_evidence.py`: takes the instance lock, refuses while a process runs, requires `AMOEBA_STORE_DIR`. It seeds a slice node with `cf.slice_name` of `resident-process-and-recovery` and a `blocked_on_human` node in project `demo`, and prints the two ids on one line, space-separated, slice node first
- [ ] Add it to the permitted-scripts list in `tests/test_writer_guard.py` (visibly, with a comment, as 103 and 104 did)
- [ ] Add `tests/test_demo_detection.py`. Run the script as a subprocess against a scratch store directory that already has project `demo` (create it with `amoeba submit create-project` plus a one-shot host as `tests/cli_harness.py` allows): exit 0, stdout is exactly two whitespace-separated ids, and a read-only open shows a slice node with the right `cf.slice_name` and a blocked node
- [ ] Refusal case: hold the instance lock in the test (use the helper `tests/test_instance_lock.py` uses), run the script, assert non-zero exit, empty stdout, and a stderr message naming the running process; assert the store is unchanged

**Success Criteria**:
- [ ] `tests/test_demo_detection.py` and `tests/test_writer_guard.py` pass
- [ ] Commit, e.g. `feat(scripts): add demo_detection seeding script`

**Files to Create**: `scripts/demo_detection.py`, `tests/test_demo_detection.py`
**Files to Modify**: `tests/test_writer_guard.py`

---

### Task 10.4: Wire the tenant into `start` and capture the label once
**Owner**: Junior AI
**Dependencies**: Task 10.3
**Effort**: 2
**Objective**: Register the second tenant; run `sq --version` once, before the loop.

**Steps**:
- [ ] In `cli/lifecycle.py`, extract the tenant assembly from `start` into a function `build_tenants(settings, supervisor_dir)` that returns the tenant tuple. It captures the `sq` label with the shared helper and `settings.sq_timeout_seconds` and passes it to `ReviewDetectionTenant` (leaving `source_factory` and `clock` at their defaults from Task 9.3); `start` calls it **before** building the process. Register the detection tenant after `InboxTenant` (comment: a backlog of submissions, including `watch_reviews`, drains first)
- [ ] Recovery still runs before any tenant ticks (unchanged)

**Success Criteria**:
- [ ] `amoeba start` runs both tenants; `tests/test_cli_lifecycle.py` passes
- [ ] Committed with Task 10.5

**Files to Modify**: `src/amoeba/cli/lifecycle.py`

---

### Task 10.5: Test the wiring in-process
**Owner**: Junior AI
**Dependencies**: Task 10.4
**Effort**: 2
**Objective**: The label is captured once, its failure path yields the marker, and no tick starts a subprocess. The real-CLI restart test is Task 10.6.

`tests/host_harness.py` cannot be used here: it builds its own bootstrap program with one throwaway tenant and does not call `start`. These cases use in-process objects.

**Steps**:
- [ ] Add `tests/process/test_review_detection_wiring.py`
- [ ] `build_tenants` called once with the label helper patched to count calls: exactly one call, and the label reaches the tenant
- [ ] `sq --version` failure path, parametrized over three cases: a fake `sq` first on `PATH` that exits non-zero; no `sq` on `PATH`; a fake `sq` that sleeps past a small `sq_timeout_seconds`. In each, `build_tenants` completes without raising, the label that reaches the tenant is the `VERSION_UNAVAILABLE` marker, and a detected file with no stamp is then recorded with that marker as `upstream_version` (not empty)
- [ ] No subprocess per tick: with a `LocalHost` (`tests/local_host_harness.py`) and a tenant built directly (fake clock), patch `subprocess.run` to raise, run several ticks with files arriving and being ingested; no call occurs

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(cli): register the detection tenant in start`

**Files to Create**: `tests/process/test_review_detection_wiring.py`

---

### Task 10.6: Test restart through the real CLI
**Owner**: Junior AI
**Dependencies**: Task 10.5
**Effort**: 3
**Objective**: Both tenants run in the real `amoeba start`, and a `kill -9` and restart re-ingest nothing.

**Steps**:
- [ ] Read `tests/cli_harness.py` and `tests/test_cli_lifecycle.py` for how they launch `amoeba start`. If neither can run a long-lived `amoeba start` subprocess with a chosen environment and `PATH`, add one `start_cli_process(env)` helper to `tests/cli_harness.py` (returns the `Popen`; the caller stops or kills it). This is the only launcher; Task 11.1's end-to-end helpers wrap it and add none of their own. Put a fake `sq` script (prints a fixed label) first on `PATH` so the test never calls a real `sq`
- [ ] Add `tests/process/test_review_detection_process.py` with one test. The setup sequence, in order, in a fresh scratch `AMOEBA_STORE_DIR`: start the process; `amoeba submit create-project --project demo`; wait until it is applied; stop the process (the demo script refuses while it runs); run `scripts/demo_detection.py` and read the slice node id; start the process again; `amoeba submit watch-reviews` for a temp reviews directory; wait until read-only `inspect watches` shows `baselined_at` set
- [ ] Then copy a real part 1 round 1 fixture in and wait on a condition until read-only `inspect verdicts` lists it on the slice node; `kill -9` the process, start it again, run past two scan intervals, and assert the verdict count and the `inspect detections` row count are unchanged
- [ ] Every wait is a condition wait with a timeout, never a fixed sleep longer than one scan interval

**Success Criteria**:
- [ ] Test passes three times consecutively
- [ ] Commit, e.g. `test(process): restart the detection tenant through the real CLI`

**Files to Create**: `tests/process/test_review_detection_process.py`
**Files to Modify**: `tests/cli_harness.py` (only if the helper is needed)

---

## Section 11: End-to-End, Docs, Final Validation

### Task 11.1: Build and smoke-test the end-to-end helper module
**Owner**: Junior AI
**Dependencies**: Task 10.6
**Effort**: 3
**Objective**: One tested helper set for Tasks 11.2–11.4, so the three end-to-end tests share proven helpers instead of one fragile copy.

**Steps**:
- [ ] Read `tests/cli_harness.py` first. Use the long-lived `amoeba start` launcher Task 10.6 found or added there (`start_cli_process`, or the existing equivalent it named); add no second launcher
- [ ] Create `tests/cli/detection_e2e_harness.py` with: `start_process(env)` (a thin wrapper over that launcher) / `stop_process` / `kill_process` / `wait_running` (condition waits with a timeout, never fixed sleeps longer than one scan interval); `start_follower(project, after=None)` returning an object that collects stdout JSON lines in a thread and exposes `lines`, `wait_for(predicate, timeout)` (on timeout it fails with the lines collected so far), `last_seq`, and `terminate`/`kill`; `build_scenario(env, *, reviews_dir_pre_files=())` that performs Task 10.6's setup sequence from scratch in a fresh scratch store, with the follower added (start, `create-project`, stop, `seed_demo`, start the follower while stopped, start, register the directory, wait for baseline) and returns a handle with the env, ids, follower, and reviews directory, so each end-to-end test builds its own state; `seed_demo(env)` that runs `scripts/demo_detection.py` and returns the two ids; `copy_fixture(name, directory)` from `tests/fixtures/sq_reviews/`; `inspect_json(env, listing, project, *args)` that runs a read-only `amoeba inspect ... --json`
- [ ] Add `tests/cli/test_detection_e2e_harness.py`, one smoke test per helper: process starts and stops; a killed process is detected as not running; the follower collects a known line and `wait_for` fails with the collected lines on timeout (use a short timeout); `copy_fixture` copies bytes exactly; `inspect_json` returns parsed rows
- [ ] The helpers hold no assertions about detection behavior; those stay in the end-to-end tests

**Success Criteria**:
- [ ] Smoke tests pass three times consecutively; `ruff`, `pyright` clean
- [ ] Commit, e.g. `test(cli): add end-to-end helpers for detection tests`

**Files to Create**: `tests/cli/detection_e2e_harness.py`, `tests/cli/test_detection_e2e_harness.py`

---

### Task 11.2: End-to-end test, part A: follow, reply, detect
**Owner**: Junior AI
**Dependencies**: Task 11.1
**Effort**: 3
**Objective**: The real CLI as subprocesses: feed, human reply, registration, detection (LLD Integration Requirements, first half).

**Steps**:
- [ ] Create `tests/cli/test_detection_end_to_end.py` (the name the LLD's step 9 runs) using `detection_e2e_harness.py` (Task 11.1). Sequence: start the process, `create-project`, stop, run the demo script, start `amoeba feed --project demo --follow` **while the process is stopped**, start the process, submit a `resolution` for the blocked node. Put `part-2.20260921T112635` in a temp reviews directory **before** registering it, register the directory, wait for `inspect watches` to show `baselined_at` set, then copy part 1 round 1 and round 2 of the 102 series in (waiting for the first to be detected before copying the second)
- [ ] Baseline end to end: after registration, `inspect detections` lists exactly one `baseline` row for the pre-placed file; no verdict exists for it; the follower printed no `review_detected` or `verdict_recorded` line for it
- [ ] Assert exact content, not just agreement: the follower printed, in order, two `node_created`, the blocked node's `node_status_changed` into the blocked status, then `node_status_changed` from the blocked status to `runnable`, then for each round one `verdict_recorded` and one `review_detected` with outcome `ingested`; read-only `inspect verdicts` lists exactly two verdicts on the slice node; `inspect detections` lists the two `ingested` rows and the one `baseline` row
- [ ] Provenance through the CLI: read-only `inspect verdicts --project demo --json` rows for the two verdicts each have `source` equal to `artifact_frontmatter` and `source_path` equal to the registered reviews directory joined with the copied file's name (paths are as given, with no symlink resolution, so build the expected value from the string that was registered). Compare only the named keys: a row also carries other columns (today `sq_run_id`, `reviewed_sha`, and more), and the test must not pin the whole row shape
- [ ] Guard against a vacuous pass: assert the collected follower lines are non-empty and the verdict count equals two before comparing follower output with `inspect`

**Success Criteria**:
- [ ] Test passes three times consecutively
- [ ] Commit, e.g. `test(cli): add detection end-to-end test, part A`

**Files to Create**: `tests/cli/test_detection_end_to_end.py`

---

### Task 11.3: End-to-end test, part B: crash, restart, provider failure, resume
**Owner**: Junior AI
**Dependencies**: Task 11.2
**Effort**: 3
**Objective**: Survive `kill -9` with nothing recorded twice (LLD Integration Requirements, second half).

**Steps**:
- [ ] Add a second, self-contained test to the same module: build its own scenario with `build_scenario` (nothing carried from part A), copy part 1 round 1 and round 2 in and wait for both to be ingested, then `kill -9` the process, start it again, and copy the part 2 provider-failure file in
- [ ] Assert: after restart no new ledger rows or verdicts appear for the earlier files; the provider failure is recorded with standing `provider_failure`; the final verdict count is exactly three; the follower printed no `verdict_recorded` twice for one verdict id
- [ ] Kill the follower, restart it with `--after` its last printed `seq`: it prints nothing old; then add a further change (a second `resolution` or a new file) and assert exactly that change arrives
- [ ] Final agreement check: every `verdict_recorded` and `review_detected` subject id in the follower's lines matches a row from read-only `inspect verdicts` / `inspect detections`, and the converse (no row without a change line), with both sides non-empty

**Success Criteria**:
- [ ] All three end-to-end tests pass three times consecutively, and each passes when run alone (`pytest -k` on one test)
- [ ] Commit, e.g. `test(cli): add detection end-to-end test, part B`

**Files to Modify**: `tests/cli/test_detection_end_to_end.py`

---

### Task 11.4: End-to-end test, part C: what detection refuses to guess
**Owner**: Junior AI
**Dependencies**: Task 11.3
**Effort**: 3
**Objective**: LLD walkthrough steps 7 and 8 through the real CLI, so they are not covered only by unit tests and a manual run.

**Steps**:
- [ ] Add a third, self-contained test to `tests/cli/test_detection_end_to_end.py`: build its own scenario with `build_scenario` (nothing carried from parts A or B), giving a registered, baselined directory with the slice node seeded
- [ ] Unattributed through the CLI, using only files under `tests/fixtures/sq_reviews/` (never a live file under `project-documents/`, which can move): create a second project `other` that has **no** slice node, register a second temp directory for it, and copy the real part 1 round 1 fixture in. Also copy a `notes.md` containing `# not a review` into the `demo` directory. Assert via read-only `inspect detections --outcome unattributed --project other` and `--outcome unparseable --project demo` that each is listed with the right outcome, the unattributed one has no candidates, and no verdict was added in either project. (The LLD walkthrough's use of the 104 review stays a manual step in Task 11.11)
- [ ] Copy a real part 1 round 1 file, wait for ingest, append a `resolution: accepted` frontmatter line to the copy, `kill -9` the process and restart it. Assert: one new `ingested` ledger row pointing at the **same** verdict id, verdict count unchanged, and the follower (still running, or restarted from its last `seq`) printed that `review_detected` line and no `verdict_recorded`

**Success Criteria**:
- [ ] Passes three times consecutively with parts A and B, and alone
- [ ] Commit, e.g. `test(cli): add detection end-to-end test, part C`

**Files to Modify**: `tests/cli/test_detection_end_to_end.py`

---

### Task 11.5: Write `docs/feed-contract.md`
**Owner**: Junior AI
**Dependencies**: Task 11.4
**Effort**: 3
**Objective**: Enough for initiative 160 to consume the feed without reading code (LLD Integration Requirements).

**Steps**:
- [ ] Front matter per `file-naming-conventions.md`; follow the structure of `docs/inbox-contract.md`
- [ ] Cover: the `Change` shape and `ChangeKind` payload table; `amoeba feed` and its JSON line format; `follow()` signature and `FeedSettings`; the delivery guarantees as the LLD words them (including save-cursor-after-acting, at-least-once); the latency bound sentence; `change_head` with `read_transaction()` and its usage pattern; "the feed says a change happened, the store is the truth"; the D8a note (no submission-outcome kind; rejections are not on the feed); nothing is deleted; the trust boundary note
- [ ] Take values and names from the code, not memory

**Success Criteria**:
- [ ] The document exists with front matter and all the topics above
- [ ] Committed with Task 11.6

**Files to Create**: `docs/feed-contract.md`

---

### Task 11.6: Test the feed contract against the code
**Owner**: Junior AI
**Dependencies**: Task 11.5
**Effort**: 2
**Objective**: A doc that names things the code lacks fails a test.

**Steps**:
- [ ] Add `tests/test_contract_docs.py`. For `docs/feed-contract.md`: every `ChangeKind` value and every `Change` field name appears in the text; every flag of `amoeba feed` (read from the argparse parser) appears; every `FeedSettings` field name appears; every backticked `amoeba.` dotted name in the document resolves with `importlib` plus `getattr`
- [ ] Design the helper so Tasks 11.7–11.9 can call it for other documents with their own required-terms lists

**Success Criteria**:
- [ ] Test passes; temporarily deleting one `ChangeKind` from the doc makes it fail (verify once, then restore)
- [ ] Commit, e.g. `docs: add feed contract`

**Files to Create**: `tests/test_contract_docs.py`

---

### Task 11.7: Update `store-contract.md` and `inbox-contract.md`
**Owner**: Junior AI
**Dependencies**: Task 11.6
**Effort**: 2
**Objective**: Record the store and inbox contract changes.

**Steps**:
- [ ] `store-contract.md`: `read_transaction()` under 101's section, credited to 106, and the `read_only` constructor flag behind it; the feed read API; `watches`, `baseline_watch` and `BaselineEntry`, `detections`, `recorded_since`, `record_detection`, `DetectionInput`, `record_detected_verdict`; `record_runner_report` with its full signature, the three writes it makes in one transaction, its entry and ledger rules (unknown entry, entry resolved by the issuer, entry `adopted` by recovery, existing ledger row with the same or a different verdict id), and that the Runner calls it instead of the three separate methods; `attribute_review`; schema 6; the trigger convention
- [ ] `inbox-contract.md`: the `watch_reviews` kind and payload; the `verdict` payload's optional `source_document`
- [ ] Extend `tests/test_contract_docs.py` with required-terms lists for these two documents (every method, kind, and field named above, including `baseline_watch`, `BaselineEntry`, and `record_runner_report`)

**Success Criteria**:
- [ ] The doc test passes; each document points to `feed-contract.md` where relevant
- [ ] Commit, e.g. `docs: update store and inbox contracts for slice 106`

**Files to Modify**: `docs/store-contract.md`, `docs/inbox-contract.md`, `tests/test_contract_docs.py`

---

### Task 11.8: Update `process-contract.md` and `evidence-contract.md`
**Owner**: Junior AI
**Dependencies**: Task 11.7
**Effort**: 2
**Objective**: Record the process and evidence contract changes, including what initiative 120 must do.

**Steps**:
- [ ] `process-contract.md`: `ReviewDetectionTenant`, the three settings, scan cadence and settle rule, the filesystem-latency posture (watched directories are expected to be local), the once-at-start `sq --version` label, the ownership rule (defer / skip), and these documented caveats: paths are stored absolute and as given with no symlink resolution, so the same directory registered under two spellings is two watches (the second is a no-op for verdicts but adds ledger rows); the tick budget (one pass per active watch, hundreds of new files at once is not a supported case because registration baselines what exists); a parked file or baseline is retried by deleting its attempts sidecar under `{store_dir}/detection/attempts/`; a Squadron upgrade while the process runs is not reflected in the label until restart; the parser-drift remedy (`unparseable` files are re-ingested with `amoeba ingest review` after a parser fix)
- [ ] `evidence-contract.md`: the series definition (node, review type, source document); the attribution rule and that **initiative 120 must use it**; D5 requirements 3 and 5 on 120, with requirement 3 met by calling `record_runner_report`; the label meaning (what the process observed at start-up); the recovery path for `unattributed` files (`inspect detections --outcome unattributed`, then `amoeba ingest review --node ID`, oldest round first); and the `recorded_since` limitation: it matches on the default verdict id (105's `review_record_id`), so a verdict recorded under an overridden id is not seen
- [ ] Extend `tests/test_contract_docs.py` with required-terms lists for these two documents (setting names, tenant name, `attribute_review`, `source_document`, `recorded_since`, `attempts.json`, `unattributed`)

**Success Criteria**:
- [ ] The doc test passes
- [ ] Commit, e.g. `docs: update process and evidence contracts for slice 106`

**Files to Modify**: `docs/process-contract.md`, `docs/evidence-contract.md`, `tests/test_contract_docs.py`

---

### Task 11.9: Update `CHANGELOG.md` and the 103 forward reference
**Owner**: Junior AI
**Dependencies**: Task 11.8
**Effort**: 1
**Objective**: The remaining paper trail.

**Steps**:
- [ ] `CHANGELOG.md`: entries under Unreleased for the feed and for detection, and an explicit line that `source_document` changes 104's contract additively
- [ ] Update the forward reference in `project-documents/user/slices/103-slice.durable-inbox-and-message-queue.md` (the sentence near line 319 naming `applied_seq` as a change source) per D8a so it points at effects; edit only that sentence
- [ ] Extend `tests/test_contract_docs.py`: `CHANGELOG.md` mentions `source_document`

**Success Criteria**:
- [ ] The doc test passes; `git diff` on the 103 slice shows one changed sentence
- [ ] Commit, e.g. `docs: add slice 106 changelog entries`

**Files to Modify**: `CHANGELOG.md`, the 103 slice document, `tests/test_contract_docs.py`

---

### Task 11.10: Rerun the boundaries and run the full checks
**Owner**: Junior AI
**Dependencies**: Task 11.9
**Effort**: 1
**Objective**: Final gate. The import-boundary and single-definition tests already exist (Task 1.6) and have guarded every task since.

**Steps**:
- [ ] Run `tests/test_import_boundaries.py` and confirm all four rules still pass over the finished tree (the `feed/` and `process/` rules now apply to real files)
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each; fix failures at their cause
- [ ] `wc -l` every new source file; any beyond ~300 lines is split by concern and the tests rerun

**Success Criteria**:
- [ ] Suite, `ruff`, and `pyright` clean; no new file past ~300 lines
- [ ] Commit only if a fix was needed, e.g. `refactor: split oversized slice 106 modules`

---

### Task 11.11: Run the Verification Walkthrough
**Owner**: Junior AI
**Dependencies**: Task 11.10
**Effort**: 2
**Objective**: Compare the real output with the LLD walkthrough.

**Steps**:
- [ ] Run walkthrough steps 1–9 from the LLD in bash against a scratch `AMOEBA_STORE_DIR`, using a second terminal or background job for the follower
- [ ] For each step, compare with the stated expectation. Write each difference (command, expected, actual) into a short list in your final message to the PM. Do not edit the LLD. If a step cannot run, say which and why
- [ ] In the same message, list the task-level additions the LLD's API Contracts table does not name (the LLD describes the behavior of some, such as the one-transaction ingest, but not the method or type): the `read_only` constructor flag, `recorded_since`, `DetectionInput`, `BaselineEntry`, `record_detected_verdict`, `baseline_watch`, `watch_state` / `detection_layout.py`, and `ReviewDirectoryUnavailableError`
- [ ] Report the `record_runner_report` signature Task 6.6 settled (the LLD left it to the tasks), that its return type is `VerdictRecord` where the LLD row says `Verdict`, and its `adopted`-entry rule
- [ ] Report the `recorded_since` consequence from Task 5.1: a verdict recorded under an overridden id is not seen, so the row stays false
- [ ] Also report: the LLD file-layout sketch's `attribute_review(nodes, slice_name)` versus its API Contracts form `attribute_review(store, project_id, slice_name)` (Task 6.2 implemented the latter); and that no load test or CI gate was added because the LLD sets no numeric targets, so the PM can overrule

**Success Criteria**:
- [ ] All nine steps run; every difference is reported to the PM (an empty list is stated as such)
- [ ] No commit needed unless the run exposes a defect; a fix is its own commit with a test

---

### Task 11.12: Trace the LLD Functional Requirements to tests, part 1 (feed and ingest)
**Owner**: Junior AI
**Dependencies**: Task 11.11
**Effort**: 2
**Objective**: Confirm that the first eleven LLD Functional Requirements each have a passing test that already asserts them (LLD Success Criteria). This is a verification pass: every assertion named below was written by an earlier task. Part 2 is Task 11.13; Technical and Integration Requirements are Task 11.14.

**Steps**:
- [ ] For each requirement below, open the named tests, find the assertion, and run the tests by name. The list follows the LLD's Success Criteria in order
  - [ ] Every tracked write emits in its transaction; replay reconciles and rebuilds node status: `test_feed_invariant` (including the dropped-trigger cases, Tasks 2.4–2.6 and 5.2a) and `test_feed_triggers`
  - [ ] No tick starts a subprocess; `sq --version` runs once, before the loop (and its failure path): `test_review_detection_wiring` (Task 10.5)
  - [ ] `resolution` produces `node_status_changed` to `runnable`: `test_feed_triggers` (block/resolve) and end-to-end part A
  - [ ] `read_transaction()` atomic against a concurrent commit: `test_read_transaction`, plus `test_snapshot_and_head_ignore_a_commit_between_them` in `test_follower` (Task 7.2)
  - [ ] `--after N`, resume, no gap or repeat, `changes` unchanged by following: `test_follower`, `tests/cli/test_feed.py`, end-to-end part B
  - [ ] `--follow` while the process is stopped, then started: `tests/cli/test_feed.py` and end-to-end part A
  - [ ] Real file recorded as a verdict with `artifact_frontmatter`, `source_path`, `ingested`, and both changes: `test_review_detection` and end-to-end part A (the `--json` provenance assertion, Task 11.2)
  - [ ] Provider failure with standing `provider_failure`: `test_review_detection` and end-to-end part B
  - [ ] Series by `source_document`; verdicts without it keep 104's behavior: `test_finding_changes_source_document` and `test_review_detection`
  - [ ] Hand edit produces no second verdict: `test_review_detection` and end-to-end part C
  - [ ] Unattributed (zero) and two matches, nothing written to a node: `test_attribution`, `test_review_detection_refusals`, end-to-end part C
- [ ] A missing assertion is a defect in the task that owned it, not a gap to fill quietly here. Add it in the named test, and list it (requirement, test, the task that should have written it) for the Task 11.14 report

**Success Criteria**:
- [ ] Each bullet above is confirmed, or fixed and listed; the named tests pass
- [ ] Commit any additions, e.g. `test: close slice 106 functional coverage gaps, part 1`

---

### Task 11.13: Trace the LLD Functional Requirements to tests, part 2 (detection rules and failures)
**Owner**: Junior AI
**Dependencies**: Task 11.12
**Effort**: 2
**Objective**: The same verification pass for the remaining ten LLD Functional Requirements.

**Steps**:
- [ ] For each requirement below, open the named tests, find the assertion, and run the tests by name
  - [ ] Non-review file `unparseable`, not retried until its bytes change: `test_review_detection_refusals` (both halves); end-to-end part C (the listing only)
  - [ ] Files at registration are `baseline`, never ingested: `test_review_detection_baseline` and end-to-end part A
  - [ ] Directory registered before it exists: `unreachable`, baselined on the first scan that can list it: `test_review_detection_baseline`
  - [ ] One unreadable file at registration: no rows, `baseline_pending`, then whole directory at once: `test_review_detection_baseline`
  - [ ] Hand `ingest review` after the slice node exists: `recorded_since` true, second ingest a no-op: `test_review_detection_refusals` (the store read), `test_detections`, `test_inspect_feed` (the listing column)
  - [ ] Defer on open `SQ_RUN`; `runner_issued` skip: `test_review_detection_ownership` (the skip marked through `record_runner_report`, Task 9.8)
  - [ ] Restart re-ingests nothing: `test_review_detection`, `test_review_detection_process` (Task 10.6), end-to-end part B
  - [ ] Removed directory shows `unreachable`, process keeps running, resumes: `test_review_detection_lifecycle` and `test_inspect_feed`
  - [ ] File deleted between listing and read: `test_review_sources` and `test_review_detection_lifecycle`
  - [ ] Store failure bounded; `failed` listed in `inspect detections`; later files still detected; deleting the sidecar retries: `test_review_detection_failure` and `test_inspect_feed`
- [ ] As in Task 11.12: a missing assertion is added in the named test and listed for the Task 11.14 report

**Success Criteria**:
- [ ] Each bullet above is confirmed, or fixed and listed; the named tests pass
- [ ] Commit any additions, e.g. `test: close slice 106 functional coverage gaps, part 2`

---

### Task 11.14: Trace the Technical and Integration Requirements and close out
**Owner**: Junior AI
**Dependencies**: Task 11.13
**Effort**: 2
**Objective**: The remaining LLD Success Criteria have passing tests, and the slice branch is left clean.

**Steps**:
- [ ] Confirm each requirement below is covered by the named test; run those tests by name. Where the named test lacks the assertion, add it there and list it as in Task 11.12
  - **Technical**
  - [ ] Enums and SQL defined once; attribution and review-producing kinds defined once; store imports nothing from upstream, process, or feed: `test_import_boundaries`
  - [ ] Follower opens the store read-only; writer guard passes with the demo script listed: `test_follower` (row counts unchanged), `test_writer_guard`
  - [ ] Real fixtures used, no hand-built reviews: confirm by reading `detection_harness.py` and the end-to-end tests' fixture setup
  - [ ] 5 to 6 upgrade intact: `test_migration_006`
  - [ ] `ruff`, `pyright` strict, full suite, files near 300 lines: Task 11.10 run
  - [ ] The one-transaction Runner report-back (LLD API Contracts, D5 point 3): `test_record_runner_report` (Task 6.7)
  - **Integration**
  - [ ] End to end through the real CLI with follower, `kill -9`, provider failure, agreement and no double recording: `tests/cli/test_detection_end_to_end.py` (parts A–C)
  - [ ] `feed-contract.md` complete: `test_contract_docs`
- [ ] Report to the PM every assertion Tasks 11.12–11.14 had to add (requirement, test, owning task), and any requirement for which no test could be named; an empty list is stated as such

**Success Criteria**:
- [ ] Each bullet above is confirmed or fixed; the suite is green
- [ ] Working tree committed on the slice branch; no merge performed
- [ ] Commit any additions, e.g. `test: close slice 106 requirement coverage gaps`

---
