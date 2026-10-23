---
docType: review
layer: project
reviewType: tasks
slice: runner-tenant-and-control-surface
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
recoveryTurn: true
sourceDocument: project-documents/user/tasks/122-tasks.runner-tenant-and-control-surface.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: d475b85bc236298f8a57d78c9991b04266cd3400
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 29
turns: 20
promptTokens: 971740
cachedTokens: 768512
completionTokens: 68410
reasoningTokens: 64826
durationSeconds: 299.3
costUsd: 0.064909
costBasis: alias_pricing
runId: run-20261023-p56-63bf9ff6
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: fail
    category: error-handling
    summary: "`ExitCode.UPSTREAM_SHAPE = 8` collides with the shipped `NOT_RUNNING_STATUS = 8`"
    location: "src/amoeba/cli/main.py:92"
  - id: F002
    severity: fail
    category: testing
    summary: "The public-API pin count is wrong: the test pins 20 names, not 13"
    location: "tests/test_process_public_api.py:13"
  - id: F003
    severity: concern
    category: testing
    summary: "`mint_run_id` is 36 characters, not the 38 the test is told to assert"
    location: "project-documents/user/tasks/122-tasks.runner-tenant-and-control-surface.md:176"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Observe needs `FaultKind` before the task that defines it, creating a dependency cycle"
    location: "project-documents/user/tasks/122-tasks.runner-tenant-and-control-surface.md:236"
  - id: F005
    severity: concern
    category: documentation
    summary: "Two shipped statements that \"no tick starts a subprocess\" stay false after the slice"
    location: "src/amoeba/process/tenants.py:30"
  - id: F006
    severity: note
    category: test-coverage
    summary: "The \"123 and 125 need no change to `tenant.py` or `launch.py`\" criterion has no verifying task"
    location: "project-documents/user/tasks/122-tasks.runner-and-control-surface.md:406"
---

# Review: tasks — slice 122

**Verdict:** FAIL
**Model:** deepseek/deepseek-v4.1-flash
**Recovery turn:** used — the first reply ended without a review, and this review came from one follow-up prompt

## Findings

### [FAIL] `ExitCode.UPSTREAM_SHAPE = 8` collides with the shipped `NOT_RUNNING_STATUS = 8`

Task 2.3 (task file line 95) instructs "Add `ExitCode.UPSTREAM_SHAPE = 8`", and its own test item on line 96 says "the exit code values are unchanged for all existing members" — which contradicts it. `ExitCode` already assigns `8` to `NOT_RUNNING_STATUS` (`src/amoeba/cli/main.py:92`), and the vocabulary now runs through `PRUNE_INCOMPLETE = 14` (line 118). Following the task literally either overwrites `NOT_RUNNING_STATUS` (breaking `amoeba status`'s contract) or trips the task's own assertion. The next free member is `15`, and `docs/process-contract.md`'s exit-code table must gain the matching row — Task 13.1 currently says only "exit code 8".

### [FAIL] The public-API pin count is wrong: the test pins 20 names, not 13

Task 3.1 (line 113) says "update `__all__` and the pinned list in `tests/test_process_public_api.py` from 13 names to 14", and Tasks 2.3, 13.1 and 13.3 all repeat "14 names". The actual `EXPECTED_EXPORTS` in `tests/test_process_public_api.py:13-35` contains **20** names — slice 120 added `RunOutcome`, `OUTCOME_EXIT_CODES`, `RunCheckpoint`, `RunOutcomeDocument`, `PollFailure`, `RunPoll` and `poll_run` without updating `docs/process-contract.md`, whose table at `docs/process-contract.md:189-197` still lists 13. A junior AI following this instruction would rewrite the pin to 14 names, silently deleting six of 120's names from the contract test, or would be unable to satisfy it without weakening the test. The correct pair is 20 → 21 in the test, and the docs table needs backfilling to 20 before it becomes 21. Task 13.3's verification line ("public API pins 14 names") and Task 13.1's ("hosting surface 14 names") carry the same error.

### [CONCERN] `mint_run_id` is 36 characters, not the 38 the test is told to assert

Task 5.1 requires "a fixed `now` gives the expected prefix and 38 characters". The LLD's own example format, `amoeba-<UTC yyyymmddTHHMMSSZ>-<12 hex>`, is 7 + 16 + 1 + 12 = **36** characters (`amoeba-20261020T221144Z-3f9a1c0d2b7e` is 36). A test asserting 38 fails on correct code, and a junior AI resolving that failure is most likely to pad the id — a silent change to the minted-id format that also breaks the `SQUADRON_RUN_ID_PATTERN` property test's intent. The LLD's "That is 38 characters" (via D5) should be corrected to 36 and the assertion in Task 5.1 follow it.

### [CONCERN] Observe needs `FaultKind` before the task that defines it, creating a dependency cycle

Task 7.1 (observe) requires recording the project-scoped faults `run_observation_failed` and `launch_overdue`, but `FaultKind` is created in Task 10.1 ("Create `runner/faults.py`"), and 10.1 depends on 9.1 → 8.1 → 7.1. That is a cycle: 7.1 → 10.1 → 9.1 → 8.1 → 7.1. Task 5.3 and Task 10.1 both insist `LaunchFailure` is "defined once", so the same "define it once locally in 7.1" escape is explicitly closed. A junior AI working the sections in the stated order either stalls at 7.1 or duplicates the enum, violating the "no magic values / one definition site" rule. Move `faults.py`'s vocabulary (or at least `FaultKind` and `STORE_FAILURES`) to a task before Section 7, and keep the escalation-write logic where it is.

### [CONCERN] Two shipped statements that "no tick starts a subprocess" stay false after the slice

The slice turns "no tick starts a subprocess" into an outdated claim. Task 2.1 removes it from `ProcessSettings.sq_timeout_seconds` (`src/amoeba/process/settings.py:64`) and Task 13.1 replaces it in `docs/process-contract.md:216`. The identical assertion survives in `src/amoeba/process/tenants.py:30` ("no tick ever starts a subprocess"), `src/amoeba/process/cf_watch.py:15`, and `docs/context-forge-contract.md:189`, and no task touches them. The process contract is the document downstream slice designs are told to trust without reading the implementation, and it will now assert the opposite of `src/amoeba/runner/`'s behaviour in two places. Add these three locations to Task 13.1's edit list — a mechanical `grep -n "tick starts a subprocess"` would have surfaced them.

### [NOTE] The "123 and 125 need no change to `tenant.py` or `launch.py`" criterion has no verifying task

The slice's third Integration Requirement is that 123 and 125 "can add their reads and planner without changing `tenant.py` or `launch.py`". Tasks 13.3 checks module length, the single `except Exception`, the public-API pin and the budget test, but nothing checks this property. It is inherently hard to test forward-looking, so the absence is defensible — but if the intent is enforceable, the closest mechanical proxy is asserting that `tenant.py` and `launch.py` expose no store-read seams beyond what the seam contract names, which Task 13.3 could state as a one-line inspection.

### Run Digest

- Response length: 6282 chars
- Response is newline-free: no
- Tool calls made: 29
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 237737
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 971740 / 768512 / not computed / 68410 / 64826
- Duration: 299.3 s
- Cost: $0.06 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
- Recovery turn used: yes (the follow-up reply is included below)
