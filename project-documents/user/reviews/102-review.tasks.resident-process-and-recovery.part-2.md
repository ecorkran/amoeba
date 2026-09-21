---
docType: review
layer: project
reviewType: tasks
slice: resident-process-and-recovery
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/tasks/102-tasks.resident-process-and-recovery-2.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260921
dateUpdated: 20260921
reviewedSha: 20b3d70883b787b2950c3f41940d797c68ce8c8d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
findings:
  - id: F001
    severity: note
    category: uncategorized
    summary: "ProcessSettings module (settings.py) not explicitly listed as a file to create"
    location: "unverified"
  - id: F002
    severity: note
    category: uncategorized
    summary: "Host-loop implementation tasks (6.1–6.3) defer their test to 6.4"
    location: "unverified"
  - id: F003
    severity: note
    category: uncategorized
    summary: "CLI skeleton and lifecycle tasks (7.1–7.2) defer their test to 7.3"
    location: "unverified"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "All success criteria from the slice design trace to tasks"
    location: "unverified"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Load-test tier and CI wiring are both present and correctly sequenced"
    location: "unverified"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Commit checkpoints distributed throughout, not batched at end"
    location: "unverified"
---

# Review: tasks — slice 102

**Verdict:** PASS
**Model:** z-ai/glm-5.2

## Findings

### [NOTE] ProcessSettings module (settings.py) not explicitly listed as a file to create

The LLD's component structure shows `src/amoeba/process/settings.py` as a distinct module (`ProcessSettings — every tunable, defined once`), and the Technical Requirements state "Every tunable (idle interval, shutdown grace, stop timeout, clock tolerance, cf timeout, runs directory) lives in ProcessSettings." Task 6.1 references `idle_interval_seconds` (implying the settings exist), and Task 7.1 says "Expose ProcessSettings tunables as CLI flags," but neither task lists `settings.py` in its "Files to Create." A junior AI would likely create it as part of 6.1 or 7.1, but the task that owns its creation is ambiguous. Adding it to Task 6.1's file list (first use) or Task 7.1's would remove the ambiguity.

### [NOTE] Host-loop implementation tasks (6.1–6.3) defer their test to 6.4

Three sequential tasks modify `host.py` before the first test (Task 6.4) runs. This deviates from a strict test-immediately-follows-implementation pattern, but it is justified: the loop, recovery gating, and signal handling are interdependent and none is independently testable without the others. The LLD's own Implementation Notes prescribe exactly this order (step 7: host loop, signals, Tenant, then the throwaway-tenant integration test). No action needed — noted for completeness.

### [NOTE] CLI skeleton and lifecycle tasks (7.1–7.2) defer their test to 7.3

Task 7.1 creates the CLI skeleton and ExitCode enum; Task 7.2 implements start/stop/status; Task 7.3 tests the lifecycle. Two implementation tasks precede the test. This is the same justified pattern as the host loop — the skeleton is not independently testable without the commands. The LLD's Implementation Notes confirm this ordering (step 8: CLI — lifecycle commands, then inspect). No action needed.

### [PASS] All success criteria from the slice design trace to tasks

Every Functional Requirement (16), Technical Requirement (11), and Integration Requirement (2) in the LLD maps to at least one task in either this file (part 2, Sections 5–9) or the referenced part 1 (Sections 1–4). No criterion is unaddressed. The D4 resolution (findings/verdicts deferred to slice 104) is correctly reflected in Task 7.4, which registers only `projects`, `nodes`, `blocked`, and `journal`.

### [PASS] Load-test tier and CI wiring are both present and correctly sequenced

Task 9.1 creates the `tests/load/` tier with its harness; Tasks 9.2–9.3 implement the crash-loop and recovery-scale tests with measured bounds; Task 9.7 wires CI (`.github/workflows/ci.yml`) to gate both the default suite and the load tier as separate steps. The LLD's Technical Requirement for `tests/load/` and the project rules' requirement for CI gating on concurrency-touching slices are both satisfied. The `--ignore=tests/load` + explicit-path collection mechanism is correctly described.

### [PASS] Commit checkpoints distributed throughout, not batched at end

Commits are specified at Tasks 5.2, 6.4, 7.3, 7.5, 8.1, 9.3, 9.4, 9.5, 9.6, 9.7, and 9.8 — distributed across the entire breakdown rather than accumulated at the end. Intermediate implementation tasks (5.1, 6.1–6.3, 7.1–7.2, 7.4, 9.1–9.2) lack explicit commit instructions, but each is followed by a test task that carries the commit, and CLAUDE.md's "at least once per task" rule covers the general case. This is the correct green-suite commit pattern.

### Run Digest

- Response length: 4034 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 17059
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
