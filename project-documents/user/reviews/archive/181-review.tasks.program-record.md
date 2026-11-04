---
docType: review
layer: project
reviewType: tasks
slice: program-record
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/181-tasks.program-record.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 879641bf1ab21aab64f48280a44a83cf945b7bd1
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 25
effort: xhigh
turns: 26
promptTokens: 665302
cachedTokens: 507928
cacheWriteTokens: 157362
completionTokens: 40664
durationSeconds: 289.8
costUsd: 0.160371
costBasis: provider
runId: run-20261104-tasks-plan-a982fbc3
squadronVersion: 0.24.19
findings:
  - id: F001
    severity: concern
    category: coverage
    summary: "Task 1.4 caller list misses three source files and one test"
    location: "project-documents/user/tasks/181-tasks.program-record.md:83"
  - id: F002
    severity: concern
    category: testing
    summary: "The load tier never runs on the changed tick path"
    location: "project-documents/user/tasks/181-tasks.program-record.md:276"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 9.2 gates unrelated docs and checks on `sq`"
    location: "project-documents/user/tasks/181-tasks.program-record.md:279"
  - id: F004
    severity: note
    category: instructions
    summary: "Task 9.2 hardcodes a dated `sq` path"
    location: "project-documents/user/tasks/181-tasks.program-record.md:279"
  - id: F005
    severity: note
    category: scope
    summary: "Task 1.5 leaves the destination of `GLOB_WILDCARD` open"
    location: "project-documents/user/tasks/181-tasks.program-record.md:90"
  - id: F006
    severity: note
    category: testing
    summary: "Task 2.10 does not name the `register_member` rejection codes"
    location: "project-documents/user/tasks/181-tasks.program-record.md:139"
  - id: F007
    severity: note
    category: granularity
    summary: "Size is proportionate to the slice"
    location: "project-documents/user/tasks/181-tasks.program-record.md:1"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success criteria are covered, test-with ordering holds, and markers sit at tested points"
    location: "project-documents/user/tasks/181-tasks.program-record.md:57"
---

# Review: tasks — slice 181

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 1.4 caller list misses three source files and one test

The task names `runner/dispatch/facts.py`, `build_view.py` and `answering/sources.py` as the callers to update. Three more import `Checkout` from `runner/dispatch/checkout.py`, the module the task deletes: `runner/dispatch/candidates.py:15`, `runner/dispatch/planner.py:35` and `runner/resolutions/planner.py:22`. The test list at line 84 also misses `tests/runner/dispatch/test_checkout_reads.py:17`. Deleting the module as written leaves four broken imports that the list does not tell the implementer to fix. Add the three source files to line 83 and `test_checkout_reads.py` to line 84.

### [CONCERN] The load tier never runs on the changed tick path

Task 6.1 adds a stage to `ProjectTick.run`, which is the tick budget path. CI already gates `tests/load` (`.github/workflows/ci.yml:54`), and `tests/load/test_runner_tick_load.py` asserts the tick deadline. Two gaps remain. Task 9.1 runs bare `uv run pytest`, which excludes `tests/load` (`pyproject.toml:66`), so no step in the breakdown runs the load tier. Nothing in the breakdown also puts a program store under the load test, so the new stage's read is never measured. No new CI wiring is needed, because CI already gates the tier. Add `uv run pytest tests/load` to Task 9.1. Add a load case in Task 6.2 with a program store present and a program registered for some projects, so the stage runs under the tick deadline.

### [CONCERN] Task 9.2 gates unrelated docs and checks on `sq`

Line 279 says Tasks 8.3 to 9.1 stay uncommitted until `sq` is available. Those tasks (the contract docs, the CHANGELOG and the full checks) do not run `sq`. Only the walkthrough in 9.2 needs it. Stopping the whole slice on that blocker withholds finished work, which the process forbids when only one part is blocked. Change the rule so 8.3 to 9.1 are committed on their own, and only 9.2 stays unchecked with its `BLOCKED:` line.

### [NOTE] Task 9.2 hardcodes a dated `sq` path

The step names `~/.local/bin/sq` "where it was found on 2026-11-04". A dated observation about one machine goes stale and reads as an expected value. Keep the lookup and drop the example location.

### [NOTE] Task 1.5 leaves the destination of `GLOB_WILDCARD` open

The constant is defined in `src/amoeba/runner/answering/passages.py:18`. The task says it "moves or is imported from a place `amoeba.store` may import". The store cannot import the runner, so the constant has to move into the store. Say so and name the destination, rather than leaving the choice to the implementer.

### [NOTE] Task 2.10 does not name the `register_member` rejection codes

The line says "each rejection recorded". The codes it means are listed in Task 2.9: `unknown_program`, `member_of_other_program` and `override_not_member`. Naming them here would make sure each one gets a test, since the success criteria require every code to be produced by a body that triggers it.

### [NOTE] Size is proportionate to the slice

The file has about 45 items across nine sections and 287 lines. That fits a slice that adds a store, an inbox root, a tenant, a stage, a package, three listings and three contract docs. Do not split it.

### [PASS] Success criteria are covered, test-with ordering holds, and markers sit at tested points

Each functional, technical and integration criterion in the design maps to at least one task. Each implementation task is followed by its tests. The `**Commit**:` markers are plain lines at tested points. Existing-test edits in Task 9.1 match the tasks that make them. The file references I checked exist: `store/migrations.py`, `store.py`'s read-only open, `project_stores.py`'s `_create_atomically`, `inbox/envelope.py`, `inspection/`, `tests/fault_injection.py` and `tests/test_writer_guard.py`.

### Run Digest

- Response length: 6313 chars
- Response is newline-free: no
- Tool calls made: 25
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 26
- Tokens — prompt / cached / cache write / completion / reasoning: 665302 / 507928 / 157362 / 40664 / not computed
- Duration: 289.8 s
- Cost: $0.16 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
