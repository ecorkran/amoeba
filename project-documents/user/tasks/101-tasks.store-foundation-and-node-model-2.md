---
docType: tasks
slice: store-foundation-and-node-model
project: amoeba
lld: user/slices/101-slice.store-foundation-and-node-model.md
dependencies: []
projectState: Continuation of 101-tasks.store-foundation-and-node-model-1.md. Assumes Sections 1-3 complete: scaffold, models, migrations, and the store API with node CRUD, block/resolve, and the two Runner queries are implemented, tested, and committed.
dateCreated: 20260915
dateUpdated: 20260915
status: not_started
---

## Context Summary

- Working on the **store-foundation-and-node-model** slice (101), part 2 of 2.
- **Part 1** is `101-tasks.store-foundation-and-node-model-1.md` (Sections 1-3). Complete it first — every task here depends on the committed store API from Task 3.8.
- **This file covers:** the enumerated store-I/O failure modes, the N to N+1 migration proof, the public API surface, contract documentation, and final verification against the design.
- **Key design commitments** (from the LLD — do not revisit them here): raw stdlib `sqlite3`; all SQL and every column name centralized in `sql.py`; the busy timeout is a named configuration constant, never an inline literal; no failure path degrades to a default, an empty result, or a fallback store.
- **Next planned slice:** 102 (Resident Process and Recovery), which hosts this store and becomes its sole writer.

**Reading note for the executing developer:** this file does not restate the LLD. Where a task says "per the LLD," open `user/slices/101-slice.store-foundation-and-node-model.md` at the named section and follow it.

---

## Section 4: Failure Modes

### Task 4.1: Implement the enumerated store-I/O failure modes
**Owner**: Junior AI
**Dependencies**: Task 3.8
**Effort**: 3
**Objective**: Implement the four failure modes enumerated in the LLD's "Failure modes on the store I/O path" so each raises a typed exception rather than degrading silently.

**Steps**:
- [ ] **Lock contention:** exhausting the busy timeout raises a typed store exception naming the contended operation; never retry indefinitely; never return an empty result as though the read succeeded
- [ ] **Corrupt or unreadable database file:** a file that is not a valid SQLite database, or whose `schema_meta` cannot be read, raises at open — never re-created, truncated, or treated as fresh
- [ ] **Permission error on the store path:** an unreadable or unwritable path, or a parent directory that cannot be created, raises at open with the resolved path in the message — no fallback to a temp location or in-memory database
- [ ] **Disk-full during commit:** the failed commit propagates; no write method returns an ignorable status code
- [ ] Confirm every `try/except` re-raises after `logger.exception`, handles a specific exception with a justifying comment, or sits at a process boundary — no bare `except`, enforced by ruff `BLE`

**Success Criteria**:
- [ ] Each of the four modes raises a specific typed exception
- [ ] No failure path degrades to a default, an empty result, or a fallback store
- [ ] `uv run ruff check .` passes with `BLE` active
- [ ] `uv run pyright` strict passes

---

### Task 4.2: Test the failure modes
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 3
**Objective**: Cover the three failure modes the LLD's Success Criteria require to be tested.

**Steps**:
- [ ] Test opening a corrupt database file (write non-SQLite bytes to a path under `tmp_path`, then open) raises the typed error
- [ ] Test opening a path the process cannot read or write raises at open, with the resolved path in the message
- [ ] Test busy-timeout exhaustion under contention raises the typed error
- [ ] Assert the busy timeout **as a named constant**, not by matching a literal value — a test that hardcodes the number defeats the purpose
- [ ] Ensure every test operates only on paths the fixture created

**Success Criteria**:
- [ ] `uv run pytest -v` passes with all three failure-mode tests green
- [ ] The busy-timeout test references the named constant
- [ ] No test touches the central per-supervisor store path

---

### Task 4.3: Add the 002 migration exercising N→N+1
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 2
**Objective**: Land a deliberately trivial second migration purely to prove the runner works end to end, so slices 102–106 add tables onto a proven mechanism.

**Steps**:
- [ ] Write `migrations/002_*.sql` with a trivial, clearly-labeled schema change
- [ ] Bump the code's expected version to 2
- [ ] Extend `tests/test_migrations.py`: open a store at version 1, apply the migration, assert the stamp advanced **and** pre-existing data survived

**Success Criteria**:
- [ ] `uv run pytest tests/test_migrations.py -v` passes
- [ ] The test asserts both the advanced stamp and data survival
- [ ] A fresh store created from scratch also arrives at version 2

**Files to Create**:
- `src/amoeba/store/migrations/002_*.sql`

---

### Task 4.4: Commit failure modes and the second migration
**Owner**: Junior AI
**Dependencies**: Task 4.3
**Effort**: 1
**Objective**: Checkpoint a hardened, fully-tested store.

**Steps**:
- [ ] Verify working directory and branch
- [ ] Run ruff check, ruff format --check, pyright, and pytest
- [ ] Commit, e.g. `feat: add typed store failure modes and n+1 migration`

**Success Criteria**:
- [ ] All four verification commands pass before the commit
- [ ] Working tree is clean

---

## Section 5: Public Surface, Documentation, and Verification

### Task 5.1: Define the public API surface in __init__.py
**Owner**: Junior AI
**Dependencies**: Task 4.4
**Effort**: 2
**Objective**: Export the contract — and only the contract — so downstream slices depend on a deliberate surface rather than on internals.

**Steps**:
- [ ] Export the store class, the dataclasses, the vocabularies, and the exception types from `src/amoeba/store/__init__.py`
- [ ] Do not export `sql.py` internals or migration machinery
- [ ] Confirm every exported callable carries a docstring sufficient for a downstream author

**Success Criteria**:
- [ ] The names in the LLD's verification walkthrough import successfully from `amoeba.store`
- [ ] Internal modules are not re-exported
- [ ] `uv run pyright` strict passes

---

### Task 5.2: Write the contract documentation
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 3
**Objective**: Document the store contract well enough that initiative 120's slice design can proceed **without reading the implementation**. Per the LLD this is the criterion that actually gates downstream work.

**Steps**:
- [ ] Document the public API: lifecycle, node writes, node reads, blocked-state writes, and the two Runner queries
- [ ] Document the status vocabulary and the other closed vocabularies, with each value's meaning
- [ ] Document the writer model explicitly: this library **does not** enforce single-writer, and slice 102 is what adds it — stated so 102 knows what it is adding rather than discovering an assumption
- [ ] Document the enumerated failure modes and which exception each raises
- [ ] Document store locality (per-supervisor, central, project-keyed) and the migration mechanism
- [ ] Note the reversal trigger for the storage-engine decision as Future Work, per the LLD

**Success Criteria**:
- [ ] Every public API element is documented
- [ ] The non-enforcement of single-writer is stated explicitly
- [ ] Each failure mode names its exception type
- [ ] A reader can design a consumer against the document without opening `store.py`

---

### Task 5.3: Execute the verification walkthrough
**Owner**: Junior AI
**Dependencies**: Task 5.2
**Effort**: 2
**Objective**: Run the LLD's Verification Walkthrough end to end and confirm each observable claim.

**Steps**:
- [ ] Run `uv sync`, then `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pyright`
- [ ] Run `uv run pytest -v`
- [ ] Execute the REPL walkthrough from the LLD's step 3 against a temporary store
- [ ] Run `uv run pytest tests/test_migrations.py -v`
- [ ] Inspect the database file with `sqlite3 <path> .schema` and confirm status values are readable strings

**Success Criteria**:
- [ ] All tooling commands report clean; pyright reports zero errors
- [ ] The full suite passes
- [ ] The walkthrough demonstrates the observable claim: a blocked node leaves the runnable set, appears in the blocked set with its blocker named, and returns to runnable only when its resolution slot is filled
- [ ] `.schema` shows the expected tables and readable status strings
- [ ] Any deviation from the walkthrough is fixed, not documented as a known issue

---

### Task 5.4: Final review against the design and commit
**Owner**: Junior AI
**Dependencies**: Task 5.3
**Effort**: 2
**Objective**: Confirm every Success Criterion in the LLD is met before the slice is declared complete.

**Steps**:
- [ ] Walk the LLD's Functional, Technical, and Integration Requirements and confirm each is satisfied
- [ ] Confirm no SQL string or column name appears outside `sql.py`
- [ ] Confirm source files are near the ~300-line guideline
- [ ] Confirm no load-test tier was added — this slice is a synchronous in-process library and sits on none of the paths that require one
- [ ] Update the task file's `status` to `complete` and the slice document's `status`, delegating checklist updates to the `task-checker` agent
- [ ] Commit, e.g. `docs: add store contract documentation for slice 101`

**Success Criteria**:
- [ ] Every LLD Success Criterion is verifiably met
- [ ] A grep confirms no SQL outside `sql.py`
- [ ] Final commit exists and the working tree is clean
- [ ] The slice is ready for PM review

---

## Out of Scope

Named here because each is a plausible scope-creep target. All belong to later slices; do not implement them in 101.

- [ ] Any long-lived process, lifecycle command, or single-instance handling — **slice 102**
- [ ] The command journal and reconcile-by-observation recovery — **slice 102**
- [ ] Single-writer enforcement — **slice 102**
- [ ] The durable inbox and message channels — **slice 103**
- [ ] Finding identity, normalization, and verdict provenance — **slice 104**
- [ ] Change feed, subscriptions, filesystem detection — **slice 105**
- [ ] Pruning and retention policy — **slice 106**
- [ ] Any parsing of CF or SQ output — the store accepts values; the Runner parses them
- [ ] A per-project store override — the LLD declines this deliberately
