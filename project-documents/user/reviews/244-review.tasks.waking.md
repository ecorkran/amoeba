---
docType: review
layer: project
reviewType: tasks
slice: waking
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/244-tasks.waking.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 8e5a2bf5e5805ac28a9ddd3dbedb567843abeaae
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 21
effort: xhigh
turns: 22
promptTokens: 1197100
cachedTokens: 991085
cacheWriteTokens: 205999
completionTokens: 85707
durationSeconds: 371.7
costUsd: 0.45737
costBasis: provider
runId: run-20261115-tasks-plan-962527a1
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: fail
    category: contradiction
    summary: "Live fixture's control by environment variables cannot reach the command"
    location: "project-documents/user/tasks/244-tasks.waking.md:253"
  - id: F002
    severity: concern
    category: spec-gap
    summary: "`claim_wake` cannot set `log_stem`, and `can_wake` has an elided signature"
    location: "project-documents/user/tasks/244-tasks.waking.md:98"
  - id: F003
    severity: concern
    category: spec-gap
    summary: "The \"child factory from deps\" does not exist"
    location: "project-documents/user/tasks/244-tasks.waking.md:145"
  - id: F004
    severity: concern
    category: contradiction
    summary: "6.8 edits 240's timing test, which the preamble and 10.1 forbid"
    location: "project-documents/user/tasks/244-tasks.waking.md:201"
  - id: F005
    severity: concern
    category: ci-gating
    summary: "The load test's CI gate is implicit"
    location: "project-documents/user/tasks/244-tasks.waking.md:198"
  - id: F006
    severity: concern
    category: docs-consistency
    summary: "The plan's prose still states 244's old dependency"
    location: "project-documents/user/architecture/240-slices.agent-messaging.md:114"
  - id: F007
    severity: note
    category: operator-walkthrough
    summary: "The operator walkthrough's \"one dead end\" undercounts"
    location: "project-documents/user/slices/244-slice.waking.md:364"
  - id: F008
    severity: note
    category: proportionality
    summary: "Size fits the slice, with two trims available"
    location: "project-documents/user/tasks/244-tasks.waking.md:89"
  - id: F009
    severity: pass
    category: coverage
    summary: "Every success criterion maps to a task"
    location: "project-documents/user/slices/244-slice.waking.md:275"
  - id: F010
    severity: pass
    category: sequencing
    summary: "Sequencing, test pairing and commit markers"
    location: "project-documents/user/tasks/244-tasks.waking.md"
  - id: F011
    severity: pass
    category: verification
    summary: "Repo facts the tasks depend on are present"
    location: "project-documents/user/tasks/244-tasks.waking.md:57"
  - id: F012
    severity: pass
    category: rules
    summary: "No deferral, usage waits or unexited states in the tasks"
    location: "project-documents/user/tasks/244-tasks.waking.md"
---

# Review: tasks — slice 244

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Live fixture's control by environment variables cannot reach the command

Task 9.1 has the fixture wait on a gate file, sleep past the timeout and write its parent pid, all "by environment variables". Task 5.4 and design D6 (`project-documents/user/slices/244-slice.waking.md:185`) give the command only the `WAKE_ENV_NAMES` variables, copied from the wrapper's own environment, and nothing else. The test's variables never reach the fixture, so the gate, timeout and SIGKILL cases in 9.2 (lines 260 and 262) would run with defaults and fail. Pass these controls as flags on the wake command, which 9.2 already builds from its flags. Change 9.1 and design D12 (line 231) to match, and say in 9.2 that only `WAKE_ENV_NAMES` reach the command.

### [CONCERN] `claim_wake` cannot set `log_stem`, and `can_wake` has an elided signature

3.1 fixes `claim_wake(transaction, member_id, now, wake_timeout_seconds, max_wakes_per_day, session_stale_seconds, directory)` and says `log_stem` is set when a directory is given. The claim generates `wake_id` itself, and 6.3 (line 182) defines the stem as `<logs_dir>/wake/<wake_id>`. Nothing passes `logs_dir` or the id in, and the store must not read layout or config. Name the parameter, or have the caller pass the id and stem. Write `can_wake`'s signature in full (line 99 has `...`).

### [CONCERN] The "child factory from deps" does not exist

5.3 has `run_wake` take "the clock and the child factory from `deps`". `Deps` has `clock` and `spawn`. `spawn` is `start_child`, typed `Spawner` (`src/amoeba/operations/processes.py:51`), which requires `LaunchLogs` and creates log files. D6 needs inherited stdout and stderr, stdin `DEVNULL` and the explicit environment, and nothing in `Deps` provides that. Name the new seam (a Popen-shaped callable on the wrapper's deps, or a `run_wake` parameter) and where it lives. The "patched child factory" in 5.6 depends on that name.

### [CONCERN] 6.8 edits 240's timing test, which the preamble and 10.1 forbid

Line 49 limits changes to existing 240 to 243 tests to the assertions 2.1, 4.4 and 6.1 name. 6.8 edits the existing sum and failing-bound test in `tests/test_message_timing.py`. 10.1 (line 272) says every other test change is an added function. Those cannot all hold. The design has the same gap: D11 (line 225) and TR3 (line 295) require the timing change, but the named edits in Integration Requirements (line 299) omit it. Either add 6.8 to the named edits (line 49, 10.1 and design line 299), or add a new function that asserts the sum and leave 240's function unchanged.

### [CONCERN] The load test's CI gate is implicit

6.7 says "CI already gates the file". That holds: `.github/workflows/ci.yml:40` runs a bare `uv run pytest`, and `pyproject.toml:64` sets `addopts = ["--ignore=tests/live"]`. But no task wires it, and the rule for load tests requires a CI wiring task rather than an implicit gate. A later change to either line would drop the gate silently. Add a CI-wiring item to 6.7 that names the step that runs `tests/load/test_wake_claim_load.py`.

### [CONCERN] The plan's prose still states 244's old dependency

Entry 5's Dependencies line already reads 240 to 243 (line 105), so 8.2 correctly leaves it. The closing prose on line 114 still says "244 needs 241's live-session check." The design's Departures (line 234) say the docs step leaves no difference between design and plan. Add line 114 to 8.2's amendments.

### [NOTE] The operator walkthrough's "one dead end" undercounts

I walked the design's operator steps: start, normal path, a second request, a failed start, a timeout, a non-zero exit, a killed wrapper, the limit, a live session, an MCP attempt, a held store and undo. Each exits without editing files. But one sub-case is missing: if the held-store write leaves `command_pid` null (D6 step 1), an orphan from a killed wrapper has no pid for `list` to show. Its exit is the same (the command's own cap), so this adds no new dead end, but the count and the walkthrough should say so.

### [NOTE] Size fits the slice, with two trims available

At 294 lines and about 41 top-level items plus the Phase 7 list, the file is proportionate to a 365-line design with 12 decisions, so I am not flagging it as overweight. Two cuts: the version-10 refusal in 2.2 re-proves the existing newer-schema guard, which no success criterion names. And 6.3 (line 180) is one function with five branches (pre-check, claim, spawn, the two start-failure types, `StoreError`). The ~50-line function guideline suggests naming helpers in the task, such as `record_start_failure`.

### [PASS] Every success criterion maps to a task

FR1 maps to 9.2 case 1. FR2 maps to 6.4, 6.5 and 9.2. FR3 maps to 5.4. FR4 maps to 9.2 (SIGKILL), 6.10 and 7.2. FR5 maps to 5.4, 5.8, 7.2 and 7.4. FR6 maps to 6.5. FR7 maps to 6.4 and 6.5. FR8 maps to 6.6. FR9 maps to 6.6 and 7.2. FR10 maps to 6.4 and 9.2. FR11 maps to 5.2 and 5.4. FR12 maps to 8.1. FR13 maps to 4.2 and 4.4. TR1 maps to 6.10. TR2 maps to 1.2, 2.2 and 10.1. TR3 maps to 6.8. TR4 maps to 10.1. The integration criteria map to 10.1 and the Phase 7 checklist. Nothing lacks a task. The load test in 6.7 is supported by D2's concurrency claim and D11's bound, so it is not scope creep.

### [PASS] Sequencing, test pairing and commit markers

Dependencies run one way: config, migration and store, CLI `add`, wrapper, `send`, status, docs, then the fixture and live tier, then verification. There are no cycles. Each implementation item is followed by its tests. There are 14 plain `**Commit**:` lines, all at group ends and none after every task, and each group lands on a tested state.

### [PASS] Repo facts the tasks depend on are present

Found: schema files 001 to 005; the `schema_meta`, `amoeba.sqlite3` and `config.yaml` names P7 uses; `BLE` in ruff's select; `MCP_CALL_DEADLINE_SECONDS` = 180.0 and `BUSY_TIMEOUT_SECONDS` = 5.0, so the 160 s sum and 25 s bound hold; `NonBlankText` and `concept`'s `model_fields_set`; the `answering_wait_seconds` and `prune_after_days` patterns; `LaunchLogs`, `LaunchError`, `start_child`, `terminate_group` and `open_state_store`; `AMOEBA_HOME`; the `Path(sys.executable).with_name("amoeba")` pattern; `tests/cli/test_parser_names.py`; `tests/load/test_report_release_load.py`; the `## Example` block in `docs/config-contract.md`; and `project_of.py` under `src/amoeba/upstream/`. Absent as expected, since 240 to 243 build them: `tests/test_message_timing.py`, `store/schema/006` and later, `live_member_ids`, `sessions`, and `tests/live/messaging`. The BLE001 behaviour stated in 5.5 is unverified by execution, but 5.5 already falls back to running ruff.

### [PASS] No deferral, usage waits or unexited states in the tasks

Checked against the Amoeba Design Rules. No task defers in-scope behaviour. None waits on usage: 9.2 uses a fixture, and walkthrough step 6's "after the window clears" has a config alternative. Every limit states its outcome: wake timeout, daily limit, `PROCESS_STOP_WAIT_SECONDS`, busy timeout and retention. Wake logs and backups sit under the state directory, and the wake keys sit in `config.yaml`. `wake_command` is stored in the state database like the other member settings, which is consistent with those settings.

### Run Digest

- Response length: 10704 chars
- Response is newline-free: no
- Tool calls made: 21
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 22
- Tokens — prompt / cached / cache write / completion / reasoning: 1197100 / 991085 / 205999 / 85707 / not computed
- Duration: 371.7 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
