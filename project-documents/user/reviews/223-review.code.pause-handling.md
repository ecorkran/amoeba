---
docType: review
layer: project
reviewType: code
slice: pause-handling
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/223-slice.pause-handling.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261110
dateUpdated: 20261110
reviewedSha: 500eb0d2a51f4e276e69034990e5c7402644edcb
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
diffTruncated: false
turns: 4
promptTokens: 466559
cachedTokens: 26932
cacheWriteTokens: 439623
completionTokens: 2359
durationSeconds: 25.0
costUsd: 1.877899
costBasis: provider
runId: run-20261110-p6-f6bd90d1
squadronVersion: 0.24.25
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: test-debt
    summary: "Test subprocesses inherit the whole shell environment"
    location: "tests/cli/test_pause_cli.py:76"
  - id: F002
    severity: concern
    category: architectural-decay
    summary: "Repeated and long-signature `noqa: PLR0913` suppressions signal missing parameter objects"
    location: "src/amoeba/operations/pause_results.py:79"
  - id: F003
    severity: note
    category: error-handling-observability
    summary: "Resume failure in `answer` is converted to a recorded `refused` result"
    location: "src/amoeba/operations/answer.py:101-106"
  - id: F004
    severity: note
    category: other
    summary: "Schema migration, JSON column parsing and the record-resume finality rule look sound"
    location: "src/amoeba/store/schema/002_pause_handling.sql"
---

# Review: code — slice 223

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Test subprocesses inherit the whole shell environment

`_run` builds the child environment as `{**os.environ, ...}`. This hands the full ambient environment to the `amoeba` subprocess, and through it to the fake `sq` and `cf`. The testing rules say to pass an explicit list of named variables and never inject the whole environment into a test process. The live tier already follows this: `tests/live/pause/harness.py` uses `pipeline_environment(os.environ)`, which builds a named list. The same pattern appears in `tests/test_sq_stub_run.py:50`, `tests/test_sq_stub_resume.py:55`, `tests/cli/test_set_up_cli.py:36` and `tests/operations/test_set_up_concurrent.py:27`. Most of those predate this diff, but `test_pause_cli.py` is new. Replace it with a small allowlist (for example `PATH`, `HOME`, `AMOEBA_HOME`, `PYTHONPATH`) and use the same helper everywhere.

### [CONCERN] Repeated and long-signature `noqa: PLR0913` suppressions signal missing parameter objects

`finish`, `resume_answer`, `_run`, `_assemble`, `_running` and `make_scratch` all suppress `PLR0913` for too many arguments. The same `store, config, deps, target, ...` bundle is passed through `pause_claim`, `pause_existing` and `pause_results`. A small context dataclass would remove the suppressions and shorten the signatures. The `PauseTarget` dataclass already exists, so folding `store`, `config` and `deps` into one context next to it would be a modest change. This is a maintainability issue, not a defect.

### [NOTE] Resume failure in `answer` is converted to a recorded `refused` result

`answer` catches the specific `SquadronError` raised by `resume`. It then records the resume as `refused` with the error text, because the answer is already committed. The comment gives a justification, so this satisfies rule (b) and is deliberate. `tests/operations/test_answer.py` covers it. The error is recorded and returned in the result but not logged, so an operator will only see it in the store. No action is required.

### [NOTE] Schema migration, JSON column parsing and the record-resume finality rule look sound

Migration 002 only adds nullable columns, and `EXPECTED_SCHEMA_VERSION` is bumped to 2. `tests/store/test_migrations.py` migrates a real version-1 store with rows and checks they survive. Every JSON column has a serializer and a parser that raises `StoreRowError` naming the column. `RECORD_RESUME` keeps `resumed` and `not_delivered` final, and the SQL binds all values as parameters. `tests/test_import_boundaries.py` now forbids `answering` from importing `store`, `config`, `operations` or `cli`, which matches the layering. Test coverage of the new operations is broad. It includes real-subprocess tests for process-group termination and CLI exit codes.

I found no FAIL-level defects. I read the pause-context, `cli-contract.md` and test-environment locations directly. For the other files I relied on the diff and the supporting tests it shows.

### Run Digest

- Response length: 3294 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 466559 / 26932 / 439623 / 2359 / not computed
- Duration: 25.0 s
- Cost: $1.88 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 4
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 4
- Finding-shaped matches — surviving validation: 4
