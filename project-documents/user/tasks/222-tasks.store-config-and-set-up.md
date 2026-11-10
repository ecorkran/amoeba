---
docType: tasks
slice: store-config-and-set-up
project: amoeba
lld: user/slices/222-slice.store-config-and-set-up.md
dependencies:
- 221-slice.the-cut
projectState: Slice 221 is merged. `src/amoeba` holds only `answering/` and `upstream/`.
  No store, config, or command exists. Nobody has run Amoeba.
dateCreated: 20261107
dateUpdated: 20261108
status: in_progress
turns: 9
promptTokens: 259263
cachedTokens: 215714
cacheWriteTokens: 43537
completionTokens: 11652
durationSeconds: 72.0
costUsd: 0.31256
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.3125598
    completionTokens: 11652
---

# Tasks: Store, Config and Set-up

## Context Summary

- Working on slice 222 (design: `user/slices/222-slice.store-config-and-set-up.md`; decisions D1 to D11 are cited below by number).
- Adds `config/` (home, user config), `store/` (SQLite, migrations, baseline schema, program reads and upserts), `operations/` (member resolution, `set_up`, `answering_for`), the `amoeba` CLI, and `upstream/context_forge/project_of.py`.
- Every closed vocabulary is a `StrEnum`; a test pins each SQL `CHECK` list to its enum. No config key has a default in code.
- Import direction (design, Component Structure) is enforced by a test added in task 10.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`. "Checks pass" means all four.
- Where slice 221 placed `AnswererSettings`, `RulesPath`, `ModelAlias`, `validate_repo_relative_path`, `AnsweredBy` or `cli_call` differently from the design, import from where the audit's Verdicts (`user/analysis/220-analysis.code-audit.md`) record them.
- Work on branch `222-slice.store-config-and-set-up`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.
- Next slices: 223 pause handling, 224 status and decisions, 226 MCP server, 227 program dependencies.

## 0. Setup

- [x] **0.1 Create the branch**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty
  - [x] Confirm the working tree is clean and you are on the target
  - [x] `git checkout -b 222-slice.store-config-and-set-up {target}`
  - [x] Success: `git branch --show-current` prints `222-slice.store-config-and-set-up`
  - Note: target is main (integration_branch empty); branch 222-slice.store-config-and-set-up created from main.

- [x] **0.2 Confirm slice 221 and locate its types**
  - [x] Confirm `src/amoeba` has `answering/` and `upstream/` and no `store/` or `cli/`; if not, write `BLOCKED: slice 221 not merged` under this task and stop
  - [x] Find the module of each of `AnswererSettings`, `RulesPath`, `ModelAlias`, `validate_repo_relative_path`, `AnsweredBy`, `run_cf`, `CfRun`, `CfCallFailed`; note the import paths under this task
  - [x] Run the checks once and note the baseline result; failures present before this slice are written down, not fixed
  - [x] Success: a note lists each import path and the baseline result
  - Note: import paths — AnswererSettings, RulesPath, ModelAlias, validate_repo_relative_path: amoeba.answering.settings; AnsweredBy: amoeba.answering.values; run_cf, CfRun, CfCallFailed: amoeba.upstream.context_forge.cli_call (no CfRun/CfCallFailed move; all as the design states). src/amoeba holds answering/ and upstream/ only. Baseline: ruff format, ruff check, pyright clean; pytest 544 passed.

## 1. Test infrastructure

- [x] **1.1 Autouse `AMOEBA_HOME` fixture (D10)**
  - [x] In `tests/conftest.py` (create or extend) add an autouse fixture that sets `AMOEBA_HOME` to a fresh temporary directory per test and restores it afterwards
  - [x] Success: a throwaway test reading `os.environ["AMOEBA_HOME"]` sees a different directory in two tests and never the real `~/.config/amoeba`

- [x] **1.2 Record Context Forge fixtures (D11)**
  - [x] Create `tests/fixtures/context_forge/` holding real `cf get --json` stdout from: a default worktree, a non-default worktree of the same project, a subdirectory of a checkout, and a directory outside any project (the `PROJECT_NOT_FOUND` document). Name each file for its case
  - [x] Capture by running `cf get --json` in each place, using `git worktree add` on a throwaway checkout of this repo for the non-default worktree; do not hand-write any fixture
  - [x] Add `tests/fixtures/context_forge/README.md` recording the `cf --version` and capture date
  - [x] If a case cannot be captured, write `BLOCKED: cannot record <case>` under this task and stop
  - [x] Success: four files exist; each parses as JSON; the subdirectory and root fixtures have the same `id`
  - Note: cf 0.19.26, captured 20261109. The PROJECT_NOT_FOUND document is on stderr (exit 1), so outside_any_project.json holds the stderr text. The non-default worktree was registered with `cf worktree init --name fixture-wt --range 800-899 -o` on a throwaway checkout, then removed (cf worktree rm, git worktree remove).

- [x] **1.3 Fake `cf` and `CfRun` helpers**
  - [x] Add test helpers: a function returning a fake `CfRun` that replays a named fixture or a given failure, and a script writer that places a fake `cf` first on `PATH` (for the CLI subprocess tests in task 10.3). The script is written for one mode: replay a named fixture, or fail (nonzero exit, no JSON)
  - [x] Success: calling the fake `CfRun` with the default-worktree fixture name returns that fixture's text; running the written failure-mode script exits nonzero
  - Note: helpers in tests/cf_fixtures.py (fake_cf_run, write_fake_cf); tests in tests/test_cf_fixtures.py. A throwaway-style home test is kept as tests/test_amoeba_home_fixture.py.

**Commit**: `test: add AMOEBA_HOME fixture and Context Forge recordings`

## 2. Home

- [ ] **2.1 Implement `config/home.py` (D1)**
  - [ ] Create `src/amoeba/config/__init__.py` and `home.py` with `amoeba_home()`, `store_path()`, `config_path()` and `AmoebaHomeError`
  - [ ] `amoeba_home()` reads `AMOEBA_HOME` at call time; unset gives `Path.home() / ".config" / "amoeba"`; set but empty or relative raises `AmoebaHomeError`; `XDG_CONFIG_HOME` is never read
  - [ ] File names `amoeba.sqlite3` and `config.yaml` are constants defined once in `home.py`
  - [ ] Success: module imports; pyright strict is clean on it

- [ ] **2.2 Home tests (D10)**
  - [ ] `tests/config/test_home.py`: paths sit under `AMOEBA_HOME`; the fixture's home is not the real default; with the variable unset and `XDG_CONFIG_HOME` set, the default is used; empty and relative values raise `AmoebaHomeError`
  - [ ] Success: tests pass

- [ ] **2.3 AST test for the one read of `AMOEBA_HOME`**
  - [ ] `tests/test_home_access.py`: parse every module under `src/amoeba` except `config/home.py`; fail if any contains the string `AMOEBA_HOME` or calls `Path.home`. Reuse `tests/ast_strings.py` helpers if they fit
  - [ ] Success: test passes; adding `Path.home()` to another module makes it fail (verify once, then revert)

**Commit**: `feat: add Amoeba home resolution`

## 3. Store

- [ ] **3.1 Vocabulary and models (D3)**
  - [ ] `store/vocabulary.py`: `ConsumedMode` (`from_source`, `from_release`), `QuestionState` (`claimed`, `answered`, `waiting_on_pm`), `ResumeOutcome` (`resumed`, `refused`, `not_delivered`), all `StrEnum`
  - [ ] `store/models.py`: frozen `Program`, `Member`, `MemberSettings`, `DependencyPair` carrying the columns in D3's tables
  - [ ] Success: modules import; pyright strict clean

- [ ] **3.2 Baseline schema (D3)**
  - [ ] `store/schema/001_baseline.sql` creating `schema_meta`, `programs`, `members`, `dependency_pairs`, `releases`, `questions`, `answers`, `pm_marker` with the columns, keys, foreign keys, `UNIQUE` and `CHECK` constraints of D3's table (including the composite foreign keys that stop a pair crossing programs and `CHECK (provider_id <> consumer_id)`)
  - [ ] `answered_by` CHECK values come from `answering.values.AnsweredBy`; all other CHECK lists from `store/vocabulary.py`
  - [ ] `pm_marker` is created with its single row at `last_seen_seq` 0; `schema_meta` is stamped by migrations (3.3), not here
  - [ ] Success: the file runs against an empty in-memory SQLite database without error

- [ ] **3.3 Migrations (D4)**
  - [ ] `store/migrations.py`: `EXPECTED_SCHEMA_VERSION` equal to the highest numbered file in `store/schema/`; a `migrate(connection)` that, inside `BEGIN IMMEDIATE`, reads the stored version (0 when the `schema_meta` table does not exist yet, as on a new store), applies missing files in order, and stamps the version
  - [ ] A store stamped higher than `EXPECTED_SCHEMA_VERSION` raises `StoreSchemaError` and is left untouched
  - [ ] Success: migrating an empty database yields version 1 and all eight tables

- [ ] **3.4 `Store` (D2)**
  - [ ] `store/store.py`: `BUSY_TIMEOUT_SECONDS = 5.0` defined once; typed errors `StoreError` and subclasses `StoreBusyError`, `StorePermissionError`, `StoreCorruptError`, `StoreSchemaError`
  - [ ] `Store.open(path, *, busy_timeout_seconds=BUSY_TIMEOUT_SECONDS)` creates the parent directory, sets the busy timeout at connect, `journal_mode=WAL`, `foreign_keys=ON`, then migrates; `Store.write()` yields a `BEGIN IMMEDIATE` transaction and `Store.read()` a `BEGIN` one, each committing or rolling back on exit
  - [ ] A busy timeout raises `StoreBusyError` naming the path and timeout; each other open failure maps to its typed error. No lock file, pid file or read-only mode
  - [ ] `store/sql.py` defines the `BEGIN IMMEDIATE` statement once (`BEGIN_IMMEDIATE`) and the statement constants; `Store.write()` and `migrate()` both use it. `store/row_values.py` holds `decode_mapping`, `decode_timestamp` and the typed column reads. Slice 221 deleted the old store and moved none of these, so write them here; the old `sql_inbox.py`, `mapping_journal.py`, `row_values.py` and `connection.py` in the commit 221 branched from may be restored and adapted
  - [ ] Success: opening a path in a missing directory creates it and the store; `git grep -n "BEGIN IMMEDIATE" src` finds the statement text in one place only

- [ ] **3.5 Store tests**
  - [ ] `tests/store/test_store.py`: open creates the store; reopen applies nothing; a store stamped higher raises `StoreSchemaError` and its bytes are unchanged; a held write transaction in a second connection with `busy_timeout_seconds=0.2` gives `StoreBusyError`; an unwritable directory gives `StorePermissionError`; a non-database file gives `StoreCorruptError`; a failed `write()` block rolls back
  - [ ] `tests/store/test_schema.py`: foreign keys are enforced (a pair across programs, a pair with equal ends, a member of a missing program all fail); `pm_marker` holds one row at 0
  - [ ] Success: tests pass

- [ ] **3.6 Vocabulary pinning test**
  - [ ] `tests/store/test_vocabulary_pinning.py`: for each `CHECK` list in `001_baseline.sql` (`consumed`, `state`, `answered_by`, `resume_outcome`), parse the list from the SQL text and assert it equals the values of the matching enum
  - [ ] Success: test passes; adding a value to an enum alone makes it fail (verify once, then revert)

- [ ] **3.7 Store test helpers (design, Audit items)**
  - [ ] `tests/store/seed.py`: functions that insert a program, member, dependency pair, question and answer row through the `store/sql.py` constants, inside a given `Store.write()` transaction; every column value is an argument, none has a default. Used by this slice's store tests and left for 223 and 224 to seed any state
  - [ ] Rewrite `tests/fault_injection.py` for the new `Store` (fail one named SQL statement in a transaction with a chosen exception); if slice 221 deleted it, restore it from the commit 221 branched from and adapt it. It has no node-specific helper
  - [ ] Add to `tests/store/test_store.py`: with a fault injected on the second insert of a `Store.write()` block that first inserted a program, no program row remains
  - [ ] Success: the seed helper builds a program with a member, a pair, a `claimed` question and an `answerer` answer, and a read-back matches (programs, members and pairs through `store/programs.py`; question and answer rows by `SELECT`); the fault-injection test passes

**Commit**: `feat: add SQLite store with baseline schema and migrations`

## 4. User config

- [ ] **4.1 Implement `config/user_config.py` (D5)**
  - [ ] Frozen pydantic models `UserConfig` and `NotAuthorizedItem`, both `extra="forbid"` with no field defaults, fields and constraints as in D5's tables (`answer_model` and `check_model` as `ModelAlias`; `max_cost_usd` > 0; `answer_limit` and `passages_max_chars` ≥ 1; `authorize_items` may be empty with unique `key`)
  - [ ] `load_user_config(path)` raises `ConfigError` listing every problem in one pass, each naming the file and key: missing file ("no config at <path>; see docs/config-contract.md"), not UTF-8, not YAML, missing key, unknown key, bad value
  - [ ] Success: modules import; pyright strict clean

- [ ] **4.2 Config contract doc and example**
  - [ ] Write `docs/config-contract.md` (with YAML frontmatter per `file-naming-conventions.md`): each key, its type and meaning, and one complete example whose `authorize_items` are the five defaults named in the design's D5 (including the item keyed `merge_to_main`), all `denied_by_default: true`
  - [ ] Success: the example block is valid YAML; the doc names every D5 key

- [ ] **4.3 Config tests**
  - [ ] `tests/config/test_user_config.py`: the example from `docs/config-contract.md` loads (extract it from the doc, do not copy it); parametrized, removing each one key in turn raises `ConfigError` naming that key; unknown key, bad value, duplicate item `key`, missing file, non-UTF-8 and non-YAML each raise `ConfigError` naming the file; two problems in one file are both listed
  - [ ] Success: tests pass

**Commit**: `feat: add user config loading and contract doc`

## 5. Project lookup (Context Forge)

- [ ] **5.1 Implement `upstream/context_forge/project_of.py` (D6)**
  - [ ] Frozen `CFProject` (`id`, `name`, `project_path` from `projectPath`; other fields ignored) and `CFProjectNotFound` (CF's message)
  - [ ] `project_of(*, directory=None, reference=None, run)` runs `cf get --json` with `cwd=directory` or with `-p <reference>`, via the injected `CfRun`; a `PROJECT_NOT_FOUND` document on either stream gives `CFProjectNotFound`; any other failure or unparseable output gives `CfCallFailed` quoting the output head
  - [ ] Module imports nothing from `answering` or the new packages
  - [ ] Success: pyright strict clean

- [ ] **5.2 `project_of` tests**
  - [ ] `tests/upstream/context_forge/test_project_of.py`: parse each task 1.2 fixture; default and non-default worktree fixtures give the same `id`; the subdirectory fixture gives the root's `id`; the not-found fixture gives `CFProjectNotFound` with the message; garbage output and a nonzero exit with no document give `CfCallFailed`; with `reference` the argument list contains `-p` and the reference
  - [ ] Success: tests pass

**Commit**: `feat: add Context Forge project lookup`

## 6. Program reads and upserts

- [ ] **6.1 Reads in `store/programs.py`**
  - [ ] `get_program`, `get_member`, `members_of`, `pairs_of`, `member_settings`, each taking an open transaction and returning the task 3.1 models (JSON columns decoded into tuples)
  - [ ] `store/` imports nothing from `config` or `operations`
  - [ ] Success: pyright strict clean

- [ ] **6.2 Upserts in `store/programs.py`**
  - [ ] Upserts for program (with concept pair), member (rules paths, authorize lists), and dependency pair (`consumed`)
  - [ ] Each upsert writes and moves `updated_at` only when a stored value changes, and returns whether it changed; `registered_at` and `updated_at` are UTC ISO-8601 text, with the clock passed in so tests control it
  - [ ] Success: a second identical upsert returns "unchanged" and leaves `updated_at` as it was

- [ ] **6.3 Programs tests**
  - [ ] `tests/store/test_programs.py`: create then read back each of program, member, pair; an unchanged upsert keeps `updated_at`; a changed value moves it; a list field replaces whole; `concept_member` and `concept_path` both null or both set; a member in a second program is refused by the unique key
  - [ ] Success: tests pass

**Commit**: `feat: add program, member and pair store access`

## 7. Member resolution

- [ ] **7.1 Implement `operations/members.py` (D6)**
  - [ ] `ContextForgeError`; `NotInProgram` (CF id) and `NotAProject` (CF message); `resolve_member(store, directory, run) -> Member | NotInProgram | NotAProject`
  - [ ] `CfCallFailed` from `project_of` is raised as `ContextForgeError`; no worktree logic of Amoeba's own
  - [ ] Success: pyright strict clean

- [ ] **7.2 Resolution tests**
  - [ ] `tests/operations/test_members.py`: a registered member's default worktree and non-default worktree fixtures both give the same `Member`; the subdirectory fixture gives it too; a CF project outside the program gives `NotInProgram` with its id; the not-found fixture gives `NotAProject`; a failing `cf` raises `ContextForgeError`
  - [ ] Success: tests pass

**Commit**: `feat: add member resolution`

## 8. `set_up`

- [ ] **8.1 Request and result models (D7)**
  - [ ] `operations/set_up.py`: frozen, `extra="forbid"` pydantic `SetUpRequest` (program, optional concept where omitted differs from null, optional members with `project`, `rules_paths`, `authorize_allow`, `authorize_deny`, `depends_on` entries of `provider` and `consumed`), `SetUpProblemCode` enum with the nine codes of D7, `SetUpProblem(code, detail)`, and `SetUpResult` (`outcome`, `changes`, `problems`, `program`, `working_directory`)
  - [ ] `rules_paths` entries use the repo-relative path validation type from slice 221; `concept.path` uses `validate_repo_relative_path`
  - [ ] Success: pyright strict clean

- [ ] **8.2 Validation and resolution phase (D7, Data Flow steps 2 and 3)**
  - [ ] `set_up(store, config, document: object, *, directory, run)` validates `document` itself; each pydantic error becomes a `malformed` problem, plus `malformed` for a member listed twice after resolution and for a key in both authorize lists
  - [ ] Resolve the working directory and every member reference (and `concept.member`, providers) to CF ids through `project_of` before the first `Store.write()` (the `Store` is passed in already open; no subprocess runs under the write lock); an omitted `project` uses the working directory; a missing project gives `not_a_project`; `ContextForgeError` propagates before anything is written
  - [ ] Success: a `cf` failure with a fake `CfRun` raises `ContextForgeError` and the store has no rows

- [ ] **8.3 Validation tests**
  - [ ] `tests/operations/test_set_up_validation.py`: a non-mapping document, a missing `program`, an unknown field, a non-repo-relative `rules_paths` and `concept.path`, a member listed twice via name and id, and a key in both authorize lists each give `malformed` with a detail naming the field; a bad reference and a bad working directory with omitted `project` give `not_a_project`
  - [ ] Success: tests pass; each rejection leaves the store empty

- [ ] **8.4 Checks (D7)**
  - [ ] Inside one `Store.write()` read current state, compute the state the request would produce, run the remaining checks (`empty_program`, `member_of_other_program`, `rules_paths_required`, `unknown_provider`, `self_dependency`, `unknown_authorize_item`, `concept_member_not_member`), and collect all problems
  - [ ] Any problem: roll back and return `rejected` with the unchanged state (null `program` if it does not exist). With no problems, this task stops after the checks; 8.6 adds the writes
  - [ ] Success: pyright strict clean

- [ ] **8.5 Check tests**
  - [ ] `tests/operations/test_set_up_checks.py`: one test per remaining D7 code, each asserting the code, a detail naming the field or member, and an unchanged store; two problems in one request are both returned
  - [ ] Success: tests pass

- [ ] **8.6 Writes and result (D7)**
  - [ ] No problems: upsert (never remove; a given list replaces the stored value) and return `applied` with one `changes` line per created or changed row, or `unchanged` with nothing written
  - [ ] `program` is read in the same transaction; `working_directory` is built from the working-directory lookup already made in 8.2 (no new `cf` call): not found gives `{not_a_project: <CF message>}`; otherwise `get_member` on the CF id in the same transaction, after any writes, gives `{member, program}` when found and `{not_in_program: <CF id>}` when not. A request naming only `program` is the read-back
  - [ ] Success: pyright strict clean

- [ ] **8.7 Outcome tests**
  - [ ] `tests/operations/test_set_up_outcomes.py`: a valid request creates program, members, settings and pairs and returns `applied` with one change line per row; the same request returns `unchanged` and every `updated_at` stays; changing one value changes only that row; a program-only request reads back; `concept: null` clears the concept and an omitted `concept` leaves it; `not_in_program` and `not_a_project` appear in `working_directory`
  - [ ] Omitted `project` from two worktrees: with a member registered through the default-worktree fixture, a request with an omitted `project` run with the non-default-worktree fixture (and again with the subdirectory fixture) resolves to the same member and returns `unchanged`
  - [ ] Success: tests pass

- [ ] **8.8 Concurrent `set_up` test**
  - [ ] `tests/operations/test_set_up_concurrent.py`: 8 processes against one new store each call `set_up` for the same program with a different member (fake `CfRun` in each); each returns `applied` or raises `StoreBusyError`, and the store ends with every member that reported `applied`
  - [ ] Success: test passes on five consecutive runs

**Commit**: `feat: add set_up operation`

## 9. Member answering settings

- [ ] **9.1 Implement `operations/member_answering.py` (D8)**
  - [ ] `MemberAnswering` (`settings: AnswererSettings`, `not_authorized`: tuple of items with descriptions) and `answering_for(member_settings, config)`
  - [ ] Not-authorized items: config items with `denied_by_default: true` not in `authorize_allow`, plus items in `authorize_deny`, in config order; `reserved_terms` are those items' screen phrases; `rules_paths` the member's; the remaining fields from the config
  - [ ] An authorize key the config lacks raises `ConfigError` naming the member and key
  - [ ] Success: pyright strict clean

- [ ] **9.2 `answering_for` tests**
  - [ ] `tests/operations/test_member_answering.py`: a member allowing `merge_to_main` lacks that item's phrases and description while another member keeps them; a member denying a `denied_by_default: false` item gets it and others don't; items keep config order; config-sourced fields reach the settings; an unknown authorize key raises `ConfigError` naming member and key
  - [ ] Success: tests pass

**Commit**: `feat: add per-member answering settings`

## 10. CLI, packaging and boundaries

- [ ] **10.1 Implement the CLI (D9)**
  - [ ] `cli/main.py`: `argparse`, subcommand `set_up` with `--file <path|->`, no per-field flags; exit codes as named constants (0 applied or unchanged, 1 rejected, 2 usage or unreadable/non-UTF-8/non-YAML request, 3 `ConfigError`, `AmoebaHomeError`, `ContextForgeError`, any `StoreError`)
  - [ ] Order: read text and `yaml.safe_load` (exit 2 on failure, before config or store), then `load_user_config(config_path())`, open the store at `store_path()`, call `set_up` with the current directory and `run_cf`, print `SetUpResult` JSON to stdout
  - [ ] Errors print `error: <ExceptionName>: <message>` to stderr; this is the one top-level handler; `RequestDocumentError` is defined here and names the source
  - [ ] Only `cli` calls `amoeba_home()`, `store_path()` and `config_path()`
  - [ ] Success: pyright strict clean

- [ ] **10.2 Packaging**
  - [ ] `pyproject.toml`: add `[project.scripts] amoeba = "amoeba.cli.main:main"` and include `src/amoeba/store/schema/*.sql` in the wheel
  - [ ] `tests/test_wheel_contents.py`: build the wheel into a temporary directory with `uv build --wheel --out-dir` and assert its file list contains `amoeba/store/schema/001_baseline.sql`
  - [ ] Success: `uv run amoeba --help` lists `set_up`; the wheel test passes

- [ ] **10.3 CLI tests**
  - [ ] `tests/cli/test_set_up_cli.py`, run as subprocesses with the task 1.3 fake `cf` first on `PATH` and the fixture `AMOEBA_HOME`: valid request from a file and from stdin exits 0 with result JSON; rerun exits 0 `unchanged`; a rejected request exits 1 with JSON; a missing file, non-UTF-8 and non-YAML request exit 2 and no store file is created; a missing config file and a config missing one key exit 3 naming the file or key; a failing `cf` exits 3 with the store unchanged; a store stamped higher exits 3
  - [ ] Success: tests pass

- [ ] **10.4 Import boundary test**
  - [ ] `tests/test_import_boundaries.py`: parse imports under `src/amoeba` and assert the design's direction: `store` imports nothing from `config`, `operations` or `cli`; `upstream` imports nothing from `answering`, `config`, `store`, `operations` or `cli`; `config` imports only `answering.settings` (and its type modules); `operations` does not import `cli`
  - [ ] Success: test passes; adding a forbidden import makes it fail (verify once, then revert)

**Commit**: `feat: add amoeba set_up command and packaging`

## 11. Contract docs and final validation

- [ ] **11.1 Store contract doc**
  - [ ] Replace the content of `docs/store-contract.md` (the old per-project store contract is obsolete after slice 221; if 221 already removed it, create it) with the D3 description: each table and column, its vocabulary, and which slice writes it; the migration rule (no edits to `001`, later migrations `ALTER TABLE … ADD COLUMN` only); the home and `AMOEBA_HOME` rule; frontmatter per `file-naming-conventions.md`
  - [ ] State two derivations the schema deliberately has no column for (design, Audit items): an answering run's scratch directory is `answering_dir() / <answering_run_id>` (223 D6, D12), so `questions.answering_run_id` is its only record; and answering has no per-member switch, since program membership is the opt-in (no `answering_enabled` column, no `answerer:` section equivalent)
  - [ ] Success: every table and column in `001_baseline.sql` appears in the doc, and the doc states both derivations

- [ ] **11.2 Contract match test**
  - [ ] `tests/test_contract_docs.py`: assert every table and column name in `001_baseline.sql` (read from `PRAGMA table_info` on a fresh store) appears in `docs/store-contract.md`, and every `UserConfig` field name appears in `docs/config-contract.md`
  - [ ] Success: test passes

- [ ] **11.3 Full validation and walkthrough**
  - [ ] Checks pass
  - [ ] Run the design's Walkthrough steps 1 to 3 with `AMOEBA_HOME="$(mktemp -d)"`; note each result under this task (step 3's two worktrees: use `git worktree add` on a registered throwaway checkout)
  - [ ] Walk the design's Success Criteria list and note any criterion not covered by a test
  - [ ] Success: all four checks pass; steps 1 to 3 give the documented results (exit 3 `ConfigError: no config at ...`, then `applied` and `unchanged`, then the same member from both worktrees and `not_a_project` from `/tmp`)

**Commit**: `docs: add store and config contracts`
