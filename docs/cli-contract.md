---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: The amoeba command line: each subcommand's arguments, its JSON result on stdout and the exit-code table.
dateCreated: 20261110
dateUpdated: 20261111
status: complete
---

# CLI contract

`amoeba <command>` is the process boundary. It alone resolves the home (`$AMOEBA_HOME`,
see `store-contract.md`), reads the user config (`config-contract.md`) and builds the
real edges (`sq`, `cf`, `git`, the clock). Each operation prints its result as JSON on
stdout.

## Exit codes

| Code | Meaning | Causes |
|---|---|---|
| 0 | The operation ran | `set_up` applied or unchanged; `handle_pause` any outcome, including `skipped`; `answer` recorded; `status` and `decisions` listed; `mark_read` moved or unchanged |
| 1 | The operation refused the request; the result says why | `set_up`, `answer`, `status`, `decisions` or `mark_read` rejected |
| 2 | Usage | bad arguments (a missing or non-integer `mark_read --through`, for one), or a `set_up` request file that cannot be read, is not UTF-8 or is not YAML |
| 3 | Operational failure; message on stderr as `error: <ExceptionName>: <message>` | `ConfigError`, `AmoebaHomeError`, `ContextForgeError`, `SquadronError`, any `StoreError` |

A Squadron or Context Forge failure is an exit 3, never a skip: "cannot tell" is not
"not mine". Nothing is written before it.

## `amoeba set_up --file PATH`

`PATH` is a YAML request document; `-` reads standard input. Result (`SetUpResult`):
`outcome` (`applied`, `unchanged` or `rejected`), `changes` (one line per changed
row), `problems` (empty unless rejected), `program` (the program as stored, or null)
and `working_directory` (informational, or null for a malformed request). Exit 1 when
`rejected`.

## `amoeba handle_pause RUN_ID`

Run it from the paused run's own checkout (Squadron does not yet confirm the
directory). It answers an agent's question and resumes the run, or records the
question as waiting on the PM. Result (`HandlePauseResult`), fields that do not apply
are null:

| Field | Meaning |
|---|---|
| `outcome` | `skipped`, `waiting_on_pm`, `superseded`, `resumed`, `refused` or `not_delivered` |
| `skip_reason` | with `skipped`: `not_paused`, `not_agent_question`, `no_question_text`, `answering_run`, `not_a_project`, `not_in_program`, `prompt_only`, `other_member`, `already_claimed`, `waiting_on_pm` or `settled` |
| `waiting_reason` | with `waiting_on_pm`: the `DeclineReason` (see `store-contract.md`) |
| `detail` | why it was skipped (some reasons), declined, refused or not delivered |
| `key` | the question: `run_id` and `paused_at` exactly as `sq runs wait --json` prints it |
| `checkout` | the checkout the question was claimed in |
| `answering_run_id` | the answering run, when one was involved |
| `answer_seq` | the answer that was handed to the run, with `resumed`, `refused` or `not_delivered` |

Exit 0 for every outcome.

## `amoeba answer RUN_ID [--paused-at TIMESTAMP] --text ANSWER`

Records the PM's answer to the question, then resumes the run. `--paused-at` is the
pause as `sq runs wait --json` prints it; without it the run's latest question is
used. Result (`AnswerResult`):

| Field | Meaning |
|---|---|
| `outcome` | `recorded` or `rejected` |
| `rejection` | with `rejected`: `no_such_question` (run `amoeba handle_pause RUN_ID` from the run's checkout first) or `malformed` (blank text, unknown field, bad type) |
| `key` | the question, when `recorded` |
| `answer_seq` | the answer row, when `recorded` |
| `resume` | `outcome` (`resumed`, `refused` or `not_delivered`), `detail`, `resume_log` |
| `problems` | one line per problem when `rejected` |

Exit 1 when `rejected`, else 0. A refused or not-delivered resume, including one
refused because `sq` could not be read, still exits 0: the answer is recorded and is
precedent.

## `amoeba status [--program ID]`

What is running, paused and waiting on the PM. Needs the config (for
`answering_wait_seconds`) and `sq runs list --json`. Scope: `--program ID` is that
program; with no flag, run from a member's checkout it is that member's program, and
from anywhere else it is every program. A failing `cf` while finding the checkout's
project is exit 3, never a wider scope. Every member in scope is listed, even with
nothing to show. Result (`StatusResult`):

| Field | Meaning |
|---|---|
| `outcome` | `listed` or `rejected` |
| `rejection` | with `rejected`: `unknown_program` (`problems` lists the known ids) or `malformed` |
| `programs` | per program, `members`: each `{id, name}` with `runs` and `waiting_on_pm` |
| `unplaced_runs` | paused runs no member could be found for: `run_id`, `status`, `reason`, `checkpoint_kind`, `detail` |
| `problems` | one line per problem when `rejected` |

A run (`runs`) has `run_id`, `pipeline`, `status` (Squadron's text, raw),
`working_directory`, `checkpoint` (`kind`, `paused_at`, `question`, or null), `pause`,
`detail` and `next`. `pause` is null for a run that is not paused, else one of:

| `pause` | Meaning | `next` |
|---|---|---|
| `not_paused` | (never shown; a run that is not paused has a null `pause`) | none |
| `other_checkpoint` | stopped at another checkpoint kind; `detail` names it | none |
| `no_question_text` | an agent question with no text or `paused_at` | none |
| `prompt_only` | a prompt-only run: its own agent's | none |
| `unhandled` | a missed hook: no question recorded | `handle_pause` |
| `claim_live` | being answered now | none |
| `claim_stale` | a claim past `answering_wait_seconds` | `handle_pause` |
| `waiting_on_pm` | waiting on the PM (also in `waiting_on_pm`) | none here |
| `answered_unresumed` | answered, not handed back; `detail` gives the resume outcome | `handle_pause` |
| `settled` | answered and handed back; `detail` gives the outcome | none |
| `run_file_unreadable` | Squadron's run file could not be read; `detail` says why | none |

`next` is `{operation, run_id, paused_at, directory}` or null. For `handle_pause`,
`directory` is the run's own checkout: run the command there. A waiting question
(`waiting_on_pm`) has `run_id`, `paused_at`, `question`, `slice_label`,
`waiting_reason`, `waiting_detail`, `since`, `run_state` and `next`. Every waiting
question of a member in scope is listed. `run_state` is `at_pause` (`next` is
`answer`), `moved_on` (`detail` gives the run's state) or `not_listed`. `reason` of an
unplaced run is `no_directory` (a run from before `sq` 0.24.24), `directory_missing`
or `lookup_failed` (`detail` has the `cf` error). A run's `status` is Squadron's text,
so a status newer than this code is shown as it is.

## `amoeba decisions [--since ISO-8601] [--program ID]`

The answers recorded since the PM's marker (or `--since`), oldest first, from every
program unless `--program` narrows it. `--since` is ISO-8601 with a UTC offset.
Result (`DecisionsResult`):

| Field | Meaning |
|---|---|
| `outcome` | `listed` or `rejected` |
| `rejection` | with `rejected`: `unknown_program` or `malformed` |
| `records` | each: `seq`, `recorded_at`, `program`, `member` (`{id, name}`), `run_id`, `paused_at`, `slice_label`, `question`, `answered_by` (`answerer` or `pm`), `answer`, `prior_answer_seq`, `based_on`, `resume` |
| `read_through` | the last listed `seq`, only when the listing started at the marker, was not narrowed and is not empty; else null. Give it to `mark_read` |
| `marker` | the marker's value when read |
| `problems` | one line per problem when `rejected` |

`prior_answer_seq` is the newest earlier answer to the same question (a PM answer after
an automatic one is an override). `based_on` is, for `answerer`, the cited passages
(`id`, `kind`, `source`, `date`; `kind` is `pm_answer` for a PM precedent and null for
the others, which the store records no kind for) with `check_verdict` and
`check_reason`; for `pm`, the question's `waiting_reason` and `waiting_detail`, or null
if the PM answered before the question waited. `resume` is `outcome`, `detail`, `at`.

## `amoeba mark_read --through SEQ`

Moves the PM's marker forward to `SEQ`, the `read_through` of a `decisions` call. There
is no "mark all": a record written after that call keeps a higher `seq` and stays
unread. Result (`MarkReadResult`): `outcome` (`moved`, `unchanged` or `rejected`),
`rejection` (`beyond_last_record` when `SEQ` is above the last answer, `malformed` for
a negative or non-integer `SEQ`), `previous`, `current`, `problems`. The marker never
moves backward, so an equal or lower `SEQ` is `unchanged`. Exit 1 when `rejected`.
