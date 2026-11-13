---
docType: review
layer: project
reviewType: slice
slice: mcp-server
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/226-slice.mcp-server.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261112
dateUpdated: 20261112
reviewedSha: 23803e729af58dbe031bd34a9ef8e524adf714ce
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
effort: high
turns: 10
promptTokens: 510078
cachedTokens: 395667
cacheWriteTokens: 114399
completionTokens: 9431
durationSeconds: 81.7
costUsd: 0.592406
costBasis: provider
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: integration
    summary: "Home preparation contract differs from 228's stated MCP interface"
    location: "project-documents/user/slices/226-slice.mcp-server.md:46-48"
  - id: F002
    severity: concern
    category: nfr
    summary: "D12's deadline value is left to a task and not tied to the waits inside `answer`"
    location: "project-documents/user/slices/226-slice.mcp-server.md:128-129"
  - id: F003
    severity: concern
    category: error-handling
    summary: "The `TimedOut` message sends the agent to the tool that timed out"
    location: "project-documents/user/slices/226-slice.mcp-server.md:128-129,157"
  - id: F004
    severity: concern
    category: operator-walkthrough
    summary: "Verification steps 6 and 7 contradict each other and change the PM's real client config"
    location: "project-documents/user/slices/226-slice.mcp-server.md:150-151"
  - id: F005
    severity: note
    category: scope
    summary: "`answer` is in-process, which departs from the plan wording"
    location: "project-documents/user/slices/226-slice.mcp-server.md:69"
  - id: F006
    severity: note
    category: under-specification
    summary: "How raw arguments reach the operations needs a pinned mechanism"
    location: "project-documents/user/slices/226-slice.mcp-server.md:53"
  - id: F007
    severity: note
    category: parent-document
    summary: "The architecture's Squadron table is stale"
    location: "project-documents/user/slices/226-slice.mcp-server.md:30"
  - id: F008
    severity: pass
    category: architecture
    summary: "Layering, dependency direction and state placement"
    location: "project-documents/user/slices/226-slice.mcp-server.md:34-48"
  - id: F009
    severity: pass
    category: error-handling
    summary: "Failure modes and exits for the detached `handle_pause`"
    location: "project-documents/user/slices/226-slice.mcp-server.md:88-94,96-104"
---

# Review: slice — slice 226

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Home preparation contract differs from 228's stated MCP interface

228 lists what it provides to 226 as "`prepare_state_home` and `StateLayout`, called once when the MCP process starts" (228 line 345). It also says `open_state_store` "moves legacy state" before `Store.open` (228 line 117). 226 never mentions `prepare_state_home` or a start-up step. Its server "holds no state" and each call runs `open_state_store` in its own worker thread.
- **The gap:** after an upgrade, the first calls reach the legacy move (228 D2: copy, verify, delete old store, move directories) from concurrent threads. Two parallel first calls from one client, or a CLI run alongside, can race each other.
- **Failure handling:** a `StoreRelocateError` is exit 3 on the CLI. 226 doesn't say whether it surfaces at server start or on each call.
- **Fix:** say whether `main()` calls `prepare_state_home` once before serving, and add a test of two concurrent first calls against a throwaway legacy home.

### [CONCERN] D12's deadline value is left to a task and not tied to the waits inside `answer`

`MCP_CALL_DEADLINE_SECONDS` is defined as "set below the default tool timeout of the clients the install doc names (task 0.3 reads each client's current default)." The design states no number or rule.
- **No relation to config:** `answer` runs in-process and waits up to `resume_wait_seconds`, a required config key (223 D8). Nothing relates that key to the deadline.
- **Dead end:** if `resume_wait_seconds` plus the `sq` and `cf` timeouts can exceed the deadline, every `answer` returns `TimedOut` after the answer is recorded and the resume started.
- **Duplicate risk:** the agent may then retry `answer`.
- **Fix:** add a start-up or test check that the worst-case `answer` time is below the deadline, or state the invariant.
- **Dropped failures:** `abandon_on_cancel` also drops any exception raised in the abandoned thread after the timeout. Say whether it is logged.

### [CONCERN] The `TimedOut` message sends the agent to the tool that timed out

The message reads "it may still complete, so check status or decisions", and the operator walkthrough says "`status` and `decisions` say which." That is circular when `status` is the call that timed out.
- **No exit:** the abandoned thread's result is discarded and nothing is cached. If `sq runs list` plus the unknown-directory lookups always take longer than the deadline, every MCP `status` times out.
- **No way out:** the design offers no exit. The only workaround is running `amoeba status` in a shell, which an agent session may not do and the PM can't ask for through MCP.
- **Fix:** for `status` and `decisions`, say that the CLI is the fallback. Alternatively, name the time bound 228 D4 gives `status` and require it to sit below the deadline, with a test.

### [CONCERN] Verification steps 6 and 7 contradict each other and change the PM's real client config

Step 6 registers `amoeba` at user scope and says "it stays on." Step 7 runs `claude mcp remove amoeba --scope user`. Step 2 reinstalls the real tool with `uv tool install --force .`.
- **The contradiction:** the registration either stays or is removed, and the doc says both.
- **The side effect:** both steps change the PM's real environment, outside the throwaway `AMOEBA_HOME`.
- **Fix:** pick one. Either use a project-scope or temporary registration that step 7 removes, or drop step 7 and say the install is the end state. Check that the stdio smoke test and live test already prove the server works without touching user-scope config.

### [NOTE] `answer` is in-process, which departs from the plan wording

The plan entry and the architecture's "One operation, two doors" principle describe `answer` with a resume as long work started detached. The design runs it in-process and says why: the resume waits only `resume_wait_seconds`, and the agent gets the typed outcome back. That is sound and arguably better. It does make the deadline relationship above matter more, and the plan's "A long call returns at once" criterion now applies to `handle_pause` only. The design's own success criterion already says "`handle_pause` excepted".

### [NOTE] How raw arguments reach the operations needs a pinned mechanism

D1 relies on the low-level server passing arguments to the operation without validating them against the published schema, so a malformed `set_up` gives `rejected` on both doors. It doesn't say how the SDK's own input validation is turned off. The D10 "same functions" test (malformed `set_up` returns `rejected`) will catch a mismatch, so no change is needed. The mechanism would still be worth one line in the design.

### [NOTE] The architecture's Squadron table is stale

226 records `ecorkran/squadron#303` as closed, checked on 20261112. The architecture's table (`220-arch.program-tool.md`, "Squadron changes") still lists it as open. I did not re-run `gh issue view` myself. The parent should be corrected so the two documents don't disagree.

### [PASS] Layering, dependency direction and state placement

- **Layering:** `cli` and `mcp` both depend on `operations` and `wiring`, `mcp` imports nothing from `store`, `config`, `upstream`, `answering` or `cli`, and an AST test enforces it.
- **Shared invocation:** the single `wiring.invoke` delivers "no logic of its own" and gives 227 a four-item recipe for adding an operation.
- **Config and state:** detached logs go under the state home's `logs/mcp/`, not `~/.config`.
- **Plan coverage:** the design covers what the plan assigns: `via`, migration 004, `wiring.invoke`, deadlines, and a live fixture walkthrough in place of a PM step.

### [PASS] Failure modes and exits for the detached `handle_pause`

- **Start failures:** invalid input, a missing `amoeba` script, a `LaunchError` and a log-creation `OSError` each have an explicit `isError` path.
- **Client disconnect:** the child runs in its own session and survives it.
- **End state:** the child is bounded by `answering_wait_seconds`, and its logs are pruned by 228's `prune`.
- **Test:** a test pins that the logs are pruned.
- **Unexpected errors:** the top-level handler in `call_tool` logs with `logger.exception`, so that rule is met.

### Run Digest

- Response length: 7193 chars
- Response is newline-free: no
- Tool calls made: 9
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 10
- Tokens — prompt / cached / cache write / completion / reasoning: 510078 / 395667 / 114399 / 9431 / not computed
- Duration: 81.7 s
- Cost: $0.59 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

## Resolution

- **[concern] Home preparation contract:** fixed. `main()` calls `wiring.prepare_home()` (228's `prepare_state_home(state_layout())`) once before serving; a failure exits non-zero with the CLI's text. Per-call `open_state_store` stays, as a no-op once moved, with 228's lock covering a CLI run beside the server. Tests: start-up order and failure, and two concurrent first calls against a throwaway legacy home (D10, tasks 5.2).
- **[concern] D12 deadline value not tied to `answer`'s waits:** fixed. `wiring.answer_bound_seconds(config)` is `resume_bound_seconds(config)` plus the other `sq` and `cf` timeouts on `answer`'s path. `main()` refuses a config where it is not below `MCP_CALL_DEADLINE_SECONDS`, naming `resume_wait_seconds`, so `answer` never times out after acting and no retry duplicates it. An exception raised by an abandoned worker is logged with `logger.exception` by a wrapper.
- **[concern] `TimedOut` sends the agent to the tool that timed out:** fixed. `ToolSpec.timeout_advice`: `status` and `decisions` name the CLI as the fallback (no deadline there); the write tools say to check `status` or `decisions` before repeating. 228 defines no time bound for `status` (it says "unchanged"), so a bound could not be required; the CLI fallback is the exit.
- **[concern] Verification steps 6 and 7 contradict:** fixed. Step 6 is the install and the end state. Step 7 only clears the throwaway world; undoing the registration is documented, not exercised. Steps 1 to 5 prove the server without touching client config.
- **[note] `answer` in-process:** no change. The design already states it and excepts `handle_pause` in its success criterion.
- **[note] Raw arguments mechanism:** fixed. D1 says the handler is registered with the SDK's input validation off; task 0.3 confirms the 2.x spelling, and the D10 "same functions" test catches a mismatch.
- **[note] Architecture's Squadron table stale:** fixed. Checked with `gh issue view` on 20261112: #302 and #303 are both closed; the rows in `220-arch.program-tool.md` now say closed.
- **[pass] Layering and failure modes:** no action.
