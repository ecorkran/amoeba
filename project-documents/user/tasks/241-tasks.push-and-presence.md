---
docType: tasks
slice: push-and-presence
project: amoeba
lld: user/slices/241-slice.push-and-presence.md
dependencies:
- 240-slice.requests
projectState: Slices 220 to 229 are merged on main. Store schema version 5 (migrations
  001 to 005), `amoeba-mcp` serves the existing tools through `server.run`, state
  is in ~/.local/state/amoeba. Slice 240 (messages, deliveries, `send`/`inbox`/`reply`/`cancel`,
  migration 006) is designed and tasked; this slice is built after it is built and
  integrated. Slices 243 and 244 read the shapes this slice fixes.
dateCreated: 20261115
dateUpdated: 20261115
status: not_started
turns: 14
promptTokens: 678791
cachedTokens: 597644
cacheWriteTokens: 81125
completionTokens: 19533
durationSeconds: 131.6
costUsd: 0.579933
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.5799328
    completionTokens: 19533
---

# Tasks: Push and Presence

## Context Summary

- Working on slice 241 (design: `user/slices/241-slice.push-and-presence.md`; decisions D1 to D10 are cited by number). Effort 4/5. The design's Overview says what it delivers.
- Paths: a path without a prefix is under `src/amoeba/`; `tests/`, `docs/` and `project-documents/` paths are from the repo root, and `user/` means `project-documents/user/`.
- Module layout is the design's Component Structure. `mcp/server.py` (221 lines) gains call sites only; a new module that passes ~300 lines is split by concern.
- Closed values are defined once (the three config key names, `LIVE_SESSION`, `CHANNEL_EVENT_MAX_ENTRIES`, `PUSH_ANSWER_SECONDS`, the client-name pattern and placeholder, the channel method and capability names). No silent fallbacks; every swallowed exception carries a comment saying why. The store imports nothing from `operations` or `mcp` and is opened only through `wiring.open_store`.
- Every store, `cf` and file call in the watcher, heartbeat, resource handlers and resolver runs in `anyio.to_thread.run_sync`, each worker opening its own store; async code only sleeps, sends and does bookkeeping (D2). The store opener is a constructor argument so tests can substitute one.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. "Checks pass" means all four. The live tier is `uv run pytest tests/live/<dir>` (never part of a bare run; LLM spend is pre-authorized).
- Tests use the autouse `AMOEBA_HOME` fixture, the stub `cf` (`tests/cf_stub.py`, `tests/cf_fixtures.py`), `tests/git_repo.py`, `tests/user_configs.py`, `tests/store/seed.py`, and the SDK client over memory streams for in-process MCP tests. Destructive SQL only against throwaway stores. No sample id, hash or timestamp sits near a value an agent must fetch (hallucination-trap rule), including docs that tests check.
- `tests/test_contract_docs.py` requires every new table, column, JSON field and config key in the contract docs, so each task that adds one adds its entry then. Task 12 writes the prose.
- Production state: tests touch throwaway stores only; no task in sections 0 to 13 writes the live store or config. Task 13.1 rehearses the migration on a copy. The live migration, with backup and the backup's removal, is the Phase 7 hand-off checklist at the end of this file (migrating the live store before the merge would leave the installed tool refusing it). The "Amoeba Design Rules" block of `CLAUDE.md` designates the live store and config for migrations.
- Work on branch `241-slice.push-and-presence`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.

## 0. Setup

- [ ] **0.1 Branch, inputs and baseline**
  - [ ] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty. The planning documents (design, this file) are committed on the target, with no other uncommitted change: `git checkout -b 241-slice.push-and-presence {target}`
  - [ ] Confirm the prerequisites exist: `store/schema/` holds `001` to `006`, `EXPECTED_SCHEMA_VERSION` is 6, the store has `deliveries` with a `(member_id, seq)` index and `highest_assigned_seq`, `operations/status_models.py` has `MemberStatus` with `requests`, and the `inbox` tool name exists in `operations/names.py`. If any is missing write `BLOCKED: <what>` under this task and stop (240 must be built and integrated first)
  - [ ] Confirm the SDK pieces D1 builds on import from the repo's `.venv` (`uv run python -c`): `Connection` (with `for_loop`, `notify`, `initialized`) from `mcp.server.connection`, `serve_connection` from `mcp.server.runner`, `JSONRPCDispatcher` from `mcp.shared.jsonrpc_dispatcher`. If a path differs, note the real one under this task
  - [ ] Find the helpers to reuse and note their paths: `tests/user_configs.py` (`example_config_text`), `tests/cf_fixtures.py`, `tests/store/seed.py`, `tests/store/test_migration_006.py` (model for the migration test), `tests/store/test_vocabulary_pinning.py`, `tests/mcp_server/test_stdio_smoke.py`, `tests/mcp_server/test_call_tool.py`, `tests/load/test_report_release_load.py` (model for the load test), `tests/live/pause/harness.py`, `tests/live/conftest.py`, `tests/live_environment.py`, `tests/live_settings.py`
  - [ ] Run the checks once and note the baseline. Failures present before this slice are written down, not fixed
  - [ ] Success: `git branch --show-current` prints `241-slice.push-and-presence`; a note under this task gives the target, the baseline result, the SDK module paths and the helper paths

## 1. Re-check the dated facts and build the pty harness (Development Approach step 1; D9, D10)

- [ ] **1.1 Pseudo-terminal harness**
  - [ ] `tests/live/channels/harness.py` (and `__init__.py`): starts a real interactive `claude --dangerously-load-development-channels server:amoeba` in a `pty` (standard library) with a throwaway `AMOEBA_HOME`, a fixture repo directory as cwd, and a process group so the whole tree can be killed. It keeps a rolling copy of the screen text and exposes: wait for text, send keystrokes, terminate cleanly, SIGKILL the server process, and the last screen contents
  - [ ] The registration form is a harness parameter (project `.mcp.json` in the cwd; an `--mcp-config <file>` argument added to the launch; or a registration in a throwaway Claude config directory the harness points the session at), so 11.1 uses whichever form 1.2 adopts without changing the harness
  - [ ] Start-up screens are answered by matching their text, never positions. Screens known from the channels reference: the development-channel warning, folder trust, the project-server consent. An unknown screen, or a next screen not appearing within `STARTUP_SCREEN_WAIT_SECONDS` (60), fails with the last screen contents. Each wait constant lives in this module and every failure message names what it waited for plus the last screen
  - [ ] Model, from the required setting `AMOEBA_LIVE_CHANNEL_MODEL` (added to `tests/live_settings.py` the way the other model settings are; a missing value fails by name). The `inbox` and `list` tools of the `amoeba` server are pre-allowed for the session
  - [ ] Success: pyright clean; `uv run pytest tests/live/channels --collect-only` collects with the setting present
- [ ] **1.2 Re-check the dated facts against the installed Claude Code**
  - [ ] Using the harness and a throwaway fixture repo with a trivial stdio MCP server (a small throwaway script in a temporary directory outside the repo, not `amoeba-mcp`; it is not committed) that declares the channel capability and sends one channel event after `initialized`, check each dated fact: the flag name, the capability `experimental["claude/channel"]`, the notification method and params (`content`, `meta`), and the `<channel source=...>` tag reaching the model. Read the channels reference again and note the Claude Code version (`claude --version`)
  - [ ] Try the registration forms in D9's order and adopt the first under which the event reaches the session: the project `.mcp.json`; the server given with `--mcp-config <file>`; the user-scope install. Run each in a throwaway home so the PM's real Claude config is untouched
  - [ ] If none registers the channel, write `BLOCKED:` with the screens seen under this task and stop. Nothing later is built on a form that does not work
  - [ ] Where a fact differs from D4 or D9, correct the design text in `user/slices/241-slice.push-and-presence.md` (D4, D9, the Operator Walkthrough) to what was observed, with the date and version
  - [ ] Success: a note under this task names the adopted registration form, the Claude Code version and every correction made to the design (or "none"). Tasks 11.1 and 12.1 name what they do for each form

**Commit**: `test: add the channels pty harness and re-check the channel registration facts`

## 2. Config keys (D7)

- [ ] **2.1 Three required keys with cross-key checks**
  - [ ] `config/user_config.py`: add `notify_poll_seconds`, `session_heartbeat_seconds`, `session_stale_seconds`, each a number greater than 0, required, no default in code (same type pattern as `answering_wait_seconds`). A model-level validator requires `session_stale_seconds` at least twice `session_heartbeat_seconds`, and `session_heartbeat_seconds` at least `notify_poll_seconds`; each failure names both keys. The 2x factor is a named constant
  - [ ] `docs/config-contract.md`: the three keys with their meaning and the cross-key rules, and the suggested values 5, 30 and 90 in the example, once. Extend the example that `tests/user_configs.py` loads, and update every fixture config in `tests/` that lists the full key set so the suite still loads
  - [ ] Success: pyright clean
- [ ] **2.2 Config tests**
  - [ ] `tests/config/`: each key missing fails with `ConfigError` naming the key; a value of 0 or a negative fails; a stale limit under twice the heartbeat fails naming both keys; a heartbeat under the poll interval fails naming both keys; equal-to-limit values load; the contract's example loads
  - [ ] Success: checks pass

**Commit**: `feat: add notify_poll_seconds, session_heartbeat_seconds and session_stale_seconds`

## 3. Store: migration 007 and the sessions and push-read modules (D2, D6)

- [ ] **3.1 `007_sessions.sql` and rows**
  - [ ] `store/schema/007_sessions.sql`, create-only: `sessions` with `session_id` (text primary key), `member_id` (references `members`), `client`, `directory`, `started_at`, `heartbeat_at`, `push_confirmed_at` (null until confirmed); indexes on `(member_id)` and `(heartbeat_at)`; no `CHECK` list. `EXPECTED_SCHEMA_VERSION` becomes 7
  - [ ] `store/models.py`: frozen dataclasses `Session` (every column) and `PushRow` (the delivery's `seq`, event, the message's kind, and the counterparty member id per D4)
  - [ ] `docs/store-contract.md`: the table, its columns and indexes, version 7. Update stale-version assertions in `tests/store/test_migrations.py` and the schema pin in `tests/store/test_schema_holds_no_mirrored_state.py`. These pins and the fixture configs of 2.1 are the only edits to existing tests in this slice besides the call sites 9.1 names
  - [ ] Success: pyright clean; existing tests pass
- [ ] **3.2 Migration test**
  - [ ] `tests/store/test_migration_007.py` (model on `test_migration_006.py`): a version-6 database holding members, messages and deliveries migrates to 7 with all rows untouched and `foreign_key_check` empty; `sessions` has the D6 columns and both indexes; a store stamped 8 is refused and left untouched
  - [ ] Success: checks pass
- [ ] **3.3 `store/sql_sessions.py` and `store/sessions.py`**
  - [ ] `store/sql_sessions.py`: the statements, with `LIVE_SESSION` (a row is live when `heartbeat_at` is newer than now minus the stale seconds) defined once, plus the confirmed clause `push_confirmed_at IS NOT NULL` defined once
  - [ ] `store/sessions.py`: `upsert_session` (one statement on `session_id`: sets `heartbeat_at` and `push_confirmed_at` from the argument, and on first insert the other columns; a re-created row keeps the caller's original `started_at`), `delete_session`, `prune_stale_sessions(transaction, now, stale_seconds)` (deletes every row that is not `LIVE_SESSION`, for all members), `live_sessions` (every fresh row, ordered by `started_at` then `session_id`, with `push_confirmed_at`), `live_member_ids(transaction, now, stale_seconds)` (members with a fresh row whose `push_confirmed_at` is set). The heartbeat's prune-then-upsert runs in one write transaction (a helper in this module that takes the transaction)
  - [ ] Success: pyright clean
- [ ] **3.4 Tests for 3.3**
  - [ ] `tests/store/test_sessions.py`: upsert inserts then updates `heartbeat_at` and `push_confirmed_at` while keeping the other columns; a re-created row (after a prune) carries the original `started_at`; `live_sessions` omits a row exactly at and past the stale limit and shows one just inside it, and returns rows oldest `started_at` first whatever the insert order, and rows with equal `started_at` in `session_id` order; `live_member_ids` returns a member with a fresh confirmed row and not one whose rows are unconfirmed or stale; prune by another process's call deletes stale rows of every member and keeps live ones; `delete_session` of an unknown id is a no-op
  - [ ] `tests/store/test_members_queried_in_one_place.py` still passes; if it fails for a legitimate reason, fix the new code, not the test
  - [ ] Success: checks pass
- [ ] **3.5 `store/push_reads.py` and its tests**
  - [ ] `store/push_reads.py`: `member_high_seq(transaction, member_id)` (one indexed `MAX(seq)` on `deliveries`, a documented value for "none yet" that the watcher treats as a real baseline, not an error) and `push_rows_after(transaction, member_id, after_seq)` returning `PushRow`s ordered by `seq` (joins `messages` for kind and the counterparty: the message member that is not the receiver, and for a note its sender). Reads write nothing and keep no marker
  - [ ] `tests/store/test_push_reads.py`: high seq with no deliveries, with deliveries for several members (only the member's counts); `push_rows_after` returns only rows above the number, in order, with the right counterparty for a received request, an accepted request (counterparty is the other party) and a note; nothing is written (row counts and `sqlite_sequence` unchanged)
  - [ ] Success: checks pass

**Commit**: `feat: add sessions in migration 007 with session and push-read store modules`

## 4. The pinned serve loop (D1)

- [ ] **4.1 `mcp/pinned_loop.py`**
  - [ ] `serve_pinned(server, streams, init_options, background, *, lifespan_state)` (`lifespan_state` is the keyword-only argument `serve_loop` and `serve_connection` require; read how `Server.run` obtains it for a server with no lifespan and pass the same value): builds the dispatcher and `Connection.for_loop`, starts `background(connection)` in a task group, runs `serve_connection`, cancels the background when it returns. It mirrors the SDK's `serve_loop` (`mcp/server/runner.py`) and nothing else; no version constant
  - [ ] Success: pyright clean
- [ ] **4.2 Protocol pin test**
  - [ ] `tests/mcp_server/test_protocol_pin.py`: over real stdio (a raw JSON-RPC driver, no SDK client), start a tiny server through `serve_pinned`, send `server/discover` for 2026-07-28 and assert error -32601 (`Method not found`); then `initialize` and assert it is served at a handshake-era version. Also run the same `Server` under `server.run` and assert the documented contrast (probe answered with `supportedVersions`, a following `initialize` refused with -32022), so an SDK change to either loop fails a test. The test header cites D1
  - [ ] A second test: the background callable runs, receives the connection, and is cancelled when the client closes its end (the server process exits within a timeout)
  - [ ] Success: checks pass
- [ ] **4.3 Move `amoeba-mcp` onto it**
  - [ ] `mcp/server.py`: `_serve` calls `serve_pinned` with a `background` that does nothing yet and is replaced in task 9. `Server` is still built by `build_server`; no capability change yet
  - [ ] Success: every existing test under `tests/mcp_server/` and `tests/live/mcp` collection still passes unchanged; checks pass

**Commit**: `feat: serve amoeba-mcp through a handshake-only pinned loop`

## 5. The channel event (D4)

- [ ] **5.1 `mcp/channel_event.py`**
  - [ ] A pure function from push rows to the event params, no I/O. Constants: the channel method name, the capability name, `CHANNEL_EVENT_MAX_ENTRIES` (10). `meta`: `first_seq`, `last_seq`, `count`, all digit strings. `content` follows D4's fixed template: count, seq range, entries `<kind>, <event> from|with <member id>` (built only from the closed enums and the counterparty's member id), at most the cap listed then `and K more`, then the instruction to call `inbox` with `since` set to the caller's own last `as_of_seq`, or omitted if it has none. No subject, body, result, reason or request id is a parameter of the function
  - [ ] `docs/mcp-server.md`: the entry for the event's `content` and `meta` fields (`first_seq`, `last_seq`, `count`), so `tests/test_contract_docs.py` stays green; 12.1 writes the prose
  - [ ] Success: pyright clean
- [ ] **5.2 Tests**
  - [ ] `tests/mcp_server/test_channel_event.py`: rows whose text-bearing fields hold marker strings produce content and meta in which no marker appears; `first_seq`, `last_seq`, `count` are right for one row and for many; with cap+1 rows exactly the cap are listed and `and 1 more` appears; every `meta` key is an identifier and every value a digit string; a note names its sender as counterparty and a request the other party
  - [ ] Success: checks pass

## 6. Presence (D2, D3, D6)

- [ ] **6.1 `PresenceState` and `resolve_presence`**
  - [ ] `mcp/presence.py`: `PresenceState` with three states (pending, a member id, off with a reason), the subscribed flag, the session id (`uuid4().hex`, made once), start time, the time of the last unanswered channel event, the push-confirmed time, and a `resolved` event set in a `finally` so pending always ends. State is touched only by event-loop tasks
  - [ ] `resolve_presence`: runs `operations.members.resolve_member(store, Path.cwd(), cf_run)` once in a worker thread (own store via the injected opener, `cf_run` from `wiring.default_deps`). `Member` sets the member; `NotInProgram` or `NotAProject` sets off with one INFO line saying the directory is not a member; `ContextForgeError` or `StoreError` propagates to the caller (the top-level handler of 6.5)
  - [ ] Success: pyright clean
- [ ] **6.2 Client name and heartbeat loop**
  - [ ] Client name: `clientInfo.name` if it matches `[A-Za-z0-9._ -]{1,64}`, else the placeholder `unrecognized` and one WARNING (pattern and placeholder are constants)
  - [ ] The heartbeat loop: first beat at `initialized`, then every `session_heartbeat_seconds`; each beat is one worker call that opens its own store and runs prune-then-upsert (3.3) with the in-memory `push_confirmed_at`. `StoreBusyError` is logged at WARNING once per run of failures and retried at the next beat (a comment states why: push is a hint and polling is the floor); any other `StoreError` propagates
  - [ ] Success: pyright clean
- [ ] **6.3 Tests for 6.1 and 6.2**
  - [ ] `tests/mcp_server/test_presence.py` (fake clock, injected opener, memory streams): a non-member directory sets off with the INFO line; a `cf` failure and a `cf` timeout (stub `cf` returning `CfCallFailed`) raise `ContextForgeError` out of `resolve_presence`; `resolved` is set in each outcome including an exception
  - [ ] Heartbeat: the first beat writes the row at `initialized` with the client name; a bad `clientInfo.name` stores `unrecognized` and warns; a busy store is retried, logs once per run, and the next beat succeeds; a corrupt-store error propagates; a process suspended past the stale limit (fake clock jump, row pruned by another connection) has its row re-created with the original `started_at`
  - [ ] Success: checks pass

**Commit**: `feat: add the channel event, presence state, member resolution and heartbeat`

- [ ] **6.4 Push confirmation (D6)**
  - [ ] `note_event_attempted(state, now)`: records an attempt only when none is waiting (an unanswered one older than `PUSH_ANSWER_SECONDS` is replaced by the next event's fresh attempt). `note_inbox_called(state, now)`: if an attempt is recorded and at most `PUSH_ANSWER_SECONDS` old, set push-confirmed (sticky); in every case clear the recorded attempt. The clock is `Deps.clock`
  - [ ] Tests in `tests/mcp_server/test_presence.py`: an `inbox` call within `PUSH_ANSWER_SECONDS` of an attempt confirms and the next beat writes `push_confirmed_at`; an `inbox` call with no attempt, or after the limit, does not; the attempt is cleared either way; a second event while one is waiting does not reset the first, and one older than the limit is replaced; confirmation is sticky, so a later `inbox` call with no attempt recorded leaves it set
  - [ ] Success: checks pass
- [ ] **6.5 `run_presence`: the presence task, its top-level handler and clean exit**
  - [ ] `run_presence(connection, state, ...)` in its own module, `mcp/presence_task.py` (so `mcp/presence.py` keeps state, resolution, heartbeat and confirmation): resolve the member; if off, return with no row and no loop. Otherwise wait on `connection.initialized`, read the client name, log the INFO line with protocol version and client name, and run the heartbeat loop in one child task group (task 7.1 adds the push loop to that group). One top-level handler catches `Exception` (not `BaseException`; cancellation passes), calls `logger.exception`, cancels the children and ends presence. In every exit path a shielded `DELETE` of the session row runs, bounded by `BUSY_TIMEOUT_SECONDS * 2`; if that delete fails the row goes stale (log it, comment why)
  - [ ] Tests in `tests/mcp_server/test_presence_task.py` (same rig as 6.3): a `cf` failure, a `cf` timeout and a `StoreError` raised by the member lookup each write no row, log with `logger.exception` and return; a non-member returns with no row; a corrupt-store error from the heartbeat is logged with its traceback, ends presence and deletes the row; clean exit (the background cancelled) deletes the row; a failing delete leaves a row that `live_sessions` stops showing after the stale limit
  - [ ] Success: checks pass

**Commit**: `feat: add push confirmation and the presence task with clean exit`

## 7. The inbox watcher (D2, D4, D5)

- [ ] **7.1 `mcp/inbox_watcher.py`**
  - [ ] The push loop, taking the connection, `PresenceState`, the store opener, the clock and `notify_poll_seconds`; `run_presence` (6.5) starts it in the same child task group as the heartbeat. It retries the baseline read (`member_high_seq`, in a worker thread) each tick until it succeeds, sending nothing before it has one. Then every `notify_poll_seconds` it reads again; when the value exceeds the last seen it reads `push_rows_after`, builds the event (task 5), sends `notifications/claude/channel` through `connection.notify`, records the attempt (`note_event_attempted`, 6.4), sends `notifications/resources/updated` for `amoeba://inbox` only if the subscribed flag is set, logs one INFO line `channel event attempted` with `first_seq`, `last_seq` and `count` (no text), and stores the new last seen
  - [ ] `StoreBusyError` in a tick or the baseline: WARNING once per run of failures, retried next tick. Any other failure propagates to the 6.5 handler
  - [ ] Success: pyright clean
- [ ] **7.2 Tests**
  - [ ] `tests/mcp_server/test_inbox_watcher.py` (fake clock, SDK client on memory streams, short intervals): no event before a baseline exists; mail written after the baseline produces one event with the right `meta`; two deliveries in one tick are one event; no delivery produces nothing; a busy store on a tick skips it, then the next event is sent; a busy baseline retries and sends nothing until it succeeds; any other store error raises out of the loop
  - [ ] 243's notes push with no change here: a note delivery seeded with `tests/store/seed.py` (the table's note shape, as 240's migration allows; 243 adds the writer) produces an event whose entry names kind `note` and its sender
  - [ ] `Connection.notify` pin: the SDK drops a send to a closed stream only for `BrokenResourceError` and `ClosedResourceError` (`mcp/server/connection.py`, `notify`), so a notify on a closed stream does not raise (drop logged at debug). Any other exception from `notify` is not swallowed: a notify patched to raise one raises out of the loop
  - [ ] The INFO line contains the numbers and no marker text written into a message subject, body or id
  - [ ] Success: checks pass

## 8. The `amoeba://inbox` resource (D5)

- [ ] **8.1 `mcp/inbox_resource.py`**
  - [ ] Handlers for `resources/list`, `resources/read`, `resources/subscribe`, `resources/unsubscribe`. Every handler first waits on `PresenceState.resolved` (only that request waits). `list`: the one resource (`amoeba://inbox`, `application/json`) for a member, an empty list otherwise. `read`: JSON `{"member": <id>, "as_of_seq": <highest_assigned_seq>}` read in a worker thread, no message text. `subscribe` sets the flag, `unsubscribe` clears it (clearing a clear flag succeeds). No member, or any other uri, makes `read`, `subscribe` and `unsubscribe` fail with invalid-params. A `StoreError` in `read` fails only that request with an internal-error response naming the error. The URI is a constant
  - [ ] `docs/mcp-server.md`: the entry for the resource's JSON fields (`member`, `as_of_seq`); 12.1 writes the prose
  - [ ] Success: pyright clean
- [ ] **8.2 Tests**
  - [ ] `tests/mcp_server/test_inbox_resource.py`: a `resources/list` made while resolution is still pending (resolver held on an event) waits, then returns the resolved answer; list is empty for a non-member; `read` returns the member and the same number `inbox` reports as `as_of_seq`; subscribe then unsubscribe toggles the flag; unsubscribe twice succeeds; a non-member and a foreign uri each give invalid-params; a `StoreError` in `read` fails that request and the next request succeeds
  - [ ] With the watcher of 7.1 running: a client that subscribed gets `notifications/resources/updated` for `amoeba://inbox` after a channel event; one that never subscribed, and one that unsubscribed, get none
  - [ ] Success: checks pass

**Commit**: `feat: add the inbox watcher and the amoeba://inbox resource`

## 9. Wire presence into `amoeba-mcp` (D1 to D6, D10)

- [ ] **9.1 Capabilities, handlers, background and logging**
  - [ ] `mcp/server.py` gains call sites only: the capability declarations (`experimental["claude/channel"] = {}` and `resources: {subscribe: true}`, on every server per D3) and the four resource handlers' registration live in `mcp/inbox_resource.py` (the channel capability name is the 5.1 constant), and `build_server` calls them. `wc -l mcp/server.py` after this task is under ~300. `main()` (synchronous, where `wiring.load_config()` already runs for `check_deadline`) reads the three keys from that config and fails to start through the existing refuse-to-start path if one is missing; it passes them into `_serve`, so no config file is read on the event loop. `_serve` builds the `PresenceState` and passes `run_presence` as the `background` of `serve_pinned`
  - [ ] `call_tool` logs `tool <name> called` at INFO at its start (name only) and, after an `inbox` call completes without error, calls `note_inbox_called`; thread the `PresenceState` to `call_tool` through the handler closure built in `build_server` and update the existing `call_tool` test call sites rather than add a hidden default
  - [ ] `INSTRUCTIONS`: add D4's paragraph (events arrive as `<channel source="amoeba">`, they say only that mail arrived, the response is to call `inbox`). `tests/mcp_server/test_instructions.py` stays green
  - [ ] Success: pyright clean; every existing MCP test passes
- [ ] **9.2 In-process behavior tests**
  - [ ] `tests/mcp_server/test_presence_serving.py` (SDK client against `serve_pinned`, memory streams, stub `cf`): `initialize` declares both capabilities for a member and for a non-member directory; a non-member server serves tools, writes no row, runs no loop and lists no resources; a `cf` failure at start does the same and logs the error; a member server writes a row, then an `inbox` tool call after an event confirms the session; the INFO lines (`tool inbox called`, the protocol/client line) appear
  - [ ] The watcher never blocks a tool call: with a store opener that blocks in its thread, `ping`, `tools/list` and a tool call each answer within one second
  - [ ] A watcher failure (opener raises a non-busy `StoreError` after the first beat) is logged with its traceback, deletes the row, and the server keeps answering tool calls
  - [ ] Success: checks pass
- [ ] **9.3 Real-stdio exit tests**
  - [ ] Extend `tests/mcp_server/test_stdio_smoke.py` or add `test_presence_stdio.py` (installed `amoeba-mcp`, throwaway `AMOEBA_HOME`, stub `cf`, short intervals): a member directory shows a row in the store while serving and none after the client closes stdin; a SIGKILLed server leaves a row that `live_sessions` stops showing after `session_stale_seconds`, and another server's heartbeat deletes it
  - [ ] Success: checks pass
- [ ] **9.4 Load test (concurrency path)**
  - [ ] `tests/load/test_presence_load.py` (model on `tests/load/test_report_release_load.py`, collected the same way): a constant number of presence runs (12) share one throwaway store, each with its own thread-opened store and short intervals, while a writer adds deliveries for several of their members and a client makes tool calls against one of them. Assert: every session row is live at the end (no heartbeat gap reached `session_stale_seconds`); each watcher sent one event per burst with the right `count`; the tool calls and `ping` answered within one second; no exception escaped a presence task and no `StoreBusyError` ended presence
  - [ ] CI gate: `pyproject.toml` collects `tests` and ignores only `tests/live`, and `.github/workflows/ci.yml` runs bare `uv run pytest`, so the load test is gated with no config change. Confirm with `uv run pytest --collect-only -q | grep test_presence_load`, which must list it
  - [ ] Success: checks pass; `uv run pytest tests/load/test_presence_load.py` passes

**Commit**: `feat: serve push and presence from amoeba-mcp`

## 10. `list` and `status` show live sessions (D8)

- [ ] **10.1 `SessionEntry` and `MemberStatus.sessions`**
  - [ ] `operations/status_models.py`: `SessionEntry` (`client`, `directory`, `started_at`, `heartbeat_at`, `push_confirmed_at`); `MemberStatus` gains `sessions`, oldest first. The status operation fills it from `live_sessions` under active members only, in the same transaction as its other reads, with the stale seconds from config. `list -j` still equals the `status` document. Sessions do not enter "waiting on you" and do not set the notice (240 D11)
  - [ ] `docs/cli-contract.md`: the new `sessions` JSON fields per member
  - [ ] Success: pyright clean
- [ ] **10.2 Renderer and tests**
  - [ ] The text renderer adds a **Live sessions** section per member with any, one line per session: `<client>  <directory>  up <age>  last beat <age> ago  push confirmed|push unconfirmed`. A member with none shows no section; `Nothing needs you.` is unchanged
  - [ ] Tests (in the existing status and list test modules, seeded with `tests/store/seed.py`): a fresh session appears with its fields; sessions of one member appear oldest first; a stale row does not; a removed member's session does not; confirmed and unconfirmed render differently; a member with no sessions has no section; `list -j` equals `status` with `sessions`; `Nothing needs you.` still prints with only sessions present; `tests/test_read_side_defined_once.py` passes
  - [ ] Integration test (244's contract): on one seeded store and clock, the members `live_member_ids` returns are exactly the members whose sessions `status` shows as push confirmed and fresh, over confirmed, unconfirmed, stale and removed-member rows
  - [ ] Success: checks pass

**Commit**: `feat: show live sessions per member in list and status`

## 11. Live test (D10)

- [ ] **11.1 Live-test rig and fixtures**
  - [ ] The `amoeba-mcp` stderr INFO lines D10 relies on exist from earlier tasks (protocol version and client name, 6.5; `channel event attempted` with the numbers, 7.1; `tool <name> called`, 9.1); a launcher script runs `amoeba-mcp` with its stderr appended to a file the test reads. Config uses `notify_poll_seconds` 1, `session_heartbeat_seconds` 1, `session_stale_seconds` 3; the harness constants are `INBOX_CALL_WAIT_SECONDS` (120) and `STALE_MARGIN_SECONDS` (5); the wait for a killed server's row is `session_stale_seconds` plus the margin
  - [ ] Fixtures in `tests/live/channels/conftest.py`: a throwaway `AMOEBA_HOME`; two repos `cf-s` and `sq-s` built through the real `cf` and registered with `add` in one program; a third directory `outside`, a git repo registered with neither `cf` as a project nor `add`. `cf-s` and `outside` each carry the registration of the form 1.2 adopted, naming the launcher (project `.mcp.json` in the directory; or the harness passing `--mcp-config <file>`; or the registration in the harness's throwaway Claude config). `amoeba` is called by absolute path, never the bare name
  - [ ] First test asserts the store `amoeba` resolves lies under the throwaway home
  - [ ] Success: that test passes; every wait failure reports what it waited for and the last screen
- [ ] **11.2 Session 1: push reaches the agent, and the session is confirmed**
  - [ ] In `cf-s`: `amoeba list -j` shows a live session under `cf-s` with its directory; the test runs `amoeba send --to cf-s --id sq-1 --subject "Need X" --body "Please add X"` from `sq-s`, then waits for `tool inbox called` in the server log with nothing typed; within `session_heartbeat_seconds` plus the margin `list -j` shows that session with `push_confirmed_at` set; after a clean exit `list -j` shows no session. Also assert the logged protocol version is a handshake version
  - [ ] Success: `uv run pytest tests/live/channels -k session_one` passes (name the test accordingly)
- [ ] **11.3 Session 2: a killed server goes stale**
  - [ ] The same setup with the server SIGKILLed; `list -j` shows no session once the stale wait has passed
  - [ ] Success: `uv run pytest tests/live/channels -k killed` passes (name the test accordingly)
- [ ] **11.4 Session 3: a non-member directory, then the whole tier**
  - [ ] In `outside`: the server log says it is not a member and `list -j` shows no session; the test types one prompt asking the agent to call the `amoeba` `list` tool, and waits for `tool list called` in the log
  - [ ] Run `uv run pytest tests/live/channels` (all three sessions)
  - [ ] Success: it passes; `tests/live/mcp` and `tests/live/pause` still pass; checks pass

**Commit**: `test: add the channels live tier against a real Claude Code session`

## 12. Documents (D4, D5, D8, D9, Departures)

- [ ] **12.1 Contract and server docs**
  - [ ] `docs/mcp-server.md`: the pinned loop and what it means for clients (handshake era only), the capabilities, the channel event (fields and the no-message-text rule), the `amoeba://inbox` resource and subscribe behavior, sessions and push confirmation, the three INFO log lines, the launch flag and the shell alias, the registration for the form 1.2 adopted (the `.mcp.json` command, the `--mcp-config` file, or the user-scope install) with the consent and start-up screens, the Team/Enterprise `channelsEnabled` note, `claude -p` ignoring the flag, how to debug a repo with no live session (`claude --debug`), and re-running `uv run pytest tests/live/channels` after a Claude Code or SDK update. The restart note: open sessions run the old server
  - [ ] `docs/store-contract.md` (sessions rules: stale predicate, prune, confirmation, cleanup), `docs/config-contract.md` (check 2.1), `docs/cli-contract.md` (check 10.1)
  - [ ] Success: `tests/test_contract_docs.py` passes
- [ ] **12.2 Parent documents and the design**
  - [ ] Amend `user/architecture/240-arch.agent-messaging.md` and `user/architecture/240-slices.agent-messaging.md` to match the design's Departures section: the `directory` column; no code defaults for the three keys; `sessions` in migration 7 and its Store and config paragraph; a non-member server declares the capabilities; the event tells the agent to use its own cursor; `serve_pinned` and the watcher beside it; pruning by every heartbeat, not the sweep; presence feeding waking only through push-confirmed sessions (the presence paragraph and walkthrough step 3)
  - [ ] Amend `user/slices/241-slice.push-and-presence.md`: the walkthrough refinement and any correction from 1.2; the Component Structure gains `mcp/presence_task.py` (`run_presence`) and the resource registration helper in `mcp/inbox_resource.py`; D2's "`Connection.notify` never raises" reworded to what the SDK does (a send to a closed stream is dropped, for `BrokenResourceError` and `ClosedResourceError` only); D8's order stated as `started_at` then `session_id`; two lines added to its Departures section: the live-store migration runs in the Phase 7 hand-off, after the merge, and a rehearsal on a copy (13.1) precedes it. Make the rest of the design agree with the hand-off, so it holds one procedure: Development Approach step 7 ends at the live test (the migration is the Phase 7 hand-off), and Special Considerations' Live store paragraph installs from the target after the merge (not "from the slice branch"), deletes the backups once the read-back passes (not "after the review passes"), and takes "the previous code" as the pre-merge target commit recorded in P7.0
  - [ ] Success: `grep -n "serve_pinned" project-documents/user/architecture/240-*.md` finds the new wording; checks pass

**Commit**: `docs: document push and presence, amend the 240 parents`

## 13. Final verification

- [ ] **13.1 Rehearse the live migration on a copy**
  - [ ] Nothing live is written. `TMP=$(mktemp -d)`; `sqlite3 ~/.local/state/amoeba/amoeba.sqlite3 ".backup $TMP/amoeba.sqlite3"`; `cp ~/.config/amoeba/config.yaml $TMP/config.yaml`; `export AMOEBA_HOME=$TMP`. Add the three keys to `$TMP/config.yaml` with values from `docs/config-contract.md`'s example
  - [ ] Record `sqlite3 $TMP/amoeba.sqlite3 "SELECT version FROM schema_meta WHERE id = 1"` and `"SELECT count(*) FROM members WHERE removed_at IS NULL"`. Expected version: the number of the last migration file before `007_sessions.sql` in `store/schema/` (240's migration), or the one before that if 240 is not migrated live, in which case also add 240's two keys from the contract's example. Any other result, including an empty one, is `BLOCKED:` with the raw query output, and the rehearsal stops. Otherwise the one `uv run amoeba list` migrates the copy to 007
  - [ ] Read back: version equal to `EXPECTED_SCHEMA_VERSION`, same member count, `PRAGMA integrity_check` ok, `PRAGMA foreign_key_check` empty, `uv run amoeba list` exits 0
  - [ ] Success: a note under this task gives the before and after version and member count. `unset AMOEBA_HOME` and `rm -r $TMP` after
- [ ] **13.2 Final verification**
  - [ ] Run Verification Walkthrough steps 1 to 3 (all four checks; `uv run pytest tests/mcp_server/test_protocol_pin.py`; `uv run pytest tests/live/channels`); step 4 is the Phase 7 checklist below. Confirm `tests/test_contract_docs.py`, `tests/test_import_boundaries.py`, `tests/test_store_opened_only_by_state_move.py` and `tests/test_read_side_defined_once.py` pass by name
  - [ ] Update the walkthrough in `user/slices/241-slice.push-and-presence.md` where Phase 6 changed it (it says it is refined when Phase 6 completes), and note any departure from the design under this task
  - [ ] Confirm 240 is unchanged apart from what the design names: `git diff {target}` shows no change to a 240 function's signature or body, and the only 240 edits are `MemberStatus` gaining `sessions`, `EXPECTED_SCHEMA_VERSION`, the stale-version and schema pins (3.1), the fixture configs (2.1) and the `call_tool` call sites (9.1). 240's tests pass with no other edit
  - [ ] Success: all checks pass; every Success Criteria line in the design maps to a passing test named in a note under this task

**Commit**: `test: verify push and presence and rehearse the live migration`

## Phase 7 hand-off checklist

Phase 6 is complete when sections 0 to 13 are checked. These items are checked in Phase 7 by the implementing agent, after the code review passes: P7.0 just before the merge, the rest after the slice is merged (the merge is Phase 7's, not a task). Designated by `CLAUDE.md`; the backup comes first. Run after 240's live migration.

- [ ] **P7.0 Record the pre-merge target**
  - [ ] Immediately before the merge, write the output of `git rev-parse {target}` into the slice notes in `user/slices/241-slice.push-and-presence.md` as the pre-merge target commit (the commit P7.3 reinstalls if it must go back). If the command prints anything other than one 40-character hex SHA, including nothing, write `BLOCKED:` with the raw output under this task and do not merge

- [ ] **P7.1 Precondition and backup**
  - [ ] Precondition, as 13.1 records its own: `sqlite3 ~/.local/state/amoeba/amoeba.sqlite3 "SELECT version FROM schema_meta WHERE id = 1"` equals the number of the last migration file before `007_sessions.sql` in `store/schema/` (240's migration), and `~/.config/amoeba/config.yaml` holds 240's two keys. Any other result, including an empty one, is `BLOCKED: 240 not migrated live` with the raw output under this task, and the checklist stops; this slice's migration does not run before 240's
  - [ ] Into `~/.local/state/amoeba/backups/`: `sqlite3 ~/.local/state/amoeba/amoeba.sqlite3 ".backup ~/.local/state/amoeba/backups/amoeba.sqlite3.pre-007"` and `cp ~/.config/amoeba/config.yaml ~/.local/state/amoeba/backups/config.yaml.pre-241`
  - [ ] Write the restore path (P7.3's restore item, with both backup paths) into the slice notes in `user/slices/241-slice.push-and-presence.md`, as the design's Special Considerations require
- [ ] **P7.2 Install, keys and migrate**
  - [ ] Back to back (between them every `amoeba` command fails with a `ConfigError` naming the missing keys): `uv tool install --force .` from the target, then add the three keys to `~/.config/amoeba/config.yaml` (values from the contract's example) and run `amoeba list` to migrate
- [ ] **P7.3 Read back, and restore if it fails**
  - [ ] As in 13.1 against the live store: version 7, the member count equal to the backup's, integrity and foreign-key checks clean, `amoeba list` exits 0. Open client sessions run the old `amoeba-mcp` until restarted; it fails its tool calls with an error naming the config, then the schema
  - [ ] Only if a read-back fails: stop every process that holds the files: SIGTERM each `amoeba-mcp` (open client sessions need a restart after the migration anyway), then re-run `pgrep -fl amoeba` until none remains, for at most 60 seconds; at that limit SIGKILL what remains and log the `pgrep` lines in the slice notes. Then copy the store backup over the live file, delete its `-wal` and `-shm`, copy the config backup back, and reinstall the tool from the pre-merge target commit recorded in P7.0 (`uv tool install --force` from a worktree at that commit; the restored store would migrate again under this slice's code). Mark this item `n/a: read-back passed` when it is not needed
- [ ] **P7.4 Remove the backups**
  - [ ] After the read-back passes: `rm ~/.local/state/amoeba/backups/amoeba.sqlite3.pre-007 ~/.local/state/amoeba/backups/config.yaml.pre-241`. From here the restore above is gone by design; a defect found later is corrected forward with a new create-only migration under the same designation, since `sessions` is harmless when unused and needs no downgrade. Stopping the use of push needs no store change: the design's Operator Walkthrough "Undo" (remove the alias and the project registration) is the whole exit
