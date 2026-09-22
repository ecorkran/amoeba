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
sourceDocument: project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-1.md
aiModel: qwen/qwen3.8-2.4t-a95b
status: complete
dateCreated: 20260922
dateUpdated: 20260922
reviewedSha: 66c59fa6a8c22011217a7bcad40c03a064f65765
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 36
findings:
  - id: F001
    severity: pass
    category: task-coverage
    summary: "All slice success criteria trace to tasks"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md"
  - id: F002
    severity: pass
    category: load-testing
    summary: "Load-test NFR is covered and explicitly CI-gated"
    location: ".github/workflows/ci.yml"
  - id: F003
    severity: concern
    category: test-maintenance
    summary: "Task 1.2's \"constant-only\" claim ignores a hardcoded guard assertion"
    location: "tests/test_writer_guard.py:222-224"
    resolution: accepted
    resolvedBy: "task 1.2 now changes all four host.py literals in the guard"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Task 3.2 requires a payload round-trip test before any payload can be persisted"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-1.md:201"
    resolution: accepted
    resolvedBy: "payload round-trip assertion moved from task 3.2 to 3.4"
  - id: F005
    severity: concern
    category: task-scope
    summary: "Project-id validation is embedded in store_path(), not independently reusable"
    location: "src/amoeba/store/paths.py:63-89"
    resolution: accepted
    resolvedBy: "task 5.1 extracts validate_project_id from store_path"
  - id: F006
    severity: concern
    category: test-infrastructure
    summary: "New test packages risk pytest collection collisions and cross-directory fixture reuse"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:272"
    resolution: accepted
    resolvedBy: "__init__.py required; fixtures to root conftest; file renamed"
  - id: F007
    severity: concern
    category: process-conformance
    summary: "Commits are batched across tasks despite the project's one-commit-per-task rule"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md"
    resolution: accepted
    resolvedBy: "per-task commits added to all 24 tasks that lacked one"
  - id: F008
    severity: note
    category: test-gap
    summary: "D2's different-content WARNING has no explicit test step"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:188"
    resolution: accepted
    resolvedBy: "task 6.8 gains an explicit different-content WARNING step"
  - id: F009
    severity: note
    category: sequencing
    summary: "Test-with pattern is batched at section granularity in a few places"
    location: "project-documents/user/tasks/103-tasks.durable-inbox-and-message-queue-2.md:93"
    resolution: accepted
    resolvedBy: "task 6.4 gains a smoke test for its own criteria"
  - id: F010
    severity: note
    category: naming
    summary: "LLD \"Mixin\" naming diverges from the existing *Operations composition style"
    location: "src/amoeba/store/store.py:45"
    resolution: accepted
    resolvedBy: "tasks specify MessageOperations and InboxOperations"
---

# Review: tasks — slice 0

**Verdict:** CONCERNS
**Model:** qwen/qwen3.8-2.4t-a95b

## Findings

### [PASS] All slice success criteria trace to tasks

Every success criterion in the slice design maps to at least one task. Functional: submit-while-stopped/replay (6.8), `create_project` running + restart race (6.8, 10.3), invalid project id (5.3, 6.5, 6.8), resolution preconditions and stale targets (4.2, 4.3), intent/acknowledge (3.3, 3.4, 4.2), D3 escalation rows (3.3–3.5), D4 ordering (4.3), quarantine ladder (6.5, 6.8), bounded attempts/`failed/` park and requeue (6.6, 6.8), `submit()` failure cleanliness (5.2, 5.3), batch size/stop (6.4, 6.8), CLI and listings running/stopped (7.1–7.3). Technical: vocabularies/SQL/layout centralization (2.1, 2.3, 5.1), one block writer (3.1), writer guard (1.2, 8.1), unchanged 102 suite (1.2), real-`submit()` fixtures (5.5), migration test (2.4), load test (9.1–9.2), quality gates and 300-line budget (10.4), docs (10.1–10.2). Integration: end-to-end walkthrough with `kill -9` (10.3) and the 160-sufficient contract doc (10.1). No scope creep detected; every task traces to a design requirement.

### [PASS] Load-test NFR is covered and explicitly CI-gated

The slice's Technical Requirement "`tests/load/` gains a concurrent-submitter test with asserted exactly-once" is covered by Task 9.1 (`tests/load/test_inbox_concurrent.py`, kill-looped process, same-id resubmissions, exactly-once assertions) plus Task 9.2's measure-first drain-time bound per slice 102's rule. No new CI wiring task is needed because `ci.yml` already runs `uv run pytest tests/load` as a separate, non-suppressed step that can fail the run independently — gating is explicit, not implicit.

### [CONCERN] Task 1.2's "constant-only" claim ignores a hardcoded guard assertion

Task 1.2 says to change `PERMITTED_MODULES` (tests/test_writer_guard.py:56) to `process/project_stores.py` and requires the suite to pass "with no changes to any slice 102 test beyond the constant." But `test_the_permitted_set_is_exactly_the_host` at line 222–224 asserts the literal `PERMITTED_MODULES == frozenset({"process/host.py"})` — changing only the constant leaves this test failing, and the task tells the junior to treat failures as extraction defects. The assertion message at line 186 and the module docstring also hardcode `process/host.py`. Task 1.2 should list that literal (and the strings) as part of its change set; otherwise the junior either violates the stated constraint or chases a phantom regression.

### [CONCERN] Task 3.2 requires a payload round-trip test before any payload can be persisted

Task 3.1 adds keyword-only `payload=None` to `block()` but explicitly defers writing escalation rows to Task 3.3, and the LLD's migration 004 adds no `payload` column to `blocked_states` (payload rides on the `messages` escalation row). So at Task 3.2 there is nowhere the payload is stored, making its step "assert `block(payload=…)` round-trips the payload and omitting it stores NULL" impossible to implement as written. Move that assertion into Task 3.4 (`tests/store/test_messages.py`), where the escalation row exists to read back.

### [CONCERN] Project-id validation is embedded in store_path(), not independently reusable

Task 5.1 says "reuse the project-id validation rule already in `amoeba.store.paths`; do not re-implement it," and Task 6.1 requires an invalid id to be refused "before any path is computed." In the actual code, the validation (non-empty, no separator, not `.`/`..`) lives inline inside `store_path()` — i.e., inside the path computation itself — and there is no standalone `validate_project_id()` function. No task scopes extracting one, and `paths.py` appears in no task's Files-to-Modify list. Add that small extraction (naturally to Task 5.1 or 6.1) so both `submit()` and `open_project` can reuse it without calling the path builder.

### [CONCERN] New test packages risk pytest collection collisions and cross-directory fixture reuse

The tasks create new directories `tests/store/`, `tests/inbox/`, `tests/process/`, `tests/cli/`, but never mention `__init__.py` files. Two concrete hazards: (1) Task 8.1 creates `tests/inbox/test_public_api.py` while `tests/test_public_api.py` already exists — under pytest's rootdir import mode, duplicate basenames in directories without `__init__.py` fail collection with an import-file mismatch; (2) Task 5.5 (file 1, line 454) says to place fixtures "where Section 6's tenant tests can reuse them," but fixtures in `tests/inbox/conftest.py` are invisible to `tests/process/` tests — conftest fixtures only apply downward. The only precedent, `tests/load/`, ships an `__init__.py`. Tasks 5.5 and 8.1 should require `__init__.py` in each new test package and put shared fixtures in the root `tests/conftest.py` (or import them explicitly).

### [CONCERN] Commits are batched across tasks despite the project's one-commit-per-task rule

CLAUDE.md requires "Git add and commit from project root at least once per task." The task files place commit checkpoints only at selected tasks, so whole runs go uncommitted: Tasks 6.3–6.7 (settings, apply loop, quarantine, attempt counter, registration) all land in the single commit at 6.8, Task 8.2's demo script and guard changes are not committed until 9.2, and Tasks 10.1–10.2 not until 10.3. This concentrates risk (a failed 6.8 test run loses attribution across five tasks' work). Add per-task commits or explicitly mark the checkpoint batching as a deliberate deviation.

### [NOTE] D2's different-content WARNING has no explicit test step

The functional requirement "Resubmitting an existing id with different content is a no-op and logs a WARNING" is implemented by Task 6.4 (line 104), but Task 6.8's assertions cover replay (file restored) without explicitly asserting the WARNING or the different-content variant. It is only implicitly caught by Task 6.8's catch-all success criterion "Every functional criterion in the LLD touching the tenant has a test here." Add an explicit step.

### [NOTE] Test-with pattern is batched at section granularity in a few places

Most of the plan pairs implementation with an immediately following test task (1.1→1.2, 2.1→2.2, 2.3→2.4, 3.1→3.2, 3.3→3.4, 5.2→5.3, 5.4→5.5, 6.1→6.2), but four implementation tasks (6.4–6.7) run before any test at 6.8, and 4.1–4.2 / 7.1–7.2 also defer testing one step. Acceptable since the test tasks enumerate every branch, but Task 6.4's own success criteria (batch size, stop_requested early-stop) are unverifiable until 6.8; a smoke test at 6.4 would reduce the blast radius.

### [NOTE] LLD "Mixin" naming diverges from the existing *Operations composition style

The assembled class is `Store(NodeOperations, BlockingOperations, JournalOperations)`, but the tasks (faithful to the LLD) speak of `MessagesMixin` and `InboxMixin` wired "alongside the existing mixins." A junior AI will follow the LLD names fine, but the naming inconsistency is worth a one-line note in Task 3.3/4.1 so the new components match the house convention (or deliberately depart from it).

## Response

All five concerns and all three notes accepted and resolved on 20260922. Every code-level claim was verified against the source before changing anything; all four that could be checked were accurate.

**F003 — accepted.** Confirmed at `tests/test_writer_guard.py`: `test_the_permitted_set_is_exactly_the_host` asserts the literal `frozenset({"process/host.py"})`, and the failure message in `_assert_no_read_write_open` plus the module docstring name it too. Task 1.2 now lists all four literals — including the test's own name — as part of its change set, and its "no other test modified" constraint is scoped to the writer guard so the junior does not chase a phantom regression.

**F004 — accepted.** Correct that the assertion was impossible as written: migration 004 adds no payload column to `blocked_states`, and the payload only becomes readable on the escalation row in Task 3.3. Task 3.2 now asserts only that `block(payload=…)` *accepts* the argument; the round-trip assertion moved to Task 3.4 with a note saying where it came from.

**F005 — accepted, and the most useful finding here.** Confirmed the three checks live inline inside `store_path()`, so there was no way to validate an id without computing a path — which both `submit()` and `open_project` need. Task 5.1 now scopes extracting `validate_project_id()` with `store_path()` calling it, keeping one definition, and `paths.py` is in its Files to Modify.

**F006 — accepted, both hazards.** `tests/test_public_api.py` does exist and `tests/load/` is the only package with an `__init__.py`. Task 8.1's new file is renamed `test_inbox_public_api.py`, and Task 5.5 now requires `__init__.py` in each new test package and puts the shared envelope fixtures in the root `tests/conftest.py` so `tests/process/` can reach them.

**F007 — accepted (PM decision).** The PM chose per-task commits over documented checkpoint batching. Twenty-four tasks gained an explicit commit step; all 38 tasks across both files now have one.

**F008 — accepted.** Task 6.8 gains an explicit step asserting the different-content case: a no-op that leaves the first record intact and logs a WARNING rather than erroring.

**F009 — accepted.** Task 6.4 gains a smoke test for its own two claims (batch size, early stop on `stop_requested`), so they are not unverified four tasks deep. Full branch coverage stays in 6.8.

**F010 — accepted.** Confirmed `Store(NodeOperations, BlockingOperations, JournalOperations)`. The tasks now specify `MessageOperations` and `InboxOperations`, with a note that this deliberately departs from the LLD's "Mixin" wording in favor of the house convention.

### Run Digest

- Response length: 8674 chars
- Response is newline-free: no
- Tool calls made: 36
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 42752
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
