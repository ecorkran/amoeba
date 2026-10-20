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
reviewedSha: 8b2ccb2b65707e57db31ffabb204419e223e230f
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 220295
cachedTokens: 136367
cacheWriteTokens: 83922
completionTokens: 4295
durationSeconds: 35.2
costUsd: 0.392956
costBasis: provider
runId: run-20261020-p5-002cb7ae
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: concern
    category: verification
    summary: "Task 8.1's \"no slice 110 reference\" grep will fail once the substrate guide exists"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:283"
  - id: F002
    severity: note
    category: verification
    summary: "The walkthrough's `-k prune` will not select scenario step 12"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md:425"
  - id: F003
    severity: note
    category: process
    summary: "Task 5.6 may end with nothing to commit when no gaps are found"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md:136"
  - id: F004
    severity: pass
    category: coverage
    summary: "Success-criteria coverage and sequencing"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F005
    severity: pass
    category: scope
    summary: "Proportionality and test placement"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
---

# Review: tasks — slice 110

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 8.1's "no slice 110 reference" grep will fail once the substrate guide exists

Task 8.1 requires `grep -rn "slice 110\|or 110" docs/` to return nothing. Task 8.2 then creates `docs/substrate-guide.md`, which links to "this slice's `CHANGELOG.md` entry". That page will almost certainly say "slice 110", so the same grep fails afterward. Other contract docs may also mention 110 as history. The slice requirement is narrower: the Future-work lines that point at 110 are replaced. Scope the check to Future-work or pending-work references, such as the pruning line in `process-contract.md` and the "or 110, if earlier" text in `evidence-contract.md`. Otherwise Task 9.1 or a later re-run will fail on a criterion that was met.

### [NOTE] The walkthrough's `-k prune` will not select scenario step 12

Walkthrough step 2 runs `pytest tests/contract tests/process -k prune` and expects scenario step 12 to be exercised. Task 7.5 puts step 12 at the end of `test_lifecycle_proof.py`, whose test and module names contain no "prune". `-k prune` therefore picks up only `tests/process/test_prune_selection.py` and `test_prune_sq_runs.py`, and step 12 is not run. Task 7.2 handled this for the selection tests but nothing handles it for step 12. Task 9.1 says to correct the walkthrough when it differs, so this will be caught. Fixing it now is cheaper, either by correcting the walkthrough command or by naming step 12's test with "prune".

### [NOTE] Task 5.6 may end with nothing to commit when no gaps are found

Task 5.6 has no commit step of its own. If no gaps are found, the "None found" edit to the Gaps Found log is left uncommitted. Task 8.3 depends on that log. Add a short commit for the log update. It could be folded into Task 6.1's commit if a separate one is unwanted.

### [PASS] Success-criteria coverage and sequencing

Each slice criterion maps to a task:
- **End state and feed replay:** Tasks 5.2, 5.3, and 5.5.
- **Network subset:** Tasks 6.1 and 6.2, including the `seq` equality check and the POST made while the resident process is down.
- **Step 3, 4, and 5 assertions:** Task 5.4, including the ownership guarantee.
- **D6 locality:** Task 5.2.
- **Pruning criteria:** Tasks 7.1 to 7.5. This includes each condition failing alone, a missing `updated_at`, a held run, failure modes leaving files in place, an unreadable store refusing before `sq`, and step 12.
- **Docs:** Tasks 8.1 to 8.3.
- **Walkthrough:** Task 9.1.

Of the supporting items in file 1, the schema-v5 fixture and the contract-doc updates for H1 to H3 are all there. The `tests/test_store_safety.py` extension appears only as a path-name addition (file 1, line 298). It may not cover the slice's "HOME or runs directory outside `tmp_path`" check, but the file 1 tasks were not reviewed here.

### [PASS] Proportionality and test placement

Tests follow their implementations in 5.3, 6.x, and 7.2/7.4, with a commit at the end of each section. Task 5.3's oracle self-tests are justified because each oracle must be shown to fail when it should. The stub-`sq` modes in Task 7.4 each map to a slice-required failure case. The slice states no NFRs, so no load-test or CI-gating task is required.

### Run Digest

- Response length: 4066 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 220295 / 136367 / 83922 / 4295 / not computed
- Duration: 35.2 s
- Cost: $0.39 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
