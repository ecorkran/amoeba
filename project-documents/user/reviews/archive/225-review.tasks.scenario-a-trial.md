---
docType: review
layer: project
reviewType: tasks
slice: scenario-a-trial
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/225-tasks.scenario-a-trial.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: aa0d7946dd3b7235c06977b1a015c8e114b585eb
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 104432
cachedTokens: 11198
cacheWriteTokens: 93230
completionTokens: 4351
durationSeconds: 37.9
costUsd: 0.4184
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage"
    location: "project-documents/user/tasks/225-tasks.scenario-a-trial.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, commit markers and proportionality"
    location: "project-documents/user/tasks/225-tasks.scenario-a-trial.md:80"
  - id: F003
    severity: concern
    category: task-clarity
    summary: "\"Judged wrong\" and \"overridden\" have no detection method"
    location: "project-documents/user/tasks/225-tasks.scenario-a-trial.md:139"
  - id: F004
    severity: concern
    category: task-clarity
    summary: "Tally recipe cannot produce counts that live only in the ledger"
    location: "project-documents/user/tasks/225-tasks.scenario-a-trial.md:153-156"
  - id: F005
    severity: note
    category: sequencing
    summary: "amoeba#35 is closed before the work reaches the target branch"
    location: "project-documents/user/tasks/225-tasks.scenario-a-trial.md:170-172"
  - id: F006
    severity: note
    category: consistency
    summary: "`trial_start` definition differs slightly from the design"
    location: "project-documents/user/tasks/225-tasks.scenario-a-trial.md:133"
---

# Review: tasks — slice 225

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage

Each slice success criterion maps to tasks:
- **Registration and hook:** members registered and a pause in each starts `handle_pause` through the hook. Tasks 2.3 and 2.4 set it up, and 4.1 and 4.2 prove it.
- **Ledger:** at least 20 counted questions from at least two members, with every `decisions` question and missed hook accounted for. Tasks 5.1 to 5.3 cover it.
- **Note, verdict and plans:** tasks 6.1 to 6.3 cover them.
- **Opt-out flag and D9 shapes:** task 1.1 covers the flag with its unit test, and task 3.1 covers the D9 fixtures and tests with the four checks.
- **amoeba#35:** task 6.4 closes it.

Every task traces to a criterion or to a decision (D1 to D10), so I found no scope creep.

### [PASS] Sequencing, commit markers and proportionality

- **Order:** the code and docs come first (1.x), then the checks and the first commit. Install (2.1) follows that commit, as the design's walkthrough requires. Registration, hook, sanity pass and trial follow in order, and no dependencies are circular.
- **BLOCKED lines:** the `BLOCKED:` lines at 1.1 and 5.3 are waits on external state, not PM approvals, so they are valid.
- **Commit markers:** they sit at tested points: after the checks pass at 1.3, per D9 fix at task 3, and at the end.
- **Size:** one task file with seven groups fits a trial slice. I found no load-test or NFR requirement to cover.

### [CONCERN] "Judged wrong" and "overridden" have no detection method

Task 5.2 asks the agent to record whether each answer was "resumed and not overridden or judged wrong", and says a PM override is always wrong. The task never says how the agent detects an override. It also doesn't say who judges an answer wrong, or against what evidence (the record fields, the run's later output). The verdict depends on the answered-without-PM share, and that share depends on this classification. A junior agent would guess. Name the `decisions` or `status` field or evidence that marks an override. Say that answers with no such evidence count as answered, and that rows the agent is unsure about are flagged for the PM to change (D6 says the PM can change any row, but the tasks never mention it).

### [CONCERN] Tally recipe cannot produce counts that live only in the ledger

Task 6.1 says to write a `jq` recipe over the CLI's JSON and fill Counts, including wrong answers, false screen matches and should-have-answered. Those three categories are judgments recorded in the note's ledger. They are not in `decisions` or `status` JSON. The "counts equal the number of ledger rows" success check only works if the recipe runs over the ledger or the ledger rows are machine-readable. State what the `jq` recipe reads. For example, it could count answered-versus-waiting from CLI JSON and cross-check those totals against the ledger's hand-recorded categories. The note's ledger format would then need to be tally-friendly, and 5.1 should say so.

### [NOTE] amoeba#35 is closed before the work reaches the target branch

Task 6.4 closes the issue "noting the commit" while the commit is still only on the slice branch. The slice branch merges in Phase 7. The commit to cite is the 1.3 commit, not the final one. The design requires the issue to be closed, so keep the task. Consider having 6.4 record the 1.3 commit hash, and note that it is unmerged at that point.

### [NOTE] `trial_start` definition differs slightly from the design

D5 defines `trial_start` as the UTC time of the first run after the sanity pass. Task 5.1 records "now" at note creation. The two match only if no real run starts between the sanity pass and 5.1. Add a half-line to 5.1 saying to record it before real work begins.

### Run Digest

- Response length: 4518 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 104432 / 11198 / 93230 / 4351 / not computed
- Duration: 37.9 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
