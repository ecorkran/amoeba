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
dateUpdated: 20261109
status: complete
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

- [x] **2.1 Implement `config/home.py` (D1)**
  - [x] Create `src/amoeba/config/__init__.py` and `home.py` with `amoeba_home()`, `store_path()`, `config_path()` and `AmoebaHomeError`
  - [x] `amoeba_home()` reads `AMOEBA_HOME` at call time; unset gives `Path.home() / ".config" / "amoeba"`; set but empty or relative raises `AmoebaHomeError`; `XDG_CONFIG_HOME` is never read
  - [x] File names `amoeba.sqlite3` and `config.yaml` are constants defined once in `home.py`
  - [x] Success: module imports; pyright strict is clean on it

- [x] **2.2 Home tests (D10)**
  - [x] `tests/config/test_home.py`: paths sit under `AMOEBA_HOME`; the fixture's home is not the real default; with the variable unset and `XDG_CONFIG_HOME` set, the default is used; empty and relative values raise `AmoebaHomeError`
  - [x] Success: tests pass
  - Note: tests/test_store_safety.py no longer forbids store_path/store_dir/DEFAULT_STORE_DIR — store_path() resolves under the per-test AMOEBA_HOME (D10), so it cannot reach the real home; the Squadron and CF directory names stay forbidden.

- [x] **2.3 AST test for the one read of `AMOEBA_HOME`**
  - [x] `tests/test_home_access.py`: parse every module under `src/amoeba` except `config/home.py`; fail if any contains the string `AMOEBA_HOME` or calls `Path.home`. Reuse `tests/ast_strings.py` helpers if they fit
  - [x] Success: test passes; adding `Path.home()` to another module makes it fail (verify once, then revert)

**Commit**: `feat: add Amoeba home resolution`

## 3. Store

- [x] **3.1 Vocabulary and models (D3)**
  - [x] `store/vocabulary.py`: `ConsumedMode` (`from_source`, `from_release`), `QuestionState` (`claimed`, `answered`, `waiting_on_pm`), `ResumeOutcome` (`resumed`, `refused`, `not_delivered`), all `StrEnum`
  - [x] `store/models.py`: frozen `Program`, `Member`, `MemberSettings`, `DependencyPair` carrying the columns in D3's tables
  - [x] Success: modules import; pyright strict clean

- [x] **3.2 Baseline schema (D3)**
  - [x] `store/schema/001_baseline.sql` creating `schema_meta`, `programs`, `members`, `dependency_pairs`, `releases`, `questions`, `answers`, `pm_marker` with the columns, keys, foreign keys, `UNIQUE` and `CHECK` constraints of D3's table (including the composite foreign keys that stop a pair crossing programs and `CHECK (provider_id <> consumer_id)`)
  - [x] `answered_by` CHECK values come from `answering.values.AnsweredBy`; all other CHECK lists from `store/vocabulary.py`
  - [x] `pm_marker` is created with its single row at `last_seen_seq` 0; `schema_meta` is stamped by migrations (3.3), not here
  - [x] Success: the file runs against an empty in-memory SQLite database without error

- [x] **3.3 Migrations (D4)**
  - [x] `store/migrations.py`: `EXPECTED_SCHEMA_VERSION` equal to the highest numbered file in `store/schema/`; a `migrate(connection)` that, inside `BEGIN IMMEDIATE`, reads the stored version (0 when the `schema_meta` table does not exist yet, as on a new store), applies missing files in order, and stamps the version
  - [x] A store stamped higher than `EXPECTED_SCHEMA_VERSION` raises `StoreSchemaError` and is left untouched
  - [x] Success: migrating an empty database yields version 1 and all eight tables
  - Note: migrations run statements one at a time (split_statements) because sqlite3 executescript would commit the open transaction.

- [x] **3.4 `Store` (D2)**
  - [x] `store/store.py`: `BUSY_TIMEOUT_SECONDS = 5.0` defined once; typed errors `StoreError` and subclasses `StoreBusyError`, `StorePermissionError`, `StoreCorruptError`, `StoreSchemaError`
  - [x] `Store.open(path, *, busy_timeout_seconds=BUSY_TIMEOUT_SECONDS)` creates the parent directory, sets the busy timeout at connect, `journal_mode=WAL`, `foreign_keys=ON`, then migrates; `Store.write()` yields a `BEGIN IMMEDIATE` transaction and `Store.read()` a `BEGIN` one, each committing or rolling back on exit
  - [x] A busy timeout raises `StoreBusyError` naming the path and timeout; each other open failure maps to its typed error. No lock file, pid file or read-only mode
  - [x] `store/sql.py` defines the `BEGIN IMMEDIATE` statement once (`BEGIN_IMMEDIATE`) and the statement constants; `Store.write()` and `migrate()` both use it. `store/row_values.py` holds `decode_mapping`, `decode_timestamp` and the typed column reads. Slice 221 deleted the old store and moved none of these, so write them here; the old `sql_inbox.py`, `mapping_journal.py`, `row_values.py` and `connection.py` in the commit 221 branched from may be restored and adapted
  - [x] Success: opening a path in a missing directory creates it and the store; `git grep -n "BEGIN IMMEDIATE" src` finds the statement text in one place only
  - Note: the typed errors live in store/errors.py (not store.py) to avoid an import cycle with migrations.py; also added StoreIntegrityError (constraint refusals) and StoreRowError (bad stored value). Transaction wraps the connection, maps sqlite3 errors, and is what store functions take. `grep -rn "BEGIN IMMEDIATE" src` finds the text only in store/sql.py (git grep ignores untracked files until committed).
  - Note: tests/answering/test_wheel_contents.py no longer asserts the wheel has no .sql file (the schema now ships); task 10.2 adds the positive wheel test.

- [x] **3.5 Store tests**
  - [x] `tests/store/test_store.py`: open creates the store; reopen applies nothing; a store stamped higher raises `StoreSchemaError` and its bytes are unchanged; a held write transaction in a second connection with `busy_timeout_seconds=0.2` gives `StoreBusyError`; an unwritable directory gives `StorePermissionError`; a non-database file gives `StoreCorruptError`; a failed `write()` block rolls back
  - [x] `tests/store/test_schema.py`: foreign keys are enforced (a pair across programs, a pair with equal ends, a member of a missing program all fail); `pm_marker` holds one row at 0
  - [x] Success: tests pass

- [x] **3.6 Vocabulary pinning test**
  - [x] `tests/store/test_vocabulary_pinning.py`: for each `CHECK` list in `001_baseline.sql` (`consumed`, `state`, `answered_by`, `resume_outcome`), parse the list from the SQL text and assert it equals the values of the matching enum
  - [x] Success: test passes; adding a value to an enum alone makes it fail (verify once, then revert)
  - Note: verified once — adding EXTRA to ConsumedMode alone failed the pinning test; reverted.

- [x] **3.7 Store test helpers (design, Audit items)**
  - [x] `tests/store/seed.py`: functions that insert a program, member, dependency pair, question and answer row through the `store/sql.py` constants, inside a given `Store.write()` transaction; every column value is an argument, none has a default. Used by this slice's store tests and left for 223 and 224 to seed any state
  - [x] Rewrite `tests/fault_injection.py` for the new `Store` (fail one named SQL statement in a transaction with a chosen exception); if slice 221 deleted it, restore it from the commit 221 branched from and adapt it. It has no node-specific helper
  - [x] Add to `tests/store/test_store.py`: with a fault injected on the second insert of a `Store.write()` block that first inserted a program, no program row remains
  - [x] Success: the seed helper builds a program with a member, a pair, a `claimed` question and an `answerer` answer, and a read-back matches (programs, members and pairs through `store/programs.py`; question and answer rows by `SELECT`); the fault-injection test passes
  - Note: the read-back in tests/store/test_schema.py uses plain SELECTs for all rows, because store/programs.py does not exist until task 6; task 6.3 adds the read-back through programs.py. Fault injection patches Transaction.execute (tests/fault_injection.py). Helper tests import as `from store.seed import ...` (tests/store is a package).

**Commit**: `feat: add SQLite store with baseline schema and migrations`

## 4. User config

- [x] **4.1 Implement `config/user_config.py` (D5)**
  - [x] Frozen pydantic models `UserConfig` and `NotAuthorizedItem`, both `extra="forbid"` with no field defaults, fields and constraints as in D5's tables (`answer_model` and `check_model` as `ModelAlias`; `max_cost_usd` > 0; `answer_limit` and `passages_max_chars` ≥ 1; `authorize_items` may be empty with unique `key`)
  - [x] `load_user_config(path)` raises `ConfigError` listing every problem in one pass, each naming the file and key: missing file ("no config at <path>; see docs/config-contract.md"), not UTF-8, not YAML, missing key, unknown key, bad value
  - [x] Success: modules import; pyright strict clean

- [x] **4.2 Config contract doc and example**
  - [x] Write `docs/config-contract.md` (with YAML frontmatter per `file-naming-conventions.md`): each key, its type and meaning, and one complete example whose `authorize_items` are the five defaults named in the design's D5 (including the item keyed `merge_to_main`), all `denied_by_default: true`
  - [x] Success: the example block is valid YAML; the doc names every D5 key
  - Note: the example's model aliases are the obvious placeholders replace-with-answer-alias and replace-with-check-alias.

- [x] **4.3 Config tests**
  - [x] `tests/config/test_user_config.py`: the example from `docs/config-contract.md` loads (extract it from the doc, do not copy it); parametrized, removing each one key in turn raises `ConfigError` naming that key; unknown key, bad value, duplicate item `key`, missing file, non-UTF-8 and non-YAML each raise `ConfigError` naming the file; two problems in one file are both listed
  - [x] Success: tests pass

**Commit**: `feat: add user config loading and contract doc`

## 5. Project lookup (Context Forge)

- [x] **5.1 Implement `upstream/context_forge/project_of.py` (D6)**
  - [x] Frozen `CFProject` (`id`, `name`, `project_path` from `projectPath`; other fields ignored) and `CFProjectNotFound` (CF's message)
  - [x] `project_of(*, directory=None, reference=None, run)` runs `cf get --json` with `cwd=directory` or with `-p <reference>`, via the injected `CfRun`; a `PROJECT_NOT_FOUND` document on either stream gives `CFProjectNotFound`; any other failure or unparseable output gives `CfCallFailed` quoting the output head
  - [x] Module imports nothing from `answering` or the new packages
  - [x] Success: pyright strict clean
  - Note: project_of returns CfCallFailed (not raises), per D6's signature; exactly one of directory/reference is required (ValueError otherwise); CF_GET_TIMEOUT_SECONDS = 30.0 is defined in project_of.py. A bad `-p` reference also yields a PROJECT_NOT_FOUND document (checked live).

- [x] **5.2 `project_of` tests**
  - [x] `tests/upstream/context_forge/test_project_of.py`: parse each task 1.2 fixture; default and non-default worktree fixtures give the same `id`; the subdirectory fixture gives the root's `id`; the not-found fixture gives `CFProjectNotFound` with the message; garbage output and a nonzero exit with no document give `CfCallFailed`; with `reference` the argument list contains `-p` and the reference
  - [x] Success: tests pass

**Commit**: `feat: add Context Forge project lookup`

## 6. Program reads and upserts

- [x] **6.1 Reads in `store/programs.py`**
  - [x] `get_program`, `get_member`, `members_of`, `pairs_of`, `member_settings`, each taking an open transaction and returning the task 3.1 models (JSON columns decoded into tuples)
  - [x] `store/` imports nothing from `config` or `operations`
  - [x] Success: pyright strict clean

- [x] **6.2 Upserts in `store/programs.py`**
  - [x] Upserts for program (with concept pair), member (rules paths, authorize lists), and dependency pair (`consumed`)
  - [x] Each upsert writes and moves `updated_at` only when a stored value changes, and returns whether it changed; `registered_at` and `updated_at` are UTC ISO-8601 text, with the clock passed in so tests control it
  - [x] Success: a second identical upsert returns "unchanged" and leaves `updated_at` as it was
  - Note: upserts return a bool; the operation (8.x) learns created-vs-changed by reading state before the write. upsert_member raises StoreIntegrityError if the member exists in another program. Added get_pair and SELECT_PAIR (not in the task text) for the pair upsert.

- [x] **6.3 Programs tests**
  - [x] `tests/store/test_programs.py`: create then read back each of program, member, pair; an unchanged upsert keeps `updated_at`; a changed value moves it; a list field replaces whole; `concept_member` and `concept_path` both null or both set; a member in a second program is refused by the unique key
  - [x] Success: tests pass
  - Note: also covers the programs.py read-back deferred from 3.7.

**Commit**: `feat: add program, member and pair store access`

## 7. Member resolution

- [x] **7.1 Implement `operations/members.py` (D6)**
  - [x] `ContextForgeError`; `NotInProgram` (CF id) and `NotAProject` (CF message); `resolve_member(store, directory, run) -> Member | NotInProgram | NotAProject`
  - [x] `CfCallFailed` from `project_of` is raised as `ContextForgeError`; no worktree logic of Amoeba's own
  - [x] Success: pyright strict clean

- [x] **7.2 Resolution tests**
  - [x] `tests/operations/test_members.py`: a registered member's default worktree and non-default worktree fixtures both give the same `Member`; the subdirectory fixture gives it too; a CF project outside the program gives `NotInProgram` with its id; the not-found fixture gives `NotAProject`; a failing `cf` raises `ContextForgeError`
  - [x] Success: tests pass

**Commit**: `feat: add member resolution`

## 8. `set_up`

- [x] **8.1 Request and result models (D7)**
  - [x] `operations/set_up.py`: frozen, `extra="forbid"` pydantic `SetUpRequest` (program, optional concept where omitted differs from null, optional members with `project`, `rules_paths`, `authorize_allow`, `authorize_deny`, `depends_on` entries of `provider` and `consumed`), `SetUpProblemCode` enum with the nine codes of D7, `SetUpProblem(code, detail)`, and `SetUpResult` (`outcome`, `changes`, `problems`, `program`, `working_directory`)
  - [x] `rules_paths` entries use the repo-relative path validation type from slice 221; `concept.path` uses `validate_repo_relative_path`
  - [x] Success: pyright strict clean
  - Note: to keep files near 300 lines the request/result models are in operations/set_up_models.py, resolution in set_up_resolve.py, checks in set_up_checks.py; set_up.py re-exports SetUpRequest, SetUpResult, SetUpProblemCode and ContextForgeError. SetUpResult.working_directory is null for a malformed request (nothing was looked up) and program is null when the program does not exist.

- [x] **8.2 Validation and resolution phase (D7, Data Flow steps 2 and 3)**
  - [x] `set_up(store, config, document: object, *, directory, run)` validates `document` itself; each pydantic error becomes a `malformed` problem, plus `malformed` for a member listed twice after resolution and for a key in both authorize lists
  - [x] Resolve the working directory and every member reference (and `concept.member`, providers) to CF ids through `project_of` before the first `Store.write()` (the `Store` is passed in already open; no subprocess runs under the write lock); an omitted `project` uses the working directory; a missing project gives `not_a_project`; `ContextForgeError` propagates before anything is written
  - [x] Success: a `cf` failure with a fake `CfRun` raises `ContextForgeError` and the store has no rows
  - Note: resolution problems (not_a_project, duplicate member) are returned without running the 8.4 checks, so problems of the two phases are not merged in one result; each phase lists all of its own.

- [x] **8.3 Validation tests**
  - [x] `tests/operations/test_set_up_validation.py`: a non-mapping document, a missing `program`, an unknown field, a non-repo-relative `rules_paths` and `concept.path`, a member listed twice via name and id, and a key in both authorize lists each give `malformed` with a detail naming the field; a bad reference and a bad working directory with omitted `project` give `not_a_project`
  - [x] Success: tests pass; each rejection leaves the store empty

- [x] **8.4 Checks (D7)**
  - [x] Inside one `Store.write()` read current state, compute the state the request would produce, run the remaining checks (`empty_program`, `member_of_other_program`, `rules_paths_required`, `unknown_provider`, `self_dependency`, `unknown_authorize_item`, `concept_member_not_member`), and collect all problems
  - [x] Any problem: roll back and return `rejected` with the unchanged state (null `program` if it does not exist). With no problems, this task stops after the checks; 8.6 adds the writes
  - [x] Success: pyright strict clean
  - Note: no writes happen before the checks pass, so on a problem the transaction simply commits empty; nothing to roll back.

- [x] **8.5 Check tests**
  - [x] `tests/operations/test_set_up_checks.py`: one test per remaining D7 code, each asserting the code, a detail naming the field or member, and an unchanged store; two problems in one request are both returned
  - [x] Success: tests pass

- [x] **8.6 Writes and result (D7)**
  - [x] No problems: upsert (never remove; a given list replaces the stored value) and return `applied` with one `changes` line per created or changed row, or `unchanged` with nothing written
  - [x] `program` is read in the same transaction; `working_directory` is built from the working-directory lookup already made in 8.2 (no new `cf` call): not found gives `{not_a_project: <CF message>}`; otherwise `get_member` on the CF id in the same transaction, after any writes, gives `{member, program}` when found and `{not_in_program: <CF id>}` when not. A request naming only `program` is the read-back
  - [x] Success: pyright strict clean

- [x] **8.7 Outcome tests**
  - [x] `tests/operations/test_set_up_outcomes.py`: a valid request creates program, members, settings and pairs and returns `applied` with one change line per row; the same request returns `unchanged` and every `updated_at` stays; changing one value changes only that row; a program-only request reads back; `concept: null` clears the concept and an omitted `concept` leaves it; `not_in_program` and `not_a_project` appear in `working_directory`
  - [x] Omitted `project` from two worktrees: with a member registered through the default-worktree fixture, a request with an omitted `project` run with the non-default-worktree fixture (and again with the subdirectory fixture) resolves to the same member and returns `unchanged`
  - [x] Success: tests pass
  - Note: tests/operations/set_up_support.py provides FakeCf (routes cf get by directory or -p reference, reusing the recorded default-worktree document with another id/name for extra projects) and set_up_worker.py is the per-process worker for 8.8.

- [x] **8.8 Concurrent `set_up` test**
  - [x] `tests/operations/test_set_up_concurrent.py`: 8 processes against one new store each call `set_up` for the same program with a different member (fake `CfRun` in each); each returns `applied` or raises `StoreBusyError`, and the store ends with every member that reported `applied`
  - [x] Success: test passes on five consecutive runs

**Commit**: `feat: add set_up operation`

## 9. Member answering settings

- [x] **9.1 Implement `operations/member_answering.py` (D8)**
  - [x] `MemberAnswering` (`settings: AnswererSettings`, `not_authorized`: tuple of items with descriptions) and `answering_for(member_settings, config)`
  - [x] Not-authorized items: config items with `denied_by_default: true` not in `authorize_allow`, plus items in `authorize_deny`, in config order; `reserved_terms` are those items' screen phrases; `rules_paths` the member's; the remaining fields from the config
  - [x] An authorize key the config lacks raises `ConfigError` naming the member and key
  - [x] Success: pyright strict clean
  - Note: an item both allowed and denied on one member stays not-authorized (deny wins); tests/user_configs.py is the shared UserConfig builder.

- [x] **9.2 `answering_for` tests**
  - [x] `tests/operations/test_member_answering.py`: a member allowing `merge_to_main` lacks that item's phrases and description while another member keeps them; a member denying a `denied_by_default: false` item gets it and others don't; items keep config order; config-sourced fields reach the settings; an unknown authorize key raises `ConfigError` naming member and key
  - [x] Success: tests pass

**Commit**: `feat: add per-member answering settings`

## 10. CLI, packaging and boundaries

- [x] **10.1 Implement the CLI (D9)**
  - [x] `cli/main.py`: `argparse`, subcommand `set_up` with `--file <path|->`, no per-field flags; exit codes as named constants (0 applied or unchanged, 1 rejected, 2 usage or unreadable/non-UTF-8/non-YAML request, 3 `ConfigError`, `AmoebaHomeError`, `ContextForgeError`, any `StoreError`)
  - [x] Order: read text and `yaml.safe_load` (exit 2 on failure, before config or store), then `load_user_config(config_path())`, open the store at `store_path()`, call `set_up` with the current directory and `run_cf`, print `SetUpResult` JSON to stdout
  - [x] Errors print `error: <ExceptionName>: <message>` to stderr; this is the one top-level handler; `RequestDocumentError` is defined here and names the source
  - [x] Only `cli` calls `amoeba_home()`, `store_path()` and `config_path()`
  - [x] Success: pyright strict clean

- [x] **10.2 Packaging**
  - [x] `pyproject.toml`: add `[project.scripts] amoeba = "amoeba.cli.main:main"` and include `src/amoeba/store/schema/*.sql` in the wheel
  - [x] `tests/test_wheel_contents.py`: build the wheel into a temporary directory with `uv build --wheel --out-dir` and assert its file list contains `amoeba/store/schema/001_baseline.sql`
  - [x] Success: `uv run amoeba --help` lists `set_up`; the wheel test passes
  - Note: tests/answering/test_wheel_contents.py no longer asserts there is no entry_points.txt (the wheel now has the amoeba entry point).

- [x] **10.3 CLI tests**
  - [x] `tests/cli/test_set_up_cli.py`, run as subprocesses with the task 1.3 fake `cf` first on `PATH` and the fixture `AMOEBA_HOME`: valid request from a file and from stdin exits 0 with result JSON; rerun exits 0 `unchanged`; a rejected request exits 1 with JSON; a missing file, non-UTF-8 and non-YAML request exit 2 and no store file is created; a missing config file and a config missing one key exit 3 naming the file or key; a failing `cf` exits 3 with the store unchanged; a store stamped higher exits 3
  - [x] Success: tests pass
  - Note: the CLI tests run the installed `amoeba` script (next to sys.executable) through process_containment.contained_popen, as the repo's containment guard requires; additionally cover a relative AMOEBA_HOME (exit 3, AmoebaHomeError), bad arguments (exit 2) and a non-mapping document (exit 1, malformed).

- [x] **10.4 Import boundary test**
  - [x] `tests/test_import_boundaries.py`: parse imports under `src/amoeba` and assert the design's direction: `store` imports nothing from `config`, `operations` or `cli`; `upstream` imports nothing from `answering`, `config`, `store`, `operations` or `cli`; `config` imports only `answering.settings` (and its type modules); `operations` does not import `cli`
  - [x] Success: test passes; adding a forbidden import makes it fail (verify once, then revert)
  - Note: tests/test_import_boundaries.py was rewritten as a table of rules (store, upstream, operations forbidden lists; config allow-list of answering.settings and answering.values); it replaces the earlier upstream-only test.

**Commit**: `feat: add amoeba set_up command and packaging`

## 11. Contract docs and final validation

- [x] **11.1 Store contract doc**
  - [x] Replace the content of `docs/store-contract.md` (the old per-project store contract is obsolete after slice 221; if 221 already removed it, create it) with the D3 description: each table and column, its vocabulary, and which slice writes it; the migration rule (no edits to `001`, later migrations `ALTER TABLE … ADD COLUMN` only); the home and `AMOEBA_HOME` rule; frontmatter per `file-naming-conventions.md`
  - [x] State two derivations the schema deliberately has no column for (design, Audit items): an answering run's scratch directory is `answering_dir() / <answering_run_id>` (223 D6, D12), so `questions.answering_run_id` is its only record; and answering has no per-member switch, since program membership is the opt-in (no `answering_enabled` column, no `answerer:` section equivalent)
  - [x] Success: every table and column in `001_baseline.sql` appears in the doc, and the doc states both derivations
  - Note: docs/store-contract.md created (docs/ did not exist; 221 had already removed the old contract). It states both derivations (scratch dir from answering_run_id; no per-member answering switch), the migration rule, and the home rule.

- [x] **11.2 Contract match test**
  - [x] `tests/test_contract_docs.py`: assert every table and column name in `001_baseline.sql` (read from `PRAGMA table_info` on a fresh store) appears in `docs/store-contract.md`, and every `UserConfig` field name appears in `docs/config-contract.md`
  - [x] Success: test passes

- [x] **11.3 Full validation and walkthrough**
  - [x] Checks pass
  - [x] Run the design's Walkthrough steps 1 to 3 with `AMOEBA_HOME="$(mktemp -d)"`; note each result under this task (step 3's two worktrees: use `git worktree add` on a registered throwaway checkout)
  - [x] Walk the design's Success Criteria list and note any criterion not covered by a test
  - [x] Success: all four checks pass; steps 1 to 3 give the documented results (exit 3 `ConfigError: no config at ...`, then `applied` and `unchanged`, then the same member from both worktrees and `not_a_project` from `/tmp`)
  - Note: four checks pass (ruff format --check, ruff check, pyright strict, pytest 756 passed). Walkthrough run with AMOEBA_HOME=$(mktemp -d) and the real cf 0.19.26: step 1 exit 3 `error: ConfigError: no config at <home>/config.yaml; see docs/config-contract.md`; after copying the doc example into config.yaml, step 2 `applied` (changes: `added program demo`, `added member project_1781844717321_1gukaohbc`; the member is amoeba's CF id) and the rerun `unchanged`; step 3 with a throwaway `git worktree add` checkout registered via `cf worktree init --name walkthrough-wt --range 800-899 -o` (removed afterwards) printed `unchanged demo project_1781844717321_1gukaohbc` (the same member as the default worktree), and from /tmp `working_directory` was `{not_a_project: 'No project specified and no registered project found at current path.'}`. Success Criteria walked: every criterion is covered by a test (set_up outcomes/validation/checks/concurrent, CLI, answering_for, store, vocabulary pinning, D10 home tests, D11 recordings, import boundaries, wheel, contract docs); none uncovered.

**Commit**: `docs: add store and config contracts`
