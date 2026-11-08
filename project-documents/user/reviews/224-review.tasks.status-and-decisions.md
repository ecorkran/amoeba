---
docType: review
layer: project
reviewType: tasks
slice: status-and-decisions
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/224-tasks.status-and-decisions.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 21f3879722c451ad17ee8e4acf8c62d2fc728eb4
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 210608
cachedTokens: 103722
cacheWriteTokens: 106880
completionTokens: 5652
durationSeconds: 45.9
costUsd: 0.495267
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "Task 5.1 gives no way to produce most of the six real `sq runs list` fixtures"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:221-225"
  - id: F002
    severity: concern
    category: completeness
    summary: "Walkthrough step 5.3 has no fixture for a pause the rules don't settle"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:231-234"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Task file is heavy for a 3/5 slice, and test pairing is inconsistent"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:86-217"
  - id: F004
    severity: note
    category: sequencing
    summary: "Hard `BLOCKED:` in 2.4 stops the slice over a fixture detail"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:103"
  - id: F005
    severity: note
    category: completeness
    summary: "`StatusResult` doesn't carry a rejected outcome, though `status` can reject"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:164"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Coverage of design decisions D1–D10"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Sequencing and commit markers"
    location: "project-documents/user/tasks/224-tasks.status-and-decisions.md:84"
---

# Review: tasks — slice 224

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 5.1 gives no way to produce most of the six real `sq runs list` fixtures

Task 5.1 requires real captures of six states, with "Never hand-write". Only the paused agent question has a named source, `tests/live/pause/asks_question.yaml`. That file is created in 223's task 2.2 (`223-tasks.pause-handling.md:129`), so the reference is valid.
- The other five states have no production method. These are a running run, a paused run of another checkpoint kind, a `null`-directory run, an older paused run, and a paused run in another directory.
- A `null`-directory run needs a pre-#303 run file. The task gives no way to get one, and the only other route is hand-editing, which the task forbids.
- 223's review flagged the same stall for its "other checkpoint kind" case.
- Add a how-to for each state, such as a second pipeline YAML or a copied run directory. Or add a `BLOCKED:` fallback for any state that can't be captured.

### [CONCERN] Walkthrough step 5.3 has no fixture for a pause the rules don't settle

Design walkthrough step 6 needs a pause that `handle_pause` declines, so that a `waiting_on_pm` entry and a later `pm` record with `based_on.waiting_reason` appear. The only pause fixture named anywhere is `asks_question.yaml`, which 223 builds so the repo's rules settle it. No task creates or points to an unsettled pipeline. Task 5.3's success line requires that outcome, so a junior would stall there. Add a small task, for example a second `tests/live/pause/` YAML whose question the rules can't settle, or tell 5.3 to use one that already exists.

### [CONCERN] Task file is heavy for a 3/5 slice, and test pairing is inconsistent

The file has about 35 subtasks. Section 3 alone has twelve, with separate test tasks for placement, classification and waiting questions.
- The test-with pattern is applied unevenly. 2.5, 3.4 and 3.5 fold tests into the implementation task. 2.1/2.2, 2.6/2.7, 3.2/3.3, 3.6/3.7, 3.8/3.9 and 3.10 split them.
- Task 3.4 bundles three unrelated store reads: `open_questions`, `latest_rows_by_run`, and a programs/members read. The programs/members read has no named tests.
- Task 2.5 puts request validation and `RejectCode` in one task, while 2.6 and 2.7 split the rest of `decisions`.
- Merge 3.8 and 3.9 and merge 3.10 into one task each. Split 3.4 into question reads and run-row reads. Use one consistent convention for test pairing. Don't drop any test the design requires (D10).

### [NOTE] Hard `BLOCKED:` in 2.4 stops the slice over a fixture detail

Task 2.4 stops the whole slice if no real `cf list projects --json` entry lacks `projectPath`. The design only wants such an entry as a fixture for the missing-field case. Consider allowing the test to proceed with the real capture and noting the absence. That would keep the more important `decisions` and `mark_read` work moving.

### [NOTE] `StatusResult` doesn't carry a rejected outcome, though `status` can reject

Tasks 3.5 and 3.11 have `status` return `rejected / unknown_program`, and 4.1 and 4.2 expect exit 1 from it. Task 3.11 doesn't say that `StatusResult` carries `outcome` and `problems` the way `DecisionsResult` and `MarkReadResult` do. Task 3.11 could say so in one line.

### [PASS] Coverage of design decisions D1–D10

- D1: `run_list`, the `--all` decision and the timeout are in 3.2 and 5.1.
- D2: scope is in 3.5.
- D3: `classify_pause`, the `handle_pause` wiring and the cross-check test are in 1.1–1.3 and 3.12.
- D4: placement and waiting questions are in 3.6–3.10.
- D5: decision reads, records and `read_through` are in 2.1–2.7.
- D6: member names are in 2.3 and 2.4.
- D7: `mark_read`, including the concurrency test, is in 2.8 and 2.9.
- D8: result shapes and CLI are in 3.11 and 4.1.
- D9: the schema test and `store-contract.md` are in 2.10.
- D10: fixtures are in 2.4, 3.1 and 5.1.

I found no scope creep. 1.4 (the `waiting_reason` pin) and 2.10 trace to D5 and D9.

### [PASS] Sequencing and commit markers

`classify_pause` comes first, then the read-side operations that don't need #303, then `status`, then the CLI, then the post-#303 work. There are no circular dependencies. `Deps` fields are added before they are used (2.3 and 3.2, then 4.1). `**Commit**:` markers sit after tested units: 1.4, 2.10, 3.12, 4.2 and 6.1. They are plain lines, not checkboxes. The last marker covers tasks 5 and 6, so the possible `BLOCKED:` stops in section 5 hold back only the final commit.

### Run Digest

- Response length: 5460 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 210608 / 103722 / 106880 / 5652 / not computed
- Duration: 45.9 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Resolution

- [concern] Task 5.1 gave no way to produce most real `sq runs list` fixtures: applied. 5.1 now says how to produce each case with real `sq` (running and paused from `asks_question.yaml`, other-kind pause from 223's recorded pipeline, other-directory pause from a second worktree, older pause left unresolved). The `null`-directory case uses a pre-#303 run file if one is listed, else a real listing edited for that one run and marked as edited in the README.
- [concern] Walkthrough step 5.3 had no unsettled-pause fixture: applied. 5.3 now first creates `tests/live/pause/asks_unsettled_question.yaml`, a question no rule file in the test member settles, modelled on `asks_question.yaml`.
- [concern] Task file heavy, test pairing inconsistent: applied. Every separate test task is merged into its implementation task ("... and tests", one Success line), so pairing is uniform. Tasks went from 34 to 28 and are renumbered, with cross-references updated. No tasks removed or functions dropped.
- [note] Hard `BLOCKED:` in 2.4: applied. It is replaced with: keep an entry lacking `projectPath` if one exists, else note it in the README and go on, since the reader reads only `id` and `name`. This is now task 2.3.
- [note] `StatusResult` had no rejected outcome: applied. Task 3.8 gives `StatusResult` `outcome` (`listed` or `rejected`) and `problems`, matching `DecisionsResult`; `unknown_program` gives `rejected`.
- [pass] Coverage of D1-D10: no change needed.
- [pass] Sequencing and commit markers: no change needed (markers are unchanged and still follow tested points).
