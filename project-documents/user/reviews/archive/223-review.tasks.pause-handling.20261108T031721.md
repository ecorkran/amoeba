---
docType: review
layer: project
reviewType: tasks
slice: pause-handling
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/223-tasks.pause-handling.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 474e4f0ff917f6d8916bc326d55752714e23e8df
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 118527
cachedTokens: 11198
cacheWriteTokens: 107325
completionTokens: 7117
durationSeconds: 56.1
costUsd: 0.50244
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md"
  - id: F002
    severity: concern
    category: sequencing
    summary: "`deps` is defined after the task that consumes it, and the import would be circular"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:247"
  - id: F003
    severity: concern
    category: source-control
    summary: "Final commit marker would commit only notes and check-offs"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:335"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Test in 5.8 depends on behavior built in 7.4"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:219"
  - id: F005
    severity: concern
    category: completeness
    summary: "Adding required config keys will break existing configs and fixtures"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:195-198"
  - id: F006
    severity: concern
    category: task-sizing
    summary: "Task 4.2 is too large"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:170-177"
  - id: F007
    severity: concern
    category: sequencing
    summary: "The pause pipeline is created twice, and the second creation comes later"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:115"
  - id: F008
    severity: concern
    category: code-structure
    summary: "`handle_pause.py` is likely to exceed the ~300-line guideline"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:245-274"
  - id: F009
    severity: note
    category: clarity
    summary: "Ambiguous reference to where `AnsweringEvidence` lives"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md:72"
  - id: F010
    severity: note
    category: test-with-pattern
    summary: "Test placement and commit markers are otherwise sound"
    location: "project-documents/user/tasks/223-tasks.pause-handling.md"
---

# Review: tasks — slice 223

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage is complete

Each slice criterion traces to tasks:
- Real pause answered and resumed: 9.2 and 10.2.
- Barred-then-allowed: 5.8 and 10.2.
- `answer` recorded, resumed and used as precedent: 1.8, 4.3, 7.9 and 10.2.
- The four checks and the `answering.yaml` grep: 3.2 and 10.1.
- The three contract docs: 5.3, 8.3 and 9.1.
- Live tier and restored tests: 9.2 and 9.3.
- The #303 comment: 9.4.

All 11 D3 `SkipReason` values are covered. 7.2 and 7.6 produce them, and 7.3 and 7.7 test them. No task is scope creep, and the slice states no NFR, so no load test or CI gating task is needed.

### [CONCERN] `deps` is defined after the task that consumes it, and the import would be circular

Task 7.1 defines the shared `deps` dataclass in `operations/handle_pause.py`. `resume.resume(..., deps)` is built and tested in task 6, and 5.5, 5.6 and 6.2 inject spawner and poller fakes. Task 6 therefore needs a type that does not exist until task 7.

If `resume.py` imported `deps` from `handle_pause.py` once it exists, that would be circular, because `handle_pause` imports `resume`. `answer.py` would also have to import `handle_pause.py` only for `deps`. Create `deps` in its own module, such as `operations/deps.py`, before task 5.5, and have 5.5, 6.1, 7.1 and 7.8 all reference it.

### [CONCERN] Final commit marker would commit only notes and check-offs

Section 10 is "run the checks" (10.1) and "record walkthrough notes" (10.2). Unless a defect turns up, the `docs: record pause-handling walkthrough results` commit holds only check-offs and notes. Project rules forbid a commit like that. Drop that marker and put a single final marker after section 10, so the section 9 code and the walkthrough notes are committed together. Alternatively, merge sections 9 and 10 under one marker.

### [CONCERN] Test in 5.8 depends on behavior built in 7.4

Task 5.8 includes "`prior` at the limit on first sight inserts `waiting_on_pm` with `answer_limit_reached` and starts nothing". That path is the new-question insert in `handle_pause` (7.4). The settle task (5.7) only counts `prior` inside the settle transaction. Move that case to 7.5, which already tests the new-question path.

### [CONCERN] Adding required config keys will break existing configs and fixtures

Task 5.3 makes `answering_wait_seconds` and `resume_wait_seconds` required with no default. 5.3 lists new tests but not the existing config fixtures, sample configs or 222 tests that currently load a config without these keys. The checks must pass at the section 5 commit marker, so those fixtures need updating. Add a step to 5.3 to update existing fixtures and examples, including the config copied in the walkthrough. 3.4 has a similar gap: changing the `assemble` signature needs the existing `assemble` tests updated.

### [CONCERN] Task 4.2 is too large

Task 4.2 bundles four separate pieces, with a single "module imports" success check:
- slice resolution through `cf` and plan search;
- committed rules and plan reads;
- program passage reads across the concept member's checkout;
- precedent and error mapping.

Split it into slice resolution and then committed/program reads plus precedent. Put 4.3's test cases with each half. 1.6 (insert, three compare-and-set moves, `add_pm_answer`, `record_resume`) and 7.6 (eight D7 rows) are also large. They are cohesive and tested by the next task, so splitting them is optional.

### [CONCERN] The pause pipeline is created twice, and the second creation comes later

Task 2.2 captures a real pause from "a throwaway pipeline that ends on a question". Task 9.2 later creates `tests/live/pause/asks_question.yaml`, which has the same purpose. The walkthrough (10.2) also uses `asks_question.yaml`. Create `asks_question.yaml` once in 2.2 and reuse it in 9.2 and 10.2. 2.2 also never says how to produce the "pause of another checkpoint kind", so a junior may stall there. Say how to produce it, or name a fallback to the `BLOCKED:` line.

### [CONCERN] `handle_pause.py` is likely to exceed the ~300-line guideline

Tasks 7.1 to 7.6 all land in `operations/handle_pause.py`: enums, result models, `deps`, eligibility checks, the new-question path and the D7 table. That will exceed ~300 lines. Moving `deps` out (see the first concern) helps. Also say in 7.4 or 7.6 to put the existing-row and dead-claim logic in its own module, such as `claimed_row.py`, which fits the "Code Structure" guidance.

### [NOTE] Ambiguous reference to where `AnsweringEvidence` lives

Task 1.3 says to define `AnsweringEvidence` "where the design's D10 says". D10 names the type but gives no location. Name the module, keeping the rule that `store` may import only `answering.values` from `answering`.

### [NOTE] Test placement and commit markers are otherwise sound

Tests follow their implementation tasks in most places. The exceptions are 1.5 and 3.1/3.2: the first has no direct tests until 1.7 and 1.8, and the second has the prompt rewrite between code and tests. Both are minor. The commit markers at the ends of sections 1 to 9 each sit at a working, checked state. The single task file is acceptable for effort 5.

### Run Digest

- Response length: 6409 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 118527 / 11198 / 107325 / 7117 / not computed
- Duration: 56.1 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
