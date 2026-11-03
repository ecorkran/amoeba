---
docType: review
layer: project
reviewType: tasks
slice: answering-run
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/144-tasks.answering-run.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: db20cce4c5e0346dbf6b86acef6c9db61ccc6fd6
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 213325
cachedTokens: 106739
cacheWriteTokens: 106580
completionTokens: 4104
durationSeconds: 37.1
costUsd: 0.478887
costBasis: provider
runId: run-20261103-p5-b9aa2db9
squadronVersion: 0.24.14
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria and technical requirements map to tasks"
    location: "project-documents/user/tasks/144-tasks.answering-run.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit markers"
    location: "project-documents/user/tasks/144-tasks.answering-run.md"
  - id: F003
    severity: concern
    category: completeness
    summary: "No task names the source of \"unresolved `sq_answer` entries\""
    location: "project-documents/user/tasks/144-tasks.answering-run.md:263-281"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Duplicate test coverage across tasks"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:86,291,309,164"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Test tasks fragmented across many small files"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:267,275,285,290"
  - id: F006
    severity: concern
    category: scope
    summary: "2.2 leaves the `classify` change point ambiguous, and 2.3 adds a mutation check beyond the criteria"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:82,88"
  - id: F007
    severity: note
    category: process
    summary: "Conditional commit marker in Task 13"
    location: "project-documents/user/tasks/144-tasks.answering-run.md:347"
---

# Review: tasks — slice 144

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria and technical requirements map to tasks

I traced each Success Criteria bullet to at least one task, and I found no gaps.
- **Run and decline paths.** The answered case is in 11.1 and 8.2, and the live version is in 14.2. Every decline reason is in 6.2, 8.2, 9.2 and 9.4.
- **Races and recovery.** The race cases are in 11.2. The "burst of pending" cap is in 10.6. Restart adoption and the crash between `begin_answering` and the spawn are in 2.7 and 11.2. The D4 done-guard is in 2.4, 2.5 and 11.2.
- **Settings.** The four required settings keys and the `.squadron.toml` cost cap are in 5.2 and 9.2.
- **Technical requirements.** Crash safety is in 4.3 and 8.4. The `awaits_routing` and `record_finished` pins are in 2.3. The 14 → 15 migration is in 3.2. Purity is in 6.2 and 13.1. The docs requirements are in 12.3.

### [PASS] Sequencing and commit markers

Dependencies run forward with no cycles: kind, then migration and types, then store operations, settings, decide, stub, finish, launch, stage and tick, end to end, inspection, and docs. Each implementation task is followed by its tests. 10.5 correctly bundles the `settle.py`, `stage.py` and `tick.py` changes so the suite stays green. `**Commit**:` markers sit at tested, working points. The stub `sq` in Task 7 commits with Task 8, which the file says explicitly. The live tier (14.1 and 14.2) carries `BLOCKED:` lines and sits last, so it does not hold up the rest.

### [CONCERN] No task names the source of "unresolved `sq_answer` entries"

10.1 (observe pass) and 10.5 (cap check) both need the project's unresolved `sq_answer` entries, but no task says where that list comes from. `Store.unresolved_journal_entries(project_id)` exists at `src/amoeba/store/journal.py:289`, so a kind filter over its result may be enough. The task should say so, and say which module holds the filter, so the observe pass and the cap count use the same one and the cap cannot drift from the set being observed. Add one line to 10.1 naming the helper and its single call site for both uses.

### [CONCERN] Duplicate test coverage across tasks

Several assertions are specified twice:
- "`sq_answer` never reaches `record_finished`" is in 2.3 and 10.7.
- "No answerer section → no `sq_answer` journaled" is in 10.7 and 11.2.
- "Every new `DeclineReason` is accepted by `decline_question`" is in 3.4. The 4.5 detail/evidence cases overlap with it.

Each belongs in one place. Cut 10.7's `record_finished` line and one of the two no-section cases. This matches the file's own habit of saying "covered by Task X" in 8.2 and 11.1.

### [CONCERN] Test tasks fragmented across many small files

The stage gets four test files (observe, stranded, pending, tick), and all four use the same stub `sq` and store harness. The stranded pass test in 10.4 is three small cases. Merging 10.2 and 10.4 into one `test_stage_passes.py`, or folding 10.4 into 10.2, would cut overhead without losing coverage. The file runs to 14 groups and about 40 subtasks for a relative-effort-4 slice. Consolidating the test tasks is the main place to trim.

### [CONCERN] 2.2 leaves the `classify` change point ambiguous, and 2.3 adds a mutation check beyond the criteria

The slice design (D3) names the change point: `resolutions/stage._answer` passes `supervision_entries(...)` to `classify`. 2.2 instead tells the implementer to "choose the one place that covers every caller", which invites a different design than the one decided. State the D3 location and let the implementer deviate only if another `classify` caller turns up. The "temporarily remove filters from two readers, then restore" step in 2.3 is a manual mutation test. The slice criteria do not ask for it. It also edits production code mid-task, which is risky for a junior implementer. Drop it, or replace it with a test that fails for each reader on its own.

### [NOTE] Conditional commit marker in Task 13

The commit marker for 13.1 applies only if the pass changed files. This is acceptable under the "markers are optional" rule, but the implementer must treat "no changes" as "no commit". The text already says so.

### Run Digest

- Response length: 4824 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 213325 / 106739 / 106580 / 4104 / not computed
- Duration: 37.1 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
