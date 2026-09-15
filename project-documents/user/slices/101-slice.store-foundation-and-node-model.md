---
docType: slice-design
slice: store-foundation-and-node-model
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: []
interfaces: [102, 103, 104, 105, 106]
dateCreated: 20260914
dateUpdated: 20260914
status: not_started
---

# Slice Design: Store Foundation and Node Model

## Overview

This slice creates the lifecycle node schema and the read/write contract that every other Amoeba initiative codes against. It is the first code in the repository: there is no `pyproject.toml`, no `src/`, no test suite. So it delivers three things at once — the project scaffold, the store itself, and the contract documentation that lets initiative 120 begin its own slice design without reading the implementation.

Deliberately excluded is any process. This slice ships a **library**: a test opens a store, writes nodes, and queries them. The resident process that hosts the Runner and becomes the store's sole writer is slice 102.

## Value

**Architectural enablement.** Initiatives 120 (Runner & Routing), 140 (Judge Invocation & Consensus), and 160 (Translator & Notification) are all blocked on this contract existing and being stable. The architecture document is explicit that the contract, not the engine, is the commitment — so the measure of this slice is whether a downstream author can design against it without asking what is underneath.

The concept's single load-bearing decision — *a checkpoint is a persisted blocked-state, not a blocking call* — becomes real here. A blocked node with an unfilled resolution slot is that decision expressed as a row. Everything that makes Amoeba async by construction, restart-survivable, and extensible to multi-project mode follows from this schema being right.

## Technical Scope

**Included:**

- Repository scaffold: `pyproject.toml` with the `uv` / `ruff` / `pyright` / `pytest` configuration the project's Python rules mandate, plus `src/` and `tests/` layout.
- The project-keyed lifecycle node tree (initiative → phase/artifact → slice → gate).
- The closed status vocabulary as a single `StrEnum`.
- Blocked-state records carrying an explicit resolution slot.
- CF and SQ reference fields on nodes.
- The two queries the Runner's loop consumes: *what is runnable?* and *what is blocked and on whom?*
- Storage engine decision, schema-version stamp, and the migration mechanism.
- The public store API and its contract documentation.

**Explicitly excluded** (named here because each is a plausible scope-creep target):

- Any long-lived process, lifecycle command, or single-instance handling — slice 102.
- The command journal and reconcile-by-observation recovery — slice 102. This slice stores nothing about issued commands.
- The durable inbox and message channels — slice 103. This slice has no concept of an external writer; the library caller is the writer.
- Finding identity, normalization, and verdict provenance — slice 104. Nodes carry *reference fields* pointing at SQ artifacts and runs, but findings and verdicts are not modeled here.
- Change feed, subscriptions, filesystem detection — slice 105.
- Pruning and retention policy — slice 106.
- Any parsing of CF or SQ output. The store accepts values; the Runner (initiative 120) parses them.

## Dependencies

### Prerequisites

None. This is foundation work and the first code in the repository.

Runtime prerequisites are deliberately minimal: Python 3.12+ and the standard library. The storage engine (`sqlite3`) ships with Python, so this slice adds no runtime storage dependency.

### Interfaces Required

None from other slices. This slice defines the interface others require.

Two *upstream* shapes are referenced but not parsed here, recorded so the schema holds the right fields:

- **Squadron run ids** have the form `run-{date}-{slug}-{uuid8}` and are generated internally by Squadron (`src/squadron/pipeline/state.py`). The store holds them as opaque strings.
- **Squadron review artifacts** live under `project-documents/user/reviews/`, with prior versions in `archive/`; the frontmatter contract includes `reviewedSha` conditionally. The store holds artifact paths and the reviewed SHA as opaque values.

## Architecture

### Component Structure

```
src/amoeba/store/
  __init__.py        Public API surface — the contract
  models.py          Node, BlockedState, Resolution dataclasses; StrEnum vocabularies
  sql.py             Every SQL statement; column names as module constants
  store.py           Store class: open/close, transactions, CRUD, the two queries
  migrations.py      Version detection and the migration runner
  migrations/
    001_initial.sql
tests/
  test_models.py
  test_store.py
  test_migrations.py
  test_queries.py
  conftest.py        Throwaway-store fixture
```

The module split follows the project's ~300-line file guideline and keeps one concern per file. `sql.py` exists as its own module for a specific reason given under Technical Decisions.

**Interaction:** `store.py` is the only module callers touch. It composes statements from `sql.py`, maps rows to the dataclasses in `models.py`, and delegates schema setup to `migrations.py` at open time. Nothing in `models.py` knows SQL exists; nothing in `sql.py` knows the dataclasses exist. The mapping between them lives in one place, in `store.py`.

### Data Flow

Two flows, both synchronous and in-process for this slice:

**Write:** caller constructs a typed dataclass → `store.py` validates the status value against the enum → maps to column values → executes a parameterized statement inside a transaction → commits.

**Read:** caller invokes a query method → `store.py` executes the parameterized select → maps each row to a typed dataclass → returns a list. An unmappable row raises; it never yields a partially-populated object, per the "unknown is a value, not a default" principle.

There is no background activity, no polling, no I/O other than the store file.

### State Management

All state is in one SQLite database file. Within this slice the caller owns the writer discipline: the library does not enforce single-writer, because the component that enforces it is the resident process in slice 102. This is stated in the contract documentation so slice 102 knows exactly what it is adding rather than discovering an assumption.

WAL journal mode is set at open, which gives concurrent readers alongside a single writer — the access pattern the architecture's writer model settles on.

## Technical Decisions

### Storage engine: SQLite via stdlib `sqlite3`

**Decision (PM, 2026-09-14):** raw `sqlite3` from the standard library, with all SQL centralized in one module.

The architecture document had already narrowed this: because the resident process is the sole writer and an inbox is the only externally-writable surface, the store never has to arbitrate concurrent external writers, which is what makes an embedded engine viable. SQLite was named as the candidate and is the natural fit for a Python process.

The remaining question was whether to go through SQLAlchemy Core. Raw was chosen because:

- The dependency count for Amoeba's first and only storage layer stays at zero.
- The migration mechanism is a small numbered-`.sql` runner the team owns and can read end to end, rather than Alembic's revision graph and env configuration — machinery aimed at fleet-upgrade problems this component does not have.
- SQLAlchemy's usual payoff is portability, and that payoff is architecturally foreclosed: the engine choice is tied to the sole-writer model, so a change there is a redesign, not a driver swap.

The real cost of raw is typing. `sqlite3` returns `Any` rows, and under `pyright` strict a column-name typo in a rarely-exercised query is a runtime failure rather than a check-time one. The mitigation is structural rather than aspirational: **every SQL statement lives in `sql.py`, and every column name is a module-level constant referenced by both the statements and the row-mapping code.** This satisfies the project rule against scattering comparison values and recovers most of the typo-safety SQLAlchemy would have bought. The typed row-mapping layer is written either way, since the contract exposes dataclasses and not tuples.

**Reversal trigger (PM):** switch to SQLAlchemy Core + Alembic if *either* schema churn across slices 102–106 makes hand-written migrations painful, *or* the hand-rolled layer turns into recurring maintenance — repeated tweaks and bug fixes in the store plumbing itself. Recorded as Future Work so the trigger is a decision someone makes on evidence, not a drift.

### Store locality: per-supervisor, central

**Decision (PM, 2026-09-14):** one store per supervisor at a central path, keyed by project — `~/.config/amoeba/` by convention, matching Squadron's `~/.config/squadron/`. Exact path resolution (XDG handling, environment override) is settled during implementation; the design commitment is central-and-project-keyed.

This follows the architecture's "resident process per supervisor (not per project)" and makes the multi-project forest a quantity change rather than a rewrite. The counter-argument the architecture raised — that a per-project store keeps lifecycle history auditable alongside the project's own git history — is accepted as a real cost and declined: one resident process holding N open stores contradicts the process model, and audit trails can be exported.

No per-project override is built. Adding one would put two locality paths in the foundation slice before any consumer needs either, which the architecture warns against directly.

### Node identity and tree shape

Nodes form a tree by parent reference, scoped by project. Every node carries `project_id` from the first row written, per the architecture's "project is a first-class key from day one" principle — which explicitly does *not* mean building multi-project supervision now.

Node identity is a store-generated opaque id. It is deliberately not derived from CF coordinates: a node's CF pointers can change (a slice is renumbered, an artifact path moves) without the node becoming a different node.

### Closed vocabularies

Status is a `StrEnum` defined once in `models.py`:

`runnable`, `in_progress`, `blocked_on_human`, `blocked_on_judge`, `blocked_on_sq_checkpoint`, `done`

This is the vocabulary fixed by the architecture and the slice plan. `StrEnum` is chosen per the Python rules, and it gives readable values in the database file — which matters because the slice 102 inspection surface reads them.

The same treatment applies to any other value this slice routes on. Free-form upstream strings (Squadron's `category`, CF's prose `recommendation`) are not stored here at all — they belong to slice 104 — and when they arrive they are stored as data, never used as logical structure.

A status value read from the database that is not in the enum is an error, not a default. This is the "unknown is a value, not a default" principle at the storage boundary.

### Patterns and conventions

- Type hints on every signature and attribute; `pyright` strict is a merge blocker, tests included.
- `@dataclass` for the store's DTOs. Pydantic is not used here: these are internal transfer objects at an in-process boundary, not external input. Slice 104, which parses Squadron output, is where the external-boundary rule applies.
- `pathlib.Path` for all paths.
- Parameterized queries only — never f-string SQL.
- Exceptions are specific and typed; the store raises on contract violations rather than returning a sentinel. No `except Exception: pass`, enforced mechanically by ruff's `BLE` rule set.

## Implementation Details

### Storage Schema

Conceptual, not final DDL — column names and types are fixed during implementation against the constants in `sql.py`.

**`schema_meta`** — one row, holding the schema version stamp. Read at open before anything else.

**`nodes`**
- `id` — store-generated primary key
- `project_id` — project scope key (indexed)
- `parent_id` — nullable self-reference forming the tree
- `kind` — closed vocabulary: initiative / phase-or-artifact / slice / gate
- `status` — the status `StrEnum` (indexed, since both required queries filter on it)
- CF reference fields: project id, phase, slice, artifact path
- SQ reference fields: run ids, review artifact paths, reviewed SHA
- timestamps

**`blocked_states`**
- `id`
- `node_id` — the blocked node
- `kind` — closed vocabulary for what it is blocked on
- context describing the block
- **resolution slot** — nullable; when filled, carries the resolution and its provenance
- timestamps

The resolution slot being *nullable and explicit* is the schema-level expression of checkpoint-as-persisted-blocked-state. Filling it is what flips the node back to `runnable`.

Indexes are created for the two required queries — `(project_id, status)` covers both — and nowhere else. Additional indexes wait for a measured need.

### Migration mechanism

A `schema_meta` table holds the current version. At open, `migrations.py` compares it against the code's expected version and applies numbered `.sql` files in order inside a transaction, updating the stamp as it goes. A store newer than the code is an error, not a silent downgrade.

`001_initial.sql` creates the schema above. The slice plan requires a tested N→N+1 migration, so the slice also lands a second, deliberately trivial migration (`002_*`) purely to exercise the runner end to end. Later slices add real migrations onto a mechanism already proven.

### API Contract

The public surface, shape-level — exact signatures settle during implementation:

**Lifecycle:** open a store at a path (creating and migrating as needed); close it; a context-manager form for tests and callers.

**Node writes:** create a node under a parent; update a node's status; update a node's CF/SQ reference fields.

**Node reads:** get by id; list children of a node; list by project.

**The two Runner queries:**
- *What is runnable?* — nodes in `runnable` status for a project.
- *What is blocked and on whom?* — nodes in any `blocked_on_*` status for a project, each with its blocked-state record, so "on whom" is answered without a second call.

**Blocked-state writes:** write a blocked-state against a node (setting the node's status accordingly); fill a resolution slot (flipping the node to `runnable`). These are single operations, not two-step sequences the caller composes — the node status and the blocked-state record must never disagree, and making that the store's responsibility rather than the caller's is what guarantees it.

Everything is synchronous. Nothing blocks on anything external; there is nothing external.

## Integration Points

### Provides to Other Slices

- **102 (Resident Process):** the store API it hosts and becomes sole writer of, plus the schema its inspection surface reads.
- **103 (Durable Inbox):** the write API the apply loop commits through, and the resolution-slot operation an inbound human reply lands in.
- **104 (Findings & Verdicts):** the migration mechanism it adds tables through, the node ids its records attach to, and the reference fields its provenance correlates against.
- **105 (Change Feed):** the status transitions it emits notifications about.
- **106 (Contract Proof):** the public API it exercises end to end with no internal access.
- **Initiatives 120 / 140 / 160:** the documented contract they design against.

### Consumes from Other Slices

Nothing. This is the bottom of the stack.

## Success Criteria

### Functional Requirements

- A node tree can be created, read, updated, and queried by project, by status, and by parent.
- The runnable query and the blocked query return correct results across every value in the status vocabulary, including the empty case.
- A blocked-state record can be written against a node; filling its resolution slot flips that node to `runnable` in the same operation.
- The status vocabulary is defined exactly once as an enumeration and referenced everywhere; a value outside it raises rather than defaulting.
- The schema carries a version stamp, and a migration from version N to N+1 runs and is covered by a test.
- Every node is scoped to a project, and queries for one project never return another project's nodes.

### Technical Requirements

- `pyproject.toml` exists with the mandated `[tool.ruff.lint]` selections (`E`, `F`, `W`, `I`, `UP`, `BLE`, `ASYNC`, `B`) and `[tool.pyright]` in strict mode covering `src` and `tests`.
- `ruff check`, `ruff format --check`, and `pyright` all pass clean.
- `pytest` passes, with tests written alongside implementation rather than appended at the end.
- Every SQL statement and column name lives in `sql.py`; no SQL string appears elsewhere in the package.
- Source files stay near the ~300-line guideline.
- The public API carries docstrings sufficient for a downstream author.

### Integration Requirements

- Contract documentation is complete enough that initiative 120's slice design can proceed against it without reading the store implementation. This is the criterion that actually gates downstream work, and it is checked by a person reading the document, not by a test.
- The migration mechanism is proven, so slices 102–106 can add tables without redesigning it.

### Verification Walkthrough

None of these commands exist yet; this slice creates them. After implementation:

**1. The scaffold is real.**

```bash
cd /Users/manta/source/repos/manta/amoeba
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pyright
```

Expect clean output from all three. `pyright` reporting zero errors across `src` and `tests` is the gate, not a TODO.

**2. The suite passes.**

```bash
uv run pytest -v
```

Expect the model, store, migration, and query tests green.

**3. Drive the contract by hand.** This is the demo that matters — it is the slice's claim, executed:

```bash
uv run python
```

```python
from amoeba.store import Store, NodeStatus

with Store.open_temporary() as store:          # throwaway store, not the real one
    initiative = store.create_node(project_id="demo", kind="initiative", ...)
    slice_node = store.create_node(project_id="demo", parent_id=initiative.id, ...)

    print(store.runnable(project_id="demo"))   # -> the nodes awaiting work

    store.block(slice_node.id, kind=NodeStatus.BLOCKED_ON_HUMAN, context=...)
    print(store.blocked(project_id="demo"))    # -> node + who it is blocked on

    store.resolve(slice_node.id, resolution=...)
    print(store.runnable(project_id="demo"))   # -> slice_node is back
```

The observable claim: a blocked node disappears from the runnable set, appears in the blocked set with its blocker identified, and returns to runnable when — and only when — its resolution slot is filled. That is checkpoint-as-persisted-blocked-state, demonstrated.

**4. Migrations actually migrate.**

```bash
uv run pytest tests/test_migrations.py -v
```

The test opens a store at version N, applies the migration, and asserts the stamp advanced and the data survived. A store stamped newer than the code raises rather than silently proceeding.

**5. Inspect the file.** The store is a real SQLite database; `sqlite3 <path> .schema` shows the tables, and status values are readable strings because the vocabulary is a `StrEnum`. Slice 102's inspection surface builds on this.

## Risk Assessment

### Technical Risks

**The schema is hard to change once downstream initiatives depend on it.** This is the slice plan's stated Medium risk and it is the genuine one. Initiatives 120, 140, and 160 all code against this contract; a shape that turns out wrong is expensive in proportion to how much has been built on it.

### Mitigation Strategies

- **The migration mechanism ships in this slice, not later.** Schema change is expected and made routine from the first commit rather than treated as an exception.
- **The contract is narrow on purpose.** Findings, verdicts, journals, inbox, and feed are all excluded. The smaller the surface committed to now, the less there is to get wrong — and slices 102–106 each extend it with a concrete consumer in hand rather than a guess.
- **Slice 106 exists precisely to falsify the contract** from the outside before initiative 120 commits to it, and slice 102 — the highest-risk slice in the sequence — was deliberately placed immediately after this one so its pressure lands early.

## Implementation Notes

### Development Approach

Suggested order within the slice:

1. Scaffold — `pyproject.toml`, tool configuration, `src/`/`tests/` layout. Verify `ruff` and `pyright` run clean on an empty package before writing store code, since the Python rules require the enforcement config to be real before substantive work.
2. `models.py` — the dataclasses and the status `StrEnum`. Pure, trivially testable, and it fixes the vocabulary everything else references.
3. `migrations.py` + `001_initial.sql` — the runner and the initial schema, with the version stamp working before there is anything to migrate.
4. `sql.py` + `store.py` — statements and column constants, then CRUD, then the two queries.
5. The `002_*` migration exercising N→N+1.
6. Contract documentation.

Tests accompany each step. The store is small enough that mocking is unnecessary and counterproductive: tests run against a real throwaway SQLite database created by the fixture.

### Special Considerations

**Test database safety.** The project's testing rules are explicit here, from a real incident. The `conftest.py` fixture creates its own throwaway store and may only destroy what it created. No test touches the central per-supervisor store path. Because this store is a local file rather than a server database there is no production URL variable in play — but the rule that a fixture destroys only what it made is followed exactly, and the fixture's scope is stated in its docstring.

**No load-test tier.** The Python rules require load tests for code on simulation, network, concurrency, or environment-layer paths. This slice is a synchronous in-process library on none of those paths. Concurrency enters with the resident process in slice 102, which is where that requirement attaches.
