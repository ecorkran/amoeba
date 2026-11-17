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
reviewedSha: 4755c4c3238a1701f05440ba481c770a72366d94
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 32
diffTruncated: false
effort: xhigh
turns: 33
promptTokens: 3086464
cachedTokens: 2699759
cacheWriteTokens: 386679
completionTokens: 63716
durationSeconds: 297.2
costUsd: 0.690503
costBasis: provider
runId: run-20261117-p6-63c2f683
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: error-handling-observability
    summary: "Release notes are skipped silently when the post-write read finds no row"
    location: "src/amoeba/operations/report_release.py:127-129"
  - id: F002
    severity: concern
    category: performance-resource
    summary: "Notes have no per-sender cap, and `inbox` returns every held note"
    location: "src/amoeba/operations/send_note.py:29-62"
  - id: F003
    severity: concern
    category: architectural-decay
    summary: "The width of a joined message row is a hard-coded 18, duplicated from the column list"
    location: "src/amoeba/store/notes.py#received_notes"
  - id: F004
    severity: note
    category: architectural-decay
    summary: "After `as_request`, the `state is None` guard in reply and cancel can no longer run"
    location: "src/amoeba/operations/reply.py:162-164 and src/amoeba/operations/cancel.py#_problem"
  - id: F005
    severity: note
    category: documentation-drift
    summary: "MCP instructions omit `versioned` from the release-note outcomes"
    location: "src/amoeba/mcp/server.py:98-99"
  - id: F006
    severity: note
    category: other
    summary: "Text `inbox` cuts release-note bodies to one line with no cut marker"
    location: "src/amoeba/cli/render/messages.py#_note_block"
  - id: F007
    severity: note
    category: test-debt
    summary: "The live test's state-path guard uses a hard-coded default path"
    location: "tests/live/notes/test_notes_live.py#LIVE_STATE"
---

# Review: code — slice 243

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 32 successful tool call(s) of 32 made; 198873 of 198873 diff characters reached the model

## Findings

### [CONCERN] Release notes are skipped silently when the post-write read finds no row

`_write_report` reads the stored report after the write with `after = releases.release_for_commit(...)`, then runs `if after is not None and plan.outcome in NOTE_OUTCOMES:`. For RECORDED, VERSIONED and CORRECTED, `after` should never be `None`. If it is, the note write is skipped, nothing is logged, and the call returns success with `report=None`. A `None` is only legitimate for WITHDRAWN, and that path writes its notes before the delete. The sibling code in `store/notes.py` (`insert_note`) raises `AssertionError` when the row is missing after its insert. The project rules forbid silent fallbacks. Narrow the condition to the note outcomes and raise when `after` is `None` for a written report.

### [CONCERN] Notes have no per-sender cap, and `inbox` returns every held note

Requests are capped at `MAX_REQUESTS_PER_SENDER` (200, `operations/message_models.py`) through `_make_room`. `write_note` has no equivalent check, so a sender can write any number of notes inside the retention window. A program note also writes one row plus one delivery per member. Nothing bounds the read side: `SELECT_RECEIVED_NOTES` in `store/sql_messages.py` has no `LIMIT`, so `inbox` without `since` returns every held note. A release note body can be up to `MAX_RELEASE_NOTE_BODY_LENGTH` = 14439 characters (`docs/cli-contract.md`), against 4000 for caller text. The slice design (D6) bounds notes by age only. Either add a count cap with a stated outcome at the limit, or record in the design why age alone is enough for both the write and read sides.

### [CONCERN] The width of a joined message row is a hard-coded 18, duplicated from the column list

`_MESSAGE_WIDTH = 18` splits the joined `SELECT_RECEIVED_NOTES` row into message fields and delivery fields. The real column count lives in `sql_messages._MESSAGE_COLUMNS`, and `message_from_row` reads those columns by hard-coded index 0 to 17. If a column is added to `_MESSAGE_COLUMNS` and this constant is not changed, delivery fields are read from the wrong positions. Some of those misreads could pass the type checks silently. The module that owns the column tuple already splits it into `_QUALIFIED_MESSAGE_COLUMNS`, so derive the width from the same tuple and export it from `sql_messages`.

### [NOTE] After `as_request`, the `state is None` guard in reply and cancel can no longer run

`effective_state` returns `None` only for a note, and `as_request` now refuses notes first. The schema also requires a non-null `state` for every `kind = 'request'` row. The `raise ValueError("... is not a request; it has no state")` branch is therefore unreachable, and its message no longer describes what it guards. Keep it as an invariant assertion with an accurate message, or remove it.

### [NOTE] MCP instructions omit `versioned` from the release-note outcomes

The instructions say a release note means a repo "recorded, corrected or withdrew a release report". `NOTE_OUTCOMES` in `operations/release_notes.py` also includes VERSIONED, which writes a note with the subject "Release report versioned: …" (covered by the live test). An agent reading the instructions would not expect a note when a version is added. The same wording appears in the 243 task file. I did not open `docs/program-rules.md`, so check that file for the same omission.

### [NOTE] Text `inbox` cuts release-note bodies to one line with no cut marker

`_note_block` renders the body with `prose_line`, which joins all whitespace and cuts to the column width (`cli/render/text.py:34-44`). A multi-line release note therefore appears as one line. Its Touched list and closing pointer to `changes` are usually not visible in text output. `_note_block` never calls `was_cut`, although `cli/render/waiting.py` uses it to flag cut text. Requests share the cut behavior, and the `text.py` docstring says the full text is in `-j`, so this is consistent but hard for an agent reading text output to notice. Consider a "(cut; see -j)" marker for notes, as `waiting.py` does.

### [NOTE] The live test's state-path guard uses a hard-coded default path

`LIVE_STATE` is the literal `Path.home() / ".local" / "state" / "amoeba"`, while the store under test is resolved by `store_path()`. The `not resolved.is_relative_to(LIVE_STATE)` assertion only protects that one literal location. The stronger check is the `resolved.is_relative_to(amoeba_home)` assertion next to it, so the literal adds little and could drift from the real resolver. Derive it from the same resolver, or remove it.

### Run Digest

- Response length: 8517 chars
- Response is newline-free: no
- Tool calls made: 32
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 33
- Tokens — prompt / cached / cache write / completion / reasoning: 3086464 / 2699759 / 386679 / 63716 / not computed
- Duration: 297.2 s
- Cost: $0.69 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
