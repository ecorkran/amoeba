---
docType: review
layer: project
reviewType: tasks
slice: push-and-presence
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/241-tasks.push-and-presence.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 873e6290f036d9a1ca67910d5de5b7362edd939b
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 25
effort: xhigh
turns: 26
promptTokens: 897150
cachedTokens: 720663
cacheWriteTokens: 176473
completionTokens: 66337
durationSeconds: 295.4
costUsd: 0.36587
costBasis: provider
runId: run-20261115-tasks-plan-962527a1
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 7.2 tests subscriptions before task 8.1 builds them"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:171"
  - id: F002
    severity: concern
    category: coverage
    summary: "The integration criterion \"243's notes push\" has no task"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:170"
  - id: F003
    severity: concern
    category: operations
    summary: "Phase 7 lacks the precondition check that 13.1 has"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:267"
  - id: F004
    severity: concern
    category: ci-gating
    summary: "The load test's CI gate is implicit"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:202"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Task 11.1 bundles three live scenarios into one task"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:224"
  - id: F006
    severity: note
    category: commit-markers
    summary: "Section 1's commit marker may include a probe that should not ship"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:66"
  - id: F007
    severity: note
    category: proportionality
    summary: "7.2 and 9.2 repeat the watcher-failure check"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:170"
  - id: F008
    severity: note
    category: proportionality
    summary: "Two file-size risks in 9.1 and 6.1 to 6.5"
    location: "src/amoeba/mcp/server.py:184"
  - id: F009
    severity: note
    category: operations
    summary: "Phase 7 operator dead ends: the restore check and the forward-only undo"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:274"
  - id: F010
    severity: note
    category: verification
    summary: "Claude Code channel facts were not checked in this review"
    location: "unverified"
  - id: F011
    severity: pass
    category: coverage
    summary: "Success criteria map to tasks"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md"
  - id: F012
    severity: pass
    category: verification
    summary: "Facts the task file relies on hold in the repo"
    location: ".venv/lib/python3.13/site-packages/mcp/server/connection.py:401"
  - id: F013
    severity: pass
    category: design-rules
    summary: "Design rules hold: no deferral, every state has an exit, config and state are separate"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md"
---

# Review: tasks — slice 241

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 7.2 tests subscriptions before task 8.1 builds them

The bullet "Subscribed client gets `notifications/resources/updated` ...; an unsubscribed one gets none" needs a client that can send `resources/subscribe`. That handler is built in 8.1 (line 179), which comes after 7. An implementer working in order cannot pass the bullet when they reach it. Move it to 8.2, where subscribe is built and tested. Leave 7.2's watcher tests (events, busy store, the notify pin) in 7.

### [CONCERN] The integration criterion "243's notes push" has no task

The design's Integration Requirements list "243's notes push with no change to this slice" as a 241 success criterion. Tasks 3.5 and 5.2 check only the note's counterparty. Nothing shows a note delivery reaching the watcher and producing a channel event. The fixture is feasible: 240's task file defines `MessageKind` as `request` and `note` (`project-documents/user/tasks/240-tasks.requests.md:59`). Add a note-kind case to 7.2 (one event, sender as counterparty) so the criterion is verified in this slice.

### [CONCERN] Phase 7 lacks the precondition check that 13.1 has

Task 13.1 handles a copy that reads schema version 5 (240's live migration not yet run) by adding 240's two keys first. The live steps P7.1 to P7.3 have no such check. P7.1 backs up without reading `schema_meta.version`, and P7.2 adds only 241's three keys. If the live store is at 5, `amoeba list` fails on 240's missing keys inside the window the design describes. P7.3's read-back cannot tell the two cases apart. Add a version and member-count read to P7.1 that stops with `BLOCKED:` unless the version is 6. 240's own live migration runs in its Phase 7 (`240-tasks.requests.md:311-316`), so 6 is the expected state.

### [CONCERN] The load test's CI gate is implicit

The 9.4 load test is required, not scope creep. The project Python rule requires a load test in `tests/load/` for concurrency paths, and this slice adds watcher threads. But 9.4 does not say how CI runs it. The single CI test step is `uv run pytest` (`.github/workflows/ci.yml:40`). The only collection exclusion is `addopts = ["--ignore=tests/live"]` (`pyproject.toml:64`), so `tests/load/test_presence_load.py` already runs in every CI run. That may be the gate, but it is implicit. The 9.4 assertions (answers within one second, every row live with 12 runs and short intervals) are timing bounds on a shared runner and can flake. Add to 9.4 an explicit statement that CI collects it, and name the timing tolerance. Or add a CI item that names the test.

### [CONCERN] Task 11.1 bundles three live scenarios into one task

11.1 covers the fixture build, Session 1 (request, inbox call, confirmation, clean exit), Session 2 (SIGKILL and stale wait) and Session 3 (non-member directory). It runs a real model in a pty, so each failure has a different cause. Split it into 11.1 (fixtures and Session 1) and 11.2 (Sessions 2 and 3), each with its own success line, so each scenario can be checked before the next starts.

### [NOTE] Section 1's commit marker may include a probe that should not ship

1.2 describes its probe as "throwaway" but places it under `tests/live/channels/`. The marker at line 72 commits everything in the section, including design corrections, under a `test:` prefix. Say whether the probe is deleted before that commit. Split the design corrections into a `docs:` commit, or move them to 12.2. Otherwise the marker sits where the harness has only been collect-tested.

### [NOTE] 7.2 and 9.2 repeat the watcher-failure check

7.2's last bullet ("any other store error ends presence ... and the server still answers a tool call") is the same check as 9.2's third bullet (line 197). Keep it in 9.2, where the whole server exists.

### [NOTE] Two file-size risks in 9.1 and 6.1 to 6.5

`server.py` is 221 lines, and `_serve` is at line 184. 9.1 adds the capability declarations, four handler registrations, the config read in `main()`, `PresenceState` threading, `call_tool` logging and the INSTRUCTIONS paragraph. That likely brings the file close to the ~300-line limit. Separately, `presence.py` would hold the state, resolution, client name, heartbeat, confirmation and `run_presence` (6.1 to 6.5). Task 6.5 defers the split with "if the file passes ~300 lines". Decide it now: `presence.py` for state and confirmation, `presence_task.py` for resolution, heartbeat and `run_presence`. Put the resource handler registration in `inbox_resource.py`.

### [NOTE] Phase 7 operator dead ends: the restore check and the forward-only undo

Walking Phase 7 as the operator: P7.3's `pgrep -fl amoeba` will match the `amoeba-mcp` processes of open client sessions, which the design expects to keep running until restarted. So any read-back failure while a session is open ends at `BLOCKED:`, and the PM must close those sessions before the restore can run. That is safe, but the step should say so. The design's Undo (`project-documents/user/slices/241-slice.push-and-presence.md:325`) needs `DROP TABLE sessions` on the live store to return to pre-241 code. The migration designation does not cover that statement. The design reports this as a dead end, and the PM should know it is the only way back.

### [NOTE] Claude Code channel facts were not checked in this review

The flag, the `experimental["claude/channel"]` capability, the notification shape, the D9 registration forms and the Claude Code version (2.1.318) depend on the installed Claude Code. I had no shell and did not run `claude --version`. Task 1.2 is the runtime check, and it runs before any code that depends on those facts. No action is needed unless 1.2's note disagrees with the design.

### [PASS] Success criteria map to tasks

Each design success criterion was checked against a task. Live test: 11.1. Pinned protocol and pin test: 4.2, 4.3, 11.1. Channel event and marker strings: 5.2. Non-member and `cf` failure at start: 6.3, 8.2, 9.2. Resource states: 8.2. Watcher failures and busy-store retry: 6.5, 7.2, 9.2. Clean exit and SIGKILL: 6.5, 9.3, 11.1. Push confirmation: 6.4, 3.4. Re-created row after suspension: 6.3. Non-blocking tool calls: 9.2. `list` and `status`: 10.2. Config keys: 2.2. Contract-doc tests: 2.1, 10.1, 12.1. Session cleanup: 3.4. Checks: 13.2. 244 contract: 10.2. 240 unchanged: 13.2. The one gap is the note criterion (CONCERN above).

### [PASS] Facts the task file relies on hold in the repo

- `mcp>=2.3,<3` is pinned in `pyproject.toml:10`, as the design says.
- The SDK modules that 0.1 and 4.1 name exist: `connection.py`, `runner.py` (`serve_connection` at line 447, `serve_loop` at line 470) and `jsonrpc_dispatcher.py`.
- `Connection.notify` catches only `BrokenResourceError` and `ClosedResourceError` (lines 401–410), which is what the 7.2 pin states.
- These exist with the names the tasks use: `CF_GET_TIMEOUT_SECONDS` (`upstream/context_forge/project_of.py:33`), `BUSY_TIMEOUT_SECONDS` (`store/store.py:28`), `resolve_member`, `NotInProgram` and `NotAProject` (`operations/members.py`), `open_store` and `default_deps` (`wiring.py`), and `Deps.clock` (`operations/deps.py:51`).
- `ConfigError` is in `wiring.OPERATIONAL_ERRORS` (`wiring.py:95-101`), so 9.1's refuse-to-start path catches a missing key.
- `_serve` (`mcp/server.py:184`) and `main` (line 202) match 9.1's description. `main` already calls `load_config` for `check_deadline` (line 218).
- The live tier is excluded from bare runs (`pyproject.toml:64`), as the Context Summary says.
- 240's backup naming (`.pre-006`, `config.yaml.pre-240`, `~/.local/state/amoeba/backups/`) matches 241's P7.1.

Not confirmed: the installed `mcp` version (2.3.0). A dist-info glob found nothing. Task 0.1 checks it at run time.

### [PASS] Design rules hold: no deferral, every state has an exit, config and state are separate

- No task defers in-scope behavior. The `BLOCKED:` in 1.2 stops on a failed premise. It does not defer anything.
- Every state I traced has an exit. Pending presence ends at `resolved`. An unanswered push attempt is replaced at the next event. A killed row goes stale and is pruned by any heartbeat. A failed delete leaves a row that goes stale.
- Config keys go in config. `sessions` and the backups go in state.
- No task waits on real usage. No task merges or pushes.
- Test-with pairing holds: each implementation block is followed by its tests (2.1/2.2, 3.1–3.4, 4.1/4.2, 5.1/5.2, 6.1–6.5, 7.1/7.2, 8.1/8.2, 9.1–9.4, 10.1/10.2).
- The 12 `**Commit**:` markers (lines 72 to 261) sit at points where the work is complete. Section 5 is committed with 6.3, and section 7 with 8.

### Run Digest

- Response length: 11584 chars
- Response is newline-free: no
- Tool calls made: 25
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 26
- Tokens — prompt / cached / cache write / completion / reasoning: 897150 / 720663 / 176473 / 66337 / not computed
- Duration: 295.4 s
- Cost: $0.37 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
