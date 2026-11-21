---
docType: review
layer: project
reviewType: slice
slice: sessions-across-machines
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/263-slice.sessions-across-machines.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: 78c71be7cb17d4a05b5dd8d16bb6dafbdefa30e7
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
effort: xhigh
turns: 21
promptTokens: 2095076
cachedTokens: 1845825
cacheWriteTokens: 249227
completionTokens: 106454
durationSeconds: 488.1
costUsd: 0.594901
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "The cf lookup has no timeout, so a hang stops presence silently"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:196"
  - id: F002
    severity: concern
    category: error-handling
    summary: "After-step outcomes are not enumerated"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:267"
  - id: F003
    severity: concern
    category: error-handling
    summary: "`machine_runs` has no stated failure modes or limit behaviour"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:334-346"
  - id: F004
    severity: concern
    category: traceability
    summary: "Integration criterion contradicts D3 for sessions started outside a project"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:521"
  - id: F005
    severity: concern
    category: operations
    summary: "The operator walkthrough omits the Codex timeout step, and the 300 deadline rests on unchecked client facts"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:625-646"
  - id: F006
    severity: concern
    category: traceability
    summary: "The \"corrected\" 216.5 cites a figure that 262 does not contain"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:88"
  - id: F007
    severity: concern
    category: integration
    summary: "263 changes 262's after-step contract without listing it as an amendment"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:269"
  - id: F008
    severity: concern
    category: scope
    summary: "Dead served check and speculative consumers should be cut now"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:393"
  - id: F009
    severity: note
    category: integration
    summary: "`session_tick` writes but is classified as non-writing"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:186"
  - id: F010
    severity: note
    category: integration
    summary: "`TICK_SECONDS_BEFORE_FIRST_REPLY` is a client-held interval"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:156"
  - id: F011
    severity: note
    category: traceability
    summary: "\"The one live rule\" is two predicates"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:385"
  - id: F012
    severity: note
    category: traceability
    summary: "Behind sessions from an old program after an upgrade are not listed"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:426"
  - id: F013
    severity: note
    category: traceability
    summary: "Runs on other machines go beyond the architecture but match the plan"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:331-340"
  - id: F014
    severity: pass
    category: traceability
    summary: "Scope from the plan entry is covered"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md#success-criteria"
---

# Review: slice — slice 263

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] The cf lookup has no timeout, so a hang stops presence silently

D3 says a `cf` call that "fails or times out" yields no answer, but it gives no timeout value. D1 runs ticks one at a time with no overlap, so one hung `cf` call stops every tick. Nothing is refreshed, the session drops out of `list` after `session_stale_seconds`, and no WARNING is logged, because D4 logs only failures that return. D10 also makes `resources/read` wait on `PresenceState.resolved` (line 206), which is set only when the first tick ends, so the resource handlers would hang too. The plan's failure-mode rule requires an explicit bound and handling for every I/O path. Name the `cf` timeout as a constant or setting, and say what the tick and `resolved` do when it fires.

### [CONCERN] After-step outcomes are not enumerated

`after_runner` runs 262's `claim_work` (a writing call that can take up to one call bound) and then starts work detached. D7 gives no outcome for an unknown or refused claim, for a spawn failure, or for an exception in the worker thread. It also does not say whether such an exception ends presence, which D4 does for tick exceptions. The architecture requires that a command that runs by itself, on an unknown result, stops at that step, logs the error, and never guesses; the claim then expires and the work is handed out again. Enumerate each outcome with its handling.

### [CONCERN] `machine_runs` has no stated failure modes or limit behaviour

D11 adds a new read and write path for another machine's run document. Not stated: what the hub does with a malformed document; what happens when a document exceeds `RUNS_DOCUMENT_MAX_BYTES`, which line 143 cites as the bound but which no one enforces in the text; what happens when a stored document from an older version fails to parse; and whether a failure while placing another machine's document fails the whole `status` call or only drops that machine's section. Every limit needs its hit behaviour, and every new I/O path needs its failures listed.

### [CONCERN] Integration criterion contradicts D3 for sessions started outside a project

The integration requirement says a repo added after its session started gets presence at the next tick. D3 (line 204) says a directory that `cf` reports as not a project stays that way for the process, and the walkthrough (line 633) requires a reconnect. Line 200 and the departures row at line 422 overstate the rule in the same way. The success criterion at line 494 covers only a directory that is a project but not a member, so it does not cover this case. Either re-ask `cf` for a not-a-project directory at a named interval, or carve the case out of lines 200, 422 and 521 and state the cost reason for stopping.

### [CONCERN] The operator walkthrough omits the Codex timeout step, and the 300 deadline rests on unchecked client facts

D14 (line 397) and the departures row (line 425) say Codex users must set `tool_timeout_sec` to at least 305. The walkthrough never mentions this. Without it, an answer that the hub accepts and resumes can be cut off by the client, and the agent sees a timeout; the walkthrough lists no step or guidance for that. The facts section (lines 76-79) checks Claude Code, `mcp`, `cf` and `sq`, but not the client timeouts the 300 figure depends on. The existing MCP doc gives Codex a 60-second default, which I could not verify here. Add the step to the walkthrough and list the client timeouts as checked facts.

### [CONCERN] The "corrected" 216.5 cites a figure that 262 does not contain

The design says 262 D6 gives 226.5 for `resume_claim_seconds`. The 262 design at its current revision contains no 226.5. Its stated rule (around its line 555) replaces the one store wait with 2 × `CALL_BOUND_SECONDS`, which yields 216.5. So the design's figure follows 262's own rule, and it is not a correction to 262's arithmetic. The architecture (line 189) says the claim allows the retry time in place of the store wait, which would give 160.5. 262 records that as a departure, and this design should cite that departure. The current answer bound also adds three store waits (`ANSWER_STORE_WAITS`); the design drops two of them without saying why. Through the door they are no longer opened locally, which the design should state.

### [CONCERN] 263 changes 262's after-step contract without listing it as an amendment

262 (line 424) says the after-step runs at the end of `wiring.invoke` for every operation. 263 changes `invoke` so the MCP door leaves it to the tick, and the component table (line 105) says `invoke` "can leave the after-step to its caller." The departures table (line 427) records this against the plan and the architecture, not against 262. The "Consumes from 262" list (line 85) treats the after-step as unchanged. Also, the tests and success criteria use `amoeba leave` and `join --set-aside-local`, which are 260's (260 lines 53 and 232), but line 85 does not list them under the interfaces required from 260. List 263's changes to 262 and 260 as amendments in both documents' terms.

### [CONCERN] Dead served check and speculative consumers should be cut now

After 262, `handle-pause` and `wake-run` no longer raise `NotServedError` (262 line 112). This slice then states that no entry point raises it (line 393), yet it keeps the error and the served check "for 264 to delete." Nothing calls them, so they are dead code. 264's plan entry names the mode switch and the local-store path, not this check. Delete `NotServedError` and the served check here. The "Provides" entries for 300's runner (line 470) and 264's set-up page (line 469) are not requirements of 263's plan entry, which has effort 2 of 5; move them to 300's and 264's designs. The rest of the design's size is largely plan- or architecture-required, so these two cuts are the ones I'd make.

### [NOTE] `session_tick` writes but is classified as non-writing

Line 186 keeps `session_tick` out of `WRITING_STEPS` because it is idempotent and never repeated. I checked the idempotence: the due rule and the once-only `push_confirmed_at` stamp hold on a second run. The classification depends on the tick's retry being zero (line 211). Pin that dependency in a test against `TICK_TIMES`, and say so in the design.

### [NOTE] `TICK_SECONDS_BEFORE_FIRST_REPLY` is a client-held interval

The architecture (line 175) says the hub's config is the only config for the timeouts a client-run command needs. This constant is the one interval the client holds. It is small and used only before the first reply, but the design should either take it from the reply or justify holding it.

### [NOTE] "The one live rule" is two predicates

Line 385 says the one live rule becomes "a fresh heartbeat and a door version." Line 252 requires `live_member_ids` to count only rows with the hub's door version, which is a different predicate. The component table (line 101) already says "the live rule and the waking rule." Name both predicates in D13.

### [NOTE] Behind sessions from an old program after an upgrade are not listed

The architecture (line 270) requires `list` and `hub machines` to show which sessions are behind. This design lists the machine but not sessions that started after the upgrade. The reason holds: the hub cannot create a row from headers alone, and the header is new in this slice. The departures row records it, and the walkthrough (line 639) gives the machine-level exit. I accept the departure but note that an operator cannot find those sessions from `list`.

### [NOTE] Runs on other machines go beyond the architecture but match the plan

The plan (line 125 of the slice plan) asks for runs on other machines to show as last reported with the machine named. The architecture (line 207) limits this to questions. The design follows the plan, records the departure, and judges other machines' open questions on the hub from a stored copy, which the architecture did not contemplate. The departure is recorded, so I accept it. The staleness is shown by age.

### [PASS] Scope from the plan entry is covered

Every bullet of the plan's 263 entry (one tick, the directory and migration, tools through the door with the hub-side deadline and no wake field, runs on other machines, unchanged channel event) and all seven of its success criteria map to a decision and a criterion in this design.

### Run Digest

- Response length: 12589 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 21
- Tokens — prompt / cached / cache write / completion / reasoning: 2095076 / 1845825 / 249227 / 106454 / not computed
- Duration: 488.1 s
- Cost: $0.59 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
