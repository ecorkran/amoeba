---
docType: review
layer: project
reviewType: tasks
slice: notes-and-release-notes
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/243-tasks.notes-and-release-notes.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 961e1a26b45ae39fb56963419929d084d9d0d7e6
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 27
effort: xhigh
turns: 28
promptTokens: 1569629
cachedTokens: 1382363
cacheWriteTokens: 187244
completionTokens: 62649
durationSeconds: 282.8
costUsd: 0.400509
costBasis: provider
runId: run-20261115-tasks-plan-962527a1
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every success criterion maps to a task"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:251"
  - id: F002
    severity: pass
    category: verification
    summary: "Referenced helpers and prerequisite tests are present or planned"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:66"
  - id: F003
    severity: pass
    category: verification
    summary: "Load-test CI gating is in place"
    location: ".github/workflows/ci.yml:40"
  - id: F004
    severity: pass
    category: sequencing
    summary: "Sequencing has no cycles and respects the build order"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:144"
  - id: F005
    severity: concern
    category: coverage
    summary: "Program-note transaction is not load-tested under the write lock"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:172"
  - id: F006
    severity: concern
    category: design-rules
    summary: "A store read only through `inbox` never prunes its notes"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:329"
  - id: F007
    severity: concern
    category: sequencing
    summary: "The parent design disagrees with the tasks until group 9"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:60"
  - id: F008
    severity: concern
    category: proportionality
    summary: "The D5 table is tested three times, and 5.2 is overweight"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:152"
  - id: F009
    severity: concern
    category: commit-cadence
    summary: "Commit markers sit after nearly every group in the back half"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:211"
  - id: F010
    severity: note
    category: coverage
    summary: "A sender's `release:` id is refused by grammar but not tested here"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:116"
  - id: F011
    severity: note
    category: verification
    summary: "Branch creation does not handle an existing branch"
    location: "project-documents/user/tasks/243-tasks.notes-and-release-notes.md:65"
---

# Review: tasks — slice 243

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Every success criterion maps to a task

Each Functional, Technical and Integration line has a task: program and direct fan-out and late members (3.3); rejections and their rows (3.2, 3.3); resend and id reuse (3.3); reply, cancel and parent refusal (4.2, 4.4); inbox notes (4.4); the one-transaction atomicity test (5.4); the matrix against `changes` (5.5); the release body bound (5.2); rm, expiry, list and status (4.5); prune and the due check (2.6); no migration and contract docs (9.1, 10.1); MCP parity (6.3); scenario D and 242's row (4.6); push through 241's check (7.1); the live test (8.1).

### [PASS] Referenced helpers and prerequisite tests are present or planned

These exist now: `tests/store/seed.py`, `tests/operations/release_support.py`, `tests/store/release_support.py`, `tests/cf_stub.py`, `tests/rule_blocks.py`, `tests/operations/test_list_view.py`, `tests/store/test_programs.py`, `tests/live/program/` (with `consumer.py`). The symbols exist too: `sql.ACTIVE_MEMBER`, `_PAIR_ENDS_ACTIVE`, `SELECT_PAIRS_CONSUMED_BY`, `programs.pairs_consumed_by`, `visible_releases`, the report constants, `ReportOutcome`, and the load-test constants. `sql.py` is 484 lines, as the task states. The 240 and 242 files the tasks name are planned in their task files (`test_message_timing.py`, `test_send.py`, `test_rm_cascade.py`, `test_status_requests.py`, `test_message_sweep_wrapper.py`, `tests/live/messaging`, `test_pause_held.py`). 0.1 gates on them. The 9.2 search targets exist in the 240 plan (line 82 heading, line 114 dependency sentence).

### [PASS] Load-test CI gating is in place

CI runs a bare `uv run pytest`, and `pyproject.toml:64` ignores only `tests/live`. So `tests/load/test_report_release_load.py` is gated without a wiring task. 5.6's confirm step is the right check.

### [PASS] Sequencing has no cycles and respects the build order

The D4 audit (group 4) lands before release notes (group 5) write rows that 240's reads could see. The commit after group 4 (line 142) matches that. 0.1 gates the build on 240, 241 and 242 being built. No task merges or pushes.

### [CONCERN] Program-note transaction is not load-tested under the write lock

The design's Write lock paragraph (243-slice:94) says both the note `send` and `report_release` keep the write lock short, and that a program note's in-lock work grows with its member count. 5.6 load-tests only `report_release`. 240's `test_message_timing.py` counts `cf` lookups and waits, not per-recipient inserts, so nothing bounds the program-note path the design asserts. 240 plans `tests/load/test_messages_load.py`, and 243 adds no program-note case to it. Add one, with a fixed member count and 5.6's bounds, to that file or to 5.6.

### [CONCERN] A store read only through `inbox` never prunes its notes

The prune runs only from `send`, `reply`, `cancel`, `list`, `status` and `handle_pause` (240-slice.requests.md:107; 243-slice:203). `inbox` writes nothing (4.4 tests this, task line 132), and neither 241's watcher nor 242 adds a sweep caller. A machine whose agents only read `inbox` and receive `report-release` notes never prunes them. The walkthrough's "Dead ends found: none" misses this. The design needs either a named trigger or a stated bound. Letting `inbox` run the due-checked sweep is the one trigger that works, but it changes the design's "inbox writes nothing" contract and 4.4's test. The PM should choose.

### [CONCERN] The parent design disagrees with the tasks until group 9

The design omits 242 from its frontmatter (lines 6–10) and Prerequisites (60–63), and says "242: no change" (line 229). Yet D4's last row is tested against 242 (4.6), and the design does not state depth 1 (State Management, lines 98–100), which 2.3 writes. Task 9.2 (line 231) fixes both, but last. Make the 243 design edits on the target in 0.1, before 0.2 cuts the branch, so the branch forks from a consistent design. The 240 and architecture edits can stay in 9.2.

### [CONCERN] The D5 table is tested three times, and 5.2 is overweight

The same D5 table is asserted in 5.2 (recipients per row, line 152), 5.4 (each outcome to exactly the consumers of D5's table, line 165) and 5.5 (the matrix against `changes`, line 170). The design's success criterion is the 5.5 matrix. Cut the table cases from 5.4 and keep its write-path checks: kind, `release:` id, one `sent` delivery, `unchanged` and rejections write nothing, withdrawal before the delete, no consumers. Also cut the helper-path note in 0.2 (line 66) to the paths the later tasks use.

### [CONCERN] Commit markers sit after nearly every group in the back half

Markers sit at 5.2, 5.6, 6.2, 6.3, 6.4, 7.1, 8.1, 9.3 and 10.1. So the MCP door (6.3), one rules paragraph (6.4) and one test (7.1) each become a standalone commit. Markers belong at working, tested points, not after every task. Merge 6.2 to 6.4 into one marker, and fold 7.1 into the 8.1 commit.

### [NOTE] A sender's `release:` id is refused by grammar but not tested here

D5 says a release note's id cannot collide with a sender's, because 240's id grammar (`[A-Za-z0-9][A-Za-z0-9._-]*`, 240-slice.requests.md:134) has no colon. 9.1 documents "a sender's cannot", but no 243 task asserts it. Add one assertion to 3.3: a sender's id beginning `release:` is `malformed`.

### [NOTE] Branch creation does not handle an existing branch

CLAUDE.md step 5 says to switch to the branch if it already exists. 0.2 runs only `git checkout -b`, so a rerun after an interruption fails. Add "if it exists, `git checkout` it."

### Run Digest

- Response length: 8494 chars
- Response is newline-free: no
- Tool calls made: 27
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 28
- Tokens — prompt / cached / cache write / completion / reasoning: 1569629 / 1382363 / 187244 / 62649 / not computed
- Duration: 282.8 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11

## Resolution

- F001 (pass, every success criterion maps to a task): no change needed.
- F002 (pass, helpers and prerequisite tests present or planned): no change needed.
- F003 (pass, load-test CI gating): no change needed.
- F004 (pass, sequencing): no change needed.
- F005 (program-note path not load-tested): fixed. Task 5.6 now has a second load case in 240's `tests/load/test_messages_load.py`: a program with `CONSUMERS` + 1 members, several processes sending program notes, with the delivery, `seq`, wait-bound and no-`cf`-under-lock assertions. The file is added to 0.2's helper list.
- F006 (a store read only through `inbox` never prunes): fixed without the `inbox` sweep. Letting `inbox` sweep would break 240's "inbox writes nothing" contract and change its timing bound. The exit already exists, since anyone running `amoeba list` or `status` prunes the notes (the due check). Task 0.1 now adds that to the design's Operator Walkthrough "Nobody reads a note" bullet, so the dead end is recorded, not missed.
- F007 (design disagrees with the tasks until group 9): fixed. The 243 design edits (242 in frontmatter and Prerequisites, `depth` 1 in State Management, and the F006 walkthrough sentence) moved from 9.2 to 0.1, on the target with their own commit marker, before 0.2 cuts the branch. 9.2 keeps only the 240 and architecture edits.
- F008 (D5 table tested three times, 5.2 overweight): fixed. 5.4 now tests the write path only (row shape, `release:` id, one `sent` delivery, nothing written for `unchanged` and rejections, withdrawal before the delete, no consumers). 5.2 keeps only the recipient cases outside the table (pair added later, removed consumer, no consumers). 5.5's matrix owns the table. 0.2's helper list is cut to the paths later tasks use.
- F009 (too many commit markers in the back half): fixed. The markers after 6.2 and 6.3 are removed, so 6.1 to 6.4 commit once as `feat: send notes from the CLI and MCP and add the note rule`. The 7.1 marker is removed and the push test commits with the live tier. This reverses the earlier round's split of group 6, as this review asked.
- F010 (a sender's `release:` id not tested): fixed. Task 3.3 now asserts that a sender's id beginning `release:` is `malformed`.
- F011 (branch creation ignores an existing branch): fixed. Task 0.2 now says to `git checkout` the branch if it already exists.
