---
docType: tasks
slice: mcp-server
project: amoeba
lld: user/slices/226-slice.mcp-server.md
dependencies:
- 224-slice.status-and-decisions
projectState: Slices 222 to 224 are designed and tasked; this slice assumes they are
  merged. The six operations (`set_up`, `handle_pause`, `answer`, `status`, `decisions`,
  `mark_read`) exist with request and result models, 223's `Deps` bundle, `processes.spawn_detached`,
  `logs_dir()` and the typed errors. The CLI (`cli/main.py`) is the only door. No
  MCP server exists. Nobody has run Amoeba. `ecorkran/squadron#303` is inherited from
  224.
dateCreated: 20261107
dateUpdated: 20261108
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

- Working on slice 226 (design: `user/slices/226-slice.mcp-server.md`; decisions D1 to D10 are cited by number).
- Adds `amoeba-mcp`, a stdio MCP server exposing the six CLI operations by the CLI's names, with the CLI's inputs and JSON results. It has no operation logic.
- New modules: `operations/names.py`, `wiring.py`, `mcp/{server,tools,in_process,detached}.py`, `docs/mcp-server.md`. Changed: `cli/main.py` (uses `OperationName`, `wiring`, `build_parser()`), `pyproject.toml`, README.
- `amoeba.mcp` imports nothing from `store`, `config`, `upstream`, `answering` or `cli` (D10 boundary test); it takes types from `wiring`.
- Python MCP SDK `mcp` 2.x (observed 2.3.0 on 20261107). The tool guide in `ai-project-guide/tool-guides/mcp` describes v1; follow the 2.x source and docs (context7) where they differ. Confirm the low-level `Server`, `on_list_tools`, `on_call_tool`, `stdio_server` and stdio client names against the installed package before coding.
- No silent fallbacks: a missing or relative `directory` is an error, a missing `amoeba` script stops start-up. Every closed vocabulary (`OperationName`, `RunMode`) is a `StrEnum` defined once. Exceptions are handled per the project rule (re-raise after `logger.exception`, or a commented specific swallow); `call_tool` is the one process-boundary handler (D7).
- Nothing in `amoeba.mcp` prints; logging goes to stderr. Ruff `ASYNC` rules are enabled in task 0.3 and must stay clean.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`. "Checks pass" means all four.
- Take 222 to 224's actual module paths over the design's sketches where they differ.
- Work on branch `226-slice.mcp-server`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.
- Next slice: 227 program dependencies (adds two rows to the table and two names).

## 0. Setup

- [ ] **0.1 Create the branch**
  - [ ] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty
  - [ ] Confirm the working tree is clean and you are on the target
  - [ ] `git checkout -b 226-slice.mcp-server {target}`
  - [ ] Success: `git branch --show-current` prints `226-slice.mcp-server`

- [ ] **0.2 Confirm 222 to 224 and locate inputs**
  - [ ] Confirm `src/amoeba/operations/` holds `set_up`, `handle_pause`, `answer`, `status`, `decisions`, `mark_read` and `deps`; and that `amoeba status --help` runs. If not, write `BLOCKED: slices 222-224 not merged` under this task and stop
  - [ ] Find the module and signature of each of: the six operation functions, their request and result models (`SetUpRequest`, status request, `DecisionsRequest`, `MarkReadRequest`, `AnswerRequest`, `HandlePauseResult` and the result models), `HandlePauseCall` (note "absent" if it does not exist; task 1.1 creates it), `Deps`, the default-deps builder in `cli/main.py`, `spawn_detached`, `logs_dir`, `amoeba_home` and the environment variable it reads, the typed errors and exit-code constants, and how `cli/main.py` loads config and opens the store; note import paths
  - [ ] Find how `cli/main.py` registers subcommands and whether a `build_parser()` function exists
  - [ ] Check the installed `mcp` version (`uv pip show mcp`) and whether it is a declared dependency; note the result
  - [ ] Run the checks once and note the baseline; failures present before this slice are written down, not fixed
  - [ ] Success: a note lists each import path, the `build_parser` status, the `mcp` version and the baseline result

- [ ] **0.3 Dependency and lint config**
  - [ ] Add `mcp>=2.3,<3` to `[project] dependencies` in `pyproject.toml` and run `uv sync`
  - [ ] Add `"ASYNC"` to ruff's `select` list in `pyproject.toml`; run `uv run ruff check .` and fix any `ASYNC` findings in existing code (or note them if there are none)
  - [ ] Confirm against the installed `mcp` package (source, and context7 if needed) the exact import paths and signatures of: `mcp.server.lowlevel.Server` and its `instructions` argument, the list-tools and call-tool handler registration (`on_list_tools`, `on_call_tool`), `mcp.server.stdio.stdio_server`, `mcp.types` for `Tool` and the call-result type with `isError` and `structuredContent`, and the stdio client (`StdioServerParameters`, `stdio_client`, `ClientSession`). Where the names differ from the design, note the real ones under this task; tasks 4.1, 4.2 and 4.4 use the noted names
  - [ ] Success: `uv run python -c "import mcp"` succeeds; `ruff check` is clean with `ASYNC` selected; the SDK names are noted

## 1. Shared names and wiring (D3, D4)

- [ ] **1.1 `OperationName` and `build_parser()` and tests**
  - [ ] Create `operations/names.py` with `OperationName(StrEnum)`: `set_up`, `handle_pause`, `answer`, `status`, `decisions`, `mark_read`
  - [ ] Change `cli/main.py` to register subcommands from `OperationName` (no literal subcommand strings left for these six) and to expose `build_parser()` returning the parser, used by `main()`. Behavior unchanged
  - [ ] Ensure `HandlePauseCall` (frozen pydantic: `run_id` any string, `directory` absolute path) exists, creating it in `operations` next to `handle_pause` only if task 0.2 found it absent; tasks 2.1 and 3.1 use it
  - [ ] Test: the `build_parser()` subcommand names equal `{n.value for n in OperationName}`; if created here, `HandlePauseCall` accepts a `run_id` starting with `-` and rejects a relative `directory`
  - [ ] Success: module imports; pyright strict clean; the CLI's existing tests pass unchanged (no edit to them)

- [ ] **1.2 `wiring.py` and tests**
  - [ ] Create `wiring.py` with `load_config()`, `open_store()`, `default_deps()` (223's bundle plus 224's `list_runs` and `project_names`) and `OPERATIONAL_ERRORS` (the tuple the CLI maps to exit 3). Move the logic from `cli/main.py`; do not copy it
  - [ ] Re-export `Store`, `UserConfig`, `OperationDeps` (the `Deps` type) from `wiring` so `mcp` need not import `store` or `config`; add an `__all__`
  - [ ] Switch `cli/main.py` to `wiring`; no behavior change
  - [ ] Test: `default_deps()` returns a bundle with every field set; `OPERATIONAL_ERRORS` contains each typed error the CLI maps to exit 3, checked against the CLI's exit-3 test inputs
  - [ ] Update 222's rule comment/doc line naming who may call `amoeba_home()` to `cli`, `mcp` and `wiring`
  - [ ] Success: module imports; pyright strict clean; the CLI's existing tests pass unchanged

**Commit**: `refactor: extract operation names and wiring for second door`

## 2. Tool table and in-process tools (D2, D4, D5, D7)

- [ ] **2.1 `tools.py`: `ToolSpec`, `TOOLS` table, schemas, argument preparation (D2, D5) and tests**
  - [ ] Create `mcp/tools.py` with `RunMode(StrEnum)` (`IN_PROCESS`, `DETACHED`), frozen dataclass `ToolSpec` (`name: OperationName`, `request_model`, `takes_directory`, `mode`, `call` adapter or none for detached, `description`) and `TOOLS: tuple[ToolSpec, ...]` with the six rows from the D2 table
  - [ ] `description` per tool is short. The `handle_pause` description says the result lands in the receipt's stdout log, an empty log may mean still running or killed, confirm through `status` or `decisions`. The `answer` description says `text` must be a decision the PM actually gave, passed on as given, never composed by the agent (D3)
  - [ ] `call` adapters are one line each: place the arguments the operation takes (request document, `directory`, deps). They contain no validation and no logic
  - [ ] Add `input_schema(spec)`: the request model's JSON schema; for `takes_directory` tools add a required string property `directory` described as an absolute path. For `handle_pause` the base is `HandlePauseCall`
  - [ ] Add `prepare_arguments(spec, raw) -> (document, directory | None)` in `mcp/tools.py`: for `takes_directory` tools require `directory` present, a string and absolute, else raise a `RequestError` (new, in `mcp/tools.py`) naming the field; remove `directory` from the rest; pass the remaining raw arguments through unvalidated (the operation validates, 222 D7). The server never reads its own working directory
  - [ ] Test (same names): tool names equal `OperationName` values and `build_parser()` subcommands; `takes_directory` is true for exactly `set_up`, `status`, `handle_pause`; `handle_pause` is the only `DETACHED` row
  - [ ] Test (schemas): each schema is an object schema; `directory` is required exactly for the three directory tools; `answer`'s schema equals `AnswerRequest`'s JSON schema unchanged
  - [ ] Test: missing, non-string and relative `directory` each raise `RequestError` naming `directory`; a valid one is removed from the document; other keys pass through unchanged, including unknown keys and invalid values; tools without `takes_directory` ignore nothing and strip nothing
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **2.2 `in_process.py` and tests**
  - [ ] Create `mcp/in_process.py` with `async run_in_process(spec, document, directory) -> dict`: in `anyio.to_thread.run_sync`, call `wiring.load_config()` and `wiring.open_store()`, build deps, call the tool's `call` adapter, close the store in a `finally`, and return `result.model_dump(mode="json")`. The store is opened and closed inside the worker thread
  - [ ] Typed errors in `OPERATIONAL_ERRORS` propagate to the caller (mapped in task 4.1); nothing is caught here
  - [ ] Test (same functions): for each in-process tool, a recording fake replaces the operation; the CLI handler and `run_in_process` given the same input reach it with equal documents and directories, and the returned dict equals the JSON the CLI prints. A malformed `set_up` document returns a `rejected` result on both
  - [ ] Test (off the loop): a tool blocked on a `threading.Event` does not stop a second call from completing; release the event at the end
  - [ ] Test: the store is closed after a normal call and after an operation that raises
  - [ ] Success: module imports; pyright strict clean; tests pass; `ruff check` clean with `ASYNC` rules selected

**Commit**: `feat: add MCP tool table and in-process tool runner`

## 3. Detached `handle_pause` (D6)

- [ ] **3.1 `detached.py`: `StartedCall`, spawn function and tests**
  - [ ] Create `mcp/detached.py` with `StartedCall` (frozen pydantic: `operation`, `pid`, `cwd`, `started_at`, `stdout_log`, `stderr_log`)
  - [ ] Add `resolve_amoeba_script()` returning `Path(sys.executable).parent / "amoeba"`, raising an explicit error naming the path if it does not exist
  - [ ] Add `async start_handle_pause(raw) -> StartedCall`: validate `raw` with `HandlePauseCall` (a failure raises `RequestError`, nothing starts); build argv `[amoeba, "handle_pause", "--", run_id]`; `cwd` is the call's `directory` (the run's checkout), never the server's directory; create `logs_dir() / "mcp" / "handle_pause" / <UTC stamp>-<hex>.{stdout,stderr}.log`; start with 223's `spawn_detached` unchanged; run all of it in `anyio.to_thread.run_sync`. An `OSError` from spawn or log creation propagates for task 4.1 to map to `isError`
  - [ ] Test (same argv): the argv parses through `build_parser()` to the input values, including a `run_id` starting with `-`
  - [ ] Test: a relative `directory` and a missing `run_id` raise `RequestError` and spawn nothing (recording fake for `spawn_detached`); the spawn receives `cwd` equal to the given `directory`
  - [ ] Test (detached): with a fake `amoeba` script (patched in as the resolved script) that waits until the test creates a go-file, then prints a `HandlePauseResult` JSON, `start_handle_pause` returns `StartedCall` while the go-file is absent (child still running); the test then creates the go-file, waits for the child's pid to exit, and asserts the stdout log holds the JSON. Log paths sit under the monkeypatched `logs_dir()`
  - [ ] Test: a missing `amoeba` script raises the explicit error; an unwritable log directory surfaces `OSError`
  - [ ] Success: module imports; pyright strict clean; tests pass

**Commit**: `feat: add detached handle_pause start for MCP`

## 4. Server, console script, dependency (D1, D7, D8)

- [ ] **4.1 `call_tool` result and error mapping and tests**
  - [ ] Create `mcp/server.py` with `async call_tool(name, arguments)`: look up the `ToolSpec` (unknown name is `isError`); `prepare_arguments`; dispatch on `mode` to `run_in_process` or `start_handle_pause`; return `structuredContent` plus the same JSON as one text content block
  - [ ] Map per D7: `RequestError` to `isError` text `RequestError: <detail>`; `OPERATIONAL_ERRORS` to `isError` text `<ExceptionName>: <message>` (the CLI's stderr text); spawn or log `OSError` to `isError`; any other exception is the process-boundary handler: `logger.exception`, return `isError` `internal error: <message>`, keep serving
  - [ ] Test: a `rejected`-style result (CLI exit 1) is a normal result, not `isError`; each of the three error rows is `isError` with the stated text; an unexpected exception is `isError` `internal error:`, is logged at ERROR, and a following call still works; an unknown tool name is `isError`
  - [ ] Test (dispatch): `call_tool("handle_pause", …)` with fakes for `start_handle_pause` and `run_in_process` reaches only `start_handle_pause` and returns its `StartedCall` JSON; an in-process tool name reaches only `run_in_process`
  - [ ] Test: `structuredContent` equals the parsed text block
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **4.2 `main()`, server instructions and `list_tools`**
  - [ ] In `mcp/server.py` build `mcp.server.lowlevel.Server("amoeba", instructions=...)` with `on_list_tools` returning one tool per `TOOLS` row (`name`, `description`, `input_schema(spec)`) and `on_call_tool` calling `call_tool`
  - [ ] Instructions are short: the tools are the CLI's operations; `handle_pause` returns a receipt; `status` gives the inputs for `handle_pause` and `answer`; `answer` carries only a decision the PM gave (D1)
  - [ ] `main()` takes no arguments; it calls `resolve_amoeba_script()` first and exits non-zero with a stderr message if it fails, then runs the server over `stdio_server()` with `anyio.run`. Logging is configured to stderr only
  - [ ] Test: with `resolve_amoeba_script` patched to raise, `main()` exits non-zero, writes the message to stderr and starts no server
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **4.3 Packaging and boundary test**
  - [ ] Add `amoeba-mcp = "amoeba.mcp.server:main"` beside `amoeba` in `[project.scripts]`; run `uv sync`
  - [ ] Test (boundary): an AST test parses every file in `src/amoeba/mcp/` and asserts none imports `amoeba.store`, `amoeba.config`, `amoeba.upstream`, `amoeba.answering` or `amoeba.cli` (absolute or relative form)
  - [ ] Success: `uv run amoeba-mcp` starts and waits on stdin without printing to stdout; boundary test passes

- [ ] **4.4 stdio smoke test**
  - [ ] Test: the SDK's stdio client starts `amoeba-mcp` (the `amoeba-mcp` script beside `sys.executable`, with the home environment variable noted in task 0.2 set to a temp directory and fake `cf` and `sq` on `PATH`) and lists six tools whose names equal `OperationName`, each with an input schema; also call `decisions` on an empty store and check a normal result
  - [ ] Success: smoke test passes without leaving a child process behind
  - [ ] Success: checks pass; the CLI's existing tests pass unchanged

**Commit**: `feat: add amoeba-mcp stdio server`

## 5. Install docs and walkthrough (D9)

- [ ] **5.1 `docs/mcp-server.md` and README link**
  - [ ] Create `docs/mcp-server.md` with YAML frontmatter per `file-naming-conventions.md`. Content: install (`uv tool install --force <repo>`, which installs `amoeba` and `amoeba-mcp` into one environment); register once at user scope (`claude mcp add --scope user amoeba -- amoeba-mcp`, or a Codex `[mcp_servers.amoeba]` entry); the client must pass a `PATH` reaching `sq`, `cf` and `git` plus model credentials; restart the client session after a reinstall; the six tools and that `handle_pause` returns a receipt whose stdout log holds the result
  - [ ] Check the Codex entry syntax against current Codex documentation before writing it; if it cannot be confirmed, state so in the doc rather than guessing
  - [ ] Link the doc from the README
  - [ ] Success: the doc exists, the README link resolves, and no credentials appear in either

- [ ] **5.2 Verification walkthrough**
  - [ ] Run the design's step 1: `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest`; all pass
  - [ ] Run steps 2 to 4 of the design's Verification Walkthrough where a configured `config.yaml`, a registered program and (for step 4) a real paused question run with `#303` exist. Record each step's outcome under this task. A step that cannot run for a missing prerequisite is noted with the prerequisite, not marked done
  - [ ] Success: step 1 passes; steps 2 to 4 are each recorded as passed or as blocked by a named prerequisite

**Commit**: `docs: add MCP server install guide`
