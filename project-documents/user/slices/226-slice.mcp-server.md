---
docType: slice-design
slice: mcp-server
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 224-slice.status-and-decisions
- 228-slice.state-home-and-question-lifecycle
interfaces:
- 227-slice.program-dependencies
dateCreated: 20261107
dateUpdated: 20261112
status: not_started
---

# Slice Design: MCP Server

## Overview

An MCP server, `amoeba-mcp`, in front of the eight operations the CLI has after 228: `set_up`, `handle_pause`, `answer`, `status`, `decisions`, `mark_read`, `dismiss` and `retract`. It uses the CLI's names, passes input through unchanged, and returns the operations' own results. It has no logic of its own. It completes scenario C: from any directory, an agent session can see what waits on the PM and what was decided, and can answer for the PM.

**Value:** the PM can ask any agent session, in any repo or none, what is waiting and answer through it, with no `cd` and no CLI flags.

**Excluded:** changes to any operation's behavior (a gap is fixed in the operation, not here; D11's `via` is recorded beside the answer, it changes no outcome); `report_release` and `changes` (227); MCP resources, prompts, notifications and HTTP transport; a tool for reading a detached call's result (the agent reads the log files).

## Dependencies

- **222 to 225 and 228 merged:** all eight operations with request and result models, 223's `Deps` bundle, `operations/processes.py` (`start_child`, `terminate_group`, the `Spawner` type), `logs_dir()` and the typed errors. 228's calls log, pruning, `state_layout()`, `config_home()`, `state_home()` and `open_state_store` exist.
- **Python MCP SDK `mcp` 2.x,** observed at 2.3.0 on 20261112 (`pip index versions mcp`). The tool guide describes v1; the design follows the 2.x source.
- **`ecorkran/squadron#303` is closed** (checked with `gh issue view` on 20261112): `sq runs list` carries each run's working directory, which `status` already uses. Nothing here waits on it. Squadron 0.24.28 is installed.

## Architecture

```
src/amoeba/
├── operations/names.py  # OperationName, Door (StrEnum) (D3, D11)
├── wiring.py            # load_config, open_store, prepare_home, default_deps, invoke(), OPERATIONAL_ERRORS, answer_bound_seconds, check_deadline; re-exports types (D4, D12)
├── mcp/
│   ├── server.py        # main(): low-level Server over stdio (D1, D7)
│   ├── tools.py         # TOOLS table, input schemas (D2, D5)
│   ├── in_process.py    # run a tool in a worker thread under a deadline (D4, D12)
│   └── detached.py      # StartedCall; start the amoeba CLI detached (D6)
└── cli/main.py          # uses OperationName, wiring.invoke, build_parser()
```

`cli` and `mcp` both import `operations` and `wiring`. `mcp` imports nothing from `store`, `config`, `upstream`, `answering` or `cli`; it gets the types and `start_child` it names from `wiring`. 228 split the home into config and state: the doors ask for `state_layout()`, `config_home()` and `state_home()`, which only `cli`, `mcp` and `wiring` may call, and they open the store only through `open_state_store` (228 D2).

The server holds no state. Each call loads the config, opens the store in its worker thread and closes it, so no SQLite connection is shared across threads. The agent client starts and stops the server with its session, which fits "nothing to run".

**Start-up.** `main()` calls `wiring.prepare_home()` once before serving. It is 228's `prepare_state_home(state_layout())`, so the legacy move runs once, single-threaded, before any call. A failure (`StoreRelocateError`, `StoreBusyError` or any other `OPERATIONAL_ERRORS`) exits non-zero with the CLI's stderr text, which the client shows, and the server never starts; the next session start tries again. Each call's `open_state_store` still runs the same function, which does nothing once the move is done. A CLI run beside the server, or beside a second server, is kept out by 228's lock on the legacy store, so two first calls cannot race. `main()` then checks the deadline invariant (D12), also before serving.

## Technical Decisions

### D1 — Low-level server over stdio
`mcp.server.lowlevel.Server("amoeba", …)` with `on_list_tools` and `on_call_tool`, served with `stdio_server()`. `amoeba-mcp` takes no arguments. The low-level server is used so the published input schema is the operation's own request model while raw arguments reach the operation unvalidated: the operations validate their own input (222 D7), so malformed input gets the same result on both doors. The handler is registered with the SDK's own input validation turned off (v1 spelled this `validate_input=False` on the call-tool decorator; task 0.3 confirms the 2.x spelling), so the arguments arrive exactly as the client sent them; the D10 "same functions" test fails if the SDK still validates. Logging goes to stderr; nothing in `amoeba.mcp` prints. Short server instructions say the tools are the CLI's operations, `handle_pause` returns a receipt, `status` gives the inputs for `handle_pause` and `answer`, and `answer` carries only a decision the PM gave (D3).

### D2 — One tool table
`TOOLS: tuple[ToolSpec, ...]`. `ToolSpec` (frozen dataclass): `name` (`OperationName`), `request_model`, `takes_directory`, `mode` (`RunMode.IN_PROCESS` or `RunMode.DETACHED`), `description` and `timeout_advice` (in-process rows: what the agent does when the call times out, D12). There is no per-tool adapter: in-process tools run through `wiring.invoke` (D4).

| Tool | Mode | Input | Result |
|---|---|---|---|
| `set_up` | in-process | `SetUpRequest` + `directory` | `SetUpResult` |
| `status` | in-process | status request + `directory` | `StatusResult` |
| `decisions` | in-process | `DecisionsRequest` | `DecisionsResult` |
| `mark_read` | in-process | `MarkReadRequest` | `MarkReadResult` |
| `answer` | in-process | `AnswerRequest` | `AnswerResult` |
| `dismiss` | in-process | `DismissRequest` | `DismissResult` |
| `retract` | in-process | `RetractRequest` | `RetractResult` |
| `handle_pause` | detached | `HandlePauseCall` (`run_id`, `directory`) | `StartedCall` |

`answer` takes the question key as `status` lists it (`run_id`, optionally `paused_at`); it is `AnswerRequest` unchanged. It runs in-process in a worker thread, not detached as the plan entry's wording had it. Its resume waits only `resume_wait_seconds` (223 D8) and starts `sq run --resume` detached in its own session, so it is not long work, and the agent relaying a PM decision gets `no_such_question`, `rejected`, `refused` or `not_delivered` back directly. Only `handle_pause`, which waits for a whole answering run, is detached. `dismiss` and `retract` are in-process too: each is one short write with no subprocess. 227 adds two rows.

### D3 — Names once, descriptions in the table
`OperationName(StrEnum)` in `operations/names.py`; the CLI registers subcommands from it and the table uses it for tool names. The `handle_pause` description says the result lands in the receipt's stdout log and an empty log may mean still running or killed, so confirm through `status` or `decisions`. The `answer` description says `text` must be a decision the PM actually gave, passed on as given, never one the agent composed, since a `pm` answer becomes precedent (223 D9).

### D4 — Shared wiring and one invoke; store calls off the loop
The CLI's `_run_*` functions each place arguments differently (`answer(store, config, document, deps=…)`, `dismiss(store, document, clock=…)`, and so on). To keep that placement in one spot, `wiring.py` holds:
- `load_config()`, `open_store()` (through `open_state_store`, 228 D2), `default_deps()` (223's bundle plus 224's `list_runs` and `project_names`) and `OPERATIONAL_ERRORS`.
- `invoke(name, document, directory, door) -> result model`: opens the store, calls the operation named by `name` with the placement the CLI uses today, closes the store. It is the moved body of the CLI's seven in-process `_run_*` functions; `cli/main.py` keeps argument parsing, printing and exit codes and calls `invoke`. The MCP in-process runner calls the same function. The names (`start_child`, `LaunchLogs`, `LaunchError`) that D6 needs are re-exported from `wiring`.

`handle_pause` stays a CLI-only body: it also appends the calls-log line (228 D11). The MCP door runs the CLI for it (D6), so the same line is written by the same code.

`call_tool` is async; every in-process call, store open included, and the detached start run in `anyio.to_thread.run_sync` under D12's deadline. Nothing synchronous runs on the loop but the table lookup and result building.

### D5 — `directory` input and results
- For tools with `takes_directory` (`set_up`, `status`, `handle_pause`), the schema is the request model's JSON schema plus a required `directory` (absolute path). `directory` is removed before the rest is passed to the operation.
- The server never reads its own working directory; an MCP session can start anywhere. A missing or relative `directory` is refused as `isError` naming the field, and nothing runs.
- Results are `model_dump(mode="json")`: exactly the JSON the CLI prints. No output schema.

### D6 — Detached `handle_pause`
- Starts the `amoeba` script beside the server's interpreter (`Path(sys.executable).parent / "amoeba"`); `amoeba-mcp` exits at start-up if it is missing. argv: `[amoeba, "handle_pause", "--", run_id]`.
- **`cwd` is the run's checkout**, the `directory` from `status`'s listing (Squadron's recorded working directory), never the server's directory. The CLI takes its `directory` from its own working directory (`_run_handle_pause`), which is why `cwd` matters.
- Arguments are validated first with `HandlePauseCall` (`run_id` any string, `directory` absolute). Failure is `isError` and nothing starts.
- Started with `wiring.start_child` (`operations.processes.start_child`, which wraps the kept `spawn`: its own session, no stdin, exclusive logs, the inherited environment). Logs go to `logs_dir() / "mcp" / "handle_pause" / <UTC stamp>-<hex>.{stdout,stderr}.log`. A `LaunchError` result or a log-creation `OSError` is `isError`.
- `StartedCall` (frozen pydantic): `operation`, `pid`, `cwd`, `started_at`, `stdout_log`, `stderr_log`.
- **How it ends.** The child is the CLI's `handle_pause`: it claims the pause, runs the answering run for at most `answering_wait_seconds` (`terminate_group` stops it after that, 223) and exits. It is in its own session on purpose, so it outlives the server and a client that disconnects. Its logs are old files under `logs/mcp/`, which 228's `prune` removes after `prune_after_days` (that directory is not protected there; the walk removes the emptied directories too). A test pins this (D10).

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
`docs/mcp-server.md`, linked from the README: install the tool; register once at user scope (`claude mcp add --scope user amoeba -- amoeba-mcp`, or a Codex `[mcp_servers.amoeba]` entry); the client must pass a `PATH` reaching `sq`, `cf` and `git` plus model credentials; restart the client session after a reinstall. After a reinstall of a running server's tool, a stale server keeps the old code until the session restarts; the doc says so.

### D10 — Tests
Default suite, fake `cf` and `sq` from 222 to 224.
- **Same names:** `build_parser()` subcommands, tool names and `OperationName` are equal sets.
- **Same functions:** for each in-process tool, `wiring.invoke` is replaced by a recorder; the CLI and the MCP handler given the same input reach it with equal documents, directories and (D11) different `door` values, and `structuredContent` equals the CLI's stdout JSON. A malformed `set_up` returns `rejected` on both. A second test runs the real `invoke` against a throwaway store through both doors.
- **Same argv:** the `handle_pause` argv parses through `build_parser()` to the input values, including a `run_id` starting with `-`.
- **Boundary:** an AST test that `amoeba.mcp` imports none of `store`, `config`, `upstream`, `answering`, `cli`.
- **Off the loop:** a tool blocked on a `threading.Event` does not stop a second call completing.
- **Deadline (D12):** a tool blocked past a patched short deadline returns the timed-out `isError` carrying that tool's advice (`READ_ADVICE` for `status` and `decisions`, `WRITE_ADVICE` for the others); a following call still works. An exception raised by the abandoned worker after the deadline is logged at ERROR.
- **Invariant (D12):** `answer_bound_seconds(config)` equals `resume_bound_seconds(config)` plus the listed timeouts, built from the constants; `check_deadline` passes when the bound is below the deadline and raises naming `resume_wait_seconds` when it is not; `main()` with such a config exits non-zero before serving.
- **Start-up:** against a throwaway legacy home, `main()` moves the state before serving; a move that fails exits non-zero with the CLI's text and serves nothing. Two `invoke` calls started at once against a second throwaway legacy home both succeed and the move happens once (228's lock).
- **Detached:** `handle_pause` returns `StartedCall` before the child exits; the child's stdout log then holds its `HandlePauseResult` and the calls log holds the child's line. A relative `directory` starts nothing.
- **Log exit:** a log under `logs/mcp/handle_pause/` older than the cutoff is removed by `prune` and its emptied directories with it; a younger one stays.
- **Via (D11):** `answer` through each door stores `cli` or `mcp`; `decisions` shows it; a store row from before migration 004 shows no `via`.
- **stdio smoke:** the SDK's stdio client starts `amoeba-mcp` and lists eight tools.

### D11 — The door is recorded on each answer
Both doors answer for the PM, so an answer should say which door carried it. `Door(StrEnum)` (`cli`, `mcp`) in `operations/names.py`; `invoke` and `answer` take a `via: Door` argument, which the doors set and the caller cannot. Migration `004_answer_via.sql` is `ALTER TABLE answers ADD COLUMN via TEXT CHECK (via IN ('cli', 'mcp'))` (ADD COLUMN only, nullable, per 222 D3; pinned to the enum by the vocabulary test). Pre-004 rows keep `NULL`, which `decisions` prints as absent rather than inventing a door. `AnswerRecord`, the `decisions` entries (`via` beside `answered_by`), `EXPECTED_SCHEMA_VERSION` (3 to 4), `docs/store-contract.md` and `docs/cli-contract.md` change with it. No outcome of any operation depends on `via`.

### D12 — Every MCP call has a deadline
`status` and `decisions` call `sq` and `cf`, and `status` makes one `cf` call per unknown directory, so their time has no fixed bound. `answer` has one: `wiring.answer_bound_seconds(config)` is `resume_bound_seconds(config)` (228 D4) plus the timeouts of the other `sq` and `cf` calls on `answer`'s path (task 0.2 lists them). `run_in_process` runs the worker under `anyio.fail_after(MCP_CALL_DEADLINE_SECONDS)` with `abandon_on_cancel=True`. `MCP_CALL_DEADLINE_SECONDS` is one named constant in `mcp/in_process.py`, set below the default tool timeout of the clients the install doc names (task 0.3 reads each client's current default and sets it; today's Codex documentation is the source for its value).

**Invariant.** `answer_bound_seconds(config)` is below `MCP_CALL_DEADLINE_SECONDS`, so `answer` never times out after it has recorded an answer and started a resume. `main()` checks it before serving and exits non-zero naming `resume_wait_seconds` as the config key to lower; a test pins the check.

**On timeout.** The call returns `isError`, `TimedOut: <tool> did not finish within <n> s; <timeout_advice>`, with the advice from the tool's `ToolSpec` (D2):
- `status`, `decisions` (`READ_ADVICE`): it was abandoned and may still finish; run `amoeba <tool>` in a shell, which has no deadline. The agent is never sent back to the tool that timed out.
- `set_up`, `answer`, `mark_read`, `dismiss`, `retract` (`WRITE_ADVICE`): it may still complete; check `status` or `decisions` before repeating it.

The abandoned thread finishes on its own, closes its store in its `finally`, and every operation write is one transaction, so a late finish leaves a consistent store. An exception it raises after the deadline is logged with `logger.exception` by the worker wrapper, since nobody awaits the result. Nothing is written for the timeout itself.

## Success Criteria

- Every CLI operation is available over MCP with the same inputs and the same JSON results, `handle_pause` excepted: it returns a `StartedCall` at once, and its work shows in `status` and `decisions`.
- No operation logic in `amoeba.mcp`; CLI and MCP place operation arguments in one function (`wiring.invoke`); D10 passes. No synchronous call on the event loop; ruff's `ASYNC` rules are clean.
- Every answer records its door; `decisions` shows it.
- No MCP call outlives `MCP_CALL_DEADLINE_SECONDS`, and `answer` cannot hit it: start-up refuses a config whose `answer` bound is not below it. A timed-out `status` or `decisions` names the CLI as the fallback.
- The state move runs once at server start-up; a failed move stops the server with the CLI's message.
- Format, lint, pyright strict and the full suite pass; the CLI's existing tests pass, edited only where a moved `_run_*` body or `via` requires it.
- `docs/mcp-server.md` exists and the README links it.
- 227 can add an operation to both doors with a name, a subcommand, an `invoke` case and a table row.

### Verification Walkthrough

All steps run by the implementing agent, with no person involved. Steps 3 to 5 are one live test, `tests/live/mcp/test_mcp_walkthrough_live.py`, which uses the pause fixtures and helpers in `tests/live/pause/` (a throwaway member, `AMOEBA_HOME` and Context Forge data directory, real `sq`, `cf` and models) and drives `amoeba-mcp` with the SDK's stdio client from a working directory under `/tmp`.

1. `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest`
2. `uv tool install --force .` succeeds and installs `amoeba` and `amoeba-mcp` side by side.
3. The client lists eight tools. `status` with `directory: /tmp/…` matches `amoeba status` run there. `decisions`, then `mark_read`; `amoeba decisions` agrees.
4. A real run pauses on a question (fixture pipeline). `handle_pause` with the `run_id` and `directory` from `status` returns a `StartedCall` at once; its stdout log later holds a `HandlePauseResult`; the calls log holds a line for it.
5. For a question the run left waiting on the PM, `answer` with a fixture text returns `AnswerResult`; `decisions` lists it with `via: mcp`; the same through `amoeba answer` lists `via: cli`. `dismiss` and `retract` on a second and third fixture question return their results.
6. Registration: `claude mcp add --scope user amoeba -- amoeba-mcp`, then `claude mcp list` shows `amoeba` connected. This is the install and the end state: it stays on. Steps 1 to 5 prove the server without touching any client configuration.
7. Clear: the throwaway world is deleted with its directory. The registration is not removed here. Undoing it is documented (`claude mcp remove amoeba --scope user`, in `docs/mcp-server.md`), not exercised.

### Operator walkthrough

- **Start.** Install the tool, register once, restart the session. A missing `amoeba` script, or an old tool without `amoeba-mcp`, stops the server at start with a stderr message the client shows. So does a failed state move (the next session start tries again) and a config whose `resume_wait_seconds` is too large for the deadline (the message names the key).
- **Normal.** Ask the agent what is waiting: `status` returns within the deadline. Ask it to answer: `answer` returns `recorded` and a resume result. A pause not yet handled: `handle_pause` returns a receipt; the agent reads the log or checks `status`.
- **Failures.** Squadron or Context Forge down: `isError` with the exception's name, nothing written. Bad input: the operation's `rejected` result, same as the CLI. Slow `sq`: `TimedOut` after the deadline. For `status` and `decisions` the message says to run the CLI in a shell, which has no deadline; for the write tools it says the work may still complete and to check `status` or `decisions` before repeating. `answer` cannot time out after it has acted, because start-up refuses a config whose resume wait exceeds the deadline. A client that disconnects during `handle_pause`: the detached child finishes in its own session.
- **End state and cleanup.** Questions end as they do in 228 (answered, closed, dismissed, retracted). Detached logs are pruned after `prune_after_days`. The server has no state; `claude mcp remove` undoes the registration.
- **Dead ends found and closed:** a `status` that times out every time and points back at itself (D12: the CLI is the named fallback); an `answer` that times out after acting (D12 invariant, checked at start-up); two first calls racing the legacy move (start-up `prepare_home`); a walkthrough that registered the client and then removed it (step 6 is the end state); detached logs nothing removed (D6, pinned by a test); answers that could not tell which door carried them (D11); a walkthrough step that needed a person's registered program and a real run (now fixtures).

## Implementation Notes

Relative effort: 3.

1. `names.py` (`OperationName`, `Door`), `wiring.py` with `invoke`, `build_parser()`; switch `cli/main.py`; CLI tests pass. Commit.
2. Migration 004, `via` in `answer`, `decisions`, contract docs. Commit.
3. `tools.py`, `in_process.py` (deadline), `detached.py` with their tests. Commit.
4. `server.py`, console script, dependency, stdio smoke. Commit.
5. `docs/mcp-server.md`, README link, live walkthrough test. Commit.

Security: local stdio only, no listener, nothing the CLI can't do. Every `answer` shows in `decisions` with `answered_by: pm` and its door.
