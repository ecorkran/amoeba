---
docType: review
layer: project
reviewType: slice
slice: run-identity-and-supported-run-surfaces
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: 7f7cba1542e8bc9ad84a89abba5f0c23c872215c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 204515
cachedTokens: 96751
cacheWriteTokens: 107758
completionTokens: 9288
durationSeconds: 77.5
costUsd: 0.534404
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Core design matches the architecture's run-identity and supported-surface decisions"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#Technical Decisions"
  - id: F002
    severity: concern
    category: scope-creep
    summary: "Launch-log machinery is 122's scope and cannot fire in this slice"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md:56-57, 180-188, 259-260, 366-370"
  - id: F003
    severity: concern
    category: error-handling
    summary: "An unreadable launch log resolves to `NotApplied`, which defeats D4's purpose"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md:187, 399"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Grace-wait and poll failure modes at startup are not fully bounded"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md:184-186, 395, 401"
  - id: F005
    severity: note
    category: architecture-alignment
    summary: "Plan criterion \"no reads of run-state files\" is narrowed for legacy entries, and the plan wording should follow"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md:193-197"
  - id: F006
    severity: note
    category: proportionality
    summary: "Test and consumer churn is large but follows from the required key"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md:250-263"
---

# Review: slice — slice 120

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Core design matches the architecture's run-identity and supported-surface decisions

The slice does what the architecture asks of 120, and it stays within the contract changes the architecture assigns to this foundation slice.
- `run_id` becomes a required `sq_run` parameter key (D1).
- Recovery finds a run by id through `sq runs wait <id> --timeout 0 --json`, with legacy matching kept only for id-less rows (D3, D5).
- Pruning moves to the outcome document (D6).
- The slice adds no subprocess call inside a tick, so the architecture's "tick never waits" rule is respected.
- Dependency direction is correct. The slice depends only on 100, and 122 and 125 consume `poll_run` and `RunOutcomeDocument`.
- Plan items assigned to other slices stay excluded: `done` terminal, acknowledgment outcomes, the project-scoped escalation and the new tables belong to 121, and ingestion belongs to 125.
- The slice plan's Future Work item 6 is carried over.

### [CONCERN] Launch-log machinery is 122's scope and cannot fire in this slice

Slice plan entry 122 owns the per-run launch logs and the exact `run_id=<id>` confirmation. The 120 entry's success criteria say nothing about launch-log evidence. This slice still adds `launch_log.py`, `launch_confirmed`, `run_log_path`, a log-evidence branch in the by-id observer, a demo case and a walkthrough case. D4 admits that "no launch logs exist" until 122, so none of this can run in production before then.

Three costs follow:
- It fixes 122's log directory layout (`runs/<project_id>/<run_id>.log`) before 122 is designed.
- It gives recovery a new input, the supervisor directory, that has to be wired through the registry.
- It adds behaviour the architecture's recovery rule doesn't contain. The architecture says an id with no state after the grace period is `not_applied`. A log-evidence escalation is an addition and should be an architecture change, not a slice-local one.

The hazard D4 guards against is real: a started run is pruned, then its id is reissued. But it exists only once launch logs exist, so 122 can add the check at the moment it starts writing logs.

Cut or defer:
- `launch_log.py`, `run_log_path`, the log branch of `SquadronRunIdObserver`, the demo and walkthrough log case, and the matching D8 and Provides lines.
- Optionally, `sq_run_dispatch.py`. The routing could be a small function in `build_observer_registry`, rather than a third observer module beside `sq_run_id.py` and `sq_runs.py`.

If the PM prefers to keep D4 here, the architecture's recovery paragraph needs the matching edit.

### [CONCERN] An unreadable launch log resolves to `NotApplied`, which defeats D4's purpose

D4 treats "a missing or unreadable log" as false, logs a WARNING, and justifies this with "the outcome it allows is `NotApplied`, which 122 checks again by polling before it reissues."

That justification fails for the exact case D4 exists for. If the run started and was then pruned, and its log exists but can't be read (a permission or I/O error), the re-poll also returns `not_found`. The id is reissued and the work runs twice.

This also contradicts the Mitigation Strategies, which say "Escalation stays the default for every ambiguous answer" and that `NotApplied` requires "no launch-log line." An unreadable log is an ambiguous answer, not an absent line. Only a missing file should count as false. Any other `OSError` should return `Unknown` with the reason named. The project's exception rule also requires that the catch name its specific exception. This applies only if the log check stays in this slice.

### [CONCERN] Grace-wait and poll failure modes at startup are not fully bounded

Recovery runs before any tenant ticks, and the slice adds blocking waits and per-entry subprocesses to it. Three failure modes are unhandled:
- **Clock skew.** The claim that sleeps "add up to at most one grace period" holds only if `issued_at <= now`. If the wall clock moved backward, `issued_at + grace` can be far in the future, so the sleep is unbounded. `issued_at` in the future should be `Unknown`, or the sleep should be capped at `launch_grace_seconds`.
- **A hanging `sq`.** Each id-bearing entry is polled serially under `sq_timeout_seconds`, so N entries cost up to N × timeout. The risk section and the load tier cover poll counts and grace delay, but not this case. Either short-circuit after the first timeout in a pass, or state the accepted bound.
- **Shutdown during the sleep.** The design doesn't say what happens if the process is signalled while recovery sleeps. The injected sleep should be interruptible, or the behaviour should be stated.

The slice doesn't restate the startup budget these waits must stay within. It should name one.

### [NOTE] Plan criterion "no reads of run-state files" is narrowed for legacy entries, and the plan wording should follow

The slice plan's criteria say "Recovery and pruning make no reads of Squadron's run-state files" and also "Entries without an id still recover through the existing matching rule." The second needs file reads. D5 resolves this openly: the no-reads property holds for all id-bearing entries and for all of pruning, and the lazy scan keeps it true for any pass without legacy rows. This is the right resolution. The slice plan's wording should be updated so the two criteria no longer appear to conflict. No design change is needed.

### [NOTE] Test and consumer churn is large but follows from the required key

The 15-file list of `sq_run` journaling callers is the direct cost of D1's required key, and D1 rightly rejects an optional key. The shared `sq_run_parameters` helper and the instruction to re-grep rather than trust the list keep it manageable. Nothing needs to be cut here beyond the launch-log items above.

### Run Digest

- Response length: 6726 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 204515 / 96751 / 107758 / 9288 / not computed
- Duration: 77.5 s
- Cost: $0.53 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
