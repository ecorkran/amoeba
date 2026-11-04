---
docType: review
layer: project
reviewType: tasks
slice: request-runs
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/184-tasks.request-runs.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: c3ebcfae544c7a7b79baaa429aaf79c74dec5f49
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 14
effort: xhigh
turns: 15
promptTokens: 510650
cachedTokens: 365222
cacheWriteTokens: 145418
completionTokens: 32913
durationSeconds: 156.7
costUsd: 0.232181
costBasis: provider
runId: run-20261104-tasks-plan-3bf84a0f
squadronVersion: 0.24.20
findings:
  - id: F001
    severity: concern
    category: accuracy
    summary: "Task 3.3 and 3.4 name an `intent` package that does not exist"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:142"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 3.3 points to the wrong task for filling `ProgramView.readiness`"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:137"
  - id: F003
    severity: concern
    category: sizing
    summary: "Task 6.6 is too large for one effort-5 task"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:196"
  - id: F004
    severity: concern
    category: coverage
    summary: "No test pins \"no provider node is blocked by a request wait\""
    location: "project-documents/user/tasks/184-tasks.request-runs.md:190"
  - id: F005
    severity: concern
    category: coverage
    summary: "The already-met criterion does not test that the asker is released only by 183's observation"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:245"
  - id: F006
    severity: concern
    category: coverage
    summary: "The tick budget is restated as a constraint, but no load case covers a request-bearing tick"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:273"
  - id: F007
    severity: note
    category: accuracy
    summary: "The design's walkthrough command conflicts with 183's convention for the kept-directory variable"
    location: "project-documents/user/slices/184-slice.request-runs.md:522"
  - id: F008
    severity: note
    category: sizing
    summary: "Two tests cover behavior that already exists and trace to no criterion"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:82"
  - id: F009
    severity: note
    category: sequencing
    summary: "Task 0.1 is under-estimated and will stop the slice until 183 merges"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:61"
---

# Review: tasks — slice 184

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 3.3 and 3.4 name an `intent` package that does not exist

Task 3.4 changes `intent/governance.py`, and the import-boundary rule in 3.3 (line 138) guards `amoeba.intent`. Neither exists. The governance module is at `src/amoeba/runner/intent/governance.py`. As written, the boundary rule would guard a package that is not there and pass for the real intent code. Name `amoeba.runner.intent` and `src/amoeba/runner/intent/governance.py` in 3.3 and 3.4. The design repeats the stale `intent/` path in its Architecture table (design lines 120 and 126). Under rule 10 of `tests/test_import_boundaries.py`, `runner/intent` importing `runner/lifecycle/readiness.py` is allowed, so the layering itself holds.

### [CONCERN] Task 3.3 points to the wrong task for filling `ProgramView.readiness`

3.3 says `readiness` is "filled in Task 6.6". Task 6.8 (line 208) is the task that fills it, and 6.6 is the finish step, which does not touch `ProgramView`. Change the reference to 6.8.

### [CONCERN] Task 6.6 is too large for one effort-5 task

6.6 covers polling, a four-row outcome table, the already-met git head read, the bind race, supersession while running, recovery ordering, crash resume, call counts and about 11 test cases. Split it into 6.6a (observe, pending-to-running recording, outcome table, entry resolution, `mark_due`) and 6.6b (already-met head check, `bind_edge` race, supersession while running, call counts). Task 6.5 is also effort 5 and borderline; keep it whole unless it grows.

### [CONCERN] No test pins "no provider node is blocked by a request wait"

The functional criterion in the design (line 488) says a request wait never blocks a provider node. 6.4 tests the request side (each request wait and its detail). 6.8 tests the reverse direction (a request run ahead of a planned slice). No listed test checks that a request whose check returns `checkout_dirty` or `checkout_branch` leaves a provider node in the same checkout to its own rules. Add that case to 6.4 or 6.8.

### [CONCERN] The already-met criterion does not test that the asker is released only by 183's observation

The design criterion (line 491) says the asker is released only when 183's observation passes. 8.2 asserts `met` and the edge bound to the commit, but not the asker's row after the bind. Add an assertion that the bind alone does not release the asker, and that the release comes from 183's observation on a later tick.

### [CONCERN] The tick budget is restated as a constraint, but no load case covers a request-bearing tick

The design says a pending request costs two subprocess calls per tick, "all under the tick budget" (design line 570). 9.1 runs three existing load files, none of which contains a request. CI already gates `tests/load` (`.github/workflows/ci.yml:54`), so no CI wiring task is needed. What is missing is one load case that ticks a provider with a pending or replied request, with bounds measured first, following the pattern 181 uses for `test_program_load.py`. Add it to 6.8 or 9.1.

### [NOTE] The design's walkthrough command conflicts with 183's convention for the kept-directory variable

The design runs `AMOEBA_KEEP_SCENARIO_DIR=1`. 183 (design line 469 and task line 285) and task 9.2 (line 276) use a `mktemp -d` path. Task 9.2 is the correct form, and `=1` would not give a directory. Correct the design at its next refresh.

### [NOTE] Two tests cover behavior that already exists and trace to no criterion

Task 1.2's "a newer-stamped store still raises `StoreSchemaError`" tests 181's behavior, and task 2.2's "finishing twice is refused" tests the journal's existing rule (line 116). Neither traces to a success criterion. Cut both unless the existing suites lack them.

### [NOTE] Task 0.1 is under-estimated and will stop the slice until 183 merges

0.1 is effort 1 but checks about 20 names across four slices. Raise it to effort 2. It will write `BLOCKED:` now, which the LLD prerequisites require. The 9.1 reference to `tests/load/test_program_load.py` names 181's file, which exists only after 181 merges.

### Run Digest

- Response length: 5993 chars
- Response is newline-free: no
- Tool calls made: 14
- Tool calls failed: 2
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 15
- Tokens — prompt / cached / cache write / completion / reasoning: 510650 / 365222 / 145418 / 32913 / not computed
- Duration: 156.7 s
- Cost: $0.23 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
