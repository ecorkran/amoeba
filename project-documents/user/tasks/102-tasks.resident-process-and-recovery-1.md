---
docType: tasks
slice: resident-process-and-recovery
project: amoeba
lld: user/slices/102-slice.resident-process-and-recovery.md
dependencies: [101]
projectState: Slice 101 shipped and merged — the store package exists at schema version 2 with nodes, blocked states, migrations, and docs/store-contract.md. There is no process, no CLI, no journal, and no runtime dependency. This slice lands all four.
dateCreated: 20260919
dateUpdated: 20260921
status: not_started
---

## Context Summary

- Working on the **resident-process-and-recovery** slice (102), the second slice of initiative 100 and the highest-risk one in the sequenced set.
- **Current state:** slice 101 is merged. `src/amoeba/store/` provides `Store.open`, node CRUD, `block()`/`resolve()`, a numbered-migration runner at `EXPECTED_SCHEMA_VERSION = 2`, central path resolution reading `AMOEBA_STORE_DIR`, and a typed `StoreError` family. `pyproject.toml` declares **zero** runtime dependencies. Nothing runs as a process and nothing enforces the sole-writer model the contract document describes.
- **Dependencies:** slice 101 only, through its public contract.
- **What this slice delivers:** the resident process (`amoeba start`/`stop`/`status` with single-instance enforcement and graceful shutdown), the command journal and its reconcile-by-observation recovery, the `amoeba inspect` read-only CLI, and a `tests/load/` tier. It ships **no tenants** — the process starts, recovers, idles, and stops.
- **Key design commitments** (from the LLD — do not revisit them here): crash-only, so graceful stop and `kill -9` converge on one recovery path; journal commits *before* the side effect and recovery never re-issues, only observes; every ambiguity becomes `blocked_on_human` rather than a guess; `fcntl.flock` is the truth about liveness and the PID file is informational; a synchronous host loop with no per-tick timeout.
- **Next planned slice:** 103 (Durable Inbox and Message Queue), which plugs its apply loop into this slice's `Tenant` seam.

**Reading note for the executing developer:** this file does not restate the LLD. Where a task says "per the LLD," open `user/slices/102-slice.resident-process-and-recovery.md` at the named section and follow it. Exact DDL, column names, signatures, and error messages are settled during implementation against that design.

**This file covers Sections 1–4** (journal, read-only open, recovery protocol, observers). Sections 5–9 (instance lock, host loop, CLI, guard test, load tier, docs) are in `102-tasks.resident-process-and-recovery-2.md`.

---

## Section 1: The Command Journal in the Store

### Task 1.1: Define the journal vocabularies and the JournalEntry model
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 2
**Objective**: Create `src/amoeba/store/journal_models.py` holding every journal vocabulary and the entry dataclass, so no journal string literal appears anywhere else in the codebase.

**Steps**:
- [ ] Create `journal_models.py` as a sibling of `models.py` (which is at 200 lines and is not to be extended), per the LLD's Component Structure
- [ ] Define `CommandKind`, `JournalOutcome`, `JournalResolver` as `StrEnum`s with exactly the members the LLD's "Closed vocabularies" section lists
- [ ] Define the frozen `JournalEntry` dataclass with the fields the LLD's API Contracts section names, plus the `is_resolved` property
- [ ] Define the required-parameter-keys mapping — `CommandKind` → the keys `journal_issue` validates — as a single module-level constant, not as conditionals at the call site
- [ ] Follow the slice 101 convention in `models.py` for frozen dataclasses and enum style

**Success Criteria**:
- [ ] Every journal vocabulary value is defined exactly once; `grep` for any outcome or kind string literal finds it only in this module
- [ ] `JournalEntry` is frozen and `is_resolved` derives from `outcome`, storing no redundant flag
- [ ] `uv run pyright` clean in strict mode
- [ ] No import of `sqlite3` or any SQL in this module

**Files to Create**: `src/amoeba/store/journal_models.py`

---

### Task 1.2: Test the journal vocabularies and model
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 1
**Objective**: Pin the vocabularies and the entry model before any SQL depends on them.

**Steps**:
- [ ] Add tests asserting each enum's exact member set — a test that fails if a member is added or renamed without deliberate intent
- [ ] Assert `JournalEntry` immutability and that `is_resolved` is `False` when `outcome` is `None` and `True` for every outcome member
- [ ] Assert the required-parameter mapping covers every `CommandKind` member, so a new kind cannot be added without declaring its keys

**Success Criteria**:
- [ ] Tests fail if a vocabulary member is added without updating the test
- [ ] Tests fail if a `CommandKind` is added with no required-keys entry
- [ ] `uv run pytest` passes

**Files to Create**: `tests/test_journal_models.py`

---

### Task 1.3: Write migration 003 and the journal SQL module
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 3
**Objective**: Add the `command_journal` table and centralize every journal statement and column name in `sql_journal.py`.

**Steps**:
- [ ] Create `src/amoeba/store/schema/003_command_journal.sql` with the `command_journal` table and the partial index per the LLD's Database / Storage Schema section
- [ ] Bump `EXPECTED_SCHEMA_VERSION` to 3 in `migrations.py`
- [ ] Create `sql_journal.py` holding every journal statement and column name, following the structure of `sql.py` exactly (which stays at 306 lines and is not to be extended)
- [ ] Confirm the foreign key from `node_id` to `nodes` is declared, and that the partial index matches the recovery query's shape
- [ ] Confirm the new `.sql` file is covered by the existing wheel `artifacts` glob in `pyproject.toml`

**Success Criteria**:
- [ ] Migration file follows the numbered-migration convention slice 101 established
- [ ] No journal SQL string or column name exists outside `sql_journal.py`
- [ ] `uv run ruff check .` and `uv run pyright` clean

**Files to Create**: `src/amoeba/store/schema/003_command_journal.sql`, `src/amoeba/store/sql_journal.py`
**Files to Modify**: `src/amoeba/store/migrations.py`

---

### Task 1.4: Test the migration from version 2 to 3
**Owner**: Junior AI
**Dependencies**: Task 1.3
**Effort**: 2
**Objective**: Prove migration `003` is the first real exercise of the mechanism slice 101 proved with a trivial `002`, and that existing data survives it.

**Steps**:
- [ ] Add a test that creates a store at schema version 2, populates nodes and at least one blocked state, then opens it and asserts it reaches version 3 with all prior rows intact
- [ ] Assert the `command_journal` table and its partial index exist after migration
- [ ] Assert a fresh store reaches version 3 directly
- [ ] Assert the existing newer-than-code rule still holds — a store stamped above 3 raises rather than downgrading

**Success Criteria**:
- [ ] A version-2 store with data upgrades in place with no row loss
- [ ] Both the fresh-store and upgrade paths land on identical schema
- [ ] `uv run pytest` passes

**Files to Modify**: `tests/test_migrations.py`

---

### Task 1.5: Implement JournalMixin write operations
**Owner**: Junior AI
**Dependencies**: Task 1.4
**Effort**: 3
**Objective**: Implement `journal_issue`, `journal_resolve`, and `journal_escalate` in `src/amoeba/store/journal.py`, joining `Store` alongside the existing node and blocking mixins.

**Steps**:
- [ ] Create `journal.py` with `JournalMixin` following the pattern of `nodes.py` and `blocking.py` over `_base.py`
- [ ] Implement `journal_issue(node_id, *, kind, parameters)` — validate the required keys for the kind (raising before any write), insert an unresolved entry, and **commit before returning**, per the LLD
- [ ] Implement `journal_resolve(entry_id, *, outcome, result, resolved_by=ISSUER)`, raising `InvalidTransitionError` on an already-resolved entry
- [ ] Implement `journal_escalate(entry_id, *, reason)` as **one transaction**: set outcome `unknown` and block the node on `HUMAN` with a context naming the entry
- [ ] Handle the already-blocked node as an **explicit branch** — check first and skip the block — not by catching `InvalidTransitionError`, per the LLD
- [ ] Raise `NodeNotFoundError` from `journal_issue` for an unknown node
- [ ] Wire `JournalMixin` into `Store` and export the new names from `amoeba.store`

**Success Criteria**:
- [ ] `journal_issue` commits before returning, so a crash immediately after it leaves a durable unresolved entry
- [ ] `journal_escalate` writes the outcome and the block atomically — neither can land without the other
- [ ] The already-blocked path writes no second blocked state and raises nothing
- [ ] Every statement used comes from `sql_journal.py`
- [ ] `uv run pyright` clean; source file stays near the 300-line budget

**Files to Create**: `src/amoeba/store/journal.py`
**Files to Modify**: `src/amoeba/store/store.py`, `src/amoeba/store/__init__.py`

---

### Task 1.6: Implement JournalMixin read queries
**Owner**: Junior AI
**Dependencies**: Task 1.5
**Effort**: 2
**Objective**: Add `unresolved_journal_entries` (what recovery consumes) and `journal_entries` (what inspection consumes).

**Steps**:
- [ ] Implement `unresolved_journal_entries(project_id)` returning oldest-first, served by the partial index from Task 1.3
- [ ] Implement `journal_entries(project_id, *, node_id=None, include_resolved=True)`
- [ ] Map rows to `JournalEntry` through the existing `mapping.py` conventions, decoding the JSON `parameters` and `result` columns
- [ ] Export both from `amoeba.store`

**Success Criteria**:
- [ ] `unresolved_journal_entries` returns only entries with a NULL outcome, oldest first
- [ ] Both queries round-trip `parameters` and `result` mappings without mutation
- [ ] `uv run pyright` clean

**Files to Modify**: `src/amoeba/store/journal.py`, `src/amoeba/store/__init__.py`

---

### Task 1.7: Test the journal store API
**Owner**: Junior AI
**Dependencies**: Task 1.6
**Effort**: 3
**Objective**: Cover every journal contract claim, including the ones recovery depends on.

**Steps**:
- [ ] Test `journal_issue` with a missing required parameter raises and **writes nothing** (assert the table is empty afterward)
- [ ] Test `journal_issue` against an unknown node raises `NodeNotFoundError`
- [ ] Test `journal_resolve` closes an entry and rejects a second resolve with `InvalidTransitionError`
- [ ] Test `journal_escalate` sets outcome `unknown` **and** blocks the node, and that the blocked-state context names the entry
- [ ] Test `journal_escalate` against an already-blocked node marks the entry and writes no second blocked state — assert the open-blocked-state count is exactly one
- [ ] Test `unresolved_journal_entries` ordering and that resolved entries disappear from it
- [ ] Test that additional non-required parameter keys are stored and returned unchanged
- [ ] Add the new public names to the `tests/test_public_api.py` pin

**Success Criteria**:
- [ ] All seven behaviors above are asserted
- [ ] The already-blocked test would fail if the implementation caught `InvalidTransitionError` instead of branching
- [ ] `uv run pytest` passes

**Files to Create**: `tests/test_journal.py`
**Files to Modify**: `tests/test_public_api.py`

---

### Task 1.8: Commit the journal layer
**Owner**: Junior AI
**Dependencies**: Task 1.7
**Effort**: 1
**Objective**: Checkpoint the pure-library half of the slice while it is independently green.

**Steps**:
- [ ] Verify the working directory is the repository root and the branch is `102-slice.resident-process-and-recovery` (Phase 6 work; create it from the integration target per the project git rules if it does not exist — read `cf config get git.integration_branch` rather than assuming)
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright`
- [ ] Stage and commit, e.g. `feat(store): add command journal with issue, resolve, and escalate`

**Success Criteria**:
- [ ] Commit exists on the slice branch; working tree clean
- [ ] All three quality commands pass at this commit

---

## Section 2: Read-Only Store Access

### Task 2.1: Prove read-only open works against a WAL store
**Owner**: Junior AI
**Dependencies**: Task 1.8
**Effort**: 2
**Objective**: Resolve the LLD's second technical risk **first**, with evidence, before any code depends on the answer. SQLite needs the `-shm` file to read a WAL database, and `mode=ro` behavior varies across versions.

**Steps**:
- [ ] Write a test that creates a store, writes nodes, closes it so no writer is alive, then opens the file with SQLite `mode=ro` and reads those nodes — on the project's actual Python and SQLite build
- [ ] Repeat with the writer still alive in a separate process, which is the real inspection case
- [ ] Record the observed SQLite version and the result in the test as a comment
- [ ] **If it fails:** take the LLD's named fallback — a read-write handle the inspection code never writes through — and note it for Task 8.1 (the guard test must then also cover `cli/inspect.py`) and Section 9 (both contract documents must state the softened invariant, per the LLD's mitigation)

**Success Criteria**:
- [ ] The test runs and its outcome is recorded, whichever way it goes
- [ ] If the fallback is taken, the decision and its evidence are written into the task file or commit message — not applied silently
- [ ] No design decision here is made in advance of the measurement

**Files to Create**: `tests/test_read_only_open.py`

---

### Task 2.2: Implement Store.open_read_only
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 2
**Objective**: Add the read-only handle every out-of-process consumer uses, per the evidence from Task 2.1.

**Steps**:
- [ ] Implement `Store.open_read_only(path=None, *, project_id=None)` per the LLD's API Contracts table
- [ ] Ensure it **never migrates** — a store at an unexpected schema version raises `StoreSchemaError`, matching slice 101's newer-than-code rule
- [ ] Ensure it opens via SQLite `mode=ro` (or the Task 2.1 fallback, if that was the evidence)
- [ ] Export from `amoeba.store` and add to the public-API pin

**Success Criteria**:
- [ ] **If Task 2.1's evidence supported true `mode=ro`:** a write attempted through the handle fails rather than succeeding silently. **If Task 2.1 forced the fallback:** this criterion does not apply to `Store.open_read_only` itself — mutation safety instead rests entirely on the guard test (Task 8.1) restricting who calls it — and the task's completion note must say which branch was taken
- [ ] Opening a store at version 2 with code expecting 3 raises `StoreSchemaError` and does not migrate — assert the file's schema version is unchanged afterward (holds under either branch)
- [ ] Opening a non-existent store raises rather than creating one (holds under either branch)
- [ ] `uv run pyright` clean

**Files to Modify**: `src/amoeba/store/store.py`, `src/amoeba/store/__init__.py`, `tests/test_public_api.py`

---

### Task 2.3: Test read-only guarantees
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 2
**Objective**: Prove inspection can never mutate a store.

**Steps**:
- [ ] **If Task 2.1's evidence supported true `mode=ro`:** test that every write operation attempted through a read-only handle raises. **If the fallback was taken:** skip this assertion here — enforcement is the guard test's job — and mark the skip with a comment pointing at Task 8.1 rather than deleting the intent silently
- [ ] Test that `open_read_only` against a store needing migration raises and leaves the file's schema version untouched
- [ ] Test that `open_read_only` does not create a database file when none exists
- [ ] Test reading nodes, blocked states, and journal entries through the handle returns the same values as a read-write open

**Success Criteria**:
- [ ] Under true `mode=ro`: all four behaviors asserted; the no-create test checks the filesystem directly. Under the fallback: the same three non-mutation-enforcement behaviors asserted, plus a comment recording that write-rejection is covered by Task 8.1 instead
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(store): add read-only store open`

**Files to Modify**: `tests/test_read_only_open.py`

---

## Section 3: The Recovery Protocol

### Task 3.1: Define the Observer protocol and Observation types
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 2
**Objective**: Create `src/amoeba/process/recovery.py` with the protocol recovery is written against, knowing nothing about Squadron or Context Forge.

**Steps**:
- [ ] Create the `src/amoeba/process/` package with `__init__.py`
- [ ] Define `Observation = Adopt | NotApplied | Unknown` as frozen dataclasses per the LLD — `Adopt` carrying the result mapping, `Unknown` carrying a human-readable `reason` and any `candidates`
- [ ] Define the `Observer` protocol with `observe(entry) -> Observation`
- [ ] Define the observer registry type keyed by `CommandKind`
- [ ] Add no Squadron or CF imports to this module — that separation is the point

**Success Criteria**:
- [ ] The module imports nothing from `observers/`
- [ ] The three observation types are frozen and exhaustive under `pyright` strict — a `match` over them needs no fallback case
- [ ] `uv run pyright` clean

**Files to Create**: `src/amoeba/process/__init__.py`, `src/amoeba/process/recovery.py`

---

### Task 3.2: Define ProcessSettings
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 2
**Objective**: Create the single frozen dataclass holding every tunable, so no magic default appears at any call site.

**Steps**:
- [ ] Create `src/amoeba/process/settings.py` with a frozen `ProcessSettings` dataclass
- [ ] Include every tunable the LLD's Technical Requirements list names: idle interval, shutdown grace, stop timeout, clock tolerance, `cf` timeout, runs directory
- [ ] Define defaults **here and only here**; no `or`-style fallback defaults anywhere else
- [ ] Add **no** new environment variable reads — `AMOEBA_STORE_DIR` in `paths.py` stays the project's only environment read, per D3

**Success Criteria**:
- [ ] Every tunable has exactly one definition site
- [ ] `grep` for `os.environ` / `getenv` across `src/amoeba/` finds only `paths.py`
- [ ] The dataclass is frozen and fully typed under strict mode

**Files to Create**: `src/amoeba/process/settings.py`

---

### Task 3.3: Implement the reconcile loop
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 3
**Objective**: Implement recovery over a store and an observer registry, per the LLD's Data Flow section.

**Steps**:
- [ ] Implement the reconcile function: for each unresolved entry oldest-first, dispatch to the registered observer and apply `Adopt` → `journal_resolve(adopted)`, `NotApplied` → `journal_resolve(not_applied)`, `Unknown` → `journal_escalate`
- [ ] Treat a **missing observer** for a kind as `Unknown`, not as an error or a skip
- [ ] Reconcile **each entry in its own transaction**, so an interrupted recovery re-runs only what is still unresolved
- [ ] Set `resolved_by=recovery` on everything recovery writes
- [ ] Return a summary (counts by outcome) for the startup log line
- [ ] Log unexpected exceptions with `logger.exception` and re-raise, per the project exception rule — recovery that cannot complete aborts startup

**Success Criteria**:
- [ ] Recovery never issues a command or calls anything but observers and the store
- [ ] Per-entry transactions verified by a test that kills recovery partway
- [ ] A kind with no registered observer escalates rather than raising or silently passing
- [ ] Function stays near the 50-line budget; split helpers if not

**Files to Modify**: `src/amoeba/process/recovery.py`

---

### Task 3.4: Test recovery with fake observers
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 3
**Objective**: Prove the reconcile logic independently of any real upstream, using in-test observers that return each observation type on demand.

**Steps**:
- [ ] Test each observation type produces the correct outcome and `resolved_by=recovery`
- [ ] Test a kind with no registered observer becomes `unknown` with a blocked node
- [ ] Test **interrupted recovery idempotence**: reconcile a batch, simulate a crash partway, re-run, and assert each entry is reconciled exactly once and none is double-blocked
- [ ] Test that an observer raising an unexpected exception aborts recovery rather than being swallowed
- [ ] Test the summary counts match what was written
- [ ] Test recovery over an already-blocked node leaves exactly one open blocked state

**Success Criteria**:
- [ ] The idempotence test would fail if recovery used a single transaction for the batch
- [ ] The raising-observer test asserts the exception propagates and prior entries stay reconciled
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(process): add reconcile-by-observation recovery`

**Files to Create**: `tests/test_recovery.py`

---

## Section 4: The Observers

### Task 4.1: Capture real upstream fixtures
**Owner**: Junior AI
**Dependencies**: Task 3.4
**Effort**: 2
**Objective**: Copy **real** upstream files into the test fixtures, because a parser tested only against invented data provides false confidence (project parsing rule).

**Steps**:
- [ ] Copy real Squadron run files from `~/.config/squadron/runs/` into `tests/fixtures/sq_runs/`, including **at least one `paused` and one `failed`**, per the LLD's Technical Requirements
- [ ] Capture real `cf get --json` output into `tests/fixtures/cf/`
- [ ] Add a short `README.md` in the fixtures directory noting, for each fixture, **the date it was captured** — and **not** an upstream version number, per the LLD's upstream-versions stance
- [ ] Redact nothing that changes shape; if a value must be redacted, replace it with an obviously-placeholder value rather than a plausible one
- [ ] Confirm no captured fixture contains a secret

**Success Criteria**:
- [ ] Fixtures are byte-real upstream output, not hand-written approximations
- [ ] At least one `paused` and one `failed` Squadron run present
- [ ] Each fixture's capture date recorded; no version pinned
- [ ] No secrets committed

**Files to Create**: `tests/fixtures/sq_runs/*.json`, `tests/fixtures/cf/*.json`, `tests/fixtures/README.md`

---

### Task 4.2: Implement the Squadron run-file parser
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 3
**Objective**: Parse the six header fields the LLD names, using `pydantic` at this external boundary per D3 and the Python rules.

**Steps**:
- [ ] Add `pydantic` to `pyproject.toml` runtime dependencies — the project's first — and run `uv sync`
- [ ] Create `src/amoeba/process/observers/` with `__init__.py` and `sq_runs.py`
- [ ] Define a pydantic model over exactly the header fields the LLD lists: `schema_version`, `run_id`, `pipeline`, `params`, `started_at`, `status`
- [ ] Configure it to **ignore unknown fields**, so an upstream that adds fields does not break recovery
- [ ] Treat a **missing required field as a parse failure**, which the matcher turns into `Unknown` — never an exception escaping the observer and never a match
- [ ] Implement directory scanning that reads the runs directory **once per recovery pass**, not once per entry

**Success Criteria**:
- [ ] Every fixture from Task 4.1 parses, including the `paused` and `failed` ones
- [ ] A fixture with an added unknown field still parses
- [ ] A fixture with a required field removed yields a parse failure, not an exception
- [ ] `uv run pyright` clean with the new dependency

**Files to Create**: `src/amoeba/process/observers/__init__.py`, `src/amoeba/process/observers/sq_runs.py`
**Files to Modify**: `pyproject.toml`, `uv.lock`

---

### Task 4.3: Implement the Squadron matching rule
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 3
**Objective**: Implement D5's four-condition candidate rule, biased entirely toward escalation.

**Steps**:
- [ ] A run is a candidate when **all four** hold, per the LLD's D5: `pipeline` equal compared **lower-cased**; every journaled `params` key present in the run's params with an equal value (**subset**, not equality); `started_at` no earlier than `issued_at` minus the clock tolerance from `ProcessSettings`; and its `run_id` not already recorded in another journal entry's result
- [ ] Exactly one candidate → `Adopt`, carrying the `run_id` and the run file's own `schema_version` as provenance
- [ ] Zero or several candidates → `Unknown` with a reason naming the count
- [ ] Runs directory missing or unreadable → `Unknown`
- [ ] A run file that fails to parse is logged at WARNING, **counted**, and named in the `Unknown` reason if the entry ends up unmatched — never silently skipped into a confident answer
- [ ] Do not compare any upstream version number anywhere in this module

**Success Criteria**:
- [ ] The only path to `Adopt` is exactly one candidate passing all four conditions
- [ ] Every other outcome is `Unknown`; the observer raises nothing for expected external failure
- [ ] Unparseable files are counted and surfaced, not dropped
- [ ] Function stays near the 50-line budget

**Files to Modify**: `src/amoeba/process/observers/sq_runs.py`

---

### Task 4.4: Test the Squadron observer against real fixtures
**Owner**: Junior AI
**Dependencies**: Task 4.3
**Effort**: 3
**Objective**: Cover each matching condition and every escalation path, using the real files from Task 4.1.

**Steps**:
- [ ] Test exactly one match → `Adopt` with the right `run_id` and the `schema_version` recorded
- [ ] Test zero matches → `Unknown`
- [ ] Test two matches → `Unknown` naming the count
- [ ] Test **subset** params matching succeeds where exact equality would fail — i.e. the run's persisted params are a superset (Squadron merges definition defaults with overrides)
- [ ] Test a run started **before** `issued_at` minus tolerance is rejected
- [ ] Test a run whose `run_id` already appears in another entry's result is not a candidate
- [ ] Test case-insensitive pipeline matching
- [ ] Test a missing/unreadable runs directory → `Unknown`
- [ ] Test an unparseable file among good ones is counted and named in the reason, and does not prevent a clean single match elsewhere
- [ ] Test a run file missing a required field degrades to `Unknown`, not an exception

**Success Criteria**:
- [ ] All ten behaviors asserted against real fixture files
- [ ] The subset test would fail under exact-equality matching
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(process): add squadron runs observer`

**Files to Create**: `tests/test_observer_sq_runs.py`

---

### Task 4.5: Implement the Context Forge read-back observer
**Owner**: Junior AI
**Dependencies**: Task 4.4
**Effort**: 3
**Objective**: Compare `cf get --json` output against the entry's `expected` mapping, with provenance per the LLD.

**Steps**:
- [ ] Create `cf_readback.py` invoking `cf get --json -p <project>` with the timeout from `ProcessSettings`, non-TTY stdin
- [ ] Parse the output with a pydantic model ignoring unknown fields
- [ ] All `expected` fields match → `Adopt`; any differ → `NotApplied`
- [ ] Record provenance on adoption per the LLD: the project record's own `updatedAt`, plus an opaque `cf --version` label captured **once per recovery pass**; record it as unavailable if that call fails, and never let provenance capture turn a clean adoption into an escalation
- [ ] Never parse, order, or branch on the version label — it is recorded, not compared
- [ ] `cf` missing, timing out, exiting non-zero, or emitting unparseable output → `Unknown`
- [ ] A required field absent from the output → `Unknown`

**Success Criteria**:
- [ ] The four external failure modes each yield `Unknown` with a distinguishable reason
- [ ] The observer raises nothing for expected external failure
- [ ] No code path compares the captured version label
- [ ] `uv run pyright` clean

**Files to Create**: `src/amoeba/process/observers/cf_readback.py`

---

### Task 4.6: Test the CF observer
**Owner**: Junior AI
**Dependencies**: Task 4.5
**Effort**: 3
**Objective**: Cover match, mismatch, and every external failure mode — with the subprocess boundary mocked for failures and **one real invocation** test.

**Steps**:
- [ ] Test expected values present → `Adopt`, carrying `updatedAt` and the version label
- [ ] Test a differing value → `NotApplied`
- [ ] Test `cf` missing from `PATH` → `Unknown`
- [ ] Test timeout → `Unknown`
- [ ] Test non-zero exit → `Unknown`
- [ ] Test unparseable output → `Unknown`
- [ ] Test a required field absent from output → `Unknown`
- [ ] Test `cf --version` failing still permits adoption, recording the label as unavailable
- [ ] Add **one** test invoking the real `cf` binary, skipped cleanly when it is not on `PATH`

**Success Criteria**:
- [ ] All eight mocked behaviors asserted plus the real-invocation test
- [ ] The real test skips rather than fails when `cf` is absent
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(process): add context forge read-back observer`

**Files to Create**: `tests/test_observer_cf_readback.py`

---

**Continue with `102-tasks.resident-process-and-recovery-2.md`** for the instance lock, host loop, CLI, guard test, load tier, and documentation.
