---
docType: architecture
layer: project
project: amoeba
archIndex: 180
component: program-coordination
initiative: program-coordination
parent: ../project-guides/001-initiative-plan.amoeba.md
dependencies: [100-arch.substrate-run-state-store, 120-arch.runner-routing-engine, 140-arch.question-answerer]
relatedSlices: []
riskLevel: medium
audience: [human, ai]
description: Architecture for program coordination. Several projects that form one product, or one tool chain, are declared as a program. When a slice in one project needs a change in another, Amoeba turns the request into a slice in the other project's requests initiative, records a cross-project edge as an extra predecessor of the waiting slice, and resumes the waiting run when the change is observed to have landed. One blocked list covers the whole program. Re-scoped from "Program Record" and moved ahead of 160 on 20261103; revised on 20261103 after four architecture review rounds, then trimmed of design surface for rare cases.
dateCreated: 20261103
dateUpdated: 20261103
status: in_progress
---

# Architecture: Program Coordination

## Overview

Program coordination is the level above projects. A **program** is a set of projects that only make sense together. Two shapes exist today. One is a product built from several repos (`trading` = `trading-data` + `trading-engine` + `trading-ui`, more coming). The other is a tool chain whose repos depend on each other's released behavior (Squadron, Context Forge, the AI project guide, Amoeba). In both, work in one project regularly needs a change in another, and today only the PM knows that, carries the request across by hand, and remembers to come back.

**The problem it addresses.** After 140, Amoeba drives each project's pipeline and answers its agents' questions, but each project is an island. An agent in `trading-engine` that needs `trading-data` to expose something can only ask, and the answerer can only answer from `trading-engine`'s own sources or decline. The question lands on the blocked list. The PM then opens the other repo, plans the change, runs it, waits for it to land, and goes back to unblock the first slice. With three or four repos in flight this is where the chaos comes from: changes that land out of order, slices that start against a contract that has not changed yet, and requests that are forgotten.

**Scope.** This component owns: (1) the **program record**, the member projects, how each member is consumed by the others, and where the program's concept document lives; (2) **cross-project edges**, each saying that a slice in one project waits on a slice in another, and what observation satisfies it; (3) **readiness and release**, which keeps a waiting slice from running while its edge is open and resumes its run when the edge is satisfied; (4) **requests between projects**, the path from an agent's question to a new slice in another member project and an edge back to the asker; (5) the **program concept as a source** for 140's answerer; (6) the **program blocked list**, one view of everything blocked across a program. It does not own how a project's pipeline runs (Squadron), launching, watching and resuming runs (120), answering a question from a project's own sources (140), notifying the PM or taking chat replies (160), or a conversation spanning projects (200).

**Motivation.** This is milestone 5 in `notes/003-milestones.amoeba.md`. It moved ahead of 160 on 20261103 because the PM's work already spans repos, and coordination across them, not comfort inside one, is the pain now.

## Design Goals

- **A cross-project need becomes work without the PM carrying it.** When an agent's question is a request for a change in another member project, the change is planned and run in that project, and the asking slice waits for it, with no person relaying the request. The only PM steps are the ones the project rules already reserve for the PM: a merge the provider's pipeline does not make, a release, and a block the PM must resolve anyway.

- **Nothing runs against a change that has not landed.** A slice that waits on another project's slice is not ready, so it is neither launched nor resumed, until the change is observed where the waiting project consumes it. Out-of-order landing is prevented by readiness itself, not by anyone remembering.

- **The waiting slice resumes knowing what changed.** Release resumes the asker's run with instructions that restate the original need and say what now exists and where: the providing slice, its project, and the observed commit.

- **Requests go first in the provider.** A request and its slice are not ordered behind the provider's planned slices or behind other requests. They take the provider's checkout ahead of planned work the moment it is free. They do not pre-empt work that holds the checkout.

- **One list per program, every wait explained.** Everything blocked across a program's projects, including slices waiting on an edge, requests waiting on a checkout, and what each waits for in turn, reads as one list. A wait only the PM can end shows as such, with its reason.

- **Each project stays a project.** A project that belongs to no program behaves exactly as it does after 140, whatever happens to any program, while the program store itself is healthy; a failure of the program store is a store failure and exits the process (Technical Considerations). A project in a program keeps its own store, plan, pipeline, checkouts and answerer configuration, and the PM's desired states are never written by the coordinator.

## Architectural Principles

- **Coordination is the Runner's, in its tick, as its own stage.** A **program stage** in the Runner tenant evaluates edges, launches request runs and binds new slices, issuing commands through the Runner's journaled control surface. The Runner remains the only part of Amoeba that issues `sq`, `cf` or `git` commands, and 180 adds no other kind of command and no new git verb. A program adds no tenant and no process.

- **The program stage feeds 120's readiness; 120 does not read the program.** Each tick the program stage computes, per project, the external predecessors (open edges), the membership-driven slices, and the request priority, and hands them to readiness, governance and the dispatch order. `runner/lifecycle` never imports the program store. Tick order within a project: intents applied, pending resolutions acknowledged (so a PM resolution that supersedes an edge closes it first), then the program stage, then readiness, governance and `decide()`. The program stage in one project's tick may open other members' stores and plan snapshots read-only, so what it sees of another member can lag by one loop.

- **An edge is a predecessor.** 120 defines a slice as ready when, among other things, its predecessor is `done`, and names `runner/lifecycle/predecessors.py` as the one place cross-project edges are added. An open edge is an extra predecessor, so the waiting slice is not ready, not current, and `decide()`'s guard refuses both launch and resume on it. Satisfying the edge makes the slice ready again; there is nothing to clear. A slice with several edges is ready only when all are satisfied. The coordinator never writes a desired-state row. Every edge in 180 is created by a request.

- **Request slices live in one requests initiative and stand alone.** Each member's registration in the program record names the index of its requests initiative (no default), so the program stage and `amoeba inspect` read it from one place. The first request run to that member creates it, so a member that never receives a request never has its plan touched. Its slices have no implicit predecessor, so one stopped or waiting request never holds up another's readiness. They share one checkout, so a stopped request slice still holds it against the next, under the held-checkout cost below, until separate request checkouts exist (184, D13). While a request slice has an open edge it is driven by program membership, a governance rule alongside "nearest row on the path", and it sorts ahead of planned slices in its checkout. A PM hold on its path still stops it. When the initiative's slice band is full, further requests to that member decline with that reason.

- **A request runs in the provider's own pipeline and checkout.** Turning a request into work means a **request run**, launched by Amoeba in the provider project, that either writes one new slice into the requests initiative or reports that the provider already meets the need, naming the commit that meets it. That commit is evidence to check, not a verdict: the edge is still satisfied only by the observation its consumption mode requires. Amoeba never edits a CF plan or another repo directly. The request carries the need, not the design; the provider's agents design it, and only they can see whether the provider already has it.

- **Requests share the provider's checkout under 132's rules, with one exemption.** A request run only adds a slice file and commits it to the target, so it may launch in a checkout held by a paused, failed or orphaned node when the tree is clean and on the target. The request slice it writes designs and builds under the normal checkout rule. The decision, and its cost: a request waits while the provider's checkout is held, and when the provider's pipeline does not merge, the checkout stays on the last finished slice's branch until the PM merges, so requests to that provider wait on that merge. Separate request checkouts are deferred until that cost shows in use.

- **The asker keeps its checkout.** A paused asker's work is in its checkout, so its run is not stopped to free it. While B waits on a request, B's checkout launches nothing else.

- **A request back to a waiting asker is refused, not deadlocked.** A request to a member whose checkout is held by a slice that is itself waiting on a request from the requester is refused (A asks B while B waits on A). That one check covers the common case, two repos negotiating a contract back and forth. It declines the question with a reason, so it reaches the PM; that is the cost until separate request checkouts exist. Longer chains across three or more members are not checked; every wait in them is still on the program blocked list with what it waits on.

- **A refused request is a decline with a reason.** A request refused by the gate, the request limit, a full requests initiative or the check above declines the question with its reason, exactly as 140 declines an answer.

- **Satisfaction is observed where the dependent consumes the provider.** Each member declares how others consume it, with a per-pair override only where one dependent differs. **From source** means the dependent builds against the provider's local checkout on its target (a sibling checkout). The provider's own tick, in the transaction that marks a providing slice `done`, records the head of its branch, named exactly `{index}-slice.{name}` from CF. The edge is satisfied when that commit, or the commit an already-met reply named, is reachable from the provider's local target. Merge commits and fast-forwards are supported; squash and rebase merges, a merge made only on a remote and never pulled, or any other way of consuming the provider count as **from a release**. A from-release edge waits, after the providing slice is `done` or an already-met reply, on the PM's **edge resolution** naming the edge. Nothing a model says satisfies an edge.

- **The PM's answer to the asker always wins.** A request leaves the asker's question block open. A PM resolution on that block supersedes the request: it applies and the request's edges close. Anything already written in the provider stays there as ordinary planned work, without membership drive or request priority. Confirming a release is a different action with a different target (an edge resolution through the program inbox), so the two never share a meaning. If release resolves the question block first, a later PM resolution on it is rejected as already resolved, as with 140's answerer.

- **No step needs the PM to act, choose or relay.** Every coordination decision has an automated answer, and every path that cannot proceed ends on the program blocked list with its reason.

- **A project belongs to at most one program.** Every later rule asks "which program is this project in" with a single lookup, so registration rejects a project already in another program.

- **The record is the memory, per project, and the program record names them.** Each project's store keeps its own nodes, questions, journal and blocks. What crosses projects (programs, members, consumption modes, edges, requests) lives in one program store. Each cross-store transition has one owning tick and an order whose partial state the owner finishes on its next tick, never lost or done twice.

## Current State

- **Stores are per project.** 100's store locality rule is one store file per project in one supervisor directory (`{project_id}.sqlite3`), and the contract proof checks that no project's rows appear in another's. The inbox applies every submission to one project's store. There is no record above a project.
- **One resident process ticks every project.** The Runner loops over all linked projects in one process. `amoeba inspect blocked` already lists every project's blocked nodes, each store opened read-only.
- **Readiness has a cross-project extension point; desired states do not fit.** A slice is ready when it is `runnable`, linked, has no blocked ancestor and its predecessor (the next lower CF index in its initiative) is `done`; `predecessors.py` is documented as where cross-project edges go. Desired states are one row per target with no cause and no stacking.
- **Checkouts are held by paused, failed and orphaned work, and by unmerged branches.** Under 132 a checkout is held by an unresolved `sq_run` and by a not-done node whose latest run is `paused`, `failed` or `orphaned`; a blocked slice holds its checkout until the PM acts. A pipeline that does not merge leaves its checkout on the slice branch. The planner orders a checkout's actions by `(initiative index, slice index)`.
- **`done` is not merged.** The supervisor marks a slice `done` when its pipeline completes; `p456` stops before the merge, which is the PM's after code review. The Runner's git allowlist is `status`, `merge-base`, `show` and `log`, with no `fetch`.
- **Questions are caught, answered or declined per project.** 140's question record has only answered and declined outcomes; its answering stage declines stranded `answering` questions and sweeps `pending` ones. Its sources are a project's committed files read from that project's checkout on its target, dated by commit.
- **A resume whose run is missing blocks.** 120 already blocks a slice whose paused run cannot be resumed, with that reason.
- **No pipeline adds one slice from a request.** Squadron 0.24.17's built-ins include `P2`, `P4` to `P6`, the `*-plan` batch pipelines and review pipelines; none writes a single slice into an existing plan from supplied text. Amoeba already ships a pipeline of its own (`answering.yaml`).

## Envisioned State

**Declaring a program.** A program is declared through the program inbox: its members, how each is consumed, and its concept document's location. Nothing is written into any member's plan until a request arrives.

**Request.** An agent in project B stops on a question that needs a change in member project A. 140's answering stage, which now sees the program concept and the member list, has a third outcome besides answer and decline: a **request** for A, carrying the need restated as a self-contained request. It passes the same gate as an answer (answer limit, PM-reserved screen) plus a request limit that caps the open requests to one provider, the only throttle on requests going first. The answering entry in B's store is resolved, the program store records the request and an unbound edge from B's slice, and B's question record moves to `requested`. B's question block stays open, listed as waiting on the request.

**Work in the provider.** A's tick owns the request. When A has a checkout a request run may take, it records the requests initiative's current slice set and the target's head on the request and launches the request run ahead of its own next slice; one pipeline per checkout means request runs to one member never overlap. The run reports one of two outcomes. **New slice:** the edge is bound only when A's next plan read shows a slice at the reported index that was absent from the recorded set. The slice is membership-driven and A's configured pipeline designs and builds it. **Already met:** the request closes and its edge waits only on the observation its mode requires, for the commit the reply named, provided the run did not move the target's head; a run that did is blocked with that reason, and anything it wrote stays on the target as ordinary planned work. A run that fails, or reports an index that does not pass the binding check, puts the request and B's slice on the program blocked list with that reason.

**Release.** B's tick owns B's edges. A from-source edge is satisfied when the recorded commit is reachable from A's local target; a from-release edge when the PM's edge resolution arrives. When every edge of B's slice is satisfied, B's tick submits a `resume` resolution on B's question block with instructions restating the need and naming the providing slice and the observed commit; that resolution closes the block. If B's paused run can no longer be resumed, 120's existing rule blocks the slice with that reason, and the restated need is on the block for the PM.

**The program view.** The program blocked list joins each member's blocked nodes with the program's open requests, edges and checkout waits: what waits, on what, and what that waits for in turn, through to the PM action at the end of a chain if there is one. 160 later delivers this list and takes replies; 200 later puts the members' agents in one conversation anchored on the program.

## Technical Considerations

- **The program store and its inbox.** A program store sits in its own subdirectory of the supervisor directory, so its file name cannot collide with a project's `{project_id}.sqlite3`. 100's locality rule and its proof change to say what may live there (programs, members, consumption modes, edges, requests), what may not (any project's nodes, blocks, questions), and that a project's tick may open other members' stores read-only. The program inbox is a second inbox path applying to the program store, with body shapes in `docs/inbox-contract.md` for program and member registration and for the edge resolution. A failure of the program store itself is a store failure and exits the process.

- **A member that cannot be read is a blocked reason, not a failure.** If a member is unlinked, or its store, link snapshot or checkout is missing, the edges and requests that depend on it show on the program blocked list with that reason, and its requests do not progress. Nothing exits, and projects in no program are untouched.

- **Crossing stores without one transaction.** Request creation is three writes in order, owned by B's tick: B's answering entry resolved, the program store's request and edge, B's question record moved to `requested`. Binding and the request run are owned by A's tick, release by B's. Each owner finishes a partial state on its next tick. 140's stranded sweep must check for a request row before declining an `answering` question whose entry is resolved, or a crash between the first two writes turns a request into `answer_discarded`.

- **Changes to 140.** The question record gains a `requested` state and a link to the request; the gate gains the request outcome and the request limit, centralized with the answer limit; the answer step's reply contract gains the request shape. The check step confirms only what B's passages and the program concept can show: that the need is real and that it belongs to A's part of the program, not B's. Whether A already meets it is the request run's call, made where A's sources are visible, and checked by observation. Release (183) answers the question record with a new `answered_by` value, `coordinator`, from the open states (`pending`, `answering`, and `requested` once it exists); every 140 reader of `answered_by` treats it as a non-answerer (not counted by the answer limit, never PM precedent, a discard for a finishing answering run).

- **Changes to 120.** Readiness takes external predecessors in `predecessors.py`; requests-initiative slices have no implicit predecessor; governance takes membership-driven slices; the dispatch order puts request runs and membership-driven slices ahead of planned slices in a checkout; the checkout-hold rule gains the request-run exemption for a clean checkout on its target; the supervisor's `done` transaction records the branch head for a providing slice, on both paths that write `done` (`record_runner_report` after a run, and hand completion observed from CF); a failed resume of a release carries the release's instructions on its block (183). All come from the program stage, and each is a contract change in 120's documents.

- **The program concept.** It is a file in one member repo, at a path the program record names, read from that member's checkout on its target at a committed commit and dated by its commit, the same way 140 reads sources. A missing snapshot, checkout or file declines the question with 140's existing source reasons; it is never silently left out.

- **The slice-writing pipeline.** No built-in fits. Amoeba ships one, as it ships `answering.yaml`. It writes one request slice, creating the requests initiative first if it does not exist, or reports that the provider already meets the need with a commit. Creating the initiative edits the project's initiative plan on the target, a shared file that slice branches also edit; this happens once per member, under the clean-on-target rule. Its review and reply contract are slice-design work; its dependency on Squadron goes in `notes/001-squadron-dependencies.amoeba.md`.

- **Cross-project visibility.** The answerer in B sees the program concept, the member list and the state of the edges and requests B is party to. It never sees another project's rules, plan or PM answers as passages. A's request run sees A's own project, as any A run does.

- **Deferred until use shows the need.** Separate request checkouts (would remove waits on held checkouts, PM merges for non-merging providers, and refused reverse requests). Automatic probes for released behavior (would add a command kind and let model output decide satisfaction). Cycle checks across three or more members. Relaunching with instructions when an asker's paused run is gone. More than one requests initiative per member. Merging duplicate requests (the second may report already met once the first lands). Hand-declared edges. Removing a program, or a member that edges or requests reference, and so moving such a project between programs.

## Anticipated Slices

- **Program record.** The program store and program inbox, program and member registration with consumption modes, the requests initiative index and the concept location, the locality rule and proof updated, unreadable members as blocked reasons, and the program blocked list in `amoeba inspect`.
- **Program concept as a source.** The program concept as dated passages in 140's source assembly, read from its member's checkout, with the visibility rule.
- **Requests.** The answerer's request outcome, check and limit, the `requested` state and the stranded-sweep change, the slice-writing pipeline and its reply contract, the requests initiative with membership drive, no implicit predecessor and request priority, the request run's checkout exemption, binding against the slice set recorded at launch, the already-met outcome, and the reverse-request refusal.
- **Edges and release.** Edges as external predecessors, branch-head recording at `done`, reachability for from-source edges, the edge resolution for from-release edges, release resuming the asker with instructions, and supersession.
- **Live walkthrough.** A throwaway program of two or three projects run against real models: a request from one project lands as a slice in another, the asker waits, and it resumes when the provider's change is on the target.

## Related Work

- Initiative plan: `user/project-guides/001-initiative-plan.amoeba.md`, initiative 180 scope and the 20261103 reorder.
- Concept: `user/project-guides/000-concept.amoeba.md`, "Multi-project programs".
- Direction: `user/notes/004-direction.amoeba.md`, no PM-in-the-loop designs and Amoeba as a supervisor over Squadron.
- Milestones: `user/notes/003-milestones.amoeba.md`, milestone 5.
- Reviews: `user/reviews/180-review.arch.program-coordination.md` (earlier rounds under `user/reviews/archive/`).
- `100-arch.substrate-run-state-store.md`: store locality, the inbox, the sole-writer model.
- `120-arch.runner-routing-engine.md` and slices 124 and 132: readiness and `predecessors.py`, governance, the checkout hold and dispatch order, the supervisor.
- `140-arch.question-answerer.md` and slices 141 to 144: the question record, source passages, the gate, the answering run.
- Contracts: `docs/store-contract.md` (store locality, desired states, question records), `docs/process-contract.md` (readiness and governance, one pipeline per checkout, git reads, the answering stage), `docs/inbox-contract.md` (intent bodies, resolutions).
- Downstream: 160 delivers the program blocked list and takes replies; 200 anchors a cross-project conversation on the program record.
