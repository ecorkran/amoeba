---
docType: tasks
slice: network-api
project: amoeba
lld: user/slices/109-slice.network-api.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108]
projectState: After files 1–2, listings live in `amoeba.inspection` with `as_of_seq`; `amoeba.serve` has settings, bind policy, the error vocabulary, request guards, the reads endpoint, and the submission endpoints, all tested in-process. No feed stream, `amoeba serve` command, load tier, or network contract doc exists yet.
dateCreated: 20261017
dateUpdated: 20261018
status: complete
---

## Context Summary (File 3 of 3)

- Continues `109-tasks.network-api-1.md` and `-2.md`. File 1's Context Summary (verified code facts, branch, commit cadence, tool knowledge, task-level additions) and file 2's event-loop and test rules apply here unchanged.
- **This file:** Sections 7–9: the stream; `amoeba serve` in the CLI; smoke, load, docs, validation.

---

## Section 7: The Stream

### Task 7.1: Add the real-server test harness
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 2
**Objective**: A real uvicorn on an ephemeral loopback port, because `TestClient` does not model a disconnect (LLD Development Approach, step 7).

**Steps**:
- [x] Create `tests/serve_harness.py` with a context manager `running_server(app) -> base_url`: a `uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, …))` run in a background thread, waiting until it has started, reading the bound port from its sockets, and stopping with `should_exit` on exit. Confirm these attributes in the uvicorn docs
- [x] A helper to read SSE events from an `httpx` streaming response (frames split on a blank line; `id`, `event`, `data`, comments) with a per-read timeout
- [x] A smoke test in `tests/serve/test_serve_harness.py`: a listing read through the running server

**Success Criteria**:
- [x] Test passes and leaves no thread running
- [x] Commit, e.g. `test: add real-server harness for serve`

**Notes**: running_server and sse_events were added to the existing tests/serve_harness.py (created in Section 4). uvicorn's timeout_graceful_shutdown is typed int | None, so the harness takes an int grace.

**Files to Create**: `tests/serve_harness.py`, `tests/serve/test_serve_harness.py`

---

### Task 7.2: Add `EventStreamResponse`
**Owner**: Junior AI
**Dependencies**: Task 7.1
**Effort**: 3
**Objective**: SSE framing, heartbeats, and a timeout on every send (LLD D6, Data Flow "The feed", event loop).

**Steps**:
- [x] In `src/amoeba/serve/stream.py`, an ASGI response class constructed with the receive side of a 1-slot anyio memory object stream, the settings, and an `on_close` callback. It sends the 200 `text/event-stream` start, then loops:
  - waits for the next item at most `heartbeat_interval_seconds`
  - a `Change` → `id: <seq>`, `event: change`, `data: <json.dumps(change_record(c))>` frame
  - a timeout → `: keepalive` comment
  - an error item (an `ApiErrorCode` with a detail) → one `event: error` frame with `error_body(...)`, then close
  - every send runs under `anyio.fail_after(send_timeout_seconds)`; `TimeoutError` or `OSError` → close
- [x] `finally`, always: close the receive side, call `on_close` (which sets the stop event and releases the slot)
- [x] Frame building is a pure function
- [x] `tests/serve/test_stream_response.py`, in-process with a fake ASGI `send` (no server): exact bytes for a change, a keepalive, and an error frame; a keepalive after an idle heartbeat interval; an error item closes the response; a `send` that never returns closes it after `send_timeout_seconds`; `on_close` runs once on every exit

**Success Criteria**:
- [x] Tests pass; `pyright` clean
- [x] Commit, e.g. `feat(serve): add EventStreamResponse`

**Notes**: PM decision 20261018: uvicorn 0.54 (h11, httptools absent) advertises ASGI spec 2.3; measured, receive() returns http.disconnect within ~10 ms of a client close while later sends silently succeed. EventStreamResponse therefore runs a disconnect watcher on receive() beside the send loop. Heartbeats and the send timeout stay. LLD D6 corrected (commit 980b37b).

**Files to Create**: `src/amoeba/serve/stream.py`, `tests/serve/test_stream_response.py`

---

### Task 7.3: Add the follow thread
**Owner**: Junior AI
**Dependencies**: Task 7.2
**Effort**: 2
**Objective**: Bridge `follow()` to the event loop through the 1-slot hand-off (LLD D6, State Management).

**Steps**:
- [x] In `stream.py`, a function that starts one `threading.Thread(daemon=True)` running `follow(store_dir, project_id, after=cursor, settings=feed_settings, stop=stop_event.is_set)`; each change sent with `anyio.from_thread.run(send_stream.send, change)`
- [x] `ClosedResourceError`, `BrokenResourceError`, or `RuntimeError` (loop gone) → return. `StorePermissionError` / `StoreSchemaError` from `follow()` → send one error item (Task 7.2), then return. Each `except` carries a comment saying why
- [x] `tests/serve/test_follow_thread.py`, in an anyio event loop with a throwaway store (no server): changes arrive in `seq` order from the cursor; closing the receive side while the thread is blocked in the hand-off makes it exit; setting the stop event while it waits in `follow()` makes it exit within one follow interval; deleting the store yields one error item. Every wait bounded

**Success Criteria**:
- [x] Tests pass; `pyright` clean
- [x] Commit, e.g. `feat(serve): add the follow thread`

**Notes**: anyio 4.15's from_thread.run needs token= from a plain thread (captured with anyio.lowlevel.current_token()); a gone loop raises anyio.RunFinishedError (a RuntimeError subclass). follow() is now typed Generator[Change] so the thread can close it. code_for_exception moved into serve/errors.py, shared with app.py.

**Files to Create**: `tests/serve/test_follow_thread.py`
**Files to Modify**: `src/amoeba/serve/stream.py`

---

### Task 7.4: Add the feed route: cursor, slots, preflight
**Owner**: Junior AI
**Dependencies**: Task 7.3
**Effort**: 2
**Objective**: `GET /v1/projects/{project_id}/feed`, joining Tasks 7.2 and 7.3 (LLD D6, Data Flow "The feed").

**Steps**:
- [x] Cursor: `Last-Event-ID` if present, else `?after=`, else 0; either must be a non-negative integer, else 400 `invalid_cursor`
- [x] Slots: one `anyio.CapacityLimiter(max_streams)` created in `build_app`; acquire without waiting (`acquire_nowait`); `WouldBlock` → 503 `stream_limit_reached` with `Retry-After`
- [x] Preflight on a worker thread: `existing_store_path`, then open read-only and close. Errors map as for reads. Release the slot on any preflight failure
- [x] Start the Task 7.3 thread and return the Task 7.2 response. Register the route in `build_app`

**Success Criteria**:
- [x] `pyright` clean
- [x] Committed with Task 7.5

**Notes**: The route lives in src/amoeba/serve/feed_route.py (stream.py would pass ~300 lines). It is a class-based ASGI endpoint because the response is a raw ASGI callable.

**Files to Modify**: `src/amoeba/serve/stream.py`, `src/amoeba/serve/app.py`

---

### Task 7.5: Test delivery, resume, and errors
**Owner**: Junior AI
**Dependencies**: Task 7.4
**Effort**: 3
**Objective**: Every change after the cursor, once, in order (LLD D6 "Exactly once, in order").

**Steps**:
- [x] `tests/serve/test_stream_delivery.py`, against `running_server` with short intervals in `ServeSettings`/`FeedSettings`:
  - [x] A follower from `after=as_of_seq` receives each new change once, `id` equal to `seq`
  - [x] Disconnect, commit changes while away, reconnect with `Last-Event-ID`: no gap, no repeat. Same with `?after=`. Both given → `Last-Event-ID` wins
  - [x] `after=-1`, `after=x`, `Last-Event-ID: x` → 400 `invalid_cursor`
  - [x] Unknown project → 404 and no `200`; schema mismatch → 503; traversal ids sent as in Task 6.2 (`.`/`..` → 400, `a%2Fb` → 404, no store opened)
  - [x] Delete the store file mid-stream → one `event: error` with `store_unreadable`, then the stream ends
  - [x] An idle stream sends a keepalive within one heartbeat interval

**Success Criteria**:
- [x] Tests pass; full suite green
- [x] Commit (Tasks 7.4–7.5), e.g. `feat(serve): add the SSE feed route`

**Files to Create**: `tests/serve/test_stream_delivery.py`

---

### Task 7.6: Test slot release and the library behaviors
**Owner**: Junior AI
**Dependencies**: Task 7.5
**Effort**: 3
**Objective**: Slots and threads are freed on every exit path, and the two uvicorn behaviors the design depends on are pinned (LLD "Interfaces Required", D6, Mitigation).

**Steps**:
- [x] `tests/serve/test_stream_slots.py`, with `max_streams=2` and short intervals:
  - [x] Two open streams, a third → 503 `stream_limit_reached` with `Retry-After`; a listing read still succeeds
  - [x] Abrupt client close: the slot is free (a new stream opens) within one heartbeat plus one follow interval, and the follow thread has exited (track threads by name)
  - [x] Stalled reader, which also pins behavior 1 (server memory does not grow with the change count): a raw socket client that sends the request and never reads, while many changes are committed. Before the send timeout fires, assert the follow thread is blocked in the hand-off and has handed off at most a bounded number of changes, far fewer than were committed. Then the slot frees within one heartbeat plus `send_timeout_seconds`, and the follow thread has exited
  - [x] Server shutdown with an open stream: the server stops and the thread exits
- [x] Pin behavior 2 (disconnect is noticed on send), with `max_streams=1` and `heartbeat_interval_seconds=30` so no heartbeat falls inside the test: after a clean client close, a new stream request 0.5 s later still gets 503; then commit one change and poll (bounded, e.g. 5 s) until a new stream opens. Put a comment on this test: it pins a uvicorn limitation the heartbeat design relies on, so if it fails because the 503 never comes, uvicorn got better at noticing disconnects. The server has not regressed; revisit the heartbeat rationale in the LLD (D6) instead of forcing the test green
- [x] Bound every wait in these tests; none may hang the suite

**Success Criteria**:
- [x] Tests pass on three consecutive runs
- [x] Commit, e.g. `test(serve): pin stream slot release and send behavior`

**Notes**: Behavior 2 is pinned as measured (disconnect reported on receive(), sends after it succeed), per the PM decision, instead of "a new stream still gets 503". A clean close with a 30 s heartbeat frees the slot well under 2 s. The stalled reader framed about 1700 changes before blocking, far fewer than the 8000 committed, then was dropped within heartbeat + send timeout. Three consecutive runs passed.

**Files to Create**: `tests/serve/test_stream_slots.py`

---

## Section 8: `amoeba serve` in the CLI

### Task 8.1: Add the server runner and the command
**Owner**: Junior AI
**Dependencies**: Task 7.6
**Effort**: 2
**Objective**: A foreground `amoeba serve` with the bind policy, TLS, and a shutdown grace (LLD D3, D7).

**Steps**:
- [x] `src/amoeba/serve/server.py`: `run(settings, token, store_dir)`: `check_bind` first; then `uvicorn.Server(uvicorn.Config(build_app(…), host, port, ssl_certfile, ssl_keyfile, timeout_graceful_shutdown=settings.shutdown_grace_seconds, …)).run()`. Confirm parameter names in the uvicorn docs. Leave uvicorn's access log on
- [x] `src/amoeba/cli/serve.py`: `add_serve_parser` with `--host`, `--port`, `--tls-cert`, `--tls-key` (defaults from `ServeSettings`, following `settings_flags.py`); `run_serve(args)`: read `os.environ.get(TOKEN_ENV_VAR)` once (empty string treated as unset), resolve `paths.store_dir()` once, call `server.run`; catch `ServeRefusedError`, print `amoeba: <message>` to stderr, return `ExitCode.SERVE_REFUSED` (file 1's "Task-level additions"; LLD "Exceptions")
- [x] In `cli/main.py`: add `SERVE_REFUSED = 13` to `ExitCode` with its comment; register the parser and dispatch `"serve"` with lazy imports, so other commands never load uvicorn. A bind failure reaches the existing boundary and exits 1

**Success Criteria**:
- [x] `pyright` clean; Task 5.5's "only `cli/serve.py` imports `amoeba.serve`" test passes
- [x] Committed with Task 8.2

**Notes**: ServeSettings.shutdown_grace_seconds is now an int (default 5): uvicorn's timeout_graceful_shutdown is typed int | None. uvicorn exits a start-up (bind) failure with its own status 3, which collides with amoeba's NOT_RUNNING; server.run catches that SystemExit as ServeStartFailedError and cli/serve.py returns ExitCode.FAILURE (1).

**Files to Create**: `src/amoeba/serve/server.py`, `src/amoeba/cli/serve.py`
**Files to Modify**: `src/amoeba/cli/main.py`

---

### Task 8.2: Test the command
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 2
**Objective**: The `amoeba serve` exit-code matrix, HTTPS, and shutdown (LLD Functional Requirements, refusal bullet).

**Steps**:
- [x] `tests/cli/test_serve.py`, through subprocesses (`cli_harness`), with a scratch store and free ports. Refusal tests use `--host 0.0.0.0` but exit before binding:
  - [x] No token → 13 and `token_required` in stderr; token but no TLS → 13 `tls_required`; a 31-character token → 13 `token_too_short`; missing, unreadable, or mismatched TLS files → 13 `tls_unusable`. The token never appears in stdout or stderr
  - [x] HTTPS on `127.0.0.1` with token and the Task 4.4 cert: 401 without the token, 200 with it (`httpx` with `verify=False`). After stopping it, the token appears nowhere in the server's stdout or stderr (uvicorn's access log goes there)
  - [x] A port already in use → exit 1
  - [x] SIGTERM with a stream open: the process exits within `shutdown_grace_seconds` plus a small margin
  - [x] `amoeba inspect projects` in a fresh interpreter does not import `uvicorn` (check `sys.modules` via `python -c`)

**Success Criteria**:
- [x] Tests pass; full suite green
- [x] Commit, e.g. `feat(cli): add amoeba serve`

**Notes**: On SIGTERM uvicorn shuts down within the grace (measured ~5.4 s with a stream open) and then re-raises the signal, so the process exit status is -SIGTERM, not 0; the tests assert that. The tls_files fixture moved to tests/conftest.py (cert generation in tests/serve_harness.py write_tls_files) so tests/cli can use it.

**Files to Create**: `tests/cli/test_serve.py`

---

## Section 9: Smoke, Load, Docs, Validation

### Task 9.1: Add the end-to-end smoke test
**Owner**: Junior AI
**Dependencies**: Task 8.2
**Effort**: 2
**Objective**: The LLD's Integration Requirement through real processes.

**Steps**:
- [x] `tests/cli/test_serve_smoke.py`, on a scratch store: start `amoeba serve --port <free>` as a subprocess. Over `httpx`, POST `create_project`; start `amoeba start`; wait for the outcome to be `applied`; stop the resident process and seed one node as the walkthrough does (the seeding requires it stopped); start it again. Then read `nodes`, open the feed from `as_of_seq`, POST an intent; the follower receives exactly one `message_posted` change
- [x] Stop the resident process with the follower open: the stream stays open (a keepalive arrives), `nodes` is still served, and a POST gets 202. Start it again. (`kill -9` survival is walkthrough step 5; the restart matrix is slice 110's)
- [x] Clean up both processes in `finally`

**Success Criteria**:
- [x] Test passes
- [x] Commit, e.g. `test: add serve end-to-end smoke test`

**Notes**: The CLI has no heartbeat flag, so the test waits through one default 15 s heartbeat; it stops the resident process right after the intent's change, so that one keepalive proves both "exactly one change" and "the stream stays open". A POST made while stopped is applied and streamed after restart. ~20 s.

**Files to Create**: `tests/cli/test_serve_smoke.py`

---

### Task 9.2: Add the load tier
**Owner**: Junior AI
**Dependencies**: Task 9.1
**Effort**: 3
**Objective**: The three load assertions in the LLD's Technical Requirements, against a real server.

**Steps**:
- [x] `tests/load/test_serve_load.py`, using `running_server` and default `FeedSettings`, `max_streams=32`:
  - [x] 32 concurrent followers; commit a burst of 600 changes, as 600 `post_intent` calls (`tests/feed_harness.py`) through one read-write `Store` in the test process; each follower receives all 600, in `seq` order, none missing
  - [x] Latency: with 32 followers reading, record commit time per change and arrival time per client; p95 ≤ 1 s. Report the measured value with `load_harness.measured`
  - [x] No starvation: 32 idle streams open; `GET /v1/listings/nodes` succeeds (no latency asserted)
- [x] Follow `tests/load/` conventions (`conftest.py`, `load_harness.py`)

**Success Criteria**:
- [x] `uv run pytest tests/load/test_serve_load.py` passes; measured p95 recorded in the task notes
- [x] CI gates it with no workflow change: `.github/workflows/ci.yml`'s `Load tests` step runs `uv run pytest tests/load`, which collects the new file. Confirm the step is still there; if it is missing, stop and tell the PM
- [x] Commit, e.g. `test: add serve load tier`

**Notes**: PM decision 20261018: the 600-change burst commits in ~60 ms, so its commit-to-arrival time measures throughput (drained to 32 followers in ~2.7 s, ~7,000 frames/s for the process with in-process clients); the burst test asserts delivery and order and prints the drain time. Latency is a separate test at a steady 100 commits/s: measured p95 0.234-0.244 s (bound 1 s). Batching the hand-off is the fix if bursts ever need to be faster. CI's Load tests step still runs uv run pytest tests/load. LLD Technical Requirements corrected.

**Files to Create**: `tests/load/test_serve_load.py`

---

### Task 9.3: Write the network contract and deltas
**Owner**: Junior AI
**Dependencies**: Task 9.2
**Effort**: 3
**Objective**: Document the surface (LLD Technical Requirements, last bullet).

**Steps**:
- [x] Read `file-naming-conventions` for frontmatter. Create `docs/network-contract.md`: endpoints and bodies, every `ApiErrorCode` with its status, bind and auth rules (including the proxy note, the random-token requirement and that length cannot detect non-randomness, rotation is a restart), SSE frames, cursor precedence, delivery guarantees (106's bound plus transport, nothing more), `as_of_seq` and "state, then follow", the required submission id, and the dated dependency observations from Task 4.1
- [x] Deltas only: `feed-contract.md` (replace "Current state, then follow"), `inbox-contract.md` (id required over the network), `process-contract.md` (exit 13, `amoeba serve`, D2's tunable-versus-credential note), `store-contract.md` (the two methods). A `CHANGELOG.md` entry in its existing style

**Success Criteria**:
- [x] Every documented name greps in `src/`; every `ApiErrorCode` member is documented
- [x] Commit, e.g. `docs: add network contract and 109 deltas`

**Notes**: docs/network-contract.md added; every ApiErrorCode member is documented, and every documented code name greps in src/ (the only names that do not are external: EventSource, TestClient, httpx2). Deltas in feed-, inbox-, process-, and store-contract.md; CHANGELOG entries under Unreleased.

**Files to Create**: `docs/network-contract.md`
**Files to Modify**: four contract docs, `CHANGELOG.md`

---

### Task 9.4: Run the verification walkthrough and final validation
**Owner**: Junior AI
**Dependencies**: Task 9.3
**Effort**: 3
**Objective**: Confirm the slice against the LLD "Verification Walkthrough" and leave the branch clean for review.

**Steps**:
- [x] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright`, once each, and `uv run pytest tests/load/test_serve_load.py` once
- [x] Run walkthrough steps 1–7 in bash against a scratch store only. If `jq` or `openssl` is missing, stop and tell the PM
- [x] Record the walkthrough output (as 107 and 108 did) and correct the LLD draft wherever reality differs, flagging each correction to the PM
- [x] Clean up as the walkthrough's last paragraph says
- [x] Delegate checklist updates to the `task-checker` agent; set all three task files' `status` to `complete`

**Success Criteria**:
- [x] Suite, load tier, `ruff`, `pyright` clean; every walkthrough step matches, or the difference is reported
- [x] Commit, e.g. `docs: record 109 walkthrough output`

**Notes**: Final: 1802 passed; ruff and pyright clean; load tier 3 passed on ten consecutive runs (paced p95 0.245-0.253 s, burst drain ~2.7 s). Walkthrough steps 1-7 all matched after two script corrections, recorded in the LLD: kill -9 the server pid found with lsof, not uv run's $!; stop the resident process before deleting the store. Running the load tier repeatedly found a real bug, fixed in 7333553: the follow thread closed its hand-off through from_thread.run_sync and could wait forever if the loop stopped as that call was scheduled; on_close now closes it on the loop.

**Files to Modify**: `user/slices/109-slice.network-api.md` (walkthrough note), all three task files
