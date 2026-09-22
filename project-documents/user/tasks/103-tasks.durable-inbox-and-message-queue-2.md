---
docType: tasks
slice: durable-inbox-and-message-queue
project: amoeba
lld: user/slices/103-slice.durable-inbox-and-message-queue.md
dependencies: [101, 102]
projectState: Continuation of 103-tasks.durable-inbox-and-message-queue-1.md. Sections 1-5 have landed ProjectStores, migration 004, the one block writer with D3 escalations, apply_submission, and the amoeba.inbox package.
dateCreated: 20260922
dateUpdated: 20260922
status: not_started
---

## Context Summary

- Continuation file for the **durable-inbox-and-message-queue** slice (103). See `103-tasks.durable-inbox-and-message-queue-1.md` for the full context summary, the ratified design commitments, and Sections 1–5.
- **This file covers Sections 6–10:** runtime project creation and `InboxTenant`, the CLI, guard and public-API tests, the load tier, and documentation.
- **Entering this file:** `ProjectStores` is extracted and is the writer guard's one permitted module; the store is at schema version 4 with `inbox_submissions` and `messages`; one internal block writer emits escalation rows for `HUMAN` blocks and for `journal_escalate`'s already-blocked branch; `apply_submission` handles all three kinds in one transaction; `amoeba.inbox` can `submit()` and list. Nothing yet consumes the inbox — the process still registers no tenants.

**Reading note for the executing developer:** this file does not restate the LLD. Where a task says "per the LLD," open `user/slices/103-slice.durable-inbox-and-message-queue.md` at the named section and follow it.

---

## Section 6: Runtime Project Creation and the Apply Loop

### Task 6.1: Add host.open_project
**Owner**: Junior AI
**Dependencies**: Task 5.5
**Effort**: 2
**Objective**: Add idempotent create-or-open to `ProjectStores` and expose it on the host, per the LLD's Host addition table.

**Steps**:
- [ ] Add `open_project(project_id) -> Store` to `ProjectStores`: create-or-open the project's store read-write and add it to the open set; **idempotent**, so calling it for an already-open project returns the open handle
- [ ] Let `Store.open` migrate a new store to the current schema as usual; a new store's journal is empty, so there is nothing to recover
- [ ] Ensure `project_ids` reflects a newly opened project **immediately**
- [ ] Expose `open_project` on the host, delegating to `ProjectStores`
- [ ] Validate the project id with the one rule in `amoeba.store.paths` **before** it reaches any filesystem path computation
- [ ] Let failures raise — the tenant, not this method, decides what a failure means

**Success Criteria**:
- [ ] `open_project` on an existing project is a no-op returning the open handle
- [ ] `host.project_ids` grows at runtime and includes a project created after startup
- [ ] An invalid project id is refused before any path is computed and no store file is created anywhere
- [ ] The writer guard's permitted set is still exactly `{process/project_stores.py}`

**Files to Modify**: `src/amoeba/process/project_stores.py`, `src/amoeba/process/host.py`

---

### Task 6.2: Test open_project against the real host
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 2
**Objective**: Cover runtime creation through `tests/host_harness.py`, the harness slice 102 established.

**Steps**:
- [ ] Assert a project created at runtime is immediately in `project_ids` and has a usable store
- [ ] Assert `open_project` is idempotent across repeated calls
- [ ] Assert a store created at runtime is at schema version 4
- [ ] Assert an invalid project id raises and creates nothing on disk

**Success Criteria**:
- [ ] All four assertions pass against the real host, not a mock
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(process): add runtime project creation`

**Files to Modify**: the host test module

---

### Task 6.3: Add the inbox settings
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 1
**Objective**: Add `inbox_batch_size` and `inbox_max_attempts` to `ProcessSettings`, each with a `start` flag like every other tunable.

**Steps**:
- [ ] Add both settings to `ProcessSettings` following the existing convention
- [ ] Add the corresponding `amoeba start` flags
- [ ] Choose a **small** default for `inbox_max_attempts` — per the LLD the point is to bound the loop, not to retry a corrupt store into working
- [ ] Centralize both defaults in the settings definition; do not hard-code either value at a call site

**Success Criteria**:
- [ ] Both settings are settable by flag and have centralized defaults
- [ ] `grep` finds neither default value anywhere outside the settings module
- [ ] `uv run pyright` clean

**Files to Modify**: the `ProcessSettings` module, `src/amoeba/cli/lifecycle.py`

---

### Task 6.4: Implement InboxTenant's apply loop
**Owner**: Junior AI
**Dependencies**: Task 6.3
**Effort**: 3
**Objective**: Implement the first real `Tenant`, per the LLD's Data Flow "Apply" block.

**Steps**:
- [ ] Create `src/amoeba/process/inbox_tenant.py` implementing the `Tenant` protocol (`name`, `tick(host) -> bool`)
- [ ] Handle at most `inbox_batch_size` files per tick, in filename (drain) order, checking `stop_requested` **between files**
- [ ] For a `create_project` envelope, call `host.open_project` before resolving the store
- [ ] Delete the file **after** the transaction commits — never before; the crash table in the LLD depends on this order
- [ ] Delete any `.attempts.json` counter along with the file on success
- [ ] Return whether any file was handled
- [ ] Log a WARNING when a submission id is reused with different content — first wins, and it is not an error (D2)

**Success Criteria**:
- [ ] A tick handles at most `inbox_batch_size` files and stops early when `stop_requested` is set
- [ ] The file delete follows the commit, so a crash between them leaves a recorded submission and a file that is a no-op on restart
- [ ] The tenant is the only module importing both `amoeba.inbox` and `amoeba.store` write paths
- [ ] `uv run pyright` clean

**Files to Create**: `src/amoeba/process/inbox_tenant.py`

---

### Task 6.5: Implement the quarantine ladder
**Owner**: Junior AI
**Dependencies**: Task 6.4
**Effort**: 2
**Objective**: Route every submission that cannot be attributed to an open store into `quarantine/` with its reason, never raising.

**Steps**:
- [ ] Quarantine with the matching `QuarantineReason` for each member of the closed vocabulary: unparseable envelope, unknown envelope version, unknown kind, invalid project id, invalid payload, and no store for the project
- [ ] Move the file and write a `.reason.json` sidecar; **never delete content**
- [ ] Continue to the next file after quarantining — a bad submission must not block later valid ones in the same tick
- [ ] Do **not** convert a `StoreError` into a quarantine: quarantine means "this submission is bad", never "the store is unwell"
- [ ] Quarantine a submission that races ahead of its project's creation rather than holding it, per the LLD's Special Considerations

**Success Criteria**:
- [ ] Each of the six quarantine reasons is reachable and produces its sidecar
- [ ] Later valid submissions in the same tick still apply after a quarantine
- [ ] No `StoreError` path leads to quarantine

**Files to Modify**: `src/amoeba/process/inbox_tenant.py`

---

### Task 6.6: Implement the bounded attempt counter and the failed/ park
**Owner**: Junior AI
**Dependencies**: Task 6.5
**Effort**: 3
**Objective**: Implement the design review's F001 resolution, per the LLD's "A failing apply stops the process, but not forever."

**Steps**:
- [ ] On an unexpected exception from `open_project` or `apply_submission`, read the file's `.attempts.json` (absent means zero) and increment
- [ ] Below `inbox_max_attempts`: write the counter beside the file in `new/` using the **same tmp-and-rename** `submit()` uses, log with `logger.exception`, and **re-raise** so the process stops — the file stays in `new/`
- [ ] At `inbox_max_attempts`: move the file **and its counter** to `inbox/failed/`, log at ERROR, and **continue to the next file** instead of re-raising
- [ ] Record `{attempts, last_error, last_failed_at}` in the counter so the failure is inspectable once the process is running again
- [ ] Ensure a file moved back from `failed/` to `new/` **resumes at its recorded count** rather than starting over

**Success Criteria**:
- [ ] The counter survives the crash that wrote it, because it is on disk rather than in memory or in the store
- [ ] The first `inbox_max_attempts - 1` failures still stop the process, so an unwell store stays loud
- [ ] After parking, the tick continues and the process stays up
- [ ] A requeued file resumes at its old count rather than buying a fresh set of attempts

**Files to Modify**: `src/amoeba/process/inbox_tenant.py`, `src/amoeba/inbox/layout.py`

---

### Task 6.7: Register InboxTenant first in amoeba start
**Owner**: Junior AI
**Dependencies**: Task 6.6
**Effort**: 1
**Objective**: Wire the tenant into the lifecycle so a backlog drains ahead of any later tenant's work.

**Steps**:
- [ ] Register `InboxTenant` in `cli/lifecycle.py` as the **first** tenant — tenants tick in registration order, and the LLD requires the inbox to drain first
- [ ] Confirm `amoeba start` changes from zero tenants to exactly one

**Success Criteria**:
- [ ] `amoeba start` registers `InboxTenant` first
- [ ] Slice 102's lifecycle tests pass, updated only where they asserted zero tenants

**Files to Modify**: `src/amoeba/cli/lifecycle.py`

---

### Task 6.8: Test the tenant against the real host
**Owner**: Junior AI
**Dependencies**: Task 6.7
**Effort**: 3
**Objective**: Cover the apply loop, the crash table, the quarantine ladder, and the attempt counter through `tests/host_harness.py`.

**Steps**:
- [ ] Assert a submission made while the process is **stopped** is applied on start and its file is gone
- [ ] Assert a `create_project` applied by a **running** process creates the store, and a later submission for that project applies **without a restart** — in the same tick and in a later one
- [ ] Assert replay: a file restored to `new/` after apply changes nothing and leaves exactly one record
- [ ] Assert each quarantine reason lands in `quarantine/` with its sidecar and that later valid submissions in the same tick still apply
- [ ] Assert the batch-size limit and early stop on `stop_requested`
- [ ] Assert the F001 path: a submission whose apply raises every time stops the process for `inbox_max_attempts - 1` starts with the counter incrementing on disk, then lands in `failed/` with the last error recorded, and the tick that parks it goes on to apply the next file
- [ ] Assert a file moved from `failed/` back to `new/` resumes at its recorded count and is deleted with its counter once it applies

**Success Criteria**:
- [ ] Every functional criterion in the LLD touching the tenant has a test here
- [ ] The F001 park is proven to keep the process up
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(process): add InboxTenant apply loop`

**Files to Create**: `tests/process/test_inbox_tenant.py`

---

## Section 7: The CLI

### Task 7.1: Implement amoeba submit
**Owner**: Junior AI
**Dependencies**: Task 6.8
**Effort**: 2
**Objective**: Add the operator- and bridge-usable writer, per the LLD's CLI table.

**Steps**:
- [ ] Create `src/amoeba/cli/submit.py` with `create-project`, `resolution`, and `intent` subcommands taking the flags the LLD's CLI table names, each printing the submission id
- [ ] Derive subcommand names **from `SubmissionKind`** — never the reverse, and never a hand-maintained second list
- [ ] Call `amoeba.inbox.submit()`; open no store
- [ ] Follow slice 102's CLI process-boundary and `ExitCode` conventions

**Success Criteria**:
- [ ] Adding a `SubmissionKind` member surfaces a subcommand without editing a second list
- [ ] `cli/submit.py` opens no store read-write, confirmed by the writer guard
- [ ] All three subcommands work with the process running and stopped

**Files to Create**: `src/amoeba/cli/submit.py`

---

### Task 7.2: Implement the three inspection listings
**Owner**: Junior AI
**Dependencies**: Task 7.1
**Effort**: 2
**Objective**: Add `inspect inbox`, `inspect submissions`, and `inspect messages`.

**Steps**:
- [ ] Add `inspect inbox` as a **supervisor-level** listing (like `projects`), showing pending, quarantined, and failed files
- [ ] Register `submissions` and `messages` into slice 102's listing registry as project-scoped listings taking `--project`
- [ ] Give `messages` a `--channel` option
- [ ] Support `--json` on all three, per the existing convention
- [ ] Read through `Store.open_read_only` — these listings must work while the process is running

**Success Criteria**:
- [ ] All three listings work with the process running and stopped
- [ ] `submissions` lists in `applied_seq` order
- [ ] Listing names derive from the registry, not from hand-maintained strings

**Files to Modify**: the inspection CLI module

---

### Task 7.3: Test the CLI as real subprocesses
**Owner**: Junior AI
**Dependencies**: Task 7.2
**Effort**: 2
**Objective**: Cover `submit` and the listings the way slice 102 tests its CLI.

**Steps**:
- [ ] Test each `submit` subcommand as a subprocess, asserting the printed id matches the file written in `new/`
- [ ] Test all three listings with the process both running and stopped
- [ ] Test `--json` output shape for each listing
- [ ] Test that an invalid project id or payload exits non-zero and writes nothing

**Success Criteria**:
- [ ] Tests exercise the real CLI as subprocesses, not by calling internal functions
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `feat(cli): add submit command and inbox listings`

**Files to Create**: `tests/cli/test_submit.py`, plus additions to the inspection CLI test module

---

## Section 8: Guard and Public-API Tests

### Task 8.1: Pin the sole-writer boundary and the inbox public API
**Owner**: Junior AI
**Dependencies**: Task 7.3
**Effort**: 2
**Objective**: Make the architectural boundary mechanical rather than asserted, per the LLD's Technical Requirements.

**Steps**:
- [ ] Assert the writer guard's permitted set is exactly `{process/project_stores.py}` and that the deliberate-widening test still pins a set of size one
- [ ] Assert `amoeba.inbox` and `cli/submit.py` open no store read-write
- [ ] Add a test asserting **`amoeba.inbox`'s public exports contain no write path other than `submit`**
- [ ] Assert `amoeba.store` does not import `amoeba.inbox`, pinning the one-way dependency direction in the LLD's Component Structure

**Success Criteria**:
- [ ] All four assertions pass, and each fails if the boundary it guards is violated
- [ ] `uv run pytest` passes
- [ ] Commit after this task, e.g. `test: pin inbox public api and writer boundary`

**Files to Modify**: `tests/test_writer_guard.py`
**Files to Create**: `tests/inbox/test_public_api.py`

---

### Task 8.2: Write and allow-list the demo script
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 1
**Objective**: Provide the seeding helper the verification walkthrough needs.

**Steps**:
- [ ] Create `scripts/demo_inbox.py` seeding one node blocked on a human in the `demo` project and printing the node id and blocked-state id
- [ ] Have it perform a read-write `Store.open` and run **only while the process is stopped**, like `demo_journal.py`
- [ ] Add it to `PERMITTED_SCRIPTS` in `tests/test_writer_guard.py`
- [ ] Note in the script why it exists: nothing outside the process can create nodes until initiative 120

**Success Criteria**:
- [ ] The script prints both ids and the writer guard passes with it allow-listed
- [ ] The guard's script allow-list grows by exactly one entry

**Files to Create**: `scripts/demo_inbox.py`
**Files to Modify**: `tests/test_writer_guard.py`

---

## Section 9: The Load Tier

### Task 9.1: Implement the concurrent-submitter load test
**Owner**: Junior AI
**Dependencies**: Task 8.2
**Effort**: 3
**Objective**: Prove exactly-once under concurrency and repeated kills, per the LLD's Implementation Notes item 9.

**Steps**:
- [ ] Run several submitter **processes**, each submitting a few hundred `intent` submissions to projects created **through the inbox during the run**
- [ ] Deliberately resubmit a fraction under the **same id** to exercise D2
- [ ] `SIGKILL` and restart the resident process at random points throughout
- [ ] Assert: every distinct id has exactly one record **and** exactly one message; `applied_seq` has no duplicates; `inbox/new/` drains to empty; no `tmp/` file is ever applied
- [ ] Place the test in the existing `tests/load/` tier

**Success Criteria**:
- [ ] The test kills and restarts the process mid-run and still asserts exactly-once per id
- [ ] Projects are created through the inbox during the run, exercising runtime creation under load
- [ ] `uv run pytest tests/load` passes

**Files to Create**: `tests/load/test_inbox_concurrent.py`

---

### Task 9.2: Measure and record the drain-time bound
**Owner**: Junior AI
**Dependencies**: Task 9.1
**Effort**: 1
**Objective**: Follow slice 102's measure-first rule rather than guessing a threshold.

**Steps**:
- [ ] Measure the observed drain time first
- [ ] Assert at roughly **twice** the observation
- [ ] Record the measured number in the test as a comment, per slice 102's precedent

**Success Criteria**:
- [ ] The threshold is derived from a recorded measurement, not chosen arbitrarily
- [ ] The recorded number is present in the test
- [ ] Commit after this task, e.g. `test: add concurrent submitter load test`

**Files to Modify**: `tests/load/test_inbox_concurrent.py`

---

## Section 10: Documentation and Completion

### Task 10.1: Write docs/inbox-contract.md
**Owner**: Junior AI
**Dependencies**: Task 9.2
**Effort**: 2
**Objective**: State the delivery and replay semantics, per the LLD's "Delivery and Replay Semantics" section — which is the content this document must carry.

**Steps**:
- [ ] State every **Guaranteed** item the LLD lists: durability on return, exactly-once effect per id, atomic effect and record, every submission reaching a terminal inspectable state, one receiver-assigned authoritative order, replayable messages, and an escalation row with every human block
- [ ] State every **Not guaranteed** item: apply order versus submit order, latency, outcome notification, that a valid submission is applied, what an open blocked state means for a recovery-attached escalation, and retention
- [ ] State the rule that a submitter creating a project waits for `submission(id)` to report `applied` before submitting into it
- [ ] Repeat slice 102's rule that callers must not place secrets in payloads
- [ ] Write for a reader who has not read the implementation — an initiative 160 slice design must be able to proceed from this document alone

**Success Criteria**:
- [ ] Every guaranteed and not-guaranteed item in the LLD appears
- [ ] The document is sufficient for an initiative 160 slice design without reading the implementation
- [ ] Durability is stated as "fsync-durable on a POSIX filesystem" rather than overclaimed

**Files to Create**: `docs/inbox-contract.md`

---

### Task 10.2: Update the existing contracts and the changelog
**Owner**: Junior AI
**Dependencies**: Task 10.1
**Effort**: 1
**Objective**: Record this slice's changes to slices 101 and 102, per the LLD's "Consumes from Other Slices."

**Steps**:
- [ ] `docs/store-contract.md`: `block()` gains `payload=None` and a `HUMAN` block writes an escalation row; `journal_escalate` shares the block writer and escalates on its already-blocked branch; the new inbox and message methods
- [ ] `docs/process-contract.md`: `open_project`; `project_ids` is no longer fixed at startup; read-write opening moved to `process/project_stores.py`; `amoeba start` now registers `InboxTenant` first
- [ ] `CHANGELOG.md`: schema version 4 and the slice's user-visible additions
- [ ] Note in the process contract that consumers **must not cache `project_ids`**, which initiative 120 depends on

**Success Criteria**:
- [ ] All three documents reflect the shipped behavior
- [ ] Both recorded consequences of D3 appear in the store contract

**Files to Modify**: `docs/store-contract.md`, `docs/process-contract.md`, `CHANGELOG.md`

---

### Task 10.3: Run the integration walkthrough and capture real output
**Owner**: Junior AI
**Dependencies**: Task 10.2
**Effort**: 2
**Objective**: Execute the LLD's Verification Walkthrough end to end and replace its draft output with captured output.

**Steps**:
- [ ] Run all eight steps from an **empty** supervisor directory through the real CLI as subprocesses
- [ ] Replace the LLD's draft walkthrough output with the captured output, removing the "Draft" note
- [ ] Add the end-to-end integration test the LLD's Integration Requirements names: `start` → `submit create-project` → seed a human-blocked node → read its escalation row read-only → `stop` → `submit resolution` → `start` → node is `runnable` → `kill -9` → `start` → state unchanged and no second apply
- [ ] Investigate any divergence between the draft and reality as a defect or a design correction, not as a transcript to edit

**Success Criteria**:
- [ ] The walkthrough in the LLD shows real captured output
- [ ] The end-to-end test passes, including the `kill -9` step
- [ ] Commit after this task, e.g. `docs: add inbox contract and capture walkthrough output`

**Files to Modify**: `user/slices/103-slice.durable-inbox-and-message-queue.md`
**Files to Create**: the end-to-end integration test module

---

### Task 10.4: Final verification and slice completion
**Owner**: Junior AI
**Dependencies**: Task 10.3
**Effort**: 1
**Objective**: Confirm every success criterion in the LLD and close the slice.

**Steps**:
- [ ] Run `uv run pytest && uv run pytest tests/load`
- [ ] Run `uv run ruff check . && uv run ruff format --check . && uv run pyright`
- [ ] Walk the LLD's Functional, Technical, and Integration Requirements checklists and confirm each item
- [ ] Confirm source files stay near 300 lines, **`host.py` included**
- [ ] Set `status: complete` in both task files and in the slice design

**Success Criteria**:
- [ ] All quality gates clean
- [ ] Every LLD success criterion is verified, not assumed
- [ ] `host.py` is within the line guideline, closing the item slice 102 left open
- [ ] Commit, then merge the slice branch into the integration target — **re-read `cf config get git.integration_branch` first** rather than inferring the target from the current branch or from memory (merge step deferred to main agent)

**Files to Modify**: both task files, `user/slices/103-slice.durable-inbox-and-message-queue.md`
