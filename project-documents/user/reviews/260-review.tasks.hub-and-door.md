---
docType: review
layer: project
reviewType: tasks
slice: hub-and-door
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/260-tasks.hub-and-door.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261121
dateUpdated: 20261121
reviewedSha: abc869b98cf5c5c0347015797c8d090a5c8744fa
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 26
effort: xhigh
turns: 27
promptTokens: 1148267
cachedTokens: 917820
cacheWriteTokens: 230433
completionTokens: 99215
durationSeconds: 439.9
costUsd: 0.511438
costBasis: provider
runId: run-20261121-p5-613fe239
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: concern
    category: completability
    summary: "Task 2.1 tells the agent to fix version-pin tests from failures the new triggers also cause"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:115"
  - id: F002
    severity: concern
    category: completability
    summary: "The dropped-reply seam in 10.1b cannot work as written, because `handle_call` never raises"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:289"
  - id: F003
    severity: concern
    category: exception-handling
    summary: "Deliberate swallows in 11.2a and 11.2b do not name the exception or the logging call"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:321"
  - id: F004
    severity: concern
    category: sizing
    summary: "Task 13.3b bundles join and leave, with about a dozen branches, into one task"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:386"
  - id: F005
    severity: concern
    category: design-invariant
    summary: "Task 6.3 puts the set-aside refusal after `prepare_state_home`, which can still move a legacy store into the state home"
    location: "src/amoeba/operations/state_move.py:119"
  - id: F006
    severity: concern
    category: design-rule
    summary: "The displaced store's only exit is a person deleting files"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:237"
  - id: F007
    severity: note
    category: completability
    summary: "No step creates `client/errors.py`"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:193"
  - id: F008
    severity: note
    category: consistency
    summary: "17.3 does not record the new `operations` → `client.client_file` import edge"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:484"
  - id: F009
    severity: note
    category: completability
    summary: "Task 16.1's commit point has no full check gate"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:465"
  - id: F010
    severity: note
    category: operator-walkthrough
    summary: "12.3 gives no way out for an unreachable hub"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:357"
  - id: F011
    severity: note
    category: completability
    summary: "3.5's no-acting-machine test must open its store with plain `Store.open`"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:144"
  - id: F012
    severity: note
    category: sequencing
    summary: "0.1 requires a clean tree, and the task file was modified at session start"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:62"
  - id: F013
    severity: note
    category: deferral
    summary: "Design D2 accepts a degraded state in 260 that no test checks"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:175"
  - id: F014
    severity: note
    category: design-rule
    summary: "Backups sit outside the state directory, which departs from the state-directory rule"
    location: "project-documents/user/slices/260-slice.hub-and-door.md:578"
  - id: F015
    severity: note
    category: hallucination-trap
    summary: "3.2 and 3.4 place expected counts and file names beside the grep meant to find them"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:133"
  - id: F016
    severity: note
    category: proportionality
    summary: "The file is large but every task traces; two test items trace to design claims, not criteria"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md:182"
  - id: F017
    severity: pass
    category: coverage
    summary: "Every success criterion in the slice design maps to a task"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md"
  - id: F018
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with and commit markers hold"
    location: "project-documents/user/tasks/260-tasks.hub-and-door.md"
  - id: F019
    severity: pass
    category: facts
    summary: "Repo facts the task depends on check out"
    location: "src/amoeba/store/migrations.py:25"
  - id: F020
    severity: pass
    category: ci-gating
    summary: "The load test is gated in CI"
    location: ".github/workflows/ci.yml:39"
---

# Review: tasks — slice 260

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 2.1 tells the agent to fix version-pin tests from failures the new triggers also cause

The 2.1 triggers make every raw record insert in the existing suite abort. Line 106 says so. Line 115 then says to run `uv run pytest tests/store -q`, take the failing tests from its output, and change "only the version number". Most of that output will be trigger aborts that 3.2 to 3.4 fix, not version pins. An agent following the text could edit correct tests. The task should say to select only failures whose assertion is the schema version (expected 11, found 10) and to leave insert failures for 3.2 to 3.4.

### [CONCERN] The dropped-reply seam in 10.1b cannot work as written, because `handle_call` never raises

Line 289 calls `hooks.after_commit` after the commit. Line 290 says `handle_call` never raises to the caller. Line 366 and D18 (design line 532) need the hook to drop the reply, so the call gets no answer before the server is restarted. The task never says how a hook drops a reply. A hook that raises conflicts with line 290. A hook that returns a value does nothing at the HTTP layer. The task should name the mechanism, for example a test-only exception that passes the refusal path and makes `hub.app` close the connection without a reply. This test covers a required criterion, so the choice must be made before 10.1b is written.

### [CONCERN] Deliberate swallows in 11.2a and 11.2b do not name the exception or the logging call

Line 321 ("Step 8 failures are logged at error level and the start goes on") and line 325 (the backup loop "logs a failure at error level") both catch an error and continue. The project rule requires a re-raise after `logger.exception`, a named exception with a comment explaining the swallow, or a documented process-boundary handler. Neither line names `BackupError`, `logger.exception` or a reason. Without those, the agent could write `except Exception:` with `logger.error`.

### [CONCERN] Task 13.3b bundles join and leave, with about a dozen branches, into one task

13.3b covers join with and without the flag, both re-run paths, `join --address`, and `leave`'s three steps plus the mark-clear branch. Section 13.5 then has 16 test bullets for it. Split it into 13.3b for `join` and 13.3c for `leave`, each with its own tests before the section commit. 13.2 has the same density (set-aside, put-back, displaced store) and could be split too.

### [CONCERN] Task 6.3 puts the set-aside refusal after `prepare_state_home`, which can still move a legacy store into the state home

`open_state_store` calls `prepare_state_home(layout)` on line 119, before `Store.open` on line 120. `prepare_state_home` moves a legacy store into the state home (lines 97 to 98). Task 6.3 line 201 says to refuse "before Store.open". An implementer will naturally place that check after line 119. D4 says no command creates a store beside a set-aside store, and this order allows it when a legacy store exists. The set-aside refusal should run before `prepare_state_home`, as the client-file refusal does.

### [CONCERN] The displaced store's only exit is a person deleting files

The Amoeba rule "every state has an exit" requires that a state ends "with nobody editing files", and it rejects "wait for a person who has no command to act with". D4 step 1 writes a `displaced-` store and says "whoever placed it decides what to do with it". Task 13.2 implements that, so no command ends the state. The design does say why the state is bounded, which meets the second clause of the rule but not the first. The design should either name a command or cleanup that ends a displaced store, or state that the bound is the exit. This is a design-rule question, so the PM should decide it.

### [NOTE] No step creates `client/errors.py`

6.2 introduces `ClientFileError`, and 12.1 imports `HubUnreachableError` from `client.errors`. The Context Summary (line 46) names that module and 17.3 records it, but no step creates it. Add "create `client/errors.py` with the four client errors" to 6.2.

### [NOTE] 17.3 does not record the new `operations` → `client.client_file` import edge

The Context Summary (line 51) allows `operations` to import `client.client_file` for 6.3. The design's import rules do not list that edge. Add it to the design-change list in 17.3.

### [NOTE] Task 16.1's commit point has no full check gate

The commit marker follows 16.1, but its success criterion is "files exist; the hub.yaml.example test still passes", not the four checks. Make it "checks pass", as the other sections do.

### [NOTE] 12.3 gives no way out for an unreachable hub

The certificate error names `join --address` and the re-invite path (line 358). The unreachable error names only the address and the time spent. A joined machine with a mistyped address in `client.yaml` does have an exit, `join --address`, which makes no hub call, but the error never mentions it. Add the way on to the unreachable text, matching line 358.

### [NOTE] 3.5's no-acting-machine test must open its store with plain `Store.open`

3.4 replaces `Store.open` with the helper, which sets an acting machine. 3.5's first test needs a store without one, so it must call plain `Store.open`. The task does not say so. One clause fixes it.

### [NOTE] 0.1 requires a clean tree, and the task file was modified at session start

At session start the task file showed as modified and uncommitted. The "no other uncommitted change" check in 0.1 cannot pass until this document's planning commit lands. The planning commit comes at the end of this review loop, so this is an ordering note only.

### [NOTE] Design D2 accepts a degraded state in 260 that no test checks

A running `amoeba-mcp` on a joined machine stops presence and push, and the design calls that "acceptable in 260". The tick is excluded from 260's scope (line 65), so this is not in-scope behaviour being deferred. No task checks that the tick fails cleanly and logs once. Consider one test in 14.4. The PM should confirm the accepted state.

### [NOTE] Backups sit outside the state directory, which departs from the state-directory rule

The Departures row records that backups live in `backup_dir`, outside the state directory. The rule that databases live in the state directory has no exception clause, and the PM added it. The departure has a reason (another disk) and the task file implements it. The PM should confirm it rather than treat it as settled.

### [NOTE] 3.2 and 3.4 place expected counts and file names beside the grep meant to find them

Line 133 ("16 statements at design time, in store/sql.py, …") and line 141 list what the grep should return. I checked both lists against the repo and they are correct today. The trap is that an empty grep would let the agent copy the list. Replace both with "if the grep finds no statement, stop and report it."

### [NOTE] The file is large but every task traces; two test items trace to design claims, not criteria

Seventeen sections and roughly 30 new source modules and 35 test files. Every task traces to a decision or criterion, so no split is needed. The two items that trace only to design claims are the `EXPLAIN QUERY PLAN` check in 5.3 (D9's index) and the concurrent-writer case in 9.2 (D15). Both are cheap. Cut them only if time runs short.

### [PASS] Every success criterion in the slice design maps to a task

The two-machine criteria are 15.2 and 15.3. Repeat and kill are 10.2, 12.4 and 15.5. The startup refusals are 11.4, noise is 15.5, and load is 15.6 with the figures recorded in 17.3. The container is 16.2, the five documents and contract tests are 17.1, the 261 extension test is 10.2, and the PM install is 7.4 with the 3.4 baseline. No criterion lacks a task, and no task lacks a criterion or design decision. The "which machines are behind" display is assigned to 263 by the parent architecture (`project-documents/user/architecture/260-slices.the-hub.md:123`), so leaving it out here is not a deferral.

### [PASS] Sequencing, test-with and commit markers hold

Dependencies run forward with no cycles. The `OPERATIONAL_ERRORS` changes come in the right order: 1.3, 6.2, 12.3 and 13.1 add members before 10.1a moves the tuple. Each implementation section ends with its test task. Commit markers sit where checks pass, and sections 2 and 3 share one marker, as the task states.

### [PASS] Repo facts the task depends on check out

Verified: schema files 001 to 010 and `EXPECTED_SCHEMA_VERSION` = 10. `OPERATIONAL_ERRORS` holds the five named members (`wiring.py:84-90`). 16 insert statements sit in the six files named in 3.2. `wiring.py` is 325 lines. `Store.open` has one caller in `src` (`state_move.py:120`). `tests/test_contract_docs.py:101` pins 14 tables, so 18 is right. `uvicorn` 0.54.0 matches D14. `anyio` and `pydantic` are already declared (`pyproject.toml:9,11`). The six "at design time" test files named in 3.4 all exist.

### [PASS] The load test is gated in CI

The `Tests` step runs bare `uv run pytest` (`ci.yml:39-40`), and `addopts` ignores only `tests/live` (`pyproject.toml:64`). So `tests/load/test_door_load.py` runs in CI. Task 15.6 states this and asks for a collect-only check, so the gate is explicit and it holds. If the PM wants a separate CI wiring task, add one; otherwise none is needed.

### Run Digest

- Response length: 13069 chars
- Response is newline-free: no
- Tool calls made: 26
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 27
- Tokens — prompt / cached / cache write / completion / reasoning: 1148267 / 917820 / 230433 / 99215 / not computed
- Duration: 439.9 s
- Cost: $0.51 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 20
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 20
- Finding-shaped matches — surviving validation: 20
