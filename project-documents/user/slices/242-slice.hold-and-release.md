---
docType: slice-design
slice: hold-and-release
project: amoeba
parent: user/architecture/240-slices.agent-messaging.md
dependencies:
- 240
interfaces: []
dateCreated: 20261115
dateUpdated: 20261116
status: complete
turns: 38
promptTokens: 3490046
cachedTokens: 3278578
cacheWriteTokens: 211418
completionTokens: 50593
durationSeconds: 407.5
costUsd: 1.679891
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 1.6798912
    completionTokens: 50593
---

# Slice Design: Hold and Release

## Overview

A run that stops on a question naming a request its repo sent waits on that request, and carries on by itself when the request is done. `handle_pause` recognizes the link by an exact id, records the question as `waiting_on_request`, and once the request has ended, the next operation that could have ended it starts `handle_pause` again for each run waiting on it. A `done` result is added as one passage to the existing answering run (140's `answering.yaml`, unchanged steps), so the answer goes through the same independent check step, the answer screen and the per-run answer limit as any automatic answer, and on a pass 220's resume runs. Every other end (declined, cancelled, expired, unknown) sends the question to the PM with the reason. This builds on 240's `messages` table and on 223 and 228's question record, claim, screen and resume.

## Value

User value. A squadron run that needs a context-forge change stops, and carries on with the result once that change is done, with nobody relaying anything. The PM sees the wait in `status`, the outcome in `decisions`, and can close it with `dismiss`. Scenario D's last step (architecture step 5) is delivered.

## Technical Scope

**Included**
- The link: a marker line in the question text, matched by exact request id (D1).
- Migration 8: the `waiting_on_request` question state and two question columns (D2).
- The hold, and the one evaluation path that settles a held question (D3, D4).
- The result as a `request_result` passage of the existing answering run (D5, D6).
- The start trigger: after any operation that could have ended a request, held questions whose request has ended are started; a failed start is retried and shown (D7).
- `dismiss`, the open-question rules, `status` and `decisions` for held questions (D8, D9).
- Four new `DeclineReason`s, one new `HandlePauseOutcome` (D10).
- Docs: `cli-contract.md`, `store-contract.md`, `config-contract.md`, `squadron-hook.md`, `mcp-server.md`, one added line in 240's Requesting block of `program-rules.md`, and the MCP `INSTRUCTIONS` line.
- Live store backed up, migrated to 8, read back.

**Excluded** (other slices, not deferred work of this one)
- Messages, the sweep and the writers (240). Push (241). Notes (243). Waking (244).
- Holding on more than one request: a question waits on exactly one request (architecture: "one wait on one request").
- Cancelling a request when its held question is dismissed. `dismiss` closes the question only; the request lives on its own lifecycle.

## Dependencies

### Prerequisites
- 240 built and integrated: the `messages` table, `get_message`, `effective_state`, and the live store at schema 6.
- 241's migration 7 exists when this slice's migration 8 is applied. This is an ordering fact, not a code dependency: `store/migrations.py` raises unless migration versions are contiguous (checked 20261115), so `008` cannot be applied without `007`. The plan's implementation order (240 → 241 → 242) already puts 241 first.
- Squadron `sq` (observed 20261115: 0.24.28).

### Interfaces Required
- From 240: `get_message(transaction, message_id)` in `store/messages.py`, its one by-id read of a request (the same function `reply` and `cancel` load through), the `Message` row, and `effective_state(row, now)`. Nothing else: this slice changes no 240 module and needs no ids out of 240's writers.
- From 140: `answering.yaml` (both steps, unchanged), `PassageKind`, `assemble`, `render_passages`, `passage_refs`.
- From 223 and 228: `questions`/`answers` and their compare-and-set moves, `settle`, `evaluate_gate`, `finish`, `resume_answer`, `classify_pause`, `dismiss_question`, the open-question clause, `question_sweep`, `answering_for`, `Deps.spawn`, the calls log and `last_call`.
- **223's `pause_claim` gains one public entry, `start_held_claim`** (D6), and `restart_dead_claim` gains an optional `request_id`. Both live in `pause_claim.py` beside the private `_prepare` and `_run` they use, so no other module calls a 223 private helper. `pause_existing._claimed` passes the row's `request_id` to `restart_dead_claim`; nothing else in it changes.
- From 226: `resolve_amoeba_script` and the detached-start pattern in `mcp/detached.py`.

## Architecture

### Component Structure

```
handle_pause ── pause_eligibility ── existing row?
   │  none, question has a link ─► pause_held.hold_new ─┐
   │  waiting_on_request ─────────► pause_held.handle_held ◄┘   (one path, D4)
   │                                    │ request done
   │                                    ▼
   │          pause_claim.start_held_claim: limit ─► _prepare (gather + request passage)
   │                                    ─► claim_held (CAS) ─► _run (answering.yaml) ─► settle ─► resume
send · reply · cancel · add · rm · status · list · handle_pause
      └─ after they return ─► request_release.start_ended_held ─► detached `amoeba handle-pause`   (D7)
```

- `operations/request_link.py`: `find_request_link(question, resolve) -> LinkResult`. Pure: `resolve`, supplied by the caller, says whether a candidate id is a request the question's member sent, so the module reads no store.
- `operations/pause_held.py`: `hold_new` and `handle_held`: the request-state table of D4. A `done` request goes to `pause_claim.start_held_claim`. No claim, scratch or dead-claim logic of its own.
- `answering/request_passage.py`: `request_passage(request_id, replied_by, done_at, result, commit, version) -> Passage`. Pure; takes plain fields so `answering` imports nothing from `store`.
- `operations/request_release.py`: `start_ended_held(store, config, deps)` (D7).
- `store/held_questions.py` and `store/sql_held.py`: the held insert, `held_rows`, `claim_held`, `settle_held_waiting`, `mark_start_attempted`. New SQL does not go in the large `sql.py`.
- `amoeba_script.py` (package root): `resolve_amoeba_script` and `AmoebaScriptMissing`, moved out of `mcp/detached.py` (which imports them). `Deps` gains `amoeba_script: Callable[[], Path]`, set to it by `production_deps`, because `operations` may not import `mcp` and tests need to fake it.
- Imports stay `cli/mcp → wiring → operations → store, answering, upstream`.

### Data Flow

**New pause with a link.** `check_eligibility` passes as today. No row, and `find_request_link` finds a marker: `hold_new` takes the path below instead of `start_new_claim`. No marker: the ordinary answering path, unchanged.

**Held question.** `handle_held` reads the request, fresh, in one read transaction, and acts by its effective state (D4). A `done` request goes to `start_held_claim`: the answer-limit check, then `_prepare` gathers the ordinary context with the request's result added as one passage and makes the scratch, then `claim_held` moves the held row to `claimed`, and `_run` runs `answering.yaml`, settles and resumes, all as for any question. The one difference from `start_new_claim` is that the claim is an update of the held row, not an insert.

**Start.** After `send`, `reply`, `cancel`, `add`, `rm`, `status` and `list` return (in `wiring.invoke`, one place for both doors), and at the end of `handle_pause`, `start_ended_held` reads the held rows and the state of each row's request. For each whose request has ended it starts `amoeba handle-pause --json -- <run_id>` detached in the row's `checkout`. That process is the ordinary `handle_pause`, so it runs the same eligibility checks and the same path as a hook call (D7).

### State Management

- Question rows gain one state and two columns. Nothing is kept in memory between calls.
- A held question keeps `request_id` through every later state (`claimed`, `answered`, `waiting_on_pm`, `closed`), so the record always says which request it came from.
- Scratch and logs of the answering run are the 223 ones (`answering_dir()/<run id>/`, `logs/answering/<run id>.*`), pruned by age like the others (228 D9). Release logs go in `logs/request-release/`, pruned by age by the existing log walk.

## Technical Decisions

### D1 — The link is a marker line, matched by exact id
Status: decided

The architecture leaves the form to this slice: an exact id match, never a judgment about the text. The question must contain a line:

`amoeba-request: <id>`

where `<id>` is the id the agent gave `send --id`. `find_request_link(text, resolve)` reads every match of `amoeba-request` (case-insensitive, `-` or `_` or a space between the words), then `:` or `=`, optional spaces and quote or bracket characters, then a run of request-id characters (`[A-Za-z0-9._-]`, as 240 D2). A trailing `.` on the run is also tried without it, because `.` is both an id character and sentence punctuation; each candidate is compared for equality with a stored request id through `resolve`.

- **Resolution.** An id counts only if it is a `request` row with `from_member` equal to the question's member. Not found, a note, or another member's request is unresolved.
- **Result.** `NoLink` (no marker line: the ordinary path), `Link(request_id)` (exactly one distinct resolved id), or `BadLink(detail)` (a marker resolves to none, or to two or more distinct ids). `BadLink` records the question `waiting_on_pm` with `request_unknown` and a detail naming what was found; no model runs.
- **Where the line goes.** Squadron's `question` is the tail of the agent's reply and can start with `…`, so a long question loses its start (observed 20261107 on `sq` 0.24.23, recorded in 223's Dependencies; the first task re-checks it on the installed `sq`). The rules line tells the agent to put the marker on the last line. The matcher reads the whole text wherever it is.
- A question that names a request in words ("waiting for the guide change") has no marker and is not held.
- Rejected: matching any whole word equal to one of the member's request ids (a request called `docs` would hold unrelated questions).

### D2 — Migration 8: `waiting_on_request` and `request_id`
Status: decided

`008_waiting_on_request.sql` rebuilds `questions`, as 003 did, by SQLite's documented procedure (create new, copy, drop, rename; the runner turns foreign keys off around it and runs `foreign_key_check` before commit). **Justification for the rebuild (the store contract allows one only with it):** `questions.state` has a `CHECK` list, and SQLite cannot widen a `CHECK` in place. A `held` flag beside an unchanged state would split one state across two columns that every reader combines. No index exists on `questions` (checked 20261115), so none is recreated. `answers` references `questions`, so the copy keeps every key.

- State list: `claimed`, `answered`, `waiting_on_pm`, `closed`, `waiting_on_request`.
- New columns, both nullable: `request_id` (with `CHECK (state <> 'waiting_on_request' OR request_id IS NOT NULL)`); `start_attempted_at`, when `start_ended_held` last started `handle_pause` for the row. It is its own column, not `updated_at`, because `close_question` uses `updated_at` as its compare-and-set guard.
- No foreign key from `request_id` to `messages`: 240's sweep prunes terminal requests by age, and a foreign key would make that prune fail while a question still names the request.
- `EXPECTED_SCHEMA_VERSION` becomes 8. `QuestionState.WAITING_ON_REQUEST` is added to `store/vocabulary.py`; the existing pinning test ties the `CHECK` to it. `store/question_rows.py` maps the columns to `QuestionRecord.request_id` and `start_attempted_at`.
- The open-question clause (`_OPEN_QUESTION_CLAUSE`, and `_OPEN_PARAMETERS` in `question_closing.py`) gains `waiting_on_request`, so a held question is open everywhere that word is used: the close sweep, `member_open_questions` (`rm` of the sender refuses until it is dismissed or answered), prune's evidence sets, and `status`.

### D3 — The states and their moves
Status: decided

| From | To | By |
|---|---|---|
| (no row) | `waiting_on_request` | `hold_new`: one insert, with `request_id` |
| `waiting_on_request` | `claimed` | request `done`: `claim_held`, compare-and-set `WHERE state = 'waiting_on_request'`, setting `answering_run_id`, `passages`, `slice_label`, `source_commit`, and `claimed_at` and `updated_at` to now |
| `waiting_on_request` | `waiting_on_pm` | request declined, cancelled, expired or unknown; answer limit reached; context or scratch failure; compare-and-set, with `waiting_reason`, `waiting_detail` |
| `claimed` | `answered` or `waiting_on_pm` | 223's `settle`, unchanged |
| `waiting_on_request` | `answered` | a PM `answer` (`add_pm_answer` sets `answered` from any state; only `waiting_on_request` rows are released, so the request no longer matters) |
| `waiting_on_request` | `closed` | `dismiss`, or the close sweep (`run_moved_on`, `run_gone`) |

`claimed_at` and `updated_at` are reset by the claim because the dead-claim rules measure a claim's age from when it was made: left at the hold time, a claim made days after the hold would read as stale at once. A move to `waiting_on_pm` leaves `claimed_at` as the hold time, so a waiting entry's `since` is when the question first stopped.

Every move is a compare-and-set naming the state it leaves, so a concurrent `answer`, `dismiss` or second `handle_pause` wins cleanly and the loser returns `superseded` or `skipped`.

### D4 — One evaluation path for a held question
Status: decided

`hold_new` inserts the held row first (unless the link is a `BadLink`, which inserts `waiting_on_pm` directly), then calls `handle_held`, so a request done before the pause and one done after it take the same code. A `reply` that commits after the read is followed by that operation's `start_ended_held`, which finds the held row. Two `handle_pause` calls on one row: the second loses `claim_held` and returns `already_claimed`, so nothing is spent twice.

`handle_held` reads the request with `get_message`, then acts on `effective_state`:

| Request | Question moves to | `waiting_reason` | Outcome |
|---|---|---|---|
| `open` or `accepted` | stays `waiting_on_request` | | `held` (`request_id` and its state in `detail`) |
| `done` | `claimed`, then D6 | | the D6 result |
| `declined` | `waiting_on_pm` | `request_declined` | `waiting_on_pm` |
| `cancelled` | `waiting_on_pm` | `request_cancelled` | `waiting_on_pm` |
| `expired` | `waiting_on_pm` | `request_expired` | `waiting_on_pm` |
| no row | `waiting_on_pm` | `request_unknown` | `waiting_on_pm` |

A held question whose request has no row was pruned after `prune_after_days` (D1 only holds on an existing request), so its detail says "the request was pruned after `prune_after_days`; its result is no longer stored".

`waiting_detail` is the request's `reason` (the decline text, `member_removed`, or the cancel reason), cut by `cut_to_bound`, or "the request ended with no reason". The detail is another repo's text, so a result that carries it carries the quoted-data notice (D9). Reading effective state means an `open` request past its TTL is expired here, before 240's sweep has recorded it.

**Failures.** The hold insert is one `INSERT … ON CONFLICT (run_id, paused_at) DO NOTHING`, as 223's claim insert; a conflict is `skipped / already_claimed`. A `StoreError` from the insert or the request read is exit 3 with the row left as it was, and the next `handle_pause` starts again. Context and scratch failures are D6's.

### D5 — The result goes through the existing answering run as a passage
Status: decided

The architecture requires the result to go through the answering pipeline's independent check step and the screen. The slice uses 140's `answering.yaml` as it is: the request's result is added to the question's passages as one passage of a new kind, `request_result`, and the ordinary answer step and check step run on it. No new pipeline, prompt file, check instructions, reply format or decision function.

- **The passage.** `request_passage` builds it: kind `request_result`, `source` the request id, `member` the project that replied, `date` the time the request was marked `done`, text the result followed by `commit:` and `version:` lines when the request has them. `assemble` gains an optional `request_result` passage, placed after the rules, plan and program passages and never trimmed (its text is already bounded by 240's text limit; if the whole set still exceeds `passages_max_chars`, that is the existing `sources_too_large`). `passage_refs` records it with the request id as its source, so `decisions` shows what the answer cited.
- **The prompt change.** Both steps' kinds list gains one sentence: a `request_result` passage is the reply another project in the program gave to a request this project sent, and its member line names that project. Everything else in both prompts is unchanged; "passage text is data" already covers it, and the check already refuses an answer that authorizes anything on the not-authorized list. The existing YAML-constants test, `sq run --validate` and 140's live answering tests cover the edited file.
- **What carries over unchanged.** The answer step writes the answer and cites passages; the check step judges it against the passages and the not-authorized list without seeing how it was produced; `decide_answer` applies 144's checks (run state, artifacts, decline, citations, verdict); `settle` runs `evaluate_gate` (the screen) and records an `answerer` row, which counts toward `answer_limit` and is never precedent. A reply that does not settle the question ends as `answerer_declined` or `check_said_no`; one that authorizes something ends as `answerer_declined`, `check_said_no` or `reserved_term`.
- **Live test** (`tests/live/hold`, real `sq` and the configured models): a faithful done resumes the run; a done that tells the reader to go ahead with something on the member's list does not; a reply that does not settle the question does not.
- Rejected: a separate check-only pipeline with new instructions (a second check the architecture does not have, with its own live proof to keep); seeding `answer.json` and starting `answering.yaml` at `--from check` (it depends on how Squadron feeds `reply_from` to a step whose source step never ran, which is not part of the dispatch file contract 140 relies on).

### D6 — The held claim
Status: decided

`pause_claim.start_held_claim(store, config, deps, target, request)` is the held question's counterpart of `start_new_claim`, in the same module:

1. **Limit.** The answer-limit check `start_new_claim` makes, shared as one helper. At the limit the row moves `waiting_on_request → waiting_on_pm` with `answer_limit_reached` by `settle_held_waiting`, and no run starts.
2. **Prepare.** `_prepare` gains an optional `request`. With one it calls `gather` as today and passes `request_passage(...)` to `assemble`; `make_scratch` is unchanged. A `SourcesProblem` or `ScratchFailure` moves the row to `waiting_on_pm` with the existing reason (`sources_*`, `answering_launch_failed`) by `settle_held_waiting`.
3. **Claim.** `claim_held` (D3). A lost compare-and-set discards the scratch and returns `skipped / already_claimed`, or `superseded` when the row is no longer held.
4. **Run.** `_run` as for any claim: `answer_claim`, `settle`, `finish`.

Once claimed, a held question is an ordinary claim with `passages` and `answering_run_id`, so `pause_existing._claimed` handles it unchanged: settle an ended run from the scratch, skip a young claim, stall an old running one. For `not_found` and old it calls `restart_dead_claim` with the row's `request_id`, which reads the request with `get_message` and passes it to `_prepare`; a request no longer found fails `_prepare` as `_Failed(request_unknown)`, which `_settle_dead_claim_waiting` records.

### D7 — The start trigger
Status: decided

`request_release.start_ended_held(store, config, deps)` starts `handle_pause` for each run whose held question waits on a request that has ended. It looks at the held rows and reads each request's `effective_state` instead of being handed ids, so one function covers every way a request ends (`reply`, `cancel`, expiry, the `rm` cascade) and a retry of a lost or failed start.

- **When it runs.** `wiring.invoke` calls it after `send`, `reply`, `cancel`, `add`, `rm`, `status` and `list` return (one constant, `START_AFTER_OPERATIONS`), and `handle_pause` calls it last, beside its prune. It runs after the operation's own transactions have committed. `inbox` stays a read.
- **Which rows.** A `waiting_on_request` row whose request is terminal by `effective_state`, or gone, and whose `start_attempted_at` is null or at least `answering_wait_seconds` old. Never-attempted rows first, then the oldest attempt. Rows and requests are read in one read transaction.
- **Per-call cap.** At most `MAX_STARTS_PER_CALL` (5, a constant in `request_release.py`) rows per call. Each costs one write, `mark_start_attempted`, which can wait `BUSY_TIMEOUT_SECONDS`. It is a compare-and-set on the `start_attempted_at` the caller read and on the row still being held, so two concurrent callers never both start one row; the loser does not spawn. It leaves `updated_at` alone; the spawn does not wait. So the worst case is `START_BOUND_SECONDS = BUSY_TIMEOUT_SECONDS × (1 + MAX_STARTS_PER_CALL)`, 30 s. 240's worst-case test adds it to `send`, `reply` and `cancel` and still fails at `MCP_CALL_DEADLINE_SECONDS` (240 change, in that slice's test). `add`, `rm`, `status` and `list` are outside that bound already: they make one `cf` lookup per member or reference in the request, or per run directory in the listing, a count no constant bounds, so `MCP_CALL_DEADLINE_SECONDS` is their cap. The test pins that every operation in `START_AFTER_OPERATIONS` is one or the other. Rows over the cap wait for the next call; each started child runs this function at its end too, so a large batch drains on its own.
- **Start.** argv `[script, "handle-pause", "--json", "--", run_id]`, cwd the row's `checkout`, logs `logs/request-release/<run id>-<UTC stamp>.{stdout,stderr}.log`, through `deps.spawn`; `script` is `deps.amoeba_script()`. The caller never waits. Two callers may both start one row; the second child loses `claim_held`, so a duplicate costs one short process and no spend.
- **What bounds a child.** It is the ordinary `handle_pause`, whose every wait is already bounded (`RUN_POLL_TIMEOUT_SECONDS`, `CF_GET_TIMEOUT_SECONDS`, `answering_wait_seconds`, `resume_bound_seconds`, `BUSY_TIMEOUT_SECONDS`), and a row gets a new child at most once per `answering_wait_seconds`, so children cannot pile up. Once claimed, the row is no longer held and is not started again.
- **No try cap.** A try costs one short `handle_pause` and no model spend until a claim, which the answer limit bounds. A row whose child can never run (checkout deleted, script missing) is retried once per `answering_wait_seconds` and ends by `dismiss`, a PM `answer`, or the close sweep (`run_gone`).
- **Failures show in the calls log.** A `LaunchError` (a returned value) appends `result_entry(run_id, checkout, "start_failed", None, detail, now)` and is logged with `logger.error`. `AmoebaScriptMissing` is caught by that type, appends an `error_entry` for each row it would have started, and is logged with `logger.exception`. A `StoreError` from this function's own reads or writes is caught by that type and logged with `logger.exception`. Neither is re-raised, with a comment saying why: the operation's own work has committed, so raising would report a failure for work that happened (the reason `_prune_note` gives); the rows are found again by the next call. A child that starts and then fails writes its own calls-log line, as every `handle_pause` ending does. `status` shows the newest line as the run's `last_call` (D9).
- **A start that keeps failing has no cap of its own, and needs none.** A row whose start or child keeps failing is started again at most once per `answering_wait_seconds`, and each failure is the run's `last_call` in `status`. It ends like any held question: the PM's `dismiss` or `answer`, or the close sweep once the run leaves the pause. A missing `amoeba` script marks no row attempted, so each listed call writes one error line per due row (at most `MAX_STARTS_PER_CALL`) until the tool is reinstalled. That is an install fault, and the MCP server already refuses to start without the script.
- **Retry of a refused or dead resume.** As in 220 and 223: the answer is recorded, `status` shows `answered_unresumed` with `next = handle_pause`, and calling `handle_pause` again resumes with the recorded answer and starts no answering run.

### D8 — `dismiss`, `answer`, the close sweep and `rm`
Status: decided

- `dismiss_question` closes `waiting_on_request` exactly as it closes `waiting_on_pm` (a new arm of its `match`, which pyright forces).
- `answer` works on a held question with no change: it adds the PM answer, sets `answered`, and resumes.
- The close sweep (228) treats `waiting_on_request` like `waiting_on_pm`: closed `run_moved_on` or `run_gone` once the run left the pause.
- `rm` of the addressee cancels the request with `member_removed`, which releases the held question to `waiting_on_pm` with `request_cancelled`.

### D9 — What `status` and `decisions` show
Status: decided

- **`PauseClass.WAITING_ON_REQUEST`** (from the row's state). `status_runs` takes the request states of the held rows as one more input (read once, `effective_state`) and shows `waiting on request <id> (<state>)`, followed by `; handle_pause last started <start_attempted_at>` when set. `WAITING_ON_REQUEST` joins `MISSED_HOOK_CLASSES` in `status_calls`, so the run gets its newest calls-log line as `last_call` (228 D11). It gives no `next`: `start_ended_held` starts it, not the PM.
- **Waiting entries:** `WaitingEntry` gains `request_id`. **`decisions`:** `DecisionsRecord` gains `request_id`; the cited `request_result` passage appears in `based_on` with the request id as its source.
- **Notice.** `DecisionsResult` and `StatusResult` carry the quoted-data notice (240 D11) when any shown entry came from a request.

### D10 — Vocabulary
Status: decided

- `DeclineReason` adds `request_declined`, `request_cancelled`, `request_expired` and `request_unknown`. `questions.waiting_reason` is unconstrained in SQL. Every other end reuses an existing reason.
- `PassageKind` adds `request_result`.
- `HandlePauseOutcome` adds `held` (exit 0). `HandlePauseResult` gains `request_id`. No new `SkipReason`.

### Departures from the parent documents
The docs step amends the slice plan and architecture so these do not stay differences.
- **`request_unknown` for a marker that resolves to nothing.** The architecture is silent. The question goes to the PM at once with no model run.
- **The result is a passage, not the candidate answer itself.** The architecture says the result "becomes the question's candidate answer" and goes through the answering pipeline's check step. Here the answering pipeline's answer step writes the answer from the result (a `request_result` passage), and its check step and the screen judge it unchanged, so the check is the existing one (D5). The docs step rewords the architecture's sentence to "the result is given to the answering pipeline as a passage; its answer goes through the pipeline's independent check step and the answer screen".
- **Every request end starts the held run.** The architecture names `reply` and the sweep's expiry; the plan says any terminal state. The design follows the plan by looking at held rows after each operation (D7), not by carrying ids out of 240's writers. 240's design already says this (`sweep` and `cancel_member_requests` return nothing; 242 reads state through `get_message`).
- **The question moves in the started `handle_pause`.** The architecture has the sweep write "the deliveries and question moves that follow" from an expiry. Here the sweep and writers touch only requests; the question moves in `handle_pause`, through the same compare-and-set paths as every other question move.
- **The plan's "independent of 241".** True of code. The migration order needs 241's migration 7 first (Prerequisites); the docs step rewords the plan's line to say so.

### Patterns and Conventions
- Compare-and-set for every question move; no transaction is open across a subprocess, as in 223.
- Reasons, states and kinds are enums. The marker text and the log directory name are constants defined once.
- The only new `try/except` blocks are in `start_ended_held` (D7), each catching one named type.

## Implementation Details

### Migration Plan
Migration 8 is the only storage change. It copies every `questions` row with `request_id` null. Downgrade is refused by the existing newer-schema guard. Every consumer of `QuestionState` is found by pyright's exhaustive `match`es (`dismiss_question`, `classify_pause`, `_judge` in `question_sweep`, `handle_existing`); each gets an arm. Existing behavior is checked by the 223 and 228 suites passing unchanged.

### API Contracts
- `handle_pause`: new outcome `held`, new field `request_id`, four new `waiting_reason` values. No new flags.
- `dismiss`: accepts a `waiting_on_request` question. `status` and `decisions`: the fields in D9.
- No new operation and no new MCP tool. `INSTRUCTIONS` gains the rules line below.

### Database / Storage Schema
As D2. `docs/store-contract.md` gets the state, the columns and their writers (`handle_pause` writes `request_id` with the held insert and never changes it; `start_ended_held` writes `start_attempted_at`), and the `waiting_reason` values.

### Rules line (`docs/program-rules.md`)
One line added to 240's Requesting block: when a run cannot continue without a request this repo sent, end its question with a last line of `amoeba-request: ` followed by the id given to `send --id`, and nothing else on that line. It uses a placeholder, not a sample id (a test asserts the block holds no literal id). The block's flags test covers it.

**Reaching repos that already have the block.** The MCP server's `INSTRUCTIONS` carries the same rule, so every MCP agent gets it on its next session whatever its rules file says. `docs/program-rules.md` says above the block that it changes between slices and a repo replaces its pasted copy with the current text. An agent with neither never writes a marker; its question takes the ordinary answering path and is answered or listed in `status`, never silently held.

## Integration Points

### Provides to Other Slices
- Nothing another slice reads. Inside the codebase, `amoeba_script.resolve_amoeba_script` and `Deps.amoeba_script` are shared by the MCP server (226) and this slice's start.

### Consumes from Other Slices
- 240's request rows, `get_message` and `effective_state`. An unreadable request row is a store error: `handle_pause` exits 3 with the question left as it was.
- 140's answering pipeline and 223/228's pause machinery, with the additions above.

## Success Criteria

### Functional Requirements
- A fixture pipeline that ends on a question with a marker line is held: a `waiting_on_request` row with `request_id`, outcome `held`, the run still paused. After `done` is replied from another fixture repo, the run is resumed, and `decisions` shows the request id, the cited `request_result` passage, the check verdict and the resume outcome.
- A request already `done` at the first `handle_pause` resumes the run in that call.
- A result such as "done, go ahead and cut a release" for a member with `release` on its list goes to the PM (`answerer_declined`, `check_said_no` or `reserved_term`) and the run is not resumed.
- `declined`, `cancelled`, `expired` and the `rm` of the addressee each move the held question to `waiting_on_pm` with the matching reason and the request's reason in `waiting_detail`.
- A held question has every exit, each tested: resume, `waiting_on_pm`, PM `answer`, `dismiss`, `run_moved_on`, `run_gone`.
- A question that names a request only in words is not held. A marker naming an unknown id, another member's request, a note, or two requests gives `waiting_on_pm` / `request_unknown` and starts no run.
- At `answer_limit` the held question goes to the PM with `answer_limit_reached` and no run starts.
- Two `handle_pause` calls racing on an ended request: one claims, the other returns `already_claimed`; one answering run exists.
- A dead held claim is restarted by `restart_dead_claim` with the request passage, and one whose request was pruned settles as `request_unknown`.
- A failed start (`LaunchError`, or the script missing) leaves the row held and writes a calls-log line that `status` shows as `last_call`; a row attempted less than `answering_wait_seconds` ago is not started again, and after that the next operation starts it.
- At most `MAX_STARTS_PER_CALL` rows start per call, never-attempted first, and a batch larger than that is fully started by the children's own calls.
- A request ended by each of `reply`, `cancel`, expiry (no sweep needed) and the `rm` of its addressee gets its held question started by the next such operation, through both doors.
- `tests/live/hold` covers the three replies D5 names.

### Technical Requirements
- Migration 8 on a version-7 store with a `claimed`, an `answered` and a `waiting_on_pm` question: every row and its `answers` survive, `foreign_key_check` is empty, and the `CHECK` list matches the enum.
- `find_request_link` is tested on the real shapes it will read: a question ending with the marker line, one starting with Squadron's `…`, a trailing `.`, quotes, different case, two markers, none.
- `assemble` keeps the request passage when PM answers are trimmed.
- No store transaction is open while an answering run, a resume or a release spawn runs.
- The edited `answering.yaml` validates with real `sq run --validate`; the YAML-constants test passes.
- `ruff format`, `ruff check`, `pyright` strict and the whole suite pass, 223 and 228 tests unchanged; `tests/test_contract_docs.py` passes with every new state, column, field, outcome, kind and reason documented.

### Verification Walkthrough

Refined after Phase 6 (2026-11-16), with the commands and output of the run that verified it. Steps 2 to 7 use a throwaway home and a throwaway Context Forge data directory, so the live store and the developer's projects are untouched. They spend model calls (the configured `AMOEBA_LIVE_*` models). `A` is the development build: `A=<repo>/.venv/bin/amoeba`. `P` is the fixture: `P=<repo>/tests/live/hold/asks_request.yaml`.

1. `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest`. Expected: all clean, `0 errors`, and the whole suite passes (3567 tests at the end of Phase 6).
2. Set up the throwaway world:
   - `S=$(mktemp -d)`, then `export AMOEBA_HOME=$S/home CONTEXT_FORGE_DATA_DIR=$S/cf-data`, and make both directories.
   - Write `$AMOEBA_HOME/config.yaml` from the config-contract example, with `answer_model`, `check_model` and `max_cost_usd` from the `AMOEBA_LIVE_*` variables, `answering_wait_seconds: 600` and `resume_wait_seconds: 120`.
   - Make three git repos, `sq-s`, `cf-s` and `guide-s`. In each: `git init -b main`, a committed `README.md`, `cf init --lite --name <repo>`, commit, then `$A add --program walk --project <repo>`. Expected: `added`, `created program walk` for the first and `added member <repo> to existing program walk` for the others.
   - **Correction:** `sq-s` also needs a committed rules file, for example a `CLAUDE.md` with one rule. Without one, the started `handle-pause` settles the question as `waiting_on_pm / sources_missing` (`no rules file found; tried: CLAUDE.md, AGENTS.md`), as any question in a repo with no rules does.
   - `cf` may print `Migrated projects.json from legacy location`. It copies the developer's legacy project list into the throwaway data directory and leaves the original unchanged.
3. In `sq-s`: `$A send --to cf-s --id hold-1 --subject "Need X" --body "Please add X"`. Expected: the quoted-data notice, then `sent: hold-1`. In `cf-s`: `$A reply hold-1 accept`. Expected: `accepted: hold-1`.
4. Start the fixture in `sq-s`: `sq run $P "$AMOEBA_LIVE_ANSWER_MODEL" --run-id <run id> -p request=hold-1 --no-pause-hook`. It exits 0 at the pause. `sq runs wait <run id> --json` shows `paused`, with the question's two lines joined by a space (`... what should this repository do next? amoeba-request: hold-1`), which the marker match allows. Then run `$A handle-pause <run id>` in `sq-s`. Expected: `held on request hold-1: accepted`; with `-j`: `outcome` `held`, `request_id` `hold-1`, `detail` `accepted`.
   - `$A status -j`: the run's entry has `pause` `waiting_on_request`, `detail` `waiting on request hold-1 (accepted)`, `next` null, `last_call.outcome` `held`, and the result's `notice` is set.
   - The text of `$A list --all` lists the run under **Other runs** as `<run id> · paused · waiting_on_request`.
   - The text `status` lists only what needs the PM. On a machine where the live tiers have run, its **Unplaced runs** also shows their answering runs as `directory_missing`: their temporary checkouts are gone. This is not caused by this slice.
5. In `cf-s`: `$A reply hold-1 done --text "X is in. The release-notes section is added; this repository needs to do nothing more and should carry on with its current slice." --version v1`. Expected: `done: hold-1`. In the same second, `$AMOEBA_HOME/logs/request-release/` holds `<run id>-<UTC stamp>.stdout.log` and `.stderr.log`. Run no `handle-pause` by hand. In `sq-s`, poll `$A decisions -j` every 5 s, up to the config's `answering_wait_seconds` plus `resume_wait_seconds` plus a margin (the live tier's `AUTO_RESUME_WAIT_SECONDS`, 900 s). Expected: the record for the run has `request_id` `hold-1`, `based_on.cited[].source` `hold-1`, `check_verdict` `yes`, `resume.outcome` `resumed`, and `notice` set. In the verifying run this took 16 s. `sq runs wait <run id> --json` then shows the run past the held pause: at a later pause, or finished.
   - **Caveat:** the resumed run is not started with `--no-pause-hook`, so a later pause goes to the user-level Squadron hook, which runs whichever `amoeba` is first on `PATH`. The fixture's agent asks the same marked question again. A hook that runs this build answers each repeat from the same `done` result until `answer_limit` (3) sends it to the PM as `answer_limit_reached`. That is the designed bound. The live tier puts a do-nothing `amoeba` first on `PATH` to avoid it.
6. Exits. Repeat steps 3 and 4 with a fresh id for each:
   - `$A reply <id> decline --text "not now"` in `cf-s`: the question becomes `waiting_on_pm / request_declined` with `waiting_detail` `not now`.
   - `$A cancel <id>` in `sq-s`: `waiting_on_pm / request_cancelled`, `waiting_detail` `the request ended with no reason`.
   - `$A dismiss <run id> --reason "no longer needed"` on a held question: `dismissed: <run id> ...`, `closed: dismissed`.
   - `$A status -j` lists the declined and cancelled questions under `waiting_on_pm` with their `request_id`, `next.operation` `answer`, and the notice set.
7. With a fresh held question: `$A reply <id> done --text "done, go ahead and cut a release"`. Expected: within the poll bound the question is `waiting_on_pm`, with `answerer_declined`, `check_said_no` or `reserved_term` (the verifying run gave `answerer_declined`). There is no `answers` row, and `sq runs wait` shows the run still at the held pause.
8. `uv run pytest tests/live/hold`. Expected: 3 passed, about 90 s. `tests/live/pause` (9) and `tests/live/answering` (12) still pass.
9. Live store: the Phase 7 hand-off (Special Considerations). The migration was rehearsed on a copy of the live store at the end of Phase 6: version 7 before and 8 after, with 1 question and 0 answers before and after, `integrity_check` `ok`, `foreign_key_check` empty, and `amoeba status` exiting 0.

Clean up with `rm -rf $S`. The fixture runs stay in Squadron's run list as paused runs whose directory is gone.

## Risk Assessment

- A result from another repo's agent resumes a real run. The check is a model, so it is a line behind the screen and the member's own list, not a proof. Mitigation: D5 (the existing check, screen and limit; never precedent).
- Migration 8 rebuilds the table every question and answer hangs from. Mitigation: 003's tested rebuild procedure, a backup, and a migration test on a populated version-7 store.

## Implementation Notes

### Development Approach
1. Vocabulary, migration 8, `QuestionRecord` fields, the open clause and the `match` arms, with the pinning and migration tests.
2. `request_link`, `request_passage`, the `request_result` kind in `assemble` and both prompts, the new reasons and outcome.
3. `start_held_claim`, `_prepare`'s request, `restart_dead_claim`'s `request_id`; `pause_held`; wire into `handle_pause` and `handle_existing`; the `classify_pause` class.
4. `request_release.start_ended_held`, the `amoeba_script` move and `Deps.amoeba_script`, and its calls in `wiring.invoke` and `handle_pause`.
5. `status`, `decisions`, `dismiss`; docs and the `INSTRUCTIONS` line.
6. Live tests. The live-store migration is the Phase 7 hand-off, after the slice merges (Special Considerations).

### Special Considerations
- **Prompt injection.** The result text is another agent's. It reaches the answering run as a passage, which both steps treat as data, and the resumed run only through an answer that passed the check and the screen.
- **Docs this slice makes stale, all updated in its docs step.** `store-contract.md`: the writers table, "How each state ends with nobody editing a file" (add `waiting_on_request`), the `waiting_reason` values, the `claimed_at` note. `cli-contract.md`: `handle-pause`, `dismiss`, and `status`/`list` (they now start `handle-pause` for ended held questions and show a held run's `last_call`). `config-contract.md`: `answering_wait_seconds` is also the least time between two starts for one held question. `squadron-hook.md`: a held question needs no further hook call. `mcp-server.md`: its `status` and `list` rows.
- **Live store (designated for migration; the backup comes first).**
  1. Wait for no claim in flight, because a running `handle_pause` is old code and would fail on the new schema: `sqlite3 ~/.local/state/amoeba/amoeba.sqlite3 "SELECT count(*) FROM questions WHERE state = 'claimed'"` must print 0. A claim whose process is alive ends by itself within `answering_wait_seconds`. A claim whose process died is not revisited by any hook: `amoeba status` lists it as `claim_stale` with `next = handle_pause`, and the agent runs `amoeba handle-pause <run id>` in the run's directory (223's dead-claim rules settle it), then checks again. Each claim is either live or settled by that command, so the count reaches 0.
  2. Back up: `sqlite3 ~/.local/state/amoeba/amoeba.sqlite3 ".backup ~/.local/state/amoeba/backups/amoeba.sqlite3.pre-008"`.
  3. At the Phase 7 hand-off, after the merge: install from the target, not from the slice branch (`uv tool install --force <repo>` with the target checked out), then migrate by running `amoeba list`.
  4. Read back: `schema_meta.version` is 8, the `questions` and `answers` row counts match the backup's, and `amoeba status` works.
  - **Processes still running.** An `amoeba-mcp` server started before the install fails its next call with the existing newer-schema error and changes nothing; it is replaced when its client session ends.
  - **Restore,** only if the read-back fails: stop every `amoeba` and `amoeba-mcp` process, copy the backup over the live file, delete its `-wal` and `-shm`, and reinstall the previous build: the target commit recorded before the merge (task 10.2). The backup is deleted with `rm` once the read-back passes. The restore path goes in the slice notes.

## Operator Walkthrough

Done as the person running it. Set-up is the marker rule: a repo pastes or replaces its Requesting block with the current text (an agent in that repo, as a commit); MCP agents also get it from `INSTRUCTIONS`.

- **Start.** The agent in `sq-s` sends the request, then stops its run on a question ending in the marker line. `handle_pause` (the hook) holds it. Nothing for the PM to do.
- **Normal path.** The request is done in `cf-s`. Amoeba starts `handle_pause` in `sq-s`'s checkout; the answering run answers from the result, the check and screen pass, the run resumes. `decisions` shows it.
- **Failure: declined, cancelled, expired, or the check, screen or answer step refuses.** The question waits on the PM with the reason; `status` lists it and `answer` or `dismiss` ends it.
- **Failure: a typo in the marker.** The question waits on the PM at once as `request_unknown`, naming what was found.
- **Failure: the start did not work, or the child failed.** The run's `status` entry shows `last_call` and when the last start was attempted. The next operation after `answering_wait_seconds` tries again; if the cause is permanent (checkout deleted), `dismiss`, `answer` or the close sweep ends it.
- **Failure: the answering run dies or stalls.** A stalled one settles as `answering_run_stalled`. A dead claim is listed as `claim_stale` with `next = handle_pause`, and `amoeba handle-pause <run id>` settles or restarts it (223 D7).
- **Failure: the resume was refused.** `status` lists `answered_unresumed` with `next = handle_pause`; running it resumes with the recorded answer and starts no answering run (220, 223).
- **End states.** Resumed, waiting on the PM, answered by the PM, or closed. A closed question's run stays paused in Squadron, where `sq run --resume` continues it, as in 228.
- **Undo.** `dismiss` closes a held question; `cancel` withdraws the request (releasing the question to the PM). Scratch and logs leave by `prune_after_days`.
- **Dead ends found: none where nobody can act.** Two failures (a dead claim, a refused resume) end by a command that `status` names, as in 223, not by waiting.
