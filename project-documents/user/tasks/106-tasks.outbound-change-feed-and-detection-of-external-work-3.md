---
docType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
lld: user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md
dependencies: [101, 102, 103, 104, 105]
projectState: Sections 1–9 (files 1 and 2) are complete — the feed, follower, `watch_reviews`, attribution, and `ReviewDetectionTenant` all exist and are tested. This file holds the listings, `start` wiring, demo script, end-to-end tests, docs, and final validation.
dateCreated: 20261007
dateUpdated: 20261007
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
- [ ] `detections`: ledger rows with `--outcome` as a `choice_options` entry (choices from `DetectionOutcome`, defined once), `recorded_since` from the store read, plus parked files as `failed` rows read from the sidecars through the layout module (they have no store row; leave unknown columns empty, not guessed). Use `parked_files` from `detection_layout.py` (Task 9.2a); this task defines no reader
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
- [ ] `--json` output has the same columns; table and JSON agree

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(cli): add inspect watches and detections`

**Files to Create**: `tests/cli/test_inspect_feed.py`

---

### Task 10.3: Wire the tenant into `start` and capture the label once
**Owner**: Junior AI
**Dependencies**: Task 10.2
**Effort**: 2
**Objective**: Register the second tenant; run `sq --version` once, before the loop.

**Steps**:
- [ ] In `cli/lifecycle.py`, extract the tenant assembly from `start` into a function `build_tenants(settings, supervisor_dir)` that returns the tenant tuple. It captures the `sq` label with the shared helper and `settings.sq_timeout_seconds` and passes it to `ReviewDetectionTenant`; `start` calls it **before** building the process. Register the detection tenant after `InboxTenant` (comment: a backlog of submissions, including `watch_reviews`, drains first)
- [ ] Recovery still runs before any tenant ticks (unchanged)

**Success Criteria**:
- [ ] `amoeba start` runs both tenants; `tests/test_cli_lifecycle.py` passes
- [ ] Committed with Task 10.4

**Files to Modify**: `src/amoeba/cli/lifecycle.py`

---

### Task 10.3a: Write `scripts/demo_detection.py` and test it
**Owner**: Junior AI
**Dependencies**: Task 10.3
**Effort**: 3
**Objective**: The seeding helper the Verification Walkthrough, Task 10.4, and the end-to-end tests use (LLD), proven by running it. It sits before Task 10.4 because that test seeds nodes with it.

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

### Task 10.4: Test the wiring
**Owner**: Junior AI
**Dependencies**: Task 10.3a
**Effort**: 3
**Objective**: Both tenants run in the real `amoeba start`; no tick starts a subprocess; the label is captured once.

`tests/host_harness.py` cannot be used here: it builds its own bootstrap program with one throwaway tenant and does not call `start`. Use the real CLI for the process test and in-process objects for the patching tests.

**Steps**:
- [ ] Read `tests/cli_harness.py` and `tests/test_cli_lifecycle.py` for how they launch `amoeba start`. If neither can run a long-lived `amoeba start` subprocess with a chosen `PATH`, add a small `start_cli_process` helper to `tests/cli_harness.py`. Put a fake `sq` script (prints a fixed label) first on `PATH` so the test never calls a real `sq`
- [ ] Add `tests/process/test_review_detection_process.py`, CLI-subprocess case: start the process, create a project and seed a slice node (demo script), register a directory, copy a real review in; wait on a condition until it is ingested (read-only `inspect verdicts`); `kill -9`, restart, and assert nothing is re-ingested
- [ ] In-process case: `build_tenants` called once with the helper patched to count calls: exactly one call, and the label reaches the tenant
- [ ] In-process case, `sq --version` failure path: put a fake `sq` that exits non-zero first on `PATH` (and again with none on `PATH`, and again with one that sleeps past a small `sq_timeout_seconds`); `build_tenants` completes without raising, the label that reaches the tenant is the `VERSION_UNAVAILABLE` marker, and a detected file with no stamp is then recorded with that marker as `upstream_version` (not empty)
- [ ] In-process case: with a `LocalHost` (`tests/local_host_harness.py`) and a tenant built directly, patch `subprocess.run` to raise, run several ticks with files arriving and being ingested; no call occurs

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(cli): register the detection tenant in start`

**Files to Create**: `tests/process/test_review_detection_process.py`
**Files to Modify**: `tests/cli_harness.py` (only if the helper is needed)

---

## Section 11: End-to-End, Docs, Final Validation

### Task 11.1: Build and smoke-test the end-to-end helper module
**Owner**: Junior AI
**Dependencies**: Task 10.4
**Effort**: 3
**Objective**: One tested helper set for Tasks 11.2–11.4, so the three end-to-end tests share proven helpers instead of one fragile copy.

**Steps**:
- [ ] Read `tests/cli_harness.py` and the helper `start_cli_process` (Tasks 10.3a/10.4) first; reuse them, do not duplicate
- [ ] Create `tests/cli/detection_e2e_harness.py` with: `start_process(env)` / `stop_process` / `kill_process` / `wait_running` (condition waits with a timeout, never fixed sleeps longer than one scan interval); `start_follower(project, after=None)` returning an object that collects stdout JSON lines in a thread and exposes `lines`, `wait_for(predicate, timeout)` (on timeout it fails with the lines collected so far), `last_seq`, and `terminate`/`kill`; `seed_demo(env)` that runs `scripts/demo_detection.py` and returns the two ids; `copy_fixture(name, directory)` from `tests/fixtures/sq_reviews/`; `inspect_json(env, listing, project, *args)` that runs a read-only `amoeba inspect ... --json`
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
- [ ] Extend the same module with a second test (reusing the Task 11.1 helpers) that continues the sequence: `kill -9` the process, start it again, then copy the part 2 provider-failure file in
- [ ] Assert: after restart no new ledger rows or verdicts appear for the earlier files; the provider failure is recorded with standing `provider_failure`; the final verdict count is exactly three; the follower printed no `verdict_recorded` twice for one verdict id
- [ ] Kill the follower, restart it with `--after` its last printed `seq`: it prints nothing old; then add a further change (a second `resolution` or a new file) and assert exactly that change arrives
- [ ] Final agreement check: every `verdict_recorded` and `review_detected` subject id in the follower's lines matches a row from read-only `inspect verdicts` / `inspect detections`, and the converse (no row without a change line), with both sides non-empty

**Success Criteria**:
- [ ] Both end-to-end tests pass three times consecutively
- [ ] Commit, e.g. `test(cli): add detection end-to-end test, part B`

**Files to Modify**: `tests/cli/test_detection_end_to_end.py`

---

### Task 11.4: End-to-end test, part C: what detection refuses to guess
**Owner**: Junior AI
**Dependencies**: Task 11.3
**Effort**: 3
**Objective**: LLD walkthrough steps 7 and 8 through the real CLI, so they are not covered only by unit tests and a manual run.

**Steps**:
- [ ] Add a third test to `tests/cli/test_detection_end_to_end.py`, reusing the Task 11.1 helpers, starting from a registered, baselined directory with the slice node seeded
- [ ] Unattributed through the CLI, using only files under `tests/fixtures/sq_reviews/` (never a live file under `project-documents/`, which can move): create a second project `other` that has **no** slice node, register a second temp directory for it, and copy the real part 1 round 1 fixture in. Also copy a `notes.md` containing `# not a review` into the `demo` directory. Assert via read-only `inspect detections --outcome unattributed --project other` and `--outcome unparseable --project demo` that each is listed with the right outcome, the unattributed one has no candidates, and no verdict was added in either project. (The LLD walkthrough's use of the 104 review stays a manual step in Task 11.11)
- [ ] Copy a real part 1 round 1 file, wait for ingest, append a `resolution: accepted` frontmatter line to the copy, `kill -9` the process and restart it. Assert: one new `ingested` ledger row pointing at the **same** verdict id, verdict count unchanged, and the follower (still running, or restarted from its last `seq`) printed that `review_detected` line and no `verdict_recorded`

**Success Criteria**:
- [ ] Passes three times consecutively with parts A and B
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
- [ ] `store-contract.md`: `read_transaction()` under 101's section, credited to 106, and the `read_only` constructor flag behind it; the feed read API; `watches`, `detections`, `recorded_since`, `record_detection`, `DetectionInput`, `record_detected_verdict`; `attribute_review`; schema 6; the trigger convention
- [ ] `inbox-contract.md`: the `watch_reviews` kind and payload; the `verdict` payload's optional `source_document`
- [ ] Extend `tests/test_contract_docs.py` with required-terms lists for these two documents (every method, kind, and field named above)

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
- [ ] `evidence-contract.md`: the series definition (node, review type, source document); the attribution rule and that **initiative 120 must use it**; D5 requirements 3 and 5 on 120; the label meaning (what the process observed at start-up); the recovery path for `unattributed` files (`inspect detections --outcome unattributed`, then `amoeba ingest review --node ID`, oldest round first); and the `recorded_since` limitation: it matches on the default verdict id (105's `review_record_id`), so a verdict recorded under an overridden id is not seen
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
- [ ] Also report: the LLD file-layout sketch's `attribute_review(nodes, slice_name)` versus its API Contracts form `attribute_review(store, project_id, slice_name)` (Task 6.2 implemented the latter); and that no load test or CI gate was added because the LLD sets no numeric targets, so the PM can overrule

**Success Criteria**:
- [ ] All nine steps run; every difference is reported to the PM (an empty list is stated as such)
- [ ] No commit needed unless the run exposes a defect; a fix is its own commit with a test

---

### Task 11.12: Trace Functional Requirements to tests
**Owner**: Junior AI
**Dependencies**: Task 11.11
**Effort**: 2
**Objective**: Every LLD Functional Requirement and Technical Requirement has a passing test (LLD Success Criteria).

**Steps**:
- [ ] Confirm each requirement below is covered by the named test; run those tests by name. Where the named test lacks the assertion, add it there. The list follows the LLD's Success Criteria in order
  - **Functional**
  - Every tracked write emits in its transaction; replay reconciles and rebuilds node status: `test_feed_invariant` (including the dropped-trigger cases) and `test_feed_triggers`
  - No tick starts a subprocess; `sq --version` runs once, before the loop (and its failure path): `test_review_detection_process`
  - `resolution` produces `node_status_changed` to `runnable`: `test_feed_triggers` (block/resolve) and end-to-end part A
  - `read_transaction()` atomic against a concurrent commit: `test_read_transaction`, plus the snapshot-then-follow case in `test_follower`
  - `--after N`, resume, no gap or repeat, `changes` unchanged by following: `test_follower`, `tests/cli/test_feed.py`, end-to-end part B
  - `--follow` while the process is stopped, then started: `tests/cli/test_feed.py` and end-to-end part A
  - Real file recorded as a verdict with `artifact_frontmatter`, `source_path`, `ingested`, and both changes: `test_review_detection` and end-to-end part A
  - Provider failure with standing `provider_failure`: `test_review_detection` and end-to-end part B
  - Series by `source_document`; verdicts without it keep 104's behavior: `test_finding_changes_source_document` and `test_review_detection`
  - Hand edit produces no second verdict: `test_review_detection` and end-to-end part C
  - Unattributed (zero) and two matches, nothing written to a node: `test_attribution`, `test_review_detection_refusals`, end-to-end part C
  - Non-review file `unparseable`, not retried until its bytes change: `test_review_detection_refusals`, end-to-end part C
  - Files at registration are `baseline`, never ingested: `test_review_detection_baseline` and end-to-end part A
  - Directory registered before it exists: `unreachable`, baselined on the first scan that can list it: `test_review_detection_baseline`
  - One unreadable file at registration: no rows, `baseline_pending`, then whole directory at once: `test_review_detection_baseline`
  - Hand `ingest review` after the slice node exists: `recorded_since` true, second ingest a no-op: `test_review_detection_refusals`, `test_detections`, `test_inspect_feed`
  - Defer on open `SQ_RUN`; `runner_issued` skip: `test_review_detection_lifecycle` (defer and skip cases)
  - Restart re-ingests nothing: `test_review_detection`, `test_review_detection_process`, end-to-end part B
  - Removed directory shows `unreachable`, process keeps running, resumes: `test_review_detection_lifecycle` and `test_inspect_feed`
  - File deleted between listing and read: `test_review_sources` and `test_review_detection_lifecycle`
  - Store failure bounded; `failed` listed in `inspect detections`; later files still detected; deleting the sidecar retries: `test_review_detection_failure` and `test_inspect_feed`
  - **Technical**
  - Enums and SQL defined once; attribution and review-producing kinds defined once; store imports nothing from upstream, process, or feed: `test_import_boundaries`
  - Follower opens the store read-only; writer guard passes with the demo script listed: `test_follower` (row counts unchanged), `test_writer_guard`
  - Real fixtures used, no hand-built reviews: confirm by reading `detection_harness.py` and the end-to-end tests' fixture setup
  - 5 to 6 upgrade intact: `test_migration_006`
  - `ruff`, `pyright` strict, full suite, files near 300 lines: Task 11.10 run
  - **Integration**
  - End to end through the real CLI with follower, `kill -9`, provider failure, agreement and no double recording: `tests/cli/test_detection_end_to_end.py` (parts A–C)
  - `feed-contract.md` complete: `test_contract_docs`
- [ ] Report any requirement for which no test could be named, with the one you added

**Success Criteria**:
- [ ] Each bullet above is confirmed or fixed; the suite is green
- [ ] Working tree committed on the slice branch; no merge performed
- [ ] Commit any additions, e.g. `test: close slice 106 requirement coverage gaps`

---
