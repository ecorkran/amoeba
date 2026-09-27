---
docType: review
layer: project
reviewType: tasks
slice: findings-verdicts-and-provenance
targetKind: slice
rulesSource: project
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-1.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 97dba6df5a047aebc30aec91d39d05e033bac162
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "Mapping-layer \"raise on unknown enum\" is tested for only one of four enum columns"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-1.md:199-216"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Success criteria cross-reference cleanly onto tasks (Sections 1–5)"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-1.md"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Sequencing mirrors the LLD's Development Approach, no cycles"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-1.md:440-448"
  - id: F004
    severity: note
    category: test-coverage
    summary: "Section 3's test task covers two implementation tasks at once"
    location: "project-documents/user/tasks/104-tasks.findings-verdicts-and-provenance-1.md:157-216"
  - id: F005
    severity: note
    category: completeness
    summary: "No load-test / NFR criterion applies to this slice"
    location: "project-documents/user/slices/104-slice.findings-verdicts-and-provenance.md"
---

# Review: tasks — slice 104

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] Mapping-layer "raise on unknown enum" is tested for only one of four enum columns

The slice design states plainly for `mapping_evidence.py`: "An unknown enum value in a row **raises**. It is never defaulted or skipped" (slice design, Architecture § Component Structure, and repeated in Technical Decisions). Task 3.2 (line 188) restates this as a general rule across the mapping module, which touches four enum-typed columns: `verdict`, `derivation` (verdicts table), and `severity`, plus the implicit `source`/`upstream`-adjacent enum handling. But Task 3.3's only enum-failure test (line 208) is: "Assert a row with an unknown `derivation` (written with raw SQL in the test) makes the mapping raise." `verdict` and `severity` are never exercised with a bad value.

This matters specifically because of this project's stated principle ("Never use silent fallback values. Fail explicitly with errors...", CLAUDE.md). A mapping module that correctly raises on bad `derivation` but silently defaults or crashes differently on bad `severity` or `verdict` is exactly the class of bug that principle exists to catch, and nothing here would catch it. Unless Task 3.2 explicitly funnels every enum column through one shared parse-or-raise helper (the task doesn't say it does), the single `derivation` case is not representative of the other three.

Fix: either (a) add one raw-SQL bad-row case per enum column (`verdict`, `severity`, and any enum on `finding_observations`) to Task 3.3's success criteria, or (b) if Task 3.2 is changed to route every enum column through one shared helper, state that explicitly in Task 3.2's steps so a single test is provably sufficient.

### [PASS] Success criteria cross-reference cleanly onto tasks (Sections 1–5)

Every Functional Requirement bullet in the slice design that belongs to Sections 1–5 has a corresponding task: content-keyed matching and the rewording limit (Task 1.3), trust-label rows (Task 2.2), the 4→5 upgrade (Task 3.3), every `record_verdict` check including the retry/WARNING rule and the `upstream_version` guard (Tasks 4.1–4.2), and `finding_changes` including the provider-failure-skipped-as-previous-round case (Task 5.2). No task in this file traces to nothing in the design — I didn't find scope creep.

### [PASS] Sequencing mirrors the LLD's Development Approach, no cycles

The slice design's Implementation Notes § Development Approach lists a 7-step build order; Sections 1–5 here map onto that order's first four steps (with step 3 split across Sections 3 and 4 for task-sizing reasons). The dependency chain is a straight line (1.1→1.2→1.3→2.1→2.2→3.1→3.2→3.3→4.1→4.2→4.3→4.4→5.1→5.2) with no cycles, and it matches the design's own instruction to "test each step right after building it" rather than being an arbitrary artifact of the breakdown.

### [NOTE] Section 3's test task covers two implementation tasks at once

Task 3.3 is the test-with task for both Task 3.1 (migration/SQL) and Task 3.2 (mapping), rather than each implementation task getting its own immediately-following test task. This is defensible — the schema alone isn't meaningfully testable without the mapping code, and mapping isn't testable without the schema — but it's a deviation from the strict test-immediately-after-impl pattern used everywhere else in this file (1.2→1.3, 2.1→2.2, 4.1→4.2, 4.3→4.4, 5.1→5.2). No action needed, just flagging it as the one place the pattern isn't 1:1.

### [NOTE] No load-test / NFR criterion applies to this slice

The slice design restates no performance NFRs — `finding_changes` is explicitly scoped as comparing "a handful of rows" for one node/review-type. No load test task is warranted in `tests/load/`, and none is present. This is correct, not a gap.

## Response

- **F001 (CONCERN, accepted):** Task 3.3 tested only `derivation` against a bad enum value, not `verdict` or `severity`. Added two more raw-SQL bad-row cases (unknown `verdict`, unknown `severity`) to Task 3.3's steps and success criteria, so all three enum columns are independently proven to raise.
- F002, F003 (PASS): no action needed.
- F004, F005 (NOTE): no action needed, reasoning in the finding stands.

### Run Digest

- Response length: 5077 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
