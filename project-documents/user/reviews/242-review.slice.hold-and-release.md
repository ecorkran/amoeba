---
docType: review
layer: project
reviewType: slice
slice: hold-and-release
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/242-slice.hold-and-release.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 21ad20b79dfef22f4ea818650830a90d1329fe47
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
effort: xhigh
turns: 18
promptTokens: 1525989
cachedTokens: 1306758
cacheWriteTokens: 219211
completionTokens: 94456
durationSeconds: 447.5
costUsd: 0.507887
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: pass
    category: architecture
    summary: "Hold, check and resume follow the architecture"
    location: "project-documents/user/slices/242-slice.hold-and-release.md#technical-decisions"
  - id: F002
    severity: pass
    category: boundaries
    summary: "Layering, state placement and config"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:88-92"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Exception handling and exits follow project rules"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:217-218"
  - id: F004
    severity: concern
    category: architecture
    summary: "The check step is a new check, not the answering pipeline's check"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:180-183 and :247"
  - id: F005
    severity: concern
    category: integration
    summary: "Request-end interface contradicts 240; `get_request` duplicates 240's load"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:64 and :249-250"
  - id: F006
    severity: concern
    category: boundaries
    summary: "Private helpers of 223 are called but not listed as interfaces"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:63-66 and :86"
  - id: F007
    severity: concern
    category: error-handling
    summary: "A started child that fails is invisible, and nothing bounds a child that does not exit"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:215-217"
  - id: F008
    severity: concern
    category: nfr
    summary: "Start work per call is unbounded inside operations that 240 bounds against the MCP deadline"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:213-215"
  - id: F009
    severity: concern
    category: operator-walkthrough
    summary: "The walkthrough's dead-end claim is wrong, and the migration gate can loop"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:351 and :368-371"
  - id: F010
    severity: concern
    category: operator-walkthrough
    summary: "Repos that already have the Requesting block never get the marker rule"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:271-272 and :360"
  - id: F011
    severity: concern
    category: proportionality
    summary: "Start-mark compare-and-set is redundant, and the design is heavy for its effort"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:215"
  - id: F012
    severity: note
    category: state-config
    summary: "Retry interval shares a key with claim age"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:214"
  - id: F013
    severity: note
    category: state-config
    summary: "A pruned request reports as `request_unknown`"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:132 and :166"
---

# Review: slice — slice 242

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Hold, check and resume follow the architecture

The marker matches by exact request id (D1). The design keeps one wait on one request. A result that would resume a run goes through the check and the screen, counts toward the per-run answer limit as an `answerer` row, and then resumes through 220/223 unchanged (D5, D6). Declined, cancelled, expired and unknown requests go to `waiting_on_pm` with a reason. `dismiss`, PM `answer`, `run_moved_on` and `run_gone` close a held question (D3, D8). Departures from the architecture are listed. The sweep no longer moves questions, which matches 240 D6.

### [PASS] Layering, state placement and config

Imports keep the `cli/mcp → wiring → operations → store, answering, upstream` direction. `resolve_amoeba_script` moves to a package-root module so `operations` never imports `mcp`, and `Deps` gains an injectable accessor (D7). Scratch and logs live under the existing state helpers. No config key is added (line 214).

### [PASS] Exception handling and exits follow project rules

The two new `except` clauses catch `AmoebaScriptMissing` and `StoreError` by type, log them, and explain in a comment why they are not re-raised (line 256). `LaunchError` is a returned value, and 144 uses `spawn` the same way, so it needs no handler.

### [CONCERN] The check step is a new check, not the answering pipeline's check

The architecture requires the result to go through "the answering pipeline's independent check step". The departure says the check step is "reused as a step of its own pipeline", and D5 says the reply format is reused. But D5 writes new instructions and a new prompt file list (question, request, result, not-authorized). It has no passages, precedence rule or answer. 140's check instructions, and the live proof that the check is independent, cover a different prompt. Either reuse 140's check instructions with only the input changed, or say in the departure that this is a second check, state what its live tests prove, and amend the architecture's trust sentence to match.

### [CONCERN] Request-end interface contradicts 240; `get_request` duplicates 240's load

240's design says `sweep` (D6) and `cancel_member_requests` (D10) return the ids they ended, that `reply` and `cancel` return the `RequestView`, and that "242 starts handle_pause from those." The 240 plan says 242 "reads request state." This design says it does not use those ids, that it "changes no 240 module," and that it reads held rows instead. The held-row approach is the better one, since it also covers expiry and retry. So 240 should drop the return values, which then have no consumer, and its Provides text should change. Line 64 also says 240 "provides no by-id read of one request," but 240's `reply` and `cancel` load a request by id inside their transactions. `get_request` should call that store function, not run a second query.

### [CONCERN] Private helpers of 223 are called but not listed as interfaces

`pause_held` calls `pause_claim._prepare`, `pause_claim._run`, `pause_claim.restart_dead_claim`, `pause_existing._claimed` and `answering_settle`, and D6 changes `_prepare` and `_claimed` to take a request branch. "Interfaces Required" lists only 223's public names, and 223's slice design does not define these functions. Depending on another module's underscore helpers, and changing them, is hidden coupling. Either name them as public 223 interfaces and update 223's design to match, or give 223's module one public entry point that takes the request branch.

### [CONCERN] A started child that fails is invisible, and nothing bounds a child that does not exit

`note_start_failed` covers only a `LaunchError` from spawn and `AmoebaScriptMissing`. A child that starts and then exits before claiming (store error, bad argument, crash) leaves the row `waiting_on_request` with `start_failure` null, and the request already terminal. `status` then shows only "waiting on request … (done)". Every later call starts another child after `answering_wait_seconds`, and the design says nothing about what bounds a child that never exits, so hung children can pile up. 228 D11 already attaches `last_call` to `unhandled` and `claim_stale` runs. Attaching it to held runs whose request has ended and whose start is due would show the failure with no new mechanism. The design should also say what bounds a child that does not exit.

### [CONCERN] Start work per call is unbounded inside operations that 240 bounds against the MCP deadline

240 computes worst cases for `send` (105 s), `reply`, `cancel` and `inbox` (75 s) against `MCP_CALL_DEADLINE_SECONDS` (180 s), and has a test that fails when one reaches it. This design runs `start_ended_held` after `send`, `reply`, `cancel`, `add`, `rm`, `status` and `list`. For each row it starts, it does a read, a write transaction that can wait up to `BUSY_TIMEOUT_SECONDS` (5 s), and a spawn. Nothing caps the rows per call. `rm` of an addressee cancels every open request to it (240 D10), so one call can release many held rows, and the worst case grows past 240's bound. 240's test will not catch this. The design should restate the bound for each affected operation and either cap starts per call (the rest are picked up by the next call, since unattempted rows start first) or move starts out of the caller.

### [CONCERN] The walkthrough's dead-end claim is wrong, and the migration gate can loop

The migration gate says a claim "ends within `answering_wait_seconds` by 223's own rules, so the agent waits and asks again." 223's dead-claim rules run only when a later `handle_pause` sees the claim. A claim whose process died is not revisited by any hook, and `status` does not settle claims, so waiting does not end it. The fix is the command `status` already gives: a `claim_stale` run's `next` is `handle_pause`, so the step should run `amoeba handle-pause <run>` for each one, then re-check. Line 368 has the same gap, since it says 223's rules settle a dead check run without naming the command. Also add a walkthrough failure for a refused resume: the run is `answered_unresumed` with `next = handle_pause` (line 219), and that retry is a manual step the walkthrough omits. "Dead ends found: none" should change once these are fixed.

### [CONCERN] Repos that already have the Requesting block never get the marker rule

The marker rule is one line added to 240's Requesting block, which repos have already pasted. The walkthrough says the rules line is "pasted once into each repo's rules file by an agent in that repo," which covers only repos that have not pasted the block yet. A repo on the old block never writes a marker, so its runs are never held, and nothing reports it: the question goes through ordinary answering. The design should say how the line reaches repos already on the block, and which agents read the `INSTRUCTIONS` line versus the rules file.

### [CONCERN] Start-mark compare-and-set is redundant, and the design is heavy for its effort

`mark_start_attempted` is a compare-and-set so that "two callers never start one row twice." D4 already says a second start loses the claim compare-and-set and "nothing is spent twice." The mark only needs to be a timestamp write, since a duplicate child costs one short process and no spend. Cut the compare-and-set and its test. The plan rates 242 at effort 3 (240 is 5), and this design runs to about 370 lines against about 360 for 240. Most of the size follows from the requirements, but three things can go or shrink: the start compare-and-set; the second `get_request` query (reuse 240's load); and the id return values in 240 that this design does not use (see the integration finding above).

### [NOTE] Retry interval shares a key with claim age

`answering_wait_seconds` already sets 223's wait for a check run and its claim-age test. Reusing it as the start-retry interval adds no key, which is good. But tuning claim age now also changes how often a stuck start is retried. Name that coupling in the config contract's description of the key.

### [NOTE] A pruned request reports as `request_unknown`

If a held row's start keeps failing past `prune_after_days`, 240's prune removes its request. The next start then reports `request_unknown`, although the request was done, and the result is gone. This follows from D2 and is deliberate, but the PM sees a wrong reason. Keeping the request's last state in `waiting_detail` when the row is first seen terminal would avoid the mislabel.

### Run Digest

- Response length: 10686 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 1525989 / 1306758 / 219211 / 94456 / not computed
- Duration: 447.5 s
- Cost: $0.51 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13

## Resolution

- **F001** (pass, hold, check and resume follow the architecture): no change needed.
- **F002** (pass, layering, state placement and config): no change needed.
- **F003** (pass, exception handling and exits): no change needed. D7 still catches only `AmoebaScriptMissing` and `StoreError`, by type.
- **F004** (the check step is a new check): fixed. D5 now says it is a second check and why 140's instructions cannot be reused, what carries over, and what its live test proves (a faithful done gets `yes`; a done that adds an authorization is refused by the check or the screen; a reply that does not settle the question gets `no`). The departure is renamed "A second check, in its own pipeline", and the docs step amends the architecture's sentence to "an independent check step of the same kind". Success Criteria gain the live check test.
- **F005** (request-end interface contradicts 240; `get_request` duplicates 240's load): fixed in both documents. 240's design no longer returns ids from `sweep` and `cancel_member_requests` (D6, D10, the technical requirement and the risk line), names `get_message` as its one by-id read (also used by `reply` and `cancel`), and its "Provides to 242" now says 242 reads request state and changes no 240 module. 242 drops `get_request` and requires `get_message`, and the departure for the start trigger records the 240 amendment.
- **F006** (223 private helpers called but not listed): fixed. Interfaces Required now names `_prepare`, `_run` and `_claimed` as private, and the slice renames them `prepare_claim`, `run_claim` and `handle_claimed` with no behavior change, as the first task of step 4. The 223 and 228 suites must pass unchanged. 223's design is left as the record of that slice as built.
- **F007** (a started child that fails is invisible; nothing bounds a child): fixed. Start and child failures go through the calls log: a `LaunchError` or a missing script appends a line, a failing child writes its own, and `WAITING_ON_REQUEST` joins `MISSED_HOOK_CLASSES` so `status` attaches `last_call` (228 D11) and shows when the last start was attempted. This removed the `start_failure` column and `note_start_failed`. D7 also lists what bounds a child: every wait in `handle_pause` is already bounded, and one row gets a new child at most once per `answering_wait_seconds`.
- **F008** (start work per call unbounded against 240's MCP deadline): fixed. D7 caps starts per call at `MAX_STARTS_PER_CALL` (5), unattempted rows first, and derives `START_BOUND_SECONDS` (30 s). 240's worst-case test adds it to `send`, `reply` and `cancel` and must stay under `MCP_CALL_DEADLINE_SECONDS`. Each started child calls the function at its end, so a large batch drains by itself. `status` and `list` stay outside the bound, as in 240.
- **F009** (walkthrough dead-end claim wrong; migration gate can loop): fixed. The gate now says a dead claim is not revisited by any hook, and runs `amoeba handle-pause <run id>` for each `claim_stale` run that `status` lists, then re-checks, with the reason it terminates. The walkthrough names the same command for a dead check run, adds a refused-resume failure (`answered_unresumed`, `next = handle_pause`), and "Dead ends found" now says two failures end by a command, not "none".
- **F010** (repos with the old Requesting block never get the marker rule): fixed. The rules-line section gives two routes: the MCP `INSTRUCTIONS` text reaches every MCP agent on its next session with no edit, and `docs/program-rules.md` tells a repo on the old block to replace its pasted copy. It states what happens to an agent with neither: the question takes the ordinary answering path and `status` lists it, so the miss is visible. The walkthrough's set-up paragraph says the same.
- **F011** (start-mark compare-and-set redundant; design heavy): fixed. `mark_start_attempted` is a plain write, and D7 says a second child loses the claim compare-and-set. The `start_failure` column, `note_start_failed`, the second `get_request` query and the ids in 240 are gone. I did not cut further: the remaining size follows from requirements.
- **F012** (retry interval shares a key with claim age): fixed. The docs list adds a `config-contract.md` change saying `answering_wait_seconds` is also the least time between two starts for one held question. No key is added.
- **F013** (pruned request reports as `request_unknown`): fixed more simply than the review suggested. The reason stays `request_unknown`, but D4's "No row" paragraph makes the detail say the request existed when the question was held and was pruned after `prune_after_days`, so the PM is not told it never existed. I did not store the request's last state, which would need a write when the row is first seen terminal.

No finding was deferred, so no GitHub issue was filed.

**Second pass 20261115.** Some entries above were redone in the design during a second resolution pass. Where this section and the design disagree, the design governs.
