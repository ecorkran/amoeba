---
docType: review
layer: project
reviewType: slice
slice: first-proof
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/129-slice.first-proof.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: c7975f6bcded6c3aaa889616ad2655503b721a4f
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 198033
cachedTokens: 98306
cacheWriteTokens: 99721
completionTokens: 6738
durationSeconds: 57.0
costUsd: 0.476911
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Alignment with the architecture's first-proof role and boundaries"
    location: "project-documents/user/slices/129-slice.first-proof.md#Technical Decisions"
  - id: F002
    severity: concern
    category: verification
    summary: "Table edits are verified only against the decisions they fix, and the post-edit recompute check cannot detect an edit's effect"
    location: "project-documents/user/slices/129-slice.first-proof.md:213-220"
  - id: F003
    severity: concern
    category: verification
    summary: "Walkthrough step 9 expects `done` steps in a fresh supervisor directory, which contradicts the plan's \"no partial progress inferred\" rule"
    location: "project-documents/user/slices/129-slice.first-proof.md:375"
  - id: F004
    severity: note
    category: failure-modes
    summary: "The D3 crash window is single-shot"
    location: "project-documents/user/slices/129-slice.first-proof.md:160-170"
  - id: F005
    severity: note
    category: dependency-direction
    summary: "The slice adds a store read to a contract the arch says changes first"
    location: "project-documents/user/slices/129-slice.first-proof.md:114-121"
  - id: F006
    severity: note
    category: proportionality
    summary: "Scope is proportionate"
    location: "project-documents/user/slices/129-slice.first-proof.md#Implementation Notes"
---

# Review: slice — slice 129

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Alignment with the architecture's first-proof role and boundaries

- The slice defers tier inference and batch dispatch to 131 and 130, as the arch orders.
- It requires table edits to stay table-only (D7: "an edit is a table change only"; a new routing input becomes slice 131), so no routing moves into code.
- It runs under the default human merge policy and leaves git writes to the PM, as the arch requires.
- It runs the Runner against a separate repository and never against the Runner's own checkout (D1).
- Decisions are recorded under a single table version (D2), which fits the arch's recompute-from-record principle.
- Its D3 SIGKILL-with-P6-in-flight test matches the arch's detached-launch and recovery design. Crashes between launch and confirmation stay in 122's proof.

### [CONCERN] Table edits are verified only against the decisions they fix, and the post-edit recompute check cannot detect an edit's effect

- **Rules are first-match-wins.** An edit that fixes one wrong stop can reroute a stop the PM classified `right`. The arch's "zero discretion, total auditability" goal means an edit must be shown not to disturb the decisions the PM accepted.
- **What D7 tests.** Fixtures are exported only for the `wrong` rows, and each test checks that one decision moves to the proposed rule.
- **What the recompute check proves.** The Success Criteria require every proof decision to recompute `yes` after the edits and a restart (lines 296, 373). Recompute reads the stored first table version (D2, D7), so it passes whatever `default.yaml` says. It verifies the store, not the edit.
- **Fix.** Export every proof decision's inputs, not just the wrong ones. Add one test that runs them all through the edited table. It should assert two things:
  - Every `right` decision keeps its route.
  - Each `wrong` decision changes only to its proposed rule.

  This stays in `test_first_proof_rules.py` and needs no new tooling. Reword the post-edit recompute criterion as a check on stored-version integrity, not on the edit.

### [CONCERN] Walkthrough step 9 expects `done` steps in a fresh supervisor directory, which contradicts the plan's "no partial progress inferred" rule

- **The expectation.** Step 9 sets up the guide's commands in a fresh supervisor directory and expects "the unit's steps show `done`".
- **The contradiction.** Slice plan Future Work 8 records that a slice partly done by hand has all its steps runnable, because the Runner infers no partial progress. A fresh store has no history of the proof, so steps would not show `done` from CF's plan alone. The merge step could be an exception if 128's git observation applies to it, but the slice does not say so.
- **Why it matters.** A guide-verification step that cannot pass as written will either block the task or push the author to weaken the guide.
- **Fix.** Replace the expectation with what a fresh directory can show. For example, the unit's node and step rows exist and nothing is driven. Alternatively, state exactly which steps 128's observation marks `done` and why.

### [NOTE] The D3 crash window is single-shot

- If P6 finishes before the PM can send `kill -9`, the crash criterion is missed and the unit cannot be re-run.
- D9 covers an unrecoverable unit, not a missed test window. Say what happens in that case. The simplest option is to repeat the SIGKILL during a later in-flight run on the same unit, such as a P6 rerun. The other option is to record the miss in the write-up.

### [NOTE] The slice adds a store read to a contract the arch says changes first

- The new resolved-blocks read in `docs/store-contract.md` changes 100's contract in the middle of the initiative.
- The arch says contract changes land ahead of the Runner. This one is an additive read that serves `inspect` and not the Runner, and 127 deferred issue #16 for exactly this purpose. I judge it acceptable and raise it only so it is a deliberate choice.

### [NOTE] Scope is proportionate

- Effort is 3/5, matching the plan, and most of it is the run and the write-up.
- D6 builds only one command and refuses a report generator. D8 states each rule once and links the contracts.
- The operator guide and the substrate guide close-out are the most cuttable pieces if time presses. I could not confirm from the slice plan text I could read whether the 129 entry assigns them, so I raise no finding.

### Run Digest

- Response length: 5352 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 198033 / 98306 / 99721 / 6738 / not computed
- Duration: 57.0 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
