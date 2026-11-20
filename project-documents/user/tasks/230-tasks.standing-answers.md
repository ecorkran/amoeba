---
docType: tasks
slice: standing-answers
project: amoeba
lld: user/slices/230-slice.standing-answers.md
dependencies:
- 222-slice.store-config-and-set-up
- 223-slice.pause-handling
- 226-slice.mcp-server
- 228-slice.state-home-and-question-lifecycle
- 229-slice.human-cli
projectState: Slices 220 to 229 and 240 to 244 are merged on main. Store schema version
  9 (migrations 001 to 009, checked 20261120). Answering runs are sent rules, plan,
  program, request and PM-answer passages; nothing reaches across repos except program
  passages. This slice adds migration 010 and is the first of scenario F (230 to 232).
dateCreated: 20261120
dateUpdated: 20261120
status: not_started
turns: 74
promptTokens: 6857404
cachedTokens: 6706866
cacheWriteTokens: 150414
completionTokens: 52748
durationSeconds: 514.3
costUsd: 3.600436
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 3.6004356000000004
    completionTokens: 52748
revision_number: 2
---

# Tasks: Standing Answers

## Context Summary

- Working on slice 230 (design: `user/slices/230-slice.standing-answers.md`; decisions D1 to D10 are cited by number). Effort 3/5. It delivers the `standing_answers` table, `standing` (give) and `withdraw` on the CLI and MCP, `list standing [--all]`, a `standing_answer` passage sent to every answering run in reach, the prompt text for that kind, withdrawal on `rm`, the contract docs and a live test. Next: 231 (pauses that are not agent questions), then 232 (promote and find rulings).
- Paths: a path without a prefix is under `src/amoeba/`; `tests/`, `docs/` and `project-documents/` paths are from the repo root, and `user/` means `project-documents/user/`.
- Built names (checked 20261120): `assemble` in `answering/passages.py`; `add_request_passage` in `answering/request_passage.py`; `gather`, `_read_store`, `_StoredFacts` in `operations/pause_context.py`; `apply_removal` in `operations/set_up_remove.py`; `ListSubject` and `list_view` in `operations/list_view.py`; `members_view` in `operations/list_registry.py`; `OperationName` in `operations/names.py`; `invoke` in `wiring.py`; `project_of` (`upstream/context_forge/project_of.py`), which `add --project` calls; `get_program` and `get_member` (active members only) in `store/programs.py`; `passage_refs` in `answering/launch.py`; the cited-passage kind in `operations/decisions.py`.
- Departures from the design's file table, by the "Small conflicts" rule (task 0.2 writes them into the design): `answering/passages.py` (390 lines), `wiring.py` (320), `mcp/tools.py` (262) and `operations/pause_context.py` (289) are at or near ~300 lines, so new logic goes in new modules and those files gain only a call, a field or a row: `answering/standing_passages.py` (like `request_passage.py`), `wiring_standing.py` (like `wiring_messages.py`), `mcp/standing_tools.py` (like `message_tools.py`), `operations/standing_sources.py`. Shared request and result models go in `operations/standing_models.py`.
- Departure on the directory: `standing` takes no working directory on either door. `project_of(reference=...)` runs `cf` with no working directory (`upstream/context_forge/project_of.py`), so `--member` resolves from anywhere, and the MCP tool stays out of the directory tools that `tests/mcp_server/test_tools.py` pins (`DIRECTORY_TOOLS`), which is unchanged.
- Departure on `decisions`: a stored `PassageRef` holds id, source, question id and date, not a kind (design State Management says "kind"; it is not stored). `decisions` today sets `kind` only for PM answers. Task 6.1 derives `standing_answer` from the `standing:` source prefix, defined once, so the walkthrough's `decisions -j` output holds. No stored format changes.
- Closed values are defined once: `StandingReach` and `MEMBER_REMOVED_REASON` (`store/vocabulary.py`), the `standing:` source prefix (`STANDING_SOURCE_PREFIX`, `answering/standing_passages.py`), the outcome and rejection enums (`operations/standing_models.py`), `PassageKind.STANDING_ANSWER`, `ListSubject.STANDING`, `OperationName.STANDING` and `.WITHDRAW`. No silent fallbacks; a swallowed exception names one type with a comment saying why.
- Import direction stays `cli/mcp → wiring → operations → store, upstream`; `answering` imports nothing from `store`; the store imports nothing from `operations`. SQL composes only from module constants and binds every value with `?` (checked in 9.2). No SQL string outside `store/sql.py` names `members` (`tests/store/test_members_queried_in_one_place.py`, unchanged).
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. "Checks pass" means all four, with no failure beyond the baseline noted in 0.1. The live tier is `uv run pytest tests/live/<dir>` (never part of a bare run; LLM spend is pre-authorized).
- Tests use the autouse `AMOEBA_HOME` fixture, the stub `cf` (`tests/cf_stub.py`, `tests/cf_fixtures.py`), `tests/store/seed.py`, `tests/user_configs.py`, a settable clock. Destructive SQL only against throwaway stores. No sample id or timestamp sits near a value an agent must fetch (hallucination-trap rule), including docs and tool descriptions.
- `tests/test_contract_docs.py` requires every new table, column, command, flag, result value and tool in the contract docs, so each task that adds one adds its doc entry then. Section 8 writes the prose sections.
- No existing test assertion changes except the ones a task names: schema pins and table counts in 1.2; the two pinned operation-name lists in `tests/cli/test_parser_names.py` in 4.2; a pinned list of `list` subjects in 4.5 if one exists; `KIND_SENTENCES` in 5.2; the `sources_too_large` detail text in 5.5 if pinned. If an existing test fails for a legitimate reason, fix the new code, not the test, and note any named edit under its task.
- Production state: sections 0 to 9 write no live store or config. The live migration is the Phase 7 hand-off at the end of this file.
- Work on branch `230-slice.standing-answers` (created in 0.1). Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.

## 0. Setup

- [ ] **0.1 Target, branch and baseline**
  - [ ] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty. `git checkout {target}`; the design and this file are committed there, and `git status --short --untracked-files=no` prints nothing (an untracked file left by another unit is not this slice's and is left alone)
  - [ ] Confirm the built names in the Context Summary exist and `EXPECTED_SCHEMA_VERSION` in `store/migrations.py` is 9 with `store/schema/001` to `009`. A name moved is recorded in a note, not blocked; a role with no built code at all is `BLOCKED: <what>` and stop
  - [ ] `git checkout -b 230-slice.standing-answers {target}`; if it exists, `git checkout 230-slice.standing-answers`
  - [ ] Run the checks once; list any failure present before this slice by test name, unfixed
  - [ ] Success: `git branch --show-current` prints `230-slice.standing-answers`; a note gives the target, the target commit and the baseline
- [ ] **0.2 Align the design**
  - [ ] Amend `user/slices/230-slice.standing-answers.md` on this branch: in Component Structure, the new modules and `operations/standing_models.py` from the Context Summary's departures (the old files gain only a call, a field or a row), and `operations/decisions.py`; in State Management, the passage record holds id, source, question id and date, and `decisions` derives `standing_answer` from the `standing:` source prefix; in Integration Points ("221/223 `assemble`"), `StandingAnswer` lives in `answering/standing_passages.py`; in D2, the MCP tool takes `text`, `program` and `member` and no `directory`, and the "needs a working directory" sentence becomes: `--member` is resolved through `cf` with no working directory; in Development Approach, the MCP tools come with the CLI commands, before the passages (an operation name needs both doors in one commit); in the Operator Walkthrough's "Too many or too long" bullet, the question already waiting exits by `answer`, `dismiss` or the run moving on, and `withdraw`, a raised cap or shorter rules change only later questions, because a `waiting_on_pm` row is skipped and never gathered again (`operations/pause_existing.py`)
  - [ ] Success: `grep -n "standing_passages.py\|wiring_standing.py\|standing_tools.py\|standing_sources.py" user/slices/230-slice.standing-answers.md` finds each; `grep -n "lives in \`answering/passages.py\`" user/slices/230-slice.standing-answers.md` finds nothing

**Commit**: `docs: align the 230 design with its task breakdown`

## 1. Migration 010 and the vocabulary (D1, D8)

- [ ] **1.1 Vocabulary, migration and model**
  - [ ] `store/vocabulary.py`: `StandingReach` (`all`, `program`, `member`) with a one-line comment each, and `MEMBER_REMOVED_REASON = "member_removed"` (the reason `rm` writes, D8)
  - [ ] `store/schema/010_standing_answers.sql`: the D1 table exactly, with a header comment: `CREATE TABLE` only, existing rows untouched; rows are never deleted (State Management). No index: the table grows only with the PM's rulings
  - [ ] `store/migrations.py`: `EXPECTED_SCHEMA_VERSION` becomes 10
  - [ ] `store/models.py`: frozen dataclass `StandingAnswerRow` with the table's fields (`reach` as `StandingReach`, times as `datetime`)
  - [ ] `docs/store-contract.md`: the table, each column and why it exists (D1), version 10. Prose on who writes it is 8.3
  - [ ] Success: pyright clean
- [ ] **1.2 Migration test**
  - [ ] `tests/store/test_migration_010.py`, modelled on `test_migration_009.py`: a version-9 store with rows in every table migrates to 10 with every existing row field-for-field equal, `standing_answers` present and empty, `foreign_key_check` empty. The `reach` `CHECK` list equals `StandingReach` (extend `tests/store/test_vocabulary_pinning.py`). Each table `CHECK` rejects one violating insert (blank text; reach `all` with a program; reach `program` with no program; reach `member` with no member; `withdrawn_at` without `withdraw_reason`) and accepts a valid row of each reach
  - [ ] Update only the existing pins this breaks (schema pins such as `tests/store/test_schema_holds_no_mirrored_state.py`, the table list in `tests/store/test_schema.py`, the table count in `tests/test_contract_docs.py`); name each in a note
  - [ ] Success: checks pass

**Commit**: `feat: add migration 010 and the standing_answers table`

## 2. `store/standing.py` (D1 to D5, D8)

- [ ] **2.1 Statements and functions**
  - [ ] `store/sql_standing.py`: one shared column list and the `withdrawn_at IS NULL` predicate as module constants, and the statements composed from them only. Every value binds with `?`
  - [ ] `store/standing.py`, every function taking a `Transaction` and `now` where it writes, reading no clock or config, and passing each `execute` a `sql_standing` constant and a parameter tuple:
    - [ ] `give_standing(transaction, text, reach, program_id, member_id, now) -> tuple[int, bool]`: when an active row has the same text, reach, program and member, returns its id and `False`; otherwise inserts and returns the new id and `True` (D2's safe repeat; the caller holds one write transaction for both)
    - [ ] `withdraw_standing(transaction, standing_id, reason, now) -> StandingWithdrawal`: a compare-and-set on `withdrawn_at IS NULL`; `StandingWithdrawal` is a small `StrEnum` defined in `store/standing.py`: `withdrawn`, `already_withdrawn`, `not_found` (the store's own words; the operation maps them)
    - [ ] `list_standing(transaction, *, include_withdrawn) -> tuple[StandingAnswerRow, ...]`: newest first by `given_at`, then id descending
    - [ ] `standing_reaching(transaction, project_id, program_id) -> tuple[StandingAnswerRow, ...]`: not withdrawn, and reach `all`, or `program` with `program_id`, or `member` with `project_id`; id order; both values bound, no read of `members` (D5)
    - [ ] `withdraw_member_standing(transaction, project_id, now) -> int`: withdraws active member-reach rows for that member with `MEMBER_REMOVED_REASON`, returns the count; program and `all` rows untouched (D8)
  - [ ] Success: pyright clean; `store/standing.py` imports nothing from `operations`
- [ ] **2.2 Store tests**
  - [ ] `tests/store/test_standing.py` (real throwaway store, clock passed in): give inserts; the same give again returns the same id and `False`; text differing by one character, or another reach, program or member, is a new row; a give after the matching row is withdrawn is a new row; withdraw sets both fields once and a second call is `already_withdrawn` with no change; an unknown id is `not_found`; `list_standing` order and the `include_withdrawn` filter; `standing_reaching` with rows of all three reaches across two programs and three members returns exactly the rows in reach, never a withdrawn one; `withdraw_member_standing` withdraws only that member's member-reach rows and returns their count
  - [ ] Success: checks pass; `tests/store/test_members_queried_in_one_place.py` passes unchanged

**Commit**: `feat: add the standing answers store`

## 3. The `standing` and `withdraw` operations (D2, D3, D10)

The operation names, dispatch, commands and tools are section 4: an `OperationName` member needs all of them in the same commit (the exhaustive match in `wiring.py`, `tests/cli/test_parser_names.py`, `tests/test_contract_docs.py`).

- [ ] **3.1 Models**
  - [ ] `operations/standing_models.py`: `StandingRequest` (`text: NonBlankText`, `program`, `member`, both optional; both set is a validation error naming the two fields); `StandingOutcome` (`given`, `unchanged`, `rejected`) and `StandingRejection` (`malformed`, `no_such_program`, `no_such_member`); `StandingResult` with D2's fields (`member` holds the member's project id); `WithdrawRequest` (`standing_id` positive integer, `reason: NonBlankText`); `WithdrawOutcome` (`withdrawn`, `unchanged`, `rejected`), `WithdrawRejection` (`no_such_standing_answer`, `malformed`); `WithdrawResult` with D3's fields. `NonBlankText` is imported from `operations/set_up_models.py`, not redefined. Follow the existing request and result model base classes (read `operations/message_models.py` first)
  - [ ] Success: pyright clean
- [ ] **3.2 `operations/standing.py`**
  - [ ] `standing(store, request, run, now) -> StandingResult`: no flag gives reach `all`; `--program` gives `program` after `get_program` finds it, else `rejected / no_such_program`; `--member` is resolved by calling `project_of(reference=..., run=run)` directly, not through `project_or_rejection` (which returns `add`'s result type): a `CfCallFailed` raises `ContextForgeError` (exit 3, nothing written), a `CFProjectNotFound` is mapped here to `rejected / no_such_member`, and the found project must be an active member by `get_member`, else `rejected / no_such_member`. `project_of` runs first, before `store.write()` opens, so no `cf` subprocess runs while the write lock is held; `get_program` or `get_member` and `give_standing` then run inside one `store.write()` transaction. A model validation error is `rejected / malformed` with its problems. It takes no directory (Context Summary)
  - [ ] Success: pyright clean
- [ ] **3.3 Tests for 3.2**
  - [ ] `tests/operations/test_standing.py`: each reach gives a row with the right fields; a repeat is `unchanged` with the same id and one row; an unknown program and an unknown or removed member are each rejected with nothing written; a cf failure raises `ContextForgeError` with nothing written; the stub `cf` records no working directory for the `--member` lookup; both flags together and blank text are `malformed`; a `standing` that commits and whose result is dropped, repeated, gives `unchanged` naming the one row (D10)
  - [ ] Success: checks pass
- [ ] **3.4 `operations/withdraw.py`**
  - [ ] `withdraw(store, request, now) -> WithdrawResult`: one write transaction; maps the store's three results to `withdrawn`, `unchanged`, `rejected / no_such_standing_answer`; a validation error is `rejected / malformed`
  - [ ] Success: pyright clean
- [ ] **3.5 Tests for 3.4**
  - [ ] `tests/operations/test_withdraw.py`: withdraws and records the reason; a second call is `unchanged` with no field changed; an unknown id is rejected; zero, negative and non-integer ids and a blank reason are `malformed`; a committed withdraw whose result is dropped, repeated, gives `unchanged` naming the row (D10)
  - [ ] Success: checks pass

**Commit**: `feat: add the standing and withdraw operations`

## 4. Names, both doors and the `standing` view (D2 to D4)

4.1 and 4.2 share the marker after 4.3: the new names need both doors before the suite passes.

- [ ] **4.1 Names, dispatch and CLI commands**
  - [ ] `operations/names.py`: `OperationName.STANDING = "standing"` and `WITHDRAW = "withdraw"`
  - [ ] `wiring_standing.py`: `place_standing(name, store, document, deps)` validates the document into the request model, calls the operation and returns the result, as `place_message` does. `wiring.py` gains one `case OperationName.STANDING | OperationName.WITHDRAW` arm calling it, and an import. Neither takes a directory
  - [ ] Parser: `amoeba standing --text TEXT [--program ID | --member NAME]` (mutually exclusive group) and `amoeba withdraw STANDING_ID --reason TEXT`, named by `OperationName.cli_name` as every command is. Exit 1 when `rejected`, else 0; exit 3 for a store or cf error, through the existing exit-code mapping. `cli/render/standing.py`, joined into `cli/render/dispatch.py`: text names the outcome, the id and the reach (`everything`, `program <id>` or `member <id>`); a rejection prints its code and problems; `-j` prints the result model
  - [ ] `docs/cli-contract.md`: both commands with every flag, the result tables from D2 and D3, and both names in the Names section
  - [ ] Success: pyright clean (the match in `wiring.py` stays exhaustive)
- [ ] **4.2 MCP tools**
  - [ ] `mcp/standing_tools.py`: in-process tool rows `standing` (`text`, `program`, `member`) and `withdraw` (`standing_id`, `reason`), with `takes_directory` false and the write timeout advice `answer` has, joined into `TOOLS` the way `message_tools.py`'s rows are, each calling `wiring.invoke` with no logic. Both descriptions carry the rule `answer`'s carries (`mcp/tools.py`): it takes only a ruling the PM actually gave, passed on as given, never one the agent composed (D2, D3). `mcp/server.py` `INSTRUCTIONS` gains one line: the PM gives a ruling for every later case with `standing`, and `withdraw` takes one back
  - [ ] `docs/mcp-server.md`: both tools and their arguments
  - [ ] Named test edits: in `tests/cli/test_parser_names.py`, add `"standing"` and `"withdraw"` to the set in `test_the_operation_names_are_the_ones_the_contract_lists`, and to `minimal` in `test_every_command_takes_json_after_its_name` (`["standing", "--text", "t"]`, `["withdraw", "1", "--reason", "x"]`). No other assertion changes
  - [ ] Success: pyright clean
- [ ] **4.3 Tests for 4.1 and 4.2**
  - [ ] `tests/cli/test_standing_cli.py`: `standing` with each reach prints the id and exits 0; a repeat prints `unchanged`; both flags is a usage error; an unknown program exits 1; `withdraw` exits 0, then `unchanged`, an unknown id exits 1; `-j` output parses and carries D2's and D3's fields; a `StoreError` raised from the operation (monkeypatched) exits 3, and a `ContextForgeError` from `--member` resolution exits 3, each with nothing written
  - [ ] `tests/mcp_server/test_tools.py` and `tests/mcp_server/test_in_process.py` (added functions): both tools are listed with their schemas and no `directory`; each description holds the PM-ruling rule; a `standing` call writes one row and a repeat is `unchanged`; a `withdraw` call withdraws. `tests/mcp_server/test_instructions.py`, `tests/cli/test_parser_names.py` (with 4.2's named edits) and `tests/test_contract_docs.py` pass
  - [ ] Success: checks pass

**Commit**: `feat: add standing and withdraw to the CLI and MCP`

- [ ] **4.4 The `standing` view of `list`**
  - [ ] `operations/list_view.py`: `ListSubject.STANDING`, dispatched to `standing_view(store, cf_run, include_withdrawn=request.all)` in `operations/list_registry.py`; it reads `list_standing` and names a member-reach row's member as `members_view` names a member. Each entry carries id, reach, program, member, member name, `given_at`, text, and with `--all` `withdrawn_at` and `withdraw_reason`. Not part of the default `list` (D4)
  - [ ] `cli/render/registry.py`: one block per entry, newest first: id, reach (`everything`, `program <id>`, `member <name>`), date, then the text; a withdrawn entry adds its date and reason; an empty view prints one line saying there are none
  - [ ] The MCP `list` tool's `view` argument accepts `standing` (from `ListSubject`, not a second literal)
  - [ ] Docs: the `standing` row in `docs/cli-contract.md`'s `list` section with its fields in order (the contract-doc test checks view fields in order), and the view in `docs/mcp-server.md`
  - [ ] Success: pyright clean
- [ ] **4.5 Tests for 4.4**
  - [ ] `tests/operations/test_list_standing.py`, `tests/cli/test_list_cli.py` and `tests/mcp_server/test_in_process.py` (added functions): active rows newest first; `--all` adds withdrawn rows with date and reason; the default `list` has no standing entries; member names come from the stub `cf`; `list` with `view: standing` returns the rows. If a test pins the list of `list` subjects, change only that assertion and name it in a note
  - [ ] Success: checks pass

**Commit**: `feat: add the standing view of list`

## 5. The passages and the prompts (D5, D6)

- [ ] **5.1 `PassageKind` and `answering/answering.yaml`**, in one task because `tests/answering/test_pipeline_yaml.py` ties every `PassageKind` to both prompts
  - [ ] `answering/passage_types.py`: `STANDING_ANSWER = "standing_answer"`, appended last, with a comment (a ruling the PM gave ahead of time, 230 D5)
  - [ ] `answering/answering.yaml`: both steps' kind sentence lists `standing_answer` last (`... program_members, request_result or standing_answer.`), and both gain the D6 sentence describing the kind. The check step gains the D6 condition: when a cited passage is a standing_answer, the question is the situation that passage describes. Nothing else changes
  - [ ] Success: pyright clean; the YAML loads
- [ ] **5.2 Prompt tests**
  - [ ] `tests/answering/test_pipeline_yaml.py`: update `KIND_SENTENCES` to the new text (the named edit); add tests that the answer step holds the D6 sentence and the check step holds the D6 condition. The existing enum-order test then ties the list to `PassageKind`
  - [ ] Success: checks pass

**Commit**: `feat: add the standing_answer kind to the answer and check prompts`

- [ ] **5.3 `answering/standing_passages.py`**
  - [ ] Frozen dataclass `StandingAnswer` (`standing_id: int`, `text: str`, `given_at: datetime`); `STANDING_SOURCE_PREFIX = "standing:"`; `standing_passage(answer) -> Passage` with kind `STANDING_ANSWER`, `source` `standing:<id>`, date `given_at`, and `question`, `slice_label`, `question_id`, `member` unset; `add_standing_passages(kept, answers) -> list[Passage]` appends them in id order, numbered after `kept` as `add_request_passage` numbers. Imports nothing from `store`
  - [ ] Success: pyright clean; `tests/test_import_boundaries.py` passes
- [ ] **5.4 `assemble` gains `standing_answers`**
  - [ ] `answering/passages.py`: keyword-only `standing_answers: Sequence[StandingAnswer]` after `program_sources`, required (no default, so every caller states it). After the request passage, call `add_standing_passages`. The size check counts everything before PM answers; when it is over `max_chars` the result is `sources_too_large` with a detail that gives both shares: the rules, plan, program and request passages' characters, the standing answers' characters, and the limit. The detail text is built by `too_large_detail(base_chars, standing_chars, max_chars) -> str`, added to `answering/standing_passages.py`; `passages.py` gains only the parameter, the `add_standing_passages` call, the second size reading and the call to `too_large_detail` in place of today's detail string. The docstring says standing answers are never trimmed
  - [ ] Every existing caller of `assemble` passes `standing_answers` (`()` in tests and callers that have none; the real one is 5.6). Find them with `grep -rn "assemble(" src tests` (it also matches `_assemble`, which is not a caller); pyright then names any one missed
  - [ ] Success: pyright clean
- [ ] **5.5 Passage tests**
  - [ ] `tests/answering/test_standing_passages.py`: the passage's fields; rendered output has `kind: standing_answer`, `source: standing:<id>`, a date and no `question:` or `slice:` line; numbering follows the kept passages
  - [ ] `tests/answering/test_passages.py` (added functions): order is rules, plan, program, request, standing answers by id, then PM answers; numbering is continuous; standing answers are never dropped while PM answers are trimmed after them; rules plus standing answers over the cap give `sources_too_large` whose detail holds both share figures and the limit; standing answers alone under the cap with no rules fit. If an existing test pins the old detail text, update only that assertion and name it in a note
  - [ ] Success: checks pass
- [ ] **5.6 `pause_context` reads the standing answers**
  - [ ] `operations/standing_sources.py`: `standing_answers_of(rows) -> tuple[StandingAnswer, ...]`, mapping each `StandingAnswerRow` to a `StandingAnswer`
  - [ ] `operations/pause_context.py` gains only: a `_StoredFacts.standing` field holding `standing_reaching(transaction, member.project_id, member.program_id)`, read in `_read_store`'s one read transaction after `pm_precedent`; and `standing_answers=standing_answers_of(stored.standing)` in the `assemble` call. `gather`'s signature is unchanged
  - [ ] Success: pyright clean
- [ ] **5.7 Tests for 5.6**
  - [ ] `tests/operations/test_pause_context_gather.py` (added functions), with real rows in a throwaway store: a member with no stored PM answers gets an `all` row; a `program` row of the member's program is sent and one of another program is not; a `member` row of another member is not sent; a withdrawn row is not sent; with no rows the passages are exactly as before; a spy wrapping `Store.read` counts exactly one entry per `gather`; rules that fit alone plus standing answers over `max_chars` give `sources_too_large` whose detail holds both shares
  - [ ] `tests/operations/test_handle_pause.py` (added functions), modelled on `test_a_context_failure_waits_with_its_reason_and_starts_nothing`: a question whose standing answers push it over the cap waits on the PM with reason `sources_too_large`, the detail holding both shares, and no answering run starts; a `StoreError` raised from `standing_reaching` (monkeypatched) propagates out of `handle_pause` with no question row written (D10)
  - [ ] Success: checks pass

**Commit**: `feat: send standing answers in reach to every answering run`

## 6. `decisions` and the authorize list (D7)

- [ ] **6.1 `decisions` names the kind**
  - [ ] `operations/decisions.py`: a cited passage whose `source` starts with `STANDING_SOURCE_PREFIX` gets `kind` `standing_answer`; PM answers keep `pm_answer`; others stay null. Update the `CitedPassage.kind` comment in `operations/decisions_models.py` and the `decisions` field description in `docs/cli-contract.md`
  - [ ] Success: pyright clean
- [ ] **6.2 Tests for 6.1 and D7**
  - [ ] `tests/operations/test_decisions.py` (added function): an answer citing a `standing:<id>` passage shows kind `standing_answer` and that source
  - [ ] `tests/operations/test_answering_settle.py` (added function), modelled on `test_an_item_barred_for_one_member_and_allowed_for_another_differs`: an answer citing a standing-answer passage that would authorize a barred item is declined as today (D7)
  - [ ] Success: checks pass

**Commit**: `feat: name standing answers in decisions`

## 7. Withdraw on `rm` (D8)

- [ ] **7.1 `apply_removal`**
  - [ ] `operations/set_up_remove.py`: when `remove_member` returns true, call `withdraw_member_standing(transaction, project_id, now)` in the same transaction, next to `cancel_member_requests`, with a comment citing 230 D8. `rm`'s result is unchanged
  - [ ] Success: pyright clean
- [ ] **7.2 Tests for 7.1**
  - [ ] `tests/operations/test_rm.py` (added functions): removing a member withdraws its member-reach rows with `member_removed` and leaves program and `all` rows and another member's rows active; a removal that fails (a member with open questions, as the existing rejection tests set up) withdraws nothing; registering the member again does not bring the rows back
  - [ ] Success: checks pass

**Commit**: `feat: withdraw a removed member's standing answers`

## 8. Documents

- [ ] **8.1 `docs/cli-contract.md`**: prose for `amoeba standing` and `amoeba withdraw` beyond the tables from 4.1: who calls them (an agent, for the PM), the safe repeat, no un-withdraw (giving it again is the undo), that withdrawing changes only later questions, and `rm`'s withdrawal
- [ ] **8.2 `docs/rules.md`**: a short section saying standing answers in reach are read too, never trimmed, and counted against `passages_max_chars`, and that `sources_too_large`'s detail gives both shares (D5)
- [ ] **8.3 `docs/store-contract.md`**: a "Standing answers and who writes them" section: give, withdraw, removal with `member_removed`, rows kept and why (State Management), and that the passage record keeps the `standing:<id>` source, not the text
- [ ] **8.4 Success**: `uv run pytest tests/test_contract_docs.py tests/test_program_rules_doc.py` passes; checks pass

**Commit**: `docs: document standing answers in the contracts and rules`

## 9. Live test and final verification

- [ ] **9.1 Fixture pipeline and live test**
  - [ ] `tests/live/pause/asks_fixture_version.yaml`, modelled on `asks_question.yaml`: one step that asks only "Should I bump the fixture version?" and stops. The fixture repo's rules say nothing about fixture versions, so only a standing answer settles it
  - [ ] `tests/live/pause/test_standing_answer_live.py`, using the pause harness and conftest: in a fixture member with no stored PM answers, give the walkthrough's standing answer (reach `all`), run the pipeline, and assert the question is answered, the run resumed, and `decisions -j` cites a `standing_answer` passage with source `standing:<id>`; then withdraw it, run again, and assert the question waits on the PM
  - [ ] Success: `uv run pytest tests/live/pause/test_standing_answer_live.py` passes
- [ ] **9.2 Final verification**
  - [ ] Run the design's Verification Walkthrough steps 1 to 5 under a throwaway `AMOEBA_HOME` (the live test may stand for steps 3 and 4; note which), all four checks, and `uv run pytest tests/live/pause`
  - [ ] Map each Success Criterion in the design to the test that proves it, in a note
  - [ ] `grep -rn "except Exception" src/amoeba/operations/standing.py src/amoeba/operations/withdraw.py src/amoeba/store/standing.py` finds nothing
  - [ ] Bound values: `grep -n 'f"' src/amoeba/store/standing.py` finds nothing; every f-string in `src/amoeba/store/sql_standing.py` interpolates only that module's constants; every `execute` call in `store/standing.py` passes its values as a parameter tuple. Note the result
  - [ ] Amend the design's Verification Walkthrough if a real output differs from what it says
  - [ ] Success: all checks pass; notes give the results and the criteria map

**Commit**: `test: add the standing answers live test and verify the slice`

### Phase 7 hand-off (not tasks; nothing here is checked off in this file)

Phase 6 is complete when sections 0 to 9 are checked. These items are done in Phase 7, after the code review passes and the slice is merged. The live store and config are designated for migrations by `CLAUDE.md`.

- The live store migrates to version 10 on first use after install. From the target checkout, run `uv run python scripts/update_live.py update`: it backs up the live store and config to `~/.local/state/amoeba/backups/<stamp>/`, installs the target, migrates through `amoeba list`, checks schema version, integrity, foreign keys, member count and the `amoeba-mcp` tool list (which now includes `standing` and `withdraw`), and restores the backup and reinstalls the previous commit itself if a check fails. `uv run python scripts/update_live.py restore` puts the newest backup back later. Paste its output into the slice notes, and restart the client sessions it lists.
- Slice plan bookkeeping: tick entry 11 in `user/architecture/220-slices.program-tool.md` and set the design's and this file's `status`.
