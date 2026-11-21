---
docType: slice-design
slice: adoption
project: amoeba
parent: user/architecture/260-slices.the-hub.md
dependencies:
- 260
- 261
- 262
- 263
interfaces:
- 265
- 300
dateCreated: 20261120
dateUpdated: 20261121
status: not_started
turns: 29
promptTokens: 2121013
cachedTokens: 1924843
cacheWriteTokens: 196138
completionTokens: 71766
durationSeconds: 814.7
costUsd: 6.394405
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-fable-5-2:
    rounds: 1
    costUsd: 6.394405000000001
    completionTokens: 71766
---

# Slice Design: adoption

## Overview

This slice moves the PM's live store to the hub and deletes the code that runs Amoeba on a local store.

- `amoeba adopt <join line>` copies a machine's local store and config to an empty hub and joins the machine, in one command that is safe to run again.
- Every command on a machine with no client file fails and says to run `amoeba join`. The mode switch, `LocalSteps`, the local store opener and the 228 state move are deleted.
- The tests that ran on a local store run through the door against a hub in the test's own process.
- The release updates the hub first, then the client it runs on.
- The hub gets a set-up document, `docs/hub-setup.md`, and the contract documents are brought in line.
- The PM's laptop is adopted onto a hub on the LAN machine by the release that ships this slice, as part of `scripts/update_live.py update`. No task in the slice touches the PM's install.

## Value

User value. The PM's decisions, messages and sessions become one store that every machine he works on reads and writes. Developer value: there is one way to run an operation, so 265 and 300 change one code path and migrate one store.

## Technical Scope

Included:

- `amoeba adopt`, with `--again`, and the three hub calls behind it. `amoeba discard-local`, which removes a store that was handed over.
- Migration 015: the `adoption` row and the closed mark's reason.
- What `join --set-aside-local` and `leave` do once no local way exists.
- Deleting the local-store way and the 228 state move, and the import rules that keep them deleted.
- Moving the tests onto the door.
- `scripts/update_live.py`, the release skill, `amoeba hub add-config-keys` and the three shell scripts that update a hub, restore or empty it, and print a join line.
- `docs/hub-setup.md` and the five contract documents.
- The release step that adopts the PM's laptop, and a rehearsal of it on a copy of the live store (D12).

Excluded:

- Members in several programs (265).
- Running agents on the hub, timers and the scheduler (300).
- Merging two stores. `adopt` loads into an empty hub only.

## Dependencies

### Prerequisites

- Slices 260 to 263, complete. After 263 every operation and every entry point is served through the door (263 D14).
- For the release, not for any task: a LAN machine the laptop reaches by `ssh`, with Docker and a clone of this repo, and `live-update.yaml` in the laptop's config directory naming the three hub commands (D10). The machine's `ssh` name is not in any project document (checked 20261120: the concept, the initiative plan, the architecture, the notes). Every task in the slice runs on fixtures and on a hub in Docker on the laptop, and needs neither. If the file is missing when the release runs, `update` stops before it changes anything and names it (D10), and the laptop stays on the previous release and its local store.
- No new package.

### Interfaces Required

- 260: the join line, the certificate fetch and `hello` of `join` (D4), `client.call`, `handle_call`, the closed mark, `open_hub_store`, backups and `serve --from-backup`, the in-process hub helper and `tests/hub_fixture.py`.
- 261: `operations.naming.name_members`, which names the members of a local store.
- 262: `Steps` and `DoorSteps`; the fix that gives old question and wake rows the `local` machine (262 D14).
- 263: `mcp.tick`, which already runs on `Steps`; `LIVE_SESSION` in `store/sql_sessions.py` and the session row's `door_version` (263 D13).
- `scripts/update_live.py` and `.claude/skills/release/SKILL.md` as they are today.

## Architecture

### Component Structure

| Package | Modules | Change |
|---|---|---|
| `amoeba.store` | `schema/015_adoption.sql`, `adoption`, `handover` (new) | The `adoption` row. Row counts and the content digest (D1). Backing up and opening a local store for a handover, marking it handed over, and deleting it. It never creates a store (D5). `handover` is one of the two modules that call `Store.open`. |
| | `relocate` | 228's copy and verify functions are deleted. 260's rename and put-back are deleted (D5). |
| `amoeba.operations` | `adopt_local` (new) | The laptop's side of adoption: open, the one-time fixes, the lock, the copy, the mark. |
| | `state_move`, `state_move_store`, `state_move_dirs`, `state_move_types`, `LocalSteps` in `store_steps` | Deleted. |
| `amoeba.hub` | `adoption` (new) | The hub's side: the check, the load, the config write. |
| | `store_open` (new) | `open_hub_store`, moved from `state_move`. The other module that calls `Store.open`. |
| | `app`, `calls`, `admin`, `serve` | The upload route. `hello` returns the hub's version. `add-config-keys`. A loading mark left by a crash is cleared at start (D4). |
| `amoeba.wire` | `protocol`, `times` | `ADOPT_CALLS`, the three header names, `ADOPT_UPLOAD_SECONDS`, `UPLOAD_IDLE_SECONDS`. |
| `amoeba.client` | `adopt` (new) | The upload. |
| `amoeba` (wiring) | `wiring_adopt` (new); `wiring`, `wiring_door`, `wiring_steps`, `wiring_presence` | `wiring_adopt` holds the steps of `adopt`, the store part of `join --set-aside-local` and `discard-local`. `joined()` raises `NotJoinedError`. Every in-process branch is deleted. |
| `amoeba.cli` | `adopt_command` (new); `join_command`, `hub_commands`, `parser` | `adopt` and `discard-local`. The new `join` and `leave` behavior. `hub add-config-keys`. |
| `amoeba.mcp` | `server`, `in_process` | No local config read, no local deadline check. Start-up with no client file (D6). |
| `amoeba.config` | `home`, `config.yaml.example` (new) | `StateLayout.legacy_home` is deleted. `legacy_state_home` stays for the one check in D7. The example config as a file in the wheel (D10). |
| `scripts`, `docker` | `update_live.py`; `hub-update.sh`, `hub-restore.sh`, `hub-invite.sh` (new) | D10. |

Import rules added to `tests/test_import_boundaries.py`:

- `Store.open` is called only in `hub/store_open.py` and `store/handover.py`. This replaces `tests/test_store_opened_only_by_state_move.py`.
- `amoeba.mcp`, `amoeba.client`, `amoeba.cli` other than `hub_commands`, and every `wiring` module other than `wiring_adopt` import nothing from `amoeba.store` but its error types.
- `amoeba.store.handover` and `operations.adopt_local` are imported only by `wiring_adopt`. `join_command` calls `wiring_adopt` for the store part of `--set-aside-local`, before the client file is written. `wiring_door` does not import `wiring_adopt`.
- `load_user_config` is called only from `amoeba.hub` and `operations.adopt_local`.

### Data Flow

`amoeba adopt <line>` on the laptop, against an empty hub:

1. **Reach the hub.** Parse the line, fetch and check the certificate, and call `hello` (260 D4, steps 3 and 4). `hello` gives the machine's name.
2. **Ask the hub.** `adopt_check` carries the laptop's adoption id, if it has one, and the schema version this program migrates to. The hub answers `empty` or `holds_this`, or refuses (D3). This is the early refusal, made before the live store is migrated.
3. **Back up.** Load the local `config.yaml` with the config loader. One that is missing or does not load stops `adopt` here, before anything is written. Then `store.handover` backs the store up before it writes anything (D5), and `adopt` copies `config.yaml` beside that backup.
4. **Open.** Open the local store, which migrates it, and run the three one-time fixes (D2). Refuse if a member is unnamed, and list the sessions to restart (D2). Write the adoption id if there is none, and commit.
5. **Lock, count, copy.** Take the store's write lock on one connection and hold it. Count every table's rows. On a second, read-only connection, copy the store with SQLite's backup call to `<state home>/adoption-copy.sqlite3`, and work out the copy's content digest (D1). Tried on 20261120 with Python 3.13.7 and SQLite 3.50.4: the second connection copies every committed row while the first holds the lock, and a backup from the lock-holding connection itself does not return. A test pins the first.
6. **Load.** Call `adopt_check` again, now with the digest, and the hub says whether to load (D1). If so, upload the copy with its SHA-256 and the counts. The hub prepares it and makes it the hub's store (D4).
7. **Config.** `adopt_config` sends the text of the local `config.yaml`. The hub validates it and writes it, or keeps the one it has and says so (D3).
8. **Switch.** In the transaction that holds the lock, write the closed mark naming the hub and the copy's digest as `handed_digest`, and commit. That one commit sets the mark and releases the lock. Then write the client file, rename the local `config.yaml` to `config.yaml.moved-to-hub`, delete the copy, and print the result.

A failure at any step before 8 rolls the lock's transaction back and deletes the copy. Nothing on the laptop has changed except the backup, the migration, the adoption id and the saved certificate, and the same command is run again. The migration is not undone: from step 4 on, an older program still running on the laptop is refused by the store's schema (D2).

That covers the laptop's own files too. A backup or a copy that cannot be written whole (a full disk, a directory that cannot be written) is deleted, and `adopt` stops with the path and the operating system's message. A failure after the mark's commit, when the client file or the rename cannot be written, leaves row 5 or row 4 of D1, and the same command finishes it.

**How long the lock is held.** Steps 6 and 7 are three hub calls made under the local store's write lock, and each has a longest time. `adopt_check` and `adopt_config` take at most 43 seconds each (260's `CALL_BOUND_SECONDS`: the retry time of 30, the connect time of 3 and the read time of 10). The upload takes at most 153: the retry time of 30, the connect time of 3 and `ADOPT_UPLOAD_SECONDS`, 120, which is the longest one whole attempt may take, sending and waiting together (D3). So the hub calls hold the lock for at most 43 + 153 + 43 = 239 seconds. The count, the copy and the digest in step 5 are local work, well under a second for a store the size of the PM's. The only program that can be waiting is a command of an older release that was already running (D2). It waits the store's busy time of 5 seconds and then fails with `StoreBusyError`, exit 3, as on any busy store today.

### State Management

| State | Where | Ends by |
|---|---|---|
| The adoption id | `adoption`, one row, in the local store and then in the hub's | Never on the hub; it says where the store came from. On the laptop, `adopt --again` replaces it |
| A local store that is handed over | The store path, at the current schema, with the closed mark | `amoeba discard-local` deletes it (D5). `adopt --again` adopts it into another hub. `update_live.py restore --local-store` puts the backup back over it (D11) |
| The pre-handover backup | `<state home>/backups/pre-handover-<stamp>/`: the store, `config.yaml`, and `previous-commit` when the release made it | `amoeba discard-local` deletes every one |
| The copy being sent | `<state home>/adoption-copy.sqlite3`, mode `0600` | Deleted when `adopt` ends, however it ends. One left by a crash is overwritten by the next `adopt` and deleted by `leave` |
| The upload on the hub | `<hub state>/adoption-upload.sqlite3` | Deleted when the upload or the load ends, however it ends, and at every hub start |
| The loading mark | The hub store's `closed_mark`, reason `loading` | Gone with the copy that replaces the store. Cleared when a load fails, and at hub start |
| A saved certificate with no client file | Client state directory (260 D1), after a failed `adopt` | Overwritten by the next `adopt` or `join`; deleted by `leave` |
| `config.yaml.moved-to-hub` | Client config directory | `adopt --again` and `restore --local-store` rename it back. `discard-local` deletes it |
| The store a failed hub update set aside, or the store and backups `hub-restore.sh --empty` set aside | `<hub state>/replaced-<UTC stamp>/` | `hub-restore.sh --put-back` or `--discard` (D10) |
| `config.yaml.before-keys` | Hub state directory | Moved back by `hub-restore.sh`. Deleted by the next `hub-update.sh` to another commit |

## Technical Decisions

### D1 — What `adopt` refuses, and running it again
Status: decided

`adopt` looks at three things on the laptop: the client file, the closed mark and the adoption id.

The rows are tried in order and the first that matches decides:

| | The laptop has | `adopt <line>` does |
|---|---|---|
| 1 | No store at the store path | Rejected: nothing to adopt; names `amoeba join` |
| 2 | A mark and no adoption id (a store set aside by `join`), with or without a client file | Rejected. Says the store was set aside, not adopted, and names `--again`. When a client file exists it names `amoeba leave` first, then `--again` |
| 3 | A mark for another hub | Rejected. Names the hub in the mark and `--again`, with `amoeba leave` first when a client file exists |
| 4 | A mark for this line's hub, and a client file | Finishes what step 8 left: the `config.yaml` rename and the copy's deletion. Then prints the result again |
| 5 | A mark for this line's hub, no client file | A switch that was cut off. When `adopt_check` answers `holds_this`: steps 7 and 8 without the mark write. When it answers `empty` or `hub_not_empty`, the hub at that address is no longer the one that was loaded: rejected, saying so and naming `--again` |
| 6 | No mark, and a client file | Rejected: the machine is joined; `amoeba leave` first |
| 7 | No mark, no client file | The full flow in Data Flow |

Rows 4 and 5 also work out the store's digest and compare it with `handed_digest`. They open the store read-only for that (D5). A difference means something wrote to the store after it was handed over (D2), and the result says so as `changed_after_handover`.

`adopt <line> --again` first clears the mark and the adoption row, and renames `config.yaml.moved-to-hub` back when no `config.yaml` is there. Then it runs the full flow with a new id and a new backup. It is the undo (D11) and the way to adopt a store that was set aside. It is rejected when a client file exists, and the message names `amoeba leave`.

Rejected is exit 1, and a rejection's result carries a `code`. A hub that cannot be reached, a `cf` failure in the naming fix, a local `config.yaml` that is missing or does not load, and a file the laptop cannot write are today's operational errors, exit 3. In every case the lock is released and the same command is run again. A missing `config.yaml` is written from `config.yaml.example` (D10) first.

Running it again after a lost reply or a failed switch follows the architecture's rule, with one case added:

| `adopt_check` finds | Then |
|---|---|
| The hub is empty (D3) | Load |
| The hub holds this adoption, and the laptop's digest equals the digest the hub loaded | Skip the load |
| The hub holds this adoption, the laptop's digest differs, and the hub's own digest still equals what it loaded | Load again, in place of the first |
| The hub holds this adoption, the laptop's digest differs, and the hub's has moved too | Refused as `both_changed` |
| Anything else | Refused as `hub_not_empty`, with each table that has rows and its count |

**The content digest** is what says a store changed. Row counts cannot: a recorded answer or a withdrawn standing answer changes a row and no count. `store.adoption.content_digest` is the SHA-256 of every row of every table outside `HUB_OWN_TABLES` (D3), read in table and key order. The laptop works it out from its copy, and the hub from the prepared upload (kept as `loaded_digest`) and from its own store when asked. Row counts stay as the check on the load itself (D4).

The fourth row is what the architecture leaves out: after a first load, another joined machine can write to the hub while the laptop still has no client file. It needs a write to the local store between two attempts, which only the late write in D2 can make.

**A second load keeps what the hub wrote for itself** where a repeat depends on it: the hub's kept call results are carried into the new copy (D4), so a writing call repeated after the load still gets its first result. The other machines' session rows and stored runs are not carried. Each is written again by that machine's next tick or `list` (263 D2, D11).

**`both_changed` and `hub_not_empty` are dead ends for one of the two stores,** because two stores are never merged. The refusal says so and gives both ways on:

- Keep the hub's records: `amoeba join <line> --set-aside-local`. The laptop's records, or its later changes, stay in the handed-over store and are on no hub.
- Keep the laptop's records: empty the hub with `docker/hub-restore.sh --empty` on the hub machine (D10), invite the laptop again and adopt into it. The hub's records are no longer served. They stay in `replaced-<stamp>/` on the hub until `--put-back` or `--discard`. The emptied hub has a new certificate, so every machine already joined gets `HubCertificateError` and needs a new invite and `join` (260 D5).

Wherever this design says to empty a hub, that script is the command. It sets the hub's backups aside with its store, because a hub does not start on an empty state directory while its `backup_dir` still holds a backup (260 D5).

### D2 — Opening the local store, and why no session can write to it
Status: decided

`operations.adopt_local` opens the store through `store.handover`, which migrates it to schema 15. It then runs the three fixes `open_state_store` ran on every open, once, in this order: make the `local` machine (260 D12), name the members (261 D4, which calls `cf`), and give old question and wake rows the `local` machine (262 D14). `open_state_store` is deleted, so `adopt` is the only place they run.

A store that holds more than the one `local` machine is not a local store and is rejected.

After the naming fix `adopt` checks, as the architecture says, that no member is unnamed, and refuses if one is. The fix names every member or raises, so this is a guard on the fix.

**Sessions.** `adopt` neither waits on an open session nor refuses because of one, because no session can write to the store after the migration:

- Every release before this one opens a new connection for each store use and refuses a store whose schema is newer than it expects (`store/migrations.py`; checked 20261121 in `wiring_presence.py`, where every heartbeat, inbox read and lookup opens the store). Migration 015 is in this release.
- This release has no code that writes a local store.

An open session's row can only go stale, and the `sessions` table is not carried to the hub (D4). After the migration `adopt` reads the live rows. Live is a fresh heartbeat: one predicate in `store/sql_sessions.py`, which 263's `LIVE_SESSION` is built from, judged with `session_stale_seconds` from the local `config.yaml` and the laptop's clock, since the rows are the laptop's own. The result carries them as `sessions_to_restart`, each with what happens next: one whose row has this release's `DOOR_VERSION` uses the hub from its next tick once the machine is joined (263 D1); one with another version or none must be restarted. A row with none is a program from before 263. The release prints the list (D10). From the migration on, an older `amoeba-mcp` still running on the laptop has failing tools until it is restarted. An `adopt` that fails for another reason is put back with the pre-migration backup (D11).

**A connection opened before step 4.** A command of an older release that was already running may hold one. The lock makes it wait, and the closed mark makes its next write fail naming the hub, for releases from 260 on. A release before 260 has no mark check, so its write succeeds with no error and is not on the hub. The one writer that runs long enough to matter is a `handle-pause` in the middle of an answering run, and what it writes is its settle. The question on the hub is still `claimed`, its claim goes stale, and the laptop's next call starts `handle-pause` again (262 D10). The cost is one repeated answering run.

The write is not silent for long. The switch records the copy's digest in the local store as `handed_digest` (Data Flow, step 8). `adopt` run again and `discard-local` each compare the store with it and report `changed_after_handover`, and `discard-local` then refuses to delete the store without `--force` (D5).

### D3 — The hub calls
Status: decided

`ADOPT_CALLS` in `wire.protocol` holds three names. They are not operations and are not in `SERVED_OPERATIONS`. All three need the token. None keeps a result under 260's repeat rule. Each is made safe to repeat by what it carries: the adoption id and digest for the first two (D1), and the config text for the third.

| Call | Carries | Answers |
|---|---|---|
| `POST /call/adopt_check` | The adoption id or null, the schema version, and on the second call the laptop's digest | `empty`, or `holds_this` (with whether to load, when the digest was sent), or a refusal |
| `POST /adopt/store` | The copy as the body. Headers: `Amoeba-Adoption-Id`, `Amoeba-Store-Sha256`, `Amoeba-Row-Counts` (a JSON object of table to count) | `loaded` with the counts, or a refusal |
| `POST /call/adopt_config` | The adoption id and the config text | `written`, `same` (the hub's file already holds this text) or `kept` (the hub has a different one) |

**The tables.** One list in `store.adoption` says how each table that is not a record table is treated. The emptiness check and the digest are both worked out from it, and a table added later is checked and digested unless someone adds it here.

| Table | Why it is listed | Checked for emptiness | In the digest |
|---|---|---|---|
| `machines` | The hub's own; the load carries them over | No | No |
| `sessions` | Written by each open session's tick | No | No |
| `machine_runs` | Written by each machine's `list` | No | No |
| `call_results` | Written by every writing call | No | No |
| `closed_mark` | The loading mark | No | No |
| `adoption` | Read by the check itself | No | No |
| `schema_meta`, `owners`, `pm_marker` | One fixed row that a new store already holds | No | Yes |

The first six are `HUB_OWN_TABLES`. **Empty** means no rows in any table not in this list, and no `adoption` row. So another machine's open session does not make a hub count as not empty.

New refusal codes in `RefusalCode`: `hub_not_empty`, `both_changed`, `schema_differs` (the message holds both versions and says which side to upgrade) and `copy_damaged` (the SHA-256 or a count does not match; the hub's store is untouched).

**The door version does not change.** These are added calls and added codes, and no existing call changes. `ADOPT_UPLOAD_SECONDS` and `UPLOAD_IDLE_SECONDS` are used by the upload alone. The architecture says a changed network time changes the door version, because a kept result's lifetime, the claim limits and the `answer` deadline are worked out from those times and must agree on both sides. Nothing is worked out from these two, and the client's one and the hub's one do not have to agree. So they are not in 260's pinned tuple, and that exception is in the departures table.

**The upload** is the one call whose body is not JSON, so it has its own route. The token is checked before any of the body is read. There is no fixed size limit; the limit is the time one attempt may take, below. Every refusal in the table is a line in the hub's log, as any refused call is (260 D16).

The route takes the body in chunks. Each chunk's write and hash, and the whole of the load (D4), run in worker threads through `anyio.to_thread.run_sync`, as 260's calls do, so no file or store work runs on the event loop. What can go wrong on the hub, and what it does:

| Case | The hub |
|---|---|
| No `Content-Length`, or a missing header | Refuses as `malformed_call` before reading the body |
| Another upload is in progress (one in-process flag, since the upload has one file) | Refuses as `hub_error`, saying an adoption is loading, without reading the body, and closes the connection |
| The hub already holds this adoption and the body's digest equals `loaded_digest` (a repeat after a load whose reply was lost) | Answers `loaded` with its counts and loads nothing |
| The connection closes before `Content-Length` bytes arrive | Deletes the partial file and logs one line. There is nobody to reply to; the client sees no reply and retries |
| No body bytes arrive for `UPLOAD_IDLE_SECONDS` (30, in `wire.times`) | Closes the connection, deletes the partial file and logs one line |
| The disk fills while the body, the prepared copy or the store is written | Refuses as `hub_error` with the operating system's message and the path. The hub's store is untouched. The exit is freeing space |
| The whole body arrived and its SHA-256 is not the header's | Refuses as `copy_damaged` |

The client sends the body in chunks, with the usual retry. One attempt may take `ADOPT_UPLOAD_SECONDS` (120, in `wire.times`) from its first byte to the reply, sending and waiting together. The client checks the time between chunks and sets what is left as the socket's wait, and an attempt that reaches the limit is stopped and counts as no reply. So a slow but steady upload cannot hold the laptop's lock past the bound in Data Flow. A store too large to send in that time on this network fails with `HubUnreachableError`, which gives the store's size and the time allowed. The ways on are a faster connection to the hub, or `join --set-aside-local`.

No reply inside the retry time is an unknown outcome, and the error says to run `amoeba adopt` again, which reads what the hub holds. A connection the hub closes while the client is still sending counts as no reply: the client retries, and if that goes on past the retry time it fails with `HubUnreachableError`, saying the hub closed the connection during the upload.

`adopt_config` requires the hub to hold that adoption. It validates the text with the config loader. A config that fails is refused as `hub_error` with the loader's message; the laptop validated the same text first, so this means the two sides are different releases. With no `config.yaml` it writes one through a temporary file and a rename. A config directory it cannot write to is `hub_error` naming the path; the compose example's config mount is therefore not read-only.

### D4 — The load
Status: decided

The hub's store is replaced whole, in one SQLite backup call, and never built up table by table.

1. Write the body to `adoption-upload.sqlite3` and check its SHA-256.
2. In one write transaction on the hub's store: check the hub against D1's table, read the hub's machines and kept call results, set the loading mark, and commit.
3. Prepare the upload, in one transaction on that file:
   - rename its `local` machine to the calling machine's name and give it that machine's token hash;
   - insert every other machine the hub has, with a new id and the copy's owner;
   - insert the hub's kept call results under their machines' new ids (D1);
   - set `loaded_at` and `loaded_digest` on the `adoption` row.
4. Count the upload's rows and compare them with the header, table by table. `machines` is compared as the laptop's one plus the hub's others. A difference is `copy_damaged` and stops here, so the hub's store has not been touched.
5. Copy the upload into the hub's store with the backup call, in one step. The prepared upload has no mark, so this also ends the loading mark.
6. Answer `loaded` with step 4's counts. In a `finally`: clear the loading mark if step 5 was not reached, and delete the upload.

Step 5 was tried on 20261120 with the project's Python 3.13.7 and SQLite 3.50.4, with the destination in WAL mode and other connections open on it. The copy lands as one transaction: a writer that arrived during it waited and then saw the new rows, a reader inside a transaction kept its old view until it ended, and the `AUTOINCREMENT` counters came with the copy. `tests/hub/test_adoption_load.py` pins this.

Nothing is compared after step 5, so `copy_damaged` always means the hub's store is as it was. The counts were checked in step 4 on the very file that step 5 copies, and the copy is one SQLite call that lands whole or not at all. A count of the hub's store after the copy could only fail with that store already replaced, with no way on but emptying the hub, so there is none. The test above asserts the counts and the digest of the hub's store after a load, and the release reads `list` back after the adoption (D10).

**The loading mark.** Between the read in step 2 and the copy in step 5, a write to the hub's store would be removed by the copy, or put back from the step-2 read. That includes a `hub rm-machine` or a re-invite, whose old token would work again. So step 2 sets 260's closed mark on the hub's store, with the reason `loading` (D8). Every write transaction checks the mark right after it takes the lock (260 D4), in the serving process and in an admin command alike, and fails saying an adoption is loading. A call is refused as `hub_error`; an admin command exits 3. Either is run again.

A hub that crashes between steps 2 and 5 leaves the mark set. `amoeba hub serve` clears a `loading` mark when it starts, since no load can be running then.

The load takes well under a second for a store the size of the PM's (160 KB on 20261120). A tick that arrives while the mark is set is refused at once, not held, and is a skipped tick (263 D4). `tests/hub/test_adoption_load.py` sends ticks during an upload whose body arrives slowly and during the load, and asserts each is answered inside the load test's 2 seconds. It also runs `hub rm-machine` between steps 2 and 5, and asserts it is refused and that the machine's token still works after the load, then ends when the command is run again.

- Rejected: `ATTACH` and `INSERT ... SELECT` per table. It keeps the hub's machine ids, but it has to list tables, order them for foreign keys and carry the sequence counters by hand.
- Rejected: replacing the store file. A call that had the old file open would write into it after the rename.

### D5 — `join` and `leave` once there is no local way
Status: decided

260 set a local store aside by renaming it, and `leave` put it back. Both go, for one reason: a release before 260 that finds no file at the store path creates an empty store there and carries on. An older `amoeba-mcp` left running would then record its agent's messages into a store nobody reads.

So a store that is handed over, by `adopt` or by `join --set-aside-local`, stays at the store path, at the current schema, with the closed mark. An older program that opens it is refused for the schema. It leaves that state by `adopt --again` or by `amoeba discard-local`.

**The backup.** `store.handover` backs a store up before it migrates or writes to it: with SQLite's backup call, into `<state home>/backups/pre-handover-<UTC stamp>/amoeba.sqlite3`. It does this whenever the store has no mark and no adoption id, so `adopt` and `--set-aside-local` both get it, and a second run of either takes no second copy. Both commands print the path. The restore path is in D11.

**`store.handover` never creates a store.** 260's guard stopped a local store being opened, and so created, on a machine with a client file. The openers it guarded are deleted (D7), and `store.handover` is the one local opener left, so the rule moves into it. It tests that the file exists, then opens it with SQLite's `mode=rw`, or with `mode=ro` where the command only reads: the digest in rows 4 and 5 of D1 and in `discard-local`. On a joined machine `adopt` and `discard-local` therefore never write to the store. Tried on 20261120 with SQLite 3.50.4: both modes fail on a missing path and create no file, and a `mode=ro` connection reads the committed rows of a store in WAL mode and cannot write. With no store at the path, `adopt` is rejected (D1, row 1), `discard-local` is rejected saying there is nothing to discard, and `join --set-aside-local` joins and says no store was there.

- **`amoeba join <line>`** refuses when the store path holds a store with no mark, and names `amoeba adopt` and `--set-aside-local`. A marked store does not stop it.
- **`amoeba join <line> --set-aside-local`** opens the store through `store.handover`, which backs it up and migrates it, and writes the mark. The store's records stay there and are on no hub.
- **`amoeba discard-local`** ends the state, on a machine that is joined or not.
  - It deletes every `backups/pre-handover-*` directory, then `config.yaml.moved-to-hub`, then the handed-over store with its side files. The store goes last, so a run that was cut off still finds a marked store and finishes when run again. It prints each path before it deletes it.
  - It refuses a store with no mark, and names `amoeba adopt` and `join --set-aside-local`.
  - Without `--force` it deletes only when it can show the records are on a hub: the machine is joined, `adopt_check` on that hub answers `holds_this` for the store's adoption id, and the store's digest is `handed_digest` (D2). Otherwise it refuses and says which of four things is the reason: the store was set aside and never adopted; the machine is not joined; the hub does not hold this adoption; the store changed after it was handed over.
  - `--force` deletes in each of those four cases and makes no hub call. So a store on a machine that has left its hub still has an exit.
  - It deletes the pre-migration backup, which both undo paths in D11 need. The output says that neither is possible afterwards, and that the hub's own backups are then the only copies.
  - It is the PM's command: nothing in this slice or in the release runs it. An older program still running on the machine would create an empty store at the path afterwards (the reason above), so the command's output says to restart the sessions `adopt` listed first.
- **`amoeba leave`** deletes the client file, the saved certificate and a left-over `adoption-copy.sqlite3`. It no longer touches a store. When the store path holds one, it prints the path and says nothing reads it.

### D6 — With no client file
Status: decided

`wiring_door.joined()` returns the client file or raises `NotJoinedError`, an operational error (exit 3; an error result on MCP). The text: this machine is not joined to a hub; run `amoeba join <line>` with a line from `amoeba hub invite <machine>` on the hub. When a file exists at the store path it adds that `amoeba adopt <line>` moves that store to an empty hub. That is a file-exists test; the store is not opened.

| Entry point | With no client file |
|---|---|
| `wiring.invoke`, any operation | `NotJoinedError` |
| `amoeba handle-pause`, `wake-run`, `resume-run` | `NotJoinedError`, before anything local is read. No calls-log line |
| `amoeba-mcp` start | Starts, with one WARNING on stderr. Its tools return `NotJoinedError` and its ticks are skipped (263 D4). A machine that joins later is served from the session's next call, with no restart |
| `amoeba hub ...` | Unchanged: these never read the client file, except to refuse in a home that has one (260 D2) |
| `amoeba join`, `adopt`, `leave`, `discard-local` | Run. `discard-local` then needs `--force` (D5) |

`amoeba-mcp` starts because the mode is decided on every call. Refusing to start would make the PM restart a session only because it was opened before `join`.

### D7 — What is deleted
Status: decided

| Deleted | Consumers updated in the same task |
|---|---|
| The four `operations/state_move*` modules, 228's part of `store/relocate.py`, `StoreRelocateError`, `StateLayout.legacy_home`, `MOVE_LOCK_NAME` | `wiring`, `mcp/server`, `operations/deps`, `status`, `status_placement`, `wake`, `wiring_messages`, which name them today |
| `open_state_store` | Its three fixes move to `adopt_local` (D2). `open_hub_store` moves to `hub/store_open.py` |
| `LocalSteps`, and the choice in `wiring_steps.steps_for` | `steps_for` returns `DoorSteps` or raises `NotJoinedError` |
| The in-process branch of every `wiring` placement (client part, then hub part on a local store) | Each placement runs the client part and makes the door call |
| The local `config.yaml` reads on a client: `amoeba-mcp`'s start checks and its `answer` deadline check, with `answer_bound_seconds` and `ANSWER_STORE_WAITS` | The hub's check is the only one (263 D9) |
| 260's guard in the two store openers and `prepare_state_home` | The local opener and `prepare_state_home` are deleted with it. `store.handover`, the one local opener left, never creates a store and only reads one for a joined machine's `adopt` and `discard-local` (D5). Hub commands keep their refusal |
| 260's rename and put-back of a set-aside store | D5 |

A machine whose store is still under `~/.config/amoeba` from before 228 is not moved any more, and is not passed over without a word. `join` and `adopt` test whether a file exists at the old store path (`legacy_state_home`, which stays for this). If one does they are rejected, naming the file and saying to install the release before this one and run any command once, which moves it. The PM's laptop has none: on 20261120 its `~/.config/amoeba` holds `config.yaml` and nothing else. The test stays because Amoeba is published on PyPI, so an install that is not the PM's can still have one. `adopt` deletes the empty `.state-move.lock` file the move left in the state home.

`tests/test_old_command_names_gone.py` gains the deleted names, so none comes back.

### D8 — The schema: migration 015
Status: decided

`015_adoption.sql` adds one table, `adoption`, holding at most one row: `adoption_id` (text), `started_at`, `loaded_at` (null until a hub loads it), `loaded_digest` (text, null until then) and `handed_digest` (text, set on the laptop at the switch). It is a single fixed row like `schema_meta`, so it has no owner.

`closed_mark` gains `reason`, one of `handed_over` and `loading`, pinned to an enum by the vocabulary test. The table is empty in every store in use, so no row needs a value. `EXPECTED_SCHEMA_VERSION` becomes 15. The migration runs on a hub at its next start, with the hub's own backup before it (260 D15), and on a local store when `adopt` or `join --set-aside-local` opens it.

### D9 — Tests
Status: decided

The fixture `joined_home` starts 260's in-process hub (the real app in a thread, with a real certificate, D18) on a throwaway store, with a clock the test sets. It invites one machine and writes the client file and saved certificate into the test's `AMOEBA_HOME`. This is the plan's "in-process hub on a throwaway store". No second way to reach a hub is added.

What happens to each kind of test:

| Test | After |
|---|---|
| Store tests, and tests of hub parts and steps as plain functions | Unchanged |
| Tests that call `wiring.invoke`, `cli.main` or an MCP tool in a home with no client file | Use `joined_home`. Assertions are unchanged |
| Tests that run on `LocalSteps`, and the parametrized pairs of 262 and 263 | Run on `DoorSteps` in `joined_home`, once |
| Tests that start `amoeba` or `amoeba-mcp` as a subprocess | Use a hub from `tests/hub_fixture.py` |
| `tests/load/`: messages, report-release, start-ended-held, wake-claim | Same writers and assertions, calling the fixture hub through the door |
| `tests/load/test_presence_load.py` | Deleted. 263's 50 ticking sessions on the door load test assert the same |
| `tests/load/test_no_cf_under_write_lock.py` | Kept, and pointed at `adopt`. Its `report_release` case goes, because the hub's part takes no `cf` and the hub's `PATH` holds none (260 D11). Its lock-probing `cf` now runs under `adopt` on a fixture store: every `cf` call of the naming fix (261 D4) is made with no write lock held, and none is made after step 5 takes the lock |
| The state-move and legacy tests, and tests of the mode switch and guard | Deleted with the code |
| `tests/live/` single-home variants | The live harness starts a fixture hub and joins the home |
| `tests/scripts/test_update_live.py` | Rewritten for D10, with fake commands for the hub |

Adoption's own tests are in `tests/hub/test_adopt*.py`, on a fixture laptop home whose store is built by the seed helpers at schema 10, so the migrations and the three fixes run. A cut is made with a hook on `adopt_local` (`AdoptHooks`, the pattern of 260's `DoorHooks`): after the load, after the config, and after the mark.

The door load test (260 D18, as widened by 261 to 263) runs unchanged, and its bounds still hold: every call inside 2 seconds with 16 clients, a median under 200 ms on an idle hub. Adoption adds no call to the steady state.

### D10 — The release
Status: decided

The live install is updated by `scripts/update_live.py update`, as the last step of a release and at no other time. On a joined machine it does this, in order:

1. Read `live-update.yaml` in the config directory. It has three required keys, `hub_update_command`, `hub_restore_command` and `hub_invite_command`. A missing file or key stops the script and names it, with nothing changed.
2. Record what `amoeba list -j` shows, and the installed commit, as today.
3. Run `hub_update_command` with the checkout's commit as its last argument, for at most `HUB_COMMAND_SECONDS` (900, a constant in the script; the command builds an image). A command still running then is stopped and counts as failed.
4. Call `hello` until the hub answers with the release's version, for at most `HUB_UPDATE_WAIT_SECONDS` (300, a constant in the script).
5. Install this checkout with `uv tool install`, as today.
6. Read back: `amoeba list -j` succeeds and shows the same members, and `amoeba-mcp` lists its tools.
7. Print the machines and sessions that are behind, from `list` (263 D12), with the upgrade command for each.

What a failure does depends on which side failed:

- **Step 3 or 4,** the hub's side: the script runs `hub_restore_command` with the previous commit, under the same time limit, and exits 1 with what it did. The laptop has not been touched. If the restore command itself fails or runs out of time, the script exits 1 saying the hub may be down and printing the restore command, which is safe to run again.
- **Step 6,** the laptop's side: the script reinstalls the previous commit on the laptop and exits 1. The hub is left as it is, because it is serving. If the release changed the door version, the laptop's commands then refuse with the upgrade command. The script's output says so and names the two ways on: `update` again with a fixed release, or `restore --hub`, which puts the hub back too.

`restore` reinstalls the previous commit on the laptop. `restore --hub` also runs `hub_restore_command`. `restore --local-store` goes back to the release before the hub (D11).

**The first run on a machine with a local store is the adoption.** When the machine has no client file and a store at the store path, `update` adopts it. This is how the PM's laptop is adopted (D12), and nothing in it is done by hand. Steps 1 to 3 are the same, and then:

1. Run `hub_invite_command`, which prints a join line for this machine. It is run again every few seconds until it succeeds, for at most `HUB_UPDATE_WAIT_SECONDS`. This takes the place of step 4, because a machine that is not joined cannot call `hello`. A hub on another schema is refused by `adopt_check` (D3).
2. Install this checkout, as in step 5.
3. Run `amoeba adopt <line> -j`.
4. Write the commit that was installed before into the pre-handover backup directory, as `previous-commit`.
5. Read back as in step 6, and compare the programs, members, open questions and requests of `amoeba list -j` with what step 2 recorded.
6. Print the backup's path, the row counts, `sessions_to_restart`, and step 7's list.

What a failure does on this path:

- **Step 3 of the main list, or the invite:** the script stops and exits 1. The laptop has not been touched and is still on the previous release and its local store. There is no earlier hub to put back, so `hub_restore_command` is not run. `update` is run again.
- **The `adopt` or the read-back:** the script runs `restore --local-store` itself and exits 1 with the error. The laptop is back on the previous release, with its store and config as they were before the migration. If the hub had already loaded the store, it still holds that copy, and the next `update` is refused as `hub_not_empty`. The script's output says so and names `hub-restore.sh --empty`.

A machine with no client file and no store has nothing to adopt. The script stops at step 1 and says to run `amoeba join`.

The script no longer backs up, migrates or checks a local store. The hub backs its own store up before a migration, and `adopt` takes the pre-handover backup. The one place it still writes a store is `restore --local-store`.

`hello`'s reply gains `hub_version`, the hub's package version. An added field does not change the door version.

**On the hub machine,** three scripts shipped in `docker/`, run from the clone that holds the compose file:

- `hub-update.sh <commit>`: fetch and check out the commit, build the image, run `amoeba hub add-config-keys` in the new image, then `docker compose up -d`. The hub takes its own backup before a migration when it starts. Two things make it safe on a first run and on a later one:
  - When the config directory holds no `hub.yaml`, it first writes `hub.yaml` and the compose file from the shipped examples and prints both paths. So the first run sets the hub up, and the release needs nothing done on the hub machine beyond the clone. The example's `backup_dir` is a directory beside the state directory; `docs/hub-setup.md` says how to point it at another disk.
  - When the clone is not already at the commit, it deletes `config.yaml.before-keys` before anything else. That file belongs to an earlier update, and `hub-restore.sh` would otherwise put a months-old config back after a failed one.
- `hub-invite.sh <machine>`: runs `amoeba hub invite <machine>` in the running container and prints the join line.
- `hub-restore.sh <commit>`: the architecture's undo, the previous image with `serve --from-backup`, as one script. Stop the hub, check out and build that commit, and move `config.yaml.before-keys` back over `config.yaml` if the update wrote one. If the update made a pre-migration backup, move the store, certificate and key into `replaced-<UTC stamp>/` inside the state directory and start once with `--from-backup` on that backup. Then `docker compose up -d`. It stops at the first step that fails and can be run again from any point: it moves the three files only when they are there, and starts from the backup only when the state directory holds no store. Until it finishes the hub is down.
- What was recorded after the update began is not on the restored hub. It is in `replaced-<stamp>/`, and the script prints that path. `hub-restore.sh --put-back <dir> <commit>` stops the hub, moves the current three files into a new `replaced-<stamp>/`, moves that directory's files back, and starts the given commit, which is the fixed release. `hub-restore.sh --discard <dir>` deletes one.
- `hub-restore.sh --empty` stops the hub, moves the store, certificate and key into a new `replaced-<stamp>/`, moves everything in `backup_dir` into `replaced-<stamp>/backups/`, and starts the hub, which makes a new store and certificate. The backups have to move too: 260's hub refuses to start on an empty state directory while `backup_dir` holds a backup (260 D5), and a new hub must not rotate the old hub's backups out. It is the command behind every "empty the hub" in this design (D1, D11). The directory it leaves ends the same two ways. `--put-back` on a directory that holds `backups/` also sets the current backups aside with the current three files and moves the kept ones back into `backup_dir`, and `--discard` deletes them with the rest. It stops at the first step that fails and can be run again, as the restore can.

`live-update.yaml` holds the three commands because only the PM's set-up knows them. For the PM's hub each is `ssh`, the hub machine's name, and the path of one of the three scripts in the clone there, with the laptop's machine name after `hub-invite.sh`. For a hub on the same computer each is the script's path.

**`amoeba hub add-config-keys`** replaces the script's `add_missing_keys`, which edited a config file that is no longer on the laptop. It works on top-level keys only, which is what every key in the config contract is. A key is missing when the parsed file's mapping does not have it. Each missing key is written as YAML at the end of the file, and a key the file already has is never touched or written twice. A wrong value inside a key, such as an `authorize_items` entry without one of its fields, is not this command's to fix; the loader reports it as today. It first copies the file to `config.yaml.before-keys` in the state directory. Then it writes the new text to a temporary file beside `config.yaml` and renames it over the old one, as `adopt_config` does, so a crash or a full disk partway leaves the old file whole. A write that fails is exit 3 with the path, and the command is run again. It prints the keys it added. With nothing to add, or with no `config.yaml` yet (a hub that is waiting for its adoption), it writes nothing.

The values come from `amoeba/config/config.yaml.example`, a YAML file in the wheel that the command loads with the YAML parser. Today the script scrapes them from the example block of `docs/config-contract.md`; that block stays as documentation, and `tests/test_contract_docs.py` asserts it equals the file. A required key the file has no value for fails the command with the key named, and nothing is written. A test loads the shipped file as a valid config, so that cannot happen in a release.

The release skill's step 7 becomes: run `update`, and report what it prints. That is the machines and sessions behind, and on the adoption run also the backup's path, the row counts and the sessions to restart. The skill keeps its line that this is a release step and not a per-slice one. The script's read-back checks from 260 to 263 that open the local store are removed.

- Rejected: restoring the hub by hand, following `docs/hub-setup.md`. A hub that fails its migration is down for every machine, and today's script puts a failed update back by itself.

### D11 — Moving and undoing
Status: decided

Nothing new is built for moving. The slice tests the architecture's path on the fixture and writes it down: `amoeba hub backup`, `amoeba hub serve --from-backup <dir>` on another state directory, `amoeba join --address` on each machine.

Undoing an adoption that went wrong, found later:

- **Adopt again.** `amoeba leave`, `hub-restore.sh --empty` on the hub machine, `hub-invite.sh` for the laptop, `amoeba adopt <line> --again`. The laptop's store is as it was at adoption, so what was recorded on the hub since is not on the new hub. It is kept in `replaced-<stamp>/` until `--put-back` or `--discard`. Other machines join the new hub with new invites.
- **Back to the release before the hub.** `uv run python scripts/update_live.py restore --local-store`. It runs `amoeba leave`, copies the oldest `backups/pre-handover-<stamp>/amoeba.sqlite3`, which is the one taken before the migration, over the store path with SQLite's backup call, puts that backup's `config.yaml` back in the config directory, deletes `config.yaml.moved-to-hub`, and installs the commit named in the backup's `previous-commit`. When the adoption was cut off before that file was written, it uses the script's own record of the installed commit, as `restore` does today. With no pre-handover backup, which is the case after `discard-local`, it stops with nothing changed and says so. What was recorded on the hub since the adoption is not on the laptop. This is the stated restore path for the migration `adopt` runs on the live store, and it is the command the release runs by itself when the adoption fails (D10).

An install with no checkout, which has no script, does the same four things by hand, and `docs/hub-setup.md` lists them. That is the restore path for `join --set-aside-local` on such a machine.

Both paths need the handed-over store or its backup, so neither is possible after `discard-local` (D5).

The architecture starts a hub straight from the laptop's backup and invites its one machine. 260's hub refuses a store with no certificate (260 D5), and `--again` reaches the same end with the command that already exists.

### D12 — Documents and the PM's install
Status: decided

`docs/hub-setup.md` is new: the clone and `live-update.yaml`, start a hub, invite, join, adopt, the fresh hub with no store to adopt, change a setting, move `backup_dir` to another disk, release and restore, empty a hub, move, undo. The call format gets its section there, taken from 260 D6 to D10.

Brought in line: `docs/cli-contract.md` (`adopt`, `hub add-config-keys`, `join` and `leave` as in D5, `NotJoinedError`, no local way), `docs/config-contract.md` (one config, on the hub; `live-update.yaml`), `docs/store-contract.md` (migration 015, the homes, with the pre-228 section removed), `docs/mcp-server.md` (start-up as in D6, no local config), `docs/squadron-hook.md` (a hook on a machine that is not joined). `tests/test_contract_docs.py` pins them.

`260-arch.the-hub.md` and the 264 entry of `260-slices.the-hub.md` hold, as amended on 20261120, the rows of the departures table below that change them: the principles "Only the hub opens the store", "One hub call is one whole transaction" and "A repeated call is safe", the door's one call that is not JSON and its two times, the meaning of an empty hub, the six adoption steps with the adopted mark and the undo, and the plan's entries for the release, the PM's install and where a store may be opened. So this design is read against parents that already hold its departures, and no task amends them. 265 and 300 read those documents, not this one.

**The PM's install is not a task of this slice.** The live install is updated by `scripts/update_live.py update` as the last step of a release, never per slice and never per merge, and adoption is no exception. The PM's store is adopted by the release that ships this slice, after code review and the merge, by the first-run path in D10. So the live store is only ever moved by code that has been reviewed, and a review fix to migration 015, the three fixes or the load is made before any real data has met them.

Nothing at the release is left for a person to do or remember. The release skill's step 7 runs `update`. `update` sets the hub up or updates it, gets the join line, installs the release, adopts, reads back and prints the backup's path, and it puts the laptop back by itself if the adoption fails. The one thing it needs that this slice cannot make is in Prerequisites: the clone on the hub machine and `live-update.yaml`. Without them it stops before it changes anything and names the file, and the laptop carries on with the previous release and its local store.

Implementation proves the same path without the PM's install:

- **On fixtures.** The tests in D9, and `tests/scripts/test_update_live.py` for the first-run path with fake hub commands.
- **The rehearsal,** the slice's last task, after the whole suite passes. A hub in Docker on the laptop is set up by `hub-update.sh` on its first run. A throwaway `AMOEBA_HOME` gets a copy of the live store, taken with SQLite's backup call on a read-only connection, and a copy of the live `config.yaml`. `hub-invite.sh` gives a line, and `uv run amoeba adopt <line>` from the slice's checkout adopts that home. `amoeba list -j` there must show the programs, members, open questions and requests that the installed release shows for the live store. The live store and the installed release are not written or changed. The output, with the row counts, goes in the slice notes.

### Departures from the parent documents

| Parent says | This design | Why |
|---|---|---|
| Adoption is refused if a member is unnamed | Kept. `adopt` also runs the naming fix first | The local opener that ran it is deleted |
| The store is renamed to a dated backup | It stays at its path, marked. The dated backup is taken before the migration | An older program that found no file would create an empty store (D5) |
| The lock is held until the client file is written | The mark is written in the lock's own transaction, and the client file after it | SQLite releases the lock at the commit; a writer that gets it next meets the mark |
| A hook waiting on the lock fails naming the hub | True for a connection of a release from 260 on. This release's hook fails with the join message and touches no store | This release has no local way |
| A count mismatch empties the hub back to its owner and machines | Counts are checked before the hub's store is touched | The store is replaced in one step (D4) |
| Matching row counts mean the hub already holds the data | A digest of the rows decides; counts check the load | A changed row changes no count (D1) |
| A hub that already holds the adoption with other counts loads the new copy | Only if the hub's own digest has not moved | Another machine may have written to the hub (D1) |
| A hub is empty when it holds nothing but its owner and its invited machines | Sessions, last reported runs and kept call results do not count either. The load drops the first two and carries the third | A joined machine writes them by itself, and writes them again at its next tick or `list` (D1, D3) |
| No transaction spans two network calls | The laptop's local write lock is held across three, for at most 239 seconds of hub calls | The architecture's own step 3 holds it to step 6. It is a lock on the store being handed over, not a hub transaction |
| The door is HTTPS with JSON | The upload's body is the store copy, on its own route. Its refusals are logged like any other | A store is not a JSON document (D3) |
| A changed network time changes the door version | `ADOPT_UPLOAD_SECONDS` and `UPLOAD_IDLE_SECONDS` are outside the pinned tuple | Only the upload uses them, nothing is worked out from them, and the two sides need not agree (D3) |
| With a client file, no local store is ever opened or created | `adopt` run again and `discard-local` open a handed-over store read-only, for its digest. Nothing creates one | The digest is how a late write is seen (D2, D5) |
| Every writing call keeps its result for a repeat | The three adoption calls keep none. Other calls' kept results are carried across a load | A repeat is answered from the adoption id, the digest and the config text (D3) |
| The hub's config directory holds two files and nothing else | Unchanged. It must be writable, and `add-config-keys` keeps its copy in the state directory | Adoption writes `config.yaml` there |
| Undo: start a hub from the laptop's backup and invite its machine | `adopt --again` into an emptied hub, or `update_live.py restore --local-store` for the release before the hub | D11 |
| The way to empty a hub is to start it on an empty state directory | `hub-restore.sh --empty` sets the store, certificate, key and backups aside and starts the hub, and keeps what it held | An exit should be a command, and 260's hub refuses an empty state directory beside a `backup_dir` that holds a backup (D10) |
| No code opens a store outside the hub and its admin commands | Also `adopt`, `join --set-aside-local` and `discard-local`, through `store.handover`, which never creates one | Handing a local store over means opening it |
| The 228 state move is deleted | One file-exists test for the old store path stays | A machine with old state is told, not passed over (D7) |
| The local `config.yaml` is no longer read | It is also renamed to `config.yaml.moved-to-hub` | An edit to a file nothing reads would fail without a word |
| The release updates the hub first, then each client | The script updates the hub and the client it runs on, and lists the others | It cannot reach the other machines |
| The plan lists no schema change, no admin command and no `discard-local` | Migration 015, `hub add-config-keys`, `discard-local` and the three hub scripts | The adoption id must travel with the store; the config moved to the hub; a handed-over store needs a command that ends it; the release has to reach the hub |
| The PM's install is part of the slice, with the adopted store as a criterion and the backup's path in the slice notes | The release adopts the PM's store, after review and the merge, and prints the path. The slice proves the path on fixtures and on a copy of the live store | The live install is updated only by a release (D12) |

### Amendments to 260 and 263

| Design says | This slice |
|---|---|
| 260 D4: `--set-aside-local` renames the store, at most one set-aside exists, and `leave` puts it back | D5 |
| 260 D12: `closed_mark` holds `hub_address` and `closed_at` | Also `reason` (D8) |
| 260 D2: `joined()` returns nothing with no client file | It raises `NotJoinedError` |
| 260 D2: both store openers and `prepare_state_home` raise `LocalStoreClosedError` when a client file exists | The local opener and `prepare_state_home` are deleted. `store.handover` never creates a store (D5, D7) |
| 260 D4: `hello` returns the machine's name | Also `hub_version` |
| 260 D12: `state_move.py` holds both openers | `hub/store_open.py` and `store/handover.py` |
| 260 D17: the compose example's three mounts | The config mount is writable |
| 260 D17: the contract's example block is the one source of the `config.yaml` example | `config.yaml.example` in the wheel is the source, shipped beside `hub.yaml.example`; the contract's block is tested equal to it (D10) |
| 263 D8: with no client file, `amoeba-mcp` runs today's start checks | It starts and its tools return `NotJoinedError` (D6) |
| 260 D19, 261 D16, 262 D14, 263 D14: read-back checks in `update_live.py` | Replaced by D10 |

## Implementation Details

### Migration Plan

- **The code.** D7 lists what is deleted and which modules are updated with it. Each deletion and its consumers are one task, so the suite passes after each.
- **The tests** move first (D9): `joined_home` is added and the suite is moved onto it while the local way still exists. The local way is deleted only once no test uses it.
- **The data.** The PM's store is copied, not transformed: the hub's store is the laptop's store with one machine renamed (D4).
- **Behavior kept.** Every operation's document and result are unchanged. What changes for the PM: the config is edited on the hub, a release updates the hub first, and a machine must be joined.

### API Contracts

```
amoeba adopt <line> [--again] [-j]
amoeba discard-local [--force] [-j]
amoeba hub add-config-keys [-j]

uv run python scripts/update_live.py update
uv run python scripts/update_live.py restore [--hub | --local-store]

docker/hub-update.sh <commit>
docker/hub-invite.sh <machine>
docker/hub-restore.sh <commit>
docker/hub-restore.sh --empty
docker/hub-restore.sh --put-back <dir> <commit>
docker/hub-restore.sh --discard <dir>
```

`adopt`'s result: `outcome` (`adopted`, `already_adopted`), `hub`, `machine`, `counts`, `config` (`written`, `same`, `kept`), `backup` (the pre-handover path), `store` (the handed-over store's path), `sessions_to_restart` and `changed_after_handover`. A rejection's result has a `code`. Exit codes are today's: 0 done, 1 rejected, 2 usage, 3 error. The hub calls are in D3.

### Database / Storage Schema

Migration 015 as in D8. `tests/store/test_migration_015.py` covers an empty `adoption` table and a schema-14 fixture's row counts unchanged.

## Integration Points

### Provides to Other Slices

- **One mode.** 265 migrates one store and changes one code path.
- **A hub that holds the PM's data,** which 300's runner and timers build on.
- **`joined_home`,** the fixture every later test of an operation uses.
- **`update_live.py`,** which every later migration rides on at release. 265's is the first: an ordinary migration on the hub, run by `hub-update.sh` at that release.

### Consumes from Other Slices

260 to 263, as listed under Interfaces Required. If the hub cannot be reached, `adopt` changes nothing that matters and is run again.

## Success Criteria

### Functional Requirements

- A fixture laptop store at schema 10, with members, questions, requests, standing answers and wakes, is adopted. Every table's count on the hub equals the laptop's, and `list` from the laptop shows the same records as the store held.
- The laptop's machine on the hub has the name in the join line, and its checkouts, sessions, questions and wakes belong to it. A second machine invited before the adoption still joins with its line afterwards.
- Adoption is refused as `hub_not_empty`, with the tables and counts, when the hub holds a member. Nothing on the laptop is marked.
- Adoption goes through with a local session row live. Its `sessions_to_restart` names each live session and says which must be restarted. A program at schema 14 that opens the store after the migration is refused.
- A store set aside by `join`, with a client file for the same hub, is rejected by `adopt`, which names `amoeba leave` and then `--again`, and nothing is renamed. `adopt --again` is rejected there too and names `amoeba leave`. After `leave`, `adopt --again` adopts the store into an empty hub.
- No store is created or written by mistake. `adopt`, `adopt --again`, `discard-local` and `join --set-aside-local`, each run in a home with no store, with and without a client file, leave no file at the store path. `adopt` run again and `discard-local` without `--force`, on a joined machine with a handed-over store, open it read-only.
- `adopt` with no local `config.yaml`, and with a backup directory that cannot be written, each stop with exit 3 before the store is migrated and leave no partial backup. The naming fix calls `cf` with no write lock held, and no `cf` call is made once the lock is taken.
- A connection opened before the adoption fails its next write with `LocalStoreClosedError` naming the hub, and the store's counts do not change. `handle-pause` from this release, run during the adoption, fails with `NotJoinedError` and opens no store.
- Adoption cut off after the load, after the config and after the mark is finished by the same command, and the hub holds one copy of the data. A row written to the local store between two attempts, and a row changed there with no count changed, are each on the hub afterwards.
- With the hub changed and the laptop changed between two attempts, adoption is refused as `both_changed` and neither store is changed. The same holds when the hub's change is to a row and no count.
- Adoption cut off after the client file is finished by the same command: the laptop's `config.yaml` is renamed. A marked store whose hub answers `empty` is rejected naming `--again`.
- The pre-handover backup, taken while the store has a `-wal` file with committed rows, holds those rows. `join --set-aside-local` takes one too.
- An upload cut off partway, and one that sends nothing for `UPLOAD_IDLE_SECONDS`, each leave no file on the hub and the hub's store as it was. A full disk is refused as `hub_error` with the store as it was. A tick during a slow upload is answered inside 2 seconds. An attempt still sending after `ADOPT_UPLOAD_SECONDS` (set small by the test) is stopped by the client, and `adopt` fails with the store's size and the time allowed, with the lock released and nothing marked. Each upload refusal is a line in the hub's log.
- An upload with a wrong SHA-256 or a wrong count is refused as `copy_damaged`, and the hub's store is as it was. A call from another machine during a load is refused and nothing of it is stored. A `hub rm-machine` during a load is refused, and a hub started with a `loading` mark clears it.
- A writing call repeated with its call id after a second load returns its first result and applies once. An upload repeated after a load answers `loaded` and loads nothing.
- A write made to the store after the switch is reported as `changed_after_handover` by `adopt` and by `discard-local`, which then deletes nothing without `--force`.
- `discard-local` deletes the backups, `config.yaml.moved-to-hub` and the store when the machine is joined and the hub holds the adoption. It refuses an unmarked store with or without `--force`. Without `--force` it refuses a set-aside store, a machine that is not joined and a hub that does not hold the adoption, and says which. With `--force` it deletes in each of those cases and makes no hub call, so a store is discarded after `leave`. Cut off after the backups are deleted, it finishes when run again.
- `join` and `adopt` are rejected, naming the file, when a store exists at the pre-228 path.
- The hub with no `config.yaml` gets the laptop's; a hub that has a different one keeps it and the result says `kept`; the same call again says `same`. The laptop's file is renamed.
- `adopt --again` after `leave` adopts the same store into a second empty hub.
- Moving: after `hub backup`, a hub started with `--from-backup` on another state directory and port serves both clients after `join --address`, and `list` shows the same.
- With no client file, every CLI command but `join`, `adopt`, `leave`, `discard-local` and `hub`, and every MCP tool, fails with `NotJoinedError`, and no file is created. `amoeba-mcp` starts, and serves from its next call once the machine joins.
- `join` refuses beside an unmarked store and names both commands. `join --set-aside-local` leaves the store at its path, at schema 15, marked. `leave` deletes only the client file, the certificate and a left-over copy.
- A fresh hub with `config.yaml` written from the example serves a new machine's `add` and `send`.
- A bad edit to the hub's `config.yaml` fails `send` with the file and key named, and the fixed file is used by the next call with no restart.
- `update_live.py update` with fake hub commands: updates the hub before the client; a hub that never reports the new version runs the restore command and leaves the laptop alone; a failed read-back reinstalls the previous commit and does not run it; a hub command that outlasts its time limit is stopped and counts as failed. A missing `live-update.yaml` key stops it before anything runs.
- `update_live.py update` in a home with a local store and no client file, with fake hub commands and a fixture hub: it gets a join line, adopts, writes `previous-commit` beside the backup and prints the backup's path, the counts and the sessions to restart. An `adopt` that fails, and a read-back that differs, each end with the store and `config.yaml` as they were before the migration, no client file, and the previous commit installed. A failed hub command leaves the home untouched and runs no restore command.
- `update_live.py restore --local-store` after a finished adoption puts the pre-migration store and the config back, removes the client file and installs the commit in `previous-commit`. With no pre-handover backup it changes nothing and says so.
- `hub add-config-keys` adds a missing required key with the value from the shipped `config.yaml.example` and keeps a copy of the file in the state directory. With nothing missing, with the key already there, or with no `config.yaml`, it writes nothing. A write that fails partway leaves the old file whole. The shipped example loads as a valid config and equals the contract's block.
- The rehearsal: a copy of the PM's live store is adopted into a hub in Docker on the laptop, and `list` in that home shows the programs, members, open questions and requests the installed release shows for the live store. The live store is not written.

### Technical Requirements

- `ruff`, `pyright` strict and the full `pytest` run pass.
- The import rules in Component Structure are tested, and no test or source file names a deleted module or function.
- The door load test passes its bounds.
- `docs/hub-setup.md` exists, the five contract documents are updated, `tests/test_contract_docs.py` passes, and `260-arch.the-hub.md` holds the amendments in D12.
- The three shell scripts are run against a hub in Docker on the laptop: a first `hub-update.sh` that writes `hub.yaml` and the compose file from the examples, `hub-invite.sh`, an update to a second commit that leaves no older `config.yaml.before-keys`, `hub-restore.sh` stopped partway and run again, and `--empty`, `--put-back` and `--discard` each run once. `--empty` is run on a hub whose `backup_dir` holds a backup, and the emptied hub starts. The output is in the slice notes.

### Integration Requirements

- 265 can add a migration that runs on the hub alone.
- The release skill's last step updates the PM's hub and laptop with one command, and on its first run that command adopts the laptop's store.

### Verification Walkthrough

These are the slice's commands and test files as they will be named. The fixture tests are the demonstration of every criterion but the rehearsal:

```bash
uv run pytest tests/hub/test_adopt.py tests/hub/test_adopt_rerun.py tests/hub/test_adoption_load.py
uv run pytest tests/hub/test_move.py tests/hub/test_not_joined.py tests/scripts/test_update_live.py
uv run pytest
```

By hand, with a hub in Docker on one computer and a throwaway laptop home:

```bash
docker/hub-update.sh "$(git rev-parse HEAD)"            # first run: writes hub.yaml and the compose file, starts the hub
docker/hub-invite.sh laptop                             # prints a join line

export AMOEBA_HOME=/tmp/laptop-home                     # holds a seeded local store
amoeba list                                             # not joined; names adopt
amoeba adopt <line> -j                                  # outcome: adopted, with counts (no session was open)
amoeba list                                             # the seeded members and questions
amoeba adopt <line> -j                                  # outcome: already_adopted
ls $AMOEBA_HOME                                         # client.yaml, config.yaml.moved-to-hub
ls $AMOEBA_HOME/backups                                 # pre-handover-<stamp>
amoeba discard-local -j                                 # deletes the store, the backup, the old config
```

The rehearsal (D12) is the same walk with the throwaway home holding a copy of the live store, and its output is in the slice notes.

The release path is shown by `tests/scripts/test_update_live.py`, which runs `update` and `restore` with fake hub and install commands. `update` is not run by hand in the slice, because it installs over the PM's installed release. The PM's own store is adopted when the release runs it (D12).

## Risk Assessment

### Technical Risks

- **The PM's live store is moved** by this slice's code at its release, and the code that ran it locally is deleted in the same slice.
- **The load replaces a store that is being served.**
- **Hundreds of tests change how they reach the store.**

### Mitigation Strategies

- The laptop's store is never renamed, is deleted only by `discard-local`, and a copy is taken before the first write. Both ways back are commands in D11, and the release runs one of them by itself when the adoption fails. The live store is adopted only at the release, by reviewed and merged code, after the rehearsal on a copy of it.
- The backup call's behavior was tried before design and is pinned by a test with a writer and a reader open during the load (D4).
- The moved tests reach the store through the real door, over TLS, with their assertions unchanged.

## Implementation Notes

### Development Approach

1. Migration 015, `store.adoption` and `store.handover`.
2. The hub's side: the check, the load with its mark, the config write.
3. `adopt` on the laptop, with the cuts and the re-run rules.
4. `joined_home`, and the suite moved onto it.
5. The deletions in D7, one consumer group at a time, then the import rules.
6. `join`, `leave` and `discard-local` (D5), `NotJoinedError` (D6).
7. The release: `add-config-keys`, the three scripts, `update_live.py` with its first-run path and `restore --local-store`, the skill.
8. The documents.
9. The rehearsal on a copy of the live store (D12).

### Special Considerations

- **Security.** The upload is the whole store. It goes over the pinned connection, the token is checked before the body is read, and both copies are mode `0600` and deleted when the call ends. The config text holds no secret today; the same rule applies if it ever does.
- **The live store is designated** for the migration `adopt` runs and for the config rename. The pre-handover backup is taken first, and `update_live.py restore --local-store` is the restore path (D11). No task in the slice writes to the live store: the rehearsal reads it to take a copy, and the release adopts it. `discard-local` is run by the PM.
- **The hub's `PATH`** still holds no `cf`, `sq` or `git`. The naming fix calls `cf` on the laptop only.

## Operator Walkthrough

Done as the PM running it, from a laptop with a local store to a laptop that is a client, with every way it can be cut off and every way back.

**Getting there**

- **Start.** The release runs `update_live.py update` on the laptop. It sets the hub up on the LAN machine or updates it, gets a join line, installs the release and runs `amoeba adopt <line>`. It prints the counts, the backup's path, whether the hub took the config, and the sessions to restart. By hand it is the same three commands: `hub-update.sh`, `hub-invite.sh laptop`, `amoeba adopt <line>`.
- **`live-update.yaml` is missing, or lacks a key, or the hub machine has no clone.** `update` stops and names it. Nothing has changed, and the laptop is still on the previous release and its local store.
- **The hub's set-up or start fails.** `update` stops with the hub command's output. The laptop has not been touched. Run `update` again.
- **Sessions were open on the laptop.** `adopt` goes through. Nothing has to be closed: the migration has already stopped them from writing. A session on this release's door version uses the hub from its next tick; each older one is named in `sessions_to_restart`, which `update` prints, and its tools fail until it is restarted.
- **The adoption fails at the release for any other reason.** `update` puts the laptop back by itself: the previous release, and the store and config as they were before the migration. Fix the cause and run `update` again. If the hub had already loaded the store, that `update` is refused as `hub_not_empty`, and `hub-restore.sh --empty` on the hub machine is the way on.
- **The local `config.yaml` is missing or does not load.** Exit 3 before anything is written, with the file and key named. Fix it, or write it from `config.yaml.example`, and run again.
- **The laptop's disk is full, or the backup directory cannot be written.** Exit 3 with the path. The partial backup or copy is deleted and the lock released. Free space and run again.
- **Another machine has a session open on the hub.** It does not make the hub count as not empty.
- **The machine has a store from before 228 under `~/.config`.** `join` and `adopt` are rejected naming it, with the release to install to move it.
- **The hub is not empty.** Refused with what it holds. Dead end for one store. Keep the hub's with `join --set-aside-local`, and the laptop's records are on no hub. Or keep the laptop's with `hub-restore.sh --empty`, which sets the hub's records aside in `replaced-<stamp>/` and means a new invite and `join` for every machine.
- **The hub cannot be reached, or a reply is lost.** The error names the address. Run the same command again; it loads only if the hub does not already hold the data.
- **`cf` fails while the members are named.** Exit 3 before anything is sent. Run it again.
- **The upload stalls or the connection drops.** The hub deletes what it received. The laptop retries, then fails naming the address. Run it again.
- **The upload is too slow to finish.** Each attempt is stopped after 120 seconds, and `adopt` fails with the store's size and the time allowed. The lock is released and nothing is marked. A faster connection to the hub, or `join --set-aside-local`.
- **The hub's disk fills during the upload or the load.** Refused with the operating system's message, and the hub's store is as it was. Free space and run it again.
- **`hub rm-machine` or `hub invite` is run during a load.** It fails saying an adoption is loading. Run it again; the load takes under a second.
- **The hub crashes during a load.** It clears the loading mark when it starts. Run `adopt` again.
- **A pause hook fires on the laptop during the adoption.** It fails with the join message. Its run shows on `list` afterwards as a paused run with no record, with the command to handle it.

**Cut off partway**

- **The command is killed after the hub loaded.** No client file, so commands say to join or adopt. Run `adopt` again; it skips the load and finishes. If the join line is gone, `hub-invite.sh laptop` gives a new one, and `adopt` finishes with it.
- **Another machine wrote to the hub between two attempts and the laptop's store also changed.** Refused as `both_changed`. The same dead end as a hub that is not empty, and the same two ways on.
- **The store is marked for a hub that has since been emptied or replaced.** Rejected, saying the hub no longer holds this adoption. `adopt <line> --again` adopts the store into it.
- **The command is killed after the client file is written.** The machine is joined. Run `adopt` again and it renames the old `config.yaml`.
- **An older command was still running on the laptop and wrote to the store after the switch.** From 260 on it fails naming the hub. Before 260 its write succeeds and is not on the hub. `adopt` run again and `discard-local` report it, and `discard-local` will not delete the store without `--force`. For a `handle-pause`, the hub starts that question again by itself.
- **`update` itself is killed during the adoption.** Run it again: it gets a new join line and `adopt` goes on from where it stopped. Or `restore --local-store` goes back.

**Set aside, not adopted**

- **`join --set-aside-local`.** The store stays at its path, marked, with a backup. Its records are on no hub.
- **Adopting that store later.** `adopt` is rejected and says how: `amoeba leave`, then `adopt <line> --again` into an empty hub.
- **`join --set-aside-local` with no store.** It joins and says no store was there. No file is created.

**As a client**

- **A fresh hub, nothing to adopt.** `hub-update.sh` writes `hub.yaml` from the example and starts the hub. Write `config.yaml` from its example, then `hub-invite.sh`, `join`, and `amoeba add` in each repo.
- **A machine that is not joined.** Every command says to run `amoeba join`. An open session's tools say the same and work once it has joined.
- **Changing a setting.** Edit `config.yaml` on the hub. The laptop's old file is named `config.yaml.moved-to-hub`, so it is not edited by mistake.
- **A release.** `update_live.py update` updates the hub, then the laptop, and lists the machines and sessions behind.
- **The hub's update fails.** The hub is put back, with its config as it was before this update's keys, and the script prints where the failed release's store is kept. `hub-restore.sh --put-back` brings it back under a fixed release and `--discard` deletes it.
- **The laptop's update fails.** The laptop is put back to the previous commit and the hub is left serving. If that release changed the door version, the laptop's commands refuse with the upgrade command until `update` is run with a fixed release, or `restore --hub` puts the hub back too. The script says which.
- **The hub's update command hangs.** It is stopped after 15 minutes and the hub is put back.
- **`hub-restore.sh` stops partway.** The hub is down and the script said which step failed. Run it again; it goes on from where it stopped.
- **Moving the hub.** `hub backup`, `serve --from-backup` on the new machine, `join --address` on each client.

**Going back, and clearing up**

- **Leaving.** `amoeba leave` unjoins the machine and changes no store. The handed-over store stays, and every command says to join. From there: `join` with a new line joins again; `adopt --again` adopts the store into an empty hub; `discard-local --force` deletes it with no hub.
- **Undo, keeping the hub.** `leave`, `hub-restore.sh --empty`, `hub-invite.sh`, `adopt <line> --again`. What the hub recorded since the adoption is set aside in `replaced-<stamp>/`.
- **Undo, back to the local store.** `update_live.py restore --local-store`. What the hub recorded since the adoption is not on the laptop.
- **Clearing up.** `amoeba discard-local`, once the old sessions are restarted, deletes the backups, the old config and the handed-over store, after the hub confirms it holds the adoption. It prints each path first. Afterwards neither undo is possible, and it says so.
- **`discard-local` is cut off.** The store is deleted last, so run it again and it finishes.
- **An older program makes an empty store at the path after `discard-local`.** `discard-local` refuses it because it has no mark, and names the way: `leave`, `join <line> --set-aside-local`, then `discard-local --force`. Restarting the sessions `adopt` listed before clearing up avoids it.
- **Sets of hub files that were set aside.** Each `replaced-<stamp>/` ends with `hub-restore.sh --put-back` or `--discard`.

**Dead ends found.** One remains, and it is stated in every refusal that meets it: two stores are never merged. When the hub is not empty, or both sides changed between two attempts, one store's records are served and the other's are not. The refusal names the command that keeps each, and neither store is deleted by either choice.

Nine were found in this walk and closed in the design:

1. A set-aside store on a joined machine was told to run `--again`, which is rejected there. The message now names `amoeba leave` first (D1).
2. `discard-local` could not run after `leave`. It runs without a client file, with `--force` (D5, D6).
3. `discard-local` cut off after the store was deleted left backups with no command to remove them. The store is deleted last (D5).
4. A count mismatch after the load had one way on, emptying the hub. The check is removed, because the counts are checked on the file before it is copied (D4).
5. "Start the hub on an empty state directory" was the exit of four refusals and was not a command. `hub-restore.sh --empty` is, and it keeps what the hub held (D10).
6. A slow upload had no end and held the laptop's lock. One attempt is limited to `ADOPT_UPLOAD_SECONDS` (D3).
7. The PM's install needed the hub machine's name inside a task, and a review fix after it meant adopting again. The release adopts, after review, and puts the laptop back by itself on failure (D10, D12).
8. The way back to the local store was four steps by hand. It is `restore --local-store` (D11).
9. `hub-restore.sh` put back a `config.yaml.before-keys` from an earlier update, losing every config edit since. `hub-update.sh` deletes the old one first (D10).
