---
docType: review
layer: project
reviewType: tasks
slice: the-gate-and-answer-submission
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/142-tasks.the-gate-and-answer-submission.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261102
dateUpdated: 20261102
reviewedSha: ab7307b2221c71f1b3c3c605b5867bea82329d62
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 104323
cachedTokens: 8831
cacheWriteTokens: 95488
completionTokens: 3610
durationSeconds: 31.4
costUsd: 0.419786
costBasis: provider
runId: run-20261102-p5-9afd4414
squadronVersion: 0.24.13
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are fully covered"
    location: "project-documents/user/tasks/142-tasks.the-gate-and-answer-submission.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit markers"
    location: "project-documents/user/tasks/142-tasks.the-gate-and-answer-submission.md"
  - id: F003
    severity: concern
    category: task-structure
    summary: "Task numbering in section 6 skips 6.1 and 6.2"
    location: "project-documents/user/tasks/142-tasks.the-gate-and-answer-submission.md:191-204"
  - id: F004
    severity: concern
    category: dry-duplication
    summary: "The declined-update change is specified twice"
    location: "project-documents/user/tasks/142-tasks.the-gate-and-answer-submission.md:94"
  - id: F005
    severity: concern
    category: sequencing
    summary: "Task 3.5 breaks the \"every task leaves the suite passing\" rule"
    location: "project-documents/user/tasks/142-tasks.the-gate-and-answer-submission.md:45"
  - id: F006
    severity: concern
    category: task-sizing
    summary: "Task 5.2 is oversized"
    location: "project-documents/user/tasks/142-tasks.the-gate-and-answer-submission.md:155-164"
  - id: F007
    severity: note
    category: task-organization
    summary: "The limit scenario test sits in the listing task"
    location: "project-documents/user/tasks/142-tasks.the-gate-and-answer-submission.md:216"
---

# Review: tasks — slice 142

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are fully covered

Each functional and technical criterion in the slice design traces to a task:
- **Limit scenario:** 7.2.
- **Reserved-term decline and listing column:** 4.2, 5.3 and 7.2.
- **Submitted outcome (slot, row and record asserted together):** 5.3.
- **PM-first and answerer-first races:** 5.4.
- **Runner rejection (D6):** 5.4.
- **Count and replay:** 5.4.
- **Config load errors:** 3.5 and 3.6.
- **Probe wiring:** 6.3 and 6.4.
- **Crash safety and gate-raises:** 5.5.
- **`ANSWER_DECISION` equals `ResolutionDecision.RESUME.value`:** 5.3.
- **Existing inbox suite unchanged:** 2.2.
- **Migration test and contract docs:** 3.4 and 7.3.
- **Walkthrough steps 5–6:** 8.1.

No task lacks a success criterion behind it. The slice states no NFR, so no load test or CI wiring task is required.

### [PASS] Sequencing, test-with pattern and commit markers

- **Dependencies and no cycles:** The extraction (2) comes before the types (3), the types before the gate (4), and the gate and types before `submit_answer` (5). The probe (6) and the listing and docs (7) come last, followed by final validation (8). There are no cycles.
- **Test-with pattern:** Tests follow their implementation tasks (3.4 after 3.1–3.3, 3.6 after 3.5, 4.2 after 4.1, 6.4 after 6.3, 7.2 after 7.1).
- **Commit markers:** The `**Commit**:` markers sit at working, tested points. They are not after every task and not only at the end.

### [CONCERN] Task numbering in section 6 skips 6.1 and 6.2

Section 6 starts at 6.3 and has no 6.1 or 6.2. This looks like leftover numbering from removed tasks. A reader or the task-checker may think two tasks are missing. Renumber to 6.1 and 6.2.

### [CONCERN] The declined-update change is specified twice

Task 3.2 already updates `UPDATE_QUESTION_DECLINED` to set `reserved_term`, and updates `decline_question` to pass `None`. Task 5.1 then says "make the declined update carry `reserved_term`" again. A junior will either redo the work or be unsure whether it's done. Remove it from 5.1, or move it from 3.2 to 5.1, so one task owns it.

Task 5.1 also hedges in two places: "or extend `UPDATE_QUESTION_ANSWERED` if…" and "reuse an existing constant if one already selects a blocked state by id". Replace both with a decision, since the facts section says the code was checked.

### [CONCERN] Task 3.5 breaks the "every task leaves the suite passing" rule

The header says each task leaves the full suite passing. Task 3.5 makes `answerer: {}` fail at load. Existing tests and fixtures that use it are only updated in 3.6. The suite is therefore red between 3.5 and 3.6. Either fold the fixture updates into 3.5, or reword the header so that it excludes the 3.5/3.6 pair. The commit marker comes after 3.6, so the committed state is fine.

### [CONCERN] Task 5.2 is oversized

Task 5.2 combines:
- validation;
- the ordered settle, block-resolved, count and gate sequence;
- the decline path;
- the submit path with three writes;
- the rollback on a `False` slot write;
- the `Store` base wiring.

Its own success line expects "near 300 lines", and the transaction body will likely pass the ~50-line function guideline. Split it into:
- (a) validation and the read-and-decide path, ending in a decline;
- (b) the submit path, the rollback handling and the `Store` wiring.

Also state how "roll back" on `_write_resolution` returning `False` is done. Without raising, the `with` block commits, so the task needs to say how to abort it.

### [NOTE] The limit scenario test sits in the listing task

The `answer_limit: 2` end-to-end scenario is in 7.2 beside the listing tests. It exercises `submit_answer`, but it needs `inspect questions --node`, so the placement is defensible. It does mean the limit's end-to-end proof only arrives after the section 5 commit. No change is required.

### Run Digest

- Response length: 4897 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 104323 / 8831 / 95488 / 3610 / not computed
- Duration: 31.4 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
