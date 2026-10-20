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
reviewedSha: 8cc662334d5b1ecec2f5f6ac869a720f3c1a05d0
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 221452
cachedTokens: 136588
cacheWriteTokens: 84858
completionTokens: 7043
durationSeconds: 59.2
costUsd: 0.4242
costBasis: provider
runId: run-20261020-p4-8ad1873b
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Architectural boundaries and writer model preserved"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md#Architecture"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Design is heavier than the slice must deliver"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md:261-266"
  - id: F003
    severity: concern
    category: integration
    summary: "Selection rule is both \"available to 120\" and non-public"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md:72-73,283"
  - id: F004
    severity: concern
    category: constants-and-config
    summary: "Scattered retention value in the proof, and a magic default outside config"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md:216,322"
  - id: F005
    severity: concern
    category: hidden-dependency
    summary: "Proof bootstrap's external-binary behavior is unspecified"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md:109,272"
  - id: F006
    severity: concern
    category: under-specification
    summary: "Stand-in run-file states are under-specified, but step 12 depends on them"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md:213-214,245"
  - id: F007
    severity: note
    category: error-handling
    summary: "Pruning failure modes are enumerated"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md:299-308"
  - id: F008
    severity: note
    category: scope
    summary: "Runner behavior on a missing resume run is set in a process-contract section here"
    location: "project-documents/user/slices/110-slice.contract-proof-and-hardening.md:303"
---

# Review: slice — slice 110

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Architectural boundaries and writer model preserved

- **Writer model.** The proof Runner writes in-process. The Judge, the PM and the network path all go through `submit()`. Pruning opens stores read-only and writes nothing.
- **Squadron files.** Run-file deletion goes only through `sq runs prune`, so no part edits Squadron's run files directly. Every Squadron invocation uses non-TTY stdin (`DEVNULL`).
- **Dependency directions.** `process/run_pruning.py` is pure. `cli/prune.py` is the only module that knows both the selection rule and the store. `tenants.py` adds no new package edge. `amoeba.upstream` never imports `amoeba.process`.
- **Slice plan coverage.** The design covers the slice plan's success criteria: a lifecycle sequence through the public API, a restart mid-sequence, locality, and pruning policy.

### [CONCERN] Design is heavier than the slice must deliver

The slice's job is to prove the contract and prune paused runs. Several mechanisms handle cases it doesn't have or cover ground its dependencies already test:
- **D7's gap machinery.** It sets a cap of two discovered gaps, one public name each. It also defines a closure rule with `xfail(strict=True)` markers and issue filing, all for gaps that don't exist yet. "Stop for the PM and amend the design" already covers an unknown gap. Keep H1–H4 and drop the cap and the xfail protocol until a real gap appears.
- **Three new guard mechanisms.** The design adds the D1 public-import AST test, a `tenants.py` import-rule AST test, and a `run_pruning.py` layering AST test. It also adds a tenant-order check and an extension to `test_store_safety.py`. Only the D1 rule is the proof's deliverable. The `tenants.py` rule guards a move that the design itself says "adds no new package edge", so it can be cut.
- **D8's race analysis.** The re-link and resume-race discussion at line 303 is longer than the rule it supports. Reduce it to "`--yes` selects afresh; a missing run on resume is a failed command". The preview/`--yes` design already makes it safe.
- **Network subset.** Two `kill -9` scenarios plus the SSE equality check are justified by 109's hand-off. Keep one kill per process and cut anything beyond that.
- **H2 is not in the slice plan entry.** `record_runner_report` adds a new Store write method. It is justified by the evidence contract's "120 (or 110, if earlier)" deferral. The scope text at line 74 says "New behavior on any existing surface" is excluded, while H2 adds exactly that on the store surface. State the carve-out explicitly, or defer H2 to 120.

### [CONCERN] Selection rule is both "available to 120" and non-public

The Excluded section says "Initiative 120 may call the selection rule later". D7/H4 says `run_pruning`'s names are deliberately kept out of `amoeba.process.__all__`, and the substrate guide tells 120 authors to use only public roots (D1). A 120 author cannot call `select_prunable` through the documented surface. Either export it and document it, or say that 120 invokes `amoeba prune sq-runs` as a subprocess. As written, the integration point 120 is told to expect doesn't exist.

### [CONCERN] Scattered retention value in the proof, and a magic default outside config

D3 hard-codes "8 days before" in the stand-in so that step 12 passes `PRUNE_RETENTION` (7 days). D1 forbids the proof from importing `run_pruning`, so the proof cannot reference the constant. Changing `PRUNE_RETENTION` then breaks step 12 for a reason unrelated to the contract. The project rules say a value used in comparisons should be defined once, and defaults should sit at the config level. Either expose the retention through `ProcessSettings` (which the proof can read) or have the proof derive its age from the preview output. The design currently says settings come "when something needs to configure them", but the proof already needs it.

### [CONCERN] Proof bootstrap's external-binary behavior is unspecified

`standard_tenants` "captures the `sq` and `cf` version labels as before", and the bootstrap runs it in a subprocess with a temporary `HOME`. The design says no test runs the real `sq`, and a stub `sq` is placed on `PATH` only for step 12. It never says what the bootstrap does when `sq` or `cf` is absent or has no version output during steps 1–11. On a CI machine without either binary, the proof could fail to reach readiness, or it could silently record a placeholder label. State how the proof supplies these binaries (stubs on `PATH` for the whole run) or how the label capture behaves when they are missing.

### [CONCERN] Stand-in run-file states are under-specified, but step 12 depends on them

Step 12 expects the preview to report exactly one owned paused run kept (beta's), and exactly one candidate (alpha's). Steps 3 and 4 produce owned runs through `launch_review`, and recovery adopts one of them. The design never gives the status those stand-in run files carry, or the `updated_at` values for beta's run versus step 7's unowned run. If the `launch_review` files are `paused`, the kept count and candidate set change. State the `status` for each stand-in run file in D3 so that the step 12 assertions are derivable from the design.

### [NOTE] Pruning failure modes are enumerated

Every new I/O path has an explicit strategy. An unreadable store refuses the command. An unparseable run file is skipped and logged at WARNING. A missing `updated_at` means never a candidate. A missing, failing, timed-out or refusing `sq` leads to a re-read of the directory and `PRUNE_INCOMPLETE`. The harness fails loudly with captured output on any wait timeout, and an unplanned SSE drop fails the test. No NFR in the architecture applies to this slice's paths.

### [NOTE] Runner behavior on a missing resume run is set in a process-contract section here

D8 prescribes that a failed resume resolves the entry and blocks the node on a human. That binds initiative 120's Runner design from a slice that doesn't build the Runner. It is acceptable as a contract statement, but flag it in the guide as a requirement 120 must confirm. Don't present it as already settled.

### Run Digest

- Response length: 7279 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 221452 / 136588 / 84858 / 7043 / not computed
- Duration: 59.2 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
