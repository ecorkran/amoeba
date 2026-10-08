---
docType: review
layer: project
reviewType: tasks
slice: judge-samples-checks-and-calibration
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 694538d61c93bede23c593ae70b1dcbe4f4d9b49
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
durationSeconds: 32.3
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Judge-sample and calibration criteria map to tasks"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:293-296"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:36-411"
  - id: F003
    severity: pass
    category: coverage
    summary: "Cross-file ownership and public exports are explicit"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:30-32"
  - id: F004
    severity: note
    category: sequencing
    summary: "Conditional 105 and 106 handling relies on Task 1.1 notes"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:242"
  - id: F005
    severity: note
    category: scope
    summary: "`mapping_evidence.py` size risk is flagged but unresolved"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:202"
  - id: F006
    severity: note
    category: testing
    summary: "\"Single definition\" criteria are asserted, not tested"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:77"
---

# Review: tasks — slice 107

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Judge-sample and calibration criteria map to tasks

- **Three separate samples:** Tasks 4.1, 4.2, 4.7 and 4.8 cover three samples of one invocation staying three records and the `judge_invocation_id` read-back.
- **D2 same-node rule:** Tasks 4.5 and 4.6 cover it on both the direct and inbox paths.
- **D3 exclusion:** Tasks 4.9 and 4.10 cover it, including the cross-type case and the unchanged review-verdict case.
- **Calibration:** Tasks 2.3, 2.4, 4.11 and 4.12 cover the D4 fields, the no-store unit tests, and the read-only handle.
- **`check_standing` table:** Tasks 2.1 and 2.2 cover every standing row.
- **Migration and upgrade:** Tasks 3.1 and 3.2 cover the migration and the upgrade-preserves-data requirement.
- **Payload key and flag:** Tasks 4.3 and 4.4 cover the payload key and the `amoeba submit verdict --judge-invocation-id` flag.

### [PASS] Sequencing and test-with pattern

- **Test tasks:** Every implementation task is followed immediately by its test task. The pairs are 2.1/2.2, 2.3/2.4, 3.1/3.2, 4.1/4.2, 4.3/4.4, 4.5/4.6, 4.7/4.8, 4.9/4.10 and 4.11/4.12.
- **Commits:** Each pair is committed together, so no commit holds untested behavior, and commits are spread through the file rather than batched at the end.
- **Dependencies:** There are no cycles. Task 4.11 correctly depends on both 4.10 and 2.4.
- **Field ordering:** Adding `judge_invocation_id` to `VerdictRecord` in 2.1 and to `VerdictInput` only in 4.1 avoids an input field that is accepted but silently dropped.

### [PASS] Cross-file ownership and public exports are explicit

The remaining criteria are assigned to file 2 and the file says so: checks and work records, the parser and ingest, listings, docs, and the end-to-end proof. The public-API export update that this file's new types need is Task 5.7 in `-2.md`. No load-test or CI task is needed, because the LLD states no NFR.

### [NOTE] Conditional 105 and 106 handling relies on Task 1.1 notes

Tasks 4.3 and 4.9 branch on whether 105 and 106 are merged, using the Task 1.1 notes. The tasks are explicit and Task 6.1 repeats the condition, so this is acceptable. A junior AI could skip reading the notes, so Task 1.1 must actually fill them in before work proceeds.

### [NOTE] `mapping_evidence.py` size risk is flagged but unresolved

`mapping_evidence.py` is at 293 lines and Task 4.1 adds to it. Task 4.1 reports any overrun to the PM instead of splitting the file, which is reasonable and keeps the task small.

### [NOTE] "Single definition" criteria are asserted, not tested

Task 2.1 requires `check_standing` to be defined in exactly one place, but no test enforces it. This is a minor point. Review is enough here, and Task 3.2 does test the column-name single definition.

### Run Digest

- Response length: 3693 chars
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
- Duration: 32.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
