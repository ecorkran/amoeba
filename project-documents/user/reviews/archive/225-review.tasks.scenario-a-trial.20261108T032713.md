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
reviewedSha: f7a427efe82b96d3c5f6450bb9b12276f1c81f57
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 104577
cachedTokens: 11198
cacheWriteTokens: 93375
completionTokens: 4359
durationSeconds: 35.7
costUsd: 0.41906
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are covered and sequenced"
    location: "project-documents/user/tasks/225-tasks.scenario-a-trial.md"
  - id: F002
    severity: concern
    category: coverage
    summary: "Hook is only proven for one member, but the criterion says \"each\""
    location: "project-documents/user/tasks/225-tasks.scenario-a-trial.md:106-113"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 5.1 contradicts the commit-marker rule and sits at the wrong point"
    location: "project-documents/user/tasks/225-tasks.scenario-a-trial.md:143-149"
  - id: F004
    severity: note
    category: proportionality
    summary: "Redundant check and count steps"
    location: "project-documents/user/tasks/225-tasks.scenario-a-trial.md:176-179"
  - id: F005
    severity: note
    category: clarity
    summary: "0.2 results have no recorded destination"
    location: "project-documents/user/tasks/225-tasks.scenario-a-trial.md:62"
---

# Review: tasks — slice 225

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are covered and sequenced

- **Members registered:** the slice's first criterion is covered by 2.3 (registration) and 2.4 (hook).
- **20 counted questions from two or more members:** covered by 4.2 and 4.3, with the stop rule matching D5.
- **Note, counts, verdict and plans:** covered by 4.1, 6.1, 6.2 and 6.3.
- **Opt-out flag and its unit test:** covered by 1.1.
- **D9 fixtures:** covered by 5.1.
- **amoeba#35:** closed in 6.4.
- **Sequencing:** it holds. 0.2 findings feed 1.1, 1.2 feeds 2.4, and the 3.3 forward reference to 5.1 is fine.
- **Test-with pattern:** 1.1 includes its test, and 5.1 pairs each fix with a failing-first test.
- **Scope creep:** none. Every task traces to a design decision (D1 to D10) or to the walkthrough.
- **NFR load test:** the slice restates no NFR, so no load test or CI wiring is needed.

### [CONCERN] Hook is only proven for one member, but the criterion says "each"

- **The criterion:** "a pause in each [D1 member] starts `handle_pause` through the hook".
- **What the tasks verify:** only `trading-data` (3.1) and the amoeba repo (3.2).
- **The gap:** if #302 is per-project, 2.4 configures the hook in each member, but nothing checks that `trading-engine` and `trading-ui` actually fire.
- **Why it matters:** 4.3 needs only two members represented. A misconfigured third member could stay silent for the whole trial. It would show up as a missed hook only if it paused.
- **Fix:** extend 3.1 to run the live fixture in each of the three members, or add one sub-item in 2.4 that triggers a pause in each member.

### [CONCERN] Task 5.1 contradicts the commit-marker rule and sits at the wrong point

- **Conflict:** 5.1 tells the agent to "commit" after each fix inside the step. The project rule is to commit only at `**Commit**:` markers.
- **Marker placement:** the marker after section 5 sits before tasks 6 and 7. The fixes it covers are triggered during 3 and 4.
- **Empty commit:** if nothing failed, 5.1 is marked "none occurred" and there is nothing to commit. The task file doesn't say to skip the marker in that case.
- **Wrong commit recorded:** each ledger row records the installed commit (D2, 4.2). A fix reinstalled from an uncommitted working tree would give rows a commit that doesn't match what was installed.
- **Fix:** keep the intent that fix, commit, then reinstall. Remove the "commit" sub-step wording, or state that the marker applies per fix. Say the marker is skipped when 5.1 is "none occurred".

### [NOTE] Redundant check and count steps

- **Repeated work:** 7.1 re-runs the four checks already run in 1.3 and 5.1. It also repeats the counts-versus-ledger check from 6.1.
- **What is new:** the only new items are the `PAUSE_COMMAND_OPT_OUT_FLAG`-defined-once check and the every-fixture-has-a-test check.
- **Option:** fold 7.1 into 6.1 and 5.1, or cut it to those two items. Keeping it is harmless but adds a task.

### [NOTE] 0.2 results have no recorded destination

- **The gap:** 0.2's success criterion is "a note lists" the #302 form, #303 result, paths and baseline. The analysis note isn't created until 4.1, and 4.1's Setup section doesn't say it takes the 0.2 results.
- **Fix:** have 4.1 pull in the 0.2 findings, or say where 0.2 writes them.

### Run Digest

- Response length: 3769 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 104577 / 11198 / 93375 / 4359 / not computed
- Duration: 35.7 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
