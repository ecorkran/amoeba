---
docType: tasks
slice: sessions-across-machines
project: amoeba
lld: user/slices/263-slice.sessions-across-machines.md
dependencies:
- 260-slice.hub-and-door
- 261-slice.members-by-name
- 262-slice.local-work-through-the-hub
projectState: Slices 220 to 244 and 260 to 262 are merged on main. Package version 0.2.9,
  store schema 13 (migrations 001 to 013), DOOR_VERSION 2, MCP_CALL_DEADLINE_SECONDS 180
  (in mcp/in_process.py). amoeba-mcp opens the store itself with two loops (heartbeat
  and inbox watcher). sq 0.24.38 and cf 0.19.28, read with `sq --version` and
  `cf --version` at breakdown, 20261124.
dateCreated: 20261124
dateUpdated: 20261124
status: not_started
---

# Tasks: Sessions Across Machines

## Context Summary

- Working on slice 263 (design: `user/slices/263-slice.sessions-across-machines.md`; decisions D1 to D15 are cited by number, success criteria by their opening words). `amoeba-mcp` becomes a client of the hub. Its two loops become one **tick**: one `session_tick` step per `notify_poll_seconds` that refreshes the session row, returns the member's new deliveries and the work flag. `list` and `status` show every session on every machine, who is behind the hub's door version, and each other machine's last reported runs. The PM's install has no client file and runs the same tick on its local store. Next slice: 264 (`amoeba adopt`, deletes the local-store way).
- **Precondition: 260, 261 and 262 are merged on the target.** Checked at breakdown on 20261124: `EXPECTED_SCHEMA_VERSION` 13, `DOOR_VERSION` 2. This file uses their names: `wire.protocol` (`SERVED_OPERATIONS`, `STEP_CALLS`, `WRITING_STEPS`), `wire.times` (`DoorTimes`, `CALL_BOUND_SECONDS`), `operations/steps/` (`models`, `dispatch`, `limits`, `work`), `operations/store_steps.py` (`Steps`, `LocalSteps`), `operations/errors.py` (`OPERATION_ERRORS`), `operations/caller.py` (`find_caller`), `operations/here.py`, `hub/calls.py` (`handle_call`), `hub/call_work.py`, `hub/admin.py`, `store/machines.py` (`touch_machine`, `remove_machine`), `store/sessions.py`, `store/push_reads.py`, `wiring_steps.py` (`DoorSteps`, `steps_for`, `after_operation`, `after_call`), `client/call.py`, `tests/hub/in_process_hub.py`, `tests/hub_fixture.py` (`two_machine_hub`, `ClientHome`), `tests/load/test_door_load.py`.
- Paths: no prefix means under `src/amoeba/`. `tests/`, `docs/`, `scripts/` are from the repo root; `user/` means `project-documents/user/`.
- New modules (Component Structure): `operations/steps/session.py`, `store/schema/014_sessions_across_machines.sql`, `store/machine_runs.py`, `mcp/tick.py`, `mcp/after_runner.py`, `cli/render/machines.py`. Added by this breakdown: `hub/call_sessions.py` (the touch rules and the behind refresh, 5.2: `hub/calls.py` is 333 lines and gets call sites only), `operations/status_machines.py` (7.1), `tests/store/schema_13.py` (2.3), `tests/mcp_server/long_call_server.py` and `tests/live/channels/test_long_call_live.py` (1.2), `tests/hub_mcp.py` (8.1). Replaced: `mcp/inbox_watcher.py` and the heartbeat loop in `mcp/presence.py` by `mcp/tick.py` (4.6 deletes them); `tests/mcp_server/test_inbox_watcher.py` and the heartbeat-loop tests in `tests/mcp_server/test_presence.py` by `test_tick.py` (4.2, 4.6).
- **Names that differ from the design, found at breakdown.** The after-step is `wiring_steps.after_operation` and `after_call` (the design says `wiring_steps.after_call`; it appears in Interfaces Required); the MCP-door after-step test is `tests/test_after_step.py::test_the_mcp_door_starts_the_ended_held_question_too` (the file was renamed from `tests/test_wiring_release.py` in 262); `CHANNEL_EVENT_MAX_ENTRIES` is in `mcp/channel_event.py` and the hub may not import `amoeba.mcp`, so 3.1 moves it to `wire.protocol`. Each is a small conflict under the Amoeba Design Rules: the task uses the real name and the design text is updated in 0.1.
- **The step flag is two flags.** The design's Amendments row for 262 D3 has one flag mean both "the step runs in a write transaction" and "its result is kept", and says the session steps write with it unset. `Step.writes` is both today (`operations/steps/model_base.py`), and `run_step` takes `store.write()` only when it is set, so the design cannot be built as written. 3.1 adds `keeps_result` beside `writes` and the design text follows in 0.1; this is a small conflict (no behavior, scope or stored data changes).
- Closed values are defined once and imported: `TICK_TIMES`, `TICK_BOUND_SECONDS` (13) in `wire.times`; `MCP_CALL_DEADLINE_SECONDS` (300) in `wire.times`; the two step names in `STEP_MODELS` mirrored as strings in `wire.protocol.STEP_CALLS` (not `WRITING_STEPS`), with 262's test that they agree; the four header names, the session id pattern and `CLIENT_NAME_PATTERN` in `wire.protocol`; `TICK_SECONDS_BEFORE_FIRST_REPLY` (5) and `CF_REASK_SECONDS` (60) in `mcp.tick`; the SQL predicates `LIVE_SESSION` and the waking rule in `store/sql_sessions.py`.
- Clocks (D5): no step request carries a date or time field; every session time is the hub's. The client's monotonic clock measures only `PUSH_ANSWER_SECONDS`.
- SQL (Design Rules): values bind with `?`; an f-string builds SQL only from module-level constants.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. "Checks pass" means all four, with no failure beyond the baseline noted in 0.2.
- Tests use the autouse `AMOEBA_HOME` fixture, `tests/store/seed.py`, `tests/store_open.py`, `tests/cf_stub.py`, `tests/sq_stub.py`, `tests/fault_injection.py`, `tests/hub/in_process_hub.py` (`DoorHooks`, the settable clock) and `tests/hub_fixture.py`. Destructive SQL runs only against throwaway stores.
- **Existing tests.** In the task that makes a change, update mechanically every test that builds a changed type, calls a changed signature, patches a moved or deleted name, or pins a set, count or text the change alters, without changing what it asserts; note the modules touched under the task. Beyond that, the design names the tests that change what they assert: the six kinds of edit in its Migration Plan (4.7), the after-step test (4.5), the deadline tests (6.1), and `test_values_equal_to_both_limits_load` in `tests/config/test_session_timing_config.py` (2.4). If any other test fails, fix the code, not the test.
- `tests/test_contract_docs.py` requires each new column, value, flag and field in the contract docs, so the task that adds one adds its entry; 9.2 writes the prose.
- Production state: no task writes the live store or config. Migration 014 rides the next release through `scripts/update_live.py update`; 9.3 tests the script on copies. 2.4 only reads the live config's three timing keys.
- Work on branch `263-slice.sessions-across-machines` (0.2). Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.

## 0. Setup (effort 1)

- [x] **0.1 Target and prerequisites**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty. `git checkout {target}`. The design and this task file are committed there, with no other uncommitted change
  - [x] Confirm 260 to 262 are merged: `store/schema/013_local_work.sql` exists, `EXPECTED_SCHEMA_VERSION` is 13, and each name in the Context Summary's precondition exists (`grep -rn`)
  - [x] Update the design text for the name differences in the Context Summary: the after-step name in Interfaces Required, the test name and the channel constant where the design uses them (Component Structure, D2, D7), and the Amendments row for 262 D3 (the flag is two flags: `writes` and `keeps_result`). Note the change under this task
  - [x] Bring the Amendments table into the designs it amends: for each row, open the design it names (`user/slices/260-slice.*.md`, `user/slices/262-slice.*.md`) and check it states the amendment in its own terms where it applies (260's entry-point table and D2 among them, for the removed served check and the deadline note); where it does not, add it. Note each file and row touched under this task
  - [x] Run `sq --version` and `cf --version` and note both
  - [x] Success: the target is checked out and clean; a note gives the target and both versions; each Amendments row is stated in the design it names
  - If a prerequisite is missing, write `BLOCKED: <what is missing>` under this task and stop.
- [x] **0.2 Branch and baseline**
  - [x] `git checkout -b 263-slice.sessions-across-machines {target}`; if it exists, `git checkout 263-slice.sessions-across-machines`
  - Note: the branch already existed and was checked out, so the checkout step was not needed.
  - [x] Run the checks once; list any failure present before this slice by test name, unfixed
  - [x] Success: `git branch --show-current` prints the slice branch; the baseline is noted

## 1. Client facts before building (D15 step 1; effort 3)

- [x] **1.1 The pin test and the channel tests**
  - [x] Run `uv run pytest tests/mcp_server/test_protocol_pin.py`, then the live channel tests: `set -a; source .env; set +a; AMOEBA_LIVE_CHANNEL_MODEL=sonnet uv run pytest tests/live/channels -v`
  - [x] Note `claude --version` and the installed `mcp` version. If either differs from the dated facts in `docs/mcp-server.md`, correct those facts there
  - [x] Success: the pin test and the live channel tests pass, or the cause of a failure is in the notes; the versions are noted
- [x] **1.2 The long-call server and test**
  - [x] `tests/mcp_server/long_call_server.py`: a small stdio server built on `serve_pinned` as `tests/mcp_server/pin_server.py` is, with one tool that waits 220 seconds and returns a marker string. No hub, no Amoeba store
  - [x] `tests/live/channels/test_long_call_live.py`: register the server with the existing harness and no timeout setting of its own, ask a real Claude Code session to call the tool, wait 300 seconds and one model turn for the marker to show, and record what the session showed at two minutes
  - [x] Success: the test runs and reports which of D15 step 1's three results occurred
  - Note: the harness gained `SessionSpec.as_channel` (default True), so a non-channel server such as the long-call server loads as a plain server.
- [x] **1.3 Run it and act on the result**
  - [x] Run the test. Append a `## Slice Notes` section to the design (this section is where later tasks put their notes) with the result, the settings used and the measured times
  - [x] If the marker reached the agent: set nothing. If it did not: rerun with `CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS=0` in the session's environment; if the marker then arrives, the live fixtures set it from now on and the test keeps it. If it still does not arrive, the test asserts that outcome and the notes say `docs/mcp-server.md` and the `answer` tool's description must say to read the outcome with `list` (9.2 writes them)
  - [x] Success: the test passes with the settings of the result it had; the notes give the result, settings and times

**Commit**: `test: add the long-call live test and record the client facts`

## 2. Migration 014, the store and the third config check (D5, D6, D13; effort 4)

- [x] **2.1 `store/schema/014_sessions_across_machines.sql`**
  - [x] `sessions.client_version` (text) and `sessions.door_version` (integer), both nullable, with a `BEFORE INSERT` trigger that aborts when either is null, worded like 260's owner triggers
  - [x] `machines.door_version`, integer, nullable
  - [x] `machine_runs`: `machine_id` (key, references `machines`), `owner_id`, `reported_at`, `document` (JSON text), with 260's owner trigger
  - [x] `EXPECTED_SCHEMA_VERSION` becomes 14. Update the schema-version pins, `tests/store/test_migration_013.py`'s among them
  - [x] `COLUMN_REASONS` in `tests/store/test_schema_holds_no_mirrored_state.py`, using its existing reasons: the three new columns beside their tables' others, and `machine_runs`' columns under the reason that fits a stored report
  - [x] `docs/store-contract.md`: the three columns, the table, the trigger, and that every time in `sessions` is the store's own clock
  - Note: migration 014 written (sessions.client_version/door_version with trigger sessions_versions_required; machines.door_version; machine_runs with trigger machine_runs_owner_required). EXPECTED_SCHEMA_VERSION is 14. No test pinned the literal 13 (tests use EXPECTED_SCHEMA_VERSION), so no schema-version pin needed editing, test_migration_013 included. COLUMN_REASONS: machines.door_version under ownership, the two session columns and the four machine_runs columns under presence (its reason text in docs/store-contract.md was widened to cover a machine's stored report). Contract doc names the columns, the table, the trigger and that every time in sessions is the store's own clock. tests/store/schema_11.py TABLES, tests/store/test_schema.py TABLES and tests/test_contract_docs.py (table count 19 to 20) gained machine_runs (mechanical).
- [x] **2.2 Store functions**
  - [x] `Session` (in `store/models.py`) gains the two versions, with no defaults. Every place that builds or reads one changes in this task, so pyright passes at the commit: `_SESSION_COLUMNS` and the positional reader in `store/sessions.py` (`sql_sessions.py`) select the two columns; `mcp/presence.py::_session` passes the running program's client version and `DOOR_VERSION` (4.6 deletes it with the heartbeat loop); `tests/store/seed.py` and the other test builders (2.3)
  - [x] `UPSERT_SESSION` (`store/sql_sessions.py`): the conflict clause also sets `client_version` and `door_version`, and carries `WHERE sessions.machine_id = excluded.machine_id` so another machine's session id is never refreshed. `upsert_session` checks that one row was affected and raises `StoreError` when none was. `heartbeat` writes both versions
  - [x] `LIVE_SESSION` becomes "fresh heartbeat and a door version"; the waking rule is `LIVE_SESSION`, push confirmed, and a door version equal to a bound parameter. `live_member_ids` takes the hub's door version. Its one caller is `store/wakes.py::wake_due` (line 141): `StepEdges` (`operations/steps/dispatch.py`) gains `door_version`, the version the program serving the call runs, `StepContext` carries it, and `wake_due` takes it from there (find its callers with `grep -rn wake_due src`). Local and CLI paths set it to `DOOR_VERSION`; 5.2 makes the hub set it from the version it serves, so a test that serves another version changes the waking rule too
  - [x] `store/machine_runs.py`: put (upsert with the given time), get one, get all, delete for a machine. `store/machines.py`: `touch_machine` writes `door_version` beside the client version, with a flag that leaves both versions as they are; `SELECT_MACHINES` (`store/sql_machines.py`) selects `door_version` and `MachineRow` gains it; `remove_machine` deletes the machine's `machine_runs` row first (the key references `machines`). It already deletes the machine's session rows
  - Note: wake_limits(config, door_version) and WakeLimits.door_version are required; StepEdges.door_version defaults to wire.times.DOOR_VERSION (local and CLI paths), StepContext.door_version carries it; operations-level callers (send_write, wake, wake_status) and hub/calls.py pass DOOR_VERSION for now: 5.2 makes the hub pass the version it serves. hub/calls.py passes door_version None to touch_machine until 5.2 parses the header. New modules store/machine_runs.py, store/sql_machine_runs.py and src/amoeba/program_version.py (the installed package version, shared by client/call.py and mcp/presence.py, which cannot import amoeba.client). Small conflict: StepEdges has a default (design says set by local paths) to avoid editing ~35 test builders; recorded here.
- [x] **2.3 Store tests** (`tests/store/test_migration_014.py`, helper `tests/store/schema_13.py` modeled on `schema_12.py`)
  - [x] A schema-13 store migrates: row counts unchanged; a session insert with a null client version or door version is refused; a pre-migration session row is not returned by `live_sessions` or `live_member_ids` and the next prune deletes it
  - [x] `machine_runs`: one row per machine, replaced by an upsert; `remove_machine` deletes it
  - [x] A behind session (door version not the bound one) is in `live_sessions` and not in `live_member_ids`; a push-confirmed current one is in both
  - [x] `upsert_session` for a session id owned by another machine raises `StoreError` and changes no column of that row
  - [x] `touch_machine` with and without the leave-versions flag
  - [x] Update mechanically `tests/store/test_sessions.py`, `test_wake_due.py`, `seed.py` and any other test that builds a `Session`, a `MachineRow` or `StepEdges`; note the modules touched
  - [x] Success: checks pass
  - Note: tests/store/test_migration_014.py and tests/store/schema_13.py written. Mechanically updated tests that build Session, WakeLimits, wake_limits, live_member_ids, touch_machine or work_waiting: tests/hub/test_across_machines.py, test_door_faults.py, test_rm_machine_work.py; tests/load/test_door_steps_load.py; tests/operations/test_add_wake_command.py, test_message_sweep_wrapper.py, test_send_wakes_across_machines.py, test_status_sessions.py, test_wake_after_send.py, test_wake_mark.py, wake_run_support.py, work_support.py; tests/store/test_acting_machine.py, test_machine_on_rows.py, test_machines.py, test_sessions.py, test_wake_due.py, test_wakes.py, wake_support.py.
- [x] **2.4 The third config check** (`config/user_config.py`, D5)
  - [x] `session_stale_seconds` must be at least `session_heartbeat_seconds + 2 * notify_poll_seconds`; a config that fails is refused at load naming the three keys, as the other two checks do
  - [x] Tests (in `tests/config/`): the example config loads; heartbeat 5, poll 5, stale 10 is refused naming the three keys; stale exactly at the sum passes and one second below is refused. `test_values_equal_to_both_limits_load` (`tests/config/test_session_timing_config.py`, heartbeat 7, poll 7, stale 14) fails the new check, so its assertion changes: it loads the least value that meets all three limits, `max(STALE_HEARTBEATS_MIN * heartbeat, heartbeat + 2 * poll)`, and asserts that value. Raise any other test rig whose timings fail the check to values that pass, without changing what the test asserts
  - [x] `docs/config-contract.md` names the check
  - [x] Read, without writing, the three timing keys in `~/.config/amoeba/config.yaml` and confirm they pass the check; note the values
  - [x] Success: checks pass; a note gives the live config's three values
  - Note: third check added; test_values_equal_to_both_limits_load renamed test_values_equal_to_all_three_limits_load per the task; no other rig failed the check. Live config (read only): notify_poll_seconds 5, session_heartbeat_seconds 30, session_stale_seconds 90; passes (90 >= 30 + 10).

**Commit**: `feat: add migration 014 and the third session timing check`

## 3. The session steps (D2, D5, D6; effort 4)

- [ ] **3.1 Names, models and constants**
  - [ ] `operations/steps/model_base.py`: `Step` gains `keeps_result`, "its reply is kept through the door"; `writes` stays "its transaction is a write" and is all `run_step` reads (`dispatch.py:93`). Every existing step row in `operations/steps/models_*.py` sets `keeps_result` explicitly, equal to its `writes` today. `wiring_steps.py` (the "hub applied the step" text, line 125) and the `WRITING_STEPS` derivation read `keeps_result`
  - [ ] `operations/steps/models.py` and `dispatch.py`: `session_tick` (request: `here`, `session_id`, `client`, `directory`, `last_seen`, `push_confirmed`; reply: member id and name or the reason, `high_seq`, `first_seq`, `count`, `entries`, `as_of_seq`, `notify_poll_seconds`) with `writes` true, `keeps_result` false and `needs_config` true (it reads the three timing keys; `run_step` loads config only when the row sets it); `session_end` (request: `session_id`; empty reply) with `writes` true, `keeps_result` false and `needs_config` false. Reply models forbid other fields; an entry is `seq`, `event`, `kind`, `counterparty` and nothing more
  - [ ] `wire.protocol`: both names in `STEP_CALLS` and not in `WRITING_STEPS`; the four header names (`Amoeba-Session-Id`, `-Project`, `-Client`, `-Directory`), the session id shape (32 hex), and `CLIENT_NAME_PATTERN` moved from `mcp/presence.py` (which imports it); `CHANNEL_EVENT_MAX_ENTRIES` moves here from `mcp/channel_event.py` (which imports it)
  - [ ] `wire.times`: `TICK_TIMES` (the default times with `retry_seconds` 0) and `TICK_BOUND_SECONDS` (connect plus read, 13)
  - [ ] The "hub applied the step" text in `DoorSteps` stays tied to `keeps_result`; session steps do not set it
- [ ] **3.2 `operations/steps/session.py`** (plain functions on a store, a config and a clock; under 300 lines)
  - [ ] `session_tick` per D2: the member from `find_caller`; with none, delete this session's row and return the reason, reading nothing else. The row is due when it is missing, its heartbeat is `session_heartbeat_seconds` old, its member differs, or `push_confirmed` is true and its `push_confirmed_at` is null; then one write deletes stale rows of every member and upserts this row with the hub's time and the running program's versions. Deliveries: the member's high number; when `last_seen` is given and lower, the entries above it, at most `CHANNEL_EVENT_MAX_ENTRIES`, with the count and the first number. `as_of_seq` is the highest number assigned to anyone. The upsert is 2.2's guarded one: another machine's session id raises `StoreError`
  - [ ] `session_end`: delete the row if it belongs to the calling machine; an id with no row is done
  - [ ] `write_behind_session(...)` for the refusal path (5.2): upsert the row with the caller's two versions and the hub's time, given the machine, member and header values
  - [ ] Success: the functions import only store, config and operations modules (no `amoeba.mcp`, no `amoeba.client`)
- [ ] **3.3 Step tests** (`tests/operations/test_session_steps.py`)
  - [ ] One test per case of D2's due rule (no row, heartbeat old, member changed, push confirmation new, none due changes no row); a refresh deletes stale rows of other members; times are the hub clock's and a client-side clock an hour ahead changes nothing stored
  - [ ] Deliveries: no entries without `last_seen`; a cap of ten with the right count and first number; `as_of_seq` is the global high; a test seeds messages whose subject, body, result and reason hold marker strings and asserts none is in a reply
  - [ ] No member deletes the row and returns the reason; a session id on another machine fails with `StoreError`; `session_end` deletes, ignores a missing id, and ignores another machine's row
  - [ ] A row written by a tick after `session_end` is not live once `session_stale_seconds` has passed on the hub's clock, and the next refresh by any session deletes it
  - [ ] `TICK_TIMES.retry_seconds == 0`; both step names are in `STEP_CALLS` and not in `WRITING_STEPS`; both rows have `writes` true and `keeps_result` false, and `run_step` takes `store.write()` for them (a counting store, as `tests/operations/test_wake_after_send.py` has); `session_tick` loads config and `session_end` does not; `steps.models` holds no date or time field
  - [ ] Two pins change, named: `tests/wire/test_protocol.py` (line 121, `len(STEP_CALLS) == 16` becomes 18; line 122 derives the writing steps from `keeps_result`, so 262's `STEP_CALLS`/`STEP_MODELS` agreement test still holds) and `tests/load/test_door_steps_load.py` (line 331, `set(timings) == set(STEP_CALLS)`: `_step_documents()` gains a document for each new step)
  - [ ] Success: checks pass

**Commit**: `feat: add the session_tick and session_end steps`

## 4. The tick on the local store (D1, D3, D4, D7, D10; effort 5)

Between 4.4 and 4.7 the tests that touch what moved or is deleted fail by design; "checks pass" is judged at 4.7, before the commit.

- [ ] **4.1 `mcp/tick.py`**
  - [ ] The loop: one pass is the member lookup (D3), one `session_tick` step in a worker thread, the reply handled on the event loop, then a sleep of the reply's `notify_poll_seconds` that starts when the pass ends. Before any reply the sleep is `TICK_SECONDS_BEFORE_FIRST_REPLY`. The worker thread enters `steps_for` itself and leaves it when the pass's step returns: a sqlite connection cannot cross threads, so a `Steps` is never passed between threads
  - [ ] Member lookup (D3): `cf` is asked until it answers with a project id, kept for the process; "not a project" is sent and asked again once `CF_REASK_SECONDS` old; a `cf` failure or timeout skips the tick. The caller is gathered by `operations.here`; `wiring_presence.py` shrinks to that gather, the two step calls, and the re-exports of the store and config error types
  - [ ] Baselines and events: no `last_seen` on the first pass or after the way changed; a reply whose `high_seq` is below the last one takes a new baseline and sends no event; a rise sends one channel event built by `mcp.channel_event` from the reply's entries and count. `PresenceState` holds the last seen number, push confirmation (measured on the monotonic clock), the newest reply's member and `as_of_seq`, and the last error; `resolved` is set when the first pass ends, reply or not
  - [ ] Failures (D4): every operational failure skips the tick (no reply, any refusal, `ClientFileError`, a `cf` failure, and with no client file `StoreError` or `ConfigError`); one WARNING when a run starts or its error type changes, one INFO `tick recovered` on the next success; anything else reaches the presence task's one top-level handler, which logs and ends presence. `amoeba.mcp` imports nothing from `amoeba.store`: the tick reaches `StoreError` and `ConfigError` through `wiring_presence`, as `inbox_resource.py` does
  - [ ] Log lines: `tick failed: <ErrorName>: <text>`, `tick recovered`, and today's presence line with `, machine <machine>` added at its end (the machine is the client file's name, or `local`)
- [ ] **4.2 Tick tests** (`tests/mcp_server/test_tick.py`, memory streams and a `Steps` the test supplies)
  - [ ] Baseline sends nothing; an event on a rise; a new baseline when the way changes and when the number falls; two ticks never overlap
  - [ ] Each failure in D4 skips the tick with one WARNING per run and one INFO on recovery; a failing local store does not end presence; a bug reaches the top-level handler and ends presence while tools keep serving
  - [ ] A `cf` stub that fails twice then answers gives a row at the third tick; a `cf` that hangs ends each tick at `CF_GET_TIMEOUT_SECONDS` with one WARNING; a "not a project" directory asks `cf` no more than once per `CF_REASK_SECONDS`; after `add` the row appears within that time plus one tick; after `rm` the next tick deletes it
  - [ ] Each design-walkthrough case that this file covers here is a test of its own: the repo not added yet, `cf` broken at start, a directory that is not a project
  - [ ] Success: the tests pass on `LocalSteps`
- [ ] **4.3 `mcp/after_runner.py` and its tests**
  - [ ] Runs 262's after-step with the tick's reply in its own worker thread, one at a time; the thread enters `steps_for` itself and leaves it when the after-step returns, and never uses the tick's `Steps`. A tick that ends while one runs starts none (the next reply's flag starts it); the thread's one handler logs with `logger.exception` and frees the runner. Outcomes follow D7's table: no reply, a refusal and a failed `open_runs` start nothing, never end presence and are logged as D4 logs a tick (one WARNING per run, one INFO on recovery); a claimed item that fails to start is recorded by 262's `start_claimed` (a `handle-pause` in the calls log, a resume as `refused`, a wake as `start_failed`) and is not logged as a tick failure
  - [ ] Tests (`tests/mcp_server/test_after_runner.py`): a `claim_work` taking 20 seconds delays no tick and no second after-step starts until the first ends; unknown and refused outcomes start nothing and leave presence as it was; refused on ten ticks in a row logs one WARNING and one INFO on the next success; an unexpected raise is logged and the next tick runs the after-step; with `LocalSteps` on a real sqlite store the tick's pass and the runner's thread each open their own, so no cross-thread use occurs
  - [ ] Success: tests pass
- [ ] **4.4 Move the consumers**
  - [ ] `mcp/presence_task.py`: start `tick` and the runner in place of the two loops; however the task ends, a session that was ever told it has a member makes one shielded `session_end` attempt bounded by `TICK_BOUND_SECONDS`. The attempt absorbs `HubUnreachableError`, `HubRefusedError`, `ClientFileError`, `StoreError` and `ConfigError`, each logged at WARNING as `session end failed: <ErrorName>: <text>` with a comment that swallowing is correct because no reply means the row goes stale (D4, D8); anything else is not caught here and reaches the task's top-level handler. `mcp/inbox_resource.py`: answers from memory per D10's table (`resources/list` always lists the resource; read and subscribe fail with the tick's last error before a first reply, invalid-params with no member)
  - [ ] `SessionTiming` and `PresenceDeps.timing` go: replies carry the poll interval. `_presence_deps` (`mcp/server.py`) takes no config. `PresenceDeps` holds the per-thread step source (the `steps_for` entry the tick and the runner each use), the `cf` runner, the clock and the client name. `mcp/server.py` and `mcp/in_process.py` pass no store opener to presence. `main()` loads the config only where start-up needs it (6.3): on a joined machine it reads none
  - [ ] Add to 4.2's tests: the exit with each absorbed error returns within the bound and raises nothing; an error outside the set reaches the top-level handler
  - [ ] Success: no module in `amoeba.mcp` imports from `amoeba.store`; `wiring_presence` re-exports error types only and holds no store function
- [ ] **4.5 Tools leave the after-step to the tick** (D7)
  - [ ] `wiring.invoke` takes whether to run the after-step; the MCP door passes false, the CLI true. `after_operation`'s MCP-`answer` special case is folded into that. `answer` on the run's own machine still resumes in its own thread and returns the resume (262 D7)
  - [ ] `tests/test_after_step.py`: `test_the_mcp_door_starts_the_ended_held_question_too` now asserts the MCP call starts nothing and the session's next tick starts the held question; the CLI door tests are unchanged
  - [ ] A test that an MCP tool result returns before any `claim_work` call is made for it
  - [ ] Success: tests pass
- [ ] **4.6 Delete the old loops and their tests**
  - [ ] Before deleting, list every test function in `tests/mcp_server/test_inbox_watcher.py` (it imports `watch_inbox` at line 21) and every test in `tests/mcp_server/test_presence.py` that runs `heartbeat_loop` (lines 161, 231, 244), and name for each the test in `test_tick.py` or `test_after_runner.py` that covers its case. Add a test there for any case with none. Note the list under this task
  - [ ] Delete `tests/mcp_server/test_inbox_watcher.py` and those `heartbeat_loop` tests; delete `mcp/inbox_watcher.py`, `heartbeat_loop` and `_session` in `mcp/presence.py` and the `wiring_presence` store functions that moved into `steps.session`
  - [ ] Success: `uv run pytest --collect-only -q tests/mcp_server` collects without an error; `grep -rn "watch_inbox\|heartbeat_loop" src tests` finds nothing
- [ ] **4.7 The 241 tests and the import rules**
  - [ ] Edit the 241 tests only in the design's six ways (Migration Plan): rigs build `PresenceDeps` with `LocalSteps` on the test store and a config; the store-error test asserts the skipped tick and the recovery; the one-shot member test asserts the next tick; 180 and 89.5 use the new constant and limit once 6.1 lands, until then unchanged; the two empty-`resources/list` tests assert the resource is listed and a read refused; the after-step test is 4.5's. Modules: `tests/mcp_server/presence_rig.py`, `serving_rig.py`, `test_presence*.py`, `test_inbox_resource.py`, `tests/load/test_presence_load.py`. Each cell of D10's handler table has a test (`tests/mcp_server/test_inbox_resource.py`)
  - [ ] `tests/test_import_boundaries.py` and `tests/mcp_server/test_boundary.py` agree: `amoeba.mcp` imports nothing from `amoeba.store` (error types come through `wiring_presence`) and nothing from `amoeba.client`; `wiring_presence` imports from `amoeba.store` only error types; `store.sessions.heartbeat`, `delete_session` and the `store.push_reads` functions are called only from `operations.steps.session`
  - [ ] Success: checks pass, 241's tests included

**Commit**: `feat: replace the two presence loops with one tick`

## 5. The door side of the tick (D6; effort 4)

- [ ] **5.1 Session identity and headers**
  - [ ] A frozen `SessionIdentity` (session id, project id or none, client, directory) in `wire.protocol`. `client.call` takes an optional one and writes the four headers from it (directory percent-encoded; the project header left out when none). `DoorSteps` hands it to `client.call` for `session_tick` and `session_end` only. `steps_for` takes the door times and the identity (defaults keep every command as it is); `LocalSteps` ignores them. The tick builds the identity once it has its values and uses `TICK_TIMES`; the exit call uses the last tick's identity
  - [ ] Tests (`tests/client/` and `tests/hub/test_door_steps.py`): the headers are sent on the two calls and no other step or operation; the project header is absent for a non-project; the exit uses the last identity; the tick uses `TICK_TIMES` (one attempt, bound 13)
  - [ ] Success: tests pass
- [ ] **5.2 The hub's touch and the behind refresh** (`hub/call_sessions.py`, called from `hub/calls.py`)
  - [ ] The touch writes `machines.door_version` beside `client_version` for every call with a good token, done and refused alike, except `session_tick` and `session_end`, which set `last_called_at` only. The door version header is parsed as a non-negative integer of at most four digits (the pattern is a constant in `wire.protocol`); a value that does not parse leaves the column as it was. The hub sets `StepEdges.door_version` (2.2) from the version it serves
  - [ ] When a `session_tick` is refused as `door_version`, the touch's transaction reads the four headers (invalid shape, a client name outside the pattern or a directory that does not decode writes no row, the refusal unchanged), finds the member with `find_caller` from the machine and project header, and for a member calls `write_behind_session` with the caller's two versions. A door version above the hub's takes the same path
  - [ ] `session_tick` and `session_end` are dispatched as steps and keep no result
  - [ ] `tests/hub/in_process_hub.py` takes the door version to serve, so a test can restart a hub one version up; the setting reaches both the call's version check and `StepEdges.door_version`
  - [ ] Tests (`tests/hub/test_session_calls.py`): the touch for a session call versus another call from the same machine; an old session ticking never writes old versions onto an upgraded machine, and an `amoeba` command there leaves the machine not behind; a refused tick writes or keeps the row with the caller's versions; bad headers write no row; a door version above the hub's is behind; the refusal body is unchanged; a door version header of `"9\x1b[2J" + "9" * 200` (as `tests/hub/test_handle_call.py:155` sends) writes nothing to `machines.door_version`; a hub serving version N+1 no longer holds off a wake for a member whose session is on N+1, and holds one off for N
  - [ ] Success: tests pass
- [ ] **5.3 The tick through the door**
  - [ ] Test (`tests/hub/test_session_door.py`) on the in-process hub: a tick through `DoorSteps` writes the row with the hub's time; a client file appearing between two ticks gives a new baseline and no event; the hub down for several ticks skips them and the first tick after returns everything above `last_seen`; a client whose own clock (the tick's injected clock) is an hour ahead is listed with the hub's times and drops out of `list` once `session_stale_seconds` has passed on the hub's clock
  - [ ] Success: checks pass
- [ ] **5.4 `hub machines` shows the door version** (`hub/admin.py`)
  - [ ] Each machine's line shows its door version and ends with `behind` or `ahead of the hub` when it differs from the hub's; the hub's own door version is on the first line; `-j` gains `door_version` and `behind` (true, false, or null when none is recorded). `docs/cli-contract.md` names both fields
  - [ ] Tests (`tests/hub/test_admin.py`): text and JSON for a current, a behind, an ahead and a never-recorded machine
  - [ ] Success: tests pass

**Commit**: `feat: serve session ticks through the door`

## 6. Start-up, the deadline and the door version (D8, D9, D14; effort 4)

- [ ] **6.1 The deadline constant and the door version**
  - [ ] `wire.times`: `MCP_CALL_DEADLINE_SECONDS` is 300 and `DOOR_VERSION` becomes 3. `mcp/in_process.py` and `mcp/server.py` import the constant; the 180 in `mcp/in_process.py` is deleted
  - [ ] 260's pinned-tuple test (find it with `grep -rn DOOR_VERSION tests/wire tests/hub`) holds the version, the times and the deadline together
  - [ ] Update `tests/mcp_server/test_deadline.py`, `tests/mcp_server/test_in_process.py` and `tests/test_message_timing.py` (it imports `MCP_CALL_DEADLINE_SECONDS` from `amoeba.mcp.in_process` at line 34) to the constant in `wire.times` and the local limit (`resume_wait_seconds` below 209.5). `grep -rn MCP_CALL_DEADLINE_SECONDS tests` finds no import from `amoeba.mcp.in_process` afterward
  - [ ] Success: checks pass
- [ ] **6.2 `DeadlineError` and the hub's check** (D9)
  - [ ] Move `DeadlineError` to `operations/errors.py` and add it to `OPERATION_ERRORS`; `wiring.DeadlineError` stays as a name for the same class. The hub part of `answer` runs the check first when `via` is MCP, before anything is recorded, against `resume_claim_seconds(config)` and the constant; the message names `resume_wait_seconds`, the hub's `config.yaml`, the bound, the deadline and the largest value that passes
  - [ ] Tests (`tests/hub/test_answer_deadline.py`): `resume_wait_seconds` 143.5 or more is refused as `hub_error` with `DeadlineError` in the message, naming the key and the largest passing value, and no answer is recorded; the example config records and resumes; the same `answer` from the CLI is not checked; the local MCP check is unchanged and bounds by 209.5
  - [ ] Success: tests pass
- [ ] **6.3 Start-up by mode** (D8; `mcp/server.py`)
  - [ ] With no client file: today's checks (script, state move, config, deadline). With one: the `amoeba` script, and the client file and saved certificate load; a missing script or `ClientFileError` refuses with one line on stderr; no hub call, no local read and no config read. Remove 260's `NotServedError` check at start. In a hub home the state move raises `HubHomeError` and nothing opens
  - [ ] Tests (`tests/mcp_server/test_server_main.py`): a home with only a client file and certificate starts with the hub stopped and creates no local file; with no local `config.yaml` present a tool call and a tick on that machine run; a missing certificate refuses and names the file; a hub home refuses with `HubHomeError` and the hub's store is unchanged
  - [ ] Success: tests pass
- [ ] **6.4 Nothing is unserved** (D14)
  - [ ] Delete `NotServedError`, `refuse_if_joined` (`wiring_door.py`, lines 80-85) and the served check in `wiring_door.route` (line 118), and the tests that expect them. The hub's own `not_served` refusal stays. The design text for 260's entry-point table was brought up to date in 0.1
  - [ ] Tests: every `OperationName` but `handle_pause` is in `SERVED_OPERATIONS` and `handle_pause` is not; a grep test that no source file names `NotServedError`; an MCP `add` with `wake_command` on a joined machine is rejected by `refuse_door_fields` and the hub's log shows no `add` call
  - [ ] Success: checks pass

**Commit**: `feat: start amoeba-mcp from a client file and raise the answer deadline to 300`

## 7. Other machines' runs and what list shows (D11, D12; effort 4)

- [ ] **7.1 The hub part of `status` and `list`** (`operations/status_machines.py`)
  - [ ] The hub part of `status`, and of `list` with no subject, upserts the calling machine's `runs` document into `machine_runs` with the hub's time, in the call's transaction. It reads every other machine's document and adds, to that machine's entry in `machines`, the run lines of runs not completed (id, pipeline, status, directory and, when paused, checkpoint). A stored document that does not validate gives that machine `runs_problem` with the error text and no run lines; the rest of the call is unaffected. A question on another machine shows as stored with its machine named and `run_state` `other_machine`. Nothing on another machine is closed or swept. With no client file the one machine is `local` and `hub_door_version` is the running `DOOR_VERSION`
  - [ ] Tests (`tests/operations/test_status_machines.py`): after `status` on `alpha`, `beta` sees `alpha`'s paused run under `alpha` and `alpha`'s waiting question with `other_machine`; a machine that stored nothing has no document; a bad stored document gives `runs_problem` and `status` still succeeds and the next call by that machine replaces it; a call whose own document does not parse is refused as `malformed_call` with nothing stored; nothing on `alpha` is closed by `beta`'s call; a failing write fails the whole call and stores nothing
  - [ ] Success: tests pass
- [ ] **7.2 The result fields** (`operations/status_models.py`, `status_sessions.py`, `status.py`)
  - [ ] `SessionEntry` gains `machine`, `client_version`, `door_version`, `behind`; `StatusResult` gains `hub_door_version` and `machines` (`name`, `last_called_at`, `client_version`, `door_version`, `behind`, and for every machine but the caller `runs_reported_at`, `runs`, `runs_problem`); `WaitingRunState` gains `other_machine`. `behind` is true when the door version differs from the hub's, false when equal, null when none is recorded. A member's `sessions` are its live sessions on every machine, oldest first. No field is renamed or removed; `list -j` still equals the `status` document
  - [ ] `docs/cli-contract.md` names each new field and `other_machine` (`tests/test_contract_docs.py`)
  - [ ] Tests: sessions of two machines under one member oldest first; `behind` true, false and null; `list -j` equals `status`
  - [ ] Success: tests pass
- [ ] **7.3 The renderers** (`cli/render/sessions.py`, new `cli/render/machines.py`, `cli/render/waiting.py`)
  - [ ] A session line is `<client>  <machine>  <directory>  up <age>  last beat <age> ago  push confirmed|push unconfirmed`, ending `behind` when behind. **Runs on other machines**: one heading per other machine, `<machine>, reported <age> ago`, `<machine>, nothing reported`, or `<machine>, reported <age> ago, runs unreadable: <runs_problem>`, with one line per run (id, pipeline, status, directory). **Behind the hub** appears when any machine or session is behind: each with its client and door version, the command `uv tool install --force amoeba-ai`, and a note to restart the sessions listed; one above the hub's is `ahead of the hub` and the section says to upgrade the hub with no client command. Sessions and machines do not count as waiting on the PM and set no notice
  - [ ] `cli/render/waiting.py`: `RUN_STATE_TEXT` (line 77) gains the `other_machine` key, so `list` does not raise `KeyError` for a question on another machine. Its text says the run is on another machine. A waiting line for a question on another machine ends `on <machine>` (design, Text). 262 shows the machine as a second line, `machine: <name>` (`_machine_text`, line 202); that line stays and the suffix is added to the first line. If that makes the design's "as in 262" wrong, 0.1's design edit says so
  - [ ] Tests (`tests/cli/`): each heading form, each line form, the Behind section with a behind and an ahead entry, and no section when nothing is behind; a waiting question with `run_state` `other_machine` renders with the `on <machine>` suffix and does not raise; a stale report shows `reported <age> ago`
  - [ ] Success: checks pass

**Commit**: `feat: show sessions and runs from every machine in list and status`

## 8. Cross-machine tests, load and live (D15; effort 4)

- [ ] **8.1 The fixture helper** (`tests/hub_mcp.py`)
  - [ ] `ClientHome` gains a helper that starts `amoeba-mcp` in a repo of that home over real stdio with the SDK client, and exposes its notifications and its stderr. Uses the existing `two_machine_hub`
  - [ ] Smoke test `tests/hub/test_hub_mcp_smoke.py`: starts a session on `beta`, reads the presence line with the machine name, and the row shows in `list -j` from `alpha`
  - [ ] Success: the smoke test passes
- [ ] **8.2 Push and presence** (`tests/hub/test_sessions_across_machines.py`)
  - [ ] A request sent from `alpha` to a member whose session is on `beta` produces one channel event within one poll interval plus the tick bound; the session's `inbox` call sets `push_confirmed_at` and a later `send` starts no wake; 262's waking fixture with a live push-confirmed session on the other machine starts no wake
  - [ ] A session on each machine appears under its member in `list -j` from either, with its machine and client version
  - [ ] A session killed with SIGKILL is not listed after `session_stale_seconds` on the hub's clock and the next refresh deletes its row; a clean exit deletes the row at once; an exit with the hub stopped returns within `TICK_BOUND_SECONDS` and the row goes stale; a session whose clock jumps (a laptop waking) is listed again at its next tick, up since then
  - [ ] With heartbeat 5, poll 5, stale 15 and a clock the test sets, a session that ticks every poll interval is live at every tick
  - [ ] A session started without the push launch flag still ticks, is listed with `push unconfirmed`, and starts its machine's waiting work
  - [ ] Success: tests pass
- [ ] **8.3 Faults and versions** (`tests/hub/test_sessions_faults.py`)
  - [ ] Hub stopped for a minute: at most one tick call in flight; attempts at most elapsed over interval plus one; each tool call returns `HubUnreachableError` naming the address; `list` from the other machine shows no session once the hub is back and the stale time has passed, until its next tick; mail delivered just before the stop is pushed by the first tick after
  - [ ] The hub's `config.yaml` broken: ticks skipped with one WARNING; the first tick after the file is fixed succeeds. A config that fails the third timing check is refused naming the three keys
  - [ ] Hub restarted one door version up: the session's tools return the upgrade message with both versions; `list` from an up-to-date machine shows the session as behind under its member and its machine in **Behind the hub**; a wake for that member is no longer held off; a session started by the old program afterward is behind too. An old session ticking on an upgraded machine leaves `list` and `amoeba hub machines -j` (5.4) showing the machine not behind after an `amoeba` command there. A door version above the hub's is `ahead of the hub`
  - [ ] `amoeba hub rm-machine` with a session open: ticks refused as `bad_token`, tools return the error with the invite and join commands, and after a new invite and `join` the next tick succeeds with no restart
  - [ ] Success: tests pass
- [ ] **8.4 Work and answers through ticks** (`tests/hub/test_sessions_work.py`)
  - [ ] A fixture pipeline paused on `alpha` and answered from `beta` resumes on `alpha` with no command run there, only an open session; with three sessions open on `alpha` it resumes once
  - [ ] A session in a directory that is no member writes no row, sends no event, and its ticks still start the machine's waiting work
  - [ ] An MCP `answer` for a run on the session's own machine returns the resume's outcome and no `resume-run` process is started for it
  - [ ] A client that cuts an `answer` call off (the SDK client cancels it after one second on a slow resume) leaves the answer recorded and the resume's outcome recorded, and `list` shows it
  - [ ] Success: tests pass
- [ ] **8.5 Joins, leaves and the resource** (`tests/hub/test_sessions_modes.py`)
  - [ ] A session open across `amoeba join --set-aside-local` uses the hub from its next tick with a new baseline and no event. On a joined machine that had no local store, after `amoeba leave` and the next tick, a plain `amoeba join` is refused naming `--set-aside-local` and `join --set-aside-local` succeeds and the session then uses the hub
  - [ ] `resources/read` returns the member and the newest tick's `as_of_seq` with no store or hub call and fails naming the tick's error before a reply; `resources/list` lists the resource in a session with no member and after a failed first tick; `subscribe` is refused there and succeeds once a later tick has a member, with no reconnect
  - [ ] Success: tests pass
- [ ] **8.6 Door load** (`tests/load/test_door_load.py`)
  - [ ] Add 50 ticking sessions across 10 members, each ticking every 0.5 seconds for 20 seconds, beside the existing 16 clients. Assert: every tick is answered within 2 seconds; no session goes more than 3 seconds between replies; every session's row stays live; 260's two bounds still hold. Print the slowest tick and the longest gap
  - [ ] Confirm CI gates it: `uv run pytest --collect-only -q tests/load/test_door_load.py` lists the new test, and `pyproject.toml`'s `addopts` ignores only `tests/live`, so the `Tests` step of `.github/workflows/ci.yml` (`uv run pytest`) runs it and its assertions are what fail the build. If any marker or ignore excludes `tests/load`, add a CI step that runs it
  - [ ] Add the measured figures to the design's Slice Notes. `tests/load/test_presence_load.py` keeps running on the local store
  - [ ] Success: the load test passes and is collected by the CI command; figures are in the notes
- [ ] **8.7 Live variant** (`tests/live/channels`)
  - [ ] A variant on `two_machine_hub`: a real Claude Code session in the member's repo on one machine, the request sent with `amoeba send` from a repo on the other. Run it as 1.1 does (spend is pre-authorized): `set -a; source .env; set +a; AMOEBA_LIVE_CHANNEL_MODEL=sonnet uv run pytest tests/live/channels -v`
  - [ ] Success: `tool inbox called` appears in the server log with nothing typed, and `list -j` from the sending machine shows the session with `push_confirmed_at` set; 241's four tests and the long-call test still pass

**Commit**: `test: run sessions across two machines, under load and live`

## 9. Admin, documents and the live update (D12 to D14; effort 3)

- [ ] **9.1 `hub rm-machine`** (`hub/admin.py`)
  - [ ] `remove_machine` already deletes the machine's session rows; 2.2 added the stored-runs delete. Nothing else changes in `rm-machine`
  - [ ] Test (`tests/hub/test_rm_machine_work.py`): rm deletes the machine's sessions and its stored runs, and leaves other machines' rows
  - [ ] Success: tests pass
- [ ] **9.2 Documents** (D14)
  - [ ] `docs/mcp-server.md`: start-up on a joined machine; the tick in place of the two loops; the member worked out each tick; what a failed tick does; the deadline of 300 and the two limits on `resume_wait_seconds` (143.5 through the door, 209.5 local); Codex's `tool_timeout_sec` of at least 305; what Claude Code does with a call past two minutes as 1.3 recorded it, with the setting if the result needed one; the resource listed in every session and its number one tick old; the new log lines
  - [ ] `docs/cli-contract.md`: the **Behind the hub** and **Runs on other machines** sections (the fields were added in 7.2 and 5.4). `docs/store-contract.md`: migration 014 and who writes `sessions`. `docs/config-contract.md`: `session_heartbeat_seconds` and `session_stale_seconds` as judged on the hub, the third check, and `resume_wait_seconds`'s limits
  - [ ] If 1.3 found the result still does not arrive, the `answer` tool's description says to read the outcome with `list`
  - [ ] Success: `tests/test_contract_docs.py` passes; each document names the behavior it is listed for
- [ ] **9.3 `scripts/update_live.py`** (D14)
  - [ ] The read-back already runs `amoeba list` (`_amoeba_list`) and reads the store (`check_store`). Add an `_amoeba_status` call beside `_amoeba_list` and two checks: the `status` document holds a `machines` list with the one `local` machine, and `machine_runs` holds one row for it. The script lists open `amoeba-mcp` sessions to restart; keep that if present, add it if not
  - [ ] Test (`tests/scripts/test_update_live.py`, using `schema_13.py`): `update` and `restore` pass against a copy of a schema-13 store, with the live paths redirected to the copy
  - [ ] Add the restore path to the design's Slice Notes: `uv run python scripts/update_live.py restore`, which puts back the store as it was before the update, loses every answer, message and decision recorded since, and reinstalls the release installed before
  - [ ] Success: tests pass; the note is written

## 10. Validation and notes (effort 2)

- [ ] **10.1 Checks and sizes**
  - [ ] Run the four checks and the slice's own tests: `uv run pytest tests/mcp_server tests/hub tests/store/test_migration_014.py tests/load/test_door_load.py tests/mcp_server/test_protocol_pin.py -v`
  - [ ] `wc -l` each new source file: each near 300 lines or less; split any that is over, with the tests passing after
  - [ ] Success: the checks pass; each Success line above was met by its task
- [ ] **10.2 Operator walkthrough, done by the implementing agent**
  - [ ] Step through the design's Operator Walkthrough bullets as the person running it, against `two_machine_hub`. Record in the Slice Notes the test that shows each bullet, from this map, and every dead end found, or `Dead ends found: none`:
    - Start: 6.3 and 8.1. A client cuts a call off: 8.4. Normal path: 8.2. The repo was not added yet, `cf` broken at start, not a Context Forge project: 4.2. The hub goes down: 8.3 (and 5.3). The hub's config is broken: 8.3 and 2.4. A session is closed, killed, or its laptop sleeps: 8.2. An `answer` refused for the deadline: 6.2. A run answered from another machine: 8.4. The hub upgraded, a machine upgraded before the hub: 8.3 and 5.4. A machine removed with a session open: 8.3. A machine joins or leaves while a session is open, and a client that listed resources early: 8.5. Runs on another machine look old: 7.3. Turning push off: 8.2. Undo: 9.3
  - [ ] Success: the notes list each bullet with its test, and any dead end is fixed in code or its design text before this task is checked

**Commit**: `feat: finish the admin views, documents and live update for sessions, and record the walkthrough`

The one commit for sections 9 and 10: the notes ride with the section 9 work, so no commit holds only notes.
