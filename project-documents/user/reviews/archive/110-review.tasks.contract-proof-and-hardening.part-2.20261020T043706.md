---
docType: review
layer: project
reviewType: tasks
slice: contract-proof-and-hardening
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261019
dateUpdated: 20261019
reviewedSha: e74eeda4975c66b8d1283514649b5f8c54f3ce03
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 183531
cachedTokens: 93019
cacheWriteTokens: 90506
completionTokens: 4877
durationSeconds: 40.8
costUsd: 0.420778
costBasis: provider
runId: run-20261020-p5-002cb7ae
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit cadence"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F003
    severity: concern
    category: task-scoping
    summary: "Step-12 stub `sq` has no shared home"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:204-231"
  - id: F004
    severity: concern
    category: coverage
    summary: "Ownership guarantee is not asserted for the adopted and checkpoint paths"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:75-108"
  - id: F005
    severity: concern
    category: task-clarity
    summary: "Task 5.5 does not list steps 9 and 11, or step 7's `finding_changes` check"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:94-108"
  - id: F006
    severity: concern
    category: task-sizing
    summary: "Task 6.1 is large for a single task"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:131-146"
  - id: F007
    severity: note
    category: process
    summary: "Task 5.6 and the Gaps Found log"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:112-127"
  - id: F008
    severity: note
    category: proportionality
    summary: "Proportionality"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
---

# Review: tasks — slice 110

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria trace to tasks

- **Scenario, end-state oracle, feed replay:** Tasks 5.1–5.5 cover the D4 scenario, the D5 oracles, and the "seq strictly increasing across steps 4, 5, 10" criterion.
- **Network subset:** Task 6.1 covers D2.
- **Pruning:** Tasks 7.1–7.5 cover the four pruning conditions, the failure modes, the `PRUNE_INCOMPLETE` exit code, and step 12.
- **Docs and validation:** Section 8 covers the process-contract pruning section, the ownership line, the substrate guide, and the CHANGELOG. Task 9.1 covers the walkthrough.
- **File 1 items:** The D1 rule, the tenant-order check, `record_runner_report` and its refusals, and the `test_store_safety` extension all sit in file 1. I checked file 1 for these.
- **No scope creep:** Every task maps to a design decision. No load test or CI task is needed, because the slice states no NFR.

### [PASS] Sequencing and commit cadence

- Dependencies run strictly forward with no cycles.
- Tests directly follow implementation: 5.3 with 5.1–5.2, 7.2 after 7.1, and 7.4 after 7.3.
- Commits are spread across the slice (5.3, 5.4, 5.5, 6.1, 7.2, 7.4, 7.5, 8.1, 8.3, 9.1) rather than batched at the end.
- The gap-stop rule for non-additive fixes (5.6) appears before Section 6.

### [CONCERN] Step-12 stub `sq` has no shared home

Task 7.4 builds the stub `sq` inside `tests/process/test_prune_sq_runs.py`. Task 7.5 needs "the stub on `PATH`" from `tests/contract/test_lifecycle_proof.py`. The task never says where the stub lives so both suites can use it. A junior would either duplicate it, which breaks DRY, or import across test packages. Add a step to 7.4 that places the stub builder in a shared helper or `conftest` fixture. Check that the location is allowed under the D1 import rule for `tests/contract/`.

### [CONCERN] Ownership guarantee is not asserted for the adopted and checkpoint paths

- **What D8 requires:** D8 says "Step 4 asserts this" (recovery's `adopted` result carries `run_id`) and "Steps 3 and 9 assert this" (the issuer's `completed` result carries `run_id`).
- **What 5.2, 5.4, and 5.5 assert:** The oracle declares journal entries by outcome and resolver only, not by `result.run_id`. Task 5.4's step-level assertions do not mention it. Task 5.5 does not mention it for step 9 either.
- **What step 12 covers:** Step 12 covers alpha's checkpoint path only by implication.
- **The uncovered case:** Nothing checks the `adopted` path. A regression there would silently stop pruning of adopted runs.
- **Fix:** Add `result.run_id` presence to the oracle's journal declaration, or to the step-level assertions for steps 3, 4, and 9.

### [CONCERN] Task 5.5 does not list steps 9 and 11, or step 7's `finding_changes` check

- **Missing steps:** The task is titled "Drive steps 7–11" but lists work only for steps 7, 8, and 10, plus the oracles.
- **Steps 9 and 11:** These are Runner `checkpoint` and `finish` intents on alpha and beta. They have no step. Step 9 also has to establish beta's open checkpoint, which step 12's "held" case depends on.
- **Step 7:** The design says `finding_changes` compares the PM-launched artifact with step 4's round. Task 5.5 never asserts that.
- **Fix:** Add explicit steps for 9 and 11, and either the `finding_changes` assertion or a note that the oracle covers it.

### [CONCERN] Task 6.1 is large for a single task

Task 6.1 rated at effort 3 combines five things:
- bootstrap and serve process management;
- SSE parsing and reconnect handling;
- two kill and restart cycles;
- the POST-while-down path;
- a final seq-equality check.

A junior can do this, since it is one test file with one commit. Still, consider splitting it. One task could cover serve kill and `Last-Event-ID` resume. A second could cover the resident-process kill and the final seq-list equality. This would give an intermediate commit before the harder half.

### [NOTE] Task 5.6 and the Gaps Found log

- The "None found" and PM-stop paths are explicit.
- Task 8.3 (CHANGELOG) reads the log, so a stop at 5.6 correctly blocks everything downstream.
- The "(none recorded yet)" placeholder is a checkbox item. Mark it checked or replace it at 5.6 so that "every log entry is marked" is verifiable.

### [NOTE] Proportionality

- The split into two task files fits a slice of effort 3 with 9 sections.
- Test tasks stay proportional. Each is tied to a success criterion, and 7.2 and 7.4 map to the design's listed conditions.
- The steps do dictate some implementation detail, such as the stub modes in 7.4 and the `FileNotFoundError` and `TimeoutExpired` handling in 7.3. In both cases the detail comes from the design's own decisions (D8) and is not extra.

### Run Digest

- Response length: 5746 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 183531 / 93019 / 90506 / 4877 / not computed
- Duration: 40.8 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
