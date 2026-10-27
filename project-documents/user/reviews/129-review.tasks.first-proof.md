---
docType: review
layer: project
reviewType: tasks
slice: first-proof
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/129-tasks.first-proof.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261027
dateUpdated: 20261027
reviewedSha: 67b6e8886094cae6791e1ae000b49bad2f41c0ef
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 104023
cachedTokens: 11176
cacheWriteTokens: 92843
completionTokens: 4982
durationSeconds: 43.8
costUsd: 0.423123
costBasis: provider
runId: run-20261027-p5-85a72bbf
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage"
    location: "project-documents/user/tasks/129-tasks.first-proof.md"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 3.4 is nested inside Task 3.3, so the order is ambiguous"
    location: "project-documents/user/tasks/129-tasks.first-proof.md:177-198"
  - id: F003
    severity: concern
    category: commit-checkpoints
    summary: "No commit between Task 3.1 and Task 3.6 during the longest, riskiest stretch"
    location: "project-documents/user/tasks/129-tasks.first-proof.md:161-216"
  - id: F004
    severity: concern
    category: gap
    summary: "The `--node` spelling is promised for Task 2.5 but missing from its steps"
    location: "project-documents/user/tasks/129-tasks.first-proof.md:62"
  - id: F005
    severity: concern
    category: proportionality
    summary: "The test lists in 2.2 and 2.4 go beyond what the success criteria need"
    location: "project-documents/user/tasks/129-tasks.first-proof.md:105-143"
  - id: F006
    severity: note
    category: sequencing
    summary: "Task 6.1 dependency understates its inputs"
    location: "project-documents/user/tasks/129-tasks.first-proof.md:279-286"
  - id: F007
    severity: note
    category: coverage
    summary: "Issue #16 close-out is left to Phase 7"
    location: "project-documents/user/tasks/129-tasks.first-proof.md:315"
---

# Review: tasks — slice 129

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage

Each LLD criterion has a task:
- **Four steps `done` and merged:** Tasks 3.2, 3.3 and 3.5.
- **Nothing run by hand:** the Command log in 3.3 and the audit in 3.6.
- **`recomputes: yes`:** 3.6 before the edits and 5.3 after them.
- **SIGKILL with P6 in flight:** 3.4, which spells out D3's three pass conditions.
- **Every stop classified, one proposal per wrong stop:** 4.1.
- **`inspect resolutions`:** 2.1–2.5, with tests for the columns, the unacknowledged case, node filtering and the schema-mismatch exit in 2.4.
- **D7 rule test:** 5.1–5.3.
- **Validation commands:** 7.1.
- **Guides, plan entries, issues and CHANGELOG:** 6.1–6.6.

The test-with pattern holds: 2.1→2.2 and 2.3→2.4 each pair implementation with its tests and commit. Merging stays out of the checklist, as the project rules require.

### [CONCERN] Task 3.4 is nested inside Task 3.3, so the order is ambiguous

Task 3.3 "repeats until the `merge` step blocks". Task 3.4's dependency is "`P6`'s `sq_run` is confirmed (inside Task 3.3)". The crash must therefore happen partway through the 3.3 loop, and 3.4 cannot be done after 3.3 as the file order implies. An implementer reading in file order would finish 3.3 first, and by then P6 has long finished. That is the miss case 3.4 itself calls a failure.

Fix it by adding an explicit trigger to 3.3's loop, such as "when the journal shows `P6`'s `sq_run` confirmed, do Task 3.4 now, then resume the loop". Alternatively, split 3.3 into "answer stops through P5" and "answer stops from P6 on".

### [CONCERN] No commit between Task 3.1 and Task 3.6 during the longest, riskiest stretch

Tasks 3.1–3.5 produce the Command log, draft Stops rows, crash evidence and the D9 defect records. These accumulate in the write-up, but the only commit is at 3.6. P6 can run for hours and the loop can span days. The D4 log is the primary record, so losing it to an uncommitted working tree is a real risk.

Add a commit checkpoint at 3.4's end and after any D9 restart, for example `review: log first-proof run progress`. The write-up is a document, not state the Runner reads, so this costs little.

### [CONCERN] The `--node` spelling is promised for Task 2.5 but missing from its steps

The Task-level additions say "Task 2.5 records this spelling in the contract text". The LLD uses `--node-id`, including in its Success Criteria and API Contracts. The task file deliberately uses `--node` to match every other listing. Task 2.5's checklist (lines 148–151) has no item that records this. Without one, the departure from the LLD is never documented, and the next reader finds `--node-id` in the LLD and `--node` in the code.

Add an item to 2.5, and consider noting the correction in the LLD's API Contracts.

### [CONCERN] The test lists in 2.2 and 2.4 go beyond what the success criteria need

The LLD requires tests for each column, the unacknowledged case, node filtering and the schema-mismatch exit. These tasks add:
- `test_reads_through_a_read_only_handle` and `test_is_scoped_to_one_project` in 2.2.
- A separate "older accept on a re-blocked step" case in 2.4.
- A "`--json` and table form both work" case in 2.4.
- A separate `reason` case for each of three block kinds in 2.4.

Some of these are defensible, such as project scoping and the older-accept rule that the Task-level additions call out. Others are likely covered by the harness or the node filter test. Merge the read-only test into the store tests that already use the handle, and combine the `--json`/table case with the column tests. State which extras are intentionally kept.

### [NOTE] Task 6.1 dependency understates its inputs

Task 6.1 lists only 3.6, but its resolutions section "uses the stops the proof met as examples". Those come from the classified rows in 4.1/4.2, and 2.5 owns the `inspect resolutions` text it links. File order satisfies both, and the stated rule is to work in file order. List 4.2 and 2.5 so the dependency is correct if tasks are reordered.

### [NOTE] Issue #16 close-out is left to Phase 7

The LLD says "#16 closes with this slice". Task 6.5 comments on #16 and leaves it open until the merge, which fits the rule against merge tasks. Task 2.4's commit message cites `(#16)` but not `Fixes #16`. Confirm that Phase 7 closes it, or use `Fixes #16` on a commit.

### Run Digest

- Response length: 5152 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 104023 / 11176 / 92843 / 4982 / not computed
- Duration: 43.8 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
