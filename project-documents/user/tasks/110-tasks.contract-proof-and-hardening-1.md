---
docType: tasks
slice: contract-proof-and-hardening
project: amoeba
lld: user/slices/110-slice.contract-proof-and-hardening.md
dependencies:
- 101
- 102
- 103
- 104
- 105
- 106
- 107
- 108
- 109
projectState: Slices 101–109 are merged (store schema 8; `amoeba serve`; `amoeba.inspection`;
  `ExitCode` up to 13 `SERVE_REFUSED`). `amoeba.process` has no `__all__`; `build_tenants`
  lives in `cli/lifecycle.py`; `SquadronRun` has six header fields and no `updated_at`;
  `store_dir`/`project_store_path` are reachable only through `amoeba.store.paths`;
  no `record_runner_report`, no `tests/contract/`, no pruning command.
dateCreated: 20261019
dateUpdated: 20261020
status: not_started
revision_number: 2
---

## Context Summary (File 1 of 2)

- Working on the **contract-proof-and-hardening** slice (110), the last slice of initiative 100 and the gate for initiative 120.
- **Current state (verified against the code, 20261019):**
  - `cli/lifecycle.py:75` `build_tenants(settings, supervisor_dir)` returns `(InboxTenant, ReviewDetectionTenant, CFWatchTenant)` and captures `sq`/`cf` version labels through `capture_sq_version_label` / `capture_cf_version_label`. Consumers: `cli/lifecycle.start` (line 64), `tests/process/test_review_detection_wiring.py` and `tests/process/test_cf_watch_wiring.py` (both call `lifecycle.build_tenants` and monkeypatch `lifecycle.capture_*`). Docs naming it: `docs/process-contract.md:130`, `docs/context-forge-contract.md:187`.
  - `process/__init__.py` holds only a docstring — no `__all__`.
  - `process/observers/sq_runs.py:50` `SquadronRun` (pydantic, `extra="ignore"`, frozen) has `schema_version, run_id, pipeline, params, started_at, status`. `parse_run_file(path) -> SquadronRun | None`.
  - `tests/fixtures/sq_runs/` holds four files (schema 3 and 4); one is `paused` (`run-20260505-review-a697ad3d.json`). `tests/fixtures/README.md` records each fixture's capture date and states fixtures are byte-real.
  - The live runs directory holds v5 paused runs with `updated_at` (e.g. `run-20261015-p5-8a59ee89.json`, *observed 20261019*).
  - `DEFAULT_SQ_RUNS_DIR` (`process/settings.py:21`) is `Path.home() / ".config/squadron/runs"`, evaluated **at import time**. A test changes it only by setting `HOME` for a subprocess.
  - `store/journal.py`: `journal_issue`, `journal_resolve(entry_id, *, outcome, result=None, resolved_by=ISSUER)`, `recorded_result_run_ids(project_id) -> dict[str, str]`, `RESULT_KEY_RUN_ID = "run_id"`.
  - `store/verdicts.py:34` `record_verdict(verdict, *, project_id)` opens `BEGIN IMMEDIATE` and calls `_record_verdict_within` (`store/_verdict_writer.py:135`), which runs inside a caller's transaction. `store/feed.py:85` `record_detection(DetectionInput)`. `DetectionOutcome.RUNNER_ISSUED` exists.
  - `Store` (`store/store.py:52`) is composed of operation mixins.
  - `store/discovery.py:14` `discover_project_ids(store_dir)`. `store/nodes.py:179` `nodes_for_project`.
  - `sq runs prune [run_ids]... --yes` exists (*observed 20261019, Squadron 0.23.3*). Its preview default is `--yes`-less, as the LLD states.
  - `tests/test_public_api.py` pins `amoeba.store.__all__` with `EXPECTED_EXPORTS`. `tests/test_store_safety.py` forbids `store_dir`, `store_path`, `DEFAULT_STORE_DIR` by name in test modules. `tests/test_import_boundaries.py` holds numbered AST rules 1–8.
- **Dependencies:** 101–109 through their contracts (LLD "Prerequisites", "Interfaces Required").
- **What this slice delivers:** LLD "Overview" and "Technical Scope".
- **Next planned work:** initiative 120 (Runner).

**Branch:** all implementation is on `110-slice.contract-proof-and-hardening`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task merges; merging follows the code review.

**Reading note:** tasks do not restate the LLD. "Per the LLD" means open `user/slices/110-slice.contract-proof-and-hardening.md` at the named section (D1–D9, "Migration Plan", "API Contracts", "Data Flow", "Patterns and Conventions"). Keep every new source file near 300 lines, functions near 50.

**Commit cadence:** one commit per task unless a task says "committed with Task N.M". A commit never holds untested behavior or a red suite. Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each before committing.

**Tool knowledge:** no tool guides exist for pydantic, httpx, or pytest in `ai-project-guide/tool-guides/`. Use the context7 MCP for current docs, then the web. Rules: `project-guides/rules/python.md`, `testing.md`, `sql.md`.

**Task-level additions to the LLD** (change only with the PM):
- `ProofRunner` takes its paths and `STANDIN_RUN_AGE` as constructor arguments; `bootstrap.py` passes them. Reason: the step enum and crash points live in `runner_tenant.py` and `scenario.py` references them, so `runner_tenant.py` importing `scenario.py` would be a cycle.
- The proof sets `HOME` for every subprocess and relies on `ProcessSettings()`'s default `sq_runs_dir`, so the resident process and `amoeba prune` derive the runs directory the same way (LLD D8 "No runs-directory flag").
- `cli/prune.py` splits into `run_prune(args)` (resolves `store_dir()` and `DEFAULT_SQ_RUNS_DIR`, maps errors to exit codes) and `prune_sq_runs(...)`, which takes the store directory, runs directory, `confirm`, `timeout_seconds`, and `now` as parameters. Reason: `DEFAULT_SQ_RUNS_DIR` is fixed at import and `SQ_PRUNE_TIMEOUT_SECONDS` is 30 s, so the failure tests call `prune_sq_runs` in-process with `tmp_path` dirs and a short timeout; the CLI wiring is proven by subprocess in scenario step 12. Neither parameter becomes a CLI flag.
- Store-safety extension (LLD "Special Considerations"): `FORBIDDEN_PATH_NAMES` gains `DEFAULT_SQ_RUNS_DIR` and `DEFAULT_CF_DATA_DIR`; the contract harness asserts at start-up that the `HOME` it passes is under `tmp_path`.
- Pruning tests live in `tests/process/` so the LLD walkthrough's `pytest tests/contract tests/process -k prune` selects them.

**Section map.** This file: 1–4. File 2: 5–9. In full: 1 baseline and tenant-order check; 2 migrations (H4, H1, H3); 3 `record_runner_report` (H2); 4 contract foundations; 5 scenario and oracles; 6 network subset; 7 pruning; 8 docs; 9 validation.

---

## Section 1: Baseline

### Task 1.1: Create the branch and record the starting state
**Owner**: Junior AI
**Dependencies**: None
**Effort**: 1
**Objective**: Work on the right branch from a clean baseline.

**Steps**:
- [x] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [x] Create `110-slice.contract-proof-and-hardening` from the target; if it exists, switch to it
- [x] Run `uv run pytest`, `uv run ruff check .`, `uv run pyright` once each. If any fails before changes, stop and tell the PM

**Success Criteria**:
- [x] On the slice branch; baseline suite, `ruff`, and `pyright` clean
- [x] No commit needed

---

### Task 1.2: Pin tenant order before the move
**Owner**: Junior AI
**Dependencies**: Task 1.1
**Effort**: 1
**Objective**: A test that fails if the `build_tenants` move changes which tenants `amoeba start` registers or their order (LLD "Migration Plan").

**Steps**:
- [x] Add `tests/process/test_tenant_order.py`. Call `lifecycle.build_tenants(ProcessSettings(...), supervisor_dir)` with `cf_data_dir` and `sq_runs_dir` under `tmp_path` (use the `supervisor_dir` fixture from `tests/process/conftest.py`)
- [x] Assert the tuple of each tenant's `name`, in order, equals a written-out expected tuple. Read the three names from the tenant classes' `name` attributes once, then write them out literally in the expected tuple, in the order of `build_tenants`'s return statement today (`lifecycle.py:75`), never from sorting or class discovery. Assert the tuple has exactly three entries
- [x] Monkeypatch both `capture_*_version_label` functions to return a fixed string so no `sq`/`cf` subprocess runs

**Success Criteria**:
- [x] Test passes against the current code
- [x] Committed: `test: pin the order of the tenants amoeba start registers`

---

## Section 2: Migrations (no behavior change)

### Task 2.1: Add `updated_at` to `SquadronRun`, with a schema-v5 fixture
**Owner**: Junior AI
**Dependencies**: Task 1.2
**Effort**: 2
**Objective**: The one run-file parser exposes the field pruning needs, tested against the shape the live directory holds today (LLD D7 H4).

**Steps**:
- [x] Copy one live v5 `paused` run file from `~/.config/squadron/runs/` (read-only; never modify that directory) into `tests/fixtures/sq_runs/`, byte-for-byte
- [x] Scan it for secrets (keys, tokens, credentials). Local paths and the `owner` field are acceptable, as in the existing fixtures. If anything must be edited, edit only that, and record the edit in the README row (the `projects.json` entry is the precedent). The LLD's "sanitized" means exactly this
- [x] Add a row to `tests/fixtures/README.md`'s `sq_runs/` table: capture date, `status`, `pipeline`, `schema_version` 5, and "carries `updated_at`, which pruning reads"
- [x] In `process/observers/sq_runs.py`, add `updated_at: datetime | None = None` to `SquadronRun`. Update its docstring ("six header fields" becomes seven; `updated_at` is optional and read only by pruning). Do not move `SquadronRun` or `parse_run_file`, and do not export them from `amoeba.process`
- [x] In `tests/test_observer_sq_runs.py`, add: the v5 fixture parses with all seven fields and a timezone-aware `updated_at` equal to the file's value; a v3/v4 fixture parses with `updated_at is None`
  > Note: v3/v4 fixtures carry their real `updated_at` (they do carry it); the `updated_at is None` case is covered by a derived v5 copy with `updated_at` removed.

**Success Criteria**:
- [x] Fixture present, README row added, no secret in the file
- [x] New tests pass; the existing observer and recovery tests pass with none edited
- [x] Committed: `feat: add updated_at to SquadronRun and a schema-v5 run fixture`

---

### Task 2.2: Move `build_tenants` to `process/tenants.py` as `standard_tenants`
**Owner**: Junior AI
**Dependencies**: Task 2.1
**Effort**: 2
**Objective**: The shipped tenants are composable from `amoeba.process` (LLD D7 H1, "Migration Plan").

**Steps**:
- [x] Create `src/amoeba/process/tenants.py` with `standard_tenants(settings, supervisor_dir) -> tuple[Tenant, ...]`: the body, imports, comment, and docstring of `build_tenants`, unchanged in behavior
- [x] `cli/lifecycle.start` calls `standard_tenants`. Delete `build_tenants` and any import only it used
- [x] Update the consumers: `tests/process/test_review_detection_wiring.py`, `tests/process/test_cf_watch_wiring.py`, and Task 1.2's test. Monkeypatches move to the `amoeba.process.tenants` module's `capture_*` names
- [x] Update `docs/process-contract.md:130` and `docs/context-forge-contract.md:187` to name `standard_tenants` in `process/tenants.py`
- [x] Confirm `amoeba.upstream` still imports nothing from `amoeba.process` (rule unchanged; `test_import_boundaries.py` passes)

**Success Criteria**:
- [x] `grep -rn build_tenants src tests docs` returns nothing
- [x] Task 1.2's test passes against `standard_tenants` with the expected tuple unedited
- [x] Full suite green, 1812 passed
- [x] Committed: `refactor(process): move build_tenants to process/tenants as standard_tenants`

---

### Task 2.3: Export the hosting contract from `amoeba.process`
**Owner**: Junior AI
**Dependencies**: Task 2.2
**Effort**: 2
**Objective**: A tenant author imports only `amoeba.process` (LLD D7 H1, "API Contracts").

**Steps**:
- [x] In `process/__init__.py`, import and list in `__all__` exactly: `ResidentProcess`, `Tenant`, `ProcessSettings`, `Observer`, `Observation`, `Adopt`, `NotApplied`, `Unknown`, `standard_tenants`, `ProcessError`, `AlreadyRunningError`, `StartupFailedError`, `GraceExpiredError`. Find each name's defining module with grep; if any name does not exist, stop and tell the PM
- [x] Check for an import cycle: `python -c "import amoeba.process"` and `python -c "import amoeba.cli.main"` both succeed
- [x] Add `tests/test_process_public_api.py`, in the style of `tests/test_public_api.py`: a written-out `EXPECTED_EXPORTS` set equal to `__all__`; every name importable
- [x] `docs/process-contract.md`: add a "Hosting tenants" section listing the H1 exports, how `amoeba start` composes `standard_tenants`, and how initiative 120 adds its Runner as `(*standard_tenants(…), runner)` in `start`. State that version-label capture never raises (`unavailable` label)

**Success Criteria**:
- [x] `set(amoeba.process.__all__) == EXPECTED_EXPORTS`; `SquadronRun`, `parse_run_file`, and no pruning name in it
- [x] Each of the 13 H1 names appears in `docs/process-contract.md` (LLD "Integration Requirements")
- [x] Committed: `feat(process): export and document the tenant-hosting contract`

---

### Task 2.4: Export `store_dir` and `project_store_path` from `amoeba.store`
**Owner**: Junior AI
**Dependencies**: Task 2.3
**Effort**: 1
**Objective**: A read-only consumer resolves store paths without an internal import (LLD D7 H3).

**Steps**:
- [x] Re-export both from `amoeba.store.__init__` (`paths.py` stays; existing internal imports may stay)
- [x] Add both to `tests/test_public_api.py`'s `EXPECTED_EXPORTS`
- [x] Confirm `tests/test_store_safety.py` still passes: it forbids the *name* `store_dir` in tests, so no test may reference it through the new export either
- [x] `docs/store-contract.md`: name `store_dir` and `project_store_path` by their public import, replacing the internal path

**Success Criteria**:
- [x] `from amoeba.store import store_dir, project_store_path` works; public-API and store-safety tests pass
- [x] Both names appear in `docs/store-contract.md` by their public import
- [x] Committed: `feat(store): export and document store_dir and project_store_path`

---

## Section 3: `record_runner_report` (H2)

### Task 3.1: Implement `record_runner_report`
**Owner**: Junior AI
**Dependencies**: Task 2.4
**Effort**: 3
**Objective**: The Runner reports a review it launched in one transaction (LLD D7 H2, "API Contracts").

> RunnerReportOperations is listed first in Store's bases because it extends JournalOperations and FeedOperations (MRO).

**Steps**:
- [x] Create `src/amoeba/store/runner_report.py` with a mixin class holding `record_runner_report(entry_id, verdict, detection, *, result) -> VerdictRecord`. Add the mixin to `Store`'s bases
- [x] Inside one `with self._connection:` block that starts with `self._execute(sql_inbox.BEGIN_IMMEDIATE, ())` (the shape `record_detected_verdict` uses in `store/feed.py`), in this order:
  1. Validate before writing: `detection.outcome` is `RUNNER_ISSUED` (else `ValueError`); the entry exists (`journal_entry` is not `None`), is unresolved, its kind is in `REVIEW_PRODUCING_KINDS`, and its project is the detection's project (else `InvalidTransitionError`). `REVIEW_PRODUCING_KINDS` is `{SQ_RUN}`, so `result` must always contain `RESULT_KEY_RUN_ID` (else `ValueError`)
  2. `_record_verdict_within(verdict, detection.project_id)` — `record_verdict`'s body and retry rule, unchanged. Refuse as `record_detected_verdict` does if the returned record belongs to another project (`StoreIntegrityError`)
  3. The `runner_issued` ledger row, carrying the verdict's id and node, through `_insert_detection` (`store/feed.py:223`, transaction-free; do not duplicate its SQL). Ledger keys are `UNIQUE (project_id, path, digest)`. If that key is already in the ledger (detection got there first), keep the existing row and insert nothing, as `record_detection` does; the entry is still resolved. Decided in the breakdown; the PM may overrule
  4. The journal resolve with `outcome=COMPLETED`, `resolved_by=ISSUER`, `result`. `journal_resolve` (`store/journal.py:111`) has no transaction-free inner function: extract one, `_resolve_entry_within(entry_id, outcome, result, resolved_by)` holding the `RESOLVE_JOURNAL_ENTRY` execute and the `rowcount != 1` check, and have `journal_resolve` call it inside its own `with self._connection:` with no behavior change
- [x] Retry rule: when the verdict id is already recorded, step 2 returns the existing record and steps 3 and 4 still run, so the entry is resolved and the ledger row written; the method returns the existing record. (A retry after a successful call never reaches this: the entry is resolved, so step 1 refuses.)
- [x] "Unknown" in the LLD's refusal list means an unknown entry id, the case `journal_resolve` words as "does not exist". An entry already resolved, including one resolved `unknown` by `journal_escalate`, is "resolved"
- [x] Docstring lists every refusal and "writes nothing" for each

**Success Criteria**:
- [x] `ruff` and `pyright` strict clean; `store/` still imports nothing from `upstream`, `process`, or `feed` (rule 1)
- [x] Committed with Task 3.2

---

### Task 3.2: Test `record_runner_report`
**Owner**: Junior AI
**Dependencies**: Task 3.1
**Effort**: 2
**Objective**: Prove the one-commit property, each refusal, and the retry rule.

**Steps**:
- [x] Add `tests/store/test_runner_report.py` using the existing evidence/journal harnesses (`tests/evidence_harness.py`; check before adding helpers)
- [x] Happy path: after one call, the verdict exists, one `runner_issued` detection row names its id and node, and the entry is `completed` by `issuer` with `result`; `recorded_result_run_ids` includes the run id for an `sq_run` entry
- [x] One commit: monkeypatch `_resolve_entry_within` to raise; assert no verdict, no ledger row, entry unresolved
- [x] Ledger key already present (an `ingested` row for the same project, path, and digest): the call inserts no second row, keeps the existing one, writes the verdict, and resolves the entry
- [x] Each refusal writes nothing: wrong detection outcome; resolved entry; entry of a non-review kind; entry in another project; `sq_run` entry whose `result` lacks `run_id`
- [x] Retry rule: with the verdict id already recorded through `record_verdict` and the entry unresolved, the call returns the existing record, writes one `runner_issued` row, and resolves the entry; the verdict count is unchanged

**Success Criteria**:
- [x] All tests pass; each refusal test asserts the row counts are unchanged
- [x] Committed (3.1–3.2): `feat(store): add record_runner_report`

---

### Task 3.3: Document `record_runner_report`
**Owner**: Junior AI
**Dependencies**: Task 3.2
**Effort**: 1
**Objective**: The evidence and store contracts name the method (LLD "Technical Scope" Docs).

**Steps**:
- [x] `docs/evidence-contract.md` point 3 (around line 420): replace "deferred to 120 (or 110, if earlier)" with the method, its signature, the one-transaction effect, and its refusals
- [x] `docs/store-contract.md`: add the method to the method list
- [x] Add `record_runner_report` to `tests/test_public_api.py`'s contract-methods check if that test lists methods

**Success Criteria**:
- [x] Both docs name the method; no remaining "deferred to 120 (or 110" text for it
- [x] Committed: `docs: document record_runner_report in the evidence and store contracts`

---

## Section 4: Contract-Proof Foundations

### Task 4.1: Implement the public-import rule
**Owner**: Junior AI
**Dependencies**: Task 3.3
**Effort**: 2
**Objective**: Imports in `tests/contract/` are mechanically limited to public names (LLD D1).

**Steps**:
- [x] Create `tests/contract/__init__.py` and `tests/contract/public_api.py` with `PUBLIC_ROOTS` (exactly the seven roots in D1) and a function returning violations for one source file, walking the AST for `import` and `from … import`
- [x] A violation is: a submodule of a root (`amoeba.store.paths`); a name not in the root's `__all__`; any `amoeba…` module outside `PUBLIC_ROOTS`. Non-`amoeba` imports (stdlib, pytest, httpx, `tests.*`) are allowed
- [x] Read `__all__` by importing the root at test time, not by a copied list

**Success Criteria**:
- [x] Function is pure (path in, violations out); no import of internals in `public_api.py` itself
- [x] Committed with Task 4.2

---

### Task 4.2: Test the public-import rule
**Owner**: Junior AI
**Dependencies**: Task 4.1
**Effort**: 1
**Objective**: The rule catches each violation and passes on the directory.

**Steps**:
- [x] `tests/contract/test_public_api_rule.py`: one `tmp_path` source per violation kind (submodule, unexported name, non-root module) is reported; an allowed source is not
- [x] One test applies the rule to every `.py` file in `tests/contract/` and asserts no violations

**Success Criteria**:
- [x] Tests pass
- [x] Committed (4.1–4.2): `test: add the contract proof's public-import rule`

---

### Task 4.3: Extend the store-safety scan
**Owner**: Junior AI
**Dependencies**: Task 4.2
**Effort**: 1
**Objective**: No test reaches the real runs or CF directory (LLD "Special Considerations", task-level addition above).

**Steps**:
- [x] Add `DEFAULT_SQ_RUNS_DIR` and `DEFAULT_CF_DATA_DIR` to `FORBIDDEN_PATH_NAMES` in `tests/test_store_safety.py`; update its comment
- [x] If an existing test now fails the scan, list it and stop for the PM (do not exempt it silently)
- [ ] Note for Task 4.5: the bootstrap lives under `tests/contract/` and is scanned too. It reads `ProcessSettings().sq_runs_dir`, never the forbidden name `DEFAULT_SQ_RUNS_DIR`, so it passes. The `HOME` contract is owned here: the harness (4.5) sets `HOME` for every subprocess and asserts it is under `tmp_path`; the scan forbids the names; nothing else restates it

**Success Criteria**:
- [x] Scan passes; `tests/contract/` is covered (it is under `tests/`)
- [x] Committed: `test: extend the store-safety scan to the runs and CF directories`

---

### Task 4.4: Implement `ProofRunner`
**Owner**: Junior AI
**Dependencies**: Task 4.3
**Effort**: 3
**Objective**: A real tenant driven by `intent` messages, with named crash points (LLD D3).

**Steps**:
- [ ] `tests/contract/runner_tenant.py`: a `ProofStep` enum (`build_tree`, `launch_review`, `checkpoint`, `finish`) and a `CrashPoint` enum (`AFTER_JOURNAL`, `AFTER_SIDE_EFFECT`); these are their only definitions. Define the intent body's keys once as constants here
- [ ] `ProofRunner` implements `Tenant` only (import from `amoeba.process`). Constructor takes: the fake-`HOME` runs directory, a mapping of project id to reviews directory, the run-file and review fixture paths, and `standin_run_age: timedelta`
- [ ] Each tick: read `pending_intents`, perform one step through the public store API, acknowledge it. Implement each step exactly as D3 describes, including `cf.slice_name` on the slice, `sq.run_id` on the **gate**, and `record_runner_report` parsing the artifact with `parse_review_artifact`/`to_verdict_input`
- [ ] Run files are written from a fixture with `run_id`, `pipeline`, `params`, `started_at` set to match the journal entry; paused ones get `updated_at = now - standin_run_age`
- [ ] At a crash point: `os.kill(os.getpid(), signal.SIGKILL)`, nothing caught or flushed
- [ ] Any `amoeba` import must pass Task 4.2's rule. If `ProofRunner` needs a name its root does not export, never import it from a submodule: that is a gap (LLD D7). Record it in file 2's "Gaps Found"; if adding it to the root's `__all__` (with its contract doc and expected-exports test) is enough, do that in its own commit, otherwise stop for the PM

**Success Criteria**:
- [ ] File near 300 lines (split step bodies into a sibling module if not); public-import rule passes
- [ ] Committed with Task 4.6

---

### Task 4.5: Implement the bootstrap and harness waits
**Owner**: Junior AI
**Dependencies**: Task 4.4
**Effort**: 3
**Objective**: Start, crash, stop, and restart the resident process from tests, failing loudly (LLD "Data Flow", "Patterns and Conventions").

**Steps**:
- [ ] Read `tests/host_harness.py` first. Reuse its subprocess, readiness, and wait helpers; do not copy them. If one needs a change to be reused, extract it with no behavior change and keep its tests green
- [ ] `tests/contract/bootstrap.py`: a `__main__` entry run as `sys.executable -m tests.contract.bootstrap` (never `uv run`), with `cwd` set to the repo root derived from `Path(__file__)` (never the caller's cwd) so `tests.contract` resolves, that builds `ResidentProcess(tenants=(*standard_tenants(ProcessSettings(cf_data_dir=…), supervisor_dir), ProofRunner(…)))` and runs it. `ProcessSettings` keeps its default `sq_runs_dir` (task-level addition above)
- [ ] The harness passes everything per-run to the bootstrap as argparse arguments: `--supervisor-dir`, `--cf-data-dir`, a repeatable `--reviews-dir PROJECT=PATH`, `--run-fixture`, and `--review-fixture`. The bootstrap passes `ProcessSettings().sq_runs_dir` and `scenario.STANDIN_RUN_AGE` to `ProofRunner` itself. A missing or malformed argument exits non-zero with argparse's error
- [ ] A harness object in `bootstrap.py` (or a sibling module) that: builds the env (`HOME`, `AMOEBA_STORE_DIR`, CF data dir, all under `tmp_path`, asserting each is under `tmp_path`); starts the process and waits for readiness; waits for exit after a crash; stops via `amoeba stop` as a subprocess; restarts
- [ ] Every wait is a predicate with a timeout. On timeout, fail with the step number and every subprocess's captured stdout and stderr
- [ ] A `follow()` subscriber on a thread that records each `Change`, stores any exception, and re-raises it on the main thread at the next wait

**Success Criteria**:
- [ ] No bare `sleep`; no `uv run`; public-import rule passes
- [ ] Committed with Task 4.6

---

### Task 4.6: Test the foundations
**Owner**: Junior AI
**Dependencies**: Task 4.5
**Effort**: 2
**Objective**: Prove the harness before the scenario depends on it.

**Steps**:
- [ ] In `tests/contract/test_harness.py`: start, `create_project` through `inbox.submit`, an intent for `build_tree`, wait until the subscriber sees `node_created`; stop cleanly
- [ ] After `watch_reviews` and `build_tree`, a `launch_review` intent with `crash_at=AFTER_JOURNAL`: the process exits by `SIGKILL`, restarts, and recovery runs (the entry is no longer unresolved)
- [ ] A forced readiness timeout fails with captured stderr in the message (use `pytest.raises` on the harness's failure)
- [ ] A subscriber-thread exception is re-raised at the next wait

**Success Criteria**:
- [ ] Tests pass in the default suite; real `HOME` untouched
- [ ] Committed (4.4–4.6): `test: add the proof runner tenant and contract harness`
