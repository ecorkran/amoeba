---
docType: tasks
slice: program-dependencies
project: amoeba
lld: user/slices/227-slice.program-dependencies.md
dependencies:
- 224-slice.status-and-decisions
- 226-slice.mcp-server
- 228-slice.state-home-and-question-lifecycle
projectState: Slices 224, 225 (complete, no verdict), 228 and 226 are designed; 228 is merged, 226 is not built yet. This slice starts after 226 merges. The store baseline already has `dependency_pairs.consumed` and the `releases` table. Neither `report_release` nor `changes` exists. Nobody has run Amoeba.
dateCreated: 20261107
dateUpdated: 20261112
status: not_started
---

# Tasks: Program Dependencies

## Context Summary

- Working on slice 227 (design: `user/slices/227-slice.program-dependencies.md`; decisions D1 to D8 are cited by number).
- Adds `report_release` with three modes (`report`, `correct`, `withdraw`) and `changes`. Both go on the CLI and the MCP table under the same names. `changes` writes nothing and stores no read marker.
- New modules: `store/releases.py`, `Release` in `store/models.py`, `operations/since.py`, `operations/report_release.py`, `operations/changes.py`, `docs/program-rules.md`. Changed: `operations/names.py`, `operations/reject_codes.py`, `operations/decisions.py` (uses `parse_since`), `wiring.py`, `cli/main.py`, `mcp/tools.py`, `docs/store-contract.md`, `docs/cli-contract.md`, `docs/mcp-server.md`.
- No table, no migration. This slice does not change `EXPECTED_SCHEMA_VERSION`; 226 sets it.
- No gate. 225 is complete with no verdict. 226 and 228 must be merged first (task 0.2 checks).
- Take the actual module paths from 222 to 228 over the design's sketches where they differ.
- Closed vocabularies (`ReportMode`, `ReportOutcome`, `ChangesOutcome`, problem codes) are `StrEnum`s defined once. No silent fallbacks. An `IntegrityError` on the `releases` unique key is a bug and is not caught.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`. "Checks pass" means all four.
- Destructive SQL only against throwaway test stores. Tests use the autouse `AMOEBA_HOME` fixture and the replayed `cf` in `tests/cf_fixtures.py`.
- No sample hash, time or version appears near a value an agent must fetch (hallucination trap rule), in docs or in tests that check docs.
- Work on branch `227-slice.program-dependencies`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.
- No task waits on a person or on real use. Integration is proven by the automated flow test and the live fixture test (D7).

## 0. Setup

- [ ] **0.1 Create the branch**
  - [ ] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty
  - [ ] Confirm the working tree is clean and you are on the target
  - [ ] `git checkout -b 227-slice.program-dependencies {target}`
  - [ ] Success: `git branch --show-current` prints `227-slice.program-dependencies`

- [ ] **0.2 Confirm prerequisites and locate inputs**
  - [ ] Confirm 226 is merged: `src/amoeba/wiring.py` (`invoke`, `default_deps`, `OPERATIONAL_ERRORS`), `operations/names.py` (`OperationName`), `mcp/tools.py` (`ToolSpec`, `RunMode`, `TOOLS`) and `build_parser()` in `cli/main.py` exist. If not, write `BLOCKED: slice 226 not merged` under this task and stop
  - [ ] Confirm 228 is merged: `state_layout()` exists in `config/home.py`. If not, write `BLOCKED: slice 228 not merged` and stop
  - [ ] Note the module and signature of each: `Store.read`, `Store.write` (and that it uses `sql.BEGIN_IMMEDIATE`), `resolve_member` and `ContextForgeError` (`operations/members.py`), `project_names` and `ReadProjectNames` on `Deps`, `pairs_of`, `ConsumedMode` (`store/vocabulary.py`), `RejectCode` and `validation_problems` (`operations/reject_codes.py`), `encode_string_list` and `decode_string_list`, `encode_timestamp` and `decode_timestamp` (`store/row_values.py`), the `EXIT_*` constants and `OPERATIONAL_ERRORS`
  - [ ] Confirm the `releases` DDL in `store/schema/001_baseline.sql` has the columns `seq`, `member_id`, `commit_sha`, `version`, `changed`, `touched`, `reported_at`, `versioned_at` and `UNIQUE (member_id, commit_sha)`. If it does not, write `BLOCKED: releases DDL differs from design D2` and stop
  - [ ] Note where `tests/test_contract_docs.py` checks `RejectCode` values against the docs (it iterates `RejectCode` near line 118), and which doc it reads
  - [ ] Find the CLI contract doc (`docs/cli-contract.md` expected) and confirm `docs/mcp-server.md` and `docs/store-contract.md` exist; note any that do not
  - [ ] Find 226's stdio test and its literal tool count, its parity tests, and any literal `takes_directory` name set
  - [ ] Find the replayed `cf` in `tests/cf_fixtures.py` and its recordings in `tests/fixtures/context_forge/`. If no recording of `cf list projects --json` exists, record it once from the real command (read-only) into that folder and note the file
  - [ ] Read `build_world` and `run_amoeba` in `tests/live/pause/harness.py`; note whether `build_world` makes one member or can make two
  - [ ] Find the helpers in `tests/git_repo.py`; note whether a commit can take a committer date (`GIT_COMMITTER_DATE`)
  - [ ] Run the checks once and note the baseline; failures present before this slice are written down, not fixed
  - [ ] Success: a note lists each import path, the timestamp helpers, the stdio test location, the `cf list projects` fixture, the live helper's member count, the git helper's date support, and the baseline result

## 1. Release store (D1, D2, D3)

- [ ] **1.1 `Release` model and `store/releases.py` writers**
  - [ ] Add `Release` to `store/models.py` (frozen, matching the existing model style): `seq`, `commit`, `version`, `changed`, `touched` (tuple of str), `reported_at`, `versioned_at`; `version` and `versioned_at` optional
  - [ ] Create `store/releases.py` with `release_for_commit(tx, member_id, commit)` (a `Release` or none), `insert_release(tx, member_id, commit, version, changed, touched, now)`, `add_version(tx, member_id, commit, version, changed, touched, now)`, `correct_release(tx, member_id, commit, version, changed, touched, now)` and `delete_release(tx, member_id, commit) -> bool`. `touched` is stored with `encode_string_list`. `now` is an argument, never read inside
  - [ ] `insert_release` sets `versioned_at` to `now` only when `version` is given, else null
  - [ ] `add_version` sets `version` and `versioned_at` and replaces `changed` and `touched`; `reported_at` and `seq` do not change
  - [ ] `correct_release` replaces `changed` and `touched`; sets `version` when one is given and keeps the stored one otherwise; sets `reported_at` to `now`; sets `versioned_at` to `now` when the row has a version after the write, else leaves it null
  - [ ] Success: module imports; pyright strict clean

- [ ] **1.2 Writer tests**
  - [ ] Test: insert without a version stores null `version` and `versioned_at`; insert with a version stores both; `touched` round-trips as a list in order
  - [ ] Test: `add_version` on a versionless row sets the version, replaces `changed` and `touched`, and leaves `reported_at` and `seq`; a second `add_version` with a different version on a versioned row does the same
  - [ ] Test: `correct_release` on a versionless row keeps `version` null, moves `reported_at` to `now` and keeps `versioned_at` null; on a versioned row without a new version it keeps the version and sets `versioned_at` to `now`; with a new version it sets that version
  - [ ] Test: `delete_release` removes the row and returns true; for an unknown commit it returns false
  - [ ] Test: `release_for_commit` finds the row for the member and commit, returns none for another member's identical commit, and none for an unknown commit
  - [ ] Test: a duplicate `(member_id, commit_sha)` insert raises `sqlite3.IntegrityError` (not caught by the writer)
  - [ ] Success: tests pass; checks pass

- [ ] **1.3 `visible_releases` and tests (D3)**
  - [ ] Add `visible_releases(tx, provider_id, consumed, since)` to `store/releases.py`. Switch on `ConsumedMode`: `from_source` selects `reported_at >= since` ordered by `reported_at`, `seq`; `from_release` selects `version IS NOT NULL AND versioned_at >= since` ordered by `versioned_at`, `seq`. A `ConsumedMode` value not handled raises an explicit error; there is no default branch that picks one
  - [ ] Test, rows seeded at chosen times through the writers: `from_source` sees a versionless row; `from_release` does not; after `add_version` `from_release` sees it
  - [ ] Test: `from_source` with `since` between `reported_at` and `versioned_at` sees nothing; with an earlier `since` sees one row carrying the version
  - [ ] Test: after `correct_release`, a `from_source` `since` between the original report and the correction sees the row; a `since` after the correction sees nothing
  - [ ] Test: ordering for each mode with three rows seeded out of order; rows of another provider never appear
  - [ ] Success: tests pass; checks pass

**Commit**: `feat: add releases store writers and visibility query`

## 2. Time parsing and `report_release` (D1, D2, D5)

- [ ] **2.1 `operations/since.py` and `decisions` switch (224 D5)**
  - [ ] Create `operations/since.py` with `parse_since(value: str) -> str`. An ISO-8601 string with an offset returns the store's UTC text (`encode_timestamp`). No offset raises `ValueError("has no UTC offset: ...")` and unparseable input raises `ValueError("not an ISO-8601 time: ...")`, with the same message text 224 uses
  - [ ] Replace the body of `DecisionsRequest._utc_text` in `operations/decisions.py` with a call to `parse_since`; the validator's behavior and messages do not change
  - [ ] Test: `+00:00`, `Z` and `-05:00` forms convert to the same UTC instant; no offset and garbage are rejected
  - [ ] Success: 224's tests pass unchanged (no edit to them); pyright strict clean; tests pass

- [ ] **2.2 Request, result models and `RejectCode` additions (D1, D2)**
  - [ ] Add `NOT_A_MEMBER` and `NOT_REPORTED` to `RejectCode` in `operations/reject_codes.py`, and update its docstring to say the vocabulary covers the write side too
  - [ ] Add the two codes to whichever contract doc task 0.2 noted `test_contract_docs` reads, in this commit, so the suite passes at this commit. The fuller contract text comes in 5.3
  - [ ] In `operations/report_release.py` add `ReportMode(StrEnum)` (`report`, `correct`, `withdraw`), `ReportOutcome(StrEnum)` (`recorded`, `versioned`, `corrected`, `unchanged`, `withdrawn`, `rejected`), `ReportReleaseRequest` (frozen, `extra="forbid"`) and `ReleaseReport` (`seq`, `commit`, `version`, `changed`, `touched`, `reported_at`, `versioned_at`) for task 3.1 to reuse
  - [ ] `ReportReleaseRequest` rules, per D1: `commit` stripped, lowercased, 40 or 64 hex characters, with the detail saying `git rev-parse` gives a full hash; `version` stripped and non-empty when given, allowed in `report` and `correct` only; `changed` non-empty, required in `report` and `correct` only; `touched` at least one non-empty string, deduplicated in order, required in `report` and `correct` only. A model validator reports any field the mode does not allow, naming the field and the mode
  - [ ] Test: abbreviated hash, non-hex hash, empty `changed`, empty and missing `touched`, blank `version`, `version` or `touched` in `withdraw`, `changed` in `withdraw`, and an unknown extra field are each rejected by the model; an upper-case hash is stored lowercased; duplicate `touched` items are removed in order
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **2.3 `report_release` operation and tests (D2)**
  - [ ] Implement `report_release(store, document, *, directory, deps)`: validate `document` into the request (failure: `rejected` / `malformed`, with `validation_problems` as the detail); `resolve_member(store, directory, deps.cf_run)` (failure: `rejected` / `not_a_member`, the resolution as detail); take `deps.clock()` once; then one `store.write()` transaction applying D2's table for the request's mode. `unchanged` writes nothing. The result carries the stored report (null after `withdrawn` and on rejection) and the member's CF project id (null when not a member)
  - [ ] Test, `report` mode, one per D2 row, asserting outcome and stored row: a new commit is `recorded` with and without a version; a different version on a versioned commit and a version on a versionless commit are each `versioned` with the text replaced and `reported_at` unmoved; a rephrased repeat is `unchanged` and keeps the stored text; a repeat with the same version is `unchanged`; a versionless repeat on a versioned commit is `unchanged`
  - [ ] Test, `correct` mode: no stored report is `rejected` / `not_reported` and writes nothing; a stored report is `corrected` with the text replaced and `reported_at` moved to now
  - [ ] Test, `withdraw` mode: no stored report is `rejected` / `not_reported`; a stored report is `withdrawn`, the row is gone, and reporting the commit again is `recorded` with a new `seq`
  - [ ] Test: the same commit reported by two different members yields two reports
  - [ ] Test (rejections write nothing): a malformed document and a non-member directory each return `rejected` with the right code and leave `releases` empty
  - [ ] Test: a `cf` failure raises `ContextForgeError` and leaves `releases` empty
  - [ ] Success: module imports; pyright strict clean; tests pass

**Commit**: `feat: add report_release operation and shared since parsing`

## 3. `changes` (D3)

- [ ] **3.1 `changes` models, operation and tests**
  - [ ] In `operations/changes.py` add `ChangesOutcome(StrEnum)` (`listed`, `rejected`), `ChangesRequest` (frozen, `extra="forbid"`; `since` required, validated by `parse_since`), and the result models per D3: `member` and each provider as `{id, name}`, `since` as normalized UTC text, `pairs` of `{provider, consumed, releases}` using task 2.2's `ReleaseReport`, `problems` and `warnings`
  - [ ] Implement `changes(store, document, *, directory, deps)` in this order: validate (`rejected` / `malformed`); call `deps.project_names()` once (a `CfCallFailed` raises `ContextForgeError`); `resolve_member` (`rejected` / `not_a_member`); then one `store.read()` transaction that takes `pairs_of` for the caller's program, keeps the pairs whose consumer is the caller, and calls `visible_releases` for each. Names come from the one `project_names` call. A member or provider id the names do not list keeps its id, gets `name: null`, and adds a `not_in_context_forge` warning. Every pair is listed, even with no releases. Pairs come in `pairs_of`'s order. Nothing is written
  - [ ] Test: a missing `since`, an offset-less `since` and an unknown field are each rejected; a valid `since` is returned normalized to UTC
  - [ ] Test (one provider, a `from_source` and a `from_release` consumer, rows seeded at chosen times): the merge report reaches only `from_source`; after versioning, `from_release` sees it with the release text; a `from_source` `since` between report and tag sees nothing; an earlier one sees one entry with the version
  - [ ] Test: two `since` values each see everything after their own point; a pair with nothing visible is still listed with empty `releases`
  - [ ] Test: a provider's provider is never listed; a member with no providers gets `listed` with empty `pairs`
  - [ ] Test: a non-member directory returns `rejected` / `not_a_member`; a `cf` names failure raises `ContextForgeError`; a provider id missing from the names is listed with `name: null` and one `not_in_context_forge` warning
  - [ ] Test: `changes` leaves the database unchanged (compare a table dump before and after)
  - [ ] Success: module imports; pyright strict clean; tests pass; checks pass

**Commit**: `feat: add changes operation for program dependencies`

## 4. Doors (D5)

- [ ] **4.1 Operation names, `invoke` cases, CLI subcommands and tests**
  - [ ] Add `REPORT_RELEASE = "report_release"` and `CHANGES = "changes"` to `OperationName`
  - [ ] Add a `report_release` case and a `changes` case to `wiring.invoke`, each calling its operation with the caller's directory and the door (226 D4)
  - [ ] Register the two subcommands in `cli/main.py` from `OperationName`, the way 226's task 1.1 does: `report_release --commit --version --changed --touched` (`--touched` with `action="append"`) plus a mutually exclusive group `--correct` and `--withdraw`; and `changes --since`. No flag is `required=True`. Absent flags are left out of the document
  - [ ] Handlers follow the existing handler pattern: build the document, call `invoke` with the current working directory, print the result JSON, return exit `0` for any non-rejected outcome and `1` for `rejected`; `OPERATIONAL_ERRORS` map to `3`; usage errors stay `2`
  - [ ] Test: for each subcommand, a recording fake receives the expected document; a repeated `--touched` arrives as a list in order; an omitted flag is absent from the document; `--correct` with `--withdraw` exits `2`
  - [ ] Test: exit `0` for a recorded or listed result, `1` for a rejected result, `3` for a raised `ContextForgeError`
  - [ ] Test: 226's name-parity test (`build_parser()` subcommands equal `OperationName`) passes with no edit
  - [ ] Success: pyright strict clean; the new CLI tests pass. Adding the names breaks 226's MCP parity tests until task 4.2 adds the rows, so run the full suite after 4.2, not here

- [ ] **4.2 MCP rows, stdio count and tests**
  - [ ] Add two `ToolSpec` rows to `mcp/tools.py`: `RunMode.IN_PROCESS`, `takes_directory = True`, `request_model` set to `ReportReleaseRequest` and `ChangesRequest`. Descriptions say what each call does, that `report_release` also corrects or withdraws, and contain no example values
  - [ ] Change 226's stdio test so its literal tool count becomes one per `OperationName` member (the one edit to a 226 test)
  - [ ] Test: 226's parity tests cover the new rows with no further edit, except a literal `takes_directory` name set if one exists: add the two names and note the edit here
  - [ ] Test: for each new tool, a recording fake replaces the operation; the CLI handler and the MCP in-process path given the same input reach it with equal documents and directories, and the returned dict equals the JSON the CLI prints
  - [ ] Test: a missing or relative `directory` is refused for both new tools
  - [ ] Success: pyright strict clean; tests pass; the AST boundary test still passes (`amoeba.mcp` imports nothing from `store`, `config`, `upstream`, `answering`, `cli`); checks pass

**Commit**: `feat: expose report_release and changes on CLI and MCP`

## 5. Rule blocks and contract docs (D6, D8)

- [ ] **5.1 `docs/program-rules.md`**
  - [ ] Create `docs/program-rules.md` with YAML frontmatter per `file-naming-conventions.md`. It has two blocks, each pasted whole, each saying where it goes: the consumer block (rules file of a member with providers) and the provider block (rules file of a member others depend on, and that repo's release skill after its tag step). Use D6's text exactly. A repo outside a program carries neither
  - [ ] Add a pointer to 222's `set_up` contract for choosing `consumed`, and D2's note that a release merges into a merge report only when the tag is on the reported commit, and that a release flow adding its own commit makes a second report
  - [ ] No sample hash, time or version appears anywhere in the file
  - [ ] Success: the file exists and reads correctly; no credentials in it

- [ ] **5.2 Rule-blocks test**
  - [ ] Test: the file has both blocks; each names its operation and flags exactly as `build_parser()` defines them (extract the flag names from the parser, not from a literal list); the consumer block contains both D4 git commands; neither block contains a 40-hex string
  - [ ] Parse the blocks leniently (by heading or marker, not exact whitespace) and use the real file as the fixture
  - [ ] Success: test passes

- [ ] **5.3 Contract docs (D8)**
  - [ ] `docs/store-contract.md`: `releases` is written only by `report_release`; `touched` is a JSON array; D2's identity, repeat, correction and withdrawal rules; no read record is kept
  - [ ] `docs/cli-contract.md`: both subcommands, their flags including the `--correct` and `--withdraw` group, outcomes and exit codes
  - [ ] `docs/mcp-server.md`: the two tools in the tool list; both take an absolute `directory`; `report_release` takes `mode`
  - [ ] The `RejectCode` values in the contract doc that `test_contract_docs` reads match the code
  - [ ] Success: each doc matches the code (flag names, modes, outcomes, codes); checks pass

**Commit**: `docs: add program rule blocks and release contracts`

## 6. Automated integration and verification

- [ ] **6.1 Flow test (D7)**
  - [ ] Create `tests/program/test_program_flow.py` (default suite). Build a provider repo and a consumer repo with `tests/git_repo.py`, both members of one program in the replayed `cf`
  - [ ] Read the consumer block from `docs/program-rules.md` (by heading, as 5.2 does); run its two git commands in the consumer repo; pass the output as `since` to `changes`
  - [ ] Window case: the consumer commits its design at a set `GIT_COMMITTER_DATE`; the provider reports after that date with a fixed clock; the consumer's `since` still sees the report
  - [ ] Then the provider tags a release and reports it with `--version`; a `from_release` consumer sees the report with the release text; a correction is seen by a consumer whose `since` predates it; a withdrawal removes it from `changes`
  - [ ] Success: the test passes in the default suite

- [ ] **6.2 Live test (D7)**
  - [ ] Create `tests/live/program/test_program_dependencies_live.py` with the helpers in `tests/live/pause/harness.py` (the member count noted in 0.2; if `build_world` makes only one member, make a second one through the same helper and note the change here). Real `cf` and `git`; a throwaway `AMOEBA_HOME`
  - [ ] Run `report_release` and `changes` through the CLI (`run_amoeba`); assert `recorded`, then `unchanged`, then exit `1` with `malformed` for an abbreviated hash, and the consumer's `changes` result listing the report
  - [ ] Success: the live test passes against real `cf`

- [ ] **6.3 Full checks and diff checks**
  - [ ] Run `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest`; all pass
  - [ ] Confirm no migration was added and `EXPECTED_SCHEMA_VERSION` is unchanged by this slice (`git diff {target} -- src/amoeba/store` shows no schema or version edit)
  - [ ] Confirm the only edits to 224 tests are none, and the only edits to 226 tests are the stdio count and, if noted in 4.2, the `takes_directory` name set
  - [ ] Success: all pass; the diff confirms the statements

- [ ] **6.4 Operator walkthrough record**
  - [ ] Record under this task which cases of the design's Operator Walkthrough the flow and live tests cover
  - [ ] Run each uncovered case once in a scratch `AMOEBA_HOME` (`mktemp -d`): bad input, not a member, `cf` failure, no previous design. Record each outcome under this task
  - [ ] Success: each case is recorded as passed, or as blocked by a named prerequisite

**Commit**: `test: add program dependency flow and live tests`
