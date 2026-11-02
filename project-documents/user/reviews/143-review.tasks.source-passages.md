---
docType: review
layer: project
reviewType: tasks
slice: source-passages
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/143-tasks.source-passages.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261102
dateUpdated: 20261102
reviewedSha: d6ffe8a6f2deaeb9ecb22962d081a352442eb95d
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 108519
cachedTokens: 11198
cacheWriteTokens: 97317
completionTokens: 4752
durationSeconds: 41.5
costUsd: 0.438754
costBasis: provider
runId: run-20261102-p5-b4493a64
squadronVersion: 0.24.13
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 4.2 depends on layout rows that are not defined until Task 6.1"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:125-128"
  - id: F002
    severity: concern
    category: prompt-hygiene
    summary: "Task 8.1 puts a hardcoded version next to a retrieval instruction"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:247"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "The unreadable-date failure path in Task 6.5 has no test in Task 6.6"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:203-210"
  - id: F004
    severity: note
    category: dependencies
    summary: "Task file lists 142 as a dependency; the slice design does not"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:6-8"
  - id: F005
    severity: note
    category: proportionality
    summary: "Task 4.4 restates slice design D7 in detail"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:135-140"
  - id: F006
    severity: pass
    category: coverage
    summary: "Success-criteria coverage"
    location: "project-documents/user/tasks/143-tasks.source-passages.md"
  - id: F007
    severity: pass
    category: structure
    summary: "Sequencing, sizing, test-with pattern and commit markers"
    location: "project-documents/user/tasks/143-tasks.source-passages.md"
---

# Review: tasks — slice 143

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 4.2 depends on layout rows that are not defined until Task 6.1

Task 4.2 tests `select_plan_files` for "all six rows for slice 132". The rows (`PlanRow` values) are defined in `source_reads.py` in Task 6.1, which comes two sections later. Task 4.1 says the rows "are passed in, not spelled here", so the 4.2 tests can only hand-write the six rows or import from a module that doesn't exist yet.

A hand-written copy would break the slice's own rule that "No other module spells a directory or file-name pattern". It would also let the tests drift from the real layout constants. Either:
- move 6.1 (constants only, no I/O) ahead of 4.2, or
- have 4.2 use a small synthetic `PlanRow` set to test selection logic, and let 6.4 assert the real rows against the fixture repository.

### [CONCERN] Task 8.1 puts a hardcoded version next to a retrieval instruction

The step reads `"observed on CF 0.19.24" (verify the version with cf --version and record what it prints...)`. If `cf --version` returns nothing, an implementer will reach for the literal `0.19.24`. This is the hallucination trap the project guidelines describe. Rewrite it so the version comes only from the `cf --version` output, and stop with an error if the command prints nothing. Don't give an example value in the same step.

### [CONCERN] The unreadable-date failure path in Task 6.5 has no test in Task 6.6

Task 6.5 requires that a failed `log` read, or an empty or unparseable date, return `sources_unreadable` "never a fallback" (slice design D5). Task 4.5 tests `parse_git_date` returning `None`. Task 6.6 tests a failing `show` and a non-UTF-8 file, but no case makes the date read fail or return garbage. The "never falls back to commit date or now" guarantee is therefore unproven at the point where it matters. Add one `run`-wrapper case to 6.6 that makes the `log` for one file's date fail or return a blank or garbage line, and assert `sources_unreadable`.

### [NOTE] Task file lists 142 as a dependency; the slice design does not

The slice design says 142 is not a dependency, and its frontmatter lists only 141. The task file lists `141` and `142`, and `projectState` says 142 is merged and `AnswererSettings` already holds `answer_limit` and `reserved_terms`. This is consistent with the code state and the task list handles it correctly (5.1 and 5.2 add two keys to the existing model). No action is needed beyond being aware of the difference.

### [NOTE] Task 4.4 restates slice design D7 in detail

The file says it "does not restate the LLD", yet 4.4 spells out the PM-answer ordering, the first-misfit drop rule and the numbering. This is harmless, since it matches D7, but it creates a second place to keep in sync. Consider pointing at D7 and keeping only what the implementer must not miss.

### [PASS] Success-criteria coverage

Every functional and technical requirement maps to a task:
- **Committed-only reads, dates, and the order for slice 132:** 6.4, 6.6, 7.3.
- **Missing slice plan, missing design or tasks, unmatched rules entry:** 6.4.
- **PM and answerer filtering:** 7.3.
- **`sources_too_large` and PM trimming:** 4.5, plus the early stop in 6.6.
- **Citation cases:** 4.7.
- **Config load errors and `[]`:** 5.2.
- **Allowlist, `git_read_only_place`, purity:** 2.3, 3.4.
- **Budget refusal at every N, the `2 + L + 2F` call count, failing `show`, non-UTF-8 file, root-level entry:** 6.4, 6.6.
- **Render comparison:** 4.5.
- **Docs and docstring:** 2.1, 8.1.

I found no scope creep. The extra items are the `parse_git_date` and `format_utc` helpers and the end-to-end fixture, and both trace to D5 and the walkthrough.

### [PASS] Sequencing, sizing, test-with pattern and commit markers

Apart from the 4.2/6.1 issue above, dependencies run forward with no cycles. Section 5 (config) precedes section 7, which uses it, and section 6 takes `max_chars` as a parameter, so it doesn't depend on 5.

Tests follow their implementations. The only separation is 4.3 and 4.4 being tested together in 4.5, which is acceptable. Commit markers sit at working, tested points: after the git reads, after the pure module, after config, after the source reads, after the entry point, and after docs. There are no per-task commits and no merge or push tasks.

The size fits one task file. No NFR is restated in the slice design, so no load-test or CI wiring task is needed.

### Run Digest

- Response length: 5345 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 108519 / 11198 / 97317 / 4752 / not computed
- Duration: 41.5 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Resolution (20261102)

- **F001 — resolved.** Task 4.2 now tests selection over a small synthetic `PlanRow` set built in the test, so it spells no real layout and does not need Task 6.1. Task 6.4 checks the real rows against the fixture repository.
- **F002 — resolved.** Task 8.1 now takes the version only from what `cf --version` prints, with today's date, and stops with an error if the command prints nothing. The example value is gone.
- **F003 — resolved.** Task 6.6 gains a case where the date read exits non-zero, returns an empty line and returns a garbage line; each must give `sources_unreadable` with no fallback date.
- **F004 — no change.** The review finds the task file consistent with the code state. 142 is merged, and its keys are already on `AnswererSettings`.
- **F005 — no change.** A proportionality note only; the detail in 4.4 is accurate and costs nothing.
