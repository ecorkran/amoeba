---
docType: review
layer: project
reviewType: code
slice: live-walkthrough
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/145-slice.live-walkthrough.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: f3b1dbb6446a3f4bef44961ad8edd81b7cdd6ccf
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
diffTruncated: false
turns: 6
promptTokens: 218119
cachedTokens: 104024
cacheWriteTokens: 114089
completionTokens: 2228
durationSeconds: 21.2
costUsd: 0.491185
costBasis: provider
squadronVersion: 0.24.16
categoriesNormalized: true
findings:
  - id: F001
    severity: note
    category: correctness
    summary: "Cost cap accepts \"inf\" and writes it unquoted into YAML"
    location: "scripts/answerer_walkthrough.py:111-118"
  - id: F002
    severity: note
    category: error-handling-observability
    summary: "Swallowed JSON error is justified and tested"
    location: "scripts/answerer_walkthrough.py:195-199"
  - id: F003
    severity: note
    category: security-hygiene
    summary: "Script failure handling and safety rules are followed"
    location: "scripts/answerer_walkthrough.py:111-205"
  - id: F004
    severity: note
    category: architectural-decay
    summary: "Test helper extraction removes duplication"
    location: "tests/runner/answering/sources_assembly.py"
---

# Review: code — slice 145

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [NOTE] Cost cap accepts "inf" and writes it unquoted into YAML

`read_live_settings` rejects `nan`, zero and negatives with `not cost > 0`, but `float("inf")` passes. The raw string is then written into `projects.yaml` as `max_cost_usd: inf`. Depending on how the config loader parses it, that either fails at load or silently removes the spend cap the walkthrough relies on. The parametrized test covers `lots`, `0`, `-1` and `nan` but not `inf`. Use `math.isfinite(cost) and cost > 0` and add `"inf"` to the test cases.

### [NOTE] Swallowed JSON error is justified and tested

The `except json.JSONDecodeError` branch catches a specific exception and carries a comment. It falls through to an explicit `SystemExit` that names the `cf get` step. This meets rule (b). `test_a_cf_get_without_a_project_id_stops_naming_the_step` exercises it with empty, non-JSON, `{}`, empty-id and list payloads.

### [NOTE] Script failure handling and safety rules are followed

`run_step` reports the failing step, the command and stderr, and leaves the partly built directory in place. `.env` is copied into the checkout only after the commit, and the template `.gitignore` ignores it. A test asserts the key never appears in the printed output. The script touches no production database and reads no production database URL variable. It sets `AMOEBA_STORE_DIR` and `CONTEXT_FORGE_DATA_DIR` to throwaway paths for every child process.

### [NOTE] Test helper extraction removes duplication

Moving the assembly helpers out of `test_sources.py` lets the new `test_walkthrough_fixture.py` reuse them, so the logic is not copied. The aliased imports in `test_sources.py` keep the existing call sites unchanged. The new fixture test uses real committed tree files and checks passage discovery, which is behavior rather than implementation. `test_question_tails_fixture.py` checks the captured fixture's shape.

### Run Digest

- Response length: 2573 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 218119 / 104024 / 114089 / 2228 / not computed
- Duration: 21.2 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 4
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 4
- Finding-shaped matches — surviving validation: 4
