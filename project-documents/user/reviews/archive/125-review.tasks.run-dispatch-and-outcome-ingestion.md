---
docType: review
layer: project
reviewType: tasks
slice: run-dispatch-and-outcome-ingestion
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261024
dateUpdated: 20261024
reviewedSha: 0a1926145a0a0827496a09cc7c96e294b3f64529
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 369998
cachedTokens: 238704
cacheWriteTokens: 131286
completionTokens: 17415
durationSeconds: 82.2
costUsd: 0.176276
costBasis: provider
runId: run-20261024-p5-0a64b162
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are covered by tasks"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:1"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Sequencing is linear where the work is independent, so one blocker stalls unrelated work"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:107"
  - id: F003
    severity: concern
    category: design-consistency
    summary: "Detection key placement in the design contradicts the code and Rule 1"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md:322"
  - id: F004
    severity: note
    category: design-consistency
    summary: "Planner tuple location differs between the design and the task file"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md:148"
  - id: F005
    severity: concern
    category: granularity
    summary: "Several tasks are too thin to justify their own commit"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:267"
  - id: F006
    severity: note
    category: coverage
    summary: "A walkthrough test name has no task that creates it"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md:563"
  - id: F007
    severity: pass
    category: commit-cadence
    summary: "Test-with pattern and commit checkpoints are distributed"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:48"
---

# Review: tasks — slice 125

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Success criteria are covered by tasks

Each functional criterion in the slice design maps to at least one task. Two-tick dispatch and `merge=false` are in 7.3. Worktree routing is in 6.1 and 7.3. Pointer failures are in 6.3 and 7.1. Checkout concurrency is in 5.5 and 7.4. Unresolved checkouts are in 5.1 and 7.2. Ingestion, split and empty reviews, unknown reviews and non-completed outcomes are in 4.1 to 4.3. Left-for-routing and crash points are in 2.5, 2.7 and 4.5. Reissue is in 8.1, and pointer-move is in 9.1 and 9.2. Technical requirements (migration 011 with `EXPLAIN QUERY PLAN`, `TickBudget` coverage, the merge-key import test) and integration requirements (the contract suite, 122/123/124 tests with `DispatchPlanner` in production) are covered by 2.4, 2.5, 2.6, 5.3, 10.1 and 10.3.

### [CONCERN] Sequencing is linear where the work is independent, so one blocker stalls unrelated work

Task 2.3 can write `BLOCKED:` if the repo root is not a registered CF worktree. Every later task declares a dependency on it, directly or through the chain. That stops the migration, the store flag and the ingestion work, which do not need the observer change at all:
- 2.4 (migration 011) and 2.5 (flag and `unrouted_outcomes`) need only 2.2 at most. 2.1 is not needed.
- 2.6 to 2.8 need no CF read-back.
- Section 4 (ingestion) needs no dispatch code.
- Section 5 (pure dispatch core) is pure. 5.1 lists 4.5 as its dependency at line 297, a crash test for ingestion, which it does not need.
- 9.1 is pure and lists 7.4, though it needs only `parse_slice_stem` and the snapshot shape.

Dependencies should name what each task reads or calls. Sections 4 and 5 should not depend on each other. Each store change should depend only on the store changes it uses. A blocker at 2.3 should then leave the rest of the store and ingestion work free to proceed.

### [CONCERN] Detection key placement in the design contradicts the code and Rule 1

D7 says detection builds the key "inside its directory source", and D10 (line 365) says "Detection's directory source is changed to call it." The code shows otherwise. `DirectoryReviewSource` is in `store/review_sources.py:75`, and the store may not import `process` (Rule 1, `tests/test_import_boundaries.py`). The key is formed in `process/review_scan.py:91-92` (`str(detected.path)`, `content_digest`). Task 2.8 places the helper there, which is correct. The design should be corrected so the design and the tasks agree, and the design's "Technical Scope" and "Component Structure" are not left describing the infeasible path.

### [NOTE] Planner tuple location differs between the design and the task file

The component table says `tenant.py CHANGED production planners`. The code has `PRODUCTION_PLANNERS` in `src/amoeba/runner/factory.py:24`. The task file's "Task-level additions" records this correctly, and Task 10.1 edits `factory.py`. The design should be updated to match.

### [CONCERN] Several tasks are too thin to justify their own commit

The file has 35 tasks. Several carry one or two bullets and one commit each:
- **4.4** is one test, which can be a case in 4.3's test file. Its own bullet says "add a test to `test_record.py` or an e2e test", which is a sign it has no clear home.
- **2.7** is a one-line change (clearing the flag) plus two tests. It belongs with 2.5, which already owns the flag and the store query.
- **5.3** is a single function with an import test. It belongs with 5.2 or 5.4.
- **6.3** extends the same file and test module as 6.2 (`pointer.py`, `test_pointer.py`). It belongs with 6.2.

Merging these four would cut the file to about 31 tasks and keep each commit a unit of behavior.

### [NOTE] A walkthrough test name has no task that creates it

The walkthrough's step 1 names `test_split_review_records_every_part`. Task 4.3 describes the behavior ("split review records every part in one transaction") but does not give that name. Step 1 will not find the test unless 4.3 names it.

### [PASS] Test-with pattern and commit checkpoints are distributed

Each implementation task carries its own tests and one commit. Test-only tasks (4.4, 4.5, 7.4, 10.3) follow the implementation they exercise. Commits are spread across all ten sections, not batched at the end. The `Fixes #9` and `Fixes #10` commits fall on the tasks that deliver the behavior (8.1, 2.7). Live runs in 10.3 are pre-authorized, and no task waits on a Project Manager approval gate.

### Run Digest

- Response length: 6074 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 369998 / 238704 / 131286 / 17415 / not computed
- Duration: 82.2 s
- Cost: $0.18 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
