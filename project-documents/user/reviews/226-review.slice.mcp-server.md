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
reviewedSha: d7abb8b975e1a0cd857ccc7b945ab087cb6db4b6
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
effort: high
turns: 7
promptTokens: 412587
cachedTokens: 301924
cacheWriteTokens: 110653
completionTokens: 9580
durationSeconds: 80.7
costUsd: 0.569467
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Two thin doors over shared operations, with the architecture's one allowed difference"
    location: "project-documents/user/slices/226-slice.mcp-server.md#Technical Decisions"
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "Architecture's MCP-specific obligations are met"
    location: "project-documents/user/slices/226-slice.mcp-server.md:165-170"
  - id: F003
    severity: concern
    category: dependency-direction
    summary: "The import-boundary rule conflicts with the typed tool table"
    location: "project-documents/user/slices/226-slice.mcp-server.md:93"
  - id: F004
    severity: concern
    category: integration-contract
    summary: "`answer` is always detached, so the PM-answer path loses its immediate result"
    location: "project-documents/user/slices/226-slice.mcp-server.md:186"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for the new I/O paths"
    location: "project-documents/user/slices/226-slice.mcp-server.md:206-213"
  - id: F006
    severity: note
    category: proportionality
    summary: "Proportionality: some behavior and tests exceed what the slice must deliver"
    location: "project-documents/user/slices/226-slice.mcp-server.md:212"
  - id: F007
    severity: note
    category: security
    summary: "`answered_by: pm` rests on description text alone"
    location: "project-documents/user/slices/226-slice.mcp-server.md:163"
---

# Review: slice — slice 226

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Two thin doors over shared operations, with the architecture's one allowed difference

The tool names come from one `OperationName` enum, and `cli/main.py` registers its subcommands from it. The tool table places arguments and nothing else, and result models are returned unchanged. The only door-specific rules are the absolute-`directory` check and detached starts for long work. Architecture decision 4 and the principle "One operation, two doors" allow both. The no-logic claim is backed by parity tests for names, functions and argv. Exclusions are correct: MCP resources, notifications, HTTP and `report_release`/`changes` (227) stay out of scope.

### [PASS] Architecture's MCP-specific obligations are met

The architecture's Technical Considerations require that the first MCP slice names the library and runs store calls off the async loop. D1 names `mcp` 2.x and D4 runs every in-process call in `anyio.to_thread.run_sync`, with a store connection per call. The explanation of how a stdio server fits "nothing to run" (State Management) matches the goal. The server is started and stopped by the client session and Amoeba starts nothing itself. The "resume's environment" consideration is carried into D6 and D9.

### [CONCERN] The import-boundary rule conflicts with the typed tool table

The design says `mcp` imports nothing from `amoeba.store`, `upstream`, `answering` or `cli`, and D10 enforces this with an AST test. D2 gives `ToolSpec.call` the signature `(store, config, document, directory, deps)`. Under pyright strict (a stated requirement) those parameters need `Store` from `amoeba.store` and `UserConfig` from `amoeba.config`. The design doesn't say where `mcp` gets those types. Either the annotations break the rule the test enforces, or the rule is met by something unstated, such as a re-export from `wiring`, a Protocol, or loose `Callable[..., Any]` typing that weakens strict mode. The same ambiguity applies to the `deps` bundle type. 222's boundary rules are written around the module graph, so this needs a decision.
Fix: state the type source for `Store`, `UserConfig` and `deps` in the `mcp` layer, and make the AST rule match it. For example, `wiring` could re-export the types as its public contract, or the adapters could be built in `wiring` so `mcp` never names them.

### [CONCERN] `answer` is always detached, so the PM-answer path loses its immediate result

The plan's success criterion is "same inputs and results", and the architecture says only long work goes detached. The plan entry lists "`answer` with a resume" as the detached case. The design detaches every `answer` call, including ones with no resume. The architecture's resume procedure only waits "briefly" for the run to reach `running`, and D6 itself says the wait is bounded by `resume_wait_seconds`. So `answer` is not long work in the sense that `handle_pause` is, since it only waits for the answering run to finish. The cost is acknowledged. The agent relaying the PM's decision gets no synchronous `no_such_question`, `refused`, `not_delivered` or `rejected` outcome, and must read a log file or call `decisions`. That undercuts "Fail where someone can see it" on the most trust-sensitive operation, and it makes `answer` the one tool whose result differs from the CLI's.
Fix: either justify detaching by naming what in-process would break (the bounded wait is not the answer, because the worker thread already keeps the loop free), or run `answer` in a worker thread and return `AnswerResult`. If the plan's choice stands, state the deviation from the "same results" criterion in Success Criteria and say how an agent confirms a PM answer was recorded.

### [PASS] Failure modes are enumerated for the new I/O paths

Client cancel, slow or hung `cf`/`sq` (bounded by 224 D1's sum), stdin EOF with a call in flight, and log-directory or log-file creation errors each have an explicit handling strategy. Detached-child outcomes are handled too: a spawn error, an empty log meaning "still running or killed", and a missing `amoeba` script at start-up. `call_tool` as the process-boundary handler matches case (c) of the project's exception rule. Stdout corruption is closed off by the stdio design and a noisy-subprocess test.

### [NOTE] Proportionality: some behavior and tests exceed what the slice must deliver

The slice is rated effort 2, and the design carries a wiring/CLI extraction, six new modules, a custom low-level server, and ten test groups. The core choices are justified: the low-level server preserves the operations' own validation, and `wiring.py` is needed by both doors. These pieces could be cut or deferred without losing a requirement:
- **EOF-with-call-in-flight test and failure-mode row** (D10, D7). This pins the default `anyio` thread behavior and a shutdown delay the design itself says nobody waits on. The "Off the loop" test, `ASYNC` lint rules and the cancel/disconnect row already cover the real risks.
- **Repeated restatement of 224 D1's timeout sum and 225 decisions** in the failure table and prerequisites. A reference would do.
- **Output schemas for every tool.** This is only needed if a client consumes them. The architecture requires input shape fidelity, not output schemas, so this could be deferred unless a target client needs it.

### [NOTE] `answered_by: pm` rests on description text alone

D3 makes the `answer` description say that `text` must be a decision the PM actually gave. The architecture's "What an answer may authorize" section says the record is the check afterward, and the design accepts that as scenario C's intent. No finding is raised. The residual risk is that an agent which ignores the description records its own judgment as the PM's, and it gets precedent status. If this shows up in real use, `answer` could take a required quoted-PM-text field to make the provenance auditable in `decisions`.

### Run Digest

- Response length: 6917 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 412587 / 301924 / 110653 / 9580 / not computed
- Duration: 80.7 s
- Cost: $0.57 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Resolution

- **[PASS] Two thin doors over shared operations:** no change needed.
- **[PASS] Architecture's MCP-specific obligations are met:** no change needed.
- **[CONCERN] Import-boundary rule conflicts with the typed tool table:** changed. `wiring` now re-exports `Store`, `UserConfig` and the `deps` bundle type `OperationDeps` as its public contract. `ToolSpec.call` is typed with those, and the import rule and the D10 AST test now also bar `amoeba.config`, so `mcp` is typed under pyright strict without importing `store` or `config`.
- **[CONCERN] `answer` always detached:** changed. `answer` now runs in-process in a worker thread and returns `AnswerResult`, because its resume waits only `resume_wait_seconds` and the resumed run is spawned in its own session. D2 states the departure from the plan entry's wording and the reason. Only `handle_pause` stays detached, and Success Criteria names it as the one result that differs from the CLI's. The `answer` argv, door validation and refusal test are removed.
- **[NOTE] Proportionality:** changed. Removed the EOF-with-call-in-flight test and shortened its failure-mode row. The timeout row and the 225 prerequisite now refer to 224 D1 and to 225's decisions instead of restating them. Output schemas and the `result_model` field are dropped, because no requirement or client consumes them.
- **[NOTE] `answered_by: pm` rests on description text alone:** rejected, no change. The review raises no defect, and a required quoted-PM-text field would be new mechanism for a risk that hasn't appeared in use. The architecture relies on the record in `decisions` as the check afterward.
