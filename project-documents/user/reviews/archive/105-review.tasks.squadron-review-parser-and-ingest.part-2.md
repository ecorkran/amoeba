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
reviewedSha: 157bbb34e9c0e3e4bd7d3699f8cc525b31507933
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
durationSeconds: 34.2
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria traceability for Sections 6–9"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:354-392"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:21-298"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Task 8.2 leaves a committed command that returns OK without submitting"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:175"
  - id: F004
    severity: note
    category: sequencing
    summary: "Task 7.3's dependency on Task 6.2 is a soft one"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:104"
  - id: F005
    severity: note
    category: process
    summary: "No explicit merge-to-target step"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:340-357"
  - id: F006
    severity: pass
    category: coverage
    summary: "NFR and load-test requirement"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:347"
---

# Review: tasks — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria traceability for Sections 6–9

Each criterion that falls in this file's range maps to a task:
- **Payload round trip:** Task 6.2 covers `verdict_to_payload` against every field, nulls, and a fixture-derived input.
- **Test migration:** Tasks 7.1–7.4 move 104's tests onto the parser and reduce `review_fixtures.py` to paths.
- **Ingest on a real file:** Task 8.5 covers the success path, and Task 8.6 covers the digest id, `source_path`, and no second record on re-ingest.
- **Failure exits:** Task 8.3 covers unreadable input, a missing version label, and a stamp/argument disagreement, each leaving `inbox/new/` empty. It also covers a project with no store file.
- **Stopped process and unknown project:** Task 8.7 covers both with the process running and stopped, and checks `inspect inbox`.
- **stderr line and D7:** Task 8.5 covers the node/slice/type line and a slice mismatch that is still submitted.
- **Stdout/file id divergence:** Task 8.8.
- **No Store in ingest:** the AST test in Task 8.3.
- **Docs and CHANGELOG:** Tasks 9.1 and 9.2.
- **Walkthrough steps 1–9:** Task 9.3 for steps 1–9, with the `kill -9` and restart from step 8 covered by Task 8.6.

I found no scope creep. Every task traces to a slice criterion, an enforced rule, or the Development Approach list.

### [PASS] Sequencing and test-with pattern

Dependencies are acyclic and respected: 6.1→6.2, 7.1–7.3→7.4→8.1, then 8.2→8.3→8.4→8.5→8.6→8.7→8.8. Each implementation task is immediately followed by its test task. Commits fall at 6.2, 7.1, 7.2, 7.3, 7.4, 8.1, 8.3, 8.5, 8.6, 8.7, 8.8, 9.1, 9.2, and 9.3, so they are not batched at the end.

Task 7.2's claim that `tests/store/test_finding_changes.py` needs no edit holds. That file imports only `evidence_harness` and the `ROUND_*` paths from `review_fixtures`. The LLD names it as a migration user, and the task explains why it is covered anyway.

### [CONCERN] Task 8.2 leaves a committed command that returns OK without submitting

Task 8.2 ends with a `TODO(8.4)` stub that returns `OK` without submitting. Task 8.2 has no commit of its own and is committed together with Task 8.3. Task 8.4 then lands in a later commit, so there is a commit where `amoeba ingest review` reports success and writes nothing. That sits badly with the project rule against silent success or fallback behavior. Two options:
- Merge 8.2 and 8.4 into one task: parse, compose, and submit. 8.3 and 8.5 would also merge into one test task, or 8.5 would still follow.
- Keep the split, but make the stub fail explicitly (for example, raise `NotImplementedError`), and remove it in 8.4.

### [NOTE] Task 7.3's dependency on Task 6.2 is a soft one

The task says the test "may use" `verdict_to_payload`, which does not make 6.2 a hard prerequisite. It does no harm, since 7.3 runs after Section 6 anyway.

### [NOTE] No explicit merge-to-target step

Task 9.3 commits on the slice branch. The repository's Git Rules require re-reading `git.integration_branch` and merging the slice branch into the target when implementation is done. The task list has no step for that. If it is handled outside the task list, this is fine. Otherwise, add a final checklist item or state in the Context Summary that the merge is the PM's step.

### [PASS] NFR and load-test requirement

The slice restates no NFR, so no `tests/load/` task and no CI gating task are required. Task 9.3 runs `uv run pytest tests/load` and says it checks only for regressions, which is a reasonable choice.

### Run Digest

- Response length: 4446 chars
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
- Duration: 34.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
