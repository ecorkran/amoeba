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
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: e7957d157e1d5f4209dddfa1712c0c7c1add9676
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 186046
cachedTokens: 93512
cacheWriteTokens: 92528
completionTokens: 4898
durationSeconds: 41.3
costUsd: 0.429124
costBasis: provider
runId: run-20261015-slices-plan-fa1ba72e
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Writer model and layer boundaries respected"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Architecture"
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "Pruning ownership follows the architecture's stated intent"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D8"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Pruning design (D8) is heavier than the requirement needs"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D8"
    resolution: accepted
    resolvedBy: "Cut KeepReason, UnreadableRun, PruneSelection, the kill-wait-observe timeout path, and PruneSettings (PM, 20261015). Preview lists candidates plus a kept count; unparseable files log WARNING; any candidate still present after sq (including timeout) exits PRUNE_INCOMPLETE; retention and sq timeout are module constants. The post-sq re-read of the runs dir is kept because sq exits 1 for an already-removed run"
  - id: F004
    severity: concern
    category: specification-consistency
    summary: "Export-documentation check is specified two contradictory ways"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md:47"
    resolution: accepted
    resolvedBy: "Technical Requirements now specify a mechanical test that every __all__ name of each PUBLIC_ROOTS package appears in its contract doc"
  - id: F005
    severity: concern
    category: dependencies
    summary: "Heavy dependence on names from three unmerged slices"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Dependencies"
    resolution: no_change_needed
    resolvedBy: "Risk note only; Development Approach step 1 stops for the PM and reconciles every name taken from 107-109 against merged code"
  - id: F006
    severity: concern
    category: under-specification
    summary: "Scenario step 12 leaves test-input setup under-specified"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D4"
    resolution: accepted
    resolvedBy: "checkpoint sets and blocks the gate node; step 7 also writes a paused run file with an unjournaled run id; stand-in run files carry updated_at 8 days before wall clock; step 12 states the expected candidate, held run, unowned run, and kept count"
  - id: F007
    severity: concern
    category: error-handling
    summary: "Failure handling for the proof harness's own processes is not enumerated"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Data-Flow"
    resolution: accepted
    resolvedBy: "Patterns and Conventions add harness failure rules: a timed-out wait fails with the step number and all subprocess output; a subscriber-thread exception is re-raised on the main thread; an unplanned SSE drop fails the test"
  - id: F008
    severity: note
    category: architecture-alignment
    summary: "Moving the run-file parser into `amoeba.upstream.squadron`"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#H4"
    resolution: accepted
    resolvedBy: "H4 requires process-contract.md and the CHANGELOG to state run_file is a run-state adapter, not part of the review-output contract"
  - id: F009
    severity: note
    category: scope-control
    summary: "Hardening scope is bounded by an explicit rule"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D7"
    resolution: no_change_needed
    resolvedBy: "Positive note; no action"
---

# Review: slice — slice 110

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Writer model and layer boundaries respected

- The Runner (`ProofRunner`) is an in-process tenant that writes directly.
- The PM and the Judge go through the inbox.
- The oracle and `amoeba prune` open stores read-only.
- Pruning deletes only through `sq runs prune`, so no part edits Squadron's run files directly.
- This matches the architecture's sole-writer model and its state-is-the-interface goal.
- `amoeba.upstream` never imports `amoeba.process`, and the Layering rules extend the existing import-boundary test.

### [PASS] Pruning ownership follows the architecture's stated intent

- The architecture says "the store's record of which paused runs it owns serves reconciliation and pruning" and "pruning policy is Amoeba's."
- D8 derives ownership from journal results and holds a run while any non-`done` node names it.
- It never prunes escalated-unknown runs, because Amoeba never proved those were its own.
- The slice plan's criterion "Pruning policy for paused SQ runs is implemented and documented" is met.
- The store-retention exclusion is explained against the slice plan's later rescoping.

### [CONCERN] Pruning design (D8) is heavier than the requirement needs

The slice plan asks for one thing: "Pruning policy for paused SQ runs is implemented and documented." D8 builds a lot more than that, and several parts can be cut or deferred:
- **KeepReason enum.** Five members plus an `UnreadableRun` type feed a "kept owned runs" listing. The preview needs to show candidates and why each owned run was kept. It does not need a closed enum plus a separate unowned-count output.
- **Timeout handling.** The design kills `sq`, waits, observes, and then makes partial-success claims. A single "sq failed or timed out, rerun" result with `PRUNE_INCOMPLETE` meets the requirement.
- **PruneSettings.** It is a frozen dataclass whose only consumers are the two values the CLI does not expose. Two module constants are enough until something configures them.
- **Slice size.** The slice carries four parts (proof, hardening, pruning, docs) at effort 3. The pruning part is the likeliest to grow past that.

Trim the observation and report layers to what the preview and `--yes` output need. Defer the rest to a follow-up.

### [CONCERN] Export-documentation check is specified two contradictory ways

- Included/Docs (line 47) and D9 say a test checks that every exported name is documented.
- Technical Requirements say "Checklist, once, at the end of the slice."
- A test and a one-time checklist are different guarantees, and the Technical Requirements do not say which one is required.
- The consumer-documentation guarantee (the substrate-guide entry for 120, 140, and 160 authors) depends on this check.
- Pick one. A mechanical test matches the slice's "executable documentation" framing and the D1 AST rule.

### [CONCERN] Heavy dependence on names from three unmerged slices

- 107, 108, and 109 are `not_started`.
- This design fixes many of their names and behaviors:
  - `judge_invocation_id`, `CFWatchTenant`, `cf_version_label`, and `store/discovery.py`;
  - `as_of_seq`, the `Last-Event-ID` semantics, and `inspection`;
  - `ExitCode` 13/14 numbering.
- The first-task gate handles this: it stops for the PM and reconciles names. That is the right mitigation.
- The design is still committing in detail to unreviewed surfaces. Keep the stable parts (D1–D3, D5, D8) free of those names where possible, so a late change in 107–109 does not force a rewrite.
- This is a risk note, not a defect.

### [CONCERN] Scenario step 12 leaves test-input setup under-specified

- Step 12 expects step 7's PM-launched run to be counted as unowned and Beta's run to be held. Neither is set up anywhere in the design.
  - Step 7 writes a review artifact. It does not say a paused run file is written, and an unowned run only counts if one exists in the runs directory.
  - Step 9 does not say which node (slice or gate) holds `sq.run_id`. Step 11's `finish` marks the slice and gate `done`.
- Alpha's checkpoint run becomes a candidate only if its holding node is `done`.
- Beta's run is held only if its node stays not `done`.
- The design should state the node, and the run file written for step 7, so the expected `KeepReason` and unowned count are derivable from the doc.
- The "at least 7 days" age condition also needs the fixture `updated_at` values to be explicit, or the test relies on an injected `now`.

### [CONCERN] Failure handling for the proof harness's own processes is not enumerated

- The design lists readiness and change predicates with timeouts, but it does not say what happens on:
  - the bootstrap subprocess failing to reach readiness;
  - the SSE follower's connection dropping outside the planned kills;
  - the `follow()` subscriber thread dying.
- The network subset exercises new I/O paths (the HTTP POST and SSE clients). It should say that a timeout fails the test with the step number and captured process output, not a hang or a skip.
- Pruning's failure modes (sq missing, refusing, timing out, unreadable store) are well covered. The harness side needs the same treatment.

### [NOTE] Moving the run-file parser into `amoeba.upstream.squadron`

- The architecture's scope says the store-adjacent adapter owns parsing of Squadron review output and "does not own parsing of other SQ output."
- The run-file parser already exists in 102's observer, so the move is placement only.
- It is acceptable because it is additive and pure, and 105's no-store-import rule is preserved.
- Say in `process-contract.md` or the CHANGELOG that `run_file` is an adapter for run state files, not part of the review-output contract. Otherwise a later reader may read the move as widening the scope.

### [NOTE] Hardening scope is bounded by an explicit rule

- D7 limits fixes to additive changes and routes behavior or schema changes to the PM. It also defines xfail closure.
- The four known gaps (H1–H4) are each additive.
- This keeps the unknown-gap risk bounded, as the Special Considerations section says.

### Run Digest

- Response length: 7351 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 186046 / 93512 / 92528 / 4898 / not computed
- Duration: 41.3 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
