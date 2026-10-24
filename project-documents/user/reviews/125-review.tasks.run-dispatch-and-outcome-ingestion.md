---
docType: review
layer: project
reviewType: tasks
slice: run-dispatch-and-outcome-ingestion
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261024
dateUpdated: 20261024
reviewedSha: 3832c9263fd8f48964ab30a3a76a113df8d69828
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 128991
cachedTokens: 12782
cacheWriteTokens: 116205
completionTokens: 33717
durationSeconds: 149.5
costUsd: 0.190617
costBasis: provider
runId: run-20261024-p5-0a64b162
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every success criterion has a task"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md:503"
  - id: F002
    severity: concern
    category: process
    summary: "Prerequisite edits are described as committed but are not"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md:95"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Two external preconditions are checked after contract work has started"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:114"
  - id: F004
    severity: concern
    category: process
    summary: "Task 1.1 has no commit and an output with nowhere to go"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:76"
  - id: F005
    severity: concern
    category: docs
    summary: "`process-contract.md` is edited in two tasks"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:181"
  - id: F006
    severity: concern
    category: sizing
    summary: "Several tasks bundle too much for one junior pass"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:247"
  - id: F007
    severity: concern
    category: testing
    summary: "Tick-level ingestion test repeats the outcome table"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:421"
  - id: F008
    severity: note
    category: sequencing
    summary: "Dependency list for 9.1 misses its direct inputs"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:446"
  - id: F009
    severity: note
    category: sequencing
    summary: "Section 2 says contract work lands before Runner code, but 2.1 edits runner code"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:92"
  - id: F010
    severity: note
    category: naming
    summary: "Some result keys are used but not in the shared-names list"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:57"
  - id: F011
    severity: note
    category: instructions
    summary: "Two instructions point at a value without saying where it comes from"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:115"
---

# Review: tasks — slice 125

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Every success criterion has a task

Functional criteria map to 6.2–6.3 and 7.3 (two-tick dispatch, pointer failures), 5.4 and 7.4 (concurrency), 7.2 (unresolved checkout), 4.2–4.4 (ingestion, split and empty reviews, unknown reviews, crash points, routing), 8.1 (reissue), and 9.1–9.2 (pointer moved). Technical criteria map to 2.4–2.5 (migration and EXPLAIN), 5.1–5.4 and 4.1 (table tests over D1, D3, D4, D6), 6.2 and 10.1 (TickBudget coverage), 5.3 (merge import test), 2.8 and 10.2 (contract text and CHANGELOG), and 10.3 (full gate and walkthrough). No load-test NFR is restated, so none is required.

### [CONCERN] Prerequisite edits are described as committed but are not

The slice says the plan entries 6–7 and the arch edits are "committed before merge" and "already met" (also line 643). The session-start git status lists `120-arch.runner-routing-engine.md` and `001-initiative-plan.amoeba.md` as modified and uncommitted. Task 1.1 branches from the target with those edits still in the working tree. Planning edits should be committed to the target before Phase 6. Add a step to 1.1 that confirms a clean tree, or commit the edits first. The D7 correction to the arch "Run identity" sentence has no task that checks it.

### [CONCERN] Two external preconditions are checked after contract work has started

Task 2.3 is the first point where the task file checks for a registered worktree (`cf worktree list --json`). Task 3.1 (line 196) is where it checks for local paused, failed and completed runs. Either one can end in BLOCKED, and that stops almost every later task, including all of Sections 5–10. Both checks are cheap and read-only. Move them into Task 1.1 so the slice fails before the contract changes are made.

### [CONCERN] Task 1.1 has no commit and an output with nowhere to go

The project rules require at least one commit per task. Task 1.1 says "No commit needed" and also says "Record the passed-test count in this task", but the task file is not committed by any step. Either drop the count or put it in the first commit's message or body (Task 2.1).

### [CONCERN] `process-contract.md` is edited in two tasks

Task 2.8 (line 181) edits the read-back section of `docs/process-contract.md`. Task 10.2 (line 485) edits the dispatch and ingest stages of the same file. Two passes over one doc invite drift. Keep the whole process-contract edit in 10.2, or make 2.8 cover only the store and evidence docs.

### [CONCERN] Several tasks bundle too much for one junior pass

- **4.3** combines the block and result logic, the factory version label, the new fault kind, the `finish` delegation, and seven test cases. Split the block and result from the `finish` delegation and re-entry tests.
- **5.3** (line 305) combines `dispatch_params`, the new action and `LaunchRun` fields, per-step `ProjectView` facts, the held-set plumbing and the import test. Split it into params and types, then view facts.
- **7.3** (line 403) combines Act for both actions, the reissue placeholder and six scenario tests. Move the concurrency and ingestion scenarios to 7.4.
- **2.3** (line 109) combines fixture capture, record fields, cwd selection, the index rule and function extraction. Split out the capture and record fields.

### [CONCERN] Tick-level ingestion test repeats the outcome table

Task 7.4 lists every outcome again (completed, split, empty, each unknown, paused, failed with `cost_cap` and `stall`, orphaned, vanished). Task 4.1 already tests each outcome as a table, and 4.3 tests the store path. The success criteria need the tick-level path, not every outcome again. Keep one paused, one failed and one unknown-review scenario, plus the unrouted check.

### [NOTE] Dependency list for 9.1 misses its direct inputs

Task 9.1 uses the pointer write's `worktree_id` (defined in 2.3) and the time the write resolved (6.3). Its listed dependencies are 2.1 and 5.1, and neither supplies those inputs. Either list 2.3 and 6.3, or state that the function takes plain values.

### [NOTE] Section 2 says contract work lands before Runner code, but 2.1 edits runner code

Task 2.1 changes `runner/lifecycle/slugs.py`. That is a placement detail, not a problem, but the section intro should not say "before any Runner code".

### [NOTE] Some result keys are used but not in the shared-names list

Task 6.3 writes `cf_updated_at` and `file_slice`. The shared-names list in line 57 does not name either, and Task 2.3's adoption record does not include `cf_updated_at`. Add both to the shared list, or state which task defines `cf_updated_at`.

### [NOTE] Two instructions point at a value without saying where it comes from

- Task 2.3 says `cf get --json -p <amoeba's CF project id>` but does not say where the id comes from. If the existing `tests/fixtures/cf/cf_get_amoeba.json` carries it, name that file.
- Task 10.3 (line 498) omits two fallbacks in the slice's walkthrough: running `cf init` if the scratch copy asks for config, and choosing the first runnable slice if slice 126 is already designed. Include both, since the task says to run the walkthrough "exactly as written".

### Run Digest

- Response length: 6731 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 128991 / 12782 / 116205 / 33717 / not computed
- Duration: 149.5 s
- Cost: $0.19 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
