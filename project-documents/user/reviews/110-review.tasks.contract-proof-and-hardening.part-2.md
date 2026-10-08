---
docType: review
layer: project
reviewType: tasks
slice: contract-proof-and-hardening
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 81ec58629fe490d0a8f07b6d5fcfb225da6f5c43
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 50
turns: 20
promptTokens: 1192107
cachedTokens: 1009536
completionTokens: 170640
reasoningTokens: 164904
durationSeconds: 478.9
runId: run-20261008-p5-9c7d33cf
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: traceability
    summary: "Actor steps attributed to the wrong task"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:36"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "LLD refusal criterion is only partly covered at the `Store.open` / `open_project` level"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:376-392"
  - id: F003
    severity: concern
    category: traceability
    summary: "Task 1.2 hands work to Task 10.2 that Task 10.2 does not contain"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:519-531"
  - id: F004
    severity: concern
    category: scope
    summary: "Task 8.2 bundles four independent proofs into one task"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:376-392"
  - id: F005
    severity: note
    category: accuracy
    summary: "Task 9.0 describes the `paused` constant as if it already exists"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:403"
  - id: F006
    severity: note
    category: build
    summary: "The restart matrix's plan to import `run_sequence` needs a path entry the named precedent does not add"
    location: "tests/load/conftest.py:23-27"
  - id: F007
    severity: pass
    category: traceability
    summary: "Every LLD success criterion and integration requirement traces to a task, and the load-tier CI gate already exists"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:342-359"
---

# Review: tasks — slice 110

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Actor steps attributed to the wrong task

Task 5.1 says "Rows for runner-owned steps are 2, 3, 4, 6, 7, 11. Steps 1, 5, 8, 9, 10 are actors' (Task 5.5)". Task 5.5 is "Test step 3 on a store, no kill" — it defines no actors. The actor definitions live in Task 5.8 ("CLI actors — Operator, Human, PM, Inspector") and Task 5.8b (Judge). A junior implementer following this reference lands on the wrong task and will not find the actor surfaces. The same paragraph's other task references (5.9 for the driver, 6.1 for `mid-follow`) are correct, so this is an isolated mis-numbering, but it sits in the task that defines the shared step table.

### [CONCERN] LLD refusal criterion is only partly covered at the `Store.open` / `open_project` level

The LLD success criterion reads: "A project id with an uppercase letter, a space, or a non-ASCII character is refused by `submit`, `open_project`, and `Store.open`." Task 8.2 asserts only `submit` (exit 9, nothing written) for those three id shapes, and defers the library-level cases with "`open_project` and `Store.open` refusals are already covered by Task 2.4: reference them rather than repeating". File 1's Task 2.4 does cover `Store.open` refusing `Demo` and `open_project("Demo")` refusing, but only with the uppercase case; the space (`de mo`) and non-ASCII (`démo`) ids are asserted only through the parametrized `validate_project_id` list in `tests/test_paths.py`, not through `Store.open` or `open_project`. So two of the three id shapes are unproven at the two library entry points the criterion names. Either Task 8.2 should parametrize all three shapes across `submit`/`open_project`/`Store.open`, or File 1's Task 2.4 should be widened — the deferral as written leaves the criterion short.

### [CONCERN] Task 1.2 hands work to Task 10.2 that Task 10.2 does not contain

File 1's Task 1.2 (the conditional one-transaction report-back) ends with: "Add it to `store-contract.md` when Task 10.2 runs." Task 10.2 is titled "Update `store-contract.md` for D5 and D6" and its steps cover only directory resolution, project-id slugs, the `done` refusals, and the mapping rule — `record_runner_report` (or whatever Task 1.1 confirms the name to be) appears in none of them. If Task 1.2 fires (106 merged without the method), the new public `Store` method ships undocumented, and the `docs/README.md` obligations row for "report back in one transaction" (Task 10.4) has no contract section to link to. Task 10.2's objective should be widened, or a step added.

### [CONCERN] Task 8.2 bundles four independent proofs into one task

Task 8.2 (effort 3) contains: (a) parametrizing the entire clean run over three directory-resolution environments, each a full host-plus-actors sequence with per-`tmp_path` assertions; (b) asserting no residue under `tmp_path`; (c) asserting that a relative `AMOEBA_STORE_DIR` and a relative `XDG_CONFIG_HOME` are refused by five separate commands (`status`, `start`, `submit`, `inspect`, `feed`); and (d) asserting a bad project id exits 9 with nothing written. (a) alone is three clean runs and carries its own reported run-time figure; (c) is a five-command matrix that can surface a genuine gap in `feed` or `serve` wiring and, when it does, will need to be fixed somewhere other than in this task. Splitting (a)+(b) from (c)+(d) would keep each commit tested and each failure attributable, and would stop a single discovery in `feed` from blocking the locality proof.

### [NOTE] Task 9.0 describes the `paused` constant as if it already exists

Task 9.0 says the new `run_files.py` holds "`SquadronRun`, `parse_run_file`, and the one named constant for Squadron's `paused` status string. Move them unchanged". In the merged tree `SquadronRun` and `parse_run_file` are in `src/amoeba/process/observers/sq_runs.py`, but no `paused` constant exists anywhere under `src/amoeba` — the observer's `RESULT_STATUS` records the status verbatim and nothing compares it. The constant is therefore new work, not part of the move, and "Move them unchanged" does not apply to it. The phrasing is unlikely to mislead (Task 9.1 says to read the status from `run_files.py`), but the word "unchanged" should not extend to a name that does not exist yet.

### [NOTE] The restart matrix's plan to import `run_sequence` needs a path entry the named precedent does not add

Task 7.1 says to reuse `run_sequence` from `tests/contract/test_lifecycle_proof.py` "through `sys.path` as `tests/load/conftest.py` does for shared harnesses". That conftest inserts only `tests/` and `tests/load` on the path, and the modules under `tests/load/` import each other with flat names (`from host_harness import start_host`, `from load_harness import ...`). If the `tests/contract/` modules follow the same flat-name convention, an import of `contract.test_lifecycle_proof` from the load tier will reach that module but not its flat-named siblings (`proof_runner`, `snapshot`, `proof_harness`), and the reuse will fail at import. This is resolvable either way — add the `tests/contract` directory to the load path, or have Task 4.1 use package-relative imports — but it should be settled before Task 7.1 runs rather than discovered then.

### [PASS] Every LLD success criterion and integration requirement traces to a task, and the load-tier CI gate already exists

Cross-referencing the LLD's Success Criteria against the two task files: the clean sequence with three verdicts, two judge samples, one `ingested` and one `runner_issued` detection and `finding_changes` naming round 1 map to Task 5.9a; the kill-point criterion maps to 6.2, 6.3, 6.4 and the eleven-case matrix in 7.1; the subscriber transcript, its replay, and the remote/local equality map to 6.5 and 6.5a; `proof-b` isolation maps to 5.9a and 8.1; the three directory resolutions and the relative-variable refusal map to 8.2; the four `done` refusals map to File 1's Task 2.6; the pruning report matches map to 9.5; the guard and the five export pins map to File 1's Tasks 4.9 and 3.3 with the deferred pins finished in 6.4a and 9.0/9.1; the store-layering and writer-guard criteria map to 11.1; the link test maps to 10.5; and the two Integration Requirements map to 10.1 and 10.4. No task in File 2 traces to nothing — Section 7 is the only load-tier addition, and it is the criterion the slice design names, not scope creep. The CI gating that the process requires for a load-tier task is satisfied rather than left implicit: `.github/workflows/ci.yml` already runs `uv run pytest tests/load` as its own non-suppressed step, and Task 7.1 requires confirming that by reading the file. Sequencing is acyclic and respected throughout — the only gated region (5–8, 9.5, 10.1, 10.4–10.6 on 105–109) is stated up front in the Context Summary with the fallback "do the tasks that do not need it, then stop".

### Run Digest

- Response length: 8407 chars
- Response is newline-free: no
- Tool calls made: 50
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 593193
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 1192107 / 1009536 / 170640 / 164904
- Duration: 478.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
