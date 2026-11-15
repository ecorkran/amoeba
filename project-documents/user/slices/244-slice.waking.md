---
docType: slice-design
slice: waking
project: amoeba
parent: user/architecture/240-slices.agent-messaging.md
dependencies:
- 240
- 241
- 242
- 243
interfaces: []
dateCreated: 20261115
dateUpdated: 20261115
status: not_started
turns: 25
promptTokens: 1949023
cachedTokens: 1799448
cacheWriteTokens: 149537
completionTokens: 44953
durationSeconds: 360.9
costUsd: 1.228029
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 1.2280288999999998
    completionTokens: 44953
---

# Slice Design: Waking

## Overview

A member can carry a `wake_command`, which the PM sets from the CLI. When `send` delivers a request to a member that has one, has no live session (241's live-member query) and no running wake, and is under its daily limit, Amoeba starts that command detached, under a small `amoeba wake-run` wrapper, in the member's checkout. The wrapper holds the wake's row while the command runs, stops the command at `wake_timeout_seconds`, and records how it ended. Migration 9 adds the `wakes` table and the `members.wake_command` column. A wake's failure changes no message: the request stays `open` for the next agent until its TTL. `list` and `status` show what is running, what stopped waking and why, and any failure. This is the last slice of the agent-messaging initiative.

## Value

User value. A request to a repo nobody has open gets an agent started for it without anyone opening the repo, whatever agent the PM configured. Whether that agent finishes the work is up to it; D2 lists what is left and how each case ends. Bounded by a daily limit per member, a timeout per wake, and the command's own required cap, so an unattended start cannot run away. Architecturally it adds the only place Amoeba starts an agent with nobody present, with every limit and every state having an exit.

## Technical Scope

**Included**
- `members.wake_command` (nullable), set from the CLI's `add` and cleared with `--no-wake-command` (D1).
- The wake decision and claim after `send`'s request is written (D2), the `wakes` table (D3), the checkout directory (D4), the start (D5).
- `amoeba wake-run`, the wrapper (D6), and the limits (D7).
- Two required config keys, `wake_timeout_seconds` and `max_wakes_per_day` (D8).
- `list` and `status` show waking per member (D9). Cleanup of rows and logs (D10). The bound on `send` (D11).
- Docs: the contract a wake command must meet, `cli-contract.md`, `config-contract.md`, `store-contract.md`, `mcp-server.md`.
- A live test with a fixture agent through the real `cf` and CLI (D12).
- Live store backed up, migrated to 9, config keys added, read back.

**Excluded**
- Choosing what the woken agent does. The command is the PM's, and Amoeba never decides what work to do (architecture).
- Setting a wake command through MCP. It is a CLI setting (D1).
- Waking for a note (243: a note never reaches the wake path), or from anything but `send`. A request is woken for at `send` (or at a same-id retry of it, D2), and never again by Amoeba. What follows from that is in D2 ("What a wake does not do"), with each case's exit.
- A command to stop a wake by hand. The wrapper's timeout is the exit; after a wrapper is killed, the command's own cap or the PM's stop of the pid `list` shows (D6).
- Detecting whether a woken agent read its mail. Amoeba records how the command ended, not what it did.

## Dependencies

### Prerequisites
- 240, 241, 242 and 243 built and integrated: `send` with its request branch, `sweep` and `sweep_messages`, `MemberStatus`, `sessions` and 241's live-member query, 243's separate note path (the note test in the success criteria needs it), and the live store at schema 8 (242's migration 8 follows 241's migration 7; 243 has none).
- `Deps.spawn` and `start_child` already exist (223).

### Interfaces Required
- From 240: `send` and its request branch (D1 of 243 keeps the note path separate), `resolve_recipient` in `operations/message_member.py`, `SendResult`, `sweep` and `sweep_messages`, `MemberStatus`, `sql.ACTIVE_MEMBER`, the worst-case timing test.
- From 241: the live-member query (`live_member_ids(transaction, now, stale_seconds)` and the config key `session_stale_seconds`), used as 241 defines "live": a fresh session that is push-confirmed (241 D6), meaning its agent answered a channel event. A session without push never confirms, so its repo is woken.
- From 242: `Deps.amoeba_script` (the moved `resolve_amoeba_script`), used to find the script for the wrapper, and `START_BOUND_SECONDS` in the timing test.
- From 220 to 229: `add`'s CLI request, resolve and render path (`set_up_models.MemberRequest`, `set_up_resolve`, `registration_arguments`, `list_registry`), `Deps.spawn`/`start_child`, `terminate_group`, `StateLayout.logs_dir`, `upstream.context_forge.project_of` (its `projectPath`), `prune`.

## Architecture

### Component Structure

```
send (request branch, after its write commits) ──► operations/wake.py  wake_after_send
        │                                              │ claim (one write transaction)      store/wakes.py
        │                                              │ spawn detached                    Deps.spawn
        │                                              ▼
        │                              amoeba wake-run <wake_id>  ──►  operations/wake_run.py
        │                                              │ runs wake_command, enforces deadline, records the end
status/list ──► operations/wake_status.py (read) ◄──── wakes rows
sweep ──► deletes wakes rows past prune_after_days       prune ──► logs/wake/ files by age (existing rule)
```

- `store/wakes.py` and `store/sql_wakes.py`: `claim_wake`, `finish_wake` (compare-and-set on `ended_at IS NULL`), `wake_summary` (the read `list` uses), `prune_wakes`, and one `LIVE_WAKE` predicate constant. Rows are a frozen dataclass `Wake` in `store/models.py`. The store imports nothing from `operations`.
- `operations/wake.py`: `wake_after_send(open_store, config, deps, recipient, wake_command)`. It returns a problem line or nothing.
- `operations/wake_run.py`: the wrapper's logic, `run_wake(store, deps, wake_id)`. It is not an operation: no `OperationName`, no MCP tool, no result model. `cli/` registers `wake-run` as a CLI-only subcommand with a branch in `main` before the operation lookup, as `handle-pause` has its own.
- `operations/wake_status.py`: builds `WakeStatus` for `MemberStatus` from one read.
- `operations/message_member.py` (240): `resolve_recipient` returns a `Recipient(member_id, project_path)`.
- `operations/set_up_*`, `cli/registration_arguments.py`, `cli/render/*`: the `wake_command` setting.
- `store/vocabulary.py`: `WakeOutcome`.

### Data Flow

**Setting.** `amoeba add --wake-command "<command>"` validates the text (D1) and stores it on the member row.

**Waking.** `send` resolves the sender and the recipient before any store lock, and the recipient lookup returns the checkout path (D4). `send`'s write transaction commits the request and its delivery as in 240. Then, when the request is `open` (outcome `sent`, or `unchanged` with the stored request still `open`) and the recipient has a wake command (D2), `wake_after_send` checks and runs one write transaction, `claim_wake`. If it claims, it inserts a `wakes` row and returns the row. `wake_after_send` then starts `amoeba wake-run <wake_id>` detached in the checkout, logs under `logs/wake/`, and returns without waiting. A failure to start ends the row as `start_failed`, and no wrapper is spawned for a row that was inserted already ended (D4).

**The wake.** `wake-run` reads its row, starts `wake_command` in a new session in the checkout with an explicit environment, waits until the row's `deadline_at`, stops the command if it is still running, and records the outcome in one short write. The woken agent reads its mail the way any agent does: `inbox`, at the session start moment its rules block names.

**Reading.** `status` and `list` read the member's recent rows and the config limits and show the state (D9). Nothing about a wake is derived from a process, only from rows and the clock.

### State Management

- `members.wake_command` (config of a member, edited through `add`) and the `wakes` table (state). The wrapper keeps nothing in memory that the row does not hold.
- A wake is **live** while its row is not ended and `deadline_at` is later than now (`LIVE_WAKE`, the one predicate, used by the claim and the read). A row whose wrapper died stays unended, reads as gone once the deadline passes, shows in `list` as overdue, and leaves by retention (D10), with nobody editing anything.
- The day's count is read, not stored: every row of the member started in the last 24 hours, whatever its outcome.
- No state outlives the retention window (D10).

## Technical Decisions

### D1 — `wake_command`: a CLI setting, executed without a shell
Status: decided

- **Storage.** `members.wake_command TEXT`, nullable, added by migration 9 (`ALTER TABLE ... ADD COLUMN`, the 229 pattern). Existing members get null: no wake.
- **Setting: the PM, from the CLI.** The architecture says waking starts "a command the PM configured", and the plan says the setting is set from the CLI (229). This design keeps both. CLI: `amoeba add --wake-command COMMAND` and `--no-wake-command` (mutually exclusive), with the rest of `add` unchanged (`--project` and `--file` work as for any setting, so the PM can set it from one repo). `MemberRequest.wake_command: NonBlankText | None`, with omitted meaning leave it and null meaning clear it, told apart by `model_fields_set` as `concept` is. The MCP `add` tool does not take the field: its input schema omits `wake_command`, so the only code that fills it is `cli/registration_arguments.py` and the bulk document read. An agent with a shell can still run `amoeba add`; that is the architecture's trust assumption (one user's machine, self-asserted identity), and the docs say the wake command is the PM's to set. `list members` shows every wake command, so the PM sees what is set.
- **Secrets.** The command is stored and printed in plain text by `list members`, `list -j` and `status`, so it must carry no secret. The contract (D12) and `add --help` say so, and say that the command runs unattended with the user's privileges. A secret belongs in a script that loads it itself (the repo's `.env` or the user's profile).
- **Environment.** The wrapper's own environment is the sender's, since `send` started it. The command must not receive it: a sender's API keys, tokens and budget settings would let a woken agent spend under the sender's credentials, outside the recipient's limits. The wrapper therefore builds the command's environment explicitly (D6): only the names in `WAKE_ENV_NAMES` (`PATH`, `HOME`, `USER`, `LOGNAME`, `SHELL`, `LANG`, `LC_ALL`, `TMPDIR`, `AMOEBA_HOME`, a constant), copied from its own when set, and nothing else. `AMOEBA_HOME` stays so the woken agent's `amoeba` calls reach the same store. The wake runs with the user's login and the recipient repo's own configuration, never the sender's variables (a departure the architecture records).
- **Validation at `add`.** The text must split with `shlex.split` into at least one token and must not contain a NUL or a newline, else `add` rejects the document with the field named. The executable is not looked up then: it may be installed later, and a missing one is a recorded `start_failed` (D6).
- **Execution.** `shlex.split` into an argv, run without a shell, in the checkout, with no stdin. A pipe, a redirect or an environment assignment needs a script, which is the documented way (D12). Nothing about the request reaches the command: no argument, no environment variable, no stdin. The woken agent learns what to do from its own rules, through `inbox`, so message text stays under the quoted-data notice (240 D11).
- Rejected: running through a shell (quoting bugs become command injection); a list of arguments instead of a string (harder to write and to show); a separate `wake` operation (every member setting is set through `add`, 229); exposing it on the MCP `add` tool (it would let any agent configure unattended starts as a tool call, against the architecture's "the PM configured").

### D2 — When a wake starts, and where the decision runs
Status: decided

The hook is in `send`'s request branch, after the transaction that wrote the request and its delivery has committed, and only while the request is `open`: outcome `sent`, or `unchanged` with the stored request still `open`. A same-id retry therefore runs the same checks again, so a wake step that failed the first time (a start failure, a held store) is retried by the sender's own retry. It cannot double-start, because the claim refuses while a wake is running, and the limit (which counts every row, D7) bounds the number of wrappers a retry loop can start. An `unchanged` for an `accepted` request does not wake: an agent is already on it. A note never reaches the hook (243). The request is durable before any wake work, so nothing below can lose or change it.

**Most sends do no wake work.** `send`'s own write transaction already reads the recipient's member row (240 D1's recipient check), and now reads `wake_command` with it. A recipient with none ends the step there: no second store open, no lock. For one with a command, `wake_after_send` opens the store once and checks 2 to 4 below in a read transaction. Only if they pass does it open the write transaction `claim_wake`, which repeats the checks and is authoritative.

`claim_wake` is one `BEGIN IMMEDIATE` transaction that checks, in this order, and stops at the first check that fails (it returns the claimed row, or nothing; `list` reads the session and the limit itself, so no reason is returned):
1. The recipient is an active member (`sql.ACTIVE_MEMBER`) with a non-null `wake_command`.
2. Its id is not among the live members 241's query returns (`live_member_ids(transaction, now, session_stale_seconds)`). A woken agent whose own `amoeba-mcp` registers a session makes later requests wait for it, which is what is wanted.
3. No row of the member satisfies `LIVE_WAKE`.
4. Fewer than `max_wakes_per_day` counted rows in the last 24 hours (D7).
5. Otherwise it inserts the row (D3) and returns it. If the checkout path is unknown, it inserts the row already ended as `start_failed` and returns nothing to start (D4).

Two sends at once are serialized by the lock: the second sees the first's live row and does not start a second wake. Its request is in the inbox the woken agent reads, and the rules block's "before ending the session" moment catches one that arrives after the agent's first read.

**What a wake does not do.** Amoeba wakes at `send` and never again, so these cases are left to their exits, none of which needs anyone to edit a file:
- A request that arrives after the woken agent's last `inbox` read, or while the limit is reached or a live session exists, waits for the next agent, or for the sender's same-id retry once the cause is gone, or until its TTL, when it expires and the sender is told. The plan states this for the limit; the other two are the same rule. An idle push-confirmed session gets the request by push.
- An agent that accepts and then times out, exits or dies leaves the request `accepted`, which has no timeout (architecture). Its exits are `done` or `decline` from the next agent in that repo, and `cancel` from any session naming the id. `list` shows its age.
- A start failure or a held store leaves the request `open`, and the sender's same-id retry re-runs the wake step once the cause is fixed.

**The wake step's expected failures never fail `send`.** Its fallible calls are store reads and writes (no `cf` call). A `StoreError` is caught by type in `wake_after_send`, logged with `logger.exception`, and returned as one line in `SendResult.wake_problem` (a new field, null when nothing went wrong; the text renderer prints it), because the request is already written and exit 3 would report a failure for work that happened, as `sweep_problem` does. `LaunchError` is a value `spawn` returns, and `AmoebaScriptMissing` is caught by type (D5). Any other exception is a bug and propagates, so `send` exits 3 for a request that was written; the sender's retry then answers `unchanged` and runs the wake step again.

### D3 — The `wakes` table: one row per wake
Status: decided

`009_wakes.sql`: `ALTER TABLE members ADD COLUMN wake_command TEXT;` and `CREATE TABLE wakes`:

`wake_id` (text primary key, `uuid4().hex`, so a restored store never collides with an existing log file), `member_id` (references `members`), `directory` (the checkout; null only for a `start_failed` row with no path), `command` (the member's `wake_command` as claimed, so a later edit changes nothing running), `started_at`, `deadline_at` (`started_at + wake_timeout_seconds`, fixed at the claim, as 240's `expires_at` is fixed at `send`), `log_stem` (null when nothing was started), `command_pid` (the command's pid, which is also its process group id, written by the wrapper right after the command starts, null until then; shown by `list` for an overdue row, D9, and never signalled by Amoeba), `ended_at`, `outcome` (`exited`, `timed_out`, `start_failed`, `wrapper_failed`), `exit_code`, `detail` (never argv text, D6). Table `CHECK`s: `ended_at` and `outcome` are both null or both set; `exit_code` is set only for `exited`. Indexes on `(member_id, started_at)` and `(started_at)`. The outcome list is pinned to `WakeOutcome` by the existing pinning test.

- **Departures from the plan and architecture** (listed in the departures section): one row per wake, kept after it ends, with no wrapper pid and no stored count.
- **Why per wake.** `list` must show how the last wake ended and why waking stopped, and the daily limit needs the starts of the last 24 hours. Both are queries over these rows. A single row per member would need a second place for the history, a counter that rolls over, and a reset rule.
- **Why no wrapper pid.** After a SIGKILL, a pid proves nothing once it is reused (241 rejected it for sessions for that reason). Liveness is decided by the deadline.
- Rejected: a counter column on the member (a reset rule and two sources of truth).

### D4 — Which directory
Status: decided

Members are stored by Context Forge project id only, with no path (220). The checkout is Context Forge's `projectPath`, which `send`'s recipient lookup (`project_of`, one `cf get`) already returns, so waking adds no `cf` call. `resolve_recipient` returns `Recipient(member_id, project_path)`, with `project_path` null when Context Forge did not know the reference (240's rule reads such a reference as an id). A null path is a `start_failed` row inserted already ended, with the reason, and no wrapper is spawned for it; a path the start cannot use is a `start_failed` from D5 or D6. Either is shown in `list` (D9), and the request stays `open`. The fix for a null path is in Context Forge (register the project's path); `amoeba add` cannot supply one. The wake runs in the registered checkout, which is where "the repo" is for Context Forge. A person working in that checkout without `amoeba-mcp` shows no session, so waking a repo someone uses that way is the PM's configuration choice (Risk).

### D5 — Starting the wrapper
Status: decided

`wake_after_send` calls `deps.amoeba_script()` and `deps.spawn([script, "wake-run", wake_id], checkout, LaunchLogs(stdout, stderr))`, with the logs `<logs_dir>/wake/<wake_id>.stdout.log` and `.stderr.log` (`log_stem` is the path without the suffix; `start_child` creates the directory and makes the logs exclusively, a new session, no stdin). Spawn returns at once. Failures, each recorded as `finish_wake(..., start_failed, detail)` and logged with `logger.error`:
- `LaunchError` (a value `spawn` returns: the checkout is missing, a log cannot be made): its text.
- `AmoebaScriptMissing`, caught by that type, with a comment that raising would report a failure for a request that is already written: its text, which names the install fix.
If recording the failure itself hits a `StoreError`, the row stays unended, stops counting as running at its deadline, shows as overdue in `list` with no pid, and leaves by retention (D10); the problem goes in `wake_problem`. A `start_failed` row counts toward the limit like any row (D7).

### D6 — `amoeba wake-run`
Status: decided

An internal command, `amoeba wake-run <wake_id>`, named in `cli-contract.md` as started by Amoeba and not meant for people. It opens the store through `open_state_store(layout)` and loads no config: the deadline is in its row, and its branch in `main` comes before any config load, so the live-store window with missing keys (Special Considerations) does not stop a wrapper that is already starting.

**Before the command starts.** Each failure here is listed with what is recorded:
- The store cannot be opened or the row cannot be read (`StoreError`), or the row is missing or already ended: nothing can be recorded. One stderr line and exit 3, and no command runs. A row that exists stays unended, stops counting as running at its deadline, and leaves by retention.
- The row's command text cannot be split, or `Popen` raises `OSError` (not found, not executable, no such directory): `finish_wake(start_failed, <detail>)` and exit 1. If that write fails too, the row is as in the first case.

**What `detail` holds.** Never argv text, because a command may have been written with a secret in it (D1) and `detail` is printed. For an `OSError` it is the exception class and its `strerror` (not the filename); for anything else, the class name. The traceback goes to the wake's stderr log.

**Running.**
1. `subprocess.Popen(shlex.split(command), cwd=directory, env={name: value for each name in WAKE_ENV_NAMES set in the wrapper's own environment}, start_new_session=True, stdin=DEVNULL)`, stdout and stderr inherited (they are the wrapper's own logs). The command's pid is its process group id. A short write then sets `command_pid`. A held store there is logged as a warning and the wait goes on; the row then shows no pid.
2. `child.wait(timeout=max(0, deadline_at - now))`. On timeout the outcome is `timed_out`, otherwise `exited` with the exit code. Either way the wrapper then calls `terminate_group(child)` (SIGTERM to the group, a 5-second grace, then SIGKILL; the existing helper): after a timeout it stops the command, and after a normal exit it sends SIGTERM to any members the command left behind, which is a no-op when none remain.
3. `finish_wake`, one short write bounded by `BUSY_TIMEOUT_SECONDS`. If it cannot write, it logs the error and exits 3: the row is as in the first case.

**Any other exception** after the command started is caught at the process boundary (the one place this slice catches `Exception`, with a comment saying so): it is logged with `logger.exception`, the command's group is stopped with `terminate_group`, and `finish_wake(wrapper_failed, <class name>)` is tried once. Before the command started it is recorded as `start_failed`.

Exit codes: 0 when a command ran and was recorded (its own exit code is data, not the wrapper's), 1 for `start_failed`, 3 for operational failures.

**A wrapper that is killed.** The wrapper only dies without recording if something sends it SIGKILL (a reboot takes the command with it). That is rare, so it gets an explicit fallback rather than a mechanism: the command runs on in its own session, and its exits are, in order, the command's own cost or time cap, which the wake-command contract requires (D12), and the PM's stop of the pid `list` shows. Its row stays unended; past `deadline_at` it no longer counts as running (so the member can be woken again), `list` shows it as overdue with the command's pid and log path (D9), and it leaves by retention (D10). Amoeba never signals a pid it did not just start, so it can never kill an unrelated process that reused one.

Rejected: a reaper that kills the orphan at the next `send` (it needs a recorded start time, a `ps` identity check, a process-group signal from a request path and its own tests, for a case that needs a SIGKILL of the wrapper; the required cap already bounds the command).

### D7 — The daily limit and the timeout
Status: decided

- **Limit.** `max_wakes_per_day`: at most that many wakes started for a member in any rolling 24 hours (`WAKE_WINDOW`, a constant). Counted: every row of the member with `started_at` in the window, ended or not, whatever its outcome, so the limit bounds wrapper spawns as well as commands. Hit: no claim, no row, no wake, and the request waits for the next agent up to its TTL, when it expires and the sender is told (240). `list` says waking is stopped and how many of how many were used. The wake that frees a slot is the next `send` after the oldest counted row is 24 hours old, so the limit has an exit by the clock alone.
- **Timeout.** `wake_timeout_seconds`: the wrapper stops the command at the deadline and the row records `timed_out`. If the wrapper was killed, the command's own cap is the bound (D6).
- **Failed starts.** Counted like any row. A broken command therefore uses its day's wakes and `list` shows waking stopped with the last failure; fixing the command takes effect once the limit allows, or sooner if the PM raises `max_wakes_per_day` in the config. Each row is bounded by retention (D10).
- A day never resets by a calendar edge: there is no midnight burst.

### D8 — Config keys
Status: decided

`wake_timeout_seconds` (a number greater than 0) and `max_wakes_per_day` (an integer of at least 1), required, with no default in code, as 240 D12 and 241 D7. Waking is turned off per member by clearing its `wake_command`, not by a zero. The suggested values appear once, in the config contract's example, and a test loads that example. The live config gets both keys in the live-store step.

### D9 — `list` and `status`
Status: decided

`MemberStatus` gains `wake`, present only for a member with a `wake_command`: `command`, `running` (the member's unended row, live or past its deadline: `started_at`, `deadline_at`, `command_pid`, `log_stem`; or null), `stopped` (when the limit is hit: `used`, `limit`; else null) and `last_problem` (the member's newest ended row when its outcome is `start_failed`, `timed_out`, `wrapper_failed` or `exited` with a non-zero code: `outcome`, `exit_code`, `detail`, `ended_at`, `log_stem`; else null). The text renderer adds a **Waking** section: the command, `running since <age>, stops <time>` (past its deadline: `overdue since <time>: its wrapper is gone; the command's own cap ends it, or check and stop pid <pid>, log <path>`), `waking stopped: <used> of <limit> wakes used in the last 24 h`, and `last wake <outcome> <age> ago: <detail>, log <path>`. Waking does not count as "waiting on you", so `Nothing needs you.` is unchanged. `list -j` still equals the `status` document. `list members` shows the command.

### D10 — Cleanup
Status: decided

- **Rows.** 240's `sweep` gains a step that deletes `wakes` rows with `started_at` older than `prune_after_days` (the existing parameter, so no signature change), whatever their state: an unended row from a killed wrapper is old enough to go. `sweep_messages`'s "is something due" read counts an aged row as due, so a quiet store is still not write-locked by a poll. The table holds at most the member's rows of the retention window.
- **Logs.** `logs/wake/` is not a protected directory, so `prune`'s existing rule for unlisted logs (remove by age, then remove emptied directories) removes them. A test creates old and new files there and checks that.
- **Removal.** `rm` of a member leaves its rows to retention; a running wake finishes on its own. `add --no-wake-command` stops later wakes.

### D11 — The bound on `send`
Status: decided

The wake step makes no `cf` call, no `ps` call, and never waits for the wrapper or the command. It opens the store once, which 240 counts as two waits (the legacy-move lock and the open, `BUSY_TIMEOUT_SECONDS` each), then up to three transactions (the read, the claim, a failure write), `BUSY_TIMEOUT_SECONDS` each. So `WAKE_BOUND_SECONDS = 5 × BUSY_TIMEOUT_SECONDS` = 25 s. 240's worst-case test for `send` (105 s) already adds 242's `START_BOUND_SECONDS` (30 s); it now adds `WAKE_BOUND_SECONDS` too, 160 s, and still fails if the sum reaches `MCP_CALL_DEADLINE_SECONDS` (180 s). A recipient with no wake command adds nothing.

### D12 — Docs and the live test
Status: decided

- **A wake command's contract** (a section in `cli-contract.md`): the PM sets it with `amoeba add --wake-command`; it runs in the member's checkout with no arguments from Amoeba and no stdin; it must check `inbox` at its start, handle each request by the repo's own rules (accept before working; decline with a reason when the rules do not settle it; done with the result), check `inbox` again before it ends, and exit; it **must** carry its own cost or time cap, since that is the only bound on it if its wrapper is killed; it runs with only the environment variables in `WAKE_ENV_NAMES`, so a script loads its own secrets; it is stopped at `wake_timeout_seconds` by its wrapper; its stdout and stderr go to the wake's log. The docs name the log path and the `list` lines (including `overdue`), and say the command is shown in plain text, so a secret goes in a script that loads it itself (D1). `mcp-server.md` says the `add` tool does not set it. The examples use a script, since pipes and assignments need one. The implementing agent runs the agent CLIs it names in the docs and copies their real flags, never from memory.
- **The fixture agent.** `tests/live/waking/fixture_agent.py` stands in for a real agent: it runs `amoeba inbox -j`, accepts and completes each open request through `amoeba reply`, rereads `inbox` before it exits, takes a `--max-seconds` cap, and can be told by environment variable to wait on a gate file, to sleep past the timeout, and to write its parent pid to a file (the wrapper's pid, for the SIGKILL test). Spend: none. A real model agent is the PM's configuration, and 241's live test already proves a real Claude Code session acts on `inbox`.

### Departures from the parent documents
The docs step amends the architecture and plan entry so none stays a difference.
- **`wakes` is one row per wake and stays after the wake ends.** The plan has the wrapper hold a row and clear it on exit, and the architecture lists a wrapper pid and a day's count. Here the wrapper records how the wake ended, the count is read from the last 24 hours of rows, the wrapper's pid is not recorded (the command's pid is, for display), and rows leave by retention (D3, D10). "A row left by a killed wrapper counts as gone after `wake_timeout_seconds`" is unchanged, through `deadline_at`.
- **"Per day" is a rolling 24 hours,** not a calendar day (D7).
- **The directory is Context Forge's `projectPath`,** since Amoeba keeps no path. `resolve_recipient` returns it and `SendResult` gains `wake_problem` (D2, D4). These are edits to 240's modules, listed in this slice's tasks.
- **`wake-run` is a CLI-only internal command,** not an operation with two doors (D6).
- **`add` can clear the setting** with `--no-wake-command` and null (D1).
- **The wake's environment is explicit** (D1). The architecture is amended to say the wake command runs with only the variables in `WAKE_ENV_NAMES`, never the sender's, so credentials do not cross repos.
- **After a wrapper is killed, Amoeba does not stop the command.** The architecture says the wrapper stops a command past its timeout and one wake runs at a time. When the wrapper is SIGKILLed, the command's own cap (required by the contract) or the PM's stop ends it, and a new wake can start beside it once the old row's deadline passes (D6). The architecture's Waking section is amended to say each wake command must carry its own cap and is the bound in that case.
- **The limit counts every row,** failed starts included (D7), where the architecture speaks only of wakes started.
- **A wake starts at `send`, or at a same-id retry of it while the request is still `open`,** and never again. The plan's entry does not say what happens to a request a wake leaves behind; D2 lists each case and its exit.
- **Dependencies.** The plan's entry 5 says "Dependencies: 240, 241". The design also needs 242 (`Deps.amoeba_script`, schema 8) and 243 (the note path its test relies on), so the docs step amends the entry to 240, 241, 242, 243. No later slice depends on 244, so `interfaces` is empty.
- The sweep gains a fourth step with no new parameter (D10). The architecture's "Store and config" paragraph is amended for both tables' columns and the two keys.

## Implementation Details

### Database / Storage Schema

As D3. `ADD COLUMN` and `CREATE TABLE` only, so existing rows are untouched and `foreign_key_check` finds nothing. `EXPECTED_SCHEMA_VERSION` becomes 9. Downgrade is refused by the existing newer-schema guard.

### API Contracts

| Surface | Detail |
|---|---|
| `add` (CLI only) | `--wake-command COMMAND`, `--no-wake-command`; bulk JSON `wake_command` (omitted leaves, null clears). The MCP `add` tool has no such field |
| `amoeba wake-run WAKE_ID` | Internal. Exits 0, 1 or 3 (D6) |
| `send` result | `wake_problem` (string or null) |
| `list`/`status` JSON | `wake` per member that has a command (D9) |
| `list members` | each member's `wake_command` |
| Config | `wake_timeout_seconds`, `max_wakes_per_day` |

## Integration Points

### Provides to Other Slices
- Nothing: this is the last slice of the initiative. It leaves `wake_command`, `amoeba wake-run` and the `wakes` table, and the live-test fixture agent.

### Consumes from Other Slices
- **240:** `send`'s request branch, `resolve_recipient`, `SendResult`, the sweep and its due check, the timing test. If a 240 change moves the request branch, the hook moves with it: it runs after the request's transaction.
- **241:** the live-member query. Whatever 241 counts as live stops a wake; a member 241 does not count as live (no `amoeba-mcp`, or a stale session) may be woken (stated in 241's departures).
- **243:** a note never wakes, because the note path never reaches the hook; a test sends a note to a member with a wake command and checks nothing starts.
- **242:** `Deps.amoeba_script` and `START_BOUND_SECONDS`, and schema 8, which migration 9 follows.

## Success Criteria

### Functional Requirements
- A request to a fixture member with a wake command, no live session and no running wake starts the command once, in the member's checkout. A second request while it runs starts nothing and is in the inbox the fixture agent rereads before exiting; both end `done`.
- A member that 241's query counts as live (a fresh `sessions` row with `push_confirmed_at` set), with no wake command, or sent a note, is not woken. A member whose only session row is unconfirmed is woken. A same-id retry answering `unchanged` for an `open` request wakes when no wake is running and the limit allows (after a start failure), and starts nothing while one runs; for an `accepted` request it starts nothing.
- A command running past `wake_timeout_seconds` is stopped with its whole process group and its row ends `timed_out`. After the command exits normally, any member it left in its group gets SIGTERM.
- A wrapper killed with SIGKILL leaves an unended row that stops reading as running at `deadline_at`. Past it, `list` shows the row as overdue with the command's pid and log path, and the next `send` to that member (limit allowing) starts a new wake. Amoeba sends no signal to the old command (the test checks it is still running, then kills it itself). The row is deleted by the sweep once past retention.
- A wrapper that cannot open the store or read its row runs no command, exits 3 and records nothing; its row stops counting as running at its deadline. A wrapper whose command cannot start, or that hits an unexpected error, records `start_failed` or `wrapper_failed` and stops any started command's group. No `detail` holds argv text: a test with a secret-like marker in the executable name finds it in no row, `list` line or `status` document except the command itself.
- At `max_wakes_per_day` no wake starts, no row is written, the request stays `open` and in `inbox`, `list` says waking is stopped with the counts, and with a clock past the TTL the request expires and the sender hears (240). Once the oldest counted row is 24 hours old, the next `send` wakes.
- A command that cannot start (not found, missing checkout, no path from Context Forge, missing `amoeba` script) ends its row `start_failed` with the reason, shows in `list`, leaves the request `open`, and counts toward the limit: with `max_wakes_per_day` failing sends to a member whose command is missing, the next one spawns no wrapper.
- A send to a member with no wake command opens the store no second time (a test counts opens), and a member with a command whose pre-check fails (live session, running wake, limit) takes no write lock.
- A command that exits non-zero ends `exited` with the code and shows as the last problem. A `StoreError` in the wake step is returned in `wake_problem`, the request stays written, and `send` still exits 0 or 1 as 240 says.
- The command receives no message text: a test sends a request whose subject and body hold marker strings and checks the command's argv, environment and stdin for them.
- The command's environment holds exactly the names in `WAKE_ENV_NAMES` that the wrapper has: a test starts the wrapper with a marker variable (`SENDER_SECRET_MARKER`) and `AMOEBA_HOME` set and checks that the command sees `AMOEBA_HOME` and not the marker.
- The contract's example command carries a cap (the fixture agent's `--max-seconds`), and a docs test fails when the example in `cli-contract.md` does not.
- `amoeba add --wake-command` and `--no-wake-command` set and clear it (directly, with `--project`, and through `--file`); a blank or unsplittable text is rejected naming the field. The MCP `add` tool's input schema has no `wake_command`, and a call passing it is rejected as an unknown field.

### Technical Requirements
- Every `wakes` row has a cleanup: rows past `prune_after_days` are deleted by the sweep, including an unended one, with a test; wake logs are pruned by `prune`, with a test over `logs/wake/`. The sweep's due check counts an aged row.
- Both keys missing fail with `ConfigError` naming the key; the example in `config-contract.md` loads. `CHECK` lists are pinned; `tests/test_contract_docs.py` passes with the column, table, fields, flags and keys documented; `tests/test_import_boundaries.py`, `tests/test_store_opened_only_by_state_move.py` and `tests/test_read_side_defined_once.py` pass.
- 240's worst-case test includes `WAKE_BOUND_SECONDS` (25 s, D11) and stays below `MCP_CALL_DEADLINE_SECONDS`.
- `ruff format`, `ruff check`, `pyright` and the whole suite pass.

### Integration Requirements
- 240's, 241's, 242's and 243's behavior and tests are unchanged except for the named edits: `resolve_recipient`'s return type, `send`'s read of `wake_command` in its existing transaction, `SendResult.wake_problem`, and the sweep step.
- The live store is backed up, migrated to 9, read back, with the restore path in the slice notes.

### Verification Walkthrough

This is the Phase 4 draft, refined when Phase 6 is complete. `--wake-command`, `wake-run` and `tests/live/waking` do not exist until the slice is built. Every step runs unattended, with a throwaway home and the fixture agent, and spends nothing.

1. `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest`. Expected: all clean and passing.
2. Set up two scratch repos and a throwaway home with the config example plus short values for the two new keys (`wake_timeout_seconds: 5`, `max_wakes_per_day: 2`):
   ```
   export AMOEBA_HOME=$(mktemp -d)
   for n in sq-s cf-s; do mkdir $n && git -C $n init -q -b main && (cd $n && git commit -q --allow-empty -m seed && cf init --lite --name $n && amoeba add --program toolchain); done
   (cd cf-s && amoeba add --wake-command "python3 <repo>/tests/live/waking/fixture_agent.py --max-seconds 60")
   ```
   Expected: `amoeba list members` shows the command under `cf-s`.
3. In `sq-s`: `amoeba send --to cf-s --id w-1 --subject "Need X" --body "Please add X"`. Expected: `sent w-1 -> cf-s`. `amoeba list` shows `cf-s` with a Waking section, `running since ...`.
4. Wait for the fixture agent to finish, then `amoeba inbox` in `sq-s`. Expected: `w-1` is `done`. `amoeba list`: `last wake` absent (it exited 0). The log is at the path the row names: `ls $AMOEBA_HOME/logs/wake`.
5. Limit: send `w-2` and `w-3` (each after the previous wake ends). Expected: `w-2` wakes; `w-3` starts nothing, stays `open`, and `amoeba list` shows `waking stopped: 2 of 2 wakes used in the last 24 h`.
6. Failures: `amoeba add --project cf-s --wake-command "no-such-agent"` and send `w-4` after the window clears (or with the limit raised in the throwaway config): `amoeba list` shows `last wake start_failed` with the reason and `w-4` is `open`. With the fixture agent set to sleep, `amoeba list` shows it `timed_out` after 5 seconds.
7. Undo: `amoeba add --project cf-s --no-wake-command`; `amoeba list members` shows no command; a new `send` starts nothing.
8. `uv run pytest tests/live/waking`. Expected: pass, covering steps 3 to 7 plus the live-session, SIGKILL and note cases.
9. Live store: see Special Considerations.

## Risk Assessment

### Technical Risks
- Amoeba starts an agent with nobody present, in the registered checkout. If a person is working there without `amoeba-mcp`, no session row says so, and the wake runs beside them.
- A SIGKILLed wrapper leaves its command running until its own cap ends it or the PM stops it, and a new wake can start beside it after its deadline (D6).

### Mitigation Strategies
- Waking is opt-in per member and set by the PM from the CLI, and `list members` shows every command. The docs say to use it for repos nobody works in.
- The orphan needs a SIGKILL of the wrapper. The contract requires every wake command to carry its own cap, a docs test checks the example does, and `list` shows the orphan as overdue with its pid and log.

## Implementation Notes

### Development Approach
1. Config keys; migration 9 and `store/wakes.py` with their tests (the claim's checks and order, the live predicate, the 24-hour count, finish, prune, pinning).
2. `wake_command` through the CLI's `add` and `list members`, and its absence from the MCP `add` tool; their tests.
3. `wake_run` and the `wake-run` subcommand, tested with a fake clock and a real short-lived child, including the timeout, the explicit environment, each failure before the command starts, and an unexpected error after it.
4. `resolve_recipient`'s return type, `send`'s read of `wake_command`, `wake_after_send`, `SendResult.wake_problem`, the sweep step and due check, and the timing test.
5. `WakeStatus`, `list`/`status` and the renderer.
6. Docs, the departures' wording in the architecture and plan, then the fixture agent and `tests/live/waking`.
7. The live-store migration.

### Special Considerations
- **Command execution.** `wake_command` is a program run with the user's privileges and nobody present. The PM sets it from the CLI; the design rests on the architecture's trust assumption, shows every command in `list members`, runs it with an explicit environment, and never passes message text to it. No SQL or shell is built from a message.
- **No process held across a lock.** The claim commits before the spawn, and the wrapper holds no store lock while the command runs.
- **Live store (designated for migration; backup first).** The implementing agent runs these in order, after 242's migration. Back up to `~/.local/state/amoeba/backups/`: `sqlite3 ~/.local/state/amoeba/amoeba.sqlite3 ".backup ~/.local/state/amoeba/backups/amoeba.sqlite3.pre-009"` and `cp ~/.config/amoeba/config.yaml ~/.local/state/amoeba/backups/config.yaml.pre-244`. Install the slice's code from the slice branch with `uv tool install --force <path to this repo>`, add the two keys to the live config, and migrate by running `amoeba list`. Read back: `schema_meta.version` is 9, the member count matches the backup's, `members.wake_command` is null for every member, `amoeba list` works. As in 241, every `amoeba` command fails with a `ConfigError` naming the missing keys between the install and the key edit, so the agent runs them back to back, and a running `amoeba-mcp` from older code errors until its client session restarts. Restore, with every `amoeba` and `amoeba-mcp` process stopped: copy the store backup over the live file, delete its `-wal` and `-shm`, copy the config backup back, and reinstall the previous code, since the restored store at 8 would migrate again. The restore path goes in the slice notes, and the implementing agent deletes the two backup files with `rm` at slice integration (Phase 7), after the review passes. No member has a wake command until the PM sets one, so migrating starts nothing.

## Operator Walkthrough

Done as the person running it.

- **Start.** Install, add the two keys, and for a repo nobody works in run `amoeba add --wake-command "<script or agent command>"` there, with the command's own cost or time cap in it (the contract requires one). `amoeba list members` shows it. Nothing else.
- **Normal path.** A request arrives for that repo; `send` starts the command; `list` shows `running since ...`. The agent reads `inbox`, accepts, works, replies `done`, rereads `inbox` and exits. The wake row ends `exited`. The sender hears through its own inbox (240).
- **A second request during the wake.** Nothing starts. It is in the woken agent's `inbox` if it reads again before ending, which the rules block's last moment says to do. If the agent had already finished, the request is left (D2): the sender can retry `send` with the same id to wake again, otherwise it waits for the next agent or expires at its TTL, and `list` shows its age.
- **The command fails to start** (wrong name, checkout gone, the wrapper's own error). `list` shows `last wake start_failed` with the reason and the request stays `open`. Fix the command with `amoeba add --wake-command ...`, then the sender's same-id `send` retry wakes it (a new request to that member does too), once the limit allows: failed starts count, so a broken command can have used the day's wakes and `list` then shows `waking stopped`. The PM can raise `max_wakes_per_day` in the config to resume sooner.
- **Context Forge has no path for the member.** Same display. The fix is in Context Forge, not `amoeba add`; then the same retry applies.
- **The command hangs.** At `wake_timeout_seconds` it is stopped, `list` shows `timed_out` with the log path, and the request is as the agent left it: `open` is left as above, and `accepted` ends by `done` or `decline` from the next agent in that repo or by `amoeba cancel ID` from any session.
- **The command exits non-zero.** `list` shows `exited` with the code and the log path; the request is as above.
- **The wrapper is killed.** Past the deadline `list` shows the wake as `overdue` with the command's pid and log path, and the member can be woken again. Amoeba does not stop the old command: its own cap (the contract requires one) ends it, or the PM checks and stops the pid `list` shows. That is the explicit exit. The row leaves by retention.
- **Limit reached.** `list` says waking is stopped and how many wakes were used. Requests wait; a same-id retry once the oldest counted wake is 24 hours old wakes, and one not picked up expires at its TTL and its sender is told.
- **A push-confirmed session is live in that repo** (by 241's query). No wake: the agent in it gets the request by push. If it does not read, the request waits until the session reads it, a same-id retry once the session is no longer live, or the TTL. An unconfirmed session does not prevent the wake.
- **An agent tries to set a wake command through MCP.** The `add` tool has no such field and rejects it; the PM sets it from the CLI.
- **The store is held** during the wake step: `send` still succeeds, prints `wake_problem`, and the retry above applies.
- **Undo.** `amoeba add --no-wake-command` stops later wakes. A running wake ends by itself. Rows and logs leave by `prune_after_days`. Dead ends found: one, with a named exit. A killed wrapper's command is not stopped by Amoeba; its own required cap ends it, or the PM stops the pid `list` shows as overdue. Every other case above ends by the TTL, `cancel`, the next agent's `done` or `decline`, or a retry, and a missing Context Forge path is visible in `list` and fixed outside Amoeba.
