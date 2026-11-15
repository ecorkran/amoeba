---
docType: review
layer: project
reviewType: slice
slice: push-and-presence
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/241-slice.push-and-presence.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: fda3db58aef652223b70ecab9b5657ee9bc790da
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 21
effort: xhigh
turns: 22
promptTokens: 1498500
cachedTokens: 1317514
cacheWriteTokens: 180964
completionTokens: 51238
durationSeconds: 249.3
costUsd: 0.25946
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: pass
    category: scope
    summary: "Scope matches the 241 plan entry"
    location: "project-documents/user/slices/241-slice.push-and-presence.md#technical-scope"
  - id: F002
    severity: pass
    category: interfaces
    summary: "Interfaces with 240 and 244 match"
    location: "project-documents/user/slices/241-slice.push-and-presence.md#integration-points"
  - id: F003
    severity: pass
    category: prompt-injection
    summary: "Channel event carries no message text"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:145"
  - id: F004
    severity: pass
    category: dependency
    summary: "SDK surface named in the design exists in the installed version"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:109-119"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Config and state placement follows the project rule"
    location: "project-documents/user/slices/241-slice.push-and-presence.md#state-management"
  - id: F006
    severity: concern
    category: architecture-alignment
    summary: "Migration 7 departs from the architecture and is not in the departures list"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:194-202"
  - id: F007
    severity: concern
    category: architecture-alignment
    summary: "Resource updates reach unsubscribed clients, and the subscribe handlers record nothing"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:151-154"
  - id: F008
    severity: concern
    category: failure-modes
    summary: "The background `cf` call has no stated timeout or failure path"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:133-136"
  - id: F009
    severity: concern
    category: error-handling
    summary: "The watcher's `StoreError` branch swallows the error and leaves a live row with no push"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:126"
  - id: F010
    severity: concern
    category: failure-modes
    summary: "Heartbeat and baseline failures are unspecified, and the \"sent\" log cannot show a dropped send"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:163"
  - id: F011
    severity: concern
    category: under-specification
    summary: "The registration form is undecided, so the operator's Start step cannot be stepped"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:183-184"
  - id: F012
    severity: concern
    category: operator-walkthrough
    summary: "Live-store cleanup names \"the two files\" without naming them, and the walkthrough omits the migration's effects"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:300"
  - id: F013
    severity: note
    category: proportionality
    summary: "The Patterns section restates project rules"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:204-207"
---

# Review: slice — slice 241

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Scope matches the 241 plan entry

Each item in the plan's 241 entry (the pinned loop, watcher, channel event, `amoeba://inbox` resource, migration 7 with `sessions`, heartbeat, stale pruning, the three config keys, `list`/`status`, docs, live test, live-store step) has a matching section. Nothing the plan assigns to 241 is dropped or deferred. The exclusions (message operations, notes, holds, waking) are assigned to 240, 242, 243 and 244 by the plan.

### [PASS] Interfaces with 240 and 244 match

240's integration section says 241 "adds the per-member read its watcher needs", and this design adds `member_high_seq`. The `deliveries` index `(member_id, seq)` covers the push read. 244 gets `live_member_ids` and the `sessions` table, as the plan and architecture require. The `sweep` signature change is listed as a departure (line 202).

### [PASS] Channel event carries no message text

The content template is fixed. Entries use closed enums and a member id. 220's analysis (`project-documents/user/analysis/220-analysis.code-audit.md`, line 320) records the member id as the Context Forge project id, not user-typed text, so the design's claim that the event holds only "Context Forge ids" holds.

### [PASS] SDK surface named in the design exists in the installed version

I checked the installed mcp package. `Connection.for_loop`, `Connection.notify` and `send_resource_updated` exist, and the SDK names the dual-era loop that D1 avoids. I did not confirm `serve_connection` or `JSONRPCDispatcher` by name, so the pin's contract test has to verify them.

### [PASS] Config and state placement follows the project rule

Sessions rows and the backups live in the state directory. The three keys are config keys with no code defaults. Nothing in the design writes state under `~/.config`.

### [CONCERN] Migration 7 departs from the architecture and is not in the departures list

The architecture puts `sessions` in "a schema 6 migration" with `messages`, `deliveries` and `wakes` (`project-documents/user/architecture/240-arch.agent-messaging.md`, lines 176-183). The plan puts `sessions` in migration 7 (`project-documents/user/architecture/240-slices.agent-messaging.md`, line 51), and this design follows the plan (D6, line 161). The departures section says the docs step amends the architecture and plan "so none stays a difference", but its list omits this split. Add a departure bullet for migration 7, with the reason (240 shipped 6 with its own tables, and sessions is a separate slice's table). The architecture's "Store and config" paragraph needs the same amendment.

### [CONCERN] Resource updates reach unsubscribed clients, and the subscribe handlers record nothing

The architecture says the update uses "the handshake protocol's resource subscription" (240-arch, line 143). The design sends the update to every client, subscribed or not (D5, departures at lines 198-199). Its justification cites the architecture's direction that a signal is "worth sending even where clients ignore it". That direction concerns clients that ignore the signal, not clients that never subscribed. Meanwhile `subscribe` and `unsubscribe` succeed and record nothing (line 153), so the server declares `resources: {subscribe: true}` but ignores subscriptions. A client that unsubscribes still gets updates.

The SDK's `send_resource_updated` has no subscription check, so the design can be built as written. The SDK's comment on change notifications applies the rule to the 2026-07-28 era, not the handshake era the server speaks, so the design must state the rule it relies on. Decide one of two options: (a) keep a per-process set of subscribed URIs and send only to subscribers, or (b) stop declaring `subscribe: true`, send unconditionally, and record the spec reasoning in the departures. The current text does neither.

### [CONCERN] The background `cf` call has no stated timeout or failure path

D3 calls `resolve_member(store, Path.cwd(), cf_run)` and names no timeout. 240 requires every `cf` call to go through `run_cf` with `CF_GET_TIMEOUT_SECONDS` (240 design, Timeouts paragraph). The architecture requires each new I/O path to enumerate hang and timeout handling. If `cf` hangs, the background task never reaches the watcher, so there is no session row, no push and no log line. The failure is silent, and "the handshake never waits on cf" does not cover it.

State the bound (the constant 240 names), confirm that `cf_run` is that bounded runner, and state that a timeout is a `ContextForgeError` that takes the logged not-a-member path (D3).

### [CONCERN] The watcher's `StoreError` branch swallows the error and leaves a live row with no push

D2 says any `StoreError` other than busy is logged with `logger.exception`, and then "the watcher ends, the server keeps serving tools". The project's exception rule requires a catch to either re-raise after logging, handle a specific exception with a stated reason, or be a designated process-boundary handler. `StoreError` is a base class covering busy, corrupt, schema and permission errors, and this branch does none of the three.

The heartbeat task keeps running after the push loop ends, so `list` keeps showing the session as live while push is dead. The design gives no stated exit from that state other than reconnecting, and does not say so. Decide which handler is the designated top-level boundary (it logs and keeps tools serving), and say what `list` shows once the push loop has ended.

### [CONCERN] Heartbeat and baseline failures are unspecified, and the "sent" log cannot show a dropped send

- **Heartbeat.** D6 handles only `StoreBusyError` on a beat. Any other `StoreError` in the heartbeat has no stated handling.
- **Baseline.** The push loop takes its baseline once (line 98). The design does not say what happens if that read fails. If the last-seen value stays unset, the next successful read could report all existing mail as new.
- **Sends.** The installed SDK's `notify` never raises and debug-logs a dropped send. The planned INFO line `channel event sent` (line 191) is therefore written even when the notification never left, so it cannot serve as delivery evidence. The live test's `tool inbox called` line is the real evidence. Label the INFO line as queued, or say it is not delivery evidence.

### [CONCERN] The registration form is undecided, so the operator's Start step cannot be stepped

D9 says the docs will state only the registration forms that registered the channel, and that the live test's first task finds those forms. The walkthrough's Start step says "register the server in the form the docs give" (line 306). D9 is marked "decided", yet the one command an operator must run is unknown at design time. This defers in-scope docs content to implementation, which the Amoeba design rules forbid. Either record the check's result in the design with the Claude Code version it was run on, or name the candidate forms and the registration outcome each must produce. D4 and D9 are also marked "decided" while Development Approach step 1 (line 289) may change them.

### [CONCERN] Live-store cleanup names "the two files" without naming them, and the walkthrough omits the migration's effects

Special Considerations says the implementing agent "deletes the two files with `rm` at slice integration". The preceding sentences name four files: the store backup, its `-wal` and `-shm`, and the config backup. Read as the backups, this deletes the only restore path after review. Read as `-wal` and `-shm`, it deletes live SQLite sidecar files. Name the files.

The same paragraph says every running `amoeba-mcp` is refused by a store stamped 7 until it restarts. The walkthrough (lines 302-314) omits that effect. Its Undo bullet (line 314) says "The only state is `sessions` rows", but undoing the migration needs the restore procedure, because the newer-schema guard refuses a downgrade. Add both to the walkthrough and point Undo at the restore path.

### [NOTE] The Patterns section restates project rules

The three bullets under "Patterns and Conventions" restate the project's exception, logging and constants rules, which the design does not need to repeat. Cut them. The design is about the size of 240's (314 against 359 lines), and its components fit the plan. The subscribe handlers are the one piece that may be cut or changed (see the resource finding above).

### Run Digest

- Response length: 11047 chars
- Response is newline-free: no
- Tool calls made: 21
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 22
- Tokens — prompt / cached / cache write / completion / reasoning: 1498500 / 1317514 / 180964 / 51238 / not computed
- Duration: 249.3 s
- Cost: $0.26 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
