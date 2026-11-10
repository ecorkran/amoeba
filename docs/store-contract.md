---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: The Amoeba store contract: the home, every table and column of the schema with its vocabulary and the operation that writes it, and the migration rule.
dateCreated: 20261109
dateUpdated: 20261110
status: complete
---

# Store contract

Amoeba keeps one SQLite file, `amoeba.sqlite3`, in its home. This document is the
reference for what is in it. `tests/test_contract_docs.py` fails if a table or column
of the schema is missing here.

## The home

- The home is `$AMOEBA_HOME` when that is set, otherwise `~/.config/amoeba/`.
  `XDG_CONFIG_HOME` is not consulted. A set but empty or relative `AMOEBA_HOME` is an
  error (`AmoebaHomeError`), never a fall back to the default.
- `config.yaml` (see `config-contract.md`) and `amoeba.sqlite3` live directly in it.
- Only `config/home.py` reads the variable. The CLI (and the MCP layer, slice 226)
  resolve the paths and pass them down; operations take an open store and a config.
- Tests set `AMOEBA_HOME` to a fresh temporary directory for every test.

## Concurrency

Writers are short-lived processes. The store opens in WAL mode with foreign keys on
and a 5-second busy timeout. `Store.write()` takes the write lock when the transaction
begins, so a read-then-write cannot fail halfway; `Store.read()` is one consistent
read. A writer that waits past the timeout gets `StoreBusyError`. There is no lock
file, pid file or read-only mode, and a missing store is created.

## Migrations

- Numbered files in `src/amoeba/store/schema/` (`001_baseline.sql`, `002_...`), shipped
  in the wheel. `EXPECTED_SCHEMA_VERSION` equals the highest number.
- Opening applies the missing files in order inside one write transaction and stamps
  `schema_meta.version`. A store stamped higher than the code expects is refused
  (`StoreSchemaError`) and left untouched.
- **No edits to `001`.** A store may already exist. Later migrations use only
  `ALTER TABLE ... ADD COLUMN`, so no table is rebuilt: an added column is nullable or
  `NOT NULL` with a constant default, may carry a `CHECK`, and may `REFERENCES` only
  with a null default.
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
| `seq` | Key; autoincrement. |
| `member_id` | The reporting member. `UNIQUE (member_id, commit_sha)`. |
| `commit_sha` | The released commit. |
| `version` | Null until the commit is tagged. |
| `changed`, `touched` | What the report says changed and what that touched. |
| `reported_at` | When the report arrived. |
| `versioned_at` | When a later tag set `version`; null until then. |

### `questions` (written by slice 223)

| Column | Meaning |
|---|---|
| `run_id`, `paused_at` | Key (together). `paused_at` is Squadron's value verbatim. |
| `member_id` | The member whose run paused. |
| `question` | The question text. |
| `checkout` | The checkout the run paused in. |
| `state` | `claimed`, `answered` or `waiting_on_pm` (`QuestionState`). |
| `answering_run_id` | The answering run, null before one starts. |
| `waiting_reason` | Why the PM must answer, a `DeclineReason`; unconstrained in SQL, checked in code. Written with the `waiting_on_pm` insert or move; a PM answer does not clear it. |
| `claimed_at`, `updated_at` | UTC times. |
| `slice_label` | Migration `002`. The slice label (`<index> <name>`, or `none`) the passages were gathered for; reused on precedent passages. Written with the claim insert by `handle_pause`; null when the question waited before context was gathered. |
| `source_commit` | Migration `002`. The commit the passages were read at. Written with the claim insert. |
| `passages` | Migration `002`. JSON array of passage references (`id`, `source`, `question_id`, `date`). Written with the claim insert; rewritten by `replace_claim` for a dead claim. |
| `waiting_detail` | Migration `002`. Bounded detail for `waiting_reason`. Written with `waiting_reason`. |
| `evidence` | Migration `002`. JSON object: `proposed_answer`, `cited`, `verdict`, `reason`, as far as the answering run got. Written when the claim settles, to `answered` or `waiting_on_pm`. |

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
| `resume_log` | Migration `002`. Path of the resume's stdout log. Written with `resume_outcome`. |
| `resume_at` | Migration `002`. UTC time the resume outcome was recorded. Written with `resume_outcome`. |

### `pm_marker` (moved by slice 224)

| Column | Meaning |
|---|---|
| `id` | Always 1; the table holds one row. |
| `last_seen_seq` | The `answers.seq` the PM has seen; created at 0, meaning nothing seen. |

## Question lifecycle and who writes it (slice 223)

A question moves `claimed` to `answered` or `waiting_on_pm`; a PM answer moves it to
`answered` from any state. Every move out of `claimed` names the claim it holds
(`answering_run_id`), so a PM answer made meanwhile wins.

| Operation | Writes |
|---|---|
| `handle_pause`, a new question | one `questions` row, inserted in one transaction: `claimed` with `answering_run_id`, `slice_label`, `source_commit` and `passages`, or `waiting_on_pm` with `waiting_reason` and `waiting_detail` (and the context columns when the failure came after the context was gathered) |
| `handle_pause`, settling an answering run | `answered`: `questions.evidence` and an `answerer` `answers` row with `cited`, in one transaction through the answer gate. Otherwise `waiting_on_pm`: `waiting_reason`, `waiting_detail`, `evidence` |
| `handle_pause`, a dead claim | `replace_claim` (`answering_run_id` and `passages`, for a claimant that died before it started), or `waiting_on_pm` with `answering_run_stalled` |
| `answer` | a `pm` `answers` row and `answered`, in one transaction; `waiting_reason` and `waiting_detail` are not cleared |
| the shared resume (both) | `answers.resume_outcome`, `resume_detail`, `resume_log`, `resume_at` |

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
