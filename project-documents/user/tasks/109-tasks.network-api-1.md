---
docType: tasks
slice: network-api
project: amoeba
lld: user/slices/109-slice.network-api.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108]
projectState: Slices 101–104 are merged (store schema 5, inbox, verdicts and findings). In the working tree `src/amoeba/` holds only `cli`, `inbox`, `process`, `store`; there is no `amoeba.inspection`, `amoeba.feed`, or `amoeba.serve`. The listing registry (`LISTINGS`) lives in `cli/inspect.py` and takes `argparse.Namespace`. Slices 105–108 are planned and may not be merged when this file starts; 109 is hard-gated on them. This slice adds `amoeba serve`, the `amoeba.inspection` package, `amoeba.inbox.locate`, `amoeba.feed.change_as_json`, `amoeba token`, and `docs/network-contract.md`.
dateCreated: 20261008
dateUpdated: 20261008
status: not_started
---

## Context Summary

- Working on the **network-api** slice (109), the ninth slice of initiative 100.
- **Current state:** `inspect` listings are declared in one registry in `cli/inspect.py` (`Listing`, `ChoiceOption`, `ValueOption`, `LISTINGS`, `LISTINGS_BY_NAME`, `run_listing`); inbox and evidence row functions are in `cli/inspect_inbox.py` and `cli/inspect_evidence.py`. `amoeba.inbox.submit()` backs `amoeba submit`. `Store.open_read_only` exists. `tests/test_writer_guard.py` scans `src/amoeba/` by AST for read-write `Store.open`. `pyproject.toml` has one runtime dependency (pydantic).
- **Dependencies:** 101–104 through their contracts. **105–108 are a hard gate** (LLD "Prerequisites"): their listing modules must be in `amoeba.cli` before the registry move. **106** supplies `follow()`, `FeedSettings`, `change_head`, `read_transaction()`, and the `Change` JSON encoding.
- **What this slice delivers:** Group A, a no-behavior-change refactor (registry → `amoeba.inspection`, `ListingQuery`, `abbreviated_columns`, `change_as_json` → `amoeba.feed`), proven by byte comparison. Group B, the network surface: read endpoints, submission and status endpoints, the SSE feed and `feed/page`, bearer-token auth with scopes, `amoeba token`, `amoeba serve` with TLS and bounds, `docs/network-contract.md`, contract updates, `CHANGELOG.md`.
- **Not in this slice:** any other write endpoint, resident-process status (D7), browser support (CORS, cookies, token in query string), WebSocket, a client library, a cross-project stream, rate limiting, metrics, token expiry, mutual TLS, OpenAPI, per-kind or per-project authorization, paging of listings (LLD "Excluded").
- **Next planned slice:** 110 (contract proof), which runs `amoeba serve` as one more subprocess.
- **No load or benchmark task:** the LLD sets one latency bound, covered by a timing test (Task 5.7), and no throughput target.

**Branch:** all implementation happens on `109-slice.network-api`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging comes after the code review (Phase 7).

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/109-slice.network-api.md` at the named section (Technical Decisions D1–D8, Migration Plan, API Contracts, `ServeSettings`, Success Criteria). Exact signatures, field lists, defaults, error tables, and file formats are settled there. Keep every source file near 300 lines. Do not copy defaults into code: each `ServeSettings` default is defined once in `serve/settings.py`.

**PM ratification:** the LLD marks D2, D6 (TLS, principal binding, scopes), and `SERVE_REFUSED` (12) as pending PM ratification. Task 1.1 asks for rulings. Group A needs none of them. Where a ruling is "no", the LLD names a fallback; the gated tasks say which one applies.

**Commit cadence:** a commit never holds untested behavior. A task that says "committed with Task N.M" is committed together with its test task, which follows immediately; every other task commits on its own. Commit messages follow the semantic prefixes in the project CLAUDE.md. In Group A, a relocation commit is made only after the byte comparison (Task 1.2) and the full suite pass.

**Section map:** this file: 1 branch, gate, byte-comparison harness; 2 Group A (registry move, `ListingQuery`, `change_as_json`); 3 Group B skeleton and supervisor-level reads (Tasks 3.1–3.7). **File 2 (`...-2.md`):** 3 continued (project listings, Tasks 3.8–3.10); 4 `inbox.locate` and submission endpoints; 5 the feed. **File 3 (`...-3.md`):** 6 authentication and tokens; 7 `amoeba serve` and server wiring; 8 end-to-end, docs, final validation.

---

## Section 1: Branch, Gate, and Byte-Comparison Harness

### Task 1.1: Create the branch, run the gate, collect PM rulings
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 2
**Objective**: Work on the right branch, on top of 105–108, with a known baseline and the PM's rulings in hand.

**Steps**:
- [ ] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [ ] Create `109-slice.network-api` from the target; if it exists, switch to it
- [ ] **Gate (a):** confirm 105, 106, 107, and 108 are merged into the target. Check by file, not by branch name: `src/amoeba/store/feed_models.py` defines `ChangeKind` and a `follow` function is importable (106); the 105, 107, and 108 listing modules exist (find them with `ls src/amoeba/cli/inspect_*.py` and by reading the `LISTINGS` tuple in `cli/inspect.py`: it must include the 105, 106, 107, and 108 listings, e.g. `calibration` and `cf-snapshots`)
- [ ] **Gate (b):** confirm every listing's row functions are still in `amoeba.cli` (`cli/inspect*.py`), not already moved. If either (a) or (b) fails, stop and tell the PM. Do not proceed on an assumed order
- [ ] Write down for later tasks: the list of `cli/inspect_*.py` modules and the name of each listing in `LISTINGS`; where 106 put the `Change` → JSON function (expected `cli/feed.py`); the real names of `follow`, `FeedSettings`, `read_transaction`, and `change_head`
- [ ] Ask the PM for rulings and record each answer in your notes: D2 (`starlette` + `uvicorn`, `httpx` for tests); D6 TLS required off-loopback; D6 `submitted_by` must equal the principal; D6 `read`/`submit` scopes; `SERVE_REFUSED` (12). If D2 is not ratified, stop before Task 3.1; Group A is unaffected
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once. If any fail before changes, stop and tell the PM

**Success Criteria**:
- [ ] On the slice branch; gate (a) and (b) both pass
- [ ] PM rulings recorded (five answers); baseline suite, `ruff`, `pyright` clean
- [ ] No commit needed

---

### Task 1.2: Byte-comparison harness for every listing
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 3
**Objective**: A repeatable check that `amoeba inspect` output is unchanged by the refactor (LLD Migration Plan, Verification).

**Steps**:
- [ ] Add a test helper (e.g. `tests/inspection_snapshot.py`) that builds one seeded store dir exercising every registered listing: reuse the existing seeding helpers (`tests/cli_harness.py`, `tests/evidence_harness.py`, `tests/inbox_harness.py`, 106–108 harnesses) rather than writing new fixtures. Include at least one row for every listing, a blocked node, findings and changes with long content keys (so abbreviation shows in the table), and a second project
- [ ] The helper runs `amoeba inspect <name>` and `amoeba inspect <name> --json` for **every** entry in `LISTINGS` (iterate the registry, so later listings are covered), with each listing's options exercised where it has any, and returns `{(listing, form, options): stdout}`
- [ ] Write the baseline once, before any move, to `tests/fixtures/inspect_baseline/` (one file per key). Run the helper twice and confirm the two runs are identical (no timestamps or ids vary; if they do, fix the seeding to use fixed ids and times, not the comparison)
- [ ] Add `tests/test_inspect_byte_compare.py` that regenerates the output and asserts equality with the baseline files. A missing baseline file for a registered listing is a test failure, not a skip
- [ ] Add a short README note beside the baseline: captured before the 109 refactor from the pre-move code; regenerate only with PM approval

**Success Criteria**:
- [ ] The byte-comparison test passes on unmodified code and covers table and `--json` for every listing
- [ ] Deleting one baseline file makes the test fail
- [ ] Commit, e.g. `test: add byte-comparison baseline for inspect output`

**Files to Create**: `tests/inspection_snapshot.py`, `tests/test_inspect_byte_compare.py`, `tests/fixtures/inspect_baseline/`

---

## Section 2: Group A — The No-Behavior-Change Refactor

Order inside Group A, per the LLD: first relocate modules unchanged; then change the row signature one module at a time, running the byte comparison after each. No re-export shims: update every importer in the same commit.

### Task 2.1: Create `amoeba.inspection` and move the registry types
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 3
**Objective**: `Row`, `ChoiceOption`, `ValueOption`, `Listing`, `LISTINGS`, `LISTINGS_BY_NAME`, `PROJECTS_LISTING`, and the four core row functions live in `amoeba.inspection`, unchanged.

**Steps**:
- [ ] Create `src/amoeba/inspection/__init__.py`, `registry.py`, and `rows_core.py` per the LLD Component Structure. Move code verbatim (git move semantics, no rewrites). The core row functions (nodes, blocked, journal, projects) go to `rows_core.py`; the types and tuples go to `registry.py`
- [ ] Keep the row functions' `argparse.Namespace` parameter for now (it changes in Tasks 2.6–2.9). For this task only, `inspection` may import `argparse`; Task 2.10 removes it
- [ ] Leave `LISTINGS` entries for listings whose row modules have not moved yet importing from `amoeba.cli` temporarily; this is the only cross-layer import allowed and is gone by Task 2.5
- [ ] Update every importer in the same commit: `cli/inspect.py` (now argparse construction, `run_listing`, table printing), `cli/main.py`, and the tests that import the moved names
- [ ] Do not move `run_listing`'s `json.dumps` yet (Task 2.11)

**Success Criteria**:
- [ ] Full suite and the byte-comparison test pass; `ruff` and `pyright` clean
- [ ] `cli/inspect.py` no longer defines `Listing`, `LISTINGS`, or any row function
- [ ] Commit, e.g. `refactor: move listing registry types to amoeba.inspection`

**Files to Create**: `src/amoeba/inspection/__init__.py`, `registry.py`, `rows_core.py`
**Files to Modify**: `src/amoeba/cli/inspect.py`, `src/amoeba/cli/main.py`, affected tests

---

### Task 2.2: Move the inbox listings
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 2
**Objective**: `cli/inspect_inbox.py` → `inspection/rows_inbox.py`, unchanged.

**Steps**:
- [ ] Move the file; update the `LISTINGS` import and every importer (`tests/cli/test_submit.py`, `tests/test_cli_inspect.py`, others found by `grep -rn inspect_inbox`)

**Success Criteria**:
- [ ] Suite and byte comparison pass; no `inspect_inbox` reference remains
- [ ] Commit, e.g. `refactor: move inbox listings to amoeba.inspection`

---

### Task 2.3: Move the evidence listings
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 2
**Objective**: `cli/inspect_evidence.py` → `inspection/rows_evidence.py`, including `VerdictNotComparableError`.

**Steps**:
- [ ] Move the file; update importers, including `cli/main.py` (the boundary handler's `VerdictNotComparableError` import), `tests/cli/test_inspect_evidence.py`, and `tests/test_cli_inspect.py`

**Success Criteria**:
- [ ] Suite and byte comparison pass; no `inspect_evidence` reference remains
- [ ] Commit, e.g. `refactor: move evidence listings to amoeba.inspection`

---

### Task 2.4: Move the 106 feed listing module
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 1
**Objective**: 106's listing module (expected `cli/inspect_feed.py`; use the name recorded in Task 1.1) → `inspection/rows_feed.py`, unchanged.

**Steps**:
- [ ] Move it, update importers and 106's CLI tests for that listing

**Success Criteria**:
- [ ] Suite and byte comparison pass; no old-module reference remains
- [ ] Commit, e.g. `refactor: move feed listings to amoeba.inspection`

---

### Task 2.5: Move the 105, 107, and 108 listing modules
**Owner**: Junior AI
**Dependencies**: Task 2.4
**Effort**: 2
**Objective**: Every remaining `cli/inspect_*.py` row module (names from Task 1.1) moves to `inspection/rows_*.py`, one per source module.

**Steps**:
- [ ] Move each remaining module as its own sub-step, running the suite after each: the 105 module(s), the 107 module(s) (calibration, checks), the 108 module (`cf-watches`, `cf-snapshots`). Name destinations `rows_<topic>.py` to match the existing ones
- [ ] Update importers and the CLI tests those slices added. Remove the temporary `amoeba.cli` import from Task 2.1

**Success Criteria**:
- [ ] `ls src/amoeba/cli/inspect_*.py` shows only `inspect.py`; `grep -rn "amoeba.cli" src/amoeba/inspection` finds nothing
- [ ] Suite and byte comparison pass
- [ ] Commit, e.g. `refactor: move remaining listing modules to amoeba.inspection`

---

### Task 2.6: Implement `ListingQuery` and `ListingQueryError`
**Owner**: Junior AI
**Dependencies**: Task 2.5
**Effort**: 3
**Objective**: The typed, frozen query record that replaces `argparse.Namespace` in row functions (LLD D3).

**Steps**:
- [ ] Create `inspection/query.py`. `ListingQuery` is a frozen record: `project: str | None` plus option values keyed by option name. It carries its listing's declared options so accessors can check them
- [ ] Add accessors `value(name) -> str | None`, `choice(name) -> str | None`, `flag(name) -> bool`. Each raises `ListingQueryError` when `name` is not an option the listing declares **with that type** (flags/choice_options/value_options on `Listing` remain the only declaration)
- [ ] Add `query_from_namespace(listing, namespace)` (used by `cli/inspect.py`) that walks the listing's declared options and builds the query. Choice values are validated against `choices`; required value options must be present. Put `query_from_params` in the same module in Task 3.5, not now
- [ ] Share the validation between both builders in one private helper so Task 3.5 reuses it

**Success Criteria**:
- [ ] `ListingQuery` is immutable; `ListingQueryError` is defined once
- [ ] No module in `amoeba.inspection` has gained an `argparse` import (the builders take a plain mapping internally; `query_from_namespace` lives in `cli/inspect.py` and calls the shared helper)
- [ ] Commit with Task 2.7

**Files to Create**: `src/amoeba/inspection/query.py`

---

### Task 2.7: Tests for `ListingQuery`
**Owner**: Junior AI
**Dependencies**: Task 2.6
**Effort**: 2
**Objective**: Pin the accessor and validation rules.

**Steps**:
- [ ] Create `tests/inspection/__init__.py` and `tests/inspection/test_query.py`
- [ ] Cover: each accessor returns the supplied value; an accessor for an undeclared name raises `ListingQueryError`; an accessor used with the wrong type (e.g. `flag` on a value option) raises; a choice outside `choices` is rejected; a missing required value option is rejected; the record is frozen
- [ ] Iterate `LISTINGS` once: build a query with no options for every listing and assert no listing's declared options make the builder fail

**Success Criteria**:
- [ ] New tests pass; suite, `ruff`, `pyright` clean
- [ ] Commit, e.g. `feat: add ListingQuery for listing options` (includes Task 2.6)

---

### Task 2.8: Add `abbreviated_columns` and convert the core row functions
**Owner**: Junior AI
**Dependencies**: Task 2.7
**Effort**: 3
**Objective**: Core rows take `(store, ListingQuery)`; presentation truncation moves out of row functions (LLD D3).

**Steps**:
- [ ] Add `abbreviated_columns: tuple[str, ...]` to `Listing` (default empty). Only the CLI table printer shortens these columns
- [ ] Convert `rows_core.py` row functions from `args: argparse.Namespace` to `query: ListingQuery`, reading options only through the accessors. Update their `Listing` entries
- [ ] In `cli/inspect.py`, build the query with `query_from_namespace` and pass it. Rows always carry full values
- [ ] Update direct tests of these row functions to pass a `ListingQuery`; limit test edits to that

**Success Criteria**:
- [ ] Byte comparison passes for the core listings, table and `--json`; suite clean
- [ ] Commit, e.g. `refactor: pass ListingQuery to core row functions`

---

### Task 2.9: Convert row modules to `ListingQuery`, one module each
**Owner**: Junior AI
**Dependencies**: Task 2.8
**Effort**: 4
**Objective**: Every remaining row function stops depending on `argparse.Namespace`. Today `findings` and `changes` shorten the content `key` unless `--json`; that moves to `abbreviated_columns`.

**Steps** (run the suite and the byte comparison after **each** sub-step; commit each):
- [ ] 2.9a `rows_inbox.py`
- [ ] 2.9b `rows_evidence.py`: remove the `args.json` key truncation; set `abbreviated_columns` on `findings` and `changes` to the columns that were shortened (read the old code first; do not guess), and have the table printer apply it
- [ ] 2.9c `rows_feed.py` (106)
- [ ] 2.9d the 105 module(s)
- [ ] 2.9e the 107 module(s)
- [ ] 2.9f the 108 module
- [ ] For each, update direct row-function tests to pass a `ListingQuery`, and nothing else in the tests

**Success Criteria**:
- [ ] `grep -rn "args\.\|Namespace" src/amoeba/inspection` finds no use
- [ ] Byte comparison passes after every sub-step; suite clean
- [ ] Six commits, e.g. `refactor: pass ListingQuery to inbox row functions`

---

### Task 2.10: Add `encode_rows` and guard the layering
**Owner**: Junior AI
**Dependencies**: Task 2.9
**Effort**: 2
**Objective**: One JSON encoding of rows; `amoeba.inspection` is argparse-free and covered by the writer guard.

**Steps**:
- [ ] Add `encode_rows(rows)` to `inspection/registry.py`, returning exactly what `json.dumps(rows, default=str)` produced in `run_listing`; make `run_listing` call it
- [ ] Add a test that no module under `src/amoeba/inspection` imports `argparse` or `amoeba.cli` (AST scan, in the style of `test_writer_guard.py`)
- [ ] Update `tests/test_writer_guard.py`: the existing assertion naming `cli/inspect.py` now names the registry module; confirm `amoeba/inspection` is in the scanned set and permitted no read-write open
- [ ] Add a test: no module under `src/amoeba/store` imports `amoeba.inspection`, `amoeba.feed`, or `amoeba.serve`

**Success Criteria**:
- [ ] Byte comparison passes; new tests pass; suite clean
- [ ] Commit, e.g. `refactor: add encode_rows and layering tests for inspection`

---

### Task 2.11: Move `Change` → JSON to `amoeba.feed`
**Owner**: Junior AI
**Dependencies**: Task 2.10
**Effort**: 2
**Objective**: `change_as_json(change) -> dict` importable from `amoeba.feed` (LLD Migration Plan §2).

**Steps**:
- [ ] If 106 left the encoding in `cli/feed.py` (location noted in Task 1.1), move it to `src/amoeba/feed/encoding.py` and export it from `amoeba.feed`. If 106 already placed it in `amoeba.feed`, record that and make no move
- [ ] Update `cli/feed.py` to import it; update importers. No shims

**Success Criteria**:
- [ ] `amoeba feed`'s existing CLI tests pass unchanged; `amoeba.feed` exports `change_as_json`
- [ ] Commit, e.g. `refactor: move change_as_json to amoeba.feed`

---

### Task 2.12: Group A checkpoint
**Owner**: Junior AI
**Dependencies**: Task 2.11
**Effort**: 1
**Objective**: Group A is complete, reviewable on its own, before any `amoeba.serve` code.

**Steps**:
- [ ] Run the full suite, `ruff`, `pyright`, and the byte-comparison test once
- [ ] Confirm `grep -rn "inspect_inbox\|inspect_evidence" src tests` finds nothing and no re-export shim exists
- [ ] Update `process-contract.md`'s "Listings are declared in one registry" paragraph to name `amoeba.inspection` (LLD Migration Plan)

**Success Criteria**:
- [ ] All checks clean; `git status` clean after commit
- [ ] Commit, e.g. `docs: point listing registry paragraph at amoeba.inspection`

---

## Section 3: Group B Skeleton and Read Endpoints

Requires the D2 ruling from Task 1.1. If D2 was not ratified, stop here and tell the PM; the LLD names aiohttp as the fallback.

### Task 3.1: Add dependencies and test directory
**Owner**: Junior AI
**Dependencies**: Task 2.12
**Effort**: 1
**Objective**: Runtime `starlette` and `uvicorn` (plain, no `[standard]`); dev `httpx`.

**Steps**:
- [ ] Add them with `uv add starlette uvicorn` and `uv add --dev httpx`; versions are whatever is current, pinned in `uv.lock`. Do not hand-write version pins
- [ ] Create `tests/serve/__init__.py`
- [ ] Read the tool guides for these tools if present under `ai-project-guide/tool-guides/` (starlette, uvicorn); otherwise use the context7 MCP for Starlette `TestClient`, `StreamingResponse`, and uvicorn `Config`/`Server` (TLS, `limit_concurrency`, `timeout_graceful_shutdown`). Note any API that differs from the LLD's assumptions and tell the PM

**Success Criteria**:
- [ ] `uv run python -c "import starlette, uvicorn, httpx"` succeeds; suite unaffected
- [ ] Commit, e.g. `package: add starlette, uvicorn, and httpx`

---

### Task 3.2: `ServeSettings` and `is_loopback`
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 2
**Objective**: The only definition of each serve default (LLD `ServeSettings` table).

**Steps**:
- [ ] Create `serve/__init__.py` and `serve/settings.py`: frozen dataclass with every field and default from the LLD table; `AuthMode` (`StrEnum`: `none`, `tokens`). `store_busy_timeout_seconds` defaults to a reference to the store's `BUSY_TIMEOUT_SECONDS`, not a copied number
- [ ] Validate positive bounds in `__post_init__` and raise a clear error naming the field
- [ ] `is_loopback(host)`: true for an IP literal whose `ipaddress` form `is_loopback`, or the literal `localhost`; false for everything else including `0.0.0.0`, `::`, and any other name

**Success Criteria**:
- [ ] Commit with Task 3.3

---

### Task 3.3: Tests for settings and `is_loopback`
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 2
**Objective**: Pin defaults and loopback decisions.

**Steps**:
- [ ] `tests/serve/test_settings.py`: defaults equal the LLD table; `store_busy_timeout_seconds` equals the store constant; non-positive values raise
- [ ] Table-driven `is_loopback`: `127.0.0.1`, `127.0.0.2`, `::1`, `localhost` true; `0.0.0.0`, `::`, `192.168.1.5`, `example.com`, `""` false

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: add ServeSettings and is_loopback`

---

### Task 3.4: Error vocabulary and the one error table
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 3
**Objective**: `ApiErrorCode` (`StrEnum`) and the single exception → `(code, status)` table (LLD Patterns and Conventions, API Contracts error statuses).

**Steps**:
- [ ] Create `serve/errors.py`: `ApiErrorCode` with exactly the LLD's members; an `ApiError` exception carrying a code and message; the table mapping `validate_project_id` errors, `StoreError` subclasses (schema mismatch/unreadable → `store_unavailable`, `StoreBusyError` → `store_busy`), `VerdictNotFoundError`, `VerdictNotComparableError`, `ListingQueryError`, `InvalidSubmissionError`, `SubmissionWriteError` to codes and statuses
- [ ] Error body is `{"error": {"code", "message"}}` plus `reason` for `invalid_submission`. `Retry-After` header for `store_busy` and `too_many_streams`; `WWW-Authenticate: Bearer` for `unauthenticated`
- [ ] A Starlette exception handler turns table entries into responses; anything else is logged with `logger.exception` and returned as `500` with a generic message (process boundary, CLAUDE.md exception rule case c). Handlers raise; none builds an error response

**Success Criteria**:
- [ ] Statuses are chosen only in this table; commit with Task 3.5

---

### Task 3.5: `query_from_params`, the error-table test, and the app factory
**Owner**: Junior AI
**Dependencies**: Task 3.4
**Effort**: 3
**Objective**: Server-side query building and an app that returns structured errors.

**Steps**:
- [ ] Add `query_from_params(listing, project, params)` to `inspection/query.py` reusing the Task 2.6 helper. Flags parse `true`/`false` (case-insensitive); anything else is a `ListingQueryError`. An **unknown query parameter** raises `ListingQueryError` (server returns `400 invalid_query` naming it)
- [ ] Create `serve/app.py` with `build_app(supervisor_dir, settings, authenticator)` returning a Starlette app with the exception handler installed and routes mounted under `/v1`; at this point `authenticator` is a placeholder protocol call-site wired in Task 6.3. Until then, pass a no-op authenticator defined in `serve/auth.py` (`NoAuth`, real in Task 6.3)
- [ ] Tests (`tests/serve/test_errors.py`, `tests/inspection/test_query_params.py`): every table entry yields its documented status and code; an unmapped exception yields `500` with the generic message and logs a traceback; `?nod=x` is `invalid_query` naming `nod`; a bad choice value and a bad flag value are rejected

**Success Criteria**:
- [ ] Tests pass; `serve` imports nothing from `amoeba.process` or `amoeba.cli` (add an AST test)
- [ ] Commit, e.g. `feat: add serve error table, query_from_params, and app factory` (includes Task 3.4)

---

### Task 3.6: Listing discovery and supervisor-level listings
**Owner**: Junior AI
**Dependencies**: Task 3.5
**Effort**: 3
**Objective**: `GET /v1/listings` and `GET /v1/listings/{name}` (LLD API Contracts).

**Steps**:
- [ ] Create `serve/reads.py`. Discovery returns each listing's `name`, `scope` (`project` or `supervisor`), `columns`, and `options` (from the registry's own metadata: option names without `--`, type, choices). Build routes and responses from `LISTINGS`, never from a hand-kept list
- [ ] Supervisor listings (`projects`, `inbox`, and any other supervisor-scoped listing the registry declares) return `{"listing", "columns", "rows"}` using `encode_rows`; no `change_head`. Asking for a project-scoped name here, or an unknown name, is `unknown_listing`
- [ ] Row functions are sync; define endpoints as sync functions so Starlette runs them in its thread pool

**Success Criteria**:
- [ ] Commit with Task 3.7

---

### Task 3.7: Tests for discovery and supervisor listings
**Owner**: Junior AI
**Dependencies**: Task 3.6
**Effort**: 2
**Objective**: Discovery matches the registry; supervisor reads work.

**Steps**:
- [ ] `tests/serve/test_reads_supervisor.py` using `TestClient` on a seeded supervisor dir (use `tests/serve/conftest.py` for a shared `client` fixture and the Task 1.2 seeding helper)
- [ ] Discovery names every entry in `LISTINGS`; scope and columns match; unknown name → `404 unknown_listing`; project-scoped name at the supervisor path → `unknown_listing`
- [ ] With a token file present in `serve/`, `GET /v1/listings/projects` and `inspect projects` do not list `serve` (LLD Database / Storage Schema test). Creating a project named `serve` works with the token file untouched (this half is completed in Task 6.2 when the file exists; add the project-name half now)

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: add listing discovery and supervisor listing endpoints`
