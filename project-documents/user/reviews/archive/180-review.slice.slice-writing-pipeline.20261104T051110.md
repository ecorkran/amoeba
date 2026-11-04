---
docType: review
layer: project
reviewType: slice
slice: slice-writing-pipeline
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/180-slice.slice-writing-pipeline.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 87b2f8c10bc4886e286a18ac3a3896ff68456013
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 281103
cachedTokens: 180957
cacheWriteTokens: 100138
completionTokens: 7055
durationSeconds: 62.9
costUsd: 0.490057
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: concern
    category: architectural-boundary
    summary: "The \"at worst a wrong plan entry\" bound is not enforced by the design"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md#D1 — One shipped pipeline: a write step and a commit step, no review"
  - id: F002
    severity: concern
    category: error-handling
    summary: "No wall-clock bound or hang handling for the write step"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md#D6 — The cost cap is per invocation"
  - id: F003
    severity: note
    category: risk
    summary: "A provider plan broken by a bad entry is a deferred guard"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md#Risk Assessment"
  - id: F004
    severity: note
    category: integration
    summary: "Request-slice entries should say \"no dependencies\" explicitly"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md#D2 — What the write step may write"
  - id: F005
    severity: note
    category: dependencies
    summary: "Gating on unreleased Squadron capabilities is handled openly"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md#Prerequisites"
  - id: F006
    severity: pass
    category: scope
    summary: "Reply contract, ownership split and proportionality"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md#D7 — Reply shapes are JSON, parsed leniently, failing by name"
---

# Review: slice — slice 180

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] The "at worst a wrong plan entry" bound is not enforced by the design

The write step is a `dispatch` with no `allowed_tools`. It runs with the provider's full tools, including a shell and the SDK's default tools (D1). It consumes `need.md`, which is model-restated text that crosses projects (Special Considerations, "Prompt injection").

The commit guard (D5) only inspects the checkout. It covers changed or untracked files outside `paths`, and a moved HEAD. It does not cover:
- anything the agent does outside the checkout (home directory, network, `git push`, other repos);
- gitignored files.

The git and CF write bans in D2 are instructions only. So the claim in Special Considerations that a steered agent "can at worst produce a wrong plan entry" is not backed by a mechanism. Architecturally, a request run is meant to write only plan entries, and the whole point of the guard is that Squadron decides what happens, not the model.

Either narrow the write step to read, glob and grep tools, edit and write tools, and read-only git and `cf`, or restate the claim to say what the design does and does not bound. Use whichever of those Squadron can express. D1 gives a reason against restriction (the SDK versus non-SDK tool sets), but it addresses only which tools exist, not what the agent may do with them.

### [CONCERN] No wall-clock bound or hang handling for the write step

A tool-using agent run is the only new long-running I/O path in this slice. The failure modes covered are:
- a missing or malformed reply (D7);
- a guard failure (D5);
- a probe timeout (D9);
- prose with no JSON (D2);
- a cost overrun (D6).

A hung or very slow agent run has no handling. The cost cap does not bound time. Observing and recovering a run is excluded as 184's job, but 184 can only act on what this slice's pipeline and launch contract provide. State one of these:
- the pipeline declares a step or run timeout, or the launch argv carries one (including as a Squadron capability if it is needed);
- the absence of a bound is deliberate, and 184's poll owns it.

The "Interfaces Provided" section should name which.

### [NOTE] A provider plan broken by a bad entry is a deferred guard

The failure that most threatens the architecture's "each project stays a project" goal is a committed plan file CF cannot read. It makes `plan_read_failed` hit the provider's whole project. The design handles it with an instruction to run `cf list slices`, plus the live tests, and defers a parse check in the commit guard until it shows up in use. That is a defensible choice given the principle of resisting complexity. The blast radius is one revertable commit, and the design says so. No change is needed, but if the first bad commit happens, the deferred check should be done at once.

### [NOTE] Request-slice entries should say "no dependencies" explicitly

The architecture says request slices stand alone, with no implicit predecessor. D2 specifies "no dependencies" for the initiative entry. For the slice entry it says only that the entry carries "dependencies, risk and effort". The instructions should tell the agent to write no dependencies, so a model-chosen dependency does not turn into an explicit predecessor that holds up a request slice.

### [NOTE] Gating on unreleased Squadron capabilities is handled openly

All three D8 capabilities are unshipped, and their option names are proposals. The design isolates this well. The criteria are split into met and gated, `BLOCKED:` lines are placed on the tasks that need Squadron, the unit tier can progress alone, and the architecture requires the dependency to be recorded in the notes register (row S16). No findings here. Minor point: the frontmatter has `dependencies: []` while Prerequisites names 100, 120, 140 and Squadron. Consider aligning them.

### [PASS] Reply contract, ownership split and proportionality

The reply shapes match the architecture's two outcomes. A new-slice reply gives an index that 184 binds against the slice set recorded at launch. An already-met reply gives a commit that 183 observes. The reader checks shape only, and nothing a model says satisfies an edge. Launching, the checkout hold, binding, the full-initiative decline and per-project configuration are all left to 184 and 183. The pipeline keeps the architecture's boundary: Amoeba issues no new command kind and no git verb, and Squadron does the commit.

The design is large but proportionate. Each mechanism has a named consumer: the shared helper (a DRY extraction from `answering`), the probe, the live tier and the per-directory settings split. Dropping the review step is justified in D1, and the architecture leaves the review question to slice design.

### Run Digest

- Response length: 5984 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 281103 / 180957 / 100138 / 7055 / not computed
- Duration: 62.9 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
