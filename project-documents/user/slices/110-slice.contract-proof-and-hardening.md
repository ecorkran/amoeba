---
docType: slice-design
slice: contract-proof-and-hardening
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108, 109]
interfaces: []
dateCreated: 20260928
dateUpdated: 20260928
status: not_started
---

# Slice Design: contract-proof-and-hardening

## Overview

Slices 101–109 each proved their own piece. Nobody has yet driven the whole substrate the way its real consumer will: a Runner living inside the resident process, a Judge and a human writing from outside, a PM running reviews by hand, a subscriber watching, and the process getting killed partway through. This slice does that, using only the documented contract, and fixes what the attempt exposes.

Four deliverables:

1. **The contract proof.** A scripted lifecycle sequence driven by a stand-in Runner tenant plus real CLI subprocesses, with `kill -9` injected at named points. The final state must come out right every time. A guard test makes "only the documented contract" a mechanical check.
2. **Hardening found by the proof.** Reading the contracts for this design already turned up five gaps (see [Contract gaps found at design](#contract-gaps-found-at-design)). Each is fixed here or assigned to the slice that owns it.
3. **A pruning policy for paused Squadron runs.** Squadron never prunes a paused run. Amoeba decides which of *its own* paused runs are dead and reports them. It deletes nothing: Squadron's files stay Squadron's (D7).
4. **A contract index for initiative authors.** One entry document that tells a 120, 140, or 160 designer which contract answers which question, and lists every obligation the substrate puts on them in one place.

## Value

Developer value. After this slice, initiative 120 designs against a contract that has been demonstrated to work for a Runner, not one assumed to. Specifically:

- The Runner has a documented, exported way to be hosted in the resident process. Today there is none: `amoeba.process` exports nothing and `amoeba start` hard-codes its tenants.
- "Any part can restart and rebuild its view from the store" is shown, not claimed: the stand-in Runner keeps no progress in memory and finishes the sequence after every kill.
- Obligations scattered across five contract documents (journal before launch, non-TTY stdin for `sq`, the attribution rule, the one-transaction report-back, "don't cache `project_ids`", "save the cursor after acting") are listed once, with links.
- The paused Squadron runs Amoeba abandoned are named, with their paths and the reason each is dead, so they can be removed with confidence instead of guessed at.

## Technical Scope

**Included**

- `tests/contract/`: the stand-in Runner tenant (`ProofRunner`), a fake Squadron that writes run files and review artifacts, the proof host bootstrap, the lifecycle snapshot and its comparison, and the proof tests.
- A guard test that the proof imports only public exports and touches no private names or SQLite directly.
- Pinned export sets for `amoeba.inbox`, `amoeba.feed`, `amoeba.process`, and `amoeba.upstream.squadron`, alongside the existing one for `amoeba.store`.
- The public hosting seam in `amoeba.process` (D3).
- Store-locality hardening: relative directory variables refused, project ids restricted to a portable form (D5).
- `done` enforced as terminal, as the store contract already says it is (D6).
- `amoeba prune sq-runs`, a read-only report (D7).
- The restart matrix in the load tier: a kill at every step boundary.
- `docs/README.md` (the contract index); updates to `store-contract.md`, `process-contract.md`, and `CHANGELOG.md`; a new Squadron dependency entry in `user/notes/001-squadron-dependencies.amoeba.md`.

**Excluded**

- Anything the Runner decides. `ProofRunner` is a test fixture that follows a fixed script. It is not a draft of initiative 120.
- `cf_write` in the sequence. Reconciling it needs a live `cf`, and 102 already covers its observer against captured output. The sequence uses `sq_run` only.
- Real Squadron model calls. The fake Squadron writes files shaped from captured fixtures; spending tokens would make the proof slow, costly, and non-deterministic.
- Journal, message, and feed retention. Still slice-plan future work.
- Removing Squadron's run files. Amoeba never deletes them itself; removal waits for a Squadron command (D7).
- Performance targets. The load tier from 102–104 already measures throughput; this slice measures correctness.

## Dependencies

### Prerequisites

All of 101 through 109 implemented. At the time of writing, 101–104 are complete, 105 through 108 are designed, and 109 has no design yet. The proof binds to whatever their contracts publish; names below are from their slice-plan entries and the designs that exist.

### Interfaces Required

- **101–104:** the contracts in `docs/store-contract.md`, `docs/process-contract.md`, `docs/inbox-contract.md`, and `docs/evidence-contract.md`, used as written.
- **106:** `follow()`, `amoeba feed`, the `watch_reviews` kind, `record_detection`, `attribute_review`, and `inspect detections`.
- **106, new requirement:** a public store method that does the Runner's report-back **in one transaction**: record the verdict, mark the file `runner_issued`, and resolve the journal entry. 106's D5 point 3 requires one transaction, but every public `Store` method is its own transaction and there is no public way to group them. Without this method 120 cannot meet 106's own requirement. This goes into 106's task breakdown; if 106 ships without it, this slice adds it.
- **105:** `parse_review_artifact`, `to_verdict_input`, the parsed-content record id, and `amoeba ingest review`, exported from `amoeba.upstream.squadron`.
- **107:** the inbox kind for judge samples and its read method, so the out-of-process Judge in the sequence records samples the way 140 will.
- **Test fixtures:** `tests/fixtures/sq_reviews/` (the captured 102 task-review series, including the provider failure) and `tests/fixtures/sq_runs/` (including the captured paused run `run-20260505-review-a697ad3d.json`).

## Architecture

### Component Structure

```
src/amoeba/process/
  __init__.py          exports the hosting seam (D3)
  tenants.py           standard_tenants(supervisor_dir, settings)
src/amoeba/cli/
  prune.py             amoeba prune sq-runs
src/amoeba/upstream/squadron/
  run_pruning.py       classify_paused_runs(...) -> list[RunDisposition]   (D7)
tests/contract/
  proof_runner.py      ProofRunner: the scripted stand-in Runner tenant
  fake_squadron.py     writes run files and review artifacts from fixtures
  proof_host.py        bootstrap: standard tenants + ProofRunner, via public exports only
  snapshot.py          LifecycleSnapshot: the final state, read through public reads only
  proof_harness.py     start/kill/restart the host; run CLI actors as subprocesses
  test_lifecycle_proof.py     the clean run and the four crash windows
  test_locality.py            store locality under the sequence
  test_public_only.py         the no-internal-access guard
tests/load/
  test_restart_matrix.py      a kill at every step boundary
docs/README.md               the contract index
```

`run_pruning.py` sits in `amoeba.upstream.squadron`, next to 105's parser, because it reads Squadron's run files. The store stays free of any Squadron knowledge.

### Data Flow

**The actors.** Every actor uses only a public surface:

| Actor | Runs | Surface |
| --- | --- | --- |
| Operator | CLI subprocess | `amoeba submit create-project`, `watch-reviews`; `amoeba status`, `stop`; `kill -9` |
| `ProofRunner` (stands in for 120) | Tenant inside the resident process | `host.store_for`, `host.project_ids`, the `Store` read/write API, the journal, 105's parser, 106's report-back method |
| Fake Squadron | Called by `ProofRunner` | Writes run JSON into the throwaway `--sq-runs-dir` and review files into a throwaway reviews directory |
| Judge (stands in for 140) | CLI subprocess | `amoeba submit verdict`, 107's judge-sample kind, `amoeba submit resolution` |
| Human | CLI subprocess | `amoeba submit resolution` |
| PM | Shell | Copies a review file into the registered reviews directory |
| Subscriber (stands in for 160) | `amoeba feed --follow` subprocess, running for the whole sequence | Its stdout transcript |
| Inspector | CLI subprocess | `amoeba inspect … --json` |

**The sequence.** Project `proof`. Each step names the state it leaves behind; `ProofRunner` works out which step it is on from the store alone (D1).

| Step | Who | What happens | State afterwards |
| --- | --- | --- | --- |
| 1 | Operator | `create-project proof`; `watch-reviews` on the reviews directory | Store exists; watch baselined (empty) |
| 2 | Runner | Creates `initiative`, then `slice` (`cf.slice_name = resident-process-and-recovery`, matching the fixtures), then a `gate` under it | Three runnable nodes |
| 3 | Runner | `journal_issue(sq_run)` on the slice node → fake Squadron writes a completed run and review round 1 (part 1) → report-back in one transaction | Verdict `CONCERNS`, detection `runner_issued`, journal `completed` |
| 4 | Runner | Blocks the gate on `judge` | `blocked_on_judge` |
| 5 | Judge | Submits a verdict and two judge samples for the gate, then a resolution for the judge block | Gate `runnable`; samples recorded individually |
| 6 | Runner | `journal_issue(sq_run)` on the gate → fake Squadron writes a **paused** run → Runner resolves the entry with the run id, sets `sq.run_id`, blocks on `sq_checkpoint` | `blocked_on_sq_checkpoint`; a paused run on disk |
| 7 | Runner | Blocks the slice node on `human` (escalation row written with it) | `blocked_on_human` |
| 8 | Human | Resolves the slice block | Slice `runnable` |
| 9 | PM | Copies round 2 (part 1) into the reviews directory | Detection `ingested`; `finding_changes` names round 1 as previous |
| 10 | Human | Resolves the checkpoint block with "abandon, do not resume" | Gate `runnable`; the paused run is now dead |
| 11 | Runner | Marks gate, slice, initiative `done` | All `done`; nothing runnable or blocked |

A second project, `proof-b`, runs steps 1–3 interleaved with the first, in the same supervisor directory, to prove project keying (see Store locality below).

**Restart injection (D4).** `ProofRunner` checks an environment variable naming a kill point and sends itself `SIGKILL` there. The harness restarts the host and lets the sequence finish:

| Kill point | Where | What recovery and the sequence must do |
| --- | --- | --- |
| `after-issue` | Step 3, after `journal_issue` commits, before the fake launch | Recovery finds zero matching runs → entry `unknown`, slice `blocked_on_human`. The Human actor resolves it; `ProofRunner` sees an `unknown` entry whose block is resolved and issues again. |
| `after-launch` | Step 3, after the run and review file exist, before the report-back | Recovery adopts the one matching run. `ProofRunner` sees an adopted entry with no verdict and records it from the artifact. If detection got there first, the record is a retry and writes nothing. |
| `inbox-while-down` | Before step 8 | The Human's resolution is submitted while the process is down and applied on start. |
| `mid-follow` | Any | Not a separate run: the subscriber stays up through every kill above, and its transcript is checked. |

The final state after each is compared to the clean run's, with the expected differences listed per kill point (see Snapshot below).

**Store locality under the sequence.**

- `proof` and `proof-b` in one supervisor directory: `runnable`, `blocked`, `verdicts`, and the feed of each never show the other's rows; `inspect projects` lists both.
- The process is started from one working directory and every CLI actor runs from another. All of them resolve the same supervisor directory.
- The supervisor directory is resolved three ways across three full clean runs: `AMOEBA_STORE_DIR`; `XDG_CONFIG_HOME` only; neither, with `HOME` pointed at a temporary directory. Each run's store, lock, inbox, and detection sidecars land under the expected directory and nowhere else.
- A relative `AMOEBA_STORE_DIR` or `XDG_CONFIG_HOME` is refused by every command (D5).
- A project id with uppercase letters is refused by `submit`, `open_project`, and `Store.open` (D5).

**Pruning (D7).**

```
amoeba prune sq-runs [--sq-runs-dir PATH] [--json]
  owned := every run id in any project's journal results or node sq.run_id   (read-only stores)
  for each run file in the runs directory (read, never written):
    classify → prunable | not_owned | not_paused | owner_not_done | unreadable
  print one row per run file, with its path
```

### State Management

The slice adds no tables and no migration. `done` becomes terminal in the store's write methods (D6); the schema is unchanged.

`ProofRunner` keeps **no** progress in memory. Each tick it reads `nodes_for_project`, `runnable`, `blocked`, `journal_entries`, and `verdicts`, finds the first step whose "state afterwards" does not hold yet, and does that step. This is what makes every kill point recoverable, and it is the pattern the contract index recommends to 120.

## Technical Decisions

### Technology Choices

**D1 — The proof is a scripted in-process Runner plus real subprocess actors.** The Runner in 120 will be a tenant writing through `host.store_for`; the Judge, Translator, and human will write through the inbox from outside. The proof uses exactly those two faces, so a gap it finds is a gap 120, 140, or 160 would have hit.

- Rejected: calling the `Store` API directly from a test with no process. It proves nothing about recovery, the inbox, or the feed, which are where the contract is hardest.
- Rejected: waiting for 120 to be the first real consumer. Contract gaps found then are found by the team that is blocked by them.

**D2 — "Only the documented contract" is a test, not a promise.** `test_public_only.py` walks the AST of every module in `tests/contract/` and fails when:

- an `amoeba` import names a module other than the five public packages (`amoeba.store`, `amoeba.inbox`, `amoeba.feed`, `amoeba.process`, `amoeba.upstream.squadron`) or a name not in that package's `__all__`;
- an attribute whose name starts with `_` is read on anything;
- `sqlite3` is imported.

Each package's `__all__` is pinned by a test written out by hand, as `tests/test_public_api.py` already does for `amoeba.store`, so adding a name to the contract is a deliberate edit in two places. CLI actors run as subprocesses and are unaffected by the guard.

**D3 — `amoeba.process` exports a hosting seam.** Additive: nothing existing changes, as when 103 and 104 added exports to `amoeba.store`. Today the package's `__init__` exports nothing, the `Tenant` protocol lives in `host.py`, and `amoeba start` builds its tenant tuple inline. The Runner has no documented way in.

- Export `ResidentProcess`, `Tenant`, `ProcessSettings`, `Observer`, `Adopt`, `NotApplied`, `Unknown`, and a new `standard_tenants(supervisor_dir, settings) -> tuple[Tenant, ...]`.
- `standard_tenants` returns the inbox tenant first and the detection tenant second, the order both slices depend on. `amoeba start` calls it; so does `proof_host.py`, followed by `ProofRunner`. There is one list of standard tenants.
- `process-contract.md` gains "Hosting a tenant": the three lines that build and run a process with your tenant after the standard ones, taken from `proof_host.py`.
- Rejected: a `--tenant module:Class` flag on `amoeba start`. It adds dynamic import to the CLI before any consumer needs it. 120 can add one if it wants `amoeba start` to host the Runner.

**D4 — Restart injection is by named kill points, checked against an expected-difference table.**

- Kill points are fixed names in `ProofRunner`. Hitting one sends `SIGKILL` to the process's own pid: no mocks, as 102 requires.
- `LifecycleSnapshot` is built only from public reads, keyed by node **title** (ids differ between runs). It holds each node's status; the set of verdict record ids with verdict and standing; finding keys per node; journal entries per node as `(kind, outcome class)`, where `completed` and `adopted` are one class, "applied"; blocked-state count per node; message count per channel; judge samples per gate; and detection outcomes.
- A kill point either leaves the snapshot equal to the clean run's, or differs only as its row in the table says. `after-issue` adds one `unknown` entry, one human block, and one escalation on the slice node. `after-launch` and `inbox-while-down` add nothing.
- The subscriber's transcript, across every kill, must equal `amoeba feed --project proof` read from 0 at the end: no gap, no repeat. Replaying it rebuilds each node's final status.
- **Default suite:** the clean run and the three kill runs. **Load tier:** a kill at every step boundary 1–11, each followed by restart, completion, and the same comparison.

**D5 — Locality: no relative directories, and project ids that cannot collide on disk.** *(PM ratification required: both halves narrow 101's published contract. See [PM ratification](#pm-ratification).)*

- **Relative directory variables are refused.** `paths.store_dir` uses `AMOEBA_STORE_DIR` and `XDG_CONFIG_HOME` verbatim, so a relative value resolves against each process's working directory. A process started in one directory and a submitter in another then use two different supervisors, and the submitter's files are never applied. `store_dir` raises `ValueError` naming the variable when either is relative. The XDG specification says to ignore a relative `XDG_CONFIG_HOME`; ignoring it would fall back to the default without saying so, which this project does not do.
- **Project ids are ASCII slugs:** `[a-z0-9][a-z0-9._-]*`. macOS filesystems are case-insensitive by default, so `Demo` and `demo` are one store file today while being two projects to every query. Unicode ids have the same problem through normalization. `validate_project_id` is the one definition and every caller already goes through it. Mapping a Context Forge project name to an Amoeba project id is 120's job; the contract states the rule it must satisfy.
- Nothing is on disk yet that could break: Amoeba has no users outside this repository's tests.

**D6 — `done` is terminal, and the store enforces it.** Not a contract change: `store-contract.md` already publishes `done` as terminal, and no write refuses to leave it. This is a defect against the published contract, fixed like any other. It matters here because D7's report calls a run dead when its nodes are `done`; that is only true if `done` is final. Four refusals, all `InvalidTransitionError`, are one rule, "nothing happens on a finished node":

- `update_node_status` refuses any change away from `done`;
- `block()` refuses a `done` node;
- `journal_issue` refuses a `done` node;
- `update_node_status(done)` refuses a node with an unresolved journal entry.

The last one means recovery can never meet an unresolved entry on a `done` node, so `journal_escalate` needs no new branch. Existing tests that move a node out of `done`, if any, are fixed, not the rule.

**D7 — The pruning policy is Amoeba's; removal stays Squadron's.** The architecture gives Amoeba the pruning *policy* ("paused runs are never pruned on SQ's side; pruning policy is Amoeba's") and forbids any part editing Squadron's run files ("State is the interface"). Both hold if Amoeba decides and reports, and never deletes.

- **Prunable** means all of: the run id is **owned** (recorded in some journal entry's result, or in some node's `sq.run_id`, in any project of this supervisor); the file's `status` is `paused` (Squadron prunes completed and failed runs itself); and every node that references the run is `done` (D6 makes that final).
- Everything else is listed with why: `not_owned` (the PM's own runs), `not_paused`, `owner_not_done`, `unreadable`.
- **Read-only on both sides.** The command opens every store read-only and reads run files; it writes nothing anywhere. Each row carries the file's path, so the operator can remove a run by hand. That is a person acting on their own files, outside Amoeba's writer model.
- **Removal arrives through Squadron.** A new entry in `001-squadron-dependencies.amoeba.md` asks for a command that discards one paused run by id, dated, not tied to a version. When it lands, a later slice adds `--apply` that calls it for each `prunable` row. Nothing in Amoeba ever unlinks a Squadron file.
- **Settles on `--sq-runs-dir`,** defaulting to the same `DEFAULT_SQ_RUNS_DIR` constant `ProcessSettings` uses. Tests always pass a throwaway directory, as 102 requires.

Rejected:

- *Amoeba unlinking the file itself, behind `--apply`.* It would be the first place Amoeba destroys data it did not create, and a standing exception to "State is the interface". Reporting delivers the policy without either.
- *An age threshold* ("paused for more than N days"). A number with no evidence behind it, and it would name runs a live node still owns.

**D8 — The contract index is a map plus an obligations list.** `docs/README.md` holds:

- **Which document answers what:** one row per contract document, with the questions it answers.
- **The public packages** and their export sets, linking to the pinned tests.
- **Hosting a Runner:** a link to D3's section in `process-contract.md`, and `ProofRunner`'s "work out the step from the store" pattern.
- **Obligations on consumers,** every "must" the contracts put on 120, 140, and 160, each linking to its source: journal before side effect; issue `sq` with non-TTY stdin and resume only by explicit id; attach reviews by `attribute_review`; report back in one transaction and from the artifact through 105's parser; poll `stop_requested` and return promptly; never cache `project_ids`; save a feed cursor after acting and make handling repeatable; resolutions target a blocked state, not a node; wait for `create_project` to apply before submitting into it; no secrets in any payload; project ids are slugs; `done` is final.
- **Known limits,** linking to each contract's future-work section.

A test checks every relative link and anchor in `docs/*.md` resolves, so the index cannot rot silently.

### Patterns and Conventions

- `RunDisposition` is a `StrEnum` defined once: `prunable`, `not_owned`, `not_paused`, `owner_not_done`, `unreadable`. Squadron's `paused` status string is one named constant in `run_pruning.py`, beside the observer's existing reading of the same field.
- Kill-point names are one `StrEnum` in `proof_runner.py`; the harness and the tests reference it.
- `amoeba prune sq-runs` exits `OK` when it prints its report, and `FAILURE` only for an unexpected error at the boundary. No new exit code.
- Errors follow the project's rule: the prune command logs and re-raises anything it did not expect. The one swallowed exception is `FileNotFoundError` for a run file that disappears between listing and reading, with a comment: Squadron pruned it in between, so there is nothing to report.

### Contract gaps found at design

Found by reading the contracts and the code they describe while writing this design. The proof tests pin each fix.

| Gap | Effect today | Disposition |
| --- | --- | --- |
| `amoeba.process` exports nothing; `start` hard-codes tenants | 120 has no documented way to host the Runner | D3 |
| Relative `AMOEBA_STORE_DIR` / `XDG_CONFIG_HOME` used as given | Process and submitter in different directories use different supervisors | D5 |
| Project ids differing only in case accepted | Two projects share one store file on macOS | D5 |
| `done` documented terminal, not enforced | A finished node can be reopened; the pruning report could call a live run dead | D6 |
| No public way to make 106's report-back one transaction | 120 cannot meet 106's D5 point 3 | Required from 106 (see Interfaces Required) |

Gaps the proof finds during implementation are added to this table with their disposition, and the contract index links to it.

### PM ratification

Two changes narrow what 101's published store contract accepts. Nothing else in this slice changes a published contract: D3 only adds exports, D6 enforces what the contract already says, and D7 writes nothing outside Amoeba. Neither item departs from an architectural principle.

| Change | Published today | After | If not ratified |
| --- | --- | --- | --- |
| Refuse a relative `AMOEBA_STORE_DIR` or `XDG_CONFIG_HOME` | "used verbatim" | `ValueError` naming the variable | The contract documents that both must be absolute, and the locality proof runs with absolute values only. The split-supervisor failure stays possible. |
| Project ids are ASCII slugs, `[a-z0-9][a-z0-9._-]*` | Any non-empty id with no path separator, not `.` or `..` | `ValueError` / `SUBMISSION_REFUSED` | The contract documents the case-insensitive filesystem collision as a known limit and tells 120 to lowercase ids itself. |

**Gate:** Phase 5 does not break these two into tasks until the PM rules. Everything else in the slice, including the rest of D5's locality proof, can proceed without them.

## Implementation Details

### API Contracts

**`amoeba.process` exports (D3):** `ResidentProcess`, `Tenant`, `ProcessSettings`, `Observer`, `Adopt`, `NotApplied`, `Unknown`, `standard_tenants`.

**`amoeba.upstream.squadron` additions (D7):**

| Name | Shape |
| --- | --- |
| `classify_paused_runs(runs_dir, *, owned: Mapping[str, Sequence[Node]]) -> list[RunDisposition]` | Pure over the directory listing and the ownership map. Reads files; writes nothing. |
| `RunDisposition` | `run_id`, `path`, `status` (Squadron's string, or `None` if unreadable), `disposition`, `owner_node_ids` |

The ownership map is built by the CLI from each project's read-only store: `recorded_result_run_ids` and each node's `sq.run_id`.

**CLI:**

| Command | Output |
| --- | --- |
| `amoeba prune sq-runs [--sq-runs-dir PATH] [--json]` | One row per run file: `run_id, path, status, disposition, owner_node_ids`. Writes nothing. |

**Store behavior changes (D5, D6):** `validate_project_id` narrows to ASCII slugs; `store_dir` refuses relative values; the four `done` refusals. All raise existing exception types. Each is documented in `store-contract.md` and named in `CHANGELOG.md` as a change to 101's contract.

## Integration Points

### Provides to Other Slices

- **Initiative 120:** the hosting seam; the demonstrated sequence as a worked example of a Runner tick; the contract index; the obligations list; `done` as a guaranteed final state it can rely on.
- **Initiatives 140 and 160:** the same index, with the Judge and subscriber roles in the proof as worked examples of their surfaces.
- **Slice 108:** nothing new; the proof's feed check covers any change 108 later lands on the feed, since it reconciles by table.

### Consumes from Other Slices

- **101–104** through their contracts. The behavior changes in D5 and D6 are this slice's, recorded as changes to 101's contract; 101's design document is not edited.
- **106:** the feed, detection, attribution, and the report-back method named in Interfaces Required.
- **105:** the parser, used by `ProofRunner` for its own reviews and, through detection, for the PM's.
- **107:** judge samples, submitted by the Judge actor.

If a dependency's contract turns out not to support a step as its document says, that is a gap: it goes in the table, and the fix lands in this slice unless the owning slice is still open.

## Success Criteria

### Functional Requirements

- The clean sequence runs to step 11 with every node `done`, three verdicts recorded (two review rounds and the Judge's), two judge samples recorded separately, one detection `ingested`, one `runner_issued`, and nothing runnable or blocked.
- `finding_changes` on the round-2 verdict names round 1 as the previous round, though one was recorded by the Runner and the other detected.
- Each kill point leaves a sequence that completes after restart, with a final snapshot equal to the clean run's except for the differences listed for that kill point.
- The subscriber's transcript across every kill equals the feed read from 0 at the end, and replaying it rebuilds every node's final status.
- `proof-b` never appears in any read, feed, or listing for `proof`, and the reverse.
- All three directory resolutions put every file under the expected supervisor directory; a relative `AMOEBA_STORE_DIR` or `XDG_CONFIG_HOME` is refused with an error naming the variable.
- A project id with an uppercase letter, a space, or a non-ASCII character is refused by `submit`, `open_project`, and `Store.open`.
- Leaving `done`, blocking a `done` node, journaling on a `done` node, and marking done a node with an unresolved entry each raise `InvalidTransitionError`.
- After the clean sequence, `amoeba prune sq-runs` lists the step-6 paused run as `prunable`, the captured paused fixture copied into the same directory as `not_owned`, and a paused run owned by a still-`runnable` node as `owner_not_done`. Every file in the runs directory is byte-identical before and after the command.

### Technical Requirements

- `test_public_only.py` passes over `tests/contract/`, and fails when a deliberately private import is added (checked by a test of the guard itself).
- Export sets for all five public packages are pinned by hand-written tests.
- The store still imports nothing from `amoeba.upstream`, `amoeba.process`, or `amoeba.feed`; `run_pruning.py` imports no store internals.
- The writer guard is unchanged: `proof_host.py` constructs `ResidentProcess`, which opens stores through `project_stores.py`.
- Every relative link and anchor in `docs/*.md` resolves.
- `ruff`, `pyright` strict, and the full suite are clean; the restart matrix passes under `uv run pytest tests/load`. Files stay near 300 lines.

### Integration Requirements

- An initiative 120 designer can answer, from `docs/` alone: how to host the Runner; how to journal, launch, and report back a Squadron review; how to block and learn of a resolution; how to follow the feed; which project ids are valid; and what it must never do. Each answer is one link from `docs/README.md`.
- The gap table is complete: every gap found during implementation has a disposition.

### Verification Walkthrough

Draft; refined with real output when Phase 6 completes. Run in **bash** from the repository root.

**1. The proof, clean and under the three crash windows.**

```bash
uv run pytest tests/contract -v
```

Expected: `test_lifecycle_proof.py` passes four cases (`clean`, `after-issue`, `after-launch`, `inbox-while-down`), `test_locality.py` passes, `test_public_only.py` passes.

**2. The guard catches internal access.** Add `from amoeba.store.sql import NODES_TABLE` to the top of `tests/contract/snapshot.py` and rerun `uv run pytest tests/contract/test_public_only.py`. It fails naming the file and the import. Remove the line.

**3. Every step boundary.**

```bash
uv run pytest tests/load/test_restart_matrix.py -v
```

Expected: eleven cases, one per step, all passing.

**4. Locality by hand.**

```bash
AMOEBA_STORE_DIR=relative/dir uv run amoeba status; echo "exit $?"
env -u AMOEBA_STORE_DIR XDG_CONFIG_HOME=relative uv run amoeba status; echo "exit $?"
export AMOEBA_STORE_DIR="$(mktemp -d)"
uv run amoeba submit create-project --project Demo --by pm; echo "exit $?"
```

The first two fail with an error naming the variable. The third exits `SUBMISSION_REFUSED` (9) with a message giving the project-id rule, and `ls "$AMOEBA_STORE_DIR"` shows nothing written.

**5. Pruning.** Needs a store that owns a paused run; the clean proof run leaves one behind (step 6) when kept with `pytest --basetemp`:

```bash
uv run pytest tests/contract/test_lifecycle_proof.py -k clean --basetemp=/tmp/amoeba-proof
export AMOEBA_STORE_DIR=/tmp/amoeba-proof/<test dir>/supervisor
RUNS=/tmp/amoeba-proof/<test dir>/sq-runs
cp tests/fixtures/sq_runs/run-20260505-review-a697ad3d.json "$RUNS/"
ls -l "$RUNS" > /tmp/before
uv run amoeba prune sq-runs --sq-runs-dir "$RUNS"
ls -l "$RUNS" | diff /tmp/before -
```

The report lists the step-6 run `prunable` with its path, the copied fixture `not_owned`, and the step-3 run `not_paused`. The `diff` prints nothing: no file was touched.

**6. The index.** Open `docs/README.md` and follow "Hosting a Runner" and each obligation link; every one lands on the section that states it. `uv run pytest tests/test_docs_links.py` checks the same mechanically.

## Implementation Notes

### Development Approach

Relative effort 4 (the slice plan estimated 3, before the gaps above were found).

1. **Hardening first, each with its test:** D5 (locality), D6 (`done` terminal), D3 (hosting seam and export pins). The proof needs all three, and each is small.
2. **Proof scaffolding:** `fake_squadron.py`, `snapshot.py`, `proof_harness.py`, `proof_host.py`, and the `test_public_only.py` guard with its self-test.
3. **`ProofRunner` and the clean run.** Build the step table as data; each step is "state that must hold" plus "action".
4. **The three kill points,** then the restart matrix in the load tier.
5. **Locality tests** (two projects, three resolutions, split working directories).
6. **Pruning:** `run_pruning.py` against fixtures, then the CLI, then the proof's pruning assertions.
7. **Docs:** `docs/README.md`, contract updates, the Squadron dependency entry, `CHANGELOG`, and the link test.

Steps 1, 2, 5, and 6 need only 101–104 and can start before 105 through 109 land. Steps 3 and 4 need all of them.

### Special Considerations

- **The proof must not grow into a Runner.** `ProofRunner` follows a fixed table and makes exactly one decision (re-issue after an `unknown` entry whose block was resolved), because the `after-issue` window cannot complete without it. Anything more belongs to 120.
- **Timing.** Every wait in the harness is "until a condition holds, with a timeout", reading public state, never a fixed sleep. Detection's settle rule and the follower's interval make fixed sleeps flaky.
- **Squadron's files are never written or deleted** by anything in this slice. The pruning report reads them; a test asserts the runs directory is unchanged after it runs.
