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
reviewedSha: 386ddd77206e1a3cc9dc4886b38036f5daa528bc
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 56.9
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Slice-105 ordering note names the wrong tasks"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:19"
  - id: F002
    severity: concern
    category: task-scope
    summary: "Task 6.1 includes test work that Task 6.2 repeats"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:166"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "Task 5.4 skips `check(check_id)` and cross-project nodes"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:85-90"
  - id: F004
    severity: concern
    category: risk
    summary: "Task 6.3 can stall on external dependencies"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:192"
  - id: F005
    severity: note
    category: maintainability
    summary: "Task 5.3 hard-codes the current line count of `store.py`"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:73"
  - id: F006
    severity: note
    category: scope
    summary: "Task 5.7 widens the metrology test to CLI modules"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:143"
  - id: F007
    severity: note
    category: commit-checkpoints
    summary: "Task 8.3 and 8.4 split one test file"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:424-425"
  - id: F008
    severity: pass
    category: coverage
    summary: "Coverage of success criteria owned by this file"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md"
  - id: F009
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern, and commit cadence"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md"
  - id: F010
    severity: pass
    category: nfr
    summary: "No NFR, so no load test or CI gating task is required"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Slice-105 ordering note names the wrong tasks

The note says "only Section 6 and Task 8.2 need 105". That does not match the tasks.
- Task 8.2 depends only on Task 8.1 and tests `demo_checks.py`. Nothing in it uses 105.
- Task 8.3 depends on Task 6.6 (the 105 ingest command) and is not named in the note.
- Task 8.3 also ingests the 302 fixture with `ingest review`. Tasks 8.4 and 8.7 depend on 8.3, and the 8.7 walkthrough step 1 uses `ingest review`.

A junior following the fallback "Sections 5 and 7 and Task 8.1 first" could run Task 8.2 and then Task 8.3 without 105. The Section 6 header has the same gap: it says to skip to Section 7 and then Task 8.1, and it never mentions the later 8.x tasks that need 105. Rewrite the note to name Tasks 8.3, 8.4 and 8.7 (the walkthrough) as 105-dependent, and drop 8.2 unless it really needs 105.

### [CONCERN] Task 6.1 includes test work that Task 6.2 repeats

Task 6.1 step 3 extends 105's round-trip test. Task 6.2 step 2 ("Round trip keeps the id…") tests the same round trip. This breaks the implement-then-test split, and 6.1 is left without a commit boundary. Move the round-trip extension into 6.2, or drop the duplicate bullet.

### [CONCERN] Task 5.4 skips `check(check_id)` and cross-project nodes

Task 5.3 adds `check(check_id) -> CheckRecord | None`, but Task 5.4 never tests it. It should cover a found id and an unknown id returning `None`. The "unknown node" rejection also does not test a node that exists in a different project. The LLD precondition is "node exists in the project", so a cross-project case is the one that proves the project check. Add both.

### [CONCERN] Task 6.3 can stall on external dependencies

Task 6.3 needs the Squadron repository path, the `sq` binary, a provider key and a throwaway repo copy. Its stop-and-ask-the-PM rules are correct. The task still blocks Section 6 and Tasks 8.3 and 8.4 on resources the junior may not have. Either add a prerequisite check to Task 1.1 so the PM is asked at the start, or split it into "copy the 302 fixture" and "capture the fresh file". Then 6.4 and 6.6 can proceed on the 302 fixture alone.

### [NOTE] Task 5.3 hard-codes the current line count of `store.py`

"it is 303 now" will be stale if 106 or Section 4 changes `store.py`. Tell the junior to measure it at task start instead.

### [NOTE] Task 5.7 widens the metrology test to CLI modules

The LLD only says 104's test "covers the new modules". Adding the CLI files is a small extension that is arguably within the spirit of that test. It is also listed ahead of the files existing, which the task handles explicitly. No change needed, but the PM should know it goes slightly past the LLD text.

### [NOTE] Task 8.3 and 8.4 split one test file

Task 8.3 ends with the process left running and defers its commit to Task 8.4. This is acceptable because it is one test file, and a commit between them would leave a test that leaks a process. Both tasks have effort 2–3, so the pair is still a reasonable unit.

### [PASS] Coverage of success criteria owned by this file

Each criterion maps to a task:
- Check standing rows, rejections and replay: Tasks 5.3–5.4.
- `record_work` and content rejection: Tasks 5.5–5.6.
- Public API export set and the metrology scan: Task 5.7.
- `ingest review --judge-invocation-id` on the judge fixture: Tasks 6.5–6.6.
- The four listings: Tasks 7.1–7.6.
- The writer-guard allow-list and `demo_checks.py`: Tasks 8.1–8.2.
- Both fixtures with README entries: Task 6.3.
- The end-to-end scenario, including the D2 rejection, the crash and a stopped-process read: Tasks 8.3–8.4.
- Docs and CHANGELOG: Tasks 8.5–8.6.
- Final validation and walkthrough: Task 8.7.

No scope creep found. Every task traces to an LLD item.

### [PASS] Sequencing, test-with pattern, and commit cadence

There are no circular dependencies. Every implementation task is followed immediately by its test task (5.1→5.2, 5.3→5.4, 5.5→5.6, 6.1→6.2, 6.5→6.6, 7.1→7.2, 7.3→7.4, 7.5→7.6, 8.1→8.2). Commits fall at the end of every test task rather than being batched. Parser tests use real fixtures and read expected values from the file's own frontmatter, which follows the project's parsing rules. Task 8.3 polls for applied submissions instead of sleeping.

### [PASS] No NFR, so no load test or CI gating task is required

The slice design states no performance or throughput NFR. The only mention is that judge samples per project are "few". Neither a `tests/load/` task nor a CI wiring task is needed.

### Run Digest

- Response length: 6105 chars
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
- Duration: 56.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
