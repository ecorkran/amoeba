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
dateUpdated: 20261115
status: not_started
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

`amoeba-mcp` tells its own client session when new mail arrives, and records that it is serving. The server resolves its member once, from its working directory. A watcher beside the MCP loop reads the member's highest delivery sequence number every `notify_poll_seconds`. When it rises, the server sends a Claude Code channel event, and a resource update on `amoeba://inbox` to a client that subscribed. Neither carries message text. Each serving process also keeps a `sessions` row (migration 7), so `list` shows who is live where. Today `server.run` serves the 2026-07-28 protocol era, which Claude Code will not register a channel on, so this slice replaces it with a handshake-only loop. The slice proves the whole path against a real interactive Claude Code session.

## Value

User value. A live Claude Code session acts on a request when it arrives, not at its next rules-file moment. The PM sees which repos have a live agent, in `list`. Architecturally, the slice provides the `sessions` table and `live_member_ids` that 244 (waking) reads, and the push path that 243's notes use unchanged.

## Technical Scope

**Included**
- A handshake-only serve loop for `amoeba-mcp`, replacing `server.run` (D1).
- The watcher: member resolution, the push check, the channel event, the resource update (D2 to D5).
- The `amoeba://inbox` resource: list, read, subscribe (D5).
- Migration 7: `sessions`. Registration, heartbeat, clean-exit delete, the stale rule, and its pruning in 240's sweep (D6).
- Three required config keys: `notify_poll_seconds`, `session_heartbeat_seconds`, `session_stale_seconds` (D7).
- `list` and `status` show live sessions per member (D8).
- Docs: the launch flag and shell alias, the registration form, `mcp-server.md`, `config-contract.md`, `store-contract.md`, `cli-contract.md`; the `INSTRUCTIONS` text (D9).
- An automated live test against a real interactive Claude Code session in a pseudo-terminal (D10).
- Live store backed up, migrated to 7, config keys added, read back.

**Excluded**
- Message operations, the delivery writer and the sweep's message steps (240). Notes (243). Waking (244).
- Push for clients other than Claude Code: they get the resource update only if they subscribe, and none did when observed 20261114 (architecture).
- Push under `claude -p`: Claude Code ignores the development flag there, so pipeline runs poll.
- Detecting whether the client registered the channel. Claude Code gives the server no signal either way, so a session row means "an `amoeba-mcp` is serving", not "push is on".

## Dependencies

### Prerequisites
- 240 built and integrated: `deliveries` with its `(member_id, seq)` index, the `sweep` and `sweep_messages` functions, `StatusResult`/`MemberStatus` with `requests`, `inbox` and the live store at schema 6.
- Claude Code installed and logged in, for the live test only. Observed 20261115: 2.1.318.
- `mcp>=2.3,<3`. Observed 20261115: 2.3.0.

### Interfaces Required
- From 240: `deliveries(seq, member_id, message_id, event, created_at)`, `messages(from_member, to_member, kind)`, `highest_assigned_seq(transaction)` (the number `inbox` returns as `as_of_seq`), `sweep(...)`, `sweep_messages(store, config, now)`, `MemberStatus`.
- From 220: `operations.members.resolve_member` (the directory-to-member rule), `wiring.open_store` (the only way the store is opened; `tests/test_store_opened_only_by_state_move.py`), `wiring.default_deps` for `cf_run`, `Deps.clock`.
- From the MCP SDK (2.3.0): `Connection.for_loop`, `Connection.notify`, `Connection.initialized`, `serve_connection` and `JSONRPCDispatcher`. These are public modules, not the top-level API; D1 pins their behavior with a contract test.

## Architecture

### Component Structure

```
amoeba-mcp main ──► mcp/pinned_loop.py ──► serve_connection (handshake-only)
                         │
                         └─ task group ─► mcp/presence.py     member, session row, heartbeat
                                          mcp/inbox_watcher.py push check ─► mcp/channel_event.py
                                          mcp/inbox_resource.py resources/list|read|subscribe
                                                  │
                         store/sessions.py · store/sql_sessions.py · store/push_reads.py
```

- `mcp/pinned_loop.py`: `serve_pinned(server, streams, init_options, background)`. Builds the dispatcher and `Connection.for_loop`, starts `background(connection)` in a task group, runs `serve_connection`, cancels the background on return. It mirrors the SDK's `serve_loop` (which does not expose its connection) and nothing else.
- `mcp/presence.py`: `PresenceState` (member id or none, set once, read by the resource handlers), `resolve_presence` (D3) and the heartbeat loop (D6).
- `mcp/inbox_watcher.py`: the push loop (D2).
- `mcp/channel_event.py`: a pure function from push rows to the event's params (D4). No I/O, so a test checks every field.
- `mcp/inbox_resource.py`: the three resource handlers (D5).
- `store/sessions.py`: `upsert_session`, `delete_session`, `prune_stale_sessions`, `live_sessions`, `live_member_ids`, with one `LIVE_SESSION` predicate constant in `store/sql_sessions.py`. `store/push_reads.py`: `member_high_seq` and `push_rows_after`. Rows are frozen dataclasses in `store/models.py` (`Session`, `PushRow`). The store imports nothing from `operations` or `mcp`.
- `operations/status_models.py`: `SessionEntry`; `MemberStatus` gains `sessions`.
- Each file stays near 300 lines. `server.py` (221 lines) only swaps `server.run` for `serve_pinned` and adds the capabilities and handlers.

### Data Flow

**Start.** `main` runs its existing checks, then `serve` opens stdio and calls `serve_pinned`. The handshake never waits on `cf` or SQLite: the background task does that work in worker threads (`anyio.to_thread`).

**Watcher.** The background task has one top-level handler (D2). Inside it: resolve the member (one `cf` call in a thread, bounded by `CF_GET_TIMEOUT_SECONDS`). If it is none, log one line and return: no row, no loop. Otherwise wait on `connection.initialized`, read the client's name, and run the heartbeat loop and the push loop in one child task group. The push loop takes its baseline (`member_high_seq`), retrying each tick until the read succeeds and sending nothing before it has one. Then every `notify_poll_seconds` it reads again. When the value is higher than the last seen, it reads the new rows (`push_rows_after`), builds the event, sends the channel event, and sends the resource update if the client subscribed (D5). The new value becomes the last seen.

**Exit.** However the background task ends, a shielded, bounded `DELETE` removes the session row. It ends when the client closes stdin (`serve_connection` returns and the background is cancelled), or when the watcher stops on an error (D2).

### State Management

- In memory: the resolved member, the last-seen sequence number, the session id (`uuid4().hex`, made once at start), the start time. Only the event loop's tasks touch them. `PresenceState` is read by the resource handlers, which run as soon as `initialize` is answered, before the member is known. It has three states: pending, a member, or off with a reason. It carries a `resolved` event that the background task sets in a `finally`, so the pending state always ends, at the latest after the lookup's own bounds (D3).
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
- `Connection.notify` never raises: a send to a closed stream is dropped with a debug log (read in `mcp/server/connection.py`, 2.3.0, and unproven until the notify test in the success criteria exists). That happens only when the client's end is closed, and `serve_connection` returns right after, so nothing retries. The INFO line for an event therefore says `channel event attempted`, and does not claim delivery.
- A baseline taken after the member resolves can miss mail that arrived between the agent's first `inbox` call and that moment, a window of one `cf` call. Polling covers it.
- Push fires on deliveries. An expiry becomes a delivery when a sweep records it (240 D6), so an expiry no write or `list` has swept is seen at the next poll, not pushed.

### D3 — The member is resolved once, in the background task
Status: decided

`resolve_member(store, Path.cwd(), cf_run)` runs once, in a worker thread, after the handshake. Claude Code starts a stdio server in the session's project directory.
- A `Member`: presence and push for it.
- `NotInProgram` or `NotAProject`: the server serves its tools exactly as today. One INFO line says the directory is not a member. No row, no loop. After `amoeba add` in that repo, the exit is reconnecting the server (`/mcp`) or starting a new session.
- `ContextForgeError`, or a `StoreError` in the lookup: the same as not a member, through D2's top-level handler (`logger.exception`, no row, no loop). The `cf` call is bounded by `CF_GET_TIMEOUT_SECONDS` (30 s): `run_cf` returns a timeout as a `CfCallFailed` value, and `resolve_member` raises it as `ContextForgeError`. The tools still work, and `list` shows the repo with no live session. The exit is reconnecting (`/mcp`) or a new session.
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

`sessions`: `session_id` (text primary key), `member_id` (references `members`), `client`, `directory`, `started_at`, `heartbeat_at`. Indexes on `(member_id)` and `(heartbeat_at)`. No `CHECK` list, so no enum to pin. `EXPECTED_SCHEMA_VERSION` becomes 7.

- **Register and beat are one statement.** An upsert on `session_id` sets `heartbeat_at` and, on a first insert, the other columns. The first beat runs at `initialized`; then every `session_heartbeat_seconds`. A failed beat (`StoreBusyError`) is retried at the next beat; so is a row the sweep pruned from a process that was suspended past the stale limit, which the upsert re-creates with the original `started_at`.
- **`client`** is the client's `clientInfo.name` if it matches `[A-Za-z0-9._ -]{1,64}`; otherwise the placeholder `unrecognized`, and one WARNING. It is displayed by `list`, so it is never free text. `directory` is the process's working directory.
- **Clean exit** deletes the row, under a shield and a bound of `BUSY_TIMEOUT_SECONDS * 2`. On SIGKILL, a crash or a SIGTERM (not handled; the client closes stdin first) the row stays.
- **Stale rule.** A row whose `heartbeat_at` is older than `session_stale_seconds` counts as gone. `LIVE_SESSION` is the one predicate, used by `live_sessions`, `live_member_ids` and the prune. A stale row is therefore never shown, whether or not it has been pruned.
- **Prune.** 240's `sweep` gains a third step and a parameter: `sweep(transaction, now, prune_after_days, session_stale_seconds)` deletes stale rows. This is this slice's change, not 240's, because `sessions` does not exist until migration 7, so 240's sweep cannot hold the step. The plan runs 240 first, so the edit lands on the sweep as built: its three write callers (`send`, `reply`, `cancel`) and `sweep_messages` (for `list`, `status` and `handle_pause`) pass `session_stale_seconds` from the config they already hold, and 240's tests must pass with it. `sweep_messages`'s "is something due" read counts a stale row as due, so a quiet store is still not write-locked by a poll. The same `prune_stale_sessions` also runs in each heartbeat's write transaction, so a server starting clears the dead rows too. The table therefore holds live rows plus the rows of killed servers since the last server start or sweep. Stale rows are never shown (the stale rule), and each is a few dozen bytes.
- Rejected: a pid column (a pid proves nothing after reuse, and the heartbeat already says whether the process lives).

### D7 — Config keys
Status: decided

`notify_poll_seconds`, `session_heartbeat_seconds` and `session_stale_seconds`, each a number greater than 0, required, no default in code (as 240 D12). A model-level check makes `session_stale_seconds` at least twice `session_heartbeat_seconds`, so one missed beat does not read as gone, and `session_heartbeat_seconds` at least `notify_poll_seconds`, because the architecture has the heartbeat less often than the push check. Each failure names both keys. The suggested values, 5, 30 and 90, appear once, in the config contract's example, and a test loads that example. The live config gets the keys in the live-store step.

### D8 — `list` and `status`
Status: decided

`MemberStatus` gains `sessions`: each live session's `client`, `directory`, `started_at` and `heartbeat_at`, oldest first. The text renderer adds a **Live sessions** section per member that has any: `<client>  <directory>  up <age>  last beat <age> ago`. A member with none shows no section. Sessions do not count as "waiting on you", so `Nothing needs you.` is unchanged. They are not other repos' text, so they do not set the notice (240 D11). `list -j` still equals the `status` document.

### D9 — Launch, registration and docs
Status: decided

What is decided is the order of forms and the `BLOCKED:` stop below. Which form is adopted is the output of step 1 of the Development Approach; until it runs, the project `.mcp.json` is the working assumption.

**Registration.** For each repo that should get push, a project `.mcp.json` naming `amoeba-mcp`, written by `claude mcp add --scope project amoeba -- amoeba-mcp` run in the repo (an agent in the repo commits it, as it does the rules blocks). This is the one form the channels reference documents for `server:<name>` ("a bare `.mcp.json` server"). Neither the channels reference nor the CLI reference says whether `server:amoeba` also names a user-scope server, so the design does not rely on it. The existing user-scope install (`claude mcp add --scope user`) stays for sessions that do not want push; both use the name `amoeba`, so a session loads one server.

**Launch.** The flag is `--dangerously-load-development-channels server:amoeba`, and the docs give it as an alias, `alias claude-amoeba='claude --dangerously-load-development-channels server:amoeba'` (the name is the operator's choice). The docs also state: an interactive session is required (the flag is ignored under `-p`); Claude Code shows a confirmation screen at start, and a consent screen the first time it sees a project server; on Team and Enterprise plans an admin must enable channels (`channelsEnabled`), otherwise events are dropped and polling still works; and `tests/live/channels` is to be re-run after a Claude Code update, since channels are a research preview. The first step of the Development Approach runs the registration against the installed Claude Code before anything is built on it. It tries three forms in this order and D9 and the docs adopt the first that registers the channel: the project `.mcp.json`; the server given to the alias with `--mcp-config <file>` (the CLI reference documents it as loading servers from JSON files); the user-scope install. If none registers it, push cannot work on this Claude Code, so that task takes a `BLOCKED:` line with the screens seen and the slice stops there; nothing later is built on a form that does not work.

### D10 — The live test
Status: decided

`tests/live/channels` drives a real interactive `claude --dangerously-load-development-channels server:amoeba` in a pseudo-terminal (`pty`, standard library), with a throwaway `AMOEBA_HOME`, two fixture repos through the real `cf`, and a launcher script that runs `amoeba-mcp` with its stderr appended to a file. The receiving fixture repo carries a `.mcp.json` of the D9 form, naming the launcher as its command.
- The harness answers each known start-up screen (development-channel warning, folder trust, MCP server consent) by matching its text, and fails with the last screen contents when a screen is unknown or the next one does not appear within `STARTUP_SCREEN_WAIT_SECONDS` (60). The wait for `tool inbox called` is `INBOX_CALL_WAIT_SECONDS` (120: one poll interval plus a model turn), and the wait for a killed server's row to read as gone is `session_stale_seconds` plus `STALE_MARGIN_SECONDS` (5). Each is a constant in the harness module and each failure reports what the test was waiting for and the last screen.
- The model comes from a required live setting (`AMOEBA_LIVE_CHANNEL_MODEL`, as the other live tiers' model settings), and the `inbox` tool is pre-allowed for the session.
- Evidence is the server's stderr, which gains three INFO lines: the negotiated protocol version and client name at `initialized`; `channel event attempted` with `first_seq`, `last_seq` and `count` (a diagnostic; the test's proof of delivery is the next line); and `tool <name> called` at the start of every tool call (the name only). The test sends a request from the other repo with `amoeba send`, then waits for `tool inbox called` with no prompt typed.
- The config uses short intervals (`notify_poll_seconds` 1, `session_heartbeat_seconds` 1, `session_stale_seconds` 3) and three sessions run in turn:
  - In member repo `cf-s` (with the D9 `.mcp.json`): `amoeba list -j` shows a live session under `cf-s` with its directory. The test sends a request from `sq-s` with `amoeba send --to cf-s --id sq-1 --subject "Need X" --body "Please add X"`, and the server log gets `tool inbox called` with no prompt typed. After a clean exit, `amoeba list -j` shows no session.
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
- `sweep` gains a parameter (D6).
- "Live" means an `amoeba-mcp` is serving for the member, not that someone is working there. The architecture's presence paragraph and its walkthrough step 3 are amended to say so. An idle session left open, with or without the flag, counts as live, so a request to that repo is not woken (244) and waits for its agent or its TTL, when it expires and the sender is told. A repo with no session at all, the case waking is for, is woken. Refining the rule would need a signal that the agent reads mail, and Claude Code gives the server none.

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
- **244:** `live_member_ids(transaction, now, stale_seconds)`, the one liveness rule, and the `sessions` table. "Live" is as the departures define it: serving, not attentive. An idle session, one without the flag, or a `claude -p` run counts, and `list` shows both the session and the request's age.

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
- A clean exit deletes the row. A server killed with SIGKILL leaves a row that `list` stops showing after `session_stale_seconds`, and the next sweep deletes.
- A process suspended past the stale limit has its row re-created by the next heartbeat.
- The watcher never blocks a tool call: with a store opener that blocks in its thread, `ping`, `tools/list` and a tool call answer within a second.
- `list` and `status` show live sessions per member; `list -j` equals the `status` document; `Nothing needs you.` is unchanged.

### Technical Requirements
- The three keys missing fail with `ConfigError` naming the key; a stale limit under twice the heartbeat, or a heartbeat under the poll interval, fails naming both keys; the config contract's example loads.
- Every table, column, JSON field and config key is documented; `tests/test_contract_docs.py`, `tests/test_import_boundaries.py`, `tests/test_store_opened_only_by_state_move.py` and `tests/test_read_side_defined_once.py` pass.
- `sessions` has a cleanup, with a test: stale rows pruned by the sweep and by another process's heartbeat, live rows kept.
- `ruff format`, `ruff check`, `pyright` and the whole suite pass.

### Integration Requirements
- 244 can call `live_member_ids` and get the same answer `list` shows.
- 243's notes push with no change to this slice.
- 240's behavior is unchanged: its operations and their tests pass with the new `sweep` parameter.

### Verification Walkthrough

This is the Phase 4 draft, refined when Phase 6 is complete. `tests/live/channels` and the `sessions` section of `list` do not exist until the slice is built. Every step runs unattended; step 3 uses a throwaway home and the Claude Code login on this machine.

1. `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest`. Expected: all clean and passing.
2. `uv run pytest tests/mcp_server/test_protocol_pin.py`. Expected: pass; it shows the probe getting `Method not found` and `initialize` served.
3. `uv run pytest tests/live/channels`. Expected: pass, through the three sessions D10 describes.
4. Live store: see Special Considerations.

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
2. Config keys; migration 7, `store/sessions.py`, `store/push_reads.py`, the `sweep` parameter, and their tests.
3. `pinned_loop.py` and `test_protocol_pin.py`; move `server.py` onto it; the existing MCP tests must pass.
4. `channel_event.py`, `inbox_watcher.py`, `presence.py`, `inbox_resource.py` with in-process tests (memory streams, SDK client, injected opener and short intervals).
5. `SessionEntry`, `list`/`status` and the renderer.
6. Docs, `INSTRUCTIONS`, the departures' wording in the architecture and plan.
7. The live test, then the live-store migration.

### Special Considerations
- **Prompt injection.** The event is text the model reads as a user turn. It holds only enums, numbers and Context Forge ids, never another agent's words (D4).
- **Spend.** The live test makes real model calls on the configured model.
- **Live store (designated for migration; backup first).** The implementing agent runs these in order, after 240's migration. First back up, to the backups directory 240 uses (`~/.local/state/amoeba/backups/`): `sqlite3 ~/.local/state/amoeba/amoeba.sqlite3 ".backup ~/.local/state/amoeba/backups/amoeba.sqlite3.pre-007"` and `cp ~/.config/amoeba/config.yaml ~/.local/state/amoeba/backups/config.yaml.pre-241`. Then install the slice's code from the slice branch, `uv tool install --force <path to this repo>` (`docs/mcp-server.md`): `amoeba list` migrates with whatever code runs it, and a restarted session loads whatever is installed. Then add the three keys to the live config, and migrate by running `amoeba list`. Read back: `schema_meta.version` is 7, the member count matches the backup's, `amoeba list` works. Last, the PM restarts every client session once. Two windows are expected. Between the install and the key edit, every `amoeba` command fails with a `ConfigError` naming the missing keys; the agent runs those two steps back to back, so it lasts seconds. From the key edit until a session restarts, that session's old `amoeba-mcp` fails its tool calls with an error naming the config, then the schema (the config holds keys its code does not know, and the store is stamped 7). Restarting ends both. Restore, with every `amoeba` and `amoeba-mcp` process stopped: copy the store backup over the live file, delete its `-wal` and `-shm`, copy the config backup back, and reinstall the previous code (`uv tool install --force` from the previous commit) if you are going back to it, since the restored store at 6 would migrate again under this slice's code. The restore path goes in the slice notes, and the implementing agent deletes the two files, `amoeba.sqlite3.pre-007` and `config.yaml.pre-241`, with `rm` at slice integration (Phase 7), after the review passes.

## Operator Walkthrough

Done as the person running it.

- **Migration (once, by the implementing agent).** The live-store procedure in Special Considerations, including its two windows and the restart of client sessions.
- **Start.** In each repo that should get push, run `claude mcp add --scope project amoeba -- amoeba-mcp` and have an agent commit the `.mcp.json`. Start Claude Code with the alias and accept the start-up screens. `amoeba list` shows the session under its repo.
- **Normal path.** A request arrives, the session shows the `← amoeba` line and calls `inbox`.
- **No flag, an org with channels off, or `claude -p`.** The server runs and shows in `list`. Events are dropped by the client, and the agent polls at its rules-file moments. Nothing is lost.
- **A non-member directory, or a repo added after the session started.** No session row. `amoeba add`, then `/mcp` reconnect or a new session.
- **Session closed.** The row is deleted at once. **Session killed.** The row reads as gone after `session_stale_seconds`, and the next sweep or server start deletes it; nobody edits anything.
- **Computer asleep.** The heartbeat stops; on wake the next beat re-creates the row.
- **Store locked.** The tick is skipped and retried. Tools answer meanwhile.
- **A Claude Code update changes channels.** `uv run pytest tests/live/channels` fails with the screen it saw; polling still works until the docs and code are updated.
- **A repo that should show a live session does not.** The reason is the server's stderr line (not a member, `cf` failed, or a store error with its traceback). `claude --debug` writes it to `~/.claude/debug/<session-id>.txt` (channels reference, read 20261115). Fix the cause (`cf` on `PATH`, `amoeba add`), then `/mcp` reconnect.
- **An idle session, or one without push, counts as live.** A request to that repo is not woken (244) and waits for its agent or its TTL. `list` shows the session and the request's age, and `amoeba cancel` ends the request.
- **Undo.** To stop using push, remove the alias and run `claude mcp remove amoeba --scope project` in the repo. The only state is `sessions` rows: live ones plus killed servers' rows until the next server start or sweep (D6). Before Phase 7, the backups restore the pre-241 store (Special Considerations). After it, the schema is deliberately forward-only: `sessions` is harmless when unused (empty once sessions end), and older code refuses a store stamped 7. Going back to pre-241 code would take, with every `amoeba` and `amoeba-mcp` process stopped, `DROP TABLE sessions` and `schema_meta.version` set to 6 on the live store, which needs the PM's explicit designation under the project rule; it loses only live-session records. Dead ends found: that one, by design.
