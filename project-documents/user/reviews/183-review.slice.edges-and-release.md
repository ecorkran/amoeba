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
reviewedSha: 943719c0d37f2243dbfa079adb2a1ecb28314064
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 107788
cachedTokens: 11162
cacheWriteTokens: 96622
completionTokens: 7360
durationSeconds: 63.1
costUsd: 0.462054
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Edge-as-predecessor, tick order and the `lifecycle` boundary match the architecture"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#D2 — Readiness takes external waits as an argument, not a default"
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "The release and supersession protocol follows the architecture's cross-store rule"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#Data Flow"
  - id: F003
    severity: concern
    category: error-handling
    summary: "A transient git failure while reading the head becomes a wait only the PM can end"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#D5 — The branch head is read before `done` and written in the `done` transaction (and D6)"
  - id: F004
    severity: concern
    category: proportionality
    summary: "D10's least-recently-evaluated fairness adds a write to every open edge on every tick, and it conflicts with the data flow"
    location: "project-documents/user/slices/183-slice.edges-and-release.md:272-273 (D10), :130-131 (Data Flow)"
  - id: F005
    severity: note
    category: data-integrity
    summary: "The \"two writers on disjoint columns\" claim does not hold for shared bookkeeping columns"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#State Management"
  - id: F006
    severity: note
    category: integration
    summary: "184 will need a table rebuild to add unbound edges"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#Database / Storage Schema"
  - id: F007
    severity: note
    category: error-handling
    summary: "D8 does not say what `submit_release` does when the question block is missing"
    location: "project-documents/user/slices/183-slice.edges-and-release.md#D8 — `submit_release`: the answerer's submission path with the coordinator's name"
---

# Review: slice — slice 183

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Edge-as-predecessor, tick order and the `lifecycle` boundary match the architecture

The slice matches the architecture on these points:
- Open edges enter readiness through `predecessors.py` as a node-id set, so `runner/lifecycle` never imports the program store.
- `decide()`'s guard is unchanged.
- The coordinator writes no desired-state row.
- The program stage runs after resolutions are acknowledged and before readiness.
- The git reads use only `log` and `merge-base`, which are on the existing allowlist, so no new verb is added.
- `satisfied` edges drop out of `waiting` without a hole, because the slice is still blocked on its question block.

### [PASS] The release and supersession protocol follows the architecture's cross-store rule

Each cross-store transition has one owning tick and a defined write order. The asker's tick owns release, in three writes. After each crash point, the next tick finishes the work without redoing it. D9 tells a release the coordinator completed apart from a PM supersession by using `resolved_by`. The slice also maps onto the architecture's "Changes to 120" and "Changes to 140" lists:
- `coordinator` as an `answered_by` value
- the head recorded on both `done` paths
- the resume-failed payload carrying the release's instructions

### [CONCERN] A transient git failure while reading the head becomes a wait only the PM can end

D5 and D6 handle a budget refusal by retrying. They handle a git failure by recording `commit` null with the failure as `detail`. D10 then reports `branch_head_missing`, and D5 says "only the PM's resolution of the question block ends" that wait. The head is read once, at the `done` transaction, and nothing re-reads it afterwards.

Two causes get the same unrecoverable treatment. A deleted branch is permanent. A transient failure, such as an `index.lock` collision, a momentary checkout problem or an unresolvable checkout at hand completion, usually is not. The architecture's goal is that "every path that cannot proceed ends on the blocked list with its reason", and nothing here stops the transient case from ending with a PM step. A transient failure gets the same outcome as a deleted branch.

Fix: when the recorded head is null and `detail` records a read failure rather than a missing branch, let `observe_edges.py` re-read the head. The branch name is deterministic and the branch normally survives `done`. Alternatively, treat a git failure like a budget refusal and leave the entry unfinished for a bounded number of ticks. Keep the PM-only wait for the missing-branch case.

### [CONCERN] D10's least-recently-evaluated fairness adds a write to every open edge on every tick, and it conflicts with the data flow

D10 sets `evaluated_at` on every evaluation, even when nothing changed. It uses `evaluated_at` for LRU ordering and adds a `(waiting_project, state, evaluated_at)` index. The aim is to stop one edge starving the others when the budget refuses. The data flow says "write state or wait reason only when it changed", which contradicts that. D10 also says only a state or wait change counts toward `tick.wrote`, so the per-tick writes are hidden from the tick's own accounting.

The starvation case needs a budget refusal that recurs after the first edge on every tick. The slice plans for only a handful of edges per program. This is the heavier option where a lighter one would do.

Choose one:
- **Cut it.** Order by `edge_id` or `created_at` and continue past a refusal. Open edges still count in `waiting`, so a refusal stays safe.
- **Keep the ordering but not the write.** Rotate a start offset held in memory, so the program store is not written each tick for nothing.

Either way, fix the data-flow line and the Success Criteria bullet about starvation to match.

### [NOTE] The "two writers on disjoint columns" claim does not hold for shared bookkeeping columns

The asker's tick owns everything except `release_confirmed_at`, and the inbox writes only that column. `updated_at` is in the schema and both writers will want to touch it. State in `docs/store-contract.md` which writer owns `updated_at`, or exclude it from the split. The same bullet could also say that the resident process hosts both writers, which is how it fits the architecture's rule that only the resident process writes the program store.

### [NOTE] 184 will need a table rebuild to add unbound edges

The check `CHECK ((provider_node_id IS NULL) <> (provider_commit IS NULL))` rejects an edge whose target is not yet bound. The architecture creates an unbound edge at request time. SQLite cannot alter a `CHECK` in place, so 184's "own migration" is a rebuild of `edges`. This is acceptable and the slice states it, but the scope note should say so. The note should also say where `program/modes.py` lives, because the component table gives no `runner/` prefix and 184 and 185 import it.

### [NOTE] D8 does not say what `submit_release` does when the question block is missing

D8 specifies `block_resolved` but not an absent block row. D1 makes `question_block_id` required, so it should not happen. It is still worth one line saying it is a programming error that raises, not a wait reason, so it is not mistaken for the member-unreadable class that D10 maps to wait reasons.

### Run Digest

- Response length: 6570 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 107788 / 11162 / 96622 / 7360 / not computed
- Duration: 63.1 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
