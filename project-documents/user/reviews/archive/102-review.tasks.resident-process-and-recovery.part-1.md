---
docType: review
layer: project
reviewType: tasks
slice: resident-process-and-recovery
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/102-tasks.resident-process-and-recovery-1.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260921
dateUpdated: 20260921
reviewedSha: 20b3d70883b787b2950c3f41940d797c68ce8c8d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 26
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "The GRACE_EXPIRED exit criterion has no CLI-level test despite Task 6.4 deferring one to Task 7.3"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-2.md:218-240"
  - id: F002
    severity: concern
    category: test-infrastructure
    summary: "Task 9.1's shared-harness instruction is unsatisfiable as written: a `tests/load/conftest.py` fixture cannot serve `tests/test_host.py`"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-2.md:325-335"
  - id: F003
    severity: pass
    category: coverage
    summary: "Every LLD success criterion traces to at least one task, and no task is scope creep"
    location: "project-documents/user/slices/102-slice.resident-process-and-recovery.md"
  - id: F004
    severity: pass
    category: sequencing
    summary: "Sequencing respects dependencies, tests immediately follow implementation, and commits are distributed"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-1.md"
  - id: F005
    severity: pass
    category: load-testing
    summary: "Load-tier tasks cover the LLD's bounds, and CI wiring exists to gate them rather than leaving the gate implicit"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-2.md:457"
  - id: F006
    severity: note
    category: test-fixtures
    summary: "Task 4.1's fixture capture depends on the executor's environment with no fallback path"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-1.md:369-388"
  - id: F007
    severity: note
    category: task-scoping
    summary: "Project-store enumeration logic is needed by two tasks but assigned to neither"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-2.md"
---

# Review: tasks — slice 102

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] The GRACE_EXPIRED exit criterion has no CLI-level test despite Task 6.4 deferring one to Task 7.3

The LLD's functional criterion (slice design line 285) reads: "A tenant that does not return within the grace period causes exit with `GRACE_EXPIRED` and an ERROR log naming the tenant." Task 6.4 tests this only at the host layer and explicitly promises, at line 152 of the same task file: "Task 7.3 separately proves this surfaces as `ExitCode.GRACE_EXPIRED` through the CLI." But Task 7.3's step list (lines 224-233) contains seven behaviors — full cycle, second `start`, `kill -9` restart, `NOT_RUNNING`, `NO_STOP_TARGET`, version-2 migration, plus the infrastructure/safety steps — and none drives a hanging tenant through the real CLI to observe the `GRACE_EXPIRED` exit status. Task 6.4's harness constructs `ResidentProcess` directly in a subprocess, so the `cli/main.py` boundary handler that maps the host's typed error to the exit code is never exercised anywhere in the plan. The only backstop is Task 9.8's generic criteria walkthrough, which would surface the miss at the very end of the slice rather than at the point of implementation. Fix: add one step (and an eighth behavior) to Task 7.3, or make the deferral at line 152 point at a task that actually contains it.

### [CONCERN] Task 9.1's shared-harness instruction is unsatisfiable as written: a `tests/load/conftest.py` fixture cannot serve `tests/test_host.py`

Task 9.1 instructs (line 327): "factor the common piece so it is written once and both `test_host.py` and this tier can use it, per the project's DRY rule" — but it also places the harness "in `conftest.py`" under `tests/load/` (Files to Create, line 334). Pytest conftest fixtures are scoped to their own directory and below; a fixture in `tests/load/conftest.py` is invisible to `tests/test_host.py`, which sits outside that tree. The instruction therefore cannot be satisfied without deviating from the file list, and the only files 9.1 is permitted to create or modify (`tests/load/__init__.py`, `tests/load/conftest.py`, `pyproject.toml`) contain no location the shared piece could occupy that both consumers can reach — the workable homes (a helper module under `tests/`, or `tests/conftest.py`, which exists and is already in scope for both) are not listed. Two secondary problems compound it: the instruction requires retroactively refactoring the already-committed Task 6.4 test, yet none of 9.1's success criteria verify that `test_host.py` actually consumes the shared harness (the smoke criterion proves only the load-side use); and criterion 1's parenthetical ("nothing is in it yet but `__init__.py`/`conftest.py`") contradicts criterion 2, which demands a minimal smoke use proven in this same task. A junior AI will have to make unguided structural decisions to complete this task. Fix: name the shared home explicitly (e.g., a `tests/`-level helper module imported by both, or `tests/conftest.py`) and add a criterion that `test_host.py` runs through it.

### [PASS] Every LLD success criterion traces to at least one task, and no task is scope creep

Cross-referencing the LLD's three criteria lists against the 35 tasks: all 17 functional criteria are covered (lifecycle and single-instance → 7.2/7.3; `kill -9` and stale-pid → 7.3; lock-held-no-PID → 7.2/7.3, with 5.2 preparing the state; grace expiry → 6.3/6.4 plus the gap noted above; `cf_write` adopted/`not_applied` and provenance → 4.5/4.6; the four `sq_run` outcomes → 4.3/4.4; already-blocked escalate → 1.5/1.7; interrupted-recovery idempotence → 3.3/3.4; missing-parameter raise → 1.5/1.7; inspect listings and never-mutates → 7.4/7.5/2.2/2.3). All 9 technical criteria are covered, including the vocabularies (1.1), `ProcessSettings` (3.2), real fixtures (4.1), unknown-not-exception (4.2/4.3/4.5), the guard test (8.1), subprocess-based process tests (7.3), the load tier (9.2/9.3), quality gates (recurring + 9.8), and all three docs (9.4/9.5). Both integration criteria are covered (throwaway tenant → 6.4; version-2 upgrade on start → 7.3). Items that could look like scope creep all trace to sanctioned provisions: `scripts/demo_journal.py` is named in the LLD's Verification Walkthrough; CI (9.7) is required by `.claude/rules/python.md`; the findings/verdicts exclusion is the ratified D4 decision recorded in file 2's closing section. Nothing in either task file implements an excluded item (no tenants shipped, no daemonizing, no network listener, no per-tick timeout — the last is explicitly prohibited in 6.3).

### [PASS] Sequencing respects dependencies, tests immediately follow implementation, and commits are distributed

The 35 tasks form a strictly linear chain with no circular dependencies, and the one place where an earlier task must be revisited (Task 2.1's conditional read-only fallback) is propagated forward explicitly in every affected task — 2.2's success criteria state which branch applies, 8.1 carries the guard-extension conditional, and 9.5 requires both contract documents to state the softened invariant, exactly as the LLD's mitigation demands. The test-with pattern holds without exception: 1.2/1.4/1.7 follow 1.1/1.3/1.5-1.6; 2.1-2.3 wrap the read-only work; 3.4 follows 3.3; 4.4 and 4.6 follow their observers; 5.2, 6.4, 7.3, 7.5, 9.2, 9.3 likewise. Commit checkpoints appear at 1.8, 2.3, 3.4, 4.4, 4.6, 5.2, 6.4, 7.3, 7.5, 8.1, 9.3, 9.4, 9.5, 9.6, 9.7, and 9.8 — the seven-task batch before 1.8 is the largest gap, but it is the LLD's own Development Approach step 1 ("Journal in the store") taken as one independently-green library unit, which is a reasonable checkpoint boundary rather than end-batching. Risk-front-loading is also correct: the WAL read-only experiment (2.1) is deliberately the first task of Section 2, before any code depends on its answer, and no design decision is pre-committed.

### [PASS] Load-tier tasks cover the LLD's bounds, and CI wiring exists to gate them rather than leaving the gate implicit

The LLD's Implementation Notes name three asserted bounds — start-to-ready under 2 s, 500 unresolved entries against 1000 run files under 30 s, and exactly one runs-directory scan per recovery pass — and Tasks 9.2 and 9.3 cover all three, including the measure-then-set-at-2x discipline and the "record the real number, don't tune the bound" rule that prevents reverse-engineered assertions. The scan-count assertion is exact, matching the LLD's statement that it is "the one that actually guards the algorithm." CI gating is not left implicit: Task 9.7 creates `.github/workflows/ci.yml` running the default suite and `uv run pytest tests/load` as independently-failing steps, which is required because the repo currently has no `.github/` directory at all and because `.claude/rules/python.md` mandates that "CI must gate load tests for slices touching these paths." I also verified the breakdown's riskiest mechanical claim — that `addopts = ["--ignore=tests/load"]` excludes the tier from a bare `uv run pytest` while still permitting an explicit `uv run pytest tests/load` — by reading the installed pytest's `Session.collect`/`Dir.collect` in `.venv`: an explicitly named path is an initial path, the ignore hook is skipped for it (`isinitpath`), and its child files are not members of the ignore list (which contains the directory), so they collect. Task 9.1's success criteria empirically verify both directions, which is the right guard even if the mechanism drifts across pytest versions. The existing `tests/test_store_safety.py` guard scans `TESTS_DIR.rglob("*.py")`, so its protection automatically extends to `tests/load/` as well.

### [NOTE] Task 4.1's fixture capture depends on the executor's environment with no fallback path

Task 4.1 requires "byte-real upstream output, not hand-written approximations" copied from `~/.config/squadron/runs/`, "including at least one `paused` and one `failed`" run, plus captured `cf get --json` output. This faithfully implements an LLD technical requirement and the project's parsing rule (fixtures must be the real format), and the LLD declares Squadron files and the `cf` CLI as slice prerequisites — so this is inherited rather than a breakdown defect. But unlike Task 4.6, which specifies a clean skip when `cf` is absent from `PATH`, Task 4.1 has no stated path for an executor whose machine lacks a `failed` Squadron run: the task simply blocks. If the executing environment cannot produce one, the executor needs guidance (e.g., run a pipeline to failure to capture one, or stop and ask the Project Manager) rather than an implicit temptation to hand-write an approximation that the success criteria forbid.

### [NOTE] Project-store enumeration logic is needed by two tasks but assigned to neither

Task 6.2 requires recovery to run "for **every** project store," and Task 7.4 requires "`projects` lists project ids having a store in the supervisor directory." Both depend on the same new capability — enumerating the stores in the resolved supervisor directory — which does not exist in slice 101 (`paths.py` provides only `store_dir` and `store_path`) and is not named as a deliverable in any task. A junior implementing 6.2 must invent the scan, and 7.4 must invent it again; if the two implementations drift (one globbing a literal `"*.sqlite3"`, the other referencing `paths.STORE_FILE_SUFFIX`), that violates the project's "never scatter comparison values" rule. One line in 6.2 ("discover project stores by scanning the supervisor directory for files with `paths.STORE_FILE_SUFFIX`, in one place both the host and `inspect projects` use") would close it.

### Run Digest

- Response length: 11483 chars
- Response is newline-free: no
- Tool calls made: 26
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 73732
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
