---
docType: review
layer: project
reviewType: code
slice: store-contract-changes-for-the-runner
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: 4d22a0951b73267995635e3233328ea40e715f23
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: false
turns: 2
promptTokens: 229580
cachedTokens: 25664
cacheWriteTokens: 203912
completionTokens: 3186
durationSeconds: 27.7
costUsd: 0.857718
costBasis: provider
runId: run-20261023-p56-87870251
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: design
    summary: "Done-is-terminal and blocked-status rules now share one writer"
    location: "src/amoeba/store/_block_writer.py:56-116"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Atomicity and validation ordering are sound and tested"
    location: "src/amoeba/store/routing_decisions.py:121-188"
  - id: F003
    severity: pass
    category: python-style
    summary: "Exception handling and typing follow the rules"
    location: "src/amoeba/store/write_values.py:19-26"
  - id: F004
    severity: note
    category: error-handling
    summary: "`_require_message` raises `InvalidTransitionError` for a missing row"
    location: "src/amoeba/store/_base.py:109-114"
  - id: F005
    severity: note
    category: testing
    summary: "Duplicated test staging in `test_routing_validation.py`"
    location: "tests/store/test_routing_validation.py:25-44"
  - id: F006
    severity: note
    category: schema
    summary: "`fault_kind` and `closed_*` are not constrained to escalation rows in the schema"
    location: "src/amoeba/store/schema/009_runner_contract.sql:19-26"
  - id: F007
    severity: note
    category: performance
    summary: "`intent_for_submission` scans an unindexed column"
    location: "src/amoeba/store/sql_inbox.py:230-237"
---

# Review: code — slice 121

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Done-is-terminal and blocked-status rules now share one writer

`update_node_status` and a routing decision's `StatusEffect` both go through `BlockWriter._write_status`. `block()` and `BlockEffect` share `_refuse_if_blocked` and `_write_block`. This removes the duplicated checks and keeps the rules in one place. `tests/store/test_terminal_done.py` guards the single-writer property with an AST scan that names the allowed modules.

### [PASS] Atomicity and validation ordering are sound and tested

`record_routing_decision` validates before opening a transaction and takes the write lock with `BEGIN IMMEDIATE` before reading the counter. It writes the table version, decision, counter and effect in one transaction. `tests/store/test_routing_decisions_atomic.py` injects a failure at each step and asserts that nothing landed. `raise_project_escalation` takes the same lock before its open-row check, and a test covers that too.

### [PASS] Exception handling and typing follow the rules

The only `try/except` blocks catch a specific exception type (`TypeError`, `ValueError`), carry an explanatory comment, and re-raise as a typed error with `from error`. The new code uses modern typing, `StrEnum` and frozen dataclasses. Column names and SQL live in single-definition modules (`sql_runner`, `sql_inbox`), which keeps the project's single-source-of-truth rule. The migration test checks the schema against those constants.

### [NOTE] `_require_message` raises `InvalidTransitionError` for a missing row

Its docstring says it raises "when it does not exist", but the message text says "vanished". That is accurate for its post-write callers (`acknowledge_message`, `raise_project_escalation`, `close_project_escalation`), where the row is expected to exist. It is a less natural exception type if the helper is reused for a plain lookup. A `StoreIntegrityError`, as `record_routing_decision` uses for the same situation, would be more consistent. The current behavior is acceptable.

### [NOTE] Duplicated test staging in `test_routing_validation.py`

`PROJECT`, `TABLE` and `_decision` repeat what `tests/routing_helpers.py` already provides as `decision_input`. Reusing the shared helper would satisfy DRY. The only difference is that this file builds its decisions without a `journal_entry_id` default.

### [NOTE] `fault_kind` and `closed_*` are not constrained to escalation rows in the schema

The partial unique index only constrains open escalation rows with a fault kind. Nothing at the schema level stops `fault_kind` being set on an intent row. The store API never does this, and `close_project_escalation` filters by channel. A `CHECK (fault_kind IS NULL OR channel = 'escalation')` would make the invariant structural. SQLite `ALTER TABLE ADD COLUMN` limits how this can be added, so this is optional.

### [NOTE] `intent_for_submission` scans an unindexed column

The code and docstring both say `submission_id` has no index and point to issue #19. This is a known, documented trade-off. It is cheap now but grows linearly with the number of intents.

### Run Digest

- Response length: 3620 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 2
- Tokens — prompt / cached / cache write / completion / reasoning: 229580 / 25664 / 203912 / 3186 / not computed
- Duration: 27.7 s
- Cost: $0.86 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
