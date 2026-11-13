---
docType: review
layer: project
reviewType: slice
slice: program-dependencies
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/227-slice.program-dependencies.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261112
dateUpdated: 20261112
reviewedSha: 172ef49fcbcdc675e4e5ee46ed1e6b0c34baff48
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
effort: high
turns: 7
promptTokens: 327193
cachedTokens: 203885
cacheWriteTokens: 123298
completionTokens: 10241
durationSeconds: 85.4
costUsd: 0.616919
costBasis: provider
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: design-risk
    summary: "Starting-point anchor uses committer time, which rebases and squashes rewrite"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:136-146"
  - id: F002
    severity: concern
    category: scope
    summary: "Edits that reconcile the architecture and plan with this slice are listed but owned by nothing"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:277-282"
  - id: F003
    severity: note
    category: error-handling
    summary: "`not_a_member` covers two different `resolve_member` outcomes"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:74"
  - id: F004
    severity: pass
    category: architecture-alignment
    summary: "Layering, dependency direction and the `cf`/write ordering"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#Architecture"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Pull-only model, no stored marker, direct providers only"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#D3"
  - id: F006
    severity: pass
    category: lifecycle
    summary: "Every state has an exit; operator dead ends are closed"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#Operator-Walkthrough"
  - id: F007
    severity: pass
    category: proportionality
    summary: "Proportionality"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#Technical-Scope"
---

# Review: slice — slice 227

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Starting-point anchor uses committer time, which rebases and squashes rewrite

D4 and the consumer rule block (D6) take `since` from `git log -1 --diff-filter=A --format=%cI`. `%cI` is the committer date. A rebase, cherry-pick, amend or squash-merge of the branch carrying the previous slice design sets the committer date to the time of the rewrite. That moves `since` later, and `changes` then skips every report between the real design time and the rewrite.

Nothing signals the loss. The call succeeds and returns `listed`, which is the "treated a gap as no changes" outcome the rule block forbids for failed calls. The flow test (D7) only sets `GIT_COMMITTER_DATE`, so it cannot catch this. Author date (`%aI`) survives all of these operations and is never later than the committer date, so a wrong `since` errs toward showing too much. Switch both commands and the flow-test dates to author date, and add one flow-test case that rebases the consumer's design commit and still sees the report.

### [CONCERN] Edits that reconcile the architecture and plan with this slice are listed but owned by nothing

"Pending Planning Edits" lists two edits and puts them "outside this slice". None of the six implementation steps performs them. The slice contradicts the parent documents in more places than those two edits cover:
- **Starting point.** Arch decision 4 says "usually its branch's last merge". The slice uses the creation of the previous slice design. This one is listed.
- **Slice plan entry 9.** Its stored-marker wording and its "real design run in the PM's repos" criterion are listed.
- **Scenario A gate.** Arch "Anticipated Slices" still says scenario B is "built only if scenario A passes its test". The plan dropped the trial, and this slice has no gate. Not listed.
- **Operations table.** Arch decision 2 describes `report_release` as recording a release only. The slice adds `correct` and `withdraw` modes. Not listed.
- **Versioning.** Arch decision 3 says versioning "adds the version". The slice replaces `changed` and `touched` on versioning (D2). Not listed.

The Amoeba design rules say to build in-scope work in the slice or delete it. Add the full edit list as a step in the D8 contract-docs step (step 5), so that when the slice merges the architecture and plan match what shipped.

### [NOTE] `not_a_member` covers two different `resolve_member` outcomes

`resolve_member` returns `NotInProgram` (a Context Forge project in no program) or `NotAProject` (a directory outside every Context Forge project, with Context Forge's message). The design maps both to `rejected / not_a_member` and does not say whether the detail tells them apart. The operator walkthrough has the agent record "outside every program", and a one-line detail per case would make that record accurate. This does not block anything.

### [PASS] Layering, dependency direction and the `cf`/write ordering

Imports run `cli`/`mcp` → `operations` → `store`/`upstream`, and the MCP rows add no per-tool adapter, matching "one operation, two doors". `resolve_member` makes its `cf` call before any store transaction, and `report_release` writes in one `BEGIN IMMEDIATE` transaction. This matches the architecture's "many short-lived writers" and restart-safe principles. SQLite busy-timeout failures follow 222's named-error criterion and exit 3.

### [PASS] Pull-only model, no stored marker, direct providers only

Nothing is marked read, no notifications are sent, and `changes` reads only the caller's direct pairs. This matches the principles "pull, never push" and "never walks the graph". The marker was dropped because a marker shared by all worktrees would hide changes from some of them, which supports the architecture's parallel-worktree goal. The `consumed` filtering matches architecture decision 3, including the `from_source` behavior that a later tag is not seen twice.

### [PASS] Every state has an exit; operator dead ends are closed

Report rows are bounded by commits. `withdraw` is the explicit cancel and `correct` fixes wrong text. A removed member's rows stay bounded by its history, and the design says so. Failure paths exit with the right codes: `cf` down gives 3, bad input gives 1, and a non-member gives `not_a_member` with nothing written. Both a flow test and a live test make integration verifiable without waiting on real use. The slice plan entry's required fixes are all present: correct/replace, a provider missing from `cf` as a warning rather than exit 3, and an automated integration check.

### [PASS] Proportionality

The effort of 3 matches the plan entry. There is no new table, no migration and no schema bump. The only change to 224 code is moving the `since` rule into `parse_since`, which avoids duplicating it. The three modes in one operation are the smallest change that closes the wrong-report dead ends. The test list is long, but each item maps to a named decision, so I see nothing to cut.

### Run Digest

- Response length: 6082 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 327193 / 203885 / 123298 / 10241 / not computed
- Duration: 85.4 s
- Cost: $0.62 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Resolution

- **[concern] Starting-point anchor uses committer time:** fixed. Both commands in D4 and the consumer block in D6 now use author time (`%aI`), which a rebase, cherry-pick or amend keeps. A squash would rewrite it too, but the project merges with a plain `git merge`, and D4 says so. The flow test sets author dates and gains a rebase case that fails if committer time is used (D7, task 6.1).
- **[concern] Reconciling edits owned by nothing:** fixed by doing them now, not leaving them to a step. `220-arch.program-tool.md` now has the `report_release` modes in the operations table, versioning replacing the text plus correction and withdrawal (decision 3), the explicit starting point (decision 4), and no gate in Anticipated Slices. `220-slices.program-tool.md` entry 9 has the starting-point wording and the new criteria. D8's "Pending Planning Edits" now lists what was applied.
- **[note] `not_a_member` covers two outcomes:** fixed. The detail says "this Context Forge project is in no program" for `NotInProgram` and "this directory is in no Context Forge project" plus Context Forge's message for `NotAProject`. The operator walkthrough records that.
- **[pass] Layering and ordering, pull-only model, every state has an exit, proportionality:** no action.
