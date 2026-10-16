---
docType: review
layer: project
reviewType: tasks
slice: judge-samples-checks-and-calibration
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 16b074042139b5b5f54b3bf2388a2858e29304a8
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
turns: 11
promptTokens: 478300
cachedTokens: 376077
cacheWriteTokens: 102211
completionTokens: 6899
durationSeconds: 55.4
costUsd: 0.516137
costBasis: provider
runId: run-20261016-p56-6f6dfbbb
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "No test ties the `CheckPayload` fields to the store's payload keys"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:107"
  - id: F002
    severity: concern
    category: process
    summary: "Task 8.3 closes GitHub issue #2 from an unmerged slice branch"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:320"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Tasks 3.3 and 3.4 are untested until Task 3.5, so test-with is loosely applied"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:201-257"
  - id: F004
    severity: note
    category: sequencing
    summary: "The judge fixture is a PM-blocking dependency discovered late"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:154"
  - id: F005
    severity: note
    category: traceability
    summary: "The slice design is inconsistent about how many new change kinds there are"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:351"
  - id: F006
    severity: note
    category: test-coverage
    summary: "The no-metrology test bans a word across all of `src/`"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:54"
  - id: F007
    severity: pass
    category: traceability
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md"
  - id: F008
    severity: pass
    category: sequencing
    summary: "Sequencing, commit cadence and proportionality fit the slice"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:25"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] No test ties the `CheckPayload` fields to the store's payload keys

Task 2.1 defines the `check` payload keys as constants and a payload-to-`CheckInput` function in the store, which cannot import pydantic. Task 6.1 then says `CheckPayload` has "field names [that] are the constants". Pydantic attributes can't be built from constants, so the two sets of names can drift apart. Task 4.1 does the same for `judge_invocation_id`.

The repo already guards the verdict equivalent. `tests/store/test_verdict_payload_types.py:48` iterates `model.model_fields`. No task here carries that over. Task 2.2 tests the conversion without pydantic, and Task 6.2 tests the inbox paths only. Add one parity assertion to Task 6.2: the `CheckPayload` field names equal the `check_models.py` key constants. Add the equivalent check for the new verdict key to Task 4.2.

### [CONCERN] Task 8.3 closes GitHub issue #2 from an unmerged slice branch

Task 8.3 runs `gh issue close 2` with a commit sha. That commit sits on the slice branch, which isn't merged until after the Phase 7 code review. Closing an issue is outward-facing and hard to reverse, and `CLAUDE.md` says to confirm those first. The pointer would reference a sha that isn't on the target, and the fix could still change in review.

Make this step a PM-confirmed action that happens after the merge. Alternatively, have the task prepare the comment text and leave the close to the PM. The slice design says only that the issue "is closed with a pointer to D4", so this fits it.

### [CONCERN] Tasks 3.3 and 3.4 are untested until Task 3.5, so test-with is loosely applied

`CheckWriter` (3.3), `CheckOperations` (3.4) and their only tests (3.5) form one three-task commit. Task 3.3's rejection order and first-wins retry logic gets no test until two tasks later. That is the longest untested run in the file. The other pairs are tight.

Either fold 3.3 and 3.4 into one task so the test task follows directly, or give 3.3 a minimal direct test. The wording "a commit never holds untested behavior" holds, but the test-with spacing doesn't.

### [NOTE] The judge fixture is a PM-blocking dependency discovered late

The slice design's Development Approach puts the fixture capture first. The task file moves it to Task 6.5 on purpose so earlier work isn't blocked. That is reasonable, and it correctly forbids hand-writing the fixture. No judge-template artifact exists in `tests/fixtures/sq_reviews/` today, and Tasks 7.2, 8.1 and 8.3 all need one. Add a line to Task 1.1 so the PM can start the capture in parallel, instead of the implementer stopping at 6.5.

### [NOTE] The slice design is inconsistent about how many new change kinds there are

Technical Requirements says "two new kinds", but D9 and the migration define one (`check_recorded`). Task 6.4 notices this and follows D9. That is correct. The slice design text should be corrected so the requirement is unambiguous.

### [NOTE] The no-metrology test bans a word across all of `src/`

Task 5.2 scans `src/` for the substring `metrology`. A grep of `src/` found no matches today, so the test will pass. It would also fail on any future docstring or comment that merely mentions the word. This is acceptable and stricter than the requirement. It matches the slice design's intent, so I'm not asking for a change.

### [PASS] Success-criteria coverage is complete

I traced every functional and technical requirement to a task and found no gaps:
- Judge samples, the D2 check, and the `verdicts` filter: Tasks 4.1–4.6.
- The previous-round skip: Task 4.6.
- Calibration counts, no-write, and no-metrology: Task 5.2.
- Check standing and `vacuous`: Tasks 2.2 and 7.5.
- Negative-count rejection, `record_progress`, retry and WARNING, and the non-empty version: Tasks 3.5 and 6.2.
- The feed trigger and invariant test: Task 6.4.
- The fixture, sample ids, and the D4 refusal with exit 12: Tasks 6.5, 7.2, 1.3.
- The 6→7 migration: Task 3.2.
- End-to-end, docs, the writer guard, and the walkthrough: Tasks 8.1–8.3.

I found no scope creep. Every task traces to the slice design, and the "no additions beyond the LLD" rule is respected.

### [PASS] Sequencing, commit cadence and proportionality fit the slice

Dependencies run in a single line with no cycles. Migration 007 grows in place across 3.1 and 6.3. The 6.1 → 6.2 → 6.3 → 6.4 handoffs say where failures are expected, so nothing gets committed red. Commits come at about every second task rather than at the end. The split into two files at the Section 4/5 boundary suits roughly 30 tasks. The referenced test paths exist, including `tests/inbox/test_listings.py`.

The slice design states no load-test NFR, so no `tests/load/` or CI-gating task is needed.

### Run Digest

- Response length: 6007 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 11
- Tokens — prompt / cached / cache write / completion / reasoning: 478300 / 376077 / 102211 / 6899 / not computed
- Duration: 55.4 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
