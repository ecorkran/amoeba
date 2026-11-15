---
docType: review
layer: project
reviewType: slice
slice: requests
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/240-slice.requests.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: c71f31fd384aeea0120dba7885a79f5732e94e80
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
effort: xhigh
turns: 18
promptTokens: 1752233
cachedTokens: 1552218
cacheWriteTokens: 199991
completionTokens: 82087
durationSeconds: 381.7
costUsd: 0.470378
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: architecture
    summary: "Explicit `member` overrides the directory for every session"
    location: "project-documents/user/slices/240-slice.requests.md:137-142"
  - id: F002
    severity: concern
    category: specification
    summary: "D10 says a re-registered member starts with no requests; D7 and slice 228 say otherwise"
    location: "project-documents/user/slices/240-slice.requests.md:198-201"
  - id: F003
    severity: concern
    category: integration
    summary: "New SQL does not say it uses slice 228's active-member predicate"
    location: "project-documents/user/slices/240-slice.requests.md:165"
  - id: F004
    severity: concern
    category: error-handling
    summary: "`reply` and `cancel` have no timeout or lost-response handling"
    location: "project-documents/user/slices/240-slice.requests.md:99-101"
  - id: F005
    severity: concern
    category: architecture
    summary: "\"No silent drops\" covers sends only"
    location: "project-documents/user/slices/240-slice.requests.md:193-196"
  - id: F006
    severity: concern
    category: specification
    summary: "The Departures section omits four deviations"
    location: "project-documents/user/slices/240-slice.requests.md:215-222"
  - id: F007
    severity: concern
    category: NFR
    summary: "The 180 s budget rests on an unnamed, configurable `cf` timeout and leaves out the SQLite wait"
    location: "project-documents/user/slices/240-slice.requests.md:97"
  - id: F008
    severity: concern
    category: proportionality
    summary: "Consumer-only fields and returns are built ahead of their slices"
    location: "project-documents/user/slices/240-slice.requests.md:259-263"
  - id: F009
    severity: note
    category: integration
    summary: "Store row mapping and operation models have no stated direction"
    location: "project-documents/user/slices/240-slice.requests.md:87-90"
  - id: F010
    severity: note
    category: specification
    summary: "The documented departures are sound and the parents need the amendments"
    location: "project-documents/user/slices/240-slice.requests.md:215-222"
  - id: F011
    severity: pass
    category: architecture
    summary: "The state machine, expiry and sweep match the architecture"
    location: "project-documents/user/slices/240-slice.requests.md:144-174"
  - id: F012
    severity: pass
    category: architecture
    summary: "No store lock is held across an outside call"
    location: "project-documents/user/slices/240-slice.requests.md:97-103"
  - id: F013
    severity: pass
    category: architecture
    summary: "Chain depth and the named integration points check out"
    location: "project-documents/user/slices/240-slice.requests.md:191"
  - id: F014
    severity: pass
    category: design-rule
    summary: "The live store step follows the designation"
    location: "project-documents/user/slices/240-slice.requests.md:334"
---

# Review: slice — slice 240

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Explicit `member` overrides the directory for every session

The architecture allows an explicit member "for sessions outside any repo" (`project-documents/user/architecture/240-arch.agent-messaging.md:115`). D3 makes `member` override the directory everywhere, on the CLI and in MCP. Identity is self-asserted, so nothing catches a repo's agent passing another repo's name, and its messages are then written under that name. The architecture says "which repo wrote this text" rests on that identity (line 71). The override also lets `reply` and `cancel` act as the addressee from any directory, though the architecture's `reply` row is "an agent in the addressee repo" (line 117). Fix: when the directory resolves to a member and `member` names a different one, reject with a named code. Keep the override only for directories in no member, or list the widening in Departures with a reason.

### [CONCERN] D10 says a re-registered member starts with no requests; D7 and slice 228 say otherwise

D10 says a removed member "that is re-registered starts with no requests." D10 cancels only non-terminal requests, and D7 says a no-`since` inbox returns "terminal ones still held" (line 181). Slice 228 D8 re-registers a removed member by naming it again, which clears `removed_at` on the same row (`project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:255`). The member's id and its retained history therefore come back, and the first `inbox` shows its cancelled and terminal requests. The sentence is wrong. The walkthrough's "Dead ends found: none" (line 347) does not cover this path. Fix: state what the re-added member sees, or name a removal-time cleanup of terminal rows and justify it.

### [CONCERN] New SQL does not say it uses slice 228's active-member predicate

D5 skips "a party that is no longer an active member," and D1 and D10 read `members`. Slice 228 D8 puts the active-member predicate in one SQL constant in `store/programs.py` and states that no other module queries `members`, which an AST test checks (`project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:255`). The design lists `tests/test_read_side_defined_once.py` as still passing (line 283), but never says the new `store/sql_messages.py` and delivery writer use that predicate. Fix: name the shared predicate as the only active-member check for deliveries, the sweep and the `rm` cascade.

### [CONCERN] `reply` and `cancel` have no timeout or lost-response handling

`send` has a retry story: the same id, stated in D2 and the data flow (line 97). `reply` and `cancel` have none. The MCP deadline returns a timeout while the write can still finish. Slice 226 D12 says "a late finish leaves a consistent store" (`project-documents/user/slices/226-slice.mcp-server.md:141`). An agent that retries a timed-out `reply accept` gets `already_accepted` naming its own agent (line 155), which looks like a failure to it. The design should say what the timed-out caller checks (its `RequestView` through `inbox`, or the named state in the rejection), and whether a repeat accept with the same `agent` label is `unchanged`.

### [CONCERN] "No silent drops" covers sends only

The architecture says "A message that can't be sent or applied is a recorded outcome with a reason, visible in `inbox` or `list`" (`project-documents/user/architecture/240-arch.agent-messaging.md:70`). D9 records rejections only for `send`. A rejected `reply` (`not_addressee`, `already_accepted`, `not_applicable`, `unknown_request`) or `cancel` goes back to the caller alone. The PM and the other party never see it, and `list` cannot show it. Either record these in the same table with the same sweep, or state in Departures that the principle covers sends only, and why.

### [CONCERN] The Departures section omits four deviations

The section lists five departures. Four more are not listed:
- (a) D2 rejects an identical resend of an ended request as `request_ended`. The architecture says a resend "changes nothing: first one wins" (line 66), and the plan says the same (`project-documents/user/architecture/240-slices.agent-messaging.md:33`). The store is unchanged, but the answer moves from `unchanged` to `rejected`.
- (b) D3 (line 141) lets the addressee, and any caller naming the id, cancel. The architecture allows "the sender's agent, or any agent acting for the PM" (line 97), and an accepted request leaves by cancel "from the sender or for the PM" (line 101). Identity cannot be checked, so say so and list the change.
- (c) D1 (line 124) builds the `note` kind, `to_program` and the note `CHECK`s in 240. The plan says 243 "adds the note kind" (`240-slices.agent-messaging.md:45`), and 243 has no migration. D1's reason, that SQLite cannot widen a `CHECK` in place, holds, but the plan's 243 entry and this section must say so.
- (d) The architecture's anticipated Messages slice included notes to programs and release-report notes (`240-arch.agent-messaging.md:223`). The plan moved them to 243. Cite that move in the Excluded list (line 57), so it reads as the plan's split and not as a deferral.

### [CONCERN] The 180 s budget rests on an unnamed, configurable `cf` timeout and leaves out the SQLite wait

The design gives "run_cf: 30 s each" and says three calls (90 s) fit inside the 180 s MCP deadline. The 30 s is not a named value. The 220 code audit says `cf_timeout_seconds` moves "into the user-level config" (`project-documents/user/analysis/220-analysis.code-audit.md:139`), so the bound can change without any check. The budget also leaves out the SQLite busy wait that happens inside the write transaction after the `cf` calls. Fix: name the key, state the bound as calls × timeout plus the busy timeout, and add a start-up check like the `check_deadline` slice 226 D12 uses, or state that the value is fixed.

### [CONCERN] Consumer-only fields and returns are built ahead of their slices

Four pieces have no caller in 240: `member_latest_seq` (for 241's watcher), `delivered_to` on the `send` result (for 244), `SweepReport.expired_ids` (for 242), and the ids that `cancel_member_requests` returns (for 242). The plan's 240 Interfaces entry (line 45) does not list them, so cutting them is not deferring 240's scope. Each consuming slice can add its field or read in the change that needs it. Keep `highest_assigned_seq`, which `inbox` uses. The note schema stays, for the reason in D1.

### [NOTE] Store row mapping and operation models have no stated direction

`RequestView` and `DeliveryView` are defined in operations (line 87), and `store/*` does "row mapping" (line 90). The design does not say whether the store returns row types that operations turns into views, or whether the store builds the views. If the store builds them, it imports operations. The import-boundary test the design lists (line 283) would catch that, but the direction should be stated so the implementer does not find out late.

### [NOTE] The documented departures are sound and the parents need the amendments

The unit-suffixed key name (`request_open_ttl_hours`), "no code defaults" (line 219, following the project rule against fallback values), the Requesting and Handling block names (line 220), the extra table (line 221) and the `agent` label (line 222) are justified. The architecture's "defaults defined once in the config layer" (`240-arch.agent-messaging.md:185`) and the plan's matching criterion (`240-slices.agent-messaging.md:42`) need the same reading. The docs step should amend both.

### [PASS] The state machine, expiry and sweep match the architecture

D4's transitions match the architecture's states table (`240-arch.agent-messaging.md:88-95`). `accepted` never expires and leaves by done, decline or cancel. Expiry is read-side (`effective_state`) and written by the sweep, as the architecture says (line 99). Each table has a named cleanup (D6, and criterion line 281).

### [PASS] No store lock is held across an outside call

The architecture requires that no write lock be held across an outside call (`240-arch.agent-messaging.md:212`). `send` resolves sender and recipient before the write transaction. `inbox` is a read with no marker. `status` and `list` sweep only when work is due, so a quiet store is not write-locked by a poll.

### [PASS] Chain depth and the named integration points check out

With `max_chain_depth` 3, a fourth link is rejected, which matches the architecture (line 109) and the walkthrough's step 8. The integration points the design names exist in the parent work: member resolution, `wiring.invoke`, `apply_removal`, `changes_models`, and the `prune_after_days` setting.

### [PASS] The live store step follows the designation

The backup is taken first, with a stated restore path. The migration is additive DDL only, with no DROP or DELETE. The one-off backups are removed at Phase 7, after review. This matches the Project Manager's designation for migrations.

### Run Digest

- Response length: 10637 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 18
- Tokens — prompt / cached / cache write / completion / reasoning: 1752233 / 1552218 / 199991 / 82087 / not computed
- Duration: 381.7 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
