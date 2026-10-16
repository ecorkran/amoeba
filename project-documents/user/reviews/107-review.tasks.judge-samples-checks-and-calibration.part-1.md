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
reviewedSha: e1d46dc185b3fd5378bdcf7c50965a0aa5091a1c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 381469
cachedTokens: 278302
cacheWriteTokens: 103157
completionTokens: 5122
durationSeconds: 42.0
costUsd: 0.49237
costBasis: provider
runId: run-20261016-p56-6f6dfbbb
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: hallucination-trap
    summary: "Task 5.2 points the junior at metrology strings the LLD does not contain"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:54"
  - id: F002
    severity: concern
    category: sequencing
    summary: "A PM-gated capture blocks the whole task chain"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:54-70"
  - id: F003
    severity: note
    category: task-sizing
    summary: "Task 3.4 combines implementation and tests"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:260-279"
  - id: F004
    severity: note
    category: proportionality
    summary: "Some steps carry more ceremony than the criteria need"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-2.md:136"
  - id: F005
    severity: note
    category: spec-consistency
    summary: "The LLD says \"two new kinds\" in the invariant test, but D9 defines one"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:351"
  - id: F006
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Sequencing and commit cadence are sound"
    location: "project-documents/user/tasks/107-tasks.judge-samples-checks-and-calibration-1.md:25"
---

# Review: tasks — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 5.2 points the junior at metrology strings the LLD does not contain

The no-metrology test step says to "take the two strings from the LLD and the 104 notes". The LLD names neither the directory nor the config key. It only says "Squadron's metrology directory or config key" (Functional Requirements, bullet 6). The notes and architecture mention `metrology/graduation.py` and `metrology.min_evidence_n`, but only as scattered prose from Squadron. The step does say to ask the PM if the key can't be found, which limits the damage. Even so, a junior is likely to pick the nearest plausible token, such as the literal word "metrology". The project's own rule on hallucination traps warns against exactly this. Name the exact strings in the task, or add a PM question at the start of Section 5 or in Task 1.2. The notes file `user/notes/002-upstream-delta.amoeba.md:121` is the likely source.

### [CONCERN] A PM-gated capture blocks the whole task chain

Task 1.2 needs a PM-run pipeline capture, and Task 2.1 depends on Task 1.5, which depends on that capture. Sections 2–5 (check models, migration, checks, judge-sample field and consistency, calibration) don't use the fixtures at all. If the capture is late, the whole implementation stalls. Either have the PM capture before the work starts, or let Sections 2–4 depend only on Task 1.1 and defer the fixture-dependent Tasks 1.3–1.5 and Task 7.2. The task file already says Section 8 uses the fixture names from Tasks 1.2 and 1.5, so the dependency is real only for those tasks.

### [NOTE] Task 3.4 combines implementation and tests

Task 3.4 adds `CheckOperations` and also holds the full `test_checks.py` suite plus the progress tests (effort 4). Other sections split these into separate implementation and test tasks. Task 3.3 (the writer) is also tested only through 3.4. This stays within the test-with pattern because they share a commit, but 3.4 is the largest task in this file. Splitting it into "add `CheckOperations`" and "test checks and progress" would be more consistent. It isn't required.

### [NOTE] Some steps carry more ceremony than the criteria need

Two steps go beyond the success criteria:
- **Task 6.4:** it asks the junior to prove the invariant test fails by running it against a throwaway migration copy missing the trigger. The LLD criterion "fails if either trigger is missing" is better served by the invariant test itself.
- **Task 5.2:** it adds a separate test asserting the row type's field names equal the D3 list.

Both are small. Trim them if the task file needs to be lighter.

### [NOTE] The LLD says "two new kinds" in the invariant test, but D9 defines one

Technical Requirements say the feed invariant test passes "with the two new kinds in its sequence". D9 and the task breakdown (Tasks 6.3–6.4) add only `check_recorded`, with no progress trigger. The tasks follow D9, which is correct. The LLD wording should be corrected so a reviewer doesn't read Task 6.4 as a gap.

### [PASS] Success-criteria coverage is complete

Every Functional and Technical Requirement maps to a task:
- **Samples and invocations:** samples, the D2 consistency check and the previous-round skip are covered by 4.1–4.6. Ingest under `j1`/`j2` is covered by 7.1–7.2.
- **Calibration:** 5.1–5.2, including the no-write and no-metrology tests.
- **Checks:** standing in 2.1–2.2, rejection and retry in 3.3–3.4 and 6.2, the feed change in 6.3–6.4, and the 6→7 upgrade in 3.2.
- **D4 refusal:** the real-fixture parse in 1.3, the refusal itself in 1.4–1.5, and exit 12 in 1.5 and 8.1.
- **Surface and wrap-up:** the `check` kind and `submit check` in 6.1–6.2, listings in 7.3–7.5, end-to-end in 8.1, docs in 8.2, and validation plus the walkthrough in 8.3.
- **Progress records:** write-only `record_progress` and its no-feed-change check are in 3.4 and 6.4.

No task falls outside a criterion. No NFR is restated, so no load test or CI gate is needed.

### [PASS] Sequencing and commit cadence are sound

There are no circular dependencies. Intermediate-failure states are called out explicitly:
- 6.1 and 6.3 note that the completeness and invariant tests fail until 6.2 and 6.4.
- Migration 007 is extended in place and never split into an 008.
- Each implementation task commits together with its test task, and commits fall at the end of every section.

### Run Digest

- Response length: 5478 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 381469 / 278302 / 103157 / 5122 / not computed
- Duration: 42.0 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
