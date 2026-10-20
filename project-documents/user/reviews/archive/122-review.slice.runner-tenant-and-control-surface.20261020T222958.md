---
docType: review
layer: project
reviewType: slice
slice: runner-tenant-and-control-surface
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: 37e511cfa8d1af49f1ec2452f1d866923acb5ecb
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 500355
cachedTokens: 393065
cacheWriteTokens: 107278
completionTokens: 8454
durationSeconds: 71.3
costUsd: 0.553786
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: boundary-violation
    summary: "D3 changes a recovery contract the plan assigns to slice 120, and the slice contradicts itself about 120's state"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D3 — Recovery leaves an existing run in flight"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Project-escalation closure rule conflicts with the once-per-lifetime `cf` probe"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D8 — Faults: one catch per project, two scopes (Closure), D9"
  - id: F003
    severity: note
    category: scope
    summary: "Departures from the architecture's text are recorded in the slice plan but not in the architecture"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D9, #D10, #D6"
  - id: F004
    severity: note
    category: error-handling
    summary: "One launch-time I/O failure is only implicitly handled"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D4 — Detached launch"
  - id: F005
    severity: pass
    category: nfr
    summary: "Tick deadline and per-call timeout restated with targets"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D10 — Settings and the tick budget"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Observe/decide/act, fault isolation and store-write boundaries match the architecture"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D1, #D2, #D8"
  - id: F007
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable, with one place to trim if scope pressure appears"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D7 — Reissuing a `not_applied` launch (issue #9)"
---

# Review: slice — slice 122

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] D3 changes a recovery contract the plan assigns to slice 120, and the slice contradicts itself about 120's state

- **Contradiction on 120's state.** Prerequisites says "120, merged" and builds on its by-id observer. D3's Sequencing note says "120 is not yet implemented" and offers to fold the change into 120. Both can't be true, and the implementer can't tell whether to modify merged code or a pending slice.
- **Conflict with the slice plan.** Slice plan entry 120 has the criterion "Recovery adopts the run when its state exists". D3 reverses it: the observer gains an `InFlight` answer and recovery leaves the entry unresolved. That is a substrate change to 100's most sensitive code, which the plan rates Medium risk.
- **Conflict with the architecture.** The architecture's "Contract changes the Runner needs from 100" says these changes "land as their own slice ahead of the Runner, so the contract changes first". This slice instead makes edits in `amoeba.process`, grows the public API from 13 to 14 names, and rewrites contract-suite oracles inside the slice the plan rates highest-risk.
- **Why the reasoning stands.** Adopting would end detection's deferral while a run may still be writing reviews, and 125 could no longer use `record_runner_report`. So the change is needed. The problem is where it lives.
- **Fix.** Before this design is accepted, make one decision. Either amend slice 120 to leave existing runs in flight and drop D3 from this slice's scope, or keep it here and correct "120, merged" and the plan's entry 120 criterion. This also trims the heaviest part of the slice.

### [CONCERN] Project-escalation closure rule conflicts with the once-per-lifetime `cf` probe

- **The rule.** D8's closure rule says that at the end of a complete project tick, every open project-scoped escalation "whose kind did not recur in that tick" is closed.
- **The probe.** D9 runs each link's `cf` probe once per lifetime. A failed link is only flagged, and nothing re-probes it.
- **The collision.** The tick after a `cf_probe_failed` escalation is raised will not re-run the probe, so the kind "did not recur". The escalation then closes on the next complete tick even though the link is still broken. The architecture closes an escalation "on the first tick where that fault no longer occurs", but here the fault is never re-evaluated, so "no longer occurs" can't be known. The Functional Requirement says a failed link "raises one `cf_probe_failed` escalation", which implies it should persist.
- **Other kinds.** The same question applies to any kind that is only evaluated on some ticks, such as `run_observation_failed` for a run that isn't due for a poll.
- **Fix.** Close only kinds the tick actually re-evaluated. For the probe, either re-raise each tick from the lifetime-failed flag or exempt it from closure.

### [NOTE] Departures from the architecture's text are recorded in the slice plan but not in the architecture

The slice plan entry already carries these changes, and each has a stated rationale. The architecture document (status complete) still says otherwise:
- **Poll cadence.** The architecture polls "each tick". The slice polls at most once per tick and no more often than a 15 s interval, based on measured CPU cost.
- **`sq` probe failure.** The architecture refuses to start "the Runner tenant". The slice refuses to start the process, and justifies that as avoiding a silent fallback.
- **`cf` probe.** The architecture probes once at start. The slice probes per link on first use, which is needed because a link is required to probe, and a failure escalates instead of refusing.
- **Launch exit 2.** The architecture "stops the Runner tenant". The slice exits the process with a new `UPSTREAM_SHAPE` code.

These are reasonable, and no action is needed in this slice. Folding them into the architecture later would keep slices 123–129 from reading the stale text.

### [NOTE] One launch-time I/O failure is only implicitly handled

D4 handles `Popen` raising `OSError`. It doesn't name the earlier step where the exclusive-create of the two log files can fail, for example from a full disk or an existing file. The entry is already journaled at that point.

The outcome is probably safe. The exception reaches the per-project catch, and the entry then falls through the grace-period path (D6) to `failed`. But that path is implicit. One sentence naming it, or a test, would settle it. The other new I/O paths are explicit: poll failure, probe failure and timeout, child exit before the line, and an unreadable log in the D7 check.

### [PASS] Tick deadline and per-call timeout restated with targets

The architecture's NFR is a deadline checked before every subprocess call, a per-call timeout, and worst-case tick length of deadline plus one call timeout. D10 restates all three with defaults (5.0 s deadline, 8.0 s call timeout). It adds a start-up bound (`tick_call_timeout_seconds < shutdown_grace_seconds`) and a test that injects a runner failing after the budget is spent. The carry-over of cut-off projects and the restart-from-the-top rule for Observe match the architecture.

### [PASS] Observe/decide/act, fault isolation and store-write boundaries match the architecture

- **Decide is pure, and Act journals before it acts.** The slice has a single `Planner` seam and a fixed stage sequence with no plugin registry.
- **Faults.** There is one process-boundary `except Exception`. Store failures and shape errors re-raise. A node with a run in flight is not blocked until its run ends. Dedup rides on 121's project-scoped escalation.
- **Boundaries.** `amoeba.runner` is imported only by `amoeba.cli`, and an import-boundary test enforces this. The Runner never kills a run and makes no git writes. The slice excludes lifecycle, `cf_write`, tick-time `cf` reads and routing, which keeps it inside the scope the plan assigns.
- **Run ids.** The id is journaled before any side effect, and a reissue reuses the id because Squadron refuses a taken one.

### [NOTE] Proportionality is acceptable, with one place to trim if scope pressure appears

Effort 4/5 matches the plan. Most mechanisms are exercised by the crash proof (reissue, in-flight adoption, block-then-resolve). The lightest cut is the reissue candidate sweep in D7, which reads full journal history once per project per lifetime. It is justified by the "killed before launch" proof case, so it should stay unless D3 moves to 120 and the reissue behaviour is rescoped with it. The long "Provides to Other Slices" and Verification Walkthrough sections largely restate 123–129's needs and could be shortened without losing requirements.

### Run Digest

- Response length: 8065 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 500355 / 393065 / 107278 / 8454 / not computed
- Duration: 71.3 s
- Cost: $0.55 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
