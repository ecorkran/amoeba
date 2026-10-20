---
docType: tasks
slice: contract-proof-and-hardening
project: amoeba
lld: user/slices/110-slice.contract-proof-and-hardening.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108, 109]
projectState: File 1 complete — H1–H4 landed (`standard_tenants`, `amoeba.process.__all__`, `store_dir`/`project_store_path` exports, `record_runner_report`, `SquadronRun.updated_at`); `tests/contract/` has the public-import rule, `ProofRunner`, and the bootstrap harness.
dateCreated: 20261019
dateUpdated: 20261019
status: not_started
---

## Context Summary (File 2 of 2)

- Continues `110-tasks.contract-proof-and-hardening-1.md`. Its Context Summary (current state, branch, reading note, commit cadence, tool knowledge, task-level additions) applies here unchanged. Read it first.
- This file: 5 scenario and oracles; 6 network subset; 7 pruning; 8 docs; 9 validation. The "Gaps Found" log at the end is filled in during Section 5.
- **Gap rule (LLD D7):** a gap is fixed in this slice only if the fix is additive (an export, a doc section, a new method composed from existing transactions, a move with no behavior change). A fix that changes existing behavior, a schema, or a recorded value: write it in "Gaps Found" and **stop for the PM**.

---

## Section 5: Scenario and Oracles

### Task 5.1: Write the scenario as data
**Owner**: Junior AI
**Dependencies**: File 1, Task 4.6
**Effort**: 3
**Objective**: `scenario.py` reads as the sequence a consumer follows (LLD D4).

**Steps**:
- [ ] `tests/contract/scenario.py`: `STANDIN_RUN_AGE = timedelta(days=365)` (its only definition); the project ids `alpha` and `beta` as constants; an actor enum (PM, Runner, Judge, External, Process)
- [ ] One frozen record per step 1–12 of the D4 table: number, actor, action, project(s), `ProofStep`/`CrashPoint` where relevant (referenced from `runner_tenant.py`, never spelled), and the change kinds expected on each project's feed afterward (`ChangeKind` members, never literals)
- [ ] `beta` takes part only in steps 1, 2, and 9
- [ ] Data only: no driver logic, no I/O

**Success Criteria**:
- [ ] 12 steps match the D4 table one-to-one; file near 300 lines; public-import rule passes
- [ ] Committed with Task 5.3

---

### Task 5.2: Declare the end state and implement the end-state oracle
**Owner**: Junior AI
**Dependencies**: Task 5.1
**Effort**: 3
**Objective**: A missing or extra row fails the proof (LLD D5 "End state", D6).

**Steps**:
- [ ] `tests/contract/oracle.py`: per project, the declared node statuses; blocked states and their resolutions; journal entries by outcome and resolver; verdicts with trust label and `judge_invocation_id`; detection-ledger outcomes by path; messages by channel and acknowledgment; submission outcomes. Values come from the D4 "Proves" column and the LLD "Functional Requirements"
- [ ] A compare function that reads each project with `Store.open_read_only(project_store_path(...))` through public reads only and returns a readable diff (missing, extra, mismatched)
- [ ] D6 checks: the supervisor directory holds exactly `alpha.sqlite3` and `beta.sqlite3`; no alpha reviews-directory path appears in beta's ledger; each project's changes carry only its own project id
- [ ] If the declaration exceeds ~300 lines, move it to `tests/contract/end_state.py` and keep the compare logic in `oracle.py`

**Success Criteria**:
- [ ] The compare function returns an empty diff only on an exact match
- [ ] Committed with Task 5.3

---

### Task 5.3: Implement the feed-replay oracle and test both oracles
**Owner**: Junior AI
**Dependencies**: Task 5.2
**Effort**: 2
**Objective**: The feed alone rebuilds node state, with no gap (LLD D5 "Feed replay").

**Steps**:
- [ ] In `oracle.py`: replay a list of `Change`s from `seq` 0 (`node_created` sets a status, `node_status_changed` moves it) into a node-id → status map; a check that `seq` is strictly increasing with no gaps
- [ ] `tests/contract/test_oracle.py`: hand-built change lists (gap, repeat, out-of-order, correct) and a small temporary store with one extra and one missing row, so each oracle is shown to fail when it should

**Success Criteria**:
- [ ] Oracle tests pass
- [ ] Committed (5.1–5.3): `test: add the contract scenario and its two oracles`

---

### Task 5.4: Drive steps 1–6
**Owner**: Junior AI
**Dependencies**: Task 5.3
**Effort**: 3
**Objective**: Project creation, tree building, reporting, and both crash windows (LLD D4 steps 1–6).

**Steps**:
- [ ] `tests/contract/test_lifecycle_proof.py`: one test that drives `scenario.py`'s steps in order using Task 4.5's harness. After each step, wait until the subscriber has that step's expected change kinds. Tasks 5.5 and 7.5 extend this file; keep it near 300 lines by moving per-step driver helpers into `tests/contract/steps.py` once it nears that size
- [ ] Step 1 starts the alpha subscriber once alpha's store exists; beta's changes are read at the end with `follow(after=0)` for the D6 check
- [ ] Steps 4 and 5: wait for the `SIGKILL` exit, restart, wait for recovery's outcome
- [ ] Step-level assertions the oracle cannot make: step 3's verdict, ledger row, and entry share one commit (no change for the verdict precedes the entry's resolution on the feed); step 4 has one verdict for the round and the detection row's `record_id` equals the parsed artifact's id; step 5 has exactly one escalation message
- [ ] Ownership guarantee (LLD D8): after step 3 (`completed` by the issuer) and after step 4 (`adopted` by recovery), `recorded_result_run_ids("alpha")` contains that step's run id

**Success Criteria**:
- [ ] Steps 1–6 pass; on failure the message names the step number
- [ ] Any gap found is in "Gaps Found" with its D7 classification
- [ ] Committed: `test: drive contract proof steps 1-6`

---

### Task 5.5: Drive steps 7–11 and run both oracles
**Owner**: Junior AI
**Dependencies**: Task 5.4
**Effort**: 3
**Objective**: External work, the Judge path, checkpoints, down-time submissions, finish (LLD D4 steps 7–11, D5).

**Steps**:
- [ ] Step 7: the driver writes a PM-launched review artifact into alpha's reviews directory and a paused run file (unowned id, `updated_at = now - STANDIN_RUN_AGE`) into the runs directory. Assert `finding_changes` for the new verdict compares it with step 4's round
- [ ] Step 8: two `verdict` submissions sharing one `judge_invocation_id` (payload shape per `docs/inbox-contract.md` and the 107 fixture)
- [ ] Step 9: a `checkpoint` intent on alpha and on beta; each gate is `blocked_on_sq_checkpoint` with `sq.run_id` set, and each run id is in its project's `recorded_result_run_ids` (ownership guarantee, checkpoint path)
- [ ] Step 10: stop with `amoeba stop`; `inbox.submit` a `resolution` for alpha's checkpoint while down; start; wait until it is applied
- [ ] Step 11: a `finish` intent on alpha; alpha's slice and gate are `done`, beta's gate stays blocked
- [ ] After step 11: run the end-state oracle and the feed-replay oracle; fail with their diffs

**Success Criteria**:
- [ ] Steps 1–11 pass; both oracles report no diff; `seq` has no gap across steps 4, 5, and 10
- [ ] Committed: `test: drive contract proof steps 7-11 and check both oracles`

---

### Task 5.6: Resolve the gaps the proof found
**Owner**: Junior AI
**Dependencies**: Task 5.5
**Effort**: 2
**Objective**: Every gap is closed or with the PM (LLD D7).

**Steps**:
- [ ] For each additive gap in "Gaps Found": fix it, document it in its contract doc, add or extend a test, one commit each (`fix:` or `feat:` as fits)
- [ ] For each non-additive gap: stop and tell the PM; do not continue past this task until the PM amends the design or defers it
- [ ] If no gaps were found, write "None found" in the log

**Success Criteria**:
- [ ] Every log entry is marked fixed (with commit) or PM-decided (with the decision)
- [ ] Suite green

---

## Section 6: Network Subset

### Task 6.1: Network subset — delivery and a `kill -9` of `amoeba serve`
**Owner**: Junior AI
**Dependencies**: Task 5.6
**Effort**: 2
**Objective**: Remote submission and SSE delivery survive a server crash (LLD D2, "Data Flow" network).

**Steps**:
- [ ] `tests/contract/test_network_subset.py`: start the bootstrap, then `amoeba serve` as `sys.executable -m amoeba.cli.main serve` on loopback with a free port (no token; see `docs/network-contract.md`); follow alpha's SSE feed with httpx. Reuse `tests/serve_harness.py`'s `sse_events` parser
- [ ] POST an intent, poll `GET …/submissions/{id}` until `applied`, receive `message_posted` over SSE
- [ ] `kill -9` serve; a POST raises a connection error; restart serve; reconnect with `Last-Event-ID` = last seq received
- [ ] The follower reconnects only at planned points; any other drop fails the test

**Success Criteria**:
- [ ] Test passes in the default suite; public-import rule passes
- [ ] Committed: `test: prove the network path across a kill of amoeba serve`

---

### Task 6.2: Network subset — a `kill -9` of the resident process
**Owner**: Junior AI
**Dependencies**: Task 6.1
**Effort**: 2
**Objective**: A POST made while the resident process is down is accepted and delivered (LLD D2).

**Steps**:
- [ ] In the same test, after Task 6.1's steps: `kill -9` the resident process; POST an intent → 202; restart it; SSE delivers it with no reconnect
- [ ] End: the SSE `seq` list equals a local `follow(after=0)` list

**Success Criteria**:
- [ ] Test passes in the default suite; no gap and no repeat in the SSE `seq` list
- [ ] Committed: `test: prove the network path across a kill of the resident process`

---

## Section 7: Pruning

### Task 7.1: Implement `select_prunable`
**Owner**: Junior AI
**Dependencies**: Task 6.2
**Effort**: 2
**Objective**: The pure selection rule (LLD D8 "Which runs", "API Contracts").

**Steps**:
- [ ] `src/amoeba/process/run_pruning.py`: `PRUNE_RETENTION = timedelta(days=7)`, `SQ_PRUNE_TIMEOUT_SECONDS = 30.0` (only definitions), and `select_prunable(runs, *, owned, held, now)` returning runs meeting all four D8 conditions
- [ ] A run with `updated_at is None` is never returned. The paused status is compared through one constant, not a scattered literal
- [ ] Imports only `process/observers/sq_runs` and the standard library
- [ ] Add rule 9 to `tests/test_import_boundaries.py`: `run_pruning.py` imports nothing but those (AST)

**Success Criteria**:
- [ ] Pure: no I/O, no clock read (`now` is a parameter)
- [ ] Committed with Task 7.2

---

### Task 7.2: Test `select_prunable`
**Owner**: Junior AI
**Dependencies**: Task 7.1
**Effort**: 1
**Objective**: Each condition is proven (LLD "Functional Requirements").

**Steps**:
- [ ] `tests/process/test_prune_selection.py` (the name must contain `prune` so the walkthrough's `-k prune` selects it; imports `PRUNE_RETENTION` directly): a run meeting all four is selected; each condition failing alone excludes it; missing `updated_at` excludes it; a resumed-but-not-done node (its id in `held`) excludes it; exactly at the retention boundary is selected

**Success Criteria**:
- [ ] Tests pass; rule 9 passes and fails on a `tmp_path` source importing `amoeba.store`
- [ ] Committed (7.1–7.2): `feat(process): add the paused-run selection rule`

---

### Task 7.3: Implement `amoeba prune sq-runs`
**Owner**: Junior AI
**Dependencies**: Task 7.2
**Effort**: 3
**Objective**: Preview by default, delete through `sq` with `--yes` (LLD D8, "Data Flow" pruning, "API Contracts" CLI).

**Steps**:
- [ ] Add `ExitCode.PRUNE_INCOMPLETE = 14` in `cli/main.py` with its comment; register `add_prune_parser` there
- [ ] `src/amoeba/cli/prune.py`: `add_prune_parser`, `run_prune`, and `prune_sq_runs` (task-level addition, file 1). Follow the LLD "Data Flow" pruning block step by step: read-only opens only; any unreadable store refuses before `sq` (existing store-error exit mapping); unparseable run file → WARNING naming it; preview prints candidates (`run_id, pipeline, updated_at, owning project`) and the kept count
- [ ] `--yes`: select afresh, run `sq runs prune <ids…> --yes` once with `stdin=DEVNULL` and the timeout; catch `FileNotFoundError` (sq missing) and `TimeoutExpired` as incomplete, each with a comment; re-read the runs directory; print any candidate still present with sq's exit status and stderr
- [ ] Never unlink a file. Exit `OK` if every candidate is gone or none existed, else `PRUNE_INCOMPLETE`

**Success Criteria**:
- [ ] `cli/prune.py` uses `Store.open_read_only` only; `test_writer_guard.py` passes unchanged
- [ ] `uv run amoeba prune sq-runs --help` works
- [ ] Committed with Task 7.4

---

### Task 7.4: Test pruning against a stub `sq`
**Owner**: Junior AI
**Dependencies**: Task 7.3
**Effort**: 2
**Objective**: Every failure leaves files and exits `PRUNE_INCOMPLETE` (LLD D8, "Functional Requirements").

**Steps**:
- [ ] `tests/sq_stub.py`: one function that writes a stub `sq` script (shebang `sys.executable`) into a given `bin` directory and returns that directory, for tests to put first on `PATH`. Task 7.5 reuses it; it is its only definition. Modes chosen by an env var: delete the named files under `$HOME/.config/squadron/runs`; exit 1 for an already-gone file; refuse one id as live (exit 1, file kept); fail (exit 1, nothing deleted); sleep past the timeout
- [ ] `tests/process/test_prune_sq_runs.py`, calling `prune_sq_runs` with `tmp_path` dirs and a short timeout: success; already-gone counts as removed; refused live run; failure; timeout; `sq` missing from `PATH` — each failure exits `PRUNE_INCOMPLETE`, prints the remaining candidates, and no file is deleted by Amoeba
- [ ] An unreadable project store refuses before the stub is called (stub records invocations to a file)
- [ ] Preview never calls the stub

**Success Criteria**:
- [ ] Tests pass; no test touches the real `HOME`
- [ ] Committed (7.3–7.4): `feat(cli): add amoeba prune sq-runs`

---

### Task 7.5: Add scenario step 12
**Owner**: Junior AI
**Dependencies**: Task 7.4
**Effort**: 2
**Objective**: Pruning against the proof's real end state (LLD D4 step 12).

**Steps**:
- [ ] At the end of `test_lifecycle_proof.py`, run `sys.executable -m amoeba.cli.main prune sq-runs` as a subprocess with the harness env and `tests/sq_stub.py`'s stub (delete mode) first on `PATH`
- [ ] Preview: exactly alpha's checkpoint run is a candidate; the kept count is 1 (beta's)
- [ ] `--yes`: only alpha's checkpoint run file is gone; beta's and step 7's remain; exit `OK`. Assert on selection, never on the retention value

**Success Criteria**:
- [ ] Full proof passes including step 12
- [ ] Committed: `test: add pruning as contract proof step 12`

---

## Section 8: Documentation

### Task 8.1: Add the pruning section to the process contract
**Owner**: Junior AI
**Dependencies**: Task 7.5
**Effort**: 2
**Objective**: Consumers know what pruning does and what 120 must do (LLD D8, "Integration Requirements").

**Steps**:
- [ ] `docs/process-contract.md`: replace the Future-work line "Pruning Squadron's paused runs — slice 110" with a "Pruning paused runs" section: the four conditions, preview vs `--yes`, Squadron deletes, the observed-result rule, the two narrow windows and the 120 requirement on a missing-run resume (D8 "`--yes` always selects afresh")
- [ ] Beside "The two shipped observers", add the ownership guarantee line (D8): an `sq_run` issuer must include `run_id` in `result`
- [ ] Add `14 PRUNE_INCOMPLETE` to the exit-code table

**Success Criteria**:
- [ ] No Future-work line pointing at slice 110 remains in any contract doc (`grep -rn "slice 110\|or 110" docs/` returns nothing)
- [ ] Committed: `docs: document paused-run pruning in the process contract`

---

### Task 8.2: Write `docs/substrate-guide.md`
**Owner**: Junior AI
**Dependencies**: Task 8.1
**Effort**: 3
**Objective**: The entry point for initiatives 120, 140, 160 (LLD D9).

**Steps**:
- [ ] Frontmatter per `file-naming-conventions.md`
- [ ] Every D9 bullet: the initiative table (120, 140, 160, notification bridge) with contract-section and scenario-step links, the 120 row citing the ownership line; the D4 sequence as prose linking `tests/contract/scenario.py`; the public import roots; the "Store locality" link; the intent-body note (D3); links to the known limits and to this slice's `CHANGELOG.md` entry, without restating them

**Success Criteria**:
- [ ] Every table row has a contract link and a scenario-step link; every link resolves
- [ ] Committed with Task 8.3

---

### Task 8.3: Update `CHANGELOG.md`
**Owner**: Junior AI
**Dependencies**: Task 8.2
**Effort**: 1
**Objective**: One entry for the slice, listing every gap once (LLD D7).

**Steps**:
- [ ] Under `[Unreleased]`, concise "Slice 110" lines: H1–H4, `record_runner_report`, `amoeba prune sq-runs` and exit code 14, the contract proof, the substrate guide, and each gap from "Gaps Found" with how it went

**Success Criteria**:
- [ ] Every gap appears exactly once; the substrate guide's link reaches this entry
- [ ] Committed (8.2–8.3): `docs: add the substrate guide and slice 110 changelog`

---

## Section 9: Validation

### Task 9.1: Final validation and walkthrough
**Owner**: Junior AI
**Dependencies**: Task 8.3
**Effort**: 1
**Objective**: The slice meets the LLD "Success Criteria".

**Steps**:
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each
- [ ] Run the LLD "Verification Walkthrough" steps 1–3 as written, in bash, with a scratch `AMOEBA_STORE_DIR`. Record any difference from the draft and correct the walkthrough in the LLD
- [ ] Check off each LLD "Success Criteria" item against a test or doc; list any not met and stop for the PM
- [ ] Every name added to a public `__all__` appears in its contract doc (review check)

**Success Criteria**:
- [ ] Suite, `ruff`, `pyright` clean; walkthrough confirmed
- [ ] Committed on the slice branch: `docs: confirm the slice 110 verification walkthrough`

---

## Gaps Found

Filled in during Section 5. One entry per gap: what the consumer lacked, D7 class (additive / needs PM), and outcome (commit, or PM decision).

- [ ] (none recorded yet)
