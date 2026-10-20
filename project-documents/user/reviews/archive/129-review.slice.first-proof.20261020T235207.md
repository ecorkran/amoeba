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
reviewedSha: 116ba04e86839cb35b5922deab45d33c33c05d68
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 286536
cachedTokens: 188239
cacheWriteTokens: 98289
completionTokens: 4902
durationSeconds: 42.7
costUsd: 0.461821
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: architectural-alignment
    summary: "Alignment with the architecture and the slice plan's 129 entry"
    location: "project-documents/user/slices/129-slice.first-proof.md#Technical Scope"
  - id: F002
    severity: concern
    category: verification
    summary: "\"Two stored table versions\" cannot be met by a restart alone"
    location: "project-documents/user/slices/129-slice.first-proof.md#D7 and Success Criteria (Functional Requirements) and Verification Walkthrough step 8"
  - id: F003
    severity: concern
    category: verification
    summary: "Walkthrough step 9 cannot be run against the finished unit"
    location: "project-documents/user/slices/129-slice.first-proof.md#Verification Walkthrough step 9"
  - id: F004
    severity: note
    category: auditability
    summary: "D4's detection evidence covers only some hand-run commands"
    location: "project-documents/user/slices/129-slice.first-proof.md#D4"
  - id: F005
    severity: note
    category: scope
    summary: "`inspect resolutions` adds a store-contract change in the last slice"
    location: "project-documents/user/slices/129-slice.first-proof.md#D6"
  - id: F006
    severity: note
    category: dependencies
    summary: "Squadron-side dependency 106 is listed only under Interfaces Required"
    location: "project-documents/user/slices/129-slice.first-proof.md (frontmatter dependencies; Interfaces Required)"
---

# Review: slice — slice 129

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Alignment with the architecture and the slice plan's 129 entry

- Every success criterion in the plan entry has a counterpart in the design.
  - A merged unit with nothing run by hand is covered by D4.
  - Recomputable decisions are covered by the recompute audit.
  - A restart that leaves the run completable is covered by D3.
  - The write-up with one proposal per wrong stop is covered by D5.
  - The operator documentation is covered by D8.
- D7 keeps routing changes in the table. A proposal that needs a new input, such as a tier, goes to 131. This matches the architecture's "one edit point" and "tier inference after the first proof" rules.
- D2 and D9 match the table-is-static and restart-is-safe principles. The Runner never merges, deletes branches or pushes.
- The slice adds no persistent state, and the judge-eligible evidence for 140 is captured as the plan requires.

### [CONCERN] "Two stored table versions" cannot be met by a restart alone

- The architecture says "Each table version's full content is kept in the store the first time a decision uses it" (The table is static config).
- D7, the success criteria and walkthrough step 8 expect `inspect` to show two stored table versions after the edits are applied and the process is restarted. That restart happens after the unit has merged.
- Nothing is driven after the merge, so no decision is made under the edited table. The second version is never stored, and the criterion cannot pass as written.
- The same gap leaves "old decisions still recompute `yes` under their stored version" untested against a real second version. Step 8's recompute check only re-reads the first version.
- Fix: either (a) drop the "two stored versions" criterion and rely on the fixture tests, which already check old table against new table, or (b) name a post-edit action that produces one decision under the new table, such as an intent on a second unit or a re-evaluation. Option (a) is lighter and enough for this slice.

### [CONCERN] Walkthrough step 9 cannot be run against the finished unit

- Step 9 asks the reader to follow `docs/runner-guide.md` from scratch for steps 2–4, in a fresh supervisor directory, "with the unit's project".
- By then the unit is merged and `done`, so a drive intent finds nothing to drive. Step 4, answering stops, cannot be exercised at all.
- The step claims "each command in the guide works as written" and that steps 2–4 needed no knowledge the guide lacks. A fresh store on a finished unit cannot show either.
- This is also the heaviest verification step in a slice that is otherwise mostly an operation, and it repeats setup effort for a document.
- Fix: scope step 9 to what a finished unit supports. Run the setup commands (start, create-project, link-cf-project, watch-reviews, `inspect nodes`) in a fresh directory. Check each flag and default against `--help` and `settings.py`. Check the stop-answering sections against the D4 log from the real run.

### [NOTE] D4's detection evidence covers only some hand-run commands

- Detection's `ingested` outcome only catches a hand-run Squadron review that produces a reviewable artifact.
- A hand-moved CF pointer is detected only while a run is in flight (arch: "A pointer someone else moves changes nothing" unless a run is in flight). A hand-run `cf set` while idle leaves no trace in the store.
- The design already says the PM's D4 log is primary and the store evidence is the check on it. The success criterion "D4's evidence checks hold" could be read as stronger than that.
- Suggestion: have the write-up state which kinds of hand action the store can and cannot detect. Do not add tooling for this.

### [NOTE] `inspect resolutions` adds a store-contract change in the last slice

- This is the only new code in the slice, and the slice plan entry for 129 does not list it. It is justified by issue #16, which was deferred for this use. It is small, read-only, and follows the existing `inspect` pattern.
- The architecture says store-contract changes land ahead of the Runner. That rule is about what the Runner needs, and this read serves operators. It does not violate the rule.
- It needs the store-contract text update the design already includes. No action is needed beyond making sure the plan entry for 129 mentions it.

### [NOTE] Squadron-side dependency 106 is listed only under Interfaces Required

- `watch-reviews` and `inspect detections` come from 106, which sits outside this initiative. Frontmatter lists only 120–128, while "Interfaces Required" names 106.
- Either add 106 to the frontmatter or state that it was merged long before this initiative. The direction of the dependency is correct.

### Run Digest

- Response length: 5740 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 286536 / 188239 / 98289 / 4902 / not computed
- Duration: 42.7 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
