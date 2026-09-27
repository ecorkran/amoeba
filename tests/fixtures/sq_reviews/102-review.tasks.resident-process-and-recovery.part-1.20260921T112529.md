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
dateCreated: 20260920
dateUpdated: 20260920
reviewedSha: bf6d292620c8b67e1230c3a1cb88484b336d498c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
findings:
  - id: F001
    severity: concern
    category: task-sequencing
    summary: "ExitCode vocabulary is consumed in Section 6 before Task 7.1 defines it"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-2.md:119-163"
  - id: F002
    severity: concern
    category: ci-gating
    summary: "No CI wiring task gates the load tier"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-2.md:313-357"
  - id: F003
    severity: concern
    category: success-criteria
    summary: "Task 2.2/2.3 success criteria are unsatisfiable under the documented fallback branch"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-1.md:231-272"
  - id: F004
    severity: concern
    category: cross-reference
    summary: "Task 2.1's fallback note cross-references the wrong task"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-1.md:220"
  - id: F005
    severity: note
    category: test-infrastructure
    summary: "Default-run exclusion mechanism for `tests/load/` is unspecified and likely needs an unlisted pyproject change"
    location: "pyproject.toml:42-43"
  - id: F006
    severity: note
    category: scope-definition
    summary: "The load-test tenant has no specified entry path into the process"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-2.md:315-334"
  - id: F007
    severity: pass
    category: coverage
    summary: "Every success criterion in the slice design traces to at least one task"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-2.md"
  - id: F008
    severity: pass
    category: task-sequencing
    summary: "Sequencing follows the LLD's development approach, with the risk-first ordering intact"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-1.md:210"
  - id: F009
    severity: pass
    category: test-organization
    summary: "Test-with pattern and commit checkpoints are correctly distributed"
    location: "project-documents/user/tasks/102-tasks.resident-process-and-recovery-1.md"
---

# Review: tasks — slice 102

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] ExitCode vocabulary is consumed in Section 6 before Task 7.1 defines it

Tasks 6.2 (line 108: "aborts the start with a specific exit code"), 6.3 (line 128: "exit `GRACE_EXPIRED`"), and 6.4 (line 152: "triggers grace expiry with `GRACE_EXPIRED`") all require the `ExitCode` vocabulary, but that enum is first created in Task 7.1 (line 177), which depends on Task 6.4. The declared dependency chain is 6.2 → 6.3 → 6.4 → 7.1, so a junior AI implementing 6.3 hits an undefined symbol and cannot satisfy the "no bare integers at call sites" rule without either creating the enum early (duplicating 7.1's work and placing it outside its LLD-assigned home in `cli/main.py`) or improvising. The LLD's own error-handling section supplies the correct split — "`cli/main.py` is the one documented process-boundary handler that maps `StoreError` and lifecycle errors to `ExitCode` values" — meaning the host should raise a typed lifecycle error and the CLI should map it. Tasks 6.2/6.3/6.4 should be reworded to that split (host raises, 7.2 maps), or the enum should be defined in an earlier task. Note also that Task 7.1 names only the five failure codes while `status` must "distinguish running from not" (7.2) and the StoreError abort (6.2) needs its own member — the enum needs more members than the task lists, which a junior AI will only discover mid-flight.

### [CONCERN] No CI wiring task gates the load tier

Tasks 9.1 and 9.2 create `tests/load/` (crash loop and recovery scale), and Task 9.1 deliberately excludes the tier from the default pytest run — yet no task wires CI to execute it. The Python rules are explicit (`.claude/rules/python.md:64`): "CI must gate load tests for slices touching these paths," and this slice is squarely on the concurrency/process boundary. The repo currently has no CI at all (no `.github/` directory or CI configuration exists at the root), and Task 9.6's gates are run by hand (`uv run pytest tests/load` locally), so nothing anywhere executes the load tier automatically — gating is left entirely implicit. Either add a CI wiring task (a minimal workflow running the default suite plus `pytest tests/load`) or record an explicit PM decision to defer CI; as written, the breakdown satisfies the letter of "load tests exist" while violating the rule that makes them meaningful.

### [CONCERN] Task 2.2/2.3 success criteria are unsatisfiable under the documented fallback branch

Task 2.2's steps correctly acknowledge the contingency ("or the Task 2.1 fallback, if that was the evidence"), but its success criterion "A write attempted through the handle fails rather than succeeding silently" — and Task 2.3's "Test that every write operation attempted through a read-only handle raises" — cannot pass if the fallback (a read-write handle the inspection code never writes through) is taken. The LLD treats this fallback as a live possibility (it is the slice's second named technical risk, with a full mitigation paragraph). In that branch a junior AI is left with a checklist item that is impossible to check. The criteria should be conditional, mirroring how Tasks 8.1 and 9.4 correctly handle the same branch.

### [CONCERN] Task 2.1's fallback note cross-references the wrong task

Task 2.1's fallback instruction says to "note it for Task 5.x (the guard test must then also cover `cli/inspect.py`)". The guard test is Task 8.1, not anything in Section 5 (Instance Lock and PID File). The reference is stale — likely a leftover section number from before the breakdown was split into two files. Impact is low because Task 8.1 independently self-references the Task 2.1 fallback ("unless Task 2.1's evidence forced the fallback, in which case extend the guard..."), but the note as written misdirects the reader to the instance-lock section, and the "Section 9" half of the same sentence is only correct by coincidence of the split. Should read "Task 8.1."

### [NOTE] Default-run exclusion mechanism for `tests/load/` is unspecified and likely needs an unlisted pyproject change

`testpaths = ["tests"]` (pyproject.toml:43) collects `tests/load/` by default, so Task 9.1's criterion "`uv run pytest` (default) does not run this tier" requires a configuration change the task does not spell out. A registered marker plus `addopts = -m "not load"` needs a `pyproject.toml` edit that is absent from Task 9.1's Files to Modify — and would also deselect the tier under the task's own stated invocation `uv run pytest tests/load` unless overridden. An env-gated skip in `tests/load/conftest.py` works without a pyproject change but then depends on CI setting that variable, which compounds the CI-gating concern above. The task should name the mechanism.

### [NOTE] The load-test tenant has no specified entry path into the process

Task 9.1 requires "repeatedly start the process with a test tenant that issues journal entries," and Task 6.4 similarly needs a throwaway tenant ticked by the real host — but the CLI ships zero tenants and has no registration mechanism, and no task creates the harness (a small script that constructs `ResidentProcess` with the tenant in a subprocess) that these tests require. `Files to Create` for 9.1 lists only `__init__.py`, `conftest.py`, and `test_crash_loop.py`. A junior AI must invent the harness, and the obvious wrong turn — adding a `--tenant` flag to the CLI — would be scope creep beyond the LLD's "ships no tenants." Task 9.1 also bundles tier scaffolding, the harness, and the crash-loop test; it is the strongest candidate in the breakdown for a split.

### [PASS] Every success criterion in the slice design traces to at least one task

I walked all 16 Functional, 9 Technical, and 2 Integration requirements in the LLD against both task files and found no gaps and no scope creep. Representative mappings: the four lifecycle failure modes (ALREADY_RUNNING / kill-9 / NO_STOP_TARGET / GRACE_EXPIRED) → Tasks 7.2–7.3 and 5.2; subset matching, clock tolerance, and run-id dedup → Tasks 4.3–4.4; already-blocked escalation → Tasks 1.5, 1.7, 3.4; interrupted-recovery idempotence → Task 3.4 and 9.1; never-migrate/never-create inspection → Tasks 2.2–2.3 and 7.4–7.5; the version-2-to-3 upgrade by `amoeba start` → Tasks 1.4 and 7.3; the throwaway-tenant seam → Task 6.4; real fixtures with paused/failed runs and capture dates → Task 4.1; the AST guard → Task 8.1; docs and changelog → Tasks 9.3–9.4. Even the items that could have been dropped — `scripts/demo_journal.py` and the walkthrough refinement (Task 9.5) — trace to explicit LLD statements ("to be written in this slice"; "Draft; to be refined with real output"). File 1 covers Sections 1–4 of the LLD's component structure completely; file 2 covers the rest, including the D4-mandated absence of findings/verdicts listings.

### [PASS] Sequencing follows the LLD's development approach, with the risk-first ordering intact

The section order (journal → read-only open → recovery protocol → observers → lock → host → CLI → guard → load → docs) is exactly the LLD's eleven-step Development Approach. Task 2.1 (line 210) is correctly an evidence-gathering *test* placed before any implementation depends on the answer, matching the LLD's mitigation ("The first task of the inspection work is a test that opens a store read-only with no writer alive... decided on that evidence, not in advance"). Declared dependencies are linear with no cycles; the only dependency defect found is the ExitCode content inversion flagged above. Task 5.2's forward references ("the state Task 6.4 and Task 7.2 must handle") are correct, unlike the Task 5.x one in file 1.

### [PASS] Test-with pattern and commit checkpoints are correctly distributed

Every implementation task is immediately followed by its test task: 1.1/1.2, 1.3/1.4, 1.5+1.6/1.7, 2.2/2.3, 3.3/3.4, 4.2+4.3/4.4, 4.5/4.6, 5.1/5.2, 6.1–6.3/6.4, 7.2/7.3, 7.4/7.5, with 8.1–9.2 being tests themselves. Commits are spread across the work (1.8; then within 2.3, 3.4, 4.4, 4.6, 5.2, 6.4, 7.3, 7.5, 8.1, 9.2, 9.4; final merge in 9.6), matching the slice-101 precedent of commit-after-green-group rather than batching at the end. The tests also inherit slice 101's mechanical safety net: the existing `tests/test_store_safety.py` scans `TESTS_DIR.rglob("*.py")`, which will cover the new `tests/load/` and CLI test files against central-path resolution for free.

### Run Digest

- Response length: 9364 chars
- Response is newline-free: no
- Tool calls made: 24
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 81434
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
