---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: The Amoeba store contract: the home, every table and column of the schema with its vocabulary and the operation that writes it, and the migration rule.
dateCreated: 20261109
dateUpdated: 20261117
status: complete
---

# Store contract

Amoeba keeps one SQLite file, `amoeba.sqlite3`, in its home. This document is the
reference for what is in it. `tests/test_contract_docs.py` fails if a table or column
of the schema is missing here.

## The homes

- **Config home:** `$AMOEBA_HOME` when set, otherwise `~/.config/amoeba/`. It holds
  `config.yaml` (see `config-contract.md`), which a person edits, and nothing else.
- **State home:** `$AMOEBA_HOME` when set, otherwise `~/.local/state/amoeba/`. It holds
  everything Amoeba writes: `amoeba.sqlite3` (with its `-wal` and `-shm` files),
  `answering/` (one scratch directory per answering run), and `logs/` with `answering/`,
  `resume/<run_id>/`, `calls/<UTC date>.jsonl` and, from slice 226, `mcp/`. With
  `AMOEBA_HOME` set both homes are that one directory.
- `XDG_CONFIG_HOME` and `XDG_STATE_HOME` are not consulted: the pause hook and an
  interactive shell may differ in them, and one command must find one store. A set but
  empty or relative `AMOEBA_HOME` is an error (`AmoebaHomeError`), never a fall back to
  the default.
- Only `config/home.py` reads the variable. The CLI (and the MCP layer, slice 226)
  build a `StateLayout` once and pass the paths down; operations take an open store and
  a config. The store is opened only through `open_state_store(layout)`.
- Tests set `AMOEBA_HOME` to a fresh temporary directory for every test.

### Moving a pre-228 install

Before slice 228 the state sat in `~/.config/amoeba/`. The first command of a new
version moves it, under a lock on the old store (so an old process still running and a
second new process both wait):

1. Back up the old store into `amoeba.sqlite3.moving` in the state home, rewrite every
   `answers.resume_log` that starts with the old home to start with the state home,
   and verify the copy (integrity check, schema version, every table's row count,
   `MAX(answers.seq)`, no path left under the old home). A failed check deletes the
   copy and is `StoreRelocateError` (exit 3); the old store is never written.
2. Rename the copy to `amoeba.sqlite3` and delete the old store with its `-wal` and
   `-shm`.
3. Move each entry of the old `answering/`, `logs/answering/` and `logs/resume/` to the
   same place under the state home (to `.<name>.moving` first, then renamed). `config.yaml`
   is never touched.

Every step can be interrupted: a rerun finishes, and never recreates the old store.
The whole move holds an `flock` on `<state home>/.state-move.lock`, an empty file
created only when old state exists (deleting it is harmless), because the directory
moves are outside the old store's SQLite lock. If both stores exist and differ (an old
process kept writing after the move), the state-home store is kept and the old one is
set aside as `amoeba.sqlite3.legacy-<UTC stamp>` in the state home, named on stderr
with both stores' row counts and `MAX(answers.seq)`. **Deleting that file is its exit:**
no process reads it and `prune` never touches it.

## Concurrency

Writers are short-lived processes. The store opens in WAL mode with foreign keys on
and a 5-second busy timeout. `Store.write()` takes the write lock when the transaction
begins, so a read-then-write cannot fail halfway; `Store.read()` is one consistent
read. A writer that waits past the timeout gets `StoreBusyError`. There is no lock
file, pid file or read-only mode, and a missing store is created.

## Migrations

- Numbered files in `src/amoeba/store/schema/` (`001_baseline.sql`, `002_pause_handling.sql`,
  `003_question_lifecycle.sql`, `004_answer_via.sql`, `005_member_rules_from.sql`, `006_messages.sql`, `007_sessions.sql`, `008_waiting_on_request.sql`, `009_wakes.sql`, `010_standing_answers.sql`, `011_hub_and_door.sql`, `012_members_by_name.sql`, `013_local_work.sql`), shipped in the wheel. `EXPECTED_SCHEMA_VERSION` equals the highest number (12).
- Opening applies the missing files in order inside one write transaction and stamps
  `schema_meta.version`. A store stamped higher than the code expects is refused
  (`StoreSchemaError`) and left untouched.
- **No edits to `001`, `002`, `003` or `004`**, or any applied migration. A store may already
  exist. `ALTER TABLE ... ADD COLUMN` stays the default: an added column is nullable or `NOT NULL` with a constant
  default, may carry a `CHECK`, and may `REFERENCES` only with a null default.
- **The one exception is `003`.** A new question state means widening
  `questions.state`'s `CHECK` list, which SQLite cannot change in place, and a
  `closed_at` column beside an unchanged `state` would split one state across two
  columns that every reader has to combine. So `003` rebuilds `questions` once (create
  `questions_new`, copy, drop, rename). The runner turns foreign keys off around a
  migration, runs `PRAGMA foreign_key_check` before commit (any row raises
  `StoreCorruptError` and rolls back) and turns them back on. A later migration that
  needs another rebuild needs the same justification in its slice design.
- **`008` is the second rebuild, with that justification (slice 242, D2).** The
  `waiting_on_request` state widens the same `CHECK` list, and a held flag beside an
  unchanged `state` would split one state across two columns. `008` rebuilds
  `questions` by the same procedure, copying every row and key, so `answers` keeps its
  references; no index exists on `questions`, so none is recreated.
- **`013` is the third and fourth rebuild, with that justification (slice 262, D14).**
  `machine_removed` widens `questions.closed_reason`'s and `wakes.outcome`'s `CHECK` lists, which
  SQLite cannot change in place. `013` rebuilds `questions` and `wakes` by the same procedure,
  carrying every column, index and trigger, and creates the two machine triggers last because a
  trigger fires on `INSERT ... SELECT`.
- Times are UTC ISO-8601 text. A member's id is an opaque key, never parsed (a member made before slice 261 keeps the Context Forge project id it was registered under; a later one gets `uuid4().hex`). Every closed
  vocabulary is a `StrEnum` (`store/vocabulary.py`, `answering/values.py`), and a test
  pins each `CHECK` list to its enum.

## Tables

### `schema_meta`

| Column | Meaning |
|---|---|
| `id` | Always 1. |
| `version` | The schema version stamped by migrations. |

### `programs` (written by `set_up`, slice 222)

| Column | Meaning |
|---|---|
| `program_id` | Key; the program's name. |
| `concept_member` | Project id of the member holding the concept document; null when none. |
| `concept_path` | Repo-relative path of the concept document in that member; null when none. |
| `registered_at`, `updated_at` | UTC times; `updated_at` moves only when a stored value changes. |

`concept_member` and `concept_path` are both null or both set (a `CHECK`).
`concept_member` must be a member of this program; that is checked in code, because
a foreign key would be circular.

### `members` (`set_up`)

| Column | Meaning |
|---|---|
| `project_id` | Key; the member's id, an opaque text key that is never parsed (slice 261, D1). A member that existed before migration `012` keeps the Context Forge project id it was registered under; a later one gets `uuid4().hex`. A member belongs to one program. |
| `program_id` | The program. `UNIQUE (program_id, project_id)` backs the pair foreign keys. |
| `rules_paths` | JSON array of repo-relative rules paths (a `*` allowed in the last segment). |
| `authorize_allow` | JSON array of config item keys taken off this member's not-authorized list. |
| `authorize_deny` | JSON array of config item keys put on it. |
| `registered_at`, `updated_at` | As above. |
| `removed_at` | Migration `003`. UTC time `set_up` removed the member; null for an active one. The row stays, because the member's questions and answers reference it and are the record. |
| `rules_from` | Migration `005`. `named` or `config_default` (`RulesFrom`, a `CHECK`), `NOT NULL`, default `named`. `named` means the member's own `rules_paths` entries (an empty list is a valid named choice: no rules); `config_default` means the config's `default_rules_paths`, read at answering time, and the stored `rules_paths` is unused (written as `[]`). Existing members stay `named`. |
| `wake_command` | Migration `009`, slice 244. Retired by slice 261: the command lives on the member's checkouts (`checkouts.wake_command`). The naming step copies a command to the member's checkout and sets this column to null, and nothing writes it afterwards. Kept as a column because the migration cannot move it (a checkout needs a machine, and the local opener makes that). |
| `name` | Migration `012`, slice 261. Text with `COLLATE NOCASE`, matching `[A-Za-z0-9][A-Za-z0-9._-]*`, at most 64 characters. Null only on a row from before the migration, until the naming step runs (`operations.naming`, or `name_by_id` on a hub store); a `BEFORE INSERT` trigger refuses a new member with no name, so only old rows can be unnamed. A partial unique index over active members (`removed_at IS NULL`) makes a name unique among them, in any case; a removed member keeps its name for display and does not hold it against anyone. |
| `origin` | Migration `012`. Text, nullable: the reduced remote (`host[:port]/path`, lower case, no scheme, user or password, no trailing slash or `.git`) that says which repo this is, so checkouts on other machines attach to one member. Null when the repo has none. A partial unique index over active members keeps two from sharing one; any number may have none. |

### `dependency_pairs` (`set_up`; read by slice 227)

| Column | Meaning |
|---|---|
| `program_id` | The program both ends belong to. |
| `provider_id`, `consumer_id` | Key (together). Both reference `members (program_id, project_id)`, so a pair cannot cross programs. `CHECK (provider_id <> consumer_id)`. |
| `consumed` | `from_source` or `from_release` (`ConsumedMode`): which of the provider's reports the consumer sees. |
| `registered_at`, `updated_at` | As above. |

### `releases` (written by slice 227)

| Column | Meaning |
|---|---|
| `seq` | Key; autoincrement, so a withdrawn commit that is reported again gets a higher `seq`. |
| `member_id` | The reporting member. `UNIQUE (member_id, commit_sha)`: one row per commit a member reported. |
| `commit_sha` | The reported commit: the full hash, lower-case (40 or 64 hex characters). |
| `version` | The release tag; null until the report has one. |
| `changed`, `touched` | What the report says changed (text) and what that touched (`touched` is a JSON array of strings, in the order given, without duplicates). |
| `reported_at` | When the report was made, or last corrected. |
| `versioned_at` | When the report got its version, or was last corrected while holding one; null while `version` is null. |

Written only by `report_release`, one `BEGIN IMMEDIATE` transaction per call; `changes`
only reads. A report is identified by its member and commit:

- A new commit inserts a row (`reported_at` now; `versioned_at` now when a version is
  given). A repeat of the commit is `unchanged` whatever its wording: the stored text
  is kept.
- A version that is new, or given to a row with none, sets `version` and `versioned_at`
  and replaces `changed` and `touched`; `reported_at` and `seq` do not move, so a
  `from_source` reader does not see the commit twice.
- A correction replaces `changed` and `touched` (and `version`, if given) and moves
  `reported_at` to now, and `versioned_at` to now when the row has a version, so readers
  whose starting time predates it see it again.
- Withdrawal deletes the row; it is the explicit cancel for a registered member's report.
- No read record is kept: `changes` takes its starting time from the caller, so
  there is no per-reader position to clean up.
- A removed member's rows stay as the record (228 D8) and no cleanup runs. The table is
  bounded by what agents report: one small row per commit a member reported, written by
  an explicit call, never by a loop.

The only index is the one behind `UNIQUE (member_id, commit_sha)`. Both reads filter by
`member_id` first, which that index serves, and then by time within one member's rows,
which is one small row per reported commit; adding a time index would need a migration
for no measured need.

What a consumer sees follows its pair's `consumed`: `from_source` reads `reported_at`,
`from_release` reads `versioned_at` and only rows with a `version`.

### `questions` (written by slice 223)

| Column | Meaning |
|---|---|
| `run_id`, `paused_at` | Key (together). `paused_at` is Squadron's value verbatim. |
| `member_id` | The member whose run paused. |
| `question` | The question text. |
| `checkout` | The checkout the run paused in. |
| `state` | `claimed`, `answered`, `waiting_on_pm`, `closed` or `waiting_on_request` (`QuestionState`; `closed` from migration `003`, `waiting_on_request` from `008`). A `CHECK` requires `request_id` on a `waiting_on_request` row. |
| `answering_run_id` | The answering run, null before one starts. |
| `waiting_reason` | Why the PM must answer, a `DeclineReason`; unconstrained in SQL, checked in code. Written with the `waiting_on_pm` insert or move; a PM answer does not clear it. |
| `claimed_at`, `updated_at` | UTC times. A held row keeps the hold time in `claimed_at` while it waits; its claim (slice 242) resets both to the claim time, so the dead-claim rules age the claim from then. |
| `slice_label` | Migration `002`. The slice label (`<index> <name>`, or `none`) the passages were gathered for; reused on precedent passages. Written with the claim insert by `handle_pause`; null when the question waited before context was gathered. |
| `source_commit` | Migration `002`. The commit the passages were read at. Written with the claim insert. |
| `passages` | Migration `002`. JSON array of passage references (`id`, `source`, `question_id`, `date`). Written with the claim insert; rewritten by `replace_claim` for a dead claim. |
| `waiting_detail` | Migration `002`. Bounded detail for `waiting_reason`. Written with `waiting_reason`. |
| `evidence` | Migration `002`. JSON object: `proposed_answer`, `cited`, `verdict`, `reason`, as far as the answering run got. Written when the claim settles, to `answered` or `waiting_on_pm`. |

| `closed_reason` | Migration `003`. Null, or `dismissed`, `run_moved_on`, `run_gone` or `machine_removed` (`ClosedReason`, a `CHECK`; `machine_removed` from migration `013`, written by `rm-machine`). Written with the move to `closed` by `dismiss`, `handle_pause` and `status`; kept as history if `answer` later reopens the question. |
| `closed_detail` | Migration `003`. The dismissal reason, or the run's state when the sweep closed it. Written with `closed_reason`. |
| `closed_at` | Migration `003`. UTC time the question was closed. Written with `closed_reason`. |
| `request_id` | Migration `008`. The request a held question waits on; null for any other question. Written by `handle_pause` with the held insert and never changed, so the row keeps it through every later state. No foreign key to `messages`, because 240's sweep prunes terminal requests by age. |
| `start_attempted_at` | Migration `008`. UTC time `claim_work` last started `handle_pause` for a held row or a stale claim; null before the first start. Written by `claim_work` as a compare-and-set on the state and the value it read, so two concurrent callers never both start one row; it leaves `updated_at` alone, because `updated_at` is the close compare-and-set's guard. It also adds one to `start_count`. |
| `machine_id` | Migration `013`. The machine the run paused on, references `machines`. Bound from the store's acting machine at insert and never changed; set to null by `rm-machine`, which closes the row. A `BEFORE INSERT` trigger (`questions_machine_required`) refuses a null. The local opener gives a row from before `013` the machine `local`. Index `(machine_id, state)`. |
| `start_count` | Migration `013`. How many automatic starts `claim_work` has handed out for the row; at the cap the row moves to `waiting_on_pm` with the reason `starts_exhausted`. Never reset. |

### `answers` (written by slice 223; counted by slice 224)

Append-only, so an automatic answer and a later PM answer are both kept.

| Column | Meaning |
|---|---|
| `seq` | Key; autoincrement. What the `decisions` marker counts. |
| `run_id`, `paused_at` | The question answered. |
| `answered_by` | `answerer` or `pm` (`AnsweredBy`). |
| `answer` | The answer text. |
| `recorded_at` | UTC time. |
| `resume_outcome` | Null, or `resumed`, `refused` or `not_delivered` (`ResumeOutcome`). Written by the shared resume; `resumed` and `not_delivered` are never overwritten, `refused` may be. |
| `cited` | Migration `002`. JSON array of the passage ids an automatic answer cites; null for a PM answer. Written with the `answerer` row. |
| `resume_detail` | Migration `002`. Refusal or not-delivered detail. Written with `resume_outcome`. |
| `resume_log` | Migration `002`. Path of the resume's stdout log. Written with `resume_outcome`. The file may have been pruned (see below); the path stays as history and a missing file is not an error. |
| `resume_at` | Migration `002`. UTC time the resume outcome was recorded. Written with `resume_outcome`. |
| `retracted_at` | Migration `003`. UTC time a PM answer was retracted; null otherwise. Written once by `retract`. The answer stays delivered and stays in `decisions`. |
| `retract_reason` | Migration `003`. Why it was retracted. Written with `retracted_at`. |
| `resume_started_at` | Migration `003`. UTC time just before a resume was spawned, retries included, so the sweep never marks an answer `not_delivered` under a resume in flight. Written by the shared resume. |
| `resume_claim_id` | Migration `013`. The id of the attempt that holds the resume claim; null when free. Set with `resume_started_at` by the one claim statement; cleared by `record_resume` only when it is the caller's. |
| `resume_start_count` | Migration `013`. How many resumes `claim_work` has handed out for the answer; at the cap the outcome is recorded `refused`. |
| `via` | Migration `004`. `cli` or `mcp` (`Door`, a `CHECK`): the door that carried a PM answer. Null for an answer from before `004` and for the answerer's automatic answers, which no door carries; read as "no door", never a guessed one. Written with the `pm` row by `answer`. |

### `messages` (migration `006`, slice 240)

One row per request or note. 240 wrote only requests; `note` rows and `to_program` were
in the table already (SQLite cannot widen a `CHECK` in place), so 243 has no migration.
Notes are written by `send` and, for a release report, by `report_release`.

| Column | Meaning |
|---|---|
| `message_id` | Key; the id the sender chose (1 to 64 characters, `[A-Za-z0-9][A-Za-z0-9._-]*`). |
| `kind` | `request` or `note` (`MessageKind`, a `CHECK`). |
| `from_member` | The sender's project id; references `members`. |
| `to_member` | The addressee's project id; references `members`. Set for a request and a direct note; null for a program note. |
| `to_program` | References `programs`; set for a program note, null otherwise. |
| `parent_id` | The request this one serves, as given; not a foreign key, because a terminal parent can be pruned while a child is open. |
| `depth` | At least 1: the parent's depth plus one, or 1 for a root; always 1 for a note. Stored at send so pruning never changes it. |
| `subject`, `body` | The sender's text. |
| `state` | `open`, `accepted`, `done`, `declined`, `cancelled` or `expired` (`RequestState`, a `CHECK`); null for a note. Read through `effective_state`, which shows an `open` request past `expires_at` as `expired` before the sweep records it. |
| `result`, `result_commit`, `result_version` | The `done` reply's text, commit and version. |
| `reason` | The decline text, or the cancel reason (`member_removed` when a member's removal cancelled it). |
| `accepted_at` | UTC time of the accept. |
| `created_at`, `state_changed_at` | UTC times; `state_changed_at` moves with every state change (an expiry records the sweep's own time); a note's equals `created_at`. |
| `expires_at` | `created_at` plus `request_open_ttl_hours`, fixed at send, so a config change never moves it; null for a note. |
| `wake_wanted_at` | Migration `013`. UTC time `send` wanted a wake for this open request, on the store's own clock; null when it did not. A mark gets one wake. |

Table `CHECK`s: a request has `to_member`, a state and `expires_at` and no `to_program`;
a note has exactly one of `to_member` and `to_program`, and no state or `expires_at`.
A note's id is the sender's, or `release:` and a random hex string for a release note
(a sender's id cannot hold a colon, so it cannot start with `release:`).
`depth` is at least 1. Indexes: `(to_member, state)`, `(from_member, state)`,
`(parent_id)` and `(state, expires_at)`.

### `deliveries` (migration `006`)

| Column | Meaning |
|---|---|
| `seq` | Key; autoincrement, so `sqlite_sequence` holds the highest number ever assigned even after rows are pruned. `inbox` returns it as `as_of_seq`. |
| `member_id` | The member the delivery is for; references `members`. |
| `message_id` | The request it concerns; references `messages`. |
| `event` | `sent`, `accepted`, `declined`, `done`, `cancelled` or `expired` (`DeliveryEvent`, a `CHECK`). |
| `created_at` | UTC time. |

Indexes: `(member_id, seq)`, and `(message_id)` for the prune's delete of a request's
deliveries and the foreign-key check.

### `message_rejections` (migration `006`)

A `send`, `reply` or `cancel` rejected once its caller was known leaves one row, so a
call that cannot be applied does not vanish. `list` and `status` show a member's rows
under it.

| Column | Meaning |
|---|---|
| `id` | Key. |
| `member_id` | The caller; references `members`. |
| `operation` | `send`, `reply` or `cancel` (an `OperationName` value; no `CHECK`). |
| `to_ref` | The recipient as given; `send` only. |
| `message_id`, `parent_id` | The request id and parent as given; null when the document gave none. |
| `code` | A `RejectCode` value; no `CHECK`, so a new code is not a migration. |
| `detail` | The reason text. |
| `created_at` | UTC time. |

Index: `(created_at)`.

### `sessions` (migration `007`, slice 241)

One row per serving `amoeba-mcp` whose working directory resolved to a member. Written
by that server's heartbeat; see "Sessions" below for the stale rule, the prune and push
confirmation.

| Column | Meaning |
|---|---|
| `session_id` | Key; a random hex id the server makes once at start. |
| `member_id` | The member it serves; references `members`. |
| `client` | The client's `clientInfo.name` when it matches `[A-Za-z0-9._ -]{1,64}`, otherwise `unrecognized`. Shown by `list`, so never free text. |
| `directory` | The server process's working directory. |
| `started_at` | UTC time the server started; kept when a pruned row is re-created. |
| `heartbeat_at` | UTC time of the last beat. |
| `push_confirmed_at` | UTC time the session's agent first answered a channel event with an `inbox` call; null until then. |

Indexes: `(member_id)` and `(heartbeat_at)`. No `CHECK` list.

### `wakes` (migration `009`, slice 244)

One row per wake of a member's `wake_command`, kept after the wake ends. The claim in
`send` writes the row (`claim_wake`); the `amoeba wake-run` wrapper writes `command_pid`
and the end fields, and `wake_after_send` writes them for a start failure it sees
itself. See "Wakes and who writes them" below for the live rule, the limit and the
retention.

| Column | Meaning |
|---|---|
| `wake_id` | Key; `uuid4().hex`, so a restored store never collides with an existing log file. |
| `member_id` | The member woken; references `members`. |
| `directory` | The checkout the command runs in (Context Forge's `projectPath`); null only for a `start_failed` row Context Forge gave no path for. |
| `command` | The member's `wake_command` as claimed, so a later edit changes nothing running. |
| `started_at` | UTC time of the claim. |
| `deadline_at` | `started_at` plus `wake_timeout_seconds`, fixed at the claim. |
| `log_stem` | The log files' path without the `.stdout.log` and `.stderr.log` suffix; null when nothing was started. |
| `command_pid` | The command's pid, also its process group id; written by the wrapper right after the command starts, null until then. It is a compare-and-set: only the first run of a wake records one, and a second `wake-run` of the same id stops its own command. Shown by `list` for an overdue row; Amoeba never signals it. |
| `ended_at` | UTC time the wake was recorded as ended; null while it has not. |
| `outcome` | `WakeOutcome` (a `CHECK`): `exited` (the command ran and exited), `timed_out` (it ran past `deadline_at` and its group was stopped), `start_failed` (it could not be started), `wrapper_failed` (the wrapper hit an unexpected error after the start), `machine_removed` (migration `013`: `rm-machine` ended a row of the removed machine). Null until `ended_at` is set. |
| `exit_code` | The command's exit code; set only for `exited`. |
| `machine_id` | Migration `013`. The machine the wake was claimed for, references `machines`; bound from the acting machine by `claim_wake`. Null after `rm-machine`, which also clears `log_stem`. A `BEFORE INSERT` trigger (`wakes_machine_required`) refuses a null. Index `(machine_id)`. |
| `detail` | Why, for a failure, never the wake command's text: from the wrapper an exception class and its OS message (`wake_detail`, the one place it makes one); for a start failure `wake_after_send` sees, the launch error's or missing-script error's own text, which names a path. |

`ended_at` and `outcome` are both null or both set, and `exit_code` is set only for
`exited` (table `CHECK`s). Indexes: `(member_id, started_at)` and `(started_at)`.

### `standing_answers` (migration `010`, slice 230)

One row per ruling the PM gave ahead of time, in the PM's own words, with the members it
reaches. A row is active until it is withdrawn, and withdrawn is terminal. Rows are
never deleted. See "Standing answers and who writes them" below.

| Column | Meaning |
|---|---|
| `id` | Key; `AUTOINCREMENT`, so an id is never reused. A delivered answer cites the row as `standing:<id>`. |
| `text` | The PM's words, situation and ruling in one field, so the agent never rewrites what the PM said. Never edited: a changed ruling is a withdraw and a new row. Not blank (a `CHECK`). |
| `reach` | `StandingReach` (a `CHECK`): `all` (every member), `program` (every member of `program_id`), `member` (the one member `member_id`). |
| `program_id` | The program reached; set only for reach `program`; references `programs`. |
| `member_id` | The member reached, by project id; set only for reach `member`; references `members`. |
| `given_at` | UTC time the ruling was given; the date of its passage, so a newer ruling wins under the prompts' "later date wins" rule. |
| `withdrawn_at` | UTC time it was withdrawn; null while active. |
| `withdraw_reason` | Why: the text given to `withdraw`, or `member_removed` when `rm` withdrew it. Null while active. |

The reach `CHECK`s tie `program_id` and `member_id` to the reach, and `withdrawn_at` and
`withdraw_reason` are both null or both set. No index: the table grows only with the
PM's rulings.

### `owners` (migration `011`, slice 260)

The owner of every record. The migration inserts exactly one row, named `pm`; nothing
else writes this table, and `the_owner` fails unless it holds exactly one row.

| Column | Meaning |
|---|---|
| `owner_id` | Key; `AUTOINCREMENT`. |
| `name` | Unique. `pm` for the one row. |
| `created_at` | UTC time the row was made (the migration's time). |

### `machines` (migration `011`)

One row per machine that acts on the store: `local` for a store opened on a laptop, and
one per machine invited with `amoeba hub invite` on a hub. The migration makes none.

| Column | Meaning |
|---|---|
| `machine_id` | Key; `AUTOINCREMENT`, so a later rename touches one row. |
| `name` | Unique; `[a-z0-9][a-z0-9._-]*`, at most 64 characters. |
| `owner_id` | The owner; not null; references `owners`. |
| `token_hash` | SHA-256 of the machine's token, hex; unique; null for a machine with no token (`local`). The token itself is never stored. |
| `created_at` | UTC time the machine was made. |
| `last_called_at` | UTC time of its last call to the hub; null until one. |
| `client_version` | The package version its last call reported; null until one. |

### `call_results` (migration `011`)

The kept result of a writing call, so a call repeated with the same id applies once.
Written in the same transaction as the operation, and deleted by the next call once
older than `CALL_RESULT_LIFETIME_SECONDS`, or with its machine by `rm-machine`.

| Column | Meaning |
|---|---|
| `machine_id` | The calling machine; references `machines`. Part of the key. |
| `call_id` | The client's call id. Part of the key, so another machine's same id is a different row. |
| `operation` | The served operation's name. |
| `request_hash` | SHA-256 of the request body, hex; a repeat with another body is refused as `call_id_reused`. |
| `reply` | The reply body, as sent. |
| `recorded_at` | UTC time kept; the index `(recorded_at)` serves the expiry delete. |

### `closed_mark` (migration `011`)

At most one row (a `CHECK` on `mark_key`), empty in a store in use. When a row is
there, every write transaction rolls back and raises `LocalStoreClosedError` naming the
hub. Written by `join --set-aside-local`, cleared by `leave`.

| Column | Meaning |
|---|---|
| `mark_key` | Always 1. |
| `hub_address` | The hub's `host:port` the store went to. |
| `closed_at` | UTC time the mark was written. |

### `checkouts` (migration `012`, slice 261)

One copy of a repo on one machine. A member has one per machine and clone, and all of
them share the member's inbox. Written by `add`, deleted by `rm`, `rm --checkout` and
`amoeba hub rm-machine`.

| Column | Meaning |
|---|---|
| `checkout_id` | Key; `AUTOINCREMENT`. Order by `added_at`, then this, gives "the one added first". |
| `member_id` | The member; not null; references `members.project_id`. Indexed. |
| `machine_id` | The machine the copy is on; not null; references `machines`. |
| `cf_project_id` | The Context Forge project id that machine knows the repo by; not null. `UNIQUE (machine_id, cf_project_id)`: one project on one machine is one checkout of one member. |
| `path` | The directory the checkout was registered at; not null; set when the row is made and never changed by `add` (a registered worktree has the same project id and its own directory, so updating it would move the checkout between worktrees). A moved repo is `rm --checkout <old path>`, then `add` in the new place. |
| `wake_command` | Text, nullable: the command a wake starts here (slice 244, moved from `members.wake_command`). Null means no wake. Set by `add --wake-command` in this checkout and cleared by `--no-wake-command`; `list members` shows it in plain text, so it holds no secret. |
| `owner_id` | The owner; references `owners`; a `BEFORE INSERT` trigger (`checkouts_owner_required`) aborts when it is null, as on the other record tables. |
| `added_at`, `updated_at` | UTC times. |

### `owner_id` and `sessions.machine_id` (migration `011`)

`owner_id` is on the twelve tables that hold records: `programs`, `members`,
`dependency_pairs`, `releases`, `questions`, `answers`, `standing_answers`, `messages`,
`deliveries`, `message_rejections`, `sessions` and `wakes`. It references `owners` and is
set to the one owner on every row that existed. A column cannot be added `NOT NULL`
without a default, and a default owner would be a silent fallback, so each table has a
`BEFORE INSERT` trigger (`<table>_owner_required`) that aborts when `owner_id` is null.
Every insert binds it from the store's acting machine. A store with no acting machine
fails its first insert with `NoActingMachineError`.

Migration `012` adds `checkouts` with the same trigger (`checkouts_owner_required`), so
the owner is on thirteen tables.

Migration `013` adds `machine_id` to `questions` and `wakes`, with the same kind of trigger
(`questions_machine_required`, `wakes_machine_required`) and an index on each table
(`questions(machine_id, state)`, `wakes(machine_id)`). Both inserts bind it from the acting
machine. A row with no machine is never work, and an answer to such a question is not delivered.

`sessions.machine_id` references `machines`, with the same kind of trigger
(`sessions_machine_required`). Rows written before the migration keep a null machine;
the heartbeat prune removes them.

### `pm_marker` (moved by slice 224)

| Column | Meaning |
|---|---|
| `id` | Always 1; the table holds one row. |
| `last_seen_seq` | The `answers.seq` the PM has seen; created at 0, meaning nothing seen. |

## Why each column exists

The schema holds no state that Context Forge or Squadron already says; every column is
one of eight things. `tests/store/test_schema_holds_no_mirrored_state.py` pins the same
columns under the same reasons, so a new column fails it until it is listed in both
places and its reason is stated.

A checkout's Context Forge id and path, and a member's `origin`, are the keys Amoeba
recognises a caller and a repo by. They are taken when `add` runs in that checkout and
are never read as Context Forge's or git's current state.

- **record**: what happened, written once when it did and never updated to follow anything else. A column here is never read as current state: `questions.checkout` is where a pause ran and `questions.slice_label` the slice its passages were gathered for, not where the member is or what slice it is on. Columns: `answers.answer`, `answers.answered_by`, `answers.cited`, `answers.paused_at`, `answers.recorded_at`, `answers.resume_at`, `answers.resume_detail`, `answers.resume_log`, `answers.resume_outcome`, `answers.resume_claim_id`, `answers.resume_start_count`, `answers.resume_started_at`, `answers.retract_reason`, `answers.retracted_at`, `answers.run_id`, `answers.seq`, `answers.via`, `questions.answering_run_id`, `questions.checkout`, `questions.claimed_at`, `questions.closed_at`, `questions.closed_detail`, `questions.closed_reason`, `questions.evidence`, `questions.member_id`, `questions.passages`, `questions.paused_at`, `questions.question`, `questions.request_id`, `questions.run_id`, `questions.slice_label`, `questions.source_commit`, `questions.machine_id`, `questions.start_attempted_at`, `questions.start_count`, `questions.state`, `questions.updated_at`, `questions.waiting_detail`, `questions.waiting_reason`, `releases.changed`, `releases.commit_sha`, `releases.member_id`, `releases.reported_at`, `releases.seq`, `releases.touched`, `releases.version`, `releases.versioned_at`.

- **membership**: who is in a program, the PM's registration and the one thing only Amoeba knows; a checkout is the registration of one copy of a repo on one machine. Columns: `checkouts.added_at`, `checkouts.cf_project_id`, `checkouts.checkout_id`, `checkouts.machine_id`, `checkouts.member_id`, `checkouts.path`, `checkouts.updated_at`, `dependency_pairs.consumer_id`, `dependency_pairs.program_id`, `dependency_pairs.provider_id`, `dependency_pairs.registered_at`, `dependency_pairs.updated_at`, `members.name`, `members.origin`, `members.program_id`, `members.project_id`, `members.registered_at`, `members.removed_at`, `members.updated_at`, `programs.program_id`, `programs.registered_at`, `programs.updated_at`.

- **settings**: what the PM chose for a program or member, and the store's own schema version. Columns: `checkouts.wake_command`, `dependency_pairs.consumed`, `members.authorize_allow`, `members.authorize_deny`, `members.rules_from`, `members.rules_paths`, `members.wake_command`, `programs.concept_member`, `programs.concept_path`, `schema_meta.id`, `schema_meta.version`.

- **messages**: what agents said to each other and where each request stands. Amoeba is the only place this exists, and a request's state is Amoeba's own, never read from Context Forge or Squadron. Columns: `deliveries.created_at`, `deliveries.event`, `deliveries.member_id`, `deliveries.message_id`, `deliveries.seq`, `message_rejections.code`, `message_rejections.created_at`, `message_rejections.detail`, `message_rejections.id`, `message_rejections.member_id`, `message_rejections.message_id`, `message_rejections.operation`, `message_rejections.parent_id`, `message_rejections.to_ref`, `messages.accepted_at`, `messages.body`, `messages.created_at`, `messages.depth`, `messages.expires_at`, `messages.from_member`, `messages.kind`, `messages.message_id`, `messages.parent_id`, `messages.reason`, `messages.result`, `messages.result_commit`, `messages.result_version`, `messages.state`, `messages.state_changed_at`, `messages.subject`, `messages.to_member`, `messages.to_program`, `messages.wake_wanted_at`.

- **waking**: what Amoeba started with nobody present and how each start ended. Amoeba is the only place this exists, and a wake's end is what its own wrapper recorded. Columns: `wakes.command`, `wakes.command_pid`, `wakes.deadline_at`, `wakes.detail`, `wakes.directory`, `wakes.ended_at`, `wakes.exit_code`, `wakes.log_stem`, `wakes.machine_id`, `wakes.member_id`, `wakes.outcome`, `wakes.started_at`, `wakes.wake_id`.

- **rulings**: the rulings the PM gave ahead of time and whether each still holds. Amoeba is the only place they exist. Columns: `standing_answers.given_at`, `standing_answers.id`, `standing_answers.member_id`, `standing_answers.program_id`, `standing_answers.reach`, `standing_answers.text`, `standing_answers.withdraw_reason`, `standing_answers.withdrawn_at`.

- **marker**: how far the PM has read the decisions. Columns: `pm_marker.id`, `pm_marker.last_seen_seq`.

- **ownership**: who owns each record and which machine wrote it, the machines that may call the hub, and the kept results and closed mark of the door (slice 260). Amoeba is the only place this exists. Columns: `answers.owner_id`, `call_results.call_id`, `call_results.machine_id`, `call_results.operation`, `call_results.recorded_at`, `call_results.reply`, `call_results.request_hash`, `checkouts.owner_id`, `closed_mark.closed_at`, `closed_mark.hub_address`, `closed_mark.mark_key`, `deliveries.owner_id`, `dependency_pairs.owner_id`, `machines.client_version`, `machines.created_at`, `machines.last_called_at`, `machines.machine_id`, `machines.name`, `machines.owner_id`, `machines.token_hash`, `members.owner_id`, `message_rejections.owner_id`, `messages.owner_id`, `owners.created_at`, `owners.name`, `owners.owner_id`, `programs.owner_id`, `questions.owner_id`, `releases.owner_id`, `sessions.machine_id`, `sessions.owner_id`, `standing_answers.owner_id`, `wakes.owner_id`.

- **presence**: which `amoeba-mcp` processes are serving now, as their own heartbeats say. Nothing else knows this, and a row that stops beating stops counting. Columns: `sessions.client`, `sessions.directory`, `sessions.heartbeat_at`, `sessions.member_id`, `sessions.push_confirmed_at`, `sessions.session_id`, `sessions.started_at`.

## Question lifecycle and who writes it (slices 223 and 228)

A question moves `claimed` to `answered` or `waiting_on_pm`; a PM answer moves it to
`answered` from any state, `closed` included. A question marked with a request its
repo sent starts `waiting_on_request` instead (slice 242) and leaves it for `claimed`
or `waiting_on_pm` by the request's state. It is **open** while it is `claimed`,
`waiting_on_pm`, `waiting_on_request`, or `answered` with its latest answer unresumed
(`resume_outcome` null or `refused`). Every move out of `claimed` names the claim it holds
(`answering_run_id`), and every close, dismissal and retraction is a compare-and-set in
one short write transaction, so a PM answer made meanwhile wins.

| Operation | Writes |
|---|---|
| `handle_pause`, a new question | one `questions` row, inserted in one transaction: `claimed` with `answering_run_id`, `slice_label`, `source_commit` and `passages`, or `waiting_on_pm` with `waiting_reason` and `waiting_detail` (and the context columns when the failure came after the context was gathered) |
| `handle_pause`, a new question marked with a request (slice 242) | `waiting_on_request` with `request_id`, through the held insert; a marker that names no request this member sent gives `waiting_on_pm` with `request_unknown` instead |
| `handle_pause`, a held question | the request `done`: `claimed` through the held claim (`answering_run_id`, `passages` with the request's `request_result` passage, `slice_label`, `source_commit`, and `claimed_at` and `updated_at` reset to now), then settled as any claim. `declined`, `cancelled`, `expired` or no longer stored: `waiting_on_pm` with `request_declined`, `request_cancelled`, `request_expired` or `request_unknown` and the request's reason as `waiting_detail`. `open` or `accepted`: nothing |
| `claim_work`, in the after-step of any call but an MCP `answer` (slices 242, 262) | `start_attempted_at` and `start_count` on each held row whose request has ended and each stale claim, `resume_claim_id`, `resume_started_at` and `resume_start_count` on each answer to resume, and a `wakes` row for each wake due; at most `MAX_WORK_PER_CLAIM` items per claim; the move itself is the started command's. At `MAX_AUTOMATIC_STARTS` a question moves to `waiting_on_pm` as `starts_exhausted` and an answer is recorded `refused` |
| `handle_pause`, settling an answering run | `answered`: `questions.evidence` and an `answerer` `answers` row with `cited`, in one transaction through the answer gate. Otherwise `waiting_on_pm`: `waiting_reason`, `waiting_detail`, `evidence` |
| `handle_pause`, a dead claim | `replace_claim` (`answering_run_id` and `passages`, for a claimant that died before it started), or `waiting_on_pm` with `answering_run_stalled` |
| `answer` | a `pm` `answers` row with `via` (the door that carried the call) and `answered`, in one transaction; `waiting_reason`, `waiting_detail` and any `closed_*` columns are not cleared |
| the shared resume (both) | `answers.resume_started_at` just before every spawn, then `resume_outcome`, `resume_detail`, `resume_log`, `resume_at` |
| `dismiss` | `closed` with `closed_reason` `dismissed`, `closed_detail` (the PM's reason) and `closed_at`, from `claimed`, `waiting_on_pm`, `waiting_on_request` or `answered` with an unresumed answer; that answer becomes `not_delivered` (`dismissed`) in the same transaction |
| `retract` | `answers.retracted_at` and `retract_reason` on a PM answer, once |
| the close sweep: `handle_pause` (that run's rows at other pauses), `status` (open rows of the members in scope) | `closed` with `closed_reason` `run_moved_on` or `run_gone` and the run's state as `closed_detail`; a claim only once its `updated_at` is `pause_claim_seconds` old; a `refused` answer whose newest sign of life is `resume_claim_seconds` old becomes `not_delivered`, and an answer with no outcome is left to its resume attempt (slice 262) |
| `set_up` removal | `members.removed_at`; the member's `dependency_pairs` rows are deleted |

How each state ends with nobody editing a file: `claimed` settles, or is replaced or
swept; `waiting_on_pm` is answered, dismissed or swept; `waiting_on_request` is
resumed (its request `done` and the answer passes), moves to `waiting_on_pm` (its
request ended without a result, or the answer did not pass), or is answered by the PM,
dismissed or swept, and `claim_work` starts its `handle_pause` once the request
ends; `answered` unresumed is resumed,
dismissed or swept; `closed` is terminal and `answer` reopens it; a retracted answer is
terminal and a new PM answer replaces it as precedent. A PM answer resets the answer
limit, which counts `answerer` answers after the run's newest `pm` answer (a retracted
one still counts as the last). Precedent is each question's newest PM answer, left out
when retracted or when the question is `closed`; an older answer is not revived.

A wake (slice 244) ends by its wrapper recording `exited`, `timed_out`, `start_failed` or
`wrapper_failed`, or `wake_after_send` recording `start_failed`; a row whose wrapper was
killed stays unended, stops counting as live at its `deadline_at` and shows as overdue,
and every row, ended or not, is deleted by the sweep once `started_at` is past
`prune_after_days`. The daily limit exits by the clock alone: a row older than 24 hours
no longer counts, so the next `send` wakes again.

Pruning (`prune_after_days`, run by `handle_pause` and `status`) removes only files:
answering scratch and logs of settled or orphaned answering runs, resume logs of runs
with no open question, calls-log day files, and other old files under `logs/`. Anything
tied to an open question is kept at any age. Store rows are never pruned: they are the
record, and the sweep, `dismiss` and set-up removal bound how many are open.

A prune walks the trees at most once an hour: it records the walk in the mtime of one
empty file, `<state home>/.last-prune`, and a call within the hour does nothing.
Deleting the file only makes the next call walk.

`questions.waiting_reason` holds a `DeclineReason` (`answering/values.py`); SQL does not
constrain it. The values `handle_pause` writes: `answer_limit_reached`,
`reserved_term`, `sources_too_large`, `sources_missing`, `sources_unreadable`,
`answering_launch_failed`, `answering_run_failed`, `answering_run_stalled`,
`answering_cost_cap`, `answering_run_orphaned`, `artifact_missing`,
`artifact_malformed`, `answerer_declined`, `uncited`, `unknown_citation`,
`check_said_no`, and for a held question (slice 242) `request_declined`,
`request_cancelled`, `request_expired` and `request_unknown`, and `claim_work` (slice 262)
writes `starts_exhausted` when a row has had its automatic starts. The remaining members (`node_already_blocked`, `question_missing`,
`answerer_not_configured`, `no_answer_on_file`, `answer_discarded`) come from before the
cut and are not written.

An answer with `resume_outcome` null or `refused` is "answered, not resumed": the next
`handle_pause` for that question resumes with the latest answer and starts no answering
run. `resumed` and `not_delivered` are never overwritten.

## Request lifecycle and who writes it (slice 240)

A request is `open` when `send` stores it. `reply accept` makes it `accepted`; `done`,
`decline` and `cancel` end it. Expiry and the removal of a member end it too. Nothing
else changes a request's `state`, and every change goes through one writer that also
writes the deliveries, in the same transaction.

| Operation | Writes |
|---|---|
| `send` | one `messages` row (`open`, `depth` the parent's plus one, `expires_at` fixed from the config) and one `sent` delivery for the addressee; a resend of the same content changes nothing |
| `reply accept` | `accepted` and `accepted_at`, from `open`; a `accepted` delivery for the sender |
| `reply decline` | `declined` and `reason`, from `open` or `accepted`; a `declined` delivery for the sender |
| `reply done` | `done` with `result`, `result_commit` and `result_version`, from `accepted` only; a `done` delivery for the sender |
| `cancel` | `cancelled` and `reason`, from `open` or `accepted`; a `cancelled` delivery for the other party, or for both when the caller is neither or unknown |
| the sweep | `expired` for every `open` request at or past `expires_at`, with an `expired` delivery for each party; then the prune |
| `rm`, and `add`'s remove path | `cancelled` with `reason` `member_removed` for every `open` or `accepted` request the member sent or received, with a delivery for the party that is still a member |

A rejected `send`, `reply` or `cancel` writes one `message_rejections` row for its
caller, in the transaction that found the problem; two cases write none, because there
is no member to show it under: `not_a_member`, and a `cancel` by a caller that is
unknown.

**Effective state.** Every read goes through `effective_state`: an `open` request whose
`expires_at` has passed reads `expired`, whether or not the sweep has recorded it yet.
`inbox`, `list`, `status` and the checks of `reply` and `cancel` all use it, so nobody
sees a stale `open`. An `accepted` request never expires: the work can take days, and it
leaves by `done`, `decline` or `cancel`.

**Who is told.** A state change writes one delivery for each party except the actor, and
skips a party that is no longer an active member. So `accept`, `decline` and `done`
reach the sender, a sender's `cancel` reaches the addressee, and a `cancel` from a
session that is neither party, expiry and the removal cascade reach both (less a removed
member). `send` writes one delivery, for the addressee.

**The delivery sequence.** `deliveries.seq` is autoincrement. The highest number ever
assigned is read from `sqlite_sequence`, so it does not fall when the prune deletes
rows; `inbox` returns it as `as_of_seq`, read in the same transaction as the rows. A
caller keeps it and passes it as `since`; a `since` above it was never assigned and is
rejected `beyond_last_record`. Nothing is marked read: two readers with different
`since` values each see every delivery after their own.

**The sweep.** `send`, `reply` and `cancel` run it at the start of their own write
transaction. `status`, `list` and `handle-pause` run it through a wrapper that reads
first and takes the write lock only when something is due, so a quiet store is never
write-locked by a poll; a store that stays locked for the busy timeout is reported as a
problem in `status` and `list` (`sweep_problem`) and as a note in `handle-pause`'s
`detail`, and the call still returns.

**Caps.** Retention is also by count. `send` keeps a sender within 200 requests: before
storing a new one it deletes the sender's oldest terminal requests (deliveries first)
to make room, and is rejected `too_many_open` when all of them are `open` or `accepted`,
dropping nothing in that case. `send` and `report-release` keep a sender within 200
notes the same way, deleting its oldest notes (deliveries first) to make room and
refusing nothing. Each rejection row written trims its member to the newest
100 rows, and cuts the text the caller gave to 500 characters (`…` marks a cut). So the
rows `inbox`, `status` and `list` read are bounded by these caps times the members.

**Retention.** The prune deletes terminal requests (`done`, `declined`, `cancelled`,
`expired`) whose `state_changed_at` is older than `prune_after_days`, their deliveries
first, and `message_rejections` rows older than that. `open` and `accepted` requests are
never pruned: each has an exit. A pruned request's id sent again is a new request. A
member that is registered again keeps its retained history and starts with no live
request.

**Notes (slice 243).** A note is a `messages` row of kind `note` with no state and no
expiry and one `sent` delivery per recipient; nothing changes it afterwards. Its only
exit is the prune: the sweep deletes notes whose `created_at` is older than
`prune_after_days`, read or not, with their deliveries (the sweep's due check counts an
aged note, and `report_release` runs the due-checked sweep before its own write, so every
write that adds a note also prunes). The expire step never touches a note (null state),
the request prune never touches one, and removing a member leaves its notes and their
deliveries until the prune. A release note is written by `report_release` inside the
report's own transaction, for `recorded`, `versioned`, `corrected` and `withdrawn`: if a
note write fails the report rolls back with it.

Text from other repos is data: `subject`, `body`, `result` and `reason` are written by
other repos' agents and stored as given, with the limits of the CLI contract. Amoeba
never acts on a request's text.

## Machines, owners and who writes them (slice 260)

One owner, `pm`, is inserted by migration 011 and is the owner of every record. A
laptop's store has one machine, `local`, made by the local opener on its first open
(`open_state_store`, never by a migration, so a hub's store gets none). A hub's store
has one machine per `amoeba hub invite`, made or re-tokened in one transaction; the
hub opens its store with `open_hub_store`, which creates no machine and sets no acting
machine, and `handle_call` sets the calling machine for the one call.

| Writer | Writes |
|---|---|
| `open_state_store` | the machine `local` (once) |
| `amoeba hub invite` | a `machines` row, or a new `token_hash` on an existing one |
| every hub call | `machines.last_called_at` and `client_version` (the touch, committed even when the call is refused); for a writing call, a `call_results` row in the same transaction as the operation |
| the next call scope | deletes `call_results` rows older than `CALL_RESULT_LIFETIME_SECONDS` |
| `amoeba hub rm-machine` | deletes the machine's `sessions` and `call_results` rows and the machine |
| `amoeba join --set-aside-local` | the `closed_mark` row, on a plain connection, then the store is copied aside and the original deleted |
| `amoeba leave` | deletes the `closed_mark` row of the set-aside store, which is renamed back |

How each ends with nobody editing a file: a kept result is deleted by the next call
after its lifetime; a machine ends with `rm-machine` (and a token with a re-invite); the
closed mark ends with `leave`, or with the same `join` run again. Every write transaction
reads the mark first, so a store that is set aside takes no more writes
(`LocalStoreClosedError`).

## Sessions and who writes them (slice 241)

Only a serving `amoeba-mcp` writes `sessions`, and only for its own row, from its
heartbeat; `list` and `status` read it. Nothing else touches the table.

- **Register and beat are one statement.** An upsert on `session_id` sets
  `heartbeat_at` and `push_confirmed_at` and, on a first insert, the other columns, so a
  row re-created after a prune keeps the server's original `started_at`. The first beat
  runs when the client finishes the handshake, then every `session_heartbeat_seconds`.
- **The stale rule.** A row whose `heartbeat_at` is not newer than now minus
  `session_stale_seconds` counts as gone. It is one predicate (`LIVE_SESSION` in
  `store/sql_sessions.py`), used by the display read, the waking read and the prune, so a
  stale row is never shown whether or not it has been pruned.
- **The prune.** Each heartbeat deletes every member's stale rows before its upsert, in
  the same write transaction. `sweep` is not involved. The table therefore holds the
  live rows plus the rows of servers killed since the last beat of any server; with no
  server running those stay until one starts, each a few dozen bytes and never shown.
- **Push confirmation.** `push_confirmed_at` is null until the session's agent answers a
  channel event with an `inbox` call within 300 seconds; the server remembers that in
  memory and its next beat writes it. `live_member_ids` (what slice 244's waking reads)
  returns active members with a fresh row whose `push_confirmed_at` is set: the same
  members `status` shows with a confirmed session.
- **Cleanup.** A clean exit deletes the row (shielded, bounded by twice the busy
  timeout). A killed server's row goes stale and the next heartbeat of any server
  deletes it. A held store skips a beat; the next beat retries.
- A removed member's server keeps beating; its rows are never shown and never count for
  waking, because both reads keep active members only.

## Standing answers and who writes them (slice 230)

- **Give.** `standing` inserts a row with `given_at` now, after checking the program
  exists or the member is active. When an active row already has the same text, reach,
  program and member, nothing is written and that row's id is returned; the check and
  the insert are one write transaction, so a repeated call never makes a second row.
- **Withdraw.** `withdraw` sets `withdrawn_at` and `withdraw_reason` by compare-and-set
  on `withdrawn_at IS NULL`, so a second call changes nothing. Withdrawn is terminal:
  there is no un-withdraw, and giving the ruling again is a new row.
- **Removal.** `rm` of a member withdraws, in its own transaction, the member's active
  member-reach rows with reason `member_removed`. Program and `all` rows are untouched:
  `rm` never deletes a program.
- **The reach read.** Each question's context reads the active rows whose reach is
  `all`, the member's program, or the member, by the member's `project_id` and
  `program_id` bound as parameters, without reading `members`. It runs in the same read
  transaction as the PM precedent, before any claim is written.
- **Rows are kept.** No statement deletes from `standing_answers`. A delivered answer
  cites a standing answer by its passage, and the question's stored passage record
  keeps the `standing:<id>` source, its id and date, never the text, so the row is
  where that text stays readable. The table is bounded by the number of rulings the PM
  gives, as stored PM answers are.

## Wakes and who writes them (slice 244)

- **Live.** A wake is live while its row is not ended and `deadline_at` is later than
  now. It is one predicate (`LIVE_WAKE` in `store/sql_wakes.py`), used by the claim and
  every read. A row whose wrapper was killed stays unended, reads as gone once its
  deadline passes, and `list` shows it as overdue.
- **The day's count is read, not stored:** every row of the member with `started_at` in
  the last 24 hours, whatever its outcome (`WAKE_WINDOW`). The limit is
  `max_wakes_per_day`; a start failure counts like any wake.
- **Retention.** The sweep deletes every `wakes` row whose `started_at` is older than
  `prune_after_days`, ended or not, and the sweep's due check counts an aged row, so a
  quiet store is not write-locked by a poll. `logs/wake/` files are removed by
  `prune`'s rule for old logs. Removing a member leaves its rows to retention.

## Derivations the schema deliberately has no column for

- **An answering run's scratch directory.** It is `answering_dir() / <answering_run_id>`
  (slice 223, D6 and D12), so `questions.answering_run_id` is its only record. A later
  explicit call reads `answer.json` and `check.json` from the claim's
  `answering_run_id` alone. Do not add a path column: it would be a second source of
  truth.
- **Whether a member answers at all.** Answering has no per-member switch: program
  membership is the opt-in. A repo is opted in by being a member and having the pause
  hook configured, and opted out by not being registered or leaving the hook
  unconfigured. A pause from a directory that is not a member is skipped
  (`resolve_member` returns `NotInProgram`). There is no `answering_enabled` column and
  no `answerer:` section; a second switch would be a second place for the two to
  disagree.
