---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: The amoeba command line: each subcommand's arguments, its JSON result on stdout and the exit-code table.
dateCreated: 20261110
dateUpdated: 20261112
status: complete
---

# CLI contract

`amoeba <command>` is the process boundary. It alone resolves the two homes (the config
home and the state home, see `store-contract.md`), reads the user config
(`config-contract.md`) and builds the real edges (`sq`, `cf`, `git`, the clock). Each
operation prints its result as JSON on stdout.

The first command after an upgrade from a pre-228 install moves the old state out of
`~/.config/amoeba/` into the state home before it does its own work, and writes one
line to stderr (`amoeba: moved state from <old> to <new> ...`) only when something
moved. A store that cannot be moved or verified is exit 3 (`StoreRelocateError`) with
the old store untouched.

## Exit codes

| Code | Meaning | Causes |
|---|---|---|
| 0 | The operation ran | `set_up` applied or unchanged; `handle_pause` any outcome, including `skipped`; `answer` recorded; `dismiss` dismissed or unchanged; `retract` retracted or unchanged; `status` and `decisions` listed; `mark_read` moved or unchanged |
| 1 | The operation refused the request; the result says why | `set_up`, `answer`, `dismiss`, `retract`, `status`, `decisions` or `mark_read` rejected |
| 2 | Usage | bad arguments (a missing or non-integer `mark_read --through`, for one), or a `set_up` request file that cannot be read, is not UTF-8 or is not YAML |
| 3 | Operational failure; message on stderr as `error: <ExceptionName>: <message>` | `ConfigError`, `AmoebaHomeError`, `ContextForgeError`, `SquadronError`, any `StoreError` (including `StoreRelocateError`, a legacy store that could not be moved) |

A Squadron or Context Forge failure is an exit 3, never a skip: "cannot tell" is not
"not mine". Nothing is written before it.

## `amoeba set_up --file PATH`

`PATH` is a YAML request document; `-` reads standard input. Result (`SetUpResult`):
`outcome` (`applied`, `unchanged` or `rejected`), `changes` (one line per changed
row), `problems` (empty unless rejected), `program` (the program as stored, or null)
and `working_directory` (informational, or null for a malformed request). Exit 1 when
`rejected`.

Each problem has a `code` and a `detail` naming the field at fault. Codes: `malformed`,
`not_a_project`, `empty_program`, `member_of_other_program`, `rules_paths_required`,
`unknown_provider`, `self_dependency`, `unknown_authorize_item`,
`concept_member_not_member`, `member_has_open_questions` and `not_a_member`. Any problem
rejects the whole request and writes nothing.

### `remove`

A request may carry a `remove` section; omitted removes nothing:

```yaml
program: demo
concept: null                     # removes the concept (omitted leaves it)
remove:
  members: [some-member]          # Context Forge names or ids
  pairs:
    - {provider: some-provider, consumer: some-consumer}
```

- A removed member is **soft-removed**: its row stays (its questions and answers are
  the record), its pairs are deleted, and everywhere else it is treated as not a
  member (`NotInProgram`, absent from `status` and the program's members). Naming it
  again under `members` re-registers it, with `rules_paths` required as for a new
  member, in this or another program. A pair is deleted.
- A reference Context Forge does not know is read as a stored member id, so a member
  whose Context Forge project was deleted can still be removed by its id.
- Removing an already removed member or an absent pair is no change, so a repeat is
  `unchanged`. `changes` gains `removed member <id>` and `removed pair <provider> ->
  <consumer>`.
- Removing the program's concept member while the concept stays is rejected
  (`concept_member_not_member`). Clear the concept in the same request with
  `concept: null` (the one way to remove a concept), or move it.
- New problem codes: `member_has_open_questions` (a `claimed` or `waiting_on_pm`
  question, or an `answered` one whose answer was not yet handed back; the detail lists
  the keys: `dismiss` or `answer` them first) and `not_a_member` (the reference is no
  member of this program, past or present). `malformed` also covers a member under both
  `members` and `remove.members`, a pair under both `depends_on` and `remove.pairs`,
  and a removed member named as the end of a pair (in `remove.pairs` or as a
  `depends_on` provider). Any problem rejects the whole request.

## `amoeba handle_pause RUN_ID`

Run it from the paused run's own checkout. For a run started on `sq` 0.24.24 or later
Squadron records where the run started, and a call from another directory is skipped
as `wrong_checkout`; an older run file records nothing and is not checked. It answers an
agent's question and resumes the run, or records the question as waiting on the PM.
Before anything else it closes this run's open questions at earlier pauses (the run
moved on, or is gone), and at the end it prunes old scratch and logs; what either did,
or could not do, is appended to `detail`. Every call adds one line to the calls log
(see below). Result (`HandlePauseResult`), fields that do not apply are null:

| Field | Meaning |
|---|---|
| `outcome` | `skipped`, `waiting_on_pm`, `superseded`, `resumed`, `refused` or `not_delivered` |
| `skip_reason` | with `skipped`: `not_paused`, `not_agent_question`, `no_question_text`, `answering_run`, `not_a_project`, `not_in_program`, `prompt_only`, `other_member`, `already_claimed`, `waiting_on_pm`, `settled`, `closed` or `wrong_checkout` |
| `waiting_reason` | with `waiting_on_pm`: the `DeclineReason` (see `store-contract.md`) |
| `detail` | why it was skipped (some reasons), declined, refused or not delivered, then any sweep or prune notes |
| `key` | the question: `run_id` and `paused_at` exactly as `sq runs wait --json` prints it |
| `checkout` | the checkout the question was claimed in |
| `answering_run_id` | the answering run, when one was involved |
| `answer_seq` | the answer that was handed to the run, with `resumed`, `refused` or `not_delivered` |

`skip_reason` `closed`: the pause's question was closed (dismissed, or its run moved
on or is gone) and is not handled again; `answer` reopens it. `wrong_checkout`: the
call was not from the checkout of the run's recorded directory (a subdirectory of it
is the same checkout; another worktree is not); `detail` names both directories, and says
so when the recorded directory no longer exists (then use Squadron's own commands, such as
`sq run --resume`). Exit 0 for every outcome.

### The calls log

Every `handle_pause` call appends one JSON line to
`<state home>/logs/calls/<UTC date>.jsonl`, whatever happened. A result is
`{at, run_id, directory, outcome, reason, detail}` (`reason` is the skip or waiting
reason); an exit-3 error, a `ConfigError` before any store opens included, is
`{at, run_id, directory, error, detail}` with the exception's name in `error`.
`directory` is the call's working directory and `detail` is cut to 4 KiB. A failing
log write puts one line on stderr and changes neither the result nor the exit code. An
`AmoebaHomeError` about the state home has nowhere to be logged and goes to stderr only.
Day files older than `prune_after_days` are deleted.

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

## `amoeba dismiss RUN_ID [--paused-at TIMESTAMP] --reason TEXT`

Closes a question that has no answer to deliver. `--paused-at` is the pause as
`sq runs wait --json` prints it; without it the run's latest question is used. The run
is not resumed or ended: it stays paused in Squadron, where `sq run --resume`
continues it. The reason is stored and returned as data. Result (`DismissResult`):

| Field | Meaning |
|---|---|
| `outcome` | `dismissed`, `unchanged` or `rejected` |
| `rejection` | with `rejected`: `no_such_question`, `malformed` (blank reason, unknown field, bad type) or `not_open` |
| `key` | the question |
| `closed_reason`, `closed_detail` | with `dismissed` or `unchanged`: why the question is closed (`dismissed` and the reason, or what closed it before) |
| `problems` | one line per problem when `rejected` |

`claimed` and `waiting_on_pm` close as `dismissed`; an `answered` question whose
answer was not yet handed back closes too and that answer becomes `not_delivered`
(`dismissed`). Already `closed` is `unchanged`. `answered` with a delivered answer is
`not_open`: the detail says a `resumed` answer was delivered and that `retract` stops it
being precedent, that a `not_delivered` answer was recorded but never delivered, or that
its resume is in flight (dismiss again once it has ended). An
`answer` to a closed question reopens it. Exit 1 when `rejected`, else 0.

## `amoeba retract ANSWER_SEQ --reason TEXT`

Stops a PM answer being precedent for later answers and for the answering run's
passages. The answer stays delivered and stays in `decisions`, with `retracted_at` and
`retract_reason`. A new PM answer to the same question is the undo. `ANSWER_SEQ` is an
integer, the `seq` `decisions` prints. Result (`RetractResult`):

| Field | Meaning |
|---|---|
| `outcome` | `retracted`, `unchanged` (already retracted) or `rejected` |
| `rejection` | with `rejected`: `no_such_answer`, `not_a_pm_answer` (an automatic answer is never precedent) or `malformed` (blank reason, non-integer sequence) |
| `answer_seq`, `key` | the answer and its question |
| `problems` | one line per problem when `rejected` |

A PM answer also resets the answer limit: `answer_limit` counts automatic answers since
the run's last PM answer, a retracted one included. Exit 1 when `rejected`, else 0.

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
| `closed_now` | what this call closed (closures made by `handle_pause` are in that call's calls-log `detail`, not here), so each automatic closure is seen once: `{program, member, run_id, paused_at, question, closed_reason, closed_detail}` for a question, and for an answer marked `not_delivered` the same with `answer_seq` and `resume_outcome` |
| `sweep_problem` | set when the closing could not take the store's lock; nothing was closed and the rows show as before |
| `file_problems` | calls-log day files that could not be read, and entries `prune` could not remove |
| `problems` | one line per problem when `rejected` |

`status` closes the open questions of the members in scope whose run is no longer at
that pause, judged from the one `sq runs list --json --all` listing it already makes
(no further `sq` call), then prunes old scratch and logs. A run absent from the listing
whose run file still exists keeps its question open: an incomplete listing closes
nothing. `closed_reason` is `dismissed` (by `dismiss`), `run_moved_on` (the run is at a
later pause, or finished; `closed_detail` is the run's state) or `run_gone` (Squadron no
longer knows the run).

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
| `closed` | the pause's question was closed; `detail` gives the reason and says the run is still paused in Squadron | none |
| `run_file_unreadable` | Squadron's run file could not be read; `detail` says why | none |

A run with `pause` `unhandled` or `claim_stale` also has `last_call`: the newest
calls-log line for it (see above), or null if none was logged, which shows why a hook
missed.

`next` is `{operation, run_id, paused_at, directory}` or null. For `handle_pause`,
`directory` is the run's own checkout: run the command there. A waiting question
(`waiting_on_pm`) has `run_id`, `paused_at`, `question`, `slice_label`,
`waiting_reason`, `waiting_detail`, `since`, `run_state` and `next`. Every open waiting
question of a member in scope is listed. `run_state` is `at_pause` (`next` is
`answer`); `moved_on` (`detail` gives the run's state) and `not_listed` appear only for
a row a failed closing left open, since the closing otherwise closes them in the same
call. `reason` of an unplaced run is `no_directory` (a run from before `sq` 0.24.24), `directory_missing`
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
