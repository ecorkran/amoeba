---
docType: slice-design
slice: answering-run
project: amoeba
parent: user/architecture/140-slices.question-answerer.md
dependencies:
- 140
- 141
- 142
- 143
interfaces:
- 145
dateCreated: 20261101
dateUpdated: 20261103
status: complete
turns: 31
promptTokens: 3341553
cachedTokens: 3161445
cacheWriteTokens: 180054
completionTokens: 42436
durationSeconds: 431.8
costUsd: 2.921986
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 2.921986300000001
    completionTokens: 42436
---

# Slice Design: answering-run

## Overview

The answerer answers. Each tick, the answering stage that 141 added does three things. It settles finished answering runs. It declines what it cannot answer. It launches an answering run for each pending question, up to the project's cap. A launch assembles 143's passages, prepares 140's scratch directory and journals one `sq_answer` entry on the slice node. In the same store transaction it moves the question record to `answering`. It then starts `sq run` from the scratch directory, with no checkout. When the run ends, a pure function decides from recorded inputs alone: the run's outcome, the two reply files, and the passage ids recorded at launch. A confirmed answer goes to 142's `submit_answer`. Anything else is declined with a distinct reason. Nothing retries.

Two changes reach code 132 owns. One shared reader removes `sq_answer` entries from a slice's journal before the supervisor's latest-entry readers see it, so a PM resolution is accepted while an answering run is in flight, and the answerer's resolution is accepted after one ends. The store's done-guard also ignores `sq_answer` entries.

## Value

User value: milestone 4. A question whose answer is in the project's rules, its plan or an earlier PM answer resumes the run without the PM. The question record shows the question, the answer sent, the passages it cited, the check's verdict and the answering run. A question the answerer cannot ground and confirm reaches the PM as it does today, and the record says why it was declined.

## Technical Scope

Included:

- `CommandKind.SQ_ANSWER`, with its required parameters and its recovery observer, registered in `build_observer_registry` (D2).
- The shared reader `supervision_entries` and its use in `classify`, `run_to_resume`, `checkout_holders`, `dispatch_state` (through `build_view`) and `_resume_count` (D3).
- The store's done-guard ignores `sq_answer` entries (D4).
- The store operation `begin_answering`: journal entry and `pending → answering` in one transaction (D5).
- The launch: passages, scratch directory, the `sq run` argv, spawn without a checkout (D6).
- The pure decide function and the decline reasons it produces (D7, D8).
- Finishing a run: decide, then `submit_answer` or `decline_question` with evidence, then resolve the entry (D9).
- The stage's passes and their place in the tick, with the concurrency cap (D10).
- Migration `015`: answering columns on `question_records` (D11).
- `AnswererSettings` gains `answer_model`, `check_model`, `max_concurrent_runs` and `max_cost_usd` (D12).
- Listing columns, the store and process contracts, and the stub `sq` acting as the answering pipeline.
- The live tests that need a model: real question tails, PM-precedent matching, and an end-to-end answered question (D13).

Excluded:

- The pipeline file, its prompts, the scratch contents and the reply parsers (140). Passage assembly and the citation rule (143). The gate and the submission transaction (142). The record, its transitions and the PM-answer rule (141).
- Retrying a failed answering run, or answering on agreement across several runs (plan Future Work 3).
- Answering `artifact_missing` replies (plan Future Work 2).
- Pruning scratch directories. They are kept, as launch logs are; see Special Considerations.
- The live end-to-end walkthrough against a real slice pipeline (145).

## Dependencies

What 144 consumes:

- **140 (answering pipeline).** `answering_pipeline_path`, `QuestionInput`, `prepare_scratch`, `read_answer`, `read_check`, `ArtifactProblem` and the param names in `pipeline_file.py`. The live tier and the first real run need a Squadron release with 140's D8 capabilities. Until one exists, those tasks carry `BLOCKED:` lines naming the Squadron issue. The stub tier does not need it.
- **141 (question record).** `question_records`, `QUESTION_TRANSITIONS`, `DeclineReason`, `decline_question`, `pending_questions`, `settle_pending`, the stage's place in `ProjectTick.run`, and D2's acknowledgment rule: it leaves an `answered` record alone and settles an `answering` one when the PM's resume is applied, which D9's discard and `block_resolved` handling rest on. 144's changes to 141's code are in D14.
- **142 (gate and submission).** `submit_answer` with its four outcomes and gate protocol (142 requires D3's acceptance test here to keep proving the Runner accepts the answerer's resume), `evaluate_gate`, `compose_instructions`, `AnswerOutcome`, and the answerer's start-up probe.
- **143 (source passages).** `assemble_sources`, `render_passages`, `slice_label`, `PassageSet` (with `ids`), `SourcesProblemKind`, and the id-based `check_citations` (D7).
- **132, 127, 122.** `RunObserver.observe`, reused unchanged for `sq_answer` entries, which carry no continuation, so `resumed_from` is empty. `SquadronRunIdObserver`: any run state means in flight, and `not_found` past the launch grace means not applied. Also `LaunchTracker`, `log_paths`, `spawn`, `build_argv`, `mint_run_id`, `Store._resolve_entry_within`, the journal insert (shared with `journal_issue`, D5), the resolution stage and the tick.

## Architecture

### Component Structure

| Component | Location | Role |
| --- | --- | --- |
| Command kind | `store/journal_models.py` | `SQ_ANSWER`, its required keys, `PARAM_SCRATCH`, and `supervision_entries` |
| Done-guard | `store/sql_journal.py` | `SELECT_UNRESOLVED_ENTRY_FOR_NODE` excludes `sq_answer` |
| Answering store operations | `store/answering.py` (mixin `AnsweringOperations`) | `begin_answering`, `question_for_answering_entry` |
| Journal insert | `store/journal.py` | `_insert_entry_within`, shared by `journal_issue` and `begin_answering` |
| Evidence and launch types | `store/question_models.py` (extended) | `AnsweringLaunch`, `PassageRef`, `AnsweringEvidence`, `BeginOutcome`, new `DeclineReason` members |
| Migration | `store/schema/015_answering_run.sql` | Columns and an index on `question_records` |
| Recovery | `process/supervisor.py` | `SQ_ANSWER: SquadronRunIdObserver(...)` |
| Settle | `runner/answering/settle.py` (141, changed) | The last branch returns `Launch` instead of `Decline(no_answer_on_file)` |
| Decide | `runner/answering/decide.py` | Pure. `RunSummary`, `decide_answer`, `Confirmed`, `Declined`, problem-to-reason maps |
| Launch | `runner/answering/launch.py` | `launch_answering`: passages, scratch, `begin_answering`, spawn |
| Finish | `runner/answering/finish.py` | `finish_answering`: decide, settle the record, resolve the entry |
| Stage | `runner/answering/stage.py` (141, grown) | `AnsweringStage.run`: observe, settle stranded records, settle pending, launch |
| Settings | `runner/project_config.py` | Four `AnswererSettings` keys |
| Listing | `inspection/questions.py` | Answering columns |

The 132-owned readers change by one line each: they filter their entries through `supervision_entries` before reading.

### Data Flow

```
ProjectTick.run
  apply intents; apply PM resolutions            (classify reads supervision_entries)
  observe sq_run entries; probes; plan reads; record_finished
  AnsweringStage.run(budget, faults)                       ← replaces 141's settle-only pass
    1. observe:  unresolved sq_answer entries → RunObserver.observe (polls take budget)
                 each finished → finish_answering(entry, finished)
    2. stranded: answering records whose entry is resolved → settle (D9)
    3. pending:  for record in pending_questions (oldest first)
                   settle_pending → Skip | Decline(reason) | Launch
                   Launch, while unresolved sq_answer < max_concurrent_runs and budget allows:
                     launch_answering(record)
  CUT_OFF return if probes or stage cut off
  view, dispatch checks (dispatch_state reads supervision_entries), decide, act

launch_answering(record)
  passages = assemble_sources(...)                           143; None → stop launching this tick
    SourcesProblem → decline_question(reason=sources_*, detail)
  run_id   = mint_run_id(now); scratch = <supervisor_dir>/answering/<run_id>/
  mkdir scratch; prepare_scratch(scratch, QuestionInput(slice_label, question), render_passages, max_cost_usd)
  begun    = store.begin_answering(record.id, AnsweringLaunch(...))       one transaction
    block resolved / record not pending → nothing written; stop for this record
  started  = spawn(argv, cwd=scratch, log_paths(supervisor_dir, entry.id))
    LaunchError → finish_answering(entry, LaunchFailed)
  tracker.track(entry.id, child)

finish_answering(entry, finished)
  record = question_for_answering_entry(entry.id)
  record not answering   → journal_resolve(entry, discarded)                PM answered first; record unchanged
  answering              → summary = RunSummary(finished); replies read if completed
                           decision = decide_answer(summary, answer, check, record.passage_ids)
                           Confirmed → submit_answer(..., evidence)   (142's gate inside)
                           Declined  → decline_question(reason, detail, evidence)
                           journal_resolve(entry, outcome, result)
```

### State Management

All state is in the project's store and the scratch directory. Nothing is held between ticks except `LaunchTracker` and `RunObserver`'s poll times, which a restart rebuilds as it does for `sq_run`.

Record transitions written in 144 (141's table, 144's writers):

| From | To | Writer |
| --- | --- | --- |
| `pending` | `answering` | `begin_answering`, with the journal entry |
| `pending` | `declined` (sources) | `decline_question`, from `launch_answering` |
| `answering` | `answered` (answerer) or `declined` (gate) | `submit_answer`, from `finish_answering` |
| `answering` | `declined` (run, artifact, citation, check) | `decline_question`, from `finish_answering` |
| `answering` | `declined` (stranded) | `decline_question`, from the stage's stranded pass |

An `answering` record is linked to exactly one `sq_answer` entry by `answering_entry_id`.

## Technical Decisions

### D1 — The answering pipeline is the one Amoeba ships; it is not a configuration key

Status: decided

- The slice plan lists "the answering pipeline" among the per-project configuration. 140 (D1) decided that the file Amoeba launches is always the one it shipped and tested, launched by path, and 142 (D8) probes that file. A per-project pipeline key would bypass both: the names-match test and the start-up probe would cover a file nobody launches. So the configuration carries the models, the cost cap and the cap on concurrent runs. The pipeline is `answering_pipeline_path()`. The architecture's "Cost and configuration" and the slice plan's 144 entry are amended to say so.
- **Rejected:** a `pipeline` key defaulting to the shipped file. A default is what the project rules forbid, and a key with one legitimate value is configuration with no use.

### D2 — `sq_answer` is the three-part change; recovery reuses the run-id observer

Status: decided

- `CommandKind.SQ_ANSWER = "sq_answer"`. Required parameters: `run_id`, `pipeline`, `params` and `scratch`. `run_id` is what recovery needs. `scratch` is the working directory, the counterpart of `sq_run`'s `checkout`. The entry does not name its question: the record links to the entry through `answering_entry_id`, and every reader joins from there.
- Recovery registers `SquadronRunIdObserver` for `SQ_ANSWER`, built with the same settings as the `sq_run` one, with no legacy matcher (no `sq_answer` predates run ids). Any run state leaves the entry in flight for the stage to poll after restart, which is the "adopt by run id" the plan requires. `not_found` past the launch grace resolves it `not_applied`. An unreadable answer escalates (`unknown`), which writes no second block on a node already blocked on the question.
- `sq_answer` is not in `REVIEW_PRODUCING_KINDS`: it writes no review. An issuer's resolution of it sets no `awaits_routing`, because `_resolution_parameters` already sets the flag only for `sq_run`. A test pins this.
- The tick's `_run_entries` already keeps only `sq_run`, so an `sq_answer` never reaches `record_finished` or 132's outcome map, as the arch requires.

### D3 — One shared reader keeps `sq_answer` away from the supervisor's journal reads

Status: decided

- `supervision_entries(entries) -> list[JournalEntry]`, beside `latest_run_entry` in `journal_models.py`, returns the entries, in order, without `sq_answer`. It is the single statement of "the answerer's entries are not the slice's commands".
- Applied at each 132-owned reader the arch names:
  - `resolutions/stage._answer` passes `supervision_entries(...)` to `classify`. Today an unresolved `sq_answer` as the latest entry would make the PM's resolution `UNRESOLVABLE`.
  - `supervise.run_to_resume` filters its input. Today a resolved `sq_answer` as the latest entry would make a resume `instructions_not_applicable`.
  - `build_view._facts_for` filters the node's entries before `dispatch_state` and `latest_run_entry`. Today an unresolved `sq_answer` would hold the step `IN_FLIGHT`, so the PM's applied resume would wait for the answering run.
  - `checkout_holders` and `ingest.record._resume_count` already skip every kind but `sq_run`. They are switched to the shared reader anyway, so the rule is in one place and a new kind cannot slip past one of them.
- The unresolved `sq_answer` is never a reason to reject a resolution: the PM wins by design (arch).
- **The test the plan and 142 (D6) rely on** builds one slice journal with a paused `sq_run` whose question block is open, plus an `sq_answer` in flight, and then the same `sq_answer` resolved. For each case it asserts: `classify` is `RUN_TO_RESUME`; `run_to_resume` returns the `sq_run`; the checkout is held by that node; `dispatch_state` with an applied resume is `RESUME`; the resume count is unchanged. A stub end-to-end case then shows a PM resolution accepted with the answering run in flight, and an answerer resolution accepted after it ends, each resuming the paused run with `sq run --resume`.

### D4 — The store's done-guard ignores `sq_answer` entries

Status: decided

- `update_node_status(done)` and `record_runner_report(complete_node_id=…)` refuse while the node has an unresolved journal entry. If the PM answers while an answering run is in flight, the resumed run can finish before the answering run does. Its completion would then raise, and the tick would fault on a slice that did finish.
- `SELECT_UNRESOLVED_ENTRY_FOR_NODE` gains `AND kind != 'sq_answer'`, with the kind value taken from `CommandKind`. The guard exists so that a command that changes the slice cannot be in flight on a done node. An answering run changes nothing in the slice. Its later result, on a done node, finds its record already `answered` by the PM and is discarded (D9).
- `lifecycle/completion.py` still treats any unresolved entry as "leave it alone". That is the conservative reading of CF-reported completion and needs no change: an answering run in flight only delays the mark by a tick or two.

### D5 — `begin_answering` journals the entry and moves the record in one transaction

Status: decided

- `journal_issue` commits on its own. If it were followed by a separate `pending → answering` write, a crash between them would leave a pending record and an `sq_answer` in flight, and the next tick would launch a second run. The plan forbids that.
- `begin_answering(question_id, launch: AnsweringLaunch) -> BeginOutcome` runs under one `BEGIN IMMEDIATE`. It reads the record and its block. If the record is not `pending`, it returns `settled`. If the block already has a resolution, it returns `block_resolved`. Either way it writes nothing. Otherwise it inserts the `sq_answer` entry through `_insert_entry_within`, the insert extracted from `journal_issue` with its required-key check. It then moves the record to `answering`, setting `answering_entry_id`, `source_commit`, `passage_index` and `dropped_pm_answers`, checked against `QUESTION_TRANSITIONS`. The result carries the entry and the record.
- The spawn happens after the commit, as every journaled command does. A crash after the commit and before the spawn leaves an entry whose run never appears. Recovery resolves it `not_applied`, and the stranded pass declines the question (D9).
- **Rejected:** writing the record first and journaling second. A crash would leave an `answering` record with no entry, which nothing would ever settle.

### D6 — The launch runs from a scratch directory keyed by the run id

Status: decided

- The scratch directory is `<supervisor_dir>/answering/<run_id>/`, beside `launch-logs/`. It is named by the minted run id, so it exists and is prepared before the entry is journaled. A crash after preparation and before `begin_answering` leaves an unused directory and a pending record, and the next tick prepares a fresh one under a new run id. `mkdir` is exclusive, so a directory is never reused.
- The argv is `build_argv(str(answering_pipeline_path()), run_id, {answer-model: …, check-model: …})`, using 140's param-name constants. With no `slice` key, nothing is positional. `build_argv` refuses a comma in a model alias before anything is journaled, and the settings refuse one at load (D12).
- The process is started with `spawn(argv, scratch, log_paths(supervisor_dir, entry.id), popen)`, the function `launch` uses. So the stderr log, the run-id confirmation line and the launch grace work unchanged in `RunObserver`. There is no checkout lookup, no clean-tree or branch check and no checkout hold (arch, "Launch without a checkout").
- Sources are assembled before the scratch directory is made, so a `SourcesProblem` or a budget refusal costs no directory. The question, the slice label and the passage set are fixed at launch. A rule committed while the run is in flight is in the next question's passages, not this one's.
- **Every launch-path failure declines `answering_launch_failed`; none retries.**
  - An `OSError` from the `mkdir` or from `prepare_scratch`, such as permissions or a full disk, happens before anything is journaled. `launch_answering` catches `OSError` at those two calls, with a comment saying why, and calls `decline_question(reason=answering_launch_failed, detail=<the error>)` on the still-`pending` record.
  - A `LaunchError` from `spawn` happens after the journal entry. It covers a launch log that cannot be created, because `spawn` already returns `spawn_error` for that. It goes straight to `finish_answering` with `LaunchFailed`.
  - Either way the question is declined in the same tick, and is never relaunched.
  - `prepare_scratch`'s `ValueError` (140: a directory that is not empty, a bad cost cap) is a programming error and raises.
- **Orphan directories.** A failed launch leaves at most one scratch directory, partly written or unused, for each question it declines. A crash between preparation and `begin_answering` leaves one more per crash. No path makes one per tick.

### D7 — The decide function is pure and reads only recorded inputs

Status: decided

`decide_answer(run: RunSummary, answer, check, passage_ids) -> Confirmed | Declined`. Inputs:

- `RunSummary`, built from the `Finished` value: launch failed, vanished, or ended with an outcome and its failure or checkpoint kind.
- `answer` and `check`: what 140's `read_answer` and `read_check` returned, or `None` when the run did not complete (the files are not read).
- `passage_ids`: the ids recorded on the question at launch (D11).

Checks, in order. The first that fails decides:

1. The run completed. Otherwise a run reason (D8).
2. The answer reply parsed. Otherwise `artifact_missing` or `artifact_malformed`, with the file named.
3. The answer step answered. A decline is `answerer_declined` with its reason, whatever the check said (140, D1).
4. The citations pass `check_citations(cited, passage_ids)`. Otherwise `uncited` or `unknown_citation` with the ids.
5. The check reply parsed. Otherwise `artifact_missing` or `artifact_malformed`.
6. The verdict is `yes`. Otherwise `check_said_no` with the check's reason.

All six passing gives `Confirmed(answer, cited)`. Every result also carries the `AnsweringEvidence` gathered so far: the proposed answer, the cited ids, the verdict and its reason.

- **The passage ids come from the record, not from `passages.md`.** Amoeba never parses `passages.md` back (143, Special Considerations), and the decision may run ticks after the launch. So `check_citations(cited: Sequence[str], passage_ids: Collection[str])` takes the set of ids, as 143 (D8) ships it, with `PassageSet.ids` giving the ids. The rule itself stays in 143.
- `decide.py` passes the purity check. A table test covers every row, and every `ArtifactProblem` and `CitationProblem` kind.

### D8 — Decline reasons are distinct, closed and mapped once

Status: decided

144 adds these `DeclineReason` members (141, D3: the store owns the vocabulary). Each maps from exactly one input, in `decide.py` or `launch.py`:

| Reason | From |
| --- | --- |
| `sources_too_large`, `sources_missing`, `sources_unreadable` | 143's `SourcesProblemKind`, one to one |
| `answering_launch_failed` | `LaunchFailed`, or an `OSError` preparing the scratch directory (D6) |
| `answering_run_failed` | `failed` with failure kind `provider_error`, `artifact_missing`, unknown or absent; `paused` (the pipeline has no human steps); `RunVanished`; an entry resolved `not_applied` or `unknown` by recovery (D9). `decline_detail` names which |
| `answering_run_stalled` | `failed`, failure kind `stall` |
| `answering_cost_cap` | `failed`, failure kind `cost_cap` |
| `answering_run_orphaned` | `orphaned` |
| `answer_discarded` | Entry resolved by the stage after `block_resolved`, and the block not awaiting the Runner (D9) |
| `artifact_missing`, `artifact_malformed` | 140's `ArtifactProblem`, either file |
| `answerer_declined` | The answer step's decline |
| `uncited`, `unknown_citation` | 143's `CitationProblem` |
| `check_said_no` | The check's `no` |

- Each decline also writes `decline_detail`: the failure message, the checkpoint kind, the problem detail, the decline's reason or the check's reason, cut to 132's bound. The reason is the code; the detail is for the PM.
- Failure kinds are compared through `FailureKind`. An `UnknownKind` maps to `answering_run_failed` with the raw kind in the detail, never to a near match.
- 141's `no_answer_on_file` stops being written. It stays in the vocabulary, because records written before 144 hold it.

### D9 — Finishing settles the record first, then resolves the entry

Status: decided

- `finish_answering` settles the record and then calls `journal_resolve`. If the process crashes between the two, the entry is still unresolved. The next tick polls it again, finds it finished, and finds the record no longer `answering` for this entry. It then only resolves the entry. Neither order makes the record and entry one transaction, but this one makes the retry safe, as 132's ingest does with its block and report.
- **Record not `answering`, or linked to another entry.** The PM's answer was acknowledged first (141, D2), or a retry already settled it. The result is discarded and the record is not changed (arch, step 7). The entry is resolved with `question_outcome: discarded`.
- **Record `answering`.** Decide (D7). For `Confirmed`, call `submit_answer(..., evidence=…)` with `instructions=compose_instructions(record.question, answer)` and `detail=ANSWERER_DETAIL`, a constant in `runner/answering/finish.py` that is provenance only (142, D5). The decision (`resume`) and the answerer's submitter name belong to the store, so 144 passes neither. The gate is `partial(evaluate_gate, answer=answer, settings=project.answerer)`. For `Declined`, call `decline_question(id, reason=…, detail=…, evidence=…)`.
- **`submit_answer` outcomes.** `submitted` and `declined` are done. `settled` means the record changed under us: the entry is resolved and nothing else happens. `block_resolved` means the PM resolved the block after the stage read it. Nothing is written to the record, which stays `answering` for the acknowledgment to settle (142, D4).
- **The stranded pass** takes `answering` records whose entry is resolved. If the block is awaiting the Runner, it skips: next tick's acknowledgment settles the record. Otherwise it declines by the entry's outcome: `not_applied` or `unknown` gives `answering_run_failed`, with the outcome in the detail, and an entry the stage resolved gives `answer_discarded`. The last is the PM's `stop`, or a rejected PM resolution, that re-pointed the record to a new block (141, D2). The question is with the PM, and the record says the answer was dropped.
- `submit_answer` and `decline_question` gain a keyword `evidence: AnsweringEvidence | None`. `decline_question` also gains `detail: str | None`. Both are written in the operation's own transaction, so the record never holds a decline without its detail or an answer without its citations. 141's stage passes neither. They are additions to 141's and 142's operations that 144 makes alongside its migration.
- The entry's result: the run outcome, the decision (`confirmed` or the decline reason) and `question_outcome` (`submitted`, `declined`, `block_resolved`, `settled` or `discarded`). `JournalOutcome` is `completed` when the run completed and `failed` otherwise.

### D10 — Stage order, the cap and the budget

Status: decided

- **Placement.** 141's place: after `record_finished` and the `shape_error` check, before the `CUT_OFF` return. The stage now starts subprocesses, so it takes the budget: every poll and every git read checks `budget.allows_call()`, and so does every spawn. Its store-only branches still run when the budget is spent: declines from `settle_pending`, the stranded pass, and finishing a run already observed. It returns `CUT_OFF` when a call was refused, and the tick returns `CUT_OFF` if the probes or the stage cut off.
- **Pass order.** Observe and finish first, then the stranded pass, then pending. A run that ended this tick frees its slot before the next launch.
- **The cap.** `max_concurrent_runs` bounds the project's unresolved `sq_answer` entries. These are the runs that are actually spending. A record stranded after `block_resolved` is not running and takes no slot. Amoeba sets no time limit on an answering run. A run that stays alive and reports no failure is bounded by Squadron: its `stall` detection and the run's `max_cost_usd` end it, and D8 declines both. When the cap is reached, the remaining pending records are left for a later tick. They still go through `settle_pending` first, so a question that needs no run (no configuration, null text, a resolved block) is settled at once.
- **Order among pending.** Oldest first, from `pending_questions`. A budget refusal during assembly or launch stops the pending pass for this tick, and the record stays `pending`.
- **Fault isolation.** Observation sets the node context per entry, as the `sq_run` pass does, so a poll fault is raised against that node. Finishing, the stranded pass, settling and launching run with the context cleared, as 141's D5 set, so an exception escalates per project.
- **No pre-gate.** The stage does not check the answer limit or the reserved terms before launching. That would put a second copy of the gate outside its transaction (142, D1 and its Integration Points). A question that the gate will decline still costs one run. The cost cap bounds it.

### D11 — Migration `015` records what the answer rested on

Status: decided

Columns on `question_records`:

| Column | Type | Set by | Notes |
| --- | --- | --- | --- |
| `answering_entry_id` | TEXT → `command_journal(id)` | `begin_answering` | Unique partial index where not null |
| `source_commit` | TEXT | `begin_answering` | 143's `PassageSet.source_commit` |
| `passage_index` | TEXT (JSON) | `begin_answering` | `[{"id", "source", "question_id", "date"}]`, without text. `question_id` is set only for a PM passage, so it also says which passages are PM answers |
| `dropped_pm_answers` | TEXT (JSON) | `begin_answering` | 143's dropped record ids |
| `proposed_answer` | TEXT | evidence | The answer step's answer, kept on a decline. `answer` (142) still holds what was submitted |
| `cited_passages` | TEXT (JSON) | evidence | The cited ids as given |
| `check_verdict` | TEXT | evidence | `yes` or `no` |
| `check_reason` | TEXT | evidence | |
| `decline_detail` | TEXT | `decline_question` | Bounded (D8) |

- `passage_index` is what makes the decision reproducible: it holds the ids `decide_answer` checks, and it lets `amoeba inspect questions --json` show where each cited id came from (a path at `source_commit`, or a PM answer's record id) and its date, which 145's precedence cases read. The text and the passage kind are not stored. A rules or plan passage can be re-read from git at `source_commit`, and a PM passage from its record.
- The answering run's id is the `run_id` parameter of the entry `answering_entry_id` names. It is not copied onto the record; the listing joins through the entry.
- `dropped_pm_answers` is kept because the plan's 143 entry requires the dropped PM answers to be recorded, and 143 (D7) leaves that recording to 144. It is shown in `--json` so a wrong answer can be traced to precedent the check step never saw.
- A PM answer to an `answering` or `declined` record leaves these columns as they were. 141's rule sets only `state`, `answered_by` and `answer`.
- No new feed kind. 141's `question_state_changed` fires for every transition here.

### D12 — Four required configuration keys

Status: decided

```yaml
projects:
  amoeba:
    pipeline: p456
    answerer:
      answer_limit: 3                 # 142
      reserved_terms: [push, merge to main, release, DROP]   # 142
      rules_paths: [CLAUDE.md]        # 143
      passages_max_chars: 200000      # 143
      answer_model: <alias>
      check_model: <alias>
      max_concurrent_runs: 2
      max_cost_usd: 0.50
```

- `answer_model` and `check_model` are stripped, non-blank strings with no `,` (Squadron would split the `-p` value). `max_concurrent_runs` is a `StrictInt` of at least 1. `max_cost_usd` is a positive number, passed to `prepare_scratch` on every run (140, D7). All four are required, with no defaults. Load errors name the key path. The example values appear only in the process contract's example config.
- **This breaks existing answerer sections.** A project whose section has only 142's and 143's keys fails at load until it adds these four. The process contract's note on the answerer section says so.
- Whether an alias runs with tools is Squadron's to refuse (140, D2 and D8, capability 4). Amoeba keeps no list of safe aliases.

### D13 — Test tiers: the stub `sq` for the stage, the live tier for meaning

Status: decided

- **Stub tier.** The stub `sq` in `tests/` learns to act as the answering pipeline. On `sq run <answering.yaml>` it writes scripted `answer.json` and `check.json` (or none) into its working directory and reports a scripted outcome to `sq runs wait`. Every decline reason, the races, recovery, the cap and the end-to-end resume run on this tier, with no spend.
- **Live tier** (`tests/live/answering/`, 140's opt-in tier and its variables). It covers what needs a model. One case is a question answered from a plan passage, which resumes a stub-paused run. The other is PM-precedent matching. A real question tail that repeats a PM answer in other wording, for the same slice, resumes. The same tail asked for a slice where the answer differs is declined. A third case uses another slice where the meaning is the same, and resumes. Each case runs the real stage, from `assemble_sources` against 143's fixture repository and a throwaway store to the record's final state. Each runs once. A wrong result fails the test, and nothing retries.
- **Real tails.** `tests/live/answering/fixtures/question_tails.json` holds `checkpoint.question` values copied from `sq runs wait --json` output of real question-paused runs. Each entry has the run id and the capture date. They are copied by hand when the fixture is made. Amoeba never reads run-state files. A tail that 145 meets and this file lacks is added there (145's criteria).

### D14 — What 144 changes in 141's and 142's code

Status: decided

The plan builds 141 and 142 before 144, so both are shipped when 144 starts. 144 edits them in three places:

- `settle_pending`'s last branch returns `Launch`. 141 (D5) left that branch for 144 to replace, and 141's settle tests for it change with it.
- `decline_question(..., detail=None, evidence=None)`, in 141's code, added with migration `015`, which adds the columns.
- `submit_answer(..., evidence=None)`, in 142's code, added the same way.

Both new keywords are optional, so 141's and 142's callers and suites run unchanged.

### Technology Choices

- Nothing new. Stdlib `sqlite3` through the store plumbing, a numbered migration, pydantic settings, `functools.partial` for the gate, and the existing launch, observe and recovery code.

### Patterns and Conventions

- Reasons, outcomes and kinds are compared only through their enums. JSON keys of `passage_index` and of the entry result are constants in `sql_questions.py` and `runner/answering/finish.py`.
- One store method, one transaction, with `BEGIN IMMEDIATE` before the first read that decides a write.
- `decide.py` and `settle.py` are pure and covered by `tests/runner/purity.py`.
- Bad model output and failed runs are values that become declines. Only programming errors raise.

## Implementation Details

### Database / Storage Schema

Migration `015_answering_run.sql`, schema version 15: the columns in D11, and a unique partial index on `answering_entry_id WHERE answering_entry_id IS NOT NULL`. No backfill: records written before 15 have nulls.

### API Contracts

Store (`docs/store-contract.md`, "Question records", new subsection "Answering runs"):

| Method | Effect |
| --- | --- |
| `begin_answering(question_id, launch: AnsweringLaunch) -> BeginOutcome` | In-process only. One transaction (D5). `AnsweringLaunch(node_id, run_id, parameters, source_commit, passages: tuple[PassageRef, ...], dropped_pm_answers)`. Outcomes: `begun` (with the entry and record), `block_resolved`, `settled`. Raises `QuestionNotFoundError`, and `ValueError` for missing required parameter keys, before any write. |
| `question_for_answering_entry(entry_id)` | The record linked to an `sq_answer` entry, or `None`. |
| `decline_question(question_id, *, reason, detail=None, evidence=None)` | 141's operation, with detail and evidence written in its transaction. |
| `submit_answer(..., evidence=None)` | 142's operation, with evidence written in its transaction on both `submitted` and `declined`. |

Journal (`docs/store-contract.md`, the command journal): `sq_answer` and its required keys. The done-guard excludes `sq_answer` (D4).

Runner (`runner/answering/`):

```python
@dataclass(frozen=True)
class Confirmed: answer: str; cited: tuple[str, ...]; evidence: AnsweringEvidence
@dataclass(frozen=True)
class Declined: reason: DeclineReason; detail: str; evidence: AnsweringEvidence

def decide_answer(run: RunSummary, answer: AnswerReply | ArtifactProblem | None,
                  check: CheckReply | ArtifactProblem | None,
                  passage_ids: Collection[str]) -> Confirmed | Declined: ...
def supervision_entries(entries: Sequence[JournalEntry]) -> list[JournalEntry]: ...   # store/journal_models.py
```

Process contract (`docs/process-contract.md`): the `sq_answer` kind, the scratch directory layout under the supervisor directory, the four answerer keys, and the stage's place in the tick.

Inspection: `questions` gains `answering_run_id` (joined from the entry), `check_verdict` and `decline_detail`. `--json` and the server also carry every D11 column.

## Integration Points

### Provides to Other Slices

- **145 (live walkthrough):** the working stage. Its four cases are a question answered from the plan, a reserved-term decline, a reworded PM answer, and a PM answer standing against an older rule. They exercise this slice end to end against a real slice pipeline.
- **160 (notification bridge):** declines with distinct reasons and a `decline_detail`, on the feed through 141's `question_state_changed`.
- **Inspection:** for any resumed run, the record shows the question, the answer, `cited_passages` resolvable through `passage_index` at `source_commit`, the verdict and the run id (arch, "Every answer is traceable").

## Success Criteria

### Functional Requirements

- A question whose answer is in a supplied passage resumes the run. The record is `answered` by the answerer and holds the answer, `cited_passages`, `passage_index`, `source_commit`, `check_verdict yes` and `answering_entry_id`, whose entry carries the run id. Live tier for a real model; stub tier for the mechanics.
- A real question tail that repeats an earlier PM answer in other words resumes from that answer, on the same slice and on another slice where the meaning is the same. Asked for a slice where the answer differs, it is declined. Live tier, with tails from real runs.
- Each of these declines the question with its own reason from D8, and none is retried: a check `no`, an uncited answer, an unknown citation, the answer step's decline, a missing or malformed reply file, a failed, stalled, cost-capped or orphaned run, a launch failure, and each `SourcesProblemKind`. A paused or vanished run, and a launch recovery found never started, decline `answering_run_failed` with the case named in `decline_detail`.
- D3's acceptance test passes: the reader cases and the stub end-to-end cases.
- A PM answer that lands while the run is in flight wins. The run's later result resolves the entry and changes nothing on the record, which stays `answered` by the PM.
- A restart with an answering run in flight adopts it by run id through recovery, polls it to its end, and never launches a second one. A crash between `begin_answering` and the spawn declines the question `answering_run_failed` after recovery.
- No answering run starts for a question whose block the PM has already resolved. That holds both when `settle_pending` sees it and when the resolution lands between the read and `begin_answering`.
- A burst of pending questions never has more unresolved `sq_answer` entries than `max_concurrent_runs`. The rest stay `pending` and launch on later ticks as slots free.
- A resumed run that completes while its slice's `sq_answer` is still in flight marks the node done without a fault (D4).
- The four D12 keys are required, with no defaults. Every run's `.squadron.toml` carries the configured `max_cost_usd`.

### Technical Requirements

- `decide_answer` and `settle_pending` pass the purity check. The decide table test covers every row of D7 and D8.
- Crash safety: a kill inside `begin_answering` leaves no entry and a `pending` record. A kill between settling and `journal_resolve` is retried without a second submission or decline.
- An issuer's resolution of an `sq_answer` sets no `awaits_routing`, and `sq_answer` is never passed to `record_finished`.
- The migration test covers 14 → 15. The feed invariant test still passes with the new transitions.
- 132's, 127's and 141–143's existing suites pass, with the reader change and the extended operations.
- Format, lint and typecheck (`ruff`, `pyright` strict) pass.
- Docs: "Answering runs" in the store contract and the latest migration moved to `015`. In the process contract: `sq_answer`, the scratch layout, the four keys and the stage's place.

### Integration Requirements

- 145 can run its walkthrough with only configuration: an answerer section with all eight keys and a Squadron release with 140's D8.
- A project with no answerer section behaves as after 141: every question is declined `answerer_not_configured`, and no `sq_answer` is ever journaled.

### Verification Walkthrough

Steps 1, 3 and 4 were run on 20261103 against the stub `sq` and pass. Step 2 (the live tier) was run on 20261103 against squadron 0.24.16 with glm-flash and deepseek4-flash and passes (four cases, 59 seconds). The unit tests for decide, settle, the shared reader, the store operations and crash recovery are in Success Criteria and Technical Requirements; the steps here are the ones an operator can see. Step 1 needs no Squadron changes and no spend. Step 2 needs squadron 0.24.16 or later and real models. The stage runs against squadron 0.24.16 only: earlier versions exit 1 from `cf get` in a scratch directory.

1. **The stage end to end, stub `sq`.**

   ```
   uv run pytest tests/runner -k answering -v
   ```

   Expected: 322 tests pass (the answering suites and the tick and end-to-end cases; the end-to-end ones are in `tests/runner/test_end_to_end_answering.py`). A question-paused slice gets one `sq_answer` and a resume with instructions that restate the question (`You asked: <question>` then `Answer: <answer>`). The record is `answered` by the answerer, with citations and verdict. The race cases pass: PM during the run, PM before `begin_answering`, PM between the read and `begin_answering`, restart with a run in flight, and a crash between `begin_answering` and the spawn. So do the cap case (three questions, cap 2) and every decline case.

2. **Live tier, real models.**

   ```
   export AMOEBA_LIVE_ANSWER_MODEL=<non-SDK alias> AMOEBA_LIVE_CHECK_MODEL=<non-SDK alias> AMOEBA_LIVE_MAX_COST_USD=<cap>
   uv run pytest tests/live/answering/test_answering_run.py -v --basetemp=/tmp/answering-run-live
   ```

   Expected: four passed. The rules-passage question is answered. The reworded PM-answer question is answered on the same slice and on the other slice where the PM's answer was given for every slice, and is declined for the slice where the answer differs. Provider keys must be in the environment. Then look at one run:

   ```
   ls /tmp/answering-run-live/<test>/supervisor/answering/    # one directory per run id
   ```

3. **A real store with the stub.** The test `test_the_operator_sees_the_answered_question_through_inspect` copies the scenario's store into a throwaway supervisor directory and runs the real CLI over it. By hand: add the eight `answerer` keys to the scratch project (see the process contract, "The project config"), start Amoeba with the stub `sq` on `PATH` scripted to answer `yes` citing `P1` (`ANSWER_SCRIPT_ENV`), and produce a question.

   ```
   amoeba inspect journal --project scratch --json
   ```

   Expected: exactly one `sq_answer` entry on the slice node and at least one `sq_run`.

   ```
   amoeba inspect questions --project scratch --json
   ```

   Expected: `state answered`, `answered_by answerer`, `check_verdict yes`, `cited_passages ["P1"]`, `passage_index` whose first element names P1's source path, and `answering_run_id` starting `amoeba-`.

4. **A decline.** `test_the_operator_sees_a_declined_question_then_the_pm_answers_it`. Script the stub's check to reply `no` and produce another question.

   ```
   amoeba inspect blocked --project scratch --json
   ```

   Expected: the question block shows `question_state declined` and `decline_reason check_said_no`. `amoeba inspect questions --project scratch --json` shows `decline_detail` with the check's reason and the `proposed_answer`. Then answer it as the PM (141's step 7). Expected: the run resumes and the record becomes `answered` by `pm`.

**Caveat found in implementation.** `sq run` takes the pipeline's first `required` param only as the positional target, so the launch is `sq run <answering.yaml> <answer-model> --run-id <id> -p check-model=<alias>`. Passing `answer-model` with `-p` exits 2 ("requires a 'answer-model' argument"; checked against squadron 0.24.16). The stub refuses the same shape.

## Risk Assessment

### Technical Risks

- **The first decision that resumes real runs without the PM.** A wrong confirmed answer costs one rerun of one step. It cannot push, merge or release (arch).
- **The second change to 132's code.** A reader that misses the filter would reject a PM resolution or stall a resume while an answering run is in flight.
- **Squadron timing.** The live tier and every real run wait on 140's D8 release.

### Mitigation Strategies

- Every uncertain path is a decline (D7, D8). The answer limit and reserved screen sit inside the only submitting operation (142). Each answering run is capped in cost and in concurrency.
- D3's acceptance test covers every reader the arch names, and the readers that already filter are switched to the shared reader so a later kind cannot slip past one. 132's suites run unchanged.
- The stub tier delivers and proves the whole stage without Squadron. Only the live-tier tasks carry `BLOCKED:` lines until the release exists.

## Implementation Notes

### Development Approach

1. `SQ_ANSWER`, its keys, `supervision_entries` and the five reader changes, with D3's acceptance test. Then the done-guard (D4) and the recovery registration.
2. Migration `015`, the new `DeclineReason` members and types, `_insert_entry_within`, `begin_answering`, `question_for_answering_entry`, and the evidence and detail keywords on `decline_question` and `submit_answer`, with store and crash tests.
3. The `AnswererSettings` keys and load errors.
4. `decide.py` with its table test. `settle_pending`'s `Launch` branch (D14).
5. The stub `sq` as the answering pipeline. Then `launch.py`, `finish.py` and the stage passes, with the tick tests and the stub end-to-end cases.
6. Listing columns and contract docs.
7. Live tier: the real-tail fixture and the three cases. `BLOCKED:` on the Squadron issue until 140's D8 release exists.

Relative effort: 4.

### Special Considerations

- **Answer text is model output.** It is stored and passed to `sq run --resume --instructions` as data, through the same argv path as the PM's instructions (142, Special Considerations).
- **Scratch directories accumulate.** Each holds the inputs, the prompts and the replies of one run: the evidence behind a decision, and small. They are kept, as `launch-logs/` is, and are not pruned in this slice. A prune target is future work if their size matters.
- **Spend.** One answering run per pending question, capped in cost and concurrency. A question declined by the gate after a confirmed answer has already spent its run (D10).
