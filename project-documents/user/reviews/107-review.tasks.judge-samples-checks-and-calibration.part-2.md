---
docType: review
layer: project
reviewType: tasks
slice: judge-samples-checks-and-calibration
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 694538d61c93bede23c593ae70b1dcbe4f4d9b49
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 56.6
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage across both task files"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:20-21"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Test-with pattern and commit cadence"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:45-57"
  - id: F003
    severity: concern
    category: task-scoping
    summary: "Task 8.10 requires a commit but produces no change"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:546-548"
  - id: F004
    severity: concern
    category: clarity
    summary: "Task 6.3 has a garbled, ambiguous gating sentence"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:204"
  - id: F005
    severity: concern
    category: task-scoping
    summary: "File-size risk is only checked at the very end"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:510-511"
  - id: F006
    severity: concern
    category: test-coverage
    summary: "Task 6.4 assumes the fresh fixture matches the LLD"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:222-225"
  - id: F007
    severity: note
    category: api-consistency
    summary: "`record_check` and `record_work` take a `project_id` keyword the LLD omits"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:69"
  - id: F008
    severity: note
    category: test-coverage
    summary: "Test coverage for the new `RecordSource` members is implicit"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:52-53"
  - id: F009
    severity: note
    category: test-design
    summary: "End-to-end scenario cost"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:423"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage across both task files

Every criterion traces to a task or to file 1, which I checked only by grep.
- Check standing rows and record_check rejections: 5.3–5.4.
- Work records: 5.5–5.6.
- Replay with a WARNING: 5.4 and 5.6.
- `ingest review --judge-invocation-id`: 6.5–6.6.
- Parser and judge fixtures: 6.1–6.4.
- Listings running and stopped: 7.2, 7.4, 7.6.
- Writer guard and demo script: 8.1–8.2.
- Integration scenario and crash recovery: 8.3–8.5.
- Docs: 8.6–8.7.
- Metrology scan and public-API export: 8.8 and 5.7.
- Requirements trace and walkthrough: 8.9–8.10.

Judge samples, D2, D3, the filter, `calibration` and the migration are owned by file 1. The grep found its Task 2.1 (`RecordSource`), 2.3 (`CalibrationRow`), 4.3–4.4 (payload key) and 4.12 (calibration test). I did not read file 1 in full.

### [PASS] Test-with pattern and commit cadence

Each implementation task is followed immediately by its test task, and the test task carries the commit ("Commit with Task N.M"). Commits land every one to two tasks across Sections 5–8, not batched at the end. The only exception is Task 8.9, which is validation and says so. Dependencies run forward with no cycles. The conditional ordering for the case where slice 105 is unmerged is stated and consistent with each task's dependencies.

### [CONCERN] Task 8.10 requires a commit but produces no change

Task 8.10 requires "Committed on the slice branch (e.g. `docs: finalize slice 107 verification`)". Its steps only run the walkthrough and report differences. The LLD is updated "only if the PM asks". A junior AI will either make an empty commit or invent a change. Make the commit conditional on a PM-requested LLD update, or name the artifact to commit, such as a short walkthrough-results note. Task 8.9 has the same gap: it says to "tick each" requirement but does not say where the trace is recorded. Name a file or the final report.

### [CONCERN] Task 6.3 has a garbled, ambiguous gating sentence

The step reads "...Task 8.9 checks it Likewise, if the 302 file cannot be found...". It is missing a sentence break and it merges two different stop conditions: the fresh fixture is unavailable, and the 302 file is missing. Split them into separate bullets, each with its own stop-and-ask action. The gate also writes into file 1's Task 1.1 notes (line 424 of file 1), so say explicitly that the edit goes there. Task 6.4 claims to wait on that line, but its "for each fixture present" wording does not enforce the wait.

### [CONCERN] File-size risk is only checked at the very end

`cli/inspect_evidence.py` is edited by Tasks 7.1 and 7.3, and `cli/inspect.py` gains three `LISTINGS` entries. Neither task has a length check, unlike 5.3 and 5.5, which do. The first length check is in Task 8.8, after the code is complete and the docs are written. The LLD already flags `sql_evidence.py` and `mapping_evidence.py` as near the limit. Add a "report if clearly over ~300 lines" criterion to 7.1 and 7.3.

Task 8.8 also holds the metrology-scan widening, which could run when the modules are created. Moving it earlier would catch a violation sooner.

### [CONCERN] Task 6.4 assumes the fresh fixture matches the LLD

Task 6.3 says to assume nothing about the fresh file's content. Task 6.4 then asserts that every fixture has `derivation` `not_reported` and standing `unattested`. If today's Squadron writes `verdictSource` on the fresh capture, the test fails and the task gives no instruction. Add a step to stop and report to the PM when the fresh file differs. That matches the "report to the PM" instruction already given for the 302 file's score.

### [NOTE] `record_check` and `record_work` take a `project_id` keyword the LLD omits

The LLD API table shows `record_check(CheckInput)` and `record_work(WorkRecordInput)`. Tasks 5.3 and 5.5 add `*, project_id: str`. This is probably right, because the "node exists in the project" rule needs it and `record_verdict` probably does the same. Confirm against `record_verdict`'s signature and record the deviation in the LLD or the task.

### [NOTE] Test coverage for the new `RecordSource` members is implicit

Task 5.2 tests that unknown values raise. It does not say that `command_output` (checks) and `document` (work records) round-trip. Add one line using those sources in the 5.2 fixtures.

### [NOTE] End-to-end scenario cost

Three tests each build a full function-scoped scenario with a stop/seed/start cycle and several subprocesses. Isolation is good, but runtime will be high. If the suite slows noticeably, a module-scoped read-only scenario for 8.3 and 8.4 would be the first thing to try. No action is needed now.

### Run Digest

- Response length: 6033 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 56.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
