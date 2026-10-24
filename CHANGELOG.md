---
docType: changelog
scope: project-wide
---

# Changelog

All notable changes to Amoeba will be documented in this file. Entries should be
concise, ideally 1-2 lines. Current changes not yet pushed and tagged will
accumulate in [Unreleased].

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Slice 124: the intent vocabulary (`amoeba.runner.intent`). An `intent` body is one of `drive` (optionally `until <step>`), `exclude`, `pause`, `resume` or `clear`, validated by `IntentBody` (unknown keys are errors); a target is the project, or a linked initiative or slice. Every intent gets one acknowledgment: `applied`, `no_op` (the target's settings would not change) or `rejected` with `malformed_body`, `target_not_initiative_or_slice`, `target_unlinked` or `until_not_applicable`.
- Slice 124: the apply stage runs first in each project tick (store-only, ignores link state) and the tick reads a `DesiredStateIndex` once. Drive resolves from the nearest row on a step's path, hold from any row; nothing is driven by default, so linking a project escalates nothing. `STEP_SEQUENCE` and `step_rank` order the steps for `until`. `HumanStepPlanner` is now in the production planner tuple.
- Slice 124: `amoeba inspect desired-states --project P` (and `/v1/listings/desired-states`) lists the stored rows. Contract text in `docs/inbox-contract.md` ("Intent bodies"), `docs/process-contract.md` and `docs/substrate-guide.md`.

- Slice 123: the lifecycle model and reconciliation (`amoeba.runner.lifecycle`). The Runner reads each linked Context Forge project's plan (`cf list initiatives --json -a`, then `cf list slices <index> --json`) and keeps the node tree in step: initiative and slice nodes linked by CF index, each with its step nodes (`architecture`, `slice_plan`, `slice_design`, `tasks`, `implementation`, `merge`, `integration`). Reconcile orphans nodes CF stops reporting (never on a failed or partial read), creates what is missing, blocks slices with an unknown status, follows renames, and marks steps CF shows complete as `done`. It runs after in-flight runs are polled, on the interval or early when a CF snapshot changes, under the tick budget.
- Slice 123: migration `010` and `CFReference.index` (`nodes.cf_index`) with a partial unique link index; `amoeba inspect nodes` shows `cf_index`. New setting `plan_read_interval_seconds` (default 30) and start flag `--plan-read-interval`. New fault kinds `plan_read_failed`, `lifecycle_orphan` and `plan_status_unknown`, and a store-only `BlockHumanStep` action with `HumanStepPlanner` (registered by slice 124, not yet in production). Only `reconcile` may call `create_node` (guard test). `ProjectView` now carries a `LifecycleTree` (`tree`) instead of `runnable_nodes`.
- Slice 123: the `cf` link probe now runs `cf list initiatives --json -a` and requires output the plan model accepts. Contract text in `docs/store-contract.md`, `docs/context-forge-contract.md`, `docs/process-contract.md` and `docs/substrate-guide.md`. Finding recorded there: CF 0.19.17 prints the "no slice plan" error document on stderr.

- Slice 122: the Runner tenant and `sq_run` control surface (`amoeba.runner`, imported only by `amoeba.cli`), composed by `amoeba start` after the shipped tenants. Each tick observes the in-flight runs, records the finished ones, decides through pure planners (the production tuple is empty, so nothing launches yet) and acts by journaling then launching `sq run --run-id` detached, with per-entry logs under `launch-logs/`. A launch is confirmed by the exact `run_id=<id>` stderr line or a run state, and a late or dead launch is escalated per project.
- Slice 122: start flags `--tick-deadline`, `--tick-call-timeout` and `--run-poll-interval`; a `TickBudget` is checked before every tick-time subprocess call; `start` probes `sq runs wait` once (`STARTUP_FAILED` on a bad shape) and each Context Forge link once (`cf_probe_failed` escalation).
- Slice 122: exit code 15 `UPSTREAM_SHAPE` and `UpstreamShapeError`; `amoeba.process` also exports `InFlight` and `SQ_EXECUTABLE`, and `amoeba.store` exports `PARAM_RUN_ID` and `PARAM_CHECKOUT`. The stub `sq` gains `run --run-id`, there is a stub `cf`, and `tests/runner/` holds a `SIGKILL` crash proof for the Runner.
- Slice 122: **behavior change** for recovery: an id-bearing `sq_run` entry whose run exists is now left unresolved (`InFlight`, counted as `in_flight` in the recovery summary) instead of being adopted, so the Runner can still record its review. The legacy attribute matcher still adopts. `docs/process-contract.md` documents the Runner, the supervisor directory's `launch-logs/`, the new flags and exit code.

- Slice 121: store contract changes for the Runner (schema version 9, migration `009`). `done` is terminal: no store write moves a done node, `journal_issue` refuses one, and `done` is refused while the node has an unresolved journal entry. `acknowledge_message` takes a required `outcome` (`AcknowledgmentOutcome`: `applied`, `no_op`, `rejected`) and optional `reason` and `desired_state`, written in one transaction; `intent_for_submission` reads the outcome back.
- Slice 121: project-scoped escalation (`raise_project_escalation`, `open_project_escalations`, `close_project_escalation`), one open row per project and fault kind. `record_routing_decision` writes a routing decision, its table version, its attempt count and its node effect in one transaction, with reads `routing_decision`, `routing_decision_for_entry`, `routing_decisions`, `routing_table_version` and `attempt_count`. Desired-state reads `desired_state` and `desired_states`.
- Slice 121: `amoeba inspect messages` (and `/v1/listings/messages`) show `acknowledgment_outcome`, `acknowledgment_reason`, `fault_kind` and `closed_at`. Contract text in `docs/store-contract.md` and `docs/inbox-contract.md`.
- Slice 121: **breaking** change to an existing method: `acknowledge_message` now requires `outcome`; the stand-in Runner in `tests/contract/` passes `AcknowledgmentOutcome.APPLIED`.

- Slice 120: `run_id` is a required `sq_run` journal parameter. Recovery and `amoeba prune sq-runs` ask Squadron through `sq runs wait --json` (new `amoeba.process.poll_run`, `RunOutcome` and friends) instead of reading its run-state files; an id-bearing entry with no run state past `--launch-grace` (default 60 s) is `not_applied`. Entries journaled before 120 still recover through the attribute matcher. `scripts/demo_journal.py` is retired.

- Slice 110: the contract proof, `tests/contract/` — a 12-step lifecycle across two projects with real processes, `kill -9` crash windows, an end-state oracle and a feed-replay oracle, plus a network subset that survives a `kill -9` of `amoeba serve` and of the resident process. Every import in it is checked to be a public export.
- Slice 110: `amoeba.process` exports the tenant-hosting contract (`ResidentProcess`, `Tenant`, `ProcessSettings`, `Observer`, `Observation`, `Adopt`, `NotApplied`, `Unknown`, `standard_tenants`, and the four process errors). `build_tenants` moved from `cli/lifecycle` to `process/tenants` as `standard_tenants`, with no behavior change.
- Slice 110: `Store.record_runner_report`, which records a launched review's verdict, its `runner_issued` ledger row, and the resolved journal entry in one transaction; `store_dir` and `project_store_path` exported from `amoeba.store`; `SquadronRun.updated_at` and a schema-v5 run fixture.
- Slice 110: `amoeba prune sq-runs [--yes]` previews the paused Squadron runs Amoeba owns that no unfinished node names, and with `--yes` deletes them through `sq runs prune`; exit code 14 `PRUNE_INCOMPLETE`. `process-contract.md` gains "Pruning paused runs" and the ownership guarantee (an `sq_run` issuer records `run_id` in its result).
- Slice 110: `docs/substrate-guide.md`, the entry point for initiatives 120, 140, 160 and the notification bridge.
- Slice 110, gap G1 (additive, fixed by documentation): `evidence-contract.md` did not say how a Runner builds the `runner_issued` ledger row's key (the file's path and the sha256 digest of its bytes) or that a verdict's journal entry must be on the verdict's own node. It does now.

- Slice 109: `amoeba serve` (Starlette + uvicorn), a second foreground process: `GET /v1/listings/{name}` over the one listing registry, `POST`/`GET` submissions through `submit()` with a required id, and an SSE feed per project resumable by `Last-Event-ID` or `?after=`; contract in `docs/network-contract.md`.
- Slice 109: bind policy (loopback, or a bearer token from `AMOEBA_SERVE_TOKEN` plus TLS), Origin/Host/content-type guards, one `ApiErrorCode` vocabulary, stream slots (`max_streams`), heartbeats, and a per-send timeout; exit code 13 `SERVE_REFUSED`.
- Slice 109: `Store.read_transaction()` and `change_head()`; every project read reports `as_of_seq` from one snapshot ("current state, then follow").
- Slice 109: dependencies `starlette`, `uvicorn` (runtime) and `httpx2` (dev).

- Slice 108: schema version 8 (migration `008`) — `cf_links` and `cf_snapshots`, a `cf_project_changed` change kind, and the `CFSnapshotOutcome` word list (`observed`, `unreadable`, `unrecognized`, `missing`); store methods `cf_links`, `cf_snapshots`, `latest_cf_snapshots`, `record_cf_snapshot`.
- Slice 108: `amoeba.upstream.context_forge` — a parser for CF's `projects.json` into a watched projection of pointer fields (project and worktree level) and a pure diff; tested against a real captured file.
- Slice 108: `CFWatchTenant`, registered third by `amoeba start`: a `stat` check of `projects.json` once per second records one snapshot, and one `cf_project_changed` feed entry, per linked project whose pointers moved; failures are recorded once per transition. `start` flag `--cf-data-dir` (`CONTEXT_FORGE_DATA_DIR` is not read).
- Slice 108: the `link_cf_project` submission kind and `amoeba submit link-cf-project`; `amoeba inspect cf-links` and `cf-snapshots`; `docs/context-forge-contract.md`.
- Slice 107: judge samples — a verdict with a `judge_invocation_id` (`VerdictInput`, the `verdict` payload, `to_verdict_input`, `amoeba ingest review --judge-invocation-id`, `amoeba submit verdict`); `verdicts(..., judge_invocation_id=)`; schema version 7 (migration `007`).
- Slice 107: `calibration` and `amoeba inspect calibration`, a descriptive per-`(review_type, model)` report of judge samples; it is not agreement evidence (GitHub issues #4, #6).
- Slice 107: check results — `record_check`, `check`, `checks`, the `check` submission kind and `amoeba submit check`, `amoeba inspect checks`, and the `check_recorded` change kind; standing is derived (`vacuous` when `examined_count` is 0, never `passed`).
- Slice 107: `record_progress`, a write-only store for SQ 280 `task_progress` and `devlog` records (GitHub issue #5); `docs/evidence-contract.md`, `inbox-contract.md`, `feed-contract.md`, and `store-contract.md` updated.

- Slice 106: schema version 6 (migration `006`). A per-project change log written by SQLite triggers in the same transaction as every node, verdict, message, and detection write; `Store.changes`, `data_version`, and `amoeba.store.paths.project_store_path`.
- Slice 106: `amoeba.feed.follow` and `amoeba feed --project ID [--after N] [--follow]`, a read-only follower printing changes as JSON lines; contract in `docs/feed-contract.md`.
- Slice 106: `ReviewDetectionTenant`, registered by `amoeba start` after the inbox: baselines registered review directories, then records new settled Squadron reviews as verdicts on their slice node, or as `unattributed`/`unparseable`; defers while a review-producing journal entry is open.
- Slice 106: the `watch_reviews` submission kind; `amoeba inspect watches` and `amoeba inspect detections`; `start` flags `--review-scan-interval` and `--sq-timeout`.
- Slice 106: `attribute_review`, `REVIEW_PRODUCING_KINDS`, and the detection ledger API (`record_detection`, `detection`, `detections`, `watches`, `baseline_watch`, `record_detected_verdict`, `recorded_since`, `has_unresolved_review_entry`).
- Slice 106: `scripts/demo_detection.py` seeds the walkthrough's slice and blocked nodes.
- Slice 105: `amoeba.upstream.squadron` — a pure parser for Squadron review files and `--output json` stdout (`ParsedReview`, `to_verdict_input`, `review_record_id`), tested against real captured reviews.
- Slice 105: `amoeba ingest review` submits a review as a `verdict` without waiting; exit code `REVIEW_UNREADABLE` (12). It refuses a project with no store.
- Slice 105: `verdict_to_payload` (the inverse of `verdict_from_payload`) and `provider_failure_problem` (one definition of the provider-failure rule, shared by the store and the parser).
- Slice 105: `inspect verdicts --json` rows carry `sq_run_id` and `reviewed_sha`.
- Slice 105: PyYAML is now a runtime dependency.
- Slice 105: the record id is a digest of the parsed review, tagged `parsed-review-v1`. The covered fields are a contract: changing them changes every id and needs a new tag and a changelog entry.
- Slice 104: verdict records and findings in the store — schema version 5 (migration `005`: `verdicts`, `finding_observations`), `record_verdict` (one transaction, caller-supplied id, first record wins), and `verdict` / `verdicts` / `observations` / `findings` reads.
- Slice 104: `amoeba.store.finding_identity`, a versioned content key per finding that survives formatting and moved line numbers but deliberately not rewording; pinned against the captured slice-102 review rounds.
- Slice 104: `finding_changes` — new, recurring, and gone against the previous comparable round, never stored; provider failures and unparsed reviews are never a baseline.
- Slice 104: a trust label (`VerdictStanding`) on every verdict, and required provenance (`upstream_version` is a label, never compared).
- Slice 104: the `verdict` submission kind and `amoeba submit verdict`; `amoeba submit` now reads flags by one rule (text and enum fields as typed, everything else as JSON).
- Slice 104: `amoeba inspect verdicts`, `amoeba inspect findings`, and `amoeba inspect changes --verdict ID`; the listing registry gains `value_options`; exit codes `NOT_FOUND` (10) and `NOT_COMPARABLE` (11).
- Slice 104: `docs/evidence-contract.md`; PyYAML as a dev-only dependency for reading captured review files in tests.
- Slice 103: the durable inbox — `amoeba.inbox.submit()` writes one fsync-durable file whether or not the process runs; the only way a part outside the process contributes state.
- Slice 103: `InboxTenant`, the first real tenant — applies each submission exactly once per id, quarantines what cannot be attributed, and bounds a failing apply with an on-disk attempt counter that parks the file in `inbox/failed/`.
- Slice 103: schema version 4 (migration `004`) — `inbox_submissions` and `messages`, with receiver-assigned `applied_seq` / `seq` as the authoritative order, and a backfill of escalations for open human blocks.
- Slice 103: three submission kinds — `create_project`, `resolution` (targets a blocked state, never redirected to a newer block), and `intent`.
- Slice 103: the `intent` and `escalation` message channels, with `messages(after_seq=…)` as a replay primitive readable through a read-only handle, plus `pending_intents` / `acknowledge_message` for the Runner.
- Slice 103: runtime project creation via `host.open_project` — a project created through the inbox is usable at once, without a restart.
- Slice 103: `amoeba submit create-project|resolution|intent`, with flags derived from each kind's payload model, and exit code `SUBMISSION_REFUSED` (9).
- Slice 103: `amoeba inspect inbox|submissions|messages`, and `--inbox-batch-size` / `--inbox-max-attempts` on `amoeba start`.
- Slice 103: `docs/inbox-contract.md`, and a concurrent-submitter load test proving exactly-once across repeated `SIGKILL`s.
- Slice 102: command journal in the store (migration `003`) — an entry is committed *before* its side effect is issued, so a crash leaves a durable record of what may have been in flight.
- Slice 102: `journal_issue` / `journal_resolve` / `journal_escalate`, with parameters validated at issue time so an entry can always be reconciled later.
- Slice 102: `Store.open_read_only` — a genuine SQLite `mode=ro` handle that never migrates and never creates, measured against this project's Python and SQLite build.
- Slice 102: the resident process — `amoeba start` / `stop` / `status`, single-instance enforcement via an advisory `flock`, and signal-driven graceful shutdown with a bounded grace period.
- Slice 102: reconcile-by-observation recovery — every journaled-but-unresolved command is reconciled by *observing* the external system, never by re-issuing; every ambiguity becomes a `blocked_on_human` node.
- Slice 102: two observers — Squadron runs-directory matching (subset-on-params, four candidate conditions) and Context Forge read-back — both tested against real captured upstream output.
- Slice 102: the `Tenant` protocol and host loop that slices 103 and 120 plug into. This slice ships **no tenants**: the process starts, recovers, idles, and stops.
- Slice 102: `amoeba inspect` — read-only listings for projects, nodes, blocked states, and journal entries, human-readable and `--json`, declared in one registry that slice 104 extends by registering.
- Slice 102: `pydantic` as the project's first runtime dependency, used only at the two external parsing boundaries.
- Slice 102: a `tests/load/` tier with crash-loop and recovery-scale tests, excluded from the default suite and gated separately in CI.
- Slice 102: an AST guard test failing if any module other than `process/host.py` opens a store read-write.
- Slice 102: contract documentation at `docs/process-contract.md`, and a Journal section plus corrected writer-model section in `docs/store-contract.md`.
- Slice 101: Python project scaffold — `pyproject.toml` with the mandated ruff, pyright strict, pytest, and uv configuration.
- Slice 101: SQLite-backed lifecycle node store — project-keyed node tree, closed `StrEnum` vocabularies, and blocked states with an explicit resolution slot.
- Slice 101: `block()` and `resolve()` as single store operations, so node status and blocked-state can never disagree.
- Slice 101: the two Runner queries — *what is runnable?* and *what is blocked and on whom?* — both project-scoped and index-backed.
- Slice 101: schema version stamp and numbered-migration runner, with a trivial `002` migration proving N→N+1 end to end.
- Slice 101: typed failure modes for lock contention, corrupt files, permission errors, and failed commits — none degrading to a default or fallback store.
- Slice 101: central per-supervisor store path resolution (`AMOEBA_STORE_DIR` → XDG → `~/.config/amoeba`), project-keyed and pure.
- Slice 101: contract documentation at `docs/store-contract.md`, sufficient to design a consumer without reading the implementation.

### Changed

- Slice 124: `ProjectView` gains `desired` and `current_steps`; `decide()` raises `ValueError` for an action on a step that is not current (ready, driven, not held); planners see `current_steps`. `LifecycleTree.node(id)` added. Test planners that launched on plain slice nodes now use `ready_step` and `drive_project` in `tests/runner/tick_support.py`.

- Slice 109: the `inspect` listings moved from `amoeba.cli` to `amoeba.inspection` (typed `ListingRequest`, `read_listing`); `discover_project_ids` to `amoeba.store.discovery`; `review_sources` to `amoeba.store`; `change_record` to `amoeba.feed.wire`. `inspect` output and `--help` are byte-identical.

- Slice 107 (104): `VerdictInput` and the `verdict` payload gain optional `judge_invocation_id`; the previous-round lookup skips samples of the target's own invocation; `record_verdict` rejects a sample on another node or review type than its invocation's earliest sample; `RecordSource` gains `command_output` and `document`; `inspect verdicts` gains a `judge_invocation_id` column and `--judge-invocation-id`.
- Slice 107 (105): `parse_review_json` raises `SquadronParseError` on stdout JSON reporting `UNKNOWN` with a `score` (`ingest review` exits 12; ingest the saved file instead; GitHub issue #2). `to_verdict_input` and `ingest review` gain the optional invocation id; the record-id digest and `parsed-review-v1` are unchanged, and a sample's default id appends `.` and the invocation id.
- Slice 107 (106): `ChangeKind` gains `check_recorded`, with migration `007`'s trigger.
- Slice 107 (103): `SubmissionKind` gains `check`.
- Slice 107 (102): the `checks` and `calibration` listings join `LISTINGS`.
- Slice 105: a review file's `providerFailure` key, when present, decides `provider_failure`; the *Provider Failure* heading is read only for files without the key.
- Slice 103: a `HUMAN` block now writes an escalation message in the same transaction; `block()` gains an optional `payload`. Every block goes through one internal writer.
- Slice 103: `journal_escalate` now writes an escalation carrying the journal entry id, including on its already-blocked branch, where it points at the existing open block.
- Slice 103: `amoeba start` registers `InboxTenant` first, where slice 102 registered no tenants.
- Slice 103: `host.project_ids` grows at runtime and must not be cached.
- Slice 103: read-write store opening moved from `process/host.py` to `process/project_stores.py`; the writer guard's one permitted module moved with it.

### Fixed

- Slice 101 (code review): `create_node` and `update_node_status` refuse blocked statuses, so `block()`/`resolve()` are structurally the only writers of blocked state.
- Slice 101 (code review): schema-level invariant violations raise `StoreIntegrityError` instead of a raw `sqlite3.IntegrityError`; `open_temporary()` closes its connection on a failed migration, matching `open()`.
