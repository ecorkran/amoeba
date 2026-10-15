---
docType: slice-design
slice: contract-proof-and-hardening
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101, 102, 103, 104, 105, 106, 107, 108, 109]
interfaces: []
dateCreated: 20261015
dateUpdated: 20261015
status: not_started
---

# Slice Design: contract-proof-and-hardening

## Overview

Slices 101–109 each proved their own surface. No test yet drives the whole substrate the way its consumers will: a Runner inside the resident process, a Judge and a PM submitting from outside, subscribers following locally and over the network, and restarts. This slice adds that test, and it may use only the documented API.

The slice has four parts:

1. **The contract proof.** `tests/contract/` runs one realistic lifecycle sequence across two projects, through real processes, with crashes injected at named points. Its imports are limited, mechanically, to the names each public package exports. It runs twice, once with local transport and once over `amoeba serve`, and both runs must reach the same declared end state.
2. **Hardening.** The proof surfaces gaps. Four are already known (H1–H4 in D7): `amoeba.process` exports nothing, the Runner's one-transaction report method was deferred "to 120 (or 110, if earlier)", a documented path helper lives in an internal module, and Squadron's run-file header model lives where the pruning code cannot import it. Each gap is closed additively in this slice. A gap that needs a behavior or schema change stops for the PM.
3. **Paused-run pruning.** Squadron never prunes paused runs. `amoeba prune sq-runs` picks the paused runs Amoeba launched and has finished with, and deletes them through `sq runs prune`. It never deletes Squadron's files itself.
4. **Consumer documentation.** `docs/substrate-guide.md` is the entry point for authors of initiatives 120, 140, and 160. It maps each initiative to the surfaces it uses and walks the proven sequence.

Store locality was decided in slice 101 (central, per supervisor, keyed by project). This slice only proves that the decision holds across processes and working directories.

## Value

- **Initiative 120 can start.** The slice plan names this slice as that gate. The Runner's whole contract is exercised from outside before 120 commits to it: hosting a tenant, the journal, recovery, reporting a review it launched, blocking and resolving, and following the feed.
- **Gaps are found now.** Today a Runner author would have to import `amoeba.process.host` and `amoeba.cli.lifecycle.build_tenants`, which no contract names, and would have to write a three-step transaction by hand that 106 says must be one. These are fixed before 120 depends on them.
- **The proof is executable documentation.** `tests/contract/scenario.py` reads as the sequence a consumer follows. If a later slice breaks the contract, this suite fails.
- **Paused runs stop piling up.** The supervisor's runs directory holds 13 paused runs today (*observed 20261015*), and Squadron never removes them. Once 120 launches runs, Amoeba's paused runs would add to that count indefinitely.

## Technical Scope

### Included

- `tests/contract/`: the scenario, a proof Runner tenant, two transports, crash injection, the end-state oracle, a feed-replay oracle, the locality checks, and the public-import rule (D1–D6).
- **Hardening (D7):**
  - H1: `amoeba.process` exports its tenant-hosting contract. `build_tenants` moves out of `cli/lifecycle.py` as `standard_tenants`.
  - H2: `Store.record_runner_report`.
  - H3: `store_dir` and `project_store_path` are exported from `amoeba.store`.
  - H4: Squadron's run-file header model moves to `amoeba.upstream.squadron.run_file`.
  - Any further gap the proof finds, fixed under D7's rule.
- **Pruning (D8):** `amoeba.upstream.squadron.run_pruning` (a pure selection rule), `amoeba prune sq-runs` (preview by default, `--yes` to delete, `--json`), a new `ExitCode` member, and a schema-v5 run-file fixture.
- **Docs:** `docs/substrate-guide.md` is new. `process-contract.md` gains sections on hosting tenants and on pruning. `evidence-contract.md` and `store-contract.md` add `record_runner_report`. A test checks that every exported name is documented (D9). The Future-work lines that point at 110 are updated, and `CHANGELOG.md` is updated.
- `scripts/demo_prune.py`, which seeds the walkthrough. Like `demo_evidence.py`, it takes the instance lock while it writes, refuses while the process runs, and is named in the writer guard's allow-list.

### Excluded

- **Store retention and compaction** of journal entries, changes, verdicts, and resolved nodes. Slice 101 listed "pruning and retention" for 110. The slice plan later scoped 110 to paused Squadron runs and moved store retention to Future Work item 5, "until there is real data volume to measure". Nothing in the store is deleted here.
- **Pruning anything but paused runs Amoeba launched.** Completed and failed runs are pruned by Squadron itself (newest 10 kept per pipeline). Runs the PM launched are the PM's.
- **Automatic pruning.** Pruning is a command the PM runs, never a tenant (D8). Initiative 120 may call the selection rule later, but scheduling it is 120's decision.
- **A tenant-registration mechanism** such as plugins, entry points, or a config file. The Runner is Amoeba code. 120 composes `standard_tenants(...)` with its own tenant in `amoeba start` (H1).
- **New behavior on any existing surface.** If the proof finds a defect that needs one, the PM decides (D7).

## Dependencies

### Prerequisites

- **101–106:** merged. Their contracts are in `docs/`.
- **107, 108, and 109:** designed (all `not_started` on 20261015). This slice depends on them as their designs specify: the `check` inbox kind and judge samples (107); `link_cf_project`, `CFWatchTenant`, `--cf-data-dir`, and `cf_project_changed` (108); and `amoeba serve`, `amoeba.inspection`, `as_of_seq`, the SSE feed, and `store/discovery.py` (109). **The first task confirms all three are merged and stops for the PM if any is not.** It then checks the names this design takes from them against the merged code, and updates this design where the code differs.
- **Squadron:** `sq runs prune [run_ids…] --yes`. *Observed 20261015, Squadron 0.22.0:*
  - A named run is pruned in any category except a live run. A live run, or a name with no matching run, is reported as a refusal, and the command exits 1.
  - A file that is already gone counts as removed.
  - The runs directory is always `Path.home()/.config/squadron/runs`, with no override (`pipeline/state.py`, `_default_runs_dir`).
  - The command has no JSON output.

  These are dated observations. The design depends on the shape (named ids, `--yes`), not on the version.

### Interfaces Required

- **Inbox (103):** `submit()` for `create_project`, `intent`, `resolution`, `verdict`, `watch_reviews`, `check` (107), and `link_cf_project` (108). Also `Store.submission(id)`.
- **Store (101, 102, 104, 106, 107):**
  - Nodes: `create_node`, `update_node_status`, `update_sq_reference`, `block`, `resolve`, `runnable`, and `blocked`.
  - Journal: `journal_issue`, `journal_resolve`, `recorded_result_run_ids`, and `journal_entries`.
  - Messages: `pending_intents` and `acknowledge_message`.
  - Evidence and feed: `verdicts`, `finding_changes`, `detections`, `changes`, `checks`, and `calibration`.
- **Process (102):** `ResidentProcess`, `Tenant`, `ProcessSettings`, recovery with the `sq_run` observer, and the lock-based `amoeba stop` and `amoeba status`.
- **Feed (106):** `follow()`, `FeedSettings`, and `Change`.
- **Network (109):** `POST …/submissions`, `GET /v1/listings/{name}`, and `GET …/feed` with `Last-Event-ID`.
- **Parser (105):** `parse_review_artifact` and `to_verdict_input`. The proof Runner reports its reviews through these (evidence contract, point 5).

## Architecture

### Component Structure

```
tests/contract/
  __init__.py
  public_api.py        PUBLIC_ROOTS; the AST import rule (D1), applied to this directory
  test_public_api_rule.py
  actors.py            Transport protocol; LocalTransport, NetworkTransport (D2)
  runner_tenant.py     ProofRunner: a Tenant driven by intents, with named crash points (D3)
  bootstrap.py         starts ResidentProcess(standard_tenants(...) + ProofRunner) in a subprocess
  scenario.py          the steps, as data: actor, action, crash point, expected changes (D4)
  oracle.py            declared end state; feed-replay reconstruction (D5)
  test_lifecycle_proof.py   parametrized over the two transports
  test_locality.py     D6
  test_docs_cover_exports.py  D9
tests/fixtures/sq_runs/ + one schema-v5 paused run (sanitized from a real file)

src/amoeba/process/__init__.py    __all__ gains the hosting contract (H1)
src/amoeba/process/tenants.py     standard_tenants(settings, supervisor_dir)   (was cli/lifecycle.build_tenants)
src/amoeba/store/__init__.py      + store_dir, project_store_path (H3)
src/amoeba/store/runner_report.py record_runner_report (H2), a Store mixin
src/amoeba/upstream/squadron/
  run_file.py          SquadronRun, parse_run_file   (moved from process/observers/sq_runs.py, H4)
  run_pruning.py       PruneSettings, KeepReason, PruneSelection, select_prunable() (D8)
src/amoeba/cli/prune.py   add_prune_parser, run_prune
docs/substrate-guide.md
scripts/demo_prune.py
```

**Layering.** These rules extend `test_import_boundaries.py`:

- `run_pruning.py` and `run_file.py` import nothing from `amoeba.store`, `amoeba.inbox`, or `amoeba.process`, which keeps 105's rule for this package.
- `cli/prune.py` is the only module that knows both the selection rule and the store.
- `amoeba.process` may import `amoeba.upstream.squadron.run_file`. The process already imports the review parser in 106's detection tenant.
- Nothing under `tests/contract/` may import outside `PUBLIC_ROOTS` (D1).

### Data Flow

**The proof** (one run, one transport):

```
pytest ─┬─ bootstrap subprocess: ResidentProcess(tenants = standard_tenants(…) + ProofRunner)
        │     HOME, AMOEBA_STORE_DIR (or XDG_CONFIG_HOME), cf_data_dir: all under tmp_path
        ├─ amoeba serve subprocess                                (network transport only)
        ├─ subscriber A: follow() on a thread, or SSE via httpx   records every Change
        ├─ subscriber B: a second follower on project beta        records every Change
        └─ scenario driver, step by step:
             PM / Judge actors ── Transport.submit(kind, payload, id) ──► inbox ──► InboxTenant applies
             Runner steps      ── Transport.submit(intent{step, crash_at}) ──► ProofRunner.tick:
                                    pending_intents → do the step with the store API → acknowledge
                                    crash_at reached → os.kill(getpid(), SIGKILL)
             crash → driver waits for exit, restarts bootstrap → recovery → tenants resume
             external work ── write files: review artifact into the watched dir; projects.json by temp+rename
             after each step: wait until both subscribers reach the step's expected change kinds
end:  oracle reads every project through Store.open_read_only and compares with the declared end state
      oracle replays subscriber A's changes from seq 0 and compares node statuses with the store
      subscribers A (local) and A' (resumed after kills) hold identical seq lists: no gap, no repeat
```

**Pruning:**

```
amoeba prune sq-runs [--yes] [--json]
  for each project in discover_project_ids(store_dir()):        read-only opens; any failure → refuse, delete nothing
      owned |= recorded_result_run_ids(p)            run ids Amoeba's journal adopted or completed
      held  |= {n.sq.run_id for n in nodes_for_project(p) if n.status != DONE and n.sq.run_id}
  runs = parse_run_file(f) for f in DEFAULT_SQ_RUNS_DIR/*.json   (unparseable → recorded, never a candidate)
  selection = select_prunable(runs, owned, held, now, settings)   pure
  print candidates and the owned paused runs kept, each with its KeepReason
  --yes and candidates:
      sq runs prune <ids…> --yes        stdin=DEVNULL, timeout=settings.sq_timeout_seconds
      re-parse the runs dir: each candidate absent → pruned, present → not_pruned (with sq's exit status and stderr)
  exit OK if every candidate was pruned (or there were none); else ExitCode.PRUNE_INCOMPLETE
```

### State Management

This slice adds no store state, no table, and no migration. `record_runner_report` writes existing tables. Pruning writes nothing to the store, and its only effect is the files `sq runs prune` deletes. The proof's state lives entirely under `tmp_path`: the supervisor directory, a fake `HOME` (Squadron runs directory), a CF data directory, and per-project reviews directories.

## Technical Decisions

### Technology Choices

No new dependency. The proof uses `httpx`, which slice 109 adds as a dev dependency, and the subprocess and signal machinery the existing harnesses already use. Nothing in it is mocked: signals, locks, SQLite, the inbox directory, and the HTTP server are all real. The only stand-in is the Squadron side effect, explained in D3.

### Decisions

**D1 — Public means exported, and the proof's imports are checked.** `PUBLIC_ROOTS` lists the library surfaces a consumer may import:

- `amoeba.store`, `amoeba.inbox`, `amoeba.feed`, `amoeba.process`;
- `amoeba.upstream.squadron` and `amoeba.upstream.context_forge` (108);
- `amoeba.inspection` (109).

The CLI and HTTP are the other public surfaces, reached only by subprocess and by HTTP. An AST test fails if any module in `tests/contract/` imports a submodule of a root (`amoeba.store.paths`, for example), imports a name not in the root's `__all__`, or imports any `amoeba` module not in `PUBLIC_ROOTS`. This turns "no internal access" from a claim into a property the suite checks.

**D2 — One scenario, two transports, one end state.** `Transport` is a protocol with three members: `submit(project_id, kind, payload, submission_id, submitted_by)`, `outcome(project_id, submission_id)`, and `subscribe(project_id, after) -> Iterator[Change-shaped dict]`.

- `LocalTransport` uses `amoeba.inbox.submit`, `Store.submission`, and `follow()`.
- `NetworkTransport` uses 109's endpoints: POST with a mandatory id, then the outcome GET, then SSE with `Last-Event-ID` on reconnect. It converts each frame back through the same `change_record` shape.

The Runner always acts in-process through the store API. That is its documented position, so it has no transport. The oracle always reads through `Store.open_read_only`. The network run additionally checks one listing per step against `amoeba inspect --json`. Both runs must produce the same end state, which is the point of 109 being a dependency.

**D3 — The proof Runner is a real tenant driven by `intent` messages.** `ProofRunner` implements `Tenant` and nothing more. Each tick it reads `pending_intents`, performs one step, and acknowledges the intent. The intent body names the step and an optional `crash_at` point:

- `build_tree` creates initiative → slice (`cf.slice_name` set, so 106's attribution rule finds it) → gate.
- `launch_review` journals an `sq_run`, then performs the stand-in side effect. It writes a run file into the fake `HOME`'s runs directory, taken from a fixture with its `run_id`, `pipeline`, `params`, and `started_at` set to match, plus a review artifact from `tests/fixtures/sq_reviews/` into the project's watched directory. It then reports with `record_runner_report` (H2), parsing the artifact through 105's parser.
- `checkpoint` journals an `sq_run`, writes a paused run file, resolves the entry `completed` with the `run_id`, sets `sq.run_id`, and blocks the node on `sq_checkpoint`.
- `finish` marks the slice and gate `done`.

*Why a stand-in, not real `sq`.* The proof is about Amoeba's contract. A real `sq review` needs a model provider, costs money, and is not deterministic. The stand-in produces exactly what the observers and detection read (a run file and a review file), in the shapes the 102 and 105 fixtures pin. The real `sq` is exercised only by the pruning walkthrough and an opt-in test (D8).

Crash points are named constants in `runner_tenant.py`:

- `AFTER_JOURNAL`: after `journal_issue` commits, before any side effect.
- `AFTER_SIDE_EFFECT`: after the run file and artifact are written, before the report.

At a crash point the tenant sends itself `SIGKILL`. Nothing is caught, flushed, or cleaned up.

**D4 — The scenario.** It runs in this order on project `alpha`, interleaved with a smaller sequence on project `beta`. The table states, for each step, what the store must show afterward. The exact expected changes are in `scenario.py`.

| # | Actor and action | Proves |
| --- | --- | --- |
| 1 | PM: `create_project` alpha and beta; `watch_reviews` for each; `link_cf_project` alpha | Runtime project creation (103); per-project reviews directories; CF link (108) |
| 2 | Runner: `build_tree` on both projects | Node writes; `node_created` on each project's own feed only |
| 3 | Runner: `launch_review` | Command-before-result; `record_runner_report` writes the verdict, the `runner_issued` ledger row, and the `completed` entry in one commit; detection does not ingest the file again |
| 4 | Runner: `launch_review` with `crash_at=AFTER_SIDE_EFFECT`; restart | Recovery adopts the run (exactly one match). Detection then ingests the artifact as `ingested`, with the same record id the Runner would have used (evidence contract, point 5). One verdict for the round, not two |
| 5 | Runner: `launch_review` with `crash_at=AFTER_JOURNAL`; restart | Zero matches: entry `unknown`, node `blocked_on_human`, an escalation message on the feed |
| 6 | PM: `resolution` for that node | The human reply flips the node runnable (103) |
| 7 | External: a PM-launched review artifact is written into alpha's directory | Detection ingests it with correct provenance; `finding_changes` compares it with step 4's round |
| 8 | Judge: two `verdict` submissions with one `judge_invocation_id`; one `check` with `examined_count = 0` | Samples recorded individually; calibration readable; a vacuous check is labelled vacuous (107) |
| 9 | External: projects.json rewritten by temp+rename, moving alpha's slice pointer | One `cf_project_changed` snapshot naming the field (108) |
| 10 | Runner: `checkpoint` on alpha and on beta | `blocked_on_sq_checkpoint` holding the run id |
| 11 | Stop the resident process gracefully. While it is down: PM submits a `resolution` for alpha's checkpoint, and projects.json changes again. Start | Submissions while down are applied on start; the CF change made during down-time is recorded on the first check |
| 12 | Network run only: `kill -9` of `amoeba serve` while subscriber A is streaming; restart it; A reconnects with `Last-Event-ID` | No gap, no repeat across a server crash |
| 13 | Network run only: `kill -9` of the resident process while A is streaming; restart it | The stream stays open and idles, then resumes delivery (109 D7) |
| 14 | Runner: `finish` on alpha | Final statuses; beta's checkpoint stays open |
| 15 | PM: `amoeba prune sq-runs` (preview), then `--yes` with a stub `sq` on `PATH` | Selects only alpha's checkpoint run. Beta's run is held (its node is not `done`), and step 7's PM-launched run is not owned |

The scenario uses `kill -9` (steps 4, 5, 12, 13) and a graceful stop (step 11). Both are restart paths the process contract promises.

**D5 — Two oracles.**

- *End state.* `oracle.py` declares, per project: node statuses; blocked states and their resolutions; journal entries by outcome (`completed`, `adopted`, `unknown`, and resolvers); verdicts with their trust labels and `judge_invocation_id`; detection-ledger outcomes by path; checks; CF snapshot count and changed fields; message channels and acknowledgment state; and the submission outcomes. The oracle compares the store with this declaration through the public read API. A missing or extra row fails the test.
- *Feed replay.* Replaying subscriber A's changes from `seq` 0 (`node_created` sets a status and `node_status_changed` moves it) must reproduce every node's final status. A's `seq` list must be strictly increasing with no gaps, across every restart and reconnect. In the network run, A's list must equal a fresh local `follow(after=0)` read at the end. This proves the feed is complete enough to rebuild state, which is what 106 promised subscribers.

**D6 — Locality is proven across processes and directories, not reimplemented.** `test_locality.py` has three checks:

- Every subprocess (bootstrap, `amoeba submit`, `amoeba inspect`, and `amoeba serve`) is started with its own working directory: two different temporary "repositories". All of them resolve the same supervisor directory, and every project's store is exactly `{dir}/{project_id}.sqlite3`.
- With `AMOEBA_STORE_DIR` unset and `XDG_CONFIG_HOME` set to a temporary path, the same is true under `$XDG_CONFIG_HOME/amoeba`. No test ever leaves both unset, so the real home directory is never touched. `HOME` is always a temporary path too.
- Project keying holds end to end. alpha's reviews directory never produces a beta row. Each project's feed carries only its own changes. alpha's oracle sees nothing of beta's.

**D7 — Hardening: additive fixes only, everything else to the PM.** A gap is any symbol, method, or document a consumer would need that the public surface lacks. A gap is fixed in this slice when the fix is additive: an export, a document section, a new method composed from existing transactions, or a move with no behavior change. A gap whose fix changes existing behavior, a schema, or a recorded value is written up and **stops for the PM**. Every gap, whichever way it went, is listed in `CHANGELOG.md` and in the substrate guide's "Hardened in 110" section. The four known gaps:

- **H1: `amoeba.process` exports nothing.** The process contract says it is "sufficient for building a tenant". Building one today means importing `amoeba.process.host`, and composing with the shipped tenants means importing `amoeba.cli.lifecycle.build_tenants`. The fix:
  - `__all__` gains `ResidentProcess`, `Tenant`, `ProcessSettings`, `Observer`, `Observation`, `Adopt`, `NotApplied`, `Unknown`, `standard_tenants`, and the process errors that `start` maps to exit codes.
  - `build_tenants` moves to `process/tenants.py` as `standard_tenants(settings, supervisor_dir)`, which captures the `sq` and `cf` version labels as before.
  - `amoeba start` calls it. Initiative 120 adds its Runner as `(*standard_tenants(…), runner)` in `start`.
- **H2: `record_runner_report(entry_id, verdict, detection, *, result)`.** One transaction does three things:
  - `record_verdict`'s body, with its retry rule.
  - A `runner_issued` ledger row carrying the verdict's id and node.
  - `journal_resolve(outcome=completed, resolved_by=issuer)`.

  It raises `ValueError` if the detection outcome is not `runner_issued`, and `InvalidTransitionError` if the entry is resolved, unknown, of a kind outside `REVIEW_PRODUCING_KINDS`, or in another project. In each case it writes nothing. A crash before the commit leaves the entry unresolved, which is exactly step 4's path. This closes the evidence contract's point 3, deferred "to 120 (or 110, if earlier)".
- **H3:** `store_dir` and `project_store_path` are exported from `amoeba.store`. `store-contract.md` already documents them by their internal path. Any consumer that opens a store read-only needs them.
- **H4:** `SquadronRun` and `parse_run_file` move from `process/observers/sq_runs.py` to `amoeba.upstream.squadron.run_file`, so the observer and the pruning rule share one parser.
  - `SquadronRun` gains `updated_at: datetime | None`. It is optional because the observer never needed it, and a run without it is never a pruning candidate (`age_unknown`).
  - The observer's behavior and tests are unchanged. A schema-v5 fixture is added, because the live directory now holds v5 files (*observed 20261015*) and the fixtures stop at v4.

**D8 — Pruning: Amoeba chooses, Squadron deletes, a human confirms.**

- *Which runs.* A run is a candidate only if **all four** of these hold:
  1. Amoeba owns it: its id is in some project's `recorded_result_run_ids`, so Amoeba's journal adopted or completed it.
  2. Its run file parses, with `status == paused`.
  3. No node in any project that is not `done` names it in `sq.run_id`.
  4. Its `updated_at` is at least `PruneSettings.retention` ago (default 7 days, *pending PM confirmation*).

  Condition 3 is stricter than "no open checkpoint block". After a human resolves a checkpoint, the node is runnable and the Runner has not yet issued `sq run --resume`. Pruning in that window would delete the run it is about to resume. "Every node that names it is done" is the earliest point at which Amoeba is provably finished with a run. Runs the PM launched fail condition 1 and are never touched, and neither is a zero-match escalation's run, whatever it turns out to be.
- *Unknown is a value.* An unreadable project store, an unparseable run file, or a missing `updated_at` never becomes a guess. A store that cannot be read refuses the whole command, because the held set would be incomplete. A file that cannot be parsed, or a run with no `updated_at`, is kept and listed with its `KeepReason`: `not_paused`, `held_by_node`, `too_recent`, `age_unknown`, or `unreadable`. `KeepReason` is a closed `StrEnum`. Unowned runs are counted but not listed.
- *Squadron deletes.* The architecture forbids any part from editing Squadron's run files directly. `--yes` runs `sq runs prune <ids…> --yes`, the command Squadron provides for this. It runs once, with non-TTY stdin (the architecture's invariant for every Squadron invocation) and `PruneSettings.sq_timeout_seconds`. Amoeba never unlinks a file itself, even if `sq` is missing or too old to have the command. That case is reported as `not_pruned`, with sq's message.
- *The result is observed, not parsed.* `sq runs prune` has no JSON output, and its human text is not a contract. After the call, Amoeba re-reads the runs directory. A candidate whose file is gone was pruned, and one whose file remains was not. This is the same reconcile-by-observation rule recovery uses. A run that was resumed between the preview and `--yes` is live, so Squadron refuses it, and it is reported as `not_pruned`.
- *No runs-directory flag.* Squadron's runs directory is always under `Path.home()`, and Amoeba's `DEFAULT_SQ_RUNS_DIR` uses the same derivation. A `--sq-runs-dir` here would let Amoeba select from one directory while Squadron deletes from another. Tests and the walkthrough point both at a scratch directory by setting `HOME`.
- *No journal entry.* Pruning is not issued by the resident process, writes nothing to the store, and converges: every run recomputes the candidates from what is on disk, and a run that is already gone is simply absent. Command-before-result exists so that recovery can learn the outcome of a command the store depends on. No store state depends on whether a paused run's file still exists, and the store's `sq.run_id` references stay as history.
- *Preview by default.* Deleting another tool's files is not reversible, so the command mirrors `sq runs prune`: it previews unless `--yes` is given. It is never a tenant (Excluded).
- *Exit status.* `ExitCode.PRUNE_INCOMPLETE` is the next free member: 14 if 109 takes 13 as designed, confirmed after 109 merges. It means that a candidate remained, or that `sq` failed or timed out. A store that cannot be read uses the existing store-error exit mapping.

**D9 — Documentation is checked, not only written.** `docs/substrate-guide.md` contains:

- one table mapping each initiative (120, 140, 160, and the notification bridge) to the surfaces and contract sections it uses;
- the D4 sequence as prose, with links into `tests/contract/scenario.py`;
- the public import roots;
- the known limits collected from every contract: S8, S9, retention, the multi-part series (issue #3), and the progress-record reader (issue #5);
- "Hardened in 110".

`test_docs_cover_exports.py` asserts that every name in every `PUBLIC_ROOTS` `__all__` appears in backticks in at least one `docs/*.md`. Exporting without documenting fails the suite.

### Patterns and Conventions

- Step names, crash points, `KeepReason`, and transport names are each defined once, as enum members or constants, and referenced everywhere. No test spells one as a literal.
- `PruneSettings` is a frozen dataclass and the only home of its defaults: `retention = timedelta(days=7)` and `sq_timeout_seconds = 30.0`. The CLI exposes `--older-than-days` and nothing else.
- The proof harness never uses `uv run` inside a subprocess, because a temporary `HOME` would move uv's cache. It uses `sys.executable -m amoeba.cli.main`, as the existing harnesses do.
- Every wait in the proof is a readiness or change predicate with a timeout (the `host_harness` pattern), never a bare sleep.

## Implementation Details

### Migration Plan

These moves change no behavior. Each is its own commit with the suite green.

| From | To | Consumers updated |
| --- | --- | --- |
| `cli/lifecycle.build_tenants` | `process/tenants.standard_tenants` | `cli/lifecycle.start`, tests that build tenants |
| `process/observers/sq_runs.py`: `SquadronRun`, `parse_run_file` | `upstream/squadron/run_file.py` | `observers/sq_runs.py`, `tests/test_observer_sq_runs.py` |
| `amoeba.store.paths.store_dir` and `project_store_path` (internal path) | re-exported from `amoeba.store` (the module stays) | `store-contract.md`. Existing internal callers may keep their imports |

`amoeba start` output, `amoeba status`, and recovery behavior must be identical before and after. The existing process, observer, and CLI lifecycle suites are the proof.

### API Contracts

**Store (H2):**

| Method | Effect |
| --- | --- |
| `record_runner_report(entry_id, verdict: VerdictInput, detection: DetectionInput, *, result: Mapping[str, object])` | One transaction: the verdict (with the retry rule), a `runner_issued` ledger row, and the entry resolved `completed` by `issuer` with `result`. Returns the `VerdictRecord`. Refusals write nothing (D7). |

**Process (H1):** `amoeba.process.__all__` exactly as D7 lists it. `standard_tenants(settings, supervisor_dir) -> tuple[Tenant, ...]` returns the tenants `amoeba start` registers, in tick order.

**Pruning (D8):**

```
select_prunable(runs: Iterable[SquadronRun | UnreadableRun], *, owned: Mapping[str, str],
                held: Set[str], now: datetime, settings: PruneSettings) -> PruneSelection
PruneSelection: candidates: tuple[SquadronRun, ...]; kept: tuple[tuple[str, KeepReason], ...]; unowned_count: int
```

**CLI:**

| Command | Behavior |
| --- | --- |
| `amoeba prune sq-runs` | Preview: candidates with `run_id, pipeline, updated_at, owning project and node`; kept owned runs with `KeepReason`; unowned count. Exit 0. |
| `amoeba prune sq-runs --yes` | Also deletes through `sq runs prune`, then reports `pruned` and `not_pruned` by observation. Exit 0, or `PRUNE_INCOMPLETE`. |
| `--json` | The same report as one JSON object. |
| `--older-than-days N` | Overrides `PruneSettings.retention` for this invocation. |

## Integration Points

### Provides to Other Slices

- **Initiative 120:** the hosting contract (H1), `record_runner_report` (H2), and a proven reference sequence for the Runner's side, including both crash windows. Its slice design reads `docs/substrate-guide.md` and the process, store, and evidence contracts, and nothing under `src/`.
- **Initiative 140:** the proven Judge path: samples under one invocation, checks, and the calibration read, through the inbox, locally or over the network.
- **Initiative 160 and the notification bridge:** the proven escalation → human reply → runnable round trip, and a remote follower that survives both processes crashing.
- **Every later slice:** `tests/contract/` as a regression suite. A change that breaks the contract fails it.

### Consumes from Other Slices

- Every surface of 101–109, through their contracts only (D1).
- **If 107, 108, or 109 is not merged,** the first task stops. Proving a partial contract would not prove what the slice plan asks, so the slice does not degrade to that.
- **If `sq` is absent,** pruning reports `not_pruned` and deletes nothing. The suite uses a stub `sq` on `PATH`. One opt-in test runs the real `sq runs prune` under a temporary `HOME`, and is skipped when `sq` is not on `PATH`.

## Success Criteria

### Functional Requirements

- The D4 scenario completes under both transports. Each run matches the D5 end-state declaration exactly, with no missing and no extra rows, and the two runs' end states are equal.
- Feed replay from `seq` 0 reproduces every node's final status. Subscriber A's `seq` list is strictly increasing with no gap across every restart (steps 4, 5, 11, and 13) and the server crash (step 12). In the network run it equals a final local `follow(after=0)`.
- Step 3 records the verdict, the `runner_issued` row, and the resolved entry in one commit. A test that kills the process between `journal_issue` and `record_runner_report` reproduces step 4's outcome. Detection never records a runner-reported file as `ingested`.
- Step 4 ends with one verdict for the round, the entry `adopted` by recovery, and the detection row `ingested`. Step 5 ends with the entry `unknown`, one escalation message, and, after step 6, the node runnable.
- Every subprocess, started from two different working directories, resolves the same supervisor directory, under both `AMOEBA_STORE_DIR` and `XDG_CONFIG_HOME`. No project's rows, feed, or detections appear in another's.
- `amoeba prune sq-runs` against the scenario's end state lists exactly alpha's checkpoint run as a candidate. Beta's run is kept `held_by_node`, and the unowned runs are counted. `--yes` leaves only that run file gone. Pure tests of `select_prunable` cover each `KeepReason`, and they cover a resumed-but-not-done node holding its run.
- With `sq` missing, failing, timing out, or refusing a run, `--yes` exits `PRUNE_INCOMPLETE`, names each run `not_pruned`, and Amoeba deletes no file. An unreadable project store refuses the command before `sq` is called.

### Technical Requirements

- The D1 import rule passes, and it fails a deliberately bad fixture module (a submodule import, a non-exported name).
- `test_docs_cover_exports.py` passes.
- The writer guard is unchanged: `cli/prune.py` opens stores read-only only.
- The `run_pruning.py` layering rule is an AST test.
- No test touches the real `HOME`, Squadron runs directory, CF data directory, or supervisor directory. 101's store-safety guard covers `tests/contract/`.
- `ruff`, `pyright` strict, and the full suite are clean. Files stay near 300 lines, so `scenario.py` holds data and `test_lifecycle_proof.py` holds the driver.
- The proof runs in the default suite (it is the slice's deliverable) and completes in under 2 minutes on the development machine. If it does not, the network run moves to the load tier, and the local run stays in the default suite.

### Integration Requirements

- An initiative-120 author can find, from `docs/substrate-guide.md` alone, how to host a tenant, journal and report a review, block and resolve, and follow the feed. Each item links to a contract section and a scenario step.
- `process-contract.md`'s Future-work line "Pruning Squadron's paused runs — slice 110" is replaced by the pruning section. `evidence-contract.md`'s point 3 names `record_runner_report`.

### Verification Walkthrough

*Draft, to be confirmed at the end of Phase 6.* Run in **bash** from the repository root. Every path is a scratch directory, and `HOME` is overridden only for the commands that need it.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
FAKE_HOME="$(mktemp -d)"
```

1. **The proof, automated.**
   ```bash
   uv run pytest tests/contract -v
   ```
   `test_lifecycle_proof.py[local]` and `[network]` pass, as do `test_locality.py`, `test_public_api_rule.py`, and `test_docs_cover_exports.py`. On failure, the test prints the step number and the oracle's diff.

2. **Locality by hand.** Create a project and seed a node, then list projects from another working directory:
   ```bash
   uv run amoeba submit create-project --project demo --by pm
   uv run amoeba start &                                  # terminal 1; applies the creation
   uv run amoeba stop
   NODE=$(uv run python scripts/demo_evidence.py)         # seeds one node; the process must be stopped
   (cd /tmp && "$OLDPWD/.venv/bin/amoeba" inspect projects)
   ls "$AMOEBA_STORE_DIR"
   ```
   The listing from `/tmp` shows `demo`, and the directory holds `demo.sqlite3`.

3. **A restart loses nothing, and the feed resumes.**
   ```bash
   uv run amoeba start &                                  # terminal 1
   uv run amoeba serve &                                  # terminal 2
   curl -sN http://127.0.0.1:8765/v1/projects/demo/feed   # terminal 3; note the last id: printed as LAST, then Ctrl-C
   kill -9 "$(pgrep -f 'amoeba.* start')"                 # the resident process, not the server
   uv run amoeba submit intent --project demo --by pm --node-id "$NODE" --body '{"ask":"status"}'
   uv run amoeba start &
   curl -sN http://127.0.0.1:8765/v1/projects/demo/feed -H "Last-Event-ID: $LAST"
   ```
   The resumed stream prints one `message_posted` change for the intent, and no id at or below `LAST`. `uv run amoeba inspect journal --project demo` shows nothing unresolved.

4. **Pruning: preview, then delete through real `sq`.** Stop the process first (`uv run amoeba stop`). The seed script writes the store directly, so like `demo_evidence.py` it takes the instance lock and refuses while the process runs.
   ```bash
   HOME="$FAKE_HOME" .venv/bin/python scripts/demo_prune.py
   ls "$FAKE_HOME/.config/squadron/runs"
   HOME="$FAKE_HOME" .venv/bin/amoeba prune sq-runs
   HOME="$FAKE_HOME" .venv/bin/amoeba prune sq-runs --yes; echo $?
   ls "$FAKE_HOME/.config/squadron/runs"
   ```
   The seed uses the `demo` project and prints the three run ids it writes. All three runs are paused and older than 7 days:
   - R1 is owned, and its node is `done`.
   - R2 is owned, and its node is blocked on `sq_checkpoint`.
   - R3 is not owned.

   The preview lists R1 as the candidate, R2 as `held_by_node`, and `unowned: 1`. `--yes` exits 0, and afterwards only R2's and R3's files remain. `.venv/bin/…` is used instead of `uv run` because a temporary `HOME` moves uv's cache.

5. **Refusals.** Remove `sq` from `PATH` and repeat step 4's `--yes` with a newly seeded candidate. It exits 14 (`PRUNE_INCOMPLETE`), reports `not_pruned`, and the file is still there.

6. **The guide.** Open `docs/substrate-guide.md`. Each row of the initiative table links to a contract section and a scenario step.

Clean up with `uv run amoeba stop`, kill the server, then `rm -rf "$AMOEBA_STORE_DIR" "$FAKE_HOME"`.

## Implementation Notes

### Development Approach

1. Confirm that 107, 108, and 109 are merged. Stop for the PM if any is not. Reconcile every name this design takes from them against the merged code, and update this design if they differ.
2. Migration commits, with no behavior change: H4's move, H1's `standard_tenants` move, and the exports for H1 and H3. Then `test_docs_cover_exports.py`, which will fail until each export is documented. Document them.
3. H2, `record_runner_report`, with store tests: the one-commit property, each refusal, and the retry rule.
4. `tests/contract/` foundations: the D1 rule and its negative fixture, the bootstrap, `ProofRunner` with crash points, and `LocalTransport`.
5. The scenario and both oracles, local transport. Fix the gaps it finds under D7's rule. Record each one.
6. `NetworkTransport` and steps 12–13.
7. `test_locality.py`.
8. Pruning: `run_pruning.py` with pure tests, `cli/prune.py`, the exit code, the stub-`sq` tests, the opt-in real-`sq` test, step 15, and `scripts/demo_prune.py`.
9. `docs/substrate-guide.md`, the contract deltas, and `CHANGELOG`.

Test each step right after building it, and commit after each.

### Special Considerations

- **Gaps found in step 5 are the main uncertainty in this slice's effort (3).** D7 bounds them: additive fixes stay in scope, and anything else goes to the PM rather than growing the slice.
- **Destructive operations.** Pruning deletes only through `sq runs prune`, only named runs, and only with `--yes`. Tests run with `HOME` pointed at `tmp_path`. A guard test asserts that no test under `tests/` sets a runs directory outside `tmp_path`, extending 101's store-safety scan to the new `HOME` override.
- **Secrets.** The network run uses a generated token only when it tests auth. The proof's payloads carry no credentials, consistent with 103's rule.
