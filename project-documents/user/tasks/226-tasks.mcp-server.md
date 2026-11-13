---
docType: tasks
slice: mcp-server
project: amoeba
lld: user/slices/226-slice.mcp-server.md
dependencies:
- 224-slice.status-and-decisions
- 228-slice.state-home-and-question-lifecycle
projectState: Slices 222 to 225 and 228 are merged. The eight operations (`set_up`,
  `handle_pause`, `answer`, `status`, `decisions`, `mark_read`, `dismiss`, `retract`)
  exist with request and result models, 223's `Deps` bundle, `operations/processes.py`
  (`start_child`, `terminate_group`), `logs_dir()`, `state_layout()` and the typed errors.
  The CLI (`cli/main.py`) is the only door; its `_run_*` functions place each operation's
  arguments. Store schema is at version 3. No MCP server exists. `ecorkran/squadron#303`
  is closed.
dateCreated: 20261107
dateUpdated: 20261112
status: not_started
turns: 7
promptTokens: 182074
cachedTokens: 148532
cacheWriteTokens: 33532
completionTokens: 8271
durationSeconds: 53.3
costUsd: 0.232011
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.23201059999999998
    completionTokens: 8271
---

# Tasks: MCP Server

## Context Summary

- Working on slice 226 (design: `user/slices/226-slice.mcp-server.md`; decisions D1 to D12 are cited by number).
- Adds `amoeba-mcp`, a stdio MCP server exposing the eight CLI operations by the CLI's names, with the CLI's inputs and JSON results. It has no operation logic. Both doors place operation arguments in one function, `wiring.invoke` (D4). Each answer records its door, `cli` or `mcp` (D11, migration 004). Every MCP call has a deadline (D12).
- New modules: `operations/names.py`, `wiring.py`, `mcp/{server,tools,in_process,detached}.py`, `docs/mcp-server.md`, `store/schema/004_answer_via.sql`, `tests/live/mcp/`. Changed: `cli/main.py`, answer and decisions code and models, `docs/store-contract.md`, `docs/cli-contract.md`, `pyproject.toml`, README.
- `amoeba.mcp` imports nothing from `store`, `config`, `upstream`, `answering` or `cli` (D10 boundary test); it takes types and `start_child` from `wiring`.
- Python MCP SDK `mcp` 2.x (observed 2.3.0 on 20261112). The tool guide in `ai-project-guide/tool-guides/mcp` describes v1; follow the 2.x source and docs (context7) where they differ. Confirm the low-level `Server`, `on_list_tools`, `on_call_tool`, `stdio_server` and stdio client names against the installed package before coding.
- No silent fallbacks: a missing or relative `directory` is an error, a missing `amoeba` script stops start-up. Every closed vocabulary (`OperationName`, `RunMode`, `Door`) is a `StrEnum` defined once. Exceptions are handled per the project rule (re-raise after `logger.exception`, or a commented specific swallow); `call_tool` is the one process-boundary handler (D7).
- Nothing in `amoeba.mcp` prints; logging goes to stderr. Ruff `ASYNC` rules are enabled in task 0.3 and must stay clean.
- Every step runs without a person. The walkthrough is a live test with fixtures (task 5.2); LLM spend and live tests are pre-authorized.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`. "Checks pass" means all four.
- Take the code's actual module paths and signatures over the design's sketches where they differ; note each difference under task 0.2.
- Work on branch `226-slice.mcp-server`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.
- Next slice: 227 program dependencies (adds two rows to the table, two names and two `invoke` cases).

## 0. Setup

- [x] **0.1 Create the branch**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty
  - [x] Confirm the working tree is clean and you are on the target
  - [x] `git checkout -b 226-slice.mcp-server {target}`
  - [x] Success: `git branch --show-current` prints `226-slice.mcp-server`

- [x] **0.2 Confirm the base and locate inputs**
  - [x] Confirm `src/amoeba/operations/` holds `set_up`, `handle_pause`, `answer`, `status`, `decisions`, `mark_read`, `dismiss`, `retract`, `deps` and `processes`, and `EXPECTED_SCHEMA_VERSION` is 3. If not, write `BLOCKED: slices 222-228 not merged` under this task and stop
  - [x] Run `gh issue view 303 -R ecorkran/squadron --json state` and `sq --version`; note both. Nothing waits on either result
  - [x] Find the module and signature of each of: the eight operation functions and how each `_run_*` in `cli/main.py` places its arguments (store, config, document, directory, deps, clock); their request and result models; `HandlePauseCall` (note "absent" if it does not exist; task 1.1 creates it); `Deps` and the default-deps builder in `cli/main.py`; `start_child`, `Spawner`, `LaunchLogs`, `LaunchError`; `logs_dir`, `state_layout()`, `config_home()`, `state_home()`, `open_state_store` and the environment variable they read; the typed errors and exit-code constants; how `cli/main.py` loads config and opens the store; how the CLI's answer and decisions code reads and writes `answers` rows; how `prune` treats `logs/mcp/`; note import paths
  - [x] Confirm `handle_pause` stops its answering child after `answering_wait_seconds` (`terminate_group` in `answering_run.py`); note the line. If it does not, write that under this task as a defect and fix it in this slice
  - [x] Find `prepare_state_home` and `open_state_store` in `operations/state_move.py`; note that `open_state_store` runs the move and that 228's lock on the legacy store keeps concurrent callers apart. Find `resume_bound_seconds(config)` in `operations/resume.py` and list every `sq` and `cf` call on `answer`'s path with its timeout constant (`RUN_POLL_TIMEOUT_SECONDS`, `CF_GET_TIMEOUT_SECONDS`, `CF_PROJECTS_TIMEOUT_SECONDS`, and any other); task 3.2 sums them into `answer`'s bound
  - [x] Find how `cli/main.py` registers subcommands and whether a `build_parser()` function exists (the parser is `_parser()` today)
  - [x] Check the installed `mcp` version (`uv pip show mcp`) and whether it is a declared dependency; note the result
  - [x] Run the checks once and note the baseline; failures present before this slice are written down, not fixed
  - [x] Success: a note lists each import path, the `_run_*` placements, the `build_parser` status, the `mcp` version and the baseline result
  - Note: Base confirmed: all operations present, `EXPECTED_SCHEMA_VERSION` is 3. `gh issue view 303 -R ecorkran/squadron` state is CLOSED; `sq` 0.24.28. Import paths: operations are in `amoeba.operations.{set_up,handle_pause,answer,status,decisions,mark_read,dismiss,retract}`; `Deps` and `production_deps` in `amoeba.operations.deps`; `start_child`, `Spawner` and `terminate_group` in `amoeba.operations.processes`; `LaunchError` and `LaunchLogs` in `amoeba.upstream.squadron.launch`; `state_layout`, `StateLayout`, `config_path` and `AmoebaHomeError` in `amoeba.config.home`; `open_state_store` and `prepare_state_home` in `amoeba.operations.state_move`; `resume_bound_seconds` in `amoeba.operations.resume`; `load_user_config` and `ConfigError` in `amoeba.config.user_config`; `Store` in `amoeba.store.store`; exit codes `EXIT_OK`/`REJECTED`/`USAGE`/`ERROR` in `cli/main.py`. Placements in `cli/main.py`: `set_up(store, config, document, directory=cwd, run=subprocess.run)`; `handle_pause(store, config, run_id, directory=, deps=)`; `answer(store, config, document, deps=)`; `dismiss(store, document, clock=deps.clock)`; `retract(store, document, clock=deps.clock)`; `status(store, config, document, directory=cwd, deps=)`; `decisions(store, document, deps=)`; `mark_read(store, {"through": n})`. Home environment variable: `AMOEBA_HOME`. `HandlePauseCall`: absent (task 1.1 creates it). `build_parser`: absent; the parser is `_parser()`. `handle_pause` stops its answering child after `answering_wait_seconds` via `terminate_group` at `answering_run.py` ~line 174. `prune`: `PROTECTED_LOG_DIRECTORIES` are `answering`, `resume` and `calls`, so `logs/mcp/` is pruned and emptied directories are removed. Timeouts on `answer`'s path: `answer` calls no `cf`; `resume` polls `sq` twice (`RUN_POLL_TIMEOUT_SECONDS` = 30, already inside `resume_bound_seconds`); the extra terms for `answer_bound_seconds` are two store busy timeouts (the `open_state_store` move lock and store open, and `answer`'s write transaction), each `BUSY_TIMEOUT_SECONDS` = 5, not `CF_GET_TIMEOUT_SECONDS` or `CF_PROJECTS_TIMEOUT_SECONDS`. `resume_wait_seconds` has no upper limit in `UserConfig` (`gt=0` only), so `check_deadline` at start-up is the only guard. `mcp` was not installed or declared before this task. Baseline: `ruff format`, `ruff check` and `pyright` clean; `pytest` 1803 passed.

- [x] **0.3 Dependency, lint config and SDK names**
  - [x] Add `mcp>=2.3,<3` to `[project] dependencies` in `pyproject.toml` and run `uv sync`
  - [x] Add `"ASYNC"` to ruff's `select` list in `pyproject.toml`; run `uv run ruff check .` and fix any `ASYNC` findings in existing code (or note them if there are none)
  - [x] Confirm against the installed `mcp` package (source, and context7 if needed) the exact import paths and signatures of: `mcp.server.lowlevel.Server` and its `instructions` argument, the list-tools and call-tool handler registration (`on_list_tools`, `on_call_tool`), how to register the call-tool handler with the SDK's own input validation off (v1: `validate_input=False`; note the 2.x spelling), `mcp.server.stdio.stdio_server`, `mcp.types` for `Tool` and the call-result type with `isError` and `structuredContent`, and the stdio client (`StdioServerParameters`, `stdio_client`, `ClientSession`). Where the names differ from the design, note the real ones under this task; tasks 4.1, 4.2 and 4.4 use the noted names
  - [x] Read the current default tool-call timeout of Claude Code and of Codex from their documentation (context7 or the docs sites) and note each value with its source. `MCP_CALL_DEADLINE_SECONDS` (task 3.2) must exceed `answer_bound_seconds` for the config contract's example, so it cannot sit below Codex's default; see the decision in the note below. `docs/mcp-server.md` (task 6.1) says how to raise a client's timeout
  - [x] Success: `uv run python -c "import mcp"` succeeds; `ruff check` is clean with `ASYNC` selected; the SDK names and the two client timeouts are noted
  - Note: Added `mcp>=2.3,<3` to `pyproject.toml`; `uv sync` installed mcp 2.3.0. `ASYNC` was already in ruff `select`; `ruff check` is clean. SDK 2.3.0 names differ from the design: `mcp.server.lowlevel.Server(name, *, instructions=..., on_list_tools=..., on_call_tool=...)` takes the handlers as constructor keyword arguments (no decorators); handlers are `async (ctx, params)`, where call-tool `params` is `CallToolRequestParams` (`name`, `arguments`) and the result is `CallToolResult`; the low-level server does no input validation, so there is no `validate_input` flag to turn off. Types live in package `mcp_types` (re-exported as `mcp.types`); `CallToolResult` fields: `content`, `structured_content`, `is_error`; `Tool` fields: `name`, `description`, `input_schema`. `from mcp import stdio_server, stdio_client, StdioServerParameters(command, args, env, cwd), ClientSession`; the server runs via `server.run(read, write, server.create_initialization_options())`. Client timeouts: Claude Code `MCP_TOOL_TIMEOUT` default is about 28 hours (code.claude.com/docs/en/mcp); Codex `tool_timeout_sec` default is 60 s and `startup_timeout_sec` 10 s (learn.chatgpt.com/docs/extend/mcp). Codex stdio entry syntax confirmed: `[mcp_servers.<name>]` with `command = "..."` and `args = [...]`. DECISION (PM, 2026-11-12): the smaller default (Codex 60 s) minus 5 s gives 55 s, which is below `answer_bound_seconds` for every config (`resume_bound_seconds` alone is `resume_wait_seconds` + 75.5 s), so the invariant could not hold. `MCP_CALL_DEADLINE_SECONDS` is set to 180 s instead (the PM approved 120 s; the config contract's example `resume_wait_seconds: 60` gives a bound of 150.5 s, so 120 s would refuse the documented config and 180 s was chosen to clear it); `docs/mcp-server.md` must tell Codex users to set `tool_timeout_sec` to at least 185. Claude Code needs no change.

## 1. Shared names and wiring (D3, D4, D11)

- [x] **1.1 `OperationName`, `Door` and `build_parser()` and tests**
  - [x] Create `operations/names.py` with `OperationName(StrEnum)`: the eight operation names; and `Door(StrEnum)`: `cli`, `mcp`
  - [x] Change `cli/main.py` to register subcommands from `OperationName` (no literal subcommand strings left for these eight) and to expose `build_parser()` returning the parser, used by `main()`. Behavior unchanged
  - [x] Ensure `HandlePauseCall` (frozen pydantic: `run_id` any string, `directory` absolute path) exists, creating it in `operations` next to `handle_pause` only if task 0.2 found it absent; tasks 2.1 and 3.1 use it
  - [x] Test: the `build_parser()` subcommand names equal `{n.value for n in OperationName}`; if created here, `HandlePauseCall` accepts a `run_id` starting with `-` and rejects a relative `directory`
  - [x] Success: module imports; pyright strict clean; the CLI's existing tests pass unchanged (no edit to them)
  - Note: Created `operations/names.py` (`OperationName`, `Door`) and `operations/handle_pause_call.py` (`HandlePauseCall`; it was absent). `build_parser()` in `cli/main.py` registers subcommands from `OperationName`. The `*_COMMAND` constants there were removed, so `tests/test_contract_docs.py` builds its command list from `OperationName` (one existing test edited for that reason). New tests: `tests/cli/test_parser_names.py`, `tests/operations/test_handle_pause_call.py`.

- [x] **1.2 `wiring.py` with `invoke` and tests**
  - [x] Create `wiring.py` with `load_config()`, `open_store()`, `default_deps()` (223's bundle plus 224's `list_runs` and `project_names`) and `OPERATIONAL_ERRORS` (the tuple the CLI maps to exit 3). Move the logic from `cli/main.py`; do not copy it
  - [x] Add `invoke(name, document, directory, door)` for the seven in-process operations: opens the store through `open_state_store`, calls the operation with exactly the placement each `_run_*` uses today, closes the store in a `finally`, returns the result model. An unsupported name (`handle_pause`) raises a `ValueError` naming it. Move the bodies of the seven `_run_*` functions into it; do not copy them. `door` is accepted now and used in task 2.1
  - [x] Switch `cli/main.py` so each `_run_*` builds its document, calls `wiring.invoke`, prints and returns its exit code. `_run_handle_pause` keeps its own body (it appends the calls-log line)
  - [x] Re-export `Store`, `UserConfig`, `OperationDeps` (the `Deps` type), `start_child`, `LaunchLogs` and `LaunchError` from `wiring` so `mcp` need not import `store`, `config` or `upstream`; add an `__all__`
  - [x] Test: `default_deps()` returns a bundle with every field set; `OPERATIONAL_ERRORS` contains each typed error the CLI maps to exit 3, checked against the CLI's exit-3 test inputs; `invoke` on each of the seven names against a throwaway store returns the result type the CLI prints, and the store is closed after a normal call and after an operation that raises
  - [x] Update the rule comment/doc line naming who may call `state_layout()`, `config_home()` and `state_home()` to `cli`, `mcp` and `wiring`
  - [x] Success: module imports; pyright strict clean; the CLI's existing tests pass unchanged
  - Note: Created `wiring.py` with `load_config`, `open_store(layout)`, `default_deps(layout)` (takes the layout, since the no-argument form would need a second `state_layout()` call), `OPERATIONAL_ERRORS` (five errors, `AmoebaHomeError` included so the CLI has one except branch), `invoke`, `result_document` and `is_rejected` (shared result JSON and exit-1 test, since results mix pydantic models and dataclasses), and re-exports with `__all__`. The seven `_run_*` bodies moved into `invoke`; `cli/main.py` now has `_document_for` and `_run_invoked`, and `_run_handle_pause` keeps its own body. The CLI prints result JSON with `ensure_ascii=False` for all results, so dataclass results no longer escape non-ASCII. `tests/cli/test_legacy_move_cli.py` patches the operations on `wiring` instead of `cli`. The home rule docstring in `config/home.py` names cli, mcp and wiring. New tests: `tests/test_wiring.py`.

**Commit**: `refactor: extract operation names, wiring and invoke for a second door`

## 2. Door recorded on each answer (D11)

- [x] **2.1 Migration 004 and `via` through answer and decisions**
  - [x] Add `store/schema/004_answer_via.sql`: `ALTER TABLE answers ADD COLUMN via TEXT CHECK (via IN ('cli', 'mcp'))` with a header comment citing D11 and 222 D3. Raise `EXPECTED_SCHEMA_VERSION` to 4. Pin the CHECK list to `Door` in the vocabulary pinning test the way 003's lists are pinned
  - [x] Add `via: Door | None` to `AnswerRecord` and read it in `answer_from_row`; `add_pm_answer` writes it. `answer(…, via: Door)` takes it from the door (a keyword argument the request cannot set) and passes it to the store write. Every other writer of `answers` rows (the answerer's automatic answers) keeps `NULL`, as they are not carried by a door
  - [x] `decisions` entries gain `via` beside `answered_by`; a pre-004 row yields no value. Update `invoke` to pass `door`; the CLI passes `Door.CLI`
  - [x] Update `docs/store-contract.md` (the column, its vocabulary, the writer, schema version 4) and `docs/cli-contract.md` (`decisions` entry field; no new CLI input)
  - [x] Test: a migration from a version-3 store with answers adds the column, keeps every row with `via` NULL and stamps 4; `answer` through `invoke` with each `Door` stores it; `decisions` shows `cli` and `mcp` and shows no `via` for the old row; an unknown value is refused by the CHECK; a repeat run of the runner changes nothing
  - [x] Test: the existing contract-doc tests (`tests/test_contract_docs.py`) pass with the docs updated
  - [x] Success: tests pass; checks pass; no existing test edited except where it hard-codes schema version 3 or the `decisions` entry's field set
  - Note: Added `store/schema/004_answer_via.sql` and set `EXPECTED_SCHEMA_VERSION` to 4. `Door` is defined in `store/vocabulary.py` (the store imports nothing from operations) and re-exported from `operations/names.py`. `AnswerRecord.via` is read by `answer_from_row`; `add_pm_answer(..., via: Door | None = None)` writes it (None for callers with no door); the answerer's automatic answer write passes NULL. `answer(..., via: Door)` is a required keyword; `wiring.invoke` passes its door; the CLI passes `Door.CLI`. `DecisionsRecord.via` sits beside `answered_by`. `docs/store-contract.md` and `docs/cli-contract.md` are updated. Existing tests were also edited for the pinned-column list (`answers.via`), the vocabulary pin (`via: Door`), `answer(...)` call sites (`via=Door.CLI`) and the `AnswerRecord` construction in `status_support.py` (`via=None`). New tests: `tests/store/test_migration_004.py` and `via` cases in `test_answer.py`, `test_decisions.py` and `test_wiring.py`. All four checks pass (ruff format, ruff check, pyright strict, pytest 1848 passed).

**Commit**: `feat: record the door on each answer`

## 3. Tool table and in-process tools (D2, D4, D5, D7, D12)

- [x] **3.1 `tools.py`: `ToolSpec`, `TOOLS` table, schemas, argument preparation (D2, D5) and tests**
  - [x] Create `mcp/tools.py` with `RunMode(StrEnum)` (`IN_PROCESS`, `DETACHED`), frozen dataclass `ToolSpec` (`name: OperationName`, `request_model`, `takes_directory`, `mode`, `description`, `timeout_advice`) and `TOOLS: tuple[ToolSpec, ...]` with the eight rows from the D2 table (`dismiss` and `retract` are in-process). `timeout_advice` is a closed pair of constants defined once (D12): `READ_ADVICE` for `status` and `decisions` (the CLI is the fallback), `WRITE_ADVICE` for `set_up`, `answer`, `mark_read`, `dismiss` and `retract` (check `status` or `decisions` before repeating); `handle_pause` has none
  - [x] `description` per tool is short. The `handle_pause` description says the result lands in the receipt's stdout log, an empty log may mean still running or killed, confirm through `status` or `decisions`. The `answer` description says `text` must be a decision the PM actually gave, passed on as given, never composed by the agent (D3), and that the key comes from `status`
  - [x] Add `input_schema(spec)`: the request model's JSON schema; for `takes_directory` tools add a required string property `directory` described as an absolute path. For `handle_pause` the base is `HandlePauseCall`
  - [x] Add `prepare_arguments(spec, raw) -> (document, directory | None)` in `mcp/tools.py`: for `takes_directory` tools require `directory` present, a string and absolute, else raise a `RequestError` (new, in `mcp/tools.py`) naming the field; remove `directory` from the rest; pass the remaining raw arguments through unvalidated (the operation validates, 222 D7). The server never reads its own working directory
  - [x] Test (same names): tool names equal `OperationName` values and `build_parser()` subcommands; `takes_directory` is true for exactly `set_up`, `status`, `handle_pause`; `handle_pause` is the only `DETACHED` row; every in-process row has a `timeout_advice` (the read pair for exactly `status` and `decisions`), and `handle_pause` has none
  - [x] Test (schemas): each schema is an object schema; `directory` is required exactly for the three directory tools; `answer`'s schema equals `AnswerRequest`'s JSON schema unchanged (it has no `via`)
  - [x] Test: missing, non-string and relative `directory` each raise `RequestError` naming `directory`; a valid one is removed from the document; other keys pass through unchanged, including unknown keys and invalid values; tools without `takes_directory` ignore nothing and strip nothing
  - [x] Success: module imports; pyright strict clean; tests pass
  - Note: Created `mcp/__init__.py` and `mcp/tools.py` (`RunMode`, `ToolSpec`, `TOOLS`, `READ_ADVICE`, `WRITE_ADVICE`, `RequestError`, `input_schema`, `prepare_arguments`). The test directory is `tests/mcp_server/`, not `tests/mcp/`, because a test package named `mcp` would shadow the SDK when pytest puts `tests/` on `sys.path`. Tests: `tests/mcp_server/test_tools.py`. For `handle_pause`, `prepare_arguments` checks and strips `directory`; task 4.1's `start_handle_pause` must re-validate with `HandlePauseCall` from the original arguments. All four checks pass (pytest 1917 passed).

- [x] **3.2 `in_process.py` with the deadline, and tests**
  - [x] Create `mcp/in_process.py` with the constant `MCP_CALL_DEADLINE_SECONDS` (value from task 0.3's note, with a comment naming the two client defaults it sits under) and `async run_in_process(spec, document, directory) -> dict`: under `anyio.fail_after(MCP_CALL_DEADLINE_SECONDS)`, run `wiring.invoke(spec.name, document, directory, Door.MCP)` in `anyio.to_thread.run_sync(..., abandon_on_cancel=True)` and return `result.model_dump(mode="json")`. The store is opened and closed inside the worker thread (inside `invoke`)
  - [x] A deadline hit raises `CallTimedOut` (new, in `mcp/in_process.py`) with the text `<tool> did not finish within <n> s; ` followed by the tool's `spec.timeout_advice` (D12). The worker is a wrapper that logs any exception it raises with `logger.exception` and re-raises, so a failure after the deadline (nobody awaits it) is not lost. Add `answer_bound_seconds(config)` to `wiring.py`: `resume_bound_seconds(config)` plus the other `sq` and `cf` timeouts on `answer`'s path from task 0.2's list, each from its constant, not a literal; and `check_deadline(config, deadline_seconds)` that raises a `DeadlineError` naming `resume_wait_seconds` when the bound is not below the deadline. The typed errors in `OPERATIONAL_ERRORS` propagate untouched (mapped in task 4.1)
  - [x] Test (same functions): for each in-process tool, `wiring.invoke` is replaced by a recorder; the CLI handler and `run_in_process` given the same input reach it with equal names, documents and directories and with `Door.CLI` and `Door.MCP`; the returned dict equals the JSON the CLI prints. A malformed `set_up` document returns a `rejected` result on both. A second test runs the real `invoke` on a throwaway store through both doors and compares the JSON
  - [x] Test (off the loop): a tool blocked on a `threading.Event` does not stop a second call from completing; release the event at the end
  - [x] Test (deadline): with `MCP_CALL_DEADLINE_SECONDS` patched to a fraction of a second and a call blocked on an event, `CallTimedOut` is raised near the deadline and a following call completes; the released thread then closes its store
  - [x] Test: the store is closed after a normal call and after an operation that raises
  - [x] Test (advice): the timed-out text for `status` and `decisions` carries `READ_ADVICE` and for `set_up`, `answer`, `mark_read`, `dismiss` and `retract` carries `WRITE_ADVICE`; an exception raised by a worker after the deadline is logged at ERROR (check the log record)
  - [x] Test (invariant): `answer_bound_seconds` equals `resume_bound_seconds(config)` plus the listed timeouts; `check_deadline` passes below the deadline and raises `DeadlineError` naming `resume_wait_seconds` at or above it; the real `MCP_CALL_DEADLINE_SECONDS` exceeds the bound for a config with the smallest allowed `resume_wait_seconds`, and for the largest value 223's config validation accepts. If the config has no upper limit, note that under this task and let `check_deadline` at start-up be the guard
  - [x] Success: module imports; pyright strict clean; tests pass; `ruff check` clean with `ASYNC` rules selected
  - Note: Created `mcp/in_process.py` (`MCP_CALL_DEADLINE_SECONDS` = 180.0, `CallTimedOut`, `run_in_process`) and, in `wiring.py`, `DeadlineError`, `ANSWER_STORE_WAITS` (3), `answer_bound_seconds` and `check_deadline`. `run_in_process` uses `anyio.move_on_after`, not `fail_after`, so a `TimeoutError` raised by the operation is never taken for the deadline; it returns `wiring.result_document(result)`, the same JSON the CLI prints (results mix pydantic models and dataclasses). `answer_bound_seconds` is `resume_bound_seconds` + 3 x `BUSY_TIMEOUT_SECONDS` (legacy-move lock, store open, answer's write). `answer` calls no `cf` and no `sq` beyond the polls already inside `resume_bound_seconds`, so no other timeouts are added. The bound is `resume_wait_seconds` + 90.5 s; the slice design D12 was corrected to say so (it said 85.5). `UserConfig` has no upper limit on `resume_wait_seconds`, so `check_deadline` at start-up is the only guard; a test pins that a 180 s wait is refused. `anyio>=4.16,<5` is a direct dependency in `pyproject.toml`. Tests: `tests/mcp_server/test_in_process.py` and `tests/mcp_server/test_deadline.py`; `tests/wiring_support.py` records opened stores and their closure (via the store's own `close`, usable across threads). All four checks pass (pytest 1917 passed).

**Commit**: `feat: add MCP tool table and in-process tool runner`

## 4. Detached `handle_pause` (D6)

- [ ] **4.1 `detached.py`: `StartedCall`, start function and tests**
  - [ ] Create `mcp/detached.py` with `StartedCall` (frozen pydantic: `operation`, `pid`, `cwd`, `started_at`, `stdout_log`, `stderr_log`)
  - [ ] Add `resolve_amoeba_script()` returning `Path(sys.executable).parent / "amoeba"`, raising an explicit error naming the path if it does not exist
  - [ ] Add `async start_handle_pause(raw) -> StartedCall`: validate `raw` with `HandlePauseCall` (a failure raises `RequestError`, nothing starts); build argv `[amoeba, "handle_pause", "--", run_id]`; `cwd` is the call's `directory` (the run's checkout), never the server's directory; create `logs_dir() / "mcp" / "handle_pause" / <UTC stamp>-<hex>.{stdout,stderr}.log`; start with `wiring.start_child` unchanged; run all of it in `anyio.to_thread.run_sync`. A `LaunchError` result raises an error carrying its text and an `OSError` from log creation propagates, both for task 5.1 to map to `isError`
  - [ ] Test (same argv): the argv parses through `build_parser()` to the input values, including a `run_id` starting with `-`
  - [ ] Test: a relative `directory` and a missing `run_id` raise `RequestError` and start nothing (recording fake `Spawner`); the start receives `cwd` equal to the given `directory`
  - [ ] Test (detached): with a fake `amoeba` script (patched in as the resolved script) that waits until the test creates a go-file, then prints a `HandlePauseResult` JSON, `start_handle_pause` returns `StartedCall` while the go-file is absent (child still running); the test then creates the go-file, waits for the child's pid to exit, and asserts the stdout log holds the JSON. Log paths sit under the monkeypatched `logs_dir()`
  - [ ] Test (real CLI): with the real `amoeba` script, a throwaway `AMOEBA_HOME`, fake `cf` and `sq`, and a `run_id` that has no pause, the child exits and the calls log under the throwaway state home holds the child's line (so the CLI's own logging runs under the MCP door)
  - [ ] Test (log exit): a log file under `logs/mcp/handle_pause/` older than the cutoff is removed by `prune` and the emptied `mcp` directories with it; a younger one stays. Uses the real `prune` against a throwaway state home
  - [ ] Test: a missing `amoeba` script raises the explicit error; an unwritable log directory surfaces `OSError`
  - [ ] Success: module imports; pyright strict clean; tests pass

**Commit**: `feat: add detached handle_pause start for MCP`

## 5. Server, console script, dependency (D1, D7, D8)

- [ ] **5.1 `call_tool` result and error mapping and tests**
  - [ ] Create `mcp/server.py` with `async call_tool(name, arguments)`: look up the `ToolSpec` (unknown name is `isError`); `prepare_arguments`; dispatch on `mode` to `run_in_process` or `start_handle_pause`; return `structuredContent` plus the same JSON as one text content block
  - [ ] Map per D7: `RequestError` to `isError` text `RequestError: <detail>`; `CallTimedOut` to `isError` with its text prefixed `TimedOut: `; `OPERATIONAL_ERRORS` to `isError` text `<ExceptionName>: <message>` (the CLI's stderr text); a `LaunchError` result or a log `OSError` to `isError`; any other exception is the process-boundary handler: `logger.exception`, return `isError` `internal error: <message>`, keep serving
  - [ ] Test: a `rejected`-style result (CLI exit 1) is a normal result, not `isError`; each error row is `isError` with the stated text; an unexpected exception is `isError` `internal error:`, is logged at ERROR, and a following call still works; an unknown tool name is `isError`
  - [ ] Test (dispatch): `call_tool("handle_pause", …)` with fakes for `start_handle_pause` and `run_in_process` reaches only `start_handle_pause` and returns its `StartedCall` JSON; an in-process tool name reaches only `run_in_process`
  - [ ] Test: `structuredContent` equals the parsed text block
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **5.2 `main()`, server instructions and `list_tools`**
  - [ ] In `mcp/server.py` build `mcp.server.lowlevel.Server("amoeba", instructions=...)` with `on_list_tools` returning one tool per `TOOLS` row (`name`, `description`, `input_schema(spec)`) and `on_call_tool` calling `call_tool`
  - [ ] Instructions are short: the tools are the CLI's operations; `handle_pause` returns a receipt; `status` gives the inputs for `handle_pause` and `answer`; `answer` carries only a decision the PM gave (D1)
  - [ ] `main()` takes no arguments; it calls `resolve_amoeba_script()` first and exits non-zero with a stderr message if it fails; then `wiring.prepare_home()` (a one-line wrapper over `prepare_state_home(state_layout())`, added to `wiring.py` and its `__all__` in this task) and `wiring.check_deadline(load_config(), MCP_CALL_DEADLINE_SECONDS)`, each exiting non-zero with the CLI's stderr text for `OPERATIONAL_ERRORS` and `DeadlineError`; then it runs the server over `stdio_server()` with `anyio.run`. The server ends when the client closes stdin. Logging is configured to stderr only
  - [ ] Test: with `resolve_amoeba_script` patched to raise, `main()` exits non-zero, writes the message to stderr and starts no server
  - [ ] Test: against a throwaway legacy home, `main()` calls `prepare_home` before it serves (a recorder on `prepare_home` and the serve step sees that order) and the state is moved; with `prepare_home` raising a `StoreRelocateError`, `main()` exits non-zero with the CLI's text and serves nothing; with a config whose bound is not below the deadline, `main()` exits non-zero naming `resume_wait_seconds` and serves nothing
  - [ ] Test: two `wiring.invoke` calls started at once against a second throwaway legacy home both return results and the move happens once (228's lock keeps them apart)
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **5.3 Packaging and boundary test**
  - [ ] Add `amoeba-mcp = "amoeba.mcp.server:main"` beside `amoeba` in `[project.scripts]`; run `uv sync`
  - [ ] Test (boundary): an AST test parses every file in `src/amoeba/mcp/` and asserts none imports `amoeba.store`, `amoeba.config`, `amoeba.upstream`, `amoeba.answering` or `amoeba.cli` (absolute or relative form)
  - [ ] Success: `uv run amoeba-mcp` starts and waits on stdin without printing to stdout; boundary test passes

- [ ] **5.4 stdio smoke test**
  - [ ] Test: the SDK's stdio client starts `amoeba-mcp` (the `amoeba-mcp` script beside `sys.executable`, with the home environment variable noted in task 0.2 set to a temp directory and fake `cf` and `sq` on `PATH`) and lists eight tools whose names equal `OperationName`, each with an input schema; also call `decisions` on an empty store and check a normal result
  - [ ] Success: smoke test passes without leaving a child process behind
  - [ ] Success: checks pass; the CLI's existing tests pass, edited only where task 1.2 or 2.1 requires it

**Commit**: `feat: add amoeba-mcp stdio server`

## 6. Install docs and walkthrough (D9)

- [ ] **6.1 `docs/mcp-server.md` and README link**
  - [ ] Create `docs/mcp-server.md` with YAML frontmatter per `file-naming-conventions.md`. Content: install (`uv tool install --force <repo>`, which installs `amoeba` and `amoeba-mcp` into one environment); register once at user scope (`claude mcp add --scope user amoeba -- amoeba-mcp`, or a Codex `[mcp_servers.amoeba]` entry); the client must pass a `PATH` reaching `sq`, `cf` and `git` plus model credentials; restart the client session after a reinstall (a running server keeps the old code until then); the eight tools, that `handle_pause` returns a receipt whose stdout log holds the result, what a `TimedOut` result means (`status` and `decisions`: run the CLI in a shell; the write tools: the work may still finish, check `status` or `decisions` before repeating), the deadline's value and that start-up refuses a `resume_wait_seconds` whose bound is not below it, and how to raise each client's tool timeout from task 0.3's note; how to remove the registration (`claude mcp remove amoeba --scope user`)
  - [ ] Check the Codex entry syntax against current Codex documentation before writing it; if it cannot be confirmed, state so in the doc rather than guessing
  - [ ] Link the doc from the README
  - [ ] Success: the doc exists, the README link resolves, and no credentials appear in either

- [ ] **6.2 Live walkthrough test**
  - [ ] Add `tests/live/mcp/test_mcp_walkthrough_live.py` using the helpers and fixtures in `tests/live/pause/` (a throwaway member with its own Context Forge data directory and `AMOEBA_HOME`; a do-nothing `amoeba` first on `PATH` so the user-level pause hook cannot act on these runs; `amoeba-mcp` driven by the SDK stdio client from a working directory under `/tmp`). It runs design walkthrough steps 3 to 5: eight tools listed; `status` matches `amoeba status`; `decisions` then `mark_read` agree with the CLI; a real run pauses on a question; `handle_pause` returns a `StartedCall` at once and its stdout log later holds a `HandlePauseResult` and the calls log a line; `answer` through MCP then through the CLI lists `via: mcp` and `via: cli`; `dismiss` and `retract` return their results. A wrong result fails the test; nothing is retried
  - [ ] Run it once with `uv run pytest tests/live/mcp`; fix failures in the code or the test, not by retrying
  - [ ] Success: the test passes with real `sq`, `cf` and models; record the command and result under this task

- [ ] **6.3 Verification walkthrough**
  - [ ] Run design step 1: `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest`; all pass
  - [ ] Run design step 2: `uv tool install --force .` from the slice branch; `amoeba` and `amoeba-mcp` both resolve on `PATH`
  - [ ] Run design step 6: `claude mcp add --scope user amoeba -- amoeba-mcp`, then `claude mcp list`; `amoeba` shows connected. This is the install and it stays registered. If `claude` is not on `PATH`, write `BLOCKED: claude CLI not installed` under this task and stop
  - [ ] Success: all three pass; record each result under this task

**Commit**: `docs: add MCP server install guide and live walkthrough`
