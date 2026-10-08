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
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 65827d9a3d54d0bc596cc25d583506764f8625a5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 46.3
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: process
    summary: "Doc tasks 8.3 and 8.4 have no commit checkpoint"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:405-437"
  - id: F002
    severity: concern
    category: task-clarity
    summary: "Task 6.1 does not name the file to edit"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:170"
  - id: F003
    severity: concern
    category: hallucination-trap
    summary: "Task 6.4 puts a hardcoded expected value next to a value the task says to retrieve"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:218"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 8.2 is large and bundles several jobs"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:386-401"
  - id: F005
    severity: note
    category: sequencing
    summary: "Unnecessary serial dependency of Section 6 on Task 5.7"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:158"
  - id: F006
    severity: note
    category: test-coverage
    summary: "Running-process coverage of the listings relies on the end-to-end test"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:287,321,357"
  - id: F007
    severity: note
    category: test-coverage
    summary: "The no-metrology-reference criterion may miss CLI modules"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:141"
  - id: F008
    severity: note
    category: coverage
    summary: "Items assumed to be covered in file 1"
    location: "unverified"
  - id: F009
    severity: pass
    category: coverage
    summary: "Criteria owned by file 2 are covered, and tests follow implementation"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:22-363"
  - id: F010
    severity: pass
    category: coverage
    summary: "Writer guard, demo script, end-to-end proof, and docs are all present"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:365-456"
  - id: F011
    severity: pass
    category: nfr
    summary: "No NFR is restated, so no load-test or CI-gate task is required"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:289-315"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Doc tasks 8.3 and 8.4 have no commit checkpoint

Tasks 8.3 and 8.4 modify four docs (`evidence-contract.md`, `inbox-contract.md`, `store-contract.md`, `CHANGELOG.md`). Neither has a commit step. Only 8.5 commits (line 456), so the doc work would sit uncommitted until final validation. The project rule is at least one commit per task, and the slice design says to "commit after each step" (Implementation Notes, Development Approach). Task 8.1 has no commit step of its own either, though 8.2 commits "with Task 8.1". Add a `docs:` commit step to 8.3 and 8.4.

### [CONCERN] Task 6.1 does not name the file to edit

"Files to Modify" lists `upstream/squadron/review.py (and its payload module)`. `verdict_to_payload` lives in a module the task never names. A junior AI would have to guess or search for it. This task also edits slice 105's code. Task 1.1's check for 105's presence is the only guard against that code being missing. Name the module, or add a step to locate it and stop if it is not found.

### [CONCERN] Task 6.4 puts a hardcoded expected value next to a value the task says to retrieve

The step says to assert "score 98.0 (the LLD walkthrough value; assert what the file actually says...)". This is the pattern the project guidelines warn about: a literal placed beside an instruction to read the value from the source. An AI could write 98.0 without reading the fixture. Reword it to: read the file's `score`, `reviewType`, and verdict, assert those, and report to the PM if they differ from the LLD walkthrough. State the LLD's expected values only in that reporting sentence.

### [CONCERN] Task 8.2 is large and bundles several jobs

Effort is 4. The task builds a subprocess harness, seeds two scripts, ingests and submits several verdicts, kills and restarts the process, then asserts across four listings plus idempotence. A junior AI could fail partway and have trouble finding the cause. Consider splitting it into 8.2a (harness, seed, ingest and submit, assert before the crash) and 8.2b (crash, restart, post-crash assertions). Each half would be a commit checkpoint.

### [NOTE] Unnecessary serial dependency of Section 6 on Task 5.7

Task 6.1 depends on 5.7 (checks API exports). The parser change only needs judge samples from Sections 3–4, so the dependency is not required. It is harmless for a single-agent run. It does stop Sections 5 and 6 from being done in either order.

### [NOTE] Running-process coverage of the listings relies on the end-to-end test

The slice criterion is that `inspect verdicts|calibration|checks|work-records` work with the process running and stopped. Tasks 7.2, 7.4, and 7.6 test only the stopped case. Task 8.2 reads after a restart, so the process is running at that point, which covers the running case for the listings it exercises. Confirm that 8.2 reads all four listings, including `verdicts` with the filter.

### [NOTE] The no-metrology-reference criterion may miss CLI modules

Task 5.7 extends 104's metrology-reference test with the five new store modules. It omits `cli/inspect_checks.py`, which this slice also adds. The slice criterion says "no source module" references the metrology directory. Add that file, and `scripts/demo_checks.py` if the test scans scripts.

### [NOTE] Items assumed to be covered in file 1

These criteria have no tasks in file 2:
- The schema upgrade test.
- The D2 and D3 behaviors.
- `verdicts(judge_invocation_id=...)` ordering.
- `calibration` and `summarize_judge_samples`.
- Empty-string refusal by payload validation.
- Pure `check_standing` tests.

Confirm each has a task in file 1.

### [PASS] Criteria owned by file 2 are covered, and tests follow implementation

- Check standing and rejections: 5.3/5.4 cover each `CheckStanding` row and every rejection.
- Replay and WARNING: 5.3–5.6 cover both checks and work records.
- Work-record content rules: 5.5/5.6.
- Public API test: 5.7.
- `ingest review --judge-invocation-id`: 6.5/6.6.
- Judge fixtures with README entries: 6.3/6.4.
- `inspect` verdict column and filter, `calibration`, `checks`, and `work-records` listings: 7.1–7.6.

Every implementation task is followed by its test task, and the commit lands with the pair. Commits are spread across Sections 5, 6, and 7 rather than batched at the end.

### [PASS] Writer guard, demo script, end-to-end proof, and docs are all present

- Task 8.1 adds `demo_checks.py` and updates the writer-guard allow-list.
- Task 8.2 covers the Integration Requirements scenario, including `kill -9` and the D2 rejection.
- Tasks 8.3 and 8.4 cover all the documentation the slice requires. That includes correcting the stale `inbox-contract.md` line, `RecordSource`, the judge-standing paragraph, and the CHANGELOG.
- Task 8.5 validates against the LLD walkthrough.

I found no scope creep. The conditional stop-and-ask guards (slice 105 missing, `sq` unavailable, fixture path unknown) are appropriate.

### [PASS] No NFR is restated, so no load-test or CI-gate task is required

The slice's success criteria are functional, technical, and integration requirements. None is a performance or throughput NFR, so no `tests/load/` task and no CI wiring task are needed.

### Run Digest

- Response length: 6815 chars
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
- Duration: 46.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
