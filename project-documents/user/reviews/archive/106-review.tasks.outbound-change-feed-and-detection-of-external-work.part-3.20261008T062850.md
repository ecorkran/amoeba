---
docType: review
layer: project
reviewType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 5d387ea192f7f4469f164ec1550234e2cd0c06c8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 77.9
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Task 10.4 depends on the demo script that Task 11.1 creates"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:90"
  - id: F002
    severity: concern
    category: coverage
    summary: "Traceability list omits several slice success criteria"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:324-342"
  - id: F003
    severity: concern
    category: accuracy
    summary: "Task 11.11 mislabels what is \"beyond the LLD\""
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:308"
  - id: F004
    severity: concern
    category: test-with-pattern
    summary: "Import-boundary and single-definition test comes only at the end"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:286"
  - id: F005
    severity: concern
    category: task-sizing
    summary: "End-to-end tasks 11.2–11.4 are large and share one fragile helper set"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:133"
  - id: F006
    severity: concern
    category: test-fixtures
    summary: "Part C depends on a live project file that may move"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:174"
  - id: F007
    severity: concern
    category: error-handling
    summary: "Wiring tests do not cover the `sq --version` failure path"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:89-92"
  - id: F008
    severity: concern
    category: documentation
    summary: "Some documented design caveats have no owning doc task"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:228-250"
  - id: F009
    severity: note
    category: nfr
    summary: "No load-test or CI-gating task is required"
    location: "unverified"
  - id: F010
    severity: note
    category: coverage
    summary: "Baseline behavior is not exercised end to end"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:133"
  - id: F011
    severity: pass
    category: coverage
    summary: "Remaining criteria in this file are covered, ordered and checkpointed"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:21-348"
---

# Review: tasks — slice 106

**Verdict:** FAIL
**Model:** claude-sonnet-5-5

## Findings

### [FAIL] Task 10.4 depends on the demo script that Task 11.1 creates

Task 10.4's CLI-subprocess case says to "create a project and seed a slice node (demo script)". That script, `scripts/demo_detection.py`, is created in Task 11.1, which lists Task 10.4 as its dependency (line 107). So 10.4 cannot be completed as written, and a junior AI would have to invent a seeding path or stall. The script needs only the store, so nothing in Section 10 blocks it. Move the demo-script task, with its writer-guard entry and test, ahead of 10.4. For example, make it Task 10.3a or 10.4 and renumber. Then have 10.4 depend on it.

### [CONCERN] Traceability list omits several slice success criteria

Task 11.12 is the final check that every Functional and Technical Requirement has a passing test. It names no test for these criteria:
- **D7 series separation.** With the captured 102 series detected, `finding_changes` on part 1 round 2 must name part 1 round 1 as previous, never part 2. Verdicts with no `source_document` must keep 104's behavior. 104's existing tests must pass unchanged.
- **Follower read-only and non-mutating.** The follower must open the store read-only, and the `changes` table must be unchanged by following or resuming. Only `--after` and resume are mapped.
- **Unattributed recovery by hand.** An `unattributed` file ingested with `amoeba ingest review` shows `recorded_since` true, and a second ingest records nothing. Task 10.2 touches `recorded_since`, but 11.12 does not list this criterion.

The part-1/part-2 series case is also absent from end-to-end parts A–C, though walkthrough step 5 exercises it. These tests may exist in files 1 and 2, but a traceability task that omits them cannot confirm them. Add bullets for each.

### [CONCERN] Task 11.11 mislabels what is "beyond the LLD"

Task 11.11 tells the junior to report `recorded_since` and `DetectionInput` as additions beyond the LLD. The LLD has both: `recorded_since` is in the `inspect detections` columns, and `record_detection(DetectionInput)` is in the store API table. Only the `read_only` constructor flag and `record_detected_verdict` look absent from the LLD. The PM would get a misleading list. Verify against the LLD and correct the list, or say "compare against the LLD and list what is missing".

### [CONCERN] Import-boundary and single-definition test comes only at the end

Task 11.10 adds `tests/test_import_boundaries.py` after all implementation. It checks that the store imports nothing from upstream, process, or feed, that SQL stays in `sql_feed.py`, and that the enums are defined once. A violation introduced in Section 1 or 2 would only surface at the end and force rework across earlier commits. Create the test with the store and feed code, and have 11.10 only run it. The same applies to the `wc -l` split pass at line 289, which risks late refactors after the end-to-end tests are green.

### [CONCERN] End-to-end tasks 11.2–11.4 are large and share one fragile helper set

Each of these tasks is rated effort 3 but bundles subprocess orchestration (process, follower, stop, `kill -9`), timeout-aware line collection, and many exact-content assertions. Task 11.2 also builds the shared helpers that 11.3 and 11.4 reuse. Consider a separate task, with a smoke test, for the helpers (start and stop process, follower line collector, wait-on-condition). Then 11.2–11.4 become assertion tasks. Also in 11.2, the `resolution` submission needs a blocked-state id, from `inspect blocked`. The demo script prints only the two node ids, and no step says where the id comes from.

### [CONCERN] Part C depends on a live project file that may move

Task 11.4 copies `project-documents/user/reviews/104-review.slice.findings-verdicts-and-provenance.md`, "or another real review". That directory is where reviews are rotated into `archive/` by hand (see the working-tree status), so the file can move or change. The slice's Technical Requirements say tests use real files from `tests/fixtures/sq_reviews/`. Pick a real review whose slice has no node, add it to the fixtures, and reference it there. Remove the "or another" hedge.

### [CONCERN] Wiring tests do not cover the `sq --version` failure path

The slice design says that if `sq --version` fails or times out at start-up, the label becomes the explicit unavailable marker, and `start` must still proceed. Task 10.4 tests only a fake `sq` that succeeds and the call-count once-only check. If file 2 does not test the marker, add a case for a missing or timing-out `sq` (`sq_timeout_seconds` is already a setting). The case should assert that `start` runs and the marker reaches the tenant.

### [CONCERN] Some documented design caveats have no owning doc task

The slice design says two things are "documented, not handled". The first is that registering one directory under two spellings creates two watches, with extra ledger rows. The second is the manual recovery path for `unattributed` files (`inspect detections --outcome unattributed`, then `ingest review --node`, oldest first). Tasks 11.7 and 11.8 list neither. Add them to `process-contract.md` and `evidence-contract.md`, or confirm another task does. Also add them to the required-terms lists.

### [NOTE] No load-test or CI-gating task is required

The slice names no non-functional requirement that calls for a load test. It says "the parent architecture sets no numeric targets". Its timing figures (2 s scan, 0.25 s follow interval, detection within about 5 s) are design choices, and the contract states only the follower bound. No `tests/load/` or CI wiring task is needed. If the PM wants the follower latency bound gated, add it as a separate decision.

### [NOTE] Baseline behavior is not exercised end to end

Walkthrough step 3 (files present at registration are `baseline` and never ingested) appears only in the manual run in Task 11.11. Parts A–C register an empty directory. The Integration Requirements do not demand it, and 11.12 maps baseline to unit tests. A baseline file in part A would make the end-to-end test cover it, though the "two ingested rows" assertion would need to allow the extra `baseline` row. Optional.

### [PASS] Remaining criteria in this file are covered, ordered and checkpointed

- **Coverage.** The two listings and the `start` wiring (10.1–10.4) are tested alongside their implementation. The demo script and writer guard (11.1) are tested too. End-to-end parts A–C cover the Integration Requirements and walkthrough steps 1, 2, 4, 6, 7 and 8. The five doc deliverables are all assigned (11.5, 11.7–11.9). The 103 forward-reference fix is limited to one sentence. The invariant and boundary checks have their own task (11.10), and the walkthrough run has its own (11.11).
- **Scope creep.** No task lacks a slice origin.
- **Sequencing.** Apart from the 10.4/11.1 defect, dependencies run forward in order.
- **Test-with pattern.** 10.1→10.2, 10.3→10.4, 11.5→11.6, and 11.7–11.9 each extend `tests/test_contract_docs.py`.
- **Checkpoints.** Commits are spread throughout. They are paired only where a test task immediately follows its implementation task.

### Run Digest

- Response length: 8875 chars
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
- Duration: 77.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
