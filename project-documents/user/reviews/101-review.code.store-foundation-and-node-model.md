---
docType: review
layer: project
reviewType: code
slice: store-foundation-and-node-model
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/101-slice.store-foundation-and-node-model.md
aiModel: moonshotai/kimi-k3
status: complete
dateCreated: 20260917
dateUpdated: 20260917
reviewedSha: a7536a850ba815590d247d778cb551f06c0c35e1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
findings:
  - id: F001
    severity: concern
    category: design-consistency
    summary: "Contract claims \"no public path that writes one half\" but `update_node_status` is exactly that"
    location: "docs/store-contract.md:184"
  - id: F002
    severity: concern
    category: documentation
    summary: "Stale docstring references `store.py` as the mapping home"
    location: "src/amoeba/store/models.py:5"
  - id: F003
    severity: concern
    category: error-handling
    summary: "`StoreIntegrityError` is exported and contract-documented but never raised"
    location: "src/amoeba/store/models.py:182"
  - id: F004
    severity: note
    category: error-handling
    summary: "`open_temporary()` does not translate connect/migrate failures into typed store errors"
    location: "src/amoeba/store/store.py:131"
  - id: F005
    severity: note
    category: database
    summary: "Schema DDL is not idempotent (`IF NOT EXISTS` absent); acceptable given the version-gate design"
    location: "src/amoeba/store/schema/001_initial.sql:1"
  - id: F006
    severity: pass
    category: convention-adherence
    summary: "Tooling, typing, error-handling, and test-safety conventions are correctly followed"
    location: "pyproject.toml:1"
---

# Review: code — slice 101

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k3

## Findings

### [CONCERN] Contract claims "no public path that writes one half" but `update_node_status` is exactly that

The contract (line 184) and `blocking.py` module docstring both assert as the core invariant: *"There is deliberately **no public path that writes one half**. Node status and blocked state cannot disagree, because the caller is never able to make them disagree."* This is false as shipped. `update_node_status(node_id, status)` is a public, contract-documented method (contract line 150) that writes the status half directly with no blocked-state coordination. A caller can set a node to `blocked_on_human` (creating a blocked node with no `blocked_states` row, violating the partial-unique-index assumption that an open blocked state exists) or set a blocked node back to `runnable` (leaving an orphaned open blocked-state row, which then breaks `resolve()`'s `rowcount != 1` and `blocked_state_for` lookups). The only mitigation is a prose "Do not call…" at line 160 — a convention, not the structural guarantee the invariant claims. Either the invariant statement needs to be scoped down to the block/resolve pair, or `update_node_status` needs to refuse transitions into/out of `BLOCKED_STATUSES`. As written, the load-bearing guarantee of the slice is contradicted by its own public API. (Confirmed against `src/amoeba/store/nodes.py:101` and the contract table.)

### [CONCERN] Stale docstring references `store.py` as the mapping home

`models.py` line 4–5 says: *"the mapping between these types and database rows lives in one place, in ``store.py``."* Mapping actually lives in `mapping.py` (`map_node` / `map_blocked_state`); `store.py` only composes the mixins. Similarly `sql.py`'s module docstring says statements and mapping code live in ``store.py``. These are leftover references from before the mapping was extracted into its own module and will mislead a reader looking for the single mapping site. Low stakes, but this is precisely the "single definition site" the design leans on, so the pointer should be correct.

### [CONCERN] `StoreIntegrityError` is exported and contract-documented but never raised

`StoreIntegrityError` is part of the exported contract (`__init__.py`, pinned in `tests/test_public_api.py`) and appears in the contract's failure-mode table (line 248: "Store invariant violated by a write"). But nothing in `src/` raises it — a write that violates a store invariant (e.g. the FK or unique-open-blocked-state index firing) currently propagates a raw `sqlite3.IntegrityError`, not the typed error the contract promises. Either the store should translate `sqlite3.IntegrityError` to `StoreIntegrityError` at the `_execute` boundary (parallel to the existing `StoreBusyError` translation), or the exception and its contract row should be removed until a slice needs it. Exporting a documented failure mode that can never occur is a silent contract gap.

### [NOTE] `open_temporary()` does not translate connect/migrate failures into typed store errors

`Store.open()` wraps directory creation and connect failures in `StorePermissionError`/`StoreCorruptError` and closes the connection on a failed `migrate`. `open_temporary()` calls `_connect` and `migrate` directly: `_connect` failures are still typed, but a `migrate` failure on the in-memory connection is not wrapped in the close-and-raise cleanup that `open()` applies, and the corrupt/permission typing differs between the two open paths. In practice an in-memory connect/migrate rarely fails, so this is informational — but the two constructors are not symmetric in their failure guarantees, and the contract presents them as equivalent entry points.

### [NOTE] Schema DDL is not idempotent (`IF NOT EXISTS` absent); acceptable given the version-gate design

The SQL rules prefer `IF NOT EXISTS` for idempotent operations. The migration files use bare `CREATE TABLE` / `ALTER TABLE`. This is safe here because `migrate()` only applies files strictly above the current stamp and the runner is proven N→N+1, so re-application cannot occur through the supported path. The design intentionally relies on the version gate rather than idempotent DDL. Worth a one-line note in the migrations docstring so a future migration author doesn't "fix" it by adding `IF NOT EXISTS` and silently masking a genuine double-apply bug — or, conversely, adopt `IF NOT EXISTS` as defense-in-depth. Noting only because the rule and the implementation differ; the implementation is internally consistent.

### [PASS] Tooling, typing, error-handling, and test-safety conventions are correctly followed

Verified the mechanical requirements that make the prose rules real: `[tool.ruff.lint]` selects at least `["E","F","W","I","UP","BLE","ASYNC","B"]` with `line-length = 88`; `[tool.pyright]` is `strict` over `src` and `tests` with `pythonVersion = "3.12"`; `requires-python = ">=3.12"`. The package uses `from __future__ import annotations`, built-in generics, `X | None` unions, `StrEnum`, frozen dataclasses, and pathlib. Every `try/except` in the store catches a specific exception and re-raises as a typed error with `logger.exception` — no bare or swallowed handlers. Tests use pytest with `conftest.py` fixtures, parametrize edge cases, and the AST-based guard in `tests/test_store_safety.py` is genuinely multiline-aware (and self-verifying via `test_scan_finds_a_wrapped_reference`). Tests target only throwaway stores under `tmp_path`, never the central path.

### Run Digest

- Response length: 6443 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 0
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
