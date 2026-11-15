---
docType: review
layer: project
reviewType: slice
slice: push-and-presence
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/241-slice.push-and-presence.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 591c6e844cef3570eb89541118186af934253f95
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 15
effort: xhigh
turns: 16
promptTokens: 810385
cachedTokens: 637687
cacheWriteTokens: 172684
completionTokens: 75709
durationSeconds: 350.0
costUsd: 0.30506
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: operations
    summary: "Restarting sessions does not load the new code"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:301"
  - id: F002
    severity: concern
    category: operations
    summary: "No undo once the backups are deleted"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:316"
  - id: F003
    severity: concern
    category: error-handling
    summary: "The watcher's handler misses exception types that end the server"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:127"
  - id: F004
    severity: concern
    category: failure-modes
    summary: "`resources/read` and `unsubscribe` have no stated failure handling"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:156"
  - id: F005
    severity: concern
    category: design-rules
    summary: "The registration form is decided, but its failure path is not"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:187"
  - id: F006
    severity: concern
    category: integration
    summary: "Waking treats an idle, non-push session as live"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:231"
  - id: F007
    severity: concern
    category: design-rules
    summary: "Verification steps 4–8 are written for a person at a terminal"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:268"
  - id: F008
    severity: note
    category: scope
    summary: "The heartbeat-before-poll ordering is not enforced"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:175"
  - id: F009
    severity: note
    category: operations
    summary: "Dead session rows persist until a sweep runs"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:316"
  - id: F010
    severity: note
    category: error-handling
    summary: "A `cf` failure at start leaves only a stderr line as the reason"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:138"
  - id: F011
    severity: note
    category: proportionality
    summary: "The custom loop may be avoidable, and the design does not show the check"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:116"
  - id: F012
    severity: note
    category: proportionality
    summary: "The departures section restates D1 to D7"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:198"
  - id: F013
    severity: pass
    category: integration
    summary: "Layering and dependency direction hold"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:90"
  - id: F014
    severity: pass
    category: integration
    summary: "The channel event carries no message text"
    location: "project-documents/user/slices/241-slice.push-and-presence.md:147"
  - id: F015
    severity: pass
    category: scope
    summary: "Scope covers the plan's entry for 241"
    location: "project-documents/user/slices/241-slice.push-and-presence.md#technical-scope"
---

# Review: slice — slice 241

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Restarting sessions does not load the new code

Special Considerations says a running `amoeba-mcp` is refused by the schema-7 store "until it restarts", and the walkthrough has the PM restart sessions once (line 307). A restart runs whichever `amoeba-mcp` is on PATH. The sibling 226 design installs both tools with `uv tool install --force <repo>` (226-slice, line 109), and this design never names that reinstall. A restart onto an old installed binary is refused again. The migration also runs in Phase 6, before review and merge, as 240's plan does, so during that window the installed tool and every session must run the slice's code. Add the reinstall before the migration and before the restarts, add a check of which binary resolves, and state what an install from `main` does during that window.

### [CONCERN] No undo once the backups are deleted

Line 212 says a downgrade is refused by the newer-schema guard. The only undo is restoring `amoeba.sqlite3.pre-007`, and line 301 deletes that backup at Phase 7, after review. After merge, reverting the slice leaves a schema-7 store that the reverted code refuses. The Undo bullet says the only state is `sessions` rows and reports "Dead ends found: none", which is wrong here. Either keep the backup past Phase 7 with a named cleanup, or state that the migration is one-way after merge and that a later revert needs a backup this design deleted.

### [CONCERN] The watcher's handler misses exception types that end the server

D2 handles only `StoreError` and `ContextForgeError`. The exit-3 set that 222 and 223 define, and that 226 names `OPERATIONAL_ERRORS`, also includes `ConfigError` and `AmoebaHomeError`, and the store opener and config reads can raise them. An unlisted exception propagates out of the task group, and with it out of `serve_pinned`. That ends the tools, although D2 says the tools keep serving. D2 also calls the handler "a process boundary". It is a task boundary inside the serving process. Under the CLAUDE.md exception rules it must either name each exception and give its reason (rule b) or re-raise. Pick one, list the types, and state what a tool call sees after the watcher stops.

### [CONCERN] `resources/read` and `unsubscribe` have no stated failure handling

Only `subscribe` gets failure handling (invalid params). `resources/read` is a new request path that reads the store for `highest_assigned_seq`, so it can hit `StoreBusyError` or another `StoreError`. The design does not say whether the client gets a JSON-RPC error, a retry or an empty result. It also does not say what `read` returns on a server with no member or for another URI, or what `unsubscribe` returns in those cases. The project criteria require each new message type to name its failure handling. Add a line for each.

### [CONCERN] The registration form is decided, but its failure path is not

D9 names the project `.mcp.json` form, and the first Development Approach step checks it "before anything is built on it", with D9 and the docs corrected "if it does not register the channel". D4 and D9 are still marked `Status: decided`, and no alternative form is named. If the check fails, the implementing agent has no decided path. Name the alternative registration and its consequences. If neither form registers, say the slice stops at step 1 with a `BLOCKED:` line.

### [CONCERN] Waking treats an idle, non-push session as live

Line 57 defines a row as "an amoeba-mcp is serving", not "push is on". Line 231 gives 244 `live_member_ids` as the one liveness rule, and the plan has 244 wake a repo only when no session is live. An open Claude Code session in a repo, with or without the flag, suppresses the wake. It polls only when someone types into it. The architecture's waking case is "a repo nobody is working in" (scenario D, step 3), so a request to a repo with an open idle session waits for a person. Either 244 needs a signal that means someone is working, or this design should state that an idle session suppresses waking, so 244 can decide whether that is acceptable.

### [CONCERN] Verification steps 4–8 are written for a person at a terminal

Steps 4 to 8 are marked "By hand", and step 4 asks someone to accept the start-up screens. The Amoeba design rules say the AI runs the walkthrough and the PM is never asked to do it. Steps 5, 7 and 8 mostly repeat success criteria the automated tests already cover: the non-member server with no row, the clean-exit delete, and the stale-row prune. Either have the pty harness or a fixture test drive each step, or cut the manual steps and point to the tests.

### [NOTE] The heartbeat-before-poll ordering is not enforced

The architecture says a session heartbeats "much less often than the push check" (240-arch, Delivery). D7 enforces only `session_stale_seconds` at least twice `session_heartbeat_seconds`. A config with heartbeat at or below the poll interval passes validation and adds the writes the architecture's write-load note is meant to limit. Either enforce a minimum ratio, or state that the architecture's wording is advisory.

### [NOTE] Dead session rows persist until a sweep runs

The walkthrough says the rows are "bounded by live processes plus the stale window". Line 169 is accurate: rows from dead processes stay until a sweep, and the sweep runs only in write, `list` and `status` calls. The stale window limits what `list` shows, not how many rows exist. State the sweep as the bound, and say why the expected call rate makes that acceptable.

### [NOTE] A `cf` failure at start leaves only a stderr line as the reason

When `cf` times out at start, the server serves tools with no presence. `list` shows the repo with "no live session" and no reason. The reason is in one ERROR log line that the PM sees only in the client's MCP log. This is a degraded mode, not a value fallback, so the project rule against silent fallbacks does not strictly apply. The design should still say how an operator learns the reason, or accept the log as the only record.

### [NOTE] The custom loop may be avoidable, and the design does not show the check

D1 replaces the SDK-negotiated pin with a custom loop on low-level SDK modules, which is the heaviest option in the design. The rejected list covers an environment variable and catching the probe, but not an SDK setting that restricts the supported protocol versions. I could not check that here: the repo's `.venv` has no `mcp` package, so I have not verified the SDK behavior. Record whether the version list was checked. If it can pin, the custom loop is not needed.

### [NOTE] The departures section restates D1 to D7

Seven departure bullets repeat decisions already stated in D1, D3, D4, D6 and D7. The docs step needs the list, but each bullet can be one line pointing to its D-section.

### [PASS] Layering and dependency direction hold

The store imports nothing from `operations` or `mcp`. `channel_event.py` is pure. The store opener is injected, so the watcher does not depend on a concrete store. The MCP layer depends on operations, not the reverse. This matches the architecture's separation, and the import-boundary tests the design cites exist in the repo.

### [PASS] The channel event carries no message text

The content and meta contain only enum values, counts, sequence numbers and the counterparty member id, which Context Forge assigns. This matches the architecture's principle that message text is data, and D4's rejection of sender-controlled subjects and request ids is correct.

### [PASS] Scope covers the plan's entry for 241

Every item in plan entry 241 maps to a decision and a success criterion: the handshake loop, the watcher, the channel event, the resource, migration 7 with `sessions` and its prune, the three keys, `list` and `status`, the docs, the live test and the live-store migration. The departures from the plan (the pin mechanism, the `directory` column, the sweep parameter) are declared.

### Run Digest

- Response length: 11167 chars
- Response is newline-free: no
- Tool calls made: 15
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 16
- Tokens — prompt / cached / cache write / completion / reasoning: 810385 / 637687 / 172684 / 75709 / not computed
- Duration: 350.0 s
- Cost: $0.31 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15
