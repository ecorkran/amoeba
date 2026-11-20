---
docType: review
layer: project
reviewType: tasks
slice: standing-answers
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/230-tasks.standing-answers.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: e346099eb6f902b762a69cdcbb5b55a0153b1390
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 27
effort: xhigh
turns: 28
promptTokens: 1145656
cachedTokens: 977855
cacheWriteTokens: 167783
completionTokens: 72251
durationSeconds: 304.5
costUsd: 0.38418
costBasis: provider
runId: run-20261120-p5-ebc0a23b
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every success criterion has a task"
    location: "project-documents/user/slices/230-slice.standing-answers.md:210-242"
  - id: F002
    severity: pass
    category: accuracy
    summary: "Built names, paths and test anchors match the repo"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:42"
  - id: F003
    severity: pass
    category: process
    summary: "Phase 7 hand-off matches `update_live.py`"
    location: "scripts/update_live.py:224-239"
  - id: F004
    severity: concern
    category: design-accuracy
    summary: "The walkthrough names an exit that does not release a waiting question"
    location: "project-documents/user/slices/230-slice.standing-answers.md:271"
  - id: F005
    severity: concern
    category: concurrency
    summary: "The `cf` lookup's place relative to the write transaction is not stated"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:110"
  - id: F006
    severity: concern
    category: format
    summary: "Numbered sub-steps have no checkboxes"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:90-94"
  - id: F007
    severity: note
    category: consistency
    summary: "Task 5.4 adds size-check logic to a file the breakdown says should not grow"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:174"
  - id: F008
    severity: note
    category: proportionality
    summary: "One test in 1.2 is beyond what the criteria need"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:79"
  - id: F009
    severity: note
    category: sequencing
    summary: "Twelve commit markers across ten sections"
    location: "project-documents/user/tasks/230-tasks.standing-answers.md:202"
---

# Review: tasks — slice 230

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Every success criterion has a task

Functional criteria F1 to F6 map to 5.7 and 9.1 (reach `all` sent), 2.2 and 5.7 (reach filtering, withdrawn rows excluded), 4.5 (`--all` shows reason), 6.2 (barred item declined), 7.1 and 7.2 (member removal), and 5.4, 5.5 and 5.7 (`sources_too_large` with both shares). Technical criteria map to 1.1 and 1.2 (migration 010, version 10), 2.2 and 9.2 (`?` binding, members AST test), 5.5 and 5.7 (passage tests), 5.2 (prompt tests against `PassageKind`) and 9.2 (all four checks). Integration criteria map to 9.1, and the walkthrough to 9.2. No criterion lacks a task, and no task traces to nothing. The one test beyond the criteria is noted below.

### [PASS] Built names, paths and test anchors match the repo

Verified: `EXPECTED_SCHEMA_VERSION` is 9 (`store/migrations.py:25`), with `001` to `009` present. `assemble` is at `answering/passages.py:327`, `gather`, `_read_store` and `_StoredFacts` at `operations/pause_context.py:160-200`, `apply_removal` at `operations/set_up_remove.py:140`, `list_view` at `operations/list_view.py:119`, `members_view` at `operations/list_registry.py:136`, `invoke` at `wiring.py:149`, and `place_message` at `wiring_messages.py:61`. `project_of` takes `run` and `reference` and runs `cf` with no working directory unless one is passed (`project_of.py:92-105`). `PassageKind`'s last member is `REQUEST_RESULT`, so appending `STANDING_ANSWER` works. `KIND_SENTENCES`, the two pinned `test_parser_names` tests, `DIRECTORY_TOOLS`, `INSTRUCTIONS`, and the test anchors the breakdown models on (`test_a_context_failure_waits_with_its_reason_and_starts_nothing`, `test_an_item_barred_for_one_member_and_allowed_for_another_differs`) all exist. The `docs/` files exist, and the live pause harness uses its own `AMOEBA_HOME`.

### [PASS] Phase 7 hand-off matches `update_live.py`

`update` backs up, installs, migrates, and checks schema version, integrity, foreign keys, member count and the MCP tool set. The tool set must equal the `OperationName` values (line 233). The breakdown adds `OperationName.STANDING` and `WITHDRAW` together with the MCP tools `standing` and `withdraw` (4.1, 4.2), so that check passes. `restore` exists (line 304). Keep this pairing if the names change.

### [CONCERN] The walkthrough names an exit that does not release a waiting question

The bullet says "`withdraw` is the exit" for a question that waits as `sources_too_large`. Withdraw only changes later questions. The design says so itself: a new standing answer "does not go back and answer questions already waiting" (line 268), and withdraw does not either. The same applies to raising the cap or shortening the rules. The waiting question exits only by `answer` or `dismiss`, as the bullet's last sentence says. This is not a dead end, but the PM would be told the wrong exit. Task 0.2 amends the design and does not correct this. Add it to 0.2: name `answer` or `dismiss` as the exit for the waiting question, and state whether the existing system re-checks a waiting question after a cap change.

### [CONCERN] The `cf` lookup's place relative to the write transaction is not stated

`project_of` runs a `cf` subprocess with a timeout (`project_of.py:106`). `get_member` takes a transaction (`store/programs.py:86`), so the active-member check has to run inside `store.write()`. The text does not say that the `cf` call happens before the transaction opens. An implementer who puts both inside `write()` holds the SQLite write lock for up to the `cf` timeout and blocks every other writer. Say in 3.2 that `project_of` runs first, outside `store.write()`, and that `get_member` and `give_standing` run inside it.

### [CONCERN] Numbered sub-steps have no checkboxes

The items in 2.1 (lines 90 to 94), 4.1 (lines 129 to 132) and 4.2 (lines 135 to 137) are numbered without `[ ]`. The convention requires a checkbox on every item and subitem. Without them the task-checker cannot check these steps off, and an implementer cannot tell which are done. Convert them to `  - [ ]` lines.

### [NOTE] Task 5.4 adds size-check logic to a file the breakdown says should not grow

The Context Summary says new logic goes in new modules and that `answering/passages.py` (390 lines, verified) gains only a call, a field or a row. Task 5.4 puts the share computation and the `sources_too_large` detail inside `passages.py`. Compute both shares in `answering/standing_passages.py`, and let `passages.py` gain a call and a branch. Or record the exception under the task.

### [NOTE] One test in 1.2 is beyond what the criteria need

"A store at version 11 is refused by the existing newer-schema guard" tests behavior this slice does not change, and no criterion names it. Cut that sentence. The `CHECK`-rejection tests stay, because they test the design's D1 contract.

### [NOTE] Twelve commit markers across ten sections

Each marker sits at a working, tested point, so the placement is acceptable. Sections 6 and 7 are a few lines each. If you want fewer commits, combine 6 with 5 or 7 with 6. This is optional.

### Run Digest

- Response length: 7861 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 1145656 / 977855 / 167783 / 72251 / not computed
- Duration: 304.5 s
- Cost: $0.38 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

## Resolution

- [pass] Every success criterion has a task: no change.
- [pass] Built names, paths and test anchors match the repo: no change.
- [pass] Phase 7 hand-off matches `update_live.py`: no change; the names and MCP tools still land together in section 4.
- [concern] Walkthrough exit: 0.2 now amends the Operator Walkthrough's "Too many or too long" bullet. The waiting question exits by `answer`, `dismiss` or the run moving on. `withdraw`, a raised cap or shorter rules change only later questions, because a `waiting_on_pm` row is skipped and never gathered again (`operations/pause_existing.py`).
- [concern] `cf` lookup placement: 3.2 now says `project_of` runs before `store.write()` opens, and the program or member check and `give_standing` run inside the one write transaction.
- [concern] Numbered sub-steps: the items in 2.1, 4.1 and 4.2 are now `- [ ]` checkboxes.
- [note] Size-check logic in `passages.py`: the detail text moves to `too_large_detail` in `answering/standing_passages.py`. `passages.py` gains only the parameter, the call, the second size reading and the call to `too_large_detail`.
- [note] Extra test in 1.2: cut the version-11 refusal sentence.
- [note] Twelve commit markers: rejected. The review calls the placement acceptable and the merge optional, and each marker sits at a working, tested point.
