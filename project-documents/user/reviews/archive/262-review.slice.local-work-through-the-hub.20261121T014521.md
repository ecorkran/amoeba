---
docType: review
layer: project
reviewType: slice
slice: local-work-through-the-hub
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/262-slice.local-work-through-the-hub.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: 7eae4b753a19cb3f7db771fbf9bb33d7e86a75dd
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
effort: xhigh
turns: 10
promptTokens: 804509
cachedTokens: 577311
cacheWriteTokens: 227186
completionTokens: 100298
durationSeconds: 452.8
costUsd: 0.493989
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: scope
    summary: "Cross-machine presence is deferred to slice 263"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:547"
  - id: F002
    severity: concern
    category: state-exit
    summary: "Dead-claim restarts have no count and re-run the answering model"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:260"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Oversized step documents and the new `open_runs` call have no stated failure outcome"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:159"
  - id: F004
    severity: concern
    category: error-handling
    summary: "A resume whose first attempt succeeded is recorded as `not_delivered`"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:410"
  - id: F005
    severity: concern
    category: under-specification
    summary: "The work flag's resume clause does not say a stale claim counts"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:367"
  - id: F006
    severity: concern
    category: error-handling
    summary: "A config failure makes the work flag silently false"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:374"
  - id: F007
    severity: concern
    category: state-exit
    summary: "A wake that failed to start blocks the request's later wakes"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:329"
  - id: F008
    severity: concern
    category: architecture
    summary: "The wake rule departs from the architecture on the live install"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:494"
  - id: F009
    severity: concern
    category: consistency
    summary: "The walkthrough and D10 state recovery rules that D5 and D11 contradict"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:694"
  - id: F010
    severity: concern
    category: consistency
    summary: "The MCP deadline check is tied to the wrong limit"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:541"
  - id: F011
    severity: concern
    category: process
    summary: "Migration 013 timing contradicts the plan and slice 261, and open MCP sessions are not covered"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:457"
  - id: F012
    severity: concern
    category: nfr
    summary: "No latency target for the paths this slice changes"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:489"
  - id: F013
    severity: concern
    category: integration
    summary: "`here` cannot carry `logs_dir` for `claim_work` in 261's shapes"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:518"
  - id: F014
    severity: concern
    category: proportionality
    summary: "One method per step on two implementations is heavier than needed"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:196"
  - id: F015
    severity: note
    category: dependency
    summary: "Prerequisite pins are inconsistent"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:76"
  - id: F016
    severity: note
    category: docs
    summary: "Frontmatter date is after today"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:13"
  - id: F017
    severity: pass
    category: architecture
    summary: "Hub clock and transaction placement follow the architecture"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:170-189"
  - id: F018
    severity: pass
    category: scope
    summary: "Scope matches the slice plan apart from presence"
    location: "project-documents/user/slices/262-slice.local-work-through-the-hub.md:49-70"
---

# Review: slice — slice 262

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Cross-machine presence is deferred to slice 263

The wake rule requires "no live session in the member on any machine" (D8, line 330). The plan puts "`send` checks presence across machines" in 262 (260-slices, line 93). But Integration Points says session rows from other machines come from 263 (line 547), and D15 keeps `amoeba-mcp` from starting on a joined machine. So in 262 the check reads only seeded rows. The Amoeba design rules reject a design that defers in-scope behavior. Either build the session write this slice needs, or remove the cross-machine clause from D8 and state what a wake does while a session is live on another machine.

### [CONCERN] Dead-claim restarts have no count and re-run the answering model

The work flag makes the restart of a stale `claimed` row automatic. Once the claim is stale, every call from that machine raises the flag, and a new answering run starts each `answering_wait_seconds`. A settle that is refused every time repeats until someone runs `dismiss`. D3's own example (an authorize key the config lacks) produces that refusal. The walkthrough accepts the same loop for `sq` (line 696). The design needs a restart count, and a stated terminal state when it is reached, such as `question_wait` with a reason.

### [CONCERN] Oversized step documents and the new `open_runs` call have no stated failure outcome

`question_settle` carries "the answer, what it cites and the evidence" (D1). The door refuses bodies over 1 MiB before reading them (260, `MAX_CALL_BYTES`). That refusal is deterministic, so with the finding above it loops. Separately, `status` and `list` now call `open_runs` before their own call (D9, line 354). `open_runs` reads `prune_after_days` from the config (D4), so `status` can fail on a config error before its own call runs. Neither failure is described. Give the size limit a handling rule, and say what `status` does when `open_runs` fails.

### [CONCERN] A resume whose first attempt succeeded is recorded as `not_delivered`

If the first `resume-run` resumed the run and its `resume_record` was lost, the second attempt "finds it past the pause and records `not_delivered`" (D11; D6, line 295). The answer was delivered, so `list` would show a delivered answer as not delivered. Say how a claim that ran out tells "resumed by an earlier attempt" from "run moved on", and record `resumed` in the first case.

### [CONCERN] The work flag's resume clause does not say a stale claim counts

The clause reads "no claim in flight (D6)". D6 hands a claim out again once `resume_started_at` is older than `resume_claim_seconds`. If the flag reads only "no claim id set", a lost claim never raises the flag, and success criterion line 557 fails. State that the flag uses the same stale test as `claim_resume`.

### [CONCERN] A config failure makes the work flag silently false

If `config.yaml` will not load, the flag is false, and the only sign is a line in the hub log. Core Principles forbid silent fallback values. Any operation that does not read the config returns success while held or resume work waits. The architecture promises that a bad edit fails calls with the file and key named (Config); the flag path does not. Have the reply say that the state is unknown, and list which work-creating operations read the config.

### [CONCERN] A wake that failed to start blocks the request's later wakes

Rule 2 counts any wake that "has ended". A `start_failed` wake has ended, so it counts, and the request is never woken again, even after the checkout is fixed. That contradicts "at most one wake that ran" (line 657) and D8's own rule that a claim which never ran does not count. The walkthrough covers the missing checkout with `dismiss` and `rm --checkout` (line 692), and says nothing about waking once a checkout is restored. Count only wakes that set a pid, and say what `start_failed` does to the request.

### [CONCERN] The wake rule departs from the architecture on the live install

The architecture makes the wake a `send`-time decision. If no machine asks, "the request waits for the next agent or its expiry" (architecture, Waking). This design derives the wake from records on every call. A request sent while a session was live is woken once that session goes stale, and any later call from a machine with the checkout fires it. The design's own risk section says the live install's wake behavior changes (line 650). The departure is recorded, but the PM has not decided it. Take it to the PM first, or keep the `send`-time decision and let the other machine claim a wake row created at `send`.

### [CONCERN] The walkthrough and D10 state recovery rules that D5 and D11 contradict

- Line 694: after a hub stop mid-`handle-pause`, "Nothing needs doing", and the next call restarts it. That holds only once `question_insert` has applied. D11 (line 409) says a run with no row shows as paused with no record and needs its command. The work flag covers rows only.
- Line 695: a `handle-pause` is handed out "after `answering_wait_seconds`". D5 (line 266) sets `answering_wait_seconds + 2 * CALL_BOUND_SECONDS`.
- D10 (line 384) gives `answering_wait_seconds` as a claim's limit. That value is the start mark's cooldown.
- Line 704 says "Dead ends found: none". The first item above is one.

### [CONCERN] The MCP deadline check is tied to the wrong limit

D6 (line 280) keeps `resume_bound_seconds` unchanged for the MCP deadline check. Integration Points (line 541) says 263's check is worked out from `resume_claim_seconds` and the network times. The architecture says the check uses the config value with the network times added (Architecture, Repeats and failures). `resume_claim_seconds` already includes the network times, so using it would count them twice. Name `resume_bound_seconds` on line 541.

### [CONCERN] Migration 013 timing contradicts the plan and slice 261, and open MCP sessions are not covered

D14 migrates the live store "when the release runs". The plan says each schema change lands on the local store as it comes (260-slices, line 27). Slice 261 (line 430) runs `update_live.py update` right after the merge, and it requires restarting open `amoeba-mcp` sessions, because an old server refuses the newer schema. Migration 013 has the same effect, and this design does not mention it. Use 261's timing, and add the session restart to the notes and the walkthrough.

### [CONCERN] No latency target for the paths this slice changes

The architecture states that "a CLI call is a `cf` call plus one round trip" (Latency). This slice turns `answer`, `handle-pause`, `send`, `list` and `status` into several door calls. `answer` can make three (the answer, the resume's record, and the after-step's `claim_work`). `handle-pause` can make up to eight. `list` and `status` make two. The departures row says "a pause costs fewer round trips" with no figure. Restate each path's call count and bound, as 261 did for its operations.

### [CONCERN] `here` cannot carry `logs_dir` for `claim_work` in 261's shapes

261 allows `here` in three shapes: `{project_id}`, `{project_id, name, path, origin}`, or `{not_a_project}` (261, API Contracts). This design adds `logs_dir` to `here` for `send` and `claim_work`. `claim_work` has no directory, so its `here` would be `{logs_dir}`, which none of the shapes allows. Say whether `logs_dir` is a sibling body key, and what `claim_work` sends.

### [CONCERN] One method per step on two implementations is heavier than needed

`Steps` has 16 methods. Each is written in the protocol, in `LocalSteps` and in `DoorSteps`, with 16 request and 16 reply models beside them. Each method only passes through to `run_step`, which already dispatches by name. A single typed call, `Steps.run(step, request)`, with one name-to-model table in `wire.protocol`, keeps each step name in one place and still checks the models. The Verification Walkthrough (lines 594–641) repeats the criteria and can be reduced to a pointer.

### [NOTE] Prerequisite pins are inconsistent

This design pins both 260 and 261 to `9a9b4d21`, which is slice 261's round-two commit. Slice 261 pins 260 at `729b57fb`. Pin each slice at its own commit. Both designs are still in review, and 261's latest round is FAIL.

### [NOTE] Frontmatter date is after today

`dateUpdated: 20261121`. Today is 20261120.

### [PASS] Hub clock and transaction placement follow the architecture

D1 moves each check that runs inside a transaction to the hub. D2 gives every store function a hub clock, and bars time fields from step requests, with a test to hold it. Both match the architecture's "hub's clock" and "one call is one transaction" principles.

### [PASS] Scope matches the slice plan apart from presence

Each 262 bullet in the plan maps to a decision: the two checks (D1, D2), the pause path and sweeps (D4, D5, D9), answer and resume claim (D6, D7), waking (D8), the work flag and claim (D10), unknown outcomes (D11), clean-up (D12), and `rm-machine` (D13). The exclusions are the items the plan gives to 263 and 264. The stated import rules keep client-run modules off the store.

### Run Digest

- Response length: 11405 chars
- Response is newline-free: no
- Tool calls made: 9
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 10
- Tokens — prompt / cached / cache write / completion / reasoning: 804509 / 577311 / 227186 / 100298 / not computed
- Duration: 452.8 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 18
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 18
- Finding-shaped matches — surviving validation: 18
