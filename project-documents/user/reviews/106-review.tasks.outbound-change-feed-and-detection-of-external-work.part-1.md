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
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: a92fb441db4f98e35252946dc0dcbd28d323284a
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 71.5
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria owned by this file are covered, with tests following implementation"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:158-270"
  - id: F002
    severity: pass
    category: scope
    summary: "No scope creep; task-level additions are justified and tracked"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:137-156"
  - id: F003
    severity: note
    category: nfr-coverage
    summary: "Load test and CI gating do not apply"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:314-321"
  - id: F004
    severity: concern
    category: documentation
    summary: "`baseline_watch` and `BaselineEntry` are not queued for contract documentation"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:512-527"
  - id: F005
    severity: concern
    category: test-design
    summary: "Import-boundary Rules 3 and 4 may produce false positives with no stated escape for Rule 3"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:137-156"
  - id: F006
    severity: concern
    category: task-sizing
    summary: "Task 5.2 bundles five independent test changes across three files"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:450-468"
  - id: F007
    severity: note
    category: task-clarity
    summary: "Task 5.3's Files-to-Modify list doesn't match its steps"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:478-489"
  - id: F008
    severity: note
    category: sequencing
    summary: "Linear dependency chain is stricter than necessary"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:427-431"
  - id: F009
    severity: note
    category: design-fidelity
    summary: "`recorded_since` is narrower than the slice design's wording"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-1.md:439"
---

# Review: tasks — slice 106

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria owned by this file are covered, with tests following implementation

- **Emission and invariant:** the slice's "every write to a tracked table emits its change" criterion maps to Tasks 2.1–2.3 and the invariant test in 2.4–2.6. Task 5.2 extends the invariant test when `detected_reviews` arrives.
- **Version-5 upgrade:** this maps to Task 1.4.
- **Atomic snapshot:** the `read_transaction()` criterion maps to Tasks 4.3–4.4, including a control case that proves the primitive is what makes the difference.
- **`source_document`:** this maps to Tasks 3.1, 3.1a and 3.2, with the part-1/part-2 separation test.
- **Watches and baseline:** the `watch_reviews` kind and baseline atomicity map to Tasks 5.3–5.6.
- **Sequencing and commits:** Tasks 1.3/1.4, 2.1/2.2, 4.1/4.2, 4.3/4.4, 5.1/5.2, 5.3/5.4 and 5.5/5.6 commit in pairs. No behavior is committed untested, and commits are spread across all five sections.

### [PASS] No scope creep; task-level additions are justified and tracked

Tasks 1.6, 4.3 and 5.1 add things the slice design doesn't spell out, and each traces back to it:
- **Task 1.6** (the import-boundary test) traces to the Technical Requirements on layering and single definitions.
- **Task 4.3** (the `read_only` constructor flag) is the mechanism behind D1a.
- **Task 5.1** (`recorded_since`, `DetectionInput`) backs the `inspect detections` column.

Tasks 4.3 and 5.1 name where each addition is recorded (Tasks 11.7, 11.8 and 11.11).

### [NOTE] Load test and CI gating do not apply

The slice says "the parent architecture sets no numeric targets". It restates no NFR, so no `tests/load/` task or CI gating task is required. The follower latency bound is a contract statement checked by the follower tests in file 2, not an NFR carried down from a parent.

### [CONCERN] `baseline_watch` and `BaselineEntry` are not queued for contract documentation

- **Gap:** Task 5.1 says `recorded_since` and `DetectionInput` are task-level additions and must be recorded in `store-contract.md` in Task 11.7. Task 5.5 adds `baseline_watch` and `BaselineEntry`, which the slice's API table also doesn't list, but says nothing about documenting them.
- **Risk:** The public store surface would ship with an undocumented method that the tenant depends on. `tests/test_contract_docs.py` wouldn't catch it unless a required term is added.
- **Fix:** Add the same "record in `store-contract.md` in Task 11.7" line to Task 5.5, and make sure 11.7 lists it.

### [CONCERN] Import-boundary Rules 3 and 4 may produce false positives with no stated escape for Rule 3

- **Rule 3** scans every string constant under `src/amoeba/` for a SQL keyword plus the whole word `changes`, `review_watches` or `detected_reviews`. The word `changes` is common in docstrings, log messages and the existing `inspect changes` listing. Docstrings are excluded only for Rule 4, not for Rule 3.
- **Rule 4** tells the implementer to stop and ask the PM on an unrelated hit, but Rule 3 gives no such instruction.
- **Risk:** A junior AI could reach for an allowlist or reword unrelated strings to make the rule pass.
- **Fix:** State that Rule 3 also excludes docstrings, and give it the same "stop and tell the PM, do not add an allowlist entry" instruction as Rule 4.

### [CONCERN] Task 5.2 bundles five independent test changes across three files

Task 5.2 is rated Effort 2, but it holds five separate pieces of work across three files:
- the ledger tests,
- the trigger cases,
- the `recorded_since` cases, including the overridden-id limitation,
- the invariant-test extension, which also deletes the `REVIEW_DETECTED` exception constant,
- a new drop-trigger parametrization case.

This is the task most likely to leave a half-finished state for a junior AI. Consider splitting it: ledger and trigger tests stay in 5.2, and a new Task 5.2a carries the invariant-test extension and the drop-trigger case. Both would still commit with the 5.1 behavior.

### [NOTE] Task 5.3's Files-to-Modify list doesn't match its steps

The steps put `WatchReviewsPayload` in `inbox/envelope.py` and the effect in `store/inbox.py`. The list names `store/inbox_models.py`, which the steps don't mention, and doesn't name `cli/submit.py` or the tests that pin the kind set. The steps also add a `review_watches` upsert, which goes in `sql_feed.py`; that file is on the list. The implementer will probably sort this out, but the list should match the steps.

### [NOTE] Linear dependency chain is stricter than necessary

Task 5.1 depends on Task 4.4 (`read_transaction()`), but `record_detection` needs only the `FeedOperations` mixin from Tasks 4.1/4.2. The strict chain is harmless for a single implementer. It does hide that the `read_transaction()` work (4.3/4.4) could be done later or in parallel without blocking detection storage.

### [NOTE] `recorded_since` is narrower than the slice design's wording

- **The gap:** The slice design says `recorded_since` is true when a verdict with that `record_id` exists, "however it got there". Task 5.1 implements it as "a verdict whose id equals `record_id`", so a verdict recorded under an overridden id (`--id`, or a Runner-supplied id) is not seen.
- **How it's handled:** The task says so openly and adds a test for it in 5.2. This follows from how 105's D5 defines the default id.
- **Action:** Put the limitation in the Task 11.11 PM report. It narrows the slice design's "however it got there" and should be a conscious decision rather than a silent one.

### Run Digest

- Response length: 7385 chars
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
- Duration: 71.5 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
