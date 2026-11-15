---
docType: tasks
slice: notes-and-release-notes
project: amoeba
lld: user/slices/243-slice.notes-and-release-notes.md
dependencies:
- 222-slice.store-config-and-set-up
- 227-slice.program-dependencies
- 240-slice.requests
- 241-slice.push-and-presence
- 242-slice.hold-and-release
projectState: Slices 220 to 229 are merged on main. Store schema version 5 (migrations
  001 to 005), state is in ~/.local/state/amoeba. Slice 240 (messages, deliveries,
  send, inbox, reply, cancel, the sweep, migration 006), slice 241 (push, migration
  007) and slice 242 (hold and release, migration 008) are designed and tasked; this
  slice is built after 240, 241 and 242 are built and integrated (241 for the push
  test, 242 for one D4 row test; nothing else here reads their code), and adds no
  migration.
dateCreated: 20261115
dateUpdated: 20261115
status: not_started
turns: 27
promptTokens: 1614106
cachedTokens: 1497855
cacheWriteTokens: 116217
completionTokens: 22064
durationSeconds: 160.2
costUsd: 0.835661
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.8356608999999999
    completionTokens: 22064
---

# Tasks: Notes and Release Notes

## Context Summary

- Working on slice 243 (design: `user/slices/243-slice.notes-and-release-notes.md`; decisions D1 to D8 are cited by number). Effort 2/5, as the slice plan's entry 4 gives it. It delivers the `note` kind of `send` (to a member or a program) and a release note per consumer from `report_release`, in the report's own transaction, so a repo hears of a release in its `inbox`.
- Paths: a path without a prefix is under `src/amoeba/`; `tests/`, `docs/` and `project-documents/` paths are from the repo root, and `user/` means `project-documents/user/`.
- Built names: 240 and 241 are designed but not built, so the design names 240 modules by role. Task 0.1 finds each built name and records it in a note; later tasks use the role names below and mean the built name. Roles: the message store module (`get_message`), the delivery writer (`write_delivery`), the sweep (`store/message_sweep.py`: `sweep`, `sweep_due`), `sweep_messages` (`operations/message_sweep.py`), `operations/send.py` and `send_write.py`, `operations/inbox.py`, `operations/message_models.py`, `store/sql_messages.py`, `store/models.py` `Message`, `wiring_messages.py`, `cli/registration_messages.py`, `cli/render/messages.py`, `mcp/message_tools.py`.
- A note's `depth` column is 1 (the column's minimum; a note has no chain, D1), written by `insert_note` only, as the design's State Management paragraph states.
- No migration, no config key, no new reject code, no change to `changes` (D7, Technical Scope). `EXPECTED_SCHEMA_VERSION` is unchanged.
- Closed values are defined once: `MessageKind`, `DeliveryEvent.SENT`, the `release:` id prefix, `MAX_RELEASE_NOTE_BODY_LENGTH`. No silent fallbacks; a swallowed exception names one type and carries a comment saying why. Member checks in new SQL use `sql.ACTIVE_MEMBER`. Files near ~300 lines get no new logic: `store/sql.py` (484 lines) gains only `SELECT_PAIRS_PROVIDED_BY`, new note SQL goes in `store/sql_messages.py`, `report_release.py` gains a call.
- Import direction stays `cli/mcp → wiring → operations → store`; the store imports nothing from `operations`.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. "Checks pass" means all four, with no failure beyond the baseline noted in 0.2. The live tier is `uv run pytest tests/live/<dir>` (never part of a bare run; LLM spend is pre-authorized).
- Tests use the autouse `AMOEBA_HOME` fixture, the stub `cf` (`tests/cf_stub.py`, `tests/cf_fixtures.py`), `tests/store/seed.py`, `tests/operations/release_support.py` (providers, a source consumer, a release consumer, a settable clock) and `tests/store/release_support.py`. Destructive SQL only against throwaway stores. No sample id, hash or timestamp sits near a value an agent must fetch (hallucination-trap rule), including docs that tests check. `release:` is spelled once in `src` and once in tests.
- `tests/test_contract_docs.py` requires every new field, kind and value in the contract docs, so each task that adds one adds its entry then. Task 9 writes the prose and the parent-document amendments.
- No existing test function or assertion in the 227, 240, 241 or 242 suites changes except the two assertions tasks 1.1 and 6.1 name; every other task only adds test functions, or a note row in an existing fixture (task 4.4). If an existing test fails for a legitimate reason, fix the new code, not the test.
- Commits: groups 1 to 4 commit once, at the end of group 4. `SendRequest` accepts `kind` from 1.1 on, `send` does not handle a note until 3.2, and 240's request code is not safe with a note row until 4.2, so no earlier point is a working one.
- Production state: no live store or config is written (D7); tests use throwaway stores only, so there is no backup, restore or Phase 7 hand-off step.
- Work on branch `243-slice.notes-and-release-notes` (created in 0.2). Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.

## 0. Setup

- [ ] **0.1 Target and prerequisites**
  - [ ] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty. `git checkout {target}`; the planning documents (design, this file) are committed there, with no other uncommitted change
  - [ ] Confirm each role has a built module, by the designed name or another (a role built under another name is mapped in the next item, not blocked): `store/schema/` holds `006` (messages, deliveries) to `008`; `operations/request_link.py` has `find_request_link` and `operations/pause_held.py` exists (242); `docs/program-rules.md` has the Handling block and `tests/rule_blocks.py` returns it (240 task 13.2); `store/messages.py` has `get_message` and `effective_state`; `store/deliveries.py` has the delivery writer; `store/message_sweep.py` has `sweep` and `sweep_due`; `operations/message_sweep.py` has `sweep_messages`; `operations/send.py`, `send_write.py`, `inbox.py`, `message_models.py` exist; `mcp/inbox_watcher.py` and `mcp/channel_event.py` exist (241); `store/releases.py` has `visible_releases`; `store/programs.py` has `members_of` and `get_program`. If a role has no built module at all, write `BLOCKED: <what>` under this task and stop (240, 241 and 242 must be built and integrated first)
  - [ ] Record in a note the built name of each role in the Context Summary's "Built names" bullet, and the signature of the delivery writer. Confirm `operations/reject_codes.py` already holds `unknown_recipient`, `parent_unknown`, `unknown_request`, `id_reused` and `malformed`; none is added here (a missing one is `BLOCKED:`)
  - [ ] Success: the target is checked out and clean; a note under this task gives the target and the role-to-built-name list

- [ ] **0.2 Branch, helpers and baseline**
  - [ ] `git checkout -b 243-slice.notes-and-release-notes {target}`; if the branch already exists, `git checkout 243-slice.notes-and-release-notes` instead
  - [ ] Note the paths of the helpers later tasks reuse: `tests/store/seed.py`, `tests/operations/release_support.py`, `tests/store/release_support.py`, 241's `tests/mcp_server/test_inbox_watcher.py` (7.1), `tests/live/program/` (8.1), `tests/load/test_report_release_load.py` and 240's `tests/load/test_messages_load.py` (5.6)
  - [ ] Run the checks once and note the baseline. Failures present before this slice are listed by test name in the note and not fixed
  - [ ] Success: `git branch --show-current` prints `243-slice.notes-and-release-notes`; a note under this task gives the baseline result and the helper paths

## 1. Models: `kind`, `to_program`, `NoteView`, `notes` (D1; Development Approach step 1)

- [ ] **1.1 `SendRequest`, `NoteView` and the result fields**
  - [ ] `operations/message_models.py`: `SendRequest` gains `kind` (a `MessageKind`, absent means `request`) and `to_program` (a program id); `to` becomes optional. The cross-field rules are D1's table: `request` requires `to`, `subject`, `body`, `id` and forbids `to_program`; `note` requires `subject`, `body`, `id` and exactly one of `to` and `to_program` and forbids `parent`. Every violation is `malformed` naming the field and the kind; the text limits stay 240's constants, over-limit refused and never cut. The mode-absent default is expressed once (the same way `report_release`'s `mode` does it), not as a literal at each use
  - [ ] `NoteView` (`id`, `from_member`, `to_member`, `to_program`, `subject`, `body`, `created_at`) built from the store's `Message` as `RequestView.from_message` is. `SendResult` gains `note` (null for a request). `InboxResult` gains `notes` (empty list when none). If `message_models.py` passes ~300 lines, put views and results in the module 240 uses for them (`message_results.py`)
  - [ ] Document each new field in `docs/cli-contract.md`: `kind`, `to_program`, `SendResult.note`, `InboxResult.notes`, the `NoteView` fields (prose is task 9.1)
  - [ ] If a 240 model test asserts that a missing `to` is refused for every document (find with `grep -n "to" tests/operations/test_message_models.py` and read the hits), change only that assertion to the new rule (refused for a request, allowed for a note with `to_program`) and say which test in a note. This is the one permitted edit to an existing assertion in this task; the CLI's argparse change is 6.1's
  - [ ] Success: pyright clean; existing tests pass except the assertion above
- [ ] **1.2 Model tests**
  - [ ] `tests/operations/test_note_models.py`: a note with `to` only and with `to_program` only validates; a note with both, neither, a `parent`, or a missing `subject`, `body` or `id` is refused naming the field and `note`; a request with `to_program`, or without `to`, is refused naming the field and `request`; a document with no `kind` is a request; `kind` values outside the enum are refused; subject 200, body 4000 and id 64 accepted and one more refused for a note as for a request; `NoteView.from_message` carries every field, with a null `to_member` for a program note and a null `to_program` for a direct note
  - [ ] Success: checks pass

## 2. Store: note rows, recipients, retention (D2, D6; step 2)

- [ ] **2.1 `programs.pairs_provided_by`**
  - [ ] `store/sql.py`: `SELECT_PAIRS_PROVIDED_BY` beside `SELECT_PAIRS_CONSUMED_BY`, reusing `_PAIR_ENDS_ACTIVE`, ordered by `consumer_id`. `store/programs.py`: `pairs_provided_by(transaction, provider_id)` as `pairs_consumed_by` is written
  - [ ] Success: pyright clean
- [ ] **2.2 Tests for 2.1**
  - [ ] `tests/store/test_programs.py` (added functions): the pairs of a provider with two consumers of different `consumed`, ordered by consumer; a pair whose consumer was removed is not returned, nor one whose provider was removed; a provider with no consumers returns an empty tuple; pairs of another provider are not returned
  - [ ] Success: checks pass
- [ ] **2.3 `store/notes.py`: insert, read, prune**
  - [ ] SQL in `store/sql_messages.py`. `insert_note(transaction, note, recipient_ids, now)`: one `messages` row (`kind` `note`, null `state`, null `expires_at`, `depth` 1, `state_changed_at` equal to `created_at`, `to_member` or `to_program` as the note says) then one delivery per recipient through 240's delivery writer, event `sent`, in the order given, each with the next `seq`. It never reads a clock or config
  - [ ] `received_notes(transaction, member_id, since)`: the notes the member has a delivery for, through the deliveries. Without `since`, every such note in the store, oldest delivery first; with `since`, those whose delivery to this member has `seq > since`, in delivery order. Each note once, with its `sent` delivery returned beside it (as 240's delivery type)
  - [ ] `prune_notes(transaction, cutoff)`: deletes the deliveries of notes with `created_at` before `cutoff`, then those notes, and returns the count; it never touches `kind = 'request'` rows
  - [ ] Success: pyright clean; every function takes `now` or `cutoff` as an argument
- [ ] **2.4 Tests for 2.3**
  - [ ] `tests/store/test_notes.py`: `insert_note` to a member writes one row and one `sent` delivery with the row's column values as above (null state and expiry, `state_changed_at` equal `created_at`); to a program with three recipients writes one row (null `to_member`) and three deliveries with increasing `seq`; a failure after the first delivery leaves no row and no delivery (use the `store.write()` rollback); `received_notes` returns the notes a member has a delivery for, never another's, never a request, honours `since` by `seq` and returns a program note once; `prune_notes` deletes an old note with its deliveries (`foreign_key_check` empty), keeps a young one, and leaves open, accepted and terminal requests alone
  - [ ] Success: checks pass
- [ ] **2.5 Prune statement and due check in the sweep**
  - [ ] `store/message_sweep.py`: `sweep` gains the note prune as its last statement, after the request statements, using `prune_notes` with the same cutoff as the request prune; the expire step is unchanged (it keys on `state = 'open'`). `sweep_due` gains "a note older than the prune cutoff" so a store holding only an aged note reports due. `operations/message_sweep.py` (`sweep_messages`) needs no change if it already calls `sweep_due`; confirm and note it
  - [ ] Success: pyright clean
- [ ] **2.6 Sweep tests**
  - [ ] `tests/store/test_message_sweep.py` (added functions): a note older than `prune_after_days` is pruned by `sweep` with its deliveries, read or not; a younger note stays; the expire step never changes a note (null state); open and accepted requests next to an aged note are untouched; `sweep_due` is true for an aged note alone and false for a young one
  - [ ] `tests/operations/test_message_sweep_wrapper.py` (added function): `sweep_messages` on a store holding only an aged note writes (the note is gone after the call); on a young note it opens no write transaction. `tests/operations/test_list_view.py` (added function): `list` on a store holding only an aged note prunes it
  - [ ] Success: checks pass

## 3. `send` takes a note (D1 to D3; step 3)

- [ ] **3.1 `operations/send_note.py`**
  - [ ] The note path of `send`, called from `send.py` after the sender is resolved and, for a direct note, the recipient is resolved, before any store lock. One write transaction: sweep, resolve recipients, check the id, `insert_note`. Recipients: a direct note has the one resolved member (a removed or unknown one is `unknown_recipient` as for a request; a note to the sender's own member is delivered, D2). A program note reads `get_program` and `members_of` in the transaction, takes the active members except the sender, and rejects `unknown_recipient` with a detail saying "unknown program" or "no one else in the program" (D2); the recipients are fixed at `send`. No `cf` call, process start or wait inside the transaction
  - [ ] Id check (D3): an existing id compares `(kind, from_member, to_member, to_program, parent_id, subject, body)`; equal is outcome `unchanged` with the stored note, no delivery written and no `request_ended` case; different, including a different kind, is `id_reused`. A rejection found here writes its `message_rejections` row in the same transaction, as 240's `send_write.py` does for a request. The row's `to_ref` is the recipient as given: the `to` value for a direct note, the `to_program` value for a program note, null when the document gave neither
  - [ ] Success: pyright clean; the file near 300 lines or less
- [ ] **3.2 The `send` branch**
  - [ ] `operations/send.py`: after validating, `kind` `note` calls 3.1 and `request` takes 240's path unchanged. A malformed note document (task 1.1's refusals) writes its rejection row and returns `rejected` as a malformed request does. Result carries `note` and the notice (240 D11). `send.py` gains only the branch
  - [ ] Success: pyright clean; `send.py` stays under its size limit
- [ ] **3.3 `send` note tests**
  - [ ] `tests/operations/test_send_note.py`: a direct note stores and delivers to the addressee only; a program note of three active members reaches the two others, one delivery each, never the sender; a member added to the program afterwards gets nothing; an unknown program, a program with only the sender, a removed recipient, an unknown recipient, a `parent`, a request with `to_program`, both or neither of `to` and `to_program`, and an over-limit subject, body and id are each rejected and leave exactly one rejection record under the sender (its `to_ref` the program id for a program note, the `to` value for a direct one, null for neither); `not_a_member` leaves none; a resend with equal content is `unchanged` with no new delivery; a changed body, and a request id reused for a note and a note id reused for a request, are `id_reused`; an id pruned and sent again is a new note; a direct note to the sender's own member is delivered; a sender's id beginning `release:` is `malformed` (the id grammar has no colon, so a release note's id cannot collide with a sender's)
  - [ ] Success: checks pass

## 4. 240's code meets a note row (D4; step 3 audit)

- [ ] **4.1 The audit: list every 240 read and write of `messages`**
  - [ ] `grep -rn "messages" src/amoeba/store src/amoeba/operations` and read each statement and function that can return a `messages` row (the by-id read, `reply`, `cancel`, `send`'s parent lookup, the `inbox` reads, the sweep's expire and prune statements, `cancel_member_requests`, the `list` and `status` request reads, 242's `get_message` callers). Put one line per hit under this task: where it is, and which D4 table row governs it. A statement that selects `messages` with no `kind` condition is a defect to fix in 4.2
  - [ ] Success: a note under this task lists every hit; none is left unmapped to a D4 row
- [ ] **4.2 Make each row of D4's table true**
  - [ ] `reply` and `cancel` (through `get_message`): a note's id is rejected `unknown_request` with a detail saying the id is a note and notes take no reply. `send`'s parent lookup: a note's id is `parent_unknown` with a detail saying it is a note. The `inbox` request reads select `kind = 'request'`. `cancel_member_requests` and the `list` and `status` request reads select requests only (non-terminal states already exclude a null state; make the kind condition explicit where the read relies on state alone). Each fix is the smallest change the audit shows; no logic is duplicated, and the kind literal comes from `MessageKind`
  - [ ] Success: pyright clean
- [ ] **4.3 `inbox` returns `notes`**
  - [ ] `operations/inbox.py`: call `received_notes` in the same read transaction as the request reads, with the caller's `since`, and fill `InboxResult.notes` with `NoteView`s and each note's `sent` delivery added to `deliveries` when `since` is given (D4's inbox row: each note once; `as_of_seq` and `beyond_last_record` are 240's, unchanged). It writes and marks nothing
  - [ ] Success: pyright clean
- [ ] **4.4 D4 tests: `reply`, `cancel`, `send` parent and `inbox`**
  - [ ] Add a note row to the fixtures of the existing 240 tests that read messages, as an added fixture row or an added test function (no existing assertion changes): `tests/operations/test_reply.py` and `test_cancel.py` (a note's id is `unknown_request` naming a note, and the note is unchanged), `test_send.py` (a `parent` that is a note's id is `parent_unknown` naming a note), `test_inbox.py` (no note in `requests`)
  - [ ] New `tests/operations/test_inbox_notes.py`: a member sees the notes it has a delivery for in `notes`, with `since` and without, none in `requests`, none it has no delivery for; a program note's sender does not see it; a direct note to one's own member shows; with `since` the notes with `seq > since` in delivery order, once each, their `sent` deliveries in `deliveries`; `as_of_seq` and `beyond_last_record` as before; `inbox` writes nothing (row counts and `PRAGMA data_version` unchanged)
  - [ ] Success: checks pass
- [ ] **4.5 D4 tests: `rm`, `status`, `list` and the sweep**
  - [ ] `tests/operations/test_rm_cascade.py` (added function): `rm` of a member leaves a note to or from it alone, and its deliveries stay. `tests/operations/test_status_requests.py` (added function): a store with an open request and a note shows the request only, `Nothing needs you.` unchanged, and a rejected note `send` appears under the sender's rejected calls; `tests/operations/test_list_view.py` (added function): with the same store `list` shows no note and its document equals `status`'s. `tests/operations/test_message_sweep_wrapper.py` or the sweep test: the expire step never expires a note
  - [ ] Success: checks pass
- [ ] **4.6 D4 tests: scenario D and 242's resolution**
  - [ ] `tests/cli/test_requests_scenario.py` (added function): 240's scenario D chain run again with a program note sent first and a direct note in the middle; every request result and every `inbox` request list is as in the original test
  - [ ] Question resolution (242): `tests/operations/test_pause_held.py` (added function, using its rig): a paused run whose question carries an `amoeba-request:` line naming the id of a note sent by the question's own member ends `waiting_on_pm / request_unknown` with no answering run started
  - [ ] Success: checks pass; 240's other tests pass unchanged

**Commit**: `feat: send notes and keep 240's request code from seeing them`

## 5. Release notes (D5; step 4)

- [ ] **5.1 `operations/release_notes.py`: recipients and composition**
  - [ ] `release_note_recipients(transaction, provider_id, outcome, report, now)`: for `recorded`, `versioned` and `corrected`, take `programs.pairs_provided_by(provider_id)` and, for each distinct `consumed` value, call `visible_releases(transaction, provider_id, consumed, since=encode_timestamp(now))` (never a copy of the visibility SQL); a consumer gets a note when the written report's `seq` is in that result. For `withdrawn` the report is read before the delete and `since` is the report's own `reported_at`, so call it with the stored row. The consumers are returned as ids in a stable order. A provider with no consumers returns none
  - [ ] `compose_release_note(outcome, report) -> (subject, body)` as D5 states: subject `Release report <outcome>: <version, or the commit when there is none>`; body for `recorded`, `versioned` and `corrected` is a first line naming the outcome, then `Commit`, `Version` (or `none`), `Changed`, `Touched` (items joined with `; `), a corrected note saying it replaces the earlier text, and a closing line saying `changes` holds the full record; body for `withdrawn` is the commit and version and that the report was withdrawn and is to be disregarded, with no `changed` text. Outcome words come from `ReportOutcome`, never literals
  - [ ] `RELEASE_NOTE_ID_PREFIX = "release:"` (the one spelling) and `MAX_RELEASE_NOTE_BODY_LENGTH`, computed once as the sum of `MAX_CHANGED_LENGTH`, the touched items at `MAX_TOUCHED_ITEMS` × `MAX_TOUCHED_ITEM_LENGTH` plus their separators, `MAX_VERSION_LENGTH`, the longest of `FULL_HASH_LENGTHS`, and the template's fixed text (take the template's fixed length from the template's own pieces, not a typed number)
  - [ ] Success: pyright clean
- [ ] **5.2 Tests for 5.1**
  - [ ] `tests/operations/test_release_notes.py`, the recipient cases outside D5's table (the table itself is 5.5's matrix): a consumer whose pair was added after the report still gets a correction and a withdrawal note if `changes` shows it the report; a consumer removed gets none; a provider with no consumers gets none
  - [ ] The size test, in two parts. (a) Build the largest report through `ReportReleaseRequest` itself, so the models, not the test, say what the limits are: each field at its limit is accepted and one more is refused (changed text, touched items and item length, version, the longest full hash). Compose it for each of the four outcomes and assert body length ≤ `MAX_RELEASE_NOTE_BODY_LENGTH` and subject length ≤ `send`'s subject limit. (b) Show the check can fail: lengthen one of the template's text pieces after import (monkeypatch) and assert the same check now fails, because the constant, computed at import, no longer covers the body
  - [ ] Two D5 behaviours: a consumer whose mode is changed later (`add --depends-on` again, as the store's `upsert_pair` does) gets no note for an earlier report; and with a fixed clock, a second report by the same provider whose time equals this event's `now` does not add or remove a recipient (the check is on this report's `seq`)
  - [ ] `compose_release_note` tests: the body carries the commit, version (or `none`), changed text and touched items for the three writing outcomes, a correction says it replaces the earlier text, a withdrawal carries no `changed` text and says to disregard
  - [ ] Success: checks pass

**Commit**: `feat: choose the recipients and compose the text of a release note`

- [ ] **5.3 `write_release_notes` and the `report_release` change**
  - [ ] `release_notes.write_release_notes(transaction, provider_id, outcome, report, now)`: finds recipients (5.1), composes once, and writes one note per recipient through `insert_note` (`from_member` the provider, `to_member` the consumer, id `RELEASE_NOTE_ID_PREFIX` + `uuid4().hex`, one per row, no clock read, no `cf` call, no process start)
  - [ ] `operations/report_release.py`: inside the existing `store.write()` block, after the report write, call it for `recorded`, `versioned`, `corrected` and, for `withdrawn`, with the recipients found before the delete (read the stored row before `_apply`'s delete and pass it in); `unchanged` and a rejection call nothing. Take `now` once, as the file does, and pass the same value to the write and to recipients. `ReportReleaseResult` is unchanged. A raise from a note write propagates out of the block, so the report rolls back and the call exits 3 as any store fault does; no new `try`
  - [ ] The sweep (D6: every write that adds a note also sweeps): `wiring_releases.place_release`, for `REPORT_RELEASE` only, calls `sweep_messages(store, load_config(), deps.clock())` before calling `report_release`, so the due-checked sweep runs in its own transactions before the report's. `report_release`'s signature is unchanged. A held store comes back as `sweep_messages`' problem text (it never raises `StoreBusyError`), is logged, and the report still runs; any other `StoreError` propagates (no new `try`), so the call exits 3 before the report is written
  - [ ] Success: pyright clean; the existing `report_release` tests pass unchanged
- [ ] **5.4 `report_release` note tests**
  - [ ] `tests/operations/test_report_release_notes.py` (settable advancing clock from `release_support.py`), the write path only (which consumers is 5.5's matrix): each note is a `messages` row of kind `note` from the provider with a `release:` id and one `sent` delivery; `unchanged` and a rejected `--correct` of an unreported commit write none; `withdrawn` writes notes for the consumers that could see the report, before the delete; a provider with no consumers stores its report and no note; two consumers get two rows with different ids
  - [ ] Atomicity: patch `insert_note` (or the delivery writer) to raise on the second recipient; the call raises, no report row and no note or delivery exists, and the same call run again succeeds as a first call with all notes written. Through the CLI door (add a function to the existing `report-release` CLI test; find it with `ls tests/cli | grep release`) the same failure exits 3 and prints no report
  - [ ] The sweep, through `wiring.invoke(OperationName.REPORT_RELEASE, ...)` (new `tests/test_report_release_sweep.py`): on a store holding an aged note (written by `insert_note` with a `now` older than `prune_after_days`), a `report-release` records its report and the aged note and its deliveries are gone; a young note stays; `sweep_messages` (patched) returning a held-store problem text still lets the report record; a non-busy `StoreError` raised from `sweep_messages` (patched) leaves no report stored
  - [ ] The existing `tests/load/test_no_cf_under_write_lock.py` still passes
  - [ ] Success: checks pass
- [ ] **5.5 The matrix test against `changes`**
  - [ ] `tests/operations/test_release_notes_match_changes.py`: for each consumed value × each outcome in D5's table, run the real `report_release` and then the real `changes` operation for each consumer with `since` equal to that event's own `now`; assert the consumers that received a note are exactly those whose `changes` lists the report, and for a withdrawal run `changes` before the withdraw with `since` equal to the report's `reported_at` and compare the same way. The oracle is `changes`, never the SQL `release_note_recipients` calls. Uses a clock that advances between events on one report
  - [ ] Success: checks pass
- [ ] **5.6 Load tests: note writes inside the write lock**
  - [ ] `tests/load/test_report_release_load.py` (added function, same `_burst` helper and bounds): a provider with `CONSUMERS` active consumers of both `consumed` values (a new named constant; seed them with `insert_member` and `insert_pair` from `tests/store/seed.py`), `WRITERS` threads each reporting `REPORTS_PER_WRITER` distinct commits. Assert: every report is `recorded`; every `from_source` consumer holds one note per report and every `from_release` consumer none; delivery `seq` values are unique; no write exceeds `LATENCY_BOUND_SECONDS` and the burst finishes within `BURST_BUDGET_SECONDS`. Confirm CI gates it: `uv run pytest --collect-only -q tests/load/test_report_release_load.py` lists the new function, and `ci.yml` runs a bare `uv run pytest` with `pyproject.toml` ignoring only `tests/live`; note the result
  - [ ] The program-note path (D5's write-lock paragraph covers `send` too): `tests/load/test_messages_load.py` (240's file; added function, same worker pattern and bounds as 240's cases): a program of `CONSUMERS` + 1 active members and several processes each sending program notes under distinct ids. Assert: every `send` is `sent`; every recipient holds one delivery per note and the sender none; delivery `seq` values are unique; no call waits beyond one store-wait bound; the stub `cf` finds the write lock free whenever it is called, as 240's case asserts
  - [ ] Success: checks pass

**Commit**: `feat: write a release note to each consumer in the report's transaction`

## 6. Doors: CLI, MCP, rules text (D1, D8; step 5)

- [ ] **6.1 CLI `send --note --to-program`**
  - [ ] `cli/registration_messages.py` and the parser: `--note` (a flag, absent when not given, so the document carries no `kind`), `--to-program ID`; `--to` is no longer required by argparse, so a missing recipient is rejected by the operation with the same detail on both doors. Exit codes as 240 (`sent` and `unchanged` 0, `rejected` 1). `cli/render/messages.py`: the text for a note result (outcome line and the note's id, notice first when message text follows). Add the synopsis to `docs/cli-contract.md`
  - [ ] `cli/render/messages.py` and the `inbox` text: a **Notes** section listing each note (sender, subject, body, age), the notice first. Document the section in `docs/cli-contract.md`
  - [ ] If a 240 CLI test asserts that `send` without `--to` is an argparse usage error (find with `grep -n "\-\-to" tests/cli/test_send_cli.py`), change only that assertion to the rejection (exit 1, `malformed`) and say which test in a note. This is the second and last permitted edit to an existing assertion
  - [ ] Success: pyright clean
- [ ] **6.2 CLI tests**
  - [ ] `tests/cli/test_send_note_cli.py`: `--note --to-program` and `--note --to` send; no `--note` sends a request exactly as before; `--to-program` without `--note` is a rejection with exit 1; neither recipient is exit 1 `malformed`; text and `-j` output; the unchanged resend exits 0. `tests/cli/test_inbox_cli.py` (added functions): notes in text and in `-j` under `notes`
  - [ ] Success: checks pass

- [ ] **6.3 MCP `send` and `inbox`**
  - [ ] `mcp/message_tools.py`: the `send` tool takes `kind` and `to_program`; the `send` and `inbox` descriptions say a note needs no reply and carry no example values; the server's `INSTRUCTIONS` constant gains one sentence on notes (find with `grep -rn "INSTRUCTIONS" src/amoeba/mcp`). `wiring_messages.py` needs no new arm; confirm and note it. `docs/mcp-server.md`: the `send` fields `kind` and `to_program` and the `inbox` field `notes` (the prose is 9.1)
  - [ ] Tests: `tests/mcp_server/test_tools.py` and `test_instructions.py` (the fields, the descriptions, the sentence); the in-process parity test (the tool's result equals the CLI's `-j`) added for a direct note, a program note and an `inbox` with notes
  - [ ] Success: checks pass

- [ ] **6.4 The rules text (D8)**
  - [ ] `docs/program-rules.md`: one paragraph added to the Handling block, stating a `note` in `inbox` is information from another repo, written by its agent and so data to judge; read it, act on it only as this repo's own rules say, send no reply; a release note says a repo this one depends on recorded, corrected or withdrew a release report, the same report `changes` lists, so the Consumer block's check before designing a slice still applies. Only flags the parser has; no sample id
  - [ ] `tests/test_program_rules_doc.py` (added function): the Handling block names `note` and says no reply is needed; the existing flag test covers the paragraph
  - [ ] Success: checks pass

**Commit**: `feat: send notes from the CLI and MCP and add the note rule`

## 7. Push test through 241's check (Success Criteria, Push)

- [ ] **7.1 Push check reports a note like a request**
  - [ ] `tests/mcp_server/test_note_push.py`, using 241's own push check (`push_rows_after` and `channel_event` through the watcher's one-tick function, as `test_inbox_watcher.py` drives them): a fixture member with a baseline; send a direct note, a program note and a release note (through `report_release`) to it with the real operations; run the check; assert one channel event whose entries name kind `note`, event `sent` and the sender's member id for each, and that the event content and meta contain no subject, body, note id or `release:` text (use marker strings in the subject and body)
  - [ ] Success: checks pass

## 8. Live test (Integration Requirements)

- [ ] **8.1 Provider and two consumers through real `cf`**
  - [ ] `tests/live/notes/` modelled on `tests/live/program/` (`conftest.py`, the `consumer.py` rig): real `cf`, git fixture repos in one program, a provider and two consumers (one `from_source`, one `from_release`), run through the real CLI by the harness's absolute path with `AMOEBA_HOME` set to a throwaway directory (first test asserts the store lies under it). A report, a version, a correction and a withdrawal each reach the right consumers' `inbox -j`
  - [ ] Run `uv run pytest tests/live/notes`; `tests/live/program` and `tests/live/messaging` still pass
  - [ ] Success: the tier passes

**Commit**: `test: add the notes push test and live tier`

## 9. Documents and amendments (Technical Scope, Amendments)

- [ ] **9.1 Contract docs**
  - [ ] `docs/cli-contract.md`: prose for the `--note` and `--to-program` flags, the `note` kind rules (no `parent`, one of `to`/`to_program`, no state), `notes` in `inbox`, the rule that a note needs no reply and `reply`/`cancel`/`--parent` refuse its id, and `MAX_RELEASE_NOTE_BODY_LENGTH` with its value and what it is derived from, beside the `send` limits. `docs/mcp-server.md`: the prose for the `send` and `inbox` fields (their entries are 6.3's). `docs/store-contract.md`: notes are written by `send` and `report_release`; a release note's id has the `release:` prefix and a sender's cannot; a note has null `state` and `expires_at` and `state_changed_at` equal to `created_at`; notes are pruned by `created_at`; a note's exit is the prune
  - [ ] Success: `tests/test_contract_docs.py` passes
- [ ] **9.2 Amend the 240 design, the architecture and the plan**
  - [ ] `user/slices/240-slice.requests.md`, each where the sentence is (design's Amendments list): the API Contracts table (`send` fields, `--to` no longer required, `inbox` `notes`), D2's resend comparison (gains `to_program`), D4's `reply` and `cancel` loads, D6's prune step (gains notes) and the Sweep paragraph's `sweep_messages` due check (gains aged notes) and callers (gain `report_release`, through its wiring), D7's request reads and `notes`, D8's parent check, and "Provides to Other Slices" (the 243 line, and the 244 line saying the wake hook sits in `send`'s request branch)
  - [ ] `user/architecture/240-arch.agent-messaging.md`: "Operations" `send` row (`parent` for a request only), `inbox` (notes listed by delivery), "Message kinds" ("the same consumers" means the consumers that see the report in `changes`), "Expiry" (the prune also removes notes), the "Delivery" principle "The sender picks the id" (a release note's id is Amoeba's `release:` id), and the text-limit sentence (a release note body is bounded by `MAX_RELEASE_NOTE_BODY_LENGTH`, composed, not caller text)
  - [ ] `user/architecture/240-slices.agent-messaging.md`: plan entry 4's limits and "the same consumers" statements, and its Dependencies line reading 222, 227, 240 and, for the push test and the request-resolution test, 241 and 242, as the design's Amendments list says. Also its Implementation Order paragraph, whose line "242 and 243 need only 240" becomes: 242 needs only 240; 243 needs 240, plus 241 and 242 for one test each
  - [ ] `user/tasks/240-tasks.requests.md`: task 11.1b's flag line (`send --to` is required there; 243 makes it optional and adds `--note` and `--to-program`), with a pointer to 243
  - [ ] Success: `sed -n '/(243) Notes and Release Notes/,/Relative Effort/p' user/architecture/240-slices.agent-messaging.md | grep "Dependencies"` prints a line naming 241 and 242, and the same range piped to `grep -c MAX_RELEASE_NOTE_BODY_LENGTH` prints at least 1; `grep -n "242 and 243 need only 240" user/architecture/240-slices.agent-messaging.md` finds nothing; `grep -n "MAX_RELEASE_NOTE_BODY_LENGTH" user/architecture/240-arch.agent-messaging.md` finds it; checks pass
- [ ] **9.3 Changelog**
  - [ ] `CHANGELOG.md` `[Unreleased]`: slice 243 entry: `send --note` (`--to` or `--to-program`), the `kind` and `to_program` MCP fields, notes in `inbox`, a release note per consumer from `report-release`, note retention, no migration and no config key; **open agent sessions must be restarted** to see the new `send` fields; each member's Handling block is updated by an agent in that repo
  - [ ] Success: the entry exists under `[Unreleased]`

**Commit**: `docs: document notes and release notes, amend the 240 parents`

## 10. Final verification

- [ ] **10.1 Verification Walkthrough and criteria**
  - [ ] Run the design's Verification Walkthrough steps 1 to 6 (step 1 is all four checks; steps 2 to 6 under a throwaway `AMOEBA_HOME`, never the live store). `tests/live/notes` runs the same flow, so the manual steps may be its output; note which
  - [ ] Confirm by name: `tests/test_contract_docs.py`, `tests/test_import_boundaries.py`, `tests/test_read_side_defined_once.py`, `tests/store/test_vocabulary_pinning.py` and `tests/test_message_timing.py` pass, and that `grep -rn '"release:"' src/amoeba` finds one spelling. Confirm `EXPECTED_SCHEMA_VERSION` equals its value on the target (`git diff {target} -- src/amoeba/store/migrations.py src/amoeba/store/schema` is empty)
  - [ ] Confirm 227, 240 and 241 are unchanged apart from what the design names: `git diff {target} -- tests | grep '^-[^-]'` lists only the assertions tasks 1.1 and 6.1 name; every other test change is an added function or fixture row
  - [ ] In `user/slices/243-slice.notes-and-release-notes.md`, update the Verification Walkthrough where Phase 6 changed it (it says it is refined when Phase 6 is complete)
  - [ ] Success: all checks pass; every Success Criteria line in the design maps to a passing test named in a note under this task

**Commit**: `docs: refine the 243 walkthrough after final verification`
