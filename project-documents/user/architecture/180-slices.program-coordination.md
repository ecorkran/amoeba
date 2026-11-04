---
docType: slice-plan
layer: project
project: amoeba
parent: user/architecture/180-arch.program-coordination.md
archIndex: 180
component: program-coordination
audience: [human, ai]
description: Slice plan for Amoeba initiative 180 — the slice-writing pipeline against Squadron, the program record, the program concept as a source, edges and release, request runs in the provider, the request outcome in the asker, and a live walkthrough.
dateCreated: 20261103
dateUpdated: 20261103
status: not_started
---

# Slice Plan: Program Coordination

## Parent Document

`180-arch.program-coordination.md`

## Planning Context

Architecture-level, built on complete initiatives 100, 120 and 140. Coordination is a program stage inside the Runner's tick, so every slice extends the Runner, 100's store and 140's answerer rather than adding a process. Every edge comes from a request, but each half of the path can be built and tested without the other.

Three things shape the decomposition:

- **Squadron capability first.** The request run needs a pipeline that writes one slice into an existing plan from supplied text, or reports that the need is already met with a commit. No built-in does this. It is the one external unknown, so it is proven before anything is designed against it, as 140 was for the answering pipeline.
- **Consumer before producer.** Edges and release ship before anything creates an edge, and the provider's request runs ship before the answerer can create a request. Each slice is tested with rows written by the test; nothing in a live project changes until the last feature slice turns the request outcome on.
- **Deterministic before nondeterministic.** The program record, the concept passages, edges and release need no LLM. The request run and the request outcome are the two slices that act on a model's output, and both are bounded by checks that already exist when they land.

Slice numbers are execution order. Following the slice-planning guide, the first slice takes the plan's index (180).

## Foundation Work

1. [ ] **(180) Slice-Writing Pipeline** — The pipeline a request run uses, shipped with Amoeba beside `answering.yaml` and proven against the installed `sq` and `cf`. Given a provider checkout, the requests initiative index, and a self-contained need, it does one of two things: writes one new slice into the requests initiative, creating the initiative in the project's initiative plan first if it does not exist, and commits it to the target; or reports that the provider already meets the need and names the commit that meets it. A reader parses its reply into one of the two shapes, so later slices never parse artifacts. Its dependency on Squadron goes in `notes/001-squadron-dependencies.amoeba.md`.
   **Value:** Architectural enablement. Removes the one external unknown before request runs are designed.
   **Success Criteria:**
   - Run against a scratch CF project with no requests initiative, it creates the initiative at the given index and writes one slice in it, committed to the target, and the reply names the slice's index.
   - Run again with a second need, it adds a second slice to the same initiative and touches no other slice or initiative.
   - Given a need the scratch project already meets, it reports already met with a commit that exists on the target.
   - The reader rejects a reply with neither shape, a new-slice reply with no index, and an already-met reply with no commit.
   - The minimum `sq` version that runs it is recorded in the process contract, and the start-up `sq` probe checks the shape it depends on.
   - Any capability `sq` or `cf` lacks is filed as an issue upstream and named in this plan as a dependency of 184.
   **Dependencies:** None inside Amoeba (100, 120 and 140 complete). External: whatever Squadron or Context Forge capability the slice design finds missing.
   **Interfaces:** Provides the pipeline file, its reply shapes and the reader to 184. Extends 120's `sq` shape probes.
   **Risk Level:** Medium. It depends on an agent editing a shared plan file correctly and on a pipeline shape Amoeba has not used.
   **Relative Effort:** 3

2. [ ] **(181) Program Record** — Programs exist. A program store in its own subdirectory of the supervisor directory holds programs, members and consumption modes (declared per member, with per-pair overrides). A program inbox applies program and member registration, with body shapes in `docs/inbox-contract.md`. Each member's project config gains the index of its requests initiative, with no default. The program record names the concept document's member and path. 100's locality rule and its proof are updated to say what lives in the program store, what may not, and that a project's tick may open other members' stores read-only. The program stage is added to the Runner's tick after intents and resolutions and before readiness; in this slice it only reads members and reports those that cannot be read (unlinked, missing store, link snapshot or checkout) as blocked reasons. `amoeba inspect program` lists a program's members and its blocked list: each member's blocked nodes plus unreadable members.
   **Value:** Architectural enablement, and a visible change for the PM: a program's projects and everything blocked in them read as one list.
   **Success Criteria:**
   - Registering a program and its members through the program inbox writes the program store; a malformed body is rejected with a reason, as the project inbox does.
   - A member with no requests initiative index, or a program with no concept location, fails registration with a named error.
   - The locality proof passes with a program store present, and fails if any project's nodes, blocks or questions appear in it.
   - An unlinked member, or one whose store, link snapshot or checkout is missing, shows on the program blocked list with that reason; nothing exits, and a project in no program ticks exactly as before.
   - A failure of the program store itself exits the process as a store failure.
   - A tick with no program store behaves exactly as after 140.
   **Dependencies:** None beyond 140.
   **Interfaces:** Adds the program store and its migrations (`docs/store-contract.md`), the program inbox path and bodies (`docs/inbox-contract.md`), the program stage's place in the tick (`docs/process-contract.md`), and the requests initiative index to project config. Consumed by every later slice.
   **Risk Level:** Medium. It changes 100's locality rule and the tick order.
   **Relative Effort:** 3

## Feature Slices

3. [ ] **(182) Program Concept as a Source** — The program concept becomes a source for 140's answerer. For a question in a program member, source assembly adds the concept file as dated passages, read with `git show` from the named member's checkout on its target at a committed commit, and adds the member list and each member's part of the program. A missing snapshot, checkout or file declines the question with 140's existing source reasons. The answerer in one member never sees another member's rules, plan or PM answers as passages.
   **Value:** User value. Questions about how the program's parts fit together can be answered without the PM, and the answerer has what it needs to tell a request from an answer.
   **Success Criteria:**
   - A question in a member includes the concept passages, dated by the concept file's last commit on the named member's target; an uncommitted edit to the concept does not appear.
   - A question in a project in no program assembles exactly as after 140.
   - A missing concept file or checkout declines with 140's source reason, never silently omitted.
   - No passage from another member's rules, plan or PM answers appears in a member's passage set; a test checks it.
   - Concept passages are never trimmed under the size limit, as rules and plan passages are not.
   **Dependencies:** 181.
   **Interfaces:** Extends 143's source assembly (no new git verb). The visibility rule goes in `docs/process-contract.md`.
   **Risk Level:** Low
   **Relative Effort:** 2

4. [ ] **(183) Edges and Release** — A slice can wait on another project's slice and resume when the change lands. The program store gains edges, each from a waiting slice to a providing slice or commit, with its consumption mode. The program stage hands each project its open edges as external predecessors through `runner/lifecycle/predecessors.py`, so a slice with an open edge is not ready, and `decide()` refuses launch and resume on it. The provider's supervisor records the head of the branch named `{index}-slice.{name}` in the transaction that marks a providing slice `done`. A from-source edge is satisfied when that commit, or a named commit, is reachable from the provider's local target; a from-release edge when the PM's edge resolution arrives through the program inbox. When every edge of a slice is satisfied, the waiting project's tick submits a `resume` resolution on its question block with instructions restating the need and naming the providing slice and the observed commit; that closes the block. A PM resolution on the question block supersedes: the edges close, and anything already written in the provider stays as ordinary planned work. The program blocked list shows each open edge and what it waits on.
   **Value:** Architectural enablement. The consumer side of coordination exists and is proven with edges written by tests, before anything creates one.
   **Success Criteria:**
   - A slice with an open edge is neither launched nor resumed; with all its edges satisfied it is ready again, with no row cleared and no desired state written.
   - The branch head is recorded in the same transaction as `done`; deleting the branch afterward does not stop the edge from being satisfied once the commit is on the target.
   - A from-source edge is satisfied by a merge commit or fast-forward on the provider's local target, and not by a commit only on the slice branch.
   - A from-release edge stays open after the providing slice is `done` until an edge resolution names it; a resolution naming an unknown edge is rejected.
   - Release resumes the paused run with instructions that restate the need and name the slice and commit; the question block closes, and a later PM resolution on it is rejected as already resolved.
   - A PM resolution on the question block before release closes the edges; the provider's slice keeps running as planned work.
   - If the paused run cannot be resumed, 120's missing-run block applies and the restated need is on the block.
   - Every git read uses the existing allowlist.
   **Dependencies:** 181.
   **Interfaces:** Adds edges and the edge resolution (`docs/store-contract.md`, `docs/inbox-contract.md`). Changes 120's readiness (`predecessors.py`) and the supervisor's `done` transaction; both go in 120's contract documents.
   **Risk Level:** Medium. It changes 120's readiness and 132's `done` transaction, and release is the first resolution the coordinator submits.
   **Relative Effort:** 4

5. [ ] **(184) Request Runs** — The provider serves requests. The program store gains requests, each with its need, provider and asking slice, and an unbound edge. The provider's tick owns them: when it has a checkout a request run may take, it records the requests initiative's current slice set on the request and launches the slice-writing pipeline (180) as a journaled entry, ahead of its own next slice. A request run may take a checkout held by a paused, failed or orphaned node when the tree is clean and on the target. On a new-slice reply the edge is bound only when the next plan read shows a slice at the reported index that was absent from the recorded set. Requests-initiative slices have no implicit predecessor; while a request slice has an open edge it is driven by membership and sorts ahead of planned slices in its checkout, and a PM hold on its path still stops it. On an already-met reply the request closes and its edge waits on the named commit through 183's observation. A failed run, a malformed reply or a failed binding check puts the request and the asking slice on the program blocked list with that reason. A full requests initiative declines further requests to that member with that reason.
   **Value:** Architectural enablement. The provider side of coordination exists and is proven with requests written by tests, before the answerer can create one.
   **Success Criteria:**
   - A request written to the program store produces one request run in the provider, launched ahead of the provider's next planned slice and never overlapping another request run in the same checkout.
   - A request run launches in a checkout held by a paused node when the tree is clean and on the target, and waits when it is not.
   - A new-slice reply binds the edge only when the plan shows a new slice at that index; a reply naming an existing or absent index blocks with the binding reason.
   - The bound slice is designed and built by the provider's configured pipeline, ahead of planned work, and with no implicit predecessor; a second request slice is not held up by a stopped first one.
   - A PM hold on the request slice's path stops it.
   - An already-met reply leaves the edge waiting on the named commit, and the asker is released only when 183's observation passes.
   - A restart with a request run in flight adopts it through journal recovery and never launches a second.
   - The pipeline's models and cost cap come from per-project configuration with no defaults.
   **Dependencies:** 180, 181, 183.
   **Interfaces:** Adds requests (`docs/store-contract.md`) and the request run's command kind with its recovery observer (`docs/process-contract.md`). Changes 120's governance (membership drive), dispatch order (request priority), the checkout-hold rule (the request-run exemption), and readiness (no implicit predecessor in the requests initiative); each goes in 120's contract documents.
   **Risk Level:** High. It changes 132's checkout hold and dispatch order, and it acts on a model's reply in another project.
   **Relative Effort:** 4

6. [ ] **(185) Request Outcome** — The answerer can ask another member for a change. 140's answering stage gains a third outcome besides answer and decline: a request for a named member, carrying the need restated as self-contained. The check step confirms only that the need is real and that it belongs to the named member's part of the program, from the asker's passages and the program concept. The gate gains the request limit, which caps the open requests to one provider, centralized with the answer limit, and the refusal of a request back to a member whose checkout is held by a slice waiting on a request from the requester. Any refusal declines the question with its reason. A passing request is three writes, owned by the asker's tick: the answering entry resolved, the program store's request and edge, the question record moved to `requested`. 140's stranded sweep checks for a request row before declining an `answering` question whose entry is resolved. The question block stays open, listed as waiting on the request.
   **Value:** User value. Milestone 5: a cross-project need becomes work in the other project and the asking slice resumes when it lands, with no one relaying it.
   **Success Criteria:**
   - A question whose need belongs to another member produces a request for that member, an edge from the asking slice, and a `requested` question record; the block stays open and the program blocked list shows what it waits on.
   - A need the check step places in the asker's own part is not a request.
   - A request over the request limit, one matching a reserved term, and a request back to a member waiting on the requester each decline with a distinct reason.
   - A crash after any of the three writes is finished by the asker's next tick; a crash between the first two never turns the request into `answer_discarded`. A test kills the sequence at each point.
   - A project in no program never produces a request.
   - The request limit comes from per-project configuration with no default.
   **Dependencies:** 182, 184.
   **Interfaces:** Extends 140's question record (`requested` state and request link), the gate, the answer step's reply contract and the stranded sweep (`docs/store-contract.md`, `docs/process-contract.md`). Extends the answerer section of `projects.yaml` with the request limit.
   **Risk Level:** High. The answerer starts creating work in other repos on a model's judgment.
   **Relative Effort:** 3

## Integration Work

7. [ ] **(186) Live Walkthrough** — A real run end to end, as in 145: a throwaway program of two or three scratch CF projects in a throwaway registry, scratch checkouts, and a throwaway supervisor directory. A real pipeline run in one project stops on a question that needs a change in another; a request slice lands in the provider's requests initiative and is built; the asker waits and resumes with instructions naming the change once it is on the provider's target. A need the provider already meets is reported with a commit and releases the asker through the same observation. A from-release edge waits for the edge resolution. The real registry is untouched.
   **Value:** Verification that coordination works against real Squadron, real agents and real repos, not only fixtures.
   **Success Criteria:**
   - The three cases above happen as described, with program-store rows, journal entries and question records that show each step.
   - The walkthrough steps are recorded in the docs so it can be repeated.
   - Any request or reply shape the walkthrough meets that the fixtures lacked becomes a fixture.
   **Dependencies:** 185.
   **Interfaces:** None new.
   **Risk Level:** Low
   **Relative Effort:** 2

## Implementation Order

`180 → 181 → 182 → 183 → 184 → 185 → 186`.

- **Dependencies.** Everything reads the program record (181). Request runs (184) bind edges (183) and use the pipeline (180). The request outcome (185) needs the concept passages (182) to tell a request from an answer, and needs request runs to serve what it creates.
- **Risk.** 180 comes first because it is the only slice that can be blocked by something outside Amoeba; a gap found there has the length of 181–183 to be fixed upstream.
- **Testability.** 181 through 183 need no LLM. 184 is tested with requests written by the test, 185 with the request path already proven.
- **Parallel work.** 180 is independent of 181–183, and 182 is independent of 183, if separate worktrees are used.

## Notes

- **Behavior between slices.** After 181 a PM sees programs and one blocked list; nothing runs differently. 182 adds concept passages to members' answers. 183 and 184 change nothing in a live project, because nothing creates an edge or a request yet. 185 turns coordination on.
- **Changes to 120- and 132-owned code.** Readiness takes external predecessors (183); the `done` transaction records the branch head (183); governance, dispatch order, the checkout hold and readiness in the requests initiative change for request runs (184). Each is a contract change in 120's documents.
- **Changes to 140-owned code.** Source assembly (182); the question record, gate, reply contract and stranded sweep (185).
- **Configuration lands where it is first read.** 181 adds the requests initiative index, 184 the slice-writing pipeline's models and cost cap, 185 the request limit. None has a default.
- **The program blocked list grows by slice.** 181 lists members' blocked nodes and unreadable members, 183 adds edges, 184 request runs and checkout waits, 185 askers waiting on requests.
- **Deferred.** Everything under the architecture's "Deferred until use shows the need" stays out of this plan.

## Future Work

Living backlog; entries may be added during slice design, task breakdown, or implementation.

1. [ ] **Separate request checkouts** — If requests often wait on held checkouts or PM merges, or reverse requests are often refused, give request runs their own checkout. Dependencies: [184]. Effort: 3/5
