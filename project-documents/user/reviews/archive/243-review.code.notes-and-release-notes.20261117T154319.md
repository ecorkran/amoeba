---
docType: review
layer: project
reviewType: code
slice: notes-and-release-notes
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/slices/243-slice.notes-and-release-notes.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261117
dateUpdated: 20261117
reviewedSha: 7d89b6a3819735e774455a6891b65bf78c4b7643
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 25
diffTruncated: false
effort: xhigh
turns: 26
promptTokens: 2690124
cachedTokens: 2331853
cacheWriteTokens: 358247
completionTokens: 66789
durationSeconds: 323.7
costUsd: 0.651563
costBasis: provider
runId: run-20261117-p6-63c2f683
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: pass
    category: correctness
    summary: "Notes stay out of request reads, the request cap and the request prune"
    location: "src/amoeba/store/sql_messages.py:109-112"
  - id: F002
    severity: concern
    category: performance-resource
    summary: "Notes have no count bound, and one `inbox` call returns all of them"
    location: "src/amoeba/store/sql_messages.py:69-75"
  - id: F003
    severity: concern
    category: architectural-decay
    summary: "The send rules are duplicated across the request and note paths"
    location: "src/amoeba/operations/send_write.py:200"
  - id: F004
    severity: note
    category: performance-resource
    summary: "`sweep_due` now scans `messages` on every read-then-write path without an index"
    location: "src/amoeba/store/sql_messages.py:190-196"
  - id: F005
    severity: note
    category: architectural-decay
    summary: "The note sweep lives in two places"
    location: "src/amoeba/wiring_releases.py#place_release"
  - id: F006
    severity: note
    category: error-handling-observability
    summary: "One held-sweep condition is logged twice"
    location: "src/amoeba/wiring_releases.py#place_release"
  - id: F007
    severity: note
    category: consistency-rot
    summary: "Cut-text pointer is shown for inbox only"
    location: "src/amoeba/cli/render/messages.py#render_send"
  - id: F008
    severity: note
    category: error-handling-observability
    summary: "Guards removed from `reply` and `cancel` rely on the schema"
    location: "src/amoeba/operations/reply.py#_problem"
  - id: F009
    severity: note
    category: consistency-rot
    summary: "Naming collisions and stale test comments"
    location: "tests/store/message_support.py:68"
  - id: F010
    severity: note
    category: type-contract-debt
    summary: "Type escapes in new code"
    location: "src/amoeba/operations/reject_codes.py#as_request"
---

# Review: code — slice 243

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 24 successful tool call(s) of 25 made; 203469 of 203469 diff characters reached the model

## Findings

### [PASS] Notes stay out of request reads, the request cap and the request prune

`SELECT_REQUESTS_OF`, `SELECT_LIVE_REQUESTS_OF`, `COUNT_REQUESTS_FROM`, `SELECT_OLDEST_TERMINAL_FROM` and the chain reads all filter `kind = 'request'`, so `_make_room` never selects a note. The `reply`/`cancel` path uses `as_request` before it reads state. The pause marker resolver (`src/amoeba/operations/pause_held.py:59-62`) checks `kind is MessageKind.REQUEST`, so a note id cannot become a held question. The schema CHECK at `src/amoeba/store/schema/006_messages.sql:34-41` ties `kind`, `state`, `expires_at` and recipient shape together.

### [CONCERN] Notes have no count bound, and one `inbox` call returns all of them

`SELECT_RECEIVED_NOTES` has no `LIMIT`, and `_read` in `src/amoeba/operations/inbox.py:85` materialises every note the member holds. Requests are capped by `MAX_REQUESTS_PER_SENDER` through `_make_room`, but `write_note` in `src/amoeba/operations/send_note.py` has no count check. A program note writes one delivery per other member. Each body can be up to `MAX_BODY_LENGTH` (4000) characters. The contract (`docs/cli-contract.md:734-735`) bounds notes by age only. That is a named exit, so the rule is met on paper. But a member can send unlimited notes inside the window, and an agent's `inbox` returns all of them at once. This is a design decision for the Project Manager: add a per-sender or per-recipient cap with a stated exit, or write down why age alone is enough.

### [CONCERN] The send rules are duplicated across the request and note paths

The "`to`, else `to_program`" recipient rule is written twice: once in `reject_send` at `send_write.py:200` and again as `declared_recipient` in `src/amoeba/operations/message_document.py:23` for the raw-document path. The D3 resend check is also reimplemented: `_resend` exists at `send_write.py:134` and at `src/amoeba/operations/send_note.py:95`. `_sent` builds a `SendResult` in both files (`send_write.py:176`, `send_note.py:130`). CLAUDE.md forbids duplicated logic. The recipient rule belongs on `SendRequest` as one property that both paths call. The resend comparison can share one helper.

### [NOTE] `sweep_due` now scans `messages` on every read-then-write path without an index

The new `OR EXISTS (SELECT 1 FROM messages WHERE kind = 'note' AND created_at < ?)` runs whenever nothing is due. The `messages` indexes in `006_messages.sql:45-48` cover `(to_member, state)`, `(from_member, state)`, `(parent_id)` and `(state, expires_at)`. None covers `kind` or `created_at`. I did not measure this. Run `EXPLAIN QUERY PLAN` and, if it scans, add a partial index on `created_at WHERE kind = 'note'` in a new migration.

### [NOTE] The note sweep lives in two places

D6 says every write that adds a note also sweeps. `send` does this inside its own transaction (`write_note` in `send_note.py`). `report_release` does it only in `place_release`, in the wiring layer. The operation itself (`src/amoeba/operations/report_release.py`) does not sweep, so any direct caller of the operation skips it. The test docstring says this is deliberate, but the two write paths now enforce the same rule differently. Consider calling `sweep_messages` from inside `report_release` before its write transaction, which would make the rule hold wherever the operation is called.

### [NOTE] One held-sweep condition is logged twice

`sweep_messages` already logs the busy condition with `logger.exception` (`src/amoeba/operations/message_sweep.py:42`) and returns the problem text. `place_release` then logs the same text again at ERROR. Keep one log. The `report-release` output does not show the held sweep to the caller at all. That matches the design, but say so in the command's docs.

### [NOTE] Cut-text pointer is shown for inbox only

`render_inbox` adds "A note cut with … is whole in:" and `amoeba inbox -j`. `render_send` shows the same note block with no pointer, so a sender's long body is cut without a way to see the whole text. Also, `_note_was_cut` only checks subject and body, so a cut note id on the first line is not flagged. Requests have the same pre-existing gap on their id lines, so this is a pattern to settle once for both.

### [NOTE] Guards removed from `reply` and `cancel` rely on the schema

The `if state is None: raise ValueError` guards are gone from `reply._problem` and `cancel._problem`. The schema CHECK makes a `kind = 'request'` row with NULL state impossible, and `as_request` keeps notes out, so the removal is safe for stored rows. `src/amoeba/store/message_transitions.py:52-53` still keeps an explicit guard for the same invariant. Pick one style.

### [NOTE] Naming collisions and stale test comments

`tests/store/message_support.py:68` defines a raw-SQL `insert_note` helper. `store/notes.py` defines a production `insert_note` with the same name and different semantics. `tests/store/test_message_sweep.py` imports both and aliases one as `write_note`, which is also the name of `send_note.write_note`. Also: the comment at `tests/load/test_messages_load.py` says "the program holds one more member", which is wrong; the program holds the sender and five others. `range(NOTE_RECIPIENTS - 2)` hard-codes `RECIPIENT` and `THIRD`. `tests/live/notes/consumer.py` asserts `returncode == 0` where `EXIT_OK` exists.

### [NOTE] Type escapes in new code

`as_request` returns `Message | str`, and callers tell the two apart with `isinstance(found, str)`. The same files use dataclass results (`SendProblem`, `Refusal`) for this. The new test helpers also use `# type: ignore[arg-type]` on `real(*args)` (`tests/store/test_notes.py`) and `real_insert_note(*arguments)` (`tests/operations/test_report_release_notes.py`) under a strict pyright configuration. Type the wrappers instead.

### Run Digest

- Response length: 10437 chars
- Response is newline-free: no
- Tool calls made: 25
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 26
- Tokens — prompt / cached / cache write / completion / reasoning: 2690124 / 2331853 / 358247 / 66789 / not computed
- Duration: 323.7 s
- Cost: $0.65 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10

### Raw Response

I'll confirm the working directory and the changed-file list first, then read the source behind any finding.
Bash is disabled in this session, so I can't run `git diff` or the test suite. I'll review by reading the working-tree files behind the diff and say so in the report. First, the store queries that a note row could leak into.
The rules text you just sent matches the Python rules already in my review instructions, so I'll apply it as written. The store queries are clean: `requests_of`, `request_counts_from`, `SELECT_OLDEST_TERMINAL_FROM` and the live-request reads all filter `kind = 'request'`, so notes don't count toward the request cap or get pruned by `_make_room`. Next I'll check the sweep wrapper, the release visibility rule and the render helpers.
The sweep wrapper, release visibility and the report write order check out. One render detail needs a look: the cut-pointer in `render_inbox` only checks subject and body, not the first line that carries the note id. Next I'll check the id limit, the command-name attribute, the message kind enum and the send path.
The id limit is 64 characters, so a note's first render line (id, sender, program, age) can exceed the 100-column width. The pointer only covers subject and body. I'll check how requests render their id lines, confirm `cli_name` is a property, and look at the dispatch edit.
Two confirmed points: `cli_name` is a property, and request id lines already use the same `prose_line` cut without a pointer, so the note id-line behaviour matches existing request rendering. Next I'll pin the exact lines of the removed `state is None` guards and check the schema for a `kind` check and indexes on the sweep path.
The schema enforces the request/note split in SQL, which changes how serious the removed guards are. I need to check two more things: the constraint text itself, and how the pause and release-waiting readers handle a note id now that a `None` state is reachable through them.
The schema CHECK makes a request without a state, or a note with one, impossible, so the removed `state is None` guards in `reply` and `cancel` are unreachable for stored rows. I'm downgrading that to a NOTE. The more important question is whether a note id can reach the held-question readers in `pause_held.py` and `request_release.py`. Those readers raise `StoreRowError` on a note, so the marker resolution that feeds them has to reject notes first.
Marker resolution in `pause_held.py:59-62` filters on `kind is REQUEST`, so a note can't become a held question. The `StoreRowError` branches are only reachable through that guarded path. Next I'll check the test-side `insert_note` name collision and whether the contract docs say anything about a note cap.
The test helper `insert_note` in `tests/store/message_support.py:68` collides by name with the new production `insert_note`, which is why `test_message_sweep.py` aliases it as `write_note`. The docs say notes leave only by age, with no count cap. I'll read that doc passage and check the string the contract test asserts on.
I have enough to write the review. Before I cite line numbers for the duplicated recipient rule and the two resend paths, I'll confirm those lines in the working tree.
## Summary

**Verdict: CONCERNS**

I reviewed the 243 changes by reading the working-tree files, not by running them. Bash is disabled in this session, so I could not run `git diff`, `ruff`, `pyright` or `pytest`. I assumed the working tree is on `243-slice.notes-and-release-notes` because every file I read matches the diff hunks. The test-suite results are unverified.

The core isolation holds: note rows stay out of request reads, the request cap and the prune. I found no correctness bugs. The two CONCERNS are a missing count bound on notes and a duplicated send rule. The rest are NOTEs.

## Findings

### [PASS] Notes stay out of request reads, the request cap and the request prune
category: correctness
location: src/amoeba/store/sql_messages.py:109-112

`SELECT_REQUESTS_OF`, `SELECT_LIVE_REQUESTS_OF`, `COUNT_REQUESTS_FROM`, `SELECT_OLDEST_TERMINAL_FROM` and the chain reads all filter `kind = 'request'`, so `_make_room` never selects a note. The `reply`/`cancel` path uses `as_request` before it reads state. The pause marker resolver (`src/amoeba/operations/pause_held.py:59-62`) checks `kind is MessageKind.REQUEST`, so a note id cannot become a held question. The schema CHECK at `src/amoeba/store/schema/006_messages.sql:34-41` ties `kind`, `state`, `expires_at` and recipient shape together.

### [CONCERN] Notes have no count bound, and one `inbox` call returns all of them
category: performance-resource
location: src/amoeba/store/sql_messages.py:69-75

`SELECT_RECEIVED_NOTES` has no `LIMIT`, and `_read` in `src/amoeba/operations/inbox.py:85` materialises every note the member holds. Requests are capped by `MAX_REQUESTS_PER_SENDER` through `_make_room`, but `write_note` in `src/amoeba/operations/send_note.py` has no count check. A program note writes one delivery per other member. Each body can be up to `MAX_BODY_LENGTH` (4000) characters. The contract (`docs/cli-contract.md:734-735`) bounds notes by age only. That is a named exit, so the rule is met on paper. But a member can send unlimited notes inside the window, and an agent's `inbox` returns all of them at once. This is a design decision for the Project Manager: add a per-sender or per-recipient cap with a stated exit, or write down why age alone is enough.

### [CONCERN] The send rules are duplicated across the request and note paths
category: architectural-decay
location: src/amoeba/operations/send_write.py:200

The "`to`, else `to_program`" recipient rule is written twice: once in `reject_send` at `send_write.py:200` and again as `declared_recipient` in `src/amoeba/operations/message_document.py:23` for the raw-document path. The D3 resend check is also reimplemented: `_resend` exists at `send_write.py:134` and at `src/amoeba/operations/send_note.py:95`. `_sent` builds a `SendResult` in both files (`send_write.py:176`, `send_note.py:130`). CLAUDE.md forbids duplicated logic. The recipient rule belongs on `SendRequest` as one property that both paths call. The resend comparison can share one helper.

### [NOTE] `sweep_due` now scans `messages` on every read-then-write path without an index
category: performance-resource
location: src/amoeba/store/sql_messages.py:190-196

The new `OR EXISTS (SELECT 1 FROM messages WHERE kind = 'note' AND created_at < ?)` runs whenever nothing is due. The `messages` indexes in `006_messages.sql:45-48` cover `(to_member, state)`, `(from_member, state)`, `(parent_id)` and `(state, expires_at)`. None covers `kind` or `created_at`. I did not measure this. Run `EXPLAIN QUERY PLAN` and, if it scans, add a partial index on `created_at WHERE kind = 'note'` in a new migration.

### [NOTE] The note sweep lives in two places
category: architectural-decay
location: src/amoeba/wiring_releases.py#place_release

D6 says every write that adds a note also sweeps. `send` does this inside its own transaction (`write_note` in `send_note.py`). `report_release` does it only in `place_release`, in the wiring layer. The operation itself (`src/amoeba/operations/report_release.py`) does not sweep, so any direct caller of the operation skips it. The test docstring says this is deliberate, but the two write paths now enforce the same rule differently. Consider calling `sweep_messages` from inside `report_release` before its write transaction, which would make the rule hold wherever the operation is called.

### [NOTE] One held-sweep condition is logged twice
category: error-handling-observability
location: src/amoeba/wiring_releases.py#place_release

`sweep_messages` already logs the busy condition with `logger.exception` (`src/amoeba/operations/message_sweep.py:42`) and returns the problem text. `place_release` then logs the same text again at ERROR. Keep one log. The `report-release` output does not show the held sweep to the caller at all. That matches the design, but say so in the command's docs.

### [NOTE] Cut-text pointer is shown for inbox only
category: consistency-rot
location: src/amoeba/cli/render/messages.py#render_send

`render_inbox` adds "A note cut with … is whole in:" and `amoeba inbox -j`. `render_send` shows the same note block with no pointer, so a sender's long body is cut without a way to see the whole text. Also, `_note_was_cut` only checks subject and body, so a cut note id on the first line is not flagged. Requests have the same pre-existing gap on their id lines, so this is a pattern to settle once for both.

### [NOTE] Guards removed from `reply` and `cancel` rely on the schema
category: error-handling-observability
location: src/amoeba/operations/reply.py#_problem

The `if state is None: raise ValueError` guards are gone from `reply._problem` and `cancel._problem`. The schema CHECK makes a `kind = 'request'` row with NULL state impossible, and `as_request` keeps notes out, so the removal is safe for stored rows. `src/amoeba/store/message_transitions.py:52-53` still keeps an explicit guard for the same invariant. Pick one style.

### [NOTE] Naming collisions and stale test comments
category: consistency-rot
location: tests/store/message_support.py:68

`tests/store/message_support.py:68` defines a raw-SQL `insert_note` helper. `store/notes.py` defines a production `insert_note` with the same name and different semantics. `tests/store/test_message_sweep.py` imports both and aliases one as `write_note`, which is also the name of `send_note.write_note`. Also: the comment at `tests/load/test_messages_load.py` says "the program holds one more member", which is wrong; the program holds the sender and five others. `range(NOTE_RECIPIENTS - 2)` hard-codes `RECIPIENT` and `THIRD`. `tests/live/notes/consumer.py` asserts `returncode == 0` where `EXIT_OK` exists.

### [NOTE] Type escapes in new code
category: type-contract-debt
location: src/amoeba/operations/reject_codes.py#as_request

`as_request` returns `Message | str`, and callers tell the two apart with `isinstance(found, str)`. The same files use dataclass results (`SendProblem`, `Refusal`) for this. The new test helpers also use `# type: ignore[arg-type]` on `real(*args)` (`tests/store/test_notes.py`) and `real_insert_note(*arguments)` (`tests/operations/test_report_release_notes.py`) under a strict pyright configuration. Type the wrappers instead.
