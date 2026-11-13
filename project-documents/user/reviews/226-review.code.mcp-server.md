---
docType: review
layer: project
reviewType: code
slice: mcp-server
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/226-slice.mcp-server.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261113
dateUpdated: 20261113
reviewedSha: f74653404a948b9e945bc0f85c4a1b961d1b5748
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 18
diffTruncated: false
effort: xhigh
turns: 19
promptTokens: 1318355
cachedTokens: 1022644
cacheWriteTokens: 295697
completionTokens: 56795
durationSeconds: 239.1
costUsd: 0.357075
costBasis: provider
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Deadline guard runs only at startup; each answer re-reads config"
    location: "src/amoeba/mcp/server.py:186"
  - id: F002
    severity: concern
    category: performance-resource
    summary: "Unbounded serialization and schema generation run on the event loop"
    location: "src/amoeba/mcp/in_process.py:70"
  - id: F003
    severity: concern
    category: test-debt
    summary: "End-to-end start-up test passes on any failure"
    location: "tests/mcp_server/test_stdio_smoke.py:81-96"
  - id: F004
    severity: concern
    category: type-contract-debt
    summary: "PM answers can be recorded with no door, by default"
    location: "src/amoeba/store/answers.py:133"
  - id: F005
    severity: concern
    category: architectural-decay
    summary: "Absolute-directory rule is implemented twice, and the detached path validates twice"
    location: "src/amoeba/mcp/tools.py:188"
  - id: F006
    severity: note
    category: consistency-rot
    summary: "Routing check keys on `timeout_advice`, not on `mode`"
    location: "src/amoeba/mcp/in_process.py:62"
  - id: F007
    severity: note
    category: architectural-decay
    summary: "Re-exports with no consumer in the MCP package"
    location: "src/amoeba/wiring.py:80"
  - id: F008
    severity: note
    category: performance-resource
    summary: "Detached child's `Popen` handle is dropped without a wait"
    location: "src/amoeba/mcp/detached.py#_start"
  - id: F009
    severity: note
    category: documentation-drift
    summary: "Package docstring says MCP types come through `wiring`, but they do not"
    location: "src/amoeba/mcp/__init__.py:3-4"
  - id: F010
    severity: pass
    category: correctness
    summary: "Answer column list and insert arity agree"
    location: "src/amoeba/store/sql.py:268"
  - id: F011
    severity: pass
    category: documentation-drift
    summary: "Deadline constants and documented numbers agree"
    location: "src/amoeba/mcp/in_process.py:25"
---

# Review: code — slice 226

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 18 successful tool call(s) of 18 made; 151418 of 151418 diff characters reached the model

## Findings

### [CONCERN] Deadline guard runs only at startup; each answer re-reads config

`main()` runs `check_deadline(load_config(), MCP_CALL_DEADLINE_SECONDS)` once at start-up. Every in-process call then reads config again: `wiring.invoke` calls `load_config()` for `answer` at `src/amoeba/wiring.py:190`. `resume_wait_seconds` is validated only as `gt=0` (`src/amoeba/config/user_config.py:73`), so a person can raise it while the server is running. The server then keeps serving, and an `answer` can run past 180 s. The MCP call reports `TimedOut` after the answer was recorded and the resume started. That is the outcome the D12 check at `src/amoeba/wiring.py:260-278` exists to prevent. Load the config once at start-up and pass it through, or re-run the check against the config each `answer` actually uses.

### [CONCERN] Unbounded serialization and schema generation run on the event loop

`run_in_process` is async. After the worker returns, line 70 runs `wiring.result_document(result)` on the loop. For `decisions` and `status`, the result grows with the number of answers and runs, so the cost has no bound, and the project's <1 ms rule for code inside await-able functions is not met. Other loop-side work in the same path:
- `_on_list_tools` (`src/amoeba/mcp/server.py:121-133`) calls `input_schema(spec)`, which runs `model_json_schema()` for all eight tools on every `tools/list`.
- `_ok` in `server.py` runs `json.dumps` on the full document on the loop.
- `start_handle_pause` (`src/amoeba/mcp/detached.py:127`) does a `Path.exists()` stat.

Return the serialized document from the worker thread, and compute the schemas once in `build_server`.

### [CONCERN] End-to-end start-up test passes on any failure

`test_the_server_refuses_to_start_without_a_config` catches `BaseException` (line 93, with `noqa: BLE001`). It asserts only that the error is not a `TimeoutError` (line 95). A server that crashes on an `ImportError`, a bad argv or any other fault passes. The test never checks the reason the server reports, which is the `error: ConfigError: ...` line `main()` writes. The in-process test in `test_server_main.py` covers the config path, but this test is the end-to-end check for the stdio refusal. Capture the child's stderr and assert on the reported error, and catch the specific exception types the SDK raises rather than `BaseException`.

### [CONCERN] PM answers can be recorded with no door, by default

`add_pm_answer(..., via: Door | None = None)` defaults to no door. The only production PM-answer path, `answer()` (`src/amoeba/operations/answer.py:100`), passes `via`, so today's behavior is correct. But a future PM-answer writer that omits `via` would silently record NULL, and `decisions` would then show `via: null` for a PM answer. That is the provenance D11 exists to keep. `test_decisions.py:232` relies on the default to build a pre-migration row. Make `via` required, and have that test pass `None` explicitly. The automatic-answer path already does this at `answers.py:290`.

### [CONCERN] Absolute-directory rule is implemented twice, and the detached path validates twice

The absolute-directory rule exists in `_directory_from` (`tools.py:188-202`, raises `RequestError`) and in `_absolute` (`src/amoeba/operations/handle_pause_call.py:17-19`, raises a pydantic `ValueError`). For `handle_pause`, `_run` calls `prepare_arguments` (`server.py:89`). The detached branch then discards that result and calls `start_handle_pause` (`server.py:92`), which validates again through `HandlePauseCall`. Two validators with different error types and messages can drift apart. Branch on `spec.mode` before `prepare_arguments`, and make `HandlePauseCall` the single validator for the detached tool.

### [NOTE] Routing check keys on `timeout_advice`, not on `mode`

`run_in_process` decides "not an in-process tool" with `spec.timeout_advice is None`. `ToolSpec.mode` (`RunMode`) is the declared discriminator, and `_run` already uses it. A row that gains or loses advice would silently change routing. Use `spec.mode is not RunMode.IN_PROCESS`.

### [NOTE] Re-exports with no consumer in the MCP package

`OperationDeps = Deps` (`wiring.py:80`) has no consumer anywhere in the repository. `Store` and `UserConfig` in `__all__` are not used by anything in `src/amoeba/mcp`, which uses `invoke`, `result_document`, `start_child`, `LaunchError`, `OPERATIONAL_ERRORS`, the deadline helpers and `load_config`. The task file (`226-tasks.mcp-server.md:94`) asked for this surface for a typed `ToolSpec.call` that the code no longer has. Remove the unused names.

### [NOTE] Detached child's `Popen` handle is dropped without a wait

`_start` keeps only `child.pid` and drops the `Popen` object. Nothing waits on the child, so it stays a zombie until CPython's `subprocess` cleanup reaps it, which happens on a later `Popen` call. The server's own `subprocess.run` calls usually trigger that. A session that makes only detached starts keeps one zombie per start. Keep the handles in a small registry that is reaped on the next start, or document why the bound is acceptable.

### [NOTE] Package docstring says MCP types come through `wiring`, but they do not

The docstring says the types the package names "come through `wiring`". `mcp/tools.py` imports the request models directly from `amoeba.operations.*`, `detached.py` imports `amoeba.operations.handle_pause_call`, and `in_process.py` imports `amoeba.operations.names`. The boundary test permits all of these, so only the sentence is wrong. Reword it to say that operation types are imported from `operations`, and that `wiring` supplies only what the boundary forbids.

### [PASS] Answer column list and insert arity agree

`ANSWER_COLUMNS` now lists 15 columns, with `via` last. Its readers agree with it: `answer_from_row` reads index 14, `decisions.py:22` derives `_ANSWER_WIDTH` from the same string, and `questions.py:144` and `sql.py:348` select the same list. `INSERT_RECORDED_ANSWER` (`sql.py:290`) has seven placeholders, matched by the seven-value tuples in `add_pm_answer` and in `settle_answered` (`answers.py:290`).

### [PASS] Deadline constants and documented numbers agree

The docstring's "150.5 s for the config contract's example" checks out. `resume_bound_seconds(60)` = 60 + 0.5 + 2×30 + 2×5 + 5 = 135.5 (`src/amoeba/operations/resume.py:50-64`, with `RUN_POLL_TIMEOUT_SECONDS` = 30 in `deps.py:29` and `TERMINATE_GRACE_SECONDS` = 5 in `processes.py:28`). Adding 3×5 s of store waits gives 150.5. The install doc's `tool_timeout_sec = 185` (`docs/mcp-server.md:49`) is the 180 s deadline plus 5. `resume_bound_seconds` grows with `resume_wait_seconds` at slope 1, so the `largest` value in `check_deadline` (`wiring.py:273`) is correct.

### Run Digest

- Response length: 10013 chars
- Response is newline-free: no
- Tool calls made: 18
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 19
- Tokens — prompt / cached / cache write / completion / reasoning: 1318355 / 1022644 / 295697 / 56795 / not computed
- Duration: 239.1 s
- Cost: $0.36 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
