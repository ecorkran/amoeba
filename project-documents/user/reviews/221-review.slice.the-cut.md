---
docType: review
layer: project
reviewType: slice
slice: the-cut
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/221-slice.the-cut.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 2b23e5d1b49c78202125c3b2244b2643b06ee1a7
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
effort: high
turns: 9
promptTokens: 398475
cachedTokens: 292424
cacheWriteTokens: 106041
completionTokens: 7232
durationSeconds: 62.8
costUsd: 0.526589
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency direction match the architecture"
    location: "project-documents/user/slices/221-slice.the-cut.md#Component Structure"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Migration plan carries throwaway re-pointing, and D6 adds a guard nothing requires"
    location: "project-documents/user/slices/221-slice.the-cut.md#Migration Plan"
  - id: F003
    severity: note
    category: dependencies
    summary: "Audit document is absent, so the layout and verdict predictions are unverified"
    location: "project-documents/user/slices/221-slice.the-cut.md#Technical Decisions"
  - id: F004
    severity: note
    category: integration
    summary: "`waits on 223` live tests are deleted now, and the restore duty on 223 is not in 223's plan entry"
    location: "project-documents/user/slices/221-slice.the-cut.md#D8 — Tests"
  - id: F005
    severity: note
    category: integration
    summary: "Directory-to-project resolution is promised to 222 without a criterion in this slice"
    location: "project-documents/user/slices/221-slice.the-cut.md#Provides to Other Slices"
  - id: F006
    severity: note
    category: architecture-alignment
    summary: "Value types are owned by `answering`, so the future store depends on the answering library"
    location: "project-documents/user/slices/221-slice.the-cut.md#D4 — Value types leave the old store"
---

# Review: slice — slice 221

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Layering and dependency direction match the architecture

`amoeba.answering → amoeba.upstream → stdlib/pydantic/pyyaml` fits "Read, don't mirror" and "Called, never calling around". Nothing resident, no store, no tick and no launcher is kept. The answer screen (`gate`) stays beside the pipeline, as the architecture's Technical Considerations require. `max_concurrent_runs` is dropped as the architecture specifies. The slice leaves the store, the config loader and the launch to 222 and 223, with no stubs (D2). The scope matches the slice plan entry for 221: the README, the old migrations, `slice_writing.yaml` and the live-test handling are all covered.

### [CONCERN] Migration plan carries throwaway re-pointing, and D6 adds a guard nothing requires

Step 2 moves the kept modules and value types. It then requires the old store and runner, which step 3 deletes, to import from the new locations "so that the old code keeps compiling". That edits code that is about to be deleted. The only reason is the self-imposed rule that every step ends with format, lint, typecheck and the full suite green. Step 1 also hedges: "or else leave it in place for that step". That leaves the delete boundary of step 1 unclear.

Cut: merge steps 2 and 3 into one "move, sever and delete" step with a single green gate, or delete before moving. Either removes the re-pointing edits and the "no signature change while old callers exist" bookkeeping. Green gates stay after step 1 and at the end.

D6 rule 2 (a third-party import allowlist for `answering` and `upstream`) is also not required by the architecture, the slice plan or the audit. It guards against a problem the slice does not have, since D6 itself notes that later packages set their own rules. Rule 1 (`upstream` does not import `answering`) and the audit scan already cover what this slice delivers. Defer rule 2 until a slice adds a heavy dependency.

### [NOTE] Audit document is absent, so the layout and verdict predictions are unverified

`user/analysis/220-analysis.code-audit.md` does not exist yet; `project-documents/user/analysis/` is empty. The slice names it as a hard prerequisite, so this is handled. D1 also supplies a correction path. D3, D4 and the Migration Plan table nevertheless name specific files and types as "decided". D2 predicts that `program/members.py` and the launch, stage and settle modules become `delete`. That departs from the architecture's current-state table ("`program/` is kept and reworked"). The architecture says the audit decides, and D2 points to the audit's section 10 for the reasons, which covers it. Re-check D3, D4 and the D2 predictions against the audit's section 10 when it lands.

### [NOTE] `waits on 223` live tests are deleted now, and the restore duty on 223 is not in 223's plan entry

The architecture says "the live answering tests stay and become the check on scenario A". D8 deletes the `waits on 223` files, expected to be `test_answering_run.py` and `stage_harness.py`. The slice plan entry for 221 allows this ("or the audit records why one waits on 223"). D8 mitigates it by requiring the audit entry to name the claim and the restore commit. The cost is that 223 inherits "restore each claim as part of the scenario A check". The 223 entry in the slice plan does not list that as a success criterion. Make sure 223's design picks it up.

### [NOTE] Directory-to-project resolution is promised to 222 without a criterion in this slice

The slice tells 222 that `upstream/context_forge` resolves a directory to its project. 222's plan criterion "two worktrees of one repo resolve to the same member" depends on that. 221's Success Criteria cover only the move, and the kept tests carry the behavior implicitly. If the kept `context_forge` tests already assert directory-to-project resolution, say so. Otherwise 222 should treat the claim as unverified.

### [NOTE] Value types are owned by `answering`, so the future store depends on the answering library

D4 puts `DeclineReason`, `AnsweredBy` and similar types in `amoeba.answering.values`, and 222's store imports them. The direction is store → answering → upstream, and the rationale is stated (rejecting a shared types package). It is acceptable, but it is a one-way commitment on 222's schema. If 222 needs record-only types, such as the question states, they stay in the store and must not flow back into `answering`.

### Run Digest

- Response length: 5382 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 398475 / 292424 / 106041 / 7232 / not computed
- Duration: 62.8 s
- Cost: $0.53 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

## Resolution

- **[PASS] Layering and dependency direction:** no change needed.
- **[CONCERN] Throwaway re-pointing and the D6 guard:** Merged Migration Plan steps 2 and 3 into one "move, sever and delete" step that runs the checks once at the end, so old code is never re-pointed. Replaced step 1's "or else leave it in place" hedge with a stated boundary: old code that imports a step 1 unit only loses those imports. Re-numbered the step references in the packaging note, the 5b mitigation and the Development Approach. Removed D6 rule 2 and the matching sentence in Component Structure. This is a removal, not a deferral: no slice needs the rule, so no issue was filed.
- **[NOTE] Audit absent, predictions unverified:** Development Approach step 1 now says to check D3, D4 and the D2 predictions against the audit's verdicts and section 10 before starting. The audit wins where they differ (D1).
- **[NOTE] Restore duty not in 223's plan entry:** Added a success criterion to the 223 entry in `220-slices.program-tool.md`: each live test that 221 deleted as `waits on 223` has its claim restored, from the commit the audit's section 8 names.
- **[NOTE] Directory-to-project resolution promised to 222:** I checked and the promise was wrong. No kept `upstream` module resolves a directory to its project; `resolve_checkout` maps a slice to a checkout. Provides to 222 now says that 222 builds this resolution for `set_up`.
- **[NOTE] Store depends on answering for value types:** D4 now says types that only a record uses, such as question states, belong to 222's store and never move into `answering`.
