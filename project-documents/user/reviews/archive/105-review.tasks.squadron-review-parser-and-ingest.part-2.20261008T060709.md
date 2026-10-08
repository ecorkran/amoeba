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
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 83153c08b9faacf705a3f27a258826318111750f
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
durationSeconds: 55.4
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Task 7.2 targets a file that does not import the four helpers"
    location: "tests/store/test_finding_changes.py:6-14"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 7.5 does not depend on Tasks 7.1–7.3"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:139-143"
  - id: F003
    severity: concern
    category: commit-cadence
    summary: "Task 8.1 has no commit checkpoint and no test"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:162-175"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Tasks 8.2 and 8.3 are large for one junior AI task"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:179-221"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "\"No `Store` import in `ingest.py`\" is checked by hand, not enforced"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:193-196"
  - id: F006
    severity: note
    category: verification
    summary: "Task 9.3 runs `tests/load`, which exists"
    location: "tests/load"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for Sections 6–9"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:354-392"
  - id: F008
    severity: pass
    category: commit-cadence
    summary: "Commit distribution and test-with pattern"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md"
---

# Review: tasks — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 7.2 targets a file that does not import the four helpers

Task 7.2 says to "apply the same replacement" as Task 7.1. It also requires "No import of the four removed helpers". But `test_finding_changes.py` imports only `ROUND_*` paths from `review_fixtures` and builds verdicts through `captured_verdict` from `evidence_harness` (lines 153–175). A grep of `tests/` for `review_findings`, `read_frontmatter`, `CapturedFinding` and `has_provider_failure_heading` finds `review_fixtures.py`, `test_demo_evidence_payloads.py`, `test_finding_identity.py` and `evidence_harness.py`. It does not find `test_finding_changes.py`.

So the success criterion is already true, and the task has nothing to change. The real migration for this file happens in Task 7.3. A junior AI could invent edits to satisfy the task. Fold 7.2 into 7.3. Alternatively, reframe it as "run `test_finding_changes.py` after 7.3 and confirm it passes unchanged". Note that the slice design lists this file as a direct user of the old reader, which appears to be inaccurate.

### [CONCERN] Task 7.5 does not depend on Tasks 7.1–7.3

Task 7.5 deletes the old reader from `tests/review_fixtures.py`. It lists only Task 7.4 as a dependency. Tasks 7.1–7.3 are independent of 7.4, so the declared graph lets 7.5 run before the other three users are migrated. Step 1 of the task does check this with a grep, which is a mitigation. The dependency list should still read 7.1, 7.2, 7.3 and 7.4.

### [CONCERN] Task 8.1 has no commit checkpoint and no test

The file's Context Summary says every task not marked "committed with Task N.M" commits on its own. Task 8.1 has no commit criterion and no "committed with 8.3" note. Task 8.2 follows that "committed with" convention. Add a commit line, or state that 8.1 is committed with 8.2 and 8.3. The new member is only exercised by Task 8.3's tests, so the second option fits the test-with pattern better.

### [CONCERN] Tasks 8.2 and 8.3 are large for one junior AI task

Task 8.2 (effort 4) holds a seven-step ordered pipeline, a mutually exclusive argument group, explicit exception branches, and registration. Task 8.3 (effort 3) packs about a dozen scenarios into one module. These include a multi-process fixture (`start_running`, `submit_cli`, `await_condition`, `stop_running`), six failure paths, the success path, D7 and `--id`.

Consider splitting 8.2 into the argument parser and registration, then the `run_ingest` pipeline. Consider splitting 8.3 into a failure-path module and a success-path module. Keep each implementation committed with its tests.

### [CONCERN] "No `Store` import in `ingest.py`" is checked by hand, not enforced

The slice design says ingest opens no store (D6). Task 8.2 states this only as a success-criterion line, and Task 5.5's import-direction test covers `upstream` and `store` only. A later change could add a `Store` import with no test failing. Extend Task 5.5, or add an assertion in Task 8.3, that `cli/ingest.py` does not import `Store`.

### [NOTE] Task 9.3 runs `tests/load`, which exists

`uv run pytest tests/load` is valid because the directory exists. The slice has no NFR, so no new load test and no CI-wiring task is needed. Task 9.3 states this.

### [PASS] Success-criteria coverage for Sections 6–9

Each criterion maps to a task:
- **Payload inverse:** the `verdict_to_payload` round trip is in 6.1 and 6.2.
- **Test migration:** the migration of 104's tests and the deletion of the old reader are in 7.1–7.5.
- **Exit code:** `ExitCode.REVIEW_UNREADABLE = 12` is in 8.1, and 11 is currently the last member.
- **Ingest command:** the command is in 8.2. 8.3 covers the failure paths, the unknown-project refusal, the stamp/argument disagreement, D7 and `--id`.
- **End to end:** running process, double ingest, `kill -9` and standings are in 8.4. The stopped process and unknown project, in both states, are in 8.5. The stdout/file pair and the doubled counts are in 8.6.
- **Docs:** the evidence-contract section, the process-contract entry and the CHANGELOG are in 9.1 and 9.2.
- **Walkthrough:** the walkthrough refresh is in 9.3.

I found no scope creep in Sections 6–9. Dependencies are acyclic.

### [PASS] Commit distribution and test-with pattern

Commits fall after 6.2, each of 7.1–7.5, 8.3, 8.4, 8.5, 8.6, 9.1, 9.2 and 9.3, so they are spread through the work and not batched at the end. Each implementation task (6.1, 8.2) is immediately followed by its test task and committed with it.

### Run Digest

- Response length: 5664 chars
- Response is newline-free: no
- Tool calls made: 9
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 55.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
