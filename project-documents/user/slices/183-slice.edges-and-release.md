---
docType: slice-design
slice: edges-and-release
project: amoeba
parent: user/architecture/180-slices.program-coordination.md
dependencies:
- 181-slice.program-record
- 123-slice.lifecycle-model-and-reconciliation
- 124-slice.intent-vocabulary
- 125-slice.run-dispatch-and-outcome-ingestion
- 127-slice.resolutions-and-resumption
- 128-slice.gates-git-and-human-steps
- 132-slice.pipeline-supervisor
- 141-slice.question-record
- 142-slice.the-gate-and-answer-submission
interfaces:
- 184-slice.request-runs
- 185-slice.request-outcome
- 186-slice.live-walkthrough
dateCreated: 20261103
dateUpdated: 20261104
status: not_started
turns: 32
promptTokens: 2984560
cachedTokens: 2851578
cacheWriteTokens: 132918
completionTokens: 36270
durationSeconds: 401.3
costUsd: 2.359647
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 2.3596472999999993
    completionTokens: 36270
---

# Slice Design: Edges and Release

## Overview

A slice can wait on another project's slice and resume when the change lands. The program store gains **edges**. Each edge goes from a waiting slice (and the question block it stopped on) to a providing slice or a named commit in another member, and carries its consumption mode and the need it stands for.

The program stage (181) grows three jobs:

- **Provider side.** It names this project's providing slices, so that when the supervisor marks one `done` it records the head of the slice's branch in the same transaction.
- **Waiting side.** It observes each open edge this project waits on. A from-source edge is satisfied when the recorded commit is reachable from the provider's local target. A from-release edge is satisfied when the PM's edge resolution arrives through the program inbox.
- **Release.** When every edge of a slice is satisfied, it submits a `resume` resolution on the slice's question block. The instructions restate the need and name the providing slice and commit. A PM resolution on that block that arrives first supersedes the edges.

Readiness takes the open edges as external predecessors through `predecessors.py`, so `decide()`'s existing guard refuses launch and resume on a waiting slice. The program blocked list shows each open edge and what it waits on.

Nothing creates an edge in this slice except tests. 184 and 185 are the producers. A live project behaves exactly as after 182.

## Value

- **Architectural enablement.** The consumer side of coordination, meaning wait, observe, release and supersede, exists and is proven with edges written by tests before anything creates one. 184 binds request slices to these edges and 185 creates them. Neither changes how an edge is satisfied or released.
- **For the PM, once 185 lands:** a waiting slice never runs against a change that has not reached the provider's target, it resumes knowing what changed, and every wait is on one list with its reason.

## Technical Scope

**Included**

- Edges in the program store (program schema migration 002), with their creation API for 184 and 185, and the effective consumption mode (closes GitHub issue #25).
- The edge resolution: a third program inbox kind, `resolve_edge`.
- The rule that `register_program` may not remove a member that a live edge references.
- Branch-head recording: project schema migration 016 (`slice_heads`). Whichever transaction marks a providing slice `done` writes it: run completion (ingest) and completion by hand (the plan stage).
- The program stage's provider side, waiting side and release, with member state through 181's `read_member` (closes GitHub issue #26).
- Readiness takes external waits (`predecessors.py`, `LifecycleTree.ready_slices`, `current_slices`).
- `AnsweredBy.COORDINATOR`, and the store operation that submits a release.
- A failed resume of a release carries the release's instructions on its block.
- Listings: edge rows on `program-blocked`.
- Contract docs: store, inbox and process.

**Excluded**

- Anything that creates an edge outside tests: requests, binding and already-met replies (184), and the request outcome (185). Hand-declared edges stay deferred (architecture).
- The `requested` question state (185). 183 defines release over the states that exist and 185 adds `requested` to that set (D8).
- Automatic probes for released behavior, relaunching an asker whose run is gone, and cycle checks (architecture, deferred).
- Unbound edges (a request before binding) and their column change: 184's migration, with its producer.
- A listing of every edge, closed ones included (GitHub issue #28).

## Dependencies

### Prerequisites

- **181 (program record).** Designed, not implemented; 183 starts after 181 merges. It uses `ProgramStore`, the program schema line and the program inbox drain (D1, D2), `read_member` with `Readable` carrying the checkout and CF project id (D6, amended by 182), the program stage seam and `RunnerHost.program_store` (D7), and the `program-blocked` listing (D8). If 181's code departs from its design, 183's tasks follow the code.
- **182** is not a prerequisite. They are independent, and either may merge first.
- **120 and 140 complete:** readiness (`predecessors.py`, `LifecycleTree`, 123; `governance.current_slices`, 124), the resolution stage and `ContinuationPlanner` (127), ingest's `record_runner_report` (125, 132), `git_read` and `read_target` (128), and `SubmissionWriter`, `_write_resolution` and the question record (141, 142).
- No external change. No new `sq`, `cf` or `git` subcommand.

### Interfaces Required

- `git_read` with the `log` and `merge-base` subcommands, and `read_target`.
- `resolve_checkout` in `amoeba.upstream.context_forge` (moved by 181).
- `Store.open_read_only` and `Store` reads of nodes, blocked states and `slice_heads` on another member's store.
- The `sq_run` entry's `PARAM_CHECKOUT`. The completing run's checkout is where its branch head is read. For a slice completed by hand, `resolve_checkout` at the slice's initiative index.

## Architecture

### Component Structure

| Component | Location | Role |
| --- | --- | --- |
| Edge schema | `store/program_schema/002_edges.sql` | The `edges` table (program schema version 2) |
| Edge operations | `store/program_edges.py` (mixed into `ProgramStore`) | `create_edge`, reads by waiting or providing project, state writes, `confirm_release` |
| Edge vocabulary | `store/program_models.py` | `EdgeState`, `EdgeTarget` (`ProvidingSlice`, `ProvidingCommit`), `EdgeWait`, `Edge` |
| Effective mode | `program/modes.py` (181's `amoeba.program` package, beside `members.py`, not under `runner/`; 184 and 185 import it) | `effective_mode(members, provider, dependent)`, pure |
| Slice heads | `store/schema/016_slice_heads.sql`, `store/runner_report.py` | `slice_heads` table. `record_runner_report` takes `branch_head` |
| Release submission | `store/release_submission.py` (mixed into `Store`) | `submit_release(blocked_state_id, instructions, detail)` in one transaction |
| Head read | `runner/program/heads.py` | Reads a providing slice's branch head before ingest or hand completion marks it `done` |
| Edge observation | `runner/program/observe_edges.py` | Per open edge: provider state, head, target, reachability. Every program-side git and `cf` read is here |
| Release decisions | `runner/program/release.py` | Pure: edges, observations and block states in, the writes to make out |
| Program stage | `runner/program/stage.py` | Grows from 181's lookup into the three jobs. Returns `ProgramView` |
| Readiness | `runner/lifecycle/predecessors.py`, `tree.py`, `intent/governance.py`, `project_view.py` | External waits as predecessors |
| Resume-failed payload | `runner/finish.py` | Adds a release's instructions |
| Listings | `inspection/program.py` | Edge rows on `program-blocked` |

`runner/lifecycle` never imports the program store. It receives a set of node ids (architecture principle).

### Data Flow

**The tick, for a project in a program** (181's order, unchanged around it):

```
intents applied; resolutions acknowledged              (unchanged)
program stage
  program = program_of(project)                         (181)
  providing = provider-side edges -> node ids           (D5)
  waiting side, for each edge this project waits on, state open|satisfied,
  in edge_id order (D10):
    block resolved?  resolved_by coordinator -> mark released   (finishes a crashed release; a satisfied edge. An open edge here cannot come from a release, so it is marked superseded)
                     anyone else             -> mark superseded (D9)
    open edge -> observe_edges -> Satisfied(commit) | Waiting(reason, detail)
                 -> write state or wait reason only when it changed
  release.plan(...): for each node among the edges read as open|satisfied (not the
  `waiting` set, which holds only open edges) that has no open edge left:
    submit_release on the question block in own store, then mark its edges released
  -> ProgramView(program, waiting = node ids with an open edge, providing)
plan reads -> head read for providing slices CF reports complete -> done + head, one txn (D6)
observe -> head read for finishing providing slices -> record_finished (done + head, one txn)
answering stage                                          (unchanged)
build view: current_slices(tree, desired, waiting)       (an open edge = not ready)
decide / act                                             (unchanged; resume of a release
                                                          goes through ContinuationPlanner)
```

**Release, across two stores.** The asker's tick owns it.

1. Each edge observed satisfied is written `satisfied` in the program store, with the commit and the time.
2. `submit_release` in the asker's store fills the question block's resolution slot (`resume`, the instructions, `resolved_by` = `coordinator`, `awaits_runner`). It writes the inbox submission row and settles the question record, all in one transaction.
3. The edges are written `released`.

A crash after step 1 repeats nothing: satisfied edges are not observed again. A crash after step 2 leaves the block resolved by `coordinator` with satisfied edges, and the next tick's first check marks them `released`. A crash after step 3 is the finished state. The next tick's resolution stage acknowledges the resolution, and `ContinuationPlanner` resumes the run, exactly as for an answerer resolution.

**Provider side.** The providing slices are the node ids named by edges in state `open` whose provider is this project. When Observe finds a finished run that will complete one of them, `heads.py` reads the slice's branch head in the run's checkout before ingest. Ingest passes it to `record_runner_report`, which writes `slice_heads` in the transaction that marks the node `done`. A providing slice CF reports complete with no run gets the same read before the plan stage marks it `done` (D6).

### State Management

- **Program store** (written only by the resident process, which hosts both writers). An edge row has exactly two writers, on disjoint columns. The asker's tick owns everything except `release_confirmed_at`: state, wait reason, satisfied fields, release and `updated_at`. `ProgramInboxTenant` writes only `release_confirmed_at` and does not touch `updated_at`; the stage only reads it. `docs/store-contract.md` states this split. 185 writes edges through the asker's tick. 184 adds one column-disjoint writer: the provider's tick sets `provider_node_id` or `provider_commit` once on an unbound edge, by compare-and-set (184, D10).
- **Provider's project store.** `slice_heads`, written by the provider's tick. Waiting projects read it read-only (181's locality rule).
- **Asker's project store.** The release resolution and the settled question record, through the same slot and submission path the answerer uses.
- **Wait reasons are stored**, unlike 181's member readability, because they come from git and `cf` reads that inspection may not make (inspection does no subprocess and does not import the Runner). Each row carries `wait_since`, set when the wait last changed, and `program-blocked` shows it in the reason.

## Technical Decisions

### D1 — An edge's shape: waiting slice and block, one target, a fixed mode, the need
Status: decided

- An edge holds the waiting project and node, and the **question block** the slice stopped on (required). It also holds the provider project, a **target**, the **mode**, the **need** text, a **state**, and observation fields.
- **Target** is exactly one of `ProvidingSlice(node_id)` (a node in the provider's store) or `ProvidingCommit(sha)` (the slice plan's "named commit", which 184's already-met reply produces). A `CHECK` requires exactly one. An unbound edge (a request before binding) is 184's, added by 184's own migration with its producer. SQLite cannot alter a `CHECK` in place, so that migration rebuilds `edges` (create new, copy, drop, rename).
- **Mode** is computed once at creation by `effective_mode` (the override for the pair if present, else the provider's `consumed`) and stored on the edge. Re-registering a member does not change an edge already open. The waiting slice was promised one observation, and the blocked list says which. Closes GitHub issue #25.
- **The need lives on the edge**, because release consumes it. 184's request references its edge and reads the need from it rather than storing a second copy.
- **States:** `open`, then `satisfied`, then `released`. `open` or `satisfied` can also go to `superseded`. `released` and `superseded` are closed. Nothing reopens an edge.
- `create_edge` checks, in one transaction, that both projects are members of the same program, that they differ, and that the need is not blank. It raises `ValueError` for a programming error. Its callers are tests in 183 and the program stage in 184 and 185.
- Rejected: one edge per slice with a list of targets, which would make partial satisfaction and per-target modes a nested structure for nothing. Also rejected: the need on the question record, because 184's request run reads it before any record exists in the provider.

### D2 — Readiness takes external waits as an argument, not a default
Status: decided

- `predecessors.py` gains `external_waits_met(node, waiting: AbstractSet[str]) -> bool`. `LifecycleTree.ready_slices(waiting)` takes the set as a **required** argument and adds that check beside `slice_predecessor_done`. `governance.current_slices(tree, index, waiting)` passes it through. `build_project_view` takes `waiting` from the tick's `ProgramView`, which is empty for a project in no program.
- A required argument, not a defaulted constructor field. The tree has four constructors, and only `build_project_view`'s tree decides readiness. A default would let a future caller silently ignore edges. `ready_slices` has one caller (`current_slices`), so the change is small.
- Only `open` edges wait. A `satisfied` edge whose slice is not yet released no longer counts as a predecessor. The slice is still blocked on its question, so it is not ready anyway, and release makes it ready through the normal resolution path.
- Nothing is written to make a slice ready again: when the edge leaves `open`, the next view leaves it out of `waiting`. The coordinator writes no desired-state row.
- `decide()` does not change. Its guard already refuses any action on a node outside `current_slices`, which covers launch and resume.
- **The tick keeps the stage's result.** 181's stage returns a `Program` that the tick discards (181, D7). 183 keeps it on the tick and grows it into `ProgramView` (members, `MemberState`, `waiting`, `providing`) that readiness and the provider-side head reads use. 183 owns any extraction from `tick.py` this needs: the stage call and the view's hand-off to `build_project_view` go in a helper beside the stage if `tick.py` grows past where it is at 181's merge.
- **Readiness is fed from a stage that runs before Observe.** So the project's own state behind its edges can be one tick old (a provider slice finished in this tick's Observe is seen as `done` next tick). That is acceptable: the architecture already accepts a one-loop lag on cross-project state, and an extra loop only delays a release, never lets a slice run early, because an open edge is the conservative state.

### D3 — From-source satisfaction is `merge-base --is-ancestor` against the target in the provider's checkout
Status: decided

- **Checkout:** for `ProvidingSlice`, `resolve_checkout` at the providing slice's initiative index in the provider's observed snapshot (181, D6, says 183 does this). For `ProvidingCommit`, the checkout `read_member` resolves, which owns the requests initiative.
- **Target:** `read_target(checkout, provider_cf_project_id)`, the same lookup the dispatch uses.
- **Reachability:** `git merge-base --is-ancestor <commit> <target>`. Exit `0` means satisfied, with the commit recorded. Exit `1` means `not_on_target`. Any other exit (an unknown commit is `128`) is `read_failed` with the command and stderr head. This is the one place 183 reads an exit code as an answer, and it is the documented contract of `--is-ancestor`, not absence inferred from failure.
- A merge commit and a fast-forward both make the head an ancestor of the target. A squash or rebase merge does not, so such an edge stays `not_on_target` until the PM resolves the question block. That is the architecture's rule: those count as from-release, and the PM declares the mode at registration.
- Calls per open from-source edge per tick: one `cf` (target) and one git, after the providing slice is `done`. None before that, because the provider's node status is a store read.

### D4 — From-release satisfaction is the PM's edge resolution, taking effect once the provider is done
Status: decided

- Body `resolve_edge`: `{"edge_id": ...}` in the program envelope (181, D2). Applying it sets `release_confirmed_at` on the edge.
- Rejections: `unknown_edge`, `edge_not_from_release` (a from-source edge is satisfied only by observation), and `edge_closed` (`released` or `superseded`). An identical re-submission on a confirmed edge is `applied`.
- The inbox records the confirmation whenever it arrives. The stage acts on it only after the provider side is complete: for a `ProvidingSlice`, when that slice is `done`; for a `ProvidingCommit`, at once, because the commit already exists. Until then the edge waits `provider_not_done`, with the confirmation still recorded, and it becomes `satisfied` on the first evaluation after `done`. This keeps the architecture's order (a from-release edge waits, after the providing slice is `done`, on the edge resolution), and nothing runs against a change that has not landed.
- The satisfied commit is the providing slice's recorded head, or the edge's named commit. The release instructions name it (D7).
- CLI: `amoeba submit resolve-edge --by operator --edge-id E`, derived by the existing flag rule.

### D5 — The branch head is read before `done` and written in the `done` transaction, for providing slices only
Status: decided

- **Which slices:** node ids named by `open` edges whose provider is this project (`ProgramView.providing`). Every other slice completes exactly as before, with no extra git call. That keeps 183 invisible in live projects, where nothing creates an edge yet.
- **Branch name:** `{cf.index}-slice.{cf.slice_name}`, built by one function beside `parse_slice_stem` in `amoeba.upstream.context_forge.slice_stem`. That module already owns the stem rule.
- **The read:** one `git log --no-walk --branches --decorate-refs=refs/heads/ --format=%H%x09%D` in the run's checkout (`PARAM_CHECKOUT`; D6 for a slice completed by hand). Each line is a tip commit and its branch names. The head is the commit whose name list contains the branch exactly. Absence is a missing line, never an exit code (143, D2). `--branches=<name>` was rejected because git appends `/*` to a pattern with no glob character, so it never matches the branch itself (checked against git 2.50).
- **The record:** `record_runner_report(..., branch_head=BranchHead(branch, commit | None, missing, detail))` writes one `slice_heads` row in the transaction that writes `done`. A read that succeeds and shows no such branch, or a slice with no CF name, records `commit` null with `missing` = true, and the edge waits `branch_head_missing`, which only the PM's resolution of the question block ends. That happens only when the branch was deleted before `done` was observed, or the slice has no CF name.
- **The edge must exist before the providing slice completes.** A head is recorded only for slices an `open` edge names at `done`. An edge created against an already-`done` slice would wait `branch_head_missing`. Request slices satisfy this, because 184 binds an edge before its slice can run. It is a contract for every producer: an already-done provider is referenced by `ProvidingCommit`, never by `ProvidingSlice`. A test pins the result of breaking it: an edge on an already-`done` slice waits `branch_head_missing`.
- **A refused or failed read:** a budget refusal leaves that entry unfinished this tick. Observation repeats next tick, and finishing is idempotent on re-entry (125). A git failure records `commit` null, `missing` = false, with the failure as the row's `detail`, so the run's outcome is not held back by a git problem. A failure is usually transient (an `index.lock` collision, a checkout briefly unavailable), so it is not final: while a providing slice's row has `commit` null and `missing` false, `observe_edges.py` re-reads the head each tick with the same command, in the checkout `resolve_checkout` gives at the slice's initiative index, under the tick budget. The edge waits `read_failed` meanwhile. A read that finds the branch fills `commit`; one that succeeds without it sets `missing`, and the edge waits `branch_head_missing`. The provider's store stays written only by the provider's tick: the waiting tick's re-read feeds its own satisfaction check and is not written back to `slice_heads`.
- **After `done`:** deleting the branch changes nothing. The commit is recorded, and reachability needs only the commit object, which the merge carried to the target.

### D6 — A slice completed by hand records its head the same way
Status: decided

- `complete_observed_slices` marks `done` a slice CF reports complete with no run (the PM did it by hand). For a providing slice, the plan stage first calls `heads.py` with the checkout `resolve_checkout` gives at the slice's initiative index. A new store call, `complete_slice(node_id, branch_head)`, then writes `done` and the `slice_heads` row in one transaction. Every other slice keeps `update_node_status` and makes no git call.
- The plan stage already runs under the tick budget. A budget refusal leaves the slice `runnable` this tick, and the completion pass repeats on the next plan read. An unresolvable checkout records `commit` null with the reason as `detail`, as a failed read does (D5).
- So the slice plan's rule ("recorded in the transaction that marks a providing slice `done`") holds on both paths that write `done`.

### D7 — Release instructions: fixed text, defined once, naming each edge's provider
Status: decided

`release_instructions(need, edges)` in `release.py`. Each satisfied edge gives one line, and the text around them is fixed:

```
The change this run was waiting on has landed. Continue from where you stopped.
Need: <need>
- <provider> slice <index>-slice.<name>: commit <sha> is on <provider>'s target <target>.
- <provider> already meets this need at commit <sha>, now on its target <target>.
- <provider> slice <index>-slice.<name>: done at commit <sha>, and the PM confirmed it is released.
```

- A slice with several edges has one need per edge. When the needs are identical they are written once. Otherwise each edge line is preceded by its own `Need:` line.
- `detail` on the resolution is the fixed `RELEASE_DETAIL` ("released by program coordination"), and `resolved_by` and `submitted_by` are `coordinator`.
- The target name is the one observed when the edge was satisfied. It is stored on the edge as `satisfied_target`.

### D8 — `submit_release`: the answerer's submission path with the coordinator's name
Status: decided

- One `BEGIN IMMEDIATE` transaction in the asker's store. Read the block. A missing block row raises: `question_block_id` is required (D1), so its absence is a programming error, not a wait reason. If it is already resolved, return `block_resolved` and write nothing (the caller then applies D9). Otherwise fill the slot through `_write_resolution` (`decision` = `resume`, `awaits_runner` = true) and insert the submission row through `SubmissionWriter`. Settle the question record linked to the block when its state is in `RELEASABLE_STATES`.
- `RELEASABLE_STATES = {pending, answering}` in 183. 185 adds `requested`. The record goes to `answered` with `answered_by = coordinator` and `answer` = the instructions. A record already `declined` keeps its decline. The block resolution is what resumes the run. If an answering run was in flight, its finish finds the record no longer `answering` and discards, which is 144's existing path.
- `AnsweredBy.COORDINATOR = "coordinator"` joins the vocabulary. `answered_by` is checked in code, not by a SQL `CHECK` (migration 013), so no migration is needed for it. Every 140 reader of `answered_by` treats it as a non-answerer, checked 20261103 against the code: the answer limit counts only `answerer` (`COUNT_ANSWERER_ANSWERS_IN_RUN`); PM precedent takes only `pm` (`sources.py`, so a release is never precedent); and a finishing answering run reports `submitted` only for `answerer`, otherwise `discarded` (`finish._already_settled`). A test pins each.
- These 120 and 140 changes (`coordinator`, `RELEASABLE_STATES`, the release-only resume-failed payload in D12, and `branch_head` on the `done` writes) are listed in the architecture's "Changes to 120" and "Changes to 140", so that 184 and 185 have one source.
- Because the slot is filled through the shared writer, a later PM resolution on the block is rejected as already resolved by the inbox's existing rule. Nothing new is needed.

### D9 — Supersession is detected from the block, before observation
Status: decided

- In the stage, before observing, each `open` or `satisfied` edge whose question block is resolved is closed:
  - **Resolved by `coordinator`:** this edge's own release, interrupted after step 2. A `satisfied` edge is marked `released`; an `open` edge cannot belong to a release (a release needs every edge satisfied), so it is marked `superseded`.
  - **Resolved by anyone else:** a PM resolution (resume or stop) supersedes. Mark it `superseded`.
- The stage runs after resolutions are acknowledged, so a PM `resume` that arrives in the same tick closes the edges before readiness reads `waiting`, and the slice resumes this tick (architecture tick order).
- Anything already done in the provider stays as ordinary work. 183 owns no provider-side state for an edge beyond `providing`, which drops the slice once its edge closes. 184 removes membership drive and request priority on the same signal.

### D10 — Wait reasons: a closed vocabulary, written only on change
Status: decided

`EdgeWait` (StrEnum), stored with a detail and `wait_since`. The first matching reason wins, checked in this order:

| Wait | When |
| --- | --- |
| `provider_unreadable` | The provider cannot be read for this edge: `read_member` returns `Unreadable` (detail: 181's reason and detail), the providing node is not in its store, or no checkout resolves at the providing slice's index. The detail names which. |
| `provider_not_done` | The providing slice is not `done`. |
| `branch_head_missing` | Done with no recorded commit (D5, D6). Applies to from-source and from-release alike, since release names the commit. |
| `awaiting_release` | From-release, not yet confirmed. |
| `not_on_target` | From-source, commit not reachable from the target. |
| `read_failed` | A git or `cf` read failed, including a head read that failed at `done` and is being retried (D5). The detail is the command and the stderr head. Cleared by the next read that succeeds. |

- A member store failure is a wait reason, never an exit (181, D6). A program store failure exits as a store failure (181, D7).
- Edges are evaluated in `edge_id` order. A budget refusal stops evaluating the remaining edges this tick and leaves them as they are; they are evaluated on a later tick. Open edges still count in `waiting`, so a refusal is always safe. No fairness ordering: a program has a handful of edges, and a refusal that recurs after the first edge on every tick is not a case the budget produces in practice.
- A row is written only when its state or wait changes, and `wait_since` is set with it. Every such write counts toward `tick.wrote`.

### D11 — The member rule for `register_program`
Status: decided

`ProgramStore.apply_submission` checks, inside the same submission transaction, whether a `register_program` replace would drop a member that any edge references as waiting or provider. If so it is rejected with 181's reserved code `member_referenced` and writes nothing. Any edge counts, closed ones included, so no edge row ever names a project that is no longer a member; removing a referenced member is deferred (181, Future Work "Member and program removal"). This implements for edges the rejection 181, D3, reserved. 184 adds the same check over requests.

### D12 — A failed resume of a release keeps the release's instructions on its block
Status: decided

- `_record_resume_failed` (`runner/finish.py`) adds `resume_instructions` to the block payload only when the failed entry carried out a resolution whose `resolved_by` is `coordinator`. It reads the instructions from the blocked state the entry's parameters name. A PM's resolution resume fails exactly as before.
- So when a released asker's run is gone, 120's existing missing-run block applies, and the restated need is on that block for the PM, as the slice plan requires.

### D13 — Listings
Status: decided

- `program-blocked` gains one row per edge in state `open` or `satisfied`: `program_id`, `project_id` (waiting), `node_id`, `title`, `blocked_on` = `edge`, `reason` = `"<wait>: <detail>"` (or `satisfied: awaiting release` for a satisfied edge), `blocked_state_id` = the question block, `context` = the edge id (what `resolve-edge` names; 186, D9), and the remaining columns empty. A satisfied edge whose release is pending is listed so that a release that fails to land is visible.
- The reason ends with ` (since <wait_since>)`, so a wait that has stood for a long time, for example while the process is stopped, reads as such.
- No listing of closed edges: nothing in 183's plan needs one (GitHub issue #28).
- With no program store, no edge rows are listed, as in 181.

### Technology Choices

No new library. The existing store machinery, program inbox, `git_read` (`log`, `merge-base`) and `read_target`.

### Patterns and Conventions

- Every vocabulary is a `StrEnum` defined once (`EdgeState`, `EdgeWait`, the `edge` blocked-list kind, `ProgramRejection` additions, `ProgramSubmissionKind.RESOLVE_EDGE`), and each is pinned to its SQL `CHECK` by a test.
- `release.py` is pure and in the purity check. All I/O is in `observe_edges.py`, `heads.py` and the stage.
- The release instruction lines and `RELEASE_DETAIL` are constants beside `release_instructions`. Tests import them.

## Implementation Details

### API Contracts

```python
# store/program_models.py
class EdgeState(StrEnum): OPEN; SATISFIED; RELEASED; SUPERSEDED
@dataclass(frozen=True) class ProvidingSlice: node_id: str
@dataclass(frozen=True) class ProvidingCommit: sha: str
type EdgeTarget = ProvidingSlice | ProvidingCommit

# ProgramStore (store/program_edges.py)
create_edge(*, waiting_project, waiting_node_id, question_block_id: str,
            provider_project, target: EdgeTarget, mode: ConsumptionMode, need: str) -> Edge
edges_waiting(project_id, states: AbstractSet[EdgeState]) -> list[Edge]
edges_providing(project_id) -> list[Edge]                           # open only (D5)
record_wait(edge_id, wait: EdgeWait, detail: str, at) -> bool        # False: unchanged
mark_satisfied(edge_id, commit: str | None, target: str | None, at)
close_edges(edge_ids, state: EdgeState, at)                         # released | superseded

# program/modes.py
def effective_mode(members: Sequence[Member], provider: str, dependent: str) -> ConsumptionMode

# Store (store/release_submission.py)
submit_release(blocked_state_id, *, instructions: str, detail: str) -> ReleaseOutcome   # submitted | block_resolved

# Store.record_runner_report gains: branch_head: BranchHead | None  (keyword, no default)
# Store (store/runner_report.py)
complete_slice(node_id, branch_head: BranchHead) -> None   # hand completion: done + head, one txn (D6)

# runner/program/stage.py
@dataclass(frozen=True)
class ProgramView:
    program: Program
    waiting: frozenset[str]      # this project's node ids with an open edge
    providing: frozenset[str]    # this project's node ids an open edge waits on
```

**Program inbox body** (`docs/inbox-contract.md`, "Program submissions"):

| Kind | Field | Rule |
| --- | --- | --- |
| `resolve_edge` | `edge_id` | Non-blank. Unknown keys refused. |

New rejection codes: `unknown_edge`, `edge_not_from_release`, `edge_closed`. `member_referenced` (reserved by 181) is now produced for edges (D11).

### Database / Storage Schema

`store/program_schema/002_edges.sql` (program schema version 2):

```sql
CREATE TABLE edges (
  edge_id TEXT PRIMARY KEY, program_id TEXT NOT NULL REFERENCES programs(program_id),
  waiting_project TEXT NOT NULL, waiting_node_id TEXT NOT NULL, question_block_id TEXT NOT NULL,
  provider_project TEXT NOT NULL, provider_node_id TEXT, provider_commit TEXT,
  mode TEXT NOT NULL CHECK (mode IN ('from_source', 'from_release')),
  need TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('open', 'satisfied', 'released', 'superseded')),
  wait TEXT, wait_detail TEXT, wait_since TEXT,            -- wait CHECKed against EdgeWait
  release_confirmed_at TEXT,
  satisfied_commit TEXT, satisfied_target TEXT, satisfied_at TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, closed_at TEXT,
  CHECK (waiting_project <> provider_project),
  CHECK ((provider_node_id IS NULL) <> (provider_commit IS NULL)));
CREATE INDEX edges_by_waiting ON edges (waiting_project, state);
CREATE INDEX edges_by_provider ON edges (provider_project, state);
```

`store/schema/016_slice_heads.sql` (project schema version 16):

```sql
CREATE TABLE slice_heads (
  node_id TEXT PRIMARY KEY REFERENCES nodes(id),
  branch TEXT,                 -- null when the slice has no name
  head_commit TEXT,            -- null when absent or unreadable
  missing INTEGER NOT NULL CHECK (missing IN (0, 1)),  -- 1: read succeeded, no branch (final); 0 with null commit: read failed, retried (D5)
  detail TEXT, recorded_at TEXT NOT NULL,
  CHECK (NOT (missing = 1 AND head_commit IS NOT NULL)));
```

The locality rule's allowed program-store set gains `edges`, and the proof's table list follows. `slice_heads` is a project table. A test asserts it never appears in the program store.

## Integration Points

### Provides to Other Slices

- **184:** `create_edge` (an edge exists before its providing slice can complete, D5), the `edges` table for 184's own migration to extend with unbound edges and its `bind_edge`, `ProvidingCommit` for already-met replies satisfied by D3 and D4 unchanged, `ProgramView.providing` (184 adds membership drive and request priority from it), the need on the edge, the `member_referenced` check to extend over requests, and D9's supersession signal.
- **185:** `create_edge` (the same D5 contract), `effective_mode`, `submit_release`'s `RELEASABLE_STATES` to extend with `requested`, and the edge rows the answerer's passages will show.
- **186:** `program-blocked` edge rows, and the `edges` rows in the program store, as the evidence of each step.

### Consumes from Other Slices

- **181:** program store, migrations line, program inbox drain and envelope, `read_member`, the stage seam and its place in the tick, `program-blocked`. A member that cannot be read becomes a wait reason. A program store failure exits.
- **120 (123 to 128, 132):** readiness, governance, the resolution stage and `ContinuationPlanner`, `git_read`, `read_target`, `resolve_checkout`, ingest's `done` transaction, `_record_resume_failed`. Changed only as D2, D5, D6 and D12 say. Each change goes in 120's contract documents.
- **140 (141, 142):** the resolution slot writer, the submission writer, the question record and its transitions.

## Success Criteria

### Functional Requirements

- A slice with an `open` edge is not in `current_slices`, so it is neither launched (a runnable slice) nor resumed (a slice with an applied resume resolution). When all its edges leave `open` it is current again, with no row cleared and no desired state written.
- A providing slice gets a `slice_heads` row in the same transaction as `done`, whether its run completed it or CF reported it complete with no run. A slice with no edge gets none and makes no extra git call. After deleting the branch, the edge is still satisfied once the commit is on the target.
- A from-source edge is satisfied by a merge commit or a fast-forward on the provider's local target, and not by a commit that is only on the slice branch.
- A from-release edge stays `open` (`awaiting_release`) after the providing slice is `done` until `resolve_edge` names it. A `resolve_edge` applied before the slice is `done` is recorded, the edge stays `provider_not_done`, and it is satisfied only after `done`. `resolve_edge` on an unknown edge, a from-source edge, or a closed edge is rejected with its code.
- Release resumes the paused run with instructions that restate the need and name the provider, slice and commit. The question block closes, the record is `answered` by `coordinator`, and a later PM resolution on that block is rejected as already resolved.
- A PM resolution on the question block before release supersedes every edge of that block. The provider's slice keeps running as planned work.
- If the released run cannot be resumed, 120's missing-run block applies and carries `resume_instructions` with the restated need.
- A crash between any two of release's three writes is finished by the next tick, with no second resolution (tests stop after each write).
- `register_program` that would drop a member any edge references is rejected `member_referenced` in the same submission transaction and writes nothing; a test covers an open and a closed edge.
- `program-blocked` shows each open or satisfied edge with its wait reason and since when it has stood.
- An edge row is written only when its state or wait changes; a tick that observes no change writes nothing to the program store.
- A head read that fails at `done` leaves the edge waiting `read_failed`, and the edge is satisfied once a later read finds the branch and its commit is on the target, with no PM step. Only a read that succeeds without the branch, or a slice with no name, waits `branch_head_missing`.
- A project in no program, and a member with no edges, tick with the same writes, commands and journal as after 181 and 182.

### Technical Requirements

- Every git read uses `git_read` with `log` or `merge-base`. A test counts the calls per edge (none before `done`, one `cf` and one git after) and returns `None` or skips the edge on each budget refusal.
- The git-backed tests use the existing `tests/runner/git_repo.py` helper to build a provider repo with a slice branch merged by merge commit, by fast-forward and by squash, and an unmerged branch.
- `release.py` passes the purity check. The vocabularies are pinned to their `CHECK`s. The locality proof covers `edges` and `slice_heads`. The import rules hold (`runner/lifecycle` does not import the program store).
- Format, lint and typecheck (`ruff`, `pyright` strict) pass, along with the full suite.
- Docs: `docs/store-contract.md` (edges, `slice_heads`, locality set, `coordinator`, `submit_release`), `docs/inbox-contract.md` (`resolve_edge`, rejection codes, `coordinator` as a submitter), `docs/process-contract.md` (the program stage's three jobs, readiness with external waits, the `done` transaction's head, release and supersession, git reads), and `CHANGELOG.md`.

### Integration Requirements

- 184 can add unbound edges in its own migration and rely on D3 to D9 unchanged.
- 185 can create an edge, extend `RELEASABLE_STATES`, and rely on release and supersession unchanged.

### Verification Walkthrough

Draft; refined after implementation. Nothing in 183 creates an edge outside tests, so the proof is the test suites plus a scripted two-project scenario. Seeing release against real runs is 186.

1. **Store and inbox.**
   ```bash
   uv run pytest tests/store/test_program_edges.py tests/store/test_release_submission.py \
       tests/store/test_slice_heads.py tests/process/test_program_inbox.py -k "edge or release or head" -v
   ```
   Expected: `create_edge` validations; state transitions and `CHECK`s; `resolve_edge` applied and each rejection; `member_referenced` over edges; `submit_release` submitted, `block_resolved`, and record settling by state; the head written in the `done` transaction by `record_runner_report` and by `complete_slice`.

2. **Readiness.**
   ```bash
   uv run pytest tests/runner/lifecycle tests/runner/intent -k "waiting or external" -v
   ```
   Expected: a runnable slice in `waiting` is not ready and is ready again when removed. An applied resume resolution on a waiting slice produces no `ResumeRun`.

3. **Observation, git-backed.**
   ```bash
   uv run pytest tests/runner/program/test_heads.py tests/runner/program/test_observe_edges.py -v
   ```
   Expected: the head found by exact branch name and absent when missing; satisfied after a merge commit and after a fast-forward; `not_on_target` for an unmerged branch and for a squash merge; still satisfied after the branch is deleted; each wait reason in D10; the call counts.

4. **Release scenario.**
   ```bash
   uv run pytest tests/runner/program/test_release_scenario.py -v
   ```
   Expected, with two scratch member stores, two scratch repos and a fake `sq`:
   - Edge from the asker's paused slice to the provider's slice. Ticks show `provider_not_done`.
   - The provider's run completes, and the head is recorded. Variant: CF reports the slice complete with no run, and the plan stage records the head.
   - `not_on_target` until the test merges the branch into the provider's target.
   - Satisfied. Release writes the resolution. The next tick resumes the run with the instructions text.
   - A late PM resolution is rejected.
   - Variants: from-release with `resolve_edge`; a PM resolution first (superseded); a crash after each release write; a resume whose run is gone (the block carries `resume_instructions`).

5. **Inspection on a throwaway supervisor.** With the scenario's supervisor directory kept (`AMOEBA_KEEP_SCENARIO_DIR`, provided by the scenario test):
   ```bash
   AMOEBA_STORE_DIR=<kept dir> amoeba inspect program-blocked
   ```
   Expected: open and satisfied edges appear as `edge` rows, with their wait reason and evaluation time.

6. **Everything.**
   ```bash
   uv run ruff check . && uv run pyright && uv run pytest -q
   ```

## Risk Assessment

### Technical Risks

- **Readiness and the `done` transaction are 120's core.** A mistake in `waiting` holds back or releases the wrong slice. A mistake in the head read delays or breaks completion.
- **Release is the first resolution Amoeba submits on its own judgment of an observation**, across two stores without one transaction.

### Mitigation Strategies

- `waiting` and `providing` are empty for every project with no edge, and a regression test pins identical ticks for such projects. Nothing in a live project creates an edge until 185.
- The head read runs only for providing slices, and a git failure records a null head instead of holding the run's outcome back.
- Release reuses the answerer's slot and submission writer and 127's acknowledgment and continuation path unchanged. The crash test stops after each of the three writes.

## Implementation Notes

### Development Approach

1. Program schema 002, `program_models`, `program_edges`, `effective_mode`, and the `member_referenced` check over edges in `apply_submission`. Store tests.
2. The `resolve_edge` kind: envelope, CLI, apply and rejections. Inbox tests.
3. Project schema 016, `BranchHead`, and `record_runner_report(branch_head=...)`. `submit_release` and `AnsweredBy.COORDINATOR`. Store tests.
4. Readiness: `predecessors.external_waits_met`, `ready_slices(waiting)`, `current_slices`, `build_project_view`. Lifecycle tests and the no-edge regression test.
5. `heads.py` and the branch-name function, wired before `record_finished`. `observe_edges.py`. Git-backed tests.
6. `release.py` (pure) and the stage's three jobs, then the `ProgramView` on the tick. `_record_resume_failed`'s instructions. The scenario test with crash points.
7. Listings, the locality proof, contract docs and CHANGELOG.

Relative effort: 4.

### Special Considerations

- **Lag.** The provider's `done` and the asker's observation are in different ticks, and release's resume is acknowledged on the tick after release. A release takes up to two loops after the merge. The architecture accepts a one-loop lag on other members' state.
- **Cost per tick.** For a member with no edges, one program store read (already 181's). For each open edge, one read-only open of the provider's store, plus, after `done`, one `cf` and one git call, under the tick budget.
- **The need is data.** It is stored and rendered verbatim into resume instructions. It never selects code paths.
- **No secrets.** Edges hold ids, commits and the need text written by 185's answerer.
