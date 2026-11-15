---
docType: review
layer: project
reviewType: tasks
slice: waking
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/244-tasks.waking.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: a06f5e6bdd8a4ea3e30a64a10a148562902b9593
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 11
effort: xhigh
turns: 12
promptTokens: 461753
cachedTokens: 287112
cacheWriteTokens: 174633
completionTokens: 90740
durationSeconds: 389.7
costUsd: 0.403363
costBasis: provider
runId: run-20261115-tasks-plan-962527a1
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "Permitted edits to existing tests are listed three different ways"
    location: "project-documents/user/tasks/244-tasks.waking.md:49"
  - id: F002
    severity: concern
    category: conventions
    summary: "The agent-CLI example in 9.1 is a hallucination trap"
    location: "project-documents/user/tasks/244-tasks.waking.md:218"
  - id: F003
    severity: concern
    category: coverage
    summary: "No test checks that a start failure's `detail` stays out of the `status` document or the renderer"
    location: "project-documents/user/tasks/244-tasks.waking.md:190"
  - id: F004
    severity: concern
    category: coverage
    summary: "The message-text criterion is tested on the wrapper's spawn, not on the command"
    location: "project-documents/user/tasks/244-tasks.waking.md:167"
  - id: F005
    severity: concern
    category: sizing
    summary: "Section 6 bundles seven subtasks across three modules and 240's `send` under one commit"
    location: "project-documents/user/tasks/244-tasks.waking.md:148"
  - id: F006
    severity: concern
    category: design-consistency
    summary: "The live-step order and install source contradict the design"
    location: "project-documents/user/tasks/244-tasks.waking.md:252"
  - id: F007
    severity: concern
    category: completability
    summary: "The live tier does not say how `amoeba` reaches the fixture agent or how the CLI is located"
    location: "project-documents/user/tasks/244-tasks.waking.md:208"
  - id: F008
    severity: concern
    category: sizing
    summary: "Proportionality: three items go beyond what the success criteria need"
    location: "project-documents/user/tasks/244-tasks.waking.md:229"
  - id: F009
    severity: note
    category: completability
    summary: "5.3 leaves two points open: the `wrapper_failed` exit code, and whether `wake-run` is hidden"
    location: "project-documents/user/tasks/244-tasks.waking.md:140"
  - id: F010
    severity: note
    category: test-scope
    summary: "The sweep test's \"live\" case cannot occur under default values"
    location: "project-documents/user/tasks/244-tasks.waking.md:173"
  - id: F011
    severity: note
    category: completability
    summary: "The `list members` output for a member with no command is unspecified"
    location: "project-documents/user/tasks/244-tasks.waking.md:118"
  - id: F012
    severity: note
    category: completability
    summary: "The timing tests need a short timeout under a fake clock"
    location: "project-documents/user/tasks/244-tasks.waking.md:136"
  - id: F013
    severity: note
    category: completability
    summary: "`EXPECTED_SCHEMA_VERSION` is named but its file is not"
    location: "src/amoeba/store/migrations.py:25"
  - id: F014
    severity: note
    category: coverage
    summary: "The TTL and sender-notice part of the limit criterion has no test in this slice"
    location: "project-documents/user/slices/244-slice.waking.md:283"
  - id: F015
    severity: pass
    category: coverage
    summary: "Every functional, technical and integration criterion maps to a task, apart from the two partial gaps above"
    location: "project-documents/user/tasks/244-tasks.waking.md"
  - id: F016
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit points are sound"
    location: "project-documents/user/tasks/244-tasks.waking.md:76"
  - id: F017
    severity: pass
    category: design-rules
    summary: "Design rules hold: no deferral, every state has an exit, and the operator walkthrough finds no dead end"
    location: "project-documents/user/slices/244-slice.waking.md:348"
  - id: F018
    severity: pass
    category: verification
    summary: "Named helpers, paths and the `AMOEBA_HOME` layout check out against the source"
    location: "src/amoeba/operations/state_move.py:117"
---

# Review: tasks — slice 244

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Permitted edits to existing tests are listed three different ways

Line 49 says only tasks 1.1, 4.4 and 6.1 change existing assertions. Line 244 (10.2) names 2.1, 4.4 and 6.1. Neither matches the work. Task 1.1 edits no test (1.2 edits only fixture keys). Task 2.1 (line 84) updates stale-version assertions and the schema pin. Task 6.7 (line 178) changes the existing 240 timing test's sum and assertion, and no list names it. As written, the 10.2 diff check fails on a legitimate edit, and an implementer cannot tell which edits are allowed. The design's Integration Requirements (line 299) also omit the version pins. Put one list of every permitted existing-assertion edit in the context summary, covering the version pins (2.1), the timing sum (6.7), `resolve_recipient` (6.1), the `add` flag list (4.4), and any 240 test that pins the whole `send -j` document once `wake_problem` is added (6.1). Make 10.2 cite that list.

### [CONCERN] The agent-CLI example in 9.1 is a hallucination trap

The step says to run the agent CLIs "the docs will name (for example `claude --help`, `codex --help`…)" and copy their flags. The example names sit beside an instruction to retrieve a value, and that source can come back empty: no agent CLI is installed, or the docs name none. The step gives no fallback, so the nearest plausible tokens fill the gap. The design (line 230) says the example is a script command. Remove the example names, name the source (the `--help` output of each agent CLI found on PATH), and say what to write when none is found (the fixture script command alone).

### [CONCERN] No test checks that a start failure's `detail` stays out of the `status` document or the renderer

Design line 282 requires that a secret-like marker in the executable name appears in no row, `list` line or `status` document. Task 5.2 (line 136) checks the row, the wrapper's log line and the wrapper's result. The 7.2 status tests (line 190) have no marker case. The 7.4 marker test (line 196) puts the marker in the command text, which the contract allows to show, so it does not test `detail`. Add a case to 7.2 and 7.4: a `start_failed` row from a marker-named executable goes through `status -j` and the text renderer, and the marker appears in neither.

### [CONCERN] The message-text criterion is tested on the wrapper's spawn, not on the command

Design line 287 requires a test that checks "the command's argv, environment and stdin" for message markers. Task 6.4 checks the spawn's argv, environment arguments and log paths, which belong to the wrapper, not the command. Task 5.2 (line 137) checks the environment with a wrapper-side marker, not message text. Add a case where a send carries markers in subject and body, and a real child records its argv, environment and stdin. The test then checks the child's record for the markers.

### [CONCERN] Section 6 bundles seven subtasks across three modules and 240's `send` under one commit

Section 6 changes 240's `send` and `resolve_recipient`, adds `wake_after_send`, the sweep step and the timing test. It has seven subtasks and about 30 checkboxes. Its only commit marker is at line 181, so a failure in 6.4 holds back the 240 `send` change too. Split it into three groups, each with a marker: (a) 6.1–6.2, the send plumbing (`resolve_recipient`, the `wake_command` read, `wake_problem`), a working point because the 240 to 243 `send` tests run unchanged; (b) 6.3–6.4, the wake step; (c) 6.5–6.7, sweep, cleanup and the timing test, which needs `WAKE_BOUND_SECONDS` from 6.3.

### [CONCERN] The live-step order and install source contradict the design

Design line 346 says the live migration runs "after 242's migration", installs "the slice's code from the slice branch", and removes the backups at Phase 7 "after the review passes." The task (line 252) says the whole live step is checked in Phase 7 "after the code review passes and the slice is merged", and P7.2 (line 259) installs "From the target." The two documents disagree on the install source and on when the step runs, and the task records no departure. Choose one. The post-merge order is safer, since the live store then gets only reviewed code. If that is the choice, say so in the task and amend design line 346 to match.

### [CONCERN] The live tier does not say how `amoeba` reaches the fixture agent or how the CLI is located

The fixture agent finds `amoeba` only through PATH (line 204). The wrapper's environment is the explicit `WAKE_ENV_NAMES` set, taken from the environment of the `send` that started it. Task 8.2 says only "the real installed CLI by its absolute path," and P7.2's install comes after the merge. Nothing says the test puts the CLI's directory on PATH for the `send` call, or how the CLI is found during `uv run pytest tests/live/waking`. Name the mechanism. `tests/live/program/conftest.py` exists and is the model the task names; point to how it locates the CLI.

### [CONCERN] Proportionality: three items go beyond what the success criteria need

The slice is rated Effort 3 (line 40), and the file has 34 subtasks and 10 commit markers. These cuts keep every criterion covered:
- 9.3 (CHANGELOG, line 229) is a separate group with one bullet. Fold it into 9.2's group.
- 8.1's own test file (`tests/live/waking/test_fixture_agent.py`, line 205) tests a test helper. The live cases in 8.2 exercise the same behaviour, so keep one smoke run inside 8.2.
- 10.1 (lines 236–240) rehearses the migration on a copy. The design asks for backup, migration and read-back (design line 346), and P7.1–P7.3 do that on the live store. The rehearsal adds a conditional branch (migrate missing migrations on the copy) that the design does not have. Cut it, or make it P7.1's dry run.

### [NOTE] 5.3 leaves two points open: the `wrapper_failed` exit code, and whether `wake-run` is hidden

D6 (design line 191) gives exit codes 0, 1 and 3, and does not say what the process boundary's `wrapper_failed` path exits with. Task 5.4 tests no exit code for that path. Also, 5.3 says "hidden from the one-line command summaries… if the parser supports that." Decide both, state them in 5.3, and test them in 5.4.

### [NOTE] The sweep test's "live" case cannot occur under default values

A row older than `prune_after_days` is past its deadline unless `wake_timeout_seconds` exceeds the retention window, so it is not live under `LIVE_WAKE`. Either drop "live" from the case, or state that the fixture sets a timeout longer than retention.

### [NOTE] The `list members` output for a member with no command is unspecified

Task 4.3 says `list members` text shows the command, but not what it prints when there is none. If it adds a line for every member, the existing 220 to 229 exact-output tests change, and no permitted-edit list covers that. Say it prints nothing for a null command, or name the edit.

### [NOTE] The timing tests need a short timeout under a fake clock

D6 waits with `child.wait(timeout=max(0, deadline_at - now))`, a real-time wait. A test that freezes the fake clock waits the full `wake_timeout_seconds` in real time. Say that the timeout tests use a 1 to 2 second `wake_timeout_seconds`, so they stay fast.

### [NOTE] `EXPECTED_SCHEMA_VERSION` is named but its file is not

Tasks 0.1 (line 57) and 2.1 (line 82) name the constant but not its file. It is at `src/amoeba/store/migrations.py:25` and reads 5 today. Name the file so the implementer does not have to search.

### [NOTE] The TTL and sender-notice part of the limit criterion has no test in this slice

The limit criterion ends "with a clock past the TTL the request expires and the sender hears (240)." This slice adds no test for that. It is 240's behaviour, so confirm that 240's suite covers it and name that test in task 6.4's note. If 240 does not cover it, add a case here.

### [PASS] Every functional, technical and integration criterion maps to a task, apart from the two partial gaps above

Mapping highlights: the claim order and the limit (3.2, 6.4, 7.2, 8.2); push-confirmed and unconfirmed sessions, notes and retries (6.4, 8.2); timeout and process group (5.2, 8.2); SIGKILL and the orphan (8.2, 6.6, 7.4); the explicit environment (5.2); CLI and MCP `add` (4.2 to 4.4); cleanup (6.6); the timing bound (6.7); both config keys (1.2); the verification walkthrough (10.2 and the Phase 7 checklist).

### [PASS] Sequencing, test-with pattern and commit points are sound

The order runs config, migration, store, `add`, wrapper, send hook, `list`/`status`, live tier, docs, verification, hand-off, and each dependency is built first. Each implementation group sits next to its tests (1.1/1.2, 2.1/2.2, 3.1/3.2, 4.1–4.4, 5.1–5.4, 6.1–6.7, 7.1–7.4). The ten commit markers come at group ends, not after every task, and there is no circular dependency.

### [PASS] Design rules hold: no deferral, every state has an exit, and the operator walkthrough finds no dead end

No task defers in-scope behaviour or waits on real use; fixtures and live pipelines carry the tests. Every row, log and limit has an exit: retention, the 24-hour clock, `add --no-wake-command`, or the sweep. I walked the operator path from the design text: start, normal path, second request, start failure, hang, non-zero exit, killed wrapper, limit, push-confirmed session, MCP attempt, held store, undo. Each ends in an exit that needs no file edit: a same-id retry, the clock, the TTL, `amoeba cancel`, the next agent's `done` or `decline`, `add --no-wake-command`, or a pid `list` shows and the operator kills.

### [PASS] Named helpers, paths and the `AMOEBA_HOME` layout check out against the source

Verified present: `open_state_store` (`operations/state_move.py:117`), `start_child` and `terminate_group` (`operations/processes.py:54,96`), `BUSY_TIMEOUT_SECONDS` (`store/store.py:28`), `project_of` (`upstream/context_forge/project_of.py:92`), migrations 001 to 005 under `store/schema/`, and the 0.2 helper files and directories. The 10.1 copy layout matches `config/home.py:88`, where `AMOEBA_HOME` makes config and state one directory. The 240 to 243 modules are not built yet, so 0.1 has to map them, as the task says.

### Run Digest

- Response length: 12703 chars
- Response is newline-free: no
- Tool calls made: 11
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 12
- Tokens — prompt / cached / cache write / completion / reasoning: 461753 / 287112 / 174633 / 90740 / not computed
- Duration: 389.7 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 18
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 18
- Finding-shaped matches — surviving validation: 18
