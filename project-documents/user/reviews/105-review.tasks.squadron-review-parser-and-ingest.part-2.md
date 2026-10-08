---
docType: review
layer: project
reviewType: tasks
slice: squadron-review-parser-and-ingest
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: 09bac3db0e57a00b11f0c97aa0f222f08bef0dd4
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
durationSeconds: 38.1
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete across both task files"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md"
  - id: F002
    severity: pass
    category: nfr
    summary: "No load-test or CI-gating task is needed"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:370"
  - id: F003
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit distribution are sound"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:21-321"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Task 8.5 forward-references Task 8.6 for seeding a node"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:234"
  - id: F005
    severity: concern
    category: scope
    summary: "Task 8.6 omits the shared harness module from its file list"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:255-262"
  - id: F006
    severity: concern
    category: spec-consistency
    summary: "Ingest's stderr message format is not pinned and may not match the walkthrough"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:173"
  - id: F007
    severity: note
    category: sequencing
    summary: "Task 8.2 commits an interim stub that always refuses"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:176"
  - id: F008
    severity: note
    category: clarity
    summary: "Task 7.2 refers to \"Task 7.2's harness change\" from inside Task 7.2"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:91"
  - id: F009
    severity: note
    category: clarity
    summary: "Task numbering uses \"8.6b\""
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:266"
---

# Review: tasks — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage is complete across both task files

Each LLD criterion maps to a task:
- **Parser, record id, version rule (file 1):** Tasks 3.5, 4.2, 5.2 and 5.4.
- **`provider_failure_problem`:** Tasks 2.2 and 2.3.
- **Round trip:** Task 6.2.
- **Test migration:** Tasks 7.1–7.4. `test_finding_changes.py` is handled conditionally in 7.2.
- **Ingest failure paths, with the process running and stopped:** Tasks 8.3 and 8.7.
- **Ingest success path, D5 and D7:** Tasks 8.5, 8.6b and 8.8.
- **Docs:** Tasks 9.1 and 9.2.
- **Walkthrough:** Task 9.3.
- **Import rules and key-defined-once:** Task 5.5.

Nothing is missing. The extra tasks (exit-code uniqueness in 8.1, the stale-LLD report in 9.3) are small and trace to the LLD.

### [PASS] No load-test or CI-gating task is needed

The slice restates no NFR. Task 9.3 says so and runs `tests/load` only as a regression check.

### [PASS] Sequencing, test-with pattern and commit distribution are sound

Each implementation task is committed with its immediately following test task (6.1/6.2, 8.2/8.3, 8.4/8.5). Commits are spread across Sections 6–9, and no dependency is circular.
- The Section 7 migration tasks are independent of Section 6.
- Task 7.4 waits on all three migrations before deleting the old reader.
- The externally gated pair (Task 1.2) is isolated to Task 8.8 and checked in Task 9.3.

### [CONCERN] Task 8.5 forward-references Task 8.6 for seeding a node

The D7 step in Task 8.5 says to seed a node with `scripts/demo_evidence.py` "as in Task 8.6". Task 8.6 comes later, so a junior reading in order has no seeding instructions yet. The 8.3 fixture creates only the project and its store, with no node.
- The assertions are all about the inbox file and stderr, and the process is stopped, so nothing is applied and no node is needed.
- Either drop the seeding from 8.5, or state the seeding step inline there and say how it fits the fixture.

### [CONCERN] Task 8.6 omits the shared harness module from its file list

Task 8.6 creates `tests/cli/ingest_e2e_harness.py` in its steps, but "Files to Create" lists only `tests/cli/test_ingest_end_to_end.py`. Tasks 8.6b, 8.7 and 8.8 depend on the harness. Add it to the file list. Its shared-helper surface (setup, post-restart state) is also left implicit, and Task 8.6 is already effort 3.

### [CONCERN] Ingest's stderr message format is not pinned and may not match the walkthrough

Task 8.2 only says "print the error on stderr". The LLD walkthrough (step 6) expects `SquadronParseError: … no frontmatter`, with the class name prefix. Task 8.3 asserts only that the message "mentions" the problem. Specify in 8.2 whether the exception class name is included, so Task 9.3's walkthrough doesn't fail on formatting alone.

### [NOTE] Task 8.2 commits an interim stub that always refuses

The `TODO(8.4)` stub returns `SUBMISSION_REFUSED`, and the commit message for 8.2/8.3 says "read and parse reviews". The stub is guarded well: it never returns `OK` and is never asserted as success. The command is still not usable between the 8.2/8.3 commit and the 8.4/8.5 commit, which is acceptable on a slice branch.

### [NOTE] Task 7.2 refers to "Task 7.2's harness change" from inside Task 7.2

The conditional about `test_finding_changes.py` reads as self-referential. Rephrase it as "after this task's harness change".

### [NOTE] Task numbering uses "8.6b"

The split is reasonable for size, and the references to it are consistent. Renumbering is optional.

### Run Digest

- Response length: 4809 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 38.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
