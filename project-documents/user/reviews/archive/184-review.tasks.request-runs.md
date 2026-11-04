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
reviewedSha: 74dfe33e6e925151ec00fea981c906e3a2c52731
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
effort: xhigh
turns: 20
promptTokens: 955732
cachedTokens: 799319
cacheWriteTokens: 156397
completionTokens: 61870
durationSeconds: 268.6
costUsd: 0.339542
costBasis: provider
runId: run-20261104-tasks-plan-3bf84a0f
squadronVersion: 0.24.20
findings:
  - id: F001
    severity: concern
    category: verification
    summary: "Task 0.1 gate omits the 183 scenario support and the test files 184 extends"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:61-69"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 0.2 recreates the baseline test if it is missing, which contradicts the gate"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:72"
  - id: F003
    severity: concern
    category: size
    summary: "Task 6.9 leaves a budget breach that is already true as a conditional"
    location: "src/amoeba/runner/tick.py"
  - id: F004
    severity: note
    category: clarity
    summary: "Task 1.6 says \"Add no new code\" but D15 requires new code"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:102"
  - id: F005
    severity: note
    category: clarity
    summary: "Tasks 7.1 and 7.3 disagree on where the shared constants live"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:229"
  - id: F006
    severity: note
    category: scope
    summary: "Task 8.2 re-tests 183's release rules"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:250"
  - id: F007
    severity: note
    category: size
    summary: "Two tasks are smaller than they need to be as separate units"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:271"
  - id: F008
    severity: note
    category: size
    summary: "`project_config.py` is at 234 lines and 4.1 adds to it"
    location: "src/amoeba/runner/project_config.py"
  - id: F009
    severity: pass
    category: coverage
    summary: "Every success criterion and decision maps to a task"
    location: "project-documents/user/slices/184-slice.request-runs.md:482-514"
  - id: F010
    severity: pass
    category: verification
    summary: "Load-test gating already exists in CI"
    location: ".github/workflows/ci.yml:54"
  - id: F011
    severity: pass
    category: verification
    summary: "The no-migration claim for `NodeKind.REQUEST` and `sq_request` holds"
    location: "src/amoeba/store/schema/003_command_journal.sql:17"
  - id: F012
    severity: pass
    category: sequencing
    summary: "Sequencing, commits and gates follow the rules"
    location: "project-documents/user/tasks/184-tasks.request-runs.md:99"
  - id: F013
    severity: pass
    category: size
    summary: "Task count fits the slice"
    location: "project-documents/user/tasks/184-tasks.request-runs.md"
---

# Review: tasks — slice 184

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 0.1 gate omits the 183 scenario support and the test files 184 extends

0.1 confirms code names but not the test infrastructure that later tasks rely on.
- 8.1 and 9.2 honor `AMOEBA_KEEP_SCENARIO_DIR` "through the scenario support 183 added" (183 Task 7.7). The variable appears only in 183's plan, not in code, and nothing checks that 183 built the support.
- Tasks 1.2, 1.6, 7.1 and 7.3 extend `tests/store/test_program_schema.py`, `tests/store/test_program_reject_program.py`, `tests/runner/program/test_observe_edges.py` and `tests/inspection/test_program.py`. Tasks 8.4 and 9.1 use `tests/load/test_program_load.py`. None of these exists in the tree yet, since 181 and 183 are unmerged. 0.1 should list them.
- Task 6.1 says "extend the existing fake sq", and 0.1 says "the existing stub sq" with no path. Several candidates exist under `tests/` (`sq_stub.py`, `sq_stub_scripts.py`, `sq_stub_resume.py`). Name the one to extend.

Add these to 0.1's list under the same BLOCKED rule.

### [CONCERN] Task 0.2 recreates the baseline test if it is missing, which contradicts the gate

0.2 says "If it does not exist, create it as 183's Task 0.2 describes, from the code as it stands." 183's Task 0.2 owns that file, and 0.1 (line 65) already lists it as a 183 artifact to confirm. If 183 has not merged, the correct result is BLOCKED. A baseline captured from post-183 code would pin whatever behavior exists then, which defeats its purpose as a regression pin. Replace the fallback with: if absent, write `BLOCKED: slice 183 code is absent from the target`.

### [CONCERN] Task 6.9 leaves a budget breach that is already true as a conditional

`tick.py` is 311 lines today, past the ~300-line guideline before 184 changes anything. Task 6.9 says "If this pushes `tick.py` past its budget, move `_launch_context`..." (line 214). That condition already holds, so the extraction is required. Make it an explicit first step of 6.9, or a task before it, so the stage wiring lands in the sibling module. Task 0.1 also says 181 adds the program-stage call to `ProjectTick.run`, so the file grows before 184 starts.

### [NOTE] Task 1.6 says "Add no new code" but D15 requires new code

D15 says `apply_submission` gains the requests half of the `member_referenced` check. "Add no new code" can be read as "no new rejection code", which is what D15 means, or as "no code change". Reword it to "add no new rejection code" so the requests query is not skipped. The 1.6 tests would catch a skip, so the risk is low.

### [NOTE] Tasks 7.1 and 7.3 disagree on where the shared constants live

7.1 says to define the two detail formats "beside the listing's formats (Task 7.3)". 7.3 says to define the kind, title and reason "beside 183's `edge` kind". A junior has two possible homes for constants that tests import. Name one module.

### [NOTE] Task 8.2 re-tests 183's release rules

The variant where a commit not reachable from the target leaves the edge `not_on_target`, and a reachable one is released, tests 183's observation logic. The already-met success criterion needs one assertion: binding does not release the asker, and 183's rules do. Keep that assertion and drop the `not_on_target` branch, which 183's own tests cover.

### [NOTE] Two tasks are smaller than they need to be as separate units

8.6 (one doc paragraph, effort 1) can fold into 8.5. 1.6 (effort 2, its own commit) can fold into 1.5's commit, which is still a working, tested point. Neither split is required.

### [NOTE] `project_config.py` is at 234 lines and 4.1 adds to it

4.1 adds `RequestSettings`, its field and a loader "the way the answerer section is loaded." If that adds about 60 lines, the file reaches the ~300-line guideline. Ask the implementer to check the count after 4.1 and move the request section to a sibling module if needed.

### [PASS] Every success criterion and decision maps to a task

I checked the 14 functional, 5 technical and 2 integration criteria. Each has a task and a test. Examples: 6.8 and 8.1 cover the one-tick ordering, 6.4 covers the call counts, 6.10 covers both crash windows, 7.2 covers supersession and 8.3 covers locality. D1–D15 each have at least one task. The D13 deviation is already reflected in the architecture plan (`project-documents/user/architecture/180-slices.program-coordination.md:100`), so it needs no task.

### [PASS] Load-test gating already exists in CI

CI runs `uv run pytest tests/load` as its own step, so the 8.4 case is gated without new CI wiring.

### [PASS] The no-migration claim for `NodeKind.REQUEST` and `sq_request` holds

`command_journal.kind` and `nodes.kind` are both `TEXT NOT NULL` with no `CHECK` (`001_initial.sql:16`). Task 2.1's "add no migration" is correct.

### [PASS] Sequencing, commits and gates follow the rules

No task merges or pushes. Dependencies run forward: store, then node and journal, then band and hold, then config, then plan marks, then the request run, then listing and scenario, then docs. The 16 `**Commit**:` markers sit at tested points, and the one at 9.2 is marked conditional. Each implementation task carries its own tests. The only wait is the BLOCKED gate in 0.1, which the rules allow.

### [PASS] Task count fits the slice

The file has 42 tasks in one file, which suits a slice with 15 decisions. The largest tasks are 6.5 and 8.1, both at effort 5. Both are cohesive: D7 steps 5–7 are one ordered sequence, and 8.1 is one scenario. Splitting either would break the ordering it tests, so I recommend no split.

### Run Digest

- Response length: 8758 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 955732 / 799319 / 156397 / 61870 / not computed
- Duration: 268.6 s
- Cost: $0.34 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
