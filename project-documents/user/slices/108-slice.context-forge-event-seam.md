---
docType: slice-design
slice: context-forge-event-seam
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101, 102, 103, 106, 107]
interfaces: [109, 110]
dateCreated: 20261015
dateUpdated: 20261015
status: not_started
---

# Slice Design: context-forge-event-seam

## Overview

Context Forge (CF) moves a project's phase, slice, and task pointers whenever any client writes: the `cf` CLI, the MCP server, another agent. Amoeba hears about none of it unless it asks. This slice makes those moves records and feed entries. It does not poll `cf next`, and it changes nothing in CF.

CF keeps every project in one file, `projects.json`. Each write goes to a temp file that is then renamed over the original, so every write by any client atomically replaces the file. A new tenant in the resident process checks that file's signature on an interval. When the file changes, the tenant parses it and compares each **linked** CF project with that project's last stored snapshot. When they differ, it records a new snapshot, and 106's trigger convention puts one `cf_project_changed` change on the feed. A PM links an Amoeba project to a CF project by CF's project id, through an inbox submission.

This is all of the scope Amoeba took over from CF initiative 220. The long-running process is 102's. Notifications and subscriptions are 106's feed. Watching the file replaces event emission on CF's side.

## Value

Developer value.

- The Runner (120) and any feed subscriber learn that a pointer moved within seconds of any client moving it, and the change names the fields that moved, with their old and new values.
- No change can be missed. Each check compares against the stored snapshot, not against anything held in memory, so changes made while the process was down show up on the first check after it starts.
- A CF file Amoeba cannot read, or no longer recognizes, is recorded and visible. It is never smoothed over.

## Technical Scope

**Included**

- Migration `008` with two tables, `cf_links` and `cf_snapshots`, and one feed trigger for `cf_snapshots`.
- `amoeba.upstream.context_forge`: a parser that reads `projects.json` into the fields Amoeba watches (the "projection"), and a pure diff function. The documented shape is the only shape it accepts.
- `CFWatchTenant` in `amoeba.process`.
- One inbox kind, `link_cf_project`, through 103's three-part seam.
- Store operations: `cf_links`, `cf_snapshots`, `record_cf_snapshot`.
- `ChangeKind.CF_PROJECT_CHANGED`. 106's invariant test gains steps that write snapshots.
- Listings: `amoeba inspect cf-links` and `amoeba inspect cf-snapshots`, each taking `--project` only.
- Settings: `cf_data_dir`, with a CLI flag, and `cf_scan_interval_seconds`, with no flag.
- A captured real `projects.json` fixture.
- `docs/context-forge-contract.md` (the observed shape). The other contract docs and `CHANGELOG.md` gain only the deltas: the kind, the listings, the setting, and the methods. They do not restate 106's trigger convention or 102's process semantics.

**Excluded**

- **Any change to Context Forge.** No daemon, no wire protocol, no event emission.
- **Interpreting a change.** The snapshot records what CF holds. Deciding what a moved pointer means (for example, that a slice is ready for review) is the Runner's job (120).
- **Who made a change.** CF does not record the writer, and this slice does not guess (D8).
- **Fields outside the projection.** `customData`, `template`, `createdAt`, `updatedAt` (kept only as provenance), and legacy keys produce no changes (D2).
- **Review-gate state.** CF recomputes it from artifact frontmatter on every call, and it is not stored in `projects.json`. The Runner reads it through `workflow_status` (120).
- **Writing to CF**, now or later. The architecture forbids editing `projects.json` directly.
- **Snapshot retention or compaction.** Same position as the feed (106).

### Deferred

Cut at design review for proportionality. None of this is required by the slice plan.

- **Unlinking or deactivating a link** (GitHub issue #7). A link is permanent in this slice.
- **Listing filters and computed columns.** `--cf-project-id` and `--outcome` on `inspect cf-snapshots`, and `last_outcome` or `last_observed_at` on `inspect cf-links`, are not built. Nothing consumes them, and `--json` gives the full rows.

## Dependencies

### Prerequisites

- **101:** `Store`, the migration mechanism (`EXPECTED_SCHEMA_VERSION` from 7 to 8), and the store's timestamp convention.
- **102:** the tenant seam (`Tenant`, the host protocol), `ProcessSettings` and its CLI flags, the listing registry, the writer guard, and the `cf --version` label with its explicit unavailable marker (`version_label`, `cf_readback.capture_version_label`).
- **103:** the submission-kind seam (a `SubmissionKind` member, a payload model in `amoeba.inbox.envelope`, a `KIND_EFFECTS` entry) and `amoeba submit`.
- **106:** the `changes` table, its trigger convention (D8 there), `ChangeKind`, and the feed invariant test. `watch_reviews` and `ReviewDetectionTenant` set the pattern this slice follows.
- **107 (ordering only):** migration 007. This slice takes 008. The first implementation task checks that 107 is merged and stops for the PM if it is not. 107 was added to the slice plan's dependency list at design time.

No new packages.

### Interfaces Required

**From Context Forge:** only the file. Its location is CF's data directory: `CONTEXT_FORGE_DATA_DIR`, or `~/.config/context-forge` by default. The file is replaced by temp-file-and-rename (`FileStorageService`, `packages/core/src/storage/FileStorageService.ts`). CF also writes `projects.json.tmp` and `projects.json.backup` next to it. Both are ignored.

**Observed shape** (CF 0.19.11, observed 20261015; a dated observation, not a version dependency):

- The top level is a JSON array of project objects. Each object has a string `id` (for example `project_1781844717321_1gukaohbc`).
- Project-level pointer fields, all optional strings: `name`, `projectPath`, `developmentPhase`, `instruction`, `fileArch`, `fileSlicePlan`, `fileSlice`, `fileTasks`.
- `worktrees`: optional. When present, it is an array of worktree objects, each with a string `id` (`wt_{timestamp}_{random}`). Since CF began scoping work to worktrees, the live pointers sit here, not at the project level. In this repository's own record, the project-level `developmentPhase` and `fileSlice` are empty strings, and the `default` worktree holds `developmentPhase`, `activeSlice`, and `activeTaskFile`. Worktree fields, all optional: `name`, `worktreePath`, `indexRange` (two integers), `archDoc`, `slicePlan`, `developmentPhase`, `activeSlice`, `activeTaskFile`, `instruction`.
- `updatedAt`: a string. Recorded as provenance and never compared, as 102's read-back observer does.

The parent architecture describes CF 0.14.x with project-level pointers only. That is an earlier dated observation. The projection reads both levels, so it does not depend on which one a given CF version fills.

## Architecture

### Component Structure

```
src/amoeba/upstream/context_forge/
  projects_file.py     parse(bytes, cf_project_id) -> CFProjectState | CFReadFailure; the field lists
  diff.py              diff_states(previous | None, current) -> tuple[CFFieldChange, ...]   (pure)
src/amoeba/store/
  cf_models.py         CFSnapshotOutcome, CFLink, CFSnapshot, CFSnapshotInput
  sql_cf.py            every statement and column name for the two tables
  mapping_cf.py        row -> record mapping
  cf_snapshots.py      CFOperations mixin, and the link_cf_project effect
  schema/008_context_forge_snapshots.sql
src/amoeba/process/
  cf_watch.py          CFWatchTenant
src/amoeba/inbox/
  envelope.py          + LinkCFProjectPayload
src/amoeba/cli/
  inspect_cf.py        the cf-links and cf-snapshots listings, appended to LISTINGS
docs/context-forge-contract.md
tests/fixtures/cf/projects.json
```

The pattern is 106's. The store imports nothing from `amoeba.upstream` or `amoeba.process`. It stores the projection as JSON that it does not interpret, as it does message payloads. The tenant is the only module that knows both the parser and the store. `inbox.py` is already over its line budget, so the effect function lives in `cf_snapshots.py`. `inbox.py` gains only its `KIND_EFFECTS` line, or the equivalent in whatever split 107 makes.

### Data Flow

**Linking:**

```
amoeba submit link-cf-project --project P --by pm --cf-project-id ID
  inbox apply: insert cf_links(project, cf_project_id, linked_at); linking again is a no-op
  the store reads no file; whether ID exists in CF is answered by the next check
```

**One `CFWatchTenant.tick`** (does nothing until `cf_scan_interval_seconds` has passed since the last check):

```
links = cf_links across open projects
signature = stat(cf_data_dir / "projects.json") -> (st_ino, st_size, st_mtime_ns), or the OS error
if (signature, links) == remembered: return            # one stat per interval, nothing else
read the bytes                                          # on OS error -> every link is unreadable
for each link:
  observation = parse(bytes, link.cf_project_id)        # CFProjectState or CFReadFailure
  last     = latest snapshot row for (project, cf_project_id)
  baseline = latest snapshot row with outcome observed  (may equal last, or be absent)
  observation is a state:
    changes = diff_states(baseline.state if baseline else None, observation)
    if changes or last.outcome != observed:
      record_cf_snapshot(observed, state, changes, cf_updated_at, version label)
  observation is a failure:
    if last is absent or (last.outcome, last.detail) != (failure.outcome, failure.detail):
      record_cf_snapshot(failure.outcome, detail)
remember (signature, links) only if every record succeeded
```

Every row insert fires the `cf_snapshots` trigger, so a change row is appended to `changes` in the same transaction.

**Down-time changes.** The remembered signature is held in memory, so it is empty after a start. The first tick reads the file and compares each link with its stored baseline. Recovery (102) runs before any tenant ticks, as it does for every tenant.

**Why the link set is part of the remembered key.** A new link must be checked even when the file has not changed since the last check. Checking an unchanged link again writes nothing, so a re-check is always safe.

### State Management

Durable state, in each project store:

- `cf_links`: one row per `(project_id, cf_project_id)`.
- `cf_snapshots`: append-only. A row is written only when something changed (D3). The latest `observed` row for a link is the baseline for the next comparison.

The only in-memory state is the tenant's remembered `(signature, links)` key, its last check time, and the last failure it logged. Losing them on a restart costs one extra read of the file.

## Technical Decisions

**D1: Watch the file by stat signature on an interval, in a tenant.** *(New, pending.)* This is the same choice as 106 D3, for the same reasons: no file-watching library, and the loop stays synchronous. CF replaces the file by renaming a new file over it, so every write gives `projects.json` a new inode. Comparing `(st_ino, st_size, st_mtime_ns)` detects every write, even one within the mtime resolution that leaves the size unchanged. A rename is atomic, so a reader never sees half a write, and no settle wait is needed (106 needed one). Each check costs one `stat`. `cf_scan_interval_seconds` is 1.0, set in `ProcessSettings` with no CLI flag; tests inject a clock. A pointer move is a human-paced event, and a 1-second bound keeps the Runner prompt.

- *Against "Push, not poll."* This is polling one file with `stat`. It is not polling `cf next`, and it never recomputes CF state to find out whether anything changed. The architecture endorses watching `projects.json`, and 106 D2 draws the same line.
- *Stat-then-read race.* A file replaced between the `stat` and the read is safe. The remembered signature is the one taken before the read, so the next tick sees a new signature and checks again.

**D2: A snapshot is a projection, not the whole CF entry.** *(New, pending.)* The field lists in Interfaces Required are defined once in `projects_file.py`, as two tuples. The projection is `{"project": {field: value}, "worktrees": {worktree_id: {field: value}}}` and holds only the keys present in the file. A write that touches only unread fields (`customData`, or `updatedAt` alone) produces no snapshot. *Why:* `updatedAt` changes on every write, and `customData` is free text. Comparing either would put noise on the feed that no consumer asked for. Adding a field later is a one-line change, and it shows up as an addition in the first snapshot after the upgrade.

**D3: A row is written only when something changed, and a change names fields with their old and new values.** *(New, pending.)*

- `diff_states` compares two projections key by key. Each `CFFieldChange` is `{worktree_id: str | null, field, from?, to?}`. `from` is omitted when the key was absent, and `to` is omitted when it became absent. Absent and `null` are therefore different, as CF's optional fields are. A worktree that is added or removed shows up as its fields being added or removed.
- Changes are keyed by worktree id, not by a dotted path, so no CF value can make a change ambiguous.
- **The first snapshot of a link lists every present field as added.** Replaying the feed from seq 0 then rebuilds each linked project's pointers, as `node_created` carrying its status does for nodes (106).
- **The first `observed` row after a failure is written even when no field changed** (with `changed: []`), so that recovery from the failure is visible.
- Changes are ordered by worktree (project level first, then by worktree id) and then by field name, so equal states always produce the same list.

**D4: Failures are outcomes, never guesses.** *(New, pending.)* `CFSnapshotOutcome` has four values: `observed`, `unreadable`, `unrecognized`, and `missing`.

| Case | Outcome | Scope |
| --- | --- | --- |
| File absent, permission denied, or any other OS error on `stat` or read | `unreadable`, with detail `{error class}: {strerror}` | every link |
| Not valid JSON; top level is not an array; an element is not an object or has no string `id` | `unrecognized`, with a detail naming the rule | every link |
| The linked id appears more than once | `unrecognized` | that link |
| The linked entry's `worktrees` is present but is not an array of objects with distinct string `id`s | `unrecognized` | that link |
| No element has the linked id | `missing` | that link |

- Only the rules that decide *which* entry and *which* worktree a value belongs to are checked. Projected field values are not type-checked: they are stored and compared as whatever JSON CF wrote.
- A malformed element with no id makes the whole file `unrecognized`, because it could be the linked project. A file that is not even JSON is also `unrecognized`, never `unreadable`: CF validates JSON before renaming, so a bad file is a real finding, not a race.
- *In-place writes are accepted noise.* A hand edit, or another tool that writes the file in place rather than renaming, can expose a truncated file for a moment. That produces an `unrecognized` row followed by an `observed` row with `changed: []`. This is accepted: it is visible, and it is accurate about what Amoeba saw.
- A failure row is written only when the outcome or detail differs from the link's latest row. A file that stays broken produces one row, not one per interval. The tenant logs one ERROR when the file goes bad and one INFO when it recovers, as 106 does for unreachable directories. The process keeps running: a broken CF file is not a sick store.
- **A store exception while recording is logged at ERROR and re-raised, which stops the process.** This is 106's rule.

**D5: Linking goes through the inbox, keyed by CF's project id.** *(Slice plan; details new and pending.)* The `link_cf_project` payload is `cf_project_id: str`, non-empty, with no format check, because CF's id format is CF's business.

- One Amoeba project can link several CF projects. Several Amoeba projects can link the same CF project, and each records its own snapshots.
- A link is permanent. Removing one is deferred (issue #7).
- An id that CF does not have is `missing` on the first check. *Why an id and not a name or path:* names are user-editable labels (CLAUDE.md), and one `projectPath` can be shared by several worktrees.

**D6: One change kind, one trigger.** *(New, pending.)* Migration 008 adds `changes_cf_project_changed`, which fires `AFTER INSERT ON cf_snapshots` for every outcome.

- `node_id` is null, because a CF project is not a node. `subject_id` is the snapshot id.
- The payload is `json_object('cf_project_id', ..., 'outcome', ..., 'changed', json(new.changed))`, with `recorded_at = new.observed_at`.
- `changed` is null for failure outcomes. The detail stays on the row, read by `subject_id`, which keeps the payload small and fixed.
- The kind name is the one the slice plan and 106 already use. A failure row is a change in what Amoeba can observe about the project, and the payload's `outcome` says which.
- `cf_links` gets no trigger, as 106's `review_watches` has none. A link is configuration, not an event.
- The invariant test's script gains one row for each outcome, plus a no-op re-check that must add nothing.

**D7: CF's data directory is a setting with a flag, with no environment read.** *(New, pending. The PM must confirm this before Phase 5: the walkthrough and the end-to-end test assume it.)* `ProcessSettings.cf_data_dir` defaults to `DEFAULT_CF_DATA_DIR = ~/.config/context-forge`, CF's own default, and `amoeba start --cf-data-dir PATH` overrides it. Amoeba does **not** read `CONTEXT_FORGE_DATA_DIR`. 102's D3 keeps `AMOEBA_STORE_DIR` as the only environment read, and the shell that starts Amoeba need not have the same environment as the CF clients. A PM who uses `CONTEXT_FORGE_DATA_DIR` passes the same directory with the flag. The tenant logs the resolved file path at INFO on start so a wrong directory surfaces as `unreadable` or `missing`, not as silence. `cf` has no command that prints its data directory (checked against 0.19.11), so asking CF is not an option.

**D8: A snapshot mirrors CF's state and claims no author.** *(New, pending.)* A CF write the Runner issues (102's `cf_write` journal kind) also changes the file, and is also recorded as a snapshot. That is not double recording. The journal records the command and its result, and the snapshot records what CF now holds. Unlike 106 D5, nothing is deferred or skipped, because nothing is attributed. The Runner can match its own write to the snapshot through `cf_updated_at`, which both its read-back adoption and the snapshot record. `context-forge-contract.md` says so for 120.

**D9: The version label is captured once, at start-up.** `cf --version` is captured in `build_tenants`, before the loop, as `sq --version` is for 106. It is stored on every snapshot row as `cf_version_label`, or as the explicit unavailable marker if capture fails. No tick starts a subprocess. A CF upgrade while the process runs is not reflected until restart, and the contract says so.

### Patterns and Conventions

- `CFSnapshotOutcome` is a `StrEnum` defined once in `cf_models.py`. Migration 008 does not repeat its values; the trigger fires for every outcome.
- The projected field names are defined once, in `projects_file.py`. The data-file name `projects.json` is a constant there too.
- All SQL is in `sql_cf.py`.
- Payload keys for `link_cf_project` are defined once in `inbox_models.py`, as 103 does for its kinds.
- Store timestamps follow 101's convention. `observed_at` is when the tenant read the file. `cf_updated_at` is CF's own value, copied as given.

## Implementation Details

### API Contracts

**Store (exported from `amoeba.store`):**

| Method | Effect |
| --- | --- |
| `cf_links(project_id) -> list[CFLink]` | Links, in the order they were linked. |
| `cf_snapshots(project_id) -> list[CFSnapshot]` | Rows in id order. |
| `latest_cf_snapshots(project_id, cf_project_id) -> tuple[CFSnapshot \| None, CFSnapshot \| None]` | The latest row, and the latest `observed` row. |
| `record_cf_snapshot(CFSnapshotInput) -> CFSnapshot` | In-process only. One insert, and its trigger. |

`CFSnapshot` is `(id, project_id, cf_project_id, outcome, state: Mapping | None, changed: Sequence[Mapping] | None, detail | None, cf_updated_at | None, cf_version_label, observed_at)`.

**Upstream (`amoeba.upstream.context_forge`):** `parse(data: bytes, cf_project_id: str) -> CFProjectState | CFReadFailure`. A file-level failure is returned the same way for every id. The tenant parses once per link, which is cheap at this file's size (about 30 KB). Also `diff_states(previous: CFProjectState | None, current: CFProjectState) -> tuple[CFFieldChange, ...]`, and `CFProjectState.to_json()` for storage. The store never sees these types.

**Inbox kind `link_cf_project`:** described in D5. An empty id is quarantined as invalid.

**CLI:**

| Command | What it does |
| --- | --- |
| `amoeba start [--cf-data-dir PATH]` | Existing command. The flag is new. |
| `amoeba submit link-cf-project --project ID --by NAME --cf-project-id CFID` | Built from the payload model, under 104's flag rule. |
| `amoeba inspect cf-links --project ID` | `cf_project_id, linked_at`. |
| `amoeba inspect cf-snapshots --project ID` | `id, observed_at, cf_project_id, outcome, changed (summarized as field names), detail, cf_updated_at`. Full values with `--json`. |

### Database / Storage Schema

Migration `008_context_forge_snapshots.sql` sets `EXPECTED_SCHEMA_VERSION` to 8. Nothing needs backfilling.

- **`cf_links`:** `project_id`, `cf_project_id`, `linked_at`. Primary key `(project_id, cf_project_id)`.
- **`cf_snapshots`:** `id` (INTEGER PRIMARY KEY AUTOINCREMENT), `project_id`, `cf_project_id`, `outcome`, `state` (JSON text, null unless `observed`), `changed` (JSON array text, null unless `observed`), `detail` (null when `observed`), `cf_updated_at` (nullable), `cf_version_label`, `observed_at`. Index on `(project_id, cf_project_id, id)`.
- The trigger is described in D6.

## Integration Points

### Provides to Other Slices

- **110:** CF snapshots and `cf_project_changed` entries, so the end-to-end proof can include a CF pointer move across a restart.
- **109:** nothing functional. 109 moves every `inspect` listing module, including `inspect_cf.py`, into `amoeba.inspection`, which is why it is ordered after this slice.
- **Initiative 120:** the feed entry, for the Runner to react to pointer moves; `latest_cf_snapshots`, for current pointers without calling `cf`; and D8's matching rule.
- **Initiative 160:** the same feed entries, for status views.

### Consumes from Other Slices

- **101–103 and 106,** through their contracts. All changes are additive:
  - `SubmissionKind` gains `link_cf_project`.
  - `ProcessSettings` gains two fields.
  - `build_tenants` registers a third tenant, after `ReviewDetectionTenant`, so the inbox drains first.
  - `LISTINGS` gains two entries, and the test that pins the listing set is updated.
  - `ChangeKind` gains one member.
- **Context Forge,** through the file only. If CF changes the shape, affected links record `unrecognized` with a detail naming the rule that failed. The fix is a parser change and a new dated observation in `context-forge-contract.md`. No snapshot is ever made from a shape that was guessed.

## Success Criteria

### Functional Requirements

- A `cf set` that moves a linked project's worktree `developmentPhase` produces exactly one `observed` snapshot and one `cf_project_changed` change. Its `changed` names that worktree id and field, with `from` and `to`.
- A change made with `--project-level` is named with `worktree_id: null`.
- A link's first check records every present projected field as added.
- A CF write that touches only another project, or only an unread field of a linked project, records nothing.
- Changes made while the process is stopped are recorded, as one snapshot per link, on the first check after `start`.
- Unreadable, unrecognized, and missing cases each record their outcome with a specific detail, once per transition and not once per interval. The process keeps running. The next good read records an `observed` row, with `changed: []` if nothing moved.
- A malformed `worktrees` in the linked entry makes that link `unrecognized`. The same defect in another project's entry does not affect the link.
- Linking an id CF does not have records `missing`. Linking the same id again records nothing new.
- No tick starts a subprocess. `cf --version` runs once, before the loop.
- A store exception while recording is logged at ERROR and stops the process.

### Technical Requirements

- The projected field lists, the outcome word list, and the data-file name are each defined once. All SQL is in `sql_cf.py`.
- The store imports nothing from `amoeba.upstream`, `amoeba.process`, or `amoeba.feed`.
- Parser tests run on `tests/fixtures/cf/projects.json`, which is captured from a real CF 0.19.11 data directory and reduced to three real entries: this repository's entry (with worktrees), one entry without `worktrees`, and one other. Entries are otherwise unedited, and the fixture README records the capture. Defect cases are derived from that file by one stated edit each.
- 106's feed invariant test passes with the new kind in its script, and fails if the trigger is missing.
- A version-7 store with data from every earlier slice upgrades to 8 intact.
- `ruff`, `pyright` strict, and the full suite are clean. Files stay near 300 lines.
- `docs/context-forge-contract.md` documents the observed shape (dated, with its CF version), the projection, the four outcomes, the change payload, D7's directory rule, and D8. The other contract docs gain only the deltas: the kind, the listings, the setting, and the methods.

### Integration Requirements

- An end-to-end test through the real CLI as subprocesses, against a scratch CF data directory:
  1. Create a project and link the fixture's entry.
  2. Start a follower, then start the process.
  3. Rewrite the file by temp-file-and-rename (as CF does) with one moved pointer.
  4. `kill -9` the process, rewrite again, and start it.

  The follower and `inspect cf-snapshots` must agree, with one change per rewrite and nothing recorded twice. The test does not need `cf` on PATH. The walkthrough uses the real `cf`.

### Verification Walkthrough

*Draft, to be confirmed at the end of Phase 6.* Run in **bash** from the repository root, against a scratch Amoeba store and a **scratch CF data directory**, so the PM's real `projects.json` is never written. `cf` must be on PATH (0.19.x). Which pointer `cf set` moves (worktree or project level) depends on the current directory; confirm the routing at implementation time.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"; CFDIR="$(mktemp -d)"
cp tests/fixtures/cf/projects.json "$CFDIR"/
CFID=$(python3 -c 'import json,sys; print([p["id"] for p in json.load(open(sys.argv[1])) if p["name"]=="amoeba"][0])' "$CFDIR/projects.json")
cf_scratch() { CONTEXT_FORGE_DATA_DIR="$CFDIR" cf "$@"; }
```

1. **Link a CF project, and follow the feed.**
   ```bash
   uv run amoeba start --cf-data-dir "$CFDIR" &
   uv run amoeba submit create-project --project demo --by pm
   uv run amoeba submit link-cf-project --project demo --by pm --cf-project-id "$CFID"
   uv run amoeba feed --project demo --follow        # terminal 2
   ```
   Within about a second, the follower prints one `cf_project_changed` with `outcome: observed`, and `changed` lists every projected field as added, including the default worktree's `activeSlice`.
2. **A CF client moves a pointer.**
   ```bash
   cf_scratch set -p "$CFID" phase "Phase 5: Task Breakdown"
   ```
   One `cf_project_changed` appears, naming `developmentPhase` with `from` `Phase 4: Slice Design` and `to` `Phase 5: Task Breakdown`, on the default worktree's id (or with `worktree_id: null` if `cf` routed the write to the project level). `uv run amoeba inspect cf-snapshots --project demo` shows two rows.
3. **Unrelated writes are silent.** Change another project in the file, and an unread field of this one:
   ```bash
   OTHER=$(python3 -c 'import json,sys; print([p["id"] for p in json.load(open(sys.argv[1])) if p["name"]!="amoeba"][0])' "$CFDIR/projects.json")
   cf_scratch set -p "$OTHER" instruction "elsewhere"
   ```
   No new feed line, and no new snapshot.
4. **Changes made while down.**
   ```bash
   uv run amoeba stop
   cf_scratch set -p "$CFID" phase "Phase 6: Implementation"
   uv run amoeba start --cf-data-dir "$CFDIR" &
   ```
   The follower, which kept running, prints one change, from `Phase 5: Task Breakdown` to `Phase 6: Implementation`.
5. **Failures are recorded, not guessed.**
   ```bash
   uv run amoeba submit link-cf-project --project demo --by pm --cf-project-id project_does_not_exist; sleep 3
   cp "$CFDIR/projects.json" "$CFDIR/keep.json"
   echo '{}' > "$CFDIR/projects.json.new" && mv "$CFDIR/projects.json.new" "$CFDIR/projects.json"; sleep 5
   mv "$CFDIR/keep.json" "$CFDIR/projects.json"; sleep 3
   uv run amoeba inspect cf-snapshots --project demo
   ```
   Expected new rows, in order:
   - `missing` for the bogus id.
   - `unrecognized` (`top level is not an array`) for each of the two links. Only one per link, although several intervals passed.
   - After the restore, `observed` with `changed: []` for `$CFID`, and `missing` again for the bogus id.

   The process is still running throughout.
6. **Automated:** `uv run pytest tests/upstream/context_forge tests/process/test_cf_watch.py tests/store/test_feed_invariant.py tests/cli/test_cf_watch_end_to_end.py -v`.

Clean up with `uv run amoeba stop; rm -rf "$AMOEBA_STORE_DIR" "$CFDIR"`.

## Implementation Notes

### Development Approach

1. Confirm that 107 is merged (migration 007 present). Stop for the PM if it is not.
2. Capture and reduce the fixture. Build `projects_file.py` and `diff.py` with table tests: every row of D4's table, absent vs null, worktree added or removed, and ordering. This step is pure and needs no store.
3. Migration 008, `cf_models.py`, `sql_cf.py`, mapping, `CFOperations`, the trigger, the 7 → 8 upgrade test, and the invariant-test steps.
4. The `link_cf_project` kind, extending 103's completeness tests.
5. `CFWatchTenant`, with an injected clock and file path: the signature skip, the link-set re-check, the transition-only failure rows, re-raising store errors, and the restart baseline.
6. Settings and flags, `build_tenants` wiring with the `cf --version` capture, the two listings, the end-to-end test, the docs, and `CHANGELOG`.

Test each step right after building it, and commit after each.

### Special Considerations

- **Effort: 2.** Everything here follows a pattern that 106 shipped. The new code is the parser and diff (pure) and one small tenant.
- **Privacy of the fixture.** A real `projects.json` holds local paths and free-text `customData`. Before committing, the reduced fixture is checked for secrets; `customData` values may be emptied, because no test reads them. That edit is recorded in the fixture README.
- **The snapshot holds paths, not content.** The trust boundary is the store's own, as with 106's feed.
- **Filesystem calls are unbounded**, as in 106. A CF data directory on a stalled network mount hangs the tick, and 102's standing remedy applies.
