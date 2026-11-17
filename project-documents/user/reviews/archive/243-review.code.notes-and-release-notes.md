---
docType: review
layer: project
reviewType: code
slice: notes-and-release-notes
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/243-slice.notes-and-release-notes.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261117
dateUpdated: 20261117
reviewedSha: bdcaa3f3ffb6f247dac1df00e5dcaeaea0f1a8b4
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 18
diffTruncated: false
effort: xhigh
turns: 19
promptTokens: 1546632
cachedTokens: 1178612
cacheWriteTokens: 368006
completionTokens: 64228
durationSeconds: 291.5
costUsd: 0.638488
costBasis: provider
runId: run-20261117-p6-63c2f683
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: fail
    category: other
    summary: "Note volume deferred to issue #42 instead of built in the slice"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:318"
  - id: F002
    severity: concern
    category: error-handling-observability
    summary: "report-release discards the sweep's problem text"
    location: "src/amoeba/wiring_releases.py:37"
  - id: F003
    severity: note
    category: type-contract-debt
    summary: "`effective_state` still returns an optional state that callers now assume away"
    location: "src/amoeba/store/messages.py#effective_state"
  - id: F004
    severity: note
    category: architectural-decay
    summary: "The \"`to`, else `to_program`\" rule is written twice"
    location: "src/amoeba/operations/message_document.py#declared_recipient"
  - id: F005
    severity: pass
    category: correctness
    summary: "Every 240 `messages` select filters on kind or on a state that notes never have"
    location: "src/amoeba/store/sql_messages.py:94-198"
  - id: F006
    severity: pass
    category: test-debt
    summary: "Store-touching tests run against a throwaway home, and the new load tests cover the write-lock paths"
    location: "tests/conftest.py:15-26"
---

# Review: code — slice 243

**Verdict:** FAIL
**Model:** claude-haiku-5-5
**Evidence:** 17 successful tool call(s) of 18 made; 214419 of 214419 diff characters reached the model

## Findings

### [FAIL] Note volume deferred to issue #42 instead of built in the slice

The design says "Notes have no per-sender cap (requests have `MAX_REQUESTS_PER_SENDER`), and `inbox` returns every held note ... a cap is filed as issue #42." That defers in-scope behaviour to an issue, which the Amoeba Design Rules forbid: "A review that finds a deferral rejects it." The code matches the deferral. `write_note` (src/amoeba/operations/send_note.py:50-65) never applies a cap, while `write_send` does through `_make_room` (src/amoeba/operations/send_write.py:78). `SELECT_RECEIVED_NOTES` (src/amoeba/store/sql_messages.py:71-77) has no `LIMIT`, so `inbox`, and the MCP `inbox` tool, return every note a member holds with full bodies. A release-note body can run to 14,439 characters (docs/cli-contract.md:610). Inside the retention window one sender can therefore grow a recipient's inbox without bound, and each program note fans out to every other member. Fix: add a per-sender note cap with a stated outcome at the limit (a rejection, or pruning the oldest notes as `_make_room` does) and a bounded inbox read, or delete the cap sentence from the design if no cap is wanted. The second option changes the design, so the PM should decide it.

### [CONCERN] report-release discards the sweep's problem text

`sweep_messages` returns problem text when the store is busy (src/amoeba/operations/message_sweep.py:39-43). It logs the exception at ERROR first, so this is not silent. `place_release` calls it without using the return value, so `report-release` reports success with no sign that the sweep was skipped. The other callers keep the text: `status` stores it as `message_problem` (src/amoeba/operations/status.py:166) and `handle_pause` returns it (src/amoeba/operations/handle_pause.py:115). The comment above the call records the choice, but the release door hides a state the other doors show. Fix: surface the text in the report result's `notice` or `problems`, or state in the design why this door differs.

### [NOTE] `effective_state` still returns an optional state that callers now assume away

`effective_state` is still typed `RequestState | None` (src/amoeba/store/messages.py:60). The guard that raised on `None` left `reply._problem` and `cancel._problem` and moved into `as_request` (src/amoeba/operations/reject_codes.py). Both callers now format `state` into a refusal, so a `None` would read "already None" rather than fail. `as_request` makes that unreachable, but the types do not say so. `send_write._resend` keeps its own `state is not None` check, so the three sites disagree. Suggest one narrower helper used by all three.

### [NOTE] The "`to`, else `to_program`" rule is written twice

`declared_recipient` (raw document) and `SendRequest.recipient_ref` (validated model) each encode "`to` if set, else `to_program`". Both inputs are real, since the raw form serves malformed documents, so this is a small DRY gap and not a bug. A shared two-argument function would keep the rule in one place.

### [PASS] Every 240 `messages` select filters on kind or on a state that notes never have

Design D4 requires this audit. The only `FROM messages` queries in the store are in this file. Each request-only select carries `kind = 'request'`, or uses `LIVE_REQUEST` or `state IN (terminal)`, which a note's NULL state never matches. That covers `SELECT_LIVE_REQUESTS_OF`, `SELECT_REQUESTS_OF`, `SELECT_REQUESTS_CHANGED_SINCE`, `COUNT_REQUESTS_FROM`, `SELECT_OLDEST_TERMINAL_FROM`, `SELECT_DUE_REQUESTS` (the expire step) and the live-children read. The by-id reads (`SELECT_MESSAGE`, `DELETE_MESSAGE`) are used only by callers that check kind or state first.

### [PASS] Store-touching tests run against a throwaway home, and the new load tests cover the write-lock paths

The new `CREATE TRIGGER` in tests/cli/test_release_cli.py runs against `store_path()`, which is safe because the autouse `amoeba_home` fixture points `AMOEBA_HOME` at a fresh temp directory for every test. The live notes test asserts the same thing. Program-note writes and release-note writes inside the write lock each have a load test with latency, lock and row-count assertions (tests/load/test_messages_load.py and tests/load/test_report_release_load.py). These tests have not been run here.

### Run Digest

- Response length: 6967 chars
- Response is newline-free: no
- Tool calls made: 18
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 19
- Tokens — prompt / cached / cache write / completion / reasoning: 1546632 / 1178612 / 368006 / 64228 / not computed
- Duration: 291.5 s
- Cost: $0.64 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
