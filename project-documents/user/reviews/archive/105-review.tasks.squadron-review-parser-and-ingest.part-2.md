---
docType: review
layer: project
reviewType: tasks
slice: squadron-review-parser-and-ingest
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: deda74ce568821093adce58148a7d32cda716340
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
durationSeconds: 30.8
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Coverage of functional and integration criteria"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:354-395"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit cadence"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:21-298"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 8.1 depends on Task 7.4 without need"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:147"
  - id: F004
    severity: concern
    category: scope
    summary: "Task 7.2 asserts `test_finding_changes.py` needs no edit; the LLD says it switches"
    location: "tests/store/test_finding_changes.py:14"
  - id: F005
    severity: concern
    category: task-size
    summary: "Task 8.6 is large"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:244-260"
  - id: F006
    severity: concern
    category: coverage
    summary: "Task 8.3's failure-path list omits the `--stdout-json` error case"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:195"
  - id: F007
    severity: note
    category: scope
    summary: "Task 9.3 edits the slice design"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:397-399"
---

# Review: tasks — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Coverage of functional and integration criteria

Each criterion in this file's scope has a task:
- `verdict_to_payload` and its round trip: 6.1 and 6.2.
- Migration of the fixture-reading tests, and deletion of the old reader: 7.1–7.4.
- The exit code: 8.1.
- Failure paths with an empty inbox, and the no-`Store` rule (D6): 8.3.
- The success path and D7: 8.5.
- Two rounds, a provider failure, the repeat ingest and the `kill -9`: 8.6.
- A stopped process and an unknown project, with the process both running and stopped: 8.7.
- D5's stdout-versus-file consequence: 8.8.
- The docs and CHANGELOG, and the Verification Walkthrough: 9.1–9.3.

Tasks 2.1 and 2.2 in file 1 cover the PyYAML move and `provider_failure_problem`. The file-1 grep also shows a test for the import rules.

### [PASS] Sequencing and commit cadence

There are no circular dependencies. The 8.2 stub (`TODO(8.4)`) and its removal in 8.4 are handled explicitly. Commits are spread across the sections: each test task commits together with its implementation task. Final validation (9.3) comes last. The LLD requires no load test, and `tests/load/` already exists, so the regression run in 9.3 is valid.

### [CONCERN] Task 8.1 depends on Task 7.4 without need

Adding `ExitCode.REVIEW_UNREADABLE` has nothing to do with the test migration. The dependency serializes work for no reason. Depend it on Task 6.2, or on nothing in this file. Task 8.2 needs the parser (Section 5) and `verdict_to_payload`, which Task 8.4 uses. Those arrive through 8.1's chain only by accident.

### [CONCERN] Task 7.2 asserts `test_finding_changes.py` needs no edit; the LLD says it switches

The LLD lists `test_finding_changes.py` among the four files that switch to the parser. My grep confirms it imports only the `ROUND_*` paths from `review_fixtures`. So Task 7.2's claim holds, and covering it by running every test that imports the harness is reasonable. Make the intent explicit: add an acceptance line saying the file is verified to use the parser through the harness, so the LLD deviation is recorded. Otherwise a reviewer may flag a missed file.

### [CONCERN] Task 8.6 is large

Effort is 3. Its steps are:
- the multi-phase setup (start, create, stop, seed, start);
- three ingests plus a repeat from a copy with a `resolution:` key;
- the `kill -9` and restart;
- inspection of standings, `source_path`, `source`, and `inspect changes`.

A junior may stall on it. Consider splitting it into a shared fixture or helper task, with the assertions as a second task. 8.7 and 8.8 repeat the same setup ("same setup as Task 8.6"), so a shared fixture would also avoid duplication. Make the helper explicit.

### [CONCERN] Task 8.3's failure-path list omits the `--stdout-json` error case

All failure cases use `--artifact`. The `--stdout-json` branch has no failure-path test at CLI level. The case with practical value is a provider error body or non-JSON text, which gives `REVIEW_UNREADABLE`. Add one case to 8.3. The LLD names a "text with no JSON object" parser error. Without a CLI-level test, a wiring bug in that branch would go unnoticed until 8.5.

### [NOTE] Task 9.3 edits the slice design

The LLD itself says the walkthrough is "refined with captured output when Phase 6 completes", so this edit is sanctioned. The "stop and report if a step differs" instruction is a good guard.

### Run Digest

- Response length: 4379 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 30.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
