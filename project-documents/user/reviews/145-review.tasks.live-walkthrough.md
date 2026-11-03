---
docType: review
layer: project
reviewType: tasks
slice: live-walkthrough
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/145-tasks.live-walkthrough.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 4f1f3e266bad54671bc1e28e9249e826f4142edb
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 100995
cachedTokens: 11198
cacheWriteTokens: 89793
completionTokens: 5708
durationSeconds: 48.7
costUsd: 0.418221
costBasis: provider
runId: run-20261103-p5-6d56c562
squadronVersion: 0.24.16
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "Fixture-cause fixes are applied only to the scratch checkout, not to the repository tree"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md:53"
  - id: F002
    severity: note
    category: proportionality
    summary: "Task 10.2 is a test beyond what the criteria need"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md:232"
  - id: F003
    severity: note
    category: traceability
    summary: "Setup script does not print node ids, which the slice's component table lists"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md:121"
  - id: F004
    severity: note
    category: sequencing
    summary: "Fixes made during task 4 ride in a later commit with a different type"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md:140"
  - id: F005
    severity: note
    category: sequencing
    summary: "Missing explicit prerequisite lines on 9.2 and 9.3"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md:214"
  - id: F006
    severity: note
    category: scope
    summary: "Task 2.1 refactors an existing test module"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md:87"
  - id: F007
    severity: pass
    category: completeness
    summary: "Success criteria coverage and test-with ordering"
    location: "project-documents/user/tasks/145-tasks.live-walkthrough.md"
---

# Review: tasks — slice 145

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Fixture-cause fixes are applied only to the scratch checkout, not to the repository tree

The D7 recovery note, and task 7.1 at line 185, say a rerun adds a fresh slice index "to the scratch plan" and "commit it", and 7.1 says to copy 101's forcing sentence. Both describe edits in `D/checkout`.

The slice's D7 "Fixture cause" says "the tree is fixed", meaning `scripts/answerer_walkthrough/project/`. D6 says the tree is committed so "a later run uses the same plan and the same forcing wording."

If a forcing sentence turns out to be at fault, the checkout gets the corrected entry and the repository tree keeps the broken one. Task 11.2 only updates the doc. A later person repeating the walkthrough would hit the same failure. Add a step to the fixture-cause recovery, or to task 11, that carries any corrected or added slice entry back into the repository tree. Then re-run `test_walkthrough_fixture.py` and fold the change into the task 11 commit.

### [NOTE] Task 10.2 is a test beyond what the criteria need

The slice requires that every tail is in `question_tails.json` with its run id and date, and that 144's live tier still collects. Task 10.1 already checks the entry count against the store, and the `--collect-only` check in 10.2 covers the second requirement. A separate test file asserting that four keys are non-empty is marginal. Consider dropping the new test file and keeping only the collect check.

### [NOTE] Setup script does not print node ids, which the slice's component table lists

The slice's Component Structure table says the script "prints the exports and node ids". Task 3.5 prints the exports and the start command only. Task 4.2 instead finds the nodes with `amoeba inspect nodes --json`, and 5.1 puts that command in the doc. That works, and D6's own script description does not mention node ids. Keep it as is, or drop "node ids" from the slice table.

### [NOTE] Fixes made during task 4 ride in a later commit with a different type

Task 4.2 tells the implementer to fix task 1 or task 3 if the link or the probe fails. Task 4 has no commit marker, so any such fix lands in task 5's `docs:` commit, though it is a script or tree change. Add a one-line instruction to commit such a fix separately as `fix:`, or accept the mislabel. Separately, tasks 6–9 are live and have no marker. Their results are committed only at task 10, which is acceptable because they change no code.

### [NOTE] Missing explicit prerequisite lines on 9.2 and 9.3

Tasks 7.1, 8.1, 8.2 and 9.1 each name their prerequisite task. 9.2 and 9.3 do not, though file order and the 9.1 → 9.2 → 9.3 dependency make it clear. For consistency, add "Prerequisite: task 9.1 complete" and "Prerequisite: task 9.2 complete".

### [NOTE] Task 2.1 refactors an existing test module

Moving the private helpers out of `test_sources.py` is not named in the slice, which says only to use "143's fixture-repository helper". It serves D6's fixture test and avoids importing from a test module. Its success check, that the existing tests pass with only their imports edited, is clear and bounded. This is reasonable and low risk.

### [PASS] Success criteria coverage and test-with ordering

- **Cases 1–4:** covered by tasks 6.1, 7.1, 8.1–8.2 and 9.1–9.3, each with the record fields and journal entries the slice names.
- **Fixture test:** covered by 2.2.
- **Script refusals and stops:** covered by 3.1–3.4 and tested in 3.6.
- **Lint, format and typecheck:** 3.6 and 11.3.
- **Doc and link:** 5.1 and 5.2.
- **Tail capture and issues:** 10.1 and 10.3.
- **Registry isolation and nothing written outside `D`:** 5.1 and 11.1.
- **Blocking:** `BLOCKED:` is on 6.1, and later live tasks name their prerequisites.
- **Commit markers:** they sit at tested points (after 1, 2, 3, 5, 10 and 11).
- **Test placement:** the script tests sit in the same task group as the script, and the fixture test follows its tree.

There are no NFRs, so no load-test or CI-gating task is needed.

### Run Digest

- Response length: 4970 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 100995 / 11198 / 89793 / 5708 / not computed
- Duration: 48.7 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
