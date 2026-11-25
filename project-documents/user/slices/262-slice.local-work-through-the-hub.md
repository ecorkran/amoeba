---
docType: slice-design
slice: local-work-through-the-hub
project: amoeba
parent: user/architecture/260-slices.the-hub.md
dependencies:
- 260
- 261
interfaces:
- 263
- 264
dateCreated: 20261120
dateUpdated: 20261124
status: complete
turns: 43
promptTokens: 2643963
cachedTokens: 2395735
cacheWriteTokens: 248192
completionTokens: 63554
durationSeconds: 680.6
costUsd: 6.993
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-fable-5-2:
    rounds: 1
    costUsd: 6.9929998
    completionTokens: 63554
---

# Slice Design: local-work-through-the-hub

## Overview

Three commands need files that exist on one machine only: `handle-pause` (the run file, the repo, the answering run), the resume (`sq run --resume` in the run's checkout) and the wake wrapper (the wake command in a checkout). Today each of them opens the store itself, between its reads of local files.

This slice splits them. The command still runs on the machine that has the files. Every store transaction it makes today becomes one hub call, called a **step**. With no client file the same command runs the same steps in process on the local store.

It also adds the rule for work that only one machine can do. Every hub reply says whether the calling machine has work waiting. A client that sees the flag makes one claim call and starts what it was given: a resume, a `handle-pause`, or a wake.

After this slice the door serves `answer`, `send` with waking, and everything `handle-pause`, the resume and `wake-run` need. The PM's install has no client file and keeps running on its local store.

## Value

User value. A run that pauses on one machine can be answered from another, and resumes on its own machine at that machine's next call. A request can wake a repo on the machine that has its checkout, whichever machine sent it.

It also makes one piece of work start once. Today the resume's started mark can be written by any caller; here it becomes a claim that one caller holds.

## Technical Scope

Included:

- The two checks the architecture left to this design (D1, D2).
- The steps: the hub side of every store transaction in the pause path, the resume and the wake wrapper (D3, D4).
- `handle_pause`, the answering settle, the resume, `wake-run`, the question sweeps and the file clean-up rewritten to run on steps (D5, D9, D12).
- The answer limit and every age and expiry judged on the hub (D1, D2).
- The resume claim (D6).
- `answer` through the door (D7).
- Waking across machines, and `send` with waking through the door (D8).
- The work flag, the claim call and the detached starts. This replaces the "start after" step (D10).
- What each command does when a step gets no reply (D11).
- `amoeba hub rm-machine` closing what waits on the machine (D13).
- Migration 013: six columns (the machine on question and wake rows, the resume claim id, the two start counts, the wake mark on a request) and the two new values its `CHECK` lists take (D14).

Excluded, because the slice plan puts them later:

- `amoeba-mcp` as a client, its tick, and the `answer` deadline check on the hub (263). On a joined machine `amoeba-mcp` still does not start.
- Showing the state of runs on other machines in `list` and `status` (263). This slice shows which machine a question or wake belongs to.
- `amoeba adopt` and deleting the local-store way (264).
- The answering pipeline itself. It is changed only where it touches the store, because 320 replaces it.

## Dependencies

### Prerequisites

- Slices 260 and 261, built. Both are built and merged on `main` as of 20261123; the task breakdown checked each name below against the code, and the one change since the pinned commits that touches this design (`update_live.py` records a version, not a commit) is applied in D14. This design uses 260's decisions as written at commit `9ee28aa5` and 261's at `006c60ad`: the door, the call scope and kept results (260 D6, D8, D9), the network times (260 D7), the two store openers and the acting machine (260 D12), the hub home (260 D1, D2), `OPERATION_ERRORS` (260 D8), the two-machine fixture (260 D18), the client part and `here` (261 D5), `find_caller` and `find_member` (261 D6), checkouts and the wake command on them (261 D2, D9), and the `runs` document (261 D11). If either design changes one of these before this slice's task breakdown, this document is updated to match first.
- No new package.

### Interfaces Required

- `operations.served.run_served`, `wire.protocol`, `client.call`, `Store.call_scope` and `Store.act_as` (260).
- `wire.times.CALL_BOUND_SECONDS` (260 D7), which the claim limits here are worked out from.
- `operations.here` and `operations.run_gather` (261), for the caller and the machine's runs.
- `checkouts`, with `machine_id`, `path` and `wake_command` (261).
- The existing injected edges in `operations.deps.Deps`: `poll_run`, `spawn`, `list_runs`, `clock`, `sleep`, the directories.
- `scripts/update_live.py`.

Facts about other tools, read 20261120 on this machine: `sq` is 0.24.34 and `cf` is 0.19.28. This slice changes no call to either. Squadron keeps its run files under the user's home (`~/.config/squadron/runs`), so two fixture homes have separate runs.

## Architecture

### Component Structure

| Package | Modules | Change |
|---|---|---|
| `amoeba.operations.steps` (new) | `models` | One Pydantic request model and one reply model per step, and `STEP_MODELS`, the one table from a step's name to its two models and whether it writes. |
| | `pause`, `resume`, `wake`, `open_runs` | The hub side of each step: a plain function on a store, a config and a clock. |
| | `work` | `work_waiting` (the flag) and `claim_work`. |
| | `limits` | `pause_claim_seconds` and `resume_claim_seconds`, each defined once. |
| | `dispatch` | `run_step(name, store, document, edges)`, the one entry the hub and the local way both use. |
| `amoeba.operations` | `store_steps` (new) | The `Steps` protocol the client-run commands call, and `LocalSteps`, which runs `run_step` on the local store. |
| | `work_start` (new, replaces `request_release`) | Starts claimed work detached. |
| | `resume_run` (new) | The body of the internal `amoeba resume-run` command. |
| | `handle_pause`, `pause_eligibility`, `pause_claim`, `pause_held`, `pause_existing`, `pause_results`, `pause_class`, `claim_waiting`, `answering_settle`, `pause_context` | Take `Steps` in place of a store and a config. No transaction is opened in these modules. |
| | `resume`, `wake_run`, `prune` | The same. |
| | `answer`, `send`, `wake`, `question_sweep`, `question_sweep_scope`, `status` | Split into a client part and a hub part, as 261 did for its ten operations. |
| | `served` | Cases for `answer`, and `send` without 261's wake refusal. |
| `amoeba.store` | `schema/013_local_work.sql` (new); `questions`, `question_closing`, `held_questions`, `answers`, `wakes`, `messages`, `sql`, `sql_held`, `sql_wakes`, `sql_messages`, `vocabulary` | The migration. The machine on question and wake rows. The resume claim and the two start counts. The wake mark on a request. Reads by machine. |
| `amoeba.wire` | `protocol` | `STEP_CALLS`, `WRITING_STEPS`, the reply key `work`, the body key `via`. |
| `amoeba.hub` | `calls`, `admin` | `handle_call` routes a step name to `run_step` and adds the work flag to a done reply. `rm-machine` does more (D13). |
| `amoeba` (wiring) | `wiring_steps` (new, replaces `wiring_release`); `wiring`, `wiring_messages` | `DoorSteps`, which makes each step a door call. `steps_for(layout)` picks `LocalSteps` or `DoorSteps` once per command (D3). The after-step that claims and starts work. |
| `amoeba.cli` | `resume_command` (new); `main`, `commands`, `wake_command` | `amoeba resume-run`. `handle-pause` and `wake-run` no longer raise `NotServedError` on a joined machine. |

Import rules added to `tests/test_import_boundaries.py`:

- The client-run modules (`handle_pause`, the `pause_*` modules, `claim_waiting`, `answering_settle`, `resume`, `resume_run`, `wake_run`, `prune`, `work_start`) do not import `amoeba.store.store`. They reach the store only through `Steps`.
- `operations.steps` imports no module that runs `cf`, `sq` or `git`, and nothing from `amoeba.answering` that reads a file. The fixture hub's `PATH` still holds none of the three tools.
- `steps.models` holds no field of a date or time type. A test walks every request model and asserts it (D2).

### Data Flow

A run pauses on machine `alpha` and the PM answers from `beta`:

1. On `alpha`, Squadron's hook runs `amoeba handle-pause <run>`. It polls the run and asks `cf` for the directory's project, then calls the step `pause_begin`. The hub sweeps that run's older questions, finds the member, and returns the member's settings and what the store holds for this pause.
2. `alpha` reads the run file, gathers the sources, makes the scratch and calls `question_insert`. The row is `claimed`, on machine `alpha`.
3. `alpha` runs the answering run and reads its replies. An answer goes to `question_settle`, where the hub applies the answer limit and the reserved-term screen in that transaction. A decline goes to `question_wait`. Say the answerer declined: the row is `waiting_on_pm`.
4. On `beta`, `amoeba answer` is one door call. The hub records the answer and sees the question is on `alpha`. The result says so, with when `alpha` last called.
5. The next call from anything on `alpha` gets `work: true` in its reply. That client calls `claim_work`, gets the resume with its claim id, and starts `amoeba resume-run` detached.
6. `resume-run` polls the run, starts `sq run --resume`, follows it, and calls `resume_record` with the outcome.

With no client file, `steps_for` returns `LocalSteps`, and each step is one transaction on the local store, as each is today.

### State Management

| State | Where | Ends by |
|---|---|---|
| A question's machine | `questions.machine_id` | Set at insert, never changed. Set to null when the machine is removed, with the question closed (D13) |
| A pause claim | `questions.state = claimed`, `updated_at` | The settle. Past `pause_claim_seconds`, the next call from its machine starts `handle-pause`, which settles it, restarts it or closes it (D5, D10) |
| A held question | `questions.state = waiting_on_request` | Its request ending, then the `handle-pause` the work claim starts. Or `dismiss`, the close sweep, or `rm-machine` |
| A start mark | `questions.start_attempted_at` | Overwritten by the next start, at most once per `answering_wait_seconds` for a row |
| A resume claim | `answers.resume_claim_id`, `resume_started_at` | `resume_record`. Past `resume_claim_seconds` with no outcome, it is handed out again (D6), at most `MAX_AUTOMATIC_STARTS` times, then recorded `refused` (D10). The close sweep never ends an answer that has no outcome (D9) |
| A refused resume | `answers.resume_outcome = refused` | A new `answer`, `handle-pause` for that run on its machine, `dismiss`, or the close sweep marking it not delivered |
| An answer waiting for another machine | `answers.resume_outcome` null | That machine's next call, whose resume attempt records an outcome, `not_delivered` if the run has left the pause. Or `dismiss`, a newer answer, or `rm-machine` |
| A wake | `wakes`, now with `machine_id` | `wake_finish`. Unended, it stops counting as a live wake at its `deadline_at`, so it no longer holds off a wake for a newer mark (D8, rule 3). Rows are deleted by the message sweep past `prune_after_days`, as today |
| A wake that is due and unclaimed | `messages.wake_wanted_at` on an open request, with no wake run since | A machine with a wakeable checkout calling. Or the request ending or expiring |
| A question's automatic starts | `questions.start_count` | At `MAX_AUTOMATIC_STARTS` the question moves to `waiting_on_pm` (D10) |
| Scratch and logs | Each machine's state directory | That machine's prune, past `prune_after_days` (D12) |

Nothing new is written outside the store and the existing state directories. No queue is added: what a machine should start is read from these records on every call.

## Technical Decisions

### D1 — Check one: what runs or is read inside a transaction
Status: decided

Every transaction in the pause path, the answering settle, the resume, `answer` and the wake step was read for this. Most only read or write rows with values the caller already has. These are the ones that run a check, call back into client code, or use a local value inside the transaction:

| Where today | What runs inside | How it moves |
|---|---|---|
| `store.answers.settle_answered` | The gate, passed in as a function: the reserved-term screen and the answer limit, from the member's settings | `question_settle`. The call carries the answer, what it cites and the evidence. The hub builds the gate from its own config and the member's settings and runs it in the transaction |
| `pause_claim._limit_reached` | Reads the count in a transaction, compares it with `answer_limit` outside | `pause_begin` makes the comparison on the hub and returns the result with its detail text |
| `pause_held.link_for` | `find_request_link` parses the question inside a read transaction and calls back to look each id up | `pause_begin`. The question text is in the call; the hub runs the parse and the lookups |
| `question_sweep._judge` | Compares the claim's age with `answering_wait_seconds`, and the answer's newest sign of life with `resume_bound_seconds`, using the caller's clock and config | `pause_begin` and the hub part of `status`. The call carries only what Squadron said about each run. The answer rule changes: it applies only to a `refused` answer, and its bound is `resume_claim_seconds` (D9) |
| `request_release._due_rows` | `effective_state` on the caller's clock, and the start mark's age | `work_waiting` and `claim_work` |
| `store.wakes.claim_wake` and `can_wake` | The live-session, live-wake and daily-limit checks, on the caller's clock and limits. `log_stem` is a path on the caller's disk | The hub part of `send`, and `claim_work`. Limits come from the hub's config. The client sends its logs directory (D8) |
| `answer` | Finds the question, adds the answer and reads the question back in one transaction | The hub part of `answer`, unchanged |
| `resume` | The final write reads the stored outcome back when its own did not apply | `resume_record` returns what the store holds |

No other transaction in these paths runs client code. The gather's store read (`pause_context._read_store`) only reads, and becomes the read step `pause_sources`.

### D2 — Check two: the hub's clock
Status: decided

**Store functions that take the time from their caller.** In these paths: `insert_question`, `settle_waiting`, `replace_claim`, `insert_held`, `claim_held`, `settle_held_waiting`, `mark_start_attempted`, `add_pm_answer`, `record_resume`, `mark_resume_started`, `mark_not_delivered`, `settle_answered`, `close_question`, `claim_wake`, `can_wake`, `finish_wake`, `wake_summary`, `effective_state` and the message sweep. Their signatures stay. Each is called only from a step or a hub part, which passes the clock it was given: the hub's on the hub, the process's own with no client file.

**Places that compare a client's time with a store time.** Each moves to the hub, and the client is given the answer instead of the two times:

| Today | Compares | Now |
|---|---|---|
| `pause_class.classify_pause` | The clock with the claim's `updated_at` | `pause_begin` returns `claim_stale`. `classify_pause` takes that flag in place of a limit and a time |
| `question_sweep._judge`, `_mark_undelivered` | The clock with `claimed_at`, and with the answer's stamps | Judged in the step (D1) |
| `pause_held._evaluate`, `request_release._due_rows` | The clock with the request's expiry | The step returns the request's effective state |
| `wake_run._wait` | The clock with the row's `deadline_at` | `wake_read` returns `seconds_left`, and the wrapper waits that long on its own monotonic clock |
| `status_runs.classify_runs` | The clock with claim ages | The hub part of `status` already runs on the hub's clock (261) |

**What a client's clock is still used for.** Naming things and measuring its own waits: the answering run id, log file names, the resume's wait loop, and the age of its own files in the prune. None of these is sent as a time.

**A run's paused time** is the text Squadron printed. It is half of the question's key and is only ever compared for equality.

No step request has a time field (the test in Component Structure). A second test runs the pause, answer and wake paths against the in-process hub with the client's clock set an hour ahead, and asserts every stored time is the hub's and no expiry, age or claim moved.

### D3 — Steps
Status: decided

A step is the hub side of one store transaction a client-run command makes. It is a plain function in `operations.steps` that takes the store, the config, the clock, the acting machine and a request model, and returns a reply model.

The client-run commands call the `Steps` protocol, which has one method: `run(step, request)` returns that step's reply model. `STEP_MODELS` gives the request and reply model for each name, so a step is written in one place: its row in that table and its function. There are two implementations, each a few lines:

- **`LocalSteps`** calls `run_step` on the local store. Each step is its own transaction, as today.
- **`DoorSteps`** sends the request model as the call's `document` to `POST /call/<step name>` and validates the reply against the step's reply model (D11 says what a reply that fails does). The hub runs `run_step` inside 260's call scope, so the step and its kept result commit together.

`wiring_steps.steps_for(layout)` picks one when a command starts, by whether a client file exists, and the command keeps it to its end. It also takes the door times and a session identity (the four values of 263's session headers, 263 D6), which 263's tick passes; the tick is not a command and calls it on every tick (263 D1). A command never changes way partway:

- One that started with a client file uses `DoorSteps` for every step. `DoorSteps` reads the client file on each call, and if the file is gone it raises 260's `ClientFileError` naming the file. That is one more case of that error than 260 D3 lists, and only `DoorSteps` raises it. It never goes to a local store.
- One that started with none uses `LocalSteps`. If the machine joins meanwhile, its next step that opens the store or writes to it fails with 260's `LocalStoreClosedError` (260 D2, D4). In a hub home the local opener refuses with `HubHomeError` (260 D2), so no client-run command runs on a hub's own store.

Each new command still decides for itself, so 260's rule that the mode is decided on every call holds between commands.

Step names are in `STEP_CALLS` in `wire.protocol`, apart from `SERVED_OPERATIONS`, because they are not operations a person calls. The hub accepts a name that is in the served list, is `HELLO_CALL` or is in `STEP_CALLS`, and refuses any other as `not_served` (260 D6). `WRITING_STEPS` are the ones whose result is kept. 263 adds `session_tick` and `session_end`, which write and keep no result, so `Step` has two flags: `writes` ("its transaction is a write") and `keeps_result` ("its reply is kept through the door"); `WRITING_STEPS` reads `keeps_result`, and every step here sets it equal to `writes` (263 D2). `wire` imports nothing, so both are plain strings, and a test asserts they equal the names and the writing rows of `STEP_MODELS`. A step is refused, with `malformed_call`, when its document does not validate.

**A step document that is too large.** 260 refuses a body over `MAX_CALL_BYTES` (1 MiB) before it reads it, and a step is refused like any other call. Only the two steps that end a claim have a row waiting on them, `question_settle` and a `question_wait` that carries a decline, and each can be over the limit only through the answer: nothing bounds the answer file a run writes. `question_settle` carries the text twice, as the answer and as the evidence's proposed answer, so an answer of about half a mebibyte reaches the limit; a decline's evidence carries it once. That is unlikely, and it gets no branch of its own. The settle is refused, `handle-pause` exits 3 with the refusal in its calls-log line, and the claim goes stale. Each automatic start then finds the dead claim and tries the settle again, which is refused again. After `MAX_AUTOMATIC_STARTS` the question waits on the PM as `starts_exhausted`, whose detail points at that machine's calls log (D10). With no client file there is no door and no limit, as today. Any other step that is refused this way exits 3; the steps that carry the question's text come before any row exists, so nothing is left to start again.

A step that fails on the hub with one of 260's `OPERATION_ERRORS` (260 D8), such as a member whose settings name an authorize key the config lacks, is refused as `hub_error` (260 D6). The client raises it, and the command exits 3 as it does today.

- Rejected: one door call for the whole of `handle-pause`. The hub cannot read the run file, the repo or the scratch.
- Rejected: a second copy of each command for the hub way. One body with two `Steps` is what keeps the local way and the hub way the same.

### D4 — The step list
Status: decided

| Step | Kind | Replaces | Does |
|---|---|---|---|
| `pause_begin` | writing | `sweep_run`, the reads in `check_eligibility` and `_handle_polled`, `link_for`, `_limit_reached`, the read in `pause_held._evaluate`, the message sweep | See below |
| `pause_sources` | read | `pause_context._read_store`, `pause_claim._read_request` | The member's program, its members with each one's checkout path and Context Forge id on the calling machine, the PM precedent, the standing answers, and a named request's result or that it is no longer stored |
| `question_insert` | writing | `insert_question` | Inserts the row as `claimed` with its answering run, or as `waiting_on_pm` with a reason. The row's machine is the acting machine |
| `question_hold` | writing | `insert_held`, then the read in `_evaluate` | Inserts the held row and returns its request's state |
| `question_claim_held` | writing | `claim_held` | `waiting_on_request` to `claimed`. When it loses, says whether another claim or an answer won |
| `question_replace_claim` | writing | `replace_claim` | Swaps a dead claim's answering run |
| `question_wait` | writing | `settle_waiting`, `settle_held_waiting` | Moves a named claim, or a held row, to `waiting_on_pm`, with the reason, the detail and the evidence. Every decline goes here: the answerer's, a run that failed or stalled, a claim path that stopped |
| `question_settle` | writing | `settle_answered`, then `_wait_on_pm` after a gate refusal | Runs the gate. Answered: writes the answer and takes its resume claim (D6). Refused by the gate: moves the row to `waiting_on_pm` with the reason. Claim gone: superseded |
| `resume_claim` | writing | `mark_resume_started` | Takes the resume claim for an answer (D6) |
| `resume_read` | read | The reads at the top of `resume` | For `resume-run`: the question, the answer text and `resume_wait_seconds`, if the claim id is still the answer's |
| `resume_record` | writing | `record_resume` and its read-back | Records the outcome and returns what the store holds |
| `claim_work` | writing | `request_release.start_ended_held` | Claims work for the calling machine (D10) |
| `open_runs` | read | The read in `prune`; `sweep_candidates` | The calling machine's open questions' run ids and open answering run ids, and `prune_after_days` |
| `wake_read` | read | The read in `wake_run` | The wake's directory, command and `seconds_left`, if it is this machine's and unended with no pid |
| `wake_set_pid` | writing | `set_command_pid` | As today |
| `wake_finish` | writing | `finish_wake` | As today |

**What each claim step matches, and what losing does.** Each is today's compare-and-set, and its request carries what the compare needs. A caller that loses starts no answering run and no resume.

| Step | Applies only when | A caller that loses |
|---|---|---|
| `question_insert` | No row exists for the run id and paused time | Discards its scratch and is skipped as `already_claimed`, as today |
| `question_hold` | The same | Skipped as `already_claimed` |
| `question_claim_held` | The row is still `waiting_on_request` | Discards its scratch. Skipped as `already_claimed` if another claim won, superseded if an answer or dismissal did |
| `question_replace_claim` | The row is `claimed` by the answering run id the request names: the one `pause_begin` returned | Discards its scratch and is skipped as `already_claimed`. So of two `handle-pause` calls that both read one stale claim, one restarts it and the other runs nothing |
| `question_wait` | The row is `claimed` by the named answering run, or still held | Superseded |
| `question_settle` | The row is `claimed` by the named answering run | Superseded. No resume |
| `resume_claim` | The claim is free (D6) | Skipped as `resume_in_progress`, or given the final outcome already stored |

**`pause_begin`.** The request holds the caller (`here`, 261 D5), or none when the run alone decides the skip (D5, step 1), the run id, what the poll said about the pause (paused or not, the checkpoint kind, the paused time, the question), and the run's fate for the sweep, or none when the poll could not say. In one transaction the hub:

1. Closes the run's older open questions on the calling machine, by today's table with the one change in D9: an answer with no outcome is left to its resume claim.
2. Runs the message sweep, when it is due. It is part of this transaction, so a failure of it is the step's failure and a busy lock cannot be one: today's note on the result for a failed or busy message sweep is gone.
3. Stops there if the run alone decides the skip (not paused, another checkpoint kind, no question text), or if the run is an answering run. A request with no caller that gets past this step is refused as `malformed_call`; the client and the hub decide "the run alone" with the same function, `classify_run_only`, so it does not happen.
4. Finds the caller with `find_caller`. Not a project and not in a program are returned as such.
5. Reads the question's row and its latest answer. A row on another machine is returned as that, with the machine's name.
6. With no row: reads the question's request link, and whether the run's answer limit is reached.
7. With a held row: reads its request's effective state, the request's result when it is done, and whether the run's answer limit is reached. Both claim paths make that check before they gather, as `_limit_reached` does today.

The reply holds what the sweep closed, and then either the skip or: the member, its answering settings (models, cost cap, answer limit, passage bound, rules, not-authorized items), `answering_wait_seconds`, `resume_wait_seconds`, the row with `claim_stale`, the latest answer, the link, the limit result and the request's state. These are the settings that come from the hub with the first call. The client reads no `config.yaml` in the pause path.

Each replaced transaction stands alone today, protected by its own compare-and-set, with nothing local between them once the `cf` lookup is done first. So merging them changes no outcome, with one exception. Today an answering run's own pause is skipped by a store read before `cf` is asked. Here `cf` is asked first, because the store read is inside `pause_begin`. The skip is the same when `cf` answers, since it is decided at step 3, before the caller is looked at. When `cf` fails, that call now exits 3 with nothing written, where today it was skipped. Nothing waits on it: an answering run's pause is settled by its claimant or by the dead-claim path, not by this call.

### D5 — `handle_pause` on steps
Status: decided

The order of work is today's, apart from the answering-run skip that D4 describes. What changes is where each piece runs.

1. **Client.** Poll the run. If the run alone decides the skip (`classify_run_only`: not paused, another checkpoint kind, no question text), no `cf` call is made, as today, and `pause_begin` is sent with no caller. Otherwise gather the caller with `cf`. A failure of the poll or of `cf` is exit 3 with nothing written, as today.
2. **`pause_begin`.**
3. **Client.** If the reply is a skip, return it. If it is "not in a program", gather the checkout, call `add` with an empty document (261 D6), and call `pause_begin` again. A rejected `add` is today's skip. `add` is an operation, not a step, so `Steps` does not carry it. `handle_pause` is handed one more callable, `register`, which `wiring` builds from the placement `amoeba add` itself uses: the client part, then the hub part in process or the `add` door call. The pause modules import neither `add` nor the store.
4. **Client.** Read the run file. Apply the three checks that need it or the directory: prompt-only, wrong checkout, another member's question. A row on another machine is a new skip, `other_machine`.
5. **Client.** Classify, with `claim_stale` from the reply, and take today's path:
   - **No row, no link.** If the limit is reached: `question_insert` as waiting. Else `pause_sources`, gather, make the scratch, `question_insert` as claimed, run the answering run, read its replies, and settle: `question_settle` for an answer, `question_wait` for a decline.
   - **No row, a link.** `question_hold`. Then by the request's state: still open is `held`; done goes to the held claim; ended without a result is `question_wait`.
   - **A held row.** The same, from the state `pause_begin` returned.
   - **A held claim.** If the limit is reached, from the result `pause_begin` returned: `question_wait` as `answer_limit_reached`, with nothing gathered and no run started, as today. Else `pause_sources` with the request, gather, scratch, `question_claim_held`, run, and settle as above.
   - **A claimed row.** Poll its answering run. Today's dead-claim table decides: settle from the scratch (`question_settle` or `question_wait`, by what the scratch holds), settle as stalled (`question_wait`), restart (`pause_sources`, `question_replace_claim`, run, settle as above), or leave a young claim alone.
   - **Answered, not resumed.** `resume_claim`, then the resume (D6).
   - **Settled, closed, waiting on the PM.** Skipped, as today.
6. **Client.** After an answered settle, the resume, with the claim the settle returned.
7. **Client.** The prune when due, whose problems are a note in the result, as today (D12). Then, on every path including a raise, the after-step's work claim (D10).

**A stale claim** is one whose `updated_at` is at least `pause_claim_seconds` old on the hub's clock: `answering_wait_seconds + 2 * CALL_BOUND_SECONDS`. The hub stamps the claim when it applies `question_insert`. The claimant may get that reply up to one call bound later, then waits up to `answering_wait_seconds` for its run, and its settle may take one more call bound to land. A claim judged at `answering_wait_seconds` alone would be called dead while its owner is still inside its own limits. The same function is used with no client file, so there is one definition.

**The gather stays on the client.** `program_sources` (the member list and the concept file, read from another member's checkout) and the rest of `pause_context` run on the machine with the files, as 261 D6 left them. The hub never runs them. `pause_sources` gives them what they read from the store today: the program, its members, and each member's checkout path and Context Forge id on the calling machine. The caller's own Context Forge id comes from its `here`. Every `cf -p` call in the gather takes one of those ids and never a member id, which `cf` does not know for a member made after 261 (261 D6). A concept member with no checkout on this machine is 261's existing `missing` problem.

The calls log, the scratch and every log file stay on the machine that ran the command.

### D6 — The resume claim
Status: decided

`answers` gains `resume_claim_id`. `steps.resume.claim_resume` is the one function that takes a claim, in one statement:

- It sets `resume_started_at` to the hub's time and `resume_claim_id` to a new id.
- It applies only when the outcome is not final (`resumed` and `not_delivered` are final), and either no claim id is set, or `resume_started_at` is older than `resume_claim_seconds`.

`resume_record` writes the outcome unless one is final, as today, and clears the claim id only when it is the caller's. So a late outcome from a claim that ran out is still recorded, and cannot free a newer claim.

`resume_claim_seconds` is today's `resume_bound_seconds` with `2 * CALL_BOUND_SECONDS` in place of the one store wait: one call bound for the claim's reply to arrive, one for the outcome to land. With the example config that is 216.5 seconds (135.5 - 5 + 86). A resume that is slow to record because the hub was restarted is retrying inside its last call bound, so it is still inside its claim. `resume_bound_seconds` itself is unchanged; with no client file it still bounds how long an in-process `answer` can take for the MCP deadline check. Through the door that check uses `resume_claim_seconds` (263 D9).

Who takes a claim:

| Caller | When | Takes a claim if the outcome is |
|---|---|---|
| The hub part of `answer` | The question is on the calling machine | None yet (it is a new answer) |
| `question_settle` | The answerer's answer was written | None yet |
| `resume_claim` | `handle-pause` finds an answered, unresumed question | None, or `refused` |
| `claim_work` | The machine has an answer waiting | None |

So a refused resume is never handed out by `claim_work`. It is tried again by a new `answer`, which is a new row with no outcome, or by `handle-pause` for that run, exactly as the architecture says.

**The resume on a claim.** `operations.resume.resume(steps, claimed, deps)` takes the claim's payload: the question, the answer text, the claim id and `resume_wait_seconds`. It polls the run, starts `sq run --resume`, follows it as today, and calls `resume_record`. The claim now comes before the first poll, because three of the four callers are handed it by the hub. Two cases follow from that:

- The run is not at this pause: `resume_record` with `not_delivered`, as today.
- The first poll cannot be read: `resume_record` with `refused` and the reason, which frees the claim. `answer` then returns the refused result and `handle-pause` raises `SquadronError`, as each does today. One case records nothing: an earlier attempt's file holds `started` (below).

**What an attempt leaves on its own machine.** Each attempt keeps one small file, `logs/resume/<run id>/<answer seq>.attempt`, on its own machine. A later attempt for the same answer runs on the same machine and reads it first. An attempt writes it twice:

- `started`, just before it starts `sq run --resume`;
- the judged outcome (the outcome, detail and log path), once it has judged one and before it calls `resume_record`.

Each write goes to a temporary name and is renamed, so a reader sees a whole file or none. The file is in the run's resume log directory and is removed with it by the prune.

| The file holds | The later attempt |
|---|---|
| A final outcome, `resumed` or `not_delivered` | Calls `resume_record` with it, and polls and starts nothing. Only a lost record leaves a final outcome in the file with a claim still to be had |
| `started` | Polls. If the run has left the pause, it records `resumed`, with the detail that an earlier attempt started the resume and stopped before it recorded an outcome, and starts nothing. If the run is still at the pause, that start did not take, and it goes on as a new attempt |
| `refused`, or there is no file | Goes on as a new attempt: it polls, and if the run is not at the pause it records `not_delivered`, as today |

So a resume that worked is recorded as `resumed` whether its attempt stopped before it judged or after, and the PM is not told to answer a run that has already moved on. A `refused` in the file is never replayed: `handle-pause` retries a refused resume with the same answer, and a replay would stop it from ever starting `sq` again.

**`started` in the file and a first poll that cannot be read.** The attempt records nothing and leaves the file as it is. `resume-run` exits 3 with the error in its log, and `handle-pause` raises `SquadronError`. A `refused` here would say nothing was started, when the earlier attempt may have resumed the run, and writing it to the file would lose `started`. The claim runs out and the next attempt polls again. The cap in D10 bounds how many times `claim_work` hands it out.

**The close sweep and the claim.** The sweep never ends an answer that has no outcome (D9). Such an answer is always work for its machine, so a resume attempt, which can read the attempt file, is what records its outcome: `resumed`, `not_delivered` or `refused`. If the sweep judged it first, a `list` or the next pause's `handle-pause` would mark a resumed answer `not_delivered` before `claim_work` in that same command handed it out, and the file would never be read.

A write of the file that fails is logged at error level and not retried, and the attempt goes on; `resume_record` is the record that counts. Without the file a later attempt behaves as today. So for an answer with no outcome, a wrong `not_delivered` now takes both a failed write to the machine's own state directory and the attempt stopping before its record lands. The one other way to a wrong `not_delivered` is the retry of a refused resume that D9 describes.

The claim comes before the first poll, so a final outcome written during that poll (a dismissal, `rm-machine`) no longer stops the spawn that follows it; the outcome is never overwritten, and the resume reports the stored one (3.4's `test_an_answer_made_not_delivered_during_the_first_poll_reports_the_stored_outcome`).

`resume_claim` that finds a claim in flight returns that, and `handle-pause` reports a new skip, `resume_in_progress`.

- Rejected: judging "in flight" from `resume_started_at` and `resume_at` alone. After a refused outcome the two stamps cannot say whether a newer attempt has started.

### D7 — `answer`
Status: decided

`answer` is added to `SERVED_OPERATIONS` and `WRITING_CALLS`. The body carries `document` and `via`, the door as the client states it (260 D6).

The hub part records the answer in today's one transaction and then, in the same transaction, looks at the question's machine:

| The question's machine | The hub | The client |
|---|---|---|
| The calling machine | Takes the resume claim and returns its payload | Runs the resume in that call and returns today's result |
| Another machine | Returns that machine's name and `last_called_at` | Returns the result with `resume` null and the new field `waiting_on_machine` |
| None (the machine was removed) | Marks the answer `not_delivered`, with the detail that the run's machine was removed | Returns that as the resume result |

The CLI prints, for the second row: the answer is recorded; the run is on `<machine>`, which last called the hub at `<time>`; it resumes at that machine's next call.

`UNKNOWN_ADVICE` for `answer`: run `amoeba list` and look at the question before answering again.

With no client file the question's machine is always `local`, so `answer` behaves as today.

### D8 — Waking across machines
Status: decided

`wakes` gains `machine_id`. A wake is claimed by a machine, for a checkout of the recipient on that machine that has a wake command and a path (261 D9).

**When a wake is due** for a member, read from records and judged on the hub's clock:

1. The member has an open request that has not expired, and `send` wanted a wake for it. `send` decides that as it does today: when the request is `open` after the call (sent, or sent again unchanged) and today's three conditions hold at that moment, it sets the request's new column `wake_wanted_at` to the hub's time. A request sent while a session was live gets no mark and is never woken later, as today.
2. No wake of the member was claimed at or after that mark. The comparison includes the mark's own time, because a wake that `send` claims in the call that set the mark carries the same time. A mark gets one wake. A row whose command was started (it has a pid) is that wake whatever became of it, a wrapper that was killed included. One kind of claim does not count: a row that is unended, has no pid and is past its deadline. That is a claim nobody picked up (see "A lost claim" below).
3. Today's three conditions hold now: no live session in the member, no live wake, and fewer than `max_wakes_per_day` wakes in the window. A live wake is today's rule, unchanged: unended and before its `deadline_at`, with or without a pid.

`store.wakes.wake_due` is the one function for this (it lives in the store because `claim_wake` calls it in its own transaction, so the read and the claim cannot differ, and `store` may not import `operations`). Rule 3 alone is `wake_conditions_hold`, which `send` uses to decide whether to set the mark and which the door's interim refusal (`wake_door`, deleted with 7.2) keeps using.

**Presence across machines.** `sessions` is one table on the hub and each row has its machine (260 D12). The live-session check reads every row of the member, whichever machine wrote it, so one query is the check across machines. The check is 244's, unchanged. It stays in this slice and is tested here, because `wake_due` would wake a repo somebody is working in without it: with a live session row for the member on machine B, a `send` from machine A marks and starts no wake, and `claim_work` from A hands none out. What this slice cannot have is a joined machine writing such a row, because `amoeba-mcp` does not start on a joined machine until 263, where the plan puts it. The plan's 263 entry says 263 provides the cross-machine presence this waking reads. What 263 provides is those rows; the read is here (see the departures table). So through the door in 262 no member has a live session, and every `send` to a member with a wake command wants a wake. With no client file, sessions are written and read as today.

**A wake that fails to start** ends as `start_failed` and is not tried again, as today. The request waits for an agent or its expiry, and sending it again unchanged sets a new mark.

**`send`.** 261's `not_served` refusal for a `send` that would wake is removed. The hub part writes the request, sets the mark when rule 1 says so, and then:

- If a wake is due and the calling machine has a wakeable checkout, it claims the wake and returns it. The client starts `amoeba wake-run <wake id>` detached, as today. A start that fails is recorded with `wake_finish` as `start_failed`.
- If a wake is due and only other machines have a wakeable checkout, the result's new field `wake_waiting_on` names each of them with its `last_called_at`.
- Otherwise nothing more happens, as today.

**The door version goes up by one.** `send` is an existing call, and it now hands the calling machine a wake to start. A client built for 261 does not know that field. The wake would stay unended with no pid, hold off every other wake of that member until its deadline, and count against the day's limit. The architecture changes the door version when an existing call changes in a way an older client cannot use, and this is one. So `DOOR_VERSION` becomes 2, and 260's pinned tuple changes with it (260 D7). The hub then refuses every call from an older client as `door_version` before it reads the body, so nothing is claimed for a client that cannot start it, and the client prints the upgrade command. Only fixtures are joined before 264, and the PM's install has no client file, so the change costs nothing now.

- Rejected: keeping the version and claiming a wake only for a call that carries `logs_dir`. It is a second rule for what an old client may do, kept for clients that do not exist.

The client sends its logs directory as the body key `logs_dir`, beside `document` and `here`. `here` keeps 261's three shapes. The hub stores `<logs directory>/wake/<wake id>` as the row's `log_stem`. So `list` shows the machine and the path of a wake's logs, and the hub never reads the path.

**Another machine's wake** is claimed by `claim_work` at that machine's next call (D10). If no such machine calls, the request waits for an agent or its expiry.

**`wake-run`** uses `wake_read`, `wake_set_pid` and `wake_finish`. It waits `seconds_left` from `wake_read` (D2). It loads no config, as today. A `wake_set_pid` that gets no reply does not stop the command (D11).

**A lost claim.** If the reply that carries a claimed wake is lost for good, the row stays unended with no pid. It blocks another wake for that member until its `deadline_at`, then stops counting (rule 2), and the wake is due again. That is the architecture's limit for a wake: `wake_timeout_seconds`.

### D9 — The close sweep
Status: decided

The sweep closes open questions whose run has left their pause. Only the run's machine can say where a run is. So every sweep judges only the questions of the calling machine.

- **In `handle-pause`:** `pause_begin`, with the fate from the poll (D4).
- **In `status` and `list` with no subject:** the client part first calls `open_runs`. For each open run the listing does not show, it checks whether the run file exists, and adds the answers to the `runs` document as `absent_runs`. The hub part then judges each of the calling machine's open rows from the document: a listed run by its state or later pause, an absent run as gone only when its file is absent too. This is today's rule with the file check done where the file is. If `open_runs` fails, `status` fails with that error and makes no further call: exit 3, nothing written. That adds no new way to fail, because the hub part of `status` needs the same hub and the same config, and already fails on a config error with the file and key named.

261 left this sweep out of the door's `status`. It now runs in both ways.

**An answered question whose run has left the pause.** Today the sweep marks its latest answer `not_delivered` when the outcome is none or `refused` and nothing has been in flight for `resume_bound_seconds`. Two things change, in both sweeps and in both ways:

- **No outcome: the sweep leaves it.** That answer is work for its machine (D10), and the sweep runs inside the command, before that command's own after-step. The resume attempt that `claim_work` hands out records the outcome: `resumed` from the attempt file, or `not_delivered` when it polls and the run is not at the pause. An answer whose attempts never record anything is recorded `refused` after `MAX_AUTOMATIC_STARTS` hand-outs (D10), and is then the next case. So no answer keeps an empty outcome for ever on a machine that calls.
- **`refused`: marked `not_delivered`, as today,** once its newest sign of life (recorded, resume started, outcome recorded) is `resume_claim_seconds` old. The bound is the claim's, not `resume_bound_seconds`, so a retry that `handle-pause` has in flight is never judged inside its own claim.

One case still ends wrong, as it does today. `handle-pause` retries a refused resume, starts the run, and is killed before it records. The outcome on the hub is still `refused`, the run has moved on, and the sweep marks the answer `not_delivered` once the claim has run out. `claim_work` does not hand out a refused resume, so nothing reads the attempt file first. It takes a kill in the few seconds between the start and the record of a retry run by hand or by the hook, and the run itself is not harmed.

A question on another machine is never closed by this machine's listing. It stays as the store has it until its own machine calls.

### D10 — Work that belongs to a machine
Status: decided

**The flag.** `steps.work.work_waiting(transaction, machine, config, now)` is true when the machine has any of:

| Work | Read from |
|---|---|
| A resume | The latest answer of an `answered` question on this machine, with no outcome, that `claim_resume` would take now: no claim id, or a claim older than `resume_claim_seconds`. The flag and the claim use one predicate (D6) |
| A `handle-pause` for a held question | A `waiting_on_request` question on this machine whose request has ended or is no longer stored, with no start in the last `answering_wait_seconds` |
| A `handle-pause` for a dead claim | A `claimed` question on this machine whose claim is stale (D5), with no start in the last `answering_wait_seconds` |
| A wake | A member with a wakeable checkout on this machine, for which a wake is due (D8) |

Each is an existence query on an index, and the function stops at the first hit.

`handle_call` runs it inside the call scope, after the operation, and puts `work: true` or `work: false` in every done reply. A repeat that gets a kept result gets a fresh flag. A refused reply carries no flag.

**When the flag cannot be worked out.** The flag needs the config's limits. If the hub's `config.yaml` cannot be loaded, the reply carries no `work` key and carries `work_problem`, the config error's text with the file and key. The client prints it as one line on stderr: the hub could not tell whether this machine has work waiting. It is never reported as false. A call loads the config only when its own work needs it, as today, so `work_problem` reaches exactly the calls whose own work needs none. Among the operations those are `decisions`, `mark_read`, `dismiss`, `retract` and `withdraw`. Among the steps they include `resume_record`, `wake_set_pid` and `wake_finish`, which load no config on purpose: a broken config must not stop a resume's outcome or a wake's end from being recorded, as it does not stop the wake wrapper today. A call whose own work needs the config is refused as `hub_error` with the same text. Work can come to exist with no call at all, when a request expires, which is why the flag does not rely on the call that made the work.

**The claim call.** `claim_work` claims up to `MAX_WORK_PER_CLAIM` (5, today's `MAX_STARTS_PER_CALL`) items in one transaction, and returns them: resumes first, then held questions never started, then the oldest starts, then wakes. Work beyond the cap is left as it is, with nothing marked. The reply to `claim_work` carries the flag like any other, and it is still true, so the machine's next call claims the next five. A `handle-pause` child runs the after-step, so a batch over the cap drains with no further command.

| Item | The claim | Returned |
|---|---|---|
| Resume | `claim_resume` (D6) | The answer's seq and the claim id |
| `handle-pause` | `mark_start_attempted`, now for `claimed` rows too | The run id and the row's checkout |
| Wake | `claim_wake` (D8) | The wake id, directory and log stem |

Its request holds one field, `logs_dir`, the calling machine's logs directory, for a wake's log stem (D8).

It is a writing call, so a repeat inside the retry time returns the same items. If the client never gets them, each item is handed out again when its own limit has passed: a resume after `resume_claim_seconds`, a wake after its `deadline_at`, and a `handle-pause` once its start mark is `answering_wait_seconds` old. That last one is the least time between two starts for a row, not the claim's limit; a dead claim is first handed out when the claim is `pause_claim_seconds` old (D5).

**A `handle-pause` that keeps failing.** Each start by `claim_work` adds one to the row's `start_count`. A start can fail every time: `sq` is broken, or a settle is refused by the same `hub_error` on each try, and a restarted claim runs the answering model again. So when a row that is due already has `MAX_AUTOMATIC_STARTS` (3, a constant in `steps.limits`) starts, `claim_work` does not start it. It moves the row to `waiting_on_pm` in that transaction, with the reason `starts_exhausted` (a new `DeclineReason`) and a detail that gives the count and says the errors are in that machine's calls log. From there the PM answers or dismisses it, as any waiting question. The count is never reset, so one question gets at most three automatic starts, and at most three answering runs from them. A `handle-pause` run by the hook or by hand is not counted or refused.

**A resume that keeps dying.** The same cap applies to resumes. Each resume `claim_work` hands out adds one to the answer's `resume_start_count`. An attempt that dies with the run still at its pause, before it starts `sq run --resume` or after a start that did not take, records no outcome, so without a cap it would be handed out again for ever. When an answer that is due already has `MAX_AUTOMATIC_STARTS` such claims, `claim_work` does not hand it out. It records the outcome `refused`, with a detail that gives the count and says no attempt recorded an outcome. A refused resume is not pending work, shows in `list`, and is tried again by a new `answer` or by `handle-pause` for that run (D6).

**The after-step.** `wiring_steps.after_call` replaces `wiring_release.start_after`. It runs at the end of `wiring.invoke`, on both doors as `start_after` does today, and at the end of `amoeba handle-pause`, on every path including a raise. On the CLI door it runs after every operation. On the MCP door it runs after every operation but `answer`: the MCP deadline check bounds an `answer` call by its resume alone (`wiring.check_deadline`), and `start_after` does not run after `answer` today either. So a `reply` or `cancel` made through an MCP tool still starts the held question it released, as it does today. 263 moves the MCP door's after-step to the session's tick, which this slice does not have (263 D7).

It first runs the file clean-up when one is due (D12), except after `handle-pause` and `status`, which have run their own. Then, if the last reply the command got had the flag set, it makes one `claim_work` call and hands the items to `work_start.start_claimed`, which starts each one detached and does not wait:

- a resume: `amoeba resume-run <seq> <claim id>`. Its own stdout and stderr go to `logs/resume-run/<seq>-<stamp>.stdout.log` and `.stderr.log`, which need no run id and are removed by age like any other log. The logs of the `sq run --resume` it starts stay under `logs/resume/<run id>/`, as today;
- a `handle-pause`: `amoeba handle-pause <run id>` in the row's checkout, as today;
- a wake: `amoeba wake-run <wake id>`, as today.

It never raises and never changes the operation's result, as today. A start that fails is logged and written to the calls log (a `handle-pause`), recorded as `refused` (a resume) or `start_failed` (a wake).

When the command stopped because a call got no reply (`HubUnreachableError`), the after-step makes no call: no `open_runs` and no `claim_work`. The hub is not answering, and each call would wait one more call bound. Nothing is lost, because the flag is worked out again on the machine's next call.

With no client file the after-step asks `LocalSteps` for the flag with one read and does the same. So on the PM's install work now starts after any CLI call and after any MCP call but `answer`, where today it started after seven operations.

`resume-run` and `wake-run` do not run the after-step. A `handle-pause` child does, so a batch over the cap drains through the children, as today.

**Same machine.** `answer` on the run's machine and `send` from a machine with the wakeable checkout get their work in that call's own reply (D7, D8). A `reply` or `cancel` that ends a request whose held question is on the calling machine sees the flag in its own reply and starts `handle-pause` in the after-step.

**What `list` and `status` show.** Each question entry gains its machine's name. An answer waiting for another machine, and a member whose wake is waiting for another machine, show that machine and its `last_called_at`. A refused resume shows its reason, as today.

### D11 — When a step gets no reply
Status: decided

`DoorSteps` raises 260's `HubUnreachableError` when a step's outcome is unknown (no reply inside the retry time), and `HubRefusedError` when it is refused. The client-run commands do not catch either. Each stops at that step:

| Command | Stops with | What is left, and what happens to it |
|---|---|---|
| `handle-pause` | Exit 3, and the error as its calls-log line, as any exit-3 error today | No row: the run shows in that machine's `list` as a paused run with no record, with the command to handle it. A `claimed` row: the claim goes stale and the next call from that machine starts `handle-pause` again, which settles from the scratch or restarts. An answered row: the resume claim runs out and is handed out again. A held row: started again when its request ends |
| `resume-run` | Exit 3, the error in its log | The claim runs out and the resume is handed out again. That attempt reads this one's attempt file and records the outcome it judged, or `resumed` if it had started the run and judged nothing (D6) |
| `wake-run`, at `wake_read` | Exit 3. No command was started | The row is unended with no pid: a lost claim, due again after its deadline (D8) |
| `wake-run`, at `wake_set_pid`, no reply | A warning in its log, and the wake goes on to its end or its deadline. This is what the wrapper does today when the store is held | The row may show no pid. `wake_finish` ends it as usual |
| `wake-run`, at `wake_set_pid`, refused | The command's process group stopped, then exit 3 | The machine was removed, and `rm-machine` ended the row (D13). Or another run of the same wake recorded its pid first, and that one's command stands |
| `wake-run`, at `wake_finish` | Exit 3. The command has already ended or been stopped at the deadline | The row stays unended until its deadline. With a pid it is the mark's wake and no second one follows. With none it is a lost claim |
| The after-step | A log line | Nothing was started. The claims, if the hub applied them, run out |

A command never carries on past a step it has no answer for, and never starts a process on a claim it did not get. `wake_set_pid` with no reply is the one exception. The claim was already read with `wake_read`, the step only records a pid, and the row's deadline bounds the command with or without it. Stopping there would end a working agent because the hub was away for a minute.

**A reply that does not validate.** A done reply that does not fit the step's reply model raises `StepReplyError`, a new operational error whose text names the step and the field. It is raised on the client, so it joins `wiring.OPERATIONAL_ERRORS` and not the hub's `OPERATION_ERRORS` (260 D8). For a writing step the text also says the hub applied it. It is handled exactly as no reply is: the rows of the table above apply, and the command exits 3 with the error in its log. It cannot come from an older or newer hub, which the door version refuses first. It means the two sides disagree inside one version, which is a bug, and a test calls every step through `DoorSteps` against the in-process hub, so each reply is run through its model.

`UNKNOWN_ADVICE` for every writing step is one text: the command stopped at this step; the next call from this machine starts the work again from what the store holds.

### D12 — Clean-up of local files
Status: decided

`prune` keeps its marker file in the state directory and its limit of one walk an hour. Its trigger widens to the architecture's "from any call": today the code calls it at the end of `handle-pause` and of `status` only (`operations/prune.py`), and now the after-step (D10) also calls it, after every other operation. `handle-pause` and `status` keep their own call, in the same place as today, because its problems go into their result. The walk covers everything under the machine's logs directory by age, as today, which includes each wake's logs, each resume's logs and attempt file, and the `resume-run` logs; `wake-run` and `resume-run` do not prune, and the next command on that machine does. When a walk is due it calls `open_runs`, which returns the calling machine's open run ids and answering run ids and `prune_after_days` from the hub's config. It then walks its own scratch and logs as today.

Through the door, 261 left the prune out of `status`. It now runs there in `status`'s client part, after the hub call and before the result is returned, with the `open_runs` reply `status` already has from the sweep (D9), so `status` makes that call once. What the prune could not do never fails the operation. In `handle-pause` and `status` it is a note in the result, as today: `detail` and `file_problems`. After any other operation the after-step runs it when the result is already made, so there it is a log line. A failed `open_runs` leaves the marker untouched, so the next call tries again.

The hub prunes nothing on a client. Store rows are cleaned by the message sweep on the hub's clock, as in 261.

### D13 — `rm-machine`
Status: decided

`amoeba hub rm-machine <machine>` now also does this, in its one transaction, before the machine row is deleted:

- Closes every open question on the machine as `machine_removed`, a new `ClosedReason`, with the machine's name in the detail. Open is today's meaning: `claimed`, `waiting_on_pm`, `waiting_on_request`, or `answered` with the resume not done.
- Marks the latest answer of each such answered question `not_delivered`, with the same detail, and clears its claim.
- Ends every unended wake of the machine as `machine_removed`, a new `WakeOutcome`, with the machine's name in the detail.
- Sets `machine_id` to null on the machine's question and wake rows, which stay as history, and clears `log_stem` on those wake rows. A log path means nothing without its machine, so `list` shows none for them.

A wake command still running on the removed machine is stopped by its own wrapper: its next step is refused as `bad_token`, and `wake-run` stops the command's process group on any refusal. If the wrapper makes no call, the command ends at the wrapper's own wait.

A later `answer` to one of those questions reopens it, as `answer` does for any closed question, and is marked `not_delivered` at once (D7).

### D14 — The schema: migration 013
Status: decided

One migration, `013_local_work.sql`, run by both ways.

- `questions.machine_id`, referencing `machines`, nullable. `closed_reason` also allows `machine_removed`. An index on `(machine_id, state)`.
- `wakes.machine_id`, the same. `outcome` also allows `machine_removed`. An index on `machine_id`.
- `answers.resume_claim_id`, text, null, and `answers.resume_start_count`, an integer that starts at 0 (D10).
- `questions.start_count`, an integer that starts at 0 (D10).
- `messages.wake_wanted_at`, a timestamp, null (D8).
- A `BEFORE INSERT` trigger on `questions` and on `wakes` that aborts when `machine_id` is null, the pattern 260 uses for the owner. Both inserts bind it from the acting machine.

SQLite cannot widen a `CHECK` in place, so `questions` and `wakes` are rebuilt, as migrations 003 and 008 rebuilt `questions`. The rebuild carries every column, index and trigger the tables have by then, including 260's owner column and trigger.

The order inside the migration matters, because every row it copies has no machine yet and a trigger fires on `INSERT ... SELECT`: create the new table, copy the rows, drop the old table and rename, and only then create the two machine triggers. The migration test runs on a schema-12 store that holds question and wake rows. Each `CHECK` list is pinned to its enum by the existing vocabulary test.

**Rows from before the migration** have no machine. The migration cannot set it, because the local store's machine is made by the opener (260 D12). So `open_state_store`, after it has the `local` machine, makes one read for a question or wake with no machine and, when there is one, sets them all to `local` in one write. After that the read finds nothing.

`open_hub_store` does not do this. On a hub a row has no machine only after `rm-machine`, or in a fixture store seeded before this slice, and D7 and D10 say what that means: it is never work, and an answer to it is not delivered.

**When the live store migrates.** At the release, and not before. `scripts/update_live.py update` is the last step of the release skill (`.claude/skills/release/SKILL.md`). It is not run per merge or per slice (260 D19). One run installs the release's code and migrates the store from whatever schema it is at, so 013 runs in order after whichever of 011 and 012 the store still lacks. Between this slice's merge and the release nothing changes on the PM's install: it is the previous release's program on that release's schema.

**The new code and a store that is behind.** The new code never refuses an older store. Opening one migrates it, as every release does today, and the opener then gives its old rows the `local` machine. The refusal is the other way round: an older program refuses a store at a newer schema, with the store's schema error.

**The backup, and what undo costs.** `update` first copies the store and the config to `<state home>/backups/<stamp>/` and records the version that was installed (a PyPI version since `ce248104`, not a commit). Its read-back gains one check, after the `amoeba list` it already runs: no question or wake has a null machine. If the read-back fails, the script restores by itself in the same run, and nothing is lost. `uv run python scripts/update_live.py restore` does the same by hand later: it puts that copy of the store and config back and reinstalls the version from before. There is no down-migration. The copy is from before the update, so a restore discards everything written since: answers, decisions, standing answers, messages, sessions and wakes. It is the undo for an update found wrong soon after, and it costs more the longer the install has been used. The script keeps one backup, so after a later release's update the restore point is that release, not this one.

**Open sessions.** An `amoeba-mcp` started before the update is the old program, so its tools fail with the store's schema error until its session is restarted. The script prints each running `amoeba-mcp` with its directory when it ends. After a restore the same holds the other way round: a session started since the update is the newer program, which migrates any store it opens, so it is restarted before anything else is run.

A test runs `update` and `restore` against a copy of a schema-12 store, with a row written between the two, and asserts that row is gone after the restore.

### D15 — What the door serves, and documents
Status: decided

- `SERVED_OPERATIONS` gains `answer`. `send` is served in full.
- `STEP_CALLS` holds the sixteen steps in D4.
- `DOOR_VERSION` becomes 2, for `send` (D8). 260's pinned tuple test holds the new value.
- In 260's entry-point table, the row for `amoeba handle-pause` and `amoeba wake-run` is removed: both run on a joined machine. `amoeba resume-run` is registered beside `wake-run`, CLI only.
- `amoeba-mcp` start is still refused on a joined machine. A server that was running before the machine joined serves its `answer` tool through `wiring.invoke`, with no deadline check until 263 adds the hub's. 263 then deletes `NotServedError` and the client's served check (263 D14).

Documents brought in line:

- `docs/store-contract.md`: the six columns of D14, the three new values (`machine_removed` as a closed reason and as a wake outcome, `starts_exhausted` as a waiting reason), and that every time in the store is the store's own clock.
- `docs/cli-contract.md`: `waiting_on_machine` on `answer`, `wake_waiting_on` on `send`, the machine on question and wake entries, the skips `other_machine` and `resume_in_progress`, the `amoeba resume-run` command and its `logs/resume-run/` logs, and work starting after any call but an MCP `answer`.
- `docs/config-contract.md`: the two claim limits and what they are worked out from.
- `docs/squadron-hook.md`: `handle-pause` on a joined machine, and what a hub that is down leaves behind.
- `docs/mcp-server.md`: the new result fields.

### D16 — Tests and the fixture
Status: decided

- **Unit.** Each step is a plain function on a throwaway store with a clock the test sets. The claim rules, `wake_due`, `work_waiting` and the stale-claim limit each have a test per row of their table.
- **One body, two ways.** The existing pause, resume and wake tests run on `LocalSteps`. A parametrized subset, one per path in D5, also runs on `DoorSteps` against the in-process hub.
- **Faults.** 260's `DoorHooks` drops a reply after the commit. The in-process hub takes a clock, so a test can pass a claim's limit without waiting.
- **The two-machine fixture** gains, per client home: the existing `sq` stub (`tests/sq_stub.py`, with its resume stub) and its own Squadron runs directory under that home.
- **Live.** `tests/live/hold` and `tests/live/waking` each gain a variant on the two-machine fixture, with the repos split across the machines.
- **Load.** 260's door load test runs with the store seeded with 500 questions and 500 requests across both machines, and adds callers of `claim_work`. Its two bounds are unchanged: every call inside 2 seconds with 16 clients, and a median under 200 ms on an idle hub. That is the bound on the work flag, which every call now pays for. The idle-hub case also times each step once, with the same 200 ms median.
- **Latency.** A whole-on-hub CLI call is one `cf` call plus one round trip. A client-run command makes one call per store step. Door calls per command, with the after-step's `claim_work` as one more whenever the flag is set, and its `open_runs` as one more at most once an hour, when a prune is due:

  | Command | Door calls | Which |
  |---|---|---|
  | `answer`, run on another machine | 1 | `answer` |
  | `answer`, run on this machine | 2 | `answer`, `resume_record` |
  | `send` | 1, after one `cf get` | `send`. One more, `wake_finish`, only when a wake fails to start |
  | `status`, `list` with no subject | 2 | `open_runs`, then the call itself |
  | `handle-pause`, a new question answered and resumed | 5 | `pause_begin`, `pause_sources`, `question_insert`, `question_settle`, `resume_record` |
  | `handle-pause`, a held question claimed, answered and resumed | 6 | The same with `question_hold` and `question_claim_held` in place of `question_insert` |
  | `handle-pause`, the most it can make | 10 | The six above, `add` and a second `pause_begin` for a repo's first pause, `open_runs` when a prune is due, and `claim_work` |
  | `resume-run` | 2 | `resume_read`, `resume_record` |
  | `wake-run` | 3 | `wake_read`, `wake_set_pid`, `wake_finish` |

  Each door call is bounded by the load test above and, when the hub does not answer, by 260's `CALL_BOUND_SECONDS` (43). A command stops at the first call that gets no reply (D11), and its after-step then makes no call (D10), so an unreachable hub costs one call bound, not one per call. The target for the door's share of a command on an idle hub is its call count times 200 ms: at most 0.6 seconds for `answer`, `send`, `status` and `list` with `claim_work` counted, and two seconds for the longest `handle-pause`, whose answering run takes minutes.

### Departures from the parent documents

| Parent says | This design | Why |
|---|---|---|
| Each existing transaction block becomes one hub call | `pause_begin` and `question_settle` each merge transactions that run back to back | Nothing local happens between them, each is its own compare-and-set, and a new question that is answered and resumed takes five door calls (D16) |
| A pause claim is handed out again after `answering_wait_seconds` | After `answering_wait_seconds + 2 * CALL_BOUND_SECONDS` | The claimant's own limit starts when it gets the reply and ends when its settle lands. The architecture says every claim's limit allows for the retries of its last call |
| Work is a resume, a `handle-pause` for a held question, or a wake | Also a `handle-pause` for a claim that went stale | The plan's own criterion: a `handle-pause` cut off by the hub is started again by the next call |
| The resume claim is the started mark | The started mark and a claim id | The mark alone cannot tell a finished refused attempt from a new one in flight |
| The resume polls, then marks | Claims, then polls. A first poll that fails is recorded as `refused`, unless an earlier attempt's file holds `started` (D6) | Three of four callers are handed the claim by the hub. Without the record the claim would block a retry until it ran out |
| Plan: the sweeps become client-run with hub steps, with no change to what they close | The close sweep no longer ends an answer that has no outcome, and judges a refused one at `resume_claim_seconds` (D9) | The sweep runs inside the command, before that command's after-step. It would mark a resumed answer `not_delivered` before the resume attempt that reads the attempt file was handed out |
| Pending work is read from records that already exist | `send` records on the request that it wanted a wake | Another machine must be able to read that a wake is wanted, and `send` must stay the one that decides, as today |
| The resume claim allows the network retry time in place of the one store wait | It allows `2 * CALL_BOUND_SECONDS`: 86 seconds, where the retry time alone is 30 | A call can take the retry time plus one connect and one read, and two calls sit inside the claim: the one that returns it and the one that records the outcome |
| The clean-up runs on today's trigger | Today's code triggers it from `handle-pause` and `status` only; it now runs from any call | The architecture describes the trigger as any call, and a machine that runs neither command would keep its wake and resume logs |
| Every reply carries the flag | Every done reply | A refused call may have no machine or no config to work it out from |
| `claim_work` is "one claim call" | It returns up to 5 items | Today's cap on starts per call |
| The client asks the hub which runs are open, for the clean-up | `status` also asks before its hub call, for the sweep | Whether an unlisted run's file exists can only be checked on the client, and the client must know which runs to check |
| The hub stores the path of a wake's log | The client sends its logs directory: the body key `logs_dir` on `send`, and the one field of `claim_work`'s request | The hub cannot know a client's state directory |
| The resume keeps nothing on disk but its logs | One attempt file beside the logs: `started` before `sq` is started, then the judged outcome (D6) | A lost record, or an attempt that stopped after it started the run, must not turn a resumed answer into `not_delivered` |
| 260: an added call or field does not change the door version, and 262 only adds | `DOOR_VERSION` becomes 2 (D8) | `send` is an existing call, and it now returns a wake that an older client cannot start |
| The wake wrapper stops at a step that gets no reply | It stops at `wake_read` and `wake_finish`. At `wake_set_pid` it goes on (D11) | The command is already running. Today's wrapper goes on the same way when the store is held |
| Plan, 263: provides the cross-machine presence that 262's waking reads | The read is here: 244's check on the hub's one `sessions` table. 263 provides the rows of joined machines | `wake_due` is wrong without the check, and no joined machine writes a session row before 263 |
| Walkthrough step 7: a `handle-pause` cut off by the hub is started again when its claim runs out | Only once the question's row is written. Before that there is no claim, and the run shows in that machine's `list` as paused with no record | Work is read from records, and there is none yet. It is the missed hook of step 6 |
| `answer` and `send` are whole on the hub | What they record is. When the run or the wakeable checkout is on the calling machine, the client also starts the resume or the wake in that command, and `answer` makes a second call to record the outcome | The architecture's own "Same machine, no wait" |
| A CLI call is a `cf` call plus one round trip | More for the commands this slice changes; D16 has the count for each | Each store step of a client-run command is a call |
| No schema change is listed for this slice | Migration 013 | Work is found by machine, and `rm-machine` needs its two reasons |
| The slice lists no new command | `amoeba resume-run`, internal | A resume claimed from another call must not block that call |

## Implementation Details

### Migration Plan

This is a refactoring slice. The order keeps the suite passing on the local store after each step.

- **What moves.** Every `store.read()` and `store.write()` block in the client-run modules moves into a function in `operations.steps`. The client-run modules take `Steps`.
- **Consumers.** `cli.commands.run_handle_pause`, `cli.wake_command.run_wake_run`, `wiring._dispatch` (for `answer`, `status`, `send`), `wiring.invoke` (the after-step) and `mcp.detached` (unchanged: it starts the CLI) are the callers. `request_release` and `wiring_release` are deleted in the task that moves their last caller.
- **Behavior kept.** With no client file every existing pause, resume, wake, hold and sweep test passes, with five kinds of edit:
  - A test that built a `Store` for a client-run function builds `LocalSteps` on it.
  - A test that pinned the stale age or the resume bound uses the two new limits.
  - A test of `start_after`'s seven operations asserts the after-step for any operation. The test that the MCP door starts a held question after `reply` and `cancel` (`tests/test_wiring_release.py`) stays and passes against the after-step.
  - The sweep test that an unresumed answer past the bound becomes `not_delivered` (`tests/operations/test_question_sweep.py`) is split: with no outcome the sweep leaves it, and a refused one is marked (D9).
  - The test that an answering run is skipped before Context Forge is asked (`tests/operations/test_pause_eligibility.py`) asserts the skip with `cf` answering, and exit 3 with `cf` failing (D4).

  The test that a held question at the answer limit waits and starts nothing (`tests/operations/test_pause_claim_held.py`) passes with no edit beyond `LocalSteps`. 260's pinned tuple test takes the new door version.

  Test edits made, as built (each is noted under its task in `262-tasks.local-work-through-the-hub.md`): the stale age and resume bound (`test_every_state_exits.py`, `test_question_sweep.py`, `test_status_matches_handle_pause.py`, `test_status_sweep.py`); the sweep split; the answering-run skip (`test_pause_eligibility.py`); the first-poll refusal (`test_resume.py`); `start_after`'s tests moved onto the after-step and `claim_work` (`test_wiring_release.py` to `test_after_step.py`, `test_request_release.py` to `test_after_step_starts.py`, `test_request_release_child.py` to `test_handle_pause_child.py`, `test_start_ended_held_load.py` to `test_after_step_load.py`); the message timing figures (`test_message_timing.py`); the door's refusals and version (`tests/wire/`, `tests/hub/test_handle_call.py`, `test_app.py`, `test_join.py`, `test_joined_entry_points.py`, `test_door_operations.py`); hello and every done reply carrying `work`; the message-sweep note tests (`test_handle_pause_message_sweep.py`, the sweep is now part of `pause_begin`); the `mark_start_attempted` callers (`expected_state`); and every `record_resume` caller (`claim_id`).
- **Existing data.** Migration 013, and the opener's one write that gives old rows the `local` machine.

### API Contracts

The door version goes up by one, for `send` (D8). The additions below would not have needed it:

- Calls: `answer`, and the sixteen step names.
- Body key `via` on `answer`. Body key `logs_dir` on `send`, beside `document` and `here`; `here` is unchanged from 261. `claim_work` sends no `here`: its document is `{"logs_dir": ...}`. The `runs` document gains `absent_runs`.
- Reply key `work` on every done reply, or `work_problem` in its place (D10).

Commands:

```
amoeba resume-run ANSWER_SEQ CLAIM_ID      internal; started by the after-step
```

Result fields added: `AnswerResult.waiting_on_machine`, `SendResult.wake_waiting_on`, `machine` on question and wake entries of `status`, `SkipReason.OTHER_MACHINE` and `SkipReason.RESUME_IN_PROGRESS`, `ClosedReason.MACHINE_REMOVED`, `WakeOutcome.MACHINE_REMOVED` and `DeclineReason.STARTS_EXHAUSTED`.

### Database / Storage Schema

Migration 013 as in D14. `EXPECTED_SCHEMA_VERSION` becomes 13. `tests/store/test_migration_013.py` covers: a schema-12 fixture's row counts unchanged across the two rebuilds; every column, index and trigger of both tables still present; an insert with a null machine refused; the two new reasons accepted; and the opener giving old rows the `local` machine once.

## Integration Points

### Provides to Other Slices

- **The work flag and `claim_work`.** 263's tick reads `work` from its reply and runs the same after-step. 263 also takes the after-step off the MCP door's tool calls, and builds the switch on `wiring.invoke` for that; in this slice `invoke` has no such switch.
- **`Steps`.** 264 deletes `LocalSteps` and the mode choice; the client-run commands do not change. 264's unit tests run the steps against an in-process hub.
- **The resume claim** and **the hub steps of the pause path.** 320 replaces the answering run between `question_insert` and `question_settle` and keeps the steps.
- **The machine on questions and wakes.** 263 uses it to show runs on other machines.
- **`resume_bound_seconds`,** unchanged, and **`resume_claim_seconds`,** which 263's `answer` deadline check on the hub uses as its bound (263 D9).

### Consumes from Other Slices

- From 260: the door, the call scope, kept results, the network times, the acting machine, `rm-machine`'s transaction, the fixture and the load test.
- From 261: `here`, `find_caller`, `find_member`, checkouts and their wake commands, the `runs` document, and the hub parts of `status`, `send`, `reply` and `cancel`.

Nothing is consumed from a later slice. The presence check across machines is here (D8); 263 adds the sessions of joined machines as rows the same check reads.

A step that fails at the door fails with 260's errors. This slice adds one, `StepReplyError`, for a reply that does not fit its model (D11).

## Success Criteria

### Functional Requirements

- A fixture pipeline paused on machine A and answered from machine B resumes on A at A's next call. `answer` on B names A and when it last called.
- Three clients on one machine call at once with a resume waiting: one gets it from `claim_work` and the run is resumed once. The same for a held question whose request ended, for a stale claim, and for a wake.
- A `claim_work` whose reply is dropped for good hands the same resume out again after `resume_claim_seconds` on the hub's clock, and not one second before. The same for a start mark after `answering_wait_seconds` and a wake after its deadline.
- A resume whose `resume_record` is retried across a hub stop and restart is recorded once, and no other client is handed that resume meanwhile.
- A refused resume is not returned by `claim_work`. A new `answer` is, and `handle-pause` for that run retries it.
- `resume_claim` while a claim is in flight is skipped as `resume_in_progress` and starts nothing.
- A late `resume_record` from a claim that ran out records its outcome and does not clear the newer claim.
- The hub is stopped in the middle of a `handle-pause`, after `question_insert`: the command exits 3 with the error in the calls log. After the hub returns and the claim is stale, the next call from that machine starts `handle-pause`, which settles the question from the scratch or restarts the claim.
- The 242 hold-and-release fixture and the 244 waking fixture pass with their repos on two fixture machines.
- A request whose only wakeable checkout is on a machine that is not calling waits. `send` and `list` name that machine and when it last called. The request expires on time.
- `send` from the machine that has the wakeable checkout starts the wake in that call.
- A request sent while the recipient had a live session is not woken, then or later. Sent again unchanged once the session is stale, it is. A wake that ran and ended is not followed by a second wake for the same mark.
- With a live session row for the member on machine B, a `send` from machine A starts no wake and `claim_work` from A hands none out.
- A wake that ended `start_failed` is not handed out again for the same mark.
- Two `handle-pause` calls that both read one stale claim: one replaces it and runs the answering run, the other is skipped as `already_claimed` and runs nothing.
- A resume whose attempts die before starting `sq` is handed out three times by `claim_work`, then recorded `refused` with the count.
- `rm-machine` leaves no `log_stem` on that machine's wake rows, and the wakes it ends name the machine in their detail.
- A `handle-pause` whose client file is removed partway fails its next step with `ClientFileError` and opens no local store, with a set-aside store put back in place.
- On a machine that runs only `send` and `inbox`, wake and resume logs past `prune_after_days` are removed.
- Migration 013 passes on a schema-12 store that holds question and wake rows.
- A dead claim whose `handle-pause` fails every time is started three times by `claim_work`. The fourth time the question is moved to `waiting_on_pm` as `starts_exhausted`, and no fourth answering run starts.
- A `question_settle` over `MAX_CALL_BYTES` is refused by the door and `handle-pause` exits 3. After three automatic starts the question waits on the PM as `starts_exhausted`, and no second answering run was started.
- A resume judged `resumed` whose `resume_record` got no reply is recorded as `resumed` by the next attempt, from the attempt file, with no second `sq run --resume`.
- A resume attempt killed after it started `sq run --resume` and before it judged: the next attempt finds `started`, sees the run has left the pause, and records `resumed` with no second `sq run --resume`. With the run still at the pause it starts `sq` again.
- A refused resume retried by `handle-pause` starts `sq run --resume` again, with the earlier attempt's file present.
- A client at the previous door version that calls `send` to a member with a wakeable checkout on its machine is refused as `door_version`, and no request and no wake row is written.
- A `wake_set_pid` that gets no reply leaves the command running; it ends at its own exit or the deadline, and `wake_finish` ends the row. A `wake_read` that gets no reply starts no command.
- A wake row with a pid, unended and past its deadline, does not hold off a wake for a newer mark, and no second wake is handed out for its own mark.
- A step reply that does not fit its model stops the command at that step with `StepReplyError`, exit 3.
- With seven resumes waiting on one machine, one `claim_work` returns five and its reply has `work: true`; the next returns two.
- With the hub's `config.yaml` broken, a `mark_read` reply carries `work_problem` and no `work`, and the client prints it. A `wake_finish` in that state ends its row and carries `work_problem` too. `status` whose `open_runs` fails exits 3 and makes no further call.
- A resume attempt is killed after it started `sq run --resume`, and the run moves on. Once the claim has run out, the next call from that machine is, in three separate tests, `list`, `status`, and `handle-pause` for the run's next pause. In each, the sweep in that call leaves the answer alone, the call's after-step hands the resume out, and the answer is recorded `resumed`. The same three calls after a `resumed` record that got no reply record `resumed` from the attempt file.
- A resume that never started, on a run that then left the pause: the sweep leaves the answer, and the resume attempt handed out by `claim_work` records `not_delivered`. A refused answer whose run has left the pause is marked `not_delivered` by the sweep once its newest sign of life is `resume_claim_seconds` old, and not before.
- No answer keeps an empty outcome on a machine that calls: with every attempt dying before it records, the third hand-out is followed by `refused`, and the sweep then marks it `not_delivered` if the run has left the pause.
- With no client file, a `reply` and a `cancel` made through the MCP door each start the `handle-pause` of the held question they released. An MCP `answer` runs no after-step.
- A held question whose request is done, on a run already at its answer limit, waits on the PM as `answer_limit_reached`. Nothing is gathered and no answering run starts. The same for a question held and released in one call.
- A `handle-pause` for a run that is not paused makes no `cf` call. One for an answering run's own pause is skipped as `answering_run` when `cf` answers.
- A `handle-pause` that fails at `pause_begin` with the hub stopped returns after one call bound: its after-step makes no `open_runs` and no `claim_work` call, including when a prune is due.
- A prune problem is in the `detail` of `handle-pause` and in `file_problems` of `status`, as today, and is a log line after `send`.
- A resume attempt that finds `started` in the attempt file and cannot read its first poll records nothing and leaves the file. The next attempt polls, finds the run gone from the pause and records `resumed`.
- A wake that `send` claims in the call that set the mark is that mark's wake: after it ends, no second wake is due.
- Two `question_settle` calls for one run, sent at once with one answer left under the limit: one is answered and the other waits on the PM as `answer_limit_reached`.
- A client whose clock is an hour ahead runs a pause, an answer, a held question and a wake: every stored time is the hub's, and no expiry, age or claim differs from a run with a correct clock.
- No step request model has a date or time field.
- `handle-pause` called for a run whose question is on another machine is skipped as `other_machine`, and that machine's rows are not swept.
- `status` from machine A closes A's open question whose run is gone, and leaves B's open question open.
- `rm-machine` leaves no open question, no question whose latest answer lacks a final outcome, and no unended wake on that machine. A later `answer` to one of those questions is recorded and marked `not_delivered`.
- A wake wrapper whose machine was removed stops its command's process group at its next step.
- Each machine's scratch and logs past `prune_after_days` are removed by that machine's prune through the door, and those of an open question on that machine are kept.
- `handle-pause` on a joined machine reads no local `config.yaml`: it passes with none present.
- With no client file, every existing pause, resume, hold, sweep and wake test passes on the local store, with the edits listed in the Migration Plan.
- `scripts/update_live.py update` and `restore` pass against a copy of a schema-12 store, and the opener gives its old rows the `local` machine. A row written between the two is gone after the restore.

### Technical Requirements

- `ruff`, `pyright` strict and the full `pytest` run pass.
- The import rules in Component Structure are tested. The fixture hub's `PATH` holds no `cf`, `sq` or `git`.
- The door load test passes its two bounds with the seeded store and `claim_work` callers (D16), with the measured figures in the slice notes.
- Every writing step has an `UNKNOWN_ADVICE` entry.
- New source files stay near 300 lines.
- The documents in D15 are updated and `tests/test_contract_docs.py` passes.

### Integration Requirements

- 263 can start a machine's waiting work from a tick by reading `work` and calling the after-step.
- 264 can delete `LocalSteps` without changing a client-run command.
- The PM's install, with no client file, behaves as before, with these differences, because the local way runs the same steps:
  - Waiting work starts after any CLI call and after any MCP call but `answer`, where today it starts after seven operations on both doors (D10).
  - The file clean-up runs from any call that runs the after-step (D12).
  - A question or a resume is started automatically at most three times (D10).
  - A pause claim counts as dead at `pause_claim_seconds`, 86 seconds later than today's `answering_wait_seconds` (D5).
  - An answer whose resume recorded no outcome is taken again by the next call, once its claim is `resume_claim_seconds` old: 216.5 seconds with the example config (D6). Its resume attempt records the outcome. Today the sweep marks such an answer `not_delivered` after `resume_bound_seconds`, 135.5, once its run has left the pause; the sweep now leaves it, and judges only a refused answer, at `resume_claim_seconds` (D9).
  - The resume claims before its first poll and keeps an attempt file. A first poll that cannot be read is stored as `refused`, where today nothing is stored (D6).
  - `handle-pause` for an answering run's own pause asks `cf` before it is skipped, and exits 3 if `cf` fails (D4).
  - A wake that `send` wanted and whose claim was lost is due again after its deadline (D8).
  - Question and wake entries show the machine `local`.

### Verification Walkthrough

The implementing agent runs this as the slice's last task and puts the output in the slice notes. Nobody else has a step in it. `tests/hub_fixture.py`, `amoeba join` and the hub commands come from 260; `amoeba resume-run` and the new result fields are built here.

The criteria above are tests on the in-process hub, the two-machine fixture and the local store. Both commands must pass:

```bash
uv run pytest tests/operations tests/hub tests/store/test_migration_013.py tests/load/test_door_load.py
uv run pytest tests/live/hold tests/live/waking      # live tier; spends on models
```

Then one pass by hand, with the fixture's hub and two client homes `alpha` and `beta` (`tests/hub_fixture.py`), a repo `widget` added on `alpha`, and a pipeline there that asks a question the answerer declines. Each step's expected output is beside it:

```bash
# alpha: the run pauses; Squadron's hook runs this
cd ~/alpha/widget && amoeba handle-pause <run id> -j
#   outcome waiting_on_pm, with the decline reason; exit 0

# beta: the PM answers
amoeba list
#   the question, with machine alpha and its answer command
amoeba answer <run id> --text "Use the v2 schema" -j
#   outcome recorded; resume null;
#   waiting_on_machine: {machine: alpha, last_called_at: <time>}; exit 0

# alpha: any call
amoeba list
#   the answer still shows as waiting for alpha: the listing was made first.
#   Its reply had work: true, so the after-step claimed the resume and
#   started resume-run detached
amoeba list
#   run once the pipeline is running again: the answer shows as resumed
ls ~/alpha/.local/state/amoeba/logs/resume/<run id>/
#   <answer seq>-<stamp>.stdout.log, .stderr.log and <answer seq>.attempt, on alpha
ls ~/beta/.local/state/amoeba/logs/resume/ 2>/dev/null
#   nothing: beta ran no resume
```

The wake across machines, the hub stopped in the middle of a pause and the older client refused at the door are shown by their tests in the first command, which name the criterion they cover.

On the local store, in a throwaway home seeded at schema 12: `amoeba list` migrates it and shows every question and wake with machine `local`, and the 242 and 244 walkthroughs behave as before.

## Risk Assessment

### Technical Risks

- **One piece of work starting twice.** A second `sq run --resume`, a second answering run for one question, or two wakes of one repo.
- **The largest refactor in the initiative.** About twenty transactions move out of the client-run modules, and a moved check that is subtly different changes what the PM's install does today.
- **The work flag is on every call.** A slow query there slows everything.

### Mitigation Strategies

- Every start is behind a claim taken in one statement inside the hub's one write lock, and each claim has a test with three callers at once and a test with a lost reply. Squadron's own run lock still refuses a second resume.
- The client-run modules keep their order of work, and the existing suite runs unchanged on `LocalSteps` apart from the five kinds of edit listed. The step functions are today's store calls moved, not rewritten.
- The flag is four existence queries on indexes, and the load test bounds it on a seeded store.

## Implementation Notes

### Development Approach

Suggested order. Each step leaves the suite passing on the local store.

1. Migration 013, the store functions by machine, and the opener's write.
2. `steps.limits`, `claim_resume` and `wake_due`, with their unit tests.
3. `Steps`, `LocalSteps` and `run_step`. Move the resume and `answer` onto them first: they are the smallest.
4. Move the pause path, one module at a time, ending with `pause_begin`.
5. Move `wake`, `wake_run`, the sweeps and the prune.
6. `work_waiting`, `claim_work`, `work_start`, `resume-run` and the after-step. Delete `request_release` and `wiring_release`.
7. `DoorSteps`, the step names in `wire.protocol`, the flag in `handle_call`, and the fixture's `sq` stubs.
8. The cross-machine tests, the clock test, the load test and the live variants.
9. `rm-machine`, the documents and `update_live.py`.

### Special Considerations

- **Secrets.** A wake command may hold a secret. It is returned only by `wake_read`, to the machine it runs on, and appears in no log line, as today.
- **Message text is data.** A question and a request's result cross the door inside step documents and are treated exactly as in 240.
- **Detached children.** Each is started in its own session with its own logs, as `wake-run` and the held `handle-pause` are today. Nothing waits on them but the wake's reaper thread.
- **Threads on the hub.** Steps share no state between calls. Each runs on its own connection inside the call scope.
- **A machine that leaves while a child is running.** The child started with a client file, so its next step fails with `ClientFileError` and it exits. It never opens the local store, including one that `leave` put back (D3). Its claim on the hub runs out, and the work is closed by `rm-machine`.

## Operator Walkthrough

Done as the person running it. Before 264 only fixtures are joined; the local store behaves the same through `LocalSteps`.

- **Start.** Nothing new to set up. The hook is the same command, `amoeba handle-pause`. On a joined machine it reads its settings from the hub.
- **Normal path.** A run pauses, the hook handles it, and the answerer answers or the question waits on the PM. `amoeba answer` from the run's machine resumes it in that call.
- **Answering from another machine.** The result names the run's machine and when it last called. The run resumes at that machine's next `amoeba` call. If that machine is asleep, the answer waits; `list` from anywhere shows it waiting and where.
- **That machine never comes back.** `amoeba dismiss` closes the question from any machine. `amoeba hub rm-machine` closes everything waiting on it.
- **A resume is refused.** `list` shows the reason. A new `answer` from any machine tries again on the run's machine. So does `amoeba handle-pause <run>` in the run's checkout.
- **The checkout a resume or wake needs is gone.** The start fails and is recorded as `refused` or `start_failed`, with the reason in `list`. `amoeba dismiss` ends the question; `amoeba rm --checkout` clears the checkout. A wake that failed to start is not tried again; sending the request again, once the checkout or command is fixed, starts one.
- **Upgrading the PM's install.** Nothing changes at the merge. The release runs `update_live.py update` as its last step: it backs up the store and config, installs the release and migrates. If its check fails it puts everything back by itself. Each `amoeba-mcp` session open at that moment fails its tools with the store's schema error until it is restarted; the script prints them.
- **Upgrading a joined machine.** The hub goes first. A machine still on the release before this one then gets the upgrade command from every call until it is upgraded. `hub machines` shows its client version and when it last called. Before 264 these are fixtures.
- **The hub is down when the hook fires.** `handle-pause` exits 3 after the retry time and writes the error to that machine's calls log. Once the hub is back, `list` on that machine shows the run as paused with no record and gives the command to handle it.
- **The hub goes down in the middle of a `handle-pause`.** The command stops. What happens next depends on whether the question's row was written. If it was, nothing needs doing: once the hub is back and the claim is `answering_wait_seconds` plus two call bounds old, the next call from that machine starts it again. If the hub went down before the row was written, there is nothing for the hub to hand out: `list` on that machine shows the run as paused with no record, and the PM or an agent runs the command it gives, as for a hook that never fired.
- **A reply carrying claimed work is lost.** The client's retry gets the same items. If the client gave up, the work is handed out again: a resume after 216.5 seconds with the example config, a `handle-pause` once its start is `answering_wait_seconds` old, a wake after `wake_timeout_seconds`.
- **`sq` is broken on a machine.** A resume records `refused` with the reason. A `handle-pause` exits 3 and is started again at most once per `answering_wait_seconds`. After three automatic starts the question waits on the PM as `starts_exhausted`, and is answered or dismissed.
- **The hub's config is broken.** Calls that need it fail with the file and key. Those that do not still do their work, a wake's end and a resume's outcome among them, and print that the hub could not tell whether work is waiting, with the same text.
- **A wake is waiting for a machine that is off.** `send` and `list` name the machine. The request waits for an agent or expires. `amoeba cancel` ends it sooner.
- **A wake's command hangs.** Its wrapper stops it at the deadline, as today. If the wrapper was killed too, the row stops holding off other wakes at its deadline and is deleted with old wakes. The request it was for is not woken a second time; sending it again unchanged asks for a new wake.
- **The hub goes down while a wake's command runs.** The command is not stopped. It runs to its end or its deadline. If the hub is still down when the wrapper records the end, the wrapper exits 3 and the row stays unended until its deadline, then stops holding off other wakes.
- **A resume is cut off after it started the run.** The machine lost power, or `resume-run` was killed. The next call from that machine after the claim runs out starts `resume-run` again. It finds the earlier attempt's file, sees the run has left the pause, and records `resumed`. Nothing is started twice. That holds whichever call it is: `list`, `status` and the next pause's `handle-pause` sweep first, and the sweep leaves an answer with no outcome to its resume attempt. Until that call, `list` from anywhere shows the answer as waiting for that machine.
- **A resume was retried by `handle-pause` and cut off after it started the run.** The outcome on the hub is still `refused`, and nothing hands a refused resume out again. Once the run has moved on, the sweep marks the answer `not_delivered`. The run is fine; the record is wrong, as it is in that case today (D9).
- **An answer is too large for the door.** `handle-pause` exits 3 with the refusal in the calls log. After three automatic starts the question waits on the PM as `starts_exhausted`, and is answered or dismissed.
- **A machine's clock is wrong.** Nothing in the store changes. That machine's own log names and file clean-up follow its clock.
- **A machine is removed.** Its open questions close as `machine_removed`, its waiting answers are marked not delivered, and its wakes end. A wake command still running there is stopped by its wrapper.
- **Old logs and scratch.** Each machine removes its own past `prune_after_days`, at most once an hour, from any `amoeba` call. Deleting the marker file only makes the next call walk.
- **A resume keeps dying before it starts.** After three automatic tries it is recorded as `refused` with the count, and `list` shows it. A new `answer` tries again.
- **Undo.** There is no setting to turn off. On a client, `amoeba leave` (260) goes back to the local store: the set-aside one if the machine had one, or else none, and the next command there starts an empty store as on a new install. That machine can no longer do the work the hub holds for it, so the second step is `amoeba hub rm-machine <machine>` on the hub. It closes the machine's open questions as `machine_removed`, marks its waiting answers not delivered and ends its wakes. Until that is run they wait, and `list` from any machine shows them with the machine's name. For the upgrade itself, `uv run python scripts/update_live.py restore` puts back the store and config as they were just before the update and reinstalls the release from before it. Everything written since the update is lost: answers, decisions, standing answers, messages, sessions and wakes. So it is for an update found wrong soon after. Sessions started since the update are restarted first; the script prints them.

Dead ends found: none. Three limits. The first two are from the architecture. Work for a machine waits until something on that machine calls the hub; each call that causes such a wait names the machine, and each wait ends with its record. And a pause whose `handle-pause` stopped before its row was written is not started again by the hub: it has no record to be read from, so it needs the command `list` shows on that machine, exactly as a missed hook does today. And the upgrade has no undo that keeps what was written after it: the restore is a copy from before the update, as for every migration so far.

One record can still be wrong, and it is not a dead end: a refused resume that `handle-pause` retried, and that was killed after it started the run, ends as `not_delivered` (D9). The answer has a final outcome and nothing waits on it.

Dead ends found by the full-text design review of 20261121, and how each is resolved:

- A resume cut off after it started the run was to be recorded `resumed` from its attempt file. But `list`, `status` and the next pause's `handle-pause` sweep before their after-step, and the sweep marked the answer `not_delivered` first. The sweep now leaves an answer with no outcome to its resume attempt (D6, D9).
- An MCP `reply` or `cancel` no longer started the held question it released, on the PM's own install, until 263. The after-step now runs on both doors in this slice (D10).
- A held question on a run at its answer limit started an answering run before the settle refused it. The limit is now read for a held row and checked before the gather (D4, D5).

## Implementation Notes as built (20261124)

**Verification.** `uv run pytest tests/operations tests/hub tests/store/test_migration_013.py tests/load/test_door_load.py` passes as part of the full suite: ruff format, ruff check and pyright clean; `uv run pytest` 5682 passed, 1 skipped. `uv run pytest tests/live/hold tests/live/waking` 16 passed, the two new two-machine variants among them (hold 45.6 s, waking 10.0 s).

**Load figures** (`tests/load/test_door_steps_load.py`, store seeded with 500 questions and 500 open requests across both machines): 16 clients, two of them `claim_work` callers, 160 calls, slowest 0.020 s, median 0.008 s. On the idle hub each of the sixteen steps once: median 4.8 ms, slowest `pause_begin` 11 ms.

**The by-hand pass.** The cross-machine path the walkthrough steps through (a pause on `alpha`, answered from `beta` with `waiting_on_machine: alpha`, resumed by `alpha`'s next call through its after-step and `resume-run`, `beta` starting nothing) is run as `tests/hub/test_across_machines.py::test_a_pause_on_alpha_answered_from_beta_is_resumed_by_alphas_next_call` on two joined homes, and with real `sq` and models by `tests/live/hold/test_hold_split_live.py`. On a throwaway home seeded at schema 12 (`tests/store/schema_12.py`), `amoeba list members -j` exits 0, the store is at schema 13, and its three questions and two wakes all have machine `local`. The 242 and 244 behaviors pass unchanged in their tests (held questions, waking), now through the after-step.

**Departures.**
- Steps' models are split across `steps/model_base.py`, `models_resume.py`, `models_pause.py`, `models_wake.py`, `models_runs.py`, `models_work.py`, with `models.py` the one table; `pause_begin` is `steps/begin.py`, `question_settle` `steps/settle.py`, `pause_sources` `steps/sources.py`.
- `wake_due` lives in `store.wakes` (D8 updated during 2.5): `claim_wake` calls it and `store` may not import `operations`.
- `steps_for(layout, last, load_config)` is a context manager that opens the local store when there is no client file; it does not yet take door times or a session identity (263 adds those with the tick).
- `rm-machine`'s closing is `store/machine_removal.close_machine_work`, called by `hub/admin.rm_machine` before `machines.remove_machine` in the one transaction.
- The cross-machine tests (8.1, 8.2) run two joined homes in one process against the in-process hub; the live variants run on the subprocess fixture. In the hold live variant `alpha` uses the real `HOME`, which real `sq` needs.
- The seeded load test is its own module beside `test_door_load.py`.
- Bugs found and fixed while building: a kept-result repeat computed the work flag without acting as the caller (`hub/calls.py`); the after-step skipped the clean-up after a `list` with a subject (`wiring_steps.after_operation`); the live tier ran the recorded `cf` that 7c0545ee put on every test's `PATH` (`tests/live/conftest.py`).

**Files over about 300 lines.** `store/sql.py` (551; 543 before the slice, edits to existing statements and two shared clauses only, noted as over and not split). `store/wakes.py` (379, from 278: the wake-due rules and the claim share their private helpers and one transaction). `operations/steps/models_pause.py` (363: the pause steps' request and reply models, one class per shape). `hub/calls.py` (333, from 326), `operations/pause_claim.py` (332, from 308), `wiring.py` (324, from 297), `cli/render/waiting.py` (319, from 307), `store/answers.py` (317, from 296), `store/models.py` (314, from 304): call sites and fields only, the logic in their new modules.
