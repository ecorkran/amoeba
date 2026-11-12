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
reviewedSha: 160f8ca294376aae8969f5ceb7028441f4307e07
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
diffTruncated: false
turns: 3
promptTokens: 464273
cachedTokens: 16698
cacheWriteTokens: 447571
completionTokens: 2447
durationSeconds: 26.2
costUsd: 1.909013
costBasis: provider
runId: run-20261110-p6-f6bd90d1
squadronVersion: 0.24.25
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: architectural-decay
    summary: "Dead `refused` accumulator in `settle`"
    location: "src/amoeba/operations/answering_settle.py:71-78"
  - id: F002
    severity: concern
    category: security-hygiene
    summary: "F-string SQL in the live test harness"
    location: "tests/live/answering/stage_harness.py:107-113"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "`answer` is not atomic across record and resume"
    location: "src/amoeba/operations/answer.py:95-110"
  - id: F004
    severity: note
    category: consistency-rot
    summary: "Redundant expression in `handle_existing`"
    location: "src/amoeba/operations/pause_existing.py (WAITING_ON_PM branch)"
  - id: F005
    severity: note
    category: type-contract-debt
    summary: "Weak runtime narrowing in `_waitable`"
    location: "src/amoeba/operations/processes.py (`_waitable`)"
  - id: F006
    severity: note
    category: test-debt
    summary: "Process-boundary size and test coverage"
    location: "src/amoeba/cli/main.py"
  - id: F007
    severity: pass
    category: other
    summary: "Exception handling, typing and layering conventions"
    location: "src/amoeba/operations"
---

# Review: code — slice 223

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Dead `refused` accumulator in `settle`

The `gate` closure inside `settle` appends each refusal to a local `refused` list, and nothing reads the list. `settle_answered` already returns the `GateRefusal`, and `_refusal_detail` uses that return value. The list and the closure's side effect are dead code and should be removed. The closure can then be a plain `lambda prior: evaluate_gate(...)`.

### [CONCERN] F-string SQL in the live test harness

`Settled` reads the store with `f"... WHERE run_id = '{self.run_id}'"`. The run id is minted locally and the connection is read-only, so there is no real injection risk. The project and SQL rules still say to always use parameterized queries. `store_rows` takes only a statement string, so it can't accept parameters. Give it a `params` argument and use `?` placeholders. That removes the pattern for anyone who copies it.

### [CONCERN] `answer` is not atomic across record and resume

`answer` records the PM answer in one transaction and then calls `resume` in a separate call. The design accepts this: the module docstring says that if `resume` raises `SquadronError`, the next call delivers the answer. Two things are worth tightening:
- The CLI reports only `error: SquadronError` and exit 3. The PM isn't told that the answer was saved. Print a note on stderr, or catch the error in `answer()` and return `RECORDED` with an unresolved resume.
- The `ValueError("question ... vanished")` branch is unreachable and untested.

### [NOTE] Redundant expression in `handle_existing`

`reason = None if existing.waiting_reason is None else existing.waiting_reason` is equal to `existing.waiting_reason`, so it can be simplified.

### [NOTE] Weak runtime narrowing in `_waitable`

`_waitable` uses `hasattr` checks and then `cast`. The kept `ChildHandle` type does not expose `wait` or `pid`, so this works. It is a trust-me cast, though. If you widen `ChildHandle` or `PopenFactory` upstream, you can drop the `cast`.

### [NOTE] Process-boundary size and test coverage

The new `handle_pause`/`answer` subcommands have subprocess tests with fake `sq` and `cf`. They cover exit codes 0, 1, 2 and 3, a live tier, and docs-parity tests that tie the contract docs to the enums. Coverage of the new paths looks solid.

### [PASS] Exception handling, typing and layering conventions

Every `try/except` I saw catches a specific type and has a justifying comment, for example in `terminate_group`, `read_run_facts` and `resolve_slice`. Signatures are fully typed with `|` unions. `SQL` values are bound parameters, and the state vocabulary comes from enums. The new import-boundary test now forbids `answering` from importing `store`, `config`, `operations` or `cli`.

I read only the `refused` and `WHERE run_id` matches in the source. The other findings come from the diff text.

### Run Digest

- Response length: 3410 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 464273 / 16698 / 447571 / 2447 / not computed
- Duration: 26.2 s
- Cost: $1.91 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
