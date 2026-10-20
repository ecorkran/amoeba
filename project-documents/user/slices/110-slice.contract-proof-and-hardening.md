---
docType: slice-design
slice: contract-proof-and-hardening
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies:
- 101
- 102
- 103
- 104
- 105
- 106
- 107
- 108
- 109
interfaces: []
dateCreated: 20261015
dateUpdated: 20261020
status: complete
turns: 50
promptTokens: 2427334
cachedTokens: 2336377
cacheWriteTokens: 90887
completionTokens: 23012
durationSeconds: 255.0
costUsd: 1.655223
usageRounds: 3
pricedRounds: 3
revision_number: 2
---

# Slice Design: contract-proof-and-hardening

## Overview

Slices 101–109 each proved their own surface. No test yet drives the whole substrate the way its consumers will: a Runner inside the resident process, a Judge and a PM submitting from outside, subscribers following locally and over the network, and restarts. This slice adds that test, and it may use only the documented API.

The slice has four parts:

1. **The contract proof.** `tests/contract/` runs one realistic lifecycle sequence across two projects, through real processes, with crashes injected at named points. Its imports are limited, mechanically, to the names each public package exports. The full sequence runs locally. A short subset then runs over `amoeba serve` and kills each process once (D2).
2. **Hardening.** The proof surfaces gaps. Four are already known (H1–H4 in D7): `amoeba.process` exports nothing, the Runner's one-transaction report method was deferred "to 120 (or 110, if earlier)", a documented path helper lives in an internal module, and Squadron's run-file header model lacks the `updated_at` field pruning needs. Each gap is closed additively in this slice. A gap that needs a behavior or schema change stops for the PM.
3. **Paused-run pruning.** Squadron never prunes paused runs. `amoeba prune sq-runs` picks the paused runs Amoeba launched and has finished with, and deletes them through `sq runs prune`. It never deletes Squadron's files itself.
4. **Consumer documentation.** `docs/substrate-guide.md` is the entry point for authors of initiatives 120, 140, and 160. It maps each initiative to the surfaces it uses and walks the proven sequence.

Store locality was decided in slice 101 (central, per supervisor, keyed by project). This slice only checks, inside the proof's oracle, that it holds under a realistic sequence (D6).

## Value

- **Initiative 120 can start.** The slice plan names this slice as that gate. The Runner's whole contract is exercised from outside before 120 commits to it: hosting a tenant, the journal, recovery, reporting a review it launched, blocking and resolving, and following the feed.
- **Gaps are found now.** Today a Runner author would have to import `amoeba.process.host` and `amoeba.cli.lifecycle.build_tenants`, which no contract names, and would have to write a three-step transaction by hand that 106 says must be one. These are fixed before 120 depends on them.
- **The proof is executable documentation.** `tests/contract/scenario.py` reads as the sequence a consumer follows. If a later slice breaks the contract, this suite fails.
- **Paused runs stop piling up.** The supervisor's runs directory holds 13 paused runs today (*observed 20261015*), and Squadron never removes them. Once 120 launches runs, Amoeba's paused runs would add to that count indefinitely.

## Technical Scope

### Included

- `tests/contract/`: the local scenario, a proof Runner tenant, crash injection, the end-state oracle, a feed-replay oracle, the network subset, and the public-import rule (D1–D6).
- **Hardening (D7):**
  - H1: `amoeba.process` exports its tenant-hosting contract. `build_tenants` moves out of `cli/lifecycle.py` as `standard_tenants`.
  - H2: `Store.record_runner_report`.
  - H3: `store_dir` and `project_store_path` are exported from `amoeba.store`.
  - H4: `SquadronRun` gains `updated_at`, in place in `process/observers/sq_runs.py`.
  - Any further gap the proof finds, fixed under D7's rule.
- **Pruning (D8):** `amoeba.process.run_pruning` (a pure selection rule), `amoeba prune sq-runs` (preview by default, `--yes` to delete), a new `ExitCode` member, and a schema-v5 run-file fixture.
- **Docs:** `docs/substrate-guide.md` is new. `process-contract.md` gains sections on hosting tenants and on pruning. `evidence-contract.md` and `store-contract.md` add `record_runner_report`. The Future-work lines that point at 110 are updated, and `CHANGELOG.md` is updated.

### Excluded

- **Store retention and compaction** of journal entries, changes, verdicts, and resolved nodes. Slice 101 listed "pruning and retention" for 110. The slice plan later scoped 110 to paused Squadron runs and moved store retention to Future Work item 5, "until there is real data volume to measure". Nothing in the store is deleted here.
- **Pruning anything but paused runs Amoeba launched.** Completed and failed runs are pruned by Squadron itself (newest 10 kept per pipeline). Runs the PM launched are the PM's.
- **Automatic pruning.** Pruning is a command the PM runs, never a tenant (D8). If initiative 120 wants pruning, it invokes `amoeba prune sq-runs --yes` as a subprocess, the same public CLI surface the PM uses. The selection rule is internal and is not exported. Scheduling it is 120's decision.
- **A tenant-registration mechanism** such as plugins, entry points, or a config file. The Runner is Amoeba code. 120 composes `standard_tenants(...)` with its own tenant in `amoeba start` (H1).
- **New behavior on any existing surface.** If the proof finds a defect that needs one, the PM decides (D7). One carve-out is accepted up front: H2 adds `Store.record_runner_report`, a new method composed from existing transactions. The evidence contract deferred it "to 120 (or 110, if earlier)", and step 3 of the proof needs it, so it lands here rather than in 120.
- **Re-proving what a dependency's own suite already proves.** The proof does not cover `cf_project_changed`, vacuous checks, or listing parity with `amoeba inspect`. 108's end-to-end test, 107's store tests, and 109's parity test own those. The scenario covers each dependency only where the plan's sequence passes through it.

## Dependencies

### Prerequisites

- **101–106:** merged. Their contracts are in `docs/`.
- **107, 108, and 109:** merged (*confirmed 20261019*). This slice uses judge samples (107); `CFWatchTenant` and the `cf` version-label capture, which move with `build_tenants` (108); and `amoeba serve`, `amoeba.inspection`, the SSE feed, and `store/discovery.py` (109). The names this design takes from them were checked against the merged code on 20261019, and the design was amended where the code differed.
- **Squadron:** `sq runs prune [run_ids…] --yes` (*observed 20261015, Squadron 0.22.0*). D8 states the behavior this design relies on. The design depends on that shape, not on the version.

### Interfaces Required

- **Inbox (103):** `submit()` for `create_project`, `intent`, `resolution`, `verdict` (with 107's `judge_invocation_id`), and `watch_reviews`. Also `Store.submission(id)`.
- **Store (101, 102, 104, 106, 107):**
  - Nodes: `create_node`, `update_node_status`, `update_sq_reference`, `block`, `resolve`, `runnable`, and `blocked`.
  - Journal: `journal_issue`, `journal_resolve`, `recorded_result_run_ids`, and `journal_entries`.
  - Messages: `pending_intents` and `acknowledge_message`.
  - Evidence and feed: `verdicts`, `finding_changes`, `detections`, `changes`, and `calibration`.
- **Process (102):** `ResidentProcess`, `Tenant`, `ProcessSettings`, recovery with the `sq_run` observer, and the lock-based `amoeba stop` and `amoeba status`.
- **Feed (106):** `follow()` and `FeedSettings` from `amoeba.feed`; `Change` from `amoeba.store`.
- **Pruning reads (internal, `cli/prune.py` only):** `Store.nodes_for_project` and `recorded_result_run_ids`; `discover_project_ids` (`store/discovery.py`, 109); `DEFAULT_SQ_RUNS_DIR` (`process/settings.py`, 102).
- **Network (109):** `POST …/submissions`, `GET …/submissions/{id}`, and `GET …/feed` with `Last-Event-ID`.
- **Parser (105):** `parse_review_artifact` and `to_verdict_input`. The proof Runner reports its reviews through these (evidence contract, point 5).

## Architecture

### Component Structure

```
tests/contract/
  __init__.py
  public_api.py        PUBLIC_ROOTS; the AST import rule (D1), applied to this directory
  test_public_api_rule.py
  runner_tenant.py     ProofRunner: a Tenant driven by intents, with named crash points (D3)
  bootstrap.py         starts ResidentProcess(standard_tenants(...) + ProofRunner) in a subprocess
  scenario.py          the steps, as data: actor, action, crash point, expected changes (D4)
  oracle.py            declared end state; feed-replay reconstruction (D5)
  test_lifecycle_proof.py   the local scenario
  test_network_subset.py    D2's network subset, with one kill of each process
tests/fixtures/sq_runs/ + one schema-v5 paused run (sanitized from a real file)

src/amoeba/process/__init__.py    __all__ gains the hosting contract (H1)
src/amoeba/process/tenants.py     standard_tenants(settings, supervisor_dir)   (was cli/lifecycle.build_tenants)
src/amoeba/store/__init__.py      + store_dir, project_store_path (H3)
src/amoeba/store/runner_report.py record_runner_report (H2), a Store mixin
src/amoeba/process/observers/sq_runs.py  SquadronRun gains updated_at (H4)
src/amoeba/process/run_pruning.py PRUNE_RETENTION, SQ_PRUNE_TIMEOUT_SECONDS, select_prunable() (D8)
src/amoeba/cli/prune.py   add_prune_parser, run_prune
docs/substrate-guide.md
```

**Layering.** These rules extend `test_import_boundaries.py`:

- `process/run_pruning.py` imports only `process/observers/sq_runs` and the standard library. It is pure: no store, inbox, CLI, or I/O.
- `cli/prune.py` is the only module that knows both the selection rule and the store.
- `process/tenants.py` takes only what `build_tenants` already imports, so the move adds no package edge. Existing import-boundary rules still apply, including `amoeba.upstream` never importing `amoeba.process` (105's rule, unchanged).
- Nothing under `tests/contract/` may import outside `PUBLIC_ROOTS` (D1).

### Data Flow

**The proof** (local):

```
pytest ─┬─ bootstrap subprocess: ResidentProcess(tenants = standard_tenants(…) + ProofRunner)
        │     HOME, AMOEBA_STORE_DIR, cf_data_dir: all under tmp_path
        ├─ subscriber: follow() on a thread on project alpha              records every Change
        └─ scenario driver, step by step:
             PM / Judge actors ── inbox.submit(kind, payload, id) ──► InboxTenant applies
             Runner steps      ── inbox.submit(intent{step, crash_at}) ──► ProofRunner.tick:
                                    pending_intents → do the step with the store API → acknowledge
                                    crash_at reached → os.kill(getpid(), SIGKILL)
             crash → driver waits for exit, restarts bootstrap → recovery → tenants resume
             external work ── write a review artifact into the watched dir
             after each step: wait until the subscriber has the step's expected change kinds
end:  oracle reads every project through Store.open_read_only and compares with the declared end state
      oracle replays the subscriber's changes from seq 0 and compares node statuses with the store
```

**The network subset** (D2): the bootstrap process, then `amoeba serve`, then an httpx SSE follower:

```
POST intent → GET outcome until applied → SSE delivers message_posted
kill -9 serve; POST is refused (connection error); restart serve; SSE resumes with Last-Event-ID
kill -9 resident process; POST intent → 202 (queued); restart; SSE delivers it
end: the SSE seq list equals a final local follow(after=0): no gap, no repeat
```

**Pruning:**

```
amoeba prune sq-runs [--yes]
  for each project in discover_project_ids(store_dir()):        read-only opens; any failure → refuse, delete nothing
      owned |= recorded_result_run_ids(p)            run ids Amoeba's journal adopted or completed
      held  |= {n.sq.run_id for n in nodes_for_project(p) if n.status != DONE and n.sq.run_id}
  runs = parse_run_file(f) for f in DEFAULT_SQ_RUNS_DIR/*.json   (unparseable → WARNING naming the file, never a candidate)
  candidates = select_prunable(runs, owned, held, now)            pure
  print the candidates, and how many owned paused runs were kept
  --yes and candidates:
      sq runs prune <ids…> --yes        stdin=DEVNULL, timeout=SQ_PRUNE_TIMEOUT_SECONDS
      re-read the runs dir: any candidate still present → print it, with sq's exit status and stderr
  exit OK if every candidate is gone (or there were none); else ExitCode.PRUNE_INCOMPLETE
```

### State Management

This slice adds no store state, no table, and no migration. `record_runner_report` writes existing tables. Pruning writes nothing to the store, and its only effect is the files `sq runs prune` deletes. The proof's state lives entirely under `tmp_path`: the supervisor directory, a fake `HOME` (Squadron runs directory), a CF data directory, and per-project reviews directories.

## Technical Decisions

### Technology Choices

No new dependency. The proof uses `httpx2`, which slice 109 added as a dev dependency, and the subprocess and signal machinery the existing harnesses already use. Nothing in it is mocked: signals, locks, SQLite, the inbox directory, and the HTTP server are all real. The only stand-in is the Squadron side effect, explained in D3.

### Decisions

**D1 — Public means exported, and the proof's imports are checked.** `PUBLIC_ROOTS` lists the library surfaces a consumer may import:

- `amoeba.store`, `amoeba.inbox`, `amoeba.feed`, `amoeba.process`;
- `amoeba.upstream.squadron` and `amoeba.upstream.context_forge` (108);
- `amoeba.inspection` (109).

The CLI and HTTP are the other public surfaces, reached only by subprocess and by HTTP. An AST test fails if any module in `tests/contract/` imports a submodule of a root (`amoeba.store.paths`, for example), imports a name not in the root's `__all__`, or imports any `amoeba` module not in `PUBLIC_ROOTS`. This turns "no internal access" from a claim into a property the suite checks.

**D2 — The full scenario runs locally; a network subset proves the remote path.** The scenario's out-of-process actors use `amoeba.inbox.submit`, `Store.submission`, and `follow()` directly, with no transport abstraction. The Runner acts in-process through the store API, which is its documented position. The oracle reads through `Store.open_read_only`.

The slice plan asks that the contract be "proven through the network surface as well as locally". `test_network_subset.py` meets that with the remote path a consumer such as the notification bridge actually uses, and nothing more:

- an intent POSTed, its outcome polled until `applied`, and the change received over SSE;
- `kill -9` of `amoeba serve`, a restart, and SSE resumed with `Last-Event-ID`;
- `kill -9` of the resident process, a POST accepted while it is down, a restart, and delivery.

The SSE `seq` list must equal a final local `follow(after=0)`.

109's design hands "`kill -9` of each process mid-sequence" to this slice, so both kills stay. The full scenario is not repeated over HTTP, because the network layer adds no write path and no state: what it could get wrong is transport, cursor, and survival, which the subset covers. Listing parity with `amoeba inspect` is 109's own test.

**D3 — The proof Runner is a real tenant driven by `intent` messages.** `ProofRunner` implements `Tenant` and nothing more. Each tick it reads `pending_intents`, performs one step, and acknowledges the intent. The intent body names the step and an optional `crash_at` point:

- `build_tree` creates initiative → slice (`cf.slice_name` set, so 106's attribution rule finds it) → gate.
- `launch_review` journals an `sq_run`, then performs the stand-in side effect. It writes a run file with `status` `completed` into the fake `HOME`'s runs directory, taken from a fixture with its `run_id`, `pipeline`, `params`, and `started_at` set to match, plus a review artifact from `tests/fixtures/sq_reviews/` into the project's watched directory. It then reports with `record_runner_report` (H2), parsing the artifact through 105's parser. A finished review's run is never paused, so step 12 never sees these as candidates.
- `checkpoint` journals an `sq_run`, writes a run file with `status` `paused`, resolves the entry `completed` with the `run_id`, sets the **gate** node's `sq.run_id`, and blocks the gate on `sq_checkpoint`.
- `finish` marks the slice and gate `done`.

*Run-file ages.* Every paused run file the stand-in writes (the `checkpoint` runs, and step 7's unowned run) has `updated_at` set to `STANDIN_RUN_AGE` before the step's wall-clock time. `STANDIN_RUN_AGE` is defined once in `scenario.py` as 365 days, far past any retention the pruning rule could plausibly use. The proof asserts which runs are selected and kept, never the retention itself, so changing `PRUNE_RETENTION` cannot break step 12. The pure `select_prunable` tests inject `now` and import `PRUNE_RETENTION` directly; they are not bound by D1.

*Why a stand-in, not real `sq`.* The proof is about Amoeba's contract. A real `sq review` needs a model provider, costs money, and is not deterministic. The stand-in produces exactly what the observers and detection read (a run file and a review file), in the shapes the 102 and 105 fixtures pin. Pruning's deletion path is tested against a stub `sq` that reproduces the observed interface (D8): named ids, `--yes`, a refusal exiting 1, and an already-gone file counting as removed. No test in this slice runs the real `sq`.

*The intent bodies are the proof's own.* `intent` is the Translator → Runner channel. The proof uses it only as a test driver, and its body format (a step name and `crash_at`) is not a contract. The substrate guide says so, so that initiative 120 does not read it as one.

Crash points are named constants in `runner_tenant.py`:

- `AFTER_JOURNAL`: after `journal_issue` commits, before any side effect.
- `AFTER_SIDE_EFFECT`: after the run file and artifact are written, before the report.

At a crash point the tenant sends itself `SIGKILL`. Nothing is caught, flushed, or cleaned up.

**D4 — The scenario.** It runs in this order on project `alpha`, interleaved with a smaller sequence on project `beta`. `beta` runs only steps 1, 2, and 9. It cannot be dropped, because D6's keying checks need a second project and step 12's held case needs an owned paused run whose gate is still open. The table states, for each step, what the store must show afterward. The exact expected changes are in `scenario.py`.

| # | Actor and action | Proves |
| --- | --- | --- |
| 1 | PM: `create_project` alpha and beta; `watch_reviews` for each | Runtime project creation (103); per-project reviews directories |
| 2 | Runner: `build_tree` on both projects | Node writes; `node_created` on each project's own feed only |
| 3 | Runner: `launch_review` | Command-before-result; `record_runner_report` writes the verdict, the `runner_issued` ledger row, and the `completed` entry in one commit; detection does not ingest the file again |
| 4 | Runner: `launch_review` with `crash_at=AFTER_SIDE_EFFECT`; restart | Recovery adopts the run (exactly one match). Detection then ingests the artifact as `ingested`, with the same record id the Runner would have used (evidence contract, point 5). One verdict for the round, not two |
| 5 | Runner: `launch_review` with `crash_at=AFTER_JOURNAL`; restart | Zero matches: entry `unknown`, node `blocked_on_human`, an escalation message on the feed |
| 6 | PM: `resolution` for that node | The human reply flips the node runnable (103) |
| 7 | External: a PM-launched review artifact is written into alpha's directory, and a paused run file for it (a run id no journal entry carries) into the runs directory | Detection ingests it with correct provenance; `finding_changes` compares it with step 4's round |
| 8 | Judge: two `verdict` submissions with one `judge_invocation_id` | Samples recorded individually, through the inbox path initiative 140 will use (107) |
| 9 | Runner: `checkpoint` on alpha and on beta | `blocked_on_sq_checkpoint` holding the run id |
| 10 | Stop the resident process gracefully. While it is down, the PM submits a `resolution` for alpha's checkpoint. Start | Submissions made while the process is down are applied on start |
| 11 | Runner: `finish` on alpha | Final statuses; beta's checkpoint stays open |
| 12 | PM: `amoeba prune sq-runs` (preview), then `--yes` with a stub `sq` on `PATH` | Selects only alpha's checkpoint run (its gate is `done` after step 11). Beta's run is held (beta's gate is still blocked), and step 7's run is unowned. The preview reports one owned run kept (beta's) |

The scenario uses `kill -9` (steps 4 and 5) and a graceful stop (step 10). Both are restart paths the process contract promises. The server's crash and a resident crash under a live stream are in the network subset (D2).

**D5 — Two oracles.**

- *End state.* `oracle.py` declares, per project: node statuses; blocked states and their resolutions; journal entries by outcome (`completed`, `adopted`, `unknown`, and resolvers); verdicts with their trust labels and `judge_invocation_id`; detection-ledger outcomes by path; message channels and acknowledgment state; and the submission outcomes. The oracle compares the store with this declaration through the public read API. A missing or extra row fails the test.
- *Feed replay.* Replaying the subscriber's changes from `seq` 0 (`node_created` sets a status and `node_status_changed` moves it) must reproduce every alpha node's final status. The `seq` list must be strictly increasing with no gaps, across every restart. This proves the feed is complete enough to rebuild state, which is what 106 promised subscribers.

**D6 — Locality is checked by the oracle, not by a separate suite.** Slice 101 decided locality, and `tests/test_paths.py` pins how the path is resolved. Under the realistic sequence, the proof adds the two checks that only it can make:

- The supervisor directory holds exactly `alpha.sqlite3` and `beta.sqlite3`.
- Project keying holds end to end. alpha's reviews directory never produces a beta row. Each project's feed carries only its own changes. alpha's oracle sees nothing of beta's.

`HOME` is always a temporary path, so the real home directory is never touched.

**D7 — Hardening: additive fixes only, everything else to the PM.** A gap is any symbol, method, or document a consumer would need that the public surface lacks. A gap is fixed in this slice when the fix is additive: an export, a document section, a new method composed from existing transactions, or a move with no behavior change. A gap whose fix changes existing behavior, a schema, or a recorded value is written up and **stops for the PM**. H1–H4 are already accepted. Any other gap the proof discovers is fixed here if the fix is additive, and stops for the PM otherwise. The PM then amends the design or defers the gap. Every gap, whichever way it went, is listed once in `CHANGELOG.md`, and the substrate guide links to that entry. The four known gaps:

- **H1: `amoeba.process` exports nothing.** The process contract says it is "sufficient for building a tenant". Building one today means importing `amoeba.process.host`, and composing with the shipped tenants means importing `amoeba.cli.lifecycle.build_tenants`. The fix:
  - `__all__` gains `ResidentProcess`, `Tenant`, `ProcessSettings`, `Observer`, `Observation`, `Adopt`, `NotApplied`, `Unknown`, `standard_tenants`, and the process errors that `start` maps to exit codes (`ProcessError`, `AlreadyRunningError`, `StartupFailedError`, `GraceExpiredError`).
  - `build_tenants` moves to `process/tenants.py` as `standard_tenants(settings, supervisor_dir)`, which captures the `sq` and `cf` version labels as before. Capture never raises: a missing, failing, or silent binary is recorded as the explicit `unavailable` label (`version_label.py`). The proof therefore needs no `sq` or `cf` on `PATH` for steps 1–11, and it does not assert on the labels.
  - `amoeba start` calls it. Initiative 120 adds its Runner as `(*standard_tenants(…), runner)` in `start`.
- **H2: `record_runner_report(entry_id, verdict, detection, *, result)`.** One transaction does three things:
  - `record_verdict`'s body, with its retry rule.
  - A `runner_issued` ledger row carrying the verdict's id and node.
  - `journal_resolve(outcome=completed, resolved_by=issuer)`.

  It raises `ValueError` if the detection outcome is not `runner_issued`, and `InvalidTransitionError` if the entry is resolved, unknown, of a kind outside `REVIEW_PRODUCING_KINDS`, or in another project. It raises `ValueError` if the entry is an `sq_run` and `result` has no `run_id` (D8's ownership guarantee). In each case it writes nothing. A crash before the commit leaves the entry unresolved, which is exactly step 4's path. This closes the evidence contract's point 3, deferred "to 120 (or 110, if earlier)".
- **H3:** `store_dir` and `project_store_path` are exported from `amoeba.store`. `store-contract.md` already documents them by their internal path. Any consumer that opens a store read-only needs them.
- **H4:** `SquadronRun` and `parse_run_file` stay in `process/observers/sq_runs.py`, and the pruning rule imports them from there, so the observer and the pruning rule share one parser. They are not moved to `amoeba.upstream.squadron`, because the architecture limits that package to Squadron's review output. Reading SQ run state is already the process's job (102's `sq_run` observer).
  - `SquadronRun` gains `updated_at: datetime | None`. It is optional because the observer never needed it, and a run without it is never a pruning candidate (`age_unknown`).
  - `SquadronRun`, `parse_run_file`, and `run_pruning`'s names are not added to `amoeba.process.__all__`, so D1 and D9 do not cover them. Their only importers are the `sq_runs` observer, `run_pruning`, and `cli/prune.py`.
  - The observer's behavior is unchanged, and its existing tests pin that. A schema-v5 fixture is added, because the live directory now holds v5 files (*observed 20261015*) and the fixtures stop at v4.

**D8 — Pruning: Amoeba chooses, Squadron deletes, a human confirms.**

- *Which runs.* A run is a candidate only if **all four** of these hold:
  1. Amoeba owns it: its id is in some project's `recorded_result_run_ids`. See the ownership guarantee below.
  2. Its run file parses, with `status == paused`.
  3. No node in any project that is not `done` names it in `sq.run_id`.
  4. Its `updated_at` is at least `PRUNE_RETENTION` ago (7 days, *PM confirmed 20261020*).

  Condition 3 is stricter than "no open checkpoint block". After a human resolves a checkpoint, the node is runnable and the Runner has not yet issued `sq run --resume`. Pruning in that window would delete the run it is about to resume. "Every node that names it is done" is the earliest point at which Amoeba is provably finished with a run. Runs the PM launched fail condition 1 and are never touched.
- *The ownership guarantee.* This line is added to `process-contract.md` beside the shipped observers. `recorded_result_run_ids` returns every journal entry whose `result` carries the `run_id` key, whatever the entry's outcome or kind (`journal.py`, which reads `RESULT_KEY_RUN_ID`). Two writers put it there:
  - **Recovery**, on `adopted`. The `sq_run` observer records `run_id` in the result (process contract, "Squadron runs"). Step 4 asserts this.
  - **The issuer**, on `completed`. For an `sq_run` entry the issuer **must** include `run_id` in `result`. `record_runner_report` refuses an `sq_run` entry whose `result` lacks it, writing nothing. Initiative 120's own `journal_resolve` calls are bound by the same contract line. Steps 3 and 9 assert this. Making `journal_resolve` enforce this is deliberately out of scope, because it would change existing behavior (D7). If 120 breaks the rule, its runs are simply never pruned (D9).

  An escalated entry (`unknown`) has no result, so the run behind it is never owned. It may exist, or there may be several candidates. A human resolves the escalation, and that run is the PM's to prune with `sq runs prune`. Amoeba never prunes it, because it never proved the run was its own.
- *Re-linking.* Condition 3 reads every node's **current** `sq.run_id`, not its history. A run linked again to a new or reopened node is held for as long as that node is not `done`. `sq run --resume <id>` keeps the run's id, so a resumed run stays named by its node. A successor launched under a new journal entry gets a new id, and the old paused run becomes a candidate only once no live node names it. History is not consulted, because only a current reference can lead to a resume.
- *Unknown is a value.* An unreadable project store, an unparseable run file, or a missing `updated_at` never becomes a guess. A store that cannot be read refuses the whole command, because the held set would be incomplete. A file that cannot be parsed is logged at WARNING with its path and is never a candidate. A run with no `updated_at` is never a candidate. The preview lists only candidates, plus a count of owned paused runs that were kept.
- *Squadron deletes.* The architecture forbids any part from editing Squadron's run files directly. `--yes` runs `sq runs prune <ids…> --yes`, the command Squadron provides for this. It runs once, with non-TTY stdin (the architecture's invariant for every Squadron invocation) and `SQ_PRUNE_TIMEOUT_SECONDS`. Amoeba never unlinks a file itself, even if `sq` is missing or too old to have the command. That case leaves the candidates present, so it is reported like any other incomplete prune, with sq's message.
- *`--yes` always selects afresh.* Nothing from a preview is saved or reused. `--yes` re-reads every store and the runs directory and runs `select_prunable` again immediately before calling `sq`, and names only what that selection returns. Squadron refuses to prune a live run, which covers a resume in the remaining window. A run re-linked to a node in that window but not yet resumed is not covered, and the stores are read one project at a time, not as one snapshot. Both windows are narrow, and the failure is explicit: a later `sq run --resume <id>` fails on the missing run. `process-contract.md`'s pruning section says so, and states it as a requirement for initiative 120 (*PM confirmed 20261020*): a resume whose run is missing is a failed command, the entry resolves with that outcome, the node blocks on a human, and the run is never relaunched automatically.
- *The result is observed, not parsed.* `sq runs prune` has no JSON output, and its human text is not a contract. Its exit status is printed but never decides the outcome: `sq` exits 1 for a file someone else already removed, and that is still the goal state. Once `sq` has exited or timed out, Amoeba re-reads the runs directory. Every candidate gone is success. Any candidate still present, including one `sq` refused as live, is printed with sq's exit status and stderr, and the command exits `PRUNE_INCOMPLETE`. A timeout is the same case, said in one line; `subprocess.run`'s timeout kills `sq` and waits for it. Running the command again converges, because it selects afresh.
- *No runs-directory flag.* Squadron's runs directory is always under `Path.home()`, and Amoeba's `DEFAULT_SQ_RUNS_DIR` uses the same derivation. A `--sq-runs-dir` here would let Amoeba select from one directory while Squadron deletes from another. Tests and the walkthrough point both at a scratch directory by setting `HOME`.
- *No journal entry.* Pruning is not issued by the resident process, writes nothing to the store, and converges: every run recomputes the candidates from what is on disk, and a run that is already gone is simply absent. Command-before-result exists so that recovery can learn the outcome of a command the store depends on. No store state depends on whether a paused run's file still exists, and the store's `sq.run_id` references stay as history.
- *Preview by default.* Deleting another tool's files is not reversible, so the command mirrors `sq runs prune`: it previews unless `--yes` is given. It is never a tenant (Excluded).
- *Exit status.* `ExitCode.PRUNE_INCOMPLETE` is the next free member, 14. 109 took 13 for `SERVE_REFUSED` (*confirmed 20261019*). It means that a candidate remained, or that `sq` failed or timed out. A store that cannot be read uses the existing store-error exit mapping.

**D9 — The consumer guide.** `docs/substrate-guide.md` contains:

- one table mapping each initiative (120, 140, 160, and the notification bridge) to the surfaces and contract sections it uses. The 120 row cites D8's ownership line: the issuer of an `sq_run` must record `run_id` in `result`. Initiative 120's slice design must cite it too. If 120 omits it, the failure is safe but costly: none of its runs are owned, so none is ever pruned;
- the D4 sequence as prose, with links into `tests/contract/scenario.py`;
- the public import roots;
- a link to `store-contract.md`'s "Store locality" section, which documents the locality model that D6 proves;
- the note on intent bodies (D3);
- links to the known limits each contract already states (S8, S9, retention, issue #3, issue #5) and to this slice's `CHANGELOG.md` entry, without restating them.

### Patterns and Conventions

- Step names and crash points are each defined once, as enum members or constants, and referenced everywhere. No test spells one as a literal.
- `PRUNE_RETENTION = timedelta(days=7)` and `SQ_PRUNE_TIMEOUT_SECONDS = 30.0` are module constants in `run_pruning.py`, their only definition. The CLI exposes neither. They become settings when something needs to configure them.
- The proof harness never uses `uv run` inside a subprocess, because a temporary `HOME` would move uv's cache. It uses `sys.executable -m amoeba.cli.main`, as the existing harnesses do.
- Every wait in the proof is a readiness or change predicate with a timeout (the `host_harness` pattern), never a bare sleep.
- **The harness fails loudly, never hangs or skips.** A wait that times out fails the test with the step number and the captured stdout and stderr of every subprocess (bootstrap, `amoeba serve`). This covers a bootstrap that never reaches readiness. An exception in the `follow()` subscriber thread is stored and re-raised on the main thread at the next wait. An SSE connection that drops outside a planned kill fails the test; the follower reconnects only at the planned points.

## Implementation Details

### Migration Plan

These moves change no behavior. Each is its own commit with the suite green.

| From | To | Consumers updated |
| --- | --- | --- |
| `cli/lifecycle.build_tenants` | `process/tenants.standard_tenants` | `cli/lifecycle.start`, tests that build tenants |
| `amoeba.store.paths.store_dir` and `project_store_path` (internal path) | re-exported from `amoeba.store` (the module stays) | `store-contract.md`, and `tests/test_public_api.py`'s `EXPECTED_EXPORTS`. Existing internal callers may keep their imports |

`amoeba start` output, `amoeba status`, and recovery behavior must be identical before and after. The existing process, observer, and CLI lifecycle suites cover behavior. They do not pin the one thing the `build_tenants` move could silently change, so one check is added **before** the move and must pass unchanged after it:

- **Tenant order.** A test pins the `name` of each tenant `build_tenants` returns, in order. After H1, the same test runs against `standard_tenants`.

The move is a relocation of the same imports, so no new import rule is added.

### API Contracts

**Store (H2):**

| Method | Effect |
| --- | --- |
| `record_runner_report(entry_id, verdict: VerdictInput, detection: DetectionInput, *, result: Mapping[str, object])` | One transaction: the verdict (with the retry rule), a `runner_issued` ledger row, and the entry resolved `completed` by `issuer` with `result`. Returns the `VerdictRecord`. Refusals write nothing (D7). |

**Process (H1):** `amoeba.process.__all__` exactly as D7 lists it, pinned by a written-out expected set in the style of `tests/test_public_api.py`. `standard_tenants(settings, supervisor_dir) -> tuple[Tenant, ...]` returns the tenants `amoeba start` registers, in tick order.

**Pruning (D8):**

```
select_prunable(runs: Iterable[SquadronRun], *, owned: Mapping[str, str],
                held: Set[str], now: datetime) -> tuple[SquadronRun, ...]
```

`owned` maps a run id to its owning project. The kept count is the owned paused runs not returned.

**CLI:**

| Command | Behavior |
| --- | --- |
| `amoeba prune sq-runs` | Preview: candidates with `run_id, pipeline, updated_at, owning project`, and the count of owned paused runs kept. Exit 0. |
| `amoeba prune sq-runs --yes` | Also deletes through `sq runs prune`, then re-reads the directory and prints any candidate still present. Exit 0, or `PRUNE_INCOMPLETE`. |

## Integration Points

### Provides to Other Slices

- **Initiative 120:** the hosting contract (H1), `record_runner_report` (H2), and a proven reference sequence for the Runner's side, including both crash windows. Its slice design reads `docs/substrate-guide.md` and the process, store, and evidence contracts, and nothing under `src/`.
- **Initiative 140:** the proven Judge path: samples under one invocation, checks, and the calibration read, through the inbox, locally or over the network.
- **Initiative 160 and the notification bridge:** the proven escalation → human reply → runnable round trip, and a remote follower that survives both processes crashing.
- **Every later slice:** `tests/contract/` as a regression suite. A change that breaks the contract fails it.

### Consumes from Other Slices

- Every surface of 101–109, through their contracts only (D1).
- **If `sq` is absent,** pruning exits `PRUNE_INCOMPLETE` and deletes nothing. The suite uses a stub `sq` on `PATH` that reproduces the observed interface (D3); no test runs the real `sq`.

## Success Criteria

### Functional Requirements

- The D4 scenario completes and matches the D5 end-state declaration exactly, with no missing and no extra rows.
- Feed replay from `seq` 0 reproduces every alpha node's final status. The subscriber's `seq` list is strictly increasing with no gap across every restart (steps 4, 5, and 10).
- The network subset (D2) delivers every change once, in order, across a `kill -9` of `amoeba serve` and a `kill -9` of the resident process. Its `seq` list equals a final local `follow(after=0)`. A POST made while the resident process is down returns 202 and is applied after the restart.
- Step 3 records the verdict, the `runner_issued` row, and the resolved entry in one commit. A test that kills the process between `journal_issue` and `record_runner_report` reproduces step 4's outcome. Detection never records a runner-reported file as `ingested`.
- Step 4 ends with one verdict for the round, the entry `adopted` by recovery, and the detection row `ingested`. Step 5 ends with the entry `unknown`, one escalation message, and, after step 6, the node runnable.
- The supervisor directory holds exactly one store file per project. No project's rows, feed, or detections appear in another's (D6).
- `amoeba prune sq-runs` against the scenario's end state lists exactly alpha's checkpoint run as a candidate. Beta's run is kept and counted. `--yes` leaves only that run file gone. Pure tests of `select_prunable` cover each of D8's four conditions failing alone, a missing `updated_at`, and a resumed-but-not-done node holding its run.
- With `sq` missing, failing, timing out, or refusing a run, `--yes` exits `PRUNE_INCOMPLETE`, prints each candidate still present, and Amoeba deletes no file. An unreadable project store refuses the command before `sq` is called.

### Technical Requirements

- The D1 import rule passes.
- The tenant-order check (Migration Plan) passes before and after the move.
- `record_runner_report` refuses an `sq_run` entry whose `result` lacks `run_id`.
- The writer guard is unchanged: `cli/prune.py` opens stores read-only only.
- The `process/run_pruning.py` layering rule is an AST test.
- No test touches the real `HOME`, Squadron runs directory, CF data directory, or supervisor directory. 101's store-safety guard covers `tests/contract/`.
- `ruff`, `pyright` strict, and the full suite are clean. Files stay near 300 lines, so `scenario.py` holds data and `test_lifecycle_proof.py` holds the driver.
- The proof and the network subset run in the default suite, because they are the slice's deliverable.

### Integration Requirements

- An initiative-120 author can find, from `docs/substrate-guide.md` alone, how to host a tenant, journal and report a review, block and resolve, and follow the feed. Each item links to a contract section and a scenario step.
- Every name this slice adds to a public `__all__` (H1, H2's method, H3) appears in that package's contract doc. This is checked at review, not by a test. Auditing every existing export is deferred to issue #8.
- `process-contract.md`'s Future-work line "Pruning Squadron's paused runs — slice 110" is replaced by the pruning section. `evidence-contract.md`'s point 3 names `record_runner_report`.

### Verification Walkthrough

*Confirmed 20261020 at the end of Phase 6.* Run in **bash** from the repository root. The proof builds its own scratch directories under pytest's `tmp_path` (including a scratch `HOME` and a scratch supervisor directory) and passes each to its subprocesses explicitly, so nothing below touches the real home, the real Squadron runs directory, or the real supervisor directory. The `export` is a belt-and-braces default for any command you add yourself; the tests do not read it.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
```

1. **The proof, automated.**
   ```bash
   uv run pytest tests/contract -v
   ```
   Expected: `47 passed` in about 15 seconds. The two long tests are `test_lifecycle_proof.py::test_the_lifecycle_proof` (all twelve steps, both oracles, and step 12's pruning) and `test_network_subset.py::test_the_network_path_survives_a_kill_of_each_process`; the rest are `test_harness.py`, `test_oracle.py`, and `test_public_api_rule.py`. These cover locality (D6), `kill -9` of each process, and `Last-Event-ID` resume, so none of that is repeated by hand. On failure, the test names the step number and prints the oracle's diff, or every subprocess's captured stdout and stderr.

2. **Pruning.**
   ```bash
   uv run pytest tests/contract tests/process -k prune -v
   ```
   Expected: `19 passed, 132 deselected`. Ten are the `select_prunable` tests (`test_prune_selection.py`): each of D8's four conditions failing alone, a missing `updated_at`, a held node, and the retention boundary. Nine are the stub-`sq` tests (`test_prune_sq_runs.py`): preview never calls `sq`; success; an already-gone run counts as removed; `sq` refusing a live run, failing, timing out, or missing each exit `PRUNE_INCOMPLETE` and delete nothing; an unreadable store refuses before `sq` is called; an unparseable run file is never chosen. **Scenario step 12 is not selected by `-k prune`**: it runs inside `test_the_lifecycle_proof`, so step 1 covers it (the preview names exactly alpha's checkpoint run and reports one owned paused run kept; `--yes` with the stub `sq` leaves only that run's file gone).

3. **The guide.** Open `docs/substrate-guide.md`. Each row of the initiative table links to a contract section and a scenario step. All 60 links in the guide, files and heading anchors, were checked by script at the end of Phase 6 and resolved.

4. **The whole suite.**
   ```bash
   uv run pytest -q && uv run ruff check . && uv run pyright
   ```
   Expected at the end of Phase 6: every test passes, and `ruff` and `pyright` (strict) are clean.

Clean up with `rm -rf "$AMOEBA_STORE_DIR"`.

## Implementation Notes

### Development Approach

1. The 7-day retention default is confirmed (*20261020*). The dependency check and name reconciliation were done on 20261019; see Prerequisites.
2. Migration commits, with no behavior change. First add the tenant-order check against the current code. Then add H4's `updated_at`, make H1's `standard_tenants` move, and the exports for H1 and H3. Document each export.
3. H2, `record_runner_report`, with store tests: the one-commit property, each refusal, and the retry rule.
4. `tests/contract/` foundations: the D1 rule, the bootstrap, and `ProofRunner` with crash points.
5. The scenario and both oracles. Fix the gaps it finds under D7's rule, and record each one. A gap that needs more than an additive fix stops for the PM.
6. `test_network_subset.py`.
7. Pruning: `run_pruning.py` with pure tests, `cli/prune.py`, the exit code, the stub-`sq` tests, and step 12.
8. `docs/substrate-guide.md`, the contract deltas, and `CHANGELOG`.

Test each step right after building it, and commit after each.

### Special Considerations

- **Gaps found in step 5 are the main uncertainty in this slice's effort (3).** D7 bounds them: only additive fixes land here, and anything else goes to the PM rather than growing the slice.
- **Destructive operations.** Pruning deletes only through `sq runs prune`, only named runs, and only with `--yes`. Tests run with `HOME` pointed at `tmp_path`. 101's store-safety scan (`tests/test_store_safety.py`) is extended, not duplicated, to fail on any test that sets a runs directory or `HOME` outside `tmp_path`.
- **Secrets.** The network run uses a generated token only when it tests auth. The proof's payloads carry no credentials, consistent with 103's rule.
