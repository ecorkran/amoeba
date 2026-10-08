---
docType: slice-design
slice: network-api
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108]
interfaces: [110]
dateCreated: 20261007
dateUpdated: 20261007
status: not_started
---

# Slice Design: network-api

## Overview

Everything Amoeba offers today needs a shell on the supervisor's machine: `amoeba inspect` opens store files, `amoeba submit` drops a file into the inbox, and `amoeba feed` reads the change log. The notification bridge, Cowork, a status UI, and remote agents will not run there. This slice adds `amoeba serve`, a separate process that puts those same three surfaces on the network and nothing else:

1. **Reads.** Every `amoeba inspect` listing, served from the same listing registry, so a remote client gets the rows `amoeba inspect --json` prints.
2. **Writes.** Inbox submission through `amoeba.inbox.submit()`, the function `amoeba submit` calls, plus a status lookup a remote client needs because it cannot see the inbox directory.
3. **The feed.** 106's change log as a Server-Sent Events stream, produced by `follow()`. A client resumes with its last `seq`.

The server holds no state of its own and opens no store read-write. The resident process stays the sole writer. Killing either process leaves the other working.

## Value

Architectural enablement. Initiative 160's notification bridge, Cowork, and any status UI can read state, follow changes, and submit replies without filesystem access to the supervisor's machine. The feed reaches remote subscribers as push: the client never polls. The server's own `follow()` checks the store every `follow_interval_seconds` (106 D2), so the effective latency target is: **a committed change is on the wire within `follow_interval_seconds` (default 0.25 s) of its commit, plus the time to read and encode it.** A submission's effect adds one resident-process tick before that commit, bounded by `idle_interval_seconds` (default 1.0 s) when the process is idle (103). Local tools keep using 106's follower, which works the same way.

For the PM: `curl` against `amoeba serve` replaces SSH for checking state, and a phone-side bridge can resolve a blocked node.

## Technical Scope

**Included**

- `amoeba serve`: an HTTP server process on Starlette and uvicorn (D2), bound to `127.0.0.1` by default.
- Read endpoints over the `inspect` listing registry, moved out of `amoeba.cli` into a new `amoeba.inspection` package so the CLI and the server share one definition (D3, Migration Plan).
- `POST` submission and `GET` submission status (D4). A new `amoeba.inbox.locate()` finds a submission that is still in the inbox directory.
- The feed as SSE, with a JSON page form (`feed/page`) for clients that do not stream (D5).
- Bearer-token authentication with principals and a two-value scope (`read`, `submit`), required for any non-loopback bind. TLS is also required for a non-loopback bind (D6).
- `amoeba token add | list | revoke` to manage the token file.
- Listing discovery (`GET /v1/listings`). This is the one addition beyond the architecture's three surfaces that is not forced by auth. It is a read of the registry's own metadata, and a remote client has no `--help` to read.
- The `Change` → JSON encoding moved from `cli/feed.py` into `amoeba.feed`, so `amoeba feed` and the stream emit identical objects.
- `ServeSettings` with CLI flags; exit code `SERVE_REFUSED` (12).
- `docs/network-contract.md`; updates to `inbox-contract.md`, `feed-contract.md`, `process-contract.md`, and `CHANGELOG.md`.

**Beyond the architecture's three surfaces, and why.** Each item is either forced by a constraint the architecture sets or the smallest way to meet one:

| Addition | Forced by |
| --- | --- |
| Registry move to `amoeba.inspection`, `ListingQuery`, `abbreviated_columns` | "Same answers as `amoeba inspect`" means sharing its code, and the server must not import `amoeba.cli` (D3) |
| `change_as_json` move | The stream must emit what `amoeba feed` prints (D5) |
| `inbox.locate` | A remote client cannot see the inbox directory, so without it a quarantined submission reads as pending forever (D4) |
| Token file, `amoeba token`, scopes | "Any other bind requires authentication" needs credentials and a way to issue and revoke them (D6) |
| TLS off-loopback | A bearer token sent in clear text can be replayed (D6; PM ratification) |
| Listing discovery | A remote client has no `--help`. One read of registry metadata replaces a hand-kept list in the contract document. |

**Two task groups, one slice.** Phase 5 splits the work so the refactor never blocks on the network code, or the reverse:

- **Group A, the no-behavior-change refactor:** the gate task (Dependencies), the registry move, `ListingQuery` and `abbreviated_columns`, and the `change_as_json` move. It finishes with the byte comparison, and is committed and reviewable on its own, before any `amoeba.serve` code exists.
- **Group B, the network surface:** everything else. It starts from a finished Group A.

Splitting Group A into a slice of its own was considered and rejected: it has no consumer but this slice, and on its own it delivers no value a slice could claim. The group boundary gives the same isolation without a slice with no purpose.

**Excluded**

- Any endpoint that writes other than by submitting to the inbox.
- Resident-process status over the network (D7).
- Browser support: CORS, cookie auth, and token-in-query-string for `EventSource`. A browser status UI can stream with `fetch` and an `Authorization` header; first-class browser support is for whichever initiative builds that UI.
- WebSocket. The feed only flows one way (D1).
- A Python client library and `amoeba feed --server`. Initiative 160 builds the clients it needs. `curl` is the reference client here.
- A cross-project stream. One stream per project, matching 106.
- Rate limiting, metrics, token expiry, mutual TLS, OpenAPI generation.
- Per-kind and per-project authorization (D6), and paging of listings (D3a).

## Dependencies

### Prerequisites

- **101:** `Store.open_read_only`, `validate_project_id`, `paths.store_dir`, and the `StoreError` hierarchy.
- **102:** the `inspect` listing registry (`LISTINGS`), `discover_project_ids` / `store_path_for`, the `ExitCode` enum, and the writer guard test.
- **103:** `amoeba.inbox.submit()`, `InvalidSubmissionError` / `SubmissionWriteError`, `Store.submission(id)`, and the inbox layout (`new/`, `quarantine/`, `failed/`, `submission_filename`).
- **104:** the evidence listings (`verdicts`, `findings`, `changes`) and `VerdictNotFoundError` / `VerdictNotComparableError`.
- **106:** `follow()`, `FeedSettings`, `change_head`, `read_transaction()` on the read-only handle (106 D1a), and the `amoeba feed` JSON shape.
- **105, 107, and 108 must be merged first, and this is a hard gate.** They add listings and submission kinds but nothing here calls them by name, so they are not functional prerequisites: whatever the registry and `SubmissionKind` contain is served. They are listed in `dependencies` anyway, because the registry move (Migration Plan) relocates their listing modules. Their task documents target `amoeba.cli`, and the move is only correct once their modules are there.
  - **Gate task.** The first task of the breakdown confirms that 105–108 are merged into the target branch and that their listing modules are in `amoeba.cli`. If either check fails, it stops and asks the PM. Work does not proceed on an assumed order.
  - The slice plan's 109 entry carries the same dependency list and the reason, so anyone who reorders slices sees it.
- **New runtime dependencies:** `starlette` and `uvicorn` (the plain package, not `uvicorn[standard]`). **New dev dependency:** `httpx`, which Starlette's `TestClient` needs. Versions are whatever is current at implementation, pinned in `uv.lock`.

### Interfaces Required

- **From 106:** the function that turns a `Change` into its JSON object must be importable from `amoeba.feed`. 106's tasks put it in `cli/feed.py`. If it ships there, this slice moves it (see Migration Plan) and `amoeba feed` imports it from the new location.
- **From 106:** `read_transaction()`, so a listing and `change_head` can be read as one snapshot.
- **From 106:** `follow()` holds no read transaction while it is suspended at a `yield`. Each batch is one `changes()` call, whose rows are fully read before the first is yielded. A stream blocked on a slow client then pins no WAL snapshot, and the resident process's checkpoints are unaffected. 106's design reads this way (`rows = changes(...)`, then yield each). This slice adds a test that fails if it ever stops holding (D5).

## Architecture

### Component Structure

```
src/amoeba/inspection/            moved from amoeba.cli (Migration Plan)
  registry.py        Listing, ChoiceOption, ValueOption, Row, LISTINGS, LISTINGS_BY_NAME,
                     read_listing(), encode_rows()
  query.py           ListingQuery, ListingQueryError; query_from_params()
  rows_core.py       projects, nodes, blocked, journal
  rows_inbox.py      inbox, submissions, messages          (was cli/inspect_inbox.py)
  rows_evidence.py   verdicts, findings, changes           (was cli/inspect_evidence.py)
  rows_*.py          106–108 listings, moved the same way
src/amoeba/feed/
  encoding.py        change_as_json(change) -> dict         (moved from cli/feed.py)
src/amoeba/inbox/
  locate.py          locate(submission_id, store_dir) -> InboxLocation | None
src/amoeba/serve/
  settings.py        ServeSettings; is_loopback(host)
  app.py             build_app(supervisor_dir, settings, authenticator) -> Starlette
  reads.py           listing endpoints
  writes.py          submission endpoints
  stream.py          feed endpoints: SSE and the JSON page
  auth.py            Authenticator protocol, NoAuth, TokenAuth, Principal
  tokens.py          token file format, read and atomic rewrite
  errors.py          ApiErrorCode, the exception → status table, the error body
  server.py          run(settings): startup checks, uvicorn.Server
src/amoeba/cli/
  serve.py           amoeba serve
  token.py           amoeba token add | list | revoke
  inspect.py         keeps argparse wiring and table printing only
docs/network-contract.md
```

`amoeba.serve` imports `amoeba.inspection`, `amoeba.inbox`, `amoeba.feed`, and `amoeba.store`. It does not import `amoeba.process` or `amoeba.cli`. Nothing imports `amoeba.serve` except `cli/serve.py`.

### Data Flow

**A read:**

```
GET /v1/projects/{project}/listings/{name}?node=…
  authenticate → validate_project_id → listing exists and is project-scoped
  query_from_params(listing, project, params) → ListingQuery     (D3)
  Store.open_read_only(store_path_for(supervisor_dir, project), busy_timeout_seconds=…)
    with read_transaction():
      rows = listing.rows(store, query)
      head = store.change_head(project)
  len(rows) > max_listing_rows → 413 listing_too_large               (D3a)
  200 {"listing", "columns", "rows": encode_rows(rows), "change_head": head}
```

`change_head` comes from the same snapshot as the rows, so "read this listing, then stream from `change_head`" misses nothing and repeats nothing. Supervisor-level listings (`projects`, `inbox`) are served at `/v1/listings/{name}` and have no `change_head`.

**A write:**

```
POST /v1/projects/{project}/submissions   {"kind", "payload", "submitted_by", "submission_id"?}
  authenticate (scope submit) → body read within request_body_timeout_seconds,
    size ≤ max_request_bytes → JSON object
  if authenticated: submitted_by must equal the principal (D6)
  amoeba.inbox.submit(project_id, kind, payload, submitted_by, submission_id, store_dir)
  202 {"submission_id"}
```

It works with the resident process stopped, as `amoeba submit` does. The process applies it on its next tick, or at its next start.

**Submission status:**

```
GET /v1/projects/{project}/submissions/{id}
  up to two passes of:
    store.submission(id)  → applied | rejected            (if the store exists)
    inbox.locate(id)      → pending | quarantined | failed (scans new/, then quarantine/, then failed/)
    store.submission(id)  → applied | rejected            (it may have been applied in between)
  nothing found in either pass → 404 unknown_submission
```

The scan order follows the direction files move. The process moves a file with one atomic rename, and only in three ways: `new/` → `quarantine/`, `new/` → `failed/`, and `new/` → deleted, which happens after its record commits. So a file is always in exactly one place, and every move goes to a place scanned later in the pass. A file that leaves `new/` after `new/` was scanned is found in `quarantine/` or `failed/`, or by the final store check. The only move against that direction is an operator requeueing a file by hand, back into `new/`. The second pass covers a requeue that happens during the first. A 404 then needs two hand moves timed against two passes. **Test:** with `locate`'s scan paused between directories, move a file `new/` → `quarantine/` (and, separately, `new/` → `failed/`, and apply-and-delete). Each lookup reports the file's real state, never 404.

**The feed stream:**

```
GET /v1/projects/{project}/feed?after=N       (or Last-Event-ID: N, which wins)
  authenticate → project store opens read-only (404 / 503 before any byte is streamed)
  acquire a stream slot (max_feed_streams) or 503 too_many_streams
  worker thread: for change in follow(store_dir, project, after=N, settings, stop=stop.is_set):
                   put change in a bounded buffer; while full, wait in short slices checking stop
                   (no read transaction is open here: follow() holds none across a yield)
  response:      for each change → send "id: {seq}\nevent: change\ndata: {change_as_json}\n\n"
                 nothing for heartbeat_seconds → send ": keepalive\n\n"
                 any one send not completed within stream_stall_seconds → close the stream
  client gone, stalled, or server shutting down → set stop; the thread exits within follow_interval
```

### State Management

None that survives a restart. Per stream, the server holds a cursor and a bounded buffer in memory. The client owns the cursor (106's rule). After a disconnect it reconnects with the last `id:` it received. The token file is the only file the server reads that is not a store or inbox file. It is read on every authenticated request, so a revocation takes effect at once for new requests, and within `heartbeat_seconds` for streams that are already open (D6). It is a few lines, so reading it each time costs little. `amoeba token` rewrites it atomically, so a reader never sees half a file. What happens when the file goes bad while the server runs is in D6.

## Technical Decisions

### Technology Choices

**D1 — HTTP/1.1 with JSON, and Server-Sent Events for the feed.** SSE is a one-way stream of events, which is exactly what the feed is. Its event `id:` and the `Last-Event-ID` header that clients send on reconnect match 106's `seq` cursor one to one, so resume needs no protocol of Amoeba's own. It is plain HTTP, so the `Authorization` header, TLS, and reverse proxies all work unchanged.

- Rejected: WebSocket. It is bidirectional, which the feed does not need, and resume would be a message format of our own.
- Rejected: long-polling the JSON page. It is offered anyway (`feed/page`), but as the primary transport it is the polling the network edge exists to remove (106 D2).

**D2 — Starlette on uvicorn.** *(PM ratification required: first runtime dependencies beyond pydantic.)*

- Starlette is a small ASGI toolkit with routing, `StreamingResponse`, and a `TestClient`, and nothing else. It accepts the synchronous read and submit functions as they are: Starlette runs a sync endpoint in its thread pool.
- uvicorn is the standard ASGI server. It handles TLS (`ssl_certfile`/`ssl_keyfile`) and graceful shutdown with a timeout. The plain package uses the pure-Python `h11` parser, which avoids the C-extension extras.
- Rejected: stdlib `http.server`. Python's documentation says it is not recommended for production and only implements basic security checks. That rules it out for something exposed to a network.
- Rejected: FastAPI. Its main benefit is request validation through pydantic models, but submissions must be validated by `submit()` itself so that network and CLI submissions are refused for identical reasons. FastAPI would add a second validator to keep in step with the first.
- Rejected: aiohttp. It is a capable server, but it has its own request model and test tooling, where Starlette's ASGI fits uvicorn and `TestClient` directly. Either would work; Starlette is the smaller surface.

**D3 — Reads are the `inspect` listing registry, moved to `amoeba.inspection`.** The success criterion is "the same answers as `amoeba inspect`". The only way to guarantee that is to make it the same code. A second set of read endpoints, one written for each store method, would drift the first time a listing gained a column.

- The registry, its option types, and every row function move out of `amoeba.cli` into `amoeba.inspection`. `cli/inspect.py` keeps argparse construction and table printing. The server would otherwise have to import from the CLI package, which inverts the layering.
- **Row functions take `(store, ListingQuery)`, not `argparse.Namespace`.** Today they take the CLI's parsed namespace. Keeping that in the shared layer would make an argparse type the contract the server depends on, and the server would have to fake a CLI parse. `ListingQuery` is a frozen record: `project: str | None`, plus the listing's option values keyed by option name. It has three typed accessors: `value(name) -> str | None`, `choice(name) -> str | None`, and `flag(name) -> bool`. Each accessor raises `ListingQueryError` if `name` is not an option the listing declares with that type. So the `Listing`'s `flags`, `choice_options`, and `value_options` stay the **only** declaration of a listing's options. There is no per-listing options class to keep in step. A row function that asks for an undeclared option fails on its first test.
- **Two builders, one validation.** `query_from_params(listing, project, params)` (server) and `query_from_namespace(listing, namespace)` (`cli/inspect.py`) both produce a `ListingQuery` by walking the listing's declared options. Choice values are checked against `choices`, required value options must be present, and flags parse `true`/`false`. On the server, an unknown query parameter is `400 invalid_query`, not ignored, so a misspelled `nod=` cannot silently return every node.
- **Rows no longer depend on output format.** Today `findings` and `changes` shorten the content `key` unless `--json` is set (`args.json`). That is presentation inside a query. After the move, rows always carry the full key, and `Listing` gains `abbreviated_columns: tuple[str, ...]`, which only the CLI's table printer shortens. `inspect --json` and the table look exactly as they do today, and the server needs no `json` flag.
- `encode_rows()` is the one JSON encoding of rows (today `json.dumps(rows, default=str)` inside `run_listing`). The CLI and the server both call it.
- A listing added later is served with no server change. That is the point: 107's `calibration` and 108's `cf-snapshots` appear on the network the day they are registered.
- Rejected: keeping `argparse.Namespace` as the carrier. It is the smallest change, but a CLI parsing type would become a cross-layer contract (see above).
- Rejected: a typed options class per listing. Every option would be declared twice, once on the `Listing` and once on the class.

**D3a — Listings are capped, not paged.** Row functions build full lists, exactly as `inspect` does locally, and no 101–108 read method takes a limit. Real paging would mean changing store contracts this slice does not own.

- **`max_listing_rows`** (default 10,000). A listing with more rows is refused with `413 listing_too_large`, giving the row count and telling the client to narrow it (`node=`, `unresolved=true`, `channel=`). The response is never truncated: a short list that looks complete is the silent failure this project forbids.
- **Memory is bounded by concurrency.** Sync endpoints run in Starlette's thread pool, so at most that many listings are being built at once. The largest store-backed lists (journal, submissions, messages) grow without bound only until retention lands. That is slice-plan future work item 5, and paging belongs with it.
- **The feed is already paged.** `feed/page` takes `limit`, and history that grows forever is meant to be read from the feed, not from a listing.

**D4 — Writes are `submit()` and nothing else.** One handler calls `amoeba.inbox.submit()` with the body's fields. There is no per-kind endpoint and no per-kind code, so a kind added by a later slice is accepted the day it lands, validated by its own payload model.

- `InvalidSubmissionError` → `422 invalid_submission`, carrying its quarantine `reason`. `SubmissionWriteError` → `503 submission_write_failed`. In both cases nothing was written, which is 103's guarantee and is stated in the error body.
- `202 Accepted`, never `200`: the submission is durable but not applied. The client learns the outcome from the status endpoint. That is 103's "learn by reading" rule, done over HTTP.
- **Submission status** needs `amoeba.inbox.locate(submission_id, store_dir) -> InboxLocation | None`, a new export: `(state: pending | quarantined | failed, path, reason | last_error)`. Without it, a remote client whose submission was quarantined as `no_store_for_project` would see "pending" forever, because it cannot list `inbox/quarantine/`. `locate` reads only file names (the id is in `submission_filename`) and sidecars, and opens no store.
- **Retries.** A client that timed out, or lost the connection before reading the response, retries with the **same `submission_id`**, which it should have chosen itself for exactly this reason. The retry gets `202` with that id, whether the first attempt was never written, is pending, or is already applied. 103's first-wins rule makes the second file a no-op when the process applies it. A retry with different content is also `202`: first wins, and the process logs the WARNING 103 specifies. The client finds out which version won from the status endpoint. No new status or error code is needed. The contract tells clients to always send their own id when they might retry. A client that lets the server generate the id cannot retry safely, because it never received the id.
- **Slow bodies.** The body must arrive within `request_body_timeout_seconds` (default 10), or the request is `408 request_timeout`. The limit is enforced while reading, together with `max_request_bytes`, before anything is parsed.
- A submission into a project with no store is accepted with `202`, exactly as `submit()` accepts it. The server does not pre-check that the project exists, because a client that just submitted `create_project` is following 103's rule correctly. The status endpoint then reports `quarantined`.

**D5 — The stream runs `follow()` in a bounded worker thread per connection.** The architecture fixes the source: "the live feed tails 106's change log with `follow()`". `follow()` blocks, so each stream runs it in a worker thread, and the async response reads from a bounded buffer the thread fills.

- **Backpressure, not buffering.** The buffer is small (`stream_buffer_size`). When a slow client stops reading, the thread blocks on the full buffer and stops reading the store. Memory per stream is bounded, and nothing is dropped. The client is behind, not lost.
- **A stalled client is closed, not waited on.** A peer that keeps its TCP connection open but stops reading would otherwise hold a stream slot indefinitely. A failed write only shows up once the kernel gives up on the connection, which can take many minutes. So every send to the client, events and keepalives alike, must complete within `stream_stall_seconds` (default 60), or the server closes the stream and logs it at INFO with the principal and last `seq` sent. The timeout measures a full socket buffer only if the server's `send` waits for the transport to drain. uvicorn's HTTP protocols are understood to pause in `send` while the transport's write buffer is over its high-water mark. That is **not assumed: it is verified at implementation**, as for slow headers (D5a). The test opens a raw socket with a small receive buffer, never reads, and asserts that the stream is closed within `stream_stall_seconds` plus a margin, and that the server's resident memory stays flat while it waits. *If it fails,* `send` is returning while uvicorn buffers in memory. Then no timeout at the application level can detect the stall, because nothing in the application ever waits. Wrapping `send` in a timeout is the mechanism here; it cannot be the fallback. The implementer stops and raises it with the PM. The candidate remedy is a different ASGI server whose `send` does apply backpressure (Hypercorn), swapped under the same Starlette app. No hand-rolled transport hack is acceptable. Closing loses nothing: the client reconnects with `Last-Event-ID` and resumes. A client that is slow but reading never hits the limit, because each send completes. Sixty seconds is four missed heartbeats, well past any network hiccup, and short enough that stalled peers cannot hold the cap for long.
- **A blocked stream pins no snapshot.** While the thread waits on a full buffer, it sits inside `follow()` at a `yield`, between batches, with no read transaction open (Interfaces Required). Its connection stays open, but in WAL mode an idle connection with no transaction does not hold back checkpoints. **Test:** fill a stream's buffer with a non-reading client, commit from a writer, run `PRAGMA wal_checkpoint(TRUNCATE)` from that writer, and assert the checkpoint completed (`busy = 0`).
- **Stop.** `follow()` takes `stop: Callable[[], bool]` (106). The response sets a per-stream event when the client disconnects or the server shuts down. The thread notices within `follow_interval_seconds`. A thread blocked on a full buffer is released by closing the buffer.
- **A cap on streams.** Each stream holds a thread for its lifetime. Streams draw from their own limiter of `max_feed_streams` (default 32), separate from the pool Starlette uses for sync reads and submissions. Too many streams cannot starve reads. Past the cap, `503 too_many_streams` with `Retry-After`.
- **Heartbeat.** An SSE comment (`: keepalive`) after `heartbeat_seconds` (default 15) with nothing to send. It keeps proxies from closing a quiet stream, and it makes a vanished client show up as a failed write within one heartbeat.
- **Resume.** The cursor comes from `Last-Event-ID` if present, otherwise `?after=N`, so a standard SSE client that reconnects to its original URL (still carrying `?after=`) resumes from what it last received. A missing cursor is `400 invalid_query` naming both forms. Silently defaulting to 0 would replay a project's whole history to a client that forgot it, and defaulting to the head would drop changes.
- **Errors before streaming, not during.** The store is opened and the project checked before the `200` and its headers are sent, so unknown projects and schema mismatches get proper status codes. A store error after streaming has started ends the stream. The client reconnects and gets the status code then.
- **Shutdown.** uvicorn's graceful shutdown waits for open connections, and a stream never finishes on its own, so `shutdown_grace_seconds` (default 5) bounds the wait. Every stream's stop event is set at shutdown. Clients reconnect to the next server with their last id.
- **`GET /v1/projects/{project}/feed/page?after=N[&limit=M]`** returns one JSON page (`changes`, and `next_after` = the last `seq`, or `after` when empty). It is `amoeba feed` without `--follow`, for clients and tests that do not stream. `limit` defaults to `FeedSettings.feed_batch_size` and may not exceed it. It sits under `feed/` rather than at `/changes`, because `/listings/changes` already names 104's finding-changes listing, and two unrelated things called "changes" in one API would be confused. `network-contract.md` names the distinction.

**D5a — Every wait has a bound.** Every wait a remote client can cause is bounded:

| Wait | Bound | Outcome |
| --- | --- | --- |
| A read meets a contended store (in WAL mode, rare: checkpoint or recovery edges) | `store_busy_timeout_seconds`, passed to `open_read_only`. It defaults to the store's own `BUSY_TIMEOUT_SECONDS` constant, referenced rather than copied. | The store raises `StoreBusyError` → `503 store_busy` with `Retry-After`. It is not folded into `store_unavailable`, which means the store cannot be read at all. |
| A slow request body | `request_body_timeout_seconds` (D4) | `408 request_timeout` |
| A stalled stream reader | `stream_stall_seconds` (D5) | Stream closed; client resumes |
| Idle keep-alive connections | uvicorn's `timeout_keep_alive`, left at uvicorn's default | Connection closed |
| Too many open connections (including slow-header clients) | `max_connections` (default 128), passed as uvicorn's `limit_concurrency` | uvicorn answers `503`; memory and threads stay bounded |
| A stream send against a full socket buffer | `stream_stall_seconds`, **provided `send` waits for drain: verified at implementation** (D5) | Stream closed. If not verified, stop and ask the PM. |
| Slow request headers | uvicorn's header handling, **verified at implementation** | The task records what uvicorn does. If it has no header-phase timeout, `network-contract.md` says so and requires a TLS-terminating proxy in front of any non-loopback deployment. A slow-header client can still only occupy a connection slot, which `max_connections` caps. |

**D6 — Authentication is explicit configuration, never inferred from the peer address.** *(PM ratification required: TLS requirement and principal binding.)*

- **`--auth none | tokens`**, default `none`. The server refuses to start (`SERVE_REFUSED`) when the bind host is not loopback and auth is `none`, or when auth is `tokens` and the token file is missing, unreadable, or has no entries. Loopback is decided once, in `is_loopback(host)`: an IP literal whose `ipaddress` form `is_loopback`, or the literal `localhost`. Any other host name, `0.0.0.0`, and `::` are non-loopback.
- **Requests are never trusted for their source address.** A reverse proxy on the same machine makes every remote client arrive from `127.0.0.1`. A rule like "local requests skip auth" would therefore open the server to the world through the proxy. With `tokens`, every endpoint requires a valid token, whatever address the request came from. The contract tells anyone fronting the server with a proxy to run `--auth tokens`.
- **Non-loopback binds also require TLS** (`--tls-cert`, `--tls-key`), or the server refuses to start. A bearer token sent over plain HTTP on a network can be read and replayed by anyone on the path. Terminating TLS at a proxy is supported through the loopback bind with `--auth tokens`.
- **Tokens.** `amoeba token add --principal NAME --scope read|submit` generates a token (`secrets.token_urlsafe(32)`), prints it once, and stores only its SHA-256, with the principal and scope, in `{supervisor_dir}/serve/tokens` (mode `0600`, rewritten atomically). `list` prints principals and scopes. `revoke --principal NAME` removes one. The server compares hashes with `hmac.compare_digest`. A stolen copy of the file cannot be used as tokens. File format: one `principal scope sha256:<hex>` per line, with `#` comments, blank lines, and any run of whitespace between the fields all accepted (lenient parsing). A malformed line, an unknown scope, or a duplicate principal refuses the whole file and names its line number. Skipping it would silently disable a token someone believes is active.
- **Scopes: `read` and `submit`.** A `read` token may use the listing and feed endpoints. A `submit` token may also post submissions. Anything else is `403 insufficient_scope`. `--scope` has no default: the operator states it. This is the first network exposure of the only write path, and a status UI or a remote reader should not hold the bridge's power to resolve blocks and create projects. Defining the field now, while the file format is new, costs one column. Adding it after tokens are in use would be a format migration. `TokenScope` is a `StrEnum`, and the endpoint → required scope mapping is one table in `auth.py`. With `--auth none` there are no principals and no scopes, and every endpoint is open. That is the loopback-only mode.
- **Open streams are re-checked, not trusted for their lifetime.** A stream outlives the request that opened it by hours. At every heartbeat tick, and so at least once every `heartbeat_seconds` whether or not events are flowing, the stream re-runs the same check a new request gets: token present in the file, scope still sufficient. The token file is read again, as for any request. If the check fails, the server sends one terminal event and closes:

  ```
  event: closed
  data: {"code": "unauthenticated" | "insufficient_scope" | "auth_unavailable"}
  ```

  The codes are `ApiErrorCode` values, and the table above applies unchanged. A revoked token or a lowered scope ends the stream. A broken token file ends every stream with `auth_unavailable`. A client that reconnects gets the same answer as an HTTP status. So revocation takes effect at once for new requests and **within `heartbeat_seconds` (default 15) for open streams**, which `network-contract.md` and the Success Criteria state. With `--auth none` there is nothing to re-check.
- **Per-kind and per-project scopes are excluded, deliberately.** Which roles need which kinds (may a Judge submit `resolution`?) is for initiatives 140 and 160 to define, and today a supervisor typically holds one project. The two-value scope is the coarse split every consumer needs now. A finer field can be added to the line format when one of them asks for it.
- **The token file failing while the server runs fails closed and loud.** The file is re-read on each authenticated request, so it can break after a startup check passed:

  | File state at request time | Response | Log |
  | --- | --- | --- |
  | Valid, token matches, scope sufficient | Served | Access log only |
  | Valid, no matching token (including every token revoked, which leaves a valid empty file) | `401 unauthenticated` | Access log only. An empty file is a deliberate revocation, not a fault. |
  | Missing, unreadable, or malformed | `503 auth_unavailable`. No request is served, including ones whose token was valid before. | ERROR once when the file goes bad, naming the cause (and line number if malformed), and INFO once when it is valid again. Not once per request. |

  `503`, not `401`, so a client and an operator can tell a broken server configuration from bad credentials. There is no fallback: neither the last good copy nor "skip the bad line" is used, since either would keep revoked tokens working or silently drop valid ones.
- **A principal is who wrote the submission.** When authenticated, the body's `submitted_by` is still required, and must equal the token's principal, or `403 principal_mismatch`. The body is the same shape in both auth modes, and the store's `submitted_by` (and so a resolution's `resolved_by`) names a party the server verified. A bridge relaying a person's reply records that person in `detail`. Recording a delegated identity is left to initiative 160 if it needs one.
- **Secrets stay out of logs.** The access log records method, path, status, and principal, and never headers. Query strings carry no credentials, because tokens are accepted only in the `Authorization` header.
- Rejected: one shared token with no principals. It cannot be revoked for one client, and it lets any client claim any `submitted_by`.
- Rejected: tokens in an environment variable. They end up in process listings and crash dumps, and this project keeps `AMOEBA_STORE_DIR` as its only environment read (102 D3).

**D7 — No resident-process status endpoint.** `amoeba status` decides "running" by trying to take the instance lock and dropping it at once (`InstanceLock.held_by_another_process`). A remote client polling that would hold the lock in brief bursts, and an `amoeba start` that landed in one would refuse with `ALREADY_RUNNING`. Reading only the PID file would give a second, weaker definition of "running" that disagrees with `amoeba status` after a `kill -9`. A remote client learns whether submissions are being applied from the status endpoint, which is what it actually needs to know. A safe status probe can be added if a consumer asks for one, and would be a change to 102's lock.

**D8 — `amoeba serve` is a separate process that takes no lock.** This follows the architecture (PM, 20260928). It has no state, opens stores read-only, and writes only inbox files, which any number of writers may do. So several servers may run at once **on the supervisor's machine**, on different ports, and none needs to coordinate with the resident process. *Same host only:* a read-only open of a WAL-mode SQLite store needs the store's `-shm` shared-memory file, which does not work across hosts or over network filesystems. Submissions are also file writes into the supervisor's inbox directory. A server on another machine would need both to work over a shared filesystem, and SQLite does not support that. `network-contract.md` states that `amoeba serve` runs on the supervisor's machine, and that remote parts reach it over the network, not by mounting its directory. It discovers projects per request, honoring "never cache `project_ids`". Logging goes to stderr, as with `amoeba start`. It runs in the foreground; supervision is the operator's (launchd, systemd), exactly as for the resident process.

### PM ratification

These choices go beyond what the architecture requires, or add to the project's footprint. **Gate:** Phase 5 does not break the affected parts into tasks until the PM rules. The registry move, the read endpoints, and the feed do not depend on any of them and can proceed.

| Decision | Why it needs a ruling | If not ratified |
| --- | --- | --- |
| D2: `starlette` + `uvicorn` at runtime, `httpx` for tests | First runtime dependencies beyond pydantic. For the expected scale of a handful of clients, dependency cost is the main trade-off against "resist complexity". | Another ASGI stack (aiohttp) is the fallback. `http.server` stays rejected for network exposure. |
| D6: TLS required for a non-loopback bind | Stricter than the architecture, which requires only authentication | Plain HTTP is allowed off-loopback, and `network-contract.md` warns that tokens can be replayed |
| D6: `submitted_by` must equal the principal | Constrains how 160's bridge records who replied | `submitted_by` is taken from the body as the CLI's `--by` is, and the principal is logged only |
| D6: `read` / `submit` scopes | Adds a field to a new file format | Every valid token can submit, and this is documented as a known limit |
| `SERVE_REFUSED` (12) | A new `ExitCode` member. Earlier slices ask the PM before adding one. | `serve` refusals use `FAILURE` (1), and are told apart only by stderr |

### Patterns and Conventions

- **Word lists** (`StrEnum`, each defined once): `ApiErrorCode` (`unauthenticated`, `auth_unavailable`, `insufficient_scope`, `principal_mismatch`, `invalid_project_id`, `unknown_project`, `unknown_listing`, `invalid_query`, `not_found`, `not_comparable`, `listing_too_large`, `invalid_submission`, `submission_write_failed`, `unknown_submission`, `store_unavailable`, `store_busy`, `request_too_large`, `request_timeout`, `too_many_streams`); `AuthMode` (`none`, `tokens`); `TokenScope` (`read`, `submit`); `SubmissionState` (`applied`, `rejected`, `pending`, `quarantined`, `failed`). `applied`/`rejected` reuse the store's outcome enum values rather than repeating them.
- **One error table** in `errors.py` maps each exception type to `(ApiErrorCode, HTTP status)`. Handlers raise and never construct an error response. Body: `{"error": {"code", "message"}}`, plus `reason` for `invalid_submission`. Anything not in the table is logged with `logger.exception` and returned as `500` with a generic message, at the process boundary (the CLAUDE.md exception rule, case c).
- **Routes are versioned** under `/v1`. Paths are built from the registry and `SubmissionKind`, never from a hand-kept list.
- **Writer guard.** Every module in `amoeba.serve` and `amoeba.inspection` is in `test_writer_guard.py`'s scanned set and none is permitted a read-write open. The existing assertion naming `cli/inspect.py` moves to the new registry module.

## Implementation Details

### Migration Plan

Two moves, both with no behavior change, done before any server code so the existing tests prove them.

**1. The listing registry → `amoeba.inspection`.**

| Source | Destination |
| --- | --- |
| `cli/inspect.py`: `Row`, `ChoiceOption`, `ValueOption`, `Listing`, `LISTINGS`, `LISTINGS_BY_NAME`, `PROJECTS_LISTING`, the four core row functions | `inspection/registry.py`, `inspection/rows_core.py` |
| `cli/inspect_inbox.py` | `inspection/rows_inbox.py` |
| `cli/inspect_evidence.py`, including `VerdictNotComparableError` | `inspection/rows_evidence.py` |
| 106's `cli/inspect_feed.py`, and the listing modules 107 and 108 add | `inspection/rows_*.py`, one per source module |
| The `json.dumps(rows, default=str)` in `run_listing` | `inspection.encode_rows()` |
| Row functions' `args: argparse.Namespace` parameter and `args.json` key truncation | `query: ListingQuery` and `Listing.abbreviated_columns` (D3). This is the one signature change in the move. |

- **Whose code moves.** 102's registry and the row modules of 104 and 106–108. Under the slice plan's order these slices are finished before 109 starts (Dependencies), so the move is a relocation of finished code, owned and done here. No other slice's task document changes. A listing written **after** this slice is added in `amoeba.inspection`. `process-contract.md`'s "Listings are declared in one registry" paragraph is updated to name the new module, which is how a later slice finds it. The registry is an internal extension seam of the CLI, not a published read contract, so moving it changes no 101–108 contract. Every listing's output stays the same.
- **Order of work inside the move.** First relocate the modules unchanged. Then change the row signature, one module at a time, running the byte comparison after each.
- **Consumers updated in the same commit:** `cli/inspect.py` (argparse, `query_from_namespace`, `run_listing`, table printing with abbreviation), `cli/main.py` (the boundary handler's `VerdictNotComparableError` import), `tests/test_cli_inspect.py`, `tests/cli/test_inspect_evidence.py`, `tests/cli/test_submit.py`, `tests/test_writer_guard.py`, the test pinning the listing set, and the CLI tests 106–108 add for their listings. There are no re-export shims: every importer is in this repository and is changed in the move.
- **Verification:** the full suite passes. Test changes are limited to import lines, plus row-function tests that called a row function directly with a namespace and now pass a `ListingQuery`. `amoeba inspect <every listing>` output, in both the table and `--json` forms, is captured on a seeded store before the move and compared byte for byte after it.

**2. `Change` → JSON → `amoeba.feed.change_as_json`.** If 106 left the encoding in `cli/feed.py`, it moves to `feed/encoding.py` and is exported. `amoeba feed`'s CLI tests pass unchanged.

### API Contracts

Base path `/v1`. With `--auth tokens`, every endpoint requires `Authorization: Bearer <token>` with at least the scope shown. All bodies are JSON, except the stream.

| Method and path | Scope | Success | Notes |
| --- | --- | --- | --- |
| `GET /v1/listings` | `read` | `200 {"listings": [{"name", "scope": "project"\|"supervisor", "columns", "options"}]}` | Discovery, from the registry. |
| `GET /v1/listings/{name}` | `read` | `200 {"listing", "columns", "rows"}` | Supervisor-level listings: `projects`, `inbox`. |
| `GET /v1/projects/{project}/listings/{name}?…` | `read` | `200 {"listing", "columns", "rows", "change_head"}` | Query parameters are the listing's options without `--`: `node=ID`, `channel=intent`, `unresolved=true`. |
| `POST /v1/projects/{project}/submissions` | `submit` | `202 {"submission_id"}` | Body `{"kind", "payload", "submitted_by", "submission_id"?}`. `payload` is omitted or `{}` for `create_project`. A retry with the same id is `202` again (D4). |
| `GET /v1/projects/{project}/submissions/{id}` | `read` | `200 {"submission_id", "state", "reason"?, "applied_seq"?}` | `state` is a `SubmissionState`. |
| `GET /v1/projects/{project}/feed/page?after=N[&limit=M]` | `read` | `200 {"changes": [...], "next_after"}` | Each change is `change_as_json`, the `amoeba feed` line. Not the `changes` listing (D5). |
| `GET /v1/projects/{project}/feed?after=N` | `read` | `200 text/event-stream` | `Last-Event-ID` overrides `after`. `Cache-Control: no-store`. Events: `id: <seq>`, `event: change`, `data: <change_as_json>`. Keepalive comments. |

Error statuses, from the one table:

| Status | Codes |
| --- | --- |
| `400` | `invalid_project_id`, `invalid_query` |
| `401` | `unauthenticated` (with `WWW-Authenticate: Bearer`) |
| `403` | `insufficient_scope`, `principal_mismatch` |
| `404` | `unknown_project`, `unknown_listing`, `not_found` (e.g. the `changes` listing with an unknown `verdict`), `unknown_submission` |
| `408` | `request_timeout` |
| `409` | `not_comparable` |
| `413` | `request_too_large`, `listing_too_large` |
| `422` | `invalid_submission` |
| `503` | `auth_unavailable`, `store_unavailable` (schema mismatch or unreadable store), `store_busy` (with `Retry-After`), `submission_write_failed`, `too_many_streams` (with `Retry-After`) |

**CLI:**

| Command | What it does |
| --- | --- |
| `amoeba serve [--host H] [--port P] [--auth none\|tokens] [--tls-cert F --tls-key F]` plus one flag per remaining `ServeSettings` field | Runs in the foreground until `SIGINT`/`SIGTERM`. Exits `SERVE_REFUSED` (12) for a refused configuration, with the reason on stderr. Flags derive from the settings fields, so a new setting appears without a second list. |
| `amoeba token add --principal NAME --scope read\|submit` | Prints the new token, and nothing else, once. Refuses a principal that already has one. |
| `amoeba token list` | Principal and scope, one per line. Never hashes or tokens. |
| `amoeba token revoke --principal NAME` | Removes it; effective on the server's next request. |

**`ServeSettings`** (frozen dataclass, the only definition of each default):

| Field | Default | Bounds / sized for |
| --- | --- | --- |
| `host` | `"127.0.0.1"` | Loopback, so a fresh install exposes nothing |
| `port` | `8740` | |
| `auth` | `AuthMode.NONE` | Refused off-loopback (D6) |
| `tls_cert`, `tls_key` | `None` | Required off-loopback (D6) |
| `max_connections` | `128` | uvicorn `limit_concurrency` (D5a) |
| `max_feed_streams` | `32` | A handful of bridges and UIs per supervisor |
| `stream_buffer_size` | `64` | Changes held per stream before backpressure |
| `heartbeat_seconds` | `15.0` | Under the 30–60 s idle timeouts common in proxies |
| `stream_stall_seconds` | `60.0` | Four missed heartbeats (D5) |
| `request_body_timeout_seconds` | `10.0` | A 1 MiB body over a slow link |
| `max_request_bytes` | `1_048_576` | Comfortably holds the largest captured review's findings |
| `max_listing_rows` | `10_000` | Far beyond any listing in the captured data; caps response size (D3a) |
| `store_busy_timeout_seconds` | the store's `BUSY_TIMEOUT_SECONDS` | Referenced, not copied (D5a) |
| `shutdown_grace_seconds` | `5.0` | Bounds the wait for open streams at shutdown |

The token file path is derived from the supervisor directory and is not a setting, so there is one place to look. The parent architecture sets no numeric targets. These are this slice's choices, and none is a contract promise except the latency bound under Value.

**`amoeba.inbox` addition:** `locate(submission_id: str, store_dir: Path | None = None) -> InboxLocation | None`, and the `InboxLocation` record.

**`amoeba.feed` addition:** `change_as_json(change: Change) -> dict[str, object]`.

### Database / Storage Schema

None. No migration and no table. The only new file is `{supervisor_dir}/serve/tokens`.

It cannot be mistaken for a project. `discover_project_ids` lists only regular files named `*{STORE_FILE_SUFFIX}` in the supervisor directory, and `store_path_for` maps a project to such a file. A `serve/` directory matches neither, which is already true of the `inbox/` and `detection/` directories beside it. A project named `serve` is still valid: its store is `serve{STORE_FILE_SUFFIX}`, a different path from the directory. **Test:** with the token file present, `inspect projects` and `GET /v1/listings/projects` do not list `serve`, and creating a project named `serve` works with the token file untouched.

## Integration Points

### Provides to Other Slices

- **110 (contract proof):** the network surface, which the slice plan says 110 proves "through the network surface as well as locally". 110's design was written before this one and had no network actor. It has been amended alongside this design to add two: a **remote subscriber** that follows the feed over SSE for the whole sequence, across every kill, whose transcript must equal the local subscriber's, and a **remote Judge** that makes its step-5 submissions through `POST /submissions` with a `submit`-scoped token. `amoeba serve` runs as one more subprocess in 110's harness and is never killed by its kill points, which belong to the resident process. Gaps found that way go in 110's gap table.
- **Initiative 160:** the transport for the notification bridge and the Translator surface: follow the feed, read blocked states and escalations, submit resolutions as an authenticated principal.
- **Cowork and status UIs:** the read and stream endpoints.
- **Every later slice:** a listing registered in `amoeba.inspection` and a `SubmissionKind` member are served with no server change.

### Consumes from Other Slices

- **101–104** through their contracts; the registry move is a relocation of 102's code with no behavior change.
- **103:** `submit()`, the inbox layout for `locate`, and `submission(id)`.
- **106:** `follow()`, `FeedSettings`, `change_head`, `read_transaction()`, and the change encoding.
- If the resident process is down, reads and the feed serve what is committed, and submissions are accepted and wait in the inbox. If a store is at a schema version this server does not expect (one process upgraded, the other not), its endpoints return `503 store_unavailable` and other projects are unaffected.

## Success Criteria

### Functional Requirements

- For every listing in the registry, on a seeded store, the server's `rows` equal `amoeba inspect <name> --json` for the same options. The test iterates the registry, so listings added later are covered automatically.
- A project-scoped listing's `change_head` comes from the same snapshot as its rows: a change committed between the two reads appears in neither.
- A submission posted while the resident process is stopped returns `202`, is applied at the next start, and the status endpoint goes from `pending` to `applied`. The stored record is identical to one made by `amoeba submit` with the same fields.
- An invalid payload returns `422` with the same `reason` `amoeba submit` would print, and nothing is written to the inbox.
- A submission into a project with no store reports `quarantined` with reason `no_store_for_project`.
- An SSE client receives each change once, in order. Disconnected mid-stream and reconnected with `Last-Event-ID`, it receives the rest with no gap and no repeat. Its full transcript equals `amoeba feed --project P` read from 0.
- A stream with no changes receives a keepalive comment every `heartbeat_seconds`. A client that stops reading does not grow the server's memory, and the stream's thread stops when the client disconnects.
- A client that keeps its connection open but stops reading has its stream closed within `stream_stall_seconds` of the first send that cannot complete, freeing its slot. Reconnecting with `Last-Event-ID` resumes with no gap.
- While a stream is blocked on a non-reading client, a `PRAGMA wal_checkpoint(TRUNCATE)` by the writer completes (`busy = 0`).
- A change committed while a follower is waiting is received within `follow_interval_seconds` plus delivery time (a timing test with a generous margin, using a small `FeedSettings`).
- A listing over `max_listing_rows` is refused with `413 listing_too_large` and its row count, never truncated. A request body that does not arrive within `request_body_timeout_seconds` is `408`. A read that meets `StoreBusyError` is `503 store_busy`.
- A submission retried with the same `submission_id` is `202` both times and is applied once.
- At `max_feed_streams` open streams, the next is refused with `503 too_many_streams`, and listing reads still succeed.
- No endpoint mutates a store. The writer guard covers `amoeba.serve` and `amoeba.inspection`, and the only file the server writes is an inbox submission.
- `amoeba serve --host 0.0.0.0` refuses to start without `--auth tokens`, and without TLS. With `--auth tokens` and no token file, it refuses. Each case exits `SERVE_REFUSED` naming the missing piece.
- With `--auth tokens`, a request with no token, a wrong token, or a revoked token is `401`, including requests from `127.0.0.1`. A submission whose `submitted_by` differs from the principal is `403 principal_mismatch`. A submission made with a `read` token is `403 insufficient_scope`.
- With the server running, deleting the token file, making it unreadable, or adding a malformed line makes every request `503 auth_unavailable` with one ERROR logged. Restoring it restores service with one INFO logged. Revoking the last token makes every request `401`.
- An open stream whose token is revoked, or whose principal's scope is lowered to below `read`, receives `event: closed` with the matching code and is closed within `heartbeat_seconds`. A broken token file closes every open stream with `auth_unavailable` within the same bound.
- A status lookup that races the process moving the file (`new/` → `quarantine/`, `new/` → `failed/`, or applied and deleted) reports the file's real state, never `404`.
- A stream to a raw socket that never reads is closed within `stream_stall_seconds` plus a margin, and server memory stays flat. If this cannot be shown on uvicorn, the slice stops for a PM decision (D5).
- With a token file present, `serve` is not listed as a project, and a project named `serve` can be created.
- Killing the server (`kill -9`) leaves the resident process running and the store unchanged. Killing the resident process leaves the server serving reads and streams and accepting submissions.

### Technical Requirements

- The registry move changes no `amoeba inspect` output, table or `--json` (byte comparison before and after). No re-export shims remain. No module in `amoeba.inspection` imports `argparse`. A row function reading an undeclared option raises `ListingQueryError`.
- `amoeba.serve` imports nothing from `amoeba.process` or `amoeba.cli`. The store imports nothing from `amoeba.serve`, `amoeba.inspection`, or `amoeba.feed`.
- Each word list is defined once; the exception → status table is the only place statuses are chosen.
- The token file stores only hashes, is created `0600`, and a malformed line refuses the file by line number. Tokens never appear in logs (tested by capturing the access log during an authenticated request).
- Endpoint tests use Starlette's `TestClient`. Stream, auth-refusal, and kill tests run `amoeba serve` as a real subprocess and use stdlib `http.client`, so no client library is needed at runtime.
- `ruff`, `pyright` strict, and the full suite are clean. Files stay near 300 lines.

### Integration Requirements

- End to end, as subprocesses: start the resident process and `amoeba serve`; create a project and seed a blocked node; follow the feed over SSE; resolve the block with `POST /submissions`; see the `node_status_changed` event; `kill -9` the resident process; submit again; restart it; see the event, with the SSE stream never dropped.
- `docs/network-contract.md` is enough for initiative 160's slice design to build the bridge's client without reading the code. `docs/inbox-contract.md`'s "Not a network service" and `feed-contract.md`'s transport note are updated to point at it.

### Verification Walkthrough

Draft; refined with real output when Phase 6 completes. Run in **bash** from the repository root. `scripts/demo_detection.py` (106) seeds a slice node and a `blocked_on_human` node.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
uv run amoeba start --sq-runs-dir "$(mktemp -d)" &
until uv run amoeba status | grep -q '^running'; do sleep 0.2; done
uv run amoeba submit create-project --project demo --by pm
uv run amoeba stop
read SLICE_NODE BLOCKED_NODE < <(uv run python scripts/demo_detection.py)
uv run amoeba start --sq-runs-dir "$(mktemp -d)" &
uv run amoeba serve &          # 127.0.0.1:8740, --auth none
API=http://127.0.0.1:8740/v1
```

**1. Same answers as `inspect`.**

```bash
curl -s "$API/projects/demo/listings/blocked" | jq .rows
uv run amoeba inspect blocked --project demo --json
curl -s "$API/listings" | jq '.listings[].name'
```

The two `blocked` outputs are identical. The discovery list names every `inspect` subcommand. `curl -s "$API/projects/demo/listings/nodes?nod=x"` is `400 invalid_query` naming `nod`.

**2. Follow the feed.** In a second terminal:

```bash
curl -sN "http://127.0.0.1:8740/v1/projects/demo/feed?after=0"
```

It prints `id:`/`event: change`/`data:` blocks for the two `node_created` changes and the `node_status_changed` to `blocked_on_human`, then a `: keepalive` line every 15 seconds.

**3. Resolve over the network.**

```bash
BS=$(curl -s "$API/projects/demo/listings/messages?channel=escalation" | jq -r '.rows[0].blocked_state_id // empty')
[ -n "$BS" ] || { echo "no escalation row carries a blocked_state_id"; exit 1; }
SID=$(curl -s -X POST "$API/projects/demo/submissions" -H 'content-type: application/json' \
  -d "{\"kind\":\"resolution\",\"submitted_by\":\"pm\",\"payload\":{\"blocked_state_id\":\"$BS\",\"detail\":\"approved\"}}" \
  | jq -r .submission_id)
curl -s "$API/projects/demo/submissions/$SID"
```

The follower prints `node_status_changed` from `blocked_on_human` to `runnable` within about 1.25 seconds: one idle tick of the resident process (`idle_interval_seconds`, 1.0) to apply the submission, plus `follow_interval_seconds` (0.25) for the server to see it. The status reads `applied`. The blocked state's id comes from the escalation channel because every human block writes an escalation row carrying it (103). That is the same route the notification bridge will take.

**4. Submitting with the resident process down.** `uv run amoeba stop`, then post an `intent` submission. The status reads `pending`. `uv run amoeba start …` again, and the status reads `applied`, while the follower shows the `message_posted` event and never disconnected.

**5. Resume.** Stop the follower after noting its last `id:` (say 5). Then run `curl -sN -H 'Last-Event-ID: 5' "$API/projects/demo/feed?after=0"`. It starts at 6. Compare with `curl -s "$API/projects/demo/feed/page?after=0" | jq '.changes[].seq'`: no gap, no repeat.

**6. Refusals.**

```bash
uv run amoeba serve --host 0.0.0.0; echo "exit $?"                 # 12: needs --auth tokens
uv run amoeba serve --host 0.0.0.0 --auth tokens; echo "exit $?"   # 12: no token file / no TLS
```

**7. Tokens.** Stop the server and restart it with auth:

```bash
TOKEN=$(uv run amoeba token add --principal bridge --scope submit)
VIEWER=$(uv run amoeba token add --principal status-ui --scope read)
uv run amoeba serve --auth tokens &
curl -s -o /dev/null -w '%{http_code}\n' "$API/listings"                                   # 401
curl -s -H "Authorization: Bearer $TOKEN" "$API/listings" | jq '.listings | length'         # >0
curl -s -H "Authorization: Bearer $TOKEN" -X POST "$API/projects/demo/submissions" \
  -H 'content-type: application/json' \
  -d '{"kind":"intent","submitted_by":"pm","payload":{"body":{"want":"x"}}}'                # 403 principal_mismatch
curl -s -H "Authorization: Bearer $VIEWER" -X POST "$API/projects/demo/submissions" \
  -H 'content-type: application/json' \
  -d '{"kind":"intent","submitted_by":"status-ui","payload":{"body":{"want":"x"}}}'         # 403 insufficient_scope
chmod 000 "$AMOEBA_STORE_DIR/serve/tokens"
curl -s -H "Authorization: Bearer $TOKEN" "$API/listings" | jq -r .error.code               # auth_unavailable
chmod 600 "$AMOEBA_STORE_DIR/serve/tokens"
uv run amoeba token revoke --principal bridge
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" "$API/listings"  # 401
```

The server's stderr shows one ERROR when the file became unreadable and one INFO when it recovered. No line contains a token.

**8. Independence.** `kill -9` the server; `uv run amoeba status` still reports running and `inspect` works. Restart the server, `kill -9` the resident process; reads, the stream, and submissions keep working, and the submissions apply when the process is started again.

**9. Automatically.**

```bash
uv run pytest tests/serve tests/inspection -v
```

## Risk Assessment

### Technical Risks

- **Thread-per-stream lifecycle.** A stream thread that misses its stop signal leaks a thread and a store connection until shutdown, and enough of them fill the stream cap.
- **First network exposure.** A mistake in the auth rule exposes inbox submission, the only write, to anyone who can reach the port.
- **Stalled peers holding stream slots.** Without a send bound, a few clients that stop reading could make the feed unavailable to everyone.

### Mitigation Strategies

- One code path ends a stream (`stop` set, buffer closed). Tests count live stream threads after client disconnect, stall timeout, and server shutdown, and assert zero.
- `stream_stall_seconds` bounds every send (D5). The cap test fills every slot with non-reading clients and asserts the slots free within the stall bound.
- The auth decision is two rules, both checked at startup and per request in one place: no inference from peer address, and non-loopback requires tokens and TLS. Scope is checked in the same place, from one endpoint → scope table. The token file fails closed (D6). The refusal matrix (host × auth × TLS × token file state) and the runtime file-failure table are table-driven tests. Loopback with `none` stays the default, so a fresh install exposes nothing off the machine.

## Implementation Notes

### Development Approach

Relative effort 4. The slice plan estimated 3, before the review added scopes, the typed listing query, and the stall, size, and timeout bounds.

1. **Group A.** The gate task (105–108 merged, their listing modules in `amoeba.cli`), then **the registry move**: relocate unchanged, then introduce `ListingQuery` and `abbreviated_columns` module by module, with the byte-comparison test (table and `--json`) after each. Then the `change_as_json` move if needed. No new behavior; the existing suite proves it.
2. **Group B begins.** `amoeba.serve` skeleton: `ServeSettings`, `errors.py`, `build_app`, the listing endpoints with `query_from_params`, `max_listing_rows`, `store_busy`, and the parity test over the whole registry.
3. `amoeba.inbox.locate`, then the submission endpoints (body size and timeout, same-id retry) and their status lookup.
4. The feed: `feed/page` first, then SSE with the worker thread, buffer, heartbeat, stall timeout, cap, and stop handling. Then the drain verification (D5), which must pass before the rest of the stream work, then the thread-count, checkpoint, latency, and stream re-authentication tests.
5. Auth: token file with scopes and `amoeba token`, `TokenAuth`, the scope table, principal binding, runtime file-failure handling, the startup refusal matrix, and `SERVE_REFUSED`. Steps 5–6 wait on the PM ratification gate where it applies.
6. `amoeba serve` and uvicorn wiring (TLS, `limit_concurrency`, graceful shutdown), and the same-host statement in the contract. Record what uvicorn does with slow headers (D5a). Then the subprocess end-to-end and kill tests, docs, and `CHANGELOG`.

Test each step after building it; commit after each.

### Special Considerations

- **The server must never open a store read-write.** It is a second process that touches the stores. The writer guard is the mechanical check, and the review should confirm `amoeba.serve` has no path to `Store.open`.
- **No secrets in payloads** (103's rule) matters more now that payloads are readable over the network through the `messages` and `submissions` listings. The network contract repeats the rule.
- **Payload size.** `max_request_bytes` is enforced while reading the body, before parsing, so a large body is refused without being held in memory.
- **Same-machine trust.** With `--auth none` on loopback, anyone who can open a local socket can submit. That is the same boundary as today's inbox, where anyone who can write the supervisor directory can submit. On a shared machine, use `--auth tokens`.
