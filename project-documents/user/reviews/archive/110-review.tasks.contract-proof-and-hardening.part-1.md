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
reviewedSha: 8b2ccb2b65707e57db31ffabb204419e223e230f
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 291556
cachedTokens: 187403
cacheWriteTokens: 104145
completionTokens: 9040
durationSeconds: 70.8
costUsd: 0.526407
costBasis: provider
runId: run-20261020-p5-002cb7ae
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "File 1 covers its share of the LLD, in a sound order"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:66-360"
  - id: F002
    severity: concern
    category: specification-gap
    summary: "Task 3.1 does not say what the retry rule does to the ledger row and the journal resolve"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:207-208"
  - id: F003
    severity: concern
    category: specification-gap
    summary: "Task 4.4 gives no path for a public name `ProofRunner` needs that is not exported"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:316-319"
  - id: F004
    severity: concern
    category: specification-gap
    summary: "Task 4.4 and 4.5 leave it unspecified how the Runner's per-project paths reach the bootstrap subprocess"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:315, 335"
  - id: F005
    severity: note
    category: task-sizing
    summary: "Tasks 4.4 and 4.5 are large and untested until 4.6"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:307-360"
  - id: F006
    severity: note
    category: scope
    summary: "Task 2.3's docstring assertion may add unplanned edits"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md:154"
---

# Review: tasks — slice 110

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] File 1 covers its share of the LLD, in a sound order

- **Coverage:**
  - Tenant-order pin (1.2) matches the Migration Plan.
  - H4 (2.1), H1 (2.2, 2.3, 2.5), H3 (2.4, 2.5), and H2 (3.1–3.3) are each covered.
  - The D1 import rule (4.1, 4.2) and the store-safety extension (4.3) are covered.
  - `ProofRunner` and the harness (4.4–4.6) are covered, and the D3 step list and crash points are carried into 4.4.
  - The 13 H1 names in 2.3 match D7.
- **Order:** the tenant-order test lands before the move and is reused after it. Exports precede their docs. The store-safety extension precedes the new `tests/contract/` code. There are no cycles.
- **Commits:** checkpoints are spread across all four sections.
- **Load tests:** the slice states no NFR, so a load-test task and CI wiring are not required.
- **Store-safety scan:** no existing test references `DEFAULT_SQ_RUNS_DIR` or `DEFAULT_CF_DATA_DIR`, so the 4.3 stop condition is unlikely to fire.

### [CONCERN] Task 3.1 does not say what the retry rule does to the ledger row and the journal resolve

- Step 2 runs `_record_verdict_within` with its "retry rule, unchanged". Steps 3 and 4 then write the ledger row and resolve the entry.
- When the verdict id is already recorded, the helper returns the existing record. The task does not say whether steps 3–4 still run in that case.
- Validation runs first and refuses an already-resolved entry. A retry of a fully committed report therefore raises `InvalidTransitionError` before it reaches the retry branch.
- A junior implementer cannot tell which behavior is intended.
- Task 3.2 (line 231) only asks the test to "state which branch it exercises".
- **Fix:** add one sentence to 3.1 on the intended outcome in the retry branch, citing the evidence contract's "retry rule". Name the reachable case, for example a verdict already recorded while the entry is still unresolved.

### [CONCERN] Task 4.4 gives no path for a public name `ProofRunner` needs that is not exported

- `ProofRunner` must use `VerdictInput`, `DetectionInput`, `DetectionOutcome`, `REVIEW_PRODUCING_KINDS`, `parse_review_artifact`, `to_verdict_input`, `journal_*`, and the node API. Each must come from a `PUBLIC_ROOTS` `__all__`.
- Step 6 only says every `amoeba` import "must pass Task 4.2's rule".
- Slice design D7 says a missing export is a gap. It is fixed here if the fix is additive, and it stops for the PM otherwise. It must also be recorded for the CHANGELOG.
- The task doesn't say what to do when the rule fails on a name the Runner genuinely needs. The likely outcomes are an improvised internal import, which defeats the proof, or a silent stall.
- **Fix:** add a step. Run the rule against `runner_tenant.py` early and list any violation. Apply D7: an additive export lands with its contract doc and a CHANGELOG note, and anything else stops for the PM.

### [CONCERN] Task 4.4 and 4.5 leave it unspecified how the Runner's per-project paths reach the bootstrap subprocess

- `ProofRunner` takes "a mapping of project id to reviews directory", plus run-file and review fixture paths.
- `bootstrap.py` runs as a separate `-m` process, started before step 1 creates the projects.
- The task doesn't say how the mapping and fixture paths cross the process boundary: argv, env, or a JSON file. It also doesn't say how project ids are known before `create_project`.
- The two tasks as written leave this to the implementer. The risk is a mismatch between the reviews directory `watch_reviews` registers and the one the Runner writes into. That would silently break the step 4 "same record id" and "no double ingest" assertions.
- **Fix:** state the transport in 4.5 (for example, one JSON config path in argv, written by the harness). State whether project ids are chosen by the harness or read from the store.

### [NOTE] Tasks 4.4 and 4.5 are large and untested until 4.6

- 4.4 and 4.5 are each effort 3 and carry no tests of their own. They are committed together with 4.6, which is a deliberate and consistent use of the "no commit holds untested behavior" rule.
- 4.6 exercises only `build_tree`, the `AFTER_JOURNAL` crash, a readiness timeout, and a subscriber exception. `launch_review`, `checkpoint`, `finish`, and `AFTER_SIDE_EFFECT` first run in Section 5. That is acceptable, since the scenario is their test.
- A split of 4.5 into "bootstrap" and "harness waits" would give an earlier green checkpoint. It is optional.

### [NOTE] Task 2.3's docstring assertion may add unplanned edits

- "Every exported callable/class has a docstring" goes beyond the LLD, which asks for a written-out expected set "in the style of `tests/test_public_api.py`".
- If the existing test has no such check, this assertion may force docstring edits across `host`, `observers` and the errors modules.
- Keep it only if `test_public_api.py` already does the same. Otherwise drop it, or say that missing docstrings are added in this task.

### Run Digest

- Response length: 5888 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 291556 / 187403 / 104145 / 9040 / not computed
- Duration: 70.8 s
- Cost: $0.53 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
