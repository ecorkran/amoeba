---
docType: review
layer: project
reviewType: tasks
slice: push-and-presence
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/241-tasks.push-and-presence.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: c8508cb3b5169a8a0a42fb3867f010f259097f5c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
effort: xhigh
turns: 25
promptTokens: 1567395
cachedTokens: 1371772
cacheWriteTokens: 195601
completionTokens: 73346
durationSeconds: 333.7
costUsd: 0.435056
costBasis: provider
runId: run-20261115-tasks-plan-962527a1
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Task 6.3 runs the push loop that task 7 builds"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:149"
  - id: F002
    severity: concern
    category: verification
    summary: "Success check 13.2 contradicts tasks 3.1 and 10.1"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:253"
  - id: F003
    severity: concern
    category: verification
    summary: "Test path in 3.4 does not exist"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:102"
  - id: F004
    severity: concern
    category: coverage
    summary: "The integration criterion that 244 gets the same answer `list` shows has no test"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:211"
  - id: F005
    severity: concern
    category: testing
    summary: "Live test Session 3 has no fixture"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:223"
  - id: F006
    severity: concern
    category: testing
    summary: "The load-test rule for concurrency paths is not met"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:194"
  - id: F007
    severity: concern
    category: commits
    summary: "Commit markers sit after every top-level task"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:135"
  - id: F008
    severity: concern
    category: format
    summary: "The Phase 7 hand-off has no checkboxes, so its live-store steps are untracked"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:258"
  - id: F009
    severity: concern
    category: operations
    summary: "After Phase 7 there is no restore path that does not need PM designation"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:266"
  - id: F010
    severity: note
    category: scope
    summary: "The Phase 7 timing and the 13.1 rehearsal are not recorded as departures"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:263"
  - id: F011
    severity: note
    category: scope
    summary: "The CHANGELOG entry is not in the design"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:238"
  - id: F012
    severity: note
    category: verification
    summary: "Task 0.1's SDK check: `serve_connection` is unverified"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:53"
  - id: F013
    severity: note
    category: verification
    summary: "The design's \"`notify` never raises\" is broader than the SDK code"
    location: ".venv/lib/python3.13/site-packages/mcp/server/connection.py:401"
  - id: F014
    severity: note
    category: sizing
    summary: "Section 6 is the largest section and the likeliest to need a split"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:137"
  - id: F015
    severity: note
    category: testing
    summary: "Ordering of live sessions is not tested"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:98"
  - id: F016
    severity: note
    category: sizing
    summary: "The Context Summary restates the design"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:36"
  - id: F017
    severity: note
    category: design-rules
    summary: "9.1 loads config in `_serve`; the async-path rule applies if `_serve` is async"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:189"
  - id: F018
    severity: note
    category: sequencing
    summary: "Task 1.2's outcome branches the downstream tasks"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:220"
  - id: F019
    severity: pass
    category: coverage
    summary: "Success criteria map to tasks"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md"
  - id: F020
    severity: pass
    category: design-rules
    summary: "The Amoeba design rules hold in the tasks"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md"
  - id: F021
    severity: pass
    category: sequencing
    summary: "The 0.1 prerequisite gate matches the repo"
    location: "project-documents/user/tasks/241-tasks.push-and-presence.md:52"
---

# Review: tasks — slice 241

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Task 6.3 runs the push loop that task 7 builds

6.3 has `run_presence` run "the heartbeat loop and the push loop (task 7) in one child task group". 6.4 then tests that handler, the clean exit and heartbeat failures. The push loop is 7.1, so the section 6 commit (line 158) is not a working point, and 6.4 cannot pass in order. The 6.4 tests also trail 6.1 to 6.3 as one block rather than beside their implementation. Fix: have `run_presence` take the push loop as a parameter, pass a no-op in section 6's tests, and wire the real watcher in 7.1. The design's Data Flow (line 98) puts both loops in one group, so the change belongs in the task order, not the design.

### [CONCERN] Success check 13.2 contradicts tasks 3.1 and 10.1

13.2 requires `git diff {target} --stat` to touch no 240 function signature and 240's tests to pass as written. But 3.1 edits the stale-version assertions in `tests/store/test_migrations.py` and the schema pin in `test_schema_holds_no_mirrored_state.py`. 10.1 adds `sessions` to `MemberStatus` (a 240 model) and makes the status operation fill it, which design D8 requires. The check cannot pass as written. Restate it as: 240 behavior unchanged; the named touchpoints (`MemberStatus.sessions`, the status fill, version pins) are the only edits; 240's tests pass with those pins updated. The design's Integration Requirements need the same correction.

### [CONCERN] Test path in 3.4 does not exist

`tests/test_members_queried_in_one_place.py` is not in the repo. The file is `tests/store/test_members_queried_in_one_place.py`. Correct the path. The "or its siblings" hedge leaves the junior to search.

### [CONCERN] The integration criterion that 244 gets the same answer `list` shows has no test

The design's Integration Requirements say `live_member_ids` returns the same answer `list` shows. 3.4 tests `live_member_ids` alone, and 10.2 tests `list` alone. Nothing asserts that they agree. Add a test that seeds a confirmed live row, an unconfirmed row, a stale row and a removed member's row, then asserts that the members `live_member_ids` returns equal the members `list` shows with `push_confirmed_at` set.

### [CONCERN] Live test Session 3 has no fixture

"A directory outside any member" is not specified. It could be a project that is not a member (NotInProgram) or a directory that is not a project (NotAProject). D9 says the repo's `.mcp.json` is what loads the server, so this directory needs its own registration or the session never starts the server. The task should name the directory, its git state, and how the channel server is registered there. As written, the junior must choose.

### [CONCERN] The load-test rule for concurrency paths is not met

`.claude/rules/python.md` requires at least one `tests/load/` test for any concurrency path. Its assertions must cover latency, throughput or resource bounds, because unit and integration tests cannot catch event-loop starvation. This slice adds the watcher, heartbeat and store worker threads beside the serve loop. The one blocked-opener check in 9.2 runs in-process under no realistic load. Add a task that writes a `tests/load/` test: concurrent `ping`, `tools/list` and tool calls against a member server, with the watcher and heartbeat running at short intervals and a slow store worker, asserting the latency bound. CI gating already exists: `pyproject.toml` ignores only `tests/live`, and `.github/workflows/ci.yml:40` runs bare `uv run pytest`, so a file in `tests/load/` runs in CI with no separate CI task. The task should say the file must not sit under `tests/live` or carry an opt-in marker.

### [CONCERN] Commit markers sit after every top-level task

The file has 13 markers, one per section 1 to 13. Section 5 (the channel event) has no consumer until section 7, and section 8 (the resource handlers) is not registered on the server until section 9, so neither commit is a working point on its own. Section 13's marker (line 256) would commit only the rehearsal notes and a walkthrough edit, and its `test:` prefix describes no test change. Merge 5 into 6 to 7 and 8 into 9. Either drop 13's marker or make its commit `docs:` with the walkthrough change as its content.

### [CONCERN] The Phase 7 hand-off has no checkboxes, so its live-store steps are untracked

The document conventions require a `[ ]` checkbox on every item of a task file. The hand-off's steps (backup, install, key edit, read-back, the restore-path note, backup removal) are plain bullets, so nothing tracks them, yet the design's Special Considerations make them required. Give each step a checkbox under a heading that says it starts after the Phase 7 merge. The merge stays a precondition, not a step.

### [CONCERN] After Phase 7 there is no restore path that does not need PM designation

The hand-off deletes both backups. After that, returning to pre-241 code means `DROP TABLE sessions` and setting `schema_meta.version` to 6 on the live store. CLAUDE.md's destructive-statement rule requires the PM's explicit designation for that. The design's Operator Walkthrough (Undo) reports this as a dead end and calls it "by design", so it is reported but not resolved. The Amoeba rules require every undo path to be named. Either keep the pre-007 backup for the life of the store with a named cleanup, or record the exact PM-designated rollback statements in the slice notes before the backup is removed.

### [NOTE] The Phase 7 timing and the 13.1 rehearsal are not recorded as departures

The design's Special Considerations say to install the slice's code from the slice branch before the merge. The task installs from the target after the merge and gives its reason inline. The 13.1 copy rehearsal is also not in the design. Both choices are sound, but the design's Departures list does not record them. Add both to 12.2's amendments.

### [NOTE] The CHANGELOG entry is not in the design

`CHANGELOG.md` exists, and the design does not ask for a slice entry. Keep it if the project convention is an entry per slice. The behavior-change label on the three keys is useful either way.

### [NOTE] Task 0.1's SDK check: `serve_connection` is unverified

In the repo's `.venv` I confirmed `Connection.for_loop` (`connection.py:300`), `Connection.initialized` (an `anyio.Event`, line 212), `Connection.notify` and `JSONRPCDispatcher` (`mcp/shared/jsonrpc_dispatcher.py:264`). I did not find `serve_connection` in the three files I searched: `mcp/server/lowlevel/server.py`, `mcp/server/mcpserver/server.py` and `mcp/shared/dispatcher.py`. Directory-level searches under `.venv` return nothing even for symbols I could read, so this is unverified, not confirmed absent. 0.1 must locate it before 4.1 uses it.

### [NOTE] The design's "`notify` never raises" is broader than the SDK code

`Connection.notify` catches only `anyio.BrokenResourceError` and `anyio.ClosedResourceError`. Other exceptions from the outbound propagate. The 7.2 pin should assert exactly the closed-stream case, not the general claim.

### [NOTE] Section 6 is the largest section and the likeliest to need a split

Section 6 has four subtasks covering state, resolution, the heartbeat, client name, push confirmation, the top-level handler, clean exit, and a dozen test cases. The design already allows a split when `presence.py` passes about 300 lines. Decide the split now: heartbeat and push confirmation in their own module. That also makes the 6.3 fix cleaner.

### [NOTE] Ordering of live sessions is not tested

3.3 and design D8 say `live_sessions` and `MemberStatus.sessions` are oldest first. No test in 3.4 or 10.2 asserts the order. Add one assertion.

### [NOTE] The Context Summary restates the design

Lines 36 to 46 repeat the design's module list, constants and check commands. Cut them to pointers so the two documents cannot drift.

### [NOTE] 9.1 loads config in `_serve`; the async-path rule applies if `_serve` is async

`.claude/rules/python.md` requires any sync work inside an async function to finish in under 1 ms worst case, or to move off the loop. I did not check whether `_serve` is async. If it is, the config load needs to run off the loop, and the task should say so.

### [NOTE] Task 1.2's outcome branches the downstream tasks

If 1.2 adopts the `--mcp-config` or user-scope form, 11.1's "the `.mcp.json` of the form task 1.2 adopted" and the alias text in 12.1 change. Have 1.2's note record which form was adopted and list the downstream text that changes, so the junior does not guess.

### [PASS] Success criteria map to tasks

Every functional and technical criterion has a named test. The live test is 11.1. The protocol pin is 4.2. The channel event is 5.2. The non-member and `cf`-failure cases are 6.4, 9.2 and 11.1. Resource states are 8.2. Watcher failures are 7.2 and 9.2. Clean exit and SIGKILL are 9.3. Push confirmation and the suspended-process re-create are 6.4 and 3.4. The blocked-opener latency check is 9.2. `list` and `status` are 10.2. The config rules are 2.2. The docs are 12.1, with the contract tests named in 13.2. The one gap is the 244-versus-`list` consistency test above. The size fits the slice: 13 sections, 33 subtasks, one file.

### [PASS] The Amoeba design rules hold in the tasks

There is no deferral and no task waits on real-world events. Every state has an exit: presence resolves in a `finally`, push attempts are cleared, and rows are pruned. State lives in the store and config in the config file. The BLOCKED gates in 0.1 and 1.2 are real preconditions, not approvals, and 1.2 re-checks the dated facts. The one open dead end is the post-merge rollback above.

### [PASS] The 0.1 prerequisite gate matches the repo

`src/amoeba/store/schema/` holds 001 to 005 only, and `tests/store/test_migration_006.py` is absent. That is consistent with 240 not yet being built, so 0.1's BLOCKED path is the right gate.

### Run Digest

- Response length: 14390 chars
- Response is newline-free: no
- Tool calls made: 24
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 25
- Tokens — prompt / cached / cache write / completion / reasoning: 1567395 / 1371772 / 195601 / 73346 / not computed
- Duration: 333.7 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 21
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 21
- Finding-shaped matches — surviving validation: 21
