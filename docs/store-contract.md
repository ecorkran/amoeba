---
docType: reference
project: amoeba
slice: store-foundation-and-node-model
dateCreated: 20260917
dateUpdated: 20260917
status: complete
---

# The Amoeba Store Contract

This document is the contract for `amoeba.store`. It is written so that a slice
design in initiative 120, 140, or 160 can proceed **without reading the store
implementation**. If you find yourself opening `store.py` to answer a design
question, that is a gap in this document — say so.

## What the store is

One SQLite file holding a project-keyed tree of lifecycle nodes, plus the
blocked states that record what any node is waiting on.

The load-bearing idea: **a checkpoint is a persisted blocked-state, not a
blocking call.** A node blocked with an unfilled resolution slot *is* the
checkpoint. Nothing waits on a socket; the block survives a restart because it
is a row. Everything that makes Amoeba async by construction follows from this.

## What the store is not

- **Not a process.** This is a synchronous, in-process library. The resident
  process that hosts it is slice 102.
- **Not a single-writer enforcer.** See [Writer model](#writer-model) — this
  matters and is easy to assume wrongly.
- **Not a parser.** CF and SQ values are stored opaquely. See
  [Reference fields](#reference-fields).
- **Not a journal.** Issued commands, findings, verdicts, the inbox, and the
  change feed belong to slices 102–105. Nothing about them is modeled here.

## Importing

Everything below is exported from `amoeba.store` directly:

```python
from amoeba.store import Store, Node, NodeKind, NodeStatus, BlockedKind
```

`sql`, `mapping`, `migrations`, `paths`, and `_base` are internal. They are not
re-exported and are not contract. A test (`tests/test_public_api.py`) pins the
export set, so this list cannot drift silently.

## Vocabularies

All vocabularies are `StrEnum`, so the values stored in the database file are
readable strings — slice 102's inspection surface reads them directly.

**A value outside a vocabulary is an error, not a default.** Reading a row whose
status is not in `NodeStatus` raises `UnknownVocabularyValueError` rather than
returning a partially-populated object. Do not write code that expects a
fallback; there is none.

### `NodeStatus`

| Value | Meaning |
| --- | --- |
| `runnable` | Awaiting work. Returned by `runnable()`. |
| `in_progress` | Work has started. Not runnable, not blocked. |
| `blocked_on_human` | Waiting on a person. Returned by `blocked()`. |
| `blocked_on_judge` | Waiting on a Judge pseudopod. Returned by `blocked()`. |
| `blocked_on_sq_checkpoint` | Waiting on a Squadron checkpoint. Returned by `blocked()`. |
| `done` | Finished. Terminal. |

`BLOCKED_STATUSES` is the frozenset of the three `blocked_on_*` values. Use it
rather than string-prefix tests or a hand-kept list of your own.

### `NodeKind`

`initiative`, `phase_or_artifact`, `slice`, `gate`. What a node represents in
the lifecycle tree.

### `BlockedKind`

`human`, `judge`, `sq_checkpoint`. What a blocked node is waiting on. Parallel
to the blocked statuses but a distinct vocabulary: the status says *that* the
node is blocked, this says *on whom*.

`BLOCKED_KIND_TO_STATUS` maps each blocker kind to the status it implies. The
store applies it for you — you never choose the status when blocking.

## Types

All are frozen dataclasses. They are transfer objects, not ORM rows: mutating
one changes nothing in the database.

- **`Node`** — `id`, `project_id`, `kind`, `status`, `title`, `parent_id`,
  `cf`, `sq`, `created_at`, `updated_at`.
- **`CFReference`** — `project`, `phase`, `slice_name`, `artifact_path`.
- **`SQReference`** — `run_id`, `review_artifact_path`, `reviewed_sha`.
- **`Resolution`** — `resolved_by`, `detail`, `resolved_at`.
- **`BlockedState`** — `id`, `node_id`, `kind`, `context`, `resolution`,
  `created_at`, `updated_at`, plus an `is_resolved` property.
- **`BlockedNode`** — a `node` and its `blocked_state`, returned by `blocked()`.

### Node identity

`Node.id` is a store-generated opaque string. It is deliberately **not** derived
from CF coordinates: a node's CF pointers can change — a slice is renumbered, an
artifact path moves — without the node becoming a different node. Correlate on
`id`; never reconstruct it.

### Reference fields

`CFReference` and `SQReference` are held as **opaque, unparsed values**. The
store writes them and reads them back verbatim. It does not validate their
shape, does not decompose a Squadron run id into its date/slug/uuid parts, and
does not resolve artifact paths.

This is a boundary, not an oversight. Slice 104 correlates provenance against
these fields, and the Runner — not the store — parses CF and SQ output. If you
need a parsed value, parse it in your own slice and store the result in a field
your slice owns.

## Lifecycle

```python
store = Store.open(path)  # explicit path
store = Store.open(project_id="amoeba")  # central per-supervisor path
store = Store.open_temporary()  # throwaway, in-memory
store.close()
```

All three support the context-manager form, which releases the connection on
normal **and** exception exit:

```python
with Store.open(path) as store:
    ...
```

`open()` creates parent directories, connects, sets WAL journal mode and the
busy timeout, then migrates the schema to the version the code expects. Passing
neither `path` nor `project_id` raises `ValueError` rather than guessing.

`busy_timeout_seconds` may be passed to `open()`; it defaults to the named
constant and exists so contention tests need not wait the production timeout.

## Node writes

| Method | Effect |
| --- | --- |
| `create_node(*, project_id, kind, title, parent_id=None, status=RUNNABLE, cf=None, sq=None)` | Creates a node and returns it, with its generated `id`. Raises `NodeNotFoundError` if `parent_id` names no node. |
| `update_node_status(node_id, status)` | Sets status, validated against the vocabulary. Returns the updated node. |
| `update_cf_reference(node_id, cf)` | Replaces all CF fields. The node's `id` is unchanged. |
| `update_sq_reference(node_id, sq)` | Replaces all SQ fields. The node's `id` is unchanged. |

`project_id` is required on every node from the first row written. This is the
architecture's "project is a first-class key from day one" — it does not mean
multi-project supervision exists yet.

**No write returns a status code you can ignore.** Failures raise.

Do not call `update_node_status` to block or unblock a node — use `block()` and
`resolve()`, which keep status and blocked-state consistent.

## Node reads

| Method | Returns |
| --- | --- |
| `get_node(node_id)` | The node, or `None` if there is none. Absence is not an error. |
| `nodes_for_project(project_id)` | Every node in the project, oldest first. |
| `children_of(node_id)` | Direct children only, oldest first. |

## Blocked-state writes

These are the load-bearing operations of the slice.

```python
state = store.block(node_id, kind=BlockedKind.HUMAN, context="awaiting PM ruling")
state = store.resolve(node_id, resolved_by="pm", detail="add the task to 101")
```

**Each is one call and one transaction.** `block()` writes the blocked-state
record *and* sets the node's status together; `resolve()` fills the resolution
slot *and* flips the node back to `runnable` together.

There is deliberately **no public path that writes one half**. Node status and
blocked state cannot disagree, because the caller is never able to make them
disagree. Do not try to compose the two-step version yourself.

Invalid transitions raise `InvalidTransitionError` rather than silently
overwriting:

- blocking a node that is already blocked
- resolving a node that is not blocked

A node may be blocked again after resolution; each block is a separate record.

| Method | Returns |
| --- | --- |
| `blocked_state_for(node_id, *, include_resolved=False)` | The open blocked state, or the most recent one when `include_resolved=True`. `None` if there is none. |
| `all_blocked_states(node_id)` | Iterator over every blocked state the node has had, oldest first. |

## The two Runner queries

```python
store.runnable(project_id)  # -> list[Node]
store.blocked(project_id)  # -> list[BlockedNode]
```

**`runnable(project_id)`** returns nodes in `runnable` status for the project.

**`blocked(project_id)`** returns every node in any `blocked_on_*` status, each
already carrying its open blocked-state record — so *"on whom?"* is answered
**without a second call**. Do not follow up with `blocked_state_for()`; the
answer is in hand.

Both queries:

- are **project-scoped**: a query for one project never returns another's nodes
- use the `(project_id, status)` index
- return an **empty list** when there is nothing, which is not an error

## Writer model

**This library does not enforce single-writer.** It is stated here explicitly so
slice 102 knows what it is *adding* rather than discovering an assumption.

WAL journal mode is set at open, which permits concurrent readers alongside one
writer. Within this slice the caller owns writer discipline. Two processes
writing the same store will contend, and contention surfaces as
`StoreBusyError` once the busy timeout is exhausted — it is not prevented.

Slice 102's resident process is what makes the store single-writer in practice.

## Failure modes

Every failure raises a specific typed exception. **No failure path degrades to a
default, an empty result, or a fallback store** — a caller silently operating
against a throwaway store it did not ask for is the worst available outcome.

| Condition | Exception |
| --- | --- |
| Busy timeout exhausted under lock contention | `StoreBusyError` (names the contended operation) |
| File is not a readable SQLite database, or `schema_meta` is unreadable | `StoreCorruptError` |
| Store path or its parent cannot be created, read, or written | `StorePermissionError` (includes the resolved path) |
| Store is stamped at a schema version newer than the code | `StoreSchemaError` |
| Stored value outside a closed vocabulary, read back | `UnknownVocabularyValueError` |
| Node id does not exist | `NodeNotFoundError` |
| Block or resolve against a node in the wrong state | `InvalidTransitionError` |
| Store invariant violated by a write | `StoreIntegrityError` |

All inherit from `StoreError`, so `except StoreError` catches the family.

Notes on specific modes:

- **A corrupt store is never re-created, truncated, or treated as fresh.**
  Silently replacing it would destroy lifecycle history, which is exactly the
  state this component exists to protect.
- **There is no fallback location.** A permission failure raises; it does not
  quietly fall back to a temp path or an in-memory database.
- **A failed commit propagates.** Writes are transactional, so SQLite's own
  guarantees leave the database consistent; the store's obligation is to surface
  the failure rather than report success.

## Store locality

One store per **supervisor**, at a central path, **keyed by project** —
following the architecture's "resident process per supervisor, not per project".

Resolution precedence, highest first:

1. `AMOEBA_STORE_DIR` — used verbatim
2. `XDG_CONFIG_HOME` — yields `$XDG_CONFIG_HOME/amoeba`
3. `~/.config/amoeba` — the default, matching Squadron's `~/.config/squadron`

The project's store file is that directory plus `{project_id}.sqlite3`.

Resolution is a **pure computation**: it creates nothing and touches no
filesystem. Directory creation happens in `Store.open()`.

**There is no per-project override.** The design declines it deliberately —
adding one would put two locality paths in the foundation slice before any
consumer needs either. Do not add one without a PM decision.

## Migrations

`schema_meta` holds a single version stamp, read at open before anything else.
The runner applies numbered `.sql` files in order, each in a transaction,
advancing the stamp as it goes.

To add a schema change in your slice: add `src/amoeba/store/schema/00N_name.sql`
and bump `EXPECTED_SCHEMA_VERSION`. The mechanism is proven end to end — a
deliberately trivial `002` migration ships purely to exercise N→N+1 — so you are
adding a table onto working machinery, not debugging both at once.

**A store stamped newer than the code raises `StoreSchemaError`.** It is never
silently downgraded.

## Testing against the store

Open a throwaway store; never the central one. `tests/conftest.py` provides
`store_file` (a path under `tmp_path`) and `store` (an open store at that path).
A guard test (`tests/test_store_safety.py`) scans test modules for references to
the central-path resolver and fails on offenders, so the property is checked
mechanically rather than assumed. The scan is AST-based and therefore
multiline-aware.

## Future work

**Storage engine reversal trigger (PM).** The decision to use raw stdlib
`sqlite3` rather than SQLAlchemy Core + Alembic should be revisited if *either*:

- schema churn across slices 102–106 makes hand-written migrations painful, or
- the hand-rolled layer becomes recurring maintenance — repeated tweaks and bug
  fixes in the store plumbing itself.

Recorded so the switch is a decision made on evidence rather than a drift. The
mitigation that makes raw viable is structural: every SQL statement and every
column name lives in `sql.py`, so a column-name typo is a single-definition
concern.
