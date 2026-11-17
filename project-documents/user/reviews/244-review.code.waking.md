---
docType: review
layer: project
reviewType: code
slice: waking
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/244-slice.waking.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261117
dateUpdated: 20261117
reviewedSha: e65c6113367e5f8e23ddbe01943d5d88136a37b0
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
diffTruncated: false
effort: xhigh
turns: 25
promptTokens: 2250272
cachedTokens: 1825758
cacheWriteTokens: 424496
completionTokens: 73345
durationSeconds: 328.5
costUsd: 0.759467
costBasis: provider
runId: run-20261117-p6-fdffa7db
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Wrapper signals a process group after its leader has been reaped"
    location: "src/amoeba/operations/wake_run.py:78-79"
  - id: F002
    severity: concern
    category: correctness
    summary: "Woken commands do not get `CONTEXT_FORGE_DATA_DIR`, which the test rigs treat as required"
    location: "src/amoeba/operations/wake_environment.py:19-29"
  - id: F003
    severity: note
    category: performance-resource
    summary: "Shared `terminate_group` now waits for the whole group"
    location: "src/amoeba/operations/processes.py:99-116"
  - id: F004
    severity: note
    category: test-debt
    summary: "The zero-cf-call assertion would pass vacuously if `calls` disappeared"
    location: "tests/operations/test_wake_after_send.py:485-495"
  - id: F005
    severity: note
    category: architectural-decay
    summary: "The daily-limit predicate is written in two places"
    location: "src/amoeba/operations/wake_status.py:54-55"
  - id: F006
    severity: pass
    category: security-hygiene
    summary: "The MCP door is default-deny for `wake_command`"
    location: "src/amoeba/operations/add_door.py:23, add_door.py:56-60"
  - id: F007
    severity: pass
    category: security-hygiene
    summary: "Wake SQL composes only from constants"
    location: "src/amoeba/store/sql_wakes.py:1-57"
---

# Review: code — slice 244

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 24 successful tool call(s) of 24 made; 252956 of 252956 diff characters reached the model

## Findings

### [CONCERN] Wrapper signals a process group after its leader has been reaped

On the normal-exit path, `_wait` (line 78) calls `child.wait()`, which reaps the command's leader. Line 79 then calls `terminate_group(child)`, and `terminate_group` runs `os.killpg(child.pid, ...)` (`processes.py:109`) on the pid it has just reaped. The error handlers at lines 89-90 and 94-95 can reach the same state when `_finish` raises after `_wait` has reaped the child. The timeout path is safe, because `Popen.wait(timeout=...)` does not reap on timeout.

Once reaped, the pid and the group it leads can be reused, so a SIGTERM or SIGKILL could reach an unrelated group. The window is small. But before this slice, `terminate_group` was only called on children that were still running (`answering_run.py:174`, `resume.py:195`), and this slice adds a call on every normal exit. A fix should stop the group before the leader is reaped, for example by waiting for exit without reaping. Check that the primitive exists on darwin, the target platform here, before relying on it.

### [CONCERN] Woken commands do not get `CONTEXT_FORGE_DATA_DIR`, which the test rigs treat as required

`WAKE_ENV_NAMES` omits `CONTEXT_FORGE_DATA_DIR`. Amoeba never reads it (`CHANGELOG.md:118`), but every other live tier sets it for the Amoeba and Context Forge calls it makes: `tests/live/channels/world.py:52`, `tests/live/pause/harness.py:93`, `tests/live/answering/conftest.py:38` and `tests/live/messaging/repos.py:7`.

The waking live test works around the omission. The fixture agent takes `--cf-data-dir` and sets the variable itself (`tests/live/waking/fixture_agent.py:35`, `tests/live/waking/world.py:98`). Its docstring says "a real agent's repo needs no such flag", which the tests do not verify. For a user whose Context Forge data directory is set through this variable, the woken agent's `amoeba inbox` and `amoeba reply` would run against the default data directory. I have not confirmed how Context Forge behaves without the variable, but the test rigs' own use of it suggests it matters. Either add the variable to the allowlist, which holds no secret, and update the list in the wake-command section of `docs/cli-contract.md`, or say explicitly that a woken command uses the default data directory. The live test should then stop injecting it.

### [NOTE] Shared `terminate_group` now waits for the whole group

The stop now waits for every member of the process group, not only the leader. For the existing resume and answering callers (`resume.py:195`, `answering_run.py:174`), a surviving member can extend the stop from one grace period to two plus polling, up to about 10 seconds. Neither caller holds a store transaction at those lines, so this is added latency, not lock contention. The change is intended, but the shared helper's contract has changed for callers outside this slice.

### [NOTE] The zero-cf-call assertion would pass vacuously if `calls` disappeared

`getattr(rig.deps.cf_run, "calls", [])` returns an empty list when the attribute is missing, so both counts become 0 and the assertion passes. The fake from `message_cf` does record `calls` (`tests/operations/set_up_support.py:53`), so the assertion does bite today. The default removes the guarantee. Use the attribute directly on a typed fake, and add a positive control: a send that does call cf must count more than zero.

### [NOTE] The daily-limit predicate is written in two places

`build_wake_status` shows "waking stopped" when `used_in_window >= max_wakes_per_day`. The claim in `src/amoeba/store/wakes.py:131` enforces the same comparison. The two can drift if one changes, for example the window or what counts. Have `WakeSummary` carry a `limit_reached` flag computed in the store, and let the display read it.

### [PASS] The MCP door is default-deny for `wake_command`

Only `Door.CLI` may set the field. Every other door gets a refusal, both for a top-level `wake_command` and for `bulk.members.N.wake_command`. The published schema hides the field too. `tests/mcp_server/test_in_process.py` covers both forms through the in-process MCP path.

### [PASS] Wake SQL composes only from constants

Every f-string joins module-level constants (`_WAKE_COLUMNS`, `LIVE_WAKE`), and runtime values bind through `?`. This meets the repo's "SQL composes from constants only" rule.

### Run Digest

- Response length: 8233 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 2250272 / 1825758 / 424496 / 73345 / not computed
- Duration: 328.5 s
- Cost: $0.76 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
