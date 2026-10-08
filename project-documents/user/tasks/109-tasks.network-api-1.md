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
- **Load tier:** this slice adds concurrency and process boundaries (many streams, a stalled-client bound, a latency bound), so the Python rules require a load tier. `tests/load/` already exists, is excluded from the default suite by `--ignore`, and `ci.yml` already runs `uv run pytest tests/load` as its own gating step. Task 8.1c adds the serve load tests there; no workflow change is needed. No benchmark or throughput target is added (the LLD sets none).

**Branch:** all implementation happens on `109-slice.network-api`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging comes after the code review (Phase 7).

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/109-slice.network-api.md` at the named section (Technical Decisions D1–D8, Migration Plan, API Contracts, `ServeSettings`, Success Criteria). Exact signatures, field lists, defaults, error tables, and file formats are settled there. Keep every source file near 300 lines. Do not copy defaults into code: each `ServeSettings` default is defined once in `serve/settings.py`.

**PM ratification:** the LLD marks D2, D6 (TLS, principal binding, scopes), and `SERVE_REFUSED` (12) as pending PM ratification. Task 1.1 asks for rulings. Group A needs none of them. Where a ruling is "no", the LLD names a fallback; the gated tasks say which one applies.

**Commit cadence:** a commit never holds untested behavior. A task that says "committed with Task N.M" is committed together with its test task, which follows immediately; every other task commits on its own. Commit messages follow the semantic prefixes in the project CLAUDE.md. In Group A, a relocation commit is made only after the byte comparison (Task 1.2) and the full suite pass.

**Task numbers with letters (2.5a, 3.4a, 3.5a) are real tasks inserted to keep each commit tested; they are done in order, as listed.**

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
- [ ] **Gate (a):** confirm 105, 106, 107, and 108 are merged into the target. Check by file, not by branch name: `src/amoeba/store/feed_models.py` defines `ChangeKind` and a `follow` function is importable (106); each of those slices' listings is registered. For each of 105–108, open its slice design (`user/slices/10N-slice.*.md`), list the `inspect` listing names it defines, and confirm every one appears in the `LISTINGS` tuple in `cli/inspect.py`. A listing named in a design but absent from `LISTINGS` fails the gate
- [ ] **Gate (b):** confirm every listing's row functions are still in `amoeba.cli` (`cli/inspect*.py`), not already moved. If either (a) or (b) fails, stop and tell the PM. Do not proceed on an assumed order
- [ ] Locate the existing durable-write routine (write to a temp file, fsync, atomic rename) that 103 and 106 use for inbox files and sidecars: search `src/amoeba/inbox` and `src/amoeba/store` for the routine that does those three steps. Record its name and module. If none exists, stop and tell the PM; Task 6.1 reuses it and must not write a second one
- [ ] Write down for later tasks: the list of `cli/inspect_*.py` modules and the name of each listing in `LISTINGS`; where 106 put the `Change` → JSON function (search `src/amoeba` for the code that builds the `amoeba feed` output line; if you cannot find one function that does it, stop and tell the PM); the real names of `follow`, `FeedSettings`, `read_transaction`, and `change_head`
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
- [ ] Add a test helper module `tests/inspection_snapshot.py` exposing two public functions: `seed_all_listings(store_dir)`, which builds one seeded store dir (Group B tests import it as their shared seeded store), and `capture_inspect_output(store_dir)`, which does the capture below. The seeded dir exercising every registered listing: reuse the existing seeding helpers (`tests/cli_harness.py`, `tests/evidence_harness.py`, `tests/inbox_harness.py`, 106–108 harnesses) rather than writing new fixtures. Include at least one row for every listing, a blocked node, findings and changes with long content keys (so abbreviation shows in the table), and a second project
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

### Task 2.1: Create `amoeba.inspection`; move the listing types and core rows
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 3
**Objective**: `Row`, `ChoiceOption`, `ValueOption`, `Listing`, and the four core row functions live in `amoeba.inspection`, unchanged. The `LISTINGS` tuple stays in `cli/inspect.py` until Task 2.5d, so imports only ever point from `cli` to `inspection`.

**Steps**:
- [ ] Create `src/amoeba/inspection/__init__.py`, `types.py`, and `rows_core.py`. `types.py` holds `Row`, `ChoiceOption`, `ValueOption`, and `Listing`. **They do not go in `registry.py`:** `registry.py` will import every row module to build `LISTINGS`, and the row modules import these types, so defining the types in `registry.py` would be an import cycle. `registry.py` is created in Task 2.5d. This differs from the LLD's Component Structure (which lists the types under `registry.py`); report it to the PM in Task 8.5
- [ ] Move code verbatim (git move semantics, no rewrites). Core row functions (nodes, blocked, journal, projects) go to `rows_core.py`
- [ ] Leave `LISTINGS`, `LISTINGS_BY_NAME`, `PROJECTS_LISTING`, and `run_listing` in `cli/inspect.py` for now; they import from `amoeba.inspection`. No module in `amoeba.inspection` may import `amoeba.cli`
- [ ] Row functions keep their `argparse.Namespace` parameter for now (changed in Tasks 2.8–2.9). `inspection` may import `argparse` until Task 2.10
- [ ] Update every importer in the same commit (`cli/inspect*.py`, `cli/main.py`, and tests that import the moved names). Do not move `run_listing`'s `json.dumps` yet (Task 2.10)

**Success Criteria**:
- [ ] Full suite and the byte-comparison test pass; `ruff` and `pyright` clean
- [ ] `grep -rn "amoeba.cli" src/amoeba/inspection` finds nothing
- [ ] Commit, e.g. `refactor: move listing types to amoeba.inspection`

**Files to Create**: `src/amoeba/inspection/__init__.py`, `types.py`, `rows_core.py`
**Files to Modify**: `src/amoeba/cli/inspect.py`, other `cli/inspect_*.py`, `src/amoeba/cli/main.py`, affected tests

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
**Objective**: 106's listing module (the name recorded in Task 1.1) → `inspection/rows_feed.py`, unchanged.

**Steps**:
- [ ] Move it, update importers and 106's CLI tests for that listing

**Success Criteria**:
- [ ] Suite and byte comparison pass; no old-module reference remains
- [ ] Commit, e.g. `refactor: move feed listings to amoeba.inspection`

---

### Task 2.5a: Move the 105 listing module(s)
**Owner**: Junior AI
**Dependencies**: Task 2.4
**Effort**: 1
**Objective**: Each 105 `cli/inspect_*.py` module (names from Task 1.1) → `inspection/rows_<topic>.py`, unchanged.

**Steps**:
- [ ] For each 105 module, as its own sub-step (2.5a-1, 2.5a-2, …): move it, update importers and the CLI tests that slice added, run the suite and the byte comparison, commit

**Success Criteria**:
- [ ] No old-module reference remains; suite and byte comparison pass after each sub-step
- [ ] One commit per module, e.g. `refactor: move parser listings to amoeba.inspection`

---

### Task 2.5b: Move the 107 listing module(s)
**Owner**: Junior AI
**Dependencies**: Task 2.5a
**Effort**: 1
**Objective**: As Task 2.5a, for the 107 modules named in Task 1.1.

**Steps**:
- [ ] For each 107 module, as its own sub-step: move it, update importers and tests, run the suite and the byte comparison, commit

**Success Criteria**:
- [ ] No old-module reference remains; suite and byte comparison pass after each sub-step
- [ ] One commit per module

---

### Task 2.5c: Move the 108 listing module(s)
**Owner**: Junior AI
**Dependencies**: Task 2.5b
**Effort**: 1
**Objective**: As Task 2.5a, for the 108 modules named in Task 1.1.

**Steps**:
- [ ] For each 108 module, as its own sub-step: move it, update importers and tests, run the suite and the byte comparison, commit

**Success Criteria**:
- [ ] `ls src/amoeba/cli/inspect_*.py` shows only `inspect.py`; suite and byte comparison pass
- [ ] One commit per module

---

### Task 2.5d: Move `LISTINGS` into the registry
**Owner**: Junior AI
**Dependencies**: Task 2.5c
**Effort**: 2
**Objective**: Now that every row module is in `amoeba.inspection`, `LISTINGS`, `LISTINGS_BY_NAME`, and `PROJECTS_LISTING` move to a new `inspection/registry.py`.

**Steps**:
- [ ] Move the three names verbatim into `registry.py`, which imports the `rows_*` modules and `types.py`. Row modules import only `types.py` (Task 2.1), so there is no cycle. Nothing under `inspection` may import `registry.py` except `query.py` consumers and the CLI/server
- [ ] `cli/inspect.py` imports `LISTINGS` and `LISTINGS_BY_NAME` from `amoeba.inspection`; update all importers, including the test that pins the listing set

**Success Criteria**:
- [ ] `grep -rn "amoeba.cli" src/amoeba/inspection` finds nothing; `cli/inspect.py` defines no listing
- [ ] Suite and byte comparison pass
- [ ] Commit, e.g. `refactor: move LISTINGS into amoeba.inspection registry`

---

### Task 2.6: Implement `ListingQuery`, `ListingQueryError`, and `build_query`
**Owner**: Junior AI
**Dependencies**: Task 2.5d
**Effort**: 3
**Objective**: The typed, frozen query record that replaces `argparse.Namespace` in row functions (LLD D3), with one public validating builder.

**Steps**:
- [ ] Create `inspection/query.py`. `ListingQuery` is a frozen record: `project: str | None` plus option values keyed by option name. It carries its listing's declared options so accessors can check them
- [ ] Add accessors `value(name) -> str | None`, `choice(name) -> str | None`, `flag(name) -> bool`. Each raises `ListingQueryError` when `name` is not an option the listing declares **with that type** (flags/choice_options/value_options on `Listing` remain the only declaration)
- [ ] Add the public `build_query(listing, project, raw: Mapping[str, str | bool | None]) -> ListingQuery`. It walks the listing's declared options, checks choice values against `choices`, requires required value options, and parses flags. It is the one validation both entry points call; it imports no `argparse`
- [ ] Add `query_from_namespace(listing, namespace)` in **`cli/inspect.py`** (it is the only place that may see a `Namespace`): it extracts each declared option's value from the namespace and calls `build_query`. `query_from_params` is added to `inspection/query.py` in Task 3.5 and calls `build_query` too
- [ ] **Intermediate state of `run_listing`:** add a temporary boolean field `uses_query` to `Listing`, default `False`. `run_listing` passes a `ListingQuery` (via `query_from_namespace`) to a listing whose `uses_query` is true and the raw `Namespace` to the rest. Tasks 2.8 and 2.9 set it to true as each module converts; Task 2.10 deletes the field once every listing is converted

**Success Criteria**:
- [ ] `ListingQuery` is immutable; `ListingQueryError` and `build_query` are defined once; no `argparse` import under `amoeba.inspection`
- [ ] Suite and byte comparison still pass with every listing at `uses_query = False`
- [ ] Commit with Task 2.7

**Files to Create**: `src/amoeba/inspection/query.py`

---

### Task 2.7: Tests for `ListingQuery`
**Owner**: Junior AI
**Dependencies**: Task 2.6
**Effort**: 2
**Objective**: Pin the accessor and `build_query` validation rules.

**Steps**:
- [ ] Create `tests/inspection/__init__.py` and `tests/inspection/test_query.py`
- [ ] Cover: each accessor returns the supplied value; an accessor for an undeclared name raises `ListingQueryError`; an accessor used with the wrong type (e.g. `flag` on a value option) raises; a choice outside `choices` is rejected; a missing required value option is rejected; the record is frozen
- [ ] Iterate `LISTINGS` once: call `build_query` with no options for every listing and assert none fails unless it declares a required option

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
- [ ] Convert `rows_core.py` row functions from `args: argparse.Namespace` to `query: ListingQuery`, reading options only through the accessors. Update their `Listing` entries and set `uses_query = True` on them
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
- [ ] 2.9a `rows_inbox.py` (each lettered sub-step is its own commit)
- [ ] 2.9b `rows_evidence.py`: remove the `args.json` key truncation; set `abbreviated_columns` on `findings` and `changes` to the columns that were shortened (read the old code first; do not guess), and have the table printer apply it
- [ ] 2.9c `rows_feed.py` (106)
- [ ] 2.9d the 105 module(s), one commit each
- [ ] 2.9e the 107 module(s), one commit each
- [ ] 2.9f the 108 module(s), one commit each
- [ ] For each module, set `uses_query = True` on its listings in the same commit
- [ ] For each, update direct row-function tests to pass a `ListingQuery`, and nothing else in the tests

**Success Criteria**:
- [ ] `grep -rn "args\.\|Namespace" src/amoeba/inspection` finds no use; every `Listing` has `uses_query = True`
- [ ] Byte comparison passes after every sub-step; suite clean
- [ ] One commit per module, e.g. `refactor: pass ListingQuery to inbox row functions`

---

### Task 2.10: Add `encode_rows` and guard the layering
**Owner**: Junior AI
**Dependencies**: Task 2.9
**Effort**: 2
**Objective**: One JSON encoding of rows; `amoeba.inspection` is argparse-free and covered by the writer guard.

**Steps**:
- [ ] Delete the temporary `uses_query` field and make `run_listing` always build a `ListingQuery`; `grep -rn uses_query src tests` finds nothing
- [ ] Add `encode_rows(rows)` to `inspection/registry.py`, returning exactly what `json.dumps(rows, default=str)` produced in `run_listing`; make `run_listing` call it
- [ ] The LLD lists `read_listing()` beside `encode_rows()` in `registry.py`. Add it only as an extraction of the step `run_listing` already performs (call the listing's row function with a store and a `ListingQuery`, return the rows) so the CLI and Task 3.8 share it. If `run_listing` has no such separable step, do not invent one: tell the PM the LLD name has no counterpart and leave it out
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
- [ ] If 106 left the encoding in the CLI package (location noted in Task 1.1), move it to `src/amoeba/feed/encoding.py` and export it from `amoeba.feed`. If 106 already placed it in `amoeba.feed`, record that and make no move
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
**Objective**: `ApiErrorCode` (`StrEnum`) and the single exception → `(code, status)` table (LLD Patterns and Conventions, API Contracts "Error statuses").

**Steps**:
- [ ] Create `serve/errors.py`: `ApiErrorCode` with exactly the LLD's members, and an `ApiError` exception carrying a code and message
- [ ] The table has two parts, both in this file. **Code → status** (from the LLD's error-status table): `invalid_project_id`, `invalid_query` → 400; `unauthenticated` → 401; `insufficient_scope`, `principal_mismatch` → 403; `unknown_project`, `unknown_listing`, `not_found`, `unknown_submission` → 404; `request_timeout` → 408; `not_comparable` → 409; `request_too_large`, `listing_too_large` → 413; `invalid_submission` → 422; `auth_unavailable`, `store_unavailable`, `store_busy`, `submission_write_failed`, `too_many_streams` → 503. Define this mapping once as data keyed by `ApiErrorCode`; a test (Task 3.4a) checks every member has a status
- [ ] **Exception → code**: `validate_project_id` errors → `invalid_project_id`; `ListingQueryError` → `invalid_query`; `VerdictNotFoundError` → `not_found`; `VerdictNotComparableError` → `not_comparable`; `StoreBusyError` → `store_busy`; other `StoreError` subclasses for schema mismatch or an unreadable store → `store_unavailable`; `InvalidSubmissionError` → `invalid_submission`; `SubmissionWriteError` → `submission_write_failed`. Read the 101 `StoreError` hierarchy first and map each subclass explicitly; an unmapped subclass falls through to the 500 path, not to a guessed code
- [ ] Error body is `{"error": {"code", "message"}}` plus `reason` for `invalid_submission`. Headers: `Retry-After` for `store_busy` and `too_many_streams`; `WWW-Authenticate: Bearer` for `unauthenticated`
- [ ] A Starlette exception handler turns table entries into responses; anything else is logged with `logger.exception` and returned as `500` with a generic message (process boundary, CLAUDE.md exception rule case c). Handlers raise; none builds an error response

**Success Criteria**:
- [ ] Statuses are chosen only in this table
- [ ] Commit with Task 3.4a

---

### Task 3.4a: Tests for the error table
**Owner**: Junior AI
**Dependencies**: Task 3.4
**Effort**: 2
**Objective**: Pin every mapping.

**Steps**:
- [ ] `tests/serve/test_errors.py`: build a minimal Starlette app with the handler and routes that raise each mapped exception. Every `ApiErrorCode` member has a status; every mapped exception yields its documented status, code, and headers; `invalid_submission` carries `reason`; an unmapped exception yields `500` with the generic message and a logged traceback

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: add serve error table` (includes Task 3.4)

---

### Task 3.5: `query_from_params`
**Owner**: Junior AI
**Dependencies**: Task 3.4a
**Effort**: 2
**Objective**: Server-side query building from URL parameters (LLD D3).

**Steps**:
- [ ] Add `query_from_params(listing, project, params)` to `inspection/query.py`. It first rejects any **unknown parameter** with a `ListingQueryError` naming it (the server returns `400 invalid_query`), then calls the public `build_query` from Task 2.6. Flags accept `true`/`false` (case-insensitive); anything else is a `ListingQueryError`
- [ ] Tests in `tests/inspection/test_query_params.py`: `nod=x` is rejected naming `nod`; a bad choice value and a bad flag value are rejected; a valid value, choice, and flag each build the expected query; iterate `LISTINGS` and build a no-parameter query for each

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: add query_from_params`

---

### Task 3.5a: App factory, authenticator seam, and route wiring
**Owner**: Junior AI
**Dependencies**: Task 3.5
**Effort**: 3
**Objective**: `build_app` exists, the authenticator seam can express a per-endpoint scope, and every endpoint is registered through one helper that enforces it, before any endpoint is written.

**Steps**:
- [ ] Create `serve/tokens.py` containing only `TokenScope` (`StrEnum`: `read`, `submit`) for now; Task 6.1 adds the file format to the same module
- [ ] In `serve/auth.py` define `Principal` (frozen: name, scope); the `Authenticator` protocol with `authenticate(headers) -> Principal | None` and `authorize(principal, required_scope: TokenScope) -> ApiErrorCode | None` (returns the denial code, or `None` when allowed); `NoAuth` (`authenticate` returns `None`, `authorize` always returns `None`); and the `ENDPOINT_SCOPES` table (route name → `TokenScope`), empty for now. Task 6.3 adds `TokenAuth` without changing these signatures
- [ ] In `serve/app.py` add `build_app(supervisor_dir, settings, authenticator)` and one registration helper `add_route(app, name, path, methods, endpoint)`. The helper looks up the route's scope in `ENDPOINT_SCOPES[name]` (a missing entry raises at startup), and wraps the endpoint so it runs `authenticate`, then `authorize(principal, scope)`, and raises `ApiError` with the returned code before the handler runs. **Every endpoint task from 3.6 on registers through `add_route` and adds its row to `ENDPOINT_SCOPES`**
- [ ] Add `amoeba/serve` to `tests/test_writer_guard.py`'s scanned set now (no module permitted a read-write open), so every later `serve` module is covered from its first commit
- [ ] Add an AST test: `amoeba.serve` imports nothing from `amoeba.process` or `amoeba.cli`
- [ ] Tests (`tests/serve/test_app.py`): an unknown path returns the structured `404` body; registering a route with no `ENDPOINT_SCOPES` row fails at startup; a stub authenticator that denies produces its code's status before the handler runs, and one that allows runs the handler; `NoAuth` allows everything

**Success Criteria**:
- [ ] Tests pass; layering and writer-guard tests pass; suite clean
- [ ] Commit, e.g. `feat: add serve app factory and authenticator seam`

---

### Task 3.6: Listing discovery and supervisor-level listings
**Owner**: Junior AI
**Dependencies**: Task 3.5a
**Effort**: 3
**Objective**: `GET /v1/listings` and `GET /v1/listings/{name}` (LLD API Contracts).

**Steps**:
- [ ] Register through `add_route` (Task 3.5a) with a `ENDPOINT_SCOPES` row of `read`. Create `serve/reads.py`. Discovery returns each listing's `name`, `scope` (`project` or `supervisor`), `columns`, and `options` (from the registry's own metadata: option names without `--`, type, choices). Build routes and responses from `LISTINGS`, never from a hand-kept list
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
- [ ] `tests/serve/test_reads_supervisor.py` using `TestClient` on a seeded supervisor dir (use `tests/serve/conftest.py` for a shared `client` fixture built on `seed_all_listings` from `tests/inspection_snapshot.py`, Task 1.2)
- [ ] Discovery names every entry in `LISTINGS`; scope and columns match; unknown name → `404 unknown_listing`; project-scoped name at the supervisor path → `unknown_listing`
- [ ] With a token file present in `serve/`, `GET /v1/listings/projects` and `inspect projects` do not list `serve` (LLD Database / Storage Schema test). Creating a project named `serve` works with the token file untouched (this half is completed in Task 6.2 when the file exists; add the project-name half now)

**Success Criteria**:
- [ ] Tests pass; suite clean
- [ ] Commit, e.g. `feat: add listing discovery and supervisor listing endpoints`
