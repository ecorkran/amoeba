---
docType: review
layer: project
reviewType: slice
slice: code-audit
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/220-slice.code-audit.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: e634b00f74d0547731e358596297fe9ae593cd4f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
effort: high
turns: 5
promptTokens: 295985
cachedTokens: 188853
cacheWriteTokens: 107124
completionTokens: 8085
durationSeconds: 68.2
costUsd: 0.529089
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: under-specification
    summary: "The D3 import scan cannot produce the rows the architecture requires, and it is claimed to be reproducible"
    location: "project-documents/user/slices/220-slice.code-audit.md:143-150"
  - id: F002
    severity: concern
    category: verification
    summary: "Coverage is claimed to be checkable by script, but the walkthrough only checks top-level entries"
    location: "project-documents/user/slices/220-slice.code-audit.md:125, 260-267"
  - id: F003
    severity: concern
    category: proportionality
    summary: "The design is heavier than a Low-risk, effort-2 audit needs"
    location: "project-documents/user/slices/220-slice.code-audit.md:125, 209-212, 279, 98-106"
  - id: F004
    severity: concern
    category: integration
    summary: "Provides-to-slices omits kept-code consumers the architecture names"
    location: "project-documents/user/slices/220-slice.code-audit.md:222-226, frontmatter interfaces"
  - id: F005
    severity: note
    category: under-specification
    summary: "The 182 verdict thresholds are judgment calls"
    location: "project-documents/user/slices/220-slice.code-audit.md:173-179"
  - id: F006
    severity: pass
    category: alignment
    summary: "Scope and layering match the architecture and the slice plan"
    location: "project-documents/user/slices/220-slice.code-audit.md#Technical-Scope"
  - id: F007
    severity: pass
    category: error-handling
    summary: "No new runtime I/O paths or NFRs"
    location: "project-documents/user/slices/220-slice.code-audit.md#State-Management"
---

# Review: slice — slice 220

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] The D3 import scan cannot produce the rows the architecture requires, and it is claimed to be reproducible

- **Required rows.** The architecture's central problem is that question records "point at nodes, journal entries and blocked states" and that launching "needs the tick loop". D4 and the success criteria require a section 5 row for each of the four. Walkthrough step 3 says the scan output must match section 5 "no more and no fewer".
- **Field and column coupling is not an import.** A `node_id` field, a foreign key or a column in the SQL schema is not an `amoeba.*` import, so a scan of imports will not find it. Those rows can only come from reading the code. That conflicts with the claim that dependencies "come from the code, not from reading it".
- **Re-exports.** D3 rejects grep because it "misses … re-exports through package `__init__` files". A plain AST import scan has the same gap. `from amoeba.store import X` resolves to the kept mixed package `amoeba.store`, even when `X` is re-exported from a deleted submodule. The design does not say how the scan resolves imported names through `__init__`.
- **Scan scope.** It is unclear whether "every `keep` and `rework` module" includes kept tests, harnesses, scripts, the console entry point and the packaged YAML. 221's criterion is "No kept module imports a deleted one", so the scan has to cover all of these.
- **Fix.** Add a second, hand-read category to section 5, "non-import coupling (fields, columns, schema, YAML)". It should hold the nodes, journal, blocked-state and tick rows that the scan cannot find. State that only the import category is reproducible. Say how names are resolved through `__init__` re-exports. Say that kept tests and scripts are in scope.

### [CONCERN] Coverage is claimed to be checkable by script, but the walkthrough only checks top-level entries

- D1 says row paths make "coverage checkable by script". The walkthrough loop checks only `src/amoeba/*/`, `tests/*/`, `tests/*.py`, `scripts/*` and `docs/*`.
- The mixed packages are `store/`, `runner/`, `runner/answering/`, `process/`, `upstream/`, `cli/`, `inspection/` and `program/`. Their nested modules are "checked by reading the tables".
- A module with no row is neither kept nor deleted. That is exactly the case that undermines the success criterion that 221 can take its delete list "without opening the code to decide anything".
- **Fix.** Replace the top-level loop with a file-level check. Enumerate every `*.py`, `*.yaml` and `*.sql` file under `src/amoeba`, `tests` and `scripts`, plus `docs/*`. For each one, require that some backticked row path is a prefix of it. This is the same loop run over `find` output, so it adds almost no effort. Step 7's line-total reconciliation can then be dropped (see the next finding).

### [CONCERN] The design is heavier than a Low-risk, effort-2 audit needs

- **Per-row line counts.** D1 and D10 require a line count on every row, "measured on the audit date". The plan asks only for a verdict and a one-line reason. The PM's stated need is "how much … survives", which per-verdict totals meet. Compute the totals from the path-to-verdict mapping with a script, and drop the hand-entered per-row numbers. That also removes walkthrough step 7, which only checks that the hand-entered numbers add up.
- **D9 and D10.** Neither is a real decision. D9 is one sentence ("record differences in section 10, don't edit the architecture"), already covered by the Excluded list. D10 is a measurement convention. Fold both into Patterns and Conventions.
- **Other restatement.** The Data Flow diagram and the Value section repeat Overview, Provides to Other Slices and the slice plan entry. They can go.
- **Test granularity.** Verdicts on about 60 top-level test files and every harness are justified by the plan's "every test directory" criterion. They can be grouped by the source unit they exercise, as section 3 already says. Per-file rows are needed only where a group splits.

### [CONCERN] Provides-to-slices omits kept-code consumers the architecture names

- **223 and `process/`.** The architecture says `process/` goes "apart from reading Squadron's output". It also says the launching and polling in `runner/` must be rewritten around `sq runs wait --json` and `sq run --resume`. The audit gives 223 only the `runner/answering/` and `upstream/` rows. Any reusable Squadron-output reader in `process/` and any `sq`-invocation code in `runner/` are the code 223's resume path starts from. Add those verdict rows to 223's interface, or say the audit will name them.
- **224 and `inspection/`.** The architecture says `inspection/` is "mostly replaced by `status` and `decisions`", so the audit's `inspection/` and `store/` read-view verdicts determine what 224 (Status and Decisions) reuses. 224 is not listed in the frontmatter `interfaces` or in Provides. The plan entry names only 221 to 223. Either list 224 as a consumer, or state that `inspection/` reuse is deliberately left to 224's own design.

### [NOTE] The 182 verdict thresholds are judgment calls

"Reuse parts" versus "redo" turns on whether the take group is "worth carrying" or "too small". The criterion is unmeasured, but the verdict is a single PM-readable decision, and each changed file still gets take, rewrite or drop. A one-line rule would remove the ambiguity. An example is "take group at or above N files or lines, or including the program passage kinds". It is not blocking.

### [PASS] Scope and layering match the architecture and the slice plan

- The slice keeps to the plan's assigned scope. It covers verdicts for `src` and tests, the imports of kept code into deleted code with replacements, the 182 verdict, the 180 confirmation and the Squadron issues.
- The four required dependencies (nodes, journal entries, blocked states, the tick loop) are named in D4.
- The architecture is left unedited and differences are recorded separately. This respects the architecture as the controlling document.
- The slice has no prerequisite slices, which matches the plan. It reads the 182 branch without changing it, and it files Squadron issues only under the plan's authorization.
- D8 carries the architecture's "live answering tests become the check on scenario A" into 221's criterion.
- D6 sets the Squadron-issue test so that an item already covered by `#299`, `#302`, `#303` or `#304` is not filed again.

### [PASS] No new runtime I/O paths or NFRs

The slice adds no runtime path and no message type, and it touches no path with an architecture NFR. Its only external calls are `git diff` and an optional `gh issue` call. The failure mode for `gh` is already handled: D6 and the success criteria require that a `squadron` row is either changed to `delete` with a reason or linked to a filed issue.

### Run Digest

- Response length: 7968 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 295985 / 188853 / 107124 / 8085 / not computed
- Duration: 68.2 s
- Cost: $0.53 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
