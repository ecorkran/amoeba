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
---

# Slice Design: MCP Server

## Overview

An MCP server, `amoeba-mcp`, in front of the six operations the CLI has after 224: `set_up`, `handle_pause`, `answer`, `status`, `decisions` and `mark_read`. It uses the CLI's names, passes input through unchanged, and returns the operations' own results. It has no logic of its own. It completes scenario C: from any directory, an agent session can see what waits on the PM and what was decided, and can answer for the PM.

**Value:** the PM can ask any agent session, in any repo or none, what is waiting and answer through it, with no `cd` and no CLI flags.

**Excluded:** changes to any operation (a gap is fixed in the operation, not here); `report_release` and `changes` (227); MCP resources, prompts, notifications and HTTP transport; a tool for reading a detached call's result (the agent reads the log files).

## Dependencies

- **222, 223, 224 complete:** all six operations with request and result models, 223's `deps` bundle, `processes.spawn_detached` and `logs_dir()`, and the typed errors. 225 is not required.
- **Python MCP SDK `mcp` 2.x,** observed at 2.3.0 on 20261107. The tool guide describes v1; the design follows the 2.x source.
- **`ecorkran/squadron#303`,** inherited from 224: run directories in `status` for `handle_pause`.

## Architecture

```
src/amoeba/
├── operations/names.py  # OperationName (StrEnum) (D3)
├── wiring.py            # load_config, open_store, default_deps, OPERATIONAL_ERRORS; re-exports Store, UserConfig, OperationDeps (D4)
├── mcp/
│   ├── server.py        # main(): low-level Server over stdio (D1, D7)
│   ├── tools.py         # TOOLS table, input schemas (D2, D5)
│   ├── in_process.py    # run a tool in a worker thread (D4)
│   └── detached.py      # StartedCall; spawn the amoeba CLI detached (D6)
└── cli/main.py          # uses OperationName, wiring, build_parser()
```

`cli` and `mcp` both import `operations` and `wiring`. `mcp` imports nothing from `store`, `config`, `upstream`, `answering` or `cli`; it gets the types it names from `wiring`. 222's rule that only the doors call `amoeba_home()` now names `cli`, `mcp` and `wiring`.

The server holds no state. Each call loads the config, opens the store in its worker thread and closes it, so no SQLite connection is shared across threads. The agent client starts and stops the server with its session, which fits "nothing to run".

## Technical Decisions

### D1 — Low-level server over stdio
`mcp.server.lowlevel.Server("amoeba", …)` with `on_list_tools` and `on_call_tool`, served with `stdio_server()`. `amoeba-mcp` takes no arguments. The low-level server is used so the published input schema is the operation's own request model while raw arguments reach the operation unvalidated: the operations validate their own input (222 D7), so malformed input gets the same result on both doors. Logging goes to stderr; nothing in `amoeba.mcp` prints. Short server instructions say the tools are the CLI's operations, `handle_pause` returns a receipt, `status` gives the inputs for `handle_pause` and `answer`, and `answer` carries only a decision the PM gave (D3).

### D2 — One tool table
`TOOLS: tuple[ToolSpec, ...]`. `ToolSpec` (frozen dataclass): `name` (`OperationName`), `request_model`, `takes_directory`, `mode` (`RunMode.IN_PROCESS` or `RunMode.DETACHED`), and for in-process tools a one-line `call` adapter that places arguments.

| Tool | Mode | Input | Result |
|---|---|---|---|
| `set_up` | in-process | `SetUpRequest` + `directory` | `SetUpResult` |
| `status` | in-process | status request + `directory` | `StatusResult` |
| `decisions` | in-process | `DecisionsRequest` | `DecisionsResult` |
| `mark_read` | in-process | `MarkReadRequest` | `MarkReadResult` |
| `answer` | in-process | `AnswerRequest` | `AnswerResult` |
| `handle_pause` | detached | `HandlePauseCall` (`run_id`, `directory`) | `StartedCall` |

`answer` runs in-process in a worker thread, not detached as the plan entry's wording has it. Its resume waits only `resume_wait_seconds` (223 D8) and spawns `sq run --resume` detached in its own session, so it is not long work, and the agent relaying a PM decision gets `no_such_question`, `rejected`, `refused` or `not_delivered` back directly. Only `handle_pause`, which waits for a whole answering run, is detached. 227 adds two rows.

### D3 — Names once, descriptions in the table
`OperationName(StrEnum)` in `operations/names.py`; the CLI registers subcommands from it and the table uses it for tool names. The `handle_pause` description says the result lands in the receipt's stdout log and an empty log may mean still running or killed, so confirm through `status` or `decisions`. The `answer` description says `text` must be a decision the PM actually gave, passed on as given, never one the agent composed, since a `pm` answer becomes precedent (223 D9).

### D4 — Shared wiring; store calls off the loop
`wiring.py` holds what both doors do before calling an operation: `load_config()`, `open_store()`, `default_deps()` (223's bundle plus 224's `list_runs` and `project_names`) and `OPERATIONAL_ERRORS`. `cli/main.py` moves to it with no behavior change. `call_tool` is async; every in-process call, store open included, and the detached spawn run in `anyio.to_thread.run_sync`. Nothing synchronous runs on the loop but the table lookup and result building.

### D5 — `directory` input and results
- For tools with `takes_directory` (`set_up`, `status`, `handle_pause`), the schema is the request model's JSON schema plus a required `directory` (absolute path). `directory` is removed before the rest is passed to the operation.
- The server never reads its own working directory; an MCP session can start anywhere. A missing or relative `directory` is refused as `isError` naming the field, and nothing runs.
- Results are `model_dump(mode="json")`: exactly the JSON the CLI prints. No output schema.

### D6 — Detached `handle_pause`
- Starts the `amoeba` script beside the server's interpreter (`Path(sys.executable).parent / "amoeba"`); `amoeba-mcp` exits at start-up if it is missing. argv: `[amoeba, "handle_pause", "--", run_id]`.
- **`cwd` is the run's checkout**, the `directory` from 224's `status` listing (Squadron's recorded directory, #303), never the server's directory.
- Arguments are validated first with `HandlePauseCall` (`run_id` any string, `directory` absolute). Failure is `isError` and nothing starts.
- Spawned with 223's `spawn_detached`, unchanged. Logs go to `logs_dir() / "mcp" / "handle_pause" / <UTC stamp>-<hex>.{stdout,stderr}.log`. A spawn or log-creation `OSError` is `isError`.
- `StartedCall` (frozen pydantic): `operation`, `pid`, `cwd`, `started_at`, `stdout_log`, `stderr_log`. The child inherits the client's environment, as do resumes (architecture, "The resume's environment").

### D7 — Results and errors

| CLI | MCP |
|---|---|
| exit 0 or 1 (a result, including `rejected`) | `structuredContent` plus the same JSON as text |
| exit 2 (input can't form a call) | `isError`, `RequestError: <detail>` (D5, D6 refusals only) |
| exit 3 (`OPERATIONAL_ERRORS`) | `isError`, `<ExceptionName>: <message>`, the CLI's stderr text |

`call_tool` is the process-boundary handler: any other exception is logged with `logger.exception` and returned as `isError` with `internal error: …`; the server keeps serving.

### D8 — Packaging
`mcp>=2.3,<3` in dependencies; `amoeba-mcp = "amoeba.mcp.server:main"` beside `amoeba` in `[project.scripts]`. `uv tool install --force <repo>` installs both into one environment, which D6 relies on.

### D9 — Install instructions
`docs/mcp-server.md`, linked from the README: install the tool; register once at user scope (`claude mcp add --scope user amoeba -- amoeba-mcp`, or a Codex `[mcp_servers.amoeba]` entry); the client must pass a `PATH` reaching `sq`, `cf` and `git` plus model credentials; restart the client session after a reinstall.

### D10 — Tests
Default suite, fake `cf` and `sq` from 222 to 224.
- **Same names:** `build_parser()` subcommands, tool names and `OperationName` are equal sets.
- **Same functions:** for each in-process tool, a recording fake replaces the operation; the CLI and MCP handler given the same input reach it with equal documents and directories, and `structuredContent` equals the CLI's stdout JSON. A malformed `set_up` returns `rejected` on both.
- **Same argv:** the `handle_pause` argv parses through `build_parser()` to the input values, including a `run_id` starting with `-`.
- **Boundary:** an AST test that `amoeba.mcp` imports none of `store`, `config`, `upstream`, `answering`, `cli`.
- **Off the loop:** a tool blocked on a `threading.Event` does not stop a second call completing.
- **Detached:** `handle_pause` returns `StartedCall` before the child exits; the child's stdout log then holds its `HandlePauseResult`. A relative `directory` starts nothing.
- **stdio smoke:** the SDK's stdio client starts `amoeba-mcp` and lists six tools.

## Success Criteria

- Every CLI operation is available over MCP with the same inputs and the same JSON results, `handle_pause` excepted: it returns a `StartedCall` at once, and its work shows in `status` and `decisions`.
- No operation logic in `amoeba.mcp`; D10 passes. No synchronous call on the event loop; ruff's `ASYNC` rules are clean.
- Format, lint, pyright strict and the full suite pass; the CLI's existing tests pass unchanged.
- `docs/mcp-server.md` exists and the README links it.
- 227 can add an operation to both doors with a name, a subcommand and a table row.

### Verification Walkthrough

Steps 2 to 4 need a configured `config.yaml` and a registered program (225 D1). Step 4 needs a real paused question run and #303.

1. `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest`
2. `uv tool install --force .`, `claude mcp add --scope user amoeba -- amoeba-mcp`; `claude mcp list` shows amoeba connected.
3. In a session started in `/tmp`, call `status` with `directory: /tmp`; it matches `amoeba status` run there. Call `decisions`, then `mark_read`; `amoeba decisions` agrees.
4. Call `handle_pause` with a run's `run_id` and `directory` from `status`: a `StartedCall` returns at once, and its stdout log later holds a `HandlePauseResult`. `answer` the waiting question with the PM's text: `AnswerResult` returns, and `amoeba decisions` lists it.

## Implementation Notes

Relative effort: 2.

1. `names.py`, `wiring.py`, `build_parser()`; switch `cli/main.py`; CLI tests pass unchanged. Commit.
2. `tools.py`, `in_process.py`, `detached.py` with their tests.
3. `server.py`, console script, dependency, stdio smoke. Commit.
4. `docs/mcp-server.md`, README link, walkthrough. Commit.

Security: local stdio only, no listener, nothing the CLI can't do. Every `answer` shows in `decisions` with `answered_by: pm`.
