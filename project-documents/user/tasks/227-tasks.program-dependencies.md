---
docType: tasks
slice: program-dependencies
project: amoeba
lld: user/slices/227-slice.program-dependencies.md
dependencies:
- 224-slice.status-and-decisions
- 225-slice.scenario-a-trial
- 226-slice.mcp-server
projectState: Slices 222 to 226 are designed and tasked; this slice assumes they are
  merged and that 225's trial gave a go verdict. The store baseline already has `dependency_pairs.consumed`
  and the `releases` table. The CLI and the MCP server expose six operations; neither
  has `report_release` or `changes`. Nobody has run Amoeba.
dateCreated: 20261107
dateUpdated: 20261108
status: not_started
turns: 8
promptTokens: 253298
cachedTokens: 211897
cacheWriteTokens: 41389
completionTokens: 8841
durationSeconds: 58.2
costUsd: 0.275476
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.27547560000000004
    completionTokens: 8841
---

# Tasks: Program Dependencies

## Context Summary

- Working on slice 227 (design: `user/slices/227-slice.program-dependencies.md`; decisions D1 to D8 are cited by number).
- Adds two operations, `report_release` (a provider records what it released) and `changes` (a consumer reads its providers' reports since a time it gives). Both go on the CLI and the MCP table under the same names. `changes` writes nothing and stores no read marker.
- New modules: `store/releases.py`, `Release` in `store/models.py`, `operations/since.py`, `operations/report_release.py`, `operations/changes.py`, `docs/program-rules.md`. Changed: `operations/names.py`, `cli/main.py`, `mcp/tools.py`, `decisions` (uses `parse_since`), `docs/store-contract.md`, the CLI contract, `docs/mcp-server.md`.
- No table, no migration: `EXPECTED_SCHEMA_VERSION` is unchanged. No new packages. No change to `set_up`.
- Gate: built only after 225's trial gave a go verdict. If the verdict was rethink, write `BLOCKED:` under task 0.2 and stop.
- Take 222 to 226's actual module paths over the design's sketches where they differ.
- Closed vocabularies (`ReportOutcome`, `ChangesOutcome`, problem codes) are `StrEnum`s defined once. No silent fallbacks. Exceptions follow the project rule. An `IntegrityError` on the `releases` unique key is a bug and is not caught.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`. "Checks pass" means all four.
- Destructive SQL only against throwaway test stores. Tests use the autouse `AMOEBA_HOME` fixture and 222's fake `cf`.
- No sample hash, time or version appears near a value an agent must fetch (hallucination trap rule), in docs or tests that check docs.
- Work on branch `227-slice.program-dependencies`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.

## 0. Setup

- [ ] **0.1 Create the branch**
  - [ ] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty
  - [ ] Confirm the working tree is clean and you are on the target
  - [ ] `git checkout -b 227-slice.program-dependencies {target}`
  - [ ] Success: `git branch --show-current` prints `227-slice.program-dependencies`

- [ ] **0.2 Confirm prerequisites and locate inputs**
  - [ ] Confirm 225's trial recorded a go verdict (find its verdict record under `user/`). If it is absent or says rethink, write `BLOCKED: 225 verdict is not go` under this task and stop
  - [ ] Confirm 224 and 226 are merged: `operations/names.py` (`OperationName`), `mcp/tools.py` (`ToolSpec`, `RunMode`, `TOOLS`), `wiring.default_deps()`, `build_parser()` and `operations/decisions.py` exist. If not, write `BLOCKED: slices 222-226 not merged` and stop
  - [ ] Find the module and signature of each of: `Store.open`, `write()`, `read()`, `resolve_member`, `store.programs.pairs_of`, `ConsumedMode`, `project_names`, the `Deps` bundle, the CLI exit-code constants, the typed errors in `OPERATIONAL_ERRORS`, and 224's `since` handling inside `decisions`
  - [ ] Read the `releases` and `dependency_pairs` DDL in the baseline schema; confirm the columns `seq`, `member_id`, `commit_sha`, `version`, `changed`, `touched`, `reported_at`, `versioned_at` and `UNIQUE (member_id, commit_sha)`, and note how timestamps are stored (UTC text format) , how existing models and store writers in `store/` are laid out, and how JSON arrays and the time argument are handled there (222's convention); note any helper to reuse
  - [ ] Find the CLI contract document (search `docs/` and `project-documents/` for the doc that lists subcommands, flags and exit codes); note its path, or note "none exists"
  - [ ] Find how 226's stdio test states its literal tool count, and how 226's parity tests enumerate rows
  - [ ] Run the checks once and note the baseline; failures present before this slice are written down, not fixed
  - [ ] Success: a note lists each import path, the timestamp format, the stdio test location and the baseline result

## 1. Release store (D2, D3)

- [ ] **1.1 `Release` model and `store/releases.py` writers**
  - [ ] Add `Release` to `store/models.py` (frozen, matching the existing model style): `seq`, `commit`, `version`, `changed`, `touched` (tuple or list of str), `reported_at`, `versioned_at`; `version` and `versioned_at` optional
  - [ ] Create `store/releases.py` with `release_for_commit(tx, member_id, commit)` returning a `Release` or none, `insert_release(tx, member_id, commit, version, changed, touched, now)` and `add_version(tx, member_id, commit, version, changed, touched, now)`. `touched` is stored as a JSON array. `now` is an argument, never read inside
  - [ ] `insert_release` sets `versioned_at` to `now` only when `version` is given, else null. `add_version` sets `version`, `versioned_at` and replaces `changed` and `touched`; `reported_at` and `seq` do not change
  - [ ] Success: module imports; pyright strict clean

- [ ] **1.2 Writer tests**
  - [ ] Test: insert without a version stores null `version` and `versioned_at`; insert with a version stores both; `touched` round-trips as a list in order
  - [ ] Test: `add_version` on a versionless row sets the version and replaces `changed` and `touched` and leaves `reported_at` and `seq`; a second `add_version` with a different version on a versioned row does the same
  - [ ] Test: `release_for_commit` finds the row for the member and commit, returns none for another member's identical commit, and none for an unknown commit
  - [ ] Test: a duplicate `(member_id, commit_sha)` insert raises `sqlite3.IntegrityError` (not caught by the writer)
  - [ ] Success: tests pass; checks pass

- [ ] **1.3 `visible_releases` and tests (D3)**
  - [ ] Add `visible_releases(tx, provider_id, consumed, since)` to `store/releases.py`. Switch on `ConsumedMode`: `from_source` selects `reported_at >= since` ordered by `reported_at`, `seq`; `from_release` selects `version IS NOT NULL AND versioned_at >= since` ordered by `versioned_at`, `seq`. A `ConsumedMode` value not handled raises an explicit error (no default branch that picks one)
  - [ ] Test, rows seeded at chosen times through the writers: `from_source` sees a versionless row; `from_release` does not; after `add_version` `from_release` sees it
  - [ ] Test: `from_source` with `since` between `reported_at` and `versioned_at` sees nothing; with an earlier `since` sees one row carrying the version
  - [ ] Test: ordering for each mode with three rows seeded out of order; rows of another provider never appear
  - [ ] Success: tests pass; checks pass

**Commit**: `feat: add releases store writers and visibility query`

## 2. Time parsing and `report_release` (D1, D2, D5)

- [ ] **2.1 `operations/since.py` and `decisions` switch (224 D5)**
  - [ ] Create `operations/since.py` with `parse_since(value) -> str` converting an ISO-8601 string with an offset to the store's UTC text; a string with no offset, or unparseable, raises a `ValueError` subclass the callers turn into `malformed`. Reuse the timestamp format helper found in task 0.2
  - [ ] Replace the `since` logic in `operations/decisions.py` with `parse_since`; behavior and detail text unchanged
  - [ ] Test: offset forms (`+00:00`, `Z`, `-05:00`) convert to the same UTC instant; no offset and garbage are rejected
  - [ ] Success: 224's tests pass unchanged (no edit to them); pyright strict clean; tests pass

- [ ] **2.2 `ReportReleaseRequest` and `ReportReleaseResult` and tests (D1, D2)**
  - [ ] In `operations/report_release.py` add `ReportOutcome(StrEnum)` (`recorded`, `versioned`, `unchanged`, `rejected`), the problem-code `StrEnum` (`malformed`, `not_a_member`) if 222 to 224 have none to reuse, `ReportReleaseRequest` (frozen, `extra="forbid"`) and `ReportReleaseResult` (`outcome`, `member`, `report`, `problems`) per D1 and D2. Add a shared `ReleaseReport` result model (`seq`, `commit`, `version`, `changed`, `touched`, `reported_at`, `versioned_at`) that task 3.1 reuses
  - [ ] `commit`: stripped, lowercased, 40 or 64 hex characters; the rejection detail says `git rev-parse` gives a full hash. `version`: stripped, non-empty when given. `changed`: required, non-empty. `touched`: list of at least one non-empty string, deduplicated, order kept
  - [ ] Test: abbreviated hash, non-hex hash, empty `changed`, empty and missing `touched`, blank `version` and an unknown extra field are each rejected by the model; an upper-case hash is stored lowercased; duplicate `touched` items are removed in order
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **2.3 `report_release` operation and tests (D2)**
  - [ ] Implement `report_release(store, document, *, directory, deps)`: validate `document` into the request (failure: `rejected` / `malformed`, with the model's message as detail); `resolve_member(directory)` (failure: `rejected` / `not_a_member`, resolution as detail); all `cf` calls before the store is touched; take UTC now once; then one `BEGIN IMMEDIATE` write applying D2's three rows. `unchanged` writes nothing. The result always carries the stored report and the member's CF project id
  - [ ] Test, one per D2 row, asserting outcome and stored row: new commit is `recorded` (with and without a version); a different version on a versioned commit and a version on a versionless commit are each `versioned` with text replaced and `reported_at` unmoved; a repeat with rephrased text is `unchanged` and keeps the stored text; a repeat with the same version is `unchanged`; a versionless repeat on a versioned commit is `unchanged`
  - [ ] Test: the same commit reported by two different members yields two reports
  - [ ] Test (rejections write nothing): a malformed document and a non-member directory each return `rejected` with the right code and leave `releases` empty
  - [ ] Test: a `cf` failure raises the typed error and leaves `releases` empty
  - [ ] Success: module imports; pyright strict clean; tests pass

**Commit**: `feat: add report_release operation and shared since parsing`

## 3. `changes` (D3)

- [ ] **3.1 `changes` models, operation and tests**
  - [ ] In `operations/changes.py` add `ChangesOutcome(StrEnum)` (`listed`, `rejected`), `ChangesRequest` (frozen, `extra="forbid"`; `since` required, validated by `parse_since`), and result models per D3: `member` and each provider as `{id, name}`, `since` as the normalized UTC text, `pairs` of `{provider, consumed, releases}` using task 2.2's `ReleaseReport`, `problems`
  - [ ] Implement `changes(store, document, *, directory, deps)`: validate (`rejected` / `malformed`), `resolve_member` (`rejected` / `not_a_member`), then one read transaction reading the caller's provider pairs through `store.programs.pairs_of` and each pair's `visible_releases`. Names come from one `project_names` call. If, per task 0.2's note, it takes only the `cf` runner and returns all names, call it before the read transaction (all `cf` calls precede the store, per the design's Flow); if it needs the provider ids, call it once after the read transaction closes and note that here. Every pair is listed even with no releases. A provider id absent from Context Forge's list raises `ContextForgeError`. Nothing is written
  - [ ] Test: a missing `since`, an offset-less `since` and an unknown field are each rejected; a valid `since` is returned normalized to UTC
  - [ ] Test (one provider, a `from_source` and a `from_release` consumer, rows seeded at chosen times): the merge report reaches only `from_source`; after versioning, `from_release` sees it with the release text; a `from_source` `since` between report and tag sees nothing, an earlier one sees one entry with the version
  - [ ] Test: two `since` values each see everything after their own point; a pair with nothing visible is still listed with empty `releases`
  - [ ] Test: a provider's provider is never listed; a member with no providers gets `listed` with empty `pairs`
  - [ ] Test: a non-member directory returns `rejected` / `not_a_member`; a provider id missing from the `project_names` result raises `ContextForgeError`; a `cf` failure raises its typed error
  - [ ] Test: `changes` leaves the database unchanged (compare row counts and a table dump before and after)
  - [ ] Success: module imports; pyright strict clean; tests pass; checks pass

**Commit**: `feat: add changes operation for program dependencies`

## 4. Doors (D5)

- [ ] **4.1 Operation names and CLI subcommands and tests**
  - [ ] Add `REPORT_RELEASE = "report_release"` and `CHANGES = "changes"` to `OperationName`
  - [ ] Register the two subcommands in `cli/main.py` from `OperationName` (the way 226 task 1.1 did): `report_release --commit --version --changed --touched` (`--touched` repeatable, collected as a list) and `changes --since`. No flag is `required=True` in argparse; flags map one-to-one onto request fields, and absent flags are left out of the document so the operation rejects them with the same detail as MCP
  - [ ] Handlers follow the existing handler pattern: build the document, call the operation with `resolve_member`'s directory (the current working directory), print the result JSON, return exit `0` for any non-rejected outcome and `1` for `rejected`; `OPERATIONAL_ERRORS` map to `3`; usage errors stay `2`
  - [ ] Test: for each subcommand, a recording fake operation receives the expected document; a repeated `--touched` arrives as a list in order; an omitted flag is absent from the document
  - [ ] Test: exit `0` for a recorded or listed result, `1` for a rejected result, `3` for a raised `ContextForgeError`
  - [ ] Test: 226's name-parity test (`build_parser()` subcommands equal `OperationName`) passes with no edit
  - [ ] Success: pyright strict clean; the new CLI tests pass. Adding the names breaks 226's MCP parity tests until task 4.2 adds the rows, so run the full suite after 4.2, not here

- [ ] **4.2 MCP rows and stdio count and tests**
  - [ ] Add two `ToolSpec` rows to `mcp/tools.py`: `RunMode.IN_PROCESS`, `takes_directory = True`, one-line `call` adapters like the existing in-process rows, `request_model` set to `ReportReleaseRequest` and `ChangesRequest`. Descriptions are short and contain no example values
  - [ ] Change 226's stdio test so its literal tool count becomes one per `OperationName` member (the one edit to a 226 test)
  - [ ] Test: 226's parity tests (tool names, `takes_directory` set, schemas, only `handle_pause` detached) cover the new rows with no further edit, except the `takes_directory` set assertion if it lists names literally: update it to include the two new names and note that edit here
  - [ ] Test: for each new tool, a recording fake replaces the operation; the CLI handler and `run_in_process` given the same input reach it with equal documents and directories, and the returned dict equals the JSON the CLI prints
  - [ ] Test: `prepare_arguments` rejects a missing or relative `directory` for both new tools
  - [ ] Success: pyright strict clean; tests pass; the AST boundary test still passes (`amoeba.mcp` imports nothing from `store`, `config`, `upstream`, `answering`, `cli`); checks pass

**Commit**: `feat: expose report_release and changes on CLI and MCP`

## 5. Rule lines and contract docs (D6, D8)

- [ ] **5.1 `docs/program-rules.md`**
  - [ ] Create `docs/program-rules.md` with YAML frontmatter per `file-naming-conventions.md`. It has two blocks, each pasted whole, each saying where it goes: the consumer block (rules file of a member with providers) and the provider block (rules file of a member others depend on, and that repo's release skill after its tag step). Use D6's text exactly; a repo outside a program carries neither
  - [ ] Add a pointer to 222's `set_up` contract for choosing `consumed`, and D2's note that a release merges into a merge report only when the tag is on the reported commit; a release flow that adds its own commit makes a second report
  - [ ] No sample hash, time or version appears anywhere in the file
  - [ ] Success: the file exists and reads correctly; no credentials in it

- [ ] **5.2 Rule-lines test**
  - [ ] Test: the file has both blocks; each names its operation and flags exactly as `build_parser()` defines them (extract the flag names from the parser, not from a literal list); the consumer block contains both D4 git commands; neither block contains a 40-hex string
  - [ ] Parse the blocks leniently (by heading or marker, not exact whitespace) and include the real file as the fixture
  - [ ] Success: test passes

- [ ] **5.3 Contract docs (D8)**
  - [ ] `docs/store-contract.md`: `releases` is written only by `report_release`; `touched` is a JSON array; D2's identity and repeat rules; no read record is kept
  - [ ] The CLI contract at the path task 0.2 noted: add both subcommands, their flags, outcomes and exit codes. If 0.2 noted "none exists", put a short Commands section with the same content in `docs/program-rules.md` instead
  - [ ] `docs/mcp-server.md`: add the two tools to the tool list and say both take an absolute `directory`
  - [ ] Success: each doc matches the code (flag names, outcomes, codes); checks pass

## 6. Verification

- [ ] **6.1 Full checks**
  - [ ] Run `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest`; all pass
  - [ ] Confirm no migration was added and `EXPECTED_SCHEMA_VERSION` is unchanged (`git diff {target} -- src/amoeba/store` shows no schema or version edit)
  - [ ] Confirm the only edits to 224 and 226 tests are the stdio count (and the literal set noted in 4.2 if any)
  - [ ] Success: all pass; the diff confirms the two statements

- [ ] **6.2 Verification walkthrough (design steps 2 to 4)**
  - [ ] Run steps 2 to 4 of the design's Verification Walkthrough, with a scratch `AMOEBA_HOME` and 225's trading repos, `amoeba` installed from this branch as 225 D2 describes. Record each step's outcome under this task
  - [ ] A step that cannot run for a missing prerequisite is noted with the prerequisite, not marked done
  - [ ] Step 5 (real use) runs later, when a real provider merge and design happen; it is not part of this task file's completion. Leave a line under this task, `Step 5 pending: record in task notes after a real design run`, and note any design that skipped the `changes` call as evidence for `ecorkran/squadron#304`
  - [ ] Success: steps 2 to 4 are each recorded as passed or as blocked by a named prerequisite

**Commit**: `docs: add program rule lines, release contracts and walkthrough record`
