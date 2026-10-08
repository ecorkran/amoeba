---
docType: review
layer: project
reviewType: tasks
slice: judge-samples-checks-and-calibration
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 65827d9a3d54d0bc596cc25d583506764f8625a5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
durationSeconds: 100.1
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Tasks 2.3 and 2.4 depend on a field that Task 4.1 adds later"
    location: "src/amoeba/store/evidence_models.py:173"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Sections 7 and 8 are blocked on slice 105 through an artificial dependency"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:153"
  - id: F003
    severity: concern
    category: process
    summary: "Task 6.4 puts a hardcoded value next to a retrieved one"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:218"
  - id: F004
    severity: concern
    category: testing
    summary: "Task 8.2 doesn't wait for submissions to be applied before `kill -9`"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:396"
  - id: F005
    severity: concern
    category: task-clarity
    summary: "Task 6.1 doesn't name the `verdict_to_payload` module"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:170"
  - id: F006
    severity: note
    category: testing
    summary: "`scripts/demo_checks.py` has no dedicated test"
    location: "scripts/demo_checks.py"
  - id: F007
    severity: note
    category: testing
    summary: "Listings are tested only with the process stopped"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:287"
  - id: F008
    severity: note
    category: nfr
    summary: "No load-test or CI-gating task is needed"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md"
  - id: F009
    severity: pass
    category: coverage
    summary: "Every slice success criterion maps to a task"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md"
  - id: F010
    severity: pass
    category: structure
    summary: "Test-with pattern and commit cadence are sound"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:28"
---

# Review: tasks — slice 107

**Verdict:** FAIL
**Model:** claude-sonnet-5-5

## Findings

### [FAIL] Tasks 2.3 and 2.4 depend on a field that Task 4.1 adds later

Task 2.3 requires `summarize_judge_samples` to raise `ValueError` for a `VerdictRecord` with no `judge_invocation_id`. Task 2.4 builds `VerdictRecord`s that carry the id. `VerdictRecord` (line 173, a subclass of `VerdictInput`) has no `judge_invocation_id` today. A grep of `src/` finds no occurrence of the name. Task 4.1 adds the field, and it comes two sections later. Under pyright strict, 2.3 and 2.4 can't be finished or committed as written. The slice's "Development Approach" step 1 says this work "depends on nothing", which is wrong.
Fix: move the `judge_invocation_id` field on `VerdictInput` and `VerdictRecord` (the model part of Task 4.1) ahead of 2.3. Alternatively, move Section 2.3/2.4 after Task 4.2.

### [CONCERN] Sections 7 and 8 are blocked on slice 105 through an artificial dependency

Section 6 stops and asks the PM if 105 is unmerged. Task 7.1 depends on Task 6.6, so the listings (7.1–7.6) wait on 105 too. The listings need only the store, which is done after Task 5.7. Only 6.x and the end-to-end test in 8.2 need 105's parser and `ingest review`. Make 7.1 depend on 5.7 and move the 105 gate to Section 6 and Task 8.2. Then a slipped 105 doesn't stall unrelated work.

### [CONCERN] Task 6.4 puts a hardcoded value next to a retrieved one

Task 6.4 gives "score 98.0" as the expected value for the 302 file, then says to assert what the file actually says. This is the hallucination trap the project CLAUDE.md warns about: a model that can't read the value may reach for 98.0. Drop the number and tell the implementer to read the score from the fixture. The same applies to Task 1.1's "highest is `005`, so this slice takes `006`" (file 1, line 47).

### [CONCERN] Task 8.2 doesn't wait for submissions to be applied before `kill -9`

The test submits samples and then kills the process. Inbox application is asynchronous, so the test can kill the process before the submissions are applied or rejected. That makes it flaky and weakens the "nothing applied twice" check. Add an explicit step to poll `inspect submissions` until all are terminal before the kill. At 4 effort the task is also large; it could split into scenario setup and post-crash assertions.

### [CONCERN] Task 6.1 doesn't name the `verdict_to_payload` module

"`review.py` (and its payload module)" doesn't tell a junior AI where `verdict_to_payload` lives. That function comes from 105, which may not be merged. Task 1.1 should record the location, as it already does for `review.py`. Task 6.1 should then reference that note.

### [NOTE] `scripts/demo_checks.py` has no dedicated test

Task 8.1 checks the script only by hand ("prints exactly one node id") and through the writer-guard test. Task 8.2 covers it indirectly. This is acceptable, but a small test of stdout and re-run idempotence would match the test-with pattern.

### [NOTE] Listings are tested only with the process stopped

The success criterion says the `inspect` listings work with the process "running and stopped". Tasks 7.2, 7.4 and 7.6 test only the stopped case. This is mostly covered by the read-only handle, but Task 8.2 could also assert one listing while the process is running.

### [NOTE] No load-test or CI-gating task is needed

The slice restates no performance NFR, so no `tests/load/` task or CI wiring task is required.

### [PASS] Every slice success criterion maps to a task

- **Judge samples:** the three-samples-stay-separate criterion is covered by 4.2 and 4.8. D2 on both paths is 4.5/4.6. D3 is 4.9/4.10.
- **Calibration:** D4 is 2.3/2.4 (pure function) and 4.11/4.12 (store).
- **Checks and work records:** every standing row, the five rejections, and replay with WARNING are in 5.3–5.6. The work-record criteria are in 5.5/5.6.
- **Migration:** the upgrade path is 3.1/3.2.
- **Parser and ingest:** these are in 6.x.
- **Listings:** the four listings are in 7.x.
- **Proof and docs:** the writer guard and `demo_checks` are 8.1, the end-to-end scenario is 8.2, and the docs and CHANGELOG are 8.3/8.4.
- **Other technical requirements:** the public-API pin and the metrology test are 5.7.
- **Fixtures and README:** these are 6.3.

No task is scope creep.

### [PASS] Test-with pattern and commit cadence are sound

Every implementation task is followed immediately by its test task, and commits are paired explicitly ("Commit with Task N.M"). Commits are spread across all eight sections rather than batched at the end. No task merges the branch, and the merge is deferred to Phase 7, as the project Git rules require.

### Run Digest

- Response length: 5914 chars
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
- Duration: 100.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
