---
docType: review
layer: project
reviewType: slice
slice: contract-proof-and-hardening
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/110-slice.contract-proof-and-hardening.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261019
dateUpdated: 20261019
reviewedSha: 5cc98ff06cc20c6672f21831a593d18c6eef6b91
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 188252
cachedTokens: 94673
cacheWriteTokens: 93573
completionTokens: 6931
durationSeconds: 57.7
costUsd: 0.45375
costBasis: provider
runId: run-20261020-p4-8ad1873b
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: concern
    category: under-specification
    summary: "Hardening cap contradicts the design's own H1–H4 and is ambiguous"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D7 — Hardening: additive fixes only, everything else to the PM"
  - id: F002
    severity: concern
    category: architecture-boundary
    summary: "`run_file` placement stretches the architecture's scope for `amoeba.upstream.squadron` with no amendment"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D7 (H4)"
  - id: F003
    severity: concern
    category: failure-modes
    summary: "The residual race in pruning is described as covered by Squadron, but one case isn't"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D8 (`--yes` always selects afresh; Re-linking)"
  - id: F004
    severity: concern
    category: proportionality
    summary: "The slice carries more verification and documentation mechanism than its deliverable needs"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Verification Walkthrough"
  - id: F005
    severity: note
    category: integration
    summary: "Prune ownership depends on a result-key convention that is enforced only in `record_runner_report`"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D8 (The ownership guarantee)"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Layering, writer model and dependency directions hold"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Component Structure"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for each new I/O path"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D8 and #Patterns and Conventions"
---

# Review: slice — slice 110

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Hardening cap contradicts the design's own H1–H4 and is ambiguous

D7 says "a gap whose fix adds more than one public name stops for the PM." H1 adds about 13 names to `amoeba.process.__all__` and H3 adds 2 to `amoeba.store`. Read literally, both H1 and H3 should have stopped for the PM.

The count of further gaps is also unclear. D7 says "a fourth gap beyond H1–H4" stops. Special Considerations says "up to three small additive fixes stay in scope." Those could mean a fifth gap, a fourth gap, or three more gaps.

This cap is the only bound on the effort risk the design names (effort 3). State whether the one-name rule applies only to newly discovered gaps, and give one unambiguous count of newly discovered gaps allowed.

### [CONCERN] `run_file` placement stretches the architecture's scope for `amoeba.upstream.squadron` with no amendment

The architecture limits Amoeba's Squadron parsing to review output. It says the architecture "does **not** own parsing of other SQ output." H4 moves the run-file header model into `amoeba.upstream.squadron`. The design admits this is "pending PM ratification" and only promises to say in `process-contract.md` and the CHANGELOG that `run_file` is not part of the review-output contract.

Ratification is a step-1 gate, but the design gives no fallback if the PM declines. It also doesn't say whether the architecture's scope sentence is amended. Pick one:
- Record the architecture amendment, or
- Name the alternative placement, such as a neutral shared module outside `upstream` that both the observer and `cli/prune.py` can import.

### [CONCERN] The residual race in pruning is described as covered by Squadron, but one case isn't

D8 says the window between selection and `sq`'s deletion is "covered by Squadron's own refusal: a run resumed in that window is live." The same section says a paused run can be linked again to a new or reopened node. A run that is relinked in that window but not yet resumed is not live. `sq` would delete it, and the Runner's later `sq run --resume <id>` would fail on a missing run.

The store reads across projects are also separate read-only opens, not one atomic snapshot.

The window is narrow and the failure is explicit, so I don't think it needs a design change. The design should:
- state the residual case, and
- add a line to the process contract saying what a Runner does when a resume targets a vanished run, so 120 handles it.

### [CONCERN] The slice carries more verification and documentation mechanism than its deliverable needs

The plan's 110 criteria are a lifecycle run through the public API, a restart mid-sequence, locality documented, and pruning implemented and documented. Several parts go beyond that or restate other material:
- **Walkthrough steps 2 and 3.** These repeat by hand what `test_network_subset.py` and the scenario already assert automatically: locality, `kill -9` of the resident process, and `Last-Event-ID` resume. They need a seeded node script, three terminals and `pgrep` kills. Cut them to the automated run plus a pointer to the tests.
- **D9's test that every new export is documented.** It is justified only for H1–H3's handful of names. A review checklist item would meet the requirement more cheaply. Keep it only if it is a few lines.
- **A second oracle plus a second scenario project.** The feed-replay oracle and project `beta` are defensible. They serve D6's locality check and the pruning "held" case, but they add steps 9–12 and per-project assertions. The design should say whether `beta` could be reduced to the pruning-only case.

None of this drops assigned scope. It can be cut or deferred without losing a plan criterion.

### [NOTE] Prune ownership depends on a result-key convention that is enforced only in `record_runner_report`

The architecture says the store's record of owned paused runs serves reconciliation and pruning. The design implements ownership as the presence of `run_id` in journal results. It enforces this for recovery's `adopted` outcome and for H2's method. Direct `journal_resolve` calls from 120 are bound only by a contract line. Making `journal_resolve` enforce it is out of scope under D7.

The failure is safe, because unowned runs are never pruned. It is stated in D8 and D9, and the 120 row of the guide cites it. The design handles this well.

### [PASS] Layering, writer model and dependency directions hold

- `cli/prune.py` opens stores read-only only.
- `run_pruning.py` and `run_file.py` import nothing from the store, inbox or process, which keeps 105's rule.
- `process/tenants.py` adds no new package edge, and AST tests pin both rules.
- `ProofRunner` writes in-process, and the Judge and PM actors write through the inbox, matching the architecture's sole-writer model.
- Network writes in the subset are inbox submissions only.
- Deletion goes only through `sq runs prune`, which respects "no part edits SQ's run files directly."
- Stdin is non-TTY, per the architecture's explicit-resume invariant.

### [PASS] Failure modes are enumerated for each new I/O path

The pruning path covers:
- `sq` missing, failing or timing out (`SQ_PRUNE_TIMEOUT_SECONDS`)
- `sq` refusing a live run
- an already-removed file
- an unreadable store (the whole command refuses)
- an unparseable run file (WARNING, never a candidate)
- a missing `updated_at`

The result is observed by re-reading the runs directory, not parsed from `sq`'s text. The harness fails loudly with step number and captured output, uses predicate waits with timeouts, re-raises thread exceptions on the main thread, and reconnects the SSE follower only at planned kill points. The parent architecture states no numeric NFR on these paths, so none needs restating.

### Run Digest

- Response length: 7325 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 188252 / 94673 / 93573 / 6931 / not computed
- Duration: 57.7 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
