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
sourceDocument: project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261019
dateUpdated: 20261019
reviewedSha: 301a280096ce818b1e1ccf6cacc282f13fee1999
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 306843
cachedTokens: 264488
cacheWriteTokens: 42347
completionTokens: 4795
durationSeconds: 40.9
costUsd: 0.244473
costBasis: provider
runId: run-20261020-p5-002cb7ae
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: concern
    category: acceptance-criteria
    summary: "Task 8.1's grep criterion fails on a legitimate mention"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:284"
  - id: F002
    severity: note
    category: coverage
    summary: "Step 6's \"node runnable\" outcome has no explicit assertion"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:97"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Success-criteria coverage for Sections 5–9"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Sequencing, sizing and commit cadence"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Proportionality"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
---

# Review: tasks — slice 110

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 8.1's grep criterion fails on a legitimate mention

The criterion says `grep -n "slice 110\|or 110" docs/*-contract.md` must return nothing. `docs/network-contract.md:14` ("slice 110's end-to-end proof can use the store…") matches `slice 110`. It is a historical statement about the proof, not a Future-work line. The task does not edit that file, so the junior AI cannot meet the criterion without deleting accurate text. The `or 110` half is already handled by file 1's `evidence-contract.md` edit. Narrow the check to Future-work lines. For example: "`docs/process-contract.md` Future-work no longer lists pruning, and `docs/evidence-contract.md` no longer says 'or 110'". Or list `network-contract.md:14` as an accepted remaining match.

### [NOTE] Step 6's "node runnable" outcome has no explicit assertion

The LLD requires that after step 6 the escalated node is runnable. Task 5.4 lists step-level assertions for steps 3, 4 and 5 but none for step 6. The end-state oracle checks only the final state, which step 11 may have changed. Adding one line, "after step 6, `runnable` includes the step-5 node", closes this.

### [PASS] Success-criteria coverage for Sections 5–9

Each LLD success criterion maps to a task:
- **Scenario, end-state and feed-replay oracles:** Tasks 5.1–5.5, including the `seq` gap check across steps 4, 5 and 10.
- **Network subset:** Tasks 6.1–6.2, including the 202-while-down case and SSE `seq` equal to local `follow(after=0)`.
- **Pruning, pure rule and tests:** Tasks 7.1–7.2.
- **Pruning, CLI and exit code 14:** Tasks 7.3–7.4, covering each failure mode, the unreadable-store refusal, and preview never calling `sq`.
- **Step 12:** Task 7.5.
- **Substrate guide, CHANGELOG, walkthrough, `__all__` documentation check:** Tasks 8.1–9.1.

The remaining criteria sit in file 1: the D1 rule, H1–H4, the store-safety guard extension, and the tenant-order check. I found no scope creep.

### [PASS] Sequencing, sizing and commit cadence

Dependencies are linear with no cycles. The test-with pattern holds throughout:
- Oracles: 5.2 is tested in 5.3.
- Selection rule: 7.1 is tested in 7.2.
- CLI: 7.3 is tested in 7.4.

The only forward reference is Task 5.4's note that 5.5 and 7.5 extend `test_lifecycle_proof.py`, which matches their dependency order. Commits land after every task or task pair, and none are batched at the end. Efforts of 1–3 are reasonable. Splitting 5.4 and 5.5 around the crash steps keeps each driver task bounded. The 5.6 gap-resolution task and the "Gaps Found" log handle the LLD's D7 uncertainty without inflating the plan.

### [PASS] Proportionality

The two-file split fits a slice of this size, and file 2 contains no test tasks beyond what the success criteria require. `test_oracle.py` is justified because the LLD says each oracle must fail when it should. The LLD names no NFRs, so no load-test or CI-gating task is needed.

### Run Digest

- Response length: 3649 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 306843 / 264488 / 42347 / 4795 / not computed
- Duration: 40.9 s
- Cost: $0.24 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
