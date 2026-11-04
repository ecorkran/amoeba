---
docType: review
layer: project
reviewType: arch
slice: program-coordination
targetKind: arch
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/architecture/180-arch.program-coordination.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 2850657afc9553c718eff53d9167f99bf4a0bd51
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 169703
cachedTokens: 99195
cacheWriteTokens: 70502
completionTokens: 9411
durationSeconds: 105.8
costUsd: 0.772942
costBasis: provider
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: fail
    category: consistency
    summary: "The \"already met\" outcome lets a model's statement satisfy an edge, which the document forbids"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#envisioned-state"
  - id: F002
    severity: concern
    category: feasibility
    summary: "Two members that need changes from each other end on the PM, and the doc does not say what a refused request does"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#architectural-principles"
  - id: F003
    severity: concern
    category: completeness
    summary: "A member that is unlinked or missing has no defined effect on edges and requests"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#technical-considerations"
  - id: F004
    severity: concern
    category: completeness
    summary: "Recording the branch head can fail if the branch is deleted or the Runner is down before B's tick reads it"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#architectural-principles"
  - id: F005
    severity: concern
    category: antipattern
    summary: "The joining run and the \"pending\" member state duplicate the rollover path"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#envisioned-state"
  - id: F006
    severity: note
    category: antipattern
    summary: "Consumption mode for every ordered pair grows quadratically with members"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#architectural-principles"
  - id: F007
    severity: note
    category: completeness
    summary: "The unit of the request limit is not stated"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#envisioned-state"
  - id: F008
    severity: note
    category: completeness
    summary: "The question block after a relaunch is not specified"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#envisioned-state"
  - id: F009
    severity: note
    category: consistency
    summary: "The cross-store write order for request creation involves three writes, not two"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#technical-considerations"
---

# Review: arch — initiative 180

**Verdict:** FAIL
**Model:** claude-opus-5-5

## Findings

### [FAIL] The "already met" outcome lets a model's statement satisfy an edge, which the document forbids

The principle "Satisfaction is observed where the dependent consumes the provider" ends with "Nothing a model says satisfies an edge." The "Deferred: automatic probes" bullet relies on the same rule: it rejects probes because "a probe written from request text would let a model's output decide satisfaction."

"Work in the provider" breaks that rule for the **Already met** outcome: "the request closes, its edge is satisfied with the provider's statement of where the need is met, and release follows." Design Goal 3 says the same thing ("or the provider's statement that it already meets the need"). In this path, the only evidence is the request run's reply, which is model output.

This also undermines Design Goal 2 ("Nothing runs against a change that has not landed") in two concrete cases:
- **From-release edge.** A's agent says the need is met on A's target. B consumes A's last release, which does not contain it. The PM edge resolution, the only gate for from-release edges, is skipped completely.
- **From-source edge.** A's agent points at code that exists only on an unmerged slice branch, or is simply wrong. The doc does not require a commit, so nothing checks reachability.

Fix: the already-met reply should carry a commit or path that the consumption mode then checks. For from-source, the program stage confirms the named commit is reachable from A's local target. For from-release, the edge still waits on the PM's edge resolution. The model's statement then goes only into the resume instructions, not into the satisfaction decision.

### [CONCERN] Two members that need changes from each other end on the PM, and the doc does not say what a refused request does

The checkout exemption only applies when the held checkout is "clean and on the target." An asker that pauses during implementation (the usual case, under `p456`) is on its slice branch, not the target. So the claim in "The asker keeps its checkout" that "a request run from another member may still use it" covers only askers paused in planning phases.

The common provider-needs-something-back case:
1. `B.5` pauses mid-build and asks A for a change.
2. `A.req1` is written and starts building.
3. `A.req1` needs a small contract change from B and asks.
4. B's checkout is held by `B.5` on its slice branch, so the request run to B waits on `B.5`, which waits on `A.req1`.

"A cycle is refused when it would be created" catches this, but the doc never says what happens to `A.req1`'s question after a refusal. It could be declined, which puts it on the PM. It could be held as a block with the reason "cycle," which also puts it on the PM. Either way, the most natural pattern between two repos (negotiating a contract back and forth) ends on the PM. That contradicts "No step needs the PM to act, choose or relay."

The document should:
- name the outcome of a refused request: the question state and the blocked-list reason.
- accept in writing that a reverse request during implementation needs the PM until separate request checkouts exist. Name it as a cost in the same paragraph as the PM-merge cost.

### [CONCERN] A member that is unlinked or missing has no defined effect on edges and requests

The doc handles two membership cases: a member that is still joining ("pending") and a submission that removes a member while edges are open (rejected). It does not handle the project-level states 120 already has:
- the member is unlinked from the Runner, so it is no longer in the loop;
- its link snapshot or checkout is missing;
- its store file is absent.

When the program stage in B's tick "may open other members' stores and plan snapshots read-only," any of these makes the reads that release depends on fail: A's node `done`, A's branch head, reachability on A's target. Requests owned by A's tick simply never progress, because A has no tick.

The doc should say whether each of these:
- blocks the dependent edges with a named reason on the program blocked list, or
- is a store failure that exits the process (the rule in "The program store and its inbox").

The second option would let one unlinked repo stop every project, including projects in no program. That conflicts with "A project that belongs to no program behaves exactly as it does after 140."

### [CONCERN] Recording the branch head can fail if the branch is deleted or the Runner is down before B's tick reads it

From-source satisfaction depends on B's tick recording "the head of its branch, named exactly `{index}-slice.{name}`" after the providing slice is `done`. The doc already accepts a one-loop lag. The Runner can also be down for hours. In that window the PM can review, merge and delete the slice branch. Branch deletion is a normal PM action after merge; the project rules only stop *agents* from deleting branches.

After that, `log` cannot resolve the head. The edge never becomes satisfiable, even though the change is on A's target. Possible fixes:
- record the head in A's tick at the moment A's supervisor marks the slice `done`. A's tick owns that transition, so this fits "one owning tick."
- name the blocked reason for a branch that cannot be found.

### [CONCERN] The joining run and the "pending" member state duplicate the rollover path

"Request slices live in requests initiatives" already describes a request run that creates the next requests initiative when the current band is full. The same request run can create the *first* initiative when none exists in the range. That is the rollover case with an empty current set.

Because the doc instead uses a separate one-time joining run at registration, it adds:
- a third mode for the slice-writing pipeline;
- a "pending" member state that requests must wait on;
- a joining step in the Program record slice;
- a crash-recovery transition ("the joining run ... by the provider's").

This also edits the initiative plan for members that may never receive a request. Cut the joining run and the pending state, and let the first request create the first initiative.

### [NOTE] Consumption mode for every ordered pair grows quadratically with members

"Each ordered pair of members says how the dependent consumes the provider." That is N(N−1) declarations: 12 for the four-repo tool chain, and more for `trading` as it grows ("more coming"). Most declarations will be the same for a given provider, because a released tool is consumed from a release by everyone. With no defaults (a project rule), registration means writing out every pair. Consider declaring the mode per provider, with per-pair overrides only when one is actually needed.

### [NOTE] The unit of the request limit is not stated

"Request" adds "a request limit of its own," centralized with the answer limit. The doc does not say what the limit counts: per asking slice, per asker project, per provider, or per program. This matters because requests "go first in the provider" ahead of all planned work. A per-asker limit does not stop several askers from starving one provider's planned slices. A per-provider limit does. Decide this here, not in slice design, because it is the only throttle on priority starvation.

### [NOTE] The question block after a relaunch is not specified

"Release" says that when B's paused run cannot be resumed, B's slice is relaunched with pending instructions. It does not say what happens to B's open question block in that path. A resume resolution normally closes it. If the block stays open after relaunch, it stays on the blocked list. It also stays resolvable by a later PM resolution, which would then "supersede" edges that are already satisfied. The doc should say that release closes the block in both the resume path and the relaunch path.

### [NOTE] The cross-store write order for request creation involves three writes, not two

"Crossing stores without one transaction" says "the program store is written first; the project side follows." For request creation, though, B's store is written before the program store as well: the answering entry is resolved, which is why the stranded-sweep change exists. The actual order is B store → program store → B store (`requested`). Stating the three-step order makes it clear which partial states the next tick has to finish.

### Run Digest

- Response length: 9477 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 169703 / 99195 / 70502 / 9411 / not computed
- Duration: 105.8 s
- Cost: $0.77 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
