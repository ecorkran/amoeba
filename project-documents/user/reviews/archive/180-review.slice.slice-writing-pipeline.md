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
reviewedSha: 29e49859f830d291491e1da103ce920bb229a9ce
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 104044
cachedTokens: 11162
cacheWriteTokens: 92878
completionTokens: 5612
durationSeconds: 48.3
costUsd: 0.429599
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Layer boundaries and edge/binding responsibilities match the architecture"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md#Technical Scope"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Disagreement between the reply and what the agent wrote is not handled"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md:153-157"
  - id: F003
    severity: concern
    category: under-specification
    summary: "D2 and D3 contradict each other on git"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md:150"
  - id: F004
    severity: concern
    category: scope
    summary: "Proportionality: refactors of 140 code and test layout can be cut or deferred"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md:54, 99, 228"
  - id: F005
    severity: note
    category: dependency
    summary: "The launch contract rests on Squadron options that do not exist yet"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md:261-267"
  - id: F006
    severity: note
    category: security
    summary: "Agent actions outside the checkout are bounded only by instruction"
    location: "project-documents/user/slices/180-slice.slice-writing-pipeline.md:134"
---

# Review: slice — slice 180

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Layer boundaries and edge/binding responsibilities match the architecture

- **Boundaries:** Amoeba never edits the provider's plan directly. The shipped pipeline runs in the provider's checkout on the target.
- **Parsing and binding:** `read_reply` checks shape only (D7). The new-index binding check stays with 184, and observing an already-met commit stays with 183.
- **Satisfaction:** An already-met commit is evidence only, never satisfaction (D3), as the architecture requires.
- **Pipeline contents:** Squadron owns the commit guard, and the Runner issues no new command kind.
- **Request slices:** The initiative-creation path and standalone request slices (no dependencies) match the architecture's description.

### [CONCERN] Disagreement between the reply and what the agent wrote is not handled

D3 says an `already_met` run "writes nothing", but nothing enforces that. The commit guard (D5) allows any change inside the two plan globs. If the agent edits a plan file, for example by creating the initiative or adding an entry, and then replies `already_met`, the commit step commits it. The result is a phantom slice or initiative on the provider's target, and the reply says nothing was written.

184's binding check only runs for `new_slice`, so nothing catches this case.

Name the handling:
- Either 184 treats `already_met` as invalid when HEAD moved, or `read_reply`'s contract states that callers must compare HEAD before and after a run.
- The live tier's already-met case already asserts "no new commit". Say that this assertion is also the runtime rule.

### [CONCERN] D2 and D3 contradict each other on git

D2 lists "No git commands" under Forbidden. D3 says the agent must take the commit hash from `git log`, and that "read-only git is part of reading the repo". The instructions the agent receives need one rule. Restate D2 as "no git writes; read-only git is allowed". Also state that the guard is the only enforcement of the write ban, because there is no tool restriction (D1).

### [CONCERN] Proportionality: refactors of 140 code and test layout can be cut or deferred

The deliverable is a pipeline, an input contract, a reply parser and a probe. Three items are not needed for it:
- **`shipped_pipelines.py` extraction.** It moves `answering_pipeline_path` onto a new module and touches 140's code and wheel test. A second three-line `importlib.resources` call in `request_run/pipeline_file.py` meets the requirement. Defer the extraction until a third pipeline exists.
- **Shared validate-and-raise helper.** `probes.py` is extended with a helper shared with `probe_answering_pipeline`. This is also a refactor of 140 code. The new probe can call `run_cf` and `output_head` directly and keep its own message.
- **Per-subdirectory live settings split.** The split edits `tests/live/answering`. A new `tests/live/request_run/conftest.py` meets the need if the existing answering variables are read only under `answering/`.

Cut these, or justify why they must land with this slice. The slice plan entry was not checked for assignment of any of them.

### [NOTE] The launch contract rests on Squadron options that do not exist yet

- **Proposed options.** The launch argv (`--io-dir`, `--max-cost`) and the YAML keys for the commit step are proposals.
- **What 184 needs.** 184 consumes this argv as a contract. The "finalize against shipped syntax" task is the right mitigation.
- **Tasks that wait.** The tasks that need real runs should carry `BLOCKED:` lines, as D8 and Dependencies state.
- **Hand-off.** State in the slice plan and process contract that the argv is provisional until that task completes, so 184's design does not freeze on it.

### [NOTE] Agent actions outside the checkout are bounded only by instruction

D1 states plainly that the commit guard does not bound actions outside the checkout. Those actions include `cf set` writes to the registry, pushes and network calls, and the instructions are the only limit on them.

The reasoning is the same exposure as the provider's own pipeline runs, so this is acceptable. If the live tier is ever extended, add an assertion that the CF registry and the remote refs are unchanged after a run. The walkthrough already checks the registry for scratch projects.

### Run Digest

- Response length: 5318 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 104044 / 11162 / 92878 / 5612 / not computed
- Duration: 48.3 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
