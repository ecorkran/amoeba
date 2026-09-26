---
docType: tasks
slice: durable-inbox-and-message-queue
project: amoeba
lld: user/slices/103-slice.durable-inbox-and-message-queue.md
dependencies: [101, 102]
projectState: Continuation of 103-tasks.durable-inbox-and-message-queue-1.md. Sections 1-5 have landed ProjectStores, migration 004, the one block writer with D3 escalations, apply_submission, and the amoeba.inbox package.
dateCreated: 20260922
dateUpdated: 20260925
status: complete
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
- [x] Add `open_project(project_id) -> Store` to `ProjectStores`: create-or-open the project's store read-write and add it to the open set; **idempotent**, so calling it for an already-open project returns the open handle
- [x] Let `Store.open` migrate a new store to the current schema as usual; a new store's journal is empty, so there is nothing to recover
- [x] Ensure `project_ids` reflects a newly opened project **immediately**
- [x] Expose `open_project` on the host, delegating to `ProjectStores`
- [x] Validate the project id with the one rule in `amoeba.store.paths` **before** it reaches any filesystem path computation
- [x] Let failures raise — the tenant, not this method, decides what a failure means

**Success Criteria**:
- [x] `open_project` on an existing project is a no-op returning the open handle
- [x] `host.project_ids` grows at runtime and includes a project created after startup
- [x] An invalid project id is refused before any path is computed and no store file is created anywhere
- [x] The writer guard's permitted set is still exactly `{process/project_stores.py}`

- [x] Commit after this task, e.g. `feat(process): add open_project for runtime creation`

**Files to Modify**: `src/amoeba/process/project_stores.py`, `src/amoeba/process/host.py`

---

### Task 6.2: Test open_project against the real host
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 2
**Objective**: Cover runtime creation through `tests/host_harness.py`, the harness slice 102 established.

**Steps**:
- [x] Assert a project created at runtime is immediately in `project_ids` and has a usable store
- [x] Assert `open_project` is idempotent across repeated calls
- [x] Assert a store created at runtime is at schema version 4
- [x] Assert an invalid project id raises and creates nothing on disk

**Success Criteria**:
- [x] All four assertions pass against the real host, not a mock
- [x] `uv run pytest` passes
- [x] Commit after this task, e.g. `feat(process): add runtime project creation`

**Files to Modify**: the host test module

---

### Task 6.3: Add the inbox settings
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 1
**Objective**: Add `inbox_batch_size` and `inbox_max_attempts` to `ProcessSettings`, each with a `start` flag like every other tunable.

**Steps**:
- [x] Add both settings to `ProcessSettings` following the existing convention
- [x] Add the corresponding `amoeba start` flags
- [x] Choose a **small** default for `inbox_max_attempts` — per the LLD the point is to bound the loop, not to retry a corrupt store into working
- [x] Centralize both defaults in the settings definition; do not hard-code either value at a call site

> Implementation note (20260923): defaults are inbox_batch_size=100 and inbox_max_attempts=3 (the LLD specifies only "small" for the latter). Both --inbox-batch-size and --inbox-max-attempts refuse values below 1.

**Success Criteria**:
- [x] Both settings are settable by flag and have centralized defaults
- [x] `grep` finds neither default value anywhere outside the settings module
- [x] `uv run pyright` clean

- [x] Commit after this task, e.g. `feat(process): add inbox batch size and max attempts settings`

**Files to Modify**: the `ProcessSettings` module, `src/amoeba/cli/lifecycle.py`

---

### Task 6.4: Implement InboxTenant's apply loop
**Owner**: Junior AI
**Dependencies**: Task 6.3
**Effort**: 3
**Objective**: Implement the first real `Tenant`, per the LLD's Data Flow "Apply" block.

**Steps**:
- [x] Create `src/amoeba/process/inbox_tenant.py` implementing the `Tenant` protocol (`name`, `tick(host) -> bool`)
- [x] Handle at most `inbox_batch_size` files per tick, in filename (drain) order, checking `stop_requested` **between files**
- [x] For a `create_project` envelope, call `host.open_project` before resolving the store
- [x] Delete the file **after** the transaction commits — never before; the crash table in the LLD depends on this order
- [x] Delete any `.attempts.json` counter along with the file on success
- [x] Return whether any file was handled
- [x] Log a WARNING when a submission id is reused with different content — first wins, and it is not an error (D2)
- [x] Add a smoke test covering **all three** of this task's claims before moving on: one `intent` submission applies and its file is deleted; a tick with more files than `inbox_batch_size` handles exactly that many; a tick with `stop_requested` set stops early. The full branch coverage stays in Task 6.8, but these are this task's own success criteria and should not go four tasks unverified

> Implementation note (20260923): Tasks 6.4–6.6 landed as one commit (fcb0813) — split, the 6.4 version would have had to crash on a bad file. The tenant types its host as a small InboxHost protocol that ResidentProcess satisfies; in-process tests drive it through tests/local_host_harness.py (real ProjectStores, no process).

**Success Criteria**:
- [x] A tick handles at most `inbox_batch_size` files and stops early when `stop_requested` is set, **proven by the smoke test**
- [x] The file delete follows the commit, so a crash between them leaves a recorded submission and a file that is a no-op on restart
- [x] The tenant is the only module importing both `amoeba.inbox` and `amoeba.store` write paths
- [x] `uv run pyright` clean
- [x] Commit after this task, e.g. `feat(process): add inbox apply loop`

**Files to Create**: `src/amoeba/process/inbox_tenant.py`, `tests/process/test_inbox_tenant.py`

---

### Task 6.5: Implement the quarantine ladder
**Owner**: Junior AI
**Dependencies**: Task 6.4
**Effort**: 2
**Objective**: Route every submission that cannot be attributed to an open store into `quarantine/` with its reason, never raising.

**Steps**:
- [x] Quarantine with the matching `QuarantineReason` for each member of the closed vocabulary: unparseable envelope, unknown envelope version, unknown kind, invalid project id, invalid payload, and no store for the project
- [x] Move the file and write a `.reason.json` sidecar; **never delete content**
- [x] Continue to the next file after quarantining — a bad submission must not block later valid ones in the same tick
- [x] Do **not** convert a `StoreError` into a quarantine: quarantine means "this submission is bad", never "the store is unwell"
- [x] Quarantine a submission that races ahead of its project's creation rather than holding it, per the LLD's Special Considerations

**Success Criteria**:
- [x] Each of the six quarantine reasons is reachable and produces its sidecar
- [x] Later valid submissions in the same tick still apply after a quarantine
- [x] No `StoreError` path leads to quarantine

- [x] Commit after this task, e.g. `feat(process): add the quarantine ladder`

**Files to Modify**: `src/amoeba/process/inbox_tenant.py`

---

### Task 6.6: Implement the bounded attempt counter and the failed/ park
**Owner**: Junior AI
**Dependencies**: Task 6.5
**Effort**: 3
**Objective**: Implement the design review's F001 resolution, per the LLD's "A failing apply stops the process, but not forever."

**Steps**:
- [x] On an unexpected exception from `open_project` or `apply_submission`, read the file's `.attempts.json` (absent means zero) and increment
- [x] Below `inbox_max_attempts`: write the counter beside the file in `new/` using the **same tmp-and-rename** `submit()` uses, log with `logger.exception`, and **re-raise** so the process stops — the file stays in `new/`
- [x] At `inbox_max_attempts`: move the file **and its counter** to `inbox/failed/`, log at ERROR, and **continue to the next file** instead of re-raising
- [x] Record `{attempts, last_error, last_failed_at}` in the counter so the failure is inspectable once the process is running again
- [x] Ensure a file moved back from `failed/` to `new/` **resumes at its recorded count** rather than starting over

**Success Criteria**:
- [x] The counter survives the crash that wrote it, because it is on disk rather than in memory or in the store
- [x] The first `inbox_max_attempts - 1` failures still stop the process, so an unwell store stays loud
- [x] After parking, the tick continues and the process stays up
- [x] A requeued file resumes at its old count rather than buying a fresh set of attempts

- [x] Commit after this task, e.g. `feat(process): bound apply failures and park in failed`

**Files to Modify**: `src/amoeba/process/inbox_tenant.py`, `src/amoeba/inbox/layout.py`

---

### Task 6.7: Register InboxTenant first in amoeba start
**Owner**: Junior AI
**Dependencies**: Task 6.6
**Effort**: 1
**Objective**: Wire the tenant into the lifecycle so a backlog drains ahead of any later tenant's work.

**Steps**:
- [x] Register `InboxTenant` in `cli/lifecycle.py` as the **first** tenant — tenants tick in registration order, and the LLD requires the inbox to drain first
- [x] Confirm `amoeba start` changes from zero tenants to exactly one

**Success Criteria**:
- [x] `amoeba start` registers `InboxTenant` first
- [x] Slice 102's lifecycle tests pass, updated only where they asserted zero tenants

- [x] Commit after this task, e.g. `feat(cli): register InboxTenant first at start`

**Files to Modify**: `src/amoeba/cli/lifecycle.py`

---

### Task 6.8: Test the tenant against the real host
**Owner**: Junior AI
**Dependencies**: Task 6.7
**Effort**: 4
**Objective**: Cover the apply loop, the crash table, the quarantine ladder, and the attempt counter through `tests/host_harness.py`.

**Steps**:
- [x] Assert a submission made while the process is **stopped** is applied on start and its file is gone
- [x] Assert a `create_project` applied by a **running** process creates the store, and a later submission for that project applies **without a restart** — in the same tick and in a later one
- [x] Assert the crash-table row that no other step reaches: a process killed **between store creation and the record commit**. Create the store via `open_project`, close without applying, leave the submission file in `new/`, restart, and assert the store is discovered and opened, the record is written, and the effect happens exactly once. Task 9.1's randomized kills only hit this window by chance, and Task 10.3's `kill -9` lands after the submission has already applied
- [x] Assert replay: a file restored to `new/` after apply changes nothing and leaves exactly one record
- [x] Assert D2's different-content case explicitly: a second submission reusing an existing id with **different** content is a no-op that leaves the first record intact and logs a WARNING — not an error, since the second file may be a legitimate retry with a differing timestamp
- [x] Assert each quarantine reason lands in `quarantine/` with its sidecar and that later valid submissions in the same tick still apply
- [x] Assert the batch-size limit and early stop on `stop_requested`
- [x] Assert the pre-park half of the F001 path: a submission whose apply raises every time stops the process for `inbox_max_attempts - 1` starts, with the counter incrementing on disk across those starts
- [x] Assert the **park transition itself** as its own step — this is the rung that separates this design from a plain crash-stop, so do not fold it into the step above. On the `inbox_max_attempts`-th failure: the file **and** its counter move to `inbox/failed/`, the sidecar carries `{attempts, last_error, last_failed_at}` with the real exception text, an ERROR is logged, the tick **continues to the next file** rather than re-raising, and the process stays up
- [x] Assert a file moved from `failed/` back to `new/` resumes at its recorded count and is deleted with its counter once it applies
- [x] Assert Task 6.5's negative criterion, which nothing else tests: construct a **sick store** and confirm the submission takes the attempt-counter path and is **never** quarantined. The LLD treats the `StoreError`-versus-quarantine line as the only thing allowed to stop the queue, so a silent regression here is invisible without this test
- [x] Assert the tenant actually ticks inside a **running `amoeba start`**, not only through the harness — a submission dropped into `new/` while the real process runs is applied without further intervention

> Implementation note (20260923): real-process tests live in tests/process/test_inbox_process.py. The sick store is a directory where its .sqlite3 file belongs. Open item for the PM: the CLI boundary maps any StoreError to ExitCode.STARTUP_FAILED (7), so a tenant's mid-run store failure exits as "startup failed"; the test asserts only a non-zero exit.

**Success Criteria**:
- [x] Every functional criterion in the LLD touching the tenant has a test here
- [x] The F001 park is proven to keep the process up
- [x] `uv run pytest` passes
- [x] Commit after this task, e.g. `feat(process): add InboxTenant apply loop`

**Files to Modify**: `tests/process/test_inbox_tenant.py` — created by Task 6.4 for its smoke test; this task extends it

---

## Section 7: The CLI

### Task 7.1: Implement amoeba submit
**Owner**: Junior AI
**Dependencies**: Task 6.8
**Effort**: 2
**Objective**: Add the operator- and bridge-usable writer, per the LLD's CLI table.

**Steps**:
- [x] Create `src/amoeba/cli/submit.py` with `create-project`, `resolution`, and `intent` subcommands taking the flags the LLD's CLI table names, each printing the submission id
- [x] Derive subcommand names **from `SubmissionKind`** — never the reverse, and never a hand-maintained second list
- [x] Call `amoeba.inbox.submit()`; open no store
- [x] Follow slice 102's CLI process-boundary and `ExitCode` conventions

> Implementation note (20260923): flags derive from each kind's payload-model fields, so a new kind needs no second list — which makes them --blocked-state-id, --node-id, and --body (JSON object) rather than the LLD draft's --blocked-state, --node, and --payload-json. Refusals exit with the new ExitCode.SUBMISSION_REFUSED (9). Tasks 7.1 and 7.2 share one commit (d204f7e) because both edit main.py; main.py's flag mapping moved to cli/settings_flags.py (367 -> 251 lines).

**Success Criteria**:
- [x] Adding a `SubmissionKind` member surfaces a subcommand without editing a second list
- [x] `cli/submit.py` opens no store read-write, confirmed by the writer guard
- [x] All three subcommands work with the process running and stopped

- [x] Commit after this task, e.g. `feat(cli): add amoeba submit`

**Files to Create**: `src/amoeba/cli/submit.py`

---

### Task 7.2: Implement the three inspection listings
**Owner**: Junior AI
**Dependencies**: Task 7.1
**Effort**: 2
**Objective**: Add `inspect inbox`, `inspect submissions`, and `inspect messages`.

**Steps**:
- [x] Add `inspect inbox` as a **supervisor-level** listing (like `projects`), showing pending, quarantined, and failed files
- [x] Register `submissions` and `messages` into slice 102's listing registry as project-scoped listings taking `--project`
- [x] Give `messages` a `--channel` option
- [x] Support `--json` on all three, per the existing convention
- [x] Read through `Store.open_read_only` — these listings must work while the process is running

> Implementation note (20260923): supervisor-level listings are now marked by a supervisor_rows callable on the registry entry rather than dispatch comparing the listing's name; --channel is a ChoiceOption. The new row builders live in cli/inspect_inbox.py to keep inspect.py near budget.

**Success Criteria**:
- [x] All three listings work with the process running and stopped
- [x] `submissions` lists in `applied_seq` order
- [x] Listing names derive from the registry, not from hand-maintained strings

- [x] Commit after this task, e.g. `feat(cli): add inbox, submissions, and messages listings`

**Files to Modify**: the inspection CLI module

---

### Task 7.3: Test the CLI as real subprocesses
**Owner**: Junior AI
**Dependencies**: Task 7.2
**Effort**: 2
**Objective**: Cover `submit` and the listings the way slice 102 tests its CLI.

**Steps**:
- [x] Test each `submit` subcommand as a subprocess, asserting the printed id matches the file written in `new/`
- [x] Test all three listings with the process both running and stopped
- [x] Test `--json` output shape for each listing
- [x] Test that an invalid project id or payload exits non-zero and writes nothing

**Success Criteria**:
- [x] Tests exercise the real CLI as subprocesses, not by calling internal functions
- [x] `uv run pytest` passes
- [x] Commit after this task, e.g. `feat(cli): add submit command and inbox listings`

**Files to Create**: `tests/cli/test_submit.py`, plus additions to the inspection CLI test module

---

## Section 8: Guard and Public-API Tests

### Task 8.1: Pin the sole-writer boundary and the inbox public API
**Owner**: Junior AI
**Dependencies**: Task 7.3
**Effort**: 2
**Objective**: Make the architectural boundary mechanical rather than asserted, per the LLD's Technical Requirements.

**Steps**:
- [x] Assert the writer guard's permitted set is exactly `{process/project_stores.py}` and that the deliberate-widening test still pins a set of size one
- [x] Assert `amoeba.inbox` and `cli/submit.py` open no store read-write
- [x] Add a test asserting **`amoeba.inbox`'s public exports contain no write path other than `submit`**
- [x] Assert `amoeba.store` does not import `amoeba.inbox`, pinning the one-way dependency direction in the LLD's Component Structure

**Success Criteria**:
- [x] All four assertions pass, and each fails if the boundary it guards is violated
- [x] `uv run pytest` passes
- [x] Commit after this task, e.g. `test: pin inbox public api and writer boundary`

**Files to Modify**: `tests/test_writer_guard.py`
**Files to Create**: `tests/inbox/test_inbox_public_api.py` — **not** `test_public_api.py`, which already exists at `tests/test_public_api.py`; duplicate basenames break pytest collection

---

### Task 8.2: Write and allow-list the demo script
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 1
**Objective**: Provide the seeding helper the verification walkthrough needs.

**Steps**:
- [x] Create `scripts/demo_inbox.py` seeding one node blocked on a human in the `demo` project and printing the node id and blocked-state id
- [x] Have it perform a read-write `Store.open` and run **only while the process is stopped**, like `demo_journal.py`
- [x] Add it to `PERMITTED_SCRIPTS` in `tests/test_writer_guard.py` — **and** update the pin assertion `PERMITTED_SCRIPTS == frozenset({"demo_journal.py"})` in the same file, which fails if only the constant changes. Same trap as Task 1.2's permitted-module rename
- [x] Note in the script why it exists: nothing outside the process can create nodes until initiative 120

> Implementation note (20260923): demo_inbox.py takes the instance lock while it writes and refuses if the resident process holds it.

**Success Criteria**:
- [x] The script prints both ids and the writer guard passes with it allow-listed
- [x] The guard's script allow-list grows by exactly one entry

- [x] Commit after this task, e.g. `test: add demo_inbox script and allow-list it`

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
- [x] Run several submitter **processes**, each submitting a few hundred `intent` submissions to projects created **through the inbox during the run**
- [x] Deliberately resubmit a fraction under the **same id** to exercise D2
- [x] `SIGKILL` and restart the resident process at random points throughout
- [x] Assert: every distinct id has exactly one record **and** exactly one message; `applied_seq` has no duplicates; `inbox/new/` drains to empty; no `tmp/` file is ever applied
- [x] Place the test in the existing `tests/load/` tier

> Implementation note (20260923): 4 submitters x 2000 intents; kills continue through the drain until 10 have landed. Submitter output goes to files — undrained pipes deadlocked earlier drafts — and the kill window's floor (0.15 s) sits above measured startup (~0.09 s) so restarts do not starve. The "resident runs as real amoeba start" choice means the tenant is exercised exactly as shipped.

**Success Criteria**:
- [x] The test kills and restarts the process mid-run and still asserts exactly-once per id
- [x] Projects are created through the inbox during the run, exercising runtime creation under load
- [x] `uv run pytest tests/load` passes

- [x] Commit after this task, e.g. `test: add concurrent submitter load test`

**Files to Create**: `tests/load/test_inbox_concurrent.py`

---

### Task 9.2: Measure and record the drain-time bound
**Owner**: Junior AI
**Dependencies**: Task 9.1
**Effort**: 1
**Objective**: Follow slice 102's measure-first rule rather than guessing a threshold.

**Steps**:
- [x] Measure the observed drain time first
- [x] Assert at roughly **twice** the observation
- [x] Record the measured number in the test as a comment, per slice 102's precedent

> Implementation note (20260923): measured final drain 2.945–3.196 s for ~6,100–6,330 files over 10 runs (~2,000 files/s); bound asserted at 6.5 s; recorded in the test's module docstring.

**Success Criteria**:
- [x] The threshold is derived from a recorded measurement, not chosen arbitrarily
- [x] The recorded number is present in the test
- [x] Commit after this task, e.g. `test: add concurrent submitter load test`

**Files to Modify**: `tests/load/test_inbox_concurrent.py`

---

## Section 10: Documentation and Completion

### Task 10.1: Write docs/inbox-contract.md
**Owner**: Junior AI
**Dependencies**: Task 9.2
**Effort**: 2
**Objective**: State the delivery and replay semantics, per the LLD's "Delivery and Replay Semantics" section — which is the content this document must carry.

**Steps**:
- [x] State every **Guaranteed** item the LLD lists: durability on return, exactly-once effect per id, atomic effect and record, every submission reaching a terminal inspectable state, one receiver-assigned authoritative order, replayable messages, and an escalation row with every human block
- [x] State every **Not guaranteed** item: apply order versus submit order, latency, outcome notification, that a valid submission is applied, what an open blocked state means for a recovery-attached escalation, and retention
- [x] State the rule that a submitter creating a project waits for `submission(id)` to report `applied` before submitting into it
- [x] Repeat slice 102's rule that callers must not place secrets in payloads
- [x] Write for a reader who has not read the implementation — an initiative 160 slice design must be able to proceed from this document alone

**Success Criteria**:
- [x] Every guaranteed and not-guaranteed item in the LLD appears
- [x] The document is sufficient for an initiative 160 slice design without reading the implementation
- [x] Durability is stated as "fsync-durable on a POSIX filesystem" rather than overclaimed

- [x] Commit after this task, e.g. `docs: add inbox contract`

**Files to Create**: `docs/inbox-contract.md`

---

### Task 10.2: Update the existing contracts and the changelog
**Owner**: Junior AI
**Dependencies**: Task 10.1
**Effort**: 1
**Objective**: Record this slice's changes to slices 101 and 102, per the LLD's "Consumes from Other Slices."

**Steps**:
- [x] `docs/store-contract.md`: `block()` gains `payload=None` and a `HUMAN` block writes an escalation row; `journal_escalate` shares the block writer and escalates on its already-blocked branch; the new inbox and message methods
- [x] `docs/process-contract.md`: `open_project`; `project_ids` is no longer fixed at startup; read-write opening moved to `process/project_stores.py`; `amoeba start` now registers `InboxTenant` first
- [x] `CHANGELOG.md`: schema version 4 and the slice's user-visible additions
- [x] Note in the process contract that consumers **must not cache `project_ids`**, which initiative 120 depends on

**Success Criteria**:
- [x] All three documents reflect the shipped behavior
- [x] Both recorded consequences of D3 appear in the store contract

- [x] Commit after this task, e.g. `docs: update store and process contracts for slice 103`

**Files to Modify**: `docs/store-contract.md`, `docs/process-contract.md`, `CHANGELOG.md`

---

### Task 10.3: Run the integration walkthrough and capture real output
**Owner**: Junior AI
**Dependencies**: Task 10.2 — the contracts and changelog are in place before output is captured, so the walkthrough runs against the documented behavior rather than ahead of it
**Effort**: 2
**Objective**: Execute the LLD's Verification Walkthrough end to end and replace its draft output with captured output.

**Steps**:
- [x] Run all eight steps from an **empty** supervisor directory through the real CLI as subprocesses
- [x] Replace the LLD's draft walkthrough output with the captured output, removing the "Draft" note
- [x] Add the end-to-end integration test the LLD's Integration Requirements names: `start` → `submit create-project` → seed a human-blocked node → read its escalation row read-only → `stop` → `submit resolution` → `start` → node is `runnable` → `kill -9` → `start` → state unchanged and no second apply
- [x] Investigate any divergence between the draft and reality as a defect or a design correction, not as a transcript to edit

**Success Criteria**:
- [x] The walkthrough in the LLD shows real captured output
- [x] The end-to-end test passes, including the `kill -9` step
- [x] Commit after this task, e.g. `docs: capture slice 103 walkthrough output`

**Files to Modify**: `user/slices/103-slice.durable-inbox-and-message-queue.md`
**Files to Create**: the end-to-end integration test module

---

### Task 10.4: Final verification and slice completion
**Owner**: Junior AI
**Dependencies**: Task 10.3
**Effort**: 1
**Objective**: Confirm every success criterion in the LLD and close the slice.

**Steps**:
- [x] Run `uv run pytest && uv run pytest tests/load`
- [x] Run `uv run ruff check . && uv run ruff format --check . && uv run pyright`
- [x] Walk the LLD's Functional, Technical, and Integration Requirements checklists and confirm each item
- [x] Confirm source files stay near 300 lines, **`host.py` included**
- [x] Set `status: complete` in both task files and in the slice design

**Success Criteria**:
- [x] All quality gates clean
- [x] Every LLD success criterion is verified, not assumed
- [x] `host.py` is within the line guideline, closing the item slice 102 left open
- [ ] Commit, then merge the slice branch into the integration target — **re-read `cf config get git.integration_branch` first** rather than inferring the target from the current branch or from memory (merge step deferred to main agent) **(merge deferred: PM requires code review before merge)**

**Files to Modify**: both task files, `user/slices/103-slice.durable-inbox-and-message-queue.md`
