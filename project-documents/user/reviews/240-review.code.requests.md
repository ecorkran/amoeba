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
reviewedSha: 329adf13deeee76ef61b951aa49fac95e6979f8a
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 15
diffTruncated: false
effort: xhigh
turns: 16
promptTokens: 1843526
cachedTokens: 1298759
cacheWriteTokens: 544755
completionTokens: 56442
durationSeconds: 264.7
costUsd: 0.851818
costBasis: provider
runId: run-20261115-p6-07f76ef9
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: performance-resource
    summary: "Recipient inbox output has no per-recipient bound, so the \"bounded\" claim is overstated"
    location: "src/amoeba/operations/inbox.py#_read"
  - id: F002
    severity: concern
    category: correctness
    summary: "`send` accepts a request addressed to the sender itself"
    location: "src/amoeba/operations/send.py#send"
  - id: F003
    severity: concern
    category: architectural-decay
    summary: "`status()` is over the function-length guideline and this slice extended it"
    location: "src/amoeba/operations/status.py#status"
  - id: F004
    severity: note
    category: security-hygiene
    summary: "`cancel` has no caller check, by design (D3)"
    location: "src/amoeba/operations/cancel.py#cancel"
  - id: F005
    severity: note
    category: architectural-decay
    summary: "Note-kind schema is in place with no writer in slice 240"
    location: "src/amoeba/store/schema/006_messages.sql"
  - id: F006
    severity: note
    category: performance-resource
    summary: "`message_rejections` has no index on `member_id`"
    location: "src/amoeba/store/schema/006_messages.sql"
  - id: F007
    severity: note
    category: error-handling-observability
    summary: "`_message_sweep_note` catches the base `StoreError`"
    location: "src/amoeba/operations/handle_pause.py:99-107"
  - id: F008
    severity: note
    category: performance-resource
    summary: "`--body-file` is read whole before the length limit applies"
    location: "src/amoeba/cli/commands.py#read_text_source"
  - id: F009
    severity: pass
    category: correctness
    summary: "Remote lookups run outside the store write lock"
    location: "src/amoeba/operations/send.py#send"
  - id: F010
    severity: pass
    category: documentation-drift
    summary: "Docs and code agree on the text limits and retention caps"
    location: "docs/cli-contract.md:572-584"
---

# Review: code — slice 240

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 15 successful tool call(s) of 15 made; 447077 of 447077 diff characters reached the model

## Findings

### [CONCERN] Recipient inbox output has no per-recipient bound, so the "bounded" claim is overstated

`message_models.py:39-44` says what `inbox`, `status` and `list` read is "bounded by how it is written". The only caps are per-sender (`MAX_REQUESTS_PER_SENDER`, 200) and per-member for rejections (100). A recipient has no cap on requests it receives. `inbox` without `since` calls `requests_of` (`store/messages.py`), which has no limit, and returns every held request it sent or received, each with its full body (up to 4000 characters, `RequestView.body`). Worst case is members × 200 requests with bodies in one result, which goes straight into an agent's context. `docs/store-contract.md:407` says "bounded by these caps times the members", which is accurate, but the code comment drops that qualifier. Either add a per-recipient limit or page `inbox`, or correct the comment. `status` and `list` also list every live received request with no limit.

### [CONCERN] `send` accepts a request addressed to the sender itself

`send` resolves the recipient and stores the request with no check that the recipient differs from the caller. A grep for equality checks between sender and recipient in `src/amoeba` returned nothing. In `store/message_transitions.py#change_state`, the party loop skips only `party == actor`. With `actor=None` (expiry, the removal cascade, or a cancel from a session in no member), a self-request writes two deliveries to the same member. The member sees a duplicate `expired` row. Refuse `to` equal to the caller with a rejection code, and add a test.

### [CONCERN] `status()` is over the function-length guideline and this slice extended it

`status()` runs from line 134 to 209, about 76 lines. Before this slice it was about 69, already over the ~50-line guideline. The slice added the message sweep (lines 157–159), the message read (194), the `notice` field (201), and the `messages` argument to `_program_status` (203). Move the message wiring (sweep, read, notice) into one helper so `status()` returns to a single purpose.

### [NOTE] `cancel` has no caller check, by design (D3)

Any member, or any session in no member, can cancel any request by id. `reply` checks the addressee; `cancel` does not. The module docstring, the `cancel` tool description ("whoever names the id may cancel") and D3 all say so, so this is a recorded decision. Residual risk: an agent in a third repo can end another pair's request, and the victim learns only from a delivery. Worth the PM confirming.

### [NOTE] Note-kind schema is in place with no writer in slice 240

`MessageKind.NOTE`, `messages.to_program`, the note branch of the `CHECK`, and the `Message` note docstrings have no writer in 240. Only the test helper `insert_note` uses them. The migration comment gives the reason: SQLite cannot widen a `CHECK` without a table rebuild, and 243 has no migration. That is a defensible trade. It is still unused code against the "resist complexity" rule, so confirm it is wanted.

### [NOTE] `message_rejections` has no index on `member_id`

`trim_rejections` (run on every rejection insert) and `rejections_of` filter on `member_id` and rely only on the `created_at` index, so both scan the table. The table is small (at most 100 rows per member), so the impact is minor. A `(member_id, id)` index would make it explicit.

### [NOTE] `_message_sweep_note` catches the base `StoreError`

The handler logs with `logger.exception` and returns a note, which the docstring justifies. It catches the whole `StoreError` family rather than a specific type, and it mirrors `_prune_note` (lines 87-96), which predates this slice. Consistent with existing code, so no change required, but it is a judgement call under the rule that asks for specific types.

### [NOTE] `--body-file` is read whole before the length limit applies

`read_text_source` reads the entire file or stdin before `SendRequest` rejects anything over 4000 characters. A very large file is fully loaded first. Reading at most `MAX_BODY_LENGTH + 1` bytes and rejecting when more arrives would bound it.

### [PASS] Remote lookups run outside the store write lock

`resolve_caller` and `resolve_recipient` (the `cf` calls) run before `store.write()` in `send`, `reply`, `cancel` and `inbox`. The write transactions in `send_write.py`, `reply.py` and `cancel.py` only do store work. `tests/load/test_messages_load.py::test_no_cf_call_runs_while_the_write_lock_is_held` checks this with a lock probe.

### [PASS] Docs and code agree on the text limits and retention caps

I checked `docs/cli-contract.md` ("Text limits" and "Caps") and `docs/store-contract.md` ("Effective state", "Who is told", "The delivery sequence", "The sweep", "Caps", "Retention") against the constants in `message_models.py`. The numbers match: 64, 200, 4000, 1000, 128, 100, 200 and 500. The `program-rules.md` notice text matches `quoted_data.py`.

### Run Digest

- Response length: 7026 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 1843526 / 1298759 / 544755 / 56442 / not computed
- Duration: 264.7 s
- Cost: $0.85 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
