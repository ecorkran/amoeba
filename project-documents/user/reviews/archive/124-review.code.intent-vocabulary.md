---
docType: review
layer: project
reviewType: code
slice: intent-vocabulary
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/124-slice.intent-vocabulary.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: 64c49d0b95f1463fe846727e53dd35fd71eff571
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 73272
cachedTokens: 3232
cacheWriteTokens: 70038
completionTokens: 2875
durationSeconds: 23.8
costUsd: 0.314765
costBasis: provider
runId: run-20261024-p56-53bc46f9
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: typing
    summary: "New tests lack return annotations that strict pyright requires"
    location: "tests/runner/intent/test_apply_pending.py:41"
  - id: F002
    severity: concern
    category: testing
    summary: "Test module imports fixture data from a sibling test module"
    location: "tests/runner/intent/test_apply_pending.py:26"
  - id: F003
    severity: concern
    category: design
    summary: "`\"project\"` target string is defined twice"
    location: "src/amoeba/inspection/desired_states.py:15"
  - id: F004
    severity: note
    category: testing
    summary: "Listing row order depends on the store, and only the first row is tested"
    location: "src/amoeba/inspection/desired_states.py:41"
  - id: F005
    severity: note
    category: testing
    summary: "Ordering assertions in `test_read_listing.py` were loosened"
    location: "tests/inspection/test_read_listing.py:96"
  - id: F006
    severity: note
    category: design
    summary: "The `decide` guard matches the design and is well covered"
    location: "src/amoeba/runner/decide.py:113"
---

# Review: code — slice 124

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] New tests lack return annotations that strict pyright requires

The Python rules include `tests/` in strict pyright, and zero errors blocks merge. Several new helpers have missing or `Any` return types:
- `spy(project_id: str)` in `test_no_pending_intents_returns_zero_without_reading_the_tree` has no return annotation.
- `_interpret(body, row)` in `tests/runner/intent/test_interpret_merge.py` has no return annotation.
- `_intent(...) -> Any` in `tests/runner/test_tick_intents.py` and the `Any`-typed `interpret` replacement in `_break_interpret` hide the real `Message` and `Interpretation` types.
- `_rig(..., *planners: object)` in `tests/runner/test_tick_governance.py` types planners as `object`, then assigns them to `rig.planners`.

Annotate these with `Message`, `Interpretation` and `Planner`. The project has no `# type: ignore` waivers for them.

### [CONCERN] Test module imports fixture data from a sibling test module

`from .test_interpret_merge import CASES` couples two test files. `CASES` is then sliced by magic indices (`case[1:3] + case[4:]`, `case[3] is APPLIED`). Reordering a column in `CASES` would silently break the parametrization. Move `CASES` into a support module such as `intent_support.py`. Make it a small named dataclass or `NamedTuple` instead of an anonymous tuple.

### [CONCERN] `"project"` target string is defined twice

`PROJECT_TARGET = "project"` repeats the value of `TargetKind.PROJECT` in `runner/intent/vocabulary.py`. The module deliberately avoids importing the Runner, so this is defensible. But the project rule says a value used in lookups should be defined once. Either note the intentional duplication, or move the shared constant to a neutral module. The "listing imports nothing from the runner" test only greps source text for `amoeba.runner`, so it is easy to defeat. An AST import check would be sturdier.

### [NOTE] Listing row order depends on the store, and only the first row is tested

The docstring promises "project target first, then by node id", but the function does no sorting. It relies on `Store.desired_states` ordering, which isn't in this diff. The test only asserts that the project row is first. Add an assertion on node-row order, or sort explicitly.

### [NOTE] Ordering assertions in `test_read_listing.py` were loosened

List equality became set equality plus a check on the last row. The seeded desired-state intent made the original exact lists impossible, so the change is reasonable. The test still proves the split-read property through `as_of_seq` and the last-row check.

### [NOTE] The `decide` guard matches the design and is well covered

The current-step guard raises `ValueError` for non-current, held, excluded and unknown nodes, and the tests cover each. `apply_pending_intents` is atomic per intent. A tick-level test checks that a failure leaves the intent pending and raises one project-scoped escalation. The new `HumanStepPlanner` in `PRODUCTION_PLANNERS` is gated on drive, with a test that linking a project blocks nothing.

### Run Digest

- Response length: 3696 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 73272 / 3232 / 70038 / 2875 / not computed
- Duration: 23.8 s
- Cost: $0.31 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
