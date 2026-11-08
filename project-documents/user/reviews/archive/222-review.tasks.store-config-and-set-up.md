---
docType: review
layer: project
reviewType: tasks
slice: store-config-and-set-up
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/222-tasks.store-config-and-set-up.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: b6e04f75224192d4e029002938b68172fc5454f6
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 113474
cachedTokens: 11198
cacheWriteTokens: 102272
completionTokens: 5499
durationSeconds: 44.0
costUsd: 0.466047
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: concern
    category: coverage-gap
    summary: "Omitted-`project` resolution from two worktrees is never tested through `set_up`"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md:216-219"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Task 8.4 is too large for one junior-completable task"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md:210-214"
  - id: F003
    severity: concern
    category: ambiguity
    summary: "\"Before the store opens\" in 8.2 contradicts the `set_up` signature and CLI order"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md:203"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Fake `cf` helper has no failure mode, but task 10.3 needs one"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md:69-71"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Concurrent-open test 3.7 duplicates 8.6"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md:126-128"
  - id: F006
    severity: note
    category: ambiguity
    summary: "`migrate()` reads `schema_meta` before it exists on a new store"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md:106-109"
  - id: F007
    severity: note
    category: scope
    summary: "Changelog task 11.4 traces to no success criterion"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md:280-282"
  - id: F008
    severity: pass
    category: coverage
    summary: "Remaining success criteria and sequencing check out"
    location: "project-documents/user/tasks/222-tasks.store-config-and-set-up.md"
---

# Review: tasks — slice 222

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Omitted-`project` resolution from two worktrees is never tested through `set_up`

The success criterion says an omitted `project` from two worktrees of one repo resolves to the same member. Task 7.2 tests `resolve_member` with both worktree fixtures. But `set_up` resolves an omitted `project` through `project_of` (8.2), not `resolve_member`. Task 8.3 exercises omitted `project` only with a bad working directory. Task 8.5 checks `working_directory` only for `not_in_program` and `not_a_project`. Nothing shows a `set_up` member entry with omitted `project` giving the same member id from the default and non-default worktree fixtures. Add that case to 8.5.

### [CONCERN] Task 8.4 is too large for one junior-completable task

Task 8.4 bundles four things:
- seven remaining check codes computed against hypothetical post-request state;
- rollback and `rejected` handling;
- upserts with whole-list replacement and per-row change lines;
- `program` read-back and `working_directory` assembly.

Its only success criterion is "pyright strict clean", which proves nothing about behavior. Split it into "checks" (collect `SetUpProblem`s) and "write and result" (upserts, `changes`, `program`, `working_directory`). Give each a behavioral success line, and move the 8.5 tests so they follow their halves.

### [CONCERN] "Before the store opens" in 8.2 contradicts the `set_up` signature and CLI order

Task 8.2 says to resolve all references "before the store opens". But `set_up(store, config, ...)` receives an already-open `Store`, and 10.1 opens the store before calling `set_up`. A junior could try to move the open inside `set_up`, or could treat the instruction as already violated. The intent is that no `cf` subprocess runs inside a `Store.write()` transaction. Reword it to "before `Store.write()` begins". The 8.2 success check ("store has no rows") stays valid.

### [CONCERN] Fake `cf` helper has no failure mode, but task 10.3 needs one

Task 1.3 describes a `PATH` script that replays fixtures. Task 10.3 requires a subprocess test where "a failing `cf` exits 3 with the store unchanged". It also needs a fake `cf` that answers for a registered member's directory. The 1.3 script writer never mentions emitting a nonzero exit or garbage output. Task 1.3's `CfRun` helper does cover "a given failure", but the script writer does not. Add failure replay to the script writer in 1.3, or the implementer of 10.3 will have to reopen a task already committed.

### [CONCERN] Concurrent-open test 3.7 duplicates 8.6

The success criteria list only the 8-process `set_up` test, the held-transaction busy test and the stamped-higher test. Task 8.6 already has 8 processes opening one new store at once, which exercises the same migration serialization. Task 3.7 adds a second 8-process test, also run five times. Either drop 3.7, or keep it and cut 8.6 down to the criterion (applied-or-busy, and the store ends with every applied member). The second option is only worthwhile if the migration-lock check is wanted at its own level.

### [NOTE] `migrate()` reads `schema_meta` before it exists on a new store

Task 3.2 creates `schema_meta` inside `001_baseline.sql`, but 3.3 has `migrate` "read `schema_meta`" first. On an empty database that table does not exist. The task should say how absence is detected, for example by checking `sqlite_master` and treating a missing table as version 0. Otherwise the implementer decides this alone. The slice design has the same gap.

### [NOTE] Changelog task 11.4 traces to no success criterion

The slice design does not require a `CHANGELOG.md` entry. This is a small, conventional addition and not harmful. It is the only task with no matching criterion, so keep it only if the project convention calls for it.

### [PASS] Remaining success criteria and sequencing check out

Every other criterion maps to a task:
- `applied`, `unchanged` and read-back: 8.5.
- Each D7 code: 8.3 and 8.5.
- Exit codes 2 and 3: 10.3.
- `answering_for`: 9.2.
- Missing config and each missing key: 4.3 and 10.3.
- Busy timeout, stamped-higher and 8-process `set_up`: 3.5 and 8.6.
- D10: 2.2 and 2.3.
- Vocabulary pinning: 3.6.
- D11 fixtures: 1.2 and 5.2.
- Import boundaries: 10.4.
- Wheel contents: 10.2.
- Contract docs: 11.1 and 11.2.

Dependencies run one way. Fixtures and the `AMOEBA_HOME` fixture come first, then home, store, config, `project_of`, store reads and upserts, member resolution, `set_up`, answering and the CLI. No cycles. The slice states no NFR, so no load-test or CI-gating task is required.

### Run Digest

- Response length: 5817 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 113474 / 11198 / 102272 / 5499 / not computed
- Duration: 44.0 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
