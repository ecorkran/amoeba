---
docType: slice-design
slice: context-forge-event-seam
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101, 102, 103, 106]
interfaces: [110]
dateCreated: 20260928
dateUpdated: 20260928
status: not_started
---

# Slice Design: context-forge-event-seam

## Overview

Context Forge state changes all the time, from the CLI, from MCP tools, from agents, and Amoeba only finds out by asking. This slice makes Amoeba notice on its own, without any change to Context Forge.

CF keeps every project's state in one file, `projects.json` in its data directory, and replaces that file atomically (write a temp file, rename over) on every write, whichever client made it. So the file is already the event source. A new tenant in the resident process watches it. When it changes, the tenant diffs each linked CF project against the last snapshot stored for it, and if anything moved, records a new snapshot. A trigger puts a `cf_project_changed` entry on 106's change feed in the same transaction.

This is all of the scope Amoeba took from CF initiative 220. 220's long-running process is 102's resident process; its notifications and subscription model are 106's feed; its storage-event emission is replaced by watching the file. The slice was deferred as a two-repository project needing a CF daemon and an agreed wire contract. It needs neither (rescoped 20260928).

## Value

Developer value.

- The Runner (120) and any feed subscriber learn that a phase, slice, task, or document pointer moved within seconds of any client moving it. Nobody polls `cf next` or re-reads CF to find out.
- Nothing is missed while the process is down. Every check compares the file against the stored snapshot, not against the previous event, so the first check after a start records whatever changed in between.
- Every recorded CF state carries provenance (CF's own `updatedAt`, the `cf --version` label), so later evidence can be tied to the CF state it was produced under.

## Technical Scope

**Included**

- Migration `008` with two tables, `cf_watches` and `cf_snapshots`, and a feed trigger on `cf_snapshots`.
- `ChangeKind.cf_project_changed`.
- A `watch_cf` inbox submission kind that links or unlinks a CF project, by CF project id, to an Amoeba project.
- `amoeba.upstream.context_forge`: reading `projects.json` into records keyed by CF project id, with typed errors, and the diff rule.
- `CFWatchTenant` in `amoeba.process`.
- Store read and write methods for watches and snapshots.
- `amoeba inspect cf-watches` and `amoeba inspect cf-snapshots`, registered in 102's listing registry.
- `ProcessSettings.cf_data_dir` and `cf_scan_interval_seconds`, with CLI flags.
- `docs/cf-contract.md` (the observed `projects.json` shape Amoeba depends on); updates to `feed-contract.md`, `store-contract.md`, `inbox-contract.md`, `process-contract.md`, and `CHANGELOG.md`.

**Excluded**

- Any change to Context Forge.
- **Writing to nodes.** CF changes are recorded as snapshots and feed entries. What a moved phase or slice pointer means for the node tree is the Runner's decision (D2).
- **Gate and review state.** `projects.json` holds pointers only. CF computes `activeSlice.status` and `gateInfo` from artifact frontmatter on every `workflow_status` call, and they are never written to the file. The Runner reads them through CF's control surface when it acts (120).
- `customData` (free text; D4).
- Per-field diffs inside `worktrees`. A change to any worktree reports `worktrees` as changed; the snapshot holds the whole value.
- Recovering intermediate CF states. Two writes between checks, or several while the process is down, are recorded as one change. CF keeps no history, so the intermediate states no longer exist anywhere.
- Changing 102's CF read-back observer. It keeps reading `cf get --json`.

## Dependencies

### Prerequisites

- **101:** `Store`, the migration mechanism (`EXPECTED_SCHEMA_VERSION` 7 → 8, after 107's 007).
- **102:** the tenant seam, `ProcessSettings` and its flag wiring, the listing registry, the writer guard, and the `cf --version` subprocess call and its `unavailable` marker convention (102 calls it once at start-up; this tenant calls it again on each detected file change).
- **103:** the inbox kind seam (member, payload model, effect) and `amoeba submit`.
- **106:** the `changes` table, the trigger emission pattern (106 D8), the feed invariant test, and the bounded-failure attempts sidecar used by detection.

Not needed: 104, 105, 107. 107 is ahead in the order only because it already holds migration 007.

### Interfaces Required

**From Context Forge:** only the file. Observed 20260928 on CF 0.18.0 (`packages/core/src/storage/`):

- **Location.** `CONTEXT_FORGE_DATA_DIR` if set. Otherwise `~/.config/context-forge` on macOS; on other platforms `$XDG_CONFIG_HOME/context-forge`, falling back to `~/.config/context-forge`. The file is `projects.json` in that directory.
- **Write.** `FileStorageService` copies the current file to `projects.json.backup`, writes `projects.json.tmp`, validates it as JSON, and renames it over `projects.json`. Readers never see a partial file written by CF.
- **Shape.** A JSON array of project objects (`ProjectData`). Each has a string `id` (`project_{ms}_{random}`), `name`, `createdAt`, `updatedAt`, and optional pointer fields: `developmentPhase`, `instruction`, `workType`, `fileSlice`, `fileTasks`, `fileArch`, `fileSlicePlan`, `fileHLD`, `fileSpec`, `fileConcept`, `projectPath`, `dateProject`, `template`, `worktrees` (array of per-worktree overlays), and `customData`. Older records carry retired keys (`slice`).
- **`worktrees` overlay shape, observed 20260928 on CF 0.18.0.** Each overlay is an object keyed by worktree path, carrying `developmentPhase`, `activeSlice`, `activeTaskFile`, `updatedAt`. No overlay observed carries its own `customData`; if CF ever adds one, it is caught by the recursive ignore rule below rather than assumed absent.

Amoeba depends on exactly two things in that shape: the file is a JSON array of objects, and each object has a string `id`. Every other key is carried as opaque data and compared by value, never interpreted. So a key CF adds, renames, or retires shows up as a changed field, not as a parse failure.

**From the store:** 106's `changes` table and its trigger convention.

## Architecture

### Component Structure

```
src/amoeba/upstream/context_forge/
  projects_file.py      resolve_cf_data_dir, read_projects_file, CFRecord,
                        ProjectsFileMissing, ProjectsFileUnrecognized
  diff.py               IGNORED_KEYS, tracked_fields(record), changed_keys(before, after)
src/amoeba/store/
  cf_models.py          CFWatch, CFWatchState, CFSnapshot, CFSnapshotInput
  sql_cf.py             every statement and column name for the two tables
  mapping_cf.py         row → record mapping
  cf_watches.py         CFWatchOperations mixin
  schema/008_cf_watches_and_snapshots.sql   tables and the feed trigger
src/amoeba/process/
  cf_watch.py           CFWatchTenant
src/amoeba/inbox/
  envelope.py           + WatchCFPayload
src/amoeba/cli/
  inspect_cf.py         the cf-watches and cf-snapshots listings
docs/cf-contract.md
```

Same pattern as 101–107: models, SQL, mapping, operations mixin. The store does not import `amoeba.upstream`; it stores CF fields as an opaque JSON object and a list of changed key names, both computed by the tenant. The tenant is the only module that knows both the file reader and the store's write path, as `ReviewDetectionTenant` is for reviews.

### Data Flow

**Linking a CF project:**

```
amoeba submit watch-cf --project P --by pm --cf-project project_1781844717321_1gukaohbc --active true
  inbox apply: upsert cf_watches(project, cf_project_id, active, state = pending)
next tick: the linked project has no snapshot yet → it is recorded (below), with every key changed
```

**One `CFWatchTenant.tick`** (at most once per `cf_scan_interval_seconds`):

```
if no active watch in any open project (checked against an in-memory cache, not a fresh query) → return
sig = stat(projects.json)  # missing file: sig = None, handled by the branch below
if sig == last_sig and the cache has no watch added since the last tick → return     # the common case: one stat, no query
last_sig = sig             # set before dispatch: an unrecognized or missing file is still not re-read until sig changes
if sig is None:
  every active watch: state unreachable (on transition only); return
read_projects_file(path)
  ProjectsFileUnrecognized → every active watch: state unrecognized, detail = error; return
for each active watch (project P, cf id C):
  current  = tracked_fields(records[C])  or  absent
  previous = latest snapshot for (P, C)  or  none
  if absent and previous is none or previous.present is false → state missing; continue
  changed = changed_keys(previous, current)     # every key when previous is none; ["$present"] when C vanished
  if changed is empty → state ok; continue       # e.g. only updatedAt or customData moved
  one transaction:
    record_cf_snapshot(P, C, present, fields = current, changed, cf_updated_at, version_label)
    state ok (or missing when absent)
    # the cf_snapshots insert trigger appends cf_project_changed to changes
```

`last_sig` lives only in memory. After a restart it is unset, so the first tick reads the file and diffs every watch against its stored snapshot: that is the whole catch-up mechanism, and it is the same code path as a normal change.

The version label is re-captured whenever the file signature changes (one `cf --version` subprocess per detected change, not per tick), so a snapshot's label reflects the CF binary that was live when the snapshot was taken. If the subprocess fails, the label is stored as `unavailable`, the same marker 102 uses at start-up.

### State Management

All durable state is in each project store:

- `cf_watches`: one row per link, with its current `state` and `detail`, written only when the state changes.
- `cf_snapshots`: append-only. One row each time a linked CF project's tracked fields differ from the previous row. The latest row per `(project, cf_project_id)` is the baseline the next check compares against.

In memory: the file signature from the last successful read. Losing it costs one extra read.

## Technical Decisions

### Technology Choices

**D1 — Watch CF's file; do not ask CF to emit events.** The file is replaced atomically by every CF client, so a change to the file is a change to CF state, and a complete read is always possible. Asking CF to emit events would need a CF-side change, a transport, and a delivery guarantee, and would still need a reconciling read after downtime. The reconciling read alone does the whole job.

- *Checked by `stat`, not by a file-watch library*, for the reason 106 D3 gives: FSEvents and inotify arrive on a thread, and a scan is still needed after restart. One `stat` per tick is nothing.
- *The signature includes the inode* because CF replaces the file by rename. Two writes within one mtime tick with equal sizes still produce different inodes.
- *Read the file directly, not through `cf get --json`.* One read covers every linked project, needs no subprocess in a tick, and sees the base record and all worktree overlays together (`cf get` resolves one overlay depending on where it runs). The price is depending on a file CF does not call a contract. That dependency is two facts (an array of objects with string `id`s), both documented in `cf-contract.md`, and a violation is recorded as `unrecognized`, never guessed around.

**D2 — Record snapshots; do not write nodes.** A CF change is recorded as a snapshot row and a feed entry. The tenant never creates, updates, or blocks a node.

- *Why:* turning "`fileSlice` moved to 105" into node changes needs a node for that slice, a rule for which node holds `cf.phase`, and a policy for what a pointer moving backwards means. That is the Runner's node model (120), the same line 105 D4 drew for gate nodes. The substrate stays deterministic plumbing: it records what CF said, with provenance, and says that it changed.
- *Reference, don't duplicate:* a snapshot is CF's state as observed at a time, with CF's own `updatedAt`, never a competing truth. The Runner reads it or CF, not a copy it mutates.
- This replaces the old plan criterion "received events update the node tree."

**D3 — Link by CF project id.** A watch names CF's `id`, never its `name`. Names are user-editable (`cf set name`), and a label is not a key. The id is carried as an opaque string; its format is not parsed.

**D4 — The diff is top-level keys, compared by value, minus two ignored keys, applied recursively into `worktrees` overlays.** `IGNORED_KEYS = {"updatedAt", "customData"}`, defined once in `diff.py`, and applied both to the record itself and to each entry of `worktrees` before comparison and before storage.

- `updatedAt` changes on every write, so it would make every write a change. It is kept on the snapshot as provenance (`cf_updated_at`), not compared. An overlay's own `updatedAt` is stripped the same way, for the same reason.
- `customData` is free text (`recentEvents` runs to kilobytes of pasted summaries). It is not workflow state, and the architecture forbids routing on free-form strings. It is not stored, whether it appears on the record or inside a `worktrees` overlay.
- Every other key is compared by value (deep JSON equality), including keys Amoeba has never seen. `changed_keys(None, x)` is every key in `x`. A record that disappears yields the reserved marker `["$present"]`, prefixed with `$` because no CF key is observed to start with it, so it cannot collide with a real CF field. `worktrees` itself is still reported as one changed key when any overlay's remaining fields differ; it is not diffed per sub-field, only cleaned of ignored keys before the whole-value comparison.

**D5 — The Runner's own CF writes are reported too.** Unlike review detection (106 D5), this tenant does not defer to open `cf_write` journal entries. A CF change the Runner made is still a CF change, and a subscriber should see it. The Runner tells its own writes apart by its journal. Deferring would add a rule with nothing to protect: there is no double-record risk, because a snapshot is recorded only when the fields differ from the last one.

### Patterns and Conventions

**Word lists** (`StrEnum`, defined once in `cf_models.py`):

- `CFWatchState`: `pending`, `ok`, `missing`, `unreachable`, `unrecognized`, `failed`
- `ChangeKind` (106) gains `cf_project_changed`.

**The feed entry:**

| Kind | `node_id` | `subject_id` | payload |
| --- | --- | --- | --- |
| `cf_project_changed` | null | snapshot id | `cf_project_id`, `present`, `changed` (array of key names) |

The payload says which keys moved, not their values; a subscriber that wants them reads `cf_snapshot(id)`. The trigger copies `changed` from the row's stored JSON column, so the feed and the store cannot disagree.

**Feed invariant (106).** The scripted sequence gains a linked CF project: a first snapshot, a change, a disappearance. The reconciliation gains one rule: snapshot ids from `cf_project_changed` equal the `cf_snapshots` table. The "every `ChangeKind` appears" check then covers the new member.

**Errors.**

- *File missing or unreadable:* every active watch goes `unreachable`, with one ERROR on the transition and one INFO on recovery. The process keeps running: CF not being installed on a machine is not a sick store.
- *File present but not an array of objects with string `id`s, or not JSON:* `unrecognized`, with the error as `detail`, one ERROR on the transition. Retried only when the signature changes. This is also what a hand edit caught mid-save looks like; the next save fixes it. One malformed or duplicate-id entry anywhere in the file, including in a project no watch links, blinds every watch — this is a deliberate trade-off, not an oversight: `read_projects_file` parses the whole file as one unit because there is no partial-validity notion in the observed shape, and refusing to guess which of two same-id records is correct is safer than silently picking one. The blast radius is visible immediately through `inspect cf-watches`, and self-heals on CF's next write.
- *Linked id never present:* `missing`, no snapshot. A typo in the id sits visibly in `inspect cf-watches`.
- *Linked id present before, now gone:* a snapshot with `present = false` and a feed entry. That is a real CF fact (`cf project rm`), not an error. If it returns, the next snapshot has every key changed.
- *Store failure while recording a snapshot:* 106's bounded-failure rule, reusing its `AttemptsSidecar` and `write_durably`. D3 keeps `cf_project_id` opaque and unparsed, so it is never used as a path component: the sidecar is keyed on a hex digest of the id, at `{store_dir}/cf/attempts/{project_id}/{sha256(cf_project_id).hexdigest()}.attempts.json`. Below `cf_max_attempts`: ERROR and re-raise. At the limit: ERROR, the watch goes `failed`, and it is skipped until the sidecar is removed. On success the sidecar is deleted.

**Settings** (added to `ProcessSettings`, with CLI flags):

- `cf_data_dir: Path`, from `resolve_cf_data_dir()`, the one place CF's location rule is mirrored. `--cf-data-dir` overrides it. The rule is CF's, copied (Interfaces Required); `cf-contract.md` names it as copied.
- `cf_scan_interval_seconds = 2.0`: same reasoning as 106's review scan. A pointer moves when a person or agent finishes a step; a few seconds' delay is invisible, and an idle tick is one `stat`.
- `cf_max_attempts = 3`: same as `inbox_max_attempts` and `detection_max_attempts`.

## Implementation Details

### API Contracts

**Store additions (exported from `amoeba.store`):**

| Method | Effect |
| --- | --- |
| `cf_watches(project_id) -> list[CFWatch]` | Links, with state and detail. |
| `cf_snapshots(project_id, *, cf_project_id=None) -> list[CFSnapshot]` | History, oldest first. |
| `latest_cf_snapshot(project_id, cf_project_id) -> CFSnapshot \| None` | The baseline. |
| `cf_snapshot(project_id, snapshot_id) -> CFSnapshot` | One snapshot; raises `CFSnapshotNotFoundError`. |
| `record_cf_snapshot(CFSnapshotInput) -> CFSnapshot` | In-process only. |
| `set_cf_watch_state(project_id, cf_project_id, state, detail)` | In-process only. No-op when unchanged. |

`CFSnapshot` is `(id, project_id, cf_project_id, present, fields: Mapping, changed: tuple[str, ...], cf_updated_at: str | None, version_label, observed_at)`. `cf_updated_at` is CF's string as written, never parsed for ordering.

**Upstream reader (`amoeba.upstream.context_forge`):** `read_projects_file(path) -> Mapping[str, CFRecord]`, keyed by `id`; raises `ProjectsFileMissing` or `ProjectsFileUnrecognized`. A duplicate `id` in the file is `ProjectsFileUnrecognized`: there is no correct record to pick.

**Inbox, the `watch_cf` kind:** payload `cf_project_id: str` (non-empty), `active: bool`. The effect upserts the watch; a new or reactivated watch starts `pending`. Reactivating diffs against the last snapshot, so changes made while inactive are recorded as one change.

**CLI:**

| Command | What it does |
| --- | --- |
| `amoeba submit watch-cf --project ID --by NAME --cf-project CFID --active true\|false` | From the payload model, under 104's flag rule. |
| `amoeba inspect cf-watches --project ID` | `cf_project_id, active, state, detail, last_snapshot_at`. |
| `amoeba inspect cf-snapshots --project ID [--cf-project CFID]` | `observed_at, cf_project_id, present, changed, cf_updated_at, version_label`; `--json` adds `fields`. |
| `amoeba start --cf-data-dir PATH` | Overrides the resolved CF data directory. |

### Database / Storage Schema

Migration `008_cf_watches_and_snapshots.sql`, `EXPECTED_SCHEMA_VERSION` 8. Nothing to backfill. This number assumes 107's `007` lands first (Prerequisites); if implementation order changes and 108 ships before 107, this migration is renumbered `007` and 107's becomes `008` — keep this visible in the slice plan rather than fixing a number here that the plan might not honor.

- **`cf_watches`:** `project_id`, `cf_project_id`, `active` (INTEGER), `state`, `detail` (nullable), `registered_at`, `updated_at`. Primary key `(project_id, cf_project_id)`.
- **`cf_snapshots`:** `id` (INTEGER PRIMARY KEY AUTOINCREMENT), `project_id`, `cf_project_id`, `present` (INTEGER), `fields` (JSON text, the record minus `IGNORED_KEYS`; `{}` when absent), `changed` (JSON array text), `cf_updated_at` (nullable), `version_label`, `observed_at`. Index on `(project_id, cf_project_id, id)`.
- **Trigger** `AFTER INSERT ON cf_snapshots`: inserts a `changes` row, kind `'cf_project_changed'`, `node_id` null, `subject_id` the snapshot id, payload `json_object('cf_project_id', …, 'present', json(iif(new.present, 'true', 'false')), 'changed', json(new.changed))`, `recorded_at = new.observed_at`. `present` is cast to a JSON boolean literal, matching 106's boolean convention, rather than SQLite's native `1`/`0`.

## Integration Points

### Provides to Other Slices

- **110:** CF snapshots and `cf_project_changed` entries in the end-to-end sequence. 110's feed check reconciles by table, so it covers them with its sequence extended by one link and one `cf set`.
- **Initiative 120:** the feed entry as its signal that CF moved, and `latest_cf_snapshot` as a read of CF state with provenance. 120 decides what a change means for nodes (D2) and reads gate state through CF itself.
- **Initiative 160:** the entries on the feed, like any other kind.

### Consumes from Other Slices

- **101–103** through their documented contracts. Additive: `SubmissionKind` gains `watch_cf`, `ProcessSettings` gains three fields, `amoeba start` registers a third tenant, `LISTINGS` gains two entries (the listing-set test is updated).
- **106:** `ChangeKind` gains a member and 106's invariant test gains a step and a rule. The detection tenant and its sidecar helper are reused, not changed.
- **Context Forge:** if CF moves its storage out of `projects.json`, or changes the file into something other than an array of objects with `id`, every watch goes `unreachable` or `unrecognized`, visibly, and nothing is recorded. The fix is a new reader in `amoeba.upstream.context_forge`; the store, tenant, and feed are unaffected.

## Success Criteria

### Functional Requirements

- Linking a CF project records a first snapshot with every tracked key in `changed` and emits one `cf_project_changed`.
- `cf set phase …` on a linked project (any CF client) produces, within about two scan intervals, one snapshot with `changed = ["developmentPhase"]` and one feed entry.
- A CF write that touches only `updatedAt` or `customData` records nothing.
- A change to an unlinked CF project records nothing.
- Changes made while the process is stopped are recorded as one snapshot on the first tick after start; a restart with no CF change records nothing.
- A linked project removed from CF records a `present = false` snapshot; restored, it records a snapshot with every key changed.
- A linked id not in the file shows `missing` and records nothing.
- A missing `projects.json` shows `unreachable`; the process keeps running and resumes when the file appears.
- A `projects.json` that is not JSON, not an array, has an entry without a string `id`, or has a duplicate `id`, shows `unrecognized` with the reason, records nothing, and is re-read only after the file changes.
- A deactivated watch records nothing; reactivated, it records one snapshot covering everything that changed while inactive.
- A store failure while recording stops the process below `cf_max_attempts`; at the limit the watch is `failed`, other watches continue, and deleting the sidecar retries.
- An idle tick performs one `stat`, no file read, and no new-watch detection beyond an in-memory cache of known watch ids (populated on tenant start and updated when `watch_cf` submissions are applied).

### Technical Requirements

- Each word list is a `StrEnum` defined once. All SQL is in `sql_cf.py`. `IGNORED_KEYS` and the CF location rule each have one definition.
- The store imports nothing from `amoeba.upstream` or `amoeba.process`. No tick starts a subprocess.
- Reader tests run against a copy of a real `projects.json` from CF 0.18.0, trimmed of `customData`, stored in `tests/fixtures/cf/`, plus files written by the real `cf` CLI into a temporary `CONTEXT_FORGE_DATA_DIR`. No hand-built file stands in for the real shape in the success-path tests.
- A version-7 store upgrades to 8 intact.
- 106's feed invariant test passes with the new step and rule.
- `ruff`, `pyright` strict, and the full suite are clean. Files stay near 300 lines.

### Integration Requirements

- End to end through the real CLIs as subprocesses: a temporary `CONTEXT_FORGE_DATA_DIR`, `cf init --lite`, link, `amoeba feed --follow`, `cf set phase`, `kill -9` the process, `cf set slice` while it is down, start it. The follower prints exactly the expected entries, and `inspect cf-snapshots` agrees.
- `docs/cf-contract.md` states the observed shape, the location rule, and what Amoeba does when either changes.

### Verification Walkthrough

Draft; refined with real output when Phase 6 completes. Run in **bash** from the repository root. `CONTEXT_FORGE_DATA_DIR` points CF at a throwaway directory so the walkthrough never touches your real CF data; `amoeba start` resolves the same variable.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
export CONTEXT_FORGE_DATA_DIR="$(mktemp -d)"
CFPROJ="$(mktemp -d)"
(cd "$CFPROJ" && cf init --lite --no-ide --name demo-cf)
CFID="$(cf get --json -p demo-cf | jq -r .id)"
uv run amoeba start --sq-runs-dir "$(mktemp -d)" &
until uv run amoeba status | grep -q '^running'; do sleep 0.2; done
uv run amoeba submit create-project --project demo --by pm
```

**1. Follow the feed.** In a second terminal, with the same `AMOEBA_STORE_DIR`: `uv run amoeba feed --project demo --follow`. It waits.

**2. Link the CF project.**

```bash
uv run amoeba submit watch-cf --project demo --by pm --cf-project "$CFID" --active true
```

Within a few seconds the follower prints one `cf_project_changed` with `present: true` and `changed` listing every key `cf init` wrote. `uv run amoeba inspect cf-watches --project demo` shows the link `ok`.

**3. Any CF client moves a pointer.**

```bash
cf set phase "Phase 4: Slice Design" -p demo-cf
```

The follower prints `cf_project_changed` with `changed: ["developmentPhase"]`. `uv run amoeba inspect cf-snapshots --project demo --json` shows the new value in `fields`, CF's `updatedAt` as `cf_updated_at`, and the `cf --version` label.

**4. Noise is not a change.** Change another CF project's field, or run `cf set` with the value already held. No feed line.

**5. Nothing is missed while the process is down.** `kill -9` the process (pid from `amoeba status`), then:

```bash
cf set slice user/slices/108-slice.context-forge-event-seam.md -p demo-cf
cf set phase "Phase 5: Task Breakdown" -p demo-cf
uv run amoeba start --sq-runs-dir "$(mktemp -d)" &
```

After start, the follower prints one `cf_project_changed` with `changed: ["developmentPhase", "fileSlice"]`. Restart once more with no CF change: nothing new is printed.

**6. What the tenant refuses to guess.**

- `uv run amoeba submit watch-cf --project demo --by pm --cf-project project_nope --active true`. `inspect cf-watches` shows it `missing`; no feed line.
- `cp "$CONTEXT_FORGE_DATA_DIR/projects.json" /tmp/cf.bak && echo '{}' > "$CONTEXT_FORGE_DATA_DIR/projects.json"`. Both watches show `unrecognized` with "not an array". `cp /tmp/cf.bak "$CONTEXT_FORGE_DATA_DIR/projects.json"`: back to `ok` and `missing`, with no feed line, because nothing changed against the stored snapshot.
- `cf project rm demo-cf`. The follower prints `cf_project_changed` with `present: false`.

**7. Automatically.**

```bash
uv run pytest tests/store/test_feed_invariant.py tests/cli/test_cf_watch_end_to_end.py -v
```

## Implementation Notes

### Development Approach

1. `amoeba.upstream.context_forge`: `resolve_cf_data_dir`, `read_projects_file`, `changed_keys`, against the real-file fixture and files written by the real `cf` CLI. No store involvement; can start before 106 lands.
2. Migration 008, `cf_models.py`, `sql_cf.py`, mapping, the operations mixin, the trigger. 7 → 8 upgrade test; extend 106's invariant test.
3. The `watch_cf` kind and its effect.
4. `CFWatchTenant`: the signature check, the per-watch diff, the state transitions, the bounded-failure path.
5. Settings and flags, `start` wiring, the two listings, the end-to-end CLI test, `docs/cf-contract.md`, the other doc updates, and `CHANGELOG`.

Test each step right after building it; commit after each.

### Special Considerations

- **The file holds every CF project,** including ones Amoeba has not linked. Only linked records are stored; the rest are read and discarded in memory. `customData` is never stored, which keeps pasted conversation summaries out of the Amoeba store.
- **Hand edits to `projects.json`** are not atomic. A read mid-save is `unrecognized` until the next save; that is the correct outcome, not a race to engineer around.
- **One file, many projects.** One read per changed signature serves every Amoeba project with an active watch, since all open project stores are ticked by the same tenant.
