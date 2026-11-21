---
docType: review
layer: project
reviewType: slice
slice: sessions-across-machines
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/263-slice.sessions-across-machines.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: 9840b0bfef4cf251901aaa9ee4a38ea403a6c543
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
effort: xhigh
turns: 11
promptTokens: 853800
cachedTokens: 642569
cacheWriteTokens: 211219
completionTokens: 85380
durationSeconds: 382.9
costUsd: 0.443731
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: architecture-alignment
    summary: "MCP `answer` resume is both skipped and budgeted in the call"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:276"
  - id: F002
    severity: concern
    category: architecture-alignment
    summary: "`session_tick` writes rows but sits outside `WRITING_STEPS`"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:191"
  - id: F003
    severity: concern
    category: scope
    summary: "The plan's \"list shows it as behind\" criterion is dropped for sessions started after an upgrade"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:261"
  - id: F004
    severity: concern
    category: integration
    summary: "Amendments to 262 omit three changes and leave a wrong figure"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:464-475"
  - id: F005
    severity: concern
    category: dry
    summary: "`answer_call_bound_seconds` duplicates `resume_claim_seconds`, and the limits lack their formula"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:322-328"
  - id: F006
    severity: concern
    category: proportionality
    summary: "D11 is heavier than the plan asks for"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:348-374"
  - id: F007
    severity: concern
    category: error-handling
    summary: "A refused `claim_work` retries every tick, logging an ERROR each time"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:283"
  - id: F008
    severity: note
    category: verification
    summary: "The client timeout fact is second-hand, and the 300-second deadline depends on it"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:82"
  - id: F009
    severity: note
    category: dependencies
    summary: "Three prerequisite designs are FAIL, and this design pins their commits"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:73"
  - id: F010
    severity: pass
    category: architecture-alignment
    summary: "Hub clock: no client time crosses the door"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:233"
  - id: F011
    severity: pass
    category: nfr
    summary: "Load-test NFR restated with specific targets"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:444"
---

# Review: slice — slice 263

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] MCP `answer` resume is both skipped and budgeted in the call

D7 says MCP tool calls leave the after-step to the tick, so a tool result returns before any claim or start. The same paragraph then says `answer` on the run's machine "resumes in that call" and calls this unchanged. D9 (line 320) builds the MCP deadline on an answer that includes the resume: 300 seconds, the door-version bump, `resume_wait_seconds` below 143.5, and Codex `tool_timeout_sec` of 305.

The sources disagree too. 262 (line 424) starts the resume detached from the after-step, and the 260 plan (line 94) and architecture (`260-arch.the-hub.md:196`, "Same machine, no wait") both require the same-machine resume to start in the call. The departures row at line 458 cites "Plan" and omits the architecture rule, so this conflict is unrecorded.

The answer depends on which path is true:
- If the resume is detached, the in-call budget is the answer call plus at most one claim call, well under 180. The 300 deadline, the door-version bump, the `resume_wait_seconds` limits and the Codex step would then be unnecessary.
- If it is synchronous, the design must say where it runs and reconcile that with 262's detached start.

The operator walkthrough (step 6) uses the CLI `amoeba answer`, so it never exercises the MCP path agents use. Fix: state which path the MCP answer takes, re-derive D9's budget from it, and record the change against the architecture.

### [CONCERN] `session_tick` writes rows but sits outside `WRITING_STEPS`

D2 has the step upsert, prune and touch rows, yet puts it in `STEP_CALLS` only. The architecture says a writing call's result is kept (`260-arch.the-hub.md:62`). 262 (line 209) defines `WRITING_STEPS` as the writing rows of `STEP_MODELS`, and a test enforces that. Under 262's own definition this step is a writing step.

The reason given (retry time 0, so no repeat) holds, and keeping a result for every tick of every session would be costly. But it is a departure from an architecture rule and is missing from the departures table. Record it there with that reason.

### [CONCERN] The plan's "list shows it as behind" criterion is dropped for sessions started after an upgrade

The 263 plan entry requires that "a session whose `amoeba-mcp` has an older door version … `list` shows it as behind" (`260-slices.the-hub.md:133`). The architecture says `list` shows which sessions are behind (`260-arch.the-hub.md:270`). D6 removes the case where the old program starts after the upgrade, so the session is not listed and only its machine is.

The technical reason is accurate: refused calls carry headers only, and the hub cannot create a row without the body. But this removes a success criterion the plan assigns to this slice. That is a decision for the PM to make and record in the plan and architecture, not a departures-table row.

### [CONCERN] Amendments to 262 omit three changes and leave a wrong figure

- 262 line 300 gives `resume_claim_seconds` as 226.5 for the example config. Its own rule (135.5 − 5 + 2×43) gives 216.5. Line 93 of this design notes the error, but 262 is not corrected and no amendment lists it.
- 262 line 300 says `resume_bound_seconds` "still bounds how long an in-process `answer` can take for the MCP deadline check". D9 moves that check to the hub with the network times added. Neither this change nor the line-604 statement that `resume_claim_seconds` "is not used for that check" appears in the Amendments table.
- 262 line 99 says the limits are "each defined once", which the next finding breaks.

Fix: correct 262 line 300 and add the deadline-check change to the Amendments table.

### [CONCERN] `answer_call_bound_seconds` duplicates `resume_claim_seconds`, and the limits lack their formula

D9 defines `answer_call_bound_seconds` as `resume_bound_seconds − BUSY_TIMEOUT + 2 × CALL_BOUND`. Line 324 then calls it "the same sum as 262's `resume_claim_seconds`" and says it is defined apart "because … the two bound different things". If they bound different things, the formulas should differ, and they do not. Two definitions of one sum can drift, which 262's "each defined once" rule forbids.

The limits 143.5 (line 328) and 209.5 (line 335) are also asserted without the formula for `resume_bound_seconds`, which sits in an earlier design. A reader cannot check them. Fix: use one function for the sum, or give the two different formulas different names, and state `resume_bound_seconds` with its constants so the limits can be checked.

### [CONCERN] D11 is heavier than the plan asks for

The plan asks that runs on other machines show "as last reported, with the machine named" (`260-slices.the-hub.md:125`), and it asks for each machine's stored runs in the migration (line 123). D11 adds more: placing another machine's runs under members through checkouts, the hub judging that machine's open questions against its stored document, a `not_reported` state, a `runs_problem` field with its own validation path, and a size-cut rule.

The rejected alternative (run state on each question row) is a reasonable rejection. But member placement and re-judging are not what "as last reported" asks for. Cut candidate: show each other machine's stored run lines as last reported under that machine's heading, with no member placement and no hub-side judging of its questions. Keep the member grouping only if the design cites the plan line that requires it.

### [CONCERN] A refused `claim_work` retries every tick, logging an ERROR each time

D7 logs a refused claim at ERROR and says "the next tick's flag is the retry". The flag stays set while the work waits, so a persistent refusal, such as a bug in the claim's document, logs an ERROR every `notify_poll_seconds` with no limit. D4 rate-limits the tick's own failures to one WARNING per run. The architecture says refused work is not pending work and "nothing retries on every tick" (`260-arch.the-hub.md:195`). Fix: apply D4's run-based logging to the after-step, and state whether a refused claim clears the flag.

### [NOTE] The client timeout fact is second-hand, and the 300-second deadline depends on it

Claude Code's `MCP_TOOL_TIMEOUT` default is taken from a GitHub issue quoting the docs. The design flags this and schedules a check as step 1, which is adequate. If D9 keeps the 300-second deadline, the check should happen before D9 is decided, not during implementation.

### [NOTE] Three prerequisite designs are FAIL, and this design pins their commits

260, 261 and 262 each have a FAIL review, and this design pins them at specific commits. The update-first rule covers changes to the pinned decisions, but the amendments in this design need re-deriving after each revision, starting with the 262 figure above.

### [PASS] Hub clock: no client time crosses the door

D5 meets the architecture's "the hub's clock is the clock" rule. Session ages are set on the hub, client waits use a monotonic clock, and a stored run document's times are shown but never compared with hub time.

### [PASS] Load-test NFR restated with specific targets

D15 restates the architecture's load-test requirement with numbers: 2 seconds per tick, a 3-second gap between replies, and live rows throughout. The sizing is consistent: 50 sessions every 0.5 seconds and 500 sessions every 5 seconds both give 100 ticks per second.

### Run Digest

- Response length: 9639 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 11
- Tokens — prompt / cached / cache write / completion / reasoning: 853800 / 642569 / 211219 / 85380 / not computed
- Duration: 382.9 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
