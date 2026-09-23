---
docType: changelog
scope: project-wide
---

# Changelog

All notable changes to Amoeba will be documented in this file. Entries should be
concise, ideally 1-2 lines. Current changes not yet pushed and tagged will
accumulate in [Unreleased].

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Slice 103: the durable inbox — `amoeba.inbox.submit()` writes one fsync-durable file whether or not the process runs; the only way a part outside the process contributes state.
- Slice 103: `InboxTenant`, the first real tenant — applies each submission exactly once per id, quarantines what cannot be attributed, and bounds a failing apply with an on-disk attempt counter that parks the file in `inbox/failed/`.
- Slice 103: schema version 4 (migration `004`) — `inbox_submissions` and `messages`, with receiver-assigned `applied_seq` / `seq` as the authoritative order, and a backfill of escalations for open human blocks.
- Slice 103: three submission kinds — `create_project`, `resolution` (targets a blocked state, never redirected to a newer block), and `intent`.
- Slice 103: the `intent` and `escalation` message channels, with `messages(after_seq=…)` as a replay primitive readable through a read-only handle, plus `pending_intents` / `acknowledge_message` for the Runner.
- Slice 103: runtime project creation via `host.open_project` — a project created through the inbox is usable at once, without a restart.
- Slice 103: `amoeba submit create-project|resolution|intent`, with flags derived from each kind's payload model, and exit code `SUBMISSION_REFUSED` (9).
- Slice 103: `amoeba inspect inbox|submissions|messages`, and `--inbox-batch-size` / `--inbox-max-attempts` on `amoeba start`.
- Slice 103: `docs/inbox-contract.md`, and a concurrent-submitter load test proving exactly-once across repeated `SIGKILL`s.
- Slice 102: command journal in the store (migration `003`) — an entry is committed *before* its side effect is issued, so a crash leaves a durable record of what may have been in flight.
- Slice 102: `journal_issue` / `journal_resolve` / `journal_escalate`, with parameters validated at issue time so an entry can always be reconciled later.
- Slice 102: `Store.open_read_only` — a genuine SQLite `mode=ro` handle that never migrates and never creates, measured against this project's Python and SQLite build.
- Slice 102: the resident process — `amoeba start` / `stop` / `status`, single-instance enforcement via an advisory `flock`, and signal-driven graceful shutdown with a bounded grace period.
- Slice 102: reconcile-by-observation recovery — every journaled-but-unresolved command is reconciled by *observing* the external system, never by re-issuing; every ambiguity becomes a `blocked_on_human` node.
- Slice 102: two observers — Squadron runs-directory matching (subset-on-params, four candidate conditions) and Context Forge read-back — both tested against real captured upstream output.
- Slice 102: the `Tenant` protocol and host loop that slices 103 and 120 plug into. This slice ships **no tenants**: the process starts, recovers, idles, and stops.
- Slice 102: `amoeba inspect` — read-only listings for projects, nodes, blocked states, and journal entries, human-readable and `--json`, declared in one registry that slice 104 extends by registering.
- Slice 102: `pydantic` as the project's first runtime dependency, used only at the two external parsing boundaries.
- Slice 102: a `tests/load/` tier with crash-loop and recovery-scale tests, excluded from the default suite and gated separately in CI.
- Slice 102: an AST guard test failing if any module other than `process/host.py` opens a store read-write.
- Slice 102: contract documentation at `docs/process-contract.md`, and a Journal section plus corrected writer-model section in `docs/store-contract.md`.
- Slice 101: Python project scaffold — `pyproject.toml` with the mandated ruff, pyright strict, pytest, and uv configuration.
- Slice 101: SQLite-backed lifecycle node store — project-keyed node tree, closed `StrEnum` vocabularies, and blocked states with an explicit resolution slot.
- Slice 101: `block()` and `resolve()` as single store operations, so node status and blocked-state can never disagree.
- Slice 101: the two Runner queries — *what is runnable?* and *what is blocked and on whom?* — both project-scoped and index-backed.
- Slice 101: schema version stamp and numbered-migration runner, with a trivial `002` migration proving N→N+1 end to end.
- Slice 101: typed failure modes for lock contention, corrupt files, permission errors, and failed commits — none degrading to a default or fallback store.
- Slice 101: central per-supervisor store path resolution (`AMOEBA_STORE_DIR` → XDG → `~/.config/amoeba`), project-keyed and pure.
- Slice 101: contract documentation at `docs/store-contract.md`, sufficient to design a consumer without reading the implementation.

### Changed

- Slice 103: a `HUMAN` block now writes an escalation message in the same transaction; `block()` gains an optional `payload`. Every block goes through one internal writer.
- Slice 103: `journal_escalate` now writes an escalation carrying the journal entry id, including on its already-blocked branch, where it points at the existing open block.
- Slice 103: `amoeba start` registers `InboxTenant` first, where slice 102 registered no tenants.
- Slice 103: `host.project_ids` grows at runtime and must not be cached.
- Slice 103: read-write store opening moved from `process/host.py` to `process/project_stores.py`; the writer guard's one permitted module moved with it.

### Fixed

- Slice 101 (code review): `create_node` and `update_node_status` refuse blocked statuses, so `block()`/`resolve()` are structurally the only writers of blocked state.
- Slice 101 (code review): schema-level invariant violations raise `StoreIntegrityError` instead of a raw `sqlite3.IntegrityError`; `open_temporary()` closes its connection on a failed migration, matching `open()`.
