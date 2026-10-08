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
reviewedSha: 4fd958020c7e37572dac8c6350dd73247072076d
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
durationSeconds: 29.3
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Registry pin updated two tasks after `calibration` is registered"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:315-350"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Task 8.8 mixes code change, validation and a long manual walkthrough"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:502-519"
  - id: F003
    severity: concern
    category: dependencies
    summary: "Fresh judge fixture can stay blocked while later tasks proceed"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:203-209"
  - id: F004
    severity: note
    category: test-coverage
    summary: "Test-with pattern for the demo script and the listings"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:374-410"
  - id: F005
    severity: pass
    category: coverage
    summary: "Coverage of the slice success criteria"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:289-319"
  - id: F006
    severity: pass
    category: scope
    summary: "No scope creep"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Registry pin updated two tasks after `calibration` is registered

Task 7.3 adds `calibration` to `LISTINGS`. Task 7.5 is the first to update the pinned registry test, so that test can fail between them. Task 7.4's success criteria say "Tests pass" and carry a commit, and a junior AI could hit a red pinned-registry test there. Move the registry-pin update into Task 7.3 or 7.4 and add `checks` and `work-records` in 7.5. Alternatively, state in 7.4 that the pinned-registry test is expected to fail until 7.5.

### [CONCERN] Task 8.8 mixes code change, validation and a long manual walkthrough

Task 8.8 combines these jobs:
- a full-suite run;
- a file-length audit;
- widening the metrology-reference test (a source change);
- fixture follow-up;
- a seven-step walkthrough with flag corrections;
- a requirement-to-test traceability pass.

The metrology widening is a code change that belongs next to the module-creation tasks (Sections 5 and 7) or in its own task with a commit. The walkthrough and the traceability pass are each large enough to be separate tasks. Splitting them gives a junior AI clearer completion points and a commit after the code change.

### [CONCERN] Fresh judge fixture can stay blocked while later tasks proceed

Task 6.3 lets the fresh-fixture capture fail ("continue with the 302 file only"). The slice requires the fresh file to pin today's frontmatter and the absent `verdictSource`. Only Task 8.8 checks for it, at the very end. Tasks 6.4 and 6.6 handle a missing fixture only partly ("each judge fixture present"). Task 6.3 should record the blocked state, for example by marking a specific open-item line in the task file. The PM can then be asked before the end of the slice.

### [NOTE] Test-with pattern for the demo script and the listings

Task 8.1 and its test, Task 8.2, are properly paired. Task 8.2 runs the script as a subprocess, checks the lock refusal and the first-wins re-run, and covers the writer-guard update. Every implementation task in Sections 5–7 is paired the same way with the test task that follows it. No change is needed.

### [PASS] Coverage of the slice success criteria

Each file-2 criterion maps to tasks:
- Check standing rows, rejections, replay and ordering map to 5.3–5.4.
- Work-record content rules and filter map to 5.5–5.6.
- `ingest review --judge-invocation-id` with `score`, `criteria` and standing `unattested` maps to 6.1–6.6.
- The listings working with the process running and stopped map to 7.1–7.6.
- The integration scenario (three `j1` samples, the D2 rejection, `split_invocations` 1, `kill -9` and read-only re-read) maps to 8.3–8.5.
- The writer guard and `demo_checks.py` map to 8.1–8.2.
- The public-API pin maps to 5.7.
- The docs and CHANGELOG map to 8.6–8.7.

The file-1 criteria are covered by Tasks 4.x and 3.x, and file 1 contains the referenced `test_calibration.py` and `test_judge_samples.py`. The file-1 criteria are not re-verified here.

### [PASS] No scope creep

Every task traces to an LLD scope item. The tasks respect the exclusions: no inbox kinds for checks or work records, no change-feed additions, and no consensus logic.

### Run Digest

- Response length: 4319 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 29.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
