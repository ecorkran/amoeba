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
reviewedSha: 5a02aa4b0ae6fd2eb27896b2cbdca61a62912ee2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 191394
cachedTokens: 91784
cacheWriteTokens: 99604
completionTokens: 8045
durationSeconds: 67.0
costUsd: 0.488724
costBasis: provider
runId: run-20261020-p4-8ad1873b
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: concern
    category: proportionality
    summary: "Design is heavier than a Low-risk, effort-3 integration slice"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md:403"
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "Writer model and layer boundaries are preserved"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#State-Management"
  - id: F003
    severity: pass
    category: architecture-alignment
    summary: "Pruning honors the architecture's ownership and \"never touch SQ files\" rules"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D8"
  - id: F004
    severity: pass
    category: error-handling
    summary: "Harness failure modes are explicit"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Patterns-and-Conventions"
  - id: F005
    severity: note
    category: scope
    summary: "Run-file parser placement widens `amoeba.upstream.squadron` beyond the architecture's wording"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md:281-283"
  - id: F006
    severity: note
    category: under-specification
    summary: "Export surface and read interfaces are under-specified for D1 and D9"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md:84-95"
  - id: F007
    severity: note
    category: integration
    summary: "Ownership guarantee is convention-only on the `journal_resolve` path"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md:295-299"
  - id: F008
    severity: note
    category: completeness
    summary: "Locality documentation is not mapped to a deliverable"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#D6"
---

# Review: slice — slice 110

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Design is heavier than a Low-risk, effort-3 integration slice

The slice plan scopes 110 as a contract proof, a locality check, implemented pruning, and consumer docs. This design also adds:
- a Store mixin method (H2);
- a tenant-factory move across packages (H1);
- a parser move (H4);
- new `amoeba.process` and `amoeba.store` exports;
- a new destructive CLI command with its own exit code and stub-`sq` failure matrix;
- an AST import rule with its own test file;
- a documentation-coverage test;
- before/after equivalence tests;
- two oracles;
- a network subset with two process kills.

Most of this is justified by the plan's pruning, "no internal access", and 109-handoff requirements. The following can be cut or narrowed:
- **Documentation-coverage test (D9, line 403).** It asserts that every name in `__all__` of every `PUBLIC_ROOTS` package appears in that package's contract doc. That is a retroactive audit of all of 101–109's surface, and nothing in the plan asks for it. Narrow it to the names this slice adds (H1, H2, H3 and the pruning exports). Defer the whole-surface audit to a later cleanup.
- **Guard test (lines 480, 406).** The new test that no test under `tests/` sets a runs directory outside `tmp_path` extends 101's store-safety scan. Fold it into that scan rather than adding a separate test.
- **Open-ended gap hunting (D7, "Any further gap").** The design says itself that the effort estimate is uncertain (line 479). Keep the PM stop rule. Also state an upper bound on additive fixes, for example "more than N, or more than one new public name per gap, returns to the PM".

### [PASS] Writer model and layer boundaries are preserved

- The slice adds no tables, migrations or write paths.
- `ProofRunner` writes in-process through the store API, which is the Runner's documented position.
- Out-of-process actors use the inbox.
- `cli/prune.py` opens stores read-only.
- The oracle and the pruning selection read only.

This matches the architecture's sole-writer model and its rule that the network layer adds no write path.

### [PASS] Pruning honors the architecture's ownership and "never touch SQ files" rules

- The architecture says "the store's record of which paused runs it owns serves reconciliation and pruning" and that no part edits SQ's run files directly. D8 derives ownership from the journal's recorded `run_id` and deletes only through `sq runs prune`.
- Escalated (`unknown`) entries are never owned, which follows "unknown is a value".
- Failure modes are enumerated with explicit handling:
  - `sq` missing, failing, timing out, or refusing a run;
  - an unreadable store, which refuses the whole command;
  - an unparseable run file, or one with no `updated_at`.
- The outcome is decided by re-reading the runs directory, not by parsing `sq`'s text or exit status. The command converges on re-run.

### [PASS] Harness failure modes are explicit

Every wait is a predicate with a timeout. A timeout fails the test with the step number and the captured output of every subprocess. A follower-thread exception is re-raised on the main thread. An unplanned SSE drop fails the test. The planned process kills, with named crash points, cover the peer-disconnect and mid-send cases for the new network path.

### [NOTE] Run-file parser placement widens `amoeba.upstream.squadron` beyond the architecture's wording

The architecture scopes `amoeba.upstream.squadron` to parsing Squadron **review output**. It assigns parsing of other SQ output to initiative 120. Moving `SquadronRun` and `parse_run_file` there so the observer and the pruning rule share one parser is a reasonable DRY choice, and the design says the move does not widen 105's scope. The architecture itself does not authorize that, so the PM should ratify it explicitly. Only `process-contract.md` and the CHANGELOG carry the note today.

### [NOTE] Export surface and read interfaces are under-specified for D1 and D9

- D1 and the D9 test depend on each root's `__all__`. The design does not say whether `run_file` and `run_pruning` names (`SquadronRun`, `parse_run_file`, `select_prunable`) are exported from the `amoeba.upstream.squadron` root or stay submodule-only.
- The pruning data flow uses `nodes_for_project`, `discover_project_ids` and `DEFAULT_SQ_RUNS_DIR`. None of these is listed under "Interfaces Required".

Neither blocks design approval. Settle both before task breakdown so the documentation-coverage test and the import rule have a defined target.

### [NOTE] Ownership guarantee is convention-only on the `journal_resolve` path

`record_runner_report` enforces `run_id` on `sq_run` entries, but a direct `journal_resolve(completed)` call does not. Initiative 120 is bound only by a contract line and the D9 citation. The design correctly calls the failure safe: unowned runs are never pruned. It is also a hidden coupling to 120, so the PM may want to confirm that tightening `journal_resolve` is deliberately out of scope. That would be a behavior change under D7.

### [NOTE] Locality documentation is not mapped to a deliverable

The plan's criterion is "Store locality behaves correctly for the chosen model **and is documented**". D6 supplies the test. Documentation exists only if `store-contract.md` already covers it, and H3 suggests it does. Say so in D9, or add a link to that section from the substrate guide, so the criterion is visibly met.

### Run Digest

- Response length: 6645 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 191394 / 91784 / 99604 / 8045 / not computed
- Duration: 67.0 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
