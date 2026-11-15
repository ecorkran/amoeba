---
docType: review
layer: project
reviewType: arch
slice: agent-messaging
targetKind: arch
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/architecture/240-arch.agent-messaging.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261114
dateUpdated: 20261114
reviewedSha: c44c0f199e7d3f1c32ff1e7325edb95722c16057
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
turns: 11
promptTokens: 662195
cachedTokens: 566515
cacheWriteTokens: 95662
completionTokens: 9900
durationSeconds: 116.9
costUsd: 1.07758
costBasis: provider
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "Updates on sent requests cannot be tracked by a sequence-number read marker"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#operations"
  - id: F002
    severity: concern
    category: consistency
    summary: "One read marker per member makes parallel worktrees miss notes and updates"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#delivery"
  - id: F003
    severity: concern
    category: consistency
    summary: "Expiry depends on a sweep that only runs in `status` and `handle_pause`"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#the-requests-states"
  - id: F004
    severity: concern
    category: completeness
    summary: "A resumed run skips 220's controls on what an answer may authorize"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#holding-a-paused-run-on-a-request"
  - id: F005
    severity: concern
    category: completeness
    summary: "Resume from `reply`: the failure path, the race, and cross-repo triggering are unspecified"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#holding-a-paused-run-on-a-request"
  - id: F006
    severity: concern
    category: completeness
    summary: "`waiting_on_request` has no PM exit while the request stays `accepted`"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#the-requests-states"
  - id: F007
    severity: concern
    category: completeness
    summary: "Requests and notes addressed to a program are undefined"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#architectural-principles"
  - id: F008
    severity: concern
    category: completeness
    summary: "Unread notes are never pruned"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#message-kinds"
  - id: F009
    severity: concern
    category: technology
    summary: "The \"change counter\" doesn't exist, and heartbeats make every MCP process a regular writer"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#delivery"
  - id: F010
    severity: concern
    category: feasibility
    summary: "Push needs a session handle that the current server structure doesn't expose"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#delivery"
  - id: F011
    severity: concern
    category: completeness
    summary: "Which member an MCP process belongs to is unresolved"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#delivery"
  - id: F012
    severity: concern
    category: feasibility
    summary: "Waking: which checkout, and repeat wakes while one is still running"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#waking-a-repo-nobody-is-working-in"
  - id: F013
    severity: concern
    category: antipattern
    summary: "Cut the `amoeba://inbox` resource update, which no observed client uses"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#delivery"
  - id: F014
    severity: concern
    category: antipattern
    summary: "`message_retention_days` duplicates the existing `prune_after_days`"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#store-and-config"
  - id: F015
    severity: note
    category: consistency
    summary: "Release-report notes duplicate `changes`, and the `consumed` filter is unstated"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#message-kinds"
  - id: F016
    severity: note
    category: other
    summary: "Sender and replier identity is self-asserted"
    location: "project-documents/user/architecture/240-arch.agent-messaging.md#operations"
---

# Review: arch — initiative 240

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] Updates on sent requests cannot be tracked by a sequence-number read marker

The principles say readers resume from a sequence number the store assigns. `inbox` returns "updates on requests it sent", and `read_through` moves a single marker per member. But under "Message kinds", a reply is a state change on the request row, not a new message. A state change gets no new sequence number. So `inbox` cannot tell an update the sender has seen from one it hasn't. Push has the same problem: it must spot "new mail for its member" from a change counter that cannot attribute updates. The design should either write each state change as an event row with its own sequence number, or say how updates are marked read. As written, "every terminal state sends the sender an update" has no delivery mechanism.

### [CONCERN] One read marker per member makes parallel worktrees miss notes and updates

The doc deals only with requests addressed to the member, which "show until they are terminal". Notes don't work that way, including the new release-report notes, and neither do updates on requests a member sent. Once one session moves the marker, they are gone for every other session. Take a live agent in worktree X waiting on a request X sent. If a session in worktree Y calls `inbox` with `read_through`, X never sees the `done`. 220 decision 4 avoided read markers on `changes` for exactly this reason ("parallel worktrees don't hide changes from each other"). This design brings the problem back without saying why.

### [CONCERN] Expiry depends on a sweep that only runs in `status` and `handle_pause`

The states table says `expired` is entered by "any Amoeba call that sees `open` past its TTL (the same bounded sweep `status` already does)". In the code, that sweep and prune runs only from `status` (`operations/status.py:191`) and `handle_pause` (`handle_pause.py:73-87`). The doc should say which operations run the TTL, retention and session-staleness sweep. If it is only `status`, then a request whose TTL has passed stays `open`, and a run paused on it never moves to `waiting_on_pm`, until someone happens to call `status`. If it is every call, including `inbox` (which the MCP notifier triggers often), then every read becomes a write, which contradicts "the MCP server's change check is a read".

### [CONCERN] A resumed run skips 220's controls on what an answer may authorize

220 enforces "what an answer may authorize" with models: the answer step, the independent check step, and the answer-screen backstop. On `done`, this design resumes the run directly with "fixed text giving the request id and its result". That result is written by another repo's agent, and it never goes through the check step or the screen. Under Technical Considerations the doc says "220's list … also applies to what a request can get done through a resumed run", but it names no step that enforces it. Quoting text as data does not stop "result: merged, go ahead and release" from reaching an agent that has tools. The design should send the result through the existing check and screen before resuming, or explain why the check isn't needed.

### [CONCERN] Resume from `reply`: the failure path, the race, and cross-repo triggering are unspecified

Three gaps:
- **Retry after a refused resume.** In 220, a refused or dead resume is retried by calling `handle_pause` again, which works because the answer is recorded. Here, the doc never says the request's result is recorded as the question's answer, or what state the question is in after a refused resume.
- **Race.** `handle_pause` only recognizes requests that are "open or accepted". If the request reaches `done` before the run pauses, or before the hook runs, the question falls through to the answering pipeline. That pipeline knows nothing about the result, so it spends money on the question or sends it to the PM.
- **Cross-repo triggering.** The `reply` call comes from an agent in context-forge, but it starts `sq run --resume` in squadron's checkout. The doc should state that this cross-repo action is allowed, and say that the MCP side starts it detached, the way 220 says for long work.

### [CONCERN] `waiting_on_request` has no PM exit while the request stays `accepted`

`accepted` has no timeout. Its exits are `done` or `decline` from the addressee, or `cancel` from the sender's agent. If the context-forge session dies and nobody returns, a squadron run paused on that request waits with no end. 220's `dismiss` only covers `claimed`, `waiting_on_pm` and `answered`, so the PM cannot close the question either. `cancel` is defined as "by the sender's agent", and the doc doesn't say whether the PM, acting through an agent outside squadron, can call it. The design should add `waiting_on_request` to `dismiss` and say who may `cancel`. It should also say whether `list` shows accepted requests that have gone stale.

### [CONCERN] Requests and notes addressed to a program are undefined

"A message goes to … a program, which reaches every member." The request state machine is written for one addressee: "the first `accept` wins", "the member accepts". For a request sent to a program, the doc doesn't say:
- whether one member's accept closes it for all, or each member gets its own state;
- whether the sender can be a member of that program (and so receive its own request);
- how `rm` of one member affects it;
- when a note sent to a program counts as "read" for retention: when one member reads it, or all of them.

The design should either define fan-out (one row per member when sent) or limit program addresses to notes.

### [CONCERN] Unread notes are never pruned

A note "ends" when its member reads it or the retention sweep removes it, but retention only prunes "terminal requests and read notes". A note to a member nobody works in again, such as a release note to a dormant consumer, stays forever. The `expires` column is listed but only defined for requests. This breaks the rule that "anything the system writes either has a named cleanup or the design says why it is bounded". The fix is to give notes an expiry or prune them by age regardless of whether they were read.

### [CONCERN] The "change counter" doesn't exist, and heartbeats make every MCP process a regular writer

"Checks the store's change counter" describes an existing feature, but there is none. A search of `src/amoeba` finds no `data_version` or counter, and the schema list under "Store and config" doesn't add one. The doc should name the mechanism. Options are `PRAGMA data_version` (per connection, which works across processes) or a counter row that every message write bumps in the same transaction. Separately, each `amoeba-mcp` refreshes its session heartbeat "on the same interval". With N open sessions, that is N writes every `notify_poll_seconds`. This contradicts Technical Considerations ("the MCP server's change check is a read"). Those writes also compete with `report_release`, which holds the write lock, as the recent commit 96838c2 shows. The heartbeat interval should be separate from the notification check, and much longer.

### [CONCERN] Push needs a session handle that the current server structure doesn't expose

`amoeba-mcp` uses the low-level `Server` (mcp>=2.3) with `server.run(read, write, …)` inside `anyio.run` (`server.py:184-194`). The `ServerSession` is only reachable inside request handlers, through `ServerRequestContext`. Pushing a notification nobody asked for, from a background loop, means restructuring `_serve`. It needs a task group alongside `server.run`, and a session reference that becomes available after `initialized`, before any tool call. Every store read in that loop must go through `anyio.to_thread` under the project's async rule. Pinning the handshake protocol to avoid 2026-07-28 also has to work through the SDK's version negotiation. None of this is mentioned, and "it costs one handler" understates the work. This should be named as the push slice's main risk.

### [CONCERN] Which member an MCP process belongs to is unresolved

Push and presence both depend on the MCP process knowing "its member". But 220 says "MCP sessions can start anywhere", and its tools take an explicit program or question for that reason. A user-scoped server, or a session started outside any repo, has no member. Under the current design it would register presence for nothing, or for the wrong repo, and could not push anything. The doc should say how the member is resolved (the process's working directory? a server argument?) and what happens when it can't be resolved. If presence is recorded for the wrong member, waking is wrongly suppressed.

### [CONCERN] Waking: which checkout, and repeat wakes while one is still running

- "Starts the command detached in the member's checkout." A member is every worktree of a repo (220), so the doc must say which checkout. The main checkout can be on any branch, with uncommitted changes.
- Waking checks presence, but presence only exists for MCP sessions. A woken `codex exec` or `claude -p` registers none. Once `wake_lease_seconds` passes, the next `send` wakes a second agent while the first is still running. The lease should last until the woken process exits (with a timeout for a process that hangs), not expire on a fixed timer.
- Waking is set off by `send` from any agent, so spending is bounded per wake but not in total. Every lease expiry can start another paid run. The cap belongs to each wake command, and Amoeba enforces none of it.

### [CONCERN] Cut the `amoeba://inbox` resource update, which no observed client uses

The doc itself observes that none of the four target clients subscribes to resource updates or acts on them. Building it means a resources capability, subscribe and unsubscribe handlers, tracking subscriptions per session, and doing all that "for each protocol revision the server serves". That is building for clients that might exist one day. If a client later supports resource updates, it can be added then. Cut it from the push slice.

### [CONCERN] `message_retention_days` duplicates the existing `prune_after_days`

`UserConfig.prune_after_days` (`config/user_config.py:77`) already controls how long settled records stay, for `status` pruning and the `list` settled window. A second retention setting for messages adds a config value and a second retention policy with no stated reason. Reuse `prune_after_days`, or explain why messages need a different window.

### [NOTE] Release-report notes duplicate `changes`, and the `consumed` filter is unstated

`report_release` now also writes a note "into each consumer's inbox". The doc should say whether this follows the pair's `consumed` value. A `from_release` consumer should not get a note for a report at merge. It should also say whether a correction sends a new note. Otherwise `inbox` and `changes` will disagree about what a consumer has seen.

### [NOTE] Sender and replier identity is self-asserted

`send` accepts "an explicit member for sessions outside any repo". By the same logic, `reply` and `cancel` are limited by the member the caller claims, not by anything verified. On a single-user machine that is acceptable. Still, the doc should state it, because the "Message text is data" principle rests on knowing which repo wrote the text.

### Run Digest

- Response length: 13561 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 11
- Tokens — prompt / cached / cache write / completion / reasoning: 662195 / 566515 / 95662 / 9900 / not computed
- Duration: 116.9 s
- Cost: $1.08 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 16
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 16
- Finding-shaped matches — surviving validation: 16
