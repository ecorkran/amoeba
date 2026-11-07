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
reviewedSha: ac164531af8d48fa1391e7cb78b93372946e679d
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
effort: high
turns: 6
promptTokens: 292961
cachedTokens: 192086
cacheWriteTokens: 100867
completionTokens: 6836
durationSeconds: 58.0
costUsd: 0.491895
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Alignment with the architecture's goals and the Current State table"
    location: "project-documents/user/slices/220-slice.code-audit.md#Overview"
  - id: F002
    severity: pass
    category: integration
    summary: "Dependency direction and integration points"
    location: "project-documents/user/slices/220-slice.code-audit.md#Integration-Points"
  - id: F003
    severity: concern
    category: under-specification
    summary: "The 5a scan is promised to 221 as a post-cut check, but it cannot resolve imports of units that no longer exist"
    location: "project-documents/user/slices/220-slice.code-audit.md:129-138"
  - id: F004
    severity: concern
    category: verification
    summary: "The coverage check in the Verification Walkthrough is weaker than the criterion it verifies"
    location: "project-documents/user/slices/220-slice.code-audit.md:256-264"
  - id: F005
    severity: concern
    category: proportionality
    summary: "The design is heavier than an effort-2, low-risk audit needs"
    location: "project-documents/user/slices/220-slice.code-audit.md:94"
  - id: F006
    severity: note
    category: specification
    summary: "D5's verdict rule keys on one module"
    location: "project-documents/user/slices/220-slice.code-audit.md:173-177"
---

# Review: slice — slice 220

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Alignment with the architecture's goals and the Current State table

The audit is read-only and judges every unit against scenarios A, B, C and set-up. It takes "Small" as the tie-breaker (Special Considerations) and settles the architecture's Current State table row by row, recording differences in section 10 instead of editing the architecture. The architecture's specific expectations all have a home:
- Nodes, journal entries, blocked states and the tick loop must appear in 5a or 5b (D3).
- Slice 182 gets a verdict (D5).
- Slice 180's pipeline delete is confirmed or reversed (D7).
- The live answering tests are the scenario A check (D8).
- Squadron issues `#299`, `#302`, `#303` and `#304` are not duplicated (D6).

Nothing here designs the store or the operations. D4 flags uncovered replacements in section 10 and does not design them.

### [PASS] Dependency direction and integration points

The slice has no slice prerequisites. "Provides to Other Slices" lines up with what each consumer needs:
- 221 gets the delete list and the scan command.
- 222 gets the `store/` and `program/` rows.
- 223 gets the `answering/`, `upstream/`, `process/` and `runner/` launch/observe/resume rows, plus the 182 groups.
- 224 gets the `inspection/` and read-view verdicts.

The 223 plan-entry note matches the slice plan's statement that 182 is decided by the audit. The `gh` dependency is declared and limited to filing issues. No NFR in the architecture applies, because the slice has no runtime path.

### [CONCERN] The 5a scan is promised to 221 as a post-cut check, but it cannot resolve imports of units that no longer exist

D3 says 221 reruns the same command after the cut and it "must print nothing". The scan resolves each imported name through package `__init__` re-exports to its defining submodule and judges that submodule's verdict. After the cut, the defining submodule of a deleted unit is gone, so the scan cannot resolve it. A kept module that still does `from amoeba.store import X` would then be skipped or crash, and the output stays empty either way. That would defeat the slice plan's 221 criterion, "No kept module imports a deleted one".

The design should say how the scan treats an `amoeba.*` import that fails to resolve. The simplest rule is to print it as a hit, so empty output means every import resolved to a kept unit. That rule also covers the bare package imports 5a currently hands off to 5b. Alternatively, D3 could stop promising the pre-cut command for post-cut use and leave 221 to specify its own check.

### [CONCERN] The coverage check in the Verification Walkthrough is weaker than the criterion it verifies

The Success Criteria say every file maps to exactly one row by the D1 longest-prefix rule. Walkthrough step 1 has three problems:
- **Document-wide matching:** the awk script collects every backticked `src|tests|scripts|docs/` path anywhere in the audit, including prose in sections 5–11. A single mention like `` `src/amoeba/store/` `` in 5b would mark every file under it as covered, even with no verdict row.
- **No path-boundary rule:** `index($0, r) == 1` is a raw string prefix. A row `src/amoeba/store/foo` also matches `src/amoeba/store/foo_bar.py`. D1's longest-prefix rule has the same ambiguity, since it doesn't say whether directory rows end in `/`.
- **At-least-one only:** the check can't detect "exactly one".

The walkthrough can therefore pass while a file has no verdict, which is the failure it exists to catch. Two small changes fix this: restrict the parse to table rows (lines starting with `|`), and state in D1 that directory rows end in `/`. Neither adds a mechanism.

### [CONCERN] The design is heavier than an effort-2, low-risk audit needs

The slice plan entry asks for a verdict and reason per package and test directory, kept-code dependencies with replacements, a 182 verdict, and Squadron issues. The design adds an 11-section document and eight decisions. It also adds three scripts in section 11 (the import scan, the coverage check and the line totals) and a line-total mechanism built on the D1 longest-prefix rule (line 210). Items the plan does not ask for and no consumer needs:
- **Line-total script:** the totals exist only to show the PM how much survives. Per-verdict totals could be a one-off `wc -l` pass over the final tables. The longest-prefix mapping is then needed only for the coverage check, and a committed script isn't required for either.
- **Rework effort 1–5** (lines 49, 123, 236): the plan wants the size of the rework "known", but a per-row score is false precision at audit time. 222 and 223 will estimate their own work. A rough per-package size, or a flag for rows needing re-keying, would do.
- **Per-rule verdicts for `tests/test_import_boundaries.py`** (line 109) and the three-way `stays`/`waits`/`delete` file verdicts in D8 are fine on their own. Together with the above they push a single document past what the slice's effort supports.

Cut or defer the line-total script and the effort scores. Keep the 5a scan, because 221 consumes it.

### [NOTE] D5's verdict rule keys on one module

"Reuse parts" requires that the take group contain the program passage kinds module. The architecture wants two things from 182: the passage kinds and the concept read. If the passage kinds module lands in rewrite but other files are takeable, the rule yields "redo" even though some of the branch is reusable. That is probably fine, because section 6 still records the groups for 223. The rule should say so explicitly, so the verdict word doesn't hide takeable files.

### Run Digest

- Response length: 6614 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 292961 / 192086 / 100867 / 6836 / not computed
- Duration: 58.0 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
