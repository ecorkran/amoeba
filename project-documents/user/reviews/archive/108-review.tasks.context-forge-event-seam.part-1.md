---
docType: review
layer: project
reviewType: tasks
slice: context-forge-event-seam
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: bd800af745253d59f5b55593780327acd05bc420
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
durationSeconds: 53.2
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:320-347"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Feed trigger is committed without its behavioural test until Task 3.7"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:166-205"
  - id: F003
    severity: concern
    category: testability
    summary: "Rollback test in Task 3.6 cannot force its failure as written"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:253"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Tasks 6.3 and 6.5 are oversized, and their test files risk the 300-line guidance"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:70-127"
  - id: F005
    severity: concern
    category: test-quality
    summary: "Success-path tests that need the real `cf` CLI can skip silently"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:81, 215, 328-341"
  - id: F006
    severity: note
    category: task-sizing
    summary: "Task 6.4 is a test-only task that largely repeats Task 6.3's assertions"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:92-108"
  - id: F007
    severity: note
    category: test-quality
    summary: "The boundary test in Task 8.4 may be brittle"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-2.md:277"
  - id: F008
    severity: note
    category: dependencies
    summary: "Prerequisites on 106 are stopped on, not worked around"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam-1.md:47-49"
  - id: F009
    severity: note
    category: nfr
    summary: "No load-test or CI-gating task is needed"
    location: "project-documents/user/slices/108-slice.context-forge-event-seam.md:260-290"
---

# Review: tasks — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage is complete

Each Functional Requirement maps to a task and test:
- First snapshot, a single-key change, noise-only writes, unlinked projects, remove and restore, and `missing`: Task 6.3.
- Down-time catch-up: Tasks 6.3, 7.4 and 8.1.
- `unreachable` and `unrecognized`: Task 6.2.
- Deactivate and reactivate: Tasks 4.2 and 6.3.
- Bounded failure: Task 6.5.
- Idle tick: Tasks 6.1 and 6.4.

Each Technical Requirement also has a task:
- Single definitions and import boundaries: Task 8.4.
- 7→8 upgrade: Task 3.3.
- Invariant extension: Task 3.7.
- Real fixtures: Task 1.2.
- Contract docs: Tasks 8.2 and 8.3.

I found no uncovered criterion and no scope creep. The three extras (the `cf_watch_revision` counter, the `--cf-max-attempts` flag, and the label timing) are each flagged in the tasks and reported to the PM in Task 8.6.

### [CONCERN] Feed trigger is committed without its behavioural test until Task 3.7

Task 3.2 creates the `AFTER INSERT ON cf_snapshots` trigger, and Task 3.3 commits it. Task 3.3 only checks that the trigger exists in `sqlite_master`. Task 3.7, four tasks later, is the first to assert what the trigger emits: payload shape, the JSON boolean for `present`, `changed` equal to the stored value, and rollback behaviour. This breaks the test-with pattern and the "a commit never holds untested behavior" rule in the file's own commit-cadence note. Either move the trigger-emission cases into Task 3.6 or 3.7 and commit them with 3.5–3.6, or add a minimal emission assertion to Task 3.3 using a raw insert.

### [CONCERN] Rollback test in Task 3.6 cannot force its failure as written

The test says to force a mid-transaction failure "with an invalid state". Task 3.2 says no `CHECK` on vocabulary columns, and Task 3.6 doesn't say the combined method validates `state`. A bad state string would therefore insert without error and the atomicity test would pass vacuously or fail confusingly. Specify the forcing mechanism. Either the method validates the state against `CFWatchState`, or the test uses a watch that doesn't exist, which `set_cf_watch_state` is already specified to raise on. The second option is the simpler fix.

### [CONCERN] Tasks 6.3 and 6.5 are oversized, and their test files risk the 300-line guidance

Task 6.3 combines the per-watch diff loop, the combined record call, label wiring, and a test file of about twelve scenarios. Those scenarios run against the real `cf` CLI, with several `cf init` and `cf set` setups. Task 6.5 combines a new module, sidecar attempt logic, `failed` skipping, per-scan sidecar existence checks, and a five-scenario test file. Each is rated Effort 4 but mixes several separable behaviours. A junior AI would have trouble landing each with a clean commit and a test file under about 300 lines. Suggested splits:
- **Task 6.3:** snapshot logic and its tests (link, change, noise, unlinked), then lifecycle cases (remove/restore, inactive/reactivate, restart/catch-up) in a second test file.
- **Task 6.5:** `cf_layout.py` with its tests, then the attempt/skip logic.

### [CONCERN] Success-path tests that need the real `cf` CLI can skip silently

The design requires that "no hand-built file stands in for the real shape in the success-path tests". Tasks 6.3 and 8.1 skip when `cf` isn't on `PATH`. Nothing says CI or the developer environment guarantees `cf`, and Task 8.7 runs the tests "by name" without checking for skips. If `cf` is absent, the most important tests (snapshots, end-to-end) skip, and the suite stays green while the requirement is unproven. Make Task 8.7 and the final validation fail if those tests were skipped, for example by reporting skip counts. Alternatively, state in Task 1.1 that `cf` must be installed to proceed, and say how CI provides it.

### [NOTE] Task 6.4 is a test-only task that largely repeats Task 6.3's assertions

Task 6.4 has one real step, "confirm the tenant stores whatever `capture_label()` returns", plus a small test file. Task 6.3 already asserts the label is called once per recording read. Folding 6.4's tests into 6.3's split-out lifecycle test file would remove a task. Keeping it separate is harmless.

### [NOTE] The boundary test in Task 8.4 may be brittle

The check that `CONTEXT_FORGE_DATA_DIR` appears in exactly one source module could trip on help text in `cli/settings_flags.py` or docstrings. It could also trip on any 102 code that already mentions the variable. Scope the search to code literals, or allow a documented exception list.

### [NOTE] Prerequisites on 106 are stopped on, not worked around

Task 1.1 stops if 106 isn't merged, and handles the 007/008 migration numbering ambiguity explicitly. The `test_contract_docs.py` and `test_import_boundaries.py` files that Tasks 8.2–8.4 extend are not in the repo at this commit (my glob found neither). They are 106's files, so the Task 1.1 gate covers them. Reaching Task 8.2 without them means 106's tasks need re-checking.

### [NOTE] No load-test or CI-gating task is needed

The slice restates no quantitative NFR. The idle-tick behaviour ("one `stat`, no file read, no query") is functional and is asserted with call-count spies in Tasks 6.1 and 6.4. A `tests/load/` task and a CI-gate task are therefore not required.

### Run Digest

- Response length: 6808 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 53.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
