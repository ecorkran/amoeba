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
reviewedSha: fbae199af97cea673217422c64abbbdda502397a
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
durationSeconds: 57.8
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 9.1 depends on the pair-dependent Task 8.8, which can stall the docs tasks"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:325-327"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Task 7.4's removal check is too narrow to prove nothing still uses the old helpers"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:129"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "Task 8.5's D7 test cannot exercise a slice mismatch against any node"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:234"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "No end-to-end assertion that the stored verdict id equals the digest id, or that a replay yields one submission"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:256-274"
  - id: F005
    severity: note
    category: sequencing
    summary: "Task 7.3's dependency on Task 6.2 is optional"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:105"
  - id: F006
    severity: note
    category: task-sizing
    summary: "Task 6.1 does not need Task 5.5, and the Task 8.6 module may grow large"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:28"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for Sections 6–9"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:21-380"
  - id: F008
    severity: pass
    category: process
    summary: "Test-with pattern, commit distribution and interim-state safety"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:172-176"
  - id: F009
    severity: pass
    category: nfr
    summary: "No load-test or CI-gating obligation"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:369"
  - id: F010
    severity: pass
    category: feasibility
    summary: "Referenced test helpers exist"
    location: "project-documents/user/tasks/105-tasks.squadron-review-parser-and-ingest-2.md:195"
---

# Review: tasks — slice 105

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 9.1 depends on the pair-dependent Task 8.8, which can stall the docs tasks

Task 1.2 is an external gate (needs `sq`, a provider key, and network). Part 1 says everything that isn't pair-dependent should carry on if it is blocked. Task 8.8 is pair-dependent and is the dependency of Task 9.1, so a blocked 1.2 stalls 9.1, 9.2 and 9.3 through the chain 8.8 → 9.1 → 9.2 → 9.3. Nothing in 9.1 needs 8.8's output: the D5 consequence is documented from the design, not from the test. Make 9.1 depend on Task 8.7 so the docs can proceed. Task 9.3 already checks for any leftover `blocked on 1.2` item.

### [CONCERN] Task 7.4's removal check is too narrow to prove nothing still uses the old helpers

The step greps only `review_findings\|read_frontmatter` under `tests/`. The helpers being deleted also include `CapturedFinding` and `has_provider_failure_heading`, and Tasks 7.1–7.3 list all four as removed. A repo-wide grep shows exactly five Python files reference these names or `review_fixtures`: `tests/review_fixtures.py`, `tests/test_demo_evidence_payloads.py`, `tests/store/test_finding_identity.py`, `tests/store/test_finding_changes.py` and `tests/evidence_harness.py`. That matches the task coverage, but the grep should name all four helpers. Running the full suite once is the real safety net, and it is already a step.

### [CONCERN] Task 8.5's D7 test cannot exercise a slice mismatch against any node

Task 8.5 runs on the Task 8.3 fixture, which has a project store and no nodes. "A review whose `slice` differs from any node's slice name" is therefore trivially true there, and ingest opens no store anyway, so the test proves little. D7 only matters when a node exists whose `cf.slice_name` differs from the review's slice. The Task 8.6 end-to-end setup already seeds a demo node and ingests the 102 reviews onto it. Add an explicit assertion there (or in 8.6b) that the verdict is applied to a node whose slice name differs from the review's `slice`. Keep the 8.5 check as the stderr-output check it effectively is.

### [CONCERN] No end-to-end assertion that the stored verdict id equals the digest id, or that a replay yields one submission

The slice's Functional Requirements say a real-file ingest "produces one verdict whose id is the digest id", and a second ingest produces no second record. Walkthrough step 5 also expects `inspect submissions` to show one submission under that id. Task 8.6 asserts three verdicts and their standings, and Task 8.6b asserts `source_path` and `source`. Neither asserts that the stored `id` equals `review_record_id(parse_review_artifact(...))`, or that the replayed ingest left a single submission row. Add both assertions to 8.6b. They are cheap and they pin the cross-process id invariant that slice 106 depends on.

### [NOTE] Task 7.3's dependency on Task 6.2 is optional

The dependency line says the test "may use `verdict_to_payload`", which is a soft dependency written as a hard one. Task 7.1 is marked "independent of Section 6". Decide whether 7.3 uses the inverse. If it does, say so in the steps. If it doesn't, drop the dependency so a junior doesn't have to guess.

### [NOTE] Task 6.1 does not need Task 5.5, and the Task 8.6 module may grow large

Task 6.1 depends on 5.5, but it only needs 104's payload module. The dependency is harmless serialization, and only Task 6.2 needs the composition from 5.4. Separately, `tests/cli/test_ingest_end_to_end.py` accumulates Tasks 8.6, 8.6b, 8.7 and 8.8 in one module with shared helpers. A reminder to split the helpers into a harness module if it nears ~300 lines would keep it within the project size guideline.

### [PASS] Success-criteria coverage for Sections 6–9

These criteria map to tasks:
- **Payload inverse:** the `verdict_to_payload` round trip is covered by 6.1 and 6.2, including nulls and key-set equality.
- **Test migration:** 104's tests moving to the parser, with the old reader deleted, is covered by 7.1–7.4.
- **Exit code 12:** covered by 8.1.
- **Failure paths:** missing, non-UTF-8, unparseable, no-version-label and no-store cases are covered by 8.3, with an empty inbox asserted.
- **Ingest never opens a store:** covered by an `ast` rule in 8.3.
- **Success path:** covered by 8.5.
- **End to end, and D6:** the integration requirement is covered by 8.6, 8.6b, 8.7 and 8.8, with the stopped and running process variants.
- **Docs:** the evidence contract, process contract and CHANGELOG are covered by 9.1 and 9.2.
- **Final walkthrough:** covered by 9.3.
- **Part 1:** it holds the parser, fields, fixtures, PyYAML, `provider_failure_problem`, the import-direction rule and the single-definition rule. Sections 1–5 close the remaining success criteria.

### [PASS] Test-with pattern, commit distribution and interim-state safety

Each implementation task is followed immediately by its test task, and the combined commits are called out as 6.1 with 6.2, 8.2 with 8.3, and 8.4 with 8.5. Commits occur at nearly every task, not at the end. The interim stub in 8.2 returns `SUBMISSION_REFUSED` with a `TODO(8.4)` marker instead of success. The 8.3 tests cover only failure paths, so no commit reports success without submitting.

### [PASS] No load-test or CI-gating obligation

The slice design restates no NFR and adds no performance requirement. Task 9.3 says so and runs the existing `tests/load` suite only as a regression check. That directory exists with concurrent-inbox, concurrent-verdict, recovery-scale and crash-loop tests. Requiring a new load test or CI wiring task would be wrong here.

### [PASS] Referenced test helpers exist

The helpers that Tasks 8.3 and 8.6 tell the junior to reuse all exist in `tests/cli_harness.py`: `cli_environment`, `start_running`, `stop_running`, `await_condition` and `submit_cli`. The fixture setup instructions are therefore concrete and doable.

### Run Digest

- Response length: 7567 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 57.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
