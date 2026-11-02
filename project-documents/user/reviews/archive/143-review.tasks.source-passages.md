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
reviewedSha: 6ab70026f94c3f004922641efa5eb749363b542b
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 108564
cachedTokens: 11198
cacheWriteTokens: 97362
completionTokens: 4140
durationSeconds: 40.4
costUsd: 0.432814
costBasis: provider
runId: run-20261102-p5-b4493a64
squadronVersion: 0.24.13
findings:
  - id: F001
    severity: concern
    category: task-sizing
    summary: "Tasks 6.2 and 6.4 are oversized and bundle several separable behaviours"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:185-210"
  - id: F002
    severity: note
    category: test-clarity
    summary: "Property test scope is ambiguous about which fixtures directory"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:110"
  - id: F003
    severity: note
    category: proportionality
    summary: "Task 6.2 and Task 4.1 restate LLD detail despite the file's own \"does not restate the LLD\" rule"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:121-122, 187-193"
  - id: F004
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/143-tasks.source-passages.md"
  - id: F005
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern are sound"
    location: "project-documents/user/tasks/143-tasks.source-passages.md"
  - id: F006
    severity: pass
    category: scope
    summary: "No scope creep; proportionality is acceptable"
    location: "project-documents/user/tasks/143-tasks.source-passages.md"
---

# Review: tasks — slice 143

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Tasks 6.2 and 6.4 are oversized and bundle several separable behaviours

Task 6.2 has nine sub-items. It covers the commit pin, directory listings, rules and plan selection, de-duplication, per-file date and text reads, four distinct problem kinds, the `UnicodeDecodeError` catch, the running size total with early stop, and date validation. It sits in one checklist item with no tests until Task 6.3 and Task 6.4, so the error paths are only exercised after all of it is written. Task 6.4 is the matching test task and has nine bullets, including per-N budget refusal, call-count arithmetic and a mid-run commit wrapper.

The slice design's own development approach already treats "fixture helper, then `source_reads.py` with the git-backed tests" as one unit. The tasks could still be split at a natural seam:

- 6.2a: resolve the commit, list directories, select files and de-duplicate, then test it (missing entry, missing slice plan, root-level entry, pinned commit, uncommitted edits ignored).
- 6.2b: per-file date and text reads, the non-UTF-8 catch, the size early stop and the budget behaviour, then test it (failing `show`, non-UTF-8, early stop, budget refusal and call count).

Task 6.3 (the fixture repo helper) would move ahead of both. This keeps the test-with pattern and gives the junior implementer smaller targets. The single `**Commit**:` marker at the end of Section 6 can stay. Moving the helper earlier is the only reordering.

### [NOTE] Property test scope is ambiguous about which fixtures directory

Task 3.4 says "for every file under the fixtures directory". Task 4.5 and Task 7.3 later add `fixtures/expected_passages.md` and `fixtures/expected_end_to_end.md` next to `fixtures/sources/`. If the property test walks `fixtures/`, it will pick up those expected-output files. Their text would not necessarily satisfy "each passage after the first starts with a heading line" or the join-gives-back-the-file expectation, and it makes the test depend on later tasks. Scope it explicitly to `fixtures/sources/`.

### [NOTE] Task 6.2 and Task 4.1 restate LLD detail despite the file's own "does not restate the LLD" rule

The header says the file does not restate the LLD. Task 4.1 (regex construction with escaped parts) and Task 6.2 (step list, error mapping) re-describe D2, D7 and D10. This is not wrong, because the steps are consistent with the design. If the design changes, though, there are two places to update. Trimming these to a "per LLD D2/D7/D10" reference plus the task-specific decisions would reduce drift risk. This needs no action to proceed.

### [PASS] Success-criteria coverage is complete

Each functional and technical criterion maps to a task:
- **Committed-only reads, pinned commit, order of slice-132 files, dates:** Task 6.4.
- **`sources_missing`, unmatched rules entry, no design or tasks:** Task 6.4.
- **Answerer and blank-answer exclusion:** Task 7.3.
- **Size limit, PM trimming and first-misfit rule:** Tasks 4.4 and 4.5, plus the early stop in Task 6.4.
- **Citation check:** Tasks 4.6 and 4.7.
- **Config keys and load errors:** Tasks 5.1 and 5.2.
- **Allowlist and `test_git_read_only_place.py`:** Task 2.3.
- **Purity check:** Task 3.4.
- **Budget refusal at every N and the `2 + L + 2F` call count:** Task 6.4.
- **Non-UTF-8 file, failing `show`, root-level entry:** Task 6.4.
- **Rendered output against an expected file:** Task 4.5.
- **Process-contract docs and the `git_read` docstring:** Tasks 2.1 and 8.1.

The slice states no NFR, so no `tests/load/` task or CI gating task is required.

### [PASS] Sequencing and test-with pattern are sound

Dependencies run forward with no cycles:
- `PlanRow` is defined in `passages.py` (Task 4.1) and filled by `source_reads.py` (Task 6.1).
- The fixtures (Task 3.3) precede the tests that use them.
- The config keys (Task 5) precede `assemble_sources` (Task 7), which consumes `AnswererSettings`.

Each implementation task is followed by its tests: 2.1–2.2 by 2.3, 3.2 by 3.4, 4.1 by 4.2, 4.3–4.4 by 4.5, and 4.6 by 4.7. Task 5.1 includes updating the existing fixtures so the suite stays green. The seven `**Commit**:` markers sit at working, tested points and are plain lines.

### [PASS] No scope creep; proportionality is acceptable

Every task traces to a design decision or success criterion. There is no store write, decline mapping or caller wiring, which the design excludes. Test tasks map to listed criteria, and the single task file matches a slice sized at effort 2 with several components. Task 1.1 is a baseline task that the branch rules require.

### Run Digest

- Response length: 5380 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 108564 / 11198 / 97362 / 4140 / not computed
- Duration: 40.4 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
