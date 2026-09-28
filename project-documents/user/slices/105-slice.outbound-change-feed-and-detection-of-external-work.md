---
docType: slice-design
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101, 102, 103, 104, 108]
interfaces: [106, 107]
dateCreated: 20260928
dateUpdated: 20260928
status: not_started
---

# Slice Design: outbound-change-feed-and-detection-of-external-work

## Overview

The store changes, and nobody outside the process hears about it. A PM runs `sq review` by hand, and the store never learns the review happened. This slice fixes both, and nothing more:

1. **A change feed.** Every state change the store commits also appends one row to a per-project change log, in the same transaction. Subscribers read the log from a cursor they own and follow it as it grows. The Translator surface, a status view, and later Cowork all consume it the same way.
2. **Detection of reviews nobody in Amoeba launched.** A new tenant in the resident process watches registered review directories. A new review file is parsed with slice 108's parser, attached to its slice node, and recorded as a verdict with a detection ledger entry. A file it cannot parse or cannot attach is recorded as exactly that, never guessed.

Human replies already arrive through 103's inbox (`resolution` submissions). They need no watcher. Applying one flips a node's status, and that status change is on the feed, which is all "detecting a human reply" has to mean once 103 exists.

## Value

Developer value.

- The Translator and any status view get an ordered stream of what changed, with a cursor that survives restarts on both sides. No one re-reads the whole store to find out what moved.
- A PM-launched review, the field norm, lands in the store as a verdict with provenance, so the Runner (120) sees it without the PM typing an `ingest` command.
- A provider-failure file is recorded as a provider failure. A file that is not a review, or has no slice node to attach to, is visible in one listing.
- When Squadron ships a review-completed event (dependency S8), the file watcher is swapped out behind one interface. Subscribers see nothing change.

## Technical Scope

**Included**

- Migration `006` with three tables: `changes`, `review_watches`, `detected_reviews`.
- Change emission inside every existing write path: node creation, node status change (including block and resolve), verdict recorded, message posted, and detection outcomes.
- `amoeba.store` read API for the feed: `changes(project_id, *, after, limit)` and `change_head(project_id)`.
- `amoeba.feed`: a subscriber-side follower that yields changes after a cursor and waits for more. `amoeba feed --project ID [--after N] [--follow]` prints them as JSON lines.
- A `watch_reviews` inbox submission kind that registers or deactivates a review directory for a project.
- `ReviewDetectionTenant` in `amoeba.process`, with a `ReviewSource` interface and one implementation, `DirectoryReviewSource`.
- The attribution rule (review → slice node), defined once and exported for initiative 120.
- `source_document` on verdicts, and `finding_changes` grouping rounds by it (D7).
- `amoeba inspect watches` and `amoeba inspect detections`, registered in 102's listing registry.
- `docs/feed-contract.md`; updates to `store-contract.md`, `inbox-contract.md`, `process-contract.md`, `evidence-contract.md`, and `CHANGELOG.md`.

**Excluded**

- Context Forge events: slice 107.
- Review completion for commands the Runner issued. The Runner observes those at process exit (120). This slice only defers to it; see the ownership rule under Technical Decisions.
- Backfilling reviews that existed before a directory was registered. Use `amoeba ingest review` (108), oldest first.
- A server-side push transport (socket, HTTP). See D2.
- A cross-project feed. Each project has its own feed and cursor.
- Feed retention and compaction. Already in the slice plan's future work.
- Parsing anything other than Squadron review files.

## Dependencies

### Prerequisites

- **101:** `Store`, nodes and their `cf.slice_name` reference, the migration mechanism (`EXPECTED_SCHEMA_VERSION` 5 → 6).
- **102:** the tenant seam, `ProcessSettings`, the command journal (the ownership rule reads open entries), the listing registry, the writer guard, and the `cf --version` "label or explicit unavailable marker" pattern this slice reuses for `sq --version`.
- **103:** the inbox, its kind seam (member, payload model, effect), `amoeba submit`, and `resolution`, which is how human replies arrive. *Added at slice design:* the plan listed 101, 102, 104, 108, but registration and reply delivery both go through 103.
- **104:** `record_verdict`, its retry rule, the trust label, and `VerdictInput`.
- **108:** `parse_review_artifact` and `to_verdict_input`. 108 has no design yet; the two requirements below go into it.

### Interfaces Required

**From slice 108** (to be written into 108's design):

- `ParsedReview` exposes the frontmatter's `slice` as a field; attribution needs it. `to_verdict_input` carries `sourceDocument` into `VerdictInput.source_document` (D7).
- The default record id is a digest of the **parsed** review, not of the raw bytes. This repository edits review files by hand after Squadron writes them (`resolution:` and `resolvedBy:` keys, which the parser ignores). A raw-bytes digest would turn each such edit into a second verdict for one review. A parsed-content digest makes the edit a no-op, and makes `amoeba ingest review` and detection agree on the id for the same review.

**From the store:** the private writer methods (`_verdict_writer`, `_block_writer`, node writes in `nodes.py`, `_apply_intent`), each of which gains one emission call; `journal_entries` filtered to unresolved.

**What Squadron writes today** (from the files in `project-documents/user/reviews/`): one file per review at the top of the reviews directory, named `{index}-review.{reviewType}.{slice}[.part-N].md`. A new round overwrites the same name; the PM moves older rounds into `archive/` with a timestamp suffix by hand. No file carries the Squadron version or run id yet (squadron#139).

## Architecture

### Component Structure

```
src/amoeba/store/
  feed_models.py        ChangeKind, Change, DetectionOutcome, ReviewWatch, DetectedReview
  sql_feed.py           every statement and column name for the three tables
  mapping_feed.py       row → record mapping
  _change_writer.py     ChangeWriter mixin: _emit_change(...), used by every writer
  feed.py               FeedOperations mixin: changes, change_head, watches, detections,
                        record_detection
  attribution.py        attribute_review(nodes, slice_name) -> Attribution
  schema/006_change_feed_and_detection.sql
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
any writer (create_node, update_node_status, block, resolve, record_verdict, intent, detection)
  inside its existing transaction:
    write its own rows
    _emit_change(kind, node_id, subject_id, payload)   # INSERT INTO changes; seq assigned here
  commit                                               # both land, or neither
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

**Registering a directory:**

```
amoeba submit watch-reviews --project P --by pm --reviews-dir /abs/path --active true
  inbox apply: upsert review_watches(project, dir, active, registered_at)
  on first activation: every file already in dir → detected_reviews row, outcome = baseline
```

Baselining at registration keeps old rounds out. Ingesting them in directory order would give them `recorded_seq` values in the wrong order, and 104's "previous round" lookup reads `recorded_seq`.

**Detecting a review** (one `ReviewDetectionTenant.tick`, at most once per `review_scan_interval_seconds`):

```
for each active watch in each open project:
  if the project has an open journal entry of a review-producing kind → skip this project this tick
  for each DetectedFile from DirectoryReviewSource (top-level *.md, settled):
    digest = sha256(bytes)
    (project, path, digest) already in detected_reviews → skip
    parse with 108's parse_review_artifact
      parse error → record_detection(outcome=unparseable, detail=error)
    attribute_review(slice nodes, parsed.slice)
      zero or several → record_detection(outcome=unattributed, detail=candidates)
      exactly one     → one transaction:
                          record_verdict(to_verdict_input(parsed, node_id, upstream_version=label))
                          record_detection(outcome=ingested, verdict_id, node_id)
```

**Settled** means the file's `(size, mtime_ns)` is unchanged since the previous scan. It stops a half-written file from being parsed. Detection latency is about two scan intervals.

**Version label:** the frontmatter's stamp when Squadron starts writing one; until then, the output of one `sq --version` per scan that found new files; if that fails, the explicit unavailable marker 102 uses for `cf --version`. `evidence-contract.md` says this label is what the detector observed, not necessarily what wrote the file.

### State Management

All durable state is in each project store:

- `changes`: append-only. `seq` is the cursor.
- `review_watches`: one row per registered directory.
- `detected_reviews`: one row per `(path, digest)` seen, with its outcome. This is what makes restart harmless: a file already in the ledger is never parsed again.

The only in-memory state is the tenant's last-scan signatures and scan time. Losing them on restart costs one extra settle interval.

## Technical Decisions

### Technology Choices

**D1 — The feed is a change log in the store, written in the mutation's transaction.** *(PM pending.)* A change and its feed row commit together or not at all, so the feed can never show a change the store does not have, or miss one it does. Order is `seq`, per project, and it matches commit order because the resident process is the sole writer. Rejected: an in-memory event bus in the process. It loses events on crash and gives a subscriber that was down no way to catch up.

**D2 — Subscribers follow the log themselves; the process runs no server.** *(PM pending.)* `follow()` is a blocking iterator. It wakes on SQLite's `PRAGMA data_version`, which changes only when another connection commits, so an idle check costs one pragma read. The subscriber sees a stream; the waiting lives in one function.

*How this sits against "Push, not poll."* That design goal is about **inbound** signals: the resident process should learn that CF changed, a Squadron run finished, or a human replied without polling `cf next`, which recomputes gate state from disk on every call. This slice meets it for the two inbound signals it owns: human replies arrive through the inbox, and PM-launched reviews are detected by the tenant, not by the Runner calling anything. The outbound feed is a different surface. Inside the implementation, `follow()` does check a counter on an interval, and the design says so plainly rather than calling it push. What the goal rules out, a subscriber re-reading or recomputing state to find out whether anything changed, does not happen: an idle check reads one integer, and a busy one reads only the new rows. The PM decision is whether that is acceptable for the outbound surface or whether a real wake-up signal is wanted now. If it is, the smallest version fits behind `follow()` with no subscriber change: each follower binds a datagram socket in `{store_dir}/feed/`, and after any commit that emitted changes the process sends one empty datagram to each socket there, never blocking and unlinking any socket that refuses. The follower still reads the rows from the log. This design does not build it.

- *Why not a Unix socket served by a tenant:* the loop is synchronous (102, D2). Serving sockets from it means non-blocking accept and send, per-connection buffers, and a slow-subscriber policy, all inside the process that owns crash recovery. The log would still be needed for catch-up, so the socket would only add latency savings.
- *What it costs:* a change reaches a follower within `follow_interval_seconds` (default 0.25), not instantly. The contract states the bound.
- *Swap later without subscriber changes:* subscribers depend on `follow()` and the JSON-lines shape of `amoeba feed`, not on how waiting works.
- *Works with the process down:* a follower reads what was committed and waits.

**D3 — Detection scans directories on an interval, in a tenant.** No file-watching library. FSEvents and inotify deliver events on a thread, and the tenant would still have to reconcile them against a scan after any restart. A top-level listing of one reviews directory every 2 seconds is a few dozen `stat` calls. Non-recursive: Squadron writes to the top level, and `archive/` holds rounds already seen.

**D4 — A review attaches to its slice node.** *(PM pending.)* The attribution rule: the one node in the project with `kind == slice` and `cf.slice_name` equal to the frontmatter's `slice`. Zero or several matches is `unattributed`, recorded with the candidate ids, and nothing is written to any node.

- It needs nothing new on the node. Slice, tasks, and code reviews on one slice node stay separate series because 104's `finding_changes` groups by `review_type`, and multi-part task reviews stay separate by D7.
- It is defined once in `amoeba.store.attribution` and exported. **Initiative 120 must attach the reviews it launches with the same rule**, or the Runner's rounds and detected rounds split across two nodes and "what changed since last round" breaks. This is recorded in `evidence-contract.md`.
- Rejected: attaching to gate nodes. Nothing on a node says which review type a gate is for, and adding it is 120's node-model decision, not 105's.
- An unattributed review does not create a blocked node. There is no node to block, and creating one would invent tree structure. It is on the feed and in `inspect detections`.

**D5 — The Runner owns the reviews it launches; detection defers, then skips.** *(PM pending.)*

- *Defer:* while a project has an unresolved journal entry of a review-producing command kind, the tenant does not scan that project. The set of review-producing kinds is defined once in `journal_models.py` (today `{SQ_RUN}`; 120 adds its review command kind to it).
- *Skip:* when the Runner records a review from a file, it calls `record_detection(outcome=runner_issued, verdict_id)` for that `(path, digest)`. Detection skips anything already in the ledger.
- A PM review that finishes while the Runner has one in flight is detected a few seconds late. Accepted.

*What the ordering rests on.* The rule is only correct if all of these hold. Tenant registration order does **not** matter.

1. **No two tenants run at once.** The loop is synchronous (102, D2), so detection never observes the Runner halfway through a tick. This is 102's standing design; if it ever changes, this rule must be revisited.
2. **The Runner journals before it launches.** 102's command-before-result rule. So any file a Runner-launched review writes appears while its entry is open, and detection is deferred for that project.
3. **The Runner marks the ledger no later than it resolves the entry, in one transaction:** record the verdict, `record_detection(runner_issued)`, resolve the journal entry. If the resolve committed first and the Runner's tick ended before the mark, the next detection tick would take the file as external. This is a requirement on 120, stated in `evidence-contract.md`.
4. **Recovery runs before any tenant ticks** (102). A crash cannot leave a project deferred forever. It can, however, resolve an entry by observation without the Runner having marked the file. That file is then detected as external. It still lands once, because of 5.
5. **The Runner records its reviews from the artifact through 108's parser**, so its record id and detection's are the same parsed-content digest. Any overlap after a crash is then a `record_verdict` retry, a no-op. Also a requirement on 120.

**D6 — One interface for where reviews come from.** `ReviewSource.poll() -> Sequence[DetectedFile]`, where `DetectedFile` is `(path, bytes, observed_at)`. `DirectoryReviewSource` is the only implementation. An S8 event source implements the same method from Squadron's event; the tenant, ledger, attribution, and feed do not change. The ledger key stays `(path, digest)`, since S8 would still name a file.

`DirectoryReviewSource` handles the file-level races itself, so the tenant only ever sees whole files it could read:

| Case | What happens |
| --- | --- |
| Listed, then gone before `stat` or read (`FileNotFoundError`) | Dropped from this scan and its remembered size and timestamp forgotten. No ledger row: a file that is gone is not a review. If it comes back, it settles again from scratch. |
| Changed between the settle check and the read | The digest is taken from the bytes actually read, and the ledger key is that digest, so what is recorded always matches what was parsed. If the file keeps changing, the next scan sees a new size or timestamp and waits for it to settle again. |
| One file unreadable (`PermissionError`) | One WARNING per file until it becomes readable, then skipped. Not a ledger row, because nothing was examined. |
| Not a regular file (directory, socket), or not `*.md` | Ignored. |

**D7 — A review series is node, review type, and reviewed document.** *(PM pending; changes 104's contract, additively.)* Task reviews come in parts. The captured 102 series has `part-1` and `part-2` reviews, both `reviewType: tasks`, both for the same slice, reviewing different task files. Attached to one slice node under 104's rule, part 2's round would become part 1's "previous round", and `finding_changes` would report every part-1 finding as new and every part-2 finding as gone.

- `VerdictInput` and the `verdicts` table gain `source_document: str | None`, filled by 108's parser from the frontmatter's `sourceDocument`.
- `finding_changes` picks the previous round on the same node, same `review_type`, and same `source_document`, compared with `IS` so two nulls match. Every verdict recorded before this slice has a null `source_document`, so their series are unchanged.
- The `verdict` inbox payload gains the optional field.
- *How a finished slice's contract is changed.* 104 is complete, and its design document is not edited: it stays the record of what 104 shipped. The change is made and owned here. Migration 006 adds the column. 105's tasks change `VerdictInput`, the payload, and the previous-round query. 105 updates `evidence-contract.md` (the series definition) and adds a `CHANGELOG` entry naming it a change to 104's contract. 104's tests run unchanged and must pass, since every one of them records verdicts without a `source_document`. One new test covers the part-1 and part-2 case.
- Rejected: attaching each review to the node whose `cf.artifact_path` equals `sourceDocument`. It avoids the column, but depends on 120 creating a node per task file with a path spelled exactly as Squadron spells it. The slice name is the stable key; the document is only a series separator.

### Patterns and Conventions

**Word lists** (`StrEnum`, defined once in `feed_models.py`):

- `ChangeKind`: `node_created`, `node_status_changed`, `verdict_recorded`, `message_posted`, `review_detected`
- `DetectionOutcome`: `baseline`, `ingested`, `unattributed`, `unparseable`, `runner_issued`

**Change payloads** are small and fixed per kind. They say what changed, not the whole record; a subscriber that wants more reads the store.

| Kind | `node_id` | `subject_id` | payload |
| --- | --- | --- | --- |
| `node_created` | the node | the node | `kind`, `parent_id` |
| `node_status_changed` | the node | the node | `from`, `to` |
| `verdict_recorded` | the node | verdict id | `verdict`, `standing`, `review_type` |
| `message_posted` | the node, or null | message id | `channel` |
| `review_detected` | the node, or null | ledger id | `outcome`, `path` |

A change is emitted only when the writer actually inserts or updates. A retried `record_verdict` that returns the existing record emits nothing. `baseline` and `runner_issued` detections emit no change: nothing happened that a subscriber should act on.

**Emission is one call per writer, and a test proves none is missed.** The invariant test: run a scripted sequence through every write path (create, block, resolve, status updates, verdicts, intents), then replay the feed from seq 0 and rebuild each node's status from `node_created` and `node_status_changed`. It must equal the store's current node statuses. A new write path that forgets to emit fails this test.

**Errors.** A watched directory that is missing or unreadable logs one ERROR when it goes bad and one INFO when it recovers, and is shown in `inspect watches` as `unreachable`. It does not stop the process: a PM deleting a checkout is not a sick store. A parse failure is an outcome, not an exception.

An exception from the store while recording a detected file follows 103's bounded-failure rule, not just its re-raise. Re-raising alone would put the process in a crash loop: restart, see the same file, fail again.

- **Counter first.** Before the recording transaction, the tenant durably writes an attempts sidecar for that file: `{store_dir}/detection/attempts/{project_id}/{digest}.attempts.json`, the same `AttemptsSidecar` model and `write_durably` path `InboxTenant` uses. It lives under the supervisor directory, because the watched directory belongs to the PM and detection never writes into it.
- **Below the limit:** log at ERROR and re-raise, so the process stops and the operator hears about it.
- **At the limit** (`detection_max_attempts`): log at ERROR, leave the sidecar as the record that the file is parked, and move on. Detection skips any `(project, digest)` with a parked sidecar. `amoeba inspect detections` lists parked files alongside ledger rows, as `failed`, read from the sidecars, the way `inspect inbox` reads `failed/`. Removing the sidecar by hand retries the file.
- **On success:** the sidecar is deleted after the transaction commits. A crash in between leaves a recorded file and a leftover counter, and the next scan finds the file already in the ledger and deletes the counter.

`failed` is a listing state, not a `DetectionOutcome`: the store could not record the file, so the store has no row for it.

**Settings** (added to `ProcessSettings`, with CLI flags): `review_scan_interval_seconds = 2.0`, `sq_timeout_seconds = 10.0`, `detection_max_attempts = 3`. The follower's `follow_interval_seconds = 0.25` and `feed_batch_size = 500` live in a `FeedSettings` dataclass in `amoeba.feed`, since followers run outside the process.

The parent architecture sets no numeric targets, so these are this slice's choices, sized to the work:

- **Scan interval, 2 s, so detection within about 5 s.** A review takes minutes to run and a person reads the result; seconds of delay are invisible. Shorter only costs more `stat` calls.
- **Follow interval, 0.25 s.** A status view should feel live; one pragma read four times a second is nothing.
- **`sq --version` timeout, 10 s.** The same as the existing `cf_timeout_seconds`.
- **Attempts, 3.** The same reasoning as `inbox_max_attempts`: loud first, bounded after.

None of these is a promise in a contract except the follower's, which `feed-contract.md` states as "within `follow_interval_seconds` of the commit, plus the time to read the new rows." Each is one field, changed in one place.

## Implementation Details

### API Contracts

**Store additions (exported from `amoeba.store`):**

| Method | Effect |
| --- | --- |
| `changes(project_id, *, after: int = 0, limit: int) -> list[Change]` | Changes with `seq > after`, in order. |
| `change_head(project_id) -> int` | The last `seq`, or 0. Read it in the same read transaction as a state snapshot, then follow from it, to get "current state, then everything after". |
| `watches(project_id) -> list[ReviewWatch]` | Registered directories. |
| `detections(project_id, *, outcome=None) -> list[DetectedReview]` | The ledger, in detection order. |
| `record_detection(DetectionInput) -> DetectedReview` | In-process only. Idempotent on `(project_id, path, digest)`. |
| `attribute_review(store, project_id, slice_name) -> Attribution` | `Attribution(node_id | None, candidates: tuple[str, ...])`. |

`Change` is `(seq, project_id, kind, node_id | None, subject_id, payload: Mapping, recorded_at)`.

**Follower (`amoeba.feed`):** `follow(store_dir, project_id, *, after: int, settings: FeedSettings, stop: Callable[[], bool] | None = None) -> Iterator[Change]`. Opens the store read-only. Raises `StoreError` subclasses as the store does; an unknown project raises before yielding anything.

**Delivery guarantees** (`docs/feed-contract.md`):

- Every committed change appears exactly once in the log, in commit order, with no gaps in `seq`.
- A follower that resumes with its last seen `seq` gets every later change once. Delivery to a subscriber is therefore at-least-once only if the subscriber saves its cursor before acting; the contract says to save after.
- The feed says a change happened. It is not the source of truth for current state; the store is.
- Nothing is ever deleted from `changes` in this slice.

**Inbox, the `watch_reviews` kind:** payload `reviews_dir: str` (absolute, validated by pydantic), `active: bool`. The effect upserts the watch. First activation baselines existing files inside the same transaction. Reactivating a directory does not re-baseline: files that arrived while inactive are detected. A relative path is quarantined as invalid.

**CLI:**

| Command | What it does |
| --- | --- |
| `amoeba feed --project ID [--after N] [--follow]` | Prints changes as JSON lines, one object per change, keys as in `Change`. Without `--follow`, prints what exists and exits 0. With it, runs until interrupted. Works with the process running or stopped. |
| `amoeba submit watch-reviews --project ID --by NAME --reviews-dir PATH --active true\|false` | From the payload model, under 104's flag rule. |
| `amoeba inspect watches --project ID` | `reviews_dir, active, registered_at, state` (`ok` / `unreachable`). |
| `amoeba inspect detections --project ID [--outcome O]` | `detected_at, outcome, path, node_id, verdict_id, detail`. |

### Database / Storage Schema

Migration `006_change_feed_and_detection.sql`, `EXPECTED_SCHEMA_VERSION` 6. Nothing to backfill: the feed of an upgraded store starts empty, and `change_head` is 0.

- **`changes`:** `seq` (INTEGER PRIMARY KEY AUTOINCREMENT), `project_id`, `kind`, `node_id` (nullable, no FK so a feed row never blocks a future node deletion), `subject_id`, `payload` (JSON text), `recorded_at`. Index on `(project_id, seq)`.
- **`review_watches`:** `project_id`, `reviews_dir`, `active` (INTEGER), `registered_at`, `updated_at`. Primary key `(project_id, reviews_dir)`.
- **`verdicts`:** gains `source_document` (TEXT, nullable). The previous-round index becomes `(project_id, node_id, review_type, source_document, recorded_seq)`.
- **`detected_reviews`:** `id` (INTEGER PRIMARY KEY AUTOINCREMENT), `project_id`, `path`, `digest`, `outcome`, `node_id` (nullable FK), `verdict_id` (nullable FK), `detail`, `detected_at`. UNIQUE `(project_id, path, digest)`.

## Integration Points

### Provides to Other Slices

- **106:** the feed, so the end-to-end proof can assert that subscribers saw the whole sequence, including across a restart.
- **107:** the change log as the place CF-sourced changes land; a CF event that updates a node emits through the same writers.
- **Initiative 120:** `attribute_review`, `record_detection(outcome=runner_issued)`, and the review-producing kinds set. The Runner may also follow the feed instead of re-querying. 120 takes on the requirements in D5, points 3 and 5: mark the ledger in the same transaction that resolves the journal entry, and record its reviews from the artifact through 108's parser.
- **Initiative 160:** `follow()` and `amoeba feed` for the Translator surface and the notification bridge.

### Consumes from Other Slices

- **101–104** through their documented contracts. The changes are additive: each private writer gains one emission call, verdicts gain `source_document` and `finding_changes` groups by it, `SubmissionKind` gains `watch_reviews`, `ProcessSettings` gains two fields, `amoeba start` registers a second tenant, and `LISTINGS` gains two entries. The test that pins the listing set is updated to the new set.
- **108:** the parser. If a file fails to parse because Squadron's shape moved, the outcome is `unparseable` with the parser's error, visible in `inspect detections`, and the file is retried only if its bytes change. A parser fix is followed by re-ingesting those files with `amoeba ingest review`.

## Success Criteria

### Functional Requirements

- Each write path emits its change in the same transaction. Feed replay from seq 0 rebuilds every node's current status (the invariant test).
- A `resolution` submission applied by the process produces a `node_status_changed` change from the blocked status to `runnable`.
- A follower started with `--after N` prints exactly the changes after N. Killed mid-stream and restarted with its last printed seq, it prints the rest with no gap and no repeat, and the `changes` table is unchanged by either.
- `amoeba feed --follow` started while the process is stopped prints new changes once the process starts and applies submissions.
- A real Squadron review file copied into a registered directory is recorded as a verdict on the matching slice node, with `source: artifact_frontmatter`, the file's path as `source_path`, and a ledger row `ingested`. A `verdict_recorded` and a `review_detected` change follow.
- The captured provider-failure file is recorded with standing `provider_failure`.
- With the captured 102 series detected on one slice node, `finding_changes` on part 1, round 2 names part 1, round 1 as the previous round, never a part-2 review. Verdicts recorded with no `source_document` keep 104's behavior.
- The same review hand-edited with `resolution:` keys after detection produces no second verdict.
- A file with no matching slice node is `unattributed` with its candidate ids; with two matching nodes, both are listed. Nothing is written to a node.
- A non-review markdown file is `unparseable` and is not retried until its bytes change.
- Files present at registration are `baseline` and never ingested.
- While the project has an open `SQ_RUN` journal entry, a new file is not processed; after the entry resolves, it is.
- A file already marked `runner_issued` is never ingested.
- Restarting the process re-ingests nothing.
- A watched directory that is removed shows `unreachable`; the process keeps running and resumes when it returns.
- A file deleted between listing and read produces no ledger row and no error; restored, it is detected normally.
- A store failure while recording one file stops the process below `detection_max_attempts`. At the limit the file is listed `failed` in `inspect detections`, later files are still detected, and the process keeps running. Deleting the sidecar retries it.

### Technical Requirements

- Each word list is a `StrEnum` defined once. All SQL is in `sql_feed.py`. The attribution rule and the review-producing kinds set each have one definition.
- The store imports nothing from `amoeba.upstream`, `amoeba.process`, or `amoeba.feed`.
- The follower opens the store read-only; the writer guard is unchanged except for adding any demo script to its permitted list, as 103 and 104 did.
- Tests use real review files from `tests/fixtures/sq_reviews/` (104's fixtures), including the captured provider failure. No hand-built review stands in for a real one.
- A version-5 store with nodes, journal entries, submissions, messages, and verdicts upgrades to 6 intact.
- `ruff`, `pyright` strict, and the full suite are clean. Files stay near 300 lines.

### Integration Requirements

- End to end through the real CLI as subprocesses: create a project, seed a slice node, register a directory, start a follower, copy two real review rounds in, `kill -9` the process, start it, copy the provider failure in. The follower's output and read-only inspection agree, and nothing is recorded twice.
- `docs/feed-contract.md` is enough for initiative 160's slice design to consume the feed without reading the code.

### Verification Walkthrough

Draft; refined with real output when Phase 6 completes. Run in **bash** from the repository root. Nothing outside the process creates nodes until initiative 120, so `scripts/demo_detection.py` (new, lock-taking, refuses while the process runs, like `demo_evidence.py`) seeds a slice node with `cf.slice_name = resident-process-and-recovery` and a `blocked_on_human` node, and prints both ids. The review files are 104's captured 102 task-review series in `tests/fixtures/sq_reviews/`: part 1 and part 2, round 1 (timestamped names) and round 2, where round 2's part 2 is a real provider failure.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
REVIEWS="$(mktemp -d)"
F=tests/fixtures/sq_reviews
P=102-review.tasks.resident-process-and-recovery
uv run amoeba start --sq-runs-dir "$(mktemp -d)" &
until uv run amoeba status | grep -q '^running'; do sleep 0.2; done
uv run amoeba submit create-project --project demo --by pm
uv run amoeba stop
read SLICE_NODE BLOCKED_NODE < <(uv run python scripts/demo_detection.py)
uv run amoeba start --sq-runs-dir "$(mktemp -d)" &
until uv run amoeba status | grep -q '^running'; do sleep 0.2; done
```

**1. Follow the feed.** In a second terminal, with the same `AMOEBA_STORE_DIR`:

```bash
uv run amoeba feed --project demo --follow
```

It prints two `node_created` lines and the blocked node's `node_status_changed` (`runnable` → `blocked_on_human`), then waits.

**2. A human reply is a change.** Take the blocked state's id from `uv run amoeba inspect blocked --project demo`, then:

```bash
uv run amoeba submit resolution --project demo --by pm --blocked-state-id "$BS" --detail approved
```

The follower prints `node_status_changed` from `blocked_on_human` to `runnable` within a second.

**3. Register a directory; files already there are baseline.**

```bash
cp "$F/$P.part-2.20260921T112635.md" "$REVIEWS/"
uv run amoeba submit watch-reviews --project demo --by pm --reviews-dir "$REVIEWS" --active true
uv run amoeba inspect detections --project demo
```

One row, `baseline`. No verdict, no feed line.

**4. A PM-launched review is detected.** Copy round 1 of part 1 in, as `sq review` would write it, then round 2 of part 1 a few seconds later:

```bash
cp "$F/$P.part-1.20260921T112529.md" "$REVIEWS/"
sleep 6
cp "$F/$P.part-1.md" "$REVIEWS/"
```

For each, within about 5 seconds, the follower prints `verdict_recorded` (`CONCERNS`, `stated`, `tasks`) and `review_detected` (`ingested`). `uv run amoeba inspect verdicts --project demo` shows both on `$SLICE_NODE`, and `--json` shows `source: artifact_frontmatter` and `source_path` pointing into `$REVIEWS`.

**5. Parts stay separate series.** `uv run amoeba inspect changes --project demo --verdict <round 2 id>` names round 1 of part 1 as the previous round. The two rounds share no keys, which is 104's rewording limit, so every round-2 finding is `new` and every round-1 finding is `gone`.

**6. A provider failure is a failure.** `cp "$F/$P.part-2.md" "$REVIEWS/"`. `inspect verdicts` shows it with standing `provider_failure`.

**7. What detection refuses to guess.**

- `cp project-documents/user/reviews/104-review.slice.findings-verdicts-and-provenance.md "$REVIEWS/"`. There is no `findings-verdicts-and-provenance` slice node, so `inspect detections --outcome unattributed` lists it with no candidates, and no verdict is recorded.
- `echo '# not a review' > "$REVIEWS/notes.md"`. Listed `unparseable` with the parser's error.

**8. Hand edits and restarts write nothing twice.** Add a `resolution: accepted` line to the frontmatter of `$REVIEWS/$P.part-1.md`. Then `kill -9` the process (pid from `amoeba status`) and start it again.

- `inspect detections` gains one `ingested` row for the edited file's new digest, pointing at the **same** `verdict_id` as before. The follower prints that `review_detected` line and no `verdict_recorded`.
- `inspect verdicts` still lists three verdicts.
- Stop the follower and restart it with `--after` its last printed seq. It prints nothing old.

**9. The invariant, automatically.**

```bash
uv run pytest tests/store/test_feed_invariant.py tests/cli/test_detection_end_to_end.py -v
```

## Risk Assessment

### Technical Risks

- **A write path that does not emit.** The feed silently stops matching the store, and subscribers act on stale state.
- **Attribution depends on 120 following the same rule.** If the Runner attaches its reviews somewhere else, detected and Runner-launched rounds of one slice split into two series.

### Mitigation Strategies

- The replay invariant test covers every write path and fails on a missed emission. Emission sits in the private writers, not in public methods, so an inbox apply and a direct call share it.
- The attribution rule is exported and named in `evidence-contract.md` as the rule 120 uses. 120's slice design lists it as a prerequisite.

## Implementation Notes

### Development Approach

1. Migration 006, `feed_models.py`, `sql_feed.py`, mapping, `_emit_change`, and emission in every existing writer. The replay invariant test and the 5 → 6 upgrade test. Riskiest piece; depends only on 101–104.
2. `changes` and `change_head`; `amoeba.feed.follow` and `amoeba feed`. Follower tests: resume, process stopped, killed follower.
3. `watch_reviews` kind with baselining; `watches` and `detections` read methods; `record_detection`.
4. `attribute_review` with its table of cases (zero, one, several, wrong kind).
5. `ReviewSource`, `DirectoryReviewSource` with the settle rule, and `ReviewDetectionTenant` with the defer rule, against real fixtures. Requires 108.
6. The two listings, `start` wiring, `scripts/demo_detection.py`, the end-to-end CLI test, docs, and `CHANGELOG`.

Steps 1–4 do not need 108 and can start before it lands. Test each step right after building it; commit after each.

### Special Considerations

- **Tick budget.** A tick scans at most one pass over each active watch and returns. Parsing a review is milliseconds; a directory with hundreds of new files at once is not a case that exists, because registration baselines what is already there.
- **Paths are stored absolute and as given.** No symlink resolution. Registering the same directory under two spellings is two watches; the ledger's digest makes the second a no-op for verdicts but not for ledger rows. Documented, not handled.
- **The feed is readable by anyone who can read the store.** Same trust boundary as the store today. No payload carries review text, only ids, statuses, and paths.
