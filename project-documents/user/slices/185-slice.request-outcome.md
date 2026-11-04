---
docType: slice-design
slice: request-outcome
project: amoeba
parent: user/architecture/180-slices.program-coordination.md
dependencies:
- 182-slice.program-concept-as-a-source
- 183-slice.edges-and-release
- 184-slice.request-runs
- 141-slice.question-record
- 142-slice.the-gate-and-answer-submission
- 144-slice.answering-run
interfaces:
- 186-slice.live-walkthrough
dateCreated: 20261103
dateUpdated: 20261104
status: not_started
turns: 32
promptTokens: 3162394
cachedTokens: 3017290
cacheWriteTokens: 145044
completionTokens: 30535
durationSeconds: 344.3
costUsd: 2.375082
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 2.375082
    completionTokens: 30535
---

# Slice Design: Request Outcome

## Overview

140's answering run gets a third outcome besides answer and decline: a **request** for a named member of the program. The request carries the need restated so that it stands on its own. The answer step proposes it and the check step confirms only two things: the need is real, and it belongs to the named member's part of the program. The check works from the asker's passages and the program concept, and does not judge whether the provider already meets the need. That is the request run's call (184).

A confirmed request then passes the **request gate**, which lives in `gate.py` beside the answer gate. It applies the answer limit, the reserved-term screen, the provider checks, the **request limit** and the **reverse-request refusal**. A refusal declines the question with a distinct reason. A request that passes is three writes, all owned by the asker's tick:

1. The answering entry is resolved, and its result carries the request.
2. The program store gets the request and its unbound edge, through 184's `create_request`.
3. The question record moves to `requested`.

The stranded sweep finishes a request that a crash left partly written, so a request is never mistaken for `answer_discarded`. The question block stays open. 183's edge row (with 184's `request_open` wait) lists the asking slice as waiting on the request, and 183's release or a PM resolution closes it.

The answerer's passages also gain a `program_requests` passage: the live edges and requests the asking project is party to. This extends 182's visibility rule.

This slice turns coordination on. Before it, nothing in a live project creates an edge or a request.

## Value

- **User value (milestone 5).** A cross-project need found by an agent becomes a slice in the other member's requests initiative, and the asking slice resumes when that slice lands. Nobody relays the request.
- **For the PM.** The PM sees a question that became a request as `requested` in `amoeba inspect questions`, with the request id. The asking slice and the provider's request both show on `amoeba inspect program-blocked`. A request that is refused reaches the PM as an ordinary decline with a reason that names the refusal.

## Technical Scope

**Included**

- The answer step's reply contract gains `kind: request` with `provider`, `need` and `cited`, and the parser gains `ProposedRequest` (D1).
- Both answering steps' instructions: when to request, what a self-contained need is, and what the check confirms (D2).
- `decide_answer` returns `Requested` for a request that passes the citation check and the check step (D3).
- The request gate in `gate.py`, with the request limit and the reverse-request refusal (D4, D5, D6).
- The three writes, each one idempotent, and their crash finishing in the stranded sweep (D7, D8).
- Changes to the question record: the `requested` state, its transitions, `request_id` (project schema migration 017) and `RELEASABLE_STATES` (D9).
- The `program_requests` passage and the extension of the visibility rule (D10).
- Configuration: `request_limit` in the `answerer` section, optional with no default; absent means the project does not request (D11).
- `create_request` gains a caller-supplied `request_id` and becomes idempotent on it (an amendment to 184's API, D7).
- Listings: `requested` and the request id in `inspect questions` (D12).
- Contract docs: store, process and inbox. `CHANGELOG.md`.

**Excluded**

- Everything after a request exists: request runs, binding, observation, release and supersession (183, 184, unchanged).
- Checks for cycles across three or more members, merging duplicate requests, and separate request checkouts (architecture, deferred).
- A new row on `program-blocked`. The asker's 183 edge row with 184's `request_open` or `request_failed` wait already is the "waiting on the request" listing (D12).
- Real model runs end to end (186).

## Dependencies

### Prerequisites

- **182, 183 and 184** are designed, not implemented. 185 starts after 184 merges. Where their code departs from their designs, 185's tasks follow the code.
- **140 is complete** (141 to 145). The code was read on 20261103: `answer_submission.py`, `answering.py`, `questions.py`, `question_models.py`, `runner/answering/{artifacts,decide,finish,gate,settle,stage}.py`, `answering.yaml` and `project_config.py`.
- No external change. No new `sq`, `cf` or `git` command.

### Interfaces Required

- **181:** the tick's `Program | None` (D7 there), `ProgramStore.members`, `read_member` (whose `Readable` result opens a member's store read-only), each member's `requests_initiative`, and `RunnerHost.program_store`.
- **182:** `ProgramContext`, `program_passages.py`, the passage order and size rule (D5 there), the `member` render line, and the instruction sentences that D8 there adds.
- **183:** `edges_waiting(project, states)`, `EdgeState`, `submit_release`, `RELEASABLE_STATES`, supersession (D9 there) and the edge row on `program-blocked`.
- **184:** `create_request`, `RequestState`, `request_for_edge`, `requests_band` with `BandState` (`Open`, `Full`, `Collision`), and `ProjectSettings.requests` (whose presence means the member serves requests).
- **140:** `decide_answer`, `finish_answering`, `settle_run_result`, the stranded sweep `_settle_stranded`, `evaluate_gate`, `submit_answer`'s answer count (`COUNT_ANSWERER_ANSWERS_IN_RUN`), `decline_question`, `_write_evidence`, `QUESTION_TRANSITIONS`, and `_settle_question_on_acknowledgment`.

## Architecture

### Component Structure

| Component | Location | Role |
| --- | --- | --- |
| Reply contract | `runner/answering/artifacts.py` | `AnswerKind.REQUEST`, `ProposedRequest(provider, need, cited)` |
| Instructions | `runner/answering/answering.yaml` | The request rule in the answer step, the request criteria in the check step, and the `program_requests` kind (D2, D10) |
| Decision | `runner/answering/decide.py` | `Requested` beside `Confirmed` and `Declined` (D3) |
| Request gate | `runner/answering/gate.py` | `evaluate_request_gate(...)`, which shares the answer limit and the reserved screen with `evaluate_gate` (D4) |
| Request facts | `runner/answering/request_facts.py` (new) | Reads what the gate needs from the program store and the provider's store, read-only (D5, D6) |
| Request writes | `runner/answering/request_writes.py` (new) | `submit_request`: writes 1 to 3. `finish_stranded_request`: writes 2 and 3 from a resolved entry (D7, D8) |
| Finish | `runner/answering/finish.py` | Dispatches `Requested` to the gate and the writes |
| Stranded sweep | `runner/answering/stage.py` | Checks an entry's request result, and then the request row, before declining (D8) |
| Requests passage | `runner/answering/program_passages.py`, `program_sources.py`, `passages.py` | `PassageKind.PROGRAM_REQUESTS` and `requests_text(...)`, which is pure (D10) |
| Question record | `store/question_models.py`, `store/questions.py`, `store/schema/017_question_request.sql` | `REQUESTED`, transitions, `request_id`, `mark_requested` (D9) |
| Release states | `store/release_submission.py` | `RELEASABLE_STATES` gains `requested` (D9) |
| Program store | `store/program_requests.py` | `create_request(request_id=...)` is idempotent. `live_request_count(provider)` is new (D5, D7) |
| Config | `runner/project_config.py` | `AnswererSettings.request_limit` (D11) |
| Listing | `inspection/questions.py` | The `requested` state and its `request_id` (D12) |

`finish.py` is at 206 lines. The request path goes into the two new modules, so `finish.py` only gains a branch.

### Data Flow

**The asker's tick** (new steps marked `+`). The order is 181's to 184's, unchanged:

```
program stage -> Program | None, ProgramView           (181, 183, 184)
answering stage
  launch: assemble_sources(..., program)              (182)
    + program_requests passage, after the member list (D10)
  observe -> finished run -> finish_answering
    decide_answer -> Confirmed | + Requested | Declined
    + Requested:
        block resolved?            -> discarded, entry resolved, nothing else (D7)
        request_facts(...)         -> program store reads; provider store read-only (band)
        evaluate_request_gate(...) -> GateRefusal -> decline record; resolve entry (140's order)
                                   -> pass ->
          (1) journal_resolve(entry, result{decision: request, request: {...}})
          (2) program_store.create_request(request_id = request_id_for(entry.id), ...)
          (3) store.mark_requested(record.id, request_id, evidence)
  stranded sweep, each `answering` record whose entry is resolved:
    block awaits the Runner              -> skip (unchanged)
    + entry result decision is `request` -> finish_stranded_request: (2) if absent, then (3)
    otherwise                            -> decline (unchanged)
```

The edge is created after this tick's program stage has computed `waiting`. That is safe, because the asking slice is blocked on its question and so is not ready anyway. The next tick's program stage counts the edge.

**After the writes** (unchanged, 183 and 184):

```
provider tick: request run -> bind (or met) -> request slice built ahead of planned work
asker tick:    edge request_open -> provider_not_done -> satisfied
               -> submit_release: requested -> answered (coordinator); block resolved; run resumes
PM resolves the asker's block first -> acknowledgment answers the record (pm)
               -> 183 supersedes the edge -> 184 withdraws the request
```

### State Management

- **Asker's project store.** The question record's new state and `request_id` (migration 017). The answering entry's result carries the request, so the decision survives a crash after write 1. The record's evidence fields are reused: `proposed_answer` holds the need, plus `cited_passages`, `check_verdict` and `check_reason`.
- **Program store.** One request and one unbound edge per request, written by the asker's tick through `create_request`. 185 adds no writer to existing columns. The edge's writers stay as 183 and 184 define them.
- **Provider's project store.** Read-only, for the band check (D5).
- No other state. The gate is pure, and the facts are read fresh at each finish.

## Technical Decisions

### D1 — The request reply: provider, need, citations
Status: decided

- The answer step's reply gains a third shape:
  `{"kind": "request", "provider": "<member project id>", "need": "<self-contained need>", "cited": ["P4"]}`.
- `read_answer` returns `ProposedRequest(provider, need, cited)`. A blank or missing `provider` or `need`, or a missing `cited`, is `artifact_malformed`. This is the same lenient parsing as the other shapes: whitespace is stripped and `kind` is matched case-insensitively.
- The parser does not check that the provider is a member. That needs the program record and is a gate check (D4), so the parser stays pure over the file.
- `cited` is required and goes through `check_citations` exactly as an answer's does. A request that cites nothing is `uncited`. That keeps it tied to passages the check can verify.
- The need is never cut. It reaches the provider's run through `need.md` (180), and release restates it (183, D7), so a silent cut would change what is asked. The store's existing text bound on the question record does not apply, because the need is stored on the edge (183, D1) and in the entry result.
- Rejected: a separate request step in the pipeline. The answer step already decides between answer and decline from the same passages, and a third shape in its reply costs nothing. A separate step would also add a model call to every question.

### D2 — Instruction changes: when to request, and what the check confirms
Status: decided

**Answer step.** These sentences are added after 182's kind sentences:

- A request is possible only when a program_members passage is present.
- Reply with a request when the question needs a change that the program_concept passages place in another project's part of the program, not in the asking project's part. Name that project's id exactly as the program_members passage lists it, and never name the project the question comes from.
- Write the need so that someone in that project who has not seen this question understands what is needed and why: what must exist, how this project will use it, and the passages that show it.
- Do not request what a program_requests passage already shows as an open request from this project to the same project for the same need. Decline instead, and say that it is already requested.
- The decline rules for push, merge to main, release, destructive database statements and policy changes apply to the need as they apply to an answer.
- The new reply shape is shown with descriptive placeholders only, never a sample project id. This follows the project's hallucination-trap rule: when the member list is unclear, a sample id would be the nearest token to copy.

**Check step.**

- "The proposed answer is an answer, not a decline" becomes "an answer or a request, not a decline".
- For a request, reply yes only if every one of these holds:
  - the named project is in the program_members passage and is not the project the question comes from;
  - the question shows that the asking project needs this;
  - the cited passages place the need in the named project's part of the program, not in the asking project's;
  - the need is understandable without the question;
  - the need does not authorize a reserved action.
- The check is told explicitly not to judge whether the named project already meets the need. Only that project's request run can see that (architecture, "Changes to 140").

The existing tests that pin instruction text are updated with the file. The pipeline file test still asserts that the step, param and file names come from `pipeline_file.py`.

### D3 — `decide_answer` returns `Requested`
Status: decided

- 144's six checks stay in order. A `ProposedRequest` follows the `ProposedAnswer` path through the citation check, the check reply and the verdict. A pass returns `Requested(provider, need, cited, evidence)`. Its evidence holds the need as `proposed_answer`, plus `cited`, `verdict` and `reason`.
- `decide.py` stays pure. Membership, limits and the program store are the gate's (D4), so a `Requested` value says only "the model and the check agree". It does not say the request may be created.

### D4 — The request gate is centralized with the answer gate
Status: decided

`evaluate_request_gate(question, prior_answers, *, request, facts, settings) -> GateRefusal | None` lives in `gate.py`, beside `evaluate_gate`. Both call the same two private checks, the answer limit and the reserved screen, so each rule is written once. The first refusal wins, in this order:

| Order | Check | Decline reason |
| --- | --- | --- |
| 1 | Asking project in no program (`facts.program is None`) | `request_outside_program` |
| 2 | Asking project has no `request_limit` (D11) | `request_limit_unconfigured` |
| 3 | `prior_answers >= answer_limit` (142's rule) | `answer_limit_reached` |
| 4 | A reserved term in the question or the need (142's screen, with the need in the place of the answer) | `reserved_term` |
| 5 | Provider not a member, or the provider is the asker | `request_provider_unknown` |
| 6 | Provider has no `requests` section (184, D14) | `request_provider_unconfigured` |
| 7 | Provider's band is `Full` or `Collision` (184, D4) | `requests_initiative_full`, `requests_band_collision` |
| 8 | Live requests to the provider, from every asker, `>= request_limit` | `request_limit_reached` |
| 9 | Reverse request (D6) | `request_back_to_waiting` |

- `GateRefusal` and `DeclineReason` are 142's. The new reasons join `DeclineReason`, which is checked in code, so no migration is needed for them. The detail names the provider, and for check 8 the count and the limit, and for check 9 the waiting slice and its edge.
- The gate runs before any write. A refusal declines the record and then resolves the entry, which is 140's existing order and its existing crash safety.
- Check 1 is how "a project in no program never produces a request" holds deterministically, whatever the model replies. A project in no program also gets no program passages (182, D1), so the instructions never offer a request there.
- **The gate is not run under the asker store's write lock**, unlike 142's `submit_answer`. Its facts span the program store and the provider's store, which no single lock covers. The one resident process ticks projects one at a time, and only the asker's own tick creates requests from that asker, so no other writer can change the facts between the read and the writes. 142's lock was there to stop two submissions in one store from both passing the limit, and that cannot happen across ticks in one process.
- An unreadable provider skips check 7 and passes. 184 checks the band again before launch, and its `unreadable` wait shows the problem on the program blocked list. The architecture's rule holds: a member that cannot be read is a blocked reason, not a failure. Declining would instead turn a transient problem with the member into a PM question.

### D5 — The request limit counts live requests to the provider
Status: decided

- **Live** means the request's edge is `open` or `satisfied`. A request whose run has ended (`bound`, `met`, `failed`) is still live while the asking slice waits, because that is exactly the load the limit throttles. It stops counting when the edge is `released` or `superseded`.
- **To one provider, from every asker.** This is the architecture's rule: the limit caps the open requests to one provider, and it is the only throttle on requests going first. Requests from every member of the program count.
- **Where the number comes from.** The asker's `answerer` section, as the slice plan says. Each asker compares the program-wide count with its own configured limit, so an asker with a lower limit stops requesting from a busy provider sooner.
- `ProgramStore.live_request_count(provider_project) -> int` is one query: requests joined to edges, filtered on the provider and on edge state `open` or `satisfied`. The state values come from `EdgeState`, not as literals in the SQL text.

### D6 — The reverse-request refusal: any live edge from the provider waiting on the asker
Status: decided

- A request from A to B is refused when B has an `open` edge that waits on A: `edges_waiting(B, {open})` filtered on `provider_project == A`. That is one program-store read.
- **This is broader than the slice plan's wording**, which says "whose checkout is held by a slice waiting on a request from the requester". The exact form would also resolve the checkout of B's waiting node and compare it with B's requests checkout. That needs B's snapshot, a `resolve_checkout` call and its failure modes inside A's finish. For the common shape, two repos where each member has one checkout, both forms give the same answer. A member with several checkouts may be refused when it could have proceeded. That case is rare. The refusal declines to the PM with a reason, and missing the case it guards against would deadlock two slices. The gate's existing bias holds: over-refusing costs one PM answer.
- Only open edges count. A satisfied edge is about to be released, and its waiting slice no longer waits on A.
- Chains across three or more members are not checked (architecture, deferred). Every wait in them shows on the program blocked list.

### D7 — The three writes, each idempotent, in the architecture's order
Status: decided

In `submit_request(store, program_store, record, entry, requested, facts)`:

0. **Block check.** If the record's block has been resolved, nothing is requested. The entry is resolved `discarded` (140's outcome when someone else answered first), and the PM's resolution settles the record at acknowledgment. This mirrors `submit_answer`'s `block_resolved` outcome.
1. **Entry resolved.** `journal_resolve(entry, completed, result)`. The result carries 144's `run_id`, `run_outcome` and `question_outcome = requested`. It also carries `decision = request` and a `request` object holding `request_id`, `provider`, `need`, `cited`, `check_reason`, `asking_slice_label` and `question_block_id`. From this point the decision is durable. The gate has passed, and nothing re-runs it.
2. **Request and edge.** `create_request(request_id=..., waiting_project, waiting_node_id = record.node_id, asking_slice_label, question_block_id = record.blocked_state_id, provider_project, need)`.
3. **Record moved.** `store.mark_requested(record.id, request_id, evidence)`. One transaction moves `answering` to `requested`, sets `request_id` and writes the evidence. A record that is already `requested` with this id is a no-op.

**Idempotency.**

- `request_id_for(answering_entry_id)` is the one function that derives the request id: `req-` followed by the entry id. Every attempt at writes 2 and 3 for one answering run uses the same id.
- **Amendment to 184's API:** `create_request` takes `request_id` as a required keyword. It returns the existing request, with nothing written, when a request with that id exists. If the existing row differs from the arguments, that is a programming error and raises `ValueError`. 184's tests pass an id.
- The asking slice label is `<cf index> <cf slice name>` of the record's node, the form 184's `need.md` uses. A node with no CF index or name cannot have reached `answering`, because questions come only from slice runs. If it happens, `QuestionInvariantError` is raised, which is the stage's existing error for an impossible record.

**Why entry first.** The architecture fixes this order. The entry is the asker store's durable record that the gate passed. Writing the record first would show `requested` with no request behind it. Writing the program store first would leave a request whose decision exists nowhere in the asker's store. With the entry first, every crash point leaves state that the next tick can finish (D8).

### D8 — The stranded sweep finishes a partly written request
Status: decided

`_settle_stranded` handles each `answering` record whose entry is resolved, in this order:

1. The block awaits the Runner: skip. This is unchanged, and the PM's resolution settles the record.
2. The entry result's `decision` is `request`: call `finish_stranded_request`, which does write 2 (`create_request` with the result's fields, a no-op if the request exists) and then write 3.
3. Otherwise, decline `answer_discarded` or `answering_run_failed` (unchanged).

| Crash after | Next tick sees | Finished by |
| --- | --- | --- |
| gate, before 1 | unresolved entry, record `answering` | observe pass. The run is still finished, so decide and gate run again. Nothing was written |
| 1 | resolved entry with a `request` result, no request row | sweep: writes 2 and 3 |
| 2 | resolved entry, request row, record `answering` | sweep: write 2 is a no-op, then write 3 |
| 3 | record `requested` | nothing to do |

- The sweep reads the request from the entry's result, which is always written before the request row. That covers the architecture's "check for a request row before declining" at both crash points, including the one where no request row exists yet. A resolved entry whose result says `request` is never declined, so a crash can never turn a request into `answer_discarded`.
- **A PM resolution between crash and finish.** If the block was resolved after write 1, step 1 skips the record, and acknowledgment answers it `pm`. If the request row already exists, 183 supersedes its edge and 184 withdraws it. If it does not exist, it is never created. So the block is resolved by the PM and the request does not linger.
- A test kills the sequence at each of the four points and asserts the end state: one request, one edge, a `requested` record, and no decline.

### D9 — The question record: `requested`, its transitions and the request link
Status: decided

- `QuestionState.REQUESTED = "requested"`. `QUESTION_TRANSITIONS` gains `answering → requested` and `requested → answered`. A `requested` record is never declined: the answerer has finished with it, and a refusal after this point does not exist. Only release (`coordinator`) or the PM (`pm`, at acknowledgment, 141's existing path) answers it. A stop or a rejection that re-blocks the node moves its `blocked_state_id`, unchanged.
- Migration 017 adds `question_records.request_id TEXT`, which is nullable and holds the program store's request id. There is no foreign key, because the row is in another store. `state` has no SQL `CHECK` (migration 013), so the new state needs no rebuild. The change-feed trigger already emits `question_state_changed`.
- `RELEASABLE_STATES` becomes `{pending, answering, requested}` (183, D8). Release moves `requested` to `answered` with `answered_by = coordinator`.
- `submit_answer`'s `_OPEN_STATES` stays `{pending, answering}`. A `requested` record is not open to the answerer, and a finishing run that meets one reports `settled`. The pending pass reads only `pending` records and the sweep reads only `answering` records, so neither touches `requested`.
- The answer limit is unchanged. It counts `answered` records with `answered_by = answerer`, so a request does not count.

### D10 — The `program_requests` passage: the state the asker is party to
Status: decided

- A new kind, `program_requests`. One generated passage, built by the pure `requests_text(asking_project, edges, requests)`. It lists every `open` or `satisfied` edge whose waiting or provider project is the asker, with its request where one exists:

  ```
  Open requests involving this project:
  - this project's slice 12 add-quotes waits on trading-data: request running; need: <need>
  - trading-ui's slice 4 chart-feed waits on this project: request bound to slice 205; need: <need>
  ```

  When there are none, the text is `No open requests involve this project.` Every member question gets the passage, so its absence never has to be interpreted. The fixed lines are constants beside the function.
- **Position and size.** It comes after the member list and before PM answers. Each need is cut to `REQUEST_NEED_PREVIEW_CHARS`, a constant beside `requests_text`, and the cut is marked with `…`. The full need stays on the edge. The passage is not counted with rules, plan and program passages. It is fitted into what they leave, before PM answers. If it does not fit, it is replaced by one fixed line: `<n> open requests involve this project; not shown: passage size limit`. So request state never makes a question `sources_too_large`. With the full list cut, the answer step may miss a duplicate, and the request limit (D5) still bounds the count.
- **Date.** The time it was read, which is the tick's clock. It states the situation as of that time. It is not evidence with an authoring date, and a state line contradicting a rule is not a case precedence is meant to settle.
- **Reads.** Program-store reads per member question: `edges_waiting(asker, {open, satisfied})`, all edges whose provider is the asker in those states (one query beside 183's `edges_providing`, which returns only open edges), plus `request_for_edge` for each listed edge. The provider-side query, `edges_provided_by(project_id, states)`, is new in `store/program_edges.py`; the rest are 183's and 184's. No member store, git or `cf` read.
- **Visibility rule.** It is extended in `docs/process-contract.md`: a member question also sees the needs and states of the edges and requests its own project waits on or provides. It never sees edges or requests between two other members. 182, D6's allowed-set test gains this kind, and a three-member fixture checks that an edge between the other two never appears.
- It is the first reader of request state in the answerer, and it is what lets the answer step decline a duplicate (D2). 182 left it to 185 (182, Technical Scope).

### D11 — `request_limit` joins the `answerer` section, optional with no default
Status: decided

- `AnswererSettings.request_limit: StrictInt | None, ge=1`. It sits with `answer_limit`, because the slice plan centralizes the two limits.
- **Absent means this project does not request.** It is not a default value. A request from a project without the key declines `request_limit_unconfigured` (D4, check 2), and the reason tells the PM which key to add. This mirrors 184's `requests` section, whose absence means a project serves no requests.
- **Existing configs keep loading.** A project outside any program needs no new key, and nothing changes for it. A value that is present but invalid (zero, negative, not an integer) fails the load and names `projects.<id>.answerer.request_limit`.

### D12 — Listings
Status: decided

- `amoeba inspect questions` accepts `--state requested`, which comes from the vocabulary. The `outcome` column for a `requested` record is `request <request_id>`, and `--json` adds `request_id`.
- `program-blocked` gains no row. The asker's waiting slice is 183's edge row, and its wait is 184's `request_open` or `request_failed` with the request's state. The provider's side is 184's request row. The slice plan's note ("185 askers waiting on requests") is met by those rows, which exist from the moment write 2 lands.
- `amoeba inspect blocked` already shows the question state beside the block (141), so the open block reads `requested`.

### Technology Choices

No new library. The existing pydantic artifact models, store machinery and migration runner, and the program store from 181, 183 and 184.

### Patterns and Conventions

- Each new vocabulary value is defined once: `AnswerKind.REQUEST`, `QuestionState.REQUESTED`, `PassageKind.PROGRAM_REQUESTS`, the decline reasons, and the result key and `decision` value `request`. Tests import them.
- `gate.py`, `decide.py` and `requests_text` stay pure and in the purity check. All I/O is in `request_facts.py`, `request_writes.py`, `program_sources.py` and the stage.
- The need is data. It goes from the model's reply onto the edge and into the provider's `need.md`. It never selects a code path.

## Implementation Details

### API Contracts

```python
# runner/answering/artifacts.py
class AnswerKind(StrEnum): ANSWER; DECLINE; REQUEST
@dataclass(frozen=True)
class ProposedRequest: provider: str; need: str; cited: tuple[str, ...]
AnswerReply = ProposedAnswer | AnswererDecline | ProposedRequest

# runner/answering/decide.py
@dataclass(frozen=True)
class Requested: provider: str; need: str; cited: tuple[str, ...]; evidence: AnsweringEvidence
def decide_answer(...) -> Confirmed | Requested | Declined

# runner/answering/request_facts.py
@dataclass(frozen=True)
class RequestFacts:
    program: Program | None
    members: tuple[Member, ...]
    provider_serves_requests: bool          # ProjectSettings.requests is not None
    band: BandState | None                  # None: provider unreadable (D4)
    live_requests: int
    reverse_edges: tuple[Edge, ...]         # provider's open edges waiting on the asker
def request_facts(*, program_store, program, members, store_dir, project_config,
                  asking_project: str, provider: str) -> RequestFacts

# runner/answering/gate.py
def evaluate_request_gate(question: str, prior_answers: int, *, request: Requested,
                          facts: RequestFacts, asking_project: str,
                          settings: AnswererSettings) -> GateRefusal | None

# runner/answering/request_writes.py
def request_id_for(answering_entry_id: str) -> str
def submit_request(...) -> Settlement          # D7; question_outcome requested | declined | discarded
def finish_stranded_request(store, program_store, record, entry) -> None   # D8

# store (QuestionOperations)
answerer_answers_in_run(record: QuestionRecord) -> int     # 142's count, made public
mark_requested(question_id: str, request_id: str, evidence: AnsweringEvidence) -> None

# ProgramStore (184, amended)
create_request(*, request_id: str, waiting_project, waiting_node_id, asking_slice_label,
               question_block_id, provider_project, need) -> Request   # idempotent on request_id
live_request_count(provider_project: str) -> int

# runner/answering/program_passages.py
def requests_text(asking_project: str, edges: Sequence[Edge],
                  requests: Mapping[str, Request]) -> str
```

`QuestionOutcome` gains `REQUESTED`. `DeclineReason` gains `REQUEST_OUTSIDE_PROGRAM`, `REQUEST_LIMIT_UNCONFIGURED`, `REQUEST_PROVIDER_UNKNOWN`, `REQUEST_PROVIDER_UNCONFIGURED`, `REQUESTS_INITIATIVE_FULL`, `REQUESTS_BAND_COLLISION`, `REQUEST_LIMIT_REACHED` and `REQUEST_BACK_TO_WAITING`.

`finish_answering` and `AnsweringStage` take a `RequestContext` (program store, the tick's `Program | None`, members, store directory, project config). It is built once per tick beside 182's `ProgramContext`. For a project in no program it carries `program = None`, and the request path declines at check 1.

**Inbox contract.** No new body and no new rejection code. A PM resolution on a `requested` question's block is the existing resolution. After release it is rejected as already resolved (183, D8).

### Database / Storage Schema

`store/schema/017_question_request.sql` (project schema):

```sql
ALTER TABLE question_records ADD COLUMN request_id TEXT;  -- program store request id; set with state 'requested'
```

Program store: no migration. `live_request_count` reads 184's `requests` and 183's `edges`.

## Integration Points

### Provides to Other Slices

- **186:** the producer. A real agent question in one member becomes a request, an edge and a `requested` record, and real request runs and releases follow. The fixtures 186 adds come from the reply shape in D1.
- **183 and 184, amended:** `RELEASABLE_STATES` gains `requested`, and `create_request` takes `request_id` and is idempotent on it. 184's Integration Points line for 185 and 183's D8 are updated to say so.
- **Process contract:** the request outcome, the request gate and its order, the three writes and the sweep, the `program_requests` passage and the extended visibility rule, and `request_limit`.

### Consumes from Other Slices

- **182:** program passages and `ProgramContext`. If 182's instruction sentences changed in implementation, D2's additions follow them.
- **183:** edges, release and supersession, used unchanged.
- **184:** `create_request`, `requests_band`, `RequestSettings` presence and request rows. A provider whose band check cannot be read is left to 184's wait (D4).
- **181:** a program store failure exits the process as a store failure (181, D7). A member store failure in `request_facts` is `Unreadable` and never exits (D4).

## Success Criteria

### Functional Requirements

- A question whose need the check places in another member's part becomes a request for that member, an unbound edge from the asking slice (184's `request_open`), and a `requested` record with the request id. The block stays open, and `program-blocked` shows the asker's edge row and the provider's request row.
- A need the check places in the asker's own part is not requested. A check `no` on a request declines `check_said_no`.
- Each refusal declines with its own reason, and no request or edge is written: no `request_limit` configured, the answer limit, a reserved term in the question or the need, an unknown provider or the asker itself, a provider with no `requests` section, a full or colliding band, the request limit, and a request back to a member waiting on the requester.
- A crash after the gate, after write 1 and after write 2 is finished by the next tick into exactly one request, one edge and a `requested` record. A crash after write 1 never ends `answer_discarded`. A test kills the sequence at each point.
- A PM resolution on the block before write 1 creates no request. A PM resolution after write 2 answers the record `pm`, supersedes the edge and withdraws the request.
- Release moves a `requested` record to `answered` by `coordinator` and resumes the asking run with 183's instructions.
- A project in no program never produces a request, even when the stub model replies `kind: request`. It declines `request_outside_program`.
- `program_requests` lists exactly the live edges and requests the asker is party to, and nothing between two other members. A list too large for the size limit is replaced by its one-line count, and the question is still answered.
- An existing `projects.yaml` without `request_limit` loads unchanged. An invalid value fails the load and names the key path.

### Technical Requirements

- `gate.py`, `decide.py` and `requests_text` pass the purity check. Every new vocabulary value is defined once and imported by its tests.
- The parser is tested with captured-format reply files for each shape: valid, a blank provider, a blank need, missing `cited`, and mixed-case `kind`.
- The stage is tested with a stub `sq` that writes `answer.json` and `check.json` per scenario, two or three scratch member stores and a program store. No live model.
- The no-program regression test from 182 and 183 still passes: the same passages, writes and journal for a non-member.
- Migration 017 is tested on a store holding records in every 140 state.
- Format, lint and typecheck (`ruff`, `pyright` strict) pass, with the full suite.
- Docs: `docs/store-contract.md` (`requested`, its transitions, `request_id`, `RELEASABLE_STATES`, the entry's `request` result), `docs/process-contract.md` (the request outcome, the gate order, the writes and the sweep, the passage, visibility, `request_limit`), `docs/inbox-contract.md` (resolutions on a `requested` block), `docs/answerer-walkthrough.md` (the new config key), and `CHANGELOG.md`.

### Integration Requirements

- With 183 and 184 merged, a request created by the answerer is served, bound, observed and released with no change to their code beyond the two amendments in Provides.
- 186 can run the walkthrough's three cases against real models with only the config keys this slice and 184 define.

### Verification Walkthrough

This is a draft, to be refined after implementation. Real models and real request runs belong to 186. Here the proof is a scripted program scenario with stub `sq`s for both the answering run and the request run.

1. **The request path end to end.**
   ```bash
   AMOEBA_KEEP_SCENARIO_DIR=1 uv run pytest tests/runner/answering/test_request_scenario.py -v -s
   ```
   The setup has two members, `asker` and `provider`, a scratch program store, and the stub answering run replying `kind: request` naming `provider` with `check: yes`. Expected, tick by tick:
   - The asker's answering run finishes. The entry result has `decision: request`, the program store has a `pending` request and an `open` unbound edge, and the record is `requested`.
   - The provider's tick launches the request run (184's stub), binds the edge, and builds the request slice.
   - The asker's edge moves through `request_open`, then `provider_not_done`, then `satisfied`. The record becomes `answered` by `coordinator`, and the asking run resumes with 183's instructions.

   The test prints its kept supervisor directory. Variants run in the same file: each gate refusal, a non-member asker, and a kill at each of the four crash points.

2. **Inspect the kept directory.**
   ```bash
   AMOEBA_STORE_DIR=<printed dir> amoeba inspect questions --project asker --state requested --json
   AMOEBA_STORE_DIR=<printed dir> amoeba inspect program-blocked
   ```
   Expected: the record with `request_id`. To see the mid-scenario snapshot, run with `-k mid_request`. It shows the asker's edge row with `request_open: running` beside the provider's `request` row.

3. **Config.** A `projects.yaml` with an `answerer` section and `request_limit: 0`:
   ```bash
   amoeba serve --project-config <file>
   ```
   Expected: start-up fails, naming `projects.<id>.answerer.request_limit`. With the key removed, start-up succeeds, and a request from that project declines `request_limit_unconfigured` (a variant in step 1's scenario file).

## Risk Assessment

### Technical Risks

- **The answerer starts creating work in other repos on a model's judgment.** A wrong request costs a provider run and a slice in its requests initiative.
- **A request can be requested twice**, for example when a second question asks for the same thing before the first request lands.

### Mitigation Strategies

- An independent check step confirms each request. The deterministic gate then bounds it: membership, the provider opting in with its `requests` section, the band, the per-provider limit and the reverse refusal. Nothing a model says satisfies an edge (183), and a PM resolution on the block withdraws the request at any time (184, D10).
- The `program_requests` passage shows open requests, so the answer step can decline a duplicate. When it does not, the request limit bounds the count. A second request for something already being built may come back already met once the first lands (architecture, deferred merging).

## Implementation Notes

### Development Approach

1. The question record: `REQUESTED`, transitions, migration 017, `mark_requested`, `answerer_answers_in_run` and `RELEASABLE_STATES`. Store and migration tests.
2. `request_limit` in `AnswererSettings`. Config tests.
3. The reply contract and parser, then `Requested` in `decide.py`. Pure tests.
4. `live_request_count` and the `request_id` amendment to `create_request`. Program store tests.
5. `request_facts.py` and `evaluate_request_gate`. Gate tests for each refusal and its order.
6. `request_writes.py`, the `finish.py` branch, the stranded sweep and `RequestContext` wiring. Crash-point tests.
7. The `program_requests` passage and the visibility test extension.
8. `answering.yaml` instructions and their pinned-text tests.
9. The `inspect questions` listing, the scenario test, contract docs and CHANGELOG.

Relative effort: 3.

### Special Considerations

- **Order of merges.** 185 needs 184's code for `create_request` and the band, and 183's for release. Its tasks begin after 184 merges.
- **Cost.** A request adds no model call. A member question adds two or three program-store reads to assembly. A confirmed request adds up to one member store open, read-only, for the band.
- **No secrets.** Request results and passages hold ids, indices, the need and a check reason.
