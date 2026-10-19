---
docType: slice-design
slice: network-api
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108]
interfaces: [110]
dateCreated: 20261015
dateUpdated: 20261018
status: complete
---

# Slice Design: network-api

## Overview

`amoeba serve` is a second, separate process that makes the store, the inbox, and the change feed reachable over HTTP. It adds no state and no write path. Reads open project stores read-only and return the same rows `amoeba inspect --json` prints. The only write is a call to 103's `submit()`. The feed is 106's `follow()` served as a Server-Sent Events stream that a client resumes from its last `seq`.

It binds to loopback by default. Any other bind requires a bearer token and TLS, and the server refuses to start without both. When a token is configured, every request must carry it, whatever the bind.

To make "same answers as `amoeba inspect`" structural, this slice moves the listing registry and every listing module out of `amoeba.cli` into a new `amoeba.inspection` package. The CLI and the server then both render that one registry (see the Migration Plan). It also adds the consistent "state, then follow" read that 106 deferred to this slice: every project read reports the feed `seq` it is current as of.

## Value

- **Initiative 160, the notification bridge, Cowork, and a status UI** can read state, submit replies, and receive pushed changes from another machine. They no longer need filesystem access to the supervisor's machine.
- **Remote followers lose nothing.** A disconnect is resumed from the client's last `seq`, with no gap and no repeat, because the stream is a view over 106's durable log and not a buffer of its own.
- **The sole-writer model is unchanged.** The server cannot write except by dropping a file into the inbox, so 102's crash guarantees and 103's delivery semantics cover network submissions without amendment.
- **Slice 110** can prove the contract through the network surface as well as locally.

## Technical Scope

### Included

- `amoeba serve`: a foreground process, like `amoeba start`, with flags for host, port, and the TLS certificate and key.
- `amoeba.serve`: a Starlette application run by uvicorn (D1). It has four groups of endpoints, a bind policy, and token authentication (API Contracts).
- **Reads:** one generic listing endpoint driven by the registry. Every current listing is served, plus 107's and 108's, and every listing added later, with no server edit.
- **Submissions:** `POST` a submission, and `GET` its outcome.
- **Feed:** an SSE stream per project, resumable by `?after=` or `Last-Event-ID`.
- **Migration:** `amoeba.inspection` takes the registry and every listing module (`cli/inspect.py`'s registry and rows, `inspect_inbox.py`, `inspect_evidence.py`, `inspect_feed.py`, 107's `inspect_checks.py`, and 108's `inspect_cf.py`). `argparse.Namespace` is replaced by a typed `ListingRequest`. `discover_project_ids` moves to `amoeba.store`, and `change_line` moves to `amoeba.feed`.
- **Store amendment (106's deferral):** `read_transaction()` and `change_head(project_id)` on the read-only handle.
- `ServeSettings`, a new `ExitCode` member, `docs/network-contract.md`, and deltas to the other contract docs and `CHANGELOG.md`.
- New dependencies: `starlette` and `uvicorn` (runtime), and `httpx2` (dev, for Starlette's test client and the load tests). *PM decision 20261018:* `httpx2` replaces the originally planned `httpx`, because Starlette 1.8's `TestClient` is typed against `httpx2` and warns at runtime when only `httpx` is installed.

### Excluded

- **Per-client identity and authorization scopes.** There is one shared token. `submitted_by` stays free-form provenance, exactly as it is locally. Per-client tokens wait for a second consumer that needs to be told apart (initiative 160 decides).
- **Push of submission outcomes.** Clients poll the outcome endpoint, as local submitters poll `submission(id)` (103). An applied submission already shows up on the feed through the row it lands.
- **Feed pages without streaming.** A client that wants a bounded read opens the stream and disconnects.
- **WebSocket, gRPC, an OpenAPI document, CORS, and rate limiting.** Nothing consumes them yet.
- **A listing catalog** (`GET /v1/listings`). Clients read listings by name. Discovery over HTTP waits for a consumer that asks for it.
- **A body-read timeout and a connection cap.** The size cap bounds a body's memory. A slow body only holds one worker, and the reads' own bounds (D6) are enough until a load test shows otherwise.
- **Managing the server's own lifecycle** (PID file, `amoeba serve --stop`, instance lock). It runs in the foreground, and its launcher stops it (D7).
- **Certificate provisioning.** The operator supplies the certificate and key files.

## Dependencies

### Prerequisites

- **101:** `Store.open_read_only`, the error hierarchy (`StorePermissionError`, `StoreSchemaError`, `StoreBusyError`), and `paths.project_store_path`.
- **102:** the listing registry (`Listing`, `ChoiceOption`, `ValueOption`, `LISTINGS`), the writer guard, `ExitCode`, the one boundary handler in `cli/main.py`, and the `settings_flags` pattern.
- **103:** `inbox.submit()`, `InvalidSubmissionError` with its `reason`, `SubmissionWriteError`, the id rule for project and submission ids, and `Store.submission(id)`.
- **104:** the verdict, finding, and finding-change listings, `VerdictNotFoundError`, and `VerdictNotComparableError`.
- **106:** `follow()`, `FeedSettings`, `Change`, and `data_version()`. 106 deferred `read_transaction()` and `change_head()` to this slice.
- **105, 107, and 108, for ordering only.** 107 and 108 add the listing modules `inspect_checks.py` and `inspect_cf.py`, which this slice moves. If this slice ran first, those modules would be written into `amoeba.cli` and moved immediately. **The first task confirms that 107 and 108 are merged, and stops for the PM if they are not.** At the time of writing (20261015), neither is merged; both designs are `not_started`.

### Interfaces Required

- `submit(project_id=, kind=, payload=, submitted_by=, submission_id=)` returns the id once the file is durable. It works with the resident process stopped.
- `follow(store_dir, project_id, after=, settings=, stop=)` yields changes in `seq` order. It checks `stop` between waits, at most one `follow_interval_seconds` apart. It raises `StorePermissionError` for an unknown or vanished store, and `StoreSchemaError` for a version mismatch.
- The listing row functions, unchanged in what they return. Only their parameter type changes.
- **External:** `starlette` and `uvicorn`, pinned with `>=` like the existing dependencies. *Observed 20261015 on PyPI:* starlette 1.8.0, uvicorn 0.54.0, httpx 0.28.1. *Resolved 20261018:* starlette 1.8.0, uvicorn 0.54.0, anyio 4.15.1, httpx2 2.13.1. These are dated observations, not requirements. The design depends on two behaviors, and a test pins each:
  - uvicorn's `send` waits while the socket's write buffer is full, so a stalled peer blocks the send rather than growing memory. This is why each send has a timeout (D6).
  - ~~Under ASGI spec 2.4, a client disconnect is noticed only when a send fails.~~ *Corrected in Phase 6 (measured 20261018, PM decision):* uvicorn 0.54 (h11; httptools not installed) advertises ASGI spec 2.3. After a client closes, `receive()` returns `http.disconnect` within milliseconds, and every later send silently succeeds. The stream therefore watches `receive()` for the disconnect (D6), and a test pins this behavior.

## Architecture

### Component Structure

```
src/amoeba/inspection/                 moved from amoeba.cli (Migration Plan)
  __init__.py      Listing, ListingScope, options, ListingRequest, LISTINGS, LISTINGS_BY_NAME, read_listing()
  core.py          projects, nodes, blocked, journal rows
  inbox.py         submissions, messages, inbox rows          (was cli/inspect_inbox.py)
  evidence.py      verdicts, findings, changes rows           (was cli/inspect_evidence.py)
  feed.py          watches, detections rows                   (was cli/inspect_feed.py)
  checks.py        checks, calibration rows                   (was 107's cli/inspect_checks.py)
  cf.py            cf-links, cf-snapshots rows                (was 108's cli/inspect_cf.py)
src/amoeba/store/
  discovery.py     discover_project_ids                       (moved from process/supervisor.py)
  feed.py          + read_transaction(), change_head()
src/amoeba/feed/
  wire.py          change_record(Change) -> dict              (was cli/feed.change_line's body)
src/amoeba/serve/
  settings.py      ServeSettings; TOKEN_ENV_VAR; MIN_TOKEN_LENGTH
  policy.py        is_loopback(host); check_bind(settings, token) -> raises ServeRefusedError
  errors.py        ApiErrorCode (closed enum); exception -> (status, code) table; error_response()
  auth.py          BearerTokenMiddleware (constant-time compare)
  reads.py         GET /v1/listings/{name}
  submissions.py   POST and GET /v1/projects/{project_id}/submissions[/{id}]
  stream.py        GET /v1/projects/{project_id}/feed: follow bridge, EventStreamResponse (SSE framing, heartbeats, send timeout), stream slots
  app.py           build_app(settings, token) -> Starlette
  server.py        run(settings, token): uvicorn.Server with the TLS files and shutdown grace
src/amoeba/cli/
  inspect.py       argparse building and table printing only, over amoeba.inspection
  serve.py         add_serve_parser, run_serve
  feed.py          prints wire.change_record as JSON lines
docs/network-contract.md
```

**Layering rules.** These extend `test_import_boundaries.py`, and each is an AST test:

- `amoeba.inspection` imports nothing from `amoeba.cli`, `amoeba.serve`, or `amoeba.process`.
- `amoeba.serve` imports nothing from `amoeba.cli` or `amoeba.process`. It is not the resident process, and it must not be able to reach its host, tenants, or `project_stores`.
- `amoeba.cli.serve` is the only module that imports `amoeba.serve`, so the CLI's other commands never load uvicorn.

The writer guard (`test_writer_guard.py`) already scans all of `src/amoeba/`. Nothing in `inspection` or `serve` is added to its allow-list. A new test also asserts that `amoeba.serve` calls no inbox function other than `submit`.

### Data Flow

**A read:**

```
GET /v1/listings/verdicts?project=demo&node=N         Authorization: Bearer … (when configured)
  auth middleware → reads.py
  validate the project id (103's id rule) → 400 invalid_project_id
  build a ListingRequest from the query string against the listing's declared options → 400 on unknown/missing/invalid
  worker thread (anyio.to_thread, default limiter):
    Store.open_read_only(project_store_path(store_dir, project))   absent file → 404 unknown_project
    with store.read_transaction():                                  one snapshot
        rows = listing.rows(store, request)                         the same function `amoeba inspect` calls
        as_of_seq = store.change_head(project)
  200 {"listing": "verdicts", "project_id": "demo", "as_of_seq": 41, "rows": [...]}
```

Supervisor-level listings (`projects`, `inbox`) open no store, take no `project`, and carry no `as_of_seq`.

**A submission:**

```
POST /v1/projects/demo/submissions  {"kind": "intent", "submission_id": "…", "submitted_by": "bridge", "payload": {...}}
  content-type not application/json → 415; Content-Length over max_request_bytes → 413 before reading
  body read chunk by chunk; reading stops at the first chunk that passes max_request_bytes and returns 413, with or without Content-Length
  worker thread: inbox.submit(project_id=…, kind=…, payload=…, submitted_by=…, submission_id=…)
    InvalidSubmissionError → 422 {"error": "invalid_submission", "reason": <QuarantineReason>, "detail": …}
    SubmissionWriteError   → 503 submission_write_failed      (nothing left in the inbox, per 103)
  202 {"submission_id": "…"}
  retry after a 503 or a lost 202: POST again with the same id; 103's first-wins rule makes it safe
GET /v1/projects/demo/submissions/{id}
  record = store.submission(id)  → 200 record, or 404 not_applied (also for a store that does not exist yet)
```

**The feed:**

```
GET /v1/projects/demo/feed?after=40        (Last-Event-ID: 40 on reconnect)
  cursor = Last-Event-ID if present, else after, else 0
  acquire a stream slot (non-blocking) → 503 stream_limit_reached, Retry-After
  preflight: open read-only and close → 404 unknown_project, 503 store_schema_mismatch     (before any byte is sent)
  200 text/event-stream; one dedicated thread per stream:
    for change in follow(store_dir, project, after=cursor, stop=stop_event.is_set):
        anyio.from_thread.run(send_channel.send, change)    # 1-slot memory object stream; blocks until the loop takes it
        ClosedResourceError / BrokenResourceError / RuntimeError (loop gone) → return
  event loop, per stream (EventStreamResponse, D6):
    wait for the next change, at most heartbeat_interval_seconds
      change  → "id: <seq>\nevent: change\ndata: <change_record JSON>\n\n"
      timeout → ": keepalive\n\n"       (keeps intermediaries from idling the connection out)
    beside the send loop: receive() → http.disconnect ends the stream at once
      follow raised → "event: error\ndata: {"error": …, "detail": …}\n\n", then close
    every send runs under anyio.fail_after(send_timeout_seconds); timeout or OSError → close
  finally (disconnect, send timeout, cancellation, shutdown): set stop_event, close both sides of the hand-off on the loop, release the slot
    a thread blocked in send wakes at once with ClosedResourceError; one waiting inside follow() exits within one follow interval
    the thread never closes the hand-off itself (Phase 6 fix: a close from the thread waits on the loop, which may never run it at shutdown)
```

### State Management

The server holds no durable state and no cursor. Its only in-memory state is per stream (a thread, a stop event, a 1-slot anyio memory object stream) and one stream-slot counter (an `anyio.CapacityLimiter`). The two thread boundaries are each published through one mechanism:

- changes from the follow thread go to the event loop through the memory object stream, sent with `anyio.from_thread.run`;
- stop requests go from the loop to the thread through a `threading.Event`, and closing the receive side wakes a thread blocked in a send.

No other state is shared. Each request opens its own read-only store and closes it, so no SQLite connection crosses threads.

## Technical Decisions

### Technology Choices

**D1 — HTTP with JSON, SSE for the feed, on Starlette and uvicorn.**

- *SSE, not WebSocket.* The feed is one-way. SSE's `id:` field and `Last-Event-ID` reconnect header are exactly 106's cursor rule, so resuming needs no protocol of Amoeba's own, and any HTTP client (`curl -N`, a browser `EventSource`) can follow.
- *Starlette and uvicorn, not the standard library's `http.server`.* `http.server`'s own documentation says it is not for production use and implements only basic security checks. That is disqualifying for a network-facing surface.
- *Not FastAPI.* Its additions (OpenAPI, dependency injection, pydantic request binding) have no consumer here. Request bodies are already validated by 103's envelope, and that check must not run twice in different places.
- *Not a synchronous WSGI server.* Each long-lived stream would hold a pool worker, so streams would starve reads. In the ASGI design, reads and streams draw on separate budgets (D6).

**D2 — Authentication: one bearer token, from the environment, enforced whenever it is set.**

- The token is read once at start-up from `AMOEBA_SERVE_TOKEN`, following the project rule that credentials come from environment variables. It is never a flag, because it would show up in `ps`. It is never in `ServeSettings` or a log line. 102's "only one environment variable" decision (D3 there) covers tunables, and a credential is not a tunable. `process-contract.md` records the distinction.
- A token shorter than `MIN_TOKEN_LENGTH` (32 characters) is refused at start-up. It is compared with `hmac.compare_digest`. A missing or wrong token returns 401 with `WWW-Authenticate: Bearer`, and the response does not say which of the two it was.
- When the token is set, every request needs it, including on a loopback bind. A reverse proxy in front of a loopback bind is otherwise an unauthenticated network exposure. The contract tells operators who front the server with a proxy to set the token.
- When the token is unset on a loopback bind, requests are unauthenticated. This is the same trust boundary as the store file and the inbox directory, which any local user with filesystem permission can already read and write.
- **Browser requests do not cross that boundary, so three checks apply on every bind.** A web page can make requests to `127.0.0.1` that the filesystem never sees.
  - A request carrying an `Origin` header is refused with 403 `origin_not_allowed`. Browsers send `Origin` on cross-origin requests and on every POST; the native clients this slice serves send none, and CORS is excluded anyway.
  - On a loopback bind, a `Host` header other than `localhost`, `127.0.0.1`, or `[::1]` (with any port) is refused with 421 `host_not_allowed`. This defeats DNS rebinding, where a page on the attacker's own name resolves to loopback.
  - `POST` requires `content-type: application/json` (415 otherwise). That makes every submission a request a browser must preflight, and the server answers no preflight.
- **Failed attempts are not throttled.** The contract requires a random token, for example `openssl rand -hex 24` (192 bits), which makes guessing infeasible without a limit. The length minimum catches a short token; it cannot detect a non-random one, and the contract says so.
- **The token never reaches a log or a response.** uvicorn's access log records the method, path, and status, not headers. A test captures every log record and response body during authenticated and failed requests and asserts the token appears in none.
- **Rotation is a restart.** The token is read once at start-up. Open streams end at shutdown and clients reconnect with the new token. The contract states this in one line.

**D3 — Bind policy: loopback, or token plus TLS.** `check_bind` runs before uvicorn is constructed:

| Host | Token | TLS cert and key | Result |
| --- | --- | --- | --- |
| loopback | any | neither, or both usable | serves |
| other | set | both set | serves over HTTPS |
| other | unset | any | refused: `token_required` |
| other | set | either missing | refused: `tls_required` |
| any | set but too short | any | refused: `token_too_short` |
| loopback | any | exactly one set | refused: `tls_required` |

Half a TLS pair is refused on every bind, loopback included, so a missing `--tls-key` never silently turns an HTTPS start into plain HTTP.

A refusal exits with `ExitCode.SERVE_REFUSED` (13) and a message that names the rule. It never falls back to a loopback bind. A host counts as loopback only if it is the literal name `localhost`, or `ipaddress.ip_address(host).is_loopback` is true for it. No name is resolved, so `0.0.0.0`, `::`, and every other hostname count as non-local. TLS is required with the token because a bearer token sent in cleartext is the credential itself, delivered to anyone on the path. There is no override flag in this slice.

When TLS files are given, `check_bind` also loads them with `ssl.SSLContext.load_cert_chain` before uvicorn is constructed. A missing or unreadable file, or a certificate and key that do not match, is refused as `tls_unusable` (exit 13), with the file path and the `OSError` or `ssl.SSLError` message. Start-up failures therefore split two ways. Configuration the server can check before binding exits 13 with a message naming the rule. A failure at bind time, such as a port already in use or a host with no such interface, exits 1 with uvicorn's own message (for example `[Errno 48] address already in use`) (D7).

**D4 — Reads go through the one listing registry, and nothing else.**

- `GET /v1/listings/{name}` is generic. The listing's declared scope decides whether `project` is required. Each declared option becomes one query parameter, named from the option's `name`. A flag option takes `true` or `false`. A choice option is validated against its `choices`. A value option is passed through, and required if declared required. An undeclared parameter is a 400, never ignored.
- Rows are the `--json` form, exactly: the server builds `ListingRequest(..., compact=False)`, the same value `amoeba inspect --json` builds. The parity test compares the server's `rows` with `json.loads` of the CLI's `--json` output for every listing in `LISTINGS`.
- `as_of_seq` is read inside the same read transaction as the rows. A client that needs "current state, then everything after" reads a listing, then follows the feed with `after=as_of_seq`. That closes 106's deferral, and `feed-contract.md`'s "Current state, then follow" section is rewritten to describe it.
- `read_transaction()` opens a deferred transaction on the read-only connection, so all statements inside it see one WAL snapshot. `change_head(project_id)` is the highest `seq`, or 0 when the feed is empty.

**D5 — Submissions are `submit()` with a mandatory id.**

- Locally, `submission_id` is optional. Over the network it is **required**. If the response is lost, a client that let the server choose the id cannot retry without risking a duplicate. A required id makes every retry safe under 103's first-wins rule. A missing id returns 422 `submission_id_required`.
- The path's `project_id` is the submission's project. For `create_project`, it is the project being created.
- The body is `{kind, submission_id, submitted_by, payload}`. Unknown top-level keys return 422. The server parses only that outer shape. `kind` is converted with `SubmissionKind(value)`, and everything inside `payload` is left to `submit()`'s envelope validation, so a network submission is refused for exactly the reason a local one would be.
- `GET …/submissions/{id}` returns 200 with the record (`id`, `kind`, `outcome`, `reason`, `submitted_by`, `submitted_at`, `applied_seq`) once applied, and 404 `not_applied` before that. 404 `not_applied` is also the answer for a `create_project` whose store does not exist yet, matching 103's "the store file not existing yet is the same answer as `None`".

**D6 — The stream: `follow()` on a dedicated thread, with backpressure, heartbeats, and a slot limit.**

- *A dedicated thread per stream, not the anyio threadpool.* `follow()` blocks for as long as the client stays connected. On the shared pool, `max_streams` idle followers would take every worker token and starve reads. Stream threads are bounded separately by `max_streams` (default 32). When the slots are full, the request gets 503 `stream_limit_reached` with `Retry-After`, and the server keeps serving reads.
- *A 1-slot hand-off.* The follow thread sends each change into a 1-slot anyio memory object stream with `from_thread.run`, and blocks until the event loop takes it. A slow client therefore just reads the durable log more slowly, and the server buffers at most one change and one socket write per stream. No slow-client policy is needed, because there is nothing to drop. This is the property the architecture wanted kept out of the resident process.
- *Waking a blocked thread.* A thread blocked in that send is not inside `follow()`, so it never checks `stop`. The stream's `finally` therefore closes the receive side as well as setting the stop event, and the blocked send raises `ClosedResourceError` at once. If the event loop itself is gone at shutdown, `from_thread.run` raises `RuntimeError`. The thread treats all three as "stop" and returns. A thread waiting inside `follow()` exits within one follow interval.
- *Heartbeats and disconnects.* After `heartbeat_interval_seconds` (default 15) with no change, the stream sends an SSE comment, which keeps intermediaries from closing an idle connection. *Corrected in Phase 6 (PM decision 20261018):* a disconnect is noticed on `receive()`, not on a failed send. uvicorn 0.54 advertises ASGI spec 2.3, returns `http.disconnect` as soon as the client goes, and lets later sends succeed silently. `EventStreamResponse` runs a watcher on `receive()` beside its send loop, and a disconnect ends the stream at once. A closed client therefore frees its slot within about one follow interval (the follow thread's exit), which is inside the heartbeat-plus-follow-interval bound below.
- *A send timeout for a stalled peer.* A client that stops reading while its connection stays open never makes a send fail. Once the socket buffer fills, the send blocks. Starlette's `StreamingResponse` gives no hook around its sends, so the stream is a small `EventStreamResponse` of its own (`serve/stream.py`) that runs every send under `anyio.fail_after(send_timeout_seconds)` (default 30) and closes the stream on timeout. A stalled client therefore holds a slot for at most one heartbeat interval plus `send_timeout_seconds`.
- *Reads and submissions are bounded too.* They run on anyio's default thread limiter (40 workers). Each worker's wait on the store is bounded by the read-only open's busy timeout, after which it returns 503 `store_busy`. No connection cap is set (uvicorn's default); one is added if a load test shows requests piling up.
- *Cursor precedence.* `Last-Event-ID` wins over `?after=` when both are present. A browser `EventSource` reconnects with its original URL plus that header, and the header is by construction the later cursor. Both must be non-negative integers, or the request gets 400 `invalid_cursor`.
- *Errors before and after the 200.* An unknown project or a schema mismatch is caught by a preflight open, before any byte is sent. A failure after streaming starts (the store vanished, a schema change) is sent as one `event: error` frame with an `ApiErrorCode`, and then the stream closes. An `EventSource` that reconnects then gets the preflight's 404 or 503 and stops.
- *Exactly once, in order.* The SSE events are `follow()`'s changes, in its order, each sent once with `id` equal to `seq`. A client that resumes from the last `id` it processed gets every later change once. Acting on a change once remains the client's job, as 106's contract says for local followers.

**D7 — Its own process, independent of the resident process.**

- `amoeba serve` takes no instance lock and writes no PID file. Two servers on different ports are harmless, because neither writes anything but inbox files. A port already in use fails at bind with uvicorn's error and exit status 1.
- It never reads the resident process's lock, PID file, or tenants. It works with the resident process stopped: reads see the last committed state, submissions wait in `inbox/new/`, and the stream idles until commits resume. Killing it affects nothing the resident process holds.
- On SIGTERM or Ctrl-C, uvicorn stops accepting connections and waits up to `shutdown_grace_seconds` (default 5). It then cancels the open streams, whose `finally` sets each stop event. Clients resume from their last `id`. The grace is set, not left at uvicorn's default, because that default waits for open connections indefinitely and an SSE stream never ends on its own.

**D8 — One error vocabulary.** `ApiErrorCode` is a closed `StrEnum`, defined once in `serve/errors.py`, together with one table from exception type to `(HTTP status, code)`. Every error body is `{"error": <code>, "detail": <str>}`, with `reason` added for an invalid submission. No route handler writes a status number or a code string. An exception not in the table is logged with `logger.exception` and returned as 500 `internal_error`. That is the server's one process-boundary handler, documented as such, like `cli/main.py`'s.

### Patterns and Conventions

- **Labels derive from structure.** Option names are declared once in the registry. The CLI derives `--flag` from them, and the server derives query parameter names from them. URL listing names are `Listing.name`. Scope is the `ListingScope` enum (`project`, `supervisor`), set by which row function a listing declares.
- **Event-loop discipline.** No route handler calls the store, the filesystem, or `submit()` on the loop. Each such call runs in `anyio.to_thread.run_sync`, or on the stream's own thread. Ruff's `ASYNC` rules are already enabled.
- **Settings.** `ServeSettings` is a frozen dataclass, the one home of every serve default (D3 of 102's settings pattern). It holds `host="127.0.0.1"`, `port=8765`, `tls_certfile`, `tls_keyfile`, `heartbeat_interval_seconds=15.0`, `send_timeout_seconds=30.0`, `max_streams=32`, `max_request_bytes=1_048_576`, `shutdown_grace_seconds=5.0`, and a `FeedSettings`. Each is load-bearing: the send timeout, the stream limit, and the size cap are what bound a slot, the stream threads, and a body's memory, and none has a usable library default. CLI flags exist for host, port, and the two TLS files only.
- **Exceptions.** Only the exceptions in D8's table are caught, plus the 500 boundary handler. `ServeRefusedError` is raised by `check_bind` and caught in `cli/serve.py`, which maps it to `ExitCode.SERVE_REFUSED`. It cannot be caught in `cli/main.py`, because `cli/serve.py` is the only module that imports `amoeba.serve`.

## Implementation Details

### Migration Plan

**Why the move is in this slice.** The slice plan assigns it here: its 109 entry says 109 moves every `inspect` listing module into `amoeba.inspection`, and it orders 105, 107, and 108 before 109 for that reason. The two cheaper options each give up something the plan or architecture requires:

- *Serving from `amoeba.cli` directly* would make the server import the CLI, and through `cli/inspect.py` it would also import `amoeba.process.supervisor` and its observers. The architecture says the server is not the resident process. The layering rule is how that is enforced, so it is not bypassed.
- *A separate preparatory slice* would add a slice the plan does not have. The work is already isolated: step 2 of the Development Approach is a gated commit range of its own, with no new behavior, which must leave `inspect` output byte-identical before any server code lands. Its contract-doc deltas are limited to updating paths.

The move is mechanical and changes no row. Its effort is counted in this slice's 3.

**What moves:**

| From | To | Consumers updated |
| --- | --- | --- |
| `cli/inspect.py`: `Listing`, `ChoiceOption`, `ValueOption`, `Row`, `LISTINGS`, `LISTINGS_BY_NAME`, and the four core row functions | `inspection/__init__.py` and `inspection/core.py` | `cli/main.py` (`_add_inspect_parser`), `cli/inspect.py`, tests that pin the registry |
| `cli/inspect_inbox.py`, `cli/inspect_evidence.py`, `cli/inspect_feed.py`, 107's `cli/inspect_checks.py`, and 108's `cli/inspect_cf.py` | `inspection/{inbox,evidence,feed,checks,cf}.py` | the registry, `cli/main.py` (`VerdictNotComparableError` import), `test_import_boundaries.py`'s `SINGLE_DEFINITION_MODULES` paths, and tests importing them |
| `process/supervisor.py`: `discover_project_ids` | `store/discovery.py` | `process/project_stores.py`, `inspection/core.py`, `tests/process/test_project_stores.py`. `store_path_for` stays in `supervisor.py`, and `inspection` uses `paths.project_store_path` directly. |
| `cli/feed.py`: the body of `change_line` | `feed/wire.py`: `change_record` | `cli/feed.py` (keeps printing `json.dumps(change_record(c))`), `serve/stream.py` |
| `process/review_sources.py` (added in Phase 6, PM decision 20261018: the `watches` rows call its `list_review_files`, and `inspection` may not import `amoeba.process`) | `store/review_sources.py`, whole module | `inspection/feed.py`, `process/review_detection.py`, `process/review_scan.py`, `tests/detection_harness.py`, `test_import_boundaries.py`'s `SINGLE_DEFINITION_MODULES`, and its tests, moved to `tests/store/` |

Consumers change their imports. No re-export shims are left in `amoeba.cli`, because nothing outside the repository imports these modules.

**What changes shape:**

- **Row signature.** `rows(store, args: argparse.Namespace)` becomes `rows(store, request: ListingRequest)`, and `supervisor_rows(supervisor_dir)` is unchanged. `ListingRequest` is a frozen dataclass with `project_id: str | None`, `options: Mapping[str, str | bool | None]` keyed by option `name`, and `compact: bool`. Row functions read `request.option(NODE_OPTION)` rather than `args.node`. Options gain a `name` field, and their `flag` becomes derived.
- **`compact`.** `finding_rows` and `change_rows` used `args.json` to choose an abbreviated or full finding key. That is now `request.compact`, so "table form" is stated as presentation, not inferred from a CLI flag. The CLI sets `compact = not args.json`, and the server always sets `False`.
- **`read_listing(name, request, store_dir)`** in `amoeba.inspection` holds what `run_listing` did except printing: resolve the listing, open read-only, run rows, return rows and `as_of_seq`. `run_listing` in the CLI becomes "build the request, call `read_listing`, print". The server calls the same function, so the open-read-only path exists once.

**Behavior preserved.** Before the move, capture `amoeba inspect <listing> --json` and the table output for every listing against a seeded store (the 104–108 walkthrough fixtures). After the move, both must be byte-identical. That proves the CLI is unchanged before any server code exists. `--help` output for `inspect` and every listing subcommand must also be identical. The full suite, ruff, and pyright strict pass at that commit.

### API Contracts

All paths are under `/v1`. JSON bodies are UTF-8. When a token is configured, every endpoint requires `Authorization: Bearer <token>`.

| Method and path | Success | Errors |
| --- | --- | --- |
| `GET /v1/listings/{name}?project=P&<option>=…` | 200 `{listing, project_id?, as_of_seq?, rows}` | 404 `unknown_listing`, 400 `missing_project` / `unexpected_parameter` / `invalid_option`, 400 `invalid_project_id`, 404 `unknown_project`, 404 `not_found` (`VerdictNotFoundError`), 422 `not_comparable`, 503 `store_busy` (with `Retry-After`) / `store_schema_mismatch` / `store_unreadable` |
| `POST /v1/projects/{project_id}/submissions` | 202 `{submission_id}` | 400 `invalid_project_id`, 413 `request_too_large`, 422 `invalid_body` / `submission_id_required` / `invalid_submission` (with `reason`), 503 `submission_write_failed` |
| `GET /v1/projects/{project_id}/submissions/{submission_id}` | 200 submission record | 404 `not_applied`, and the store errors as for reads |
| `GET /v1/projects/{project_id}/feed?after=N` | 200 `text/event-stream` | 400 `invalid_cursor`, 404 `unknown_project`, 503 `stream_limit_reached` (with `Retry-After`) / `store_schema_mismatch`; after the 200, an `event: error` frame |
| any | — | 401 `unauthorized`, 403 `origin_not_allowed`, 421 `host_not_allowed`, 415 `unsupported_media_type` (POST) |

**SSE frames:**

```
id: 42
event: change
data: {"seq":42,"project_id":"demo","kind":"message_posted","node_id":null,"subject_id":"…","payload":{"channel":"intent"},"recorded_at":"…"}

: keepalive

event: error
data: {"error":"store_unreadable","detail":"store at … no longer exists"}
```

The `data` object is `change_record`, so it is the same object `amoeba feed` prints per line.

### Database / Storage Schema

There is no migration and no table. The only store change is the two read-only methods in D4, added to the read-only handle's feed mixin and documented in `store-contract.md`.

## Integration Points

### Provides to Other Slices

- **110:** the network surface, so the end-to-end proof can run reads, submissions, and a follower over HTTP, with a restart of each process mid-sequence. `as_of_seq` gives it a consistent "state, then follow" read.
- **Initiative 160 and the notification bridge:** remote submission of `resolution` and `intent`, remote following of `message_posted` escalations, and outcome lookup.
- **Cowork and status views:** the listings, plus the stream.
- **Every later slice that adds a listing:** it is served with no server change, because the server iterates the registry.

### Consumes from Other Slices

- **101–108, through their contracts.** The changes to them are the moves in the Migration Plan and two additive read-only store methods. No behavior changes, and no migration.
- **If the resident process is down,** reads and the stream still work, and submissions queue in `inbox/new/` (D7). This is not degraded behavior; it is 103's contract.
- **If a store is mid-upgrade or at another schema version,** reads and the stream return 503 `store_schema_mismatch`. The server never migrates, because it opens only read-only.

## Success Criteria

### Functional Requirements

- For every listing in `LISTINGS`, against a store seeded by the 104–108 walkthroughs, `GET /v1/listings/{name}` returns `rows` equal to `amoeba inspect {name} --json`, with each declared option exercised at least once.
- A listing read's `as_of_seq` equals the feed head at the moment of the read. A test commits between two statements of a multi-query listing and shows that the rows and `as_of_seq` come from one snapshot.
- A submission POSTed over HTTP while the resident process is stopped is applied on `start`, and its outcome endpoint goes from 404 `not_applied` to 200 `applied`. A second POST with the same id returns 202 and applies nothing twice. An invalid payload returns 422 with the same `reason` that `amoeba submit` reports, and leaves nothing in the inbox.
- A stream client receives every change after its cursor once, in `seq` order. Disconnecting and reconnecting with `Last-Event-ID` (or `?after=`) across commits made while it was away yields no gap and no repeat.
- An idle stream sends a keepalive every `heartbeat_interval_seconds`. A client that closes its connection frees its stream slot within one heartbeat interval plus one follow interval. A client that stays connected but stops reading frees it within one heartbeat interval plus `send_timeout_seconds`. In both cases the follow thread has exited, including when it was blocked handing off a change.
- A POST body over `max_request_bytes` gets 413, whether or not it declares `Content-Length`, and the server stops reading at the first chunk that takes it past `max_request_bytes` (it reads at most the cap plus that one chunk). A POST retried with the same id after a 503 `submission_write_failed` is applied once.
- A request with an `Origin` header gets 403. On a loopback bind, a request with a `Host` other than a loopback name gets 421. A POST that is not `application/json` gets 415.
- During authenticated and failed requests, the token appears in no log record and no response body.
- At `max_streams` open streams, the next stream request gets 503 `stream_limit_reached`, and reads still succeed.
- `amoeba serve --host 0.0.0.0` exits 13 without a token, exits 13 with a token but no TLS files, exits 13 with a token under 32 characters, exits 13 with a missing, unreadable, or mismatched certificate and key, and serves over HTTPS with all three. With a token configured, a request without it, or with a wrong one, gets 401 on every endpoint, loopback included.
- A project id containing a path separator, `.`, or `..` gets 400 on every endpoint, and no file outside the supervisor directory is opened.
- `kill -9` of the server leaves the resident process running and the store unchanged. Stopping the resident process leaves the server serving reads, accepting submissions, and holding streams open.

### Technical Requirements

- The migration commit leaves `inspect` output and `--help` byte-identical, with the suite green, before any server code lands.
- The layering rules in Component Structure are AST tests. The writer guard is unchanged and passes. A test asserts that `amoeba.serve` calls no inbox function other than `submit` and no `Store.open`.
- `ApiErrorCode` and the exception table are the only place a status number or code appears in `amoeba.serve` (a single-definition test like 106's Rule 3).
- **Load tier** (`tests/load/test_serve_load.py`, per the Python rules for network and concurrency paths), against a real uvicorn server on a loopback port:
  - 32 concurrent followers each receive all of a burst of 600 changes, in order, with none missed. 600 is more than one `feed_batch_size` (500), so the burst crosses a batch boundary, which is where loss or reordering would appear.
  - **Delivery latency:** with 32 followers connected and reading, the p95 time from a change's commit to its arrival at a client is at most 1 s. *Corrected in Phase 6 (PM, 20261018):* measured at a steady 100 commits/s (p95 0.234 s). The 600-change burst commits in about 60 ms, so its commit-to-arrival time measures throughput (it drains to all 32 followers in about 2.7 s, roughly 7,000 frames/s for the process); the burst test asserts delivery and order only and prints the drain time. Batching the hand-off is the fix if a consumer ever needs faster bursts. This is derived from 106's bound (`follow_interval_seconds`, 0.25 s, plus the read time) with room for the hand-off and loopback transport. `network-contract.md` promises 106's bound plus transport, and nothing more.
  - **No starvation:** with 32 idle streams open, `GET /v1/listings/nodes` still succeeds. No read latency is promised, so no number is asserted.
- `ruff`, `pyright` strict, and the full suite are clean. Files stay near 300 lines.
- `docs/network-contract.md` documents the endpoints, the error codes, the bind and auth rules (including the proxy note), the stream frames, cursor precedence, delivery guarantees, `as_of_seq`, and the dated dependency observations. `feed-contract.md` replaces its "Current state, then follow" section. `inbox-contract.md` notes the required id over the network. `process-contract.md` adds the exit code and D2's tunable-versus-credential note. `store-contract.md` adds the two methods.

### Integration Requirements

- One smoke test through real subprocesses (`amoeba start`, `amoeba serve`, and an `httpx` client): create a project over HTTP, read a listing, follow the feed, and submit an intent. The follower receives one `message_posted` change. The restart matrix (`kill -9` of each process mid-sequence) belongs to slice 110's contract proof, and step 5 of the walkthrough checks mutual survival by hand.

### Verification Walkthrough

*Confirmed 20261018 at the end of Phase 6.* Run in **bash** from the repository root against a scratch store. Use three terminals, and export the same `AMOEBA_STORE_DIR` in each. `jq` and `openssl` must be on PATH. Port 8765 (and 8766 for step 6) must be free: `lsof -nP -iTCP:8765 -sTCP:LISTEN` prints nothing.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
unset AMOEBA_SERVE_TOKEN
uv run amoeba submit create-project --project demo --by pm   # prints a submission id
NODE=$(uv run python scripts/demo_evidence.py)               # seeds one node; the process must be stopped
uv run amoeba start &                                        # terminal 1
uv run amoeba serve &                                        # terminal 2: logs "Uvicorn running on http://127.0.0.1:8765"
API=http://127.0.0.1:8765/v1
```

1. **Reads match `inspect`.**
   ```bash
   diff <(curl -s "$API/listings/nodes?project=demo" | jq '.rows') <(uv run amoeba inspect nodes --project demo --json | jq '.')
   curl -s "$API/listings/nodes?project=demo" | jq '.as_of_seq'
   uv run amoeba feed --project demo | tail -1 | jq '.seq'
   ```
   The `diff` prints nothing. The two numbers are equal (observed: `1` and `1`, the seeded node's `node_created`).
2. **Follow the feed, from the snapshot.** In terminal 3:
   ```bash
   SEQ=$(curl -s "$API/listings/nodes?project=demo" | jq '.as_of_seq')
   curl -sN "$API/projects/demo/feed?after=$SEQ"
   ```
   Nothing prints except a `: keepalive` line every 15 seconds.
3. **Submit over the network.**
   ```bash
   BODY="{\"kind\":\"intent\",\"submission_id\":\"remote-1\",\"submitted_by\":\"pm\",\"payload\":{\"node_id\":\"$NODE\",\"body\":{\"ask\":\"status\"}}}"
   curl -s -w ' [%{http_code}]\n' -X POST $API/projects/demo/submissions -H 'content-type: application/json' -d "$BODY"
   curl -s $API/projects/demo/submissions/remote-1 | jq -r '.outcome'
   curl -s -w ' [%{http_code}]\n' -X POST $API/projects/demo/submissions -H 'content-type: application/json' -d "$BODY"
   ```
   The first POST prints `{"submission_id": "remote-1"} [202]`. Within a second, terminal 3 prints one frame, `id: 2`, `event: change`, with `"kind": "message_posted"` in its `data`. The outcome is `applied`. Repeating the POST prints the same `[202]`, and nothing new appears: the feed head and `inspect messages` stay where they were. *(Keep the body in a variable: nesting the escaped JSON inside `"$( … )"` mangles it into a 422 `invalid_body`.)*
4. **Submit while the resident process is down, and resume.** Stop the follower (Ctrl-C) and note the last `id:` it printed as `LAST` (observed: `2`).
   ```bash
   uv run amoeba stop                                        # "amoeba: stopped (pid …)"
   curl -s -X POST $API/projects/demo/submissions -H 'content-type: application/json' \
     -d "{\"kind\":\"intent\",\"submission_id\":\"remote-2\",\"submitted_by\":\"pm\",\"payload\":{\"node_id\":\"$NODE\",\"body\":{\"ask\":\"again\"}}}"
   curl -s $API/projects/demo/submissions/remote-2           # {"error":"not_applied","detail":"submission 'remote-2' is not applied yet"}
   uv run amoeba start &
   curl -sN $API/projects/demo/feed -H "Last-Event-ID: $LAST"
   ```
   The resumed stream prints exactly one change (`id: 3`, `message_posted`) for `remote-2`, and no repeat of `remote-1`. The outcome endpoint now returns `applied`.
5. **Each process survives the other.** Kill the **server process itself**: `kill -9 $(lsof -ti tcp:8765 -sTCP:LISTEN)`. *(Correction: under `uv run`, `$!` is uv's pid; killing it orphans the real server, which keeps listening.)* Then `uv run amoeba status` still prints `running  pid=…`, `lsof -nP -iTCP:8765 -sTCP:LISTEN` prints nothing, and `uv run amoeba inspect messages --project demo --json | jq length` prints `2`. Start `uv run amoeba serve &` again; step 1's `diff` still prints nothing.
6. **Refusals and authentication.**
   ```bash
   uv run amoeba serve --host 0.0.0.0; echo $?        # amoeba: token_required: binding '0.0.0.0' requires a bearer token / 13
   export AMOEBA_SERVE_TOKEN="$(openssl rand -hex 24)"
   uv run amoeba serve --host 0.0.0.0; echo $?        # amoeba: tls_required: binding '0.0.0.0' requires a TLS certificate and key / 13
   openssl req -x509 -newkey rsa:2048 -nodes -subj /CN=localhost -days 1 -keyout key.pem -out cert.pem
   uv run amoeba serve --host 0.0.0.0 --port 8766 --tls-cert cert.pem --tls-key key.pem &
   curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1:8766/v1/listings/projects                     # 401
   curl -sk -H "Authorization: Bearer $AMOEBA_SERVE_TOKEN" https://127.0.0.1:8766/v1/listings/projects | jq '.rows | length'   # 1
   curl -s "$API/listings/nodes?project=..%2Fx" | jq '.error'                                                 # "invalid_project_id"
   ```
   The token never appears in either server's output.
7. **Automated:** `uv run pytest tests/serve tests/inspection tests/cli/test_serve.py tests/cli/test_serve_smoke.py -v` (observed: all pass; the smoke test takes about 20 s, one default heartbeat), then `uv run pytest -s tests/load/test_serve_load.py -v` (observed: 3 passed, about 12 s; it prints the burst drain time, about 2.7 s, and the paced p95, about 0.25 s).

Clean up in this order, so `stop` still finds the store: `uv run amoeba stop`; stop each server with `kill $(lsof -ti tcp:8765 -sTCP:LISTEN) $(lsof -ti tcp:8766 -sTCP:LISTEN)`; then `rm -rf "$AMOEBA_STORE_DIR" key.pem cert.pem; unset AMOEBA_SERVE_TOKEN`. On `SIGTERM` the server shuts down within its 5-second grace and exits by the signal (a shell sees 143).

## Risk Assessment

### Technical Risks

- **Disconnect detection depends on the server's ASGI behavior.** If a uvicorn or Starlette release changes how a disconnect surfaces, slots could leak or streams could end early.
- **First network exposure.** A mistake in the bind policy or in project-id validation exposes the store, or lets a request reach files outside the supervisor directory.

### Mitigation Strategies

- The stream ends on either signal: `http.disconnect` from `receive()`, or a send that fails or times out. Tests pin slot release after an abrupt client close and after a clean close with no heartbeat due, and a test pins uvicorn's current behavior (disconnect on `receive()`, silent sends after it), so an upgrade that changes either fails the suite rather than leaking in the field.
- `check_bind` is a pure function, tested against every row of D3's table. Project ids pass through 103's id rule before any path is built. There are traversal tests on every endpoint that takes a project id, and the defaults are loopback with no override flag.

## Implementation Notes

### Development Approach

1. Confirm that 107 and 108 are merged (`inspect checks` and `inspect cf-snapshots` exist). Stop for the PM if they are not. This design takes their module names and row signatures from their designs, so check both against the merged code and update the Migration Plan's table before step 2.
2. **Migration**, with no new behavior: `amoeba.inspection`, `ListingRequest`, option names, `compact`, `read_listing`, `store/discovery.py`, and `feed/wire.py`. Capture `inspect` and `--help` outputs before, and show them byte-identical after. Commit.
3. `read_transaction()` and `change_head()`, with the snapshot test.
4. `serve/settings.py`, `policy.py`, and `errors.py`, with pure tests (D3's table, the error table, the single-definition test).
5. The app with reads and auth (Starlette `TestClient`), including the parity test over every listing and the traversal tests.
6. Submissions and outcome lookup.
7. The stream: the follow bridge, the hand-off queue, heartbeats, slots, cursor precedence, and preflight and mid-stream errors. Test against a real uvicorn on an ephemeral loopback port, because `TestClient` does not model a disconnect faithfully.
8. `amoeba serve` in the CLI, `ExitCode.SERVE_REFUSED`, TLS wiring, and shutdown grace.
9. The smoke test, the load tier, the docs, and `CHANGELOG`.

Test each step right after building it, and commit after each.

### Special Considerations

- **Secrets.** The token is never logged, echoed in an error, or stored. uvicorn's access log records paths and status codes, not headers. Submission payloads remain subject to 103's rule that callers place no secrets in them; network transport does not change that.
- **Tests never bind off loopback** and never touch the real supervisor directory. Each server test uses a scratch `AMOEBA_STORE_DIR` and an ephemeral port.
- **No new environment reads other than the token.** `AMOEBA_STORE_DIR` resolution is unchanged, and the server resolves the store directory once at start-up.
