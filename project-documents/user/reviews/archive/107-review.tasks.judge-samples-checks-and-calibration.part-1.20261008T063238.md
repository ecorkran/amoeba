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
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: b1a8e2fee89c1042152dd6190c726d0b3ee3f4dd
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 53.1
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "File-1 success criteria are traced to implementation and test tasks"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:57-406"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pairing, and commit cadence are sound"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:28"
  - id: F003
    severity: concern
    category: testing
    summary: "D3 exclusion can silently drop review verdicts through SQL NULL semantics, and no test pins it"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:344-370"
  - id: F004
    severity: concern
    category: scope
    summary: "`sql_evidence.py` receives statements from five tasks with no size check, and Task 4.5 names an ambiguous location"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:200"
  - id: F005
    severity: concern
    category: dependencies
    summary: "Task 1.1 does not say what to do if slice 105 is absent, though Section 6 depends on it"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:46"
  - id: F006
    severity: note
    category: prompt-hygiene
    summary: "Task 1.1 puts a concrete migration number next to a value the agent must read"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:47"
  - id: F007
    severity: note
    category: task-sizing
    summary: "Task 2.1 mixes check vocabularies with a verdict-model change"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:66"
  - id: F008
    severity: note
    category: task-clarity
    summary: "Several test tasks omit a \"Files to Modify\" line"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:251-265"
  - id: F009
    severity: note
    category: nfr
    summary: "No load-test or CI-gating task is required"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:289-320"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] File-1 success criteria are traced to implementation and test tasks

Each criterion in this file's scope has a task and a test:
- **Three samples stay three records, in order:** 4.7 and 4.8.
- **D2 on both paths, with error precedence:** 4.5 and 4.6.
- **D3 exclusion, with the 104/106 tests unchanged:** 4.9 and 4.10.
- **Calibration:** 2.3 and 2.4 test the pure function on built records with no store. 4.11 and 4.12 add the store and read-only cases.
- **Every standing row and the vocabularies:** 2.1 and 2.2.
- **Upgrade path with `judge_invocation_id` NULL:** 3.1 and 3.2.
- **Payload key through inbox and `amoeba submit`:** 4.3 and 4.4.

I found no scope creep. Every task traces to a slice design section or decision.

### [PASS] Sequencing, test-with pairing, and commit cadence are sound

- **Test-with pattern:** each implementation task is followed immediately by its test task, and the pair is committed together.
- **Commits:** they are spread across Sections 2–4 and none is batched at the end.
- **Dependencies:** they are acyclic.
- **Pure rules first:** vocabularies and the calibration function come before the migration, so they have no store dependency.
- **Task 2.1 field ordering:** adding the `judge_invocation_id` field there is explained by Task 2.3's need for it.

### [CONCERN] D3 exclusion can silently drop review verdicts through SQL NULL semantics, and no test pins it

Task 4.9 says "Rows with a different id, or none, remain candidates." The natural implementation is `judge_invocation_id != ?`, and in SQLite that evaluates to NULL for rows with no id. Those rows would then be excluded from the previous round. Task 4.9 does not warn about this, and Task 4.10 does not catch it:
- The cross-type case differs by review type, which the task itself says is "no other mechanism needed".
- The `j0` case uses another invocation id, not a NULL one.
- The regression case uses review verdicts as the target, so the exclusion never applies.

Add a Task 4.9 step to compare NULL-safely (`IS NOT`, or `IS NULL OR !=`). Add a Task 4.10 case where a judge sample and an id-less verdict share node, review type and `source_document`. The id-less verdict must still be the candidate previous round. This should match the LLD only if judge review types never overlap with ordinary ones, so confirm that expectation.

### [CONCERN] `sql_evidence.py` receives statements from five tasks with no size check, and Task 4.5 names an ambiguous location

Task 4.1 states "`sql_evidence.py` (204) needs no split". Tasks 3.1 (shared provenance constant), 4.1, 4.5, 4.7, 4.9 and 4.11 each add statements to it. Task 4.5 says "`sql_evidence.py` (or the new module)", but the only new SQL module planned is `sql_checks.py`, which is for the check and work-record tables. Task 4.1's conditional split rule covers `mapping_evidence.py` only. `verdicts.py` also gains the filter, D3 and `calibration()` with no size check.

Add a line-count check to Task 4.11's success criteria for `sql_evidence.py` and `verdicts.py`. Say where overflow statements go, for example a `sql_judge.py`. Remove the "(or the new module)" ambiguity from Task 4.5.

### [CONCERN] Task 1.1 does not say what to do if slice 105 is absent, though Section 6 depends on it

Task 1.1 records whether `src/amoeba/upstream/squadron/review.py` exists. It only adjusts migration numbering and tells the PM when 106 is unmerged. Task 4.3 defers `verdict_to_payload` to "Task 6.1" if 105 is absent. The slice design lists 105 as a prerequisite (`to_verdict_input`, `ingest review`). If 105 is unmerged, Section 6 cannot be done and the end-to-end criterion cannot be met. Add an explicit instruction: either proceed through Section 5 and stop before Section 6 until 105 merges, or ask the PM now. Verify that Task 6.1 in file 2 actually owns the deferred `verdict_to_payload` work.

### [NOTE] Task 1.1 puts a concrete migration number next to a value the agent must read

The step says "the highest is `005`... takes `006`... `EXPECTED_SCHEMA_VERSION` becomes 6". Task 3.1 hard-codes the file name `007_...`. The prose does say to use the actual number, but a literal next to a retrieval instruction is the pattern the project's CLAUDE.md warns about. Phrase it as "max(existing)+1, taken from the directory listing", and have Task 1.1 write the number into the task notes so Task 3.1 reads it from there. Also say where "the Task 1.1 notes" live.

### [NOTE] Task 2.1 mixes check vocabularies with a verdict-model change

Adding `judge_invocation_id` to `VerdictInput` and `VerdictRecord` is a judge-sample change inside a "check vocabularies" task. The task justifies it by sequencing, and Task 2.2 tests it, so the pairing holds. Effort 2 is on the small side for four distinct edits, but the work is mechanical. No action is needed. Splitting the verdict-model field into its own step would make the commit message clearer.

### [NOTE] Several test tasks omit a "Files to Modify" line

Tasks 4.4, 4.6, 4.8, 4.10 and 4.12 have no file list. Task 4.1's list omits the conditional `mapping_observations.py`. Task 4.4 names the style to follow but not the test files to touch. A junior agent can infer them, but listing them would cut exploration.

### [NOTE] No load-test or CI-gating task is required

The slice design's Success Criteria state no performance or throughput NFR. The only related remark is that judge samples per project are few, which is not a requirement. A `tests/load/` task and a CI-wiring task are therefore not required.

### Run Digest

- Response length: 6910 chars
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
- Duration: 53.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
