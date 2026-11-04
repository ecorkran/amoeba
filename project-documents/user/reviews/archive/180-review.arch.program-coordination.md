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
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/architecture/180-arch.program-coordination.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 2850657afc9553c718eff53d9167f99bf4a0bd51
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
turns: 9
promptTokens: 508237
cachedTokens: 426960
cacheWriteTokens: 81263
completionTokens: 9067
durationSeconds: 104.6
costUsd: 0.917735
costBasis: provider
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: fail
    category: feasibility
    summary: "Request slices wait on held checkouts, but the deadlock graph and blocked list only cover request runs"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#envisioned-state"
  - id: F002
    severity: concern
    category: consistency
    summary: "The answerer's check cannot judge A's sources, because the visibility rule hides them"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#technical-considerations"
  - id: F003
    severity: concern
    category: completeness
    summary: "Binding records the slice set at request time, so two requests to one provider can bind to the same slice"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#envisioned-state"
  - id: F004
    severity: concern
    category: feasibility
    summary: "Requests to a provider whose pipeline does not merge wait on the PM after every slice"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#architectural-principles"
  - id: F005
    severity: concern
    category: consistency
    summary: "Reachability is checked on the provider's local refs, not where the dependent consumes the change"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#architectural-principles"
  - id: F006
    severity: concern
    category: completeness
    summary: "The standing requests initiative has a limited index range and needs dispatch order changes"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#technical-considerations"
  - id: F007
    severity: concern
    category: completeness
    summary: "Supersession does not say what happens to a request that is still unbound or in flight, or to its membership drive"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#architectural-principles"
  - id: F008
    severity: note
    category: dependencies
    summary: "A dependent's tick reads the provider's store and plan"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#technical-considerations"
  - id: F009
    severity: note
    category: completeness
    summary: "The program concept is read from another member's checkout"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#technical-considerations"
---

# Review: arch — initiative 180

**Verdict:** FAIL
**Model:** claude-opus-5-5

## Findings

### [FAIL] Request slices wait on held checkouts, but the deadlock graph and blocked list only cover request runs

The "Deadlock" paragraph defines checkout waits as "a request run waiting on a checkout, that checkout held by a waiting slice". The exemption in "A request run takes a clean checkout on its target" also covers only the *request run*. The *request slice* that run writes then has to design and build in the provider's checkout, under the normal rule (`process-contract.md:484-489`). That checkout is held by any not-done node whose latest run is `paused`, `failed` or `orphaned`. "The asker keeps its checkout" means a waiting asker always holds its checkout. So with two projects asking each other:
1. A.3 pauses and asks B for a change. B's checkout is clean on its target, so B's request run writes B.req1.
2. B.5 pauses and asks A for a change. A's request run writes A.req1.
3. B.req1 cannot launch because B.5 holds B's checkout. A.req1 cannot launch because A.3 holds A's checkout.

All four edges are bound, so this is a real cycle. It runs through two request-slice checkout waits, which the defined graph does not contain, so the check never sees it.

The same gap appears without any cycle. If the provider has a slice blocked on the PM (`auto_resume_exhausted`, stopped), that slice holds the checkout, and every request slice to that provider waits on the PM. The blocked-list rule only reports request runs waiting this way, so these waits never get their reason shown.

To fix it, the graph and the blocked-list reasons need to cover any membership-driven slice waiting on a held checkout, not just request runs. Alternatively, the document should state that request slices only progress once the asker that holds the checkout resumes, and accept that cost.

### [CONCERN] The answerer's check cannot judge A's sources, because the visibility rule hides them

"Changes to 140" requires the check step to confirm the need "belongs to A and not to B itself, and is not already met by A's sources". But "Cross-project visibility" says the answerer in B "never sees another project's rules, plan or PM answers as passages". Its only view of A is the program concept, the member list and edge state. It cannot see whether A already meets the need, so the check's verdict on that point is a guess. That is exactly the "nothing a model says decides" problem the document guards against elsewhere.

The document should do one of two things:
- Drop that clause from the check and let the provider's own request run decline a need A already meets. That run then needs a "no slice needed" outcome, which today would land as "writes no slice", a blocked failure.
- Name the narrow, read-only slice of A (for example its plan index) that the check may see.

### [CONCERN] Binding records the slice set at request time, so two requests to one provider can bind to the same slice

"Request" records "the request initiative's current slice set" when the request is created in B's tick. Two requests to A created before either request run runs (from B and C, or two from B) record the same set. Request run 1 writes slice N. Request run 2 runs a little later and wrongly reports N, a plausible slip because N is now in its own plan. N is absent from run 2's recorded set, so run 2 binds to it, and both askers bind to one slice built for one need. The set should be recorded when the request run *launches*, in A's tick, which owns the request run anyway.

### [CONCERN] Requests to a provider whose pipeline does not merge wait on the PM after every slice

`process-contract.md:956-958`: "A pipeline that does not merge leaves its checkout on the slice branch". The request-run rule makes a request wait when the checkout is "on a slice branch". So for a `p456` provider, the shape of this project's own config, every request waits on the PM's merge of whatever slice last finished there, even though nothing is paused or in flight. That conflicts with the design goal "Requests do not wait behind other work". It also makes PM merges a routine wait for unrelated askers, not just for the edge that actually depends on the merge. The document should accept this cost and state it, or let request runs use a checkout separate from the provider's slice checkout.

### [CONCERN] Reachability is checked on the provider's local refs, not where the dependent consumes the change

The goal "observed where the waiting project consumes it" becomes "that commit is reachable from the provider's target, observed with the Runner's read-only git". There are three gaps:
- `git_read` allows only `status`, `merge-base`, `show` and `log` (`process-contract.md:936-937`), with no `fetch`. A merge the PM makes on the remote (a GitHub PR) never reaches A's local target, so the edge waits indefinitely. The blocked list keeps showing it as "waiting on the PM's merge" even after the merge has happened.
- A squash or rebase merge leaves the recorded branch head unreachable for good.
- The observation is made in A's repo, but B "builds against the provider's target" through its own path (a sibling checkout, a git dependency). A commit on A's local target does not prove B's build sees it.

The document should state which merge strategies it supports and say that from-source means A's local checkout target. It should also say how the branch head is found from `{index}-slice.*` when several branches match.

### [CONCERN] The standing requests initiative has a limited index range and needs dispatch order changes

The design has two gaps here:
- **Index range.** CF slice indexes sit inside the initiative's index band; in this project initiatives step by 20, so 141 to 145 belong to 140. A *standing* initiative that collects every request indefinitely runs out of indexes after about 19 requests. The document defers "numbering" to slice design, but whether requests roll over into a new initiative, or the band is made larger, decides how the joining run, binding's "that initiative" check and worktree `indexRange` routing work.
- **Dispatch order.** The planner orders actions by `(initiative index, slice index)` (`process-contract.md:488-489`). "Changes to 120" gives priority only to the request *run*. The request *slice* still sorts behind current slices of lower-index initiatives in the same checkout, which contradicts "Requests do not wait behind other work". The priority needs to cover membership-driven slices as well.

### [CONCERN] Supersession does not say what happens to a request that is still unbound or in flight, or to its membership drive

"The PM's answer to the asker always wins" covers only the case where the request slice already exists ("continues as the provider's own work"). If the PM resolves B's block before A's request run launches, or while it is in flight, the document does not say whether the run is cancelled, whether its slice is still written, or whether the unbound edge closes.

Once superseded, the slice stays in the standing requests initiative, so membership still drives it and it still gets request priority. That is not "the provider's own work": it keeps consuming A's checkout for a need nobody is waiting on, and the PM can only stop it with a hold. The document should either drop the membership drive when the last edge on a request slice closes as superseded, or explicitly keep it.

### [NOTE] A dependent's tick reads the provider's store and plan

"Crossing stores without one transaction" says which tick owns each write. But release ("B's tick owns B's edges") has to read A's node `done`, A's branch head and A's target, and request creation records A's plan slice set. So the program stage running in B's tick opens A's project store and reads A's CF plan. That is allowed, since reads are read-only, but 100's locality contract should say a project tick may open other members' stores read-only. The one-tick lag that comes from loop order is also worth stating for the walkthrough.

### [NOTE] The program concept is read from another member's checkout

140's source reads go through B's `git_read` on B's checkout (`source_reads.py`). The concept lives in "one member repo", so assembling B's sources means resolving that member's checkout and target from its link snapshot. That is a second checkout in one source assembly, and a new failure case for `sources_missing` when that member's snapshot is absent or stale.

### Run Digest

- Response length: 10024 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 508237 / 426960 / 81263 / 9067 / not computed
- Duration: 104.6 s
- Cost: $0.92 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
