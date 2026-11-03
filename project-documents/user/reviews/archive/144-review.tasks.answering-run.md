---
docType: review
layer: project
reviewType: tasks
slice: answering-run
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/144-tasks.answering-run.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 07a9970e558497ab037d1b3a6e9731e1e95f4b3d
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 115153
cachedTokens: 11198
cacheWriteTokens: 103951
completionTokens: 5215
durationSeconds: 44.4
costUsd: 0.469923
costBasis: provider
runId: run-20261103-p5-b9aa2db9
squadronVersion: 0.24.14
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 10.1 breaks the \"each task leaves the suite passing\" rule for seven tasks"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:250-253"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Task 11.1 repeats decline coverage that Tasks 6.2, 8.2 and 9.2 already give"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:294-297"
  - id: F003
    severity: note
    category: task-sizing
    summary: "Tasks 8.1, 9.1 and 10.6 are each large"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:212-216"
  - id: F004
    severity: note
    category: commit-placement
    summary: "Task 7 commits stub changes that have no tests of their own"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:204-206"
  - id: F005
    severity: note
    category: test-coverage
    summary: "Server route output is untested"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:312-318"
  - id: F006
    severity: note
    category: schema
    summary: "Task 3.1 does not mention a reason CHECK constraint"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:112-114"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks, with no scope creep"
    location: "project-documents/user/tasks/144-tasks.answering-run.md"
---

# Review: tasks — slice 144

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 10.1 breaks the "each task leaves the suite passing" rule for seven tasks

The file states "Each task leaves the full suite passing" (line 48). Task 10.1 changes `settle_pending`'s last branch to return `Launch`, which removes the `no_answer_on_file` decline. 10.1 defers `tests/runner/test_tick_answering.py` to 10.8 and says the suite is green again only at 10.9. Tasks 10.2–10.7 are then built on a red suite, so a junior AI cannot tell whether a failure comes from its own task. Make the `Launch` change part of 10.8, where the stage replaces the tick call. Alternatively, do it in 10.6 together with the stage's pending pass and update the tick test there. Either way the suite stays green at every step.

### [CONCERN] Task 11.1 repeats decline coverage that Tasks 6.2, 8.2 and 9.2 already give

Task 11.1 adds six end-to-end decline cases: check `no`, malformed reply, failed run, vanished run, launch failure and sources problem. These paths are already covered at lower tiers:
- 6.2 covers every decide row.
- 8.2 covers the Declined path through `finish_answering`.
- 9.2 covers every launch failure and sources problem.

No success criterion needs the e2e repeat. The criterion "declines with its own reason, none retried" is met by 6.2 plus 9.2. The only extra thing 11.1 gives is "never relaunched on a later tick". Cut 11.1 to one decline case that also asserts no relaunch on a second tick, and keep the answered case. That removes about five slow e2e tests.

### [NOTE] Tasks 8.1, 9.1 and 10.6 are each large

- 8.1 combines the record lookup, the decide call, the submit or decline branch, outcome handling and the entry resolution.
- 9.1 combines source assembly, the scratch directory, `begin_answering`, the spawn and three error paths.
- 10.6 combines the pending loop, the cap, the budget and the node-context rules.

Each maps to one function or one pass and has a matching test task. I would not split them, but a junior may need to break each into helpers. The "keep files near 300 lines" note already covers the stage.

### [NOTE] Task 7 commits stub changes that have no tests of their own

The Task 7 commit marker sits after a stub change whose only proof is the existing stub tests passing unchanged. The new mode is exercised first in Tasks 8–11. This is acceptable because the task says so explicitly. Merging Task 7 into the Task 8 commit would give a commit that is tested end to end.

### [NOTE] Server route output is untested

Task 12.1 says "and the server carry every D11 column", but 12.2 only tests the inspection listing and `--json`. If the server route builds its own output rather than sharing the model, add one assertion for it. If it shares the model, the existing tests suffice.

### [NOTE] Task 3.1 does not mention a reason CHECK constraint

Task 3.3 says to check new `DeclineReason` values against any CHECK constraint that lists reasons, but migration 015 in 3.1 does not say it would change one. The 3.4 test (every new reason accepted by `decline_question`) would catch the problem. It would be cheaper to look for such a constraint while writing 3.1.

### [PASS] Success criteria trace to tasks, with no scope creep

- **Reader and acceptance tests:** D3's reader cases and `awaits_routing` are in 2.3. `record_finished` ignoring `sq_answer` is in 2.3 and 10.9.
- **Done-guard:** D4 is in 2.4, 2.5 and 11.2.
- **Recovery:** 2.6 and 2.7.
- **Migration:** the 14 → 15 test and the feed invariant are in 3.2.
- **`begin_answering`:** the transaction, crash safety and the `block_resolved` and `settled` outcomes are in 4.2–4.3.
- **Evidence and detail on writers:** 4.4 and 4.5.
- **Settings:** the four keys are required with load errors in 5.1 and 5.2. The `.squadron.toml` cost cap is in 9.2.
- **Decide and purity:** 6.1 and 6.2.
- **Finish:** discard, crash retry and the gate decline are in 8.2.
- **Concurrency cap, order and budget:** 10.7.
- **Settle purity:** 10.1.
- **No-answerer behaviour:** 10.9 and 11.2.
- **Race cases:** PM during the run, PM before `begin_answering`, and PM between the read and `begin_answering` are in 11.2.
- **Restart adoption and crash before spawn:** 11.2.
- **Contract docs:** 12.3, including the D1 amendments.
- **Live tier:** 14.1 and 14.2, correctly marked `BLOCKED:` on the Squadron release.

The slice restates no NFR, so no load test or CI gate is required. Commit markers all sit at tested, passing points, except the Task 10.1 issue above. The dependency order holds: types come before store operations, then settings, decide, stub, finish, launch, stage, e2e, docs and live.

### Run Digest

- Response length: 5507 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 115153 / 11198 / 103951 / 5215 / not computed
- Duration: 44.4 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
