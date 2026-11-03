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
reviewedSha: 946ebc35f08ae1c41b8ab0c596f07e753866b0d5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 114888
cachedTokens: 11198
cacheWriteTokens: 103686
completionTokens: 5417
durationSeconds: 45.8
costUsd: 0.470883
costBasis: provider
runId: run-20261103-p5-b9aa2db9
squadronVersion: 0.24.14
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 8 tests depend on `finish_answering`, which is not built until Task 9"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:224"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 6.3 commit leaves unmatched questions stuck in `pending`"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:195-201"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Decline-reason coverage is repeated in four test tasks"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:287"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 10.1 is too large for one task"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:259-262"
  - id: F005
    severity: note
    category: proportionality
    summary: "Task 7.2 tests the test double"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:211-213"
  - id: F006
    severity: note
    category: commit-cadence
    summary: "Commit marker for Task 12 mixes source and docs"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:317"
  - id: F007
    severity: note
    category: sequencing
    summary: "Task 14 is gated by the blocked Task 13 and has no commit marker"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:345"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success criteria are covered by tasks"
    location: "project-documents/user/tasks/144-tasks.answering-run.md"
  - id: F009
    severity: pass
    category: commit-cadence
    summary: "Test-with pattern and commit markers are well placed"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:105"
---

# Review: tasks — slice 144

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 8 tests depend on `finish_answering`, which is not built until Task 9

Task 8.1 sends a `LaunchError` from `spawn` to `finish_answering`, and 8.2 (line 229) asserts the entry is resolved and the question declined `answering_launch_failed`. `finish.py` is Task 9, so that assertion cannot pass at the Task 8 commit marker. Task 8.1 also says the finish call is "wired in Task 10", but `finish_answering` is created in Task 9, so the text contradicts itself. This breaks the file's own rule that "each task leaves the full suite passing" and puts a commit at a point that isn't tested. Either move the spawn-failure case into Task 9's tests, or build `finish.py` before `launch.py` so Task 8 can call it. Correct the "Task 10" reference either way.

### [CONCERN] Task 6.3 commit leaves unmatched questions stuck in `pending`

After 6.3, `settle_pending` returns `Launch` and the stage "ignores `Launch` for now". A question with no answer on file is then neither declined `no_answer_on_file` nor launched, so it stays `pending` forever. The `feat:` commit at the Task 6 marker is therefore a behavioural regression, even though the suite passes. Either keep the old decline until Task 10, or move the `Launch` branch change into Task 10 where the stage handles it. Otherwise record in the task that this intermediate state is knowingly regressed.

### [CONCERN] Decline-reason coverage is repeated in four test tasks

Each D8 reason is tested in the decide table (6.2), in launch (8.2), in finish (9.2, "one case per decline reason"), and again in the end-to-end task 11.1 ("one decline case per D8 reason"). The mapping from input to reason is already proven by the 6.2 table. The end-to-end tier only needs to prove the wiring. Cut 9.2's per-reason sweep to a few representatives: a gate decline, a decide decline carrying evidence, and the discard path. Make 11.1 one parametrized case that uses the stub scripts. It should assert the decline, the block fields, and that a later tick does not relaunch, which is the one property only an end-to-end test shows.

### [CONCERN] Task 10.1 is too large for one task

10.1 builds the whole `AnsweringStage`: the observe pass, the stranded pass, the pending pass with the cap and budget rules, and the node-context handling. A junior AI would have to hold D9 and D10 in full. Split it into observe-and-finish, then stranded, then pending-and-launch. Or at least give each pass its own sub-task with its own success line. Task 10.3 is similarly large and could follow the same split.

### [NOTE] Task 7.2 tests the test double

The stub's answering mode is exercised directly by Tasks 8–11, and the round-trip through `read_answer` and `read_check` is already checked there. A dedicated stub test file (`tests/test_sq_stub_answering.py`) traces to no Success Criterion. Consider folding the round-trip check into 7.1 as a single smoke test, or dropping it.

### [NOTE] Commit marker for Task 12 mixes source and docs

`docs: document answering runs, add listing columns` also commits `inspection/questions.py` source changes. The listing columns are a `feat:`. Either use a `feat:` prefix or split the listing work (12.1–12.2) from the docs (12.3) with a marker between them.

### [NOTE] Task 14 is gated by the blocked Task 13 and has no commit marker

Tasks 13.1 and 13.2 carry valid `BLOCKED:` lines, so the Task 13 commit and the final validation can't complete until a Squadron release with 140's D8 capabilities exists. That is consistent with the slice, but it means the slice cannot close until then. Task 14.1 also says "clean after the commit" with no marker. If validation produces changes, such as formatting, a final commit is needed. If not, reword the line.

### [PASS] Success criteria are covered by tasks

Each criterion traces to at least one task.
- **Answer and record fields:** the answered-with-evidence criterion is covered by 4.4–4.5, 9.2 and 11.1.
- **PM precedent:** covered by 13.2.
- **Declines:** the distinct decline reasons are covered by 6.2, 8.2, 9.2 and 11.1.
- **D3 and D4:** covered by 2.3, 2.5 and 11.2.
- **Race and PM-wins cases:** covered by 11.2.
- **Restart adoption and crash between `begin_answering` and spawn:** covered by 2.7 and 11.2.
- **Cap:** covered by 10.3.
- **Settings:** the four required keys are covered by 5.1–5.2, and the `max_cost_usd` in `.squadron.toml` by 8.2.
- **Technical requirements:** purity (6.2, 6.3), crash safety (4.3, 9.2), `awaits_routing` and `record_finished` (2.3, 10.4), migration and feed-invariant tests (3.2) and docs (12.3).
- **No answerer section:** covered by 10.2, 10.4 and 11.2.

No task lacks a traceable criterion. The listing columns trace to the slice's Technical Scope and Inspection contract.

### [PASS] Test-with pattern and commit markers are well placed

Each implementation task is followed immediately by its tests. Commit markers sit after tested groups: reader, done-guard and recovery in Task 2, migration and types in Task 3, store operations in Task 4, settings in Task 5, and so on. They are not after every task and not only at the end. The slice states no NFR, so no load-test or CI-gating task is required.

### Run Digest

- Response length: 6358 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 114888 / 11198 / 103686 / 5417 / not computed
- Duration: 45.8 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
