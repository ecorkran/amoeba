---
docType: review
layer: project
reviewType: tasks
slice: store-contract-changes-for-the-runner
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: 64208ab23b6cee797a6407a4f0223f7af036fe2e
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 203261
cachedTokens: 98819
cacheWriteTokens: 104436
completionTokens: 6602
durationSeconds: 51.3
costUsd: 0.494464
costBasis: provider
runId: run-20261023-p56-87870251
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 7.3 `StatusEffect` cannot reuse `update_node_status` inside its transaction, and nothing in Task 3.2 sets up a shared helper"
    location: "src/amoeba/store/nodes.py:114-134"
  - id: F002
    severity: concern
    category: scope
    summary: "Task 2.1 adds `idx_messages_submission`, which the slice design does not call for and its own success criterion forbids"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md:85"
  - id: F003
    severity: concern
    category: process
    summary: "Docs tasks 9.1 and 9.2 have no commit step"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md:378-391"
  - id: F004
    severity: note
    category: test-with-pattern
    summary: "Test coverage lags implementation in sections 3 and 7"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md:133-176"
  - id: F005
    severity: note
    category: proportionality
    summary: "Proportionality is mostly reasonable, with a few spots that dictate more than the slice needs"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md:63-69"
  - id: F006
    severity: pass
    category: coverage
    summary: "Success-criteria coverage"
    location: "project-documents/user/slices/121-slice.store-contract-changes-for-the-runner.md:327-348"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Sequencing and checkpoints"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md:57"
---

# Review: tasks — slice 121

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 7.3 `StatusEffect` cannot reuse `update_node_status` inside its transaction, and nothing in Task 3.2 sets up a shared helper

- **Problem:** `update_node_status` opens its own `with self._connection:` block at `nodes.py:129`. A `StatusEffect` runs inside `record_routing_decision`'s outer `with self._connection:` block (7.3). Calling the public method would commit mid-write and break the atomicity that D5 and the success criteria require.
- **Why the obvious workaround fails:** Task 3.4's writer-inventory test allows `UPDATE_NODE_STATUS` only in `store/_block_writer.py`, `store/nodes.py` and `store/sql.py`. `UPDATE_NODE_STATUS` is referenced only from those modules today (`_block_writer.py:73,107`, `nodes.py:131`, `sql.py:179`). If `routing_decisions.py` executed it directly, the test would fail.
- **Gap in the plan:** Task 7.3 says "Share the check with Task 3.2 rather than copying it". Task 3.2 only adds `_refuse_done` and the unresolved-entry refusal inline. It never asks for a reusable, non-committing helper.
- **Fix:** In Task 3.2, factor a non-committing status-write helper in `nodes.py`. It should hold the done, blocked-status and unresolved-entry checks plus the `UPDATE_NODE_STATUS` execute. `update_node_status` should wrap it in its own transaction. In Task 7.3, call that helper instead of the public method.

### [CONCERN] Task 2.1 adds `idx_messages_submission`, which the slice design does not call for and its own success criterion forbids

- **Contradiction:** Task 2.1 adds a partial index on `messages (submission_id)` and labels it "an addition to the LLD's sketch". The same task's success criterion says the migration contains "no statement the LLD does not call for".
- **What I checked:** `004_inbox_and_messages.sql:39` defines `submission_id` as a plain column with no index, so the lookup would be a scan. D2 and the "Tick cost" section never claim `intent_for_submission` is on a bounded per-tick path. It is a submitter-side read.
- **Fix:** Either drop the index, or amend the slice design (D2 and the schema sketch) to include it and reword the criterion. As written, the task file and the design disagree.
- **Related detail:** The literal-`WHERE` instruction in Task 4.2 and the new index-name constant in `sql_runner.py` come along with the index. If you keep the index, those stay. If you drop it, they go too.

### [CONCERN] Docs tasks 9.1 and 9.2 have no commit step

- Every other section ends with a named commit (`feat: ...`). Tasks 9.1 and 9.2 list no commit. Task 9.3 only says "Work is committed".
- The file's cadence note defaults to one commit per task, but that default is not repeated here. The risk is that two documentation edits and the public-API check get swept into an unnamed final commit.
- **Fix:** Add `docs: document the Runner store contract` to 9.1 and 9.2, or one combined commit at the end of 9.2.

### [NOTE] Test coverage lags implementation in sections 3 and 7

- Tasks 3.1 to 3.3 have no tests until 3.4. Tasks 7.1 to 7.3 have none until 7.4. The tasks in each group commit together, so no untested behaviour is committed.
- 7.3 is the largest implementation task (Effort 4) and is verified only by 7.4. This is acceptable, but if 7.3 runs long, splitting off its rollback ordering would keep it manageable.

### [NOTE] Proportionality is mostly reasonable, with a few spots that dictate more than the slice needs

- **Task 1.1:** It asks for a caller inventory across `src/`, `tests/`, `scripts/` and `docs/`, pre-populated with an expected list. That is reasonable for a signature change, but the "expected from the LLD" list restates content the slice design does not contain. Treat it as a hint, not a checklist.
- **Section 2.3:** The migration fixture is a node, an acknowledged intent, an unacknowledged intent and a node escalation. The design's technical requirement says "holds data from every earlier migration". The fixture likely covers this, but the task never states it, so a junior could read it as narrower.
- **Section 7.4:** It has nine bullets plus a four-step rollback matrix. This matches the design's rollback criterion and is not excess.
- **Sections 4.3 and 8.1:** They rely on greps to find tests to update, which is appropriate.

### [PASS] Success-criteria coverage

- **Terminal done and journal_issue:** The done-terminal, `journal_issue`, unresolved-entry and writer-inventory criteria map to 3.1 to 3.4.
- **Acknowledgment and read-only handle:** The outcome criteria and the read-only `intent_for_submission` criterion map to 4.1 to 4.3.
- **Desired state:** The atomic write, forced-failure rollback, clear, and non-applied rejection map to 5.1 to 5.3.
- **Project escalation:** Dedup, reraise after close, and the direct-SQL index refusal map to 2.3 and 6.2.
- **Routing decisions:** The one-transaction write, rollback at each step, the duplicate entry, and same-version-different-content cases map to 7.3 and 7.4.
- **Migration:** Migration on v8, read-only open raising `StoreSchemaError`, and the version pin update map to 2.3.
- **Contract suite and inspection:** The contract suite stand-in and oracle map to 4.3. The inspection columns map to 8.1 and 8.2, including the network listing.
- **Docs and walkthrough:** The contract documents map to 9.1 and 9.2. The verification walkthrough maps to 9.3.
- **Load tests:** The slice states no NFR, so a load test and CI gating task are not needed.

### [PASS] Sequencing and checkpoints

- Dependencies run strictly forward from 1.1 to 9.3 with no cycles.
- The signature-breaking change in 4.1 is paired with its caller updates in 4.3 and committed together, so no commit leaves the suite red.
- Six implementation commits land before the docs section. Each section ends on a green full-suite gate.
- Merge is correctly excluded, per the Git Rules.

### Run Digest

- Response length: 7135 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 203261 / 98819 / 104436 / 6602 / not computed
- Duration: 51.3 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
