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
reviewedSha: 342f9bdb980864e95295e1fe1bac3ca5b9b092e0
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
effort: high
turns: 9
promptTokens: 517331
cachedTokens: 402389
cacheWriteTokens: 114930
completionTokens: 7618
durationSeconds: 63.5
costUsd: 0.577004
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: architectural-boundary
    summary: "D2 deletes kept units, which contradicts D1 and the success criteria"
    location: "project-documents/user/slices/221-slice.the-cut.md:145-156"
  - id: F002
    severity: concern
    category: scope-gap
    summary: "Two audit outcomes are not carried out: `squadron` verdicts and the 182 take group"
    location: "project-documents/user/slices/221-slice.the-cut.md:42-61"
  - id: F003
    severity: concern
    category: proportionality
    summary: "The design is heavier than the cut needs"
    location: "project-documents/user/slices/221-slice.the-cut.md:84-110"
  - id: F004
    severity: concern
    category: architecture-alignment
    summary: "Deleting the \"waits on 223\" live tests drops the architecture's scenario A check"
    location: "project-documents/user/slices/221-slice.the-cut.md:207"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Dependency direction and layering match the architecture"
    location: "project-documents/user/slices/221-slice.the-cut.md:112-118"
  - id: F006
    severity: pass
    category: integration
    summary: "Interfaces to 222 and 223 match the slice plan"
    location: "project-documents/user/slices/221-slice.the-cut.md:262-266"
---

# Review: slice — slice 221

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] D2 deletes kept units, which contradicts D1 and the success criteria

- **The conflict:** D1 and the Excluded list say the audit decides verdicts and 221 only carries them out. D2 then names units to delete regardless of verdict: `answering/launch.py`, `stage.py`, `settle.py`, the store-writing half of `finish.py`, and (line 110) `program/members.py`.
- **Against the architecture:** The architecture expects these to be kept and reworked. It says `runner/answering/` keeps the pipeline, passages, decision logic and screen and "rewrite[s] its launching and polling". It says `program/` "is kept and reworked", and slice plan entry 222 provides "member resolution".
- **Against the success criteria:** Line 278 requires that "every `keep` and `rework` unit exists" at its D3 location. That cannot hold if an audit `rework` row is deleted in 221.
- **Missing procedure:** D1's correct-the-audit-row procedure is written for unexpected cases. It does not say that deleting an audit-`rework` unit under D2 needs the audit row changed in the same commit.
- **Fix:** State that D2 is a rule for the audit's `rework` rows, and that each such deletion changes the row to `delete` with a reason. Or ask the audit to mark these rows `delete`. Then drop the unit-by-unit "expected" lists, or label them as predictions only.

### [CONCERN] Two audit outcomes are not carried out: `squadron` verdicts and the 182 take group

- **The gap:** Audit D2 defines four verdicts: `keep`, `rework`, `squadron` and `delete`. The slice acts only on `delete`, and on `keep` and `rework`.
- **`squadron` rows:** Nothing says whether these units are removed from Amoeba in 221. The delete check in walkthrough step 2 filters only `delete` rows, so a `squadron` unit would stay in the repo with no one responsible.
- **Slice 182:** The audit sorts the 182 branch files into take, rewrite and drop. Excluded line 61 forbids only deleting branches. The slice does not say whether any "take" files are merged in 221 or left to 223.
- **Fix:** State in Technical Scope what 221 does with a `squadron` row and with the 182 take group. A one-line scope item for each is enough.

### [CONCERN] The design is heavier than the cut needs

- **Layout section restates the audit:** The layout lists expected `keep` and `rework` units from "a read of the code on 20261107", and then says the audit wins wherever they differ. That is a second copy of the audit's membership, and it will drift. Cut it to the D3 layout rules plus a pointer to the audit.
- **Cosmetic renames and merges:** The `TickBudget` to `CallBudget` rename, dropping `TickResult`, and folding `pipeline_resource.py` into `pipeline_file.py` are not needed to sever coupling. D2 lists only three allowed moves (Parameter, Move, Drop), and a rename is not one of them. The Scope bullet at line 49 allows a rename but does not name these. Defer them, or add them to D2 explicitly with a reason.
- **Redundant boundary rule:** D6 rule 3 says deleted packages must not exist and nothing may import them. It duplicates the audit's section 11 scan and the grep in walkthrough step 3. D6 itself says a later slice must narrow it. Drop rule 3 and the step 3 grep, and rely on the scan.
- **Unsupported rule 2:** D6 rule 2 limits third-party imports to `pydantic` and `yaml`. Nothing in the slice confirms the kept upstream readers meet that. If they don't, the rule would force an unplanned rework, so verify it or drop it.
- **Brittle awk script:** Step 2 of the walkthrough depends on the audit's table layout, and the document admits it ("Adjust `$3`").

### [CONCERN] Deleting the "waits on 223" live tests drops the architecture's scenario A check

- **The conflict:** The architecture says the live answering tests "stay and become the check on scenario A". D8 deletes the "waits on 223" files, expected to be `test_answering_run.py` and `stage_harness.py`. The slice plan allows this only if "the audit records why one waits on 223".
- **What D8 leaves open:** D8 relies on the audit's section 8 for 223 to restore the claims. It does not say that section 8 must record, for each deleted file, the claim it covers, so that 223 knows what to restore.
- **Fix:** Make the audit's section 8 entry for each deleted live file a stated precondition of deleting it. The entry should name the claim and the git revision to restore it from.

### [PASS] Dependency direction and layering match the architecture

`answering → upstream → stdlib, pydantic, pyyaml` keeps answering above the readers of other tools' state. This fits "read, don't mirror" and puts nothing between the library and the store that 222 adds. The answer screen stays beside the answering pipeline, as the architecture's technical considerations require.

### [PASS] Interfaces to 222 and 223 match the slice plan

- **222:** It gets `amoeba.answering.values`, `AnswererSettings`, and no console entry point.
- **223:** It gets the library entry points, `run_outcome.poll_run`, and the list of live tests to restore.
- **Fit with the plan:** D2 and D5 push store and settings concerns to 222, and launch and resume to 223. That matches the plan entries for those slices.
- **NFRs and failure modes:** No new I/O path or message type is added, so there are no new failure modes to list. The architecture states no NFR that applies to this slice.

### Run Digest

- Response length: 6510 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 517331 / 402389 / 114930 / 7618 / not computed
- Duration: 63.5 s
- Cost: $0.58 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
