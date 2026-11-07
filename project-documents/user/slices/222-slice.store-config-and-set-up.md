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
dateUpdated: 20261107
status: not_started
turns: 19
promptTokens: 1429016
cachedTokens: 1311952
cacheWriteTokens: 117028
completionTokens: 33821
durationSeconds: 350.9
costUsd: 1.875511
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 1.8755109999999997
    completionTokens: 33821
---

# Slice Design: Store, Config and Set-up

## Overview

After slice 221, Amoeba is a library with two packages, `answering/` and `upstream/`. It has no store, no config and no command. This slice adds those and the first operation:

- **The Amoeba home.** One fixed per-user directory, `~/.config/amoeba/`, holds the store and the config file. Tests redirect it with one environment variable, `AMOEBA_HOME`, and only one function reads that variable.
- **The store.** One SQLite file, `amoeba.sqlite3`, with a new baseline schema: programs, members, per-member settings, dependency pairs carrying `consumed`, reported releases, the question record keyed on run id and `paused_at`, answers, and the PM's single `decisions` marker. Writers are short-lived processes, and SQLite's busy timeout handles contention.
- **The config.** One user-level YAML file, `config.yaml`, holding the models, the cost cap, the per-run answer limit, the passage budget, and the default list of what answers may not authorize. The code has no defaults for any of these.
- **Member resolution.** A directory resolves to its Context Forge project, then to that project's membership. Worktrees of one repo resolve to one member.
- **`set_up`.** Registers or updates a program, its members, their settings and their dependency pairs from one request document. It is available as `amoeba set_up`, the first command of the new console entry point.

## Value

Architectural enablement, and the first thing the PM can run. Every later operation (`handle_pause`, `answer`, `status`, `decisions`, `mark_read`, `report_release`, `changes`) reads the member, the config and the store this slice provides. The PM, through an agent, can set up a program and read it back.

## Technical Scope

**Included:**

- `amoeba.config`: home resolution (D1) and the user config model and loader (D5).
- `amoeba.store`: opening, the baseline migration, write transactions, and the program reads and writes `set_up` needs (D2, D3, D4).
- The question, answer, release and marker tables in the baseline schema, with their closed vocabularies. They are created here and written by 223, 224 and 227 (D3).
- `upstream/context_forge/project_of.py`, which reads `cf get --json` for a directory or a name (D6).
- `amoeba.operations`: member resolution (D6), the `set_up` operation (D7), and `member_answering`, which builds a member's `AnswererSettings` from the config and the member's settings (D8).
- `amoeba.cli`: the `amoeba` console entry point with one command, `set_up` (D9).
- Test isolation from the real home (D10).
- `docs/store-contract.md` and `docs/config-contract.md`.

**Excluded:**

- Writing question, answer or marker rows. That is 223 and 224.
- Writing release rows, and `report_release` and `changes`. That is 227.
- Removing members or dependency pairs (see Future Work below).
- MCP. That is 226, which wraps `set_up` with the same request model.
- Any change to the answering library apart from the import of `AnswererSettings` by `member_answering`.

## Dependencies

### Prerequisites

- **Slice 221 complete.** `src/amoeba` holds only `answering/` and `upstream/`. There is no `amoeba.store`, no console entry point and no old migrations.
- **Context Forge CLI** (`cf`), observed at 0.19.26 on 20261107. `cf get --json` run in a directory prints that directory's project, with `id`, `name`, `projectPath` and a `worktree` object. Run with `-p <id or name>`, it prints the named project. Outside any project it prints an error document with `"code": "PROJECT_NOT_FOUND"`.
- No new Python packages. `pyyaml`, `pydantic` and `sqlite3` are already used, and the CLI uses `argparse`.

### Interfaces Required

From 221:

- `amoeba.answering.settings.AnswererSettings`, with the fields `answer_limit`, `reserved_terms`, `rules_paths`, `passages_max_chars`, `answer_model`, `check_model` and `max_cost_usd`, and its `RulesPath` and `ModelAlias` types. The repo-relative path rule (`validate_repo_relative_path`) moves with it.
- `amoeba.answering.values`: `AnsweredBy`, which the `answers.answered_by` vocabulary follows.
- `amoeba.upstream.context_forge.cli_call`: `run_cf`, `CfRun` and `CfCallFailed`, the bounded `cf` call.

## Architecture

### Component Structure

```
src/amoeba/
├── config/
│   ├── home.py          # amoeba_home(), store_path(), config_path(): the only read of AMOEBA_HOME
│   └── user_config.py   # UserConfig, NotAuthorizedItem, load_user_config()
├── store/
│   ├── store.py         # Store.open(), write transactions, typed errors
│   ├── migrations.py    # numbered SQL package, schema_meta version check
│   ├── schema/001_baseline.sql
│   ├── vocabulary.py    # ConsumedMode, QuestionState, ResumeOutcome
│   ├── programs.py      # program, member, settings and pair reads and upserts
│   └── models.py        # Program, Member, MemberSettings, DependencyPair dataclasses
├── operations/
│   ├── members.py       # resolve_member(directory); ContextForgeError
│   ├── set_up.py        # SetUpRequest, SetUpResult, set_up()
│   └── member_answering.py  # answering settings for one member
├── cli/
│   └── main.py          # `amoeba` entry point; `set_up` subcommand
├── upstream/context_forge/project_of.py   # cf get --json → CFProject | CFProjectNotFound
├── answering/  (from 221, unchanged)
└── upstream/   (from 221)
```

Import direction (enforced by `tests/test_import_boundaries.py`):

```
cli ──► operations ──► store ──► answering.values
             │   └────► config ──► answering.settings
             └────────► upstream, answering
```

- `store` imports nothing from `config`, `operations` or `cli`. It takes its path as an argument.
- `config` imports nothing from `store`. Combining config with a member's settings happens in `operations.member_answering`.
- `upstream` still imports nothing from `answering` (221 D6), and nothing from the new packages.
- Only `cli` (and 226's MCP layer) calls `amoeba_home()`. Operations take a `Store` and a `UserConfig` as arguments, so tests pass them in.

### Data Flow

`amoeba set_up --file program.yaml`, run in a member's checkout:

1. `cli` reads the request text (a file, or `-` for stdin) and parses it as YAML. JSON is valid YAML, so JSON works too. If the text can't be read, isn't UTF-8 or isn't YAML, the CLI exits with a usage error and goes no further (D9). Otherwise it passes the parsed document, still unvalidated, to `set_up`.
2. `cli` loads `UserConfig` from `config_path()` (D5). A missing file or value is an error that names it.
3. `set_up` validates the document into `SetUpRequest` (D7). A document that fails validation, including one that isn't a mapping, returns `rejected` with one `malformed` problem per error, and nothing else runs. 226's MCP tool passes its JSON input to the same function, so validation lives in one place.
4. `set_up` resolves the working directory and every member reference to a Context Forge project id (D6). An omitted `project` means the working directory's project. A name or id is resolved with `cf get -p`. All `cf` calls run here, before the store is opened. So no subprocess runs while a write lock is held, and a `ContextForgeError` stops the call before anything is written.
5. `set_up` opens the store and begins one `BEGIN IMMEDIATE` transaction. It reads the program's current state, checks the request against it (D7), and either writes the changes and commits, or rolls back and returns the problems. The working directory's membership, for the result's `working_directory` field, is read from the store in the same transaction, using the project id from step 4.
6. `cli` prints the `SetUpResult` as JSON on stdout and exits with the outcome's code (D9).

### State Management

- **Store.** `$AMOEBA_HOME/amoeba.sqlite3`, in WAL mode. Created and migrated on first open by any operation. One open mode, read-write, because every caller is a short-lived process and a missing store is equivalent to an empty one.
- **Config.** `$AMOEBA_HOME/config.yaml`. The PM writes it, and Amoeba only reads it. It is loaded once per process.
- **No other state.** Run state stays in Squadron and slice state in Context Forge. The member's Context Forge name and paths are read from `cf` when needed, never stored.

## Technical Decisions

### D1 — The Amoeba home and the one variable
Status: decided

- `amoeba_home()` in `config/home.py` returns `Path(os.environ["AMOEBA_HOME"])` when the variable is set, and `Path.home() / ".config" / "amoeba"` otherwise. This matches Squadron's `~/.config/squadron/`. `XDG_CONFIG_HOME` is not consulted. The architecture says nothing else picks the location, and the old store's XDG step was a second way to pick it.
- A value that is set but empty, or that is not absolute, raises `AmoebaHomeError` naming the variable and the value. It never falls back to the default.
- The home is resolved at call time, never at import time. The old `DEFAULT_STORE_DIR` module constant would capture the real home before a test fixture could redirect it.
- `store_path()` is `amoeba_home() / "amoeba.sqlite3"` and `config_path()` is `amoeba_home() / "config.yaml"`. Each file name is a constant in `home.py`.
- Files left in `~/.config/amoeba/` by the old store (per-project `*.sqlite3`, `programs/`) are never read. Their names don't collide with `amoeba.sqlite3`.

Rejected: keeping the name `AMOEBA_STORE_DIR`. The directory now holds the config too, and the old name would suggest it moves only the store. Rejected: separate variables for the store and the config. The architecture says one variable, and two would let a test redirect one and read the real other.

### D2 — Opening the store and concurrent writers
Status: decided

- `Store.open(path, *, busy_timeout_seconds=BUSY_TIMEOUT_SECONDS)` creates the parent directory, connects with the busy timeout set at connect time, sets `journal_mode=WAL` and `foreign_keys=ON`, and migrates (D4). `BUSY_TIMEOUT_SECONDS` is defined once in `store.py`, at 5.0 seconds, the old store's value. The keyword exists so tests can force contention quickly. No caller outside tests passes it.
- Every write runs in `BEGIN IMMEDIATE`. A deferred transaction that reads and then writes can get `SQLITE_BUSY` at the upgrade without waiting on the busy handler. Taking the write lock at the start means contention always waits, up to the timeout.
- When the timeout expires, the `sqlite3.OperationalError` ("database is locked") is mapped to `StoreBusyError`, naming the store path and the timeout. Other open failures map to `StorePermissionError` (path unusable), `StoreCorruptError` (not a SQLite database) and `StoreSchemaError` (stamped newer than this code), as in the old store.
- There is no single-writer lock, no pid file and no read-only open mode.

Rejected: a lock file around writes. SQLite already serializes writers, and a lock file brings back the stale-lock recovery the cut removed.

### D3 — Baseline schema
Status: decided

One migration, `001_baseline.sql`. Ids of members are Context Forge project ids. Times are UTC ISO-8601 text. Every closed vocabulary is a `StrEnum` in `store/vocabulary.py` or `answering/values.py`, and a test pins each `CHECK` list to its enum.

| Table | Columns (key in bold) | Notes |
|---|---|---|
| `schema_meta` | **`id`** (=1), `version` | |
| `programs` | **`program_id`**, `concept_member` NULL, `concept_path` NULL, `registered_at`, `updated_at` | Concept columns are both null or both set. `concept_member` must be a member of this program, checked in code inside the transaction (a foreign key would be circular on creation). |
| `members` | **`project_id`**, `program_id` → `programs`, `rules_paths` (JSON array), `authorize_allow` and `authorize_deny` (JSON arrays of config item keys), `registered_at`, `updated_at` | One program per member: `project_id` is the key. `UNIQUE (program_id, project_id)` backs the pair foreign keys. The two authorize arrays are the member's changes to the not-authorized list (D8). |
| `dependency_pairs` | `program_id`, **`provider_id`, `consumer_id`**, `consumed` (`from_source`, `from_release`), `registered_at`, `updated_at` | Both ends reference `members (program_id, project_id)`, so a pair can't cross programs. `CHECK (provider_id <> consumer_id)`. |
| `releases` | **`seq`** (autoincrement), `member_id` → `members`, `commit_sha`, `version` NULL, `changed`, `touched`, `reported_at`, `versioned_at` NULL | `UNIQUE (member_id, commit_sha)`: a later tag on a reported commit sets `version` and `versioned_at`, so a `from_release` consumer can find a version added after its starting point. Written by 227. |
| `questions` | **`run_id`, `paused_at`**, `member_id` → `members`, `question`, `checkout`, `state` (`claimed`, `answered`, `waiting_on_pm`), `answering_run_id` NULL, `waiting_reason` NULL, `claimed_at`, `updated_at` | `paused_at` is Squadron's value, verbatim. Written by 223. |
| `answers` | **`seq`** (autoincrement), `run_id`, `paused_at` → `questions`, `answered_by` (`answerer`, `pm`), `answer`, `recorded_at`, `resume_outcome` NULL (`resumed`, `refused`, `not_delivered`) | Append-only answers: a PM answer to a waiting question is a new row, so the record keeps both. `seq` is what the `decisions` marker counts. Written by 223. |
| `pm_marker` | **`id`** (=1), `last_seen_seq` | One row, created by the migration with `last_seen_seq` 0, which is "nothing seen yet". Moved by 224's `mark_read`. |

- The old program record's `requests_initiative`, `consumption_overrides` and `program_submissions` don't exist here. `consumed` is on the pair (architecture).
- Answers are a separate append-only table rather than columns on `questions`, because a question can have an automatic answer and a later PM answer, and `decisions` lists answers in `seq` order.
- The question, answer, release and marker tables are created here because the slice plan puts the whole baseline in 222. They carry only their keys, their foreign keys, and the columns and vocabularies the architecture already fixes: the claim's checkout and answering run id, the question states, who answered, the resume outcomes, and a release's commit, version, changes and what they touched. Everything else the owning slice designs (passages and evidence, resume detail and log path, waiting detail, the slice reference, and the vocabulary of `waiting_reason`) is added by that slice in its own migration, starting at `002`. Nobody edits `001`, because the store may already exist on the PM's machine once `set_up` has been run. 222 adds no code that writes these tables.
- Later migrations to these tables use only `ALTER TABLE … ADD COLUMN`, so no table is ever rebuilt or dropped. SQLite's limits on that statement decide the rule:
  - An added column is nullable, or `NOT NULL` with a constant default. It may carry a `CHECK`. It may be a `REFERENCES` column only if its default is null.
  - No constraint on an existing column changes.
  - All the deferred columns are optional record detail, so each fits. `waiting_reason` stays unconstrained in SQL, and 223 checks it in code against `DeclineReason`.
  - A slice whose design needs a change outside this rule takes that change back to the PM, rather than writing a table rebuild.
- Nothing in the schema holds run status, checkpoint kind, slice state or a Context Forge name. 224's schema test checks this.

### D4 — Migrations
Status: decided

- `store/schema/` is a package of numbered `.sql` files, shipped in the wheel (`pyproject.toml` artifacts gain `src/amoeba/store/schema/*.sql`). `EXPECTED_SCHEMA_VERSION` is defined once in `migrations.py` and equals the highest file number.
- Migration runs inside `BEGIN IMMEDIATE`. It reads `schema_meta` inside the transaction, applies each missing file in order, and stamps the version. Two processes opening a new store at once both wait on the lock, so the second sees the version the first stamped and applies nothing.
- A store stamped higher than `EXPECTED_SCHEMA_VERSION` raises `StoreSchemaError` and is left untouched.

### D5 — The user config file
Status: decided

`config.yaml` is validated by `UserConfig`, a frozen pydantic model with `extra="forbid"` and no field defaults:

| Key | Type | Meaning |
|---|---|---|
| `answer_model` | `ModelAlias` | Squadron alias for the answer step |
| `check_model` | `ModelAlias` | Squadron alias for the check step |
| `max_cost_usd` | number > 0 | Cost cap of one answering run |
| `answer_limit` | int ≥ 1 | Most automatic answers one run may take |
| `passages_max_chars` | int ≥ 1 | Most characters of rendered passages an answering run is sent |
| `authorize_items` | list of items, may be empty | Everything a member's answers may be barred from authorizing, and whether each is barred by default |

Each `authorize_items` entry has these fields, all required:

- `key`: a stripped identifier, unique in the list. Keys are what members refer to (D8).
- `description`: the text the answer and check steps are told (used by 223). Descriptions are never matched on.
- `screen_phrases`: the deterministic screen's phrases for this item. May be empty.
- `denied_by_default`: `true` puts the item on every member's not-authorized list unless the member allows it. `false` keeps it off unless the member denies it.

- `load_user_config(path)` raises `ConfigError`, listing every problem in one pass. Each problem names the file and the key: a missing file ("no config at <path>; see docs/config-contract.md"), text that isn't UTF-8, text that isn't YAML, a missing key, an unknown key, or a bad value.
- The architecture's default list (push, merge to the main branch, release, destructive database statement, policy change, each `denied_by_default: true`) exists only as the example in `docs/config-contract.md`, which the PM copies. Nothing in code supplies it.
- Later slices add keys (for example, how long 223's resume waits for `running`) to `UserConfig` and the contract doc. A new key is required too, so an old config fails naming it.

Rejected: a `config init` command writing a starter file. That would be a default in code under another name.

### D6 — Member resolution
Status: decided

- `upstream/context_forge/project_of.py` has `project_of(*, directory=None, reference=None, run) -> CFProject | CFProjectNotFound | CfCallFailed`. It runs `cf get --json`, with `cwd=directory` or with `-p <reference>`. `CFProject` holds `id`, `name` and `project_path`, which the parser reads from `id`, `name` and `projectPath`. It ignores every other field, and the D11 fixtures assert all three. An error document with code `PROJECT_NOT_FOUND`, on either stream, is `CFProjectNotFound` with CF's message. Any other non-zero exit, or output it can't parse, is `CfCallFailed` quoting the output head.
- `operations.members.resolve_member(store, directory, run) -> Member | NotInProgram | NotAProject`. `NotAProject` carries CF's message, and `NotInProgram` carries the CF project id. A `CfCallFailed` is raised as `ContextForgeError`, because "cf isn't working" must not read as "not a member". `ContextForgeError` is defined in `operations/members.py`. `set_up` raises it for references too, and `cli` catches it, which keeps the `cli → operations → upstream` direction.
- Worktrees are one member because Context Forge gives every worktree of a project the same project id (checked on Squadron's worktrees, 20261106). Amoeba adds no worktree logic of its own.
- A subdirectory of a checkout resolves like the checkout, because CF matches the project whose directory contains the working directory. A D11 fixture records this.

Rejected: matching the directory against stored paths. Paths move and worktrees add more, and CF already owns this mapping.

### D7 — The `set_up` operation
Status: decided

**Request.** `SetUpRequest`, a frozen pydantic model with `extra="forbid"`. `set_up` takes the parsed document as an unvalidated `object` and validates it into this model itself, so the CLI and 226's MCP tool pass input through unchanged.

```yaml
program: trading                 # required
concept:                         # optional; omitted = unchanged, null = no concept
  member: trading-core           # CF project name or id
  path: project-documents/user/project-guides/000-concept.trading.md
members:                         # optional
  - project: trading-core        # CF project name or id; omitted = the working directory's project
    rules_paths: [CLAUDE.md]     # required when the member is new; replaces the stored list when given
    authorize_allow: [merge_to_main]  # optional; config item keys taken off this member's not-authorized list; replaces the stored list when given
    authorize_deny: [deploy]          # optional; config item keys put on this member's not-authorized list; replaces the stored list when given
    depends_on:                  # optional; upserts these pairs with this member as consumer
      - provider: trading-data   # CF project name or id
        consumed: from_release
```

**Semantics: upsert, never remove.** What the request names is created or set. What it doesn't name is left alone. A list field that is given (`rules_paths`, `authorize_allow`, `authorize_deny`) replaces the stored value whole, so the stored value always equals the last value given. `depends_on` creates each pair or sets its `consumed`. Pairs not listed are untouched.

**Checks.** Each check runs against the state the request would produce, inside the transaction. Every problem is collected, and any problem rejects the whole request. A problem is `SetUpProblem(code, detail)`, and `code` is the closed `SetUpProblemCode`:

| Code | When |
|---|---|
| `malformed` | The document fails `SetUpRequest` validation (one problem per pydantic error) |
| `not_a_project` | A reference, or the working directory for an omitted `project`, is no Context Forge project |
| `empty_program` | The program doesn't exist and the request adds no member |
| `member_of_other_program` | A named member already belongs to a different program |
| `rules_paths_required` | A new member has no `rules_paths` |
| `unknown_provider` | A `depends_on` provider is not a member of this program after the request |
| `self_dependency` | A member lists itself as a provider |
| `unknown_authorize_item` | An `authorize_allow` or `authorize_deny` key is not an `authorize_items` key in the config |
| `concept_member_not_member` | `concept.member` is not a member of this program after the request |

Paths (`rules_paths`, `concept.path`) use the repo-relative rule kept with `AnswererSettings`, and a bad path is a `malformed` problem. A member listed twice in one request, after resolution, is `malformed`, and so is a key in both of a member's authorize lists.

**Result.** `SetUpResult`:

- `outcome`: `applied`, `unchanged` or `rejected`.
- `changes`: one line per created or changed row (for example `member project_17… created`, `pair project_17… → project_18… consumed from_source → from_release`). Empty when the outcome is `unchanged` or `rejected`.
- `problems`: empty unless the outcome is `rejected`.
- `program`: the program's state after the call. That is its concept, and each member's id, rules paths, authorize lists and pairs, read inside the same transaction. On `rejected` it is the unchanged state, or null if the program doesn't exist.
- `working_directory`: the resolution of the caller's directory (D6): `{member, program}`, `{not_in_program: <cf id>}` or `{not_a_project: <message>}`. The `cf` call is made before the transaction, and the membership is read inside it, so this field reflects the committed state. It is informational: `not_a_project` here is a problem only when a member entry omits `project`.

A repeat of an applied request writes nothing and returns `unchanged`. `updated_at` moves only when a value changes. A request naming only `program` is the read-back: it returns the program's state as `unchanged`, or `empty_program` if the program doesn't exist.

Rejected: a whole-program declaration that the store is made to match. A member registering itself from its own repo would then have to restate every other member, or remove them. Rejected: removal in this slice. A mistaken registration is rare. Until removal exists, a pair's `consumed` can be changed by upsert, and anything else is fixed by hand in SQLite (Future Work).

### D8 — A member's answering settings
Status: decided

`operations.member_answering.answering_for(member_settings, config) -> MemberAnswering` is the loader 221 D5 leaves to 222.

- The member's not-authorized items are the config items with `denied_by_default: true` whose key is not in the member's `authorize_allow`, plus the items whose key is in the member's `authorize_deny`, in config order. So a member can take items off the list or put items on it. An item a repo needs that no member has yet is added to the config with `denied_by_default: false`, then denied in that member.
- `MemberAnswering.settings` is an `AnswererSettings`. Its `reserved_terms` are the screen phrases of those items, in order. Its `rules_paths` are the member's. Its `answer_limit`, `passages_max_chars`, `answer_model`, `check_model` and `max_cost_usd` come from the config.
- `MemberAnswering.not_authorized` is the tuple of those items, keys and descriptions included. 223 decides how the descriptions reach the answer and check steps.
- An `authorize_allow` or `authorize_deny` key the config no longer has raises `ConfigError` naming the member and the key. Config edits after `set_up` are caught here, at use.

So allowing an item for a member removes it from both what the models are told and what the screen matches. 223's criterion "allowing that item for the member lets the same kind of answer through" rests on this.

### D9 — The CLI
Status: decided

- `[project.scripts] amoeba = "amoeba.cli.main:main"` returns. `argparse`, one subcommand per operation, named exactly as the operation (`set_up`), so the CLI and MCP share one set of names.
- `amoeba set_up --file <path|->`. There are no per-field flags. The nested member settings would make flags a second, lossy request format.
- Output is the `SetUpResult` as JSON on stdout. Agents are the expected callers.
- The CLI's only request handling is reading the text and `yaml.safe_load`. A file it can't read (`OSError`), text that isn't UTF-8, or text that isn't YAML is a usage error: it prints `error: RequestDocumentError: <path or stdin>: <reason>` on stderr and exits 2, before the config or store is touched. A document that parses but is the wrong shape goes to `set_up`, which rejects it as `malformed` (D7).
- Exit codes are named constants in `cli/main.py`: `0` for `applied` or `unchanged`, `1` for `rejected`, `2` for a usage error (argparse's own, or an unreadable request document), and `3` for an operational error (`ConfigError`, `AmoebaHomeError`, `ContextForgeError`, any `StoreError`). An operational error prints `error: <ExceptionName>: <message>` on stderr and nothing on stdout.
- The CLI is the process boundary. It is the one top-level handler that catches these typed errors, under the project's exception rule (c).

### D10 — Tests never touch the real home
Status: decided

- An autouse fixture in `tests/conftest.py` sets `AMOEBA_HOME` to a fresh per-test temporary directory with `monkeypatch.setenv`. Subprocesses started by a test inherit it.
- `tests/config/test_home.py` checks:
  - With the variable set, `store_path()` and `config_path()` are under it.
  - Under the fixture, `amoeba_home()` is not `Path.home() / ".config" / "amoeba"`.
  - With the variable unset, `XDG_CONFIG_HOME` set and `Path.home` patched to a temporary directory, the home is `<patched home>/.config/amoeba`, which shows that XDG is ignored.
  - An empty or relative value raises `AmoebaHomeError`.
- An AST test checks that no module under `src/amoeba` other than `config/home.py` contains the string `AMOEBA_HOME` or calls `Path.home`. So nothing else picks the location.
- Tests that need `cf` inject a fake `CfRun`. Subprocess CLI tests put a fake `cf` script first on `PATH`. The script replays recorded `cf get --json` outputs, and the recordings (D11) are its data.

### D11 — Fixtures from real Context Forge output
Status: decided

`tests/fixtures/context_forge/` holds the actual output of CF 0.19.26:

- `cf get --json` in a default worktree.
- The same in a non-default worktree of the same project.
- The same in a subdirectory of a checkout (`project-documents/user`). On 20261107 this gave the same `id` as the repo root.
- The `PROJECT_NOT_FOUND` error document from a directory in no project.

The `project_of` parser is tested on these files, as the project's parsing rules require.

### Technology Choices

- SQLite through the standard library `sqlite3`, in WAL mode, as in the old store.
- pydantic v2 for `UserConfig` and `SetUpRequest`. Both are validated from `yaml.safe_load` output.
- `argparse` for the CLI. One subcommand now, eight at most, so a CLI library is not justified.

### Patterns and Conventions

- Every vocabulary value is defined once in a `StrEnum`, and a test pins each SQL `CHECK` list to its enum.
- Every error is a typed exception with a message that names the path, key or value. There are no silent defaults: an absent optional field in a request means "unchanged", and that is the only meaning absence has.
- Store methods take an open transaction. `set_up` owns the one transaction per call.
- Every module carries a docstring, and the ~300-line file and ~50-line function limits apply.

## Implementation Details

### API Contracts

**CLI**

```
amoeba set_up --file <path>|-
```

| Exit | Meaning | stdout | stderr |
|---|---|---|---|
| 0 | `applied` or `unchanged` | `SetUpResult` JSON | — |
| 1 | `rejected` | `SetUpResult` JSON with `problems` | — |
| 2 | usage error, or a request document that can't be read or isn't YAML | — | argparse usage, or `error: RequestDocumentError: <source>: <reason>` |
| 3 | operational error | — | `error: <ExceptionName>: <message>` |

**Python (for 223, 224, 226, 227)**

- `config.home.amoeba_home()`, `store_path()`, `config_path()`
- `config.user_config.load_user_config(path) -> UserConfig`
- `store.store.Store.open(path)`, plus `Store.write()` and `Store.read()`, context managers that yield a transaction (`BEGIN IMMEDIATE` and `BEGIN` respectively)
- `store.programs`: `get_program`, `get_member`, `members_of`, `pairs_of`, `member_settings`, and the upserts `set_up` uses
- `operations.members.resolve_member(store, directory, run)`
- `operations.set_up.set_up(store, config, document: object, *, directory, run) -> SetUpResult`, which validates `document` itself
- `operations.member_answering.answering_for(member_settings, config) -> MemberAnswering`

### Database / Storage Schema

D3 has the tables. `docs/store-contract.md` gets the full DDL meaning: each column, its vocabulary, which slice writes it, and the rule that later changes are new numbered migrations. `docs/config-contract.md` gets the D5 keys, the error forms and an example `config.yaml` with the architecture's default not-authorized list.

## Integration Points

### Provides to Other Slices

- **223**: `resolve_member` (handle only runs in a program member), `answering_for` (settings, screen phrases and not-authorized descriptions per member), the `questions` and `answers` tables with their state and outcome vocabularies, the store's write transaction for the claim, and `Store.open` and `load_user_config` for its CLI commands. Config keys 223 needs (resume wait) are added by 223 under D5's rule. The errors listed in D9 can happen in `handle_pause` before any claim. Started from the detached hook, they would reach only stderr, so 223 decides where they become a record that `status` can show.
- **224**: the `answers.seq` order and `pm_marker` for `decisions` and `mark_read`, members and programs for `status`, and a schema with no mirrored run or slice state.
- **226**: `SetUpRequest` and `set_up` to wrap. The request model is the MCP tool's input schema, and the result model is its output.
- **227**: the `dependency_pairs` with `consumed` and the `releases` table.

### Consumes from Other Slices

- **221**: `AnswererSettings` and its types, the answering values, and `cli_call`. If 221 places any of them elsewhere, 222 imports from wherever the audit records it. Nothing is re-created.
- **Context Forge**: `cf get --json`. If `cf` is missing or fails, every caller gets `ContextForgeError` with the output head. Nothing degrades silently.

## Success Criteria

### Functional Requirements

- `amoeba set_up` with a valid request creates the program, its members, their settings and their pairs, and returns `applied` with one change line per row.
- The same request again returns `unchanged`, writes nothing, and leaves every `updated_at` as it was.
- A request naming only `program` returns that program's state.
- A malformed request, and each check in D7's table, is rejected with its code and a detail naming the field or member, and the store is unchanged.
- A request file that is missing, not UTF-8 or not YAML exits 2 with `RequestDocumentError` on stderr. A YAML document that isn't a mapping is `rejected` as `malformed`.
- When `cf` fails, `set_up` raises `ContextForgeError` (exit 3) and the store is unchanged.
- An omitted `project`, run from two worktrees of one repo, resolves to the same member. Run from a directory that is a CF project but no member, `working_directory` is `not_in_program`. From a directory that is no CF project, it is `not_a_project`.
- `answering_for` gives a member with `authorize_allow: [merge_to_main]` settings whose `reserved_terms` and `not_authorized` lack that item's phrases and description, while another member keeps them. A member with `authorize_deny` naming a `denied_by_default: false` item gets that item, and other members don't.
- A missing config file, and a config missing any one D5 key, each fail with exit 3 and a message naming the file or the key.

### Technical Requirements

- `ruff format --check`, `ruff check`, `pyright` (strict) and `pytest` pass.
- The D10 tests pass. The fixture redirects every test, XDG is ignored, and only `config/home.py` names `AMOEBA_HOME` or calls `Path.home`.
- A concurrency test starts 8 processes against one new store (no file at the start). Each calls `set_up` for the same program with a different member, through an injected resolver. Every process returns `applied` or raises `StoreBusyError`, the store ends with every member whose process applied, and nothing else is raised.
- A test holds a write transaction open and calls `set_up` with `busy_timeout_seconds` set to 0.2. It gets `StoreBusyError` naming the path.
- A test opening a store stamped with a higher version gets `StoreSchemaError`, and the file is unchanged.
- Each `CHECK` vocabulary is pinned to its enum by a test.
- The `project_of` parser passes on the D11 fixtures.
- `tests/test_import_boundaries.py` enforces the direction in Component Structure.
- The built wheel contains `amoeba/store/schema/001_baseline.sql`.
- `docs/store-contract.md` and `docs/config-contract.md` exist and match the code.

### Integration Requirements

- 223 can resolve a run's member, get its answering settings and open a write transaction without adding to `config` or the program tables.
- 226 can expose `set_up` by passing its MCP input to `set_up` and returning `SetUpResult`, with no logic of its own.

### Verification Walkthrough

Run from the amoeba repo root. Steps 1 to 5 use a scratch home, so the real `~/.config/amoeba` is untouched until the PM chooses to set up for real (step 7).

1. **Checks.**
   ```bash
   uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest
   ```
   Expected: all pass.

2. **Missing config is named.**
   ```bash
   export AMOEBA_HOME="$(mktemp -d)"
   printf 'program: demo\n' | uv run amoeba set_up --file -; echo "exit $?"
   ```
   Expected: `error: ConfigError: no config at $AMOEBA_HOME/config.yaml; see docs/config-contract.md`, exit 3. Copy the example from `docs/config-contract.md` to `$AMOEBA_HOME/config.yaml`, delete its `answer_limit` line and rerun. Expected: an error naming `answer_limit`, exit 3. Restore the line.

3. **Set up a program from inside a member.**
   ```bash
   cat > /tmp/demo.yaml <<'EOF'
   program: demo
   members:
     - rules_paths: [CLAUDE.md]
       authorize_allow: [merge_to_main]
   EOF
   uv run amoeba set_up --file /tmp/demo.yaml; echo "exit $?"
   ```
   Expected: `"outcome": "applied"`, a change line creating program `demo` and the amoeba project as a member. `program.members` lists amoeba's CF project id (the `id` from `cf get --json`) with `rules_paths` and `authorize_allow: ["merge_to_main"]`. `working_directory` names that member and `demo`. Exit 0.

4. **Repeat, read back, reject.**
   - Rerun the same command. Expected: `"outcome": "unchanged"`, empty `changes`, exit 0.
   - `printf 'program: demo\n' | uv run amoeba set_up --file -`. Expected: the same `program` state, `unchanged`.
   - `printf 'program: demo\nmembers:\n  - depends_on: [{provider: nosuch, consumed: from_source}]\n' | uv run amoeba set_up --file -`. Expected: `rejected`, a `not_a_project` problem naming `nosuch`, exit 1. The read-back shows no change.
   - `printf 'program: demo\nmembers:\n  - rules_paths: [/etc/passwd]\n' | uv run amoeba set_up --file -`. Expected: `rejected`, `malformed`, with the detail that the path must be relative.

5. **Worktrees and non-members.**
   - In a repo with two worktrees registered in Context Forge (`cf worktree list --json` lists them), register it from the first worktree with a request like step 3's, run with `uv run --project <amoeba repo> amoeba set_up --file /tmp/demo.yaml`. Then run `printf 'program: demo\n' | uv run --project <amoeba repo> amoeba set_up --file -` from the second worktree. Expected: `working_directory` names the same member id in both.
   - From a CF project that is not in `demo`, the read-back shows `{"not_in_program": "<its cf id>"}`. From `/tmp`, it shows `{"not_a_project": "..."}`. Both exit 0.

6. **Concurrency.** `uv run pytest tests/store/test_concurrent_writers.py -v`. Expected: passes, and the output shows 8 processes.

7. **Real set-up (when the PM is ready).** `unset AMOEBA_HOME`, write `~/.config/amoeba/config.yaml` from the contract doc, and run step 3's request with the real program name in each member repo. 223 builds on this.

## Implementation Notes

### Development Approach

Suggested order, each step ending with the checks passing:

1. `config/home.py`, the D10 fixture and the home tests.
2. `config/user_config.py` and `docs/config-contract.md`.
3. `store/`: vocabulary, the baseline migration, `Store.open`, transactions, typed errors, the pinning tests, and the concurrency and busy tests. `docs/store-contract.md`.
4. `upstream/context_forge/project_of.py` with the D11 fixtures, then `operations/members.py`.
5. `store/programs.py`, `operations/set_up.py` and `operations/member_answering.py`, with unit tests for every D7 check and the upsert semantics.
6. `cli/main.py`, the entry point, the fake-`cf` subprocess tests, packaging, and the import-boundary rules.
7. The Verification Walkthrough. Record the results in the task notes.

Effort: 3.

### Special Considerations

- **Security.** The config holds model aliases and limits, never credentials, and the contract doc says so. The store holds question and answer text from the PM's own repos. It lives in the PM's home directory with the default file mode.
- **Store growth.** Not a concern at one PM's question volume. No pruning is designed.

## Future Work

- **Removing members and pairs through `set_up`.** Add explicit `remove` entries if use shows mistaken registrations happen. A member with question records would be refused, to keep the record exact. Effort: 1/5.
