---
docType: review
layer: project
reviewType: code
slice: the-gate-and-answer-submission
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/142-slice.the-gate-and-answer-submission.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261102
dateUpdated: 20261102
reviewedSha: 14c9ef623eaf1e4c5ebf2e7de36dc63729e69436
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 56475
cachedTokens: 3232
cacheWriteTokens: 53241
completionTokens: 1847
durationSeconds: 17.0
costUsd: 0.235481
costBasis: provider
squadronVersion: 0.24.13
categoriesNormalized: true
findings:
  - id: F001
    severity: pass
    category: correctness
    summary: "Gate runs atomically under the write lock"
    location: "src/amoeba/store/answer_submission.py:84-100"
  - id: F002
    severity: pass
    category: test-debt
    summary: "Pure gate with test coverage"
    location: "src/amoeba/runner/answering/gate.py:34-56"
  - id: F003
    severity: note
    category: correctness
    summary: "Missing question text raises before the state check"
    location: "src/amoeba/store/answer_submission.py:94-97"
  - id: F004
    severity: note
    category: type-contract-debt
    summary: "Mutable list on a frozen settings model"
    location: "src/amoeba/runner/project_config.py:49-51"
  - id: F005
    severity: note
    category: consistency-rot
    summary: "Decision string duplicated across the layer boundary"
    location: "src/amoeba/store/question_models.py:35-39"
  - id: F006
    severity: pass
    category: type-contract-debt
    summary: "Config validation and start-up probe wiring"
    location: "src/amoeba/runner/project_config.py:36-52"
---

# Review: code — slice 142

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Gate runs atomically under the write lock

`submit_answer` opens `BEGIN IMMEDIATE` and then reads the record, checks that the block is open, counts prior answers, runs the gate and writes. The resolution slot, the submission row and the `answered` state commit together, and the crash tests inject a failure into each write plus the gate to confirm a full rollback. The prior-answer count excludes the record being submitted, so a replay settles instead of double-counting. Two concurrent submissions therefore cannot both pass the limit.

### [PASS] Pure gate with test coverage

`evaluate_gate` has no I/O and a single normalization definition. The tests cover limit boundaries, limit-before-term precedence, configured term order, case and whitespace folding, substring matching and the empty term list. A purity test guards the module against I/O.

### [NOTE] Missing question text raises before the state check

`_gate_and_write` raises `ValueError` for a record with no question text before it checks whether the record is still open. A replayed call on an already settled record with no text raises instead of returning `SETTLED`. In practice open records always carry text, so this is low risk. Moving the state check first would make the outcomes more consistent.

### [NOTE] Mutable list on a frozen settings model

`AnswererSettings` is `frozen=True`, but `reserved_terms` is a `list`, which can still be mutated in place. A `tuple[...]` would make the immutability real. This is minor because the gate only reads the list.

### [NOTE] Decision string duplicated across the layer boundary

`ANSWER_DECISION = "resume"` repeats the Runner's `ResolutionDecision.RESUME` value, because the store cannot import the Runner. The duplication is documented, and `test_the_answer_decision_is_the_runners_resume` pins the two together, so drift will fail a test. This is acceptable.

### [PASS] Config validation and start-up probe wiring

`answer_limit` and `reserved_terms` are required with no silent defaults. Strict types, `ge=1` and non-blank terms are enforced at load, and the parametrized tests assert each failure's key path. `runner_tenant` runs the answering probe only when an answerer is configured, and the tests cover the run, fail and skip cases. Migration 014 is nullable, has a test, and the schema version is bumped.

### Run Digest

- Response length: 2837 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 56475 / 3232 / 53241 / 1847 / not computed
- Duration: 17.0 s
- Cost: $0.24 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

## Resolution (20261102)

- **F003 — resolved.** `submit_answer` now checks the record's state before its question text, so a replay on an already settled record with no text returns `settled`. An open record with no text still raises `ValueError`. `test_a_settled_record_with_no_question_text_settles_instead_of_raising` covers it.
- **F004 — resolved.** `AnswererSettings.reserved_terms` is a `tuple[str, ...]`, so the frozen model is immutable all the way down. A YAML list still loads; code that builds the settings passes a tuple.
- **F005 — no change.** The review calls the duplication acceptable: the store cannot import the Runner, and `test_the_answer_decision_is_the_runners_resume` fails if the two strings drift.
