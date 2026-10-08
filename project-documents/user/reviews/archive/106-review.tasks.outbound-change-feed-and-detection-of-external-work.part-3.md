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
reviewedSha: 0fee83708104833e2eac43087fc2ac55009feebd
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 40.1
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: test-design
    summary: "End-to-end parts B and C are written as continuations of part A's state"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:174-196"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Task 11.12 is a large coverage audit with a low effort rating"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:336-380"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 11.1 attributes `start_cli_process` to Task 10.3a, which does not create it"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:135"
  - id: F004
    severity: note
    category: nfr-coverage
    summary: "Load-test and CI-gate omission is explicit and reasoned"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:17"
  - id: F005
    severity: note
    category: coverage
    summary: "Coverage of this file's success criteria is complete"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md:384-423"
  - id: F006
    severity: note
    category: sequencing
    summary: "Commit cadence and test-with pattern are acceptable"
    location: "project-documents/user/tasks/106-tasks.outbound-change-feed-and-detection-of-external-work-3.md:38"
---

# Review: tasks — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] End-to-end parts B and C are written as continuations of part A's state

Task 11.3 adds "a second test … that continues the sequence" from Task 11.2. Task 11.4 adds a third test "starting from a registered, baselined directory with the slice node seeded". Pytest tests must not depend on the state or ordering of other tests. If they do, running one alone fails, and `-k`, `-x`, or xdist runs break. The three-times-consecutive success criteria also fail to isolate flakiness.

The tasks should say how state is shared. Either use one module-scoped fixture that builds the store, process, and follower and is torn down once, or write one long test function. Alternatively, have each test build its own prefix through the 11.1 helpers, such as `seed_demo`, project creation, and registration. Task 11.4 should also say how the `other` project is created, since that needs a running process.

### [CONCERN] Task 11.12 is a large coverage audit with a low effort rating

Task 11.12 checks about 25 requirement-to-test mappings across all earlier sections. For each, the junior must find the named test, run it, and add missing assertions. It is rated Effort 2, and the fix-it-where-missing instruction could grow it a lot. It also names tests such as `test_finding_changes_source_document`, `test_review_detection_refusals`, and `test_review_detection_lifecycle`. These are defined in files 1 and 2 and cannot be checked from this file. If any file 1 or 2 task uses a different test name, the audit will turn up false gaps.

Consider splitting it into Functional and Technical/Integration halves, or raising the effort. Also confirm the names against files 1 and 2.

### [CONCERN] Task 11.1 attributes `start_cli_process` to Task 10.3a, which does not create it

Task 11.1 says to reuse "the helper `start_cli_process` (Tasks 10.3a/10.4)". Task 10.3a creates only the demo script and its tests. `start_cli_process` is conditionally added in Task 10.4, and only if `tests/cli_harness.py` lacks an equivalent. The reference should say 10.4 and allow for the helper not having been added. Otherwise a junior may look for a helper that does not exist.

### [NOTE] Load-test and CI-gate omission is explicit and reasoned

The slice sets no numeric NFR targets. The 0.25 s follow interval, 2 s scan interval, and roughly 5 s detection latency are described as sizing choices, not promises. The one stated promise is the follower's bound in `feed-contract.md`. The header and Task 11.11 record why no `tests/load/` task or CI gate exists and ask the PM to confirm. This is acceptable. If the PM treats the follower latency bound as an NFR, a load test and a CI task would be needed.

### [NOTE] Coverage of this file's success criteria is complete

- **Listings:** `inspect watches` and `inspect detections` are covered by 10.1 and 10.2.
- **Wiring and subprocess rule:** `start` wiring, the once-only `sq --version`, the failure paths, and "no tick starts a subprocess" are covered by 10.3 and 10.4.
- **Writer guard and demo script:** covered by 10.3a.
- **End-to-end flow:** follower while the process is stopped, kill -9, provider failure, `--after` resume, and agreement between follower and inspect are covered by 11.2 and 11.3.
- **Refusals:** the unattributed and unparseable files and the hand-edit/no-second-verdict case are covered by 11.4.
- **Docs and changelog:** the five contract documents, `CHANGELOG`, and the 103 forward reference are covered by 11.5–11.9. The doc-drift test in 11.6 is a useful guard.
- **Final checks:** 11.10, 11.11, and 11.12 cover the final gates, the walkthrough, and the requirement trace.

I found no scope creep. The `build_tenants` extraction in 10.3 and the 11.1 harness module both serve testability.

### [NOTE] Commit cadence and test-with pattern are acceptable

Implementation tasks 10.1, 10.3, and 11.5 commit together with their paired test tasks (10.2, 10.4, 11.6). Every other task commits on its own. Commits are spread throughout the file, not batched at the end. Task 10.3a sits between 10.3 and its test in 10.4, with a stated reason. Dependencies run in one direction with no cycles.

### Run Digest

- Response length: 5423 chars
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
- Duration: 40.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
