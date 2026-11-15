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
reviewedSha: ed93703339ce07d9129b1670638ebfc0b24ea4cb
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 21
diffTruncated: false
effort: xhigh
turns: 22
promptTokens: 2207399
cachedTokens: 1664691
cacheWriteTokens: 542694
completionTokens: 81199
durationSeconds: 369.2
costUsd: 0.923636
costBasis: provider
runId: run-20261115-p6-07f76ef9
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "`cancel` silently drops an explicit `--member` that names no active member"
    location: "src/amoeba/operations/message_member.py:101-114"
  - id: F002
    severity: concern
    category: correctness
    summary: "A retried `send` whose parent was pruned is refused, not answered `unchanged`"
    location: "src/amoeba/operations/send_write.py:53-63"
  - id: F003
    severity: concern
    category: architectural-decay
    summary: "Schema and types for notes and `to_program` ship in 240 with no writer"
    location: "src/amoeba/store/schema/006_messages.sql:7-9, 14, 17, 39-40"
  - id: F004
    severity: concern
    category: test-debt
    summary: "The contract test for text limits passes when a limit is a prefix of a documented number"
    location: "tests/test_contract_docs.py#test_the_cli_contract_states_every_message_text_limit"
  - id: F005
    severity: note
    category: type-contract-debt
    summary: "The TTL config key has no upper bound, so a huge value fails mid-send"
    location: "src/amoeba/config/user_config.py:80"
  - id: F006
    severity: note
    category: performance-resource
    summary: "Rejection rows and child lookups are unbounded on the read path"
    location: "src/amoeba/operations/status_requests.py#read_member_messages"
  - id: F007
    severity: note
    category: architectural-decay
    summary: "`wiring.py` has grown past the file-size guide"
    location: "src/amoeba/wiring.py"
  - id: F008
    severity: note
    category: architectural-decay
    summary: "`CallerResolution` is dead code"
    location: "src/amoeba/operations/message_member.py:60"
  - id: F009
    severity: note
    category: architectural-decay
    summary: "The rejection-recording call is repeated in three places"
    location: "src/amoeba/operations/reply.py:104-113"
  - id: F010
    severity: note
    category: documentation-drift
    summary: "The write-advice text names `send` for `reply` and `cancel` too"
    location: "src/amoeba/mcp/message_tools.py#MESSAGE_WRITE_ADVICE"
  - id: F011
    severity: note
    category: type-contract-debt
    summary: "`RequestView` holds encoded timestamp strings where the other models hold `datetime`"
    location: "src/amoeba/operations/message_results.py#RequestView"
  - id: F012
    severity: pass
    category: performance-resource
    summary: "No `cf` call runs under the store write lock"
    location: "src/amoeba/operations/send.py:35-60"
  - id: F013
    severity: pass
    category: correctness
    summary: "A rejection row written before a `return` inside `store.write()` is committed"
    location: "src/amoeba/store/store.py:119-123"
---

# Review: code — slice 240

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 21 successful tool call(s) of 21 made; 418437 of 418437 diff characters reached the model

## Findings

### [CONCERN] `cancel` silently drops an explicit `--member` that names no active member

`resolve_actor` turns every `NOT_A_MEMBER` refusal into `UnknownActor` (lines 111-113). From a directory in no member, `resolve_caller` returns `NOT_A_MEMBER` for an explicit `member` that is not active (lines 91-97). So `amoeba cancel ID --member <typo>` from outside any repo succeeds. It returns `cancelled` with `direction: null`, both parties are told, and the bad name is never reported.

The same input is refused elsewhere. `send`, `reply` and `inbox` return `not_a_member` and name the member. From inside a member's directory, `resolve_caller` returns `member_mismatch` (lines 84-89). The contract (`docs/cli-contract.md`, around line 614) and design D3 cover the case with no `member` given. Neither covers an unknown explicit name. The test `test_an_actor_resolution_gives_an_unknown_actor_where_a_member_is_missing` pins the drop. Core Principles say "Never use silent fallback values". Fix: return `UnknownActor` only when `member is None`, and keep the refusal otherwise.

### [CONCERN] A retried `send` whose parent was pruned is refused, not answered `unchanged`

`write_send` checks the parent (lines 56-60) before it looks up an existing row with the same `id` (lines 61-63). Once the parent is pruned, `_check_parent` returns `PARENT_UNKNOWN` (lines 86-90). A retry of a child that is already stored, with the same content, is then refused, and a `message_rejections` row is written.

This breaks the contract. `docs/cli-contract.md` (around line 616) says a retried `send` is `unchanged` or `request_ended`. The `send` tool description says "sending the same `id` with the same content again changes nothing, so a retry is safe." The case is reachable: a child that is still `accepted` never expires, so it can outlive its parent's 30-day retention. Fix: look up `existing` before the parent check, and return `unchanged` or `request_ended` for a same-content resend. Add a test that sends a child under a parent, ends the parent, advances past retention, and resends the child.

### [CONCERN] Schema and types for notes and `to_program` ship in 240 with no writer

`kind` accepts `'note'`, `to_program` is a foreign key, and the CHECK has a note branch. The code carries the same surface: `MessageKind.NOTE` in `store/vocabulary.py`, `Message.to_program` in `store/models.py:180`, the note branch in `effective_state`, and the note rejection in `RequestView.from_message`. The tests add `insert_note` and three note tests. A grep of `src/` finds no writer of `kind='note'` or `MessageKind.NOTE`. The migration comment gives a real reason (SQLite cannot widen a CHECK in place). Still, this slice's rules say to resist complexity and to build the feature or delete it from the design. Since 006 is unmerged, dropping the note kind and `to_program` now is the cheapest option. If they stay, record the decision in the slice design, not only in the SQL comment.

### [CONCERN] The contract test for text limits passes when a limit is a prefix of a documented number

The check is `f" {limit}" not in paragraph`. `" 100"` is a substring of `" 1000"`, and the paragraph documents the `reason` limit as `1000` (`docs/cli-contract.md:572-575`). So a `MAX_REASON_LENGTH` of 100 passes, which is the drift this test exists to catch. The same happens for 20 against 200. Fix: match whole numbers, for example with `(?<!\d)100(?!\d)`, or check each limit against its own field phrase in the paragraph.

### [NOTE] The TTL config key has no upper bound, so a huge value fails mid-send

`request_open_ttl_hours` is `Field(ge=1)` with no maximum. `send_write.py:73` builds `timedelta(hours=...)`, and `insert_request` computes `now + ttl`. A value above about 70 million hours overflows `datetime` inside the write transaction. The failure is an uncaught `OverflowError`, not a config error at load. Add a `le=` bound.

### [NOTE] Rejection rows and child lookups are unbounded on the read path

`rejections_of` returns every retained rejection for each member, with no limit. `status` and `list` put all of them in the JSON, while the text shows five. Retention bounds the total by time, not by count, and no write path caps the rows. `_request_entry` also runs `live_child_ids` once per live request, which is an N+1 pattern. Add a limit or a count to the rejections query, and state the cap in the design, since "every limit says what happens when it is hit" applies. Fetch the children of all parents in one query.

### [NOTE] `wiring.py` has grown past the file-size guide

The file is now 378 lines (the guide says about 300). The message dispatch adds a case block and union members. `wiring_messages.py` already holds the message logic. Move the `invoke` dispatch or the result aliases into a helper module.

### [NOTE] `CallerResolution` is dead code

The type alias is defined and exported in `__all__` (line 27), and nothing else uses it. Remove it, or use it in the `resolve_*` signatures.

### [NOTE] The rejection-recording call is repeated in three places

`reply._apply`, `cancel._record` (cancel.py:163) and `send_write._reject` (send_write.py:160) each repeat the same nine-argument `record_rejection` call, inside the write transaction. `message_rejection.record_refusal` (lines 38-47) repeats it again in its own transaction. Add one helper that takes a transaction and a refusal, and use it everywhere.

### [NOTE] The write-advice text names `send` for `reply` and `cancel` too

`MESSAGE_WRITE_ADVICE` ends "A repeated `send` with the same `id` is safe", and it is attached to `reply` and `cancel` as well. For those tools the sentence is misleading. Split the advice per tool, or drop the `send` clause for the others.

### [NOTE] `RequestView` holds encoded timestamp strings where the other models hold `datetime`

`RequestView` stores `created_at`, `accepted_at`, `state_changed_at` and `expires_at` as strings. `RequestEntry` and `RejectedCall` use `datetime`. The renderer parses the string back with `datetime.fromisoformat(view.created_at)` in `cli/render/messages.py`. Keep `datetime` in the models and encode at the serializer.

### [PASS] No `cf` call runs under the store write lock

Each operation resolves `cf` (the caller, the recipient, and in `reply` and `cancel` the caller) before it opens `store.write()`. `write_send`, `_apply` and `inbox`'s read run only store work. `test_no_cf_call_runs_while_the_write_lock_is_held` checks this with a lock probe.

### [PASS] A rejection row written before a `return` inside `store.write()` is committed

`write()` runs `BEGIN IMMEDIATE`, yields, and commits on normal exit. The `return _reject(...)` paths in `write_send` and `_apply` therefore commit their rejection rows, as the design requires. Rollback happens only when the block raises.

### Run Digest

- Response length: 10644 chars
- Response is newline-free: no
- Tool calls made: 21
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 22
- Tokens — prompt / cached / cache write / completion / reasoning: 2207399 / 1664691 / 542694 / 81199 / not computed
- Duration: 369.2 s
- Cost: $0.92 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
