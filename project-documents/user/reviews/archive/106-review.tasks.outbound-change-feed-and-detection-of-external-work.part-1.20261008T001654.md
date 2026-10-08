---
docType: review
layer: project
reviewType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: b5da659741742529433c377b91c455da5186e39a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 100.8
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for sections 1–6"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit checkpoints"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 5.3 is oversized"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:383-401"
  - id: F004
    severity: concern
    category: test-with
    summary: "Several implementation tasks have no test until a later task"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:199-235"
  - id: F005
    severity: concern
    category: clarity
    summary: "`read_transaction` mode handling is under-specified"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:301-318"
  - id: F006
    severity: note
    category: nfr
    summary: "No load-test or CI-gating task, and none is required"
    location: "unverified"
  - id: F007
    severity: note
    category: scope
    summary: "Minor scope observations"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:269"
---

# Review: tasks — slice 106

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage for sections 1–6

Each criterion that belongs to these sections has a task:
- Trigger emission and the 5 → 6 upgrade: Tasks 1.3–1.5 and 2.1–2.3.
- The `verdict_recorded` payload and retry-emits-nothing rule: Task 2.3.
- `source_document` and part-1/part-2 series separation (D7): Tasks 3.1–3.3.
- `read_transaction` atomicity, with a control case (D1a): Tasks 4.3–4.4.
- The ledger, silent outcomes and `recorded_since`: Tasks 5.1–5.2.
- Registration, baseline atomicity and the `watch_reviews` kind: Tasks 5.3–5.4.
- The invariant test, including "every `ChangeKind` appears" and the literal-drift check: Task 5.5.
- `attribute_review` cases and the review-producing kinds set (D4/D5): Tasks 6.1–6.3.

Items from the slice that sit outside this file are placed in the later files:
- The `store-contract.md` update, including `read_transaction()`.
- The D8a edit to the 103 slice document.
- The `resolution` → `node_status_changed` end-to-end assertion.

### [PASS] Sequencing and commit checkpoints

- Dependencies run linearly with no cycles.
- Every implementation task is paired with a test task immediately after it (1.3→1.4, 2.x with triggers, 3.x→3.3, 4.1→4.2, 4.3→4.4, 5.1→5.2, 5.3→5.4, 6.x→6.3).
- Commit points are spread across the sections. The file states the rule that a commit never holds untested behavior.
- Putting the invariant test (5.5) after detection storage is correct, because it needs all five outcomes.
- The "triggers grow in place, never create a 007" note prevents a real mistake.

### [CONCERN] Task 5.3 is oversized

Task 5.3 (effort 4) bundles four separable pieces:
- A new `SubmissionKind`, payload model and effect.
- Upsert semantics that preserve `baselined_at`.
- Two new store methods (`watches`, `baseline_watch`) with transactional atomicity.
- A CLI-derivation check.

A junior AI could stall partway. Consider splitting it into (a) the kind, payload and effect, and (b) `watches` and `baseline_watch`, each with its test. If it stays as one task, the "Fix only if it does not" step for the CLI flag needs a stop-and-ask rule.

### [CONCERN] Several implementation tasks have no test until a later task

- Tasks 3.1 and 3.2 modify the verdict writer, mapping, payload and previous-round query. They rely only on the existing 104 suite until Task 3.3.
- 3.1's success criterion "reads back with it; without reads back `None`" is only implicitly exercised by 3.3's cases.
- Tasks 1.2–1.5 form one commit spanning four tasks, which is a large checkpoint.

None of this violates the "committed with" rule, but it makes failures harder to localize. Make 3.3 explicitly assert `source_document` read-back for both the value and the null case.

### [CONCERN] `read_transaction` mode handling is under-specified

- Task 4.3 says to document the read-only intent in the docstring rather than add mode tracking. The LLD says the method lives on the read-only handle.
- Nothing prevents it being called on a read-write handle, where `BEGIN` would interact with writer transactions.
- The "error if a transaction is already open" step is a small addition beyond the LLD, and its detection mechanism is unspecified.

Specify how an open transaction is detected (for example `connection.in_transaction`), and say whether a call on a read-write handle should fail.

### [NOTE] No load-test or CI-gating task, and none is required

The slice states no throughput or latency NFR that needs a `tests/load/` test. The numbers it gives (scan interval, follow interval, attempts) are design choices, not NFRs, and `feed-contract.md` states only the follower latency bound. No load-test task or CI gating task is needed.

### [NOTE] Minor scope observations

- `DetectionInput` and `recorded_since` appear in the tasks but not in the LLD's API table. They are justified by the `record_detection` signature and the `inspect detections` columns, so they are not scope creep.
- The `limit` argument has no default, as the project's no-magic-defaults rule requires.
- The Task 4.4 control case ("stop and tell the PM rather than weakening the test") is a good guard against a vacuous test.

### Run Digest

- Response length: 5342 chars
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
- Duration: 100.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
