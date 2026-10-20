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
reviewedSha: 8d2aca07cb762d2adb27d995df3987db31f008a4
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 199349
cachedTokens: 98560
cacheWriteTokens: 100783
completionTokens: 4543
durationSeconds: 39.7
costUsd: 0.459235
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: under-specification
    summary: "Table-edit proposals have no path for wrong stops that have no routing decision"
    location: "project-documents/user/slices/129-slice.first-proof.md#D7 — Wrong stops that become table edits"
  - id: F002
    severity: concern
    category: success-criteria
    summary: "D3's miss fallback contradicts the SIGKILL success criterion"
    location: "project-documents/user/slices/129-slice.first-proof.md#D3 — The restart is a SIGKILL with P6 in flight"
  - id: F003
    severity: note
    category: scope
    summary: "`inspect resolutions` adds a store read to 100's contract"
    location: "project-documents/user/slices/129-slice.first-proof.md#D6 — `amoeba inspect resolutions`"
  - id: F004
    severity: note
    category: proportionality
    summary: "Post-edit restart recompute check is weak by design"
    location: "project-documents/user/slices/129-slice.first-proof.md#Verification Walkthrough (step 8)"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Alignment with architecture boundaries and the plan entry"
    location: "project-documents/user/slices/129-slice.first-proof.md#Technical Scope"
---

# Review: slice — slice 129

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Table-edit proposals have no path for wrong stops that have no routing decision

D5 lets any `wrong` row propose a table edit. Some rows have no routing decision, only a fault kind. That is the "block with no decision" case in D5's row format. The architecture escalates every fault in v1 and says a retry class for transient faults is added only after the first proof. So a fault stop cannot be fixed by editing `default.yaml`. It needs new table inputs or code, which makes it a follow-on slice or Future Work 2.

D7 builds its test from recorded decision inputs. A fault-stop edit would have no fixture, so the check that "nothing else changes" cannot cover it.

Fix: state in D5 or D7 that a `wrong` row with no decision record can only propose a follow-on slice or a code issue, never a table edit. Alternatively, say how such an edit would be fixtured. This keeps the "one edit point for routing" boundary clear and makes the "every wrong stop has exactly one proposal" criterion verifiable.

### [CONCERN] D3's miss fallback contradicts the SIGKILL success criterion

The slice plan requires that "a restart of the resident process during the proof leaves the run completable." Functional Requirements restate this as "One SIGKILL with P6 in flight: … the unit completed." D3 then allows that if no run remains in flight, "the write-up records the miss". Under that fallback the criterion is unmet, but the slice could still be declared done.

Fix: choose one of two options.
- Make the miss a failure of the slice. The kill must land on some in-flight run, and the PM may need to hold the unit back, or choose a unit whose P6 is long enough, until it does.
- Say explicitly that a miss defers the crash proof, and name where it is proven. 122's crash proof already covers the no-op case, but not a real run.

The first option matches the plan.

### [NOTE] `inspect resolutions` adds a store read to 100's contract

This is the only new code in the slice, and the plan entry for 129 does not list it. D6 justifies it: issue #16 was deferred for exactly this read-out, the read is additive and read-only, and it serves operators rather than the Runner. It does not breach the contract-first rule, and the explicit "no proof harness or report generator" exclusion keeps it from growing. No change needed. Keep the store read and its `docs/store-contract.md` text in one task so the contract and the code land together.

### [NOTE] Post-edit restart recompute check is weak by design

The doc says that recompute after the D7 edit "says nothing about the edit". It only shows that the stored first table version survived a restart. That still serves the architecture's goal that any decision can be recomputed from its stored table version. It is one command in a walkthrough that already restarts the process, so it is not worth cutting. Be careful that Success Criteria wording does not present it as evidence the edited table is correct. The D7 test carries that evidence.

### [PASS] Alignment with architecture boundaries and the plan entry

- **Boundaries.** The slice only consumes Runner surfaces. A defect in 120–128 goes through the Fixes rule (D9) instead of being worked around, and the Runner's no-merge, no-push and no-branch-delete rules are preserved. The PM merges at the human step.
- **Single edit point.** D2 fixes one table version per run. D7 limits changes to table edits and sends any new routing input, such as a tier, to 131.
- **Deferred questions answered.** Issues #12 and #13, Future Work 2 and 10, and 126's time bounds are answered from the run. Judge-eligible escalations are collected as 140's first evidence.
- **Proof checks the architecture's invariants.** It checks recompute under a stored table version, recovery of an in-flight detached run across SIGKILL, and "nothing run by hand". The last uses store evidence plus a PM log, and the design states what the store cannot detect.
- **Failure modes for the new I/O path.** `inspect resolutions` is read-only. The design covers the unacknowledged-resolution case and the schema-mismatch exit. Defects found mid-proof are handled by D9, including the unrecoverable-unit case.

### Run Digest

- Response length: 5132 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 199349 / 98560 / 100783 / 4543 / not computed
- Duration: 39.7 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
