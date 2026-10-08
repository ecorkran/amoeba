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
reviewedSha: 0fee83708104833e2eac43087fc2ac55009feebd
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 60.2
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria for this file's scope trace to tasks"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:158-529"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern, and commit cadence are sound"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:26"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 3.1 bundles too many concerns for one junior task"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:276-295"
  - id: F004
    severity: concern
    category: scope
    summary: "Task 3.1 settles a design question the slice design leaves open, and nothing reports it"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:286"
  - id: F005
    severity: note
    category: scope
    summary: "The `read_only` constructor flag is a task-level mechanism that changes 101's `Store.__init__`"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:374-376"
  - id: F006
    severity: note
    category: consistency
    summary: "`SILENT_OUTCOMES` is attributed to a test that does not use it"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:64"
  - id: F007
    severity: note
    category: test-coverage
    summary: "\"Confirm no trust label\" in Task 2.3 is not an assertion"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:209"
  - id: F008
    severity: pass
    category: nfr
    summary: "No load-test or CI-gating task is required"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:314"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria for this file's scope trace to tasks

Each criterion that Sections 1–5 should own has a task and a test:
- **Feed emission and replay:** Tasks 2.1–2.6 cover emission and the reconciliation test, including the dropped-trigger and enum-literal checks.
- **`resolution` → `node_status_changed`:** Task 2.2 covers the block/resolve path.
- **`read_transaction()` atomicity (D1a):** Tasks 4.3–4.4 cover it, including the control case and the rollback and nesting cases.
- **`source_document` and series separation (D7):** Tasks 3.1–3.2.
- **Version-5 upgrade:** Task 1.4.
- **Single-definition and layering requirements:** Task 1.6.
- **Ledger, silent outcomes, `watch_reviews` and baselining:** Tasks 5.1–5.6.

Criteria not owned here (follower, attribution, tenant, listings, end-to-end) land in files 2 and 3, and Task 11.12 traces each one back to a test.

### [PASS] Sequencing, test-with pattern, and commit cadence are sound

There are no circular dependencies. Every implementation task is followed immediately by its test task (1.3→1.4, 4.1→4.2, 4.3→4.4, 5.1→5.2, 5.3→5.4, 5.5→5.6). The "committed with Task N.M" rule keeps untested behavior out of commits, and commits are spread through the file rather than batched. Putting the invariant test (2.4–2.6) right after the triggers it checks, then extending it in Task 5.2, matches the slice design's "riskiest piece first" step 1.

### [CONCERN] Task 3.1 bundles too many concerns for one junior task

Task 3.1 touches about nine files across four layers:
- `VerdictInput` and `VerdictRecord`
- SQL and mapping
- the verdict writer
- the inbox payload and `verdict_payload.py`
- the `verdicts.py` retry comparison and its docstring

It also introduces a new retry behavior and a new test module, all at Effort 3. This is a change to 104's finished contract, so a mid-task failure is hard to diagnose. Consider splitting it into (a) model, SQL, mapping, writer and the read-back test, and (b) the inbox payload, the retry rule and their tests. Each half would then commit on its own.

### [CONCERN] Task 3.1 settles a design question the slice design leaves open, and nothing reports it

The slice design (D7) does not say what happens when a `record_verdict` retry carries a different `source_document`. Task 3.1 decides it: keep the first record, log a WARNING, add no conflict error. The Task 11.11 report lists the other task-level additions (`read_only`, `recorded_since`, `DetectionInput`, and so on) but omits this decision. It changes behavior for the Runner (120) and for hand-edited reviews. Add it to the Task 11.11 report list, and to `evidence-contract.md` in Task 11.8, so the PM can overrule it. The project guidelines say not to guess.

### [NOTE] The `read_only` constructor flag is a task-level mechanism that changes 101's `Store.__init__`

The slice design only says `read_transaction()` lives on the read-only handle. Task 4.3 adds a keyword-only `read_only` flag to the constructor and requires updating direct `Store(...)` constructions in tests. The task discloses this and plans documentation (Task 11.7) and a PM report (Task 11.11), so I'm not flagging it as a gap. The implementer should confirm no lighter option exists, such as reading the connection's own read-only mode, before adding constructor surface.

### [NOTE] `SILENT_OUTCOMES` is attributed to a test that does not use it

Task 1.2 says `SILENT_OUTCOMES` serves "the trigger-literal test in Task 2.6". Task 2.6 excludes `review_detected` and does not use the silent set. Task 5.2 is what adds the `SILENT_OUTCOMES` literal check. Correct the reference so the junior implementer is not confused.

### [NOTE] "Confirm no trust label" in Task 2.3 is not an assertion

The design requires that the `verdict_recorded` payload carries no trust label. The step says "Confirm", which a reader can satisfy without writing a test. Make it an assertion on the exact payload key set in the existing `verdict_recorded` test.

### [PASS] No load-test or CI-gating task is required

The slice design states that the parent architecture sets no numeric targets. The 2 s scan, 0.25 s follow and 5 s detection figures are settings choices, not restated NFRs. Files 2 and 3 say explicitly that no load test was added, and Task 11.11 tells the PM so they can overrule it. That is consistent with the review criteria.

### Run Digest

- Response length: 5831 chars
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
- Duration: 60.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
