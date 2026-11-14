---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: The amoeba command line: each command's arguments, its text and `-j` JSON output and the exit-code table.
dateCreated: 20261110
dateUpdated: 20261114
status: complete
---

# CLI contract

`amoeba <command>` is the process boundary. It alone resolves the two homes (the config
home and the state home, see `store-contract.md`), reads the user config
(`config-contract.md`) and builds the real edges (`sq`, `cf`, `git`, the clock).

## Text and JSON

Every command prints **text** by default, written for a person, and its **result as
JSON** with `-j` (or `--json`), placed after the command name: `amoeba list -j`. The
JSON is the result document both doors give (the MCP tool returns the same document),
and it is what the sections below describe field by field.

- The first line of the text says what happened: `added`, `removed`, `changed`,
  `unchanged`, `recorded`, `dismissed`..., or `rejected: <code>: <detail>`.
- Prose (a question, an answer, a reason) is cut to 100 columns with `…` and kept on
  one line; the full text is in `-j`. A command or a path is never cut: it sits on its
  own indented line, so it can be pasted.
- No colour and no table wider than 100 columns.
- Errors are `error: <ExceptionName>: <message>` on stderr, with the exit codes below,
  in both forms.
- `handle-pause` prints one line (`answered`, `waiting_on_pm: <reason>`,
  `skipped: <reason>`, with its detail). Nothing parses the hook's output.

## Names

A command's name is its operation's name with `_` as `-`: `handle-pause`,
`mark-read` and `report-release`; the others (`add`, `rm`, `list`, `answer`, `status`, `decisions`,
`dismiss`, `retract`, `changes`) have no underscore. `rm` also answers to `remove`. MCP tool names
stay snake_case (`handle_pause`, `mark_read`), and so does the `operation` in JSON
`next` entries. There is no alias for an old command name (`set_up`, `handle_pause`,
`mark_read`): it is argparse's invalid-choice error, which lists the valid names, exit
2. `set_up` is gone: `add` and `rm` replace it on both doors.

The first command after an upgrade from a pre-228 install moves the old state out of
`~/.config/amoeba/` into the state home before it does its own work, and writes one
line to stderr (`amoeba: moved state from <old> to <new> ...`) only when something
moved. A store that cannot be moved or verified is exit 3 (`StoreRelocateError`) with
the old store untouched.

## Exit codes

| Code | Meaning | Causes |
|---|---|---|
| 0 | The operation ran | `add` or `rm` applied or unchanged; `list` and `status` listed; `handle-pause` any outcome, including `skipped`; `answer` recorded; `dismiss` dismissed or unchanged; `retract` retracted or unchanged; `decisions` listed; `mark-read` moved or unchanged; `report-release` recorded, versioned, corrected, unchanged or withdrawn; `changes` listed |
| 1 | The operation refused the request; the result says why | `add`, `rm`, `list`, `answer`, `dismiss`, `retract`, `status`, `decisions`, `mark-read`, `report-release` or `changes` rejected |
| 2 | Usage | bad arguments (a missing or non-integer `mark-read --through`, an old command name, `--all` with `list members`, `--file` with another `add` flag, mutually exclusive rules flags, an empty side of `--concept`), or an `add --file` request file that cannot be read, is not UTF-8 or is not YAML |
| 3 | Operational failure; message on stderr as `error: <ExceptionName>: <message>` | `ConfigError`, `AmoebaHomeError`, `ContextForgeError`, `SquadronError`, any `StoreError` (including `StoreRelocateError`, a legacy store that could not be moved) |

A Squadron or Context Forge failure is an exit 3, never a skip: "cannot tell" is not
"not mine". Nothing is written before it.

## `amoeba add`

```
amoeba add [--program ID] [--project NAME] [--rules PATH]... [--default-rules]
           [--no-rules] [--allow KEY]... [--no-allow] [--deny KEY]... [--no-deny]
           [--depends-on PROVIDER[:MODE]]... [--concept MEMBER:PATH] [-j]
amoeba add --file PATH [-j]
```

Registers the working directory's repo (or the project `--project` names) as a member
of a program. With no flag at all it registers the repo in a program named for its
Context Forge project, on the default rules. A repeat changes nothing and is
`unchanged`.

| Flag | Request field | Meaning |
|---|---|---|
| `--program ID` | `program` | The program (created when new). Without it: the member's own program when it is registered (a removed member's too), else a new program named for its Context Forge project. A program that already exists by that name is joined, and the text says `added member Y to existing program X` instead of `created program X` |
| `--project NAME` | `project` | A Context Forge project name or id; default the working directory's. A directory with no project and no `--project` is `not_a_project` and nothing is written |
| `--rules PATH` (repeatable) | `rules_paths: [PATH...]` | Replaces the member's rules with these entries (`rules.md`) |
| `--default-rules` | `rules_default: true` | Returns the member to the config's `default_rules_paths` |
| `--no-rules` | `rules_paths: []` | Stores no rules at all |
| `--allow KEY` (repeatable) | `authorize_allow: [KEY...]` | Replaces the member's allow list |
| `--no-allow` | `authorize_allow: []` | Stores an empty allow list |
| `--deny KEY`, `--no-deny` | `authorize_deny` | The same for the deny list |
| `--depends-on PROVIDER[:MODE]` (repeatable) | `depends_on: [{provider, consumed}]` | A provider (Context Forge name or id); `MODE` is `from_source` or `from_release`, and without it the config's `default_consumed` |
| `--concept MEMBER:PATH` | `concept: {member, path}` | The program's concept file, split at the first `:`; an empty side is a usage error |
| `--file PATH` (`-` is stdin) | `bulk` | A whole request document (below); it cannot be combined with another flag |

`--rules`, `--default-rules` and `--no-rules` are mutually exclusive, and so are
`--allow` with `--no-allow` and `--deny` with `--no-deny`. A flag not given leaves its
field out of the request, and a field left out leaves the stored value alone; giving
none of the three rules flags leaves an existing member's rules as they are and gives a
new member the default. `--allow`, `--deny` and `--rules` replace the list, they do not
add to it.

The MCP `add` tool takes the same fields (`program`, `project`, `rules_paths`,
`rules_default`, `authorize_allow`, `authorize_deny`, `depends_on`, `concept`) or `bulk`,
never both, plus `directory`. `add` builds a request for the `set_up` engine and returns
its result (`SetUpResult`): `outcome` (`applied`, `unchanged` or `rejected`), `changes`
(one line per changed row, `<added|updated|removed> <program|member|dependency|pair>
...`), `change_records` (the same changes as `{verb, subject, detail}`), `problems` (empty unless rejected), `program` (the program as stored, or null)
and `working_directory` (informational, or null for a malformed request). Exit 1 when
`rejected`.

Each problem has a `code`, a `detail` naming the field at fault, and `open_questions` (empty except for `member_has_open_questions`, where it lists each blocking question as `{run_id, paused_at}`). Codes: `malformed`,
`not_a_project`, `empty_program`, `member_of_other_program`,
`unknown_provider`, `self_dependency`, `unknown_authorize_item`,
`concept_member_not_member`, `member_has_open_questions` and `not_a_member`. Any problem
rejects the whole request and writes nothing. A new member needs no rules: it gets the
default.

## `amoeba rm`

```
amoeba rm [MEMBER]... [--pair PROVIDER:CONSUMER]... [--concept] [--program ID] [-j]
```

Also `amoeba remove`. With no `MEMBER`, no pair and no `--concept`, it removes the
working directory's project. `MEMBER` is a Context Forge name or id (an id works after
the Context Forge project is deleted). Every named member and pair end must belong to
one program, found from the store, or `--program` names it: members of different
programs are `member_of_other_program`, a member that was never in a program is
`not_a_member`. `--concept` clears the program's concept, the only way to remove the
concept's member (without it that member is `concept_member_not_member`). `rm` builds
the `remove` section of a request (below), so soft removal and its refusals are the
engine's. The MCP `rm` tool takes `members`, `pairs` (each `PROVIDER:CONSUMER`),
`concept` (true) and `program`, plus `directory`.

A member with open questions is refused (`member_has_open_questions`); the text prints
each question's key and the `amoeba answer` and `amoeba dismiss` command that clears it.
Removing an already removed member is `unchanged`. A removed member comes back with
`amoeba add` (in its old program unless `--program` names another).

## `amoeba list`

```
amoeba list [SUBJECT] [--all] [--program ID] [-j]
```

One view of what needs the PM, and what is registered. `SUBJECT` is `programs`,
`members` or `dependencies` (the singular forms work too); with none it is the default
view. The MCP `list` tool takes the same as `subject`, `all` and `program`, plus
`directory`.

**The default view** runs `status` (same code, same sweep): `list -j` is the `status`
document, nothing more, and the text is the same as `status`'s. The text has these
sections, in order, each left out when empty: **Waiting on you** (member, run, how long,
reason, the question on one line, and the `amoeba answer` and `amoeba dismiss`
commands), **Paused, not handled** (runs the hook missed, each with `amoeba handle-pause
RUN_ID` to run in the run's checkout and, for a missed hook or a dead claim, the newest
calls-log line), **Unplaced runs** (each says how it clears), **Problems**, then what
this call closed. `Nothing needs you.` when nothing waits. With `--all` the document
gains one top-level `settled` (the questions answered or closed within
`prune_after_days`: `program`, `member_id`, `member_name`, `run_id`, `paused_at`,
`question`, `ended`, `settled_at`), and the text adds **Other runs** under their members
and **Settled**. `--program ID` narrows the view.

**`programs`**: `{programs: [{program, concept: {member, path} | null, members:
[project_id]}]}`. A program with no active members and no concept is left out unless
`--all` is given; the row cannot be deleted (it is the target of its removed members'
records), and `add --program` refills it.

**`members`**: `{members: [{project_id, name, path, in_context_forge, program,
rules_from, rules_paths, authorize_allow, authorize_deny, depends_on: [{provider,
consumed}]}]}`. `path` is Context Forge's `projectPath`; the text says `(no path in
Context Forge)` when it has none, and a member whose project is gone shows its id and
`(not in Context Forge)`. `rules_paths` is the stored entries for `named` rules and the
config's current `default_rules_paths` for `config_default`. A removed member is not
listed.

**`dependencies`**: `{dependencies: [{provider_id, provider_name, consumer_id,
consumer_name, consumed}]}`.

`--all` with `members` or `dependencies` is a usage error, exit 2 (as an operation it
is `rejected`, `malformed`). The registered views read Context Forge once; `cf` failing
is exit 3 with no partial view. An unknown `--program` is `rejected` with
`unknown_program`.

## The request document

`add --file` (and the `bulk` field of the MCP `add` tool) takes a YAML request:

```yaml
program: demo
concept: {member: some-member, path: docs/concept.md}   # omitted leaves it
members:
  - project: some-member          # Context Forge name or id; omitted: the working directory's
    rules_paths: [CLAUDE.md]      # omitted: keep (a new member gets the default); [] is no rules
    rules_default: false          # true returns the member to the default rules
    authorize_allow: []
    authorize_deny: []
    depends_on:
      - {provider: some-provider, consumed: from_source}
remove:
  members: [other-member]         # Context Forge names or ids
  pairs:
    - {provider: some-provider, consumer: some-consumer}
```

`rules_paths` and `rules_default` together are `malformed`. `remove` is what `rm` builds:

- A removed member is **soft-removed**: its row stays (its questions and answers are
  the record), its pairs are deleted, and everywhere else it is treated as not a
  member (`NotInProgram`, absent from `status` and the program's members). Naming it
  again under `members` re-registers it as a new member (the config's default rules
  unless `rules_paths` is given), in this or another program. A pair is deleted.
- A reference Context Forge does not know is read as a stored member id, so a member
  whose Context Forge project was deleted can still be removed by its id.
- Removing an already removed member or an absent pair is no change, so a repeat is
  `unchanged`. `changes` gains `removed member <id>` and `removed pair <provider> ->
  <consumer>`.
- Removing the program's concept member while the concept stays is rejected
  (`concept_member_not_member`). Clear the concept in the same request with
  `concept: null` (the one way to remove a concept), or move it.
- `member_has_open_questions` (a `claimed` or `waiting_on_pm` question, or an
  `answered` one whose answer was not yet handed back; the detail lists the keys:
  `dismiss` or `answer` them first) and `not_a_member` (the reference is no member of
  this program, past or present). `malformed` also covers a member under both
  `members` and `remove.members`, a pair under both `depends_on` and `remove.pairs`,
  and a removed member named as the end of a pair (in `remove.pairs` or as a
  `depends_on` provider). Any problem rejects the whole request.

## `amoeba handle-pause RUN_ID`

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

Every `handle-pause` call appends one JSON line to
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
| `rejection` | with `rejected`: `no_such_question` (run `amoeba handle-pause RUN_ID` from the run's checkout first) or `malformed` (blank text, unknown field, bad type) |
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
| `closed_now` | what this call closed (closures made by `handle-pause` are in that call's calls-log `detail`, not here), so each automatic closure is seen once: `{program, member, run_id, paused_at, question, closed_reason, closed_detail}` for a question, and for an answer marked `not_delivered` the same with `answer_seq` and `resume_outcome` |
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
| `records` | each: `seq`, `recorded_at`, `program`, `member` (`{id, name}`), `run_id`, `paused_at`, `slice_label`, `question`, `answered_by` (`answerer` or `pm`), `via` (`cli` or `mcp`, the door that carried a PM answer; null for an answer from before schema version 4 and for automatic answers), `answer`, `prior_answer_seq`, `based_on`, `resume` |
| `read_through` | the last listed `seq`, only when the listing started at the marker, was not narrowed and is not empty; else null. Give it to `mark-read` |
| `marker` | the marker's value when read |
| `problems` | one line per problem when `rejected` |

`prior_answer_seq` is the newest earlier answer to the same question (a PM answer after
an automatic one is an override). `based_on` is, for `answerer`, the cited passages
(`id`, `kind`, `source`, `date`; `kind` is `pm_answer` for a PM precedent and null for
the others, which the store records no kind for) with `check_verdict` and
`check_reason`; for `pm`, the question's `waiting_reason` and `waiting_detail`, or null
if the PM answered before the question waited. `resume` is `outcome`, `detail`, `at`.

## `amoeba mark-read --through SEQ`

Moves the PM's marker forward to `SEQ`, the `read_through` of a `decisions` call. There
is no "mark all": a record written after that call keeps a higher `seq` and stays
unread. Result (`MarkReadResult`): `outcome` (`moved`, `unchanged` or `rejected`),
`rejection` (`beyond_last_record` when `SEQ` is above the last answer, `malformed` for
a negative or non-integer `SEQ`), `previous`, `current`, `problems`. The marker never
moves backward, so an equal or lower `SEQ` is `unchanged`. Exit 1 when `rejected`.

## `amoeba report-release`

```
amoeba report-release --commit HASH [--version TAG] --changed TEXT --touched ITEM [--touched ITEM ...] [--correct]
amoeba report-release --commit HASH --withdraw
```

A provider repo tells the repos that depend on it what a merge or release changed. It
runs from the member's own checkout. `--commit` is the full commit hash (40 or 64 hex
characters; `git rev-parse` gives it; Amoeba checks its shape only and never runs `git`, so
it does not know whether the commit exists), `--version` the release tag (printable, no whitespace), `--changed` what
changed for someone using the repo, and `--touched` one thing changed, repeated for each
(duplicates are dropped, order kept). `--correct` and `--withdraw` are mutually
exclusive (both is exit 2). No flag is required by argparse: an absent flag is left out
of the request, and the operation rejects a missing field with the same detail on both
doors.

Three modes, from the flags: no mode flag is `report`, `--correct` is `correct`, and
`--withdraw` is `withdraw`. `--commit` is needed in every mode. `--changed` and
`--touched` are needed in `report` and `correct`; `--version` is optional there. None of
`--version`, `--changed` and `--touched` is allowed in `withdraw`. A report is one per
member and commit.

| Mode | Case | `outcome` |
|---|---|---|
| `report` | no report for the commit | `recorded` |
| `report` | a `--version` that is new, or one on a report with none: the version is set and the text replaced | `versioned` |
| `report` | anything else, whatever the wording: the stored report is kept | `unchanged` |
| `correct` | a report exists: the text is replaced (and the version, if given) and the report counts as new | `corrected` |
| `withdraw` | a report exists: it is deleted | `withdrawn` |
| `correct` or `withdraw` | no report for the commit | `rejected` with `not_reported` |

Result (`ReportReleaseResult`), the same document over MCP:

```json
{"outcome": "recorded",
 "member": "<cf project id>",
 "report": {"seq": 0, "commit": "<full hash>", "version": "<tag>", "changed": "<text>",
            "touched": ["<item>"], "reported_at": "<UTC ISO-8601>",
            "versioned_at": "<UTC ISO-8601>"},
 "problems": []}
```

`member` is null when the directory is not a member. `report` is the stored report after
the call; it is null after `withdrawn` and on a rejection. `version` and `versioned_at`
are null until the report has a version. `problems` is `{code, detail}` per problem:

- `malformed`: the request is wrong (the detail names the field, and for `--commit` says
  `git rev-parse` gives a full hash); nothing is written.
- `not_a_member`: the caller's directory is in no Context Forge project, or its project
  is in no program; the detail says which. Nothing is written.
- `not_reported`: `--correct` or `--withdraw` found no report by this member for that
  commit. Nothing is written.

A version on an already reported commit does not move `reported_at`, so a consumer that
takes `from_source` does not see the commit twice. A correction moves `reported_at` (and
`versioned_at`, when the report has a version) to now, so consumers whose `--since`
predates it see it again. A withdrawn commit can be reported again.

Text: the first line is `reported` (for `recorded` and `versioned`), `unchanged`,
`corrected`, `withdrawn`, or `rejected: <code>` with a line per problem. Exit 0 for any
outcome but `rejected`, 1 for `rejected`, 2 for usage, 3 for an operational error
(`ContextForgeError` when `cf` fails, never a rejection; nothing is written).

## `amoeba changes --since ISO-8601`

What the providers of this repo reported since a time. It runs from the member's own
checkout and writes nothing: no read marker is kept, so the caller chooses its starting
point (the rule blocks in `docs/program-rules.md` say how). `--since` is ISO-8601 with a
UTC offset and is required by the operation (an absent or offset-less value is
`rejected` with `malformed`).

For each pair where this member is the consumer, the provider's reports that the pair's
`consumed` shows: `from_source` sees a report from when it was made or last corrected
(`reported_at` at or after `--since`), `from_release` sees only a report with a version,
from when it was versioned or last corrected (`versioned_at` at or after `--since`).
Every pair is listed, including one with nothing visible, so "checked, nothing new"
differs from "not a dependency". A provider's own providers are never listed, and a
provider that `rm` removed is gone with its pair: its reports are not listed, though
they stay in the store. This command's name is also the name of a field: `changes` in
an `add` or `rm` result lists the rows that call changed, which is unrelated. Result
(`ChangesResult`), the same document over MCP:

```json
{"outcome": "listed",
 "member": {"id": "<cf project id>", "name": "<cf name>"},
 "since": "<UTC ISO-8601>",
 "pairs": [{"provider": {"id": "<cf project id>", "name": "<cf name>"},
            "consumed": "from_release",
            "releases": [{"seq": 0, "commit": "<full hash>", "version": "<tag>",
                          "changed": "<text>", "touched": ["<item>"],
                          "reported_at": "<UTC ISO-8601>",
                          "versioned_at": "<UTC ISO-8601>"}]}],
 "problems": [],
 "warnings": []}
```

`outcome` is `listed` or `rejected`. `since` is the normalized UTC text. A member with no
providers is `listed` with empty `pairs`. Each release is oldest first and has the same
shape as `report` above. `problems` are `malformed` (the request) or `not_a_member` (as
for `report-release`). `warnings` hold `not_in_context_forge` when Context Forge's
project list does not name the caller or a provider: the id is kept, `name` is null and
the outcome stays `listed`. A `cf` failure is exit 3, never a warning or an empty list.

Text: one entry per report (provider name or id, commit, version, the changed text cut
to the line width, the touched items), warnings as `warning:` lines, and
`No changes since <time>.` when no pair has a report. A rejection prints
`rejected: <code>` and a line per problem. Exit codes are as for `report-release`.

## Release rejection codes

`not_a_member` and `not_reported` are two members of the rejection vocabulary, next to
`malformed`; `report-release` and `changes` use the codes that apply to them, as above.
