---
docType: slice-design
slice: request-runs
project: amoeba
parent: user/architecture/180-slices.program-coordination.md
dependencies:
- 180-slice.slice-writing-pipeline
- 181-slice.program-record
- 183-slice.edges-and-release
- 124-slice.intent-vocabulary
- 125-slice.run-dispatch-and-outcome-ingestion
- 128-slice.gates-git-and-human-steps
- 132-slice.pipeline-supervisor
- 144-slice.answering-run
interfaces:
- 185-slice.request-outcome
- 186-slice.live-walkthrough
dateCreated: 20261103
dateUpdated: 20261104
status: not_started
turns: 26
promptTokens: 2626329
cachedTokens: 2455522
cacheWriteTokens: 170763
completionTokens: 41821
durationSeconds: 443.7
costUsd: 2.694136
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 2.6941357
    completionTokens: 41821
---

# Slice Design: Request Runs

## Overview

The provider serves requests. The program store gains **requests**. Each request belongs to one **unbound edge** (183), which holds the need, the asking slice and its question block. The provider's tick owns the request from creation to close:

1. **Launch.** When the checkout that owns the provider's requests initiative is free for a request run, the tick records the initiative's current slice set and the target's head on the request. It then launches the slice-writing pipeline (180) as a journaled `sq_request` entry, ahead of the provider's own next slice. The checkout may be held by a paused, failed or orphaned node, but the tree must be clean and on the target.
2. **Reply.** A completed run's reply is parsed by 180's `read_reply`.
   - **New slice:** the edge is bound to the new slice only when the next plan read shows a slice at the reported index that was absent from the recorded set.
   - **Already met:** the edge is bound to the named commit, provided the run did not move the target's head. 183's observation then decides when the asker is released.
3. **Failure.** A failed run, a missing or malformed reply, a failed binding check, a moved head or a full requests initiative ends the request `failed` with that reason. The request and the asking slice both show on the program blocked list.

Requests-initiative slices have no implicit predecessor. While a request slice has an open edge it is **driven by membership** and **sorts ahead** of planned slices in its checkout. A PM hold on its path still stops it.

Nothing outside tests creates a request in this slice. 185 is the producer. A live project behaves exactly as after 183.

## Value

- **Architectural enablement.** The provider side of coordination exists and is proven with requests written by tests, before the answerer can create one. 185 only has to call `create_request` and decline what 184's band check says is full.
- **For the PM, once 185 lands:** a request from another member becomes a slice in this project's requests initiative and is built ahead of planned work, with no relaying. Every request that cannot proceed shows on the program blocked list with its reason.

## Technical Scope

**Included**

- Program schema migration 003: the `requests` table. It also rebuilds `edges` so that an edge may be unbound, and adds two edge waits.
- `create_request` (request and unbound edge in one transaction) and the request state machine.
- The `sq_request` command kind, its required keys and its recovery observer. The `request` node kind that carries the entry in the provider's store.
- The **request stage** in the provider's tick: observe and finish request runs, bind, and launch.
- The checkout rule for request runs, which is 132's hold with the request-run exemption, plus the clean-on-target check.
- The binding check against the recorded slice set, gated on a plan read that started after the reply.
- The requests band: the full-initiative and band-collision checks, exported for 185.
- Readiness and dispatch changes: no implicit predecessor in the requests initiative, membership drive, and request priority in the sort key.
- Per-project configuration: a `requests` section with `model` and `max_cost_usd`, with no defaults. Start-up wiring of 180's probe.
- 183's edge observation of an unbound edge, and supersession closing a pending request.
- `register_program`: the `member_referenced` check over requests (181, D3).
- `program-blocked` request rows.
- Contract docs: store, inbox and process.

**Excluded**

- Creating a request from a question, the request limit, and the reverse-request refusal (185).
- The pipeline file, its reply parser and its probe (180). 184 launches, parses and wires them.
- How a bound edge is satisfied and released (183, unchanged).
- Separate request checkouts, merging duplicate requests, and relaunching a lost request run (architecture, deferred).
- A listing of closed requests. Closed requests stay in the program store. GitHub issue #28 covers closed edges, and the same listing would cover requests.

## Dependencies

### Prerequisites

- **180, 181 and 183** designed, not implemented. 184 starts after 183 merges. If their code departs from their designs, 184's tasks follow the code.
- **180's launch argv is provisional** until 180's "finalize against shipped syntax" task completes. 184 builds the argv in one function from 180's constants (D7) and does not otherwise depend on its spelling.
- **External:** Squadron #241 (per-run cost cap) and the run I/O directory and guarded commit issue that 180 files (180, D8). 184's own tests use a stub `sq` and do not need them. The start-up probe on a real `sq`, and any real request run, need a release that has them. Real runs are proven in 186.
- 120, 132 and 140 complete. 182 is independent.

### Interfaces Required

Only the seams 184 changes or calls into are listed; everything else is used as its owner documents it.

- **180:** `prepare_request_directory`, `read_reply` and `probe_slice_writing_pipeline`.
- **181:** each member's `requests_initiative`, the program stage seam, `apply_submission`'s reserved `member_referenced` code, and the `program-blocked` listing.
- **183:** the `edges` table (rebuilt here), `EdgeWait`, `ProgramView.providing`, D9 supersession, and the `waiting` argument to readiness (wrapped here).
- **120 and 132:** `checkout_holders` (`dispatch/hold.py`), the fresh-launch rule, `PlanStage`, `supervision_entries` and the dispatch `SortKey`, all changed here; launch, observation and recovery used as `sq_answer` uses them (144's pattern).

## Architecture

### Component Structure

| Component | Location | Role |
| --- | --- | --- |
| Request schema | `store/program_schema/003_requests.sql` | The `requests` table. Rebuilds `edges` to allow unbound edges and the two new waits |
| Request vocabulary | `store/program_models.py` | `RequestState`, `RequestWait`, `RequestFailure`, `Request` |
| Request operations | `store/program_requests.py` (mixed into `ProgramStore`) | `create_request`, reads, state writes, `bind_edge` |
| Request node and entry | `store/request_run.py` (mixed into `Store`) | `begin_request_run`: the `request` node and the `sq_request` entry in one transaction |
| Journal kind | `store/journal_models.py` | `CommandKind.SQ_REQUEST`, its required keys. `supervision_entries` also drops it |
| Requests band | `program/band.py` | `requests_band(nodes, requests_index) -> BandState`. Pure and shared with 185 |
| Launch | `runner/request_run/launch.py` | Checkout, check, slice set, I/O directory, argv, journal, spawn |
| Finish | `runner/request_run/finish.py` | Run outcome, reply, head check, recording the reply |
| Binding | `runner/request_run/bind.py` | Pure: request, tree and read freshness in, a bind or a failure out |
| Request stage | `runner/request_run/stage.py` | Observe, finish, bind, then launch, once a tick |
| Checkout rule | `runner/dispatch/hold.py` | `checkout_holds` separates in-flight holders from stopped ones. `sq_request` entries hold |
| Readiness value | `runner/lifecycle/readiness.py` | `ProgramReadiness`: three frozen node-id sets. Owned by lifecycle; imports nothing from `runner/program` |
| Readiness | `runner/lifecycle/predecessors.py`, `intent/governance.py`, `dispatch/build_view.py`, `dispatch/facts.py` | No implicit predecessor, membership drive, request priority |
| Program stage | `runner/program/stage.py`, `observe_edges.py` | Fills `ProgramView.readiness`. Unbound edges wait on their request |
| Listings | `inspection/program.py` | `request` rows on `program-blocked` |

Also changed in place: `PlanStage` (`mark_due`, `read_completed_since`, D9), `project_config.py` (`RequestSettings`, D14) and the start-up probe wiring (D14).

`runner/lifecycle` and `intent/` still never import the program store or `runner/program`. They receive node-id sets in a value they own (183's principle); the program stage imports `runner/lifecycle/readiness.py` to fill it, never the reverse.

### Data Flow

**The provider's tick, for a project in a program** (new steps marked `+`):

```
intents applied; resolutions acknowledged                   (unchanged)
program stage (181, 183)
  + ProgramView.readiness: waiting, membership_driven, standalone_initiative
  + unbound edges this project waits on: wait = the request's state (D11)
observe sq_run entries; probes; plan reads                  (unchanged; a link marked due is read)
record finished sq_run runs                                 (unchanged)
+ request stage, for requests whose provider is this project:
    1 observe: each unresolved sq_request entry -> poll -> finished? finish (D8)
    2 bind:    each `replied` request whose link has a read completed since reply -> bind | fail (D9)
    3 launch:  oldest `pending` request, if none is `running` or `replied` -> launch | wait (D5, D6)
answering stage                                             (unchanged)
build view: current_slices(tree, desired, readiness)        (D12, D13)
check; decide; act                                          (sq_request in flight holds its checkout)
```

The request stage runs before the view is built. A request run it launches is an unresolved entry by the time `checkout_holders` is computed, so `DispatchPlanner` sees the checkout as held. That is how a request run goes ahead of the provider's next slice in the same tick.

**One request, across two stores and two ticks:**

```
185 (asker's tick) ── create_request ──▶ program store: request `pending` + edge `open`, unbound
provider tick T   ── launch ──▶ provider store: `request` node + `sq_request` entry (one txn)
                                program store: request `running` (slice set, head, run id)
                                sq run slice_writing.yaml in the checkout
provider tick T+k ── finish ──▶ program store: request `replied` (new_slice, index); link marked due
                                provider store: entry resolved, request node `done`
provider tick T+k+1 plan read creates the slice node
                  ── bind ──▶  program store: edge -> ProvidingSlice(node), request `bound`
provider tick T+k+2 the slice is membership-driven and launches ahead of planned work
asker ticks       ── 183 observes the edge as usual: provider_not_done ... satisfied ... released
```

On an already-met reply, finish checks the target head and binds the edge to `ProvidingCommit(sha)` in the same step. The request goes to `met`, and there is no plan read.

### State Management

- **Program store.** Request rows are created by the asker's tick (`create_request`, 185), then written only by the provider's tick. Edge rows keep 183's writers. The asker's tick writes state, waits, satisfaction and release. The program inbox writes `release_confirmed_at`. 184 adds one column-disjoint writer: the provider's tick writes `provider_node_id` or `provider_commit` once, through `bind_edge`. `bind_edge` is a compare-and-set that succeeds only on an `open`, unbound edge (D10). 183's State Management line saying there is no third writer is amended to match.
- **Provider's project store.** One `request` node per request run and its `sq_request` entry. The node is created `in_progress` and set to `done` when the run's entry resolves. Nothing else in the provider's store changes until the plan read creates the slice.
- **Run I/O directory.** `<supervisor_dir>/requests/<run_id>/`, beside `answering/`, derived from the run id by one function and not stored. It is made fresh with exclusive `mkdir` and left in place after the run as evidence.
- **Waits are stored**, as 183's edge waits are, with `wait_since`, because they come from git and `cf` reads that inspection may not make. A row is written only when its state or wait changes, and `wait_since` is set with it (183, D10).
- **Evaluation order** matches 183: requests are evaluated oldest first (`created_at`, then `request_id`), and a budget refusal stops the pass and leaves the rest as they are for a later tick. No fairness ordering.

## Technical Decisions

### D1 — A request is a row beside its edge; the edge holds the need
Status: decided

- `requests` holds `request_id`, `program_id`, `edge_id` (unique, references `edges`), the `asking_slice_label` (`<index> <name>`, which `need.md` names and the edge does not carry), `state`, a wait or failure with detail, and only the run fields binding and recovery read: `slice_set`, `launch_head`, `run_id`, `journal_entry_id`, `reply_index` and the timestamps.
- The need, the asking project, node and question block, and the provider live on the edge (183, D1). The request reads them from there and stores no second copy; "requests whose provider is this project" joins on `edges_by_provider`. The requests index comes from the member record and the target from the entry's parameters (D7); the I/O directory is derived from the run id. An already-met commit lives on the edge once bound, and in the failure detail for `head_moved`.
- `create_request(*, waiting_project, waiting_node_id, asking_slice_label, question_block_id, provider_project, need) -> Request` writes the unbound edge, through 183's `create_edge` checks, and the `pending` request in one `BEGIN IMMEDIATE` transaction. The edge's mode is `effective_mode` at creation, as for every edge. 185 is the caller. In 184 only tests call it.
- Rejected: storing the request as more edge columns. The request has its own lifecycle (pending, running, replied) that ends while the edge is still open. Folding it in would make every edge reader filter on request columns.

### D2 — Request states, waits and failures are closed vocabularies
Status: decided

| State | Meaning | Next |
| --- | --- | --- |
| `pending` | Created, not launched. May carry a wait | `running`, `failed`, `withdrawn` |
| `running` | Entry journaled. Slice set, head and run id recorded | `replied`, `met`, `failed`, `withdrawn` |
| `replied` | New-slice reply recorded, awaiting the binding plan read | `bound`, `failed`, `withdrawn` |
| `bound` | Edge bound to the new slice. Closed | — |
| `met` | Edge bound to the named commit. Closed | — |
| `failed` | Closed with a `RequestFailure` | — |
| `withdrawn` | The edge closed (superseded) before binding. Closed | — |

`RequestWait` applies to `pending` and `replied`, and to `running` only for `unreadable` when the already-met head read fails (D8). The first match wins:

- `unreadable`: the stage cannot evaluate the request. That covers a missing CF link or snapshot, no checkout at the requests index, or a failed git or `cf` read. The detail names which, with the command and stderr head for a read.
- `requests_unconfigured`: the provider's project config has no `requests` section. Fixed by config and a restart, so it is a wait.
- `checkout_in_use`: a run is in flight in the checkout, or another request to this provider is `running` or `replied` (D6). The detail names the holding node or the request ahead.
- `checkout_branch`: the checkout is detached or not on the target.
- `checkout_dirty`: the tree has changes. The detail gives the first paths and the count.
- `awaiting_plan_read`: `replied` with no plan read completed since.

`RequestFailure`:

- `run_failed`: the run did not complete. The detail is Squadron's failure kind and text.
- `run_lost`: recovery resolved the entry `not_applied` or `unknown`.
- `reply_missing`, `reply_malformed`: from `ReplyProblem`.
- `binding_failed`: no new slice at the reported index, or the index existed at launch.
- `head_moved`: an already-met run moved the target head (180, D3).
- `requests_initiative_full`, `requests_band_collision` (D4).
- `launch_failed`: making the I/O directory, writing `need.md` or spawning failed.

Each vocabulary is a `StrEnum` pinned to its SQL `CHECK`. Nothing retries a failed request. The asker's question block stays open for the PM, and the PM's resolution supersedes the edge (183, D9).

### D3 — A `request` node in the provider's store carries the `sq_request` entry
Status: decided

- Journal entries need a node (`command_journal.node_id` references `nodes`). The run acts for no existing slice, and on a first request the initiative it writes does not exist yet.
- So `begin_request_run` creates a node of a new kind, `NodeKind.REQUEST`, and journals the entry against it, in one transaction. The node has no parent, no CF link, the title `request <request_id> from <asking project>`, and a node id derived from the request id by one function (`request_node_id`). `nodes.kind` has no `CHECK`, so no project migration is needed for the kind.
- No existing reader mistakes it for work. `ready_slices` takes only slices. The orphan rule takes only linked nodes. `supervision_entries` drops `sq_request` entries, so the resolution classifier sees none on the node. A PM resolution of a block on a request node (only recovery's `unknown` escalation or the tenant's fault catch writes one) is acknowledged with no continuation, and a test pins this.
- Rejected: journaling against the requests initiative node, which is absent on the first request. Also rejected: a placeholder initiative node, which reconcile would orphan. Also rejected: journaling in the program store, which breaks 181's locality rule (no journal there) and recovery's per-project-store loop.

### D4 — The requests band: ten indices from the requests index
Status: decided

- `file-naming-conventions.md` gives an initiative ten indices from its base. The band is `requests_index` to `min(requests_index + 9, 799)`. The width and the ceiling are constants in `program/band.py`.
- `requests_band(nodes, requests_index)` reads a project's nodes (its own store, or another member's store read-only for 185) and returns:
  - `Open(next_index)`, where `next_index` is 180's index rule: the requests index when the initiative has no linked slices, else one more than the highest;
  - `Full`, when `next_index` would leave the band;
  - `Collision(index)`, when a linked initiative node other than the requests initiative has its index inside the band.
- The provider checks it before launching, from its own store. `Full` and `Collision` fail the request with `requests_initiative_full` or `requests_band_collision`. This is 181, D4's "collides with an existing planned initiative" check. 185 calls the same function to decline up front, so a full member is refused in the asker before a request exists.
- The function reads the store's view of the plan, which can lag the checkout by one plan read. Request runs to one provider are serialized (D6), so only a hand-added slice could be missed. In that case the agent's write lands one index higher, or outside the band, and binding catches it.

### D5 — The request run's checkout rule: 132's hold, with one exemption, plus clean on target
Status: decided

- **Which checkout:** `resolve_checkout` at the member's `requests_initiative` in the provider's latest observed snapshot, the same checkout 181 checks for readability.
- **Hold:** `dispatch/hold.py` gains `checkout_holds(entries, done) -> Mapping[Path, CheckoutHold]`. `CheckoutHold` has two sets: `in_flight`, the nodes with an unresolved `sq_run` **or `sq_request`** entry in the checkout, and `stopped`, the nodes 132's paused, failed or orphaned rule names. `checkout_holders` becomes the union of the two, so `DispatchPlanner` and `ContinuationPlanner` are unchanged. They now also see an in-flight request run as a holder, which keeps one pipeline per checkout.
- **Exemption:** a request run may launch when `in_flight` is empty, whatever `stopped` holds. A request run only adds a plan commit on the target (180, D5), so it cannot disturb a stopped run's work as long as the tree is clean and on the target.
- **Check:** before launch, `checkout_reads` (git status, then the target through `cf config get`) and the existing fresh-launch rule in `checkout_check.py`. That rule rejects a detached HEAD, a branch other than the target, and any changed, staged, unmerged or untracked path. The rule's `Block` becomes a request wait (`checkout_branch`, `checkout_dirty`), never a node block. A request path never blocks a provider node. `Ok`'s evidence is recorded on the entry as `dispatch_check`, and its `head` is the request's `launch_head`.
- A stopped node whose run already created its slice branch has the checkout off the target, so the request waits `checkout_branch`. That is the architecture's accepted cost until separate request checkouts exist.

### D6 — One request at a time per provider, oldest first
Status: decided

- The stage launches the oldest `pending` request (`created_at`, then `request_id`) only when no request to this provider is `running` or `replied`. The others wait `checkout_in_use`, naming the request ahead.
- All requests to a member run in the one checkout that owns its requests index, so they could not overlap anyway. The extra rule covers `replied`. The next run does not launch until the previous new slice has been bound. So the slice set each run records already contains every earlier request's slice, and the binding check (D9) cannot accept an index an earlier request wrote.
- Cost: a request can wait up to one plan read behind the previous one. That is short next to a slice-writing run.
- **No request timeout, by design.** A run that never finishes is bounded by its cost cap and Squadron's stall failure (180, D6). A plan read that never succeeds keeps the `replied` request, and every later request to that provider, waiting. Both cases are visible on the program blocked list and in `plan_read_failed`. The exit is the PM's resolution of the asker's block, which withdraws the request (D10).

### D7 — The launch: everything that can fail cleanly happens before the journal
Status: decided

In order, for the chosen request:

1. **Configured?** `RequestSettings` for the provider, or wait `requests_unconfigured`.
2. **Checkout and band.** D5's checkout, D4's band from the provider's store, and D5's hold. A failure becomes a wait or a failure, with nothing journaled.
3. **Edge still open?** If it was superseded, the request goes `withdrawn` and nothing launches (D10).
4. **Check.** D5's reads, under the tick budget. A budget refusal stops launching for this tick and leaves the request `pending`.
5. **Directory, input and journal.** Make `<supervisor_dir>/requests/<run_id>/` (`mint_run_id`) and call 180's `prepare_request_directory` with `RequestInput(asking project, asking slice label, requests index, need)`. Build the argv with `request_argv(...)`. An `OSError` fails the request `launch_failed` and removes the directory. Then `begin_request_run` writes the node and the entry in one provider-store transaction. Required parameter keys: `pipeline`, `params`, `run_id`, `checkout`, `request_id`, `requests_index`, `slice_set`, `target`, plus `dispatch_check` as evidence (its `head` is the launch head).
6. **Program store.** The request goes `running` with `slice_set` (the sorted CF indices of the linked slices under the requests initiative, empty when it does not exist), `launch_head`, `run_id` and `journal_entry_id`, all copied from the entry.
7. **Spawn.** `launch.spawn` from the checkout as working directory, with the existing launch logs, `run_id=` confirmation and launch grace. A spawn failure resolves the entry `failed`, sets the node `done`, and fails the request `launch_failed`, all in the same tick.

**Crash windows need no adoption branch.** The observe step (D8) runs before launch and walks unresolved `sq_request` entries. An entry whose request is still `pending` (a crash between 5 and 6) is recorded `running` from the entry's parameters there, so launch never sees that request as `pending` again. A run that was never spawned (a crash before 7) is left to recovery, which resolves the entry `not_applied` after the launch grace; the request then fails `run_lost` (D8). Relaunching is deferred (architecture). A run that was spawned is finished normally. No path launches a second run.

- **The argv** is built only in `request_argv(pipeline_path, requests_index, run_id, io_dir, max_cost_usd, model)`. Today it builds 180's provisional form: `sq run <path> <requests index> --run-id <id> --io-dir <dir> --max-cost <usd> -p model=<alias>`. When 180 finalizes the syntax, only this function and its test change.
- `params` journaled are the `-p` params (`model`). The cost cap is journaled as its own key, `max_cost_usd`, because it is not a pipeline param.

### D8 — Finishing a request run
Status: decided

The stage polls each unresolved `sq_request` entry with `RunObserver.poll_run`, under the budget and `--run-poll-interval`, as the answering stage polls `sq_answer`. First, an entry whose request is still `pending` is recorded `running` from its parameters (D7, crash windows). A run Squadron does not know about is not a finished run: the stage leaves the entry to recovery, which owns the launch grace and resolves it `not_applied`, and the request then fails `run_lost`. So a never-spawned run always ends `run_lost`, whatever the tick order. For a finished run, the program-store write comes first and the entry is resolved second. A crash in between is finished again on the next tick, because the request state tells the stage what is already recorded.

| Run outcome | Reply | Effect |
| --- | --- | --- |
| finished, not `completed` (failed, paused, orphaned) | not read (180, D7) | `failed` `run_failed`, with the failure kind and the 4 KiB tail |
| `completed` | `ReplyProblem` | `failed` `reply_missing` or `reply_malformed`, with the detail |
| `completed` | `NewSlice(index)` | `replied` with `reply_index`. The provider's link is marked due (D9) |
| `completed` | `AlreadyMet(commit)` | head check, then `met` or `failed` `head_moved` |

- **Head check.** One `git_read` `log -1 --format=%H <target>` in the checkout. If the result equals `launch_head`, the stage calls `bind_edge(ProvidingCommit(commit))` and the request goes `met`. Otherwise it fails `head_moved`, naming both heads. The commit stays on the target as an undriven plan entry the PM can see (180, D3). A failed read leaves the request `running` with wait `unreadable`, and it is retried next tick, since the entry is not yet resolved.
- **A `False` from `bind_edge`** means the edge closed (superseded) since the stage read it. The request goes `withdrawn` (D10), here and in D9's bind alike.
- **The entry's result** is `{run_id, run_outcome, reply_kind, request_state}`. It carries `run_id`, so the run is Amoeba's for pruning (process contract, ownership guarantee). The request node goes `done` in the same transaction.
- **A paused run** is not resumed. The pipeline has no human step, so a pause means Squadron stopped it. It fails `run_failed` with the pause's reason.
- **Recovery.** `sq_request` registers the by-id `sq` observer, as `sq_answer` does, with no legacy matcher. An existing run is left in flight for the stage. An entry recovery resolves `not_applied` or `unknown` fails the request `run_lost` the next time the stage sees it. Nothing relaunches it (architecture, deferred).

### D9 — Binding waits for a plan read that started after the reply
Status: decided

- On a `NewSlice` reply the stage calls `PlanStage.mark_due(project, link)`. The provider's link is then read on the next tick rather than at `--plan-read-interval`. A request run's commit does not necessarily change the CF snapshot.
- `PlanReadSchedule` records the start time of each complete read. `read_completed_since(project, link, at)` is true when a read that started at or after `at` completed. After a restart the schedule is empty, and the first tick reads every link, so the first complete read satisfies the check.
- `bind.decide_binding(request, tree, fresh)` is pure:
  - Not fresh: wait `awaiting_plan_read`.
  - Fresh, and the tree has a linked slice at `reply_index` under the initiative node at `requests_index`, `reply_index` is not in `slice_set`, and it is inside the band: bind `ProvidingSlice(node_id)`, and the request goes `bound`.
  - Otherwise: fail `binding_failed`, naming which part failed (absent, already there at launch, or outside the band).
- **The plan read failed.** A read that keeps failing (for example a plan file CF cannot parse, 180's named risk) never counts as complete. The request waits `awaiting_plan_read` beside the project's `plan_read_failed` escalation. The PM sees both.
- The plan read that creates the node, and the bind, happen in the same tick: plan reads run before the request stage. So the edge names the slice before anything can launch it, which keeps 183, D5's contract that an edge exists before its providing slice completes.

### D10 — `bind_edge` is a compare-and-set; supersession withdraws
Status: decided

- `bind_edge(request_id, target, at) -> bool` finds the request's edge and sets `provider_node_id` or `provider_commit` only where the edge is `open` and both are null, in the same transaction as the request's move to `bound` or `met`. It returns `False` and writes nothing otherwise. Both callers (D8's already-met finish, D9's bind) then withdraw the request with `withdraw_request`; there is no other `False` path, because only supersession closes an open edge before it is bound.
- **Supersession.** A PM resolution on the asker's question block supersedes the edge in the asker's tick (183, D9). The request stage sees that the edge is closed:
  - `pending` goes `withdrawn` and does not launch.
  - `running` finishes the run (the entry must resolve) and then goes `withdrawn` with the reply recorded.
  - `replied` goes `withdrawn`.
- A slice already written stays in the provider's plan as ordinary planned work. It is not membership-driven, because no open edge names it. That is the architecture's rule.
- Both ticks run in one process, one at a time, and every write is a `BEGIN IMMEDIATE` transaction. So the compare-and-set covers the one interleaving that matters: the asker supersedes between the provider's read and its bind.

### D11 — 183's observation of an unbound edge
Status: decided

- `EdgeWait` gains two waits, checked first, before 183's table:
  - `request_open`: the edge is unbound and its request is `pending`, `running` or `replied`. The detail is the request's state and wait.
  - `request_failed`: the edge is unbound and its request is `failed`. The detail is the failure and its detail.
- The asker's tick reads the request row from the program store. That is no git, no `cf` and no member store open, so an unbound edge costs one program-store read.
- An unbound edge is `open`, so the asking slice is in `waiting` and is not ready, by 183, D2 unchanged.
- Migration 003 rebuilds `edges`, because SQLite cannot alter a `CHECK`. The target check becomes "not both set", and the wait `CHECK` gains the two values. The rebuild is create, copy, drop and rename in the migration's one transaction. A migration test runs it on a store holding 183's edges.

### D12 — Readiness: no implicit predecessor, and membership drive, through one value
Status: decided

- 183's `waiting` argument becomes `ProgramReadiness(waiting, membership_driven, standalone_initiatives)`, defined in `runner/lifecycle/readiness.py` so lifecycle and intent own it and never import `runner/program`. These are three frozen node-id sets, and `ProgramReadiness.EMPTY` is used for a project in no program. It is still a required argument with no default, for 183, D2's reason.
  - `waiting`: 183's set, unchanged.
  - `standalone_initiatives`: the node id of the initiative at the member's `requests_initiative`, when the node exists.
  - `membership_driven`: `ProgramView.providing`, unchanged. Every edge is created by a request, so only request slices are in it.
- `predecessors.slice_predecessor` returns `None` for a slice whose initiative is in `standalone_initiatives`. Request slices never wait on each other, while the edge is open and after it closes (architecture: "its slices have no implicit predecessor").
- `governance.governing` makes a slice in `membership_driven` driven whatever its drive rows say. `held` is still any hold row on its path, so a PM hold stops it.

### D13 — Request priority in the dispatch order
Status: decided

- `SortKey` becomes `(priority, initiative index, slice index)`, where `priority` is `0` for a membership-driven slice and `1` otherwise. It is built in `dispatch/build_view.py` from `ProgramReadiness.membership_driven`. `DispatchPlanner` is unchanged: it already takes the lowest key per checkout.
- Request runs need no priority value. They launch in the request stage, before the view exists (Data Flow).
- **What priority does not do: readiness independence, not runtime independence.** A request slice designs and builds under the normal checkout rule (architecture: "The request slice it writes designs and builds under the normal checkout rule"). A stopped first request slice holds its checkout, so a second request slice in the same checkout is ready but waits for that checkout, as any slice does. A predecessor never holds it back (D12), and the wait shows on the program blocked list through its edge (`provider_not_done`).
- **Deviation from the slice plan.** The plan's criterion "a second request slice is not held up by a stopped first one" is met for readiness only. The plan entry is amended to say so. The cost is the one the architecture accepts for held checkouts: requests wait while the provider's checkout is held, until separate request checkouts exist (slice plan Future Work 1).

### D14 — Configuration and start-up
Status: decided

`projects.yaml` gains an optional `requests` section per project. Its presence lets the project serve requests. Both keys are required, with no defaults:

```yaml
projects:
  trading-data:
    pipeline: p456
    requests:
      model: <Squadron model alias whose provider gives file and shell tools>
      max_cost_usd: <cap for one request run>
```

- `model`: stripped, non-blank, no `,`. `max_cost_usd`: a number above zero. `requests: {}`, a null section, a missing key or an unknown key fails the load, naming the key path (`projects.<id>.requests.model`), as the `answerer` section does.
- **Start-up:** when any project has a `requests` section, `probe_slice_writing_pipeline` runs once. A failure exits `STARTUP_FAILED`, naming the command. With no section the probe does not run, so an `sq` without 180's capabilities never stops an install that serves no requests (180, D9).
- A program member with no section is not an error. Its requests wait `requests_unconfigured` on the program blocked list.

### D15 — `register_program` and `program-blocked`
Status: decided

- `ProgramStore.apply_submission` gains the `member_referenced` check over requests that 181, D3 reserved: a `register_program` that would drop a member any request references, as provider or asker through its edge, in any state, is rejected `member_referenced` in the same submission transaction and writes nothing else. 183 adds the same check over edges; 184 adds only the requests half. This also covers a request still running after its edge was superseded. No new rejection code.
- `program-blocked` gains one row per request in `pending`, `running`, `replied` or `failed` whose edge is still open:
  - `project_id` is the provider, `node_id` the request node (empty before launch), and `title` `request <id> from <asking project> slice <label>`.
  - `blocked_on` is `request`, and `blocked_state_id` is empty.
  - `reason` is `"<state>: <wait or failure>: <detail> (since <wait_since>)"`, as 183's edge rows.
- The asking slice's own row is 183's edge row, now with `request_open` or `request_failed`. So a stuck request reads as two linked rows: the provider's request, and the asker waiting on it.
- A failed request whose edge closed (the PM resolved the asker) is no longer listed. The PM has acted.

### Technology Choices

No new library. The existing store machinery and migration runner, the launch and observation code, `git_read` (`status`, `log`) and `checkout_reads`, plus 180's pipeline modules.

### Patterns and Conventions

- `sq_request` follows `sq_answer` throughout. It has its own kind, required keys, observer registration, stage and directory. It is excluded from `supervision_entries` and never passed to `record_finished`.
- `bind.py` and `program/band.py` are pure and in the purity check. All I/O is in `launch.py`, `finish.py` and the stage.
- `program/band.py` lives in `amoeba.program`, which imports only `amoeba.store` and `amoeba.upstream` (181), so 185's answering stage and inspection can both use it.
- Request titles and reason formats are constants beside the listing, and tests import them.

## Implementation Details

### API Contracts

```python
# store/program_models.py
class RequestState(StrEnum): PENDING; RUNNING; REPLIED; BOUND; MET; FAILED; WITHDRAWN
class RequestWait(StrEnum): ...      # D2
class RequestFailure(StrEnum): ...   # D2
EdgeWait += REQUEST_OPEN, REQUEST_FAILED   # D11

# ProgramStore (store/program_requests.py)
create_request(*, waiting_project, waiting_node_id, asking_slice_label: str,
               question_block_id: str, provider_project, need: str) -> Request          # request + unbound edge, one txn
requests_providing(project_id, states: AbstractSet[RequestState]) -> list[Request]
request_for_edge(edge_id) -> Request | None
record_request_wait(request_id, wait: RequestWait, detail: str, at) -> bool   # False: unchanged
mark_running(request_id, *, slice_set, launch_head, run_id, journal_entry_id, at)
record_reply(request_id, reply: NewSlice, at)                   # -> replied
bind_edge(request_id, target: EdgeTarget, at) -> bool           # CAS; -> bound | met
fail_request(request_id, failure: RequestFailure, detail: str, at)
withdraw_request(request_id, at)

# Store (store/request_run.py)
request_node_id(request_id: str) -> str
begin_request_run(*, project_id, request_id, title, parameters) -> JournalEntry  # node + entry, one txn
finish_request_run(entry_id, result: Mapping[str, object]) -> None             # entry resolved + node done

# program/band.py
type BandState = Open | Full | Collision
def requests_band(nodes: Sequence[Node], requests_index: int) -> BandState

# runner/request_run/launch.py
def request_argv(pipeline: Path, requests_index: int, run_id: str, io_dir: Path,
                 max_cost_usd: float, model: str) -> tuple[str, ...]

# runner/lifecycle/readiness.py  (imports nothing from runner/program or the program store)
@dataclass(frozen=True)
class ProgramReadiness:
    waiting: frozenset[str]
    membership_driven: frozenset[str]
    standalone_initiatives: frozenset[str]
    EMPTY: ClassVar[ProgramReadiness]

# runner/program/stage.py
# ProgramView gains: readiness: ProgramReadiness   (filled here)

# runner/project_config.py
@dataclass(frozen=True)
class RequestSettings: model: str; max_cost_usd: float
# ProjectSettings gains: requests: RequestSettings | None
```

**Inbox contract:** no new rejection code and no new body. A request has no inbox path: 185 creates it in the asker's tick.

### Database / Storage Schema

`store/program_schema/003_requests.sql` (program schema version 3):

```sql
-- edges rebuilt: unbound allowed, two waits added (D11); data copied unchanged
CREATE TABLE edges_new (... as 002 ...,
  wait TEXT CHECK (wait IN (<183's waits>, 'request_open', 'request_failed')),
  CHECK (NOT (provider_node_id IS NOT NULL AND provider_commit IS NOT NULL)));
INSERT INTO edges_new SELECT * FROM edges; DROP TABLE edges; ALTER TABLE edges_new RENAME TO edges;
-- 183's two indexes recreated

CREATE TABLE requests (
  request_id TEXT PRIMARY KEY, program_id TEXT NOT NULL REFERENCES programs(program_id),
  edge_id TEXT NOT NULL UNIQUE REFERENCES edges(edge_id),
  asking_slice_label TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('pending','running','replied','bound','met','failed','withdrawn')),
  wait TEXT, wait_detail TEXT, wait_since TEXT,            -- CHECKed against RequestWait; written only on change
  failure TEXT, failure_detail TEXT,                       -- CHECKed against RequestFailure
  slice_set TEXT,                                          -- JSON array of CF indices, set at launch
  launch_head TEXT, run_id TEXT, journal_entry_id TEXT,
  reply_index INTEGER, replied_at TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, closed_at TEXT,
  CHECK ((state = 'failed') = (failure IS NOT NULL)));
CREATE INDEX requests_by_state ON requests (state, created_at);
-- provider lookups join edges on edges_by_provider
```

Project store: no migration. `NodeKind.REQUEST` is a new value in an unchecked column, and `sq_request` is a new value of the journal's unchecked `kind`. The locality rule's allowed program-store set gains `requests`, and the proof's table list follows.

## Integration Points

### Provides to Other Slices

- **185:** `create_request` (the only way a request and its edge come to exist), `requests_band` to decline a full or colliding member before requesting, `RequestSettings` presence to decline a member that serves no requests (it reads the same loaded project config), and the request rows the answerer's passages show.
- **186:** the request rows, `sq_request` entries, the I/O directories and the `program-blocked` request rows as the evidence of each step against real runs.
- **Process contract:** the request stage and its place in the tick, `sq_request` and its recovery, the request-run exemption, membership drive, request priority, no implicit predecessor in the requests initiative, and the `requests` config section.

### Consumes from Other Slices

- **180:** the pipeline, input, reply and probe. If 180's finalized argv differs, `request_argv` changes. If Squadron never ships D8, the probe fails at start for any install with a `requests` section, and no real request run happens. That is an explicit stop, never a degraded run.
- **181:** each member's `requests_initiative` and the program stage seam. An unreadable provider is a request wait, never an exit. A program store failure exits as a store failure (181, D7).
- **183:** edges, waits, supervision and readiness. 184 changes 183's code only as D10, D11 and D12 say: the bind writer, two waits, an unbound edge, and `waiting` wrapped in `ProgramReadiness`.
- **120 and 132:** the hold, dispatch order, governance, predecessors, launch, observation, recovery and plan stage. Each change goes in 120's contract documents.

## Success Criteria

### Functional Requirements

- A request written with `create_request` produces exactly one request run in the provider, launched in the tick it becomes eligible, before the provider's next planned slice in that checkout. A test has a planned slice and a pending request both eligible in one tick: the request run launches and the planned slice does not.
- A request run never overlaps a run in flight in the same checkout. A second request waits `checkout_in_use`, naming the first, while the first is `running` or `replied`.
- A request run launches in a checkout held only by a paused, failed or orphaned node when the tree is clean and on the target. It waits `checkout_branch` or `checkout_dirty` otherwise, and `checkout_in_use` while any run is in flight there. No provider node is blocked by a request wait.
- A new-slice reply binds the edge only after a plan read that started after the reply shows a new slice at that index. A reply naming an index that was in the recorded set, or one absent from the plan, fails `binding_failed`.
- The bound slice has no implicit predecessor, is driven by membership while its edge is open, sorts ahead of planned slices in its checkout, and is launched by the provider's configured pipeline. A PM hold on its path stops it. A second request slice is ready while a first one is stopped, and launches when the checkout is free.
- An already-met reply binds the edge to the named commit when the target head is unchanged since launch, and the asker is released only when 183's observation passes. A run that moved the head fails `head_moved`.
- A failed run, a missing or malformed reply, a full band and a band collision each fail the request with their reason. The request row and the asker's edge row (`request_failed`) both show on `program-blocked`.
- A PM resolution on the asker's question block withdraws a pending request without launching. A running request finishes and is withdrawn, and the slice it wrote is not membership-driven.
- A restart with a request run in flight adopts it through recovery and the stage, and never launches a second. A test kills the launch between the provider-store journal and the program-store `running` write, and again between that write and the spawn. In both cases the next tick records the request `running` from the entry, recovery resolves it `not_applied`, and the request fails `run_lost` with no second launch.
- A missing `requests` section leaves the provider's requests waiting `requests_unconfigured`. A section with a missing or invalid key fails the load naming the key path. The probe runs at start only when some project has the section.
- `register_program` that would drop a member any request references, in any state, is rejected `member_referenced` and writes nothing else; a test drops a member referenced only by a closed request and by a request still running after supersession.
- A run Squadron does not know about, inside or past the launch grace, ends `run_lost` through recovery and never `run_failed`; a test runs the stage before and after recovery in both orders.
- A bind or already-met finish that loses the race to supersession (`bind_edge` returns `False`) leaves the request `withdrawn`.
- A project in no program, and a member with no requests, tick with the same writes, commands and journal as after 183.

### Technical Requirements

- `bind.py` and `program/band.py` pass the purity check. Every new vocabulary is pinned to its `CHECK`. The locality proof covers `requests`. An import-boundary test fails if `runner/lifecycle` or `intent/` imports `runner/program` or the program store, directly or transitively.
- Migration 003 is tested on a program store holding 183's edges in every state, and preserves them.
- The stage is tested with a stub `sq` that writes `reply.json` into the I/O directory and exits per scenario, and with `tests/runner/git_repo.py` repos for the checkout and head checks. No live `sq` or model.
- `request_argv` has one test pinning the provisional form, marked to change with 180's finalization.
- Every git read goes through `git_read` (`status`, `log`). A test counts calls: none for a request blocked by a store-only reason, two (`git status`, `cf config get`) before a launch, and one (`log`) to finish an already-met run.
- Format, lint and typecheck (`ruff`, `pyright` strict) pass, with the full suite.
- Docs: `docs/store-contract.md` (requests, the edge rebuild, the `request` node kind, `sq_request` and its keys, the bind writer, locality), `docs/inbox-contract.md` (`member_referenced` also checks requests), `docs/process-contract.md` (the request stage, the checkout rule and exemption, readiness and dispatch changes, the `requests` section, the probe wiring, recovery), and `CHANGELOG.md`.

### Integration Requirements

- 185 can create a request with `create_request`, decline up front with `requests_band` and the presence of `RequestSettings`, and rely on 184 and 183 for everything after.
- 186 can run a real request end to end once a Squadron release has 180's D8, changing only `request_argv` if 180's finalized syntax differs.

### Verification Walkthrough

Draft; refined after implementation. Nothing in 184 creates a request outside tests, and real request runs need a Squadron release with 180's D8. So the proof is one scripted two-project scenario with a stub `sq`. Seeing it against real runs is 186.

1. **Two-project scenario.**
   ```bash
   AMOEBA_KEEP_SCENARIO_DIR=1 uv run pytest tests/runner/request_run/test_request_scenario.py -v -s
   ```
   This uses 183's kept-directory variable. The setup is two scratch member stores, a scratch provider repo and a stub `sq` whose "agent" appends a slice entry and commits. Expected:
   - The provider has a paused planned slice on the target, clean. The request run launches anyway (exemption). The paused slice is not resumed while the run is in flight.
   - The reply is `new_slice`. The next tick's plan read (stubbed `cf`) shows the slice, and the edge is bound.
   - The following tick launches the request slice's pipeline ahead of a ready planned slice in the same checkout.
   - The asker's edge row moves from `request_open` to `provider_not_done`.
   - Variants: `already_met` with an unchanged head (`met`, edge on the commit), and with a moved head (`head_moved`). A malformed reply. A full band.

   The test prints its kept supervisor directory.

2. **Inspection on the kept directory.**
   ```bash
   AMOEBA_STORE_DIR=<printed dir> amoeba inspect program-blocked
   ```
   Expected: `request` rows with state, wait or failure, and `wait_since`, beside the asker's `edge` rows.

## Risk Assessment

### Technical Risks

- **It changes 132's checkout hold and dispatch order and 124's governance.** A mistake launches a request run over live work, or drives the wrong slice.
- **It acts on a model's reply about another project's repo.** A wrong index could bind an unrelated slice.
- **180's launch shape is not final**, and real runs wait on Squadron.

### Mitigation Strategies

- The exemption applies only when no run is in flight and the tree is clean and on the target. The check is the existing fresh-launch rule, unchanged. Membership drive applies only to slices an open edge names, and only requests create edges. A no-program regression test pins identical ticks.
- Binding requires a new slice at the reported index, absent at launch, inside the band, seen by a plan read that started after the reply. Requests to one provider are serialized, so no other request can supply that slice. Nothing a model says satisfies an edge (183).
- The argv lives in one function, the probe guards start-up, and every real-run step belongs to 186.

## Implementation Notes

### Development Approach

1. Program schema 003 (edge rebuild and `requests`), vocabularies, `program_requests` with `create_request` and `bind_edge`, and the `member_referenced` check over requests in `apply_submission`. Store, migration and rejection tests.
2. `NodeKind.REQUEST`, `CommandKind.SQ_REQUEST` with its keys and observer registration, `supervision_entries`, and `begin_request_run` and `finish_request_run`. Store and recovery tests.
3. `program/band.py`. `checkout_holds` in `hold.py`. `ProgramReadiness` through predecessors, governance, `build_view` and the sort key. Lifecycle, intent and dispatch tests, plus the no-program regression test.
4. `RequestSettings` and probe wiring. Config and start-up tests.
5. `PlanStage.mark_due` and `read_completed_since`. `request_run/launch.py`, `finish.py`, `bind.py` and `stage.py`, and the stage's place in the tick. Stub-`sq` tests and crash points.
6. 183's observation of unbound edges (D11) and the `program-blocked` request rows.
7. The two-project scenario test, the locality proof, contract docs and CHANGELOG.

Relative effort: 4.

### Special Considerations

- **`tick.py` budget.** The stage is one call. If adding it pushes `tick.py` past its budget, `_launch_context` and its request counterpart move to a sibling module in the same task (181, D7 names the same extraction).
- **Cost per tick.** A member with no requests: one program-store read. A pending request: store reads, then two subprocess calls (git status and `cf config get`) only when its checkout has no run in flight. All are under the tick budget, and a refusal stops launching for the tick.
- **The need is data.** It reaches the provider only through `need.md`, which 180's instructions mark as data, and it never selects code paths.
- **No secrets.** Request rows and journal parameters hold ids, indices, commits, paths, a model alias and a cost cap.
