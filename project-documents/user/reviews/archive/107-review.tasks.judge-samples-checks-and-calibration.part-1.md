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
reviewedSha: c739f1e105e628b788302c45ea34caf6ac5a8f2b
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 38.2
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Judge-sample, D2, D3, D4 and migration criteria each have an implementation task and a test task"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md"
  - id: F002
    severity: concern
    category: hallucination-trap
    summary: "Hardcoded migration number and schema version sit next to a value Task 1.1 must retrieve"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:47"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 4.3 branches on external merge state, and it ends in an unwritten test"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:241"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "Task 4.3 says to confirm the payload field-name test, but 4.4 has no step for it"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:240"
  - id: F005
    severity: concern
    category: task-sizing
    summary: "Task 4.1 bundles several concerns, including a conditional file split"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:192-207"
  - id: F006
    severity: note
    category: sequencing
    summary: "Task 3.1 depends on Task 2.4 without need"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:153"
  - id: F007
    severity: note
    category: documentation
    summary: "Minor task-file inconsistencies"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:145"
  - id: F008
    severity: note
    category: nfr
    summary: "No load-test or CI-gating task is required"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md"
  - id: F009
    severity: note
    category: coverage
    summary: "Criteria that depend on Sections 5–8 in `-2.md`"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Judge-sample, D2, D3, D4 and migration criteria each have an implementation task and a test task

- **Three samples stay three records:** Tasks 4.7 and 4.8 cover this.
- **D2:** Tasks 4.5 and 4.6 cover both the direct and inbox paths and the `NodeNotFoundError` precedence.
- **D3:** Tasks 4.9 and 4.10 cover the exclusion, the earlier-invocation case and the cross-type case.
- **Calibration:** Tasks 2.3 and 2.4 cover the pure function on built records. Tasks 4.11 and 4.12 cover the store-level report, including a read-only handle.
- **Check standing:** Tasks 2.1 and 2.2 cover the standing table.
- **Upgrade path:** Tasks 3.1 and 3.2 cover the previous-version upgrade, with every verdict's `judge_invocation_id` left `NULL`.
- **Pattern and cadence:** Implementation tasks are followed immediately by their tests. Commits are spread across sections: 2.1/2.2, 2.3/2.4, 3.1/3.2, 4.1/4.2, 4.3/4.4, 4.5/4.6, 4.7/4.8, 4.9/4.10 and 4.11/4.12.

### [CONCERN] Hardcoded migration number and schema version sit next to a value Task 1.1 must retrieve

- **Retrieval step:** Task 1.1 tells the implementer to read the highest migration file and `EXPECTED_SCHEMA_VERSION` from disk.
- **Hardcoded values:** The same step states "the highest is `005`... `006`... becomes 6". Task 3.1 names the file `007_...`, and the Context Summary also says "007 (or 006...)".
- **Risk:** The project's CLAUDE.md warns against this pattern. If the retrieval returns nothing or is misread, the implementer is likely to use the nearest literal.
- **Fix:** Phrase the rule as `max(existing) + 1`, with no literal example numbers. In Task 3.1, say "the number recorded in Task 1.1" and give the filename as `NNN_judge_samples_checks_and_work.sql`.

### [CONCERN] Task 4.3 branches on external merge state, and it ends in an unwritten test

- **Conditional step:** The `verdict_to_payload` step depends on whether 105 is merged. If it is, add the key and a round-trip case in 4.3. If not, Task 6.1 does it.
- **Cross-file dependency:** The branch depends on a task in the other file, so a junior implementer cannot resolve it from this file alone.
- **Missing test task:** The round-trip test is added inside the implementation task (4.3). Task 4.4 does not list it, which breaks the test-with pattern.
- **Fix:** Add the `verdict_to_payload` step and its test to 4.4's step list under the "if 105 merged" condition, and state in Task 1.1 that the outcome is recorded for 4.3 and 6.1 to use. Alternatively, move the step unconditionally into Section 6.

### [CONCERN] Task 4.3 says to confirm the payload field-name test, but 4.4 has no step for it

- **Gap:** Task 4.3 asks the implementer to confirm that the existing test pinning payload names covers the new key, and to extend it if not. That is test work inside an implementation task, and 4.4 has no matching step.
- **Fix:** Move the step to 4.4. Also assert there that `verdict_from_payload` yields `None` when the key is absent.

### [CONCERN] Task 4.1 bundles several concerns, including a conditional file split

- **Scope:** Task 4.1 covers the replay comparison, the SQL column and insert, parameters and mapping, the empty-string refusal, a possible `mapping_evidence.py` split with import updates in two modules, and the harness change.
- **Effort estimate:** Effort 3 looks low, since the conditional extraction touches several modules.
- **Test gap:** The empty-string `ValueError` branch is part of this task, and nothing proves it until 4.2.
- **Fix:** Split the optional `mapping_observations.py` extraction into its own refactor task. That task would do a pure move with existing tests green and commit separately as `refactor:`. Also give the "if above ~310 lines" threshold a deterministic form, such as "run `wc -l` after the edit".

### [NOTE] Task 3.1 depends on Task 2.4 without need

- The migration and `sql_checks.py` do not use the calibration code.
- The dependency only serializes the work. It is harmless, but it is not a real dependency.

### [NOTE] Minor task-file inconsistencies

- **File list:** Task 2.4 lists `tests/store/test_calibration.py` under "Files to Modify", though the file is created in that task.
- **Missing field:** Tasks 4.4, 4.6, 4.8, 4.10 and 4.12 have no "Files" field.
- **Task 1.1 notes:** Task 1.1 asks the implementer to "record in the Task 1.1 notes", but the file has no notes area. Say where the notes go, such as an appended `## Task 1.1 notes` section, since Tasks 3.1, 4.3 and 4.9 consume the values.
- **Vague builder step:** Task 4.7's "prefer one statement builder" is advisory, so it is not verifiable as a success criterion. State the expected outcome instead, such as "no third `SELECT_VERDICTS_*` constant added".

### [NOTE] No load-test or CI-gating task is required

- The slice restates no performance NFR, so the load-test and CI-wiring rules do not apply.
- The only quantitative statement is that judge samples per project are few, which is a design assumption and not an NFR.

### [NOTE] Criteria that depend on Sections 5–8 in `-2.md`

- The `-2.md` review should confirm tasks for the following criteria:
  - `record_check` and `record_work` preconditions and first-wins behaviour.
  - Ingest `--judge-invocation-id` and the judge fixtures.
  - The four listings and the `verdicts` CLI filter.
  - `scripts/demo_checks.py`, with the writer-guard allow-list.
  - The pinned public-API export set, which here gains `calibration` and `CalibrationRow`.
  - The no-metrology-reference test covering the new modules.
  - The end-to-end CLI test, docs and `CHANGELOG`.

### Run Digest

- Response length: 7107 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 38.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
