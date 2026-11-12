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
reviewedSha: 2322a065db613969d68bcaf6c4525b9badb59772
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 36
diffTruncated: false
turns: 20
promptTokens: 2882336
cachedTokens: 2442240
completionTokens: 126517
reasoningTokens: 122576
durationSeconds: 924.2
costUsd: 0.137962
costBasis: alias_pricing
runId: run-20261111-p6-fe470d63
squadronVersion: 0.24.26
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: consistency-rot
    summary: "Two lines in the new `cf` project reader exceed the project's 88-character line length"
    location: "src/amoeba/upstream/context_forge/projects.py#_id_and_name"
  - id: F002
    severity: note
    category: correctness
    summary: "The `prompt_only` skip is now decided after the `other_member` check, which changes the reported reason for one corner case"
    location: "src/amoeba/operations/pause_eligibility.py#_member_checks"
  - id: F003
    severity: note
    category: consistency-rot
    summary: "The CLI now has two JSON serialization conventions for its result types"
    location: "src/amoeba/cli/main.py#_print_model"
  - id: F004
    severity: note
    category: other
    summary: "Row slicing in the decisions read derives its column widths from splitting the SQL column constants"
    location: "src/amoeba/store/decisions.py#_decision"
  - id: F005
    severity: pass
    category: architectural-decay
    summary: "One definition per concept, with mechanical guards that keep it that way"
    location: "src/amoeba/operations/pause_class.py#classify_pause"
---

# Review: code — slice 224

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash
**Evidence:** 36 successful tool call(s) of 36 made; 227293 of 227293 diff characters reached the model

## Findings

### [CONCERN] Two lines in the new `cf` project reader exceed the project's 88-character line length

The `redirect_to_...` — the two `entry.get(...)` lines each carry an inline `# pyright: ignore[...]` comment. Counted character by character they are 105 and 101 characters respectively, against `line-length = 88` in `pyproject.toml`. The lint selection there is `["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]` with no `ignore` list, so `E501` is in scope, and the Python rules make `ruff check` a pre-commit and CI gate. Neither line is splittable by the formatter because the trailing comment is what makes it long, so the only fixes are shortening the ignore (a bare `# pyright: ignore` or a narrower code list) or hoisting the annotation. The prose in the same file's docstring is not the issue; the ignore comments are. I could not execute `ruff` to confirm the failure, but the line lengths themselves are verifiable from the file text.

### [NOTE] The `prompt_only` skip is now decided after the `other_member` check, which changes the reported reason for one corner case

223 returned `SkipReason.PROMPT_ONLY` from `read_run_facts` *before* reading the question row; the new code reads the row first, checks `OTHER_MEMBER`, and only then applies `classify_no_row(facts)`. Dropping `prompt_only` when a row exists is the intended D3 behavior ("No row, `execution_mode` prompt-only") and matches `classify_pause`, so the main change is right. The residual difference is a prompt-only run whose row belongs to a different member: it now reports `OTHER_MEMBER` where it used to report `PROMPT_ONLY`. Neither outcome writes anything and the new answer is arguably the more informative one, but no test in `tests/operations/test_pause_eligibility.py` covers the combination and no comment records the reordering. Either a test or one line of comment would keep the precedence from being re-litigated.

### [NOTE] The CLI now has two JSON serialization conventions for its result types

`_print_result` serializes the 223 dataclass results (`HandlePauseResult`, `AnswerResult`) via `json.dumps(asdict(result))`, while the new `_print_model` serializes the 224 pydantic results via `model_dump_json`. Both are the same external boundary and produce the same shape of output, so a reader of `cli/main.py` has to hold both conventions. 224's models are pydantic deliberately (the python rules ask for pydantic at external boundaries), so this is a drift inherited from 223 rather than a mistake in this slice; consolidating would be out of scope here. Worth noting so the next slice that touches a result type picks one.

### [NOTE] Row slicing in the decisions read derives its column widths from splitting the SQL column constants

`_ANSWER_WIDTH` and `_QUESTION_WIDTH` are `len(sql.ANSWER_COLUMNS.split(","))`, and `_decision` slices the joined row with them before handing the pieces to `answer_from_row` and `question_from_row`. The offsets I checked are correct today (11 answer columns, 15 question columns, then `members.program_id` and the prior-answer subquery). The pattern is at least self-updating, and `sql._qualified` already depends on the same comma-splitting of these constants, so it is consistent rather than scattered. The residual risk is that any non-column text added inside those string constants shifts both the widths and the qualification silently. Explicit width constants next to the column constants, or a comment stating the comma-only constraint, would close it. Not blocking.

### [PASS] One definition per concept, with mechanical guards that keep it that way

The D3 table is now a single pure function used by both `handle_pause` and `status`, and the old duplicate — `pause_existing._DELIVERED`, the inline age comparison in `_claimed`, and the eligibility module's own outcome/kind/question checks — are gone rather than left beside the new one. `normalized_citations` is extracted from `check_citations` and consumed by `decisions._cited`, so "what a stored citation means" is one function. `test_read_side_defined_once.py` mechanically pins each vocabulary to one module and `run_list.py` as the only speller of `sq runs list`, and `test_status_matches_handle_pause.py` asserts the two callers agree on every class, which is the property the extraction exists to hold.

### Run Digest

- Response length: 5816 chars
- Response is newline-free: no
- Tool calls made: 36
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 462907
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 2882336 / 2442240 / not computed / 126517 / 122576
- Duration: 924.2 s
- Cost: $0.14 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
