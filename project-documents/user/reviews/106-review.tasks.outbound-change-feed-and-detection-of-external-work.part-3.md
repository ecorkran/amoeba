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
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: a92fb441db4f98e35252946dc0dcbd28d323284a
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 71.9
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 10.3 is left uncommitted across Task 10.3a, and its tests come two tasks later"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:63-98"
  - id: F002
    severity: concern
    category: requirements-clarity
    summary: "`inspect detections --outcome` leaves parked (`failed`) rows undefined"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:33"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 10.4 bundles four independent tests and duplicates setup that Task 11.1 later formalizes"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:102-122"
  - id: F004
    severity: concern
    category: coverage
    summary: "Task 11.12 relies on a catch-all to add assertions, and its cited coverage is not in the e2e tasks"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:336-370"
  - id: F005
    severity: note
    category: nfr-coverage
    summary: "No load test or CI gate task"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:17"
  - id: F006
    severity: note
    category: coverage
    summary: "The published follower latency bound is not tested"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:321"
  - id: F007
    severity: note
    category: process
    summary: "File-size check happens only at the end"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:301-314"
  - id: F008
    severity: pass
    category: coverage
    summary: "Sections 10–11 cover the remaining LLD deliverables, sequenced and traceable"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:22-398"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 10.3 is left uncommitted across Task 10.3a, and its tests come two tasks later

Task 10.3 (the `lifecycle.py` refactor and tenant registration) says "Committed with Task 10.4". Task 10.3a sits between them with its own commit (`feat(scripts): add demo_detection seeding script`). The 10.3 changes would either sit uncommitted through 10.3a or be swept into 10.3a's commit. That breaks the test-with pattern and the "commit at least once per task" rule. 10.3a's stated dependency on 10.3 is also unnecessary. The seeding script and its test need neither the tenant nor `build_tenants`. Move 10.3a before 10.3, depending on 10.2. Then 10.3 and 10.4 are adjacent and commit together.

### [CONCERN] `inspect detections --outcome` leaves parked (`failed`) rows undefined

Task 10.1 takes the `--outcome` choices from `DetectionOutcome`. It also merges parked files into the listing as `failed` rows. The LLD (Errors section) says `failed` is a listing state, not a `DetectionOutcome`. The task does not say what `--outcome unattributed` does with parked rows (presumably excludes them). It also does not say whether `--outcome failed` is allowed. That would need a second source of choices, which conflicts with the "defined once" rule. Task 10.2 tests the filter but not this interaction. State the rule and add a test case.

### [CONCERN] Task 10.4 bundles four independent tests and duplicates setup that Task 11.1 later formalizes

Task 10.4 contains these pieces:
- a long-lived CLI-subprocess `kill -9` test;
- a call-count test for `build_tenants`;
- a three-variant `sq --version` failure matrix (non-zero exit, absent, timeout);
- a `subprocess.run`-raises test over several ticks.

It may also add a `start_cli_process` helper. The subprocess case needs the stop, seed, restart sequence, which 10.4 never states. Task 11.1 then builds `start_process` and `build_scenario` doing the same thing. Split it into 10.4 (in-process: label capture, failure matrix, no-subprocess) and 10.4a (CLI subprocess restart test). Have 10.4a state the full setup sequence explicitly. Put any shared start helper in one place, so 11.1 reuses rather than reinvents it.

### [CONCERN] Task 11.12 relies on a catch-all to add assertions, and its cited coverage is not in the e2e tasks

Task 11.12 maps the "real file recorded with `source: artifact_frontmatter`, `source_path`" criterion to "end-to-end part A". Task 11.2's assertions cover only the follower's change lines, the verdict count, and the ledger rows. They do not check `source` or `source_path`. Task 11.12 absorbs such gaps with "where the named test lacks the assertion, add it". It is effort 4 and spans about 20 requirements. Add the `--json` `source` and `source_path` assertion to 11.2 where it belongs. Consider splitting 11.12 into two tasks of about 10 requirements each, so the late pass is verification rather than first-time test writing.

### [NOTE] No load test or CI gate task

The slice states no NFR with a numeric target. It says the parent architecture "sets no numeric targets" and presents the intervals as "this slice's choices". The omission is justified, and no CI wiring task is needed. Task 11.11 surfaces the decision to the PM for override, which is the right place.

### [NOTE] The published follower latency bound is not tested

`feed-contract.md` will promise "within `follow_interval_seconds` of the commit, plus the time to read the new rows" (Task 11.5). No task asserts it. The walkthrough's "within a second" is only a manual check. A bounded `wait_for` in the end-to-end tests, with a generous multiple of the interval, would give the promise a regression guard. This is optional.

### [NOTE] File-size check happens only at the end

Task 11.10 is the first place that checks the ~300-line limit (`wc -l`) and splits oversized modules. A split at that point means refactoring files after all their tests are written. The import-boundary tests have guarded every task, but nothing guards file size. Consider adding a per-task `wc -l` check in files 1 and 2, or accept the late refactor risk knowingly.

### [PASS] Sections 10–11 cover the remaining LLD deliverables, sequenced and traceable

These LLD deliverables all have owning tasks:
- two listings (10.1/10.2);
- `start` wiring and the once-at-start `sq --version` label (10.3/10.4);
- `scripts/demo_detection.py` with the writer-guard entry (10.3a);
- end-to-end tests for the three scenarios in the LLD's Integration Requirements (11.2–11.4);
- `feed-contract.md` with a doc-vs-code test (11.5/11.6);
- the four contract updates and `CHANGELOG` (11.7–11.9);
- the 103 forward-reference fix required by D8a (11.9);
- the final gates and walkthrough (11.10/11.11);
- requirement traceability (11.12/11.12a).

I found no circular dependencies and no scope creep. The doc-test helper is the closest thing, and it is justified by the `feed-contract.md` completeness criterion. Commits are spread across tasks, and the end-to-end tasks require three consecutive passes and a solo run.

### Run Digest

- Response length: 6422 chars
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
- Duration: 71.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
