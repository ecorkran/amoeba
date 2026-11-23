---
docType: review
layer: project
reviewType: code
slice: hub-and-door
conventionsSource: AGENTS.md
projectRules: [general.md, python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/260-slice.hub-and-door.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261122
dateUpdated: 20261122
reviewedSha: 682b7b9b095f9148424f5ed6094be186943dede5
reviewedBlob: b9956e9714094d2a41c175eddd2d63382bc4b52a
reviewedBlobCurrent: true
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 27
injected:
  - key: conventions
    path: "AGENTS.md"
    chars: 24525
    sha256: 2387512002bb2a73aa247bc36bc98d7162c5b5110ded41f56319d098d282ddbc
    whole: true
filesRead:
  - "tests/test_import_boundaries.py"
  - "src/amoeba/cli/init_command.py"
  - "src/amoeba/hub/start.py"
  - "src/amoeba/cli/main.py"
  - "src/amoeba/config/user_config.py"
  - "src/amoeba/hub/calls.py"
  - "src/amoeba/store/store.py"
  - "src/amoeba/mcp/server.py"
  - "project-documents/user/slices/260-slice.hub-and-door.md"
  - "src/amoeba/cli/commands.py"
  - "docs/config-contract.md"
searches:
  - "list_files {docker/*,LICENSE,README.md,.claude/skills/release/SKILL.md,docs/config-contract.md,.dockerignore} in /Users/manta/source/repos/manta/amoeba"
  - "grep CLI_ONLY_COMMANDS in /Users/manta/source/repos/manta/amoeba"
  - "grep ^from amoeba\\.(client|hub|upstream)|^from amoeba\\.wiring|^import amoeba in /Users/manta/source/repos/manta/amoeba/src/amoeba/operations/state_move.py"
  - "grep compose|docker in /Users/manta/source/repos/manta/amoeba/docs/config-contract.md"
  - "grep clear_orphan_side_files|def load_user_config|def read_config_text|backup_hours|hub_logs_kept in /Users/manta/source/repos/manta/amoeba"
  - "grep def open_store|def open_state_store|open_state_store\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba/wiring.py"
  - "grep amoeba-mcp|MCP server|joined machine.*(MCP|mcp) in /Users/manta/source/repos/manta/amoeba/project-documents/user"
  - "grep D4|fingerprint|migrat in /Users/manta/source/repos/manta/amoeba/project-documents/user/slices/260-slice.hub-and-door.md"
  - "grep write-ahead|-wal|side file in /Users/manta/source/repos/manta/amoeba/project-documents/user/slices/260-slice.hub-and-door.md"
  - "grep Store\\.open\\(|open_hub_store\\(|def _missing_file in /Users/manta/source/repos/manta/amoeba/src"
  - "grep def run_invoked|calls_log|def log_call|def _log|record_call|log_failed_call\\( in /Users/manta/source/repos/manta/amoeba/src/amoeba/cli"
  - "grep IPv6|\\[::1\\]|\\\\[:: in /Users/manta/source/repos/manta/amoeba/tests"
  - "list_files {src/amoeba/hub/hub.yaml.example,uv.lock,pyproject.toml,src/amoeba/hub/serve.py} in /Users/manta/source/repos/manta/amoeba"
  - "grep lock = threading.Lock|del lock|def test_|THINK_SECONDS =  in /Users/manta/source/repos/manta/amoeba/tests/load/test_door_load.py"
  - "grep def split_address|def fetch_certificate|socket\\.create_connection in /Users/manta/source/repos/manta/amoeba/src/amoeba"
diffTruncated: false
effort: xhigh
turns: 28
promptTokens: 5612120
cachedTokens: 5222695
cacheWriteTokens: 389395
completionTokens: 85105
durationSeconds: 379.4
costUsd: 1.008815
costBasis: provider
runId: run-20261122-p6-be735421
squadronVersion: 0.24.37
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Certificate fetch fails for IPv6 hub addresses that the parser accepts"
    location: "src/amoeba/client/trust.py:44"
  - id: F002
    severity: concern
    category: correctness
    summary: "`join --set-aside-local` changes the local store before the hub or the fingerprint is checked"
    location: "src/amoeba/wiring_door.py#join"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "The hub's missing-config message points to a command that fails on a hub home"
    location: "src/amoeba/config/user_config.py:152"
  - id: F004
    severity: concern
    category: correctness
    summary: "A hub first start can open a new store with a stale write-ahead log beside it"
    location: "src/amoeba/hub/start.py:200"
  - id: F005
    severity: concern
    category: architectural-decay
    summary: "The operations package now depends on the client package, so the hub depends on it indirectly"
    location: "src/amoeba/operations/state_move.py:19"
  - id: F006
    severity: note
    category: documentation-drift
    summary: "The `CLI_ONLY_COMMANDS` comment says \"no `-j`\", but the new commands accept it"
    location: "src/amoeba/cli/wake_command.py:26"
  - id: F007
    severity: note
    category: consistency-rot
    summary: "The `standing` config requirement is hard-coded in the hub, not in the served registry"
    location: "src/amoeba/hub/calls.py#NEEDS_CONFIG"
  - id: F008
    severity: note
    category: test-debt
    summary: "Dead code in the load test"
    location: "tests/load/test_door_load.py:113"
  - id: F009
    severity: pass
    category: correctness
    summary: "Savepoint and call-scope semantics match their use in `handle_call`"
    location: "src/amoeba/store/store.py#Store.call_scope"
  - id: F010
    severity: pass
    category: dependency-config-debt
    summary: "Container files reference paths that exist"
    location: "docker/Dockerfile"
---

# Review: code — slice 260

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 26 successful tool call(s) of 27 made; 640409 of 640409 diff characters reached the model

## Findings

### [CONCERN] Certificate fetch fails for IPv6 hub addresses that the parser accepts

`split_address` keeps the brackets of an IPv6 host (`[::1]:8443` gives `"[::1]"`, asserted in `tests/wire/test_address.py`). `fetch_certificate` passes that host straight to `socket.create_connection`, which cannot resolve bracketed text. `join` therefore reports "cannot reach the hub" for a reachable hub. The call path is not affected, because `http.client` strips the brackets. Strip the brackets in one place, for example in `split_address`'s consumers or a shared helper, so both paths agree. A test with a real `[::1]` listener would catch this.

### [CONCERN] `join --set-aside-local` changes the local store before the hub or the fingerprint is checked

`join` calls `_migrate_before_marking`, which opens the local store, migrates it and writes the `local` machine row. This runs before `client_join.join` compares the fingerprint. The design's step 1 asks for this migration, but the failure table in `260-slice.hub-and-door.md` (line 238) says a fingerprint mismatch leaves "Nothing". The `JoinError` in `src/amoeba/client/join.py#join` also says "nothing was saved". Both statements are false when the flag is given. The migration is only needed before `set_aside` writes the mark, so moving the `_migrate_before_marking` call into `_set_aside_local`, which runs after `hello`, would make the code match the table. Otherwise the table and message need correcting.

### [CONCERN] The hub's missing-config message points to a command that fails on a hub home

A `standing` call on the hub with no `config.yaml` gets "run `amoeba init`", because `_hub_config_loader` in `src/amoeba/cli/hub_commands.py` loads with the default kind. On a hub home `amoeba init` writes a starter config with placeholder model aliases, then fails at the store step with `HubHomeError`, because `open_state_store` refuses when `hub.yaml` exists. The operator gets a contradictory result. Either the hub's loader should name the contract document (the image path is already defined as `IMAGE_CONTRACT_DOC`), or `amoeba init` should refuse on a hub home before it writes anything.

### [CONCERN] A hub first start can open a new store with a stale write-ahead log beside it

`_open_store` creates the store on the first-start kinds without clearing `amoeba.sqlite3-wal` and `-shm`. `clear_orphan_side_files` exists for this (`store/set_aside.py`, used by `join` and `leave`). The design says side files with no store are always deleted before a store is placed (`260-slice.hub-and-door.md`, line 265). The trigger is narrow: an operator deletes only the store file and no backup exists. Call `clear_orphan_side_files(layout.store_path)` before `open_hub_store(..., create=True)`. SQLite can replay a leftover WAL into a new database at the same path.

### [CONCERN] The operations package now depends on the client package, so the hub depends on it indirectly

`state_move` imports `read_client_address` from `amoeba.client.client_file`. `hub/admin.py` and `hub/start.py` import `state_move`, so the hub now depends on the client package transitively. `hub/__init__.py` says it imports nothing from `client`. `tests/test_import_boundaries.py` checks only direct imports per file, so it cannot catch this. Move the address reader to `wire` (which may import only stdlib and third-party code) and import it from both places.

### [NOTE] The `CLI_ONLY_COMMANDS` comment says "no `-j`", but the new commands accept it

`join`, `leave` and the hub's `invite`, `machines`, `rm-machine` and `backup` all register `-j` through `json_parent`. The comment is now wrong, and this set of all CLI-only commands lives in `wake_command.py`, which is an odd home for it.

### [NOTE] The `standing` config requirement is hard-coded in the hub, not in the served registry

`NEEDS_CONFIG = frozenset({"standing"})` repeats a fact the served registry in `operations/served.py` already implies, since only `_standing` calls `edges.load_config()`. A future config-reading operation that is missing from this set fails loudly (`_loaded` raises `AssertionError`, reported as `hub_fault`), so it is not silent. Recording the need on `ServedOperation` would remove the second list.

### [NOTE] Dead code in the load test

`lock = threading.Lock()` at line 113 and `del lock` at line 172 do nothing. Remove both.

### [PASS] Savepoint and call-scope semantics match their use in `handle_call`

I read `Store.call_scope`, `_savepoint` and `_transaction`, and the call sites in `hub/calls.py` (`_serve`, `_operation_reply`). A failed operation rolls back only its savepoint. The kept result is written in the same savepoint as the operation. The touch survives because the exception is caught inside the scope. Read and write checks run in the right order.

### [PASS] Container files reference paths that exist

Every `COPY` source exists: `pyproject.toml`, `uv.lock`, `README.md`, `LICENSE`, `src`, `src/amoeba/hub/hub.yaml.example` and `docs/config-contract.md`. `uv sync --locked` is pinned with `uv` 0.13.5. The entry point is exec form, so `amoeba` is PID 1 and receives SIGTERM. I did not build the image.

### Run Digest

- Response length: 8468 chars
- Response is newline-free: no
- Tool calls made: 27
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: none
- Reasoning characters: 0
- Effort: xhigh
- Turns: 28
- Tokens — prompt / cached / cache write / completion / reasoning: 5612120 / 5222695 / 389395 / 85105 / not computed
- Duration: 379.4 s
- Cost: $1.01 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
