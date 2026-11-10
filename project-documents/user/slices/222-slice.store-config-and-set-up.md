---
docType: slice-design
slice: store-config-and-set-up
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 221-slice.the-cut
interfaces:
- 223-slice.pause-handling
- 224-slice.status-and-decisions
- 226-slice.mcp-server
- 227-slice.program-dependencies
dateCreated: 20261107
dateUpdated: 20261109
status: complete
---

# Slice Design: Store, Config and Set-up

## Overview

After 221, Amoeba is a library with `answering/` and `upstream/`, and no store, config or command. This slice adds:

- **The home.** `~/.config/amoeba/` holds the store and the config. Tests redirect it with `AMOEBA_HOME`, read by one function.
- **The store.** One SQLite file, `amoeba.sqlite3`, with a new baseline schema. Writers are short-lived processes and rely on SQLite's busy timeout.
- **The config.** One user-level `config.yaml`. The code has no defaults for any key.
- **Member resolution.** A directory resolves to its Context Forge project, then to that project's membership. Worktrees of one repo are one member.
- **`set_up`.** Registers or updates a program, its members, their settings and dependency pairs from one request document, as `amoeba set_up`.

Every later operation reads the member, config and store this slice provides. Effort: 3.

**Excluded:** writing question, answer, marker or release rows (223, 224, 227); removing members or pairs (Future Work); MCP (226); any change to the answering library.

## Dependencies

- **Slice 221 complete.** From it: `answering.settings.AnswererSettings` (fields `answer_limit`, `reserved_terms`, `rules_paths`, `passages_max_chars`, `answer_model`, `check_model`, `max_cost_usd`), its `RulesPath` and `ModelAlias` types and `validate_repo_relative_path`; `answering.values.AnsweredBy`; and `upstream.context_forge.cli_call` (`run_cf`, `CfRun`, `CfCallFailed`). If 221 places any of them elsewhere, import from wherever the audit's Verdicts record it.
- **Context Forge CLI**, observed at 0.19.26 on 20261107. `cf get --json` prints the working directory's project (`id`, `name`, `projectPath`, `worktree`); `-p <id or name>` prints a named one; outside any project it prints an error document with `"code": "PROJECT_NOT_FOUND"`.
- No new Python packages (`pyyaml`, `pydantic`, `sqlite3`, `argparse`).

## Architecture

### Component Structure

```
src/amoeba/
├── config/
│   ├── home.py          # amoeba_home(), store_path(), config_path(): the only read of AMOEBA_HOME
│   └── user_config.py   # UserConfig, NotAuthorizedItem, load_user_config()
├── store/
│   ├── store.py         # Store.open(), transactions, typed errors
│   ├── migrations.py    # numbered SQL files, schema_meta version check
│   ├── sql.py           # statement constants, BEGIN_IMMEDIATE defined once
│   ├── row_values.py    # decode_mapping, decode_timestamp, typed column reads
│   ├── schema/001_baseline.sql
│   ├── vocabulary.py    # ConsumedMode, QuestionState, ResumeOutcome
│   ├── programs.py      # program, member, settings and pair reads and upserts
│   └── models.py        # Program, Member, MemberSettings, DependencyPair
├── operations/
│   ├── members.py       # resolve_member(); ContextForgeError
│   ├── set_up.py        # SetUpRequest, SetUpResult, set_up()
│   └── member_answering.py  # answering_for()
├── cli/main.py          # `amoeba` entry point
└── upstream/context_forge/project_of.py   # cf get --json → CFProject | CFProjectNotFound
```

Import direction, enforced by `tests/test_import_boundaries.py`:

```
cli ──► operations ──► store ──► answering.values
             │   └────► config ──► answering.settings
             └────────► upstream, answering
```

`store` takes its path as an argument and imports nothing from `config`. `upstream` imports nothing from `answering` or the new packages. Only `cli` (and 226's MCP layer) calls `amoeba_home()`; operations take a `Store` and `UserConfig` as arguments.

### Data Flow

`amoeba set_up --file program.yaml`, run in a member's checkout:

1. `cli` reads the text and runs `yaml.safe_load` (D9), then loads `UserConfig` (D5).
2. `set_up` validates the document into `SetUpRequest` (D7). Failure returns `rejected` with `malformed` problems.
3. `set_up` resolves the working directory and every member reference to a Context Forge id (D6). All `cf` calls finish before the store opens, so no subprocess runs under a write lock and a `ContextForgeError` stops the call before anything is written.
4. `set_up` opens one `BEGIN IMMEDIATE` transaction, reads current state, runs the checks, and either writes and commits or rolls back and returns the problems.
5. `cli` prints `SetUpResult` as JSON and exits with the outcome's code.

## Technical Decisions

### D1 — The home and the one variable

- `amoeba_home()` returns `Path(os.environ["AMOEBA_HOME"])` when set, else `Path.home() / ".config" / "amoeba"`. `XDG_CONFIG_HOME` is not consulted, because the architecture allows only one way to pick the location.
- A set but empty or relative value raises `AmoebaHomeError`. It never falls back to the default.
- The home is resolved at call time, never import time, so a test fixture can redirect it.
- `store_path()` is `<home>/amoeba.sqlite3` and `config_path()` is `<home>/config.yaml`, with each name a constant in `home.py`. Old per-project store files in the same directory are never read.

### D2 — Opening the store and concurrent writers

- `Store.open(path, *, busy_timeout_seconds=BUSY_TIMEOUT_SECONDS)` creates the parent directory, sets the busy timeout at connect, sets `journal_mode=WAL` and `foreign_keys=ON`, and migrates (D4). `BUSY_TIMEOUT_SECONDS` is 5.0, defined once in `store.py`. Only tests pass the keyword.
- `Store.write()` yields a `BEGIN IMMEDIATE` transaction and `Store.read()` a `BEGIN` one, and store functions take an open transaction. Writes take the lock up front, because a deferred read-then-write can get `SQLITE_BUSY` without waiting.
- A busy timeout maps to `StoreBusyError` naming the path and timeout. Other open failures map to `StorePermissionError`, `StoreCorruptError` and `StoreSchemaError` (stamped newer than this code). All are `StoreError`.
- No lock file, pid file or read-only mode. One open mode: a missing store is created.

### D3 — Baseline schema

One migration, `001_baseline.sql`. Member ids are Context Forge project ids. Times are UTC ISO-8601 text. Every closed vocabulary is a `StrEnum` in `store/vocabulary.py` or `answering/values.py`, and a test pins each `CHECK` list to its enum.

| Table | Columns (key in bold) | Notes |
|---|---|---|
| `schema_meta` | **`id`** (=1), `version` | |
| `programs` | **`program_id`**, `concept_member` NULL, `concept_path` NULL, `registered_at`, `updated_at` | Concept columns both null or both set. `concept_member` must be a member of this program, checked in code (a foreign key would be circular). |
| `members` | **`project_id`**, `program_id` → `programs`, `rules_paths`, `authorize_allow`, `authorize_deny` (JSON arrays), `registered_at`, `updated_at` | One program per member. `UNIQUE (program_id, project_id)` backs the pair foreign keys. |
| `dependency_pairs` | `program_id`, **`provider_id`, `consumer_id`**, `consumed` (`from_source`, `from_release`), `registered_at`, `updated_at` | Both ends reference `members (program_id, project_id)`, so a pair can't cross programs. `CHECK (provider_id <> consumer_id)`. |
| `releases` | **`seq`** (autoincrement), `member_id` → `members`, `commit_sha`, `version` NULL, `changed`, `touched`, `reported_at`, `versioned_at` NULL | `UNIQUE (member_id, commit_sha)`. A later tag on a reported commit sets `version` and `versioned_at`, so `from_release` consumers can find a version added after their starting point. Written by 227. |
| `questions` | **`run_id`, `paused_at`**, `member_id` → `members`, `question`, `checkout`, `state` (`claimed`, `answered`, `waiting_on_pm`), `answering_run_id` NULL, `waiting_reason` NULL, `claimed_at`, `updated_at` | `paused_at` is Squadron's value verbatim. Written by 223. |
| `answers` | **`seq`** (autoincrement), `run_id`, `paused_at` → `questions`, `answered_by` (`answerer`, `pm`), `answer`, `recorded_at`, `resume_outcome` NULL (`resumed`, `refused`, `not_delivered`) | Append-only, so an automatic answer and a later PM answer are both kept. `seq` is what the `decisions` marker counts. Written by 223. |
| `pm_marker` | **`id`** (=1), `last_seen_seq` | One row, created at 0 ("nothing seen"). Moved by 224's `mark_read`. |

- The question, answer, release and marker tables carry only what the architecture fixes. The owning slice adds the rest in its own migration from `002`.
- Nobody edits `001`, since the store may exist once `set_up` has run. Later migrations use only `ALTER TABLE … ADD COLUMN`, so no table is rebuilt: an added column is nullable or `NOT NULL` with a constant default, may carry a `CHECK`, and may `REFERENCES` only with a null default. `waiting_reason` stays unconstrained in SQL; 223 checks it in code.
- No table holds run status, checkpoint kind, slice state or a CF name. `requests_initiative` and the overrides table are gone.
- `docs/store-contract.md` describes each column, its vocabulary and which slice writes it.

### D4 — Migrations

- `store/schema/` holds numbered `.sql` files, shipped in the wheel (`pyproject.toml` gains `src/amoeba/store/schema/*.sql`). `EXPECTED_SCHEMA_VERSION` in `migrations.py` equals the highest file number.
- Migration runs inside `BEGIN IMMEDIATE`, reads `schema_meta`, applies missing files in order and stamps the version. Two processes opening a new store serialize on the lock, and the second applies nothing.
- A store stamped higher raises `StoreSchemaError` and is left untouched.

### D5 — The user config file

`UserConfig` is a frozen pydantic model with `extra="forbid"` and no field defaults:

| Key | Type | Meaning |
|---|---|---|
| `answer_model`, `check_model` | `ModelAlias` | Squadron aliases for the answer and check steps |
| `max_cost_usd` | number > 0 | Cost cap of one answering run |
| `answer_limit` | int ≥ 1 | Most automatic answers one run may take |
| `passages_max_chars` | int ≥ 1 | Most characters of passages an answering run is sent |
| `authorize_items` | list, may be empty | Everything answers may be barred from authorizing |

Each `authorize_items` entry requires `key` (unique identifier, what members refer to), `description` (what the answer and check steps are told; never matched on), `screen_phrases` (may be empty) and `denied_by_default` (bool).

- `load_user_config(path)` raises `ConfigError` listing every problem in one pass, each naming the file and key: missing file ("no config at <path>; see docs/config-contract.md"), not UTF-8, not YAML, missing key, unknown key, bad value.
- The architecture's default list (push, merge to the main branch, release, destructive database statement, policy change, all `denied_by_default: true`) exists only as the example in `docs/config-contract.md`. No `config init` command: it would be a default in code.
- Keys later slices add are required too, so an old config fails naming the new key.

### D6 — Member resolution

- `project_of(*, directory=None, reference=None, run) -> CFProject | CFProjectNotFound | CfCallFailed` runs `cf get --json` with `cwd=directory` or `-p <reference>`. `CFProject` holds `id`, `name`, `project_path` (from `projectPath`); other fields are ignored. A `PROJECT_NOT_FOUND` document on either stream is `CFProjectNotFound` with CF's message. Any other failure or unparseable output is `CfCallFailed` quoting the output head.
- `resolve_member(store, directory, run) -> Member | NotInProgram | NotAProject`. `NotInProgram` carries the CF id and `NotAProject` CF's message. `CfCallFailed` is raised as `ContextForgeError` (defined in `operations/members.py`), so "cf isn't working" never reads as "not a member".
- Worktrees and subdirectories of a checkout resolve to the same project id because CF does that. Amoeba adds no worktree logic.

### D7 — The `set_up` operation

**Request.** `SetUpRequest`, frozen pydantic, `extra="forbid"`. `set_up` takes the parsed document as an unvalidated `object` and validates it itself, so the CLI and 226 pass input through unchanged.

```yaml
program: trading                 # required
concept:                         # optional; omitted = unchanged, null = no concept
  member: trading-core           # CF project name or id
  path: project-documents/user/project-guides/000-concept.trading.md
members:                         # optional
  - project: trading-core        # CF name or id; omitted = the working directory's project
    rules_paths: [CLAUDE.md]     # required for a new member
    authorize_allow: [merge_to_main]  # config item keys taken off this member's not-authorized list
    authorize_deny: [deploy]          # config item keys put on it
    depends_on:                  # upserts pairs with this member as consumer
      - provider: trading-data
        consumed: from_release
```

**Upsert, never remove.** What the request names is created or set; the rest is left alone. A given list field replaces the stored value whole. `depends_on` creates each pair or sets its `consumed`.

**Checks** run against the state the request would produce, inside the transaction. All problems are collected and any one rejects the whole request. A problem is `SetUpProblem(code, detail)`:

| `SetUpProblemCode` | When |
|---|---|
| `malformed` | Fails `SetUpRequest` validation (one per pydantic error), including a non-repo-relative path, a member listed twice after resolution, or a key in both authorize lists |
| `not_a_project` | A reference, or the working directory for an omitted `project`, is no CF project |
| `empty_program` | The program doesn't exist and the request adds no member |
| `member_of_other_program` | A named member already belongs to another program |
| `rules_paths_required` | A new member has no `rules_paths` |
| `unknown_provider` | A provider is not a member of this program after the request |
| `self_dependency` | A member lists itself as a provider |
| `unknown_authorize_item` | An authorize key is not in the config's `authorize_items` |
| `concept_member_not_member` | `concept.member` is not a member after the request |

**Result.** `SetUpResult`:

- `outcome`: `applied`, `unchanged` or `rejected`.
- `changes`: one line per created or changed row; empty unless `applied`.
- `problems`: empty unless `rejected`.
- `program`: concept and each member's id, rules paths, authorize lists and pairs, read in the same transaction. On `rejected` the unchanged state, or null if the program doesn't exist.
- `working_directory`: `{member, program}`, `{not_in_program: <cf id>}` or `{not_a_project: <message>}`. Informational; `not_a_project` is a problem only when a member entry omits `project`.

A repeat writes nothing and returns `unchanged`; `updated_at` moves only when a value changes. A request naming only `program` is the read-back.

### D8 — A member's answering settings

`answering_for(member_settings, config) -> MemberAnswering` is the loader 221 D5 leaves to 222.

- The not-authorized items are the config items with `denied_by_default: true` not in `authorize_allow`, plus the items in `authorize_deny`, in config order.
- `MemberAnswering.settings` is an `AnswererSettings`: `reserved_terms` are those items' screen phrases, `rules_paths` the member's, and the rest from the config. `MemberAnswering.not_authorized` is the tuple of items with descriptions; 223 decides how they reach the models.
- So allowing an item removes it from both what the models are told and what the screen matches.
- An authorize key the config no longer has raises `ConfigError` naming the member and key.

### D9 — The CLI

- `[project.scripts] amoeba = "amoeba.cli.main:main"`. `argparse`, one subcommand per operation, named as the operation.
- `amoeba set_up --file <path|->`, with no per-field flags. Output is `SetUpResult` JSON on stdout.
- The CLI's only request handling is reading the text and `yaml.safe_load`. A document that parses but has the wrong shape goes to `set_up` as `malformed`.
- Exit codes are named constants in `cli/main.py`, which later slices reuse:

| Exit | Meaning | stdout | stderr |
|---|---|---|---|
| 0 | `applied` or `unchanged` | result JSON | — |
| 1 | `rejected` | result JSON | — |
| 2 | usage error, or a request that can't be read, isn't UTF-8 or isn't YAML (before config or store) | — | argparse usage, or `error: RequestDocumentError: <source>: <reason>` |
| 3 | `ConfigError`, `AmoebaHomeError`, `ContextForgeError`, any `StoreError` | — | `error: <ExceptionName>: <message>` |

The CLI is the process boundary and the one top-level handler for these errors.

### D10 — Tests never touch the real home

- An autouse fixture in `tests/conftest.py` sets `AMOEBA_HOME` to a fresh temporary directory per test. Subprocesses inherit it.
- `tests/config/test_home.py` checks paths sit under the variable, the fixture's home is not the real one, XDG is ignored when the variable is unset, and empty or relative values raise.
- An AST test checks that no module under `src/amoeba` other than `config/home.py` contains `AMOEBA_HOME` or calls `Path.home`.
- Tests inject a fake `CfRun`. Subprocess CLI tests put a fake `cf` first on `PATH` that replays the D11 recordings.

### D11 — Fixtures from real Context Forge output

`tests/fixtures/context_forge/` holds CF 0.19.26's `cf get --json` output from a default worktree, a non-default worktree of the same project, a subdirectory of a checkout (same `id` as the root on 20261107), and the `PROJECT_NOT_FOUND` document. The `project_of` parser is tested on them.

### Audit items (220 code audit)

`user/analysis/220-analysis.code-audit.md` ("Dependencies of kept code" and "Differences from the architecture") raised items that land on this slice. Those already settled above: the concept columns and the optional concept (D3, D7); the per-member authorize lists and their relation to `reserved_terms` (D3 `members`, D8: both come from the same config items, so they are one source and two derived values); the resume outcome (`answers.resume_outcome`, D3; the resume log path is a column 223 adds in its `002`); the fresh-store race (D4, tested by task 8.8); `XDG_CONFIG_HOME` (D1: not consulted); the answering run id and checkout on the claim (`questions.answering_run_id`, `checkout`, D3); the slice label on the question record (223's `002` adds `questions.slice_label`). The rest:

- **Scratch directory.** No column. An answering run's scratch directory is derived as `answering_dir() / <answering_run_id>` (223 D6 and D12), so a later explicit call reads `answer.json` and `check.json` from the claim's `answering_run_id` alone. This slice adds no path column; `docs/store-contract.md` states the derivation so nobody adds a second source of truth. The answering run's log paths are derived from the same id (223 D6).
- **Opting a member in or out of answering.** Program membership is the only switch. There is no `answering_enabled` column and no equivalent of the old `answerer:` section. A repo is opted in by being a program member and having the pause hook configured; it is opted out by not being registered, or by leaving the hook unconfigured. A pause from a directory that is not a member is skipped by `handle_pause` (223), which is why `resolve_member` returns `NotInProgram`. A second switch would be a second place for the two to disagree. `docs/store-contract.md` records this.
- **Store helpers re-homed from the old store.** 221 deletes `src/amoeba/store` whole and moves none of the helpers the audit lists, so this slice creates them: `BEGIN_IMMEDIATE` is defined once in `store/sql.py` and used by `Store.write()` and `migrate()`; `decode_mapping` and `decode_timestamp` live in `store/row_values.py` for the program mapping now and the question mapping in 223. The old versions (`sql_inbox.py`, `mapping_journal.py`, `row_values.py`, `connection.py` in the commit 221 branched from) may be restored and adapted; no other old store module is.
- **Test seeding helper.** The old `question_harness.py` (seeding through nodes and journal entries) is gone. This slice adds `tests/store/seed.py`, which inserts programs, members, pairs, questions and answers through the store's `sql.py` constants, taking each column value as an argument with no default, so 223 and 224 seed any state without going through the operation under test. `tests/fault_injection.py` (fail one named SQL statement to prove a rollback) is rewritten for the new `Store` and used by this slice's atomicity tests and by 223's.

## API Contracts

For 223, 224, 226 and 227 (the CLI is in D9):

- `config.home`: `amoeba_home()`, `store_path()`, `config_path()`
- `config.user_config.load_user_config(path) -> UserConfig`
- `store.store.Store.open(path)`, `Store.write()`, `Store.read()`
- `store.programs`: `get_program`, `get_member`, `members_of`, `pairs_of`, `member_settings`, and the upserts `set_up` uses
- `operations.members.resolve_member(store, directory, run)`
- `operations.set_up.set_up(store, config, document: object, *, directory, run) -> SetUpResult`
- `operations.member_answering.answering_for(member_settings, config) -> MemberAnswering`

What each slice takes:

- **223:** `resolve_member`, `answering_for`, the `questions` and `answers` tables with `QuestionState` and `ResumeOutcome`, and the write transaction for the claim. It adds its config keys under D5. The D9 errors can occur in `handle_pause` before any claim, where from the detached hook they reach only stderr; 223 decides where they become a record `status` can show.
- **224:** `answers.seq` and `pm_marker` for `decisions` and `mark_read`; programs and members for `status`.
- **226:** `SetUpRequest` as the MCP tool's input schema and `SetUpResult` as its output, with no logic of its own.
- **227:** `dependency_pairs` with `consumed`, and `releases`.

## Success Criteria

- A valid request creates the program, members, settings and pairs and returns `applied` with one change line per row. The same request again returns `unchanged` and leaves every `updated_at` alone. A request naming only `program` returns its state.
- Each D7 check rejects with its code and a detail naming the field or member, with the store unchanged. A non-mapping YAML document is `malformed`; an unreadable or non-YAML request exits 2; a `cf` failure exits 3 with the store unchanged.
- An omitted `project` from two worktrees of one repo resolves to the same member. A CF project outside the program gives `not_in_program`; a non-project directory gives `not_a_project`.
- `answering_for`: a member allowing `merge_to_main` lacks that item's phrases and description while another member keeps them; a member denying a `denied_by_default: false` item gets it and others don't.
- A missing config file, or a config missing any one D5 key, exits 3 naming the file or key.
- 8 processes against one new store each call `set_up` for the same program with a different member; each returns `applied` or raises `StoreBusyError`, and the store ends with every applied member. A held write transaction with `busy_timeout_seconds=0.2` gives `StoreBusyError`. A store stamped higher gives `StoreSchemaError` and is unchanged.
- The D10, vocabulary-pinning, D11 and import-boundary tests pass, as do `ruff format --check`, `ruff check`, `pyright` (strict) and `pytest`. The wheel contains `001_baseline.sql`. Both contract docs match the code.

**Walkthrough** (repo root; run 20261109 with the real `cf` 0.19.26; any agent can repeat it)

Setup: `export AMOEBA_HOME="$(mktemp -d)"` and `A="$PWD/.venv/bin/amoeba"` (after `uv sync`; `uv run amoeba` is the same command, but step 3 runs it from other directories).

1. No config yet: `printf 'program: demo\n' | $A set_up --file -` prints `error: ConfigError: no config at $AMOEBA_HOME/config.yaml; see docs/config-contract.md` on stderr and exits 3. Then copy the yaml block under `## Example` in `docs/config-contract.md` into `$AMOEBA_HOME/config.yaml`.
2. Write `$AMOEBA_HOME/req.yaml`:

   ```yaml
   program: demo
   members:
     - rules_paths: [CLAUDE.md]
   ```

   `$A set_up --file $AMOEBA_HOME/req.yaml` exits 0 and prints JSON with `"outcome": "applied"`, `"changes": ["added program demo", "added member <amoeba's Context Forge id>"]`, and `program.members` holding that one member. Run it again: exit 0, `"outcome": "unchanged"`, `"changes": []`.
3. Worktrees. From a second registered worktree of the same repo (`git worktree add --detach <dir> HEAD`, then in `<dir>`: `cf worktree init --name walkthrough-wt --range 800-899 -o`, which does not alter the default worktree's range), `printf 'program: demo\n' | $A set_up --file -` returns `unchanged` and `working_directory` is `{"member": {...}, "program": "demo"}` with the same `project_id` as step 2. From `/tmp` the same command returns `unchanged` with `"working_directory": {"not_a_project": "No project specified and no registered project found at current path."}`. Remove the throwaway afterwards: `cf worktree rm walkthrough-wt -y` and `git worktree remove --force <dir>`.

Caveats found while running it: the `not_a_project` text is Context Forge's own message, so it can change with `cf`. A project that is not a member gives `{"not_in_program": "<cf id>"}` instead of `member`. `rules_paths` is required only for a member not yet registered.

## Future Work

- **Removing members and pairs through `set_up`.** Explicit `remove` entries, refusing a member with question records, if mistaken registrations turn out to happen. Until then a pair's `consumed` changes by upsert and anything else is fixed by hand in SQLite. Effort: 1/5.
