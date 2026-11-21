---
docType: slice-design
slice: hub-and-door
project: amoeba
parent: user/architecture/260-slices.the-hub.md
dependencies:
- 240
interfaces:
- 261
- 262
- 263
- 264
dateCreated: 20261120
dateUpdated: 20261121
status: not_started
turns: 28
promptTokens: 2058924
cachedTokens: 1863532
cacheWriteTokens: 195360
completionTokens: 66917
durationSeconds: 735.4
costUsd: 6.175732
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-fable-5-2:
    rounds: 1
    costUsd: 6.1757324
    completionTokens: 66917
---

# Slice Design: hub-and-door

## Overview

This slice builds the hub: `amoeba hub serve`, one process that holds the store and serves it over an encrypted, authenticated network door. It also builds the client side: `amoeba join` writes a client file, and from then on every call on that machine goes to the hub instead of a local store.

Six operations are served through the door: `decisions`, `mark_read`, `dismiss`, `retract`, `standing` and `withdraw`. Every other operation, on a machine with a client file, fails and says the door does not serve it yet. Slices 261 to 263 widen that list.

The PM's install has no client file, so it keeps running on its local store exactly as today. Everything here is proven with fixtures: one hub and two client homes on one computer.

## Value

Architectural enablement. After this slice there is a hub that stays up, takes its own backups, and that a second machine can join with one command. Both machines already read the same decisions and standing answers. Every later slice in the initiative adds operations to this door and relies on its access control, its repeat rule and its machines.

## Technical Scope

Included:

- `amoeba hub serve`, with `--from-backup`, and its `hub.yaml`.
- The hub's certificate, made at first start.
- Machines, tokens and the owner, in migration 011. `amoeba hub invite`, `amoeba hub machines`, `amoeba hub rm-machine`, `amoeba hub backup`.
- `amoeba join` (with `--address` and `--set-aside-local`) and `amoeba leave`.
- The door: the call format, the door version, the shared network times, the three outcomes, kept results for repeated calls.
- The mode switch, checked on every call, and the guard that keeps a joined machine from opening a local store.
- The six served operations.
- Timed backups, backups before a migration, and the rotating hub log.
- The container image definition and example files.
- A load test, and the two-machine fixture later slices reuse.

Excluded, because the slice plan puts them in later slices:

- Member names, checkouts and the operations that name the caller (261): `add`, `rm`, `inbox`, `reply`, `cancel`, `changes`, `report_release`, `list`, `status`, and `send` for a recipient with no wake to start.
- `answer`, `handle_pause`, `send` with waking, the internal wake command and the work flag (262).
- `amoeba-mcp` sessions through the door, and the session's own calls (263).
- `amoeba adopt`, deleting the local-store way, and the hub set-up page (264).
- What else `rm-machine` must end. Here it ends the token, the machine's session rows and its kept results (D13). 261 adds the machine's checkouts, and 262 adds its open questions, its waiting answers and its wakes. Both extend the one transaction this slice builds.

## Dependencies

### Prerequisites

- Slice 240 and everything before it (complete).
- `cryptography`, `starlette` and `uvicorn` become direct dependencies because this slice's code imports them. All three are already installed through `mcp` (see `uv.lock`), so nothing new is installed.

### Interfaces Required

- `wiring.invoke`, which both the CLI and the MCP server already call for every operation. The mode switch goes here, so both get it.
- `operations/state_move.py`, the single caller of `Store.open` (pinned by `tests/test_store_opened_only_by_state_move.py`). The guard goes here.
- The six operations' existing request documents and result types, unchanged.
- `store/migrations.py`: ordinary numbered migrations.
- `scripts/update_live.py`, which backs up, migrates and reads back the live store at release time.

## Architecture

### Component Structure

Three new packages and additions to five existing ones. The shared package is named `wire`, because `Door` is already the store's name for how a call arrived (CLI or MCP).

| Package | Modules | Holds |
|---|---|---|
| `amoeba.wire` (new) | `times`, `protocol`, `join_line`, `fingerprint` | What the client and the hub must agree on: the door version, the network times, the call and reply shapes, the refusal codes, the served-operation list, the join line format, the certificate fingerprint. |
| `amoeba.client` (new) | `client_file`, `trust`, `call`, `join` | Reading and writing the client file and the saved certificate, the pinned TLS setting, one call with retry, and the network and file steps of `join` and `leave`. |
| `amoeba.hub` (new) | `hub_config`, `certificate`, `backups`, `hub_log`, `calls`, `app`, `serve`, `admin` | `hub.yaml`, the certificate, backups, the log, the handling of one call (a plain function), the web app around it, the start sequence, and the admin commands. |
| `amoeba.store` | `machines`, `sql_machines`, `call_results`, `schema/011_hub_and_door.sql`; changes to `store.py` and `relocate.py` | Machines, the owner, kept results, the call scope, the acting machine, the closed mark, and setting a store aside and putting it back. |
| `amoeba.operations` | `served` (new); small changes to `decisions`, `standing` and `state_move` | One function that runs any of the six served operations, used by both the local way and the hub. The guard and the two store openers. |
| `amoeba.config` | changes to `home` | The new paths. `StateLayout` gains the client file's path. |
| `amoeba` (wiring) | `wiring_door` (new); changes to `wiring`, `wiring_results` | The mode switch, the steps of `join` and `leave` in order, and turning a reply back into a typed result. |
| `amoeba.cli` | `hub_commands`, `join_command`; changes to `parser`, `main` | The new commands. The served check in `main` before `handle-pause` and `wake-run`. |
| `amoeba.mcp` | changes to `server`, `in_process` | The served check at start and before the `answer` deadline check. |

`cli.hub_commands` builds the state layout and hands the hub a store opener bound to it, so the hub never imports `wiring`.

Import rules, added to `tests/test_import_boundaries.py`:

- `wire` imports nothing from any other `amoeba` package. The served names are plain strings in `wire.protocol`, and a test asserts each is an `OperationName` value.
- `client` imports nothing from `store`, `hub` or `upstream`.
- `hub` imports nothing from `client`, `upstream`, `cli`, `mcp` or the `wiring` modules.

### Data Flow

A served call on a joined machine:

1. `wiring.invoke` finds a client file. It checks that the operation is in the served list, before reading anything else local.
2. `client.call` opens a TLS connection that trusts only the saved certificate, and posts the call with the token and a new call id. If no reply comes it repeats the same call with the same id until the retry time is over.
3. On the hub, the web app reads the request and hands it to `hub.calls.handle_call` in a worker thread. That function opens its own store connection, checks the token, and runs the operation and the kept-result write in one transaction (D8, D9).
4. The reply comes back as JSON. `wiring_results.result_from_document` turns it into the same typed result the local way returns, so the CLI's renderers and exit codes and the MCP server's result documents are unchanged.

With no client file, `wiring.invoke` runs as today. The six operations go through the same `operations.served.run_served` function the hub uses, with today's `cf`-backed readers.

### State Management

| State | Where | Ends by |
|---|---|---|
| Machines and token hashes | Store, `machines` | `amoeba hub rm-machine`; a token alone by `amoeba hub invite` for the same name |
| The owner | Store, `owners`, one row | Never; it is the store's owner |
| Kept results | Store, `call_results` | Deleted by the next call once older than the fixed lifetime (D9) |
| The hub's certificate and key | Hub state directory | Never replaced. They travel in every backup |
| Backups | `backup_dir`, two rotations | Rotation to `backups_kept` in each kind (D15) |
| The hub log | Hub state directory, `logs/hub/` | Rotation by size to `hub_logs_kept` files (D16) |
| The client file | Client config directory | Overwritten by `amoeba join`; removed by `amoeba leave` |
| The saved hub certificate | Client state directory | Overwritten by `amoeba join`; removed by `amoeba leave` |
| A set-aside local store | Client state directory | Put back by `amoeba leave`. At most one exists (D4) |

Config is `hub.yaml`, `config.yaml` and the client file. Everything the system writes for itself is in a state directory, except backups (D1).

## Technical Decisions

### D1 — Where files live
Status: decided

All paths come from `config/home.py`, which stays the only reader of `AMOEBA_HOME`.

- Client, config directory: `client.yaml`. `join` writes it, but it stays config: the architecture puts it there, and it is the one file that says which hub this machine uses, which a person may read and change.
- Client, state directory: `pinned-hub-cert.pem`. `join` writes it and nobody edits it, so it is state.
- Hub, config directory: `hub.yaml` and `config.yaml`.
- Hub, state directory: `amoeba.sqlite3` (the same store path as today, so a hub's store and a laptop's store are the same kind of file), `hub-cert.pem`, `hub-key.pem`, `logs/hub/hub.log`.
- Hub backups: `backup_dir` from `hub.yaml`. This is the one piece of state outside the state directory. The architecture requires it to be configurable so it can be on a different disk from the store it protects.

A hub home and a client home are always different directories. A single-machine user runs the hub in its container, whose directories are its own mounts. The guard in D2 enforces this: hub commands refuse in a home that holds a client file.

### D2 — The mode switch and the guard
Status: decided

`wiring_door.joined()` returns the loaded client file, or nothing when the file does not exist. It is called on every call and never cached. 264 deletes the local way, and from then `joined()` raises `NotJoinedError` when there is no client file (264 D6). With a client file, it also checks the saved certificate is there (D3).

With a client file, the served check is the first line of every entry point. Nothing local is read or written before it: no `config.yaml`, no store, no state move, no log line.

This table is the state after 260. Each later slice serves more of it, and 263 moves the `answer` deadline check to the hub. After 263 nothing is left unserved, so 263 deletes `NotServedError` and the client's served check (263 D14). The hub keeps its own check and its `not_served` refusal.

| Entry point | With a client file |
|---|---|
| `wiring.invoke`, a served operation | Goes to the hub |
| `wiring.invoke`, any other operation | `NotServedError` |
| `amoeba handle-pause`, `amoeba wake-run` | `NotServedError`, raised in `cli.main` before the layout is built and before the config is loaded. No calls-log line is written |
| `amoeba-mcp` start | `NotServedError`, before the state move and the config load |
| `amoeba-mcp` tool call | Through `wiring.invoke`, as above. The `answer` deadline check, which reads the local config, runs only with no client file |
| `amoeba hub ...` | `LocalStoreClosedError`, checked on the first line of each hub command, before `hub.yaml` is read or any file is written |
| `amoeba join`, `amoeba leave` | Run. Neither goes through `joined()`. `join` reads the existing client file only for `--address`. `leave` works with any of the files missing (D4) |

`NotServedError` says: this machine is joined to the hub at `<address>`, and the door does not serve `<name>` yet. It joins `OPERATIONAL_ERRORS`, so the CLI exits 3 and MCP returns an error result.

The guard: both store openers and `prepare_state_home` raise `LocalStoreClosedError` when the layout's client file exists. The message names the hub's address. It is a `StoreError`, so every existing handler already deals with it. 264 deletes the local opener and `prepare_state_home`, and the guard with them. The one local opener it leaves, `store.handover`, never creates a store (264 D5, D7).

This is what covers an `amoeba-mcp` that was running before the machine joined: its next tick fails in its existing store-error handler, presence and push stop with a log line, and its tools keep serving through `wiring.invoke`. No store file is opened or created. Push stopping without a message to the agent is acceptable in 260 because only fixtures join; 263 makes the tick a hub call.

A test runs every CLI command and every MCP tool, and starts `amoeba-mcp`, in a home that holds only a client file and a saved certificate. It asserts the error type and that no file was created.

### D3 — The client file and the join line
Status: decided

`client.yaml` holds exactly three keys: `address` (`host:port`), `machine` and `token`. It is written through a temporary file and a rename, with mode `0600`.

Loading fails with `ClientFileError`, which joins `OPERATIONAL_ERRORS`, in three cases. Each message names the file:

- Anyone but the owner can read `client.yaml`. The message gives the `chmod 600` command.
- A key is missing or unknown. The message names the key.
- `pinned-hub-cert.pem` is missing or unreadable. The message says to run `amoeba join` again with a new line from `amoeba hub invite`.

The join line is three fields separated by commas, with no spaces, so it needs no shell quoting:

`<address>,<fingerprint>,<token>`

- The address comes from `hub.yaml` (D14).
- The fingerprint is the SHA-256 of the certificate's DER bytes, in hex. The parser accepts upper case and colons.
- The token is `secrets.token_urlsafe(32)`. The hub stores only its SHA-256, which is enough for a random 256-bit value.

The parser strips surrounding whitespace and quotes. A line with the wrong number of fields fails and says what a join line looks like without printing the token.

A machine name matches `[a-z0-9][a-z0-9._-]*`, at most 64 characters. The client learns its name from the `hello` call.

### D4 — `join` and `leave`
Status: decided

`wiring_door` runs the steps in order. `client.join` does the network and file steps. `store.relocate` owns setting a store aside and putting it back.

`amoeba join <line>`:

1. With no client file, runs the pre-228 state move as every command does today, so only the state-home store counts below.
2. If a local store exists, refuses and names `--set-aside-local`. (`amoeba adopt` is named here too once 264 builds it.)
3. Fetches the hub's certificate, waiting at most `CONNECT_SECONDS`. This one connection cannot verify anything, because the client has no certificate yet. It uses a TLS setting with verification off, sends no request bytes, reads the certificate the hub presented and closes. The fingerprint in the line is then compared. Nothing else is done on that connection or with that setting, and the token is first sent in step 4, on the pinned setting of D5.
4. Saves the certificate, then makes one `hello` call with the token over the pinned connection. `hello` returns the machine's name. 264 adds `hub_version`, the hub's package version, to that reply (264 D10).
5. Writes the client file.

What can fail, and what is left behind. None of these is retried by `join`, apart from the retry inside the `hello` call:

| Failure | Error | Left behind |
|---|---|---|
| Step 3: connection refused, timeout, or the peer does not speak TLS | `HubUnreachableError` naming the address and the cause | Nothing |
| Step 3: the fingerprint is not the one in the line | `JoinError` with both fingerprints | Nothing. The token was never sent |
| Step 4: `hello` refused or no reply | The call's own error (D6, D10) | Nothing: the saved certificate is removed, or the previous one put back |

Run on a machine that is already joined, it replaces the client file and certificate after a successful `hello`. That is how a re-invited machine gets its new token.

**Setting a store aside.** `amoeba join <line> --set-aside-local` does the same, and between steps 4 and 5 sets the local store aside. On a plain SQLite connection holding the store's write lock (`BEGIN IMMEDIATE`) it writes the closed mark, naming the hub's address and replacing any mark already there, then checkpoints the write-ahead log, renames the store to `amoeba.sqlite3.set-aside-<UTC stamp>` and removes the two side files. It prints the new path.

The closed mark is one row in a `closed_mark` table (D12). Every write transaction checks it right after taking the lock and, if it is set, rolls back and raises `LocalStoreClosedError` naming the hub. So a command that was already running during the join, and still holds a connection, cannot write into the set-aside file: its next write fails and says where the store went. 264's adopted mark is this same row.

At most one set-aside store exists. If one is already there beside a local store, the command refuses and names both. Amoeba's commands never make that pair: while a set-aside store exists the machine is joined or mid-join, and the guard and the local opener refuse to create a store at the store path. So it comes only from files placed by hand, such as a state-directory backup restored over a joined home. `join` refuses it, names both files and says to run `amoeba leave`, which ends the pair (step 1 below): the hand-placed store is moved to a dated name and the set-aside store goes back. Nothing is deleted. If the command stops after the rename and before the client file is written, the machine has a set-aside store and no store. The local store opener refuses to create a new store in that state and says to run `amoeba leave`. Running the same `join` again also finishes it.

If the command stops after the mark is written and before the rename, the store is still at the store path with the mark, and there is no client file. Local writes fail with `LocalStoreClosedError`, whose message says to run `amoeba leave` or the same `join` again. Either ends it. The mark is written on a plain connection, which does not make the mark check that store writes make, so the re-run `join` rewrites it and goes on. `leave` clears it (step 1).

**`amoeba join --address <address>`** needs an existing client file and changes only the address in it. It makes no hub call.

**`amoeba leave`** makes no hub call, so it works with the hub down. Its steps, each skipped when there is nothing to do:

1. Put the set-aside store back: clear its closed mark and rename it to the store path. If the store path is already taken (only by a file placed by hand, see above), first move that store and any side files it has to `amoeba.sqlite3.displaced-<UTC stamp>` and print the new path. Amoeba never opens a displaced store. It is bounded: one comes only from a hand-placed file, and whoever placed it decides what to do with it. With no set-aside store and a store at the store path that holds the closed mark (a `join` stopped before the rename), clear the mark on a plain connection instead.
2. Delete the client file.
3. Delete the saved certificate.

Step 1 does not go through either store opener, so the guard in D2 does not stop it. `store.relocate` opens the set-aside file by its own path on a plain SQLite connection, as it already does for the copy in the state move, deletes the `closed_mark` row in one transaction, closes the connection and renames the file. The guard covers the openers and the store path; `leave` touches neither until the rename.

If it stops partway, running it again finishes it. After step 1 alone the machine is still joined, because the client file is still there, so nothing opens the restored store until step 2 is done. If it stops between clearing the mark and the rename, the next run finds no mark to clear and does the rename.

This is the exit from the joined state and the undo of `--set-aside-local`. The machine's row on the hub is ended separately by `amoeba hub rm-machine`.

264 changes the set-aside, once no local way exists. A store that is set aside stays at the store path, at the current schema, with the closed mark and a dated backup beside it; it is not renamed. `leave` then deletes only the client file and the certificate and puts no store back, and the set-aside store is ended by `amoeba discard-local` or adopted with `amoeba adopt --again` (264 D5).

- Rejected: leaving the joined state with no command. The only exit would be deleting files by hand.

### D5 — The certificate and the client's connection
Status: decided

At first start the hub makes an EC P-256 key and a self-signed certificate with `cryptography`: common name `amoeba-hub`, valid until `9999-12-31T23:59:59Z`, the X.509 value for "no end date". The key file has mode `0600`.

The hub makes a certificate only on a first start, which is a state directory with no store, no certificate and no key. Two cases look like one and are refused:

- **Part of the state is missing.** The state directory holds the certificate without the key, the key without the certificate, or a store with neither. The hub refuses to start and names the missing file. It never makes a new certificate beside an existing key or store, because a new certificate would lock out every client.
- **The state directory is empty and `backup_dir` holds a complete backup,** of either kind. That is a hub whose state directory was lost, for example a mount that did not come up, and not a first start. A new certificate and an empty store here would lock out every client, and the new hub's backups would rotate the old hub's out. The hub refuses to start, names the newest backup, and gives both ways on: `amoeba hub serve --from-backup <that directory>` to bring the hub back, or, to start a new and empty hub on purpose, set `backup_dir` in `hub.yaml` to an empty directory. Two hubs never share one backup rotation.

Every call uses `http.client.HTTPSConnection` with an `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)` that has `check_hostname = False`, `verify_mode = CERT_REQUIRED` and only the saved certificate loaded as trusted. No system certificates are loaded.

This was tried on the project's Python 3.13.7 on 20261120 and is pinned by `tests/hub/test_trust.py`: the right hub is accepted, and a hub with another certificate fails the handshake having received no request bytes.

A certificate failure is not retried and is not an unknown outcome. The client fails at once with `HubCertificateError`, which joins `OPERATIONAL_ERRORS`. It says the hub at `<address>` did not present the saved certificate, and gives the way on: if the address is wrong, `amoeba join --address`; if the hub was replaced by a new one, `amoeba hub invite <machine>` there and `amoeba join <line>` here.

### D6 — The call format
Status: decided

One call is one `POST /call/<name>`. `<name>` is a served operation's name or `hello`.

Request headers: `Authorization: Bearer <token>`, `Amoeba-Door-Version`, `Amoeba-Client-Version` (the installed package version), `Amoeba-Call-Id` (`uuid4().hex`, made once per call and reused by its repeats). The body is JSON with one key, `document`, the operation's existing request document. Later slices add keys beside `document` (Integration Points). The six documents come from flags or from MCP's JSON, so they are always JSON values. 263's `session_tick` and `session_end` also send four `Amoeba-Session-*` headers (263 D6).

None of the six operations takes the existing `Door` value (CLI or MCP), so the body does not carry it. When 262 serves `answer`, the body gains a `via` key holding that value as the client states it, and the hub records it as today.

A body over `MAX_CALL_BYTES` (1 MiB, a constant in `wire.protocol`) or with no valid length is refused before it is read.

The reply body is JSON:

- Done: `{"outcome": "done", "result": <the operation's result document>}`. A result that is itself a rejection, such as `no_such_question`, is a done call: the hub ran the operation and this is its answer, exactly as today.
- Refused: `{"outcome": "refused", "code": <code>, "message": <text>}`. The hub did not run the operation.

Refusal codes, a `RefusalCode` enum in `wire.protocol`:

| Code | When | HTTP status |
|---|---|---|
| `bad_token` | No token, an unknown token, or a removed or re-invited machine's old token | 401 |
| `door_version` | The client's door version is not the hub's. The message holds both | 426 |
| `malformed_call` | Bad headers, body or size | 400 |
| `not_served` | The name is not in the served list | 404 |
| `call_id_reused` | The call id was kept for a different operation or a different body | 409 |
| `hub_error` | The operation raised one of today's operational errors on the hub, such as a missing `config.yaml` or a busy store. The message is `<ErrorName>: <text>` | 500 |
| `hub_fault` | Anything else was raised on the hub (D8). The message is the exception's type name and says the traceback is in the hub log | 500 |

The client goes by the body, never the status. Any response whose body parses as a reply is an answer. Anything else counts as no reply.

A refused call reaches the caller as `HubRefusedError`, whose text names the hub's address, the code and the message. It joins `OPERATIONAL_ERRORS`. The client adds what to do for two codes:

- `door_version`: both versions and the upgrade command, `uv tool install --force amoeba-ai`.
- `bad_token`: this machine's token is not known to the hub; run `amoeba hub invite <machine>` on the hub and `amoeba join <line>` here. The machine name is the one in the client file.

### D7 — The door version and the network times
Status: decided

`wire.times` holds, each defined once:

| Constant | Value | Meaning |
|---|---|---|
| `DOOR_VERSION` | 1 | The shape of the door |
| `CONNECT_SECONDS` | 3 | Longest wait to connect |
| `READ_SECONDS` | 10 | Longest wait for a reply to one attempt |
| `RETRY_SECONDS` | 30 | A new attempt starts only while less than this has passed since the first |
| `RETRY_PAUSE_SECONDS` | 0.5 | Wait between attempts |
| `CALL_BOUND_SECONDS` | 43 | Worked out: `RETRY_SECONDS + CONNECT_SECONDS + READ_SECONDS`, the longest a call can take |
| `CALL_RESULT_LIFETIME_SECONDS` | 600 | How long the hub keeps a writing call's result |

Why these values: a container restart takes a few seconds, so 30 seconds of retrying rides through one. A hub call waits for the store's lock once (D8), for at most the existing 5-second busy time, so 10 seconds to read covers a hub that is going to answer.

Tests pin three relations: `READ_SECONDS` is above `HUB_LOCK_WAITS_PER_CALL` (1, a constant in `hub.calls`) times the store's busy time; `CALL_RESULT_LIFETIME_SECONDS` is above `CALL_BOUND_SECONDS`; and the pair of `DOOR_VERSION` and the time values equals a pinned tuple, so nobody changes a time without changing the version. 263 adds `MCP_CALL_DEADLINE_SECONDS` to that tuple and raises `DOOR_VERSION` by one (263 D9). 262 raises `DOOR_VERSION` to 2 first, because `send` then returns a wake an older client cannot start (262 D8). So it is 3 after 263. 264 adds two times that only the adoption upload uses; they stay outside the tuple and the version does not change (264 D3).

`client.call` takes the times as a `DoorTimes` value that defaults to these constants. Tests pass shorter ones. There is no setting.

Both sides check the version on every call. The hub refuses a different version with `door_version`. The client also reads `Amoeba-Door-Version` from every reply and raises the same error if it differs.

### D8 — One call is one transaction
Status: decided

`hub.calls.handle_call` runs in a worker thread and opens its own connection with the hub store opener it was given (D12). The steps:

1. **Token, read only.** Look the token's hash up with a plain read, which waits for no lock. A miss is `bad_token`. A scanner therefore never takes the write lock.
2. **Checks that need no store.** The version, the body, the served list, and the config when the operation needs it (`standing` needs `passages_max_chars`). A failure here is remembered, not yet returned.
3. **The call scope.** One `BEGIN IMMEDIATE` transaction, the call's only lock wait:
   - Touch the machine by its token hash: set `last_called_at` (hub time) and `client_version`. No row means the token ended since step 1, by `rm-machine` or a re-invite, and the call is refused as `bad_token`.
   - If step 2 failed, commit the touch and refuse. So `amoeba hub machines` shows the client version of a machine that was refused for its door version. 263 adds `machines.door_version`, which the touch also sets, and on a `door_version` refusal of a tick writes the session's row from the headers (263 D6).
   - Delete expired kept results (D9).
   - For a writing call, look for a kept result and return it if found.
   - Set the acting machine (D12) and run the operation inside a savepoint.
   - For a writing call, insert the kept result.
   - Commit.

**When the operation raises.** `handle_call` is the hub's boundary for a call and never raises to the web app. Its handler rolls the operation's savepoint back, commits the touch, keeps nothing, and then:

- for one of today's operational errors, refuses as `hub_error` and writes the usual one-line refusal to the hub log;
- for any other exception, such as a bug or a trigger's abort, logs it with `logger.exception`, so the traceback is in the hub log, and refuses as `hub_fault`.

A failure outside the call scope, such as the store failing to open, goes through the same handler without the touch.

The operations open their own transactions with `store.write()` and `store.read()`. Inside a call scope those become savepoints: released on a normal exit, rolled back to on an exception. This matters for `standing`, which raises inside its write block to undo an insert that would overflow. The operation code is not changed for this.

`Store.call_scope()` is the new context manager. Outside one, `write()` and `read()` behave as today, apart from the closed-mark check (D4).

- Rejected: writing the kept result in a second transaction after the operation's. A hub killed between the two would apply a repeat twice.

### D9 — Kept results and repeats
Status: decided

Writing calls are `mark_read`, `dismiss`, `retract`, `standing` and `withdraw`. `decisions` and `hello` are reads and keep nothing. The set is `WRITING_CALLS` in `wire.protocol`.

A kept result is one row in `call_results`, keyed by machine and call id, holding the operation name, the SHA-256 of the request body, the reply body and the hub's time. A repeat with the same machine and id gets the stored reply and nothing runs. The same id from another machine is a different key, so it runs as a new call. The same id with a different operation or body is refused as `call_id_reused`.

Cleanup: every call scope first deletes rows older than `CALL_RESULT_LIFETIME_SECONDS`, using an index on the time. When calls stop, what is left is at most the last ten minutes of writing calls, and the next call removes it. `rm-machine` deletes that machine's rows.

### D10 — Retry and unknown
Status: decided

`client.call` makes an attempt, and on no reply (connection refused, timeout, a response that is not a reply) waits `RETRY_PAUSE_SECONDS` and tries again with the same call id, while less than `RETRY_SECONDS` has passed.

When the time is up it raises `HubUnreachableError`, which joins `OPERATIONAL_ERRORS`. The text names the hub's address and how long it tried. For a writing call it adds that the outcome is unknown, in those words, and the operation's advice from `UNKNOWN_ADVICE` in `wire.protocol`.

The architecture's advice is to read the state with `inbox` or `list` before sending again. Neither is served in 260. Each of the five writing operations is compare-and-set, so running it again is itself the read: if the first one was applied, the answer is `unchanged`.

| Operation | Advice | A served read that also shows it |
|---|---|---|
| `mark_read` | Run it again; `unchanged` means it was applied | `decisions`, by its marker |
| `retract` | Run it again; `unchanged` means it was applied | `decisions`, by the record's `retracted_at` |
| `dismiss` | Run it again; `unchanged` means it was applied | None in 260 |
| `standing` | Run it again with the same text; `unchanged` with an id means it was applied | None in 260 |
| `withdraw` | Run it again; `unchanged` means it was applied | None in 260 |

A test asserts every writing call has an advice entry.

### D11 — The served operations and member names
Status: decided

`SERVED_OPERATIONS` in `wire.protocol` is the one list. The client checks it before calling and the hub checks it on arrival.

`operations.served.run_served(name, store, document, edges)` runs any of the six. `edges` is a small frozen dataclass: the clock, a config loader, a names reader and a member resolver. `wiring._dispatch` calls it for these six with today's `cf`-backed readers. The hub calls it with the hub's clock, the hub's `config.yaml` and the two readers below.

Two of the six touch `cf` today, the hub has no `cf`, and a client may ask `cf` only about its own directory. Members get names in 261. Until then the hub uses the architecture's rule for a member with no name: it is named by its id.

- **`decisions`** shows each member's name. On the hub, the names reader gives each listed member its id as its name. `decisions` changes from taking `Deps` to taking a names reader that is handed the listed member ids.
- **`standing` with `member`** resolves a reference to a member id. On the hub, the reference is the member's id, looked up in the store. Any other text is `no_such_member`, as an unknown name is today. `standing` changes from taking the `cf` runner to taking the resolver.

Nothing is sent beside the document, and no client calls `cf` for a served operation. 261 replaces both readers with the store's names.

The hub fixture runs with a `PATH` that has no `cf` and no `sq`, which proves the hub calls neither.

`wiring_results.result_from_document(name, document)` rebuilds the typed result. A test round-trips representative results of all six through `result_document` and back and asserts equality.

### D12 — The schema: migration 011
Status: decided

One migration, `011_hub_and_door.sql`, run by both ways.

- **`owners`**: `owner_id` (integer key), `name` (unique), `created_at`. The migration inserts one row, named `pm`.
- **`machines`**: `machine_id` (integer key, so a later rename touches one row), `name` (unique), `owner_id` (not null), `token_hash` (unique, null for a machine with no token), `created_at`, `last_called_at`, `client_version`.
- **`call_results`**: `machine_id`, `call_id`, `operation`, `request_hash`, `reply`, `recorded_at`; key `(machine_id, call_id)`; index on `recorded_at`. Its owner is its machine's.
- **`closed_mark`**: at most one row, `hub_address` and `closed_at` (D4). Empty in a store that is in use. 264's migration 015 adds `reason`, one of `handed_over` and `loading` (264 D8).
- **`owner_id`** on every table that holds records, twelve in all: `programs`, `members`, `dependency_pairs`, `releases`, `questions`, `answers`, `standing_answers`, `messages`, `deliveries`, `message_rejections`, `sessions`, `wakes`. Added as a nullable column referencing `owners`, then set to the one owner on every existing row. `schema_meta` and `pm_marker` are single fixed rows, not records.
- **`sessions.machine_id`**, referencing `machines`, nullable. See below.

SQLite cannot add a `NOT NULL` column without a default, and a default owner would be a silent fallback. So each of the twelve tables gets a `BEFORE INSERT` trigger that aborts when `owner_id` is null, and `sessions` gets the same for `machine_id`. An insert that forgets the owner fails loudly.

**The acting machine.** Each of the twelve insert statements binds `owner_id`, and the session insert also binds `machine_id`, from the store's acting machine. No operation's signature changes. A store with no acting machine set fails any of those inserts with a `StoreError` that says so. There is no default.

`state_move.py` has two openers, and stays the only caller of `Store.open`:

- **`open_state_store`**, the local way. After opening, it finds the machine named `local`, or creates it with the one owner and no token, and sets it as the acting machine. This is the "one machine standing for the install". It costs one read per open, and one write the first time.
- **`open_hub_store`**, used by `hub serve` and the admin commands. It creates no machine and sets no acting machine. `handle_call` sets it with `store.act_as(machine)` in the call scope, from the token. So a fresh hub store never gets a `local` machine, and a hub call that forgot `act_as` fails on its first insert.

`amoeba hub invite` needs no acting machine. It gives a new machine the store's one owner, read from `owners`, and fails if that table does not hold exactly one row.

264 deletes `state_move.py`. `open_hub_store` moves to `hub/store_open.py`, `open_state_store` goes, and its fix runs once inside `amoeba adopt`. The two callers of `Store.open` are then `hub/store_open.py` and `store/handover.py` (264 D2, D7).

Tests that open a store directly and insert records set the acting machine with the same helper `open_state_store` uses. This is a mechanical change to the shared store fixtures.

**Sessions.** `rm-machine` must remove a machine's session rows, so sessions get their machine here and not in 263. Rows written before the migration have a null machine. They are already stale by the time new code runs, and the existing heartbeat prune removes them.

The migration only adds. It deletes and rebuilds nothing.

### D13 — The admin commands
Status: decided

CLI only, registered like `wake-run` with no `OperationName`. Each takes `-j`. Each checks the guard first (D2).

| Command | Does | Rejected when (exit 1) |
|---|---|---|
| `amoeba hub invite <machine>` | Creates the machine, or gives an existing one a new token, in one transaction. Prints the join line. Needs `hub.yaml` for the address and the certificate for the fingerprint | The name is malformed |
| `amoeba hub machines` | Lists each machine: name, whether it has a token, `last_called_at` and `client_version`. The hub does not store a machine's door version in this slice, so it does not say which machines are behind; 263 adds the column and that display (263 D6) | — |
| `amoeba hub rm-machine <machine>` | One transaction: deletes the machine's session rows, its kept results and the machine. 261 and 262 add to this transaction (Technical Scope) | No such machine |
| `amoeba hub backup` | Takes a timed backup now and prints its path (D15) | — |

### D14 — `hub.yaml` and the start sequence
Status: decided

`hub.yaml` keys, each required, no default in code, unknown keys refused, every problem reported in one pass naming the file and key (the same pattern as `load_user_config`):

| Key | Meaning |
|---|---|
| `bind` | The interface to listen on |
| `port` | The port to listen on |
| `address` | `host:port` that clients are told to connect to, printed in join lines |
| `backup_dir` | Absolute path for backups |
| `backup_hours` | Greater than 0 |
| `backups_kept` | At least 1 |
| `hub_log_max_bytes` | At least 1 |
| `hub_logs_kept` | At least 2, counting the current file |

`amoeba hub serve` starts in this order. Steps 1 to 7 stop the start on failure, with one line on stderr and exit 3:

1. The guard (D2).
2. Load `hub.yaml`.
3. Bind the listening socket. A taken port stops the start here, before anything is written or migrated.
4. With `--from-backup <dir>`: the state directory must hold no store, certificate or key, or the start is refused naming what is there. The backup's three files are copied in.
5. Make the certificate on a first start. Refuse when part of the state is missing, or when the state directory is empty and `backup_dir` holds a backup (D5).
6. Start the log (D16).
7. If a store exists and its schema is behind, take a backup before the migration (D15). Then open the store, which migrates it.
8. Take a timed backup if one is due. A failure here is logged at error level and the start goes on, so a full backup disk does not keep the hub down.
9. Serve on the socket from step 3.

While serving, one task wakes every `BACKUP_CHECK_SECONDS` (300, a constant) and runs the timed-backup check in a worker thread. A failed backup is logged at error level and tried again at the next check.

The web app is one Starlette route. Its handler reads the body and calls `handle_call` through `anyio.to_thread.run_sync`, so no store call runs on the event loop. `uvicorn` serves it on the bound socket with the certificate and key, with its own access log off and its own logging set-up off (`log_config=None`), so what it logs goes where D16 says.

**A peer that stalls.** Nothing here adds a timeout or a connection cap of the hub's own, and this is what bounds a slow or silent peer:

- A peer that does not finish the TLS handshake is closed by `asyncio` after its handshake timeout, 60 seconds by default.
- A peer that finishes the handshake and then sends nothing, or sends its headers or body slowly, holds one socket and nothing else: no worker thread, no store connection and no lock, because `handle_call` starts only when the whole body has arrived. `uvicorn` 0.54 has no timeout for a first request, and its `limit_concurrency` only answers 503 to every caller once that many connections are open, which would turn stalled peers into refused clients. So it is not set.
- The limit is the process's open-file limit. When it is hit, `asyncio` cannot accept new connections, logs that once a second to the hub log, and keeps trying. Calls on connections already open still complete. A client that cannot connect sees no reply, retries, and fails with `HubUnreachableError` after the retry time (D10). The way out is restarting the hub, which drops every connection: `docker restart`, or the container's own restart. Nothing in the store is affected.
- Calls that have arrived wait for one of `anyio`'s 40 worker threads. One call holds a thread for at most the store's busy time plus the operation. A call that waits longer than the client's `READ_SECONDS` is repeated by the client under the same id (D9).

The hub listens on a LAN, where a peer that opens connections until the file limit is hit is not expected. An idle timeout for connections would mean replacing `uvicorn`'s protocol class, so the case gets a stated limit and a way out, not a mechanism.

### D15 — Backups
Status: decided

A backup is a directory holding `amoeba.sqlite3` (made with SQLite's backup call on its own connection), `hub-cert.pem` and `hub-key.pem`. Directories are `0700` and files `0600`, because a backup holds the key and the token hashes.

- Timed: `<backup_dir>/timed/<UTC stamp>/`. Taken when there is none or the newest is older than `backup_hours`.
- Before a migration: `<backup_dir>/pre-migration/<UTC stamp>-v<schema version before>/`.

Each is written under a `.partial-` name and renamed when complete, so a crash mid-copy never counts as the newest. Partial directories are bounded to one:

- An attempt that fails deletes its own partial directory before it reports the failure.
- Every attempt starts by deleting any partial directory left by a crash, before it copies anything.

After a successful backup, that kind's directories beyond the newest `backups_kept` are deleted. The two kinds rotate separately.

`amoeba hub backup` writes into the timed rotation. It is safe while the hub is serving.

If the backup before a migration cannot be written, the start stops there and the store is not migrated.

### D16 — The hub log
Status: decided

`logging.handlers.RotatingFileHandler` on `logs/hub/hub.log`, with `maxBytes = hub_log_max_bytes` and `backupCount = hub_logs_kept - 1`.

The serving process logs to this file only. Stderr gets start-up failures and one line saying it is serving. The container runtime keeps stdout and stderr without a size limit by default, so sending refused calls there would let a scanner fill the disk.

That covers the libraries' own messages too, which a peer can cause without a token: `uvicorn` logs a malformed HTTP request on the `uvicorn.error` logger, and `asyncio` logs a failed handshake or a failed accept on the `asyncio` logger. The handler is put on the root logger, and `uvicorn` is started with `log_config=None` (D14) so it installs no stderr handler of its own. Both loggers pass their records up to the root, so those lines land in the hub log and rotate with it. Because the root logger has a handler, Python's last-resort stderr handler is never used.

A test sends the fixture hub random bytes, a plaintext HTTP request on the TLS port, and a malformed HTTP request inside TLS, many times each. It asserts the hub's stderr holds only the serving line, stdout is empty, and the hub log holds no more than `hub_logs_kept` files.

A refused call is one line: the hub's time, the caller's address, the code, and the machine's name when the token was good. Never the token, the body or the document. A `hub_fault` also has its traceback (D8).

### D17 — The container
Status: decided

- `docker/Dockerfile`: `python:3.13-slim`, installs Amoeba from the checkout, runs as a non-root user `amoeba`, declares the config, state and backup directories as volumes at that user's default config and state paths and at `/backups`, and has `amoeba hub serve` as its entry point. `AMOEBA_HOME` is not set.
- `docker/compose.example.yaml`: the three mounts, the published port and `restart: always`, which is what starts the hub at boot and restarts it on failure.
- Two examples in the image at `/usr/share/amoeba/`: `hub.yaml.example`, which is `src/amoeba/hub/hub.yaml.example` from the wheel, and `config-contract.md`, copied from `docs/`, whose example block is the `config.yaml` example. The contract stays the one source of that example. A test loads `hub.yaml.example` as a valid hub config.
- 264 changes two of these. The config mount is writable, because adoption writes `config.yaml` there. And `config.yaml.example`, a file in the wheel beside `hub.yaml.example`, becomes the source of the `config.yaml` example, with the contract's block tested equal to it (264 D3, D10).

Admin commands run with `docker exec`.

### D18 — Tests and the fixture
Status: decided

- **Unit.** `handle_call` is a plain function, tested against a throwaway store with no network.
- **In-process hub.** A helper runs the real app with `uvicorn` in a thread on `127.0.0.1` and a free port, with a real certificate. Client tests call it over real TLS.
- **The fault seam.** `handle_call` takes a `DoorHooks` value with an `after_commit` hook, the same pattern as the state move's `MoveHooks`. Production passes none. The repeat test's hook drops the reply after the commit; the test then stops that server, starts a new one on the same store, and repeats the call. This is the exact case of the plan's "killed between the commit and the reply": the commit is on disk, no reply left the hub, and a new server serves the repeat.
- **The kill test.** The same criterion with a real process death, on the two-machine fixture. A client thread makes a `standing` call with the normal retry. The test polls `call_results` on a read-only connection until the row is there, kills the hub with `SIGKILL` and starts it again. The call returns `given`, from the first reply or from a retry. The test then repeats the call under the same id and gets the same result, and the store holds one standing answer. Whichever side of the reply the kill lands on, the assertions are the same, so timing cannot fail it. No hook is needed in the child.
- **The two-machine fixture,** `tests/hub_fixture.py`: starts `amoeba hub serve` as a subprocess on a hub home, invites two machines with the real CLI, and joins two client homes with `amoeba join`. It can stop, kill and restart the hub. While the hub is stopped, a test can seed the hub's store with the store's own functions, as `tests/store/seed.py` does: a program, members, questions and answers. `add` and `handle_pause` are not served yet, so this is the only way records get there. Names need no `cf` (D11). Later slices reuse the fixture. It spends nothing, so it runs in the normal tier and in CI.
- **Load,** `tests/load/test_door_load.py`: 16 client threads against the fixture hub, half reading `decisions` over a store seeded with 500 answers, half writing (`standing`, `withdraw`, `mark_read`). It asserts no call is refused or unknown and every call finishes within 2 seconds. A second case makes 100 calls from one thread against the idle hub and asserts a median under 200 ms. The measured figures go in the slice notes.

### D19 — Documents and the live store
Status: decided

This slice documents what it changes:

- `docs/store-contract.md`: the four tables, `owner_id`, `sessions.machine_id`. `tests/test_contract_docs.py` pins this.
- `docs/cli-contract.md`: `amoeba hub ...`, `amoeba join`, `amoeba leave`, and the new errors.
- `docs/config-contract.md`: `hub.yaml` and the client file.
- `docs/mcp-server.md`: on a joined machine `amoeba-mcp` does not start, and a running one's tools go through the door.
- `docs/squadron-hook.md`: on a joined machine `handle-pause` fails with `NotServedError` and writes no calls-log line.

The call format has no document of its own. D6 to D10 are its one source until 264 writes the hub set-up page.

The live store is not migrated when this slice merges. It is migrated by `scripts/update_live.py update`, which the release skill runs as the last step of a release (`.claude/skills/release/SKILL.md`). What that script does to the live store, as it is today:

- **Backup first.** Before anything changes it copies the store, with SQLite's backup call, and `config.yaml` into `<state home>/backups/<UTC stamp>/`, with the commit that was installed. For the PM's install that is `~/.local/state/amoeba/backups/<stamp>/`. The script already does this; this slice does not add it.
- **Migrate and read back.** It installs the release, runs `amoeba list`, which migrates the store, and checks the schema version, integrity, foreign keys, the member count and the MCP tool list.
- **A failed read-back restores by itself.** The script puts the backup's store and config back, reinstalls the commit that was installed before, and exits 1.
- **One backup is kept.** A successful update deletes the older backup directories.
- **The restore path** is `uv run python scripts/update_live.py restore`. It puts the newest backup's store and config back and reinstalls the commit recorded in it. Everything recorded after the update is lost. The slice notes record this command and the backup directory.

This slice changes the script in three small ways. It adds two read-back checks: `owners` holds one row, and after the `amoeba list` the script runs, `machines` holds the one `local` row. It corrects the docstring, which says to run the script after a slice merges. And a test runs `update` and `restore` against a copy of a schema-10 store in a throwaway home. No config key is added to `config.yaml`. 264 replaces the script's local-store backup and read-back checks: from its release the script updates the hub first, then the client, and on its first run adopts the local store (264 D10).

### Departures from the parent documents

| Parent says | This design | Why |
|---|---|---|
| `hub.yaml` holds the port, the backup keys and the log limits | Adds `bind` and `address` | `invite` must print an address, and a container does not know its LAN name. Fixtures must listen on loopback, or macOS asks to allow incoming connections on every test run |
| The door adds no new server dependency | `starlette` and `uvicorn` are declared | Hub code imports them. Nothing new is installed |
| The saved certificate is beside the client file in the config directory | It is in the client's state directory | The system writes it and nobody edits it. State never lives in the config directory |
| The client's connection never turns checking off and compares afterwards | The one certificate fetch in `join` does (D4) | There is no certificate to check against yet. No request bytes and no token go over that connection |
| No command leaves the joined state | `amoeba leave` | Every state needs an exit that is not deleting files |
| Unknown tells the caller to read the state with `inbox` or `list` | For the five writing operations here, the advice is to run the command again (D10) | Neither read is served in 260, and each of the five answers `unchanged` when it was already applied |
| Kept results are deleted by the sweep | Deleted at the start of every call scope | The hourly sweep runs only from operations this slice does not serve |
| 263's migration adds the machine to a session row | 260 adds it | `rm-machine` removes a machine's sessions in this slice. The 263 plan entry is updated |
| The migration gives the local store its one machine | The local store opener creates it | A migration that made it would also put a `local` machine in every fresh hub store |
| The hub creates the owner when it first starts | The migration creates it | Both ways run the same migration, and a hub's first start is when its store is migrated |
| `join` names `amoeba adopt` when a local store exists | Names only `--set-aside-local` until 264 | `adopt` does not exist yet |
| A member's name is its Context Forge project name | Through the door, until 261, a member is named and referred to by its id | The hub has no `cf`, a client may ask `cf` only about its own directory, and names arrive in 261. This is the architecture's rule for a member with no name |
| `docs/mcp-server.md` and `docs/squadron-hook.md` are brought in line in 264 | Their joined-machine behavior is documented here | This slice changes it |
| Criterion: the hub is killed between the commit and the reply | Tested two ways (D18): a dropped reply and a new server on the same store, and a real hub process killed once the kept result is on disk | The first hits the exact moment every time. The second is a real kill, which cannot be aimed at that moment |
| Architecture, Owner: eight kinds of record hold their owner (programs, members, questions, answers, standing answers, messages, sessions, wakes) | Twelve tables do: those eight and `dependency_pairs`, `releases`, `deliveries`, `message_rejections` (D12) | The architecture's description and the plan both say every record, and these four tables hold records |
| Amoeba rule: databases and run records live in the state directory | Hub backups live in `backup_dir`, a required `hub.yaml` key with no default, outside the state directory (D1) | The architecture requires backups to be able to sit on another disk from the store they protect. A backup on the store's own disk is lost with it |
| The certificate is made at first start | A start on an empty state directory is refused when `backup_dir` holds a backup (D5) | That is a lost state directory. A new certificate would lock out every client while the backup that restores the hub sits unused |
## Implementation Details

### API Contracts

The door is specified in D6, D7 and D9. Commands this slice adds:

```
amoeba hub serve [--from-backup <backup dir>]
amoeba hub invite <machine> [-j]
amoeba hub machines [-j]
amoeba hub rm-machine <machine> [-j]
amoeba hub backup [-j]
amoeba join <line> [--set-aside-local] [-j]
amoeba join --address <host:port> [-j]
amoeba leave [-j]
```

Exit codes are today's: 0 done, 1 rejected, 2 usage, 3 error.

### Database / Storage Schema

Migration 011 as in D12. `EXPECTED_SCHEMA_VERSION` becomes 11. The store contract and `tests/store/test_migration_011.py` cover: the one owner row, every existing row's `owner_id` set, the triggers refusing a null, no machine made by the migration, an empty `closed_mark`, and a schema-10 fixture's row counts unchanged.

### Migration Plan

Nothing moves. Two functions change what they take (`decisions`, `standing`, D11) and their two callers are updated in the same task. `wiring._dispatch` sends the six served operations through `run_served`. With no client file, behavior is identical, and the existing suite is the proof.

## Integration Points

### Provides to Other Slices

- **The door.** 261, 262 and 263 add names to `SERVED_OPERATIONS` and a case to `run_served` or their own hub-side function. A call that needs values only the client can read adds a key beside `document`. An added call or field does not change the door version.
- **The call scope.** Any operation run inside it is one transaction with its kept result, however many transaction blocks it has today.
- **Machines and the acting machine.** 261's checkouts reference `machines`. 263's session rows already carry their machine.
- **The mode switch and `NotServedError`.** A later slice serves an entry point by removing its row from the table in D2.
- **The closed mark,** which 264's adoption sets.
- **The fixture** in `tests/hub_fixture.py` and the load test, which 263 extends.
- **Backups and `--from-backup`,** which 264 uses for moving and undoing the hub.

**What later slices change here.** 263's changes to this design are stated where they apply: the entry-point table and `NotServedError` (D2), the session headers (D6), the pinned tuple and the door version (D7), and the touch and `machines.door_version` (D8, D13). They are listed in 263's "Amendments to 260 and 262". 264's are stated the same way: `joined()` and the guard (D2), the set-aside store and `leave` (D4), `hello`'s reply (D4), the upload's two times (D7), `closed_mark.reason` and the two openers (D12), the config mount and the example's source (D17), and the release script (D19). They are listed in 264's "Amendments to 260 and 263".

### Consumes from Other Slices

Nothing beyond the complete slices. The six operations and their documents are used as they are.

## Success Criteria

### Functional Requirements

- With the fixture hub and two client homes, a `standing` given from the first machine is read from the second two ways:
  - `standing` with the same text from the second answers `unchanged` with the first's id.
  - With the hub stopped, the test seeds an answer that cites `standing:<id>`. After a restart, `decisions` from the second machine shows that record citing it.
- `withdraw` from the second withdraws it, and `withdraw` from the first then answers `unchanged`.
- `decisions` from both shows the same records, each member named by its id, and `mark_read` from one moves the marker the other reads.
- `standing --member <id>` for a seeded member works through the door, and any other reference is `no_such_member`. The hub's `PATH` holds no `cf`, and no client calls `cf` for a served operation.
- A call to a hub with a different certificate fails in the handshake with `HubCertificateError`, and that hub receives no request bytes. `join` with a wrong fingerprint fails with `JoinError` after the fetch, having sent no request bytes, and saves nothing. `join` against an address nothing listens on saves nothing.
- A client file with no saved certificate fails every call with `ClientFileError` naming the file, and `leave` still works.
- A call with no token, a bad token, a removed machine's token or a re-invited machine's old token is refused as `bad_token`, and each is a line in the hub log without the token. The client's error names the two commands to come back.
- A writing call repeated with the same id returns the first result and applies once, including when the reply is dropped after the commit and the hub is restarted, and when the hub process is killed once the kept result is on disk. The same id from the other machine runs as a new call.
- An operation that raises a non-operational exception on the hub is refused as `hub_fault`, the traceback is in the hub log, nothing of the operation is stored, and the hub serves the next call.
- With the hub stopped, a call fails after the retry time with the hub's address in the error, and a writing call's error says the outcome is unknown.
- With no client file, the same commands run on the local store, and every existing test passes.
- With a client file, every unserved command and tool, `amoeba-mcp` start and every hub command fail with their error from D2, and no local file is created.
- A client with a different door version gets both versions and the upgrade command, and `hub machines` shows the client version and call time of that refused call.
- A hub restarted five times in a row takes no new timed backup. A hub started with `--from-backup` on a new state directory accepts both clients with no new invite.
- `rm-machine` and a re-invite each end the old token on the very next call.
- A half certificate pair, a store with no certificate, a bad `hub.yaml` key and an unwritable `backup_dir` before a migration each stop the start and name the problem. A taken port stops it with the store not migrated and no file written.
- An empty state directory beside a `backup_dir` that holds a backup stops the start, names the newest backup and gives the `--from-backup` command, and no certificate or store is made. The same start with `backup_dir` set to an empty directory succeeds as a first start.
- Random bytes, plaintext HTTP on the TLS port and malformed HTTP inside TLS, sent many times, leave the hub's stderr with only the serving line and its stdout empty, and the hub log inside its keep count. The hub serves the next call.
- With an unwritable `backup_dir` and no migration due, the hub starts and serves, and the failure is in the log. A backup that fails partway leaves no partial directory.
- After more backups and more log than the keep counts allow, each kind of backup holds `backups_kept` directories and the log holds `hub_logs_kept` files.
- `join --set-aside-local` followed by `leave` puts the local store back with its rows and leaves no set-aside file, and the next command writes to that store, so its closed mark is gone. A connection opened before the set-aside fails its next write with `LocalStoreClosedError` naming the hub. `leave` stopped after any step is finished by running it again.
- A hub call that sets no acting machine fails on its first insert, and the hub store holds no `local` machine after the full fixture run.
- `scripts/update_live.py update` and `restore` pass against a copy of a schema-10 store.

### Technical Requirements

- `ruff`, `pyright` strict and the full `pytest` run pass.
- The import rules in Component Structure are tested.
- The load test passes its two bounds (D18), with the measured figures in the slice notes.
- New source files stay near 300 lines.
- The five documents in D19 are updated and `tests/test_contract_docs.py` passes.

### Integration Requirements

- 261 can serve a new operation by adding to the served list and `run_served`, with no change to the call format.
- The PM's install, with no client file, behaves as before the slice.

### Verification Walkthrough

Draft; refined after implementation. None of these commands exist yet.

Each functional criterion above has a test on the two-machine fixture, under `tests/hub/`, and running them is the demonstration:

```bash
uv run pytest tests/hub tests/load/test_door_load.py
```

The container is the one thing the suite does not run. The implementing agent does this once and records the output in the slice notes:

```bash
docker build -f docker/Dockerfile -t amoeba-hub .
```

Start it with the mounts from `docker/compose.example.yaml`, with `hub.yaml` copied from `/usr/share/amoeba/hub.yaml.example` and `config.yaml` written from the example in `/usr/share/amoeba/config-contract.md`. `docker exec <container> amoeba hub invite alpha` prints a join line, `amoeba join <line>` in a throwaway home succeeds, and `amoeba standing --text "..." -j` from that home answers `given`.

## Risk Assessment

### Technical Risks

- **The call scope changes how transactions nest.** A mistake in the savepoint handling could commit a row an operation meant to roll back.
- **The acting machine touches twelve insert paths and the store tests' fixtures.** A missed one fails every insert into that table.
- **Access control is new code that everything later trusts.**

### Mitigation Strategies

- The call scope is tested with the existing fault injection (`tests/fault_injection.py`) for each of the five writing operations, including `standing`'s overflow path, asserting nothing is left behind.
- The triggers and the missing-acting-machine error make a missed owner a loud failure in the first test that inserts, and the existing suite inserts into all twelve tables.
- The pinned-certificate behavior was tried before design (D5) and is pinned by a test that asserts the wrong hub received no request bytes. Token refusal has one test per case in the criteria.

## Implementation Notes

### Special Considerations

- **Security.** The token and the hub's key never appear in a log line, an error text or a result. `invite` prints the token once, in the join line. Backups hold the key, so their permissions are part of the backup test.
- **Threads.** Each call has its own connection and shares no mutable state with another. The only state crossing threads is the store itself, ordered by SQLite's lock as today.
- **The hub's `PATH`.** The fixture hub runs without `cf` and `sq`, so an accidental hub-side call to either fails a test.

## Operator Walkthrough

Done as the person running it. Before 264 the PM's own install is not joined; this is a hub run for the fixture or for trying it out.

- **Start.** Write `hub.yaml` and `config.yaml` in the hub's config directory from the two examples the image ships, start the hub, `hub invite <machine>` for each machine, `join <line>` on each.
- **`hub.yaml` is wrong.** The start stops and names every bad key. Fix the file and start again.
- **The port is taken.** The start stops and names it. Nothing was migrated or written.
- **`backup_dir` cannot be written.** With a migration due, the start stops and names it. Otherwise the hub serves and the hub log has the failure at each check.
- **Normal path.** `standing`, `withdraw`, `decisions`, `mark-read`, `dismiss` and `retract` work from every joined machine on one store. Members show by their ids until 261. Any other command says the door does not serve it yet.
- **`join` on a machine with a local store.** Refused, naming `--set-aside-local`. With that flag the store is renamed and its path printed. `amoeba leave` puts it back. A command that was running during the join fails its next write and names the hub.
- **`join` with a line from a different hub, a mistyped line, or no hub at that address.** The fingerprint does not match, the line does not parse, or the error names the address. Nothing is saved.
- **The saved certificate is gone.** Every call names the missing file and says to join again. `leave` still works.
- **The hub presents a different certificate.** The call fails at once and gives the two ways on: `join --address` if the address is wrong, or a new invite and `join` if the hub was replaced.
- **The hub goes down.** Calls fail after about 30 seconds naming the address. A writing call says its outcome is unknown and that running it again shows whether it was applied. The container restarts the hub; nothing needs doing on the clients.
- **A reply is lost.** The client's repeat gets the first result.
- **A call hits a bug on the hub.** It is refused as `hub_fault`, the traceback is in the hub log, and the hub keeps serving.
- **A token leaks.** `hub invite <machine>` again, then `join` with the new line on that machine. The old token stops working at once.
- **A machine is retired.** `hub rm-machine <machine>`. Its next call is refused as `bad_token`, and the error names `hub invite` and `join` as the way back.
- **The client is a different door version.** It prints both versions and the upgrade command. `hub machines` shows each machine's client version and when it last called; which machines are behind is shown from 263 on.
- **The hub's state directory is lost,** so the hub finds it empty: a mount that did not come up, or a replaced disk. With a backup in `backup_dir`, the start refuses, names the newest backup and prints the command. Start with `--from-backup <dir>`, and clients connect as before. With no backup at all, this is a first start: the hub makes a new certificate and an empty store, every client's call fails with `HubCertificateError`, which names the two commands, and each machine is invited and joined again. The old store's records are not carried over, which is the cost of having run with no working backup.
- **The state directory is damaged: the key or certificate alone is missing, or the store has neither.** The start refuses and names the missing file. Start with `--from-backup <dir>` on a new, empty state directory, and clients connect as before. With no backup at all, a new, empty state directory is a first start, as above.
- **Starting a new, empty hub on purpose where an old hub's backups are.** Refused, as a lost state directory is. Set `backup_dir` in `hub.yaml` to an empty directory and start again. The old backups stay where they were.
- **A scanner or a stalled peer.** Refused calls and malformed requests are lines in the hub log, which rotates; nothing goes to stderr. A peer that holds connections open costs one socket each. If the open-file limit is ever hit, clients fail with the hub's address after the retry time and the hub log says why; restarting the hub clears it.
- **The hub moves to a new address.** `join --address` on each machine.
- **`leave` or `join --set-aside-local` stops partway.** Run the same command again. A `join` stopped before the rename can also be ended with `leave`. Until then no command creates a second store.
- **Undo.** On a client, `amoeba leave`. On the hub, stop the container; its directories are everything it wrote.

Dead ends found by the task review, and how each is resolved:

- A `join --set-aside-local` re-run after a stop between the rename and the client file was refused by the task text. It now skips the set-aside and finishes (D4), as this walkthrough says.
- A `join --set-aside-local` stopped after the closed mark and before the rename left a marked store that neither `leave` nor a re-run `join` ended. The mark is now written on a plain connection, so the re-run goes on, and `leave` clears a mark on the store path (D4).
- A local store beside a set-aside store had no command that ended it. Amoeba's commands never make that pair; it comes only from files placed by hand. `leave` now ends it: it moves the hand-placed store to a dated `displaced-` name, prints it and puts the set-aside store back, deleting nothing (D4).
