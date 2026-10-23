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
reviewedSha: 42b3631a257bf7035a91bfc0a98e130cb2c0facd
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 93884
cachedTokens: 3232
cacheWriteTokens: 90650
completionTokens: 3665
durationSeconds: 29.4
costUsd: 0.407172
costBasis: provider
runId: run-20261023-p56-87870251
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Raising a project escalation is check-then-insert outside a transaction"
    location: "src/amoeba/store/project_escalations.py:62-88"
  - id: F002
    severity: concern
    category: correctness
    summary: "`desired_state(project_id, node_id=...)` ignores `project_id` for node targets"
    location: "src/amoeba/store/desired_states.py:44-52"
  - id: F003
    severity: concern
    category: concurrency
    summary: "Block-effect \"already blocked\" check runs before the write lock is taken"
    location: "src/amoeba/store/routing_decisions.py:239-262"
  - id: F004
    severity: concern
    category: dry
    summary: "Duplicated helpers across the new store modules and tests"
    location: "src/amoeba/store/routing_decisions.py:46-58"
  - id: F005
    severity: concern
    category: simplicity
    summary: "Redundant node reads in the status-write path"
    location: "src/amoeba/store/_block_writer.py:78-95"
  - id: F006
    severity: note
    category: testing
    summary: "Tests reach into private members and rely on `type: ignore`"
    location: "tests/routing_helpers.py:52"
  - id: F007
    severity: note
    category: documentation
    summary: "Class and module docstrings understate what `RoutingDecisionOperations` does"
    location: "src/amoeba/store/routing_decisions.py:1-9"
  - id: F008
    severity: pass
    category: testing
    summary: "Atomicity, terminal-`done` enforcement and migration coverage"
    location: "tests/store/test_terminal_done.py"
---

# Review: code — slice 121

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Raising a project escalation is check-then-insert outside a transaction

`raise_project_escalation` runs the open-row `SELECT` and then, in a separate `with self._connection:` block, the `INSERT`. The docstring promises "return the one already open". If another writer inserts the same `(project, fault_kind)` between the two statements, the partial unique index rejects the insert. The caller then gets a raw `sqlite3.IntegrityError` instead of the existing row. `record_routing_decision` handles the same problem with `BEGIN_IMMEDIATE`. Move the select inside the transaction after taking the write lock, or catch the integrity error narrowly and re-read. Nothing in the diff tests the contended case.

### [CONCERN] `desired_state(project_id, node_id=...)` ignores `project_id` for node targets

When `node_id` is given, `SELECT_DESIRED_NODE_TARGET` binds only the node id. A caller who passes a node from another project gets that project's row back, and `project_id` is silently unused. The write path enforces project membership via `_require_node_in_project`, so the read should too. Add `project_id = ?` to the node-target select. Also add a test for a node queried under the wrong project; none exists.

### [CONCERN] Block-effect "already blocked" check runs before the write lock is taken

`_validate_routing_decision` calls `_refuse_if_blocked(node)` on a node read before `BEGIN IMMEDIATE`. Inside the transaction, `_write_block` re-checks only `done`, not blocked. `StatusEffect` re-validates inside the lock through `_write_status`, but `BlockEffect` does not. If the node is blocked between validation and the lock, a second block can be written over the first. `block()` already has this gap, but this change adds a second caller and its comments say it is atomic. Re-run `_refuse_if_blocked` on a fresh `_require_node` after `BEGIN_IMMEDIATE`.

### [CONCERN] Duplicated helpers across the new store modules and tests

`_require_text` is defined identically in `routing_decisions.py` and `project_escalations.py`. The JSON-encode-or-`ValueError` helper (`_encode` and `_encode_payload`) is also copied. In tests, `_decision` in `tests/store/test_routing_validation.py` duplicates `routing_helpers.decision_input` and `TABLE`. Project rules require DRY. Extract the helpers into one shared module (for example `store/_validation.py`) and have the validation test import from `routing_helpers`.

### [CONCERN] Redundant node reads in the status-write path

`update_node_status` calls `_require_node`. `_write_status` then calls `_require_node` again, and `_refuse_done` calls it a third time. That is three identical SELECTs per status write. Have `_refuse_done` accept the already-loaded `Node` (as `_refuse_if_blocked` does), or drop the leading `_require_node` in `nodes.py`.

### [NOTE] Tests reach into private members and rely on `type: ignore`

`routing_helpers.py` and `test_routing_validation.py` use `# type: ignore[arg-type]`. The Python rules call for pyright, so prefer `# pyright: ignore[...]` or build the input with typed keyword arguments. `test_routing_reads.py` and `test_routing_validation.py` call `store._connection` and `_validate_routing_decision` directly. The public path already covers the validation (`test_routing_decisions_atomic.py`), so the private-method tests are optional.

### [NOTE] Class and module docstrings understate what `RoutingDecisionOperations` does

The module and class docstrings describe "reads", but the class also holds the write path `record_routing_decision`. The module docstring also says decisions are "written only by `record_routing_decision`" while calling the module reads-only. Update both so they match.

### [PASS] Atomicity, terminal-`done` enforcement and migration coverage

All status writers now go through `_write_status`, which is `BlockWriter`'s single write path for `nodes.status`. An AST inventory test guards it. Fault-injection tests cover each step of the routing-decision transaction and the desired-state write. Migration 009 is tested from a populated version-8 store, including the partial unique indexes. Acknowledgment outcome validation happens before any write, and `outcome` is required with no default.

### Run Digest

- Response length: 4811 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 93884 / 3232 / 90650 / 3665 / not computed
- Duration: 29.4 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
