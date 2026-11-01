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
reviewedSha: f9f2cf393a7aa2615c57441f5c1d08ff59ba7e5b
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 101457
cachedTokens: 11162
cacheWriteTokens: 90291
completionTokens: 4604
durationSeconds: 41.1
costUsd: 0.409167
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Boundaries, dependency direction and gate behavior match the architecture"
    location: "project-documents/user/slices/145-slice.live-walkthrough.md#Technical Scope"
  - id: F002
    severity: concern
    category: under-specification
    summary: "Case 4's precedence check depends on passage-date precision the slice never states"
    location: "project-documents/user/slices/145-slice.live-walkthrough.md#D4 — Case 4 uses the answer limit to send the exception to the PM"
  - id: F003
    severity: concern
    category: proportionality
    summary: "The Verification Walkthrough duplicates the doc and is declared as allowed to drift"
    location: "project-documents/user/slices/145-slice.live-walkthrough.md#Verification Walkthrough"
  - id: F004
    severity: note
    category: scope
    summary: "`docs/process-contract.md` link is a success criterion but not in Technical Scope"
    location: "project-documents/user/slices/145-slice.live-walkthrough.md#Integration Requirements"
  - id: F005
    severity: note
    category: proportionality
    summary: "Real-registry hash guard is the heaviest part of the setup script"
    location: "project-documents/user/slices/145-slice.live-walkthrough.md#D6 — Repeatable from the repository"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure modes for the new I/O paths are enumerated with handling"
    location: "project-documents/user/slices/145-slice.live-walkthrough.md#D7 — Each case runs once; a wrong outcome is a recorded finding"
---

# Review: slice — slice 145

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Boundaries, dependency direction and gate behavior match the architecture

The slice only consumes 140–144 (the Runner stage, the question record, the gate, 143's assembly, and 132's drive and resume). Defects found become issues (D7) instead of fixes inside 140–144. D3 relies on the arch's design that the screen is "a net after the model said yes", and uses explicit `reserved_terms` with no defaults, as the arch requires. D4's `answer_limit_reached` path follows the arch's "asked after its run reached the answer limit is declined". Only PM answers become passages. The slice also treats a rule changed after a PM answer as overriding it, which is the arch's date precedence.

### [CONCERN] Case 4's precedence check depends on passage-date precision the slice never states

The arch's precedence rule is "by date". A rules passage carries the date of its file's last commit, and a PM answer carries the date it was given. Case 4 commits the rule and gives the PM answer within one sitting. Slice 105's success depends on the PM passage being strictly later than the rule. The Case 4 success criterion also requires `passage_index` to show the rule's date before the PM answer's. If 143 records dates at day granularity, both passages carry the same date. The check step then sees a tie, and the arch does not say how a tie is resolved, so the case would end in `check_said_no` for a reason unrelated to the answerer's logic. The slice should state 143's date precision, which it consumes. If the precision is a day, it should add a step that guarantees the ordering, or the expected record should say what a tie produces. D7's "model judgement" rerun does not cover this, because the rerun would hit the same tie.

### [CONCERN] The Verification Walkthrough duplicates the doc and is declared as allowed to drift

D6 says `docs/answerer-walkthrough.md` is the only full walkthrough. The Verification Walkthrough section then restates the per-slice expected records and PM answer texts in a table, and the doc says it "is not kept in step". Those are the same facts as the Success Criteria (Cases 1–4), D3, D4 and the forcing-sentence table. The PM answer strings now live in two places in this document and in a third, the doc. Cut the Verification Walkthrough to the fixture-test command, the setup and start commands, and a pointer to the doc. The Success Criteria already carry the expected outcomes. This also follows the "define once" principle.

### [NOTE] `docs/process-contract.md` link is a success criterion but not in Technical Scope

Integration Requirements require that `docs/process-contract.md`'s answerer section links the walkthrough doc. The "Included" list in Technical Scope does not name that edit, so a task breakdown driven from scope could miss it. Add it to the Included list.

### [NOTE] Real-registry hash guard is the heaviest part of the setup script

The hash guard has to locate the real registry directory through the user's environment or Amoeba's settings default, and it has its own failure branches. It protects an invariant that 132's walkthrough already set, and the arch does not require it. It is defensible, since the real registry must never be written. If effort needs trimming, this is the first candidate. Pointing `CONTEXT_FORGE_DATA_DIR` at `D/cf` in every spawned process already gives the isolation, and the hash check only confirms it afterward.

### [PASS] Failure modes for the new I/O paths are enumerated with handling

Setup-script failures (non-zero subprocess, missing cf project id, missing live variable, existing `D`, missing `projects.json`) stop the script, report the step and leave `D` in place. Live failure classes are separated into fixture cause, product cause, model judgement and environment (`failed`, `orphaned`, stall). Each has a rerun or `BLOCKED:` rule. The missing Squadron D8 capability is covered by `BLOCKED:` tasks and the start-up probe. The arch has no numeric NFR for this path, so none needs restating.

### Run Digest

- Response length: 5083 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 101457 / 11162 / 90291 / 4604 / not computed
- Duration: 41.1 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
