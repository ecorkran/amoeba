---
docType: review
layer: project
reviewType: tasks
slice: status-and-decisions
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/224-tasks.status-and-decisions.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 6804b4114021ca8747ad9b027bc757bae15305ef
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 112167
cachedTokens: 11198
cacheWriteTokens: 100965
completionTokens: 4019
durationSeconds: 32.5
costUsd: 0.446019
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Design decisions D1–D10 trace to tasks"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit markers"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:84"
  - id: F003
    severity: concern
    category: consistency
    summary: "`RejectCode` is defined in 2.5 without `beyond_last_record`"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:108"
  - id: F004
    severity: concern
    category: clarity
    summary: "Where `Deps` gains `project_names` and `list_runs` is stated twice"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:99"
  - id: F005
    severity: concern
    category: task-sizing
    summary: "Tasks 2.5 and 3.10 are each too large for one junior-AI step"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:107-113"
  - id: F006
    severity: note
    category: testing
    summary: "Hand-written fixtures in 3.1 depart from the \"never hand-write\" convention"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:139"
---

# Review: tasks — slice 224

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Design decisions D1–D10 trace to tasks

The slice has no separate success-criteria list, so I used D1–D10 and the walkthrough as the criteria. Each maps to tasks:
- D1: 3.1–3.3, 5.1–5.2.
- D2: 3.5.
- D3: 1.1–1.3, 3.8–3.9, plus the cross-check table test in 3.11.
- D4: 3.4, 3.6–3.7, 3.10–3.11.
- D5: 2.1–2.2, 2.5–2.6.
- D6: 2.3–2.4.
- D7: 2.7–2.8.
- D8: 3.10 and 4.1–4.2.
- D9: 2.9.
- D10: the recorded-fixture tasks 2.4 and 5.1.
- The `waiting_reason` retention pin is 1.4.
- Walkthrough steps 1–7 are 5.3.

I found no scope creep. Every task traces to a decision.

### [PASS] Sequencing, test-with pattern and commit markers

- **Order:** the groups follow the design's Development Order. `classify_pause` comes first, then the #303-independent work, then the fake-`sq` work, then the CLI, then the real fixtures. There are no circular dependencies.
- **Tests:** each implementation task is followed immediately by its test task.
- **Commit markers:** markers sit after groups 1, 2, 3, 4 and 6. Each marker falls at a point where the checks pass.
- **External dependency:** the `BLOCKED:` line for #303 is on a task that truly depends on an external deliverable, so it is valid.

### [CONCERN] `RejectCode` is defined in 2.5 without `beyond_last_record`

Task 2.5 defines the shared `RejectCode` `StrEnum` with only `unknown_program` and `malformed`. Task 2.7 returns `rejected / beyond_last_record` but never says to add that member. Task 6.1 requires every rejection code to be defined once. A junior implementer could define a second enum in `mark_read.py`, or add a bare string. Fix: list all three members in 2.5, or have 2.7 say to add `beyond_last_record` to the existing `RejectCode`.

### [CONCERN] Where `Deps` gains `project_names` and `list_runs` is stated twice

Task 2.3 adds `project_names` to `Deps`, and 3.2 adds `list_runs`. Task 4.1 then says the CLI alone builds `Deps` "(adding `list_runs` and `project_names`)". It is unclear whether the earlier tasks only change the `Deps` type and 4.1 wires the production values, or whether the wiring already happened. Fix: say in 2.3 and 3.2 that they extend the `Deps` definition, and in 4.1 that it supplies the production values. Alternatively, drop the repeat from 4.1.

### [CONCERN] Tasks 2.5 and 3.10 are each too large for one junior-AI step

- **2.5:** it bundles the request model, the result and record models, `since` conversion, program validation, record construction for two `answered_by` variants, member names and `read_through` rules.
- **3.10:** it bundles scope, the store read, the `sq` call, placement, classification, question-to-run joins, three `run_state` values, names and error mapping (lines 183–188).

Suggested cuts:
- Split 2.5 into the models plus request validation (`since` and `program`), then record building (`based_on`, `resume`, names) plus `read_through`.
- Split 3.10 into the orchestration flow, then the waiting-questions `run_state` join.

Keep the existing tests in 2.6 and 3.11 after each pair. Also, 0.2's discovery list is long (about 25 items). It is acceptable as a one-time lookup, but it could be trimmed to the items later tasks actually import.

### [NOTE] Hand-written fixtures in 3.1 depart from the "never hand-write" convention

Task 3.1 writes `sq runs list` fixtures by hand, while 2.4 and 5.1 forbid hand-written fixtures. This is sanctioned by D1 as a stand-in until #303 lands. The README requirement and the replacement in 5.2 bound the risk, so no change is needed.

### Run Digest

- Response length: 4281 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 112167 / 11198 / 100965 / 4019 / not computed
- Duration: 32.5 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
