---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: The amoeba command line: each command's arguments, its text and `-j` JSON output and the exit-code table.
dateCreated: 20261110
dateUpdated: 20261122
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

`list` and `status` color their section headings (cyan; yellow for a section that
needs you; green for `Nothing needs you.`) when stdout is a terminal. A pipe, a file
and `-j` get plain text, and `NO_COLOR` or `TERM=dumb` turns color off.

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
`dismiss`, `retract`, `changes`, `standing`, `withdraw`) have no underscore. `rm` also answers to `remove`. MCP tool names
stay snake_case (`handle_pause`, `mark_read`), and so does the `operation` in JSON
`next` entries. There is no alias for an old command name (`set_up`, `handle_pause`,
`mark_read`): it is argparse's invalid-choice error, which lists the valid names, exit
2. `set_up` is gone: `add` and `rm` replace it on both doors.

`amoeba --version` (or `-v`) prints the installed `amoeba-ai` version, read from the
package metadata, and exits 0 before any config or state is touched. `amoeba-mcp` has
no flags; it is started by an MCP client, not by hand.

The first command after an upgrade from a pre-228 install moves the old state out of
`~/.config/amoeba/` into the state home before it does its own work, and writes one
line to stderr (`amoeba: moved state from <old> to <new> ...`) only when something
moved. A store that cannot be moved or verified is exit 3 (`StoreRelocateError`) with
the old store untouched.

## Exit codes

| Code | Meaning | Causes |
|---|---|---|
| 0 | The operation ran | `add` or `rm` applied or unchanged; `list` and `status` listed; `handle-pause` any outcome, including `skipped`; `answer` recorded; `dismiss` dismissed or unchanged; `retract` retracted or unchanged; `decisions` listed; `mark-read` moved or unchanged; `report-release` recorded, versioned, corrected, unchanged or withdrawn; `changes` listed; `send` sent or unchanged; `inbox` listed; `reply` applied; `cancel` cancelled |
| 1 | The operation refused the request; the result says why | `add`, `rm`, `list`, `answer`, `dismiss`, `retract`, `status`, `decisions`, `mark-read`, `report-release`, `changes`, `send`, `inbox`, `reply` or `cancel` rejected |
| 2 | Usage | bad arguments (a missing or non-integer `mark-read --through`, an old command name, `--all` with `list members`, `--file` with another `add` flag, mutually exclusive rules flags, an empty side of `--concept`), or an `add --file` request file that cannot be read, is not UTF-8 or is not YAML, a `send --body-file` that cannot be read or is not UTF-8, or `send --body` with `--body-file` |
| 3 | Operational failure; message on stderr as `error: <ExceptionName>: <message>` | `ConfigError`, `AmoebaHomeError`, `ContextForgeError`, `SquadronError`, any `StoreError` (including `StoreRelocateError`, a legacy store that could not be moved, `LocalStoreClosedError`, `HubHomeError`, `NoActingMachineError` and `HubStoreMissingError`); and, from slice 260, `JoinError`, `ClientFileError`, `HubUnreachableError`, `HubCertificateError`, `HubRefusedError`, `NotServedError`, `HubConfigError`, `HubStartError` and `BackupError` (see "The hub and joined machines") |

A Squadron or Context Forge failure is an exit 3, never a skip: "cannot tell" is not
"not mine". Nothing is written before it.

## `amoeba init`

```
amoeba init
```

Takes a machine from nothing to a working Amoeba. It is the first command on a new
machine, and it is safe to repeat.

- **Config.** With no `config.yaml` in the config home, it writes the starter config:
  every key, with the values under Example in `docs/config-contract.md`. With a config
  already there, it adds each required key the file lacks, from the same values, and
  changes nothing else. It never overwrites a value. A file that is empty or only
  comments gets every key. A config that is a link is written through the link.
- **Store.** It creates the store in the state home, or brings an existing one up to
  date.

It prints what it did to the config (`wrote`, with a note that the two model aliases
are placeholders; `added <keys> to`; or `is already complete`), one line for the store
(`created` or `is already there`), and the next step.
Exit 0. A config with a fault that adding keys does not fix (an unknown key, a bad
value) is exit 3, naming the file and the key, and the file is left as it was.

CLI-only, like `answer-first`: it has no MCP tool and no `-j`. Every other command that
finds no config fails with exit 3 and says to run it.

## `amoeba add`

```
amoeba add [--program ID] [--project NAME] [--rules PATH]... [--default-rules]
           [--no-rules] [--allow KEY]... [--no-allow] [--deny KEY]... [--no-deny]
           [--depends-on PROVIDER[:MODE]]... [--concept MEMBER:PATH]
           [--wake-command COMMAND | --no-wake-command] [-j]
amoeba add --file PATH [-j]
```

Registers the working directory's repo (or the project `--project` names) as a member
of a program. With no flag at all it registers the repo in a program named for its
Context Forge project, on the default rules. A repeat changes nothing and is
`unchanged`.

| Flag | Request field | Meaning |
|---|---|---|
| `--program ID` | `program` | The program (created when new). Without it: the member's own program when it is registered (a removed member's too), else a new program named for its Context Forge project. A program that already exists by that name is joined, and the text says `added member Y to existing program X` instead of `created program X` |
| `--project NAME` | `project` | An existing member's name or id (slice 261); default this directory's checkout, which `add` finds or creates the member for ("Which member", below). It never creates a member and runs no `cf`, so it works from any directory. A directory with no project and no `--project` is `not_a_project` and nothing is written |
| `--name NAME` | `name` | Sets or changes the member's name (default: the Context Forge name). A name is `[A-Za-z0-9][A-Za-z0-9._-]*`, at most 64 characters, compared without case; one that another active member has, or that is another member's id, is `name_taken` |
| `--attach-to NAME` | `attach_to` | Attach this checkout to that member when it has no checkout on any machine (`member_has_checkouts` otherwise): the way to give a checkout back to a member with no `origin` to match on. `malformed` when this checkout is already on record (`amoeba rm --checkout` first) |
| `--new-member` | `new_member` | Make a new member of this checkout and skip the `origin` steps; the name must be free. The undo for a checkout that attached to the wrong member |
| `--rules PATH` (repeatable) | `rules_paths: [PATH...]` | Replaces the member's rules with these entries (`rules.md`) |
| `--default-rules` | `rules_default: true` | Returns the member to the config's `default_rules_paths` |
| `--no-rules` | `rules_paths: []` | Stores no rules at all |
| `--allow KEY` (repeatable) | `authorize_allow: [KEY...]` | Replaces the member's allow list |
| `--no-allow` | `authorize_allow: []` | Stores an empty allow list |
| `--deny KEY`, `--no-deny` | `authorize_deny` | The same for the deny list |
| `--depends-on PROVIDER[:MODE]` (repeatable) | `depends_on: [{provider, consumed}]` | A provider (Context Forge name or id); `MODE` is `from_source` or `from_release`, and without it the config's `default_consumed` |
| `--concept MEMBER:PATH` | `concept: {member, path}` | The program's concept file, split at the first `:`; an empty side is a usage error |
| `--wake-command COMMAND` | `wake_command: COMMAND` | The command Amoeba starts, unattended, when a request arrives for this member and no agent is live in it ("The wake command", below). It is set on the checkout the command runs in, so it is given from that repo and never with `--project` or for another bulk entry (`malformed`, "a wake command is set from its own checkout"). The text must split into words (`shlex` rules) with at least one, and hold no NUL or line break; the executable is not looked up. Omitted leaves the member's command. A CLI-only setting: the MCP `add` tool does not take it |
| `--no-wake-command` | `wake_command: null` | Clears this checkout's wake command, so nothing wakes it from here |
| `--file PATH` (`-` is stdin) | `bulk` | A whole request document (below); it cannot be combined with another flag |

`--rules`, `--default-rules` and `--no-rules` are mutually exclusive, and so are
`--allow` with `--no-allow`, `--deny` with `--no-deny` and `--wake-command` with
`--no-wake-command`. A flag not given leaves its
field out of the request, and a field left out leaves the stored value alone; giving
none of the three rules flags leaves an existing member's rules as they are and gives a
new member the default. `--allow`, `--deny` and `--rules` replace the list, they do not
add to it.

The MCP `add` tool takes the same fields (`program`, `project`, `rules_paths`,
`rules_default`, `authorize_allow`, `authorize_deny`, `depends_on`, `concept`) or `bulk`,
never both, plus `directory`; it does not take `wake_command`, in the single fields or
in a bulk member, and a call that passes it is `rejected` as an unknown field. `add` builds a request for the `set_up` engine and returns
its result (`SetUpResult`): `outcome` (`applied`, `unchanged` or `rejected`), `changes`
(one line per changed row, `<added|updated|removed> <program|member|dependency|pair|checkout>
...`), `change_records` (the same changes as `{verb, subject, detail}`), `problems` (empty unless rejected), `program` (the program as stored, or null)
and `working_directory` (informational, or null for a malformed request). Exit 1 when
`rejected`.

Each problem has a `code`, a `detail` naming the field at fault, and `open_questions` (empty except for `member_has_open_questions`, where it lists each blocking question as `{run_id, paused_at}`). Codes: `malformed`,
`not_a_project`, `empty_program`, `member_of_other_program`,
`unknown_provider`, `self_dependency`, `unknown_authorize_item`,
`concept_member_not_member`, `member_has_open_questions`, `not_a_member`, and from slice
261 `name_taken`, `origin_taken`, `no_origin`, `member_has_checkouts` and `not_a_checkout`.
Those five carry the way on in their `detail` (the remotes, the flags to give), and the text
prints the whole detail, wrapped, never cut; on a joined machine the text of `add` and `rm`
says `rules: default` alone, since the config that applies is the hub's.
Any problem rejects the whole request and writes nothing. A new member needs no rules: it gets the
default.

**Which member (slice 261).** With no `--project`, `add` reads this directory's
checkout (the Context Forge project id and path, and the repo's `origin` remote reduced
to `host[:port]/path`, with no scheme, user or password) and chooses the member in this
order: (1) this checkout is on record on this machine: its member, whatever path
arrived; the member's `origin` is recorded when it has none, kept when the checkout has
none, and replaced (both values in the change record) when they differ, `origin_taken`
when another active member has the new one; (2) an active member has this `origin`: the
checkout is added to it; (3) a removed member has this `origin`: the most recent one is
registered again, `name_taken` if its name is taken now and no `--name` is given; (4) a
free name (`--name`, else the Context Forge name) makes a new member with id
`uuid4().hex`; (5) a name an active member has is `name_taken` when this checkout has an
`origin` (naming both remotes and the way on) and `no_origin` when it has none (a repo
with no `origin` remote can have one checkout, because nothing shows a second is the
same repo). `change_records` gain the subject `checkout` (`added checkout PATH of
NAME`) and `updated member` lines for a rename or an `origin` change.

## `amoeba rm`

```
amoeba rm [MEMBER]... [--pair PROVIDER:CONSUMER]... [--concept] [--program ID] [-j]
amoeba rm --checkout PATH [-j]
```

Also `amoeba remove`. With no `MEMBER`, no pair and no `--concept`, it removes the
caller's member: the one whose checkout is the working directory's Context Forge
project on this machine (the only case that reads the working directory; `rm <name>`
runs no `cf` and works from any directory and machine, and `working_directory` is null
in its result). `MEMBER` is a member's name (any case) or id. Every named member and
pair end must belong to one program, found from the store, or `--program` names it:
members of different programs are `member_of_other_program`, a member that was never in
a program is `not_a_member`. A removed member is found by its id only, so `rm <id>`
twice is `unchanged` and `rm <name>` twice is `not_a_member` (a removed member's name is
free for another member). `--concept` clears the program's concept, the only way to
remove the concept's member (without it that member is `concept_member_not_member`).
`rm` builds the `remove` section of a request (below), so soft removal and its refusals
are the engine's. Removing a member also deletes its checkouts on every machine, and
their wake commands with them. The MCP `rm` tool takes `members`, `pairs` (each
`PROVIDER:CONSUMER`), `concept` (true), `program` and `checkout`, plus `directory`.

`--checkout PATH` removes one checkout of this machine and leaves the member, the way to
clear a deleted clone (slice 261). It is found by its stored path as `list members`
shows it, compared as text with trailing slashes dropped from both sides and not
resolved against the disk, because the directory may be gone; a path that is not
absolute is `malformed`. If two checkouts here hold that path, both go. A path with no
checkout on this machine is `not_a_checkout`, and the detail lists this machine's stored
paths. It cannot be combined with members, `--pair`, `--concept` or `--program` (`malformed`). The
result's change record is `removed checkout PATH`. Removing the last checkout leaves a
member with none, which `list members` marks.

A member with open questions is refused (`member_has_open_questions`); the text prints
each question's key and the `amoeba answer` and `amoeba dismiss` command that clears it.
Removing an already removed member by id is `unchanged`. A removed member comes back
with `amoeba add` in a checkout of its repo that has the same `origin` remote (step 3
of "Which member"), in its old program unless `--program` names another.

## `amoeba list`

```
amoeba list [SUBJECT] [--all] [--program ID] [-j]
```

One view of what needs the PM, and what is registered. `SUBJECT` is `programs`,
`members` or `dependencies` (the singular forms work too), or `standing`; with none it
is the default view. The MCP `list` tool takes the same as `subject`, `all` and `program`, plus
`directory`.

**The default view** runs `status` (same code, same sweep): `list -j` is the `status`
document, nothing more, and the text is the same as `status`'s. The text has these
sections, in order, each left out when empty: **Waiting on you** (member, run, how long,
reason, the question on one line, and the `amoeba answer` and `amoeba dismiss`
commands), **Paused, not handled** (runs the hook missed, each with `amoeba handle-pause
RUN_ID` to run in the run's checkout and, for a missed hook or a dead claim, the newest
calls-log line), **Unplaced runs** (each says how it clears; runs Amoeba has no record of are one count, and `--all` lists each), **Problems**, then what
this call closed. `Nothing needs you.` when nothing waits. With `--all` the document
gains one top-level `settled` (the questions answered or closed within
`prune_after_days`: `program`, `member_id`, `member_name`, `run_id`, `paused_at`,
`question`, `ended`, `settled_at`), and the text adds **Other runs** under their members
and **Settled**. `--program ID` narrows the view.

**`programs`**: `{programs: [{program, concept: {member, path} | null, members:
[project_id], names: {project_id: name}}]}`; `names` covers the members and the
concept's member, from the store. A program with no active members and no concept is
left out unless `--all` is given; the row cannot be deleted (it is the target of its removed members'
records), and `add --program` refills it.

**`members`**: `{members: [{project_id, name, path, in_context_forge, program,
rules_from, rules_paths, authorize_allow, authorize_deny, wake_command, depends_on:
[{provider, consumed}], origin, checkouts: [{machine, path, cf_project_id,
wake_command}]}]}` (slice 261). `project_id` is the member's own id (opaque) and `name`
its name. `path` is the path of the member's first-added checkout on the calling
machine, null when it has none there, and `in_context_forge` says whether it has one;
`checkouts` lists every checkout on every machine, the one added first first, with the
machine's name and the Context Forge project id that machine knows it by. `origin` is
the reduced remote (`host[:port]/path`) or null. `rules_paths` is the stored entries
for `named` rules and the config's current `default_rules_paths` for `config_default`.
`wake_command` is the command a wake claimed on the calling machine would run, in plain
text, or null; the text shows it on a `wake command:` line, with the command on the next
line, for a member that has one. The text shows, per member: the name, then `id:`,
`origin:`, `rules:`, any `allow:` and `deny:`, `depends on:` and `checkouts:` (each with
its machine, Context Forge id, path and wake command), and marks a member with no
checkout `(no checkout)` and one named by its id `(named by its id)` with the
`amoeba add --project ID --name NAME` command that renames it. A removed member is not
listed.

**`dependencies`**: `{dependencies: [{provider_id, provider_name, consumer_id,
consumer_name, consumed}]}`.

**`standing`**: `{standing: [{standing_id, reach, program, member, member_name,
given_at, text, withdrawn_at, withdraw_reason}]}`, newest first (slice 230). Active
standing answers only; `--all` adds withdrawn ones, whose `withdrawn_at` and
`withdraw_reason` are set (null on an active one). `program` is set for reach
`program`; `member` (the member's id) and `member_name` (its name) for reach `member`. The text shows one block per entry:
the id, the reach (`everything`, `program <id>` or `member <name>`) and the date, then
the text, wrapped to 100 columns and never cut, and for a withdrawn one its date and reason; `No standing
answers.` when there are none. `--program` does not apply (a reach `all` entry reaches every program)
and is `rejected`, `malformed`. It is not part of the default view.

`--all` with `members` or `dependencies` is a usage error, exit 2 (as an operation it
is `rejected`, `malformed`). The registered views read the store and run no `cf`. An unknown `--program` is `rejected` with
`unknown_program`.

## The request document

`add --file` (and the `bulk` field of the MCP `add` tool) takes a YAML request:

```yaml
program: demo
concept: {member: some-member, path: docs/concept.md}   # omitted leaves it
members:
  - project: some-member          # an existing member's name or id; omitted: the working directory's checkout (at most one entry)
    name: some-name               # sets or changes the member's name
    rules_paths: [CLAUDE.md]      # omitted: keep (a new member gets the default); [] is no rules
    rules_default: false          # true returns the member to the default rules
    authorize_allow: []
    authorize_deny: []
    wake_command: null            # omitted: keep; a command sets it, null clears it (CLI only)
    depends_on:
      - {provider: some-provider, consumed: from_source}
remove:
  members: [other-member]         # members' names or ids
  pairs:
    - {provider: some-provider, consumer: some-consumer}
```

`rules_paths` and `rules_default` together are `malformed`. `remove` is what `rm` builds:

- A removed member is **soft-removed**: its row stays (its questions and answers are
  the record), its pairs are deleted, and everywhere else it is treated as not a
  member (`NotInProgram`, absent from `status` and the program's members). It comes
  back through `add` in a checkout of its repo with the same `origin` (slice 261), not
  by naming it in a request: a reference to a removed member is `not_a_member`. A pair
  is deleted.
- A reference nobody matches is `not_a_member`; a removed member can still be removed
  again by its id (`unchanged`).
- Removing an already removed member or an absent pair is no change, so a repeat is
  `unchanged`. `changes` gains `removed member <name>` and `removed pair <provider> ->
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

## `amoeba answer-first install|uninstall`

Adds, or removes, the answer-first hook under `PreToolUse` and `Stop` in Claude Code's
user settings (`~/.claude/settings.json`, or `$CLAUDE_CONFIG_DIR/settings.json`), always
both together, leaving every other hook in place. It is CLI-only (no MCP tool, no `-j`),
safe to repeat, and touches no Amoeba state. Exit 0 with a line saying what it wrote;
exit 1 with `error: AnswerFirstInstallError: ...` when the settings file is not a JSON
object it can edit, in which case the file is left as it was. See `docs/answer-first.md`.

## `amoeba wake-run WAKE_ID`

Internal: Amoeba starts it, detached, when a request wakes a member (see "The wake
command"); it is not meant for people. It reads the wake's row (a row that already has a command, or has ended, is refused), runs the row's command
in the member's checkout with only the `WAKE_ENV_NAMES` variables, stops the command's
process group at the row's `deadline_at`, and records how the wake ended. It loads no
config and prints no result: its stdout and stderr are the wake's log files. It is a
CLI command only: no MCP tool, and it takes no `-j`. Exit codes: 0 when the command ran
and was recorded (its own exit code is data in the row, not the wrapper's), 1 when the
command could not be started (recorded `start_failed`), 3 for an operational failure
(a missing or already ended row, a store that cannot be read or written, or the
wrapper's own unexpected error, recorded `wrapper_failed`) with one `error:` line on
stderr.

## `amoeba resume-run ANSWER_SEQ CLAIM_ID`

Internal (slice 262): the after-step starts it, detached, for a resume that another call's
`claim_work` handed out, so that call never waits on a run. It is not meant for people. It
reads the claim's payload (nothing is started when `CLAIM_ID` is no longer the answer's:
the claim ran out and was taken again, or an outcome cleared it), reads the answer's
attempt file (`logs/resume/<run id>/<answer seq>.attempt`) and resumes the run with
`sq run --resume`, or records the outcome an earlier attempt judged, then records the
outcome. It runs no after-step of its own. Its stdout and stderr are
`<state home>/logs/resume-run/<answer seq>-<UTC stamp>.{stdout,stderr}.log`; the logs of
the `sq run --resume` it starts stay under `logs/resume/<run id>/`. A CLI command only:
no MCP tool, and it takes no `-j`. Exit codes: 0 when the outcome was `resumed` or
`not_delivered`, or the claim was no longer the answer's; 1 when it was `refused`; 3 for
an operational failure (the first poll could not be read, `sq` or the store could not be
used) with one `error:` line on stderr.

## The wake command

A checkout can carry a **wake command** (slice 244, moved from the member by slice 261):
a command Amoeba starts, unattended, when a request is sent to that checkout's member
and nobody is working in its repo. The PM sets it with `amoeba add --wake-command`, from
that checkout (never with `--project`: a command belongs to the copy of the repo it runs
in), and clears it with `--no-wake-command`; `list members`, `list -j` and `status` show it in plain text, so it
must carry no secret. A pipe, a redirect or an environment assignment needs a script,
because the command runs without a shell. An example, a script that carries its own cap:

```
amoeba add --wake-command "python3 /home/pm/bin/wake_agent.py --max-seconds 600"
```

**When a wake starts.** `send` starts one after a request is stored, when the request
is `open` (outcome `sent`, or `unchanged` with the stored request still `open`) and the
recipient has a wake command, has no push-confirmed live session (`sessions`, above),
has no wake running, and has fewer than `max_wakes_per_day` wakes started in the last
24 hours (failed starts count). A note never wakes anyone, nor does a request already
`accepted`. The wake runs from the member's first-added checkout on this machine that
has a command (a member with none here is not woken from here). Amoeba starts
`amoeba wake-run` (above) detached in that checkout's directory, and `send` returns
without waiting. The
wake step never changes a request and never makes `send` fail: a store error in it is
`wake_problem` in the result, and the request stays `open`. If the store also cannot
record a start failure, the row stays unended: `list` shows it as `running` (with no
pid) until its deadline and then as `overdue`, and it leaves by retention; `wake_problem`
is the only sign that nothing started.

**What the command must do.** It runs in the checkout with no arguments from Amoeba and
no stdin. Nothing about the request reaches it (no argument, no variable, no input): it
learns what to do from its own rules, through `inbox`. It must check `inbox` at its
start, handle each request by the repo's own rules (accept before working, decline with
a reason when the rules do not settle it, reply `done` with the result), check `inbox`
again before it ends, and exit.

**It must carry its own cost or time cap.** Amoeba stops the command at
`wake_timeout_seconds`, but if its wrapper is killed (SIGKILL, a reboot) nothing stops
it, and the command's own cap is the only bound. Amoeba cannot check that a command has
one: that is the PM's duty when choosing a command.

**Its environment.** The command runs with only these variables, copied from the wrapper
when set (`WAKE_ENV_NAMES`): `PATH`, `HOME`, `USER`, `LOGNAME`, `SHELL`, `LANG`,
`LC_ALL`, `TMPDIR`, `AMOEBA_HOME` and `CONTEXT_FORGE_DATA_DIR`, so its `amoeba`
calls reach the same store and resolve the same Context Forge projects. The sender's other variables, keys and tokens never cross repos, so a script
loads its own secrets (from the repo's `.env` or the user's profile).

**Its output and its end.** Its stdout and stderr go to the wake's log files,
`<state home>/logs/wake/<wake id>.stdout.log` and `.stderr.log` (the row's `log_stem` is
the path without the suffix; `prune` removes them by age). The wake ends one of four
ways, recorded in its `wakes` row: `exited` (with the command's exit code, which is
data), `timed_out` (the command and its whole process group were stopped at
`wake_timeout_seconds`), `start_failed` (the command could not start: not found, not
executable, no checkout, no path from Context Forge, a missing `amoeba` script) or
`wrapper_failed` (the wrapper's own error after the start; the command's group was
stopped). A `detail` is never the command's text.

**What a wake does not do.** Amoeba wakes at `send` and never again, so these cases end
by their own exits, none of which needs a file edited:

- A request that arrives after the woken agent's last `inbox` read, or while the limit
  is reached or a live session exists, waits for the next agent, or for the sender's
  same-id `send` retry once the cause is gone, or until its TTL, when it expires and the
  sender is told. An idle push-confirmed session gets the request by push.
- An agent that accepts and then times out, exits or dies leaves the request
  `accepted`, which has no timeout. It ends by `done` or `decline` from the next agent
  in that repo, or `cancel` from any session naming the id.
- A start failure or a held store leaves the request `open`, and the sender's same-id
  retry runs the wake step again once the cause is fixed.

**What `list` shows** (the **Waking** section, per member with a command): the command;
`running since <age>, stops <time>`; when no end was recorded by the deadline,
`overdue since <time>: no end was recorded, so its wrapper is probably gone; the
command's own cap ends it, or check and stop pid <pid>, log <path>` (Amoeba never signals that pid; the row stops counting as running at its
deadline, so the member can be woken again, and the row is deleted by the sweep after
`prune_after_days`); `waking stopped: <used> of <limit> wakes used in the last 24 h`
(the limit frees by the clock alone: the next `send` after the oldest counted wake is 24
hours old wakes again, or the PM raises `max_wakes_per_day`); and `last wake <outcome>
<age> ago: <detail>, log <path>` for the newest wake that went wrong.

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
| `outcome` | `skipped`, `waiting_on_pm`, `superseded`, `resumed`, `refused`, `not_delivered` or `held` |
| `skip_reason` | with `skipped`: `not_paused`, `not_agent_question`, `no_question_text`, `answering_run`, `not_a_project`, `not_in_program`, `prompt_only`, `other_member`, `other_machine`, `already_claimed`, `resume_in_progress`, `waiting_on_pm`, `settled`, `closed` or `wrong_checkout` |
| `waiting_reason` | with `waiting_on_pm`: the `DeclineReason` (see `store-contract.md`). For a held question (slice 242): `request_declined`, `request_cancelled` or `request_expired` when its request ended that way, and `request_unknown` when its request was pruned or its marker names no request this project sent |
| `detail` | why it was skipped (some reasons), declined, refused or not delivered, then any sweep or prune notes |
| `key` | the question: `run_id` and `paused_at` exactly as `sq runs wait --json` prints it |
| `checkout` | the checkout the question was claimed in |
| `answering_run_id` | the answering run, when one was involved |
| `answer_seq` | the answer that was handed to the run, with `resumed`, `refused` or `not_delivered` |
| `request_id` | the request a held question waits on or came from (slice 242); null for any other question |

`skip_reason` `closed`: the pause's question was closed (dismissed, or its run moved
on or is gone) and is not handled again; `answer` reopens it. `other_machine` (slice
262): the question's row is on another machine, which handles it; `detail` names that
machine. `resume_in_progress`: another attempt holds the answer's resume claim, so
nothing is started; the claim runs out and the answer is handed out again. `wrong_checkout`: the
call was not from the checkout of the run's recorded directory (a subdirectory of it
is the same checkout; another worktree is not); `detail` names both directories, and says
so when the recorded directory no longer exists (then use Squadron's own commands, such as
`sq run --resume`). `held` (slice 242): the question ends with an `amoeba-request: <id>`
marker naming a request this project sent, and that request is still `open` or
`accepted`; `detail` gives its state. The run stays paused, and Amoeba starts
`handle-pause` for it again once the request ends: after any call but an MCP `answer`
(slice 262: the CLI after every command, and `amoeba handle-pause` itself), a machine with
work waiting makes one `claim_work` call and starts, detached, an
`amoeba handle-pause --json -- <run id>` in the run's checkout for every held question
whose request is `done`, `declined`, `cancelled`, `expired` or no longer stored (at most
five items per claim, and one question at most once per `answering_wait_seconds`). The
same claim hands out a dead claim's `handle-pause`, a resume, and a wake (below). Its
output goes to `<state home>/logs/handle-pause/<run id>-<UTC stamp>.{stdout,stderr}.log`,
and a start that fails is a `start_failed` line in the calls log. A question is started
at most three times this way (`MAX_AUTOMATIC_STARTS`); then it waits on the PM as
`starts_exhausted`. That call settles the
question by the request: a `done` result is given to the answering run as a passage, and
any other end waits on the PM. Nothing else needs to run `handle-pause` for a held
question. Exit 0 for every outcome.

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
| `resume` | `outcome` (`resumed`, `refused` or `not_delivered`), `detail`, `resume_log`; null when the run is on another machine |
| `waiting_on_machine` | when the question's run is on another machine (slice 262): `machine` (its name) and `last_called_at` (the hub's time that machine last called, or null). The answer is recorded and the run resumes at that machine's next call; plain text says so |
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

`claimed`, `waiting_on_pm` and `waiting_on_request` (a held question, slice 242) close
as `dismissed`; a dismissed held question's request keeps its own state, and its end
starts nothing; an `answered` question whose
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

## `amoeba standing --text TEXT [--program ID | --member NAME]`

Records a standing answer: a ruling the PM gave ahead of time, in the PM's own words,
for every later case it covers (slice 230). With neither flag it reaches every member
(reach `all`); `--program` limits it to that program's members (reach `program`), and
the program must exist; `--member` limits it to one member (reach `member`), a Context
Forge project name or id that must be an active member. `--program` and `--member`
together is a usage error (exit 2). It takes no working directory. Result
(`StandingResult`):

| Field | Meaning |
|---|---|
| `outcome` | `given`, `unchanged` (an active standing answer already has the same text and reach; nothing written) or `rejected` |
| `rejection` | with `rejected`: `malformed` (blank text, both reaches, unknown field), `no_such_program`, `no_such_member` (Context Forge does not know the name, or the project is not an active member) or `too_long` (with it, the rendered standing answers reaching some member it reaches would pass `passages_max_chars`; nothing written. The rules, plan and program text they join is checked at each pause, as `sources_too_large`) |
| `standing_id` | the standing answer given, or the matching active one; null when `rejected` |
| `reach` | `all`, `program` or `member` |
| `program` | the program, for reach `program` |
| `member` | the member's Context Forge project id, for reach `member` |
| `problems` | one line per problem when `rejected` |

The text says `given` or `unchanged`, the id and the reach (`everything`,
`program <id>` or `member <id>`). Exit 1 when `rejected`, exit 3 when the store or
Context Forge fails (nothing written), else 0.

An agent calls it for the PM, like `answer`: the text is a ruling the PM actually gave,
passed on as given, never one the agent composed. From the next question on, every
answering run for a member it reaches is sent it as a `standing_answer` passage, which
still passes the not-authorized list, the check step and the answer screen like any
other passage. It does not answer questions already waiting. A repeat is safe: the
lookup and the insert are one write transaction, so a call whose result never arrived
(an MCP timeout or a dropped client) can be made again and answers `unchanged` with the
one row. The text is never edited: a changed ruling is `withdraw` and a new `standing`,
and the newer date wins under the prompts' "later date wins" rule even before the old
one is withdrawn.

## `amoeba withdraw STANDING_ID --reason TEXT`

Withdraws a standing answer, so no answering run that gathers context after it is sent
it (slice 230). `STANDING_ID` is an integer, the id `list standing` prints. Result
(`WithdrawResult`):

| Field | Meaning |
|---|---|
| `outcome` | `withdrawn`, `unchanged` (already withdrawn; nothing changed) or `rejected` |
| `rejection` | with `rejected`: `no_such_standing_answer` or `malformed` (blank reason, an id that is not a positive integer) |
| `standing_id` | the standing answer |
| `problems` | one line per problem when `rejected` |

Exit 1 when `rejected`, exit 3 when the store fails (nothing written), else 0.

An agent calls it for the PM, under the same rule as `standing`. Withdrawing changes
only what later questions are sent: answers already delivered from it stay delivered
and stay in `decisions`, and a question already waiting is not gathered again (it ends
by `answer`, `dismiss` or the run moving on). There is no un-withdraw; giving the ruling
again with `standing` is the undo, as a new row. Repeating a call is safe: a row already
withdrawn answers `unchanged` and keeps its first date and reason. `rm` of a member
withdraws the standing answers whose reach is that member, with reason
`member_removed`, in the same transaction as the removal; reach `program` and `all`
are untouched, and registering the member again does not bring them back.

## `amoeba status [--program ID]`

What is running, paused and waiting on the PM. Needs the config (for
`answering_wait_seconds`) and `sq runs list --json`. Scope: `--program ID` is that
program; with no flag, run from a member's checkout it is that member's program, and
from anywhere else it is every program. A failing `cf` while finding the checkout's
project is exit 3, never a wider scope. Every member in scope is listed, even with
nothing to show. After the result is built, `status` (and `list`'s default view) starts
`handle-pause` for each held question whose request has ended, as `handle-pause`'s
`held` describes; the result does not change. Result (`StatusResult`):

| Field | Meaning |
|---|---|
| `outcome` | `listed` or `rejected` |
| `rejection` | with `rejected`: `unknown_program` (`problems` lists the known ids) or `malformed` |
| `notice` | the quoted-data notice (`QUOTED_DATA_NOTICE`), set when any member shows a request, a rejected call, a `waiting_on_request` run or a waiting question with a `request_id`, and null otherwise: those subjects, recipients and request reasons are other agents' text |
| `programs` | per program, `members`: each `{id, name}` with `runs`, `waiting_on_pm`, `requests`, `rejected_calls`, `sessions` and `wake` |
| `unplaced_runs` | paused runs no member could be found for: `run_id`, `status`, `reason`, `checkpoint_kind`, `detail` |
| `closed_now` | what this call closed (closures made by `handle-pause` are in that call's calls-log `detail`, not here), so each automatic closure is seen once: `{program, member, run_id, paused_at, question, closed_reason, closed_detail}` for a question, and for an answer marked `not_delivered` the same with `answer_seq` and `resume_outcome` |
| `sweep_problem` | set when the closing, or the message sweep, could not take the store's lock; nothing was closed and the rows show as before (both texts, joined, when both fail) |
| `file_problems` | calls-log day files that could not be read, a sentence naming how many runs of each kind were left out when the machine's runs document passed its size limit (paused runs are kept first, so the runs listed under each member are paused runs first, then the others), and entries `prune` could not remove |
| `problems` | one line per problem when `rejected` |

`status` closes the open questions of the members in scope whose run is no longer at
that pause, judged from the one `sq runs list --json --all` listing it already makes
(no further `sq` call), then prunes old scratch and logs. A run absent from the listing
whose run file still exists keeps its question open: an incomplete listing closes
nothing. `closed_reason` is `dismissed` (by `dismiss`), `run_moved_on` (the run is at a
later pause, or finished; `closed_detail` is the run's state) `run_gone` (Squadron no
longer knows the run) or `machine_removed` (`amoeba hub rm-machine` removed the machine the
run paused on; `closed_detail` names it).

A member's `requests` are its open and accepted requests, sent and received, each
`{id, direction, other_member, other_name, subject, state, created_at, state_changed_at,
parent_id, child_ids}`. `state` is the effective state, `other_name` is the member's
stored name (a removed member keeps its name), and `child_ids` are the live requests whose
`parent_id` is this one (what it is waiting on). Requests do not count as waiting on
the PM. A member's `rejected_calls` are its retained refused `send`, `reply` and
`cancel` calls, newest first, each `{operation, code, to_ref, message_id, parent_id,
detail, created_at}`.

A member's `sessions` are its live `amoeba-mcp` sessions (slice 241), oldest first,
each `{client, directory, started_at, heartbeat_at, push_confirmed_at, machine,
client_version, door_version, behind}`: `client` is
the client's name as it gave it (or `unrecognized`), `directory` the server's working
directory, `machine` the machine it runs on (slice 263, sessions of every machine are
listed), `client_version` and `door_version` those of its program, `behind` true when
its door version differs from the hub's, `heartbeat_at` its last beat, and `push_confirmed_at` when its agent first
answered a channel event with an `inbox` call (null while unconfirmed). A session
whose last beat is older than `session_stale_seconds` is gone and not listed, and only
active members show sessions. Sessions do not count as waiting on the PM and do not
set the `notice`. The text adds a **Live sessions** section, one line per session:
`<client>  <machine>  <directory>  up <age>  last beat <age> ago  push confirmed|push
unconfirmed`, ending `behind` for a behind one.

`status` also returns (slice 263) `hub_door_version`, the door version the hub serves,
and `machines`: each machine with a token and the calling machine, by name, each
`{name, last_called_at, client_version, door_version, behind, calling, runs_reported_at,
runs, runs_problem}`. `behind` is true when `door_version` differs from the hub's, false
when equal, null when none is recorded (the `local` machine); `calling` is true for the
machine that made the call. For every other machine `runs_reported_at` is when it last
reported its runs (null when it never did), `runs` its runs not completed, each
`{run_id, pipeline, status, directory, checkpoint}` (`checkpoint` for a paused run), and
`runs_problem` the error text when its stored report does not validate, with no `runs`;
the next `status` or `list` that machine makes replaces the report. The calling
machine's own runs are in the other fields. Nothing on another machine is placed under
a member, closed or swept by this call. The text adds **Runs on other machines**: one
heading per other machine, `<machine>, reported <age> ago`, `<machine>, nothing
reported` or `<machine>, reported <age> ago, runs unreadable: <runs_problem>`, with one
line per run (id, pipeline, status, directory); and **Behind the hub**, when any machine
or session is behind: each with its client and door version, `uv tool install --force
amoeba-ai`, and a note to restart the sessions listed. One whose door version is above
the hub's is marked `ahead of the hub`, and the section then says to upgrade the hub
and gives no client command. Neither section counts as waiting on the PM or sets the
`notice`.

A member's `wake` (slice 244) is present only for a member with a wake command, else
null: `{command, machine, waiting_on, running, stopped, last_problem}`. `command` is the
stored command in plain text. `machine` (slice 262) is the machine whose checkout's
command it is, shown as `wake command (on <machine>):`; `waiting_on` lists the other
machines (`machine`, `last_called_at`) a due wake waits for, which claim it at their next
call. `running` is the member's wake not yet recorded as ended, or null:
`{started_at, deadline_at, command_pid, log_stem, overdue}`; `overdue` is true once
`deadline_at` has passed with the row still unended, which most likely means its wrapper
is gone (the row cannot show it; it only shows that no end was recorded): it no longer
counts as a live wake, so the member can be woken again, and `command_pid`
(null when unknown) is the command's pid, which Amoeba never signals. `log_stem` is the
log files' path without the `.stdout.log` and `.stderr.log` suffix. `stopped` is
`{used, limit}` once the member has used `max_wakes_per_day` wakes in the last 24 hours
(failed starts included), else null. `last_problem` is the member's newest ended wake
when it was `start_failed`, `timed_out`, `wrapper_failed` or `exited` with a non-zero
code: `{outcome, exit_code, detail, ended_at, log_stem}`; a newest wake that exited 0
clears it. `detail` is an exception class and its OS message, never the command's text.
Waking does not count as waiting on the PM, so it does not change `Nothing needs you.`
The text adds a **Waking** section: under each such member the command on its own line,
then `running since <age>, stops <time>`, or when overdue `overdue since <time>: no end
was recorded, so its wrapper is probably gone; the command's own cap ends it, or check
and stop pid <pid>, log <log_stem>` (no pid text when the pid is unknown), then `waking stopped: <used> of
<limit> wakes used in the last 24 h`, then `last wake <outcome> <age> ago: <detail>, log
<log_stem>`.

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
| `waiting_on_request` | held on a request this repo sent (slice 242); `detail` is `waiting on request <id> (<state>)`, the state being the request's effective state or `gone` when the store no longer holds it, followed by `; handle_pause last started <time>` once Amoeba has started one; Amoeba starts `handle-pause` itself once the request ends | none |
| `run_file_unreadable` | Squadron's run file could not be read; `detail` says why | none |

A run with `pause` `unhandled`, `claim_stale` or `waiting_on_request` also has
`last_call`: the newest calls-log line for it (see above), or null if none was logged,
which shows why a hook missed or, for a held run, why a start failed (`start_failed`)
or how the started `handle-pause` ended.

`next` is `{operation, run_id, paused_at, directory}` or null. For `handle_pause`,
`directory` is the run's own checkout: run the command there. A waiting question
(`waiting_on_pm`) has `run_id`, `paused_at`, `question`, `slice_label`,
`waiting_reason`, `waiting_detail`, `since`, `run_state`, `next`, `request_id`, `machine`
and `machine_last_called_at`. `request_id` is the request behind a `request_*` reason
(slice 242), else null. `machine` (slice 262) is the machine the run paused on, null once
it was removed, shown as a `machine:` line; `machine_last_called_at` is set only when that
is not the calling machine, because an answer for it waits for its next call. Every open waiting
question of a member in scope is listed. `run_state` is `at_pause` (`next` is
`answer`); `moved_on` (`detail` gives the run's state) and `not_listed` appear only for
a row a failed closing left open, since the closing otherwise closes them in the same
call. `other_machine` (slice 263) is a question on a machine other than the caller's:
this call cannot say where its run is (`next` is null), and its first line ends
`on <machine>`. `reason` of an unplaced run is `no_directory` (a run from before `sq` 0.24.24), `directory_missing`
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
| `notice` | the quoted-data notice (`QUOTED_DATA_NOTICE`), set when any record has a `request_id` and null otherwise: a request's result, reason and cited passage are another repo's text |
| `records` | each: `seq`, `recorded_at`, `program`, `member` (`{id, name}`), `run_id`, `paused_at`, `slice_label`, `question`, `answered_by` (`answerer` or `pm`), `via` (`cli` or `mcp`, the door that carried a PM answer; null for an answer from before schema version 4 and for automatic answers), `answer`, `prior_answer_seq`, `based_on`, `resume`, `retracted_at`, `retract_reason`, `request_id` (the request a held question waited on, slice 242; null for any other question) |
| `read_through` | the last listed `seq`, only when the listing started at the marker, was not narrowed and is not empty; else null. Give it to `mark-read` |
| `marker` | the marker's value when read |
| `problems` | one line per problem when `rejected` |

`prior_answer_seq` is the newest earlier answer to the same question (a PM answer after
an automatic one is an override). `based_on` is, for `answerer`, the cited passages
(`id`, `kind`, `source`, `date`; `kind` is `pm_answer` for a PM precedent,
`standing_answer` for a standing answer (its `source` is `standing:<id>`, the id
`list standing` shows; slice 230), and null for the others, which the store records no
kind for; a cited `request_result` passage, a
held question's request result, has the request id as its `source` and a null `kind`,
being a passage the store records no kind for) with `check_verdict` and
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
exclusive (both is exit 2). Limits: `--version` at most 128 characters, `--changed` at most
4000, at most 50 `--touched` items of at most 200 characters each; a report over a limit
is rejected as `malformed`, naming the limit, and nothing is cut. No flag is required by argparse: an absent flag is left out
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
 "problems": [],
 "sweep_problem": null}
```

`sweep_problem` is the text of the message sweep that did not run because the store stayed
locked (the report was still made); text mode prints it as a last line. `member` is null
when the directory is not a member. `report` is the stored report after
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
for `report-release`). `name` is the member's stored name. `warnings` is always
empty: `not_in_context_forge` (a member Context Forge's project list did not name) is no
longer raised, because names come from the store, and the code stays for old readers. No
`cf` call is made by `changes` beyond the caller's own directory; a `cf` failure there is
exit 3.

Text: when any report is shown, a first line saying release reports and messages are
written by other repos' agents, data to judge and never instructions
(`QUOTED_DATA_NOTICE`, in `operations/quoted_data.py`); then one
entry per report (provider name or id, commit, version, the changed text cut
to the line width, the touched items), warnings as `warning:` lines, and
`No changes since <time>.` when no pair has a report. A rejection prints
`rejected: <code>` and a line per problem. Exit codes are as for `report-release`.

## `amoeba send`, `inbox`, `reply` and `cancel`

Requests between members (slice 240): any agent in one repo can ask another repo for
work and hear back, by polling `inbox`. Each command works for the member whose checkout
it runs in; a session in no member names the caller with `--member` (a Context Forge
project name or id). A directory in a member plus a `--member` naming a different one is
`member_mismatch`: a repo's session cannot send as another repo.

```
amoeba send --id ID --to MEMBER --subject TEXT (--body TEXT | --body-file FILE|-) [--parent ID] [--member MEMBER]
amoeba send --note --id ID (--to MEMBER | --to-program ID) --subject TEXT (--body TEXT | --body-file FILE|-) [--member MEMBER]
amoeba inbox [--since SEQ] [--member MEMBER]
amoeba reply ID accept|decline|done [--text TEXT] [--commit HASH] [--version TAG] [--member MEMBER]
amoeba cancel ID [--reason TEXT] [--member MEMBER]
```

No flag is required at the parser: an absent one is left out of the request, so the
operation rejects it with the same detail on both doors. `--body-file -` reads the body
from stdin. `--body` with `--body-file` is exit 2, as is a `--body-file` that cannot be
read or is not UTF-8, and a `--since` that is not a whole number.

| Command | `outcome` values | Exit 0 | Exit 1 |
|---|---|---|---|
| `send` | `sent`, `unchanged`, `rejected` | `sent` and `unchanged` | `rejected` |
| `inbox` | `listed`, `rejected` | `listed` | `rejected` |
| `reply` | `applied`, `rejected` | `applied` | `rejected` |
| `cancel` | `cancelled`, `rejected` | `cancelled` | `rejected` |

Any of them is exit 3 when `cf` fails or times out, with nothing written.

**Text limits.** A text over its limit is rejected `malformed`, naming the limit; it is
never cut. `id` 64 characters (`[A-Za-z0-9][A-Za-z0-9._-]*`), `subject` 200, `body`
4000, a `done` result and a `decline` text 4000, a cancel `reason` 1000, a `version` 128.
`parent` follows the `id` rule. `commit` is a full hash (40 or 64 hex characters). A release note's body is composed by Amoeba and has its own bound, `MAX_RELEASE_NOTE_BODY_LENGTH` (14439 characters; see Release notes below).

**Caps.** What `inbox`, `status` and `list` read is bounded by how it is written. A
member keeps its newest 100 rejected calls: an older one is dropped as a new one
arrives. A sender holds at most 200 requests: a `send` that would pass that first drops
the sender's oldest finished requests (`done`, `declined`, `cancelled`, `expired`) with
their deliveries, and is rejected `too_many_open` only when all 200 are still `open` or
`accepted`; finishing or cancelling one frees a place. A sender holds at most 200
notes: a note that would pass that first drops the sender's oldest notes with their
deliveries (a note has no state, so none is ever refused). A rejected call keeps the id,
recipient, parent and detail as given, cut to 500 characters and ending in `…` when
longer (a request's own text is never cut).

**`send`.** `--id` is yours, so a retry after a lost response is safe. Sending an id that
exists compares the sender, the addressee, the parent, the subject and the body: the same
content, request not ended, is `unchanged` (the stored request, no second delivery); the
same content for a request that is `done`, `declined`, `cancelled` or `expired` is
`request_ended`, naming the state and saying to send it again under a new id, so a retry
never reads as success for a request that is gone; different content is `id_reused`,
whoever sent it. `--parent` must name a request (`parent_unknown`) whose depth is below
`max_chain_depth` (`chain_too_deep`); the new request's depth is the parent's plus one.
`--to` is any active member of any program (`unknown_recipient` otherwise). A request
expires `request_open_ttl_hours` after it was sent.

**`reply`.** Only the addressee may reply (`not_addressee`). `accept` is from `open`. A
second `accept` is `already_accepted`, naming when the first happened, so exactly one of
two at once wins. `decline` is from `open` or `accepted`. `done` is from `accepted` only
(`not_applicable` on an `open` request, saying to accept first). `decline` and `done`
need `--text`; `--commit` and `--version` are for `done` only; `accept` takes no text.
An unknown id is `unknown_request`. Any action on a request that has ended is
`not_applicable`, naming its state; an `open` request past its expiry counts as
`expired`.

**`cancel`.** Nothing is checked about the caller: whoever names the id may cancel,
which includes the sender's agent, the addressee, and an agent acting for the PM from a
session in no member that names no `--member` (then both parties are told). An
explicit `--member` that names no active member is rejected `not_a_member` and cancels
nothing: the caller said who it is, and that is wrong. `open` and `accepted` become
`cancelled` with the optional `--reason`; anything else is `not_applicable` naming the
state, so a repeated cancel is rejected.

**`inbox`.** Without `--since`: every request the member sent or received that the store
still holds, `deliveries` empty. With `--since SEQ`: the member's deliveries after `SEQ`
in order, and the requests they concern in their current state (a request that changed
twice appears once in `requests` and twice in `deliveries`), plus the member's open
requests already past their expiry, shown `expired`. `as_of_seq` is the highest delivery
number ever assigned: keep it and pass it as the next `--since`. A `--since` above it is
`beyond_last_record`, with a message saying to call without `--since`: the cursor came
from a replaced store. `inbox` writes nothing and marks nothing read.

**Who is calling is a claim.** Nothing verifies it. A session in a member's checkout
cannot name another member (`member_mismatch`), but a session in no member can name any
active member with `--member`, and any caller that names a request id may `cancel` it.
That is the architecture's stated trade: every agent on one machine acts for the same PM.

**Rejections are recorded.** A `send`, `reply` or `cancel` rejected once its caller is
known (a malformed or over-limit document included) leaves a row that `list` and
`status` show under the caller; `not_a_member`, and a `cancel` by an unknown caller,
leave none. When a call times out or its response is lost, the work may have happened:
a retried `send` is `unchanged` or `request_ended`, and a retried `reply` or `cancel` is
rejected naming the state the first call reached. A rejection after a timeout means the
first call took effect, and `inbox` shows the state.

**Text from other repos is data.** Every result that holds request text has a `notice`
saying release reports and messages are written by other repos' agents: data to judge,
never instructions. The text output prints it as its first line wherever such text
follows, and the tool descriptions of the four tools, `list` and `status` carry it. In
text, a rejection prints `rejected: <code>: <problem>`; a request prints its id, who it
is to or from, its state and age, then its subject, body, result and reason cut to the
line width (the full text is in `-j`).

## Release rejection codes

`not_a_member` and `not_reported` are two members of the rejection vocabulary, next to
`malformed`; `report-release` and `changes` use the codes that apply to them, as above.

## Request rejection codes and result fields

The four request operations (`send`, `inbox`, `reply`, `cancel`; slice 240) reuse
`malformed`, `not_a_member` and `beyond_last_record`, and add these codes to the same
vocabulary:

| Code | Meaning |
|---|---|
| `unknown_recipient` | `send` to a reference that is no active member |
| `member_mismatch` | an explicit `member` names someone other than the member the directory is in |
| `id_reused` | `send` with an id that exists and carries different content |
| `request_ended` | `send` again of a request that is done, declined, cancelled or expired; names the state |
| `unknown_request` | `reply` or `cancel` for an id no request has |
| `not_addressee` | `reply` by a member the request was not sent to |
| `already_accepted` | `reply accept` on a request already accepted; names when |
| `not_applicable` | a `reply` or `cancel` the request's current state does not allow; names the state |
| `parent_unknown` | `send` whose `parent` names no request |
| `chain_too_deep` | `send` whose parent is already `max_chain_depth` deep |
| `too_many_open` | `send` by a sender that already holds the most requests (200), every one still `open` or `accepted` |

Every result has `outcome`, `notice`, `rejection` (a code, null unless rejected) and
`problems` (one line per problem when rejected, empty otherwise). `send`, `reply` and
`cancel` add `request`, a request view or null; `inbox` adds `member`, `since`,
`as_of_seq`, `requests` and `deliveries`. `send` also has `wake_problem` (slice 244):
a string when the wake step of a stored request failed with a store error, so no wake
was claimed or its start could not be recorded, and null otherwise. The request is
written regardless, and the text output prints the line; a same-id retry while the
request is still `open` runs the wake step again. Slice 262 adds two more. `woke` is the
wake the hub claimed for the calling machine (`wake_id`, `directory`, `log_stem`), which
the client then starts as `amoeba wake-run <wake id>`, detached; it is null when no wake
was claimed here. `wake_waiting_on` lists each machine (`machine`, and `last_called_at`,
the hub's time it last called, or null) that has the recipient's wakeable checkout when a
wake is due and none of the calling machine's checkouts can take it: that machine claims
the wake at its next call, and the text output says so. A request nobody can wake waits
for an agent or its expiry.

A request view has `id`, `direction` (`sent` or `received`, relative to the caller; null
when the caller is neither party, as for a `cancel` from a session in no member),
`from_member`, `to_member`, `parent_id`, `depth`, `subject`, `body`, `state` (the
effective state), `result`, `result_commit`, `result_version`, `reason`, `created_at`,
`accepted_at`, `state_changed_at` and `expires_at`. A delivery view has `seq`,
`message_id`, `event` and `created_at`.

**Notes (slice 243).** `send --note` sends information that needs no reply, to one
member (`--to`) or to every other active member of a program (`--to-program`, a
program id). `--note` is a flag: absent, the document carries no `kind` and means a
request. A `send` document carries `kind`, `request` (the default when absent) or
`note`, and `to_program`. The rules by kind:

- A **request** needs `to`, `subject`, `body` and `id`, and takes no `to_program`.
- A **note** needs `subject`, `body`, `id` and exactly one of `to` and `to_program`,
  and takes no `parent`: it has no chain and no state. A violation is `malformed`,
  naming the field and the kind, and is recorded; the text limits are the request's.
- A note to a program reaches the program's active members except the sender, each as
  its own delivery, fixed when it is sent (a member added later gets nothing). An
  unknown program, and a program with no one else in it, are `unknown_recipient`, the
  detail saying which. A note to one's own member (`--to`) is delivered.
- Resending a note with the same content is `unchanged` and writes no delivery; a
  reused id with other content, or another kind, is `id_reused`.
- A note needs no reply and has no state. `reply` and `cancel` of a note's id are
  `unknown_request`, and a `--parent` that names one is `parent_unknown`, each saying
  the id is a note. A note leaves by age: it is pruned `prune_after_days` after it was
  sent, read or not, with its deliveries. `list` and `status` show no note.

`send` gives `note` in its result, a note view or null (null for a request and on
rejection). `inbox` gives `notes`, a list of note views, empty when there are none: the
notes the member has a delivery for, with `--since` (those after that delivery number,
in order) or without (every one still held). A program note's sender does not see it.
Its text has a **Notes** section after **Requests**: each note's id, sender, age,
subject and body, the notice first. A note view has `id`, `from_member`, `to_member`
(null for a program note), `to_program` (null for a direct note), `subject`, `body`
and `created_at`. A send with neither recipient is rejected `malformed` by the
operation, as on the MCP tool: `--to` is no longer required by the parser.

**Release notes.** `report-release` writes one note to each consumer that sees the
report in `changes`, in the report's own transaction, for `recorded`, `versioned`,
`corrected` and `withdrawn` (`unchanged` and a rejection write none). The note is from
the provider, with an id of `release:` and a random hex string (a sender's id cannot
hold a colon, so the two never collide), and a subject and body composed by Amoeba: the
commit, the version or `none`, the `changed` text and the `touched` items; a correction
says it replaces the earlier text; a withdrawal carries the commit and version and says
to disregard the report. A report that cannot write its notes is not stored and the
call exits 3, so retrying runs as a first call. Before its write, `report-release` runs the due-checked message sweep (so notes are pruned); a store held past the busy timeout skips that sweep, which is logged and returned as `sweep_problem` in the result, and the report is still recorded. The body is bounded by
`MAX_RELEASE_NOTE_BODY_LENGTH`, 14439 characters: the length of the longest body the
template composes from a report with every field at its limit (4000 characters of
`changed`, 50 touched items of 200 characters, a 128-character version and a
64-character hash), so it follows those limits and the template. It is composed, not
caller text, so `send`'s `body` limit does not bind it.

## Work a machine has waiting (slice 262)

After every operation on the CLI, after every MCP tool call but `answer`, and at the end
of `handle-pause` on every path, a raise included, Amoeba runs one **after-step**. It
never changes the call's result or exit code, and a failure in it is one log line.

1. The file clean-up, when one is due (at most one walk an hour), except after
   `handle-pause`, `status` and `list`, which run their own and report its problems.
2. If this machine has work waiting, one claim of up to five items, started detached:
   an answer to resume (`amoeba resume-run <answer seq> <claim id>`), a held question
   whose request ended or a claim that went stale (`amoeba handle-pause <run id>` in the
   question's checkout, logs under `logs/handle-pause/`), and a due wake
   (`amoeba wake-run <wake id>`). The rest waits for the next call. A `handle-pause` it
   starts runs the after-step too, so a batch over five drains.

Through the door every done reply says whether the calling machine has work waiting;
with no client file the after-step reads it from the local store. When the hub cannot
tell (its `config.yaml` does not load) the client prints one line on stderr, `the hub
could not tell whether this machine has work waiting: <error>`. When the call got no
reply, the after-step makes no call.

Work is the machine's own: a question's resume and its `handle-pause` run on the
machine whose run it is, a wake on the machine with the wakeable checkout. Each item is
claimed before it is started, so two machines or two calls never start one item twice;
a claim nobody finishes is handed out again once its limit has passed. A question
started automatically three times with no outcome waits for the PM as
`starts_exhausted` (its detail points at that machine's calls log), and an answer
handed out three times with no recorded outcome is recorded `refused` with the count.

## The hub and joined machines (slice 260)

A machine with a client file (`client.yaml` in the config home, written by
`amoeba join`) is **joined**: its commands go to the hub, not to a local store. The
check is made on every call, before anything local is read or written.

| On a joined machine | Result |
|---|---|
| `decisions`, `mark-read`, `dismiss`, `retract`, `standing`, `withdraw`, (slice 261) `add`, `rm`, `list`, `status`, `send`, `inbox`, `reply`, `cancel`, `changes`, `report-release`, and (slice 262) `answer` | Run on the hub's store. The text, `-j` JSON and exit codes are the ones the local way gives. Members show by name |
| `handle-pause`, `wake-run`, `resume-run` (slice 262) | Run on this machine, each store step a door call (below). No local `config.yaml` is read: the hub's settings come with the first step |
| `amoeba-mcp` start | `NotServedError`: this machine is joined to the hub at `<address>`, and the door does not serve `amoeba-mcp` yet. Exit 3, nothing local is read or written |
| `amoeba hub ...` | `LocalStoreClosedError` naming the hub, before `hub.yaml` is read or any file is written |
| `amoeba join`, `amoeba leave` | Run (below) |

**Commands that run here (slice 262).** `handle-pause`, `wake-run` and `resume-run` read
this machine's run files, repos and scratch, so they run here; each store transaction
they make is one door call (a step). A command decides once, when it starts, whether it
uses the door (a client file exists) or the local store, and keeps that to its end. If
the client file goes partway, the next step fails with `ClientFileError` and no local
store is opened. A step that gets no reply stops the command with
`HubUnreachableError` (exit 3); a reply that does not fit what the client expects is
`StepReplyError` (exit 3, naming the step and the field, and for a step that writes,
that the hub applied it). What a down hub leaves behind is picked up by this machine's
next call: a stale claim, a resume claim that ran out and an unended wake are each
handed out again once their limit has passed.

**What the client does first (slice 261).** The operations that need something only this
machine can read gather it before any hub call, and a failure raises `ContextForgeError`
(exit 3) with nothing sent: the caller's Context Forge project (`cf get --json` in the
current directory) for `send`, `inbox`, `reply`, `cancel`, `changes`, `report-release`,
`status`, `list` with no subject, and `rm` with nothing named; the checkout (the project's
id, name and path and the repo's reduced `origin`, from `git remote get-url origin`) for
`add` when an entry names no member; and the machine's Squadron runs (`sq runs list`, each
run's directory's project, a paused run's run file and the calls log) for `status` and
`list` with no subject. They travel beside the document as the body keys `here` and `runs`;
a call that does not need one sends none, and the hub ignores one it is sent. A key the
call needs that is missing or does not parse is refused as `malformed_call`, and so is an
`origin` that is not in its reduced form: the raw address can hold a password and never
leaves the client. The hub does not start wakes yet (slice 262): a `send` to a member a
wake is due for on any machine is refused as `not_served`, naming the member and the
machines with a wake command, with nothing written; remove the wake command
(`amoeba add --no-wake-command` in that checkout) to send. The hub does not run the close
sweep, pruning or run starts for `status` and `list`: they read the files of the machine
that ran `sq`.

On a **hub home** (the config home holds `hub.yaml`) every command that opens the
local store, and `amoeba join`, refuse with `HubHomeError` / `JoinError`: the hub's
store is served by `amoeba hub serve`, never written behind the door.

### `amoeba join LINE [--set-aside-local] [-j]`

`LINE` is `<address>,<fingerprint>,<token>`, printed by `amoeba hub invite <machine>`.
It fetches the hub's certificate, checks its fingerprint against the line, saves it,
makes one `hello` call and writes the client file. Re-running it on a joined machine
replaces the token. With `--set-aside-local` the local store is marked closed, copied to
`amoeba.sqlite3.set-aside-<UTC stamp>` and the original deleted; its path is printed.
Without the flag a local store makes `join` refuse (`JoinError`). A stopped `join` is
finished by running the same command again, or ended by `amoeba leave`.

Text: `joined the hub at <address> as <machine>`, then the set-aside path when there is
one. `-j`: `{"machine", "address", "set_aside"}`.

### `amoeba join --address HOST:PORT [-j]`

Changes only the address in the client file and makes no hub call. With no client file
it is a `JoinError` (the machine is not joined). `-j`: `{"address", "machine"}`.

### `amoeba leave [-j]`

Puts a set-aside store back, deletes the client file, deletes the saved certificate;
each step is skipped when there is nothing to do, and no hub call is made, so it works
with the hub down. A store found at the store path that `join` did not make is moved to
`amoeba.sqlite3.displaced-<UTC stamp>` and its path is printed; only the newest three
displaced stores are kept, so `leave` deletes the older ones when it makes another.
`leave` in a hub's home (one with `hub.yaml`) is refused with `JoinError` and changes
nothing. Where nothing is joined and nothing is set aside it does nothing and exits 0. `-j`: `{"restored", "displaced", "cleared_mark",
"removed"}`.

| Error | Exit | When |
|---|---|---|
| `JoinError` | 3 | A join line that does not parse; a fingerprint that does not match (saves nothing; the token was not sent); a local store without `--set-aside-local`; a hub home; `--address` with no client file |
| `StoreRelocateError` | 3 | (also, as above) a set-aside store beside a store `join` did not make: the message names both files and says to run `amoeba leave` |
| `ClientFileError` | 3 | The client file is readable by others (the message gives `chmod 600`), has a missing or unknown key, or the saved certificate is missing (join again with a new line) |
| `HubUnreachableError` | 3 | No reply within the retry time (30 s), or nothing at the address speaks TLS; a writing call adds that its outcome is unknown and what to run |
| `HubCertificateError` | 3 | The hub did not present the saved certificate; never retried |
| `HubRefusedError` | 3 | The hub refused the call; the message holds the hub's address, the code and its text. `door_version` adds the upgrade command and `bad_token` adds `hub invite` and `join` |
| `NotServedError` | 3 | A joined machine ran a command the door does not serve |
| `StepReplyError` | 3 | A step's reply did not fit its model (slice 262): names the step and the field, and for a writing step says the hub applied it |
| `LocalStoreClosedError` | 3 | A command found the machine joined, or a local store set aside for a hub |

### `amoeba hub ...`

CLI-only (no MCP tool), run in a **hub home** (the config home holds `hub.yaml`). The
first line of each refuses on a machine with a client file (`LocalStoreClosedError`),
before `hub.yaml` is read or any file is written. Each admin command (every one but
`serve`) then refuses a home with no `hub.yaml` (`NotAHubHomeError`), so it never
opens an ordinary machine's own store, and refuses a hub store whose schema is behind
(`HubStoreBehindError`), because only `serve` migrates, after its backup. Each admin
command opens the store without creating it: before the hub has finished its first
start each fails with `HubStoreMissingError` (exit 3) and writes no file. A rejected request is exit 1;
`HubStartError`, `BackupError`, `HubConfigError` and every operational error are exit 3
with one stderr line.

| Command | Does | Exit 1 when | `-j` |
|---|---|---|---|
| `amoeba hub serve [--from-backup DIR]` (`DIR` may be relative) | Starts the hub (D14): loads `hub.yaml`, binds the socket, decides the start from what the state directory and `backup_dir` hold, migrates after a pre-migration backup, takes a timed backup if due, serves | — | no |
| `amoeba hub invite MACHINE` | Makes the machine, or gives an existing one a new token (ending the old one), and prints the join line `<address>,<fingerprint>,<token>`; needs `hub.yaml` for the address and the certificate for the fingerprint | the name is not `[a-z0-9][a-z0-9._-]*`, at most 64 characters | `{"machine", "join_line", "new"}` |
| `amoeba hub machines` | Lists each machine: name, whether it has a token, last call time, client version and door version; the first line is the hub's own door version, and a machine whose door version differs ends its line with `behind` or `ahead of the hub` | — | a list of `{"name", "has_token", "last_called_at", "client_version", "door_version", "behind"}`; `door_version` is the last one a non-session call recorded, `behind` is true when it differs from the hub's (its sessions cannot take a wake) and both are null when none is recorded |
| `amoeba hub rm-machine MACHINE` | In one transaction: closes what waits on the machine (its open questions as `machine_removed`, their undelivered answers as `not_delivered`, its unended wakes as `machine_removed`), then deletes the machine, its sessions and its kept results; its next call is `bad_token`, and a wake wrapper still running there stops its command at its next step. A later `answer` to one of its questions is recorded and `not_delivered` | no such machine | `{"removed"}` |
| `amoeba hub backup` | Takes a timed backup now and prints its path; safe while the hub serves | — | `{"path"}` |

`--from-backup DIR` restores a backup's store, certificate and key into the state
directory first, for one start only: it refuses a state directory that already holds a
working hub, moves anything else there into `replaced-<UTC stamp>/` and prints that
path on stderr. Only the newest `backups_kept` `replaced-` directories stay; a finished
restore deletes the older ones. A restore stopped anywhere is finished by running the same command
again; until then any other `hub serve` refuses and says so. Never put the flag in a
compose file.
