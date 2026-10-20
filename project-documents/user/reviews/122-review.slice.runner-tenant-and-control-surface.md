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
reviewedSha: 530c2be7c287f973d3d9291463b208bb13e17b79
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 405252
cachedTokens: 297616
cacheWriteTokens: 107626
completionTokens: 6764
durationSeconds: 58.9
costUsd: 0.52873
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Observe/decide/act, fault boundary and tick-deadline NFR match the architecture"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#Technical Decisions"
  - id: F002
    severity: concern
    category: error-handling
    summary: "A launch failed at the grace period can leave a late run that nothing observes"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D6 — Launch confirmation"
  - id: F003
    severity: concern
    category: under-specification
    summary: "The `cf` probe depends on an `amoeba.upstream.context_forge` module that the structure and scope never list"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D9 — Shape probes"
  - id: F004
    severity: note
    category: proportionality
    summary: "Scope is large but fits the plan's 4/5 effort and highest-risk rating. These parts could shrink if the design needs trimming"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D9 — Shape probes"
  - id: F005
    severity: note
    category: failure-modes
    summary: "Launch logs have no growth bound for long-lived runs"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#Special Considerations"
  - id: F006
    severity: note
    category: documentation
    summary: "The architecture already contains the departures that Special Considerations says remain to be recorded"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#Special Considerations"
---

# Review: slice — slice 122

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Observe/decide/act, fault boundary and tick-deadline NFR match the architecture

- **Stages.** D1 keeps Decide pure, with a `Planner` seam and no I/O. Act issues only journaled commands.
- **Fault boundary.** D8 has exactly one `except Exception`. Store failures re-raise, which matches the architecture's "faults stay in their project" principle. A node with a run in flight gets a project-scoped escalation, not a block, and escalation dedupe plus closure follow 121.
- **Tick NFR.** D10 restates the "tick never waits" NFR with numbers: a deadline checked before every subprocess call, a per-call timeout, and a worst case of deadline plus one call. It also checks `tick_call_timeout_seconds < shutdown_grace_seconds` at start.
- **Dependency direction.** `amoeba.runner` is imported only by `amoeba.cli`, and an import-boundary test enforces this.
- **Failure modes.** The slice enumerates them for each new I/O path:
  - launch log creation failure
  - `Popen` `OSError`
  - an unreadable stderr log
  - exit 2 from a launch
  - a `PollFailure`
  - a cut-off probe
  - a crash between block and resolve

### [CONCERN] A launch failed at the grace period can leave a late run that nothing observes

- **What the design does.** At grace expiry with no `run_id=` line and one poll finding no state, D6 resolves the entry `failed` and blocks the node on `HUMAN`. It says the child "is not killed" and "a late run may still appear under this id."
- **What the architecture and plan expect.** The plan entry for 122 says "a late launch is adopted by polling again." The architecture says a slow launch can still create the run, so the Runner polls again and adopts it if it exists.
- **The gap.** After the entry resolves, no later poll exists. A late run is then:
  - unobserved
  - able to write reviews that no unresolved entry can receive through `record_runner_report`
  - able to hold the checkout while the PM, acting on the block, starts a second run in it
- **Why it matters.** This is the lost-run and duplicate-run risk the slice itself rates highest. D7 defers only the *reissue*, not this adoption.
- **Fix.** `LaunchTracker` still holds the live handle. While the child is alive after a grace-period failure, either keep the entry unresolved, or poll once more when the child exits, and adopt the run if a state exists. After a restart the handle is gone, so state explicitly that issue #9 and 125 cover that case. As written, the slice narrows the plan entry's "late launch is adopted" without recording the change.

### [CONCERN] The `cf` probe depends on an `amoeba.upstream.context_forge` module that the structure and scope never list

- **The reference.** D9 says `probes.py` "calls three parser functions in `amoeba.upstream.context_forge`" and that 123 replaces them.
- **The omission.** The Component Structure and the Included list name no new or changed `amoeba/upstream/` file. I found no `context_forge` module under `src/amoeba/upstream/`, which holds only `squadron/` and `__init__.py`.
- **Unspecified items.** The slice also doesn't say:
  - which module owns the `cf` subprocess call
  - how the call is bounded and made injectable. The Patterns section says the subprocess runner is injected, but doesn't say where that seam sits.
  - whether `amoeba.upstream` publicly exports the parsers
- **Why it matters.** 123 builds on this seam, so its owner and public shape should be fixed here.
- **Fix.** Add the module to the Component Structure as NEW, with its public names, and say who owns the `cf` runner.

### [NOTE] Scope is large but fits the plan's 4/5 effort and highest-risk rating. These parts could shrink if the design needs trimming

- **Lifetime failed-link flag.** The flag exists to keep the `cf_probe_failed` escalation open through D8's closure rule. It could go if the probe simply re-ran each lifetime for a failed link. That is cheaper than a recurrence-by-flag mechanism.
- **`UPSTREAM_SHAPE` exit code 8 and `UpstreamShapeError`.** The architecture requires a clear stop with a named error. It doesn't require a new exit code. `STARTUP_FAILED` is the alternative, though it is not available once the process is running.
- **`finish.record()` result fields.** The `failure` and `checkpoint` fields it records are replaced by 125, so they are throwaway work.
- **Cuts to the plan's scope.** None of these cuts removes anything the plan assigns to 122.

### [NOTE] Launch logs have no growth bound for long-lived runs

Retention covers only deleting finished logs. A multi-day run writes its stdout and stderr to a file with no size limit. This is acceptable for v1, but one line saying so would close the question.

### [NOTE] The architecture already contains the departures that Special Considerations says remain to be recorded

The architecture already reflects these decisions:
- the exit-2 launch stopping the process (D6)
- the poll interval (D10)
- recovery leaving runs in flight (D3)
- the per-link `cf` probe (D9)

Only the slice plan entry remains to be updated, and that entry already says "Recovery leaves an entry whose run exists in flight." The statements "This departs from the arch's…" in D6 and D9 are stale. Reword them so the task breakdown doesn't schedule redundant architecture edits.

### Run Digest

- Response length: 6110 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 405252 / 297616 / 107626 / 6764 / not computed
- Duration: 58.9 s
- Cost: $0.53 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
