---
docType: reference
project: amoeba
slice: contract-proof-and-hardening
dateCreated: 20261020
dateUpdated: 20261030
status: complete
---

# The Amoeba Substrate Guide

Start here if you are designing initiative 120 (Runner), 140 (Judge), 160
(Translator), or the notification bridge. This guide says which surfaces each
needs and where each is specified. It restates none of them: the contracts are
the authority, and the proof in `tests/contract/` shows each one working.

You should not need to read anything under `src/`. If you do, the gap is the
contract's, and slice 110 wants to hear about it (see "Known limits").

## What the proof is

[`tests/contract/`](../tests/contract/) drives the substrate the way a later
initiative will: real processes, real signals, a real inbox directory, no mocks.
Its only stand-in is Squadron's side effect (a run file and a review file), which
is written in the formats the observers and detection already read. Every
import in it is checked to be public (see "Public import roots"), so a thing it
does is a thing you can do.

The sequence is in [`scenario.py`](../tests/contract/scenario.py), as data. In
prose, across two projects, `alpha` and `beta`:

1. **The PM creates both projects and watches their review directories.**
   Projects are created at run time, through the inbox.
2. **The Runner builds a tree** (initiative, slice, gate) in each.
3. **The Runner launches a review.** It journals the command first, does the
   work, then reports the verdict, the ledger row, and the resolved entry in one
   transaction (`record_runner_report`). Detection never ingests the file again.
4. **A crash after the work, before the report.** Recovery finds exactly one
   matching run and adopts it. Detection then ingests the review under the id
   the Runner would have used: one verdict for the round.
5. **A crash right after the journal entry.** Recovery finds no run, marks the
   entry `unknown`, blocks the node on a human, and posts one escalation.
6. **The PM replies.** The node becomes runnable.
7. **A review the PM launched** appears in the watched directory. Detection
   ingests it, and `finding_changes` compares it with step 4's round.
8. **The Judge submits two samples** of one invocation, through the inbox.
9. **The Runner checkpoints** a paused run on each project's gate.
10. **The process is stopped**, the PM submits a reply while it is down, and it
    is started again. The reply is applied on start.
11. **The Runner finishes** alpha. Beta's checkpoint stays open.
12. **The PM prunes paused runs.** Only alpha's checkpoint run is offered.

Two oracles check the end: every project's store against a declared end state
(a missing or extra row fails), and the feed, replayed from `seq` 0, against the
nodes' final statuses. The network subset
([`test_network_subset.py`](../tests/contract/test_network_subset.py)) repeats
the delivery path over HTTP with a `kill -9` of `amoeba serve` and of the
resident process.

## Which surfaces each initiative uses

| Initiative | What it does with the substrate | Contract sections | Scenario steps |
| --- | --- | --- | --- |
| **120 Runner** | Hosts a tenant beside the shipped ones; journals each Squadron command before issuing it; reports a review it launched; checkpoints and blocks; consumes `intent` messages; follows the feed. **The issuer of an `sq_run` must put `run_id` in both the entry's `parameters` (journal_issue refuses an `sq_run` without it, and recovery finds the run by it) and its `result`**, or none of its runs is ever pruned. A resume whose run is missing is a failed command (the entry resolves with that outcome, the node blocks on a human, the run is never relaunched). **Since slice 122 recovery leaves an id-bearing `sq_run` entry whose run exists unresolved (`InFlight`), and the Runner finishes it by polling the run id;** the `RunnerTenant` (`amoeba.runner`) launches detached, confirms by the `run_id=<id>` line, and observes by id under a tick deadline (see [The Runner tenant](process-contract.md#the-runner-tenant)). **Since slice 123 it projects each linked CF project's plan into the node tree** (initiative and slice nodes linked by `CFReference.index`, kept in step by reconcile on `--plan-read-interval`; see [The plan read](process-contract.md#the-plan-read), [Lifecycle nodes and the CF index](store-contract.md#lifecycle-nodes-and-the-cf-index), [Plan reads](context-forge-contract.md#plan-reads-slice-123)). **Since slice 132 it is a supervisor over each project's Squadron pipeline** (it replaces slices 125 to 128's step dispatch, routing, gate reads and merge policy): a driven slice gets one `sq run <pipeline> <index>` of the pipeline the project config names (`--project-config`; no default pipeline), in the slice's checkout after a git-only check (clean tree, on the target; a resume on the target or the slice's branch); the slice is the unit of work, the Runner writes no CF pointer and reads no CF gate, and slices of an initiative run in index order. A finished run is classified by a fixed outcome map: `completed` marks the slice `done` in the same transaction that resolves the entry (`record_runner_report(complete_node_id=...)`); `orphaned`, `provider_error`, `stall` and a `usage_limit` pause with `resets_at` are resumed with `sq run --resume`, up to `--auto-resume-limit` (default 3) consecutive times at one step, then the slice blocks `auto_resume_exhausted`; an `agent_question` pause blocks the slice on a human with the question in the escalation payload (`{run_id, reason, step, question}`) for slice 140 to answer; anything else blocks with its reason. The PM answers a block with a `resolution` of `resume` (optional verbatim instructions) or `stop`; the Runner acknowledges each `applied` or `rejected` (`runner_outcome`, `runner_code`; migration `012`). Intents (`drive`, `exclude`, `pause`, `resume`, `clear`) carry no `until`. `amoeba inspect blocked` lists every project's blocked nodes with their reason. The routing-decision, table-version and attempt-count tables, `awaits_routing` and `drive_until_step` stay in 100's contract, unwritten by the Runner (see [Dispatch and ingestion](process-contract.md#dispatch-and-ingestion), [The outcome map](process-contract.md#the-outcome-map), [Automatic resume](process-contract.md#automatic-resume), [Resolutions and resumption](process-contract.md#resolutions-and-resumption), [The project config](process-contract.md#the-project-config), [Git and the pre-dispatch check](process-contract.md#git-and-the-pre-dispatch-check), [What the Runner does with Context Forge](context-forge-contract.md#what-the-runner-does-with-context-forge-slices-125-128-132), [Unrouted outcomes](store-contract.md#unrouted-outcomes)). | [Hosting tenants](process-contract.md#hosting-tenants), [The tenant obligation](process-contract.md#the-tenant-obligation), [Recovery](process-contract.md#recovery), [The ownership guarantee](process-contract.md#the-two-shipped-observers), [Pruning paused runs](process-contract.md#pruning-paused-runs), [The command journal](store-contract.md#the-command-journal), [Reviews found on disk](evidence-contract.md#reviews-found-on-disk), [Requirements on initiative 120](evidence-contract.md#requirements-on-initiative-120-d5) | [2](../tests/contract/scenario.py), [3](../tests/contract/scenario.py), [4](../tests/contract/scenario.py), [5](../tests/contract/scenario.py), [9](../tests/contract/scenario.py), [11](../tests/contract/scenario.py), [12](../tests/contract/scenario.py) |
| **140 Judge** | Submits samples of one invocation as `verdict` submissions; records checks; reads the calibration report. | [Judge samples](evidence-contract.md#judge-samples), [Calibration](evidence-contract.md#calibration), [Checks](evidence-contract.md#checks), [Submitting](inbox-contract.md#submitting) | [8](../tests/contract/scenario.py), and [the network subset](../tests/contract/test_network_subset.py) for the remote path |
| **160 Translator** | Turns intent into `intent` submissions; reads escalations and replies with `resolution`; works with the process stopped. | [Submitting](inbox-contract.md#submitting), [Reading messages](inbox-contract.md#reading-messages), [Learning the outcome](inbox-contract.md#learning-the-outcome), [Delivery and replay semantics](inbox-contract.md#delivery-and-replay-semantics) | [5](../tests/contract/scenario.py), [6](../tests/contract/scenario.py), [10](../tests/contract/scenario.py) |
| **Notification bridge** | Follows a project's feed from outside the process, over HTTP or locally, and survives either process dying. | [The feed endpoint](network-contract.md#get-v1projectsproject_idfeed), [Delivery guarantees](network-contract.md#delivery-guarantees), ["Current state, then follow"](network-contract.md#current-state-then-follow), [`follow()`](feed-contract.md#follow) | [the network subset](../tests/contract/test_network_subset.py), and every step's expected changes in [`scenario.py`](../tests/contract/scenario.py) |

## Four things a Runner author does

- **Host a tenant.** Implement `Tenant` and compose it as
  `(*standard_tenants(settings, supervisor_dir), runner)` in
  `ResidentProcess`. [Hosting tenants](process-contract.md#hosting-tenants);
  the proof's tenant is `runner_tenant.py`, built in
  [`bootstrap.py`](../tests/contract/bootstrap.py).
- **Journal and report a review.** `journal_issue` before the side effect, then
  `record_runner_report` after it. The run is journaled on the step node, the work
  item; the verdict is recorded on the slice node the review is of, with
  `journal_entry_id=None`.
  [The command journal](store-contract.md#the-command-journal) and
  [Requirements on initiative 120](evidence-contract.md#requirements-on-initiative-120-d5);
  scenario steps [3](../tests/contract/scenario.py) to
  [5](../tests/contract/scenario.py).
- **Block and resolve.** `block` a node on a checkpoint or a human; the reply
  arrives as a `resolution` submission.
  [Blocked-state writes](store-contract.md#blocked-state-writes);
  scenario steps [5](../tests/contract/scenario.py),
  [6](../tests/contract/scenario.py), [9](../tests/contract/scenario.py), and
  [10](../tests/contract/scenario.py).
- **Follow the feed.** `follow()` locally, or the SSE endpoint remotely, from a
  saved cursor. [`follow()`](feed-contract.md#follow);
  [the feed endpoint](network-contract.md#get-v1projectsproject_idfeed);
  every step in [`scenario.py`](../tests/contract/scenario.py) lists the changes
  it must produce.

## Public import roots

A consumer imports from these seven packages and nothing deeper. The proof's
imports are checked against each package's `__all__`
([`public_api.py`](../tests/contract/public_api.py)), so the list is enforced,
not just stated.

`amoeba.store`, `amoeba.inbox`, `amoeba.feed`, `amoeba.process`,
`amoeba.upstream.squadron`, `amoeba.upstream.context_forge`, `amoeba.inspection`.

The CLI and HTTP are the other public surfaces, reached by subprocess and by
HTTP.

## Store locality

One store file per project, in one supervisor directory. The model is documented
in [Store locality](store-contract.md#store-locality); the proof checks it end to
end: the directory holds exactly one store file per project, and no project's
rows, feed, or detections appear in another's.

## The intent body is the proof's own

The proof drives its stand-in Runner with `intent` messages whose body is a step
name and an optional crash point. `intent` is the Translator-to-Runner channel,
and **that body format is only how the proof steers a stand-in; it is not a
contract.** Do not read it as one. What an intent body carries is initiative
120's and 160's to define.

## Known limits

Each limit is stated where it belongs; none is restated here.

- Process: [Future work](process-contract.md#future-work).
- Store: [Retention](store-contract.md#retention) (per section) and
  [Future work](store-contract.md#future-work).
- Evidence: [Future work](evidence-contract.md#future-work).
- Inbox: [Not guaranteed](inbox-contract.md#not-guaranteed) and
  [Future work](inbox-contract.md#future-work).
- What slice 110 found and changed, including every gap and how it was resolved:
  [the Slice 110 entry in the changelog](../CHANGELOG.md#unreleased).
