---
docType: review
layer: project
reviewType: code
slice: store-contract-changes-for-the-runner
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: c362b3eee8f57f7ed402af23a998a96956b3baf5
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: false
turns: 2
promptTokens: 229215
cachedTokens: 25664
cacheWriteTokens: 203547
completionTokens: 3634
durationSeconds: 30.0
costUsd: 0.860696
costBasis: provider
runId: run-20261023-p56-87870251
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: testing
    summary: "Concurrency guarantees are claimed but never exercised by a test"
    location: "src/amoeba/store/project_escalations.py:58-62"
  - id: F002
    severity: note
    category: design
    summary: "Routing-decision validation runs outside the write lock"
    location: "src/amoeba/store/routing_decisions.py#RoutingDecisionOperations._validate_routing_decision"
  - id: F003
    severity: note
    category: dry
    summary: "Blocked-status refusal is applied twice for a `StatusEffect`"
    location: "src/amoeba/store/routing_decisions.py:60-63"
  - id: F004
    severity: note
    category: testing
    summary: "Test helpers are duplicated"
    location: "tests/store/test_messages.py:360-370"
  - id: F005
    severity: note
    category: testing
    summary: "Tests reach into private members"
    location: "tests/store/test_routing_validation.py:52"
  - id: F006
    severity: note
    category: style
    summary: "`__all__` grouping is inconsistent"
    location: "src/amoeba/store/__init__.py:126-129"
  - id: F007
    severity: pass
    category: design
    summary: "Done-is-terminal enforcement is centralised and guarded"
    location: "src/amoeba/store/_block_writer.py:55-117"
  - id: F008
    severity: pass
    category: sql
    summary: "Schema, SQL and mapping follow project conventions"
    location: "src/amoeba/store/schema/009_runner_contract.sql"
---

# Review: code — slice 121

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Concurrency guarantees are claimed but never exercised by a test

`raise_project_escalation` and `record_routing_decision` rely on `BEGIN IMMEDIATE` to stop two writers racing. For escalations the race is two raisers both seeing "none open". For decisions it is the attempt counter being read and then incremented. The comments and docstrings state these guarantees. `tests/store/test_project_escalation.py` and `tests/store/test_routing_decisions.py` only call them sequentially. The partial unique index backstops the escalation case, but nothing checks that a second connection gets the existing row back instead of an `IntegrityError`. Nothing checks either that concurrent decisions on one `(node, step)` get distinct counts. The Python rules ask for a realistic-configuration test on concurrency paths. Add a test with two `Store` handles on one file, ideally in `tests/load/`.

### [NOTE] Routing-decision validation runs outside the write lock

Node-in-project and journal-entry-in-project checks run before `BEGIN IMMEDIATE`. The state-dependent effect checks (done, blocked, unresolved entry) correctly run inside the transaction, and the docstring says so. Because the node and entry FKs protect the writes, the gap is benign today. If rows are ever deletable, move these checks inside the lock.

### [NOTE] Blocked-status refusal is applied twice for a `StatusEffect`

`_check_values` calls `refuse_blocked_status` for `StatusEffect`, and `BlockWriter._write_status` repeats it. The early check does give a pre-transaction failure, and it is tested. Still, two sites need editing if the rule changes. The `_write_status` docstring says it is the single place the rules live.

### [NOTE] Test helpers are duplicated

`_submit_intent` repeats `routing_helpers.submit_intent`. `test_routing_validation.py` redefines `TABLE` and `_decision`, which `routing_helpers` already provides. Reuse the shared helpers.

### [NOTE] Tests reach into private members

`_check` calls `store._validate_routing_decision`, and `test_routing_reads.py` uses `store._connection`, each with a pyright ignore. The validation behaviour is also covered through the public method in `test_routing_decisions_atomic.py`. Prefer that route where possible.

### [NOTE] `__all__` grouping is inconsistent

`"Route"` sits among the enums and constants, between `"Channel"` and `"CommandKind"`. The other new runner types are under "Transfer objects". Move it for consistency.

### [PASS] Done-is-terminal enforcement is centralised and guarded

`BlockWriter._write_status`, `_refuse_done`, `_refuse_if_blocked` and the shared `refuse_blocked_status` give one set of rules for `update_node_status`, `StatusEffect` and `BlockEffect`. `tests/store/test_terminal_done.py` adds an AST inventory test that fails if any other module references `UPDATE_NODE_STATUS`. This is a mechanical guard rather than an advisory one.

### [PASS] Schema, SQL and mapping follow project conventions

- All SQL is parameterised, with column names defined once in `sql_inbox` and `sql_runner`.
- The partial-index `WHERE` literals are repeated deliberately and documented.
- The migration is nullable and needs no backfill.
- Row mappers raise on bad width or an unknown vocabulary value, with no silent defaults.
- The `except ValueError`/`TypeError` re-raises are specific and commented.
- The migration test covers an upgrade of a populated version-8 store, and the `acknowledge_message` outcome validation is tested.

### Run Digest

- Response length: 4113 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 229215 / 25664 / 203547 / 3634 / not computed
- Duration: 30.0 s
- Cost: $0.86 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
