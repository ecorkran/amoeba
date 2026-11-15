---
docType: slice-plan
layer: project
project: amoeba
parent: user/architecture/240-arch.agent-messaging.md
archIndex: 240
component: agent-messaging
audience: [human, ai]
description: Slice plan for Amoeba initiative 240. Requests between members over the CLI and MCP with polling, then push and presence from the MCP server, then holding a paused run on a request, then notes to members and programs with release-report notes, then waking a repo nobody is working in.
dateCreated: 20261114
dateUpdated: 20261114
status: not_started
---

# Slice Plan: Agent Messaging

## Parent Document

`240-arch.agent-messaging.md`

## Planning Context

Architecture-level. 220 left a store, operations with two doors (CLI and MCP) and an MCP server. This plan adds messages between members on top. Four things shape it:

- **Polling first, and it is enough on its own.** The first slice carries scenario D end to end with polling only: any agent sends, reads, accepts and finishes requests, and the rules blocks tell agents when to check. Everything after adds to a system that already works.
- **The riskiest slice comes second.** Push depends on a research-preview Claude Code feature and on restructuring the MCP server's run loop. It goes right after the base it needs, so a surprise there shows up before anything else is built on top.
- **Waking is last.** The PM chose to start without it.

Slice numbers are execution order. The first slice takes the plan's index (240).

## Foundation Work

1. [ ] **(240) Requests** — The message store and scenario D by polling. Migration 6 adds `messages` and `deliveries`. New operations `send`, `inbox`, `reply` and `cancel`, on the CLI (kebab-case, text by default, `-j`) and MCP (snake_case) through `wiring.invoke`. A request moves through open, accepted, done, declined, cancelled and expired. The first `accept` wins, a reply targets exactly one request id, and a resend with the same sender id changes nothing (different content under a reused id is rejected). Every new message and state change writes one delivery row per receiving member with a store-assigned sequence number. `inbox` takes an optional `since` and always returns `as_of_seq`, and it keeps no read marker. Reads treat an `open` request past `request_open_ttl` as expired. The sweep that records expiry, and prunes terminal requests past `prune_after_days`, runs in `send`, `reply`, `cancel`, `status`/`list` and `handle_pause`. `send` takes an optional `parent` and rejects a chain already `max_chain_depth` deep. `rm` of a member cancels its non-terminal requests, sent and received, with reason `member_removed`. The sender is the member for the working directory, or an explicit member outside any repo. Text limits are constants stated in `docs/cli-contract.md`, and over-limit text is rejected, never cut. `QUOTED_DATA_NOTICE` moves out of `changes_models` and wraps all message text. `list` and `status` show open and accepted requests per member with age and any waiting chain. `docs/program-rules.md` gains the consumer and provider messaging blocks: the four moments to check `inbox`, and that a request this repo's rules don't settle is declined with that reason.
   **Value:** User value. An agent in one repo can ask another repo for work and hear back, with any agent and any UI, and the PM sees every request in `list`.
   **Success Criteria:**
   - Scenario D's three-repo chain runs end to end in fixture repos through the CLI, and again through MCP: send, accept, child request with parent, done on the child, done on the parent, each party seeing each change in `inbox`.
   - Every request state has a tested exit: done, decline, cancel by the sender and by an explicit id from another session, expiry at the TTL, and `rm` of either member.
   - Two `accept` calls at once: one wins and the other is rejected naming the winner. A reply to the wrong id, a stale reply and a reused id with new content are each rejected with a reason.
   - Two worktrees of one member reading `inbox` from different `since` values each see every delivery after their own point.
   - A chain at `max_chain_depth` is rejected at `send`, with the rejection recorded.
   - Terminal requests and their deliveries past `prune_after_days` are pruned by the sweep. Every table the slice adds has that cleanup.
   - The new config keys fail with a named error when missing, with defaults defined once in the config layer.
   - The live store is backed up, migrated to 6 and read back, with the restore path in the slice notes.
   **Dependencies:** 220 (complete).
   **Interfaces:** Provides the `messages` and `deliveries` tables, the sweep, `send`, `inbox`, `reply`, `cancel`, the general quoted-data notice and the messaging rules blocks. 241 reads the delivery sequence, 242 reads request state, 243 adds the note kind, 244 hooks into `send`.
   **Risk Level:** Medium. It is the largest slice and sets the shapes every later slice reads.
   **Relative Effort:** 5

## Feature Slices (in implementation order)

2. [ ] **(241) Push and Presence** — `amoeba-mcp` tells its own session about new mail. The server resolves its member once at start from its working directory, and a directory that is not a member gets today's tools with no presence and no push. The serve loop runs a watcher in a task group beside `server.run`, captures the session at `initialized`, and does every store read through `anyio.to_thread`. Every `notify_poll_seconds` the watcher reads the member's highest delivery sequence number. When it rises, it sends a Claude Code channel event (`notifications/claude/channel`, with the `claude/channel` experimental capability declared) and a resource update on `amoeba://inbox`. The event carries only the new sequence number, kinds and senders, and tells the agent to call `inbox` with `since`. The server pins the handshake to a protocol revision Claude Code registers channels on, through the SDK's version negotiation. Migration 7 adds `sessions`: each serving process registers a row, heartbeats every `session_heartbeat_seconds`, and deletes it on clean exit. The sweep prunes rows older than `session_stale_seconds`. `list` shows who is live where. The slice re-checks the dated channel facts first, and the docs give the launch flag and a shell alias for it.
   **Value:** User value. A live Claude Code session acts on a request when it arrives, instead of at its next rules-file moment.
   **Success Criteria:**
   - An automated live test drives an interactive Claude Code session started with the development channels flag (in a pseudo-terminal), sends it a request from another fixture repo, and sees the session call `inbox` with no prompt from the test.
   - The pinned protocol is the one negotiated in that session, and every existing MCP tool test still passes under it.
   - The event carries no message text. A test checks its fields.
   - A server outside any member starts and serves the tools with no session row and no watcher.
   - A killed server's row reads as gone after `session_stale_seconds` and is pruned by the sweep. A clean exit deletes it.
   - The watcher never blocks a tool call. A test holds a store read and checks that tool calls still answer.
   - The live store is backed up and migrated to 7.
   **Dependencies:** 240.
   **Interfaces:** Provides the channel event, the `amoeba://inbox` resource, the `sessions` table and the live-member query 244 uses.
   **Risk Level:** High. It rests on a research-preview client feature, a protocol pin and a new server structure.
   **Relative Effort:** 4

3. [ ] **(242) Hold and Release** — A paused run waits on a request it sent. Migration 8 rebuilds the question table's state check to add `waiting_on_request`. `handle_pause` recognizes a question that names, by exact id, a request sent from this member. A request not yet terminal records the question as `waiting_on_request`. A `done` request, before or after the pause, makes its result the candidate answer. It goes through the check step and the answer screen, with the member's authorize list, and counts toward the per-run automatic-answer limit. A passing answer is recorded and 220's resume runs. A failing one moves the question to `waiting_on_pm` with the reason. A declined, cancelled or expired request moves it to `waiting_on_pm` with that reason. When a request reaches any terminal state (by `reply`, `cancel`, `rm` or the sweep's expiry), Amoeba starts `handle_pause` detached for each run waiting on it. A refused or dead resume is retried by calling `handle_pause` again with the recorded answer. 220's `run_moved_on` and `run_gone` closes apply. `dismiss` closes a `waiting_on_request` question. `status` and `decisions` show a run resumed by a request's result.
   **Value:** User value. A run that stops because it needs another repo's change carries on by itself once that change is done.
   **Success Criteria:**
   - A fixture pipeline paused on a request resumes with the result after `done` is replied from another fixture repo, and the record shows the request, check, screen and resume outcome.
   - A request done before the pause resumes the run at the first `handle_pause`.
   - A result that tries to authorize something on the member's list ("done, go ahead and release") goes to the PM with the reason.
   - Decline, cancel, expiry and `rm` each move the held question to `waiting_on_pm` with that reason.
   - A refused resume is retried with the recorded answer and starts no new answering run.
   - A held question has every exit: resume, `waiting_on_pm`, `dismiss`, `run_moved_on` and `run_gone`.
   - A question that names a request only in its wording, without an exact id match, is not held.
   - The live store is backed up and migrated to 8.
   **Dependencies:** 240. Independent of 241.
   **Interfaces:** Provides `waiting_on_request` and the request-done trigger. Consumes 220's answering check, screen, resume and question record.
   **Risk Level:** High. A result from another repo's agent resumes a real run.
   **Relative Effort:** 3

4. [ ] **(243) Notes and Release Notes** — The `note` kind. `send` takes a note to a member, or to a program with one delivery per member, the sender excluded. Notes have no state and are pruned past `prune_after_days` by the sweep. `report_release` writes a note to each consumer the report is visible to under the pair's `consumed` value, in the same transaction. A `from_release` consumer gets none for a merge report and gets one when a version is added. A correction or withdrawal sends a new note to the same consumers. The rules blocks say notes are information and need no reply.
   **Value:** User value. A repo hears about an upstream release and about program-wide news in the same inbox as its requests.
   **Success Criteria:**
   - A note to a program reaches every member except the sender, each as its own delivery.
   - For each `consumed` value, the consumers that see a report in `changes` are exactly the ones that get a note, including after a version is added, a correction and a withdrawal.
   - The note and the report are written in one transaction. A test fails the note write and finds no report.
   - Notes past `prune_after_days` are pruned with their deliveries.
   - 241's push fires for a note the same as for a request.
   **Dependencies:** 240, and 241 for the push test. 227 (complete) for `report_release`. Release-note bodies stay within a limit derived from 227's report text limits.
   **Interfaces:** Provides the note kind and release-report notes. Consumes 227's `report_release`.
   **Risk Level:** Low
   **Relative Effort:** 2

5. [ ] **(244) Waking** — A member may set `wake_command` through `add` (229: every member setting is set from the CLI). When `send` delivers a request to a member with a wake command, no live session (241) and no running wake, it starts the command detached under `amoeba wake-run`, in the member's registered directory. Migration 9 adds `wakes`. The wrapper holds the member's wake row while the command runs, records its log path under `~/.local/state/amoeba/`, stops a command past `wake_timeout_seconds`, and records how the wake ended. Rows leave by retention. The command runs with a fixed environment, never the sender's. A row left by a killed wrapper counts as gone after `wake_timeout_seconds`. Wakes per member per day stop at `max_wakes_per_day`, and the request then waits for the next agent up to its TTL. `list` shows waking stopped and why, and a failure to start. A wake's failure changes no message. Wake logs are pruned with the existing logs.
   **Value:** User value. A request to a repo nobody has open gets worked without anyone opening it.
   **Success Criteria:**
   - A request to a fixture member with a wake command and no live session starts it once. A second request during the wake starts nothing and is in the woken agent's `inbox`.
   - A member with a live session, or with no wake command, is not woken.
   - A command past `wake_timeout_seconds` is stopped and its row cleared. A wrapper killed with SIGKILL leaves a row that reads as gone after the timeout.
   - At `max_wakes_per_day` no wake starts, `list` says why, and the request still expires at its TTL.
   - A command that fails to start shows in `list` and leaves the request `open`.
   - Wake logs are pruned. Every wake row has a cleanup.
   - The live store is backed up and migrated to 9.
   **Dependencies:** 240, 241, 242, 243.
   **Interfaces:** Provides `wake_command`, `amoeba wake-run` and the `wakes` table.
   **Risk Level:** Medium. It starts agents with nobody present. The daily limit and each command's own cost cap bound it.
   **Relative Effort:** 3

## Implementation Order

`240 → 241 → 242 → 243 → 244`.

- **Dependencies.** Everything builds on 240. 244 needs 241's live-session check. 242 and 243 need only 240.
- **Risk.** 241 rests on the least certain ground, so it comes right after 240. 242 is next because it resumes real runs.

## Notes

- **Concept and initiative plan.** Scenario D was added to the concept 20261114, and the "not Amoeba" lines were replaced.
- **Dated facts.** Claude Code channel behavior and client support for resource updates were read 20261114. 241 re-checks them before building.

## Future Work

Living backlog; entries may be added during slice design, task breakdown, or implementation.
