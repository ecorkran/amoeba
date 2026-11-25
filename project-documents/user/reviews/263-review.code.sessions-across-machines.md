---
docType: review
layer: project
reviewType: code
slice: sessions-across-machines
projectRules: [general.md, python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS (the after-step exit and tick body concerns resolved 20261125; the invoke concern checked and dropped)
verdictSource: derived
sourceDocument: project-documents/user/slices/263-slice.sessions-across-machines.md
aiModel: haiku-line-pass
aiRecipe: true
recipeComplete: true
status: complete
dateCreated: 20261125
dateUpdated: 20261125
reviewedSha: 6d8b6eca65d59cb88b711f4471e6faa437d6f6b9
reviewedBlob: edc728e84ba0948069dc733214f7ff3e79be29bb
reviewedBlobCurrent: true
revision_number: 2
injected:
  - key: conventions
    path: "AGENTS.md"
    chars: 24525
    sha256: 2387512002bb2a73aa247bc36bc98d7162c5b5110ded41f56319d098d282ddbc
    whole: true
filesRead:
  - "src/amoeba/mcp/in_process.py"
  - "src/amoeba/store/sql_machine_runs.py"
  - "src/amoeba/operations/steps/models_session.py"
  - "scripts/update_live.py"
  - "src/amoeba/wiring_steps.py"
  - "src/amoeba/operations/status_waiting.py"
  - "src/amoeba/hub/calls.py"
  - "src/amoeba/mcp/after_runner.py"
  - "src/amoeba/mcp/presence_task.py"
searches:
  - "list_files src/amoeba/iring_presence.py in ."
  - "grep def _read_only|def update\\(|except |def check_status|_amoeba_status|def main in /Users/manta/source/repos/manta/amoeba/scripts/update_live.py"
  - "grep \"status\" in /Users/manta/source/repos/manta/amoeba/src/amoeba/cli"
  - "grep STATUS|def _exit_code|EXIT_NEEDS|needs_you|return EXIT in /Users/manta/source/repos/manta/amoeba/src/amoeba/cli"
  - "grep STEP_ADVICE\\s*[:=]|outcome of this call is unknown in /Users/manta/source/repos/manta/amoeba/src"
  - "grep ^ in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep optional_integer|^from amoeba.store.row_values import|^from amoeba.store.row_values in /Users/manta/source/repos/manta/amoeba/src/amoeba/store"
  - "grep uv tool install --force amoeba-ai|\"amoeba-ai\"|\\[A-Za-z0-9\\._ -\\]\\{1,64\\}|\"behind\"|CHANNEL_EVENT_MAX_ENTRIES\\s*[:=]|MCP_CALL_DEADLINE_SECONDS\\s*[:=]|TICK_SECONDS_BEFORE_FIRST_REPLY\\s*[:=] in /Users/manta/source/repos/manta/amoeba"
  - "grep def write\\(|def call_scope|SAVEPOINT|BEGIN IMMEDIATE|def _open_write|nested in /Users/manta/source/repos/manta/amoeba/src/amoeba/store/store.py"
  - "grep SESSION_CALLS|SESSION_STEP_NAMES in /Users/manta/source/repos/manta/amoeba/src"
  - "grep def result_document|model_dump|extra=|class _Model in /Users/manta/source/repos/manta/amoeba/src/amoeba"
  - "grep tool_timeout_sec|185|180 s|180 seconds in /Users/manta/source/repos/manta/amoeba"
  - "grep def test_the_tick_and_the_runner_each_open|threads\\b|short_wait_before_the_first_reply|def raise_when_called_from|inspect\\.stack in /Users/manta/source/repos/manta/amoeba/tests/mcp_server"
  - "grep iring_presence in /Users/manta/source/repos/manta/amoeba"
  - "grep amoeba\\.iring_presence|from amoeba import iring_presence|import iring_presence in /Users/manta/source/repos/manta/amoeba"
turns: 27
promptTokens: 5168450
cachedTokens: 4569790
cacheWriteTokens: 598628
completionTokens: 88189
durationSeconds: 401.5
costUsd: 1.296123
runId: run-20261125-p6-fbf201a3
squadronVersion: 0.24.38
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Session exit can wait on an in-flight after-step, past its bound"
    location: "src/amoeba/mcp/after_runner.py:80"
  - id: F002
    severity: concern
    category: type-contract-debt
    summary: "Session tick body fields skip the validation their headers get"
    location: "src/amoeba/operations/steps/models_session.py:23-28"
  - id: F003
    severity: concern
    category: correctness
    summary: "`wiring.py` changes `invoke` to skip the after-step on the MCP door, but `test_after_step.py` pins the old keyword-only contract"
    location: "src/amoeba/wiring.py#invoke"
  - id: F004
    severity: note
    category: correctness
    summary: "`StepReplyError` no longer says \"applied\" for session writes"
    location: "src/amoeba/wiring_steps.py:154"
  - id: F005
    severity: note
    category: documentation-drift
    summary: "A parameter comment does not match its SQL"
    location: "src/amoeba/store/sql_machine_runs.py:7"
  - id: F006
    severity: note
    category: other
    summary: "A retired machine's stored runs stay listed until it is removed"
    location: "src/amoeba/operations/status_machines.py#read_machines"
  - id: F007
    severity: note
    category: test-debt
    summary: "Test helper depends on stack inspection and private function names"
    location: "tests/mcp_server/presence_rig.py:111"
  - id: F008
    severity: note
    category: consistency-rot
    summary: "The word \"behind\" is a literal in two places"
    location: "src/amoeba/cli/hub_commands.py:161"
  - id: F009
    severity: note
    category: architectural-decay
    summary: "`mcp/tick.py` and `mcp/presence.py` both define a failure-logging helper for ticks and after-steps"
    location: "src/amoeba/mcp/presence.py#FailureLog"
  - id: F010
    severity: note
    category: other
    summary: "`iring_presence.py` is added as an empty file"
    location: "src/amoeba/iring_presence.py"
---

# Review: code — slice 263

**Verdict:** CONCERNS
**Model:** haiku-line-pass

## Recipe

Recipe `haiku-line-pass`; complete: yes.

| Stage | Kind | Alias | Answering model | Outcome | Findings | Cost |
|---|---|---|---|---|---|---|
| review haiku-xhigh | review | haiku-xhigh | claude-haiku-5-5 | ok | 12 findings | $0.9211 |
| review haiku | review | haiku | claude-haiku-5-5 | ok | 4 findings | $0.3750 |

### Not gating

| Reviewer | Category | Severity | Location | Title |
|---|---|---|---|---|
| haiku-xhigh | test-debt | CONCERN | tests/mcp_server/test_after_runner.py:259 | Thread-isolation test asserts nothing about threads |
| haiku-xhigh | architectural-decay | CONCERN | src/amoeba/hub/call_sessions.py:36 | Constants are defined in more than one place |
| haiku-xhigh | architectural-decay | CONCERN | src/amoeba/hub/calls.py\#_serve | `hub/calls.py` is 385 lines, and `_serve` is about 80 lines |
| haiku-xhigh | architectural-decay | CONCERN | src/amoeba/operations/steps/dispatch.py\#StepEdges | `door_version` is threaded through about fifteen signatures, with defaults |
| haiku-xhigh | architectural-decay | CONCERN | src/amoeba/iring_presence.py | A stray empty module ships in the package |
| haiku | test-debt | CONCERN | src/amoeba/cli/render/sessions.py:41-52 | `_session_line` in `sessions.py` renders the machine field the same way as the other session fields, but the rendering test was updated without a corresponding check for the empty-name case |

## Findings

### [CONCERN] Session exit can wait on an in-flight after-step, past its bound

`_run` awaits `anyio.to_thread.run_sync(self._body, tick_last)` without `abandon_on_cancel`. The tick's own worker does abandon on cancel (`mcp/tick.py`, `_step`, with the comment "Abandoned at exit rather than waited for (D8)"). `_serve_presence` (`presence_task.py:50-52`) starts the runner in the same task group as `run_ticks`, so on shutdown the group cannot exit until that thread returns. `run_presence` calls `_end_session` only after `_serve_presence` returns, so the exit's `session_end` starts late. `TICK_BOUND_SECONDS` bounds only the call inside `_end_session`. The after-step's own work is not bounded by it: `_prune` can walk the calls-log directory, and `claim_work` retries. An exit the design describes as one bounded attempt can therefore take as long as a file walk or a claim retry. Either abandon the after-step thread the way the tick does, or run `_end_session` without waiting for the group.

Reviewer: haiku-xhigh

### [CONCERN] Session tick body fields skip the validation their headers get

`SessionTickRequest` validates `client` (name pattern) and `directory` (`is_session_directory`). It does not validate `session_id` (line 23) or `client_version` (line 28). The same values arrive as headers, where the hub checks them: `session_id` against `is_session_id`, and the client version against `_is_acceptable` in `hub/calls.py`. On the success path the body's `session_id` is the row key that `_refresh` writes, and the body's `client_version` is stored on the session. It is then shown in the "Behind the hub" section and in `status -j`. A successful tick can therefore store an over-long or control-character value that a refused tick would reject. The caller is an authenticated machine of the same owner, so the risk is modest. Add the same validators to the request model, or take these values only from the validated headers.

Reviewer: haiku-xhigh

### [CONCERN] `wiring.py` changes `invoke` to skip the after-step on the MCP door, but `test_after_step.py` pins the old keyword-only contract

`invoke` gains `after_step: bool = True`, and `in_process.py` now calls it with `after_step=False`. The tests check that this keyword reaches `invoke`. Nothing in the diff shows a path where a CLI caller forgets the default, so this is consistent. Still, the flag is a new switch that changes whether a state-changing after-step runs, so the single call site in `in_process.py` is the only thing keeping MCP operations from starting work twice. I could not confirm the other call sites from the diff alone.

Reviewer: haiku

### [NOTE] `StepReplyError` no longer says "applied" for session writes

The suffix "The hub applied the step." now depends on `step.keeps_result` instead of `step.writes`. `session_tick` and `session_end` write and keep no result, so a reply that does not fit their models omits the suffix, although the hub did apply the write. Key the suffix on `step.writes`, or record the reason for the change in the step model's docstring. No test covers this path for the session steps.

Reviewer: haiku-xhigh

### [NOTE] A parameter comment does not match its SQL

The comment lists six parameters ("machine id, owner id, reported_at, document, reported_at, document"). `PUT_MACHINE_RUNS` binds four `?` values, and its `ON CONFLICT` clause uses `excluded.*`. Correct the comment.

Reviewer: haiku-xhigh

### [NOTE] A retired machine's stored runs stay listed until it is removed

Each machine's `runs` document is shown with its age and replaced only when that machine next calls `status` or `list`. The only cleanup is `amoeba hub rm-machine`, which runs `remove_machine`. A machine that is put away keeps its paused runs under "Runs on other machines", with a growing "reported N days ago". This has a named exit, so it is a note. Still, an operator has no way to dismiss a stale report short of removing the machine. Consider an age cutoff in the render, or state in the design why these rows are bounded.

Reviewer: haiku-xhigh

### [NOTE] Test helper depends on stack inspection and private function names

`raise_when_called_from` calls `inspect.stack()` on every open while errors are queued, and selects the failure by function name (`"work"`, `"_end_in_thread"`, `"_body"`). `inspect.stack()` reads source for every frame, which is slow in a loop. A rename silently stops the injected failure. The test then waits for a presence stop that never comes, so it fails, but the message points nowhere. Pass the failing step or a named context flag instead of inspecting frames.

Reviewer: haiku-xhigh

### [NOTE] The word "behind" is a literal in two places

`_door_text` writes `"behind"` directly, while `cli/render/sessions.py:22` already defines `BEHIND` for the same text. The ahead/behind direction is also worked out separately in `hub_commands.py` and `render/machines.py`. Use the shared constant and one helper for the direction.

Reviewer: haiku-xhigh

### [NOTE] `mcp/tick.py` and `mcp/presence.py` both define a failure-logging helper for ticks and after-steps

`FailureLog` is now shared by the tick and the after-runner, which is good. The old `BusyWarning` class is deleted. I did not see a second copy in the hunks shown, so no finding is raised. This is informational only.

Reviewer: haiku

### [NOTE] `iring_presence.py` is added as an empty file

The diff adds `src/amoeba/iring_presence.py` with no content. It looks like a stray file, probably a typo for `wiring_presence.py`, which already exists. Nothing imports it in the hunks shown. Removing it is probably correct, but I have not verified that nothing imports it.

Reviewer: haiku

### Run Digest

- Response length: 7128 chars
- Response is newline-free: no
- Tool calls made: not offered
- Tool calls failed: not computed
- Stop reason: not computed
- Output budget: backend default
- System prompt: not computed
- Settings sources: not computed
- Reasoning characters: not computed
- Effort: backend default
- Turns: 27
- Tokens — prompt / cached / cache write / completion / reasoning: 5168450 / 4569790 / 598628 / 88189 / not computed
- Duration: 401.5 s
- Cost: $1.30
- `## Summary` located: not computed
- `## Findings` located: not computed
- Finding-shaped matches — whole response: not computed
- Finding-shaped matches — inside fences: not computed
- Finding-shaped matches — in findings section: not computed
- Finding-shaped matches — surviving validation: not computed
