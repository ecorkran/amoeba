---
docType: review
layer: project
reviewType: code
slice: standing-answers
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/230-slice.standing-answers.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: 9786c9310968908327a10518d3ef05566d6f3ccf
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
diffTruncated: false
effort: xhigh
turns: 20
promptTokens: 1114847
cachedTokens: 905058
cacheWriteTokens: 209777
completionTokens: 43549
durationSeconds: 199.7
costUsd: 0.371348
costBasis: provider
runId: run-20261120-p6-fd5a9ca4
squadronVersion: 0.24.34
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "The give-time length check measures raw text, but the cap applies to the rendered passage"
    location: "src/amoeba/operations/standing.py:50"
  - id: F002
    severity: concern
    category: correctness
    summary: "Nothing checks the total standing text against the cap at give time"
    location: "src/amoeba/answering/passages.py:355-362"
  - id: F003
    severity: concern
    category: security-hygiene
    summary: "The MCP write tools rely only on description text, and the code comment misstates their reach"
    location: "src/amoeba/mcp/standing_tools.py:15-21"
  - id: F004
    severity: note
    category: type-contract-debt
    summary: "The passage kind is inferred from a string prefix in `source`"
    location: "src/amoeba/operations/decisions.py#_cited_kind"
  - id: F005
    severity: note
    category: consistency-rot
    summary: "Naming and docstring drift in the new store and wiring modules"
    location: "src/amoeba/store/standing.py:50"
---

# Review: code — slice 230

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 19 successful tool call(s) of 19 made; 150215 of 150215 diff characters reached the model

## Findings

### [CONCERN] The give-time length check measures raw text, but the cap applies to the rendered passage

`standing()` refuses text only when `len(request.text) > max_chars`. The docstring and the TOO_LONG message say that anything at or under the cap can be sent. That is false. `_render_section` (`src/amoeba/answering/passages.py:266-280`) adds about 85 characters of header (`## Passage P1`, `kind:`, `source:`, `date:`, blank lines). So a text of exactly `passages_max_chars` is accepted with `GIVEN`, but its passage is over the cap. Every pause for every member it reaches then ends in `sources_too_large`, until someone withdraws it. `tests/operations/test_standing.py:204-212` pins this wrong behaviour by asserting that the at-cap text is `GIVEN`. Fix it by checking the rendered size of the single passage (`render_passages` of `standing_passage(answer, 1)`), and change that test to expect `TOO_LONG` just over the rendered limit.

### [CONCERN] Nothing checks the total standing text against the cap at give time

Standing passages are never trimmed, and they count in the size check of `assemble`. The `standing` result, though, reports only its own row. One valid call can therefore turn every later pause for every reached member into a wait, and the give call shows nothing. The failure surfaces at pause time, far from the cause. The exits exist (`withdraw`, or raising the cap), and the `too_large_detail` text names both shares, so this is not silent. It is still a design gap the PM should decide on: either the give-time check accounts for the active rulings and the rules already in the set, or `standing` returns a size warning. This must not be deferred to a later slice.

### [CONCERN] The MCP write tools rely only on description text, and the code comment misstates their reach

`standing` with reach `all` writes a ruling that every later automatic answer for every member can cite, until withdrawn. The only control on this is `PM_RULING_RULE`, a sentence in the tool description. The comment at lines 15-21 says a standing answer "gains no power `answer` lacks". That is not accurate in scope. `answer` settles one question, and its precedent stays with that member. A reach-`all` standing answer applies to every member's future questions with no per-question review. The barred-item test (`tests/operations/test_answering_settle.py`) limits the damage, but not the scope. The same comment also says "Slice 231 … owns any stronger control". The Amoeba Design Rules forbid deferring in-scope behaviour, so the PM should confirm that a description-only gate is the intended trust model before merge. The comment should state the trust model accurately.

### [NOTE] The passage kind is inferred from a string prefix in `source`

`_cited_kind` returns `standing_answer` when the stored source starts with `standing:`. The store keeps no kind, and `source` also holds rule paths, which come from PM-supplied configuration. A rule path beginning with `standing:` would be mislabelled. The risk is low. Storing the kind, or validating the prefix at the one place that writes it, would remove the inference.

### [NOTE] Naming and docstring drift in the new store and wiring modules

`give_standing` takes a parameter named `text`, which shadows the `text` row-value helper imported into the same module. `SELECT_WITHDRAWN_AT` (`src/amoeba/store/sql_standing.py:32`) selects a column that `withdraw_standing` never reads, since it checks only for existence. The docstring in `src/amoeba/wiring_standing.py` also has a ragged wrap ("Neither takes" / "the caller's directory").

### Run Digest

- Response length: 6096 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 1114847 / 905058 / 209777 / 43549 / not computed
- Duration: 199.7 s
- Cost: $0.37 (provider)
- `## Summary` located: yes
- `## Findings` located: no
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
