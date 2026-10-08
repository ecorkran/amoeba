---
docType: tasks
slice: contract-proof-and-hardening
project: amoeba
lld: user/slices/110-slice.contract-proof-and-hardening.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108, 109]
projectState: Slices 101–104 are merged (store schema 5, inbox, verdicts and findings). In the working tree `src/amoeba/` holds `cli`, `inbox`, `process`, `store`; `amoeba.process.__init__` exports nothing and `cli/lifecycle.py` `start()` builds `tenants=(InboxTenant(supervisor_dir),)` inline. `store/paths.py` uses `AMOEBA_STORE_DIR` and `XDG_CONFIG_HOME` verbatim and `validate_project_id` only calls `validate_path_component`. `NodeOperations.update_node_status` does not refuse leaving `done`. Slices 105–109 are designed and may not be merged when this file starts; Sections 2 and 3 and (in File 2) Tasks 10.2 and 10.3 need only 101–104. Tasks 9.0–9.4 also need 105 (they live in `amoeba.upstream.squadron`). Task 1.2 needs 106. Section 4 needs 101–104 except where it reads detections, judge samples, or 105's parser. Sections 5–8, Task 9.5, and Tasks 10.1 and 10.4–10.6 need 105–109 (File 2 says which).
dateCreated: 20261008
dateUpdated: 20261008
status: not_started
---

## Context Summary

- Working on the **contract-proof-and-hardening** slice (110), the tenth and last slice of initiative 100.
- **What this slice delivers:** (1) a scripted lifecycle proof: a stand-in Runner tenant (`ProofRunner`) in the resident process plus real CLI/HTTP actors, with `kill -9` at named points, ending in the same state every time; (2) hardening found at design: relative store directories refused, project ids restricted to ASCII slugs, `done` made terminal, `amoeba.process` hosting seam, pinned export sets for five public packages; (3) `amoeba prune sq-runs`, a read-only report on dead paused Squadron runs; (4) `docs/README.md`, a contract index with an obligations list.
- **Current state:** see `projectState` above. Test dirs already present: `tests/{cli,inbox,process,store,load,fixtures}`; shared harnesses `tests/host_harness.py`, `tests/cli_harness.py`, `tests/local_host_harness.py`, `tests/load/load_harness.py`. `tests/load/` is excluded from the default run and `ci.yml` already runs it as its own step. `tests/test_public_api.py` pins `amoeba.store` by hand-written set and is the model for the other four pins.
- **Dependencies:** 101–104 through their contracts. **105** (`parse_review_artifact`, `to_verdict_input`, `amoeba ingest review`), **106** (`follow`, `amoeba feed`, `watch_reviews`, `record_detection`, `attribute_review`, `record_runner_report`), **107** (judge samples via `amoeba submit verdict --judge-invocation-id`), **109** (`amoeba serve`, `amoeba token`, SSE resume) supply names the proof binds to. Names in this file for those slices come from their designs; Task 1.1 confirms them against the merged code.
- **Not in this slice:** anything the Runner decides (`ProofRunner` follows a fixed table), `cf_write` in the sequence, real Squadron model calls, journal/message/feed retention, Amoeba deleting Squadron files, performance targets (LLD "Excluded").
- **Next planned slice:** none in initiative 100. Initiative 120 (Runner) designs against this slice's output.

**Branch:** all implementation happens on `110-slice.contract-proof-and-hardening`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging comes after the code review (Phase 7).

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/110-slice.contract-proof-and-hardening.md` at the named section (Technical Decisions D1–D8, Data Flow sequence and kill-point tables, Success Criteria). The step table, kill-point table, snapshot contents, slug pattern, and pruning classification are settled there. Keep every source file near 300 lines. Define each value once (kill-point names, `RunDisposition`, the slug pattern, `paused`) and reference it.

**PM ratification:** both D5 changes were ratified 20261008 (LLD "PM ratification"). No further ruling is needed.

**Commit cadence:** one commit per task unless a task says "Committed with Task N.M". That wording always names the test task that exercises it, and means: make one commit after Task N.M's tests pass, covering every task that names N.M. A task never names a partner that itself defers to a third task, so commit chains cannot form. A commit never holds untested behavior; scaffolding with no behavior (Task 4.1) commits on its own. Semantic prefixes per project CLAUDE.md. Tests that start a process or subprocess use only throwaway directories under `tmp_path`, never the real supervisor directory or the real Squadron runs directory.

**Section map:** this file: 1 branch, gate, baseline; 2 hardening (locality, slug ids, `done` terminal); 3 hosting seam and export pins; 4 proof scaffolding. **File 2 (`...-2.md`):** 5 `ProofRunner` and the clean run; 6 kill points and subscribers; 7 restart matrix; 8 locality under the sequence; 9 pruning; 10 docs and index; 11 final validation.

---

## Section 1: Branch, Gate, and Baseline

### Task 1.1: Create the branch, run the gate, record the names
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 2
**Objective**: Work on the right branch with a known baseline, and know which of 105–109 are present.

**Steps**:
- [ ] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [ ] Create `110-slice.contract-proof-and-hardening` from the target; if it exists, switch to it
- [ ] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once. If any fail before changes, stop and tell the PM
- [ ] **Presence check, by file, not branch name.** For each of 105, 106, 107, 108, 109 record present/absent: `src/amoeba/upstream/squadron/` exists (105); `src/amoeba/feed/` exists and exports `follow` (106); `judge_invocation_id` appears in `src/amoeba/store/` (107); a 108 module exists (see `user/slices/108-*.md` Component Structure); `src/amoeba/serve/` and `src/amoeba/cli/token.py` exist (109). Write the result in the task's notes
- [ ] For each present slice, record the real names the proof will bind to: 106's one-transaction report-back method (LLD says `record_runner_report`; open `user/slices/106-*.md` API Contracts and the merged `Store` to get the exact signature), `attribute_review`, `record_detection`; 105's `parse_review_artifact` and `to_verdict_input`; 109's SSE client helper in `tests/` if it has one (search `tests/` for `text/event-stream`), and which HTTP client library 109's tests use (check the `dev` group in `pyproject.toml` and the imports in `tests/`); Tasks 5.8b and 6.5 use that client and add no second one
- [ ] Record whether 106's report-back method exists. If 106 is merged and it does not, Task 1.2 adds it (the LLD makes this slice responsible). If 106 is not merged, Task 1.2 waits with the other gated tasks
- [ ] **Ask the PM to rule on one naming conflict and record the answer:** the LLD uses `RunDisposition` for two things (the result record in API Contracts, and a status `StrEnum` in Patterns). This file proposes `RunDisposition` for the record and `DispositionKind` for the enum. Task 9.1 uses whichever the PM rules; until ruled, do not start Task 9.1
- [ ] Locate the per-node journal query (search `store/journal.py` for a method taking a node id). Record its name; Task 2.5 uses it

**Success Criteria**:
- [ ] On the slice branch; baseline suite, `ruff`, `pyright` clean
- [ ] Presence table for 105–109 and the confirmed names are written down; the PM's naming ruling is recorded (or Task 9.1 is marked blocked on it)
- [ ] No commit needed

### Task 1.2: Add the one-transaction report-back if 106 shipped without it
**Owner**: Junior AI
**Dependencies**: 1.1
**Effort**: 3
**Objective**: A public `Store` method that records the verdict, marks the review file `runner_issued`, and resolves the journal entry in **one** transaction, so initiative 120 can meet 106's own requirement (106 D5 point 3). Skip this task if Task 1.1 found the method already in the merged `Store`; if 106 is not merged, skip it for now and do it when the gate opens.

**Steps**:
- [ ] Read 106's LLD API Contracts row for `record_runner_report`: `record_runner_report(project_id, *, verdict: VerdictInput, path, digest, journal_entry_id, ...)`. The remaining parameters are those `journal_resolve` and `record_detection` need that are not already listed; take them from those two methods' real signatures and do not add any other parameter
- [ ] Read how `record_verdict`, `record_detection`, and `journal_resolve` each open their own transaction. Implement the new method with one `with self._connection:` block that performs all three writes. Reuse each method's body by extracting its non-transactional part into a private helper that both the existing method and the new one call; do not copy their SQL
- [ ] Idempotent on `(project_id, path, digest)`: a retry returns the existing verdict and writes nothing. A journal entry that is unknown or already resolved raises before any write
- [ ] Export it through the existing `Store` surface (it is a method; no new package export). Add it to `store-contract.md` when Task 10.2 runs

**Success Criteria**:
- [ ] Method exists with the signature fixed above; existing tests still pass
- [ ] Committed with Task 1.3

### Task 1.3: Test the one-transaction report-back
**Owner**: Junior AI
**Dependencies**: 1.2
**Effort**: 2
**Objective**: Prove all-or-nothing and idempotence.

**Steps**:
- [ ] `tests/store/test_runner_report.py`: the happy path leaves one verdict, one `runner_issued` detection for that `(path, digest)`, and a resolved entry
- [ ] Failure atomicity: an unknown journal entry id, and an already-resolved entry, each raise and leave **no** verdict and **no** detection behind
- [ ] Retrying the same call returns the same verdict and creates no second verdict, detection, or resolution

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit `feat: add one-transaction runner report-back to the store`

---

## Section 2: Hardening (D5, D6)

Each fix is a narrowing or enforcement in the store; each is tested at once. `store-contract.md` and `CHANGELOG.md` edits are in Section 10.

### Task 2.1: Refuse relative `AMOEBA_STORE_DIR` and `XDG_CONFIG_HOME`
**Owner**: Junior AI
**Dependencies**: 1.1
**Effort**: 2
**Objective**: `store_dir` raises `ValueError` naming the variable when either variable is set to a relative path (D5, first half).

**Steps**:
- [ ] In `src/amoeba/store/paths.py` change `store_dir`: if `AMOEBA_STORE_DIR` is set and the path is not absolute, raise `ValueError` whose message names `STORE_DIR_ENV_VAR` and the offending value; do the same for `XDG_CONFIG_HOME` using `XDG_CONFIG_HOME_ENV_VAR`. Use the constants, not literals. Empty values keep today's meaning (treated as unset)
- [ ] Update the `store_dir` docstring: "used verbatim" becomes "must be absolute", with the reason (a relative value resolves against each process's own working directory, so process and submitter would use different supervisors)
- [ ] Run the CLI by hand: `AMOEBA_STORE_DIR=relative/dir uv run amoeba status; echo $?`. Confirm the boundary handler turns the `ValueError` into an error naming the variable. If it surfaces a raw traceback or an unhelpful exit, find where `store_dir()` is first called in `cli/` and fix it there (one place), not with a new catch-all

**Success Criteria**:
- [ ] Both variables, when relative, raise `ValueError` naming the variable; absolute values and unset behave as before
- [ ] Hand run shows an error naming `AMOEBA_STORE_DIR`, no traceback
- [ ] Committed with Task 2.2

### Task 2.2: Tests for relative-directory refusal
**Owner**: Junior AI
**Dependencies**: 2.1
**Effort**: 1
**Objective**: Lock the refusal in `tests/test_paths.py`.

**Steps**:
- [ ] Add cases to `tests/test_paths.py`, passing `env=` dicts: relative `AMOEBA_STORE_DIR` raises and the message contains `AMOEBA_STORE_DIR`; relative `XDG_CONFIG_HOME` raises and names it; relative `AMOEBA_STORE_DIR` with a valid `XDG_CONFIG_HOME` still raises (override is not silently skipped); absolute values still resolve as before
- [ ] Add one CLI-level case (in `tests/cli/` using `tests/cli_harness.py`) that `amoeba status` with a relative `AMOEBA_STORE_DIR` exits nonzero and prints the variable name
- [ ] Fix any existing test that set a relative value

**Success Criteria**:
- [ ] New tests pass; full `tests/test_paths.py` and `tests/cli` pass
- [ ] Commit `fix: refuse relative store directory variables`

### Task 2.3: Restrict project ids to ASCII slugs
**Owner**: Junior AI
**Dependencies**: 2.2
**Effort**: 2
**Objective**: `validate_project_id` accepts only `[a-z0-9]([a-z0-9._-]*[a-z0-9_-])?` (D5, second half), defined once.

**Steps**:
- [ ] In `store/paths.py` define the slug pattern once as a module constant with a comment giving the reasons (case-insensitive filesystems, Windows trailing dots, Unicode normalization). `validate_project_id` keeps calling `validate_path_component` first, then applies the pattern, and raises `ValueError` whose message states the rule. Do not change `validate_path_component`, which also validates submission ids
- [ ] Confirm every caller already goes through it: `grep -rn "validate_project_id\|validate_path_component" src` (known: `inbox/envelope.py`, `process/project_stores.py`, `store_path`). Confirm `Store.open` reaches it via `store_path`, and `ResidentProcess.open_project` via `project_stores.py`. If any path to a project id skips it, route that path through it; do not add a second check
- [ ] Confirm what `amoeba submit` does with the `ValueError`/envelope error: the expected outcome is exit `SUBMISSION_REFUSED` (9) with the rule in the message and nothing written. If not, fix at the one place that maps it
- [ ] Update the docstring to state the rule

**Success Criteria**:
- [ ] Uppercase, space, non-ASCII, trailing dot, leading dot or hyphen, and empty ids are refused; `proof`, `proof-b`, `demo.v2`, `a`, `a_` are accepted
- [ ] The pattern literal appears exactly once in `src/` (check with grep)
- [ ] Committed with Task 2.4

### Task 2.4: Tests for slug ids
**Owner**: Junior AI
**Dependencies**: 2.3
**Effort**: 2
**Objective**: Prove the rule at every entry point.

**Steps**:
- [ ] `tests/test_paths.py`: parametrized accept list and refuse list (include `Demo`, `de mo`, `démo`, `demo.`, `.demo`, `-demo`, `` empty, `a/b`, `..`)
- [ ] `tests/store/`: `Store.open` refuses `Demo` and creates no file in the store directory
- [ ] `tests/process/test_project_stores.py`: `open_project("Demo")` raises and creates nothing
- [ ] `tests/cli/test_submit.py`: `amoeba submit create-project --project Demo --by pm` exits 9, prints the rule, and the supervisor directory is empty afterward
- [ ] Fix existing tests or fixtures that use uppercase or odd ids (change the test data, not the rule)

**Success Criteria**:
- [ ] New tests pass; full default suite passes
- [ ] Commit `fix: restrict project ids to ASCII slugs`

### Task 2.5: Make `done` terminal in the store
**Owner**: Junior AI
**Dependencies**: 2.4
**Effort**: 3
**Objective**: Four refusals, all `InvalidTransitionError`, per D6: nothing happens on a finished node.

**Steps**:
- [ ] `update_node_status` (`store/nodes.py`): refuse any change away from `done`. Setting `done` on an already-`done` node is not a change away, so it stays a no-op success (a retried "mark done" must stay repeatable); say so in a comment
- [ ] `block()` (`store/blocking.py`): refuse a node whose status is `done`
- [ ] `journal_issue` (`store/journal.py`): refuse a `done` node
- [ ] `update_node_status(done)`: refuse a node that has an unresolved journal entry, using the per-node query recorded in Task 1.1. Do this check in the same transaction as the status write, or the check can race the write
- [ ] Each message says what was refused and why ("finished nodes are final"). Do not add a new exception type, and do not add a branch to `journal_escalate` (the last rule means recovery never meets an unresolved entry on a `done` node)
- [ ] Search `src/` for any internal caller that moves a node out of `done` (`resolve`, recovery, inbox apply). If one exists, stop and tell the PM; the LLD assumes none

**Success Criteria**:
- [ ] The four refusals raise `InvalidTransitionError`; `done` to `done` succeeds
- [ ] No other store behavior changes
- [ ] Committed with Task 2.6

### Task 2.6: Tests for `done` terminal
**Owner**: Junior AI
**Dependencies**: 2.5
**Effort**: 2
**Objective**: One test per refusal plus the allowed cases.

**Steps**:
- [ ] Add `tests/store/test_done_terminal.py`: done → runnable refused; done → every other non-blocked status refused; `block()` on a `done` node refused for each blocked kind; `journal_issue` on a `done` node refused; marking done a node with an unresolved entry refused, and succeeds once the entry is resolved; `done` → `done` succeeds; the node's status and journal are unchanged after each refusal
- [ ] Run the whole suite. Fix existing tests that reopen a `done` node (change the test, not the rule)

**Success Criteria**:
- [ ] New tests pass; full default suite passes; `ruff` and `pyright` clean
- [ ] Commit `fix: enforce done as a terminal node status`

---

## Section 3: Hosting Seam and Export Pins (D3, D2)

### Task 3.1: `standard_tenants` and the `amoeba.process` exports
**Owner**: Junior AI
**Dependencies**: 2.6
**Effort**: 2
**Objective**: One list of standard tenants, and `amoeba.process` exports the hosting seam.

**Steps**:
- [ ] Create `src/amoeba/process/tenants.py` with `standard_tenants(supervisor_dir, settings) -> tuple[Tenant, ...]`. It returns the inbox tenant first. If 106 is merged (Task 1.1), the detection tenant is second; check how `cli/lifecycle.py` registers it today and move that exact registration here. If 106 is not merged, return the inbox tenant alone and add a comment that 106's detection tenant is added here, second
- [ ] `cli/lifecycle.py` `start()` calls `standard_tenants` and keeps its comment about ordering (move the ordering rationale to `tenants.py`)
- [ ] Export from `amoeba/process/__init__.py`: `ResidentProcess`, `Tenant`, `ProcessSettings`, `Observer`, `Adopt`, `NotApplied`, `Unknown`, `standard_tenants`, with `__all__`. Find where `Observer`, `Adopt`, `NotApplied`, `Unknown` are defined (`grep -rn "class Observer\|class Adopt\|class NotApplied\|class Unknown" src/amoeba/process`) and import from there. Update the package docstring to point at "Hosting a tenant" (written in Task 10.1)
- [ ] Confirm importing `amoeba.process` does not create an import cycle with `amoeba.cli` (run `uv run python -c "import amoeba.process"`)

**Success Criteria**:
- [ ] `amoeba start` behavior is unchanged (existing `tests/test_cli_lifecycle.py` and `tests/process` pass)
- [ ] `from amoeba.process import ResidentProcess, standard_tenants` works; the store still imports nothing from `amoeba.process`
- [ ] Committed with Task 3.2

### Task 3.2: Tests for the seam
**Owner**: Junior AI
**Dependencies**: 3.1
**Effort**: 2
**Objective**: Prove the order and that a host can be built from public exports alone.

**Steps**:
- [ ] `tests/process/test_tenants.py`: `standard_tenants` returns the inbox tenant at index 0 (and detection at index 1 when present); the tuple is what `start()` passes (assert via a spy on `ResidentProcess` construction, or by constructing with `standard_tenants` and checking `host.tenants`)
- [ ] A test builds `ResidentProcess(settings, store_dir=..., version=..., tenants=(*standard_tenants(...), extra))` using only names imported from `amoeba.process`, runs it with the shared `tests/host_harness.py` pattern, and shows `extra.tick` is called after the inbox tenant's

**Success Criteria**:
- [ ] New tests pass; `tests/test_writer_guard.py` still passes
- [ ] Commit `feat: export tenant hosting seam from amoeba.process`

### Task 3.3: Pin the export sets of the four other public packages
**Owner**: Junior AI
**Dependencies**: 3.2
**Effort**: 2
**Objective**: Hand-written export-set tests for `amoeba.process`, `amoeba.inbox`, `amoeba.feed`, `amoeba.upstream.squadron`, alongside the existing one for `amoeba.store`. One shared helper, four short test modules (each pin is the same check against a different literal set).

**Steps**:
- [ ] Read `tests/test_public_api.py` once. Add `tests/export_pins.py` with one helper `assert_exports(module, expected)`: asserts `set(module.__all__) == expected` (the set is written out literally by the caller, never derived from `__all__`) and that every name resolves via `getattr`
- [ ] `tests/test_public_api_process.py`: the eight names from the LLD (`ResidentProcess`, `Tenant`, `ProcessSettings`, `Observer`, `Adopt`, `NotApplied`, `Unknown`, `standard_tenants`)
- [ ] `tests/test_public_api_inbox.py`: re-read `src/amoeba/inbox/__init__.py` now and write out its current `__all__` (`submit`, `failed`, `pending`, `quarantined`, the three transfer objects, four exceptions, plus anything 105–109 added)
- [ ] `tests/test_public_api_feed.py`: if `src/amoeba/feed/` is absent (Task 1.1), skip this module and record it; Task 6.5 does it once 106 lands. Otherwise write out the merged `__all__` (expected to include `follow`, `FeedSettings`, `Change`, and `change_as_json` if 109 landed)
- [ ] `tests/test_public_api_squadron.py`: if `src/amoeba/upstream/squadron/` is absent, skip and record it (Task 6.5 does it later). Otherwise write out the merged `__all__` (105's list: `parse_review_json`, `parse_review_artifact`, `ParsedReview`, `to_verdict_input`, `review_record_id`, `SquadronReviewError`, `SquadronParseError`, `UpstreamVersionError`). Task 9.1 adds `classify_paused_runs`, `RunDisposition`, `DispositionKind`

**Success Criteria**:
- [ ] Every module that could be written passes; adding a stray name to one `__all__` makes its test fail (check once by hand, then revert)
- [ ] Skips, if any, are recorded with the slice that unblocks them
- [ ] Commit `test: pin public export sets for process, inbox, feed, squadron`

---

## Section 4: Proof Scaffolding (D1, D2, D4)

All files under `tests/contract/`. Every module there may import only the five public packages and only names in their `__all__` (the guard in Task 4.9 enforces it), read no `_`-prefixed attribute, and import no `sqlite3`.

### Task 4.1: Create `tests/contract/` and its conftest
**Owner**: Junior AI
**Dependencies**: 3.3
**Effort**: 1
**Objective**: A package with throwaway-directory fixtures.

**Steps**:
- [ ] Create `tests/contract/__init__.py` and `conftest.py`, copying the `sys.path` approach and the `supervisor_dir` / `runs_dir` fixtures from `tests/load/conftest.py`. Add a `reviews_dir` fixture (throwaway, under `tmp_path`), a `host_dir` fixture (the resident process's working directory), and a `work_dir` fixture (the CLI actors' working directory); the two are different directories
- [ ] Mark nothing slow: the default suite runs this directory

**Success Criteria**:
- [ ] `uv run pytest tests/contract --collect-only` succeeds with zero tests
- [ ] Commit `test: add contract-proof package and fixtures` (scaffolding only, no behavior)

### Task 4.2: `fake_squadron.py`
**Owner**: Junior AI
**Dependencies**: 4.1, 1.1
**Effort**: 3
**Objective**: Stand-in for Squadron that writes run files and review artifacts shaped from captured fixtures, with no model calls.

**Steps**:
- [ ] Read `tests/fixtures/README.md`, one completed run in `tests/fixtures/sq_runs/`, the captured paused run `run-20260505-review-a697ad3d.json`, and `tests/fixtures/sq_reviews/102-review.tasks.resident-process-and-recovery.part-1.md` and `part-2.md`
- [ ] Provide: `write_completed_run(runs_dir, run_id) -> Path`; `write_paused_run(runs_dir, run_id) -> Path`; `write_review_round(reviews_dir, round_number) -> Path` returning the artifact path (round 1 part 1 and round 2 part 1, built by copying the fixture files with the fields the parser reads preserved: slice name `resident-process-and-recovery`, `review_type`, verdict `CONCERNS`, findings). Generate run ids deterministically from a counter so two runs of the proof compare equal
- [ ] Copy-and-adjust fixtures rather than hand-writing JSON; the run file must be one the existing `process/observers/sq_runs.py` reads as it reads real runs (it matches runs to journal entries by command, time, and project; check what it requires and satisfy exactly that)
- [ ] The module writes only inside the directories it is handed

**Success Criteria**:
- [ ] Every file it writes parses with 105's `parse_review_artifact` (if 105 present) and is read by `observers/sq_runs.py` as a completed or paused run
- [ ] Committed with Task 4.3

### Task 4.3: Test `fake_squadron.py`
**Owner**: Junior AI
**Dependencies**: 4.2
**Effort**: 2
**Objective**: The fake's output is accepted by the real readers, so the proof does not rest on a fake the system would reject.

**Steps**:
- [ ] `tests/contract/test_fake_squadron.py`: run the sq_runs observer's reading function (find the public one used by `tests/test_observer_sq_runs.py`; that test shows how) on the written completed and paused runs and assert status classification; if 105 is present, parse each written review and assert slice name, verdict, and at least one finding; assert two calls with the same counter produce identical bytes

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit `test: add contract-proof scaffolding and fake Squadron`

### Task 4.4: `snapshot.py` (`LifecycleSnapshot`)
**Owner**: Junior AI
**Dependencies**: 4.3
**Effort**: 4
**Objective**: Build the final state from public reads only, keyed by node title (D4). Comparison is Task 4.4a.

**Steps**:
- [ ] Define `LifecycleSnapshot` (frozen dataclass) and `build_snapshot(supervisor_dir, project_id)`. It opens the store read-only through `Store.open_read_only` (exported by `amoeba.store`; check the name) and reads through public methods only. Contents per the LLD: node status by title; set of verdict record ids with verdict and standing; finding keys per node; journal entries per node as `(kind, outcome class)` where `completed` and `adopted` are one class "applied"; blocked-state count per node; message count per channel; judge samples per gate (read with the public `verdicts(..., judge_invocation_id=J)` filter from 107); detection outcomes (via 106's read method if present)
- [ ] Parts needing a later slice (detections, judge samples, finding keys) are included when the read exists; otherwise the field is omitted and a module-level comment lists which field waits for which slice. Do not stub with fake values
- [ ] Verdict record ids are compared as a set of ids; if ids differ between runs because they embed a timestamp, use the record id 105 derives from parsed content (identical across runs) and otherwise compare `(title, verdict, standing)` tuples. Check by building two snapshots in Task 4.5

**Success Criteria**:
- [ ] Module under ~300 lines, no private attribute reads, no `sqlite3`
- [ ] Committed with Task 4.5

### Task 4.4a: Snapshot comparison
**Owner**: Junior AI
**Dependencies**: 4.4
**Effort**: 2
**Objective**: Compare two snapshots and report differences, with named allowed differences (D4).

**Steps**:
- [ ] `compare(clean, other, *, allowed_differences)` returns the list of differences; an empty list means equal. `allowed_differences` is a set of named differences defined once as a `StrEnum` or constants in this module (per kill point, Task 6.1 fills them: `after-issue` adds one `unknown` entry, one human block, one escalation on the slice node)

**Success Criteria**:
- [ ] Module still under ~300 lines (split `compare` into its own module if not), no private attribute reads, no `sqlite3`
- [ ] Committed with Task 4.5

### Task 4.5: Test `snapshot.py`
**Owner**: Junior AI
**Dependencies**: 4.4a
**Effort**: 2
**Objective**: Snapshot equality and difference reporting work on built stores.

**Steps**:
- [ ] `tests/contract/test_snapshot.py`: build two stores in two temp dirs with the same nodes, statuses, a journal entry, and a block; snapshots are equal though node ids differ. Change one node status in the second: `compare` reports exactly that difference. Add one unresolved `unknown` entry to the second: `compare` reports it, and passes when it is listed in `allowed_differences`. `completed` vs `adopted` entries compare equal. Cover each remaining snapshot field with a one-field difference that `compare` must report: a verdict added or with a different standing; a finding key added to a node; a blocked state added; a message on one channel; a judge sample added to a gate and a detection outcome changed (these two only if 106/107 are present, else the test notes the skip)

**Success Criteria**:
- [ ] Tests pass
- [ ] Commit `test: add lifecycle snapshot for the contract proof`

### Task 4.6: `proof_harness.py` — process control
**Owner**: Junior AI
**Dependencies**: 4.5
**Effort**: 4
**Objective**: Start, kill, and restart the host; wait for conditions; run CLI actors as subprocesses.

**Steps**:
- [ ] Read `tests/host_harness.py` and `tests/cli_harness.py` first and reuse what they provide (a subprocess runner, env building, wait helpers); extend them only if a needed capability is missing, otherwise import them. Do not write a second subprocess helper
- [ ] Provide: `start_host(...)` launching `proof_host.py` (Task 4.7) as a subprocess with `AMOEBA_STORE_DIR`, the throwaway runs directory, and an optional kill-point environment variable; `wait_until(condition, timeout)` polling public state (never a fixed sleep); `run_cli(args, env)` running `amoeba …` from `work_dir` (a different working directory from the host's); `kill_host()` for the harness-side `kill -9`
- [ ] `start_host` launches the process with `cwd=host_dir`; `run_cli` and every actor use `cwd=work_dir`; the two are never the same path (assert it in the harness). This is what makes the locality claim in Task 8.1 mean something
- [ ] The timeout of every wait is a named constant in one place; a timeout fails the test with the last observed state in the message

**Success Criteria**:
- [ ] A scratch test starts the host, `amoeba status` from `work_dir` reports it running, `stop` stops it
- [ ] Committed with Task 4.8

### Task 4.7: `proof_host.py` — bootstrap through public exports
**Owner**: Junior AI
**Dependencies**: 4.6
**Effort**: 2
**Objective**: The three-line host that Task 10.1 will quote in `process-contract.md`.

**Steps**:
- [ ] Create `proof_host.py` runnable as `python -m` / by path. It reads the supervisor dir, runs dir, and kill point from its environment or arguments, builds `ProcessSettings`, then `ResidentProcess(settings, store_dir=..., version=..., tenants=(*standard_tenants(supervisor_dir, settings), ProofRunner(...)))`, `install_signal_handlers()`, `run()`. Imports only from `amoeba.process` (and `ProofRunner` from this package). Until Task 5.x exists, register no extra tenant
- [ ] Keep the construction lines contiguous and free of test-only noise so they can be quoted verbatim in the docs

**Success Criteria**:
- [ ] The harness scratch test from Task 4.6 now runs through `proof_host.py`
- [ ] Committed with Task 4.8

### Task 4.8: Harness smoke test
**Owner**: Junior AI
**Dependencies**: 4.7
**Effort**: 1
**Objective**: Replace the scratch test with a permanent one.

**Steps**:
- [ ] `tests/contract/test_harness_smoke.py`: start the host, submit `create-project proof` from `work_dir`, wait until the project is listed by `amoeba inspect projects --json`, stop the host, assert exit `OK`. Then start, `kill -9`, restart, and assert the host comes back (status running)

**Success Criteria**:
- [ ] Test passes twice in a row (no leaked processes or lock files: assert the lock is free at the end)
- [ ] Commit `test: add proof host bootstrap, harness, and smoke test`

### Task 4.9: `test_public_only.py` — the no-internal-access guard
**Owner**: Junior AI
**Dependencies**: 4.8
**Effort**: 3
**Objective**: Make "only the documented contract" a mechanical check (D2).

**Steps**:
- [ ] Define the five public packages once (`amoeba.store`, `amoeba.inbox`, `amoeba.feed`, `amoeba.process`, `amoeba.upstream.squadron`) as a constant. Walk the AST of every `.py` in `tests/contract/` and report, with file and line: an `amoeba` import of any other module (a submodule of a public package counts as another module); a `from <public package> import name` where `name` is not in that package's `__all__` (import the package and read `__all__`); any attribute access whose name starts with `_` (dunder names like `__name__` are allowed: say so in a comment); an import of `sqlite3`
- [ ] Skip the guard test file itself when walking (it must name `sqlite3` and `_` to test for them). A public package that does not exist yet (106's feed, 105's squadron) is skipped with a recorded reason, not failed
- [ ] Self-test: the guard function takes source text, so tests feed it four bad snippets (a private-module import, a non-exported name, a `_private` attribute read, `import sqlite3`) and assert each is reported, plus a clean snippet that is not

**Success Criteria**:
- [ ] The guard passes over the current `tests/contract/`; each bad snippet is caught; a deliberate `from amoeba.store.sql import NODES_TABLE` appended to `snapshot.py` fails the real run naming file and line (check once by hand, then remove)
- [ ] Commit `test: add public-contract guard for the contract proof`
