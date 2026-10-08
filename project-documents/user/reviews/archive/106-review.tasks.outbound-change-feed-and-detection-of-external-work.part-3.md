---
docType: review
layer: project
reviewType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 5aade9e5d6aebd988061a3975597c6e24b572def
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 40.8
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: coverage-gap
    summary: "Coverage trace (11.12) omits several slice criteria"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:322-343"
  - id: F002
    severity: concern
    category: test-fragility
    summary: "Task 11.4 depends on a mutable project document as a \"real fixture\""
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:174"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Boundary and single-definition pins come only at the end"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:279-296"
  - id: F004
    severity: note
    category: task-scope
    summary: "Task 11.10 mixes a new test with whole-suite validation and file-size cleanup"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:285-289"
  - id: F005
    severity: note
    category: nfr
    summary: "No load test or CI gating task, which is appropriate here"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:314-321"
  - id: F006
    severity: note
    category: verification
    summary: "Task 11.11 is a manual verification with no pass/fail test"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:299-312"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success criteria for listings, wiring, and process behavior are covered"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:21-100"
  - id: F008
    severity: pass
    category: coverage
    summary: "End-to-end tests map to the Integration Requirements and walkthrough"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:105-181"
  - id: F009
    severity: pass
    category: documentation
    summary: "Documentation tasks are traceable and verified by tests"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:185-275"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Coverage trace (11.12) omits several slice criteria

Task 11.12 is meant to be the check that every Functional and Technical Requirement has a passing test. Its bullet list leaves out several criteria:
- The D7 series criterion: part-1 round 2 names part-1 round 1 as its previous round, and verdicts without `source_document` keep 104's behavior. File 1 has `test_finding_changes_source_document.py`, but 11.12 never names it.
- "104's tests run unchanged and must pass" (design D7).
- `watch_reviews` behaviors: a relative path is quarantined, and reactivation does not re-baseline. These are covered in file 1's `test_watch_reviews.py`, but the trace skips them.
- Message and node-created emission through the recovery escalation path, beyond the single `test_feed_invariant` line.

Add these bullets so the final trace can't pass while skipping them. Also say which test covers "the captured 102 series detected on one slice node yields the correct previous round". Today that check appears only in the manual walkthrough (step 5). The end-to-end tests assert no `finding_changes` result.

### [CONCERN] Task 11.4 depends on a mutable project document as a "real fixture"

The unattributed case copies `project-documents/user/reviews/104-review.slice.findings-verdicts-and-provenance.md`. The reviews directory is where the PM moves rounds into `archive/` by hand. The file can therefore be renamed, moved or overwritten, and the test would break or change meaning. The slice's Technical Requirements say tests use real files from `tests/fixtures/sq_reviews/`. Use a fixture in that directory whose slice name has no seeded node. The 102 series fixtures work if the demo script seeds a different slice name. If no suitable fixture exists, add one as an explicit step. Don't leave "or another real review" open-ended.

### [CONCERN] Boundary and single-definition pins come only at the end

Task 11.10 adds `tests/test_import_boundaries.py`. It pins the "store imports nothing from upstream/process/feed" rule and the "SQL only in `sql_feed.py`" and "enums defined once" rules. These constrain code written in Sections 1–9, so a violation found now means rework. The text scan for enum string values (`ingested`, `baseline`, `unparseable`) across `src/amoeba/` is also prone to false positives from CLI help text and docstrings. State what the scan ignores, such as comments and docstrings, or limit it to quoted literals in comparisons. Consider adding the AST import check earlier, with the feed package. The final run can then just confirm it.

### [NOTE] Task 11.10 mixes a new test with whole-suite validation and file-size cleanup

It bundles writing a test, the full pytest, ruff and pyright run, and splitting any file over about 300 lines. The split could be substantial and could touch many files. The effort of 2 is likely low if a split is needed. This is acceptable, but say that a split is its own commit with tests rerun.

### [NOTE] No load test or CI gating task, which is appropriate here

The slice design states that the parent architecture sets no numeric targets. Its latency bounds (scan interval, follow interval) are described as slice choices, not NFRs. The only contract promise is the follower's latency bound, and the tasks test the follower's behavior. No `tests/load/` task or CI wiring is required.

### [NOTE] Task 11.11 is a manual verification with no pass/fail test

The run is reasonably scoped. It produces a report of differences instead of editing the LLD, and it states what to do if a step can't run. Walkthrough step 9 re-runs the end-to-end tests, so there is no extra gap. Success depends on the AI reporting accurately, and the task says to report empty results explicitly.

### [PASS] Success criteria for listings, wiring, and process behavior are covered

- Tasks 10.1/10.2 cover `inspect watches` and `inspect detections`. The `watches` states are `ok`, `unreachable`, `baseline_pending` and `failed`. The `detections` listing covers every outcome, the `--outcome` filter, parked files as `failed`, and `recorded_since`.
- Task 10.3 registers the second tenant and captures the `sq` label once, before the loop. Task 10.4 tests restart with `kill -9`, the single label capture, and that no tick starts a subprocess.

### [PASS] End-to-end tests map to the Integration Requirements and walkthrough

- Tasks 11.1–11.4 cover walkthrough steps 1–8. They assert exact ordered feed content and guard against vacuous passes.
- They cover the follower started while the process is stopped, `kill -9` with restart, the provider failure, resume with `--after`, hand edits that add no second verdict, and unattributed and unparseable files.
- The demo script is added to the writer-guard permitted list with a refusal-case test.

### [PASS] Documentation tasks are traceable and verified by tests

- Tasks 11.5–11.9 cover `feed-contract.md`, the four contract updates, the CHANGELOG, and the single-sentence edit to the 103 forward reference.
- The docs are checked against code with a reusable `test_contract_docs` helper. The helper extends across 11.6–11.9.
- The documentation includes the requirements on initiative 120 (attribution rule, D5 points 3 and 5) and the D8a note.

### Run Digest

- Response length: 6857 chars
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
- Duration: 40.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
