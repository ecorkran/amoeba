---
docType: slice-design
slice: run-identity-and-supported-run-surfaces
project: amoeba
parent: user/architecture/120-slices.runner-routing-engine.md
dependencies: []
interfaces:
- 122
- 125
dateCreated: 20261020
dateUpdated: 20261021
status: not_started
turns: 32
promptTokens: 2415436
cachedTokens: 2292294
cacheWriteTokens: 123086
completionTokens: 35458
durationSeconds: 357.6
costUsd: 2.152862
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Run Identity and Supported Run Surfaces

## Overview

This slice moves 100's Squadron handling onto the surfaces Squadron supports. Today two parts of 100 read Squadron's run-state files under `~/.config/squadron/runs/`, which Squadron calls internal: the recovery observer for `sq_run` entries, which matches a journaled command against those files by attributes, and `amoeba prune sq-runs`, which picks paused runs from them.

After this slice:

- Every new `sq_run` journal entry carries the run id its issuer minted, as a required parameter key.
- Recovery finds that run by id through `sq runs wait <id> --timeout 0 --json` (S10). It adopts the run when it has a state, and marks the entry `not_applied` when no state exists after the launch grace period.
- Pruning decides from the same outcome document.
- Attribute matching against the runs directory remains only for entries journaled without an id, which are entries written before this slice.

The slice changes 100's side only. It adds no Runner code, but it gives 122 and 125 the single reader of Squadron's outcome document that they will poll with.

## Value

Architectural enablement.

- **Recovery becomes exact.** An entry's run is found by id. It is no longer chosen from candidates by pipeline, params and start time, which escalates on any ambiguity.
- **Amoeba stops depending on a file Squadron may change.** Once this slice lands, an upstream change to the run-state format cannot break recovery or pruning of id-bearing runs.
- **The Runner has one outcome reader.** 122 polls in-flight runs and 125 ingests outcomes through the reader this slice adds. Neither writes its own parser.

## Technical Scope

**Included**

- `run_id` added to `REQUIRED_PARAMETER_KEYS[CommandKind.SQ_RUN]`.
- A Squadron outcome reader (`process/sq_outcome.py`). It runs `sq runs wait <id> --timeout 0 --json` once, checks the document against the exit code, and returns a typed document or a poll failure.
- A by-id recovery observer (`observers/sq_run_id.py`), including the launch grace rule (D4).
- A dispatching `sq_run` observer. An entry with a run id goes to the by-id observer. An entry without one goes to the existing attribute matcher, and the runs directory is scanned only when such an entry exists.
- Pruning (`run_pruning.py`, `cli/prune.py`) rewritten over outcome documents. Selection reads no run-state file, and neither does the check after `sq runs prune`.
- A new setting, `launch_grace_seconds`, with a `--launch-grace` start flag. 122 also consumes it.
- Updates to every consumer: the contract suite's stand-in Runner and `sq` stub, the tests that journal `sq_run`, and the contract documents. `scripts/demo_journal.py` is retired (see Migration Plan).
- Tests proving that recovery of id-bearing entries and all of pruning make no run-state file reads.

**Excluded**

- Minting run ids, launching runs, launch logs and the `run_id=<id>` line check, and per-tick polling. These belong to 122. Reissuing a `not_applied` entry, with its launch-log check, belongs to 125 (125, D9, issue #9). This slice records the rule in the contract (D4).
- Ingesting reviews, checkpoints or failures from the outcome document. This belongs to 125. The reader models only the fields this slice uses, and 125 extends it (D2).
- Every other 100 contract change (`done` terminal, acknowledgment outcomes, project-scoped escalation, new tables). These belong to 121.
- Schema migrations. Journal parameters are stored as JSON, so the new key needs none.

## Dependencies

### Prerequisites

- Initiative 100 complete (slices 101–110), including the recovery protocol, the `sq_run` journal kind, and `amoeba prune sq-runs`.
- squadron-ai 0.23.5 or later on `PATH` as `sq`. This slice relies on its shapes, not its version number: `sq runs wait <id> --timeout 0 --json` (S10) and a caller-chosen run id (S9, used by 122).

### Interfaces Required

- **`sq runs wait <id> --timeout 0 --json`** (Squadron `pipeline/run_wait.py`, `pipeline/run_outcome.py`, documented in `docs/COMMANDS.md`):
  - Exit codes: 0 completed, 1 failed, 3 paused, 4 timed_out (with `--timeout 0`, this means still running), 5 not_found, 6 unreadable, 7 unknown_status, 8 orphaned. Usage errors exit 2.
  - The document always has `run_id` and `outcome`, and `outcome` maps one-to-one to the exit code. Whenever a run state was read, it also has `status`, `pipeline`, `started_at`, `updated_at`, `checkpoint`, `failure` and `reviews`. For not_found and unreadable, only `run_id` and `outcome` are present.
  - `checkpoint.paused_at` is present for a paused run. A null always means unknown, and keys may be added later.
- **100's store API**: `unresolved_journal_entries`, `journal_resolve`, `journal_escalate`, `recorded_result_run_ids`, `nodes_for_project`, and `Store.open_read_only`. None of these change.

## Architecture

### Component Structure

```
amoeba/process/
  sq_outcome.py       NEW   RunOutcome enum + exit-code map, RunOutcomeDocument,
                            poll_run() → RunPoll = RunOutcomeDocument | PollFailure
  observers/
    sq_run_id.py      NEW   SquadronRunIdObserver (by id, launch grace);
                            SquadronRunObserver: id present → by-id, absent → matcher
    sq_runs.py        KEPT  attribute matcher, now legacy-only; lazy scan
  run_pruning.py      CHANGED  select_prunable over RunOutcomeDocument
  supervisor.py       CHANGED  registry builds the dispatcher; no eager scan
  settings.py         CHANGED  + launch_grace_seconds
amoeba/store/
  journal_models.py   CHANGED  sq_run required keys + run_id; PARAM_RUN_ID constant
amoeba/cli/
  prune.py            CHANGED  polls owned ids; verifies by polling
  settings_flags.py   CHANGED  + --launch-grace; --sq-runs-dir help says legacy-only
```

`sq_outcome.py` is the only module that runs `sq runs wait` or parses its output. Recovery, pruning, and later 122 and 125 all call `poll_run`, so it sits in `amoeba/process/` beside its callers rather than under `observers/`, which holds recovery observers only.

### Data Flow

**Recovery of an `sq_run` entry (at start, before any tenant ticks):**

```
reconcile(store, project, registry)
  └─ SquadronRunObserver.observe(entry)
       ├─ "run_id" in entry.parameters ──► SquadronRunIdObserver
       │     poll_run(run_id) ── sq runs wait <id> --timeout 0 --json
       │       ├─ state exists (completed|failed|paused|timed_out|
       │       │   unknown_status|orphaned) ──────────────► Adopt{run_id, outcome, status}
       │       ├─ not_found
       │       │    ├─ issued_at null ─────────────────────► Unknown(reason)
       │       │    ├─ now < issued_at + grace ── sleep (capped at grace), poll once more
       │       │    │     (state now exists → Adopt; still not_found → continue below)
       │       │    └─ grace passed ──────────────────────► NotApplied("no run state after grace")
       │       └─ unreadable | PollFailure ───────────────► Unknown(reason)
       └─ no "run_id" key ──► SquadronRunsObserver (unchanged matcher; first use scans dir)
```

**Pruning (`amoeba prune sq-runs`):**

```
for each project store (read-only): owned ← recorded_result_run_ids; held ← run ids on non-done nodes
for each owned id: poll_run(id)  → documents (failures named on stderr, never chosen)
select_prunable(documents, owned, held, now)          → candidates (pure)
preview; with --yes: sq runs prune <ids…> --yes once
for each candidate: poll_run(id); not_found = removed, anything else = still present
```

### State Management

The slice adds no store state.

- The run id lives in the journal entry's `parameters`, which are already JSON.
- An adoption records `run_id`, `outcome` and `status` in the entry's `result`. Because `recorded_result_run_ids` reads `result["run_id"]`, the ownership rule for pruning is unchanged.

## Technical Decisions

### D1 — The run id is a required `sq_run` parameter key
Status: decided
- `REQUIRED_PARAMETER_KEYS[SQ_RUN]` becomes `{"pipeline", "params", "run_id"}`. The key is defined once as `PARAM_RUN_ID` in `journal_models.py`. `journal_issue` refuses an `sq_run` without it, as it does for the other keys today. A new id-less entry cannot be created, so "journaled without an id" means only rows written before this slice.
- `journal_issue` checks only that the key is present, as it does for every other key. The by-id observer treats a present value that is not a non-empty string as `Unknown`, with the reason naming the bad value. The format is Squadron's rule (letters, digits, `.`, `_`, `-`, first character a letter or digit, at most 128). Squadron enforces it at launch, and 122 mints ids that satisfy it.
- Rejected: an optional key. With an optional key, a new issuer could silently drop back to attribute matching, which is exactly the dependency on internal files this slice removes.

### D2 — One outcome reader, modelling only what is read
Status: decided
- `poll_run(run_id, *, timeout_seconds) -> RunPoll` runs `[SQ_EXECUTABLE, "runs", "wait", run_id, "--timeout", "0", "--json"]` with `stdin=DEVNULL`, captured output, `timeout=timeout_seconds` and `check=False`. `SQ_EXECUTABLE` moves from `cli/prune.py` into this module and is defined only here.
- `RunOutcome` is a `StrEnum` of the eight outcomes, and `OUTCOME_EXIT_CODES` maps each outcome to its exit code. Both are defined once in this module.
- `RunOutcomeDocument` is a frozen pydantic model with `extra="ignore"`. It holds `run_id: str`, `outcome: RunOutcome`, and these optional fields: `status: str | None`, `pipeline: str | None`, `started_at: datetime | None`, `updated_at: datetime | None`, and `checkpoint: RunCheckpoint | None`. `RunCheckpoint` holds `paused_at: datetime | None`. 125 adds the remaining checkpoint fields, `failure` and `reviews` to these models. This is the one place their shape is defined.
- These all return `PollFailure(reason)` rather than raising:
  - `sq` is missing (`FileNotFoundError`).
  - The call times out (`TimeoutExpired`).
  - Any other `OSError`.
  - Exit 2, or any exit code that is not in the map.
  - stdout is not JSON, or it fails validation.
  - The document's `outcome` disagrees with the exit code.
  - The document's `run_id` differs from the requested id.

  Each reason names what happened, and for an unexpected exit it includes the tail of stderr. This follows the `cf_readback` convention: an expected external failure is an answer.
- The model has no defaults beyond `None`. A missing field is unknown and is never filled in.

### D3 — By-id recovery: any run state adopts
Status: decided
- `completed`, `failed`, `paused`, `timed_out` (still running), `unknown_status` and `orphaned` all mean Squadron holds a state for this id, so the command reached Squadron. All six adopt. The result records `run_id`, `outcome` and `status`. Deciding what an orphaned or unknown-status run means is the Runner's job when it observes the adopted run (122, 125), and both escalate there. Recovery answers only whether the command took effect.
- `unreadable` and every `PollFailure` return `Unknown`.
- The `claimed_run_ids` guard stays. If another entry's result already holds this id, the observer returns `Unknown` instead of adopting, so one run never gets two owners.
- The run file's `schema_version` is no longer recorded for id-bearing entries, because the run file is no longer read. The legacy matcher still records it.
- Recovery property 3 in the process contract becomes: "the only route to `adopted` is a run state found by the entry's own id, or, for a legacy entry, exactly one matching candidate."

### D4 — not_found: the launch grace period
Status: decided
- If `issued_at` is null, return `Unknown`: there is nothing to measure the grace period from.
- If `now < issued_at + launch_grace_seconds`, the launch may still be in progress, because launches are detached and can outlive the crashed process. Sleep until that deadline, but never longer than `launch_grace_seconds`, so an `issued_at` ahead of the local clock cannot stretch the wait. Then poll once more. If a state now exists, adopt. If the poll fails, return `Unknown`. If there is still no state, return `NotApplied`.
- Otherwise, return `NotApplied("no run state for <id> after the launch grace period")`.
- **This extends the architecture.** The arch says only that recovery marks the entry `not_applied` once the grace period has passed. Its "still launching" handling is the Runner's launch confirmation, which watches a launch child of the current process (122, D6). After a restart there is no such child, so recovery must answer the in-grace case itself.
- The cost is a start-up stall of at most the grace period still remaining, once per pass, and only after a crash within one grace period of a launch. Start-up after a crash is rare and no tenant is waiting yet, so the stall is accepted over the alternatives rejected below.
- **Startup bound.** Each id-bearing entry makes at most two polls, each bounded by `sq_timeout_seconds`. Deadlines are absolute, so the sleeps across all of a pass's entries add up to at most one `launch_grace_seconds`. A pass with N id-bearing entries therefore delays startup by at most `launch_grace_seconds + 2 × N × sq_timeout_seconds`, and the grace term applies only after a crash within a grace period of a launch. A missing or hanging `sq` costs each entry one failed poll, which escalates it (D3); there is no retry. The clock and sleep are injected for tests, and the bound is asserted in the load tier.
- A run that started and whose state was later removed (for example by `sq runs prune`, whose default categories include completed and failed runs) also returns not_found. Recovery cannot tell it from a launch that never happened without the launch log, which is 122's (122, D4). The guard is the reissue rule: check the launch log, then poll once more, before relaunching (125, D9, issue #9). This slice records that rule as a contract, not only as a note to other slices: the `not_applied` definition for `sq_run` in `docs/process-contract.md` says that it means no run state after the grace period, not proof that the run never started, and that an issuer reissues only after the launch-log check and one more poll. In this slice no Runner reissues anything, so nothing is launched twice.
- Rejected:
  - Escalating every not_found entry, or returning `Unknown` while the grace period runs. That is 100's behaviour, and it would turn the ordinary crash-before-launch case into PM work. 122's crash proof expects `not_applied` for that case.
  - Leaving an in-grace entry unresolved for 122 to finish. Recovery's gate allows an unresolved entry only when it is tied to a run Squadron reports (122, D3), and an in-grace not_found entry has no run. 122 would also need a grace path for a launch with no child.

### D5 — Legacy matching stays, behind a dispatcher, with a lazy scan
Status: decided
- `SquadronRunObserver` routes on whether the `run_id` key is present. `build_observer_registry` stops scanning eagerly and builds the matcher with `scan=None`, so the matcher's existing `scan` property reads the directory on first use. A pass with no legacy entries therefore reads no run-state file. A pass with legacy entries reads the directory once, as before.
- This settles the tension between two of the slice plan's criteria: legacy entries recover by matching, and recovery reads no run-state files. The second criterion holds for every entry this or any later code writes. The first needs the file reads, and it is reachable only for rows written before this slice. The slice plan's criterion is reworded to say so.
- The matcher module's docstring and the `--sq-runs-dir` help text say that it is legacy-only.

### D6 — Pruning decides from the outcome document
Status: decided
- Every owned id is polled. A run is a candidate only when all of these hold:
  1. It is owned. This rule is unchanged.
  2. It is not held. This rule is unchanged.
  3. Its `outcome` is `paused` and its `status` is `paused`.
  4. `checkpoint.paused_at` is present and timezone-aware.
  5. `updated_at` is present and timezone-aware, and `now - updated_at >= PRUNE_RETENTION`.

  A null value in any of them makes the run a non-candidate.
- `paused_at` is always at or before `updated_at`, so retention is measured from `updated_at`, the run's last activity. Requiring `paused_at` excludes a pause whose checkpoint Squadron could not report.
- A poll that fails is not a candidate. Its id is printed on stderr as `could not check: <id> (<reason>)`, and the command still exits `OK` for a preview. The kept count keeps its meaning: owned runs that are paused but not chosen.
- After `sq runs prune`, each candidate is polled again. `not_found` counts as removed. Any other outcome, or a poll failure, counts as still present and leads to `PRUNE_INCOMPLETE`, as today.
- Cost: one `sq` subprocess per owned id. This is acceptable for a manual, rare command over today's small owned set. If the set grows, skipping held ids (which can never be candidates) is the first remedy. That item goes in Future Work, not here.

### D7 — Settings
Status: decided
- `ProcessSettings.launch_grace_seconds: float = 60.0`, with the start flag `--launch-grace SECONDS`. Sixty seconds is many times Squadron's observed time from launch to the `run_id=` line, which comes before the first step. This slice reads it during recovery. 122 reads the same field to confirm launches and to decide when to poll again.
- The per-poll timeout reuses `ProcessSettings.sq_timeout_seconds`, which bounds start-up subprocess calls. Recovery runs at start-up. `amoeba prune` takes the value from `ProcessSettings()` and adds no flag of its own. 122 adds its own per-call tick timeout.
- `sq_runs_dir` and `clock_tolerance_seconds` stay, documented as used only by legacy matching.

### D8 — Proving there are no run-state reads
Status: decided
- **Recovery:** a test journals only id-bearing entries and covers all three observations. It runs `recover_every_project` with `scan_runs_directory` and `parse_run_file` patched to fail the test if called, and points `sq_runs_dir` at a directory whose files would match. The test passes only if neither function is called.
- **Pruning:** an import-boundary test asserts that `cli/prune.py` and `process/run_pruning.py` import nothing from `observers.sq_runs` and do not import `DEFAULT_SQ_RUNS_DIR`. A behavioural test runs prune with the stub `sq` and a run-state directory that would select differently, then asserts the result follows the stub's outcome documents.
- **Contract suite:** the lifecycle proof's stand-in Runner journals with a run id. Its recovery steps and step 12's pruning pass through the stub's `runs wait`.

### Technology Choices

- Standard library `subprocess` and pydantic v2, both already in use. No new dependency.
- The real `sq` is never run in the automated tests. `tests/sq_stub.py` gains a `runs wait` mode (see Migration Plan), matching the existing stance that tests do not need provider credentials.

### Patterns and Conventions

- Expected external failures are answers (`Unknown`, `PollFailure`), never exceptions. Unexpected exceptions propagate and abort startup, which is unchanged.
- Each comparison value is defined once: `RunOutcome`, `OUTCOME_EXIT_CODES`, `PARAM_RUN_ID`, `SQ_EXECUTABLE`, `PAUSED_STATUS`, and the launch-line prefix `run_id=`.
- Each new module stays under about 300 lines. `sq_outcome.py` is expected to be about 150.

## Implementation Details

### Migration Plan

**What moves:** Squadron observation for id-bearing entries and for pruning, from parsing files under `~/.config/squadron/runs/` to `sq runs wait --json`.

| Source | Destination | Note |
|---|---|---|
| `SquadronRun` model, as used by pruning | `RunOutcomeDocument` (`sq_outcome.py`) | `SquadronRun` stays for the legacy matcher only |
| `cli/prune.py` `_read_runs` (directory glob) | `poll_run` per owned id | Same for the check after pruning |
| `cli/prune.py` `SQ_EXECUTABLE` | `sq_outcome.py` | Imported by prune |
| Eager `scan_runs_directory` in `supervisor.build_observer_registry` | Lazy scan inside the matcher | Scanned only for legacy entries |

**Consumers updated in this slice:**

- `src/amoeba/process/supervisor.py`: the registry builds `SquadronRunObserver`.
- `src/amoeba/process/run_pruning.py` and its tests in `tests/process/test_prune_selection.py`.
- `src/amoeba/cli/prune.py` and `tests/process/test_prune_sq_runs.py`.
- `tests/sq_stub.py`: adds `runs wait <id> --timeout 0 --json`. The stub plays Squadron and keeps its own state, one file per id containing the outcome document to print. It exits with the code for that document's `outcome`. For a missing id it prints `{"run_id": id, "outcome": "not_found"}` and exits 5. The existing prune modes delete those same files, so a pruned id then returns not_found. Failure cases (mismatch, exit 2, hang, non-JSON) are added to the stub only where a `poll_run` integration test needs the real subprocess path. Unit tests cover them by patching the subprocess call.
- `tests/contract/standin.py` and `runner_tenant.py`: the run id is minted before `journal_issue` and passed in `parameters`, and the stub-state outcome document is written instead of an internal-shaped run file. `steps_prune.py` checks presence through the stub's state directory.
- Every test that journals `sq_run` gains a `run_id` through one shared helper, `sq_run_parameters(...)` in a tests support module. Today that is `test_journal.py`, `test_journal_models.py`, `test_recovery.py`, `test_host.py`, `test_cli_lifecycle.py`, `test_read_only_open.py`, `inspection_harness.py`, `inspection/test_feed.py`, `load/load_harness.py`, `load/test_recovery_scale.py`, `store/test_runner_report.py`, `store/test_messages.py`, `process/test_review_detection_ownership.py`, `contract/harness.py` and `contract/end_state.py`. The task breakdown re-greps for `CommandKind.SQ_RUN` instead of trusting this list. The helper only adds a `run_id` to the parameters a caller passes, and does nothing more. This churn is the cost of D1 and is not cut: an optional key was rejected there.
- `tests/test_observer_sq_runs.py` keeps its matcher tests. A legacy entry is built as a `JournalEntry` value, and at store level as a row written through a raw `sqlite3` test helper that represents a pre-120 row.
- `tests/load/test_recovery_scale.py`: the scan-count assertions become zero scans for id-bearing entries, one for a pass with legacy entries, and one poll per id-bearing entry.
- `scripts/demo_journal.py` is deleted, along with its entry in `tests/test_writer_guard.py`'s `PERMITTED_SCRIPTS`. It demonstrated 101's attribute matching with id-less entries, which `journal_issue` now refuses, and the recovery tests cover both paths.

**Data:** existing stores need no migration. Unresolved id-less entries in existing stores recover through the matcher as before.

**Behaviour preserved:**

- Legacy recovery outcomes are identical, because the matcher tests are unchanged.
- The prune command's interface, exit codes, preview format and ownership rules are unchanged.
- 100's contract suite passes.

### API Contracts

Python API, internal to `amoeba.process`. 122 and 125 consume it in-package. It is exported from `amoeba.process` alongside the existing observer types:

```python
class RunOutcome(StrEnum): COMPLETED, FAILED, PAUSED, TIMED_OUT, NOT_FOUND,
                           UNREADABLE, UNKNOWN_STATUS, ORPHANED
OUTCOME_EXIT_CODES: Final[Mapping[RunOutcome, int]]

@dataclass(frozen=True)
class PollFailure: reason: str

type RunPoll = RunOutcomeDocument | PollFailure
def poll_run(run_id: str, *, timeout_seconds: float) -> RunPoll: ...

```

CLI: `amoeba start --launch-grace SECONDS` (new). `amoeba prune sq-runs [--yes]` keeps its interface. It may now print `could not check: <id> (<reason>)` lines on stderr.

## Integration Points

### Provides to Other Slices

- **122 Runner tenant:**
  - It must journal `run_id` in every `sq_run`.
  - It polls in-flight runs with `poll_run`, mapping `TIMED_OUT` to still running.
  - It reads `launch_grace_seconds`.
  - It can rely on recovery having resolved every id-bearing entry as `adopted`, `not_applied` (no run state after the grace period; not proof the run never started), or `unknown` (escalated). 122 changes the answer for a run that exists from `adopted` to in flight (122, D3).
- **125 Dispatch and reissue:** a `not_applied` entry is reissued only under the contract rule D4 records: the launch-log check, then one more poll (125, D9, issue #9).
- **125 Dispatch and ingestion:** `RunOutcomeDocument` is the one model of the outcome document. 125 extends it with `checkpoint` fields, `failure` and `reviews`.
- **Contract documents:**
  - `docs/process-contract.md`: Recovery properties, the `not_applied` definition for `sq_run` and its reissue rule (D4), the shipped observers, the supervisor directory table (`runs/`), the start flags, and pruning.
  - `docs/store-contract.md`: required parameter keys.
  - `docs/substrate-guide.md`: the 120 row, which now says the issuer must put `run_id` in both `parameters` and `result`.

### Consumes from Other Slices

- **100:** the recovery protocol, the observer registry, the journal, `recorded_result_run_ids`, and read-only store opening, all unchanged.
- **Squadron S10:** if `sq` is missing or a document is malformed, recovery escalates the affected entries (`Unknown`) and pruning chooses nothing. Neither guesses.

## Success Criteria

### Functional Requirements

- `journal_issue` refuses an `sq_run` without `run_id`.
- An id-bearing entry whose run has a state is adopted with `run_id`, `outcome` and `status`. This holds for each of the six outcomes that carry a state.
- An id-bearing entry with no state is marked `not_applied` once `issued_at + launch_grace_seconds` has passed. Recovery waits out a grace period still running, for no longer than one grace period, and adopts if the state appears during it. An entry with a null `issued_at` escalates.
- `unreadable`, a missing `sq`, a timeout, exit 2, non-JSON output, an outcome that disagrees with the exit code, a mismatched `run_id`, and a malformed parameter value each escalate with a reason naming the cause.
- An entry without the `run_id` key recovers through the existing matching rule with unchanged results.
- Pruning selects exactly the owned, unheld runs that are paused, have a known `paused_at`, and whose `updated_at` is past retention. A poll failure is named and never chosen. Removal is confirmed by `not_found`.

### Technical Requirements

- The no-reads tests in D8 pass. Recovery of id-bearing entries and every pruning path make no call to `scan_runs_directory` or `parse_run_file`.
- `uv run pytest`, `uv run ruff check .`, and `uv run pyright` (strict) are clean.
- New modules follow the project exception rule, and each catch names its specific exception with a comment.
- The contract documents listed under Provides are updated in the same slice, and the CHANGELOG has an entry.

### Integration Requirements

- 100's contract suite (`tests/contract`) passes, extended so that the stand-in Runner journals with a run id and recovery and pruning go through the stub's `runs wait`.
- 122 can code its polling against `poll_run` and `launch_grace_seconds`, without reading any Squadron file.

### Verification Walkthrough

Run in bash from the repository root. Steps 1–2 are automated. Step 3 uses the real `sq` (0.23.5 or later) read-only and launches nothing.

1. **Unit, integration and contract tests:**
   ```bash
   uv run pytest tests/test_observer_sq_run_id.py tests/test_observer_sq_outcome.py \
     tests/test_observer_sq_runs.py tests/test_recovery.py tests/process -k "sq or prune or recovery" -v
   uv run pytest tests/contract -v
   ```
   Expected: everything passes. The D8 no-reads tests are named `test_recovery_by_id_reads_no_run_state_file` and `test_prune_reads_no_run_state_file`.

2. **Full gate:**
   ```bash
   uv run pytest -q && uv run ruff check . && uv run pyright
   ```

3. **See the surface recovery now reads.** Pick any id from your real runs, then ask for one that does not exist:
   ```bash
   sq runs list --all | head -5
   sq runs wait <an-id-from-the-list> --timeout 0 --json; echo "exit $?"
   sq runs wait amoeba-unused-0001 --timeout 0 --json; echo "exit $?"
   ```
   Expected: a document with `outcome`, `status` and `updated_at`, and an exit code matching the outcome. Then `{"run_id": "amoeba-unused-0001", "outcome": "not_found"}` with exit 5.

## Risk Assessment

### Technical Risks

- **Recovery is 100's most sensitive path.** A wrong `NotApplied` lets 122 launch the same work twice.
- **Startup latency.** Each id-bearing entry costs one or two `sq` subprocesses, bounded as in D4.

### Mitigation Strategies

- Escalation stays the default for every ambiguous answer. `NotApplied` needs a not_found answer after the grace period and a known `issued_at`. Before reissuing, the issuer checks the launch log and polls once more (arch, "Observing a run without blocking the tick"; 125, D9). This slice writes that rule into the `not_applied` definition in `docs/process-contract.md` (D4).
- The legacy matcher and its tests are unchanged, so existing recovery behaviour is a regression baseline.
- The load tier asserts poll counts and the D4 startup bound.

## Implementation Notes

### Development Approach

Suggested order. Each step leaves the suite green.

1. `sq_outcome.py` (`RunOutcome`, the document model, `poll_run`, `PollFailure`), with the stub's `runs wait` mode and its unit tests.
2. The `launch_grace_seconds` setting and flag.
3. The `run_id` required key, the shared `sq_run_parameters` test helper, and updates to every journaling caller (tests, stand-in).
4. `SquadronRunIdObserver`, the dispatcher, the lazy legacy scan, and the registry wiring, followed by recovery tests and the D8 recovery no-reads test.
5. Pruning on outcome documents, followed by its selection and CLI tests and the D8 pruning tests.
6. The contract suite through the stub. Then the documents (process, store, substrate guide), the CHANGELOG, and retiring the demo script.

Testing approach:

- Unit tests use an injected clock and sleep for the grace rule, and `JournalEntry` values for observer cases.
- Integration tests use the stub `sq` on `PATH` under a temporary `HOME`.
- The real `sq` is used only in the manual walkthrough, and only read-only.

### Special Considerations

- Subprocess calls are made only at start-up (recovery) and in the manual prune command. This slice adds no subprocess call inside a tick.
- No secrets are involved.
- Future Work (slice plan item 6): skip polling held ids during pruning if the owned set grows large enough to make `amoeba prune` slow.
