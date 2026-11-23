---
docType: review
layer: project
reviewType: code
slice: hub-and-door
conventionsSource: AGENTS.md
projectRules: [general.md, python.md, sql.md, testing.md]
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/260-slice.hub-and-door.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261122
dateUpdated: 20261122
reviewedSha: c3f31a32ddb5b6a2dec90ae15bc18088daeaa922
reviewedBlob: 47351c42e13e3f6dc80e53f7f0c8e046ad160dbb
reviewedBlobCurrent: true
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 32
injected:
  - key: conventions
    path: "AGENTS.md"
    chars: 24525
    sha256: 2387512002bb2a73aa247bc36bc98d7162c5b5110ded41f56319d098d282ddbc
    whole: true
filesRead:
  - "pyproject.toml"
  - "docker/compose.example.yaml"
  - "src/amoeba/wiring_door.py"
searches:
  - "list_files {docker/**,docs/config-contract.md,.claude/skills/release/SKILL.md,src/amoeba/hub/*.py,src/amoeba/client/*.py,src/amoeba/wire/*.py} in /Users/manta/source/repos/manta/amoeba"
  - "grep refuse_if_joined in /Users/manta/source/repos/manta/amoeba/src"
  - "grep TEMPORARY_SUFFIX|_write_through_rename|def write_client_file|def _print|HUB_LOCK_WAITS_PER_CALL in /Users/manta/source/repos/manta/amoeba/src"
  - "grep except BaseException|rpartition\\(\":\"\\)|must be a mapping of keys in /Users/manta/source/repos/manta/amoeba/src"
  - "list_files **/* in /Users/manta/source/repos/manta/amoeba/docker"
  - "grep Store\\.open\\( in /Users/manta/source/repos/manta/amoeba/src"
  - "grep PLR0913|RUF009|RUF100 in /Users/manta/source/repos/manta/amoeba"
  - "grep replaced-|displaced- in /Users/manta/source/repos/manta/amoeba/project-documents"
  - "grep replaced-|displaced-|stall|cleanup|never deleted|bounded in /Users/manta/source/repos/manta/amoeba/project-documents/user/slices/260-slice.hub-and-door.md"
  - "grep def leave|def put_back|def _refuse_in_a_hub_home|def join_address|def route|def joined in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep def clear_orphan_side_files|def _delete_store|def set_aside|JoinError|from amoeba.wire in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/set_aside.py"
  - "grep client_version|def touch_machine in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep SERVED_OPERATIONS|WRITING_CALLS|SERVED_RUNNERS|_SERVED_RESULT_TYPES|UNKNOWN_ADVICE|NEEDS_CONFIG in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep StateLayout\\( in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep def _kept_reply|def _operation_reply|def _attempt|def _serve|def handle_call|HUB_LOCK_WAITS_PER_CALL|NEEDS_CONFIG: |_BAD_TOKEN: Final in /Users/manta/source/repos/manta/amoeba/src/amoeba/hub/calls.py"
  - "grep def _attempt|def call\\(|def _unreachable|JSON_TYPE|MACHINE_PLACEHOLDER in /Users/manta/source/repos/manta/amoeba/src/amoeba/client/call.py"
  - "grep write_text|LOCAL_MACHINE_NAME|OWNER_NAME|JSON_TYPE|STAMP_FORMAT: Final|def run\\(|def keep\\( in /Users/manta/source/repos/manta/amoeba"
  - "grep lock|del lock|assert DOOR_VERSION == 1|assert protocol.SERVED_OPERATIONS|assert _done\\( in /Users/manta/source/repos/manta/amoeba/tests"
  - "grep def serve\\(|def run\\(|def backup_loop|timeout|limit_concurrency|access_log in /Users/manta/source/repos/manta/amoeba/src/amoeba/hub/serve.py"
  - "grep moved away|Bounded as D14|264 adds|leave.{0,80}hub home|hub home.{0,120}leave|a stall|stalls in /Users/manta/source/repos/manta/amoeba/project-documents/user/slices/260-slice.hub-and-door.md"
  - "grep moved aside|old files|set aside into|replaced in /Users/manta/source/repos/manta/amoeba/project-documents/user/slices/260-slice.hub-and-door.md"
  - "grep ### D2 |Every command that opens|`leave`.{0,60}(hub|refus)|refus.{0,60}`leave` in /Users/manta/source/repos/manta/amoeba/project-documents/user/slices/260-slice.hub-and-door.md"
  - "grep clear_orphan_side_files\\(store_path\\)|def cli_name|cli_name|class OperationName|CONTRACT_DOC|def test_a_seventh|def _mark_read|def _decisions in /Users/manta/source/repos/manta/amoeba"
  - "grep except BaseException|def _savepoint|def _transaction|def call_scope in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/store.py"
  - "grep def _restore_or_refuse|def prepare_start|def _bind|def _decide in /Users/manta/source/repos/manta/amoeba/src/amoeba/hub/start.py"
  - "list_files {uv.lock,.github/workflows/*.yml} in /Users/manta/source/repos/manta/amoeba"
  - "grep HUB_LOCK_WAITS_PER_CALL|uv sync|uv run|uv export in /Users/manta/source/repos/manta/amoeba"
diffTruncated: false
effort: xhigh
turns: 33
promptTokens: 3425668
cachedTokens: 3009387
cacheWriteTokens: 416263
completionTokens: 114781
durationSeconds: 491.7
costUsd: 0.995141
costBasis: provider
runId: run-20261122-p6-be735421
squadronVersion: 0.24.37
categoriesNormalized: true
findings:
  - id: F001
    severity: fail
    category: other
    summary: "Restore and displacement directories have no cleanup, and the design defers it to slice 264"
    location: "src/amoeba/hub/restore.py#_move_aside"
  - id: F002
    severity: concern
    category: correctness
    summary: "`amoeba leave` has no hub-home guard, and it deletes WAL and shared-memory files beside a missing store"
    location: "src/amoeba/wiring_door.py:208"
  - id: F003
    severity: concern
    category: security-hygiene
    summary: "Client-supplied headers reach the hub's store and the admin's terminal unchecked"
    location: "src/amoeba/hub/calls.py:123"
  - id: F004
    severity: concern
    category: consistency-rot
    summary: "Two functions named `refuse_if_joined` take different arguments and raise different errors"
    location: "src/amoeba/wiring_door.py:75"
  - id: F005
    severity: concern
    category: architectural-decay
    summary: "Served operations are registered in five places, and the documented recipe covers two"
    location: "src/amoeba/operations/served.py:87-88"
  - id: F006
    severity: concern
    category: architectural-decay
    summary: "The store layer raises a join-command error"
    location: "src/amoeba/store/set_aside.py:22"
  - id: F007
    severity: concern
    category: architectural-decay
    summary: "Parsers are duplicated, and the client file accepts any address text"
    location: "src/amoeba/client/trust.py:23"
  - id: F008
    severity: concern
    category: architectural-decay
    summary: "Atomic-write logic is written twice, and the pinned certificate is written non-atomically"
    location: "src/amoeba/client/join.py:64"
  - id: F009
    severity: concern
    category: error-handling-observability
    summary: "Cleanup-only `except BaseException` blocks re-raise without logging"
    location: "src/amoeba/client/join.py:75"
  - id: F010
    severity: concern
    category: documentation-drift
    summary: "Container messages point to a path the image does not have"
    location: "src/amoeba/config/user_config.py:34"
  - id: F011
    severity: concern
    category: dependency-config-debt
    summary: "The compose example builds from `context: ..`, which breaks if the file is copied elsewhere"
    location: "docker/compose.example.yaml:27"
  - id: F012
    severity: concern
    category: dependency-config-debt
    summary: "The image installs with pip, which bypasses the committed `uv.lock`"
    location: "docker/Dockerfile:14"
  - id: F013
    severity: note
    category: architectural-decay
    summary: "Small duplicates: `_print` written twice, and a `\"local\"` literal in the update script"
    location: "src/amoeba/cli/join_command.py:60"
  - id: F014
    severity: note
    category: test-debt
    summary: "Dead production constant, and tests with dead code or assertions that check nothing"
    location: "src/amoeba/hub/calls.py:58"
  - id: F015
    severity: note
    category: architectural-decay
    summary: "Seven test files hand-build `StateLayout`, and each gained the same six fields in this diff"
    location: "tests/hub/call_support.py#layout_in"
---

# Review: code — slice 260

**Verdict:** FAIL
**Model:** claude-haiku-5-5
**Evidence:** 32 successful tool call(s) of 32 made; 621789 of 621789 diff characters reached the model

## Findings

### [FAIL] Restore and displacement directories have no cleanup, and the design defers it to slice 264

Each `--from-backup` start moves the existing state into a new `replaced-<UTC stamp>/` directory, which holds a full copy of the store. `leave` does the same with `displaced-<stamp>` (`src/amoeba/store/set_aside.py#_displace`). Nothing reads, rotates or deletes either kind.

The slice design's file table says `replaced-` is "Bounded as D14 says; 264 adds the commands that end one" (`project-documents/user/slices/260-slice.hub-and-door.md:138`). D14 step 4 (line 545) says only "print its path" and gives no bound. The design also says the `displaced-` row is "bounded as D4 says", and I found no bound for it in D4 or in the code.

AGENTS.md's Amoeba design rules say "No deferral" (a review that finds one rejects it) and "Every state has an exit", meaning a named cleanup or a stated bound. This slice writes the state and defers the exit. Fix: rotate both directory kinds to a keep count, as the backups are, and test the rotation. Or state in the design why the count is bounded, and build that bound.

### [CONCERN] `amoeba leave` has no hub-home guard, and it deletes WAL and shared-memory files beside a missing store

`join` refuses in a hub home through `_refuse_in_a_hub_home` (`wiring_door.py:119`). `leave()` (lines 208-215) does not. It calls `put_back`, which calls `clear_orphan_side_files(store_path)` (`src/amoeba/store/set_aside.py:227`) before it checks for a set-aside store. If a hub's `amoeba.sqlite3` is missing (the lost-store case D5 refuses to start on) but its `-wal` and `-shm` remain, `amoeba leave` run in that home deletes them. Those files can hold committed writes not yet checkpointed into the main file. D2 guards the local opener and `prepare_state_home` but not `leave`. Fix: add the same hub-home refusal to `leave()`, and add a test that `leave` in a hub home fails and leaves the `-wal` in place.

### [CONCERN] Client-supplied headers reach the hub's store and the admin's terminal unchecked

`Amoeba-Client-Version` and `Amoeba-Call-Id` are read with no length or character check. `touch_machine` writes the version to `machines.client_version` (`src/amoeba/store/machines.py:144`). `amoeba hub machines` prints it raw in text mode (`src/amoeba/cli/hub_commands.py:155`). The call id is a key in `call_results` with no bound. A holder of one machine's token (a copied `client.yaml`, for example) can put terminal escape sequences into the admin's output, or store arbitrarily long keys. The Python rules say to validate everything entering the system via Pydantic. Fix: validate both headers against a bounded pattern and refuse with `malformed_call` otherwise, with tests.

### [CONCERN] Two functions named `refuse_if_joined` take different arguments and raise different errors

`wiring_door.refuse_if_joined(operation: str)` raises `NotServedError`. `operations/state_move.py:100`'s `refuse_if_joined(layout: StateLayout)` raises `LocalStoreClosedError`. `wiring` re-exports the first (`wiring.py:53`), which `cli/main.py:75,87` and `mcp/server.py:287` use. `cli/hub_commands.py:36,181` uses the second. The two behaviors differ on purpose (D2), so one name for both is a trap for any reader. Rename them, for example `refuse_if_not_served` and `refuse_if_local_store_closed`.

### [CONCERN] Served operations are registered in five places, and the documented recipe covers two

The comment at `served.py:87` says a new served operation needs its name in `wire.protocol.SERVED_OPERATIONS` and an entry in `SERVED_RUNNERS`. It also needs:
- `WRITING_CALLS` (`wire/protocol.py:28`), if it writes.
- `UNKNOWN_ADVICE` (`protocol.py:135`), if it writes. Otherwise `client/call.py:145` raises `KeyError` on an unknown outcome.
- `_SERVED_RESULT_TYPES` (`src/amoeba/wiring_results.py:87`). Without it a joined client raises `ValueError` from `route`.
- A `case` in `wiring.py#_dispatch`, or the local way takes a different path.
- `NEEDS_CONFIG` (`hub/calls.py:60`), if it reads config.

`test_a_seventh_operation_is_served...` (`tests/hub/test_handle_call.py:318`) patches only `SERVED_RUNNERS` and the hub's list. It never calls `route` or `result_from_document`, so it misses the gap. Fix: one registry (name to runner, result type, writes, advice, needs-config), with the other tables derived from it, and an end-to-end test that walks it.

### [CONCERN] The store layer raises a join-command error

`set_aside` raises `JoinError` (line 161), imported from `amoeba.wire.join_line`. That class is documented as the `join`/`leave` exit-3 error (`wire/join_line.py`). A store module now decides a CLI outcome, which breaks the layering the rest of the slice keeps. Fix: have `set_aside` raise a store error and let `wiring_door` translate it, or let `wiring_door` check the pair before it calls.

### [CONCERN] Parsers are duplicated, and the client file accepts any address text

Three copies of the host:port check: `trust.py:23` (`split_address`), `client/join.py:96` (`change_address`), `hub/hub_config.py:68` (`_host_and_port`). Three copies of the "top level must be a mapping" check: `client/client_file.py:68`, `config/user_config.py:188` (`config_document`), and `hub/hub_config.py:96`, which re-implements it.

Separately, `ClientFile.address` is `StrictStr` with no format check (`client/client_file.py`). A malformed address in `client.yaml` loads cleanly and fails later as `HubUnreachableError`. Fix: one `parse_host_port` in `wire/` (which imports nothing), used everywhere, with `ClientFile.address` validated through it and one shared mapping check.

### [CONCERN] Atomic-write logic is written twice, and the pinned certificate is written non-atomically

`write_client_file` (`client/client_file.py:41-52`) and `_write_through_rename` (`hub/certificate.py:43-50`) each do a temp-name, mode, rename sequence. Each has its own `TEMPORARY_SUFFIX = ".tmp"` (`client_file.py:22`, `certificate.py:31`). `join` writes the pinned certificate with `cert_path.write_text(pem)` at line 64, which is not atomic. That write sits before the `try` that restores the previous certificate on failure. If it fails partway (disk full, for example), the old certificate is neither restored nor removed, and `client.yaml` points at a damaged file. Fix: one atomic-write helper for all three callers, and move the certificate write inside the `try`.

### [CONCERN] Cleanup-only `except BaseException` blocks re-raise without logging

The Python rule (AGENTS.md, Exception Handling (a)) requires every try/except to re-raise after `logger.exception`, handle a specific exception with a justifying comment, or be a process-boundary handler. These blocks clean up and re-raise without logging:
- `client/join.py:75` (restore the certificate)
- `hub/backups.py:230` (delete the partial directory)
- `hub/start.py:255` (close the listener)
- `operations/state_move.py:191` (close the store)
- `store/store.py:206` (roll back the savepoint)

Use `try/finally` where the cleanup runs on both paths. Where it does not, add `logger.exception` before the re-raise.

### [CONCERN] Container messages point to a path the image does not have

`CONTRACT_DOC` is `docs/config-contract.md` (line 34). Missing-config errors say `see docs/config-contract.md` (line 153), and `hub.yaml.example` line 2 says the same. The image ships the contract at `/usr/share/amoeba/config-contract.md` (`docker/Dockerfile:22`), and the compose example points there. Inside the container, `amoeba hub serve` with no `hub.yaml` names a path that does not exist, and the wheel ships no `docs/`. Fix: name the in-image path when running in the container, or ship the contract as package data and point there.

### [CONCERN] The compose example builds from `context: ..`, which breaks if the file is copied elsewhere

Compose resolves `context: ..` against the compose file's own directory. The file's header (line 1) says to copy it to `compose.yaml`. A copy at the repo root makes the build context the repo's parent, and a copy in `~/amoeba-hub/` makes it the home directory. Both fail with no Dockerfile found. Fix: say to keep the file in `docker/`, or use an absolute context path, or publish the image and drop `build:`.

### [CONCERN] The image installs with pip, which bypasses the committed `uv.lock`

`uv.lock` is committed, and CI runs `uv sync --all-extras --dev` (`.github/workflows/ci.yml:28`). The image runs `pip install --prefix=/install .` (`Dockerfile:14`). That ignores the lock and resolves every transitive dependency fresh at build time. The hub is the one component that listens on a network address, and its build is the one path CI does not test. The Python rules say to use `uv` for all projects. Fix: export the locked set in the build stage (`uv export --frozen`) and install from that, so the image gets the same resolution CI tests.

### [NOTE] Small duplicates: `_print` written twice, and a `"local"` literal in the update script

`_print` is defined in `cli/join_command.py:60` and `cli/hub_commands.py:77` with the same body. `scripts/update_live.py:59` defines `LOCAL_MACHINE_NAME = "local"`, duplicating `store/machines.py:28`. The script's `check_store` compares against its copy (`update_live.py:174`). If the store's constant changes, the script's read-back fails without an obvious cause. Fix: import the store's constant, and share one `_print`.

### [NOTE] Dead production constant, and tests with dead code or assertions that check nothing

`HUB_LOCK_WAITS_PER_CALL` (`calls.py:58`) is referenced only by `tests/wire/test_times.py:43`. It describes a retry the code never does. In `tests/load/test_door_load.py`, `lock = threading.Lock()` (line 113) is never used and is deleted at line 172. In `tests/hub/test_handle_call.py:332-333`, `assert DOOR_VERSION == 1` and `assert protocol.SERVED_OPERATIONS == SERVED_OPERATIONS` do not relate to the test's name and check nothing about the seventh-operation path. Fix: remove the constant, delete the lock, and replace the two asserts with the route check from the registry finding.

### [NOTE] Seven test files hand-build `StateLayout`, and each gained the same six fields in this diff

The seven builders are `tests/hub_fixture.py#hub_layout`, `tests/hub/call_support.py#layout_in`, `tests/operations/test_prune.py`, `tests/mcp_server/test_detached.py`, `tests/operations/state_move_worker.py`, `tests/operations/test_prune_wiring.py` and `tests/operations/state_move_support.py#make_layout`. The next field added to `StateLayout` means editing all seven. Fix: one test factory, such as `tests/layout_support.py#layout_under(root)`, that each of them calls.

### Run Digest

- Response length: 14094 chars
- Response is newline-free: no
- Tool calls made: 32
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 33
- Tokens — prompt / cached / cache write / completion / reasoning: 3425668 / 3009387 / 416263 / 114781 / not computed
- Duration: 491.7 s
- Cost: $1.00 (provider)
- `## Summary` located: yes
- `## Findings` located: no
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15
