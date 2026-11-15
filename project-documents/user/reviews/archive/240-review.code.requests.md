---
docType: review
layer: project
reviewType: code
slice: requests
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/240-slice.requests.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 6381418511fbf51685d5d6502e79a741896ddda2
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
diffTruncated: false
effort: xhigh
turns: 25
promptTokens: 3039546
cachedTokens: 2477625
cacheWriteTokens: 561903
completionTokens: 84116
durationSeconds: 381.8
costUsd: 0.993603
costBasis: provider
runId: run-20261115-p6-07f76ef9
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: security-hygiene
    summary: "Caller text is recorded in message_rejections with no length bound"
    location: "src/amoeba/operations/message_document.py:14"
  - id: F002
    severity: concern
    category: performance-resource
    summary: "Status, list and inbox read every retained row with no cap"
    location: "src/amoeba/operations/status_requests.py:50"
  - id: F003
    severity: note
    category: security-hygiene
    summary: "Any directory in no member can act as any active member"
    location: "src/amoeba/operations/message_member.py#resolve_caller"
  - id: F004
    severity: note
    category: architectural-decay
    summary: "Note-only paths in a slice that writes only requests"
    location: "src/amoeba/store/vocabulary.py#MessageKind"
  - id: F005
    severity: note
    category: error-handling-observability
    summary: "Rejection text prints an empty code when the code is missing"
    location: "src/amoeba/cli/render/messages.py:154"
  - id: F006
    severity: pass
    category: correctness
    summary: "Moved names, SQL placeholder counts and transaction boundaries check out"
    location: "src/amoeba/store/sql_messages.py"
---

# Review: code — slice 240

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 23 successful tool call(s) of 24 made; 431738 of 431738 diff characters reached the model

## Findings

### [CONCERN] Caller text is recorded in message_rejections with no length bound

`declared_text` returns the caller's `id`, `to`, `parent` and `member` exactly as given, whatever their length. `record_declared` (`src/amoeba/operations/message_rejection.py:78`) writes them into `message_rejections`. This covers malformed documents, where validation never runs, so nothing caps those values. The validated path has the same gap: `to` and `member` are `NonBlankText` (`src/amoeba/operations/set_up_models.py:29`), which has no maximum length. An unresolved `to` reaches `message_rejections.detail` through `UNKNOWN_RECIPIENT`, and a mismatched `member` reaches it through `MEMBER_MISMATCH` and `NOT_A_MEMBER` (`src/amoeba/operations/message_member.py:83` and `:92`).

Everything else the message operations store is bounded. `docs/cli-contract.md:572` promises that over-limit text is refused, never cut. The existing calls log also bounds its detail when it writes (`src/amoeba/operations/calls_log.py:91`). So an MCP `send` with a multi-megabyte `id` is stored in full, and the row comes back in every `status` and `list` result (as `rejected_calls`, and in `-j`) until retention prunes it.

Suggested fix: cap the raw fields at the same limits as their validated forms, storing an over-limit value as a marker. Give `to` and `member` a stated maximum in the request models.

### [CONCERN] Status, list and inbox read every retained row with no cap

`read_member_messages` loads every retained rejection for each member on every `status` and `list` call. It calls `rejections_of` (`src/amoeba/store/message_rejections.py:50-54`), and `SELECT_REJECTIONS_OF` (`src/amoeba/store/sql_messages.py:131`) has no `LIMIT`. The text shows five (`REJECTED_CALLS_SHOWN`), but the query, the object build and the `-j` document all cover the whole retention window.

Writes are uncapped too. Each refused call adds a row in its own write transaction, so an agent that loops on a refused call grows the table, and every later status call reads all of it.

`inbox` without `since` has the same shape. `requests_of` (`src/amoeba/operations/inbox.py:76`, backed by `SELECT_REQUESTS_OF` at `sql_messages.py:71`) returns every held request with its full body, up to 4000 characters each, and nothing limits how many.

Suggested fix: cap each read (newest N rejections, a page of inbox requests), return a `total` or `truncated` field saying how many were left out, and state the cap in the contract.

### [NOTE] Any directory in no member can act as any active member

`resolve_caller` accepts an explicit `member` from a directory in no member, if that member is active, so the call acts as that member. `reply` accepts the addressee named this way. `cancel` checks nothing about its caller (`src/amoeba/operations/cancel.py`).

The design records this (D3, and the tool descriptions say "whoever names the id may cancel"), so it is a decision rather than a defect. It does mean any process that can run `amoeba` can reply to or cancel a request if it knows the id. Ids are chosen by the sender and are easy to guess (`ask-1` in the tests). `ID_REUSED` also tells a caller that another member already holds an id.

Please confirm this is the intended trust model before agents from untrusted sources rely on requests.

### [NOTE] Note-only paths in a slice that writes only requests

`MessageKind.NOTE`, `Message.to_program` (always null, since nothing writes it), the `note` branches of the `messages` CHECK constraints, `effective_state`'s `None` return, the note refusal in `RequestView.from_message`, and the `insert_note` test helper all serve slice 243. No code in this slice writes a note.

The schema reason holds: `006_messages.sql` says SQLite cannot widen a CHECK without a rebuild, so the vocabulary has to exist now. The Python side is dead code in this slice, and the tests that exercise it insert rows by raw SQL.

Keep the schema. Either drop the Python note branches until 243, or record in the design that they are accepted scaffolding.

### [NOTE] Rejection text prints an empty code when the code is missing

`_rejection` takes `code: RejectCode | None` and prints `rejected: : <detail>` when the code is None. Every caller passes a code, so this branch is unreachable today. If the invariant ever breaks, though, the output shows an unlabelled rejection instead of failing, which is the silent fallback the project rules rule out. Make the code required where the result is rendered, or raise when it is absent.

### [PASS] Moved names, SQL placeholder counts and transaction boundaries check out

Checked by targeted search and the cited lines:
- Modules that lost imports (`changes_models`, `report_release_models`, `rm`, `mcp/tools.py`, `wiring.py`) have no remaining references to the removed names.
- `handle_pause.py` defines `logger` and imports `StoreError`.
- The parameter tuples for the `sql_messages` statements I traced (`UPDATE_STATE`, `INSERT_REQUEST`, the sweep statements, `SELECT_REQUESTS_CHANGED_SINCE`, `SELECT_LIVE_CHILDREN_OF_MEMBER`, `SELECT_SWEEP_DUE`) match their placeholder counts.
- `apply_removal` runs the cascade inside the removal transaction, after `remove_member` makes the member inactive, so the notice goes only to the surviving party.
- `Store.write` uses `BEGIN IMMEDIATE` and `Store.read` uses a deferred transaction.

### Run Digest

- Response length: 8034 chars
- Response is newline-free: no
- Tool calls made: 24
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 25
- Tokens — prompt / cached / cache write / completion / reasoning: 3039546 / 2477625 / 561903 / 84116 / not computed
- Duration: 381.8 s
- Cost: $0.99 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
