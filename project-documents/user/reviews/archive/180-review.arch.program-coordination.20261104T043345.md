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
toolCallsMade: 6
turns: 7
promptTokens: 311678
cachedTokens: 239282
cacheWriteTokens: 72386
completionTokens: 7136
durationSeconds: 79.0
costUsd: 0.770548
costBasis: provider
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: fail
    category: feasibility
    summary: "\"An edge is a hold with a reason\" cannot be built on 120's desired-state rows as they exist"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#architectural-principles"
  - id: F002
    severity: concern
    category: extension-points
    summary: "The design ignores the extension point 120 built for cross-project edges"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#architectural-principles"
  - id: F003
    severity: concern
    category: completeness
    summary: "Cycle detection only considers edges, but deadlocks also form through in-project predecessor order"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#technical-considerations"
  - id: F004
    severity: concern
    category: feasibility
    summary: "Where the provider slice lands in A's plan decides how long B waits, and the document never addresses it"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#envisioned-state"
  - id: F005
    severity: concern
    category: completeness
    summary: "The provider's request-run scheduling is a load-bearing decision, and it is left open"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#technical-considerations"
  - id: F006
    severity: concern
    category: completeness
    summary: "Gaps in how the program store and program inbox are wired into the Runner"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#anticipated-slices"
  - id: F007
    severity: concern
    category: consistency
    summary: "Release competes with the PM for B's resolution slot, and question-record changes are missing"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#envisioned-state"
  - id: F008
    severity: concern
    category: completeness
    summary: "Relaunching with instructions is new 120 capability that no slice covers"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#technical-considerations"
  - id: F009
    severity: concern
    category: consistency
    summary: "Probes break the \"only sq or cf\" principle, and their source is undefined"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#technical-considerations"
  - id: F010
    severity: concern
    category: antipattern
    summary: "Overweight scope: tool-chain probes and request de-duplication should be deferred"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#anticipated-slices"
  - id: F011
    severity: note
    category: feasibility
    summary: "`done` in A is assumed to mean the change is usable in B for product repos"
    location: "project-documents/user/architecture/180-arch.program-coordination.md#architectural-principles"
---

# Review: arch — initiative 180

**Verdict:** FAIL
**Model:** claude-opus-5-5

## Findings

### [FAIL] "An edge is a hold with a reason" cannot be built on 120's desired-state rows as they exist

The document says the coordinator writes a hold "with the edge as its cause" and that release "clears exactly the hold it placed and nothing the PM set." The store cannot do this today. `docs/store-contract.md:695-705` defines one desired-state row per target:
- `SetDesiredState` replaces the whole row.
- `ClearDesiredState` deletes it.
- The only provenance is `message_id`, meaning "the intent that last set the row."
- There is no cause column and no way to stack holds.

This creates three concrete failures:
1. **A PM setting is erased.** Suppose the PM has set `drive=True` or their own `hold=True` on B's slice. Amoeba's hold either overwrites that row or gets merged into it. Release then deletes or rewrites the row and loses the PM's setting.
2. **Two edges on one slice.** If B's slice waits on edges to A and to C, satisfying either edge clears the single row. The slice is released while the other edge is still open, which breaks the goal "Nothing runs against a change that has not landed".
3. **No write path.** Desired states are written only in `acknowledge_message` for an inbox intent (`process-contract.md:434-439`). The document does not say whether the coordinator submits intents to itself or needs a new write path.

The architecture must either specify a schema change (layered holds keyed by cause) or drop holds as the enforcement mechanism (see the next finding).

### [CONCERN] The design ignores the extension point 120 built for cross-project edges

`docs/process-contract.md:446-450` defines readiness as "its predecessor is `done`" and names `predecessors.py` as "the one place a later slice adds cross-project edges." This is a readiness predicate, not a desired state. If cross-project edges are extra predecessors:
- A slice with an open edge is simply not ready, so it is not current.
- `decide()`'s guard (`process-contract.md:456-458`) then refuses both dispatch and resume, with no separate enforcement.
- Release needs no clear step. The edge becoming satisfied makes the slice ready.
- The PM's desired-state rows are never touched.
- Multiple edges on one slice work naturally.

The document does not mention this extension point. It does not explain why a hold is better than readiness. As written, it builds a second ordering mechanism next to the one designed for this purpose.

### [CONCERN] Cycle detection only considers edges, but deadlocks also form through in-project predecessor order

"Cycles and duplicates" refuses only edge cycles ("A waits on B waits on A"). But each project also orders its slices implicitly: a slice waits on the next lower CF index in its initiative (`process-contract.md:447-449`). That allows a deadlock with no edge cycle:
1. B.3 has an edge waiting on A.new.
2. A.new is appended after A.5, so it waits on A.5 through predecessor order.
3. A.5 has an edge waiting on B.4.
4. B.4 waits on B.3 through predecessor order.

No two edges form a cycle, yet nothing can move. Cycle checks must run over the union of edges and predecessor links. They must also run again when a plan read changes predecessors, for example when a request run inserts a slice.

### [CONCERN] Where the provider slice lands in A's plan decides how long B waits, and the document never addresses it

"Work in the provider" assumes A's new slice "is driven like any slice." There are two problems:
- **Queue position.** Under 120's predecessor rule, a slice appended to an initiative waits until every earlier slice in that initiative is `done`. If it is inserted in the middle instead, it changes the predecessor of an existing slice. Either B waits behind A's whole backlog, or A's existing ordering changes. The document calls slice numbering "slice-design work," but the choice decides whether the first design goal can be met at all.
- **Drive.** A slice runs only if some row on its path drives it (`process-contract.md:451-453`). If A's project and initiative are not driven, the provider slice never runs, and B is held forever. The document does not say this case goes on the blocked list.

The architecture must decide where request slices go (for example a dedicated initiative) and how they get driven.

### [CONCERN] The provider's request-run scheduling is a load-bearing decision, and it is left open

"When the provider can take a request run" is presented as the open question carried over from the initiative plan, and nothing settles it. It decides:
- whether the request run competes with A's in-flight pipeline under 132's one-pipeline-per-checkout rule;
- whether a commit to A's target (planning commits go straight to the target) conflicts with an open slice branch that also edits the slice plan file.

It also decides the crash-recovery shape of the request record versus A's journal. The "Requests" slice cannot be designed until this is answered, so the architecture should pick an option, for example "only when A has no run in flight," with the cost stated.

### [CONCERN] Gaps in how the program store and program inbox are wired into the Runner

- **Program inbox.** "Program and member registration through the inbox" has no target store. `apply_submission` takes a `project_id` and writes to that project's store (`store-contract.md:387`). A program-level submission needs a new inbox path, or a rule for which project's inbox carries it.
- **Edge ownership.** "Every member project's Runner tick also evaluates the program's edges" does not say which tick owns a given edge transition (the dependent's or the provider's). Without that, edges are evaluated N times per sweep and the idempotency rules get harder.
- **Fault scope.** Failures are project-scoped `unexpected_fault`s (`process-contract.md:441-443`). The document does not say which project faults when the program store fails, or whether a program-store failure stops the whole process the way a project-store failure does.
- **File naming.** Project stores are named `{project_id}.sqlite3` in the same directory (`store-contract.md:1079`). The program store's file name must not be able to collide with a project id.

### [CONCERN] Release competes with the PM for B's resolution slot, and question-record changes are missing

B's question gets a request instead of an answer, so B's block resolution slot stays open while A works. During that time the PM can submit a `resume` resolution through the inbox. The document does not cover either side of this:
- If the PM fills the slot first, release's resume (with the "coordinator as the submitter") finds it closed.
- If release goes first, the PM's resolution is rejected.

140's question record also has only answered and declined outcomes (`store-contract.md:942`). A third "requested" outcome means a schema change and a gate-outcome change. Neither is listed in the "Requests" slice.

### [CONCERN] Relaunching with instructions is new 120 capability that no slice covers

"Release when the asker's run is gone" requires the restated need to reach a fresh launch, and the document admits "today only a resume carries" instructions. Per `process-contract.md:466-467`, `DispatchPlanner` launches the configured pipeline and stores nothing beyond the journal. Carrying per-slice instructions into the next dispatch is a change to 120's dispatch contract. None of the anticipated slices includes it, and the "Edges, hold and release" slice covers only resuming the asker's run.

### [CONCERN] Probes break the "only sq or cf" principle, and their source is undefined

The Architectural Principles say the Runner "remains the only part of Amoeba that issues `sq` or `cf` commands." A probe "run in the dependent project's environment" is a different kind of command, for example a version check of an installed tool. Nothing in the principles allows arbitrary commands.

If the probe comes from the request text, a model wrote it. That weakens "Nothing a model says satisfies an edge." The document hands the choice to slice design ("fixed set," or "`done` plus release tag"), but the answer changes the Runner's trust boundary, so the architecture should decide it.

### [CONCERN] Overweight scope: tool-chain probes and request de-duplication should be deferred

Three parts can be cut or deferred:
- **Tool-chain edges.** The "Tool-chain edges" slice brings in a probe mechanism, a new command class (previous finding) and a PM-release wait state. The milestone's stated pain is the `trading` product repos, where `done` is enough. An edge satisfied by `done` and shown as "waiting on PM release" until the PM clears it covers tool chains without probes. Defer probes.
- **De-duplication.** "Two requests … should become one provider slice with two edges" needs a model judgment of "the same change," and the document already offers the fallback of "left as two requests." Take the fallback and cut de-duplication.
- **Program-level PM answers.** Raised as an open question in "Cross-project visibility," with no consumer. Drop it until one appears.

### [NOTE] `done` in A is assumed to mean the change is usable in B for product repos

"Satisfaction is observed" treats A's slice merging into A's target as enough for product-repo edges. B builds from its own checkout. If B uses A through a pinned package, a git submodule or a deployed service, A's merge is not yet visible to B. The document draws the line between products and tool chains by the shape of the program. The real distinction is how B consumes A, which can differ edge by edge, even within `trading`.

### Run Digest

- Response length: 10966 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 311678 / 239282 / 72386 / 7136 / not computed
- Duration: 79.0 s
- Cost: $0.77 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
