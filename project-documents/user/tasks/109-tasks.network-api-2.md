---
docType: tasks
slice: network-api
project: amoeba
lld: user/slices/109-slice.network-api.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108]
projectState: Continuation of file 1. On entry, Group A is complete (`amoeba.inspection`, `ListingQuery`, `change_as_json` in `amoeba.feed`), and `amoeba.serve` has settings, the error table, the app factory, and listing discovery with supervisor-level listings. There are no project-scoped endpoints, no `inbox.locate`, no submission or feed endpoints, and no real authentication yet.
dateCreated: 20261008
dateUpdated: 20261008
status: not_started
---

## Context Summary

- Continuation file for the **network-api** slice (109). See `109-tasks.network-api-1.md` for the full context summary, branch rule, reading note, PM-ratification note, and commit cadence; they apply here unchanged.
- **This file:** Section 3 continued (project-scoped listing endpoints), Section 4 (`inbox.locate` and submissions), Section 5 (the feed: `feed/page`, the stream worker, SSE, bounds, and the stall verification).
- **Authentication placeholder:** until Section 6, `build_app` takes `NoAuth` (defined in Task 3.5a). Streams call the authenticator's `authorize()` at every heartbeat tick; Task 6.8 supplies the real check and its tests. Do not add token logic in this file.
- **Feed settings:** the LLD's `ServeSettings` has no feed fields. `build_app` stores a default-constructed `FeedSettings` (106; read how 106 constructs it) at `app.state.feed_settings`; every feed endpoint reads it there, and tests replace it before serving (for small intervals). No new flags are added for it. Task 8.5 reports this to the PM.
- **Server harness:** streaming tests need a real server. Task 5.5 adds `tests/serve/server_harness.py`, which runs `uvicorn.Server` for a built app in a thread on an ephemeral port; Task 7.1's `server.run` reuses the same uvicorn settings but not the harness.
- **Next file:** `109-tasks.network-api-3.md` (Sections 6–8).

---

## Section 3 (continued): Project-Scoped Read Endpoints

### Task 3.8: Project listing endpoint
**Owner**: Junior AI
**Dependencies**: Task 3.7
**Effort**: 4
**Objective**: `GET /v1/projects/{project}/listings/{name}?…` with rows and `change_head` from one snapshot (LLD Data Flow "A read", D3, D3a, D5a).

**Steps**:
- [ ] In `serve/reads.py`, add the endpoint: `validate_project_id` (→ `invalid_project_id`), listing exists and is project-scoped (else `unknown_listing`), `query_from_params`, store path via `store_path_for(supervisor_dir, project)`; a project with no store file is `unknown_project`
- [ ] Open with `Store.open_read_only(path, busy_timeout_seconds=settings.store_busy_timeout_seconds)`. Inside `store.read_transaction()` call the listing's rows (through `read_listing` if Task 2.10 added it, else `listing.rows(store, query)`) and `store.change_head(project)`; close the store in a `finally`/context manager
- [ ] If `len(rows) > settings.max_listing_rows`, raise `listing_too_large` (413) with the row count in the message and a hint to narrow (`node=`, `unresolved=true`, `channel=`). Never truncate
- [ ] Respond `200 {"listing", "columns", "rows": encode_rows(rows), "change_head": head}`
- [ ] Map `StoreBusyError` → `503 store_busy`, schema mismatch or unreadable → `503 store_unavailable` through the Task 3.4 table (add entries there if a subclass is missing; do not pick statuses in the endpoint). `VerdictNotFoundError` → `404 not_found`; `VerdictNotComparableError` → `409 not_comparable`
- [ ] Discover projects per request; never cache project ids

**Success Criteria**:
- [ ] Commit with Task 3.9

---

### Task 3.9: Parity and bound tests for project listings
**Owner**: Junior AI
**Dependencies**: Task 3.8
**Effort**: 4
**Objective**: "Same answers as `amoeba inspect`" proven over the whole registry; the bounds behave as stated.

**Steps**:
- [ ] `tests/serve/test_reads_project.py`: iterate **every** project-scoped listing in `LISTINGS` (so later listings are covered) on the store from `seed_all_listings` (Task 1.2). For each, with no options and with each option exercised where the listing has any, assert the response `rows` equal the parsed output of `amoeba inspect <name> --json` run against the same store. Assert `columns` equal too
- [ ] Snapshot test: with `read_transaction` held by a hook between the rows read and the `change_head` read, commit a change from a writer; assert it appears in neither (use the existing harness for a second connection; if the read functions cannot be interleaved, patch `change_head` to commit first and assert the returned head equals the head seen by the rows)
- [ ] `max_listing_rows`: build the app with a tiny limit; a listing over it → `413 listing_too_large` with the count in the body and no `rows` key
- [ ] `StoreBusyError` (patch the open to raise it) → `503 store_busy` with `Retry-After`. A store at an unexpected schema version → `503 store_unavailable` while another project still serves
- [ ] Unknown project → `404 unknown_project`; bad project id → `400 invalid_project_id`; unknown listing → `404 unknown_listing`; `changes` listing with an unknown verdict → `404 not_found`; not comparable → `409 not_comparable`
- [ ] Add `amoeba/serve` to `test_writer_guard.py`'s scanned set (no module permitted a read-write open) and assert endpoints leave the store file bytes and `PRAGMA data_version` unchanged after a read

**Success Criteria**:
- [ ] Tests pass; suite, `ruff`, `pyright` clean
- [ ] Commit, e.g. `feat: serve project-scoped listings` (includes Task 3.8)

---

### Task 3.10: Group B read checkpoint
**Owner**: Junior AI
**Dependencies**: Task 3.9
**Effort**: 1
**Objective**: Reads are complete and committed before writes begin.

**Steps**:
- [ ] Run the full suite, `ruff`, `pyright` once; confirm `git status` is clean

**Success Criteria**:
- [ ] All checks clean; nothing uncommitted

---

## Section 4: `inbox.locate` and Submissions

### Task 4.1: `InboxLocation` and `locate`
**Owner**: Junior AI
**Dependencies**: Task 3.10
**Effort**: 3
**Objective**: Find a submission still in the inbox directory (LLD D4).

**Steps**:
- [ ] Create `inbox/locate.py` and export `locate` and `InboxLocation` from `amoeba.inbox`. `locate(submission_id, store_dir=None) -> InboxLocation | None`. `InboxLocation` carries `state` (`pending`, `quarantined`, `failed`), `path`, and `reason` or `last_error`
- [ ] Scan `new/`, then `quarantine/`, then `failed/` (this order matters; the LLD explains why). Match by the id inside `submission_filename`, using the existing filename helpers from 103, not a new parser. Read only file names and sidecars; open no store
- [ ] Reuse 103's sidecar format and the attempts-sidecar helper (106) to read `reason`/`last_error`; do not redefine either
- [ ] Add an optional between-directories hook parameter (a plain callable, default `None`) so a test can pause the scan between directories. Keep it out of the public docs

**Success Criteria**:
- [ ] Commit with Task 4.2

**Files to Create**: `src/amoeba/inbox/locate.py`

---

### Task 4.2: Tests for `locate`
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 3
**Objective**: Every state, plus the race (LLD D4 and Success Criteria).

**Steps**:
- [ ] `tests/inbox/test_locate.py`: one file each in `new/`, `quarantine/` (with reason sidecar), `failed/` (with last_error); unknown id → `None`; no store opened (assert `locate` works with no store file at all)
- [ ] Race: use the hook to pause between directories and move the file `new/` → `quarantine/`, then separately `new/` → `failed/`; assert `locate` reports the real location, never `None`. Apply-and-delete is covered by the status test (Task 4.5), because it needs the store check

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: add inbox.locate` (includes Task 4.1)

---

### Task 4.3: `POST /submissions`
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 4
**Objective**: Inbox submission over HTTP through `amoeba.inbox.submit()` and nothing else (LLD D4).

**Steps**:
- [ ] Create `serve/writes.py`. Read the body incrementally within `settings.request_body_timeout_seconds` and cap at `settings.max_request_bytes` **while reading**, before parsing: over size → `413 request_too_large`; not complete in time → `408 request_timeout`. The body must be a JSON object, else `422 invalid_submission` with a reason (bad JSON and wrong types are client errors, not 500s)
- [ ] Fields: `kind`, `payload` (omitted means `{}`), `submitted_by`, optional `submission_id`. Call `amoeba.inbox.submit(project_id, kind, payload, submitted_by, submission_id, store_dir)` and nothing else; no per-kind code, no kind list. `validate_project_id` first
- [ ] `InvalidSubmissionError` → `422 invalid_submission` carrying its quarantine `reason`; `SubmissionWriteError` → `503 submission_write_failed` (both via the error table; message states nothing was written)
- [ ] Success: `202 {"submission_id"}`. Do not pre-check that the project has a store (a client that just submitted `create_project` is correct)
- [ ] The `submitted_by` == principal rule is added in Task 6.7; leave a clearly named seam (a function taking the principal or `None`), not a TODO

**Success Criteria**:
- [ ] Commit with Task 4.4

---

### Task 4.4: Tests for `POST /submissions`
**Owner**: Junior AI
**Dependencies**: Task 4.3
**Effort**: 4
**Objective**: Network and CLI submissions are refused for identical reasons and produce identical records.

**Steps**:
- [ ] `tests/serve/test_writes.py`: valid submission → `202`, one file in `new/`; apply it with the 103 apply helper and assert the stored record equals one made by `submit()` with the same fields
- [ ] Invalid payload → `422` and the `reason` equals what `amoeba submit` prints for the same input; assert nothing was written to the inbox. Iterate every `SubmissionKind` once with an invalid payload so new kinds are covered
- [ ] Retry: the same `submission_id` twice → `202` both times and applied once; same id with different content → `202`, first wins (assert the 103 WARNING is logged)
- [ ] `create_project` for a project with no store → `202`; an `intent` into a missing project → `202` (quarantine is reported by status in Task 4.5)
- [ ] Oversized body → `413` with no file written, and the body is not fully held (feed a chunked body larger than the cap and assert reading stops at the cap). Slow body (an async stream that stalls, with a tiny timeout) → `408`. Malformed JSON and a non-object body → `422`
- [ ] `SubmissionWriteError` (patch `submit` to raise) → `503 submission_write_failed`
- [ ] Invalid project id in the path → `400 invalid_project_id` and nothing written
- [ ] Server accepts a submission with no resident process running (no host in the test)

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: add submission endpoint` (includes Task 4.3)

---

### Task 4.5: Submission status endpoint
**Owner**: Junior AI
**Dependencies**: Task 4.4
**Effort**: 3
**Objective**: `GET /v1/projects/{project}/submissions/{id}` reports `applied`, `rejected`, `pending`, `quarantined`, or `failed` (LLD Data Flow "Submission status").

**Steps**:
- [ ] Add `SubmissionState` (`StrEnum`) to `serve/` (once): `applied`/`rejected` reuse the store's outcome enum values by reference, not retyped
- [ ] Up to two passes of: `store.submission(id)` if the store exists (read-only open, as in Task 3.8) → `applied | rejected` (include `applied_seq` when applied and `reason` when rejected); then `inbox.locate(id)` → `pending | quarantined | failed` with `reason`; then `store.submission(id)` again. Nothing found in either pass → `404 unknown_submission`
- [ ] Tests (`tests/serve/test_submission_status.py`): `pending` after submit; `applied` after the apply helper; `rejected` for a rejected record; `quarantined` with reason `no_store_for_project` for an `intent` into a project with no store; `failed` for a parked file; unknown id → `404`; bad project id → `400`

**Success Criteria**:
- [ ] Tests pass; suite, `ruff`, `pyright` clean
- [ ] Commit, e.g. `feat: add submission status endpoint`

---

### Task 4.6: Status races and the resident-process round trip
**Owner**: Junior AI
**Dependencies**: Task 4.5
**Effort**: 3
**Objective**: A lookup that races the process moving a file reports the real state, never `404`; a submission made with the process stopped is applied at next start.

**Steps**:
- [ ] `tests/serve/test_submission_races.py`, using the `locate` hook: pause between directories and (a) move `new/` → `quarantine/`, (b) move `new/` → `failed/`, (c) apply the submission and delete the file. Each lookup reports the real state, never `404`
- [ ] Round trip: submit with the resident process stopped → `pending`; start the host harness → `applied`, and the stored record equals one from `amoeba submit` with the same fields

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `test: pin submission status races and round trip`

---

## Section 5: The Feed

### Task 5.1: `feed/page`
**Owner**: Junior AI
**Dependencies**: Task 4.6
**Effort**: 3
**Objective**: `GET /v1/projects/{project}/feed/page?after=N[&limit=M]`, the non-streaming form (LLD D5).

**Steps**:
- [ ] Set `app.state.feed_settings` in `build_app` as described in the Context Summary. Create `serve/stream.py` (page endpoint first). `after` is required: missing or non-integer → `400 invalid_query` naming `after`. `limit` defaults to `FeedSettings.feed_batch_size` and may not exceed it (over → `400 invalid_query`)
- [ ] Open the store read-only (errors before any body, as in Task 3.8), read one page with 106's changes reader, return `{"changes": [change_as_json(c)…], "next_after"}`. `next_after` is the last `seq`, or `after` when empty
- [ ] Do not reuse the `changes` listing; the two names are unrelated (LLD D5)

**Success Criteria**:
- [ ] Commit with Task 5.2

---

### Task 5.2: Tests for `feed/page`
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 2
**Objective**: The page equals `amoeba feed`.

**Steps**:
- [ ] `tests/serve/test_feed_page.py`: seed changes; the `changes` array equals the parsed output of `amoeba feed --project P` read from 0 (same objects); paging with `next_after` returns every change once, in order; empty page returns `next_after == after`; missing/bad `after` and over-limit `limit` → `400 invalid_query`; unknown project → `404`; bad project id → `400`

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: add feed page endpoint` (includes Task 5.1)

---

### Task 5.3: Stream worker and bounded buffer
**Owner**: Junior AI
**Dependencies**: Task 5.2
**Effort**: 3
**Objective**: One thread per stream running 106's `follow()` into a bounded buffer, with one way to stop it (LLD D5, Mitigation Strategies).

**Steps**:
- [ ] Create `serve/stream_worker.py` (keep `stream.py` near 300 lines). A `StreamWorker` owns: a `threading.Event` stop, a bounded queue sized `settings.stream_buffer_size`, and a thread that runs `follow(store_dir, project, after=N, settings=feed_settings, stop=stop.is_set)` and puts each `Change` in the queue. When the queue is full, wait in short slices that re-check `stop` (never block forever)
- [ ] A single `close()` ends the stream: sets `stop`, releases a thread blocked on a full buffer, and joins within a bound. All end paths (client gone, stall, shutdown) call it
- [ ] A store error raised by `follow()` in the thread is passed through the queue as a terminal marker so the response ends the stream (after streaming has started the status code cannot change; the client reconnects and gets the code then). Log it at ERROR with `logger.exception`
- [ ] Expose a live-thread count for tests (a counter on the worker class), not a global scan of all threads

**Success Criteria**:
- [ ] Commit with Task 5.4

---

### Task 5.4: Tests for the stream worker
**Owner**: Junior AI
**Dependencies**: Task 5.3
**Effort**: 3
**Objective**: Lifecycle and backpressure, without HTTP.

**Steps**:
- [ ] `tests/serve/test_stream_worker.py` against a seeded store: delivers changes in order from `after`; stops within a small `follow_interval_seconds` of `close()`; a worker blocked on a full buffer is released by `close()`; a worker does not read ahead of a full buffer (assert the number of changes taken from the store stays within the buffer bound plus one batch while the consumer is idle); a store error from `follow()` arrives as the terminal marker; live-thread count is zero after every case

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: add stream worker` (includes Task 5.3)

---

### Task 5.5: SSE endpoint, server harness, and shutdown hook
**Owner**: Junior AI
**Dependencies**: Task 5.4
**Effort**: 4
**Objective**: `GET /v1/projects/{project}/feed` as `text/event-stream` (LLD D5, API Contracts), without the cap and stall bounds (Task 5.7).

**Steps**:
- [ ] Cursor: `Last-Event-ID` if present, else `?after=N`; neither → `400 invalid_query` naming both forms. Never default to 0 or to the head
- [ ] Before sending headers: authenticate, validate the project, open the store read-only to prove it opens (so `404`/`503` are real status codes). Headers include `Cache-Control: no-store`. Event format: `id: {seq}\nevent: change\ndata: {change_as_json}\n\n`
- [ ] Nothing to send for `settings.heartbeat_seconds` → send `: keepalive\n\n`. At each heartbeat tick call `authenticator.authorize(principal)`; if it returns a denial code, send one terminal `event: closed` with `data: {"code": …}` and end the stream (a no-op for `NoAuth`; Task 6.8 tests it)
- [ ] Client disconnect ends the stream through `StreamWorker.close()`
- [ ] **Shutdown lives in the app, not in the launcher:** register a Starlette lifespan shutdown handler in `build_app` that sets the stop event of every open stream. Keep a registry of open workers on `app.state` for this
- [ ] Create `tests/serve/server_harness.py`: a context manager that runs `uvicorn.Server` for a given app in a thread on an ephemeral port and stops it by setting `should_exit`, so the lifespan shutdown handler runs. It is the only server launcher the Section 5 tests use

**Success Criteria**:
- [ ] Commit with Task 5.6

---

### Task 5.6: SSE core tests
**Owner**: Junior AI
**Dependencies**: Task 5.5
**Effort**: 4
**Objective**: Ordering, resume, heartbeat, and pre-stream errors. Use the harness with stdlib `http.client`; `TestClient` does not stream incrementally.

**Steps**:
- [ ] `tests/serve/test_stream_sse.py`: each change arrives once, in order, with correct `id:`/`event:`/`data:`. The transcript equals `amoeba feed --project P` read from 0
- [ ] Resume: disconnect mid-stream, reconnect with `Last-Event-ID`; no gap, no repeat. `Last-Event-ID` wins over `?after=`. No cursor → `400`
- [ ] Heartbeat: no changes for `heartbeat_seconds` (small value) → a `: keepalive` comment
- [ ] Errors before streaming: unknown project → `404`, bad project id → `400`, schema mismatch → `503 store_unavailable`, each with no event bytes sent
- [ ] Shutdown: stopping the harness while a stream is open ends the stream and the live-thread count reaches zero

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: add SSE feed endpoint` (includes Task 5.5)

---

### Task 5.7: Stream cap and stall bound
**Owner**: Junior AI
**Dependencies**: Task 5.6
**Effort**: 3
**Objective**: Bound the two ways a remote client can hold a stream slot (LLD D5, D5a).

**Steps**:
- [ ] A limiter of `settings.max_feed_streams` slots, separate from Starlette's thread pool (reads and submissions must still work at the cap). Past the cap: `503 too_many_streams` with `Retry-After`. Acquire after the pre-stream checks; release in a `finally` on every exit path
- [ ] Every send (events and keepalives) must complete within `settings.stream_stall_seconds`, else log at INFO with the principal and last `seq` sent, close the stream through `StreamWorker.close()`, and free the slot
- [ ] Do not wrap the stall bound in any transport workaround; Task 5.8 verifies that it is able to fire

**Success Criteria**:
- [ ] Commit with Task 5.8

---

### Task 5.8: Verify uvicorn's `send` drains (D5 stop-and-ask check)
**Owner**: Junior AI
**Dependencies**: Task 5.7
**Effort**: 3
**Objective**: Establish, not assume, that a never-reading client makes uvicorn's `send` wait (LLD D5 and D5a).

**Steps**:
- [ ] `tests/serve/test_stream_stall.py` using the server harness with a small `stream_stall_seconds`. Open a raw socket with a small `SO_RCVBUF`, send the GET, read nothing. Produce enough changes to fill the socket buffers. Assert (a) the server closes the stream within `stream_stall_seconds` plus a margin, (b) the server's resident memory (read with `ps -o rss= -p <pid>`; run the server as a subprocess for this test so the pid is its own) stays flat while waiting, (c) the slot is freed
- [ ] Then reconnect with `Last-Event-ID` set to the last id received before the stall and assert the stream resumes with no gap and no repeat
- [ ] **If (a) or (b) fails, STOP.** It means `send` returns while uvicorn buffers in memory and no application-level timeout can detect the stall. Do not hand-roll a transport workaround. Tell the PM; the candidate remedy is Hypercorn under the same Starlette app (LLD D5). Record the outcome (pass or fail, uvicorn version) in the task notes for Task 8.2

**Success Criteria**:
- [ ] The test passes, or work has stopped with the PM informed
- [ ] Commit with Task 5.9 only if it passes

---

### Task 5.9: Cap, cleanup, and backpressure tests
**Owner**: Junior AI
**Dependencies**: Task 5.8
**Effort**: 3
**Objective**: The remaining stream Success Criteria.

**Steps**:
- [ ] `tests/serve/test_stream_limits.py`: fill `max_feed_streams` (small) with open streams → the next is `503 too_many_streams` with `Retry-After`, and a listing read still succeeds
- [ ] Fill every slot with non-reading clients; assert the slots free within the stall bound and a new stream is then accepted
- [ ] Thread count: after client disconnect, after stall timeout, and after server shutdown, the live stream-thread count is zero
- [ ] Backpressure: a slow but reading client never hits the stall bound; a non-reading client does not grow server memory and the worker stops reading the store

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: bound stream slots and stalled sends` (includes Tasks 5.7–5.8)

---

### Task 5.10: Checkpoint and latency tests
**Owner**: Junior AI
**Dependencies**: Task 5.9
**Effort**: 3
**Objective**: A blocked stream pins no snapshot; the latency bound holds (LLD D5, Success Criteria). These run in the default suite; the LLD sets no throughput target, so no separate load test or CI gate exists.

**Steps**:
- [ ] Checkpoint test (`tests/serve/test_stream_checkpoint.py`): fill a stream's buffer with a non-reading client, commit from a writer, run `PRAGMA wal_checkpoint(TRUNCATE)` from the writer connection, and assert `busy = 0`. If it fails, `follow()` is holding a read transaction across a `yield`; stop and tell the PM (106 interface). Do not work around it in the server
- [ ] Latency test: with a small `FeedSettings.follow_interval_seconds` set on `app.state.feed_settings`, a change committed while a follower waits is received within that interval plus delivery time, with a generous margin. Do not assert exact timings. If it is flaky, widen the margin and tell the PM; never mark it skipped

**Success Criteria**:
- [ ] Tests pass without flakiness on three consecutive runs; suite clean
- [ ] Commit, e.g. `test: pin stream checkpoint and latency behavior`
