---
docType: review
layer: project
reviewType: slice
slice: edges-and-release
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/183-slice.edges-and-release.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 92e82043d273dd4f795d631cc3e08ee366af8c5d
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 107422
cachedTokens: 11162
cacheWriteTokens: 96256
completionTokens: 5912
durationSeconds: 52.6
costUsd: 0.44611
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: concern
    category: architectural-alignment
    summary: "`resolve_edge` is accepted before the provider is `done`, and that satisfies the edge early"
    location: "project-documents/user/slices/183-slice.edges-and-release.md:195-201"
  - id: F002
    severity: note
    category: proportionality
    summary: "Proportionality: the design is heavy but mostly architecture-assigned"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#Technical Decisions"
  - id: F003
    severity: note
    category: integration
    summary: "Head recording depends on the edge being open before the provider's slice completes"
    location: "project-documents/user/slices/183-slice.edges-and-release.md:204-210"
  - id: F004
    severity: pass
    category: architectural-alignment
    summary: "Boundaries, ownership and dependency direction match the architecture"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#Architecture"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Failure modes for each new I/O path are enumerated with explicit handling"
    location: "project-documents/user/slices/183-slice.edges-and-release.md:186-193, 204-211, 256-272"
---

# Review: slice — slice 183

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] `resolve_edge` is accepted before the provider is `done`, and that satisfies the edge early

D4 accepts the PM's edge resolution "at any time", including before the providing slice is `done`. It then makes the edge `satisfied` and releases the asker.

- The architecture says a from-release edge "waits, **after the providing slice is `done`** or an already-met reply, on the PM's edge resolution". Satisfaction is therefore sequenced after provider completion.
- The first design goal is "Nothing runs against a change that has not landed."
- A premature confirmation would release the asker while the provider's slice is still `runnable` or in progress. The `provider_not_done` wait only shows the problem. It does not stop the release.
- The stated reason for accepting early is that refusing "would need the program inbox to open member stores". That reason doesn't hold. The inbox can record `release_confirmed_at` at any time, as designed. The waiting side already reads the provider's node state (D10, `provider_not_done`), so the stage can decide.
- Recommended fix: keep the inbox as written. Have the stage ignore `release_confirmed_at` until the provider is `done` (or the target is a `ProvidingCommit`). The confirmation then stays recorded and takes effect once the provider is done. This keeps the architecture's ordering at no extra mechanism cost.
- The same change settles which commit D4 records. The head will exist by then, so the "else the named commit, else none" fallback and the third release-instruction line ("the PM confirmed it is released (commit …)") need less hedging.

### [NOTE] Proportionality: the design is heavy but mostly architecture-assigned

Relative effort is 4, with two migrations, a new inbox kind, and changes to readiness, ingest, the plan stage, `finish.py` and listings. Nearly all of it traces to the architecture's "Edges and release" slice and its "Changes to 120/140". If trimming is needed, these are the candidates:

- **D10 rotation by `evaluated_at`.** It exists to prevent starvation under a budget refusal, but the budget only refuses in rare cases. A simpler alternative is to evaluate in stable order and rely on the budget being per-tick. This one is defensible as written.
- **`satisfied_target` and `satisfied_commit` on the edge.** Both are needed only for the instruction text.
- **`edges_providing` with the `states` parameter.** Only `open` is used (D5). The parameter is generality nothing calls yet.

None of these blocks the slice.

### [NOTE] Head recording depends on the edge being open before the provider's slice completes

D5 records a head only for slices named by `open` edges at `done` time. If an edge were created after the provider's slice was already `done`, the edge would wait `branch_head_missing` until the PM resolved the question block.

- The architecture makes this impossible for request slices. They are membership-driven only while an edge is open, and binding happens before they run.
- The 184 and 185 integration contract should say it explicitly: "the edge exists before the providing slice can complete". Otherwise a later producer could break it silently.
- Tests creating `ProvidingSlice` edges on already-`done` nodes would show this as `branch_head_missing`.

### [PASS] Boundaries, ownership and dependency direction match the architecture

- `runner/lifecycle` receives only a set of node ids and never imports the program store (D2). This matches "the program stage feeds 120's readiness; 120 does not read the program".
- The tick order (intents, resolutions acknowledged, program stage, readiness, `decide()`) matches the architecture. D9 relies on that order for PM supersession.
- Edge writes have one owner per column. The asker's tick owns everything except `release_confirmed_at`, which only the inbox tenant writes.
- Release writes in an order the owner finishes on the next tick: edge `satisfied`, then block resolution, then edge `released`. Each crash point is covered by a test.
- No new git verb is used. `log` and `merge-base` are already in the allowlist.
- Branch-head recording on both `done` paths (`record_runner_report` and hand completion) follows the architecture's "Changes to 120".
- `AnsweredBy.COORDINATOR` and its non-answerer treatment match the architecture's "Changes to 140".

### [PASS] Failure modes for each new I/O path are enumerated with explicit handling

- **Provider store, checkout or `cf` unreadable.** This becomes a stored wait reason (`provider_unreadable` or `read_failed`) and never an exit. A program store failure exits, as in 181.
- **Git exit codes.** `--is-ancestor` exit 1 is `not_on_target`, and any other nonzero exit is `read_failed`.
- **Budget refusal.** It leaves edges untouched and still counts them in `waiting`. For the head read, the entry stays unfinished this tick.
- **Git failure during head read.** It records a null head with `detail`, so the run's outcome is not held back.
- **Release interrupted between its writes, or a PM resolution racing release.** Both are handled (`block_resolved`, D9).
- **Resume impossible because the run is gone.** 120's block carries `resume_instructions` (D12).

The slice also restates the one-loop lag NFR in "Special Considerations".

### Run Digest

- Response length: 5866 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 107422 / 11162 / 96256 / 5912 / not computed
- Duration: 52.6 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
