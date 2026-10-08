---
docType: review
layer: project
reviewType: tasks
slice: context-forge-event-seam
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: f5d55a58aa9aabb0a35ac75ec7b1518452b70078
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
durationSeconds: 205.6
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: ci-wiring
    summary: "Real-`cf` tests will fail in CI because no task installs `cf`"
    location: ".github/workflows/ci.yml:48"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "New writers are not explicitly registered with the writer guard until the last section"
    location: "tests/test_writer_guard.py"
  - id: F003
    severity: concern
    category: correctness
    summary: "`cf_watch_revision` bump timing is ambiguous against the inbox transaction"
    location: "src/amoeba/store/inbox.py"
  - id: F004
    severity: note
    category: sequencing
    summary: "Task 3.5 and Task 4.1 each carry no tests of their own, but their commit grouping is sound"
    location: "unverified"
  - id: F005
    severity: note
    category: coverage
    summary: "Cross-file requirement coverage is complete"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md"
  - id: F006
    severity: note
    category: nfr
    summary: "No load test or NFR is required"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md"
  - id: F007
    severity: note
    category: scope
    summary: "Scope additions are flagged and reported"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md"
  - id: F008
    severity: note
    category: test-fidelity
    summary: "The worktree overlay may have no real fixture"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md"
  - id: F009
    severity: pass
    category: task-sizing
    summary: "Sizing and sequencing"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md"
---

# Review: tasks — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Real-`cf` tests will fail in CI because no task installs `cf`

Task 1.3's `real_cf` fixture fails when `cf` is not on `PATH`. It never skips, and that is deliberate. Tasks 6.3, 6.4 and 8.1 depend on it. `.github/workflows/ci.yml` runs `uv run pytest` (line 48) and has no step that installs Context Forge. Once those tests land, CI goes red. The alternative is that someone adds a skip, which would undo the no-silent-skip guarantee. No task in either file edits the workflow or names the `cf` version CI should install. Add a task, ideally right after 1.3, that installs `cf` in CI and records the version. Task 8.6 should then report that version.

### [CONCERN] New writers are not explicitly registered with the writer guard until the last section

Task 3.5 says `record_cf_snapshot` and `set_cf_watch_state` are "in-process only (writer guard)". No task extends the guard's test or registry to cover the new methods. Task 8.4 only says the guard test "still passes". That passes trivially if the new methods are not registered. Add the registration and a refusal test in Task 3.6, where the methods are tested. In Task 8.4, assert that the new methods are present in the guard.

### [CONCERN] `cf_watch_revision` bump timing is ambiguous against the inbox transaction

Task 4.3 says the revision is "incremented after the `watch_cf` effect commits". Effects run inside the inbox apply transaction, so the effect cannot see the commit. A bump made inside the effect would also fire on rollback. The planned "rolled-back apply does not bump" test would then fail, or pass only through an accidental design. The task should say where the bump hooks in, for example a post-commit callback or a compare-and-bump after apply returns. It should also say who owns that hook. The "same handle" check at the start of 4.3 is good, but it does not settle this.

### [NOTE] Task 3.5 and Task 4.1 each carry no tests of their own, but their commit grouping is sound

Task 3.5 is committed with 3.6, 3.2 with 3.3, and 4.1 with 4.2. The test-with pattern holds. Commits are spread across all eight sections, with no batching at the end.

### [NOTE] Cross-file requirement coverage is complete

Every Functional and Technical requirement in the slice maps to a task.
- Reader, diff and `IGNORED_KEYS`: Tasks 2.1–2.3.
- Migration, trigger and invariant: Tasks 3.2–3.7.
- `watch_cf` kind: Tasks 4.1–4.3.
- Settings: Task 5.1.
- Idle path, file states, snapshots, absence and catch-up, bounded failure and retry: Tasks 6.1–6.6.
- Listings and wiring: Tasks 7.1–7.4.
- End-to-end test, docs and boundaries: Tasks 8.1–8.4.

Task 8.7 traces each requirement to a named test. I found no cross-file gaps or circular dependencies.

### [NOTE] No load test or NFR is required

The slice states no quantitative NFR. The idle-tick "one `stat`" guarantee is a functional criterion, and the spy-based tests in 6.1 and 6.6 cover it. The repo CI does run `tests/load`, so adding a load test is not needed here.

### [NOTE] Scope additions are flagged and reported

The slice does not list `--cf-max-attempts` as a flag in its Technical Scope, though it does list the setting. Task 5.1 adds the flag and Task 8.6 reports it. The same applies to the revision counter (4.3), the per-recording-read label capture (6.3), and the failed-watch existence check (6.6). All four are small, justified, and reported to the PM. The clock and label-callable injection is also consistent with the slice's no-subprocess-in-a-tick rule.

### [NOTE] The worktree overlay may have no real fixture

Task 1.2 allows capturing no overlay fixture. In that case, recursion of `IGNORED_KEYS` into `worktrees` is tested only on in-memory-modified records (Task 2.3). That is acceptable because Task 8.6 reports it. Still, the PM should know the recursive rule is not verified against real CF output if no overlay is captured.

### [PASS] Sizing and sequencing

Dependencies run in order, with the harness and fixtures first and wiring, docs and validation last. Tasks 6.3 and 6.5 are the largest, at effort 4 and 3. Both are bounded, and each has a clear success criterion and a named test file.

### Run Digest

- Response length: 4971 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 205.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
