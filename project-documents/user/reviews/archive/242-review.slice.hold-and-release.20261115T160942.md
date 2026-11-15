---
docType: review
layer: project
reviewType: slice
slice: hold-and-release
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: derived
sourceDocument: project-documents/user/slices/242-slice.hold-and-release.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 442347a7a4ac8866305e61df429b297bce74b6ba
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 15
effort: xhigh
turns: 16
promptTokens: 1538082
cachedTokens: 1331155
cacheWriteTokens: 206907
completionTokens: 56079
durationSeconds: 273.4
costUsd: 0.401201
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: fail
    category: completeness
    summary: "A lost release trigger has no automatic recovery, which defers in-scope behavior"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:215"
  - id: F002
    severity: concern
    category: dependencies
    summary: "The migration order conflicts with the slice plan, and the design gives two numberings"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:60"
  - id: F003
    severity: concern
    category: scope
    summary: "Held-question paths duplicate 223's claim, scratch and dead-claim restart logic"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:344"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure handling for the hold insert and the scratch write is not stated"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:277"
  - id: F005
    severity: concern
    category: error-handling
    summary: "The release's catch breaks the exception rule and names no exception types"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:251"
  - id: F006
    severity: concern
    category: dependencies
    summary: "A request read the design needs is missing from 240's provided interfaces"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:64"
  - id: F007
    severity: note
    category: completeness
    summary: "Crash of a held claim is covered by 223's dead-claim status, but the design does not say so"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:344"
  - id: F008
    severity: note
    category: rules
    summary: "The Squadron truncation fact behind the last-line rule is undated"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:120"
  - id: F009
    severity: pass
    category: consistency
    summary: "Hold, check, screen, resume and exits match the architecture"
    location: "project-documents/user/slices/242-slice.hold-and-release.md#technical-decisions"
---

# Review: slice — slice 242

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] A lost release trigger has no automatic recovery, which defers in-scope behavior

D7 says a failed or lost release start is left for `status` to show (`next = handle_pause`), and that "No timer and no retry loop is added: a lost trigger is rare." The Departures list repeats this at line 246. The architecture and the plan both say Amoeba starts `handle_pause` for each run waiting on a request that ends. The rarity argument for not building the mechanism is the "build only if use shows it's needed" pattern that the Amoeba design rules prohibit, and a review must reject it.

The fix is cheap and needs no new process. The design already runs `sweep_messages` in `status`, `list`, `send`, `reply`, `cancel` and `handle_pause`. At the same post-commit point, `release_held` can also start `handle_pause` for every `waiting_on_request` row whose request is terminal, not only the rows whose request ended in this call. A lost or failed trigger is then re-driven by the next call of any of those commands. Repeated spawn failures are bounded by how often those calls happen, and the design should say so. The `status` fallback can then go, and the "Dead ends found: none" claim at line 361 becomes true.

Walkthrough result: the normal, declined, expired, `rm`, `request_unknown`, answer-limit and check-no paths all reach an exit. The one dead end is a failed release, which waits on a person reading `status`.

### [CONCERN] The migration order conflicts with the slice plan, and the design gives two numberings

Line 60 requires 241's migration 7 to apply first. It also says that if 241 is not built, this migration "takes the next free number and the live-store step follows it." Elsewhere the design hard-codes `008_waiting_on_request.sql`, `EXPECTED_SCHEMA_VERSION` 8, the `pre-008` backup and "migrated to 8" (lines 127–133, 346, 295). The slice plan says 242 depends on 240 only and is "Independent of 241" (plan entry 242), with build order 240 → 241 → 242. The 241 design hard-codes migration 7 and "migrated to 7." If 242 were built first and took 7, 241's numbers would break. The frontmatter at lines 6–7 lists only 240.

Resolve it one way. Either make build order a stated requirement (241 before 242), list 241 in the frontmatter, and ask the PM to amend the plan's "Independent of 241." Or number migrations at task time and make 241's document match.

### [CONCERN] Held-question paths duplicate 223's claim, scratch and dead-claim restart logic

The design adds `restart_held_claim` (re-read the request, new scratch, compare-and-set run-id swap, run again), `claim_held` (the compare-and-set from `waiting_on_request` to `claimed`), a `request_scratch` module, and a `Claim.candidate` branch. 223 already handles a `claimed` claim whose run is not found and is old: gather again, new scratch under a new id, replace the claim by compare-and-set, spawn. The design also says it reuses `start_new_claim`'s shape. The rule against duplicated logic applies here.

`restart_held_claim` also has no count. A claim whose run never appears is restarted on every `handle_pause` call, and the design gives no limit, which the "every limit says what happens when hit" rule requires.

Proposed cut: route held claims through 223's existing `claimed` path and its `replace_claim`. The only held-specific step is "gather again": read the request, and a missing request moves the question to `waiting_on_pm` with `request_unknown`. Write the scratch with 223's writer and a candidate input, not a parallel module. Keep `claim_held` only if 223's start path cannot take the candidate.

### [CONCERN] Failure handling for the hold insert and the scratch write is not stated

Line 277 says a store error reading a request makes `handle_pause` exit 3 "with the question left as it was." But D4 (line 152) inserts the held row first, in its own write. A first-time hold that then fails on the read leaves a committed `waiting_on_request` row, so "left as it was" is wrong. The design should say the row stays, and that the next `handle_pause` finds it and takes `handle_held`.

Two more I/O steps have no stated outcome. A scratch write failure in `request_scratch.prepare` (line 177) is not in the reused reasons list (line 237). A failure reading request states for `status` (D9, line 229) is also unstated. Each new I/O step needs its failure outcome and reason named.

### [CONCERN] The release's catch breaks the exception rule and names no exception types

Line 251 says "No new try/except that swallows," then describes a release that "logs a failed start with `logger.exception` and carries on." Under the project rule, a catch must re-raise after logging, catch a named exception with a comment explaining why swallowing is correct, or sit at a process boundary. As written it is none of these. Line 214 lists "`LaunchError`, the script missing, the checkout gone," which is not a single type. A missing working directory raises an OS error from the spawn, not `LaunchError`.

Name the exception types the spawn can raise, catch them in one place with the comment, and state why continuing past one failed run is correct: that run's question state is its record.

### [CONCERN] A request read the design needs is missing from 240's provided interfaces

Line 64 names a by-id read of one request as a 240 interface, then hedges: "if 240's build has no such reader, the first task adds `get_message` there." 240's design lists what it provides to 242 (`RequestView`, `effective_state`, `sweep`, `cancel_member_requests`, `reply`, `cancel`) and no by-id read. The hedge moves a 240 gap into 242's first task, and into a store module 240 owns. Add the reader to 240's provided interfaces and have 242 consume it without an alternative.

### [NOTE] Crash of a held claim is covered by 223's dead-claim status, but the design does not say so

D7's fallback covers only `waiting_on_request` rows. If the process dies after a claim commits, the held row is `claimed` with no release pending. 223's status already reports dead claims with `next = handle_pause`, so an exit exists. Stating that the held claim uses it would back the walkthrough's "none" claim.

### [NOTE] The Squadron truncation fact behind the last-line rule is undated

The last-line placement rests on Squadron keeping only the tail of the reply, starting with `…`. The design gives no probe or version for this, unlike the `sq run --validate` probe at line 61. The Amoeba rule asks for facts about other tools to be dated and verified when written. Probe and date it, or note that the matcher reads the whole text, so the last-line rule is only guidance.

### [PASS] Hold, check, screen, resume and exits match the architecture

The exact-id link (the architecture leaves its form to this slice) and the held-state table match the architecture's "Holding a paused run" section. A `done` result goes through the check and the screen, counts toward the answer limit, and resumes through 220's procedure. Declined, cancelled and expired requests go to `waiting_on_pm` with a reason. `dismiss`, `run_moved_on` and `run_gone` are the exits. The prior architecture review's F004 (check and screen on results), F005 (race and retry) and F006 (PM exit for held questions) are each answered. The release lives in operations, script resolution in wiring, and the store does not import operations. The no-transaction-across-a-subprocess test at line 297 restates the architecture's write-lock rule. The departures from the parents are listed.

### Run Digest

- Response length: 8905 chars
- Response is newline-free: no
- Tool calls made: 15
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 16
- Tokens — prompt / cached / cache write / completion / reasoning: 1538082 / 1331155 / 206907 / 56079 / not computed
- Duration: 273.4 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

### Raw Response

## Summary

**Verdict: FAIL.** The slice follows the architecture's hold, check, screen, resume and exit model closely. One design choice breaks the project's no-deferral rule: when a release trigger is lost, the design leaves recovery to a person running a command. Several CONCERN items also need resolving before implementation: the migration order conflicts with the slice plan, held-claim paths duplicate 223's existing logic, and some failure paths and the exception handling are not specified.

## Findings

### [FAIL] A lost release trigger has no automatic recovery, which defers in-scope behavior
location: project-documents/user/slices/242-slice.hold-and-release.md:215
category: completeness

D7 says a failed or lost release start is left for `status` to show (`next = handle_pause`), and that "No timer and no retry loop is added: a lost trigger is rare." The Departures list repeats this at line 246. The architecture and the plan both say Amoeba starts `handle_pause` for each run waiting on a request that ends. The rarity argument for not building the mechanism is the "build only if use shows it's needed" pattern that the Amoeba design rules prohibit, and a review must reject it.

The fix is cheap and needs no new process. The design already runs `sweep_messages` in `status`, `list`, `send`, `reply`, `cancel` and `handle_pause`. At the same post-commit point, `release_held` can also start `handle_pause` for every `waiting_on_request` row whose request is terminal, not only the rows whose request ended in this call. A lost or failed trigger is then re-driven by the next call of any of those commands. Repeated spawn failures are bounded by how often those calls happen, and the design should say so. The `status` fallback can then go, and the "Dead ends found: none" claim at line 361 becomes true.

Walkthrough result: the normal, declined, expired, `rm`, `request_unknown`, answer-limit and check-no paths all reach an exit. The one dead end is a failed release, which waits on a person reading `status`.

### [CONCERN] The migration order conflicts with the slice plan, and the design gives two numberings
location: project-documents/user/slices/242-slice.hold-and-release.md:60
category: dependencies

Line 60 requires 241's migration 7 to apply first. It also says that if 241 is not built, this migration "takes the next free number and the live-store step follows it." Elsewhere the design hard-codes `008_waiting_on_request.sql`, `EXPECTED_SCHEMA_VERSION` 8, the `pre-008` backup and "migrated to 8" (lines 127–133, 346, 295). The slice plan says 242 depends on 240 only and is "Independent of 241" (plan entry 242), with build order 240 → 241 → 242. The 241 design hard-codes migration 7 and "migrated to 7." If 242 were built first and took 7, 241's numbers would break. The frontmatter at lines 6–7 lists only 240.

Resolve it one way. Either make build order a stated requirement (241 before 242), list 241 in the frontmatter, and ask the PM to amend the plan's "Independent of 241." Or number migrations at task time and make 241's document match.

### [CONCERN] Held-question paths duplicate 223's claim, scratch and dead-claim restart logic
location: project-documents/user/slices/242-slice.hold-and-release.md:344
category: scope

The design adds `restart_held_claim` (re-read the request, new scratch, compare-and-set run-id swap, run again), `claim_held` (the compare-and-set from `waiting_on_request` to `claimed`), a `request_scratch` module, and a `Claim.candidate` branch. 223 already handles a `claimed` claim whose run is not found and is old: gather again, new scratch under a new id, replace the claim by compare-and-set, spawn. The design also says it reuses `start_new_claim`'s shape. The rule against duplicated logic applies here.

`restart_held_claim` also has no count. A claim whose run never appears is restarted on every `handle_pause` call, and the design gives no limit, which the "every limit says what happens when hit" rule requires.

Proposed cut: route held claims through 223's existing `claimed` path and its `replace_claim`. The only held-specific step is "gather again": read the request, and a missing request moves the question to `waiting_on_pm` with `request_unknown`. Write the scratch with 223's writer and a candidate input, not a parallel module. Keep `claim_held` only if 223's start path cannot take the candidate.

### [CONCERN] Failure handling for the hold insert and the scratch write is not stated
location: project-documents/user/slices/242-slice.hold-and-release.md:277
category: error-handling

Line 277 says a store error reading a request makes `handle_pause` exit 3 "with the question left as it was." But D4 (line 152) inserts the held row first, in its own write. A first-time hold that then fails on the read leaves a committed `waiting_on_request` row, so "left as it was" is wrong. The design should say the row stays, and that the next `handle_pause` finds it and takes `handle_held`.

Two more I/O steps have no stated outcome. A scratch write failure in `request_scratch.prepare` (line 177) is not in the reused reasons list (line 237). A failure reading request states for `status` (D9, line 229) is also unstated. Each new I/O step needs its failure outcome and reason named.

### [CONCERN] The release's catch breaks the exception rule and names no exception types
location: project-documents/user/slices/242-slice.hold-and-release.md:251
category: error-handling

Line 251 says "No new try/except that swallows," then describes a release that "logs a failed start with `logger.exception` and carries on." Under the project rule, a catch must re-raise after logging, catch a named exception with a comment explaining why swallowing is correct, or sit at a process boundary. As written it is none of these. Line 214 lists "`LaunchError`, the script missing, the checkout gone," which is not a single type. A missing working directory raises an OS error from the spawn, not `LaunchError`.

Name the exception types the spawn can raise, catch them in one place with the comment, and state why continuing past one failed run is correct: that run's question state is its record.

### [CONCERN] A request read the design needs is missing from 240's provided interfaces
location: project-documents/user/slices/242-slice.hold-and-release.md:64
category: dependencies

Line 64 names a by-id read of one request as a 240 interface, then hedges: "if 240's build has no such reader, the first task adds `get_message` there." 240's design lists what it provides to 242 (`RequestView`, `effective_state`, `sweep`, `cancel_member_requests`, `reply`, `cancel`) and no by-id read. The hedge moves a 240 gap into 242's first task, and into a store module 240 owns. Add the reader to 240's provided interfaces and have 242 consume it without an alternative.

### [NOTE] Crash of a held claim is covered by 223's dead-claim status, but the design does not say so
location: project-documents/user/slices/242-slice.hold-and-release.md:344
category: completeness

D7's fallback covers only `waiting_on_request` rows. If the process dies after a claim commits, the held row is `claimed` with no release pending. 223's status already reports dead claims with `next = handle_pause`, so an exit exists. Stating that the held claim uses it would back the walkthrough's "none" claim.

### [NOTE] The Squadron truncation fact behind the last-line rule is undated
location: project-documents/user/slices/242-slice.hold-and-release.md:120
category: rules

The last-line placement rests on Squadron keeping only the tail of the reply, starting with `…`. The design gives no probe or version for this, unlike the `sq run --validate` probe at line 61. The Amoeba rule asks for facts about other tools to be dated and verified when written. Probe and date it, or note that the matcher reads the whole text, so the last-line rule is only guidance.

### [PASS] Hold, check, screen, resume and exits match the architecture
location: project-documents/user/slices/242-slice.hold-and-release.md#technical-decisions
category: consistency

The exact-id link (the architecture leaves its form to this slice) and the held-state table match the architecture's "Holding a paused run" section. A `done` result goes through the check and the screen, counts toward the answer limit, and resumes through 220's procedure. Declined, cancelled and expired requests go to `waiting_on_pm` with a reason. `dismiss`, `run_moved_on` and `run_gone` are the exits. The prior architecture review's F004 (check and screen on results), F005 (race and retry) and F006 (PM exit for held questions) are each answered. The release lives in operations, script resolution in wiring, and the store does not import operations. The no-transaction-across-a-subprocess test at line 297 restates the architecture's write-lock rule. The departures from the parents are listed.
