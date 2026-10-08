---
docType: review
layer: project
reviewType: tasks
slice: judge-samples-checks-and-calibration
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 4fd958020c7e37572dac8c6350dd73247072076d
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
durationSeconds: 35.7
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Judge-sample, D2, D3, filter, and calibration criteria all have implementation and test tasks"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:293-296"
  - id: F002
    severity: pass
    category: coverage
    summary: "Criteria not owned by this file are explicitly handed off to file 2"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:32"
  - id: F003
    severity: pass
    category: nfr
    summary: "No load test or CI gate is required"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:19"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Task 4.6's empty-id inbox case contradicts Tasks 4.3 and 4.4"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:298"
  - id: F005
    severity: concern
    category: error-handling
    summary: "An intermediate commit accepts `judge_invocation_id` and silently discards it"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:68"
  - id: F006
    severity: concern
    category: sequencing
    summary: "Task 4.3 may break 105's `verdict_to_payload` tests if 105 is already merged"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:241-245"
  - id: F007
    severity: note
    category: documentation
    summary: "Task 1.1 asks for \"notes\" with no stated location"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:48-49"
  - id: F008
    severity: note
    category: task-sizing
    summary: "Task 4.5 and Task 4.9 are on the larger side but acceptable"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:268-355"
  - id: F009
    severity: note
    category: commits
    summary: "Commit cadence and test-with pattern are respected"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:28"
  - id: F010
    severity: note
    category: sequencing
    summary: "Dependencies are acyclic"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Judge-sample, D2, D3, filter, and calibration criteria all have implementation and test tasks

- The three-separate-records criterion maps to Tasks 4.1, 4.2, 4.7 and 4.8.
- D2 maps to Tasks 4.5 and 4.6.
- D3 maps to Tasks 4.9 and 4.10.
- The calibration cases map to Tasks 2.3, 2.4, 4.11 and 4.12. Task 2.4 tests the pure function on built records with no store, as the criterion requires.
- The `check_standing` rows map to Tasks 2.1 and 2.2, and the upgrade criterion maps to Tasks 3.1 and 3.2.

### [PASS] Criteria not owned by this file are explicitly handed off to file 2

- File 1's Context Summary lists the criteria it does not own.
- A grep of file 2 shows the public-API export (Task 5.7), the metrology-reference test (Task 8.x), the writer-guard allow-list, and the `verdict_to_payload` update (Task 6.1) all exist there.
- No gap was found.

### [PASS] No load test or CI gate is required

The slice states no NFR, and the task file says so explicitly. No `tests/load/` task or CI wiring task is needed.

### [CONCERN] Task 4.6's empty-id inbox case contradicts Tasks 4.3 and 4.4

- Tasks 4.3 and 4.4 say payload validation refuses an empty-string `judge_invocation_id`, so the submission is quarantined as an invalid payload.
- Task 4.6 then expects the same input to be `rejected` on the inbox path, by the `_verdict_rejection` branch added in Task 4.5.
- Payload validation runs first, so the Task 4.5 branch cannot be reached from the inbox. The Task 4.6 assertion would fail, or a junior AI would weaken it to make it pass.
- Decide which behaviour applies. Either:
  - Keep the Task 4.5 empty-id branch for the direct path only and have Task 4.6 assert quarantine on the inbox path, or
  - Drop payload-level validation.
- The LLD only specifies payload validation. The direct-path `ValueError` for an empty id is a small addition the LLD does not mention. Note that in the task.

### [CONCERN] An intermediate commit accepts `judge_invocation_id` and silently discards it

- Task 2.1 adds `judge_invocation_id` to `VerdictInput` and `VerdictRecord`, and it is committed with Task 2.2.
- Task 4.1 does not persist the field until later, so every commit in between has a store that accepts the id and drops it.
- That conflicts with the project rule against silent fallbacks. It also makes Task 2.1 mix check vocabularies with a verdict-model change.
- Move the model field into Task 4.1, so the field and its persistence land in one commit.
- Task 2.3 and Task 2.4 only need the field to exist on `VerdictRecord`. If it stays in Task 2.1, say explicitly that the id is not yet persisted until Task 4.1.

### [CONCERN] Task 4.3 may break 105's `verdict_to_payload` tests if 105 is already merged

- Task 4.3 adds the payload field and key but deliberately leaves `verdict_to_payload` alone until Task 6.1.
- If 105 is merged, its round-trip test and any payload-field pinning test may require `verdict_to_payload` to emit every `VerdictPayload` field. Task 4.4 extends such a pinning test, so the suite could fail between Task 4.4 and Task 6.1.
- Add a step in Task 4.4 to run 105's tests, and either update `verdict_to_payload` earlier or state which assertions are expected to stay green.
- The step-by-step success criteria say only that `ruff` and `pyright` are clean, with no full-suite run.

### [NOTE] Task 1.1 asks for "notes" with no stated location

Task 1.1 records the migration number and merge state "in the Task 1.1 notes", but no notes file or section is named. Later tasks depend on the recorded N. Name the place, for example a section appended to this task file. The task already says "no commit needed", so persistence matters.

### [NOTE] Task 4.5 and Task 4.9 are on the larger side but acceptable

Both touch `_verdict_writer.py`, `sql_evidence.py` and `verdicts.py`, which are near the size limit. Each is scoped to one rule, with a test task right after. Task 4.9 depends on whether 106 is merged, but it handles both cases. Task 4.1 already tells the junior to report line counts over ~300.

### [NOTE] Commit cadence and test-with pattern are respected

Every implementation task is followed by its test task and committed together, at roughly 2–3 tasks per commit across Sections 2–4. Commits are distributed through the file, not batched at the end.

### [NOTE] Dependencies are acyclic

- Section 2 depends only on Task 1.1, and Section 3 on Task 1.1.
- Section 4 builds linearly from 3.2.
- Task 4.11 correctly depends on both 4.10 and 2.4.
- No scope creep was found; each task traces to an LLD decision or criterion.

### Run Digest

- Response length: 6055 chars
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
- Duration: 35.7 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
