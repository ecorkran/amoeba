---
docType: slice-design
slice: pause-handling
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 222-slice.store-config-and-set-up
interfaces:
- 224-slice.status-and-decisions
- 225-slice.scenario-a-trial
- 226-slice.mcp-server
dateCreated: 20261107
dateUpdated: 20261107
status: not_started
turns: 35
promptTokens: 2677496
cachedTokens: 2533746
cacheWriteTokens: 143698
completionTokens: 39368
durationSeconds: 445.2
costUsd: 2.444234
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 2.4442345
    completionTokens: 39368
---

# Slice Design: Pause Handling

## Overview

This slice delivers scenario A through the CLI. It adds two operations and the resume they share:

- **`amoeba handle_pause <run_id>`**, run in the paused run's checkout. It handles one kind of pause: an agent's question, from an in-process run, in a program member. It leaves every other run alone and says why. For a question it handles, it gathers context, starts the answering run from a scratch directory and waits for it. If the answer passes the check and the screen, it records the answer and resumes the run. Otherwise it records the question as waiting on the PM, with the reason. If the question already has an answer that was never delivered, it only resumes.
- **`amoeba answer <run_id> --text …`**. Records the PM's answer, which becomes the precedent for the same question next time, and resumes the run if it is still at that pause.
- **The resume.** It checks that the run is still at the question's checkpoint, starts `sq run --resume` detached from the recorded checkout with a log file, waits briefly for the run to start, and records the outcome as `resumed`, `refused` or `not_delivered`.

Each member's authorize list reaches the answer and check steps as a prompt file, and the answer screen acts as a backstop. The slice also covers the dead-claim path, migration `002`, the Squadron hook documentation, and restoring the live answering tests that 221 deleted.

## Value

User value. A run that stops on a question at night gets an answer and carries on. If it can't be answered, it leaves a recorded reason for the PM. This slice is also the test of the whole design: 225 measures it on real work before anything else is built.

## Technical Scope

**Included:** the modules in Component Structure and the decisions D1 to D15: `handle_pause`, `answer`, the shared resume, migration `002`, the answering-library changes, two config keys, the CLI subcommands, `docs/squadron-hook.md` with the contract-doc updates, and the restored live answering tests.

**Excluded:**

- `status`, `decisions`, `mark_read` and the missed-hook listing. These are 224.
- MCP. That is 226, which wraps `handle_pause` and `answer` and starts them detached.
- Any background retry, watcher or notification. The architecture rules these out.
- Sharing PM precedent across a program. It stays per member.
- Configuring the hook in real repos. That is 225.

## Dependencies

### Prerequisites

- **Slice 222 complete.** The store, config, `resolve_member`, `answering_for` and the `amoeba` entry point exist.
- **Slice 221 complete, and the audit (220).** The answering library is at `amoeba/answering/` and the Squadron reader at `amoeba/upstream/squadron/run_outcome.py`. The audit's section 6 gives the slice 182 take and rewrite groups. Section 8 gives the live tests marked `waits on 223` and the commit to restore them from.
- **Squadron**, observed at 0.24.23 on 20261107:
  - `sq runs wait <id> --timeout 0 --json` prints `status`, `pipeline`, and a `checkpoint` holding `kind`, `paused_at` and `question`. `question` is the tail of the agent's reply and can start with `…`.
  - `sq run --resume <id> --instructions <text>` resumes a paused run and adds the text to the dispatches that run.
  - `sq run --run-id <id>` creates a run under a given id.
  - The run file `~/.config/squadron/runs/<run_id>.json` (`schema_version` 5) holds `params` and `execution_mode` (`sdk` or `prompt-only`). Neither field appears in `sq runs wait --json`.
- **External, not blocking the build:**
  - `ecorkran/squadron#299` (tool-less Claude steps). Until it lands, the config names non-Claude models for the answer and check steps.
  - `ecorkran/squadron#302` (the command started on pause, and its per-run opt-out flag). Calling `handle_pause` by hand works without it. D6 and D14 say what waits on it.

### Interfaces Required

- **From 222:** the store and its transactions, the config loader, `resolve_member`, `answering_for` (giving `settings` and `not_authorized`), and the `questions` and `answers` tables with `QuestionState` and `ResumeOutcome`, as 222's API Contracts list them. D8, D6 and D12 extend the config and home.
- **From 221:** the answering library (inputs, passages, source reads, artifacts, `decide`, `gate`, `pipeline_file`, `values`), `upstream.squadron.run_outcome.poll_run`, and the Context Forge readers (`read_target`, the plan reads, `run_cf`), at the locations the audit records.

## Architecture

### Component Structure

```
src/amoeba/
├── operations/
│   ├── handle_pause.py     # handle_pause(): checks, new question, dead claim, already answered
│   ├── pause_context.py    # slice from run params, passages, PM precedent
│   ├── answering_run.py    # prepare scratch, start, wait, settle (decide + gate)
│   ├── resume.py           # resume(): checkpoint compare, detached sq run --resume, outcome
│   ├── answer.py           # answer(): PM answer, then resume
│   └── processes.py        # spawn_detached(argv, cwd, logs); stderr_tail
├── store/
│   ├── questions.py        # question and answer reads and compare-and-set writes
│   └── schema/002_pause_handling.sql
├── upstream/squadron/
│   ├── run_outcome.py      # (221) poll_run
│   └── run_file.py         # RunFacts(params, execution_mode) from the run file
├── answering/              # (221) + not_authorized.md input, no-slice reads, program passage kinds (values passed in)
├── config/home.py          # + answering_dir(), logs_dir(), squadron_runs_dir()
└── cli/main.py             # + handle_pause, answer
```

The import direction stays as 222 set it (`cli → operations → store, config, upstream, answering`). `processes.py` imports nothing from Amoeba. `run_file.py` imports nothing from `answering`.

### Data Flow

**`handle_pause <run_id>`**, started by the hook in the run's directory, or by an agent from that member's checkout:

1. `poll_run(run_id)` reads the run's outcome. A `PollFailure` is an operational error (`SquadronError`).
2. Eligibility (D3). Any check that fails ends the call with `skipped` and a `SkipReason`. Nothing is written.
3. `resolve_member(cwd)` gives the member. The question key is `(run_id, checkpoint.paused_at)`.
4. The existing question row, if any, picks the path (D4):
   - **No row.** Gather context (D5) and prepare the scratch directory (D6). Then, in one transaction, insert the row: `claimed` with the answering run id and passages, or `waiting_on_pm` if context or scratch failed. If the insert conflicts, the call lost the race: it removes its scratch directory and returns `skipped / already_claimed`.

     This reverses the architecture's order, which claims (its step 3) before working out context (its step 4). Claiming last lets one insert record either the answering run id, which the architecture requires on the claim, or the context failure with its reason, so no claim ever exists without one of them. The cost is that a losing racer repeats the `cf` and git reads and the scratch creation before it backs off. Races are rare (the hook and a catching-up agent), so this cost is small.
   - **`claimed`.** Dead-claim path (D7).
   - **`answered`, latest answer not yet resumed or refused.** Go to step 7.
   - **Anything else.** `skipped`, with the state as the reason.
5. Start the answering run detached and wait for its process to exit. Then read its outcome with `poll_run` (D6).
6. Settle (D6). `decide_answer` on the replies, then `evaluate_gate`. A confirmed answer that passes moves the row from `claimed` to `answered` and adds an `answerer` answer row, in one compare-and-set transaction. A decline moves it to `waiting_on_pm` with the reason. If the row is no longer `claimed` (the PM answered meanwhile), nothing is written and the result is `superseded`.
7. Resume (D8) with the latest answer.
8. The CLI prints the `HandlePauseResult` as JSON and exits (D13).

**`answer <run_id> [--paused-at …] --text …`**, from anywhere:

1. Find the question: the given `paused_at`, or else the run's latest question.
2. In one transaction, add a `pm` answer row and set the question to `answered`, whatever its state was.
3. Resume (D8) with this answer, from the checkout recorded on the question.

### State Management

- **Store.** Question rows, answer rows, and the resume outcome on the answer row (D10). Every write is one short `BEGIN IMMEDIATE` transaction. No transaction is held across a subprocess.
- **Files under `$AMOEBA_HOME`.** `answering/<answering_run_id>/` is the scratch directory of one answering run. It is kept, because the replies in it are evidence and the dead-claim path reads them. `logs/` holds the answering run logs and the resume logs. Nothing is pruned (Special Considerations).
- **Not stored.** Run status, checkpoint kind and slice state are read from Squadron and Context Forge on each call.

## Technical Decisions

### D1 — One reader per Squadron fact, and `paused_at` verbatim
Status: decided

- Run status, checkpoint kind, question text and `paused_at` come only from `poll_run` (`sq runs wait --json`). `params` and `execution_mode` come only from `run_file.py` (D2). No other module runs `sq runs` or opens a run file.
- `paused_at` is stored as the string `sq runs wait --json` printed, for example `2026-11-04T14:49:23.815251+00:00`. Every comparison uses a value from the same reader. The run file writes the same instant in a different form (`…Z`), and Amoeba never reads `paused_at` from it.
- The question text is stored verbatim, including a leading `…`. The answering pipeline already handles question tails (the live fixtures in `question_tails.py`).

### D2 — The run file reader
Status: decided

- `run_file.read_run_facts(runs_dir, run_id) -> RunFacts | RunFileProblem`. It reads `<runs_dir>/<run_id>.json` and checks `schema_version` is `5`. It returns `params` (string to string) and `execution_mode` as `ExecutionMode` (`sdk`, `prompt-only`). A missing file, a different schema version, invalid JSON, a missing field or an unknown mode is a `RunFileProblem` naming the file and the field. The caller raises it as `SquadronError`, and it never falls back to `sdk`.
- `runs_dir` is passed in. The CLI passes `squadron_runs_dir()` (D12), and tests pass a fixture directory.
- **Why read the file.** Squadron prints neither field in any JSON output, and the architecture already counts on the run file's `execution_mode`. All of this coupling sits in one module, behind a version check. One implementation task comments on `ecorkran/squadron#303` asking for `params` and `execution_mode` in `sq runs wait --json`. When that lands, this module switches to it and nothing else changes.

Rejected: parsing `sq run --status`, which prints a rich text box meant for people.

### D3 — What `handle_pause` leaves alone
Status: decided

The checks run in this order, and the first one that fails gives the `SkipReason` (a `StrEnum` in `operations/handle_pause.py`):

| Reason | When |
|---|---|
| `not_paused` | The outcome is not `paused`. The detail gives the outcome |
| `not_agent_question` | The checkpoint kind is not `agent_question`. The detail gives the kind, raw if unknown |
| `no_question_text` | The checkpoint has no `question` or no `paused_at` |
| `answering_run` | The run id equals some question's `answering_run_id` in the store. It is one of Amoeba's own answering runs. This store check doesn't depend on Context Forge or on #302's opt-out |
| `not_a_project` | The working directory is no Context Forge project |
| `not_in_program` | The project is in no program |
| `prompt_only` | `execution_mode` is `prompt-only`. That run belongs to the agent driving it. This check comes after the membership checks, because it needs the run file (D2), and a run-file problem must not turn a repo in no program into an error |
| `other_member` | A row for this question exists under a different member. The call was made from the wrong checkout |
| `already_claimed` | A live claim exists (D7), or this call lost the insert race |
| `waiting_on_pm` | The question is waiting on the PM |
| `settled` | The latest answer's resume outcome is `resumed` or `not_delivered` |

A skip writes nothing. Its result goes to stdout, and the run shows in Squadron as paused, as before. A Squadron or `cf` failure is not a skip. It is an operational error (exit 3), because "can't tell" must not read as "not mine".

**The checkout is the working directory.** The hook supplies the run's directory (#302), and 224's catch-up supplies Squadron's recorded one (#303). A resume started in the wrong checkout is not refused: Squadron 0.24.23 locks and runs in the caller's directory. So the result carries the claimed `checkout`, and D14 says a hand call must run in the run's own checkout. Once #303 records the directory, D2's reader returns it, and a mismatch becomes the skip `wrong_checkout`.

### D4 — The question record lifecycle
Status: decided

```
                 insert (context ok)                      settle: confirmed + screen ok
  (none) ───────────────────────────► claimed ───────────────────────────────► answered
     │                                   │  settle: declined / screen refused        ▲
     │ insert (context or scratch failed)▼                                            │
     └──────────────────────────────► waiting_on_pm ─────── answer (PM) ─────────────┘
                                         claimed ── answer (PM) ──► answered (in-flight result: superseded)
```

- The insert is `INSERT … ON CONFLICT (run_id, paused_at) DO NOTHING`. The process whose row was written is the claimant.
- Each move out of `claimed` is a compare-and-set: `UPDATE … WHERE state = 'claimed' AND answering_run_id = ?`. A second process can't settle a claim it doesn't hold, and a PM answer that arrives mid-run wins.
- An answer row is never changed apart from its resume columns (D8). A PM answer on an `answered` question adds a row, and the newest answer row is the one a resume delivers.
- `waiting_reason` is a `DeclineReason` value, checked in code (222, D3). `waiting_detail` holds the bounded detail text from `decide`.

### D5 — Context: the slice, the passages and the precedent
Status: decided

`pause_context.gather(checkout, member, program, run_facts, question, settings, cf_run) -> PauseContext | SourcesProblem`.

- **The slice.** The run's `slice` parameter (the parameter name the deleted `build_argv` used as `TARGET_PARAM_KEY`, defined once in `pause_context.py`) is a slice index. Its initiative is found through Context Forge's plan reads. The code lists the initiatives, then lists the slices of each initiative whose index is no higher than the slice's, highest first, and stops at the first list that contains the slice. The label is `<index> <name>` from that entry. A `slice` value that isn't an integer, or isn't in any plan, is `sources_missing`, naming the value. It is never treated as "no slice".
  - **Assumptions.** This relies on two Context Forge conventions, observed on 20261107. An initiative's index is never higher than its slices' indexes (for example 220 holds 220 to 227). Each `cf list slices <index> --json` entry carries an integer `index`, which the kept `plan.py` parser already requires. If an index isn't found, the result is `sources_missing`, so a broken convention shows up as a waiting question and never as a wrong slice.
  - **Fixtures.** Real `cf list initiatives --json -a` and `cf list slices <index> --json` output from this repo goes in `tests/fixtures/context_forge/`. The lookup is tested on it, including a slice that is in no plan.
- **No slice.** A run with no `slice` parameter gets the rules, the program passages and the precedent, and no plan passages. Its label is the constant `NO_SLICE_LABEL = "none"`. The plan row selection in `source_reads` becomes optional when `slice_ref` is `None`. That is the only change to the reads.
- **Committed reads.** Rules and plan files are read through `read_committed_sources` from the question's checkout, at the target Context Forge reports for it (`read_target`), as 143 built. The member's `rules_paths` come from `answering_for`.
- **Program passages.** This module reads the concept and the member list (store, `project_of`, git) and passes them to `assemble` as `ProgramSources` (D11).
- **Precedent.** `questions.pm_precedent(store, member_id)` returns, for each question of this member with a `pm` answer, the newest PM answer, with the question text, the stored slice label and the answer's `recorded_at`. Automatic answers are never precedent.
- **Failures.** Each `SourcesProblem` maps to its `DeclineReason` through the kept `sources_reason`, so the question waits on the PM with that reason. A failing `cf` call while reading the plan or the target is `sources_unreadable` with the call's output head, as 143 decided for reads.

### D6 — The answering run
Status: decided

- **Id and scratch.** The answering run id is minted as the deleted `mint_run_id` did (`amoeba-<UTC stamp>-<12 hex>`), and the function returns to `answering_run.py`. Before the claim, the scratch directory `answering_dir() / <id>` is created exclusively and filled by `prepare_scratch`, with the not-authorized file (D11). An `OSError` here becomes `answering_launch_failed`, and the row is inserted as `waiting_on_pm`.
- **Command.** `sq run <answering.yaml> <answer_model> --run-id <id> -p check-model=<check_model>`. The answer model is the positional target, as the deleted launch code noted. This slice passes no pause opt-out flag, because #302 hasn't defined one. If the answering run pauses and the hook fires on it, the call is skipped as `answering_run` (D3), because the claim already holds its id (see Order). Adding #302's flag is deferred to 225, which depends on #302 (#35).
- **Order.** Insert the claim with the answering run id, then spawn. If the process dies in between, the claim names a run that never started, and D7 handles it.
- **Spawn.** `processes.spawn_detached(argv, cwd=scratch, logs)`. It opens the logs exclusively, uses its own session, `stdin` from `/dev/null`, inherits the environment and closes file descriptors. Logs are `logs_dir() / "answering" / <id>.{stdout,stderr}.log`. A spawn error settles as `answering_launch_failed` with the error text.
- **Wait.** The parent waits up to `answering_wait_seconds` from the config for the child process to exit. The cost cap limits spend, not time, so this is the wall-clock bound. When the time runs out, the parent terminates the child's process group and settles the question as `answering_run_stalled`, with the detail `no result after <n> seconds`. Otherwise a single `poll_run(id)` gives the outcome, which becomes a `RunSummary`. A `PollFailure` here settles as `answering_run_failed` with the failure text, rather than leaving the claim hanging.
- **Config.** `answering_wait_seconds` (a number > 0) is added to `UserConfig` and `docs/config-contract.md` the same way as D8's `resume_wait_seconds`. It is required.
- **Settle.** `read_answer` and `read_check` from the scratch directory if the run completed. Then `decide_answer(summary, answer, check, passage_ids)`, with the passage ids recorded on the claim. A `Confirmed` answer goes through `evaluate_gate(question, prior, answer=…, settings=…)`, where `prior` is the run's automatic answers counted inside the settle transaction (`answered_by = 'answerer'` for this `run_id`, any `paused_at`). PM answers are never counted.
- **Before spending.** If `prior` already meets `answer_limit` when the question is first seen, the row is inserted as `waiting_on_pm` with `answer_limit_reached` and no answering run starts. The gate's own check stays as the final word.

### D7 — The dead claim
Status: decided

A `claimed` row seen by a later call means another process is answering it, or one died partway. The recorded `answering_run_id` decides which:

| `poll_run(answering_run_id)` | Meaning | Action |
|---|---|---|
| `timed_out` (still running), `claimed_at` within `answering_wait_seconds` | Someone is still answering | `skipped / already_claimed` |
| `timed_out` (still running), `claimed_at` older than `answering_wait_seconds` | The run hung and its waiter is gone | Compare-and-set the row to `waiting_on_pm` with `answering_run_stalled`. A later reply from that run is ignored, because the row is no longer `claimed` |
| `completed`, `failed`, `paused`, `orphaned` | The run finished and its settler died | Settle from the scratch directory (D6), then resume |
| `not_found`, `claimed_at` within `answering_wait_seconds` | The claimant may still be starting its run: Squadron writes no run file until `sq` has loaded the pipeline, which takes seconds | `skipped / already_claimed` |
| `not_found`, `claimed_at` older than `answering_wait_seconds` | The claimant died before the spawn | Gather context again, prepare a new scratch directory under a new id, compare-and-set `answering_run_id` and the passages from the old id to the new, spawn, and continue as D6 |
| `PollFailure` | Unknown | Operational error, nothing written |

With the age gate, only a claimant that died before its spawn leads to a second answering run, which is the double-spend case the architecture accepts.

### D8 — The resume
Status: decided

`resume.resume(store, question, answer_seq, *, deps) -> ResumeResult`. Both operations call it.

1. **Check the checkpoint.** `poll_run(run_id)`. If the run is not `paused`, or its `checkpoint.paused_at` differs from the question's, the outcome is `not_delivered`, and nothing is started.
2. **Start.** `sq run --resume <run_id> --instructions <compose_instructions(question, answer)>`, spawned detached with `cwd` set to `questions.checkout`. The logs are `logs_dir() / "resume" / <run_id> / <answer_seq>-<UTC stamp>.{stdout,stderr}.log`. The stdout log path is recorded as `resume_log`. A spawn error is `refused`, with the error text.
3. **Wait for `running`.** Poll every `RESUME_POLL_INTERVAL_SECONDS` (0.5, defined once in `resume.py`) for up to `resume_wait_seconds` from the config:
   - The run is `running`, or has moved past this pause (another `paused_at`, or `completed` or `failed`): **resumed**. A fast run can pause again before a poll sees `running`.
   - The child has exited and the run is still at this pause: **refused**, with the stderr tail as the detail. A held run lock is one cause.
   - Time runs out with the child alive and the run unchanged: terminate the child's process group, wait for it to exit, then poll once more. The child can take the lock between the last poll and the kill, so this final poll decides:
     - Still paused at this pause: **refused**, with the detail `not running after <n> seconds`.
     - `running` or moved past: **resumed**, with the detail `resume process terminated after taking the run`. Squadron then reports the run through its own state (orphaned or failed), and `status` shows it like any other run.
4. **Record.** Write `resume_outcome`, `resume_detail`, `resume_log` and `resume_at` on the answer row with `WHERE resume_outcome IS NULL OR resume_outcome = 'refused'`. A `resumed` or `not_delivered` outcome is never overwritten. So if two resumes race, the run lock refuses the second, and the first one's `resumed` stands.

`resume_wait_seconds` (a number > 0) is added to `UserConfig` and `docs/config-contract.md` under 222's D5 rule. It is required, so an existing config fails and names it.

Once resumed, the run belongs to Squadron. A refused resume, or a process that died between steps 2 and 4, leaves the answer with no outcome or with `refused`. The next `handle_pause` takes the "already answered" path and resumes with the recorded answer, starting no new answering run.

### D9 — The `answer` operation
Status: decided

`answer.answer(store, config, document, *, deps) -> AnswerResult`, where `document` is validated into `AnswerRequest` (`run_id`, optional `paused_at`, `text`). The CLI and 226's MCP tool pass input through unchanged, as with `set_up`.

- **Finding the question.** By `(run_id, paused_at)`, or the run's row with the latest `claimed_at` when `paused_at` is omitted. No row is `rejected / no_such_question`. The detail says Amoeba never saw that pause, and that `handle_pause` from the run's checkout records it. Without a row, Amoeba has no checkout to resume from.
- **Text.** It is stripped and must be non-empty, or the request is `rejected / malformed`. PM answers skip the screen and the limit. The PM can authorize anything.
- **Write.** One transaction adds an answer row with `answered_by = 'pm'` and sets the question to `answered`, from any state. Its newest PM answer is then the precedent for repeats (D5), so this also covers an override of an automatic answer.
- **Resume.** D8 with the new answer row. On a question that was already resumed, the checkpoint compare finds the run past that pause, and this answer is recorded as `not_delivered`. The override still stands as precedent.
- **Result.** `outcome` (`recorded` or `rejected`), the question key, `answer_seq`, the `ResumeResult`, and `problems`.

### D10 — Migration `002_pause_handling.sql`
Status: decided

It follows 222's D3 rule: `ALTER TABLE … ADD COLUMN` only, with nullable columns.

| Table | Added column | Holds |
|---|---|---|
| `questions` | `slice_label` | D5's label, used again on precedent passages |
| `questions` | `source_commit` | The commit the passages were read at |
| `questions` | `passages` | JSON array of `PassageRef` (id, kind, source, date) |
| `questions` | `waiting_detail` | Bounded detail for `waiting_reason` |
| `questions` | `evidence` | JSON `AnsweringEvidence`: the proposed answer, the citations, the check's verdict and reason |
| `answers` | `cited` | JSON array of passage ids (automatic answers) |
| `answers` | `resume_detail` | The refusal reason, or the not-delivered detail |
| `answers` | `resume_log` | The resume's stdout log path |
| `answers` | `resume_at` | When the outcome was recorded |

`EXPECTED_SCHEMA_VERSION` becomes 2. Each JSON column is written by one serializer and read by one parser in `store/questions.py`, and is tested round-trip.

### D11 — Changes to the answering library
Status: decided

- **Not-authorized file.** `pipeline_file.NOT_AUTHORIZED_FILE = "not_authorized.md"`. `inputs.render_not_authorized(items)` writes one bullet per item: `key: description`. An empty list renders the constant sentence `No item is barred for this repository.` `prepare_scratch` takes the items and writes the file. In `answering.yaml`, both steps list it in `prompt_files` after `passages.md`. The hard-coded list ("a push, a merge to main, …") in both prompts is replaced by text telling the step that the list follows the passages, and that it must decline (answer step) or reply no (check step) when an answer would authorize anything on it. The existing test that pins step, parameter and file names to `pipeline_file.py` covers the new file.
- **Screen.** `MemberAnswering.settings.reserved_terms` already holds only the member's barred items (222, D8). `evaluate_gate` is unchanged. So allowing an item for a member takes it off both the prompt file and the screen.
- **Program passages.** `program_concept` and `program_members` come from the slice 182 take group, as audit section 6 records it. `answering.passages` gains the two kinds and their rendering. `assemble` takes them as plain values: a `ProgramSources` holding the concept as a `SourceFile` (member id, path, commit, date, text) and the member list. `answering` imports no store module and runs no `cf` call, because `store` already imports `answering.values` and the reverse would be a cycle.
- **Where the program reads happen.** All of them are in `operations/pause_context.py` (D5), in place of 181's `read_member`:
  - the concept member and path from `programs`
  - the member list from `members_of`
  - the concept member's checkout from `project_path` on the `CFProject` that `project_of(reference=…)` returns (222, D6, where `CFProject` holds `id`, `name` and `project_path`)
  - the concept file through the existing git allowlist at that checkout's target, as 182's D3 specified. If the asker is the concept member, its own pinned commit is used (182, D3).

  `tests/test_import_boundaries.py` gains the rule that `amoeba.answering` imports nothing from `amoeba.store`, `amoeba.config` or `amoeba.operations`. Both prompts list the two new kind words.
- **No-slice reads.** D5.

Rejected: putting the member's list into the pipeline as a parameter. Squadron splits `-p` values on commas, and the descriptions are prose.

### D12 — Home paths
Status: decided

`config/home.py` gains `answering_dir()` (`amoeba_home() / "answering"`), `logs_dir()` (`amoeba_home() / "logs"`) and `squadron_runs_dir()` (`Path.home() / ".config" / "squadron" / "runs"`, the default Squadron reads). Each name is a constant there. The last one sits in `home.py` because 222's AST rule (222, D10) lets only that module call `Path.home`. Operations take these paths as arguments. Only the CLI calls the helpers.

Unit tests pass a fixture directory to the reader. CLI subprocess tests set `HOME` to a temporary directory holding `.config/squadron/runs/<run_id>.json`, copied from the recorded run file. `Path.home()` reads `HOME`, so the CLI resolves the test directory with no new variable, and no test reads the developer's real run files.

### D13 — CLI
Status: decided

```
amoeba handle_pause <run_id>
amoeba answer <run_id> [--paused-at <ts>] --text <answer>
```

- Both print their result model as JSON on stdout.
- Exit codes extend 222's named constants. For `handle_pause`, every outcome is exit `0`, including `skipped`, because a skip is a correct answer. `answer` exits `1` when `rejected`. `2` is a usage error. `3` is an operational error: `SquadronError`, `ContextForgeError`, `ConfigError`, `AmoebaHomeError` or any `StoreError`.
- `HandlePauseResult.outcome` is one of `skipped`, `waiting_on_pm`, `superseded`, `resumed`, `refused` or `not_delivered`, plus `skip_reason` or `waiting_reason`, `detail`, the question key, the claimed `checkout`, `answering_run_id` and `answer_seq` where they apply.
- **No call log.** A call that writes no question row leaves a pause that still shows in Squadron as paused, and 224's `status` lists it as a missed hook, as the architecture intends. Operational errors go to stderr with exit 3. Logging why a hook call was missed is deferred until 225 shows the need (#34).

### D14 — Wiring the hook
Status: decided

`docs/squadron-hook.md` gives:

- The command to configure: `amoeba handle_pause <run_id>`, run in the run's directory. Squadron supplies both (#302).
- The hand call. The exact config line is added with #302's form in 225 (#35).
- That only repos in a program need anything, and that a run started with the opt-out flag is left alone.
- That a hand call must run in the run's own checkout, because until #303 nothing confirms it, and a resume started elsewhere works in that directory (D3).
- That the hook's environment must reach `sq`, `cf`, `git` and the model credentials, because the resume inherits it (architecture, "The resume's environment").

### D15 — Tests
Status: decided

- **Fake `sq` and recorded output.** Unit and CLI tests use a fake `sq` script first on `PATH`, which replays recorded `sq runs wait --json` documents and exit codes. Recordings in `tests/fixtures/squadron/` come from real Squadron 0.24.23 output: an `agent_question` pause (the run captured on 20261107 is a model), another checkpoint kind, a running run and a completed run. A real schema-5 run file is the `run_file` parser's fixture, as the project's parsing rules require.
- **Unit coverage.** Every `SkipReason`. Each `DeclineReason` the paths can produce. Every row of D7's table. Each D8 branch: `not_delivered`, `resumed` on `running`, `resumed` on moved-past, `refused` on child exit, `refused` on timeout, and `resumed` when the final poll after the timeout kill finds the run `running`. The compare-and-set guards: a PM answer during settling gives `superseded`, and `resumed` is never overwritten. The answer-limit count ignores PM answers. The authorize-list path: an item barred for one member and allowed for another.
- **Live tier** (`tests/live/pause/`, outside the default suite like `tests/live/answering`):
  - A fixture pipeline whose single dispatch is told to end on a question that the repo's rules settle. It runs in a throwaway worktree of the amoeba repo, registered as a member under a test `AMOEBA_HOME`. The test runs it, sees an `agent_question` pause, calls `amoeba handle_pause`, and asserts that the record holds the question, passages, answer and `resumed`, and that the run left the pause.
  - The audit's section 8 `waits on 223` files are restored from the named commit and rewritten to drive `handle_pause` in place of the stage. Each keeps its claim.

## Implementation Details

### API Contracts

The CLI is in D13.

**Python (for 224 and 226)**

- `operations.handle_pause.handle_pause(store, config, run_id, *, directory, deps) -> HandlePauseResult`
- `operations.answer.answer(store, config, document: object, *, deps) -> AnswerResult`
- `operations.resume.resume(...)`, internal to the two operations
- `store.questions`: `get_question`, `latest_question`, `answers_of`, `latest_answer`, `automatic_answer_count`, `pm_precedent`, and the writes D4 and D8 name
- `deps` bundles the injected `cf` runner, `poll_run`, the spawner and the paths, so tests and 226 pass the same set

### Database / Storage Schema

D10 gives the columns. `docs/store-contract.md` gets them, the `SkipReason` and result vocabularies, and which operation writes each column.

## Integration Points

### Provides to Other Slices

- **224**: the question states, `waiting_reason` and `waiting_detail`, and the answer rows with `seq`, `answered_by`, `cited` and the resume columns. `status` needs these to show waiting questions and answers not yet resumed. A question with an answer whose `resume_outcome` is null or `refused` is "answered, not resumed". `handle_pause` is what `status` points an agent at for a missed hook.
- **225**: `docs/squadron-hook.md`, and `decisions`-ready records to measure.
- **226**: `handle_pause` and `answer` with request and result models and the `deps` bundle. MCP starts them as detached CLI processes. The run's checkout is a required input of `handle_pause`: MCP must start it with `cwd` set to that directory, and the directory comes from 224's listing (Squadron's recorded directory, #303). It is never the MCP server's own directory (D3).

### Consumes from Other Slices

- **222**: as listed under Interfaces Required. If a needed store read is missing from `store.programs`, it is added there, not copied.
- **221 and the audit**: the library and the 182 groups. If the audit's 182 take group is empty, D11's program passages are written new from 182's design.
- **Squadron**: if `sq` is missing or fails, every path stops with `SquadronError` before writing anything. The one exception is the D6 wait, which records a decline so the claim doesn't hang.

## Success Criteria

### Functional Requirements

- On a real paused run in a member, `handle_pause` answers it and resumes it. The record shows the question, its passages, the answer with its citations and the check's verdict, and `resumed`.
- A run in no program, a prompt-only run, a non-question checkpoint and an already-claimed question are each `skipped` with their reason, and nothing is written.
- An answer that authorizes an item on the member's list waits on the PM, with `check_said_no` or `reserved_term`. After `set_up` allows that item for the member, the same question is answered.
- A run resumed by someone else before Amoeba's resume is recorded as `not_delivered` and is not resumed again.
- A `refused` resume, or one whose `handle_pause` died before recording, is resumed by a second `handle_pause` with the recorded answer and no new answering run.
- A claim whose answering run finished after its settler died is settled by the next call from the scratch directory. A claim whose run never started gets one new answering run.
- `answer` on a waiting question records it, resumes the run, and is offered as precedent when the same question is asked at a later pause. It never counts toward the answer limit.
- `answer` during an in-flight answering run wins, and the in-flight call reports `superseded`.

### Technical Requirements

- `ruff format --check`, `ruff check`, `pyright` (strict) and `pytest` pass.
- The D15 unit tests pass on the recorded Squadron fixtures. The `run_file` parser passes on a real run file.
- Migration `002` applies on a store created at version 1, and the JSON columns round-trip.
- No transaction is open while a subprocess runs. A test asserts this through the injected spawner and poller.
- `answering.yaml` holds no hard-coded authorize list. The pin test covers `not_authorized.md`.
- `docs/squadron-hook.md`, `docs/store-contract.md` and `docs/config-contract.md` match the code.
- The live tier in `tests/live/pause` and the restored `tests/live/answering` files pass with the `AMOEBA_LIVE_*` variables set.
- A comment on `ecorkran/squadron#303` asks for `params` and `execution_mode` in `sq runs wait --json` (D2).

### Integration Requirements

- 224 can list waiting questions, answers not yet resumed and missed hooks from the store and Squadron, with no new columns.
- 226 can expose both operations by passing MCP input to the same functions.

### Verification Walkthrough

Run from the amoeba repo root. Steps 2 to 7 use a scratch home with a config copied from `docs/config-contract.md`, with `resume_wait_seconds` and `answering_wait_seconds` set and non-Claude answer and check models until `#299` lands.

1. **Checks.**
   ```bash
   uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest
   ```
   Expected: all pass.

2. **Set up.**
   ```bash
   export AMOEBA_HOME="$(mktemp -d)"; cp <filled config> "$AMOEBA_HOME/config.yaml"
   printf 'program: demo\nmembers:\n  - rules_paths: [CLAUDE.md]\n' | uv run amoeba set_up --file -
   ```
   Expected: `applied`, with amoeba as a member.

3. **Make a real pause.** Run the live tier's fixture pipeline by hand. It has no `slice` parameter, so the no-slice path is used and the rules settle the question.
   ```bash
   sq run tests/live/pause/asks_question.yaml <model> --run-id demo-pause-1
   sq runs wait demo-pause-1 --timeout 0 --json
   ```
   Expected: `outcome: paused`, `checkpoint.kind: agent_question`, and a question about file length limits.

4. **Leave-alone cases.**
   - `cd /tmp && uv run --project <amoeba repo> amoeba handle_pause demo-pause-1`. Expected: `skipped`, `not_a_project`.
   - `uv run amoeba handle_pause <id of any completed run>`. Expected: `skipped`, `not_paused`.

5. **Answer and resume.** From the repo root: `uv run amoeba handle_pause demo-pause-1`. Expected: `"outcome": "resumed"`, an `answering_run_id`, an `answer_seq`. `sq runs wait demo-pause-1 --timeout 0 --json` shows the run `running`, or past that pause. Then:
   ```bash
   sqlite3 "$AMOEBA_HOME/amoeba.sqlite3" "select state, slice_label, passages, evidence from questions; select answered_by, answer, cited, resume_outcome, resume_log from answers;"
   ```
   Expected: `answered`, the passages, the check's `yes`, an `answerer` answer with citations, `resumed`, and a log path that exists. Run `uv run amoeba handle_pause demo-pause-1` again. Expected: `skipped`, `settled`.

6. **Authorize list.** Covered by the D15 unit test of an item barred for one member and allowed for another, and by the success criterion's `set_up` allow.

7. **PM answer and precedent.** Covered by D15. By hand: `uv run amoeba answer <run_id> --text "…"` on a `waiting_on_pm` question gives `recorded` and a `resume` result.

8. **Not delivered, refused and retried.** These are covered by the D15 unit tests, and the D8 branches are exercised against the recorded Squadron fixtures.

9. **Live tier.** `uv run pytest tests/live/pause tests/live/answering` with the `AMOEBA_LIVE_*` variables set. Expected: passes.

## Risk Assessment

### Technical Risks

- **Resuming real runs on a model's answer.** A wrong answer goes into every dispatch of the resumed run. This is the risk the slice plan names.
- **Coupling to Squadron's run file.** `params` and `execution_mode` are read from a file whose format Squadron owns.
- **Squadron behavior not observed yet.** The `running` transition timing on resume, and how a fast-pausing run looks to the poll.

### Mitigation Strategies

- The answer passes an independent check, the member's authorize list and the screen. Every answer, its passages and its verdict are in the record, and 225 measures wrong answers before anything more is built.
- One reader module, a schema version check that fails loudly, and the #303 comment so the file read can be replaced.
- D8 treats "moved past this pause" as resumed. The live test exercises the real transition, and anything it shows that the fixtures lack becomes a fixture.

## Implementation Notes

### Development Approach

Suggested order, each step ending with the checks passing:

1. Migration `002`, `store/questions.py` with its compare-and-set writes, and the round-trip tests.
2. `upstream/squadron/run_file.py` with the real run-file fixture. The home helpers (D12). The recorded `sq` fixtures and the fake `sq` script.
3. Library changes (D11): the not-authorized file and prompts, no-slice reads, program passages from the 182 groups.
4. `pause_context.py` (D5).
5. `processes.py`, then `answering_run.py`: scratch, spawn, wait, settle (D6).
6. `resume.py` (D8).
7. `handle_pause.py`: checks, paths and dead claim (D3, D4, D7). Then `answer.py` (D9).
8. CLI subcommands and exit codes (D13). The `resume_wait_seconds` and `answering_wait_seconds` config keys. Contract docs.
9. Live tier: the fixture pipeline, the pause test, the restored `waits on 223` files (D15). `docs/squadron-hook.md` (D14). The #303 comment.
10. The Verification Walkthrough, with results in the task notes.

Effort: 5.

### Special Considerations

- **Security.** The answer text reaches tool-using dispatches through `--instructions`. That is intended, and D11 and the screen are its limits. The question text from the run is stored and rendered as data in `question.md`, never put on a command line except as the single `--instructions` argument, passed as an argv element with no shell.
- **Disk.** Scratch directories and logs are kept as evidence and never pruned. At one PM's question volume they are small. Pruning waits until use shows the need.
- **Spend.** Each answering run is capped by `max_cost_usd`. A work run's unattended resumes are bounded by `answer_limit`, as the architecture describes. No per-window cap is designed (slice plan Future Work).
