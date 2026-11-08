---
docType: review
layer: project
reviewType: tasks
slice: the-cut
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/221-tasks.the-cut.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 69fae68c81a3a76fe80bf37b83375474127337e8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 107817
cachedTokens: 11198
cacheWriteTokens: 96615
completionTokens: 5296
durationSeconds: 43.6
costUsd: 0.44139
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage"
    location: "project-documents/user/tasks/221-tasks.the-cut.md"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Section 2 commit lands at a non-working, unchecked point"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:171"
  - id: F003
    severity: concern
    category: consistency
    summary: "Dangling and contradictory references in section 2/3 intros"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:110"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Later tasks must make checks pass but fail the 3.6 gate first"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:199"
  - id: F005
    severity: concern
    category: task-sizing
    summary: "Task 2.8 is too large and unbounded"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:154"
  - id: F006
    severity: concern
    category: sequencing
    summary: "2.9 should run before 2.8, and the rework units' moves are unspecified"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:161"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Over-granular tasks should be merged"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:66-85"
  - id: F008
    severity: concern
    category: commit-markers
    summary: "Task 7.1 has no deliverable and falls after the last commit marker"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:269"
  - id: F009
    severity: note
    category: proportionality
    summary: "Task 1.9 edits code that section 3 deletes"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:101"
  - id: F010
    severity: note
    category: prompt-hygiene
    summary: "\"Expected\" example lists sit next to audit-sourced values"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:113"
---

# Review: tasks — slice 221

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage

All ten success criteria in the slice design trace to tasks:
- Deletions: 1.x and 3.x.
- D3 locations: 2.1 to 2.7.
- Checks: 1.9, 3.6 and 6.3.
- Library tests without a store: 3.6.
- Live tier: 5.x and 6.3.
- Import boundary: 6.1.
- Wheel and packaging: 4.x.
- Audit-row changes: 2.9 and 6.3.
- README: 6.2.
- `amoeba#32` pointer: 7.1.

The slice has no NFR, so no load test or CI gating task is needed.

### [CONCERN] Section 2 commit lands at a non-working, unchecked point

- The slice design says each step ends with format, lint, pyright and the default suite passing. Section 2 has no checks task.
- Section 3 says checks run once at the end (3.6). After 2.1 to 2.10, old `runner/`, `process/` and `store/` code still imports modules that were `git mv`'d, so the tree is broken at that marker.
- Fix: drop the `**Commit**:` after section 2 and commit once after 3.6 (merging the two groups), or add a checks gate that can actually pass before the marker.

### [CONCERN] Dangling and contradictory references in section 2/3 intros

- The section 2 intro says old paths stay "recoverable until verification (task 2.12)". No 2.12 exists (the section ends at 2.10), and 2.1 uses `git mv`, which removes the old paths.
- The section 3 intro says checks run "at the end (task 3.5)". The checks are task 3.6.
- Fix: correct both references and drop the "old paths still present" claim.

### [CONCERN] Later tasks must make checks pass but fail the 3.6 gate first

- 3.6 requires all four checks to pass. Several items that can break them are scheduled afterwards:
  - `tests/live/answering` still imports deleted code until 5.1 and 5.2. If pyright or ruff covers that directory, 3.6 cannot pass. I did not verify the pyright scope.
  - `test_wheel_contents.py` still checks the old schema globs until 4.2, after 3.3 deletes the `.sql` files.
- Fix: pull 5.1, 5.2 and 4.2 ahead of 3.6, or state that 3.6's checks exclude them.

### [CONCERN] Task 2.8 is too large and unbounded

- 2.8 says "work every Dependencies of kept code entry". It carries no list of entries, spans every kept module, and bundles the sever, the signature-driven test rewrites and a hunt for non-import coupling.
- A junior AI cannot tell when it is done, and a failure leaves no checkpoint.
- Fix: split it into one subtask per audit entry or per kept module. Keep a final subtask for the non-import coupling sweep.

### [CONCERN] 2.9 should run before 2.8, and the rework units' moves are unspecified

- 2.8 severs all `rework` units, including the ones 2.9 then deletes (`launch`, `stage`, `settle`, `finish`'s store-writing half). That is wasted effort.
- 2.1 moves only the "kept" modules and its expected list omits launch, stage, settle and finish. Yet 2.9 deletes `answering/launch.py` at the new path, and `finish.py` needs a split that no task describes.
- Fix: delete first (reorder 2.9 before 2.8), and state where each rework unit lives before the delete.

### [CONCERN] Over-granular tasks should be merged

- 1.1, 1.2, 1.3 and 1.5 are each a single `git rm -r` with the same success shape. Merge them into one "delete leaf packages" task and keep 1.4 and 1.6 separate because they edit `pyproject.toml`.
- 2.5, 2.6 and 2.7 (moves into `upstream/`) are similar. Merge them.
- 0.1 to 0.3 could shrink to two tasks.

### [CONCERN] Task 7.1 has no deliverable and falls after the last commit marker

- 7.1 only adds a note line under itself. No commit marker follows it, and repo rules forbid a commit that only adds notes.
- The `amoeba#32` criterion is met at merge in Phase 7, not by this task.
- Fix: delete section 7 and put the pointer line in 6.3 before the final commit.

### [NOTE] Task 1.9 edits code that section 3 deletes

Removing imports from old code that section 3 deletes anyway is extra work. It matches the design's step 1 ("old code only loses those imports"), so it is acceptable. It could be dropped if the leaf and rest deletions are one commit.

### [NOTE] "Expected" example lists sit next to audit-sourced values

- The "expected: …" lists in 1.8, 2.1 and 5.2 name modules and files the audit supplies. They are low risk because 0.2 blocks on an incomplete audit.
- Consider adding "if the audit disagrees, the audit wins" to each of these lists. 0.2 already states that rule, but only in one place.

### Run Digest

- Response length: 5438 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 107817 / 11198 / 96615 / 5296 / not computed
- Duration: 43.6 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
