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
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: a92fb441db4f98e35252946dc0dcbd28d323284a
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 66.3
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Criteria owned by Sections 6–9 are covered, and each task traces to a criterion"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit cadence are sound"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "Task 7.2 does not exercise the D1a atomicity guarantee"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:161"
  - id: F004
    severity: concern
    category: test-design
    summary: "Task 6.5 failure injection contradicts Task 6.4's idempotence rule"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:109"
  - id: F005
    severity: concern
    category: interface-consistency
    summary: "The tenant constructor has no clock, but the tests assume an injectable one"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:363-364"
  - id: F006
    severity: note
    category: dependency
    summary: "`recorded_since` is asserted in Task 9.6a, before any listing exists"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:460"
  - id: F007
    severity: note
    category: scope
    summary: "Task 8.1 edits slice 105's code and tests"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:224-225"
  - id: F008
    severity: note
    category: nfr
    summary: "No load test or CI gating task, which is consistent with the slice"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:20"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Criteria owned by Sections 6–9 are covered, and each task traces to a criterion

I checked the slice's success criteria against the tasks in this file, and each has a task and a test.
- Attribution, the review-producing kinds set and the one-transaction ingest are in 6.1–6.5.
- The follower and `amoeba feed` are in 7.1–7.4.
- Settle and file races are in 8.3–8.4.
- Baseline, including the unreachable and unreadable cases, is in 9.3–9.4.
- Ingest, series, hand-edit and restart are in 9.6.
- Unattributed, unparseable and version label are in 9.6a.
- Directory loss, cadence and reactivation are in 9.6b.
- Defer and skip are in 9.7–9.8.
- Bounded failure is in 9.9–9.10.

I found no scope creep. Two tasks reach beyond the new code but trace to the slice. Task 7.1 adds `project_store_path` so `amoeba.feed` doesn't import `amoeba.process`. Task 8.1 passes `source_document` through the parser (D7).

The criteria this file does not own are explicitly deferred to files 1 and 3 in the Context Summary.

### [PASS] Sequencing and commit cadence are sound

- **Dependencies:** I found no cycles. The cross-file dependencies (5.6, 4.4) point backward. The ordering of 7.1 after Section 6 is explained. The 105 gate in 8.1 stops rather than stubbing the parser.
- **Test-with pattern:** each implementation task is followed by its tests. The longest gap is 8.2–8.3 before 8.4, and 8.2 is a protocol definition.
- **Commits:** they land at 6.3, 6.5, 7.2, 7.4, 8.1, 8.4, 9.2, 9.2a, 9.4, 9.6, 9.6a, 9.6b, 9.8 and 9.10. Nothing is batched at the end.
- **File size:** 9.5 splits `review_scan.py` out up front, and the harness is a separate module, so no file should pass about 300 lines.

### [CONCERN] Task 7.2 does not exercise the D1a atomicity guarantee

The slice (D1a and the functional requirement on `read_transaction()`) requires a test that does the following:
1. Seed state and open `read_transaction()`.
2. Read state.
3. Commit a change from a second connection.
4. Read `change_head()`.
5. Assert the head did not observe the commit.

The slice says this goes "in the follower test suite". The "Snapshot then follow" case in 7.2 commits only after the head read. A plain, non-transactional read would pass it too, so it can't catch a broken `read_transaction()`. Either file 1 already tests the between-the-reads case, or this case should be changed to commit between the state read and the head read. Confirm which, and add a criterion that names the test.

### [CONCERN] Task 6.5 failure injection contradicts Task 6.4's idempotence rule

Task 6.5 suggests injecting the ledger-insert failure with "a duplicate key with a different verdict id". Task 6.4 (line 91) says a repeat with the same ledger key returns the existing records and writes nothing. The slice also makes `record_detection` idempotent on `(project_id, path, digest)`. Under that rule a duplicate key returns the existing row silently and raises nothing, so the test would not fail as 6.5 expects.

6.4 also never says what happens when the ledger key matches but the verdict id differs. 6.4 should state that case explicitly: raise, or return the existing row. 6.5 should then use a patched statement as its primary injection, which is the alternative it already mentions. The "new ledger key, same verdict id" case that 6.5 tests (line 110) is likewise only implied by 6.4. Make it explicit there.

### [CONCERN] The tenant constructor has no clock, but the tests assume an injectable one

Task 9.3 gives the constructor as `ReviewDetectionTenant(supervisor_dir, *, version_label, source_factory)`. It then says the clock is "passed in or `time.monotonic`", which leaves the choice open. Tasks 9.4 (line 391), 9.6 (line 434) and 9.6b (line 479) all build tenants "with a fake clock". A junior implementer could pick `time.monotonic` directly and break every cadence test.

Put a `clock: Callable[[], float]` parameter in the 9.3 signature and say whether it has a default. If it has one, state it once at the config or constructor level. Otherwise the tests become flaky or sleep for the real interval.

### [NOTE] `recorded_since` is asserted in Task 9.6a, before any listing exists

Task 9.6a asserts `recorded_since` true after an in-process `ingest review`. The slice defines `recorded_since` as a column of `amoeba inspect detections`, which is built in Section 10 (file 3). I can't confirm from this file whether a store read from file 1 (`detections()` or a helper) computes it. If the listing module computes it, 9.6a can't assert it. Name the function that provides it, or move the assertion to Task 10.x.

### [NOTE] Task 8.1 edits slice 105's code and tests

The slice's "Interfaces Required" section says 105's design already carries `sourceDocument` into `VerdictInput`. Task 8.1 instead says 105 left that pass-through to this slice and has a test pinning the opposite behavior. That test is changed here. The task traces to D7 and limits the change to one line plus one intended assertion, so I don't consider it scope creep. But it modifies a finished slice's tests and goes beyond what the slice's D7 describes for 104. Have the PM confirm, and have the CHANGELOG task in file 3 mention it.

### [NOTE] No load test or CI gating task, which is consistent with the slice

The slice restates no numeric NFR. Its Settings section says the figures are sizing choices, not promises. The only contractual figure is the follower's "within `follow_interval_seconds`", which Task 7.2 tests functionally. So no `tests/load/` task or CI gate is required. The file states the omission and defers it to Task 11.11 so the PM can overrule it. That is acceptable.

### Run Digest

- Response length: 6730 chars
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
- Duration: 66.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
