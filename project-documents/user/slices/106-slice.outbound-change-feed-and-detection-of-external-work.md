---
docType: slice-design
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101, 102, 103, 104, 105]
interfaces: [108, 110]
dateCreated: 20260928
dateUpdated: 20261015
status: not_started
---

# Slice Design: outbound-change-feed-and-detection-of-external-work

## Overview

The store changes, and nobody outside the process hears about it. A PM runs `sq review` by hand, and the store never learns the review happened. This slice fixes both, and nothing more:

1. **A change feed.** Every state change the store commits also appends one row to a per-project change log, in the same transaction. Subscribers read the log from a cursor they own and follow it as it grows.
2. **Detection of reviews nobody in Amoeba launched.** A new tenant in the resident process watches registered review directories. A new review file is parsed with slice 105's parser, attached to its slice node, and recorded as a verdict with a detection ledger entry. A file it cannot parse or cannot attach is recorded as exactly that, never guessed.

Human replies already arrive through 103's inbox (`resolution` submissions). They need no watcher: applying one flips a node's status, and that status change is on the feed.

*Trimmed 20261015* after a proportionality review. Deferred out of this slice, each with a GitHub issue: the consistent snapshot-plus-head read (`read_transaction()`), the Runner's one-transaction report-back (`record_runner_report`), and the `source_document` series key. See Deferred.

## Value

Developer value.

- The Translator and any status view get an ordered stream of what changed, with a cursor that survives restarts on both sides.
- A PM-launched review lands in the store as a verdict with provenance, so the Runner (120) sees it without the PM typing an `ingest` command.
- A provider-failure file is recorded as a provider failure. A file that is not a review, or has no slice node, is visible in one listing.
- When Squadron ships a review-completed event (dependency S8), the file watcher is swapped out behind one interface. Subscribers see nothing change.

## Technical Scope

**Included**

- Migration `006` with three tables: `changes`, `review_watches`, `detected_reviews`.
- Change emission by SQLite triggers on the tracked tables: node creation, node status change (including block and resolve), verdict recorded, message posted, and detection outcomes (D8).
- `amoeba.store` read API: `changes(project_id, *, after, limit)`, `watches`, `detections`, and `record_detection`.
- `amoeba.feed`: a subscriber-side follower. `amoeba feed --project ID [--after N] [--follow]` prints changes as JSON lines.
- A `watch_reviews` inbox submission kind that registers or deactivates a review directory.
- `ReviewDetectionTenant` in `amoeba.process`, with a `ReviewSource` interface and one implementation, `DirectoryReviewSource`.
- The attribution rule (review → slice node), defined once and exported for initiative 120.
- `amoeba inspect watches` and `amoeba inspect detections`, registered in 102's listing registry.
- `docs/feed-contract.md`; updates to `store-contract.md`, `inbox-contract.md`, `process-contract.md`, `evidence-contract.md`, and `CHANGELOG.md`.

**Excluded**

- Context Forge events: slice 108.
- Review completion for commands the Runner issued. The Runner observes those at process exit (120); see D5.
- Backfilling reviews that existed before a directory was registered. Use `amoeba ingest review` (105), oldest first.
- A network transport for the feed. Slice 109.
- A cross-project feed; feed retention and compaction (already in the slice plan's future work); parsing anything other than Squadron review files.

### Deferred (each filed as a GitHub issue)

- **`read_transaction()` on the read-only handle, and `change_head()`.** They exist so a reader can take a state snapshot and the feed head atomically, then follow from it. Nothing in 106 reads both; the first consumer is 109. A follower that needs "current state, then everything after" before then reads state, then follows with `--after 0` and applies changes idempotently. 109 adds both, as an amendment to 101's handle.
- **`record_runner_report`.** The Runner's write path, wanted by 110/120. D5 point 3 stays a stated requirement on 120 in `evidence-contract.md`; 120 (or 110, if earlier) builds the method.
- **`source_document` as part of a review series.** Task reviews come in parts (`part-1`, `part-2`, both `reviewType: tasks`, same slice), and under 104's rule they share one series per node, so part 2's round becomes part 1's "previous round" in `finding_changes`. That is a real limit and is **accepted for now**: it affects only the "what changed since last round" comparison for multi-part task reviews, not what is recorded. Fixing it changes 104's contract (a verdict column and the previous-round query) and deserves its own small slice.

## Dependencies

### Prerequisites

- **101:** `Store`, nodes and their `cf.slice_name` reference, the migration mechanism (`EXPECTED_SCHEMA_VERSION` 5 → 6).
- **102:** the tenant seam, `ProcessSettings`, the command journal (D5 reads open entries), the listing registry, the writer guard, and the `cf --version` "label or explicit unavailable marker" pattern this slice reuses for `sq --version`.
- **103:** the inbox and its kind seam (member, payload model, effect), `amoeba submit`, and `resolution`.
- **104:** `record_verdict`, its retry rule, the trust label, and `VerdictInput`.
- **105:** `parse_review_artifact`, `to_verdict_input`, and `review_record_id`. `ParsedReview` exposes the frontmatter's `slice` as a field; attribution needs it. The default record id is a digest of the **parsed** review, not of the raw bytes, because this repository edits review files by hand after Squadron writes them (`resolution:` and `resolvedBy:` keys). A parsed-content digest makes the edit a no-op, and makes `amoeba ingest review` and detection agree on the id for the same review.

### Interfaces Required

**From the store:** the `nodes`, `verdicts`, and `messages` tables and their timestamp columns, which the triggers read (no writer method changes); `journal_entries` filtered to unresolved.

**What Squadron writes today:** one file per review at the top of the reviews directory, named `{index}-review.{reviewType}.{slice}[.part-N].md`. A new round overwrites the same name; the PM moves older rounds into `archive/` with a timestamp suffix by hand. No file carries the Squadron version or run id yet (squadron#139).

## Architecture

### Component Structure

```
src/amoeba/store/
  feed_models.py        ChangeKind, Change, DetectionOutcome, ReviewWatch, DetectedReview
  sql_feed.py           every statement and column name for the three tables
  mapping_feed.py       row → record mapping
  feed.py               FeedOperations mixin: changes, watches, detections, record_detection
  attribution.py        attribute_review(slice_nodes, slice_name) -> Attribution   (pure)
  schema/006_change_feed_and_detection.sql   tables and the emission triggers
src/amoeba/feed/
  follower.py           follow(store_dir, project_id, after) -> Iterator[Change]
src/amoeba/process/
  review_sources.py     ReviewSource protocol, DetectedFile, DirectoryReviewSource
  review_detection.py   ReviewDetectionTenant
src/amoeba/inbox/
  envelope.py           + WatchReviewsPayload
src/amoeba/cli/
  feed.py               amoeba feed
  inspect_feed.py       the watches and detections listings
docs/feed-contract.md
```

Same pattern as 101–104: models, SQL, mapping, operations mixin. The store does not import `amoeba.upstream` or `amoeba.process`. The tenant is the only module that knows both the parser and the store's write path, as `InboxTenant` is for the inbox.

### Data Flow

**Emitting a change:**

```
any write to nodes, verdicts, messages, or detected_reviews, by any code path
  AFTER INSERT / AFTER UPDATE OF status trigger fires inside the same transaction
    INSERT INTO changes (kind, node_id, subject_id, payload via json_object,
                         recorded_at = the row's own timestamp)
  commit                                   # the row and its change land together, or neither
```

**Following the feed:**

```
follow(store_dir, project, after=N)
  open the project store read-only
  loop:
    rows = changes(project, after=cursor, limit=batch)
    yield each; cursor = last seq
    if no rows: wait until PRAGMA data_version changes (checked every follow_interval), then loop
```

The subscriber owns the cursor. The store keeps no record of subscribers.

**Follower failures.** Retry only what is transient; raise everything else, because 109 and 160 build on this contract.

| Case | Behavior |
| --- | --- |
| Busy or locked read during a writer commit | Retried on the next interval; never surfaces. |
| Store at a schema version other than the follower's | Raises the store's version error before yielding. The CLI exits through its existing `StoreError` mapping. No retry: an upgrade needs the process, not the follower. |
| Unknown project, or store directory gone (at start or mid-follow) | Raises `StoreError` subclasses as the store does. Same CLI mapping. |
| `stop` callable raises | Propagates. The follower does not catch its caller's bugs. |
| `stop` returns true | The iterator ends cleanly (exit 0 in the CLI). |

**Registering a directory:**

```
amoeba submit watch-reviews --project P --by pm --reviews-dir /abs/path --active true
  inbox apply: upsert review_watches(project, dir, active, registered_at); baselined_at stays null
next detection tick, for an active watch with baselined_at null:
  list and read every top-level *.md
  any failure (directory missing, a file unreadable) → write nothing, log one WARNING when the
      reason changes, retry next scan
  success → one transaction: a detected_reviews row per file (outcome = baseline), set baselined_at
a watch is scanned for new reviews only once baselined_at is set
```

The baseline is taken by the tenant, not by the inbox apply, so the store does no filesystem reads. It is all or nothing: a partial baseline would let a file it missed be ingested later as new, out of order. A file deleted between listing and read is dropped from the baseline. Baselining at registration keeps old rounds out; ingesting them in directory order would give them `recorded_seq` values in the wrong order, and 104's "previous round" lookup reads `recorded_seq`.

**Detecting a review** (one `ReviewDetectionTenant.tick`, at most once per `review_scan_interval_seconds`):

```
for each active, baselined watch in each open project:
  if the project has an unresolved journal entry of a review-producing kind → skip it this tick
  for each DetectedFile from DirectoryReviewSource (top-level *.md, settled):
    digest = sha256(bytes)
    (project, path, digest) already in detected_reviews → continue
    parse with 105's parse_review_artifact
      parse error → record_detection(outcome=unparseable, detail=error); continue
    attribution = attribute_review(slice nodes of the project, parsed.slice)
      zero or several → record_detection(outcome=unattributed, detail=candidates); continue
      exactly one     → one transaction:
                          record_verdict(to_verdict_input(parsed, node_id, upstream_version=label))
                          record_detection(outcome=ingested, verdict_id, node_id)
```

**Settled** means the file's `(size, mtime_ns)` is unchanged since the previous scan. It stops a half-written file from being parsed. Detection latency is about two scan intervals.

**Filesystem calls are unbounded.** Directory listing, `stat`, and reads run inside the synchronous loop with no timeout, like the rest of 102's loop. A watched directory on a stalled network mount hangs the tick. Watched directories are expected to be local; 102's standing remedy applies.

**Version label:** the frontmatter's stamp when Squadron starts writing one; until then, the `sq --version` label captured **once at process start-up**, before the loop, next to recovery; if that fails, the explicit unavailable marker 102 uses for `cf --version`. No tick starts a subprocess. A Squadron upgrade while the process runs is not reflected until restart; `evidence-contract.md` says the label is what the process observed at start-up.

### State Management

All durable state is in each project store:

- `changes`: append-only. `seq` is the cursor.
- `review_watches`: one row per registered directory.
- `detected_reviews`: one row per `(path, digest)` seen, with its outcome. This is what makes restart harmless: a file already in the ledger is never parsed again.

The only in-memory state is the tenant's last-scan signatures and scan time. Losing them on restart costs one extra settle interval.

## Technical Decisions

**D1 — The feed is a change log in the store, written in the mutation's transaction.** *(PM — ratified 20260928.)* A change and its feed row commit together or not at all, so the feed can never show a change the store does not have, or miss one it does. Order is `seq`, per project, and it matches commit order because the resident process is the sole writer. Rejected: an in-memory event bus in the process. It loses events on crash and gives a subscriber that was down no way to catch up.

**D2 — Subscribers follow the log themselves; the process runs no server.** *(PM — ratified 20260928.)* `follow()` is a blocking iterator. It wakes on SQLite's `PRAGMA data_version`, which changes only when another connection commits, so an idle check costs one pragma read.

*How this sits against "Push, not poll."* That goal is about **inbound** signals: the process should learn that CF changed, a Squadron run finished, or a human replied without polling. This slice meets it for the two inbound signals it owns (replies through the inbox; PM-launched reviews through the tenant). The outbound feed is a different surface, and `follow()` does check a counter on an interval; the design says so plainly rather than calling it push. What the goal rules out, a subscriber re-reading or recomputing state to find out whether anything changed, does not happen. Polling is accepted for followers on the same machine as the store. Real push belongs at the network edge: slice 109 serves the feed as a live stream by tailing this same log through `follow()`.

- *Why not a Unix socket served by a tenant:* the loop is synchronous (102, D2); serving sockets from it means non-blocking accept and send, per-connection buffers, and a slow-subscriber policy inside the process that owns crash recovery. The log would still be needed for catch-up.
- *What it costs:* a change reaches a follower within `follow_interval_seconds` (default 0.25), not instantly. The contract states the bound.
- *Works with the process down:* a follower reads what was committed and waits.

**D3 — Detection scans directories on an interval, in a tenant.** No file-watching library. FSEvents and inotify deliver events on a thread, and the tenant would still have to reconcile them against a scan after any restart. A top-level listing of one reviews directory every 2 seconds is a few dozen `stat` calls. Non-recursive: Squadron writes to the top level, and `archive/` holds rounds already seen.

**D4 — A review attaches to its slice node.** *(PM — ratified 20260928.)* The attribution rule: the one node in the project with `kind == slice` and `cf.slice_name` equal to the frontmatter's `slice`. Zero or several matches is `unattributed`, recorded with the candidate ids, and nothing is written to any node.

- **One signature:** `attribute_review(slice_nodes: Sequence[Node], slice_name: str) -> Attribution`, with `Attribution(node_id: str | None, candidates: tuple[str, ...])`. It is pure; the caller reads the project's slice nodes. 120 calls the same function.
- It needs nothing new on the node. Slice, tasks, and code reviews on one slice node stay separate series because 104's `finding_changes` groups by `review_type`.
- **Initiative 120 must attach the reviews it launches with the same rule**, or the Runner's rounds and detected rounds split across two nodes. Recorded in `evidence-contract.md`.
- Rejected: attaching to gate nodes. Nothing on a node says which review type a gate is for; that is 120's node-model decision.
- An unattributed review does not create a blocked node. There is no node to block, and creating one would invent tree structure. It is on the feed and in `inspect detections`.
- *Unattributed is terminal for detection; recovery is by hand.* The file's `(path, digest)` is in the ledger, and retrying later would record old rounds after newer ones. Once the right slice node exists, the PM runs `amoeba inspect detections --outcome unattributed`, then `amoeba ingest review --node ID` (105) on each file, oldest round first. The ledger row keeps the parsed-content id (`record_id`), so the listing shows `recorded_since` once that is done, and ingesting twice is a no-op.

**D5 — The Runner owns the reviews it launches; detection defers, then skips.** *(PM — ratified 20260928.)*

- *Defer:* while a project has an **unresolved** journal entry of a review-producing command kind, the tenant does not scan that project. "Unresolved" is literal: an entry stays unresolved, and so keeps deferring, whatever recovery did around it (including turning it into a `blocked_on_human` node). The set of review-producing kinds is defined once in `journal_models.py` (today `{SQ_RUN}`; 120 adds its review command kind).
- *Deferral is visible, not silent.* The tenant logs one WARNING when it starts deferring a project and one INFO when it resumes. `inspect watches` shows `deferred` for any active watch whose project has an unresolved review-producing entry; the listing computes that from the journal, so it needs no tenant memory. Deferral has no timeout: a stuck entry is the Runner's problem to resolve, and the listing is how the PM sees it.
- *Skip:* when the Runner records a review from a file, it marks that `(path, digest)` `runner_issued` in the ledger. Detection skips anything already in the ledger.
- A PM review that finishes while the Runner has one in flight is detected a few seconds late. Accepted.

*What the ordering rests on.* Tenant registration order does **not** matter.

1. **No two tenants run at once.** The loop is synchronous (102, D2). If that changes, this rule must be revisited.
2. **The Runner journals before it launches** (102's command-before-result rule), so any file a Runner-launched review writes appears while its entry is open.
3. **The Runner marks the ledger no later than it resolves the entry, in one transaction:** record the verdict, mark `runner_issued`, resolve the entry. Otherwise the next tick takes the file as external. A requirement on 120, stated in `evidence-contract.md`; the method that makes it one call is deferred (see Deferred).
4. **Recovery runs before any tenant ticks** (102). Recovery can resolve an entry by observation without the Runner having marked the file; that file is then detected as external, and still lands once, because of 5.
5. **The Runner records its reviews from the artifact through 105's parser**, so its record id and detection's are the same parsed-content digest. Any overlap is a `record_verdict` retry, a no-op. Also a requirement on 120.

**D6 — One interface for where reviews come from.** `ReviewSource.poll() -> Sequence[DetectedFile]`, where `DetectedFile` is `(path, bytes, observed_at)`. `DirectoryReviewSource` is the only implementation. An S8 event source implements the same method; the tenant, ledger, attribution, and feed do not change. The ledger key stays `(path, digest)`, since S8 would still name a file.

`DirectoryReviewSource` handles file-level races itself, so the tenant only sees whole files it could read:

| Case | What happens |
| --- | --- |
| Listed, then gone before `stat` or read | Dropped from this scan, its remembered signature forgotten. No ledger row: a file that is gone is not a review. If it returns, it settles again from scratch. |
| Changed between the settle check and the read | The digest is taken from the bytes actually read, so what is recorded matches what was parsed. If it keeps changing, the next scan waits for it to settle again. |
| Unreadable (`PermissionError`) | One WARNING per file until readable, then skipped. Not a ledger row: nothing was examined. |
| Not a regular file, or not `*.md` | Ignored. |

**D8 — Changes are emitted by SQLite triggers, not by writer code.** A trigger on each tracked table (`nodes` insert and status update, `verdicts` insert, `messages` insert, `detected_reviews` insert) writes the `changes` row in the same transaction as the write that fired it. No writer method changes.

- *Why:* emission in writer code is only as complete as the list of writers. That list is longer than it looks: recovery (102) writes escalation messages outside the inbox. A trigger fires for every write to its table, whoever makes it, including paths that do not exist yet.
- *Payloads* are built with `json_object` from the row. `recorded_at` is copied from the row's own timestamp column, so the feed and the store never disagree on when something happened. The node-status trigger fires only `WHEN old.status IS NOT new.status`. The detection trigger fires only `WHEN new.outcome NOT IN ('baseline', 'runner_issued')`.
- *The cost:* `ChangeKind` and `DetectionOutcome` values appear as literals in the migration's SQL as well as in the enums. A shipped migration is frozen. The invariant test ties them together: a drifted literal fails its "every kind appears" check.
- *Submission outcomes are not their own `ChangeKind`; their effects are.* 103 named `inbox_submissions.applied_seq` as a possible feed source. This slice adds no trigger on `inbox_submissions`: every kind of submission resolves into a row on a tracked table, which fires its own trigger. A *rejected* submission lands nothing, so a subscriber learns of it only by reading `submission(id)` (103). Accepted as a gap for rejections. **103's design document is not edited** (it is a completed slice and stays the record of what it shipped); this correction is recorded here and in `feed-contract.md`.
- *Rejected:* an `_emit_change` call in each writer method; its only guard would be a test of the writers it knows about.

### Patterns and Conventions

**Word lists** (`StrEnum`, defined once in `feed_models.py`):

- `ChangeKind`: `node_created`, `node_status_changed`, `verdict_recorded`, `message_posted`, `review_detected`
- `DetectionOutcome`: `baseline`, `ingested`, `unattributed`, `unparseable`, `runner_issued`

**Change payloads** are small and fixed per kind. They say what changed, not the whole record.

| Kind | `node_id` | `subject_id` | payload |
| --- | --- | --- | --- |
| `node_created` | the node | the node | `kind`, `parent_id`, `status` |
| `node_status_changed` | the node | the node | `from`, `to` |
| `verdict_recorded` | the node | verdict id | `verdict`, `review_type`, `provider_failure` |
| `message_posted` | the node, or null | message id | `channel` |
| `review_detected` | the node, or null | ledger id | `outcome`, `path` |

`node_created` carries the initial status, so replaying the feed from seq 0 rebuilds each node's status without reading the store. `verdict_recorded` carries no trust label (computed on read, and a trigger cannot call that function). A change is emitted only when a row is actually inserted or a status actually changes: a retried `record_verdict` emits nothing. `baseline` and `runner_issued` detections emit no change.

**Feed coverage is bounded.** The feed announces node, verdict, message, and detection changes only. It does not cover blocked-state resolution, finding status, or journal entries (node status changes already cover block and resolve). `feed-contract.md` says so plainly.

**The invariant test checks every tracked table.** It runs a scripted sequence through every write path that exists (create, block, resolve, status updates, verdicts, intents, a recovery escalation, detections of every outcome), then replays the feed from seq 0 and reconciles it against the store, table by table: node ids and rebuilt statuses, verdict ids, message ids, and ledger ids (excluding `baseline` and `runner_issued`). Every `ChangeKind` must appear at least once, so a kind whose trigger was never written, or whose SQL literal drifted from the enum, fails. A later write path is covered because its rows fire the same triggers; a new **table** needs a new `ChangeKind`, which fails the last check until a trigger and a script step are added.

**Errors.**

- A watched directory that is missing or unreadable logs one ERROR when it goes bad and one INFO when it recovers. It does not stop the process: a PM deleting a checkout is not a sick store. `inspect watches` shows `unreachable`.
- A parse failure is an outcome, not an exception.
- **A store exception while recording a detection is logged at ERROR and re-raised: the process stops and the operator intervenes.** A store that cannot record a row is sick, and continuing past it would hide that. No attempts counter, no parked state.

**Watch states** (`inspect watches`, computed on read): `unreachable` (directory cannot be listed now), `baseline_pending` (`baselined_at` null), `deferred` (D5), `ok`, in that precedence order; an inactive watch shows `inactive`.

**Settings** (added to `ProcessSettings`, with CLI flags): `review_scan_interval_seconds = 2.0`, `sq_timeout_seconds = 10.0`. The follower's `follow_interval_seconds = 0.25` and `feed_batch_size = 500` live in a `FeedSettings` dataclass in `amoeba.feed`, since followers run outside the process. The parent architecture sets no numeric targets; these are sized to the work (a review takes minutes, so seconds of detection delay are invisible; a status view should feel live at four pragma reads a second; `sq_timeout_seconds` matches `cf_timeout_seconds` and bounds start-up only). Only the follower's interval is a contract promise: "within `follow_interval_seconds` of the commit, plus the time to read the new rows."

## Implementation Details

### API Contracts

**Store additions (exported from `amoeba.store`):**

| Method | Effect |
| --- | --- |
| `changes(project_id, *, after: int = 0, limit: int) -> list[Change]` | Changes with `seq > after`, in order. |
| `watches(project_id) -> list[ReviewWatch]` | Registered directories. |
| `detections(project_id, *, outcome=None) -> list[DetectedReview]` | The ledger, in detection order. |
| `record_detection(DetectionInput) -> DetectedReview` | In-process only. Idempotent on `(project_id, path, digest)`. |

`attribute_review` is the pure function in D4, not a store method. `Change` is `(seq, project_id, kind, node_id | None, subject_id, payload: Mapping, recorded_at)`.

**Follower (`amoeba.feed`):** `follow(store_dir, project_id, *, after: int, settings: FeedSettings, stop: Callable[[], bool] | None = None) -> Iterator[Change]`. Failure behavior per the table under Data Flow.

**Delivery guarantees** (`docs/feed-contract.md`):

- Every committed change appears exactly once in the log, in commit order, with no gaps in `seq`.
- A follower that resumes with its last seen `seq` gets every later change once. Whether a subscriber *acts* on each change once depends on when it saves its cursor: saving **after** acting gives at-least-once; saving **before** gives at-most-once. The contract tells subscribers to save after acting and make handling safe to repeat.
- The feed says a change happened. It is not the source of truth for current state; the store is.
- Nothing is ever deleted from `changes` in this slice.

**Inbox, the `watch_reviews` kind:** payload `reviews_dir: str` (absolute, validated by pydantic), `active: bool`. The effect upserts the watch and leaves `baselined_at` null on first activation. Reactivating a directory does not re-baseline: files that arrived while inactive are detected. A relative path is quarantined as invalid.

**CLI:**

| Command | What it does |
| --- | --- |
| `amoeba feed --project ID [--after N] [--follow]` | Prints changes as JSON lines, keys as in `Change`. Without `--follow`, prints what exists and exits 0. With it, runs until interrupted. Works with the process running or stopped. |
| `amoeba submit watch-reviews --project ID --by NAME --reviews-dir PATH --active true\|false` | From the payload model, under 104's flag rule. |
| `amoeba inspect watches --project ID` | `reviews_dir, active, registered_at, baselined_at, state`. |
| `amoeba inspect detections --project ID [--outcome O]` | `detected_at, outcome, path, node_id, verdict_id, record_id, recorded_since, detail`. `recorded_since` is true when a verdict with that `record_id` now exists, however it got there. |

### Database / Storage Schema

Migration `006_change_feed_and_detection.sql`, `EXPECTED_SCHEMA_VERSION` 6. Nothing to backfill: the feed of an upgraded store starts empty.

- **`changes`:** `seq` (INTEGER PRIMARY KEY AUTOINCREMENT), `project_id`, `kind`, `node_id` (nullable, no FK so a feed row never blocks a future node deletion), `subject_id`, `payload` (JSON text), `recorded_at`. Index on `(project_id, seq)`.
- **`review_watches`:** `project_id`, `reviews_dir`, `active` (INTEGER), `registered_at`, `baselined_at` (nullable), `updated_at`. Primary key `(project_id, reviews_dir)`.
- **`detected_reviews`:** `id` (INTEGER PRIMARY KEY AUTOINCREMENT), `project_id`, `path`, `digest`, `outcome`, `node_id` (nullable FK), `verdict_id` (nullable FK), `record_id` (nullable: the parsed-content id from 105, set for every file that parsed), `detail`, `detected_at`. UNIQUE `(project_id, path, digest)`.

`verdicts` is not touched.

## Integration Points

### Provides to Other Slices

- **110:** the feed, so the end-to-end proof can assert subscribers saw the whole sequence, including across a restart.
- **108:** the change log and trigger convention. 108 adds a `cf_snapshots` table with its own trigger and a `cf_project_changed` kind, and extends the invariant test.
- **Initiative 120:** `attribute_review`, `record_detection(outcome=runner_issued)`, and the review-producing kinds set. 120 takes on D5 points 3 and 5, and D4's attribution rule; its slice design lists them as prerequisites. It also builds the one-transaction report-back (Deferred).
- **109:** `follow()`, which the network API streams to remote subscribers. 109 also adds `read_transaction()` and `change_head()` (Deferred).
- **Initiative 160:** `follow()` and `amoeba feed` for the Translator surface and the notification bridge, locally or through 109.

### Consumes from Other Slices

- **101–104** through their documented contracts. The changes are additive: triggers on `nodes`, `verdicts`, and `messages` (no writer code changes), `SubmissionKind` gains `watch_reviews`, `ProcessSettings` gains two fields, `amoeba start` registers a second tenant, and `LISTINGS` gains two entries. The test that pins the listing set is updated.
- **105:** the parser. If a file fails to parse because Squadron's shape moved, the outcome is `unparseable` with the parser's error, and the file is retried only if its bytes change. A parser fix is followed by re-ingesting those files with `amoeba ingest review`.

## Success Criteria

### Functional Requirements

- Every write to a tracked table emits its change in the same transaction. Feed replay from seq 0 reconciles with every tracked table and rebuilds every node's current status (the invariant test).
- No tick starts a subprocess; `sq --version` runs once, before the loop.
- A `resolution` submission applied by the process produces a `node_status_changed` change from the blocked status to `runnable`.
- A follower started with `--after N` prints exactly the changes after N. Killed and restarted with its last printed seq, it prints the rest with no gap and no repeat, and the `changes` table is unchanged by either.
- `amoeba feed --follow` started while the process is stopped prints new changes once the process starts and applies submissions.
- Follower failure table: a schema-version mismatch and an unknown project raise before yielding; a busy read is retried; `stop` returning true ends the iterator.
- A real Squadron review file copied into a registered directory is recorded as a verdict on the matching slice node, with `source: artifact_frontmatter`, the file's path as `source_path`, and a ledger row `ingested`. A `verdict_recorded` and a `review_detected` change follow.
- The captured provider-failure file is recorded with standing `provider_failure`.
- The same review hand-edited with `resolution:` keys after detection produces no second verdict.
- A file with no matching slice node is `unattributed` with its candidate ids; with two matching nodes, both are listed. Nothing is written to a node. An `unparseable` file does not fall through to attribution.
- A non-review markdown file is `unparseable` and is not retried until its bytes change.
- Files present at registration are `baseline` and never ingested. A directory registered before it exists shows `unreachable`, then is baselined on the first scan that can list it. With one unreadable file present, no baseline rows are written until it is readable; then the whole directory is baselined at once.
- An `unattributed` file ingested by hand after its slice node exists shows `recorded_since` true, and a second ingest records nothing.
- While the project has an unresolved `SQ_RUN` journal entry, a new file is not processed and `inspect watches` shows `deferred`; after the entry resolves, the file is processed.
- A file already marked `runner_issued` is never ingested.
- Restarting the process re-ingests nothing.
- A watched directory that is removed shows `unreachable`; the process keeps running and resumes when it returns.
- A file deleted between listing and read produces no ledger row and no error; restored, it is detected normally.
- A store exception while recording a detection is logged at ERROR and stops the process.

### Technical Requirements

- Each word list is a `StrEnum` defined once. All SQL is in `sql_feed.py`. The attribution rule and the review-producing kinds set each have one definition.
- The store imports nothing from `amoeba.upstream`, `amoeba.process`, or `amoeba.feed`.
- The follower opens the store read-only; the writer guard is unchanged except for adding any demo script to its permitted list, as 103 and 104 did.
- Tests use real review files from `tests/fixtures/sq_reviews/`, including the captured provider failure. No hand-built review stands in for a real one.
- A version-5 store with nodes, journal entries, submissions, messages, and verdicts upgrades to 6 intact.
- `ruff`, `pyright` strict, and the full suite are clean. Files stay near 300 lines.

### Integration Requirements

- End to end through the real CLI as subprocesses: create a project, seed a slice node, register a directory, start a follower, copy two real review rounds in, `kill -9` the process, start it, copy the provider failure in. The follower's output and read-only inspection agree, and nothing is recorded twice.
- `docs/feed-contract.md` is enough for initiative 160's slice design to consume the feed without reading the code.

### Verification Walkthrough

Draft; refined with real output when Phase 6 completes. Run in **bash** from the repository root. Nothing outside the process creates nodes until initiative 120, so `scripts/demo_detection.py` (new, lock-taking, refuses while the process runs, like `demo_evidence.py`) seeds a slice node with `cf.slice_name = resident-process-and-recovery` and a `blocked_on_human` node, and prints both ids. Review files come from 104's captured task-review series in `tests/fixtures/sq_reviews/`.

1. **Follow the feed.** Start the process, create a project, run the demo script, then `amoeba feed --project demo --follow` in a second terminal. It prints two `node_created` lines and the blocked node's `node_status_changed`, then waits.
2. **A human reply is a change.** `amoeba submit resolution ...` on the blocked state. The follower prints `node_status_changed` to `runnable` within a second.
3. **Register a directory; files already there are baseline.** Copy one review in, `amoeba submit watch-reviews`, wait one scan. `inspect watches` shows `ok` with `baselined_at` set; `inspect detections` shows one `baseline` row; no verdict, no feed line.
4. **A PM-launched review is detected.** Copy two further rounds in a few seconds apart. Within about 5 seconds each produces `verdict_recorded` and `review_detected` (`ingested`); `inspect verdicts --json` shows `source: artifact_frontmatter` and `source_path` pointing into the watched directory. Copy the captured provider failure in: standing `provider_failure`.
5. **What detection refuses to guess.** Copy a review for a slice with no node: `unattributed`, no verdict. `echo '# not a review' > notes.md`: `unparseable`.
6. **Hand edits and restarts write nothing twice.** Add a `resolution: accepted` line to a detected file, `kill -9` the process, start it. `inspect detections` gains one `ingested` row pointing at the **same** `verdict_id`; no new `verdict_recorded`.
7. **The invariant, automatically:** `uv run pytest tests/store/test_feed_invariant.py tests/cli/test_detection_end_to_end.py -v`.

## Risk Assessment

### Technical Risks

- **A write path that does not emit.** The feed silently stops matching the store.
- **Attribution depends on 120 following the same rule.** If the Runner attaches its reviews elsewhere, detected and Runner-launched rounds of one slice split into two series.
- **Multi-part task reviews share a series** until the `source_document` follow-up lands (Deferred).

### Mitigation Strategies

- Emission is by trigger (D8), so no write path can skip it, and the invariant test requires every `ChangeKind`.
- The attribution rule is exported and named in `evidence-contract.md`; 120's slice design lists it as a prerequisite.

## Implementation Notes

### Development Approach

1. Migration 006 with its triggers, `feed_models.py`, `sql_feed.py`, and mapping. The invariant test and the 5 → 6 upgrade test. Riskiest piece; depends only on 101–104.
2. `changes`; `amoeba.feed.follow` and `amoeba feed`. Follower tests: resume, process stopped, killed follower, the failure table.
3. `watch_reviews` kind with baselining; `watches` and `detections` read methods; `record_detection`.
4. `attribute_review` with its table of cases (zero, one, several, wrong kind).
5. `ReviewSource`, `DirectoryReviewSource` with the settle rule, and `ReviewDetectionTenant` with the defer rule, against real fixtures. Requires 105.
6. The two listings, `start` wiring, `scripts/demo_detection.py`, the end-to-end CLI test, docs, and `CHANGELOG`.

Steps 1–4 do not need 105. Test each step right after building it; commit after each.

### Special Considerations

- **Tick budget.** A tick makes at most one pass over each active watch and returns. Parsing a review is milliseconds, and registration baselines what is already there, so a flood of new files is not a case that exists.
- **Paths are stored absolute and as given.** No symlink resolution. Registering the same directory under two spellings is two watches; the ledger's digest makes the second a no-op for verdicts but not for ledger rows. Documented, not handled.
- **The feed is readable by anyone who can read the store.** Same trust boundary as the store. No payload carries review text, only ids, statuses, and paths.
