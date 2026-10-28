---
docType: review
layer: project
reviewType: slice
slice: pipeline-supervisor
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/132-slice.pipeline-supervisor.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261028
dateUpdated: 20261028
reviewedSha: 3976df0a3fcf5689e7a0b3a9d2059b5ee484c432
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 85028
cachedTokens: 22309
cacheWriteTokens: 62715
completionTokens: 5576
durationSeconds: 48.2
costUsd: 0.309664
costBasis: provider
runId: run-20261028-p4-86ec9636
squadronVersion: 0.24.8
findings:
  - id: F001
    severity: pass
    category: architectural-alignment
    summary: "Slice matches the Direction Change cut"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#Overview"
  - id: F002
    severity: concern
    category: concurrency
    summary: "Checkout hold does not cover a pending transient resume"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#D3, #D5"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Automatic resume confirmation and re-ingestion are not specified"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#D5, #D6"
  - id: F004
    severity: concern
    category: boundary
    summary: "Store contract change is bundled inside the Runner slice"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#D4"
  - id: F005
    severity: note
    category: documentation
    summary: "Arch body still describes the superseded design"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md"
  - id: F006
    severity: note
    category: scope
    summary: "`usage_limit` auto-resume extends the arch's transient list"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#D5"
  - id: F007
    severity: note
    category: hidden-dependency
    summary: "Pre-ship `agent_question` on implement steps completes silently"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#D10"
  - id: F008
    severity: pass
    category: proportionality
    summary: "Proportionality and deferred scope"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#Technical-Scope"
---

# Review: slice — slice 132

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Slice matches the Direction Change cut

Each item in the arch's "What slice 132 removes or shrinks" has a matching decision:
- Routing engine: D4, D9.
- Step map: D1.
- CF gate reads, ungate hatches, merge policy and merge observation: D9.
- Pointer writes: D3.
- Resolutions cut to resume and stop: D6.
- Config cut to pipeline and params: D2.
- Clean-tree check kept: D3.

The "What stands" list (tenant stages, journal, probes, one pipeline per checkout, drive/hold) is preserved. The dependency direction is correct, since the slice cuts code in 120–128 and provides inputs to 140 and 160. Declining the run-state-file exception (D10) is a justified narrowing of what the arch allows.

### [CONCERN] Checkout hold does not cover a pending transient resume

D3 keeps 125's rule that a checkout is held "until the run is neither running nor paused". For an `orphaned` or `failed` (`provider_error`/`stall`) outcome, D5 sets the slice `runnable` and queues a `ResumeRun` for a later Decide. In that window the run is neither running nor paused, so the hold lapses. The arch's concurrency rule says a checkout runs one pipeline at a time. Another slice in the same checkout (a different initiative, since the planner orders by initiative then slice) could be launched while the transient slice's branch holds uncommitted work. The pre-dispatch check would probably block that launch with `checkout_dirty` or `checkout_branch`, but the slice relies on that side effect instead of saying the hold persists. A held slice, or one waiting on `resets_at`, makes the window long. State that a slice with a resume candidate keeps its checkout held until the resume is issued or the slice blocks.

### [CONCERN] Automatic resume confirmation and re-ingestion are not specified

The arch (127, D6) confirms a resume when a poll shows the run has left the pause it was resumed from, because Squadron prints no `run_id=` on resume. That rule fits `paused` runs. D5 now resumes `failed` and `orphaned` runs automatically, where "left the pause" does not apply. The slice does not say two things:
- **Confirmation:** how a resume of a failed or orphaned run is confirmed.
- **Stale re-ingestion:** what stops observation from re-ingesting the same terminal `failed` or `orphaned` state before the resumed process claims the run. That would double-count toward the bound or issue a second resume. The `_refuse_live_run` guard (#195) and the act-time pre-poll only partly cover this.

Each new `ResumeRun` is an I/O path with a failure mode, so name the confirmation rule and the failure handling for "resume issued, run never leaves the failed state". The bound will probably catch it, but the design should say so.

### [CONCERN] Store contract change is bundled inside the Runner slice

The arch says contract changes to 100 "land as their own slice ahead of the Runner" and that where "the contract lacks, the contract changes first". D4 adds an additive atomic-completion option to the store's ingestion write inside 132, ordered in Migration Plan step 3 with the wiring. The change is small and additive, so a separate slice is not needed. The Migration Plan should make it the first task of step 3 with its own contract-suite test, and `store-contract.md` should be updated in that same task. Otherwise the Runner code in this slice could be written against an API that does not yet exist.

### [NOTE] Arch body still describes the superseded design

The Direction Change section is authoritative, but the rest of the arch still describes the routing table, `cf_write`, the step map, merge policy and the retry/accept/handled resolutions. Examples are "Merge policy is a pipeline parameter" and "In v1 the kinds are `sq_run` and `cf_write`". The slice is consistent with the Direction Change, but a reader of the arch alone sees contradictions. The arch should be trimmed once 132 lands.

### [NOTE] `usage_limit` auto-resume extends the arch's transient list

The arch says only "transient reason". The slice picks orphaned, `provider_error`, `stall` and `usage_limit` with `resets_at`, and edits the plan entry to match. This is proportionate and bounded. The wait itself is not covered by the "tick never waits" rule, because Decide reads `view.now` and nothing blocks.

### [NOTE] Pre-ship `agent_question` on implement steps completes silently

Until Squadron ships its Unreleased change, an implement-step question completes the run and the slice goes `done`. The slice states this and degrades the other absent fields to `BLOCKED`, never to a resume. The behaviour is Squadron's, not the Runner's, but the PM should know about it before enabling a pipeline that includes implement.

### [PASS] Proportionality and deferred scope

Most of the work is deletion. The new mechanisms are minimal:
- One pure module (`supervise.py`).
- One setting (`auto_resume_limit`).
- No new tables or columns.
- No configurable outcome table, with the reason stated.

The deferrals (routing store API retirement, per-phase review recording, multi-project scheduling) are not assigned to this slice by the plan, and each has a stated reason and a Future Work entry.

### Run Digest

- Response length: 6018 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 85028 / 22309 / 62715 / 5576 / not computed
- Duration: 48.2 s
- Cost: $0.31 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
