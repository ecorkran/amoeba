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
reviewedSha: 5f5483b74c8066c4bd7557561b661bf681b8112e
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
effort: high
turns: 11
promptTokens: 509084
cachedTokens: 395937
cacheWriteTokens: 113135
completionTokens: 10201
durationSeconds: 85.0
costUsd: 0.59501
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Layering, dependency direction and the two-doors principle hold"
    location: "project-documents/user/slices/226-slice.mcp-server.md#Architecture"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Failure modes of the stdio server and in-process calls are not enumerated"
    location: "project-documents/user/slices/226-slice.mcp-server.md#State Management"
  - id: F003
    severity: concern
    category: integrity
    summary: "Nothing tells the agent that `answer` text must be the PM's own words"
    location: "project-documents/user/slices/226-slice.mcp-server.md:131"
  - id: F004
    severity: note
    category: plan-alignment
    summary: "Detached tools return a receipt, not the operation's result"
    location: "project-documents/user/slices/226-slice.mcp-server.md:35-36"
  - id: F005
    severity: note
    category: proportionality
    summary: "Some of the design could be trimmed"
    location: "project-documents/user/slices/226-slice.mcp-server.md#D3"
---

# Review: slice — slice 226

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Layering, dependency direction and the two-doors principle hold

- **Two doors:** `cli` and `mcp` both sit above `operations` and `wiring`. D10's same-functions test and the AST import rules enforce "no logic of their own" (arch, Principle "One operation, two doors").
- **Detached long calls:** `handle_pause` and `answer` start the ordinary `amoeba` CLI, as the architecture says.
- **Process lifetime:** the stdio server lives only while a client is connected and starts no work on its own. That matches the architecture's "nothing to run" and its MCP bullet under Technical Considerations ("first MCP slice names the library and runs store calls off the async loop").
- **Sibling slices:** the home-helper rule matches 222's line 123 ("Only `cli` (and 226's MCP layer) calls `amoeba_home()`"). 223's `answer` already expects 226 to pass input through unchanged (223 line 258). `processes.py` sits under `operations`, so `mcp` importing it does not break the rule against importing `upstream` or `answering`.
- **No MCP-specific NFR:** the architecture states none.

### [CONCERN] Failure modes of the stdio server and in-process calls are not enumerated

The slice adds two new I/O paths: the stdio session and worker-thread calls that run `cf` and `sq` subprocesses. D7 maps operational errors and unexpected exceptions. It does not cover these cases:
- **Client disconnects or cancels mid-call.** The slice does not say what happens to the worker thread that is already running. It does not say whether the store closes in a `finally`. It does not say whether a `mark_read` or `set_up` write that is in flight completes. `anyio.to_thread.run_sync` does not abandon the thread on cancel by default, but the design does not state its choice.
- **Hang or slow call.** D4 notes that `status` "can take seconds." No timeout is named for the `cf` and `sq` runners in `default_deps`. The slice does not say whether it relies on timeouts from 223 and 224 or on the client's own tool timeout.
- **Server ending.** The design does not say that stdin EOF ends the server cleanly. It also does not say what happens to detached children when the client session ends. The children are in their own session and survive, but the slice does not state this.
- **Log setup failure.** The slice does not say how a failure to create `logs/mcp/<operation>/` or open the logs is reported. An `OSError` there might fall into D7's generic "internal error" path.

Fix: add a short failure-mode table in D4 or D7, with one row per case and its handling. It can be mostly "worker finishes, store closes in `finally`, result is discarded."

### [CONCERN] Nothing tells the agent that `answer` text must be the PM's own words

The architecture's record principle and its precedent rule depend on `answered_by: pm` meaning the PM decided. "PM answers become precedent," and a recorded answer resumes a run whose agents have tools. Over MCP, any agent session can call `answer`. D1's instructions say only that tools use the CLI's names and that long tools return receipts. The `answer` tool description (D3) is the summary plus the receipt sentence. Special Considerations (line 346) accepts that "the agent acts for the PM" but does not make the agent say so.

An eager or misled agent could record its own judgment as a PM decision. That corrupts the record and the precedent set, and `decisions` could not reveal it.

Fix: have the server instructions and the `answer` tool description say that `text` must be a decision the PM actually gave in this conversation, and that the agent must not compose it. This is a constant string, so it adds no mechanism. `answer` is already not marked read-only, so clients will prompt as usual.

### [NOTE] Detached tools return a receipt, not the operation's result

The slice plan's criterion reads "same inputs and results." The architecture allows the exception ("long work over MCP starts a detached CLI process and returns at once"), so the design is within bounds. Because `answer` is always detached, a `rejected / no_such_question` or `not_delivered` outcome appears only in the stdout log. The receipt carries no exit code, so an empty log cannot be told apart from a child that is still running or one that was killed. `status` and `decisions` cover the visible outcome, and D9 documents how to read the receipt. Consider one sentence in the tool description telling the agent to confirm a recorded answer through `decisions` rather than assume it.

### [NOTE] Some of the design could be trimmed

The slice plan sizes this at effort 2, and the design adds quite a lot to it. Two parts go beyond what the plan's criteria need:
- **D3's shared `OPERATION_SUMMARIES`.** It makes the CLI argparse help come from the same mapping, which widens the CLI edit. The plan's criteria are same names and no logic in the MCP layer, and `OperationName` plus the names parity test deliver both. Tool descriptions can be written in `tools.py`, and the summaries can be shared later if they drift.
- **D9's tool table.** It restates D2. A link to the tool table would do.

The `wiring.py` and `build_parser()` extractions are justified by the same-functions and same-argv tests, so they stay.

### Run Digest

- Response length: 6171 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 11
- Tokens — prompt / cached / cache write / completion / reasoning: 509084 / 395937 / 113135 / 10201 / not computed
- Duration: 85.0 s
- Cost: $0.60 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
