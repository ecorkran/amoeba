---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: Installing and registering amoeba-mcp, the MCP server that gives an agent session the amoeba commands, and what its tools, timeouts and start-up checks do.
dateCreated: 20261112
dateUpdated: 20261114
status: complete
---

# MCP server

`amoeba-mcp` serves the `amoeba` command's operations to an agent session over stdio,
so the PM can ask any session, in any repo or none, what is waiting and answer through
it, with no `cd` and no flags. It has no operation logic of its own: each tool takes
the CLI's input and returns the CLI's JSON (`cli-contract.md`).

## Install

```
uv tool install --force <path to this repo>
```

This installs `amoeba` and `amoeba-mcp` into one environment. The server starts the
`amoeba` script next to its own interpreter for `handle-pause`, so the two must stay
together; `amoeba-mcp` refuses to start if that script is missing.

**Restart the client session after every reinstall.** A running server keeps the old
code until its session ends: an open session still has the tool names it started with
(after slice 229, `set_up` instead of `add`, `rm` and `list`), and its detached
`handle_pause` now fails with the CLI's invalid-choice error until it is restarted. A
fresh session lists the current tools.

## Register

Once, at user scope, so every session has it:

```
claude mcp add --scope user amoeba -- amoeba-mcp
claude mcp list
```

`amoeba` should show as connected.

For Codex, add a table to `~/.codex/config.toml` (Codex's documented default
location):

```toml
[mcp_servers.amoeba]
command = "amoeba-mcp"
tool_timeout_sec = 185
```

The server needs, in the environment the client gives it: a `PATH` that reaches `sq`,
`cf` and `git`, and the model credentials `sq` uses for answering runs. Claude Code
passes its own environment. Codex lists the variables it forwards: add
`env_vars = ["<NAME>", ...]` to the table for each credential variable, and make sure
`PATH` is among what it passes. The server reads the same config and state homes as
the CLI (`config-contract.md`, `$AMOEBA_HOME`).

## Remove

```
claude mcp remove amoeba --scope user
```

For Codex, delete the `[mcp_servers.amoeba]` table.

## The tools

One tool per operation, named by the operation's name (snake_case; the CLI spells
`handle_pause` and `mark_read` with a dash), each taking the CLI's request as
JSON arguments and returning its result as `structuredContent` (and the same JSON as
text). A request the operation refuses is a normal result with `outcome: rejected`, as
on the CLI; it is not an error.

| Tool | Notes |
|---|---|
| `add` | Registers a repo in a program. Takes `directory` (the caller's checkout, an absolute path) and the single-member fields (`program`, `project`, `rules_paths`, `rules_default`, `authorize_allow`, `authorize_deny`, `depends_on`, `concept`) or `bulk`, a whole multi-member request, never both. |
| `rm` | Removes members, pairs (`PROVIDER:CONSUMER`) or the concept (`concept: true`). Also takes `directory`; with nothing named it removes that repo. |
| `list` | What needs the PM: with no `subject`, the same document as `status` (and `all` adds `settled`); `programs`, `members` and `dependencies` show what is registered. Also takes `directory`. |
| `status` | Also takes `directory`. Its listing gives each run's `run_id` and `directory` for `handle_pause`, and the question key for `answer`. |
| `decisions` | `read_through` goes to `mark_read`. Each record shows `via`, the door that carried a PM answer (`cli` or `mcp`). |
| `mark_read` | |
| `answer` | `text` must be a decision the PM actually gave, passed on as given. It becomes precedent. Recorded with `via: mcp`. |
| `dismiss`, `retract` | |
| `report_release` | Takes `directory` (the caller's checkout, an absolute path) and `commit` (the full hash), `changed`, `touched`, `version`, and `mode` (`report`, `correct` or `withdraw`; `report` when absent). |
| `changes` | Takes `directory` (the caller's checkout, an absolute path) and `since` (ISO-8601 with a UTC offset). Writes nothing. |
| `handle_pause` | Takes `run_id` and `directory` (the run's checkout, from `status`). Starts the work detached and returns a receipt at once. |

`directory` is never guessed: a session can start anywhere, so a missing or relative
`directory` is an error naming the field.

### `handle_pause` returns a receipt

Answering can run for minutes, longer than a client waits for a tool. The tool starts
the CLI's own `handle-pause` (with `--json`, so the log stays machine-readable) in a
session of its own, so it outlives the server and a
client that disconnects, and returns:

`operation`, `pid`, `cwd`, `started_at`, `stdout_log`, `stderr_log`.

The result (`HandlePauseResult`, as the CLI prints it) lands in `stdout_log`, and the
child appends its line to the calls log like any run. An empty `stdout_log` can mean
the work is still running or was killed: confirm through `status` or `decisions`.
These logs live under `logs/mcp/handle_pause/` in the state home and are pruned after
`prune_after_days`.

## Errors and the deadline

A failure is an error result whose text starts with its kind:

- `RequestError: ...`: the call could not form a request (a bad `directory`).
- `<ExceptionName>: ...`: the CLI's own exit-3 failures, with the CLI's stderr text
  (`SquadronError`, `ContextForgeError`, `ConfigError`, `StoreError` and its kinds).
- `TimedOut: <tool> did not finish within 180 s; ...`: the call outlived the server's
  deadline, `MCP_CALL_DEADLINE_SECONDS` (180 s). What to do depends on the tool:
  - `status`, `decisions`, `list`, `changes`: it may still finish. Run `amoeba status`,
    `amoeba decisions`, `amoeba list` or `amoeba changes` in a shell, which has no
    deadline. Do not call the tool again.
  - `add`, `rm`, `answer`, `mark_read`, `dismiss`, `retract`, `report_release`: the work may still
    complete. Check `status` or `decisions` before repeating it.
- `internal error: ...`: a bug; it is logged on stderr and the server keeps serving.

`answer` cannot time out after it has acted: start-up refuses a config whose
`resume_wait_seconds` makes an answer's worst case (`resume_wait_seconds` plus 90.5 s)
reach the deadline, so `resume_wait_seconds` must be below 89.5.

### Client timeouts

What each client waits for a tool by default, checked on 20261112:

- **Claude Code** waits about 28 hours for a tool (`MCP_TOOL_TIMEOUT`, in
  milliseconds; a per-server `timeout` overrides it). Nothing to change.
- **Codex** waits 60 s by default (`tool_timeout_sec`). That is below the 180 s
  deadline, so set `tool_timeout_sec` to at least 185, as in the table above.
  Without it Codex cuts an `answer` off at 60 s while the work goes on.

## Start-up

`amoeba-mcp` takes no arguments. Before it serves it checks, and exits non-zero with
one stderr line (which the client shows) if:

- the `amoeba` script is not beside its interpreter (reinstall);
- the legacy state move fails (`StoreRelocateError`, `StoreBusyError`; the next session
  start tries again, `store-contract.md`);
- `config.yaml` is missing or invalid (`ConfigError`);
- `resume_wait_seconds` is too large for the deadline: the message names the key and
  the largest value that passes.

The server holds no state. It ends when the client closes its end.
