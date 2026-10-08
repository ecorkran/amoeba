---
docType: tasks
slice: network-api
project: amoeba
lld: user/slices/109-slice.network-api.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108]
projectState: Continuation of files 1–2. On entry, `amoeba.serve` serves listings, submissions with status, `feed/page`, and the SSE feed behind a no-op authenticator; `amoeba.inbox.locate` exists; the stall behavior of uvicorn's `send` is verified. There is no token file, no `amoeba token`, no `TokenAuth`, no `amoeba serve` command, no `SERVE_REFUSED`, and no `docs/network-contract.md`.
dateCreated: 20261008
dateUpdated: 20261008
status: not_started
---

## Context Summary

- Continuation file for the **network-api** slice (109). See `109-tasks.network-api-1.md` for the full context summary, branch rule, reading note, PM-ratification note, and commit cadence; they apply here unchanged.
- **This file:** Section 6 (authentication, tokens, scopes), Section 7 (`amoeba serve` and server wiring), Section 8 (end-to-end, docs, final validation).
- **PM rulings (recorded in Task 1.1) decide the gated tasks:**
  - D6 scopes not ratified: every valid token can submit; keep the token file format's scope column out; document the limit (Tasks 6.1–6.3, 6.6 adjust).
  - D6 principal binding not ratified: `submitted_by` is taken from the body as `--by` is, and the principal is only logged (Task 6.7).
  - D6 TLS not ratified: plain HTTP is allowed off-loopback and the contract warns that tokens can be replayed (Task 7.1).
  - `SERVE_REFUSED` not ratified: refusals use `FAILURE` (1), told apart by stderr (Task 6.9).
  - If a ruling is "no", change the named task to the fallback and say so in the commit message. If a ruling is unknown, stop and ask.
- **Not in this slice:** see file 1. Final merge happens in Phase 7, not here.

---

## Section 6: Authentication and Tokens

### Task 6.1: Token file format and store
**Owner**: Junior AI
**Dependencies**: Task 5.7
**Effort**: 4
**Objective**: Read and atomically rewrite `{supervisor_dir}/serve/tokens` (LLD D6 "Tokens").

**Steps**:
- [ ] Create `serve/tokens.py`. `TokenScope` (`StrEnum`: `read`, `submit`) is defined once in `serve/auth.py`'s vocabulary module and imported here
- [ ] Line format: `principal scope sha256:<hex>`. Lenient parsing: any run of whitespace between fields, `#` comments, blank lines, trailing whitespace, CRLF endings. A malformed line, an unknown scope, or a duplicate principal refuses the **whole file** with an error naming the line number. Never skip a line
- [ ] Token generation: `secrets.token_urlsafe(32)`; store only the SHA-256 hex digest. Compare with `hmac.compare_digest`
- [ ] Atomic rewrite: write a temp file in the same directory with mode `0600`, fsync, rename. Create `serve/` if missing. A reader never sees half a file. Reuse 103/106's durable-write helper if it fits (its location is in your Task 1.1 notes; if none was recorded, find it with `grep -rn "write_durably" src/`); do not write a second one
- [ ] The token file path derives from the supervisor directory; it is not a setting

**Success Criteria**:
- [ ] Commit with Task 6.2

---

### Task 6.2: Tests for the token file
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 3
**Objective**: Pin the format and failure behavior.

**Steps**:
- [ ] `tests/serve/test_tokens.py`: round trip add/list/revoke; file mode is `0600`; only hashes are stored (the plain token never appears in the file); parsing accepts compact, multi-space, tab-separated, commented, and CRLF input; **include a fixture written exactly as the real `amoeba token add` writes it**, per the project parsing rule
- [ ] Table-driven refusals, each naming its line number: malformed line, unknown scope, duplicate principal, bad hash prefix. An empty (all-revoked) file is valid and empty
- [ ] A concurrent reader during a rewrite never sees a partial file (loop reads against repeated rewrites)
- [ ] Complete the Task 3.7 test: with the token file present, `GET /v1/listings/projects` and `inspect projects` do not list `serve`, and creating a project named `serve` works with the token file untouched

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: add token file format and store` (includes Task 6.1)

---

### Task 6.3: `Authenticator`, `NoAuth`, `TokenAuth`, `Principal`
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 4
**Objective**: One place that decides who a request is (LLD D6).

**Steps**:
- [ ] In `serve/auth.py`: `Principal` (name, scope); an `Authenticator` protocol with `authenticate(headers) -> Principal | None` and `authorize(principal, required_scope)` used at request time and at stream heartbeats; `NoAuth` (no principals, every endpoint open); `TokenAuth` (reads the file on **every** call, looks up the bearer token by hash)
- [ ] The `Authorization: Bearer <token>` header is the only accepted form. Tokens in a query string are never read
- [ ] **Never trust the peer address.** No rule anywhere skips auth for loopback requests; the only inputs are the header and the token file
- [ ] One table `ENDPOINT_SCOPES` maps each route to its required scope (`read` for listings, discovery, status, feed, page; `submit` for `POST /submissions`; `submit` includes `read`). Routes are checked against the table in a test so a new route without an entry fails
- [ ] Wire the app to call the authenticator before every handler (middleware or one dependency), and map outcomes through the error table: no/wrong/revoked token → `401 unauthenticated` with `WWW-Authenticate: Bearer`; insufficient scope → `403 insufficient_scope`
- [ ] Fallback if scopes were not ratified: every valid token passes; omit the scope column and `ENDPOINT_SCOPES`

**Success Criteria**:
- [ ] Commit with Task 6.4

---

### Task 6.4: Runtime token-file failure handling
**Owner**: Junior AI
**Dependencies**: Task 6.3
**Effort**: 4
**Objective**: The file failing while the server runs fails closed and loud (LLD D6 table).

**Steps**:
- [ ] A missing, unreadable, or malformed file at request time → `503 auth_unavailable` for every request, including ones whose token was valid before. No fallback to a last good copy or a skipped line
- [ ] A valid file with no matching token, including a valid empty file after every token is revoked → `401 unauthenticated` (a deliberate revocation, not a fault)
- [ ] Logging: ERROR once when the file goes bad, naming the cause and the line number if malformed; INFO once when it is valid again. Track the last-known state in the authenticator so it does not log per request. This state is a log-dedup flag only and is never used to authorize
- [ ] The access log records method, path, status, and principal, never headers

**Success Criteria**:
- [ ] Commit with Task 6.5

---

### Task 6.5: Tests for `TokenAuth`, scopes, and file failures
**Owner**: Junior AI
**Dependencies**: Task 6.4
**Effort**: 5
**Objective**: Auth behavior from the LLD Success Criteria.

**Steps**:
- [ ] `tests/serve/test_auth.py`, `TestClient` with `TokenAuth`: no token, wrong token, and a revoked token are `401` including requests presented as coming from `127.0.0.1`; a valid `read` token reads but a `submit`-requiring route is `403 insufficient_scope`; a `submit` token reads and submits. Iterate every route in the app against `ENDPOINT_SCOPES`
- [ ] File failures, table-driven: delete the file, `chmod 000`, add a malformed line → every request `503 auth_unavailable` with exactly one ERROR logged (capture with `caplog`); restore → service resumes with exactly one INFO. Revoke the last token → `401`, no ERROR
- [ ] Tokens never appear in logs: capture the access log during an authenticated request and assert the token string is absent
- [ ] `NoAuth`: all endpoints open

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: add token authentication with scopes` (includes Tasks 6.3–6.4)

---

### Task 6.6: `amoeba token add | list | revoke`
**Owner**: Junior AI
**Dependencies**: Task 6.5
**Effort**: 3
**Objective**: The operator interface to the token file (LLD CLI table).

**Steps**:
- [ ] Create `cli/token.py` and register the subcommand in `cli/main.py`. `add --principal NAME --scope read|submit`: no default for `--scope`; prints the new token and nothing else, once; refuses a principal that already has one. `list`: principal and scope, one per line, never hashes or tokens. `revoke --principal NAME`: removes the entry; unknown principal is a clear error
- [ ] Derive the scope choices from `TokenScope`, not a second list. The CLI imports `amoeba.serve.tokens`; no other module imports `amoeba.serve` except `cli/serve.py` and `cli/token.py` (update the layering test accordingly: `amoeba.serve` imports nothing from `amoeba.cli` or `amoeba.process`)
- [ ] The CLI resolves the supervisor directory as the other commands do (`AMOEBA_STORE_DIR` via the existing resolver)

**Success Criteria**:
- [ ] Committed together with the tests below

**Tests (same task)**:
- [ ] `tests/cli/test_token.py` using the CLI harness: add prints only the token; the file then holds only its hash; duplicate principal refused; `list` output contains no hash or token; `revoke` makes `TokenAuth` reject that token on the next call; missing `--scope` is a usage error
- [ ] Commit, e.g. `feat: add amoeba token commands`

---

### Task 6.7: Principal binding on submissions
**Owner**: Junior AI
**Dependencies**: Task 6.6
**Effort**: 2
**Objective**: When authenticated, `submitted_by` must equal the principal (LLD D6). Fallback if not ratified: log the principal, take `submitted_by` from the body.

**Steps**:
- [ ] In `serve/writes.py`, fill the Task 4.3 seam: `submitted_by` is still required in the body; if a principal is present and differs → `403 principal_mismatch`. With `NoAuth` there is no principal and no check
- [ ] Tests in `tests/serve/test_writes_auth.py`: matching principal → `202`; mismatch → `403 principal_mismatch` and nothing written to the inbox; `NoAuth` accepts any `submitted_by`; a `read` token posting → `403 insufficient_scope`

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: bind submitted_by to the authenticated principal`

---

### Task 6.8: Re-authenticate open streams at each heartbeat
**Owner**: Junior AI
**Dependencies**: Task 6.7
**Effort**: 3
**Objective**: Revocation takes effect on open streams within `heartbeat_seconds` (LLD D6).

**Steps**:
- [ ] Make the Task 5.4 heartbeat hook call the real authenticator: re-read the token file and re-check presence and scope sufficiency (`read`). On failure send one terminal event, `event: closed` with `data: {"code": "unauthenticated" | "insufficient_scope" | "auth_unavailable"}` (values are `ApiErrorCode` members, not retyped strings), then close the stream through `StreamWorker.close()`
- [ ] The check runs at every heartbeat tick whether or not events are flowing
- [ ] Tests in `tests/serve/test_stream_auth.py` (real server, `http.client`, small `heartbeat_seconds`): revoke the token → `closed` with `unauthenticated` within the bound; lower the principal's scope below `read` (rewrite the file) → `insufficient_scope`; break the file → every open stream gets `auth_unavailable`; thread count returns to zero after each; with `NoAuth` nothing is re-checked

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: re-check authentication on open streams`

---

### Task 6.9: `SERVE_REFUSED` and the startup refusal matrix
**Owner**: Junior AI
**Dependencies**: Task 6.8
**Effort**: 3
**Objective**: Decide, once, whether a configuration may start (LLD D6).

**Steps**:
- [ ] Add `SERVE_REFUSED = 12` to the `ExitCode` enum (definition in the 102 location found by `grep -n "class ExitCode"`). Fallback if not ratified: use `FAILURE` and skip the enum change
- [ ] Create `serve/startup.py` with one function `check_startup(settings, supervisor_dir)` that raises a `ServeRefusedError` naming the missing piece. Rules: non-loopback host with `auth=none` refused; non-loopback without `tls_cert`/`tls_key` refused (both required together; one without the other is refused for any host); `auth=tokens` with the token file missing, unreadable, malformed, or empty refused
- [ ] Tests (`tests/serve/test_startup.py`), table-driven over host × auth × TLS × token-file state: every refusal names its reason; loopback + `none` starts; loopback + `tokens` + valid file starts; `0.0.0.0` and `::` count as non-loopback

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: add serve startup refusal checks`

---

## Section 7: `amoeba serve` and Server Wiring

### Task 7.1: `server.run` with uvicorn
**Owner**: Junior AI
**Dependencies**: Task 6.9
**Effort**: 4
**Objective**: Run the app under uvicorn with the LLD's bounds (D5, D5a, D8).

**Steps**:
- [ ] Create `serve/server.py`: `run(settings, supervisor_dir)` calls `check_startup`, builds the authenticator from `settings.auth`, builds the app, and runs `uvicorn.Server` with `limit_concurrency=settings.max_connections`, `ssl_certfile`/`ssl_keyfile` from settings, `timeout_graceful_shutdown=settings.shutdown_grace_seconds`, and uvicorn's default `timeout_keep_alive`. Logging to stderr; foreground; no instance lock
- [ ] Shutdown: on `SIGINT`/`SIGTERM` set every stream's stop event (Task 5.4 hook) before uvicorn's graceful wait, so streams end within the grace bound
- [ ] Fallback if TLS-off-loopback is not ratified: drop only the TLS refusal in Task 6.9, and have `network-contract.md` warn about replay

**Success Criteria**:
- [ ] Commit with Task 7.3

---

### Task 7.2: `amoeba serve` command and flags
**Owner**: Junior AI
**Dependencies**: Task 7.1
**Effort**: 3
**Objective**: `amoeba serve [--host H] [--port P] [--auth none|tokens] [--tls-cert F --tls-key F]` plus a flag per remaining setting (LLD CLI table).

**Steps**:
- [ ] Create `cli/serve.py` and register it. Derive flags from the `ServeSettings` fields using the existing `cli/settings_flags.py` mechanism, so a new setting appears without a second list; defaults come from the dataclass, never retyped
- [ ] `ServeRefusedError` → print the reason to stderr and exit `ExitCode.SERVE_REFUSED`. Bad flag values are usage errors as elsewhere
- [ ] Update the process-boundary handler in `cli/main.py` as needed, without importing `amoeba.serve` outside `cli/serve.py` and `cli/token.py`

**Success Criteria**:
- [ ] Commit with Task 7.3

---

### Task 7.3: Subprocess tests for the server and CLI
**Owner**: Junior AI
**Dependencies**: Task 7.2
**Effort**: 4
**Objective**: The real command behaves as specified.

**Steps**:
- [ ] `tests/serve/test_serve_cli.py` (subprocess, `http.client`, ephemeral port): `amoeba serve` serves `/v1/listings` on `127.0.0.1`; `--host 0.0.0.0` without `--auth tokens` exits `12` with the reason on stderr; with tokens and no token file exits `12`; with tokens but no TLS exits `12`; settings flags change behavior (e.g. a small `--max-feed-streams`)
- [ ] TLS: generate a throwaway self-signed certificate in a temp directory at test time (no key committed), start with `--host 127.0.0.1 --tls-cert … --tls-key …`, and fetch over HTTPS with the cert trusted
- [ ] Graceful shutdown: `SIGTERM` with an open stream ends the stream and the process within `shutdown_grace_seconds` plus a margin; stream thread count reaches zero
- [ ] `max_connections`: past the limit uvicorn answers `503`, and the server keeps serving afterward
- [ ] Re-run the Task 5.5 stall test against the real command

**Success Criteria**:
- [ ] Tests pass; suite, `ruff`, `pyright` clean
- [ ] Commit, e.g. `feat: add amoeba serve command` (includes Tasks 7.1–7.2)

---

### Task 7.4: Record what uvicorn does with slow headers
**Owner**: Junior AI
**Dependencies**: Task 7.3
**Effort**: 2
**Objective**: Replace the LLD's assumption with an observed fact (D5a).

**Steps**:
- [ ] Open a raw socket to a running server and send request headers one byte at a time, slowly, for longer than any plausible header timeout. Observe whether uvicorn closes the connection, and when. Also confirm the connection counts against `max_connections`
- [ ] Record the result and the uvicorn version in the task notes. Do not change the server to compensate. If uvicorn has no header-phase timeout, Task 8.2 states that in `network-contract.md` and requires a TLS-terminating proxy in front of any non-loopback deployment
- [ ] Add a test only for what is observed and stable (e.g. the connection slot cap); do not add a timing test for behavior uvicorn lacks

**Success Criteria**:
- [ ] The observation is recorded with the version; suite clean
- [ ] Commit any test, e.g. `test: pin connection cap under slow headers`

---

## Section 8: End-to-End, Docs, and Final Validation

### Task 8.1: End-to-end and independence tests
**Owner**: Junior AI
**Dependencies**: Task 7.4
**Effort**: 5
**Objective**: The LLD Integration Requirements as subprocesses.

**Steps**:
- [ ] `tests/serve/test_network_end_to_end.py`: start the resident process and `amoeba serve` as subprocesses on a temp supervisor dir; create a project and seed a blocked node (reuse 106's `scripts/demo_detection.py` or its harness); follow the feed over SSE; read the `escalation` message to find the `blocked_state_id`; resolve the block with `POST /submissions` (a `resolution`); see the `node_status_changed` event; `kill -9` the resident process; submit again (status `pending`); restart it; see the event and `applied`, with the SSE stream never dropped
- [ ] Independence: `kill -9` the server → the resident process still runs (`amoeba status`), the store is unchanged, and `inspect` works; restart the server, `kill -9` the resident process → reads, the stream, and submissions keep working
- [ ] The transcript of the SSE stream equals `amoeba feed --project P` read from 0
- [ ] Authenticated variant: repeat the submit step with a `submit` token and `--auth tokens`

**Success Criteria**:
- [ ] Tests pass on three consecutive runs; suite clean
- [ ] Commit, e.g. `test: add network end-to-end and independence tests`

---

### Task 8.2: `docs/network-contract.md`
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 3
**Objective**: Enough for initiative 160 to build the bridge's client without reading code.

**Steps**:
- [ ] Create `docs/network-contract.md` (with the YAML frontmatter the docs convention requires): endpoint table with scopes, success and error statuses and codes (taken from the error table, not retyped by hand where a generator is practical); auth modes, token file format, scopes, principal binding; SSE event format, resume rules, heartbeat, terminal `closed` event; the `feed/page` vs `changes` listing distinction; retry guidance (always send your own `submission_id`); `ServeSettings` bounds; same-host statement (`amoeba serve` runs on the supervisor's machine; remote parts reach it over the network, not by mounting its directory); proxies (run `--auth tokens`; never trust source address); revocation latency (`heartbeat_seconds` for open streams); no secrets in payloads; the slow-header finding from Task 7.4; the Task 5.5 result; the same-machine trust note for `--auth none`
- [ ] Mark the doc as written from the final code, not the design; fix any mismatch with the LLD in the doc and note it for Task 8.4

**Success Criteria**:
- [ ] Every endpoint, code, and setting in the code appears in the doc (a test that diffs `ApiErrorCode` members and `ServeSettings` fields against the doc text is acceptable and preferred)
- [ ] Commit, e.g. `docs: add network contract`

---

### Task 8.3: Update the other contracts and `CHANGELOG.md`
**Owner**: Junior AI
**Dependencies**: Task 8.2
**Effort**: 2
**Objective**: Existing docs point to the new surface.

**Steps**:
- [ ] `inbox-contract.md`: update "Not a network service" to point at `network-contract.md`; add `inbox.locate`
- [ ] `feed-contract.md`: update the transport note; name `change_as_json`'s new location
- [ ] `process-contract.md`: confirm the Task 2.12 paragraph, and add that `amoeba serve` is a separate process that takes no lock
- [ ] `CHANGELOG.md`: add entries for the new dependencies, `amoeba serve`, `amoeba token`, `SERVE_REFUSED`, the registry move, and `inbox.locate`

**Success Criteria**:
- [ ] No contract still says there is no network surface; links resolve
- [ ] Commit, e.g. `docs: update contracts and changelog for the network api`

---

### Task 8.4: Verification walkthrough
**Owner**: Junior AI
**Dependencies**: Task 8.3
**Effort**: 3
**Objective**: Run the LLD's Verification Walkthrough against the real build and refine it with real output.

**Steps**:
- [ ] Run walkthrough steps 1–9 from the LLD in bash from the repo root. Record real output (trimmed) for each. Where the LLD's draft disagrees with reality, correct the LLD's walkthrough section only; do not edit other sections, and list every discrepancy for the PM
- [ ] Add `tests/serve tests/inspection` to the walkthrough's automatic step and confirm it passes

**Success Criteria**:
- [ ] All nine steps produce the stated results or the discrepancy is listed
- [ ] Commit, e.g. `docs: record network api walkthrough output`

---

### Task 8.5: Final validation and report
**Owner**: Junior AI
**Dependencies**: Task 8.4
**Effort**: 2
**Objective**: Confirm every Success Criterion and Technical Requirement, and report open points.

**Steps**:
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each; fix any failure at its cause
- [ ] Re-run the byte-comparison test: `amoeba inspect` output is unchanged from the Task 1.2 baseline
- [ ] Check Technical Requirements by test or grep: no re-export shims; no `argparse` in `amoeba.inspection`; `amoeba.serve` imports nothing from `amoeba.process` or `amoeba.cli`; the store imports nothing from `amoeba.serve`, `amoeba.inspection`, or `amoeba.feed`; every word list is defined once; the writer guard covers `amoeba.serve` and `amoeba.inspection`; files near 300 lines (list any larger)
- [ ] Walk the LLD Success Criteria list and name the test covering each; list any criterion without one and add the test
- [ ] Report to the PM: the five rulings and where any fallback was applied; the uvicorn `send` and slow-header findings; any departure from the LLD; any file over 300 lines

**Success Criteria**:
- [ ] All checks clean; every Success Criterion maps to a passing test
- [ ] Final commit on the slice branch, e.g. `chore: finalize slice 109 validation`
