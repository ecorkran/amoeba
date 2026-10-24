---
docType: tasks
slice: run-dispatch-and-outcome-ingestion
project: amoeba
lld: user/slices/125-slice.run-dispatch-and-outcome-ingestion.md
dependencies:
- 120
- 121
- 122
- 123
- 124
projectState: Slices 120–124 are merged. `amoeba.runner` has the tick (`runner/tick.py`,
  with a `# [route - slice 126]` slot), `decide.py` (`Action = LaunchRun | BlockHumanStep`,
  `ProjectView.current_steps`, the current-step guard), `finish.record()` with 122's
  minimal body, `launch.py` (`launch()`, `log_paths`, `stderr_confirms`), and `PRODUCTION_PLANNERS
  = (HumanStepPlanner(),)` in `runner/factory.py`. `process/sq_outcome.py` has `RunCheckpoint(paused_at)`
  only. `cf_write` requires `{project, expected}`. The store is at migration `010`.
  `record_runner_report` takes one review. The stem rule lives in `runner/lifecycle/slugs.py`
  and parses design file names only. `amoeba.runner.dispatch` and `amoeba.runner.ingest`
  do not exist.
dateCreated: 20261024
dateUpdated: 20261024
status: in_progress
turns: 48
promptTokens: 4568605
cachedTokens: 4415865
cacheWriteTokens: 152648
completionTokens: 53879
durationSeconds: 676.3
costUsd: 3.182593
usageRounds: 3
pricedRounds: 3
revision_number: 2
---

## Context Summary

- Working on the **run-dispatch-and-outcome-ingestion** slice (125), the sixth slice of initiative 120 (Runner and Routing Engine). It is the first slice whose production planner launches anything: a driven pipeline step gets a CF pointer write, then a Squadron run, and the finished run becomes evidence awaiting routing.
- **Current state:** nothing dispatches. 122's `finish.record()` blocks and resolves without recording reviews. The store has no routing flag.
- **Dependencies:** 120 (`poll_run`, `RunOutcomeDocument`, by-id observer), 121 (`record_routing_decision`, project-scoped escalation), 122 (tick, `TickBudget`, `launch()`, faults), 123 (`STEP_MAP`, step nodes, stem rule, migration `010`), 124 (`current_steps`, guard). All merged. squadron-ai 0.23.5+ shapes and CF worktree routing (observed CF 0.19.16) per the LLD, "Interfaces Required".
- **What this slice delivers:** contract changes to 100 (D10, D8: `cf_write` keys, the read-back in the checkout, migration `011`, `unrouted_outcomes`, multi-review `record_runner_report`, `detection_key`); the extended outcome document; `amoeba.runner.ingest`; `amoeba.runner.dispatch`; the pointer write in Act; the reissue path (issue #9); the pointer-move check; `DispatchPlanner` in production; contract text and CHANGELOG.
- **Next planned slice:** 126 (routing engine), which reads `unrouted_outcomes` and records decisions.

**Branch:** all implementation happens on `125-slice.run-dispatch-and-outcome-ingestion`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/125-slice.run-dispatch-and-outcome-ingestion.md` at the named decision (D1–D12), "Architecture", or "Implementation Details". Source lives under `src/amoeba/`; paths below are relative to it unless they start with `tests/` or `docs/`. Keep every new or changed source file near 300 lines and each function near 50.

**Order and dependencies:** work tasks in file order. Each task's **Dependencies** lists only its real prerequisites. If a task is `BLOCKED:`, continue with the next task whose dependencies are all checked off; only its dependents wait.

**Commit cadence:** one commit per task. A commit never holds untested behavior. Run `uv run ruff format .` before each commit. Commit type is `feat:` for new behavior, `refactor:` for behavior-preserving change, `test:` for test-only work, `docs:` for contract text.

**Task-level additions to the LLD** (code facts the LLD does not state, checked against the code on 20261024; each resolves a placement, not a product decision):
- **Planner tuple location.** The LLD puts the production tuple in `tenant.py`. In the code it is `PRODUCTION_PLANNERS` in `runner/factory.py`. Change it there.
- **The stem rule moves to `amoeba.upstream.context_forge`.** The read-back observer (`process/observers/cf_readback.py`) must parse an index from `fileSlice`, but `amoeba.process` may not import `amoeba.runner` (`tests/test_import_boundaries.py`, Rule 10). Task 2.1 defines one stem parser in the upstream package, and `runner/lifecycle/slugs.py` delegates to it.
- **The detection key call site.** The LLD says detection's "directory source" forms the key. `DirectoryReviewSource` is in `store/review_sources.py`, which may not import `amoeba.process` (Rule 1). The key is actually formed in `process/review_scan.py`'s `examine` (`str(detected.path)`, `content_digest`). Task 2.7 makes `examine` and ingest share `detection_key` there.
- **The routing-flag stand-in.** 126 does not exist. Tests that need a routing decision call `store.record_routing_decision` directly, through one helper in `tests/runner/ingest/routing_support.py` (Task 4.4).
- **Shared names, defined once.** `DispatchState`, `CheckpointKind`, `FailureKind`, the new `FaultKind` members, the `slice`/`merge` param keys and the `false` value, the `cf_write` keys `checkout` and `expected_slice_index`, the result keys `outcome_document`, `verdict_ids`, `review_fault`, `worktree_id`, `project_path`, `file_slice` (defined in Task 2.3) and `cf_updated_at` (defined in Task 6.3), and the block reasons `failed`, `orphaned`, `vanished`, `started_before_crash`. Tests import them. They never retype a value.
- **Exception rule.** No new `except Exception`. Every `except` names a specific exception with a comment, or re-raises after `logger.exception`. Expected external failures are answers (`CheckoutUnresolved`, `ReviewUnknown`, a failed pointer write), never exceptions.
- **Upstream fixtures are real.** New Squadron and CF fixtures are captured from the real tools with read-only commands and recorded in `tests/fixtures/README.md` with the capture date. A fixture changed by hand carries `-edited` in its name, as existing ones do.
- **Test doubles.** Pure functions get table-driven tests. Store-backed tests use `Store.open_temporary()`. Tick-level tests use `tests/runner/tick_support.py` and `plan_tick_support.py` with the stub `cf` (`tests/cf_stub.py`) and stub `sq` (`tests/sq_stub.py`) on `PATH` under a temporary `HOME`. Nothing sleeps or runs a real `cf` or `sq`.
- **Test naming and location.** Tests are named for the rule they prove (LLD, Verification Walkthrough step 1). New test packages: `tests/runner/dispatch/` and `tests/runner/ingest/` (each with `__init__.py`).

**Section map.** 1 baseline; 2 contract changes (stem rule, `cf_write`, observer, migration, flag, report, decision, detection key, contract text); 3 outcome document and stub `sq`; 4 ingestion; 5 dispatch core (pure); 6 stub `cf` and the pointer write; 7 Observe, view and launch wiring; 8 reissue; 9 pointer move; 10 production wiring, contract text and final validation.

**Overrun fallback** (LLD, Implementation Notes): Sections 8 and 9 are independent of each other. If the slice overruns, either can be split into a follow-on slice through a plan edit. Until Section 8 lands, Task 7.3's Act blocks a `REISSUE` step on `HUMAN` instead of launching.

---

## Section 1: Baseline

### Task 1.1: Create the branch and record the starting state
**Owner**: Junior AI | **Dependencies**: None | **Effort**: 1

- [x] Confirm `pwd` is the amoeba repo root. Read the target with `cf config get git.integration_branch` (empty means `main`)
- [x] Run `git status --short`. The tree must be clean before the branch is created. Uncommitted edits to planning documents (the arch, the initiative plan, the slice or its tasks) are committed to the target first as `docs:`, each file by name. If any other file is dirty, write `BLOCKED:` naming it and stop
- [x] Check the two external preconditions now, so the slice fails before any contract work. Both are read-only:
  - [x] `cf worktree list --json` has an entry whose `worktreePath` is the repo root (Task 2.3 needs it for the worktree-form fixture). Do not register a worktree yourself
  - [x] `sq runs list` shows local completed, failed and paused runs (Task 3.1 captures fixtures from them). Paused runs are those whose run-state file in `~/.config/squadron/runs/` contains `"status": "paused"`
  - If either is missing, write `BLOCKED:` naming the missing item and stop
- [x] Confirm the D7 correction to the arch "Run identity" sentence (`user/architecture/120-arch.runner-routing-engine.md`) is present per the LLD. If it is not, make that edit and commit it as `docs:`
- [x] Create `125-slice.run-dispatch-and-outcome-ingestion` from the target. If it exists, switch to it
- [x] Run `uv run pytest -q`, `uv run ruff check .`, `uv run pyright` once each
- **Success Criteria**:
  - [x] On the slice branch with a clean tree. Baseline suite, `ruff` and `pyright` are clean. If not, write `BLOCKED:` with the failure and stop. This task adds no commit of its own

---

## Section 2: Contract changes to 100 (D10, D8)

These land before the new Runner modules (`ingest`, `dispatch`) and the tick wiring (LLD, D10 "Order"). Task 2.1 touches `runner/lifecycle/slugs.py` only to delegate to the shared parser.

### Task 2.1: One slice stem parser in the upstream package, with tests
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

See "Task-level additions". Create a module in `upstream/context_forge/` (for example `slice_stem.py`) and export it from the package's `__init__.py`.

- [x] `parse_slice_stem(text: str | None) -> SliceStem | None`, where `SliceStem` is a frozen dataclass `(index: int, name: str)`. Accept `NNN-slice.{name}` (CF's `fileSlice`/`activeSlice` form) and `NNN-slice.{name}.md` (a design file), with or without a directory. Lenient on digit count; `None` for empty input or any other shape
- [x] Change `runner/lifecycle/slugs.py` so `slice_name_from_design_file` delegates to it. Behavior for design file paths is unchanged. The regex exists only in the new module
- [x] Tests (table-driven): the real `fileSlice` value from `tests/fixtures/cf/cf_get_amoeba.json`; the real `activeSlice` form (`125-slice.run-dispatch-and-outcome-ingestion`); a `.md` path with directories; a name containing dots; empty, `None`, `slice.foo`, `125-tasks.foo` give `None`. Existing `slugs` tests pass unchanged
- **Success Criteria**:
  - [x] Tests, `tests/test_import_boundaries.py`, `ruff` and `pyright` pass. Commit: `refactor: define the slice stem rule once in the CF upstream package`

### Task 2.2: `cf_write` gains `checkout` and `expected_slice_index`, with tests
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

Per the LLD, D10 "`cf_write`". Edit `store/journal_models.py` and its tests (`tests/test_journal_models.py`, `tests/test_journal.py`).

- [x] Define `PARAM_CHECKOUT` and `PARAM_EXPECTED_SLICE_INDEX` once in `journal_models.py` and export them from `amoeba.store`
- [x] `REQUIRED_PARAMETER_KEYS[CommandKind.CF_WRITE]` becomes `{project, expected, checkout}`. `expected_slice_index` stays optional
- [x] Find every `cf_write` issuer in `src/` and `tests/` (`grep -rn "CF_WRITE" src tests`) and add `checkout` where a new entry is issued. Rows already in a store are untouched
- [x] Tests: `journal_issue` of a `cf_write` without `checkout` raises the existing missing-key error; with `checkout` and with or without `expected_slice_index` it succeeds
- **Success Criteria**:
  - [x] Journal tests, `ruff` and `pyright` pass, and the full suite still passes. Commit: `feat: require a checkout on cf_write journal entries`

### Task 2.3: The read-back runs in the checkout and checks the slice index, with tests
**Owner**: Junior AI | **Dependencies**: 2.1, 2.2 | **Effort**: 3

Per the LLD, D10 bullets on the observer, D2 "Read-back". Edit `process/observers/cf_readback.py` and `tests/test_observer_cf_readback.py`.

- [x] Capture one real fixture (Task 1.1 confirmed the registered worktree): from the repo root, run `cf get --json -p <id>` (read-only), where `<id>` is the top-level `id` field of `tests/fixtures/cf/cf_get_amoeba.json`. Save the bytes as `tests/fixtures/cf/cf_get_worktree.json`. Confirm it carries `fileSlice`, `projectPath` and a `worktree` object with `id`. Add a README entry with the date
- [x] `CFProjectRecord` reads `worktree.id` and `projectPath` in addition to the fields it reads today
- [x] When the entry has `checkout`, run `cf get` with `cwd=checkout`. Without it (entries before this slice), run with no working directory
- [x] When `expected_slice_index` is present: `fileSlice` parsed by `parse_slice_stem` to that index is a match; another index is `NotApplied`; an absent field or a `fileSlice` that does not parse is `Unknown`
- [x] An empty `expected` with no `expected_slice_index` is `Unknown` (no vacuous adoption)
- [x] Adoption records `file_slice`, `worktree_id` and `project_path` in its result. Define the result keys once (they are reused by Tasks 6.2–6.3)
- [x] Expose the comparison as one function the in-tick read-back can call (LLD, D10 "There is one read-back"). Name it in this task, for example `read_back_cf_write(entry, run, timeout)`; Task 6.2 calls it, never a copy
- [x] Tests: the worktree fixture with a matching index adopts with the three fields; another index is `NotApplied`; a fixture with `fileSlice` removed is `Unknown`; empty `expected` and no index is `Unknown`; the subprocess is called with `cwd` equal to `checkout` (injected runner) and with no `cwd` for an old entry; existing tests pass. Run `tests/test_recovery.py`
- **Success Criteria**:
  - [x] Observer and recovery tests, `ruff` and `pyright` pass. Commit: `feat: read back CF writes in their checkout and check the slice index`

### Task 2.4: Migration `011` and `JournalEntry.awaits_routing`, with tests
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

Per the LLD, "Database / Storage Schema" and D8. Create `store/schema/011_journal_awaits_routing.sql` and `tests/store/test_migration_011.py` (model it on `test_migration_010.py`).

- [x] The migration adds `awaits_routing INTEGER` and the partial index `idx_journal_awaits_routing` exactly as in the LLD. Register it wherever `010` is registered
- [x] `JournalEntry` gains `awaits_routing: bool`. The row mapping (`store/mapping_journal.py`) reads null and `0` as `False`, `1` as `True`
- [x] Tests: on a populated v10 store, `011` applies, every existing row reads `awaits_routing=False`, and the schema version reports `11`; `tests/test_migrations.py` passes
- **Success Criteria**:
  - [x] Tests, `ruff` and `pyright` pass. Commit: `feat: add the awaits_routing journal flag (migration 011)`

### Task 2.5: Issuer resolutions set the flag; `unrouted_outcomes`, with tests
**Owner**: Junior AI | **Dependencies**: 2.4 | **Effort**: 3

Per the LLD, D8. Edit `store/journal.py` (and `store/sql_journal.py` for the query).

- [x] Every issuer resolution of an `sq_run` entry through `journal_resolve` sets `awaits_routing = 1` in the same transaction. Recovery resolutions (`adopted`, `not_applied`, `unknown`) and every non-`sq_run` kind leave it null. Identify the recovery path by the code that performs it, not by a caller-supplied flag
- [x] `unrouted_outcomes(project_id) -> list[JournalEntry]`: entries with `awaits_routing = 1`, oldest `issued_at` first
- [x] Show the flag in `amoeba inspect journal` (LLD, "API Contracts"): an `awaits_routing` column in `inspection/core.py` (`journal_rows`) and the key in `--json`
- [x] Tests: a `completed` and a `failed` issuer resolution each set the flag; a recovery `not_applied` does not; a resolved `cf_write` does not; `unrouted_outcomes` returns them oldest first and only for its project; an `EXPLAIN QUERY PLAN` of its SQL names `idx_journal_awaits_routing`; the journal listing shows `true` for a flagged entry and `false` otherwise, in table and JSON output (`tests/test_cli_inspect.py` or `tests/inspection/`)
- **Success Criteria**:
  - [x] Store tests, `ruff` and `pyright` pass. Commit: `feat: mark resolved sq_run entries as awaiting routing`

### Task 2.6: `record_runner_report` takes a sequence of reviews; a decision clears the flag, with tests
**Owner**: Junior AI | **Dependencies**: 2.5 | **Effort**: 3

Per the LLD, D10 "`record_runner_report`" and D8 "Cleared by the decision". Edit `store/runner_report.py`, `store/runner_models.py`, `store/routing_decisions.py`, `tests/store/test_runner_report.py` and `tests/store/test_routing_decisions.py`.

- [x] Add `RunnerReview(verdict, detection)` (frozen) and export it from `amoeba.store`
- [x] New signature `record_runner_report(entry_id, reviews: Sequence[RunnerReview], *, outcome, result)`. `outcome` other than `completed` or `failed` raises `ValueError`. One transaction: every review's existing checks, then each verdict and ledger row in order, then the resolution, which sets `awaits_routing`
- [x] Update callers: `tests/contract/runner_tenant.py` (the stand-in Runner) and `tests/test_public_api.py`. Fix any contract-suite break in the stand-in (`runner_tenant.py`, `standin.py`), not in the contract assertions
- [x] Tests: zero reviews resolves and flags the entry; two reviews record both verdicts and ledger rows in order; a failing check on the second review writes nothing at all (first verdict absent, entry unresolved); `outcome="paused"` raises `ValueError`; `failed` resolves `failed` and still flags
- [x] `record_routing_decision` sets `awaits_routing` to null on its `journal_entry_id` inside its own transaction
- [x] Tests: after a decision, `unrouted_outcomes` no longer lists the entry; a decision that fails validation leaves the flag set (`test_routing_decisions_atomic.py` pattern)
- **Success Criteria**:
  - [x] Store tests, `uv run pytest tests/contract`, `ruff` and `pyright` pass. Commit: `feat: record every runner review part and clear the flag on decision` with `Fixes #10` in the body

### Task 2.7: `detection_key`, shared by detection, with tests
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

Per the LLD, D7 last bullet and D10 "`detection_key`"; see "Task-level additions". Edit `process/review_scan.py` and its tests.

- [x] Add `detection_key(watches, file: Path) -> tuple[str, str] | None` beside `content_digest`: the watch whose `reviews_dir` is the file's parent directory gives `(str(Path(reviews_dir) / file.name), content_digest(bytes))`; no covering watch gives `None`. Take the bytes as an argument if that keeps the file read once (ingest reads each file once, D7); state the final signature in the docstring
- [x] `examine` forms its `(path, digest)` through the same helper, so detection's key has one definition. Detection behavior is unchanged
- [x] Export it from `amoeba.process`
- [x] Tests: a file in a watched directory gets the watch-joined path and the digest; a file outside every watch gives `None`; a watch path given with a trailing separator still matches; the detection test suites (`tests/process/`, `tests/store/test_detections.py`) pass unchanged
- **Success Criteria**:
  - [x] Tests, `ruff` and `pyright` pass. Commit: `refactor: form the review detection key in one function`

### Task 2.8: Contract text for the store, read-back and evidence changes
**Owner**: Junior AI | **Dependencies**: 2.2–2.7 | **Effort**: 2

Per the LLD, D10 "Order" and "Provides to Other Slices" (Contract documents). Text only.

- [x] `docs/store-contract.md`: the `cf_write` keys, `record_runner_report`'s new signature, migration `011`, `unrouted_outcomes`, the flag set by issuer resolutions and cleared by a decision (the API Contracts table)
- [x] `docs/evidence-contract.md`: the Runner journals the run on the step node and records the verdict on the slice node with `sq_run_id` and `journal_entry_id=None` (replace the sentence "a Runner journals a review command on the node the review is of", D7); multi-part recording; verdict ids are 105's content digest
- [x] Correct the LLD (`user/slices/125-slice.run-dispatch-and-outcome-ingestion.md`) where the code contradicts it: D7's last bullet and D10's `detection_key` bullet say detection's directory source calls `detection_key`; state instead that `review_scan.examine` forms detection's key through it (the source is in `store/`, which Rule 1 bars from importing `amoeba.process`). Component Structure's `tenant.py` line names the production planners; move that entry to `factory.py` (`PRODUCTION_PLANNERS`)
- **Success Criteria**:
  - [x] Every changed statement matches the code from Tasks 2.2–2.7, and the LLD matches the task-level additions. Commit: `docs: update store, process and evidence contracts for slice 125`

---

## Section 3: Outcome document and the stub `sq`

### Task 3.1: `checkpoint`, `failure` and `reviews` on the outcome document, with tests
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 3

Per the LLD, D7 (Technical Scope), "API Contracts" (Outcome document) and "Patterns and Conventions". Edit `process/sq_outcome.py` and `tests/test_observer_sq_outcome.py`.

- [x] Capture real fixtures into a new `tests/fixtures/sq_outcomes/` with `sq runs wait --timeout 0 --json <run id>` (read-only) on local runs (`~/.config/squadron/runs/`): a completed run with a non-empty `reviews` list; a completed run whose last review has non-null `paths`; a failed run with `failure`; a paused run with `checkpoint`. Choose run ids by inspecting the output, not by name. Paused candidates are the run-state files containing `"status": "paused"`; their documents carry `checkpoint`. If no local run yields one of the four kinds, write `BLOCKED:` under this task naming the missing kind and stop. Never compose a fixture by hand. Record each file in the README with the date
- [x] `RunCheckpoint` gains every field in the LLD (all optional; `None` means unknown). Add `RunFailure` and `RunReview`. `RunOutcomeDocument` gains `checkpoint`, `failure`, `reviews`
- [x] `CheckpointKind` and `FailureKind` (`StrEnum`, values from the LLD). The model keeps raw `str | None`. Parse functions return a member, or an explicit unknown value that carries the raw text (for example `UnknownKind(raw)`); `None` stays `None`. Never map to a near match
- [x] Export the new names from `amoeba.process`
- [x] Tests: each real fixture parses with the expected field values; `paths` is a list on the split one and `None` otherwise; an unrecognized checkpoint or failure kind parses to the unknown carrying its text; a document with no `reviews` key reads `None`; 120's existing fixtures still parse; `tests/process` pruning tests pass (Rule 9 shares this model)
- **Success Criteria**:
  - [x] Tests, `ruff` and `pyright` pass. Commit: `feat: read checkpoint, failure and reviews from the run outcome document`

### Task 3.2: The stub `sq` writes review files and a `reviews` list, with tests
**Owner**: Junior AI | **Dependencies**: 3.1 | **Effort**: 3

Per the LLD, "Technology Choices". Edit `tests/sq_stub.py` and `tests/test_sq_stub_run.py`.

- [x] The stub's run mode can be configured (through its existing state/env mechanism) to write review files into the run's working directory and list them in the outcome document's `reviews`: a single review, a split review (`paths` with two part files), an entry with null `path` and `paths`, an empty list, and a listed file that is not written (missing)
- [x] Review file contents come from real fixtures in `tests/fixtures/sq_reviews/`, rewritten only in their `slice` frontmatter where a test needs a given slice (helper in `tests/review_fixtures.py` if it fits)
- [x] The stub can emit `checkpoint` and `failure` objects shaped like the Task 3.1 fixtures, and records every `sq run` argv (including `--run-id` and each `-p`) as today
- [x] Tests: each configuration produces the files and a document that `RunOutcomeDocument` parses; `paths` order is preserved; the argv log shows `-p slice=…`
- **Success Criteria**:
  - [x] Stub tests, `ruff` and `pyright` pass. Commit: `test: make the stub sq write review files and a reviews list`

---

## Section 4: Ingestion (`amoeba.runner.ingest`)

### Task 4.1: Outcome-to-block mapping, with tests
**Owner**: Junior AI | **Dependencies**: 3.1 | **Effort**: 2

Per the LLD, D6 "The block, by outcome". Create `runner/ingest/__init__.py`, `runner/ingest/outcome.py` and `tests/runner/ingest/test_outcome.py`.

- [ ] A pure function from a finished run (122's `Finished`: `RunEnded`, `RunVanished`; `LaunchFailed` stays with 122's path) to `BlockPlan(kind, context, payload) | None` and the entry outcome, following every row of the D6 table
- [ ] Define the block reasons `failed`, `orphaned`, `vanished` once here (reuse 122's `REASON_VANISHED` by moving it, not copying). `started_before_crash` is added here too, for Task 8.1
- [ ] `SQ_CHECKPOINT` blocks carry no payload; context is `paused: <kind> at <step>, run <run_id>`, with `unknown` for a null kind or step
- [ ] Squadron text copied into a block's context or payload (checkpoint kind and step, `failure.message`) is cut to 122's `STDERR_TAIL_LIMIT_BYTES` bound (LLD, Special Considerations "Security"). Reuse that constant; do not define another
- [ ] Tests (table-driven, every D6 row): completed gives no block and `completed`; paused gives `SQ_CHECKPOINT`; failed with each `FailureKind`, an unknown kind and a null failure gives `HUMAN` with `{reason: failed, run_id, failure}`; orphaned and vanished give `HUMAN` and `failed`; an oversized `failure.message` is cut to the bound
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `feat: map finished run outcomes to blocked states`

### Task 4.2: Review selection, reading, parsing and attribution, with tests
**Owner**: Junior AI | **Dependencies**: 2.7, 3.1 | **Effort**: 3

Per the LLD, D7. Create `runner/ingest/reviews.py` and `tests/runner/ingest/test_reviews.py`.

- [ ] `select_review_files(document, checkout, …) -> ReviewFiles | ReviewUnknown`. Last `reviews` entry; its `paths` in order if non-null, else its `path`; empty or absent list gives empty `ReviewFiles`. Relative paths resolve against `checkout`
- [ ] Each file is read once, whole. Parse with `parse_review_artifact`; build each verdict with `to_verdict_input` (`sq_run_id`, `journal_entry_id=None`, provenance per D7). Version label: the file's `squadronVersion`, else the captured `sq --version` label (passed in), else the explicit `unavailable` marker detection uses (import it, never retype it)
- [ ] The ledger key comes from `detection_key` (Task 2.7); `None` falls back to the resolved absolute path
- [ ] Attribution: `attribute_review(slice nodes, review.slice)` must return exactly the step's parent slice node
- [ ] `ReviewUnknown(path, reason)` for each D7 case: null `path` and `paths`; missing, unreadable or unparseable file; attribution to none, several, or another node. Any one makes the whole run unknown
- [ ] Tests: single review; split review in part order; empty list; each `ReviewUnknown` case; the version-label fallback chain; **agreement test** `test_ingest_and_detection_compute_the_same_key` (one file under a watched directory, detection's `examine` path and ingest's key are equal)
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `feat: select, parse and attribute a run's last review`

### Task 4.3: `ingest.record` replaces 122's body, with tests
**Owner**: Junior AI | **Dependencies**: 2.6, 4.1, 4.2 | **Effort**: 3

Per the LLD, D6 and D7 "`ReviewUnknown`" (block rules). Create `runner/ingest/record.py`; change `runner/finish.py` to delegate; edit `runner/factory.py` and `tests/runner/test_finish.py`; add `tests/runner/ingest/test_record.py`.

- [ ] `runner/factory.py` captures the `sq --version` label once at start (120's `version_label`) and passes it to whatever builds ingest. No per-tick capture
- [ ] Order: block (skipped if the node is already blocked), then one `record_runner_report(entry, reviews, outcome=…, result=…)`
- [ ] Result keys `run_id`, `outcome`, `status`, `outcome_document` (the polled document, verbatim), `verdict_ids` (part order, empty if nothing recorded), `review_fault` (null or the `ReviewUnknown` reason). Define them once; drop 122's `checkpoint`/`paused_at` result keys in favor of `outcome_document`
- [ ] Review unknown with no outcome block: block `HUMAN` with `{fault_kind: review_unknown, path, reason}`. With an outcome block: that block stands with `review_fault` added to its payload. Paused with review unknown: block `HUMAN`, not `SQ_CHECKPOINT`. The `reason` is cut to the same bound as Task 4.1
- [ ] Add `FaultKind.REVIEW_UNKNOWN` in `runner/faults.py`
- [ ] `finish.record` keeps the `LaunchFailed` path (122) and delegates `RunEnded`/`RunVanished` to `ingest.record`
- [ ] Tests (store-backed, files on disk): completed records on the slice node with `sq_run_id`, a `runner_issued` ledger row, entry `completed` with `verdict_ids` and `awaits_routing`; `test_split_review_records_every_part` (every part in one transaction); empty list resolves and flags; each unknown case blocks with `review_unknown`, including paused (blocked `HUMAN`); failed plus unknown keeps the failed block with `review_fault`; calling `record` twice gives one block and one verdict per part (re-entry)
- **Success Criteria**:
  - [ ] Tests, the full `tests/runner` suite, `ruff` and `pyright` pass. Commit: `feat: ingest finished runs with their reviews`

### Task 4.4: Ingestion proofs: detection skip and crash points, with tests
**Owner**: Junior AI | **Dependencies**: 3.2, 4.3 | **Effort**: 3

Per the LLD, "Testing approach", D6 ("Detection must not take that file as external either") and Success Criteria "Ingestion of a completed run", "Crash during ingestion" and "Left for routing". Edit `tests/runner/crash_entry.py`, `tests/runner/crash_harness.py`, `tests/runner/test_crash_recovery.py`; create `tests/runner/ingest/routing_support.py`.

- [ ] Detection skip (in `tests/runner/ingest/test_record.py`, or with `tests/detection_e2e_harness.py`): ingest a completed run whose review file sits in a watched reviews directory, run one detection scan, and assert no new verdict, no new ledger row, and the existing row `runner_issued`. Repeat for a paused run whose last review is the review behind its checkpoint verdict
- [ ] `routing_support.py`: one helper that records a routing decision for an entry through `store.record_routing_decision` (the stand-in for 126)
- [ ] Add `KillPoint` members: after the block and before `record_runner_report`; after ingestion and before the test router's decision
- [ ] `test_kill_between_block_and_report_finishes_once`: after restart the next tick completes the report; the node has one blocked state; each verdict is recorded once
- [ ] `test_kill_between_ingest_and_route_keeps_outcome_unrouted`: after restart `unrouted_outcomes` still lists the entry; after the helper records a decision it does not
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `test: prove detection skip and crash recovery around ingestion`

---

## Section 5: Dispatch core (`amoeba.runner.dispatch`)

All functions in this section are pure: no store, subprocess or clock.

### Task 5.1: `resolve_checkout`, with tests
**Owner**: Junior AI | **Dependencies**: 1.1 | **Effort**: 2

Per the LLD, D1. Create `runner/dispatch/__init__.py`, `runner/dispatch/checkout.py` and `tests/runner/dispatch/test_checkout.py`.

- [ ] `Checkout(path: Path, worktree_id: str | None)` and `CheckoutUnresolved(reason: str)`, frozen
- [ ] `resolve_checkout(snapshot, slice_index, *, is_dir)` over the projection `latest_cf_snapshots` returns. Inject the directory check (`is_dir`) so the function stays pure; the caller passes `Path.is_dir`
- [ ] Every D1 rule: worktrees present, exactly one containing `indexRange` with a non-empty `worktreePath`; no worktrees, `projectPath`; else `CheckoutUnresolved` naming which case
- [ ] Tests (table-driven, one row per D1 case): two worktrees and the index in the second; no worktrees; no snapshot; no range contains the index; two ranges contain it; empty `worktreePath`; path not a directory; range bounds inclusive at both ends. Build rows in the projection shape `tests/store/test_cf_snapshots.py` uses
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `feat: resolve a slice's checkout from CF worktree ranges`

### Task 5.2: `DispatchState` and `dispatch_state`, with tests
**Owner**: Junior AI | **Dependencies**: 2.5 | **Effort**: 2

Per the LLD, D3. Create `runner/dispatch/state.py` and `tests/runner/dispatch/test_state.py`.

- [ ] `DispatchState(StrEnum)`: `in_flight`, `awaiting_routing`, `reissue`, `pointed`, `needs_pointer`
- [ ] `dispatch_state(entries, *, pointer_confirmed: bool) -> DispatchState`. `entries` are the step's own, oldest first. `pointer_confirmed` is this tick's read-back answer (Task 7.1); the journal alone saying `POINTED` with `pointer_confirmed=False` gives `NEEDS_POINTER`
- [ ] Rows evaluated in the D3 table's order: any unresolved entry; latest `sq_run` with `awaits_routing`; latest entry an `sq_run` resolved `not_applied` by recovery; latest entry a `cf_write` resolved `completed` or `adopted`; else `NEEDS_POINTER`
- [ ] Tests (every row, plus): no entries; failed pointer write; routed `sq_run` (flag cleared); recovery `unknown` and `adopted` `sq_run`; a completed `cf_write` followed by a routed `sq_run` is `NEEDS_POINTER`; `pointer_confirmed=False` on a completed `cf_write`
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `feat: derive a step's dispatch state from its journal`

### Task 5.3: `dispatch_params`; actions and view gain the dispatch facts, with tests
**Owner**: Junior AI | **Dependencies**: 5.1, 5.2 | **Effort**: 2

Per the LLD, D5, "Runner, internal" and Component Structure (`decide.py`). Edit `runner/decide.py` and `tests/runner/test_decide.py`; put `dispatch_params` in `runner/dispatch/params.py` with `tests/runner/dispatch/test_params.py`.

- [ ] Define `PARAM_SLICE = "slice"`, `PARAM_MERGE = "merge"`, `MERGE_DISABLED = "false"` once, beside `dispatch_params(step, slice_index) -> Mapping[str, str]`. The pipeline comes from 123's `STEP_MAP`. Every pipeline step gets `slice`; `implementation` (`P6`) also gets `merge=false`
- [ ] Tests: `slice_design`, `tasks`, `implementation` give the right pipeline and params; a non-pipeline step raises `ValueError`; **import test** `test_merge_param_is_built_only_by_dispatch_params` scans `src/amoeba/runner` (use `tests/ast_strings.py`) and finds the merge key literal only in `params.py`

- [ ] Add `WriteSlicePointer(node_id, cf_project_id, slice_index, checkout: Checkout)`. `LaunchRun` gains `run_id: str | None = None` and `reissue_of: str | None = None`. `Action = LaunchRun | BlockHumanStep | WriteSlicePointer`. Update the "125 adds" comment
- [ ] `ProjectView` gains, per current pipeline step, its dispatch facts (state, resolved checkout or `CheckoutUnresolved`, slice index, CF project id, the latest entry needed for a reissue, sort key `(initiative index, slice index, step rank)`) and the project's held-checkout set. Use one frozen dataclass for the per-step facts, keyed by node id
- [ ] Existing view builders and tests construct the new fields (empty by default where a test does not dispatch). The guard in `decide()` covers `WriteSlicePointer` unchanged
- [ ] Tests: `decide()` refuses a `WriteSlicePointer` for a non-current node and two actions for one node
- **Success Criteria**:
  - [ ] `tests/runner`, `ruff` and `pyright` pass. Commit: `feat: add dispatch params, the pointer-write action and dispatch facts`

### Task 5.4: Held checkouts and `DispatchPlanner`, with tests
**Owner**: Junior AI | **Dependencies**: 5.3 | **Effort**: 3

Per the LLD, D4 and D3 ("Planner does" column). Create `runner/dispatch/planner.py` (put the hold computation in `runner/dispatch/hold.py` if `planner.py` nears 300 lines), `tests/runner/dispatch/test_hold.py` and `tests/runner/dispatch/test_planner.py`.

- [ ] `held_checkouts(...) -> frozenset[Path]`, pure, across the whole project: unresolved `sq_run` entries' `checkout`; a not-done node whose latest `sq_run` has recorded outcome `paused` (read from the result's `outcome`, never the block kind); a current step that is `POINTED` or in flight on a `cf_write`
- [ ] `DispatchPlanner.plan(view)`: for each current pipeline step with a resolved checkout not held, `POINTED` gives `LaunchRun(pipeline, dispatch_params(...), checkout.path)`; `REISSUE` gives `LaunchRun(..., run_id=<old>, reissue_of=<old entry id>)` with the old entry's pipeline, params and checkout; `NEEDS_POINTER` gives `WriteSlicePointer`. `IN_FLIGHT`, `AWAITING_ROUTING` and `CheckoutUnresolved` give nothing (Task 7.2 blocks the unresolved case)
- [ ] At most one action per checkout per tick. Within a free checkout: `POINTED` and `REISSUE` first, then `(initiative index, slice index, step rank)`
- [ ] Tests (table-driven over every D3 row and D4 rule): second slice in a held checkout gets nothing while the first is `POINTED`, in flight, or paused; paused-with-unknown-review (blocked `HUMAN`) still holds; a later `sq_run` on the paused node releases; a slice in another worktree is planned meanwhile; ordering picks the `POINTED` step over an earlier `NEEDS_POINTER` one; a held or excluded slice's in-flight run still holds; `merge=false` on every `P6`
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `feat: add DispatchPlanner with one pipeline per checkout`

---

## Section 6: The stub `cf` and the pointer write

### Task 6.1: Stub `cf` routes `set slice` and `get --json` by working directory, with tests
**Owner**: Junior AI | **Dependencies**: 2.3 | **Effort**: 3

Per the LLD, Interfaces Required (Context Forge) and "Technology Choices". Edit `tests/cf_stub.py`, `tests/cf_fixture.py` and `tests/runner/test_cf_stub_plan.py` (or a new `tests/test_cf_stub_pointer.py`).

- [ ] The stub keeps a `projects.json`-shaped state file (fixture-shaped, with `worktrees`, `indexRange`, `worktreePath`, `activeSlice`, `updatedAt`)
- [ ] `cf set -p <id> slice <index>`: chooses the worktree whose `worktreePath` is the longest prefix of the process cwd, else the project level; stores `NNN-slice.{name}` from a configured slice-plan entry; bumps `updatedAt`; an index with no entry exits non-zero with `ARTIFACT_NOT_FOUND` on stderr; an unchanged value writes nothing
- [ ] `cf get --json -p <id>`: emits the shape of `tests/fixtures/cf/cf_get_worktree.json` (Task 2.3) for the cwd's worktree, or the project-level shape of `cf_get_amoeba.json`
- [ ] Test knobs: make `set` exit non-zero, make `get` fail or time out, make `get` omit `fileSlice`, make `get` report a different `projectPath` or worktree id
- [ ] Tests: two worktrees, a write from each cwd lands in its own worktree; a cwd outside every worktree lands at project level; output parses through the read-back observer
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `test: route stub cf pointer writes by working directory`

### Task 6.2: `issue_pointer_write` and `read_back` answers, with tests
**Owner**: Junior AI | **Dependencies**: 2.3, 5.3, 6.1 | **Effort**: 2

Per the LLD, D2 and D1 "The read-back confirms it". Create `runner/dispatch/pointer.py` and `tests/runner/dispatch/test_pointer.py`.

- [ ] `issue_pointer_write(store, action, budget, ...)`: journal a `cf_write` with `project`, `checkout` (absolute), `expected={}`, `expected_slice_index`; run `cf set -p <id> slice <index>` with `cwd=checkout` through `TickBudget` and `tick_call_timeout_seconds` (122's injected runner and `runner/cf_call.py`); then `read_back`. It returns the `cf set` result and the read-back answer; it writes nothing else (Task 6.3 applies them)
- [ ] `read_back(store, entry, expected_checkout, budget, ...)` calls the observer function from Task 2.3, then checks `project_path == checkout.path` and `worktree_id` equal (absent when no worktrees). Returns an answer: `Confirmed(stem)`, `Mismatch(reason)`, `Unknown(reason)`, or `ReadFailed(reason)`
- [ ] Tests (stub `cf`): each answer from the matching stub knob (Task 6.1); the journaled parameters; every subprocess goes through `TickBudget` (122's injected-runner assertion pattern)
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `feat: write and read back the CF slice pointer in the checkout`

### Task 6.3: Apply pointer-write outcomes, with tests
**Owner**: Junior AI | **Dependencies**: 6.2 | **Effort**: 2

Per the LLD, D2 outcome bullets. Edit `runner/dispatch/pointer.py`; extend `tests/runner/dispatch/test_pointer.py`.

- [ ] Add `FaultKind.POINTER_WRITE_FAILED`
- [ ] `Confirmed` resolves `completed` with `{cf_updated_at, file_slice, worktree_id, project_path}` and sets the slice node's `cf.slice_name` via `update_cf_reference` when it differs
- [ ] `Mismatch` or another index blocks the step `HUMAN` with `pointer_write_failed` and resolves `failed`. `Unknown` goes through `journal_escalate` at once. `ReadFailed` leaves the entry unresolved
- [ ] `cf set` non-zero resolves `failed` and blocks with the stderr head bounded by 122's tail bound. A `cf set` timeout is a cut-off: entry unresolved, read back next tick
- [ ] Tests (store plus stub `cf`): one per outcome above; `slice_name` set from the stem
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `feat: resolve or block on the pointer read-back`

---

## Section 7: Observe, view and launch wiring

`runner/tick.py` is near 255 lines. Put new stage bodies in `runner/dispatch/` (for example `dispatch/stage.py`) and keep `tick.py` to calls, near 300 lines.

### Task 7.1: Observe reads back pointers, with tests
**Owner**: Junior AI | **Dependencies**: 5.2, 6.3 | **Effort**: 3

Per the LLD, Data Flow (observe), D2 "A read that fails" and D3 "CF still points". Edit the tick's observe stage; add `tests/runner/dispatch/test_observe_pointer.py`.

- [ ] Each unresolved `cf_write` entry gets `read_back` under `TickBudget`, handled as in Task 6.3. A read still failing once `launch_grace_seconds` has passed since `issued_at` goes through `journal_escalate` with the last failure as its reason
- [ ] Each current step whose journal says `POINTED` gets one read-back; the answer becomes `pointer_confirmed` for Task 5.2. Anything but a confirmed index is `False`
- [ ] Observe scope stays 124's predicate (`drives_anything()` or a run in flight)
- [ ] Tests: a cut-off read-back completes on the next tick; a read-back with an absent field escalates at once; a read that keeps failing escalates once the grace has passed and not before; a `POINTED` step whose pointer was overwritten reads `pointer_confirmed=False`
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `feat: read back CF pointers in the observe stage`

### Task 7.2: Build the dispatch facts and block unresolved checkouts, with tests
**Owner**: Junior AI | **Dependencies**: 7.1 | **Effort**: 3

Per the LLD, D1 (`CheckoutUnresolved` blocks) and State Management (per-tick, in memory). Edit the tick's view building.

- [ ] For each current pipeline step: read its entries (`journal_entries(project, node_id=step)`), its slice's latest observed snapshot (`latest_cf_snapshots`), resolve the checkout, compute `dispatch_state`, and compute the project's held checkouts. Built each tick, never cached
- [ ] Add `FaultKind.CHECKOUT_UNRESOLVED`. `CheckoutUnresolved` blocks the step on `HUMAN` with `{fault_kind: checkout_unresolved, index, reason}` (122's node block path) and the step gets no action this tick
- [ ] Tests (tick-level): no range holding the index, two ranges holding it, and a missing path each block with `checkout_unresolved`
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `feat: build per-step dispatch facts each tick`

### Task 7.3: Act performs both actions; two-tick dispatch, with tests
**Owner**: Junior AI | **Dependencies**: 5.4, 7.2 | **Effort**: 3

Per the LLD, Data Flow ("One step, end to end"). Edit `_act` in `runner/tick.py` to dispatch `WriteSlicePointer` to `issue_pointer_write` and `LaunchRun` to 122's launch (reissue arrives in Section 8). Add `tests/runner/dispatch/test_tick_dispatch.py`. Tick tests pass `planners=(HumanStepPlanner(), DispatchPlanner())` explicitly; production wiring is Task 10.1.

- [ ] `LaunchRun` journals an `sq_run` with `checkout` and the `dispatch_params`, and launches with `cwd=checkout` (122)
- [ ] A `LaunchRun` with `reissue_of` launches nothing yet: it blocks the step on `HUMAN` naming the `not_applied` entry (the overrun fallback). Task 8.1 replaces this, so a new run is never launched over one that may have started
- [ ] Tests: `test_driven_slice_design_writes_pointer_then_launches_p4` (tick 1 `cf_write` with `checkout` and `expected_slice_index`; tick 2 `sq_run` of `P4` with `-p slice=<index>`, in that checkout); held or not driven issues neither; `P6` carries `-p merge=false`; two worktrees, the write lands in the right one and `slice_name` is set; already-pointed checkout (stub `set` writes nothing, no snapshot follows) still launches on the next tick; `cf set` non-zero, another index, path mismatch and worktree mismatch each block `pointer_write_failed` and resolve `failed`
- **Success Criteria**:
  - [ ] Tests, `tests/runner`, `ruff` and `pyright` pass. Commit: `feat: dispatch a driven step in two ticks`

### Task 7.4: Checkout concurrency and ingestion at tick level, with tests
**Owner**: Junior AI | **Dependencies**: 3.2, 4.4, 7.3 | **Effort**: 3

Per the LLD, Success Criteria "Checkout concurrency", "Each non-completed outcome", "Left for routing". Add `tests/runner/dispatch/test_tick_concurrency.py` and `tests/runner/ingest/test_tick_ingest.py`.

- [ ] `test_second_slice_waits_for_checkout`: no pointer write while the first is `POINTED`, in flight or paused; dispatched on the first tick after the first run completes or fails; a slice in another worktree is dispatched meanwhile
- [ ] A paused run with an unknown review (blocked `HUMAN`) still holds its checkout
- [ ] A `POINTED` step overwritten while not current writes its pointer again before launching
- [ ] Ingestion end to end with the stub `sq`, three scenarios only (Task 4.1 tests every outcome as a table and 4.3 the store path): a paused run (`SQ_CHECKPOINT`, checkpoint in the result), a failed run, a completed run with an unknown review. After a completed or failed ingestion `unrouted_outcomes` lists the entry and the step gets no further action; a routing decision (Task 4.4 helper) removes it
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `test: prove checkout concurrency and tick-level ingestion`

---

## Section 8: Reissue a `not_applied` launch (D9, issue #9)

### Task 8.1: The reissue path, with tests
**Owner**: Junior AI | **Dependencies**: 7.3 | **Effort**: 3

Per the LLD, D9. Edit `runner/launch.py` (keep it near 300 lines; move the reissue into `runner/dispatch/reissue.py` if needed) and `_act`; add `tests/runner/dispatch/test_reissue.py`.

- [ ] For `LaunchRun` with `reissue_of`: (1) check the old entry's `<entry_id>.stderr.log` with 122's `log_paths` and `stderr_confirms` (64 KiB head); an exact `run_id=<id>` line blocks `HUMAN` with `{reason: started_before_crash, run_id}`; an existing unreadable log blocks `HUMAN` naming the error; no log or no line continues. (2) Journal a new `sq_run` with the same `pipeline`, `params`, `checkout`, `run_id`, plus `reissue_of`. (3) Poll once; a found run is adopted (entry confirmed, nothing launched). (4) Not found: 122's `launch()`
- [ ] Define the `reissue_of` parameter key once
- [ ] The pointer is not re-written
- [ ] Tests: `test_reissue_with_run_id_line_escalates` (nothing launched); unreadable log blocks; no log relaunches once under the same run id in a new entry with `reissue_of`, and the stub `sq` saw one `sq run` for that id; a state appearing before the relaunch is adopted without a launch; a crash-proof variant (`tests/runner/test_crash_recovery.py`): kill before launch, recovery resolves `not_applied`, restart relaunches once
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `feat: reissue a not_applied launch under its own run id` with `Fixes #9` in the body

---

## Section 9: Pointer moved during a run (D11)

### Task 9.1: `pointer_moved`, with tests
**Owner**: Junior AI | **Dependencies**: 2.1, 2.3, 5.1, 6.3 | **Effort**: 2

Per the LLD, D11. Inputs: the pointer write's `worktree_id` result key (defined in 2.3, written in 6.3) and the time the write resolved (the journal entry's `resolved_at`). Create `runner/dispatch/pointer_watch.py` and `tests/runner/dispatch/test_pointer_watch.py`.

- [ ] `pointer_moved(in_flight, snapshots) -> list[MovedPointer]`, pure. For each in-flight run: its pointer write's `worktree_id` (or project level), the latest snapshot recorded after that write resolved, and its `activeSlice` (or project `fileSlice`) parsed by `parse_slice_stem`. A different index gives `MovedPointer(node_id, run_id, worktree_id, observed)`
- [ ] Tests: same index, no move; different index, moved; snapshot recorded before the write resolved is ignored; no later snapshot, no move; project with no worktrees uses `fileSlice`; unparseable value is not a move
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `feat: detect a CF pointer moved away from a running step`

### Task 9.2: Raise and close `pointer_moved` at project scope, with tests
**Owner**: Junior AI | **Dependencies**: 7.1, 9.1 | **Effort**: 2

Per the LLD, D11 bullets on escalation. Wire into observe; add `FaultKind.POINTER_MOVED`; add `tests/runner/dispatch/test_tick_pointer_moved.py`.

- [ ] A non-empty result raises one project-scoped `pointer_moved` escalation whose payload lists every moved run. It counts as a recurrence while the condition holds and closes on the first complete tick without it (122's closure rule, 123's recurrence pattern)
- [ ] The run is still observed and ingested
- [ ] Tests: a stub snapshot moving the run's worktree raises one escalation; it stays open while the snapshot holds; it closes when the pointer returns or the run ends; the run is ingested
- **Success Criteria**:
  - [ ] Tests, `ruff` and `pyright` pass. Commit: `feat: escalate a moved pointer while a run is in flight`

---

## Section 10: Production wiring, contract text, final validation

### Task 10.1: `DispatchPlanner` in production, with tests
**Owner**: Junior AI | **Dependencies**: 7.4, 8.1, 9.2 | **Effort**: 2

- [ ] `PRODUCTION_PLANNERS = (HumanStepPlanner(), DispatchPlanner())` in `runner/factory.py`
- [ ] Update `tests/runner/test_factory.py` to assert the tuple and order
- [ ] Run 122's crash proof, 123's reconcile tests and 124's guard tests (`tests/runner/test_crash_recovery.py`, `tests/runner/lifecycle`, `tests/runner/intent`, `tests/runner/test_tick_governance.py`); fix breaks in test setup only where a test now needs a snapshot or stub `cf` state
- [ ] `tests/runner/test_budget_coverage.py` covers every new `cf` and `sq` call in the dispatch path
- **Success Criteria**:
  - [ ] `tests/runner`, `ruff` and `pyright` pass. Commit: `feat: put DispatchPlanner in the production planners`

### Task 10.2: Remaining contract text and CHANGELOG
**Owner**: Junior AI | **Dependencies**: 10.1 | **Effort**: 2

Per the LLD, "Provides to Other Slices" (Contract documents) and Implementation Notes step 7.

- [ ] `docs/process-contract.md` (the only task that edits it): the read-back's working directory and index check, and `Unknown` for an empty comparison (Task 2.3); the dispatch and ingest stages, the two-tick dispatch, the checkout hold, no `started` status
- [ ] `docs/context-forge-contract.md`: a write lands where its working directory says; the pointer-move rule (D11)
- [ ] `docs/substrate-guide.md`: the 120 row; issues #9 and #10 closed
- [ ] `CHANGELOG.md`: an entry under the unreleased section (patch-level per the Release Versioning rule)
- **Success Criteria**:
  - [ ] Every statement matches the code. Commit: `docs: add dispatch and ingestion contract text and changelog`

### Task 10.3: Full validation and the live walkthrough
**Owner**: Junior AI | **Dependencies**: 10.2 | **Effort**: 3

Per the LLD, Verification Walkthrough. Live runs are pre-authorized.

- [ ] Run walkthrough steps 1 and 2 once each. All pass
- [ ] Run step 3 on a scratch copy exactly as written (one real `P4` run), including its two fallbacks: `cf init` is interactive if the copy has no CF config (use the same template as this repository), and if the copy's slice 126 is already designed, drive the first slice whose `slice_design` step is `runnable` instead. Record the observed results under this task: the `cf_write` and `sq_run` entries, `cf status` `activeSlice.index`, the `slice_name`, and the final entry state (`awaits_routing`, or the checkpoint block). Then submit the pause intent, confirm no further `cf_write`, and stop the process
- [ ] If step 3 fails, record the actual error text under this task and fix the cause before checking it off
- **Success Criteria**:
  - [ ] `uv run pytest -q`, `ruff check`, `ruff format --check` and `pyright` are clean; the walkthrough results are recorded. Commit: `test: record the slice 125 walkthrough`
