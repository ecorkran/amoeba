---
docType: review
layer: project
reviewType: code
slice: question-record
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/141-slice.question-record.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261102
dateUpdated: 20261102
reviewedSha: ea81d0195833179dde56a99573f5f19f5e064fa0
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: false
turns: 2
promptTokens: 200434
cachedTokens: 16579
cacheWriteTokens: 183851
completionTokens: 2262
durationSeconds: 23.6
costUsd: 0.765599
costBasis: provider
squadronVersion: 0.24.12
categoriesNormalized: true
findings:
  - id: F001
    severity: note
    category: correctness
    summary: "Settlement on acknowledgment depends on the effect shape"
    location: "src/amoeba/store/questions.py:195-232"
  - id: F002
    severity: note
    category: architectural-decay
    summary: "Duplicated shape between `PlannedQuestion` and `QuestionCatch`"
    location: "src/amoeba/runner/ingest/outcome.py:64-76"
  - id: F003
    severity: note
    category: test-debt
    summary: "Private store access in test harnesses"
    location: "tests/question_harness.py:104-110"
  - id: F004
    severity: note
    category: consistency-rot
    summary: "Magic-number threshold reuse is correct, and truncation is conservative"
    location: "src/amoeba/runner/ingest/outcome.py:274-278"
  - id: F005
    severity: pass
    category: other
    summary: "Transactions, SQL safety and exception handling"
    location: "src/amoeba/store/sql_questions.py"
---

# Review: code — slice 141

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [NOTE] Settlement on acknowledgment depends on the effect shape

`_settle_question_on_acknowledgment` answers the record only when the acknowledgment is applied with no effect. It moves the link when a new block is written. A `StatusEffect` leaves the record untouched, and `tests/store/test_question_acknowledgment.py` asserts this. A pending record on a block that is resolved and acknowledged would then make `settle_pending` raise `QuestionInvariantError` on every tick. A grep of `src` found no `StatusEffect(` constructions, so the path is unreachable today. `test_the_judge_produces_only_these_acknowledgment_shapes` guards the decision and outcome vocabularies but not the effect types. A guard on the effect types, or an explicit comment at the call site, would stop a future producer from tripping the invariant.

### [NOTE] Duplicated shape between `PlannedQuestion` and `QuestionCatch`

`PlannedQuestion` (run_id, step, question, truncated) repeats the fields of `QuestionCatch` that ingest does not get from the entry. `_write_block` in `record.py` copies them one by one. This is acceptable because the runner plan and the store input are separate layers. If a field is added, both need editing.

### [NOTE] Private store access in test harnesses

`seed_question` and one acknowledgment test use `store._connection` with a pyright ignore, and the crash entry patches `Store._insert_question`. This is documented as deliberate, since the tests need to stage states the public API cannot reach. It couples the tests to store internals.

### [NOTE] Magic-number threshold reuse is correct, and truncation is conservative

`truncated` is `len(question) >= QUESTION_TAIL_CHARS`, measured on the raw text before `cut_to_bound`. The limit is defined once in `amoeba.process` and exported, and the boundary cases are parametrized in tests. A question of exactly 400 characters is flagged truncated even if it was not cut. That is a safe over-approximation and the comment states the intent.

### [PASS] Transactions, SQL safety and exception handling

All statements use bound parameters, and the column names are f-string constants, not user input. The one-block-one-question rule is enforced by a partial unique index. `record_question` is idempotent per `source_entry_id`. The mapper raises on unknown vocabulary values and does not default them. The new `try/except` in `mapping_questions._vocabulary` catches `ValueError` and re-raises as a typed error with `from`. No blanket catches were added. The Pydantic `answerer` section rejects null and unknown keys, and tests cover both.

### Run Digest

- Response length: 3273 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 2
- Tokens — prompt / cached / cache write / completion / reasoning: 200434 / 16579 / 183851 / 2262 / not computed
- Duration: 23.6 s
- Cost: $0.77 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5

## Resolution (20261102)

- **F001 — resolved.** A comment at the call site in `store/blocking.py` states the three acknowledgment shapes and the rule for each. `test_no_runner_module_produces_a_status_effect` fails if any module under `runner/` constructs a `StatusEffect`, so a future producer must be given a rule in `_settle_question_on_acknowledgment` first.
- **F002 — no change.** The review calls the duplication acceptable: the runner plan and the store input are separate layers.
- **F003 — no change.** The private access is deliberate; the tests stage states the public API cannot reach.
- **F004 — no change.** The review finds the threshold use correct and the over-approximation safe.
