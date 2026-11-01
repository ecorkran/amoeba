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
reviewedSha: ce7bf64ae5146c6476ca35b0c6ba6733ac486d07
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 194315
cachedTokens: 94227
cacheWriteTokens: 100082
completionTokens: 5894
durationSeconds: 54.6
costUsd: 0.469506
costBasis: provider
runId: run-20261101-p4-6b23341c
squadronVersion: 0.24.11
findings:
  - id: F001
    severity: pass
    category: architectural-alignment
    summary: "Squadron capability gap handled as the architecture requires"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#D8 — Squadron capability request; the first `sq` that runs the pipeline is recorded as an observation"
  - id: F002
    severity: pass
    category: failure-modes
    summary: "Slice honestly states what the probe and the unit tier can prove"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#D9 — Start-up probe: the shipped pipeline must validate"
  - id: F003
    severity: concern
    category: dependency-direction
    summary: "143's dependency on this slice contradicts the slice plan and the slice's own mitigation"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md:306-309"
  - id: F004
    severity: concern
    category: integration-points
    summary: "The check step and Amoeba may select different JSON objects from the same reply"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md:182, 207, 231"
  - id: F005
    severity: note
    category: scope
    summary: "Scope beyond the slice plan entry is modest but should be confirmed"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#D10 — Live tier for real-pipeline tests"
  - id: F006
    severity: note
    category: under-specification
    summary: "Ties in precedence are not addressed"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#D3 — Inputs are files Amoeba writes; instructions live in the pipeline"
---

# Review: slice — slice 140

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Squadron capability gap handled as the architecture requires

The architecture says "A missing capability is a Squadron change, not an Amoeba workaround" and asks for a pinned minimum version. D8 files five capabilities as one Squadron issue. It records the first `sq` observed running the pipeline as a dated note in the process contract. It also avoids version comparison in code, which keeps the probe behavioral. D2 declines to keep an alias or provider safe-list in Amoeba. The no-tools and independent-check properties come from the pipeline, as the trust model needs.

### [PASS] Slice honestly states what the probe and the unit tier can prove

The probe covers non-zero exit, timeout and missing `sq`, each raising `StartupFailedError`. The slice says plainly that on 0.24.11 the probe passes even though the pipeline cannot run. Success Criteria separates what the unit tier proves from what waits on Squadron. Parsers return a named `missing` or `malformed` problem. `prepare_scratch` requires an empty directory, so stale output files cannot be read. A failed step writes no partial reply.

### [CONCERN] 143's dependency on this slice contradicts the slice plan and the slice's own mitigation

"Provides to Other Slices" makes `Passage`, `PassageKind` and `AnsweringInput.passage_ids()` the type 143 returns and the object its citation check reads. The frontmatter lists 143 under `interfaces`. The slice plan says the opposite. Entry 143 states "Independent of 140 and 142". Entry 140's Interfaces list names only 144 as a consumer. The Implementation Order section says 140 and 143 can run in parallel. The slice's own mitigation (line 399) says "141 to 143 do not depend on this slice".

If 143 imports types from this slice, then 143 depends on 140's unit-tier work. 140 cannot complete until Squadron ships D8. The parallelism and the "Squadron gap has the length of 141–143 to be fixed" argument both break.

The slice also defines `Passage` and `AnsweringInput`, with id assignment and rendering. The plan gives 143 the job of "cuts them into numbered passages". Resolve this one way or the other:
- Declare 143 dependent on the unit-tier part of 140. This means amending the plan entries for 140 and 143, and 140 would need its unit tier to finish separately from its Squadron-gated criteria.
- Or move `Passage` and `PassageKind` to a module that 143 owns, and have 140's `AnsweringInput` consume them.

### [CONCERN] The check step and Amoeba may select different JSON objects from the same reply

The trust model rests on the check step judging the answer that 144 will send. D4 and capability 2 have Squadron pass "the first JSON object in its reply" to the check step. D6 has Amoeba's parser read `answer.json` (the verbatim reply) and take "the first well-formed JSON object", also accepting fenced blocks and prose-wrapped objects.

These two rules are not the same rule. Suppose the reply opens with prose containing a brace fragment, or with a malformed object. Squadron's extraction and Amoeba's could pick different objects. The check would then confirm one object while Amoeba sends another. The slice's parser tests and live tests do not cover this.

Fix one of these:
- Specify a single extraction rule in the Squadron issue (capability 2) and mirror it in `artifacts.py`.
- Or have capability 3 write the extracted object that the check step actually saw. Amoeba would then parse that file.

Add a live or fixture test that asserts the parsed answer equals the reply embedded in `check.prompt.md`.

### [NOTE] Scope beyond the slice plan entry is modest but should be confirmed

The plan entry for 140 covers the pipeline, the artifact shapes, the probe and the version note. The slice adds an input contract (`prepare_scratch`, rendering), a live-test tier with environment variables, and PM-precedent matching instructions with two live matching tests. The input rendering and the pipeline instructions are needed to run the pipeline, so they are defensible. The matching live tests overlap 144's success criterion on rewording and per-slice matching. Each is a paid real run. Keep them only if the live cost stays within the cap. Otherwise defer them to 144's tests, which use question tails from real runs.

### [NOTE] Ties in precedence are not addressed

The architecture's check says no passage of "equal or higher precedence" may contradict the answer. The slice states only "later date wins". Dates are second-resolution UTC. Two passages with the same timestamp, or a file whose commit date equals a PM answer's date, leave the check instruction silent. Add one sentence to the check instructions saying what the check step does on a tie. The architecture's decline-by-default stance suggests: answer no on a tie that conflicts.

### Run Digest

- Response length: 5700 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 194315 / 94227 / 100082 / 5894 / not computed
- Duration: 54.6 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
