---
docType: tasks
slice: request-runs
project: amoeba
lld: user/slices/184-slice.request-runs.md
dependencies:
- 180
- 181
- 183
- 120
- 124
- 125
- 128
- 132
- 144
projectState: Initiatives 100, 120 and 140 are complete and merged. Slices 180 (slice-writing
  pipeline), 181 (program record) and 183 (edges and release) are designed and tasked.
  Per the LLD's Prerequisites, 184 starts only after they merge, and Task 0.1 verifies
  that against the code. Nothing under `src/amoeba/runner/request_run/`, `store/program_requests.py`,
  `store/request_run.py` or `program/band.py` exists yet. 183's `waiting` readiness
  argument and `edges` table are the seams this slice changes.
dateCreated: 20261104
dateUpdated: 20261104
status: not_started
turns: 13
promptTokens: 703373
cachedTokens: 617608
cacheWriteTokens: 85745
completionTokens: 19641
durationSeconds: 132.5
costUsd: 0.601612
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.6016117000000001
    completionTokens: 19641
---

## Context Summary

- Working on the **request-runs** slice (184), the fifth slice of initiative 180 (program coordination). The provider side of coordination: the program store gains requests, and the provider's tick launches the slice-writing pipeline (180) for each one, binds the asker's edge to the slice the run wrote, and builds that slice ahead of planned work.
- **Current state:** see `projectState`.
- **Dependencies:** 180 (`prepare_request_directory`, `read_reply`, `probe_slice_writing_pipeline`); 181 (member `requests_initiative`, the program stage seam, `member_referenced`, `program-blocked`); 183 (`edges`, `EdgeWait`, `ProgramView.providing`, supersession, the `waiting` readiness argument); 120 and 132 (`checkout_holders`, fresh-launch rule, `PlanStage`, `supervision_entries`, `SortKey`); 144 (`sq_answer`, the pattern `sq_request` follows).
- **What this slice delivers:** program schema 003 (`requests`, `edges` rebuilt); `create_request` and the request state machine; `bind_edge`; the `request` node kind and `sq_request` command kind with recovery; `program/band.py`; `checkout_holds` and the request-run exemption; `ProgramReadiness`, no implicit predecessor, membership drive and request priority; `RequestSettings` and the start-up probe; `PlanStage.mark_due` and `read_completed_since`; `runner/request_run/` (`bind`, `launch`, `finish`, `stage`); 183's observation of unbound edges; `member_referenced` over requests; `program-blocked` request rows; contract docs and CHANGELOG.
- **Nothing outside tests creates a request.** 185 is the producer. A live project behaves exactly as after 183.
- **Next planned slice:** 185 (request outcome); 186 (live walkthrough) follows.

**Branch:** read the target (`cf config get git.integration_branch`; empty means `main`). Before Task 0.1, create `184-slice.request-runs` from the target and work there. No task merges or pushes. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/184-slice.request-runs.md` at the named decision (D1 to D15) or section. Source paths are relative to `src/amoeba/` unless they start with `tests/`, `docs/` or `project-documents/`. Follow `.claude/rules/python.md`, `.claude/rules/sql.md` and `.claude/rules/testing.md`: ruff and strict pyright, no silent fallbacks, every `try/except` justified. Read each file before editing it. Keep source files near 300 lines and functions near 50. Every vocabulary is a `StrEnum` defined once and pinned to its SQL `CHECK` by a test; no comparison value is repeated as a literal elsewhere. Where 181's, 183's or 180's code differs in name or shape from their designs, follow the code and use its names throughout.

**Order:** work tasks in file order. No task needs a model, a key, live CF or a real `sq`; every scenario uses test-written stores, temporary git repositories (`tests/runner/git_repo.py`) and a stub `sq`.

**Commit cadence:** commit only at the `**Commit**:` markers. Run `uv run ruff format .` before each commit, and `uv run ruff check .` and `uv run pyright` before markers that follow Python changes.

---

## 0. Preflight

- [ ] **0.1 Confirm the prerequisite code exists and record its real names** (effort 3)
  - [ ] This task checks the LLD's Prerequisites (184 starts after 180, 181 and 183 merge). It adds no wait of its own.
  - [ ] Create the branch (see Branch above). Then read, and change nothing, to confirm each of these is on the target:
    - [ ] 181: `resolve_checkout`, `Checkout` and `CheckoutUnresolved` now in `amoeba.upstream.context_forge` (181 moves them from `runner/dispatch/checkout.py`; Task 6.4 imports from there); `ProgramStore` (`open`, `open_read_only`, `members`, `apply_submission` with the named `member_referenced` hook), the program schema version constant, each member's `requests_initiative`, `read_member`, `Readable`, the program stage in `runner/program/stage.py` and where `ProjectTick.run` calls it, `inspection/program.py`.
    - [ ] 183: `store/program_edges.py` (`create_edge`, `edges_by_provider`), `EdgeWait`, `EdgeTarget`, `ProvidingSlice`, `ProvidingCommit`, `effective_mode`, `ProgramView` with `waiting` and `providing`, `runner/program/observe_edges.py`, the `waiting` argument on `ready_slices`, `current_slices` and `build_project_view`, and 183's tick baseline test (`tests/runner/program/test_tick_baseline.py`).
    - [ ] 180: `prepare_request_directory`, `RequestInput`, `read_reply` with `NewSlice`, `AlreadyMet` and `ReplyProblem`, `probe_slice_writing_pipeline`, and the constants the argv is built from.
    - [ ] 120, 132 and 144: `dispatch/hold.py` (`checkout_holders`), `checkout_check.py`, `checkout_reads.py`, `PlanStage` and its read schedule, `supervision_entries`, `SortKey`, the `sq_answer` kind, its required keys, observer registration and `runner/answering/` stage, and `tests/runner/git_repo.py`. The stub `sq` to extend is `tests/sq_stub.py` with `tests/sq_stub_scripts.py` (the pair 144's `tests/runner/test_end_to_end_answering.py` imports).
    - [ ] Test files this slice extends or reuses: `tests/store/test_program_schema.py`, `tests/store/test_program_reject_program.py`, `tests/runner/program/test_observe_edges.py`, `tests/inspection/test_program.py`, `tests/load/test_program_load.py`, and 183's scenario support under `tests/runner/program/` (its Task 7.7), which honors `AMOEBA_KEEP_SCENARIO_DIR`.
  - [ ] Write the names this finds as a short list at the top of the task you reach first that uses a changed name. Do not edit the other slices' designs.
  - [ ] Success: each name was found by reading the code, not assumed. If 180, 181 or 183 code is absent from the target, write `BLOCKED: slice <n> code is absent from the target` under this task, leave it unchecked, and stop.
- [ ] **0.2 Confirm the tick baseline test still passes** (effort 1)
  - [ ] Run 183's baseline test unedited. It ticks a project in no program and pins its store writes, issued commands and journal entries. It must pass now and again at Task 9.1.
  - [ ] Success: `uv run pytest tests/runner/program/test_tick_baseline.py` passes. If it does not exist, write `BLOCKED: slice 183 code is absent from the target` under this task, leave it unchecked, and stop. Do not create it here: a baseline taken from code that already includes 184's changes would pin the wrong behavior.

## 1. Requests in the program store

- [ ] **1.1 Vocabularies and models** (effort 2)
  - [ ] In `store/program_models.py` (or a sibling if it would pass ~300 lines) add per LLD API Contracts and D2: `RequestState` (seven values), `RequestWait` (`unreadable`, `requests_unconfigured`, `checkout_in_use`, `checkout_branch`, `checkout_dirty`, `awaiting_plan_read`), `RequestFailure` (`run_failed`, `run_lost`, `reply_missing`, `reply_malformed`, `binding_failed`, `head_moved`, `requests_initiative_full`, `requests_band_collision`, `launch_failed`, `remote_refs_changed` (D16)), and a frozen `Request` carrying every column of the LLD schema.
  - [ ] Add `request_open` and `request_failed` to 183's `EdgeWait`.
  - [ ] The closed states (`bound`, `met`, `failed`, `withdrawn`) are defined once as a set beside `RequestState`. Export from `amoeba.store`.
  - [ ] Success: `uv run pyright` passes.
- [ ] **1.2 Schema 003: the edge rebuild and `requests`** (effort 4)
  - [ ] Create `store/program_schema/003_requests.sql` as the LLD "Database / Storage Schema" gives it: create `edges_new` as 002 defines it with the target check changed to "not both set" and the `wait` check extended by the two new waits; copy, drop, rename and recreate 183's two indexes; then create `requests` (with the `CHECK`s against `RequestState`, `RequestWait` and `RequestFailure`, nullable wait and failure columns) and `requests_by_state`. Raise the program schema's expected-version constant to 3 and update every test that asserts 2 to read the constant.
  - [ ] Tests in `tests/store/test_program_schema.py` (extend): migrating a version-2 store holding edges in every state (open with each wait, satisfied, released, superseded; both target kinds; confirmed and unconfirmed) preserves every row and both indexes; each enum equals its `CHECK` list read from `sqlite_master`; an unbound open edge is accepted; a row with both target columns set is refused; `state = 'failed'` without a failure (and the reverse) is refused.
  - [ ] Success: tests pass.
- [ ] **1.3 `create_request`** (effort 3)
  - [ ] Create `store/program_requests.py`, mixed into `ProgramStore`: `create_request(...)` per D1, in one `BEGIN IMMEDIATE` transaction. It writes the unbound edge through 183's `create_edge` checks (factor the checks out of `create_edge` so both share them; do not copy them) with the mode from `effective_mode`, and the `pending` request. Refuse with `ValueError`, writing nothing, when the checks fail or `asking_slice_label` is blank. SQL and row mapping follow the existing `sql_*.py` / `mapping_*.py` split.
  - [ ] Tests in `tests/store/test_program_requests.py`: a request and its unbound edge appear together, edge `open` and request `pending`; every 183 refusal (different programs, same project, blank need, blank question block) and a blank label write nothing; a failure injected after the edge write leaves neither row; the edge's mode is `effective_mode` for a pair with an override and one without; a second request for the same edge cannot exist.
  - [ ] Success: tests pass; 183's `create_edge` tests pass unchanged.
- [ ] **1.4 Request reads and state writes** (effort 4)
  - [ ] Add to `store/program_requests.py`: reads `requests_providing(project_id, states)` (joining `edges_by_provider`; ordered `created_at` then `request_id`) and `request_for_edge(edge_id)`; writes `record_request_wait` (per D2: only when wait or detail changes, sets `wait_since` with it, returns `False` when unchanged), `mark_running` (sets `slice_set` as JSON, `launch_head`, `run_id`, `journal_entry_id`, clears the wait), `record_reply` (to `replied`, sets `reply_index` and `replied_at`), `fail_request` and `withdraw_request` (set `closed_at`).
  - [ ] Transitions per D2's table; any other raises the store's existing invalid-transition error and writes nothing. `mark_running` and `fail_request` are idempotent in the sense D8 needs: a request already in the target state is left alone and the call reports it.
  - [ ] Tests (same file as 1.3 or a sibling): each legal and each illegal transition; a closed request cannot reopen; `record_request_wait` returns `True` then `False` and `wait_since` does not move on the `False`; `slice_set` round-trips (empty and several indices); order of the provider read; read through `open_read_only` works and cannot write.
  - [ ] Success: tests pass.
- [ ] **1.5 `bind_edge`, the compare-and-set** (effort 3)
  - [ ] Add `bind_edge(request_id, target, at) -> bool` per D10: in one transaction, set `provider_node_id` or `provider_commit` on the request's edge only where the edge is `open` and both are null, and move the request to `bound` (slice target) or `met` (commit target). On any other edge state return `False` and write nothing.
  - [ ] Tests: binds a slice and moves the request to `bound`; binds a commit and moves it to `met`; returns `False`, writes nothing, on a `superseded` edge; returns `False` on an edge already bound; a failure injected between the two writes leaves neither; the asker-side writers (`record_wait`, `mark_satisfied`, `close_edges`, `confirm_release`) still work on a bound edge and leave the target columns alone.
  - [ ] Success: tests pass.

- [ ] **1.6 `member_referenced` over requests** (effort 2)
  - [ ] In `ProgramStore.apply_submission` extend 183's `member_referenced` check (D15): a `register_program` replace that would drop a member any request references, as provider or asker through its edge, in any request state, is rejected `member_referenced` in the same transaction with nothing else written. Add the requests query to the check; add no new rejection code.
  - [ ] Tests in `tests/store/test_program_reject_program.py` (extend): rejected for a provider member and for an asker member, each with a request in every state; a member referenced only by a closed request (`bound`) is still protected; a member referenced only by a request still `running` after its edge was superseded is protected; a replace that keeps every referenced member is applied; nothing else is written on rejection.
  - [ ] Success: tests pass; the rejection-order test still holds, with `member_referenced` last.

**Commit**: `feat: add requests to the program store with schema 003`

## 2. The request node and the `sq_request` entry

- [ ] **2.1 `NodeKind.REQUEST` and `CommandKind.SQ_REQUEST`** (effort 3)
  - [ ] Add `NodeKind.REQUEST` and `CommandKind.SQ_REQUEST` with its required parameter keys (D7: `pipeline`, `params`, `run_id`, `checkout`, `request_id`, `requests_index`, `slice_set`, `target`, `max_cost_usd`, `remote_refs`, `dispatch_check`), each key defined once beside the kind as `sq_answer`'s are. Neither store column has a `CHECK`, so add no migration.
  - [ ] `supervision_entries` drops `sq_request` entries (D3), as it drops `sq_answer`. Confirm by reading that no other reader (`ready_slices`, the orphan rule, `record_finished`) takes the new node kind or kind of entry.
  - [ ] Tests: the required-key set is pinned; `supervision_entries` returns none of a node's `sq_request` entries while still returning its `sq_run` ones; `ready_slices` ignores a `request` node; the orphan rule ignores it; the journal's kind round-trips.
  - [ ] Success: tests pass.
- [ ] **2.2 `begin_request_run` and `finish_request_run`** (effort 4)
  - [ ] Create `store/request_run.py`, mixed into `Store`: `request_node_id(request_id)` (one derivation, used everywhere), `begin_request_run(*, project_id, request_id, title, parameters)` creating the `request` node (`in_progress`, no parent, no CF link, the D3 title) and journaling the `sq_request` entry against it in one transaction, refusing parameters that miss a required key; and `finish_request_run(entry_id, result)` resolving the entry and setting the node `done` in one transaction.
  - [ ] Tests `tests/store/test_request_run.py`: node and entry appear together; a missing required key raises and writes nothing; a failure injected after the node write leaves neither; the node id is a function of the request id only; finishing resolves the entry and sets `done` together; finishing twice is refused as the journal's existing rule refuses a second resolution; a PM resolution of a block on a request node is acknowledged with no continuation (D3: add this case to the resolution planner's tests).
  - [ ] Success: tests pass.
- [ ] **2.3 Recovery observer for `sq_request`** (effort 3)
  - [ ] Register the by-id `sq` observer for `sq_request` exactly as `sq_answer` registers it, with no legacy matcher (D8). An existing run is left in flight. An entry recovery resolves `not_applied` or `unknown` is left resolved for the stage to see.
  - [ ] Tests extend the recovery tests: an unresolved `sq_request` entry whose run exists is left in flight; one whose run is unknown to `sq` past the launch grace resolves `not_applied`; inside the grace it is left alone.
  - [ ] Success: tests pass.

**Commit**: `feat: add the request node and the sq_request journal kind`

## 3. Band, checkout hold and readiness

- [ ] **3.1 `program/band.py`** (effort 3)
  - [ ] Create `program/band.py` (the `amoeba.program` package, importing only `amoeba.store` and `amoeba.upstream`): `BAND_WIDTH` and the 799 ceiling as constants; frozen `Open(next_index)`, `Full`, `Collision(index)` with `type BandState`; and `requests_band(nodes, requests_index)` per D4, pure. `next_index` follows 180's index rule (the requests index when the initiative has no linked slices, else one more than the highest).
  - [ ] Purity: in the test file add `assert io_use(band) == []`, with `io_use` from `tests/runner/purity.py`.
  - [ ] Tests `tests/program/test_band.py`: no initiative gives `Open(requests_index)`; slices at the first and several indices give the next; the last index inside the band is `Open`, the next is `Full`; the 799 ceiling truncates the band; a linked initiative other than the requests initiative inside the band gives `Collision` naming its index, and one outside the band does not; the purity check passes.
  - [ ] Success: tests pass; `tests/test_import_boundaries.py` passes.
- [ ] **3.2 `checkout_holds` and the request-run exemption** (effort 4)
  - [ ] In `runner/dispatch/hold.py` add `CheckoutHold(in_flight, stopped)` and `checkout_holds(entries, done) -> Mapping[Path, CheckoutHold]` per D5. `in_flight` holds the nodes with an unresolved `sq_run` or `sq_request` entry in the checkout; `stopped` holds 132's paused, failed and orphaned nodes. `checkout_holders` becomes the union of the two so `DispatchPlanner` and `ContinuationPlanner` are unchanged. Add a small pure helper, beside it, that says whether a request run may launch in a checkout (`in_flight` empty).
  - [ ] Tests extend `tests/runner/dispatch/test_hold.py`: each of 132's existing cases yields the same `checkout_holders`; an unresolved `sq_request` entry is an in-flight holder and blocks `DispatchPlanner` from launching a slice in that checkout; a stopped node alone leaves `in_flight` empty and the helper true; an in-flight run and a stopped node together make the helper false; two checkouts are independent.
  - [ ] Success: tests pass; every existing hold and planner test passes unedited.
- [ ] **3.3 `ProgramReadiness`, replacing `waiting`** (effort 4)
  - [ ] Create `runner/lifecycle/readiness.py` with frozen `ProgramReadiness(waiting, membership_driven, standalone_initiatives)` and `EMPTY`, per D12. It imports nothing from `runner/program` or the program store. Replace 183's required `waiting` argument with a required `readiness: ProgramReadiness` on `ready_slices`, `current_slices` and `build_project_view`. `tick.py` builds the value for now from `ProgramView.waiting` and `ProgramView.providing` as `ProgramReadiness(waiting=<waiting>, membership_driven=<providing>, standalone_initiatives=frozenset())`; Task 6.9 moves that construction into the program stage. Update every caller and fixture (`grep -rn "ready_slices\|current_slices\|build_project_view\|waiting=" src tests`).
  - [ ] Tests: the existing `waiting` tests pass with the wrapped value; `EMPTY` behaves as an empty `waiting`; the value is frozen; an import-boundary rule in `tests/test_import_boundaries.py` fails if `amoeba.runner.lifecycle` or `amoeba.runner.intent` imports `runner/program` or a program-store module, directly or transitively (confirm it fails on a deliberate import, then revert it).
  - [ ] Regression: Task 0.2's baseline test passes unedited.
  - [ ] Success: `uv run pytest tests/runner tests/test_import_boundaries.py` passes; `uv run pyright` passes.
- [ ] **3.4 No implicit predecessor and membership drive** (effort 3)
  - [ ] In `runner/lifecycle/predecessors.py`, `slice_predecessor` returns `None` for a slice whose initiative node id is in `standalone_initiatives` (D12). In `runner/intent/governance.py`, `governing` makes a slice in `membership_driven` driven whatever its drive rows say; `held` is unchanged, so a hold row on its path still stops it.
  - [ ] Tests extend `tests/runner/lifecycle/test_ready_slices.py` and `tests/runner/intent/test_governing.py`: a second slice in a standalone initiative is ready while the first is not done, and still ready after the first is done; a slice in an ordinary initiative keeps its predecessor; a membership-driven slice is current with no drive row; a membership-driven slice with a hold row on its slice, its initiative and a higher path node is not current; a slice not in the set is unchanged.
  - [ ] Success: tests pass.
- [ ] **3.5 Request priority in the sort key** (effort 3)
  - [ ] In `runner/dispatch/facts.py` change `SortKey` to `(priority, initiative index, slice index)`. In `dispatch/build_view.py` set `priority` to `0` for a node in `membership_driven` and `1` otherwise (priority values defined once as constants). `DispatchPlanner` is unchanged.
  - [ ] Tests extend `tests/runner/dispatch/`: a membership-driven slice in a later initiative sorts ahead of a planned slice in an earlier one in the same checkout; two membership-driven slices keep initiative-then-slice order; with no membership-driven slice the order equals the old order (parametrize over the existing ordering cases); a stopped first request slice holding its checkout leaves a second ready but not launched (D13's runtime-independence caveat, pinned by test).
  - [ ] Success: tests pass; Task 0.2's baseline test passes unedited.

**Commit**: `feat: add the requests band, the request-run hold, and membership-driven priority`

## 4. Configuration and start-up

- [ ] **4.1 `RequestSettings` in `projects.yaml`** (effort 3)
  - [ ] In `runner/project_config.py` add frozen `RequestSettings(model, max_cost_usd)` and `ProjectSettings.requests: RequestSettings | None`, loaded per D14 the way the `answerer` section is. `model` is stripped, non-blank, with no `,`. `max_cost_usd` is a number above zero (a bool is not a number). `requests: {}`, a null section, a missing key or an unknown key fails the load naming the key path, for example `projects.<id>.requests.model`. Neither key has a default. `project_config.py` is 234 lines before this task: if the section's loader leaves it past ~300 lines, put `RequestSettings` and its loader in a sibling module that `project_config.py` imports.
  - [ ] Tests extend `tests/runner/test_project_config.py`: a valid section loads; no section loads as `None`; each failure case above names the path; a model with a comma fails; zero, negative and `true` fail for the cost; a real-format `projects.yaml` file fixture (written as a user would) loads.
  - [ ] Success: tests pass.
- [ ] **4.2 Start-up probe wiring** (effort 3)
  - [ ] Where start-up runs 120's `sq` probes, call 180's `probe_slice_writing_pipeline` once when any project has a `requests` section, and not otherwise (D14). A failure exits `STARTUP_FAILED` naming the command, as the existing probes do.
  - [ ] Tests: a config with a `requests` section runs the probe once; a config with none never calls it; a failing probe exits `STARTUP_FAILED` with the command in the message; two projects with sections still run it once.
  - [ ] Success: tests pass; the existing start-up tests pass.

**Commit**: `feat: add the requests configuration section and wire the slice-writing probe`

## 5. Plan reads that bind

- [ ] **5.1 `mark_due` and `read_completed_since`** (effort 3)
  - [ ] In `runner/lifecycle` or wherever `PlanStage` and `PlanReadSchedule` live (read them first), add D9's two operations: `PlanStage.mark_due(project, link)` makes that link read on the next tick regardless of the read interval, and `PlanReadSchedule` records the start time of each complete read so `read_completed_since(project, link, at)` is true only when a read that started at or after `at` completed. A read that failed never counts. After a restart the schedule is empty and the first complete read satisfies the check.
  - [ ] Tests extend the plan-stage tests with an injected clock: a due link is read next tick although the interval has not elapsed; a read that started before `at` does not satisfy it and one that started after does; a failed read does not; an empty schedule after restart is satisfied by the first complete read; an unmarked link keeps its interval.
  - [ ] Success: tests pass; every existing plan-stage test passes unedited.

**Commit**: `feat: let the plan stage mark a link due and report fresh reads`

## 6. The request run

- [ ] **6.1 Test rig for request runs** (effort 3)
  - [ ] Create `tests/runner/request_run/` with a support module: two scratch member stores and a program store with a program whose provider is configured with `requests` settings; a scratch provider repo from `tests/runner/git_repo.py` on a target branch; a stub `sq` (extend the existing fake `sq` rather than writing a second) that accepts the request argv, writes `reply.json` into the I/O directory per scenario (`new_slice`, `already_met`, malformed, missing) and exits `completed` or failed per scenario; a stubbed `cf` for the plan read; and a helper that calls `create_request`. Support also a recording git runner so tests can count calls.
  - [ ] Success: a smoke test creates a request, runs the stub `sq` once by hand, and reads back the reply file it wrote.
- [ ] **6.2 `bind.py`** (effort 3)
  - [ ] Create `runner/request_run/bind.py`, pure: `decide_binding(request, tree, fresh)` per D9, returning a bind of `ProvidingSlice(node_id)`, a wait `awaiting_plan_read`, or a `binding_failed` naming which part failed (absent, already in the launch slice set, outside the band).
  - [ ] Purity: `assert io_use(bind) == []` in its test file.
  - [ ] Tests `tests/runner/request_run/test_bind.py`: not fresh waits; fresh with a new slice at `reply_index` under the initiative at the requests index binds with its node id; index absent fails with that reason; index in `slice_set` fails with that reason; index outside the band fails with that reason; a slice at the index under a different initiative does not bind; the purity check passes.
  - [ ] Success: tests pass.
- [ ] **6.3 `request_argv`** (effort 2)
  - [ ] Create `runner/request_run/launch.py` with `request_argv(pipeline, requests_index, run_id, io_dir, max_cost_usd, model)` per D7, built from 180's constants. It is the only place the argv is spelled.
  - [ ] Test: one test pins the provisional form, with a comment that it changes with 180's finalization against the shipped Squadron syntax.
  - [ ] Success: test passes.
- [ ] **6.4 Launch: the checks before the journal** (effort 4)
  - [ ] In `runner/request_run/launch.py` implement D7 steps 1 to 4 as one function returning a launch plan, a wait or a failure and writing nothing to the journal: `RequestSettings` or wait `requests_unconfigured`; the checkout (`resolve_checkout` at the member's requests index, failing as wait `unreadable`); D4's band check from the provider's store (`Full` or `Collision` fail the request); D5's hold (`checkout_in_use` naming the holder); the edge still open (else `withdrawn`); then `checkout_reads` and the fresh-launch rule, whose `Block` becomes wait `checkout_branch` or `checkout_dirty` with the first paths and the count, and whose `Ok` evidence is kept as `dispatch_check`; then D16's one `git_read` of `for-each-ref --format=%(refname) %(objectname) refs/remotes`, kept as `remote_refs` (a failed read is wait `unreadable`). Add `for-each-ref` to the `git_read` allowlist with a test. A budget refusal returns a stop value and leaves the request `pending`. Waits are recorded with `record_request_wait`.
  - [ ] Tests `tests/runner/request_run/test_launch_checks.py` (git-backed with the rig): each wait and failure with its detail; first match wins when two apply; a stopped (paused, failed, orphaned) node alone does not block a clean tree on the target; an in-flight run blocks with `checkout_in_use`; a detached head, another branch, and a dirty tree each wait with the right reason; a superseded edge withdraws; for every wait above (including `checkout_in_use` and each checkout wait over a node with a paused run), no block, state change or journal entry is written for any provider node, only the request row; call counts: no git for a store-only reason, exactly two (`git status`, `cf config get`) when the checks reach the checkout; a refused budget returns the stop value and runs no git.
  - [ ] Success: tests pass.
- [ ] **6.5 Launch: directory, journal, spawn** (effort 5)
  - [ ] In `launch.py` implement D7 steps 5 to 7: exclusive `mkdir` of `<supervisor_dir>/requests/<run_id>/` (`mint_run_id`; the path derived from the run id by one function, not stored), 180's `prepare_request_directory`, D16's `pre-push` hook at `<run dir>/git-hooks/pre-push` (executable, prints that request runs may not push, exits 1), the argv, `begin_request_run` with every required key, then the program store's `mark_running` with the slice set (sorted CF indices of the linked slices under the requests initiative) and launch head, then `launch.spawn` from the checkout with D16's environment overlay (`GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0=core.hooksPath`, `GIT_CONFIG_VALUE_0=<hook dir>`), the existing launch logs, `run_id=` confirmation and grace. An `OSError` before the journal fails the request `launch_failed` and removes the directory. A spawn failure resolves the entry `failed`, sets the node `done` and fails the request `launch_failed` in the same tick.
  - [ ] Tests `tests/runner/request_run/test_launch.py`: a launch writes the node, the entry (all keys, `dispatch_check` included), the `running` request with the slice set and head, and spawns once; the directory holds `need.md` and is left after the run; an unwritable supervisor directory fails `launch_failed` with nothing journaled; a spawn failure ends with the entry resolved, the node `done` and the request `launch_failed`; the cost cap is journaled as `max_cost_usd`, separate from `params`; the entry carries the launch's `remote_refs`; a failed listing read is wait `unreadable` with nothing journaled; the hook exists, is executable and exits 1; the spawn gets the three `GIT_CONFIG_*` variables on top of the inherited environment.
  - [ ] `launch.spawn` gains an optional environment overlay, default none; with none the child's environment is the inherited one, as today. Test: an existing launch path's spawn call is unchanged, and an overlay reaches the child merged over the inherited environment.
  - [ ] A real-git test in a throwaway repo with a bare remote: with the overlay set, `git push` fails and the remote is unchanged.
  - [ ] Success: tests pass.
- [ ] **6.6 Finish: observing the run and recording a new-slice reply** (effort 3)
  - [ ] Create `runner/request_run/finish.py` per D8. Poll each unresolved `sq_request` entry with `RunObserver.poll_run` under the budget and `--run-poll-interval`. First, an entry whose request is still `pending` is recorded `running` from its parameters. A run Squadron does not know is left to recovery, and a request whose entry recovery resolved `not_applied` or `unknown` fails `run_lost`. For every finished run, first apply D16: read the remote-ref listing once with `git_read`; a failed read leaves the request `running` with wait `unreadable` and the entry unresolved; a listing that differs from the entry's `remote_refs` fails `remote_refs_changed` with the first changed refs in the detail, without reading the reply. For a finished run, write the program store first, then resolve the entry and set the node `done` with `finish_request_run` and the result `{run_id, run_outcome, reply_kind, request_state}`. Outcomes per D8's table, except `AlreadyMet` (Task 6.7): not `completed` fails `run_failed` with the failure kind and 4 KiB tail (a pause included) without reading the reply; a `ReplyProblem` fails `reply_missing` or `reply_malformed`; `NewSlice` records the reply and calls `PlanStage.mark_due`.
  - [ ] Tests `tests/runner/request_run/test_finish.py` (rig and stub `sq`): each of those rows with its detail; changed remote refs fail `remote_refs_changed` for a `completed` new-slice reply and for a failed run alike, and the reply is not read; a failed listing read retries next tick and then finishes; the provider's link is marked due only on `new_slice`; an unknown run before and after recovery, in both tick orders, ends `run_lost` and never `run_failed`; a crash between the program-store write and the entry resolution is finished again on the next tick with no second write; a pending request with an unresolved entry is recorded `running` and never launched again.
  - [ ] Success: tests pass.
- [ ] **6.7 Finish: the already-met head check and supersession** (effort 3)
  - [ ] In `finish.py` add the `AlreadyMet` row of D8. Read the head once with `git_read` (`log -1 --format=%H <target>`) in the checkout. If it equals `launch_head`, bind the edge to `ProvidingCommit` and the request goes `met`; otherwise fail `head_moved` naming both heads. A failed read leaves the request `running` with wait `unreadable` and the entry unresolved. A `False` from `bind_edge` withdraws the request. A request whose edge was superseded while `running` finishes the run and then goes `withdrawn` with the reply recorded (D10).
  - [ ] Tests (same file as 6.6): an unchanged head binds the commit and the request is `met`; a moved head fails `head_moved` naming both heads; a failed read retries next tick and then finishes; a supersession race (`bind_edge` returns `False`) leaves the request `withdrawn`; a run superseded while running finishes and is withdrawn with the reply recorded; call counts: two git calls to finish an already-met run (the D16 listing, then the head) and one for any other outcome.
  - [ ] Success: tests pass.
- [ ] **6.8 The request stage** (effort 4)
  - [ ] Create `runner/request_run/stage.py`, per the LLD Data Flow, for requests whose provider is this project: (1) observe and finish, (2) bind each `replied` request using `decide_binding` with `read_completed_since` from the request's `replied_at`, withdrawing it if its edge closed, (3) launch the oldest `pending` request only when none is `running` or `replied` (D6), recording `checkout_in_use` naming the request ahead on the others. A `False` from `bind_edge` withdraws. A budget refusal stops launching for the tick. Evaluation is oldest first, and the stage returns whether it wrote.
  - [ ] Tests `tests/runner/request_run/test_stage.py`: two pending requests launch the older only and the second waits `checkout_in_use` naming the first; the second stays blocked while the first is `replied`, and launches the tick after it is bound; a `replied` request waits `awaiting_plan_read` until a fresh read, then binds when the slice is present and fails `binding_failed` when not; a supersession withdraws a `pending` request without launching it, and withdraws a `replied` request with no binding; an unchanged wait writes nothing; with no requests the stage writes nothing and reads only the program store.
  - [ ] Success: tests pass.

**Commit**: `feat: add the request run stage with launch, finish and binding`

- [ ] **6.9 The stage in the tick, and the filled `ProgramView`** (effort 4)
  - [ ] In `runner/program/stage.py` add `readiness: ProgramReadiness` to `ProgramView` and fill it (D12): `waiting` as 183 does, `membership_driven` from `providing`, and `standalone_initiatives` as the node id of the initiative at the member's `requests_initiative` when that node exists. Replace Task 3.3's interim construction in `tick.py` with the stage's `readiness`.
  - [ ] Extract before wiring the stage: `runner/tick.py` is already over ~300 lines (311 before 181 and 183 add to it). Move `_launch_context` to a sibling module and re-run `tests/runner` (a pure move, no behavior change), so the request stage's wiring lands outside `tick.py` (LLD Special Considerations).
  - [ ] Then call the request stage in `ProjectTick.run` after plan reads and the recording of finished `sq_run` runs, and before the answering stage and the view (LLD Data Flow), so a launched request run is an unresolved entry when `checkout_holds` is computed. Put the request counterpart of `_launch_context` in the same sibling module.
  - [ ] Tests `tests/runner/request_run/test_tick_stage.py`: a pending request and a ready planned slice in one tick: the request run launches and the planned slice does not; a request slice with an open edge is membership-driven and launches ahead of a ready planned slice; a PM hold on its path stops it; a second request slice is ready while a stopped first one holds the checkout and launches when it is free. Regression: tick one scripted project with no program store, with a program store holding an unrelated program, and with a member that has no requests: store writes, issued commands and journal entries are identical across the three (extend 183's regression), and Task 0.2's baseline test passes unedited.
  - [ ] Success: tests pass; `uv run pytest tests/runner` passes.

**Commit**: `feat: run the request stage in the provider's tick and drive request slices by membership`

- [ ] **6.10 Crash points** (effort 3)
  - [ ] In `tests/runner/request_run/test_crash_points.py` kill the launch at each point: after the provider-store journal and before the program-store `running` write, and after that write and before the spawn. In both cases the next tick records the request `running` from the entry, recovery resolves it `not_applied`, and the request fails `run_lost` with no second launch. Add a restart with a spawned run in flight: the stage adopts it and no second run launches.
  - [ ] Success: tests pass; the stub `sq` was started at most once in each test.

**Commit**: `test: prove request runs are adopted or failed across a restart`

## 7. Asker side and listings

- [ ] **7.1 Observing an unbound edge** (effort 3)
  - [ ] In `runner/program/observe_edges.py` check first, before 183's table (D11): an unbound edge whose request is `pending`, `running` or `replied` is wait `request_open` with the request's state and wait as detail; one whose request is `failed` is `request_failed` with the failure and its detail. The request is one program-store read, with no git, `cf` or member store opened. Define both detail formats once as constants in a new module, `program/request_text.py` (`amoeba.program` is importable from the runner and from inspection); tests import them.
  - [ ] Tests extend `tests/runner/program/test_observe_edges.py`: each of the two waits with its detail; a request that is `bound` or `met` leaves the edge to 183's rules; precedence over `provider_unreadable`; no git, `cf` or member-store call (recording runner); the asking slice stays in `waiting` across `request_open`.
  - [ ] Success: tests pass.
- [ ] **7.2 Supersession closing a request** (effort 3)
  - [ ] Confirm 183's supersession (PM resolution on the question block closes the edge `superseded`) already runs in the asker's tick, and add a test-only chain that the provider's request stage then withdraws a `pending`, `running` or `replied` request per D10. Add no second supersession path.
  - [ ] Tests `tests/runner/request_run/test_supersession.py`: a PM resolution before launch withdraws the request and nothing launches; during the run the run finishes and the request is `withdrawn`; the slice it wrote is a plain planned slice, not membership-driven (no open edge names it), and sorts with planned work.
  - [ ] Success: tests pass.
- [ ] **7.3 Request rows on `program-blocked`** (effort 3)
  - [ ] Define the `request` blocked-on kind once beside 183's `edge` kind in `inspection/program.py`, and the title and reason formats once in `program/request_text.py` (Task 7.1's module). In `inspection/program.py` add one row per request in `pending`, `running`, `replied` or `failed` whose edge is still open (D15): provider as `project_id`, the request node id as `node_id` (empty before launch), `blocked_on` `request`, empty `blocked_state_id`, `reason` `"<state>: <wait or failure>: <detail> (since <wait_since>)"`. A failed request whose edge closed is not listed. With no program store, no request rows. Inspection stays read-only and makes no subprocess.
  - [ ] Tests extend `tests/inspection/test_program.py`: a row for each listed state; a failed request with an open edge is listed and the asker's `edge` row shows `request_failed` beside it; a failed request whose edge was superseded is absent; `bound` and `met` are absent; the title and reason come from the constants the tests import; 181's and 183's rows are unchanged; works with the process stopped and writes nothing; tests that enumerate blocked-on kinds are updated.
  - [ ] Success: tests pass.

**Commit**: `feat: observe unbound edges and list request runs on program-blocked`

## 8. Scenario, locality and docs

- [ ] **8.1 Two-project scenario: the main path** (effort 5)
  - [ ] Create `tests/runner/request_run/test_request_scenario.py` using the rig: two scratch member stores, a scratch provider repo, the stub `sq` whose "agent" appends a slice entry to the plan and commits, a stubbed `cf`. Honor `AMOEBA_KEEP_SCENARIO_DIR` through the scenario support 183 added (its value is the path to keep the supervisor directory in), and print that path (LLD walkthrough step 1).
  - [ ] Main path, one test: the provider has a paused planned slice on a clean target and the request run launches anyway, without resuming the paused slice while the run is in flight; the reply is `new_slice`; the next plan read shows the slice and the edge is bound; the following tick launches the request slice's pipeline ahead of a ready planned slice in the same checkout; the asker's edge row moves from `request_open` to `provider_not_done`.
  - [ ] Success: the test passes.
- [ ] **8.2 Two-project scenario: variants** (effort 3)
  - [ ] In the same module, one test per variant: `already_met` with an unchanged head (`met`, edge on the commit) and with a moved head (`head_moved`); the asker is released only by 183's observation, not by the binding: after `met` the edge is still `open` and the asking block unresolved, and the asker is released only on the tick where 183's observation returns satisfied (183's own tests cover its reachability rules); a malformed reply; a full band (`requests_initiative_full`); in each failure the request row and the asker's `request_failed` edge row both appear on `program-blocked`.
  - [ ] Success: all pass; `tests/runner/request_run` passes as a directory.

**Commit**: `test: prove request runs across two projects with a stub sq`

- [ ] **8.3 Locality proof and writer guard** (effort 3)
  - [ ] Add `requests` to the program store's allowed table set in `tests/contract/oracle.py` (`locality_problems`), extend the scenario so a request exists when the proof runs, and make the proof's table list follow. Add a check that the `request` node and `sq_request` entries live only in project stores (D3 and the LLD's locality rule: the program store has no journal).
  - [ ] Negative test in `tests/contract/test_oracle.py`: a `request` node or journal table added to a scratch program store makes the proof fail naming the table. Confirm `tests/test_writer_guard.py` passes: requests and `bind_edge` are written only through the host's `ProgramStore`, and the `Store` request-run writers only through the runner.
  - [ ] Success: `uv run pytest tests/contract tests/test_writer_guard.py` passes.

**Commit**: `test: extend the locality proof to requests`

- [ ] **8.4 Load case for a request-bearing tick** (effort 3)
  - [ ] Read `tests/load/test_program_load.py` (181's, extended by 183) and `tests/load/load_harness.py`, then add one case there in the same style: a provider member with many `pending` requests behind one `running` request, and other members with none, ticked under the real tick budget. Assert the tick stays within the bound the file already uses, that the requests behind the running one cost only store reads (no git or `cf` call), and that a member with no requests costs one program-store read.
  - [ ] Success: the case passes and the file's existing bounds are unchanged.

**Commit**: `test: add a request-bearing tick to the program load test`

- [ ] **8.5 `docs/store-contract.md` and `docs/inbox-contract.md`** (effort 2)
  - [ ] In `docs/inbox-contract.md`, "Program submissions": `member_referenced` is now also produced for requests. State that a request has no inbox path.
  - [ ] In `docs/store-contract.md` add the `requests` table, the `edges` rebuild and the new waits, the request states and transitions, the `bind_edge` writer as the third, column-disjoint writer on `edges` (amend 183's "no third writer" statement), the `request` node kind, `sq_request` with its required keys, the updated locality set, and the program schema line now at 3.
  - [ ] Success: each LLD "API Contracts" method appears; no claim contradicts the code; the inbox text matches `apply_submission`.
- [ ] **8.6 `docs/process-contract.md`** (effort 3)
  - [ ] Describe the request stage and its place in the tick, the checkout rule and the request-run exemption, `sq_request` and its recovery story (the two crash windows and `run_lost`), readiness (`ProgramReadiness`, no implicit predecessor), membership drive and request priority including D13's runtime-independence caveat, the `requests` section and probe wiring, the request waits and failures, D16's push guard (the hook through the launch environment, its side effect on the provider's hooks, and the remote-ref comparison), and every request-side git and `cf` read with its call count.
  - [ ] Success: the stage's place and the read counts match `ProjectTick.run` and the code.

**Commit**: `docs: document request runs in the store, inbox and process contracts`

## 9. Final validation

- [ ] **9.1 Full checks** (effort 1)
  - [ ] Run `uv run ruff format .`, `uv run ruff check .`, `uv run pyright` and `uv run pytest` (the bare run, which excludes the live and load tiers).
  - [ ] Run the existing load tests as regression checks by explicit path: `uv run pytest tests/load/test_runner_tick_load.py tests/load/test_inbox_concurrent.py tests/load/test_program_load.py`. The bounds must hold without edits.
  - [ ] Success: all pass, with no existing test skipped, weakened or edited to pass, apart from the version-constant, `readiness`-argument, `SortKey`, hold, blocked-on-kind and `EdgeWait` updates Tasks 1.1 to 3.5 and 7.3 name. If a check fails, fix its cause and re-run.
- [ ] **9.2 Verification walkthrough** (effort 3)
  - [ ] Run the LLD "Verification Walkthrough" with `AMOEBA_KEEP_SCENARIO_DIR` set to a `mktemp -d` path, never the real supervisor directory. The LLD's step 1 shows the variable set to `1`; use the path instead, as 183's tasks do. Step 2 runs `AMOEBA_STORE_DIR=<kept dir> amoeba inspect program-blocked` against the kept directory.
  - [ ] Success: each step shows what the LLD says, including `request` rows beside the asker's `edge` rows; any difference is fixed in code, and the closing report says what each step showed. After any fix, re-run Task 9.1's checks. Delete the throwaway directory when done.

Write no walkthrough note into this file. If a step needed a code fix, commit it at the marker below.

**Commit**: `fix: correct what the request-runs walkthrough found` (only when a step needed a code fix; use `test:` when only tests changed)

- [ ] **9.3 CHANGELOG** (effort 1)
  - [ ] Under `[Unreleased] / Added`, one or two lines for slice 184 in the existing style: requests and the request run, the `requests` configuration section, request priority and membership drive in the requests initiative, request rows on `program-blocked`. Note that nothing creates a request yet.
  - [ ] Success: entry present, concise.

**Commit**: `docs: add slice 184 to the changelog`
