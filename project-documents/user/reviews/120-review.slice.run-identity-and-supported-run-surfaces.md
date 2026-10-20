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
reviewedSha: 5b3ab57754b40703a9f57f0e433caf56e057a3f6
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 194955
cachedTokens: 97995
cacheWriteTokens: 96954
completionTokens: 4211
durationSeconds: 35.6
costUsd: 0.440543
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Start-up grace wait goes beyond what the architecture defines"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#D4 — not_found: the launch grace period"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Recovery can mark `NotApplied` for a run that did start, and nothing in this slice guards it"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#D4 — not_found: the launch grace period"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Test-fixture and documentation churn is large for a 3-point slice"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#Migration Plan"
  - id: F004
    severity: pass
    category: error-handling
    summary: "Failure modes for the new subprocess path are enumerated with explicit handling"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#D2 — One outcome reader, modelling only what is read"
  - id: F005
    severity: pass
    category: nfr
    summary: "The tick-never-waits NFR is respected and restated"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#Special Considerations"
  - id: F006
    severity: pass
    category: boundaries
    summary: "Layering, dependency direction and integration points are sound"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#Component Structure"
  - id: F007
    severity: note
    category: alignment
    summary: "Adopting `orphaned` and `unknown_status` at recovery diverges in wording from the architecture but not in effect"
    location: "project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md#D3 — By-id recovery: any run state adopts"
---

# Review: slice — slice 120

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Start-up grace wait goes beyond what the architecture defines

The architecture says only that, after a restart, an id with no run state once the grace period has passed is marked `not_applied`. It puts the "still launching" handling in the Runner's launch confirmation, which reads the log's `run_id=` line (122). D4 adds a sleep-and-repoll inside recovery, plus a startup-delay formula and injected clock and sleep. The document says this is "this design's choice". It is bounded and reasoned, and the tenant-never-waits rule applies to ticks, not to start-up, so it is not a violation. The cost is real: start-up can stall for up to `launch_grace_seconds` (60 s by default), and a second poll path needs its own tests, including the load-tier bound assertion.
A lighter option meets the criterion. If `now < issued_at + grace`, return `Unknown` or leave the entry for 122's launch confirmation. D4 rejects both, but it never weighs the stall against the criterion, which only needs `not_applied` after the grace period. Either keep the wait and state that the architecture is being extended, or cut it.

### [CONCERN] Recovery can mark `NotApplied` for a run that did start, and nothing in this slice guards it

A started run whose state was later removed returns `not_found`. Recovery marks it `not_applied` after the grace period. Under the architecture's re-issue rule, `not_applied` entries "may be issued again". The slice defers the launch-log check to 122 as issue #9. It argues that no Runner reissues anything yet, so nothing launches twice. That holds today, but the Risk section names a wrong `NotApplied` as the main risk, and the only guard lives in another slice. The architecture's guard is to poll again before reissuing and again if the reissue fails. The slice's own Provides section tells 122 to poll once more and check the launch log. The cost is that 122's design depends on an issue number, not on a recorded contract.
Record the 122 obligation in `docs/process-contract.md`. Put it in the `not_applied` definition for `sq_run`, not just in the Provides list of this document.

### [CONCERN] Test-fixture and documentation churn is large for a 3-point slice

The plan updates 15 test files by hand, adds a `sq_run_parameters` helper, extends the stub with a `SQ_STUB_WAIT_MODE` family, and retires `scripts/demo_journal.py`. It also adds a separate `sq_run_dispatch.py` module and updates three contract documents. Most of this is necessary once `run_id` becomes required.
Two items could be cut or deferred:
- **Dispatcher module.** `SquadronRunObserver` is a small routing wrapper. It could live in `sq_run_id.py` or `sq_runs.py` instead of a third observer file.
- **Wait-mode variants.** Add the stub's mismatch, exit 2, hang and non-JSON modes only as the unit tests for `poll_run` need them. Do not build them up front.
The task breakdown should keep the helper to the minimum the grep finds.

### [PASS] Failure modes for the new subprocess path are enumerated with explicit handling

D2 maps each of these to `PollFailure(reason)` and then to `Unknown` or "not chosen":
- missing `sq`
- timeout
- other `OSError`
- exit 2 or an unmapped exit code
- non-JSON output
- a document that fails validation
- an outcome that disagrees with the exit code
- a `run_id` mismatch

D4 bounds the start-up cost. Peer disconnect is not applicable to a one-shot subprocess. This matches the architecture's "unknown escalates" principle and its "expected external failure is an answer" convention.

### [PASS] The tick-never-waits NFR is respected and restated

The slice states that subprocess calls happen only at start-up (recovery) and in the manual prune command, and adds none inside a tick. It sets the per-poll timeout from the existing `sq_timeout_seconds` and gives a concrete start-up bound. `poll_run` is a single `--timeout 0` call, as the architecture requires.

### [PASS] Layering, dependency direction and integration points are sound

`sq_outcome.py` is the sole parser of `sq runs wait`, and it sits in `process/`, not `observers/`. Recovery, pruning, 122 and 125 all depend on it, and it depends on none of them. `RunOutcomeDocument` models only the fields in use, and 125 is told to extend it. The slice leaves id minting, launch logs and per-tick polling to 122, and the other 100 contract changes to 121. That matches the architecture's slice boundaries and leaves 122 and 125 an unambiguous reader.

### [NOTE] Adopting `orphaned` and `unknown_status` at recovery diverges in wording from the architecture but not in effect

The architecture says an orphaned run escalates. The slice has recovery adopt all six states that carry a state. The Runner then observes the adopted run and escalates it (122, 125). Recovery answers only "did the command take effect". This is consistent, provided 122 and 125 handle `orphaned` and `unknown_status` on the first observation after an adopted recovery. The Provides section already says so.

### Run Digest

- Response length: 6348 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 194955 / 97995 / 96954 / 4211 / not computed
- Duration: 35.6 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
