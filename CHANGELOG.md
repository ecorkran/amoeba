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
