---
docType: review
layer: project
reviewType: tasks
slice: run-dispatch-and-outcome-ingestion
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261024
dateUpdated: 20261024
reviewedSha: 923f561488da78f1d8a6c92f8fa33e3e3b2a097b
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 128845
cachedTokens: 9623
cacheWriteTokens: 119218
completionTokens: 28632
durationSeconds: 128.9
costUsd: 0.178347
costBasis: provider
runId: run-20261024-p5-0a64b162
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are all covered by tasks"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md:503"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Commit cadence and test-with pattern"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:47"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Declared dependencies contradict the file's stated independence of Sections 8 and 9"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:454"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Task 6.2 is overweight"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:384-395"
  - id: F005
    severity: concern
    category: fixtures
    summary: "Task 2.3 assumes a registered CF worktree exists, with no BLOCKED path"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:111"
  - id: F006
    severity: concern
    category: fixtures
    summary: "The paused-run fixture is hand-built from the LLD, not from real output"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:215"
  - id: F007
    severity: concern
    category: coverage
    summary: "A D6 requirement has no test: detection must not take a paused run's review as external"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:280-288"
  - id: F008
    severity: concern
    category: security
    summary: "Payload bounding is required by the design but no task applies it"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:244-247"
  - id: F009
    severity: concern
    category: granularity
    summary: "Several one-item tasks are too granular"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:178-188"
  - id: F010
    severity: note
    category: coverage
    summary: "Four placement corrections to the LLD are documented but not verified in this review"
    location: "project-documents/user/tasks/125-tasks.run-dispatch-and-outcome-ingestion.md:49-52"
  - id: F011
    severity: note
    category: proportionality
    summary: "No `tests/load/` task is needed for the restated bound on `unrouted_outcomes`"
    location: "project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md:329"
---

# Review: tasks — slice 125

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Success criteria are all covered by tasks

Each functional, technical and integration criterion has a task that tests it. Examples: two-tick dispatch (7.3), worktree routing and read-back (6.1, 6.2, 7.3), pointer failure cases (6.2, 7.1), checkout concurrency (5.5, 7.4), split and empty reviews (4.2, 4.3), the reissue (8.1), pointer-moved (9.1, 9.2), the migration and `EXPLAIN` check (2.4, 2.5), and the walkthrough (10.3). The only criterion without a dedicated test is "126 can read `unrouted_outcomes` without changing `dispatch/` or `ingest/`", which is a design property and not testable here.

### [PASS] Commit cadence and test-with pattern

Each implementation task carries its own tests and one commit. Test-only tasks (2.10, 3.2, 4.4, 4.5, 7.4) follow the code they exercise. Commits are spread across all ten sections, not batched at the end. The dependency graph has no cycles.

### [CONCERN] Declared dependencies contradict the file's stated independence of Sections 8 and 9

Lines 62–63 say "Sections 8 and 9 are independent of each other and of Sections 5–7." But 8.1 depends on 7.4 and 9.1 depends on 8.1. Also, every task lists only its immediate predecessor, so the file is one linear chain with no parallel work. Two specific fixes:
- 8.1 needs at least 7.3, because 8.1 replaces the placeholder block that 7.3 adds (line 432).
- 9.1 needs only 6.2 and the snapshot store, so it should depend on 6.2.

Correct the declared dependencies, or remove the independence claim.

### [CONCERN] Task 6.2 is overweight

One effort-3 task covers `issue_pointer_write`, `read_back` with four answer types, seven D2 outcomes, two new fault kinds, and the timeout branch. Split it in two: (a) the journal, the `cf set` call, and its exit and timeout outcomes; (b) the read-back answers and their entry resolutions, including `slice_name`. Task 7.3 (lines 426–435) is also heavy: it wires both actions, adds the reissue placeholder, and covers eight scenarios. Move the `cf set` failure scenarios into 7.4 or into 6.2's split.

### [CONCERN] Task 2.3 assumes a registered CF worktree exists, with no BLOCKED path

The step says to capture `cf get --json` "from the repo root (a registered CF worktree)", but nothing checks or creates that registration. If the repo root is not registered, the fixture cannot be captured, and 6.1 and 7.x depend on it. Task 3.1 has a fallback; this task has none. Add: "If the repo root is not a registered CF worktree, write `BLOCKED:` with the reason and stop."

### [CONCERN] The paused-run fixture is hand-built from the LLD, not from real output

If no real paused run appears within 60 seconds, 3.1 copies a completed document and writes the `checkpoint` keys from the LLD. The `-edited` suffix records this, but the parser rule in AGENTS.md says a parser's fixture must match the format production emits. A checkpoint shape written from the design doc cannot prove that. Either stop with `BLOCKED:` when no real paused run is found, or make the paused-path tests explicitly shape-only and capture a real paused run during the 10.3 walkthrough.

### [CONCERN] A D6 requirement has no test: detection must not take a paused run's review as external

The slice design (line 301) says a paused run's last review is the review behind its checkpoint verdict, and that "Detection must not take that file as external either." Task 4.4 tests only the completed case. Add a paused-run scan case to 4.4, or to 7.4 if the e2e harness is simpler there.

### [CONCERN] Payload bounding is required by the design but no task applies it

The design's Security note (slice design line 646) says CF and Squadron output stored in payloads is bounded like 122's tail. Task 4.1's `failed` payload `{reason, run_id, failure}` embeds `RunFailure`, including its free-text `message`, and no task states a bound or tests one. The design also stores `outcome_document` verbatim in the result (D6, line 297). That is a result, not a payload, so the two statements may not conflict, but the design does not say so. The PM should decide whether results are exempt. Then 4.1 should state the bound for `failure.message` and test it.

### [CONCERN] Several one-item tasks are too granular

2.9 (journal listing column), 2.10 (run the contract suite) and 4.4 (one detection test) each have one or two checks and effort 1–2. Task 5.3 (`dispatch_params`, effort 1) could fold into 5.4, which edits the same view. Merge 2.9 and 2.10, fold 4.4 into 4.3's test list, and fold 5.3 into 5.4. This keeps the commit-per-task rule and cuts about four tasks.

### [NOTE] Four placement corrections to the LLD are documented but not verified in this review

The task file moves the planner tuple to `runner/factory.py` (LLD says `tenant.py`), moves the stem rule to `upstream/context_forge`, and places the detection key in `process/review_scan.py`. Each is justified by an import boundary or by the code's current state, and the projectState line supports the factory placement. I did not read the source to confirm them. Confirm before 2.1, 2.8 or 10.1 starts.

### [NOTE] No `tests/load/` task is needed for the restated bound on `unrouted_outcomes`

The design says the read cost is "bounded by unrouted work, not by history." The `EXPLAIN QUERY PLAN` test in 2.5 is the proportionate check for that bound. No load test or CI gate is required.

### Run Digest

- Response length: 6854 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 128845 / 9623 / 119218 / 28632 / not computed
- Duration: 128.9 s
- Cost: $0.18 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
