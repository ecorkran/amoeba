---
docType: review
layer: project
reviewType: slice
slice: answering-pipeline
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/140-slice.answering-pipeline.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: 2a36940c2794ea7e7b19198ad54e61f5bd9293ae
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 102462
cachedTokens: 11162
cacheWriteTokens: 91296
completionTokens: 3900
durationSeconds: 35.1
costUsd: 0.406112
costBasis: provider
runId: run-20261101-p4-6b23341c
squadronVersion: 0.24.11
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Trust-model properties map to the architecture's answering-run principles"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#D2 — No tools and no shared session, guaranteed by Squadron"
  - id: F002
    severity: pass
    category: layer-boundaries
    summary: "Boundaries with 142, 143 and 144 are drawn correctly"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#Technical Scope"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes for each new I/O path are enumerated"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#D6 — Reply shapes are JSON, parsed leniently, failing by name"
  - id: F004
    severity: concern
    category: hidden-dependency
    summary: "External Squadron dependency is absent from the slice's declared dependencies"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md:6"
  - id: F005
    severity: concern
    category: proportionality
    summary: "`question.md` carries fields no step instruction consumes"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#D3 — Inputs are files Amoeba writes; instructions live in the pipeline"
  - id: F006
    severity: note
    category: scope
    summary: "Parser and artifact contract sit in this slice, while the architecture lists artifact parsing under the answering-run slice"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#Technical Scope"
  - id: F007
    severity: note
    category: integration
    summary: "The probe gives no protection on 0.24.11"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#D9 — Start-up probe: the shipped pipeline must validate"
---

# Review: slice — slice 140

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Trust-model properties map to the architecture's answering-run principles

The architecture requires a read-only run with pre-assembled text, no file tools and a scratch directory. It also requires a check step that sees the question, the answer and the whole passage set, but not the answer step's reasoning. D1 to D5 deliver these. The check step gets the same two input files as the answer step, and only the first JSON object of the answer reply (D4). `check.prompt.md` gives a way to verify independence. D2 puts the no-tools guarantee in Squadron instead of keeping an alias list in Amoeba. That matches the architecture's rule that a missing capability is "a Squadron change, not an Amoeba workaround."

### [PASS] Boundaries with 142, 143 and 144 are drawn correctly

- **Excluded from this slice:** launching, the journal entry, the decide function, the citation check against the supplied set, passage assembly, and where the scratch directory lives. The architecture assigns each of these to other slices.
- **Decline path:** the check step runs even after an answer-step decline, and 144 declines on the answer step's decline regardless of what the check says. This keeps the architecture's rule that every uncertain path ends in a decline.
- **Dependency direction:** 143 renders to a written `passages.md` contract with no shared code, so 143 does not wait on this slice. 142 wires the probe at start-up, behind the answerer-section condition.
- **Architecture rules kept:** `max_cost_usd` is passed per run, nothing has a default, and the architecture's "no answerer section behaves as 132" rule is respected.

### [PASS] Failure modes for each new I/O path are enumerated

Each new I/O path has a named handling strategy:
- **Reply files:** `ArtifactProblem(missing|malformed)`, with an explicit list of malformed cases and no defaults. An absent `verdict` is malformed, never `no`.
- **Squadron reply and prompt files:** a failed step writes neither file, or leaves an existing one unchanged (capability 3). A reply with no JSON object fails the earlier step (capability 2).
- **Scratch directory:** `prepare_scratch` raises on misuse.
- **Probe:** a non-zero exit, a timeout or a missing `sq` each map to `StartupFailedError` and exit 7, bounded by `--sq-timeout`.

The architecture's per-run cost bound is restated as `.squadron.toml` `max_cost_usd`. The architecture states no latency or throughput NFR on this path.

### [CONCERN] External Squadron dependency is absent from the slice's declared dependencies

The frontmatter says `dependencies: []`. The body says the slice cannot complete until a Squadron release ships the D8 capabilities. 0.24.11 lacks all five. Every real-run criterion and the live tier are gated on that release, and 144 has no proven pipeline until then. The architecture's spike entry says a gap becomes "a Squadron issue that the answering slice depends on." The dependency is stated in prose and in the plan, but a tool reading the frontmatter will see a slice with no blockers. Record the Squadron issue as a dependency once it is filed, or add an explicit external-dependency field. The Prerequisites section and the `BLOCKED:` task convention are otherwise adequate.

### [CONCERN] `question.md` carries fields no step instruction consumes

`QuestionInput` and `question.md` include `project`, `step` and `cut_off`. The instruction text that D3 describes uses only the question and the `slice:` line, for PM-precedent matching.
- **`cut_off`:** in the architecture it is a record flag that measures how often truncation happens. It is not an input to the model, and the slice states no behavior that depends on it.
- **`project` and `step`:** neither has a stated use in the answer or check instructions.

Each extra field widens the contract with 144 and adds rendering and test surface. Either cut these fields, or state in the instructions what each one changes. If none changes anything, keep only the question text and the slice label.

### [NOTE] Parser and artifact contract sit in this slice, while the architecture lists artifact parsing under the answering-run slice

The architecture's "Answering run" slice includes "parsing its artifact." This design moves `read_answer`, `read_check` and `ArtifactProblem` into 140. That is defensible. The reply shape and the live-captured fixtures are tied to the pipeline, and 144 gets a proven contract. I did not read the slice plan entry, so I cannot confirm it assigns this scope to 140. Confirm it does, or note the move there so 144's scope is not double-counted.

### [NOTE] The probe gives no protection on 0.24.11

D9 says this plainly. 0.24.11 accepts any step key, so the probe passes even though the pipeline cannot run. The architecture's "pin the minimum version" intent is replaced by a behavioral probe plus a human-read dated note. This is consistent with the project rule against comparing upstream versions. It is sound only once capability 5 ships, and the document says so.

### Run Digest

- Response length: 6155 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 102462 / 11162 / 91296 / 3900 / not computed
- Duration: 35.1 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
