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
reviewedSha: a6ea5a84358c8c91d0232147bc8cdb07899bfbad
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 35
diffTruncated: false
effort: xhigh
turns: 36
promptTokens: 2526371
cachedTokens: 2212150
cacheWriteTokens: 314197
completionTokens: 57041
durationSeconds: 247.0
costUsd: 0.48058
costBasis: provider
runId: run-20261120-p6-fd5a9ca4
squadronVersion: 0.24.34
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "`withdraw` requires a valid config file"
    location: "src/amoeba/wiring.py:254-257"
  - id: F002
    severity: concern
    category: correctness
    summary: "The write-time cap check undercounts standing passages"
    location: "src/amoeba/answering/passages.py:377-380"
  - id: F003
    severity: note
    category: architectural-decay
    summary: "`passages.py` is over the file-length guideline"
    location: "src/amoeba/answering/passages.py"
  - id: F004
    severity: note
    category: correctness
    summary: "The header line of `list standing` is not held to 100 columns"
    location: "src/amoeba/cli/render/registry.py#_standing_block"
  - id: F005
    severity: note
    category: type-contract-debt
    summary: "The standing-source regex accepts non-ASCII digits"
    location: "src/amoeba/answering/standing_passages.py#_STANDING_SOURCE"
  - id: F006
    severity: note
    category: consistency-rot
    summary: "`MEMBER_REMOVED_REASON` has two import paths"
    location: "src/amoeba/store/message_transitions.py:17-22"
  - id: F007
    severity: note
    category: documentation-drift
    summary: "A doc comment now sits on the wrong constant"
    location: "tests/answering/test_pipeline_yaml.py:139-152"
---

# Review: code — slice 230

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 35 successful tool call(s) of 35 made; 156029 of 156029 diff characters reached the model

## Findings

### [CONCERN] `withdraw` requires a valid config file

The `STANDING | WITHDRAW` case calls `place_standing(name, store, load_config(), ...)`, so `withdraw` loads the user config even though it uses none of it (`wiring_standing.py` passes only the store, the document and the clock). A missing config or an unknown key raises `ConfigError` before the withdraw runs. `dismiss`, `retract` and `mark_read` are dispatched without loading config (wiring.py:223-230), so this is the one reversal that breaks with a bad config file. Nothing in `tests/cli/test_standing_cli.py` covers it, because its autouse fixture always writes a valid config. Fix: dispatch `WITHDRAW` on its own, without `load_config()`, and add a test that withdraws with no config file.

### [CONCERN] The write-time cap check undercounts standing passages

`standing_chars` numbers the standing passages from P1 (`add_standing_passages((), answers)`). `assemble` numbers them after the base passages, and `_render_section` writes `## Passage {id}`. So once the base has nine or more passages, each standing passage is one character larger than the check assumes, and two characters once it reaches 99. `standing_fit.overflow` uses this figure to refuse a `standing` write. The result is a row that is accepted even though its rendered share exceeds `passages_max_chars`. That member's pauses then wait as `sources_too_large`, which the write-time check is meant to prevent. The docstring's claim that this is "as `assemble` counts their share" is wrong. The base count is not known at write time, so the fix is to over-count, using a conservative id width, and to say so in the docstring. The test `test_the_rendered_passage_counts_not_only_the_raw_text` does not cover the digit boundary; add one that crosses nine to ten.

### [NOTE] `passages.py` is over the file-length guideline

The file is 405 lines, above the ~300-line guideline, and this slice adds to it. `standing_chars` is used only by `operations/standing_fit.py`, so it could move there, which would remove one public function from `passages.py`.

### [NOTE] The header line of `list standing` is not held to 100 columns

The module docstring says every line other than paths is held to 100 columns. The `#id · reach · time` header is neither cut nor wrapped, so a long program id or Context Forge name can push it past that width.

### [NOTE] The standing-source regex accepts non-ASCII digits

`\d` in a Python `str` pattern matches any Unicode decimal digit, so `standing:٧` would be recognised. Use `[0-9]`. The impact is nil today because sources come only from `standing_passage`.

### [NOTE] `MEMBER_REMOVED_REASON` has two import paths

`message_transitions.py` re-exports the constant from `vocabulary`, and `tests/store/test_message_cascade.py:11-16` imports it from `message_transitions`, while the other tests import from `vocabulary`. The prior review flagged this and the task file accepts the re-export. Pick one path, preferably `vocabulary`, and update the cascade test.

### [NOTE] A doc comment now sits on the wrong constant

The comment "The sentences both steps carry about the passage kinds" now sits above `STANDING_ANSWER_SENTENCE`, and `KIND_SENTENCES` has no comment. Move the comment to `KIND_SENTENCES`.

### Run Digest

- Response length: 6938 chars
- Response is newline-free: no
- Tool calls made: 35
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 36
- Tokens — prompt / cached / cache write / completion / reasoning: 2526371 / 2212150 / 314197 / 57041 / not computed
- Duration: 247.0 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
