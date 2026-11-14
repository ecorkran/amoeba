---
docType: tasks
slice: program-dependencies
project: amoeba
lld: user/slices/227-slice.program-dependencies.md
dependencies:
- 224-slice.status-and-decisions
- 226-slice.mcp-server
- 228-slice.state-home-and-question-lifecycle
- 229-slice.human-cli
projectState: Slices 222 to 226, 228 and 229 are merged on main (schema version 5,
  ten operations on the CLI and the MCP server, kebab-case CLI names, text output
  with -j). The store baseline already has `dependency_pairs.consumed` and the `releases`
  table. Neither `report_release` nor `changes` exists. `tests/program/` does not
  exist. Nobody has run Amoeba.
dateCreated: 20261114
dateUpdated: 20261114
status: complete
turns: 36
promptTokens: 2895609
cachedTokens: 2737661
cacheWriteTokens: 157890
completionTokens: 49847
durationSeconds: 354.0
costUsd: 1.404206
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-sonnet-5-5:
    rounds: 3
    costUsd: 1.404207
    completionTokens: 49847
revision_number: 2
---

# Tasks: Program Dependencies

## Context Summary

- Working on slice 227 (design: `user/slices/227-slice.program-dependencies.md`; decisions D1 to D8 are cited by number). Effort 3/5.
- Adds `report_release` (modes `report`, `correct`, `withdraw`) and `changes`. Both go on the CLI (`report-release`, `changes`) and the MCP table under the same operation names. `changes` writes nothing and stores no read marker.
- New modules: `store/releases.py`, `Release` in `store/models.py`, `operations/since.py`, `operations/report_release_models.py` (request, result and the shared `ReleaseReport`), `operations/release_member.py`, `operations/report_release.py`, `operations/changes.py`, `cli/render/releases.py`, `docs/program-rules.md`. Changed: `operations/names.py`, `operations/reject_codes.py`, `operations/decisions.py`, `wiring.py`, `cli/parser.py`, `cli/commands.py`, `cli/render/dispatch.py`, `mcp/tools.py`, `mcp/server.py` (instructions), `docs/store-contract.md`, `docs/cli-contract.md`, `docs/mcp-server.md`, `README.md`.
- No table, no migration. `EXPECTED_SCHEMA_VERSION` is not changed by this slice. Nothing in `store/schema/` changes.
- Out of scope: pasting the rule blocks into other repos' rules files and release skills. Those are commits in those repos, made by their own agent sessions once this slice has merged (design, Operator Walkthrough, Start); this slice delivers the blocks and the tests that prove them.
- No gate: 225 is complete with no verdict. 224, 226, 228 and 229 are merged (task 0.1 checks).
- Decisions made by these tasks where the design is silent: the shared `ReleaseReport` result model lives in `report_release_models.py`; the MCP server `INSTRUCTIONS` gain the two operations (`test_instructions_name_every_tool` requires every tool named) and the README command list gains them so it is not stale; `changes` is a read tool for timeout advice (`READ_ADVICE`), `report_release` a write tool (`WRITE_ADVICE`).
- Closed vocabularies (`ReportMode`, `ReportOutcome`, `ChangesOutcome`, `ChangesWarningCode`, the two new `RejectCode` members) are each a `StrEnum` defined once; a problem's `code` is typed `RejectCode`. No silent fallbacks. An `IntegrityError` on the `releases` unique key is a bug and is not caught.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. "Checks pass" means all four. The live tier is `uv run pytest tests/live/<dir>` (never in a bare run; LLM spend is pre-authorized).
- Tests use the autouse `AMOEBA_HOME` fixture, the replayed `cf` (`tests/cf_fixtures.py`, `tests/operations/status_support.py`), `tests/store/seed.py` and `tests/git_repo.py`. Destructive SQL only against throwaway test stores.
- No sample hash, time or version appears near a value an agent must fetch (hallucination-trap rule), in docs or in tests that check docs.
- Keep each source file to about 300 lines and each function to about 50; split a module that grows past that.
- Work on branch `227-slice.program-dependencies`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push. No task waits on a person or on real use.

## 0. Setup

- [x] **0.1 Branch, prerequisites, inputs and baseline**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty. With the target checked out, if `git status` shows this slice's design or task file uncommitted, commit each on the target first, one commit per document: `docs: add the slice 227 design` and `docs: add the slice 227 task breakdown` (planning commits go on the target, not the branch). Then `git checkout -b 227-slice.program-dependencies {target}`
  - [x] Confirm 224, 226, 228 and 229 are merged: `DecisionsRequest` in `operations/decisions.py` (224); `OperationName`, `ToolSpec`, `TOOLS` and `invoke` in `operations/names.py`, `mcp/tools.py` and `wiring.py` (226); `state_layout` in `config/home.py` (228); `OperationName.cli_name`, `build_parser()` in `cli/parser.py` and `run_invoked` in `cli/commands.py` (229). If any is missing, write `BLOCKED: slice <number> not merged` under this task and stop
  - [x] Confirm the `releases` DDL in `store/schema/001_baseline.sql` has `seq`, `member_id`, `commit_sha`, `version`, `changed`, `touched`, `reported_at`, `versioned_at` and `UNIQUE (member_id, commit_sha)`. If not, write `BLOCKED: releases DDL differs from design D2` and stop
  - [x] Confirm D4's first git command runs in this repo: `git log -1 --diff-filter=A --format=%aI -- project-documents/user/slices/` prints an ISO-8601 time with an offset
  - [x] Run the four checks once. If any fails before this slice's work, write `BLOCKED: baseline red: <failing checks>` under this task and stop, since the slice's success criteria need them green
  - [x] Success: `git branch --show-current` prints `227-slice.program-dependencies`; the four checks pass; a note under this task gives the target's name
  Note: target is main (git.integration_branch is empty); the slice branch 227-slice.program-dependencies was already present at main's head.

## 1. Release store (D1, D2, D3)

- [x] **1.1 `Release` model and `store/releases.py` writers**
  - [x] Add `Release` to `store/models.py` (frozen dataclass, the file's style): `seq`, `commit`, `version`, `changed`, `touched` (tuple of str), `reported_at`, `versioned_at`; `version` and `versioned_at` optional
  - [x] Create `store/releases.py` (SQL constants in `store/sql.py`): `release_for_commit(tx, member_id, commit)` (a `Release` or none), `insert_release(tx, member_id, commit, version, changed, touched, now)`, `add_version(...)`, `correct_release(...)` (same arguments) and `delete_release(tx, member_id, commit) -> bool`. `touched` is stored with `encode_string_list` and read with `decode_string_list`
  - [x] `insert_release`: `reported_at` is `now`; `versioned_at` is `now` only when `version` is given, else null
  - [x] `add_version`: sets `version` and `versioned_at` to `now`, replaces `changed` and `touched`; `reported_at` and `seq` do not change
  - [x] `correct_release`: replaces `changed` and `touched`; sets `version` when given, else keeps the stored one; `reported_at` is `now`; `versioned_at` is `now` when the row has a version after the write, else null
  - [x] Success: module imports; pyright strict clean

- [x] **1.2 Writer tests** (`tests/store/test_releases.py`)
  - [x] Insert without a version stores null `version` and `versioned_at`; with a version stores both; `touched` round-trips as a tuple in order
  - [x] `add_version` on a versionless row sets the version and replaces the text, keeping `reported_at` and `seq`; a second `add_version` with a different version on a versioned row does the same
  - [x] `correct_release` on a versionless row keeps `version` null, moves `reported_at` to `now`, keeps `versioned_at` null; on a versioned row without a new version keeps the version and sets `versioned_at` to `now`; with a new version sets that version
  - [x] `delete_release` removes the row and returns true; for an unknown commit returns false; a re-insert of the deleted commit gets a higher `seq`
  - [x] `release_for_commit` finds the member's row, returns none for another member's identical commit and for an unknown commit
  - [x] A duplicate `(member_id, commit_sha)` insert raises `sqlite3.IntegrityError`; the writer does not catch it
  - [x] Success: tests pass; checks pass
  Note: a duplicate (member_id, commit_sha) insert raises amoeba.store.errors.StoreIntegrityError, not sqlite3.IntegrityError, because Transaction.execute wraps sqlite3 errors in typed StoreErrors; the test asserts StoreIntegrityError and the writer does not catch it.

- [x] **1.3 `visible_releases` and tests (D3)**
  - [x] Add `visible_releases(tx, provider_id, consumed, since)` to `store/releases.py` with a `match` on `ConsumedMode` and `assert_never` in the last case: `from_source` selects `reported_at >= since` ordered by `reported_at`, `seq`; `from_release` selects `version IS NOT NULL AND versioned_at >= since` ordered by `versioned_at`, `seq`. `since` is the store's UTC text
  - [x] Test, rows seeded at chosen times through the writers: `from_source` sees a versionless row and `from_release` does not; after `add_version` `from_release` sees it with the release text
  - [x] Test: `from_source` with `since` between `reported_at` and `versioned_at` sees nothing; with an earlier `since` sees one row carrying the version
  - [x] Test: after `correct_release`, a `from_source` `since` between the original report and the correction sees the row and a `since` after it sees nothing; a `from_release` reader sees a corrected row only once it is versioned
  - [x] Test: ordering for each mode with three rows seeded out of order; another provider's rows never appear
  - [x] Success: tests pass; checks pass

**Commit**: `feat: add releases store writers and visibility query`

## 2. Time parsing, reject codes and `report_release` (D1, D2, D5)

- [x] **2.1 `operations/since.py` and the `decisions` switch**
  - [x] Create `operations/since.py` with `parse_since(value: str) -> str`: an ISO-8601 string with an offset returns the store's UTC text (`encode_timestamp`); a string with no offset raises `ValueError(f"has no UTC offset: {value!r}")`; one that does not parse raises `ValueError(f"not an ISO-8601 time: {value!r}")`. Move the logic out of `DecisionsRequest._utc_text` (`operations/decisions.py`) with its messages unchanged
  - [x] `DecisionsRequest._utc_text` keeps its `None` pass-through and calls `parse_since` for a value
  - [x] Test (`tests/operations/test_since.py`): `+00:00`, `Z` and `-05:00` forms of one instant give the same text; no offset and garbage each raise with the message text above; surrounding whitespace is stripped
  - [x] Success: the existing decisions tests pass with no edit; pyright strict clean; tests pass

- [x] **2.2 `RejectCode` additions (D5)**
  - [x] Add `NOT_A_MEMBER = "not_a_member"` and `NOT_REPORTED = "not_reported"` to `RejectCode`; update the module docstring to say it covers the write side too
  - [x] Add both values, each in backticks with a one-line meaning, to `docs/cli-contract.md` where the other reject codes are listed, so `test_the_cli_contract_names_every_command_exit_code_and_result_value` passes at this commit. The fuller contract text comes in 4.4
  - [x] `tests/operations/test_decisions_request.py` asserts the exact set of `RejectCode` values (`test_the_rejection_codes_are_the_three_the_design_names`): update it to the five codes and rename it to a count-free name
  - [x] Success: `uv run pytest tests/test_contract_docs.py tests/operations/test_decisions_request.py` passes; checks pass
  Note: docs/cli-contract.md gained a "Release rejection codes" section naming not_a_member and not_reported; task 4.4 adds the fuller contract text.

**Commit**: `feat: share since parsing and add the release reject codes`

- [x] **2.3 Request and result models (D1, D2)**
  - [x] Create `operations/report_release_models.py`: `ReportMode(StrEnum)` (`report`, `correct`, `withdraw`), `ReportOutcome(StrEnum)` (`recorded`, `versioned`, `corrected`, `unchanged`, `withdrawn`, `rejected`), `ReportReleaseRequest` (frozen, `extra="forbid"`, `mode` default `report`), `ReleaseReport` (`seq`, `commit`, `version`, `changed`, `touched` list, `reported_at`, `versioned_at`, times as UTC text; the one `report` shape for both operations), `ReleaseProblem` (`code`, `detail`) and `ReportReleaseResult` (`outcome`, `member`, `report`, `problems`)
  - [x] `ReportReleaseRequest` rules per D1, in one model validator plus field validators: `commit` required in every mode, stripped, lowercased, 40 or 64 hex characters, the detail saying `git rev-parse` gives a full hash; `version` stripped and non-blank when given, not allowed in `withdraw`; `changed` required and non-blank in `report` and `correct`, not allowed in `withdraw`; `touched` required in `report` and `correct`, at least one non-blank item, duplicates removed with order kept, not allowed in `withdraw`. A field the mode does not allow is an error naming the field and the mode
  - [x] Test (`tests/operations/test_report_release_request.py`): per mode, each of these is rejected by the model: abbreviated hash, non-hex hash, missing hash, empty `changed`, empty and missing `touched`, blank `version`, `version`, `changed` or `touched` in `withdraw`, an unknown field. An upper-case hash is stored lowercased; duplicate `touched` items are removed in order; a 64-character hash is accepted
  - [x] Success: module imports; pyright strict clean; tests pass

- [x] **2.4 `report_release` operation and tests (D2)**
  - [x] Implement `report_release(store, document, *, directory, deps)` in `operations/report_release.py`: validate (failure: `rejected` / `malformed`, details from `validation_problems`, `member` null); the member from `resolve_release_member` before any write transaction (failure: `rejected` / `not_a_member`; see the next item); take `now = deps.clock()` once; then one `store.write()` transaction that reads `release_for_commit` and applies the D2 table. The result carries the stored report after the call (null after `withdrawn` and on rejection)
  - [x] Define the member rule once, in `operations/release_member.py`: `resolve_release_member(store, directory, cf_run)` calls `resolve_member` and returns the `Member`, or a `ReleaseProblem` (`not_a_member`) whose detail says "this Context Forge project is in no program" for `NotInProgram`, and "this directory is in no Context Forge project" followed by Context Forge's message for `NotAProject`. `ContextForgeError` propagates. `changes` (3.2) calls the same function
  - [x] Keep the D2 case table in one function that returns the outcome and the write to make, so each row is one visible branch; split the module if it passes about 300 lines
  - [x] Test, `report` mode, one per D2 row, asserting outcome and stored row: a new commit is `recorded` with and without a version; a different version on a versioned commit, and a version on a versionless commit, are each `versioned` with the text replaced and `reported_at` and `seq` unmoved; a rephrased repeat is `unchanged` and keeps the stored text and returns the stored report; a repeat with the same version is `unchanged`
  - [x] Test, `correct`: no stored report is `rejected` / `not_reported` and writes nothing; a stored report is `corrected` with the text replaced and `reported_at` at the call's time
  - [x] Test, `withdraw`: no stored report is `rejected` / `not_reported`; a stored report is `withdrawn` and the row is gone; reporting the commit again is `recorded` with a new `seq`
  - [x] Test: the same commit reported by two members gives two reports; a malformed document and a non-member directory (the `NotInProgram` and the `NotAProject` detail, tested here once for both operations) are `rejected`, return the right code and leave `releases` empty; a `cf` failure raises `ContextForgeError` and leaves `releases` empty
  - [x] Success: module imports; pyright strict clean; tests pass; checks pass

**Commit**: `feat: add the report_release operation`

## 3. `changes` and its output (D3, D5)

- [x] **3.1 `changes` models and request validation**
  - [x] In `operations/changes_models.py` add `ChangesOutcome(StrEnum)` (`listed`, `rejected`), `ChangesRequest` (frozen, `extra="forbid"`; `since` required, validated by `parse_since`), `MemberRef` (`id`, `name` or null), `ProviderPair` (`provider`, `consumed`, `releases` as `ReleaseReport`), `ChangesWarningCode(StrEnum)` (`not_in_context_forge`) and `ChangesWarning` (`code`, `detail`, naming the id) and `ChangesResult` (`outcome`, `member`, `since`, `pairs`, `problems`, `warnings`). `problems` reuse `ReleaseProblem` with codes `malformed` and `not_a_member`
  - [x] Test (`tests/operations/test_changes_request.py`): a missing `since`, an offset-less `since`, an unparseable `since`, an empty `since` and an unknown field are each rejected; a valid `since` comes back as normalized UTC text
  - [x] Success: module imports; pyright strict clean; tests pass

- [x] **3.2 `changes` operation and tests (D3)**
  - [x] Implement `changes(store, document, *, directory, deps)` in `operations/changes.py`, in this order: validate (`rejected` / `malformed`); `deps.project_names()` once (a `CfCallFailed` raises `ContextForgeError` with its detail); `resolve_release_member` (`rejected` / `not_a_member`); then one `store.read()` transaction that takes `pairs_of` for the caller's program, keeps the pairs whose consumer is the caller, and calls `visible_releases` for each. Writes nothing; no `cf` call runs inside the transaction
  - [x] Every pair is listed, including pairs with nothing visible; a member with no providers gets `listed` with empty `pairs`; pairs keep `pairs_of`'s order. A member or provider id missing from the names keeps its id, gets `name: null` and one `not_in_context_forge` warning; the outcome stays `listed`
  - [x] Test (one provider; a `from_source` and a `from_release` consumer; rows seeded at chosen times): the merge report reaches only `from_source`; after versioning `from_release` sees it with the release text; a `from_source` `since` between report and tag sees nothing and an earlier one sees one entry with the version; a corrected report is seen by a `since` before the correction and not after it
  - [x] Test: two `since` values each see everything after their own point; a pair with nothing visible is listed with empty `releases`; a provider's provider is never listed; a member with no providers gets empty `pairs`; a pair whose member was removed (228's active-member rule) is not listed
  - [x] Test: a non-member directory returns `rejected` / `not_a_member`; a `cf` names failure raises `ContextForgeError`; a provider id absent from the names is listed with `name: null` and one `not_in_context_forge` warning; the member's own id absent gives the same warning
  - [x] Test: `changes` leaves the database unchanged: a dump of every table before and after is equal
  - [x] Success: module imports; pyright strict clean; tests pass; checks pass

**Commit**: `feat: add the changes operation for program dependencies`

- [x] **3.3 Result plumbing and text renderers**
  - [x] In `wiring.py` add `ReportReleaseResult` and `ChangesResult` to `OperationResult` and both `REJECTED` outcomes to `is_rejected`
  - [x] Create `cli/render/releases.py` with `render_report_release(result)` and `render_changes(result)`, and add both to `render_result` in `cli/render/dispatch.py`. The first line of `report_release` is D5's: `reported` for both `recorded` and `versioned`, `unchanged`, `corrected`, `withdrawn`, or `rejected: <code>` followed by each problem's detail. `changes` prints one entry per report (provider name or id, commit, version, changed text cut to the line width the other renderers use, the touched items), warnings as lines, and `No changes since <time>.` when no pair has a release
  - [x] Test (`tests/cli/render/test_releases.py`): each outcome's first line (`recorded` and `versioned` both `reported`); a rejected result prints its code and detail; `changes` with two providers, one with a long `changed` text (cut), one empty; `No changes since` appears only when every pair is empty; a warning is printed
  - [x] Test (`tests/test_wiring.py`): a rejected `ReportReleaseResult` or `ChangesResult` is `is_rejected`; a `recorded`, `unchanged` or `listed` one is not; `result_document` gives the JSON shape of the design's Implementation Details
  - [x] Success: pyright strict clean (the `render_result` and `is_rejected` matches stay exhaustive); tests pass; checks pass

**Commit**: `feat: render and classify the release results`

## 4. Doors (D5)

Section 4 is one unit: the new `OperationName` members make existing parity, contract-doc and instruction tests fail until the CLI, the MCP rows, the instructions and the docs all exist, so the suite is red from 4.1 to 4.4 and the one commit is at the end. The edits to existing tests are all made in 4.1, so every later failure is a real one. Run only the new tests until 4.4, then the full suite.

- [x] **4.1 Names, `invoke` cases and the existing-test edits**
  - [x] Add `REPORT_RELEASE = "report_release"` and `CHANGES = "changes"` to `OperationName`
  - [x] Edit the existing tests the names break, here and nowhere later: add both names to the literal set in `tests/cli/test_parser_names.py` (rename its test from "eleven" to a count-free name); add both names to `DIRECTORY_TOOLS` and `CHANGES` to `READ_TOOLS` in `tests/mcp_server/test_tools.py`; in `tests/test_contract_docs.py` add the `ReportOutcome`, `ReportMode` and `ChangesOutcome` values and the `ChangesWarningCode` value to the list it checks against `cli-contract.md`. `test_stdio_smoke.py` needs no edit
  - [x] In `wiring.py` add an `invoke` case for each, calling its operation with `_required_directory(name, directory)` and `default_deps(layout)` (the same pattern as `STATUS`), each about four lines, the way `STATUS` is
  - [x] Test (`tests/test_wiring.py`, following the existing `invoke` tests): each name through `invoke` reaches its operation with the directory; a missing directory raises `ValueError`
  - [x] Success: pyright strict clean (the `invoke` match stays exhaustive); the new tests pass
  Note: two more existing tests needed edits than this task lists, both hardcoded per-operation tables: tests/cli/test_parser_names.py (also test_every_command_takes_json_after_its_name) and tests/mcp_server/test_in_process.py (the READ set in test_the_timed_out_text_carries_that_tools_advice, and two parity CASES entries). Task 6.3's list of edited existing tests must include tests/mcp_server/test_in_process.py.

- [x] **4.2 CLI subcommands and request documents**
  - [x] In `cli/parser.py` register `report-release` and `changes` through `_command` (so each gets `-j`): `report-release` takes `--commit`, `--version`, `--changed`, `--touched` (`action="append"`, repeatable) and a mutually exclusive group `--correct`, `--withdraw`; `changes` takes `--since`. No flag is `required=True`. Move the two registrations into a new `cli/release_arguments.py` if `parser.py` would pass about 300 lines
  - [x] In `cli/commands.py` extend `_document_for`: `report-release` builds the document from the flags given (absent flags are left out; `--correct` sets `mode` to `correct`, `--withdraw` to `withdraw`, neither leaves `mode` out); `changes` builds `{since}` when given. Exit codes come from `run_invoked`: 0 for a non-rejected outcome, 1 for rejected, 2 usage, 3 for `OPERATIONAL_ERRORS`
  - [x] Test (`tests/cli/test_release_cli.py`, following `tests/cli/test_read_side_cli.py`): each subcommand run with `-j` prints the result document; exit 0 for `recorded` and `listed`, 1 for a `malformed` rejection (such as an abbreviated hash), 2 for `--correct` with `--withdraw`, 3 for a `cf` failure; a repeated `--touched` reaches the operation as a list in order; an omitted flag is absent from the document; `--withdraw` sets `mode` to `withdraw`
  - [x] Success: pyright strict clean; the new CLI tests pass

- [x] **4.3 MCP rows, instructions and the door-equivalence test**
  - [x] Add two `ToolSpec` rows to `mcp/tools.py`: `RunMode.IN_PROCESS`, `takes_directory=True`, `request_model` `ReportReleaseRequest` and `ChangesRequest`; `timeout_advice` `WRITE_ADVICE` for `report_release` and `READ_ADVICE` for `changes`. Descriptions say what each call does, that `report_release` also corrects or withdraws, and contain no example values
  - [x] Add both tools to `INSTRUCTIONS` in `mcp/server.py`, each named in backticks with what it is for: `changes` before designing a slice, `report_release` after a merge or release that other repos use
  - [x] Test (`tests/mcp_server/test_release_tools.py`, a fake `cf` on `PATH` as `tests/cli/cli_support.py` provides, a seeded store, the real operations): the same request given as CLI flags and as MCP arguments gives equal result documents for `report_release` and for `changes`; a directory in no program gives `not_a_member` through both doors and leaves `releases` empty. 226's parity tests already cover the rows and the `directory` rule, so this test does not repeat them
  - [x] Success: pyright strict clean; the AST boundary test (`tests/test_import_boundaries.py`) still passes (`amoeba.mcp` imports nothing from `store`, `config`, `upstream`, `answering`, `cli`); the MCP tests pass

- [x] **4.4 Contract docs for the doors, and the contract-doc test lists**
  - [x] `docs/cli-contract.md`: a section for `amoeba report-release` and one for `amoeba changes` (flags including the `--correct`/`--withdraw` group, modes, outcomes, problem codes, warnings, exit codes, the JSON shapes from the design's Implementation Details); add both names to the "Names" paragraph. Every flag the parser has is named in backticks
  - [x] `docs/mcp-server.md`: two rows in the tools table; both take an absolute `directory`; `report_release` takes `mode`
  - [x] `README.md`: add `report-release` and `changes` to the command list in the first paragraph
  - [x] Success: the full suite passes; checks pass

**Commit**: `feat: expose report_release and changes on the CLI and MCP server`

## 5. Rule blocks and the store contract (D6, D8)

- [x] **5.1 `docs/program-rules.md`**
  - [x] Create `docs/program-rules.md` with YAML frontmatter per `file-naming-conventions.md`. It holds two blocks, each pasted whole and each saying where it goes: the consumer block (rules file of a member with providers) and the provider block (rules file of a member others depend on, and that repo's release skill after its tag step). Use D6's text exactly, including the `-j` flag and both D4 git commands in the consumer block. A repo outside a program carries neither
  - [x] Add a pointer, as D8 puts it in this file, to where choosing `consumed` is documented: the `--depends-on PROVIDER[:MODE]` row of `amoeba add` in `docs/cli-contract.md` and `default_consumed` in `docs/config-contract.md`; D2's note that a release merges into a merge report only when the tag is on the reported commit and that a release flow adding its own commit makes a second report; and D4's note that a member whose slice designs live elsewhere edits the path in the pasted block
  - [x] No sample hash, time or version appears anywhere in the file
  - [x] Success: the file exists and reads correctly

- [x] **5.2 Rule-blocks test** (`tests/test_program_rules_doc.py`)
  - [x] Create `tests/rule_blocks.py` with `rule_blocks(text)`, which returns the consumer and provider blocks, parsed leniently (by heading, tolerant of whitespace and heading depth); task 6.1 imports it from there. The real file is the fixture
  - [x] Test: both blocks exist; each names its operation (`amoeba changes`, `amoeba report-release`) and every flag it uses; take the valid flags from `build_parser()` (the `_option_flags` approach in `tests/test_contract_docs.py`), never from a literal list; the consumer block contains both D4 git commands; neither block contains a 40-hex string
  - [x] Success: the test passes

- [x] **5.3 `docs/store-contract.md` (D8)**
  - [x] Update the `releases` section (heading "written by slice 227" stays accurate): written only by `report_release`; `touched` is a JSON array; the D2 identity, repeat, versioning, correction and withdrawal rules; times move on correction; no read record is kept; rows are one per reported commit; `withdraw` is the explicit cancel for a registered member's row; removing a member keeps its rows as the record (228 D8) and no cleanup runs
  - [x] Success: `tests/test_contract_docs.py` passes; the text matches the code; checks pass

**Commit**: `docs: add the program rule blocks and the release contract`

## 6. Automated integration and verification (D7)

- [x] **6.1 Flow test**
  - [x] Create `tests/program/__init__.py` and `tests/program/test_program_flow.py` (default suite). Build a provider repo and a consumer repo from `tests/git_repo.py`, both members of one program (seeded through `tests/store/seed.py`), with a replayed `cf` giving each directory its own project id and names (`status_support.FakeCf`; `program_rig.py` serves one concept repo with one project and does not fit)
  - [x] Read the consumer block from `docs/program-rules.md` (`rule_blocks` from `tests/rule_blocks.py`). Locate its git commands as the inline-code spans that start with `git `; run each with `subprocess.run(["sh", "-c", span], cwd=<consumer repo>)` (the second has a pipe), take the first command's stripped output as `since` and the second's only when the first printed nothing, and pass it to `changes`. Set author and committer dates separately with `git(..., env={"GIT_AUTHOR_DATE": ..., "GIT_COMMITTER_DATE": ...})`; `commit_file(date=)` cannot do that
  - [x] Window case: the consumer commits its slice design at a set author date; the provider then reports (a fixed `deps.clock` after the design commit); the consumer's `since`, taken from the block's command before its own merge, still sees the report
  - [x] Rebase case: the consumer's branch is rebased onto a newer commit with `GIT_COMMITTER_DATE` after the report; `since` taken again from the block's command still sees the report (this fails if the block used committer time)
  - [x] No previous design: in a repo with no commit under the slices path, the fallback command's output is the root commit's time and `changes` accepts it. In a repo with no commits at all, both commands print nothing to stdout, and `changes` with that empty `since` is `rejected` / `malformed`
  - [x] Release case: the provider tags and reports the tagged commit with a version; a `from_release` consumer sees it with the release text; a correction is seen by a consumer whose `since` predates it; a withdrawal removes it from `changes`
  - [x] Two worktrees (success criterion 4): add a second worktree of the consumer with `git worktree add`; the replayed `cf` gives both directories the one project id; each worktree's own branch gives its own `since` from the block's command, and each `changes` call sees everything since its own point and no more
  - [x] Success: the test passes in the default suite

- [x] **6.2 Live test**
  - [x] Create `tests/live/program/__init__.py`, a `conftest.py` and `test_program_dependencies_live.py`. Build the provider with `build_world` unchanged. Build the consumer in a helper inside `tests/live/program/` (the shared harness is not edited): it reuses the provider world's environment, so both members share one `cf-data` directory (one `cf list projects` shows both) and one `AMOEBA_HOME` and config (one program in one store); it makes its own repo, runs `cf init --lite --name` with that environment, and runs `add --program` with `--depends-on` naming the provider through `run_amoeba`, on `dataclasses.replace(provider_world, repo=<consumer repo>)`. The `AMOEBA_LIVE_*` settings `build_world` needs for its config are read the way `tests/live/pause/conftest.py` does; no model runs
  - [x] Real `cf` and `git`, a throwaway `AMOEBA_HOME`. Through the CLI (`run_amoeba`): provider `report-release` with the full hash gives `recorded`; the same call again gives `unchanged`; an abbreviated hash gives exit 1 and `malformed`; the consumer's `changes` lists the report with its provider name (this exercises the real `cf list projects` output through `project_names`); a call from a directory outside every member gives `not_a_member`; a second worktree of the consumer (`git worktree add`) resolves through real `cf` to the same member, and its `changes` call with a later `since` sees less than the main checkout's call with an earlier one (success criterion 4 against real `cf`)
  - [x] Success: `uv run pytest tests/live/program` passes with real `cf` and `git`

- [x] **6.3 Full checks and diff checks**
  - [x] Run the four checks; all pass
  - [x] `git diff {target} --stat -- src/amoeba/store` shows no schema file and no change to `EXPECTED_SCHEMA_VERSION` in `store/migrations.py`
  - [x] The only existing tests edited are those named in 2.2 and 4.1: `git diff {target} --stat -- tests` shows new files plus only `tests/operations/test_decisions_request.py`, `tests/cli/test_parser_names.py`, `tests/mcp_server/test_tools.py`, `tests/mcp_server/test_in_process.py`, `tests/test_contract_docs.py` and `tests/test_wiring.py`
  - [x] Success: all pass and the diffs confirm the statements

**Commit**: `test: add the program dependency flow and live tests`
