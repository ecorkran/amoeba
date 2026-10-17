---
docType: tasks
slice: network-api
project: amoeba
lld: user/slices/109-slice.network-api.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108]
projectState: Slices 101–108 are merged (store schema 8, listing registry in `cli/inspect.py` with siblings `inspect_inbox.py`, `inspect_evidence.py`, `inspect_feed.py`, `inspect_checks.py`, `inspect_cf.py`; `inbox.submit()`; 106's `follow()` and `Change`; `ExitCode` up to 12). No `amoeba.inspection`, `amoeba.serve`, `read_transaction()`, `change_head()`, or HTTP dependency exists. This slice moves the listings into `amoeba.inspection`, adds the two read-only store methods, and adds `amoeba serve` (Starlette + uvicorn) with reads, submissions, an SSE feed, bind policy, and token auth.
dateCreated: 20261017
dateUpdated: 20261017
status: not_started
---

## Context Summary (File 1 of 3)

- Working on the **network-api** slice (109), the ninth slice of initiative 100.
- **Current state (verified against the code, 20261017):**
  - 107 and 108 are merged: `inspect checks`, `inspect calibration`, `inspect cf-links`, `inspect cf-snapshots` exist. The LLD's Migration Plan table matches the merged code; module names are as the LLD states.
  - Every row function has signature `rows(store, args: argparse.Namespace)` and reads these attributes: `args.project` (all); `args.unresolved` (journal); `args.channel` (messages); `args.node`, `args.judge_invocation_id` (verdicts); `args.node`, `args.json` (findings); `args.verdict`, `args.json` (changes); `args.node` (checks); `args.outcome` (detections).
  - `Listing.flags` is a tuple of `(flag, help)` pairs, not an option type. `ChoiceOption`/`ValueOption` carry `flag`, not `name`. `Listing.requires_project` is a property derived from which row function is set.
  - `cli/main.py` builds the inspect parser (`_add_inspect_parser`) and imports `VerdictNotComparableError` from `cli/inspect_evidence.py`.
  - `run_listing` prints JSON with `json.dumps(rows, indent=2, default=str)`. The server's rows must serialize the same way (`default=str`) for parity.
  - `discover_project_ids` is in `process/supervisor.py`; consumers are `cli/inspect.py`, `process/project_stores.py`, `tests/process/test_project_stores.py`.
  - `change_line` is in `cli/feed.py`, used only there.
  - 103's id rule is `paths.validate_project_id` (raises `ValueError`). `paths.project_store_path` does **not** validate.
  - `Store.open_read_only` raises `StorePermissionError` both for "no store exists" and for "cannot read". The server tells them apart with an existence check before opening (Task 5.3).
  - Connections use `isolation_level="DEFERRED"`; Python's `sqlite3` does not open a transaction for a `SELECT`, so `read_transaction()` must issue `BEGIN` itself (Task 3.1).
  - `FeedOperations` (`store/feed.py`) is the feed mixin of the one `Store` class.
  - `tests/test_cli_inspect.py` (496 lines) has a `populated` fixture that seeds a row for every listing, including one pending inbox file.
  - `SINGLE_DEFINITION_MODULES` in `tests/test_import_boundaries.py` lists `cli/inspect_feed.py`.
  - No contract doc references the moved module paths (grep, 20261017).
- **Dependencies:** 101–108 through their contracts (LLD "Prerequisites", "Interfaces Required").
- **What this slice delivers:** see the LLD "Overview" and "Technical Scope".
- **Next planned slice:** 110 (contract proof and hardening).

**Branch:** all implementation happens on `109-slice.network-api`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges; merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/109-slice.network-api.md` at the named section (D1–D8, "Migration Plan", "API Contracts", "Data Flow"). Keep every new source file near 300 lines.

**Commit cadence:** a commit never holds untested behavior or a red suite. A task that says "committed with Task N.M" is committed together with that later task; every other task commits on its own.

**Tool knowledge:** there are no tool guides for Starlette, uvicorn, anyio, or httpx in `ai-project-guide/tool-guides/`. Use the context7 MCP for their current documentation, then the web. Where a task names a library parameter, confirm it in the docs for the installed version before using it; if it does not exist, stop and tell the PM.

**Open item for the PM (gates Task 8.1 only):** the LLD says `ServeRefusedError` is "mapped to the exit code in `cli/main.py`", and also that "`amoeba.cli.serve` is the only module that imports `amoeba.serve`". Both cannot hold. Recommendation: `cli/serve.py`'s `run_serve` catches `ServeRefusedError`, prints it, and returns `ExitCode.SERVE_REFUSED`; `ExitCode` stays defined in `cli/main.py`. Tasks 8.1–8.2 assume this.

**Task-level additions to the LLD:**
- `inspection/listing.py` holds the registry's types (`Row`, `ListingScope`, the option classes, `ListingRequest`, `Listing`) and the shared `NODE_OPTION`; `inspection/__init__.py` holds the registry and `read_listing`. Reason: the row modules need the option objects at runtime, and the package `__init__` imports the row modules, so defining the types in `__init__` would be an import cycle.
- `FlagOption`, a typed replacement for the `(flag, help)` pairs, so flags gain a `name` like the other options (LLD "What changes shape").
- `tests/inspection_harness.py`, the `populated` seeding extracted from `tests/test_cli_inspect.py`, so the baseline capture and the server parity test use one seeded store.
- The guard order in Task 5.2 and the exception-to-code mapping in Task 4.5 are task-level choices; change them only with the PM.
- In `serve/errors.py`, `ApiError` (an exception carrying an `ApiErrorCode` and detail) and one status-by-code mapping, because several codes (`missing_project`, `invalid_cursor`, …) come from no store exception (LLD D8).

**Section map.** This file: 1–3. File 2: 4–6. File 3: 7–9. In full: 1 baseline and seeded harness; 2 migration to `amoeba.inspection`; 3 store amendment and `as_of_seq`; 4 serve foundations (dependencies, settings, policy, errors); 5 the app, auth, and reads; 6 submissions; 7 the stream; 8 `amoeba serve` in the CLI; 9 smoke, load, docs, validation.

---

## Section 1: Baseline and Seeded Harness

### Task 1.1: Create the branch and record the starting state
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 1
**Objective**: Work on the right branch from a clean baseline, with 107 and 108 confirmed merged.

**Steps**:
- [ ] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [ ] Confirm `uv run amoeba inspect checks --help` and `uv run amoeba inspect cf-snapshots --help` succeed. If not, stop and tell the PM (LLD "Prerequisites")
- [ ] Create `109-slice.network-api` from the target; if it exists, switch to it
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each. If any fails before changes, stop and tell the PM

**Success Criteria**:
- [ ] On the slice branch; baseline suite, `ruff`, and `pyright` clean
- [ ] No commit needed

---

### Task 1.2: Extract the seeded-store harness
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 2
**Objective**: One function that seeds a supervisor directory with at least one row for every listing, usable from tests and from a plain script.

**Steps**:
- [ ] Create `tests/inspection_harness.py`. Move the body of `tests/test_cli_inspect.py`'s `populated` fixture into `seed_every_listing(supervisor_dir: Path) -> SeededStore`, where `SeededStore` is a frozen dataclass holding the project id and the ids a listing option needs (the node id, the verdict id `changes` takes, the judge invocation id)
- [ ] Move the constants the seeding uses (`PROJECT`, `_FIXTURE_VERDICT`, …) with it; `test_cli_inspect.py` imports them
- [ ] Keep `populated` as a thin fixture calling `seed_every_listing`
- [ ] Add a test in `tests/test_cli_inspect.py` (if one does not already assert it) that every listing in `LISTINGS` returns at least one row from the seeded store with `--json`

**Success Criteria**:
- [ ] `uv run pytest tests/test_cli_inspect.py` passes, with no test removed
- [ ] `tests/test_cli_inspect.py` is shorter by the moved seeding
- [ ] Commit, e.g. `test: extract shared seeded-store harness for listings`

**Files to Create**: `tests/inspection_harness.py`
**Files to Modify**: `tests/test_cli_inspect.py`

---

### Task 1.3: Capture the baseline `inspect` output
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 2
**Objective**: A fixed seeded store and the exact CLI output against it, so Task 2.8 can prove the migration changed nothing (LLD "Behavior preserved").

**Steps**:
- [ ] Choose a scratch directory outside the repo, e.g. `BASE="$(mktemp -d)"`, and record its path in the task notes. It must survive until Task 2.8
- [ ] Seed `"$BASE/store"` once with `seed_every_listing`, from a throwaway script kept outside the repo (put `tests/` on `sys.path`). Never seed again: ids and timestamps differ per seeding
- [ ] With `AMOEBA_STORE_DIR="$BASE/store"`, write into `"$BASE/before/"` one file per command: `inspect --help`; for every listing, `inspect <name> --help`, the table form, and `--json`; and for each declared option, one run exercising it (each flag set, each choice option with one choice, each value option with the seeded id)
- [ ] Generate the command list from the registry (iterate `LISTINGS`), not by hand, so no listing is missed. Keep the capture script with the scratch directory for reuse in Task 2.8

**Success Criteria**:
- [ ] `"$BASE/before/"` holds a non-empty file for every listing and every option run; no file contains a traceback
- [ ] No commit (nothing in the repo changes)

---

## Section 2: Migration to `amoeba.inspection` (no new behavior)

### Task 2.1: Add the registry types
**Owner**: Junior AI
**Dependencies**: Task 1.3
**Effort**: 2
**Objective**: The typed request and option model the row functions will take (LLD "What changes shape").

**Steps**:
- [ ] Create `src/amoeba/inspection/listing.py` with:
  - `Row` (moved type alias), and `ListingScope(StrEnum)` with `PROJECT = "project"`, `SUPERVISOR = "supervisor"`
  - `FlagOption`, `ChoiceOption`, `ValueOption`: frozen dataclasses with a `name` field (a Python identifier, e.g. `judge_invocation_id`) and their existing fields except `flag`. `flag` becomes a property: `"--" + name.replace("_", "-")`
  - `ListingRequest`: frozen; `project_id: str | None`, `options: Mapping[str, str | bool | None]` keyed by option `name`, `compact: bool`; method `option(opt) -> str | bool | None` that raises `KeyError` naming the option when absent (never a default)
  - `Listing`: as today, but `rows: Callable[[Store, ListingRequest], list[Row]] | None`, `flags: tuple[FlagOption, ...]`, and a `scope` property replacing `requires_project`. Keep `flags`, `choice_options`, `value_options` as three separate tuples: argparse adds them in that order, and `--help` must not change
  - `NODE_OPTION = ValueOption(name="node", help_text="Only this node.", metavar="ID")`
- [ ] Create an empty `src/amoeba/inspection/__init__.py` with a module docstring (filled in Task 2.6)
- [ ] Nothing imports these yet

**Success Criteria**:
- [ ] `uv run pyright` clean
- [ ] Committed with Task 2.2

**Files to Create**: `src/amoeba/inspection/__init__.py`, `src/amoeba/inspection/listing.py`

---

### Task 2.2: Test the registry types
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 1
**Objective**: Pin flag derivation, scope, and the request accessor.

**Steps**:
- [ ] Create `tests/inspection/__init__.py` and `tests/inspection/test_listing.py`
- [ ] Test: `ValueOption(name="judge_invocation_id", …).flag == "--judge-invocation-id"`; each option class derives its flag the same way
- [ ] Test: a `Listing` with both or neither row function raises `ValueError`; `scope` is `PROJECT` for `rows`, `SUPERVISOR` for `supervisor_rows`
- [ ] Test: `ListingRequest.option` returns the stored value, and raises `KeyError` for an option not in `options`

**Success Criteria**:
- [ ] New tests pass; full suite green
- [ ] Commit, e.g. `feat(inspection): add typed listing request and options`

**Files to Create**: `tests/inspection/__init__.py`, `tests/inspection/test_listing.py`

---

### Task 2.3: Move `discover_project_ids` to the store
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 1
**Objective**: Inspection can list projects without importing the process (LLD Migration Plan, row 3).

**Steps**:
- [ ] Create `src/amoeba/store/discovery.py` holding `discover_project_ids` unchanged (it uses `STORE_FILE_SUFFIX`; import it from `store/paths.py`)
- [ ] Delete it from `process/supervisor.py`. `store_path_for` stays there
- [ ] Update `process/project_stores.py`, `cli/inspect.py`, and `tests/process/test_project_stores.py` to import from `amoeba.store.discovery`. No re-export shim

**Success Criteria**:
- [ ] `grep -rn discover_project_ids src tests` shows only `store/discovery.py` as the definition
- [ ] Suite, `ruff`, `pyright` clean
- [ ] Commit, e.g. `refactor(store): move discover_project_ids into amoeba.store`

**Files to Create**: `src/amoeba/store/discovery.py`
**Files to Modify**: `src/amoeba/process/supervisor.py`, `src/amoeba/process/project_stores.py`, `src/amoeba/cli/inspect.py`, `tests/process/test_project_stores.py`

---

### Task 2.4: Move the change record to `amoeba.feed`
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 1
**Objective**: One definition of a change's wire form, shared by `amoeba feed` and the stream (LLD Migration Plan, row 4).

**Steps**:
- [ ] Create `src/amoeba/feed/wire.py` with `change_record(change: Change) -> dict[str, object]`: the dict currently built inside `change_line`, same keys, same order
- [ ] In `cli/feed.py`, replace `change_line` with printing `json.dumps(change_record(change))`; remove `change_line`
- [ ] Add `tests/feed/test_wire.py`: the keys and their order, `kind` as the enum value, `recorded_at` as ISO text, `payload` a plain dict
- [ ] Add `feed/wire.py` to `SINGLE_DEFINITION_MODULES` in `tests/test_import_boundaries.py`

**Success Criteria**:
- [ ] `tests/cli/test_feed.py` passes unchanged (proves `amoeba feed` output is identical); new test passes
- [ ] Commit, e.g. `refactor(feed): extract change_record wire form`

**Files to Create**: `src/amoeba/feed/wire.py`, `tests/feed/test_wire.py`
**Files to Modify**: `src/amoeba/cli/feed.py`, `tests/test_import_boundaries.py`

---

### Task 2.5: Move the row modules into `amoeba.inspection`
**Owner**: Junior AI
**Dependencies**: Task 2.4
**Effort**: 3
**Objective**: Every row function lives in `amoeba.inspection` and takes a `ListingRequest` (LLD Migration Plan, rows 1–2).

**Steps**:
- [ ] Use `git mv` for each move so history follows the file. In each moved module: import `Row` and the option types from `amoeba.inspection.listing`; replace `args.project` with `request.project_id`; drop `import argparse`. Define each listing-specific option once, in the module whose row function reads it, and read it with `request.option(THAT_OPTION)`:
  1. [ ] `cli/inspect.py`'s `_node_rows`, `_blocked_rows`, `_journal_rows`, `_project_rows` → new `inspection/core.py` (public names, no underscore). Define `UNRESOLVED_OPTION` (`FlagOption`, name `unresolved`) here. `project_rows` uses `paths.project_store_path`, not `store_path_for`
  2. [ ] `cli/inspect_inbox.py` → `inspection/inbox.py`. Define `CHANNEL_OPTION` (`ChoiceOption`, name `channel`)
  3. [ ] `cli/inspect_evidence.py` → `inspection/evidence.py`, with `VerdictNotComparableError`. Define `JUDGE_INVOCATION_OPTION` (name `judge_invocation_id`) and `VERDICT_OPTION` (name `verdict`, required). `args.json` becomes `not request.compact`; use `NODE_OPTION`
  4. [ ] `cli/inspect_feed.py` → `inspection/feed.py`. Define `OUTCOME_OPTION` (`ChoiceOption`, name `outcome`, choices `OUTCOME_CHOICES`)
  5. [ ] `cli/inspect_checks.py` → `inspection/checks.py`; use `NODE_OPTION`
  6. [ ] `cli/inspect_cf.py` → `inspection/cf.py`
- [ ] Keep help texts, choices, metavars, and `required` exactly as today
- [ ] Update each module docstring that names `inspect.py` or a sibling to the new names
- [ ] The suite will not pass until Task 2.6 rewires the registry; do not commit here

**Success Criteria**:
- [ ] No `argparse` import in `src/amoeba/inspection/`
- [ ] Committed with Task 2.6

**Files to Create**: `src/amoeba/inspection/core.py`
**Files to Move**: the five `cli/inspect_*.py` modules, as listed

---

### Task 2.6: Move the registry and add `read_listing`
**Owner**: Junior AI
**Dependencies**: Task 2.5
**Effort**: 3
**Objective**: One registry and one open-read-only path, used by the CLI and later the server (LLD "What changes shape", `read_listing`).

**Steps**:
- [ ] Move `LISTINGS`, `LISTINGS_BY_NAME`, and `PROJECTS_LISTING` from `cli/inspect.py` into `inspection/__init__.py`, referencing the option objects from Task 2.5. Re-export the `listing.py` types from `__init__`
- [ ] Add `ListingResult` (frozen: `rows: list[Row]`, `as_of_seq: int | None`) and `read_listing(name, request, store_dir) -> ListingResult`: resolve the listing, call `supervisor_rows(store_dir)` or open `paths.project_store_path(store_dir, project_id)` read-only and call `rows`. `as_of_seq` is `None` for now (Task 3.3 fills it). Raise `ValueError` if a project listing gets `project_id=None`
- [ ] Reduce `cli/inspect.py` to argparse helpers and printing: `run_listing` builds a `ListingRequest` from `args` (each option's value read by its `name`, `compact = not args.json`), calls `read_listing(…, paths.store_dir())`, and prints exactly as before (`json.dumps(rows, indent=2, default=str)` or the table)
- [ ] In `cli/main.py`: `_add_inspect_parser` iterates `amoeba.inspection.LISTINGS`, uses `listing.scope` instead of `requires_project`, and adds each option by its derived `flag`, flags first, then choices, then values, as today. Import `VerdictNotComparableError` from `amoeba.inspection.evidence`
- [ ] Update test imports: `tests/test_cli_inspect.py` (registry from `amoeba.inspection`, `scope` instead of `requires_project`); `git mv` `tests/cli/test_inspect_{evidence,feed,checks,cf}.py` to `tests/inspection/test_{evidence,feed,checks,cf}.py` and fix their imports
- [ ] In `tests/test_import_boundaries.py`, change `cli/inspect_feed.py` to `inspection/feed.py`

**Success Criteria**:
- [ ] `grep -rn "amoeba.cli.inspect_\|cli import inspect_" src tests` finds nothing
- [ ] Suite, `ruff`, `pyright` clean
- [ ] Commit (Tasks 2.5–2.6 together), e.g. `refactor(inspection): move listing registry and rows out of the CLI`

**Files to Modify**: `src/amoeba/inspection/__init__.py`, `src/amoeba/cli/inspect.py`, `src/amoeba/cli/main.py`, `tests/test_cli_inspect.py`, `tests/test_import_boundaries.py`
**Files to Move**: four `tests/cli/test_inspect_*.py` files

---

### Task 2.7: Add the inspection layering test
**Owner**: Junior AI
**Dependencies**: Task 2.6
**Effort**: 1
**Objective**: Enforce that inspection imports nothing from the CLI, the server, or the process (LLD "Layering rules", first rule).

**Steps**:
- [ ] In `tests/test_import_boundaries.py`, add `FORBIDDEN_FOR_INSPECTION = ("amoeba.cli", "amoeba.serve", "amoeba.process")` and a test using the existing `_violations("inspection", …)`
- [ ] Update the module docstring's rule list
- [ ] Confirm the test fails if you temporarily add `import amoeba.cli` to `inspection/core.py`; then remove it
- [ ] Confirm `tests/test_writer_guard.py` passes with no allow-list change

**Success Criteria**:
- [ ] Layering and writer-guard tests pass
- [ ] Commit, e.g. `test: forbid inspection from importing cli, serve, or process`

**Files to Modify**: `tests/test_import_boundaries.py`

---

### Task 2.8: Prove `inspect` output is byte-identical
**Owner**: Junior AI
**Dependencies**: Task 2.7
**Effort**: 1
**Objective**: The migration gate: the CLI is unchanged before any server code lands (LLD Technical Requirements, first bullet).

**Steps**:
- [ ] Rerun Task 1.3's capture script against the same `"$BASE/store"` into `"$BASE/after/"`. Do not reseed
- [ ] `diff -r "$BASE/before" "$BASE/after"` must print nothing. If it prints anything, fix the cause; do not edit the baseline
- [ ] Rerun `grep -rn "cli/inspect\|inspect_inbox\|inspect_evidence\|inspect_feed\|inspect_checks\|inspect_cf\|change_line\|discover_project_ids" docs README.md`. The Context Summary records no hits on 20261017; update any hit to the new path and commit it with `docs: update moved inspection paths`
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each
- [ ] Delete `"$BASE"`

**Success Criteria**:
- [ ] `diff -r` empty; suite, `ruff`, `pyright` clean
- [ ] No other commit needed; note the result in the task notes

---

## Section 3: Store Amendment and `as_of_seq`

### Task 3.1: Add `read_transaction()` and `change_head()`
**Owner**: Junior AI
**Dependencies**: Task 2.8
**Effort**: 2
**Objective**: One WAL snapshot across several reads, and the feed head inside it (LLD D4, 106's deferral).

**Steps**:
- [ ] In `store/sql_feed.py`, add `BEGIN_DEFERRED` (or reuse an existing `BEGIN` constant if one exists), and `SELECT_CHANGE_HEAD`: the highest `seq` for a project, `0` when there is none (`COALESCE(MAX(seq), 0)`)
- [ ] In `FeedOperations` (`store/feed.py`), add `change_head(project_id) -> int`
- [ ] Add `read_transaction()`, a context manager: executes the `BEGIN`, yields, and always ends the transaction (`ROLLBACK` is enough; nothing is written). Docstring: SQLite takes the snapshot at the first read inside the transaction, not at `BEGIN`; it is for reads only; it must not be nested
- [ ] If `store/feed.py` passes ~300 lines, ask the PM where the two methods go before splitting

**Success Criteria**:
- [ ] `pyright` clean
- [ ] Committed with Task 3.2

**Files to Modify**: `src/amoeba/store/sql_feed.py`, `src/amoeba/store/feed.py`

---

### Task 3.2: Test the snapshot and the head
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 2
**Objective**: Prove reads inside `read_transaction()` see one snapshot.

**Steps**:
- [ ] Create `tests/store/test_read_transaction.py`, using a throwaway store in `tmp_path`
- [ ] Test: `change_head` is `0` on an empty feed, and equals the last `seq` from `changes()` after commits
- [ ] Test: open the store read-only; inside `read_transaction()`, read `change_head`; commit a change through a separate read-write `Store.open`; read `change_head` again inside the same transaction — unchanged; after the block — the new value
- [ ] Test: the read-only handle is still usable after an exception raised inside the block (the transaction was ended)

**Success Criteria**:
- [ ] New tests pass; full suite green
- [ ] Commit, e.g. `feat(store): add read_transaction and change_head`

**Files to Create**: `tests/store/test_read_transaction.py`

---

### Task 3.3: Report `as_of_seq` from `read_listing`
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 1
**Objective**: Every project read reports the feed `seq` it is current as of (LLD D4, Data Flow "A read").

**Steps**:
- [ ] In `read_listing`, for a project listing, run `listing.rows(store, request)` and then `store.change_head(project_id)` inside one `store.read_transaction()`, and set `as_of_seq`. Supervisor listings keep `None`
- [ ] The CLI ignores `as_of_seq`; its output must not change

**Success Criteria**:
- [ ] `pyright` clean; `tests/test_cli_inspect.py` passes unchanged
- [ ] Committed with Task 3.4

**Files to Modify**: `src/amoeba/inspection/__init__.py`

---

### Task 3.4: Test that rows and `as_of_seq` share a snapshot
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 2
**Objective**: The LLD's Functional Requirement: a commit between two statements of a multi-query listing does not split the read.

**Steps**:
- [ ] Create `tests/inspection/test_read_listing.py`
- [ ] Test: `as_of_seq` equals `change_head` after a read with no concurrent writes; supervisor listings return `None`
- [ ] Snapshot test: use `messages` (one query per channel). Wrap the read-only `Store.messages` with `monkeypatch` so that after its first call it commits a new intent message through a separate read-write store. Assert the rows do not contain the new message and `as_of_seq` is the pre-commit head; a second `read_listing` shows both
- [ ] Test: a project listing with `project_id=None` raises `ValueError`

**Success Criteria**:
- [ ] New tests pass; full suite, `ruff`, `pyright` clean
- [ ] Commit, e.g. `feat(inspection): report as_of_seq from one read snapshot`

**Files to Create**: `tests/inspection/test_read_listing.py`

Continue in `109-tasks.network-api-2.md` (Section 4).
