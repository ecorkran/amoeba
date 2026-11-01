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
sourceDocument: project-documents/user/slices/145-slice.live-walkthrough.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: 3fe43648f13ad1d75160a02dfb17b9ebbf076dbe
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 189444
cachedTokens: 93195
cacheWriteTokens: 96243
completionTokens: 6942
durationSeconds: 60.4
costUsd: 0.464563
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Cases map to the architecture's goals and boundaries"
    location: "project-documents/user/slices/145-slice.live-walkthrough.md#Technical Scope"
  - id: F002
    severity: concern
    category: proportionality
    summary: "The walkthrough text is kept in several copies"
    location: "project-documents/user/slices/145-slice.live-walkthrough.md:180"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Setup script failure handling covers only some of its I/O"
    location: "project-documents/user/slices/145-slice.live-walkthrough.md:179"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Environment failures of the design runs have no handling"
    location: "project-documents/user/slices/145-slice.live-walkthrough.md:184-191"
  - id: F005
    severity: note
    category: hidden-dependency
    summary: "Registry check path is written as a literal"
    location: "project-documents/user/slices/145-slice.live-walkthrough.md:281-283"
  - id: F006
    severity: note
    category: dependency
    summary: "Live tasks depend on a Squadron release that does not exist yet"
    location: "project-documents/user/slices/145-slice.live-walkthrough.md:64"
---

# Review: slice — slice 145

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Cases map to the architecture's goals and boundaries

- **Required cases:** The architecture's "Live walkthrough" entry asks for a real question answered with the run completing, and a PM-reserved question declined. Cases 1 and 2 cover both.
- **Added precedent cases:** Cases 3 and 4 live-test two stated design goals. One is "a question the PM already answered stays answered". The other is that a later PM answer stands against an older rule by date. Nothing else in the plan exercises those goals against a real agent.
- **Boundaries:** Nothing is added under `src/`. A defect found in 140–144 becomes an issue, so 145 does not leak into other slices' code. Dependencies point from 145 to 144 and 140–143.
- **Gate and screen:** D3 uses the screen as the fixed net that works after the model says yes, as the architecture describes. D4 uses the answer limit, so case 4 does not depend on model judgement.
- **Date precedence:** Slice 143 renders dates to the second (`%cI`, converted to UTC). The rule commit and the PM answer in case 4 are minutes apart, so the strict ordering the slice expects is realistic.

### [CONCERN] The walkthrough text is kept in several copies

- **Copies:** The Verification Walkthrough (lines 275–355) is about 80 lines of commands and expected records. D6 says `docs/answerer-walkthrough.md` carries the same text, and Implementation Notes step 5 updates the LLD walkthrough as a third copy. Each copy has to be revised after Phase 6, and the doc says its copies "stay the same text".
- **What to cut:** Make `docs/answerer-walkthrough.md` the only full walkthrough. Reduce the slice's Verification Walkthrough to a short case-to-expected-record table with a link to the doc. This removes two copies and the sync task without losing any scope.
- **Not a cut:** Slice 100's case 1 overlaps with 104's first question, which is also answered from the concept. Case 1 is a plan-assigned case, so I would keep it.

### [CONCERN] Setup script failure handling covers only some of its I/O

- **Covered failures:** The script names three failures: `D` exists, a live variable is unset, and the CF project id is absent from `cf get` output.
- **Uncovered failures:** It also calls `git init` and commit, `cf init`, `amoeba submit create-project` and `link-cf-project`. The design does not say what happens when one of those exits non-zero partway through.
- **Why it matters:** A mid-way failure leaves `D` partly built. The refuse-existing-`D` rule then blocks a rerun, and nobody is told to remove `D`.
- **Fix:** State that any non-zero subprocess exit stops the script with the command, its stderr and the step that failed. State also that it names the leftover `D` and never deletes it. This follows the project rule against silent fallbacks.

### [CONCERN] Environment failures of the design runs have no handling

- **Current taxonomy:** D7 sorts wrong outcomes into three causes: fixture, product and model judgement. Special Considerations adds only the `p4` review loop that never passes.
- **Gap:** A `p4` run can also end `failed` or orphaned, or on a provider error, a missing key in the checkout `.env`, or a stall. These are not questions. They never reach the answerer, and no case can complete.
- **Fix:** Add one line to D7. An environment failure of a design run is recorded with its outcome and the run is repeated on a fresh slice index. A repeat failure becomes a `BLOCKED:` on the cause, not a finding against the answerer.

### [NOTE] Registry check path is written as a literal

Step 0 hashes `~/.config/context-forge/projects.json`. If CF's real registry lives elsewhere, `shasum` fails or hashes a file that is not the real registry, and the isolation check proves nothing. The doc should say to take the path from CF's own output, as the script does for the project id, and to stop if CF does not report one.

### [NOTE] Live tasks depend on a Squadron release that does not exist yet

The design says plainly that steps 3–8 carry `BLOCKED:` lines until a release with 140's D8 capabilities is installed. It also orders the build so the tree, test, script and doc come first. The slice cannot finish before that release, but the sequencing is sound and no change is needed.

### Run Digest

- Response length: 5052 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 189444 / 93195 / 96243 / 6942 / not computed
- Duration: 60.4 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
