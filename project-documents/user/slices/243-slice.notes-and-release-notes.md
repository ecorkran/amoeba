---
docType: slice-design
slice: notes-and-release-notes
project: amoeba
parent: user/architecture/240-slices.agent-messaging.md
dependencies:
- 222
- 227
- 240
- 241
- 242
interfaces: []
dateCreated: 20261115
dateUpdated: 20261117
status: complete
turns: 17
promptTokens: 1215286
cachedTokens: 1087634
cacheWriteTokens: 127626
completionTokens: 38398
durationSeconds: 311.5
costUsd: 1.003633
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 1.0036329000000002
    completionTokens: 38398
---

# Slice Design: Notes and Release Notes

## Overview

A note is a message that tells and asks for nothing. This slice adds the `note` kind to `send`, to one member or to a whole program, and makes `report_release` write a note to each consumer that can see the report, in the same transaction as the report. After it, a repo hears about an upstream release and about program-wide news in the same `inbox` as its requests. The schema already has the `note` kind and `to_program` (240 D1), so there is no migration, no config key and no new reject code.

## Value

User value. A consumer repo learns of a provider's release at its next `inbox` check, without having to remember to run `changes`, and the PM or any agent can post news to every repo in a program with one command. `changes` stays the design-time catch-up call, and the two always agree on which reports exist. Architecturally it exercises the part of 240's schema no earlier slice writes, so notes need no later rebuild.

## Technical Scope

**Included**
- `send` with `kind` `note`: to one member (`to`) or to a program (`to_program`), one delivery per active member of the program, the sender excluded.
- Retention: the sweep's prune step deletes notes past `prune_after_days` with their deliveries, `sweep_messages`' due check counts aged notes, and `report-release` runs `sweep_messages` before its write, so every write that adds a note also sweeps.
- `inbox` returns the notes a member has a delivery for (`notes`).
- `reply`, `cancel` and `send --parent` refuse a note's id.
- `report_release` writes a release note per consumer, in its own transaction, for the four outcomes that write: `recorded`, `versioned`, `corrected` and `withdrawn`.
- Rules text: the Handling block says notes are information and need no reply.
- Docs: `cli-contract.md`, `mcp-server.md`, `store-contract.md`, `program-rules.md`, and the MCP `INSTRUCTIONS` text.

**Excluded**
- A migration, a config key, a reject code, or any change to `changes` (it stays as 227 left it).
- State for notes: no read marker, reply, recall or cancel. Notes are pruned by age.
- Showing notes in `list` and `status`. They have no state to show. A rejected note `send` appears there under the sender's rejected calls, as any rejected `send` does (240 D9).
- Push (241 sends the channel event for a note with no change) and waking (244 wakes for requests only).

## Dependencies

### Prerequisites
- 240 complete: `messages`, `deliveries`, `message_rejections`, `send`, `inbox`, `reply`, `cancel`, the sweep, `effective_state`, `get_message`, the delivery writer, the notice, the text-limit constants and the doors' wiring.
- 227's `report_release`, `releases` and `visible_releases`; 222's `dependency_pairs`.
- 241's push check, for one test (the push criterion below). The test is required. The plan's order builds 241 before 243, so it is always present, and no other part of this slice reads 241's code.
- 242's request resolution, for one test (D4's last row: a question naming a note's id is unresolved). The plan's order builds 242 before 243, and no other part of this slice reads 242's code. The frontmatter lists every slice named here, and plan entry 4's Dependencies line is amended to match (see Amendments).

### Interfaces Required
- 240's `Message`, `Delivery` rows and the delivery writer `send` uses. Where this document names a 240 module by role, the task breakdown checks the built name.
- `store.write()` (`BEGIN IMMEDIATE`, rolls back when its block raises) and `visible_releases(transaction, provider_id, consumed, since)`.
- `programs.get_program`, `programs.members_of`, and `sql.ACTIVE_MEMBER`.

## Architecture

### Component Structure

```
send ──kind=request──▶ 240's request path
     └─kind=note────▶ operations/send_note.py ──▶ store/notes.py ──▶ messages, deliveries

report_release ─ one store.write() ─▶ releases (227)
                                   └▶ operations/release_notes.py ──▶ store/notes.py
```

- `operations/message_models.py` (240): `SendRequest` gains `kind` and `to_program`, with the cross-field rules of D1. `SendResult` gains `note` (null for a request). `InboxResult` gains `notes`. New `NoteView`.
- `operations/send_note.py`: the note path of `send`. `send.py` validates, resolves the caller and the direct recipient as today, then calls it for a note, so `send.py` stays under its size limit.
- `operations/release_notes.py`: `release_note_recipients`, `compose_release_note` and `write_release_notes`, the note template and the id prefix constant. `report_release.py` calls it and nothing else changes in how the report is decided.
- `store/notes.py`: `insert_note` (one message row, then one delivery per recipient through 240's delivery writer), `received_notes` (the read for `inbox`), `prune_notes`. Its SQL goes in `store/sql_messages.py`. `programs.pairs_provided_by(transaction, provider_id)` is the one new pair read, with `SELECT_PAIRS_PROVIDED_BY` beside its siblings in `sql.py`, reusing `_PAIR_ENDS_ACTIVE`.
- `NoteView` is built from the store's `Message` dataclass as `RequestView` is.

### Data Flow

**Note to a member or program.** `send` resolves the sender and, for a direct note, the recipient through `cf`, before any store lock (240 D3). One write transaction: sweep, resolve the program's recipients, check the id against an existing row, insert the note, write the deliveries. A rejection after the sender is resolved is recorded (240 D9) and returned.

**Release report.** `report_release` resolves the member through `cf` before any lock, as today. Its door wiring first runs `sweep_messages` (D6), in its own transactions, before the report's. Then one write transaction: the report write, the recipients (D5), and one note and delivery per recipient. For `withdrawn` the recipients are found before the delete. If any step raises, the transaction rolls back and the report is not stored.

**Write lock.** The architecture keeps writes short and never holds the write lock across an outside call. Both transactions above keep to it. They make no `cf` call, no process start and no wait inside the lock: the note text is composed in process and the ids come from `uuid4`. Their length is the existing work plus one insert per recipient (a program's member count for a program note, a provider's consumer count for a release), and the waits are the store's `BUSY_TIMEOUT_SECONDS` each for the legacy-move lock, the open and the transaction, as 240 counts them. The inserts run inside the transaction already held, so they add local work and no wait. A program note adds no lookup, so 240's worst-case bound for `send` still holds, and `report_release`'s own transaction gains no lookup and no wait. The `sweep_messages` call before it (D6) adds what it adds to `list` and `status` in 240: one read, and one short write only when something is due, each with the store's wait, never holding a lock across the report's transaction.

**Reading.** `inbox` reads the member's notes through its deliveries. Nothing is marked.

### State Management

The slice adds no table and no column. A note is a `messages` row with `kind` `note`, null `state` and null `expires_at`, plus its deliveries. A note's `state_changed_at` is set equal to `created_at`, and its `depth` is 1 (the column's minimum; a note has no chain). Its only exit is the prune.

## Technical Decisions

### D1 — `send` takes a note
Status: decided

`SendRequest` gains two fields:
- `kind`: `request` or `note`, a `MessageKind` (240 D1's enum). Absent means `request`, which is `send`'s behavior in 240, as `mode` absent means `report` in `report_release`.
- `to_program`: a program id.

| `kind` | Required | Not allowed |
|---|---|---|
| `request` | `to`, `subject`, `body`, `id` | `to_program` |
| `note` | `subject`, `body`, `id`, and exactly one of `to` and `to_program` | `parent` |

A violation is `malformed`, naming the field and the kind, with 240's text limits (`id` 64, `subject` 200, `body` 4000; over-limit rejected, never cut). CLI: `amoeba send --note --to-program ID ...` and `amoeba send --note --to MEMBER ...`. `--note` is a flag, absent when not given, so the document carries no `kind` and means a request. `--to` is no longer required by argparse, so the operation rejects a missing recipient with the same detail on both doors, as `report-release` does for its flags. MCP `send` gains `kind` and `to_program`.

- A note takes no `parent`: chains are request chains with a depth, and a note has no state to wait on.
- Rejected: a separate `send_note` operation (a fifth operation and tool with the same arguments, for a difference of one field); inferring a note from `to_program` alone (a program note sent by a typo in flags would then change meaning silently).

### D2 — A program's recipients
Status: decided

`to_program` is read as a program id, looked up in Amoeba's own store with `get_program`, so no `cf` call is added. Inside the write transaction:
- Recipients are the program's active members (`members_of`, which applies `sql.ACTIVE_MEMBER`) except the sender.
- An unknown program, or no recipients (the sender is the only member), is rejected `unknown_recipient`, with a detail that says which. A note nobody can read would only wait to be pruned, and "sent" would be false.
- The recipients are fixed at `send`. A member added later does not get the note.

The message row has `to_program` set and `to_member` null (240 D1's check). Each recipient gets one delivery, event `sent`, each with the next `seq`. A direct note has `to_member` set and one delivery. A note to a removed or unknown member is `unknown_recipient`, as for a request. A direct note to the sender's own member is not special-cased: it is delivered, as a request to oneself would be in 240.

### D3 — Note ids and resend
Status: decided

The sender passes `id` as for a request (240 D2, same grammar). A second `send` with an existing id compares `(kind, from_member, to_member, to_program, parent_id, subject, body)`:
- Equal: outcome `unchanged`, the stored note returned, no delivery written. A note has no state, so there is no `request_ended` case for it.
- Different, including a different kind: rejected `id_reused`, whoever sent it.

An id pruned and sent again is a new note, as for requests.

### D4 — Where a note row meets 240's code
Status: decided

240 wrote only requests. Every 240 read or write that can see a `messages` row now has to handle a note. The audit is a task; the expected behavior is:

| 240 code | Behavior with a note |
|---|---|
| `reply` and `cancel`, through `get_message` | A note's id is rejected `unknown_request`, with a detail saying the id is a note and notes take no reply. |
| `send`'s `parent` lookup | A note's id is rejected `parent_unknown`, with a detail saying it is a note, so a note is never read as a request. |
| `inbox` request reads | Select `kind = 'request'`, so notes never appear in `requests`. |
| `inbox` note reads (new) | Notes the member has a delivery for, in `notes`, found through its deliveries. Without `since`, every such note inside retention, oldest delivery first. With `since`, the notes whose delivery to this member has `seq > since`, in delivery order. A note has one delivery per recipient and no later state change, so each appears once, and `deliveries` lists its `sent` delivery beside it. `as_of_seq` and the `beyond_last_record` check are 240's, unchanged. A program note's sender has no delivery, so it does not see its own note. A direct note to one's own member is delivered, so it shows. |
| The sweep's expire step | Touches `state = 'open'` only, so a note (null state) is never expired. |
| The sweep's prune step | Gains the note statement (D6). The request statement keys on terminal states and leaves notes alone. |
| `cancel_member_requests` (`rm`) | Cancels non-terminal requests only. A note is not touched, and its deliveries to a removed member stay until pruned. |
| `list` and `status` request lines | Count `open` and `accepted` requests only. Notes never show. |
| 242's request resolution | Already counts a `request` row only. A question naming a note id is unresolved. |

Each row is a test, with a note row in the fixture next to requests, so a 240 query that forgets the kind fails here.

### D5 — Release notes
Status: decided

`report_release` writes notes for every outcome that changes what `changes` shows: `recorded`, `versioned`, `corrected` and `withdrawn`, which are the outcome values 227 already names, so a note's event has one name everywhere. `unchanged` and a rejection write none.

**Who gets one.** A consumer gets a note exactly when the report is visible to it in `changes`, at the moment of the event. That rule is `visible_releases`, called, not copied (project rule: one definition). For `recorded`, `versioned` and `corrected`, `release_note_recipients` takes the member's active pairs (`pairs_provided_by`) and, for each `consumed` value in use, calls `visible_releases(transaction, provider, consumed, since=now)`. A consumer gets a note when the written report's `seq` is in the result.

- **The boundary.** `now` is the one value `report_release` takes from `deps.clock()` and writes as `reported_at` and `versioned_at`. Both visibility queries compare with `>=` on their own time column, so `since=now` includes a report whose time this event set to `now`, and excludes one whose time stayed earlier. A report written at `now` is in, a report whose time did not move is out. Another report written at the same instant does not matter, because the check looks for this report's `seq`.
- **The assumption.** The rule needs each event on one report to have a later `now` than the one before, so that a time an event did not move is earlier than `now`. Events on one report are separate calls, serialized by `BEGIN IMMEDIATE`, so a real clock advances between them. If it did not (a stopped or stepped-back clock), an unmoved time would equal `now` and the consumer would get one extra note, never a missing one. Tests therefore use a clock that advances between events, and the matrix test (Success Criteria) uses each event's own `now` as its `changes` oracle's `since`, the same value the rule uses. A fixed clock is fine for a test that makes one event per report.

With 227's visibility rules that gives:

| Outcome | `from_source` consumer | `from_release` consumer |
|---|---|---|
| `recorded`, no version | note | none |
| `recorded`, with a version | note | note |
| `versioned` (a version added or changed) | none (`reported_at` did not move) | note |
| `corrected`, the report has a version after the write | note | note |
| `corrected`, the report has none after the write | note | none |

For `withdrawn`, the report must still exist to be read, so recipients are found before the delete, with `since` set to the report's own `reported_at`: the consumers that could see the report at all. This is inclusive in the same way. How 227 sets the two times decides who is included: a first report sets `reported_at`, and sets `versioned_at` equal to it only when a version is given; versioning sets `versioned_at` to `now`; a correction sets `reported_at` to `now`, and sets `versioned_at` to `now` when the report has a version after the write and to null when it has none. So `versioned_at`, when set, is never before `reported_at`, a `from_release` consumer is included exactly when the report has a version, and a `from_source` consumer always is. A `from_release` consumer of a report that was never versioned gets none, because it never saw the report. The plan's "the same consumers" is read this way, so it holds for every row above.
- A consumer whose pair was added after the report was made was never sent the original, but it sees the report in `changes` (a `from_source` consumer sees any report from its `since` on), so it gets the correction or withdrawal note. The rule is "notes follow `changes`", and that is its result.

- Pairs whose ends are not both active are not returned (`_PAIR_ENDS_ACTIVE`), so a removed member gets nothing.
- A consumer's mode changing later (`add --depends-on` again) sends nothing retroactively.
- A provider with no consumers writes its report and no notes.

**What the note holds.** One `messages` row per consumer: `kind` `note`, `from_member` the provider, `to_member` the consumer, `subject` and `body` composed by Amoeba from the outcome and the stored report.
- `subject`: `Release report <outcome>: <version, or the commit when there is none>`.
- `body` for `recorded`, `versioned` and `corrected`: a first line naming the outcome (the provider is the note's `from_member`), then `Commit`, `Version` (or `none`), `Changed`, and `Touched` (items joined with `; `). A corrected note says it replaces the earlier text. The closing line says `changes` holds the full record.
- `body` for `withdrawn`: the commit and version, and that the report was withdrawn and is to be disregarded. It carries no `changed` text.
- **Limit.** The `body` limit of `send` binds text a caller supplies. A release note's body is composed by Amoeba from a report that `report_release` already bounds, through the constants in `report_release_models.py` (`MAX_CHANGED_LENGTH`, `MAX_TOUCHED_ITEMS`, `MAX_TOUCHED_ITEM_LENGTH`, `MAX_VERSION_LENGTH`, `FULL_HASH_LENGTHS`). It has its own constant, `MAX_RELEASE_NOTE_BODY_LENGTH`, defined once in `release_notes.py` as the sum of those bounds (the touched items with their separators) and the template's own fixed text. A test composes the largest possible report, every field at its limit, for each outcome and checks the body is within the constant, so a change to a report constant or to the template that breaks the bound fails a test. The body is never cut, and nothing is rejected: the report's own limits already did that. `cli-contract.md` states the constant's value and what it is derived from, beside the `send` limits. The subject is within `send`'s subject limit, because its variable part is a version (`MAX_VERSION_LENGTH`) or a commit (`FULL_HASH_LENGTHS`); the same test checks it.
- **Id.** `release:` followed by `uuid4().hex`, one per row. A colon cannot appear in a sender's id (240 D2's grammar), so a release note's id can never collide with an agent's, and `release:` is the one prefix constant the tests use to find release notes. Nothing parses it, and nothing reads the id to decide behavior.
- **Delivery event.** `sent`, as for any note. A correction or withdrawal is a new note, not a state change of the earlier one.

**Atomicity.** The notes are written inside `report_release`'s `store.write()` block, after the report write. A raise from a note write rolls the report back, so a consumer can never see a note for a report that is not stored, and a report is never stored without its notes. A retry of the same call then runs as a first call. `ReportReleaseResult` is unchanged.

- Rejected: one note to a program (the visible set is a subset of the program's members, and `to_program` means all of them); a note at a fixed event only, such as at merge (it would disagree with `changes` for a `from_release` consumer); a link column from note to report (a migration, for a read nothing makes); a `notified` field on the result (nothing in the plan reads it, and `inbox` shows the notes).

### D6 — Retention
Status: decided

The sweep's prune step (240 D6) gains one statement: delete notes whose `created_at` is older than `prune_after_days`, deleting their `deliveries` first (the foreign key), in the same transaction, after the request statements. Read notes are pruned the same as unread: there is no read state.

A sender also holds at most `MAX_NOTES_PER_SENDER` notes (200, as `MAX_REQUESTS_PER_SENDER` is for requests). `send` and `report_release` call one helper just before each note insert; it deletes all but the sender's newest `MAX - 1` notes, deliveries first, so one more fits. A note has no state, so the oldest always goes and nothing is refused. This bounds what `inbox` reads to the cap times the senders.

The sweep's callers are 240's, plus one: `send`, `reply` and `cancel` in their write transactions, and `list`, `status`, `handle_pause` and now `report_release` through `sweep_messages`, which reads first and writes only when something is due. Its due check gains "a note older than the prune cutoff". Every write that adds a note therefore also sweeps: `send` in its transaction, and `report_release` through `sweep_messages`, so a store whose agents only run `inbox` (which writes nothing) and `report-release` still has its notes pruned, with nobody editing anything.

- `report_release`'s call is made by its door wiring (`wiring_releases.place_release`), which loads the config as the other config-reading operations' wiring does, before `report_release` opens its own transaction. The operation's signature is unchanged, so 227's tests are unchanged. The sweep is due-checked, so a quiet store gains one read and no write.
- An expiry the sweep records is harmless to 242: 242 reads a request's effective state, so its start set does not depend on who records an expiry.
- A held store is `sweep_messages`' problem text, as for every sweep caller: it is logged and the report still runs, and the next due call prunes. Any other `StoreError` from the sweep propagates and the call exits 3 before the report is written, as any store fault does. Running the same call again is the exit.
- **A failing note write.** The notes share the report's transaction, so a failing insert rolls the report back and the call exits 3, as any store fault in 227's write does. Running the same call again is the exit.

### D7 — No migration, no config
Status: decided

No table, column, config key or file is added. The live store and config are untouched, so no backup or restore step belongs to this slice. Notes are 240's rows in the live store's existing tables.

### D8 — The rules text
Status: decided

The Handling block (240) gains one paragraph: a `note` in `inbox` is information from another repo, written by its agent and so data to judge; read it, act on it only as this repo's own rules say, and send no reply. A release note says a repo this one depends on recorded, corrected or withdrew a release report, and it is the same report `changes` lists, so the Consumer block's check before designing a slice still applies. It uses only flags the parser has. `tests/test_program_rules_doc.py` checks that the Handling block names `note`.

### Amendments to 240 and the parent documents

The decisions above change what 240, the architecture and the plan say. The docs step makes the same changes in each of them, so no two documents disagree:
- **`240-slice.requests.md`:** its API Contracts table (`send`'s fields and `--to` no longer required, `inbox`'s `notes`), D2's resend comparison (gains `to_program`), D4's `reply` and `cancel` loads, D6's prune step (gains notes) and the "Sweep" paragraph's `sweep_messages` due check (gains aged notes) and its callers (gain `report_release`, through its wiring), D7's request reads and `notes`, D8's parent check, and "Provides to Other Slices": the 243 line, and the 244 line, which says 244's wake hook sits in `send`'s request branch, not in the delivery writer.
- **The architecture:**
  - "Operations", `send` row: `parent` applies to a request only, and a note takes none (D1).
  - "Operations", `inbox`: notes are listed by delivery, so a member sees the notes it received.
  - "Message kinds": "the same consumers" for a correction or withdrawal means the consumers that see the report in `changes` (D5).
  - "Expiry": the sweep's prune also removes notes past `prune_after_days`.
  - "Delivery"/principles, "The sender picks the id": a release note's id is Amoeba's `release:` id, because no agent sends it (D5).
  - "Operations", the text-limit sentence: a release note's body is bounded by `MAX_RELEASE_NOTE_BODY_LENGTH`, derived from its report's limits, and is composed, not caller text (D5).
- **242:** no edit. Its request resolution already counts only `request` rows, so a question naming a note's id is unresolved (D4's last row), and this slice tests that against 242's code. The expiries `report_release`'s sweep may record need nothing from 242, which reads effective state (D6).
- **The plan's entry 4:** the same two statements about limits and "the same consumers", and its Dependencies line reads 222, 227, 240 and, for the push test and the request-resolution test, 241 and 242.
- **244:** no change. Its design already places the wake hook in `send`'s request branch after the request's transaction commits, so the note path (`send_note.py`) never reaches it, and it has the test (a note to a member with a wake command starts nothing).
- **Contract docs:** `cli-contract.md`, `mcp-server.md` and `store-contract.md` follow the code as in 240. `store-contract.md` gains that notes are written by `send` and `report_release`, a release note's id has the `release:` prefix and a sender's cannot, a note has null `state` and `expires_at` and `state_changed_at` equal to `created_at`, and notes are pruned by `created_at`. The tool descriptions for `send` and `inbox` say a note needs no reply and carry no example values, and the `INSTRUCTIONS` text gains one sentence on notes.

## Implementation Details

### API Contracts

`NoteView`: `id`, `from_member`, `to_member` (null for a program note), `to_program` (null for a direct note), `subject`, `body`, `created_at`. Members are ids; no message operation looks up names (240 D7). `SendResult` and `InboxResult` carry the notice (240 D11). `ReportReleaseResult` is unchanged and holds no text of other agents. Exit codes are as in 240.

## Integration Points

### Provides to Other Slices
- 241: nothing to change. A note is a delivery, so the watcher's read sees it. The push criterion is tested through 241's own push check (see Success Criteria).
- 244: a requirement, not code, which 244's design already meets. Waking is for requests only, so 244's hook is in `send`'s request branch and never in the delivery writer that notes also use.

### Consumes from Other Slices
- 240's tables, `send`, `inbox`, sweep, delivery writer, notice and limits. If one is missing, the slice does not start.
- 227's `report_release` and `visible_releases`, whose visibility rules the notes follow by calling them.
- 241's push check, for the push test.

## Success Criteria

### Functional Requirements
- A note to a program reaches every active member except the sender, each as its own delivery. A member added afterwards gets nothing. A direct note reaches that member.
- Over-limit text, a note with a `parent`, a request with `to_program`, a send with both or neither of `to` and `to_program`, an unknown program, and a program with no one else in it are each rejected, and each leaves one rejection record for the sender.
- A resend of a note with the same content is `unchanged` and writes no delivery. A reused id with new content, or with another kind, is `id_reused`.
- `reply` and `cancel` of a note's id, and a `send` whose `parent` is a note's id, are rejected, each with a detail saying the id is a note.
- For every `consumed` value and every outcome in D5's table, the consumers that get a note are exactly those whose `changes` result lists the report with `since` equal to the event's `now`, and for a withdrawal, those whose `changes` lists it, before the withdrawal, with `since` equal to the report's `reported_at`. This includes a version added, a correction and a withdrawal.
- `inbox` lists the notes a member has a delivery for in `notes`, with `since` or without, none in `requests`, and none it has no delivery for. A program note's sender does not see it. A release note's body carries the report's commit, version, changed text and touched items.
- The note and the report are written in one transaction. A test makes the note write fail and finds no report and no note.
- **Push.** 241's push check, run for a member after a note arrives, reports it the same as a request: a test sends a direct note, a program note and a release note to a fixture member, runs the check, and finds a channel event whose entries name `note`, `sent` and the sender's member id, with no subject or body, in the form 241 gives a request.

### Technical Requirements
- Notes older than `prune_after_days` are pruned with their deliveries, read or not, by the sweep. Younger notes stay. Open and accepted requests are not touched by the note statement.
- `list` on a store holding only an aged note prunes it, through `sweep_messages`' due check (D6). So does a `report-release` through its door wiring.
- A release note's body, composed from the largest possible report for each outcome, is within `MAX_RELEASE_NOTE_BODY_LENGTH` (D5).
- An `rm` leaves notes alone. The sweep never expires a note.
- `list` and `status` do not show notes, and `Nothing needs you.` is unchanged by them.
- No migration: `EXPECTED_SCHEMA_VERSION` is unchanged, and the contract-docs test passes with the new fields documented.
- `tests/test_import_boundaries.py` and `tests/test_read_side_defined_once.py` still pass. `release:` is spelled once.
- `ruff format`, `ruff check`, `pyright` and the whole suite pass.

### Integration Requirements
- The MCP `send` tool takes `kind` and `to_program`, and the in-process parity tests cover both doors for a note.
- 240's request flows, scenario D included, behave as before with notes in the store.
- A live test, through real `cf` and the CLI, with a provider and two consumers of different `consumed` values: a report, a version, a correction and a withdrawal each reach the right consumers' `inbox`.

### Verification Walkthrough

Verified at the end of Phase 6 (2026-11-17): step 1 in the repo, steps 2 to 6 by hand under a throwaway home and a throwaway Context Forge data directory with real `cf` and `git` (the outputs below are from that run), and steps 3, 5 and 6 again by `uv run pytest tests/live/notes`. Never run the steps against the live store or the installed `amoeba`: the installed tool is the previous build until the release skill updates it. Retention is shown by the unit tests (`tests/store/test_message_sweep.py`, `tests/test_report_release_sweep.py`).

1. `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest`. Expected: all clean and passing.
2. Set up four scratch repos in one program, with a throwaway home and data directory, using this repo's build as `amoeba`:
   ```
   WORK=$(mktemp -d); cd "$WORK"
   export CONTEXT_FORGE_DATA_DIR="$WORK/cf-data" AMOEBA_HOME="$WORK/home"
   mkdir -p "$CONTEXT_FORGE_DATA_DIR" "$AMOEBA_HOME"
   amoeba() { /path/to/this/repo/.venv/bin/amoeba "$@"; }
   # config.yaml: the yaml block under "## Example" in docs/config-contract.md, saved as $AMOEBA_HOME/config.yaml
   for n in prov-s src-s rel-s other-s; do mkdir $n && git -C $n init -q -b main && (cd $n && git commit -q --allow-empty -m seed && cf init --lite --name $n); done
   (cd prov-s && amoeba add --program toolchain)
   (cd src-s && amoeba add --program toolchain --depends-on prov-s:from_source)
   (cd rel-s && amoeba add --program toolchain --depends-on prov-s:from_release)
   (cd other-s && amoeba add --program toolchain)
   ```
   Expected: each `add` exits 0.
3. A note to the program. In `other-s`: `amoeba send --note --to-program toolchain --id n-1 --subject "Freeze on Friday" --body "Do not merge after noon."`. Expected, exit 0: the notice line, `sent: n-1`, then the note (`n-1 · from <other-s's project id> · to program toolchain · <1m`, `subject: Freeze on Friday`, `body: Do not merge after noon.`). In `prov-s`, `src-s` and `rel-s`: `amoeba inbox` prints the notice line, a `Notes` section with that note, and `as_of_seq: 3 (pass it as --since next time)`. In `other-s`: `amoeba inbox` prints `No requests.` and the same `as_of_seq` (no note: the sender has no delivery).
4. Refusals. Each from `other-s`, with the exits shown:
   - The same command with `--body "changed body"`: `rejected: id_reused: the id 'n-1' belongs to a different message; send this one under a new id`, exit 1.
   - With `--parent n-1`: `rejected: malformed: document: Value error, parent is not allowed for kind note`, exit 1.
   - With `--to-program no-such-program --id n-2`: `rejected: unknown_recipient: unknown program 'no-such-program'; known programs: toolchain`, exit 1.
   - The first command unchanged: `unchanged: n-1`, exit 0; `amoeba inbox -j --since 0` in `src-s` still lists one delivery, `n-1` with event `sent`.
   - In `src-s`: `amoeba reply n-1 accept`: `rejected: unknown_request: 'n-1' is a note, not a request: a note takes no reply, …` (cut to the line width in text; `-j` has it whole), exit 1.
5. A release note. In `prov-s`, after `git commit --allow-empty -m feature` (call its hash `$C`): `amoeba report-release --commit "$C" --changed "adds the thing" --touched "the thing"`. Expected: `reported`. `src-s`'s `inbox -j` has one note with the subject `Release report recorded: $C` and an id starting `release:`; `rel-s`'s has none. Then the same command with `--version v-walk-1`: `reported` (outcome `versioned` in `-j`). `rel-s`'s `inbox` now has a note `Release report versioned: v-walk-1` whose body is the lines `A release report was versioned.`, `Commit: $C`, `Version: v-walk-1`, `Changed: adds the thing`, `Touched: the thing` and `` `changes` holds the full record. ``; `src-s` still has one release note.
6. Correct and withdraw. In `prov-s`: the same commit with `--correct`, `--changed "new text"` and `--touched "the thing"`: both consumers get a note, `Release report corrected: v-walk-1` (two release notes in `src-s`, two in `rel-s`). Then `amoeba report-release --commit "$C" --withdraw`: both get `Release report withdrawn: v-walk-1`, whose body begins `A release report was withdrawn and is to be disregarded; do not rely on it.` and holds the commit and version and no changed text (three release notes each).

Caveats found: a note's sender prints as the project id, not the name, because no message operation looks names up (240 D7); `report-release` now reads `config.yaml` for its sweep, so a missing config fails it with exit 3 like the other commands that read it; the text of a rejection is cut to 100 columns, `-j` has the whole detail.

## Risk Assessment

### Technical Risks
- A 240 query that selects `messages` without a kind sees a note where it expects a request. D4's audit and one test per row cover it.
- The recipient rule is calling 227's `visible_releases` at the right `since`. A wrong `since` makes the note set differ from `changes`. The matrix test (every consumed value, every outcome, compared with `changes` at the same `since` the rule uses) is the check, and its oracle is the `changes` operation, not the SQL the implementation calls.
- Note volume inside the retention window is bounded by a per-sender cap, `MAX_NOTES_PER_SENDER` (200, as for requests): a note that would pass it first drops the sender's oldest notes with their deliveries, in the writing transaction, for both `send` and `report-release`. Nothing is refused, because a note has no state to wait on. `inbox` therefore reads at most that many notes per sender.

## Implementation Notes

### Development Approach
1. `MessageKind` use in `SendRequest` (D1), `NoteView`, the result fields, and their model tests.
2. `store/notes.py`, `pairs_provided_by`, the prune statement and the due-check clause, with store tests (insert, deliveries, program recipients, prune).
3. `send_note.py` and the `send` branch, then the D4 audit with a note row in every 240 test fixture that reads messages.
4. `release_notes.py` and the `report_release` change, with the outcome table and atomicity tests, then the matrix test against `changes`.
5. CLI flags and renderer lines, MCP fields and descriptions, `INSTRUCTIONS`, the rules text, the docs, and the amendments' wording in the architecture and plan.
6. The push test (through 241's check) and the live test.

### Special Considerations
Prompt injection and self-asserted sender identity are as the architecture states them: note text reaches an agent only through `inbox`, under the notice (240 D11). Nothing here acts on note text, and a note starts no run and no wake.

## Operator Walkthrough

Done as the person running it. Set-up is nothing new: the rules text is pasted once with the other blocks, and after that no state below ends by someone editing a file.

- **Start.** Update the Handling block in each repo's rules file (an agent in each repo does it as a commit). No config change.
- **Normal path.** A provider's agent runs `report-release` after a merge or release, as before. Each consumer's agent finds the note at its next `inbox` check, reads it as information, and does what its own rules say, with no reply. The PM or an agent posts news with `send --note`.
- **A note to the wrong place.** An unknown program or a program with no one else in it is rejected with a reason, recorded, and shown under the sender in `list`.
- **A wrong manual note.** There is no recall: a note has no state and the reader may already have it. The sender sends a correcting note. It leaves by age.
- **A wrong release report.** `report-release --correct` or `--withdraw` sends consumers a new note, so they stop relying on it.
- **A report with no consumers.** The report is stored and no note is written.
- **A failing note write.** The report is rolled back and the call exits 3, and the provider's agent does what the Provider block says on a non-zero exit, as for any 227 store error. The same command is run again; until then no consumer sees the report in `changes` or `inbox`, which is the plan's atomicity rule. A store that fails every write is a store fault 227 already has, not a state this slice adds.
- **A consumer repo is removed, or its mode changes.** It gets nothing further. Its earlier notes stay until pruned.
- **Nobody reads a note.** It is pruned `prune_after_days` after it was sent, by the next sweep, which any `send`, `reply`, `cancel`, `report-release`, `list`, `status` or `handle-pause` runs. No one edits anything.
- **Undo and cleanup.** Nothing to undo beyond the correcting note. Notes leave by age. Dead ends found: one, now closed. A store whose agents only run `inbox` and `report-release` never swept, so its notes never left; `report-release` now runs the due-checked sweep (D6), so every write that adds a note also prunes.
