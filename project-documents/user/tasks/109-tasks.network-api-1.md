---
docType: tasks
slice: network-api
project: amoeba
lld: user/slices/109-slice.network-api.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108]
projectState: Slices 101–108 are merged (store schema 8, listing registry in `cli/inspect.py` with siblings `inspect_inbox.py`, `inspect_evidence.py`, `inspect_feed.py`, `inspect_checks.py`, `inspect_cf.py`; `inbox.submit()`; 106's `follow()` and `Change`; `ExitCode` up to 12). No `amoeba.inspection`, `amoeba.serve`, `read_transaction()`, `change_head()`, or HTTP dependency exists. This slice moves the listings into `amoeba.inspection`, adds the two read-only store methods, and adds `amoeba serve` (Starlette + uvicorn) with reads, submissions, an SSE feed, bind policy, and token auth.
dateCreated: 20261017
dateUpdated: 20261018
status: in_progress
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
  - `Store.open_read_only` raises `StorePermissionError` both for "no store exists" and for "cannot read". The server tells them apart with an existence check before opening (Task 5.1).
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

**Task-level additions to the LLD:**
- `ServeRefusedError` is caught in `cli/serve.py`'s `run_serve`, which prints it and returns `ExitCode.SERVE_REFUSED`; `ExitCode` stays defined in `cli/main.py`. Reason: `cli/serve.py` is the only module allowed to import `amoeba.serve` (LLD "Layering rules"), so `cli/main.py` cannot catch it. The LLD's "Exceptions" bullet says the same.
- Each listing-specific option object is defined once, in the `inspection` module whose row function reads it: `CHANNEL_OPTION` in `inbox.py`, `JUDGE_INVOCATION_OPTION` and `VERDICT_OPTION` in `evidence.py`, `OUTCOME_OPTION` in `feed.py`, `UNRESOLVED_OPTION` in `core.py`. `NODE_OPTION` is shared, in `listing.py`. The server derives query parameters from these objects through the registry, never by importing them by name.
- `inspection/listing.py` holds the registry's types (`Row`, `ListingScope`, the option classes, `ListingRequest`, `Listing`) and the shared `NODE_OPTION`; `inspection/__init__.py` holds the registry and `read_listing`. Reason: the row modules need the option objects at runtime, and the package `__init__` imports the row modules, so defining the types in `__init__` would be an import cycle.
- `FlagOption`, a typed replacement for the `(flag, help)` pairs, so flags gain a `name` like the other options (LLD "What changes shape").
- `tests/inspection_harness.py`, the `populated` seeding extracted from `tests/test_cli_inspect.py`, so the baseline capture and the server parity test use one seeded store.
- The guard order in Task 5.3, the bind-rule order in Task 4.3, and the exception-to-code mapping in Task 4.5 are task-level choices; change them only with the PM.
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
- [x] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [x] Confirm `uv run amoeba inspect checks --help` and `uv run amoeba inspect cf-snapshots --help` succeed. If not, stop and tell the PM (LLD "Prerequisites")
- [x] Create `109-slice.network-api` from the target; if it exists, switch to it
- [x] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each. If any fails before changes, stop and tell the PM

**Success Criteria**:
- [x] On the slice branch; baseline suite, `ruff`, and `pyright` clean
- [x] No commit needed

---

### Task 1.2: Extract the seeded-store harness
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 2
**Objective**: One function that seeds a supervisor directory with at least one row for every listing, usable from tests and from a plain script.

**Steps**:
- [x] Create `tests/inspection_harness.py`. Move the body of `tests/test_cli_inspect.py`'s `populated` fixture into `seed_every_listing(supervisor_dir: Path) -> SeededStore`, where `SeededStore` is a frozen dataclass holding the project id and the ids a listing option needs (the node id, the verdict id `changes` takes, the judge invocation id)
- [x] Move the constants the seeding uses (`PROJECT`, `_FIXTURE_VERDICT`, …) with it; `test_cli_inspect.py` imports them
- [x] Keep `populated` as a thin fixture calling `seed_every_listing`
- [x] Add no new test. `test_every_listing_renders_json` already asserts that every listing returns at least one row from the seeded store, which is what keeps the Task 5.2 parity test from passing on empty rows

**Success Criteria**:
- [x] `uv run pytest tests/test_cli_inspect.py` passes, with no test removed, and `test_every_listing_renders_json` still runs for every listing
- [x] Commit, e.g. `test: extract shared seeded-store harness for listings`

**Files to Create**: `tests/inspection_harness.py`
**Files to Modify**: `tests/test_cli_inspect.py`

---

### Task 1.3: Capture the baseline `inspect` output
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 2
**Objective**: A fixed seeded store and the exact CLI output against it, so Task 2.8 can prove the migration changed nothing (LLD "Behavior preserved").

**Steps**:
- [x] Choose a scratch directory outside the repo, e.g. `BASE="$(mktemp -d)"`, and record its path in the task notes. It must survive until Task 3.4
- [x] Seed `"$BASE/store"` once with `seed_every_listing`, from a throwaway script kept outside the repo (put `tests/` on `sys.path`). Never seed again: ids and timestamps differ per seeding
- [x] With `AMOEBA_STORE_DIR="$BASE/store"`, write into `"$BASE/before/"` one file per command: `inspect --help`; for every listing, `inspect <name> --help`, the table form, and `--json`; and for each declared option, one run exercising it (each flag set, each choice option with one choice, each value option with the seeded id)
- [x] Generate the command list from the registry (iterate `LISTINGS`), not by hand, so no listing is missed. Keep the capture script with the scratch directory for reuse in Task 2.8

**Success Criteria**:
- [x] `"$BASE/before/"` holds a non-empty file for every listing and every option run; no file contains a traceback
- [x] No commit (nothing in the repo changes)

**Notes**: Baseline at /tmp/amoeba-109-baseline.jeId4e (store/, commands.json, before/, capture.sh, seed_and_list.py). 56 captures, all exit 0, no tracebacks; a repeat capture was byte-identical. Replay with: capture.sh "$BASE" "$BASE/after".

---

## Section 2: Migration to `amoeba.inspection` (no new behavior)

### Task 2.1: Add the registry types
**Owner**: Junior AI
**Dependencies**: Task 1.3
**Effort**: 2
**Objective**: The typed request and option model the row functions will take (LLD "What changes shape").

**Steps**:
- [x] Create `src/amoeba/inspection/listing.py` with:
  - `Row` (moved type alias), and `ListingScope(StrEnum)` with `PROJECT = "project"`, `SUPERVISOR = "supervisor"`
  - `FlagOption`, `ChoiceOption`, `ValueOption`: frozen dataclasses with a `name` field (a Python identifier, e.g. `judge_invocation_id`) and their existing fields except `flag`. `flag` becomes a property: `"--" + name.replace("_", "-")`
  - `ListingRequest`: frozen; `project_id: str | None`, `options: Mapping[str, str | bool | None]` keyed by option `name`, `compact: bool`; method `option(opt) -> str | bool | None` that raises `KeyError` naming the option when absent (never a default)
  - `Listing`: as today, but `rows: Callable[[Store, ListingRequest], list[Row]] | None`, `flags: tuple[FlagOption, ...]`, and a `scope` property replacing `requires_project`. Keep `flags`, `choice_options`, `value_options` as three separate tuples: argparse adds them in that order, and `--help` must not change
  - `NODE_OPTION = ValueOption(name="node", help_text="Only this node.", metavar="ID")`
- [x] Create an empty `src/amoeba/inspection/__init__.py` with a module docstring (filled in Task 2.6)
- [x] Nothing imports these yet

**Success Criteria**:
- [x] `uv run pyright` clean
- [x] Committed with Task 2.2

**Files to Create**: `src/amoeba/inspection/__init__.py`, `src/amoeba/inspection/listing.py`

---

### Task 2.2: Test the registry types
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 1
**Objective**: Pin flag derivation, scope, and the request accessor.

**Steps**:
- [x] Create `tests/inspection/__init__.py` and `tests/inspection/test_listing.py`
- [x] Test: `ValueOption(name="judge_invocation_id", …).flag == "--judge-invocation-id"`; each option class derives its flag the same way
- [x] Test: a `Listing` with both or neither row function raises `ValueError`; `scope` is `PROJECT` for `rows`, `SUPERVISOR` for `supervisor_rows`
- [x] Test: `ListingRequest.option` returns the stored value, and raises `KeyError` for an option not in `options`

**Success Criteria**:
- [x] New tests pass; full suite green
- [x] Commit, e.g. `feat(inspection): add typed listing request and options`

**Files to Create**: `tests/inspection/__init__.py`, `tests/inspection/test_listing.py`

---

### Task 2.3: Move `discover_project_ids` to the store
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 1
**Objective**: Inspection can list projects without importing the process (LLD Migration Plan, row 3).

**Steps**:
- [x] Create `src/amoeba/store/discovery.py` holding `discover_project_ids` unchanged (it uses `STORE_FILE_SUFFIX`; import it from `store/paths.py`)
- [x] Delete it from `process/supervisor.py`. `store_path_for` stays there
- [x] Update `process/project_stores.py`, `cli/inspect.py`, and `tests/process/test_project_stores.py` to import from `amoeba.store.discovery`. No re-export shim

**Success Criteria**:
- [x] `grep -rn discover_project_ids src tests` shows only `store/discovery.py` as the definition
- [x] Suite, `ruff`, `pyright` clean
- [x] Commit, e.g. `refactor(store): move discover_project_ids into amoeba.store`

**Files to Create**: `src/amoeba/store/discovery.py`
**Files to Modify**: `src/amoeba/process/supervisor.py`, `src/amoeba/process/project_stores.py`, `src/amoeba/cli/inspect.py`, `tests/process/test_project_stores.py`

---

### Task 2.4: Move the change record to `amoeba.feed`
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 1
**Objective**: One definition of a change's wire form, shared by `amoeba feed` and the stream (LLD Migration Plan, row 4).

**Steps**:
- [x] Create `src/amoeba/feed/wire.py` with `change_record(change: Change) -> dict[str, object]`: the dict currently built inside `change_line`, same keys, same order
- [x] In `cli/feed.py`, replace `change_line` with printing `json.dumps(change_record(change))`; remove `change_line`
- [x] Add `tests/feed/test_wire.py`: the keys and their order, `kind` as the enum value, `recorded_at` as ISO text, `payload` a plain dict

**Success Criteria**:
- [x] `tests/cli/test_feed.py` passes unchanged (proves `amoeba feed` output is identical); new test passes
- [x] Commit, e.g. `refactor(feed): extract change_record wire form`

**Files to Create**: `src/amoeba/feed/wire.py`, `tests/feed/test_wire.py`
**Files to Modify**: `src/amoeba/cli/feed.py`

---

### Task 2.5a: Convert the rows to `ListingRequest` in place
**Owner**: Junior AI
**Dependencies**: Task 2.4
**Effort**: 2
**Objective**: Every row function takes a `ListingRequest` while every module stays where it is, so the change of shape is committed green before anything moves (LLD "What changes shape").

**Steps**:
- [x] In each sibling module, still under `cli/`: import `Row` and the option types from `amoeba.inspection.listing`; replace `args.project` with `request.project_id`; drop `import argparse`. Define each listing-specific option once, in the module whose row function reads it (file 1's "Task-level additions"), and read it with `request.option(THAT_OPTION)`:
  1. [x] `cli/inspect_inbox.py`: define `CHANNEL_OPTION` (`ChoiceOption`, name `channel`)
  2. [x] `cli/inspect_evidence.py`: define `JUDGE_INVOCATION_OPTION` (name `judge_invocation_id`) and `VERDICT_OPTION` (name `verdict`, required). `args.json` becomes `not request.compact`; use `NODE_OPTION`
  3. [x] `cli/inspect_feed.py`: define `OUTCOME_OPTION` (`ChoiceOption`, name `outcome`, choices `OUTCOME_CHOICES`)
  4. [x] `cli/inspect_checks.py`: use `NODE_OPTION`
  5. [x] `cli/inspect_cf.py`: `request.project_id` only
- [x] Run `uv run pytest tests/cli` once after the five modules; it must be green before the next step
- [x] In `cli/inspect.py`: convert the four core row functions the same way, defining `UNRESOLVED_OPTION` (`FlagOption`, name `unresolved`); build `LISTINGS` from `amoeba.inspection.listing.Listing` and the option objects; `run_listing` builds a `ListingRequest` from `args` (each option's value read by its `name`, `compact = not args.json`) and prints exactly as before
- [x] In `cli/main.py`: `_add_inspect_parser` uses `listing.scope` instead of `requires_project` and adds each option by its derived `flag`, flags first, then choices, then values, as today
- [x] Keep help texts, choices, metavars, and `required` exactly as today
- [x] Tests: `scope` instead of `requires_project` in `tests/test_cli_inspect.py`

**Success Criteria**:
- [x] No `argparse` import in any of the five sibling modules
- [x] Suite, `ruff`, `pyright` clean
- [x] Commit, e.g. `refactor(inspect): read listing options through ListingRequest`

**Notes**: Added ListingRequest.require_project_id() (raises ValueError when project_id is None) because store methods take a str project id; row functions call it instead of reading request.project_id. The intermediate "run tests/cli after the five modules" step could not be green on its own (cli/inspect.py still passed an argparse.Namespace), so the suite was run once after inspect.py and main.py were converted. Argparse options now use dest=option.name. Baseline replay byte-identical.

**Files to Modify**: the five `cli/inspect_*.py` modules, `src/amoeba/cli/inspect.py`, `src/amoeba/cli/main.py`, `tests/test_cli_inspect.py`

---

### Task 2.5b: Move the sibling modules to `amoeba.inspection`
**Owner**: Junior AI
**Dependencies**: Task 2.5a
**Effort**: 1
**Objective**: The five sibling modules live in `amoeba.inspection`, as a pure move so git history follows each file; the registry stays in `cli/inspect.py` for one more task (LLD Migration Plan, row 2).

**Steps**:
- [x] `git mv` each module, then fix imports only. No other edit in this commit:
  1. [x] `cli/inspect_inbox.py` → `inspection/inbox.py`
  2. [x] `cli/inspect_evidence.py` → `inspection/evidence.py` (with `VerdictNotComparableError`)
  3. [x] `cli/inspect_feed.py` → `inspection/feed.py`
  4. [x] `cli/inspect_checks.py` → `inspection/checks.py`
  5. [x] `cli/inspect_cf.py` → `inspection/cf.py`
- [x] Update `cli/inspect.py`'s imports, and `cli/main.py`'s `VerdictNotComparableError` import to `amoeba.inspection.evidence`. Update each module docstring that names `inspect.py` or a sibling
- [x] Tests: `git mv` `tests/cli/test_inspect_{evidence,feed,checks,cf}.py` to `tests/inspection/test_{evidence,feed,checks,cf}.py` and fix their imports; in `tests/test_import_boundaries.py`, change `cli/inspect_feed.py` to `inspection/feed.py`

**Success Criteria**:
- [x] `grep -rn "amoeba.cli.inspect_\|cli import inspect_" src tests` finds nothing; `git log --follow` on each moved file shows its history
- [x] Suite, `ruff`, `pyright` clean
- [x] Commit, e.g. `refactor(inspection): move listing rows out of the CLI`

**Notes**: Preceded by commit 7c2c766, which moved process/review_sources.py to store/review_sources.py (PM decision 20261018): inspection/feed.py's watches rows call list_review_files, and Task 2.7 forbids inspection importing amoeba.process. Recorded in the LLD Migration Plan table.

**Files to Modify**: `src/amoeba/cli/inspect.py`, `src/amoeba/cli/main.py`, `tests/test_import_boundaries.py`
**Files to Move**: the five `cli/inspect_*.py` modules and four `tests/cli/test_inspect_*.py` files, as listed

---

### Task 2.6: Move the registry and add `read_listing`
**Owner**: Junior AI
**Dependencies**: Task 2.5b
**Effort**: 2
**Objective**: One registry and one open-read-only path, used by the CLI and later the server (LLD "What changes shape", `read_listing`).

**Steps**:
- [x] Move the four core row functions from `cli/inspect.py` to new `inspection/core.py` (public names, no underscore), with `UNRESOLVED_OPTION`. `project_rows` uses `paths.project_store_path`, not `store_path_for`
- [x] Move `LISTINGS`, `LISTINGS_BY_NAME`, and `PROJECTS_LISTING` into `inspection/__init__.py`. Re-export the `listing.py` types from `__init__`
- [x] Add `ListingResult` (frozen: `rows: list[Row]`, `as_of_seq: int | None`) and `read_listing(name, request, store_dir) -> ListingResult`: resolve the listing, call `supervisor_rows(store_dir)` or open `paths.project_store_path(store_dir, project_id)` read-only and call `rows`. `as_of_seq` is `None` for now (Task 3.3 fills it). Raise `ValueError` if a project listing gets `project_id=None`
- [x] Reduce `cli/inspect.py` to argparse helpers and printing: `run_listing` calls `read_listing(…, paths.store_dir())` and prints as before. `cli/main.py` and `tests/test_cli_inspect.py` import the registry from `amoeba.inspection`

**Success Criteria**:
- [x] Suite, `ruff`, `pyright` clean
- [x] Commit, e.g. `refactor(inspection): move listing registry out of the CLI`

**Files to Create**: `src/amoeba/inspection/core.py`
**Files to Modify**: `src/amoeba/inspection/__init__.py`, `src/amoeba/cli/inspect.py`, `src/amoeba/cli/main.py`, `tests/test_cli_inspect.py`

---

### Task 2.7: Add the inspection layering test
**Owner**: Junior AI
**Dependencies**: Task 2.6
**Effort**: 1
**Objective**: Enforce that inspection imports nothing from the CLI, the server, or the process (LLD "Layering rules", first rule).

**Steps**:
- [x] In `tests/test_import_boundaries.py`, add `FORBIDDEN_FOR_INSPECTION = ("amoeba.cli", "amoeba.serve", "amoeba.process")` and a test using the existing `_violations("inspection", …)`
- [x] Update the module docstring's rule list
- [x] Confirm the test fails if you temporarily add `import amoeba.cli` to `inspection/core.py`; then remove it
- [x] Confirm `tests/test_writer_guard.py` passes with no allow-list change

**Success Criteria**:
- [x] Layering and writer-guard tests pass
- [x] Commit, e.g. `test: forbid inspection from importing cli, serve, or process`

**Files to Modify**: `tests/test_import_boundaries.py`

---

### Task 2.8: Prove `inspect` output is byte-identical
**Owner**: Junior AI
**Dependencies**: Task 2.7
**Effort**: 1
**Objective**: The migration gate: the CLI is unchanged before any server code lands (LLD Technical Requirements, first bullet).

**Steps**:
- [x] Rerun Task 1.3's capture script against the same `"$BASE/store"` into `"$BASE/after/"`. Do not reseed
- [x] `diff -r "$BASE/before" "$BASE/after"` must print nothing. If it prints anything, fix the cause; do not edit the baseline
- [x] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each

**Success Criteria**:
- [x] `diff -r` empty; suite, `ruff`, `pyright` clean
- [x] No commit needed; note the result in the task notes. Keep `"$BASE"` for Task 3.4

**Notes**: diff -r before/after empty (56 files); suite 1558 passed, ruff and pyright clean.

---

## Section 3: Store Amendment and `as_of_seq`

### Task 3.1: Add `read_transaction()` and `change_head()`
**Owner**: Junior AI
**Dependencies**: Task 2.8
**Effort**: 2
**Objective**: One WAL snapshot across several reads, and the feed head inside it (LLD D4, 106's deferral).

**Steps**:
- [x] In `store/sql_feed.py`, add `BEGIN_DEFERRED` (or reuse an existing `BEGIN` constant if one exists), and `SELECT_CHANGE_HEAD`: the highest `seq` for a project, `0` when there is none (`COALESCE(MAX(seq), 0)`)
- [x] In `FeedOperations` (`store/feed.py`), add `change_head(project_id) -> int`
- [x] Add `read_transaction()`, a context manager: executes the `BEGIN`, yields, and always ends the transaction (`ROLLBACK` is enough; nothing is written). Docstring: SQLite takes the snapshot at the first read inside the transaction, not at `BEGIN`; it is for reads only; it must not be nested
- [x] If `store/feed.py` passes ~300 lines, ask the PM where the two methods go before splitting

**Success Criteria**:
- [x] `pyright` clean
- [x] Committed with Task 3.2

**Notes**: read_transaction is typed Generator[None]; typeshed marks @contextmanager on an Iterator return as deprecated under pyright strict.

**Files to Modify**: `src/amoeba/store/sql_feed.py`, `src/amoeba/store/feed.py`

---

### Task 3.2: Test the snapshot and the head
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 2
**Objective**: Prove reads inside `read_transaction()` see one snapshot.

**Steps**:
- [x] Create `tests/store/test_read_transaction.py`, using a throwaway store in `tmp_path`
- [x] Test: `change_head` is `0` on an empty feed, and equals the last `seq` from `changes()` after commits
- [x] Test: open the store read-only; inside `read_transaction()`, read `change_head`; commit a change through a separate read-write `Store.open`; read `change_head` again inside the same transaction — unchanged; after the block — the new value
- [x] Test: the read-only handle is still usable after an exception raised inside the block (the transaction was ended)

**Success Criteria**:
- [x] New tests pass; full suite green
- [x] Commit, e.g. `feat(store): add read_transaction and change_head`

**Files to Create**: `tests/store/test_read_transaction.py`

---

### Task 3.3: Report `as_of_seq` from `read_listing`
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 1
**Objective**: Every project read reports the feed `seq` it is current as of (LLD D4, Data Flow "A read").

**Steps**:
- [x] In `read_listing`, for a project listing, run `listing.rows(store, request)` and then `store.change_head(project_id)` inside one `store.read_transaction()`, and set `as_of_seq`. Supervisor listings keep `None`
- [x] The CLI ignores `as_of_seq`; its output must not change

**Success Criteria**:
- [x] `pyright` clean; `tests/test_cli_inspect.py` passes unchanged
- [x] Committed with Task 3.4

**Files to Modify**: `src/amoeba/inspection/__init__.py`

---

### Task 3.4: Test that rows and `as_of_seq` share a snapshot
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 2
**Objective**: The LLD's Functional Requirement: a commit between two statements of a multi-query listing does not split the read.

**Steps**:
- [x] Create `tests/inspection/test_read_listing.py`
- [x] Test: `as_of_seq` equals `change_head` after a read with no concurrent writes; supervisor listings return `None`
- [x] Snapshot test: use `messages` (one query per channel). Wrap the read-only `Store.messages` with `monkeypatch` so that after its first call it commits a new intent message through a separate read-write store. Assert the rows do not contain the new message and `as_of_seq` is the pre-commit head; a second `read_listing` shows both
- [x] Test: a project listing with `project_id=None` raises `ValueError`
- [x] Rerun Task 1.3's capture into `"$BASE/after/"` (replacing it); `diff -r "$BASE/before" "$BASE/after"` must print nothing, because Task 3.3 changed the CLI's read path. Then delete `"$BASE"`

**Success Criteria**:
- [x] New tests pass; `diff -r` empty; full suite, `ruff`, `pyright` clean
- [x] Commit, e.g. `feat(inspection): report as_of_seq from one read snapshot`

**Notes**: The snapshot test commits an escalation message (journal_escalate on the seeded unresolved entry), not an intent message: messages queries intent first and escalation second, so an intent committed after the first query would be missed with or without a snapshot. Verified non-vacuous: with read_transaction removed, the test fails. Baseline replay identical (56 files); baseline directory deleted.

**Files to Create**: `tests/inspection/test_read_listing.py`

Continue in `109-tasks.network-api-2.md` (Section 4).
