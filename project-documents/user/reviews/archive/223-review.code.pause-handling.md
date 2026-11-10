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
reviewedSha: a61253044dc6a6e94fc63649534ea51eb0d8bc9f
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
diffTruncated: false
turns: 4
promptTokens: 467107
cachedTokens: 26932
cacheWriteTokens: 440171
completionTokens: 3686
durationSeconds: 36.9
costUsd: 1.89332
costBasis: provider
runId: run-20261110-p6-f6bd90d1
squadronVersion: 0.24.25
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: consistency-rot
    summary: "PM-answer precedent is ordered by a user-editable label string"
    location: "src/amoeba/answering/passages.py:333-342"
  - id: F002
    severity: concern
    category: type-contract-debt
    summary: "Run-file JSON is validated by hand at an external boundary"
    location: "src/amoeba/upstream/squadron/run_file.py:67-113"
  - id: F003
    severity: concern
    category: architectural-decay
    summary: "Context-sensitive `settle_waiting` and answer paths repeat result-building logic"
    location: "src/amoeba/operations/pause_claim.py:211-246"
  - id: F004
    severity: concern
    category: correctness
    summary: "`answer` is not atomic across its three store steps"
    location: "src/amoeba/operations/answer.py:101-118"
  - id: F005
    severity: concern
    category: security-hygiene
    summary: "Resume instruction text carries unescaped PM or answerer text into `sq`"
    location: "src/amoeba/operations/resume.py:128"
  - id: F006
    severity: note
    category: test-debt
    summary: "Live-test seed key uses `hash()`, which is nondeterministic across runs"
    location: "tests/live/answering/stage_harness.py:73-75"
  - id: F007
    severity: note
    category: test-debt
    summary: "Test `_run` helper has a convoluted HOME fallback"
    location: "tests/cli/test_pause_cli.py:62-86"
  - id: F008
    severity: note
    category: documentation-drift
    summary: "Stale reference in the `passages.py` docstring"
    location: "src/amoeba/answering/passages.py:1-6"
  - id: F009
    severity: pass
    category: other
    summary: "Concurrency and claim protocol"
    location: "src/amoeba/store/answers.py:settle_answered"
  - id: F010
    severity: pass
    category: other
    summary: "Exception handling and import boundaries"
    location: "src/amoeba/operations/processes.py:terminate_group"
---

# Review: code — slice 223

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] PM-answer precedent is ordered by a user-editable label string

`_pm_order` ranks same-slice precedent with `a.slice_label != slice_label`. The label is the free-text `"<index> <title>"` built in `pause_context._find_in_plans` from the CF plan entry name. It is stored in `questions.slice_label` and compared as a string. The project rule says never to use user-accessible labels as logical structure. If a slice is renamed in the plan, old PM answers silently stop counting as same-slice. The `"none"` sentinel (`NO_SLICE_LABEL`) is a second string-compared value in the same field. Consider matching on the slice index, stored in its own column, and keeping the title for display only.

### [CONCERN] Run-file JSON is validated by hand at an external boundary

The Python rules require Pydantic for file parsing. `read_run_facts` instead hand-walks the decoded JSON with `isinstance` checks and a `cast`. `AnswerRequest` and `UserConfig` use Pydantic, so this is the odd one out. The hand-rolled checks are careful and well tested against the real recording. A small frozen model with `extra="ignore"` would still cut the code and make the file's contract explicit.

### [CONCERN] Context-sensitive `settle_waiting` and answer paths repeat result-building logic

`_record_waiting` and `_settle_dead_claim_waiting` each hand-build `HandlePauseResult(WAITING_ON_PM, ...)` with the same fields. `pause_results.finish` builds the same result for the `Waiting` case. `NewQuestion` construction is also written out twice, in `start_new_claim` and `_record_waiting`. A shared helper for the waiting result would give DRY. Several `# noqa: PLR0913` suppressions (`finish`, `resume_answer`, `_run`, `_assemble`, `_running`, `make_scratch`) point to the same cause: parameter bundles such as `deps`, `config`, `store` and `target` are passed separately through every layer.

### [CONCERN] `answer` is not atomic across its three store steps

`answer()` finds the question in one read transaction, writes the PM answer in a second, and re-reads the question in a third. If the question vanished in between, the code raises a bare `ValueError`. `main()` does not catch that, so the user sees a traceback instead of an exit-3 error. The window is tiny and the schema has no deletes, so this is unlikely. Returning the row from the write transaction, or reading it inside the same one, would remove the unreachable branch.

### [CONCERN] Resume instruction text carries unescaped PM or answerer text into `sq`

The composed `"You asked: …\nAnswer: …"` string is passed as a single argv element via `resume_argv`. There is no shell, so there is no shell injection, and `test_instructions_are_one_argv_element...` covers quoting. If the answer text starts with `-`, it may still be read as an option by `sq`, depending on how `resume_argv` places it. It is safe in the tested layout because the text always starts with `You asked:`. I did not open `resume_argv`; confirm it passes the text as the value of `--instructions`.

### [NOTE] Live-test seed key uses `hash()`, which is nondeterministic across runs

`seeded-{abs(hash((question, slice_label)))}` changes with `PYTHONHASHSEED`. It is only used to make unique keys, so it is harmless, but a counter or a UUID would make failures reproducible.

### [NOTE] Test `_run` helper has a convoluted HOME fallback

`"HOME": str(_home(tmp_path)) if not (tmp_path / "home").exists() else str(tmp_path / "home")` is a confusing way to say "create the home once". Calling `_home` unconditionally would do the same, since it uses `exist_ok=True`.

### [NOTE] Stale reference in the `passages.py` docstring

The docstring now says "the pause context wires it to the caller's values", which is correct. CHANGELOG entries for slices 143 and 221 still mention `assemble_sources`. That is acceptable history, since `sources.py` is deleted and no live code references it.

### [PASS] Concurrency and claim protocol

The gate runs inside a single `BEGIN IMMEDIATE` transaction, and a lost claim is checked before the gate result is used. Every move out of `claimed` names the claim it holds. `record_resume` keeps `resumed` and `not_delivered` final. Tests cover the PM-wins, stalled-then-late-reply and limit-counting races.

### [PASS] Exception handling and import boundaries

Each `except` is specific and has an inline reason. The CLI catches the expected failures once, at the process boundary, and `SquadronError` is added to that list. The new `answering` entry in `FORBIDDEN` in `tests/test_import_boundaries.py` enforces the layering mechanically.

### Run Digest

- Response length: 5754 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 467107 / 26932 / 440171 / 3686 / not computed
- Duration: 36.9 s
- Cost: $1.89 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
