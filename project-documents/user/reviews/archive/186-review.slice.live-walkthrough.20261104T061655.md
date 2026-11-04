---
docType: review
layer: project
reviewType: slice
slice: live-walkthrough
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/186-slice.live-walkthrough.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: a91d43639383f25c3a996edf6b3e4b4de8bcf2a4
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 275997
cachedTokens: 180509
cacheWriteTokens: 95480
completionTokens: 3947
durationSeconds: 34.6
costUsd: 0.440299
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: concern
    category: integration
    summary: "D9 amends 183, but 183's design doesn't contain the amendment"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md:266-272"
  - id: F002
    severity: concern
    category: gate-interaction
    summary: "The `release` reserved term can refuse case 3 before the request is created"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md:195-217"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Shared-setup extraction from 145's script adds refactor scope; the slice doesn't show it is needed"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md:96, 236"
  - id: F004
    severity: concern
    category: proportionality
    summary: "The \"Expected record per case\" table and \"Interfaces Required\" restate other slices' contracts"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md:80-87, 299-315"
  - id: F005
    severity: note
    category: alignment
    summary: "Case 3 correctly covers the from-release path and the architecture's PM boundary"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md:171-181"
  - id: F006
    severity: note
    category: error-handling
    summary: "Failure handling for live runs is bounded"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md:243-252, 345"
---

# Review: slice — slice 186

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] D9 amends 183, but 183's design doesn't contain the amendment

D9 makes the edge id on `program-blocked` a prerequisite ("183's D13 amended per D9", Prerequisites). 183's current D13 (`183-slice.edges-and-release.md:289`) lists the edge row columns and says "the remaining columns empty". It has no edge id in `context`.

Case 3 and the Verification Walkthrough step 4 depend on that id, so 186 would be blocked.

Do the 183 edit first, or add it to 183's task list.

Two smaller mismatches show the two documents haven't been reconciled:
- 183 line 202 specifies `resolve-edge --by operator`, while 186 uses `--by pm` in D4 and step 4.
- 183 describes a satisfied edge as `satisfied: awaiting release`, while 186 expects `awaiting_release` as the case 3 wait.

Align both to 183's wording.

### [CONCERN] The `release` reserved term can refuse case 3 before the request is created

D5 sets `reserved_terms: [push, merge, release, DROP]` and claims the terms "exclude nothing a case needs". The program concept (Implementation Details) says `notes-export` "is released as a package". The answer step restates the need as a self-contained request and may carry that phrase. The PM-reserved screen would then decline the question instead of creating the request, and case 3 would fail for a fixture reason, not a coordination one.

The design checks the forced question text but not the concept text or the answer step's restatement. Either drop `release` from the walkthrough's reserved terms, or reword the concept, and have the fixture test assert the concept contains no reserved term.

### [CONCERN] Shared-setup extraction from 145's script adds refactor scope; the slice doesn't show it is needed

The slice moves 145's setup functions into `scripts/walkthrough_setup.py` and rewires `answerer_walkthrough.py` and its test. The DRY reason is sound. But it is a refactor of a shipped script inside a verification slice that is stated to change no product code. It also adds regression risk to 145 that nothing in the architecture asks for.

Either state that the extraction is the cheaper option because the functions are already parameterizable, or do it as a separate `refactor:` commit and keep it out of this slice's success criteria.

### [CONCERN] The "Expected record per case" table and "Interfaces Required" restate other slices' contracts

The table says column names "follow the listings as implemented". It also duplicates what `docs/program-walkthrough.md` is meant to hold, and what 181, 183, 184 and 185 already specify. The slice already says that where names differ, the doc uses the implemented names. That makes the table a second copy that can drift from the doc and from the slices it restates.

Cut it to the case-level observable outcomes already in Functional Requirements, and keep the per-step rows only in the walkthrough doc.

### [NOTE] Case 3 correctly covers the from-release path and the architecture's PM boundary

D4 limits PM actions to driving asker slices, the provider-branch merge, and `resolve-edge`. This matches the architecture's reserved steps: "a merge the provider's pipeline does not make, a release, and a block the PM must resolve anyway". D2's choice of `p456` for providers follows the architecture's `{index}-slice.{name}` branch-head rule.

### [NOTE] Failure handling for live runs is bounded

D7 classifies wrong outcomes into fixture, product, model and environment causes, each with a rerun limit and a `BLOCKED:` rule. The setup script's subprocess failures stop the run with the step, command and stderr. The design states the Squadron dependency as `BLOCKED:` and orders the non-live work first. No parent-architecture NFR applies to this slice.

### Run Digest

- Response length: 4630 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 275997 / 180509 / 95480 / 3947 / not computed
- Duration: 34.6 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
