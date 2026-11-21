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
- For the release, not for any task: a LAN machine the laptop reaches by `ssh`, with Docker and a clone of this repo, and `live-update.yaml` in the laptop's config directory naming the three hub commands and the address the laptop reaches the hub at (D10). The machine's `ssh` name is not in any project document (checked 20261120: the concept, the initiative plan, the architecture, the notes). Every task in the slice runs on fixtures and on a hub in Docker on the laptop, and needs neither. If the file is missing when the release runs, `update` stops before it changes anything and names it (D10), and the laptop stays on the previous release and its local store.
- No new package.

### Interfaces Required

- 260: the join line, the certificate fetch and `hello` of `join` (D4), `client.call`, `handle_call`, the closed mark, `open_hub_store`, which never creates a store (D12), the hub-home check (D1, D2), backups and `serve --from-backup` with its `restore.partial/` and `replaced-<UTC stamp>/` (D14, D17), the in-process hub helper and `tests/hub_fixture.py`.
- 261: `operations.naming.name_members`, which names the members of a local store.
- 262: `Steps` and `DoorSteps`; the fix that gives old question and wake rows the `local` machine (262 D14).
- 263: `mcp.tick`, which already runs on `Steps`; the heartbeat test inside `LIVE_SESSION` in `store/sql_sessions.py`, which this slice names `FRESH_HEARTBEAT` (D2), and the session row's `door_version` (263 D13).
- `scripts/update_live.py` and `.claude/skills/release/SKILL.md` as they are today.

## Architecture

### Component Structure

| Package | Modules | Change |
|---|---|---|
| `amoeba.store` | `schema/015_adoption.sql`, `adoption`, `handover` (new) | The `adoption` row. `STORE_TABLES`, the one list of table names, with the row counts and the content digest built from it (D1, D3). Backing up and opening a local store for a handover, marking it handed over, and deleting it, under the handover lock. It never creates a store and refuses in a hub home (D5). `handover` is one of the two modules that call `Store.open`. |
| | `relocate` | 228's copy and verify functions are deleted. 260's set-aside copy and put-back are deleted (D5). |
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
2. **Ask the hub.** `adopt_check` carries the laptop's adoption id, if it has one, and the schema version this program migrates to. The hub answers `empty` or `holds_this`, or refuses (D3). This is the early refusal, made before the live store is migrated. The id and the mark are read on a read-only connection, and a missing table means none: a store below schema 15 has no `adoption` table and so no id, and one below schema 11 has no `closed_mark` table and so no mark. With no `adoption` row, the id is the one `restore --local-store` kept, if there is one (D11).
3. **Back up.** Read the local `config.yaml`. Each required top-level key it lacks is added to the text in memory, with the value from `config.yaml.example`, by the function behind `hub add-config-keys` (D10). The file on the laptop is not changed, so the previous release still loads it. The completed text is loaded with the config loader, and it is the text step 7 sends. A file that is missing, or a text that does not load, stops `adopt` here, before anything is written. Then `store.handover` backs the store up before it writes anything (D5), and `adopt` copies `config.yaml` beside that backup.
4. **Open.** Open the local store, which migrates it, and run the three one-time fixes (D2). Refuse if a member is unnamed, and list the sessions to restart (D2). Write the adoption id if the store has none, and commit: the kept one when there is one, and then the kept file is deleted, or else a new one.
5. **Lock, count, copy.** Take the store's write lock on one connection and hold it. Count the rows of every table outside `HUB_OWN_TABLES` (D3). On a second, read-only connection, copy the store with SQLite's backup call to `<state home>/adoption-copy.sqlite3`, and work out the copy's content digest (D1). Tried on 20261120 with Python 3.13.7 and SQLite 3.50.4: the second connection copies every committed row while the first holds the lock, and a backup from the lock-holding connection itself does not return. A test pins the first.
6. **Load.** Call `adopt_check` again, now with the digest, and the hub says whether to load (D1). If so, upload the copy with its SHA-256 and the counts. The hub prepares it and makes it the hub's store (D4).
7. **Config.** `adopt_config` sends the text of the local `config.yaml` as step 3 completed it. The hub validates it and writes it, or keeps the one it has and says so (D3).
8. **Switch.** In the transaction that holds the lock, write the closed mark naming the hub and the copy's digest as `handed_digest`, and commit. That one commit sets the mark and releases the lock. Then write the client file, rename the local `config.yaml` to `config.yaml.moved-to-hub`, delete the copy, and print the result.

A failure at any step before 8 rolls the lock's transaction back and deletes the copy. Nothing on the laptop has changed except the backup, the migration, the adoption id and the saved certificate, and the same command is run again. The migration is not undone: from step 4 on, an older program still running on the laptop is refused by the store's schema (D2).

That covers the laptop's own files too. A backup or a copy that cannot be written whole (a full disk, a directory that cannot be written) is deleted, and `adopt` stops with the path and the operating system's message. The copy is a store in WAL mode, so "the copy" here and below means the file and the two side files SQLite makes beside it when it is opened. One `adopt` runs at a time on a machine (the handover lock, D5), so a run only ever deletes a copy it made. A failure after the mark's commit, when the client file or the rename cannot be written, leaves row 5 or row 4 of D1, and the same command finishes it.

**How long the lock is held.** Steps 6 and 7 are three hub calls made under the local store's write lock, and each has a longest time. `adopt_check` and `adopt_config` take at most 43 seconds each (260's `CALL_BOUND_SECONDS`: the retry time of 30, the connect time of 3 and the read time of 10). The upload takes at most 153: the retry time of 30, the connect time of 3 and `ADOPT_UPLOAD_SECONDS`, 120, which is the longest one whole attempt may take, sending and waiting together (D3). So the hub calls hold the lock for at most 43 + 153 + 43 = 239 seconds. The count, the copy and the digest in step 5 are local work, well under a second for a store the size of the PM's. The only program that can be waiting is a command of an older release that was already running (D2). It waits the store's busy time of 5 seconds and then fails with `StoreBusyError`, exit 3, as on any busy store today.

### State Management

| State | Where | Ends by |
|---|---|---|
| The adoption id | `adoption`, one row, in the local store and then in the hub's | Never on the hub; it says where the store came from. On the laptop, `adopt --again` replaces it |
| A local store that is handed over | The store path, at the schema of the release that handed it over, with the closed mark | `amoeba discard-local` deletes it (D5). `adopt --again` adopts it into another hub. `update_live.py restore --local-store` puts the backup back over it (D11) |
| The pre-handover backup | `<state home>/backups/pre-handover-<stamp>/`: the store, `config.yaml`, and `previous-commit` when the release made it. Written as `.partial-pre-handover-<stamp>/` and renamed when whole | One is kept: a new one, once whole, deletes the older ones and any partial one (D5). `amoeba discard-local` deletes every one |
| The handover lock | `<state home>/handover.lock`, one empty file | Kept. The lock on it ends with the process that holds it (D5) |
| The release script's lock | `<state home>/update.lock`, one empty file | Kept. The lock on it ends with the `update` or `restore` that holds it (D10) |
| A kept adoption id | `<state home>/kept-adoption-id` | Used and deleted by the next `adopt` that runs the full flow. Overwritten by the next `restore --local-store`. Deleted by `adopt --again`, `join --set-aside-local` and `discard-local` (D5, D11) |
| The release's adoption record | `<state home>/backups/adoption-run.json`: what `list -j` showed and the installed commit, before the adoption | Deleted by the `update` that finishes the adoption, by an `update` that fails before `adopt` runs, and by `restore --local-store`. One left by a kill is ended by the next `update` (D10) |
| The script's two commit files | `<state home>/backups/installed-commit` and `backups/previous-commit`, one line each | Each is overwritten by the next `update` that writes it. The adoption run deletes `previous-commit` when it finishes (D10). `restore --local-store` writes `installed-commit` and deletes `previous-commit` (D11) |
| The backup the earlier release script kept | `<state home>/backups/<stamp>/` | Deleted by the first `update` of this release that succeeds (D10) |
| The copy being sent | `<state home>/adoption-copy.sqlite3`, mode `0600` | Deleted when `adopt` ends, however it ends. One left by a crash is overwritten by the next `adopt` and deleted by `leave` |
| The upload on the hub | `<hub state>/adoption-upload.sqlite3` | Deleted when the upload or the load ends, however it ends, and at every hub start |
| The loading mark | The hub store's `closed_mark`, reason `loading` | Gone with the copy that replaces the store. Cleared when a load fails, and at hub start |
| A saved certificate with no client file | Client state directory (260 D1), after a failed `adopt` | Overwritten by the next `adopt` or `join`; deleted by `leave` |
| `config.yaml.moved-to-hub` | Client config directory | `adopt --again` renames it back. `restore --local-store` puts the backup's `config.yaml` back and deletes it. `discard-local` deletes it |
| The store a failed hub update set aside, the store and backups `hub-restore.sh --empty` set aside, or the files 260's own `serve --from-backup` moved away (260 D14) | `<hub state>/replaced-<UTC stamp>/` | `hub-restore.sh --put-back` or `--discard` (D10) |
| `config.yaml.before-keys` and `pre-update-backups`, the names of the pre-migration backups that existed before the update | Hub state directory | The first is moved back by `hub-restore.sh`, and the second deleted by it once the restore is done. Both are deleted by the next `hub-update.sh` to another commit, once it has finished a restore that was cut off, and by `hub-restore.sh --empty`. `--put-back` deletes the second |

## Technical Decisions

### D1 — What `adopt` refuses, and running it again
Status: decided

`adopt` looks at three things on the laptop: the client file, the closed mark and the adoption id.

The rows are tried in order and the first that matches decides:

| | The laptop has | `adopt <line>` does |
|---|---|---|
| 1 | No store at the store path | Rejected: nothing to adopt; names `amoeba join`. When a store set aside by a release from 260 to 263 is there (`amoeba.sqlite3.set-aside-<stamp>`, D5), it names that file and the two ways on |
| 2 | A mark and no adoption id (a store set aside by `join`), with or without a client file | Rejected. Says the store was set aside, not adopted, and names `--again`. When a client file exists it names `amoeba leave` first, then `--again` |
| 3 | A mark for another hub | Rejected. Names the hub in the mark and `--again`, with `amoeba leave` first when a client file exists |
| 4 | A mark for this line's hub, an adoption id, and a client file | After step 1's `hello`, writes the client file again from this line, as `join` does on a joined machine (260 D4), so a line from a new invite brings its new token. Then finishes what step 8 left: the `config.yaml` rename and the copy's deletion. Then prints the result again |
| 5 | A mark for this line's hub, no client file | A switch that was cut off. When `adopt_check` answers `holds_this`: steps 7 and 8 without the mark write. When it answers `empty` or `hub_not_empty`, the hub at that address is no longer the one that was loaded: rejected, saying so and naming `--again` |
| 6 | No mark, and a client file | Rejected: the machine is joined; `amoeba leave` first |
| 7 | No mark, no client file | The full flow in Data Flow |

Rows 4 and 5 also work out the store's digest and compare it with `handed_digest`. They open the store read-only for that (D5). A difference means something wrote to the store after it was handed over (D2), and the result says so as `changed_after_handover`.

A store set aside by `join --set-aside-local` never has an adoption id, because that command deletes the adoption row when it writes the mark (D5). So a store that was set aside after an `adopt` failed is row 2, and is never reported as adopted by row 4.

"An adoption id" in the rows above is the store's own `adoption` row and nothing else. The id that `restore --local-store` kept in a file (D11) is not looked at to choose a row. It is used in one place, the full flow of row 7: `adopt_check` carries it and step 4 writes it into the store. `join --set-aside-local` deletes that file (D5), so a set-aside store never lies beside one.

`adopt <line> --again` first clears the mark and the adoption row, deletes a kept adoption id (D11), and renames `config.yaml.moved-to-hub` back when no `config.yaml` is there. Then it runs the full flow with a new id. Its backup follows D5's one test, as every hand-over command's does: a store at schema 15 or above gets none, because the backup taken before its first migration still holds every record in it, and a store below 15 (one `restore --local-store` put back) gets a new one (D5). It is the undo (D11) and the way to adopt a store that was set aside. It is rejected in two cases:

- A client file exists. The message names `amoeba leave`.
- The store has an adoption id and no mark. That is an adoption that was cut off before its switch, and `adopt <line>` without `--again` finishes it. A new id here would make the hub that already loaded it answer `hub_not_empty`. The message names `adopt <line>`.

Rejected is exit 1, and a rejection's result carries a `code`. A hub that cannot be reached, a `cf` failure in the naming fix, a local `config.yaml` that is missing or does not load, a file the laptop cannot write, a home that is a hub's (D5) and another hand-over command already running (`HandoverBusyError`, D5) are operational errors, exit 3. In every case the lock is released and the same command is run again. For a missing `config.yaml`, the message gives the path of `config.yaml.example` (D10) and the command that copies it to the config directory. `adopt` writes no local config itself.

Running it again after a lost reply or a failed switch follows the architecture's rule, with one case added:

| `adopt_check` finds | Then |
|---|---|
| The hub is empty (D3) | Load |
| The hub holds this adoption, and the laptop's digest equals the digest the hub loaded | Skip the load |
| The hub holds this adoption, the laptop's digest differs, and the hub's own digest still equals what it loaded | Load again, in place of the first |
| The hub holds this adoption, the laptop's digest differs, and the hub's has moved too | Refused as `both_changed` |
| Anything else | Refused as `hub_not_empty`, with each table that has rows and its count |

**The content digest** is what says a store changed. Row counts cannot: a recorded answer or a withdrawn standing answer changes a row and no count. `store.adoption.content_digest` is the SHA-256 of every row of every table outside `HUB_OWN_TABLES` (D3), read in the order of `STORE_TABLES` and, inside a table, by its primary key (`rowid` for a table that declares none). The laptop works it out from its copy, and the hub from the prepared upload (kept as `loaded_digest`) and from its own store when asked. Row counts stay as the check on the load itself (D4).

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

An open session's row can only go stale, and the `sessions` table is not carried to the hub (D4). After the migration `adopt` reads the live rows. Live is a fresh heartbeat and nothing more: `FRESH_HEARTBEAT`, a constant this slice adds to `store/sql_sessions.py` holding the heartbeat test that 263's `LIVE_SESSION` already contains. `LIVE_SESSION` is then composed from it and the door-version test, so the heartbeat rule is still written once. `adopt` cannot use `LIVE_SESSION` itself, because that leaves out a row with no door version (263 D13), and those are the sessions that must be restarted. It is judged with `session_stale_seconds` from the local `config.yaml` and the laptop's clock, since the rows are the laptop's own. The result carries them as `sessions_to_restart`, each with what happens next: one whose row has this release's `DOOR_VERSION` uses the hub from its next tick once the machine is joined (263 D1); one with another version or none must be restarted. A row with none is a program from before 263. The release prints the list (D10). From the migration on, an older `amoeba-mcp` still running on the laptop has failing tools until it is restarted. An `adopt` that fails for another reason is put back with the pre-migration backup (D11).

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

**The tables.** `STORE_TABLES` in `store.adoption` is a module-level tuple that names every table of the store and marks the ones below that are not record tables. The emptiness check, the counts and the digest are all worked out from it, so their SQL is built from that constant alone. No table name is ever read from `sqlite_master` or from a request and put into SQL (the repo's rule that SQL composes from constants only). A test asserts the tuple holds exactly the tables of a freshly migrated store. So a table added by a later migration fails that test until it is listed, and it is then checked and digested unless it is marked here. The `Amoeba-Row-Counts` header holds one count for each table in the tuple outside `HUB_OWN_TABLES`. A key that is not one of those names, or one of them missing, is refused as `malformed_call`; the header's names are only ever compared, never run.

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
   - delete every row of its `sessions`, `machine_runs` and `call_results`, which are the laptop's own and are not carried (D2, D3);
   - rename its `local` machine to the calling machine's name and give it that machine's token hash;
   - insert every other machine the hub has, with a new id and the copy's owner;
   - insert the hub's kept call results under their machines' new ids (D1);
   - set `loaded_at` and `loaded_digest` on the `adoption` row.
4. Count the upload's rows and compare them with the header, for every table outside `HUB_OWN_TABLES` (D3). The six tables in `HUB_OWN_TABLES` are not compared, because step 3 has just changed them: it emptied three, and wrote the hub's machines and kept results into two. A difference is `copy_damaged` and stops here, so the hub's store has not been touched.
5. Copy the upload into the hub's store with the backup call, in one step. The prepared upload has no mark, so this also ends the loading mark. The destination is opened without creating it, as `open_hub_store` does (260 D12): a hub store that has gone missing is `HubStoreMissingError`, refused as `hub_error`, and no empty store is made for the copy to land in.
6. Answer `loaded` with step 4's counts. In a `finally`: clear the loading mark if step 5 was not reached, and delete the upload with its two side files. The clear is made on a plain connection, as 260 clears a mark in `leave` (260 D4), because a store write would be refused by the mark it is clearing.

Step 5 was tried on 20261120 with the project's Python 3.13.7 and SQLite 3.50.4, with the destination in WAL mode and other connections open on it. The copy lands as one transaction: a writer that arrived during it waited and then saw the new rows, a reader inside a transaction kept its old view until it ended, and the `AUTOINCREMENT` counters came with the copy. `tests/hub/test_adoption_load.py` pins this.

Nothing is compared after step 5, so `copy_damaged` always means the hub's store is as it was. The counts were checked in step 4 on the very file that step 5 copies, and the copy is one SQLite call that lands whole or not at all. A count of the hub's store after the copy could only fail with that store already replaced, with no way on but emptying the hub, so there is none. The test above asserts the counts and the digest of the hub's store after a load, and the release reads `list` back after the adoption (D10).

**The loading mark.** Between the read in step 2 and the copy in step 5, a write to the hub's store would be removed by the copy, or put back from the step-2 read. That includes a `hub rm-machine` or a re-invite, whose old token would work again. So step 2 sets 260's closed mark on the hub's store, with the reason `loading` (D8). Every write transaction checks the mark right after it takes the lock (260 D4), in the serving process and in an admin command alike, and fails saying an adoption is loading. A call is refused as `hub_error`; an admin command exits 3. Either is run again.

A hub that crashes between steps 2 and 5 leaves the mark set. `amoeba hub serve` clears a `loading` mark when it starts, the same way, since no load can be running then.

The load takes well under a second for a store the size of the PM's (160 KB on 20261120). A tick that arrives while the mark is set is refused at once, not held, and is a skipped tick (263 D4). `tests/hub/test_adoption_load.py` sends ticks during an upload whose body arrives slowly and during the load, and asserts each is answered inside the load test's 2 seconds. It also runs `hub rm-machine` between steps 2 and 5, and asserts it is refused and that the machine's token still works after the load, then ends when the command is run again.

- Rejected: `ATTACH` and `INSERT ... SELECT` per table. It keeps the hub's machine ids, but it has to list tables, order them for foreign keys and carry the sequence counters by hand.
- Rejected: replacing the store file. A call that had the old file open would write into it after the rename.

### D5 — `join` and `leave` once there is no local way
Status: decided

260 set a local store aside by marking it, copying it to `amoeba.sqlite3.set-aside-<UTC stamp>` and deleting the original, and `leave` put the copy back (260 D4). Both go, for one reason: a release before 260 that finds no file at the store path creates an empty store there and carries on. An older `amoeba-mcp` left running would then record its agent's messages into a store nobody reads.

So a store that is handed over, by `adopt` or by `join --set-aside-local`, stays at the store path, at the schema of the release that handed it over (15 here), with the closed mark. An older program that opens it is refused for the schema. It leaves that state by `adopt --again` or by `amoeba discard-local`. It is not migrated again by later releases while it lies there. The read-only open below makes no schema check, so a later release's `discard-local` and `adopt` still read its mark, id and digest; `adopt --again` opens it for writing, which migrates it to that release's schema like any other store.

**The backup.** `store.handover` backs a store up before it migrates it: with SQLite's backup call, into `<state home>/backups/pre-handover-<UTC stamp>/amoeba.sqlite3`. The rule is one test: the store's schema is below 15, the schema that adds the `adoption` table (`HANDOVER_SCHEMA_VERSION`, a constant in `store.handover`). That is a store no hand-over command has opened before. All of a store's pending migrations run in one transaction (`store/migrations.py`), so a store is either as the previous release left it or at schema 15, never between. So:

- A store the previous release can still use is always backed up before `adopt` or `--set-aside-local` changes it, however many times an earlier attempt ran.
- A store at schema 15 or above gets no second backup: not when `adopt` is run again after any failure, and not for `--again`. That holds in a later release too, whose `adopt` or `--again` migrates such a store past 15 with no new backup. The records are safe without one: a store at 15 or above has had no writer since the backup taken before its first migration (the next bullet), so that backup holds every record the migration could damage, and `restore --local-store` puts it back (D11). A second backup would replace it with a copy the previous release cannot open.
- The newest whole backup is always the store as it was just before the migration that closed it to the previous release. Nothing can write that store between the two, and nothing but `restore --local-store` takes it back below schema 15 (D11).

The backup is written under `.partial-pre-handover-<stamp>/` and renamed when whole, the pattern of 260's hub backups (260 D15). An attempt first deletes a partial directory left by a kill. Once the new one is whole it deletes every older `pre-handover-*` directory, so one is kept and the newest is the only one. Both commands print the path. The restore path is in D11.

**One hand-over command at a time.** `adopt`, `join --set-aside-local` and `discard-local` each hold an exclusive file lock on `<state home>/handover.lock` from their first read of the store to their end. A second one fails at once with `HandoverBusyError`, exit 3, saying another is running. The operating system releases the lock when its holder exits, however it exits, so a killed command never leaves it held.

`update_live.py restore --local-store` takes the same lock for the part of its run that reads and writes the store and the kept id (D11), and stops the same way when it is held. It has to: tried on 20261121, SQLite's backup call onto a store whose write lock another connection holds does not give up at the busy time. It waits for the lock and then replaces the store, which would be the moment after `adopt` committed the mark. `amoeba leave` takes the lock for one thing, deleting a left-over `adoption-copy.sqlite3`, and only if it is free: when another command holds it, `leave` skips that delete and says so, and does the rest. So a `leave` run during an `adopt` never deletes the copy that `adopt` is sending. `restore --local-store` runs `leave` while it holds the lock, and deletes a left-over copy itself.

**`store.handover` never creates a store.** 260's guard stopped a local store being opened, and so created, on a machine with a client file. The openers it guarded are deleted (D7), and `store.handover` is the one local opener left, so the rule moves into it. It tests that the file exists, then opens it with SQLite's `mode=rw`, or with `mode=ro` where the command only reads: the digest in rows 4 and 5 of D1 and in `discard-local`. On a joined machine `adopt` and `discard-local` therefore never write to the store. Tried on 20261120 with SQLite 3.50.4: both modes fail on a missing path and create no file, and a `mode=ro` connection reads the committed rows of a store in WAL mode and cannot write. With no store at the path, `adopt` is rejected (D1, row 1), `discard-local` is rejected saying there is nothing to discard, and `join --set-aside-local` joins and says no store was there.

**A hub home.** 260's local opener raises `HubHomeError` in a home whose config directory holds `hub.yaml`, so that a client command never writes a hub's store behind the door (260 D1, D2). That opener is deleted (D7), so the check moves into `store.handover` too: `adopt` and `discard-local` fail with `HubHomeError`, exit 3, before they read anything, and `join` keeps its own refusal (260 D4, step 0). A hub's store is therefore never marked, adopted or discarded.

- **`amoeba join <line>`** refuses when the store path holds a store with no mark, and names `amoeba adopt` and `--set-aside-local`. A marked store does not stop it.
- **`amoeba join <line> --set-aside-local`** opens the store through `store.handover`, which backs it up and migrates it, and in one transaction writes the mark and deletes the adoption row if there is one. It then deletes a kept adoption id (D11), so no id of an earlier adoption lies beside a set-aside store; run again after a kill between the two, it deletes the file then. The store's records stay there and are on no hub. Deleting the row is what makes a set-aside store one thing everywhere: D1's row 2, and `discard-local`'s "set aside and never adopted". Without it, a store set aside after a failed `adopt` would carry that attempt's id and be reported as adopted.
- **`amoeba discard-local`** ends the state, on a machine that is joined or not.
  - It deletes every `backups/pre-handover-*` directory and a partial one, then a kept adoption id, then `config.yaml.moved-to-hub`, then the handed-over store with its side files. The store goes last, so a run that was cut off still finds a marked store and finishes when run again. It prints each path before it deletes it.
  - It refuses a store with no mark, and names `amoeba adopt` and `join --set-aside-local`.
  - A store set aside by a release from 260 to 263 is a file named `amoeba.sqlite3.set-aside-<UTC stamp>` beside the store path (260 D4), and this release's `leave` does not put one back. `discard-local` treats it as a set-aside store: without `--force` it refuses, saying the store was set aside and never adopted, and with `--force` it deletes that file and a `.set-aside.partial` file beside it. To keep its records instead, `amoeba leave` run with the release that set it aside puts it back at the store path, and this release's `adopt` then adopts it. The PM's laptop has none, because it was never joined before this release.
  - Without `--force` it deletes only when it can show the records are on a hub: the machine is joined, `adopt_check` on that hub answers `holds_this` for the store's adoption id, and the store's digest is `handed_digest` (D2). Otherwise it refuses and says which of four things is the reason: the store was set aside and never adopted; the machine is not joined; the hub does not hold this adoption; the store changed after it was handed over.
  - `--force` deletes in each of those four cases and makes no hub call. So a store on a machine that has left its hub still has an exit.
  - It deletes the pre-migration backup, which both undo paths in D11 need. The output says that neither is possible afterwards, and that the hub's own backups are then the only copies.
  - It is the PM's command: nothing in this slice or in the release runs it. An older program still running on the machine would create an empty store at the path afterwards (the reason above), so the command's output says to restart the sessions `adopt` listed first.
- **`amoeba leave`** deletes the client file, the saved certificate and a left-over `adoption-copy.sqlite3` (the copy only when no hand-over command is running, above). It no longer touches a store. When the store path holds one, it prints the path and says nothing reads it.

### D6 — With no client file
Status: decided

`wiring_door.joined()` returns the client file or raises `NotJoinedError`, an operational error (exit 3; an error result on MCP). The text: this machine is not joined to a hub; run `amoeba join <line>` with a line from `amoeba hub invite <machine>` on the hub. When a file exists at the store path it adds that `amoeba adopt <line>` moves that store to an empty hub. That is a file-exists test; the store is not opened.

| Entry point | With no client file |
|---|---|
| `wiring.invoke`, any operation | `NotJoinedError` |
| `amoeba handle-pause`, `wake-run`, `resume-run` | `NotJoinedError`, before anything local is read. No calls-log line |
| `amoeba-mcp` start | Starts, with one WARNING on stderr. Its tools return `NotJoinedError` and its ticks are skipped (263 D4). A machine that joins later is served from the session's next call, with no restart |
| `amoeba hub ...` | Unchanged: these never read the client file, except to refuse in a home that has one (260 D2) |
| `amoeba join`, `adopt`, `leave`, `discard-local` | Run. `discard-local` then needs `--force` (D5). In a hub home `join`, `adopt` and `discard-local` are refused (D5) |

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
| 260's guard in the two store openers and `prepare_state_home` | The local opener and `prepare_state_home` are deleted with it. `store.handover`, the one local opener left, never creates a store and only reads one for a joined machine's `adopt` and `discard-local` (D5). Hub commands keep their refusal. The local opener's `HubHomeError` check moves into `store.handover` (D5) |
| 260's set-aside copy (`set-aside-<stamp>`, its `.partial` file and the `displaced-` name) and `leave`'s put-back | D5 |

A machine whose store is still under `~/.config/amoeba` from before 228 is not moved any more, and is not passed over without a word. `join` and `adopt` test whether a file exists at the old store path: the store's file name under the directory `legacy_state_home` returns, which stays for this. That function returns nothing when `AMOEBA_HOME` is set, and then there is no old path to test. If a file is there they are rejected, naming the file and saying to install the release before this one and run any command once, which moves it. The PM's laptop has none: on 20261120 its `~/.config/amoeba` holds `config.yaml` and nothing else. The test stays because Amoeba is published on PyPI, so an install that is not the PM's can still have one. `adopt` deletes the empty `.state-move.lock` file the move left in the state home.

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

Adoption's own tests are in `tests/hub/test_adopt*.py`, on a fixture laptop home whose store is at schema 10, so the migrations and the three fixes run. The seed helpers in `tests/store/seed.py` write through the store's current functions, so they cannot make an old store. The fixture is built the way the migration tests build one (`_migrate_to` in `tests/store/test_migration_010.py`): it runs the first ten migration files with `migration_files` and `EXPECTED_SCHEMA_VERSION` patched, then inserts its rows with SQL written for schema 10, one or more in every table, and writes the file to the fixture home. A cut is made with a hook on `adopt_local` (`AdoptHooks`, the pattern of 260's `DoorHooks`): after the load, after the config, and after the mark.

The door load test (260 D18, as widened by 261 to 263) runs unchanged, and its bounds still hold: every call inside 2 seconds with 16 clients, a median under 200 ms on an idle hub. Adoption adds no call to the steady state.

### D10 — The release
Status: decided

The live install is updated by `scripts/update_live.py update`, as the last step of a release and at no other time.

**One run at a time.** `update` and `restore`, with any flag, hold an exclusive file lock on `<state home>/update.lock` from their first step to their last. A second one exits 1 at once, saying another is running, and has changed nothing. The operating system releases the lock when its holder exits, so a killed run never leaves it held. It is a different file from the handover lock, because `update` runs `adopt`, which takes that one itself.

On a joined machine `update` does this, in order:

1. Read `live-update.yaml` in the config directory. It has four required keys: `hub_update_command`, `hub_restore_command`, `hub_invite_command` and `hub_address`, the `host:port` this machine reaches the hub at. A missing file or key stops the script and names it, with nothing changed.
2. Record what `amoeba list -j` shows, and the installed commit. The commit is the one in `backups/installed-commit`, which today's script writes after each update, or the one given with `--previous <commit>`. With neither, the script stops here and names the flag, as today. It writes that commit to `backups/previous-commit`, which is what `restore` installs.
3. Run `hub_update_command` with `--address <hub_address>` and the checkout's commit as its last arguments, for at most `HUB_COMMAND_SECONDS` (900, a constant in the script; the command builds an image). A command still running then is stopped and counts as failed.
4. Call `hello` until the hub answers with the release's version, for at most `HUB_UPDATE_WAIT_SECONDS` (300, a constant in the script).
5. Install this checkout with `uv tool install`, as today.
6. Read back: `amoeba list -j` succeeds and shows the same members, and `amoeba-mcp` lists its tools.
7. Print the machines and sessions that are behind, from `list` (263 D12), with the upgrade command for each.
8. Write this commit to `backups/installed-commit`, as today. Delete every `backups/<stamp>/` directory, which is the store backup the script of earlier releases kept. It is a copy of a store that is now on the hub, and nothing in this release reads it. The `pre-handover-*` directories are not touched.

What a failure does depends on which side failed:

- **Step 3 or 4,** the hub's side: the script runs `hub_restore_command` with the previous commit, under the same time limit, and exits 1 with what it did. The laptop has not been touched. If the restore command itself fails or runs out of time, the script exits 1 saying the hub may be down and printing the restore command, which is safe to run again.
- **Step 6,** the laptop's side: the script reinstalls the previous commit on the laptop and exits 1. The hub is left as it is, because it is serving. If the release changed the door version, the laptop's commands then refuse with the upgrade command. The script's output says so and names the two ways on: `update` again with a fixed release, or `restore --hub`, which puts the hub back too.

`restore` reinstalls the previous commit on the laptop, the one step 2 wrote to `backups/previous-commit`. `restore --hub` also runs `hub_restore_command`. With no `backups/previous-commit` both stop with nothing changed and say why: no update of a joined machine has run since the adoption, so the release before this one is the one before the hub, and the way back to it is `restore --local-store`. The adoption run leaves no such file (below), so neither command can install a release that cannot open the handed-over store, or build a hub from a commit that has none. `restore --local-store` goes back to the release before the hub (D11).

**The first run on a machine with a local store is the adoption.** `update` takes this path in two cases: the machine has no client file and a store at the store path; or the script finds its own adoption record (step 2 below), which means an earlier run started the adoption and did not finish it. This is how the PM's laptop is adopted (D12), and nothing in it is done by hand.

The order keeps the laptop working for as long as it can. `adopt` is run from the checkout with `uv run`, before the release is installed. So until `adopt` migrates the store, the laptop is on the previous release with a store that release opens, and a failure up to that point leaves it exactly so.

1. Step 1 of the main list.
2. **The record.** Read the store's schema on a read-only connection, as the script's read-back does today.
   - Below 15: the previous release still runs on this store, but it may not be the one installed: an earlier run was killed, or a restore was cut off after the store went back, by this script or by hand, and the release installed may be one that cannot list a local store. So the script first runs `restore --local-store`, which reinstalls the record's commit, or with no record the one in `backups/installed-commit`, and deletes the record (D11). Then it records `amoeba list -j` and the installed commit, found as in step 2 of the main list, and writes both to `backups/adoption-run.json`. The commit goes in the record only: this path writes no `backups/previous-commit`.
   - At 15: an earlier run migrated it, and no release installed on the laptop can list it. The script uses the record that run wrote. Nothing has been written to the store since, so the record still describes it. Two cases are not the script's own adoption:
     - A record beside a store that has the mark and no adoption row, or beside no store at all. The first was set aside by a `join --set-aside-local` run by hand after the record was written, and the second was removed by `discard-local`; neither is being adopted. The script deletes the record. A machine with a client file then takes the main list. One without is the next case when it has a store, and has nothing to adopt when it has none (below).
     - No record, on a machine with no client file. The store was handed over by hand and not by `update`. The script stops with nothing changed and names the three ways on: `amoeba join <line>`, which a marked store does not stop; `amoeba adopt <line>`, which finishes a cut-off adoption or says why it cannot; or `restore --local-store`.
3. Step 3 of the main list.
4. Run `hub_invite_command`, which prints a join line for this machine. It is run again every few seconds until it succeeds, for at most `HUB_UPDATE_WAIT_SECONDS`. A hub that has not finished its first start refuses the invite with `HubStoreMissingError` (260 D13), and the retry covers that. This takes the place of step 4 of the main list, because a machine that is not joined cannot call `hello`. A hub on another schema is refused by `adopt_check` (D3). On a run after a kill the line carries a new token; `adopt` takes it in every row of D1 that goes on, row 4 included.
5. Run `uv run amoeba adopt <line> -j` from the checkout.
6. Write the record's commit into the pre-handover backup directory, as `previous-commit`.
7. Install this checkout, as in step 5 of the main list.
8. Read back. `amoeba list -j` succeeds, `amoeba-mcp` lists its tools, and, when `adopt`'s result says `load` is `loaded`, `list` shows as many programs and as many members as the record. When `load` is `skipped`, the hub already held this adoption from an earlier run, and this machine or another may have added or removed members there since. The two numbers are then printed beside the record's and not compared. Open questions and open requests are always printed beside the record's and never compared: a request can expire, and close a question with it, between the two listings. The load has already checked the count of every table it carries (D4), on this run or on the one that loaded.
9. Do step 8 of the main list, delete `backups/previous-commit` if there is one, then delete the record, last, and print the backup's path, the row counts, `sessions_to_restart`, and step 7's list.

What a failure does on this path:

- **Steps 1 to 4, on a run that found the store below schema 15:** the script stops and exits 1. The laptop has not been touched and is still on the previous release and its local store. There is no earlier hub to put back, so `hub_restore_command` is not run. The script deletes the record this run wrote before it exits, so no record outlives a run that never reached `adopt`. The one exception is a failure of the restore that step 2 runs first: the older record it was finishing stays, because that restore still needs it, and it deletes the record itself when it is done. `update` is run again.
- **`adopt` exits with `HandoverBusyError`:** another hand-over command is running on this machine, started by hand. The script exits 1 saying so and runs no restore, because a restore would write the store under that command (D5). The record stays when the store is already migrated and is deleted when it is not, as above. `update` is run again when that command has ended.
- **Anything else after step 4** (`adopt`, the install, the read-back), **and steps 3 and 4 on a run that found the store already migrated:** the script runs `restore --local-store` itself and exits 1 with the error. What that command does is decided by the store alone (D11). A store that `adopt` never migrated is left exactly as it is, with its config, and the record's commit is installed again. It is installed every time, without asking what is installed now: nothing on the laptop records that until an update has finished, and installing the same commit twice changes nothing. A migrated store is replaced by the backup taken just before its migration. Either way the laptop ends on the previous release, with a store that release opens and every record the laptop has written, and with no client file.
- **The hub after such a failure.** If it had loaded the store, it still holds that copy. `restore --local-store` keeps the store's adoption id (D11), so the next `update` is not refused: `adopt_check` answers `holds_this`, and the hub skips the load, or loads the store again if the laptop has written to it since (D1). Nothing is done on the hub machine. The one case that still refuses is D1's `both_changed`: the laptop wrote to its store after the restore and another machine wrote to the hub. That refusal names its two commands.
- **The script is killed.** No handler runs, so nothing is put back. Where it was killed decides what the laptop holds, and `update` run again goes on from any of them: a store below 15 starts the adoption over, after `restore --local-store` finishes any restore that was cut off (step 2); a migrated store uses the record; a machine that already has its client file is D1's row 4. A kill inside step 9 leaves the record, and the next `update` walks the same path once more, finds everything done and finishes. `restore --local-store` goes back from any of them. Between a kill after `adopt` migrated the store and the next of those two commands, the previous release's commands and sessions are refused by the store's schema, with the store's usual message. That cannot be avoided, since no handler runs after a kill, and it is ended by either command.

A machine with no client file and no store has nothing to adopt. The script stops at step 1 and says to run `amoeba join`.

The script no longer backs up, migrates or checks a local store. The hub backs its own store up before a migration, and `adopt` takes the pre-handover backup. It reads a local store's schema version, and whether it has the mark and an adoption row, read-only and with a missing table meaning none, to choose its path. The one place it still writes a store is `restore --local-store`.

`hello`'s reply gains `hub_version`, the hub's package version. An added field does not change the door version.

**On the hub machine,** three scripts shipped in `docker/`, run from the clone that holds the compose file:

- `hub-update.sh [--address <host:port>] <commit>`: fetch and check out the commit, build the image, run `amoeba hub add-config-keys` in the new image, write `pre-update-backups` (below), then `docker compose up -d`. The hub takes its own backup before a migration when it starts. `add-config-keys` opens no store, so it runs before the hub has one. These make it safe on a first run and on a later one:
  - When the config directory holds no `hub.yaml`, it first writes `hub.yaml` and the compose file from the shipped examples and prints both paths. So the first run sets the hub up, and the release needs nothing done on the hub machine beyond the clone. The example's `backup_dir` is a directory beside the state directory; `docs/hub-setup.md` says how to point it at another disk.
  - **The address.** `hub.yaml`'s `address` is what join lines carry (260 D14), and neither a container nor an example file knows the hub machine's LAN name. So a first run needs `--address`: it writes that value as `address` and its port as `port`, and without the flag it stops before it writes anything and names it. On a later run a given `--address` that differs from `hub.yaml`'s replaces it, through a temporary file and a rename, and the script prints the old and the new value. So a wrong `hub_address` is corrected in `live-update.yaml` alone and the next `update` carries it to the hub. Only join lines made after that change; a machine already joined keeps the address in its client file until `amoeba join --address`. If the new address has another port than `hub.yaml`'s `port`, the script stops before anything changes and prints both, because the published port is in the compose file and moving it is a change to the hub's set-up (`docs/hub-setup.md`). `update` always passes `hub_address` from `live-update.yaml`.
  - **Where the hub's directories are.** The example compose file mounts three directories under `~/amoeba-hub/` on the hub machine: `config/`, `state/` and `backups/`. They are never the machine's own Amoeba config and state directories. A home that holds `hub.yaml` is a hub home, where `join` and `adopt` are refused (D5), so a hub in Docker on a machine that is also a client, such as the laptop in the rehearsal, must not share them.
  - When the clone is not already at the commit, it deletes `config.yaml.before-keys` and `pre-update-backups` before anything else. Those files belong to an earlier update, and `hub-restore.sh` would otherwise put a months-old config back after a failed one.
  - **A restore that did not finish** is the one case where those files are still needed, so the script looks for it before that delete. The signs are a `restore.partial/` in the state directory, or all three of: `pre-update-backups` exists, `<backup_dir>/pre-migration/` holds a whole directory the file does not list, and the state directory holds no store. `hub-restore.sh` moved the store away and never brought the backup in. Then `hub-update.sh` finishes that restore first: it runs `hub-restore.sh` with the commit the clone is at, which is the one the restore checked out in its step 1, before the step that moved the store. The restore works from the list that is still there. When it has succeeded the update goes on as usual; when it fails, `hub-update.sh` stops there with its output, having deleted nothing, and is run again. A first run that failed has no pre-migration backup, so it never looks like this and is simply run again. A restore that failed before it moved the store leaves the migrated store in place under a stopped hub, and the update goes on from that store, which is the one the failed release left.
  - **`pre-update-backups`** is a file in the state directory that lists the names of the whole directories under `<backup_dir>/pre-migration/` just before the new image starts. It is written once per commit: a run that finds it leaves it. It is how `hub-restore.sh` tells the backup this update made from one an earlier release left.
- `hub-invite.sh <machine>`: runs `amoeba hub invite <machine>` in the running container and prints the join line.
- `hub-restore.sh <commit>`: the architecture's undo, the previous image with `serve --from-backup`, as one script. Its steps:
  1. `docker compose stop`, check out and build that commit, and move `config.yaml.before-keys` back over `config.yaml` if the update wrote one.
  2. Decide whether the store must go back. It must when `pre-update-backups` exists and `<backup_dir>/pre-migration/` holds a whole directory that the file does not list. That directory is the backup the failed update's migration made. 260 keeps one per schema version (260 D15), so there is one; if there are more, the newest is used. With no such directory the update did not migrate, the store is the previous release's own, and the script goes to step 5. With no `pre-update-backups` file a restore has already finished (step 4), and the script goes to step 5.
  3. Move the store with its side files, the certificate and the key into a new `replaced-<UTC stamp>/` in the state directory, each only if it is there. 260's `--from-backup` refuses a working hub and leaves it to this script to move the files first (260 D14).
  4. Make 260's one restoring start (260 D17): `docker compose run --rm --service-ports hub --from-backup <that directory>`, in the background, with its stderr read by the script. That start prints its one serving line on stderr when the restore is done and it is serving (260 D16). The script waits for the line for at most `RESTORE_START_SECONDS` (120, a constant in the script), then stops that container and deletes `pre-update-backups`. If the container exits first or the time runs out, the script stops the container, prints its stderr and exits 1, with the file still there.
  5. `docker compose up -d`.

  It stops at the first step that fails and can be run again from any point. Each move is made only when its file is there. Whenever it stops on a failure and a `replaced-<stamp>/` directory exists, its last line names the newest one with the full `hub-restore.sh --put-back <that dir> <commit>` command, so stacked failures never leave the operator to work out which set of files to bring back. A restore cut off inside step 4 leaves `restore.partial/`, and the next run's `--from-backup` finishes it (260 D14). A run killed between the serving line and the delete restores the same backup once more, which sets the just-restored files aside in one more `replaced-` directory and ends the same way. Until it finishes the hub is down.
- What was recorded after the update began is not on the restored hub. It is in `replaced-<stamp>/`, and the script prints that path. `hub-restore.sh --put-back <dir> <commit>` stops the hub, deletes `pre-update-backups` for the reason given under `--empty` below, moves the current three files into a new `replaced-<stamp>/`, moves that directory's files back, and starts the given commit, which is the fixed release. `hub-restore.sh --discard <dir>` deletes one. These two commands end every `replaced-<stamp>/` directory, whoever made it: this script, `--empty`, or 260's own `serve --from-backup` run by hand, which moves away a damaged hub's files or a stopped first start's (260 D14). Such a directory may hold only some of the three files. `--put-back` refuses a directory that lacks the store, the certificate or the key, names what is missing and changes nothing, because putting part of a hub back makes a hub that will not start; `--discard` is the end for that one.
- `hub-restore.sh --empty` stops the hub, deletes `config.yaml.before-keys` and `pre-update-backups`, moves the store, certificate and key into a new `replaced-<stamp>/`, in that order, then moves the `timed/` and `pre-migration/` directories of `backup_dir` into `replaced-<stamp>/backups/`, and starts the hub, which makes a new store and certificate. The backup lock file stays (260 D15). The backups have to move too: by 260's start table a state directory with no store beside a `backup_dir` that holds a backup is a lost hub and is refused, and with no store, no certificate, no key and no backup it is a first start (260 D5). A new hub must not rotate the old hub's backups out either. The order matters if the script is cut off and the container is started by something else, such as a reboot: with the store gone and a backup still there the start is refused, and no state in between makes a new certificate beside the old store. It is the command behind every "empty the hub" in this design (D1, D11). The directory it leaves ends the same two ways. `--put-back` on a directory that holds `backups/` also sets the current backups aside with the current three files and moves the kept ones back into `backup_dir`, and `--discard` deletes them with the rest. It stops at the first step that fails and can be run again, as the restore can. The two files are deleted before the store moves, so a half-emptied hub never looks to `hub-update.sh` like a restore that did not finish, and no backup is restored into it.

`live-update.yaml` holds the three commands and `hub_address` because only the PM's set-up knows them. `hub_address` is the hub machine's LAN name and the hub's port, as the laptop reaches it, and it is the address every join line of that hub then carries. For the PM's hub each is `ssh`, the hub machine's name, and the path of one of the three scripts in the clone there, with the laptop's machine name after `hub-invite.sh`. For a hub on the same computer each is the script's path.

**`amoeba hub add-config-keys`** replaces the script's `add_missing_keys`, which edited a config file that is no longer on the laptop. It works on top-level keys only, which is what every key in the config contract is. A key is missing when the parsed file's mapping does not have it. Each missing key is written as YAML at the end of the file, and a key the file already has is never touched or written twice. A wrong value inside a key, such as an `authorize_items` entry without one of its fields, is not this command's to fix; the loader reports it as today. When it has a key to add, it first copies the file to `config.yaml.before-keys` in the state directory, unless that file is already there: a second run for the same commit must not replace the copy from before the first with a config that already holds the new keys, which the previous release's loader would refuse as unknown. Then it writes the new text to a temporary file beside `config.yaml` and renames it over the old one, as `adopt_config` does, so a crash or a full disk partway leaves the old file whole. A write that fails is exit 3 with the path, and the command is run again. It prints the keys it added. With nothing to add, or with no `config.yaml` yet (a hub that is waiting for its adoption), it writes nothing.

The values come from `amoeba/config/config.yaml.example`, a YAML file in the wheel that the command loads with the YAML parser. Today the script scrapes them from the example block of `docs/config-contract.md`; that block stays as documentation, and `tests/test_contract_docs.py` asserts it equals the file. A required key the file has no value for fails the command with the key named, and nothing is written. A test loads the shipped file as a valid config, so that cannot happen in a release.

**The laptop's config on the adoption run.** Today's script adds a missing key to the laptop's `config.yaml` before it installs. On the adoption run that work is `adopt`'s: the function that works out the completed text is one function, used by `add-config-keys` on the hub's file and by `adopt` on the laptop's text in memory (Data Flow, step 3). So a key this release requires and the PM's file lacks never stops the adoption, and no file is edited by hand. The laptop's file itself is left as it is, because the release's restore puts the laptop back on the previous release, whose loader refuses a key it does not know. The hub gets the completed text, and `adopt`'s result lists the keys as `config_keys_added`, which `update` prints.

The release skill's step 7 becomes: run `update`, and report what it prints. That is the machines and sessions behind, and on the adoption run also the backup's path, the row counts and the sessions to restart. The skill keeps its line that this is a release step and not a per-slice one. The script's read-back checks from 260 to 263 that open the local store are removed.

- Rejected: restoring the hub by hand, following `docs/hub-setup.md`. A hub that fails its migration is down for every machine, and today's script puts a failed update back by itself.

### D11 — Moving and undoing
Status: decided

Nothing new is built for moving. The slice tests the architecture's path on the fixture and writes it down: `amoeba hub backup`, `amoeba hub serve --from-backup <dir>` on another state directory, `amoeba join --address` on each machine.

Undoing an adoption that went wrong, found later:

- **Adopt again.** `amoeba leave`, `hub-restore.sh --empty` on the hub machine, `hub-invite.sh` for the laptop, `amoeba adopt <line> --again`. The laptop's store is as it was at adoption, so what was recorded on the hub since is not on the new hub. It is kept in `replaced-<stamp>/` until `--put-back` or `--discard`. Other machines join the new hub with new invites.
- **Back to the release before the hub.** `uv run python scripts/update_live.py restore --local-store`. It takes the handover lock first and holds it to its last store step, and stops with `HandoverBusyError` and nothing changed when an `adopt`, a `join --set-aside-local` or a `discard-local` holds it (D5). Then it reads the store's schema on a read-only connection, and that alone decides what it does to the store. "At 15" below, and in D10, means 15 or above: a store a later release migrated further is restored the same way.

  - **Below 15, or no store.** `adopt` never migrated this store, so the previous release still opens it and it may hold records written since any backup. The store and `config.yaml` are not touched, whatever backups exist. The command runs `amoeba leave` (from the checkout with `uv run`, here and below, since the installed release may be one that has no `leave`), installs the commit in `backups/adoption-run.json`, or with no record the one in `backups/installed-commit`, writes that commit to `backups/installed-commit`, and then deletes the record. It installs that commit every time, without asking what is installed now, since nothing on the laptop records that in the middle of an update or of a restore that was cut off. With neither file nothing is installed. A `previous-commit` in an older backup is never used here: it names the release before an earlier adoption, which could not open this store.
  - **At 15, with a whole pre-handover backup.** In this order: `amoeba leave`, and delete a left-over `adoption-copy.sqlite3`, which `leave` skips while this command holds the lock (D5); put the backup's `config.yaml` back in the config directory when `config.yaml` is missing or `config.yaml.moved-to-hub` is there, and delete `config.yaml.moved-to-hub`; write the store's adoption id, when it has one, to `<state home>/kept-adoption-id`; write the previous commit (below) to `backups/installed-commit` and delete `backups/previous-commit`, which names a release of the hub era; copy the backup's `amoeba.sqlite3` over the store path with SQLite's backup call, which lands whole or not at all; install the previous commit; delete `backups/adoption-run.json`. Each step is skipped when it is already done, so a restore that was cut off is finished by running it again: once the store is back below 15, the run is the first case, and the config was put back before the store.
  - **At 15, with no whole backup.** That is the case after `discard-local` was cut off. It stops with nothing changed and names `amoeba discard-local`, which finishes.

  There is one whole backup at most, the newest, and it is the store as it was just before the migration that closed it (D5). So this command can never put back a store older than records the laptop has written: a store the previous release could still write is never replaced, and a store at schema 15 has had no writer since its backup, apart from the late write D2 describes, which `adopt` and `discard-local` report. In the second case the previous commit is the one in that backup's `previous-commit`, never `backups/previous-commit`. When the adoption was cut off before that file was written, it is the commit in `backups/adoption-run.json`, or else in `backups/installed-commit`, which the script writes only when an update has finished and in `restore --local-store`. Writing it before the store goes back means the next `update`'s record, and a cut-off restore run again (the first case), install the release before the hub, never a release of the hub era over a local store.

  **The kept adoption id** is what lets the next `adopt` go on with the same hub. The restored store has no `adoption` table, so without it the hub that loaded this store would answer `hub_not_empty`. With it `adopt_check` answers `holds_this`, and D1's table decides: skip the load, load again, or `both_changed`. The next `adopt` that runs the full flow writes it into the store and deletes the file; if the store already has an id, it just deletes the file. The file never chooses a row of D1, and `join --set-aside-local`, `adopt --again` and `discard-local` delete it (D1, D5).

  What was recorded on the hub since the adoption is not on the laptop. This is the stated restore path for the migration `adopt` runs on the live store, and it is the command the release runs by itself when the adoption fails (D10).

Restore needs the script, so it needs a checkout. An install with no checkout gets one with `git clone` and runs `uv run python scripts/update_live.py restore --local-store` from it. Nothing is restored by hand, and `docs/hub-setup.md` says so.

Both paths need the handed-over store or its backup, so neither is possible after `discard-local` (D5).

The architecture starts a hub straight from the laptop's backup and invites its one machine. 260's hub refuses a store with no certificate (260 D5), and `--again` reaches the same end with the command that already exists.

### D12 — Documents and the PM's install
Status: decided

`docs/hub-setup.md` is new: the clone and `live-update.yaml`, start a hub, invite, join, adopt, the fresh hub with no store to adopt, change a setting, move `backup_dir` to another disk, release and restore, empty a hub, move, undo. The call format gets its section there, taken from 260 D6 to D10.

Brought in line: `docs/cli-contract.md` (`adopt`, `hub add-config-keys`, `join` and `leave` as in D5, `NotJoinedError`, no local way), `docs/config-contract.md` (one config, on the hub; `live-update.yaml`), `docs/store-contract.md` (migration 015, the homes, with the pre-228 section removed), `docs/mcp-server.md` (start-up as in D6, no local config), `docs/squadron-hook.md` (a hook on a machine that is not joined). `tests/test_contract_docs.py` pins them.

`260-arch.the-hub.md` and the 264 entry of `260-slices.the-hub.md` hold, as amended on 20261120, the rows of the departures table below that change them: the principles "Only the hub opens the store", "One hub call is one whole transaction" and "A repeated call is safe", the door's one call that is not JSON and its two times, the meaning of an empty hub, the six adoption steps with the adopted mark and the undo, and the plan's entries for the release, the PM's install and where a store may be opened. So this design is read against parents that already hold its departures, and no task amends them. 265 and 300 read those documents, not this one. The full-text review of 20261121 added the rows at the end of the departures table that are marked with that date. Where a parent still says otherwise, this design is the one to build from, and the parent's sentence is listed in that review's resolution.

**The PM's install is not a task of this slice.** The live install is updated by `scripts/update_live.py update` as the last step of a release, never per slice and never per merge, and adoption is no exception. The PM's store is adopted by the release that ships this slice, after code review and the merge, by the first-run path in D10. So the live store is only ever moved by code that has been reviewed, and a review fix to migration 015, the three fixes or the load is made before any real data has met them.

Nothing at the release is left for a person to do or remember. The release skill's step 7 runs `update`. `update` sets the hub up or updates it, gets the join line, adopts, installs the release, reads back and prints the backup's path, and it puts the laptop back by itself if the adoption fails. The one thing it needs that this slice cannot make is in Prerequisites: the clone on the hub machine and `live-update.yaml`. Without them it stops before it changes anything and names the file, and the laptop carries on with the previous release and its local store.

Implementation proves the same path without the PM's install:

- **On fixtures.** The tests in D9, and `tests/scripts/test_update_live.py` for the first-run path with fake hub commands.
- **The rehearsal,** the slice's last task, after the whole suite passes. A hub in Docker on the laptop is set up by `hub-update.sh --address 127.0.0.1:<port>` on its first run, in its own directories under `~/amoeba-hub/` (D10). A throwaway `AMOEBA_HOME` gets a copy of the live store, taken with SQLite's backup call on a read-only connection, and a copy of the live `config.yaml`. `hub-invite.sh` gives a line, and `uv run amoeba adopt <line>` from the slice's checkout adopts that home. `amoeba list -j` there must show the programs, members, open questions and requests that the installed release shows for the live store. The live store and the installed release are not written or changed. The output, with the row counts, goes in the slice notes.

  **What the rehearsal proves about the address, and what it cannot.** It proves the path the address takes: a first run without `--address` stops and writes nothing; with it, `hub.yaml` holds that address, the join line carries it, and `adopt` reaches the hub at it. It cannot prove that the PM's `hub_address` is right, that the LAN machine's name resolves from the laptop, or that its port is open, because the rehearsal's hub is on the laptop itself. Those are first met at the release, in step 1 of `adopt`, which fetches the certificate and calls `hello` before anything on the laptop changes. A wrong address fails there with `HubUnreachableError` naming it, the laptop is untouched and still on the previous release, and `update` is run again once `live-update.yaml` holds the right one; `hub-update.sh` then writes it into the hub's `hub.yaml` (D10).

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
| Plan, Planning Context: adoption "is a copy, not a migration". Architecture: by then "the laptop's store is already at the new schema and its members are named" (20261121) | `adopt` migrates the store to schema 15 and names the members itself, on a store that may still be at schema 10 | 260 to 264 can ship in one release, migration 015 is this slice's, and the opener that migrated and named on every call is deleted (D2) |
| Architecture walkthrough, step 1: a person writes `hub.yaml` on the LAN machine (20261121) | `hub-update.sh` writes it on its first run, with `address` from `hub_address` in `live-update.yaml` | Nothing at the release is done by hand, and only the PM's set-up knows the address (D10) |
| Every row count matches on the hub (20261121) | Every count outside the six hub-own tables matches. The laptop's own session rows, reported runs and kept results are not carried | They describe programs on the laptop, and each is written again by a tick or a `list` (D4) |
| `restore --local-store` puts the pre-migration backup and the config back (20261121) | Only over a store `adopt` migrated. A store the previous release still opens is left alone. The store's adoption id is kept for the next `adopt` | A backup must never replace records written after it, and the hub that loaded the store must not refuse the next attempt (D11) |
| The release runs `amoeba adopt` on the laptop (20261121) | It runs it from the checkout before it installs the release | The laptop stays on a release that opens its store until the store is migrated (D10) |

### Amendments to 260 and 263

| Design says | This slice |
|---|---|
| 260 D4: `--set-aside-local` marks the store, copies it to `amoeba.sqlite3.set-aside-<UTC stamp>` through a `.partial` file and deletes the original; at most one set-aside exists; `leave` puts it back, and moves a hand-placed store to a `displaced-` name | The store stays at its path, at schema 15, marked, with a pre-handover backup. `leave` touches no store. No `set-aside-`, `.partial` or `displaced-` file is made. One left by a release from 260 to 263 is ended by `discard-local --force` (D5) |
| 260 D4: `join` on a joined machine replaces the client file after a successful `hello` | `adopt` does the same in D1's row 4 |
| 260 D1, D2: the local opener and `prepare_state_home` raise `HubHomeError` in a hub home | Both are deleted. `store.handover` makes the check, so `adopt` and `discard-local` refuse there (D5) |
| 260 D14: `replaced-<UTC stamp>/` has no command that ends it; 264 adds them | `hub-restore.sh --put-back` and `--discard`, for every such directory (D10) |
| 260 D14, D17: a restore is one start with `--from-backup`, run by hand with the compose service stopped | `hub-restore.sh` makes that start itself, after moving a working hub's three files away, and stops it at the serving line (D10) |
| 260 D14: `hub.yaml`'s `address` is written by a person | `hub-update.sh --address` writes it on a first run and replaces it on a later one (D10) |
| 260 D12: `closed_mark` holds `hub_address` and `closed_at` | Also `reason` (D8) |
| 260 D2: `joined()` returns nothing with no client file | It raises `NotJoinedError` |
| 260 D2: both store openers and `prepare_state_home` raise `LocalStoreClosedError` when a client file exists | The local opener and `prepare_state_home` are deleted. `store.handover` never creates a store (D5, D7) |
| 260 D4: `hello` returns the machine's name | Also `hub_version` |
| 260 D12: `state_move.py` holds both openers | `hub/store_open.py` and `store/handover.py` |
| 260 D17: the compose example's three mounts | The config mount is writable, and the three host directories are under `~/amoeba-hub/`, never a client's own home (D10) |
| 260 D17: the contract's example block is the one source of the `config.yaml` example | `config.yaml.example` in the wheel is the source, shipped beside `hub.yaml.example`; the contract's block is tested equal to it (D10) |
| 263 D8: with no client file, `amoeba-mcp` runs today's start checks | It starts and its tools return `NotJoinedError` (D6) |
| 263 D13: two predicates in `store/sql_sessions.py`, `LIVE_SESSION` and the waking rule | A third, `FRESH_HEARTBEAT`, the heartbeat test alone. `LIVE_SESSION` is composed from it and means what it meant (D2) |
| 260 D4: `leave` deletes the client file and the certificate | It also deletes a left-over `adoption-copy.sqlite3`, when no hand-over command is running (D5) |
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

uv run python scripts/update_live.py update [--previous <commit>]
uv run python scripts/update_live.py restore [--hub | --local-store]

docker/hub-update.sh [--address <host:port>] <commit>
docker/hub-invite.sh <machine>
docker/hub-restore.sh <commit>
docker/hub-restore.sh --empty
docker/hub-restore.sh --put-back <dir> <commit>
docker/hub-restore.sh --discard <dir>
```

`adopt`'s result: `outcome` (`adopted`, `already_adopted`), `hub`, `machine`, `load` (`loaded` when this run sent the store and the hub loaded it; `skipped` on every other run that goes on, rows 4 and 5 of D1 included), `counts`, `config` (`written`, `same`, `kept`), `config_keys_added`, `backup` (the pre-handover path), `store` (the handed-over store's path), `sessions_to_restart` and `changed_after_handover`. A rejection's result has a `code`, and an error's result names its error type, which is how `update` tells `HandoverBusyError` from any other failure. Exit codes are today's: 0 done, 1 rejected, 2 usage, 3 error. The hub calls are in D3.

`update` and `restore` exit 1 at once when another one holds `update.lock`. `restore` and `restore --hub` exit 1 with nothing changed when there is no `backups/previous-commit`, and name `restore --local-store`.

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

- A fixture laptop store at schema 10, with members, questions, requests, standing answers and wakes, is adopted. The count of every table outside `HUB_OWN_TABLES` on the hub equals the laptop's, and `list` from the laptop shows the same records as the store held. The laptop's own session rows, reported runs and kept results are not on the hub.
- The laptop's machine on the hub has the name in the join line, and its checkouts, questions and wakes belong to it. A second machine invited before the adoption still joins with its line afterwards.
- A second load onto a hub that holds kept call results of another machine is not refused as `copy_damaged`. An upload whose count header names a table that is not in `STORE_TABLES`, or lacks one, is refused as `malformed_call`. `STORE_TABLES` equals the tables of a freshly migrated store, and no statement in `store.adoption` or `hub.adoption` is built from a name read at run time.
- Adoption is refused as `hub_not_empty`, with the tables and counts, when the hub holds a member. Nothing on the laptop is marked.
- Adoption goes through with a local session row live. Its `sessions_to_restart` names each live session, one whose row has no door version included, and says which must be restarted. A program at schema 14 that opens the store after the migration is refused.
- A store set aside by `join`, with a client file for the same hub, is rejected by `adopt`, which names `amoeba leave` and then `--again`, and nothing is renamed. `adopt --again` is rejected there too and names `amoeba leave`. After `leave`, `adopt --again` adopts the store into an empty hub.
- A store set aside with `join --set-aside-local` after an `adopt` that failed once its id was written has no adoption row. `adopt` on it is rejected as set aside, never prints `already_adopted` and renames nothing, and `discard-local` says it was set aside and never adopted. `adopt --again` on a store that has an adoption id and no mark is rejected and names `adopt`; `adopt` then finishes it with one copy on the hub.
- `adopt` and `discard-local` in a home that holds `hub.yaml` fail with `HubHomeError` and leave the store's rows and mark as they were. A second hand-over command started while one runs fails at once, and the first one's copy and backup are untouched.
- No store is created or written by mistake. `adopt`, `adopt --again`, `discard-local` and `join --set-aside-local`, each run in a home with no store, with and without a client file, leave no file at the store path. `adopt` run again and `discard-local` without `--force`, on a joined machine with a handed-over store, open it read-only.
- `adopt` with no local `config.yaml`, and with a backup directory that cannot be written, each stop with exit 3 before the store is migrated and leave no partial backup. The naming fix calls `cf` with no write lock held, and no `cf` call is made once the lock is taken.
- A connection opened before the adoption fails its next write with `LocalStoreClosedError` naming the hub, and the store's counts do not change. `handle-pause` from this release, run during the adoption, fails with `NotJoinedError` and opens no store.
- Adoption cut off after the load, after the config and after the mark is finished by the same command, and the hub holds one copy of the data. A row written to the local store between two attempts, and a row changed there with no count changed, are each on the hub afterwards.
- With the hub changed and the laptop changed between two attempts, adoption is refused as `both_changed` and neither store is changed. The same holds when the hub's change is to a row and no count.
- Adoption cut off after the client file is finished by the same command: the laptop's `config.yaml` is renamed. A marked store whose hub answers `empty` is rejected naming `--again`.
- The pre-handover backup, taken while the store has a `-wal` file with committed rows, holds those rows. `join --set-aside-local` takes one too. An `adopt` that fails after the migration and is run again takes no second backup, and `--again` on a store at schema 15 takes none. `--again` on a store that `restore --local-store` put back takes a new one, and a record written to that store before it is on the hub and in that backup. A backup killed partway leaves only a `.partial-` directory, which the next backup deletes and which is never restored from. After a store is restored and adopted again, one `pre-handover-*` directory exists, the new one.
- An upload cut off partway, and one that sends nothing for `UPLOAD_IDLE_SECONDS`, each leave no file on the hub and the hub's store as it was. A full disk is refused as `hub_error` with the store as it was. A tick during a slow upload is answered inside 2 seconds. An attempt still sending after `ADOPT_UPLOAD_SECONDS` (set small by the test) is stopped by the client, and `adopt` fails with the store's size and the time allowed, with the lock released and nothing marked. Each upload refusal is a line in the hub's log.
- An upload with a wrong SHA-256 or a wrong count is refused as `copy_damaged`, and the hub's store is as it was. A call from another machine during a load is refused and nothing of it is stored. A `hub rm-machine` during a load is refused, and a hub started with a `loading` mark clears it.
- A writing call repeated with its call id after a second load returns its first result and applies once. An upload repeated after a load answers `loaded` and loads nothing.
- A write made to the store after the switch is reported as `changed_after_handover` by `adopt` and by `discard-local`, which then deletes nothing without `--force`.
- `discard-local` deletes the backups, `config.yaml.moved-to-hub` and the store when the machine is joined and the hub holds the adoption. It refuses an unmarked store with or without `--force`. Without `--force` it refuses a set-aside store, a machine that is not joined and a hub that does not hold the adoption, and says which. With `--force` it deletes in each of those cases and makes no hub call, so a store is discarded after `leave`. Cut off after the backups are deleted, it finishes when run again. A `set-aside-<stamp>` store left by an earlier release is refused without `--force` and deleted with it. A handed-over store stamped at schema 15 is read by `discard-local` when the program expects a later schema.
- `join` and `adopt` are rejected, naming the file, when a store exists at the pre-228 path.
- The hub with no `config.yaml` gets the laptop's; a hub that has a different one keeps it and the result says `kept`; the same call again says `same`. The laptop's file is renamed.
- `adopt --again` after `leave` adopts the same store into a second empty hub.
- Moving: after `hub backup`, a hub started with `--from-backup` on another state directory and port serves both clients after `join --address`, and `list` shows the same.
- With no client file, every CLI command but `join`, `adopt`, `leave`, `discard-local` and `hub`, and every MCP tool, fails with `NotJoinedError`, and no file is created. `amoeba-mcp` starts, and serves from its next call once the machine joins.
- `join` refuses beside an unmarked store and names both commands. `join --set-aside-local` leaves the store at its path, at schema 15, marked. `leave` deletes only the client file, the certificate and a left-over copy.
- A fresh hub with `config.yaml` written from the example serves a new machine's `add` and `send`.
- A bad edit to the hub's `config.yaml` fails `send` with the file and key named, and the fixed file is used by the next call with no restart.
- `update_live.py update` with fake hub commands: updates the hub before the client; a hub that never reports the new version runs the restore command and leaves the laptop alone; a failed read-back reinstalls the previous commit and does not run it; a hub command that outlasts its time limit is stopped and counts as failed. A missing `live-update.yaml` key, `hub_address` among them, stops it before anything runs. A successful run deletes an old `backups/<stamp>/` directory and no `pre-handover-*` one.
- `update_live.py update` in a home with a local store and no client file, with fake hub commands and a fixture hub: it gets a join line, adopts from the checkout before it installs, writes `previous-commit` beside the backup and prints the backup's path, the counts and the sessions to restart. A failed hub command leaves the home untouched and runs no restore command.
- No failure of that run replaces records or strands the laptop. Each case below ends with the previous commit installed, no client file, and a store that commit opens:
  - `adopt` refused before it migrates (the hub unreachable at a wrong address, `hub_not_empty`, a bad local config): the store and `config.yaml` are byte for byte as they were, including a row written after an older pre-handover backup that is still in `backups/`.
  - `adopt` failing after the migration, a failed install, and a read-back that differs: the store and `config.yaml` are as they were before the migration.
- `update` run again after each of those adopts the store. Where the hub had already loaded it, the second run is not refused as `hub_not_empty`: it skips the load, or loads again when a row was written to the restored store in between, and that row is on the hub. Run a third time after a second failure, it ends the same way.
- `update` killed (the test stops it with a hook) after `adopt` migrated the store, after the mark, after the client file and after the install is each finished by running `update` again, with one copy of the data on the hub and the laptop's token the newest invite's. After each of those kills `restore --local-store` instead puts the pre-migration store back.
- Two runs at once. A second `update` or `restore` started while one runs exits 1 at once and changes nothing. `restore --local-store` started while an `adopt` holds the handover lock stops with `HandoverBusyError`, and the store, the mark and the copy are as that `adopt` left them. An `update` whose `adopt` meets a hand-run hand-over command exits 1 and runs no restore. `leave` run during an `adopt` does not delete the copy, and the `adopt` finishes.
- A stale record does nothing. `update` whose hub command fails before `adopt` leaves no `adoption-run.json`. With a record left by a kill, then `join --set-aside-local` run by hand: the next `update` deletes the record, takes the main list, and the machine is still joined with its set-aside store untouched. The same with the store removed by `discard-local`.
- A kept id does not make a set-aside store look adopted. After an adoption that loaded, `restore --local-store`, a row written to the store and `join --set-aside-local`: no `kept-adoption-id` is left, `adopt` is rejected as set aside and prints no `already_adopted`, and `discard-local` says the store was set aside and never adopted. The same store with the file put back by the test is still rejected as set aside.
- A restore cut off after the install. `update` killed inside its own restore, after the store is back below 15 and before the previous commit is reinstalled, is finished by `update` run again: it reinstalls the record's commit, records the listing and adopts. `restore --local-store` on a store below 15 with a record reinstalls the record's commit even when that commit is already installed. After a finished adoption, `restore --local-store` and then `update` whose `adopt` is refused before it migrates (the hub unreachable): the laptop ends on the release before the hub, and `restore` and `restore --hub` stop and name `restore --local-store`. A hand-run `restore --local-store` killed after the store is back and before the install is finished by `update`.
- After a restore and a member added on the hub by another machine, `update` run again skips the load, prints both member counts and does not fail its read-back. `restore` and `restore --hub` run after the adoption run stop with nothing changed and name `restore --local-store`. `update` killed inside its last step is finished by `update` run again, and `installed-commit` holds the release.
- A laptop `config.yaml` that lacks a required key is adopted: the hub's `config.yaml` holds the key with the example's value, the result lists it in `config_keys_added`, and the laptop's file and the copy in the pre-handover backup are byte for byte as they were.
- `update_live.py restore --local-store` after a finished adoption puts the pre-migration store and the config back, removes the client file, keeps the adoption id, installs the commit in the backup's `previous-commit` even when a later update left another in `backups/previous-commit`, writes it to `backups/installed-commit` and deletes `backups/previous-commit`. On a store below schema 15 it changes neither the store nor the config. Killed after the config is back and after the store is back, it is finished by running it again. With a store at schema 15 and no whole backup it changes nothing and says so.
- `hub-update.sh` on a first run without `--address` writes nothing and names the flag. With it, `hub.yaml` holds that address and the join line carries it. A later run with another address replaces it and prints both. `hub-restore.sh` after an update that migrated restores the backup that update made, and after one that did not migrate restores no store, with an older pre-migration backup present in both cases. Stopped inside its restoring start and run again, it finishes. `hub-update.sh` to another commit, run on a hub whose restore was stopped after the store was moved away, finishes that restore from the same backup before it updates, and deletes `pre-update-backups` only after. `hub-update.sh` run twice for one commit leaves `config.yaml.before-keys` as the first run wrote it.
- `hub add-config-keys` adds a missing required key with the value from the shipped `config.yaml.example` and keeps a copy of the file in the state directory. With nothing missing, with the key already there, or with no `config.yaml`, it writes nothing. A write that fails partway leaves the old file whole. The shipped example loads as a valid config and equals the contract's block.
- The rehearsal: a copy of the PM's live store is adopted into a hub in Docker on the laptop, and `list` in that home shows the programs, members, open questions and requests the installed release shows for the live store. The live store is not written. The rehearsal's hub is set up with `--address`, its join line carries that address, and the laptop's own config directory holds no `hub.yaml` afterwards.

### Technical Requirements

- `ruff`, `pyright` strict and the full `pytest` run pass.
- The import rules in Component Structure are tested, and no test or source file names a deleted module or function.
- The door load test passes its bounds.
- `docs/hub-setup.md` exists, the five contract documents are updated, `tests/test_contract_docs.py` passes, and `260-arch.the-hub.md` holds the amendments in D12.
- The three shell scripts are run against a hub in Docker on the laptop: a first `hub-update.sh --address` that writes `hub.yaml` and the compose file from the examples, `hub-invite.sh`, an update to a second commit that leaves no older `config.yaml.before-keys`, `hub-restore.sh` stopped partway and run again, and `--empty`, `--put-back` and `--discard` each run once. `--put-back` is also run on a directory that lacks the key, and refuses. `--empty` is run on a hub whose `backup_dir` holds a backup, and the emptied hub starts. The output is in the slice notes.

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
docker/hub-update.sh --address 127.0.0.1:<port> "$(git rev-parse HEAD)"   # first run: writes hub.yaml and the compose file, starts the hub
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

- The laptop's store is never renamed, is deleted only by `discard-local`, and a copy is taken before the first write. Both ways back are commands in D11, and the release runs one of them by itself when the adoption fails. That command never replaces a store the previous release can still write, and `adopt` runs before the release is installed, so the laptop is never left on a release that cannot open its store by anything short of a kill (D10, D11). The live store is adopted only at the release, by reviewed and merged code, after the rehearsal on a copy of it.
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

- **Start.** The release runs `update_live.py update` on the laptop. It sets the hub up on the LAN machine or updates it, gets a join line, runs `amoeba adopt <line>` from the checkout and then installs the release. It prints the counts, the backup's path, whether the hub took the config, and the sessions to restart. By hand it is the same three commands: `hub-update.sh --address`, `hub-invite.sh laptop`, `amoeba adopt <line>`.
- **`live-update.yaml` is missing, or lacks a key, or the hub machine has no clone.** `update` stops and names it. Nothing has changed, and the laptop is still on the previous release and its local store.
- **`hub_address` is wrong.** The hub is set up with it, the join line carries it, and `adopt` cannot reach the hub: it fails naming the address before anything on the laptop changes. Correct `hub_address` in `live-update.yaml` and run `update` again; `hub-update.sh` puts the new address in `hub.yaml` and prints both.
- **The hub's set-up or start fails.** `update` stops with the hub command's output. The laptop has not been touched. Run `update` again.
- **Sessions were open on the laptop.** `adopt` goes through. Nothing has to be closed: the migration has already stopped them from writing. A session on this release's door version uses the hub from its next tick; each older one is named in `sessions_to_restart`, which `update` prints, and its tools fail until it is restarted.
- **The adoption fails at the release for any other reason.** `update` puts the laptop back by itself, and how depends on how far `adopt` got. Refused before it migrated the store: the store and config were never changed and are left alone, with every record in them. After the migration: the store and config go back as they were just before it. Either way the laptop is on the previous release with a store that release opens. Fix the cause and run `update` again, as many times as it takes. If the hub had already loaded the store, the next `update` goes on with it: the laptop still has its adoption id, so the hub skips the load, or loads the store again if the laptop wrote to it in between. On such a run the member counts are printed beside the earlier ones and not compared, because the hub may have been written since it loaded.
- **The local `config.yaml` lacks a key this release requires.** `adopt` adds it to the text it sends, with the example's value, and lists it. The laptop's file is not changed.
- **The local `config.yaml` is missing, or holds a wrong value.** Exit 3 before anything is written, with the file and key named. For a missing file the message gives the command that copies `config.yaml.example` into place. Run again.
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
- **`update` itself is killed during the adoption.** Nothing is put back, because nothing runs after a kill. Before `adopt` migrated the store, the laptop is as it was. After, the previous release is still installed and its commands are refused by the store's newer schema until one of two commands is run. `update` again: it uses the record it wrote before the adoption, gets a new join line, and `adopt` goes on from where it stopped, taking the new token even when the client file was already written. Or `restore --local-store` goes back.
- **The release's install fails after `adopt` finished.** `update` puts the laptop back as for any failure after the migration. The hub keeps the copy, and the next `update` goes on with it.
- **`restore --local-store` is cut off.** Run it again. Or run `update`: with the store already back it finishes the restore, whether this script or a person started it, and then adopts, and with the store still migrated it goes on with the adoption. The config goes back before the store, a store already back is left alone, and the previous commit is installed again whether or not it already is.

**Set aside, not adopted**

- **`join --set-aside-local`.** The store stays at its path, marked, with a backup. Its records are on no hub.
- **Adopting that store later.** `adopt` is rejected and says how: `amoeba leave`, then `adopt <line> --again` into an empty hub.
- **`join --set-aside-local` after an `adopt` that failed.** The store loses that attempt's adoption id, so it is a set-aside store like any other: `adopt` says it was set aside, never that it is adopted, and `discard-local` needs `--force`.
- **`adopt --again` on a store whose adoption was only cut off.** Rejected, naming `adopt <line>`, which finishes it.
- **Two hand-over commands at once.** The second fails at once and says another is running. `restore --local-store` counts as one, so it never writes the store under a running `adopt`. Run the second again when the first has ended.
- **Two `update` or `restore` runs at once.** The second exits at once, saying another is running, and has changed nothing.
- **`update` failed before `adopt`, and the store was then set aside or discarded by hand.** The next `update` finds no record of that run, or deletes the one a kill left, and is an ordinary update of a joined machine. It does not adopt or restore anything.
- **`restore` or `restore --hub` right after the adoption.** Each stops with nothing changed and names `restore --local-store`, the one way back to the release before the hub.
- **A store set aside by a release from 260 to 263.** It lies beside the store path under a `set-aside-` name. `adopt` names it and both ways on: `leave` with that release puts it back to be adopted, or `discard-local --force` deletes it.
- **`join --set-aside-local` with no store.** It joins and says no store was there. No file is created.

**As a client**

- **A fresh hub, nothing to adopt.** `hub-update.sh --address <host:port>` writes `hub.yaml` from the example with that address and starts the hub. Without the flag it stops and names it. Write `config.yaml` from its example, then `hub-invite.sh`, `join`, and `amoeba add` in each repo.
- **A machine that is not joined.** Every command says to run `amoeba join`. An open session's tools say the same and work once it has joined.
- **Changing a setting.** Edit `config.yaml` on the hub. The laptop's old file is named `config.yaml.moved-to-hub`, so it is not edited by mistake.
- **A release.** `update_live.py update` updates the hub, then the laptop, and lists the machines and sessions behind.
- **The hub's update fails.** The hub is put back, with its config as it was before this update's keys, and the script prints where the failed release's store is kept. The store goes back only if this update migrated it, and then from the backup this update made, never from an earlier release's. `hub-restore.sh --put-back` brings it back under a fixed release and `--discard` deletes it.
- **The laptop's update fails.** The laptop is put back to the previous commit and the hub is left serving. If that release changed the door version, the laptop's commands refuse with the upgrade command until `update` is run with a fixed release, or `restore --hub` puts the hub back too. The script says which.
- **The hub's update command hangs.** It is stopped after 15 minutes and the hub is put back.
- **`hub-restore.sh` stops partway.** The hub is down and the script said which step failed. Run it again; it goes on from where it stopped. If its restoring start does not print its serving line inside two minutes, the script stops it and exits 1, and the same holds. If `update` is run before the restore is run again, `hub-update.sh` finishes the restore first and then updates.
- **`hub-update.sh` or `hub-invite.sh` is killed.** Run it again, or let `update` do so. An update killed before `docker compose up -d` leaves the old hub serving or, on a first run, no hub yet; the invite is retried by `update` until the hub has its store.
- **`hub-restore.sh --empty` is cut off.** Run it again. Until the backups have moved, a start is refused as a lost hub and makes nothing new.
- **Moving the hub.** `hub backup`, `serve --from-backup` on the new machine, `join --address` on each client.

**Going back, and clearing up**

- **Leaving.** `amoeba leave` unjoins the machine and changes no store. The handed-over store stays, and every command says to join. From there: `join` with a new line joins again; `adopt --again` adopts the store into an empty hub; `discard-local --force` deletes it with no hub.
- **Undo, keeping the hub.** `leave`, `hub-restore.sh --empty`, `hub-invite.sh`, `adopt <line> --again`. What the hub recorded since the adoption is set aside in `replaced-<stamp>/`.
- **Undo, back to the local store.** `update_live.py restore --local-store`. What the hub recorded since the adoption is not on the laptop.
- **Clearing up.** `amoeba discard-local`, once the old sessions are restarted, deletes the backups, the old config and the handed-over store, after the hub confirms it holds the adoption. It prints each path first. Afterwards neither undo is possible, and it says so.
- **`discard-local` is cut off.** The store is deleted last, so run it again and it finishes.
- **An older program makes an empty store at the path after `discard-local`.** `discard-local` refuses it because it has no mark, and names the way: `leave`, `join <line> --set-aside-local`, then `discard-local --force`. Restarting the sessions `adopt` listed before clearing up avoids it.
- **Sets of hub files that were set aside.** Each `replaced-<stamp>/` ends with `hub-restore.sh --put-back` or `--discard`, including one made by `serve --from-backup` run by hand. One that lacks the store, the certificate or the key cannot be put back; `--put-back` says what is missing, and `--discard` ends it.

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

Seven more were found by the full-text review of 20261121, on the path that touches the PM's store, and closed:

10. `restore --local-store` put back the oldest backup, which after one restore was older than records the laptop had written since. It now leaves a store alone unless `adopt` migrated it, and the one backup kept is the one taken just before that migration (D5, D11).
11. An `adopt` refused before its backup left the release installed over a store only the previous release could run. `adopt` now runs from the checkout before the install, and the script's restore installs the previous commit whatever the store's state (D10, D11).
12. `update` run again after a kill could not list the store it had already migrated. It keeps a record from before the adoption and goes on from it (D10).
13. The first-run `hub.yaml` could not know the hub's address. It comes from `hub_address` in `live-update.yaml`, and a wrong one is corrected there (D10).
14. After a failed adoption the hub held the copy and refused every later attempt until someone emptied it by hand. The restore keeps the adoption id, so the next attempt goes on with that hub (D10, D11).
15. `hub-restore.sh` could not tell this update's backup from an earlier release's, and its restoring start had no stated end. It lists the backups before the update and waits for the serving line, for two minutes at most (D10).
16. A store set aside by a release from 260 to 263, and a `replaced-<stamp>/` directory made by 260's own restore, had no command that ended them. `discard-local --force`, `--put-back` and `--discard` do (D5, D10).

Seven more were found by a second pass on 20261121, which walked the pieces the first review added, and closed:

17. `restore --local-store` wrote the store outside the handover lock, and a second `update` ran it under the first one's `adopt`. The script has its own lock, the restore takes the handover lock, and a busy `adopt` is not followed by a restore (D5, D10).
18. A record left by a failed or killed `update` made a later `update` restore a store that had since been set aside by hand. A run that fails before `adopt` deletes its record, and a record beside a set-aside store or no store is deleted (D10).
19. A kept adoption id beside a set-aside store could be read as that store's id. The rows of D1 read the store's own row only, and `join --set-aside-local` deletes the file (D1, D5).
20. `update` could not go on after its own restore was killed following the install, and the restore asked what was installed with nothing to tell it. `update` finishes that restore first, and the record's commit is always installed again (D10, D11).
21. A read-back after a skipped load compared the hub's members with an old listing and told the PM to empty the hub. The numbers are printed and not compared (D10).
22. `update` run after a hub restore had failed threw away the list that restore needed. `hub-update.sh` finishes the restore first (D10).
23. `restore` and `restore --hub` after the adoption installed a release that could not open the store, or built a hub from a commit with none. With no `previous-commit` they stop and name `restore --local-store` (D10).
