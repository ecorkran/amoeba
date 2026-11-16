---
docType: slice-design
slice: push-and-presence
project: amoeba
parent: user/architecture/240-slices.agent-messaging.md
dependencies:
- 240
interfaces:
- 243
- 244
dateCreated: 20261115
dateUpdated: 20261116
status: complete
turns: 38
promptTokens: 3541923
cachedTokens: 3353387
cacheWriteTokens: 188478
completionTokens: 48015
durationSeconds: 404.5
costUsd: 1.575208
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 1.5752076999999998
    completionTokens: 48015
---

# Slice Design: Push and Presence

## Overview

`amoeba-mcp` tells its own client session when new mail arrives, and records that it is serving. The server resolves its member once, from its working directory. A watcher beside the MCP loop reads the member's highest delivery sequence number every `notify_poll_seconds`. When it rises, the server sends a Claude Code channel event, and a resource update on `amoeba://inbox` to a client that subscribed. Neither carries message text. Each serving process also keeps a `sessions` row (migration 7), so `list` shows who is live where. A session whose agent answers a channel event with an `inbox` call is marked push-confirmed, and only those sessions stop 244 from waking the repo. Today `server.run` serves the 2026-07-28 protocol era, which Claude Code will not register a channel on, so this slice replaces it with a handshake-only loop. The slice proves the whole path against a real interactive Claude Code session.

## Value

User value. A live Claude Code session acts on a request when it arrives, not at its next rules-file moment. The PM sees which repos have a live agent, in `list`. Architecturally, the slice provides the `sessions` table and `live_member_ids` that 244 (waking) reads, and the push path that 243's notes use unchanged.

## Technical Scope

**Included**
- A handshake-only serve loop for `amoeba-mcp`, replacing `server.run` (D1).
- The watcher: member resolution, the push check, the channel event, the resource update (D2 to D5).
- The `amoeba://inbox` resource: list, read, subscribe (D5).
- Migration 7: `sessions`. Registration, heartbeat, clean-exit delete, the stale rule, pruning in the heartbeat, and push confirmation (D6).
- Three required config keys: `notify_poll_seconds`, `session_heartbeat_seconds`, `session_stale_seconds` (D7).
- `list` and `status` show live sessions per member (D8).
- Docs: the launch flag and shell alias, the registration form, `mcp-server.md`, `config-contract.md`, `store-contract.md`, `cli-contract.md`; the `INSTRUCTIONS` text (D9).
- An automated live test against a real interactive Claude Code session in a pseudo-terminal (D10).
- Live store backed up, migrated to 7, config keys added, read back.

**Excluded**
- Message operations, the delivery writer and the sweep's message steps (240). Notes (243). Waking (244).
- Push for clients other than Claude Code: they get the resource update only if they subscribe, and none did when observed 20261114 (architecture).
- Push under `claude -p`: Claude Code ignores the development flag there, so pipeline runs poll.
- Asking the client whether it registered the channel. Claude Code gives the server no signal either way, so a session row means "an `amoeba-mcp` is serving". Push confirmation (D6) infers "push is on" from the agent answering an event instead.

## Dependencies

### Prerequisites
- 240 built and integrated: `deliveries` with its `(member_id, seq)` index, `StatusResult`/`MemberStatus` with `requests`, `inbox` and the live store at schema 6. 241 changes no 240 function or signature.
- Claude Code installed and logged in, for the live test only. Observed 20261115: 2.1.318.
- `mcp>=2.3,<3`. Observed 20261115: 2.3.0. The range admits 2.x minor releases, and `pinned_loop.py` imports SDK internals (`mcp.server.runner`, `mcp.shared.jsonrpc_dispatcher`, `mcp.shared.transport_context`) with untyped streams, so a minor bump can move them without a type error. `tests/mcp_server/test_protocol_pin.py` runs in the default suite (CI included) and is what catches that drift. Observed 20261116: `serve_pinned` read against the installed 2.3.0 `serve_loop` builds the same dispatcher (`initialize` inline, default `raise_handler_exceptions`), the same `Connection.for_loop` and the same `serve_connection` call, and adds only the background task group.

### Interfaces Required
- From 240: `deliveries(seq, member_id, message_id, event, created_at)`, `messages(from_member, to_member, kind)`, `highest_assigned_seq(transaction)` (the number `inbox` returns as `as_of_seq`), `MemberStatus`, and the `inbox` tool name, which `call_tool` watches for push confirmation (D6).
- From 220: `operations.members.resolve_member` (the directory-to-member rule), `wiring.open_store` (the only way the store is opened; `tests/test_store_opened_only_by_state_move.py`), `wiring.default_deps` for `cf_run`, `Deps.clock`.
- From the MCP SDK (2.3.0): `Connection.for_loop`, `Connection.notify`, `Connection.initialized`, `serve_connection` and `JSONRPCDispatcher`. These are public modules, not the top-level API; D1 pins their behavior with a contract test.

## Architecture

### Component Structure

```
amoeba-mcp main ──► mcp/pinned_loop.py ──► serve_connection (handshake-only)
                         │
                         └─ task group ─► mcp/presence_task.py run_presence: resolve, then
                                            ├─ mcp/presence.py      state, member, heartbeat, confirmation
                                            └─ mcp/inbox_watcher.py push check ─► mcp/channel_event.py
                                          mcp/inbox_resource.py resources/list|read|subscribe|unsubscribe
                                                  │
                         wiring_presence.py ─► store/sessions.py · store/sql_sessions.py · store/push_reads.py
```

- `mcp/pinned_loop.py`: `serve_pinned(server, streams, init_options, background)`. Builds the dispatcher and `Connection.for_loop`, starts `background(connection)` in a task group, runs `serve_connection`, cancels the background on return. It mirrors the SDK's `serve_loop` (which does not expose its connection) and nothing else.
- `mcp/presence.py`: `PresenceState` (member id or none, set once, read by the resource handlers), `resolve_presence` (D3), the heartbeat loop, `note_event_attempted` and `note_inbox_called`, and `ToolPresence`, through which `call_tool` reports a successful `inbox` (D6).
- `mcp/presence_task.py`: `run_presence`, the background task: resolution, then the heartbeat and push loops in one child task group, its one top-level handler, and the shielded exit delete (D2).
- `mcp/inbox_watcher.py`: the push loop (D2).
- `mcp/channel_event.py`: a pure function from push rows to the event's params (D4). No I/O, so a test checks every field.
- `mcp/inbox_resource.py`: the four resource handlers (list, read, subscribe, unsubscribe; D5), `register_inbox_resource`, which adds them to the server (and so declares `resources: {subscribe: true}`), and `initialization_options`, which declares the channel capability.
- `wiring_presence.py`: the synchronous bodies the worker threads run (member lookup, heartbeat, exit delete, the push reads, `as_of_seq`) and the types presence passes around. `amoeba.mcp` reaches nothing but `wiring` and the operations' types (226 D10), so the store is reached through this module, beside the other `wiring_*` modules.
- `operations/status_sessions.py`: the sessions `status` shows, read in their own transaction.
- `store/sessions.py`: `upsert_session`, `delete_session`, `prune_stale_sessions`, `live_sessions`, `live_member_ids`, with one `LIVE_SESSION` predicate constant in `store/sql_sessions.py`. `store/push_reads.py`: `member_high_seq` and `push_rows_after`. Rows are frozen dataclasses in `store/models.py` (`Session`, `PushRow`). The store imports nothing from `operations` or `mcp`.
- `operations/status_models.py`: `SessionEntry`; `MemberStatus` gains `sessions`.
- Each file stays near 300 lines. `server.py` (221 lines before this slice, 283 after) only swaps `server.run` for `serve_pinned`, adds the capabilities and handlers, and threads `ToolPresence` to `call_tool`.

### Data Flow

**Start.** `main` runs its existing checks, then `serve` opens stdio and calls `serve_pinned`. The handshake never waits on `cf` or SQLite: the background task does that work in worker threads (`anyio.to_thread`).

**Watcher.** The background task has one top-level handler (D2). Inside it: resolve the member (one `cf` call in a thread, bounded by `CF_GET_TIMEOUT_SECONDS`). If it is none, log one line and return: no row, no loop. Otherwise wait on `connection.initialized`, read the client's name, and run the heartbeat loop and the push loop in one child task group. The push loop takes its baseline (`member_high_seq`), retrying each tick until the read succeeds and sending nothing before it has one. Then every `notify_poll_seconds` it reads again. When the value is higher than the last seen, it reads the new rows (`push_rows_after`), builds the event, sends the channel event, and sends the resource update if the client subscribed (D5). The new value becomes the last seen.

**Exit.** However the background task ends, a shielded, bounded `DELETE` removes the session row. It ends when the client closes stdin (`serve_connection` returns and the background is cancelled), or when the watcher stops on an error (D2).

### State Management

- In memory: the resolved member, the last-seen sequence number, the session id (`uuid4().hex`, made once at start), the start time, the time of the last unanswered channel event, and the push-confirmed time (D6). Only the event loop's tasks touch them. `PresenceState` is read by the resource handlers, which run as soon as `initialize` is answered, before the member is known. It has three states: pending, a member, or off with a reason. It carries a `resolved` event that the background task sets in a `finally`, so the pending state always ends, at the latest after the lookup's own bounds (D3).
- In the store: one `sessions` row per serving process. Nothing else is written. The watcher's reads write nothing and keep no marker, so they never hide mail from another reader (architecture: no shared read marker).

## Technical Decisions

### D1 — A handshake-only serve loop
Status: decided

`Server.run` in mcp 2.3 is a dual-era loop: the client's first request decides the era. Claude Code (v2 runtime, the default from 2.1.274) opens every stdio server with a `server/discover` probe for 2026-07-28, and does not register a channel on a server that answers it. Measured 20261115 with a raw JSON-RPC driver against the SDK, same `Server` object both ways:
- `Server.run`: the probe is answered with `supportedVersions: ["2026-07-28"]`, and a following `initialize` is refused (error -32022).
- A handshake-only loop: the probe gets `Method not found` (-32601), and `initialize` is served at 2025-11-25. The client's documented fallback is the earlier handshake.

So the server serves the handshake era only, through `serve_pinned`. The pin is the loop choice, not a negotiated value: there is no version constant to keep in step.
- Every MCP client that opens with `initialize` is unaffected, which includes the SDK client the existing tests use. A client that speaks only 2026-07-28 cannot connect. The architecture accepts this.
- `tests/mcp_server/test_protocol_pin.py` reproduces the measurement over real stdio on every run, so an SDK change to either loop fails a test, not a session. The symbols this builds on (`Connection.for_loop`, `serve_connection`, `JSONRPCDispatcher`) were imported and run against the mcp 2.3.0 install in the same measurement (the install is in the repo's `.venv`); until the pin test exists, that measurement is the only evidence.
- Rejected: `MCP_PROTOCOL_NEGOTIATION=legacy` in the client's environment (it changes every server, and each user would have to set it); catching the probe inside `Server.run` (the era is chosen before any handler runs); the SDK's one-call `serve_loop` with the session captured in a `notifications/initialized` handler. Measured 20261115: it works and needs no `Connection` or dispatcher, but `ServerSession.send_notification` takes only the SDK's own notification types, so the channel event would need a non-SDK model cast into that union (or a read of the private `_connection`). The owned `Connection` has a public, typed `notify`.

### D2 — The watcher runs beside the loop, and never blocks it
Status: decided

The push loop and the heartbeat loop are two tasks, so a store wait in one does not delay the other. Every store open, read, write and `cf` call goes through `anyio.to_thread.run_sync`; the tasks themselves only sleep, send and bookkeep. Each worker call opens its own store through `wiring.open_store` (sqlite connections do not cross threads, and every in-process tool call already does the same). The store opener is a constructor argument, so a test substitutes a blocking one.
- The push check is one indexed read, `SELECT MAX(seq) FROM deliveries WHERE member_id = ?`, a few milliseconds.
- `StoreBusyError` in a push tick, the baseline read or a heartbeat: logged at WARNING once per run of failures, and the next tick or beat retries. This is a specific exception with a stated reason: push is a hint, and polling is the floor. If beats keep failing past `session_stale_seconds`, `list` stops showing the session (D6), and the first beat that succeeds re-creates the row.
- Any other failure ends presence: a `StoreError` (corrupt, schema) from either loop, a `ContextForgeError` or `StoreError` during member resolution (D3), and anything else the task raises (an unreadable working directory, a bad config, a bug), including the exception group the child tasks raise. The background task shares its task group with `serve_connection`, so an escaping exception would cancel the loop and end every tool. Its one top-level handler therefore catches `Exception` (not `BaseException`, so cancellation passes), as `call_tool` does at its boundary: it calls `logger.exception`, the child tasks are cancelled, and the row is deleted (if that delete fails too, the row goes stale, D6). The server keeps serving its tools, which report their own errors. Presence is removed rather than left running, so `list` never shows a live session that has no push.
- `Connection.notify` drops a send to a closed stream with a debug log, for `BrokenResourceError` and `ClosedResourceError` only; any other exception it raises reaches the top-level handler (read in `mcp/server/connection.py`, 2.3.0, and pinned by `tests/mcp_server/test_inbox_watcher.py`). That happens only when the client's end is closed, and `serve_connection` returns right after, so nothing retries. The INFO line for an event therefore says `channel event attempted`, and does not claim delivery.
- A baseline taken after the member resolves can miss mail that arrived between the agent's first `inbox` call and that moment, a window of one `cf` call. Polling covers it.
- Push fires on deliveries. An expiry becomes a delivery when a sweep records it (240 D6), so an expiry no write or `list` has swept is seen at the next poll, not pushed.

### D3 — The member is resolved once, in the background task
Status: decided

`resolve_member(store, Path.cwd(), cf_run)` runs once, in a worker thread, after the handshake. Claude Code starts a stdio server in the session's project directory.
- A `Member`: presence and push for it.
- `NotInProgram` or `NotAProject`: the server serves its tools exactly as today. One INFO line says the directory is not a member. No row, no loop. After `amoeba add` in that repo, the exit is reconnecting the server (`/mcp`) or starting a new session.
- `ContextForgeError`, or a `StoreError` in the lookup: the same as not a member, through D2's top-level handler (`logger.exception`, no row, no loop). The `cf` call is bounded by `CF_GET_TIMEOUT_SECONDS` (30 s): `run_cf` returns a timeout as a `CfCallFailed` value, and `resolve_member` raises it as `ContextForgeError`. The tools still work, and `list` shows the repo with no live session. The exit is reconnecting (`/mcp`) or a new session. Resolution is one-shot by design: there is no retry, and `list` cannot tell a failed lookup from a repo with no agent running. The signal is the ERROR line with its traceback in the server's log. Both failures are rare (a local `cf` call and a local store), so one-shot resolution with a reconnect as the exit is accepted rather than adding a retry loop or a stored unresolved state.
- Capabilities are fixed at `initialize` and cannot wait for this answer, so every server declares the channel capability and the resources capability, and a non-member server never sends. `resources/list` returns an empty list there. This differs from the plan's "today's tools" only in the declared capabilities.
- A member removed with `rm` while its server runs keeps heartbeating. `list` shows live sessions only under active members, so it shows nothing; a member re-added later is live again at once, which is true.

### D4 — The channel event
Status: decided

Method `notifications/claude/channel`, with the capability `experimental["claude/channel"] = {}` declared at `initialize`. Params, per the Claude Code channels reference (read 20261115): `content` (string, becomes the tag body) and `meta` (string values; keys must be identifiers, or Claude Code drops them silently).
- `meta`: `first_seq`, `last_seq` and `count`, all digits.
- `content`, fixed template: `Amoeba: N new deliveries for this repo (seq A-B): <entries>. Call the inbox tool. Pass since=<as_of_seq from your last inbox call>, or omit since if you have none.` Each entry is `<kind>, <event> from|with <member id>`, built only from the closed enums (`request` or `note`; `sent`, `accepted`, ...) and the counterparty's member id, which Context Forge assigned. At most `CHANNEL_EVENT_MAX_ENTRIES` entries (a constant, 10) are listed, then `and K more`. Subjects, bodies, results, reasons and the sender-chosen request id never appear, so message text reaches the agent only through `inbox`, under the notice.
- The counterparty is the member of the message that is not the receiving member (for a note, its sender).
- The instruction tells the caller to use its own cursor, not a number from the event: an agent that ignored an earlier event must not skip it. Events queue and arrive together on the next turn (channels reference), so there is no ordering to preserve.
- The server's `INSTRUCTIONS` text gains a paragraph: events arrive as `<channel source="amoeba">`, they say only that mail arrived, and the response is to call `inbox`.
- Rejected: including a subject or request id (sender-controlled text in the one place that is not under the notice); one event per delivery (a burst would start a turn per item).

### D5 — The `amoeba://inbox` resource
Status: decided

Every handler first waits for `PresenceState.resolved`, so none answers from the pending state: a `resources/list` during resolution returns the resource (or nothing, once resolution finds no member), and a subscribe is not refused for a member not yet known. The wait ends within the lookup's bounds, a `cf` call of at most `CF_GET_TIMEOUT_SECONDS` plus the store waits (D3), and only that request waits; the loop and the tools do not. `resources/list` returns the one resource for a member, nothing otherwise. `resources/read` returns JSON `{"member": <id>, "as_of_seq": <highest_assigned_seq>}`, the same number `inbox` gives, and no message text. `resources/subscribe` of `amoeba://inbox` sets a flag in `PresenceState` and `unsubscribe` clears it; `unsubscribe` with the flag already clear succeeds. Both run on the event loop, as the watcher does, so no state crosses a thread. On a server with no member, or for any other uri, `read`, `subscribe` and `unsubscribe` each fail with an invalid-params error. The `read` reads `as_of_seq` in a worker thread; a `StoreError` there fails that one request with an internal-error response naming the error, and the server keeps serving. After each channel event the watcher sends `notifications/resources/updated` for `amoeba://inbox` if the flag is set, and not otherwise, because the spec has a server notify only clients that subscribed. Observed 20261114 (architecture): none of Claude Code, Codex CLI, Gemini CLI or Cursor subscribes, so today the update reaches no one. Any client that subscribes gets it, whether or not it acts on it, which is the PM's direction to send a useful signal even where clients ignore it.

### D6 — Sessions: register, heartbeat, exit
Status: decided

Migration `007_sessions.sql`, create-only:

`sessions`: `session_id` (text primary key), `member_id` (references `members`), `client`, `directory`, `started_at`, `heartbeat_at`, `push_confirmed_at` (null until confirmed). Indexes on `(member_id)` and `(heartbeat_at)`. No `CHECK` list, so no enum to pin. `EXPECTED_SCHEMA_VERSION` becomes 7.

- **Register and beat are one statement.** An upsert on `session_id` sets `heartbeat_at` and `push_confirmed_at` (from memory, null until confirmed) and, on a first insert, the other columns. The first beat runs at `initialized`; then every `session_heartbeat_seconds`. A failed beat (`StoreBusyError`) is retried at the next beat; so is a row a heartbeat pruned from a process that was suspended past the stale limit, which the upsert re-creates with the original `started_at`.
- **`client`** is the client's `clientInfo.name` if it matches `[A-Za-z0-9._ -]{1,64}`; otherwise the placeholder `unrecognized`, and one WARNING. It is displayed by `list`, so it is never free text. `directory` is the process's working directory.
- **Clean exit** deletes the row, under a shield and a bound of `BUSY_TIMEOUT_SECONDS * 2`. On SIGKILL, a crash or a SIGTERM (not handled; the client closes stdin first) the row stays.
- **Stale rule.** A row whose `heartbeat_at` is older than `session_stale_seconds` counts as gone. `LIVE_SESSION` is the one predicate, used by `live_sessions`, `live_member_ids` and the prune. A stale row is therefore never shown, whether or not it has been pruned.
- **Prune.** `prune_stale_sessions` runs in each heartbeat's write transaction, before the upsert, so every serving process clears every member's dead rows every `session_heartbeat_seconds`, and a server starting clears them at its first beat. 240's `sweep` is not touched: 241 owns the whole cleanup. The table therefore holds the live rows plus the rows of servers killed since the last beat of any server. With no server running, those rows stay until one starts; they are bounded by the number of kills in that time, each is a few dozen bytes, and the stale rule means none is ever shown.
- **Push confirmation.** "Live" for waking means a session whose agent acts on push (244 consumes it through `live_member_ids`). When the watcher attempts a channel event and no event is waiting for an answer, it records the attempt time in memory. When `call_tool` completes an `inbox` call without error, it calls `note_inbox_called`: if an attempt is recorded and is at most `PUSH_ANSWER_SECONDS` old (a constant, 300: a queued event waits for the agent's current turn to end), the session becomes push-confirmed; either way the recorded attempt is cleared. Confirmation is in memory and sticky for the process (the launch flag cannot change mid-session), and the next beat's upsert writes `push_confirmed_at`, so no new write path exists. An unanswered attempt older than the limit is cleared by the next event, which records a fresh attempt.
  - `live_sessions` (for `list`) returns every fresh row with its `push_confirmed_at`. `live_member_ids(transaction, now, stale_seconds)` returns members with a fresh row whose `push_confirmed_at` is set. Both use `LIVE_SESSION`; the second adds `push_confirmed_at IS NOT NULL`, once, in `store/sql_sessions.py`.
  - The common case works: an idle session without the flag, under `claude -p`, or in an org with channels off never answers an event, so it never confirms and the repo is woken. An idle session with the flag answers its first event within seconds and from then on suppresses waking, which is right because push reaches it.
  - Two rare misreads, each with a bounded cost and no new mechanism. A push session that has not yet received an event is unconfirmed, so the first request to its repo can also wake an agent; both see the request, and the second to accept gets `already_accepted` (240), with wakes capped by 244's daily limit. An unflagged session whose agent happens to call `inbox` within the limit after an attempted event confirms falsely and suppresses waking like a live session; the request waits for that agent or its TTL, and `list` shows the session as push-confirmed and the request's age, and `amoeba cancel` ends it.
- Rejected: a pid column (a pid proves nothing after reuse, and the heartbeat already says whether the process lives).

### D7 — Config keys
Status: decided

`notify_poll_seconds`, `session_heartbeat_seconds` and `session_stale_seconds`, each a number greater than 0, required, no default in code (as 240 D12). A model-level check makes `session_stale_seconds` at least twice `session_heartbeat_seconds`, so one missed beat does not read as gone, and `session_heartbeat_seconds` at least `notify_poll_seconds`, because the architecture has the heartbeat less often than the push check. Each failure names both keys. The suggested values, 5, 30 and 90, appear once, in the config contract's example, and a test loads that example. The live config gets the keys in the live-store step.

### D8 — `list` and `status`
Status: decided

`MemberStatus` gains `sessions`: each live session's `client`, `directory`, `started_at`, `heartbeat_at` and `push_confirmed_at`, ordered by `started_at` then `session_id`. The text renderer adds a **Live sessions** section per member that has any: `<client>  <directory>  up <age>  last beat <age> ago  push confirmed|push unconfirmed`, so the PM can see which sessions hold off waking. A member with none shows no section. Sessions do not count as "waiting on you", so `Nothing needs you.` is unchanged. They are not other repos' text, so they do not set the notice (240 D11). `list -j` still equals the `status` document.

### D9 — Launch, registration and docs
Status: decided

What is decided is the order of forms and the `BLOCKED:` stop below. Which form is adopted is the output of step 1 of the Development Approach.

**Observed 20261116 (Claude Code 2.1.318, then 2.1.325; task 1.2).** The project `.mcp.json` form registers the channel: a throwaway server declaring `experimental["claude/channel"]` sent one `notifications/claude/channel` event (`content`, `meta`) after `initialized`, the session showed `← <server>: <content>`, and the model called that server's tool with nothing typed. The client opened with a `server/discover` probe for 2026-07-28 and, answered `Method not found`, sent `initialize` at 2025-11-25 (D1). It is adopted; `--mcp-config` and the user-scope install were not needed and were not tried. Start-up screens appear in this order: folder trust ("Quick safety check", default "No, exit"), project-server consent ("New MCP server found in this project: <name>", default "Continue without using this MCP server"), then the development-channel warning (default "I am using this for local development"). The channels reference (read 20261116) agrees with D4 and this section; no correction to them.

**Registration.** For each repo that should get push, a project `.mcp.json` naming `amoeba-mcp`, written by `claude mcp add --scope project amoeba -- amoeba-mcp` run in the repo (an agent in the repo commits it, as it does the rules blocks). This is the one form the channels reference documents for `server:<name>` ("a bare `.mcp.json` server"). Neither the channels reference nor the CLI reference says whether `server:amoeba` also names a user-scope server, so the design does not rely on it. The existing user-scope install (`claude mcp add --scope user`) stays for sessions that do not want push; both use the name `amoeba`, so a session loads one server.

**Launch.** The flag is `--dangerously-load-development-channels server:amoeba`, and the docs give it as an alias, `alias claude-amoeba='claude --dangerously-load-development-channels server:amoeba'` (the name is the operator's choice). The docs also state: an interactive session is required (the flag is ignored under `-p`); Claude Code shows a confirmation screen at start, and a consent screen the first time it sees a project server; on Team and Enterprise plans an admin must enable channels (`channelsEnabled`), otherwise events are dropped and polling still works; and `tests/live/channels` is to be re-run after a Claude Code update, since channels are a research preview. The first step of the Development Approach runs the registration against the installed Claude Code before anything is built on it. It tries three forms in this order and D9 and the docs adopt the first that registers the channel: the project `.mcp.json`; the server given to the alias with `--mcp-config <file>` (the CLI reference documents it as loading servers from JSON files); the user-scope install. If none registers it, push cannot work on this Claude Code, so that task takes a `BLOCKED:` line with the screens seen and the slice stops there; nothing later is built on a form that does not work.

### D10 — The live test
Status: decided

`tests/live/channels` drives a real interactive `claude --dangerously-load-development-channels server:amoeba` in a pseudo-terminal (`pty`, standard library), with a throwaway `AMOEBA_HOME`, two fixture repos through the real `cf`, and a launcher script that runs `amoeba-mcp` with its stderr appended to a file. The receiving fixture repo carries a `.mcp.json` of the D9 form, naming the launcher as its command.
- The harness answers each known start-up screen (development-channel warning, folder trust, MCP server consent) by matching its text, and fails with the last screen contents when a screen is unknown or the next one does not appear within `STARTUP_SCREEN_WAIT_SECONDS` (60). The wait for `tool inbox called` is `INBOX_CALL_WAIT_SECONDS` (120: one poll interval plus a model turn), and the wait for a killed server's row to read as gone is `session_stale_seconds` plus `STALE_MARGIN_SECONDS` (5). Each is a constant in the harness module and each failure reports what the test was waiting for and the last screen.
- The model comes from a required live setting (`AMOEBA_LIVE_CHANNEL_MODEL`, as the other live tiers' model settings), and the `inbox` tool is pre-allowed for the session.
- Claude Code's login is held per config directory (a throwaway `CLAUDE_CONFIG_DIR` starts logged out, observed 20261116), so the session uses the operator's Claude config with `--setting-sources project,local`: the operator's user settings (hooks, permission mode) do not apply, and the consent screen shows as it does for an operator. The server is registered only in the fixture directory. The only write to the operator's config is Claude Code's own folder-trust record for each throwaway directory. `DISABLE_AUTOUPDATER=1` keeps a test run from updating the installed Claude Code (an unguarded run updated 2.1.318 to 2.1.325).
- Evidence is the server's stderr, which gains three INFO lines: the negotiated protocol version and client name at `initialized`; `channel event attempted` with `first_seq`, `last_seq` and `count` (a diagnostic; the test's proof of delivery is the next line); and `tool <name> called` at the start of every tool call (the name only). The test sends a request from the other repo with `amoeba send`, then waits for `tool inbox called` with no prompt typed.
- The config uses short intervals (`notify_poll_seconds` 1, `session_heartbeat_seconds` 1, `session_stale_seconds` 3) and three sessions run in turn:
  - In member repo `cf-s` (with the D9 `.mcp.json`): `amoeba list -j` shows a live session under `cf-s` with its directory. The test sends a request from `sq-s` with `amoeba send --to cf-s --id sq-1 --subject "Need X" --body "Please add X"`, and the server log gets `tool inbox called` with no prompt typed. Within `session_heartbeat_seconds` plus `STALE_MARGIN_SECONDS`, `amoeba list -j` shows that session with `push_confirmed_at` set. After a clean exit, `amoeba list -j` shows no session.
  - The same session with the server killed by SIGKILL: `list -j` shows no session once the wait above has passed.
  - A directory outside any member: the server log says it is not a member, `list -j` shows no session, and a tool call still answers.
- Spend is pre-authorized for live tiers.

### Departures from the parent documents
The docs step amends the architecture and plan entry so none stays a difference.
- A `directory` column on `sessions` (D6).
- No code defaults for the three keys (D7), as 240 D12.
- `sessions` in migration 7, not the architecture's schema 6 migration (D6). Of the architecture's four tables, 240's migration 6 creates `messages` and `deliveries` (and `message_rejections`, which 240 adds itself), and the plan gives `sessions` here and `wakes` to 244 their own migrations, 7 and 9. The architecture's "Store and config" paragraph is amended for `sessions`.
- A non-member server declares the channel and resources capabilities (D3).
- The event tells the agent to use its own cursor, not "call `inbox` with `since`" (D4).
- The serve loop is `serve_pinned`, not `server.run`, and the watcher runs beside it, not beside `server.run` as the plan and architecture say. The protocol pin is that loop choice, not "the SDK's version negotiation" (D1).
- Stale sessions are pruned by every server's heartbeat, not by the sweep (D6). 240's sweep is unchanged.
- Presence feeds waking only through push-confirmed sessions (D6): a session suppresses a wake once its agent has answered a channel event, and `list` shows every serving session with whether it is confirmed. The architecture's presence paragraph and its walkthrough step 3 are amended to say so.
- The live-store migration runs in the Phase 7 hand-off, after the merge, not in Phase 6: migrating the live store before the merge would leave the installed tool refusing it.
- A rehearsal of that migration on a copy of the live store and config (task 13.1) precedes it.

## Implementation Details

### Database / Storage Schema

As D6. The migration only creates a table and its indexes, so existing rows are untouched and `foreign_key_check` finds nothing. Downgrade is refused by the existing newer-schema guard.

### API Contracts

No new tool. Protocol surface added to `amoeba-mcp`:

| Surface | Detail |
|---|---|
| Capability | `experimental: {"claude/channel": {}}`; `resources: {subscribe: true}` |
| Notification | `notifications/claude/channel` with `content` and `meta` (`first_seq`, `last_seq`, `count`) |
| Notification | `notifications/resources/updated`, `uri: amoeba://inbox`, to a client that subscribed |
| Resource | `amoeba://inbox`, `application/json`, `{"member", "as_of_seq"}` |
| Config | `notify_poll_seconds`, `session_heartbeat_seconds`, `session_stale_seconds` |
| `list`/`status` JSON | `sessions` per member |

## Integration Points

### Provides to Other Slices
- **243:** nothing to change. A note is a delivery, so the same check pushes it; the event names the kind. 243's criterion "push fires for a note" is a test over this path.
- **244:** `live_member_ids(transaction, now, stale_seconds)`, the one liveness rule for waking, and the `sessions` table. A member is live when it has a fresh, push-confirmed session (D6). A session without the flag, under `claude -p`, or not yet sent an event does not count, so its repo is woken.

### Consumes from Other Slices
- **240:** the tables and functions under Interfaces Required. If `cf` fails at start, the server serves tools with no push (D3). If the store is held, the watcher skips the tick (D2).

## Success Criteria

### Functional Requirements
- The live test: an interactive Claude Code session started with the development flag, sent a request from another fixture repo, calls `inbox` with no prompt from the test.
- The negotiated protocol in that session is a handshake version, and the protocol-pin test passes: probe answered `Method not found`, `initialize` served. Every existing MCP tool test still passes.
- The channel event is as D4 says: a test builds events from rows whose text fields hold marker strings and checks that none appears, and checks `first_seq`, `last_seq`, `count` and the `K more` cap.
- A server started in a directory outside any member serves the tools, writes no session row, runs no push loop, and returns an empty `resources/list`. A `cf` failure or timeout at start does the same and logs the error.
- The resource handlers behave as D5 says, tested in each state: a request made while the member is still resolving waits and then gets the resolved answer; a subscribed client gets `notifications/resources/updated` after an event and one that did not gets none; the invalid-params and `StoreError` cases fail only their request.
- The watcher's failures behave as D2 says: a busy store is retried, after which the next event is sent and the row is current; any other error is logged with its traceback, ends presence and deletes the row, and the server keeps answering tool calls. A send on a closed stream does not raise, which pins `Connection.notify` (D2).
- A clean exit deletes the row. A server killed with SIGKILL leaves a row that `list` stops showing after `session_stale_seconds`, and the next heartbeat of any server deletes.
- Push confirmation behaves as D6 says: an `inbox` call within `PUSH_ANSWER_SECONDS` of an attempted event confirms the session and the next beat writes `push_confirmed_at`; an `inbox` call with no attempt recorded, or after the limit, does not; `live_member_ids` returns a member with a fresh confirmed row and not one whose only rows are unconfirmed or stale.
- A process suspended past the stale limit has its row re-created by the next heartbeat.
- The watcher never blocks a tool call: with a store opener that blocks in its thread, `ping`, `tools/list` and a tool call answer within a second.
- `list` and `status` show live sessions per member; `list -j` equals the `status` document; `Nothing needs you.` is unchanged.

### Technical Requirements
- The three keys missing fail with `ConfigError` naming the key; a stale limit under twice the heartbeat, or a heartbeat under the poll interval, fails naming both keys; the config contract's example loads.
- Every table, column, JSON field and config key is documented; `tests/test_contract_docs.py`, `tests/test_import_boundaries.py`, `tests/test_store_opened_only_by_state_move.py` and `tests/test_read_side_defined_once.py` pass.
- `sessions` has a cleanup, with a test: stale rows pruned by another process's heartbeat, live rows kept.
- `ruff format`, `ruff check`, `pyright` and the whole suite pass.

### Integration Requirements
- 244 can call `live_member_ids` and get the same answer `list` shows.
- 243's notes push with no change to this slice.
- 240's behavior is unchanged: 241 edits no 240 function or signature, and 240's tests pass as written.

### Verification Walkthrough

Refined at the end of Phase 6 (20261116, Claude Code 2.1.325, mcp 2.3.0). Every step runs unattended from the repo root. Step 3 uses throwaway Amoeba and Context Forge homes, the real `cf`, and the Claude Code login of the operator's own config (a throwaway Claude config directory has no login; D10).

1. Checks:
   ```
   uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest -q
   ```
   Expected: `... files already formatted`, `All checks passed!`, `0 errors, 0 warnings, 0 informations`, and `N passed` with no failure (3378 at the end of Phase 6). The bare run includes `tests/load/test_presence_load.py` (12 presences on one store) and the real-stdio exit tests in `tests/mcp_server/test_presence_stdio.py`.
2. Protocol pin:
   ```
   uv run pytest tests/mcp_server/test_protocol_pin.py -v
   ```
   Expected: 3 passed. `test_the_pinned_loop_refuses_the_probe_and_serves_the_handshake` (probe answered -32601, `initialize` served at a handshake version), `test_server_run_answers_the_probe_and_then_refuses_the_handshake` (the contrast: `supportedVersions` then -32022), and the background-cancellation test.
3. Live tier, with the live settings in the environment (the pause tier's three `AMOEBA_LIVE_*` variables, which the repo's `.env` holds, plus the session model):
   ```
   set -a; source .env; set +a
   AMOEBA_LIVE_CHANNEL_MODEL=sonnet uv run pytest tests/live/channels -v
   ```
   Expected: 4 passed in about a minute: the throwaway-home check, session one (push reaches the agent with nothing typed, `tool inbox called` in the server log, `push_confirmed_at` in `list -j`, no session after a clean exit), the killed server going stale, and session three (non-member: no session, a prompted `list` call answers). A missing variable fails collection naming it. A failure prints what it waited for and the last screen. Caveat: the first time Claude Code sees each throwaway directory it records folder trust in the operator's Claude config; nothing else there is written.
4. Live store: the Phase 7 hand-off, `uv run python scripts/update_live.py update` after the merge (Special Considerations); task 13.1 rehearses the migration on a copy first.

## Risk Assessment

### Technical Risks
- Push rests on a research-preview Claude Code feature: the flag, the capability, the notification shape and the handshake behavior can change in an update.
- The pinned loop composes SDK modules that are public but low-level, and `Server.run` is what most code uses.
- A pseudo-terminal test of an interactive program can be brittle across start-up screens.

### Mitigation Strategies
- The live test and the pin test are the detectors, and the docs say to re-run them after a Claude Code or SDK update. When push breaks, polling still delivers (architecture, walkthrough step 9).
- `pyproject` bounds the SDK at `<3`; the pin test fails first on a behavior change.
- The harness matches screen text, not positions, and fails with the screen it saw.

## Implementation Notes

### Development Approach
1. Re-check the dated facts against the installed Claude Code and SDK (flag, capability, notification shape, and that the D9 `.mcp.json` registration registers the channel); correct D4, D9 and the docs where they differ. Build the pty harness enough to start a session and read its screens.
2. Config keys; migration 7, `store/sessions.py`, `store/push_reads.py`, and their tests.
3. `pinned_loop.py` and `test_protocol_pin.py`; move `server.py` onto it; the existing MCP tests must pass.
4. `channel_event.py`, `inbox_watcher.py`, `presence.py`, `inbox_resource.py` with in-process tests (memory streams, SDK client, injected opener and short intervals).
5. `SessionEntry`, `list`/`status` and the renderer.
6. Docs, `INSTRUCTIONS`, the departures' wording in the architecture and plan.
7. The live test. The live-store migration is the Phase 7 hand-off, after the merge (Special Considerations).

### Special Considerations
- **Prompt injection.** The event is text the model reads as a user turn. It holds only enums, numbers and Context Forge ids, never another agent's words (D4).
- **Spend.** The live test makes real model calls on the configured model.
- **Live store (designated for migration; backup first).** One step, in the Phase 7 hand-off from the target checkout after the merge: `uv run python scripts/update_live.py update`. It backs up the live store and config, appends any config key the new code requires (value from the config contract's example), installs the target, migrates through `amoeba list`, reads back the schema version, integrity, foreign keys, member count and the installed `amoeba-mcp` tool list, and on any failure restores the backup and reinstalls the previously installed commit itself. Client sessions it lists are restarted afterwards (they run the old `amoeba-mcp` until then). `uv run python scripts/update_live.py restore` puts the newest backup back later. Task 13.1 rehearses the migration on a copy first.

## Operator Walkthrough

Done as the person running it.

- **Migration (once, by the implementing agent, in the Phase 7 hand-off).** The live-store step in Special Considerations, then the restart of client sessions.
- **Start.** In each repo that should get push, run `claude mcp add --scope project amoeba -- amoeba-mcp` and have an agent commit the `.mcp.json`. Start Claude Code with the alias and accept the start-up screens. `amoeba list` shows the session under its repo.
- **Normal path.** A request arrives, the session shows the `← amoeba` line and calls `inbox`.
- **No flag, an org with channels off, or `claude -p`.** The server runs and shows in `list`. Events are dropped by the client, and the agent polls at its rules-file moments. Nothing is lost.
- **A non-member directory, or a repo added after the session started.** No session row. `amoeba add`, then `/mcp` reconnect or a new session.
- **Session closed.** The row is deleted at once. **Session killed.** The row reads as gone after `session_stale_seconds`, and the next heartbeat of any server deletes it; nobody edits anything.
- **Computer asleep.** The heartbeat stops; on wake the next beat re-creates the row.
- **Store locked.** The tick is skipped and retried. Tools answer meanwhile.
- **A Claude Code update changes channels.** `uv run pytest tests/live/channels` fails with the screen it saw; polling still works until the docs and code are updated.
- **A repo that should show a live session does not.** The reason is the server's stderr line (not a member, `cf` failed, or a store error with its traceback). `claude --debug` writes it to `~/.claude/debug/<session-id>.txt` (channels reference, read 20261115). Fix the cause (`cf` on `PATH`, `amoeba add`), then `/mcp` reconnect.
- **An idle session in a repo with a wake command.** Without push it never confirms, so a request wakes the repo (244). With push, the event starts a turn and the session confirms; until its first event, a request can both push to it and wake an agent, and the second to accept gets `already_accepted`. `list` shows which sessions are push-confirmed.
- **Undo.** To stop using push, remove the alias and run `claude mcp remove amoeba --scope project` in the repo. The only state is `sessions` rows: live ones plus killed servers' rows until the next beat of any server (D6). Until the next update, `uv run python scripts/update_live.py restore` puts back the pre-241 store and config from the hand-off's backup (Special Considerations). Past that, the schema is deliberately forward-only: `sessions` is harmless when unused (empty once sessions end), and older code refuses a store stamped 7. Going back to pre-241 code would take, with every `amoeba` and `amoeba-mcp` process stopped, `DROP TABLE sessions` and `schema_meta.version` set to 6 on the live store, which needs the PM's explicit designation under the project rule; it loses only live-session records. Dead ends found: that one, by design.
