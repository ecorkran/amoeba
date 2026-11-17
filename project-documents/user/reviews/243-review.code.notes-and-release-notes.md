---
docType: review
layer: project
reviewType: code
slice: notes-and-release-notes
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/243-slice.notes-and-release-notes.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261117
dateUpdated: 20261117
reviewedSha: a3a77d96845f6dc4e76099fe84b0291680697a24
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 35
diffTruncated: false
effort: xhigh
turns: 36
promptTokens: 3851410
cachedTokens: 3423356
cacheWriteTokens: 428026
completionTokens: 94263
durationSeconds: 409.7
costUsd: 0.88964
costBasis: provider
runId: run-20261117-p6-63c2f683
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: documentation-drift
    summary: "Sweep-skip visibility: code, cli-contract and slice design disagree"
    location: "docs/cli-contract.md:760"
  - id: F002
    severity: concern
    category: test-debt
    summary: "Renamed test stubs the path it names, so the real note row is never exercised"
    location: "tests/operations/test_request_release.py:279-298"
  - id: F003
    severity: note
    category: error-handling-observability
    summary: "Removed guards lose the question key from their errors"
    location: "src/amoeba/operations/request_release.py:111"
  - id: F004
    severity: note
    category: security-hygiene
    summary: "A program note is not limited to the sender's own program"
    location: "src/amoeba/operations/send_note.py#_recipients"
  - id: F005
    severity: note
    category: correctness
    summary: "\"Oldest\" for the cap breaks timestamp ties by message id"
    location: "src/amoeba/store/sql_messages.py:85-88"
  - id: F006
    severity: note
    category: other
    summary: "The send-cut pointer sends the sender to a call it cannot make"
    location: "src/amoeba/cli/render/messages.py#NOTE_CUT_IN_SEND"
  - id: F007
    severity: note
    category: architectural-decay
    summary: "`write_note` repeats the orchestration of `write_send`"
    location: "src/amoeba/operations/send_note.py#write_note"
  - id: F008
    severity: note
    category: documentation-drift
    summary: "Stale future tense in a test docstring"
    location: "tests/cli/test_requests_scenario.py#_write_note"
  - id: F009
    severity: pass
    category: correctness
    summary: "Release-note recipients use the `changes` rule, and correction timing matches it"
    location: "src/amoeba/operations/release_notes.py#release_note_recipients"
  - id: F010
    severity: pass
    category: correctness
    summary: "A note id no longer crashes cancel, reply, or a parent check"
    location: "src/amoeba/operations/reject_codes.py#as_request"
  - id: F011
    severity: pass
    category: security-hygiene
    summary: "SQL is built from constants and bound values only"
    location: "src/amoeba/store/sql_messages.py"
---

# Review: code — slice 243

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 34 successful tool call(s) of 35 made; 231904 of 231904 diff characters reached the model

## Findings

### [CONCERN] Sweep-skip visibility: code, cli-contract and slice design disagree

`cli-contract.md:760` says a held store skips the sweep, "which is logged, and the report is still recorded: the result does not show it." The code shows it in three places. `wiring_releases.place_release` attaches it (`src/amoeba/wiring_releases.py:37-39`). `ReportReleaseResult.sweep_problem` carries it (`src/amoeba/operations/report_release_models.py:172-174`). `render_report_release` prints it (`src/amoeba/cli/render/releases.py:65-66`). The JSON result has the key, and `test_wiring` pins it.

The slice design takes a third position. `243-slice.notes-and-release-notes.md:196` and `:244` both say `ReportReleaseResult` is unchanged. D6 (line 211) says the problem text is handled "as for every sweep caller", and `status` does surface it in its result (`status_models.py:221`).

Choose one. Either the result carries the text (fix the `cli-contract` sentence and amend the two "unchanged" lines in the design), or it is only logged (remove the field, the render line and the wiring `model_copy`). Note also that wiring fills the field after the operation returns, so direct callers of `report_release` never see it.

### [CONCERN] Renamed test stubs the path it names, so the real note row is never exercised

The guard in `request_release._due_rows` that raised "held question … names a note" was removed. `_due_rows` now calls `effective_state` directly (`src/amoeba/operations/request_release.py:111-112`). The test was edited to monkeypatch `effective_state` so the stub raises. Because the stub replaces the real function, the test passes whether or not the real `effective_state` raises for notes. It only checks that `start_ended_held` logs whatever `StoreError` it receives.

Seed a real note with `insert_note`, hold a row whose `request_id` is that note's id, and assert the logged error and that no spawn happens. The pause_held test is different: `link_for` does reject notes (`pause_held.py:59-64`), so that test does run the real path.

### [NOTE] Removed guards lose the question key from their errors

Before this diff, `_due_rows`, `held_request_states` (`status_runs.py:89`) and `_evaluate` (`pause_held.py:122`) raised `StoreRowError` naming the held question's key. They now rely on `effective_state` (`src/amoeba/store/messages.py:68-69`), which reports only `message '<id>' is a note, not a request`. The log from `start_ended_held` says only "could not read the held questions to start," with no row key. The failure is still loud and logged, but an operator has less to go on. Either re-raise with the key in each caller, or accept the loss and say so.

### [NOTE] A program note is not limited to the sender's own program

`_recipients` takes the `to_program` id, checks only that the program exists, and fans out to its active members except the sender. Nothing requires the sender to belong to that program. Slice design D2 (`243-slice…md:126-129`) states the same rule, and direct requests already resolve a member "in any program" (`message_member.py:118`). So this matches the design and the request model, but a member of program A can now put one note in front of every member of program B, where a request reaches one recipient. Confirm this is intended before release. If not, require `sender ∈ program` and add a rejection test.

### [NOTE] "Oldest" for the cap breaks timestamp ties by message id

`SELECT_NOTES_BEYOND_NEWEST_FROM` orders by `created_at DESC, message_id DESC`. Two notes with the same timestamp are ranked by id, which for release notes is random hex. Production timestamps have microsecond precision, so ties appear only under a fixed clock, which the load test uses (`_burst` with `SettableClock`). That test asserts counts only, so it does not check which notes survive. Ordering by `rowid` (insertion order) would match what D6 promises. Low risk now.

### [NOTE] The send-cut pointer sends the sender to a call it cannot make

The line reads "A note cut with … is whole in the -j result of this call." The sender cannot get the full text from the call that printed the cut text unless it runs the same command again with `-j`. That re-run returns `unchanged` with the full note, so it works, but the wording does not say to re-run. Inbox also never lists a sender's own notes. Consider "run the same command with -j for the whole note."

### [NOTE] `write_note` repeats the orchestration of `write_send`

`write_note` runs the same sequence as `send_write.write_send`: sweep, id lookup, resend-or-reject, recipient check, make room, insert, result. The shared pieces (`same_content`, `id_reused`, `reject_send`, `sent_result`) were extracted, so the duplication is small. Still, a change to the request path's order, such as where the sweep runs, must now be made in two places. Consider one orchestrator parameterized by kind, or a comment in both files saying they move together.

### [NOTE] Stale future tense in a test docstring

The docstring says the helper writes notes "as ``send --note`` will (243 6.1)." The `send --note` path is in this diff, so "will" is stale. Trivial to fix.

### [PASS] Release-note recipients use the `changes` rule, and correction timing matches it

Recipients come from `visible_releases`, the same function `changes` uses, with `since` set to now (or the report's `reported_at` on withdrawal). They are then filtered to this report's `seq`, which handles two reports at the same instant. I checked `CORRECT_RELEASE` (`src/amoeba/store/sql.py:193-198`): a correction moves `reported_at`, and moves `versioned_at` to now when a version is present. A from-release consumer therefore sees a corrected, versioned report in its `versioned_at >= now` read and gets the correction note. `VERSION_RELEASE` leaves `reported_at` alone, so from-source consumers are not re-notified on a version. Both match D5.

### [PASS] A note id no longer crashes cancel, reply, or a parent check

Before this diff, `cancel` on a note id reached `effective_state` returning `None` and raised `ValueError`. `as_request` now returns `NotARequest`, and each caller turns that into `unknown_request` or `parent_unknown` with a detail naming the note. I read the call sites (`cancel.py:158`, `reply.py`, `send_write.py:123`), and each one uses the narrowed value. The test suite has a case for each path.

### [PASS] SQL is built from constants and bound values only

The f-strings in `sql_messages.py` and `sql.py` (`_NOTE`, `_QUALIFIED_MESSAGE_COLUMNS`, `SELECT_RECEIVED_NOTES`, `SELECT_PAIRS_PROVIDED_BY`) interpolate only module-level constants. Runtime values (member id, `since`, cutoffs, keep count) bind through `?`, as the amoeba SQL rule requires. I checked the due-check parameter list (now, request cutoff, note cutoff, rejection cutoff) against its placeholders. I found no deferral language in the source.

### Run Digest

- Response length: 11578 chars
- Response is newline-free: no
- Tool calls made: 35
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 36
- Tokens — prompt / cached / cache write / completion / reasoning: 3851410 / 3423356 / 428026 / 94263 / not computed
- Duration: 409.7 s
- Cost: $0.89 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
