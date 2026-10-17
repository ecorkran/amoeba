---
docType: reference
project: amoeba
slice: context-forge-event-seam
dateCreated: 20261016
dateUpdated: 20261016
status: complete
---

# The Amoeba Context Forge Contract

This document is the contract for how Amoeba learns that Context Forge (CF)
moved a project's pointers. It is written so that initiative 120 (the Runner)
and 160 (status views) can consume the result **without reading the
implementation**. The generic mechanisms are documented elsewhere and not
repeated here: the change-feed trigger convention in
[`store-contract.md`](store-contract.md), the tenant protocol in
[`process-contract.md`](process-contract.md), and the feed itself in
[`feed-contract.md`](feed-contract.md).

## What this is

CF keeps every project in one file, `projects.json`. Any client that writes —
the `cf` CLI, the MCP server, another agent — replaces that file by writing a
temp file and renaming it over the original. Amoeba watches the file, compares
each **linked** CF project with its last stored snapshot, and records one
`cf_project_changed` feed entry per real change, naming the fields that moved.

It does not poll `cf next`, it changes nothing in CF, and it never writes to
`projects.json` (the architecture forbids editing it directly).

## What this is not

- **Not an interpretation.** A snapshot records what CF holds. That a moved
  pointer means "this slice is ready for review" is the Runner's job (120).
- **Not an authorship record.** CF does not record who wrote, and Amoeba does
  not guess. See "The Runner's own writes".
- **Not review-gate state.** CF recomputes it from artifact frontmatter on each
  call and does not store it in `projects.json`; the Runner reads it through
  `workflow_status`.
- **Not a retention policy.** Snapshots are never deleted or compacted in this
  slice.

## The observed shape

*Observed on CF 0.19.13 on 2026-10-16 (first on 0.19.11, 2026-10-15). A dated
observation, not a version dependency: Amoeba accepts the shape below and
nothing else, and a shape it does not recognize is recorded, never guessed.*

- The top level is a JSON array of project objects. Each has a string `id`
  (for example `project_1781844717321_1gukaohbc`).
- Project-level pointer fields, all optional strings: `name`, `projectPath`,
  `developmentPhase`, `instruction`, `fileArch`, `fileSlicePlan`, `fileSlice`,
  `fileTasks`.
- `worktrees`: optional. When present, an array of objects, each with a string
  `id` (`wt_{timestamp}_{random}`). Since CF began scoping work to worktrees the
  live pointers sit here, not at project level: in this repository's record the
  project-level `developmentPhase` and `fileSlice` are empty strings, and the
  `default` worktree holds `developmentPhase`, `activeSlice`, `activeTaskFile`.
  Worktree fields, all optional: `name`, `worktreePath`, `indexRange` (two
  integers), `archDoc`, `slicePlan`, `developmentPhase`, `activeSlice`,
  `activeTaskFile`, `instruction`.
- `updatedAt`: a string, recorded as provenance and never compared.

An earlier dated observation (CF 0.14.x) had project-level pointers only. The
projection reads both levels, so it does not depend on which one a CF version
fills. The reduced real file used by the tests is `tests/fixtures/cf/projects.json`
(see `tests/fixtures/README.md`).

## The projection

A snapshot holds `{"project": {field: value}, "worktrees": {worktree_id:
{field: value}}}`: only the keys **present** in the file, values copied as CF
wrote them (not type-checked). The field lists are defined once, in
`amoeba.upstream.context_forge.projects_file`.

`updatedAt` and `customData` are **not** projected. `updatedAt` changes on every
write and `customData` is free text; comparing either would put noise on the feed
that no consumer asked for. A write that touches only unprojected fields, or only
another project's entry, records nothing. `updatedAt` is kept only as the
snapshot's `cf_updated_at`. Adding a field later is a one-line change and shows
up as an addition in the first snapshot after the upgrade.

## Linking

```
amoeba submit link-cf-project --project ID --by NAME --cf-project-id CFID
```

The `link_cf_project` submission links an Amoeba project to a CF project by CF's
own id (names are editable labels; one `projectPath` can be shared by several
worktrees). `cf_project_id` must be non-empty; its format is CF's business. One
Amoeba project may link several CF projects, and several Amoeba projects may link
the same one (each records its own snapshots). Linking again is a no-op. A link
is permanent in this slice (unlinking is GitHub issue #7). The store does not
check that CF has the id: the first check answers, with `missing`.

## What the watch records

A tenant (`CFWatchTenant`, registered third by `amoeba start`) takes one `stat`
of the file every `cf_scan_interval_seconds`. Only when the file's signature
`(inode, size, mtime_ns)` or the set of links changed does it read the file and
check each link. The rename gives every CF write a new inode, so every write is
seen even within the mtime resolution, and a reader never sees half a write.

Each check compares a link with its **stored** snapshots, never with memory, so
changes made while the process was down show up as one snapshot per link on the
first check after `start`.

Rules for what is written (`diff_states` and the tenant):

- **The first snapshot of a link lists every present projected field as added**
  (`to` only), so replaying the feed from `seq` 0 rebuilds each linked project's
  pointers.
- After that, a snapshot is written only when the projection differs from the
  latest `observed` one. Re-checking an unchanged link writes nothing.
- **The first `observed` row after a failure is written even when nothing moved**
  (`changed: []`), so recovery is visible. The next diff is against the last
  `observed` row, not the failure row.
- Changes are ordered: project level first, then worktrees by id, then fields by
  name. Absent and `null` are different: `from` is omitted when the key was
  absent, `to` when it became absent. A worktree added or removed shows as its
  fields added or removed.

### Outcomes

| Outcome | When | Scope |
| --- | --- | --- |
| `observed` | The linked entry was read. | the link |
| `unreadable` | The file is absent, permission-denied, or any other OS error on `stat` or read. `detail` is `{error class}: {strerror}`. | every link |
| `unrecognized` | Not valid JSON; the top level is not an array; an element is not an object with a string `id`. A bad file is always `unrecognized`, never `unreadable`: CF validates JSON before renaming. | every link |
| `unrecognized` | The linked id appears more than once; or its `worktrees` is present but is not an array of objects with distinct string `id`s. | that link |
| `missing` | No element has the linked id. | that link |

Only the rules that decide *which* entry and *which* worktree a value belongs to
are checked. A defect in another project's entry does not affect the link.

A failure row is written only when its outcome or detail differs from the link's
latest row: a file that stays broken records one row per link, not one per
interval. The tenant logs one ERROR when the file goes bad and one INFO when it
recovers, and the process keeps running — a broken CF file is not a sick store.
A store exception while recording is logged at ERROR and **stops the process**
(106's rule). A file that cannot be read is retried every interval (a permission
fix leaves the signature unchanged).

**In-place writes are accepted noise.** A hand edit, or a tool that writes the
file in place rather than renaming, can expose a truncated file for a moment.
That records an `unrecognized` row followed by an `observed` row with
`changed: []`. It is visible, and it is accurate about what Amoeba saw.

## The feed entry

`cf_project_changed`, one per snapshot row, for every outcome (the trigger is
the generic convention; see the store contract). `node_id` is null (a CF project
is not a node); `subject_id` is the snapshot id; `recorded_at` is `observed_at`.

| Payload key | Value |
| --- | --- |
| `cf_project_id` | The CF id. |
| `outcome` | One of the four outcome words. |
| `changed` | A list of `{worktree_id, field, from?, to?}` for `observed`; `null` for a failure. The failure's `detail` stays on the row: read it by `subject_id` (`inspect cf-snapshots`). |

`worktree_id` is `null` for a project-level field. Which level a `cf set` writes
to depends on the directory it runs in.

## Where Amoeba looks (D7)

`ProcessSettings.cf_data_dir` defaults to `~/.config/context-forge`, CF's own
default; `amoeba start --cf-data-dir PATH` overrides it. **Amoeba does not read
`CONTEXT_FORGE_DATA_DIR`**: `AMOEBA_STORE_DIR` stays the only environment read,
and the shell that starts Amoeba need not match the CF clients'. If you use that
variable, pass the same directory with the flag. The tenant logs the resolved
file path at INFO on its first tick, so a wrong directory surfaces as
`unreadable` or `missing`, not silence. `cf` has no command that prints its data
directory (checked against 0.19.11).

CF also writes `projects.json.tmp` and `projects.json.backup` beside the file;
both are ignored.

| Setting | Flag | Default | Meaning |
| --- | --- | --- | --- |
| `cf_data_dir` | `--cf-data-dir` | `~/.config/context-forge` | Directory holding `projects.json`. |
| `cf_scan_interval_seconds` | none | 1.0 | Seconds between `stat` checks. |

## The version label (D9)

`cf --version` is captured **once, at start-up**, in `build_tenants`, with
`cf_timeout_seconds`, and stored on every snapshot as `cf_version_label` — or as
the explicit `unavailable` marker if capture fails. No tick starts a subprocess.
A CF upgrade while the process runs is not reflected until restart.

## The Runner's own writes (D8)

A CF write the Runner issues (102's `cf_write` journal kind) also changes the
file, and is also recorded as a snapshot. That is not double recording: the
journal records the command and its result, the snapshot records what CF now
holds. Nothing is deferred or skipped, because nothing is attributed. To match
its own write to a snapshot, the Runner compares `cf_updated_at`, which both its
read-back adoption and the snapshot record.

## Reading it

| What | How |
| --- | --- |
| The links | `amoeba inspect cf-links --project ID`, or `store.cf_links(project_id)`. |
| The snapshots | `amoeba inspect cf-snapshots --project ID` (text shows `changed_fields`; `--json` carries the full `changed` and `state`), or `store.cf_snapshots(project_id)`. |
| Current pointers without calling `cf` | `store.latest_cf_snapshots(project_id, cf_project_id)` → `(latest, latest observed)`. |
| Following moves | `amoeba feed --project ID --follow`, kind `cf_project_changed`. |

Both listings take `--project` only and work through a read-only handle, whether
or not the process is running.

## Trust boundary

The snapshot holds paths and pointer names, not content, and is read from a file
the same user owns. The trust boundary is the store's own, as with the feed.
Filesystem calls are unbounded (as in review detection): a CF data directory on
a stalled network mount hangs the tick, and the tenant obligation's remedy
applies.
