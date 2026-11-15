---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: The Amoeba store contract: the home, every table and column of the schema with its vocabulary and the operation that writes it, and the migration rule.
dateCreated: 20261109
dateUpdated: 20261112
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
  `003_question_lifecycle.sql`, `004_answer_via.sql`, `005_member_rules_from.sql`, `006_messages.sql`), shipped in the wheel. `EXPECTED_SCHEMA_VERSION` equals the highest number (6).
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
- Times are UTC ISO-8601 text. Member ids are Context Forge project ids. Every closed
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
| `project_id` | Key; the Context Forge project id. A member belongs to one program. |
| `program_id` | The program. `UNIQUE (program_id, project_id)` backs the pair foreign keys. |
| `rules_paths` | JSON array of repo-relative rules paths (a `*` allowed in the last segment). |
| `authorize_allow` | JSON array of config item keys taken off this member's not-authorized list. |
| `authorize_deny` | JSON array of config item keys put on it. |
| `registered_at`, `updated_at` | As above. |
| `removed_at` | Migration `003`. UTC time `set_up` removed the member; null for an active one. The row stays, because the member's questions and answers reference it and are the record. |
| `rules_from` | Migration `005`. `named` or `config_default` (`RulesFrom`, a `CHECK`), `NOT NULL`, default `named`. `named` means the member's own `rules_paths` entries (an empty list is a valid named choice: no rules); `config_default` means the config's `default_rules_paths`, read at answering time, and the stored `rules_paths` is unused (written as `[]`). Existing members stay `named`. |

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
| `state` | `claimed`, `answered`, `waiting_on_pm` or `closed` (`QuestionState`; `closed` from migration `003`). |
| `answering_run_id` | The answering run, null before one starts. |
| `waiting_reason` | Why the PM must answer, a `DeclineReason`; unconstrained in SQL, checked in code. Written with the `waiting_on_pm` insert or move; a PM answer does not clear it. |
| `claimed_at`, `updated_at` | UTC times. |
| `slice_label` | Migration `002`. The slice label (`<index> <name>`, or `none`) the passages were gathered for; reused on precedent passages. Written with the claim insert by `handle_pause`; null when the question waited before context was gathered. |
| `source_commit` | Migration `002`. The commit the passages were read at. Written with the claim insert. |
| `passages` | Migration `002`. JSON array of passage references (`id`, `source`, `question_id`, `date`). Written with the claim insert; rewritten by `replace_claim` for a dead claim. |
| `waiting_detail` | Migration `002`. Bounded detail for `waiting_reason`. Written with `waiting_reason`. |
| `evidence` | Migration `002`. JSON object: `proposed_answer`, `cited`, `verdict`, `reason`, as far as the answering run got. Written when the claim settles, to `answered` or `waiting_on_pm`. |

| `closed_reason` | Migration `003`. Null, or `dismissed`, `run_moved_on` or `run_gone` (`ClosedReason`, a `CHECK`). Written with the move to `closed` by `dismiss`, `handle_pause` and `status`; kept as history if `answer` later reopens the question. |
| `closed_detail` | Migration `003`. The dismissal reason, or the run's state when the sweep closed it. Written with `closed_reason`. |
| `closed_at` | Migration `003`. UTC time the question was closed. Written with `closed_reason`. |

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
| `via` | Migration `004`. `cli` or `mcp` (`Door`, a `CHECK`): the door that carried a PM answer. Null for an answer from before `004` and for the answerer's automatic answers, which no door carries; read as "no door", never a guessed one. Written with the `pm` row by `answer`. |

### `messages` (migration `006`, slice 240)

One row per request. `note` rows and `to_program` are in the table for slice 243 and are
never written by 240 (SQLite cannot widen a `CHECK` in place, and 243 has no migration).

| Column | Meaning |
|---|---|
| `message_id` | Key; the id the sender chose (1 to 64 characters, `[A-Za-z0-9][A-Za-z0-9._-]*`). |
| `kind` | `request` or `note` (`MessageKind`, a `CHECK`). |
| `from_member` | The sender's project id; references `members`. |
| `to_member` | The addressee's project id; references `members`. Set for a request. |
| `to_program` | References `programs`; null for a request. |
| `parent_id` | The request this one serves, as given; not a foreign key, because a terminal parent can be pruned while a child is open. |
| `depth` | At least 1: the parent's depth plus one, or 1 for a root. Stored at send so pruning never changes it. |
| `subject`, `body` | The sender's text. |
| `state` | `open`, `accepted`, `done`, `declined`, `cancelled` or `expired` (`RequestState`, a `CHECK`); null for a note. Read through `effective_state`, which shows an `open` request past `expires_at` as `expired` before the sweep records it. |
| `result`, `result_commit`, `result_version` | The `done` reply's text, commit and version. |
| `reason` | The decline text, or the cancel reason (`member_removed` when a member's removal cancelled it). |
| `accepted_at` | UTC time of the accept. |
| `created_at`, `state_changed_at` | UTC times; `state_changed_at` moves with every state change (an expiry records the sweep's own time). |
| `expires_at` | `created_at` plus `request_open_ttl_hours`, fixed at send, so a config change never moves it; null for a note. |

Table `CHECK`s: a request has `to_member`, a state and `expires_at` and no `to_program`;
a note has exactly one of `to_member` and `to_program`, and no state or `expires_at`.
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

### `pm_marker` (moved by slice 224)

| Column | Meaning |
|---|---|
| `id` | Always 1; the table holds one row. |
| `last_seen_seq` | The `answers.seq` the PM has seen; created at 0, meaning nothing seen. |

## Why each column exists

The schema holds no state that Context Forge or Squadron already says; every column is
one of five things. `tests/store/test_schema_holds_no_mirrored_state.py` pins the same
columns under the same reasons, so a new column fails it until it is listed in both
places and its reason is stated.

- **record**: what happened, written once when it did and never updated to follow anything else. A column here is never read as current state: `questions.checkout` is where a pause ran and `questions.slice_label` the slice its passages were gathered for, not where the member is or what slice it is on. Columns: `answers.answer`, `answers.answered_by`, `answers.cited`, `answers.paused_at`, `answers.recorded_at`, `answers.resume_at`, `answers.resume_detail`, `answers.resume_log`, `answers.resume_outcome`, `answers.resume_started_at`, `answers.retract_reason`, `answers.retracted_at`, `answers.run_id`, `answers.seq`, `answers.via`, `questions.answering_run_id`, `questions.checkout`, `questions.claimed_at`, `questions.closed_at`, `questions.closed_detail`, `questions.closed_reason`, `questions.evidence`, `questions.member_id`, `questions.passages`, `questions.paused_at`, `questions.question`, `questions.run_id`, `questions.slice_label`, `questions.source_commit`, `questions.state`, `questions.updated_at`, `questions.waiting_detail`, `questions.waiting_reason`, `releases.changed`, `releases.commit_sha`, `releases.member_id`, `releases.reported_at`, `releases.seq`, `releases.touched`, `releases.version`, `releases.versioned_at`.

- **membership**: who is in a program, the PM's registration and the one thing only Amoeba knows. Columns: `dependency_pairs.consumer_id`, `dependency_pairs.program_id`, `dependency_pairs.provider_id`, `dependency_pairs.registered_at`, `dependency_pairs.updated_at`, `members.program_id`, `members.project_id`, `members.registered_at`, `members.removed_at`, `members.updated_at`, `programs.program_id`, `programs.registered_at`, `programs.updated_at`.

- **settings**: what the PM chose for a program or member, and the store's own schema version. Columns: `dependency_pairs.consumed`, `members.authorize_allow`, `members.authorize_deny`, `members.rules_from`, `members.rules_paths`, `programs.concept_member`, `programs.concept_path`, `schema_meta.id`, `schema_meta.version`.

- **messages**: what agents said to each other and where each request stands. Amoeba is the only place this exists, and a request's state is Amoeba's own, never read from Context Forge or Squadron. Columns: `deliveries.created_at`, `deliveries.event`, `deliveries.member_id`, `deliveries.message_id`, `deliveries.seq`, `message_rejections.code`, `message_rejections.created_at`, `message_rejections.detail`, `message_rejections.id`, `message_rejections.member_id`, `message_rejections.message_id`, `message_rejections.operation`, `message_rejections.parent_id`, `message_rejections.to_ref`, `messages.accepted_at`, `messages.body`, `messages.created_at`, `messages.depth`, `messages.expires_at`, `messages.from_member`, `messages.kind`, `messages.message_id`, `messages.parent_id`, `messages.reason`, `messages.result`, `messages.result_commit`, `messages.result_version`, `messages.state`, `messages.state_changed_at`, `messages.subject`, `messages.to_member`, `messages.to_program`.

- **marker**: how far the PM has read the decisions. Columns: `pm_marker.id`, `pm_marker.last_seen_seq`.

## Question lifecycle and who writes it (slices 223 and 228)

A question moves `claimed` to `answered` or `waiting_on_pm`; a PM answer moves it to
`answered` from any state, `closed` included. It is **open** while it is `claimed`,
`waiting_on_pm`, or `answered` with its latest answer unresumed (`resume_outcome` null
or `refused`). Every move out of `claimed` names the claim it holds
(`answering_run_id`), and every close, dismissal and retraction is a compare-and-set in
one short write transaction, so a PM answer made meanwhile wins.

| Operation | Writes |
|---|---|
| `handle_pause`, a new question | one `questions` row, inserted in one transaction: `claimed` with `answering_run_id`, `slice_label`, `source_commit` and `passages`, or `waiting_on_pm` with `waiting_reason` and `waiting_detail` (and the context columns when the failure came after the context was gathered) |
| `handle_pause`, settling an answering run | `answered`: `questions.evidence` and an `answerer` `answers` row with `cited`, in one transaction through the answer gate. Otherwise `waiting_on_pm`: `waiting_reason`, `waiting_detail`, `evidence` |
| `handle_pause`, a dead claim | `replace_claim` (`answering_run_id` and `passages`, for a claimant that died before it started), or `waiting_on_pm` with `answering_run_stalled` |
| `answer` | a `pm` `answers` row with `via` (the door that carried the call) and `answered`, in one transaction; `waiting_reason`, `waiting_detail` and any `closed_*` columns are not cleared |
| the shared resume (both) | `answers.resume_started_at` just before every spawn, then `resume_outcome`, `resume_detail`, `resume_log`, `resume_at` |
| `dismiss` | `closed` with `closed_reason` `dismissed`, `closed_detail` (the PM's reason) and `closed_at`, from `claimed`, `waiting_on_pm` or `answered` with an unresumed answer; that answer becomes `not_delivered` (`dismissed`) in the same transaction |
| `retract` | `answers.retracted_at` and `retract_reason` on a PM answer, once |
| the close sweep: `handle_pause` (that run's rows at other pauses), `status` (open rows of the members in scope) | `closed` with `closed_reason` `run_moved_on` or `run_gone` and the run's state as `closed_detail`; a claim only once older than `answering_wait_seconds`; an unresumed answer past `resume_bound_seconds` becomes `not_delivered` |
| `set_up` removal | `members.removed_at`; the member's `dependency_pairs` rows are deleted |

How each state ends with nobody editing a file: `claimed` settles, or is replaced or
swept; `waiting_on_pm` is answered, dismissed or swept; `answered` unresumed is resumed,
dismissed or swept; `closed` is terminal and `answer` reopens it; a retracted answer is
terminal and a new PM answer replaces it as precedent. A PM answer resets the answer
limit, which counts `answerer` answers after the run's newest `pm` answer (a retracted
one still counts as the last). Precedent is each question's newest PM answer, left out
when retracted or when the question is `closed`; an older answer is not revived.

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
`check_said_no`. The remaining members (`node_already_blocked`, `question_missing`,
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
dropping nothing in that case. Each rejection row written trims its member to the newest
100 rows, and cuts the text the caller gave to 500 characters (`…` marks a cut). So the
rows `inbox`, `status` and `list` read are bounded by these caps times the members.

**Retention.** The prune deletes terminal requests (`done`, `declined`, `cancelled`,
`expired`) whose `state_changed_at` is older than `prune_after_days`, their deliveries
first, and `message_rejections` rows older than that. `open` and `accepted` requests are
never pruned: each has an exit. A pruned request's id sent again is a new request. A
member that is registered again keeps its retained history and starts with no live
request.

Text from other repos is data: `subject`, `body`, `result` and `reason` are written by
other repos' agents and stored as given, with the limits of the CLI contract. Amoeba
never acts on a request's text.

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
