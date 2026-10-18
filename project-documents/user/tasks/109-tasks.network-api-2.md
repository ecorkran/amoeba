---
docType: tasks
slice: network-api
project: amoeba
lld: user/slices/109-slice.network-api.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108]
projectState: After file 1, every listing lives in `amoeba.inspection` behind `read_listing`, which returns rows and `as_of_seq` from one snapshot; `discover_project_ids` is in `amoeba.store`, `change_record` in `amoeba.feed.wire`. No `amoeba.serve` package, HTTP dependency, or `amoeba serve` command exists yet.
dateCreated: 20261017
dateUpdated: 20261017
status: not_started
---

## Context Summary (File 2 of 3)

- Continues `109-tasks.network-api-1.md`. Its Context Summary (verified code facts, branch, commit cadence, tool knowledge, task-level additions) applies here unchanged.
- **This file:** Sections 4–6: serve foundations; the app, auth, and reads; submissions. File 3: Sections 7–9.
- **Event-loop discipline (LLD "Patterns"):** no route handler calls the store, the filesystem, or `submit()` on the loop. Each such call runs in `anyio.to_thread.run_sync`, or on the stream's own thread.
- **Test rule (LLD "Special Considerations"):** tests never bind off loopback and never touch the real supervisor directory. Every server test uses a scratch `AMOEBA_STORE_DIR` and an ephemeral port.

---

## Section 4: Serve Foundations

### Task 4.1: Add the HTTP dependencies
**Owner**: Junior AI
**Dependencies**: Task 3.4
**Effort**: 1
**Objective**: Starlette and uvicorn at runtime, httpx for tests (LLD "Interfaces Required", External).

**Steps**:
- [ ] `uv add "starlette>=<current>" "uvicorn>=<current>"` and `uv add --dev "httpx>=<current>"`, where `<current>` is the version uv resolves today (pin with `>=` like the existing dependencies). Do not add the `uvicorn[standard]` extra
- [ ] Record the resolved versions in the task notes as a dated observation
- [ ] Run `uv run pyright` once. If it reports missing types for either library, stop and tell the PM

**Success Criteria**:
- [ ] Suite, `ruff`, `pyright` clean
- [ ] Commit, e.g. `chore: add starlette, uvicorn, and httpx`

**Files to Modify**: `pyproject.toml`, `uv.lock`

---

### Task 4.2: Add `ServeSettings`
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 1
**Objective**: The one home of every serve default (LLD "Patterns", Settings).

**Steps**:
- [ ] Create `src/amoeba/serve/__init__.py` (docstring only; it must not import uvicorn) and `src/amoeba/serve/settings.py`
- [ ] `ServeSettings`: a frozen dataclass with exactly these ten fields and defaults, as the LLD lists them (LLD "Patterns", Settings). Add no other field. Follow `process/settings.py`'s style:
  - `host = "127.0.0.1"`, `port = 8765`
  - `tls_certfile` and `tls_keyfile`, both `Path | None = None`
  - `heartbeat_interval_seconds = 15.0`, `send_timeout_seconds = 30.0`, `max_streams = 32`
  - `max_request_bytes = 1_048_576`, `shutdown_grace_seconds = 5.0`
  - `feed`, a `FeedSettings` with its own defaults
- [ ] `TOKEN_ENV_VAR = "AMOEBA_SERVE_TOKEN"`, `MIN_TOKEN_LENGTH = 32`. The token is never a field of `ServeSettings`
- [ ] `__post_init__` raises `ValueError` when `heartbeat_interval_seconds`, `send_timeout_seconds`, `max_streams`, `max_request_bytes`, or `shutdown_grace_seconds` is not positive, and for a port outside 0–65535 (0 is allowed: tests use an ephemeral port)
- [ ] Add `tests/serve/__init__.py` and `tests/serve/test_settings.py`: defaults as the LLD states; each invalid value raises

**Success Criteria**:
- [ ] Tests pass; `pyright` clean
- [ ] Commit, e.g. `feat(serve): add ServeSettings`

**Files to Create**: `src/amoeba/serve/__init__.py`, `src/amoeba/serve/settings.py`, `tests/serve/__init__.py`, `tests/serve/test_settings.py`

---

### Task 4.3: Add the bind policy
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 2
**Objective**: A pure check that refuses an unsafe bind before uvicorn exists (LLD D3).

**Steps**:
- [ ] Create `src/amoeba/serve/policy.py` with `RefusalRule(StrEnum)`: `token_required`, `tls_required`, `token_too_short`, `tls_unusable`; and `ServeRefusedError(rule, detail)`, whose message names the rule
- [ ] `is_loopback(host) -> bool`: true only for `localhost` (case-insensitive) or an address whose `ipaddress.ip_address(host).is_loopback` is true. A non-address name, including a bracketed form such as `[::1]`, returns false. Never resolve a name
- [ ] `check_bind(settings, token: str | None) -> None`. `token` is `None` when unset (the CLI turns an empty variable into `None`, Task 8.1). Apply these rules in this order; the first that matches decides:
  1. [ ] Token given and shorter than `MIN_TOKEN_LENGTH` → `token_too_short`, on every bind (D2)
  2. [ ] Non-loopback host and no token → `token_required` (D3 row 3: whatever the TLS files)
  3. [ ] Exactly one of the two TLS files given → `tls_required`, on every bind, loopback included (D3's last row: half a TLS pair is never silently ignored)
  4. [ ] Both given → build an `ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)` and call `load_cert_chain(certfile, keyfile)`; an `OSError` or `ssl.SSLError` → `tls_unusable` with the file path and the error message, on every bind (D3)
  5. [ ] Loopback host → allowed
  6. [ ] No TLS files → `tls_required`
  7. [ ] Otherwise allowed (HTTPS)
- [ ] Never fall back to loopback; never log the token

**Success Criteria**:
- [ ] `pyright` clean
- [ ] Committed with Task 4.4

**Files to Create**: `src/amoeba/serve/policy.py`

---

### Task 4.4: Test the bind policy
**Owner**: Junior AI
**Dependencies**: Task 4.3
**Effort**: 2
**Objective**: Every row of D3's table, and every TLS failure, pinned.

**Steps**:
- [ ] Add a session fixture in `tests/serve/conftest.py` that writes a self-signed cert and key, and a second key that does not match, into a temp directory with `openssl req -x509 -newkey rsa:2048 -nodes -subj /CN=localhost -days 1 …`. If `openssl` is not on PATH, fail with a message saying so (no skip)
- [ ] `tests/serve/test_policy.py`: `is_loopback` for `localhost`, `127.0.0.1`, `127.1.2.3`, `::1` (true) and `0.0.0.0`, `::`, `example.com`, `192.168.1.1` (false)
- [ ] Parametrized over D3's table and each of Task 4.3's seven rules, including the overlaps (a short token on loopback; one TLS file on loopback; no token and one TLS file off loopback → `token_required`): `check_bind` returns, or raises with the right `RefusalRule`
- [ ] `tls_unusable` for: a missing cert path, a missing key path, a directory as the cert, and the mismatched key. The detail names the path
- [ ] A short-token refusal's message does not contain the token

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `feat(serve): add bind policy`

**Files to Create**: `tests/serve/conftest.py`, `tests/serve/test_policy.py`

---

### Task 4.5: Add the error vocabulary
**Owner**: Junior AI
**Dependencies**: Task 4.4
**Effort**: 2
**Objective**: One closed set of codes and the only place a status number appears (LLD D8).

**Steps**:
- [ ] Create `src/amoeba/serve/errors.py`:
  - `ApiErrorCode(StrEnum)`: every code in the LLD "API Contracts" table, plus `internal_error`
  - `STATUS_BY_CODE: Mapping[ApiErrorCode, int]`, one status for each code, from the table. An import-time check (or test) that every member has a status
  - `RETRY_AFTER_CODES`: `store_busy`, `stream_limit_reached`, with one named `RETRY_AFTER_SECONDS` constant
  - `ApiError(Exception)`: code, detail, optional `reason`. Handlers raise it; they never build a response with a status
  - `CODE_BY_EXCEPTION`: `StoreBusyError` → `store_busy`, `StoreSchemaError` → `store_schema_mismatch`, `StorePermissionError` and `StoreCorruptError` → `store_unreadable`, `VerdictNotFoundError` → `not_found`, `VerdictNotComparableError` → `not_comparable`, `SubmissionWriteError` → `submission_write_failed`. `InvalidSubmissionError` is not in this table: Task 6.1 owns its handler, because it adds `reason`
  - `error_body(code, detail, reason=None) -> dict` and `error_response(...) -> JSONResponse` adding `WWW-Authenticate: Bearer` for `unauthorized` and `Retry-After` for the codes above
- [ ] An error body is exactly `{"error", "detail"}`, plus `reason` only for `invalid_submission`

**Success Criteria**:
- [ ] `pyright` clean
- [ ] Committed with Task 4.6

**Files to Create**: `src/amoeba/serve/errors.py`

---

### Task 4.6: Test the error vocabulary and its single definition
**Owner**: Junior AI
**Dependencies**: Task 4.5
**Effort**: 2
**Objective**: Pin the table and enforce that no other serve module spells a status or code (LLD Technical Requirements, single-definition test).

**Steps**:
- [ ] `tests/serve/test_errors.py`: every `ApiErrorCode` has a status; each exception maps to its code and status; headers for `unauthorized`, `store_busy`, `stream_limit_reached`; body shapes
- [ ] Add a rule to `tests/test_import_boundaries.py` (reuse `_string_literals`), written as a helper that takes a directory: no module in it other than `errors.py` contains an `ApiErrorCode` value as a string literal, or an integer literal in 400–599 (AST `ast.Constant` of type `int`). One test runs it on `src/amoeba/serve/` (via `rglob`, so later modules are covered automatically)
- [ ] A second test runs the helper on a `tmp_path` directory holding one module with `"not_found"` and `404`, and asserts both are reported

**Success Criteria**:
- [ ] Tests pass; full suite green
- [ ] Commit, e.g. `feat(serve): add the API error vocabulary`

**Files to Create**: `tests/serve/test_errors.py`
**Files to Modify**: `tests/test_import_boundaries.py`

---

## Section 5: The App, Auth, and Reads

### Task 5.1: Add the reads endpoint and `build_app`
**Owner**: Junior AI
**Dependencies**: Task 4.6
**Effort**: 3
**Objective**: `GET /v1/listings/{name}` over the one registry (LLD D4, Data Flow "A read").

**Steps**:
- [ ] In `tests/serve/conftest.py`, add fixtures: `seeded` (a `tmp_path` supervisor directory seeded with `seed_every_listing`, `AMOEBA_STORE_DIR` set by `monkeypatch`); `make_client`, a factory fixture returning a callable `(token: str | None = None) -> TestClient` that builds a Starlette `TestClient` over `build_app(settings, token, store_dir)` with base URL `http://127.0.0.1`; `TEST_TOKEN`, a 48-hex-character constant clearly marked as a test value
- [ ] Create `src/amoeba/serve/reads.py`:
  - `validated_project_id(value) -> str`: `paths.validate_project_id`; `ValueError` → `ApiError(invalid_project_id)`. Used by every endpoint that takes a project id
  - `existing_store_path(store_dir, project_id) -> Path`: `project_store_path`, and `ApiError(unknown_project)` if it is not a file. Shared with the stream preflight (Task 7.4)
  - `listing_request(listing, query) -> ListingRequest`: `project` required for `ListingScope.PROJECT` (`missing_project`) and refused for `SUPERVISOR` (`unexpected_parameter`); any parameter not `project` and not a declared option `name` → `unexpected_parameter`; a flag accepts `true`/`false` only, absent is `False`; a choice must be in `choices`; a required value option must be present (`invalid_option`); repeated parameters → `invalid_option`; `compact=False`
  - the route: unknown name → `unknown_listing`; then validate, then on a worker thread (`anyio.to_thread.run_sync`) check the store exists and call `read_listing`. Body: `{"listing", "project_id", "as_of_seq", "rows"}`, without `project_id`/`as_of_seq` for supervisor listings. Serialize rows with `json.dumps(…, default=str)`, as the CLI does
- [ ] Create `src/amoeba/serve/app.py` with `build_app(settings, token, store_dir) -> Starlette`: routes, an exception handler for `ApiError`, one for each `CODE_BY_EXCEPTION` type, and the one boundary handler for anything else (`logger.exception`, 500 `internal_error`), commented as the server's process-boundary handler
- [ ] `store_dir` is resolved once by the caller and passed in; the app never reads the environment

**Success Criteria**:
- [ ] `pyright` clean
- [ ] Committed with Task 5.2

**Files to Create**: `src/amoeba/serve/reads.py`, `src/amoeba/serve/app.py`
**Files to Modify**: `tests/serve/conftest.py`

---

### Task 5.2: Test reads and parity with `inspect`
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 3
**Objective**: Rows equal `amoeba inspect --json` for every listing (LLD Functional Requirements, first bullet).

**Steps**:
- [ ] `tests/serve/test_reads.py`. Parity, parametrized over `LISTINGS`: for each listing, and for each declared option once (the seeded ids from `SeededStore`), `rows` equals `json.loads` of `run_cli(... "inspect", name, ..., "--json")`. The parameter set is generated from the registry, not written by hand
- [ ] `as_of_seq` equals `change_head` for project listings; absent for `projects` and `inbox`
- [ ] Refusals: unknown listing, missing project, `project` on a supervisor listing, undeclared parameter, bad flag value, bad choice, missing required `verdict`, unknown project (404), `VerdictNotFoundError` (404 `not_found`), a non-comparable verdict (422, if the seeding has one; otherwise seed one in the test)
- [ ] Traversal: `project` values `../x`, `a/b`, `.`, `..` (URL-encoded) → 400 `invalid_project_id`; assert with `monkeypatch` on `Store.open_read_only` that it was never called
- [ ] `store_schema_mismatch`: a store stamped another version (reuse the approach in `tests/test_read_only_open.py`) → 503; a file that is not SQLite → 503 `store_unreadable`; `read_listing` monkeypatched to raise `StoreBusyError` → 503 `store_busy` with `Retry-After`

**Success Criteria**:
- [ ] Tests pass; full suite green
- [ ] Commit (Tasks 5.1–5.2), e.g. `feat(serve): add the listings read endpoint`

**Files to Create**: `tests/serve/test_reads.py`

---

### Task 5.3: Add the request guard middleware
**Owner**: Junior AI
**Dependencies**: Task 5.2
**Effort**: 2
**Objective**: Token, Origin, Host, and content-type checks on every request (LLD D2).

**Steps**:
- [ ] Create `src/amoeba/serve/auth.py` with `RequestGuardMiddleware`, a **pure ASGI** middleware (not `BaseHTTPMiddleware`, which wraps streaming responses; confirm in the Starlette docs). Scopes other than `http` (uvicorn's `lifespan`; there is no websocket route) pass through to the app unchanged. Constructed with the token (or `None`) and whether the bind is loopback. In order:
  1. [ ] An `Origin` header → 403 `origin_not_allowed`
  2. [ ] Loopback bind and a `Host` whose name (port stripped; `[::1]` bracket form handled) is not `localhost`, `127.0.0.1`, or `::1` → 421 `host_not_allowed`. Hold the allowed names in one constant
  3. [ ] Token set and `Authorization` not `Bearer <token>` (compared with `hmac.compare_digest` on bytes) → 401 `unauthorized`, one detail for missing and wrong alike
  4. [ ] `POST` whose `content-type` media type is not `application/json` (parameters such as `charset` allowed) → 415 `unsupported_media_type`
- [ ] Add the middleware in `build_app`. Responses come from `errors.error_response`. Nothing here logs a header

**Success Criteria**:
- [ ] `pyright` clean
- [ ] Committed with Task 5.4

**Files to Create**: `src/amoeba/serve/auth.py`
**Files to Modify**: `src/amoeba/serve/app.py`

---

### Task 5.4: Test the request guards and token secrecy
**Owner**: Junior AI
**Dependencies**: Task 5.3
**Effort**: 2
**Objective**: D2's checks, and the token in no log or body.

**Steps**:
- [ ] `tests/serve/test_auth.py`: with a token, a request without it and with a wrong one get 401 and `WWW-Authenticate: Bearer`, with identical bodies; a correct one gets 200. Without a token on loopback, requests pass
- [ ] "401 on every endpoint": parametrize the missing-token and wrong-token cases over every route, `GET /v1/listings/nodes`, `POST /v1/projects/p/submissions`, `GET /v1/projects/p/submissions/s`, and `GET /v1/projects/p/feed`. The middleware refuses before routing, so the routes Sections 6 and 7 add need not exist yet
- [ ] `Origin` present → 403. Host `evil.example` → 421; `localhost:8765`, `127.0.0.1`, `[::1]:8765` pass
- [ ] Secrecy: with `caplog` at DEBUG for all loggers, make authenticated and failed requests; assert `TEST_TOKEN` appears in no record's message or args and no response body or header
- [ ] Order: a request with both `Origin` and a bad token gets 403 (Origin first)

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit (Tasks 5.3–5.4), e.g. `feat(serve): add request guards`. Uvicorn's access log is outside `TestClient`; Task 8.2 covers it

**Files to Create**: `tests/serve/test_auth.py`

---

### Task 5.5: Add the serve layering tests
**Owner**: Junior AI
**Dependencies**: Task 5.4
**Effort**: 2
**Objective**: The server cannot reach the CLI, the process, or a write path (LLD "Layering rules" and Technical Requirements).

**Steps**:
- [ ] In `tests/test_import_boundaries.py`: `amoeba.serve` imports nothing from `amoeba.cli` or `amoeba.process`
- [ ] No module in `src/amoeba/` other than `cli/serve.py` imports `amoeba.serve` (the test tolerates `cli/serve.py` not existing yet; it will by Task 8.1)
- [ ] AST check over `serve/`, enforcing the LLD rule that `serve` calls no inbox function other than `submit`:
  - every name imported from `amoeba.inbox` is in one named allow-set: `submit`, `InvalidSubmissionError`, `SubmissionWriteError`. Anything else (`pending`, `failed`, `quarantined`, …) fails the test
  - `SubmissionKind` comes from `amoeba.store.inbox_models`, where it is defined, not through `amoeba.inbox`
  - no call to `Store.open` (attribute `open` on `Store`) appears
- [ ] The check passes vacuously until Task 6.1 adds the first inbox import; Task 6.1 re-runs it
- [ ] Confirm `tests/test_writer_guard.py` passes with no allow-list change

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit, e.g. `test: add serve layering rules`

**Files to Modify**: `tests/test_import_boundaries.py`

---

## Section 6: Submissions

### Task 6.1: Add the submission endpoints
**Owner**: Junior AI
**Dependencies**: Task 5.5
**Effort**: 3
**Objective**: `POST` a submission through `submit()` with a required id, and `GET` its outcome (LLD D5, Data Flow "A submission").

**Steps**:
- [ ] Create `src/amoeba/serve/submissions.py`. `POST /v1/projects/{project_id}/submissions`:
  1. [ ] Validate the project id
  2. [ ] `Content-Length` over `max_request_bytes` → 413 `request_too_large` before reading. Then read the body chunk by chunk from `request.stream()`, keeping a running byte count. As soon as one chunk takes the count past `max_request_bytes`, stop reading, and do not take another chunk, then return 413. This holds with or without `Content-Length`. The server cannot choose the chunk size, so the bound is "the cap plus the one chunk that crossed it", not "the cap plus one byte"
  3. [ ] Parse JSON. The body must be an object with exactly these keys: `kind` (string), `submission_id` (string), `submitted_by` (string), `payload` (object). Missing `submission_id` → 422 `submission_id_required`; any other missing key, an unknown key, a wrong type, bad JSON, or a non-object → 422 `invalid_body`. `kind` via `SubmissionKind(value)`; an unknown kind → `invalid_body`. String contents (e.g. empty) are left to `submit()`
  4. [ ] On a worker thread: `submit(project_id=…, kind=…, payload=…, submitted_by=…, submission_id=…, store_dir=store_dir)`. Exceptions map through `CODE_BY_EXCEPTION`
  5. [ ] 202 `{"submission_id": …}`
- [ ] `GET …/submissions/{submission_id}`: validate the project id; on a worker thread, if the store file is absent → 404 `not_applied`; else open read-only, `store.submission(id)`; `None` → 404 `not_applied`; else 200 with the record fields the LLD D5 lists
- [ ] Register both routes in `build_app`, and a handler for `InvalidSubmissionError` → 422 `invalid_submission` with `reason=error.reason` and `detail=error.detail`

**Success Criteria**:
- [ ] `pyright` clean; Task 5.5's inbox allow-set test passes now that `serve/` imports from `amoeba.inbox`
- [ ] Committed with Task 6.2

**Files to Create**: `src/amoeba/serve/submissions.py`
**Files to Modify**: `src/amoeba/serve/app.py`

---

### Task 6.2: Test submissions
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 3
**Objective**: The submission requirements in the LLD's Functional Requirements, in-process.

**Steps**:
- [ ] `tests/serve/test_submissions.py` (no resident process; apply files with the store's existing apply path from `tests/inbox_harness.py` or `feed_harness.py` where needed):
  - [ ] A valid intent → 202, and exactly one file in `inbox/new/`. A second POST with the same id → 202; after applying, one record
  - [ ] Outcome: 404 `not_applied` before apply, 200 with `outcome` after; 404 for a `create_project` whose store does not exist yet
  - [ ] An invalid payload → 422 with the same `reason` `amoeba submit` reports for that payload (run the CLI once to obtain it, not a literal) and nothing in the inbox
  - [ ] Missing id → 422 `submission_id_required`; unknown key, non-object body, bad JSON → 422 `invalid_body`
  - [ ] 413 with `Content-Length` too large (through `TestClient`)
  - [ ] Early stop on a body with no `Content-Length`. Do not use `TestClient`, which may drain the request body before the app sees it. Call the app from `build_app(...)` directly as an ASGI callable, with a hand-written `receive` that hands out fixed 64 KiB `http.request` chunks (`more_body=True`), up to well past the cap. It counts the bytes it hands out and records every call. Use a small `max_request_bytes`, e.g. 200 KiB, and a hand-written `send` that collects the response. The `http` scope must pass the Task 5.3 guards: `host: 127.0.0.1`, `content-type: application/json`, no `Origin`, and no token configured. Assert:
    - the status is 413 `request_too_large`
    - `receive` was not called again after the chunk that took the count past the cap
    - bytes handed out ≤ `max_request_bytes` + one chunk
  - [ ] `SubmissionWriteError` (monkeypatch `submit` to raise it) → 503 `submission_write_failed`; a retry with the same id then succeeds and applies once
  - [ ] Traversal ids on both endpoints. Send the path unnormalized (confirm the client keeps `.`/`..` segments; if it removes them, send the request on a raw socket): `.` and `..` reach the handler → 400 `invalid_project_id`. `a%2Fb` is decoded before routing and matches no route → 404; record this as a correction to the LLD's "400 on every endpoint" for path parameters (Task 9.4). In every case `submit` and `Store.open_read_only` were not called (monkeypatch), `inbox/` holds no file, and no new path exists under `tmp_path`
- [ ] `POST` with `content-type: text/plain` → 415 `unsupported_media_type`; `application/json; charset=utf-8` is accepted

**Success Criteria**:
- [ ] Tests pass; full suite green
- [ ] Commit, e.g. `feat(serve): add submission and outcome endpoints`

**Files to Create**: `tests/serve/test_submissions.py`

Continue in `109-tasks.network-api-3.md` (Section 7).
