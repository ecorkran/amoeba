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
reviewedSha: 323ad5c4b0d876eea5a78f007d431f4c46849de7
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 23
effort: xhigh
turns: 24
promptTokens: 1431314
cachedTokens: 1230472
cacheWriteTokens: 200822
completionTokens: 60072
durationSeconds: 278.1
costUsd: 0.400058
costBasis: provider
runId: run-20261115-tasks-plan-962527a1
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: concern
    category: recovery-safety
    summary: "Restore path names \"the pre-merge tool\" but no step records its commit"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:284"
  - id: F002
    severity: concern
    category: placeholder-trap
    summary: "Version numbers sit next to lookup steps with no branch for unexpected output"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:277"
  - id: F003
    severity: concern
    category: spec-amendment
    summary: "Design amendment list (12.2) misses three places that conflict with Phase 7"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:303-308"
  - id: F004
    severity: concern
    category: contract-docs
    summary: "Task 5.1 and 8.1 add JSON fields without the doc entries the task's own rule requires"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:129"
  - id: F005
    severity: concern
    category: ci-gating
    summary: "Load test gate depends on collection rules, not on a named CI step"
    location: ".github/workflows/ci.yml:39-40"
  - id: F006
    severity: concern
    category: test-coverage
    summary: "Two named design behaviors have no test"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:154-158"
  - id: F007
    severity: concern
    category: task-size
    summary: "Task 9.1 bundles six separate concerns"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:190-194"
  - id: F008
    severity: note
    category: api-detail
    summary: "`serve_pinned` signature omits the `lifespan_state` argument the SDK requires"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:113-115"
  - id: F009
    severity: note
    category: ops-walkthrough
    summary: "Walkthrough dead ends: no clearing step for the BLOCKED, and an undo that is forward-only"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:277"
  - id: F010
    severity: note
    category: ordering
    summary: "Session ordering has no tiebreak; the test avoids the case"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:101"
  - id: F011
    severity: note
    category: ci-gating
    summary: "Load test asserts one-second answer bounds on a shared CI runner"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:204"
  - id: F012
    severity: pass
    category: verification
    summary: "SDK behavior task 7.2 pins matches the installed mcp 2.3.0"
    location: ".venv/lib/python3.13/site-packages/mcp/server/connection.py:401-410"
  - id: F013
    severity: pass
    category: prerequisites
    summary: "Prerequisite gate is correct: 240 is not built in the repo yet"
    location: "src/amoeba/store/migrations.py:25"
  - id: F014
    severity: pass
    category: coverage
    summary: "Every design success criterion maps to a task"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:268"
  - id: F015
    severity: pass
    category: sequencing
    summary: "No scope creep; sequencing and test pattern are sound"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:50"
  - id: F016
    severity: pass
    category: design-rules
    summary: "Amoeba design rules hold for the live store and the harness"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:274"
  - id: F017
    severity: pass
    category: verification
    summary: "The stdio smoke test already locates the installed script in a CI-safe way"
    location: "tests/mcp_server/test_stdio_smoke.py:27"
---

# Review: tasks — slice 241

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Restore path names "the pre-merge tool" but no step records its commit

P7.3 says to "reinstall the pre-merge tool from a worktree of the target", but nothing records which commit that is. P7.1 (lines 278-279) writes only the two backup paths into the slice notes. The design's Special Considerations (line 308) says "uv tool install --force from the previous commit". Once the merge lands, the target's pre-merge SHA is gone unless it was captured first. Recommend: record `git rev-parse {target}` in the slice notes before the Phase 7 merge, and have P7.3 name that SHA. P7.3 also waits "for at most the config's `answering_wait_seconds`" (line 284). That is a 240 key for answering waits, reused as a process-stop bound. Name a constant for it.

### [CONCERN] Version numbers sit next to lookup steps with no branch for unexpected output

P7.1 says the version query "prints 6". 13.1 (line 261) says "If the copy reads 5 … Otherwise it migrates 6 to 7". The Amoeba rule against hardcoded example values applies here: an empty or unexpected result can be filled in from the nearby literal. Neither step says what to do when the query returns nothing or a value outside the expected ones. Recommend: state the expected value once, in the form the precondition uses, and require BLOCKED with the raw output for any other result, including an empty one.

### [CONCERN] Design amendment list (12.2) misses three places that conflict with Phase 7

Task 12.2 adds two lines to the design's Departures section. Three other places still describe the old procedure. Development Approach step 7 (line 303) says "the live test, then the live-store migration". Special Considerations (line 308) says to install "from the slice branch" and to delete the backups "at slice integration (Phase 7), after the review passes". P7.2 installs from the target, and P7.4 deletes the backups after the read-back. An implementing agent gets two procedures. Recommend: 12.2 amends step 7 and Special Considerations too.

### [CONCERN] Task 5.1 and 8.1 add JSON fields without the doc entries the task's own rule requires

Line 43 says each task that adds a table, column, JSON field or config key adds its entry then, and Task 12 writes the prose. 5.1 adds the channel event's `content` and `meta` fields, and 8.1 adds the `amoeba://inbox` JSON (`member`, `as_of_seq`). Neither task adds a docs entry; only 12.1 does. The design's Technical Requirements say `tests/test_contract_docs.py` must pass for every JSON field. Recommend: add the entries in 5.1 and 8.1, as line 43 says.

### [CONCERN] Load test gate depends on collection rules, not on a named CI step

9.4 relies on `pyproject.toml` (`addopts = ["--ignore=tests/live"]`, line 64) and on the one CI "Tests" step, which runs bare `uv run pytest` (line 40). I confirmed both: the load test does run today. But the gate is implicit. Nothing in CI names `tests/load`, and a later change to `addopts` or to the CI command would drop it without notice. Recommend: add a named CI step for `tests/load` in `ci.yml`, or have 9.4 write one.

### [CONCERN] Two named design behaviors have no test

(a) D6 makes confirmation "sticky for the process". 6.4's test list covers confirm, no-attempt, limit and replacement, but not a later `inbox` call with no attempt leaving an earlier confirmation in place. (b) D3 says a `StoreError` during member lookup behaves like a non-member through the top-level handler: logged, no row, no loop. 6.5 tests `cf` failure and timeout, and a corrupt-store error from the heartbeat, but not a `StoreError` from the lookup. Add one test for each.

### [CONCERN] Task 9.1 bundles six separate concerns

9.1 covers the capability declarations, four resource-handler registrations, the `main()` config read and refusal, `_serve` wiring, `call_tool` logging and `PresenceState` threading, the INSTRUCTIONS paragraph, and updates to existing test call sites. Recommend splitting it into two tasks: (a) capabilities, handler registration and INSTRUCTIONS; (b) `main()` config, `_serve` wiring and `call_tool`. Each keeps its own success line.

### [NOTE] `serve_pinned` signature omits the `lifespan_state` argument the SDK requires

4.1 says `serve_pinned` "mirrors the SDK's serve_loop and nothing else", but its signature is `(server, streams, init_options, background)`. `serve_connection` requires a keyword-only `lifespan_state` (`.venv/lib/python3.13/site-packages/mcp/server/runner.py:447-453`), and `serve_loop` takes it too (runner.py:470-477). A junior agent will have to work out the argument itself. Name it in the signature.

### [NOTE] Walkthrough dead ends: no clearing step for the BLOCKED, and an undo that is forward-only

P7.1's BLOCKED ("240 not migrated live") names no action that clears it, such as running 240's live migration and then re-running P7 from P7.1. The design's "Undo" entry (line 325) names the one dead end, that going back to pre-241 code after Phase 7 needs a PM-designated DROP. The design reports it, so this is acknowledged, not a defect. P7.4 then deletes the backups, which removes the only other restore path.

### [NOTE] Session ordering has no tiebreak; the test avoids the case

3.3 orders `live_sessions` by `started_at`, and D8 says "oldest first". Neither specifies a tiebreak. 3.4 tests only distinct `started_at` values. Two servers starting in the same second would tie, so `list -j` and `status` could disagree. Recommend `started_at, session_id` in 3.3, and a test with equal `started_at`.

### [NOTE] Load test asserts one-second answer bounds on a shared CI runner

9.4 runs 12 presence runs and asserts that tool calls and `ping` answer within one second, on the same runner that runs the rest of the suite. Latency bounds are what the load-test rule asks for, so keep them. But say what happens on a slow runner: a fixed bound with no stated tolerance will flake.

### [PASS] SDK behavior task 7.2 pins matches the installed mcp 2.3.0

`Connection.notify` catches only `anyio.BrokenResourceError` and `anyio.ClosedResourceError` and logs at debug. Other exceptions propagate. 7.2's test (a closed stream does not raise; any other exception does) matches this. The design's D2 says "never raises", which is too strong; 12.2 already corrects that wording.

### [PASS] Prerequisite gate is correct: 240 is not built in the repo yet

The schema directory holds 001 to 005, and `EXPECTED_SCHEMA_VERSION` is 5. 0.1's BLOCKED check is therefore needed, and the slice cannot start until 240 lands. The other references check out: `wiring.open_store`, `wiring.default_deps`, `wiring.load_config`, `wiring.check_deadline`, `operations/members.py`'s `resolve_member`, `MemberStatus`, `tests/load/test_report_release_load.py`, the pty and live helpers, and the four contract tests. `server.py` is 221 lines and still calls `server.run` (line 187), as the design says.

### [PASS] Every design success criterion maps to a task

Functional, technical and integration criteria each map to a task: the live tier (11.2), the protocol pin (4.2), the channel event (5.2), non-member start (9.2), resource states (8.2), watcher failures (9.2), exit and SIGKILL (9.3), push confirmation (6.4), re-creation (6.3), non-blocking (9.2), list and status (10.2), config (2.2), contract docs (12.1), the cleanup test (3.4), and the 244 contract (10.2). 13.2 requires each criterion to name a passing test in a note.

### [PASS] No scope creep; sequencing and test pattern are sound

Every task traces to a design section or a required step. Each implementation task is followed by its tests. No task depends on a later one. The commit markers fall at working, tested points, and none is a checkbox. Branching follows the integration-target rules. No task writes a merge or push. The one task file is the right size for the slice: one file, about 45 subtasks, no split needed.

### [PASS] Amoeba design rules hold for the live store and the harness

The live store and config are designated for migration, with a backup and a restore path first. No task defers in-scope behavior, and no step waits on real usage. The harness fails with the last screen, and every wait constant lives in one module.

### [PASS] The stdio smoke test already locates the installed script in a CI-safe way

The existing test resolves `amoeba-mcp` beside `sys.executable`. 9.3 can reuse that, so its real-process tests run under bare `uv run pytest` in CI without a PATH assumption.

### Run Digest

- Response length: 12830 chars
- Response is newline-free: no
- Tool calls made: 23
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 24
- Tokens — prompt / cached / cache write / completion / reasoning: 1431314 / 1230472 / 200822 / 60072 / not computed
- Duration: 278.1 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17

## Resolution

- [concern] Restore path records no commit: fixed. New P7.0 writes `git rev-parse {target}` into the slice notes just before the merge (BLOCKED on any non-SHA output); P7.3 reinstalls from that commit and states its own 60-second stop wait instead of borrowing `answering_wait_seconds`.
- [concern] Version numbers beside lookup steps: fixed. P7.1 and 13.1 state the expected version once (the last migration before `007_sessions.sql`) and any other result, including empty, is `BLOCKED:` with the raw output.
- [concern] 12.2 misses places that conflict with Phase 7: fixed. 12.2 also amends Development Approach step 7 and Special Considerations (install from the target after the merge, backups deleted after the read-back).
- [concern] 5.1 and 8.1 lack doc entries: fixed. Each adds its `docs/mcp-server.md` entry in the same task.
- [concern] Load test gate implicit: dropped; bare `uv run pytest` already collects `tests/load`.
- [concern] Two design behaviors untested: fixed. 6.4 adds sticky confirmation across a later no-attempt `inbox` call; 6.5 adds a `StoreError` from the member lookup.
- [concern] 9.1 bundles six concerns: dropped; one task at this size is acceptable.
- [note] `serve_pinned` omits `lifespan_state`: fixed. 4.1's signature takes keyword-only `lifespan_state` (checked against `mcp/server/runner.py`).
- [note] Walkthrough dead ends: dropped; the BLOCKED reason is self-explanatory and the forward-only undo is already acknowledged in the design.
- [note] Session ordering has no tiebreak: fixed. 3.3 orders by `started_at, session_id`; 3.4 tests equal `started_at`.
- [note] One-second bounds on a shared runner: dropped; no flake observed to justify a tolerance.
