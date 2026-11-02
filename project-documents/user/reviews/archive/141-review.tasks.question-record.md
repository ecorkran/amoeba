---
docType: review
layer: project
reviewType: tasks
slice: question-record
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/141-tasks.question-record.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: ec3df72be0553c2fd340f61d296bf6c5b57c57cd
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 106127
cachedTokens: 11118
cacheWriteTokens: 95005
completionTokens: 3750
durationSeconds: 32.6
costUsd: 0.419478
costBasis: provider
runId: run-20261102-p5-6140d2da
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "End-to-end `pending` assertion from 5.4 breaks once the stage lands in 7.3"
    location: "project-documents/user/tasks/141-tasks.question-record.md:170"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Task 2.3 is too granular and has no testable outcome"
    location: "project-documents/user/tasks/141-tasks.question-record.md:82-84"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Migration 013 is committed in Section 2 and edited again in Section 8"
    location: "project-documents/user/tasks/141-tasks.question-record.md:79"
  - id: F004
    severity: note
    category: test-guidance
    summary: "Task 7.4's invariant case gives no way to set up the state"
    location: "project-documents/user/tasks/141-tasks.question-record.md:215"
  - id: F005
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable but on the heavy side"
    location: "project-documents/user/tasks/141-tasks.question-record.md"
  - id: F006
    severity: pass
    category: coverage
    summary: "Success-criteria coverage and scope"
    location: "project-documents/user/slices/141-slice.question-record.md:335-361"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Dependency order and commit distribution"
    location: "project-documents/user/tasks/141-tasks.question-record.md:98-276"
---

# Review: tasks — slice 141

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] End-to-end `pending` assertion from 5.4 breaks once the stage lands in 7.3

Task 5.4 asserts one `pending` record after the question tick. Task 7.3 then declines that record in the same tick, so the assertion becomes false. Task 7.4 only says to insert a `declined (answerer_not_configured)` assertion "before the resume". It never says to remove or replace the `pending` assertion. The file states that each task leaves the full suite passing. Task 7.3 breaks that, and the 7.3/7.4 split has no commit between them. Task 7.4 should say outright to replace the `pending` post-tick assertion with `declined`. Task 5.4 could also assert `pending` only on the ingest-level test, where no stage runs. The same check applies to any other 5.4 ingest or crash assertion that reads record state after a full tick.

### [CONCERN] Task 2.3 is too granular and has no testable outcome

Task 2.3 creates `sql_questions.py` and `mapping_questions.py` with no behaviour of their own. Its success criterion is only "the modules import". It also says "add statements as the operations in Tasks 2.4, 3.1 and 4.1 need them", so the task stays open across three later tasks. It should be merged into 2.4, which first uses it. The `sql_*`/`mapping_*` rule (no SQL outside `sql_questions.py`) can stay as a constraint on 2.4, 3.1 and 4.1.

### [CONCERN] Migration 013 is committed in Section 2 and edited again in Section 8

Task 2.2 creates `013_question_records.sql` and Task 8.1 later edits the same file to add the triggers. The commit at the end of Section 2 therefore holds a migration that Section 8 changes. This is acceptable only because the migration is unreleased on the slice branch. Add one line to Task 8.1 saying that editing the unreleased `013` is intended and that `test_migration_013.py` must still pass after the edit. Otherwise a junior implementer may add a `014` migration instead.

### [NOTE] Task 7.4's invariant case gives no way to set up the state

The invariant case needs a resolved block that does not await the Runner. No store operation can produce that state, because D2 makes it unreachable. The task should name how the test builds it, for example by writing the row directly through the test helper. Without that, the implementer may add production code just to reach the state.

### [NOTE] Proportionality is acceptable but on the heavy side

The file has 11 sections and about 25 tasks for a slice rated effort 3. It is still one task file, which is correct. Every test and doc task traces to a named success criterion or Verification Walkthrough step. Task 11.1's scratch-store walkthrough (steps 5–7) repeats behaviour that the tests in 5.4, 7.4, 8.2 and 9.3 already cover. It could be trimmed to the config-load failure and the `amoeba feed` output, but it matches the design's walkthrough, so it is optional.

### [PASS] Success-criteria coverage and scope

The tasks cover every functional and technical requirement:
- **Block and record written together:** tasks 3.1, 3.2 and 5.3.
- **Already-blocked node, and null question:** tasks 3.2 and 7.4.
- **Declined `answerer_not_configured` and `no_answer_on_file`, and the config load error:** tasks 6.2 and 7.4.
- **PM resolution submitted before the stage runs (skip):** task 7.4.
- **Acknowledgment shapes (applied resume, stop, rejection, `StatusEffect`, already-answered, answerer-name case):** task 4.2.
- **Transition walk:** task 4.2.
- **Crash safety:** task 5.4.
- **Feed kinds and the re-point emitting nothing:** task 8.2.
- **Listings and the server route:** tasks 9.1 to 9.3.
- **Migration test and read-only open of a version-12 store:** task 2.5.
- **Purity check:** tasks 7.1 and 7.2.
- **Contract docs, including `QUESTION_TAIL_CHARS`:** task 10.1.

I found no scope creep. The slice states no NFR, so no load test or CI-gating task is needed.

### [PASS] Dependency order and commit distribution

The dependency order holds: models and migration, then `record_question`, then the acknowledgment rule, then ingest, config, stage, feed, listings and docs. Each implementation task is followed by its tests in the same section. There are eight commit markers, one per section from 2 to 10. None are batched at the end, and none merge or push, which matches the project's rules.

### Run Digest

- Response length: 5200 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 106127 / 11118 / 95005 / 3750 / not computed
- Duration: 32.6 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
