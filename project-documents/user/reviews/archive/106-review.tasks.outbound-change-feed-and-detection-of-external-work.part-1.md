---
docType: review
layer: project
reviewType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 5d387ea192f7f4469f164ec1550234e2cd0c06c8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 46.8
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Invariant test sits at the end of Section 5, though the design makes it step 1 and the riskiest piece"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:465-469"
  - id: F002
    severity: concern
    category: task-clarity
    summary: "Task 5.6 failure injection cannot be done with Task 5.5's signature"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:437-459"
  - id: F003
    severity: note
    category: scope
    summary: "`read_only` constructor flag is scope beyond the design, but it is disclosed"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:313-315"
  - id: F004
    severity: note
    category: task-clarity
    summary: "`recorded_since` assumes the verdict id is the 105 `record_id`"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:355"
  - id: F005
    severity: note
    category: edge-case
    summary: "Retry rule for `record_verdict` with a differing `source_document` is not addressed"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:200-217"
  - id: F006
    severity: note
    category: granularity
    summary: "Task 3.3 is thin enough to merge into Task 3.2"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:244-258"
  - id: F007
    severity: note
    category: task-clarity
    summary: "Task 1.4 has a conditional step that is vague for a junior AI"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:109"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for Sections 1–5 and test-with / commit cadence"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:34-518"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Invariant test sits at the end of Section 5, though the design makes it step 1 and the riskiest piece

Task 5.7 says it is the "Riskiest piece; it gates the rest." But it follows about 20 tasks (Sections 2–5), and Sections 6–11 do not depend on it. The slice design's Development Approach step 1 pairs migration 006, its triggers and the invariant test. Triggers for nodes, verdicts and messages exist after Task 2.3, so a first reconciliation (nodes, verdicts, messages) could run right then. The detection part could be added in Task 5.2. As written, a wrong payload, a wrong `recorded_at` source or a missing trigger surfaces only after Sections 3–5 are built on top. Recommendation: either move a partial invariant test to follow Task 2.3 and extend it in Task 5.2, or drop the "gates the rest" wording and add a real dependency from Section 6 on Task 5.9.

### [CONCERN] Task 5.6 failure injection cannot be done with Task 5.5's signature

Task 5.5 defines `baseline_watch(project_id, reviews_dir, entries)`, which inserts one `baseline` row per `(path, digest)`. The outcome is fixed, so entries carry no outcome. Task 5.6 then says to "force a failure partway (an invalid outcome in the batch)." There is no way to put an invalid outcome in the batch. A junior AI would have to invent a mechanism, or would weaken the atomicity test. Specify a concrete injection point, for example a malformed entry such as a non-string digest or an empty path that violates a constraint, or a monkeypatched private insert that raises on the Nth call. Say which one in Task 5.5 or 5.6.

### [NOTE] `read_only` constructor flag is scope beyond the design, but it is disclosed

Task 4.3 adds a keyword-only `read_only` flag to `Store.__init__`, which the design does not spell out. It enforces D1a's "read-only handle only" rule, and the task records it in `store-contract.md` (Task 11.7) and in the PM report (Task 11.11). It also touches 101's constructor and "any direct `Store(...)` constructions in tests". Keep it, but the PM should confirm the constructor change.

### [NOTE] `recorded_since` assumes the verdict id is the 105 `record_id`

Task 5.1 says "`record_id` is the verdict id 105 uses." The design says only that `recorded_since` is true when "a verdict with that `record_id` now exists." If 105's `review_record_id` is not literally `verdicts.id`, the select will be wrong. Task 5.2 tests only "a verdict with that id". Task 8.1 gates on 105, but this assumption is checked in Section 5, before 105 is verified. Add a check against 105's contract, or a note that the Task 8.1 test must confirm the equivalence.

### [NOTE] Retry rule for `record_verdict` with a differing `source_document` is not addressed

Task 3.1 adds `source_document` to `VerdictInput` and the writer. It does not say what a retried `record_verdict` with the same id but a different `source_document` should do. The Task 3.1 tests cover only the present and absent cases. It is probably a no-op under 104's retry rule, but state it, or add one test that pins the behavior.

### [NOTE] Task 3.3 is thin enough to merge into Task 3.2

Task 3.3 is effort 2. It extends the test file Task 3.2 creates, and it is a test-only variant that runs the same scenario through `apply_submission`. This is acceptable as written. Merging it into 3.2 would save a task boundary, but it would make 3.2 effort 4–5. No change required.

### [NOTE] Task 1.4 has a conditional step that is vague for a junior AI

"Assert the duplicate-column / re-apply case fails loudly … (same as 005's test, if it has one)". The instruction depends on a lookup and has no stated outcome if 005 has no such test. Tell the junior AI to read `test_migration_005.py` first. If it has no such test, they should either skip the step or write it from scratch.

### [PASS] Success-criteria coverage for Sections 1–5 and test-with / commit cadence

These slice criteria trace to tasks in this file:
- Migration 006 and the 5→6 upgrade: Tasks 1.3–1.4.
- Triggers for nodes, status changes (including the same-status case), verdicts (including a retried verdict and provider failure) and messages (including recovery escalation): Tasks 2.1–2.3.
- `source_document` and the part-1/part-2 series: Tasks 3.1–3.3.
- `changes`, `change_head` and the `read_transaction` concurrency test with its control case: Tasks 4.1–4.4.
- `watch_reviews`, baselining and atomicity: Tasks 5.3–5.6.
- The invariant test: Tasks 5.7–5.9.

No task is scope creep. Each implementation task is paired with its test, either in the same task or in the immediately following one. Commits are distributed throughout, not batched at the end. The design restates no numeric NFR: it says the parent architecture sets no targets and that the follow interval is a contract statement, not a load target. So no `tests/load/` task or CI gating task is required here.

### Run Digest

- Response length: 6548 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 46.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
