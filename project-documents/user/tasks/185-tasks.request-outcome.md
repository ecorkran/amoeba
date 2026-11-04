---
docType: tasks
slice: request-outcome
project: amoeba
lld: user/slices/185-slice.request-outcome.md
dependencies:
- 141
- 142
- 144
- 181
- 182
- 183
- 184
projectState: Initiatives 100, 120 and 140 are complete and merged. Slices 181 to
  184 (program coordination) are designed and tasked. Per the LLD's Prerequisites,
  185 starts only after 184 merges, and Task 0.1 verifies that against the code. Nothing
  yet creates a request or an edge in a live project. `ProposedRequest`, `Requested`,
  `request_facts.py`, `request_writes.py`, `QuestionState.REQUESTED`, migration 017
  and `AnswererSettings.request_limit` do not exist.
dateCreated: 20261104
dateUpdated: 20261104
status: not_started
turns: 17
promptTokens: 554101
cachedTokens: 475080
cacheWriteTokens: 79003
completionTokens: 17499
durationSeconds: 116.2
costUsd: 0.538843
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.5388429
    completionTokens: 17499
---

## Context Summary

- Working on the **request-outcome** slice (185), the sixth slice of initiative 180 (program coordination). It gives 140's answering run a third outcome: a **request** for a named program member. A confirmed request passes a request gate, then three idempotent writes (entry resolved, request and edge created, record moved to `requested`), finished by the stranded sweep after a crash.
- **Current state:** see `projectState`.
- **Dependencies:** 141, 142, 144 (question record, answer gate, answering run); 181 (`ProgramStore`, `read_member`, the tick's `Program | None`); 182 (`ProgramContext`, program passages, instruction sentences); 183 (edges, `edges_waiting`, `RELEASABLE_STATES`, release, supersession); 184 (`create_request`, `requests_band`, `BandState`, `request_for_edge`, `ProjectSettings.requests`).
- **What this slice delivers:** the `requested` question state and migration 017; `request_limit` in the `answerer` config; `ProposedRequest` and `Requested`; `create_request(request_id=...)` idempotent plus `live_request_count` and `edges_provided_by`; `request_facts.py`; `evaluate_request_gate`; `request_writes.py`; the finish branch, sweep and `RequestContext`; the `program_requests` passage; both steps' instructions; the `requested` listing; contract docs and CHANGELOG.
- **This slice turns coordination on.** Before it nothing in a live project creates an edge or a request. A project in no program must behave exactly as before.
- **Next planned slice:** 186 (live walkthrough).

**Branch:** read the target (`cf config get git.integration_branch`; empty means `main`). Before Task 0.1, create `185-slice.request-outcome` from the target and work there. No task merges or pushes. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/185-slice.request-outcome.md` at the named decision (D1 to D12) or section. Source paths are relative to `src/amoeba/` unless they start with `tests/`, `docs/` or `project-documents/`. Follow `.claude/rules/python.md`, `.claude/rules/sql.md` and `.claude/rules/testing.md`: ruff and strict pyright, no silent fallbacks, every `try/except` justified. Read each file before editing it. Keep source files near 300 lines and functions near 50. Every vocabulary value is defined once and imported by its tests, never repeated as a literal. Where 182's, 183's or 184's code differs in name or shape from their designs, follow the code and use its names throughout.

**Order:** work tasks in file order. No task needs a model, a key, live CF or a real `sq`; scenarios use test-written stores, temporary git repositories (`tests/runner/git_repo.py`) and the stub `sq` (`tests/sq_stub.py`, `tests/sq_stub_scripts.py`).

**Commit cadence:** commit only at the `**Commit**:` markers. Run `uv run ruff format .` before each commit, and `uv run ruff check .` and `uv run pyright` before markers that follow Python changes.

---

## 0. Preflight

- [ ] **0.1 Confirm the prerequisite code exists and record its real names** (effort 3)
  - [ ] This task checks the LLD's Prerequisites (185 starts after 182, 183 and 184 merge). It adds no wait of its own.
  - [ ] Create the branch (see Branch above). Then read, and change nothing, to confirm each of these is on the target:
    - [ ] 181: `ProgramStore` (`open`, `open_read_only`, `members`), `read_member` and its `Readable` result, each member's `requests_initiative`, the tick's `Program | None`, `RunnerHost.program_store`.
    - [ ] 182: `ProgramContext`, `program_passages.py`, `program_sources.py`, `PassageKind` program kinds, the passage order and size rule, the `member` render line, and the instruction sentences 182 added to `answering.yaml`. Note where `ProgramContext` is built per tick and passed to `AnsweringStage` and `assemble_sources` (Task 6.4 builds `RequestContext` beside it).
    - [ ] 183: `store/program_edges.py` (`create_edge`, `edges_waiting`, and the provider-side reader, which the LLD and 183's design call `edges_providing` (open edges only) while 184's tasks call it `edges_by_provider`, 183's index name: confirm which function exists; Task 4.2's `edges_provided_by` copies its ordering), `Edge`, `EdgeState`, `submit_release`, `RELEASABLE_STATES` and where it is defined, supersession, and the edge row on `program-blocked`.
    - [ ] 184: `store/program_requests.py` (`create_request`, `request_for_edge`), `Request`, `RequestState`, `program/band.py` (`requests_band`, `BandState` with `Open`, `Full`, `Collision`), `ProjectSettings.requests`, and the stub request-run pieces under `tests/runner/request_run/`.
    - [ ] Project schema numbering: 183 added `store/schema/016_slice_heads.sql`, so 017 is the next free number (Task 1.2). If the highest file on the target is not 016, use the next free number in its place and record it as `017 → <number>`.
    - [ ] Load tier: `tests/load/test_program_load.py` and `tests/load/load_harness.py` exist (CI already runs `tests/load`; Task 10.4 extends the first).
    - [ ] 140: in `runner/answering/` the files `artifacts.py`, `decide.py`, `finish.py`, `gate.py`, `settle.py`, `stage.py`, `passages.py`, `answering.yaml`; in `store/` `questions.py`, `question_models.py`, `schema/015_answering_run.sql`; `QUESTION_TRANSITIONS`, `_OPEN_STATES` and `COUNT_ANSWERER_ANSWERS_IN_RUN` (find each by grep); `runner/project_config.py` `AnswererSettings`; `inspection/questions.py`; `_settle_question_on_acknowledgment`.
  - [ ] For each name whose code form differs from the LLD, add one line under this task, `LLD name → code name`. Later tasks use the code names. Do not edit the other slices' designs, except the two amendments Task 10.5 names.
  - [ ] Success: each name was found by reading the code, not assumed. If code from slice 181, 182, 183 or 184 is absent from the target, write `BLOCKED: slice <n> code is absent from the target` under this task, leave it unchecked, and stop. Slice 140's code is on the target already, so a name missing from it is a mismatch to record, not a block.
- [ ] **0.2 Confirm the no-program baselines pass** (effort 1)
  - [ ] Run two baselines unedited: 183's tick baseline (`tests/runner/program/test_tick_baseline.py`) and 182's answering baseline (`uv run pytest tests/runner/answering/test_sources.py -k baseline`, 182's Tasks 0.2 and 7.1). They pin a project in no program: passages, `cf` and git calls, store writes, issued commands and journal entries. They must pass now and again at Task 11.1.
  - [ ] Success: both pass. If either does not exist, write `BLOCKED: slice <n> code is absent from the target` under this task, leave it unchecked, and stop. Do not create it here: a baseline taken from code that already includes 185's changes would pin the wrong behavior.

## 1. The question record

- [ ] **1.1 The `requested` state, its transitions and the new decline reasons** (effort 2)
  - [ ] In `store/question_models.py` add `QuestionState.REQUESTED` (`QuestionOutcome.REQUESTED` is separate and comes in Task 6.3). Add `answering → requested` and `requested → answered` to `QUESTION_TRANSITIONS`, per D9. `requested` has no transition to `declined`. Add the eight new `DeclineReason` values the LLD's API Contracts list (`REQUEST_OUTSIDE_PROGRAM` to `REQUEST_BACK_TO_WAITING`).
  - [ ] Tests (extend `tests/store/test_question_records.py`): the transition table has each legal move and refuses `requested → declined`, `requested → answering` and `pending → requested`.
  - [ ] Success: tests pass; `uv run pyright` passes.
- [ ] **1.2 Migration 017 and `request_id` on the record** (effort 2)
  - [ ] Create `store/schema/017_question_request.sql` per the LLD "Database / Storage Schema" (one nullable column, no foreign key, no `CHECK`). Add `request_id: str | None` to `QuestionRecord` (a frozen dataclass whose fields have no defaults, so every direct construction breaks) and to its row mapping. Find every `QuestionRecord(` call with grep, today `store/mapping_questions.py` and `tests/runner/answering/test_settle.py`, and pass `request_id` explicitly in each. Raise the project schema's expected-version constant and update every test that asserts the old number to read the constant.
  - [ ] Tests (extend `tests/store/test_question_answering_fields.py`): migration 017 on a store holding records in every 140 state keeps every row and gives each a null `request_id`.
  - [ ] Success: tests pass.
- [ ] **1.3 `mark_requested`** (effort 3)
  - [ ] Add `QuestionOperations.mark_requested(question_id, request_id, evidence)`: in one transaction move `answering` to `requested`, set `request_id` and write the evidence fields (`proposed_answer` holds the need, plus `cited_passages`, `check_verdict`, `check_reason`). A record already `requested` with this request id is a no-op. Any other state raises the store's existing invalid-transition error and writes nothing.
  - [ ] Tests (a new `tests/store/test_question_request.py`, and extend `test_answering_evidence.py`): state, id and evidence are written together; a repeat is a no-op; a different id on a `requested` record is refused; a `pending` or `declined` record is refused with nothing written; the `question_state_changed` change-feed event fires once.
  - [ ] Success: tests pass.
- [ ] **1.4 `RELEASABLE_STATES` and `submit_answer` stay correct** (effort 2)
  - [ ] Add `requested` to `RELEASABLE_STATES` (183, D8; per D9 it becomes `{pending, answering, requested}`). Leave `submit_answer`'s `_OPEN_STATES` as `{pending, answering}`.
  - [ ] Tests (extend 183's release tests and `tests/store/test_answer_submission.py`): release moves a `requested` record to `answered` with `answered_by = coordinator`; `submit_answer` on a `requested` record reports `settled` and writes nothing; a PM resolution at acknowledgment answers a `requested` record `pm` through the existing `_settle_question_on_acknowledgment` path.
  - [ ] Success: tests pass; 183's and 141's existing tests pass unedited.

**Commit**: `feat: add the requested question state and request_id`

## 2. Configuration

- [ ] **2.1 `request_limit` in `AnswererSettings`** (effort 2)
  - [ ] In `runner/project_config.py` add `request_limit: Annotated[StrictInt, Field(ge=1)] | None = None` beside `answer_limit` (D11). The `= None` is required: a pydantic field without it is required even when typed `| None`, and every existing `answerer` section would stop loading. It marks the key absent, as `ProjectSettings.answerer` does; it is not a default limit, and the gate declines `request_limit_unconfigured` on it. Update the class docstring ("All eight keys are required with no defaults") and the validator's error text to say that `request_limit` is the one optional key. A present but invalid value (zero, negative, non-integer, boolean) fails the load and names `projects.<id>.answerer.request_limit`.
  - [ ] Tests (extend `tests/runner/test_project_config.py`): a config without the key loads unchanged and gives `None`; a valid value loads; zero, negative, a string and `true` each fail naming the key path; an existing sample `projects.yaml` from the tests loads identically to before.
  - [ ] Success: tests pass.

**Commit**: `feat: add request_limit to the answerer configuration`

## 3. The reply contract and the decision

- [ ] **3.1 `ProposedRequest` and the parser** (effort 3)
  - [ ] In `runner/answering/artifacts.py` add `AnswerKind.REQUEST`, the frozen `ProposedRequest(provider, need, cited)` and extend `AnswerReply`, per D1. `read_answer` parses `{"kind": "request", "provider", "need", "cited"}` with the same lenient rules as the other shapes (strip whitespace, `kind` case-insensitive). A blank or missing `provider` or `need`, or a missing `cited`, is `artifact_malformed`. The parser does not check membership and never cuts the need. Define the reply's key names once as constants beside the existing ones.
  - [ ] Tests (extend `tests/runner/answering/test_read_answer.py`, using captured-format reply files as the existing tests do): valid; blank provider; blank need; missing `provider`; missing `cited`; mixed-case `kind`; a long need is returned whole; the answer and decline shapes still parse as before.
  - [ ] Success: tests pass.
- [ ] **3.2 `Requested` in `decide_answer`** (effort 3)
  - [ ] In `runner/answering/decide.py` add the frozen `Requested(provider, need, cited, evidence)` and return it from `decide_answer` for a `ProposedRequest` that passes the citation check, the check reply and the verdict, per D3. 144's checks keep their order. Evidence holds the need as `proposed_answer`, plus `cited`, `verdict`, `reason`. The module stays pure. Update the return annotation and the module's purity-check entry.
  - [ ] Keep the build green at this commit: `settle_run_result` in `finish.py` sends every non-`Confirmed` result to `_decline(..., Declined)`, which pyright rejects once `decide_answer` can return `Requested`. Add one explicit branch there that declines a `Requested` result `artifact_malformed` with a detail saying requests are not handled yet; Task 6.5 replaces it. A stray request reply from a model then becomes an ordinary PM question and never a tick crash. Add a test in `tests/runner/answering/test_finish_answering.py` that a `Requested` result declines with that reason and detail.
  - [ ] Tests (extend `tests/runner/answering/test_decide.py`): a request with a yes check returns `Requested` with that evidence; a check `no` declines `check_said_no`; a request citing nothing declines `uncited`; an unknown citation declines `unknown_citation`; a missing or malformed `check.json` declines as for an answer; membership is not checked here (an arbitrary provider string passes); the existing answer and decline cases are unchanged.
  - [ ] Success: tests pass; the purity check still passes; `uv run pyright` and `uv run pytest tests/runner/answering` pass.

**Commit**: `feat: parse request replies and decide Requested`

## 4. Program store: idempotent `create_request` and two reads

- [ ] **4.1 `create_request` takes a caller-supplied id** (effort 3)
  - [ ] In `store/program_requests.py` make `request_id` a required keyword of `create_request` and make the call idempotent on it (D7). If a request with that id exists, return it and write nothing. If the existing row differs from the arguments (waiting project, node, provider, need, question block, label), raise `ValueError`. A new id behaves as 184 defined, including every refusal.
  - [ ] Update every call to `create_request` in 184's code and tests to pass an id. Do not change any other 184 behavior.
  - [ ] Tests (extend `tests/store/test_program_requests.py`): a second call with the same id and arguments returns the same request, one edge and one request row; a second call with the same id and a different need raises `ValueError` and writes nothing; a different id for the same edge still cannot exist (184's rule); 184's existing tests pass with the id added.
  - [ ] Success: tests pass.
- [ ] **4.2 Two program-store reads: `live_request_count` and `edges_provided_by`** (effort 3)
  - [ ] Add `ProgramStore.live_request_count(provider_project) -> int` (D5): one query joining requests to edges, filtered on the provider and on edge state `open` or `satisfied`. The state values come from `EdgeState`, not literals in the SQL text. It works through `open_read_only`.
  - [ ] In `store/program_edges.py` add `edges_provided_by(project_id, states)`: every edge whose `provider_project` is the project, in the given states, ordered as 183's `edges_providing` orders. This is the provider-side counterpart of `edges_waiting`, needed for open and satisfied edges (D10).
  - [ ] Tests: the count includes open and satisfied edges, from every asker; a request whose run ended (`bound`, `met`, `failed`) still counts while its edge is open; a `released` or `superseded` edge does not count; another provider's requests do not count; zero for none. For `edges_provided_by` (extend 183's edge tests): only the requested states; unbound and bound edges both appear; edges where the project is only the asker do not appear; works read-only.
  - [ ] Success: tests pass.

**Commit**: `feat: make create_request idempotent and add the live request count`

## 5. Request facts and the request gate

- [ ] **5.1 `request_facts.py`** (effort 4)
  - [ ] Create `runner/answering/request_facts.py` with the frozen `RequestFacts` and `request_facts(...)` per the LLD API Contracts. All I/O is here and read-only. Read: members from the program; `provider_serves_requests` from the provider's `ProjectSettings.requests`; the band through 184's `requests_band` on the provider's store opened through `read_member`; `live_requests` from Task 4.2; `reverse_edges` as `edges_waiting(provider, {open})` filtered on `provider_project == asking_project` (D6).
  - [ ] Guards: a program of `None` returns facts with `program = None` and reads nothing else. A provider that is not a member, or is the asker, returns facts that let the gate refuse and opens no member store. `band = None` means one thing only: the provider is a member that serves requests but its store could not be read. It never raises (D4). This is by design: the gate lets it through, and 184 checks the band again before launch and shows the problem as its `unreadable` wait on `program-blocked`. Declining would turn a transient member fault into a PM question. A program store failure propagates (181, D7).
  - [ ] Tests `tests/runner/answering/test_request_facts.py` (scratch member stores and program store): each field for a normal provider; no program; unknown provider; provider is the asker; provider without a `requests` section; unreadable provider store gives `band None`; full band and a band collision are reported; the live count and reverse edges are right; the provider store is opened read-only and not written (recording check); a satisfied reverse edge is excluded.
  - [ ] Success: tests pass.
- [ ] **5.2 Share the answer gate's two checks** (effort 2)
  - [ ] In `runner/answering/gate.py` factor the answer-limit check and the reserved-term screen out of `evaluate_gate` into two private functions that Task 5.3's gate will also call, so each rule is written once (D4). No change to `evaluate_gate`'s behavior.
  - [ ] Success: 142's existing gate tests (`tests/runner/test_answer_gate.py`) pass unedited; `uv run pyright` passes.
- [ ] **5.3 `evaluate_request_gate`** (effort 4)
  - [ ] In `gate.py` add `evaluate_request_gate(question, prior_answers, *, request, facts, asking_project, settings)` returning the first refusal in the D4 table's order, nine checks, using Task 5.2's two functions. The reserved screen reads the question and the need. A `None` band skips check 7. The detail names the provider, and for check 8 the count and the limit, and for check 9 the waiting slice and its edge. For check 2 the detail names the missing key path, `projects.<asking_project>.answerer.request_limit`, so the PM knows which key to add (D11). The module stays pure.
  - [ ] Tests (extend `tests/runner/test_answer_gate.py` or a new `tests/runner/answering/test_request_gate.py`): one case per refusal with its exact decline reason (`request_outside_program`, `request_limit_unconfigured`, `answer_limit_reached`, `reserved_term` in the question and in the need, `request_provider_unknown` for an unknown provider and for the asker itself, `request_provider_unconfigured`, `requests_initiative_full`, `requests_band_collision`, `request_limit_reached`, `request_back_to_waiting`); a passing request returns `None`; a case that trips two checks returns the earlier one, for each adjacent pair; `request_limit_reached` triggers at exactly the limit and not one below; `band = None` passes check 7 and the request is allowed (the unreadable-provider case, D4); the `request_limit_unconfigured` detail contains the key path built from the asking project's id.
  - [ ] Success: tests pass; the purity check still passes.

**Commit**: `feat: add the request gate and its read-only facts`

## 6. The writes, the finish branch and the sweep

- [ ] **6.1 `request_writes.py`: the id and the stranded finish** (effort 3)
  - [ ] Create `runner/answering/request_writes.py` with `request_id_for(answering_entry_id)` (`req-` followed by the entry id, defined once) and `finish_stranded_request(store, program_store, record, entry)` per D8: read the request from the entry result's `request` object, do write 2 (`create_request` with the result's fields; a no-op if it exists), then write 3 (`mark_requested`). Put writes 2 and 3 in one helper in this module, which Task 6.3 reuses. A result without a usable `request` object raises `QuestionInvariantError`. Define the result's key names (`request`, `request_id`, `provider`, `need`, `cited`, `check_reason`, `asking_slice_label`, `question_block_id`) and the `decision` value `request` once, in this module or beside `RESULT_DECISION` in `finish.py`, whichever avoids an import cycle.
  - [ ] Tests `tests/runner/answering/test_request_writes_stranded.py`: from a resolved entry with a request result and no request row, the request, its unbound edge and a `requested` record appear; with the request row already present, write 2 is a no-op and the record becomes `requested`; with the record already `requested`, nothing is written; a result missing its `request` object raises; `request_id_for` is a function of the entry id only.
  - [ ] Success: tests pass.
- [ ] **6.2 `submit_request`: the block check and the refusals** (effort 3)
  - [ ] In `request_writes.py` add `submit_request(store, program_store, record, entry, requested, facts)` returning a `Settlement` (D7). This task writes the two paths that create nothing. Step 0: if the record's block is resolved, resolve the entry `discarded` and write nothing else. Gate: call `evaluate_request_gate` (Task 5.3) with `record.question` (a missing question raises `QuestionInvariantError`) and `prior_answers` from the store's `answerer_answers_in_run(record)`. That method is 142's private `_prior_answers` in `store/answer_submission.py` (the logic behind `COUNT_ANSWERER_ANSWERS_IN_RUN`), made public here with `submit_answer` calling it: a pure rename, no behavior change. On a refusal, decline the record with its reason and detail, then resolve the entry, 140's order. The passing path is a clearly marked stub raising `NotImplementedError` until Task 6.3. The gate is not run under the asker store's write lock (D4); say so in the docstring.
  - [ ] Tests `tests/runner/answering/test_submit_request_refused.py`: a resolved block writes no request, resolves the entry `discarded` and returns `discarded`; a record with as many answerer answers in its run as `answer_limit` declines `answer_limit_reached`, resolves the entry, and writes no request or edge (this proves `prior_answers` reaches the gate from the store), and one with fewer is not refused on that account; `answerer_answers_in_run` returns what `submit_answer` used before for zero, one and several answerer answers and does not count a `requested` record. The other refusals are Task 5.3's, and Task 10.2 runs each through the stage.
  - [ ] Success: tests pass; 142's existing tests pass unedited.
- [ ] **6.3 `submit_request`: the three writes** (effort 3)
  - [ ] Replace the stub with the passing path: (1) `journal_resolve` with the result 144 writes plus `decision = request` and the `request` object, `question_outcome = requested`; (2) `create_request` with `request_id_for(entry.id)`, `waiting_node_id = record.node_id`, `question_block_id = record.blocked_state_id`; (3) `mark_requested`. The asking slice label is `<cf index> <cf slice name>` of the record's node, the form 184's `need.md` uses; a node lacking either raises `QuestionInvariantError`. Add `QuestionOutcome.REQUESTED` in `finish.py`. Writes 2 and 3 are the same calls `finish_stranded_request` makes; share one helper, do not copy.
  - [ ] Tests `tests/runner/answering/test_submit_request.py`: a passing request writes the three things and returns `requested`, with the record `requested` and carrying the request id, the request `pending` and the edge `open` and unbound; a node without a CF index raises `QuestionInvariantError` with nothing written; the entry result holds every key the LLD lists.
  - [ ] Success: tests pass.

**Commit**: `feat: write a request in three idempotent steps`

- [ ] **6.4 `RequestContext` and the stage wiring** (effort 3)
  - [ ] Define `RequestContext` (program store, the tick's `Program | None`, members, store directory, project config) in a small module under `runner/answering/`. Build it once per tick beside 182's `ProgramContext`, and pass it to `AnsweringStage`, which holds it for Task 6.5's `finish_answering` and Task 6.6's sweep. For a project in no program it carries `program = None`. Use the build site Task 0.1 found; keep `runner/tick.py` from growing past its current size by putting the construction in the sibling module where `ProgramContext` is built.
  - [ ] Tests (extend `tests/runner/test_tick_answering.py`): a tick for a program member builds a context with its members; a tick for a non-member builds one with `program = None`.
  - [ ] Success: tests pass; 182's answering baseline (Task 0.2) passes unedited.
- [ ] **6.5 The finish branch** (effort 3)
  - [ ] In `runner/answering/finish.py` replace Task 3.2's interim decline branch (and its test) in `settle_run_result` with the real `Requested` branch (a branch only; the request logic stays in `request_writes.py`, so the file stays near its current ~206 lines plus a few). `finish_answering` takes the `RequestContext` (Task 6.4), reads `request_facts` from it, and passes both to `submit_request`. The final `journal_resolve` must not run a second time for a request: write 1 is the entry's resolution, so the branch returns the settlement and `finish_answering` skips the resolve for it. `_already_settled` reports a `requested` record for this entry as `QuestionOutcome.REQUESTED`.
  - [ ] Tests (extend `tests/runner/answering/test_finish_answering.py`): a finished run with a confirmed request ends with the entry resolved once, carrying `decision = request`; finishing the same run twice leaves one request, one edge and one resolved entry; the existing answer, decline and failed-run cases are unchanged.
  - [ ] Success: tests pass.
- [ ] **6.6 The stranded sweep** (effort 3)
  - [ ] In `runner/answering/stage.py` change `_settle_stranded` per D8, in this order: block awaits the Runner, skip (unchanged); entry result `decision` is `request`, call `finish_stranded_request` and mark the stage as having written; otherwise decline as now. Keep the existing helper functions and add no second loop.
  - [ ] Tests (extend `tests/runner/answering/test_stage_stranded.py`): a resolved entry with a request result is finished into a request and a `requested` record and is never declined `answer_discarded`; a plain resolved entry is still declined as before; a resolved entry with a request result whose block awaits the Runner (a PM resolution after write 1) is skipped: no request is created and the record is left to acknowledgment (`pm`).
  - [ ] Success: tests pass.
- [ ] **6.7 Crash points** (effort 4)
  - [ ] In `tests/runner/answering/test_request_crash_points.py` kill the finish sequence at each of the four points in D8's table, then tick: after the gate and before write 1, after write 1, after write 2, and after write 3. Assert for each end state: exactly one request, one edge, a `requested` record and no decline. For the first point the run is finished again and the gate re-runs, with nothing written beforehand. Use fault injection on the store and program-store calls, not sleeps.
  - [ ] Success: all four tests pass; the stub `sq` was started once per test.

**Commit**: `feat: finish requests in the answering stage and after a crash`

## 7. The `program_requests` passage

- [ ] **7.1 `requests_text` and the passage kind** (effort 3)
  - [ ] In `runner/answering/passages.py` add `PassageKind.PROGRAM_REQUESTS`. In `program_passages.py` add the pure `requests_text(asking_project, edges, requests)` per D10: one line per edge with its state wording and need, the none-text `No open requests involve this project.`, `REQUEST_NEED_PREVIEW_CHARS` and the `…` cut mark, and the size-limit replacement line. Every fixed line is a constant beside the function.
  - [ ] Tests (extend `tests/runner/answering/test_passages.py` and 182's program-passage tests): lines for an edge the asker waits on and one it provides; an edge with no request row; a long need is cut at the constant with the mark; the none-text; the replacement line carries the count; purity (no I/O); the module stays in the purity check.
  - [ ] Success: tests pass.
- [ ] **7.2 Reading and placing the passage** (effort 4)
  - [ ] In `program_sources.py` read, per member question, `edges_waiting(asker, {open, satisfied})`, `edges_provided_by(asker, {open, satisfied})` (Task 4.2) and `request_for_edge` for each listed edge. No member store, git or `cf` read. In `passages.py` or the assembly code, place the passage after the member list and before PM answers, outside the rules, plan and program size count: fit it into what they leave, and replace it by the one-line count when it does not fit, so request state never produces `sources_too_large`. The date is the tick clock; the passage is a state line, not dated evidence.
  - [ ] Every member question gets the passage. A project in no program gets none, and its passages are byte-identical to before.
  - [ ] Tests (extend `tests/runner/answering/test_passages.py`, 182's source tests and the size tests): position after the member list and before PM answers; a member question whose asker is party to no edge still gets the passage, carrying the none-text; a passage that does not fit becomes the count line and the question is still assembled; a very large rules set still yields `sources_too_large` exactly as before and not because of this passage; read counts are program-store only (recording check). A non-member's sources stay unchanged, proved by 182's baseline (Task 0.2).
  - [ ] Success: tests pass.
- [ ] **7.3 The visibility rule** (effort 3)
  - [ ] Add the new kind to 182's D6 allowed-set test. Build a three-member fixture (asker A, provider B, other C) with edges A→B, B→C and C→A, and assert that A's question passage shows only A's own two edges (A→B, C→A) and never B→C. Update `docs/process-contract.md`'s visibility paragraph in Task 10.5, not here.
  - [ ] Success: the test fails if the passage is built from all edges and passes with the asker filter.

**Commit**: `feat: add the program_requests passage and extend the visibility rule`

## 8. Instructions

- [ ] **8.1 Answer-step and check-step instructions** (effort 3)
  - [ ] In `runner/answering/answering.yaml` add, after 182's kind sentences, the answer-step request sentences of D2: when a request is possible, when to request, the provider named exactly as the member list shows and never the asking project, the self-contained need, declining an already-requested need, the reserved-action rule applying to the need, and the new reply shape written with descriptive placeholders only (no sample project id; the project's hallucination-trap rule). Describe the `program_requests` kind where 182's instruction describes its kinds.
  - [ ] In the check step change "an answer, not a decline" to "an answer or a request, not a decline", add the five request criteria of D2, and tell it explicitly not to judge whether the named project already meets the need.
  - [ ] Keep every step, param and file name coming from `pipeline_file.py`.
  - [ ] Tests (update the existing instruction-pinning tests, and `tests/runner/answering/test_launch_answering.py`): pinned sentences updated to the new text; the instruction file contains no sample project id (assert that no member id used in tests, and no `trading-` prefix, appears in the request shape); the pipeline file test still asserts names come from `pipeline_file.py`; the pipeline validates through 140's existing probe test.
  - [ ] Success: tests pass.

**Commit**: `feat: teach the answering steps to request and to check a request`

## 9. Listings

- [ ] **9.1 `requested` in `inspect questions`** (effort 2)
  - [ ] In `inspection/questions.py` accept `--state requested` (the state vocabulary comes from `QuestionState`), show the `outcome` column of a `requested` record as `request <request_id>`, and add `request_id` to `--json`. The text format goes in a constant beside the existing outcome formats.
  - [ ] Tests (extend 141's inspection tests): filter by `requested`; the outcome text; the JSON key; records in other states list as before; no new row on `program-blocked` (assert 183's and 184's rows only, per D12); `inspect blocked` shows the question state `requested` beside an open block.
  - [ ] Success: tests pass.

**Commit**: `feat: list requested questions with their request id`

## 10. Scenario, regression and docs

- [ ] **10.1 Scenario: the main path** (effort 5)
  - [ ] Create `tests/runner/answering/test_request_scenario.py` on 184's two-member rig (scratch member stores, scratch program store, the stub `sq` for both the answering run and the request run). Honor `AMOEBA_KEEP_SCENARIO_DIR` through the support 183 added (its value is the path to keep the supervisor directory in) and print that path (LLD walkthrough step 1).
  - [ ] Main path, one test, tick by tick: the stub answering run replies `kind: request` naming the provider with `check: yes`; after the asker's tick the entry result has `decision: request`, the program store has a `pending` request and an `open` unbound edge, and the record is `requested`; the provider's tick launches the request run (184's stub) and binds the edge; the asker's edge moves through `request_open`, `provider_not_done` and `satisfied`; release answers the record `answered` by `coordinator` and the asking run resumes with 183's instructions.
  - [ ] A second test, named `test_mid_request_snapshot` (the walkthrough selects it with `-k mid_request`; `-k` matches names, so the name is the contract), stops after the provider's launch and keeps that snapshot. It asserts on the same `program-blocked` listing function 184's inspection tests use (`inspection/program.py`): the asker's `edge` row with wait `request_open` and the provider's `request` row, both present, with the titles and reasons built from the constants 184 defined.
  - [ ] Success: both tests pass.
- [ ] **10.2 Scenario: variants and PM supersession** (effort 4)
  - [ ] In the same module, the variants the LLD walkthrough names, each through the real stage: every gate refusal reaching its own decline, one parametrized test over the ten decline reasons of the gate's nine checks (`full` and `collision` are check 7's two), each writing no request or edge; a non-member asker with the model replying `kind: request` (declines `request_outside_program`, the program store untouched, and the writes equal those of any other decline); a check `no` (declines `check_said_no`; whether a need belongs in the asker's own part is the check model's judgment, so this proves only the decline path, and real-model behavior is 186's); an unreadable provider store (the request is created, and `program-blocked` shows 184's `unreadable` wait on the provider's request row and the asker's edge row); a PM resolution after write 2 (the record answers `pm`, the edge is superseded and the request withdrawn).
  - [ ] Success: all pass; `tests/runner/answering` passes as a directory.
- [ ] **10.3 Regression and locality** (effort 3)
  - [ ] Run 183's tick baseline and 182's answering baseline unedited (Task 0.2). Confirm `tests/contract` (the locality proof, extended by 184) and `tests/test_writer_guard.py` pass: `create_request` is called only through the host's `ProgramStore`, and `mark_requested` only through the runner. Extend the guard's list if it enumerates writers.
  - [ ] Success: `uv run pytest tests/contract tests/test_writer_guard.py tests/runner/program` passes with no existing test edited, apart from the version-constant, `create_request` id and `RELEASABLE_STATES` updates Tasks 1.2, 1.4 and 4.1 name.

**Commit**: `test: prove the request outcome across projects and crash points`

- [ ] **10.4 Load case for the request reads** (effort 3)
  - [ ] Read `tests/load/test_program_load.py` (181's, extended by 183 and 184) and `tests/load/load_harness.py`, then add one case in the same style for what this slice adds to a question: a member asker party to many `open` and `satisfied` edges with requests, assembling its `program_requests` passage and running `request_facts` for a request to a provider with many live requests. Assert the file's existing time bound holds; that the reads are program-store reads plus at most one read-only open of the provider's store, with no git or `cf` call; and that the passage is replaced by its one-line count when the list exceeds the size limit.
  - [ ] Success: the case passes and the file's existing bounds are unchanged.

**Commit**: `test: add the request reads to the program load test`

- [ ] **10.5 Contract docs and the two design amendments** (effort 4)
  - [ ] `docs/store-contract.md`: the `requested` state, its transitions, `question_records.request_id` and migration 017, `RELEASABLE_STATES`, the entry result's `request` object and `decision = request`, `create_request`'s `request_id` idempotency, `live_request_count`, `edges_provided_by`, and the project schema version line.
  - [ ] `docs/inbox-contract.md`: a PM resolution on a `requested` question's block is the existing resolution, rejected as already resolved after release. No new body and no new rejection code.
  - [ ] `docs/process-contract.md`: the request outcome and reply shape, the request gate with its nine checks in order and its decline reasons, why the gate is not run under a lock, the three writes and their order, the stranded sweep's four crash points, the `program_requests` passage with its size rule, the extended visibility rule, `request_limit`, and the read cost per member question.
  - [ ] `docs/answerer-walkthrough.md`: the `request_limit` key: what it caps, that absent means the project does not request, and the decline reason `request_limit_unconfigured` that names it.
  - [ ] The LLD's "Provides to Other Slices" requires two edits to other slices' designs, and these are the only ones allowed: in `user/slices/183-slice.edges-and-release.md` D8, say that `RELEASABLE_STATES` gains `requested`; in `user/slices/184-slice.request-runs.md`, update the Integration Points line for 185 and the `create_request` signature line (D1) to say it takes `request_id` and is idempotent on it. Change only those lines.
  - [ ] Success: each LLD API Contracts method appears; the gate order and the crash table match the code; the visibility rule matches Task 7.3's test; the two design lines match what Tasks 1.4 and 4.1 built; no claim contradicts the code.

**Commit**: `docs: document the request outcome in the store, inbox and process contracts`

## 11. Final validation

- [ ] **11.1 Full checks** (effort 1)
  - [ ] Run `uv run ruff format .`, `uv run ruff check .`, `uv run pyright` and `uv run pytest` (the bare run, which excludes the live and load tiers). Run the load tests as regression checks by explicit path: `uv run pytest tests/load/test_runner_tick_load.py tests/load/test_inbox_concurrent.py tests/load/test_program_load.py`. Bounds must hold without edits.
  - [ ] Success: all pass, with no existing test skipped, weakened or edited to pass, apart from the updates Task 10.3 names. If a check fails, fix its cause and re-run.
- [ ] **11.2 Verification walkthrough** (effort 3)
  - [ ] Run the LLD "Verification Walkthrough" with `AMOEBA_KEEP_SCENARIO_DIR` set to a `mktemp -d` path, never the real supervisor directory, and run the LLD's step 1 with that path. Step 2 runs `amoeba inspect questions` and `amoeba inspect program-blocked` with `AMOEBA_STORE_DIR` set to the kept directory. Step 3 runs `amoeba serve --project-config <file>` against a scratch `projects.yaml` with `request_limit: 0`, then with the key removed, in a throwaway directory.
  - [ ] Success: each step shows what the LLD says, including the asker's `edge` row beside the provider's `request` row at the mid-request snapshot; any difference is fixed in code, and the closing report says what each step showed. After any fix, re-run Task 11.1's checks. Delete the throwaway directories when done.

Write no walkthrough note into this file. If a step needed a code fix, commit it at the marker below.

**Commit**: `fix: correct what the request-outcome walkthrough found` (only when a step needed a code fix; use `test:` when only tests changed)

- [ ] **11.3 CHANGELOG** (effort 1)
  - [ ] Under `[Unreleased] / Added`, one or two lines for slice 185 in the existing style: the request outcome of the answering run, the request gate, the `requested` question state, the `request_limit` key, the `program_requests` passage. Note that coordination is now live for projects in a program that configure `request_limit` and `requests`.
  - [ ] Success: entry present, concise.

**Commit**: `docs: add slice 185 to the changelog`
