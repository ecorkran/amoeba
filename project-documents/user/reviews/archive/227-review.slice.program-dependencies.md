---
docType: review
layer: project
reviewType: slice
slice: program-dependencies
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/227-slice.program-dependencies.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: a3dd824911e12ffecc1a0ed47156b32816393676
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 12
effort: high
turns: 13
promptTokens: 826073
cachedTokens: 712574
cacheWriteTokens: 113481
completionTokens: 9180
durationSeconds: 80.4
costUsd: 0.61786
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: architecture-alignment
    summary: "Report identity is narrower than the architecture's, and the difference is not flagged"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#D2 — Report identity and repeats"
  - id: F002
    severity: concern
    category: integration
    summary: "The starting-point gap sits in scenario B's main timing"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#D4 — The starting point belongs to the caller"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Overweight material that can be cut or deferred"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#Verification Walkthrough"
  - id: F004
    severity: note
    category: verification
    summary: "The \"integration requirement\" depends on events outside the slice"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#Integration Requirements"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Layering, dependency direction and scope"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#Architecture"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure modes for the new I/O paths"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#D2, D3, D5"
---

# Review: slice — slice 227

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Report identity is narrower than the architecture's, and the difference is not flagged

The architecture (Decision 3) and the slice plan entry both key a report on "member, commit and version". D2 keys it on member and commit (222's `UNIQUE (member_id, commit_sha)`). It also makes a version belong to one commit per member, enforced in code and not by the schema. So a commit with two versions, or a version that moves to another commit, returns `version_conflict` and is "fixed by hand in SQLite".

- A release candidate promoted to final on the same commit is a common flow, and it is refused.
- The design calls this rare, and that may be right. But it changes the architecture's stated identity, and neither the slice nor the architecture says so.
- Do one of two things. Record the narrowing in the architecture's Decision 3. Or allow a later version on an already-versioned commit, and state how `from_release` consumers see it.

### [CONCERN] The starting-point gap sits in scenario B's main timing

D4 admits a known gap. A provider reports after a consumer's slice design but before that slice merges. The report then falls before the next design's `since`, so no design is shown it.

- A provider merging while a consumer implements a slice is the ordinary case for scenario B, not an edge.
- The architecture accepts a soft starting point, and "errs toward showing more" is the stated bias. Yet the chosen rule (last merge on the branch) misses this case by construction.
- Either pick a `since` that covers it, or make the gap measurable. Walkthrough step 8 should explicitly record any report a design should have seen and didn't, as evidence for `#304`.
- Currently step 8 only checks that the Dependencies section records what `changes` returned.

### [CONCERN] Overweight material that can be cut or deferred

Several parts restate other sections or other slices' work.

- **Walkthrough steps 6 and 7.** Step 6 repeats D7's visibility and non-member tests. Step 7 repeats 226's parity and stdio coverage. Keep only what needs real tools: the scratch program, the CLI round trip, and step 8's real use.
- **D6 rule-line text.** The full drafts appear in D6 and will appear again in `docs/program-rules.md`. The slice could name each line's required instructions and leave the wording to the doc. The rule-line test already guards the instructions.
- **Edits to shipped slices.** The design changes 224's `decisions` (via `since.py`), adds a `clock` field to 226's `OperationDeps`, and edits a 226 test assertion. The `parse_since` extraction is justified on DRY grounds. But the "224's tests must pass unchanged" condition and the stdio change add coordination cost, so keep them as small as possible.
- **Contract docs.** D8 updates four documents. The `consumed`-choice paragraph in `program-rules.md` belongs to 222's `set_up` contract, so a pointer there is enough.

### [NOTE] The "integration requirement" depends on events outside the slice

The plan assigns the criterion that the rule lines lead a design agent to call `changes` in a real run, so it belongs here. Completing it needs a real provider merge and a real design. Implementation Notes already treat step 8 as recorded "when it happens", which keeps the slice from stalling on it. Say plainly whether the slice can close before step 8 happens.

### [PASS] Layering, dependency direction and scope

- `cli` and `mcp` → `operations` → `store` is unchanged, and `store/releases.py` imports nothing from `operations`.
- The slice adds no table, no migration and no `set_up` change.
- It marks nothing read, follows no graph beyond direct pairs, and runs no `git` from Amoeba. That matches "pull, never push" and "never walks the graph".
- The exclusions (the pipeline step `#304`, report removal) match the architecture and the slice plan.
- The two operations and three rule lines match plan entry 227's scope.
- The `consumed` semantics match the architecture: `from_source` sees every report and `from_release` sees only versioned ones. The tag-on-reported-commit behavior also matches.
- The 226 tool counts are consistent: 226 lists six tools, and this slice makes eight.

### [PASS] Failure modes for the new I/O paths

- **Store writes.** Concurrent reports are serialized by `BEGIN IMMEDIATE`. An `IntegrityError` is deliberately treated as a bug and not swallowed, which fits the project's exception rules.
- **`cf` calls.** All `cf` calls happen before the write. A failure becomes `ContextForgeError`, exit 3. A provider id missing from the `cf` list also raises, as in 224.
- **Input errors.** Malformed input, non-members and version conflicts each get a typed rejection with detail.
- **Soft rule lines.** The consumer line says a failed call is never "no changes". The provider and release-skill lines say to surface a non-zero exit and not retry with different values.
- **Not restated.** The slice does not restate any `cf` call timeout. It inherits that from the 222 and 224 runners, which is acceptable.

### Run Digest

- Response length: 6251 chars
- Response is newline-free: no
- Tool calls made: 12
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 13
- Tokens — prompt / cached / cache write / completion / reasoning: 826073 / 712574 / 113481 / 9180 / not computed
- Duration: 80.4 s
- Cost: $0.62 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
