---
docType: review
layer: project
reviewType: code
slice: durable-inbox-and-message-queue
targetKind: slice
rulesSource: project
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/103-slice.durable-inbox-and-message-queue.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260925
dateUpdated: 20260925
reviewedSha: 2391251b08830f8e7e14bdc3c7c1f5c36404e2ae
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
findings:
  - id: F001
    severity: pass
    category: correctness
    summary: "Crash-safety invariants (D2/D3/D4) are implemented and tested consistently"
    location: "src/amoeba/store/inbox.py#apply_submission"
  - id: F002
    severity: pass
    category: correctness
    summary: "Atomic runtime project-store creation guards against a stranded WAL"
    location: "src/amoeba/process/project_stores.py:15-33"
  - id: F003
    severity: note
    category: naming/structure
    summary: "`journal_entry_id` and `payload` are computed by row-builders but excluded from the declared table columns"
    location: "src/amoeba/cli/inspect_inbox.py:24-46"
    resolution: accepted
    resolvedBy: "journal_entry_id added to the messages table columns; payload stays JSON-only"
  - id: F004
    severity: note
    category: error-handling
    summary: "`InvalidSubmissionError` doesn't carry `detail` the way its sibling `EnvelopeError` does"
    location: "src/amoeba/inbox/submit.py:36-42"
    resolution: accepted
    resolvedBy: "InvalidSubmissionError stores detail, matching EnvelopeError"
  - id: F005
    severity: note
    category: correctness
    summary: "Explicit `BEGIN IMMEDIATE` executed inside a `with self._connection:` block"
    location: "src/amoeba/store/inbox.py:117-119"
    resolution: rejected
    resolvedBy: "store connects in legacy isolation_level mode (no autocommit arg); explicit BEGIN IMMEDIATE is correct there and covered by replay and kill tests"
---

# Review: code — slice 103

**Verdict:** PASS
**Model:** claude-sonnet-5

## Findings

### [PASS] Crash-safety invariants (D2/D3/D4) are implemented and tested consistently

Replay (D2) is enforced by checking `submission()` for an existing record before applying an effect, inside the same `BEGIN IMMEDIATE` transaction as the effect and the record insert. D3 (escalation-with-block) is centralized in `_block_writer.py`'s `BlockWriter`, used by both `blocking.py` and `journal.py`, so no code path can write a human block without its escalation row. D4 (`applied_seq`/`seq` as receiver-assigned order, independent of submitter-supplied `submitted_at`) is asserted directly in `tests/store/test_inbox_apply.py::test_order_is_apply_order_not_submitted_at`. The concurrent-kill load test (`tests/load/test_inbox_concurrent.py`) exercises all three under real SIGKILLs.

### [PASS] Atomic runtime project-store creation guards against a stranded WAL

`_create_atomically` builds a store under a `.creating` temp name, migrates it, and explicitly refuses to rename it into place if SQLite left `-wal`/`-shm` sidecars behind after close — raising `StoreError` rather than silently producing a store whose committed pages might be stranded in an orphaned WAL. Combined with cleanup of leftovers from a previous crashed attempt, this is a solid crash-safe design, and it's exercised by `tests/process/test_project_stores.py`.

### [NOTE] `journal_entry_id` and `payload` are computed by row-builders but excluded from the declared table columns

`message_rows` and `submission_rows` include `journal_entry_id`/`payload` in the returned dict, but the `messages`/`submissions` `Listing.columns` tuples in `src/amoeba/cli/inspect.py` omit them, so `amoeba inspect messages` (table form) never shows which journal entry raised an escalation — only `--json` surfaces it. This looks like a deliberate "concise table, full JSON" choice (payload is treated the same way for both listings), but since `journal_entry_id` is operator-relevant (distinguishes a recovery-raised escalation from a direct human block) it may be worth a second look at whether it belongs in the table view too.

### [NOTE] `InvalidSubmissionError` doesn't carry `detail` the way its sibling `EnvelopeError` does

`EnvelopeError` stores both `self.reason` and `self.detail`; `InvalidSubmissionError.__init__` only stores `self.reason` (detail is folded into the message string via `super().__init__`). Not a functional bug — `str(error)` is all current callers use — but the asymmetry means a future caller wanting the two exceptions to interoperate uniformly (e.g. structured logging by field) would need to special-case one of them.

### [NOTE] Explicit `BEGIN IMMEDIATE` executed inside a `with self._connection:` block

`apply_submission` issues `sql_inbox.BEGIN_IMMEDIATE` manually and then relies on the connection's context-manager `__exit__` to commit/rollback. This is a legitimate way to upgrade SQLite's default DEFERRED transaction to IMMEDIATE (so the replay check and the effect are covered by the same write-locked transaction) and appears exercised correctly by `tests/store/test_inbox_apply.py`'s replay tests. Flagging only because sqlite3's transaction-control semantics changed in Python 3.12 (`autocommit` attribute) and this pattern is sensitive to that configuration — worth double-checking against whatever `sqlite3.connect(..., autocommit=...)` (or lack thereof) is used in `_base.py`/`StoreBase`, which wasn't part of this diff.

### Run Digest

- Response length: 4333 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5

## Response

20260925. The review is thin: the 275 KB diff was truncated in the prompt and the model made no tool calls, so this PASS rests on partial input. It is a sanity check, not the Phase 7 gate on its own.

- **F003 accepted.** `journal_entry_id` tells an operator whether an escalation came from recovery or from a direct human block, so it now shows in the `messages` table. `payload` stays in `--json` only; it is free-form and would wreck the table width.
- **F004 accepted.** `InvalidSubmissionError` now stores `detail` like `EnvelopeError`.
- **F005 rejected.** `Store._connect` passes `isolation_level="DEFERRED"` and no `autocommit` argument, which is the legacy transaction mode on Python 3.12+. In that mode an explicit `BEGIN IMMEDIATE` followed by the connection context manager commits or rolls back as intended. The replay tests and the concurrent-kill load test exercise it.

