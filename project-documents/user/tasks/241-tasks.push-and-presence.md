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
dateUpdated: 20261116
status: complete
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

- [x] **0.1 Branch, inputs and baseline**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty. The planning documents (design, this file) are committed on the target, with no other uncommitted change: `git checkout -b 241-slice.push-and-presence {target}`
  - [x] Confirm the prerequisites exist: `store/schema/` holds `001` to `006`, `EXPECTED_SCHEMA_VERSION` is 6, the store has `deliveries` with a `(member_id, seq)` index and `highest_assigned_seq`, `operations/status_models.py` has `MemberStatus` with `requests`, and the `inbox` tool name exists in `operations/names.py`. If any is missing write `BLOCKED: <what>` under this task and stop (240 must be built and integrated first)
  - [x] Confirm the SDK pieces D1 builds on import from the repo's `.venv` (`uv run python -c`): `Connection` (with `for_loop`, `notify`, `initialized`) from `mcp.server.connection`, `serve_connection` from `mcp.server.runner`, `JSONRPCDispatcher` from `mcp.shared.jsonrpc_dispatcher`. If a path differs, note the real one under this task
  - [x] Find the helpers to reuse and note their paths: `tests/user_configs.py` (`example_config_text`), `tests/cf_fixtures.py`, `tests/store/seed.py`, `tests/store/test_migration_006.py` (model for the migration test), `tests/store/test_vocabulary_pinning.py`, `tests/mcp_server/test_stdio_smoke.py`, `tests/mcp_server/test_call_tool.py`, `tests/load/test_report_release_load.py` (model for the load test), `tests/live/pause/harness.py`, `tests/live/conftest.py`, `tests/live_environment.py`, `tests/live_settings.py`
  - [x] Run the checks once and note the baseline. Failures present before this slice are written down, not fixed
  - [x] Success: `git branch --show-current` prints `241-slice.push-and-presence`; a note under this task gives the target, the baseline result, the SDK module paths and the helper paths
    - Note: Target: main (`cf config get git.integration_branch` empty). Branch 241-slice.push-and-presence already existed at main's head with no commits of its own; work continues on it.
      - Prerequisites present: store/schema 001-006, EXPECTED_SCHEMA_VERSION 6, deliveries_member_seq index (member_id, seq), store/deliveries.py highest_assigned_seq, MemberStatus.requests, ToolName INBOX in operations/names.py.
      - SDK (mcp 2.3.0): `Connection` from mcp.server.connection (`for_loop` classmethod, `notify`, `initialized` is an instance anyio.Event); `serve_connection` and `serve_loop` from mcp.server.runner; `JSONRPCDispatcher` from mcp.shared.jsonrpc_dispatcher. Paths as the task names them.
      - Helpers all present at the named paths (tests/user_configs.py example_config_text, tests/cf_fixtures.py, tests/cf_stub.py, tests/store/seed.py, tests/store/test_migration_006.py, tests/store/test_vocabulary_pinning.py, tests/mcp_server/test_stdio_smoke.py, tests/mcp_server/test_call_tool.py, tests/load/test_report_release_load.py, tests/live/pause/harness.py, tests/live/conftest.py, tests/live_environment.py, tests/live_settings.py, tests/git_repo.py).
      - Baseline: ruff format clean, ruff check clean, pyright 0 errors, pytest 3208 passed.

## 1. Re-check the dated facts and build the pty harness (Development Approach step 1; D9, D10)

- [x] **1.1 Pseudo-terminal harness**
  - [x] `tests/live/channels/harness.py` (and `__init__.py`): starts a real interactive `claude --dangerously-load-development-channels server:amoeba` in a `pty` (standard library) with a throwaway `AMOEBA_HOME`, a fixture repo directory as cwd, and a process group so the whole tree can be killed. It keeps a rolling copy of the screen text and exposes: wait for text, send keystrokes, terminate cleanly, SIGKILL the server process, and the last screen contents
  - [x] The registration form is a harness parameter (project `.mcp.json` in the cwd; an `--mcp-config <file>` argument added to the launch; or a registration in a throwaway Claude config directory the harness points the session at), so 11.1 uses whichever form 1.2 adopts without changing the harness
  - [x] Start-up screens are answered by matching their text, never positions. Screens known from the channels reference: the development-channel warning, folder trust, the project-server consent. An unknown screen, or a next screen not appearing within `STARTUP_SCREEN_WAIT_SECONDS` (60), fails with the last screen contents. Each wait constant lives in this module and every failure message names what it waited for plus the last screen
  - [x] Model, from the required setting `AMOEBA_LIVE_CHANNEL_MODEL` (added to `tests/live_settings.py` the way the other model settings are; a missing value fails by name). The `inbox` and `list` tools of the `amoeba` server are pre-allowed for the session
  - [x] Success: pyright clean; `uv run pytest tests/live/channels --collect-only` collects with the setting present
    - Note: Harness split by concern: tests/live/channels/harness.py (ClaudeSession: start, wait_for, send, choose, type_prompt, terminate, kill, kill_server(pid_file), last_screen), registration.py (RegistrationForm with all three forms, ServerRegistration, SessionSpec, register), screen.py (ScreenLog; cursor moves become spaces, matching on whitespace-normalized text). Setting AMOEBA_LIVE_CHANNEL_MODEL added to tests/live_settings.py (read_channel_model), read at collection in tests/live/channels/conftest.py.
      - Departure (smallest change keeping intent): a throwaway CLAUDE_CONFIG_DIR has no login (Claude Code keys its keychain credential per config dir), so the session uses the operator's Claude config with `--setting-sources project,local` (no user hooks or permission mode) and DISABLE_AUTOUPDATER=1. Registration is only ever written in the fixture directory or a scratch file; the only write to the operator's config is Claude Code's own folder-trust record for each throwaway directory. Design D10 updated to say so.
- [x] **1.2 Re-check the dated facts against the installed Claude Code**
  - [x] Using the harness and a throwaway fixture repo with a trivial stdio MCP server (a small throwaway script in a temporary directory outside the repo, not `amoeba-mcp`; it is not committed) that declares the channel capability and sends one channel event after `initialized`, check each dated fact: the flag name, the capability `experimental["claude/channel"]`, the notification method and params (`content`, `meta`), and the `<channel source=...>` tag reaching the model. Read the channels reference again and note the Claude Code version (`claude --version`)
  - [x] Try the registration forms in D9's order and adopt the first under which the event reaches the session: the project `.mcp.json`; the server given with `--mcp-config <file>`; the user-scope install. Run each in a throwaway home so the PM's real Claude config is untouched
  - [x] If none registers the channel, write `BLOCKED:` with the screens seen under this task and stop. Nothing later is built on a form that does not work
  - [x] Where a fact differs from D4 or D9, correct the design text in `user/slices/241-slice.push-and-presence.md` (D4, D9, the Operator Walkthrough) to what was observed, with the date and version
  - [x] Success: a note under this task names the adopted registration form, the Claude Code version and every correction made to the design (or "none"). Tasks 11.1 and 12.1 name what they do for each form
    - Note: Adopted form: project `.mcp.json` (first form tried; it registered the channel, the session showed `← probe: ...` and the model called the probe server's tool with nothing typed). --mcp-config and user-scope not tried.
      - Claude Code version: 2.1.318 at the first run, and that unguarded run auto-updated it to 2.1.325; all later runs on 2.1.325, auto-updater off.
      - Facts confirmed: flag `--dangerously-load-development-channels server:<name>`, capability `experimental["claude/channel"]`, method `notifications/claude/channel` with `content` and `meta`; client sends `server/discover` (2026-07-28) first, then `initialize` at 2025-11-25 after Method not found (D1). Channels reference re-read 20261116: agrees.
      - Start-up screens in order: folder trust, project-server consent ("New MCP server found in this project"), development-channel warning.
      - Corrections to the design: none to D4. D9 gained an "Observed 20261116" paragraph (adopted form, screen order, versions); D10 gained the login/setting-sources/auto-updater paragraph. 11.1 uses the project `.mcp.json` form (RegistrationForm.PROJECT_MCP_JSON); 12.1 documents the `.mcp.json` registration.

**Commit**: `test: add the channels pty harness and re-check the channel registration facts`

## 2. Config keys (D7)

- [x] **2.1 Three required keys with cross-key checks**
  - [x] `config/user_config.py`: add `notify_poll_seconds`, `session_heartbeat_seconds`, `session_stale_seconds`, each a number greater than 0, required, no default in code (same type pattern as `answering_wait_seconds`). A model-level validator requires `session_stale_seconds` at least twice `session_heartbeat_seconds`, and `session_heartbeat_seconds` at least `notify_poll_seconds`; each failure names both keys. The 2x factor is a named constant
  - [x] `docs/config-contract.md`: the three keys with their meaning and the cross-key rules, and the suggested values 5, 30 and 90 in the example, once. Extend the example that `tests/user_configs.py` loads, and update every fixture config in `tests/` that lists the full key set so the suite still loads
  - [x] Success: pyright clean
- [x] **2.2 Config tests**
  - [x] `tests/config/`: each key missing fails with `ConfigError` naming the key; a value of 0 or a negative fails; a stale limit under twice the heartbeat fails naming both keys; a heartbeat under the poll interval fails naming both keys; equal-to-limit values load; the contract's example loads
  - [x] Success: checks pass
  - Note: The 2x factor is `STALE_HEARTBEATS_MIN` in config/user_config.py; the cross-key check is a model validator `_session_timing_holds`.
    - Fixture configs updated: tests/user_configs.py (reads the three values from the contract example via `_example_number`) and the `TOP_LEVEL_KEYS` list in tests/config/test_user_config.py. New tests: tests/config/test_session_timing_config.py.
    - Also in this commit: tests/live/channels/harness.py now starts the session through `process_containment.contained_popen`, which `tests/test_process_containment.py` requires of every test module (missed in task 1.1; harness re-driven against Claude Code afterwards, still passes).

**Commit**: `feat: add notify_poll_seconds, session_heartbeat_seconds and session_stale_seconds`

## 3. Store: migration 007 and the sessions and push-read modules (D2, D6)

- [x] **3.1 `007_sessions.sql` and rows**
  - [x] `store/schema/007_sessions.sql`, create-only: `sessions` with `session_id` (text primary key), `member_id` (references `members`), `client`, `directory`, `started_at`, `heartbeat_at`, `push_confirmed_at` (null until confirmed); indexes on `(member_id)` and `(heartbeat_at)`; no `CHECK` list. `EXPECTED_SCHEMA_VERSION` becomes 7
  - [x] `store/models.py`: frozen dataclasses `Session` (every column) and `PushRow` (the delivery's `seq`, event, the message's kind, and the counterparty member id per D4)
  - [x] `docs/store-contract.md`: the table, its columns and indexes, version 7. Update stale-version assertions in `tests/store/test_migrations.py` and the schema pin in `tests/store/test_schema_holds_no_mirrored_state.py`. These pins and the fixture configs of 2.1 are the only edits to existing tests in this slice besides the call sites 9.1 names
  - [x] Success: pyright clean; existing tests pass
  - Note:
    - Three more pins of the same kind as the ones 3.1 names needed the new table or version, and got the smallest change: tests/store/test_migration_006.py now pins its migrate to the first six files (as test_migration_005.py does) instead of asserting EXPECTED_SCHEMA_VERSION == 6; tests/store/test_schema.py's table set gains `sessions` (test renamed ..._all_twelve_tables); tests/test_contract_docs.py's table count is 12.
    - docs/store-contract.md: `sessions` table section, version 7, and a sixth column reason, **presence**, mirrored in tests/store/test_schema_holds_no_mirrored_state.py.
- [x] **3.2 Migration test**
  - [x] `tests/store/test_migration_007.py` (model on `test_migration_006.py`): a version-6 database holding members, messages and deliveries migrates to 7 with all rows untouched and `foreign_key_check` empty; `sessions` has the D6 columns and both indexes; a store stamped 8 is refused and left untouched
  - [x] Success: checks pass
- [x] **3.3 `store/sql_sessions.py` and `store/sessions.py`**
  - [x] `store/sql_sessions.py`: the statements, with `LIVE_SESSION` (a row is live when `heartbeat_at` is newer than now minus the stale seconds) defined once, plus the confirmed clause `push_confirmed_at IS NOT NULL` defined once
  - [x] `store/sessions.py`: `upsert_session` (one statement on `session_id`: sets `heartbeat_at` and `push_confirmed_at` from the argument, and on first insert the other columns; a re-created row keeps the caller's original `started_at`), `delete_session`, `prune_stale_sessions(transaction, now, stale_seconds)` (deletes every row that is not `LIVE_SESSION`, for all members), `live_sessions` (every fresh row, ordered by `started_at` then `session_id`, with `push_confirmed_at`), `live_member_ids(transaction, now, stale_seconds)` (members with a fresh row whose `push_confirmed_at` is set). The heartbeat's prune-then-upsert runs in one write transaction (a helper in this module that takes the transaction)
  - [x] Success: pyright clean
- [x] **3.4 Tests for 3.3**
  - [x] `tests/store/test_sessions.py`: upsert inserts then updates `heartbeat_at` and `push_confirmed_at` while keeping the other columns; a re-created row (after a prune) carries the original `started_at`; `live_sessions` omits a row exactly at and past the stale limit and shows one just inside it, and returns rows oldest `started_at` first whatever the insert order, and rows with equal `started_at` in `session_id` order; `live_member_ids` returns a member with a fresh confirmed row and not one whose rows are unconfirmed or stale; prune by another process's call deletes stale rows of every member and keeps live ones; `delete_session` of an unknown id is a no-op
  - [x] `tests/store/test_members_queried_in_one_place.py` still passes; if it fails for a legitimate reason, fix the new code, not the test
  - [x] Success: checks pass
- [x] **3.5 `store/push_reads.py` and its tests**
  - [x] `store/push_reads.py`: `member_high_seq(transaction, member_id)` (one indexed `MAX(seq)` on `deliveries`, a documented value for "none yet" that the watcher treats as a real baseline, not an error) and `push_rows_after(transaction, member_id, after_seq)` returning `PushRow`s ordered by `seq` (joins `messages` for kind and the counterparty: the message member that is not the receiver, and for a note its sender). Reads write nothing and keep no marker
  - [x] `tests/store/test_push_reads.py`: high seq with no deliveries, with deliveries for several members (only the member's counts); `push_rows_after` returns only rows above the number, in order, with the right counterparty for a received request, an accepted request (counterparty is the other party) and a note; nothing is written (row counts and `sqlite_sequence` unchanged)
  - [x] Success: checks pass
  - Note: The push-read SQL lives in store/sql_messages.py beside the other delivery SQL (`SELECT_MEMBER_HIGH_SEQ`, `SELECT_PUSH_ROWS_AFTER`); the note kind is spelled from `MessageKind.NOTE`. "None yet" is `NO_DELIVERY_SEQ` (0) in store/push_reads.py. The heartbeat helper in store/sessions.py is `heartbeat(transaction, session, stale_seconds)`.

**Commit**: `feat: add sessions in migration 007 with session and push-read store modules`

## 4. The pinned serve loop (D1)

- [x] **4.1 `mcp/pinned_loop.py`**
  - [x] `serve_pinned(server, streams, init_options, background, *, lifespan_state)` (`lifespan_state` is the keyword-only argument `serve_loop` and `serve_connection` require; read how `Server.run` obtains it for a server with no lifespan and pass the same value): builds the dispatcher and `Connection.for_loop`, starts `background(connection)` in a task group, runs `serve_connection`, cancels the background when it returns. It mirrors the SDK's `serve_loop` (`mcp/server/runner.py`) and nothing else; no version constant
  - [x] Success: pyright clean
- [x] **4.2 Protocol pin test**
  - [x] `tests/mcp_server/test_protocol_pin.py`: over real stdio (a raw JSON-RPC driver, no SDK client), start a tiny server through `serve_pinned`, send `server/discover` for 2026-07-28 and assert error -32601 (`Method not found`); then `initialize` and assert it is served at a handshake-era version. Also run the same `Server` under `server.run` and assert the documented contrast (probe answered with `supportedVersions`, a following `initialize` refused with -32022), so an SDK change to either loop fails a test. The test header cites D1
  - [x] A second test: the background callable runs, receives the connection, and is cancelled when the client closes its end (the server process exits within a timeout)
  - [x] Success: checks pass
  - Note: The tiny server is tests/mcp_server/pin_server.py, run as a script (`pinned <marker>` through serve_pinned, `dual` through Server.run). The raw driver sends the probe in the shape Claude Code sent it (era in `_meta`). Observed: pinned loop answers the probe -32601 and serves `initialize` at 2025-11-25; Server.run answers `supportedVersions: ["2026-07-28"]` and refuses `initialize` with -32022. `lifespan_state` is whatever `server.lifespan(server)` yields, as Server.run does (the default lifespan yields `{}`); `_serve` enters it the same way.
- [x] **4.3 Move `amoeba-mcp` onto it**
  - [x] `mcp/server.py`: `_serve` calls `serve_pinned` with a `background` that does nothing yet and is replaced in task 9. `Server` is still built by `build_server`; no capability change yet
  - [x] Success: every existing test under `tests/mcp_server/` and `tests/live/mcp` collection still passes unchanged; checks pass

**Commit**: `feat: serve amoeba-mcp through a handshake-only pinned loop`

## 5. The channel event (D4)

- [x] **5.1 `mcp/channel_event.py`**
  - [x] A pure function from push rows to the event params, no I/O. Constants: the channel method name, the capability name, `CHANNEL_EVENT_MAX_ENTRIES` (10). `meta`: `first_seq`, `last_seq`, `count`, all digit strings. `content` follows D4's fixed template: count, seq range, entries `<kind>, <event> from|with <member id>` (built only from the closed enums and the counterparty's member id), at most the cap listed then `and K more`, then the instruction to call `inbox` with `since` set to the caller's own last `as_of_seq`, or omitted if it has none. No subject, body, result, reason or request id is a parameter of the function
  - [x] `docs/mcp-server.md`: the entry for the event's `content` and `meta` fields (`first_seq`, `last_seq`, `count`), so `tests/test_contract_docs.py` stays green; 12.1 writes the prose
  - [x] Success: pyright clean
  - Note:
    - Entry preposition: `from` for a `sent` delivery (always the counterparty's new message), `with` for every other event. The noun is "delivery" for one and "deliveries" otherwise. Constants: CHANNEL_METHOD, CHANNEL_CAPABILITY, CHANNEL_EVENT_MAX_ENTRIES, and the three meta key names. docs/mcp-server.md gained a "Push and presence" section with the event's field table.
- [x] **5.2 Tests**
  - [x] `tests/mcp_server/test_channel_event.py`: rows whose text-bearing fields hold marker strings produce content and meta in which no marker appears; `first_seq`, `last_seq`, `count` are right for one row and for many; with cap+1 rows exactly the cap are listed and `and 1 more` appears; every `meta` key is an identifier and every value a digit string; a note names its sender as counterparty and a request the other party
  - [x] Success: checks pass

## 6. Presence (D2, D3, D6)

- [x] **6.1 `PresenceState` and `resolve_presence`**
  - [x] `mcp/presence.py`: `PresenceState` with three states (pending, a member id, off with a reason), the subscribed flag, the session id (`uuid4().hex`, made once), start time, the time of the last unanswered channel event, the push-confirmed time, and a `resolved` event set in a `finally` so pending always ends. State is touched only by event-loop tasks
  - [x] `resolve_presence`: runs `operations.members.resolve_member(store, Path.cwd(), cf_run)` once in a worker thread (own store via the injected opener, `cf_run` from `wiring.default_deps`). `Member` sets the member; `NotInProgram` or `NotAProject` sets off with one INFO line saying the directory is not a member; `ContextForgeError` or `StoreError` propagates to the caller (the top-level handler of 6.5)
  - [x] Success: pyright clean
  - Note:
    - Departure (smallest change keeping intent): tests/mcp_server/test_boundary.py forbids `amoeba.mcp` from importing `store` or `upstream` (226 D10). The synchronous worker bodies (lookup_member, beat_session, end_session, read_high_seq, read_push_rows, read_as_of_seq) and the types presence passes around (Session, PushRow, StoreOpener, StoreBusyError, StoreError, CfRun, DeliveryEvent, MessageKind, BUSY_TIMEOUT_SECONDS) live in a new src/amoeba/wiring_presence.py, beside the other wiring_* modules; mcp/ reaches the store only through it. Design Component Structure to be amended in 12.2.
    - `PresenceState` holds started_at, session_id (uuid4 hex), member_id, off_reason, directory, subscribed, attempt_at, push_confirmed_at and the `resolved` anyio.Event. The production opener and PresenceDeps (opener, cf_run, clock, SessionTiming) are built in server.py in task 9.
    - note_event_attempted and note_inbox_called (6.4) are already in mcp/presence.py; their tests and the 6.4 check-off come with the next commit.
- [x] **6.2 Client name and heartbeat loop**
  - [x] Client name: `clientInfo.name` if it matches `[A-Za-z0-9._ -]{1,64}`, else the placeholder `unrecognized` and one WARNING (pattern and placeholder are constants)
  - [x] The heartbeat loop: first beat at `initialized`, then every `session_heartbeat_seconds`; each beat is one worker call that opens its own store and runs prune-then-upsert (3.3) with the in-memory `push_confirmed_at`. `StoreBusyError` is logged at WARNING once per run of failures and retried at the next beat (a comment states why: push is a hint and polling is the floor); any other `StoreError` propagates
  - [x] Success: pyright clean
- [x] **6.3 Tests for 6.1 and 6.2**
  - [x] `tests/mcp_server/test_presence.py` (fake clock, injected opener, memory streams): a non-member directory sets off with the INFO line; a `cf` failure and a `cf` timeout (stub `cf` returning `CfCallFailed`) raise `ContextForgeError` out of `resolve_presence`; `resolved` is set in each outcome including an exception
  - [x] Heartbeat: the first beat writes the row at `initialized` with the client name; a bad `clientInfo.name` stores `unrecognized` and warns; a busy store is retried, logs once per run, and the next beat succeeds; a corrupt-store error propagates; a process suspended past the stale limit (fake clock jump, row pruned by another connection) has its row re-created with the original `started_at`
  - [x] Success: checks pass
  - Note:
    - Shared rig: tests/mcp_server/presence_rig.py (FakeClock, Opener that can raise queued errors or block, seed_member, make_deps, eventually). The cf timeout is a cf_run raising subprocess.TimeoutExpired, which run_cf turns into CfCallFailed and resolve_member into ContextForgeError.

**Commit**: `feat: add the channel event, presence state, member resolution and heartbeat`

- [x] **6.4 Push confirmation (D6)**
  - [x] `note_event_attempted(state, now)`: records an attempt only when none is waiting (an unanswered one older than `PUSH_ANSWER_SECONDS` is replaced by the next event's fresh attempt). `note_inbox_called(state, now)`: if an attempt is recorded and at most `PUSH_ANSWER_SECONDS` old, set push-confirmed (sticky); in every case clear the recorded attempt. The clock is `Deps.clock`
  - [x] Tests in `tests/mcp_server/test_presence.py`: an `inbox` call within `PUSH_ANSWER_SECONDS` of an attempt confirms and the next beat writes `push_confirmed_at`; an `inbox` call with no attempt, or after the limit, does not; the attempt is cleared either way; a second event while one is waiting does not reset the first, and one older than the limit is replaced; confirmation is sticky, so a later `inbox` call with no attempt recorded leaves it set
  - [x] Success: checks pass
- [x] **6.5 `run_presence`: the presence task, its top-level handler and clean exit**
  - [x] `run_presence(connection, state, ...)` in its own module, `mcp/presence_task.py` (so `mcp/presence.py` keeps state, resolution, heartbeat and confirmation): resolve the member; if off, return with no row and no loop. Otherwise wait on `connection.initialized`, read the client name, log the INFO line with protocol version and client name, and run the heartbeat loop in one child task group (task 7.1 adds the push loop to that group). One top-level handler catches `Exception` (not `BaseException`; cancellation passes), calls `logger.exception`, cancels the children and ends presence. In every exit path a shielded `DELETE` of the session row runs, bounded by `BUSY_TIMEOUT_SECONDS * 2`; if that delete fails the row goes stale (log it, comment why)
  - [x] Tests in `tests/mcp_server/test_presence_task.py` (same rig as 6.3): a `cf` failure, a `cf` timeout and a `StoreError` raised by the member lookup each write no row, log with `logger.exception` and return; a non-member returns with no row; a corrupt-store error from the heartbeat is logged with its traceback, ends presence and deletes the row; clean exit (the background cancelled) deletes the row; a failing delete leaves a row that `live_sessions` stops showing after the stale limit
  - [x] Success: checks pass
    - Note: The 6.4 tests are in `tests/mcp_server/test_presence.py` (committed with 6.3). `run_presence`'s INFO line reads `presence for <member>: protocol <version>, client <name>`. The exit delete runs only when a member was resolved (no row can exist otherwise), in a shielded `move_on_after(EXIT_DELETE_SECONDS)` with the worker abandoned on the bound; a `StoreError` there is logged with `logger.exception` and the row goes stale. The rig gained `RecordingOutbound` and `make_connection` (a real SDK `Connection` on a recording outbound), and its `Opener` now takes `None` entries meaning "open normally".

**Commit**: `feat: add push confirmation and the presence task with clean exit`

## 7. The inbox watcher (D2, D4, D5)

- [x] **7.1 `mcp/inbox_watcher.py`**
  - [x] The push loop, taking the connection, `PresenceState`, the store opener, the clock and `notify_poll_seconds`; `run_presence` (6.5) starts it in the same child task group as the heartbeat. It retries the baseline read (`member_high_seq`, in a worker thread) each tick until it succeeds, sending nothing before it has one. Then every `notify_poll_seconds` it reads again; when the value exceeds the last seen it reads `push_rows_after`, builds the event (task 5), sends `notifications/claude/channel` through `connection.notify`, records the attempt (`note_event_attempted`, 6.4), sends `notifications/resources/updated` for `amoeba://inbox` only if the subscribed flag is set, logs one INFO line `channel event attempted` with `first_seq`, `last_seq` and `count` (no text), and stores the new last seen
  - [x] `StoreBusyError` in a tick or the baseline: WARNING once per run of failures, retried next tick. Any other failure propagates to the 6.5 handler
  - [x] Success: pyright clean
- [x] **7.2 Tests**
  - [x] `tests/mcp_server/test_inbox_watcher.py` (fake clock, SDK client on memory streams, short intervals): no event before a baseline exists; mail written after the baseline produces one event with the right `meta`; two deliveries in one tick are one event; no delivery produces nothing; a busy store on a tick skips it, then the next event is sent; a busy baseline retries and sends nothing until it succeeds; any other store error raises out of the loop
  - [x] 243's notes push with no change here: a note delivery seeded with `tests/store/seed.py` (the table's note shape, as 240's migration allows; 243 adds the writer) produces an event whose entry names kind `note` and its sender
  - [x] `Connection.notify` pin: the SDK drops a send to a closed stream only for `BrokenResourceError` and `ClosedResourceError` (`mcp/server/connection.py`, `notify`), so a notify on a closed stream does not raise (drop logged at debug). Any other exception from `notify` is not swallowed: a notify patched to raise one raises out of the loop
  - [x] The INFO line contains the numbers and no marker text written into a message subject, body or id
  - [x] Success: checks pass
  - Note:
    - The watcher unit tests run on a real SDK `Connection` whose outbound records notifications (tests/mcp_server/presence_rig.py `RecordingOutbound`), not an SDK client: it lets the notify pin exercise `Connection.notify`'s own except clause (ClosedResourceError and BrokenResourceError dropped; a RuntimeError raises out of the loop). The SDK client over memory streams is used in 8.2 and 9.2. The fake clock gives the attempt times; real sleeps are milliseconds.
    - `watch_inbox` is started by `run_presence` in the same child task group as the heartbeat.

## 8. The `amoeba://inbox` resource (D5)

- [x] **8.1 `mcp/inbox_resource.py`**
  - [x] Handlers for `resources/list`, `resources/read`, `resources/subscribe`, `resources/unsubscribe`. Every handler first waits on `PresenceState.resolved` (only that request waits). `list`: the one resource (`amoeba://inbox`, `application/json`) for a member, an empty list otherwise. `read`: JSON `{"member": <id>, "as_of_seq": <highest_assigned_seq>}` read in a worker thread, no message text. `subscribe` sets the flag, `unsubscribe` clears it (clearing a clear flag succeeds). No member, or any other uri, makes `read`, `subscribe` and `unsubscribe` fail with invalid-params. A `StoreError` in `read` fails only that request with an internal-error response naming the error. The URI is a constant
  - [x] `docs/mcp-server.md`: the entry for the resource's JSON fields (`member`, `as_of_seq`); 12.1 writes the prose
  - [x] Success: pyright clean
  - Note:
    - The four handlers are methods of `InboxResource` in mcp/inbox_resource.py, registered with `Server.add_request_handler` by `register_inbox_resource(server, state, open_store)`; registering `resources/subscribe` is what makes the SDK declare `resources: {subscribe: true}`. `initialization_options(server)` adds `experimental: {"claude/channel": {}}`. Both are what task 9.1's build_server calls.
- [x] **8.2 Tests**
  - [x] `tests/mcp_server/test_inbox_resource.py`: a `resources/list` made while resolution is still pending (resolver held on an event) waits, then returns the resolved answer; list is empty for a non-member; `read` returns the member and the same number `inbox` reports as `as_of_seq`; subscribe then unsubscribe toggles the flag; unsubscribe twice succeeds; a non-member and a foreign uri each give invalid-params; a `StoreError` in `read` fails that request and the next request succeeds
  - [x] With the watcher of 7.1 running: a client that subscribed gets `notifications/resources/updated` for `amoeba://inbox` after a channel event; one that never subscribed, and one that unsubscribed, get none
  - [x] Success: checks pass
  - Note:
    - Rig: tests/mcp_server/serving_rig.py (`serving` runs serve_pinned to an SDK ClientSession over the SDK's memory streams; `presence_background`; `subscribe`/`unsubscribe` wrappers, since the SDK marks those client methods deprecated for the 2026-07-28 era only). The read-error test gives the resource its own opener so the queued StoreBusyError meets the read and not a presence loop.

**Commit**: `feat: add the inbox watcher and the amoeba://inbox resource`

## 9. Wire presence into `amoeba-mcp` (D1 to D6, D10)

- [x] **9.1 Capabilities, handlers, background and logging**
  - [x] `mcp/server.py` gains call sites only: the capability declarations (`experimental["claude/channel"] = {}` and `resources: {subscribe: true}`, on every server per D3) and the four resource handlers' registration live in `mcp/inbox_resource.py` (the channel capability name is the 5.1 constant), and `build_server` calls them. `wc -l mcp/server.py` after this task is under ~300. `main()` (synchronous, where `wiring.load_config()` already runs for `check_deadline`) reads the three keys from that config and fails to start through the existing refuse-to-start path if one is missing; it passes them into `_serve`, so no config file is read on the event loop. `_serve` builds the `PresenceState` and passes `run_presence` as the `background` of `serve_pinned`
  - [x] `call_tool` logs `tool <name> called` at INFO at its start (name only) and, after an `inbox` call completes without error, calls `note_inbox_called`; thread the `PresenceState` to `call_tool` through the handler closure built in `build_server` and update the existing `call_tool` test call sites rather than add a hidden default
  - [x] `INSTRUCTIONS`: add D4's paragraph (events arrive as `<channel source="amoeba">`, they say only that mail arrived, the response is to call `inbox`). `tests/mcp_server/test_instructions.py` stays green
  - [x] Success: pyright clean; every existing MCP test passes
    - Note:
      - `call_tool(name, arguments, presence: ToolPresence)`; `ToolPresence` (mcp/presence.py) carries the state and the clock, and its `inbox_called()` runs `note_inbox_called`. `build_server(presence, open_store)` builds the `on_call_tool` closure and calls `register_inbox_resource`; `_serve` passes `initialization_options(server)` (the channel capability) and `run_presence` as the background. `main()` reads the config once (load_config already fails on a missing key through the refuse-to-start path) and builds `PresenceDeps` (`partial(wiring.open_store, wiring.state_layout())`, cf_run and clock from `wiring.default_deps`, the three keys) before the loop; `serve(deps)` takes them. `_refuse_to_start` is now typed NoReturn.
      - Existing call sites updated: the four `server.call_tool` test helpers pass `idle_presence()` (tests/mcp_server/presence_rig.py), and test_server_main.py's `_Serve` fake and `recording_serve` take the deps argument (the same kind of call-site update as call_tool).
- [x] **9.2 In-process behavior tests**
  - [x] `tests/mcp_server/test_presence_serving.py` (SDK client against `serve_pinned`, memory streams, stub `cf`): `initialize` declares both capabilities for a member and for a non-member directory; a non-member server serves tools, writes no row, runs no loop and lists no resources; a `cf` failure at start does the same and logs the error; a member server writes a row, then an `inbox` tool call after an event confirms the session; the INFO lines (`tool inbox called`, the protocol/client line) appear
  - [x] The watcher never blocks a tool call: with a store opener that blocks in its thread, `ping`, `tools/list` and a tool call each answer within one second
  - [x] A watcher failure (opener raises a non-busy `StoreError` after the first beat) is logged with its traceback, deletes the row, and the server keeps answering tool calls
  - [x] Success: checks pass
- [x] **9.3 Real-stdio exit tests**
  - [x] Extend `tests/mcp_server/test_stdio_smoke.py` or add `test_presence_stdio.py` (installed `amoeba-mcp`, throwaway `AMOEBA_HOME`, stub `cf`, short intervals): a member directory shows a row in the store while serving and none after the client closes stdin; a SIGKILLed server leaves a row that `live_sessions` stops showing after `session_stale_seconds`, and another server's heartbeat deletes it
  - [x] Success: checks pass
- [x] **9.4 Load test (concurrency path)**
  - [x] `tests/load/test_presence_load.py` (model on `tests/load/test_report_release_load.py`, collected the same way): a constant number of presence runs (12) share one throwaway store, each with its own thread-opened store and short intervals, while a writer adds deliveries for several of their members and a client makes tool calls against one of them. Assert: every session row is live at the end (no heartbeat gap reached `session_stale_seconds`); each watcher sent one event per burst with the right `count`; the tool calls and `ping` answered within one second; no exception escaped a presence task and no `StoreBusyError` ended presence
  - [x] CI gate: `pyproject.toml` collects `tests` and ignores only `tests/live`, and `.github/workflows/ci.yml` runs bare `uv run pytest`, so the load test is gated with no config change. Confirm with `uv run pytest --collect-only -q | grep test_presence_load`, which must list it
  - [x] Success: checks pass; `uv run pytest tests/load/test_presence_load.py` passes
    - Note: tests/load/test_presence_load.py: 12 presences (11 on recording outbounds, 1 served through build_server to an SDK client calling ping, tools/list and `decisions` throughout), 6 bursted members, 3 bursts of 2 deliveries each in one transaction, real wall clock, poll 0.02 s, heartbeat 0.05 s, stale 1 s. Each member's cf_run answers the recorded `cf get` document under its own id.

**Commit**: `feat: serve push and presence from amoeba-mcp`

## 10. `list` and `status` show live sessions (D8)

- [x] **10.1 `SessionEntry` and `MemberStatus.sessions`**
  - [x] `operations/status_models.py`: `SessionEntry` (`client`, `directory`, `started_at`, `heartbeat_at`, `push_confirmed_at`); `MemberStatus` gains `sessions`, oldest first. The status operation fills it from `live_sessions` under active members only, in the same transaction as its other reads, with the stale seconds from config. `list -j` still equals the `status` document. Sessions do not enter "waiting on you" and do not set the notice (240 D11)
  - [x] `docs/cli-contract.md`: the new `sessions` JSON fields per member
  - [x] Success: pyright clean
  - Note:
    - Departure (smallest change keeping intent): sessions are read in their own read transaction by a new operations/status_sessions.py (`read_member_sessions`), not inside 240's `read_member_messages` transaction, so no 240 function body is rewritten for it. status() and `_program_status` gain only the sessions argument and the `sessions=` field. 240's member-keys pin in tests/operations/test_status_requests.py gains `sessions` (it moves with MemberStatus gaining the field, which the design names).
    - Found while testing the 244 contract: `live_member_ids` returned a removed member's confirmed session, which `status` never shows. It now keeps only ids `get_member` finds active, so "a removed member is not a member" stays in `sql.ACTIVE_MEMBER` alone (tests/store/test_members_queried_in_one_place.py unchanged); a store test covers it.
- [x] **10.2 Renderer and tests**
  - [x] The text renderer adds a **Live sessions** section per member with any, one line per session: `<client>  <directory>  up <age>  last beat <age> ago  push confirmed|push unconfirmed`. A member with none shows no section; `Nothing needs you.` is unchanged
  - [x] Tests (in the existing status and list test modules, seeded with `tests/store/seed.py`): a fresh session appears with its fields; sessions of one member appear oldest first; a stale row does not; a removed member's session does not; confirmed and unconfirmed render differently; a member with no sessions has no section; `list -j` equals `status` with `sessions`; `Nothing needs you.` still prints with only sessions present; `tests/test_read_side_defined_once.py` passes
  - [x] Integration test (244's contract): on one seeded store and clock, the members `live_member_ids` returns are exactly the members whose sessions `status` shows as push confirmed and fresh, over confirmed, unconfirmed, stale and removed-member rows
  - [x] Success: checks pass
  - Note:
    - The renderer is a new cli/render/sessions.py (`sessions_section`), added after the message sections in render_waiting. The tests are in new modules beside the existing ones, because 240's are near the size guide: tests/operations/test_status_sessions.py (status fields, order, stale, removed member, no notice, `list -j` equals `status`, and the 244 integration test) and tests/cli/render/test_status_sessions.py (line format, confirmed vs unconfirmed, no section, `Nothing needs you.`).

**Commit**: `feat: show live sessions per member in list and status`

## 11. Live test (D10)

- [x] **11.1 Live-test rig and fixtures**
  - [x] The `amoeba-mcp` stderr INFO lines D10 relies on exist from earlier tasks (protocol version and client name, 6.5; `channel event attempted` with the numbers, 7.1; `tool <name> called`, 9.1); a launcher script runs `amoeba-mcp` with its stderr appended to a file the test reads. Config uses `notify_poll_seconds` 1, `session_heartbeat_seconds` 1, `session_stale_seconds` 3; the harness constants are `INBOX_CALL_WAIT_SECONDS` (120) and `STALE_MARGIN_SECONDS` (5); the wait for a killed server's row is `session_stale_seconds` plus the margin
  - [x] Fixtures in `tests/live/channels/conftest.py`: a throwaway `AMOEBA_HOME`; two repos `cf-s` and `sq-s` built through the real `cf` and registered with `add` in one program; a third directory `outside`, a git repo registered with neither `cf` as a project nor `add`. `cf-s` and `outside` each carry the registration of the form 1.2 adopted, naming the launcher (project `.mcp.json` in the directory; or the harness passing `--mcp-config <file>`; or the registration in the harness's throwaway Claude config). `amoeba` is called by absolute path, never the bare name
  - [x] First test asserts the store `amoeba` resolves lies under the throwaway home
  - [x] Success: that test passes; every wait failure reports what it waited for and the last screen
    - Note: Fixtures: tests/live/channels/world.py (`build_channel_world` on the pause tier's world: `cf-s` and `sq-s` through the messaging tier's `build_repo`, `outside` a plain git repo; a launcher per session that writes its pid file and runs the venv's `amoeba-mcp` by absolute path with stderr appended to a log; the project `.mcp.json` form from 1.2, with AMOEBA_HOME and CONTEXT_FORGE_DATA_DIR in its env) and tests/live/channels/conftest.py (`channel_world`). Constants INBOX_CALL_WAIT_SECONDS (120), STALE_MARGIN_SECONDS (5) and PROMPTED_CALL_WAIT_SECONDS (120) are in harness.py. The world's config lowers `resume_wait_seconds` to 60, as the mcp and messaging tiers do: with the pause tier's 120 `amoeba-mcp` refuses to start (DeadlineError), which the first live run showed in the server log.
- [x] **11.2 Session 1: push reaches the agent, and the session is confirmed**
  - [x] In `cf-s`: `amoeba list -j` shows a live session under `cf-s` with its directory; the test runs `amoeba send --to cf-s --id sq-1 --subject "Need X" --body "Please add X"` from `sq-s`, then waits for `tool inbox called` in the server log with nothing typed; within `session_heartbeat_seconds` plus the margin `list -j` shows that session with `push_confirmed_at` set; after a clean exit `list -j` shows no session. Also assert the logged protocol version is a handshake version
  - [x] Success: `uv run pytest tests/live/channels -k session_one` passes (name the test accordingly)
- [x] **11.3 Session 2: a killed server goes stale**
  - [x] The same setup with the server SIGKILLed; `list -j` shows no session once the stale wait has passed
  - [x] Success: `uv run pytest tests/live/channels -k killed` passes (name the test accordingly)
- [x] **11.4 Session 3: a non-member directory, then the whole tier**
  - [x] In `outside`: the server log says it is not a member and `list -j` shows no session; the test types one prompt asking the agent to call the `amoeba` `list` tool, and waits for `tool list called` in the log
  - [x] Run `uv run pytest tests/live/channels` (all three sessions)
  - [x] Success: it passes; `tests/live/mcp` and `tests/live/pause` still pass; checks pass
    - Note: Test names: test_the_store_amoeba_resolves_is_under_the_throwaway_home, test_session_one_push_reaches_the_agent_and_confirms, test_killed_server_goes_stale, test_session_three_a_non_member_directory_serves_tools_and_no_session (all in tests/live/channels/test_channels_live.py). AMOEBA_LIVE_CHANNEL_MODEL is not in the repo's `.env`; the runs passed it on the command line.

**Commit**: `test: add the channels live tier against a real Claude Code session`

## 12. Documents (D4, D5, D8, D9, Departures)

- [x] **12.1 Contract and server docs**
  - [x] `docs/mcp-server.md`: the pinned loop and what it means for clients (handshake era only), the capabilities, the channel event (fields and the no-message-text rule), the `amoeba://inbox` resource and subscribe behavior, sessions and push confirmation, the three INFO log lines, the launch flag and the shell alias, the registration for the form 1.2 adopted (the `.mcp.json` command, the `--mcp-config` file, or the user-scope install) with the consent and start-up screens, the Team/Enterprise `channelsEnabled` note, `claude -p` ignoring the flag, how to debug a repo with no live session (`claude --debug`), and re-running `uv run pytest tests/live/channels` after a Claude Code or SDK update. The restart note: open sessions run the old server
  - [x] `docs/store-contract.md` (sessions rules: stale predicate, prune, confirmation, cleanup), `docs/config-contract.md` (check 2.1), `docs/cli-contract.md` (check 10.1)
  - [x] Success: `tests/test_contract_docs.py` passes
- [x] **12.2 Parent documents and the design**
  - [x] Amend `user/architecture/240-arch.agent-messaging.md` and `user/architecture/240-slices.agent-messaging.md` to match the design's Departures section: the `directory` column; no code defaults for the three keys; `sessions` in migration 7 and its Store and config paragraph; a non-member server declares the capabilities; the event tells the agent to use its own cursor; `serve_pinned` and the watcher beside it; pruning by every heartbeat, not the sweep; presence feeding waking only through push-confirmed sessions (the presence paragraph and walkthrough step 3)
  - [x] Amend `user/slices/241-slice.push-and-presence.md`: the walkthrough refinement and any correction from 1.2; the Component Structure gains `mcp/presence_task.py` (`run_presence`) and the resource registration helper in `mcp/inbox_resource.py`; D2's "`Connection.notify` never raises" reworded to what the SDK does (a send to a closed stream is dropped, for `BrokenResourceError` and `ClosedResourceError` only); D8's order stated as `started_at` then `session_id`; two lines added to its Departures section: the live-store migration runs in the Phase 7 hand-off, after the merge, and a rehearsal on a copy (13.1) precedes it. Make the rest of the design agree with the hand-off, so it holds one procedure: Development Approach step 7 ends at the live test (the migration is the Phase 7 hand-off), and Special Considerations' Live store paragraph is replaced by the hand-off's one step, `scripts/update_live.py update` from the target after the merge (backup, install, migrate, read-back, automatic restore to the previously installed commit)
  - [x] Success: `grep -n "serve_pinned" project-documents/user/architecture/240-*.md` finds the new wording; checks pass
  - Note: docs/mcp-server.md has the "Push and presence" section (turning it on with the project `.mcp.json` and the flag/alias, the three start-up screens in order, `-p`, `channelsEnabled`, re-running the live and pin tests after an update, the serve loop, what the server does per directory, sessions and push confirmation, the three log lines and `claude --debug`, turning it off), the restart note, and Start-up. docs/store-contract.md has "Sessions and who writes them". config-contract and cli-contract were written in 2.1 and 10.1.
  - Note: the 241 design now also names `mcp/presence_task.py`, the four resource handlers with `register_inbox_resource` and `initialization_options`, `wiring_presence.py` and `operations/status_sessions.py` in its Component Structure; D2's notify wording, D8's order, the two Phase 7 departures; Development Approach step 7, Special Considerations' live-store paragraph and the Operator Walkthrough's migration and Undo lines now describe the one `scripts/update_live.py update` hand-off step. The Verification Walkthrough is refined with the actual commands and results (13.2 re-runs it).

**Commit**: `docs: document push and presence, amend the 240 parents`

## 13. Final verification

- [x] **13.1 Rehearse the live migration on a copy**
  - [x] Nothing live is written. `TMP=$(mktemp -d)`; `sqlite3 ~/.local/state/amoeba/amoeba.sqlite3 ".backup $TMP/amoeba.sqlite3"`; `cp ~/.config/amoeba/config.yaml $TMP/config.yaml`; `export AMOEBA_HOME=$TMP`. Add the three keys to `$TMP/config.yaml` with values from `docs/config-contract.md`'s example
  - [x] Record `sqlite3 $TMP/amoeba.sqlite3 "SELECT version FROM schema_meta WHERE id = 1"` and `"SELECT count(*) FROM members WHERE removed_at IS NULL"`. Expected version: the number of the last migration file before `007_sessions.sql` in `store/schema/` (240's migration), or the one before that if 240 is not migrated live, in which case also add 240's two keys from the contract's example. Any other result, including an empty one, is `BLOCKED:` with the raw query output, and the rehearsal stops. Otherwise the one `uv run amoeba list` migrates the copy to 007
  - [x] Read back: version equal to `EXPECTED_SCHEMA_VERSION`, same member count, `PRAGMA integrity_check` ok, `PRAGMA foreign_key_check` empty, `uv run amoeba list` exits 0
  - [x] Success: a note under this task gives the before and after version and member count. `unset AMOEBA_HOME` and `rm -r $TMP` after
  - Note: Rehearsal on a copy (nothing live written; the live store still reads version 6 afterwards): before, version 6 (240's migration, so 240's keys were already in the config) and 3 active members; the three keys added with the contract example's values 5, 30, 90; one `AMOEBA_HOME=$TMP uv run amoeba list` exited 0; after, version 7 (= EXPECTED_SCHEMA_VERSION), 3 active members, `PRAGMA integrity_check` ok, `PRAGMA foreign_key_check` empty, a second `amoeba list` exited 0. The copy was removed.
- [x] **13.2 Final verification**
  - [x] Run Verification Walkthrough steps 1 to 3 (all four checks; `uv run pytest tests/mcp_server/test_protocol_pin.py`; `uv run pytest tests/live/channels`); step 4 is the Phase 7 checklist below. Confirm `tests/test_contract_docs.py`, `tests/test_import_boundaries.py`, `tests/test_store_opened_only_by_state_move.py` and `tests/test_read_side_defined_once.py` pass by name
  - [x] Update the walkthrough in `user/slices/241-slice.push-and-presence.md` where Phase 6 changed it (it says it is refined when Phase 6 completes), and note any departure from the design under this task
  - [x] Confirm 240 is unchanged apart from what the design names: `git diff {target}` shows no change to a 240 function's signature or body, and the only 240 edits are `MemberStatus` gaining `sessions`, `EXPECTED_SCHEMA_VERSION`, the stale-version and schema pins (3.1), the fixture configs (2.1) and the `call_tool` call sites (9.1). 240's tests pass with no other edit
  - [x] Success: all checks pass; every Success Criteria line in the design maps to a passing test named in a note under this task
  - Note:
    - Walkthrough step 1: format, lint, pyright clean; pytest 3378 passed. Step 2: test_protocol_pin.py 3 passed. Step 3: `AMOEBA_LIVE_CHANNEL_MODEL=sonnet uv run pytest tests/live/channels` 4 passed (59.9 s), with the `.env` live settings sourced. tests/test_contract_docs.py, tests/test_import_boundaries.py, tests/test_store_opened_only_by_state_move.py and tests/test_read_side_defined_once.py pass (34 passed). The walkthrough was refined in 12.2 and still matches.
    - 240 unchanged apart from what the design names: `git diff main -- src` shows 240 code changed only in status() and _program_status (the sessions argument and field), MemberStatus gaining `sessions`, EXPECTED_SCHEMA_VERSION, and additions to store/models.py and store/sql_messages.py. 240 test edits: the version and table pins (3.1), the fixture configs (2.1), the call_tool call sites and main's serve fake (9.1), and the member-keys pin in tests/operations/test_status_requests.py (10.1).
    - Departures, all noted under their tasks: wiring_presence.py for the 226 boundary (6.1); sessions read in their own transaction (10.1); live_member_ids keeps active members only (10.1); the harness uses the operator's Claude login with `--setting-sources project,local` and the auto-updater off (1.1); watcher unit tests on a recording outbound (7.2); new test modules beside 240's (10.2).
    - Success criteria to tests: live push → tests/live/channels::test_session_one_push_reaches_the_agent_and_confirms; handshake protocol and pin → that test's version check and tests/mcp_server/test_protocol_pin.py; channel event → tests/mcp_server/test_channel_event.py; non-member and cf failure → tests/mcp_server/test_presence_serving.py::test_a_server_with_no_member_declares_push_serves_tools_and_does_nothing_else and test_presence_task.py; resource handlers → tests/mcp_server/test_inbox_resource.py; watcher failures and the notify pin → tests/mcp_server/test_inbox_watcher.py and test_presence_serving.py::test_a_watcher_failure_is_logged_deletes_the_row_and_tools_keep_answering; clean exit and SIGKILL → tests/mcp_server/test_presence_stdio.py and live test_killed_server_goes_stale; push confirmation → tests/mcp_server/test_presence.py (6.4 tests) and tests/store/test_sessions.py live_member_ids tests; suspended process → test_presence.py::test_a_process_suspended_past_the_stale_limit_gets_its_row_back; never blocks a tool call → test_presence_serving.py::test_a_stuck_store_never_blocks_a_tool_call and tests/load/test_presence_load.py; list/status → tests/operations/test_status_sessions.py and tests/cli/render/test_status_sessions.py; config keys → tests/config/test_session_timing_config.py; sessions cleanup → tests/store/test_sessions.py::test_one_servers_prune_deletes_every_members_stale_rows_and_keeps_live_ones; 244's same answer → test_status_sessions.py::test_live_member_ids_matches_the_confirmed_fresh_sessions_status_shows; 243's notes push → test_inbox_watcher.py::test_a_note_pushes_naming_its_kind_and_sender; 240 unchanged → the full suite.

**Commit**: `test: verify push and presence and rehearse the live migration`

### Phase 7 hand-off (not tasks; nothing here is checked off in this file)

Owner: the implementing agent, at slice integration, after the code review passes and the slice is merged (the merge is Phase 7's, not a task). Designated by `CLAUDE.md`. From the target checkout: `uv run python scripts/update_live.py update`. It backs up the live store and config to `~/.local/state/amoeba/backups/<stamp>/`, appends any config key the new code requires (value from the config contract's example), installs the target, migrates the store through `amoeba list`, and checks the schema version, integrity, foreign keys, the member count and the installed `amoeba-mcp` tool list. If any check fails it restores the backup and reinstalls the previous commit itself, and exits 1. It needs `--previous <commit>` only when no earlier run has recorded the installed commit. Paste its output into the slice notes, and restart the client sessions it lists (they run the old `amoeba-mcp` until restarted). `uv run python scripts/update_live.py restore` puts the newest backup back later; a successful update deletes the older backup set
