---
docType: tasks
slice: edges-and-release
project: amoeba
lld: user/slices/183-slice.edges-and-release.md
dependencies:
- 181
- 123
- 124
- 125
- 127
- 128
- 132
- 141
- 142
projectState: Initiatives 100, 120 and 140 are complete and merged. The project store
  is at schema version 15 (`src/amoeba/store/schema/`). `ready_slices()` takes no
  argument, `current_slices(tree, index)` takes two, and `record_runner_report` has
  no `branch_head`. `AnsweredBy` has `answerer` and `pm` only. Slice 181 (program
  record) is designed and tasked but not implemented when this file was written; its
  code being on the target is the precondition checked in Task 0.1. Nothing under
  `src/amoeba/program/`, `store/program_schema/` or `runner/program/` exists yet.
dateCreated: 20261104
dateUpdated: 20261104
status: not_started
turns: 23
promptTokens: 1283031
cachedTokens: 1164577
cacheWriteTokens: 118422
completionTokens: 26333
durationSeconds: 191.4
costUsd: 0.853838
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.8538376
    completionTokens: 26333
---

## Context Summary

- Working on the **edges-and-release** slice (183), the fourth slice of initiative 180 (program coordination). A slice can wait on another project's slice and resume when the change lands. The program store gains edges; the program stage gains a provider side, a waiting side and release; readiness takes open edges as external predecessors.
- **Current state:** see `projectState`.
- **Dependencies:** 181 (`ProgramStore`, program schema line, program inbox drain, `read_member` and `Readable`, the program stage seam, `RunnerHost.program_store`, `program-blocked`); 120's readiness, resolution stage, ingest and `git_read` (123 to 128, 132); 140's question record and submission writer (141, 142).
- **What this slice delivers:** program schema 002 (`edges`); `EdgeState`, `EdgeWait`, `EdgeTarget`, `effective_mode`; `resolve_edge` inbox kind; the `member_referenced` check over edges; project schema 016 (`slice_heads`) and the head written in the `done` transaction; `submit_release` and `AnsweredBy.COORDINATOR`; readiness with external waits; `heads.py`, `observe_edges.py`, `release.py`; the stage's three jobs and `ProgramView`; the resume-failed payload; edge rows on `program-blocked`; contract docs and CHANGELOG.
- **Nothing creates an edge except tests.** A live project behaves exactly as after 182. GitHub issues #25 and #26 are closed at merge (Phase 7), not by a task.
- **Next planned slice:** 184 (request runs); 185 (request outcome) and 186 (live walkthrough) follow.

**Branch:** read the target (`cf config get git.integration_branch`; empty means `main`). Before Task 0.1, create `183-slice.edges-and-release` from the target and work there. No task merges or pushes. Merging follows the code review. Per the LLD's Prerequisites, 183 starts only after 181 has merged; Task 0.1 verifies that and is not a wait on anyone.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/183-slice.edges-and-release.md` at the named decision (D1 to D13) or section. Source paths are relative to `src/amoeba/` unless they start with `tests/`, `docs/` or `project-documents/`. Follow `.claude/rules/python.md` and `.claude/rules/sql.md`: ruff and strict pyright, no silent fallbacks, every `try/except` justified. Read each file before editing it. Keep source files near 300 lines and functions near 50. Every vocabulary is a `StrEnum` defined once and pinned to its SQL `CHECK` by a test; no comparison value is repeated as a literal elsewhere.

**Order:** work tasks in file order. No task needs a model, a key, live CF or `sq`; every scenario uses test-written stores, temporary git repositories (`tests/runner/git_repo.py`) and the existing fake `sq`.

**Commit cadence:** commit only at the `**Commit**:` markers. Run `uv run ruff format .` before each commit, and `uv run ruff check .` and `uv run pyright` before markers that follow Python changes.

---

## 0. Preflight

- [ ] **0.1 Confirm 181's code exists and record its real names** (effort 1)
  - [ ] Create the branch (see Branch above). Then check that 181's code is present on the target (read the files; change nothing): `ProgramStore` (`open`, `open_read_only`, `members`, `program_of`, `apply_submission`) and the program schema version constant; `ProgramSubmissionKind`, `ConsumptionMode`, `ProgramRejection` (with `member_referenced` reserved and its named hook in `apply_submission`), `Program`, `Member`; `inbox/program_envelope.py`, `submit_program` and the `submit` CLI derivation; `process/program_inbox_tenant.py`; `read_member`, `Readable` (with the resolved `Checkout` and the CF project id), `Unreadable`, `MemberState`; `RunnerHost.program_store`; `runner/program/stage.py` and where `ProjectTick.run` calls it; `inspection/program.py` with the `program-blocked` listing and its `member_unreadable` kind; the locality proof in `tests/contract/oracle.py`; `resolve_checkout` exported from `amoeba.upstream.context_forge`. Also note whether 182's code is on the target (it is independent and may merge either way); Task 0.2's literals describe whichever state this finds, and are re-run on the merged code if 182 lands later.
  - [ ] Where 181's code differs in name or shape from this file, follow the code and use its names in every task below. Do not edit 181's design.
  - [ ] Success: each name above was found by reading the code (not assumed); any difference is noted at the top of the task you are on when you reach it. If 181's code is not on the target, write `BLOCKED: slice 181 code is absent from the target` under this task, leave it unchecked, and stop.
- [ ] **0.2 Pin the tick baseline before any change** (effort 2)
  - [ ] In `tests/runner/program/test_tick_baseline.py`, using the harness of `tests/runner/test_end_to_end.py`, tick one scripted project that is in no program (with a runnable slice, a paused run and a finished run) and assert three things against literals written in the test: the store writes, the issued commands, and the journal entries.
  - [ ] Write the literals by running the test on the unchanged code and copying what it recorded, so they are the current behavior and not a guess. Task 4.1 reuses this test unedited, and it must still pass at Task 7.5.
  - [ ] Success: the test passes on the code as it stands; `uv run pytest tests/runner/program/test_tick_baseline.py` passes.

**Commit**: `test: pin the tick baseline for a project in no program`

## 1. Edges in the program store

- [ ] **1.1 Vocabularies and models** (effort 2)
  - [ ] In `store/program_models.py` (or a sibling `program_edge_models.py` if it would pass ~300 lines) add per LLD API Contracts: `EdgeState` (`open`, `satisfied`, `released`, `superseded`), `EdgeWait` (the six reasons of D10), frozen `ProvidingSlice(node_id)` and `ProvidingCommit(sha)` with `type EdgeTarget`, and frozen `Edge` carrying every column of the LLD schema (target as `EdgeTarget`). Export from `amoeba.store`.
  - [ ] The closed states (`released`, `superseded`) are defined once as a set beside `EdgeState`.
  - [ ] Success: `uv run pyright` passes.
- [ ] **1.2 `effective_mode`** (effort 2)
  - [ ] Create `program/modes.py` (181's `amoeba.program` package): `effective_mode(members, provider, dependent) -> ConsumptionMode`, pure: the override on the dependent for that provider if present, else the provider's `consumed`. An unknown provider raises `ValueError`. The package imports only `amoeba.store` and `amoeba.upstream`.
  - [ ] Tests in `tests/program/test_modes.py`: no override gives `consumed`; an override wins in both directions; an override for a different pair is ignored; unknown provider raises.
  - [ ] Success: tests pass; the `amoeba.program` import rule still holds (`tests/test_import_boundaries.py`).
- [ ] **1.3 Schema 002 and the pinning test** (effort 3)
  - [ ] Create `store/program_schema/002_edges.sql` exactly as the LLD "Database / Storage Schema" gives it, with the `wait` column `CHECK`ed against the `EdgeWait` values (null allowed) and both indexes. Raise the program schema's expected-version constant (defined once in Task 0.1's names) to 2, and update every 181 test that asserts version 1 to read that constant instead.
  - [ ] Test in `tests/store/test_program_schema.py` (extend): migrating a version-1 program store to 2 keeps its rows; each enum (`EdgeState`, `EdgeWait`, `ConsumptionMode` for `mode`) equals the `CHECK` list read from `sqlite_master`; a row with both or neither of `provider_node_id` and `provider_commit` is refused; a row whose waiting and provider projects are equal is refused; an unknown state, mode or wait is refused.
  - [ ] Success: tests pass; a newer-stamped program store still raises `StoreSchemaError`.
- [ ] **1.4 `create_edge` and the reads** (effort 3)
  - [ ] Create `store/program_edges.py`, mixed into `ProgramStore`: `create_edge(...)` per D1 (one transaction: both projects are members of the same program, they differ, the need is not blank, `question_block_id` is non-blank; otherwise `ValueError`, nothing written). It computes nothing itself: the caller passes the `mode` (from `effective_mode`) and the edge stores it. New edges are `open` with no wait. Reads: `edge(edge_id)`, `edges_waiting(project_id, states)`, `edges_providing(project_id)` (open edges only, D5), each in `edge_id` order. SQL and row mapping follow the existing `sql_*.py` / `mapping_*.py` split.
  - [ ] Tests `tests/store/test_program_edges.py`: create with each target kind; each `ValueError` case writes nothing; reads by waiting project and state set, by provider (open only); order; a read through `open_read_only` works and cannot write.
  - [ ] Success: tests pass.
- [ ] **1.5 Edge state writes** (effort 3)
  - [ ] Add `record_wait(edge_id, wait, detail, at) -> bool` (writes `wait`, `wait_detail`, `wait_since` and `updated_at` only when the wait or detail differs from the stored one; returns `False` when unchanged and writes nothing), `mark_satisfied(edge_id, commit, target, at)` (open to satisfied; stores `satisfied_commit`, `satisfied_target`, `satisfied_at`, clears the wait), `close_edges(edge_ids, state, at)` (to `released` or `superseded` only; sets `closed_at`), and `confirm_release(edge_id, at)` (writes only `release_confirmed_at`, leaving every other column including `updated_at`; Task 2.2 calls it).
  - [ ] Transitions per D1: `open` to `satisfied`, `open` or `satisfied` to `superseded`, `satisfied` to `released`. Anything else (a closed edge, `released` straight from `open`) raises `InvalidTransitionError`-style (reuse the store's existing error type), writing nothing. Each call is one transaction. Only `confirm_release` writes `release_confirmed_at`, and it changes no state.
  - [ ] Tests (same file as 1.4 or a sibling): `record_wait` returns `True` then `False` for the same wait and detail, and `wait_since` does not move on the `False`; a changed detail returns `True`; `mark_satisfied` fields; each legal and each illegal transition; a closed edge cannot reopen; `release_confirmed_at` is untouched by the other three; `confirm_release` writes only that column and no state.
  - [ ] Success: tests pass.

**Commit**: `feat: add edges to the program store with schema 002`

- [ ] **1.6 `member_referenced` over edges** (effort 2)
  - [ ] Fill 181's named hook in `ProgramStore.apply_submission` (D11): a `register_program` replace that would drop a member any edge references as waiting or provider, closed edges included, is rejected `member_referenced` in the same transaction, with nothing else written. The reason names the member and an edge id.
  - [ ] Tests in `tests/store/test_program_reject_program.py` (extend): rejected for a waiting member and for a provider member, each with an open edge and with a `released` edge; a replace that keeps every referenced member is applied; nothing else is written on rejection (compare table contents).
  - [ ] Success: tests pass; 181's rejection-order test still holds, with `member_referenced` last.

**Commit**: `feat: refuse to drop a program member that an edge references`

## 2. The `resolve_edge` submission

- [ ] **2.1 Kind, payload and CLI** (effort 3)
  - [ ] Add `ProgramSubmissionKind.RESOLVE_EDGE`, the field-name constant `edge_id`, and the three `ProgramRejection` codes `unknown_edge`, `edge_not_from_release`, `edge_closed`. Add the Pydantic payload model (`edge_id` non-blank, unknown keys refused) and register the kind in 181's envelope parser. The `submit` CLI derives `resolve-edge --by operator --edge-id E` from the kind and field by the existing flag rule; it takes no `--project`.
  - [ ] Tests: extend `tests/inbox/test_program_payloads.py` (valid body; blank id; unknown key; the field-name pin), `test_program_envelope.py` (valid envelope; a real-format file written by `submit_program`), and `tests/cli/` (the command prints an id; a blank `--edge-id ""` exits 9 (`SUBMISSION_REFUSED`) naming the field; a missing `--edge-id` is argparse's usage error, because `add_payload_flags` makes a required field a required flag). Extend the pin test that ties each `ProgramRejection` to its documented codes.
  - [ ] Success: tests pass; `amoeba submit --help` lists `resolve-edge`.
- [ ] **2.2 Applying `resolve_edge`** (effort 3)
  - [ ] In `apply_submission` apply the kind per D4: set `release_confirmed_at` (apply time) on the edge, writing no other column (`updated_at` included). The write is `confirm_release(edge_id, at)` in `store/program_edges.py` (the name the LLD's component table gives), run inside `apply_submission`'s transaction. Rejections, recorded like the others and checked in this order: `unknown_edge`, `edge_not_from_release` (mode is `from_source`), `edge_closed` (`released` or `superseded`). An identical re-submission on an already confirmed open or satisfied edge is `applied` and changes nothing but the submission row.
  - [ ] Tests `tests/store/test_program_apply_resolve_edge.py`: applied sets only `release_confirmed_at`; the other columns, `updated_at` included, are unchanged; confirmation before the provider is done is recorded; re-submission is applied and writes no second confirmation time; each rejection recorded with `"<code>: <detail>"` and nothing else written; a `satisfied` edge is still confirmable. Add one end-to-end case through `ProgramInboxTenant` (file in `programs/inbox/new/`, applied, file deleted) in a new `tests/process/test_program_inbox.py`, with `edge` in the test name so LLD walkthrough step 1's `-k` selects it.
  - [ ] Success: tests pass.

**Commit**: `feat: add the resolve_edge program submission`

## 3. The branch head and `submit_release`

- [ ] **3.1 `slice_heads` and `BranchHead`** (effort 3)
  - [ ] Create `store/schema/016_slice_heads.sql` exactly as the LLD gives it and raise the project schema's expected version to 16 (the constant `Store` passes, defined once); update every test that asserts 15 to read the constant. Add the frozen `BranchHead(branch, commit, missing, detail)` model and a `SliceHead` read model, and a `Store.slice_head(node_id) -> SliceHead | None` read (works through `open_read_only`).
  - [ ] Tests `tests/store/test_migration_016.py` (mirror `test_migration_015.py`): migrating 15 to 16 keeps rows; the `missing` and `NOT (missing = 1 AND head_commit IS NOT NULL)` checks refuse bad rows; `slice_head` reads one; `slice_heads` references `nodes`.
  - [ ] Success: tests pass; `tests/test_migrations.py` passes with its version updated to the constant.
- [ ] **3.2 `branch_head` on the `done` writes** (effort 4)
  - [ ] `record_runner_report` gains a keyword `branch_head: BranchHead | None` with **no default**; update every caller (`runner/ingest/record.py` passes `None` for now; tests pass `None` unless they test the head). With a head, the `slice_heads` row is written in the same transaction as `done`, after the resolution; `branch_head` given without `complete_node_id` raises `ValueError`. A node already `done` still gets its row only if it has none. Add `complete_slice(node_id, branch_head)` in the same module: marks `done` and writes the row in one transaction (D6), refusing as `update_node_status` does.
  - [ ] Tests `tests/store/test_slice_heads.py`: the row lands with `done` from `record_runner_report` and from `complete_slice`; a failure inside the transaction (a blocked node) leaves neither `done` nor a row; `None` writes no row; `branch_head` without `complete_node_id` raises and writes nothing; each of the three `BranchHead` shapes (commit, missing, failed read with detail) round-trips.
  - [ ] Success: tests pass; existing `tests/store/test_runner_report.py` and `tests/runner/ingest` pass with only the explicit `branch_head=None` added.

**Commit**: `feat: record a providing slice's branch head in the done transaction`

- [ ] **3.3 `AnsweredBy.COORDINATOR` and `submit_release`** (effort 4)
  - [ ] Add `AnsweredBy.COORDINATOR = "coordinator"` in `store/question_models.py`; no migration (`answered_by` is checked in code). Define `RELEASABLE_STATES = {pending, answering}` once beside `QuestionState`. Create `store/release_submission.py` mixed into `Store`: `submit_release(blocked_state_id, *, instructions, detail) -> ReleaseOutcome` (`submitted` | `block_resolved`) per D8, in one `BEGIN IMMEDIATE`: a missing block row raises; an already resolved block returns `block_resolved` and writes nothing; otherwise fill the slot through `_write_resolution` (`resume`, `awaits_runner` true, `resolved_by` coordinator), insert the submission row through `SubmissionWriter` with `submitted_by` coordinator, and settle the linked question record to `answered` (`answered_by` coordinator, `answer` = instructions) when its state is in `RELEASABLE_STATES`. A `declined` or `answered` record is left as it is.
  - [ ] The decision string is the existing `ANSWER_DECISION`, not a second literal.
  - [ ] Tests `tests/store/test_release_submission.py`: submitted on a block with a `pending` record and with an `answering` record; submitted on a block with no record; `block_resolved` writes nothing (a PM-resolved block and a coordinator-resolved block); a `declined` record keeps its decline; a missing block raises; the slot, the submission row and the record are all written, or none (inject a failure after the slot write); a later PM resolution on the block is rejected as already resolved by the inbox's existing rule.
  - [ ] Pin each 140 reader of `answered_by` (D8): the answer limit counts only `answerer` (`COUNT_ANSWERER_ANSWERS_IN_RUN`); `runner/answering/sources.py` takes only `pm` as precedent; a finishing answering run over a record settled by `coordinator` reports `discarded`. Put each in the existing test file of that reader.
  - [ ] Success: tests pass.

**Commit**: `feat: add submit_release and the coordinator as an answerer`

## 4. Readiness with external waits

- [ ] **4.1 `external_waits_met` and the required `waiting` argument** (effort 3)
  - [ ] In `runner/lifecycle/predecessors.py` add `external_waits_met(node, waiting: AbstractSet[str]) -> bool` (true when the node id is not in the set). `LifecycleTree.ready_slices(waiting)` takes the set as a **required** argument and adds the check beside `slice_predecessor_done`; `governance.current_slices(tree, index, waiting)` passes it through; `build_project_view(..., waiting)` takes it as a required keyword and passes it on. `tick.py` passes `frozenset()` for now (Task 7.5 feeds the real set). Update every caller and test fixture (`grep -rn "ready_slices\|current_slices\|build_project_view" src tests`).
  - [ ] The predecessors module docstring is updated: it says external waits are now part of what a slice waits for. `runner/lifecycle` must not import the program store.
  - [ ] Every test below has `waiting` or `external` in its name, so LLD walkthrough step 2's `-k "waiting or external"` collects them.
  - [ ] Tests: `tests/runner/lifecycle/test_ready_slices.py` (a runnable slice in `waiting` is not ready; it is ready again when removed; other slices are unaffected; the predecessor rule still applies together with a wait), `tests/runner/intent/test_governing.py` (`current_slices` honors `waiting`), and a resolution-planner case in `tests/runner/resolutions/` (an applied `resume` resolution on a waiting slice yields no `ResumeRun`; it yields one once the node leaves `waiting`). Add a rule to `tests/test_import_boundaries.py` that `amoeba.runner.lifecycle` imports no program-store module, and confirm it fails on a deliberate import (revert it).
  - [ ] Regression: Task 0.2's baseline test passes with its literals unedited, now that `waiting` is empty on every tick.
  - [ ] Success: `uv run pytest tests/runner tests/test_import_boundaries.py` passes; `uv run pyright` passes.

**Commit**: `feat: readiness takes external waits as a required argument`

## 5. Reading a providing slice's branch head

- [ ] **5.1 The branch-name function** (effort 1)
  - [ ] In `upstream/context_forge/slice_stem.py` add `slice_branch_name(index, name) -> str` returning `{index}-slice.{name}`, and use it wherever the repo builds that string today (`grep -rn '"-slice\.\|-slice\.{' src`). Export it from the package.
  - [ ] Tests beside `parse_slice_stem`'s: the name for an index and slug; a round trip with `parse_slice_stem`.
  - [ ] Success: tests pass.
- [ ] **5.2 `heads.py`** (effort 4)
  - [ ] In `runner/git_read.py` add `branch_heads_args()` beside the other argument builders: `log --no-walk --branches --decorate-refs=refs/heads/ --format=%H%x09%D` (the `log` subcommand is already allowed). Create `runner/program/heads.py` with `read_branch_head(checkout, branch, budget, run, timeout) -> BranchHead | None`: parse the lines, take the commit whose name list contains the branch exactly (`D5`; not a prefix, not `origin/…`); `None` when the budget refuses; a non-zero exit or `GitReadFailure` gives `commit` null, `missing` false and the failure as `detail`; a successful read with no such branch gives `commit` null and `missing` true. A slice with no CF name is the caller's case (`missing` true with a detail naming it), through one helper in this module.
  - [ ] Git-backed tests `tests/runner/program/test_heads.py` using `tests/runner/git_repo.py`: the head is found for a branch among several, including one whose name is a prefix of another; absent branch is `missing`; a remote-tracking ref does not count; a non-repository directory is a failed read with a detail; a refused budget returns `None` and runs no git; a slice with no CF name gives `missing` true with a detail naming the cause and runs no git.
  - [ ] Success: tests pass; `tests/runner/test_git_read.py` and `test_git_read_only_place.py` pass.
- [ ] **5.3 Head read before ingest marks `done`** (effort 4)
  - [ ] Read `runner/record_runs.py`, `runner/finish.py` and `runner/ingest/record.py`. Thread the providing set, the budget, the git runner and the timeout (the same ones the plan stage uses; read how `tick.py` supplies them) into `record_finished` and `ingest`. For a finished run whose plan completes the node (`plan.complete_node` and no block) and whose node id is in `providing`: read the head with `heads.py` in the run's `PARAM_CHECKOUT`, before any write, and pass it as `branch_head`. Every other run passes `None` and makes no git call. A budget refusal (`None`) leaves the entry unfinished this tick: nothing is written for it and the next tick observes it again (idempotent on re-entry, 125).
  - [ ] `tick.py` passes `frozenset()` as `providing` for now (Task 7.5).
  - [ ] Tests `tests/runner/ingest/test_record_head.py`: a completing run on a providing slice writes the `slice_heads` row with `done`; the same run on a non-providing slice makes no git call and writes no row; a failed read records `commit` null, `missing` false, with the detail, and the run's outcome is still recorded; a missing branch records `missing`; a refusal leaves the journal entry unresolved and the node not `done`, and the next call completes it; a run that does not complete the node (blocked, paused, failed) makes no git call.
  - [ ] Success: tests pass; the existing ingest and tick tests pass.

**Commit**: `feat: read a providing slice's branch head before its run marks it done`

- [ ] **5.4 Head read for a slice completed by hand** (effort 3)
  - [ ] In `runner/lifecycle/completion.py`, `complete_observed_slices` takes the providing set and a `read_head: Callable[[str], BranchHead | None]` (a `None` is a budget refusal), and does no git or checkout work itself. For a providing slice reported complete with no run it calls `read_head(node_id)`, then `store.complete_slice(node_id, head)`; a `None` leaves the slice `runnable` this tick. Every other slice keeps `update_node_status` and never calls `read_head`. Add `slice_head_reader(...)` to `runner/program/heads.py`: it returns the callable the plan stage builds, which resolves the checkout with `resolve_checkout` at the slice's initiative index (the observed snapshot of its CF link) and reads the head under the plan stage's budget; an unresolvable checkout gives `commit` null, `missing` false and the reason as `detail`. Pass the set and the reader through `reconcile.py` and the plan stage; `tick.py` passes `frozenset()` and a reader that is never called for now.
  - [ ] Tests extend `tests/runner/lifecycle/test_completion.py` with a fake `read_head` (no git): a providing slice gets `done` and its row in one transaction; a non-providing slice never calls `read_head` and gets no row; a refusal leaves it `runnable` and the next pass completes it; a slice with an unresolved journal entry is still left alone. Git-backed tests of `slice_head_reader` go in `tests/runner/program/test_heads.py`: an unresolvable checkout records the failure; a found branch gives its commit.
  - [ ] Add a rule to `tests/test_import_boundaries.py` that `amoeba.runner.lifecycle` imports neither `runner.git_read` nor `runner.program`.
  - [ ] Success: tests pass; `tests/runner/lifecycle` passes.

**Commit**: `feat: record the branch head of a providing slice completed by hand`

## 6. Observing an edge

- [ ] **6.1 Provider facts and the first three waits** (effort 4)
  - [ ] Create `runner/program/observe_edges.py` (every program-side git and `cf` read lives here, D10). Define the frozen results `Satisfied(commit, target)` and `Waiting(wait, detail)`. `observe_edge(edge, ...)` first reads the provider: `read_member` (an `Unreadable` gives `provider_unreadable` with its reason and detail), a read-only `Store.open_read_only` of the provider's store for the providing node (absent node: `provider_unreadable`, detail names it), and for a `ProvidingSlice` its status and `slice_head`. A `StoreError` from the provider's store is `provider_unreadable` (specific `except`, with the comment 181 D6 requires). The first matching wait wins, in D10's order: `provider_unreadable`, `provider_not_done`, `branch_head_missing` (done with no `slice_heads` row at all, e.g. done before the edge existed, or a row with no commit and `missing` true; a row with no commit and `missing` false is Task 6.4's `read_failed`).
  - [ ] Tests `tests/runner/program/test_observe_edges.py` with test-written member stores: each of the three waits, with the detail naming what failed (`branch_head_missing` for a done slice with no row and for one with a `missing` row); precedence when two apply (an unreadable provider with a not-done slice reports unreadable); the provider's store file is unchanged after the call; no git or `cf` call is made for any of them (a recording runner).
  - [ ] Success: tests pass.
- [ ] **6.2 From-release satisfaction** (effort 3)
  - [ ] Add D4's rule: a `from_release` edge on a done `ProvidingSlice` waits `awaiting_release` until `release_confirmed_at` is set, then is `Satisfied` with the recorded head and a `None` target. A `ProvidingCommit` edge needs no provider-done check (the commit exists): satisfied once confirmed, else `awaiting_release`. A confirmation recorded before the provider is `done` keeps the edge `provider_not_done`, then `Satisfied` on the first evaluation after `done`.
  - [ ] Tests (same file): confirmation before done; confirmation after done; no confirmation; commit target with and without confirmation; `branch_head_missing` precedence for a done slice with no head (from-release too); no git call in any case.
  - [ ] Success: tests pass.

**Commit**: `feat: observe an edge's provider and from-release satisfaction`

- [ ] **6.3 From-source reachability** (effort 4)
  - [ ] Add D3's rule for a `from_source` edge whose provider is done (or a `ProvidingCommit`): the checkout is `resolve_checkout` at the providing slice's initiative index in the provider's observed snapshot (no checkout resolves: `provider_unreadable`, detail names it), or `Readable`'s checkout for a commit target; the target is `read_target(checkout, provider_cf_project_id)`; reachability is `git merge-base --is-ancestor <commit> <target>` through `git_read` and `is_ancestor_args`. Exit `0` is `Satisfied(commit, target)`, exit `1` is `not_on_target`, any other exit or a failed read is `read_failed` with the command and stderr head. A `cf` read failure is `read_failed`. A budget refusal from either call returns `None` (the caller stops for this tick, D10). Exit code `1` as an answer is documented by a comment citing `--is-ancestor`.
  - [ ] Git-backed tests (same file, `tests/runner/git_repo.py`): satisfied after a merge commit and after a fast-forward onto the target; `not_on_target` for an unmerged branch and for a squash merge; still satisfied after the slice branch is deleted; an unknown commit (exit 128) is `read_failed`; a `cf` failure is `read_failed`; a non-default `git.integration_branch` is the target used; call counts: no `cf` or git call before the provider is done, exactly one `cf` and one git after; each budget refusal returns `None`.
  - [ ] Success: tests pass.
- [ ] **6.4 Retrying a head that failed to read** (effort 3)
  - [ ] Per D5: while the provider's `slice_heads` row has `commit` null and `missing` false, `observe_edge` re-reads the head each tick with `heads.py` in the checkout `resolve_checkout` gives at the slice's initiative index, under the budget. The edge waits `read_failed` meanwhile; a read that finds the branch supplies the commit to the satisfaction check; one that succeeds without it gives `branch_head_missing`. Nothing is written back to the provider's store.
  - [ ] Tests: a transient failure then success gives `read_failed`, then reachability on the same tick the head is found; success without the branch gives `branch_head_missing`; the provider's `slice_heads` row and file are unchanged; a refusal returns `None`.
  - [ ] Success: tests pass.

**Commit**: `feat: observe from-source edges against the provider's target`

## 7. Release and the program stage

- [ ] **7.1 `release.py`** (effort 4)
  - [ ] Create `runner/program/release.py`, pure. Constants (the instruction lines of D7 and `RELEASE_DETAIL`) defined once beside `release_instructions(need, edges)`; one line per satisfied edge by its target kind and mode; identical needs written once, otherwise each edge line preceded by its own `Need:` line. `plan(edges, observations, block_states)` returns the writes to make: per node among the `open` and `satisfied` edges, whether every edge is satisfied (ready to release) and the edge ids to close as `released` or `superseded` (D9: a block resolved by `coordinator` closes its `satisfied` edges `released` and an `open` one `superseded`, resolved by anyone else `superseded`).
  - [ ] Purity: in `tests/runner/program/test_release.py` add `assert io_use(release) == []`, with `io_use` from `tests/runner/purity.py` (each module's purity assertion lives in its own test file, as in `tests/runner/test_decide.py`).
  - [ ] Tests `tests/runner/program/test_release.py`: the exact text for each of the three line shapes, importing the constants; identical needs once; differing needs each with a `Need:` line; several edges for one slice; a node with one open edge is not released; each supersession case; the purity check passes.
  - [ ] Success: tests pass.
- [ ] **7.2 `ProgramView` and supersession** (effort 3)
  - [ ] In `runner/program/stage.py` replace 181's `Program | None` result with the frozen `ProgramView(program, waiting, providing)` (empty `waiting` and `providing` for now; Tasks 7.3 and 7.4 fill them). Add the first waiting-side job (D9): for each `open` or `satisfied` edge this project waits on, in `edge_id` order, read its question block in the asker's own store and close the edge per `release.plan` (resolved by `coordinator`: a `satisfied` edge is `released`, an `open` edge is `superseded` because a release needs every edge satisfied; resolved by anyone else: `superseded`), counting each write toward `tick.wrote`. A program store failure propagates (it is in `STORE_FAILURES`).
  - [ ] Tests `tests/runner/program/test_stage_supersede.py` with test-written stores: a PM resolution on the block supersedes the edges before anything is observed; a block resolved by `coordinator` closes its `satisfied` edges `released` and an `open` one `superseded`; an unresolved block closes nothing and writes nothing; a project in no program gets `None` as before; 181's stage tests pass with the result type updated.
  - [ ] Success: tests pass.
- [ ] **7.3 Observing open edges** (effort 4)
  - [ ] In the stage, after supersession, for each `open` edge in `edge_id` order call `observe_edges`, writing `mark_satisfied` or `record_wait` only when the state or wait changed, each write counting toward `tick.wrote`. A `None` (budget refusal) stops evaluating the remaining edges this tick and leaves them as they are. `waiting` is the node ids with an `open` edge after this evaluation. A member store failure is a wait reason, never an exit (D10).
  - [ ] Tests `tests/runner/program/test_stage_waiting.py` with test-written stores and a stubbed `observe_edges` result: each observation writes the right state and wait; an unchanged observation writes nothing and leaves `wrote` false; a refusal stops the loop and the later edges are untouched but still in `waiting`; `waiting` holds only `open` edges.
  - [ ] Success: tests pass.
- [ ] **7.4 The provider side and release** (effort 4)
  - [ ] `providing` is the node ids named by `edges_providing(project_id)`. After the waiting side, group the project's `edges_waiting(project_id, {open, satisfied})` by node (not the `waiting` set, which holds only `open` edges and never contains a node whose edges are all satisfied); for each node with no `open` edge: `submit_release` on the question block in the asker's own store with `release_instructions` and `RELEASE_DETAIL`, then `close_edges(..., released)`. A `block_resolved` outcome applies D9 instead (close by who resolved it). A crash between the writes is finished by the next tick, with no second resolution.
  - [ ] Tests `tests/runner/program/test_stage_release.py`: release writes the resolution, closes the edges `released`, and the record is `answered` by `coordinator`; two edges on one slice release only after both are satisfied; a node whose edges are all `satisfied` (so absent from `waiting`) is released, and a test fails if the loop reads `waiting`; `block_resolved` closes by resolver; stop after each of the three writes (satisfied, resolution, released) and run the next tick: exactly one resolution exists afterwards; `providing` lists only open provider-side edges and drops a slice once its edge closes.
  - [ ] Success: tests pass.
- [ ] **7.5 The view on the tick** (effort 4)
  - [ ] Read `runner/tick.py` (311 lines). Keep the stage's `ProgramView` on the tick: pass `waiting` to `build_project_view`, and `providing` to `record_finished` and the plan stage (replacing the empty sets of Tasks 4.1, 5.3, 5.4). If this grows `tick.py` past where it is at 181's merge, put the stage call and the hand-off to `build_project_view` in a helper beside the stage (D2). The stage keeps its place: after resolutions are acknowledged, before Observe.
  - [ ] Tests `tests/runner/program/test_tick_edges.py` (use `tick_rig.py` and `tests/runner/test_end_to_end.py` helpers): a slice with an open edge is not launched and an applied `resume` resolution is not resumed; when its edges leave `open` it is current again with no desired-state row written; a PM `resume` arriving in the same tick closes the edges and the slice resumes that tick. Regression: tick one scripted project with no program store, with a program store holding an unrelated program, and with one holding its own program and no edges; store writes, issued commands and journal entries are identical across the three (extend 181's regression test).
  - [ ] Success: tests pass; `uv run pytest tests/runner` passes.

**Commit**: `feat: grow the program stage into observe, release and supersede`

- [ ] **7.6 Resume-failed payload for a release** (effort 2)
  - [ ] In `runner/finish.py`, `_record_resume_failed` adds `resume_instructions` to the block payload only when the failed entry carried out a resolution whose `resolved_by` is `coordinator`, reading the instructions from the blocked state the entry's parameters name (D12). The key is a constant beside the other payload keys. A PM resolution's failed resume is unchanged.
  - [ ] Tests extend `tests/runner/test_finish.py`: a failed resume of a coordinator resolution carries `resume_instructions` equal to the release text; a PM resolution's failed resume has no such key and an otherwise identical payload; a missing run (`RUN_MISSING`) carries it too and still resolves `not_found`.
  - [ ] Success: tests pass.

**Commit**: `feat: carry release instructions on a failed resume`

- [ ] **7.7 Release scenario: the main path** (effort 5)
  - [ ] Create `tests/runner/program/test_release_scenario.py` and its support module (two scratch member stores, two scratch repos, the fake `sq`, a program store with a program and one edge written by the test via `create_edge` and `effective_mode`). Honor `AMOEBA_KEEP_SCENARIO_DIR` by keeping the supervisor directory and printing its path (LLD walkthrough step 5).
  - [ ] Main path, one test: ticks show `provider_not_done`; the provider's run completes and the head is recorded; `not_on_target` until the test's git helper puts the slice's commit on the provider's target; satisfied; release writes the resolution; the next tick resumes the run and the instructions text is the one `release_instructions` builds; a late PM resolution on the block is rejected as already resolved.
  - [ ] Success: the test passes.
- [ ] **7.8 Release scenario: release variants** (effort 3)
  - [ ] In the same module, one test per variant: from-release with `resolve_edge` before and after `done`; a PM resolution first (edges `superseded`, the provider's slice keeps running); a resume whose run is gone (the block carries `resume_instructions`). The crash points of release are proven in Task 7.4's tests and are not repeated here.
  - [ ] Success: all pass.
- [ ] **7.9 Release scenario: head variants** (effort 3)
  - [ ] In the same module, one test per variant: the provider slice completed by hand (CF reports it complete with no run), head recorded by the plan stage; an edge created against an already-`done` `ProvidingSlice` waits `branch_head_missing` (the contract test D5 requires); a branch deleted after `done` leaves the edge satisfiable once its commit is on the target; a head read that fails at `done` waits `read_failed` and is satisfied after a later read finds the branch, with no PM step; a tick that observes no change writes nothing to the program store.
  - [ ] Success: all pass; `tests/runner/program` passes as a directory.

**Commit**: `test: prove release, supersession and head recording across two projects`

## 8. Listings, locality and docs

- [ ] **8.1 Edge rows on `program-blocked`** (effort 3)
  - [ ] Define the `edge` blocked-on kind once beside 181's `member_unreadable`. In `inspection/program.py` add one row per edge in state `open` or `satisfied` per D13: `program_id`, waiting `project_id`, `node_id`, `title`, `blocked_on` = `edge`, `reason` = `"<wait>: <detail> (since <wait_since>)"` or `satisfied: awaiting release`, `blocked_state_id` = the question block, `context` = the edge id, other columns empty. Closed edges are not listed. With no program store, no edge rows. Inspection stays read-only and makes no subprocess.
  - [ ] Tests extend `tests/inspection/test_program.py`: an open edge with each wait; a satisfied edge; a released and a superseded edge are absent; `context` is the edge id; `since` appears in the reason; the member rows 181 lists are unchanged; works with the process stopped and writes nothing.
  - [ ] Success: tests pass; tests that enumerate blocked-on kinds are updated.

**Commit**: `feat: list edges on program-blocked`

- [ ] **8.2 Locality proof and writer guard** (effort 3)
  - [ ] Add `edges` to the program store's allowed table set in `tests/contract/oracle.py` (`locality_problems`) and extend the scenario so an edge exists when the proof runs. Add a check that `slice_heads` is never in the program store and is present in project stores.
  - [ ] Negative tests in `tests/contract/test_oracle.py`: `slice_heads` added to a scratch program store makes the proof fail naming the table; an unknown table in the program store still fails. Confirm `tests/test_writer_guard.py` passes unchanged (edges are written only through the host's `ProgramStore`).
  - [ ] Success: `uv run pytest tests/contract tests/test_writer_guard.py` passes.

**Commit**: `test: extend the locality proof to edges`

- [ ] **8.3 `docs/store-contract.md`** (effort 2)
  - [ ] Add the `edges` table, its two writers on disjoint columns (the asker's tick owns everything but `release_confirmed_at`; `ProgramInboxTenant` writes only that column), the edge states and transitions, `slice_heads` and the `done` transaction's head, the updated locality set, `AnsweredBy.COORDINATOR` and `submit_release`; the program schema line now at 2 and the project line at 16.
  - [ ] Success: each LLD "API Contracts" method appears; no claim contradicts the code.
- [ ] **8.4 `docs/inbox-contract.md`** (effort 2)
  - [ ] "Program submissions" gains `resolve_edge` (field table), the three new rejection codes, `member_referenced` now produced for edges, and `coordinator` as a submitter on the resolution row.
  - [ ] Success: the field table matches the payload model.
- [ ] **8.5 `docs/process-contract.md`** (effort 3)
  - [ ] Describe the program stage's three jobs and its result (`ProgramView`), readiness with external waits, the head read before `done` on both paths, release and supersession (including the crash story and the two-loop lag), the wait-reason vocabulary, and every program-side git and `cf` read with its budget behavior.
  - [ ] Success: the stage's place and the read counts match `ProjectTick.run` and `observe_edges.py`.

**Commit**: `docs: document edges, release and the branch head`

## 9. Final validation

- [ ] **9.1 Full checks** (effort 1)
  - [ ] Run `uv run ruff format .`, `uv run ruff check .`, `uv run pyright` and `uv run pytest` (the bare run, which excludes the live and load tiers).
  - [ ] Run the existing load tests as regression checks (none exercises an edge), by explicit path: `uv run pytest tests/load/test_runner_tick_load.py tests/load/test_inbox_concurrent.py tests/load/test_program_load.py` (the last is 181's). The bounds must hold without edits.
  - [ ] Success: all pass, with no existing test skipped, weakened or edited to pass, apart from the version-constant, `branch_head=None`, `ready_slices(waiting)`, blocked-on-kind and result-type updates Tasks 1.3, 3.1, 3.2, 4.1, 7.2 and 8.1 name. If a check fails, fix its cause and re-run.
- [ ] **9.2 Verification walkthrough** (effort 3)
  - [ ] Run steps 1 to 4 and 6 of the LLD "Verification Walkthrough". Step 5 runs against the directory the scenario keeps (`AMOEBA_KEEP_SCENARIO_DIR` set to a `mktemp -d` path, never the real supervisor directory): `AMOEBA_STORE_DIR=<kept dir> amoeba inspect program-blocked` shows open and satisfied edges with their wait and since.
  - [ ] Success: every step shows what the LLD says; any difference is fixed in code, and the closing report says what each step showed. After any fix, re-run Task 9.1's checks. Delete the throwaway directory when done.

Write no walkthrough note into this file. If a step needed a code fix, commit it at the marker below.

**Commit**: `fix: correct what the edges walkthrough found` (only when a step needed a code fix; use `test:` when only tests changed)

- [ ] **9.3 CHANGELOG** (effort 1)
  - [ ] Under `[Unreleased] / Added`, one or two lines for slice 183 in the existing style: edges and the `resolve_edge` submission, the effective consumption mode and member state reads, the branch head in the `done` transaction, release and supersession, edge rows on `program-blocked`. Note that nothing creates an edge yet.
  - [ ] Success: entry present, concise.

**Commit**: `docs: add slice 183 to the changelog`
