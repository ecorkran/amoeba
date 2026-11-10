---
docType: review
layer: project
reviewType: code
slice: store-config-and-set-up
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/222-slice.store-config-and-set-up.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261110
dateUpdated: 20261110
reviewedSha: 70c6b7ae4e32f744a0686ccb5488a19dc9a8d49d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
diffTruncated: false
turns: 3
promptTokens: 330694
cachedTokens: 163674
cacheWriteTokens: 167016
completionTokens: 2838
durationSeconds: 27.9
costUsd: 0.722112
costBasis: provider
squadronVersion: 0.24.25
categoriesNormalized: true
findings:
  - id: F001
    severity: note
    category: architectural-decay
    summary: "Store and row helpers with no caller in `src`"
    location: "src/amoeba/store/row_values.py:27"
  - id: F002
    severity: note
    category: consistency-rot
    summary: "`ConfigError` raised for a member-level problem"
    location: "src/amoeba/operations/member_answering.py:25"
  - id: F003
    severity: note
    category: consistency-rot
    summary: "Test hard-codes the `-p` flag, and a `type: ignore` is used under strict pyright"
    location: "tests/operations/set_up_support.py:62"
  - id: F004
    severity: note
    category: other
    summary: "Overall conformance"
    location: "src/amoeba/cli/main.py"
---

# Review: code — slice 222

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [NOTE] Store and row helpers with no caller in `src`

`integer` and `decode_mapping` in `row_values.py`, and `member_settings` in `store/programs.py:85`, are only referenced by tests. The same goes for `answering_for` and `resolve_member` in `operations`, and the `INSERT_QUESTION` and `INSERT_ANSWER` statements in `sql.py`. The comments say these are staged for slices 223 and 226. Remove any that slice 223 or 226 does not end up using.

### [NOTE] `ConfigError` raised for a member-level problem

`_require_known_keys` raises `ConfigError` when a stored member refers to an authorize key the config no longer has. The problem is a mismatch between stored state and config, but `ConfigError` is documented as being about the config file. The CLI maps it to the same exit code as other failures, so behavior is correct. A dedicated error type would be clearer if later slices need to tell the two cases apart.

### [NOTE] Test hard-codes the `-p` flag, and a `type: ignore` is used under strict pyright

`FakeCf` and `tests/upstream/context_forge/test_project_of.py` hard-code `"-p"` instead of importing `CF_PROJECT_FLAG`. The same test file also uses `# type: ignore[arg-type]`, which is mypy syntax. Under strict pyright the right form is `# pyright: ignore[...]`, or the recording helper can be typed to return `CompletedProcess[str]`. Both are minor.

### [NOTE] Overall conformance

I read the ruff and pyright configuration in `pyproject.toml`, and it matches the required rule set (`BLE`, `ASYNC`, `B`, strict pyright). The code follows the project conventions:
- **Exception handling:** each handler either re-raises with a log, narrows to a specific exception with a justification, or sits at the process boundary in `main`.
- **Environment and config:** `AMOEBA_HOME` is read in one place, enforced by a test, and missing config keys fail with an error instead of falling back to a default.
- **SQL:** all values are bound parameters, and the SQL strings are built only from module constants.
- **Writes:** `set_up` runs the Context Forge calls before taking the write lock, and rolls back on any failure.
- **Tests:** each test gets a throwaway `AMOEBA_HOME`, there is a guard against real tool directories, and there is a concurrency test with eight processes.

### Run Digest

- Response length: 2583 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 330694 / 163674 / 167016 / 2838 / not computed
- Duration: 27.9 s
- Cost: $0.72 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 4
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 4
- Finding-shaped matches — surviving validation: 4
