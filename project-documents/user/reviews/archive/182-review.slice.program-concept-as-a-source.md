---
docType: review
layer: project
reviewType: slice
slice: program-concept-as-a-source
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/182-slice.program-concept-as-a-source.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: e4f946492ec186592a8b5c2b22dd71ce680d377a
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 101014
cachedTokens: 11162
cacheWriteTokens: 89848
completionTokens: 3600
durationSeconds: 33.1
costUsd: 0.397357
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: concern
    category: under-specification
    summary: "Asking project that is also the concept member is not specified"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#D3 and #D4"
  - id: F002
    severity: note
    category: dependency
    summary: "182 depends on an amendment to 181's unimplemented design"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#Interfaces Required"
  - id: F003
    severity: note
    category: scope
    summary: "Edge and request state as passages is deferred to 185"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#Technical Scope (Excluded)"
  - id: F004
    severity: note
    category: observability
    summary: "`passage_index` does not record which member a concept passage came from"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#Technical Scope (Excluded)"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Boundaries, dependency direction and failure handling match the architecture"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#D1-D3"
---

# Review: slice — slice 182

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Asking project that is also the concept member is not specified

The concept member is one of the program's members, so a question can come from the concept member itself. The design says nothing about that case, and the architecture's Envisioned State expects it to be common. In `trading`, `trading-data` holds the concept and also receives questions. Several behaviours are left undefined:
- **Duplicate passages.** The concept file is read twice, once by the project's own reads (143) if its glob or plan covers the file, and once as `program_concept`. Nothing says to dedupe or to skip the concept read.
- **Two commit pins.** The project's own reads pin commit C on the asking project's checkout. The concept read pins Q on the checkout `read_member` resolves for the same project, which may differ in a worktree setup. One question can then render two different commits of the same repo.
- **Member list markers.** D4 shows the "holds the program concept" and "this question comes from this project" markers on separate lines. For the concept member, both markers belong to one project, and the text rule does not say how they combine.
- **Unneeded store open and `cf` call.** `read_member` for the asker's own project opens its own store read-only and makes a second `cf` target call. The asker's checkout and target are already known.

The design should state the rule for this case and add one test. It could say, for example, that the concept read reuses the asker's own checkout and commit, and that the markers combine on one line.

### [NOTE] 182 depends on an amendment to 181's unimplemented design

`Readable` must carry the `Checkout` and the CF project id, and `Program` and `Member` must carry `updated_at`. The design records the amendment to 181 and checks it against 181's design, with "tasks follow the code" as the fallback. Because 181 is not yet implemented, the change is cheap now. Confirm that 181's design text actually carries both fields, since a mismatch would surface only at 182's implementation.

### [NOTE] Edge and request state as passages is deferred to 185

The architecture's "Cross-project visibility" sentence includes "the state of the edges and requests B is party to". That state does not exist until 183 and 184, so deferring it is sound. The deferral is explicit, names its owner (185), and has 185 extend D6's visibility rule. Make sure the slice plan entry for 185 lists this item, so the architectural requirement keeps an owner.

### [NOTE] `passage_index` does not record which member a concept passage came from

`passage_index` stores only the source path and date, so a recorded concept passage cannot be traced to its member repo or commit. The design defers this to issue #27 because nothing reads it yet. The deferral is proportionate. The visibility test already asserts `(kind, member, source)` on the rendered set.

### [PASS] Boundaries, dependency direction and failure handling match the architecture

- **Boundaries.** All program reads happen in the Runner's answering path. No new git verb or command kind is added, and the answerer never reads another member's rules, plan or PM answers.
- **Dependencies.** The design depends on 181 only through `read_member` and the tick's `Program`. It also depends on the unchanged 143 and 144 interfaces. Nothing flows backward into 120's lifecycle.
- **Failure modes.** Each new read has a handling strategy:
  - An unreadable member returns `sources_unreadable` with 181's reason.
  - A missing file returns `sources_missing`.
  - A git or `cf` failure or timeout returns `sources_unreadable`.
  - A refused budget returns `None`.
  - An oversize concept returns `sources_too_large`.
  - A program store failure exits, per 181.
- **Architecture sentence.** This satisfies the architecture's "declines the question with 140's existing source reasons; never silently left out."
- **Proportionality.** The design adds no decline reason, no config and no store change, and it reuses the existing helpers by making them public. No scope needs cutting.

### Run Digest

- Response length: 5115 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 101014 / 11162 / 89848 / 3600 / not computed
- Duration: 33.1 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
