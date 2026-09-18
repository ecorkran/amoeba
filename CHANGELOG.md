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

- Slice 101: Python project scaffold — `pyproject.toml` with the mandated ruff, pyright strict, pytest, and uv configuration.
- Slice 101: SQLite-backed lifecycle node store — project-keyed node tree, closed `StrEnum` vocabularies, and blocked states with an explicit resolution slot.
- Slice 101: `block()` and `resolve()` as single store operations, so node status and blocked-state can never disagree.
- Slice 101: the two Runner queries — *what is runnable?* and *what is blocked and on whom?* — both project-scoped and index-backed.
- Slice 101: schema version stamp and numbered-migration runner, with a trivial `002` migration proving N→N+1 end to end.
- Slice 101: typed failure modes for lock contention, corrupt files, permission errors, and failed commits — none degrading to a default or fallback store.
- Slice 101: central per-supervisor store path resolution (`AMOEBA_STORE_DIR` → XDG → `~/.config/amoeba`), project-keyed and pure.
- Slice 101: contract documentation at `docs/store-contract.md`, sufficient to design a consumer without reading the implementation.

### Fixed

- Slice 101 (code review): `create_node` and `update_node_status` refuse blocked statuses, so `block()`/`resolve()` are structurally the only writers of blocked state.
- Slice 101 (code review): schema-level invariant violations raise `StoreIntegrityError` instead of a raw `sqlite3.IntegrityError`; `open_temporary()` closes its connection on a failed migration, matching `open()`.
