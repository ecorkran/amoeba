---
docType: review
layer: project
reviewType: tasks
slice: outbound-change-feed-and-detection-of-external-work
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 63eb9efb6b38fec581d2cdbd1f514efa2e462865
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 55.6
runId: run-20261015-p5-a36b1511
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Doc-drift test task is not required by any success criterion"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:456-469"
  - id: F002
    severity: concern
    category: scope
    summary: "Demo-script test exceeds what the criteria need"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:341-357"
  - id: F003
    severity: concern
    category: granularity
    summary: "Task 9.1 is a separate harness task with no behaviour of its own"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:399-414"
  - id: F004
    severity: concern
    category: coverage
    summary: "Tenant-level \"deleted between listing and read\" criterion has no test"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:112-117"
  - id: F005
    severity: concern
    category: scope
    summary: "Task 7.1 prescribes a refactor beyond what the slice needs"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:137-138"
  - id: F006
    severity: note
    category: nfr
    summary: "No load test or CI gating task, which is correct for this slice"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:277"
  - id: F007
    severity: note
    category: sequencing
    summary: "Dependency chain is more serial than necessary"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:84-88"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for this file's scope"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:23-538"
  - id: F009
    severity: pass
    category: process
    summary: "Test-with pattern and commit cadence"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:62-80"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Doc-drift test task is not required by any success criterion

Task 9.4 adds `tests/test_contract_docs.py` with a "reusable helper (document path, required terms)". It also asserts that every backticked `amoeba.` name resolves through `importlib`. The slice only asks that `docs/feed-contract.md` be "enough for initiative 160 to consume the feed without reading the code" (Integration Requirements), and no success criterion calls for a doc-versus-code test. The reusable helper serves no consumer in this slice. The doc is also written from the code (Task 9.3, "take names and values from the code"). Cut Task 9.4 and fold a manual check of the names into Task 9.3. If the PM wants the guard, keep only a single `ChangeKind`/`Change`-field check with no generic helper. Then Task 9.3's commit is the `docs:` commit.

### [CONCERN] Demo-script test exceeds what the criteria need

Task 8.3 adds `tests/test_demo_detection.py` covering exit codes, stdout shape, a read-only open and a lock-held refusal case. The slice treats the script as a seeding helper for the walkthrough and end-to-end test, and only requires the writer-guard permitted-list change. Task 9.2 already exercises the script through `seed_demo(env)`, which proves the happy path. The lock-held and "store unchanged" cases test behaviour copied from `demo_evidence.py`, not anything this slice promises. Drop the standalone test module and rely on the Task 9.2 exercise. If the lock-refusal behaviour matters, keep one lock-held test.

### [CONCERN] Task 9.1 is a separate harness task with no behaviour of its own

Task 9.1 builds a thread-based follower collector, a process start/stop/kill wrapper and several helpers. Its own text says it is "exercised by Task 9.2 (no separate smoke tests)", and it is committed with 9.2. It is a prerequisite step inside Task 9.2, not an independently verifiable task. It also carries a conditional launcher edit to `tests/cli_harness.py`. Merge 9.1 into 9.2 as its first steps, or keep it and state plainly that it has no verification of its own. The merged task is large (about Effort 6), so splitting Test A and Test B into separate tasks would keep it junior-sized.

### [CONCERN] Tenant-level "deleted between listing and read" criterion has no test

The slice criterion says that "a file deleted between listing and read produces no ledger row and no error; restored, it is detected normally". Task 6.2 tests this only at the source level, where the file is dropped and settles again. No test asserts that the tenant writes no ledger row. The baseline variant is also untested: Task 7.3 says a file deleted between list and read is dropped from the baseline, but Task 7.4 has no case for it. Task 9.8 would catch the gap late. Add one case to Task 7.6 (patched read raising `FileNotFoundError` during a scan, then no row, then restored and detected). Add one baseline case to Task 7.4.

### [CONCERN] Task 7.1 prescribes a refactor beyond what the slice needs

The slice says only that `sq --version` reuses the "label or explicit unavailable marker" pattern. Task 7.1 dictates moving `VERSION_UNAVAILABLE` into a new `version_label.py`, generalizing `capture_version_label` and touching the import sites. That is a reasonable way to meet DRY, but the steps fix module layout and a helper name that the slice does not require. State the outcome instead: one shared capture routine, the `sq` executable and its version args defined once, and cf behaviour unchanged. Leave the module split to the implementer. The risk is moderate because the cf regression surface is large. The existing cf tests are named as the guard, which mitigates it.

### [NOTE] No load test or CI gating task, which is correct for this slice

The slice sets no numeric NFR targets. The only contract promise is the follower's `follow_interval_seconds` latency bound, which is a documented bound, not a throughput target. No `tests/load/` task or CI wiring task is needed. Task 9.7 reports the omission to the PM, which is the right handling.

### [NOTE] Dependency chain is more serial than necessary

Task 6.1 (`DirectoryReviewSource`) depends on Task 5.3, and Task 7.1 depends on Task 6.2. Neither has a real data dependency on its predecessor. The linear order is harmless for a single implementer, but it hides the fact that Sections 5 and 6 are independent. Nothing needs fixing.

### [PASS] Success-criteria coverage for this file's scope

Each criterion maps to a task:
- **Attribution rule and review-producing kinds:** Tasks 5.1–5.3.
- **Settle rule and race table:** Tasks 6.1–6.2.
- **Baselining, including the unreadable-file case:** Tasks 7.3–7.4.
- **Ingest, provider failure, hand edit, restart, refusals and the label:** Tasks 7.5–7.6.
- **Store error stops the process:** Task 7.6 runs the tenant inside a real `ResidentProcess`.
- **Defer and `runner_issued` skip, plus the directory-removed and reactivation lifecycle:** Tasks 7.7–7.8.
- **`inspect watches` and `inspect detections` with all five states:** Tasks 8.1–8.2.
- **Subprocess only once at start-up:** Tasks 8.4–8.5.
- **End-to-end through the real CLI, including `kill -9` and follower resume:** Task 9.2.
- **Contract docs and changelog:** Tasks 9.3 and 9.5.
- **Final trace of requirements to tests:** Task 9.8.

The deferred items (`read_transaction`, `record_runner_report`, `source_document`) are correctly absent. Real fixtures are used throughout, in line with the Technical Requirements.

### [PASS] Test-with pattern and commit cadence

Every implementation task is followed immediately by its test task: 5.2→5.3, 6.1→6.2, 7.1→7.2, 7.3→7.4, 7.5→7.6, 7.7→7.8, 8.1→8.2 and 8.4→8.5. Commits land at the end of each pair, with semantic prefixes, rather than batched at the end. Task 9.8 keeps the slice branch unmerged, which matches the branch policy in file 1.

### Run Digest

- Response length: 7529 chars
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
- Duration: 55.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
