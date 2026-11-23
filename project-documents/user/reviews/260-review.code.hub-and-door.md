---
docType: review
layer: project
reviewType: code
slice: hub-and-door
conventionsSource: AGENTS.md
projectRules: [general.md, python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/slices/260-slice.hub-and-door.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261122
dateUpdated: 20261122
reviewedSha: f9bb63f04fcf4149be0a33eb7e23a9bd95ecc83b
reviewedBlob: bf6dba5372b4b72795ea2f9c17be7ab0b1e4e56b
reviewedBlobCurrent: true
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 23
injected:
  - key: conventions
    path: "AGENTS.md"
    chars: 24525
    sha256: 2387512002bb2a73aa247bc36bc98d7162c5b5110ded41f56319d098d282ddbc
    whole: true
filesRead:
  - "pyproject.toml"
  - "src/amoeba/hub/restore.py"
  - "src/amoeba/store/store.py"
  - "src/amoeba/cli/hub_commands.py"
searches:
  - "list_files docker/* in ."
  - "list_files docs/*.md in ."
  - "list_files .claude/skills/release/SKILL.md in ."
  - "grep owners|call_results|closed_mark|machines in /Users/manta/source/repos/manta/amoeba/docs"
  - "grep hub_logs_kept|backup_hours|client\\.yaml|hub\\.yaml|machine in /Users/manta/source/repos/manta/amoeba/docs/config-contract.md"
  - "grep MCP_CALL_DEADLINE_SECONDS\\s*[:=]|CLI_ONLY_COMMANDS|def check_deadline|timeout_advice in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep until 261|261 in /Users/manta/source/repos/manta/amoeba/project-documents"
  - "grep `(bind|port|address|backup_dir|backup_hours|backups_kept|hub_log_max_bytes|hub_logs_kept|machine|token)` in /Users/manta/source/repos/manta/amoeba/docs/config-contract.md"
  - "grep owners|call_results|closed_mark|owner_id|machine_id in /Users/manta/source/repos/manta/amoeba/docs/store-contract.md"
  - "grep D11|260 D|slice 260|hub-and-door in /Users/manta/source/repos/manta/amoeba/project-documents/user"
  - "grep migrate\\(|def open\\(|def act_as|CLI_ONLY_COMMANDS in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep 261 in /Users/manta/source/repos/manta/amoeba/project-documents/user/slices/260-slice.hub-and-door.md"
  - "grep def _displace|displaced = Path|store_path.rename\\(displaced\\)|STAMP_FORMAT: Final|def _stamp|if layout.client_file.exists\\(\\)|def remove_machine|DELETE_MACHINE_SESSIONS, \\(name|BackupSource\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep except |EXIT_ERROR\\b in /Users/manta/source/repos/manta/amoeba/src/amoeba/cli/main.py"
  - "grep update_live in /Users/manta/source/repos/manta/amoeba/.claude/skills/release/SKILL.md"
  - "grep except \\(OSError, http\\.client\\.HTTPException\\)|except ssl\\.SSLCertVerificationError in /Users/manta/source/repos/manta/amoeba/src/amoeba/client/call.py"
  - "grep client\\.yaml.{0,200}(config|state)|(config|state) home.{0,120}client in /Users/manta/source/repos/manta/amoeba/project-documents/user/slices/260-slice.hub-and-door.md"
  - "grep class OperationName|def cli_name|def value in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/names.py"
diffTruncated: false
effort: xhigh
turns: 24
promptTokens: 3724707
cachedTokens: 3344894
cacheWriteTokens: 379793
completionTokens: 80105
durationSeconds: 362.2
costUsd: 0.895284
costBasis: provider
runId: run-20261122-p6-be735421
squadronVersion: 0.24.37
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Relative `--from-backup` path crashes with a traceback instead of a refusal"
    location: "src/amoeba/hub/restore.py:66"
  - id: F002
    severity: concern
    category: correctness
    summary: "Hub commands act on a laptop's local store, and `rm-machine local` deletes its machine row"
    location: "src/amoeba/cli/hub_commands.py:179 and src/amoeba/hub/store_open.py:28"
  - id: F003
    severity: concern
    category: other
    summary: "Member names are deferred to slice 261, which the project's no-deferral rule forbids"
    location: "src/amoeba/operations/served.py#id_names"
  - id: F004
    severity: note
    category: correctness
    summary: "Displacing a hand-placed store can overwrite an earlier displaced store"
    location: "src/amoeba/store/set_aside.py:203–209"
  - id: F005
    severity: note
    category: consistency-rot
    summary: "Timestamp format constant is defined three times with different precision"
    location: "src/amoeba/store/set_aside.py:28"
  - id: F006
    severity: note
    category: architectural-decay
    summary: "Backup wiring is duplicated"
    location: "src/amoeba/cli/hub_commands.py:92"
  - id: F007
    severity: note
    category: other
    summary: "`run_hub` sends any unmatched action to `backup`"
    location: "src/amoeba/cli/hub_commands.py:199"
  - id: F008
    severity: note
    category: error-handling-observability
    summary: "The broad `OSError` swallow in the call loop has no justification comment"
    location: "src/amoeba/client/call.py:183"
  - id: F009
    severity: note
    category: correctness
    summary: "Admin commands can migrate a hub store without the pre-migration backup"
    location: "src/amoeba/hub/store_open.py:39"
  - id: F010
    severity: note
    category: architectural-decay
    summary: "`hub/calls.py` is 313 lines"
    location: "src/amoeba/hub/calls.py"
  - id: F011
    severity: pass
    category: correctness
    summary: "The served registry matches the operation names"
    location: "src/amoeba/operations/served.py#SERVED"
  - id: F012
    severity: pass
    category: security-hygiene
    summary: "The client sends no token until the certificate fingerprint matches"
    location: "src/amoeba/client/join.py#join"
  - id: F013
    severity: pass
    category: documentation-drift
    summary: "Contract docs and container files exist and name the new keys and tables"
    location: "docs/config-contract.md"
---

# Review: code — slice 260

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 23 successful tool call(s) of 23 made; 652161 of 652161 diff characters reached the model

## Findings

### [CONCERN] Relative `--from-backup` path crashes with a traceback instead of a refusal

`_check_backup` calls `store.as_uri()` on the backup path. `Path.as_uri()` raises `ValueError` for a relative path, and `--from-backup` is parsed as a plain `Path` with no `resolve()`. The only handler in `_check_backup` catches `sqlite3.Error`, so the `ValueError` passes through `prepare_start`, which only closes the listener in its `finally`, then `run_hub`, which catches only `AdminRejection`. `main` (src/amoeba/cli/main.py:94–106) lists specific types, so the user gets a traceback.

Nothing on disk changes before this point, because `_check_backup` runs before any file move. No test uses a relative path. Resolve the path in `run_serve` or in `_check_backup`, and add a test that passes a relative path.

### [CONCERN] Hub commands act on a laptop's local store, and `rm-machine local` deletes its machine row

D2 says hub commands refuse on a machine with a client file. That is the only check. `run_hub` calls `refuse_local_store_if_joined`, and `open_hub_store` checks the client file and that the store exists, then calls `Store.open`. A home with a local store, no `hub.yaml` and no client file passes both checks. In that home:

- `amoeba hub rm-machine local` calls `remove_machine` (src/amoeba/store/machines.py:192–205). It deletes the `local` row, its `sessions` rows and its `call_results`. `act_as_local` recreates the row on the next open, so the damage is limited to presence sessions. It is still a write to a store that is not a hub's.
- `amoeba hub machines` and `amoeba hub backup` open and migrate the laptop store (`Store.open` migrates, src/amoeba/store/store.py:131) before they fail on the missing `hub.yaml`.

Fix: have `open_hub_store` refuse a home without `layout.hub_file` before `Store.open`, mirroring `refuse_joined_or_hub_home`. Tests that open a store with `create=True` but no `hub.yaml` will need updating.

### [CONCERN] Member names are deferred to slice 261, which the project's no-deferral rule forbids

AGENTS.md (Amoeba Design Rules) says a slice design or review never defers in-scope behavior to a later slice, and that a review finding of a deferral rejects it. The 260 design defers member names to 261 at lines 63, 454, 671 and 893 of project-documents/user/slices/260-slice.hub-and-door.md. The code carries the deferral: `id_names` and `id_resolver` say "until 261". On a joined machine, `decisions` and `standing --member` show and accept only member ids.

Whether the 260–263 split is in scope is the Project Manager's call, not this review's. The PM should decide it explicitly. If the split stands, the design should record it. Otherwise the names reader and resolver belong in 260.

### [NOTE] Displacing a hand-placed store can overwrite an earlier displaced store

`_displace` names the file with a seconds-precision stamp and calls `store_path.rename(displaced)` with no existence check. On POSIX, `rename` replaces an existing file, so two displacements in the same second would silently overwrite the first. The docstring promises "nothing of it is deleted". `restore_from_backup` avoids the collision with a `-N` suffix. The fix is the same suffix loop. This is unlikely in practice.

### [NOTE] Timestamp format constant is defined three times with different precision

`set_aside.STAMP_FORMAT` is `%Y%m%dT%H%M%SZ` (seconds). `hub/backups.py:35` and `operations/state_move_store.py:39` use `%Y%m%dT%H%M%S%fZ` (microseconds). `set_aside._stamp` also reimplements the helper that `hub/restore.py` takes from `backups`. Define one format in one module and import it.

### [NOTE] Backup wiring is duplicated

`BackupSource(layout.store_path, layout.hub_cert, layout.hub_key)` is built in three places: here, `hub/start.py:164` (`_backup_source`) and `hub/admin.py:114`. `_timed_check` here repeats the timed-backup call that `hub/start.py:_first_timed_backup` makes. A `StateLayout.backup_source()` and one timed-backup function would remove both.

### [NOTE] `run_hub` sends any unmatched action to `backup`

The last statement of `run_hub` runs `admin.backup` for every action it did not match. A future action added to the parser but not to this function would silently take a backup. Match `BACKUP` explicitly and fail on anything else.

### [NOTE] The broad `OSError` swallow in the call loop has no justification comment

`except (OSError, http.client.HTTPException): reply = None` is a deliberate swallow, since no reply means retry, and rule (b) allows that. The rule also requires an inline comment saying why. The docstring explains it, but the handler needs one line.

### [NOTE] Admin commands can migrate a hub store without the pre-migration backup

`prepare_start` takes the D15 pre-migration backup. `open_hub_store`, which every admin command uses, calls `Store.open`, which migrates with no backup. The first hub store is created at schema 11, so no current path reaches this. It matters from migration 012 on: `amoeba hub machines` against a stopped hub with an older store would migrate it unbacked up. Either back up in `open_hub_store` when the store is behind, or make admin commands refuse a store that is behind and point at `amoeba hub serve`.

### [NOTE] `hub/calls.py` is 313 lines

This is over the ~300-line guideline. The reply-writing helpers (`_kept_reply`, `_operation_reply`) could move beside `call_refusals.py`.

### [PASS] The served registry matches the operation names

`OperationName` is a `StrEnum`, so the string lookups in `_served()` and `run_served()` match the enum-keyed `SERVED` dict. `tests/operations/test_served.py` pins `SERVED` to `SERVED_OPERATIONS`.

### [PASS] The client sends no token until the certificate fingerprint matches

`fetch_certificate` sends no request bytes. `join` compares the fingerprint before it writes the pinned certificate, and `hello` (which carries the token) runs only after the match. On any later failure the previous certificate is restored.

### [PASS] Contract docs and container files exist and name the new keys and tables

`docs/config-contract.md` names all eight `hub.yaml` keys and the three client-file keys, backticked. `docs/store-contract.md` names the new tables and columns. `docker/Dockerfile` and `docker/compose.example.yaml` both exist. `.claude/skills/release/SKILL.md` references `update_live.py`.

### Run Digest

- Response length: 9804 chars
- Response is newline-free: no
- Tool calls made: 23
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 24
- Tokens — prompt / cached / cache write / completion / reasoning: 3724707 / 3344894 / 379793 / 80105 / not computed
- Duration: 362.2 s
- Cost: $0.90 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13

### Raw Response

I'll start by checking the files the diff depends on, since a few of them aren't in the diff itself.
The compose file and the release skill both exist. The `as_uri()` call in `restore.py:66` is reachable with a relative `--from-backup` path, which I'll come back to. Next I'll check whether the docs the contract tests read actually name the new tables and keys.
`MCP_CALL_DEADLINE_SECONDS` is 180 s, which is well above the 43 s call bound, so there's no timeout issue there. Next I'll check the config and store contract docs against the keys the tests require.
The contract docs already name the new tables and keys, so the contract tests should pass. Next I'll check whether `Store.open` migrates, how `CLI_ONLY_COMMANDS` is used, and whether the 260 design actually defers member names to slice 261.
The 260 design itself defers member names to slice 261, so I'll record that as a finding against the project's no-deferral rule. Next I'll confirm what `Store.open` does, since the hub admin commands go through it.
Confirmed: `run_hub` checks only for a client file, and `open_hub_store` checks only that the store exists, so the hub commands run against a plain laptop home. Next I'll pin line numbers for the other findings and check file sizes.
Confirmed `open_hub_store` leads to `Store.open`, which migrates on open (`store.py:131`). Now I'll check the top-level exception handling for the relative `--from-backup` path, and whether the release skill really references the update script.
The top-level handler only catches the listed errors, so a `ValueError` from `as_uri()` would escape as a traceback. Last, I'll check the design's rationale for placing the credential-bearing `client.yaml` in the config home, since AGENTS.md says state never lives under `~/.config`.
The design explicitly justifies `client.yaml` in the config home (a person may read and change it), so I won't flag that. One last check: the served registry is keyed by `OperationName` members but looked up with plain strings, which only works if `OperationName` is a `StrEnum`.
## Summary

Verdict: **CONCERNS**

I reviewed the hub, door, client, store and wiring modules that carry the slice's risk, and checked the contract docs and container files that the tests read. The code follows the D-rules I traced, and the contract docs name the new tables and keys. I did not run the test suite, ruff or pyright, because this session has no shell tool. Test status is unverified. I skimmed the test files and did not read every one.

## Findings

### [CONCERN] Relative `--from-backup` path crashes with a traceback instead of a refusal
category: correctness
location: src/amoeba/hub/restore.py:66

`_check_backup` calls `store.as_uri()` on the backup path. `Path.as_uri()` raises `ValueError` for a relative path, and `--from-backup` is parsed as a plain `Path` with no `resolve()`. The only handler in `_check_backup` catches `sqlite3.Error`, so the `ValueError` passes through `prepare_start`, which only closes the listener in its `finally`, then `run_hub`, which catches only `AdminRejection`. `main` (src/amoeba/cli/main.py:94–106) lists specific types, so the user gets a traceback.

Nothing on disk changes before this point, because `_check_backup` runs before any file move. No test uses a relative path. Resolve the path in `run_serve` or in `_check_backup`, and add a test that passes a relative path.

### [CONCERN] Hub commands act on a laptop's local store, and `rm-machine local` deletes its machine row
category: correctness
location: src/amoeba/cli/hub_commands.py:179 and src/amoeba/hub/store_open.py:28

D2 says hub commands refuse on a machine with a client file. That is the only check. `run_hub` calls `refuse_local_store_if_joined`, and `open_hub_store` checks the client file and that the store exists, then calls `Store.open`. A home with a local store, no `hub.yaml` and no client file passes both checks. In that home:

- `amoeba hub rm-machine local` calls `remove_machine` (src/amoeba/store/machines.py:192–205). It deletes the `local` row, its `sessions` rows and its `call_results`. `act_as_local` recreates the row on the next open, so the damage is limited to presence sessions. It is still a write to a store that is not a hub's.
- `amoeba hub machines` and `amoeba hub backup` open and migrate the laptop store (`Store.open` migrates, src/amoeba/store/store.py:131) before they fail on the missing `hub.yaml`.

Fix: have `open_hub_store` refuse a home without `layout.hub_file` before `Store.open`, mirroring `refuse_joined_or_hub_home`. Tests that open a store with `create=True` but no `hub.yaml` will need updating.

### [CONCERN] Member names are deferred to slice 261, which the project's no-deferral rule forbids
category: other
location: src/amoeba/operations/served.py#id_names

AGENTS.md (Amoeba Design Rules) says a slice design or review never defers in-scope behavior to a later slice, and that a review finding of a deferral rejects it. The 260 design defers member names to 261 at lines 63, 454, 671 and 893 of project-documents/user/slices/260-slice.hub-and-door.md. The code carries the deferral: `id_names` and `id_resolver` say "until 261". On a joined machine, `decisions` and `standing --member` show and accept only member ids.

Whether the 260–263 split is in scope is the Project Manager's call, not this review's. The PM should decide it explicitly. If the split stands, the design should record it. Otherwise the names reader and resolver belong in 260.

### [NOTE] Displacing a hand-placed store can overwrite an earlier displaced store
category: correctness
location: src/amoeba/store/set_aside.py:203–209

`_displace` names the file with a seconds-precision stamp and calls `store_path.rename(displaced)` with no existence check. On POSIX, `rename` replaces an existing file, so two displacements in the same second would silently overwrite the first. The docstring promises "nothing of it is deleted". `restore_from_backup` avoids the collision with a `-N` suffix. The fix is the same suffix loop. This is unlikely in practice.

### [NOTE] Timestamp format constant is defined three times with different precision
category: consistency-rot
location: src/amoeba/store/set_aside.py:28

`set_aside.STAMP_FORMAT` is `%Y%m%dT%H%M%SZ` (seconds). `hub/backups.py:35` and `operations/state_move_store.py:39` use `%Y%m%dT%H%M%S%fZ` (microseconds). `set_aside._stamp` also reimplements the helper that `hub/restore.py` takes from `backups`. Define one format in one module and import it.

### [NOTE] Backup wiring is duplicated
category: architectural-decay
location: src/amoeba/cli/hub_commands.py:92

`BackupSource(layout.store_path, layout.hub_cert, layout.hub_key)` is built in three places: here, `hub/start.py:164` (`_backup_source`) and `hub/admin.py:114`. `_timed_check` here repeats the timed-backup call that `hub/start.py:_first_timed_backup` makes. A `StateLayout.backup_source()` and one timed-backup function would remove both.

### [NOTE] `run_hub` sends any unmatched action to `backup`
category: other
location: src/amoeba/cli/hub_commands.py:199

The last statement of `run_hub` runs `admin.backup` for every action it did not match. A future action added to the parser but not to this function would silently take a backup. Match `BACKUP` explicitly and fail on anything else.

### [NOTE] The broad `OSError` swallow in the call loop has no justification comment
category: error-handling-observability
location: src/amoeba/client/call.py:183

`except (OSError, http.client.HTTPException): reply = None` is a deliberate swallow, since no reply means retry, and rule (b) allows that. The rule also requires an inline comment saying why. The docstring explains it, but the handler needs one line.

### [NOTE] Admin commands can migrate a hub store without the pre-migration backup
category: correctness
location: src/amoeba/hub/store_open.py:39

`prepare_start` takes the D15 pre-migration backup. `open_hub_store`, which every admin command uses, calls `Store.open`, which migrates with no backup. The first hub store is created at schema 11, so no current path reaches this. It matters from migration 012 on: `amoeba hub machines` against a stopped hub with an older store would migrate it unbacked up. Either back up in `open_hub_store` when the store is behind, or make admin commands refuse a store that is behind and point at `amoeba hub serve`.

### [NOTE] `hub/calls.py` is 313 lines
category: architectural-decay
location: src/amoeba/hub/calls.py

This is over the ~300-line guideline. The reply-writing helpers (`_kept_reply`, `_operation_reply`) could move beside `call_refusals.py`.

### [PASS] The served registry matches the operation names
category: correctness
location: src/amoeba/operations/served.py#SERVED

`OperationName` is a `StrEnum`, so the string lookups in `_served()` and `run_served()` match the enum-keyed `SERVED` dict. `tests/operations/test_served.py` pins `SERVED` to `SERVED_OPERATIONS`.

### [PASS] The client sends no token until the certificate fingerprint matches
category: security-hygiene
location: src/amoeba/client/join.py#join

`fetch_certificate` sends no request bytes. `join` compares the fingerprint before it writes the pinned certificate, and `hello` (which carries the token) runs only after the match. On any later failure the previous certificate is restored.

### [PASS] Contract docs and container files exist and name the new keys and tables
category: documentation-drift
location: docs/config-contract.md

`docs/config-contract.md` names all eight `hub.yaml` keys and the three client-file keys, backticked. `docs/store-contract.md` names the new tables and columns. `docker/Dockerfile` and `docker/compose.example.yaml` both exist. `.claude/skills/release/SKILL.md` references `update_live.py`.
