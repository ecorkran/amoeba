---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: The amoeba command line: each subcommand's arguments, its JSON result on stdout and the exit-code table.
dateCreated: 20261110
dateUpdated: 20261110
status: complete
---

# CLI contract

`amoeba <command>` is the process boundary. It alone resolves the home (`$AMOEBA_HOME`,
see `store-contract.md`), reads the user config (`config-contract.md`) and builds the
real edges (`sq`, `cf`, `git`, the clock). Each operation prints its result as JSON on
stdout. Slice 224 extends this file for its operations.

## Exit codes

| Code | Meaning | Causes |
|---|---|---|
| 0 | The operation ran | `set_up` applied or unchanged; `handle_pause` any outcome, including `skipped`; `answer` recorded |
| 1 | The operation refused the request; the result says why | `set_up` rejected; `answer` rejected |
| 2 | Usage | bad arguments, or a `set_up` request file that cannot be read, is not UTF-8 or is not YAML |
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

Exit 1 when `rejected`, else 0 (a refused or not-delivered resume still exits 0: the
answer is recorded and is precedent).
