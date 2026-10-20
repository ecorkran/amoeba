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
reviewedSha: 9e492f9a81b7248101e2d81568e05bbfe9631f5e
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 306775
cachedTokens: 200700
cacheWriteTokens: 106067
completionTokens: 5511
durationSeconds: 48.3
costUsd: 0.500269
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: nfr-restatement
    summary: "cf probe may break the \"deadline plus one call timeout\" bound"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D9 — Shape probes; project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D10 — Settings and the tick budget"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Launch-confirmation log read has no failure handling"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D6 — Launch confirmation"
  - id: F003
    severity: concern
    category: architectural-alignment
    summary: "Launch exit-2 handling is a stronger reaction than the architecture states, and it is not listed as a departure"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D6 — Launch confirmation; project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#Special Considerations"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Design is heavy for the work it must deliver; several pieces could be cut or deferred"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#Component Structure"
  - id: F005
    severity: note
    category: dependency-direction
    summary: "Recovery change to 120 (D3) is a cross-slice edit that the plan entry records"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D3 — Recovery leaves an existing run in flight"
  - id: F006
    severity: note
    category: architectural-alignment
    summary: "Fault vocabulary and project-scoped escalation are consistent with the architecture and 121"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D8 — Faults: one catch per project, two scopes"
  - id: F007
    severity: pass
    category: architectural-alignment
    summary: "Layer boundaries and dependency direction"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#Component Structure"
  - id: F008
    severity: pass
    category: architectural-alignment
    summary: "Observation, detached launch and crash-recovery design match the architecture"
    location: "project-documents/user/slices/122-slice.runner-tenant-and-control-surface.md#D4 — Detached launch"
---

# Review: slice — slice 122

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] cf probe may break the "deadline plus one call timeout" bound

The architecture binds the tick as: "Worst-case tick length is therefore the deadline plus one per-call timeout", with the deadline "checked before every subprocess call". D10 restates the deadline and the per-call timeout and claims the same bound, which is good.

D9 conflicts with that claim. It runs the three `cf` probe commands on "the first observation … that has budget for three `cf` calls". If that is one `allows_call()` check followed by three calls of up to 8 s each, the worst case becomes the deadline plus three call timeouts. That is about 29 s with the defaults, against a stated 13 s. It would also exceed the shutdown reasoning in D10, which assumes shutdown waits for at most one call.

The slice should say that `TickBudget.allows_call()` is checked before each of the three commands. It should also say what a partially completed probe does. One option is to discard the partial result and re-probe from the top on the next tick, which is safe because observation only reads.

### [CONCERN] Launch-confirmation log read has no failure handling

The task requires every new I/O path to have explicit failure handling. D4 covers the log-open failures and `Popen` `OSError`. D7 covers an unreadable log during the reissue check. D6 reads the stderr log on every tick until a launch is confirmed, but it never says what happens when that read raises `OSError` (log removed, permission change, I/O error).

As written, the error reaches the catch in D8. That blocks the node, or raises a project escalation if the node has a run in flight. It does so even though the launch may be healthy, and it repeats every tick.

D6 should treat an unreadable log as "no line yet". The poll-on-exit and poll-on-grace-expiry paths already decide the outcome. Alternatively it should name a specific fault. The behaviour should match what D7 already decides for an unreadable log.

### [CONCERN] Launch exit-2 handling is a stronger reaction than the architecture states, and it is not listed as a departure

The architecture says an exit 2 from a launch "stops the Runner tenant with an error naming the command". D6 and D8 instead re-raise `UpstreamShapeError` through the project catch, so the whole resident process exits with `UPSTREAM_SHAPE`. The other tenants stop too, and so do the other projects.

The slice may be right that a tenant fault is process-fatal. If so, the "Slice plan and architecture" list in Special Considerations should record the exit-2 behaviour as a departure, as it does for the probe, polling and recovery. The listed arch sentences ("Unknown escalates", "Observing a run without blocking the tick") do not cover it. Otherwise the design should stop only the Runner tenant.

D6 also leaves one case open: a child that exits 2 and leaves a run state. Per D6 that run is observed, and the exit code is ignored.

### [CONCERN] Design is heavy for the work it must deliver; several pieces could be cut or deferred

The slice plan assigns most of this scope, and I'm not recommending cutting the assigned behaviour. The plan assigns:
- the detached launch;
- confirmation;
- crash recovery;
- the probes;
- the fault boundary;
- the deadline.

The design still carries more mechanism than that needs. It has 13 new modules, ten decisions, a closed `Action` union, a separate `view.py` and `actions.py`, and a `Planner` protocol. The only production planner is `ReissuePlanner`, and a test planner is the only other implementation. It also adds three new settings and flags, a new exit code, a project-escalation closure rule, and a crash proof that runs the real process.

Specific candidates to trim or defer:
- **Poll interval flag.** `--run-poll-interval` is justified (D10) by the architecture and the plan. `--tick-call-timeout` and `--tick-deadline` are also named in the architecture. If all three exist, state that none of them is meant to be tuned per run. Otherwise keep them as settings only and defer the flags until someone needs to change them.
- **Module split.** `actions.py` (two dataclasses) and `view.py` could merge into `decide.py`. `launch_log.py` and `run_ids.py` could merge into `launch.py`. This would keep the files under about 300 lines and cut import surface.
- **Reissue sweep bookkeeping.** The "once per lifetime per project" sweep reads full `journal_entries(project_id)`. D7 already concedes the cost scales with journal history. A bounded or indexed query is only worth building once that cost shows up.
- **Contract-document edits.** The long list under Provides (tenants, tenant obligation, recovery, supervisor directory, flags, exit codes, substrate guide) restates other documents. Reduce it to the sentences that actually change.

I don't consider any of these a blocker.

### [NOTE] Recovery change to 120 (D3) is a cross-slice edit that the plan entry records

D3 changes the observer, recovery and contract text that 120 ships. The plan entry for 122 includes the matching criterion ("Recovery leaves an entry whose run exists in flight … rather than adopting it"). The architecture's launch description says the same: "recovery does not resolve an entry whose run exists". The direction is correct, since the new in-flight model belongs to the Runner. D3 handles the sequencing by making it the first code task, so I raise no issue. The plan's 120 criterion still says recovery "adopts the run when its state exists". That wording now describes behaviour this slice changes, so 120's criterion should be reworded to match.

### [NOTE] Fault vocabulary and project-scoped escalation are consistent with the architecture and 121

- The single `except Exception` at the project boundary matches the architecture.
- Store failures and `UpstreamShapeError` re-raise, so the process exits.
- A node with a run in flight escalates at project scope and blocks only when its run ends. This is the architecture's rule.
- Closure happens only on a complete tick, which fits 121's deduplication.
- Expected faults are treated as answers, not exceptions.

### [PASS] Layer boundaries and dependency direction

The Runner writes only through the store's public API and imports only the public names of `amoeba.store`, `amoeba.process` and `amoeba.upstream`. `amoeba.runner` is imported only by `amoeba.cli`, and an import-boundary test enforces that. Decide is pure, Act issues only journaled commands, and the Runner never kills a run and makes no git writes. All of this matches the architecture's principles.

Later-slice scope (intents, reconciliation, dispatch, routing) is correctly excluded.

### [PASS] Observation, detached launch and crash-recovery design match the architecture

Runs launch detached in their own session with stdin from `/dev/null` and per-entry logs. Observation is by run id with no process handle. Confirmation uses the exact `run_id=` line, with a poll before a launch is failed. Reissue reuses the run id, and the pre-reissue and post-failure polls follow the architecture's description. The `sq_run` entry spans the whole run, which the evidence contract's D5 requires. The `SIGKILL` proof covers the kill points that matter.

### Run Digest

- Response length: 8949 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 306775 / 200700 / 106067 / 5511 / not computed
- Duration: 48.3 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
