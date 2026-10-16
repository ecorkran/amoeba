---
docType: review
layer: project
reviewType: tasks
slice: judge-samples-checks-and-calibration
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 4eecc95c13ed5ab6e94a4a307b099fe79c831026
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 97655
cachedTokens: 10984
cacheWriteTokens: 86667
completionTokens: 3984
durationSeconds: 33.8
costUsd: 0.388286
costBasis: provider
runId: run-20261016-p56-6f6dfbbb
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: task-clarity
    summary: "Calibration field-name instructions contradict each other"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:28-29,55"
  - id: F002
    severity: concern
    category: commit-checkpoints
    summary: "Task 7.1 commit is deferred past Task 7.2's commit"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:163,182"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 6.2 is overweight"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:87-105"
  - id: F004
    severity: note
    category: sequencing
    summary: "Migration 007 is edited again in Task 6.3"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:117"
  - id: F005
    severity: note
    category: coverage
    summary: "Issue #2 closure is deferred to the PM"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:327"
  - id: F006
    severity: note
    category: code-structure
    summary: "`inbox.py` is already over the line budget"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:94"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for Sections 5–8"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Calibration field-name instructions contradict each other

Task 5.1 says the row's fields are "exactly as the D3 table", then says `pass` can't be a Python name and tells the implementer to pick something like `pass_count`. Task 5.2 asserts "its field names equal the D3 list exactly". D3 lists `pass`, so the test either fails against a `pass_count` field or forces a mapping the tasks never describe. Task 7.5 and the JSON output also depend on the chosen names.
- Fix: in 5.1, fix the exact Python field names and the CLI/JSON column names, including how `pass` maps.
- Fix: in 5.2, assert against those names, and keep the "no cross-sample comparison field" check as an explicit expected list.

### [CONCERN] Task 7.1 commit is deferred past Task 7.2's commit

Task 7.1 is "Committed with Task 7.3", but Task 7.2 sits between them and has its own commit step. Task 7.2 does not depend on 7.1's code, so the 7.1 changes either get swept into 7.2's `test:` commit or stay uncommitted across a task. Either way it breaks the "at least once per task" rule.
- Fix: swap the order so 7.2 (fixture) comes before 7.1 and 7.1 is followed directly by 7.3, or state that 7.2's commit stages only its own files.

### [CONCERN] Task 6.2 is overweight

Task 6.2 combines the effect implementation, a writer-dependency refactor, extending two existing enumeration tests, a payload-key pin test, six inbox behavior tests, and a CLI submit test. Its effort rating is 4, the same as the simpler 5.1.
- Fix: split it into 6.2a (effect, registration, enumeration and key-pin tests) and 6.2b (inbox behavior and `amoeba submit check` tests). Keep the single commit at the end of 6.2b.
- Fix: also say how 6.2's own tests run, since the full suite is expected to fail between 6.1 and 6.2.

### [NOTE] Migration 007 is edited again in Task 6.3

Task 6.3 adds a trigger to migration 007, which file 1's tasks already created and tested for the 6→7 upgrade. This is acceptable because the branch is unmerged. Task 6.3's success criterion only says the migration "applies cleanly on a fresh store", but file 1's upgrade test should also pass again after the edit. Say so explicitly.

### [NOTE] Issue #2 closure is deferred to the PM

The slice's Technical Requirements list "GitHub issue #2 is closed with a pointer to D4". Task 8.3 defers the closure to a Phase 7 PM action after the merge. That is reasonable because closing an issue is outward-facing, but it departs from the slice text. Task 8.3's listing for the PM should note that departure.

### [NOTE] `inbox.py` is already over the line budget

Task 6.2 acknowledges `inbox.py` is at 308 lines and keeps the new effect small. Task 8.3's line-count check will flag the file regardless. Record that this is a pre-existing overage so validation doesn't treat it as new.

### [PASS] Success-criteria coverage for Sections 5–8

All of these map to a task:
- **Calibration:** counts, ordering and unknown handling, the read-only and no-metrology constraints, and the descriptive-only row (5.1–5.2).
- **`check` kind:** the three-part seam, rejections, and the CLI flags (6.1–6.2).
- **Feed change:** one `check_recorded` per check, none per retry or progress record, and the invariant test extension (6.3–6.4). The "two new kinds" versus D9 discrepancy is called out.
- **Ingest:** `--judge-invocation-id`, the sample-id rule, and the real judge fixture (7.1–7.3).
- **Listings:** the `verdicts` column and filter, and `checks`/`calibration` with the pinned-registry update (7.4–7.6).
- **End-to-end, docs, walkthrough:** the kill -9 flow and feed counts, the contract docs and CHANGELOG, and the walkthrough (8.1–8.3).

I found no scope creep. The only extras are small, reasonable additions: the `ChangeKind` enumeration test updates and the README entry check.

### Run Digest

- Response length: 5130 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 97655 / 10984 / 86667 / 3984 / not computed
- Duration: 33.8 s
- Cost: $0.39 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
