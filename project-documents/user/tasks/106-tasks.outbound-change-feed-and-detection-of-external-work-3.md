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
- **Sections in this file:** 10 listings and `start` wiring; 11 demo script, end-to-end tests, docs, final validation.
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
- [ ] `watches`: `state` comes from `watch_state` (Task 9.3); the listing opens the store read-only plus the supervisor directory and writes nothing
- [ ] `detections`: ledger rows with `--outcome` as a `choice_options` entry (choices from `DetectionOutcome`, defined once), `recorded_since` from the store read, plus parked files as `failed` rows read from the sidecars through the layout module (they have no store row; leave unknown columns empty, not guessed). Add the pure sidecar-directory reader here if Task 9.9 did not
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
- [ ] In `cli/lifecycle.py::start`, capture the `sq` label with the shared helper and `settings.sq_timeout_seconds` **before** building the process, and pass it to `ReviewDetectionTenant`. Register it after `InboxTenant` (comment: a backlog of submissions, including `watch_reviews`, drains first)
- [ ] Recovery still runs before any tenant ticks (unchanged)

**Success Criteria**:
- [ ] `amoeba start` runs both tenants; `tests/test_cli_lifecycle.py` passes
- [ ] Committed with Task 10.4

**Files to Modify**: `src/amoeba/cli/lifecycle.py`

---

### Task 10.4: Test the wiring
**Owner**: Junior AI
**Dependencies**: Task 10.3
**Effort**: 3
**Objective**: Both tenants run in the real host; no tick starts a subprocess.

**Steps**:
- [ ] Add `tests/process/test_review_detection_process.py` using `start_host` from `tests/host_harness.py`: a registered directory is baselined and a new file is ingested end to end; `kill -9` and restart re-ingest nothing
- [ ] No tick spawns a subprocess: patch `subprocess.run` after start-up (in-process host), run several ticks with files arriving, assert zero calls
- [ ] The label is captured once: patch the helper to count calls; assert one call at start-up regardless of tick count

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(cli): register the detection tenant in start`

**Files to Create**: `tests/process/test_review_detection_process.py`

---

---

## Section 11: End-to-End, Docs, Final Validation

### Task 11.1: Write `scripts/demo_detection.py` and test it
**Owner**: Junior AI
**Dependencies**: Task 10.4
**Effort**: 3
**Objective**: The seeding helper the Verification Walkthrough uses (LLD), proven by running it.

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

### Task 11.2: End-to-end test, part A: follow, reply, detect
**Owner**: Junior AI
**Dependencies**: Task 11.1
**Effort**: 3
**Objective**: The real CLI as subprocesses: feed, human reply, registration, detection (LLD Integration Requirements, first half).

**Steps**:
- [ ] Create `tests/cli/test_detection_end_to_end.py` (the name the LLD's step 9 runs) with shared helpers at the top. Sequence: start the process, `create-project`, stop, run the demo script, start `amoeba feed --project demo --follow` **while the process is stopped**, start the process, submit a `resolution` for the blocked node, register a temp reviews directory, copy part 1 round 1 and round 2 of the 102 series in (waiting for the first to be detected before copying the second)
- [ ] Wait on conditions (process status, expected feed lines read with a timeout), never fixed sleeps longer than one scan interval; on timeout, fail with the lines collected so far
- [ ] Assert exact content, not just agreement: the follower printed, in order, two `node_created`, the blocked node's `node_status_changed` into the blocked status, then `node_status_changed` from the blocked status to `runnable`, then for each round one `verdict_recorded` and one `review_detected` with outcome `ingested`; read-only `inspect verdicts` lists exactly two verdicts on the slice node; `inspect detections` lists the two `ingested` rows
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
- [ ] Extend the same module with a second test (reusing part A's helpers) that continues the sequence: `kill -9` the process, start it again, then copy the part 2 provider-failure file in
- [ ] Assert: after restart no new ledger rows or verdicts appear for the earlier files; the provider failure is recorded with standing `provider_failure`; the final verdict count is exactly three; the follower printed no `verdict_recorded` twice for one verdict id
- [ ] Kill the follower, restart it with `--after` its last printed `seq`: it prints nothing old; then add a further change (a second `resolution` or a new file) and assert exactly that change arrives
- [ ] Final agreement check: every `verdict_recorded` and `review_detected` subject id in the follower's lines matches a row from read-only `inspect verdicts` / `inspect detections`, and the converse (no row without a change line), with both sides non-empty

**Success Criteria**:
- [ ] Both end-to-end tests pass three times consecutively
- [ ] Commit, e.g. `test(cli): add detection end-to-end test, part B`

**Files to Modify**: `tests/cli/test_detection_end_to_end.py`

---

### Task 11.4: Write `docs/feed-contract.md`
**Owner**: Junior AI
**Dependencies**: Task 11.3
**Effort**: 3
**Objective**: Enough for initiative 160 to consume the feed without reading code (LLD Integration Requirements).

**Steps**:
- [ ] Front matter per `file-naming-conventions.md`; follow the structure of `docs/inbox-contract.md`
- [ ] Cover: the `Change` shape and `ChangeKind` payload table; `amoeba feed` and its JSON line format; `follow()` signature and `FeedSettings`; the delivery guarantees as the LLD words them (including save-cursor-after-acting, at-least-once); the latency bound sentence; `change_head` with `read_transaction()` and its usage pattern; "the feed says a change happened, the store is the truth"; the D8a note (no submission-outcome kind; rejections are not on the feed); nothing is deleted; the trust boundary note
- [ ] Take values and names from the code, not memory

**Success Criteria**:
- [ ] The document exists with front matter and all the topics above
- [ ] Committed with Task 11.5

**Files to Create**: `docs/feed-contract.md`

---

### Task 11.5: Test the feed contract against the code
**Owner**: Junior AI
**Dependencies**: Task 11.4
**Effort**: 2
**Objective**: A doc that names things the code lacks fails a test.

**Steps**:
- [ ] Add `tests/test_contract_docs.py`. For `docs/feed-contract.md`: every `ChangeKind` value and every `Change` field name appears in the text; every flag of `amoeba feed` (read from the argparse parser) appears; every `FeedSettings` field name appears; every backticked `amoeba.` dotted name in the document resolves with `importlib` plus `getattr`
- [ ] Design the helper so Task 11.6 can call it for other contracts with their own required-terms lists

**Success Criteria**:
- [ ] Test passes; temporarily deleting one `ChangeKind` from the doc makes it fail (verify once, then restore)
- [ ] Commit, e.g. `docs: add feed contract`

**Files to Create**: `tests/test_contract_docs.py`

---

### Task 11.6: Update the existing contracts and `CHANGELOG.md`
**Owner**: Junior AI
**Dependencies**: Task 11.5
**Effort**: 3
**Objective**: Record every contract change this slice made (LLD Technical Scope, last bullet).

**Steps**:
- [ ] `store-contract.md`: `read_transaction()` under 101's section, credited to 106; the feed read API; `watches`, `detections`, `record_detection`, `record_detected_verdict`; `attribute_review`; schema 6; the trigger convention
- [ ] `inbox-contract.md`: the `watch_reviews` kind and payload; the `verdict` payload's optional `source_document`
- [ ] `process-contract.md`: `ReviewDetectionTenant`, the three settings, scan cadence and settle rule, the filesystem-latency posture (watched directories are expected to be local), the once-at-start `sq --version` label, the ownership rule (defer / skip)
- [ ] `evidence-contract.md`: the series definition (node, review type, source document); the attribution rule and that **initiative 120 must use it**; D5 requirements 3 and 5 on 120; the label meaning (what the process observed at start-up)
- [ ] `CHANGELOG.md`: entries under Unreleased for the feed, detection, and an explicit line that `source_document` changes 104's contract additively
- [ ] Update the forward reference in `103-slice.durable-inbox-and-message-queue.md` (line near 319) per D8a so it points at effects, not `applied_seq`; edit only that sentence
- [ ] Extend `tests/test_contract_docs.py` with one required-terms list per updated contract (the new method, kind, setting, and setting-name strings listed above) and a check that `CHANGELOG.md` mentions `source_document`

**Success Criteria**:
- [ ] The extended doc test passes; each contract points to `feed-contract.md` where relevant
- [ ] Commit, e.g. `docs: update contracts and changelog for slice 106`

**Files to Modify**: the four contracts, `CHANGELOG.md`, `tests/test_contract_docs.py`, `project-documents/user/slices/103-slice.durable-inbox-and-message-queue.md`

---

### Task 11.7: Pin the import boundary and run the full checks
**Owner**: Junior AI
**Dependencies**: Task 11.6
**Effort**: 2
**Objective**: Technical Requirements that a test can hold.

**Steps**:
- [ ] Add `tests/test_import_boundaries.py` (AST-based, like `tests/test_writer_guard.py`): nothing under `src/amoeba/store/` imports `amoeba.upstream`, `amoeba.process`, or `amoeba.feed`; nothing under `src/amoeba/feed/` imports `amoeba.process`
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each; fix failures at their cause
- [ ] `wc -l` every new source file; any beyond ~330 lines is split by concern, with tests rerun

**Success Criteria**:
- [ ] Suite, `ruff`, and `pyright` clean
- [ ] Commit, e.g. `test: pin store and feed import boundaries`

**Files to Create**: `tests/test_import_boundaries.py`

---

### Task 11.8: Run the Verification Walkthrough
**Owner**: Junior AI
**Dependencies**: Task 11.7
**Effort**: 2
**Objective**: Compare the real output with the LLD walkthrough.

**Steps**:
- [ ] Run walkthrough steps 1–9 from the LLD in bash against a scratch `AMOEBA_STORE_DIR`, using a second terminal or background job for the follower
- [ ] For each step, compare with the stated expectation. Write each difference (command, expected, actual) into a short list in your final message to the PM. Do not edit the LLD. If a step cannot run, say which and why

**Success Criteria**:
- [ ] All nine steps run; every difference is reported to the PM (an empty list is stated as such)
- [ ] No commit needed unless the run exposes a defect; a fix is its own commit with a test

---

### Task 11.9: Trace Functional Requirements to tests
**Owner**: Junior AI
**Dependencies**: Task 11.8
**Effort**: 2
**Objective**: Every LLD Functional Requirement has a passing test (LLD Success Criteria).

**Steps**:
- [ ] Confirm each requirement below is covered by the named test; run those tests by name. Where the named test lacks the assertion, add it there
  - Invariant and reconciliation: `test_feed_invariant`
  - No tick starts a subprocess; label captured once: `test_review_detection_process`
  - `resolution` produces `node_status_changed` to `runnable`: `test_feed_triggers` (block/resolve) and the end-to-end test
  - `read_transaction()` atomic against a concurrent commit: `test_read_transaction`
  - `--after N`, resume, no gap or repeat: `test_follower`, `tests/cli/test_feed.py`, end-to-end part B
  - `--follow` while the process is stopped: end-to-end part A
  - Real file, provider failure, series, hand edit, unattributed, non-review, hand ingest and `recorded_since`: `test_review_detection`
  - Baseline, unreachable directory, unreadable file at registration, removed directory: `test_review_detection_baseline`
  - Defer on open `SQ_RUN`, `runner_issued` skip: `test_review_detection` (defer and skip cases)
  - Restart re-ingests nothing: `test_review_detection` and `test_review_detection_process`
  - File deleted between listing and read: `test_review_sources` and `test_review_detection`
  - Store failure bounded: `test_review_detection_failure`
  - 5 → 6 upgrade: `test_migration_006`
- [ ] Report any requirement for which no test could be named, with the one you added

**Success Criteria**:
- [ ] Each bullet above is confirmed or fixed; the suite is green
- [ ] Working tree committed on the slice branch; no merge performed
- [ ] Commit any additions, e.g. `test: close slice 106 requirement coverage gaps`

---
