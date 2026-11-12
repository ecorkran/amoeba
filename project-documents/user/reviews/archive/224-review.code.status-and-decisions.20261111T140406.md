---
docType: review
layer: project
reviewType: code
slice: status-and-decisions
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/224-slice.status-and-decisions.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261111
dateUpdated: 20261111
reviewedSha: 4518f19cd9a336e56a0223f9438c793edb8c8789
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 41
diffTruncated: false
turns: 20
promptTokens: 2888637
cachedTokens: 2429824
completionTokens: 119103
reasoningTokens: 108231
durationSeconds: 610.6
costUsd: 0.136525
costBasis: alias_pricing
runId: run-20261111-p6-fe470d63
squadronVersion: 0.24.26
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: architectural-decay
    summary: "`RUN_ONLY_CLASSES` is defined and never used"
    location: "src/amoeba/operations/pause_class.py:47-53"
  - id: F002
    severity: concern
    category: consistency-rot
    summary: "The `pm_answer` kind is spelled twice instead of using `PassageKind.PM_ANSWER`"
    location: "src/amoeba/operations/decisions.py:56"
  - id: F003
    severity: concern
    category: consistency-rot
    summary: "`OUTPUT_HEAD_CHARS` and `output_head` are duplicated between the two upstream readers"
    location: "src/amoeba/upstream/squadron/run_list.py:35"
  - id: F004
    severity: note
    category: test-debt
    summary: "`CfAnswer.TIMES_OUT` is handled but never exercised"
    location: "tests/operations/status_support.py:114"
  - id: F005
    severity: note
    category: error-handling-observability
    summary: "Store invariant violations in the read paths raise `ValueError`, not `StoreRowError`"
    location: "src/amoeba/operations/status_runs.py:184"
---

# Review: code — slice 224

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash
**Evidence:** 41 successful tool call(s) of 41 made; 223041 of 223041 diff characters reached the model

## Findings

### [CONCERN] `RUN_ONLY_CLASSES` is defined and never used

`RUN_ONLY_CLASSES: frozenset[PauseClass]` is declared with a comment ("The classes decided from the run alone, before any membership or row is known") but is referenced nowhere: not in `pause_class.py` (which uses `classify_run_only`, `run_facts_needed` and `classify_no_row`), not in `pause_eligibility.py`, `status_runs.py`, or any test — a repository-wide search returns only the definition. It is dead code that also risks drifting out of step with `classify_run_only`'s return values; either delete it or have `classify_run_only`'s contract reference it.

### [CONCERN] The `pm_answer` kind is spelled twice instead of using `PassageKind.PM_ANSWER`

`_PM_ANSWER_KIND = "pm_answer"` in `decisions.py` duplicates `PassageKind.PM_ANSWER = "pm_answer"` in `src/amoeba/answering/passages.py:33`, which is the canonical declaration of that vocabulary ("The `kind:` words of 140's `passages.md` format"). This is the value the CLI contract freezes as output (`docs/cli-contract.md`: "`kind` is `pm_answer` for a PM precedent"), so a rename of the enum member would leave the wire value silently different in the two places. It is also exactly the pattern AGENTS.md forbids ("Never scatter comparison values across code … define it once … and reference that definition everywhere"). `operations` may already import `amoeba.answering` (`decisions.py` imports `AnsweredBy, PassageRef` from it), so `PassageKind.PM_ANSWER` is available here with no boundary change.

### [CONCERN] `OUTPUT_HEAD_CHARS` and `output_head` are duplicated between the two upstream readers

`run_list.py` declares `OUTPUT_HEAD_CHARS: Final = 200` with the identical meaning and value as `src/amoeba/upstream/context_forge/cli_call.py:18`, and then reimplements `cli_call.output_head` inline at `run_list.py:114` (`(completed.stdout or completed.stderr)[:OUTPUT_HEAD_CHARS]`) and again at `:123`. Nothing imports the other's constant, so the bound that keeps a failure detail one line long, and the "whichever stream carried output" rule, now live in two places. Importing `OUTPUT_HEAD_CHARS`/`output_head` from `amoeba.upstream.context_forge.cli_call` across packages inside `upstream` is permitted by `tests/test_import_boundaries.py` (only `answering`, `config`, `store`, `operations` and `cli` are forbidden to `upstream`).

### [NOTE] `CfAnswer.TIMES_OUT` is handled but never exercised

`FakeCf.__call__` has a `TIMES_OUT` branch (raising `subprocess.TimeoutExpired`), and the slice design (D4) says a `project_of` *timeout* is `unplaced_runs` / `lookup_failed`. No test passes `CfAnswer.TIMES_OUT`; only `CfAnswer.FAILS` is exercised, which reaches the same `unplaced` path through `run_cf`'s `OSError`/exit-code handling rather than through the timeout branch of `run_cf`. The behaviour is close enough to covered that this is informational, but the timeout-specific path (the one D4 calls out explicitly) has no test.

### [NOTE] Store invariant violations in the read paths raise `ValueError`, not `StoreRowError`

An `answered` question with no answer row makes `classify_pause` raise `ValueError` (`pause_class.py:148`) and `_resume_text` raise `ValueError` (`status_runs.py:184`); a `pm_marker` with no row makes `read_marker` raise `ValueError` (`store/decisions.py:40`). `status`'s docstring promises `StoreError` for store problems, and `ValueError` is not in the CLI's caught tuple, so such a row would crash with a traceback instead of the documented `error: <ExceptionName>: …` exit-3 line. `handle_pause` guards its own copy of this case with `StoreRowError`. This matches the existing style elsewhere (`pause_results.py`, `answer.py` use `ValueError` for "impossible" invariants), so it is flagged as an observation rather than a defect — but the two sibling checks in the same slice (`handle_pause.py` raising `StoreRowError`) show the choice is inconsistent within this slice alone.

### Run Digest

- Response length: 5020 chars
- Response is newline-free: no
- Tool calls made: 41
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 432328
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 2888637 / 2429824 / not computed / 119103 / 108231
- Duration: 610.6 s
- Cost: $0.14 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
