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
reviewedSha: 99c0e9b03d52c19e06d1d95b32e8ea08a69f77c9
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 104226
cachedTokens: 11162
cacheWriteTokens: 93060
completionTokens: 5085
durationSeconds: 44.9
costUsd: 0.425057
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency direction match the architecture"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md#Architecture"
  - id: F002
    severity: concern
    category: scope-and-guarantees
    summary: "Value statement overclaims the guarantee that D1 disclaims"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md:43"
  - id: F003
    severity: concern
    category: integration-points
    summary: "D3 puts a new launch-time obligation on 184 that the architecture does not record"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md:154"
  - id: F004
    severity: note
    category: metadata
    summary: "Frontmatter understates dependencies and consumers"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md:6-8"
  - id: F005
    severity: note
    category: external-dependency
    summary: "Most real-run criteria are gated on an unshipped Squadron release"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md#Dependencies"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for the new I/O paths"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md#D5"
---

# Review: slice — slice 180

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Layering and dependency direction match the architecture

The pipeline ships as package data beside `answering.yaml`, as the architecture's slice-writing-pipeline paragraph says. It lives in a new `runner/request_run/` package that never imports the program store or `runner/lifecycle`. Git commits are delegated to Squadron's commit step. That keeps the architecture's rule that the Runner adds "no new git verb" and that Amoeba never edits a plan directly. The initiative-creation behaviour in D2 matches the architecture's "creates the requests initiative first… once per member". The D1 decision to skip a review step is a legitimate answer to the architecture's "review… slice-design work" deferral.

### [CONCERN] Value statement overclaims the guarantee that D1 disclaims

The Value section says the guarantee is "a run changes nothing in the provider except one commit that touches only the plan files." D1 (line 131) says the opposite. Nothing bounds the agent's actions outside the checkout or in gitignored files, and the write ban there is instruction-only. The commit guard (D5) only sees changed or untracked files in the repo. The architecture's trust model for requests, "a request run only adds a slice file and commits it", leans on this guarantee. 184 and the PM could read the Value text as a hard bound. Restate the guarantee in Value, in "Provides to 184" (line 270) and in the success criteria as: "at most one commit on the target touching only the two plan files, with no tracked or untracked change left in the checkout". Then state the unbounded exposure in the same place.

### [CONCERN] D3 puts a new launch-time obligation on 184 that the architecture does not record

The architecture's request-run description has 184 record only "the requests initiative's current slice set" at launch. D3 requires 184 to also record the target HEAD. It must block an `already_met` reply from a run that moved HEAD. Without that check, an agent that writes a plan entry and then replies `already_met` closes the request. It also leaves an undriven slice in the provider. The commit guard cannot catch this, because the guard allows changes inside the plan globs. The design lists the rule under "Provides to 184" but does not say it updates the 184 slice-plan entry. The architecture's already-met path also omits it. Add the HEAD-recording requirement to 184's slice-plan entry, or to the architecture's "Work in the provider" paragraph. As written, 184's author could miss a safety rule that only 184 can enforce.

### [NOTE] Frontmatter understates dependencies and consumers

`dependencies: []` conflicts with the Prerequisites (initiatives 100, 120 and 140, slice 122's probe pattern, and Squadron D8). `interfaces: [184]` omits 183, which consumes `AlreadyMet.commit` (line 271). Update both fields so dependency tooling sees the real graph.

### [NOTE] Most real-run criteria are gated on an unshipped Squadron release

The design states the gate openly. It splits the criteria into those met with the stub `sq` and those that need a real run, and it marks `BLOCKED:` tasks. No lighter in-repo alternative fits the architecture. The Runner may not add git verbs, and an agent-run commit is unguarded. The dependency also appears in the register (S16). No change is needed. Keep the unit-tier work (parser, input, probe) landing first, as the Development Approach plans.

### [PASS] Failure modes are enumerated for the new I/O paths

Each new path has an explicit handling strategy:
- **Guard failure, moved HEAD or failed run:** the run fails and 184 blocks the request with Squadron's message (D5).
- **Prose-only reply:** Squadron fails the step (D2, "A provider that cannot take a request").
- **Stalled or runaway agent:** Squadron's stall failure and the cost cap (D6).
- **Missing or malformed reply:** `ReplyProblem` kinds (D7).
- **Stale `reply.json` after a failed run:** 184 decides from the run outcome first (D7).
- **Unparseable plan files:** the agent's self-check, the live assertion, and a stated escalation path (Risk Assessment).

### Run Digest

- Response length: 4898 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 104226 / 11162 / 93060 / 5085 / not computed
- Duration: 44.9 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
