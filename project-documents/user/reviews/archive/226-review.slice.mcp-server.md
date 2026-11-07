---
docType: review
layer: project
reviewType: slice
slice: mcp-server
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/226-slice.mcp-server.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 61fc488988a461e118c4ba5ec6059d40c1bed4bc
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
effort: high
turns: 7
promptTokens: 313863
cachedTokens: 201897
cacheWriteTokens: 111958
completionTokens: 11874
durationSeconds: 94.6
costUsd: 0.58762
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Two doors over one set of operations, with the long-work split the architecture describes"
    location: "project-documents/user/slices/226-slice.mcp-server.md:33-37"
  - id: F002
    severity: pass
    category: dependencies
    summary: "Dependency direction and layering are correct"
    location: "project-documents/user/slices/226-slice.mcp-server.md:93"
  - id: F003
    severity: pass
    category: architecture-alignment
    summary: "Resident server reconciled with \"nothing to run\", and store calls kept off the loop"
    location: "project-documents/user/slices/226-slice.mcp-server.md:117-119"
  - id: F004
    severity: concern
    category: layer-boundaries
    summary: "`HandlePauseCall` puts a new input model and validation rule in the MCP layer"
    location: "project-documents/user/slices/226-slice.mcp-server.md:141,189"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Shutdown and cancel behavior with a slow in-flight `status` is stated too optimistically"
    location: "project-documents/user/slices/226-slice.mcp-server.md:211-213"
  - id: F006
    severity: note
    category: architecture-alignment
    summary: "`answer` is described as \"always ends in a resume\", which doesn't match the architecture"
    location: "project-documents/user/slices/226-slice.mcp-server.md:36"
  - id: F007
    severity: note
    category: dependencies
    summary: "Soft dependency on 225 is stated inconsistently"
    location: "project-documents/user/slices/226-slice.mcp-server.md:64,220,317"
  - id: F008
    severity: note
    category: proportionality
    summary: "Proportionality: a few items could be cut or deferred"
    location: "project-documents/user/slices/226-slice.mcp-server.md:136-157"
---

# Review: slice — slice 226

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Two doors over one set of operations, with the long-work split the architecture describes

The design matches the "One operation, two doors" principle in the architecture. It uses the CLI's names. In-process tools return the operation's own result models. Long work starts a detached CLI process and returns a receipt. `OperationName`, one `ToolSpec` table and the D10 parity tests (names, functions, argv) enforce "same names, no logic of its own" mechanically. The slice plan's success criteria are all covered.

### [PASS] Dependency direction and layering are correct

`cli` and `mcp` both depend on `operations` and `wiring`, and `mcp` imports nothing from `store`, `upstream`, `answering` or `cli`. An import-boundary test backs this up. Extracting `wiring.py` and `build_parser()` out of `cli/main.py` is the least intrusive way to share setup between the doors. The prerequisites (222 to 224) match the plan, and 227 can add an operation by adding a row.

### [PASS] Resident server reconciled with "nothing to run", and store calls kept off the loop

The architecture says no Amoeba process exists until something calls it. A stdio MCP server lives for the length of a client session, which looks like a conflict. The design states the conflict and resolves it: the client starts and stops the server, and Amoeba starts nothing itself. It also meets the architecture's requirement to run synchronous store calls off the async loop. Each call gets its own worker thread and its own store connection, so no connection is shared across threads.

### [CONCERN] `HandlePauseCall` puts a new input model and validation rule in the MCP layer

The design says the MCP layer has no logic and that any gap "is fixed in the operation, not in the MCP layer" (lines 55, 289). `handle_pause` has no request model, because its signature is positional (`run_id`, `directory`). So 226 defines `HandlePauseCall` itself, with a rule that `run_id` is a non-empty string. D6 says this "adds no rule of its own". That holds only if the CLI and the operation already enforce the same non-empty check, and the design doesn't say they do. D10's parity tests cover the argv parse, but nothing ties `HandlePauseCall` to what the CLI or operation accepts. The two doors could therefore disagree on what a valid `handle_pause` request is.

Fix one of two ways:
- Put the `run_id` and `directory` request model in `operations`, owned by 223's `handle_pause`, with the CLI and MCP both using it. The absolute-path check stays as the one door-specific rule.
- State which existing rule `HandlePauseCall` mirrors, and add a D10 test that the CLI rejects the same `run_id` inputs.

### [CONCERN] Shutdown and cancel behavior with a slow in-flight `status` is stated too optimistically

D7 says a cancelled call's worker "runs to the end" (default `anyio` thread behavior). It also says that on stdin EOF `Server.run` returns and `main` exits 0. These two statements conflict when a call is in flight. The process cannot exit until the non-abandoned worker finishes. 224 makes one `cf get` call per distinct run directory, each bounded only by the `cf` timeout. So the exit delay is roughly N × timeout, not one timeout. D7's "Slow or hung `cf` or `sq`" row says "no new timeout is added" and doesn't mention this multiplier.

The same applies to client-side request timeouts. A client that times out and retries `status` leaves earlier workers running, so threads and `cf` subprocesses pile up.

Needed:
- State the actual bound on exit delay, and whether the server accepts it or caps it.
- Add a D10 case for EOF with a call in flight, so the exit behavior is tested.

### [NOTE] `answer` is described as "always ends in a resume", which doesn't match the architecture

The architecture says `answer` "starts the resume if the run is still at that pause". The resume step waits only briefly for the run to reach `running`, and it can end as `not delivered` or `refused`. The slice plan assigns `answer` to the detached mode, so this isn't a deviation. But the design never says why the brief-wait operation is detached. One consequence is that the agent relaying a PM decision learns of `no_such_question` or `not delivered` only by reading a log. A short rationale would help the implementer, and the wording should match the architecture.

### [NOTE] Soft dependency on 225 is stated inconsistently

The plan says 226 "does not wait on 225" and can run beside it. Prerequisites say 225 is not required. But D8 cites 225 D2 for the install command, D6 depends on the form of 225's `pgrep` reinstall guard, and the walkthrough needs 225 D1 for config and program registration. None of this blocks implementation, since `pyproject.toml` scripts install without 225 and the walkthrough already flags the 225 D1 need. Still, say once in Prerequisites that the end-to-end walkthrough and the install doc's `uv tool install --force` line depend on 225's decisions, and that 226 stays buildable without them.

### [NOTE] Proportionality: a few items could be cut or deferred

The design is generally proportionate to a "thin door" slice, and the heavier choices are justified (low-level server, detached starter, wiring extraction). A few items serve no stated consumer:
- **`annotations` hints and the `result_model` field in `ToolSpec`.** The `annotations` field has no consumer in any requirement, and `result_model` is only needed to publish the output schema. If agent clients don't use the hints, drop `annotations` for now.
- **D9's tool-table link and "how to read a `StartedCall`".** The server's own tool descriptions (D3) already say this.
- **The separate AST "no `Path.cwd`" test.** It repeats D5's rule and the D10 import-boundary test.

These are small trims and not blocking.

### Run Digest

- Response length: 6589 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 313863 / 201897 / 111958 / 11874 / not computed
- Duration: 94.6 s
- Cost: $0.59 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
