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
reviewedSha: d81076d077daecfbf39899998ede7bf932cfa788
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 102873
cachedTokens: 11162
cacheWriteTokens: 91707
completionTokens: 4805
durationSeconds: 41.1
costUsd: 0.416845
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Boundaries and PM actions match the architecture"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md#D4 — PM actions are exactly the ones the architecture reserves"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure handling for live and setup paths is explicit"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md#D7 — Each case runs once; a wrong outcome is a recorded finding"
  - id: F003
    severity: concern
    category: coverage-gap
    summary: "The walkthrough tunes the screen config around a likely real refusal"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md#D5 — The walkthrough configuration"
  - id: F004
    severity: concern
    category: completion-criteria
    summary: "\"Shown in part\" closure conflicts with the slice's success criteria"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md#D7 — Each case runs once; a wrong outcome is a recorded finding"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Restated content that can be cut"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md#Verification Walkthrough"
  - id: F006
    severity: note
    category: dependencies
    summary: "Dependency on slice 145 is not declared"
    location: "project-documents/user/slices/186-slice.live-walkthrough.md:6-12"
---

# Review: slice — slice 186

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Boundaries and PM actions match the architecture

The slice drives coordination only through the existing CLI and inbox surfaces, and writes nothing under `src/`. The PM's actions are the architecture's reserved ones:
- The PM merges `notes-store`'s request slice branch (D4, D2).
- The PM submits `resolve-edge` for the from-release edge in case 3.
- Provider slices run undriven under membership drive.

`p456` for providers matches the architecture's rule that satisfaction is observed from the providing slice's `{index}-slice.{name}` branch head. Registry and supervisor isolation (D6, State Management) keep the real stores unwritten.

### [PASS] Failure handling for live and setup paths is explicit

D7 sorts failures into fixture cause, product cause, model judgement and environment, and gives each a response. Those responses cover rerun, issue, `BLOCKED:` and `stop`. The setup script's failure rules cover an existing `D`, a missing variable, a non-`applied` registration and a non-zero subprocess. The Squadron prerequisite is guarded by the 180 start-up probe. The architecture states no NFR on this path, so none needs restating.

### [CONCERN] The walkthrough tunes the screen config around a likely real refusal

D5 removes `release` from `reserved_terms` because a from-release need is likely to be worded with "release" and be refused before the request exists. The architecture says every cross-project need becomes work "without the PM carrying it", and the gate includes the PM-reserved screen. A real program with the default terms would hit the same refusal for ordinary from-release requests. The slice calls this "145's coverage, not this slice's", so the milestone-5 verification would pass without exercising, or even recording, that gap.

Keep the config change if you need it for case 3, but also do these:
- Add an explicit D7-style finding for it, or an issue against 185 and 145 if the screen refuses a legitimate from-release need.
- Note the deviation in `docs/program-walkthrough.md`.

### [CONCERN] "Shown in part" closure conflicts with the slice's success criteria

D7 lets a model-judgement miss close a case "as shown in part, with no issue and no `BLOCKED:`". Functional Requirements state Case 1, 2 and 3 outcomes without qualification. The slice doesn't say whether it can complete with a case shown only in part, or whether milestone 5's end-to-end claim then holds. Add a line stating the completion rule. For example: the slice is complete with a recorded partial case, and the doc marks that case as not demonstrated.

### [CONCERN] Restated content that can be cut

D6 says `docs/program-walkthrough.md` is "the only full walkthrough". The Verification Walkthrough nonetheless carries steps 1–5 with commands, expected rows and the git merge sequence. The Data Flow block also restates the internals of 183 and 184, such as `not_on_target`, `branch_head_missing` and the checkout rule. D7 re-explains 145's rules. The duplicated steps will drift once the doc is "updated to what was run". Cut the Verification Walkthrough to the fixture test command, the setup command and a pointer to the doc. Reference 183 and 184 for edge and request states rather than restating them.

### [NOTE] Dependency on slice 145 is not declared

The slice modifies `answerer_walkthrough.py` and its test, which 145 owns, and reuses 144's and 145's live variables and fixtures. The frontmatter dependencies list only 180–185. Add 145, and 144 for the fixture file, so the dependency graph shows the real coupling. Separately, the slice provides fixtures to 160 and 200, but `interfaces` is empty.

### Run Digest

- Response length: 4846 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 102873 / 11162 / 91707 / 4805 / not computed
- Duration: 41.1 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
