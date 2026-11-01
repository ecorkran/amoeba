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
reviewedSha: 67dad094fd99546bfa42ccf084eea0c7f992c8f7
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 275380
cachedTokens: 176910
cacheWriteTokens: 98462
completionTokens: 6396
durationSeconds: 55.0
costUsd: 0.476318
costBasis: provider
runId: run-20261101-p4-6b23341c
squadronVersion: 0.24.11
findings:
  - id: F001
    severity: concern
    category: architecture-alignment
    summary: "Start-up probe makes the answerer's pipeline mandatory for projects with the answerer off"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#D9 — Start-up probe: the shipped pipeline must validate"
  - id: F002
    severity: concern
    category: scope-gap
    summary: "Neither step's instructions are specified to carry the PM-precedent matching the architecture assigns to them"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#Technical Scope"
  - id: F003
    severity: concern
    category: dependency
    summary: "The slice's real-run criteria cannot be met on the installed `sq`, and the plan says \"proven against the installed `sq`\""
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#Dependencies"
  - id: F004
    severity: note
    category: verification
    summary: "The probe is toothless on today's `sq` until capability 5 ships"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#D9 — Start-up probe: the shipped pipeline must validate"
  - id: F005
    severity: note
    category: trust-model
    summary: "Prose around the answer JSON can leak reasoning to the check step"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#D4 — The check step's prompt is composed by Squadron from named parts"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Boundaries, dependency direction and ownership match the architecture"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#Technical Scope"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Failure modes and the cost NFR are enumerated"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#D6 — Reply shapes are JSON, parsed leniently, failing by name"
  - id: F008
    severity: pass
    category: proportionality
    summary: "Proportionality is acceptable"
    location: "project-documents/user/slices/140-slice.answering-pipeline.md#D10 — Live tier for real-pipeline tests"
---

# Review: slice — slice 140

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Start-up probe makes the answerer's pipeline mandatory for projects with the answerer off

The architecture says "A project whose config has no answerer section has the answerer off and behaves as 132 does." D9 runs the probe unconditionally, so `amoeba start` exits `STARTUP_FAILED` on an older `sq` even for projects that never configure an answerer. The slice states the tradeoff and gives a reason: the answerer's configuration doesn't exist until 142 and 144. The slice plan does assign the probe to this slice, so the probe itself is in scope. The conflict is with the architecture's off-state behavior, and the slice doesn't flag it as a deviation.
- Reconcile it explicitly. Either gate the probe on "any project has an answerer section", wired when 144 adds that configuration, or record in the architecture that the answerer pipeline is a hard `sq` requirement for every Amoeba install.
- The plan's Foundation Work item says "pinned beside 0.24.9", but D8 records only a dated observation. Decide where that pin lives, so 144's `projects.yaml` work can rely on it.

### [CONCERN] Neither step's instructions are specified to carry the PM-precedent matching the architecture assigns to them

The architecture makes "means the same thing, taking the slice into account" the answer step's job ("which branch?" for another slice is a different question). It makes the check step confirm that match. The architecture says this is done with no matching code, only the model. The instructions are written in `answering.yaml` in this slice. The slice lists the instruction contents as the citation rule, the decline form, the precedence rule and refusal of reserved actions. It does not list repeat-question matching, slice sensitivity, or the check step confirming a PM-answer match. `passages.md` does carry `question:` and `slice:` for PM passages, so the data is there. If the instructions leave out the matching rule, 144's success criterion on repeat questions has no pipeline support. Nothing in this slice's live tests would catch the gap either, because both precedence cases use rule-versus-PM-answer conflicts, not repeat-question wording. Add the matching rule to the instruction list. Add one live case: a differently worded repeat question, and a same-wording question for another slice.

### [CONCERN] The slice's real-run criteria cannot be met on the installed `sq`, and the plan says "proven against the installed `sq`"

The design says 0.24.11 cannot run the pipeline. The plan entry's criteria are two artifacts written, no file access, a recorded check prompt, and both precedence directions, all against a real run. The slice handles this with `BLOCKED:` lines and a Squadron issue. That is the right handling under the project rules, but the frontmatter has `dependencies: []` while Prerequisites names a Squadron release. The slice also can't complete, and 144 can't start on a proven pipeline, until Squadron ships. Two edits would remove the ambiguity:
- Show the external dependency in the frontmatter or the slice plan.
- State which success criteria are met by the unit tier alone, and which are gated.

### [NOTE] The probe is toothless on today's `sq` until capability 5 ships

D8 records that 0.24.11 accepts any step key, so `--validate` passes a pipeline that uses unsupported keys. Walkthrough step 5 therefore shows `amoeba start` starting normally on the real, current `sq`. That outcome passes, but it doesn't show the pipeline can run. The slice is honest about this in D8 and D9. Keep the stub-`sq` tests as the proof of the failure paths. Don't let the success criteria read as though the probe protects against 0.24.11.

### [NOTE] Prose around the answer JSON can leak reasoning to the check step

The architecture says the check step does not see the answer step's reasoning. D4 accepts that a model's prose around the JSON reaches the check step, and it explains why. This is a small, stated deviation. If the live tier shows models routinely adding justification, consider asking Squadron for the reply to be extracted from the JSON object (a capability-2 refinement) instead of accepting the leak.

### [PASS] Boundaries, dependency direction and ownership match the architecture

- Launching, journaling and recovery stay with 144.
- Citation-existence checks stay with 143.
- The decision and the gate stay with 144 and 142.
- 120's rule that Amoeba never reads the run-state file is kept (D5).
- The question and passages travel as files because pipeline params can't carry them (D3).
- The rejected per-question inlined YAML (placeholder rewriting) and the two-run alternative (journal doubling against the one-`sq_answer`-entry architecture rule) are sound.

### [PASS] Failure modes and the cost NFR are enumerated

- **Missing or malformed output:** `missing` and `malformed` problems cover a missing file or malformed JSON, with no defaults.
- **Partial writes:** capability 3 forbids partial reply files.
- **Probe:** it covers a non-zero exit, a timeout and a missing `sq`, each bounded by `--sq-timeout` and mapped to exit code 7.
- **Live waits:** they are bounded.
- **Cost cap:** the architecture's `max_cost_usd` bound is restated in D7 with a positive-value requirement and per-run isolation through `.squadron.toml`.
- **Rules block:** the unnumbered, uncitable `rules_dir` hole is closed by D7 and checked through the prompt files.

### [PASS] Proportionality is acceptable

The module count is small, and the live tier is opt-in and fails loudly instead of skipping or defaulting. Everything in the slice maps to a plan success criterion. The only candidate to trim is the draft Verification Walkthrough. It restates test content and is marked "refined after Phase 6", so it can be shortened when that refinement happens.

### Run Digest

- Response length: 7546 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 275380 / 176910 / 98462 / 6396 / not computed
- Duration: 55.0 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
