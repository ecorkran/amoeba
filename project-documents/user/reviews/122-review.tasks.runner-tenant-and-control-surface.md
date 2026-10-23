---
docType: review
layer: project
reviewType: tasks
slice: runner-tenant-and-control-surface
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/122-tasks.runner-tenant-and-control-surface.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: 018be9e1d4c230698c4889558454058e95de2152
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 41
turns: 20
promptTokens: 923151
cachedTokens: 698368
completionTokens: 53757
reasoningTokens: 50082
durationSeconds: 213.4
costUsd: 0.059761
costBasis: alias_pricing
runId: run-20261023-p56-63bf9ff6
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "`UpstreamShapeError` cannot be both unexported and importable by `amoeba.runner`"
    location: "project-documents/user/tasks/122-tasks.runner-and-control-surface.md"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Exit code number for `UPSTREAM_SHAPE` contradicts itself inside Task 2.3"
    location: "src/amoeba/cli/main.py:58-92"
  - id: F003
    severity: concern
    category: test-structure
    summary: "Two helper modules named in the header have no creating task"
    location: "project-documents/user/tasks/122-tasks.runner-tenant-and-control-surface.md"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Over-granular splits: 6.2, 13.2, 13.3 do not earn their own task files"
    location: "project-documents/user/tasks/122-tasks.runner-and-control-surface.md"
  - id: F005
    severity: note
    category: process
    summary: "Commit cadence departs from the standing \"one commit per task\" rule"
    location: "AGENTS.md"
  - id: F006
    severity: note
    category: error-handling
    summary: "The slice's `TickBudget`-coverage test is verified but never authored"
    location: "project-documents/user/tasks/122-tasks.runner-and-control-surface.md"
---

# Review: tasks — slice 122

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] `UpstreamShapeError` cannot be both unexported and importable by `amoeba.runner`

Task 2.3 states `UpstreamShapeError` "is not exported from `amoeba.process` (the pin stays 21 names after Task 3.1)"; Task 11.3 then requires a boundary test asserting "`amoeba.runner` imports `amoeba.store`, `amoeba.process`, `amoeba.upstream` only through public names". `tenant.py` (Task 10.2) must catch and re-raise `UpstreamShapeError`, so it either imports `amoeba.process.errors` — violating 11.3's rule — or requires the name exported, changing the 21-name pin that 2.3 and 13.3 both assert. The slice's API Contracts section is silent. One of the two tasks must change; today a junior AI will implement 2.3, then have 11.3 or 13.3 fail, with no instruction which to relax.

### [CONCERN] Exit code number for `UPSTREAM_SHAPE` contradicts itself inside Task 2.3

The step adds `ExitCode.UPSTREAM_SHAPE = 15` and explains "the LLD says 8, but 8 is `NOT_RUNNING_STATUS`; 15 is the next free value" — a correction I verified against `ExitCode` (0–14 are all taken, and `NOT_RUNNING_STATUS = 8`). But the very next step says "raising `UpstreamShapeError` from a tenant exits 8 and prints the message", and Task 12.3 says "exit 15 when run through `amoeba start`". The test bullet as written asserts the value the same task just declared wrong, so the implementer writes a test that must fail. Say 15 consistently (and note only that the LLD's 8 is stale).

### [CONCERN] Two helper modules named in the header have no creating task

The task-level additions say tests "live in `tests/runner/` (with `__init__.py`), sharing helpers in `tests/runner/conftest.py` and `tests/runner/harness.py`". No task creates `tests/runner/__init__.py`, `conftest.py` or `harness.py`; Task 5.1 creates `test_launch_ids.py` and Task 12.1 creates `crash_entry.py`/`crash_harness.py` (a different file). Either fold their creation into Task 5.1 ("create the package, `conftest.py` and `harness.py` with the shared fake clock/`Popen`/host fixtures the later tasks use") or drop the mention, so the shared fixtures the rest of the file leans on have an owner.

### [CONCERN] Over-granular splits: 6.2, 13.2, 13.3 do not earn their own task files

The file is 40 tasks across 13 sections for a 4/5-effort slice, which is defensible for a high-risk slice; three splits are not. Task 6.2 (`TickBudget`, two steps, effort 2) is a constructor plus `allows_call()` that Task 6.1's `decide` and Task 9.1's tick both depend on — merge into 6.1. Task 13.2 and 13.3 are two documentation/cherry-pick-and-verify steps each; both could be one task with two commits, or 13.3's validation folded into 13.2's success criteria. Cutting these saves three task headers and the associated reading without losing a checkpoint.

### [NOTE] Commit cadence departs from the standing "one commit per task" rule

Task 1.1 explicitly needs no commit, Task 3.1–3.3 is one commit at 3.3, and Task 4.1–4.2 is one commit at 4.2. Each is justified in place (a broken intermediate state, an untestable stub mode), and 3.1's grouping is the honest way to keep the suite green after changing `Observation`. Worth noting only so the reviewer does not treat the grouped commits as missed work.

### [NOTE] The slice's `TickBudget`-coverage test is verified but never authored

The slice's Technical Requirements demand "a test asserts that every tick-time subprocess call goes through `TickBudget` … by injecting a runner that fails the test when it is called after the budget is spent". Task 9.1 covers "the budget is checked before `Popen` and before every poll" and Task 11.1 covers the probe's deadline check, but no task names the injected-runner test itself; Task 13.3 only "verifies" it. If the per-site tests in 9.1 and 11.1 are meant to satisfy it, say so; otherwise add the injection to 9.1's test list.

### Run Digest

- Response length: 5016 chars
- Response is newline-free: no
- Tool calls made: 41
- Tool calls failed: 1
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 184281
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 923151 / 698368 / not computed / 53757 / 50082
- Duration: 213.4 s
- Cost: $0.06 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
