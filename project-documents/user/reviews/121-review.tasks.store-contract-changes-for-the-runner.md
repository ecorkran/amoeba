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
reviewedSha: 8a13ec54ca3f6d756cada9886c8124414d0e4616
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 203552
cachedTokens: 101796
cacheWriteTokens: 101750
completionTokens: 5976
durationSeconds: 47.4
costUsd: 0.477756
costBasis: provider
runId: run-20261023-p56-87870251
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Section 7 is over-split and over-tested for the size of the slice"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md:284-339"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Tasks 4.1–4.2 leave the tree failing until 4.3"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md:175-204"
  - id: F004
    severity: concern
    category: test-with
    summary: "Test-with gap: 5.1 and 5.2 are untested until 5.3"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md:210-246"
  - id: F005
    severity: concern
    category: missing-verification
    summary: "New operation modules may trip the writer-guard and store-safety tests, and no task checks"
    location: "tests/test_writer_guard.py"
  - id: F006
    severity: concern
    category: accuracy
    summary: "Unverifiable issue reference and fabricated rationale in Task 4.2"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md:190"
  - id: F007
    severity: note
    category: scope
    summary: "Small additions beyond the slice text"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md:258"
  - id: F008
    severity: note
    category: code-structure
    summary: "Module-size risk for `sql_runner.py` and the new test files"
    location: "project-documents/user/tasks/121-tasks.store-contract-changes-for-the-runner.md:98"
---

# Review: tasks — slice 121

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria trace to tasks

- **Terminal done.** Covered by 3.1–3.4 and 7.4: the `block()`, `update_node_status` and `StatusEffect` refusals, the `journal_issue` refusal, the unresolved-entry refusal, and the writer-inventory test.
- **Acknowledgment.** Covered by 4.1–4.3 and 5.1–5.3: outcomes, `intent_for_submission` through a read-only handle, atomic desired state with rollback, and the stand-in Runner and oracle updates.
- **Project-scoped escalation.** Covered by 6.1–6.2: dedup, close and reopen, the feed `message_posted` change, and direct-SQL index refusal in 2.3.
- **Routing decisions.** Covered by 7.1–7.4: the four-step rollback, duplicate-entry refusal, and same-version/different-content refusal.
- **Migration, inspection, docs and public API pin.** Covered by 2.x, 8.x and 9.x.
- **Scope creep.** I found none worth flagging.

### [CONCERN] Section 7 is over-split and over-tested for the size of the slice

- **Four tasks and three test modules.** Tasks 7.1–7.4 produce `test_routing_reads.py`, `test_routing_validation.py` and `test_routing_decisions.py`.
- **7.2 is a private function with no public caller.** It ships a standalone validator with its own test module. Task 7.4 then re-asserts "Each Task 7.2 validation failure writes nothing" through the public method, so the validation is tested twice.
- **7.1's tests are indirect.** They insert rows through raw `sql_runner.py` statements to exercise the reads. 7.4 already exercises every read through the real write path.
- **What to cut:**
  - Merge 7.2 into 7.3 and drop `test_routing_validation.py`. Keep the validation assertions in 7.4.
  - Fold the 7.1 read tests into 7.4. Keep one fresh-store and read-only-handle test for the empty and `0` cases.
  - The split-file contingencies ("if it nears 300 lines") can become a single note in 9.3.

### [CONCERN] Tasks 4.1–4.2 leave the tree failing until 4.3

- **Why the tree breaks.** Task 4.1 makes `outcome` required. That breaks every existing `acknowledge_message` caller: `tests/store/test_messages.py`, `tests/contract/runner_tenant.py` and the oracle. They are fixed only in 4.3.
- **What is missing from 4.1 and 4.2.** Neither task has a test or its own success check beyond a prose assertion, and the three tasks share one commit. That is acceptable for the commit rule, but it breaks the test-with pattern.
- **Suggested fix.** Move the caller updates (`test_messages.py` and the stand-in Runner) into 4.1, and fold 4.2 into 4.1 or 4.3. The commit then lands with a green suite after the first task, and 4.2 isn't a separate task for a single method.

### [CONCERN] Test-with gap: 5.1 and 5.2 are untested until 5.3

- **The gap.** Tasks 5.1 and 5.2 ship the reads, the shape checks and the atomic write with no tests. All of them arrive in 5.3.
- **Why it matters.** The grouped commit makes this survivable, but a junior AI working 5.1 has no verification beyond "reads return None".
- **Suggested fix.** Move the read-path and shape-rule tests into 5.1, and keep the rollback and atomicity tests in 5.2/5.3.

### [CONCERN] New operation modules may trip the writer-guard and store-safety tests, and no task checks

- **The criterion.** The slice requires "the writer guard and store-safety tests pass unchanged".
- **What the tasks do.** No task explicitly runs `tests/test_writer_guard.py` or `tests/test_store_safety*` when `desired_states.py`, `project_escalations.py` and `routing_decisions.py` are added. 3.4 and 9.3 run the full suite, but only 9.3 would catch a drift.
- **Suggested fix.** Add `tests/test_writer_guard.py` to the 5.3, 6.2 and 7.4 test runs, so a violation is caught in the task that causes it.

### [CONCERN] Unverifiable issue reference and fabricated rationale in Task 4.2

- **The claim.** Task 4.2 says "Issue #19 tracks adding the index" for `messages.submission_id`.
- **Why it can't be checked.** The slice design never mentions this issue or index. It cites only #10, for the unrouted-outcomes query.
- **Why it matters.** If #19 does not exist, a junior AI may cite a phantom tracking item or go looking for it.
- **Suggested fix.** Confirm #19 with the Project Manager, or reword to say the scan is accepted and no index is added in this slice.

### [NOTE] Small additions beyond the slice text

- **`closed_by`.** Task 6.1 requires a non-empty `closed_by` (`ValueError`). The slice's D4 says nothing about this.
- **`BlockEffect`.** Task 7.3 adds a refusal for `BlockEffect` on an already-blocked node. D5 does not list it.
- **Verdict.** Both are reasonable and consistent with the store's no-silent-defaults rule, so I don't count them as scope creep. The slice's failure-modes table in `docs/store-contract.md` (9.1) should list them, so the documented contract matches behaviour.

### [NOTE] Module-size risk for `sql_runner.py` and the new test files

- **`sql_runner.py`.** It accumulates statements for four tables plus the message columns across Tasks 2.2, 5.1, 6.1 and 7.1. It could pass 300 lines.
- **`test_terminal_done.py`.** It collects tests from four tasks (3.1–3.4).
- **Existing handling.** Task 9.3 catches size problems, but only at the end, with a 330-line threshold that is looser than the project's ~300.
- **Suggested fix.** Add a "split by table" note in 2.2 and use the same ~300 figure in 9.3.

### Run Digest

- Response length: 6513 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 203552 / 101796 / 101750 / 5976 / not computed
- Duration: 47.4 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
