---
docType: slice-design
slice: sessions-across-machines
project: amoeba
parent: user/architecture/260-slices.the-hub.md
dependencies:
- 260
- 261
- 262
interfaces:
- 264
dateCreated: 20261120
dateUpdated: 20261121
status: not_started
turns: 29
promptTokens: 2452589
cachedTokens: 2210522
cacheWriteTokens: 242037
completionTokens: 61696
durationSeconds: 662.0
costUsd: 6.783108
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-fable-5-2:
    rounds: 1
    costUsd: 6.783107800000002
    completionTokens: 61696
---

# Slice Design: sessions-across-machines

## Overview

`amoeba-mcp` is the local process each agent session starts. Today it opens the store itself: every few seconds to look for new mail, every half minute to write its session row, and for every tool call. On a joined machine it does not start at all (260 D2).

This slice makes it a client of the hub. Its two loops become one **tick**: one hub call every `notify_poll_seconds` that keeps the session row fresh, reads the member's new deliveries, and says whether the machine has work waiting. Its tools already go through `wiring.invoke`, which 260 to 262 put behind the door; this slice removes the last local reads beside them.

`list` and `status` then show every session on every machine, which machines and sessions run a program too old for the hub, and the runs each other machine last reported.

The PM's install has no client file and keeps running on its local store, through the same tick.

## Value

User value. A session on one machine hears about mail sent from another within one tick. `amoeba list` from any machine shows who is working where. A request to a repo whose agent is live on another machine is pushed to it and wakes nobody.

After this slice every entry point is served through the door, which is what 264 needs before it deletes the local-store way.

## Technical Scope

Included:

- The tick, as one step run the same way on the hub and on a local store (D1 to D4).
- Session rows written and judged on the hub's clock, with the client version and door version (D5, D6).
- Starting a machine's waiting work from a tick (D7).
- `amoeba-mcp` starting on a joined machine, and its clean exit (D8).
- Every MCP tool through the door with no local read, and the `answer` deadline check on the hub (D9).
- The `amoeba://inbox` resource without a store read (D10).
- Each machine's last reported runs, stored on the hub and shown from other machines (D11).
- What `list` and `status` show: sessions with their machine, machines, and who is behind (D12).
- Migration 014 (D13).

Excluded:

- `amoeba adopt`, deleting the local-store way and the hub set-up page (264).
- Any change to the channel event, the pinned handshake or the `inbox` rule. They are 241's and stay as they are.
- Polling in the background on a machine with no session and no command running. The architecture rules it out.

## Dependencies

### Prerequisites

- Slices 260, 261 and 262, built. As of 20261120 all three are designed and none is built, and each design's latest review is FAIL. This design uses 260 as written at commit `9ee28aa5` with the edits committed alongside this revision (re-read 20261121), 261 at `006c60ad`, and 262 at `002730bf` with the edits committed alongside this revision. If one of them changes a decision named under Interfaces Required before this slice's task breakdown, this document is updated to match first.
- No new package.

Facts about other tools, read 20261120 on this machine:

- Claude Code is 2.1.325, the version 241's channel facts were last measured on. `mcp` is 2.3.0. `uv run pytest tests/mcp_server/test_protocol_pin.py` passes (3 passed), so the probe and handshake behavior 241 D1 rests on is unchanged.
- The client timeouts the 300-second deadline in D9 depends on:
  - Codex CLI (0.163.0 installed) waits `tool_timeout_sec` for a tool, 60 seconds by default. Source: OpenAI's Codex MCP page, `developers.openai.com/codex/mcp`.
  - Claude Code waits `MCP_TOOL_TIMEOUT` for a tool, about 28 hours when unset, and a per-server `timeout` overrides it. It also ends a call to a stdio server that has sent no response and no progress for 30 minutes (`CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`), and moves a call still running after 2 minutes to a background task, where it finishes (`CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS`, from 2.1.212). None of the three cuts a call off inside 300 seconds. Source: Claude Code's MCP page, `code.claude.com/docs/en/mcp`, read 20261120 through a fetch that summarizes long pages, so the wording is the summary's and the three values are the page's.
  - The same three, checked 20261121 in the text of the installed 2.1.325 program. All three settings are in it. The idle limit for a stdio server is 1,800,000 ms. The move to the background is at 120,000 ms, and setting `CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS` to 0 turns it off. A per-server `timeout` is a hard limit per call and overrides `MCP_TOOL_TIMEOUT`.
  - Two things that reading does not settle: the value of `MCP_TOOL_TIMEOUT` when unset, and what the agent is given when a call is moved to the background and how the result then reaches it. An `answer` can run 216.5 seconds with the example config, so it crosses the 2-minute point. Step 1 of the Development Approach measures both with a real session and a call of that length, and says what follows from each result. Nothing in this design rests on either until then.

### Interfaces Required

- From 260: `client.call` and `DoorTimes` (D7, D10), the headers of a call (D6), the touch and the refusal path in `hub.calls.handle_call` (D8), `OPERATION_ERRORS` in `operations/errors.py` (D8), `RefusalCode`, `wire.times`, `sessions.machine_id` and the acting machine (D12), `amoeba hub machines` and `amoeba hub rm-machine` (D13), `amoeba join --set-aside-local` and `amoeba leave` (D4), the two-machine fixture and the door load test (D18).
- From 261: `operations.here` for the caller, `find_caller`, the `runs` document and the hub part of `status` (D5, D6, D11).
- From 262: `Steps`, `STEP_MODELS`, `run_step`, `LocalSteps`, `DoorSteps` and `steps_for` (D3); the `work` reply key, `claim_work` and `wiring_steps.after_call` (D10); the hub part of `answer` with `via` (D7); the presence read in `wake_due` (D8); the machine on question entries; `resume_claim_seconds` (D6), and `resume_bound_seconds` unchanged.
- From 241, already built: `mcp.pinned_loop`, `mcp.channel_event`, `mcp.presence`, `mcp.presence_task`, `mcp.inbox_watcher`, `mcp.inbox_resource`, `store.sessions`, `store.push_reads`, and the config keys `notify_poll_seconds`, `session_heartbeat_seconds` and `session_stale_seconds`.

This slice changes some of what 260 and 262 say, the after-step among them. Each change is listed under "Amendments to 260 and 262".

`resume_claim_seconds` (216.5 seconds with the example config; D9 shows the sum) follows a rule that is 262's own departure from the architecture, recorded in 262's departures table: the architecture puts the retry time alone in place of the store wait, which would give 160.5.

## Architecture

### Component Structure

| Package | Modules | Change |
|---|---|---|
| `amoeba.operations.steps` | `session` (new) | The hub side of `session_tick` and `session_end`: plain functions on a store, a config and a clock. |
| | `models`, `dispatch` | The two steps' request and reply models and their rows in `STEP_MODELS`. |
| `amoeba.operations` | `answer` | The hub part checks the MCP call deadline when `via` is MCP (D9). |
| | `errors` | `DeadlineError` moves here from `wiring` and joins `OPERATION_ERRORS` (D9). |
| | `status`, `status_sessions`, `status_models` | Sessions with their machine. The machines list, with each other machine's stored run lines. |
| `amoeba.store` | `schema/014_sessions_across_machines.sql`, `machine_runs` (new) | The migration. Reading and writing a machine's stored runs document. |
| | `sessions`, `sql_sessions`, `machines`, `sql_machines`, `models` | The two version columns. The live rule and the waking rule (D6, D13). The machine's door version. |
| `amoeba.wire` | `times`, `protocol` | `MCP_CALL_DEADLINE_SECONDS`, `TICK_TIMES`, the door version. The two step names. The session headers' names, the session id's shape and the client-name pattern, which moves here from `mcp.presence` (D6). |
| `amoeba.hub` | `calls`, `admin` | The touch writes the door version, except for the two session calls (D6). A `door_version` refusal writes the session's row from the call's headers. `hub machines` shows each machine's door version and whether it differs from the hub's (D12). `rm-machine` deletes the machine's stored runs. |
| `amoeba.client` | `call` | Sends the session headers when it is given them. |
| `amoeba.config` | `user_config` | The third session timing check (D5). |
| `amoeba` (wiring) | `wiring_steps`, `wiring`, `wiring_door`, `wiring_presence` | `steps_for` takes the times and the session's identity, the four values the session headers carry (D6). `invoke` can leave the after-step to its caller. `NotServedError` and the client's served check are deleted (D14). `wiring.DeadlineError` is the name from `operations/errors.py`. `wiring_presence` shrinks to the caller gather and the two step calls. |
| `amoeba.mcp` | `tick` (new, replaces `inbox_watcher`) | The one loop. |
| | `after_runner` (new) | Runs the after-step off the loop, one at a time. |
| | `presence`, `presence_task`, `inbox_resource`, `server`, `in_process` | No store opener. Start-up by mode. The resource answers from memory. Tools leave the after-step to the tick. |
| `amoeba.cli` | `render/sessions`, `render/machines` (new), `render/` run lines | The machine on each line, and the **Behind the hub** section. |
| `scripts` | `update_live.py` | Two read-back checks (D14). |

Import rules added to `tests/test_import_boundaries.py`:

- `amoeba.mcp` and `wiring_presence` import nothing from `amoeba.store` but its error types, and nothing from `amoeba.client`. A session reaches the store only through `Steps`.
- `store.sessions.heartbeat`, `delete_session` and the `store.push_reads` functions are called only from `operations.steps.session`. The refusal path in `hub.calls` (D6) writes its row through a function in `operations.steps.session` too.
- `steps.models` still holds no field of a date or time type (262's test covers the two new request models).

### Data Flow

A session is open in a checkout of `widget` on machine `beta`. A repo on `alpha` sends `widget` a request.

1. At start, `amoeba-mcp` on `beta` asks `cf` once for its directory's project.
2. Its tick calls `session_tick` with that project id, its session id, its client name and directory, and no last-seen number. The hub finds the member from (`beta`, project id), writes the session row, and returns the member, its highest delivery number, and `notify_poll_seconds`. The session now has a baseline and has sent nothing.
3. Every `notify_poll_seconds` the tick runs again, carrying the last number it saw. The hub refreshes the row only when a heartbeat is due.
4. On `alpha`, `amoeba send --to widget ...` is one door call. The hub's presence check reads `widget`'s rows on every machine (262 D8). The session on `beta` is not yet push-confirmed, so if `widget` has a wake command a wake is still due, exactly as 241 D6 says for a first event.
5. The next tick from `beta` carries a lower number than the hub now holds. The reply holds the new entries. The session sends one channel event, as today.
6. The agent calls `inbox`. That is a tool call through the door. The session marks itself push-confirmed in memory, the next tick says so, and the hub stamps `push_confirmed_at` with its own time. From then on a `send` to `widget` from any machine starts no wake.
7. Any tick's reply may carry `work: true`. The session then runs 262's after-step, which claims the work and starts it detached.

With no client file the same loop runs the same step through `LocalSteps` on the local store.

### State Management

| State | Where | Ends by |
|---|---|---|
| A session row | `sessions`, on the hub | `session_end` at a clean exit. Otherwise it stops counting once its heartbeat is `session_stale_seconds` old on the hub's clock, and the next refresh by any session deletes it. A row written again by a tick that was in flight at exit ends the same way (D8). `amoeba hub rm-machine` deletes its machine's rows (260) |
| A session's member | Worked out on every tick from the machine and project id | The row is deleted in the tick that finds no member |
| A session that is behind | Its row, kept fresh by its refused ticks (D6) | The session ending: its ticks stop and the row goes stale |
| A machine's door version | `machines.door_version` | Overwritten by that machine's next call that is not a session's tick or exit call (D6). Deleted with the machine |
| A machine's last reported runs | `machine_runs`, one row per machine | Replaced by that machine's next `status` or `list`. Deleted by `rm-machine` |
| The session's last-seen number, its push confirmation and the hub's last `as_of_seq` | Memory of the `amoeba-mcp` process | The process ending |

Nothing new is written on a client's disk. `machine_runs` holds at most one document per machine, each bounded as D11 says.

## Technical Decisions

### D1 — One tick, one body, two ways
Status: decided

241's heartbeat loop and push loop become one loop in `mcp.tick`. Each pass makes one call to the step `session_tick` (D2) in a worker thread, handles the reply on the event loop, and then sleeps `notify_poll_seconds`. The sleep starts when the pass ends, so two ticks never overlap and nothing queues.

The tick is a 262 step. Each pass asks `wiring_steps.steps_for` which way to go, so the mode is decided on every tick: a session that was open before its machine joined uses the hub from its next tick. With a client file the step is one door call. With none it runs on the local store through `LocalSteps`, which is the architecture's way for a machine with no client file until 264.

The tick adds no rule of its own for `amoeba leave` (260 D4). A session open across it has no client file at its next tick, and does what any call on that machine then does. Before 264 that is the local way. After 264 deletes the local way, the tick fails with the message to run `amoeba join`, and D4 skips it until the machine joins again.

One effect of that before 264, on a machine that had no local store when it joined. `leave` puts nothing back, and the open session's next tick takes the local way. Opening the local store there makes an empty one, as the next command there would (262, Operator Walkthrough, "Undo"). The tick itself may then fail for want of a local `config.yaml`, and is skipped (D4). A plain `amoeba join` after that is refused and names `--set-aside-local` (260 D4). With the flag the empty store is set aside and the machine joins; `leave` puts it back. So the state ends with a command and nothing is deleted by hand. It is accepted as it is because the tick does only what any `amoeba` call there does, only fixtures leave before 264, and 264 removes the local way.

The step numbers of two stores are unrelated. So when the way changes between two ticks, or a reply's highest number is below the last one seen, the session takes a new baseline and sends no event for that tick. Mail in that gap is found by the agent's next `inbox` poll, as mail before a first baseline is today.

`notify_poll_seconds` comes in every reply, from the config of whichever side ran the step. A session that has had no reply yet waits `TICK_SECONDS_BEFORE_FIRST_REPLY` (5, a constant in `mcp.tick`) between tries. That is the only interval the client holds, and it is used only until the first reply. It cannot come from the hub's config, because it is the wait while no reply has ever arrived, and a session must be able to start with the hub down (D8).

- Rejected: keeping two loops and making each a hub call. It doubles the calls and still needs both to agree on the member.
- Rejected: a separate loop for the hub way. 264 would delete one of them, and until then the PM's install would run code the fixtures do not.

### D2 — The `session_tick` step
Status: decided

Request, with no time in it:

| Field | Holds |
|---|---|
| `here` | The caller as 261 D5 gathers it: `{project_id}` or `{not_a_project}` |
| `session_id` | `uuid4().hex`, made once per process |
| `client` | The client's name, already reduced to the displayable form (241 D6) |
| `directory` | The process's working directory |
| `last_seen` | The highest delivery number this session has seen, or null for a baseline |
| `push_confirmed` | Whether this session's agent has answered a channel event |

The hub side, `steps.session.session_tick`, on the hub's clock and config:

1. **The member.** `find_caller(machine, here)`. With no member, it deletes this session's row if there is one and returns the reason. Nothing else is read.
2. **The row, when a heartbeat is due.** It is due when the session has no row, the row's heartbeat is at least `session_heartbeat_seconds` old, the row's member is not this member, or `push_confirmed` is true and the row's `push_confirmed_at` is null. Then, in one write: stale rows of every member are deleted, and this row is upserted (D5). When nothing is due, the step writes nothing.
3. **Deliveries.** The member's highest delivery number. When `last_seen` is given and lower, the entries above it: at most `CHANNEL_EVENT_MAX_ENTRIES` (10, 241's constant), with how many there are in all and the first one's number. So the reply's size does not grow with the backlog. The event's `and K more` comes from the count.
4. **`as_of_seq`,** the highest delivery number assigned to anyone, for the resource (D10).

Reply: the member's id and name or the reason there is none, `high_seq`, `first_seq`, `count`, `entries`, `as_of_seq` and `notify_poll_seconds`. An entry is 241's push row and nothing more: `seq`, `event` and `kind` (both closed enums) and `counterparty` (a member id). The reply model forbids other fields, and a test seeds messages whose subject, body, result and reason hold marker strings and asserts none is in a reply. Through the door, the reply also carries 262's `work` key like every done reply.

The upsert changes a row only when it belongs to the calling machine. A session id that exists on another machine makes the step fail with a `StoreError`, refused as `hub_error`. Ids are random, so this is a guard and not a case.

**`session_end`** has one request field, `session_id`, and a reply with no fields. The hub side, `steps.session.session_end`, deletes the row with that id if it belongs to the calling machine, and reads nothing else. An id with no row is done, not an error. Through the door its reply carries `work` like every done reply; the session is ending and does not act on it.

`session_tick` and `session_end` are in `STEP_CALLS` and not in `WRITING_STEPS`. Run twice they leave the same store, and the tick is never repeated, so no result is kept. That rests on the tick's retry time being 0 (D4). A test asserts `TICK_TIMES` has a retry time of 0 and that both calls are made with it, so nobody gives the tick a retry without making it a writing step.

The channel event is built from the reply exactly as 241 D4 says. The counterparty is still a member id.

### D3 — Who the session's member is
Status: decided

The client asks `cf` for its directory's project until it gets a project id, then keeps it for the life of the process.

- A project id: kept, and sent as `here` on every tick.
- "Not a project": sent as `here`, and asked again once the answer is `CF_REASK_SECONDS` old (60, a constant in `mcp.tick`). So a directory made a project and added after its session started has presence within about a minute, with no reconnect. One `cf` call a minute is the cost of a session open outside a project.
- `cf` fails or times out: no answer. That tick is skipped (D4) and the next one asks again. 241 resolved once and left a failed lookup dead until the session reconnected.

The `cf` call is bounded by the existing `CF_GET_TIMEOUT_SECONDS` (30, in `upstream/context_forge/project_of.py`): `run_cf` stops a call that runs that long and returns it as a failure. So a `cf` that hangs is a failed tick every 30 seconds, with D4's WARNING, and never a tick that does not end.

The hub works the member out from `here` on every tick. So:

- A directory that is a Context Forge project, added with `amoeba add` after its session started, has presence and push from its next tick. 241 needed a reconnect.
- A member removed with `amoeba rm`, or a checkout removed with `rm --checkout`, loses its row at the next tick.
- A session in a directory that is no member still ticks. It has no row and gets no push, and its ticks still carry the work flag and count as its machine calling the hub.

`PresenceState.resolved` is set when the first tick ends, with a reply or without. The resource handlers wait on it as today, and then answer from the newest tick, because the member can now change after the first one (D10). The first tick ends within `CF_GET_TIMEOUT_SECONDS` plus `TICK_BOUND_SECONDS` (43 seconds), so that wait is bounded.

### D4 — A tick that fails
Status: decided

The tick's door call is one attempt: `TICK_TIMES` in `wire.times` is 260's times with a retry time of 0. So a tick takes at most `TICK_BOUND_SECONDS` (13: one connect and one read) and then gives up. The next tick is the retry.

Every operational failure of a tick is handled one way: the tick is skipped, and the loop goes on. That covers no reply, any refusal (`bad_token`, `door_version`, `hub_error`, `hub_fault`), a `ClientFileError`, a `cf` failure in D3, and with no client file a `StoreError` or `ConfigError`. One WARNING is logged when a run of failures starts or its error type changes, and one INFO line when a tick next succeeds.

While ticks fail, the row is not refreshed, so `list` stops showing the session after `session_stale_seconds`. The first tick that succeeds writes the row again and returns everything above the session's last-seen number. So push resumes at that tick, including mail that arrived just before the outage.

Anything that is not an operational error is a bug. It reaches the presence task's one top-level handler, which logs it and ends presence, as in 241 D2. The tools keep serving.

A session whose ticks are refused for good (its program is behind, D6, or its machine was removed) keeps ticking until it ends. Each tick is one small refused call, and the hub logs a refused call as one line in a rotating file (260 D16).

- Rejected: ending presence on a store or door error, as 241 does for a store error. The session would need a reconnect after every hub restart.

### D5 — The hub's clock
Status: decided

No time crosses the door from a session.

| Column | Set by | From |
|---|---|---|
| `started_at` | The insert | The hub's clock |
| `heartbeat_at` | Each refresh | The hub's clock |
| `push_confirmed_at` | The first refresh that carries `push_confirmed: true` | The hub's clock |

`live_sessions`, `live_member_ids` and the prune already take the time from their caller. Each is called only from a step or a hub part, with the hub's clock.

The client still measures one wait of its own: whether an `inbox` call came within `PUSH_ANSWER_SECONDS` of an attempted event. It now uses its monotonic clock for that, and sends only the yes or no.

A row that was pruned while its process was suspended is inserted again at the next tick, with a new `started_at`. `list` then shows the session as up since it came back.

`session_heartbeat_seconds` keeps its meaning and its two config checks: it is at least `notify_poll_seconds`, and `session_stale_seconds` is at least twice it. Those two were enough while a session beat on its own timer. Now a row is refreshed by the first tick that finds it due, so two refreshes of a healthy session are up to one heartbeat plus one poll interval apart, plus the tick's own time. A config the two checks accept (heartbeat 5, poll 5, stale 10) would put a healthy session past stale just before each refresh.

So `config/user_config.py` gains a third check beside the two: `session_stale_seconds` is at least `session_heartbeat_seconds + 2 * notify_poll_seconds`. The second poll interval is the room for the tick's own time. A config that fails is refused at load with the three keys named, as the other two checks do. The example config (heartbeat 30, poll 5, stale 90) needs 40 and passes. The PM's live config holds the same three values (read 20261121) and passes. The smallest shape the old checks accepted, heartbeat equal to poll and stale twice that, is refused.

The check does not cover a tick that takes longer than one poll interval, or one that fails. Through the door a tick can take `TICK_BOUND_SECONDS` (13). Then the row can pass `session_stale_seconds`. The session drops out of `list` and stops holding off a wake until its next refresh writes the row again, which is what D4 says of ticks that fail.

### D6 — Sessions and machines that are behind
Status: decided

A call whose door version differs from the hub's is refused before its body is read as anything (260 D8). So the hub knows a caller is behind only from its headers.

- **Machines.** `machines` gains `door_version`. The touch that already runs for every call with a good token writes it beside `client_version`, for done and refused calls alike. 260's `hub machines` shows the client version only; this slice adds the column and the behind display, and `hub machines` and `list` both read it (D12).

  The two session calls are the exception. For `session_tick` and `session_end` the touch sets `last_called_at` only and leaves the machine's two versions as they are. A session's versions are on its own row. Without this, one old session left open on an upgraded machine would write the old versions back every few seconds, and the machine would read as behind from every other machine. So a machine's versions are those of the last `amoeba` command or session tool call from it. `join` makes one such call, `hello`, so a joined machine always has them. A tool call from an old session still writes the old versions, until the next `amoeba` command there. That session is itself listed as behind, and restarting it ends that.
- **Sessions.** A session row holds the `client_version` and `door_version` of the program that wrote it. `amoeba-mcp` sends four headers on `session_tick` and `session_end`: `Amoeba-Session-Id`, `Amoeba-Session-Project` (the project id from `here`, left out when the directory is not a project), `Amoeba-Session-Client` and `Amoeba-Session-Directory` (percent-encoded). They repeat what the body holds, in the one part of a call the hub reads before it checks the version. When the hub refuses a `session_tick` as `door_version`, the touch's transaction also finds the member with `find_caller` from the machine and the project header and, for a member, upserts the session's row with the caller's two versions and the hub's time. So the row is kept, or made, with the caller's door version on it.

A session or machine is **behind** when its door version is not the hub's. So after the hub is upgraded to a new door version, every session run by an older program shows in `list` as behind for as long as it runs, with its machine and client version, whether it was open at the upgrade or started after it. Its tools return 260's upgrade message.

A door version above the hub's differs too. That is a machine upgraded before the hub, which the release order rules out but a person can do. It is `behind` like the others, because its calls are refused the same way, and its line in `list` says the hub is the one to upgrade (D12).

A behind session gets no push, because its ticks are refused. So it does not hold off a wake: `live_member_ids` counts only rows whose door version is the hub's.

The headers are the part of the door every version shares, as the version header itself is. A session id that is not 32 hex characters, a client name outside 241's pattern, or a directory that does not decode makes the hub write no row for that refusal. The refusal is unchanged. The session id's shape and the client-name pattern are constants in `wire.protocol`, each defined once. The pattern is today's `CLIENT_NAME_PATTERN`, moved from `mcp/presence.py`, which imports it from there: the hub may not import `amoeba.mcp` (260, Component Structure).

The four values reach the call as one session identity. The tick builds it once it has them and passes it to `steps_for` with `TICK_TIMES`. `DoorSteps` hands it to `client.call` for `session_tick` and `session_end` and for no other step, and `client.call` writes the headers from it. `LocalSteps` ignores it. The exit call uses the identity of the last tick.

With no client file there is no touch. The `local` machine's door version stays null, `behind` is null for it, and its sessions carry the running program's own versions.

- Rejected: reading the body of a refused tick to make a row. A different door version means the body's shape is not known.

### D7 — Work that belongs to the machine
Status: decided

After every tick that got a reply, the session runs 262's after-step with that reply: the file clean-up when it is due, and `claim_work` when the flag is set. This is how a machine with open sessions and no command running resumes an answered run within one tick.

`mcp.after_runner` runs it in its own worker thread, never on the event loop and never in the tick's thread. One runs at a time. A tick that ends while one is still running starts none; the flag is still set in the next tick's reply, which starts it then. So a slow `claim_work` (it retries, up to one call bound) delays neither the next tick nor a heartbeat.

MCP tool calls leave the after-step to the tick. This is a change this slice makes. In 262 the after-step runs at the end of `wiring.invoke` on both doors, as `start_after` does today: after every operation on the CLI door, and after every operation but `answer` on the MCP door. Here `wiring.invoke` takes whether to run it, and the MCP door says no. The existing test `tests/test_wiring_release.py::test_the_mcp_door_starts_the_ended_held_question_too` pins the old behavior for `reply` and `cancel`. This slice changes it to assert that the MCP call starts nothing and that the session's next tick does. A tool's result therefore returns before any claim or clean-up, which keeps them out of the MCP call deadline (D9). The work starts at most one poll interval later.

Two things are not the after-step and are unchanged on the MCP door. They are part of the operation itself, in 262 D7 and D8, and use no `claim_work`:

- **`answer` on the run's own machine.** The hub part of `answer` takes the resume claim and returns it in the answer's own reply. The client part of `answer` then runs the resume in the same thread, waits for its outcome, records it with `resume_record`, and returns today's result with the resume in it. This is the architecture's "Same machine, no wait", and it is the path the deadline in D9 is worked out for. The detached `amoeba resume-run` that 262's after-step starts is the other case: an answer given from another machine, claimed later by `claim_work`.
- **`send` from the machine with the wakeable checkout.** The wake comes back in the reply and `wake-run` is started detached in that call.

What each outcome of the after-step does. None of them ends presence or changes a tick, and none is retried by the runner; the next tick's flag is the retry. A failed claim does not clear the flag, which the hub works out from its records, so while the cause lasts each tick makes one more claim call. Failures are logged exactly as D4 logs a tick's, at the same levels.

| Outcome | Handling |
|---|---|
| `claim_work` gets no reply (unknown) | Logged as above. Nothing is started. If the hub applied the claims, each runs out on its own limit and is handed out again (262 D10, D11) |
| `claim_work` is refused | Logged as above. Nothing is started |
| A claimed item fails to start | 262's `start_claimed` records it: a `handle-pause` in the calls log, a resume as `refused`, a wake as `start_failed` |
| `open_runs` for the clean-up fails | Logged. The marker is not touched, so the next after-step tries again (262 D12) |
| Anything else is raised | 262's after-step never raises. The runner's thread still has one handler as its boundary: it logs with `logger.exception` and the runner is free for the next tick |

If presence has ended on a bug (D4), that session starts no work. The next CLI call or any other session on the machine does.

### D8 — Start-up and exit
Status: decided

`amoeba-mcp` start, by mode:

| | With no client file | With a client file |
|---|---|---|
| Checks | Today's: the `amoeba` script, the state move, the config, the deadline | The `amoeba` script, and that the client file and saved certificate load (260 D3) |
| Refuses to start on | Any of those failing, as today | A missing script or a `ClientFileError`, with its one line on stderr |
| Reads | The local config and store | Neither. No hub call is made, so a hub that is down does not stop a session from starting |

260's `NotServedError` at `amoeba-mcp` start is removed. The mode is still decided on every call after that: the table only says what start-up checks.

In a hub home, one whose config directory holds `hub.yaml`, the left column applies, since `join` refuses there. The state move raises 260's `HubHomeError` (260 D2), so `amoeba-mcp` does not start in a hub home and opens nothing.

264 deletes the left column. With no client file `amoeba-mcp` then starts with one WARNING, reads nothing local, and its tools return `NotJoinedError` until the machine joins (264 D6).

**Exit.** However the presence task ends, a session that was ever told it has a member calls `session_end`, which deletes its row on the calling machine. It is one attempt, shielded and bounded by `TICK_BOUND_SECONDS`. If it gets no reply the row goes stale. A `session_end` refused as `door_version` deletes nothing, and that row goes stale the same way.

**A tick in flight at exit.** The tick's worker thread is abandoned at exit, not stopped, so its call can reach the hub after `session_end` has deleted the row. The step then finds no row and writes one. Nothing refreshes that row, so it ends as a killed session's row does: it stops counting once it is `session_stale_seconds` old on the hub's clock, and the next refresh by any session deletes it. Until then `list` shows a session that has ended, and if it was push-confirmed it holds off a wake for its member for at most `session_stale_seconds`. That is the same limit a killed session already has. It needs a tick to be in its hub call at the moment of exit, which is a few milliseconds in every poll interval, so no ordering is built to close it.

### D9 — Tools through the door, and the `answer` deadline
Status: decided

Every MCP tool already goes through `wiring.invoke`, and after 262 every operation is served. Three local reads were left in `amoeba.mcp`. This slice removes each on a joined machine:

| Local read today | Now |
|---|---|
| The config and deadline check at start | Not made with a client file (D8) |
| The config load and deadline check before `answer` | Made on the hub (below) |
| `as_of_seq` for the resource | From the tick's reply (D10) |

`handle_pause` from MCP starts the CLI's `handle-pause` detached, which 262 serves. Its logs stay under the machine's own state directory.

The wake command is never sent from MCP: 261 put `refuse_door_fields` in the client part of `add`, which rejects the field on the MCP door before any hub call. A test here pins it through the door.

**The deadline.** An MCP `answer` on the run's own machine runs the resume in the call (D7). It takes one door call that records the answer and returns the claim, the resume, and one door call that records the outcome. That is exactly what 262's `resume_claim_seconds(config)` bounds, so the check uses that one function and no second definition:

`resume_bound_seconds(config) - BUSY_TIMEOUT_SECONDS + 2 * CALL_BOUND_SECONDS`

`resume_bound_seconds` is in `operations/resume.py` today:

| Part | Seconds |
|---|---|
| `resume_wait_seconds` | 60 in the example config |
| `RESUME_POLL_INTERVAL_SECONDS` | 0.5 |
| Two polls, `2 * RUN_POLL_TIMEOUT_SECONDS` | 60 |
| Two graces, `2 * TERMINATE_GRACE_SECONDS` | 10 |
| The store write, `BUSY_TIMEOUT_SECONDS` | 5 |
| **`resume_bound_seconds`** | `resume_wait_seconds` + 75.5, so 135.5 |

Through the door the store write is replaced by the two call bounds (43 each, 260 D7): `resume_wait_seconds` + 156.5, so 216.5 with the example config. Today's bound also adds three local store waits (`ANSWER_STORE_WAITS`: the legacy-move lock, the store open and the answer's write). Through the door none of them is made on the client: a joined machine runs no state move and opens no store, and the answer's write is the hub's one lock wait, inside the answer call's bound.

216.5 is above today's deadline of 180, so the example config would have every MCP `answer` refused. Therefore:

- `MCP_CALL_DEADLINE_SECONDS` moves to `wire.times`, where both sides read it, and becomes 300. Through the door `resume_wait_seconds` must be below 300 - 156.5 = 143.5.
- It joins 260's pinned tuple of the door version and the times, and the door version goes up by one, from the 2 that 262 set to 3. A server still running the old program would cut a call off at 180 seconds while the hub allowed 300, which is the disagreement the version exists to stop. Only fixtures are joined, so the bump costs nothing now.

The hub part of `answer` runs the check first, when `via` is MCP, before anything is recorded. A config that fails raises `DeadlineError`. That class is in `wiring.py` today, which neither `operations` nor the hub may import. It moves to `operations/errors.py` and joins 260's `OPERATION_ERRORS` there (260 D8), so the hub refuses it as `hub_error` like every other operational error, with no case of its own. `wiring.DeadlineError` stays as a name for the same class, so the local check and `amoeba-mcp`'s handlers are unchanged. The message names `resume_wait_seconds`, the hub's `config.yaml`, the bound, the deadline and the largest value that passes. Refusing through an existing code means a client of any version can show it.

The check runs for every MCP `answer`, whichever machine the run is on, as it does today for every answer. It is a check of the config, and a refusal should not depend on where the run happens to be.

With no client file the check is today's, in the MCP process, against the same constant. There the bound is today's `answer_bound_seconds`, `resume_bound_seconds` plus the three store waits (15): `resume_wait_seconds` + 90.5. So `resume_wait_seconds` must be below 300 - 90.5 = 209.5.

The longest any other tool can take through the door is `status`, 236 seconds in all:

| Part | Seconds |
|---|---|
| The caller's own `cf get`, `CF_GET_TIMEOUT_SECONDS` (261 D5) | 30 |
| The run listing, `RUN_POLL_TIMEOUT_SECONDS` (261 D11) | 30 |
| The directory lookups, `RUNS_GATHER_SECONDS` (261 D11) | 60 |
| The one lookup in flight when that time runs out (261 D15) | 30 |
| `open_runs`, one call bound (262 D9) | 43 |
| The call itself, one call bound | 43 |
| **`status`** | 236 |

That is below 300, and it is reached only when `cf` or `sq` hangs.

### D10 — The `amoeba://inbox` resource
Status: decided

`resources/read` returns `{"member", "as_of_seq"}` from memory: the member's id and the `as_of_seq` of the newest tick reply. The handler makes no store read and no hub call.

The number is at most one tick old. That is safe: an agent that passes an older `as_of_seq` to `inbox` reads a little more, never less.

When no tick has had a reply yet, the read fails with an internal-error response carrying the tick's last error, as a `StoreError` does today.

The four handlers were written for a member that is resolved once. Now it can appear or go after the first tick, so each answers from the newest tick's reply, in this order:

| Handler | No tick has had a reply | The newest reply has no member | It has a member |
|---|---|---|---|
| `resources/list` | Lists the resource | Lists the resource | Lists the resource |
| `resources/read` | Internal error with the tick's last error | Invalid-params, "this server serves no member", as today | The document above |
| `subscribe`, `unsubscribe` | Internal error with the tick's last error | Invalid-params, as today | Sets or clears the flag, as today |

`resources/list` now offers the resource in every session. Today it is empty for a session with no member. A client lists once, at start, and the handshake has no way to tell it the list changed, so a session that started while the hub was down, or before its repo was added, would never be offered the resource without a reconnect. Listing it always costs nothing: a read or subscribe on a session with no member is refused in the words above.

### D11 — Runs on other machines
Status: decided

Only a machine can read its own Squadron runs. So each machine's `runs` document (261 D11) is kept on the hub. The hub part of `status`, and of `list` with no subject, upserts the calling machine's document into `machine_runs` with the hub's time, in the same transaction as the rest of the call.

`list` and `status` show each other machine's runs as that machine last reported them, under the machine's own heading. The hub part reads the run lines out of the stored document and adds them to that machine's entry in `machines`: for each run that is not completed, its id, pipeline, status, directory and, when paused, its checkpoint. It does nothing else with them:

- Runs from another machine are not placed under members, and no question is judged against them.
- Nothing is closed or swept. A question on another machine shows as the store has it, with its machine named (262 D10), until its own machine calls (262 D9). Its `run_state` is the new value `other_machine`: this call cannot say where that run is.

How old a stored document is depends on when that machine last ran `status` or `list`. A session's tick does not gather runs: that is an `sq` call and several `cf` calls, too much for every few seconds. So the heading always gives the age.

Limits and failures:

| Case | What happens |
|---|---|
| The calling machine's document does not parse | The call is refused as `malformed_call` before anything runs (261 D5). Nothing is stored and the earlier document stays |
| The document is too large | The client cuts it to `RUNS_DOCUMENT_MAX_BYTES` (768 KiB) and says how many runs it left out (261 D11). A body over 260's `MAX_CALL_BYTES` (1 MiB) is refused before it is read. So no stored document is over 1 MiB, and the hub checks nothing more |
| Another machine's stored document does not validate, because an older program wrote it | That machine's entry has no run lines and carries `runs_problem` with the error's text. The rest of the `status` call is unaffected. The document is replaced at that machine's next `status` or `list` |
| The write of the calling machine's document fails | It is in the call's one transaction, so the call fails as any store error does, and nothing of the call is stored |

- Rejected: placing another machine's runs under members and judging its questions from the stored document. The plan asks for runs "as last reported, with the machine named", and no more.

### D12 — What `list` and `status` show
Status: decided

| Result | Gains |
|---|---|
| `SessionEntry` | `machine`, `client_version`, `door_version`, `behind` |
| `StatusResult` | `hub_door_version`, and `machines`: each machine's `name`, `last_called_at`, `client_version`, `door_version`, `behind`, and for every machine but the caller `runs_reported_at`, `runs` (the run lines of D11) and `runs_problem` |
| `WaitingRunState` | `other_machine` |
| `amoeba hub machines -j`, each machine | `door_version`, `behind` |

`behind` is true when the door version differs from the hub's, false when it is the same, and null when none is recorded, which is the `local` machine (D6).

No field is renamed or removed. `list -j` still equals the `status` document.

A member's `sessions` are its live sessions on every machine, oldest first.

Text:

- A session line gains its machine after the client: `<client>  <machine>  <directory>  up <age>  last beat <age> ago  push confirmed|push unconfirmed`. A behind one ends with `behind`.
- A section **Runs on other machines** has one heading per other machine, `<machine>, reported <age> ago` or `<machine>, nothing reported`, with one line per run under it: id, pipeline, status and directory. A machine whose stored document does not validate has the heading `<machine>, reported <age> ago, runs unreadable: <runs_problem>` and no run lines (D11). A waiting line for a question on another machine ends with `on <machine>`, as in 262.
- A section **Behind the hub** appears when any machine or session is behind. It lists each with its client version and door version, gives the upgrade command (`uv tool install --force amoeba-ai`), and says to restart the sessions listed. One whose door version is above the hub's is listed as `ahead of the hub`, and for it the section says to upgrade the hub and gives no client command (D6).
- `amoeba hub machines` gains the door version on each machine's line, and the line ends with `behind` or `ahead of the hub` when it differs from the hub's. The hub's own door version is on the first line.

With no client file, `hub_door_version` is the running program's own `DOOR_VERSION`. It is also the value the waking rule binds there (D13).

Sessions and machines do not count as waiting on the PM and set no notice, as in 241 D8.

### D13 — The schema: migration 014
Status: decided

One migration, `014_sessions_across_machines.sql`, run by both ways. It only adds.

- `sessions.client_version` (text) and `sessions.door_version` (integer), both nullable, with a `BEFORE INSERT` trigger that aborts when either is null. The pattern is 260's for the owner.
- `machines.door_version`, integer, null until the machine's next call that is not a session's tick or exit call (D6).
- **`machine_runs`**: `machine_id` (key, references `machines`), `owner_id`, `reported_at`, `document` (the JSON text). 260's owner trigger is added for it.

`sessions.machine_id` is 260's.

**Rows from before the migration** have no door version. Their writers are programs that refuse the newer schema, so they can never beat again. There are two predicates in `store/sql_sessions.py`, each defined once:

- **`LIVE_SESSION`,** used by `live_sessions` (display) and the prune, becomes "a fresh heartbeat and a door version". A behind session passes it, so it is shown. 264 names the heartbeat test inside it `FRESH_HEARTBEAT` and composes `LIVE_SESSION` from that, so the two predicates here become three (264 D2).
- **The waking rule,** used by `live_member_ids`, is `LIVE_SESSION`, push confirmed, and a door version equal to the hub's, which is bound as a parameter (D6).

A row from before the migration fails both. It is never shown and never holds off a wake, and the first refresh's prune deletes it. No reader has to handle a null.

`EXPECTED_SCHEMA_VERSION` becomes 14.

### D14 — What the door serves, documents and the live store
Status: decided

- `STEP_CALLS` gains `session_tick` and `session_end`.
- In 260's entry-point table (D2), the row for `amoeba-mcp` start is removed, and the row for a tool call loses its note about the deadline check. After this slice every operation is served and no entry point raises `NotServedError`. So the error and the client's served check in `wiring.invoke` are deleted here, with the tests that expect them. A test asserts every `OperationName` but `handle_pause` is in `SERVED_OPERATIONS`. `handle_pause` is never a door call: the command runs on its own machine and makes its store steps as step calls (262 D5), so adding its name would have the hub accept a call it has no function for. The same test asserts `handle_pause` is not in the list. The hub keeps its own check and its `not_served` refusal, which is how it answers a call name it does not know.

Documents brought in line:

- `docs/mcp-server.md`: start-up on a joined machine; the tick in place of the two loops; the member worked out each tick; what a failed tick does; the deadline of 300 and the two limits on `resume_wait_seconds`; Codex's `tool_timeout_sec` of at least 305; what Claude Code does with a call that runs past two minutes, as step 1 of the Development Approach measured it; the resource listed in every session and its number being one tick old; the new log lines.
- `docs/cli-contract.md`: the result fields in D12, the **Behind the hub** and **Runs on other machines** sections, `other_machine`, and the door version in `amoeba hub machines`.
- `docs/store-contract.md`: migration 014, who writes `sessions`, and that every time in it is the store's own clock.
- `docs/config-contract.md`: `session_heartbeat_seconds` and `session_stale_seconds` as judged on the hub, the third check on `session_stale_seconds` (D5), and `resume_wait_seconds`'s limits.

The live store is migrated by `scripts/update_live.py update` when the release runs, as in 260 and 262. The script backs up the store and config first. Its read-back gains two checks after the `amoeba list` it already runs: the `status` document holds a `machines` list with the one `local` machine, and `machine_runs` holds one row for it. A test runs `update` and `restore` against a copy of a schema-13 store. 264 replaces these read-back checks, and the others that open the local store: from its release the script updates the hub first and then the client (264 D10).

The restore path is `uv run python scripts/update_live.py restore`, recorded in the slice notes. It puts back the store as it was before the update, so every answer, message and decision recorded since is lost, and it reinstalls the release that was installed before. `amoeba-mcp` sessions open at the update are the old program and refuse the newer schema; the script lists them, and each is restarted.

### D15 — Tests and the fixture
Status: decided

- **Unit.** `session_tick` and `session_end` are plain functions on a throwaway store with a clock the test sets. One test per case of D2's "due" rule, per row of D5's table, and for the behind rule in D6. The third config check (D5) is tested with the example config, with heartbeat 5, poll 5 and stale 10, which is refused, and at its boundary. The touch is tested for a session call and for another call from the same machine (D6).
- **The loop.** `mcp.tick` is tested in process with memory streams and a `Steps` the test supplies: baseline, an event on a rise, a new baseline when the way changes, each failure in D4, and recovery. Each cell of D10's handler table has a test. The existing 241 tests run on `LocalSteps`.
- **In-process hub.** 260's helper takes the door version to serve, so a test can restart a hub one version up.
- **The two-machine fixture** gains a helper that starts `amoeba-mcp` in a client home's repo over real stdio with the SDK client, and reads its notifications and its stderr.
- **Load.** 260's `tests/load/test_door_load.py` adds 50 ticking sessions across 10 members, each ticking every 0.5 seconds for 20 seconds, beside its 16 clients reading and writing. That is the tick rate of 500 real sessions at the example interval. It asserts: every tick is answered within 2 seconds; no session goes more than 3 seconds between two replies, which is what "no tick is starved" means here; every session's row stays live throughout; and 260's two bounds still hold. The measured figures go in the slice notes. `tests/load/test_presence_load.py` keeps running on the local store.
- **Live.** `tests/live/channels` gains a variant on the two-machine fixture: the real Claude Code session is in the member's repo on one machine, and the request is sent with `amoeba send` from a repo on the other. It also gains the long-call test that step 1 of the Development Approach describes.

### Departures from the parent documents

| Parent says | This design | Why |
|---|---|---|
| Architecture ("Sessions across machines"): a session row gains its machine and its client version | It also gains the door version, a machine gains its door version, and `machine_runs` is added, as the plan's 263 entry lists | "Behind" is about the door version, and another machine's runs must be kept somewhere to be shown |
| Architecture: the tick refreshes its session row when a heartbeat is due | The hub decides when it is due, on its own clock and config | The client then needs neither the heartbeat setting nor a clock the hub would have to trust |
| 241 D3: the member is resolved once, when the session starts | Worked out on every tick; `cf` is asked until it answers | The tick must carry the project id anyway, to write a row again after a prune. A project added later gets push with no reconnect |
| 241 D2: a store error ends presence | A failed tick is skipped, whatever the operational error | A session must come back by itself after the hub restarts |
| 241 D6: a row written again after a prune keeps its first `started_at` | It gets the hub's time at the new insert | The client sends no time |
| Architecture: the MCP deadline check runs on the hub with the network times added | Also raises the deadline from 180 to 300 seconds and the door version by one (the 260 and 262 rows below) | With the network times added, the example config's bound is 216.5 seconds |
| Plan and architecture ("Work that belongs to a machine"): a client that sees the flag makes one more call to claim the work | An MCP tool call leaves that to the session's next tick. The architecture's "Same machine, no wait" is kept: an MCP `answer` on the run's machine still resumes in the call (D7) | A claim made inside a tool call would count against the call's deadline |
| Architecture ("A repeated call is safe"): the hub keeps each writing call's result | `session_tick` and `session_end` write and keep none | A tick is never repeated, and a result kept for every tick of every session would be the store's largest table for nothing. A test pins the retry time of 0 (D2) |
| Plan: 263 provides the session rows of joined machines, which 262's presence check reads | It does, and the rows of behind sessions are left out of that check (D6) | A behind session's ticks are refused, so it gets no push and cannot stand in for a wake |
| Architecture ("Retry"): a client that gets no reply repeats the call; only the tick is exempt | `session_end` is also one attempt | It runs while the process is exiting. A row it leaves goes stale by itself (D8) |
| Architecture and 262 D12: the file clean-up runs from any call | On the MCP door it runs from the session's tick, not from a tool call | It is part of the after-step (D7). Every open session ticks, so it still runs at least as often |
| 241 D5: `resources/read` reads `as_of_seq` from the store | It returns the newest tick's number | No call is needed, and an older number is safe |
| 241 D5: `resources/list` is empty for a session with no member | It lists the resource in every session (D10) | The member can appear after the client has listed, and the handshake cannot say the list changed |
| 241 D7: two checks on the session timing keys | A third: `session_stale_seconds` is at least `session_heartbeat_seconds + 2 * notify_poll_seconds` (D5) | A row is now refreshed by the first tick that finds it due, so the gap is a heartbeat plus a poll interval |
| Architecture ("Machines"): a machine holds the client version it last called with | The versions of its last call that was not a session's tick or exit call (D6) | An old session left open would otherwise write the old versions back every few seconds |

### Amendments to 260 and 262

These change what the two earlier designs say. Each is stated in that design's own terms. Each is also stated in that design where it applies. A row added or changed by a revision of this document is brought into that design with the same revision.

| Design says | This slice | Where |
|---|---|---|
| 262 D10: the after-step runs at the end of `wiring.invoke` on both doors, after every operation on the CLI door and after every operation but `answer` on the MCP door | For every operation on the CLI door. `invoke` takes whether to run it. On the MCP door it does not, and the session's tick runs it. `tests/test_wiring_release.py::test_the_mcp_door_starts_the_ended_held_question_too` is changed to assert that | D7 |
| 262 D3: `steps_for(layout)` picks one way "when a command starts, by whether a client file exists, and the command keeps it to its end" | That holds for commands. `steps_for` also takes the door times and a session identity. A session's tick calls it on every tick, with `TICK_TIMES` and the four values the session headers carry | D1, D4, D6 |
| 260 D7: the pinned tuple is the door version and the network times, and `DOOR_VERSION` is 1 | The tuple also holds `MCP_CALL_DEADLINE_SECONDS`, and the door version goes up by one, to 3 after 262's 2 | D9 |
| 260 D8: the touch sets `last_called_at` and `client_version` | It also sets `machines.door_version`. For `session_tick` and `session_end` it sets `last_called_at` only. On a `door_version` refusal of a tick it writes the session's row from the headers | D6 |
| 260 D8: the five operational errors are `OPERATION_ERRORS` in `operations/errors.py` | `DeadlineError` moves there from `wiring` and is the sixth | D9 |
| 260 D13: `amoeba hub machines` lists name, token, `last_called_at` and `client_version` | It also shows each machine's door version and whether it differs from the hub's | D12 |
| 260 Component Structure: `wire.protocol` holds the call and reply shapes | It also holds the session id's shape and the client-name pattern, moved from `mcp/presence.py` | D6 |
| 260 D6: a call's headers are the token, the two versions and the call id | `session_tick` and `session_end` also send the four `Amoeba-Session-*` headers | D6 |
| 262 D3: `WRITING_STEPS` are the writing rows of `STEP_MODELS`, the steps whose result is kept | The row's flag means "its result is kept". `session_tick` and `session_end` write and have it unset | D2 |
| 262 D6 and Provides: `resume_bound_seconds` is unchanged and, with no client file, bounds the MCP deadline check | Through the door the check is on the hub and uses `resume_claim_seconds`, 216.5 seconds with the example config | D9 |
| 260 D2, 262 D15: `NotServedError` and the served check at the top of every entry point | Both are deleted, because nothing is left unserved | D14 |

## Implementation Details

### Migration Plan

This slice restructures `amoeba.mcp`'s presence code. The order keeps the suite passing on the local store.

- **What moves.** The store work in `wiring_presence` (`beat_session`, `end_session`, `read_high_seq`, `read_push_rows`, `read_as_of_seq`, `lookup_member`) moves into `steps.session`. `mcp.inbox_watcher` and `presence.heartbeat_loop` are replaced by `mcp.tick`.
- **Consumers.** `mcp.presence_task` (starts the loop, makes the exit call), `mcp.inbox_resource` (reads memory), `mcp.server` (start-up by mode, no opener), `mcp.in_process` (the deadline constant's new home, the after-step left out), `tests/mcp_server/presence_rig.py` and `serving_rig.py`, and `tests/load/test_presence_load.py`.
- **Behavior kept.** With no client file every 241 test passes on the local store, with six kinds of edit:
  - A test that built `PresenceDeps` with a store opener and timings builds it with `LocalSteps` on that store and a config. The timings the rigs use today pass the third config check (D5).
  - A test that pinned "a store error ends presence" asserts the skipped tick and the recovery.
  - A test that pinned one-shot member resolution asserts the next tick.
  - A test that pinned 180 seconds or 89.5 uses the new constant and limit.
  - The two tests that pin an empty `resources/list` for a session with no member, in `tests/mcp_server/test_inbox_resource.py` and `test_presence_serving.py`, assert the resource is listed and a read is refused (D10).
  - `tests/test_wiring_release.py::test_the_mcp_door_starts_the_ended_held_question_too` asserts that the MCP call starts nothing and that the session's next tick starts the held question (D7).
- **Existing data.** Migration 014. No row is rewritten.

### API Contracts

Door additions:

- Calls: `session_tick` and `session_end`, both steps, neither keeps a result.
- Headers: `Amoeba-Session-Id`, `Amoeba-Session-Project`, `Amoeba-Session-Client` and `Amoeba-Session-Directory`, on those two calls.
- Reply to `session_tick`: the fields in D2, with 262's `work`.
- `answer` with `via` MCP can be refused as `hub_error` with a `DeadlineError` message.

The door version goes up by one, for the deadline (D9). The added calls, headers and refusal would not have needed it.

`amoeba-mcp` protocol surface: unchanged from 241. Result fields added: D12.

New log lines on the session's stderr: `tick failed: <ErrorName>: <text>` once per run of failures, `tick recovered` when one ends, and today's presence line with the machine added at its end: `presence for <member>: protocol <version>, client <name>, machine <machine>`. The protocol version and client stay in it, so the tests that match its start and its `client` part are unchanged. The machine is the name in the client file, or `local`.

### Database / Storage Schema

Migration 014 as in D13. `tests/store/test_migration_014.py` covers: a schema-13 fixture's row counts unchanged; a session insert with a null client version or door version refused; a session row from before the migration not returned by `live_sessions` or `live_member_ids` and deleted by the next prune; one `machine_runs` row per machine, replaced by an upsert.

## Integration Points

### Provides to Other Slices

- **Session rows from every machine,** which 262's `wake_due` already reads. A live, push-confirmed session on any machine holds off a wake for its member.
- **Every entry point served.** 264 can delete the local-store way and `LocalSteps`. The tick does not change: it already runs on `Steps`.

### Consumes from Other Slices

- From 260: the door, the touch and the refusal path, `OPERATION_ERRORS`, the network times, `hub machines`, `rm-machine`, `join --set-aside-local` and `leave`, the fixture and the load test.
- From 261: `here`, `find_caller`, the `runs` document and the hub part of `status`.
- From 262: `Steps` and its two implementations, the work flag, `claim_work`, the after-step as amended above, `answer` through the door, `resume_claim_seconds`, and the machine on question entries.

A tick or tool call that fails at the door fails with 260's errors. This slice adds none.

## Success Criteria

### Functional Requirements

- With a session on fixture machine `beta` in a member's repo, a request sent from a repo on `alpha` produces one channel event in that session within one poll interval plus the tick bound.
- A session on each of two fixture machines appears under its member in `list -j` from either machine, with its machine's name and client version.
- A session killed with SIGKILL is not listed once `session_stale_seconds` has passed on the hub's clock, and the next refresh of any session deletes its row. A session whose clock is an hour ahead writes rows whose three times are the hub's, and is listed and goes stale like any other.
- A clean exit deletes the row. An exit with the hub stopped returns within `TICK_BOUND_SECONDS` and the row goes stale.
- With the hub stopped for a minute: at most one tick call is ever in flight; the number of attempts is at most the elapsed time over the interval, plus one; each tool call returns `HubUnreachableError` naming the hub's address; `list` from the other machine, once the hub is back and the stale time has passed, shows no session until its next tick; and a request delivered just before the stop is pushed by the first tick after the hub returns.
- A tick refused as `hub_error` because the hub's `config.yaml` is broken is skipped with one WARNING, and the first tick after the file is fixed succeeds.
- A session ticking against a hub that is restarted one door version up: its tools return the upgrade message with both versions; `list` from an up-to-date machine shows that session under its member as behind and its machine, whose last call was that tool call, in **Behind the hub**; a wake for that member is no longer held off by it. A session started by the old program after the restart is listed as behind in the same way.
- With an old session ticking on a machine, an `amoeba` command from the current program there leaves the machine not behind in `list` from the other machine and in `amoeba hub machines`, through the session's next ticks. The session is still listed as behind. `amoeba hub machines -j` holds each machine's `door_version` and `behind`.
- A session whose door version is above the hub's is listed as `ahead of the hub`, and the section says to upgrade the hub.
- A tick's reply with `work: true` starts that machine's waiting resume: a fixture pipeline paused on `alpha` and answered from `beta` resumes on `alpha` with no command run there, only an open session. With three sessions open on `alpha`, the run is resumed once.
- A `claim_work` that takes 20 seconds delays no tick: ticks keep their interval, and no second after-step starts until the first ends.
- An MCP tool call's result returns before any `claim_work` call is made for it.
- A session in a directory that is no member writes no row, sends no event, and its ticks still start the machine's waiting work. After `amoeba add` in that repo, the next tick writes the row with no reconnect. After `amoeba rm`, the next tick deletes it.
- With a `cf` stub that fails twice and then answers, the session has a row after the third tick. With one that hangs, each tick ends at the `cf` timeout with one WARNING for the run of failures, and `resources/read` answers with that error instead of waiting.
- A session whose directory `cf` reports as not a project asks `cf` again no more than once per `CF_REASK_SECONDS`, and has a row within that time plus one tick after the directory is made a project and added.
- A `claim_work` from a tick that gets no reply, and one that is refused, each start nothing and leave presence and the next tick as they were. Refused on ten ticks in a row, it logs one WARNING, and one INFO line when it next succeeds.
- With a stored `machine_runs` document that does not validate, `status` from another machine succeeds, shows no run lines for that machine, and carries `runs_problem` on its entry. The text heading for that machine says its runs are unreadable and gives the problem.
- No code names `NotServedError`. Every `OperationName` but `handle_pause` is in `SERVED_OPERATIONS`, and `handle_pause` is not.
- A session open across `amoeba join --set-aside-local` uses the hub from its next tick, takes a new baseline and sends no event for it.
- `amoeba-mcp` starts in a home that holds only a client file and a saved certificate, with the hub stopped, and creates no local file. Every MCP tool then runs through the door with no local `config.yaml` present. With a client file whose certificate is missing, it refuses to start and names the file.
- The MCP `add` tool with `wake_command` on a joined machine is rejected, and the hub's log shows no `add` call for it.
- An MCP `answer` for a run on the session's own machine returns the resume's outcome in its result, and no `resume-run` process is started for it.
- An MCP `answer` with the hub's `resume_wait_seconds` at 143.5 or more is refused with `DeadlineError` in the message, naming the key and the largest value that passes, and no answer is recorded. With the example config it is recorded and resumed. The same `answer` from the CLI is not checked.
- `resources/read` returns the member and the newest tick's `as_of_seq` with no store or hub call, and fails naming the tick's error when no tick has replied. `resources/list` lists the resource in a session with no member and in one whose first tick failed. `subscribe` in such a session is refused, and succeeds once a later tick has a member, with no reconnect.
- A config with `session_heartbeat_seconds` 5, `notify_poll_seconds` 5 and `session_stale_seconds` 10 is refused at load, naming the three keys. The example config loads. With heartbeat 5, poll 5 and stale 15, and a clock the test sets, a session that ticks every poll interval is live at every tick.
- A tick held in its hub call while the session exits writes its row after `session_end`. That row is not listed once `session_stale_seconds` has passed, and the next refresh of any session deletes it.
- After `status` on `alpha`, `list` from `beta` shows `alpha`'s paused run under the heading `alpha, reported <age> ago`, and `alpha`'s waiting question with `on alpha` and the run state `other_machine`. A machine that has stored no document shows `nothing reported`. Nothing on `alpha` is closed by `beta`'s call.
- `amoeba hub rm-machine` deletes the machine's session rows and its stored runs. A session still open there has its ticks refused as `bad_token` and keeps serving its tools' errors; after a new invite and `join` its next tick succeeds with no restart.
- The 241 live test passes with the session on one fixture machine and the request sent from the other: `tool inbox called` appears in the server log with nothing typed, and `list -j` from the sending machine shows the session with `push_confirmed_at` set.
- With no client file, the 241 tests pass on the local store with the six kinds of edit in the Migration Plan.
- `scripts/update_live.py update` and `restore` pass against a copy of a schema-13 store.
- The long-call test of step 1 runs with a real Claude Code session and a tool that takes 220 seconds, and its result is one of the two the step names. The slice notes record which, and `docs/mcp-server.md` and the launch settings match that result.
- `amoeba-mcp` started in a hub home refuses to start with `HubHomeError` and leaves the hub's store unchanged.
- On a joined machine that had no local store, with a session open: after `amoeba leave` and the session's next tick, if that tick made a local store, a plain `amoeba join` is refused and names `--set-aside-local`, and `amoeba join --set-aside-local` joins. The session then uses the hub from its next tick.

### Technical Requirements

- `ruff`, `pyright` strict and the full `pytest` run pass.
- The import rules in Component Structure are tested.
- The door load test passes its bounds with 50 ticking sessions (D15), with the measured figures in the slice notes.
- 260's pinned tuple holds the new door version and `MCP_CALL_DEADLINE_SECONDS`.
- `tests/mcp_server/test_protocol_pin.py` passes unchanged.
- New source files stay near 300 lines.
- The documents in D14 are updated and `tests/test_contract_docs.py` passes.

### Integration Requirements

- 262's waking fixture, run with a live push-confirmed session for the recipient on the other machine, starts no wake.
- 264 can delete `LocalSteps` and the mode switch without changing `mcp.tick`.
- The PM's install, with no client file, behaves as before with these differences: one loop in place of two; a store error no longer ends presence; a Context Forge project added after its session started gets presence at the next tick; an MCP tool call's waiting work starts at the next tick; the MCP call deadline is 300 seconds; `list` shows the `local` machine on each session line; `resources/list` offers the inbox resource in every session; and the config has a third timing check, which the live config passes (D5).

### Verification Walkthrough

`tests/hub_fixture.py`, `amoeba join` and the hub commands come from 260 to 262 and do not exist until those slices are built. Everything else named here exists today or is built in this slice.

1. The checks and the suite, from the repo root:

   ```bash
   uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest -q
   ```

   Expected: no formatting change, `All checks passed!`, `0 errors`, and no test failure.

2. This slice's own tests:

   ```bash
   uv run pytest tests/mcp_server tests/hub/test_sessions.py tests/store/test_migration_014.py tests/load/test_door_load.py tests/mcp_server/test_protocol_pin.py -v
   ```

   Expected: all pass. The load test prints the slowest tick and the longest gap between two replies, both under their bounds.

3. The live tier, which spends on a model:

   ```bash
   set -a; source .env; set +a
   AMOEBA_LIVE_CHANNEL_MODEL=sonnet uv run pytest tests/live/channels -v
   ```

   Expected: 241's four tests pass on the local store, and the two-machine variant passes: the session on one machine calls `inbox` with nothing typed after a `send` from the other. The long-call test passes with the result recorded in the slice notes at step 1 of the Development Approach.

4. By hand, on the fixture's hub with client homes `alpha` and `beta`, `widget` added on `beta` and `tool` on `alpha`. Each step shows one functional criterion, named by its opening words.

   - **Push across machines** ("With a session on fixture machine `beta`"). On `beta`: `cd ~/beta/widget && claude --dangerously-load-development-channels server:amoeba`. On `alpha`: `cd ~/alpha/tool && amoeba send --to widget --id demo-1 --subject "Need X" --body "Please add X"`. Within a few seconds the session shows `← amoeba: Amoeba: 1 new deliveries for this repo ...` and the agent calls `inbox`. `amoeba list` on `alpha` shows the session under `widget` with machine `beta` and `push confirmed`.
   - **The hub goes away** ("With the hub stopped for a minute"). Stop the hub and ask the session for `list`: the tool returns `HubUnreachableError` naming the hub's address, and the server's stderr has one `tick failed:` line. Start the hub: stderr gets `tick recovered`.
   - **Work from a tick** ("A tick's reply with `work: true`"). With a run paused on `beta`: on `alpha`, `amoeba answer <run id> --text "Use the v2 schema"` says the run is on `beta`. A few seconds later `amoeba list` shows the answer as resumed, with nothing typed on `beta`.
   - **An agent answers** ("An MCP `answer` for a run on the session's own machine"). With a second run paused on `beta`, ask the session there to answer it with the `answer` tool. The result holds the resume's outcome, `resumed`. While the tool runs, `pgrep -f "amoeba resume-run"` on `beta` prints nothing: the resume ran inside the call. Its `sq` logs and attempt file are under `beta`'s `logs/resume/<run id>/`, as for any resume (262 D6).
   - **Runs elsewhere** ("After `status` on `alpha`"). `amoeba list` on `beta`, then on `alpha`: `beta`'s runs show under **Runs on other machines**, headed `beta, reported <age> ago`.

5. On the local store, after the release's update: `amoeba list` shows each live session with the machine `local`, and a session started before the update is listed by the script as one to restart.

## Risk Assessment

### Technical Risks

- **Every tick is a network call and a write lock on the hub** (260's touch). Many sessions could slow each other or the CLI.
- **The presence code of the PM's install is restructured** two slices before the local way is deleted. A mistake there stops push on the install in daily use.
- **Push still rests on a research-preview Claude Code feature.** Nothing here changes how it is used, and an update can still break it.

### Mitigation Strategies

- The load test bounds each tick and the gap between replies (D15).
- The 241 tests and the 241 live test run on the new loop (Migration Plan, D15). When push fails, polling `inbox` still delivers everything.
- The pin test and the live test are the detectors, run as the first implementation step.

## Implementation Notes

### Development Approach

Suggested order. Each step leaves the suite passing on the local store.

1. Check the client facts before anything is built. Both parts run on today's code.
   - Run `tests/live/channels` and the pin test against the installed Claude Code and `mcp`, and correct 241's dated facts in `docs/mcp-server.md` if either differs.
   - Add the long-call test to `tests/live/channels` and run it. It registers a small stdio server, built on `serve_pinned` as `tests/mcp_server/pin_server.py` is, with one tool that waits 220 seconds and then returns a marker string. 220 is above the 216.5 seconds an `answer` can take with the example config, and past Claude Code's 2-minute move to the background. A real Claude Code session, started by the existing harness with no timeout setting of its own, is asked to call the tool. The test waits 300 seconds and one model turn for the marker to show in the session, and records what the session showed at two minutes. It needs no hub and no Amoeba store. Each result has its handling, and the slice goes on after any of them:
     - **The marker reaches the agent,** as the tool's result or as the result of a call that was moved to the background. Nothing is set. `docs/mcp-server.md` says what the agent sees at two minutes and when the result arrives.
     - **The marker does not reach the agent.** The test is run again with `CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS` set to 0 in the session's environment, which the installed program's text says turns the move off. If the marker then arrives, `docs/mcp-server.md` tells Claude Code users to set it, beside the Codex step, the live fixtures set it, and the Operator Walkthrough's start step names it.
     - **It still does not arrive.** Then a Claude Code session is not shown the result of an `answer` that runs past two minutes. `docs/mcp-server.md` and the `answer` tool's description say so, and say to read the outcome with `list`. The answer is still recorded and the run still resumed, because the server abandons a cut-off call's thread and does not stop it (Operator Walkthrough).
   - The test stays in the live tier with the settings of the result it had. The result, the settings and the measured times go in the slice notes.
2. Migration 014, the store functions for the version columns and `machine_runs`, the new live rule, and the third config check.
3. `steps.session` with its models and unit tests.
4. `mcp.tick` and `mcp.after_runner` on `LocalSteps`; move `presence_task`, `inbox_resource` and `server` onto them; delete `inbox_watcher` and the heartbeat loop. The 241 tests pass with their edits.
5. The door side: the two step names, `TICK_TIMES`, the four session headers and the session identity in `steps_for`, the touch's door version and the behind refresh in `handle_call`.
6. Start-up by mode, the deadline constant in `wire.times`, the door version, `DeadlineError` in `operations/errors.py`, and the check in the hub part of `answer`.
7. `machine_runs` in the hub part of `status`, the result fields and the renderers.
8. The fixture helper, the cross-machine tests, the load test and the live variant.
9. `rm-machine`, `hub machines`, the documents and `update_live.py`.

### Special Considerations

- **Prompt injection.** The channel event is built from the same closed values as in 241, now read from the tick's reply. No message text is in the reply.
- **Threads.** The tick, the after-step and each tool call run in their own worker threads. Only event-loop tasks touch `PresenceState`, as today. A tick abandoned at exit finishes by itself and holds nothing. If its call lands after the exit call, the row it writes goes stale (D8).
- **What a session sends.** Its directory and client name go to the hub and are shown by `list` on every machine. Both are already shown today, on one machine.
- **Spend.** The live test makes real model calls on the configured model.

## Operator Walkthrough

Done as the person running it. Before 264 only fixtures are joined; the PM's install runs the same loop on its local store.

- **Start.** A session started in a repo on a joined machine starts `amoeba-mcp` as before. The hub can be down at that moment. One step for Codex users only: set `tool_timeout_sec` for the `amoeba` server to at least 305 in Codex's config, where it was 185. Claude Code needs no change, unless the long-call test (Development Approach, step 1) found that it does. Then it is the one setting that test passed with, `CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS=0`, and `docs/mcp-server.md` gives it beside the Codex step.
- **A client cuts a tool call off before the server does.** This is Codex with `tool_timeout_sec` left below 305, on a slow `answer`. The agent sees a timeout. It is also a Claude Code session that is not shown the result of a call that ran past two minutes, if the long-call test found that case; `docs/mcp-server.md` then says so. The work still finishes: the call's worker thread is abandoned, not stopped (`abandon_on_cancel`, as today), so the answer is recorded, the resume runs and its outcome is recorded. `amoeba list` shows it. Do not answer again. Then raise `tool_timeout_sec`.
- **Normal path.** `amoeba list` on any machine shows each live session under its repo, with its machine. Mail sent from any machine reaches an open session within a few seconds.
- **The repo was not added yet.** The session has no line in `list`. After `amoeba add` there, it appears within one tick.
- **`cf` is broken when the session starts.** The server's stderr says so once. When `cf` works again the session appears at the next tick.
- **The directory is not a Context Forge project.** No presence for that session. After making it a project and adding it, the session appears within about a minute.
- **The hub goes down.** Open sessions stay up. Their tools fail after about 30 seconds naming the hub's address. After `session_stale_seconds` they drop out of `list`. When the hub is back they return by themselves and push resumes.
- **The hub's config is broken.** Ticks and tools fail with the file and key named. Fix the file; the next tick works. A config whose `session_stale_seconds` is below `session_heartbeat_seconds` plus twice `notify_poll_seconds` is one such case, with the three keys named.
- **A session is closed.** Its line leaves `list` at once. Rarely a tick that was in flight writes the row again after the exit call; then the line stays for `session_stale_seconds` and goes by itself.
- **A session is killed, or its laptop sleeps.** It drops out of `list` after `session_stale_seconds`. A laptop that wakes shows its session again at the next tick, as up since then.
- **An `answer` from a session is refused for the deadline.** The message names `resume_wait_seconds`, the hub's `config.yaml` and the largest value that passes. Lower it there, or answer from a shell, which has no deadline.
- **A run was answered from another machine.** It resumes on its own machine within a few seconds if any session is open there, with nothing typed. With none open, it waits for the next `amoeba` call on that machine; `amoeba list` there starts it. If that machine is gone for good, `amoeba hub rm-machine <machine>` ends the wait (262 D13).
- **The hub is upgraded to a new door version.** `amoeba list` has a **Behind the hub** section naming each machine and open session that is behind, with the upgrade command. Upgrade each machine, then restart the sessions listed. A session started on a machine that is still behind is listed too, and its tools say to upgrade. A machine that was upgraded but still has an old session open stops being listed after its next `amoeba` command; the old session stays listed until it is restarted. `amoeba hub machines` on the hub shows the same per machine.
- **A machine was upgraded before the hub.** Its calls are refused, and `list` from another machine shows it and its sessions as `ahead of the hub` and says to upgrade the hub. After the hub is upgraded they work again with no restart.
- **A machine is removed while a session is open there.** The session's tools say its token is not known and give the invite and join commands. After those, the session's tools work again with no restart. Removing the machine removed its checkouts, so `amoeba add` is run in each repo there, and the session is listed again from its next tick.
- **A machine joins while a session is open.** The session uses the hub from its next tick. After `amoeba leave`, the session's ticks do what any `amoeba` call on that machine does. On a machine that had no local store that makes an empty one, so a later `amoeba join` there is refused and names `--set-aside-local`; with that flag it joins (D1).
- **A client that listed resources before its repo was added, or while the hub was down.** It was offered `amoeba://inbox` anyway. A read or subscribe is refused until a tick has a member, and works from then on with no reconnect.
- **Runs on another machine look old.** The heading says when they were reported. Run `amoeba list` on that machine to report again.
- **Turning push off.** As in 241: drop the launch flag. The session still ticks, shows in `list`, and starts its machine's work.
- **Undo.** There is no setting to turn off. For the upgrade itself, `uv run python scripts/update_live.py restore` puts back the store and config from before the update and reinstalls the release that was installed then. Everything recorded since the update is lost, so it is for an update that went wrong, soon after it.

Dead ends found: none.
