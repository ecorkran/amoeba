---
docType: review
layer: project
reviewType: tasks
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 5aade9e5d6aebd988061a3975597c6e24b572def
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 81.6
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Baselining needs a read the `ReviewSource` interface does not provide"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:361"
  - id: F002
    severity: concern
    category: coverage
    summary: "Baseline failure counting is not a step in Task 9.9"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:487-503"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 9.6 asserts `recorded_since` before the task that likely builds it"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:440"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 9.6 is too large"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:420-446"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "No test for \"no tick starts a subprocess\""
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:303"
  - id: F006
    severity: concern
    category: scope
    summary: "Task 8.1 edits a finished slice's code and tests, which conflicts with the slice design"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:211-227"
  - id: F007
    severity: concern
    category: test-coverage
    summary: "Task 6.5 does not test the hand-edit case at the unit level"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:99-112"
  - id: F008
    severity: note
    category: documentation
    summary: "`record_detected_verdict` is not in the slice's API Contracts table"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:327-338"
  - id: F009
    severity: note
    category: sequencing
    summary: "Some dependencies are looser than they need to be"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:121-124"
  - id: F010
    severity: note
    category: coverage
    summary: "Criteria whose coverage sits in file 1 or file 3 and was not verified"
    location: "unverified"
  - id: F011
    severity: pass
    category: coverage
    summary: "Remaining slice criteria in Sections 6–9 trace to tasks and tests"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:22-527"
  - id: F012
    severity: pass
    category: process
    summary: "Test-with pattern and commit cadence hold"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:73"
  - id: F013
    severity: pass
    category: nfr
    summary: "No load-test or CI-gating task is required"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:314"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Baselining needs a read the `ReviewSource` interface does not provide

Task 9.3 baselines by listing and reading every top-level `*.md` "not through the settle rule". It builds the source through `source_factory`, and Task 9.4 counts calls on a substitute source. But Task 8.2 defines the interface as only `poll()`, which returns settled files, and Task 8.3 implements only that. Task 8.4 has no baseline test.

A junior AI would have to invent a second method on the protocol. The alternative is to duplicate directory listing and the race handling inside the tenant. That breaks DRY and splits the D6 race table from 9.3's own failure table. An S8 event source would also have no way to take a baseline.

Fix: add an explicit "list everything, unsettled, raise on unreadable" method to Task 8.2 (or a separate documented baseline function). Implement it in 8.3 and test it in 8.4. Then have 9.3 call it.

### [CONCERN] Baseline failure counting is not a step in Task 9.9

Task 9.3 defers baseline store-failure counting and parking to Task 9.9. Task 9.9's steps only describe the per-file digest sidecar. The only baseline mention is the last bullet ("a parked baseline leaves the watch `failed`"). No step says to write or increment the `baseline-{sha256 of dir}` sidecar before `baseline_watch`. The slice's failure table requires it, and Task 9.10 tests it.

Two smaller problems in the same task:
- "Recording" is ambiguous. It should state that the counter wraps `record_detection` (unparseable and unattributed) as well as `record_detected_verdict`.
- The parked-skip rule appears twice, in steps 2 and 4.

### [CONCERN] Task 9.6 asserts `recorded_since` before the task that likely builds it

The last bullet of Task 9.6 expects `recorded_since` to be true after a hand `ingest review`. The slice defines `recorded_since` as a column of `inspect detections`, which Section 10 builds. If it is computed in the CLI listing, this bullet depends on a later task. Either confirm that file 1's `detections()` store read computes it, or move the bullet to the Section 10 listing tests.

### [CONCERN] Task 9.6 is too large

Task 9.6 has about 14 distinct test scenarios under an effort of 4. They cover ingest and series, hand edits, attribution, restart, version label, directory loss, interval, reactivation, races and manual ingest. Split it into at least two tasks, each with its own commit:
- core detection: ingest, series, provider failure, hand edit, unattributed, unparseable, restart, manual ingest
- operational cases: version label, directory removed and restored, scan interval, reactivation, delete-and-restore race

### [CONCERN] No test for "no tick starts a subprocess"

The slice lists "No tick starts a subprocess; `sq --version` runs once, before the loop" as a functional requirement. Task 9.1 states the rule but nothing in Sections 6–9 asserts it. Task 9.2 tests only the label helper. Add a case to Task 9.6 or 9.8 that patches `subprocess.run` (or `Popen`) to fail and ticks the tenant through baseline and scan. Task 10.3 could also cover it, but I cannot confirm that.

### [CONCERN] Task 8.1 edits a finished slice's code and tests, which conflicts with the slice design

The slice design lists "`to_verdict_input` carries `sourceDocument` into `VerdictInput.source_document`" under "met by 105's design". Task 8.1 says 105 left the pass-through undone and has 106 change `to_verdict_input` and one of 105's tests.
- If 105 already does this, steps 2–3 are no-ops.
- If it does not, the slice's Interfaces Required section is stale.

Reconcile the two, and record the contract change to 105 in the CHANGELOG entry, as D7 does for 104.

### [CONCERN] Task 6.5 does not test the hand-edit case at the unit level

Task 6.4 says the verdict-retry path must still insert a ledger row. That is the case of the same verdict id with a new digest, which is what a hand edit produces. Task 6.5 tests only an exact repeat, a failure and a non-`ingested` outcome. Add the case "same verdict id, different digest → one new ledger row, no new verdict, one `review_detected`, no `verdict_recorded`". Task 9.6 covers it only end to end.

### [NOTE] `record_detected_verdict` is not in the slice's API Contracts table

Task 6.4 adds a public `FeedOperations` method that the slice's API table omits. The slice describes the same behavior in prose in its "Detecting a review" data flow, so this is not scope creep. Add the method to the slice's API table and to `store-contract.md`, so that initiative 120 can use the same atomic pattern for `runner_issued` (D5 point 3).

### [NOTE] Some dependencies are looser than they need to be

- Task 7.1 depends on Task 6.3, but the follower does not use attribution.
- Tasks 8.2–8.4 do not need 105's parser, yet sit behind the 8.1 gate.
- Only Task 9.5 onward needs the parser.

None of this causes harm. It only delays work that could proceed if 105 slips.

### [NOTE] Criteria whose coverage sits in file 1 or file 3 and was not verified

These slice criteria have no task in Sections 6–9, so I could not confirm them:
- the `resolution` → `node_status_changed` change
- the `read_transaction()` atomicity test (the slice places it in the follower test suite, but Task 7.2 does not list it)
- the `inspect watches` and `inspect detections` listings, including `failed` rows
- the `kill -9` end-to-end test
- the docs and CHANGELOG
- the `scripts/demo_detection.py` writer-guard entry

Please confirm that file 1 or file 3 covers each of them.

### [PASS] Remaining slice criteria in Sections 6–9 trace to tasks and tests

- **Attribution and review kinds:** Tasks 6.1–6.3 cover the D4 case table and the D5 kinds set.
- **Follower and CLI:** Tasks 7.1–7.4 cover resume, process-stopped, killed-follower and exact-after behavior.
- **Directory source:** Tasks 8.3–8.4 cover the settle rule and the D6 race table.
- **Settings and `sq --version`:** Tasks 9.1–9.2 cover the three settings and the once-at-start label.
- **Baselining:** Tasks 9.3–9.4 cover the baseline failure table.
- **Detection:** Tasks 9.5–9.6 cover provider failure, series separation, hand edits, unattributed, unparseable, restart and reactivation.
- **Defer/skip:** Tasks 9.7–9.8 cover the defer and skip rules.
- **Bounded failure:** Tasks 9.9–9.10 cover the sidecar rules for per-file failures.

Nothing in these sections is scope creep. The extra helpers (`record_detected_verdict`, `detection_layout`, the shared label helper) each serve a slice requirement.

### [PASS] Test-with pattern and commit cadence hold

Every implementation task is followed immediately by its test task, and Task 9.2a bundles its tests. There are no circular dependencies. Commit points land at 6.3, 6.5, 7.2, 7.4, 8.1, 8.4, 9.2, 9.2a, 9.4, 9.6, 9.8 and 9.10, so they are spread through the file. Fixtures are real review files, and parsers are tested against real input, as the project rules require.

### [PASS] No load-test or CI-gating task is required

The slice states that the parent architecture sets no numeric targets. Its interval and timeout values (2 s scan, 0.25 s follow, and so on) are its own sizing choices, not restated NFRs. No `tests/load/` task and no CI-wiring task are therefore required.

### Run Digest

- Response length: 9223 chars
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
- Duration: 81.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
