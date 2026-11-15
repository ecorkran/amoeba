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
reviewedSha: d54677b3eed5dc3fcf72b7e8d3a8917b9f3bf88c
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
effort: xhigh
turns: 14
promptTokens: 1058993
cachedTokens: 873787
cacheWriteTokens: 185190
completionTokens: 60641
durationSeconds: 282.3
costUsd: 0.36801
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: state-management
    summary: "Resource handlers have no defined behavior while the member is still resolving"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:104"
  - id: F002
    severity: concern
    category: architecture-alignment
    summary: "\"Live\" means \"a server is serving,\" which defeats the architecture's waking scenario for the common case"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:231"
  - id: F003
    severity: concern
    category: integration-points
    summary: "The departures list misstates 240's migration and omits a replaced mechanism"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:198-206"
  - id: F004
    severity: concern
    category: integration-points
    summary: "Changing 240's `sweep` contract before 240 is built"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:169"
  - id: F005
    severity: concern
    category: state-cleanup
    summary: "The stated bound on `sessions` does not hold when no server is running"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:169"
  - id: F006
    severity: concern
    category: failure-modes
    summary: "The live test's \"stated limit\" is not stated"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:193"
  - id: F007
    severity: concern
    category: operator-walkthrough
    summary: "The operator walkthrough reports no dead ends, but its own steps leave two"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:299-316"
  - id: F008
    severity: concern
    category: proportionality
    summary: "Operator steps are duplicated, and the verification walkthrough restates D10"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:299-316"
  - id: F009
    severity: note
    category: verification
    summary: "D9 is marked \"decided\" while its registration form depends on an experiment, and one path is unverified"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:187"
  - id: F010
    severity: note
    category: verification
    summary: "Two load-bearing claims rest on the design alone"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:128"
  - id: F011
    severity: pass
    category: integration-points
    summary: "Reused 220 and 240 interfaces match what they are assumed to be"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:135"
  - id: F012
    severity: pass
    category: nfr
    summary: "The watcher's no-block requirement is restated with a target"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:247"
---

# Review: slice — slice 241

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Resource handlers have no defined behavior while the member is still resolving

Line 104 says `PresenceState` is "assigned once before the tasks that read it start." That does not hold for the resource handlers. They run in the `serve_connection` loop, which is already running after `initialize`. D3 (lines 135–139) resolves the member later, in the background task, after `initialized`, and that call can take up to 30 s (`CF_GET_TIMEOUT_SECONDS`). For that window, the design gives no behavior for `resources/list`, `read`, `subscribe` or `unsubscribe`. D5 (line 156) says "no member" gets invalid-params, but a pending resolution is not the same as "not a member." Two concrete failures follow. A client that calls `resources/list` during resolution gets an empty list, and the server never sends `list_changed`, so it never sees `amoeba://inbox`. A client that subscribes during resolution gets invalid-params and never retries. The design should name the pending state and say how handlers behave in it, for example by waiting on an event that resolution sets, bounded by the 30 s timeout, or by returning an explicit "resolving" error.

### [CONCERN] "Live" means "a server is serving," which defeats the architecture's waking scenario for the common case

The architecture's operator walkthrough, step 3 ("Nobody works in context-forge… With waking: the first `send` starts the configured command"), and its presence paragraph ("who is working where and waking") both assume a live session means someone is working there. The slice defines live as "an `amoeba-mcp` is serving," so an idle Claude Code session left open, with or without the flag, suppresses 244's wake until the request's TTL expires. The walkthrough at line 315 records this as expected behavior, and line 316 says "Dead ends found: none." The departures list (lines 198–206) does not include this change, although the section promises that the docs step will amend every departure. Either refine the liveness rule so it matches the architecture (for example, a session that has recently read `inbox` or acknowledged a push), or list this as a departure and amend the architecture walkthrough and 244's wake rule to match.

### [CONCERN] The departures list misstates 240's migration and omits a replaced mechanism

Line 202 says "240 D1 creates three of the four tables, and the plan gives `sessions` here and `wakes` to 244." Migration 6 in the 240 plan (line 33) adds `messages` and `deliveries`. The 240 design's D1 (lines 118–124) adds those two plus `message_rejections`, which the architecture does not list. So 240 creates two of the architecture's four tables, and the sentence's count does not add up. The docs step will copy this into the architecture. The list also omits that the plan (line 51) and architecture (line 147) say the watcher runs "beside `server.run`" and pin the protocol "through the SDK's version negotiation." D1 replaces `server.run` with `serve_pinned`. The pin is listed, but the replacement is not.

### [CONCERN] Changing 240's `sweep` contract before 240 is built

Line 169 changes `sweep(transaction, now, prune_after_days)` (240 D6, line 172) to add `session_stale_seconds`. It also changes the "is something due" read in `sweep_messages`. The prerequisite (line 62) requires 240 to be "built and integrated," but 240's design is still at review CONCERNS and its plan entry is `not_started`. So 241 would edit an integrated contract after 240 is done, touching the callers `send`, `reply`, `cancel`, `status`, `list` and `handle_pause`. The parameter should be part of 240 D6 now, so 240 is built once with the final signature.

### [CONCERN] The stated bound on `sessions` does not hold when no server is running

Line 169 says the table "is bounded by live processes plus the stale window, whether or not anyone runs a sweep." Pruning runs in a heartbeat's write transaction, and heartbeats only happen while some server is running. Sweeps run only in `send`, `reply`, `cancel`, `status`, `list` and `handle_pause`, and `inbox` does not sweep. A SIGKILLed server's row therefore persists until the next server start or one of those calls. Rows are invisible once stale, and each is bounded, so the cleanup exists. The stated bound is still wrong. The design should say the table holds live rows plus rows from kills since the last server start or sweep.

### [CONCERN] The live test's "stated limit" is not stated

Line 193 says the harness "fails… when a screen is unknown or nothing happens within a stated limit." No value appears anywhere in the design. The wait for `tool inbox called` (line 195) has no limit either. The rule requires explicit handling for each I/O path, and an unnamed timeout is not one. Name the constant for each wait: start-up screens, and the `inbox` wait.

### [CONCERN] The operator walkthrough reports no dead ends, but its own steps leave two

Line 316 says "Dead ends found: none," yet the same bullet says that after Phase 7 the schema cannot be rolled back. Older code refuses a store stamped 7, and the only rollback is a `DROP`, which needs the PM's designation. The walkthrough should name that as a dead end and give the rollback steps, or justify forward-only migration explicitly. Also, step order in Special Considerations (line 299) is install, back up, add keys, migrate. Once the new code is installed, every `amoeba` command fails at config load until the keys are added, because the keys are required (D7). That window is not mentioned, and the walkthrough says "every command now needs the three keys" only after migration. Add the keys before the install, or state the window and say what agents see during it.

### [CONCERN] Operator steps are duplicated, and the verification walkthrough restates D10

The migration procedure appears in three places: the live-store step (line 299), the migration bullet in the operator walkthrough (line 305), and the undo bullet (line 316). The verification walkthrough (lines 263–271) restates D10's test steps and the success criteria. Cut the operator-walkthrough migration bullet to one line that points at line 299, and reduce verification step 3 to a reference to D10. The Functional Requirements list also repeats D2, D4 and D5 detail, and could point at those sections instead.

### [NOTE] D9 is marked "decided" while its registration form depends on an experiment, and one path is unverified

Line 187 names three registration forms, adopts whichever registers the channel in step 1, and allows a `BLOCKED:` stop if none does. The section's "Status: decided" (line 183) is therefore conditional. Mark it as decided pending step 1. Line 314 also states that `claude --debug` writes to `~/.claude/debug/<session-id>.txt`. That path is not verified in the design, and the Verify-facts rule applies to it.

### [NOTE] Two load-bearing claims rest on the design alone

Line 128 says `Connection.notify` "never raises," and D2 relies on that to say nothing retries a dropped event. No test pins it. The MCP 2.3 symbols that D1 builds on (`Connection.for_loop`, `serve_connection`, `JSONRPCDispatcher`) are also not verifiable from the repo, since no SDK install exists there. I could not check them, and D1's pin test is the only evidence. The design should name both as unverified until the pin test and a notify test exist.

### [PASS] Reused 220 and 240 interfaces match what they are assumed to be

Checked against the built 220 code: `resolve_member(store, directory, run)` matches the call in D3. `StoreBusyError` subclasses `StoreError`, so D2's specific retry catch is reachable and other store errors fall through to the top-level handler. `BUSY_TIMEOUT_SECONDS`, `CF_GET_TIMEOUT_SECONDS` (30 s), `MCP_CALL_DEADLINE_SECONDS`, `run_cf`/`CfCallFailed`, `wiring.open_store` and `default_deps` all exist. `mcp>=2.3,<3` is already declared. The 240 items (`highest_assigned_seq`, `deliveries (member_id, seq)`) match 240's design, which is not yet built.

### [PASS] The watcher's no-block requirement is restated with a target

The architecture's "many short-lived writers" and "none holds the write lock across an outside call" requirements are carried into D2 (every store call through `to_thread`, one worker-side open per call). Success criterion line 247 restates the no-block requirement with a target: `ping`, `tools/list` and a tool call answer within one second while a store read is held. D3 gives the 30 s `cf` bound.

### Run Digest

- Response length: 10933 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 14
- Tokens — prompt / cached / cache write / completion / reasoning: 1058993 / 873787 / 185190 / 60641 / not computed
- Duration: 282.3 s
- Cost: $0.37 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12

## Resolution

- **F001** (resource handlers while the member resolves): fixed. `PresenceState` now has a named pending state and a `resolved` event set in a `finally`; every resource handler waits on it, bounded by the lookup's own limits, so none answers from the pending state (State Management, D5, and a success criterion testing each state).
- **F002** ("live" means serving): applied as a departure, not a rule change. Departures now say "live" is serving, not attentive, that the architecture's presence paragraph and walkthrough step 3 are amended to say so, and why the rule is not refined: Claude Code gives the server no signal that the agent reads mail. A repo with no session, the case waking is for, is still woken. "Provides to 244" now points at the departure.
- **F003** (departures misstate 240's migration, omit the replaced mechanism): fixed. The migration line now says 240's migration 6 creates `messages` and `deliveries` (and `message_rejections`, its own addition) and that `sessions` and `wakes` get migrations 7 and 9. A new line records that the serve loop is `serve_pinned` and the watcher runs beside it, not beside `server.run`.
- **F004** (changing 240's `sweep` before 240 is built): remedy rejected, reason added to D6. The parameter cannot go into 240 now because the `sessions` table does not exist until migration 7, so 240's sweep cannot hold the step. The plan runs 240 first, so the edit lands on the sweep as built; D6 names the callers that pass the value from the config they already hold, and 240's tests must pass with it.
- **F005** (bound on `sessions` wrong with no server running): fixed. D6 and the Undo bullet now say the table holds live rows plus killed servers' rows until the next server start or sweep, and that stale rows are never shown.
- **F006** (live test limit not stated): fixed. D10 names `STARTUP_SCREEN_WAIT_SECONDS` (60), `INBOX_CALL_WAIT_SECONDS` (120) and `STALE_MARGIN_SECONDS` (5), and says each failure reports what it was waiting for and the last screen.
- **F007** (walkthrough reports no dead ends but leaves two): fixed. The forward-only schema after Phase 7 is now named a dead end by design, with its justification and the exact rollback (`DROP TABLE sessions`, `schema_meta.version` 6) that needs the PM's designation. The install-before-keys window, and the window from the key edit until a session restarts, are stated in the live-store procedure. The order is now back up, install, keys, migrate, restart.
- **F008** (duplicated operator steps, walkthrough restates D10): fixed. The operator Migration bullet is one line pointing at the live-store procedure. Verification step 3 refers to D10, whose three-session script moved there from the walkthrough. Three Functional Requirements bullets now point at D2, D4 and D5 instead of restating them.
- **F009** (D9 "decided" but conditional; debug path unverified): fixed. D9 says what is decided (the order and the `BLOCKED:` stop) and that the adopted form is step 1's output, with the project `.mcp.json` as the working assumption until then. The `~/.claude/debug/<session-id>.txt` path is documented in the channels reference (read 20261115) and is now cited there.
- **F010** (two load-bearing claims rest on the design alone): partly applied. D1 and D2 now say what evidence exists (the 20261115 measurement against the 2.3.0 install in the repo's `.venv`, and the SDK source for `Connection.notify`) and that it is the only evidence until the pin test exists. A success criterion adds a test that a send on a closed stream does not raise.
- **F011** (pass: reused 220 and 240 interfaces): no change needed.
- **F012** (pass: no-block requirement has a target): no change needed.

No finding needed a deferral, so no GitHub issue was filed and the artifact names none.

**Second pass 20261115.** Some entries above were redone in the design during a second resolution pass. Where this section and the design disagree, the design governs.
