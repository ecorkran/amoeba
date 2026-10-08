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
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 386ddd77206e1a3cc9dc4886b38036f5daa528bc
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 184.8
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria in file 1's scope are covered"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:34-404"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:28"
  - id: F003
    severity: note
    category: test-coverage
    summary: "Task 2.4 does not pin distinct-invocation counting or the numeric score aggregation"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:130-137"
  - id: F004
    severity: note
    category: test-quality
    summary: "Task 4.10's cross-type assertion is not specified"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:362"
  - id: F005
    severity: note
    category: task-clarity
    summary: "Some size-limit and file-listing details are left to the implementer"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:198"
  - id: F006
    severity: note
    category: sequencing
    summary: "`verdict_to_payload` is split from the other judge-sample wiring"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:30"
---

# Review: tasks — slice 107

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria in file 1's scope are covered

Each LLD criterion that file 1 owns maps to a task and a matching test task:
- Three samples stay three records, and the `judge_invocation_id` read-back: Tasks 4.1–4.2, 4.7–4.8.
- D2 on both the direct and inbox paths, with review verdicts unaffected: Tasks 4.5–4.6.
- D3 exclusion: Tasks 4.9–4.10.
- D4 `calibration`, pure (2.3–2.4) and store-level, including read-only (4.11–4.12).
- `check_standing` and every standing row: Tasks 2.1–2.2.
- Upgrade path with `NULL` ids: Tasks 3.1–3.2.
- The inbox payload key and the `amoeba submit` flag: Tasks 4.3–4.4.

File 2 picks up the remaining criteria:
- Checks, work records, exports and the metrology test: Section 5.
- The parser and ingest: Section 6.
- Listings: Section 7.
- The demo script, end-to-end test and docs: Section 8.

I found no unowned criterion. The LLD restates no NFR, so no `tests/load/` task or CI gating task is required.

### [PASS] Sequencing and test-with pattern

- **Dependencies:** they run in order with no cycles. Task 2.1 puts `judge_invocation_id` on the models before 2.3 reads it. Task 4.1 builds on that. Task 4.11 correctly depends on both 4.10 and 2.4.
- **Test-with:** every implementation task is followed immediately by its test task, and the commit-with relationships are explicit.
- **Commits:** nine checkpoints fall between Tasks 2.2 and 4.12, so none are batched at the end.
- **Scope:** I found no scope creep. Everything traces to LLD D1–D4 or its Technical Requirements.

### [NOTE] Task 2.4 does not pin distinct-invocation counting or the numeric score aggregation

Task 2.4 only has an unscored case (`None` scores) and a single-invocation case. Two D4 behaviours that the LLD says must be tested "exactly" have no case:
- **`invocations` counting distinct ids:** nothing covers a row where `samples` exceeds `invocations`, for example two samples of one invocation from the same model, or two invocations in one row.
- **`score_min`, `score_mean` and `score_max` with several scored samples:** nothing checks hand-computed values, such as the plain arithmetic mean staying unrounded, or a mix of scored and unscored samples.

Add both cases to 2.4. Without them a wrong implementation (counting samples as invocations, or rounding the mean) can pass.

### [NOTE] Task 4.10's cross-type assertion is not specified

The step "assert the actual behavior" leaves the expected outcome to the implementer, which invites a test that restates whatever the code does. The LLD says judge review types never match ordinary ones. State the expected result, for example that a review verdict with a different `review_type` is not a candidate previous round, and that `finding_changes` for the judge sample has no previous round because of it.

### [NOTE] Some size-limit and file-listing details are left to the implementer

- **Task 4.1:** `mapping_evidence.py` is at 293 lines, so adding the column will probably push it past ~300. "If either file would exceed ~300 lines, move the new code into a new module" leaves the choice of module open. Name the target module or say which code moves.
- **Tasks 4.4, 4.6, 4.8, 4.10 and 4.12:** they have no "Files to Modify/Create" line. Task 4.4 also doesn't name the test files it extends.
- **Task 1.1:** it states "the highest is `005`… takes `006`… version 6" next to the instruction to read those values from the repo. The conditional is clearly framed, but under the project's hallucination-trap rule it is safer to say only "highest existing + 1" and drop the literal numbers.

### [NOTE] `verdict_to_payload` is split from the other judge-sample wiring

The LLD's development step 3 groups `verdict_to_payload` with the other judge-sample work. The tasks move it to Task 6.1 in file 2 because it depends on slice 105. This is reasonable and file 2 documents the reordering. File 1's Context Summary should state that judge-sample work in Section 4 doesn't include `verdict_to_payload`, so a reader doesn't take Section 4 as complete for the payload round trip.

### Run Digest

- Response length: 5264 chars
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
- Duration: 184.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
