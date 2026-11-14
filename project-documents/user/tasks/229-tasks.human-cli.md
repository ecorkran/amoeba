---
docType: tasks
slice: human-cli
project: amoeba
lld: user/slices/229-slice.human-cli.md
dependencies:
- 226-slice.mcp-server
- 228-slice.state-home-and-question-lifecycle
projectState: Slices 222 to 226 and 228 are merged on main (schema version 4, eight
  operations on the CLI and the MCP server, state in ~/.local/state/amoeba). The CLI
  prints JSON only, uses underscore names, and registers through `set_up --file`.
  Three members of program `trading` are registered with named rules ["CLAUDE.md"].
  The 220 architecture, the 227 design and the 220 slice plan already use the 229
  names (commits 5e03f6f, 5df183c, df34ea5).
dateCreated: 20261113
dateUpdated: 20261114
status: in_progress
turns: 105
promptTokens: 9193319
cachedTokens: 8978808
cacheWriteTokens: 214389
completionTokens: 65162
durationSeconds: 486.0
costUsd: 2.407596
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-sonnet-5-5:
    rounds: 3
    costUsd: 2.4075961999999995
    completionTokens: 65162
revision_number: 2
---

# Tasks: Human CLI

## Context Summary

- Working on slice 229 (design: `user/slices/229-slice.human-cli.md`; decisions D1 to D14 are cited by number). Effort 4/5.
- Delivers: text output by default and `-j` on every command (D2); kebab-case CLI names derived from `names.py` (D1); `add`, `rm`, `list` replacing `set_up` on both doors (D3 to D6); config-default rules with optional entries, duplicate dropping and `@path` imports (D7 to D10); migration 005 (D11); docs and the cutover (D12, D13).
- The `set_up` engine keeps its module names and every guard. `add` and `rm` build a `SetUpRequest` for it. No operation's decision logic changes.
- Where the design's architecture names a module that does not exist yet (`cli/parser.py`, `cli/commands.py`, `cli/render/`, `operations/add.py`, `rm.py`, `list_view.py`, `list_registry.py`, `store/settled.py`, `answering/rule_imports.py`), create it. `cli/main.py` today holds `build_parser()` and the runners; 9.1 splits it. `store/sql.py` (406 lines), `passages.py` (402), `set_up.py` (305), `wiring.py` (303) and `source_reads.py` (281) are already at or past the 300-line guide: new logic goes in the new modules named in 3.1, 3.3, 3.7 and 9.2, and these files gain only call sites and constants.
- Decisions made by these tasks where the design is silent: a `config_default` member stores `rules_paths = ()` (the stored list is unused for it); `--no-rules` stores an empty named list (`rules_paths: []`, D7), so only giving none of the three rules flags yields the default for a new member; `set_up`'s change lines keep naming Context Forge ids, and the CLI runner maps ids to names for the renderers; the verbs and subjects of those lines are defined once and used by both `set_up` and the `add` renderer (no parsing of free text).
- Closed vocabularies (`RulesFrom`, new problem codes, `OperationName`, list subjects) are each a `StrEnum` defined once. No silent fallbacks. A swallowed exception needs a comment saying why. Every Context Forge or `git` failure is reported, never read as "absent" (D8).
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. "Checks pass" means all four. The live tier is `uv run pytest tests/live/<dir>` (never part of a bare run; LLM spend is pre-authorized).
- Tests use the autouse `AMOEBA_HOME` fixture, the stub `sq` and `cf`, `tests/git_repo.py`, `tests/user_configs.py`. Destructive SQL only against throwaway stores. No sample id, hash or timestamp sits near a value an agent must fetch (hallucination-trap rule), including docs that tests check.
- Production state: tests touch throwaway stores only. Task 11 alone changes the live store (migration 005 runs on it) and the live config. `sql.md` ("Production Database Protection") requires a Project Manager designation, and the Project Manager gave it on 2026-11-14 as a standing rule: the "Amoeba Design Rules" block of `CLAUDE.md` designates the live store and config for migrations and their config edits, with a backup first. No task waits for a further designation. Task 11 can still stop on its own checks (backup fails, store version is wrong); then 12.2 words the cutover only when 11 completed, and if 11 did not complete the hook and store-version-5 success criteria stay unmet: the slice is not complete, and the final reply says so.
- Work on branch `229-slice.human-cli`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.

## 0. Setup

- [x] **0.1 Branch, inputs and baseline**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty. With a clean tree on the target: `git checkout -b 229-slice.human-cli {target}`
  - [x] Confirm 226 and 228 are merged: `src/amoeba/mcp/tools.py`, `config/home.py` with `state_layout`, `store/schema/004_answer_via.sql` and `operations/dismiss.py` exist; `store/schema/` holds `001` to `004` only. If not, write `BLOCKED: slices 226 and 228 not merged` under this task and stop
  - [x] Confirm the planning edits are on the target: `grep -n "kebab" project-documents/user/architecture/220-arch.program-tool.md` finds the names line, and `grep -n "add --depends-on" project-documents/user/slices/227-slice.program-dependencies.md` finds the new command names. If either is missing, write `BLOCKED: 220 or 227 not updated` and stop
  - [x] Run `cf list projects --json` and confirm entries have `id` and `name` and most have `projectPath`; run `sq config set --help` and confirm it exists. If either differs from D3 and D13, write `BLOCKED:` with what differs and stop
  - [x] Find the test helpers to reuse: `tests/user_configs.py`, `tests/operations/{set_up_support,status_support,program_rig}.py`, `tests/store/seed.py`, `tests/cf_fixtures.py` (incl. `LIST_PROJECTS`), `tests/answering/sources_repo.py`, `tests/git_repo.py`, `tests/live/pause/harness.py`, and the existing CLI tests in `tests/cli/`
  - [x] Run the checks once and note the baseline. Failures present before this slice are written down, not fixed
  - [x] Success: `git branch --show-current` prints `229-slice.human-cli`; a note under this task gives the target's name, the baseline result, and the located helper paths
  - Note: target is `main`; branch `229-slice.human-cli` (== main at start); baseline: ruff format/check, pyright, pytest (1985 passed) all clean; helpers located: tests/user_configs.py, tests/operations/{set_up_support,status_support,program_rig}.py, tests/store/seed.py, tests/cf_fixtures.py, tests/answering/sources_repo.py, tests/git_repo.py, tests/live/pause/harness.py, tests/cli/*. cf list projects --json has id/name/projectPath (some missing); sq config set exists.

## 1. Store: migration 005 (D11)

- [x] **1.1 `members.rules_from`**
  - [x] Add `store/schema/005_member_rules_from.sql`: `ALTER TABLE members ADD COLUMN rules_from TEXT NOT NULL DEFAULT 'named' CHECK (rules_from IN ('named','config_default'))`. `EXPECTED_SCHEMA_VERSION` becomes 5
  - [x] Define `RulesFrom` (`NAMED`, `CONFIG_DEFAULT`) once in `store/vocabulary.py`. `MemberSettings` (`store/models.py`) gains `rules_from: RulesFrom`; thread it through `store/sql.py` (the member insert and both updates) and `store/programs.py` (`_member`, `upsert_member`). Update every caller pyright reports, passing `RulesFrom.NAMED` where behavior must not change yet
  - [x] Success: pyright strict clean; existing tests pass
- [x] **1.2 Migration and store tests**
  - [x] `tests/store/test_migration_005.py` (model on `test_migration_004.py`): a version-4 database holding a member migrates to 5, the member keeps its `rules_paths` and reads `named`; a bad `rules_from` value is refused by the CHECK
  - [x] Add `RulesFrom` to `tests/store/test_vocabulary_pinning.py`; update the schema pin (`test_schema_holds_no_mirrored_state.py`) and the stale-version assertions in `test_migrations.py`
  - [x] Update `docs/store-contract.md` (the column, the vocabulary, version 5) so `tests/test_contract_docs.py` passes
  - [x] Success: checks pass

**Commit**: `feat: add members.rules_from in migration 005`

## 2. Config keys (D7)

- [x] **2.1 `default_rules_paths` and `default_consumed`**
  - [x] In `config/user_config.py` add both to `UserConfig`, required, no default in code: `default_rules_paths` is a non-empty tuple of `RulesPath` (reuse the type from `answering/settings.py`; an empty list is a validation error), `default_consumed` is `ConsumedMode`. Keep the module's one-pass error report naming the key
  - [x] Update `tests/user_configs.py` (`example_config_text` and the builders) to carry both keys: `[CLAUDE.md, AGENTS.md]` and `from_source`. Every test config and the live harness read it
  - [x] Success: pyright clean; existing tests pass
  - Note: `tests/test_import_boundaries.py` now allows `config` to import `amoeba.store.vocabulary` (a leaf enum module) because `default_consumed` is a `ConsumedMode`.
- [x] **2.2 Config tests and doc**
  - [x] In `tests/config/test_user_config.py`: a config missing each new key fails naming that key; an empty `default_rules_paths`, a non-list and a bad `default_consumed` each fail naming the key
  - [x] Update `docs/config-contract.md` for the two keys and `passages_max_chars` (example 250000, and the sum it must cover: the rules, the slice's plan files, the program concept, room for precedent); `tests/test_contract_docs.py` passes
  - [x] Success: checks pass

**Commit**: `feat: require default_rules_paths and default_consumed in the config`

## 3. Rules selection (D7 to D10)

- [x] **3.1 Member rules choice (D7)**
  - [x] Add one frozen value `RulesChoice` (entries, `optional: bool`) in `answering/settings.py`. `answering_for` (`operations/member_answering.py`) builds it: a `CONFIG_DEFAULT` member gets the config's `default_rules_paths` with `optional=True`, read at answering time so a config edit changes every default member; a `NAMED` member gets its stored entries with `optional=False`. `AnswererSettings` carries the choice in place of `rules_paths`; update `pause_context.py` and every other reader. `source_reads` still reads the entries as before (a named member behaves exactly as today)
  - [x] Add cases to `tests/operations/test_member_answering.py`: `answering_for` gives a `named` member its stored entries with `optional=False` and a `config_default` member the config's current entries with `optional=True`
  - [x] Success: the new cases and the existing tests pass; pyright clean
- [x] **3.1b Optional entries (D8)**
  - [x] `answering/source_reads.py`: `locate_sources` and `read_committed_sources` take the choice; `source_reads` keeps no list of its own. Move `_select_rules` into a new `answering/rule_entries.py` that holds the optional-entry handling below, so `source_reads.py` only calls it. An optional entry matching no file is skipped and its `SelectedFile` is marked optional (3.7 needs this). If every entry of an optional choice is skipped, return `sources_missing` with detail `no rules file found; tried: <entries joined by ", ">`. A named entry that matches nothing still fails the whole selection as today
  - [x] For an optional entry in a subdirectory, read the directory with `git ls-tree`: exit 0 with empty output means absent; any non-zero exit stays `sources_unreadable`. Absence is never concluded from an error
  - [x] Success: pyright clean; existing tests pass (the new behavior is tested in 3.2)
- [x] **3.2 Selection tests**
  - [x] In `tests/answering/test_source_reads.py` with git-fixture repos (`sources_repo.py`): both default entries present; only one present; none present (`sources_missing`, detail names both); a named entry missing (fails as before); an optional entry in a missing subdirectory (skipped); a failing `git ls-tree` (`sources_unreadable`, not skipped)
  - [x] A `config_default` member reads the config's entries as they are at the time (edit the config between two calls); a `named` member with `[]` reads no rules and is not declined for it
  - [x] Success: checks pass

  Note: the 3.2 and later source-read tests live in `tests/answering/test_default_rules_reads.py` (helpers in `tests/answering/rules_reads_support.py`) because `test_source_reads.py` is past 300 lines; `git ls-tree` was added to the `git_read` allowlist for the optional-directory check.

**Commit**: `feat: read config-default rules files, each skipped when absent`

- [x] **3.3 Duplicate rule sections dropped (D9)**
  - [x] In a new `answering/rule_dedup.py` add one helper that, given the rule passages read so far and a new file's passages, returns which are new. A rule passage whose text equals an earlier rule passage (after `cut_passages`, compared exactly) is dropped; the first file keeps it. Plan and program passages are never dropped
  - [x] Both `read_committed_sources` (its running size, so duplicates do not trip `sources_too_large` early) and `_committed_passages` (numbering, in `passages.py`) call the helper, adding no more than the call. A citation names the file that kept the passage
  - [x] Success: pyright clean; existing tests pass
  - Note: helper is `RuleDeduper` in `answering/rule_dedup.py`; `read_committed_sources` now returns `CommittedSources.chars` (deduplicated passage text) and `pause_context` uses it in place of the raw-text sum. Duplicate tests are in `tests/answering/test_rule_dedup.py` (test_passages.py is past 300 lines).
- [x] **3.4 Duplicate tests**
  - [x] Copy this repo's real `CLAUDE.md` and `AGENTS.md` into a new `tests/answering/fixtures/rules_repo/` (beside, not inside, the existing `sources/` tree and `expected_passages.md`). In `tests/answering/test_passages.py`: the shared sections appear once and under `CLAUDE.md`; every `AGENTS.md`-only section stays; passage numbers are contiguous; a section edited in one file stays in both; plan passages equal to a rule passage are kept
  - [x] In `test_source_reads.py`: a selection whose raw text exceeds `passages_max_chars` but whose deduplicated text fits is not `sources_too_large`
  - [x] Success: checks pass

**Commit**: `feat: drop duplicate rule sections before numbering and counting`

- [x] **3.5 `@path` import parser (D10)**
  - [x] `answering/rule_imports.py`: one pure function returning the import paths in a rules file's text, per D10 (a token starting with `@` at line start or after whitespace, outside fenced blocks and inline code, no whitespace in the path, ends in `.md` after trailing `.,;:)` is removed, not starting with `/` or `~`). Reuse the fence logic in `passages.py` rather than a second copy
  - [x] Success: pyright clean
  - Note: `fence_after` in `passages.py` is now public (renamed from `_fence_after`) and `answering/rule_imports.py` (`rule_imports`) reuses it.
- [x] **3.6 Parser tests**
  - [x] `tests/answering/test_rule_imports.py`: a plain import, one after whitespace, a fenced `@x.md`, inline code, `@types/node`, `@modelcontextprotocol/server`, trailing punctuation, an absolute and a `~` path, `..` segments; the copied real `CLAUDE.md` (`tests/answering/fixtures/rules_repo/`) yields no import
  - [x] Success: checks pass

**Commit**: `feat: parse @path imports in rules files`

- [x] **3.7 Following imports (D10)**
  - [x] In a new `answering/import_follow.py`, called from `read_committed_sources` after it reads a rule file ending `.md`, follow its imports: resolve against the importing file's directory; a path that resolves outside the repository declines `sources_unreadable`, the detail naming the import and the file (D10), under a default or a named entry; read the target at the pinned commit as a rule file placed directly after its importer, recurse. Limits: `IMPORT_DEPTH = 3` (deeper is `sources_unreadable`, detail gives the chain); a file already selected is not read twice, no error; a missing target is skipped when the chain began at an optional entry, else `sources_missing` with detail `import @x in F matches no file`; imported text counts against `passages_max_chars` and goes through the 3.3 helper
  - [x] Success: pyright clean; existing tests pass
  - Note: `follow_imports` in `answering/import_follow.py` is driven by `_Reading` in `source_reads.py` (which now owns the running size, dedup and the files read); tests are in `tests/answering/test_rule_import_reads.py`.
- [x] **3.8 Following tests**
  - [x] In `test_source_reads.py` with git fixtures: a chain of depth 3 reads, depth 4 declines naming the chain; a cycle reads each file once; a missing import under a default entry is skipped and under a named entry is `sources_missing`; an import that resolves outside the repository declines `sources_unreadable` naming the import and file, under a default and under a named entry; imported text is counted against the size cap
  - [x] Success: checks pass

**Commit**: `feat: follow @path imports in rules files`

## 4. `set_up` engine: rules choice (D4, D7)

- [x] **4.1 `rules_default` and the new-member default**
  - [x] `MemberRequest` (`operations/set_up_models.py`) gains `rules_default: bool = False`; a validator rejects `rules_default` true with `rules_paths` given (`malformed`). `rules_paths` keeps its meaning: omitted leaves the member's rules, given (including `[]`) replaces them and sets `NAMED`
  - [x] `_merged_settings` in `set_up.py` (and `ResolvedMember` in `set_up_resolve.py`): `rules_default` true, or a new member with neither field, sets `CONFIG_DEFAULT` and stores `rules_paths = ()`; an existing member with neither field keeps both stored values
  - [x] Remove `RULES_PATHS_REQUIRED` from `SetUpProblemCode` and its check in `set_up_checks.py`. `MemberState` gains `rules_from`
  - [x] Define the change-line verbs and subjects (`added|updated program|member|dependency ...`) once in `set_up_models.py` and make the writers in `set_up.py` use them, so the 8.2 renderer reads the same definitions
  - [x] Success: pyright clean
  - Note: change-line vocabulary is `ChangeVerb`, `ChangeSubject`, `change_line`, `parse_change_line` in `set_up_models.py` (also used by `set_up_remove.py`, with `removed`/`pair`); engine rules tests are in `tests/operations/test_set_up_rules.py`.
- [x] **4.2 Engine tests**
  - [x] Update `tests/operations/test_set_up_checks.py`, `test_set_up_outcomes.py`, `test_set_up_validation.py` and the vocabulary pin for the removed code: a new member with no rules field is added as `config_default`; `rules_default` returns a named member to default; `rules_paths: []` is named and empty; both fields together is `malformed`; a repeat is `unchanged`; an existing member's rules survive a request that omits both
  - [x] `tests/test_contract_docs.py` still passes (update `docs/cli-contract.md`'s problem-code list, which loses `rules_paths_required`)
  - [x] Success: checks pass

**Commit**: `feat: give a new member the config's default rules in set_up`

## 5. `add` operation (D4, D5)

- [x] **5.1 `AddRequest`**
  - [x] `operations/add.py`: pydantic `AddRequest` with `bulk: SetUpRequest | None` or the single-member fields `program`, `project`, `rules_paths`, `rules_default`, `authorize_allow`, `authorize_deny`, `depends_on`, `concept` (as `ConceptRequest`), never both (validator). Omitted vs given follows `model_fields_set`, as in `set_up_models.py`
  - [x] A pure function builds the `SetUpRequest` for the one member: `rules_paths`, `authorize_*` pass through (so `[]` is the empty list and omitted leaves it); `depends_on` entries without a mode get `config.default_consumed` (the CLI passes the mode as given, `None` when absent, so the config fills it here, once)
  - [x] The flag-to-field mapping, stated once for 9.3 and 9.5: `--rules P` (repeatable) is `rules_paths: [P...]`; `--default-rules` is `rules_default: true`; `--no-rules` is `rules_paths: []`; `--allow K` is `authorize_allow: [K...]`; `--no-allow` is `authorize_allow: []`; `--deny` and `--no-deny` likewise for `authorize_deny`. A flag not given leaves its field omitted
  - [x] Success: pyright clean
- [x] **5.2 Request tests**
  - [x] `tests/operations/test_add_request.py`: each field maps to the `SetUpRequest` field (including `rules_paths: []` and each `authorize_*: []` reaching it as the empty list, and an omitted field staying omitted); bulk and single fields together are `malformed`; a missing mode takes `default_consumed`; `bulk` passes through unchanged
  - [x] Success: tests pass
- [x] **5.3 `add` and program choice (D5)**
  - [x] `add(store, config, document, *, directory, run)` validates, resolves the member's Context Forge project (`project_of` for the working directory, the existing reference lookup for `--project`), picks the program, and calls `set_up`. Program: the request's `program`; else the member's current program from the store; else a new program whose id is the CF project name. A bulk request goes straight to `set_up`
  - [x] No project and no `project` field: return a rejected `SetUpResult` with `not_a_project` whose detail says to run `cf init` or pass `--project`; nothing is written. A reference CF cannot resolve is `not_a_project` carrying CF's message (set_up already reports it). `cf` failures raise `ContextForgeError`, exit 3
  - [x] Success: pyright clean
  - Note: `set_up.malformed_result` (was `_malformed`) is now public and `add` uses it; a removed member re-added without `program` returns to its old program (`get_member_any`); a `project` reference cf cannot resolve is rejected by `add` itself (`not_a_project`, detail `project: <cf message>`, nothing written).
- [x] **5.4 `add` tests**
  - [x] `tests/operations/test_add.py` with the stub `cf`: first run creates program named for the CF project (change lines include `added program` and `added member`); second repo with `program` joins it; a repeat is `unchanged`; the member keeps its current program when none is given; a program that already exists by that name is joined and the change lines carry no `added program`
  - [x] Each guard through the new door with its existing code: `not_a_project`, `member_of_other_program`, `unknown_provider`, `self_dependency`, `unknown_authorize_item`, `concept_member_not_member`; `cf` absent raises `ContextForgeError`; `--file`-style `bulk` equals the old `set_up` result for the same document
  - [x] Success: checks pass

**Commit**: `feat: add the add operation`

## 6. `rm` operation (D6)

- [x] **6.1 `RmRequest` and `rm`**
  - [x] `operations/rm.py`: `RmRequest` with `members` (CF names or ids), `pairs` (`PROVIDER:CONSUMER`), `concept: bool`, `program`. `rm(store, config, document, *, directory, run)`: no members, pairs or concept given means the working directory's project. Find the program from the store for each named member (an id works after the CF project is deleted); members or pairs of different programs, or not matching `program`, are `member_of_other_program`; a member in no program is `not_a_member`
  - [x] Build the `remove` section of a `SetUpRequest` (`concept: null` for `concept` true) and call `set_up`; `member_has_open_questions` and `not_a_member` stay the engine's. The refusal detail for open questions carries the question keys; the renderer adds the `answer` and `dismiss` commands (8.2)
  - [x] Success: pyright clean
  - Note: `rm` resolves each named member through `cf` (an unknown reference is read as a stored id), finds the program from the store, and does its own rejection for `not_a_member` (member in no program), `member_of_other_program` and an unknown `program` with `concept` (`malformed`); `FrozenModel` (was `_Model`) in `set_up_models.py` is the shared request base; `rejected_result` builds a pre-engine rejection.
- [x] **6.2 `rm` tests**
  - [x] `tests/operations/test_rm.py`: remove the working directory's member; remove by name and by id; two members of one program; members of two programs rejected; a pair; `concept` clears it; removing the concept's member without `concept` is refused by the engine; open questions refuse with the keys; a removed member's re-`add` revives it in its old program and, with `--program` naming another, in that one (the typo-fix path of D3: `get_member` reads active members only, so the engine does not refuse it)
  - [x] Success: checks pass

**Commit**: `feat: add the rm operation`

## 7. `list` operation (D3)

- [x] **7.1 Context Forge project details**
  - [x] `upstream/context_forge/projects.py`: add `project_details(run)` returning each project's `id`, `name` and `projectPath` or `None`, from the same single `cf list projects --json` call as `project_names`; share the parsing, no second copy. A malformed entry is a `CfCallFailed`, as today
  - [x] Test in the existing projects test: a recording with and without `projectPath` gives the path or `None`
  - [x] Success: tests pass
- [x] **7.2 Settled questions**
  - [x] `store/settled.py`: questions answered or closed at or after a given time, newest first, with program, member, key, question and how it ended; SQL parameterized, in `store/sql.py` style. Test in `tests/store/test_settled.py` with seeded rows inside and outside the window
  - [x] Success: tests pass
- [x] **7.3 Default view and `--all`**
  - [x] `operations/list_view.py`: `ListSubject` `StrEnum` (singular and plural forms map to one value), `ListRequest` (`subject`, `all`, `program`), `ListResult`. With no subject it runs the `status` operation (same code, same sweep) and returns its `StatusResult` unchanged as the result. `all` adds a `settled` field (null when `all` is not given): questions answered or closed within `config.prune_after_days`, via 7.2. The "every other run" part of D3 needs no new data: the status document already lists every run under its member, and 8.3 prints them only when `settled` is present. `--all` with `members` or `dependencies` is `rejected` (the CLI maps it to exit 2); with `programs` it is valid (7.5)
  - [x] Success: pyright clean

  Note: `ListResult` (in `list_view.py`) holds `status` (the StatusResult, unchanged) and `settled` (null without `all`); its `document()` is the status document plus a top-level `settled` only with `all`. Rejections (`all` with members/dependencies, unknown program, malformed) come back as a `ListResult` whose `status` is a rejected `StatusResult`. `SettledQuestion.ended` is a `ClosedReason` or `AnsweredBy`. Tests: `tests/operations/test_list_view.py`, `test_list_registry.py`, `list_support.py`.
- [x] **7.4 Default view tests**
  - [x] `tests/operations/test_list_view.py`: no subject equals `status`'s result for the same fixture; `all` adds `settled` and nothing else (the runs 8.3 prints are already in the status document); a settled item older than the window is absent; `all` with `members` or `dependencies` is rejected
  - [x] Success: tests pass
- [x] **7.5 Registered views**
  - [x] `operations/list_registry.py`: `programs` (each program: members, concept; programs with no active members and no concept hidden unless `all`), `members` (each active member: CF name, id, repo path or `None`, program, rules as the stored `named` entries, or for `config_default` the config's current `default_rules_paths` as written, with no git call per member; allow/deny, dependencies), `dependencies` (provider to consumer, consumed mode, names). One `project_details` call per view. A member id missing from CF is marked not in Context Forge; a removed member is not listed; `program` filters
  - [x] The JSON documents are these pydantic models, defined here and used by 8.4 and 9.5 (`-j` prints `model_dump(mode="json")`): `programs` is `{programs: [{program, concept: {member, path} | null, members: [project_id]}]}`; `members` is `{members: [{project_id, name | null, path | null, in_context_forge: bool, program, rules_from, rules_paths, authorize_allow, authorize_deny, depends_on: [{provider, consumed}]}]}` (`rules_paths` is the stored entries for `named`, the config's for `config_default`); `dependencies` is `{dependencies: [{provider_id, provider_name | null, consumer_id, consumer_name | null, consumed}]}`
  - [x] `cf` failure raises `ContextForgeError` (exit 3, no partial view)
  - [x] Success: pyright clean
- [x] **7.6 Registered view tests**
  - [x] `tests/operations/test_list_registry.py` with the stub `cf`: a path-less project, a gone project, a removed member, a program with no members (hidden, then shown with `all`, and refilled by `add`), a `config_default` member shows the config entries, `cf` failing raises; each view's model validates its documented shape
  - [x] Success: checks pass

**Commit**: `feat: add the list operation and its registered views`

## 8. Text renderers (D2)

- [x] **8.1 Rendering helpers**
  - [x] `cli/render/text.py`: `cut(text, columns=100)` ends a cut line with `…` and keeps a single line; a `command_line(text)` helper puts a command or path on its own indented line, never cut. The 100 is a named constant. Pure functions, no I/O
  - [x] Tests (`tests/cli/render/`): a 300-character question is cut to 100 columns; a command longer than 100 is whole; newlines collapse
  - [x] Success: tests pass
- [x] **8.2 `add` and `rm`**
  - [x] `cli/render/registration.py`: one renderer for both. First line `added`, `unchanged` or `rejected: <code>: <detail>`; then one line per change using the 4.1 definitions and CF names (the runner passes an id-to-name map; an id with no name prints as the id): `created program X`, `added member Y`, `added member Y to existing program X`, `changed ...`; the member's rules read `default (CLAUDE.md, AGENTS.md)` or the named entries. A `not_a_project` rejection prints the `cf init` / `--project` fix. A `member_has_open_questions` refusal prints the keys and the `amoeba answer` and `amoeba dismiss` commands that clear them
  - [x] Tests with exact expected text for each shape in D4 to D6 and the operator walkthrough
  - [x] Success: tests pass
  - Note: a refusal's open-question keys are written by `format_question_keys` and read back by `parse_question_keys` (both in `set_up_models.py`, tested together) so the renderer prints the `answer` and `dismiss` commands; commands come from `cli/render/commands.py` (built on `OperationName.cli_name`, which was added early). `render_registration` takes the id-to-name map and the config's default rules. Under 8.3 the renderer also prints a `Closed by this check` section for the status document's `closed_now`, after the four sections.
- [x] **8.3 `list` default view (also `status`)**
  - [x] `cli/render/waiting.py`: sections in this order, each omitted when empty: **Waiting on you** (member, run, how long, reason, question cut to one line, the `amoeba answer` command and the `amoeba dismiss` command: fixing a rules file or the cap helps the next question; this one is cleared by an answer or a dismiss, or closes when its run moves on), **Paused, not handled** (runs whose `pause` is `unhandled`, `claim_stale` or `answered_unresumed`, each with `amoeba handle-pause RUN_ID`, run in the run's checkout (`RunEntry.next.directory`; the three are `HANDLED_BY_HANDLE_PAUSE` in `status_runs.py`), and, for `unhandled` and `claim_stale`, the newest calls-log line, `RunEntry.last_call`), **Unplaced runs** (each with its reason and one line on how it clears: `lookup_failed`, run `amoeba list` again once `cf` answers; `no_directory` and `directory_missing`, Amoeba holds no record of the run and it leaves the list when Squadron no longer lists it as paused; no command is offered because `handle-pause` needs the run's own checkout), **Problems** (`sweep_problem`, `file_problems`, `problems`); `Nothing needs you.` when nothing waits. With `settled`: every other run under its member, then **Settled**. `status`'s text uses this same renderer
  - [x] Tests with exact text from `StatusResult` fixtures: each section alone, all together, nothing waiting, with and without `settled`
  - [x] Success: tests pass
- [x] **8.4 Registered views**
  - [x] `cli/render/registry.py`: programs, members (`(no path in Context Forge)`, `(not in Context Forge)`, rules as default or named), dependencies; no table wider than 100 columns
  - [x] Tests with exact text for each view and each marker
  - [x] Success: tests pass
- [x] **8.5 The other commands**
  - [x] Renderers for `answer`, `decisions`, `mark-read`, `dismiss`, `retract` (first line says what happened, rejected ones `rejected: <code>: <detail>`, prose cut, commands whole) and `handle-pause` (one line: `answered`, `waiting_on_pm: <reason>`, `skipped: <reason>`, with its detail)
  - [x] Tests with exact text per command and outcome
  - [x] Success: checks pass

**Commit**: `feat: add text renderers for every command`

## 9. Names and doors (D1, D2)

- [x] **9.1 Split `cli/main.py` (a pure move)**
  - [x] `cli/parser.py` (`build_parser()`), `cli/commands.py` (the runners and `_document_for`), `cli/main.py` (`main` and the exit codes). No behavior change; each file stays under about 300 lines
  - [x] Success: the full suite passes with only import paths updated; checks pass
  - Note: the exit codes moved to `cli/exit_codes.py` (re-exported by `cli/main.py`) so `commands.py` can use them without a cycle; tests that patched `cli.invoke`/`cli.handle_pause` now patch `cli.commands`.

**Commit**: `refactor: split cli/main.py into parser, commands and main`

- [x] **9.2 Names, wiring, MCP, detached**
  - [x] `operations/names.py`: add `ADD`, `RM`, `LIST`, remove `SET_UP`; add a `cli_name` property (`_` to `-`). Values stay snake_case
  - [x] `wiring.py`: `invoke` cases for the three (add and rm take the directory; `list` takes it for the default view), each arm one line calling a helper in a new `wiring_registry.py` that places the arguments; extend `OperationResult`, `is_rejected` and `result_document`. `list -j` is the status document, and with `all` the same plus one top-level `settled`
  - [x] `mcp/tools.py`: rows for `add`, `rm`, `list` (request models as input schemas, `directory` added; `add` carries all single-member fields plus `bulk`), none for `set_up`; descriptions name the new operations. `mcp/detached.py` builds its command line from `cli_name` and passes `--json`
  - [x] Rename the old command in user-facing text: the `no_such_question` detail in `operations/answer.py` now says `amoeba handle-pause`, the `set_up` mention in the `mcp/tools.py` description goes with the new rows, and the `mcp/detached.py` docstring; update the `answer` test that asserts the detail
  - [x] Update `tests/mcp_server` and `tests/test_wiring.py` in this step: the tool table has `add`, `rm`, `list` and no `set_up`; the detached child test asserts `handle-pause` and `--json`
  - [x] Success: `tests/mcp_server`, `tests/test_wiring.py` and the `answer` tests pass. The CLI does not import until 9.3 (`parser.py` still names `OperationName.SET_UP`), so `tests/cli`, `tests/test_contract_docs.py` and the live tiers fail until 9.4 and 9.5: expected, do not fix them here. No marker
  - Note: `wiring_registry.py` holds `place_add/place_rm/place_list`; `wiring.py` is now 324 lines.
- [x] **9.3 Parser registration, `-j` and runners for the existing commands**
  - [x] `cli/parser.py`: a parent parser adding `-j/--json` placed after the subcommand, the existing commands (`handle-pause`, `answer`, `status`, `decisions`, `mark-read`, `dismiss`, `retract`) registered by `cli_name`, no alias for any old name. `cli/commands.py`: one runner per command: build the request, call `invoke`, print `result_document` as JSON with `-j`, else the 8.x renderer. `add`, `rm` and `list` are registered in 9.3b
  - [x] Success: pyright clean; `build_parser()` imports and `amoeba handle-pause --help` and `amoeba mark-read --help` run. Tests in `tests/cli` still fail until 9.4: expected
- [x] **9.3b `add`, `rm` and `list` commands**
  - [x] `cli/parser.py` and `cli/commands.py`: register `add`, `rm` (also answering to `remove`) and `list`, with CF names fetched for the `add`/`rm` text. Flags per D4 to D6, building the requests as 5.1's mapping states: `add` (`--program`, `--project`, repeatable `--rules`, `--default-rules`, `--no-rules` mutually exclusive; `--allow`/`--deny` repeatable with `--no-allow`/`--no-deny`; repeatable `--depends-on PROVIDER[:MODE]` with `from_source|from_release`; `--concept MEMBER:PATH` split at the first `:`, an empty side is a usage error; `--file PATH|-` reads YAML into `bulk` and conflicts with every other flag), `rm`, and `list [SUBJECT] [--all] [--program ID]`. `--all` with `members` or `dependencies` is exit 2. Exit codes 0, 1, 2, 3 are unchanged; errors stay `error: <Name>: <message>` on stderr
  - [x] Success: pyright clean; `amoeba add --help`, `amoeba rm --help` and `amoeba list --help` run. The CLI tests, `tests/test_contract_docs.py` and the live tiers fail until 9.4 and 9.5: expected, do not fix them here
  - Note: flags, usage checks and request builders for add/rm/list are in `cli/registration_arguments.py`; each subparser records its operation (`set_defaults(operation=...)`); `check_usage` (called by `main`) refuses `--file` with other add flags and `--all` with members/dependencies (exit 2); text is chosen by type in `cli/render/dispatch.py`; for add/rm text, names come from `cf list projects`, and if that fails ids print and a `note:` line goes to stderr (the write already happened).
- [x] **9.4 Tests for the renamed and existing commands**
  - [x] Rewrite `tests/cli/test_parser_names.py`: every `OperationName` has one command by `cli_name` and a tool row by its value, and nothing else; `rm`/`remove`; singular and plural `list` subjects; an old name (`set_up`, `handle_pause`, `mark_read`) exits 2 with argparse's choice list. End each line in these old-name cases with the comment `# old-name-case`, and nothing else in the file; 12.2's scan skips only lines carrying it
  - [x] Update `test_pause_cli.py`, `test_read_side_cli.py`, `test_dismiss_retract_cli.py`, `test_legacy_move_cli.py` for the new names and text-by-default; each command prints text by default and the existing JSON with `-j`
  - [x] Keep the full suite green: `tests/test_contract_docs.py` requires `amoeba <name>` in `docs/cli-contract.md` for every command. Change it to use each command's `cli_name`, and edit `docs/cli-contract.md` just enough to name `amoeba add`, `amoeba rm`, `amoeba list`, `amoeba handle-pause`, `amoeba mark-read` and drop `amoeba set_up`; the prose rewrite stays in 12.1
  - [x] Delete `test_set_up_cli.py` (its cases move to 9.5). Success: checks pass (the full suite)

**Commit**: `feat: kebab-case command names, text output and -j on every command`

- [x] **9.5 Tests for `add`, `rm` and `list`**
  - [x] `tests/cli/test_add_cli.py`: `amoeba add` with no flag; for each flag the request it builds (D14), including `--no-rules`, `--no-allow`, `--no-deny`, `--default-rules`, an empty side of `--concept` (exit 2), exclusive flags together (exit 2); `--file` equals the old `set_up` result for the same document and conflicts with other flags
  - [x] `test_rm_cli.py` and `test_list_cli.py`: text and `-j`; `list -j` equals `status`'s document and `list --all -j` adds only `settled`; `list programs|members|dependencies -j` print the 7.5 documents; `--all` with `members` is exit 2, with `programs` is accepted; exit 3 when `cf` fails
  - [x] Success: checks pass
  - Note: the subprocess helper is `tests/cli/cli_support.py`; `render_registration`'s first line is `added`, `removed` (only removals) or `changed` (only updates), so `rm` does not say `added`.

**Commit**: `feat: add, rm and list commands with text output and -j on both doors`

## 10. Live tier (D14)

- [x] **10.1 Pause and MCP live tests**
  - [x] `tests/live/pause/harness.py` and its tests: every call goes through the harness's absolute `AMOEBA` path (`Path(sys.executable).with_name("amoeba")`), never the bare name, which on `PATH` is the pre-slice install until task 11. D14 requires the hook itself: following `test_hook_opt_out.py`, the pause test's member `.squadron.toml` sets `pipeline.on_pause_command` to `<absolute AMOEBA path> handle-pause`, the pipeline is started without the opt-out flag, and the test waits for the hook to run and asserts the question is recorded (a calls-log line for the run in the test's `AMOEBA_HOME`, and `list` showing it). The other live tests call `handle-pause` directly as they do today. Replace each `set_up` registration (harness line 106 and `test_lifecycle_walkthrough_live.py`) with `add`, and each `handle_pause` call with `handle-pause`. After the pipeline pauses, `list` shows the question (and `list -j` carries it), and after an answer `list --all` shows it under settled. One member is registered with `add --project NAME` and no rules flag, so it reads the default rules
  - [x] `tests/live/mcp/test_mcp_walkthrough_live.py` uses `add`, `rm`, `list` and `handle_pause`; assert the tool list has no `set_up`. Update the other live files that call `set_up` or an underscore command
  - [x] Run `uv run pytest tests/live/pause` and `uv run pytest tests/live/mcp`
  - [x] Success: both pass; checks pass
  - Note: new `tests/live/pause/test_hook_live.py` runs the real hook (`.squadron.toml` `pipeline.on_pause_command` = absolute amoeba path + `handle-pause`, no opt-out) and checks the calls-log line, the stored question and `list --all` settled. The harness registers the member with `add --program live-pause --project amoeba-live-pause` and no rules flag; `run_amoeba` adds `-j` unless `as_json=False`. Pre-existing failure found and fixed: `test_step_8_removal_is_blocked_by_an_open_question_and_pruning_keeps_it` failed on the base commit too, because prune walks at most once an hour and an earlier call had already walked; the test now removes the prune marker (`PRUNE_MARKER_NAME`) before its `status`. `inert_hook(world)` in the harness puts a do-nothing `amoeba` first on `PATH` for every live world (the user-level hook is now the real installed `amoeba handle-pause`, which would otherwise handle resumed runs behind the test's back); `test_hook_live.py` uses an absolute-path project-level hook instead.

**Commit**: `test: move the live tiers to the 229 command names`

## 11. Cutover (D13)

Note: done on the live machine on 20261114 and verified again 20261114 before checking off (see the notes below).

- [x] **11.1 Designation and backup**
  - [x] Designation: already given. The "Amoeba Design Rules" block of `CLAUDE.md` designates the live store (`~/.local/state/amoeba/amoeba.sqlite3`) and config (`~/.config/amoeba/config.yaml`) for migrations and their config edits, backup first. Confirm that rule is present with `grep -n "designated by default for migrations" CLAUDE.md`; if it is missing, write `BLOCKED: designation rule missing from CLAUDE.md` under this task and stop task 11 here; continue with task 12
  - [x] Backup to a new durable directory for this attempt, `~/amoeba-backup-229-<UTC stamp, YYYYMMDDTHHMMSS>` (call its literal path BACKUP; a retry after a restore makes a new one, so an old directory never blocks it): `cp -R ~/.config/amoeba BACKUP/config`; `cp -R ~/.local/state/amoeba BACKUP/state` (stop any running `amoeba` process first: `pgrep -fl amoeba` finds none). Nothing in this slice removes BACKUP; the PM deletes old ones. Record the member count with `amoeba status` (the installed pre-slice tool has no `list`)
  - [x] Success: both copies exist; the literal path and the counts are in the reply
  - Note: BACKUP is /Users/manta/amoeba-backup-229-20261114T154258 (config/ and state/; the backup store passes integrity_check, schema 4, 3 members). Pre-slice `amoeba status`: program `trading` with 3 members, 0 waiting; the store had 1 question and 0 answers. Cutover: config got default_rules_paths [CLAUDE.md, AGENTS.md], default_consumed from_source, passages_max_chars 250000; `uv tool install --force .` and `sq config set pipeline.on_pause_command "amoeba handle-pause"` ran in one line; `amoeba list members` showed the 3 members with named rules ["CLAUDE.md"], then `amoeba add --project NAME --default-rules` ran for trading-data, trading-ui and trading-engine. Post: store at version 5, 3 active members unchanged, all config_default; `sq config get pipeline.on_pause_command` = `amoeba handle-pause`; `amoeba list` runs. 11.3: the installed `amoeba-mcp` over stdio lists add, answer, decisions, dismiss, handle_pause, list, mark_read, retract, rm, status (no set_up).
- [x] **11.2 Install and re-register**
  - [x] In this order with no pause: add `default_rules_paths: [CLAUDE.md, AGENTS.md]` and `default_consumed: from_source` and set `passages_max_chars: 250000` in `~/.config/amoeba/config.yaml`; then one command line `uv tool install --force . && sq config set pipeline.on_pause_command "amoeba handle-pause"`; then `amoeba list members`, and for each member shown with named rules `amoeba add --project NAME --default-rules`
  - [x] Success: `amoeba list members` shows every member as default rules; the store is at version 5 with the member count unchanged; `sq config get pipeline.on_pause_command` prints `amoeba handle-pause`; `amoeba list` runs. Report results in the reply
  - [x] Restore, only if a success check fails: reinstall the pre-slice tool from a worktree of the target (`git worktree add BACKUP/target-tree {target}`; `uv tool install --force BACKUP/target-tree`; then `git worktree remove BACKUP/target-tree` so the target is free to check out), `sq config set pipeline.on_pause_command "amoeba handle_pause"`, restore `BACKUP/config` and `BACKUP/state` over the two homes (`cp -R BACKUP/config/. ~/.config/amoeba/`, likewise state), using the literal path recorded in 11.1, confirm `amoeba status` works. Write the failing check under this task, fix its cause in the slice, and retry not needed: every success check passed
  - Note: `amoeba list` shows many `directory_missing` unplaced runs: paused Squadron runs left by the live tier (their temp directories are gone); they leave the list when Squadron stops listing them as paused.
- [x] **11.3 Fresh session sees the new tools**
  - [x] Run the installed `amoeba-mcp` through the live MCP walkthrough's stdio client (or its stdio smoke test) and confirm the tool list holds `add`, `rm`, `list` and no `set_up`. The docs (12.1) say open sessions need a restart
  - [x] Success: the tool list matches; reported in the reply

## 12. Documents (D12)

- [x] **12.1 Rules and contract docs**
  - [x] `docs/rules.md` (new, with front matter) from the user's side: what is read and why; only committed files at the target; where it is set (`add`, the config default); the defaults and how to change them (`--rules`, `--default-rules`, `--no-rules`, editing `default_rules_paths`); `list members` shows what a member uses; duplicates and imports; a missing file (default skipped, named fails, nothing found waits on the PM); the size cap and how to size it
  - [x] Rewrite `docs/cli-contract.md` for `add`, `rm`, `list`, text and `-j`, kebab names and the unchanged exit codes; update `docs/mcp-server.md` (new tool table, and the restart note: open sessions run the old server and need a restart), `docs/squadron-hook.md` (hook line `amoeba handle-pause`), `README.md`; update `tests/test_contract_docs.py` for anything else the rewrite changes (the command-list change is in 9.4)
  - [x] Success: `tests/test_contract_docs.py` passes
  - Note: `tests/test_contract_docs.py` now also checks that every add/rm/list flag and every registered-view and request field is named in `docs/cli-contract.md`, and that `rules.md`, `mcp-server.md` and `squadron-hook.md` name what they must.
- [x] **12.2 Old names gone, changelog**
  - [x] `tests/test_old_command_names_gone.py`: scan `src`, `docs`, `README.md`, `tests` (this file itself holds the patterns and is skipped, and so is any line ending `# old-name-case`, which 9.4 puts on the old-name cases) for `amoeba set_up`, `amoeba handle_pause`, `amoeba mark_read` and `OperationName.SET_UP`; the scan is multiline-aware
  - Note: The scan is multiline-aware (`amoeba\nset_up` is found) and skips lines ending `# old-name-case`.
  - [x] `CHANGELOG.md` `[Unreleased]`: slice 229 entry (names, `-j`, `add`/`rm`/`list`, default rules, dedup and imports, migration 005, the two new required config keys marked **behavior change**, the restart note). Only when task 11 completed (not blocked), also say the live store and hook were moved; when it was blocked, the commit message below drops `, record slice 229 cutover`
  - [x] Success: the scan passes; checks pass; `uv run pytest tests/live/pause` and `tests/live/mcp` still pass

**Commit**: `docs: document the human CLI and default rules, record slice 229 cutover`
