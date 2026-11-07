---
docType: slice-design
slice: mcp-server
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 224-slice.status-and-decisions
interfaces:
- 227-slice.program-dependencies
dateCreated: 20261107
dateUpdated: 20261107
status: not_started
turns: 28
promptTokens: 2112583
cachedTokens: 2005371
cacheWriteTokens: 107156
completionTokens: 29672
durationSeconds: 313.5
costUsd: 1.852317
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 1.8523174999999998
    completionTokens: 29672
---

# Slice Design: MCP Server

## Overview

This slice puts an MCP server in front of the six operations the CLI has after 224: `set_up`, `handle_pause`, `answer`, `status`, `decisions` and `mark_read`. It uses the same names as the CLI and has no logic of its own. It completes scenario C: from any directory, an agent session can see what is waiting on the PM and what was decided, and can answer for the PM.

- **Short operations** (`set_up`, `status`, `decisions`, `mark_read`, `answer`) run in the server process, in a worker thread, so neither store calls nor `cf` and `sq` subprocesses block the async loop. They return the operation's own result model.
- **Long work** (`handle_pause`, which waits for a whole answering run) starts a detached `amoeba` CLI process and returns at once with a receipt. The receipt names the log files. The CLI's own result JSON lands in the stdout log, and the work shows in `status` and `decisions`.
- **One server command,** `amoeba-mcp`, speaks MCP over stdio. It is installed with the `amoeba` tool and registered once per agent client at user scope.

## Value

User value. The PM can ask any agent session, in any repo or none, what is waiting and what was decided, and can answer through it, with no need to `cd` into a member or remember CLI flags. An agent can also catch up a missed hook that `status` reports by calling `handle_pause` with the directory `status` gives. For 227, adding `report_release` and `changes` to MCP becomes one table row each.

## Technical Scope

**Included:**

- `src/amoeba/mcp/`: the stdio server, the tool table, input schemas, the in-process runner and the detached starter (D1 to D7).
- `operations/names.py`: operation names, defined once and used by both doors (D3).
- `src/amoeba/wiring.py`: opening the store, loading the config, building the `deps` bundle and the operational error tuple, moved out of `cli/main.py` so both doors share them (D4).
- The `amoeba-mcp` console script, the `mcp` dependency, `docs/mcp-server.md` with install instructions, and a README pointer (D8, D9).
- Parity, loop and stdio tests (D10).

**Excluded:**

- Any change to an operation's behavior, inputs or result models. If a gap shows up, it is fixed in the operation, not in the MCP layer.
- `report_release` and `changes`. These are 227, which adds them to both doors.
- MCP resources, prompts, notifications and the Streamable HTTP transport. The architecture pushes nothing, and the server is local.
- A tool for reading a detached call's result. The receipt gives the log paths, and the agent's own file tools read them (D6).

## Dependencies

### Prerequisites

- **Slices 222, 223 and 224 complete.** All six operations exist with request and result models and a CLI subcommand each. 225 is not required, and 226 builds and passes its tests without it. The call log (225 D4), the install line and reinstall guard (225 D2) and the walkthrough's config and registration (225 D1) come from 225's decisions, and none of them blocks the build.
- **Python MCP SDK `mcp` 2.x,** observed at 2.3.0 on PyPI on 20261107. In 2.x, v1's `FastMCP` is `mcp.server.mcpserver.MCPServer`, and the low-level server takes `on_list_tools` and `on_call_tool` handlers as constructor arguments. The tool guide in `ai-project-guide/tool-guides/mcp/` describes v1. The design follows the 2.3.0 source.
- **`ecorkran/squadron#303`** for the run directories that `status` gives to `handle_pause`. This is inherited from 224, not new.

### Interfaces Required

- **From 222:** `set_up(store, config, document, *, directory, run)`, `SetUpResult`, `Store.open`, `load_user_config`, the home helpers, and the typed errors (`ConfigError`, `AmoebaHomeError`, `ContextForgeError`, `StoreError`).
- **From 223:** `handle_pause(store, config, run_id, *, directory, deps)` and `answer(store, config, document, *, deps)` with `AnswerRequest`, the `deps` bundle, `processes.spawn_detached(argv, cwd, logs)`, `logs_dir()`, and `SquadronError`.
- **From 224:** `status(store, config, document, *, directory, deps)`, `decisions(store, document, *, deps)` and `mark_read(store, document)`, with their request and result models.
- **From the CLI:** a `build_parser()` function that returns the argparse parser, so tests can compare subcommands and parse the argv MCP builds (D10). If `cli/main.py` builds its parser inline, this slice extracts it.

## Architecture

### Component Structure

```
src/amoeba/
├── operations/
│   └── names.py         # OperationName (StrEnum) (D3)
├── wiring.py            # open_store(), load_config(), default_deps(), OPERATIONAL_ERRORS; re-exports Store, UserConfig, OperationDeps (D4)
├── mcp/
│   ├── server.py        # main(): low-level Server over stdio; list and call handlers (D1)
│   ├── tools.py         # TOOLS: one ToolSpec per operation (D2)
│   ├── schemas.py       # input schema from the request model (+ directory) (D5)
│   ├── in_process.py    # run a short operation in a worker thread (D4)
│   └── detached.py      # StartedCall; build argv, spawn the amoeba CLI detached (D6)
└── cli/main.py          # names from OperationName; wiring from wiring.py; build_parser()
```

Import direction: `cli` and `mcp` both import `operations` and `wiring`. `mcp` imports nothing from `store`, `config`, `upstream`, `answering` or `cli`. The types its adapters name (`Store`, `UserConfig` and the `deps` bundle type `OperationDeps`) come from `wiring`, which re-exports them as its public contract, so `mcp` is typed under pyright strict without importing those packages. `wiring` is the only module below the doors that calls the home helpers. `tests/test_import_boundaries.py` gains these rules, and 222's rule that only the doors call `amoeba_home()` now names `cli`, `mcp` and `wiring`.

### Data Flow

**A short call** (`status` shown):

1. The client sends `tools/call` with `name: status` and `arguments: {directory, program?}`.
2. `server.py` looks up the `ToolSpec`. An unknown name is a protocol error from the SDK.
3. `in_process.run(spec, arguments)` runs under `anyio.to_thread.run_sync`. In the worker thread it:
   - removes `directory` from the arguments, for tools that take one (D5)
   - loads the config, opens the store and builds `deps` through `wiring`
   - calls `status(store, config, arguments, directory=Path(directory), deps=deps)`
   - closes the store
4. The result model goes back as `structuredContent`, with the same JSON as a text block. An operational error goes back as `isError` with `<ExceptionName>: <message>`, the same text the CLI prints on stderr (D7).

**A long call** (`handle_pause` shown):

1. The client sends `tools/call` with `name: handle_pause` and `arguments: {run_id, directory}`, taken from a `status` run entry's `next`.
2. `detached.start(spec, arguments)` runs in a worker thread. It validates the arguments into the tool's input model (D6), builds the argv, and calls `spawn_detached(argv, cwd=directory, logs)`.
3. The tool returns a `StartedCall` at once. The child is the ordinary CLI: it handles the pause, writes its `HandlePauseResult` JSON to the stdout log, and exits. 225's call log records it if it writes no question row.
4. The agent reads the stdout log, or calls `status` or `decisions`, to see the outcome.

### State Management

The server holds no state between calls. Each in-process call loads the config and opens the store in its worker thread, then closes the store. So a config edit takes effect on the next call, and no SQLite connection is shared across threads. Concurrent calls each have their own connection, and SQLite's busy timeout handles them, as 222 D2 does for concurrent CLI processes. Detached calls write only their log files. Everything else is the operations' own state.

The server is a process that the agent client starts and stops with its session. That fits the architecture's "nothing to run": it exists only while a caller is connected, and Amoeba starts nothing on its own.

## Technical Decisions

### D1 — The low-level server over stdio
Status: decided

`mcp.server.lowlevel.Server("amoeba", version=<package version>, instructions=…)`, constructed with `on_list_tools` and `on_call_tool`, and served with `stdio_server()` and `Server.run`. `amoeba-mcp` takes no arguments.

- **Why the low-level server.** The operations validate their own input (222 D7, 223 D9, 224 D5). `MCPServer` builds each tool's schema from a function signature and validates arguments before the function runs. Malformed input would then fail in the SDK with a different error on MCP than on the CLI. The low-level server lets the published input schema be the operation's own request model while the raw arguments go to the operation unchanged. The server leaves `get_tool_input_schema` unset, which in 2.3.0 only drives Streamable HTTP header checks. A test pins that a malformed `set_up` over MCP returns the operation's `rejected / malformed` result (D10).
- **Rejected:** `MCPServer` with a `dict[str, Any]` parameter. That would pass input through but publish an empty schema, so agents would lose the request shape.
- **stdio only.** In 2.3.0, `stdio_server()` points fd 1 at stderr while it serves, so stray output from a handler or a child process can't corrupt the stream. Logging goes to stderr through `logging`. Nothing in `amoeba.mcp` calls `print`.
- **Instructions.** These are a short constant in `server.py`. They say that the tools are Amoeba's operations under the CLI's names, that `handle_pause` returns a receipt whose stdout log holds the result, that `status` gives the inputs for `handle_pause` and `answer`, and that `answer` carries only a decision the PM gave, never one the agent composed (D3). They include no example ids or paths.

### D2 — One tool table
Status: decided

`mcp/tools.py` defines `TOOLS: tuple[ToolSpec, ...]`, one row per operation. `ToolSpec` is a frozen dataclass:

| Field | Holds |
|---|---|
| `name` | `OperationName` member |
| `request_model` | the operation's request model, or `HandlePauseCall` for `handle_pause`, whose operation takes positional arguments (D6) |
| `takes_directory` | whether the CLI form reads the working directory |
| `mode` | `RunMode.IN_PROCESS` or `RunMode.DETACHED` |
| `call` | for in-process tools, an adapter from `(Store, UserConfig, document, directory, OperationDeps)` to the operation function, with the types imported from `wiring` |

| Tool | Mode | Input | Result |
|---|---|---|---|
| `set_up` | in-process | `SetUpRequest` + `directory` | `SetUpResult` |
| `status` | in-process | status request + `directory` | `StatusResult` |
| `decisions` | in-process | `DecisionsRequest` | `DecisionsResult` |
| `mark_read` | in-process | `MarkReadRequest` | `MarkReadResult` |
| `handle_pause` | detached | `HandlePauseCall` (`run_id`, `directory`) | `StartedCall` |
| `answer` | in-process | `AnswerRequest` | `AnswerResult` |

`answer` runs in-process. Its resume waits only up to `resume_wait_seconds` (223 D8), the worker thread keeps the loop free, and the `sq run --resume` it starts goes through `spawn_detached` in its own session, so the resumed run outlives the server. The architecture detaches only long work. So this departs from the plan entry's wording ("`answer` with a resume" detached), and in return the agent relaying a PM decision gets `no_such_question`, `rejected`, `refused` or `not_delivered` back from the call itself.

The `call` adapters are one line each. They place arguments, and nothing else. `list_tools` is built from this table, and `call_tool` dispatches through it. 227 adds two rows.

### D3 — Operation names defined once, descriptions in the tool table
Status: decided

`operations/names.py` defines `OperationName(StrEnum)` with the six names. `cli/main.py` registers its subcommands from it, and `mcp/tools.py` uses the same members as tool names. So a name is changed in one place. Argparse help stays as the CLI has it.

Tool descriptions are constants in `tools.py`. The `handle_pause` description adds one sentence: it returns a receipt, its result is in the receipt's stdout log once the process exits, and an empty log may mean the process is still running or was killed, so the outcome is confirmed through `status` or `decisions` rather than assumed. The `answer` description says that `text` must be a decision the PM actually gave in this conversation, passed on as given, and that the agent must never compose an answer or record its own judgment as the PM's. A recorded `pm` answer resumes a run and becomes precedent (223 D9), so `answered_by: pm` has to mean the PM decided.

### D4 — Shared wiring, and short calls off the loop
Status: decided

- **`wiring.py`** holds what both doors do before calling an operation: `load_config()` (from `config_path()`), `open_store()` (from `store_path()`), `default_deps()` (223's bundle plus 224's `list_runs` and `project_names`, with the real `cf` and `sq` runners and the home paths), and `OPERATIONAL_ERRORS`, the tuple of typed errors the CLI maps to exit 3. `cli/main.py` is changed to use it, with no behavior change, and its existing tests must pass unchanged.
- **Off the loop.** `call_tool` is `async`. Every in-process call, including the store open and `answer`'s resume wait, runs inside `anyio.to_thread.run_sync`. The operations are synchronous: they use `sqlite3` and run `cf` and `sq` subprocesses, so `status` can take seconds. The detached starter runs in a worker thread too, because opening the logs and spawning is blocking I/O. Nothing synchronous runs on the loop apart from the table lookup and building the result.
- **Per call.** The config is loaded, the store opened, and `deps` built on every call, inside the worker thread. The cost is small next to the subprocess calls, and it removes shared state between threads (python rules, Concurrency & Shared State).

### D5 — Schemas and the `directory` input
Status: decided

- **Input schema.** The schema is the request model's `model_json_schema()`. For tools with `takes_directory`, a `directory` property (string, an absolute path) is added and made required. This is done once, in `schemas.py`. The request models forbid extra keys, so `in_process.run` removes `directory` before passing the rest to the operation.
- **`directory` is required wherever the CLI reads the working directory** (`set_up`, `status`, `handle_pause`). An MCP session can start anywhere (architecture, decision 4), and the server's own working directory says nothing about the caller. So the server never reads its own working directory. The agent passes its own directory, and `status` then scopes exactly as it does on the CLI from that directory: that program inside a member, every program outside.
- **A relative or missing `directory`** is refused at the door as an `isError` result naming the field (D7). A relative path would otherwise resolve against the server's directory without anyone noticing. Whether the path exists is left to the operation (`set_up`, `status`) or to the spawn (`handle_pause`), which already report it.
- **Results.** The result is the operation's model as `model_dump(mode="json")`, so MCP returns exactly the JSON the CLI prints. No output schema is published, because no requirement or target client consumes one.

### D6 — Detached calls
Status: decided

- **What is started.** The `amoeba` console script from the server's own install: `Path(sys.executable).parent / "amoeba"`. This is the same code as the server, and its command line matches 225's `pgrep -f "amoeba handle_pause"` reinstall guard. If the script is missing, `amoeba-mcp` exits at start-up with an error naming the path, before it serves anything.
- **argv.**
  - `handle_pause`: `[amoeba, "handle_pause", "--", run_id]`, with `cwd` set to `directory`.
  - The `--` stops argparse from reading a value that starts with `-` as an option.
- **Validation at the door.** A detached child can't report a malformed request back to the caller, and argv can't be built from input of the wrong shape. So the starter validates the arguments with `HandlePauseCall` first. `handle_pause` takes positional arguments and has no request model, so `HandlePauseCall` exists only to build argv. Its `run_id` is any string, which is what the CLI's argparse positional accepts, and whether a run id is valid stays the operation's decision. Its `directory` carries D5's absolute-path check, the one door-specific rule. Input that fails is refused as `isError` with the pydantic errors, and no process starts.
- **Spawn.** `processes.spawn_detached` from 223, unchanged: own session, `stdin` from `/dev/null`, inherited environment, closed descriptors. The logs are `logs_dir() / "mcp" / <operation> / <UTC stamp>-<8 hex>.{stdout,stderr}.log`, and the directory names are constants in `detached.py`. A spawn error (a missing `directory`, for example) is returned as `isError` with the error text.
- **`StartedCall`**, a frozen pydantic model: `operation`, `pid`, `cwd`, `started_at` (UTC), `stdout_log` and `stderr_log`. When the process has exited, the stdout log holds the result JSON, or the stderr log holds `error: <ExceptionName>: <message>`. The receipt carries no exit code, because the call returns before there is one.
- **Environment.** The child inherits the server's environment, which is the agent client's. Every resume it or an in-process `answer` starts inherits it too (architecture, "The resume's environment"). `docs/mcp-server.md` says the client must pass `PATH` reaching `sq`, `cf` and `git`, and the model credentials. A test checks that `AMOEBA_HOME` reaches the child.

### D7 — Results and errors
Status: decided

The CLI's exit codes map onto MCP results:

| CLI | MCP |
|---|---|
| exit 0 or 1 (a result, including `rejected`) | result: `structuredContent` plus the same JSON as text, `isError: false` |
| exit 2 (input that can't form a call) | `isError: true`, text `RequestError: <detail>`. Only D5 and D6 door refusals produce this |
| exit 3 (`OPERATIONAL_ERRORS`) | `isError: true`, text `<ExceptionName>: <message>` |

A `rejected` outcome is a result, not an error. Its model carries `outcome` and `problems`, as the CLI's stdout does. `call_tool` is the process boundary's top-level handler. Any other exception is logged with `logger.exception` to stderr and returned as `isError` with `internal error: <ExceptionName>: <message>`. The server keeps serving. This is case (c) of the project's exception rule.

**Failure modes:**

| Case | Handling |
|---|---|
| Client cancels or disconnects mid-call | `anyio.to_thread.run_sync` keeps its default, which does not abandon the thread. The worker runs to the end, its write transaction commits or rolls back as one unit, the store closes in a `finally`, and the result is discarded. A `set_up` or `mark_read` therefore either lands whole or not at all |
| Slow or hung `cf` or `sq` | Each subprocess is bounded by the timeouts `default_deps` already carries for `run_cf`, `poll_run` and `list_runs`. A whole `status` call is bounded by 224 D1's sum. A timeout is that operation's typed error, returned as `isError`. The server accepts this bound and adds no cap of its own. A client that times out and retries leaves the earlier worker running until that bound, so repeated retries of a hanging `status` hold one thread and at most one subprocess each until they end |
| Client session ends (stdin EOF) | `Server.run` returns and `main` exits 0, after any in-flight worker finishes (at most the bound above). Detached children are in their own session (223's `spawn_detached`), so they finish their work and write their logs regardless |
| Log directory or log file can't be created | The `OSError` from creating `logs/mcp/<operation>/` or opening the logs is handled like a spawn error: `isError` with `OSError: <message>` naming the path, and no process starts |

### D8 — Packaging and the server command
Status: decided

- `pyproject.toml`: `mcp>=2.3,<3` in `dependencies`, and `[project.scripts] amoeba-mcp = "amoeba.mcp.server:main"` beside `amoeba`. The major version is pinned because 2.x already broke v1's API.
- `uv tool install --force <amoeba repo>` (225 D2) installs both scripts into one tool environment, so D6 finds `amoeba` next to the server's interpreter.
- `starlette` and `uvicorn` belong to the HTTP server that 221 deletes. Whether they are still listed is 221's concern, and this slice adds no HTTP dependency.

### D9 — Install instructions
Status: decided

`docs/mcp-server.md`, linked from the README:

- Install the tool (`uv tool install --force <amoeba repo>`), then register the server once at user scope so every session has it. Claude Code: `claude mcp add --scope user amoeba -- amoeba-mcp`. Codex: an `[mcp_servers.amoeba]` entry with `command = "amoeba-mcp"` in its `config.toml`.
- The environment the client must pass (D6), and how to check it: a `status` call that fails with `SquadronError` or `ContextForgeError` means `sq` or `cf` isn't reachable from the server.
- After a reinstall, restart the client session. A running server keeps its loaded code, although its detached calls already run the new `amoeba`.

### D10 — Tests
Status: decided

All in the default suite, using the fake `cf` and `sq` scripts and recordings from 222 to 224, and the autouse `AMOEBA_HOME` fixture.

- **Same names.** The CLI subcommands from `build_parser()` equal the MCP tool names, and both equal the set of `OperationName`.
- **Same functions.** For each in-process tool, `answer` included, the operation function is replaced at its module with a recording fake. The CLI and the MCP call handler are each called with the same input, and the test asserts that both reached the same function with equal documents and directories, and that the MCP `structuredContent` equals the CLI's stdout JSON.
- **Same argv.** The argv the `handle_pause` starter builds is parsed by `build_parser()` into the same subcommand and values as the input. This includes a `run_id` that starts with `-`, and an empty `run_id`, which both doors pass to `handle_pause` alike.
- **No logic in the layer.** An AST test checks that `amoeba.mcp` imports nothing from `amoeba.store`, `amoeba.config`, `amoeba.upstream`, `amoeba.answering` or `amoeba.cli`.
- **Raw input reaches the operation.** A malformed `set_up` over MCP returns `SetUpResult` `rejected / malformed`, the same as the CLI with the same document.
- **Off the loop.** An in-process tool whose operation blocks on a `threading.Event` does not stop a second call (`decisions`) from completing first. The event is then released.
- **Errors.** A missing config gives `isError` with `ConfigError: …`, matching the CLI's stderr text. A relative `directory` for `handle_pause` is refused with no process started (the spawner is a recording fake).
- **Detached end to end.** `handle_pause` over MCP, with the fake `sq` replaying an `agent_question` pause for an unregistered directory, returns a `StartedCall` before the child exits. The child's stdout log then holds `HandlePauseResult` `skipped` with the CLI's reason, and the child saw the test's `AMOEBA_HOME`.
- **stdio end to end.** The SDK's stdio client starts `amoeba-mcp` as a subprocess, lists six tools with their input schemas, calls `decisions` and `mark_read` on a seeded test store, and gets valid JSON-RPC throughout, with fake `cf` and `sq` writing noise to their stdout and stderr.

### Technology Choices

- `mcp` 2.x low-level `Server` with `stdio_server()` (D1). Its `anyio` dependency provides `anyio.to_thread.run_sync`.
- No other new package. The pydantic request models from 222 to 224 provide the input schemas.

### Patterns and Conventions

- Tool names come only from `OperationName`. Run modes and the log directory names are constants defined once.
- The MCP layer places arguments and maps results. Any rule about what an input means lives in the operation.
- Every module carries a docstring, and the ~300-line file and ~50-line function limits apply.

## Implementation Details

### API Contracts

**Server:** `amoeba-mcp`, stdio, no arguments. Six tools, as in D2.

**Tool inputs** are the request models from 222 to 224, with `directory` added where D5 says. The `handle_pause` input is `{run_id: string, directory: absolute path}`.

**Tool results** are the operation result models for in-process tools, and for `handle_pause`:

```json
{"operation": "handle_pause", "pid": 0, "cwd": "/abs/checkout",
 "started_at": "<UTC ISO-8601>",
 "stdout_log": "<AMOEBA_HOME>/logs/mcp/handle_pause/<stamp>-<hex>.stdout.log",
 "stderr_log": "<AMOEBA_HOME>/logs/mcp/handle_pause/<stamp>-<hex>.stderr.log"}
```

**Errors:** D7.

**Python (for 227):** add an `OperationName` member, a CLI subcommand, and a `ToolSpec` row. D10's parity tests then cover the new operation with no test changes.

## Integration Points

### Provides to Other Slices

- **227:** the tool table and parity tests. `report_release` and `changes` are added to both doors by adding names and rows, as in API Contracts.
- **225 and later use:** scenario C from any agent session. The detached `handle_pause` calls pass through 225's CLI call log.

### Consumes from Other Slices

- **222 to 224:** the operation functions, models, `deps` and errors, unchanged. If an operation needs an input the CLI supplies implicitly, other than the working directory, the gap is fixed in the operation, not worked around here.
- **224's `status`:** `next` gives `handle_pause`'s `run_id` and `directory`. Until #303 lands, `status` lists no run directories, so over MCP `handle_pause` can only be called with a directory the agent already knows. This is the same limit as on the CLI.
- **Squadron and Context Forge:** reached only through the operations. If they fail, the operation's typed errors come back as `isError` (D7).

## Success Criteria

### Functional Requirements

- Each of `set_up`, `status`, `decisions`, `mark_read` and `answer` over MCP returns the same JSON the CLI prints for the same input and directory, including `rejected` results.
- `handle_pause` over MCP returns a `StartedCall` before the child process exits. This is the one result that differs from the CLI's, as the architecture allows for long work. The child's stdout log holds the CLI's result. The work shows in `status` and `decisions`.
- Calls with a missing or relative `directory` are refused with a reason and start nothing.
- An operational error comes back as `isError` with the same `<ExceptionName>: <message>` text the CLI prints.

### Technical Requirements

- No operation logic in `amoeba.mcp`. D10's import, name, function and argv tests pass.
- No synchronous call runs on the event loop. D10's blocking test passes, and ruff's `ASYNC` rules are clean.
- The server never reads its own working directory, and never writes to stdout outside the protocol.
- Format, lint, typecheck (pyright strict) and the full default suite pass. The CLI's existing tests pass unchanged after the `wiring.py` and `names.py` extraction.
- `docs/mcp-server.md` exists and the README links it.

### Integration Requirements

- `uv tool install --force .` installs `amoeba` and `amoeba-mcp` together, and an agent client registered as in D9 lists the six tools.
- 227 can add an operation to both doors by adding a name, a subcommand and a table row.

### Verification Walkthrough

Draft. Steps 3 to 6 need a configured `~/.config/amoeba/config.yaml` and at least one registered program (225 D1 provides both). Step 5 needs a real paused question run, and Squadron with #303 for its directory to come from `status`.

1. **Checks.**
   ```bash
   uv run ruff format --check . && uv run ruff check . && uv run pyright
   uv run pytest tests/mcp tests/test_import_boundaries.py
   uv run pytest
   ```
   All pass.

2. **Install and register.**
   ```bash
   uv tool install --force .
   command -v amoeba amoeba-mcp            # both in the same tool bin directory
   claude mcp add --scope user amoeba -- amoeba-mcp
   claude mcp list                          # amoeba listed as connected
   ```

3. **Status from outside any member.** Start a Claude Code session in a directory that is in no program (for example `/tmp`) and ask: "Use amoeba's status tool for this directory." The tool call carries `directory: /tmp`. In a terminal in the same directory, run `amoeba status`. The two JSON documents match, and both cover every program.

4. **Decisions and mark_read.** In the session, ask for `decisions`, then for `mark_read` through the `read_through` it returned. In a terminal, `amoeba decisions` now lists nothing newer than the marker. A second `mark_read` with the same value returns `unchanged`.

5. **A long call.** With a paused question run listed by `status` with a `handle_pause` `next`, ask the agent to call `handle_pause` with that `run_id` and `directory`. The call returns a `StartedCall` at once. `cat` its `stdout_log` once the process has exited: it holds a `HandlePauseResult`. `amoeba status` shows the run resumed, or its question waiting on the PM with the reason. For a waiting question, ask the agent to `answer` it with the PM's text. The call returns `AnswerResult` with its resume outcome, and `amoeba decisions` lists the PM answer.

6. **Errors and refusals.** Ask for `status` with a relative directory: refused with a `RequestError` naming `directory`. Temporarily rename `config.yaml` and ask for `status`: `isError` with `ConfigError: …`, the same message `amoeba status` prints on stderr. Restore the file.

## Implementation Notes

### Development Approach

Relative effort: 2.

1. `operations/names.py` and `wiring.py`, then switch `cli/main.py` to them and extract `build_parser()`. The CLI tests pass unchanged. Commit.
2. `mcp/schemas.py`, `mcp/tools.py` and `mcp/in_process.py`, with the name, function, raw-input, error and blocking tests.
3. `mcp/detached.py` and `StartedCall` for `handle_pause`, with the argv, refusal and detached end-to-end tests.
4. `mcp/server.py`, the console script and the dependency, with the stdio end-to-end test and the import-boundary rules. Commit.
5. `docs/mcp-server.md` and the README link. Run the walkthrough steps that the environment allows. Commit.

### Special Considerations

- **Security.** The server is local stdio, started by the PM's own agent client, with no network listener. It can do nothing the CLI can't. `answer` lets an agent record a PM answer, which can authorize anything (223 D9). That is scenario C's intent. The agent acts for the PM, and every answer shows in `decisions` with `answered_by: pm`.
- **Concurrency.** Simultaneous tool calls run in separate worker threads, each with its own store connection. Two detached `handle_pause` calls on one pause are decided by the question key's uniqueness, exactly as with two CLI calls (223 D4).
- **Log growth.** `logs/mcp/` is never pruned, like 223's other logs. Pruning waits until use shows the need.
