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
toolCallsMade: 5
turns: 6
promptTokens: 250561
cachedTokens: 174710
cacheWriteTokens: 75843
completionTokens: 8027
durationSeconds: 89.3
costUsd: 0.803101
costBasis: provider
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: fail
    category: feasibility
    summary: "Checkout holds make a deadlock the edge-plus-predecessor cycle check cannot see"
    location: "project-documents/user/architecture/180-arch.program-coordination.md:57"
  - id: F002
    severity: fail
    category: consistency
    summary: "From-source satisfaction on `done` lets a slice run before the change lands, for pipelines that do not merge"
    location: "project-documents/user/architecture/180-arch.program-coordination.md:59"
  - id: F003
    severity: concern
    category: consistency
    summary: "PM release confirmation and PM supersession are the same action on the same block"
    location: "project-documents/user/architecture/180-arch.program-coordination.md:63"
  - id: F004
    severity: concern
    category: feasibility
    summary: "Request slices in one standing initiative block each other in line"
    location: "project-documents/user/architecture/180-arch.program-coordination.md:55"
  - id: F005
    severity: concern
    category: consistency
    summary: "\"Edges between existing slices\" has no creation path"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#anticipated-slices"
  - id: F006
    severity: concern
    category: dependencies
    summary: "120's lifecycle modules come to depend on 180's program store"
    location: "project-documents/user/architecture/180-arch.program-coordination.md:100"
  - id: F007
    severity: concern
    category: completeness
    summary: "Binding trusts the slice index the model reports"
    location: "project-documents/user/architecture/180-arch.program-coordination.md:82"
  - id: F008
    severity: concern
    category: completeness
    summary: "The program concept has no defined location or read rule"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#technical-considerations"
  - id: F009
    severity: concern
    category: feasibility
    summary: "Creating the standing requests initiative edits shared plan files"
    location: "project-documents/user/architecture/180-arch.program-coordination.md:55"
  - id: F010
    severity: concern
    category: feasibility
    summary: "The asker's checkout stays held for the whole request lifetime"
    location: "project-documents/user/architecture/180-arch.program-coordination.md:84"
  - id: F011
    severity: note
    category: completeness
    summary: "Membership changes with open edges are unspecified"
    location: "project-documents/user/architecture/180-arch.program-coordination.md:94"
  - id: F012
    severity: note
    category: completeness
    summary: "The `requested` state must be handled by 140's stranded and pending sweeps"
    location: "project-documents/user/architecture/180-arch.program-coordination.md:98"
---

# Review: arch — initiative 180

**Verdict:** FAIL
**Model:** claude-opus-5-5

## Findings

### [FAIL] Checkout holds make a deadlock the edge-plus-predecessor cycle check cannot see

"A request run goes ahead of the provider's next slice" launches the request run only "when the provider's checkout has no run in flight." Under 132 (`docs/process-contract.md:484-489`), a checkout is held by more than an unresolved `sq_run`. It is also held by any node that is not done and whose latest run outcome is `paused`, `failed` or `orphaned`.

An asker waiting on a request is, by construction, a paused run with an open question block. So while a project waits on any request, its own checkout is held, and it cannot launch a request run for anyone else. That gives a deadlock:
1. A.7 pauses and requests a change from B. A's checkout is held.
2. B.4 pauses and requests a change from A. B's checkout is held.
3. Neither request run can launch.

At that point the request slices do not exist yet, so the edges are unbound. The "Deadlock" check in Envisioned State runs over "edges and predecessor links." It sees no cycle because the cycle goes through checkout holds, not slices.

The same mechanism also breaks the first design goal without any cycle. A provider with any blocked slice (`auto_resume_exhausted`, stopped, or failed) holds its checkout "until the PM acts." Every request to that provider then waits on a PM action, which contradicts "No step needs the PM to act, choose or relay" (line 61). The architecture has to pick one of these:
- The request run, which is a planning-only run committing to the target, gets an exemption from the checkout hold.
- The request run runs in a separate checkout.
- The deadlock graph includes checkout holds, and a request stuck behind a held checkout goes on the program blocked list with that reason.

### [FAIL] From-source satisfaction on `done` lets a slice run before the change lands, for pipelines that do not merge

"A from-source edge is satisfied when the providing slice node is `done`, which for a pipeline that merges means merged to the target." For a pipeline that does not merge, `done` means CF reports the slice complete on its slice branch. This project's own config example uses `p456` for `amoeba` (`process-contract.md:849`). Merging is Phase 7, after code review. B builds against A's target, so it would be resumed against a change that is not there.

That directly breaks the design goal "Nothing runs against a change that has not landed" (line 35). The document names the case but never says what satisfies the edge in it. Two options:
- Treat a non-merging provider like a from-release edge: wait for the PM's merge, shown on the blocked list.
- Observe the merge itself, for example by checking that the providing slice's commit is reachable from the target.

Separately, "the commit that satisfied it" in the release instructions (line 37) has no source. Node `done` records no merge commit, so whoever writes the instructions has nothing to read the commit from.

### [CONCERN] PM release confirmation and PM supersession are the same action on the same block

For from-release edges, the edge "is satisfied by the PM's resolution saying the release exists" (lines 59, 88). The only open block is B's question block. The document never describes a block on the edge itself or in the program store.

"The PM's answer always wins" (line 63) says a PM resolution on that same question block closes the edge "as superseded by the PM." So one PM action has two incompatible meanings:
- "Release exists": resume with release-generated instructions naming the provider's work.
- "Superseded": the PM's own instructions apply.

Nothing tells the Runner which one the PM meant. A release-confirmation resolution needs its own target, for example an edge id through the program inbox, and its own body shape in `docs/inbox-contract.md`.

### [CONCERN] Request slices in one standing initiative block each other in line

"Because predecessor order is per initiative, a request slice waits only on earlier request slices." That is still a single queue for every asker. If request slice N−1 stops, fails, is held by the PM, or waits on a from-release edge of its own, every later request to that provider stalls. That includes requests from unrelated askers in other projects. Design goal 4, "A request does not wait behind the provider's backlog," then fails, because the backlog has moved into the request initiative.

Request slices are independent by construction, so they should not use the in-initiative predecessor rule. `predecessors.py` already has to change for edges, so making request-initiative slices have no implicit predecessor costs nothing extra. The document should decide this rather than inherit the default.

### [CONCERN] "Edges between existing slices" has no creation path

The "Edges and release" slice builds "edges between existing slices of member projects." In the Envisioned State, though, edges are only ever created by a request, with the provider side unbound until binding. Nothing describes who declares an edge between two existing slices, or how:
- There is no inbox body for it.
- The program inbox (line 94) registers only programs, members and consumption modes.

Either the program inbox gets an edge-declaration intent, spelled out with validation and the cycle check at declaration time, or this slice's scope is really "edges as a test fixture," and the plan should say so. As written, the slice ordering implies a feature that no section designs.

### [CONCERN] 120's lifecycle modules come to depend on 180's program store

"Changes to 120" calls these "a contract change … not a new mechanism." Two of the changes, though, make 120's lower layer read 180's state:
- `predecessors.py` now needs edge rows plus provider node state from other projects' stores.
- Governance needs to know about program membership in order to drive request slices.

Both run inside the project tick before `decide()`, and today they read only the project's own store and desired-state index (`process-contract.md:444-458`). The document should state the dependency direction. For example, the program stage computes a per-project "external predecessors + membership-driven slice set" each tick and injects it into readiness and governance, so `runner/lifecycle` never imports the program store. It should also give the in-tick ordering: B's PM resolution has to close the superseded edge before readiness runs, or `decide()` raises on the resume.

### [CONCERN] Binding trusts the slice index the model reports

The edge binds "only when CF shows a slice at that index in that initiative." That check proves the slice exists, not that this run created it. A request run that reports an earlier request slice's index would pass and bind B to unrelated work. This is a plausible slip, because the provider's agents "see the earlier request slice in their own plan" (line 108).

Since "Nothing a model says satisfies an edge," binding should also require that the index was absent from the plan read before the run launched. The pre-launch slice set could be recorded in the request row.

### [CONCERN] The program concept has no defined location or read rule

The program record holds "the program's concept document," and 140 is supposed to read it as "dated passages." But 140's sources are read from a project's target-branch committed content, dated by committer date (`process-contract.md:817-837`, 865-870). The document does not say:
- whether the concept lives in a member repo (which one, at which commit) or as a file the program store points to;
- how it gets a date;
- what `sources_missing` means for it.

The "Program concept as a source" slice cannot be designed without this.

### [CONCERN] Creating the standing requests initiative edits shared plan files

The principle argues the request run's commit "does not touch a file an open slice branch is editing" because it has its own slice plan file. That holds for later requests. The first request run, though, creates the initiative. In CF that normally means adding an entry to the project's `001-initiative-plan.*.md` and writing an architecture file. The initiative plan is shared and regularly edited on slice branches. The first-request case needs either a stated conflict risk or a requirement that the initiative be created when the project joins the program, not lazily.

### [CONCERN] The asker's checkout stays held for the whole request lifetime

The first FAIL covers the deadlock. Short of deadlock, B's paused slice holds B's only checkout for the provider's planning run, the provider's full design/build/merge pipeline, and possibly a PM release. During all of that, B runs nothing. The document says nothing about this cost. The alternative is to let B's paused run give up the checkout (fail or stop it and rely on the relaunch-with-instructions path the document already requires) so B's other work can continue. The architecture should choose and state the cost, as it does for the provider's side on line 57.

### [NOTE] Membership changes with open edges are unspecified

Nothing says what happens when a member is removed, or a consumption mode changes from source to release, while edges reference it. The simplest rule is to reject such a submission while open edges reference the member. That is one line in the program inbox contract.

### [NOTE] The `requested` state must be handled by 140's stranded and pending sweeps

140's answering stage declines stranded `answering` questions and sweeps `pending` ones (`process-contract.md:781-787`). With the new state, the order matters: the program store's request is written first, and the record moves to `requested` after. A crash between the two leaves a resolved `sq_answer` entry with the question still `answering`. The stranded step would then decline it as `answer_discarded` before the request's owning tick finishes the move. The stranded step needs to check for an existing request row first.

### Run Digest

- Response length: 11744 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 250561 / 174710 / 75843 / 8027 / not computed
- Duration: 89.3 s
- Cost: $0.80 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
