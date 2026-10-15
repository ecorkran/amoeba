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
reviewedSha: 4395a7694957241fac827b9f790727d13ccd22ba
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
durationSeconds: 57.1
runId: run-20261015-p5-a36b1511
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria in this file's scope are covered"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:23-523"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Task 9.1 is too large for one junior task"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:398-416"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 7.6 is oversized, and its split is left conditional"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:233-255"
  - id: F004
    severity: concern
    category: test-with-pattern
    summary: "Scan-time reachability and reactivation tests are separated from the code they test"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:289"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Some tasks and tests can be merged or cut"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:25-58"
  - id: F006
    severity: note
    category: sequencing
    summary: "Artificial linear dependencies and a late-tested script"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:84-88"
  - id: F007
    severity: note
    category: scope
    summary: "`review_scan.py` is not in the slice's component structure"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:217"
  - id: F008
    severity: note
    category: prompt-hygiene
    summary: "Hard-coded example next to a \"look it up\" instruction"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-2.md:172"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria in this file's scope are covered

- **Detection:** ingest, provider failure, hand edit, `unattributed`, `unparseable`, hand recovery, restart and store-failure-stops-process map to 7.6. Baseline, unreadable file and pre-existing directory map to 7.4.
- **Ownership:** defer and `runner_issued` are in 7.8, and `deferred` in `inspect watches` is in 8.2.
- **Sources and wiring:** the race table and "deleted between listing and read" are in 6.2, and "`sq --version` once, no subprocess per tick" is in 8.5.
- **Follower and integration:** "follower while the process is stopped" and the `resolution` → `runnable` change are in 9.1. The `kill -9` scenario is in 9.2.
- **Docs and guard:** the doc deliverables are in 9.3–9.4, and the writer-guard addition is in 8.3.
- **Load test:** the slice states no NFR, so no load test or CI gate is needed. 9.6 tells the PM this.
- **Commits:** commit checkpoints are spread across every section, and each implementation task is paired with its test or the next task's commit.

### [CONCERN] Task 9.1 is too large for one junior task

Effort 4 bundles three pieces of work:
- possibly adding a CLI launcher to `tests/cli_harness.py`;
- building a new harness module with about seven helpers (process control, a threaded follower collector, `seed_demo`, `copy_fixture`, `inspect_json`);
- writing a long, order-sensitive end-to-end Test A with a three-consecutive-runs gate.

If the harness is wrong, the test failure is hard to diagnose. Split it into a harness task (launcher plus `detection_e2e_harness.py`, with a smoke check such as start, stop and follower prints one line) and a Test A task. 9.2 then depends only on the harness and Test A.

### [CONCERN] Task 7.6 is oversized, and its split is left conditional

- **Size:** it carries nine behavior groups: ingest rounds, provider failure, hand edit, restart, race, refusals, label, hand recovery, and store failure inside a real `ResidentProcess`. A junior will probably exceed the ~300-line module limit.
- **Conditional split:** the success criterion says "split into a second module if this one passes ~300 lines". That decision belongs in the task plan, not at execution time.
- **Suggested split:** pre-split into (a) ingest, provider failure, hand edit, restart and race, and (b) refusals, label, hand recovery and store failure. Each half then gets its own commit.

### [CONCERN] Scan-time reachability and reactivation tests are separated from the code they test

- **Misplaced bullet:** 7.8 ends with "Remaining LLD lifecycle bullets": a baselined directory removed and restored (one ERROR, one INFO), and deactivate/reactivate without re-baselining. 7.8 is the defer/ownership test, but those behaviors are implemented in 7.3 and 7.5, not 7.7.
- **Result:** the scan-path reachability code from 7.5 goes untested through 7.6 and 7.7. The module name `test_review_detection_ownership.py` also no longer describes its contents.
- **Fix:** move these bullets into 7.6, immediately after 7.5, or into a small lifecycle module there.

### [CONCERN] Some tasks and tests can be merged or cut

- **5.1 and 5.2:** both are Effort 1, edit a few lines each, and are tested together in 5.3. Merge them into one implementation task followed by 5.3.
- **7.8 non-review kind:** "an open entry of a non-review kind does not defer" repeats a case 5.3 already pins at the store-read level, and the tenant just calls that read. Drop it or reduce it to one assertion.
- **9.7:** the trace walk mostly repeats 9.5's full suite, and 9.2 already ends with named assertions. The only unique value is catching a missing assertion. Fold it into 9.6 as one step, or keep it but state that it adds no new test files.

### [NOTE] Artificial linear dependencies and a late-tested script

- **Unneeded chains:** 6.1 depends on 5.3 and 8.3 depends on 8.2, but neither needs the earlier task's output. The ordering is harmless and only serializes work.
- **Late-tested script:** `scripts/demo_detection.py` (8.3) has no test until 9.1, so a defect surfaces a task and a half later. This is acceptable because the task says so explicitly.
- **8.2 wording:** it says states are staged by "writing store rows directly (no tenant)". `unreachable` also needs a nonexistent directory on disk, and `deferred` needs a journal entry. Say so.

### [NOTE] `review_scan.py` is not in the slice's component structure

The slice's Component Structure lists only `review_sources.py` and `review_detection.py` under `process/`. Task 7.5 adds a third module, `review_scan.py`, to stay under ~300 lines. That is a reasonable call, but update the slice's component list, or note it as a task-level addition in file 1's list, so the design and plan agree.

### [NOTE] Hard-coded example next to a "look it up" instruction

Task 7.3 says "Check `InboxTenant`'s constructor for what else it needs (e.g. `supervisor_dir`)". This is the pattern the project guidelines warn about: if the lookup yields nothing, a model may reach for the example. Here `supervisor_dir` is real, since 8.4 uses it. Still, drop the "e.g." and say "mirror every constructor argument `InboxTenant` takes beyond the store".

### Run Digest

- Response length: 6654 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 57.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
