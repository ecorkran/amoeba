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
reviewedSha: d42a0623563245b61d9485eef0e4dfaf52918f13
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 12
effort: xhigh
turns: 13
promptTokens: 547066
cachedTokens: 374451
cacheWriteTokens: 172605
completionTokens: 62042
durationSeconds: 290.1
costUsd: 0.33146
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "The sweep's return value is specified two ways"
    location: "project-documents/user/slices/240-slice.requests.md:326"
  - id: F002
    severity: concern
    category: integration
    summary: "An expiry reaches `inbox --since` pollers only when some write runs the sweep"
    location: "project-documents/user/slices/240-slice.requests.md:173"
  - id: F003
    severity: concern
    category: integration
    summary: "The writers' return contract is left to 242"
    location: "project-documents/user/slices/240-slice.requests.md:267"
  - id: F004
    severity: concern
    category: consistency
    summary: "Several departures from the architecture are missing from the Departures section"
    location: "project-documents/user/slices/240-slice.requests.md:217"
  - id: F005
    severity: concern
    category: scope
    summary: "The config-defaults requirement from the plan and architecture is dropped"
    location: "project-documents/user/slices/240-slice.requests.md:221"
  - id: F006
    severity: concern
    category: proportionality
    summary: "Mechanisms the plan does not require can be cut"
    location: "project-documents/user/slices/240-slice.requests.md:134"
  - id: F007
    severity: concern
    category: proportionality
    summary: "The inbox poll looks up member names through `cf` on every call"
    location: "project-documents/user/slices/240-slice.requests.md:187"
  - id: F008
    severity: note
    category: failure-modes
    summary: "\"A timeout is a ContextForgeError\" does not match how names fail"
    location: "project-documents/user/slices/240-slice.requests.md:105"
  - id: F009
    severity: concern
    category: failure-modes
    summary: "`list` and `status` gain a write path that is outside the timing check"
    location: "project-documents/user/slices/240-slice.requests.md:107"
  - id: F010
    severity: pass
    category: architecture
    summary: "The core model matches the architecture"
    location: "project-documents/user/slices/240-slice.requests.md:146-176"
  - id: F011
    severity: pass
    category: integration
    summary: "Dependency direction and existing integration points check out"
    location: "project-documents/user/slices/240-slice.requests.md:90"
  - id: F012
    severity: pass
    category: failure-modes
    summary: "The timeout arithmetic is consistent"
    location: "project-documents/user/slices/240-slice.requests.md:105"
  - id: F013
    severity: pass
    category: operator-walkthrough
    summary: "The operator walkthrough has no dead end where nobody can act"
    location: "project-documents/user/slices/240-slice.requests.md:344-355"
---

# Review: slice — slice 240

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] The sweep's return value is specified two ways

Risk Assessment says "the `note` kind, `to_program` and the sweep's return value are in now so later slices add rows, not columns." D6 (line 176) says the sweep "returns nothing; tests read the rows. 242 changes it to report the ids," and Integration Points (line 267) says the writers "return no ids here." The document contradicts itself on the one shape it says 240 fixes for 242. Pick one. Given the next finding, returning the affected ids now is the cheaper choice.

### [CONCERN] An expiry reaches `inbox --since` pollers only when some write runs the sweep

The sweep writes the `expired` delivery (D6 step 1). `inbox` stays a read, as the architecture requires. After the first call, the rules tell agents to pass `as_of_seq`, so they read deliveries only. In a quiet store, a sender or addressee polling with `since` never sees an expiry until some other write, `list` or `status` runs the sweep. The walkthrough (line 350) says "the next write or list records it," which describes the wait without saying how long it can be. The plan's success criterion requires each party to see each change in `inbox`. Either state the delay and its bound in the design and walkthrough, or decide how a `since` reader learns of an expiry without making `inbox` write.

### [CONCERN] The writers' return contract is left to 242

Value (line 40) says the slice "fixes the shapes 241 to 244 read." Provides to 242 says `reply`, `cancel`, `sweep` and `cancel_member_requests` return nothing here, and that 242 will add the returns and thread the `rm` ids out through `apply_removal`. The architecture already names the ids 242 needs: a `reply` marking done or a sweep expiry starts `handle_pause` for each run waiting on that request. 240's tests would then be written against return types that change in 242, and 242 changes four signatures plus `apply_removal`'s return. This is a known need, not a later-slice feature. Return the affected request ids from these writers in 240.

### [CONCERN] Several departures from the architecture are missing from the Departures section

The section lists nine departures and says the docs step will amend the architecture to match. Four more are undocumented:
- **Cancel.** D3 (line 143) lets any party that names the id cancel, including the addressee. The architecture (Operations and "Who may cancel") allows the sender's agent or an agent acting for the PM.
- **Explicit `member`.** D3 (line 139) rejects an explicit `member` that names a different member from a repo session (`member_mismatch`). The architecture's identity principle says "or one the caller names." The plan says "outside any repo," so the design follows the plan, but the architecture is still departed from.
- **`to_self`.** The rejection at line 141 is not in the architecture, which says cycles are allowed.
- **`inbox --since` returns `requests`.** Line 184 adds requests to the since-response. The architecture says "only the deliveries after that sequence number."

Each is a reasoned choice, but each needs a line in Departures so the amended architecture matches the code.

### [CONCERN] The config-defaults requirement from the plan and architecture is dropped

The plan's success criterion (Foundation Work #1) and the architecture's "Store and config" section both say the new keys have "defaults defined once in the config layer." The design says the config layer holds none, and the values live only in the contract's example. That reading matches the existing `prune_after_days` precedent, which is required with no default, and the project's no-silent-fallback rule. It is still a departure from both parent documents, and the docs step must amend both. Make that amendment explicit, not just a Departures entry.

### [CONCERN] Mechanisms the plan does not require can be cut

- **Generated ids** (D2, with `Deps.new_id`, departure at line 225). The architecture says the sender picks the id, and a generated-id send is not retry-safe. Cut it: make `--id` required, and drop `new_id` from `Deps`.
- **`agent` label on `reply`** (API table, departure at line 224). The architecture says the member accepts, not the session, and that the second accept names who accepted. Naming the accepting member satisfies that. The label adds a column, a field, a 100-character limit and a CLI flag.
- **`to_self`** (line 141). Cut it, or justify it against "cycles are allowed."

Keep these only if the PM wants them. None of them is in the plan's scope.

### [CONCERN] The inbox poll looks up member names through `cf` on every call

`RequestView` carries `{id, name}` for both members, so each `inbox` call adds a second `cf` subprocess (up to 30 s, exit 3 on failure, no degraded mode). Agents poll at four moments per session. The plan does not require names in `inbox`, and `list` and `status` already show them. Cut the names from `inbox` and keep them in `list` and `status`. That removes one external call and one failure point from the path every agent uses.

### [NOTE] "A timeout is a ContextForgeError" does not match how names fail

The `cf` runner returns a failure value rather than raising, and the project-names lookup returns its failure as a value too. The names step of `inbox` therefore needs an explicit mapping from that value to exit 3. The design should state that mapping, as the existing `changes` path does.

### [CONCERN] `list` and `status` gain a write path that is outside the timing check

`status` and `list` now call `sweep_messages`, which opens a write transaction when something is due, with a 5 s busy wait. Both also make `cf` calls. The worst-case test (line 289) covers only `send`, `reply`, `cancel` and `inbox`, though the 180 s MCP deadline applies to every tool. The design also does not say what a busy store does to `list` and `status`. Patterns (line 231) implies exit 3, but a read command that fails on write contention should say so on its own path. Add both to the worst-case test and state their handling.

### [PASS] The core model matches the architecture

The request states and transition table (D4) match the architecture's state table, including `accepted` leaving only by `done`, `decline` or `cancel`. The per-party delivery rule, the store-assigned sequence, and `as_of_seq` from `sqlite_sequence` (D5, D6, D7) match the architecture's "no shared read marker" principle. Effective state for expiry, and `accepted` having no timeout with explicit exits, match the "Expiry" and "member accepts" paragraphs. Chain depth and cycle handling (D8) match the chains section. Exclusions match the plan's 241–244 split.

### [PASS] Dependency direction and existing integration points check out

The store imports nothing from operations, and operations build pydantic views from store dataclasses, as the architecture's layering requires. The design reuses the existing active-member predicate rather than copying it. `apply_removal` takes a transaction and returns a list of change records, which matches what the design says the `rm` cascade hooks into.

### [PASS] The timeout arithmetic is consistent

Worst cases are 4×30 + 3×5 = 135 s for `send` and 3×30 + 3×5 = 105 s for `reply`, `cancel` and `inbox`, both under the 180 s MCP deadline. The store-wait count matches the existing `ANSWER_STORE_WAITS` formula. Writes never span an outside `cf` call, since each operation resolves its caller and recipient before its write transaction. The remaining gap is `list` and `status`, noted above.

### [PASS] The operator walkthrough has no dead end where nobody can act

I walked the design as the person running it: set-up, the normal path, an unanswered request, an accepted request whose session dies, a repo removed mid-request, a wrong cursor, and undo. Every state has an exit by command or by age: `open` by expiry or `cancel`, `accepted` by `done`, `decline` or `cancel`, and terminal rows, deliveries and rejections by age. The only soft spot is the `since`-poller latency noted above.

### Run Digest

- Response length: 10415 chars
- Response is newline-free: no
- Tool calls made: 12
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 13
- Tokens — prompt / cached / cache write / completion / reasoning: 547066 / 374451 / 172605 / 62042 / not computed
- Duration: 290.1 s
- Cost: $0.33 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13

## Resolution

- **F001** (sweep return value stated two ways): fixed. D6 and Provides to 242 now say `sweep` returns the ids it expired, as a tuple, matching the Risk Assessment wording.
- **F002** (expiry reaches `since` pollers late): fixed. D7 now lists the member's unswept past-TTL `open` requests in `requests` as `expired`, so a poller sees it at once. The `expired` delivery follows when a write, `list` or `status` runs the sweep. The Operator Walkthrough says so, and `inbox` stays a read.
- **F003** (return contract left to 242): fixed. `sweep` and `cancel_member_requests` return the ids they ended, and `reply` and `cancel` return the `RequestView`, whose terminal state says it ended. Only the threading of the `rm` ids out through `apply_removal` stays with 242, its one consumer (D10, Provides). A new technical requirement tests the returned ids.
- **F004** (missing departures): fixed. Departures now lists cancel authority, explicit `member` and `member_mismatch`, and `inbox --since` returning `requests`. It also lists the losing accept naming the time, not the accepter, which follows from cutting the `agent` label (F006). `to_self` is cut, not documented.
- **F005** (config-defaults requirement dropped): fixed. The "No code defaults" departure now says the docs step rewords the architecture's "Store and config" paragraph and the plan's entry 1 criterion to "required, with no default in code; suggested values in the config contract's example".
- **F006** (cuttable mechanisms): fixed. `id` is now required and `Deps.new_id` is gone. The `agent` label is cut: the column, field, flag, limit and the "naming `codex-1`" wording. `to_self` and its reject code are cut.
- **F007** (names on the `inbox` poll): fixed. `RequestView` carries member ids only, and no message operation reads project names. `list` and `status` keep names. `inbox` is now one `cf` call, or two with an explicit `member`.
- **F008** (timeout mapping for names): fixed by removal and restatement. The message operations no longer look up names. The Timeouts paragraph states that `run_cf` returns a `CfCallFailed` value and the lookups map it to `ContextForgeError`, as `resolve_member` and `rm` do.
- **F009** (`list` and `status` write path outside the timing check): partly applied. The handling is stated: `StoreBusyError` from the message sweep is logged and reported in `sweep_problem`, and the call returns, with a test. I did not add `list` and `status` to the worst-case test, because their existing per-run `cf` lookups grow with the number of runs, so no honest bound exists. The Timeouts paragraph says that, and that their timeout advice sends the caller to the CLI. The test covers the four message operations, now 105 s for `send` and 75 s for the others.
- **F010** (pass: core model matches the architecture): no change needed.
- **F011** (pass: dependency direction and integration points): no change needed.
- **F012** (pass: timeout arithmetic): no change needed to the finding, though the arithmetic itself changed with F007 (the names lookup is gone), as stated under F009.
- **F013** (pass: operator walkthrough has no dead end): no change needed, apart from the expiry line, which F002 touched.

No finding needed a deferral, so no GitHub issue was filed and the artifact names none.
