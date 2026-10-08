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
reviewedSha: c739f1e105e628b788302c45ea34caf6ac5a8f2b
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 32.0
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are traced to tasks"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:20"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Tasks 8.3 and 8.4 conflict on how the end-to-end test is structured"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:412-445"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 8.3 is overloaded"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:412-427"
  - id: F004
    severity: concern
    category: scope
    summary: "Task 6.1 lists a test file to modify but says no tests are written there"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:168-173"
  - id: F005
    severity: concern
    category: sequencing
    summary: "Metrology-test widening is split across Tasks 5.7 and 8.7"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:147,496"
  - id: F006
    severity: note
    category: sequencing
    summary: "Task 5.1 is sequenced after Task 4.12 without a real dependency"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:28"
  - id: F007
    severity: note
    category: maintainability
    summary: "Task 8.1 cites a fragile line number"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:380"
  - id: F008
    severity: note
    category: coverage
    summary: "The LLD walkthrough is inconsistent with its own commands"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:356-374"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are traced to tasks

Checks, work records, the `--judge-invocation-id` ingest option, the three new listings, and the verdicts column and filter are all covered by tasks.
- **Checks (5.1–5.4):** every `CheckStanding` row, each rejection, replay, and the other-project case.
- **Work records (5.5–5.6):** content handling, rejections, and the `kind` filter.
- **Ingest (6.5–6.6):** `--judge-invocation-id`.
- **Listings (7.x):** `calibration`, `checks`, `work-records`, and the verdicts column and filter, each tested running and stopped.
- **Supporting items:** both fixtures (6.3–6.4), the demo script and writer guard (8.1–8.2), docs and `CHANGELOG` (8.5–8.6), the public-API export (5.7), and the metrology test (5.7, 8.7).

Task 8.7 re-checks file 1's items (judge samples, D2, D3, the filter, `calibration`, and the migration) against the LLD. I did not read file 1, so I could not confirm that those items are covered there.

### [CONCERN] Tasks 8.3 and 8.4 conflict on how the end-to-end test is structured

- **Process state:** Task 8.3 says its test passes "with the process left running (Task 8.4 extends it)". Task 8.4 asks for "a second test function reusing Task 8.3's seeded-instance helper".
- **Captured output:** Task 8.3 says to capture each listing's `--json` output "for Task 8.4". A second pytest function cannot see the first one's captured output or its running process.
- **Teardown:** Task 8.4 requires teardown with no leftover processes, which contradicts leaving the process running.
- **Structure:** 8.3 plus 8.4 is a single test that was split into two tasks for size.

Pick one structure.
- **Preferred:** a module-scoped fixture or helper that builds the scenario and returns the pre-crash captures, with 8.3 asserting on it. Task 8.4 would then do its own setup, capture, crash and restart, and compare, inside one test.
- **Alternative:** merge them into one task.

### [CONCERN] Task 8.3 is overloaded

Task 8.3 is rated effort 3 but combines several jobs.
- Building the project and nodes with two seeding scripts.
- Mixed ingest and submit.
- Polling for applied submissions.
- Assertions across five listings.
- Capturing output for reuse.
- A shared helper.

Splitting it would help. One task could build the shared helper plus the seeding and wait; a second could hold the assertions. Even after the 8.3/8.4 fix, the helper and the setup flow are worth their own checkpoint. It also has no commit of its own: it says "Commit with Task 8.4".

### [CONCERN] Task 6.1 lists a test file to modify but says no tests are written there

Step 3 says "No tests here; Task 6.2 owns them". Yet "Files to Modify" includes 105's round-trip test (`tests/store/test_verdict_to_payload.py`). Remove that entry from 6.1, or state that only fixing existing tests broken by the signature change is allowed. Otherwise a junior AI may edit tests in the wrong task, or break the existing 105 tests that the success criteria say must still pass.

### [CONCERN] Metrology-test widening is split across Tasks 5.7 and 8.7

Task 5.7 extends the metrology-reference test to the new store modules. Task 8.7 widens it again to the CLI modules. The LLD only says 104's test "covers the new modules". Make one task do the whole extension, ideally after the last new module exists in Task 7.5, with 8.7 only verifying it. A final-validation task should not be where new test code gets added.

### [NOTE] Task 5.1 is sequenced after Task 4.12 without a real dependency

`mapping_checks.py` only needs the models and the migration (Sections 1–3). Depending on Task 4.12 (calibration tests) serializes work that could proceed independently. It is harmless, but it does give Section 5 a longer critical path than it needs.

### [NOTE] Task 8.1 cites a fragile line number

"The set asserted near line 290 in `tests/test_writer_guard.py`" will drift. Describe it by symbol, `PERMITTED_SCRIPTS` and the test that asserts its contents.

### [NOTE] The LLD walkthrough is inconsistent with its own commands

Step 2 submits samples for `glm-5.3` and `kimi-k3`. Step 3 expects "the minimax row" with score 98. Task 8.7 already says to compare results with the LLD and report differences, which will surface this. The PM should know about it before Phase 6, because the models in the fixture and in the commands need to match.

### Run Digest

- Response length: 5682 chars
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
- Duration: 32.0 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
