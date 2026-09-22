---
docType: review
layer: project
reviewType: tasks
slice: durable-inbox-and-message-queue
targetKind: slice
rulesSource: project
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260922
dateUpdated: 20260922
reviewedSha: ea9e3e22620271d9a4887a68763abddd81cfcb05
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 11
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "No task covers the `inbox_max_attempts`-th failure actually parking in `failed/`"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:146-216"
    resolution: accepted
    resolvedBy: "park transition split into its own assertion step in 6.8"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Tenant lifecycle smoke-test success criteria hang off a task that does not implement the loop"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:171"
    resolution: rejected
    resolvedBy: "section 6 chain is linear 6.1-6.8; no cycle. tick-in-start point accepted into 6.8"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "Task 6.5's no-`StoreError`-quarantine criterion is stated but never tested"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:138"
    resolution: accepted
    resolvedBy: "task 6.8 gains a sick-store step for the StoreError boundary"
  - id: F004
    severity: note
    category: documentation
    summary: "Task 6.4's smoke test says \"two claims\" but lists three"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:109"
    resolution: accepted
    resolvedBy: "task 6.4 now reads all three claims"
  - id: F005
    severity: note
    category: documentation
    summary: "Task 6.4 and Task 6.8 both claim to create the same test file"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:215"
    resolution: accepted
    resolvedBy: "task 6.8 now says Files to Modify"
  - id: F006
    severity: note
    category: documentation
    summary: "Task 8.2 must also update the writer guard's pin of the script allow-list"
    location: "tests/test_writer_guard.py:264"
    resolution: accepted
    resolvedBy: "task 8.2 now names the PERMITTED_SCRIPTS pin"
  - id: F007
    severity: note
    category: sequencing
    summary: "Task 10.3 modifies a task-10.1 deliverable but is sequenced after 10.2"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:428"
    resolution: accepted
    resolvedBy: "task 10.3 dependency line states the ordering reason"
  - id: F008
    severity: note
    category: documentation
    summary: "Task 10.3's example commit message overlaps Task 10.1's"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:447"
    resolution: accepted
    resolvedBy: "task 10.3 commit message made distinct"
  - id: F009
    severity: pass
    category: nfr
    summary: "Load-tier NFR has a load test in `tests/load/` and CI wiring to gate it"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:336-359"
  - id: F010
    severity: pass
    category: architecture
    summary: "Architectural boundary success criteria are each covered by a pinned test"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:289"
  - id: F011
    severity: pass
    category: test-with
    summary: "Test-after-implementation pairs keep tests adjacent to their tasks"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:51-266"
  - id: F012
    severity: pass
    category: process
    summary: "Commit checkpoints are distributed, not batched at the end"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:25-471"
---

# Review: tasks — slice 0

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [CONCERN] No task covers the `inbox_max_attempts`-th failure actually parking in `failed/`

Task 6.6 implements the park ("At `inbox_max_attempts`: move the file **and its counter** to `inbox/failed/`…") and Task 6.8 asserts the pre-park behavior ("stops the process for `inbox_max_attempts - 1` starts with the counter incrementing on disk, then lands in `failed/`"). But the rung that differentiates this design from a plain crash-stop — the terminal park, sidecar contents (`{attempts, last_error, last_failed_at}`), and the tick continuing instead of re-raising — is never exercised in either part of the breakdown. Task 6.6's success criteria are stated as claims without a test task; Task 6.8's F001 step stops at the count boundary reached and requeue-after-park, and no test elsewhere (Sections 7–10) covers the park transition itself. The park's `failed/` sidecar contents are likewise read back only by `pending()`/`failed()` listings (Task 5.4, part 1), which are implemented before the park exists. A junior AI executing Task 6.8 has no step that makes the `inbox_max_attempts`-th failure happen and inspects `inbox/failed/`. Split the F001 step in Task 6.8 into an explicit park-assertion step (park transition, ERROR log, tick continues, sidecar fields).

### [CONCERN] Tenant lifecycle smoke-test success criteria hang off a task that does not implement the loop

Task 6.4's success criteria ("A tick handles at most `inbox_batch_size`… proven by the smoke test") depend on Task 6.7 (registration), which depends on Task 6.5 and 6.6, which in turn depend on Task 6.4. Task 6.7's own criteria are lifecycle-shaped (`amoeba start` registers `InboxTenant` first; slice 102's lifecycle tests pass), not apply-loop-shaped, and Task 6.8 runs only after Task 6.7 — so as written, the registered-tick behavior (tenant actually ticks within a running `amoeba start`) is never directly asserted. The criteria stated in 6.4 are testable only through the harness at the tick level, which 6.2's harness does exercise, so this is closable inside 6.8; but the current dependency chain leaves the criterion satisfied only if a later task happens to repeat it. Consider moving the batch-size/stop assertions explicitly into Task 6.8's step list or reordering 6.7's criteria to name the tick.

### [CONCERN] Task 6.5's no-`StoreError`-quarantine criterion is stated but never tested

Task 6.5's success criterion "No `StoreError` path leads to quarantine" is a negative architectural property, but no step in Task 6.8 (or any other task) constructs a sick store and asserts the submission instead follows the attempt-counter path. This matters because the LLD's Risk Assessment treats the StoreError-vs-quarantine distinction as the only thing allowed to stop the queue. Without a test, a junior AI can satisfy every other step and still regress this boundary silently.

### [NOTE] Task 6.4's smoke test says "two claims" but lists three

The step text reads "covering this task's two claims" and then enumerates three assertions (intent applies and file deleted; batch size caps; `stop_requested` stops early). A junior AI could read this as only needing two of the three. Correct the count or enumerate them as a checklist.

### [NOTE] Task 6.4 and Task 6.8 both claim to create the same test file

Task 6.4 lists `tests/process/test_inbox_tenant.py` under **Files to Create** (for its inline smoke test), and Task 6.8 lists it again. Since 6.4 runs first and commits, the smoke-test file will already exist when 6.8 starts; "Files to Create" should read "Files to Modify" there. Functionally harmless — 6.8 will extend it — but the repeated "Create" is misleading.

### [NOTE] Task 8.2 must also update the writer guard's pin of the script allow-list

The guard has a test asserting `PERMITTED_SCRIPTS == frozenset({"demo_journal.py"})` exactly. Task 8.2 says the allow-list "grows by exactly one entry" and modifies `tests/test_writer_guard.py`, so the work is covered, but the task never names this pin assertion — the same trap Task 1.2 (part 1) documented for the permitted-module rename, where four unnamed places went stale. An explicit step ("update the `frozenset({...})` pin in the allow-list test") would save the junior AI a debugging round-trip.

### [NOTE] Task 10.3 modifies a task-10.1 deliverable but is sequenced after 10.2

Task 10.3's `Files to Modify` includes `user/slices/103-slice.durable-inbox-and-message-queue.md` (replacing the draft walkthrough with captured output). Task 10.1 is the walkthrough's prerequisite (it writes `docs/inbox-contract.md`), and 10.2 updates the other contracts, so the ordering works — but the dependency 10.3 → 10.2 is only because 10.2's changelog should be in place before walkthrough output is captured, which is worth stating so the sequence isn't read as arbitrary.

### [NOTE] Task 10.3's example commit message overlaps Task 10.1's

Both Task 10.1 and Task 10.3 suggest `docs: add inbox contract and capture walkthrough output` / `docs: add inbox contract`, producing two commits with near-identical summaries on the same slice. Minor `git log --oneline` noise; suggest a distinct summary like `docs: capture walkthrough output in slice 103`.

### [PASS] Load-tier NFR has a load test in `tests/load/` and CI wiring to gate it

The slice design's concurrency/process-boundary work triggers the Python rule that load tests must exist and be CI-gated. Task 9.1 creates `tests/load/test_inbox_concurrent.py` in the existing tier with exactly-once, `applied_seq`-duplicate, drain-to-empty, and no-`tmp/`-applied assertions; Task 9.2 follows the slice-102 measure-first rule with a recorded drain-time bound, satisfying "assert on latency/throughput bounds, not just functional correctness." I verified the CI gate exists: `.github/workflows/ci.yml:47` runs `uv run pytest tests/load` as a separately failing step, and `pyproject.toml:53` excludes the tier from the default suite so the explicit gate is the only entry point — the gate is not left implicit, and Task 10.4's final verification runs both suites.

### [PASS] Architectural boundary success criteria are each covered by a pinned test

Task 8.1's four assertions map one-to-one to the slice design's technical criteria: permitted set exactly `{process/project_stores.py}` with the widening test still size-one; `amoeba.inbox` and `cli/submit.py` open no store read-write; `amoeba.inbox` public exports contain no write path other than `submit`; and `amoeba.store` does not import `amoeba.inbox` (the one-way dependency direction). Task 8.1 also correctly dodges the duplicate-basename pytest-collection trap by naming `tests/inbox/test_inbox_public_api.py` rather than `test_public_api.py`, consistent with the `__init__.py` convention Task 5.5 (part 1) established. Task 8.2 extends the guard's script allow-list, which is scope in service of the walkthrough (Task 10.3) rather than creep.

### [PASS] Test-after-implementation pairs keep tests adjacent to their tasks

Within Sections 6 and 7: 6.1→6.2 (open_project), 6.4→(inline smoke test), 6.4→6.8 (full tenant coverage), 7.1+7.2→7.3 (CLI as real subprocesses), and the load tier 9.1→9.2 all follow the implement-then-test pattern immediately; part 1 of the breakdown shows the same pattern for the store work (2.1→2.2, 2.3→2.4, 3.1→3.2, 3.3→3.4, 4.1/4.2→4.3, 5.2→5.3, 5.4→5.5). One deviation — Task 6.5 and 6.6 defer their tests to 6.8 rather than getting their own test tasks — is mitigated by 6.4's inline smoke test requirement and is acceptable, though the three CONCERNed coverage gaps above live exactly in that deferred stretch.

### [PASS] Commit checkpoints are distributed, not batched at the end

Every task in Sections 6–10 carries its own `Commit after this task` checkpoint with a semantic commit message suggestion (`feat(process)`, `feat(cli)`, `test:`, `docs:`), matching the project convention of at least one commit per task and leaving no stretch of implementation without a checkpoint. Task 10.4 correctly defers the branch merge until after final verification and explicitly instructs re-reading `cf config get git.integration_branch` before merging, per the git rules.

## Response

Seven of eight actionable findings accepted and resolved on 20260922. F002 is rejected on the evidence, with the one real point inside it folded into Task 6.8. Every code-level claim was checked against source first.

**F001 — accepted, the strongest finding here.** Correct that 6.8's step said "then lands in `failed/`" and stopped there: nothing made the `inbox_max_attempts`-th failure happen and then inspected the result. The step is now split. The pre-park half asserts the counter incrementing across restarts; a separate step asserts the park transition itself — file and counter moved, sidecar carrying the real exception text, ERROR logged, tick continuing to the next file, process staying up. That transition is the whole point of the F001 design from the slice review, and it was asserted only as prose.

**F002 — rejected.** The dependency chain in Section 6 is linear: 6.1→6.2→6.3→6.4→6.5→6.6→6.7→6.8, each task naming its immediate predecessor, verified by reading the `Dependencies` lines. There is no cycle. The finding conflates "this task's criteria are not fully proven until later" with "this task depends on a later task"; 6.4's smoke test runs against `tests/host_harness.py` at tick level and needs nothing from 6.7. The real observation buried in it is accepted: nothing asserted the tenant ticking inside a **running `amoeba start`** as opposed to through the harness. Task 6.8 gains that step.

**F003 — accepted.** Task 6.5's "No `StoreError` path leads to quarantine" was a negative architectural property stated with nothing constructing a sick store to prove it. Given that the LLD treats the `StoreError`-versus-quarantine line as the only thing allowed to stop the queue, a silent regression would have been invisible. Task 6.8 gains an explicit step.

**F004 — accepted.** "Two claims" followed by three enumerated assertions, introduced when Task 6.4's smoke test was added in response to the previous review. Now reads "all three".

**F005 — accepted.** Both 6.4 and 6.8 listed `tests/process/test_inbox_tenant.py` under Files to Create, an artifact of that same edit. Task 6.8 now says Files to **Modify**, noting 6.4 creates it.

**F006 — accepted, and a good catch of a repeated pattern.** Confirmed `PERMITTED_SCRIPTS == frozenset({"demo_journal.py"})` is pinned exactly in `tests/test_writer_guard.py`. Task 8.2 said the allow-list "grows by exactly one entry" without naming the pin — the same trap the previous review found in Task 1.2, in a different place. The pin is now named explicitly.

**F007 — accepted.** Task 10.3's dependency line now states why it follows 10.2 rather than leaving the order to be read as arbitrary.

**F008 — accepted.** Tasks 10.1 and 10.3 both suggested `docs: add inbox contract`. 10.3's is now `docs: capture slice 103 walkthrough output`.

Task 6.8 absorbed four new assertions across both reviews, so its relative effort moves 3 → 4.

**On the passes:** F009's CI claim was verified and holds, though the step is at `.github/workflows/ci.yml:54`, not line 47 as cited. F010–F012 were spot-checked and are accurate.

### Run Digest

- Response length: 10305 chars
- Response is newline-free: no
- Tool calls made: 11
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 3721
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
