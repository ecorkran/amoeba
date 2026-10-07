---
docType: review
layer: project
reviewType: tasks
slice: squadron-review-parser-and-ingest
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 84d710f653b37956a71877572e68d3073ad5e4c8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 35.7
runId: run-20261007-tasks-plan-25f0a00a
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: coverage-gap
    summary: "README \"known gap\" entry is not assigned to any task"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:388"
  - id: F002
    severity: concern
    category: coverage-gap
    summary: "The edited-copy fixture is never created by a task"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:227"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 3.2 is too large for one junior task"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:191-213"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "Missing negative tests for a finding without `severity` or `summary`"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:228"
  - id: F005
    severity: concern
    category: sequencing
    summary: "Two implementation tasks run back to back before their tests"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:287-325"
  - id: F006
    severity: concern
    category: specification-clarity
    summary: "Vague or conditional constants in Task 2.4"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:154-158"
  - id: F007
    severity: note
    category: specification-clarity
    summary: "Some fixture references are under-specified"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:271"
  - id: F008
    severity: note
    category: sequencing
    summary: "Task 2.1's dependency on Task 1.2 is artificial"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:94"
  - id: F009
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for Sections 1–5"
    location: "project-documents/user/slices/105-slice.squadron-review-parser-and-ingest.md:354-390"
  - id: F010
    severity: pass
    category: robustness
    summary: "Safeguards against hallucinated inputs"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-1.md:76"
---

# Review: tasks — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] README "known gap" entry is not assigned to any task

The LLD says the README records that no real *Findings Not Parsed* + CONCERNS/FAIL file exists, and labels the edited copy as edited. Task 1.1 adds README entries only for the four copied files. Task 3.3 says "add the label to the README if Task 1.1 did not", and a conditional step like that is easy to skip. Nothing records the "missing" note at all. Add an explicit README step, in Task 1.1 or 3.3, for the known-gap note and the edited-copy label.

### [CONCERN] The edited-copy fixture is never created by a task

Task 3.3 describes "a copy of a real CONCERNS file with the *Findings Not Parsed* heading added". The README is meant to label it as edited, which implies a committed fixture. It is unclear whether the copy is a file in `tests/fixtures/sq_reviews/` or is built in the test at runtime. Neither Section 1 nor Task 3.3 lists it under Files to Create. Also, a hand-edited file inside a directory the other tasks treat as byte-for-byte real input blurs that boundary. Decide where it lives (a test-built copy is simplest) and state it.

### [CONCERN] Task 3.2 is too large for one junior task

Task 3.2 bundles five jobs:
- frontmatter splitting
- safe YAML loading
- body heading scan
- the full D3 field mapping, with optional/required rules
- finding mapping and the `provider_failure_problem` call

Its effort is 4, and it has no intermediate checkpoint or commit. Task 4.1 needs the finding mapper from it as a shared helper. Consider splitting it into "frontmatter and headings extraction" and "field and finding mapping", with the finding mapper as its own function from the start. That would also avoid the refactor Task 4.1 anticipates.

### [CONCERN] Missing negative tests for a finding without `severity` or `summary`

Task 3.2 and D3 require a finding to have `severity` and `summary`. The LLD's "Nothing is defaulted" list names "lacks `severity` or `summary`". Task 3.3's error cases test only "finding that is not a mapping" and "unknown severity". Add one case each for a missing `severity` and a missing `summary`. The same applies to Task 4.2 for stdout findings.

### [CONCERN] Two implementation tasks run back to back before their tests

Tasks 5.1 and 5.2 both land before Task 5.3, which tests both. The same happens in Tasks 3.1 and 3.2 before Task 3.3, and Tasks 4.1 and 4.2 are correctly paired. Task 5.1 (`review_record_id`) is pure and could be tested immediately: stability, enum-by-value, and hand-edit invariance. Consider moving those tests into 5.1 and keeping D4 and the import rules in 5.3. This is a mild departure from the test-with pattern, not a defect. Commits do land at 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 3.3, 4.2 and 5.3, which is acceptably distributed.

### [CONCERN] Vague or conditional constants in Task 2.4

Task 2.4 says to define the `stated` / `derived` literals "if the parser compares them". D3's `findings_parsed` rule compares against `stated` and `not_reported`, so the parser does compare, and `not_reported` is also the default. The condition should be removed and the literals named: `stated`, `not_reported`, and any others. Otherwise a junior may skip them and inline the strings in Task 4.1, which breaks the single-definition rule. The `unverified` literal is passed through, so no constant is needed there.

### [NOTE] Some fixture references are under-specified

Task 4.2 refers to "the clean PASS", "the CONCERNS capture", and "the 0.14.0 captures" without naming files. These are existing fixtures from 104, and the junior must infer which file is which. Naming them (they are in `tests/review_fixtures.py` or `tests/fixtures/sq_reviews/`) would remove the guesswork. Task 3.3 has the same issue with "a real CONCERNS file".

### [NOTE] Task 2.1's dependency on Task 1.2 is artificial

PyYAML's move has no technical dependency on the fixture capture. The ordering is harmless, and it keeps the capture, which may block on the PM, out of the later critical path. It is only worth noting.

### [PASS] Success-criteria coverage for Sections 1–5

Each of these maps to a task with no scope creep:
- Fixtures: 1.1 and 1.2.
- `provider_failure_problem` as the single definition of the rule: 2.2 and 2.3.
- `review_fields.py`: 2.4.
- Reader behavior, including both provider-failure files, *Findings Not Parsed*, the PR review, the 0.15.0 stamp, and the error list: 3.3.
- `fallback_used` rules, `requested_model` handling, trailing stdout text, and the file/stdout key equality on the new pair: 4.1 and 4.2.
- Digest-id invariance, D4 and the import-direction test: 5.1 to 5.3.

The remaining criteria (round trip, test migration, ingest, end-to-end, docs) are covered in part 2.

### [PASS] Safeguards against hallucinated inputs

Task 1.2 stops and asks the PM rather than hand-building a pair if `sq` or a provider key is unavailable. Task 1.1 checks each fixture for hand edits and verifies the expected frontmatter before copying. Task 3.1 stops rather than adding `RecordSource` strings. This is consistent with the project rule against fabricated values.

### Run Digest

- Response length: 6756 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 35.7 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
