---
docType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
lld: user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md
dependencies: [101, 102, 103, 104, 105]
projectState: Sections 1–10 (files 1 and 2) are complete — the feed, follower, `watch_reviews`, `ReviewDetectionTenant`, the listings, and `start` wiring all exist and are tested. This file holds the demo script, the end-to-end test, the docs, and the final validation.
dateCreated: 20261007
dateUpdated: 20261007
status: not_started
---

## Context Summary

- Working on the **outbound-change-feed-and-detection-of-external-work** slice (106), continued from `...-1.md` (Sections 1–6) and `...-2.md` (Sections 7–10). Read file 1's Context Summary, branch, reading note, and commit cadence; they apply here unchanged.
- **Section in this file:** 11 demo script, end-to-end test, docs, final validation.
- **Branch:** still `106-slice.outbound-change-feed-and-detection-of-external-work`. No task here merges.

---

## Section 11: End-to-End, Docs, Final Validation

### Task 11.1: Write `scripts/demo_detection.py`
**Owner**: Junior AI
**Dependencies**: Task 10.3
**Effort**: 2
**Objective**: The seeding helper the Verification Walkthrough uses (LLD).

**Steps**:
- [ ] Model it on `scripts/demo_evidence.py`: takes the lock, refuses while the process runs, requires `AMOEBA_STORE_DIR`. It seeds a slice node with `cf.slice_name` of `resident-process-and-recovery` and a `blocked_on_human` node in project `demo`, and prints the two ids on one line, space-separated, slice node first
- [ ] Add it to the permitted-scripts list in `tests/test_writer_guard.py` (visibly, with a comment, as 103 and 104 did)
- [ ] Extend or add a small test that the script refuses while a process runs

**Success Criteria**:
- [ ] `tests/test_writer_guard.py` passes
- [ ] Commit, e.g. `feat(scripts): add demo_detection seeding script`

**Files to Create**: `scripts/demo_detection.py`
**Files to Modify**: `tests/test_writer_guard.py`

---

### Task 11.2: Write the end-to-end CLI test
**Owner**: Junior AI
**Dependencies**: Task 11.1
**Effort**: 4
**Objective**: The LLD Integration Requirement, through the real CLI as subprocesses.

**Steps**:
- [ ] Add `tests/cli/test_detection_end_to_end.py` (the name the LLD's step 9 runs). Sequence: start the process, create a project, stop, seed with the demo script, start again, register a directory, start `amoeba feed --follow`, copy two real review rounds in, `kill -9` the process, start it, copy the provider failure in
- [ ] Assert: the follower output and read-only `inspect` agree; verdicts and ledger rows are not duplicated; the follower saw `node_status_changed` for a `resolution` submission; `--after` resume prints nothing old
- [ ] Reuse `tests/cli_harness.py` and `tests/host_harness.py`; wait on conditions (status, feed lines), never fixed sleeps longer than a scan interval

**Success Criteria**:
- [ ] Test passes three times consecutively
- [ ] Commit, e.g. `test(cli): add detection end-to-end test`

**Files to Create**: `tests/cli/test_detection_end_to_end.py`

---

### Task 11.3: Write `docs/feed-contract.md`
**Owner**: Junior AI
**Dependencies**: Task 11.2
**Effort**: 3
**Objective**: Enough for initiative 160 to consume the feed without reading code (LLD Integration Requirements).

**Steps**:
- [ ] Front matter per `file-naming-conventions.md`; follow the structure of `docs/inbox-contract.md`
- [ ] Cover: the `Change` shape and `ChangeKind` payload table; `amoeba feed` and its JSON line format; `follow()` signature and `FeedSettings`; the delivery guarantees as the LLD words them (including save-cursor-after-acting, at-least-once); the latency bound sentence; `change_head` with `read_transaction()` and its usage pattern; "the feed says a change happened, the store is the truth"; the D8a note (no submission-outcome kind; rejections are not on the feed); nothing is deleted; the trust boundary note
- [ ] Take values and names from the code, not memory; cross-check each against the source

**Success Criteria**:
- [ ] Every name in the document exists in `src/` (spot-check by grep)
- [ ] Commit, e.g. `docs: add feed contract`

**Files to Create**: `docs/feed-contract.md`

---

### Task 11.4: Update the existing contracts and `CHANGELOG.md`
**Owner**: Junior AI
**Dependencies**: Task 11.3
**Effort**: 3
**Objective**: Record every contract change this slice made (LLD Technical Scope, last bullet).

**Steps**:
- [ ] `store-contract.md`: `read_transaction()` under 101's section, credited to 106; the feed read API; `watches`, `detections`, `record_detection`; `attribute_review`; schema 6; the trigger convention
- [ ] `inbox-contract.md`: the `watch_reviews` kind and payload; the `verdict` payload's optional `source_document`
- [ ] `process-contract.md`: `ReviewDetectionTenant`, the three settings, scan cadence and settle rule, the filesystem-latency posture (watched directories are expected to be local), the once-at-start `sq --version` label, the ownership rule (defer / skip)
- [ ] `evidence-contract.md`: the series definition (node, review type, source document); the attribution rule and that **initiative 120 must use it**; D5 requirements 3 and 5 on 120; the label meaning (what the process observed at start-up)
- [ ] `CHANGELOG.md`: entries under Unreleased for the feed, detection, and an explicit line that `source_document` changes 104's contract additively
- [ ] Update the forward reference in `103-slice.durable-inbox-and-message-queue.md` (line near 319) per D8a so it points at effects, not `applied_seq`; edit only that sentence

**Success Criteria**:
- [ ] Each contract states the change with a pointer to `feed-contract.md` where relevant
- [ ] Commit, e.g. `docs: update contracts and changelog for slice 106`

**Files to Modify**: the four contracts, `CHANGELOG.md`, `project-documents/user/slices/103-slice.durable-inbox-and-message-queue.md`

---

### Task 11.5: Final validation
**Owner**: Junior AI
**Dependencies**: Task 11.4
**Effort**: 2
**Objective**: Prove the LLD Success Criteria hold on the branch.

**Steps**:
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each; fix failures at their cause
- [ ] Run the LLD Verification Walkthrough steps 1–9 against a scratch `AMOEBA_STORE_DIR`; compare outputs to what the walkthrough says. Record any difference for the PM instead of editing the LLD
- [ ] Size check with `wc -l`: new source files near 300 lines; split any file well beyond that
- [ ] Confirm the store imports nothing from `amoeba.upstream`, `amoeba.process`, or `amoeba.feed` (grep)
- [ ] Walk the LLD Functional Requirements list and name the test covering each; add a missing test if any has none

**Success Criteria**:
- [ ] Suite, `ruff`, and `pyright` clean; walkthrough output matches or differences are reported
- [ ] Every Functional Requirement maps to a passing test
- [ ] Working tree committed on the slice branch; no merge performed
- [ ] Commit any remaining changes, e.g. `chore: finalize slice 106 validation`

---
