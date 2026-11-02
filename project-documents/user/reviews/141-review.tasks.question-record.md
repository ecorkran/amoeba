---
docType: review
layer: project
reviewType: tasks
slice: question-record
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: resolved
sourceDocument: project-documents/user/tasks/141-tasks.question-record.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: 4f070b9ba4ad4e39e8feb5e45d559b963aab8c66
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 106093
cachedTokens: 11118
cacheWriteTokens: 94971
completionTokens: 3896
durationSeconds: 33.8
costUsd: 0.420801
costBasis: provider
runId: run-20261102-p5-6140d2da
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage is complete"
    location: "project-documents/user/tasks/141-tasks.question-record.md"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Feed trigger tests sit in a trailing test-only task, and the commit is mislabeled"
    location: "project-documents/user/tasks/141-tasks.question-record.md:222-229"
  - id: F003
    severity: concern
    category: scope
    summary: "Task 9.2 adds an all-projects `blocked` form the slice design does not specify"
    location: "project-documents/user/tasks/141-tasks.question-record.md:243"
  - id: F004
    severity: concern
    category: process
    summary: "The final verification commit is conditional and oddly named"
    location: "project-documents/user/tasks/141-tasks.question-record.md:280-281"
  - id: F005
    severity: note
    category: proportionality
    summary: "Task 11.1 mixes automated checks with a manual scratch-store walkthrough"
    location: "project-documents/user/tasks/141-tasks.question-record.md:276-277"
  - id: F006
    severity: note
    category: task-clarity
    summary: "`grep -rn \"012\" docs/` will produce false positives"
    location: "project-documents/user/tasks/141-tasks.question-record.md:265"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Sequencing and commit distribution are sound"
    location: "project-documents/user/tasks/141-tasks.question-record.md"
---

# Review: tasks — slice 141

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage is complete

Each functional and technical criterion maps to a task:
- Catch, block and record in one transaction, byte-identical payload: 3.x, 5.2, 5.4.
- Already-blocked node and null question: 3.2 and 7.4.
- Config: 6.x and 7.4.
- PM answer, stop and rejection, and answerer-name cases: 4.2.
- Resolution submitted before the stage runs: 7.4.
- Transition walk and crash safety: 4.2 and 5.4.
- Feed invariant and migration tests: 2.4 and 8.1.
- Purity check: 7.1.
- Contract docs: 10.1.
- Walkthrough steps 1–7: 11.1.

### [CONCERN] Feed trigger tests sit in a trailing test-only task, and the commit is mislabeled

The `question_recorded` and `question_state_changed` triggers are written in 2.2, but their behavioural tests (record, decline, PM answer, re-point emits nothing) wait until Task 8.1. That breaks the test-with pattern, and the triggers go six tasks and four commits untested beyond the invariant test.
Task 8's commit is `feat: put question record changes on the change feed`, but it contains only tests, so it should be `test:`.
Merge 8.1 into Task 4.2, the point where all of 141's writers exist, or into Task 2.4 for the record and decline cases. Task 8 then disappears, along with one commit. If the separate task stays, retitle its commit `test:`.

### [CONCERN] Task 9.2 adds an all-projects `blocked` form the slice design does not specify

Task 9.2 says "the project-scoped and the all-projects (`supervisor_rows`) forms both get the columns". Task 9.3 then tests the all-projects form. LLD D8 and the Success Criteria describe only a project-scoped `blocked` with `question_state` and `decline_reason`, so no success criterion traces to this requirement. If the all-projects form is a separate code path, it is unrequested scope. If it shares the code with the project-scoped form, the sentence and its test are redundant. Either drop the all-projects wording, or point it at a named LLD requirement.

### [CONCERN] The final verification commit is conditional and oddly named

The marker `chore: finish question-record verification fixes` applies only "if verification required changes". Nothing tells the implementer what to do when it does apply, such as which prior commit the fix belongs to, or what to do if the walkthrough fails. A `chore:` type also misdescribes verification fixes to source code, which would be `fix:`. Reword it to "commit any verification fixes as `fix: …`; otherwise no commit".

### [NOTE] Task 11.1 mixes automated checks with a manual scratch-store walkthrough

Steps 1–4 are `pytest` runs already covered by earlier tasks. Steps 5–7 are a manual CLI walkthrough that follows the LLD's Verification Walkthrough. Task 11.1 is the only place the CLI output, `amoeba feed` lines and config start-up failure are checked end to end, so it is justified. Steps 1–4 repeat checks the earlier tasks already run, so you could cut them.

### [NOTE] `grep -rn "012" docs/` will produce false positives

The "no stale 012 text" success check will also match unrelated strings, such as the historic migration list and the `012` file names. Scope it to the latest-migration paragraph instead.

### [PASS] Sequencing and commit distribution are sound

Dependencies run forward with no cycles. Each test task directly follows its implementation task, except Task 8 above. Tasks 5.4 and 7.4 explicitly coordinate edits to the same end-to-end test, so the pre-stage and post-stage states are not asserted wrongly. Commit markers are spread over eight points, none batched at the end. The task file is one file for an effort-3 slice, which fits.

### Run Digest

- Response length: 4615 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 106093 / 11118 / 94971 / 3896 / not computed
- Duration: 33.8 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Resolution (20261102)

- **Feed trigger tests in a trailing task** Fixed. The trigger tests moved into Task 4.2, where every 141 writer exists; the old Task 8 and its mislabeled `feat:` commit are gone, and later sections are renumbered.
- **All-projects `blocked` form** Fixed. `blocked_rows` and `all_blocked_rows` share `_blocked_rows`, so Task 8.2 now says to add the columns there, and the separate all-projects test clause is dropped.
- **Conditional verification commit** Fixed. The marker now says to commit verification changes as `fix: …`, or make no commit, and to rerun Task 10.1 after fixing a failed walkthrough step.
- **Task 10.1 repeats `pytest` steps** Fixed. The walkthrough runs steps 5–7 only; the full suite already covers steps 1–4.
- **`grep "012"` false positives** Fixed. The check now reads the latest-migration paragraph in `docs/store-contract.md`.
