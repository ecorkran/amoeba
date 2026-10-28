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
reviewedSha: 84bf0029c9d5491798302b475116347df1c967a5
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 113860
cachedTokens: 11220
cacheWriteTokens: 102636
completionTokens: 5638
durationSeconds: 49.3
costUsd: 0.468859
costBasis: provider
runId: run-20261028-p4-86ec9636
squadronVersion: 0.24.8
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Supervisor cut matches the Direction Change"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#Overview"
  - id: F002
    severity: concern
    category: error-handling
    summary: "A mistyped pipeline name can stop the whole resident process"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#D2 (pipeline name is not validated at load)"
  - id: F003
    severity: note
    category: architecture-alignment
    summary: "The checkout hold now outlasts the arch's stated rule"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#D3"
  - id: F004
    severity: note
    category: dependency
    summary: "The store change lands inside this slice, not ahead of it"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#D4 (Atomic completion)"
  - id: F005
    severity: note
    category: risk
    summary: "Implement-step questions are accepted as completions until Squadron ships its fix"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#D10"
  - id: F006
    severity: note
    category: proportionality
    summary: "Some restated content could be trimmed"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#Component Structure"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Failure modes on the new resume and question paths are enumerated"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#D5"
---

# Review: slice — slice 132

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Supervisor cut matches the Direction Change

The slice implements each item the arch's "What slice 132 removes or shrinks" list names:
- **Routing and steps:** it removes the routing engine and the lifecycle step map.
- **Gates and merge:** it removes CF gate reads, the ungate hatches, and merge policy and observation.
- **Pointer writes:** it removes `cf_write` pointer moves.
- **Resolutions:** it cuts resolutions to `resume` and `stop`.
- **Config:** it cuts per-project config to `pipeline` and `params`.

It keeps what the arch says stands: tenant stages, fault isolation, detached launch and confirmation, journal and recovery, drive and hold intents, per-checkout concurrency, and shape probes. The clean-tree check stays, and a resume is checked for branch only. The outcome map (D4) is a closed enum over closed inputs, and unknown kinds go to `BLOCKED`. That matches the arch's "Unknown escalates" and "Closed vocabularies" principles.

### [CONCERN] A mistyped pipeline name can stop the whole resident process

D2 leaves the pipeline name unvalidated at load. It says an unknown pipeline "fails its launch before the `run_id=` line", and 122's launch-failure path then blocks the slice. In the same bullet it adds "an exit 2 still stops the process (122, D6)". The arch says Squadron exits 2 on a usage error before anything runs, and that an exit 2 from a launch stops the resident process. An unknown pipeline name is plausibly such a usage error. If so, one typo in one project's `pipeline` value stops the supervisor for every project, on first launch rather than at start. The slice does not say which exit code an unknown pipeline produces, so it does not say whether the slice blocks or the process stops. Fix this in one of these ways:
- **State the exit code:** pin the exit code Squadron returns for an unknown pipeline and say which path it takes.
- **Probe at start:** validate configured pipeline names once at start, in the way the arch already probes other shapes.
- **Isolate the fault:** treat a launch exit 2 caused by the configured pipeline as a per-project fault.

The Success Criteria also have no case for this.

### [NOTE] The checkout hold now outlasts the arch's stated rule

The arch's concurrency item holds a checkout "until its run is no longer running or paused". D3 widens this to failed and orphaned runs, because a resume needs their work left in the checkout. The reasoning is sound. It does mean a blocked slice holds its project's checkout until the PM acts, including after `auto_resume_exhausted` or `stop`. The arch body is only trimmed later (issue #22), so the two documents disagree until then. Record the widening in the arch's Direction Change text, or in #22's scope.

### [NOTE] The store change lands inside this slice, not ahead of it

The arch says "the contract changes first and the Runner then codes against it". The atomic-completion option on the ingestion write is an additive change to 100's contract. The slice makes it the first task of step 3, with its own contract-suite test and the `store-contract.md` update in the same task. That is proportionate, and a separate slice for one additive option would be heavier. The dependency direction is still correct, because 100's suite is stated to pass unchanged.

### [NOTE] Implement-step questions are accepted as completions until Squadron ships its fix

The arch's "hand off questions" behaviour is only partly delivered for `p456`-style pipelines. With Squadron's current release, an implement-step question completes the run. This slice then marks the slice `done` and launches its successor. D10 states this and accepts it. The Risk Assessment omits it, though, and it is the one path where the Runner can advance past unfinished work. Add it to the Risks, and tell the PM which pipelines are exposed.

### [NOTE] Some restated content could be trimmed

The Component Structure table's last row repeats D9's deletion list. D9's "confirmed against Squadron" table restates reasoning from `004-direction.amoeba.md`. Both are cheap to keep, but they are the first things to cut or replace with a reference if the document needs to shrink. The rest of the design is proportionate: most of the effort is deletion, no new tables are added, and the one new setting (`auto_resume_limit`) has a justified use.

### [PASS] Failure modes on the new resume and question paths are enumerated

The resume path has an explicit handling strategy for each failure, instead of leaving it "TBD":
- **Stale poll:** a poll that still shows the old state is `StillResuming` and is not re-ingested.
- **Resume never takes:** the slice blocks with `resume_failed` and no further automatic resume is issued.
- **Run gone at act time:** the act-time pre-poll withholds the resume.
- **Run missing or exit 2:** it is a failed command and never a relaunch.
- **Exhausted resumes:** the slice blocks with `auto_resume_exhausted`.
- **Restart:** the resume count is derived from the journal, so a restart cannot reset it.

Text bounds apply to questions and failure text. The new fields are optional, and an absent field degrades to `BLOCKED`, never to a resume.

### Run Digest

- Response length: 5979 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 113860 / 11220 / 102636 / 5638 / not computed
- Duration: 49.3 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
