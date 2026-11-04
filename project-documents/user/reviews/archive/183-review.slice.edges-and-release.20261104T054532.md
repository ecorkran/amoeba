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
reviewedSha: 5664277e48290a442155008a8769150282e29d98
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
turns: 8
promptTokens: 463577
cachedTokens: 364399
cacheWriteTokens: 99166
completionTokens: 6056
durationSeconds: 55.2
costUsd: 0.494528
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Tick order, readiness seam and layer boundaries match the architecture"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#Data Flow"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Cross-store release and supersession handle partial failure"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#Data Flow"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Design carries 184's producer plumbing that nothing in 183 uses"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#D1"
  - id: F004
    severity: concern
    category: scope
    summary: "Hand-completed providing slices record no head, narrowing the plan's \"recorded at `done`\" criterion"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#D6"
  - id: F005
    severity: concern
    category: integration
    summary: "Changes to 120 and 140 vocabulary go beyond what the architecture lists"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#D8"
  - id: F006
    severity: note
    category: boundaries
    summary: "The program inbox writes `release_confirmed_at` on an edge owned by the asker's tick"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#State Management"
  - id: F007
    severity: note
    category: error-handling
    summary: "D11's budget-refusal rule can starve later edges"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#D11"
---

# Review: slice — slice 183

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Tick order, readiness seam and layer boundaries match the architecture

The stage runs after resolutions are acknowledged and before readiness and `decide()`. An open edge is an external predecessor through `predecessors.py`. `runner/lifecycle` receives only a set of node ids. `decide()` is unchanged, and the coordinator never writes a desired-state row. All of this matches the architecture's principles "The program stage feeds 120's readiness" and "An edge is a predecessor". Every git and `cf` read sits in the Runner (`observe_edges.py`, `heads.py`), and inspection stays subprocess-free by reading stored wait reasons.

### [PASS] Cross-store release and supersession handle partial failure

The three-write release has one owning tick (the asker's). Each crash point (D8, D9, "Release, across two stores") is finished by the next tick, and tests stop after each write. This is the architecture's "each owner finishes a partial state" rule. Member-store failures become wait reasons. A program-store failure exits, as 181 and the architecture require. Budget refusals leave edges open, which is the safe direction.

### [CONCERN] Design carries 184's producer plumbing that nothing in 183 uses

The slice's own premise is that only tests create edges. It still builds:
- the `Unbound` target, with its `unbound` wait reason, for 184's requests;
- `ProvidingCommit` plumbing, for 184's already-met replies;
- the nullable `provider_commit` and `provider_node_id` columns that exist only to carry those targets.

The stated reason is that SQLite cannot alter a `CHECK`. That is a convenience for 184, not something 183 must deliver. 184 can own its migration (003) or table rebuild.

Other items that could be cut or trimmed:
- **`program-edges` listing:** 18 columns. Cut it to the columns 186 reads, or defer the new listing and keep only the edge rows on `program-blocked`. Those rows already carry state and reason.
- **D10 blockless edges:** a separate `release.plan` branch that exists only for tests. A test can use a block and exercise the same path.
- **D13:** it widens `_record_resume_failed` for every resolution resume, the PM's included. The architecture requires only that the restated need is on the block after a release. Scope the payload to coordinator-resolved blocks, or accept the wider change explicitly in 120's docs.
- **Stored wait reasons:** D11 lists eleven values plus `evaluated_at`. Several are the same condition with different text (`provider_slice_missing`, `checkout_unresolved`, `read_failed`, `git_failed`). Merging them would shrink the `CHECK` and the enum without losing anything the PM can act on.

### [CONCERN] Hand-completed providing slices record no head, narrowing the plan's "recorded at `done`" criterion

The slice plan entry says the head is recorded in the transaction that marks a providing slice `done`. D6 excludes the `complete_observed_slices` path (a slice CF reports complete with no run). Edges on such slices wait `branch_head_missing` until the PM resolves the asker's question block. That contradicts the architecture goal "No step needs the PM to act, choose or relay", and it drops part of the assigned scope. The rationale is that this case is rare. Either read the head there with a bounded git read, or record the exception in the architecture and slice plan so the narrowing is a decided deviation. The architecture-level goal also needs a one-line caveat.

### [CONCERN] Changes to 120 and 140 vocabulary go beyond what the architecture lists

The architecture's "Changes to 120" and "Changes to 140" lists do not mention:
- `AnsweredBy.COORDINATOR`;
- `RELEASABLE_STATES` and settling the question record from the coordinator;
- the `_record_resume_failed` payload change (D13);
- the `branch_head` keyword on `record_runner_report`.

The slice says each goes into 120's contract docs, which is good. The architecture should still gain these lines so 184 and 185 (and 144's discard path) have one source for them. Also confirm that 140's answer-limit and answering-stage code treats `coordinator` as a non-answerer, since the doc asserts this only for the answer limit.

### [NOTE] The program inbox writes `release_confirmed_at` on an edge owned by the asker's tick

"Each edge has one owning tick" holds for state and wait columns. `ProgramInboxTenant` writes `release_confirmed_at` on the same row. The columns are disjoint and the stage reads the flag, so there is no conflict. Say so explicitly in the store contract, so that 184 and 185 do not add a third writer.

### [NOTE] D11's budget-refusal rule can starve later edges

A refusal stops evaluation of the remaining edges for the tick. If edge order is fixed, a persistently refused edge could delay every edge behind it. Rotating the start order or ordering by `evaluated_at` would prevent this. The behavior is safe, because open edges keep their slices waiting, so this is a latency issue only.

### Run Digest

- Response length: 5772 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 8
- Tokens — prompt / cached / cache write / completion / reasoning: 463577 / 364399 / 99166 / 6056 / not computed
- Duration: 55.2 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
