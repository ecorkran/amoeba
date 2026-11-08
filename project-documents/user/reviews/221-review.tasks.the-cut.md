---
docType: review
layer: project
reviewType: tasks
slice: the-cut
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/221-tasks.the-cut.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 1dffaed5d7421780ff4d0d6c4d454a1b0a3d38c4
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 196193
cachedTokens: 98264
cacheWriteTokens: 97923
completionTokens: 4900
durationSeconds: 39.3
costUsd: 0.451372
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage"
    location: "project-documents/user/tasks/221-tasks.the-cut.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit markers"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:97"
  - id: F003
    severity: concern
    category: coverage
    summary: "Reworked scripts and docs have no owning task"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:84-86"
  - id: F004
    severity: concern
    category: task-scope
    summary: "Task 2.14 bundles two unrelated pieces of work"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:165-169"
  - id: F005
    severity: note
    category: task-scope
    summary: "Test triage overlaps the severing tasks"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:119-134"
  - id: F006
    severity: note
    category: sequencing
    summary: "Fixes found during section 3 have no commit home"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:197-208"
  - id: F007
    severity: note
    category: dependencies
    summary: "Audit file is not yet present"
    location: "project-documents/user/tasks/221-tasks.the-cut.md:51-55"
  - id: F008
    severity: pass
    category: proportionality
    summary: "Proportionality"
    location: "project-documents/user/tasks/221-tasks.the-cut.md"
---

# Review: tasks — slice 221

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage

Each design criterion maps to a task:
- **Delete list:** tasks 1.1–1.5 and 2.10–2.13 remove every `delete` and `squadron` path.
- **D3 locations:** tasks 2.2–2.5 move the kept units.
- **Four checks:** tasks 1.6, 2.19 and 4.2 run them.
- **Library tests without a store, and the `src/amoeba` contents:** tasks 2.13 and 2.19.
- **Live tier:** tasks 2.17, 2.18 and 3.2.
- **Boundaries test:** task 2.14.
- **`uv build` and packaging:** tasks 1.2–1.4, 2.15, 2.16 and 3.1.
- **Audit-row changes:** tasks 2.1 and 4.2.
- **README:** task 4.1.
- **`amoeba#32`:** deferred to Phase 7, as the design says.

No task lacks a tie to a criterion or a D-decision, so I found no scope creep. The slice states no NFR, so no load-test or CI-gating task is required. Deleting `tests/load` matches D8.

### [PASS] Sequencing and commit markers

Dependencies run in a sound order: leaf deletions, then moves and severs while the old code still exists, then the remaining deletions, then tests and packaging, then the gate, then the wheel build, live tier and README. The old code can't compile between the moves and the deletions, so section 2 correctly gets one commit, after the gate at 2.19. The markers sit at points where checks pass: after 1.6, after 2.19 and after 4.2. Moving the boundaries test from the design's step 3 into 2.14 is the right call, because the gate needs it rewritten.

### [CONCERN] Reworked scripts and docs have no owning task

Task 1.5 deletes the `delete` files under `scripts/` and `docs/` and leaves the `keep` and `rework` ones. No task says how a `rework` script or doc is changed. D9 says `docs/` and `scripts/` follow the audit, and the "every `rework` unit at its audit location" criterion covers them. Only the 1.6 grep touches them, and it runs before the moves, so a script importing `amoeba.runner.answering` or `amoeba.store` after section 2 is only caught if lint or pyright covers `scripts/`. Docs are only checked by the 4.2 grep, which gives no instruction to fix hits.

Add a sub-item to 2.8 or 2.9 to update `rework` scripts and docs to the new paths. Extend the grep at 2.19 or 2.9 to `scripts docs`.

### [CONCERN] Task 2.14 bundles two unrelated pieces of work

Task 2.14 covers a broad triage of every remaining test, with the old-shape fixture sweep, and the rewrite of `tests/test_import_boundaries.py` to the single D6 rule. The triage is open-ended and needs judgement per test, and its success line ("no test or fixture mentions nodes, journal entries, blocked states or a tick") is easy to over-claim. The boundaries rewrite is small and has a crisp success line. Split the rewrite into its own task (for example 2.14b) so the large triage doesn't hide it.

### [NOTE] Test triage overlaps the severing tasks

Tasks 2.2, 2.4 and 2.6 already move or rework tests for the code they touch. Task 2.14 then triages the remainder. A short line in 2.14 would remove the ambiguity: "tests already moved or reworked by 2.2–2.8 are not revisited except for the old-shape sweep".

### [NOTE] Fixes found during section 3 have no commit home

Section 3 says it changes no files. If `uv build` or the live tier exposes a defect from the cut, the fix would land in the final `docs:` commit, which mixes code and README. State where such a fix goes: either amend it into the 2.19 commit, or accept a `fix:` commit. It is a small matter.

### [NOTE] Audit file is not yet present

`project-documents/user/analysis/220-analysis.code-audit.md` does not exist in the repo yet. Task 0.2 handles this correctly with a `BLOCKED:` line and a stop, so no change is needed. Implementation can't begin until slice 220 completes.

### [PASS] Proportionality

A single task file is the right size for this slice. The steps name the checks and the audit sections to read, and they leave implementation to the D-decisions. The only test-related work is reworking the kept tests, as D8 requires, and the one new rewrite is the D6 boundaries test the design asks for. I found no extra test tasks. Task 2.16 refers to two `test_wheel_contents.py` files, one under `runner/answering` and one under `runner/request_run`. Both exist in the repo, so that reference is accurate.

### Run Digest

- Response length: 5212 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 196193 / 98264 / 97923 / 4900 / not computed
- Duration: 39.3 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Resolution

- [pass] Success criteria coverage: no change needed.
- [pass] Sequencing and commit markers: no change needed.
- [concern] Reworked scripts and docs have no owning task: added task 2.16, which edits each `rework` script and doc per the audit row's reason; tasks after it renumbered.
- [concern] Task 2.14 bundles two unrelated pieces of work: split into 2.14 (test triage) and 2.15 (import-boundaries rewrite).
- [note] Test triage overlaps the severing tasks: 2.14 now covers only tests not already moved or re-signatured in 2.2 to 2.8.
- [note] Fixes found during section 3 have no commit home: 3.1 now says a needed file change is committed as `refactor: {what was fixed}`, the section's only commit.
- [note] Audit file is not yet present: rejected as a task change. Task 0.2 already stops with `BLOCKED:` unless the audit is `complete`, and the design makes 220 a dependency; the file appears when slice 220 runs.
- [pass] Proportionality: no change needed.
