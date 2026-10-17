---
docType: review
layer: project
reviewType: tasks
slice: context-forge-event-seam
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/108-tasks.context-forge-event-seam.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261016
dateUpdated: 20261016
reviewedSha: f79f1f5ebab5fe9d03cf09af6e00fd8a21db71ae
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 99094
cachedTokens: 8724
cacheWriteTokens: 90366
completionTokens: 5063
durationSeconds: 41.7
costUsd: 0.413644
costBasis: provider
runId: run-20261017-p56-7ed94110
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam.md:312-355"
  - id: F002
    severity: concern
    category: sequencing
    summary: "`cf_scan_interval_seconds` is added in 5.1 but settings-enumerating tests are only updated in 6.1"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam.md:296"
  - id: F003
    severity: concern
    category: task-scope
    summary: "Task 5.1 is overweight and restates the LLD algorithm"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam.md:294-302"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Task 5.3 re-tests parser outcomes already covered in Task 2.4"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam.md:344"
  - id: F005
    severity: concern
    category: commit-checkpoints
    summary: "Long runs of untested implementation tasks share one commit"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam.md:93"
  - id: F006
    severity: concern
    category: clarity
    summary: "Vague or unverifiable steps"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam.md:233"
  - id: F007
    severity: note
    category: sequencing
    summary: "Task ordering and dependencies are sound"
    location: "project-documents/user/tasks/108-tasks.context-forge-event-seam.md:31"
---

# Review: tasks — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage

All functional and technical criteria trace to tasks, with no gaps:
- **Worktree and project-level change** (`worktree_id` null), **first snapshot**, **unrelated writes silent**, and **down-time restart**: Task 5.2.
- **Failure outcomes once per transition**, **malformed `worktrees` in the linked entry versus another entry**, **store exception logged and re-raised**, and **no subprocess in `tick`**: Tasks 2.4 and 5.3.
- **Link twice is a no-op** and **empty id quarantined**: Task 4.2.
- **`cf --version` captured once**: Task 6.2.
- **Fields defined once**: Task 2.4.
- **Store import direction**, **feed invariant**, and **7 → 8 upgrade**: Task 3.4.
- **Fixture capture**: Task 1.2.
- **End-to-end across `kill -9`**: Task 6.4.
- **Docs**: Task 6.5.
- **Walkthrough**: Task 6.6.

No scope creep was found. The slice states no NFR, so no load test or CI gating task is required.

### [CONCERN] `cf_scan_interval_seconds` is added in 5.1 but settings-enumerating tests are only updated in 6.1

Task 5.1 adds a field to `ProcessSettings`. The instruction to "update any test that enumerates settings or `start` flags" appears only in Task 6.1 (line 370). Task 5.3 must leave the full suite passing, and that is the commit that carries 5.1, so any settings-enumeration test would fail there. Move both settings, or at least the test update, into one task. The simplest fix is to add both settings in 5.1, or to move the interval into 6.1 and have the 5.x tests pass it to the tenant as an argument.

### [CONCERN] Task 5.1 is overweight and restates the LLD algorithm

The reading note (line 23) says the file does not restate the LLD. Task 5.1 then re-narrates the tick algorithm from "Data Flow": the record conditions, the remembered-key rules, and the log levels. It also mixes in a settings edit, the outcome mapping, and a function-splitting instruction. At effort 4 with seven dense steps, it is the one task likely to exceed a junior AI's scope. Cut the step text to "implement `tick` per the LLD Data Flow, D1, D3, D4, D9" plus the items the LLD does not settle: follow `ReviewDetectionTenant`, and the outcome mapping lives in this module. Move the settings edit out (see the previous finding).

### [CONCERN] Task 5.3 re-tests parser outcomes already covered in Task 2.4

The bullet enumerates invalid JSON, `{}`, unknown id, malformed `worktrees`, and the same defect in another entry. Task 2.4 (lines 146-147) already covers these through `parse`. The tenant only adds two things: the OS-error cases (absent file, permission denied) and the once-per-transition recording. Cut the bullet to one representative per outcome class plus the OS-error cases. The "other entry leaves link `observed`" check does not need repeating at tenant level. Likewise, 5.2 and 6.4 both include a restart-over-the-same-store scenario. Keep both, since the LLD requires the end-to-end test, but keep 6.4 to a single happy-path flow.

### [CONCERN] Long runs of untested implementation tasks share one commit

Tasks 2.1–2.3 (three tasks), 3.1–3.3 (three, including the migration with no test until 3.4), and 5.1 plus its two test tasks are each committed as a unit. Sections 2 and 5 follow the "a commit never holds untested behavior" rule the file sets, so this is acceptable. Task 2.1 is only types and constants and could merge into 2.2 to cut a task boundary. Task 3.2 (the migration) is not exercised until 3.4, so a quick "fresh store opens at version 8" check there is worthwhile. The success criterion already says so, but no step runs it.

### [CONCERN] Vague or unverifiable steps

- **Task 3.4 (line 233):** "Extend `tests/store/test_import_direction`-style check (wherever the store's import rule is tested)" leaves the target file unnamed. Task 2.4 handles the same situation by saying "extend `test_import_direction.py` if it enumerates packages". Name the actual file after checking it, or phrase it the same way.
- **Task 5.1 (line 301):** it requires the INFO log of the resolved path on first tick, but no test in 5.2 or 5.3 asserts it.
- **Task 6.6 (line 470):** `rm -rf "$AMOEBA_STORE_DIR" "$CFDIR"` runs against shell variables. State that both must be non-empty and point at the `mktemp -d` directories before deleting, since an unset or reassigned variable would delete something else.

### [NOTE] Task ordering and dependencies are sound

The order runs fixture, then pure parser and diff, then store, then inbox kind, then tenant, then wiring, listings, end-to-end, docs, and validation. Each task's declared dependencies point backward. Task 6.4 correctly follows 6.3, because it needs `inspect cf-snapshots`. The D7 gate in Task 1.1 correctly precedes the tasks it affects, and the file lists them (6.1, 6.2, 6.4, 6.5, 6.6).

### Run Digest

- Response length: 5832 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 99094 / 8724 / 90366 / 5063 / not computed
- Duration: 41.7 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
