---
docType: review
layer: project
reviewType: code
slice: waking
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/244-slice.waking.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261117
dateUpdated: 20261117
reviewedSha: d15679113e06c37fe7b5cba269076ca89aad84e3
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 28
diffTruncated: false
effort: xhigh
turns: 29
promptTokens: 3066880
cachedTokens: 2651150
cacheWriteTokens: 415706
completionTokens: 81862
durationSeconds: 368.3
costUsd: 0.809355
costBasis: provider
runId: run-20261117-p6-fdffa7db
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "A stopped wake can leave group members running after `timed_out` is recorded"
    location: "src/amoeba/operations/processes.py:96-115"
  - id: F002
    severity: concern
    category: error-handling-observability
    summary: "`run_wake` logs and re-raises against the project's logging rule"
    location: "src/amoeba/operations/wake_run.py:153-169"
  - id: F003
    severity: concern
    category: type-contract-debt
    summary: "`MemberSettings.wake_command` defaults silently to \"no wake\""
    location: "src/amoeba/store/models.py:59"
  - id: F004
    severity: concern
    category: consistency-rot
    summary: "The live test copies the wake environment allowlist instead of using the constant"
    location: "tests/live/waking/test_waking_live.py#test_the_command_receives_no_message_text"
  - id: F005
    severity: note
    category: security-hygiene
    summary: "The MCP refusal is enforced only in the wiring layer"
    location: "src/amoeba/operations/add.py:69"
  - id: F006
    severity: note
    category: correctness
    summary: "`wake-run` does not claim the row, so a second run starts a second command"
    location: "src/amoeba/operations/wake_run.py#run_wake"
  - id: F007
    severity: note
    category: correctness
    summary: "A start whose failure could not be recorded still reads as running"
    location: "src/amoeba/operations/wake.py#_record_start_failure"
---

# Review: code — slice 244

**Verdict:** FAIL
**Model:** claude-haiku-5-5
**Evidence:** 28 successful tool call(s) of 28 made; 234697 of 234697 diff characters reached the model

## Findings

### [FAIL] A stopped wake can leave group members running after `timed_out` is recorded

`terminate_group` sends SIGTERM to the process group, then waits only on the leader with `child.wait(timeout=TERMINATE_GRACE_SECONDS)`. If the leader exits on SIGTERM, the function returns at line 114. It never checks whether other group members survived, and it sends SIGKILL only when the leader is still alive after the grace period. A member that ignores or traps SIGTERM is therefore left running.

`run_wake` calls this helper on the timeout path (`wake_run.py:76`), on the error path (`:87`) and on the wrapper-failure path (`:92`), then records the wake as ended. The contract says `timed_out` means "the command and its whole process group were stopped" (`docs/cli-contract.md:293-294`), and the slice design says the same (`244-slice.waking.md:279`). Because the row is ended, the member's wake limit and live-wake check no longer cover the survivor. A second unattended agent can start beside it.

The test `test_a_command_past_the_deadline_is_stopped_with_its_whole_group` passes only because its grandchild dies on SIGTERM. `processes.py` predates this slice, but the slice's contract depends on it. Fix: after the leader exits, poll `os.killpg(pid, 0)` for the grace period and SIGKILL the group if anything remains. Add a test whose grandchild traps SIGTERM.

### [CONCERN] `run_wake` logs and re-raises against the project's logging rule

`_finish` logs a store failure with `logger.error` (line 168), which drops the traceback, then re-raises (line 169). The project rule requires `logger.exception` before a re-raise. The branch at lines 83-88, `except (WakeRunError, StoreError)`, re-raises with no log at all. The rule covers every try/except, so this branch also deviates.

### [CONCERN] `MemberSettings.wake_command` defaults silently to "no wake"

`wake_command: str | None = None` lets a caller omit the field without a warning. `upsert_member` then writes `None` over the stored command (`programs.py`, the UPDATE and REREGISTER branches). Today both production constructors pass it explicitly (`set_up.py:208` and `programs.py:47`), so nothing is broken yet. Making the field required avoids the trap; the tests that build `MemberSettings` would need the keyword.

### [CONCERN] The live test copies the wake environment allowlist instead of using the constant

The assertion that the command's environment is limited builds its own set literal (around lines 244-255, including `__CF_USER_TEXT_ENCODING`). It does not use `WAKE_ENV_NAMES`, which `tests/operations/test_wake_run.py` does use. If the constant changes, this check drifts silently. Replace the literal with the constant plus the OS-added name, the way `test_wake_run.py` does.

### [NOTE] The MCP refusal is enforced only in the wiring layer

`AddRequest.wake_command` and `MemberRequest.wake_command` accept the field. `SkipJsonSchema` hides it only from the published schema. The refusal lives in `place_add` (`wiring_registry.py`), and `add()` itself does not check the door. Today `place_add` is the only caller, so there is no live bypass. A future caller that skipped the wiring would accept an unattended-start field from MCP. Passing the door into `add()` would make the rule non-bypassable.

### [NOTE] `wake-run` does not claim the row, so a second run starts a second command

`_unended_row` checks only that `ended_at` is null. Nothing marks the row as started before the command is spawned, so a manual re-run of `amoeba wake-run <id>` starts a second command. The live-wake check happens only at claim time, which a re-run bypasses. The wake id is visible in the `status` log paths. A compare-and-set on a start marker would make the command idempotent.

### [NOTE] A start whose failure could not be recorded still reads as running

If `_record_start_failure` raises `StoreBusyError`, `wake_after_send` returns one problem line, but the row stays unended with no pid and no process. `status` then shows "running since …, stops …" and blocks waking until the deadline. The sender sees the failure only once, in the send result. The display should not claim a run that never started.

### Run Digest

- Response length: 8105 chars
- Response is newline-free: no
- Tool calls made: 28
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 29
- Tokens — prompt / cached / cache write / completion / reasoning: 3066880 / 2651150 / 415706 / 81862 / not computed
- Duration: 368.3 s
- Cost: $0.81 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
