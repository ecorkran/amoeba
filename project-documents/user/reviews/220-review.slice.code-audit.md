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
reviewedSha: 1105c7f45583a7b08c1ff7520d9d6e5ac7961eeb
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
effort: high
turns: 5
promptTokens: 296373
cachedTokens: 191461
cacheWriteTokens: 104904
completionTokens: 7835
durationSeconds: 67.7
costUsd: 0.51797
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: architectural-alignment
    summary: "Scope, boundaries and dependency direction match the architecture"
    location: "project-documents/user/slices/220-slice.code-audit.md#Technical Scope"
  - id: F002
    severity: concern
    category: under-specification
    summary: "Coverage and duplicate check collides with path-keyed tables in other sections"
    location: "project-documents/user/slices/220-slice.code-audit.md:257-264"
  - id: F003
    severity: concern
    category: under-specification
    summary: "D1 grouping of tests contradicts the longest-prefix coverage rule, and directory rows in `docs/` mismatch the check"
    location: "project-documents/user/slices/220-slice.code-audit.md:109-111"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Overweight for an effort-2, low-risk document slice"
    location: "project-documents/user/slices/220-slice.code-audit.md:41,82,211"
  - id: F005
    severity: note
    category: under-specification
    summary: "The 5a scan's source of verdicts is not stated"
    location: "project-documents/user/slices/220-slice.code-audit.md:132-138"
  - id: F006
    severity: note
    category: integration
    summary: "The `cli/` verdict has no named consumer"
    location: "project-documents/user/slices/220-slice.code-audit.md:215-224"
  - id: F007
    severity: note
    category: consistency
    summary: "The Technical Scope sentence on outputs conflicts with the later sections"
    location: "project-documents/user/slices/220-slice.code-audit.md:37"
---

# Review: slice — slice 220

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Scope, boundaries and dependency direction match the architecture

The slice settles the architecture's Current State table, which the architecture calls a guess. It changes no code, leaves the architecture document alone, and records differences in its own section 10. It has no prerequisites, matching the slice plan. Its outputs are the analysis document and any Squadron issues. The Provides section maps cleanly onto 221 to 224: delete list, store and program rows, answering and upstream rows, the Squadron-output readers and `sq` launch and poll code, and the inspection and read-view verdicts. D3 and D4 require nodes, journal entries, blocked states and the tick loop to appear in 5a or 5b, which are the dependencies named in the slice plan and architecture. The 182 and 180 decisions (D5, D7) follow the architecture's Related Work and Retired Work notes. The live-test classification (D8) serves the architecture's "live answering tests stay as the scenario A check" and 221's success criterion.

### [CONCERN] Coverage and duplicate check collides with path-keyed tables in other sections

The walkthrough greps every table row in the whole document whose first cell is a backticked `src|tests|scripts|docs` path. It then treats `uniq -d` hits as duplicate verdicts. The natural layouts of other sections key on paths too:
- Section 5 (dependencies of kept code) is likely to list the importing file first.
- Section 6 (slice 182 files) lists changed files, and some of them also have a section 2 row.
- Section 8 (live tests) lists each `tests/live/answering/*` file, which D8 gives its own verdict.
- Section 9 (move to Squadron) lists each unit.

Each of those rows is a second row for a path already in sections 2 to 4. That fails the "no path has two rows" rule and the walkthrough, even though the audit is correct. D8's `stays` and `waits on 223` are also not D2 verdicts, so they would fail walkthrough step 2.

Fix one of these:
- Say that only sections 2 to 4 may start a row with a repo path, and have the commands read only those sections.
- State that other sections put the path in a later column.
- State that D8's three words go in a separate column from the D2 verdict.

### [CONCERN] D1 grouping of tests contradicts the longest-prefix coverage rule, and directory rows in `docs/` mismatch the check

D1 says top-level `tests/*.py` files and shared harnesses are "grouped under the source unit they exercise". It also says a file's verdict comes from the longest row path that is a prefix of the file's path. A top-level `tests/test_x.py` is not a path-prefix child of `src/amoeba/x/`. Harnesses and `conftest.py` sit beside the tests they serve. So grouped tests either need one row per file, which is the several-hundred-row outcome D1 rejects, or need rows keyed on filename prefixes. The design says neither.

There is a second mismatch. The check lists `docs/*` with `ls -d`, which prints directories without a trailing `/`. D1 requires directory rows to end in `/`. A `docs/` subdirectory row would therefore be reported as `missing`.

Define how grouped tests are covered, for example filename-prefix rows such as `tests/test_inbox`. Make the `docs` listing add a trailing `/` for directories.

### [CONCERN] Overweight for an effort-2, low-risk document slice

The design has 8 decisions, 11 required sections and a 6-step walkthrough. Several parts are not in the slice plan's success criteria, and the plan asks only that every package and test directory has a verdict. Candidates to cut or defer:
- **Line totals per verdict.** This needs a counting script with its own rules (non-blank lines, no `__pycache__`, tests and src separately), and no consumer needs it. The slice plan and 221 to 224 work from verdicts, not sizes. The architecture's own table already gives the size baseline. If kept, make it one sentence ("approximate totals, optional") rather than a Summary requirement.
- **Section 11 "Scripts".** It has to hold the 5a scan and the coverage check, and the coverage check already appears in the Verification Walkthrough. Keep the scan command in section 11 and point the walkthrough to it, or the reverse.
- **Success Criteria and Technical Scope.** Both restate the same list as the Component Structure and the walkthrough. One home for each requirement is enough.

Only the first two items add mechanism. The third is document weight.

### [NOTE] The 5a scan's source of verdicts is not stated

The scan prints imports that do not resolve to a kept unit. It must therefore read verdicts from the audit's own tables, using the same D1 longest-prefix rule. Section 11 should say so. Otherwise "221 runs the same command after the cut and it must print nothing" has no defined input once the deleted files are gone. Resolving imports through `__init__` re-exports is the heaviest part of the scan. Keep it only if the kept packages actually re-export, such as `store`.

### [NOTE] The `cli/` verdict has no named consumer

Slices 222 to 224 expose their operations "through the CLI", and 222's criterion is `set_up` through the CLI. The Provides section names no consumer for the `src/amoeba/cli/` and console entry point verdicts. Those verdicts decide whether the CLI scaffold is reused or replaced. Add them to the 222 bullet. The architecture's "replaced by the operations" is only an expectation.

### [NOTE] The Technical Scope sentence on outputs conflicts with the later sections

Line 37 says the only other outputs are Squadron issues. State Management (line 98), Integration Requirements (line 251) and Implementation Notes (line 289) also add one-line notes to the 223 slice plan entry and possibly others. Align line 37 with those.

### Run Digest

- Response length: 6638 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 296373 / 191461 / 104904 / 7835 / not computed
- Duration: 67.7 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Resolution

- **[PASS] Scope, boundaries and dependency direction:** no change needed.
- **[CONCERN] Coverage and duplicate check collides with path-keyed tables:**
  - Component Structure now says only rows in sections 2 to 4 start with a repo path, and tables in sections 5 to 10 put any path in a later column.
  - Section 8 holds D8's word in its own column, not as a D2 verdict.
  - Walkthrough step 2 checks only the section 2 to 4 tables.
- **[CONCERN] D1 test grouping versus the longest-prefix rule, and `docs/` directories:**
  - D1 now groups tests by filename-prefix rows (for example `tests/test_observer_sq`). Files that share no prefix each get their own row.
  - A filename-prefix row has no trailing `/`.
  - The `docs` listing uses `ls -dp`, so directories carry a trailing `/`.
- **[CONCERN] Overweight:**
  - Line totals are removed from the Summary, Technical Scope, Patterns and Conventions, and the Development Approach.
  - Section 11 now holds only the 5a scan command. The coverage check lives only in the walkthrough.
  - Technical Scope's Included list is cut to one line pointing at Component Structure.
- **[NOTE] Where the 5a scan gets its verdicts:** D3 now says the scan reads verdicts from the section 2 to 4 tables by the D1 longest-prefix rule. It also says why re-export resolution is kept: `amoeba.store` re-exports its submodules' names.
- **[NOTE] The `cli/` verdict has no consumer:** added the `src/amoeba/cli/` and console entry point verdicts to the 222 bullet in Provides.
- **[NOTE] The outputs sentence conflicts with later sections:** the Overview sentence now names the one-line slice plan notes alongside the Squadron issues.
