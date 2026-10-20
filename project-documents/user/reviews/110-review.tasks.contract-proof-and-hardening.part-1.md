---
docType: review
layer: project
reviewType: tasks
slice: contract-proof-and-hardening
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261019
dateUpdated: 20261019
reviewedSha: 301a280096ce818b1e1ccf6cacc282f13fee1999
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 224380
cachedTokens: 182353
cacheWriteTokens: 42021
completionTokens: 3150
durationSeconds: 28.1
costUsd: 0.218502
costBasis: provider
runId: run-20261020-p5-002cb7ae
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: concern
    category: task-sizing
    summary: "Task 4.4 carries three separable responsibilities and defers its test to 4.6"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:308-324"
  - id: F002
    severity: concern
    category: clarity
    summary: "Task 3.1 defers important design decisions as \"stop and ask\" branches"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:205-213"
  - id: F003
    severity: concern
    category: sequencing
    summary: "The `HOME`/`DEFAULT_SQ_RUNS_DIR` contract is spread across tasks with no single owner"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:56-59"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Task 2.5 and Task 3.3 split doc and export updates across tasks beyond what the criteria need"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:162-193"
  - id: F005
    severity: concern
    category: test-quality
    summary: "Task 1.2 asks for names to be \"read once, then written out\", which can leave the test circular"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:93"
  - id: F006
    severity: note
    category: coverage
    summary: "Coverage of the LLD success criteria in this file"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:62"
  - id: F007
    severity: note
    category: proportionality
    summary: "Proportionality of the task set"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:66"
  - id: F008
    severity: pass
    category: sequencing
    summary: "Sequencing, commit cadence and scope traceability"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:85-362"
---

# Review: tasks — slice 110

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 4.4 carries three separable responsibilities and defers its test to 4.6

Task 4.4 (effort 3) covers the enum definitions and intent-key constants. It also implements four step behaviors and two crash modes, and adds a rule for handling gaps in the public API. That gap rule can create a separate commit with a contract doc and an expected-exports test. The task is "committed with Task 4.6", which is two tasks later. Task 4.5 is also "committed with Task 4.6". Three tasks, 4.4 to 4.6, therefore share one commit. That commit has only a harness smoke test, which exercises `build_tree` and `AFTER_JOURNAL`. The `launch_review` and `checkpoint` bodies are first exercised in Section 5. Splitting 4.4 would give a smaller commit at the `build_tree`/enums point and a second one for the review/checkpoint/crash steps. Alternatively, move the `checkpoint`, `finish` and `AFTER_SIDE_EFFECT` behaviors into Task 5.x, where the scenario first tests them. That keeps the "test-with" pattern honest. The unit is a test-only module, so this is a CONCERN, not a FAIL.

### [CONCERN] Task 3.1 defers important design decisions as "stop and ask" branches

Task 3.1 leaves several branches for the implementer to resolve by stopping and asking the PM:
- the ledger writer may refuse a row because the same file is already in the ledger;
- the meaning of "unknown" in the refusal list;
- whether inner `_within` functions exist for the journal-resolve and record-detection writers.

For a junior AI these branches are ambiguous. The retry path may also conflict with ledger uniqueness, so the retry rule in the task may not be implementable as written. The LLD lists "unknown" among refusals, and the task reinterprets it. Settle these questions in the task breakdown by checking the current code, instead of leaving them to execution time. The task text says the `_within` writers exist or need extracting, which shows the code has not been inspected for this.

### [CONCERN] The `HOME`/`DEFAULT_SQ_RUNS_DIR` contract is spread across tasks with no single owner

The context summary adds three task-level rules about `HOME`. They are that the proof sets `HOME` for every subprocess, that `ProofRunner` and `ProcessSettings()` derive the runs directory the same way, and that `DEFAULT_SQ_RUNS_DIR` is forbidden by name in tests. Task 4.3 forbids `DEFAULT_SQ_RUNS_DIR` in tests. Task 4.5 then has the bootstrap read `ProcessSettings().sq_runs_dir`. The bootstrap lives under `tests/contract/`, so it is covered by the new scan. It reads the setting, not the forbidden name, so the scan should pass. Task 4.3 has no step that confirms this. Task 4.3 should say so explicitly. Without that, a junior who gets a scan failure in 4.5 has no guidance.

### [CONCERN] Task 2.5 and Task 3.3 split doc and export updates across tasks beyond what the criteria need

The H3 export (Task 2.4) is not a committed unit. It is "committed with Task 2.5", which is a docs task. The H1 export in Task 2.3 is committed on its own, with its docs deferred to Task 2.5. The "Integration Requirements" section of the LLD says every public name must appear in the contract doc, so the docs belong with the export. A single commit per export plus its doc would match the stated cadence ("a commit never holds untested behavior"). Task 2.3's commit adds 13 public names that have no doc until a later commit. Merge 2.4 and 2.5 into one task, and either move the H1 doc into Task 2.3 or note why it is deferred. This is a bookkeeping issue, and the content is correct.

### [CONCERN] Task 1.2 asks for names to be "read once, then written out", which can leave the test circular

The step says to read the three names from the tenant classes' `name` attributes and then write them literally in the expected tuple. That is correct as a one-time capture. The step does not say to assert that the expected tuple has three entries, in the order the LLD says `amoeba start` registers them. It also gives no instruction about where tick order is defined. The test pins the current order. Add a line that the expected tuple is the order `build_tenants` returns today, taken from the code's return statement and not from sorting or from class discovery. This is a small clarification.

### [NOTE] Coverage of the LLD success criteria in this file

This file correctly covers the Technical Requirements it owns. They are the tenant-order check before and after the move, the D1 import rule (Tasks 4.1–4.2) and the `record_runner_report` refusals including the `run_id` requirement (Tasks 3.1–3.2). It also covers the extended store-safety scan (Task 4.3) and the H4 `updated_at` field with a v5 fixture (Task 2.1). The functional criteria about the scenario, oracles, network subset and pruning belong to file 2, whose headings map to them. The "process/run_pruning.py layering AST test" requirement and the NFR and load-test checks do not apply here. The LLD states no NFR.

### [NOTE] Proportionality of the task set

The file has 16 tasks in four sections. That is heavy but fits a slice of effort 3 that spans hardening, a proof harness and pruning. The two-file split is justified by the section count. I found no test task that goes beyond a success criterion. Task 4.6 tests the harness before the scenario depends on it, which the LLD's fail-loudly requirement justifies.

### [PASS] Sequencing, commit cadence and scope traceability

Each task traces to an LLD item (D1, D3, D7 H1–H4, "Migration Plan", "Special Considerations"). Task 1.2 comes before the move in Task 2.2, as the Migration Plan requires. Task 3.1 depends on Task 2.5, which is stricter than needed. H2 needs no H1 or H3 exports, so the ordering is conservative and not wrong. Tests follow their implementations in Sections 3 and 4. Commits occur in Sections 1, 2, 3 and 4, so none are batched at the end.

### Run Digest

- Response length: 7285 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 224380 / 182353 / 42021 / 3150 / not computed
- Duration: 28.1 s
- Cost: $0.22 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
