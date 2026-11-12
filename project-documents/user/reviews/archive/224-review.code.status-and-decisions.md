---
docType: review
layer: project
reviewType: code
slice: status-and-decisions
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/224-slice.status-and-decisions.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261111
dateUpdated: 20261111
reviewedSha: c58ccd2aafcc7eb213fa2430f955f9395b34bb18
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 38
diffTruncated: false
turns: 20
promptTokens: 2997113
cachedTokens: 2637440
completionTokens: 150200
reasoningTokens: 137096
durationSeconds: 786.1
costUsd: 0.141631
costBasis: alias_pricing
runId: run-20261111-p6-fe470d63
squadronVersion: 0.24.26
categoriesNormalized: true
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "`decisions` rejects citation ids the write path deliberately accepts"
    location: "src/amoeba/operations/decisions.py:182-196"
  - id: F002
    severity: concern
    category: architectural-decay
    summary: "A third copy of the identical `NonBlank` annotation"
    location: "src/amoeba/operations/status.py:68"
  - id: F003
    severity: concern
    category: consistency-rot
    summary: "The \"classes `handle_pause` acts on\" set is stated twice"
    location: "src/amoeba/operations/status_runs.py:40-46"
  - id: F004
    severity: note
    category: documentation-drift
    summary: "`Deps`' class docstring no longer describes `Deps`"
    location: "src/amoeba/operations/deps.py:44"
  - id: F005
    severity: pass
    category: error-handling-observability
    summary: "No subprocess runs inside a store transaction"
    location: "src/amoeba/operations/status.py:5-7"
  - id: F006
    severity: pass
    category: other
    summary: "Layer boundaries and store safety in the new tests"
    location: "tests/cli/test_read_side_cli.py"
  - id: F007
    severity: pass
    category: other
    summary: "Closed vocabularies and contracts are pinned mechanically"
    location: "tests/read_side_defined_once.py"
---

# Review: code — slice 224

**Verdict:** FAIL
**Model:** deepseek/deepseek-v4.1-flash
**Evidence:** 38 successful tool call(s) of 38 made; 223655 of 223655 diff characters reached the model

## Findings

### [FAIL] `decisions` rejects citation ids the write path deliberately accepts

`_cited` builds `offered` keyed by the passage's stored id (`P1`) and then does `offered.get(passage_id)` on the raw cited id, raising `StoreRowError` when it misses. But the write path never normalizes the ids it stores, and its validator explicitly tolerates non-canonical ones:

- `src/amoeba/answering/passages.py:392` — `check_citations` normalizes with `item.strip().upper()` before comparing, so `"p1"` or `" P1 "` passes validation.
- `src/amoeba/answering/decide.py:239` — `return Confirmed(answer.answer, answer.cited, checked)` returns the **raw** `answer.cited`, not the normalized list.
- `src/amoeba/operations/answering_settle.py:82` — `cited=decision.cited` passes that raw tuple to `settle_answered`.
- `src/amoeba/store/answers.py:225` — `serialize_cited(cited)` stores it verbatim.

So a model that emits `{"cited": ["p1"]}` is accepted, answered, and resumed — and then `amoeba decisions` raises `StoreRowError` from `_record`, which the CLI turns into `error: StoreRowError: ...` and exit 3. Because `records = tuple(_record(row, names) for row in rows)` (decisions.py:107) evaluates eagerly, one such row poisons the entire listing, not just its own record.

The project rule this violates is explicit ("Prefer lenient parsing over strict matching… a regex that silently fails on valid input is a bug"), and the review rules call out "several ways of doing the same thing": the write side folds case and whitespace, the read side requires exact bytes. The existing test only covers the canonical case — `tests/operations/test_decisions.py::test_an_automatic_record_names_its_passages_check_and_resume` seeds `cited=("r1",)` against a passage id of `"r1"`.

Fix by making the lookup agree with the validator (fold `passage_id.strip().upper()` before `offered.get`, or store normalized ids from `decide_answer`), and add a test with a lowercase or padded cited id.

### [CONCERN] A third copy of the identical `NonBlank` annotation

`_NonBlank = Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1)]` is defined at `src/amoeba/operations/status.py:68`, again at `src/amoeba/operations/decisions.py:57`, and a public, identical `NonBlank` already exists at `src/amoeba/config/user_config.py:29`. Three byte-identical definitions of the same constraint annotation, two of them private duplicates of a name that is already exported.

This is the "define it once" rule: a change to the blank-string policy in the config would silently not apply to the two read-side requests, and nothing mechanically catches the divergence. Import `NonBlank` from `config.user_config` (operations may import config) or hoist one shared definition.

### [CONCERN] The "classes `handle_pause` acts on" set is stated twice

`_HANDLED_BY_HANDLE_PAUSE = frozenset({UNHANDLED, CLAIM_STALE, ANSWERED_UNRESUMED})` in production is restated verbatim as `ACTED_ON` in `tests/operations/test_status_matches_handle_pause.py:42`. The test's copy is deliberately independent, so it does detect drift — but it is also the only place the two are compared, and a reader of `status_runs.py` has no pointer to the contract that says those three (and exactly those three) map to `handle_pause` in `next`. `docs/cli-contract.md` states the same three in prose. Consider having the cross-check test derive the set from a single exported definition, or reference `_HANDLED_BY_HANDLE_PAUSE` from the test (exported for that purpose), so there is one value and one place to change it.

### [NOTE] `Deps`' class docstring no longer describes `Deps`

The module docstring was correctly updated to say “the pause and read operations,” but the class docstring still reads `"""The injectable edges of ``handle_pause`` and ``answer``."""`, while the class now also carries `project_names` and `list_runs`, used only by `status` and `decisions` — neither of which is named. `test_import_boundaries` and the doc-contract tests do not cover this, so it will drift again. Name all four operations, or drop the enumeration.

### [PASS] No subprocess runs inside a store transaction

I verified the module docstring's ordering claim against the code rather than taking it on faith. `resolve_scope` (`status.py:95`) performs its `cf` lookups through `resolve_member` before opening any transaction, and `_scoped` (`status.py:124`) only reads. `status` then opens one `store.read()` for `open_questions`/`latest_rows_by_run`, closes it, and only afterwards calls `deps.list_runs()` and `place_runs`. `tests/operations/test_status.py::test_no_store_transaction_is_open_while_sq_is_asked` proves it mechanically by taking `store.write()` inside the `list_runs` fake. `decisions` (`decisions.py:88`) follows the same shape, with the comment at line 87 stating the invariant it keeps.

### [PASS] Layer boundaries and store safety in the new tests

`operations` imports `store`, `config` and `upstream` but never `cli`; `upstream/squadron/run_list.py` imports nothing from `operations` or `store`, keeping the new reader at the right layer (`tests/test_import_boundaries.py` enforces this). The new tests touch only throwaway databases: every fixture opens `Store.open(tmp_path / "...")`, `tests/conftest.py` pins `AMOEBA_HOME` to a fresh directory, and `tests/cli/test_read_side_cli.py` passes an explicit named variable list plus a temporary `HOME` rather than injecting the whole environment. The one `UPDATE members SET project_id = ...` in `_seed_one_answer` targets the fixture's own store. This satisfies the SQL and testing rules on production-database protection.

### [PASS] Closed vocabularies and contracts are pinned mechanically

The read side's new vocabularies each have exactly one defining module, and `tests/test_read_side_defined_once.py` fails if a class is defined twice or if any module other than `run_list.py` spells `"runs"`/`"list"` as string constants. `tests/store/test_schema_holds_no_mirrored_state.py` pins every `(table, column)` under one of four reasons and cross-checks the same list against `docs/store-contract.md`; `tests/test_contract_docs.py` extends the CLI-contract check to the three new commands, the new reject codes and the new outcome enums. `run_list.py` also correctly reads only stdout so `sq`'s real warning on stderr is not treated as an error, which `tests/upstream/squadron/test_run_list.py` verifies against the recorded stderr.

### Run Digest

- Response length: 7594 chars
- Response is newline-free: no
- Tool calls made: 38
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 548358
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 2997113 / 2637440 / not computed / 150200 / 137096
- Duration: 786.1 s
- Cost: $0.14 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
