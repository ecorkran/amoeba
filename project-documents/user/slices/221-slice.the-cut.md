---
docType: slice-design
slice: the-cut
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 220-slice.code-audit
interfaces:
- 222-slice.store-config-and-set-up
- 223-slice.pause-handling
dateCreated: 20261107
dateUpdated: 20261108
status: not_started
---

# Slice Design: The Cut

## Overview

Slice 220's audit (`user/analysis/220-analysis.code-audit.md`) gives every unit of `src/amoeba`, `tests`, `scripts` and `docs` a verdict. This slice carries them out. It deletes every `delete` and `squadron` unit. It moves the kept answering pieces and upstream readers into a small library that depends on nothing deleted. It rewrites the README.

Afterward Amoeba is a library with no store, no tick, no resident process and no command. Slices 222 to 224 build on it.

## Value

Architectural. About 34k lines of source and 69k of tests come down to what the scenarios use, so 222 to 224 have nothing to work around.

## Scope

**Included:** the deletions, the moves into the D3 layout, the severs (D2), test rework (D8), packaging (D7) and the README (D9).

**Excluded:**

- Deciding verdicts. The audit decides; a wrong verdict is corrected in the audit (D1).
- The new store, config file, store-location variable and `set_up` (222). Launch, wait, resume and the question record (223). `status` and `decisions` (224).
- Editing old slice designs, task files, architecture documents or slice plans.
- Deleting branches, or merging anything from the slice 182 branch. Its take and rewrite groups stay there for 223.

## Dependencies

**Slice 220 complete.** 221 cannot start without the audit. It uses these sections:

- **Verdicts:** the `delete` and `squadron` rows are the delete list. The `keep` and `rework` rows are the kept list; a `rework` reason says what changes. A file's verdict is that of the most specific row covering it.
- **Dependencies of kept code:** each entry names a replacement. 221 carries out "value passed in" and "dropped". An entry whose replacement is the new store (222) or an operation (223, 224) means the kept code's use goes away now and the later slice builds the replacement (D2).
- **Live tests:** `stays`, `waits on 223` (with its scenario A claim) or `delete` (D8).
- **Move to Squadron:** the issues are already filed, so nothing is ported here.
- **Differences from the architecture:** where a D2 deletion differs from the architecture's "kept and reworked", with the reason.

The live tier (`tests/live/answering`) needs `sq` and model credentials, as today.

## Architecture

After the cut `src/amoeba` holds two packages: `answering/` (the library) and `upstream/` (readers of other tools' state).

```
amoeba.answering  ──►  amoeba.upstream  ──►  stdlib, pydantic, pyyaml
```

`amoeba.upstream` imports nothing from `amoeba.answering`.

The library's flow is slices 143 and 144's, minus the store reads. The caller passes the question, slice reference, PM's earlier answers and `AnswererSettings`. `sources` assembles passages; `inputs` writes `question.md` and `passages.md` to a scratch directory for `answering.yaml`. (223 launches the run and waits.) `artifacts` reads the replies, `decide` returns a confirmed answer or a decline with a `DeclineReason`, and `gate` screens the answer and composes the resume instructions.

The slice adds no state. The old store, schema, migrations and per-project store files go. Nobody has run Amoeba, so nothing is migrated.

## Technical Decisions

### D1 — The audit is the delete list
221 decides nothing new. If a verdict proves wrong during the cut (typically a kept module needs something marked `delete` and no "value passed in" or "dropped" replacement works), the implementer changes its Verdicts row and its Dependencies of kept code entry in the same commit as the code, with a one-line reason, and notes it in the task file. The audit stays the record 222 to 224 read.

### D2 — Sever, don't rebuild
A `rework` unit is changed only as far as needed to cut it off from deleted code. Three moves are allowed:

- **Parameter:** a value read from deleted state is passed in by the caller (e.g. `assemble_sources` takes a slice reference and a tuple of `PmAnswer` instead of a `Store` and a `Node`).
- **Move:** a small helper taken from a deleted module moves next to its only kept user, or to the lower layer (`upstream` before `answering`) if two use it.
- **Drop:** a use with no scenario behind it goes, with any field only it read.

A `rework` unit that only works with a later replacement (question record, `sq` launch, store submit) is deleted, not stubbed. Under D1 its row becomes `delete`, and Differences from the architecture records why. Predicted: `answering/launch.py`, `stage.py`, `settle.py`, the store-writing half of `finish.py`, and `program/members.py`. A stub would be dead code that 222 or 223 must fit around.

### D3 — Layout
- The answering library moves from `amoeba/runner/answering/` to `amoeba/answering/`. Nothing else in `runner/` is kept except the survivors listed under Audit items (audit wins, D1), which go to `upstream/`.
- Readers of other tools' state live under `amoeba/upstream/`: Context Forge (`plan.py`, reworked, plus `cf_call.py` as `context_forge/cli_call.py`; the audit deletes the other existing Context Forge files and the review parsers, so the earlier "the upstream readers stay" was wrong, audit wins, D1), Squadron run output (`process/sq_outcome.py` as `squadron/run_outcome.py`, with the `observed.py` values `decide` uses) and the other `sq` and `cf` survivors in Audit items, and git (`git_read.py`).
- Files move with `git mv`, so history follows them.
- Imports name the defining module. `__init__` files re-export nothing. The audit deletes `upstream/context_forge/__init__.py`, so its existing exports go too (audit wins, D1).

### D4 — Value types leave the old store
Each value type the kept code still uses from `amoeba.store` (`DeclineReason`, `GateRefusal`, `AnsweringEvidence`, `PassageRef`, `AnsweredBy`, `GLOB_WILDCARD`, the parameter-name constants) moves unchanged to `amoeba/answering/values.py`. `CFSnapshot` goes, not moves: only `upstream/context_forge/checkout.py` and the snapshot tables used it, and the audit deletes both (audit wins, D1). Types only deleted code used (`QuestionRecord`, `QuestionState`, `BlockedState`, `JournalEntry`) go. The vocabulary of answers belongs to answering, so 222's store imports it from here. Record-only types, such as question states, belong to 222's store and never move into `answering`.

### D5 — Answerer settings
`AnswererSettings` moves from `runner/project_config.py` to `answering/settings.py`, keeping its no-defaults rule. `max_concurrent_runs` is dropped, as the architecture removes that limit. The rest of `project_config.py` goes. 222 adds the loader and decides where `rules_paths` and the authorize list come from.

### D6 — Import boundaries
`tests/test_import_boundaries.py` is rewritten to enforce one rule: `amoeba.upstream` imports nothing from `amoeba.answering`. Its rules about deleted packages go. No separate check for imports of deleted code is needed: any such import fails pyright and the test suite.

### D7 — Packaging
- Remove the `[project.scripts] amoeba` entry. The first new command comes in 222; a placeholder would be a silent fallback.
- Remove `starlette`, `uvicorn` and dev `httpx2` if nothing kept uses them. Regenerate `uv.lock`.
- Wheel `artifacts`: remove the schema globs and `slice_writing.yaml`; point at `src/amoeba/answering/answering.yaml`. `test_wheel_contents.py` moves with the library and checks the new path.
- pytest `addopts`: remove `--ignore=tests/load`; keep `--ignore=tests/live`.

### D8 — Tests
- A test of deleted code goes with it. A shared fixture or harness goes when its last user does.
- A kept test is `rework` only if its claim holds without nodes, journal entries, blocked states or a tick; it then builds its inputs directly. Otherwise it is deleted and 223 or 224 writes the replacement. A test whose fixture carries old-shape fields (`node_id`, journal ids) is reworked or deleted, never left passing.
- Kept tests move with their code: `tests/runner/answering/` to `tests/answering/`, moved upstream modules' tests to `tests/upstream/`.
- Live answering tests follow the audit's Live tests section. A `stays` file gets its imports updated and must pass. A `waits on 223` file (expected: `test_answering_run.py`, `stage_harness.py`) imports deleted code, so it is deleted now. Before deleting, its Live tests entry must name the scenario A claim and the restore commit (the `main` commit the slice branch forks from); if either is missing, it is added in the same commit. 223 restores each claim.
- `tests/load/` goes with the inbox, removing the failing test in `amoeba#32`.

### D9 — README and docs
The README drops the hero image and old pitch and says briefly: what Amoeba is (a tool agents and pipelines call to answer a paused run's first-level questions and keep the record, across a program of repos; no process of its own; optional for Squadron), what exists now (the library, no command), where the design lives (concept, `220-arch.program-tool.md`, slice plan), and how to run the checks, including the live tier's `AMOEBA_LIVE_*` variables. It claims nothing the code does not back. The `assets/` image goes if unused. `pyproject.toml`'s `description` matches the README's first line. `docs/` and `scripts/` follow the audit (the walkthrough script and doc are expected to go, since they drive the stage through the store).

### Audit items (220 code audit)

The audit's "Differences from the architecture" and "Ordering constraints for 221" raise items that land here. Where they contradict the decisions above, the audit wins (D1); D3, D4 and the Migration Plan table are amended. Already settled above: the live-test `stays` and `waits on 223` handling (D8) and the unused server dependencies, schema artifacts and slice-writing artifact (D7). The rest:

- **`upstream/` is mostly delete.** Only `context_forge/plan.py` (`parse_initiatives`, `parse_slice_list`, `CFInitiative`, `CFSliceList`, `CFErrorDocument`) is kept, reworked: drop the plan-status and `reported_complete` helpers. `context_forge/{checkout, projects_file, diff, slice_stem, __init__}.py` and `squadron/review*.py` are deleted.
- **One home for the surviving `sq` and `cf` helpers (an audit gap; 221 decides).** They go under `upstream/`, the lower layer, so `answering` and 223 import them and `upstream` imports nothing from `answering`. Filenames below are the new names; contents move unchanged except the drops named.
  - `squadron/run_outcome.py`: `process/sq_outcome.py` including `SQ_EXECUTABLE` (drop `RunReview` and `reviews`), and the `observed.py` values `RunEnded`, `RunVanished`, `LaunchFailed`, `ResumeFailed` and `Finished` as plain values (`ObservedRun`, `Observed`, `TickResult` go).
  - `squadron/faults.py`: `LaunchFailure` and `ResumeFailure` (the rest of `faults.py` goes).
  - `squadron/launch.py`: the kept half of `runner/launch.py` (`mint_run_id`, `SQUADRON_RUN_ID_PATTERN`, `build_argv`, `param_problem`, `spawn`, `LaunchLogs`, `ChildHandle`, `stderr_confirms`, `stderr_tail`, `LaunchError`, `PopenFactory`, `STDERR_TAIL_LIMIT_BYTES`). `launch(entry, ...)`, `text_parameter`, `PARAM_*`, `LaunchTracker`, `TrackedLaunch` and `LAUNCH_LOGS_DIRNAME` go.
  - `squadron/resume_argv.py` (`resolutions/argv.py`; only its `SQ_RUN_COMMAND` import changes) and `squadron/resume_confirm.py` (`ResumedFrom`, `has_left`, `is_at`, `resume_progress`; `resumed_from_entry` and `STOPPED_OUTCOMES` go).
  - `context_forge/target_read.py`: `read_config` and `read_target` (from `dispatch/checkout_reads.py`) with `cf_argv`, `config_get_command` and `CF_KEY_INTEGRATION_BRANCH` (from `lifecycle/plan_read.py`); the budget parameter goes.
  - `bounded_text.py`: `cut_to_bound` (from `ingest/outcome.py`; `decide` and `launch` both use it).
- **Names the live tier needs.** The kept live files import these, so they keep their names and signatures and only their module paths change: `SQ_EXECUTABLE`, `RunOutcome`, `RunOutcomeDocument`, `PollFailure`, `RunPoll`, `poll_run`, `QUESTION_TAIL_CHARS`, `mint_run_id`, `prepare_scratch(directory, question, passages_markdown, max_cost_usd)`, `OUTPUT_HEAD_CHARS` (in `cli_call`). Do not delete a unit whose name is on this list under D2.
- **Relocate before the home file goes.** Kept code imports these from modules that are deleted, so each moves first: `cut_to_bound`, `STDERR_TAIL_LIMIT_BYTES`, `LaunchFailure`, `ResumeFailure`, the `Finished` values, `SQ_EXECUTABLE`, and the `read_config`, `read_target` and `cf_argv` pieces, all to the homes above. `validate_repo_relative_path` (in `store/paths.py`, used by `AnswererSettings`'s `RulesPath`, and imported by 222) moves with `AnswererSettings` to `answering/settings.py`. `QuestionInvariantError` (in `settle.py`) moves next to its kept importer; if the only importer is a unit deleted under D2, it goes. `BEGIN_IMMEDIATE` (`sql_inbox.py`) and `decode_mapping` and `decode_timestamp` (`mapping_journal.py`) have no kept user because the whole store goes, so nothing moves; 222 creates them in its own `store/sql.py` and `row_values.py`.
- **`DEFAULT_TARGET_BRANCH = "main"`** (in `checkout_reads.py`) is a magic default the project rules forbid. 221 adds no behavior, so it moves unchanged with `read_target`, defined once. An empty `git.integration_branch` means `main` in Context Forge itself, so it is not removed: 223 (task 4.6) keeps it as the single named constant, with tests.
- **Test helpers split before their owners are deleted.** `tests/runner/observe_support.py`: keep the generic fakes (`Clock`, `Host`, `FakeCf`), drop `TickBudget`, `RunObserver`, `LaunchTracker` and journal types. `tests/conftest.py`: drop the fixtures importing the inbox, serve and store rigs; only `reap_orphans` (the session-start orphan reaping) remains once the store is gone. `tests/sq_stub_scripts.py`: drop the review scripts (they import `review_fixtures`), `runs prune` and any `--timeout 0` assumption. `tests/runner/answering/sources_repo.py`: drop its `runner.budget` import. `test_question_tails_fixture.py` reads `tests/live/answering/fixtures/`, which stays.
- **`store_path` and `test_store_safety.py`.** The guard stays, but it builds its forbidden names from `amoeba.store.paths`, which goes. Replace that import with the same names as string literals (`store_dir`, `store_path`, `DEFAULT_STORE_DIR`, `DEFAULT_SQ_RUNS_DIR`, `DEFAULT_CF_DATA_DIR`), so the guard covers 222's accessors of those names.
- **Live files.** `tests/live/answering/test_sdk_refusal.py` is deleted (Squadron's behavior, not an Amoeba claim) and `SDK_MODEL_VARIABLE` is removed from `tests/live_settings.py`; the README names no `AMOEBA_LIVE_SDK_MODEL`. The two `waits on 223` files restore from the commit in the audit's Live tests table, and a restore brings back only those two files: `launch_rig.py`, `question_harness.py` and the old `observe_support.py` are gone, so 223 rewrites its helpers using the restored files as a template.
- **CI.** `.github/workflows/ci.yml` loses its "Load tests" step and the header comments that describe a separate load tier; the default suite step stays.

## Migration Plan

**What moves** (expected; the audit decides):

| Source | Destination |
|---|---|
| `runner/answering/{answering.yaml, pipeline_file, inputs, passages, source_reads, sources, artifacts, decide, gate}` | `answering/` |
| `runner/pipeline_resource.py` | `answering/pipeline_resource.py` |
| `AnswererSettings` from `runner/project_config.py` | `answering/settings.py` |
| Value types from `store/` | `answering/values.py` (`CFSnapshot` is dropped) |
| `process/sq_outcome.py`, run values from `runner/observed.py` | `upstream/squadron/run_outcome.py` |
| `runner/git_read.py` (`budget.py` is `delete` in the audit) | `upstream/git_read.py` |
| `runner/cf_call.py` | `upstream/context_forge/cli_call.py` |
| Other `sq` and `cf` survivors (`launch.py`, `resolutions/{argv,confirm}.py`, `faults.py`, `read_target`, `cut_to_bound`) | `upstream/`, per Audit items |

Paths are under `src/amoeba/`. No compatibility re-exports are left at old paths.

**Steps.** Each ends with format, lint, pyright and the default suite passing, and a commit marker.

1. **Leaf deletions.** Delete units no kept unit depends on: `serve/`, `inbox/`, `feed/`, `cli/`, `inspection/`, `runner/request_run/`, `tests/load/`, the demo scripts, and their tests and docs. Old code that imports one of these only loses those imports and uses. Also: the console entry point, `slice_writing.yaml` and `--ignore=tests/load`.
2. **Move, sever and delete.** Create the D3 layout, move the kept modules and D4 types, apply the D2 severs, and delete the remaining `delete` and `squadron` rows with their tests (predicted: the rest of `runner/`, `process/`, `store/`, `program/` and the upstream review parsers). Work every Dependencies of kept code entry, since non-import coupling (schema columns, YAML references, being started by the tick) shows in no check. Rework or delete the remaining tests (D8). Also: the new `answering.yaml` path, schema globs and unused dependencies. Checks run once at the end, so old code is never re-pointed to keep it compiling.
3. **Boundaries and docs.** Rewrite the import-boundaries test (D6) and the README (D9).

No new behavior. Where a sever changes a signature, the function's tests move to the new signature and keep their assertions. Commits: `chore:` for deletions and packaging, `refactor:` for moves and severs, `docs:` for the README.

## Integration Points

**Provides:**

- **222:** `amoeba.answering.values` (what its store persists), `AnswererSettings` (what its loader builds) and `cli_call`. No console entry point and no old migrations. No kept module resolves a directory to its Context Forge project (`resolve_checkout` maps a slice to a checkout), so 222 builds that for `set_up`.
- **223:** the answering library (question, slice reference, precedent and settings in; scratch directory, passages, then a confirmed answer or decline out), `upstream/squadron/run_outcome.py` (`poll_run`, checkpoint kinds), and the `waits on 223` live tests with their claims and restore commit. Deleted launch and stage code stays readable in git history.
- **224:** nothing beyond the base.

**Consumes:** the audit (220), and the answering code from slices 140 to 144.

## Success Criteria

- Every path the audit marks `delete` or `squadron` is gone, with its tests.
- Every `keep` and `rework` unit is at its D3 location, or where its audit row records.
- `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright` and `uv run pytest` pass. Because deleted modules no longer exist, this also shows no kept module imports one.
- The library's tests (`tests/answering`, `tests/upstream`) pass with no store, tick or resident process. `src/amoeba` holds only `__init__.py`, `answering` and `upstream`, plus anything the audit kept under another name.
- `uv run pytest tests/live/answering` passes with the `AMOEBA_LIVE_*` variables set. Every file the Live tests section marks `stays` is present, and every deleted `waits on 223` file has its claim and restore commit recorded.
- `tests/test_import_boundaries.py` enforces D6 and passes.
- `uv build` gives a wheel with `amoeba/answering/answering.yaml` and no `.sql` files; `pyproject.toml` has no console entry point or server dependencies.
- Any audit row changed during the cut has a reason and is in the same commit as the code.
- The README says what Amoeba is now and what exists, with nothing from the old pitch.
- `amoeba#32` is closed at merge with a pointer to this slice.

## Risks

- **Hidden coupling.** Kept code can depend on deleted code without importing it, and a test can still pass on an old-shape fixture. Mitigation: work each Dependencies of kept code entry in step 2, and apply D8's old-shape fixture rule. A wrong audit row is handled under D1.

## Implementation Notes

1. Confirm the audit is `complete` and branch `221-slice.the-cut` from `main`. Check D2's predictions, D3 and D4 against the audit's Verdicts and Differences from the architecture. Where they differ, the audit wins (D1).
2. Follow the three Migration Plan steps. Run the live tier after steps 2 and 3.
3. Normal route: tasks, implementation on the branch, code review, merge in Phase 7.

- **Smaller wins.** A kept test or helper in doubt, with no scenario behind it, goes. Git history keeps it.
- **Don't fix while cutting.** A bug in kept code is filed as an issue under the Fixes rule, so the diff is only moves, severs and deletes.
