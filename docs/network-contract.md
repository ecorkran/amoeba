---
docType: reference
project: amoeba
slice: network-api
dateCreated: 20261018
dateUpdated: 20261018
status: complete
---

# The Amoeba Network Contract

This document is the contract for `amoeba serve` and the `amoeba.serve`
package. It is written so that initiative 160, the notification bridge, a
status UI, and slice 110's end-to-end proof can use the store, the inbox, and
the change feed from another machine without reading the source.

## What the server is

`amoeba serve` is a second process, separate from the resident one. It adds no
state and no write path:

- **Reads** open project stores read-only and return the same rows
  `amoeba inspect --json` prints.
- **The only write** is `inbox.submit()`. The server drops a file into the
  inbox, exactly as `amoeba submit` does.
- **The feed** is `follow()` served as Server-Sent Events, resumable from the
  client's last `seq`.

It takes no instance lock, writes no PID file, and never reads the resident
process's lock, PID file, or tenants. It works with the resident process
stopped: reads see the last committed state, submissions wait in
`inbox/new/`, and streams idle until commits resume. Killing it affects nothing
the resident process holds. Two servers on different ports are harmless.

## What the server is not

- Not a second writer. It cannot write a store, and a test enforces that it
  calls no inbox function but `submit` and never `Store.open`.
- Not an identity system. One shared token; `submitted_by` stays free-form
  provenance.
- Not a push channel for submission outcomes. Clients poll the outcome
  endpoint. An applied submission also shows up on the feed through the row it
  lands.
- No WebSocket, gRPC, OpenAPI document, CORS, rate limiting, listing catalog,
  body-read timeout, or connection cap.

## Running it

```
amoeba serve [--host HOST] [--port PORT] [--tls-cert FILE --tls-key FILE]
```

Defaults: `127.0.0.1:8765`, plain HTTP. The token is read once, at start-up,
from `AMOEBA_SERVE_TOKEN`; an empty value counts as unset. Every other tunable
is a field of `ServeSettings` with no flag:

| Setting | Default | What it bounds |
| --- | --- | --- |
| `heartbeat_interval_seconds` | 15.0 | The gap between keepalives on an idle stream. |
| `send_timeout_seconds` | 30.0 | How long one stream send may block on a client that stopped reading. |
| `max_streams` | 32 | Open feed streams, each holding one thread. |
| `max_request_bytes` | 1,048,576 | A request body. |
| `shutdown_grace_seconds` | 5 | How long shutdown waits for open connections. Whole seconds. |
| `feed` | `FeedSettings()` | The follow interval and batch size the streams use. |

**Exit status.**

| Status | When |
| --- | --- |
| 13 (`SERVE_REFUSED`) | The bind policy refused the configuration. The message names the rule. Nothing was bound. |
| 1 (`FAILURE`) | uvicorn could not start, such as a port already in use or a host with no such interface. uvicorn logs its own message first. |
| killed by the signal | `SIGTERM` or Ctrl-C. uvicorn stops accepting connections, waits up to `shutdown_grace_seconds` for open ones, cancels the open streams, and then re-raises the signal. A shell sees 143 for `SIGTERM`. |

uvicorn's access log is on. It records the method, path, and status, and
never a header.

## Bind and authentication

`check_bind` runs before uvicorn is constructed. The first matching rule
decides:

| # | Condition | Result |
| --- | --- | --- |
| 1 | A token shorter than 32 characters, on any bind | refused: `token_too_short` |
| 2 | A non-loopback host and no token | refused: `token_required` |
| 3 | Exactly one of `--tls-cert` and `--tls-key`, on any bind | refused: `tls_required` |
| 4 | Both TLS files, and loading them fails | refused: `tls_unusable`, with the path and the error |
| 5 | A loopback host | serves |
| 6 | A non-loopback host and no TLS files | refused: `tls_required` |
| 7 | Otherwise | serves over HTTPS |

A host is loopback only if it is the literal `localhost` or an address whose
`ipaddress.ip_address(host).is_loopback` is true. No name is resolved, so
`0.0.0.0`, `::`, and every hostname count as non-local. A refusal never falls
back to a loopback bind, and there is no override flag.

**The token.**

- When a token is set, **every request needs it, on every bind, loopback
  included**: `Authorization: Bearer <token>`. A missing or wrong token gets
  401 with `WWW-Authenticate: Bearer`, and the body does not say which.
- **If you put a reverse proxy in front of a loopback bind, set the token.**
  Without one, the proxy turns the server into an unauthenticated network
  service.
- The token must be random, for example `openssl rand -hex 24` (192 bits).
  Failed attempts are not throttled; randomness is what makes guessing
  infeasible. The length check catches a short token, but it cannot tell a
  random one from a non-random one.
- The token never appears in a log record, a response body, or a header.
- **Rotating the token is a restart.** Open streams end at shutdown, and
  clients reconnect with the new token.
- Without a token, on loopback, requests are unauthenticated. That is the same
  trust boundary as the store file and the inbox directory.

**Browser defences, on every bind.** The guard refuses before routing, in this
order:

1. An `Origin` header gets 403 `origin_not_allowed`. Browsers send it; native
   clients do not.
2. On a loopback bind, a `Host` whose name is not `localhost`, `127.0.0.1`, or
   `::1` (any port, `[::1]` bracketed) gets 421 `host_not_allowed`. This
   defeats DNS rebinding.
3. The token check.
4. A `POST` whose media type is not `application/json` gets 415
   `unsupported_media_type`. Parameters such as `charset` are allowed.

## Endpoints

All paths are under `/v1`. Bodies are UTF-8 JSON. Every error body is
`{"error": <code>, "detail": <str>}`, with `reason` added for
`invalid_submission` only.

### `GET /v1/listings/{name}`

One endpoint for every listing in `amoeba.inspection.LISTINGS`. A listing added
later is served with no server change.

- **Project-scoped listings** require `project=<id>`. **Supervisor listings**
  (`projects`, `inbox`) refuse it.
- **Each declared option** is one query parameter named by the option's
  `name`: `unresolved`, `channel`, `node`, `judge_invocation_id`, `verdict`,
  `outcome`.
  - A flag takes `true` or `false`; absent means `false`.
  - A choice must be one of its choices.
  - A required value (`verdict`) must be present.
- **Strict parameters.** An undeclared parameter, or a parameter given twice,
  is refused, never ignored.
- **The body.**

  ```json
  {"listing": "nodes", "project_id": "demo", "as_of_seq": 41, "rows": [...]}
  ```

  - `rows` equals `amoeba inspect <name> --json`, serialized the same way.
  - Supervisor listings carry neither `project_id` nor `as_of_seq`.

### `POST /v1/projects/{project_id}/submissions`

```json
{"kind": "intent", "submission_id": "remote-1", "submitted_by": "bridge", "payload": {...}}
```

- **Required id.** `submission_id` is required over the network, unlike
  locally. If the 202 is lost, a client retries with the same id, and 103's
  first-wins rule makes the retry safe.
- **Exact keys.** The body must have exactly those four keys. The server
  checks only that outer shape.
- **`kind`.** Any `SubmissionKind` value. For `create_project`, the path's
  project is the one being created.
- **`payload`.** Validated by `submit()`, so a network submission is refused
  for exactly the reason a local one would be.
- **Size cap.** A declared `Content-Length` over `max_request_bytes` is refused
  before reading. Otherwise the body is read chunk by chunk, and reading stops
  at the first chunk that passes the cap. The server holds at most the cap
  plus that one chunk.
- **Success.** 202 `{"submission_id": "..."}`, once the file is durable in
  `inbox/new/`.

### `GET /v1/projects/{project_id}/submissions/{submission_id}`

- 200, once the submission has been applied or rejected:

  ```json
  {"id", "kind", "outcome", "reason", "submitted_by", "submitted_at", "applied_seq"}
  ```

- 404 `not_applied` before that. Also for a `create_project` whose store does
  not exist yet.

### `GET /v1/projects/{project_id}/feed`

**Cursor.**

- `Last-Event-ID` wins over `?after=`, then the default is 0.
- A browser `EventSource` reconnects with its original URL plus that header,
  which is the later cursor.
- Each must be a non-negative integer, or the request gets 400
  `invalid_cursor`.

**Before the 200.**

- A stream slot is taken without waiting. When all `max_streams` are taken,
  the request gets 503 `stream_limit_reached` with `Retry-After`, and reads
  keep working.
- A preflight opens the store read-only and closes it, so an unknown project
  or a schema mismatch is answered with a status, not a stream.

**Frames.**

```
id: 42
event: change
data: {"seq":42,"project_id":"demo","kind":"message_posted","node_id":null,"subject_id":"…","payload":{"channel":"intent"},"recorded_at":"…"}

: keepalive

event: error
data: {"error":"store_unreadable","detail":"…"}
```

- **`change`.** `data` is `amoeba.feed.wire.change_record`, the same object
  `amoeba feed` prints per line, and `id` is its `seq`.
- **Keepalive.** An idle stream sends `: keepalive` every
  `heartbeat_interval_seconds`, which keeps intermediaries from closing the
  connection.
- **`error`.** A failure after the 200 (the store vanished, a schema change)
  is sent as one `event: error` frame, and then the stream closes. A
  reconnecting `EventSource` then gets the preflight's 404 or 503.

**When a stream ends.**

- **The client disconnects.** The stream ends at once, and its slot frees
  within about one follow interval.
- **A send times out.** A client that stays connected but stops reading is
  dropped after `send_timeout_seconds`.
- **Shutdown.** Streams are cancelled after the grace.

In every case the follow thread exits.

### Path parameters

A project id must pass 103's id rule: non-empty, no path separator, and neither
`.` nor `..`. Otherwise the request gets 400 `invalid_project_id`, and no file
is opened.

One exception: an encoded slash such as `a%2Fb` is decoded before routing. It
matches no route and gets a plain 404, never reaching a handler.

## Error codes

Defined once, in `amoeba.serve.errors.ApiErrorCode`, with one status each:

| Code | Status | When |
| --- | --- | --- |
| `unknown_listing` | 404 | No listing by that name. |
| `missing_project` | 400 | A project-scoped listing without `project`. |
| `unexpected_parameter` | 400 | An undeclared parameter, or `project` on a supervisor listing. |
| `invalid_option` | 400 | A bad flag or choice value, a missing required value, or a repeated parameter. |
| `invalid_project_id` | 400 | The project id fails 103's id rule. |
| `unknown_project` | 404 | No store for that project. |
| `not_found` | 404 | A named record does not exist (`VerdictNotFoundError`). |
| `not_comparable` | 422 | `changes` on a failed or unparsed review. |
| `store_busy` | 503 | The store stayed locked past the busy timeout. Carries `Retry-After`. |
| `store_schema_mismatch` | 503 | The store is at another schema version. The server never migrates. |
| `store_unreadable` | 503 | The store cannot be read, or vanished mid-stream. |
| `request_too_large` | 413 | The body passed `max_request_bytes`. |
| `invalid_body` | 422 | Bad JSON, a non-object, a missing, unknown, or mistyped key, or an unknown `kind`. |
| `submission_id_required` | 422 | A POST without `submission_id`. |
| `invalid_submission` | 422 | `submit()` refused the payload. `reason` is the quarantine reason `amoeba submit` reports. |
| `submission_write_failed` | 503 | Valid, but not durably written. Nothing is left in the inbox. Retry with the same id. |
| `not_applied` | 404 | The submission is not applied yet, or its store does not exist yet. |
| `invalid_cursor` | 400 | A cursor that is not a non-negative integer. |
| `stream_limit_reached` | 503 | All stream slots are taken. Carries `Retry-After`. |
| `unauthorized` | 401 | A missing or wrong token. Carries `WWW-Authenticate: Bearer`. |
| `origin_not_allowed` | 403 | The request carried an `Origin` header. |
| `host_not_allowed` | 421 | A non-loopback `Host` on a loopback bind. |
| `unsupported_media_type` | 415 | A POST that is not `application/json`. |
| `internal_error` | 500 | Anything unmapped. It is logged with a traceback, and the detail is generic. |

`Retry-After` is 5 seconds (`RETRY_AFTER_SECONDS`).

## "Current state, then follow"

Every project read reports `as_of_seq`, the feed head inside the same read
transaction as the rows, so both come from one WAL snapshot. To get current
state and then everything after it, a client reads a listing and then opens the
feed with `after=as_of_seq`. Nothing is missed and nothing is repeated.

## Delivery guarantees

- **Exactly once, in order.** The stream's events are `follow()`'s changes, in
  order, each sent once with `id` equal to `seq`. A client that resumes from the
  last `id` it processed gets every later change once.
- **Acting once is the client's job.** As with local followers, save the
  cursor after acting, and make handling safe to repeat.
- **Backpressure, not buffering.** The server holds at most one change and one
  socket write per stream. A slow client just reads the durable log more
  slowly, and nothing is dropped.
- **Latency: 106's bound plus transport, and nothing more.** At a steady
  commit rate, a change reaches a client within `follow_interval_seconds` plus
  the read, plus loopback transport. Measured 20261018: 32 followers at 100
  commits/s, p95 0.234 s.
- **No throughput promise.** A burst is delivered in full and in order, but it
  drains at the process's rate. Measured 20261018: 600 changes committed in
  60 ms drained to 32 followers in about 2.7 s, roughly 7,000 frames/s, with
  the test clients in the same process. If a consumer needs bursts delivered
  faster, the fix is to hand off batches.

## Dependencies

Runtime: `starlette` and `uvicorn`, pinned with `>=`. Tests use `httpx2`,
because Starlette 1.8's `TestClient` is typed against it. *Resolved 20261018:*
starlette 1.8.0, uvicorn 0.54.0 (h11; httptools not installed), anyio 4.15.1,
httpx2 2.13.1. These are dated observations, not requirements.

The design depends on two uvicorn behaviors, and a test pins each:

1. **A full write buffer blocks the send.** A stalled peer blocks the send
   rather than growing memory. This is why each send has a timeout.
2. **A disconnect arrives on `receive()`.** uvicorn 0.54 advertises ASGI spec
   2.3. When a client goes, `receive()` returns `http.disconnect`, and later
   sends silently succeed. The stream therefore watches `receive()`. If a
   later uvicorn makes sends fail instead (spec 2.4), that test fails and this
   section is revisited; the stream still ends, because a failed send also
   closes it.
