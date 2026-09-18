---
docType: tasks
slice: store-foundation-and-node-model
project: amoeba
lld: user/slices/101-slice.store-foundation-and-node-model.md
dependencies: []
projectState: Empty repository — no pyproject.toml, no src/, no tests/, no uv.lock. Planning artifacts only. This slice lands the first code.
dateCreated: 20260915
dateUpdated: 20260917
status: complete
---

## Context Summary

- Working on the **store-foundation-and-node-model** slice (101), the first code in the Amoeba repository.
- **Current state:** the repository contains planning documents and nothing else. There is no Python package, no test suite, and no tooling configuration. Tasks 1.x create all of it.
- **Dependencies:** none. This slice is the bottom of the stack and defines the interface every other slice consumes.
- **What this slice delivers:** the project scaffold, a SQLite-backed lifecycle node store (project-keyed node tree, closed status vocabulary, blocked-states with an explicit resolution slot, the two Runner queries, a schema-version stamp and migration runner), and contract documentation complete enough that initiative 120 can design against it without reading the implementation.
- **Key design commitments** (from the LLD — do not revisit them here): raw stdlib `sqlite3`, not SQLAlchemy; all SQL and every column name centralized in `sql.py`; one per-supervisor central store keyed by project; `block()` and `resolve()` are single store operations so node status and blocked-state can never disagree.
- **Next planned slice:** 102 (Resident Process and Recovery), which hosts this store and becomes its sole writer.

**Reading note for the executing developer:** this file does not restate the LLD. Where a task says "per the LLD," open `user/slices/101-slice.store-foundation-and-node-model.md` at the named section and follow it. Exact DDL, column names, and signatures are settled during implementation against that design.

---

## Section 1: Scaffold and Test Infrastructure

### Task 1.1: Create the Python project scaffold
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 2
**Objective**: Create `pyproject.toml` and the `src/` / `tests/` layout so that tooling is real before any store code is written.

**Steps**:
- [x] Create `pyproject.toml` at the repository root with project metadata, `requires-python = ">=3.12"`, and no runtime dependencies (the store uses only the standard library)
- [x] Add the `[tool.ruff]` and `[tool.ruff.lint]` blocks mandated by `rules/python.md`, selecting exactly `["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]` with `line-length = 88`
- [x] Add the `[tool.pyright]` block in `strict` mode covering both `src` and `tests`, with `pythonVersion` matching the project target
- [x] Add `pytest` as a development dependency and configure its test paths
- [x] Create the package directory `src/amoeba/store/` with `__init__.py` files, and an empty `tests/` directory
- [x] Run `uv sync` to create the lockfile and environment

**Success Criteria**:
- [x] `uv sync` completes and `uv.lock` exists
- [x] `uv run ruff check .` passes clean on the empty package
- [x] `uv run ruff format --check .` passes clean
- [x] `uv run pyright` reports zero errors across `src` and `tests`
- [x] The ruff selection list and the pyright strict block match `rules/python.md` exactly — no relaxed settings, no per-file ignores added to make things pass

**Files to Create**:
- `pyproject.toml`
- `src/amoeba/__init__.py`, `src/amoeba/store/__init__.py`
- `tests/` (directory)

---

### Task 1.2: Add the .gitignore entries for a Python project
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 1
**Objective**: Ensure build artifacts, virtual environments, and caches are not committed.

**Steps**:
- [x] Add Python entries to the existing root `.gitignore`: `__pycache__/`, `*.py[cod]`, `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `dist/`, `build/`, `*.egg-info/`
- [x] Confirm `uv.lock` is **not** ignored — it is committed

**Success Criteria**:
- [x] `git status --porcelain` shows no cache, venv, or bytecode files as untracked
- [x] `uv.lock` appears as a tracked or stageable file

---

### Task 1.3: Commit the scaffold
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 1
**Objective**: Establish a clean, verified checkpoint before any store code exists.

**Steps**:
- [x] Verify the current working directory is the repository root
- [x] Confirm the branch is the slice branch `101-slice.store-foundation-and-node-model` (Phase 6 work; create it from the integration target if it does not exist, per the project git rules)
- [x] Stage and commit with a semantic message, e.g. `chore: add python project scaffold and tooling config`

**Success Criteria**:
- [x] Commit exists on the slice branch
- [x] Working tree is clean
- [x] All three tooling commands from Task 1.1 still pass at this commit

---

### Task 1.4: Implement central store path resolution
**Owner**: Junior AI
**Dependencies**: Task 1.3
**Effort**: 2
**Objective**: Implement the per-supervisor default store path as a named constant with explicit resolution rules, per the LLD's "Store locality" section. This precedes the test fixture because the fixture's safety guard checks against this constant.

**Steps**:
- [x] Define the central store directory as a named module-level constant, following the `~/.config/amoeba/` convention that matches Squadron's `~/.config/squadron/`
- [x] Implement resolution with an explicit precedence order: environment override first, then XDG base-directory handling, then the `~/.config/amoeba/` default
- [x] Key the resolved store path by project, per the LLD's central-and-project-keyed commitment
- [x] Do **not** build a per-project override — the LLD declines it deliberately
- [x] Resolution computes a path only; it performs no I/O and creates nothing. Directory creation stays in the store's open path (Task 3.2)

**Success Criteria**:
- [x] The default directory is a named constant, referenced everywhere rather than repeated as a literal
- [x] Precedence is explicit and covered by tests: env override beats XDG, XDG beats the default
- [x] Resolution is a pure function — no directory is created and no file is touched by calling it
- [x] `uv run pyright` strict and `uv run ruff check .` pass

**Files to Create**:
- `src/amoeba/store/paths.py`

---

### Task 1.5: Test path resolution
**Owner**: Junior AI
**Dependencies**: Task 1.4
**Effort**: 2
**Objective**: Verify the precedence order and the no-I/O guarantee.

**Steps**:
- [x] Test each precedence level with a monkeypatched environment: override set, override unset with XDG set, neither set
- [x] Test that the resolved path is project-keyed and that two project ids yield different paths
- [x] Test that calling resolution creates no directory and no file
- [x] Assert against the named constant, not a hardcoded `~/.config/amoeba` literal

**Success Criteria**:
- [x] `uv run pytest tests/test_paths.py -v` passes
- [x] All three precedence levels are covered
- [x] A test asserts no filesystem side effects

**Files to Create**:
- `tests/test_paths.py`

---

### Task 1.6: Create the throwaway-store test fixture
**Owner**: Junior AI
**Dependencies**: Task 1.5
**Effort**: 2
**Objective**: Create `tests/conftest.py` providing a fixture that creates its own throwaway store, so no test can touch the real per-supervisor store. This task precedes all implementation because every later test depends on it.

**Steps**:
- [x] Create `tests/conftest.py` with a fixture that creates a store in a pytest `tmp_path` and yields its path or an open store
- [x] The fixture destroys only what it created — per the testing rules' database-safety section and the LLD's "Special Considerations"
- [x] State the fixture's scope and its safety guarantee in its docstring
- [x] Add a guard test asserting that no test module references the central store path constant or the resolution function defined in `paths.py` (Task 1.4), so the safety property is mechanically checked rather than assumed
- [x] Make the guard scan multiline-aware, per the testing rules — a per-line grep is defeated by a call split across lines

**Success Criteria**:
- [x] The fixture creates its store under `tmp_path` and never under the resolved central path
- [x] The fixture's docstring states its scope and that it destroys only what it created
- [x] The guard test passes, and fails if a test module reaches for the `paths.py` constant or resolver
- [x] `uv run pyright` passes on `tests/` in strict mode

**Files to Create**:
- `tests/conftest.py`

**Note**: the fixture will not be fully exercisable until Task 2.3 lands an openable store. Write it against the API the LLD specifies; adjust in Task 2.3 if signatures settle differently.

---

## Section 2: Models, Migrations, and Schema

### Task 2.1: Implement models.py — vocabularies and dataclasses
**Owner**: Junior AI
**Dependencies**: Task 1.6
**Effort**: 3
**Objective**: Define the status `StrEnum`, the other closed vocabularies, and the `Node` / `BlockedState` / `Resolution` dataclasses. This module fixes the vocabulary every other module references.

**Steps**:
- [x] Define the node status `StrEnum` with exactly the six values in the LLD's "Closed vocabularies" section — no additions
- [x] Define the node `kind` closed vocabulary (initiative / phase-or-artifact / slice / gate) as a `StrEnum`
- [x] Define the blocked-state `kind` closed vocabulary as a `StrEnum`
- [x] Define `Node`, `BlockedState`, and `Resolution` as `@dataclass` types with full type hints on every attribute, using `pathlib.Path` for path-valued fields
- [x] Define the typed store exception hierarchy used by later tasks (a base store error plus the specific errors the failure-mode task raises)
- [x] Ensure nothing in this module imports `sqlite3` or references SQL

**Success Criteria**:
- [x] The status vocabulary is defined exactly once and nowhere duplicated
- [x] All three vocabularies are `StrEnum`, so their database values are readable strings
- [x] `uv run pyright` strict passes with zero errors
- [x] `uv run ruff check .` passes
- [x] No SQL string and no `sqlite3` import appears in this module

**Files to Create**:
- `src/amoeba/store/models.py`

---

### Task 2.2: Test models.py
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 2
**Objective**: Verify the vocabularies and dataclasses behave as the contract requires.

**Steps**:
- [x] Test that each status enum member's value is the expected readable string
- [x] Test that constructing a dataclass with a valid status succeeds and attributes round-trip
- [x] Test that an out-of-vocabulary status string raises rather than producing a defaulted value — the "unknown is a value, not a default" principle
- [x] Parametrize across every status value rather than testing one representative

**Success Criteria**:
- [x] `uv run pytest tests/test_models.py -v` passes
- [x] Every value in the status vocabulary is covered by the parametrized tests
- [x] A test demonstrates that an unknown status raises

**Files to Create**:
- `tests/test_models.py`

---

### Task 2.3: Implement migrations.py and 001_initial.sql
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 3
**Objective**: Implement the version stamp and the numbered-migration runner, plus the initial schema, so the version mechanism works before there is anything to migrate.

**Steps**:
- [x] Write `migrations/001_initial.sql` creating `schema_meta`, `nodes`, and `blocked_states` per the LLD's "Storage Schema" section
- [x] Create the index covering `(project_id, status)` — and no other indexes, per the LLD
- [x] Implement version detection: read the stamp from `schema_meta` at open, before anything else
- [x] Implement the runner: apply numbered `.sql` files in order inside a transaction, updating the stamp as it goes
- [x] Raise a typed error when the store's version is **newer** than the code expects — never silently downgrade or proceed
- [x] Ensure migration `.sql` files are packaged so they resolve when the package is installed, not only from a source checkout

**Success Criteria**:
- [x] Opening a fresh path creates the schema and stamps version 1
- [x] The stamp is read before any other query at open
- [x] A store stamped newer than the code raises a typed error
- [x] `uv run pyright` strict and `uv run ruff check .` pass

**Files to Create**:
- `src/amoeba/store/migrations.py`
- `src/amoeba/store/migrations/001_initial.sql`

---

### Task 2.4: Test the migration runner and version stamp
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 2
**Objective**: Verify version detection and the runner before the store API is layered on top.

**Steps**:
- [x] Test that a fresh store is created at the expected version and the schema objects exist
- [x] Test that opening an already-migrated store does not re-apply migrations
- [x] Test that a store stamped newer than the code raises the typed error
- [x] Test that a migration failure leaves the stamp unadvanced (the transaction rolled back)

**Success Criteria**:
- [x] `uv run pytest tests/test_migrations.py -v` passes
- [x] The newer-than-code case asserts the specific typed exception, not a generic one
- [x] The rollback test demonstrates the stamp and schema stay consistent after a failed migration

**Files to Create**:
- `tests/test_migrations.py`

---

### Task 2.5: Commit models and migrations
**Owner**: Junior AI
**Dependencies**: Task 2.4
**Effort**: 1
**Objective**: Checkpoint a verified, buildable state before the store API lands.

**Steps**:
- [x] Verify working directory and branch
- [x] Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, and `uv run pytest`
- [x] Commit, e.g. `feat: add node models and sqlite migration runner`

**Success Criteria**:
- [x] All four verification commands pass before the commit
- [x] Commit exists and the working tree is clean

---

## Section 3: SQL Layer and Store API

### Task 3.1: Implement sql.py — column constants and statements
**Owner**: Junior AI
**Dependencies**: Task 2.5
**Effort**: 3
**Objective**: Centralize every SQL statement and every column name so a column-name typo is a single-definition concern rather than scattered runtime risk. This is the structural mitigation the LLD commits to in exchange for choosing raw `sqlite3`.

**Steps**:
- [x] Define every column name as a module-level constant
- [x] Write every statement the store needs — node CRUD, blocked-state writes, the resolution-slot fill, and the two Runner queries — as parameterized statements referencing those constants
- [x] Define the busy-timeout value as a **named configuration constant** here (or in a config module), never as an inline literal at the `connect` call
- [x] Use parameterized placeholders only — no f-string SQL anywhere
- [x] Ensure this module imports neither the dataclasses nor `sqlite3`; it holds statements and names only

**Success Criteria**:
- [x] Every column name used anywhere in the package resolves to a constant defined in this module
- [x] No SQL string literal appears in any other module of the package
- [x] No f-string or concatenated SQL exists anywhere
- [x] The busy timeout is a named constant
- [x] `uv run pyright` strict and `uv run ruff check .` pass

**Files to Create**:
- `src/amoeba/store/sql.py`

---

### Task 3.2: Implement store.py — open, close, and row mapping
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 3
**Objective**: Implement store lifecycle (open, close, context-manager form) and the single row-mapping layer between SQL rows and typed dataclasses.

**Steps**:
- [x] Implement open: accept an explicit path, or fall back to the resolver from `paths.py` (Task 1.4) when none is given; create parent directories as needed, connect, set WAL journal mode, set the busy timeout from the named constant, then delegate to the migration runner
- [x] Implement close and a context-manager form for tests and callers
- [x] Implement `open_temporary()` for throwaway stores, as used by the LLD's verification walkthrough
- [x] Implement row-to-dataclass mapping in exactly one place; an unmappable row raises rather than yielding a partially-populated object
- [x] Validate status values against the enum on the way in and on the way out
- [x] Keep the file near the ~300-line guideline; if it exceeds it, split by concern rather than padding

**Success Criteria**:
- [x] A store opens at a path, creating and migrating as needed, and closes cleanly
- [x] The context-manager form releases the connection on both normal and exception exit
- [x] WAL mode and the busy timeout are set at open
- [x] Row mapping exists in exactly one place; a row with an out-of-vocabulary status raises
- [x] `uv run pyright` strict and `uv run ruff check .` pass

**Files to Create**:
- `src/amoeba/store/store.py`

---

### Task 3.3: Implement node CRUD
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 3
**Objective**: Implement node creation, status update, reference-field update, and the read methods.

**Steps**:
- [x] Implement create-node-under-parent, generating a store-generated opaque id (not derived from CF coordinates, per the LLD)
- [x] Require `project_id` on every node from the first row written
- [x] Implement update-node-status, validating against the enum
- [x] Implement update of the CF and SQ reference fields, stored as opaque values with no parsing
- [x] Implement reads: get by id, list children of a node, list by project
- [x] Wrap writes in transactions; failures propagate rather than returning an ignorable status code

**Success Criteria**:
- [x] A node tree can be created, read, updated, and queried by project and by parent
- [x] Node ids are store-generated and stable across reference-field changes
- [x] No write method returns a status code a caller can ignore
- [x] `uv run pyright` strict and `uv run ruff check .` pass

---

### Task 3.4: Test node CRUD and project scoping
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 3
**Objective**: Verify CRUD behavior and the project-isolation guarantee.

**Steps**:
- [x] Test create / read / update / list-children round-trips
- [x] Test that updating reference fields does not change the node's id
- [x] Test that a status outside the vocabulary raises on write
- [x] Test the **read** side of the vocabulary guarantee: write a row containing an out-of-vocabulary status directly via SQL, then assert reading it raises rather than yielding a partially-populated object — the "unknown is a value, not a default" principle at the storage boundary
- [x] Test the context-manager form releases its connection on normal exit **and** on exception exit
- [x] Test project isolation: with two projects populated, every query for one project returns none of the other's nodes
- [x] Test the empty case: queries against a project with no nodes return an empty result, not an error

**Success Criteria**:
- [x] `uv run pytest tests/test_store.py -v` passes
- [x] A dedicated test demonstrates cross-project isolation
- [x] An unmappable row raises on read; no test observes a partially-populated object
- [x] The context manager releases on both exit paths
- [x] The empty case is covered

**Files to Create**:
- `tests/test_store.py`

---

### Task 3.5: Implement block() and resolve() as single operations
**Owner**: Junior AI
**Dependencies**: Task 3.4
**Effort**: 3
**Objective**: Implement the blocked-state write and the resolution-slot fill as **single store operations**, so node status and blocked-state can never disagree. This is the schema-level expression of checkpoint-as-persisted-blocked-state and is the load-bearing behavior of the slice.

**Steps**:
- [x] Implement `block()`: write the blocked-state record against a node **and** set that node's status, in one transaction
- [x] Implement `resolve()`: fill the resolution slot with its provenance **and** flip the node to `runnable`, in one transaction
- [x] Do not expose a caller-composed two-step alternative — the caller must not be able to write one half
- [x] Raise a typed error when resolving a node that is not blocked, or blocking a node already blocked, rather than silently overwriting

**Success Criteria**:
- [x] `block()` and `resolve()` are each one call and one transaction
- [x] There is no public path that sets a blocked-state without also setting node status, or vice versa
- [x] Invalid transitions raise typed errors
- [x] `uv run pyright` strict and `uv run ruff check .` pass

---

### Task 3.6: Implement the two Runner queries
**Owner**: Junior AI
**Dependencies**: Task 3.5
**Effort**: 2
**Objective**: Implement *what is runnable?* and *what is blocked and on whom?* — the two queries the Runner's loop consumes.

**Steps**:
- [x] Implement the runnable query: nodes in `runnable` status for a project
- [x] Implement the blocked query: nodes in any `blocked_on_*` status for a project, each returned **with** its blocked-state record so "on whom" needs no second call
- [x] Confirm both queries use the `(project_id, status)` index
- [x] Add docstrings sufficient for a downstream author who will not read the implementation

**Success Criteria**:
- [x] The blocked query answers "on whom" in a single call
- [x] Both queries are project-scoped
- [x] `uv run pyright` strict and `uv run ruff check .` pass

---

### Task 3.7: Test block/resolve and the two queries
**Owner**: Junior AI
**Dependencies**: Task 3.6
**Effort**: 3
**Objective**: Verify the checkpoint mechanic end to end — the claim this slice exists to make.

**Steps**:
- [x] Test that blocking a node removes it from the runnable set and places it in the blocked set with its blocker identified
- [x] Test that the node returns to runnable when — and only when — its resolution slot is filled
- [x] Test that node status and blocked-state never disagree, including after a failed operation
- [x] Parametrize the blocked query across every `blocked_on_*` status value
- [x] Test cross-project isolation for **both Runner queries**: with two projects each holding runnable and blocked nodes, `runnable()` and `blocked()` scoped to project A return none of project B's nodes. Functional Requirement 6 is a blanket claim about all queries, and these two are the pair the Runner depends on — assert it here rather than inheriting confidence from the CRUD-level test
- [x] Test both queries' empty cases
- [x] Test that invalid transitions raise

**Success Criteria**:
- [x] `uv run pytest tests/test_queries.py -v` passes
- [x] Every `blocked_on_*` value is exercised
- [x] Both Runner queries are asserted project-scoped against a populated second project
- [x] A test asserts the node is absent from runnable while blocked and present after resolution

**Files to Create**:
- `tests/test_queries.py`

---

### Task 3.8: Commit the store API
**Owner**: Junior AI
**Dependencies**: Task 3.7
**Effort**: 1
**Objective**: Checkpoint the working store before failure-mode hardening.

**Steps**:
- [x] Verify working directory and branch
- [x] Run ruff check, ruff format --check, pyright, and pytest
- [x] Commit, e.g. `feat: add store api with node crud and runner queries`

**Success Criteria**:
- [x] All four verification commands pass before the commit
- [x] Working tree is clean

---

