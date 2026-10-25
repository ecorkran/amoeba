---
docType: review
layer: project
reviewType: tasks
slice: resolutions-and-resumption
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/127-tasks.resolutions-and-resumption.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261025
dateUpdated: 20261025
reviewedSha: 2ea151364db3733afc56de83662a9c24228b28c8
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 118577
cachedTokens: 11222
cacheWriteTokens: 107351
completionTokens: 11089
durationSeconds: 83.3
costUsd: 0.542231
costBasis: provider
runId: run-20261025-p5-ce38b28c
squadronVersion: 0.24.4
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Declared dependencies omit real prerequisites"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:289"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 7.2 adds a required argument that breaks the tick until Task 7.3"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:284"
  - id: F003
    severity: concern
    category: coverage
    summary: "The `handled` path is never proven end to end"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:342"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 6.4 is too large and should be split"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:259-268"
  - id: F005
    severity: note
    category: completeness
    summary: "`PARAM_RESUME_SKIPPED` and its value have no creating task"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:155"
  - id: F006
    severity: note
    category: documentation-consistency
    summary: "Task-level deviations from the slice design are not reflected in the design"
    location: "project-documents/user/slices/127-slice.resolutions-and-resumption.md:113"
  - id: F007
    severity: note
    category: size-guideline
    summary: "`observe.py` will stay over the size guideline"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:363"
  - id: F008
    severity: note
    category: sequencing
    summary: "Failure tests in 7.3 run before the `resume_failed` routing input exists"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:293"
  - id: F009
    severity: note
    category: traceability
    summary: "Pointer watch (Task 7.4) traces to the design body, not a success criterion"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md:299"
  - id: F010
    severity: pass
    category: coverage
    summary: "Success-criteria coverage, test-with pattern and commit distribution"
    location: "project-documents/user/tasks/127-tasks.resolutions-and-resumption.md"
---

# Review: tasks — slice 127

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Declared dependencies omit real prerequisites

The file says that if a task is `BLOCKED:`, work continues with the next task whose listed dependencies are all checked off. That makes the dependency lists load-bearing, and three of them are incomplete:
- **Task 7.3** (line 289) lists 6.4 and 7.2. Its tick tests run "from an applied retry", which needs the resolution stage wired in by Task 4.2. Neither 6.4 nor 7.2 depends on 4.2, directly or transitively.
- **Task 9.2** (line 340) lists 8.2 and 9.1. It tests `rerun`, which needs Task 5.4's `resolution` key on the pointer write. It also needs the stage from Task 4.2. Neither is reachable through its listed dependencies.
- **Task 4.2** (line 191) edits `tick.py` but lists only 4.1. It does not list Task 1.2, which moves the act stage out of `tick.py`.

Task 4.2 has an explicit `BLOCKED:` path, so a blocked 4.2 would not stop 7.3 or 9.2 from being picked up.

Add 1.2 to 4.2, 4.2 to 7.3, and 4.2 and 5.4 to 9.2.

### [CONCERN] Task 7.2 adds a required argument that breaks the tick until Task 7.3

Task 7.2 makes `observe` take the resumed-from mapping "as a new argument". The tick only starts building and passing that mapping in Task 7.3 (line 291). Task 7.2 commits with its own "tests pass" success line, and the project forbids silent default values. So the tick's existing `observe` call would either break at 7.2, or 7.2 would have to quietly update the call site.

Either make 7.2 update the call site with the real mapping build, or merge the mapping-building step from 7.3 into 7.2. Each commit then leaves the suite green.

### [CONCERN] The `handled` path is never proven end to end

The slice design requires that after `handled`, "the run's current outcome is ingested and routed". Task 9.2 excludes `handled` from its tick-level proofs. It says retry, accept and handled "are proven in Tasks 6.4 and 7.3".
- Task 6.4 only asserts that `handled` journals an entry and launches nothing (line 267).
- Task 7.3's tick tests start from an applied `retry` (line 293).

Nothing drives an `ObserveRun` through confirmation, ingestion and routing. Add a `handled` case to 7.3 or 9.2: a run that has moved on is observed, ingested and routed.

### [CONCERN] Task 6.4 is too large and should be split

Task 6.4 puts these in one `act_continuation` function:
- the budget check, the pre-poll, and `prepoll_decision`;
- four branches: wait, run missing, observe, and launch;
- two budget gates;
- journaling the entry with up to seven keys;
- `spawn` and tracking, with its `LaunchError` path.

That conflicts with the file's own rule of about 50 lines per function. It is also the file's longest test list.

The observe, skip and run-missing branches (`ObserveRun`, `resume_skipped`, `run_missing`) share no code with the launch branch beyond the pre-poll and the journal write. Split it into:
- 6.4a: pre-poll, wait, run missing, and observe/skip;
- 6.4b: the launch path with `spawn`, argv and spawn errors.

Tests and a commit would follow each part.

### [NOTE] `PARAM_RESUME_SKIPPED` and its value have no creating task

The task-level additions (line 67) define `PARAM_RESUME_SKIPPED` and the value `run_not_at_pause` in `runner/resolutions/vocabulary.py`. Task 3.1's list of vocabulary contents (line 155) does not mention them. Tasks 6.3 and 6.4 consume them. Add them to 3.1 so they are defined once and before use.

### [NOTE] Task-level deviations from the slice design are not reflected in the design

The task file's "Task-level additions" change several LLD details:
- `classify` takes `(node, executor, entries)`, where the LLD sketch at line 113 shows `(step, executor, entries, decisions)`.
- `Acknowledgment` gains a `code` field.
- `dispatch_state` keeps its `pointer_confirmed` argument.
- `ContinuationPlanner` is registered in `factory.py`, where line 125 names `tenant.py`.
- `resume_skipped` is a journal parameter, but line 350 lists it as a result key.

The task file lists these openly, but its reading note never says that the task file wins over the LLD. A junior AI reading both will hit contradictions. Either add a one-line precedence statement or amend the LLD.

### [NOTE] `observe.py` will stay over the size guideline

`observe.py` is already 335 lines, and Task 7.2 still adds lines to it (line 286). Task 9.5 asks to confirm that every changed file is "near 300 lines". That check will either fail or be waved through. Reword it to "no file this slice changed grew past the guideline except where noted", or move the dispatch out of `observe.py`.

### [NOTE] Failure tests in 7.3 run before the `resume_failed` routing input exists

Task 7.3 asserts that failed resumes block the step and re-offer the paused-run decisions. The routing vocabulary only learns `resume_failed` in Task 8.1. Design D8 says a failed resume "can only escalate" through routing. I could not verify from these documents whether the route stage already routes a resolved-failed entry that has `outcome: paused`. If it does, 7.3's assertions pass only by accident, and a second block could appear once 8.1 lands. Confirm the order, or make the 7.3 assertions explicit about what routing does at that point.

### [NOTE] Pointer watch (Task 7.4) traces to the design body, not a success criterion

No success criterion mentions the pointer-move check for continuation entries. It comes from "Consumes from Other Slices" (125) in the LLD, at slice design line 427. It is a small, design-backed task, so I would keep it. If you want strict traceability, add a one-line criterion to the LLD.

### [PASS] Success-criteria coverage, test-with pattern and commit distribution

Apart from the `handled` gap above, every functional, technical and integration criterion maps to at least one task:
- Retry and accept: 6.4, 7.3.
- Accept of a completed outcome, rerun and stop: 9.2, 5.4.
- Rejections: 3.3, 4.1.
- Instructions passed byte for byte: 6.1, 6.3, plus the source test in 9.2.
- Missing run and recovery: 2.4, 6.2, 6.4.
- Resume confirmation and failures: 7.1, 7.2, 7.3.
- A run moved by hand, and cut-off or poll failure: 6.4.
- Accept over CONCERNS: 8.2.
- Crash safety: 7.5.
- A poisoned resolution stays contained: 4.2.
- Hold: 9.2.
- Migration and the partial-index `EXPLAIN` test: 2.1, 2.3.
- Contract suite: 2.5.
- Docs and CHANGELOG: 9.3, 9.4.

Implementation tasks pair with their tests, or explicitly commit with the next task (4.1 with 4.2, 5.1 with 5.2, 8.1 with 8.2). Commits fall in every section rather than at the end. I found no circular dependencies. The slice states no NFR, so no load-test or CI-gating task is needed. Task count and test scope are proportionate for a 3/5-effort slice.

### Run Digest

- Response length: 8057 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 118577 / 11222 / 107351 / 11089 / not computed
- Duration: 83.3 s
- Cost: $0.54 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
