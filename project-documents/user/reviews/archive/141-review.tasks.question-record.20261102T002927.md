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
reviewedSha: 72b9bdf8008d08cf526e0e1bb2f608243312e9e3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 106090
cachedTokens: 8791
cacheWriteTokens: 97295
completionTokens: 3426
durationSeconds: 32.8
costUsd: 0.425165
costBasis: provider
runId: run-20261102-p5-6140d2da
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Transition-walk test in 2.5 cannot use writers that don't exist yet"
    location: "project-documents/user/tasks/141-tasks.question-record.md:94"
  - id: F002
    severity: concern
    category: testability
    summary: "\"Illegal transition inside the acknowledgment\" case in 4.3 looks unreachable"
    location: "project-documents/user/tasks/141-tasks.question-record.md:144"
  - id: F003
    severity: concern
    category: task-clarity
    summary: "Deferred end-to-end assertion is hedged though the ordering makes it certain"
    location: "project-documents/user/tasks/141-tasks.question-record.md:176"
  - id: F004
    severity: note
    category: granularity
    summary: "Tiny tasks that could merge into their neighbours"
    location: "project-documents/user/tasks/141-tasks.question-record.md:124"
  - id: F005
    severity: note
    category: proportionality
    summary: "Implementation detail beyond what the slice requires"
    location: "project-documents/user/tasks/141-tasks.question-record.md:81-84"
  - id: F006
    severity: pass
    category: coverage
    summary: "Success-criteria coverage"
    location: "project-documents/user/slices/141-slice.question-record.md:335-361"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Sequencing and commit distribution"
    location: "project-documents/user/tasks/141-tasks.question-record.md"
---

# Review: tasks — slice 141

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Transition-walk test in 2.5 cannot use writers that don't exist yet

Task 2.5 asks for a test that walks every (from, to) `QuestionState` pair "through the available writers". At that point the only writer is `decline_question`. The `answered` writer is `acknowledge_resolution`, which Task 4 adds. The `answering` writer belongs to 144 and does not exist. Task 2.5 also says to insert test rows through a helper, not through `record_question`. The slice's Technical Requirements call for this pair walk, so the task needs to say how each pair is exercised. One option is to seed the row in the "from" state directly and drive the writer for the "to" state. The other is to split the test, putting the `decline_question` pairs in 2.5 and the acknowledgment pairs in 4.3. As written, a junior implementer would have to guess.

### [CONCERN] "Illegal transition inside the acknowledgment" case in 4.3 looks unreachable

Task 4.3 requires a case where an illegal transition inside `acknowledge_resolution` raises `InvalidTransitionError` and rolls the whole acknowledgment back. D2's rule skips a record that is already `answered`, and `pending`, `declined` and `answering` can all legally reach `answered`. So no real record state hits the illegal branch. The task needs to say how to force it, for example by patching `QUESTION_TRANSITIONS` or injecting a fault. Otherwise the case should be dropped. The rollback property is already covered by the fault-injection case in 3.2 and the guard in 4.2.

### [CONCERN] Deferred end-to-end assertion is hedged though the ordering makes it certain

Task 5.5 says "If the stage does not exist yet, assert only the first state here", and Task 7.4 says "if they were deferred". The answering stage is built in Task 7, after 5.5, so the deferral always happens. Both tasks should state it plainly. 5.5 asserts only `pending`. 7.4 adds the `declined` → `answered` assertions.

### [NOTE] Tiny tasks that could merge into their neighbours

Task 4.1 is a one-function return-value change and Task 5.1 is a single constant. Both are trivial. Fold 4.1 into 4.2, and 5.1 into 5.2. This is optional because each has its own success check.

### [NOTE] Implementation detail beyond what the slice requires

Task 2.3 lists each SQL statement to write, and Task 2.1 spells out model fields. The LLD's schema table and API Contracts already fix these, so the task steps repeat them. A single reference to the LLD would be enough. The CHANGELOG entry in 10.1 does not trace to any success criterion. It looks like project convention rather than scope creep, so I only flag it.

### [PASS] Success-criteria coverage

Each criterion maps to a task:
- **Block and record, byte-identical payload:** 5.3, 5.5.
- **`node_already_blocked`:** 3.2, 5.5.
- **`question_missing`, config decline reasons and the null-config error:** 6.2, 7.4.
- **PM resolution before the stage runs:** 7.4.
- **PM resume with and without instructions, and re-pointing on stop or rejection:** 4.3.
- **Answerer record untouched, and a `submitted_by` spoof:** 4.3.
- **Transitions, crash safety, feed invariant, migration, purity:** 2.5, 5.5, 8.2, 2.5, 7.1.
- **Listings and `blocked` columns:** 9.1–9.3.
- **Docs:** 10.1.

### [PASS] Sequencing and commit distribution

Dependencies run in order. Models and the migration come first, then `record_question`, the acknowledgment rule, ingest, config, the settle function and stage, feed, inspection and docs. No circular dependencies exist. Each implementation task is followed by its tests. There are commit markers after groups 2 through 10, and the final commit is conditional on verification needing changes. No load or NFR test is required, because the slice restates no NFR.

### Run Digest

- Response length: 4693 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 106090 / 8791 / 97295 / 3426 / not computed
- Duration: 32.8 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
